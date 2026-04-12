"""
AXIOM Brain Poller — Adaptive heard.txt watcher
=================================================
Monitors scene.json for people presence and heard.txt for new speech.
When people are detected, polls every 5s (active mode).
When nobody's around, polls every 60s (idle mode).

Writes new-speech.flag when new speech is detected, so the brain
session can check one file instead of manually polling.

Usage:
  python brain_poll.py
"""
import os
import sys
import time
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEARD_FILE = os.path.join(BASE_DIR, "heard.txt")
SCENE_FILE = os.path.join(BASE_DIR, "scene.json")
FLAG_FILE = os.path.join(BASE_DIR, "new-speech.flag")
LOG_FILE = os.path.join(BASE_DIR, "brain-poll-log.txt")

# Polling intervals
ACTIVE_INTERVAL = 5    # seconds when people detected
IDLE_INTERVAL = 60     # seconds when nobody around
WARM_INTERVAL = 15     # seconds after person leaves (cooldown)
WARM_DURATION = 120    # stay warm for 2 min after person leaves


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def read_scene():
    if not os.path.exists(SCENE_FILE):
        return 0, 0.0
    try:
        with open(SCENE_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return d.get("people_count", 0), d.get("brightness", 0.0)
    except:
        return 0, 0.0


def read_heard():
    if not os.path.exists(HEARD_FILE):
        return None, None
    try:
        with open(HEARD_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return d.get("text"), d.get("timestamp")
    except:
        return None, None


def write_flag(text, timestamp, people, brightness):
    """Write flag file that brain session checks"""
    data = {
        "text": text,
        "timestamp": timestamp,
        "people_nearby": people,
        "brightness": brightness,
        "flagged_at": datetime.now().isoformat(),
    }
    with open(FLAG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def main():
    log("Brain poller starting — adaptive mode")

    last_heard_ts = None
    last_person_time = 0
    mode = "idle"

    # Initialize with current heard.txt timestamp so we don't re-flag old speech
    _, last_heard_ts = read_heard()
    log(f"Initial heard timestamp: {last_heard_ts}")

    while True:
        try:
            people, brightness = read_scene()
            now = time.time()

            # Determine polling mode
            if people > 0:
                last_person_time = now
                new_mode = "active"
                interval = ACTIVE_INTERVAL
            elif now - last_person_time < WARM_DURATION:
                new_mode = "warm"
                interval = WARM_INTERVAL
            else:
                new_mode = "idle"
                interval = IDLE_INTERVAL

            if new_mode != mode:
                log(f"Mode: {mode} -> {new_mode} (people={people}, brightness={brightness:.0f})")
                mode = new_mode

            # Check for new speech
            text, ts = read_heard()
            if ts and ts != last_heard_ts:
                last_heard_ts = ts
                log(f"NEW SPEECH: \"{text[:80]}\" (mode={mode})")
                write_flag(text, ts, people, brightness)

            time.sleep(interval)

        except KeyboardInterrupt:
            log("Brain poller stopped")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
