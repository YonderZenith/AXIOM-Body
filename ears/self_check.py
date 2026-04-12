"""
AXIOM Self-Awareness Check
===========================
Writes axiom/ears/status.json with current system health.
Brain session reads this to know its own state.

Usage:
  python self_check.py          # One-shot status check
  python self_check.py --loop   # Continuous monitoring (every 15s)
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EARS_DIR = os.path.join(BASE_DIR, "axiom", "ears")
STATUS_FILE = os.path.join(EARS_DIR, "status.json")
SCENE_FILE = os.path.join(EARS_DIR, "scene.json")
STREAM_FILE = os.path.join(EARS_DIR, "heard-stream.txt")
LISTENER_LOG = os.path.join(EARS_DIR, "listener-log.txt")
VOICE_LOOP_LOG = os.path.join(EARS_DIR, "voice-loop-log.txt")
MUTE_FILE = os.path.join(EARS_DIR, "mute.flag")
FLAG_FILE = os.path.join(EARS_DIR, "new-speech.flag")

# Set PYTHON to the python executable on your system (e.g. "python3" or full path)
PYTHON = sys.executable

DAEMON_SIGNATURES = {
    "listener": "listener.py",
    "voice_loop": "voice_loop.py",
    "vision": "vision.py",
    "idle": "idle.py",
    "brain_poll": "brain_poll.py",
}


def get_running_daemons():
    """Check which AXIOM daemons are running via tasklist."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Select-Object ProcessId, CommandLine | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        processes = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(processes, dict):
            processes = [processes]
    except Exception:
        return {}

    running = {}
    for proc in processes:
        cmd = proc.get("CommandLine", "") or ""
        pid = proc.get("ProcessId", 0)
        for name, sig in DAEMON_SIGNATURES.items():
            if sig in cmd:
                running[name] = {"pid": pid, "cmd_snippet": sig}
    return running


def get_scene():
    """Read current scene data."""
    try:
        with open(SCENE_FILE, "r", encoding="utf-8") as f:
            scene = json.load(f)
        age = (datetime.now() - datetime.fromisoformat(scene["timestamp"])).total_seconds()
        return {
            "people_count": scene.get("people_count", 0),
            "brightness": round(scene.get("brightness", 0), 1),
            "age_seconds": round(age, 1),
            "stale": age > 30,
        }
    except Exception:
        return {"people_count": -1, "brightness": -1, "age_seconds": -1, "stale": True}


def get_ears_state():
    """Check listener/voice_loop log for current state."""
    for log_file in [LISTENER_LOG, VOICE_LOOP_LOG]:
        if not os.path.exists(log_file):
            continue
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                continue
            last_line = lines[-1].strip()
            # Parse timestamp
            if last_line.startswith("[") and "]" in last_line:
                ts_str = last_line[1:last_line.index("]")]
                msg = last_line[last_line.index("]") + 2:]
                # Determine state from message
                if "sleeping" in msg.lower():
                    state = "sleeping"
                elif "waking" in msg.lower():
                    state = "awake"
                elif "recording" in msg.lower():
                    state = "recording"
                elif "heard" in msg.lower():
                    state = "heard_speech"
                elif "listening" in msg.lower() or "active" in msg.lower():
                    state = "listening"
                else:
                    state = "active"
                return {
                    "state": state,
                    "last_log": msg,
                    "last_time": ts_str,
                    "source": os.path.basename(log_file),
                }
        except Exception:
            continue
    return {"state": "unknown", "last_log": "", "last_time": "", "source": "none"}


def get_last_heard():
    """Get the most recent speech from heard-stream.txt."""
    try:
        with open(STREAM_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            last = lines[-1].strip()
            count = len(lines)
            return {"last_speech": last, "total_lines": count}
    except Exception:
        pass
    return {"last_speech": "", "total_lines": 0}


def get_voice_state():
    """Check if currently speaking (mute.flag exists)."""
    return {
        "speaking": os.path.exists(MUTE_FILE),
        "pending_flag": os.path.exists(FLAG_FILE),
    }


def run_check():
    """Run full self-awareness check and write status.json."""
    daemons = get_running_daemons()
    scene = get_scene()
    ears = get_ears_state()
    heard = get_last_heard()
    voice = get_voice_state()

    # Determine overall health
    issues = []
    has_ears = "listener" in daemons or "voice_loop" in daemons
    has_eyes = "vision" in daemons
    has_face = "idle" in daemons

    if not has_ears:
        issues.append("NO EARS - listener/voice_loop not running")
    if not has_eyes:
        issues.append("NO EYES - vision.py not running")
    if not has_face:
        issues.append("NO FACE - idle.py not running")
    if scene["stale"]:
        issues.append(f"STALE SCENE - {scene['age_seconds']}s old")
    if ears["state"] == "unknown":
        issues.append("EARS STATE UNKNOWN - no log data")

    health = "HEALTHY" if not issues else "DEGRADED"
    if not has_ears and not has_eyes:
        health = "CRITICAL"

    # Conscious state summary
    if scene["people_count"] > 0 and has_ears:
        conscious = "ENGAGED - person present, ears active"
    elif scene["people_count"] > 0 and not has_ears:
        conscious = "BLIND-DEAF - person present but can't hear"
    elif scene["people_count"] == 0 and ears["state"] == "sleeping":
        conscious = "STANDBY - no people, ears sleeping"
    elif scene["people_count"] == 0 and has_ears:
        conscious = "ALERT - no people, ears listening"
    else:
        conscious = "UNKNOWN"

    status = {
        "timestamp": datetime.now().isoformat(),
        "health": health,
        "conscious_state": conscious,
        "issues": issues,
        "daemons": daemons,
        "scene": scene,
        "ears": ears,
        "last_heard": heard,
        "voice": voice,
    }

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

    return status


def print_status(status):
    """Human-readable status output."""
    print(f"=== AXIOM Self-Check [{status['timestamp'][:19]}] ===")
    print(f"Health: {status['health']}")
    print(f"State:  {status['conscious_state']}")
    if status["issues"]:
        print(f"Issues: {', '.join(status['issues'])}")
    print(f"Scene:  {status['scene']['people_count']} people, brightness {status['scene']['brightness']}")
    print(f"Ears:   {status['ears']['state']} ({status['ears']['source']})")
    print(f"Voice:  {'SPEAKING' if status['voice']['speaking'] else 'quiet'}")
    print(f"Heard:  {status['last_heard']['total_lines']} total, last: {status['last_heard']['last_speech'][:60]}")
    dnames = list(status["daemons"].keys())
    print(f"Daemons: {', '.join(dnames) if dnames else 'NONE'}")


if __name__ == "__main__":
    loop = "--loop" in sys.argv
    status = run_check()
    print_status(status)

    if loop:
        print("\n--- Continuous monitoring (15s interval) ---")
        while True:
            time.sleep(15)
            try:
                status = run_check()
                print_status(status)
                print()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
