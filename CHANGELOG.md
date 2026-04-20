# Changelog

All notable changes to AXIOM-Body.

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
