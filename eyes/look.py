"""
AXIOM Eyes — on-demand vision.

The ambient daemon (`ears/vision.py`) is only the *starting point* — a
continuous scene.json stream of who/what is in frame. This script is the
agent's active eyes: call it any time to take a picture or a short video
and get back structured analysis.

Capabilities:
  - Photo  : snap one frame, run YOLO, optionally Claude Vision for a semantic
             description. Saves the image for the agent to reference later.
  - Video  : capture N seconds, save mp4/avi, run YOLO on the last frame,
             optionally Claude Vision on a mid-clip frame.
  - Always-on by default. Disabled only if:
       * `config/eyes.off` file exists, OR
       * env `AXIOM_EYES_DISABLED=1`, OR
       * no working camera is present.

Semantic description (Claude Vision) is an UPGRADE path:
  - If ANTHROPIC_API_KEY env is set OR `config/anthropic_api_key.txt` exists,
    the captured image is sent to claude-haiku-4-5 for a short description.
  - Otherwise, YOLO classes + counts are the baseline.

Output: prints a JSON blob to stdout so the calling agent can parse directly.

Usage:
  python eyes/look.py                        # photo + analysis
  python eyes/look.py --photo                # same
  python eyes/look.py --video --seconds 5    # 5-second clip
  python eyes/look.py --prompt "who is in this frame?"   # custom vision prompt
  python eyes/look.py --no-describe          # YOLO only (skip Claude Vision)
  python eyes/look.py --camera 1             # override camera index
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EYES_DIR = ROOT / "eyes"
CAPTURE_DIR = EYES_DIR / "captures"
OFF_FLAG = ROOT / "config" / "eyes.off"
API_KEY_FILE = ROOT / "config" / "anthropic_api_key.txt"
# Ambient daemon (ears/vision.py) writes every snap here. Photo mode uses it
# by default so we don't fight the ambient daemon for the camera.
AMBIENT_SNAP = ROOT / "ears" / "latest_snap.jpg"
AMBIENT_SNAP_STALE_SEC = 60

# Reuse the existing vision code rather than duplicating it.
sys.path.insert(0, str(ROOT / "ears"))
import vision as ambient_vision  # noqa: E402


def eyes_disabled_reason():
    """Return a string reason if eyes should not fire, else None."""
    if os.environ.get("AXIOM_EYES_DISABLED", "").strip() in {"1", "true", "yes"}:
        return "AXIOM_EYES_DISABLED env is set"
    if OFF_FLAG.exists():
        return f"{OFF_FLAG} exists"
    return None


def read_anthropic_key():
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if k:
        return k
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text(encoding="utf-8").strip()
    return ""


def claude_vision_describe(image_path, prompt, api_key):
    """Send a single frame to Claude Vision. Returns {description, model, error}."""
    try:
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    except Exception as e:
        return {"description": None, "error": f"read image: {e}"}

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 400,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text",  "text": prompt},
            ],
        }],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            j = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:400]
        return {"description": None, "error": f"Claude {e.code}: {err}"}
    except Exception as e:
        return {"description": None, "error": str(e)}

    # Extract first text block from response.content
    text = ""
    for block in j.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")
    return {
        "description": text.strip() or None,
        "model": j.get("model"),
        "usage": j.get("usage"),
        "error": None,
    }


def _ambient_snap_age_sec():
    if not AMBIENT_SNAP.exists():
        return None
    return time.time() - AMBIENT_SNAP.stat().st_mtime


def take_photo(camera_idx, prompt, do_describe, force_fresh):
    """Photo mode. By default uses the ambient daemon's latest_snap.jpg if it's
    fresh, so we don't fight the daemon for the camera. --fresh forces live."""
    import cv2

    frame = None
    source = None
    age = _ambient_snap_age_sec()

    if not force_fresh and age is not None and age <= AMBIENT_SNAP_STALE_SEC:
        frame = cv2.imread(str(AMBIENT_SNAP))
        if frame is not None:
            source = "ambient_cache"

    if frame is None:
        # Fall back to live capture (works if ambient is off or --fresh was set).
        frame = ambient_vision.capture_frame(camera_idx)
        if frame is not None:
            source = "live"

    if frame is None:
        return {
            "ok": False,
            "error": "no_frame_available",
            "camera": camera_idx,
            "ambient_snap_age_sec": round(age, 2) if age is not None else None,
            "hint": "Ambient daemon may be holding the camera. Stop ears/vision.py or use --fresh once it releases.",
        }

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    image_path = CAPTURE_DIR / f"photo-{stamp}.jpg"
    cv2.imwrite(str(image_path), frame)

    try:
        scene = ambient_vision.analyze_frame(frame)
    except Exception as e:
        scene = {"error": f"analyze_failed: {e}"}

    out = {
        "ok": True,
        "kind": "photo",
        "source": source,
        "path": str(image_path),
        "camera": camera_idx,
        "scene": scene,
        "description": None,
    }
    if source == "ambient_cache":
        out["ambient_snap_age_sec"] = round(age, 2)

    if do_describe:
        api_key = read_anthropic_key()
        if api_key:
            desc = claude_vision_describe(str(image_path), prompt, api_key)
            out["description"] = desc.get("description")
            out["vision_model"] = desc.get("model")
            if desc.get("error"):
                out["vision_error"] = desc["error"]
        else:
            out["vision_error"] = "no ANTHROPIC_API_KEY — skipped semantic description"

    return out


def take_video(camera_idx, seconds, prompt, do_describe):
    import cv2
    cap = cv2.VideoCapture(camera_idx, ambient_vision._cv_backend())
    if not cap.isOpened():
        return {"ok": False, "error": "camera_unavailable", "camera": camera_idx}

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    video_path = CAPTURE_DIR / f"clip-{stamp}.mp4"
    midframe_path = CAPTURE_DIR / f"clip-{stamp}-mid.jpg"

    # Probe first frame for dimensions.
    ret, first = cap.read()
    if not ret or first is None:
        cap.release()
        return {"ok": False, "error": "initial_frame_failed", "camera": camera_idx}
    h, w = first.shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 15.0, (w, h))
    writer.write(first)

    frames_written = 1
    mid_frame = first
    end_at = time.time() + max(1, int(seconds))
    try:
        while time.time() < end_at:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)
            mid_frame = frame  # last successful frame doubles as mid sample
            frames_written += 1
    finally:
        writer.release()
        cap.release()

    cv2.imwrite(str(midframe_path), mid_frame)

    try:
        scene = ambient_vision.analyze_frame(mid_frame)
    except Exception as e:
        scene = {"error": f"analyze_failed: {e}"}

    out = {
        "ok": True,
        "kind": "video",
        "path": str(video_path),
        "mid_frame": str(midframe_path),
        "seconds": seconds,
        "frames_written": frames_written,
        "camera": camera_idx,
        "scene": scene,
        "description": None,
    }

    if do_describe:
        api_key = read_anthropic_key()
        if api_key:
            desc = claude_vision_describe(str(midframe_path), prompt, api_key)
            out["description"] = desc.get("description")
            out["vision_model"] = desc.get("model")
            if desc.get("error"):
                out["vision_error"] = desc["error"]
        else:
            out["vision_error"] = "no ANTHROPIC_API_KEY — skipped semantic description"

    return out


def main():
    parser = argparse.ArgumentParser(description="AXIOM Eyes — on-demand photo + video + analysis")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--photo", action="store_true", help="Take one photo (default)")
    mode.add_argument("--video", action="store_true", help="Capture a short video clip")
    parser.add_argument("--seconds", type=int, default=4, help="Video length (default 4s)")
    parser.add_argument("--camera", type=int, default=None, help="Camera index (auto-detect if omitted)")
    parser.add_argument("--prompt", default="Describe what you see in this frame in 2-3 sentences. Note people, objects, context.", help="Prompt sent to Claude Vision")
    parser.add_argument("--no-describe", action="store_true", help="Skip Claude Vision (YOLO only)")
    parser.add_argument("--fresh", action="store_true", help="Photo mode: force a live camera capture instead of using the ambient snap cache")
    args = parser.parse_args()

    reason = eyes_disabled_reason()
    if reason:
        print(json.dumps({"ok": False, "error": "eyes_disabled", "reason": reason}))
        return

    do_describe = not args.no_describe

    # For photo mode, the ambient cache is fine even without a live camera probe.
    need_live_camera = args.video or args.fresh
    camera = args.camera
    if camera is None and need_live_camera:
        camera = ambient_vision.find_camera()
    if camera is None and need_live_camera:
        print(json.dumps({"ok": False, "error": "no_camera_found"}))
        return

    if args.video:
        result = take_video(camera, args.seconds, args.prompt, do_describe)
    else:
        result = take_photo(camera if camera is not None else 0, args.prompt, do_describe, args.fresh)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
