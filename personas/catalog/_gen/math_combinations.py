"""
Rigorous combinatorics for AXIOM Body persona composition.

Computes:
  1. Menu-only combinations (agent picks from the bank, no overrides).
  2. Semi-custom combinations (agent overrides color hex values).
  3. Fully-custom combinations (free personality floats, free voice prompts,
     free custom-authored expressions).

The menu-only number is an honest, factually-checkable claim.
The semi-custom number is still a discrete count (finite).
The fully-custom space is continuous in several dimensions, so its
cardinality is formally c (continuum) or effectively unbounded once
natural-language voice-design prompts and agent-authored expressions
enter the picture.

This module is imported by the docs build (if any) and can be run
stand-alone:

    python personas/catalog/_gen/math_combinations.py

Sources for combinatorics frame:
  - Feller, "An Introduction to Probability Theory and Its Applications" (Vol. I, ch. 2).
  - Knuth, "Concrete Mathematics" (ch. 5 -- Binomial Coefficients).
  - Stanley, "Enumerative Combinatorics" (Vol. 1, ch. 1).
"""
from __future__ import annotations
import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENTS = ROOT / "personas" / "catalog" / "_components"
BANK = ROOT / "onboard" / "expressions-bank.json"


def load_counts() -> dict:
    def n(path, key):
        return len(json.loads(path.read_text(encoding="utf-8"))[key])
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    schema = bank["authoring_schema"]
    rules = bank["picking_rules"]
    return {
        "personality_profiles":  n(COMPONENTS / "personality_profiles.json", "profiles"),
        "emotion_registers":     n(COMPONENTS / "emotion_registers.json",    "registers"),
        "archetypes":            n(COMPONENTS / "archetypes.json",           "archetypes"),
        "aesthetic_palettes":    n(COMPONENTS / "aesthetic_palettes.json",   "palettes"),
        "vocations":             n(COMPONENTS / "vocations.json",            "vocations"),
        "face_styles":           n(COMPONENTS / "face_styles.json",          "face_styles"),
        "voice_profiles":        n(COMPONENTS / "voice_profiles.json",       "profiles"),
        "expression_atoms":      len(bank["expressions"]),
        "base_modes":            len(schema["valid_base_modes"]),
        "eye_states":            len(schema["valid_eye_states"]),
        "mouth_shapes":          len(schema["valid_mouth_shapes"]),
        "min_expression_picks":  rules["min_picks_per_agent"],
        "max_expression_picks":  rules["max_picks_per_agent"],
    }


def menu_only_combinations(c: dict) -> int:
    """Agent picks one entry from each required category and 5-8 expressions
    from the bank. Optional categories (emotion_register, archetype, vocation)
    each get a '+1' for the None choice so the count reflects real branches.
    Expressions are unordered sets (no positional semantics in the persona)."""
    expr = sum(
        comb(c["expression_atoms"], k)
        for k in range(c["min_expression_picks"], c["max_expression_picks"] + 1)
    )
    required = (
        c["personality_profiles"]
        * c["aesthetic_palettes"]
        * c["face_styles"]
        * c["voice_profiles"]
        * expr
    )
    optional = (
        (c["emotion_registers"] + 1)  # +1 for "skip this category"
        * (c["archetypes"] + 1)
        * (c["vocations"] + 1)
    )
    return required * optional


def palette_override_variations() -> int:
    """Each of the 8 palette slots can be any of 2**24 RGB values."""
    return (2 ** 24) ** 8  # = 2**192


def personality_float_variations(resolution_per_float: int = 101) -> int:
    """Seven personality floats in [0.0, 1.0]. At 0.01 resolution that's 101 values each.
    At float32 precision it's ~2**32 per float -- effectively R^7."""
    return resolution_per_float ** 7


def behavior_weight_variations(resolution_per_weight: int = 101) -> int:
    """Five behavior weights in [0.0, 1.0]."""
    return resolution_per_weight ** 5


def custom_expression_atoms(c: dict) -> int:
    """Distinct (base_mode, eye_state, mouth_shape) tuples the engine accepts,
    before considering accent/glow/label/notes fields."""
    return c["base_modes"] * c["eye_states"] * c["mouth_shapes"]


def print_report():
    c = load_counts()
    menu = menu_only_combinations(c)
    pal = palette_override_variations()
    pers = personality_float_variations()
    bw = behavior_weight_variations()
    atom = custom_expression_atoms(c)

    print("=" * 72)
    print("AXIOM BODY -- PERSONA COMBINATION MATH (rigorous)")
    print("=" * 72)
    print()
    print("Component menus (as of", __import__("datetime").date.today().isoformat(), "):")
    for k, v in c.items():
        print(f"  {k:28s} {v:>6}")
    print()
    print("-- MENU-ONLY (no customization, pick from existing menus) --")
    print()
    print("Formula:")
    print("  required = personality x palette x face_style x voice x Sum C(99,k) for k=5..8")
    print("  optional = (emotion+1) x (archetype+1) x (vocation+1)")
    print("  total    = required x optional")
    print()
    expr = sum(comb(c["expression_atoms"], k) for k in range(5, 9))
    print(f"  Sum C({c['expression_atoms']},k) for k=5..8 = {expr:,}  ({expr:.3e})")
    print(f"  required                          = {c['personality_profiles']} x {c['aesthetic_palettes']} x {c['face_styles']} x {c['voice_profiles']} x {expr:,}")
    print(f"                                    = {c['personality_profiles']*c['aesthetic_palettes']*c['face_styles']*c['voice_profiles']*expr:,}")
    print(f"  optional                          = {c['emotion_registers']+1} x {c['archetypes']+1} x {c['vocations']+1} = {(c['emotion_registers']+1)*(c['archetypes']+1)*(c['vocations']+1):,}")
    print(f"  menu-only total                   = {menu:,}  (~= {menu:.3e})")
    print()
    print("Scale check:")
    print(f"  Grains of sand on all Earth's beaches  ~= 7.5 x 10^18")
    print(f"  AXIOM Body menu-only combinations       ~= {menu:.3e}")
    print(f"  Stars in the observable universe        ~= 1 x 10^22")
    print(f"  Atoms in a human body                   ~= 7 x 10^27")
    print()
    print("-- WITH CUSTOMIZATION (agent overrides fields) --")
    print()
    print(f"  Palette overrides (8 x 2^24 RGB slots)  = 2^192 ~= {pal:.3e}")
    print(f"  Personality floats (7 x 101 buckets)    = 101^7 ~= {pers:.3e}")
    print(f"  Behavior weights (5 x 101 buckets)      = 101^5 ~= {bw:.3e}")
    print(f"  Custom expression atoms (basexeyexmouth) = {c['base_modes']} x {c['eye_states']} x {c['mouth_shapes']} = {atom}")
    print(f"  Voice rate + pitch                      = R x R   (continuous)")
    print(f"  Voice design prompt (free text)         = aleph-0   (countably infinite token strings)")
    print(f"  Custom expression labels + notes        = aleph-0   (free text)")
    print()
    print("Compounding (discrete layers only):")
    combined = menu * pal * pers * bw
    print(f"  menu-only x palette x personality x behavior-weights")
    print(f"  ~= {menu:.2e} x {pal:.2e} x {pers:.2e} x {bw:.2e}")
    print(f"  ~= {combined:.3e}")
    print()
    print("Continuous + natural-language layers bring the effective space")
    print("to the cardinality of the continuum. Marketing claim 'unlimited'")
    print("is literally defensible -- any finite catalogue would be surpassed.")
    print()
    print("Headline numbers for docs:")
    print(f"  - menu-only:     {menu:.2e}  (\"more than grains of sand on Earth\")")
    print(f"  - with RGB only: {menu * pal:.2e}  (palette overrides alone)")
    print(f"  - full custom:   unlimited (continuous + free-text dimensions)")
    print("=" * 72)


if __name__ == "__main__":
    print_report()
