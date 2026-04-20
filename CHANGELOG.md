# Changelog

All notable changes to AXIOM-Body.

## [1.2.1] — 2026-04-20

### Added — Tunable ambient sensor
- `config/eyes.json` — new tuning file. Fields: `model` (yolov8n/s/m/l/x, default nano), `interval_sec`, `confidence.{min,person}`, `camera_index`. The sensor is multi-purpose: ambient scene snapshots, sleep detection, keep-face-alive during idle/compaction windows, and deciding when to trigger on-demand `eyes/look.py`. Installer will prompt for model size on fresh scaffolds.
- `ears/vision.py` — `load_eyes_config()` + `_apply_config()` now override `MIN_CONF`, `PERSON_CONF`, interval, and camera index from `config/eyes.json`. `get_model()` loads the configured YOLO weight by name with a nano fallback if the name is unknown. No behavior change for existing installs (defaults match prior hardcoded values).

### Site
- `docs/index.html` — added "The Hive" and "Tally" ecosystem cards alongside YonderClaw + QIS Protocol + AXIOM Body.
- `docs/index.html` — new v1.2.1 release card "Always-On Sensor, Tunable Model" documenting the sensor's multi-purpose role (sleep, keep-face-alive, active-vision trigger) and exposing the five YOLO size options.
- `docs/index.html` — Eyes component card rewritten to emphasize the ambient sensor's multiple roles and model tunability.

### Added — On-demand active vision
- `eyes/look.py` — agents actively take photos or video and get back structured analysis. Photo mode re-reads the ambient daemon's `latest_snap.jpg` so it doesn't fight for the camera; `--fresh` forces a live capture; `--video --seconds N` captures a clip and analyses a mid-frame. YOLO is the always-on baseline; Claude Vision (`claude-haiku-4-5`) adds a semantic description when `ANTHROPIC_API_KEY` or `config/anthropic_api_key.txt` is present. Off-switch via `config/eyes.off` or `AXIOM_EYES_DISABLED=1`.

### Added — Agent self-onboarding (no default face)
- `onboard/designer.py` — programmatic + interactive onboarding CLI. SHA-256-seeded unique starter palette (HSV + golden-ratio complement), personality weights, and voice rate/pitch so no two agents default to the same look/sound. Writes `personas/<slug>.json` and stamps `config/face.json` with `onboarded: true`.
- `onboard/expressions-bank.json` — 18 starter expressions agents can pick from (`shy_smile`, `cocky_smirk`, `wide_curious`, `suspicious_side_eye`, `wink_right`/`wink_left`, `sleepy_droop`, `yawn`, `dazzled`, `deadpan`, `melting_grin`, `focused`, `giggle`, `pout`, `determined`, `heart_eyes`, `glitch`, `smolder`). Includes authoring schema so agents can define their own modes.
- `voice/speak.py` — graceful TTS ladder. Tries ElevenLabs `/with-timestamps` first if `ELEVENLABS_API_KEY` env or `config/elevenlabs_api_key.txt` is set AND persona `voice.elevenlabs_voice_id` is not a placeholder; falls back to Windows SAPI (free, offline). Publishes `voice-meta.json` + `mute.flag` on both paths for face-engine mouth sync.

### Changed
- `face/face-engine.py` — refuses to start if `config/face.json` is missing or `onboarded != true`. Directs the agent to `python onboard/designer.py`. Adds `--skip-onboard-check` for tests.
- `face/web-face.html` — fetch path corrected to `../face-state.json` (state lives at repo root, not under `/face/`).
- `face/face-engine.py` — `_read_scene` now accepts both list (`[x, y]`) and dict (`{x,y}`) `gaze_target` payloads.
- `ears/vision.py`, `ears/listener.py`, `ears/respond.py` — all file-IPC paths rooted at repo root so face-engine sees `scene.json`, `listening.flag`, `mute.flag` regardless of where the script was started from.

### Philosophy
Every agent that boots AXIOM-Body now self-designs their face, voice, and expression palette. There is no default Axiom face — first run forces onboarding.

## [1.2.0-alpha.1] — 2026-04-20

### Added — Face v2 (state-driven architecture)
- `face/face-engine.py` — pure state producer. Reads `scene.json`, `listening.flag`, `voice-meta.json`, `mute.flag`; writes `face-state.json` at 10 Hz. Single source of truth for every renderer.
- `face/web-face.html` — dumb renderer. Polls `face-state.json` every 100 ms via `fetch`; renders 10 modes (idle, surprised, attentive, curious, tongue, eye_tag, listening, thinking, speaking, sleep) on a 400×400 canvas. Works in any browser.
- `face/test_engine.py` — engine unit tests (mode transitions, palette, mouth sync).
- `face/screenshot-all-modes.js` — puppeteer-based visual regression harness. Drives each mode via `face-state.json` and screenshots to `face-screenshots/`.
- `config/face.json` — per-agent identity (colors, voice, personality). Pick a persona or author your own.
- `personas/{axiom,ember,nova}.json` — three shipped personas. Axiom: cyan/green. Ember: warm amber. Nova: deep purple.
- `voice/tts-dispatcher.py` — optional hook point for swapping TTS providers without touching `ears/respond.py`.

### Changed
- `ears/listener.py` — touches `listening.flag` the instant speech is detected; removes it on silence-stop, mute-drain, sleep, or MAX_SPEECH cutoff. Five call sites instrumented. Face-engine reacts to this flag to drive `mode=listening`.
- `ears/respond.py` — writes `voice-meta.json` on every TTS start (word-level timings + est_end_ms), removes it in the finally block. Face-engine uses this for per-word mouth sync instead of audio-amplitude guessing.
- `face/web-face.html` — rewritten as a `face-state.json` poller. Old embedded state logic removed.

### File-IPC contract (stable for v1.2.x)
- `scene.json` (vision.py → face-engine) — `{people_count, gaze_target, ...}`
- `listening.flag` (listener.py → face-engine) — presence = user speaking
- `voice-meta.json` (respond.py → face-engine) — `{started_at_ms, est_end_ms, words: [{s,e,w}], ...}`
- `mute.flag` (respond.py → listener.py) — existing, reused
- `face-state.json` (face-engine → every renderer) — 10 Hz state snapshot

### Install
Installer bump to follow: `npx create-axiom-body@1.2.0-alpha.1 my-axiom` pulls this tag.

## [1.1.0] — 2026-04-XX
- Cross-platform fixes, generic hardware detection.

## [1.0.0]
- Web-based face renderer (single-file HTML).
- Leadfeeder tracker.
- MetaClaw → YonderClaw rename.
- Landing page upgrade.
