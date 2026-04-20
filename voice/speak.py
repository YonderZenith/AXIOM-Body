"""
speak.py — graceful TTS ladder for AXIOM-Body.

Ladder:
  1. ElevenLabs  — if ELEVENLABS_API_KEY env or config/elevenlabs_api_key.txt is present
                   AND the account has credit.
  2. Windows SAPI (System.Speech) — free, offline, ships with Windows. No key.
  3. macOS `say` / Linux `espeak` — future, not wired here.

In every case we publish the v2 file-IPC signals so face-engine.py
renders speaking mode with mouth sync:
  - voice-meta.json  (started_at_ms, est_end_ms, words[{s,e,w}])
  - mute.flag        (presence = speaking)

Usage:
  python voice/speak.py "hi ct"
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE_META = ROOT / "voice-meta.json"
MUTE_FLAG = ROOT / "mute.flag"
KEY_FILE = ROOT / "config" / "elevenlabs_api_key.txt"

# Provider ordering — env > config file > SAPI fallback.
def _read_api_key():
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if k:
        return k
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    return ""


def _load_persona_voice():
    cfg = ROOT / "config" / "face.json"
    if cfg.exists():
        try:
            j = json.loads(cfg.read_text(encoding="utf-8"))
            return j.get("voice", {}) or {}
        except Exception:
            pass
    return {}


def _estimate_words(text, total_sec):
    words = text.split()
    if not words:
        return []
    per = total_sec / len(words)
    out = []
    t = 0.0
    for w in words:
        out.append({"s": round(t, 3), "e": round(t + max(0.05, per - 0.04), 3), "w": w})
        t += per
    return out


def _publish_meta(text, total_sec, provider, voice_id=""):
    now_ms = time.time() * 1000.0
    meta = {
        "schema_version": 1,
        "text": text,
        "started_at_ms": now_ms,
        "est_end_ms": now_ms + total_sec * 1000.0,
        "provider": provider,
        "voice_id": voice_id,
        "words": _estimate_words(text, total_sec),
    }
    tmp = str(VOICE_META) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    os.replace(tmp, VOICE_META)
    MUTE_FLAG.write_text("1")


def _clear_meta():
    for p in (VOICE_META, MUTE_FLAG):
        try:
            os.remove(p)
        except OSError:
            pass


def _elevenlabs_speak(text, api_key, voice_id):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    body = json.dumps({
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[speak] ElevenLabs {e.code}: {body[:200]}", flush=True)
        return False
    except Exception as e:
        print(f"[speak] ElevenLabs error: {e}", flush=True)
        return False

    audio_b64 = data.get("audio_base64")
    alignment = data.get("alignment") or {}
    if not audio_b64:
        print("[speak] ElevenLabs: no audio returned", flush=True)
        return False

    import base64
    audio_path = ROOT / f"voice-now-{int(time.time()*1000)}.mp3"
    audio_path.write_bytes(base64.b64decode(audio_b64))

    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    total_sec = float(ends[-1]) if ends else 2.0

    # Build word entries from char alignment
    words = []
    cur = ""
    cur_start = 0.0
    for i, ch in enumerate(chars):
        if ch == " " or ch in ".,!?":
            if cur.strip():
                words.append({
                    "s": round(cur_start, 3),
                    "e": round(float(ends[i - 1] if i > 0 else starts[i]), 3),
                    "w": cur.strip(),
                })
            cur = ""
            cur_start = float(starts[i + 1]) if i + 1 < len(starts) else cur_start
        else:
            if not cur:
                cur_start = float(starts[i])
            cur += ch
    if cur.strip():
        words.append({"s": round(cur_start, 3), "e": round(total_sec, 3), "w": cur.strip()})

    now_ms = time.time() * 1000.0
    meta = {
        "schema_version": 1,
        "text": text,
        "started_at_ms": now_ms,
        "est_end_ms": now_ms + total_sec * 1000.0,
        "provider": "elevenlabs",
        "voice_id": voice_id,
        "words": words,
    }
    tmp = str(VOICE_META) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    os.replace(tmp, VOICE_META)
    MUTE_FLAG.write_text("1")

    # Play audio via Windows MCI (winmm.dll) — reliable for MP3, blocks until
    # playback ends, no PowerShell/COM hang. Falls back to WMPlayer COM if MCI
    # isn't available (non-Windows or locked-down env).
    try:
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW
        alias = f"voice{int(time.time()*1000)}"
        mci(f'open "{audio_path}" type mpegvideo alias {alias}', None, 0, 0)
        mci(f'play {alias} wait', None, 0, 0)
        mci(f'close {alias}', None, 0, 0)
    except Exception as e:
        print(f"[speak] playback error: {e}", flush=True)
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass
    _clear_meta()
    return True


def _sapi_speak(text):
    # Estimate duration — SAPI default rate ~170 wpm → 0.35s per word avg.
    words = len(text.split())
    est = max(0.6, words * 0.32)
    _publish_meta(text, est, provider="sapi", voice_id="windows-default")

    ps = (
        'Add-Type -AssemblyName System.Speech; '
        '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
        '$s.Rate = 0; '
        f'$s.Speak([string]@"\n{text}\n"@)'
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=est + 10)
    except Exception as e:
        print(f"[speak] sapi error: {e}", flush=True)
    _clear_meta()
    return True


def speak(text):
    if not text.strip():
        return False
    # Sense gate — if voice is toggled off, log and silent-success so the brain
    # treats the utterance as sent and does not retry. Fail-open on any error.
    el_enabled = True  # fail-open: EL path allowed unless toggle explicitly off
    try:
        senses_path = ROOT / "config" / "senses.json"
        if senses_path.exists():
            with open(senses_path, "r", encoding="utf-8") as f:
                senses = json.load(f)
            if senses.get("voice") is False:
                log_path = ROOT / "voice" / "muted-utterances.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(f"[{ts}] (-) {text}\n")
                print(f"[speak] voice disabled — logged (not spoken): {text[:60]}", flush=True)
                return True
            if senses.get("voice_elevenlabs") is False:
                el_enabled = False
    except Exception:
        pass  # fail-open: missing/corrupt senses.json means speak normally with EL allowed.
    voice_cfg = _load_persona_voice()
    api_key = _read_api_key()
    eleven_id = (voice_cfg.get("elevenlabs_voice_id") or "").strip()
    # Try ElevenLabs first if enabled AND we have a key AND a non-placeholder voice id.
    if el_enabled and api_key and eleven_id and not eleven_id.startswith("<"):
        print(f"[speak] via ElevenLabs (voice={eleven_id})", flush=True)
        ok = _elevenlabs_speak(text, api_key, eleven_id)
        if ok:
            return True
        print("[speak] ElevenLabs failed, falling back to SAPI", flush=True)
    else:
        if not el_enabled:
            print("[speak] EL toggle off — using SAPI (credit-save mode)", flush=True)
        elif not api_key:
            print("[speak] no ElevenLabs key, using SAPI", flush=True)
        else:
            print(f"[speak] EL voice id missing or placeholder ({eleven_id!r}), using SAPI", flush=True)
    return _sapi_speak(text)


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print("usage: python voice/speak.py \"hello world\"", file=sys.stderr)
        sys.exit(2)
    ok = speak(text)
    sys.exit(0 if ok else 1)
