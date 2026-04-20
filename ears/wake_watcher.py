"""
AXIOM Wake Watcher — motion + speech + sound wake daemon
=========================================================
Pre-computes "is there something worth waking the brain for" into a
single file (brain-wake.flag) so the brain's cron just reads one file
and exits fast when there's nothing. Also appends every wake event to
wake-events.jsonl for A/B latency analysis.

Wake triggers (in order of latency, fastest first):
  - sound_gate       : listener amp-gate fired (pre-VAD raw audio) — sub-second
  - speech_detected  : listener VAD confirmed speech onset — ~100ms after sound
  - new_speech       : Whisper finished a full utterance -> new-speech.flag
  - motion_arrival   : people_count transitions 0 -> N
  - presence_tick    : warm re-check every TICK_SEC while people visible

Sources:
  - scene.json               (vision daemon)
  - ears/new-speech.flag     (brain_poll daemon)
  - listener.log             (tail — sound_gate + speech_detected)

Outputs:
  - brain-wake.flag          (single payload the brain reads + deletes)
  - wake-events.jsonl        (one line per wake, metrics for A/B)
  - wake-watcher.log         (human-readable operator log)

The brain is expected to delete brain-wake.flag after handling. If it
doesn't, we won't re-write until a NEW trigger fires -- so snoozing is
safe.
"""
import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENE_FILE = ROOT / "scene.json"
SPEECH_FLAG = ROOT / "ears" / "new-speech.flag"
LISTENER_LOG = ROOT / "listener.log"
WAKE_FLAG = ROOT / "brain-wake.flag"
OPS_LOG = ROOT / "wake-watcher.log"
METRICS = ROOT / "wake-events.jsonl"

# Log-line signatures we tail for fast wake. Listener prints these via log().
SOUND_GATE_MARK = "Ears waking on sound"
SPEECH_DETECT_MARK = "Speech detected, recording"

_write_lock = threading.Lock()


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(OPS_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_scene():
    try:
        with open(SCENE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def read_speech_flag():
    if not SPEECH_FLAG.exists():
        return None
    try:
        with open(SPEECH_FLAG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def append_metrics(entry):
    try:
        with open(METRICS, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log(f"metrics write failed: {e}")


def write_wake(reason, scene, speech, extra=None, source="watcher"):
    """Serialized wake-flag write + JSONL metrics append."""
    with _write_lock:
        now_iso = datetime.now().isoformat()
        payload = {
            "reason": reason,
            "source": source,
            "written_at": now_iso,
            "people_count": scene.get("people_count", 0) if scene else 0,
            "gaze_target": scene.get("gaze_target") if scene else None,
            "attention_level": scene.get("attention_level") if scene else None,
            "brightness": scene.get("brightness") if scene else None,
            "speech": speech,
        }
        if extra:
            payload.update(extra)
        tmp = str(WAKE_FLAG) + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp, WAKE_FLAG)
        except Exception as e:
            log(f"wake flag write failed: {e}")
            return
        append_metrics({
            "ts": now_iso,
            "source": source,
            "reason": reason,
            "people_count": payload["people_count"],
            "extra": extra or {},
        })
        log(f"wake -> {reason} [{source}] (people={payload['people_count']})")


# ----------------------- listener.log tail thread -----------------------

def _tail_listener_log(state, cooldowns):
    """Follow listener.log and fire fast wakes on sound/speech marks.

    Opens the file, seeks to end, polls for new content. Survives log
    rotation via inode/size checks every poll cycle.
    """
    path = LISTENER_LOG
    log(f"tail-thread attaching to {path}")
    fh = None
    last_inode = None
    last_size = 0
    while not state.get("stop"):
        try:
            if not path.exists():
                time.sleep(1.0)
                continue
            st = path.stat()
            # re-open on rotation or first attach
            if fh is None or st.st_ino != last_inode or st.st_size < last_size:
                try:
                    if fh:
                        fh.close()
                except Exception:
                    pass
                fh = open(path, "r", encoding="utf-8", errors="replace")
                fh.seek(0, 2)  # start at end — we only care about NEW lines
                last_inode = st.st_ino
                last_size = st.st_size
                log(f"tail-thread: attached at offset {fh.tell()}")

            line = fh.readline()
            if not line:
                last_size = st.st_size
                time.sleep(0.2)
                continue

            now = time.time()
            scene = read_scene()

            if SOUND_GATE_MARK in line:
                if now - cooldowns["sound_gate"] > 3.0:
                    write_wake(
                        "sound_gate", scene, read_speech_flag(),
                        extra={"log_line": line.strip()[-200:]},
                        source="listener_log",
                    )
                    cooldowns["sound_gate"] = now
            elif SPEECH_DETECT_MARK in line:
                if now - cooldowns["speech_detected"] > 2.0:
                    write_wake(
                        "speech_detected", scene, read_speech_flag(),
                        extra={"log_line": line.strip()[-200:]},
                        source="listener_log",
                    )
                    cooldowns["speech_detected"] = now
        except Exception as e:
            log(f"tail-thread error: {e}")
            time.sleep(1.0)


# ----------------------- main loop (scene + flag watcher) -----------------------

def main():
    parser = argparse.ArgumentParser(description="AXIOM wake watcher")
    parser.add_argument("--poll", type=float, default=2.0, help="scene poll interval seconds")
    parser.add_argument("--tick", type=int, default=60, help="presence_tick seconds")
    parser.add_argument("--motion-cooldown", type=int, default=8, help="seconds between motion_arrival fires")
    parser.add_argument("--no-tail", action="store_true", help="disable listener.log tail thread (scene-only mode)")
    args = parser.parse_args()

    log(f"wake_watcher v2 starting  poll={args.poll}s tick={args.tick}s tail={'off' if args.no_tail else 'on'}")

    state = {"stop": False}
    cooldowns = {"sound_gate": 0.0, "speech_detected": 0.0}

    tail_thread = None
    if not args.no_tail:
        tail_thread = threading.Thread(
            target=_tail_listener_log, args=(state, cooldowns),
            name="wake-tail", daemon=True,
        )
        tail_thread.start()

    last_people = 0
    last_speech_ts = None
    last_motion_fire = 0.0
    last_presence_tick = 0.0

    scene0 = read_scene()
    last_people = scene0.get("people_count", 0)
    sp0 = read_speech_flag()
    last_speech_ts = sp0.get("timestamp") if sp0 else None

    try:
        while True:
            try:
                scene = read_scene()
                people = scene.get("people_count", 0)
                now = time.time()

                if people > 0 and last_people == 0 and (now - last_motion_fire) > args.motion_cooldown:
                    write_wake(
                        "motion_arrival", scene, read_speech_flag(),
                        extra={"transition": f"0->{people}"},
                        source="scene",
                    )
                    last_motion_fire = now
                    last_presence_tick = now

                sp = read_speech_flag()
                sp_ts = sp.get("timestamp") if sp else None
                if sp_ts and sp_ts != last_speech_ts:
                    write_wake("new_speech", scene, sp, source="speech_flag")
                    last_speech_ts = sp_ts
                    last_presence_tick = now

                if people > 0 and (now - last_presence_tick) > args.tick:
                    write_wake("presence_tick", scene, sp, source="scene")
                    last_presence_tick = now

                last_people = people
                time.sleep(args.poll)
            except Exception as e:
                log(f"main-loop error: {e}")
                time.sleep(args.poll)
    except KeyboardInterrupt:
        state["stop"] = True
        log("wake_watcher stopped")


if __name__ == "__main__":
    main()
