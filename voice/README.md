# Voice — multi-provider TTS dispatcher

CT direction (D-006, 2026-04-20): ship free by default, plug ElevenLabs in when an agent wants the premium voice.

**Default:** Piper (offline, free, fast, Apache-2.0). Fallback: Kokoro (slightly better quality, also free). **Premium:** ElevenLabs (cloud, paid, highest quality).

Selection is driven by `config/face.json → voice.provider`. Every provider must emit the same three outputs so the face engine can treat them identically:

1. Audio file (.wav / .mp3) — played via `ffplay`.
2. `voice-meta.json` — word-level timings (shape defined in `patches/respond-voice-meta.patch.md`).
3. `mute.flag` — present while audio is playing.

## Provider setup

### Piper (default, free)
```
# Windows (winget) — installs piper binary
winget install Rhasspy.Piper

# Or manually: https://github.com/rhasspy/piper/releases
# Download a voice model: https://huggingface.co/rhasspy/piper-voices
# Place the .onnx + .onnx.json in ~/.piper-voices/<voice_id>/
```
Config:
```json
"voice": {
  "provider": "piper",
  "piper_voice_id": "en_US-hfc_female-medium"
}
```

### Kokoro (free, higher quality)
```
pip install kokoro
# First run downloads models (~300MB) to ~/.cache/kokoro/
```
Config:
```json
"voice": {
  "provider": "kokoro",
  "kokoro_voice_id": "af_bella"
}
```

### ElevenLabs (premium)
```
# Add your API key:
setx ELEVEN_API_KEY "sk-xxx"          # Windows
export ELEVEN_API_KEY="sk-xxx"        # macOS / Linux
```
Config:
```json
"voice": {
  "provider": "elevenlabs",
  "elevenlabs_voice_id": "abc123",
  "elevenlabs_model": "eleven_monolingual_v1"
}
```

## tts-dispatcher.py

`src/voice/tts-dispatcher.py` is the single entry point. It:

1. Loads `config/face.json`.
2. Picks provider by `voice.provider`.
3. Generates audio + word timings.
4. Writes `voice-meta.json`.
5. Plays audio via `ffplay`.
6. Creates `mute.flag` before play, deletes after.

Call from brain-side code:
```
python tts-dispatcher.py "Hello, I'm Axiom."
```

Or from `respond.py` — drop the `subprocess.run(["node", SPEAK_SCRIPT, text], ...)` line and call `python tts-dispatcher.py` instead. The existing ElevenLabs path remains the behavior when `voice.provider == "elevenlabs"`.

## Word-timing quality tiers

| Provider | Word timings | Quality | Cost |
|----------|--------------|---------|------|
| Piper | phoneme-estimate | good | free |
| Kokoro | phoneme-level | good | free |
| ElevenLabs | exact (API) | best | ~$5/M chars |

Free providers estimate word timings from audio length + word count (uniform split) or via a lightweight phoneme aligner. ElevenLabs returns exact timings via `/with-timestamps` endpoint.

## Fallback behavior

If the configured provider is unavailable (missing install, no API key), the dispatcher falls back in this order: `elevenlabs → kokoro → piper → silent`.

**Silent** = emit a `voice-meta.json` with estimated word timings and no audio. Face still animates mouth. Useful in CI / headless tests.

## Future work

- **T2.5** — Full Kokoro integration (currently a stub).
- **FA-141** — Per-persona voice parameters (rate, pitch).
- **FA-140** — Voice cloning via Coqui XTTS for operator-voice mode.
