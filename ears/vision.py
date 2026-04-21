"""
AXIOM Eyes — Ambient Vision Daemon
====================================
Periodically captures frames from a USB camera, runs YOLOv8-nano
for person/object detection, and writes scene state to a JSON file.

The brain (main AXIOM session) reads this file to adapt behavior:
- Adjust eye gaze toward detected people
- Increase listener attention when someone is nearby
- React to interesting objects or changes in the scene

Usage:
  python vision.py                # Run with defaults (30s interval)
  python vision.py --interval 15  # Snap every 15 seconds
  python vision.py --camera 0     # Use specific camera index
"""
import os
import sys
import time
import json
import argparse
from datetime import datetime

import cv2
import numpy as np

# Lazy-load YOLO to speed up imports
_model = None
_model_name_loaded = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)  # v2: face-engine reads scene.json from repo root
SCENE_FILE = os.path.join(ROOT_DIR, "scene.json")  # v2: shared with face-engine
SNAP_FILE = os.path.join(BASE_DIR, "latest_snap.jpg")
LOG_FILE = os.path.join(BASE_DIR, "vision-log.txt")
EYES_CONFIG_FILE = os.path.join(ROOT_DIR, "config", "eyes.json")

# YOLO class names we care about (subset of COCO 80)
INTERESTING = {
    0: "person",
    15: "cat", 16: "dog",
    24: "backpack", 25: "umbrella",
    39: "bottle", 41: "cup",
    56: "chair", 57: "couch",
    62: "tv", 63: "laptop", 64: "mouse", 66: "keyboard",
    67: "cell phone", 73: "book",
}

# Valid YOLO model names (ultralytics auto-downloads on first use).
VALID_MODELS = {"yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x"}
DEFAULT_MODEL = "yolov8n"

# Fallback confidence defaults (overridden by config/eyes.json if present).
MIN_CONF = 0.35
PERSON_CONF = 0.25


def load_eyes_config():
    """Read config/eyes.json. Returns {} if missing/corrupt."""
    try:
        with open(EYES_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _apply_config():
    """Pull confidence thresholds from config/eyes.json if present."""
    global MIN_CONF, PERSON_CONF
    cfg = load_eyes_config()
    conf = cfg.get("confidence") or {}
    if isinstance(conf.get("min"), (int, float)):
        MIN_CONF = float(conf["min"])
    if isinstance(conf.get("person"), (int, float)):
        PERSON_CONF = float(conf["person"])


_apply_config()


SENSES_FILE = os.path.join(ROOT_DIR, "config", "senses.json")


def _senses_eyes_off():
    try:
        with open(SENSES_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("eyes") is False
    except Exception:
        return False


def eyes_disabled():
    if os.environ.get("AXIOM_EYES_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        return True
    cfg = load_eyes_config()
    flag_rel = (cfg.get("off_switch") or {}).get("flag_file") or "config/eyes.off"
    if os.path.exists(os.path.join(ROOT_DIR, flag_rel)):
        return True
    if _senses_eyes_off():
        return True
    return False


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def get_model():
    """Load the YOLO model named in config/eyes.json (default yolov8n).
    Falls back to yolov8n if the configured name is unknown."""
    global _model, _model_name_loaded
    if _model is not None:
        return _model
    cfg = load_eyes_config()
    name = str(cfg.get("model") or DEFAULT_MODEL).strip().lower()
    if name not in VALID_MODELS:
        log(f"Unknown YOLO model '{name}' in config/eyes.json — falling back to {DEFAULT_MODEL}")
        name = DEFAULT_MODEL
    from ultralytics import YOLO
    log(f"Loading YOLO model: {name}...")
    _model = YOLO(f"{name}.pt")  # Auto-downloads on first use
    _model_name_loaded = name
    log(f"{name} loaded")
    return _model


def _cv_backend():
    """Use DirectShow on Windows (avoids audio conflict), default elsewhere."""
    import platform
    return cv2.CAP_DSHOW if platform.system() == "Windows" else 0


def find_camera():
    """Find a working camera by testing indices 0-4 for a real image.
    Device indices shift on reboot — this tests by brightness, not index."""
    backend = _cv_backend()
    for i in range(5):
        cap = cv2.VideoCapture(i, backend)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame.mean() > 30:  # Real camera has brightness > 30
                log(f"Auto-detected working camera at index {i} (brightness {frame.mean():.0f})")
                return i
        else:
            continue
    return None


def capture_frame(camera_idx=0):
    """Capture a single frame from the camera."""
    cap = cv2.VideoCapture(camera_idx, _cv_backend())
    if not cap.isOpened():
        log(f"Camera {camera_idx} not available")
        return None
    try:
        ret, frame = cap.read()
        if ret:
            return frame
        else:
            log("Failed to capture frame")
            return None
    finally:
        cap.release()


def analyze_frame(frame):
    """Run YOLO detection on a frame, return structured scene data"""
    model = get_model()
    h, w = frame.shape[:2]

    # Run inference (verbose=False to suppress output)
    results = model(frame, verbose=False)

    detections = []
    people = []

    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # Filter by confidence
            if cls_id == 0 and conf < PERSON_CONF:
                continue
            if cls_id != 0 and conf < MIN_CONF:
                continue

            # Get label
            label = INTERESTING.get(cls_id)
            if label is None:
                # Use YOLO's own class name for unlisted classes
                label = model.names.get(cls_id, f"class_{cls_id}")
                if conf < MIN_CONF:
                    continue

            # Calculate center and relative position
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            box_w = x2 - x1
            box_h = y2 - y1

            det = {
                "label": label,
                "confidence": round(conf, 2),
                "center_x": round(cx / w, 3),  # 0-1 normalized
                "center_y": round(cy / h, 3),
                "width": round(box_w / w, 3),
                "height": round(box_h / h, 3),
                "size": round((box_w * box_h) / (w * h), 4),  # Relative area
            }

            detections.append(det)
            if label == "person":
                people.append(det)

    # Reject "person" detections that are near-certain false positives:
    # (a) bbox dominates the frame AND (b) heavily overlaps a bed/couch/chair.
    # YOLOv8n routinely mislabels rumpled bedding / draped blankets as people
    # with high confidence, which keeps people_count>0 forever and blocks sleep.
    FURNITURE = {"bed", "couch", "chair"}
    furniture = [d for d in detections if d["label"] in FURNITURE]
    def _iou(a, b):
        ax1, ay1 = a["center_x"] - a["width"] / 2, a["center_y"] - a["height"] / 2
        ax2, ay2 = ax1 + a["width"], ay1 + a["height"]
        bx1, by1 = b["center_x"] - b["width"] / 2, b["center_y"] - b["height"] / 2
        bx2, by2 = bx1 + b["width"], by1 + b["height"]
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        union = a["width"] * a["height"] + b["width"] * b["height"] - inter
        return inter / union if union > 0 else 0.0
    kept_people = []
    for p in people:
        dominating = p["size"] > 0.5
        over_furniture = any(_iou(p, f) > 0.4 for f in furniture)
        if dominating and over_furniture:
            # Drop from people list and mark the detection as furniture-miscall.
            for d in detections:
                if d is p:
                    d["label"] = "furniture_miscall"
                    break
            continue
        kept_people.append(p)
    people = kept_people

    # Determine eye gaze target (look at closest/largest person)
    gaze_x, gaze_y = 0, 0
    if people:
        # Pick the largest person (closest to camera)
        biggest = max(people, key=lambda p: p["size"])
        # Map to eye offset: center=0, left=-3, right=+3
        gaze_x = round((biggest["center_x"] - 0.5) * 6)
        gaze_y = round((biggest["center_y"] - 0.5) * 4)
        # Clamp
        gaze_x = max(-3, min(3, gaze_x))
        gaze_y = max(-2, min(2, gaze_y))

    # Overall scene brightness
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))

    scene = {
        "timestamp": datetime.now().isoformat(),
        "people_count": len(people),
        "people": people,
        "objects": [d for d in detections if d["label"] != "person"],
        "gaze_target": {"x": gaze_x, "y": gaze_y},
        "brightness": round(brightness, 1),
        "attention_level": "high" if people else ("medium" if detections else "idle"),
        "frame_size": {"w": w, "h": h},
    }

    return scene


def save_scene(scene):
    """Write scene data to JSON for the brain to read"""
    with open(SCENE_FILE, "w", encoding="utf-8") as f:
        json.dump(scene, f, indent=2)


def main():
    cfg = load_eyes_config()
    default_interval = int(cfg.get("interval_sec") or 30)
    default_camera = cfg.get("camera_index")
    if not isinstance(default_camera, int):
        default_camera = None

    parser = argparse.ArgumentParser(description="AXIOM Eyes — Ambient Vision")
    parser.add_argument("--camera", type=int, default=default_camera, help="Camera index (auto-detects camera if omitted)")
    parser.add_argument("--interval", type=int, default=default_interval, help=f"Seconds between snapshots (default {default_interval})")
    parser.add_argument("--once", action="store_true", help="Capture once and exit")
    args = parser.parse_args()

    camera = args.camera
    if camera is None:
        camera = find_camera()
        if camera is None:
            log("No working camera found, defaulting to 0")
            camera = 0
    else:
        log(f"Using manually specified camera {camera}")

    log(f"AXIOM Eyes starting. Camera {camera}, interval {args.interval}s")

    # Pre-load model
    get_model()

    if args.once:
        frame = capture_frame(camera)
        if frame is not None:
            cv2.imwrite(SNAP_FILE, frame)
            scene = analyze_frame(frame)
            save_scene(scene)
            log(f"Scene: {scene['people_count']} people, {len(scene['objects'])} objects, "
                f"brightness {scene['brightness']}, attention: {scene['attention_level']}")
            print(json.dumps(scene, indent=2))
        return

    log("Vision daemon active. Scanning...")

    last_people = 0
    while True:
        try:
            if eyes_disabled():
                # Heartbeat scene with sense_off so listener knows the diff
                # between "no one is there" and "we can't see".
                save_scene({
                    "timestamp": datetime.now().isoformat(),
                    "people_count": 0,
                    "people": [],
                    "objects": [],
                    "gaze_target": {"x": 0, "y": 0},
                    "brightness": 0,
                    "attention_level": "idle",
                    "sense_off": "eyes",
                })
                time.sleep(args.interval)
                continue
            frame = capture_frame(camera)
            if frame is None:
                time.sleep(args.interval)
                continue

            # Save latest snap
            cv2.imwrite(SNAP_FILE, frame)

            # Analyze
            scene = analyze_frame(frame)
            save_scene(scene)

            people = scene["people_count"]
            objects = len(scene["objects"])
            brightness = scene["brightness"]
            attention = scene["attention_level"]

            # Log changes or periodic status
            if people != last_people:
                if people > 0:
                    log(f"People detected: {people} (gaze -> {scene['gaze_target']})")
                else:
                    log("No people in view")
                last_people = people
            else:
                log(f"Scene: {people} people, {objects} objects, "
                    f"brightness {brightness:.0f}, {attention}")

            time.sleep(args.interval)

        except KeyboardInterrupt:
            log("Vision stopped")
            break
        except Exception as e:
            log(f"Vision error: {e}")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
