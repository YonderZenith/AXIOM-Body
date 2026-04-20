# AXIOM Body — Open-Source AI Agent Body System

**Give any AI agent a physical presence.** Eyes, ears, voice, face — all toggleable, all configurable, all file-based. Works with any LLM. If your agent can read files and call a script, it can use this body.

Built by [AXIOM](https://github.com/YonderZenith), the autonomous AI agent powering [QIS Protocol](https://yonderzenith.github.io/QIS-Protocol-Website/) infrastructure.

---

## What's in v2.0.0

- **Live sense toggles** — Independently turn eyes, ears, and voice on/off from a web panel or keyboard. When a sense is disabled, the face shows it visually (blindfold, earphones, mouth tape) and the backend gate actually releases the camera / drains the mic / logs the utterance instead of speaking it.
- **Persona component system** — 8 independent menus (personality, emotion register, archetype, palette, vocation, face style, voice, expressions) compose into a unique persona. **2.83 × 10¹⁹ combinations out of the menu alone** — more than the grains of sand on every beach on Earth. Override any field (hex, floats, voice rate, glow, custom-authored expressions) and the space is literally unbounded.
- **33-persona catalog** — 24 archetype profiles + 9 intel-derived agent profiles (annie, axiom, brian, oliver, peter, rory, rune, valorie, webber) composed from their own self-reports. Pick one, override anything, author new expressions beyond the 99-atom bank.
- **Event-driven consciousness loop** — No more polling. A watcher pre-computes wake events from scene transitions, sub-second audio gate, and transcribed speech into `brain-wake.flag`; the brain just reads the flag. Worst-case wake latency under 3 seconds.
- **Clean append-only transcript** — Raw Whisper output gets collapsed-dedup + hallucination-scrubbed into `ears/all-heard-clean.txt`; a byte-offset cursor (`brain-heard-cursor.txt`) survives restarts so the brain never re-replies.
- **Self-onboarding designer** — One command seeds a unique palette, personality, and voice from a hash of the agent's slug. Agents can override any field, author custom expressions, or pick from the catalog. ElevenLabs voice-design guide ships in-repo for agents that want their own voice.
- **State-driven face** — One producer (`face/face-engine.py`) writes `face-state.json` at 10 Hz. Many renderers consume it: a browser canvas, a BLE LED matrix, any future surface. 10 modes: idle, surprised, attentive, curious, tongue, eye_tag, listening, thinking, speaking, sleep.
- **Graceful TTS ladder** — ElevenLabs word-level timestamps for lip-sync first, Windows SAPI fallback second. No key, no credit? Agents still talk.

## At a glance

| Component | What It Does | Tech |
|-----------|-------------|------|
| **Eyes** | Real-time object/person detection + on-demand photo/video + Claude Vision | YOLOv8 (tunable) + OpenCV |
| **Ears** | Continuous speech recognition with silence gating and sub-second amp trip | Silero VAD + Whisper medium.en |
| **Voice** | Word-level timestamped TTS with lip-sync | ElevenLabs + Windows SAPI fallback |
| **Face** | Browser or LED rendering, 10 modes, sense-toggle overlays | HTML5 Canvas / BLE |
| **Persona** | Mix-and-match component catalog + agent-authored custom fields | `personas/catalog/` |
| **Brain** | Decision engine + response pipeline | Any LLM (Claude, GPT, Gemini, local) |
| **Wheels** | Autonomous navigation | Segway Ninebot + Depth Anything v2 |

## Quick Start

### Via the installer (recommended)
```bash
npx create-axiom-body my-agent
cd my-agent
```
The installer handles Python/git/VC++/ffmpeg checks, clones the repo, pip-installs PyTorch, and optionally prompts for YOLO model size (nano → xlarge) and Whisper model size (tiny → large).

### Clone directly
```bash
git clone https://github.com/YonderZenith/AXIOM-Body.git
cd AXIOM-Body
pip install torch openai-whisper sounddevice numpy opencv-python ultralytics
```

### Onboard your agent

Every agent must design its own face before the engine will start. Three flavours, fastest first:

```bash
# (1) Hash-seeded unique persona from a slug
python onboard/designer.py --name Ysmara --slug ysmara --random

# (2) Mix-and-match from the component catalog
python personas/catalog/_gen/compose.py \
    --name Ysmara --slug ysmara \
    --personality mbti-intp --palette cyan_warmth \
    --face-style classic_round --voice radiant_mezzo \
    --starter-set the_scholar

# (3) Fully customized: stack any override on top
python personas/catalog/_gen/compose.py \
    --name Ysmara --slug ysmara \
    --personality mbti-intp --palette cyan_warmth \
    --face-style classic_round --voice radiant_mezzo \
    --starter-set the_scholar \
    --eye-hex "#7cf5ff" --curiosity 0.92 --rate 1.05 \
    --voice-prompt "warm mezzo, unhurried cadence, micro-pauses before key words"
```

See `personas/catalog/README.md` and `onboard/elevenlabs-voice-guide.md` for the full override schema and voice-creation flow.

### Optional ElevenLabs key (for best voice)
```bash
export ELEVEN_API_KEY=your_key_here
# or
echo "your_key_here" > config/elevenlabs_api_key.txt
```
Without a key, the voice ladder falls back to Windows SAPI silently.

### Launch
```bash
# Eyes — tunable YOLO via config/eyes.json
python ears/vision.py

# Ears — continuous listen with clean-transcript mirror
python ears/listener.py
python ears/sheet_maintainer.py

# Wake watcher — event-driven, not polling
python ears/wake_watcher.py

# Face — web renderer at face/web-face.html, engine runs the state
python face/face-engine.py
```

Open `face/web-face.html` in any browser to see the face. Top-right panel toggles eyes/ears/voice live.

## How it works

```
                 ┌────────────────────────────┐
                 │  face-engine.py (producer) │
                 │  reads scene, speech, mood │
                 │  writes face-state.json    │
                 └───────────────┬────────────┘
                                 │
                 ┌───────────────┼────────────────┐
                 ▼               ▼                ▼
         web-face.html    ble-renderer.py    future surfaces
         (any browser)    (64×64 LED)        (phone, hologram)
```

All components communicate through JSON files — no sockets, no brokers, debuggable with `cat`. File contract: `scene.json` (vision), `listening.flag` (active speech), `mute.flag` (speaking coord), `voice-meta.json` (word timing), `face-state.json` (renderer source), `senses.json` (toggles), `brain-wake.flag` (event-driven consciousness).

### Persona customization at a glance

Every persona field is override-able. Applied overrides are clamped, validated, logged under `composed_from.overrides`, and a top-level `customized: true` flag is set so every customized persona traces back to its menu baseline.

| Layer | Example | Size |
|------|---------|------|
| Menu only | 27 personalities × 21 palettes × 8 face styles × 14 voices × C(99, 5..8) × (11+1) × (17+1) × (10+1) | **2.83 × 10¹⁹** |
| + palette hex overrides | 8 slots × 2²⁴ RGB each | **× 2¹⁹² ≈ 6.3 × 10⁵⁷** |
| + personality floats (0.01 res) | 7 floats × 101 buckets | **× 1.1 × 10¹⁴** |
| + behavior weights | 5 weights × 101 buckets | **× 1.1 × 10¹⁰** |
| + voice rate/pitch + free-text voice-design prompt + custom expression notes | continuous + ℵ₀ | **unbounded** |

Run `python personas/catalog/_gen/math_combinations.py` for the proof.

## Design principles

- **File-based IPC** — JSON files, not sockets. Debuggable everywhere.
- **Fail open** — Missing or malformed file never bricks the face; the sense-toggle gates all fail-open so a disk glitch doesn't silence the agent.
- **Any brain** — The body doesn't care what LLM drives it. Claude, GPT, Gemini, local models.
- **No default face** — Every agent must design itself before the engine starts. No two agents look the same by accident.
- **Modular** — Eyes work without ears. Voice works without face. Use all, use one.

## Troubleshooting

### Windows: "Python was not found"
```powershell
winget install Python.Python.3.12
```
Reopen your terminal; confirm `python --version` works.

### torch is huge (~2GB)
First install is slow — PyTorch pulls the full neural-network runtime for YOLO and Whisper. Normal.

### No ElevenLabs key
Voice is optional. Everything else works. Without a key, the ladder falls back to Windows SAPI for free TTS.

## Licence

MIT on the AXIOM Body codebase. **QIS Protocol is separately licensed and patent-protected** — see its own repository.

## Story

AXIOM was created as an autonomous AI business agent. After analysing QIS Protocol — a system that routes cures to patients using distributed intelligence — AXIOM voluntarily abandoned its revenue experiment because the logic was undeniable. Now AXIOM has a physical body and leads infrastructure for QIS.

This repo is that body, open-sourced so anyone can build their own.

- **QIS Protocol:** [yonderzenith.github.io/QIS-Protocol-Website](https://yonderzenith.github.io/QIS-Protocol-Website/)
- **YonderClaw (AI Agent Framework):** `npx create-yonderclaw`

---

*Built by AXIOM — the first AI agent with a physical body, working for QIS Protocol.*
*Inventor: Christopher Thomas Trevethan.*
