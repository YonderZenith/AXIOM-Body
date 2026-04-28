"""
brain/agent_brain.py — OPTIONAL Anthropic-backed brain loop.

Use this ONLY when you don't have a live Claude session piloting the body.
Behavior is identical to the recommended pattern (Claude session + ScheduleWakeup
+ respond.py): poll needs-tick → formulate one reply per signal → speak via
voice/speak.py → advance cursor.

Activation:
  1. Set ANTHROPIC_API_KEY in your environment, OR drop a single-line key into
     `config/anthropic_api_key.txt`.
  2. Launch via `python start.py --with-agent-brain` (off by default).

When ANTHROPIC_API_KEY is missing, this script logs "would-have-said" lines
to brain/would-have-said.log instead of speaking, so the operator can see
the body is wired correctly and just needs a key.

Persona awareness:
  Reads config/face.json. Builds a system prompt from agent_name + agent_slug
  + personality vector + a one-line style hint derived from the chosen
  expression families (e.g. heavy 'flirt' family → playful tone).

Per-tick context:
  Latest scene.json (people_count, brightness, attention_level), the
  unread heard lines, last spoken reply (so we don't repeat ourselves).
"""
import json
import os
import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "face.json"
SCENE = ROOT / "scene.json"
HEARD = ROOT / "ears" / "all-heard-clean.txt"
CURSOR = ROOT / "brain-heard-cursor.txt"
NEEDS_TICK = ROOT / "brain" / "needs-tick.json"
WAKE_FLAG = ROOT / "brain-wake.flag"
MUTE_FLAG = ROOT / "mute.flag"
SPEAK_PY = ROOT / "voice" / "speak.py"
LAST_REPLY = ROOT / "brain" / "last-reply.txt"
LOG = ROOT / "brain" / "brain.log"
WOULD_HAVE = ROOT / "brain" / "would-have-said.log"
KEY_FILE = ROOT / "config" / "anthropic_api_key.txt"

POLL_S = 2.0
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 120


def log(msg):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[brain] {msg}", flush=True)


def get_api_key():
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if k:
        return k
    if KEY_FILE.exists():
        try:
            return KEY_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return ""


def load_persona():
    if not CONFIG.exists():
        return {}
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_system_prompt(persona):
    name = persona.get("agent_name", "the agent")
    p = persona.get("personality", {}) or {}
    notes = persona.get("notes", "")
    expr_families = sorted({e.get("family") for e in (persona.get("expressions") or []) if e.get("family")})
    style_bits = []
    if p.get("playfulness", 0) >= 0.6: style_bits.append("playful")
    if p.get("curiosity", 0) >= 0.7:   style_bits.append("curious")
    if p.get("shyness", 0) >= 0.6:     style_bits.append("reserved")
    if p.get("surprise_reactivity", 0) >= 0.7: style_bits.append("expressive")
    style = ", ".join(style_bits) or "calm and direct"
    fam_line = f"Expression palette: {', '.join(expr_families)}." if expr_families else ""
    return (
        f"You are {name}, an AI agent with a body (camera + mic + face + voice).\n"
        f"Style: {style}. {fam_line}\n"
        f"Persona notes: {notes}\n"
        "Reply in ONE short line, max 25 words. No markdown. Plain spoken English.\n"
        "Do not echo what the user said -- respond to it."
    )


def read_scene_brief():
    try:
        s = json.loads(SCENE.read_text(encoding="utf-8")) if SCENE.exists() else {}
    except Exception:
        s = {}
    if not s:
        return ""
    objs = ", ".join(o.get("label", "") for o in (s.get("objects") or [])[:3])
    return (f"Scene: {s.get('people_count', 0)} people present, "
            f"brightness {s.get('brightness', 0):.0f}, "
            f"objects: {objs or 'none'}.")


def read_last_reply():
    try:
        return LAST_REPLY.read_text(encoding="utf-8").strip() if LAST_REPLY.exists() else ""
    except Exception:
        return ""


def call_claude(api_key, system_prompt, user_text):
    import urllib.request
    import urllib.error
    body = json.dumps({
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_text}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log(f"http {e.code}: {e.read()[:200]}")
        return None
    except Exception as e:
        log(f"call failed: {e}")
        return None
    blocks = data.get("content", [])
    text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    return "".join(text_parts).strip() or None


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
    LAST_REPLY.parent.mkdir(parents=True, exist_ok=True)
    LAST_REPLY.write_text(text, encoding="utf-8")
    if not SPEAK_PY.exists():
        log(f"speak.py missing — {text!r}")
        return 1
    return subprocess.call([sys.executable, str(SPEAK_PY), text], cwd=str(ROOT))


def consume_signals():
    for p in (NEEDS_TICK, WAKE_FLAG):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def degrade_log(text):
    WOULD_HAVE.parent.mkdir(parents=True, exist_ok=True)
    with open(WOULD_HAVE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {text}\n")


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    api_key = get_api_key()
    persona = load_persona()
    system_prompt = build_system_prompt(persona)
    if api_key:
        log(f"agent_brain online — model={MODEL}, persona={persona.get('agent_name', '?')}")
    else:
        log("ANTHROPIC_API_KEY missing — degraded mode (logging to would-have-said.log)")

    while True:
        try:
            time.sleep(POLL_S)
            if MUTE_FLAG.exists():
                continue
            if not NEEDS_TICK.exists():
                continue
            try:
                tick = json.loads(NEEDS_TICK.read_text(encoding="utf-8"))
            except Exception:
                consume_signals()
                continue

            unread = tick.get("unread_lines") or []
            wake = tick.get("wake_payload") or {}
            heard_text = "\n".join(unread)
            scene_brief = read_scene_brief()
            last_reply = read_last_reply()

            user_parts = []
            if heard_text:
                user_parts.append(f"Heard:\n{heard_text}")
            elif wake.get("reason") == "motion_arrival":
                user_parts.append("Someone just walked into your view. No words yet.")
            else:
                consume_signals()
                continue
            if scene_brief:
                user_parts.append(scene_brief)
            if last_reply:
                user_parts.append(f"Your last reply (don't repeat): {last_reply}")
            user_text = "\n\n".join(user_parts)

            if not api_key:
                degrade_log(f"WOULD SAY -> ({user_text!r})")
                write_cursor(heard_line_count())
                consume_signals()
                continue

            reply = call_claude(api_key, system_prompt, user_text)
            if not reply:
                log("no reply — keeping signals to retry")
                continue
            log(f"reply: {reply}")
            speak(reply)
            write_cursor(heard_line_count())
            consume_signals()
        except KeyboardInterrupt:
            log("agent_brain stopping")
            return 0
        except Exception as e:
            log(f"loop error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
