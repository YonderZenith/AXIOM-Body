"""
brain/respond.py — reply helper for the agent brain.

Usage:
  python brain/respond.py "your one-line reply"
  echo "reply" | python brain/respond.py -

What it does, atomically:
  1. Speaks the reply via voice/speak.py (ElevenLabs → SAPI fallback).
  2. Advances brain-heard-cursor.txt to the current line-count of all-heard-clean.
  3. Clears brain/needs-tick.json.
  4. Deletes brain-wake.flag.

The agent's main brain (its Claude session) calls this once per tick after
formulating a reply. The atomicity guarantees the same lines never get
replied to twice.
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEARD = ROOT / "ears" / "all-heard-clean.txt"
CURSOR = ROOT / "brain-heard-cursor.txt"
NEEDS_TICK = ROOT / "brain" / "needs-tick.json"
WAKE_FLAG = ROOT / "brain-wake.flag"
SPEAK_PY = ROOT / "voice" / "speak.py"


def heard_line_count():
    if not HEARD.exists():
        return 0
    with open(HEARD, "r", encoding="utf-8") as f:
        return sum(1 for ln in f if ln.strip())


def write_cursor(n):
    tmp = str(CURSOR) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(n))
    os.replace(tmp, CURSOR)


def speak(text):
    if not SPEAK_PY.exists():
        print(f"[respond] {SPEAK_PY} missing — cannot speak", file=sys.stderr)
        return 1
    try:
        return subprocess.call([sys.executable, str(SPEAK_PY), text], cwd=str(ROOT))
    except Exception as e:
        print(f"[respond] speak failed: {e}", file=sys.stderr)
        return 1


def clear_signals():
    for p in (NEEDS_TICK, WAKE_FLAG):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    arg = sys.argv[1]
    text = sys.stdin.read().strip() if arg == "-" else " ".join(sys.argv[1:])
    text = text.strip()
    if not text:
        print("[respond] empty reply — nothing to speak", file=sys.stderr)
        return 2

    rc = speak(text)
    if rc != 0:
        print(f"[respond] speak.py exited {rc}; advancing cursor anyway to avoid replay loop",
              file=sys.stderr)
    write_cursor(heard_line_count())
    clear_signals()
    return 0


if __name__ == "__main__":
    sys.exit(main())
