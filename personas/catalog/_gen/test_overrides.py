"""
Smoke test for the persona customization layer.

Exercises every override kwarg on `compose_persona()`, verifies the resulting
persona reflects the override, and confirms validators reject out-of-range /
unknown-field input with a clean ComposeError.

Run:
    python personas/catalog/_gen/test_overrides.py
"""
from __future__ import annotations
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose import compose_persona, ComposeError  # noqa: E402


BASE_PICKS = dict(
    agent_name="OverrideDemo",
    agent_slug="override-demo",
    personality_profile="mbti-intp",
    aesthetic_palette="cyan_warmth",
    face_style="classic_round",
    voice_profile="radiant_mezzo",
    starter_expression_set_id="the_scholar",
)


def _assert(cond, msg: str = "assertion failed"):
    if not cond:
        raise AssertionError(msg)


def test_baseline_no_overrides():
    p = compose_persona(**BASE_PICKS)
    _assert(p["customized"] is False, "baseline should not be marked customized")
    _assert("overrides" not in p["composed_from"], "baseline should have no overrides log")
    print("  OK baseline_no_overrides")


def test_palette_override():
    p = compose_persona(**BASE_PICKS, palette_overrides={"eye": "#ff00ff", "bg": "#101020"})
    _assert(p["palette"]["eye"] == [255, 0, 255], f"eye override failed: {p['palette']['eye']}")
    _assert(p["palette"]["bg"] == [16, 16, 32], f"bg override failed: {p['palette']['bg']}")
    _assert(p["customized"] is True, "expected customized=True")
    _assert(p["composed_from"]["overrides"]["palette"] == {"eye": "#ff00ff", "bg": "#101020"})
    print("  OK palette_override")


def test_personality_override():
    p = compose_persona(**BASE_PICKS,
                        personality_overrides={"blink_rate": 0.9, "curiosity": 0.1, "sleep_threshold_sec": 12.5})
    _assert(p["personality"]["blink_rate"] == 0.9)
    _assert(p["personality"]["curiosity"] == 0.1)
    _assert(p["personality"]["sleep_threshold_sec"] == 12.5)
    print("  OK personality_override")


def test_personality_override_clamps():
    p = compose_persona(**BASE_PICKS, personality_overrides={"blink_rate": 5.0, "shyness": -0.3})
    _assert(p["personality"]["blink_rate"] == 1.0, "should clamp to 1.0")
    _assert(p["personality"]["shyness"] == 0.0, "should clamp to 0.0")
    print("  OK personality_override_clamps")


def test_voice_override():
    p = compose_persona(**BASE_PICKS, voice_overrides={"rate": 1.3, "pitch": 0.8})
    _assert(p["voice"]["rate"] == 1.3)
    _assert(p["voice"]["pitch"] == 0.8)
    print("  OK voice_override")


def test_voice_override_clamps():
    p = compose_persona(**BASE_PICKS, voice_overrides={"rate": 99.0, "pitch": 0.01})
    _assert(p["voice"]["rate"] == 2.5, "rate should clamp to 2.5")
    _assert(p["voice"]["pitch"] == 0.25, "pitch should clamp to 0.25")
    print("  OK voice_override_clamps")


def test_face_style_override():
    p = compose_persona(**BASE_PICKS, face_style_overrides={"glow_intensity": 0.95})
    _assert(p["face_style"]["glow_intensity"] == 0.95)
    print("  OK face_style_override")


def test_voice_design_prompt_override():
    p = compose_persona(**BASE_PICKS,
                        voice_design_prompt_override="A low, gravelly voice like a night-shift radio host.")
    _assert(p["voice_design"]["voice_design_prompt"].startswith("A low"))
    print("  OK voice_design_prompt_override")


def test_behavior_weight_override():
    p = compose_persona(**BASE_PICKS,
                        behavior_weight_overrides={"curious": 0.95, "chill": 0.05})
    _assert(p["behavior_weights"]["curious"] == 0.95)
    _assert(p["behavior_weights"]["chill"] == 0.05)
    print("  OK behavior_weight_override")


def test_custom_expression():
    # Author a brand-new expression the bank doesn't have.
    custom = [{
        "id": "demo_smirk_plus",
        "label": "Demo Smirk Plus",
        "family": "custom",
        "base_mode": "thinking",
        "eye_state": "squint",
        "mouth_shape": "asymmetric_smile",
        "notes": "Demo of an agent-authored expression beyond the 99-atom bank.",
    }]
    p = compose_persona(**BASE_PICKS, custom_expressions=custom)
    ids = [e["id"] for e in p["expressions"]]
    _assert("demo_smirk_plus" in ids, f"custom expression not appended: {ids}")
    _assert(p["composed_from"]["overrides"]["custom_expressions"] == ["demo_smirk_plus"])
    print("  OK custom_expression")


def test_custom_expression_rejects_bad_enum():
    try:
        compose_persona(**BASE_PICKS, custom_expressions=[{
            "id": "bad_one",
            "base_mode": "not_a_real_mode",
            "eye_state": "squint",
            "mouth_shape": "asymmetric_smile",
        }])
    except ComposeError as e:
        _assert("not in engine set" in str(e), f"wrong error: {e}")
        print("  OK custom_expression_rejects_bad_enum")
        return
    raise AssertionError("expected ComposeError for bad base_mode")


def test_custom_expression_rejects_dup_id():
    # 'focused' is in the bank already
    try:
        compose_persona(**BASE_PICKS, custom_expressions=[{
            "id": "focused",
            "base_mode": "thinking",
            "eye_state": "open",
            "mouth_shape": "soft_small",
        }])
    except ComposeError as e:
        _assert("duplicates" in str(e), f"wrong error: {e}")
        print("  OK custom_expression_rejects_dup_id")
        return
    raise AssertionError("expected ComposeError for duplicate id")


def test_palette_rejects_bad_hex():
    for bad in ["#GGGGGG", "#12345", "#1234567", "not-a-hex", "#zzzzzz"]:
        try:
            compose_persona(**BASE_PICKS, palette_overrides={"eye": bad})
        except ComposeError as e:
            _assert("#rrggbb" in str(e) or "hex" in str(e), f"bad msg for {bad!r}: {e}")
            continue
        raise AssertionError(f"expected ComposeError for palette eye={bad!r}")
    print("  OK palette_rejects_bad_hex")


def test_palette_rejects_non_string():
    for bad in [12345, None, ["#ff00ff"], b"#ff00ff"]:
        try:
            compose_persona(**BASE_PICKS, palette_overrides={"eye": bad})
        except ComposeError as e:
            _assert("hex string" in str(e) or "#rrggbb" in str(e),
                    f"bad msg for {bad!r}: {e}")
            continue
        raise AssertionError(f"expected ComposeError for palette eye={bad!r}")
    print("  OK palette_rejects_non_string")


def test_unknown_override_field_rejected():
    try:
        compose_persona(**BASE_PICKS, personality_overrides={"not_a_field": 0.5})
    except ComposeError as e:
        _assert("not recognized" in str(e), f"wrong error: {e}")
        print("  OK unknown_override_field_rejected")
        return
    raise AssertionError("expected ComposeError for unknown field")


def test_stacked_all_overrides():
    """The money shot: every override type at once — the 'unlimited' demo."""
    p = compose_persona(
        **BASE_PICKS,
        palette_overrides={"eye": "#00ffd5", "bg": "#05101a", "mouth": "#ff3377"},
        personality_overrides={"blink_rate": 0.7, "curiosity": 0.95, "shyness": 0.2},
        behavior_weight_overrides={"curious": 0.9, "chill": 0.3},
        voice_overrides={"rate": 1.1, "pitch": 0.92},
        face_style_overrides={"glow_intensity": 0.75},
        voice_design_prompt_override="A crisp, confident tenor with warmth at the edges.",
        elevenlabs_preferred_override=True,
        custom_expressions=[{
            "id": "demo_dazzled_plus",
            "label": "Demo Dazzled Plus",
            "family": "custom",
            "base_mode": "surprised",
            "eye_state": "wide",
            "mouth_shape": "big_o",
            "glow": 0.9,
            "notes": "Stacked-overrides demo.",
        }],
        intel_credit="Stacked override demo — 2026-04-21",
    )
    _assert(p["customized"] is True)
    log = p["composed_from"]["overrides"]
    for k in ["palette", "personality", "behavior_weights", "voice", "face_style",
              "voice_design_prompt", "elevenlabs_preferred", "custom_expressions"]:
        _assert(k in log, f"overrides log missing {k}")
    _assert(p["voice_design"]["elevenlabs_preferred"] is True)
    _assert(p["voice_design"]["voice_design_prompt"].startswith("A crisp"))
    print("  OK stacked_all_overrides")


TESTS = [
    test_baseline_no_overrides,
    test_palette_override,
    test_personality_override,
    test_personality_override_clamps,
    test_voice_override,
    test_voice_override_clamps,
    test_face_style_override,
    test_voice_design_prompt_override,
    test_behavior_weight_override,
    test_custom_expression,
    test_custom_expression_rejects_bad_enum,
    test_custom_expression_rejects_dup_id,
    test_palette_rejects_bad_hex,
    test_palette_rejects_non_string,
    test_unknown_override_field_rejected,
    test_stacked_all_overrides,
]


def main():
    print("=" * 64)
    print("AXIOM Body persona override smoke test")
    print("=" * 64)
    failed = 0
    for fn in TESTS:
        try:
            fn()
        except Exception as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
            traceback.print_exc()
    print("-" * 64)
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed.")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
