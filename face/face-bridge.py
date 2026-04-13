"""
AXIOM Face Bridge — connects the body system to the web face renderer.

Reads mute.flag (created by respond.py when speaking) and writes
face-state.json for web-face.html to consume via fetch().

Usage:
  python face-bridge.py

Runs from the face/ directory. Writes face-state.json alongside itself.
"""

import os
import sys
import json
import time
import random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

MUTE_FILE = os.path.join(BASE_DIR, "axiom", "ears", "mute.flag")
STATE_FILE = os.path.join(SCRIPT_DIR, "face-state.json")

POLL_INTERVAL = 0.08  # 80ms — slightly faster than the renderer's 100ms poll


def write_state(mode, mouth=0, look_x=0, look_y=0):
    """Atomically write face-state.json."""
    data = {
        "mode": mode,
        "mouth": mouth,
        "look_x": look_x,
        "look_y": look_y,
    }
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    # Atomic rename (works on Windows if same drive)
    try:
        os.replace(tmp, STATE_FILE)
    except OSError:
        # Fallback: direct write
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)


def is_speaking():
    """Check if mute.flag exists (respond.py creates it while speaking)."""
    return os.path.exists(MUTE_FILE)


def main():
    print(f"[face-bridge] Watching: {MUTE_FILE}")
    print(f"[face-bridge] Writing:  {STATE_FILE}")
    print(f"[face-bridge] Press Ctrl+C to stop.\n")

    was_speaking = False
    mouth_cycle = 0
    idle_timer = 0

    # Mouth animation sequence for speaking — cycles through shapes
    MOUTH_SEQ = [1, 2, 3, 2, 1, 0, 1, 2, 2, 3, 2, 1, 0, 0]

    try:
        while True:
            speaking = is_speaking()

            if speaking:
                # Animate mouth while speaking
                mouth_val = MOUTH_SEQ[mouth_cycle % len(MOUTH_SEQ)]
                # Add some randomness
                if random.random() < 0.3:
                    mouth_val = random.randint(0, 3)
                write_state("speaking", mouth=mouth_val)
                mouth_cycle += 1
                was_speaking = True
            else:
                if was_speaking:
                    # Just finished speaking — close mouth
                    write_state("idle", mouth=0)
                    was_speaking = False
                    mouth_cycle = 0
                    idle_timer = 0
                else:
                    # Idle — let the web renderer handle autonomous animations
                    idle_timer += POLL_INTERVAL
                    write_state("idle", mouth=0)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[face-bridge] Stopped.")
        # Clean up — write idle state
        write_state("idle", mouth=0)


if __name__ == "__main__":
    main()
