"""
brain/brain_monitor.py — surfaces state changes for the agent-brain.

The brain IS the running agent's Claude session, NOT this script. This sidecar
just maintains a tiny "needs-attention" flag the agent reads on each
ScheduleWakeup tick. No LLM calls. No API keys. Just state-watching.

Loop, every POLL_S:
  - Read all-heard-clean.txt line count vs brain-heard-cursor.txt.
  - Read brain-wake.flag for motion/presence events.
  - If either has new content AND mute.flag absent, write/update
    `brain/needs-tick.json` summarizing what's new (including the unread
    lines themselves, so the agent doesn't have to re-read the sheet).
  - If nothing new, ensure the flag is absent.

The agent checks `brain/needs-tick.json` each tick. If present, agent reads
the unread_lines + scene + latest_snap, formulates ONE reply in its own
context, calls `python brain/respond.py "<reply>"`. respond.py speaks via
voice/speak.py, advances the cursor, and clears needs-tick.json + wake flag.
"""
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEARD = ROOT / "ears" / "all-heard-clean.txt"
CURSOR = ROOT / "brain-heard-cursor.txt"
WAKE_FLAG = ROOT / "brain-wake.flag"
MUTE_FLAG = ROOT / "mute.flag"
NEEDS_TICK = ROOT / "brain" / "needs-tick.json"
LOG = ROOT / "brain" / "monitor.log"

POLL_S = 1.0
MAX_NEW_LINES_IN_PAYLOAD = 20  # cap so first-tick after long absence doesn't blow up


def log(msg):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[brain-mon] {msg}", flush=True)


def heard_lines():
    if not HEARD.exists():
        return []
    with open(HEARD, "r", encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]


def read_cursor():
    if not CURSOR.exists():
        return None
    try:
        return int(CURSOR.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def write_cursor(n):
    tmp = str(CURSOR) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(n))
    os.replace(tmp, CURSOR)


def write_needs_tick(payload):
    NEEDS_TICK.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(NEEDS_TICK) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, NEEDS_TICK)


def clear_needs_tick():
    if NEEDS_TICK.exists():
        try:
            NEEDS_TICK.unlink()
        except Exception:
            pass


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    cursor = read_cursor()
    if cursor is None:
        cursor = len(heard_lines())
        write_cursor(cursor)
        log(f"cursor initialized at line {cursor} (no replay flood on first run)")
    log("monitor running — agent brain handles ticks via its own session")

    while True:
        try:
            time.sleep(POLL_S)

            if MUTE_FLAG.exists():
                continue  # we're speaking — don't pile up signals

            lines = heard_lines()
            if cursor > len(lines):
                cursor = len(lines)  # cleaned sheet shrank (rotation)
                write_cursor(cursor)

            new_count = max(0, len(lines) - cursor)
            unread = lines[cursor:cursor + MAX_NEW_LINES_IN_PAYLOAD] if new_count else []

            wake_payload = None
            if WAKE_FLAG.exists():
                try:
                    wake_payload = json.loads(WAKE_FLAG.read_text(encoding="utf-8"))
                except Exception:
                    wake_payload = None

            should_signal = False
            reasons = []
            if new_count > 0:
                should_signal = True
                reasons.append(f"speech:{new_count}")
            if wake_payload and wake_payload.get("reason") in {"motion_arrival", "presence_tick"}:
                should_signal = True
                reasons.append(f"wake:{wake_payload['reason']}")

            if should_signal:
                write_needs_tick({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "reasons": reasons,
                    "unread_lines": unread,
                    "unread_speech_count": new_count,
                    "cursor": cursor,
                    "total_lines": len(lines),
                    "wake_payload": wake_payload,
                })
            else:
                clear_needs_tick()
        except KeyboardInterrupt:
            log("monitor stopping")
            return 0
        except Exception as e:
            log(f"loop error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()
