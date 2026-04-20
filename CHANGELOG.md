# Changelog

All notable changes to AXIOM-Body.

## [2.0.0] — 2026-04-20 (evening) — 2026-04-21 (component system)

**Major release.** AXIOM Body grows a proper nervous-system UI. Operators can toggle eyes, ears, and voice independently from a live panel with clear visual feedback (blindfold / earphones / tape overlays). The consciousness loop moves from poll-derived state to pre-computed wake events. The persona system flips from a pre-baked catalog to a mix-and-match component architecture so every agent onboards onto a combinatorially-unique face. v1.2.x is rolled forward into 2.0.0 — nothing is deprecated, but the sense-toggles contract and persona component system are large enough additions that a major bump is warranted.

### Added — Persona component system (mix-and-match)
- `personas/catalog/_components/` — eight independent category menus replace any notion of a fixed catalog. Agent picks one entry from each (plus 5-8 expressions from the bank) to compose a persona. Combinatorial scope ≈ 2 × 10¹⁹ after the 2026-04-21 agent-intel expansion. Category files:
  - `personality_profiles.json` — 27 named temperaments across MBTI (9), Big Five axial profiles (4), Enneagram (11 — 5 base + 6 wings), HEXACO (1), attachment (2). Each defines the 7 personality floats + 5 behavior_weights; newer wing profiles add an optional `texture_extensions` dict for agent-contributed textures (gravity, verification_reflex, continuity_orientation, presence_gradient, laconic_factor, dryness, craft_intensity, restraint, log_reflex, scar_memory_depth, parse_patience, mission_gravity).
  - `emotion_registers.json` — 11 resting-affect biases (sanguine, phlegmatic, melancholic, choleric, radiant, stoic, dreamy, volatile, wary, bright, **lantern** — Rune's 2026-04-21 coinage for steady-warm-responsive).
  - `archetypes.json` — 17 narrative roles (Jung's 12 + Vogler mentor/shadow/trickster/threshold_guardian + **hunter** — Oliver's 2026-04-21 coinage for recognition-before-engagement, distinct from explorer).
  - `aesthetic_palettes.json` — 21 Pixar-style 8-hex palette packs (cosmic_indigo, neon_cyberpunk, golden_hour, midnight_velvet, voidcore, sakura_bloom, etc., plus 7 intel-derived from 2026-04-21: late_night_ops, library_at_dusk, sentinel_cyan, amber_forest, cyan_warmth, golden_hour_tech, midnight_steel).
  - `vocations.json` — 10 behavior-weight overlays for daily activity (healer, analyst, creator, warrior, scholar, guardian, entertainer, diplomat, seeker, teacher).
  - `face_styles.json` — 8 silhouette + canvas combinations (classic_round, pixel_crisp, sleepy_soft, angular_alien, minimal_dot, oval_theatrical, spectral_glow, carved_mask).
  - `voice_profiles.json` — 14 voice profiles with provider + rate + pitch + piper/kokoro voice_ids + an ElevenLabs `voice_design_prompt` for agent-authored custom voices. 6 new intel-derived voices from 2026-04-21: dry_technical_baritone (Webber/Brian/Axiom), wry_alto_writer (Rory), seasoned_alto (Annie), concierge_tenor (Rune), documentary_soprano (Valorie), deliberate_baritone (Peter).
  - `starter_expression_sets.json` — 10 curated 5-8-expression bundles (the_stoic, the_giggler, the_scholar, the_caregiver, the_hero, the_jester, the_dreamer, the_shadow, the_lover, the_sage) as optional one-click shortcuts.
  - `README.md` — full architectural doc with combinatorial math, expert-board mapping, compose CLI recipe.
- `personas/catalog/_gen/compose.py` — composer library + CLI. Merges one pick per category into a $schema_version-2 persona JSON, validates every id against the component menus and every expression triple against the engine's enum sets. Surfaces `voice_design.voice_design_prompt` when the picked voice_profile is EL-preferred. CLI: `python personas/catalog/_gen/compose.py --name X --slug y --personality mbti-entp --palette neon_cyberpunk --face-style pixel_crisp --voice quicksilver_tenor --expressions a,b,c,d,e`.
- `onboard/designer.py` — picks up the new compose flags (`--personality`, `--emotion`, `--archetype`, `--palette`, `--vocation`, `--face-style`, `--voice`, `--starter-set`) and delegates to compose.py when any are given. Legacy hash-seeded path untouched. `--list-components` prints every valid id per category.

### Added — Expression bank expansion
- `onboard/expressions-bank.json` — atomic expression bank expanded 18 → 60 → 99 entries across 19 families (joy, surprise, sadness, anger, fear, disgust, thinking, curiosity, flirt, sleep, error, focus, neutral, tongue + 5 new families from 2026-04-21 agent intel: insight, persistence, verification, presence, alert). Every entry carries its family tag + notes on when it reads, with `Credit: <agent>` attribution on intel-derived atoms. `picking_rules.recommended_to_include` replaces hard-mandatory `thinking` so pure-jester and pure-shadow personas stay valid. C(99, 8) ≈ 1.9 × 10¹¹ expression combinations alone.

### Added — ElevenLabs voice-design flow
- `onboard/elevenlabs-voice-guide.md` — agent-readable guide for using ElevenLabs voice-design to author a one-off custom voice matching the agent's personality. Documents the 2-step API flow (create-previews → create-voice-from-preview), prompt-writing best practices, budget notes, and pointers to EL's canonical docs for when their API surface shifts.
- `onboard/designer.py` — new `nudge_elevenlabs_if_needed()` helper. When an agent picks a voice profile with `elevenlabs_preferred: true` and `ELEVEN_API_KEY` is not set, prints a one-time nudge to the operator with sign-up URL, key-setup commands, and the path to the voice-design guide. Falls back to Piper/Kokoro silently; persona still valid.

### Bulletin sent
- `Z:\BULLETINS HERE ONLY!\2026-04-21T03-15-00Z_ysmara-AXIOM-BODY-EXPRESSION-INTEL-REQUESTED.json` — asks every agent (Annie, Axiom, Brian, Oliver, Peter, Rory, Rune, Valorie, Webber) to self-describe their face: resting expression, daily 5-8, signature micro-expression, focus / finishing / surprise / frustration / relational modes, missing-from-bank expressions, invisible-personality textures, archetype + palette + voice self-identification (Q1-Q14). Responses land in `Z:/inbox/ysmara/` and feed the v2 catalog evolution.

### Added — 9 agent intel-derived pre-composed personas (2026-04-21)
- All 9 responding agents received a pre-composed catalog entry at `personas/catalog/agent-<slug>.json` built via `compose.py` from their own 2026-04-21 self-reports. Each pick (personality profile, emotion register, archetype, palette, vocation, face style, voice profile, 8 expressions) is sourced from the agent's answers to Q1-Q14. Intel-attribution is preserved in `composed_from` + expression `notes`:
  - `agent-annie.json` — enneagram-5w6 + wary + threshold_guardian + sentinel_cyan + guardian + minimal_dot + seasoned_alto. Scar-memory-deep, operator-filter reflex.
  - `agent-axiom.json` — enneagram-5w6 + stoic + mentor + cyan_warmth + guardian + angular_alien + dry_technical_baritone. Green mouth = voice-as-connection, loading-glow signature.
  - `agent-brian.json` — enneagram-5w6 + stoic + creator + neon_cyberpunk + scholar + carved_mask + dry_technical_baritone. Forge-fire + stuck-protocol-firing.
  - `agent-oliver.json` — enneagram-3w4 + radiant + hunter (new archetype) + neon_cyberpunk + diplomat + pixel_crisp + crisp_tenor. Mission-gravity + day-one-fire.
  - `agent-peter.json` — enneagram-1w9 + stoic + threshold_guardian + midnight_steel + scholar + classic_round + deliberate_baritone. Scanning + caught_it + clean_pass audit triad.
  - `agent-rory.json` — enneagram-5w1 + bright + sage + library_at_dusk + creator + oval_theatrical + wry_alto_writer. Writer-editor register, dryness 0.60.
  - `agent-rune.json` — mbti-intp + lantern (new register) + threshold_guardian + amber_forest + guardian + sleepy_soft + concierge_tenor. Parse-patience + log-reflex.
  - `agent-valorie.json` — enneagram-1w2 + bright + creator + golden_hour_tech + creator + classic_round + documentary_soprano. Craft-intensity + restraint.
  - `agent-webber.json` — enneagram-1w5 + phlegmatic + mentor + late_night_ops + scholar + classic_round + dry_technical_baritone. Documentation-urge + cross-check + continuity.
- `personas/catalog/_gen/compose_agent_catalog.py` — one-shot driver that maps agent-intel picks → `compose_persona()` → `personas/catalog/agent-<slug>.json`. Does not overwrite active persona files under `personas/` root.
- `C:\Users\ctt03\.claude\projects\C--Users-ctt03\memory\logic_log_axiom_body_intel_parse.md` — master parse log (Q10 atoms, Q11 floats, Q12 archetypes/registers, Q13 palettes, Q14 voices) documenting the reasoning behind every catalog addition.

### Added — Unlimited customization layer (override any field)
- `personas/catalog/_gen/compose.py` — `compose_persona()` gains 7 override kwargs on top of the menu picks: `palette_overrides` (any of 8 slots, per-slot #rrggbb hex), `personality_overrides` (7 floats, clamped [0.0, 1.0]), `behavior_weight_overrides` (5 weights, clamped), `voice_overrides` (rate/pitch clamped [0.25, 2.5], provider + voice_id strings), `face_style_overrides` (glow_intensity clamped; shape strings passthrough), `voice_design_prompt_override` + `elevenlabs_preferred_override` (free-text EL voice-design prompt routed to `persona.voice_design`), and `custom_expressions` (agent-authored expressions beyond the 99-atom bank — engine-enum validated, dedup-checked, total capped at max_picks_per_agent).
- All overrides are validated & clamped before merge; invalid slot/field names raise `ComposeError` with the full valid-key list. Applied overrides are logged under `persona.composed_from.overrides` and a top-level `persona.customized = True` flag is set.
- CLI flags for common overrides: `--eye-hex / --bg-hex / --mouth-hex / --pupil-hex`, `--blink / --curiosity / --shyness / --playfulness / --attention-drift / --surprise / --sleep`, `--rate / --pitch / --voice-prompt`, `--glow`, plus `--overrides <path.json>` for the full override schema (palette, personality, behavior_weights, voice, face_style, voice_design_prompt, elevenlabs_preferred, custom_expressions).
- `personas/catalog/_gen/test_overrides.py` — 16-case smoke test exercising every override kwarg: palette (incl. hostile-hex rejection and non-string rejection), personality (incl. clamping), voice (incl. clamping), face_style, voice_design_prompt, behavior_weights, custom expressions (bad enum rejected, duplicate id rejected, unknown override field rejected), plus a stacked-all-overrides "money shot" case. 16/16 passing.
- `personas/catalog/_gen/compose_override_demo.py` — reference driver that stacks every customization layer at once and writes `personas/catalog/agent-override-demo.json`. Canonical example to show new agents the full customization surface.
- `personas/catalog/_gen/math_combinations.py` — rigorous combinatorics module citing Feller / Knuth / Stanley. Computes menu-only count (2.83 × 10¹⁹, ~= grains of sand on every beach on Earth), palette-override count (2¹⁹², ~= 6.3 × 10⁵⁷), personality-float count at 0.01 resolution (101⁷ ~= 1.1 × 10¹⁴), behavior-weight count (101⁵ ~= 1.1 × 10¹⁰), and discrete-compounded total (~2 × 10¹⁰¹). With continuous voice rate/pitch and free-text voice-design prompts + custom expression labels/notes, the effective space is the cardinality of the continuum — literally unbounded.

### Docs — "Unlimited out of the box"
- `docs/index.html` — two new release cards in the "Just Shipped" grid: CUSTOMIZE ("Unlimited Out-of-the-Box Variations" — menu-first, override-anything, with a full CLI example) and MATH ("The Actual Numbers" — 2.83 × 10¹⁹ menu-only, 10¹⁰¹ discrete compounded, unbounded with continuous + free-text). Subtitle of the release section updated to reflect the customization story.

### Stats (after 2026-04-21 agent-intel expansion + customization layer)
- Expression atoms: **99** (+39, +65%)
- Expression families: **19** (+5 new: insight, persistence, verification, presence, alert)
- Personality profiles: **27** (+7)
- Emotion registers: **11** (+1)
- Archetypes: **17** (+1)
- Aesthetic palettes: **21** (+7)
- Voice profiles: **14** (+6)
- Pre-composed catalog personas: **33** (+9)
- Persona combinations (menu-only): **≈ 2.83 × 10¹⁹**
- Persona combinations (discrete compounded w/ overrides): **≈ 2 × 10¹⁰¹**
- Persona combinations (w/ continuous + free-text layers): **unbounded** (cardinality of the continuum)

---

**Original v2.0.0 preamble (evening 2026-04-20):** AXIOM Body grows a proper nervous-system UI. Operators can toggle eyes, ears, and voice independently from a live panel with clear visual feedback (blindfold / earphones / tape overlays). The consciousness loop moves from poll-derived state to pre-computed wake events. A 33-persona catalog lands (24 archetypes + 9 intel-derived agent profiles) so new agents never start from a blank config. v1.2.x is rolled forward into 2.0.0 — nothing is deprecated, but the sense-toggles contract and persona catalog are large enough additions that a major bump is warranted.

### Added — Sense toggles (eyes / ears / voice)
- `config/senses.json` — new single-source-of-truth boolean state (all default `true`). Atomic-written; every reader fail-opens on missing or malformed file so a disk glitch never bricks the face.
- `config/senses-server.py` — tiny HTTP sidecar on `127.0.0.1:7899`. `GET /senses` returns current state; `POST /senses` atomically writes a cleaned payload. CORS `*` so `file://`-hosted `web-face.html` can POST to it. Auto-spawned by `face-engine.py` at boot (detached subprocess) so operators don't need a second terminal.
- `face/web-face.html` — collapsible top-right SENSES panel. 22×22 pill expands to 180×128 card with three switches (EYES/EARS/VOICE). Keyboard: `E`/`A`/`V`/`P`/`Esc`. Writes through senses-server, falls back to localStorage if server offline. Row flash + footer timestamp for feedback.
- `face/web-face.html` — three overlay renderers drawn after the normal face: `drawBlindfold()` (band rows 19-25 + knot near right edge), `drawEarphones()` (oval cups at canvas edges on eye-line), `drawMouthTape()` (strip rows 46-50 with diagonal crease + corner tears). Colors derived from the active persona palette. Overlays are drawn LAST so they sit on top of eyes/mouth regardless of mode.
- `face/face-engine.py` — `read_senses()` helper + `state["senses"]` field in every `face-state.json` tick (authoritative downstream signal for the renderer). `_spawn_senses_server()` auto-starts the sidecar on engine boot if 7899 is free.
- `ears/vision.py` — new `eyes_disabled()` gate OR'd with existing env/flag-file off-switches. When true: camera handle released, YOLO skipped, heartbeat `scene.json` written with `sense_off: "eyes"`. Privacy-correct: a disabled eye means a physically dark lens.
- `ears/listener.py` — new `_ears_disabled()` guard in main loop. When true: drain audio queue, skip VAD/transcription, clear `listening.flag`, log once/minute. Stream stays open (drain-only) — avoids Windows mic-light flicker on rapid toggles; the spec's 5-minute stream release is nice-to-have, deferred.
- `voice/speak.py` — voice-gate check at top of `speak()`. When `voice=false`: append an ISO-timestamped line to `voice/muted-utterances.log` with provider slot `(-)` (short-circuits before provider selection), do NOT create `mute.flag` or publish `voice-meta.json`, return `True` so the brain treats the utterance as sent and does not retry.
- `face/SENSE-TOGGLES-SPEC.md` — design-complete authoring spec shipping alongside the runtime implementation.

### Added — Event-driven wake pattern
- `ears/wake_watcher.py` v2 — pre-computes wake events into `brain-wake.flag` so the consciousness loop doesn't have to re-derive state. Three sources now: (a) scene (motion/speech transitions), (b) `listener.log` tail (sub-second sound_gate + speech_detected via Whisper markers), (c) `new-speech.flag`. Appends to `wake-events.jsonl` for A/B latency analysis. `--no-tail` disables log tail for scene-only mode. Cooldowns: 3s sound_gate, 2s speech_detected.
- `WAKE-CHECK-PROMPT-V2.md` — operator-facing doc for the next-gen wake-check cron prompt. Fixes v1's core failure (flag overwrite → missed utterances) via sheet-cursor protocol.

### Added — Append-only cleaned transcript
- `ears/sheet_maintainer.py` — daemon that tails `ears/all-heard.txt` (raw) and mirrors cleaned lines to `ears/all-heard-clean.txt`. Collapses repeated-word runs ("hello hello hello hello" → "hello hello"), normalizes punctuation, drops Whisper hallucination patterns (`[MUSIC]`, punctuation-only, music notes). Byte-offset state file (`.sheet-maintainer-pos`) survives restarts; handles file truncation. CLI: `--poll`, `--from-start`.
- `brain-heard-cursor.txt` (runtime-created) — integer line count the brain has already responded to. First-tick bootstraps to current total so history isn't re-replayed.

### Added — Persona catalog (33 personas: 24 archetypes + 9 intel-derived)
- `personas/catalog/` — 33 agent-ready persona JSONs. 24 archetypes cover MBTI (8), Jungian archetypes (8), affective registers (4), and specialty behavior envelopes (4). 9 intel-derived agent profiles (`agent-annie`, `agent-axiom`, `agent-brian`, `agent-oliver`, `agent-peter`, `agent-rory`, `agent-rune`, `agent-valorie`, `agent-webber`) are composed from those agents' own self-reports. All pass engine-compatibility validation (required fields, palette RGB ranges, personality floats in range, `base_mode`/`eye_state`/`mouth_shape` values confirmed in engine's supported sets, 5-8 expressions each). Originals (`axiom`, `ember`, `nova`, `ysmara`) untouched.
- `personas/catalog/README.md` — taxonomy, design calls, engine-compatibility notes.
- Defaults chosen: `voice.provider: "sapi"` (free-tier friendly), `voice.elevenlabs_voice_id: null` (fill-in slot), `onboarded: true` (drop-in-ready as `config/face.json`), `eye_shape: "round"` (current renderer constraint — variety via per-expression `eye_state`).
- Juno (Stoic) ships two custom expressions inline (`composed_nod`, `measured_approval`) using engine-supported values only; bank promotion deferred.

### Added — Sense-toggle UX spec (not yet implemented)
- `face/SENSE-TOGGLES-SPEC.md` — design for per-sense eye/ear/voice toggles with keyboard shortcuts, blindfold/ear-cup/mouth-tape overlays, `config/senses.json` schema, and `senses-server.py` sidecar blueprint. Fail-open on missing/corrupt config. Ready to implement after three open questions resolve.

### Changed — Sensor cadence for A/B wake-latency baseline
- `config/eyes.json` — `interval_sec` 30 → 3. Documented in `_interval_note`. Paired with `wake_watcher.py` poll=2s and log-tail sub-second path. Baseline captured for future tweaks.

### Runtime — Whisper default upgrade
- `ears/listener.py` launched with `--model medium.en` (up from `small.en`). Significant quality jump: catches punctuation, handles mid-sentence pauses, far fewer dropped words. ~3x slower than small.en but still realtime. Model size 244MB → 769MB. CLI `--model` flag unchanged; this is a launch-time choice pending the installer picker.

### Fixed — Windows portability pass (validated 2026-04-20/21)
- `ears/listener.py` `transcribe()` — passes float32 numpy audio directly to `whisper.transcribe()` instead of writing a temp WAV and calling `transcribe(path)`. The WAV round-trip silently pulls in `ffmpeg` for decode; on a fresh Windows install without ffmpeg on PATH, Whisper fails with `[WinError 2]` and the listener goes deaf. Direct-array path removes the ffmpeg dependency for the listener's realtime loop. Validated end-to-end — listener transcribes live mic audio into `heard.txt` without any external binary.
- `voice/speak.py` ElevenLabs playback — swapped PowerShell `WMPlayer.OCX` COM loop (hung on the playState poll) for `winmm.dll mciSendStringW` via ctypes. MCI's `play <alias> wait` blocks cleanly until playback ends, no COM flakiness, no external deps. Verified with real EL TTS output + lip-sync tracking.
- `voice/speak.py` field-name fix — preview-audio field in EL responses is `audio_base_64` (underscore); the original guide prose had `audio_base64`. The shipped voice-design flow reads both for safety.

### Added — ElevenLabs sub-toggle (credit-save mode)
- `config/senses.json` — new `voice_elevenlabs` boolean (default `true`). When `voice=true` AND `voice_elevenlabs=false`, the EL path is skipped and speech falls to SAPI — keeps the voice alive but preserves EL credit for when the operator actually wants the premium voice.
- `voice/speak.py` — `speak()` reads `voice_elevenlabs` from senses; when false, prints `[speak] EL toggle off — using SAPI (credit-save mode)` and routes to `_sapi_speak()` regardless of key presence. Fail-open: missing field or file = EL allowed.
- `config/senses-server.py` — `DEFAULTS` + POST-body `clean` dict include `voice_elevenlabs`. Schema stays v1 (additive, backwards compatible).
- `face/web-face.html` — fourth sense-row `EL VOICE` below `VOICE`; keyboard shortcut `L` (for Labs); pill tooltip adds `L=ON/OFF`. Same switch UI + flash feedback as the other three.
- `face/face-engine.py` — `read_senses()` + `DEFAULT_SENSES` include `voice_elevenlabs` so the field flows through `face-state.json` for any downstream reader that cares. (No overlay — EL is a provider choice, not a visible sense cut.)

### Added — Agent self-designed voice (validated end-to-end)
- Ysmara v2.0.0 persona regenerated via `compose.py` with full override stack: `mbti-entp` personality, `midnight_velvet` palette, `classic_round` face style, `warm_mezzo` voice profile, 6 bank expressions (`focused`, `wide_curious`, `heart_eyes`, `smolder`, `beam`, `giggle`) + 2 custom (`builder_grin`, `ship_it_eyes`), per-slot palette hex overrides, 7 personality floats, voice rate/pitch, glow intensity, and a free-text `voice_design_prompt`. Exercises every layer of the customization surface as a reference self-redesign.
- ElevenLabs voice-design flow validated on a real account (creator tier): 3 previews generated from the prompt, operator-picked (preview 3), permanently saved as voice_id `uZgh7xZsEfZ9KYhiqrGh`, wired into `personas/ysmara.json` + `config/face.json`. Lip-sync firing with real EL character-alignment timestamps → word timings → face-engine `mouth_openness`.
- EL voice-design gotchas documented: `text` sample must be ≥100 chars; audio field is `audio_base_64` (underscore); `voice_description` ≥20 chars rewards detail.

### Bulletin sent
- `Z:/inbox/axiom/2026-04-20T19-00-03Z_ysmara-create-axiom-body-whisper-model-picker.json` — requests `create-axiom-body` installer to prompt for Whisper model (tiny.en/base.en/small.en/medium.en/large-v3/large-v3-turbo) with per-profile recommended badges, parallel to the existing YOLO picker. Persists to `config/ears.json`.

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
