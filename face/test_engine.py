"""
Quick smoke test for face-engine.py.
Imports the engine as a module, drives it through every mode with short
phases (0.5-1s each), and asserts the expected face-state.json output.
Prints a per-mode summary and a final PASS/FAIL tally.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_PATH = HERE / "face-engine.py"
BASE = HERE.parent

spec = importlib.util.spec_from_file_location("face_engine", ENGINE_PATH)
fe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fe)


def clear_all():
    for p in (fe.SCENE_FILE, fe.LISTENING_FLAG, fe.MUTE_FLAG, fe.VOICE_META, fe.STATE_FILE):
        try: os.remove(p)
        except OSError: pass


def write_scene(people, gx=0, gy=0):
    with open(fe.SCENE_FILE, "w") as f:
        json.dump({"people_count": people, "gaze_target": {"x": gx, "y": gy}}, f)


def touch(p):
    with open(p, "w") as f: f.write("1")


def write_voice_meta(duration_sec):
    words = []
    t = 0.0
    started = time.time() * 1000.0
    while t < duration_sec:
        s = t + 0.1; e = s + 0.3
        if e > duration_sec: break
        words.append({"s": round(s, 3), "e": round(e, 3), "w": f"word{len(words)}"})
        t = e + 0.1
    with open(fe.VOICE_META, "w") as f:
        json.dump({
            "schema_version": 1,
            "words": words,
            "started_at_ms": started,
            "est_end_ms": started + duration_sec * 1000,
            "provider": "mock",
            "voice_id": "",
            "text": "mock test"
        }, f)


def run_phase(engine, label, duration_sec, setup_fn, expected_modes):
    setup_fn()
    end = time.time() + duration_sec
    last = time.time()
    modes_seen = set()
    final_state = None
    while time.time() < end:
        now = time.time()
        dt_ms = (now - last) * 1000.0
        last = now
        state = engine.tick(dt_ms)
        modes_seen.add(state["mode"])
        final_state = state
        time.sleep(fe.TICK_SEC)

    ok = any(m in modes_seen for m in expected_modes)
    status = "PASS" if ok else "FAIL"
    expected_str = " or ".join(expected_modes)
    print(f"  [{status}] {label:<30} -> mode={final_state['mode']:<10} seen={sorted(modes_seen)} (expected: {expected_str})")
    return ok, final_state


def main():
    print("=== face-engine smoke test ===")
    print(f"Engine: {ENGINE_PATH}")
    print(f"State:  {fe.STATE_FILE}")
    clear_all()

    cfg = fe.load_config(fe.DEFAULT_CONFIG)
    print(f"Config: agent_name={cfg.get('agent_name')}  palette.eye={cfg.get('palette',{}).get('eye')}")

    engine = fe.FaceEngine(cfg)

    phases = [
        ("idle (no one)",      1.5, lambda: clear_all(), ["idle"]),
        ("person arrives",     0.5, lambda: write_scene(1, 2, 0), ["surprised"]),
        ("stay attentive-ish", 2.0, lambda: write_scene(1, 2, 0), ["attentive", "eye_tag", "curious", "tongue", "idle"]),
        ("listening",          1.5, lambda: (write_scene(1, 2, 0), touch(fe.LISTENING_FLAG)), ["listening"]),
        ("thinking after list",1.5, lambda: (os.remove(fe.LISTENING_FLAG), write_scene(0, 0, 0)), ["thinking"]),
        ("speaking",           2.0, lambda: (touch(fe.MUTE_FLAG), write_voice_meta(2.0)), ["speaking"]),
        ("post-speak idle",    1.5, lambda: clear_all(), ["idle", "thinking"]),
    ]

    passes = 0; total = 0
    for label, dur, setup, expected in phases:
        ok, state = run_phase(engine, label, dur, setup, expected)
        total += 1
        passes += int(ok)

    # Verify final state on disk
    final_json = None
    try:
        with open(fe.STATE_FILE) as f:
            final_json = json.load(f)
    except Exception as e:
        print(f"[FAIL] couldn't read final state: {e}")

    if final_json:
        required = ["schema_version", "agent_name", "mode", "mouth", "look_x", "look_y",
                    "eye_state", "glow", "palette"]
        missing = [k for k in required if k not in final_json]
        if missing:
            print(f"[FAIL] final state missing keys: {missing}")
        else:
            print(f"[PASS] final state has all required keys. schema_version={final_json['schema_version']}")
            passes += 1
        total += 1

    print()
    print(f"=== {passes}/{total} checks passed ===")
    clear_all()
    return 0 if passes == total else 1


if __name__ == "__main__":
    sys.exit(main())
