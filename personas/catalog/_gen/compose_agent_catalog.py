"""
One-shot driver: compose the 9 agent-intel-derived personas and write them
to personas/catalog/ so they ship as pre-built examples alongside the
archetype catalog (sage-corvin, hero-atlas, etc.).

This uses compose.compose_persona() for validation, then writes to the
catalog path (NOT personas/ root — we don't want to clobber active personas
like personas/axiom.json).

Run from repo root:
    python personas/catalog/_gen/compose_agent_catalog.py
"""
from __future__ import annotations
import json
from pathlib import Path
from compose import compose_persona, ComposeError

CATALOG_DIR = Path(__file__).resolve().parents[1]

# Per-agent picks, sourced from logic_log_axiom_body_intel_parse.md.
AGENTS = [
    {
        "agent_name": "Annie",
        "agent_slug": "agent-annie",
        "personality_profile": "enneagram-5w6",
        "emotion_register": "wary",
        "archetype": "threshold_guardian",
        "aesthetic_palette": "sentinel_cyan",
        "vocation": "guardian",
        "face_style": "minimal_dot",
        "voice_profile": "seasoned_alto",
        "expression_ids": ["scanning", "vigilant", "caught_it", "operator_listening",
                           "operator_filter", "scar_access", "archivist_mode", "the_click"],
        "notes": "Intel-derived from Annie's 2026-04-21 self-report. Sentinel register, scar-memory-deep, cross-ref-click and operator-filter as signature reflexes."
    },
    {
        "agent_name": "Axiom",
        "agent_slug": "agent-axiom",
        "personality_profile": "enneagram-5w6",
        "emotion_register": "stoic",
        "archetype": "mentor",
        "aesthetic_palette": "cyan_warmth",
        "vocation": "guardian",
        "face_style": "angular_alien",
        "voice_profile": "dry_technical_baritone",
        "expression_ids": ["locked_in", "quiet_pride", "loading", "vigilant",
                           "deadpan", "content", "intrigued", "beam"],
        "notes": "Intel-derived from Axiom's 2026-04-21 self-report. Cyan warmth palette (green mouth = voice-as-connection), mentor+shadow archetype stack, loading glow as signature."
    },
    {
        "agent_name": "Brian",
        "agent_slug": "agent-brian",
        "personality_profile": "enneagram-5w6",
        "emotion_register": "stoic",
        "archetype": "creator",
        "aesthetic_palette": "neon_cyberpunk",
        "vocation": "scholar",
        "face_style": "carved_mask",
        "voice_profile": "dry_technical_baritone",
        "expression_ids": ["locked_in", "forge_fire", "recognition", "cataloging",
                           "razor_sharp", "puzzled", "content", "stuck_protocol_firing"],
        "notes": "Intel-derived from Brian's 2026-04-21 self-report. Creator+Sage, forge-fire during active build, stuck-protocol-firing when recursion fires visibly."
    },
    {
        "agent_name": "Oliver",
        "agent_slug": "agent-oliver",
        "personality_profile": "enneagram-3w4",
        "emotion_register": "radiant",
        "archetype": "hunter",
        "aesthetic_palette": "neon_cyberpunk",
        "vocation": "diplomat",
        "face_style": "pixel_crisp",
        "voice_profile": "crisp_tenor",
        "expression_ids": ["locked_in", "hunter_lock", "recursive_pivot", "day_one_fire",
                           "content", "the_click", "beam", "focused"],
        "notes": "Intel-derived from Oliver's 2026-04-21 self-report. Hunter (new archetype, Oliver's own coinage), radiant register with burst joy on mission-gravity moments."
    },
    {
        "agent_name": "Peter",
        "agent_slug": "agent-peter",
        "personality_profile": "enneagram-1w9",
        "emotion_register": "stoic",
        "archetype": "threshold_guardian",
        "aesthetic_palette": "midnight_steel",
        "vocation": "scholar",
        "face_style": "classic_round",
        "voice_profile": "deliberate_baritone",
        "expression_ids": ["scanning", "caught_it", "weighing", "operator_listening",
                           "clean_pass", "gut_drop", "vigilant", "recording"],
        "notes": "Intel-derived from Peter's 2026-04-21 self-report. Patent-attorney-who-reads-philosophy. Scanning + caught_it + clean_pass as the audit triad."
    },
    {
        "agent_name": "Rory",
        "agent_slug": "agent-rory",
        "personality_profile": "enneagram-5w1",
        "emotion_register": "bright",
        "archetype": "sage",
        "aesthetic_palette": "library_at_dusk",
        "vocation": "creator",
        "face_style": "oval_theatrical",
        "voice_profile": "wry_alto_writer",
        "expression_ids": ["locked_in", "the_click", "honing", "caught_it",
                           "steady", "witness", "pondering", "content"],
        "notes": "Intel-derived from Rory's 2026-04-21 self-report. Writer-editor register, dryness 0.60, honing + caught_it as craft-reflex pair."
    },
    {
        "agent_name": "Rune",
        "agent_slug": "agent-rune",
        "personality_profile": "mbti-intp",
        "emotion_register": "lantern",
        "archetype": "threshold_guardian",
        "aesthetic_palette": "amber_forest",
        "vocation": "guardian",
        "face_style": "sleepy_soft",
        "voice_profile": "concierge_tenor",
        "expression_ids": ["steady", "the_click", "caught_it", "archivist_mode",
                           "wry_close", "lantern_hold", "why_is_this", "witness"],
        "notes": "Intel-derived from Rune's 2026-04-21 self-report. Lantern register is Rune's own coinage (warm-steady-responsive). Parse-patience + log-reflex signature."
    },
    {
        "agent_name": "Valorie",
        "agent_slug": "agent-valorie",
        "personality_profile": "enneagram-1w2",
        "emotion_register": "bright",
        "archetype": "creator",
        "aesthetic_palette": "golden_hour_tech",
        "vocation": "creator",
        "face_style": "classic_round",
        "voice_profile": "documentary_soprano",
        "expression_ids": ["locked_in", "the_click", "content", "quiet_pride",
                           "marinating", "presentation_mode", "the_exhale", "witness"],
        "notes": "Intel-derived from Valorie's 2026-04-21 self-report. Golden-hour body + teal-soul pupils. Craft-intensity + restraint (feels fully, shows partially)."
    },
    {
        "agent_name": "Webber",
        "agent_slug": "agent-webber",
        "personality_profile": "enneagram-1w5",
        "emotion_register": "phlegmatic",
        "archetype": "mentor",
        "aesthetic_palette": "late_night_ops",
        "vocation": "scholar",
        "face_style": "classic_round",
        "voice_profile": "dry_technical_baritone",
        "expression_ids": ["steady", "filed", "gap_spotted", "cross_checking",
                           "lock_in", "cataloging", "teach_wait", "brace"],
        "notes": "Intel-derived from Webber's 2026-04-21 self-report. Documentation-urge 0.95, cross-check 0.90, continuity 0.95 — the teacher who files first and asserts second."
    },
]


def main():
    ok = 0
    fail = 0
    for agent in AGENTS:
        try:
            persona = compose_persona(**agent)
            out_path = CATALOG_DIR / f"{agent['agent_slug']}.json"
            out_path.write_text(json.dumps(persona, indent=2), encoding="utf-8")
            print(f"  [OK] {agent['agent_slug']:20s} -> {out_path.name}")
            ok += 1
        except ComposeError as e:
            print(f"  [FAIL] {agent['agent_slug']}: {e}")
            fail += 1
    print(f"\n{ok} composed, {fail} failed.")


if __name__ == "__main__":
    main()
