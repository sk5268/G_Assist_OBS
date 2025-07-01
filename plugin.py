import json
import logging
import os
import time
from threading import Thread
from obswebsocket import obsws, requests

CONFIG_PATH = os.path.join(os.environ.get("USERPROFILE", "."), 'config.json')
LOG_PATH = os.path.join(os.environ.get("USERPROFILE", "."), 'obs_voice_plugin.log')

logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class OBSController:
    def __init__(self):
        self.ws = None
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        return {}

    def connect(self):
        try:
            self.ws = obsws(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 4455),
                password=self.config.get('password', '')
            )
            self.ws.connect()
            logging.info("Connected to OBS WebSocket")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to OBS: {str(e)}")
            return False

    def disconnect(self):
        if self.ws:
            self.ws.disconnect()
            self.ws = None

obs = OBSController()

def initialize():
    connected = obs.connect()
    return generate_success_response("Initialized and connected to OBS") if connected else generate_failure_response("Failed to connect to OBS")

def shutdown():
    obs.disconnect()
    return generate_success_response("Disconnected from OBS")

def generate_success_response(message=None):
    return {"success": True, "message": message or "Success"}

def generate_failure_response(message=None):
    return {"success": False, "message": message or "Failure"}

def write_response(response):
    print(json.dumps(response), flush=True)

def read_command():
    try:
        return json.loads(input())
    except Exception as e:
        logging.error(f"Error reading command: {e}")
        return None

def handle_play_brb_scene(props):
    scene = props.get("scene_name") or obs.config.get("brb_scene", "BRB")
    try:
        obs.ws.call(requests.SetCurrentProgramScene(scene))
        return generate_success_response(f"Switched to {scene} scene")
    except Exception as e:
        return generate_failure_response(str(e))

def handle_resume_stream(props):
    scene = props.get("scene_name") or obs.config.get("main_scene", "Main")
    try:
        obs.ws.call(requests.SetCurrentProgramScene(scene))
        return generate_success_response(f"Resumed to {scene} scene")
    except Exception as e:
        return generate_failure_response(str(e))

def handle_mute_mic(props):
    source = props.get("mic_source") or obs.config.get("mic_source", "Mic/Aux")
    try:
        current = obs.ws.call(requests.GetInputMute(source)).get_muted()
        obs.ws.call(requests.SetInputMute(source, not current))
        return generate_success_response(f"Toggled mute for {source}")
    except Exception as e:
        return generate_failure_response(str(e))

def handle_play_intro(props):
    scene = props.get("scene_name") or obs.config.get("intro_scene", "Intro")
    try:
        obs.ws.call(requests.SetCurrentProgramScene(scene))
        return generate_success_response(f"Switched to {scene} scene")
    except Exception as e:
        return generate_failure_response(str(e))

def handle_play_outro(props):
    scene = props.get("scene_name") or obs.config.get("outro_scene", "Outro")
    try:
        obs.ws.call(requests.SetCurrentProgramScene(scene))
        return generate_success_response(f"Switched to {scene} scene")
    except Exception as e:
        return generate_failure_response(str(e))

def handle_run_sponsor_break(props):
    sponsor = props.get("sponsor_scene") or obs.config.get("sponsor_scene", "Sponsor")
    main = props.get("main_scene") or obs.config.get("main_scene", "Main")

    def switch_back():
        time.sleep(60)
        try:
            obs.ws.call(requests.SetCurrentProgramScene(main))
            logging.info("Returned to main scene")
        except Exception as e:
            logging.error(f"Error returning to main scene: {e}")

    try:
        obs.ws.call(requests.SetCurrentProgramScene(sponsor))
        Thread(target=switch_back).start()
        return generate_success_response(f"Showing sponsor scene: {sponsor}")
    except Exception as e:
        return generate_failure_response(str(e))

def handle_clip_last_30_seconds(_):
    try:
        obs.ws.call(requests.SaveReplayBuffer())
        return generate_success_response("Clip of last 30 seconds saved")
    except Exception as e:
        return generate_failure_response(str(e))

function_map = {
    "initialize": initialize,
    "shutdown": shutdown,
    "play_brb_scene": handle_play_brb_scene,
    "resume_stream": handle_resume_stream,
    "mute_mic": handle_mute_mic,
    "play_intro": handle_play_intro,
    "play_outro": handle_play_outro,
    "run_sponsor_break": handle_run_sponsor_break,
    "clip_last_30_seconds": handle_clip_last_30_seconds,
}

def main():
    while True:
        command = read_command()
        if not command:
            continue
        if "tool_calls" not in command:
            write_response(generate_failure_response("Missing tool_calls"))
            continue

        for tool_call in command["tool_calls"]:
            name = tool_call.get("func")
            props = tool_call.get("properties", {})
            if name in function_map:
                result = function_map[name](props)
            else:
                result = generate_failure_response(f"Unknown function: {name}")
            write_response(result)
            if name == "shutdown":
                return

if __name__ == '__main__':
    main()