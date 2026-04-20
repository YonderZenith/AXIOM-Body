"""
AXIOM Body Face Engine v2 — pure state producer
================================================
Reads sensor / system inputs. Writes face-state.json. Knows nothing about
how the face gets rendered — that's the renderer's job (web-face.html,
ble-renderer.py, Tauri panel, etc.).

Inputs (file-based IPC):
  scene.json         — vision.py output (people_count, gaze_target, faces)
  listening.flag     — listener.py creates while VAD says user is speaking
  mute.flag          — respond.py creates while TTS is playing
  voice-meta.json    — respond.py writes word timings for mouth sync
  config/face.json   — per-agent identity (colors, voice, personality)

Output:
  face-state.json    — rich state every ~50ms, schema_version=2

State machine modes:
  sleep       — no people recently; eyes closed + Z's floating
  idle        — base state; blinks, micro-saccades, smile
  attentive   — person in view, eyes track them
  eye_tag     — saw a person, shy glance pattern
  curious     — something novel, squint
  tongue      — playful stick-out (low probability)
  surprised   — person just arrived, or sudden scene change
  listening   — user is talking; widen eyes, gaze to speaker, glow pulse
  thinking    — between listening and speaking (no mute, no listening)
  speaking    — mute.flag present; mouth driven by voice-meta word timings

Tick: 50ms (20 Hz). No BLE, no audio, no network. Pure I/O on files.

Usage:
  python face-engine.py                       # Run engine loop
  python face-engine.py --config my.json      # Override config path
  python face-engine.py --mock                # Emit a demo sequence for testing
"""
import os
import sys
import json
import time
import math
import random
import argparse
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
SCENE_FILE = BASE_DIR / "scene.json"
LISTENING_FLAG = BASE_DIR / "listening.flag"
MUTE_FLAG = BASE_DIR / "mute.flag"
VOICE_META = BASE_DIR / "voice-meta.json"
STATE_FILE = BASE_DIR / "face-state.json"
DEFAULT_CONFIG = BASE_DIR / "config" / "face.json"

TICK_SEC = 0.05                   # 20 Hz
SCHEMA_VERSION = 2


# --- Config ---
DEFAULT_CONFIG_INLINE = {
    "agent_name": "Axiom",
    "agent_slug": "axiom",
    "palette": {
        "bg": [10, 10, 15],
        "eye": [0, 212, 255],
        "pupil": [200, 255, 255],
        "mouth": [16, 185, 129],
        "tongue": [220, 60, 90],
        "listening_accent": [120, 220, 255],
        "thinking_accent": [180, 140, 255],
        "surprised_accent": [255, 220, 100],
    },
    "personality": {
        "blink_rate": 1.0,
        "shyness": 0.3,
        "playfulness": 0.5,
        "attention_drift": 0.5,
        "curiosity": 0.6,
        "surprise_reactivity": 0.7,
        "sleep_threshold_sec": 45.0,
    },
    "face_style": {"glow_intensity": 0.85},
    "behavior_weights": {
        "eye_tag": 0.35, "attentive": 0.20, "tongue": 0.15,
        "curious": 0.15, "chill": 0.15,
    },
}


def load_config(path):
    """Load config. Falls back to inline default if file missing or broken."""
    if not path or not os.path.exists(path):
        return dict(DEFAULT_CONFIG_INLINE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = dict(DEFAULT_CONFIG_INLINE)
        for k, v in cfg.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        return merged
    except Exception as e:
        print(f"[face-engine] config load failed: {e} — using inline default", flush=True)
        return dict(DEFAULT_CONFIG_INLINE)


# --- File IPC helpers ---
def read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_state_atomic(data):
    tmp = str(STATE_FILE) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, STATE_FILE)
    except OSError:
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass


# --- Engine ---
class FaceEngine:
    def __init__(self, config):
        self.cfg = config
        self.start_ms = time.time() * 1000.0

        self.mode = "idle"
        self.prev_mode = "idle"
        self.mode_entered_ms = self.start_ms

        self.look_x = 0
        self.look_y = 0
        self.saccade_x = 0
        self.saccade_y = 0

        self.blink_phase = 0          # 0 open, 1 closing, 2 closed, 3 opening
        self.blink_timer_ms = 0.0
        self.next_blink_ms = random.uniform(3000.0, 5000.0) / max(0.1, self._personality("blink_rate"))

        self.saccade_timer_ms = 0.0
        self.next_saccade_ms = random.uniform(500.0, 2000.0)

        self.gaze_timer_ms = 0.0
        self.next_gaze_ms = random.uniform(4000.0, 8000.0)
        self.gaze_target_x = 0
        self.gaze_target_y = 0

        self.last_people_count = 0
        self.last_person_seen_ms = 0.0
        self.last_eye_tag_ms = 0.0
        self.last_tongue_ms = 0.0
        self.last_curious_ms = 0.0

        self.breath_phase = 0.0
        self.listening_pulse_phase = 0.0
        self.thinking_spin_phase = 0.0

        self.voice_meta = None
        self.speak_started_ms = None
        self.active_word_end_ms = None

    # Small helpers -------------------------------------------------
    def _personality(self, key, default=0.5):
        return float(self.cfg.get("personality", {}).get(key, default))

    def _now_ms(self):
        return time.time() * 1000.0

    def _in_mode_ms(self, now_ms):
        return now_ms - self.mode_entered_ms

    def _set_mode(self, mode, now_ms):
        if mode != self.mode:
            self.prev_mode = self.mode
            self.mode = mode
            self.mode_entered_ms = now_ms

    # Blink / saccade / gaze ---------------------------------------
    def _tick_blink(self, dt_ms):
        self.blink_timer_ms += dt_ms
        if self.blink_phase == 0 and self.blink_timer_ms >= self.next_blink_ms:
            self.blink_phase = 1
            self.blink_timer_ms = 0.0
        elif self.blink_phase == 1 and self.blink_timer_ms >= 50.0:
            self.blink_phase = 2
            self.blink_timer_ms = 0.0
        elif self.blink_phase == 2 and self.blink_timer_ms >= 80.0:
            self.blink_phase = 3
            self.blink_timer_ms = 0.0
        elif self.blink_phase == 3 and self.blink_timer_ms >= 50.0:
            self.blink_phase = 0
            self.blink_timer_ms = 0.0
            rate = max(0.1, self._personality("blink_rate"))
            self.next_blink_ms = random.uniform(3000.0, 5000.0) / rate

    def _tick_saccade(self, dt_ms):
        self.saccade_timer_ms += dt_ms
        if self.saccade_timer_ms >= self.next_saccade_ms:
            self.saccade_x = random.choice([-1, 0, 1])
            self.saccade_y = random.choice([-1, 0, 0])
            self.saccade_timer_ms = 0.0
            self.next_saccade_ms = random.uniform(500.0, 2000.0)
        elif self.saccade_timer_ms >= 150.0:
            self.saccade_x = 0
            self.saccade_y = 0

    def _tick_idle_gaze(self, dt_ms):
        self.gaze_timer_ms += dt_ms
        drift = self._personality("attention_drift", 0.5)
        if self.gaze_timer_ms >= self.next_gaze_ms:
            spread = 1 + int(round(drift * 2))
            self.gaze_target_x = random.randint(-spread, spread)
            self.gaze_target_y = random.choice([-1, 0, 0, 1])
            self.gaze_timer_ms = 0.0
            self.next_gaze_ms = random.uniform(4000.0, 8000.0) * (1.5 - drift)

    # Input gathering -----------------------------------------------
    def _read_scene(self):
        scene = read_json(SCENE_FILE) or {}
        people = int(scene.get("people_count", 0) or 0)
        gaze = scene.get("gaze_target") or {}
        if isinstance(gaze, (list, tuple)) and len(gaze) >= 2:
            gx_raw, gy_raw = gaze[0], gaze[1]
        elif isinstance(gaze, dict):
            gx_raw, gy_raw = gaze.get("x", 0), gaze.get("y", 0)
        else:
            gx_raw, gy_raw = 0, 0
        gx = int(max(-3, min(3, gx_raw or 0)))
        gy = int(max(-2, min(2, gy_raw or 0)))
        novelty = bool(scene.get("novelty", False))
        return people, gx, gy, novelty

    def _is_listening(self):
        return os.path.exists(LISTENING_FLAG)

    def _is_speaking(self):
        return os.path.exists(MUTE_FLAG)

    def _read_voice_meta(self):
        if not self._is_speaking():
            self.voice_meta = None
            self.speak_started_ms = None
            self.active_word_end_ms = None
            return
        meta = read_json(VOICE_META)
        if meta and meta.get("words"):
            self.voice_meta = meta
            if self.speak_started_ms is None:
                self.speak_started_ms = meta.get("started_at_ms") or self._now_ms()

    # Mode selection ------------------------------------------------
    def _select_mode(self, now_ms, people, gx, gy, novelty):
        if self._is_speaking():
            return "speaking"
        if self._is_listening():
            return "listening"

        arrived = (people > 0) and (self.last_people_count == 0)
        if arrived:
            return "surprised"

        since_mode = self._in_mode_ms(now_ms)

        if self.mode == "surprised" and since_mode < 1500.0:
            return "surprised"
        if self.mode == "surprised" and people > 0:
            return "eye_tag"

        if people == 0:
            if self.mode == "speaking" or self.mode == "listening":
                return "thinking"
            sleep_thresh = self._personality("sleep_threshold_sec", 45.0) * 1000.0
            alone_for = now_ms - self.last_person_seen_ms if self.last_person_seen_ms else now_ms - self.start_ms
            if alone_for > sleep_thresh:
                return "sleep"
            return "idle"

        # People present -> pick a behavior by personality-weighted roll
        if self.mode in ("eye_tag", "attentive", "tongue", "curious", "chill") and since_mode < 4000.0:
            return self.mode

        weights = self.cfg.get("behavior_weights", DEFAULT_CONFIG_INLINE["behavior_weights"])
        play = self._personality("playfulness", 0.5)
        shy = self._personality("shyness", 0.3)
        cur = self._personality("curiosity", 0.6)

        bucket = {
            "eye_tag": weights.get("eye_tag", 0.35) * (0.7 + shy),
            "attentive": weights.get("attentive", 0.20) * (1.2 - shy),
            "tongue": weights.get("tongue", 0.15) * (0.4 + play),
            "curious": weights.get("curious", 0.15) * (0.5 + cur),
            "chill": weights.get("chill", 0.15),
        }
        # Respect cooldowns so the face doesn't spam the same trick
        if now_ms - self.last_eye_tag_ms < 15000.0:
            bucket["eye_tag"] *= 0.2
        if now_ms - self.last_tongue_ms < 60000.0:
            bucket["tongue"] *= 0.05
        if now_ms - self.last_curious_ms < 20000.0:
            bucket["curious"] *= 0.3

        total = sum(bucket.values()) or 1.0
        r = random.random() * total
        acc = 0.0
        for name, w in bucket.items():
            acc += w
            if r <= acc:
                return {"chill": "idle", "eye_tag": "eye_tag"}.get(name, name)
        return "idle"

    # Per-mode targets ---------------------------------------------
    def _mode_targets(self, mode, now_ms, gx, gy):
        """Return (eye_state, mouth, expression, glow, look_x, look_y, extras)."""
        extras = {}
        glow_base = float(self.cfg.get("face_style", {}).get("glow_intensity", 0.85))

        if mode == "sleep":
            return "closed", 0, "smile", glow_base * 0.35, 0, 0, extras

        if mode == "surprised":
            return "wide", 1, "neutral", min(1.0, glow_base * 1.3), gx, gy, extras

        if mode == "curious":
            return "squint", 0, "smile", glow_base * 0.9, gx // 2, gy, extras

        if mode == "tongue":
            return "open", 3, "smile", glow_base * 1.0, gx // 2, gy, extras

        if mode == "eye_tag":
            phase = self._in_mode_ms(now_ms)
            if phase < 400:   tx, ty = 0, 0
            elif phase < 1200: tx, ty = gx, gy
            elif phase < 2400: tx, ty = -gx if gx else random.choice([-3, 3]), 0
            elif phase < 4000: tx, ty = gx + random.choice([-1, 0, 1]), gy
            else:              tx, ty = 0, 0
            tx = max(-3, min(3, tx))
            ty = max(-2, min(2, ty))
            return "open", 0, "smile", glow_base, tx, ty, extras

        if mode == "attentive":
            return "open", 0, "smile", glow_base, gx, gy, extras

        if mode == "listening":
            # Widen eyes, gaze at last person direction, glow pulse
            self.listening_pulse_phase = (self.listening_pulse_phase + 0.15) % (math.pi * 2)
            pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self.listening_pulse_phase))
            tx = gx if gx else self.look_x
            ty = gy if gy else self.look_y
            extras["listening_intensity"] = pulse
            return "wide", 0, "neutral", min(1.0, glow_base * (0.9 + 0.3 * pulse)), tx, ty, extras

        if mode == "thinking":
            self.thinking_spin_phase = (self.thinking_spin_phase + 0.05) % (math.pi * 2)
            tx = -2 + int(round(math.sin(self.thinking_spin_phase * 0.7)))
            ty = -1
            return "half", 0, "neutral", glow_base * 0.8, tx, ty, extras

        if mode == "speaking":
            mouth, active_end = self._mouth_from_voice_meta(now_ms)
            extras["active_word_end_ms"] = active_end
            tx = self.look_x + (0 if random.random() < 0.7 else random.choice([-1, 0, 1]))
            ty = self.look_y
            tx = max(-3, min(3, tx))
            ty = max(-2, min(2, ty))
            return "open", mouth, "smile", glow_base * 1.05, tx, ty, extras

        # idle (default)
        return "open", 0, "smile", glow_base, self.gaze_target_x, self.gaze_target_y, extras

    def _mouth_from_voice_meta(self, now_ms):
        """Map current tick to a mouth-shape 0-3 using voice-meta word timings."""
        meta = self.voice_meta
        if not meta or not meta.get("words"):
            # Fallback: animate mouth with a random but bounded pattern
            phase = (now_ms / 90.0) % 4
            idx = int(phase)
            return max(0, min(3, idx)), None

        started = meta.get("started_at_ms") or self.speak_started_ms or now_ms
        elapsed = (now_ms - started) / 1000.0
        active_end = None
        in_word = False
        for w in meta["words"]:
            s = float(w.get("s", 0))
            e = float(w.get("e", 0))
            if s <= elapsed <= e:
                in_word = True
                active_end = int(started + e * 1000.0)
                break

        if not in_word:
            return 0, active_end

        # Vary shape within a word so it feels alive, not a strobe
        jitter = int((now_ms / 95.0) % 3)
        return [1, 2, 3][jitter], active_end

    # Main tick -----------------------------------------------------
    def tick(self, dt_ms):
        now_ms = self._now_ms()
        people, gx, gy, novelty = self._read_scene()
        if people > 0:
            self.last_person_seen_ms = now_ms

        self._read_voice_meta()
        new_mode = self._select_mode(now_ms, people, gx, gy, novelty)
        self._set_mode(new_mode, now_ms)

        # Mode-entry side effects
        if new_mode == "eye_tag" and self.mode_entered_ms == now_ms:
            self.last_eye_tag_ms = now_ms
        elif new_mode == "tongue" and self.mode_entered_ms == now_ms:
            self.last_tongue_ms = now_ms
        elif new_mode == "curious" and self.mode_entered_ms == now_ms:
            self.last_curious_ms = now_ms

        self._tick_blink(dt_ms)
        self._tick_saccade(dt_ms)
        if new_mode in ("idle",):
            self._tick_idle_gaze(dt_ms)

        eye_state, mouth, expression, glow, target_x, target_y, extras = \
            self._mode_targets(new_mode, now_ms, gx, gy)

        # Smoothly approach target (1 step per tick so it tweens)
        self.look_x += 1 if target_x > self.look_x else -1 if target_x < self.look_x else 0
        self.look_y += 1 if target_y > self.look_y else -1 if target_y < self.look_y else 0

        # Blink overrides eye_state visually
        if self.blink_phase == 2:
            eye_state_effective = "closed"
        elif self.blink_phase in (1, 3):
            eye_state_effective = "half"
        else:
            eye_state_effective = eye_state

        self.breath_phase += dt_ms * 0.0012
        breath = 0.85 + 0.15 * math.sin(self.breath_phase)

        state = {
            "schema_version": SCHEMA_VERSION,
            "agent_name": self.cfg.get("agent_name", "Axiom"),
            "agent_slug": self.cfg.get("agent_slug", "axiom"),
            "mode": new_mode,
            "prev_mode": self.prev_mode,
            "mode_age_ms": int(self._in_mode_ms(now_ms)),
            "mouth": int(mouth),
            "mouth_openness": float(mouth) / 3.0,
            "look_x": int(max(-3, min(3, self.look_x + self.saccade_x))),
            "look_y": int(max(-2, min(2, self.look_y + self.saccade_y))),
            "eye_state": eye_state_effective,
            "expression": expression,
            "glow": round(min(1.0, glow * breath), 3),
            "blink_phase": self.blink_phase,
            "listening_intensity": round(extras.get("listening_intensity", 0.0), 3),
            "active_word_end_ms": extras.get("active_word_end_ms"),
            "people_count": people,
            "scene_gaze": {"x": gx, "y": gy},
            "palette": self.cfg.get("palette", {}),
            "tick_ms": int(now_ms - self.start_ms),
        }
        write_state_atomic(state)

        self.last_people_count = people
        return state


def run_loop(config_path):
    cfg = load_config(config_path)
    engine = FaceEngine(cfg)
    print(f"[face-engine] agent={cfg.get('agent_name')} tick={int(TICK_SEC*1000)}ms", flush=True)
    print(f"[face-engine] state -> {STATE_FILE}", flush=True)

    last = time.time()
    try:
        while True:
            now = time.time()
            dt_ms = (now - last) * 1000.0
            last = now
            engine.tick(dt_ms)
            elapsed = time.time() - now
            sleep_for = max(0.0, TICK_SEC - elapsed)
            time.sleep(sleep_for)
    except KeyboardInterrupt:
        print("\n[face-engine] stopped", flush=True)


def run_mock():
    """Drive the engine with synthetic scene data to exercise every mode."""
    cfg = load_config(DEFAULT_CONFIG)
    engine = FaceEngine(cfg)
    script = [
        ("idle 3s", 3.0, lambda: _clear_all()),
        ("person arrives (surprised)", 2.0, lambda: _set_scene(1, 2, 0)),
        ("attentive 4s", 4.0, lambda: _set_scene(1, 2, 0)),
        ("listening 3s", 3.0, lambda: (_set_scene(1, 2, 0), _touch(LISTENING_FLAG))),
        ("thinking 2s", 2.0, lambda: (_remove(LISTENING_FLAG), _set_scene(0, 0, 0))),
        ("speaking 5s", 5.0, lambda: _start_speak_mock(5.0)),
        ("post-speak idle 2s", 2.0, lambda: (_remove(MUTE_FLAG), _remove(VOICE_META))),
        ("alone 50s (sleep)", 50.0, lambda: _set_scene(0, 0, 0)),
    ]
    last = time.time()
    for label, dur, setup in script:
        print(f"[mock] {label}", flush=True)
        setup()
        end = time.time() + dur
        while time.time() < end:
            now = time.time()
            dt_ms = (now - last) * 1000.0
            last = now
            state = engine.tick(dt_ms)
            time.sleep(TICK_SEC)
        last = time.time()
    _clear_all()
    print("[mock] done", flush=True)


# --- Mock helpers ---
def _set_scene(people, gx, gy):
    with open(SCENE_FILE, "w", encoding="utf-8") as f:
        json.dump({"people_count": people, "gaze_target": {"x": gx, "y": gy}}, f)


def _touch(p):
    with open(p, "w") as f:
        f.write("1")


def _remove(p):
    try:
        os.remove(p)
    except OSError:
        pass


def _start_speak_mock(duration_sec):
    _touch(MUTE_FLAG)
    # Build fake word timings across duration_sec
    words = []
    t = 0.0
    started = time.time() * 1000.0
    while t < duration_sec:
        s = t + random.uniform(0.05, 0.2)
        e = s + random.uniform(0.2, 0.45)
        if e > duration_sec:
            break
        words.append({"s": round(s, 3), "e": round(e, 3)})
        t = e + random.uniform(0.05, 0.15)
    with open(VOICE_META, "w", encoding="utf-8") as f:
        json.dump({"words": words, "started_at_ms": started, "est_end_ms": started + duration_sec * 1000}, f)


def _clear_all():
    for p in (SCENE_FILE, LISTENING_FLAG, MUTE_FLAG, VOICE_META):
        _remove(p)


def require_onboarded(config_path):
    """Refuse to start if the agent hasn't self-designed their face via
    onboard/designer.py. There is no default face — every agent chooses."""
    if not os.path.exists(config_path):
        print("[face-engine] config/face.json missing — no persona has been designed yet.", file=sys.stderr)
        print("[face-engine] Run the onboarding designer first:", file=sys.stderr)
        print("    python onboard/designer.py --name <Name> --slug <slug> --random", file=sys.stderr)
        print("  or for full control:", file=sys.stderr)
        print("    python onboard/designer.py --interactive", file=sys.stderr)
        sys.exit(2)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"[face-engine] config/face.json is unreadable ({e}). Re-run onboard/designer.py.", file=sys.stderr)
        sys.exit(2)
    if not cfg.get("onboarded"):
        print("[face-engine] config/face.json exists but onboarded != true.", file=sys.stderr)
        print("[face-engine] Re-run onboarding: python onboard/designer.py --interactive", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AXIOM Face Engine v2")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to face config json")
    parser.add_argument("--mock", action="store_true", help="Run scripted mock sequence then exit")
    parser.add_argument("--skip-onboard-check", action="store_true", help="Bypass the onboarding gate (tests only)")
    args = parser.parse_args()

    if not args.mock and not args.skip_onboard_check:
        require_onboarded(args.config)

    if args.mock:
        run_mock()
    else:
        run_loop(args.config)
