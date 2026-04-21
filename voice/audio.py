"""
audio.py — single-entrypoint audio toolkit for AXIOM-Body.

Replaces a sprawl of one-off shell invocations. All ElevenLabs audio surfaces
(TTS, sound effects, voice browsing) live under one CLI with subcommands.

Usage:
  python voice/audio.py sfx "warm magical chime"
  python voice/audio.py sfx "airhorn triple" --seconds 2 --keep
  python voice/audio.py sfx <alias>                   # fire a curated preset
  python voice/audio.py preset ls                     # list curated presets
  python voice/audio.py voice ls                      # list EL shared voices (top page)
  python voice/audio.py voice ls --search british     # filter the shared catalog
  python voice/audio.py voice try <voice-id> <text>   # one-shot TTS with any voice
  python voice/audio.py voice mine                    # list your own EL voices

Speech for Ysmara (persona + lip-sync) still lives in speak.py — that path is
unchanged. This toolkit is for everything else that wants an EL audio surface.
"""
import argparse
import base64
import ctypes
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY_FILE = ROOT / "config" / "elevenlabs_api_key.txt"
BANK_DIR = ROOT / "voice" / "sfx-bank"

# Curated SFX presets — short text prompts I'd actually reach for in the
# build-ship-test loop. Aliases are free to call from the brain later, so we
# keep the names short + lowercase + underscore.
PRESETS = {
    "chime":        ("warm magical chime with soft sparkle tail", 2.0),
    "ping":         ("bubbly sci-fi notification ping", 1.0),
    "thud":         ("deep cinematic bass thump impact, brief", 1.0),
    "whoosh":       ("short sci-fi portal whoosh, high to low", 2.0),
    "coin":         ("retro 8-bit arcade coin pickup", 1.0),
    "rimshot":      ("rimshot badum tss drum sting, joke punchline", 2.0),
    "airhorn":      ("airhorn blast triple short, party horn", 2.0),
    "cheer":        ("stadium crowd cheer burst, celebration, short", 3.0),
    "fanfare":      ("victory fanfare orchestra short triumphant", 3.0),
    "scratch":      ("record scratch dramatic stop, vinyl screech", 1.0),
    "kazoo":        ("solo kazoo melody, playful, short phrase", 3.0),
    "sad_trombone": ("sad trombone wah wah wah waaah", 3.0),
    "ship_it":      ("soft triumphant chime with a short sparkle tail", 2.0),
    "oops":         ("gentle retro error buzz, brief", 1.0),
    "wake":         ("soft morning chime, warm, single bell", 2.0),
    "sleep":        ("low ambient hum fading out, calm", 3.0),
    "typing":       ("rapid mechanical keyboard typing burst", 2.0),
}


def read_api_key():
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if k:
        return k
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    return ""


def _http(method, url, api_key, body=None, accept="application/json"):
    headers = {"xi-api-key": api_key, "Accept": accept}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, "", e.read()
    except Exception as e:
        return 0, "", str(e).encode("utf-8")


def play_mci(path):
    try:
        mci = ctypes.windll.winmm.mciSendStringW
        alias = f"aud{int(time.time() * 1000)}"
        mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0)
        mci(f'play {alias} wait', None, 0, 0)
        mci(f'close {alias}', None, 0, 0)
        return True
    except Exception as e:
        print(f"[audio] playback error: {e}", flush=True)
        return False


# --- sfx ------------------------------------------------------------
def cmd_sfx(args, api_key):
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        print("usage: audio.py sfx \"<prompt>\" | <preset-alias>", file=sys.stderr)
        return 2
    seconds = args.seconds
    if prompt in PRESETS:
        default_prompt, default_sec = PRESETS[prompt]
        prompt = default_prompt
        if seconds is None:
            seconds = default_sec
    if seconds is None:
        seconds = 3.0
    seconds = max(0.5, min(22.0, float(seconds)))
    print(f"[sfx] {prompt!r} ({seconds}s)", flush=True)

    status, ctype, data = _http("POST",
                                "https://api.elevenlabs.io/v1/sound-generation",
                                api_key,
                                body={"text": prompt, "duration_seconds": seconds, "prompt_influence": 0.3},
                                accept="audio/mpeg")
    if status != 200 or "audio" not in ctype.lower():
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict) and parsed.get("audio_base_64"):
                data = base64.b64decode(parsed["audio_base_64"])
            else:
                print(f"[sfx] EL {status}: {json.dumps(parsed)[:300]}", flush=True)
                return 1
        except Exception:
            print(f"[sfx] EL {status}: {data[:200]!r}", flush=True)
            return 1

    if args.out:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
    else:
        out = ROOT / f"sfx-now-{int(time.time() * 1000)}.mp3"
    out.write_bytes(data)
    print(f"[sfx] wrote {len(data)} bytes -> {out}", flush=True)

    if not args.no_play:
        play_mci(str(out))

    if not args.keep and not args.out:
        try:
            out.unlink()
        except OSError:
            pass
    return 0


# --- preset ls ------------------------------------------------------
def cmd_preset(args, api_key):
    if args.op == "ls":
        width = max(len(k) for k in PRESETS)
        for name, (p, s) in sorted(PRESETS.items()):
            print(f"  {name:<{width}}  {s:>4}s  {p}")
        return 0
    print(f"unknown preset op: {args.op}", file=sys.stderr)
    return 2


# --- voice ls / try / mine ------------------------------------------
def cmd_voice(args, api_key):
    if args.op == "ls":
        url = "https://api.elevenlabs.io/v1/shared-voices?page_size=30"
        status, _, data = _http("GET", url, api_key)
        if status != 200:
            print(f"[voice ls] EL {status}: {data[:200]!r}", flush=True)
            return 1
        body = json.loads(data)
        rows = []
        q = (args.search or "").lower().strip()
        for v in body.get("voices", []):
            name = v.get("name", "")
            acc = v.get("accent") or ""
            age = v.get("age") or ""
            gen = v.get("gender") or ""
            desc = (v.get("description") or "").strip()
            hay = f"{name} {acc} {age} {gen} {desc}".lower()
            if q and q not in hay:
                continue
            rows.append((v.get("voice_id", ""), name, f"{age} {gen} {acc}".strip(), desc[:70]))
        w_id = 22
        w_nm = max((len(r[1]) for r in rows), default=10)
        for vid, name, tags, desc in rows:
            print(f"  {vid:<{w_id}}  {name:<{w_nm}}  {tags:<32}  {desc}")
        print(f"[voice ls] {len(rows)} shown")
        return 0

    if args.op == "mine":
        status, _, data = _http("GET", "https://api.elevenlabs.io/v1/voices", api_key)
        if status != 200:
            print(f"[voice mine] EL {status}: {data[:200]!r}", flush=True)
            return 1
        body = json.loads(data)
        for v in body.get("voices", []):
            cat = v.get("category") or ""
            if cat == "premade":
                continue
            print(f"  {v.get('voice_id')}  {v.get('name')}  [{cat}]")
        return 0

    if args.op == "try":
        if not args.voice_id or not args.text:
            print("usage: audio.py voice try <voice-id> <text>", file=sys.stderr)
            return 2
        text = " ".join(args.text)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{args.voice_id}"
        body = {"text": text, "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        status, ctype, data = _http("POST", url, api_key, body=body, accept="audio/mpeg")
        if status != 200 or "audio" not in ctype.lower():
            try:
                print(f"[voice try] EL {status}: {data.decode('utf-8', 'replace')[:300]}", flush=True)
            except Exception:
                print(f"[voice try] EL {status}", flush=True)
            return 1
        out = ROOT / f"voice-try-{int(time.time() * 1000)}.mp3"
        out.write_bytes(data)
        play_mci(str(out))
        try:
            out.unlink()
        except OSError:
            pass
        return 0

    print(f"unknown voice op: {args.op}", file=sys.stderr)
    return 2


def main():
    ap = argparse.ArgumentParser(prog="audio.py", description="AXIOM-Body audio toolkit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sfx", help="generate + play a sound effect (or a preset alias)")
    sp.add_argument("prompt", nargs="+")
    sp.add_argument("--seconds", type=float, default=None)
    sp.add_argument("--keep", action="store_true")
    sp.add_argument("--out", type=str, default="")
    sp.add_argument("--no-play", action="store_true")

    pp = sub.add_parser("preset", help="manage curated SFX presets")
    pp.add_argument("op", choices=["ls"])

    vp = sub.add_parser("voice", help="browse + try ElevenLabs voices")
    vp.add_argument("op", choices=["ls", "try", "mine"])
    vp.add_argument("voice_id", nargs="?")
    vp.add_argument("text", nargs="*")
    vp.add_argument("--search", type=str, default="")

    args = ap.parse_args()
    api_key = read_api_key()
    if not api_key:
        print("[audio] no ElevenLabs key — set ELEVENLABS_API_KEY or config/elevenlabs_api_key.txt", flush=True)
        return 3

    if args.cmd == "sfx":
        return cmd_sfx(args, api_key)
    if args.cmd == "preset":
        return cmd_preset(args, api_key)
    if args.cmd == "voice":
        return cmd_voice(args, api_key)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
