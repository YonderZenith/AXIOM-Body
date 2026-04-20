"""
AXIOM Body — TTS Dispatcher v2
===============================
One entry point for speaking. Reads config/face.json, picks provider (Piper /
Kokoro / ElevenLabs), generates audio, writes voice-meta.json, plays audio.

Replaces direct `scripts/speak.cjs` calls in respond.py. Keeps ElevenLabs as
the premium path; adds free local providers as the default.

Usage:
  python tts-dispatcher.py "Hello, I am Axiom."
  python tts-dispatcher.py --config ../config/face.json "text to speak"
  python tts-dispatcher.py --provider piper "override provider"
"""
import os
import sys
import json
import time
import shutil
import argparse
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent  # src/
DEFAULT_CONFIG = BASE / "config" / "face.json"
OUT_DIR = BASE  # voice-meta.json + mute.flag alongside face-state.json by default

MUTE_FLAG = OUT_DIR / "mute.flag"
VOICE_META = OUT_DIR / "voice-meta.json"


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _touch(p, content="1"):
    try:
        with open(p, "w") as f:
            f.write(content)
    except Exception:
        pass


def _remove(p):
    try:
        os.remove(p)
    except OSError:
        pass


def _write_json_atomic(path, data):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        os.replace(tmp, path)
    except OSError:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)


def _estimate_uniform_words(text, duration_sec):
    """Fallback word timings — uniform split of the clip across words."""
    words = [w for w in text.replace("\n", " ").split(" ") if w]
    if not words:
        return []
    slot = duration_sec / len(words)
    out = []
    for i, w in enumerate(words):
        s = round(i * slot + slot * 0.1, 3)
        e = round((i + 1) * slot - slot * 0.05, 3)
        out.append({"s": s, "e": max(s + 0.05, e), "w": w})
    return out


def play_audio(path):
    """Play a wav/mp3 file with ffplay (installed by AXIOM installer)."""
    ffplay = shutil.which("ffplay")
    if not ffplay:
        print("[tts] ffplay not found on PATH — skipping playback", flush=True)
        return 0.0
    start = time.time()
    subprocess.run(
        [ffplay, "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "quiet", path],
        check=False,
    )
    return time.time() - start


# --- Providers -------------------------------------------------
def speak_elevenlabs(text, cfg):
    """Delegate to the existing Node speak.cjs script. Requires ELEVEN_API_KEY."""
    speak_script = os.environ.get("AXIOM_SPEAK_SCRIPT")
    if not speak_script:
        # Try a few plausible locations
        candidates = [
            BASE.parent / "scripts" / "speak.cjs",
            Path.home() / "Desktop" / "AXIOM-Body" / "scripts" / "speak.cjs",
        ]
        for c in candidates:
            if c.exists():
                speak_script = str(c)
                break
    if not speak_script:
        raise FileNotFoundError("speak.cjs not found — set AXIOM_SPEAK_SCRIPT env var")

    # scripts/speak.cjs writes axiom/voice-playing.signal with exactDurationSec + words
    signal_path = BASE / "voice-playing.signal"
    _remove(signal_path)

    proc = subprocess.Popen(
        ["node", speak_script, text],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # Wait up to 15s for the signal, but let the Node proc keep running
    wait_start = time.time()
    while not signal_path.exists() and time.time() - wait_start < 15:
        time.sleep(0.05)

    words = []
    duration = 0.0
    if signal_path.exists():
        try:
            with open(signal_path, "r", encoding="utf-8") as f:
                sig = json.load(f)
            duration = float(sig.get("exactDurationSec", 0.0))
            for w in sig.get("words", []):
                words.append({"s": float(w.get("s", 0)),
                              "e": float(w.get("e", 0)),
                              "w": w.get("word", w.get("w", ""))})
        except Exception as e:
            print(f"[tts] elevenlabs signal parse failed: {e}", flush=True)

    proc.wait(timeout=180)
    return {
        "provider": "elevenlabs",
        "voice_id": cfg.get("voice", {}).get("elevenlabs_voice_id", ""),
        "duration_sec": duration or 0.0,
        "words": words,
        "audio_played": True,
    }


def speak_piper(text, cfg):
    """Offline TTS via Piper. Requires `piper` binary + a voice model."""
    piper = shutil.which("piper")
    voice_id = cfg.get("voice", {}).get("piper_voice_id", "en_US-hfc_female-medium")

    # Voices usually live in ~/.piper-voices/<id>/<id>.onnx
    voice_dir = Path.home() / ".piper-voices" / voice_id
    model = voice_dir / f"{voice_id}.onnx"

    if not piper or not model.exists():
        print(f"[tts] piper missing or voice {voice_id} not installed", flush=True)
        return {"provider": "piper", "voice_id": voice_id, "duration_sec": 0.0,
                "words": [], "audio_played": False, "skipped_reason": "not_installed"}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        wav_path = tmp.name

    try:
        proc = subprocess.run(
            [piper, "--model", str(model), "--output_file", wav_path],
            input=text, text=True, capture_output=True, timeout=120,
        )
        if proc.returncode != 0:
            print(f"[tts] piper failed: {proc.stderr}", flush=True)
            return {"provider": "piper", "voice_id": voice_id, "duration_sec": 0.0,
                    "words": [], "audio_played": False, "skipped_reason": "synth_failed"}
        duration = play_audio(wav_path)
        words = _estimate_uniform_words(text, duration or 2.5)
        return {"provider": "piper", "voice_id": voice_id, "duration_sec": duration,
                "words": words, "audio_played": True}
    finally:
        _remove(wav_path)


def speak_kokoro(text, cfg):
    """Offline TTS via Kokoro. Requires `pip install kokoro` + model cache."""
    try:
        from kokoro import KPipeline  # type: ignore
    except Exception:
        print("[tts] kokoro not installed — try: pip install kokoro", flush=True)
        return {"provider": "kokoro", "voice_id": "", "duration_sec": 0.0,
                "words": [], "audio_played": False, "skipped_reason": "not_installed"}
    voice_id = cfg.get("voice", {}).get("kokoro_voice_id") or "af_bella"
    try:
        pipeline = KPipeline(lang_code="a")
        gen = pipeline(text, voice=voice_id)
        import soundfile as sf  # type: ignore
        import numpy as np
        chunks = []
        for _, _, audio in gen:
            chunks.append(audio)
        if not chunks:
            raise RuntimeError("empty kokoro output")
        audio = np.concatenate(chunks)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            wav_path = tmp.name
        sf.write(wav_path, audio, 24000)
        duration = play_audio(wav_path)
        words = _estimate_uniform_words(text, duration or 2.5)
        _remove(wav_path)
        return {"provider": "kokoro", "voice_id": voice_id, "duration_sec": duration,
                "words": words, "audio_played": True}
    except Exception as e:
        print(f"[tts] kokoro failed: {e}", flush=True)
        return {"provider": "kokoro", "voice_id": voice_id, "duration_sec": 0.0,
                "words": [], "audio_played": False, "skipped_reason": str(e)}


def speak_silent(text, cfg):
    """No audio; emit plausible timings so face engine still mouth-syncs."""
    duration = max(1.0, len(text) / 28.0)
    words = _estimate_uniform_words(text, duration)
    time.sleep(duration)
    return {"provider": "silent", "voice_id": "", "duration_sec": duration,
            "words": words, "audio_played": False, "skipped_reason": "silent_fallback"}


PROVIDERS = {
    "elevenlabs": speak_elevenlabs,
    "piper": speak_piper,
    "kokoro": speak_kokoro,
    "silent": speak_silent,
}


def dispatch(text, config_path, provider_override=None):
    cfg = load_config(config_path)
    provider = provider_override or cfg.get("voice", {}).get("provider") or "piper"

    # If elevenlabs chosen but no API key, fall back
    if provider == "elevenlabs" and not os.environ.get("ELEVEN_API_KEY"):
        print("[tts] ELEVEN_API_KEY not set — falling back to piper", flush=True)
        provider = "piper"

    order = [provider] + [p for p in ["piper", "kokoro", "silent"] if p != provider]

    _touch(MUTE_FLAG, "speaking")
    start_ms = time.time() * 1000.0

    result = None
    try:
        for name in order:
            fn = PROVIDERS.get(name)
            if not fn:
                continue
            result = fn(text, cfg)
            if result and result.get("audio_played") or result and result.get("words"):
                break

        meta = {
            "schema_version": 1,
            "text": text,
            "provider": result.get("provider", "silent") if result else "silent",
            "voice_id": result.get("voice_id", "") if result else "",
            "started_at_ms": start_ms,
            "duration_sec": result.get("duration_sec", 0.0) if result else 0.0,
            "est_end_ms": start_ms + (result.get("duration_sec", 0.0) * 1000.0 if result else 0.0),
            "words": result.get("words", []) if result else [],
        }
        _write_json_atomic(VOICE_META, meta)

    finally:
        _remove(MUTE_FLAG)
        _remove(VOICE_META)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AXIOM TTS dispatcher")
    parser.add_argument("text", nargs="+", help="Text to speak")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--provider", default=None, choices=list(PROVIDERS.keys()))
    args = parser.parse_args()
    text = " ".join(args.text)
    result = dispatch(text, args.config, args.provider)
    print(json.dumps({"result": result}, indent=2), flush=True)
