"""
Sheet maintainer — cleans ears/all-heard.txt into ears/all-heard-clean.txt

Watches the raw append-only transcript sheet and mirrors each new line to a
cleaned parallel sheet with:
  1. Repeated-word collapse ("hello hello hello hello" -> "hello hello", max 2)
  2. Punctuation normalization (".." -> ".", double spaces, etc.)
  3. Drop known Whisper hallucination patterns (bracket tags, punctuation-only)
  4. Drop lines with <3 chars of real content
  5. Preserve "[HH:MM:SS] " timestamp prefix

The brain reads the CLEAN sheet, not the raw one. Raw stays pristine for audit
(and the listener keeps appending to it while we clean — no race, because we
only read past the last byte offset we've processed, via a tiny state file).

Usage:
  python ears/sheet_maintainer.py                 # follow-mode from last pos
  python ears/sheet_maintainer.py --from-start    # wipe clean sheet, rebuild
"""
import argparse
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_SHEET = ROOT / "ears" / "all-heard.txt"
CLEAN_SHEET = ROOT / "ears" / "all-heard-clean.txt"
STATE = ROOT / "ears" / ".sheet-maintainer-pos"

LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")

HALLUCINATION_PATTERNS = [
    re.compile(r"^\[.*\]$"),               # [MUSIC], [APPLAUSE], [silence]
    re.compile(r"^[\.\?,!]+$"),            # punctuation-only lines
    re.compile(r"^\u266a+$"),              # music-note hallucinations
]


def collapse_word_runs(text, max_run=2):
    """'hello hello hello hello' -> 'hello hello'. Case-insensitive, punct-trimmed key."""
    words = text.split()
    if not words:
        return text
    out = [words[0]]
    run_key = words[0].lower().rstrip(".,!?\"'")
    run_len = 1
    for w in words[1:]:
        key = w.lower().rstrip(".,!?\"'")
        if key and key == run_key:
            run_len += 1
            if run_len <= max_run:
                out.append(w)
        else:
            run_key = key
            run_len = 1
            out.append(w)
    return " ".join(out)


def normalize_punct(text):
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"\!{2,}", "!", text)
    text = re.sub(r"\s+([.,!?])", r"\1", text)
    return text


def is_noise(text):
    t = text.strip()
    if len(t) < 3:
        return True
    for pat in HALLUCINATION_PATTERNS:
        if pat.match(t):
            return True
    return False


def clean_line(line):
    line = line.rstrip("\n").rstrip("\r")
    m = LINE_RE.match(line)
    if not m:
        return None
    ts, text = m.groups()
    text = collapse_word_runs(text)
    text = normalize_punct(text)
    if is_noise(text):
        return None
    return f"[{ts}] {text}\n"


def read_pos():
    if STATE.exists():
        try:
            return int(STATE.read_text().strip())
        except Exception:
            return 0
    return 0


def write_pos(pos):
    STATE.write_text(str(pos))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll", type=float, default=1.5, help="seconds between checks")
    parser.add_argument("--from-start", action="store_true", help="wipe clean sheet, rebuild from beginning of raw")
    args = parser.parse_args()

    if args.from_start:
        CLEAN_SHEET.write_text("", encoding="utf-8")
        write_pos(0)
        print(f"[sheet_maintainer] rebuilding clean sheet from start")

    print(f"[sheet_maintainer] watching {RAW_SHEET} -> {CLEAN_SHEET} (poll {args.poll}s)", flush=True)

    while True:
        try:
            if not RAW_SHEET.exists():
                time.sleep(args.poll)
                continue
            pos = read_pos()
            size = RAW_SHEET.stat().st_size
            if size < pos:
                pos = 0  # file truncated/rotated
            if size == pos:
                time.sleep(args.poll)
                continue

            with open(RAW_SHEET, "rb") as f:
                f.seek(pos)
                chunk = f.read()

            text = chunk.decode("utf-8", errors="replace")
            new_pos = pos + len(chunk)

            # If we grabbed a partial last line, rewind so we process it fully next tick
            if not text.endswith("\n"):
                last_nl = text.rfind("\n")
                if last_nl == -1:
                    time.sleep(args.poll)
                    continue
                partial = text[last_nl + 1:]
                new_pos -= len(partial.encode("utf-8"))
                text = text[: last_nl + 1]

            out = []
            dropped = 0
            for ln in text.split("\n"):
                if not ln.strip():
                    continue
                cleaned = clean_line(ln)
                if cleaned:
                    out.append(cleaned)
                else:
                    dropped += 1

            if out:
                with open(CLEAN_SHEET, "a", encoding="utf-8") as f:
                    f.writelines(out)
                print(f"[sheet_maintainer] +{len(out)} lines, dropped {dropped}", flush=True)

            write_pos(new_pos)
            time.sleep(args.poll)
        except KeyboardInterrupt:
            print("[sheet_maintainer] stopped")
            return
        except Exception as e:
            print(f"[sheet_maintainer] error: {e}", flush=True)
            time.sleep(args.poll)


if __name__ == "__main__":
    main()
