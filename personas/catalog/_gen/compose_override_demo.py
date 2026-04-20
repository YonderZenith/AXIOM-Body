"""
Reference demo: stacking every customization layer in one compose call.

Writes `personas/catalog/agent-override-demo.json` — a single persona that
exercises palette hex overrides, personality float overrides, behavior-weight
overrides, voice rate/pitch overrides, face-style glow override, a free-text
voice-design prompt override, and an agent-authored custom expression beyond
the 99-atom bank. This is the canonical example to show new agents that
"pick from the menu, then customize anything" works end-to-end.

Run:
    python personas/catalog/_gen/compose_override_demo.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose import compose_persona, ComposeError  # noqa: E402

CATALOG_DIR = Path(__file__).resolve().parents[1]


def main():
    persona = compose_persona(
        agent_name="Override Demo",
        agent_slug="override-demo",
        personality_profile="mbti-intp",
        emotion_register="lantern",
        archetype="sage",
        aesthetic_palette="cyan_warmth",
        vocation="scholar",
        face_style="classic_round",
        voice_profile="radiant_mezzo",
        starter_expression_set_id="the_scholar",
        # -- Customization layer: any single field in any category can be changed.
        palette_overrides={
            "eye": "#7cf5ff",       # cooler cyan than the default
            "bg": "#060a14",        # deeper midnight
            "thinking_accent": "#a98bff",
        },
        personality_overrides={
            "blink_rate": 0.45,
            "curiosity": 0.92,
            "shyness": 0.15,
            "sleep_threshold_sec": 180.0,
        },
        behavior_weight_overrides={
            "curious": 0.85,
            "chill": 0.35,
        },
        voice_overrides={"rate": 1.05, "pitch": 0.98},
        face_style_overrides={"glow_intensity": 0.7},
        voice_design_prompt_override=(
            "A thoughtful mezzo voice with warm curiosity, unhurried cadence, "
            "and micro-pauses before key words. Low sibilance; natural breaths."
        ),
        elevenlabs_preferred_override=True,
        custom_expressions=[{
            "id": "demo_thoughtful_gleam",
            "label": "Thoughtful Gleam",
            "family": "custom",
            "base_mode": "thinking",
            "eye_state": "half",
            "mouth_shape": "soft_small",
            "glow": 0.8,
            "notes": (
                "Agent-authored: eyes soften while the mind chases an insight. "
                "Use when you're about to say something you've just realized."
            ),
        }],
        notes=(
            "Reference demo for the AXIOM Body v2.0.0 customization layer. "
            "Shows every override knob firing at once; the engine still accepts it."
        ),
        intel_credit="Override layer demo — 2026-04-21",
    )

    out_path = CATALOG_DIR / "agent-override-demo.json"
    out_path.write_text(json.dumps(persona, indent=2), encoding="utf-8")
    print(f"[override-demo] wrote {out_path}")
    print(f"[override-demo] customized={persona['customized']}")
    print(f"[override-demo] overrides applied:")
    for k in persona["composed_from"].get("overrides", {}):
        print(f"  - {k}")


if __name__ == "__main__":
    try:
        main()
    except ComposeError as e:
        print(f"[override-demo] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
