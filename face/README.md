# AXIOM Face — Web LED Matrix Renderer

A browser-based 64x64 LED matrix face for the AXIOM Body system. Drop-in replacement for the BLE LED backpack — same animations, rendered on screen.

## Quick Start

Just open the HTML file in a browser:

```
face/web-face.html
```

The face runs in **standalone demo mode** by default — autonomous blinks, saccades, gaze shifts, and occasional mouth movements. No server or dependencies required.

## With the Body System

To connect the face to the AXIOM voice pipeline (respond.py), run the bridge:

```bash
cd face/
python face-bridge.py
```

Then serve the face directory with any static file server:

```bash
# Python
python -m http.server 8080

# Node
npx serve .
```

Open `http://localhost:8080/web-face.html` in a browser. The face will poll `face-state.json` every 100ms and animate the mouth in sync with speech.

## How It Works

- `web-face.html` — Self-contained renderer. 64x64 canvas with LED matrix aesthetic, eye animations (blink, saccade, gaze), and mouth shapes (4 levels).
- `face-bridge.py` — Reads `mute.flag` (created by respond.py during speech) and writes `face-state.json` with the current face state.
- `face-state.json` — Shared state file. Format:

```json
{
  "mode": "idle",
  "mouth": 0,
  "look_x": 0,
  "look_y": 0
}
```

| Field    | Values                        | Description                  |
|----------|-------------------------------|------------------------------|
| `mode`   | `idle`, `speaking`, `sleep`   | Current face mode            |
| `mouth`  | `0` - `3`                     | Mouth openness (0 = closed)  |
| `look_x` | `-3` to `3`                   | Horizontal gaze offset       |
| `look_y` | `-2` to `2`                   | Vertical gaze offset         |

## Standalone Demo

If `face-state.json` is not available (e.g., opened directly as a file), the renderer runs fully autonomous animations:

- Random blinks every 3-5 seconds
- Micro-saccades (tiny 1px jitter)
- Gaze shifts every 4-8 seconds
- Occasional mouth movement bursts
- Subtle breathing pulse on all pixels

## License

Part of the [AXIOM Body](https://github.com/YonderZenith/AXIOM-Body) open-source project.
