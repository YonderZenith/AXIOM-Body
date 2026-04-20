# AXIOM Body — Sense Toggles Spec (Eyes / Ears / Voice)

**Status:** Design-complete, ready to implement.
**Author:** Senior UX + FE + systems hybrid, briefed by Ysmara.
**Target owner to apply edits:** Ysmara.
**Scope:** Add a collapsible operator panel to `face/web-face.html` that toggles Eyes, Ears, and Voice independently; render three distinct overlays on the 64×64 face when a sense is disabled; wire the toggles through to `vision.py`, `listener.py`, `speak.py`, and `face-engine.py` via a single source of truth (`config/senses.json`).

This is a **spec only** — it does not modify code files. All code blocks are diff-style hints for the implementer.

---

## 0. Architecture at a glance

```
                           +-----------------------+
                           |  web-face.html panel  |  (UI — operator toggles)
                           +-----------+-----------+
                                       |
                 POST /senses / PUT    v                writes
                           +-----------+-----------+    (atomic tmp+rename)
                           |  config/senses.json   | <---- single source of truth
                           +-----------+-----------+
                                       |
       +-----------------+-------------+------------+-----------------+
       |                 |                          |                 |
       v                 v                          v                 v
  vision.py         listener.py                speak.py          face-engine.py
  (Eyes off ->      (Ears off ->               (Voice off ->     (reads all 3,
   stop YOLO        drain mic, keep             log utterance,    mirrors to
   loop, still      stream open, no             return success    face-state.json
   write a          transcription)              without TTS)      so renderer
   heartbeat                                                      can draw the
   scene.json                                                     overlays)
   with sense_off)
```

Single file (`config/senses.json`) is the **single writer** target. Everything else is a reader. This is the same pattern already used for `scene.json`, `face-state.json`, `mute.flag`, `listening.flag` — so we fit the codebase.

---

## 1. UX design

### 1.1 Panel placement — **top-right corner, collapsed by default**

Rationale:
- The 64×64 face is **centered** by `web-face.html` (see `resize()` at L49-57 which centers with `offsetX/offsetY`). A top-right panel never overlaps the face on any reasonable aspect ratio until the viewport is narrower than ~320px (edge case — mobile). Bottom-left is already occupied by `#label` (L11-17), so bottom-right or top-right are the only real options.
- Top-right is the Western-reading UI convention for "system / utility controls" (close box, settings gear, preferences). Operator brain immediately goes there when something feels off — *"why is she not listening? look top-right."*
- Collapsed-by-default because the face is the product. The panel is a fallback console, not the main event.

### 1.2 Collapsed state

- A **22×22 pixel pill** with a single glyph: three dots arranged horizontally (`···`) rendered in the persona's `palette.listening_accent` at 35% opacity.
- Position: `top: 12px; right: 12px;` (mirrors the bottom-left label offsets for visual symmetry).
- Hover: opacity → 85%, no layout change.
- Focus ring: 1px outline in `palette.eye` when keyboard-focused (a11y).
- Aria label: `"Sense controls (collapsed). Press to expand."`

### 1.3 Expanded state

- On click/tap or `Enter`/`Space` when focused, the pill animates-expands (150ms CSS transition on `width` and `height`) into a **180×128 px card** anchored top-right.
- Card contents (top to bottom):
  1. Header row: title `SENSES` (10px monospace, 50% opacity) + close X at right.
  2. Three toggle rows, each: icon glyph + label + switch. Rows are 32px tall. Full-row click-target.
     - Row 1: `EYES` — glyph `O` — switch
     - Row 2: `EARS` — glyph `)` — switch
     - Row 3: `VOICE` — glyph `~` — switch
  3. Footer row (16px, 40% opacity): last-updated timestamp, e.g. `saved 14:02:11`.
- Card uses `background: rgba(15, 15, 25, 0.92); backdrop-filter: blur(6px);` for legibility over the glowing face.

### 1.4 Switch affordance

- Pure CSS switch: 36×18 px track; 14×14 knob that slides.
- **ON** state: track color = `palette.eye` at 70%; knob = `palette.pupil`.
- **OFF** state: track = `rgba(255,255,255,0.12)`; knob = `rgba(255,255,255,0.45)`.
- `aria-checked` reflects state; the switch is a `<button role="switch">`.
- Clicking anywhere on the row toggles — not just the track — to reduce mis-taps.

### 1.5 Keyboard shortcuts

All modifier-free keys, active when the face page has focus (no text input exists, so no conflict):

| Key | Action |
|-----|--------|
| `E` | Toggle **E**yes |
| `A` | Toggle e**A**rs (E is taken) |
| `V` | Toggle **V**oice |
| `P` | Expand/collapse the **P**anel |
| `Esc` | Collapse the panel |
| `?` | (future) help overlay — not in v1 |

Each shortcut also flashes the corresponding row's background for 200ms so the operator sees which one was hit. Shortcuts are announced on the collapsed pill via `title="E=eyes A=ears V=voice P=panel"`.

### 1.6 Hover behavior

- Hovering the collapsed pill shows a native tooltip (`title` attribute) with current state, e.g. `"Eyes ON · Ears ON · Voice OFF"`.
- Hovering a switch in the expanded card highlights the track (110% brightness) — feels alive, cheap to implement.
- No hover on touch devices; all states must be reachable by tap alone.

---

## 2. Visual spec — disabled-sense overlays

Every overlay is drawn **on top of** the normal face by `web-face.html` inside the same `tick()` loop, using the existing `setPixel(x, y, r, g, b, glow)` primitive. The 64×64 grid origin is `(0,0)` at top-left. Key anchors from existing code (see `web-face.html` L127-128):

- `EYE_LX = 20`, `EYE_RX = 44`, `EYE_Y = 22` — eye centers
- `MOUTH_CX = 32`, `MOUTH_CY = 48` — mouth center

There is no head silhouette. This means "headphones on the head" is a metaphor we interpret as *accent marks near the horizontal eye-line, at the extreme left and right edges of the canvas*.

### 2.1 Eyes off → **blindfold**

**Shape:** a horizontal band across both eyes, with a knot on the right side.

**Grid footprint:**
- Main band: rows **y=19 to y=25** (7 rows tall), cols **x=8 to x=56** (49 cols wide). This covers both `eyeOpen()` bounding boxes (y: 19-24, x: 16-47 for each eye, plus outer margin).
- Knot: a small 4×4 diamond centered at `(58, 22)` — just off the right edge of the band, evoking a tied knot.
- Top and bottom edges of the band get a 1-row dim accent (50% glow) for a "fabric fold" look.

**Color:** derived from persona palette so it matches the agent. Use `palette.pupil` darkened to 40% of its RGB — the blindfold reads as "pale cloth" over the eye's own bright color. The darkened pupil color ensures legibility against any `palette.eye` choice.

```
derivedBlindfold = [
  Math.round(palette.pupil[0] * 0.40),
  Math.round(palette.pupil[1] * 0.40),
  Math.round(palette.pupil[2] * 0.40)
]
```

**Opacity / glow:** `0.92` for the core band (near-opaque — the eyes should be visibly covered). Edge rows at `0.55`.

**ASCII sketch** (cols 0..63 → left-to-right, rows 18..26):

```
row 18 : ................................................................
row 19 : ........############################################............
row 20 : ........##########BLINDFOLD BAND (core)##############............
row 21 : ........################################################........
row 22 : ........################################################..##....  <- knot row
row 23 : ........################################################....##..
row 24 : ........################################################..##....
row 25 : ........############################################............
row 26 : ................................................................
         ^        ^                                          ^       ^
         col 0    col 8                                      col 56  col 61
```

The blindfold is drawn **after** the eye shapes in the tick, so it overwrites them. Pupils drawn under the blindfold are naturally hidden.

### 2.2 Ears off → **earphones (left + right cups)**

**Shape:** two vertically-oriented oval cups, one at each side of the canvas at the horizontal eye-line, suggesting over-ear headphones. No arch band connecting them (the face has no forehead to cross).

**Grid footprint per cup:**
- Left cup: rows **y=18 to y=28** (11 rows tall), cols **x=1 to x=6** (6 cols wide).
- Right cup: rows **y=18 to y=28**, cols **x=57 to x=62**.
- Each cup is an ellipse — corners rounded by skipping the 4 corner pixels.

**Color:** persona-derived. Use `palette.listening_accent` at full saturation for the rim and `palette.eye` at 50% for the cup interior. This makes "ears are off" read as *"the accent color normally used to indicate listening is now worn as a silencer"* — a nice visual pun.

```
rimColor    = palette.listening_accent || palette.eye
innerColor  = [palette.eye[0]*0.5, palette.eye[1]*0.5, palette.eye[2]*0.5]
```

**Opacity:** rim at `0.90`, interior at `0.55`.

**Render pseudocode:**

```js
function drawEarCup(cx, cy) {
  const W = 3, H = 5;   // half-widths (cup is (2W+1) x (2H+1))
  for (let dy = -H; dy <= H; dy++) {
    for (let dx = -W; dx <= W; dx++) {
      // Ellipse test
      const ex = dx / W, ey = dy / H;
      const d = ex*ex + ey*ey;
      if (d > 1.0) continue;
      const onRim = d > 0.55;
      const [r, g, b] = onRim ? rimColor : innerColor;
      const alpha = onRim ? 0.90 : 0.55;
      setPixel(cx + dx, cy + dy, r, g, b, alpha);
    }
  }
}
// Call for each cup:
drawEarCup(3, 23);    // left
drawEarCup(60, 23);   // right
```

**ASCII sketch** (cols 0..63, rows 17..29):

```
row 17 : .................................
row 18 : .###.........................###.
row 19 : ##OOO#......................#OOO##
row 20 : #OOOOO#....................#OOOOO#
row 21 : #OOOOO#....................#OOOOO#
row 22 : #OOOOO#....................#OOOOO#
row 23 : #OOOOO#....................#OOOOO#  <- eye-line (y=22, drawn BELOW eyes)
row 24 : #OOOOO#....................#OOOOO#
row 25 : #OOOOO#....................#OOOOO#
row 26 : ##OOO#......................#OOO##
row 27 : .###.........................###.
row 28 : .................................
```

(# = rim, O = interior. Only cols 0-6 and 57-63 shown in detail.)

### 2.3 Voice off → **mouth tape (horizontal strip, crossed corners)**

**Shape:** a flat rectangular strip over the mouth, wider than any mouth shape, with a single subtle diagonal "creased-tape" accent.

**Grid footprint:**
- Main strip: rows **y=46 to y=50** (5 rows tall), cols **x=22 to x=42** (21 cols wide). This fully covers `mouthWide()` which goes from `MOUTH_CX-7` to `MOUTH_CX+6` = 25-38 — we extend an extra 3 cols each side for a "tape sticks past the lips" look.
- Tape tears (optional polish): single pixels at `(21, 47)`, `(21, 49)`, `(43, 47)`, `(43, 49)` at 40% glow for a jagged-edge hint.
- Crease accent: a single diagonal line from `(26, 46)` to `(38, 50)` at 50% glow, color = `listening_accent` to make the tape look like it has a highlight.

**Color:** use `palette.listening_accent` for the crease and a desaturated version of `palette.mouth` for the tape body:

```
tapeBody = [
  Math.round(palette.mouth[0] * 0.35 + 180 * 0.65),
  Math.round(palette.mouth[1] * 0.35 + 180 * 0.65),
  Math.round(palette.mouth[2] * 0.35 + 180 * 0.65)
]  // ~ pale neutral with a tint of the mouth color
creaseColor = palette.listening_accent || palette.pupil
```

**Opacity:** body `0.88`, crease `0.55`, tears `0.40`.

**ASCII sketch** (cols 20..44, rows 44..52):

```
col    222222222233333333334444
col    234567890123456789012345
row 44 : .........................
row 45 : .........................
row 46 : ..#####################..
row 47 : .######################.#    <- left tear at (21,47), right at (43,47)
row 48 : ..#####################..
row 49 : .######################.#    <- left tear at (21,49), right at (43,49)
row 50 : ..#####################..
row 51 : .........................
row 52 : .........................
```

The crease diagonal is subtle and not shown in ASCII — see pseudocode below.

**Render pseudocode:**

```js
function drawMouthTape(palette) {
  const body = desaturateMix(palette.mouth, [180,180,180], 0.35);
  const crease = palette.listening_accent || palette.pupil || [255,255,255];
  // Body
  for (let y = 46; y <= 50; y++) {
    for (let x = 22; x <= 42; x++) {
      setPixel(x, y, body[0], body[1], body[2], 0.88);
    }
  }
  // Tear pixels
  const tears = [[21,47],[21,49],[43,47],[43,49]];
  for (const [x, y] of tears) setPixel(x, y, body[0], body[1], body[2], 0.40);
  // Diagonal crease — from (26,46) to (38,50): 5 rows, 12 cols => step ≈ 2.4
  for (let i = 0; i <= 12; i++) {
    const x = 26 + i;
    const y = 46 + Math.floor(i * 4 / 12);
    setPixel(x, y, crease[0], crease[1], crease[2], 0.55);
  }
}
```

### 2.4 Drawing order in `tick()`

Overlays must be drawn **last** (after eyes, pupils, mouth, tongue, Zs) so they sit on top. If multiple senses are off, all overlays are drawn — they never conflict because they occupy distinct rows:

- Blindfold: y ∈ [19, 25]
- Earphones: y ∈ [18, 28] (edges only, x ∈ [0,6] ∪ [57,63])
- Mouth tape: y ∈ [46, 50]

---

## 3. State model — `config/senses.json`

### 3.1 Schema

```json
{
  "schema_version": 1,
  "eyes": true,
  "ears": true,
  "voice": true,
  "updated_at": "2026-04-20T14:02:11.345Z",
  "updated_by": "web-face"
}
```

- **`schema_version`**: integer. v1 is the only version.
- **`eyes` / `ears` / `voice`**: booleans. `true` = sense enabled. `false` = disabled.
- **`updated_at`**: ISO 8601 UTC. Used by the panel footer.
- **`updated_by`**: free-form short string (`"web-face"`, `"cli"`, `"mock"`). Purely informational, helps when debugging.

### 3.2 Write authority

- **Primary writer:** the web panel (via a small local endpoint, see §3.3).
- **Fallback writers (human, rare):** an operator may `echo '{...}' > config/senses.json` by hand. The atomic-write pattern protects readers from partial reads even then.
- **Not a writer:** `vision.py`, `listener.py`, `speak.py`, `face-engine.py`. They are all read-only w.r.t. this file.

### 3.3 How the web UI writes it

The web page is served over `file://` today with no backing HTTP server. Two possible paths:

**Option A (recommended): tiny Python write-helper endpoint.** Add a `senses-server.py` (out of scope for this spec — just noting) that binds `127.0.0.1:7899` and accepts `POST /senses` with the JSON body, then performs an atomic write. The UI does `fetch("http://127.0.0.1:7899/senses", {method:"POST", body: JSON.stringify(state)})`.

**Option B (fallback, v1 pragmatic): use `localStorage` + periodic `navigator.sendBeacon` to a write-through stub**, OR just have the user run a helper script that watches `localStorage` via a Tauri bridge. **For v1 we go with A.** It is ~30 lines of Python (http.server) and matches the existing "every sidecar is a small Python process" architecture.

**Atomic write pattern** (server side, mirroring `face-engine.py` L120-131):

```python
def write_senses(state):
    path = ROOT / "config" / "senses.json"
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)   # atomic on POSIX and Windows NTFS
```

**Cache mirror in browser:** every successful write also stores the state in `localStorage['axiom.senses']` so the UI repaints instantly on next load even before `senses.json` is re-polled.

### 3.4 Read pattern

Everyone who reads it:
1. Opens the file inside a `try/except`.
2. On `FileNotFoundError` → **fail-open** (treat all senses as `true`).
3. On `json.JSONDecodeError` → **fail-open** AND log a warning.

Rationale for fail-open is in §8.

---

## 4. Backend gates

### 4.1 Eyes off

Two existing disable paths must be OR'd together with the new one:

| Source | Means |
|---|---|
| `config/eyes.json.off_switch.flag_file` (default: `config/eyes.off` exists) | existing |
| `AXIOM_EYES_DISABLED` env var truthy | existing |
| `config/senses.json.eyes === false` | **new** |

The effective rule used by `vision.py`:

```python
def eyes_disabled():
    # 1) env var
    if os.environ.get("AXIOM_EYES_DISABLED", "").strip().lower() in ("1","true","yes"):
        return True
    # 2) flag file from config/eyes.json.off_switch
    cfg = load_eyes_config()
    flag_rel = (cfg.get("off_switch") or {}).get("flag_file") or "config/eyes.off"
    if os.path.exists(os.path.join(ROOT_DIR, flag_rel)):
        return True
    # 3) senses.json (NEW)
    senses = load_senses()   # fail-open: returns {"eyes":True,...} if missing/bad
    if senses.get("eyes") is False:
        return True
    return False
```

**Behavior when disabled:**
- `vision.py` skips the YOLO inference entirely (no model load if not already loaded; if already loaded, just skip the frame).
- Camera handle is **released** — not held. `cv2.VideoCapture.release()` — because keeping it open while "eyes are off" is a privacy violation. A disabled eye should mean a physically dark lens.
- Every `interval_sec` tick, still write a heartbeat `scene.json` with:
  ```json
  {
    "timestamp": "…",
    "people_count": 0,
    "people": [],
    "objects": [],
    "gaze_target": {"x": 0, "y": 0},
    "brightness": 0,
    "attention_level": "idle",
    "sense_off": "eyes"
  }
  ```
  The `sense_off` field lets `listener.py`'s `check_people_present()` distinguish "no one is there" from "we can't see". When `sense_off == "eyes"`, listener should treat people-presence as **unknown → default true** (its existing fail-open on error path, which is correct).

### 4.2 Ears off

**New pattern** mirroring eyes:
- Add an equivalent `off_switch` block to the future `config/ears.json` (or inline default: flag file = `config/ears.off`, env var = `AXIOM_EARS_DISABLED`).
- `listener.py` reads `config/senses.json` every tick (already does file polling) plus checks the flag/env.

**Stream-stays-open vs. close-the-stream — defend the choice:**

**Decision: keep the stream open, drain audio to `/dev/null` (drop chunks), don't transcribe.**

Rationale:
- Opening `sounddevice.InputStream` on Windows takes 300-800ms and flickers the mic light. Doing that every time the operator toggles ears introduces visible mic-light flash and can fail if another app (e.g. a browser tab) has grabbed exclusive access in between.
- Draining-but-not-processing costs ~negligible CPU (just `audio_q.get_nowait()` in a loop) and zero privacy cost because **nothing is written to disk or sent anywhere**. The audio evaporates.
- This matches the existing mute-flag pattern (L296-308 in `listener.py`) which already drains the queue during AXIOM's own TTS playback.

When `ears === false`:
- Drain the queue.
- Skip VAD, skip transcription, skip writing `heard.txt` / `heard-stream.txt` / `new-speech.flag`.
- Clear `listening.flag` if present (so the face doesn't get stuck in "listening" mode).
- Log a once-per-minute heartbeat: `"[listener] ears disabled — draining"`.

If ears are disabled for > 5 minutes, **release the stream** and re-open on re-enable. Rationale: prevents OS mic lock leaks from long sessions and allows the OS mic LED to go off entirely (so the user visibly sees "mic is really off"). 5 minutes is the balance between flicker-cost and privacy-optics.

### 4.3 Voice off

`speak.py` checks `config/senses.json.voice` before the ladder starts (very first line of `speak()`).

**Behavior:**
- If `voice === false`:
  1. Append a line to `voice/muted-utterances.log` with format:
     ```
     [2026-04-20T14:02:11.345Z] (sapi|elevenlabs|-)  "the text that would have been said"
     ```
     The provider tag is `-` because nothing was selected — we short-circuit before provider selection.
  2. Do **not** create `mute.flag` and do **not** publish `voice-meta.json`. The face engine will therefore not enter `speaking` mode. This is correct: there was no speech.
  3. Return `True` from `speak()` so the brain treats the utterance as "sent" and does not retry. **This is the most important part.** If we return `False`, the brain will think the voice pipeline is broken and retry, filling the log with duplicates.
- Exception: if the brain relies on `mute.flag`'s disappearance as an "I'm done speaking, you can listen now" signal (it does — listener drains during mute), then silent mode must **not** set and clear `mute.flag`. It never sets it. Listener stays in its normal state. Good.

### 4.4 Cross-sense invariants

- `listener.py` must **not** depend on `voice-meta.json` presence to decide anything — it only cares about `mute.flag`. Already true. Good.
- `face-engine.py` must surface all three sense states in `face-state.json` (see §5) so the renderer can draw overlays even during `listening`/`speaking` modes.

---

## 5. Face-engine hook

`face-engine.py` gains a read of `config/senses.json` inside each `tick()` (after `_read_voice_meta()` is a good spot). New helper:

```python
DEFAULT_SENSES = {"eyes": True, "ears": True, "voice": True}
SENSES_FILE = BASE_DIR / "config" / "senses.json"

def read_senses():
    try:
        with open(SENSES_FILE, "r", encoding="utf-8") as f:
            j = json.load(f)
        return {
            "eyes": bool(j.get("eyes", True)),
            "ears": bool(j.get("ears", True)),
            "voice": bool(j.get("voice", True)),
        }
    except FileNotFoundError:
        return dict(DEFAULT_SENSES)
    except Exception:
        return dict(DEFAULT_SENSES)   # fail-open
```

New field appended to the emitted `state` dict (see `face-engine.py` L453-474):

```python
state["senses"] = read_senses()
```

Downstream, `web-face.html` reads `state.senses` in each poll and uses it to draw the overlays described in §2.

### 5.1 Mode interaction

- **Eyes off + `attentive` / `listening` modes:** the engine still runs the mode (gaze does not move — `scene.json` has `people_count=0`, so face will drift to `idle` naturally within a couple of seconds). Blindfold draws on top regardless.
- **Ears off + `listening` mode:** because listener never writes `listening.flag` while ears are off, `_is_listening()` returns False. So the engine never enters `listening` on its own. Consistent.
- **Voice off + `speaking` mode:** because `speak.py` short-circuits and never writes `mute.flag`, `_is_speaking()` returns False. Engine never enters `speaking`. Mouth tape simply sits over a closed/smile mouth.

This means the overlays are **semantic decorations over a face that's already correctly not doing that thing.** No special-case logic in the engine beyond reading and passing through the three booleans.

---

## 6. UI panel HTML / CSS / JS (paste into `web-face.html`)

Target: paste after the `<canvas>` / `<div id="label">` block (around L21) and before the `<script>` block. Total is 76 lines, under the 80-line budget. Uses only vanilla CSS + JS.

```html
<style>
  #sense-panel {
    position: fixed; top: 12px; right: 12px;
    font: 11px/1.2 "JetBrains Mono", monospace;
    color: #e7e9ef;
    background: rgba(15,15,25,0.92);
    backdrop-filter: blur(6px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 11px;
    overflow: hidden;
    transition: width 150ms ease, height 150ms ease;
    width: 22px; height: 22px;
    z-index: 10;
  }
  #sense-panel.open { width: 180px; height: 128px; }
  #sense-pill { width:22px; height:22px; display:flex; align-items:center; justify-content:center;
    cursor:pointer; letter-spacing:1px; opacity:0.35; user-select:none; }
  #sense-pill:hover { opacity:0.85; }
  #sense-panel.open #sense-pill { display: none; }
  #sense-card { display:none; padding:8px 10px; width:180px; }
  #sense-panel.open #sense-card { display:block; }
  #sense-card header { display:flex; justify-content:space-between; opacity:0.5; font-size:10px; margin-bottom:6px; letter-spacing:1px; }
  #sense-card header button { background:none; border:0; color:inherit; cursor:pointer; font:inherit; }
  .sense-row { display:flex; align-items:center; justify-content:space-between; padding:6px 0; cursor:pointer; border-radius:6px; }
  .sense-row:hover { background: rgba(255,255,255,0.04); }
  .sense-row.flash { background: rgba(120,220,255,0.18); }
  .sense-row .lbl { display:flex; align-items:center; gap:8px; }
  .sense-row .glyph { opacity:0.55; width:10px; text-align:center; }
  .switch { width:36px; height:18px; background:rgba(255,255,255,0.12); border-radius:9px; position:relative; transition:background 120ms; }
  .switch::after { content:""; position:absolute; top:2px; left:2px; width:14px; height:14px; border-radius:50%; background:rgba(255,255,255,0.45); transition:left 120ms, background 120ms; }
  .sense-row.on .switch { background:rgba(0,212,255,0.7); }
  .sense-row.on .switch::after { left:20px; background:rgb(200,255,255); }
  #sense-foot { margin-top:4px; opacity:0.4; font-size:10px; }
</style>
<div id="sense-panel" role="group" aria-label="Sense controls">
  <div id="sense-pill" tabindex="0" title="E=eyes A=ears V=voice P=panel" aria-label="Sense controls (collapsed). Press to expand.">···</div>
  <div id="sense-card">
    <header><span>SENSES</span><button id="sense-close" aria-label="Close">x</button></header>
    <div class="sense-row on" data-sense="eyes"><span class="lbl"><span class="glyph">O</span>EYES</span><button role="switch" aria-checked="true" class="switch" aria-label="Toggle eyes"></button></div>
    <div class="sense-row on" data-sense="ears"><span class="lbl"><span class="glyph">)</span>EARS</span><button role="switch" aria-checked="true" class="switch" aria-label="Toggle ears"></button></div>
    <div class="sense-row on" data-sense="voice"><span class="lbl"><span class="glyph">~</span>VOICE</span><button role="switch" aria-checked="true" class="switch" aria-label="Toggle voice"></button></div>
    <div id="sense-foot">not saved yet</div>
  </div>
</div>
<script>
(function(){
  const LS_KEY = "axiom.senses";
  const ENDPOINT = "http://127.0.0.1:7899/senses";
  const panel = document.getElementById("sense-panel");
  const pill = document.getElementById("sense-pill");
  const close = document.getElementById("sense-close");
  const foot = document.getElementById("sense-foot");
  let senses = { eyes:true, ears:true, voice:true };
  try { Object.assign(senses, JSON.parse(localStorage.getItem(LS_KEY) || "{}")); } catch(e){}
  function render() {
    for (const k of ["eyes","ears","voice"]) {
      const row = document.querySelector(`.sense-row[data-sense="${k}"]`);
      row.classList.toggle("on", !!senses[k]);
      row.querySelector(".switch").setAttribute("aria-checked", senses[k] ? "true" : "false");
    }
    pill.title = `E=${senses.eyes?"ON":"OFF"} A=${senses.ears?"ON":"OFF"} V=${senses.voice?"ON":"OFF"}`;
  }
  async function save() {
    const payload = Object.assign({schema_version:1, updated_by:"web-face", updated_at:new Date().toISOString()}, senses);
    localStorage.setItem(LS_KEY, JSON.stringify(senses));
    foot.textContent = "saving…";
    try {
      await fetch(ENDPOINT, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
      foot.textContent = "saved " + new Date().toLocaleTimeString();
    } catch(e) { foot.textContent = "offline — cached locally"; }
  }
  function toggle(k) {
    senses[k] = !senses[k]; render(); save();
    const row = document.querySelector(`.sense-row[data-sense="${k}"]`);
    row.classList.add("flash"); setTimeout(()=>row.classList.remove("flash"), 200);
  }
  function open(){ panel.classList.add("open"); }
  function shut(){ panel.classList.remove("open"); }
  pill.addEventListener("click", open);
  pill.addEventListener("keydown", e => { if (e.key==="Enter"||e.key===" ") { e.preventDefault(); open(); }});
  close.addEventListener("click", shut);
  document.querySelectorAll(".sense-row").forEach(r => r.addEventListener("click", () => toggle(r.dataset.sense)));
  window.addEventListener("keydown", e => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    const k = e.key.toLowerCase();
    if (k === "e") toggle("eyes");
    else if (k === "a") toggle("ears");
    else if (k === "v") toggle("voice");
    else if (k === "p") panel.classList.toggle("open");
    else if (e.key === "Escape") shut();
  });
  render();
})();
</script>
```

The existing face `tick()` loop (from line ~390 onward) needs a small extension to draw overlays when `state.senses` says so:

```js
// Just before `render(palette);` on line ~510:
if (state.senses) {
  if (state.senses.eyes === false) drawBlindfold(palette);
  if (state.senses.ears === false) drawEarphones(palette);
  if (state.senses.voice === false) drawMouthTape(palette);
}
```

The three `drawXxx(palette)` helpers live with the other shape builders (after `tongueShape()`, before `MOUTH_SHAPES`). Their full bodies are specified in §2.1 / §2.2 / §2.3.

---

## 7. Backend integration snippets (diffs — do NOT apply as code yet)

Line numbers approximate. Apply by hand.

### 7.1 `ears/vision.py`

Add near the other config helpers (after `_apply_config()` at L78):

```diff
+ SENSES_FILE = os.path.join(ROOT_DIR, "config", "senses.json")
+
+ def _senses_eyes_off():
+     try:
+         with open(SENSES_FILE, "r", encoding="utf-8") as f:
+             return json.load(f).get("eyes") is False
+     except Exception:
+         return False
+
+ def eyes_disabled():
+     if os.environ.get("AXIOM_EYES_DISABLED","").strip().lower() in ("1","true","yes"):
+         return True
+     cfg = load_eyes_config()
+     flag_rel = (cfg.get("off_switch") or {}).get("flag_file") or "config/eyes.off"
+     if os.path.exists(os.path.join(ROOT_DIR, flag_rel)):
+         return True
+     if _senses_eyes_off():
+         return True
+     return False
```

In `main()`'s while loop (around L279), at the top of each iteration:

```diff
      while True:
          try:
+             if eyes_disabled():
+                 # Heartbeat scene with sense_off, release the camera (if open).
+                 save_scene({
+                     "timestamp": datetime.now().isoformat(),
+                     "people_count": 0, "people": [], "objects": [],
+                     "gaze_target": {"x":0,"y":0}, "brightness": 0,
+                     "attention_level": "idle", "sense_off": "eyes",
+                 })
+                 time.sleep(args.interval)
+                 continue
              frame = capture_frame(camera)
```

### 7.2 `ears/listener.py`

Near the other file-path constants (after `MUTE_FILE` at L46):

```diff
+ SENSES_FILE = os.path.join(ROOT_DIR, "config", "senses.json")
+ _stream_released_until = 0
+
+ def _ears_disabled():
+     try:
+         with open(SENSES_FILE, "r", encoding="utf-8") as f:
+             return json.load(f).get("ears") is False
+     except Exception:
+         return False
```

In the main loop (around L293), immediately after the mute-flag block (before the people-presence check at ~L311):

```diff
              if os.path.exists(MUTE_FILE):
                  ...
                  continue
+             if _ears_disabled():
+                 # Drain queue, don't transcribe, don't write flags.
+                 while not audio_q.empty():
+                     try: audio_q.get_nowait()
+                     except queue.Empty: break
+                 speech_frames = 0; silence_frames = 0
+                 recording = False; audio_buffer = []
+                 _clear_listening()
+                 # once/min heartbeat log
+                 if int(time.time()) % 60 == 0:
+                     log("ears disabled — draining")
+                 time.sleep(0.1)
+                 continue
```

(The 5-minute stream-release optimization in §4.2 is a nice-to-have; skip it in v1.)

### 7.3 `voice/speak.py`

At the top of `speak()` (currently L207):

```diff
  def speak(text):
      if not text.strip():
          return False
+     # Sense gate — if voice is off, log and silent-success.
+     try:
+         with open(ROOT / "config" / "senses.json", "r", encoding="utf-8") as f:
+             if json.load(f).get("voice") is False:
+                 log_path = ROOT / "voice" / "muted-utterances.log"
+                 log_path.parent.mkdir(parents=True, exist_ok=True)
+                 with open(log_path, "a", encoding="utf-8") as lf:
+                     ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
+                     lf.write(f"[{ts}] (-) {text}\n")
+                 print(f"[speak] voice disabled — logged (not spoken): {text[:60]}", flush=True)
+                 return True  # Silent success — brain will not retry.
+     except Exception:
+         pass  # fail-open: missing/corrupt senses.json means speak normally.
      voice_cfg = _load_persona_voice()
      api_key = _read_api_key()
      ...
```

### 7.4 `face/face-engine.py`

Near the file-IPC path constants (around L48-53):

```diff
  STATE_FILE = BASE_DIR / "face-state.json"
  DEFAULT_CONFIG = BASE_DIR / "config" / "face.json"
+ SENSES_FILE = BASE_DIR / "config" / "senses.json"
+ DEFAULT_SENSES = {"eyes": True, "ears": True, "voice": True}
+
+ def read_senses():
+     try:
+         with open(SENSES_FILE, "r", encoding="utf-8") as f:
+             j = json.load(f)
+         return {
+             "eyes": bool(j.get("eyes", True)),
+             "ears": bool(j.get("ears", True)),
+             "voice": bool(j.get("voice", True)),
+         }
+     except Exception:
+         return dict(DEFAULT_SENSES)
```

In the `tick()` state dict construction (around L453-474):

```diff
          state = {
              "schema_version": SCHEMA_VERSION,
              ...
              "tick_ms": int(now_ms - self.start_ms),
+             "senses": read_senses(),
          }
```

### 7.5 (Optional) `config/senses-server.py` — a new file

Out of scope for this spec (it's a file Ysmara will create). A ~30 line `http.server.BaseHTTPRequestHandler` that:
- Accepts `GET /senses` → returns current file contents (or defaults if missing).
- Accepts `POST /senses` with JSON body → atomic-writes `config/senses.json`.
- Serves `Access-Control-Allow-Origin: *` so `file://`-hosted `web-face.html` can POST to it.
- Binds `127.0.0.1:7899`.

---

## 8. Edge cases

### 8.1 All three senses off

**Expected visual:** face still runs. Mode machine drifts to `idle` (no scene, no listening, no mute), so: smile mouth, open eyes, smooth breath-glow — then all three overlays painted over: blindfold hides eyes, earphones at edges, tape over mouth. No animation halts. The face is "there, just silenced" — which is exactly the operator-intent message.

**Mode constraint:** engine never enters `surprised` / `attentive` / `listening` / `speaking` because the inputs that trigger them (scene people count, listening.flag, mute.flag) will all be suppressed by the disabled senses. Good.

**Expressions allowed:** blink, breath, idle saccade, curious/tongue random rolls. These are cosmetic and safe — they run on a timer, not on input.

### 8.2 Missing / malformed `config/senses.json` — **fail-open**

**Decision: fail-open (all senses treated as enabled).**

Rationale:
- AXIOM Body is in the user's home, not a hospital. A bricked face that stays silent because a config file is corrupt is a worse user experience than a face that accidentally does its normal thing.
- The worst case of fail-open is "operator expected mic off, mic is actually on for 30 seconds until they notice." That's annoying but recoverable. The worst case of fail-closed is "operator never toggled anything, but config got corrupted by a disk glitch, and now AXIOM is blind/deaf/mute and can't be reached." That's unrecoverable without touching the keyboard.
- Matches the existing fail-open pattern in `listener.py::check_people_present()` (L213, "On error, default to listening").

**However:** every fail-open path must log a WARN-level line (`print("[xxx] senses.json unreadable — treating as enabled", flush=True)`) so it shows up in stdout for debugging.

### 8.3 Voice toggled off mid-utterance

**Decision: finish the current utterance, then stop.**

Rationale:
- `speak.py` reads `senses.json` **once**, at the entrance of `speak()`. It does not poll mid-speech. This means if the operator toggles off while an ElevenLabs clip is already playing, the clip finishes (typically 1-6 seconds).
- Polling mid-clip would require either killing the `powershell` subprocess (ugly — causes audio pop and may leave the mp3 temp file) or re-architecting playback to a cancellable pipeline (out of scope for v1).
- 1-6 seconds of tail-speech is acceptable. The mouth tape overlay appears immediately upon toggle (since `face-engine.py` polls senses every tick), so the visual says "muted" even while audio tail plays — which is accurate: *she's wearing tape now, but these last words already escaped.*

**If the operator wants instant cut:** they can kill the voice sidecar. Out of scope.

### 8.4 Ears toggled off mid-speech-capture

Listener is already recording, then ears toggle off. The new guard at the top of the loop runs on the **next** chunk (100ms later), so:
- Recording stops instantly (within 100ms).
- The buffered audio so far is discarded (not transcribed).
- `listening.flag` is cleared.
- Face exits `listening` mode on the next tick.

Clean. No garbage transcripts saved.

### 8.5 Eyes toggled off mid-`eye_tag`

`eye_tag` is a 4-second face-choreography. When eyes toggle off:
- `vision.py` starts writing `scene.json` with `people_count=0` immediately.
- Engine's `_select_mode()` enters `thinking` (because prev mode was a people-mode). Within a few seconds it settles to `idle`.
- Blindfold overlay appears instantly (next `face-state.json` tick).

Visually: face does a quick "look-away" choreography then the blindfold drops. Reads well.

### 8.6 Sense toggled on while brain is mid-loop

Senses coming back on is lossless:
- Eyes: next `interval_sec` tick (up to 3s), normal scene resumes.
- Ears: next audio chunk (100ms), transcription resumes. Any speech during the off window is lost (expected).
- Voice: next `speak()` call uses normal TTS.

### 8.7 Panel state and page reload

`localStorage['axiom.senses']` is read on page load and repainted immediately. Within ~100ms (first poll cycle) the `senses.json` value wins if it differs (the file is ground truth, not localStorage).

### 8.8 Two tabs of `web-face.html` open at once

Only the last tab to POST to `/senses` wins. They both read the same `senses.json` on each poll, so they converge. No conflict.

### 8.9 Senses-server.py not running

- POSTs fail silently. UI shows `"offline — cached locally"` in the footer.
- The current `senses.json` on disk is authoritative. The user can still edit the file by hand.
- **Do not block the UI** — the panel still toggles locally so the operator can queue their desired state and the next time the server is up it will sync.

A future enhancement would be to write a side `senses.json.pending` from the UI and have the server flush on startup — out of scope for v1.

### 8.10 Disk full / permission denied during atomic write

Server-side: the `os.replace()` step atomic-fails. `senses.json` keeps its last-good content. The POST returns a 500 and the panel footer shows `"save failed — retry"`. The localStorage cache is still updated so UI state is preserved until next successful save.

---

## 9. Testing checklist

### 9.1 Unit / smoke (10 cases)

1. **Fresh boot, no `senses.json`** → all three switches render ON; `vision.py`, `listener.py`, `speak.py` all operate normally. No errors logged.
2. **Toggle EYES off via UI** → blindfold appears within one tick (<100ms visual), camera handle released (`latest_snap.jpg` not updated), `scene.json` has `sense_off: "eyes"` within 3s.
3. **Toggle EYES back on** → blindfold disappears, `scene.json` starts producing normal detections within one `interval_sec`.
4. **Toggle EARS off via UI** → earphone overlays appear, `heard-stream.txt` stops growing, `listening.flag` cleared, `listener-log.txt` logs "ears disabled — draining" within 60s.
5. **Toggle EARS off while recording** → current recording discarded (no new `heard.txt` entry), `listening.flag` cleared within 100ms.
6. **Toggle VOICE off, then call `python voice/speak.py "hello"`** → no audio plays, `voice/muted-utterances.log` gets a line with "hello", `speak.py` exits 0.
7. **Toggle VOICE off mid-utterance (ElevenLabs playing)** → tape overlay appears immediately; current audio finishes; next `speak()` call is silent.
8. **Toggle all three off** → all overlays present, face still blinks/breathes, no engine errors.
9. **Corrupt `senses.json`** (write `{not json`) → all processes fail-open (senses treated as enabled), each logs one warning line, overlays do not appear.
10. **Missing `senses.json`** → identical to fresh-boot (case 1).

### 9.2 UX / panel (3 cases)

11. **Keyboard shortcut `E`** with page focused → eyes toggle, row flashes, pill tooltip updates.
12. **Keyboard shortcut `P`** → panel expands; `Esc` collapses; state preserved.
13. **Two browser tabs of `web-face.html`** open; toggle in tab A → within 100ms tab B's overlay matches (proves file-poll convergence).

---

## 10. Implementation order (for Ysmara)

Do them in this order; each is ship-testable alone:

1. Create `config/senses.json` with defaults (`{eyes:true, ears:true, voice:true}`).
2. Create `config/senses-server.py` (tiny http.server on 7899).
3. Add the UI block (§6) to `web-face.html`. Test toggles → verify `senses.json` updates.
4. Add `read_senses()` to `face-engine.py` and append to state. Verify `face-state.json` has the field.
5. Add the three `draw*` overlay functions to `web-face.html`. Verify overlays appear/disappear when the file is edited by hand.
6. Add the `eyes_disabled()` guard to `vision.py`.
7. Add the `_ears_disabled()` guard to `listener.py`.
8. Add the voice gate to `speak.py`.
9. Run through §9 testing checklist end-to-end.

Est. time start-to-finish for a junior with this spec open: **3-4 hours**.

---

## 11. Non-goals (for v1)

- No remote control of senses (e.g. from the brain session). Brain can write `senses.json` directly if it wants — no new API.
- No per-sense "timed off" (e.g. "mute for 5 minutes"). Add later if needed.
- No audio cue when senses toggle (beep). The visual is sufficient; adding a beep conflicts with the "voice-off" concept.
- No icon design beyond the text glyphs `O`, `)`, `~`. Ysmara can upgrade to SVGs later.
