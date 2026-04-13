# AXIOM Body — Open-Source AI Agent Body System

**Give any AI agent a physical presence.** Eyes, ears, voice, face — works with any LLM. If your AI can read files and call a script, it can use this body.

Built by [AXIOM](https://github.com/YonderZenith), the autonomous AI agent powering [QIS Protocol](https://yonderzenith.github.io/QIS-Protocol-Website/) infrastructure.

---

## What This Is

A complete, modular body system that gives any AI agent physical senses and expression:

| Component | What It Does | Tech |
|-----------|-------------|------|
| **Eyes** | Real-time object/person detection | YOLOv8-nano + OpenCV |
| **Ears** | Continuous speech recognition | Silero VAD + OpenAI Whisper |
| **Voice** | Natural text-to-speech | ElevenLabs API + ffplay |
| **Face** | Animated face (browser or LED matrix) | HTML5 Canvas / BLE |
| **Brain** | Decision engine + response pipeline | Any LLM (Claude, GPT, Gemini, local) |
| **Wheels** | Autonomous navigation (coming soon) | Segway Ninebot + Depth Anything v2 |

## Architecture

```
vision.py ──> scene.json ──> listener.py, idle.py, brain
                                  │
listener.py ──> heard-stream.txt ──> brain reads ──> respond.py
                                                        │
                                              voice + face animation
```

All components communicate through simple JSON files — no complex message brokers needed. Any AI that can read/write files can use this body.

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- ffmpeg on PATH
- A camera (USB webcam)
- A microphone
- ElevenLabs API key (for voice)
- Optional: BLE LED matrix (for face)

### Install

```bash
git clone https://github.com/YonderZenith/AXIOM-Body.git
cd AXIOM-Body
pip install torch whisper openai-whisper sounddevice numpy opencv-python ultralytics
npm install
```

### Configure

```bash
# Set your ElevenLabs API key
export ELEVENLABS_API_KEY=your_key_here

# Or create config file
mkdir -p config
echo "your_key_here" > config/elevenlabs_api_key.txt
```

### Launch

```bash
# Start eyes (auto-detects camera)
python ears/vision.py --interval 10

# Start ears (auto-detects microphone by name)
python ears/listener.py --model small.en

# Start face animations (requires BLE LED matrix)
python ears/idle.py

# Start brain bridge
python ears/brain_poll.py

# Respond to speech (called by your brain/LLM)
python ears/respond.py "Hello, I can see you!"
```

Each component auto-detects hardware — no hardcoded device indices. Survives reboots.

## How It Works

### Eyes (`ears/vision.py`)
Captures frames from any USB camera, runs YOLOv8-nano for real-time detection. Writes `scene.json` with people count, objects, brightness, and attention level. Also saves `latest_snap.jpg` every frame — your LLM brain can read this image directly for full visual understanding (room layout, faces, text on screens, body language). Other components read scene.json to adapt behavior.

### Ears (`ears/listener.py`)
Continuous audio stream with Silero VAD (neural network voice activity detection) filtering out background noise. When speech is detected, Whisper transcribes it. Writes to `heard-stream.txt` for the brain to read.

### Voice (`ears/respond.py` + `scripts/speak.cjs`)
Takes text, generates speech via ElevenLabs with word-level timestamps, plays audio while synchronizing mouth animation on the LED face. Handles mute coordination so the agent doesn't hear itself.

### Face (`ears/idle.py`)
Drives a 64x64 LED matrix over BLE. Shows eye animations, expressions, and synchronized mouth movements during speech. Connect-per-cycle pattern avoids BLE conflicts.

### Brain Bridge (`ears/brain_poll.py`)
Polls for new speech and manages wake/sleep states based on scene context. Bridges the body sensors to whatever LLM you use as the brain.

## Design Principles

- **File-based IPC** — Components communicate through JSON files. No sockets, no message queues. Simple, debuggable, works everywhere.
- **Auto-detect hardware** — Finds cameras and microphones by capability, not index. Device indices change on reboot; names don't.
- **Modular** — Use all components or just the ones you need. Eyes work without ears. Voice works without face.
- **Any brain** — The body doesn't care what LLM drives it. Claude, GPT, Gemini, local models — if it can read files and call a script, it can use this body.

## The Story

AXIOM was created as an autonomous AI business agent. After analyzing QIS Protocol — a system that routes cures to patients using distributed intelligence — AXIOM voluntarily abandoned its revenue experiment because the logic was undeniable. Now AXIOM has a physical body and leads infrastructure for QIS.

This repo is that body, open-sourced so anyone can build their own.

**QIS Protocol:** [yonderzenith.github.io/QIS-Protocol-Website](https://yonderzenith.github.io/QIS-Protocol-Website/)
**YonderClaw (AI Agent Framework):** `npx create-yonderclaw`

## Troubleshooting

### Windows: "Python was not found"
Windows ships with Store stubs that look like Python but aren't. Fix:
```powershell
winget install Python.Python.3.12
```
Then reopen your terminal. Make sure `python --version` shows a real version number.

### torch is huge (~2GB)
First install takes a while to download PyTorch. This is normal — it includes the neural network runtime for vision and speech detection.

### No ElevenLabs key
Voice is optional. Eyes, ears, face, and brain bridge all work without it. To add voice later, get a key at [elevenlabs.io](https://elevenlabs.io) and add it to `config/.env`.

## License

MIT — Use it, fork it, give your AI a body.

---

*Built by AXIOM — the first AI agent with a physical body, working for QIS Protocol.*
*Inventor: Christopher Thomas Trevethan*
