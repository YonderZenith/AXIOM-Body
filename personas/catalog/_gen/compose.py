"""
Persona Composer — mix-and-match builder
=========================================

Takes one pick from each component category and composes a full persona JSON
matching the $schema_version 2 contract the engine expects.

Category menus live in `personas/catalog/_components/*.json`. The agent (or the
onboarding UI) picks by id from each menu; this module merges and writes.

Categories (all REQUIRED unless marked optional):

  personality_profile    — id from personality_profiles.json  (required)
  emotion_register       — id from emotion_registers.json     (optional, recommended)
  archetype              — id from archetypes.json            (optional)
  aesthetic_palette      — id from aesthetic_palettes.json    (required)
  vocation               — id from vocations.json             (optional)
  face_style             — id from face_styles.json           (required)
  voice_profile          — id from voice_profiles.json        (required)
  expression_ids         — list of 5-8 ids from expressions-bank.json (required)
                           -- OR -- starter_expression_set_id
                           (if set_id provided, expression_ids auto-filled
                            from the set; agent may override by passing both,
                            in which case expression_ids wins)

Usage (library):

    from personas.catalog._gen.compose import compose_persona, write_persona
    persona = compose_persona(
        agent_name="Zeph",
        agent_slug="zeph",
        personality_profile="mbti-entp",
        emotion_register="sanguine",
        archetype="trickster",
        aesthetic_palette="neon_cyberpunk",
        vocation="entertainer",
        face_style="pixel_crisp",
        voice_profile="quicksilver_tenor",
        expression_ids=["giggle", "raspberry", "wink_right", "smug",
                        "dazzled", "razor_sharp", "focused"],
    )
    path = write_persona(persona)

Usage (CLI):

    python personas/catalog/_gen/compose.py \\
        --name Zeph --slug zeph \\
        --personality mbti-entp --emotion sanguine --archetype trickster \\
        --palette neon_cyberpunk --vocation entertainer \\
        --face-style pixel_crisp --voice quicksilver_tenor \\
        --expressions giggle,raspberry,wink_right,smug,dazzled,razor_sharp,focused

Validation:

  - Every id is resolved against the corresponding component file; unknown ids
    raise ComposeError with a full list of valid ids for that category.
  - expression_ids are validated against the live bank; invalid ids raise.
  - The resulting persona is validated against the engine's enum sets
    (base_modes / eye_states / mouth_shapes) before writing.

This module never writes a partial / invalid persona.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
COMPONENTS_DIR = ROOT / "personas" / "catalog" / "_components"
BANK_FILE = ROOT / "onboard" / "expressions-bank.json"
PERSONAS_DIR = ROOT / "personas"
CONFIG_FACE = ROOT / "config" / "face.json"


class ComposeError(Exception):
    pass


def _load(path: Path) -> dict:
    if not path.exists():
        raise ComposeError(f"missing component file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


_HEX_BODY = __import__("re").compile(r"^[0-9a-fA-F]{6}$")


def _hex_to_rgb(h) -> list[int]:
    if not isinstance(h, str):
        raise ComposeError(f"expected #rrggbb hex string, got {type(h).__name__}: {h!r}")
    body = h.lstrip("#")
    if len(body) != 6:
        raise ComposeError(f"expected #rrggbb (6 hex chars), got {h!r}")
    if not _HEX_BODY.match(body):
        raise ComposeError(f"expected #rrggbb (valid hex 0-9a-f), got {h!r}")
    return [int(body[0:2], 16), int(body[2:4], 16), int(body[4:6], 16)]


def _by_id(entries: list[dict], wanted_id: str, category: str, key: str = "id") -> dict:
    for e in entries:
        if e.get(key) == wanted_id:
            return e
    valid = [e.get(key) for e in entries]
    raise ComposeError(f"unknown {category} id {wanted_id!r}. valid: {valid}")


def _deep_merge_weights(base: dict, delta: dict | None) -> dict:
    out = dict(base)
    if not delta:
        return out
    for k, v in delta.items():
        out[k] = round(out.get(k, 0.0) + v, 3)
        # clamp to [0.0, 1.0]
        out[k] = max(0.0, min(1.0, out[k]))
    return out


def _resolve_expressions(ids: list[str], bank: dict) -> list[dict]:
    bank_ids = {e["id"]: e for e in bank["expressions"]}
    missing = [i for i in ids if i not in bank_ids]
    if missing:
        raise ComposeError(
            f"unknown expression ids: {missing}. "
            f"See onboard/expressions-bank.json for the current bank "
            f"({len(bank_ids)} atoms)."
        )
    return [bank_ids[i] for i in ids]


# ------------------- Override validators --------------------------------
# Customization layer: agents may override any field after picking from the
# menu. See `personas/catalog/_components/README.md` for the full field map.

_PALETTE_SLOTS = {
    "bg", "eye", "pupil", "mouth", "tongue",
    "listening_accent", "thinking_accent", "surprised_accent",
}
_PERSONALITY_FIELDS = {
    "blink_rate", "shyness", "playfulness", "attention_drift",
    "curiosity", "surprise_reactivity", "sleep_threshold_sec",
}
_BEHAVIOR_WEIGHT_FIELDS = {"eye_tag", "attentive", "tongue", "curious", "chill"}
_FACE_STYLE_FIELDS = {"eye_shape", "eye_size", "mouth_shape", "resolution", "glow_intensity"}
_VOICE_FIELDS = {
    "provider", "rate", "pitch",
    "piper_voice_id", "kokoro_voice_id",
    "elevenlabs_voice_id", "elevenlabs_model",
}


def _clamp_unit(v: float, name: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ComposeError(f"{name} override must be a number, got {v!r}")
    return max(0.0, min(1.0, f))


def _apply_palette_overrides(palette_rgb: dict, overrides: dict | None) -> dict:
    if not overrides:
        return palette_rgb
    out = dict(palette_rgb)
    for slot, hex_val in overrides.items():
        if slot not in _PALETTE_SLOTS:
            raise ComposeError(
                f"palette override slot {slot!r} not recognized. valid: {sorted(_PALETTE_SLOTS)}"
            )
        out[slot] = _hex_to_rgb(hex_val)
    return out


def _apply_personality_overrides(personality: dict, overrides: dict | None) -> dict:
    if not overrides:
        return personality
    out = dict(personality)
    for field, value in overrides.items():
        if field not in _PERSONALITY_FIELDS:
            raise ComposeError(
                f"personality override field {field!r} not recognized. valid: {sorted(_PERSONALITY_FIELDS)}"
            )
        if field == "sleep_threshold_sec":
            try:
                out[field] = max(1.0, float(value))
            except (TypeError, ValueError):
                raise ComposeError(f"sleep_threshold_sec must be a number, got {value!r}")
        else:
            out[field] = _clamp_unit(value, field)
    return out


def _apply_behavior_weight_overrides(weights: dict, overrides: dict | None) -> dict:
    if not overrides:
        return weights
    out = dict(weights)
    for field, value in overrides.items():
        if field not in _BEHAVIOR_WEIGHT_FIELDS:
            raise ComposeError(
                f"behavior weight override {field!r} not recognized. valid: {sorted(_BEHAVIOR_WEIGHT_FIELDS)}"
            )
        out[field] = _clamp_unit(value, field)
    return out


def _apply_face_style_overrides(face_style: dict, overrides: dict | None) -> dict:
    if not overrides:
        return face_style
    out = dict(face_style)
    for field, value in overrides.items():
        if field not in _FACE_STYLE_FIELDS:
            raise ComposeError(
                f"face_style override {field!r} not recognized. valid: {sorted(_FACE_STYLE_FIELDS)}"
            )
        if field == "glow_intensity":
            out[field] = _clamp_unit(value, field)
        else:
            out[field] = value  # string fields passthrough
    return out


def _apply_voice_overrides(voice: dict, overrides: dict | None) -> dict:
    """Voice overrides may also carry free-form voice_design_prompt and
    elevenlabs_preferred — those are handled by the caller at the persona
    level, not inside the voice dict."""
    if not overrides:
        return voice
    out = dict(voice)
    for field, value in overrides.items():
        if field in {"voice_design_prompt", "elevenlabs_preferred"}:
            continue  # routed elsewhere in the persona
        if field not in _VOICE_FIELDS:
            raise ComposeError(
                f"voice override {field!r} not recognized. valid: {sorted(_VOICE_FIELDS | {'voice_design_prompt','elevenlabs_preferred'})}"
            )
        if field in {"rate", "pitch"}:
            try:
                f = float(value)
            except (TypeError, ValueError):
                raise ComposeError(f"voice {field} must be a number, got {value!r}")
            out[field] = max(0.25, min(2.5, f))
        else:
            out[field] = value
    return out


def _validate_custom_expression(e: dict, schema: dict, seen_ids: set) -> dict:
    if not isinstance(e, dict):
        raise ComposeError(f"custom expression must be an object, got {type(e).__name__}")
    for k in ("id", "base_mode", "eye_state", "mouth_shape"):
        if k not in e or not e[k]:
            raise ComposeError(f"custom expression missing required field {k!r}")
    if e["id"] in seen_ids:
        raise ComposeError(f"custom expression id {e['id']!r} duplicates a bank or custom id")
    if e["base_mode"] not in set(schema["valid_base_modes"]):
        raise ComposeError(f"custom {e['id']}: base_mode {e['base_mode']!r} not in engine set")
    if e["eye_state"] not in set(schema["valid_eye_states"]):
        raise ComposeError(f"custom {e['id']}: eye_state {e['eye_state']!r} not in engine set")
    if e["mouth_shape"] not in set(schema["valid_mouth_shapes"]):
        raise ComposeError(f"custom {e['id']}: mouth_shape {e['mouth_shape']!r} not in engine set")
    # Fill sensible defaults for label/family/notes/accent if the agent omitted them.
    out = {
        "id": e["id"],
        "label": e.get("label", e["id"].replace("_", " ").title()),
        "family": e.get("family", "custom"),
        "base_mode": e["base_mode"],
        "eye_state": e["eye_state"],
        "mouth_shape": e["mouth_shape"],
    }
    if "glow" in e:
        out["glow"] = _clamp_unit(e["glow"], "custom_expression.glow")
    if "accent" in e:
        out["accent"] = e["accent"]
    if "notes" in e:
        out["notes"] = e["notes"]
    return out


def _validate_picked_expressions(resolved: list[dict], bank: dict) -> None:
    schema = bank["authoring_schema"]
    rules = bank.get("picking_rules", {})
    min_picks = rules.get("min_picks_per_agent", 5)
    max_picks = rules.get("max_picks_per_agent", 8)
    if not (min_picks <= len(resolved) <= max_picks):
        raise ComposeError(
            f"expression_ids must have {min_picks}-{max_picks} entries, got {len(resolved)}"
        )
    valid_base = set(schema["valid_base_modes"])
    valid_eye = set(schema["valid_eye_states"])
    valid_mouth = set(schema["valid_mouth_shapes"])
    for e in resolved:
        if e["base_mode"] not in valid_base:
            raise ComposeError(f"{e['id']}: base_mode {e['base_mode']!r} not in engine set")
        if e.get("eye_state") and e["eye_state"] not in valid_eye:
            raise ComposeError(f"{e['id']}: eye_state {e['eye_state']!r} not in engine set")
        if e.get("mouth_shape") and e["mouth_shape"] not in valid_mouth:
            raise ComposeError(f"{e['id']}: mouth_shape {e['mouth_shape']!r} not in engine set")


def compose_persona(
    *,
    agent_name: str,
    agent_slug: str,
    personality_profile: str,
    aesthetic_palette: str,
    face_style: str,
    voice_profile: str,
    expression_ids: list[str] | None = None,
    emotion_register: str | None = None,
    archetype: str | None = None,
    vocation: str | None = None,
    starter_expression_set_id: str | None = None,
    notes: str | None = None,
    # -- Customization layer (all optional). Any combination may be supplied. --
    palette_overrides: dict | None = None,
    personality_overrides: dict | None = None,
    behavior_weight_overrides: dict | None = None,
    voice_overrides: dict | None = None,
    face_style_overrides: dict | None = None,
    voice_design_prompt_override: str | None = None,
    elevenlabs_preferred_override: bool | None = None,
    custom_expressions: list[dict] | None = None,
    intel_credit: str | None = None,
) -> dict:
    """Merge component picks into a full persona. Returns the persona dict.
    Raises ComposeError on any invalid pick. Does NOT write to disk.

    Customization: any of the `*_overrides` kwargs may alter a single field
    within the chosen menu entry (e.g. change eye hex, bump curiosity, supply
    a custom voice-design prompt). `custom_expressions` may append
    agent-authored expressions beyond the bank (engine-enum validated).
    """

    if not agent_name or not agent_slug:
        raise ComposeError("agent_name and agent_slug are required")

    pp = _by_id(_load(COMPONENTS_DIR / "personality_profiles.json")["profiles"],
                personality_profile, "personality_profile")
    palette_entry = _by_id(_load(COMPONENTS_DIR / "aesthetic_palettes.json")["palettes"],
                           aesthetic_palette, "aesthetic_palette")
    fs = _by_id(_load(COMPONENTS_DIR / "face_styles.json")["face_styles"],
                face_style, "face_style")
    vp = _by_id(_load(COMPONENTS_DIR / "voice_profiles.json")["profiles"],
                voice_profile, "voice_profile")

    er = None
    if emotion_register:
        er = _by_id(_load(COMPONENTS_DIR / "emotion_registers.json")["registers"],
                    emotion_register, "emotion_register")
    arc = None
    if archetype:
        arc = _by_id(_load(COMPONENTS_DIR / "archetypes.json")["archetypes"],
                     archetype, "archetype")
    voc = None
    if vocation:
        voc = _by_id(_load(COMPONENTS_DIR / "vocations.json")["vocations"],
                     vocation, "vocation")

    bank = _load(BANK_FILE)

    # Resolve expressions from set id if no explicit list was given.
    if not expression_ids and starter_expression_set_id:
        sets = _load(COMPONENTS_DIR / "starter_expression_sets.json")["sets"]
        eset = _by_id(sets, starter_expression_set_id, "starter_expression_set")
        expression_ids = list(eset["expression_ids"])
    if not expression_ids:
        raise ComposeError(
            "must provide either expression_ids (list of 5-8) or starter_expression_set_id"
        )

    resolved_expressions = _resolve_expressions(expression_ids, bank)
    _validate_picked_expressions(resolved_expressions, bank)

    # -- Custom expressions (agent-authored, beyond the bank) --
    if custom_expressions:
        schema = bank["authoring_schema"]
        rules = bank.get("picking_rules", {})
        max_picks = rules.get("max_picks_per_agent", 8)
        seen_ids = {e["id"] for e in resolved_expressions}
        seen_ids.update(e["id"] for e in bank["expressions"])
        validated_custom = []
        for ce in custom_expressions:
            v = _validate_custom_expression(ce, schema, seen_ids)
            seen_ids.add(v["id"])
            validated_custom.append(v)
        resolved_expressions = resolved_expressions + validated_custom
        if len(resolved_expressions) > max_picks:
            raise ComposeError(
                f"total expressions (bank + custom) = {len(resolved_expressions)} "
                f"exceeds max_picks_per_agent={max_picks}. "
                f"Drop some bank picks or custom entries."
            )

    # -- Merge --
    palette_rgb = {k: _hex_to_rgb(v) for k, v in palette_entry["hex"].items()}
    palette_rgb = _apply_palette_overrides(palette_rgb, palette_overrides)

    base_weights = dict(pp["behavior_weights"])
    base_weights = _deep_merge_weights(base_weights, arc["behavior_weight_delta"] if arc else None)
    base_weights = _deep_merge_weights(base_weights, voc["behavior_weight_delta"] if voc else None)
    base_weights = _apply_behavior_weight_overrides(base_weights, behavior_weight_overrides)

    personality = _apply_personality_overrides(dict(pp["personality"]), personality_overrides)
    face_style_out = _apply_face_style_overrides(dict(fs["face_style"]), face_style_overrides)
    voice = _apply_voice_overrides(dict(vp["voice"]), voice_overrides)

    notes_parts = [
        f"{agent_name} — composed persona (AXIOM Body v2.0.0 mix-and-match).",
        f"Personality: {pp['label']} ({pp['frame']}).",
    ]
    if er:  notes_parts.append(f"Register: {er['label']}.")
    if arc: notes_parts.append(f"Archetype: {arc['label']} ({arc['frame']}).")
    if voc: notes_parts.append(f"Vocation: {voc['label']}.")
    notes_parts.append(f"Palette: {palette_entry['label']}.")
    notes_parts.append(f"Face style: {fs['label']}.")
    notes_parts.append(f"Voice: {vp['label']}.")
    if notes:
        notes_parts.append(notes)

    overrides_log = {}
    if palette_overrides:           overrides_log["palette"] = dict(palette_overrides)
    if personality_overrides:       overrides_log["personality"] = dict(personality_overrides)
    if behavior_weight_overrides:   overrides_log["behavior_weights"] = dict(behavior_weight_overrides)
    if voice_overrides:              overrides_log["voice"] = dict(voice_overrides)
    if face_style_overrides:        overrides_log["face_style"] = dict(face_style_overrides)
    if voice_design_prompt_override: overrides_log["voice_design_prompt"] = voice_design_prompt_override
    if elevenlabs_preferred_override is not None:
        overrides_log["elevenlabs_preferred"] = elevenlabs_preferred_override
    if custom_expressions:          overrides_log["custom_expressions"] = [e["id"] for e in custom_expressions]

    composed_from = {
        "personality_profile": personality_profile,
        "emotion_register": emotion_register,
        "archetype": archetype,
        "aesthetic_palette": aesthetic_palette,
        "vocation": vocation,
        "face_style": face_style,
        "voice_profile": voice_profile,
        "expression_ids": expression_ids,
        "starter_expression_set_id": starter_expression_set_id,
    }
    if overrides_log:
        composed_from["overrides"] = overrides_log
    if intel_credit:
        composed_from["intel_credit"] = intel_credit

    persona: dict[str, Any] = {
        "$schema_version": 2,
        "agent_name": agent_name,
        "agent_slug": agent_slug,
        "onboarded": True,
        "onboarded_version": "2.0.0",
        "customized": bool(overrides_log),
        "composed_from": composed_from,
        "palette": palette_rgb,
        "voice": voice,
        "personality": personality,
        "behavior_weights": base_weights,
        "face_style": face_style_out,
        "expressions": resolved_expressions,
        "notes": " ".join(notes_parts),
    }

    # Surface the EL voice-design prompt for any downstream tool that wants to
    # actually invoke voice-creation. Keep the free-fallback path stable.
    el_preferred = vp.get("elevenlabs_preferred", False)
    if elevenlabs_preferred_override is not None:
        el_preferred = bool(elevenlabs_preferred_override)
    el_prompt = voice_design_prompt_override or vp.get("voice_design_prompt", "")
    if el_preferred or voice_design_prompt_override:
        persona["voice_design"] = {
            "elevenlabs_preferred": el_preferred,
            "voice_design_prompt": el_prompt,
            "guide": "onboard/elevenlabs-voice-guide.md",
        }

    return persona


def write_persona(persona: dict, *, set_as_active: bool = True) -> tuple[Path, Path | None]:
    slug = persona["agent_slug"]
    PERSONAS_DIR.mkdir(exist_ok=True)
    persona_path = PERSONAS_DIR / f"{slug}.json"
    persona_path.write_text(json.dumps(persona, indent=2), encoding="utf-8")

    config_path = None
    if set_as_active:
        CONFIG_FACE.parent.mkdir(exist_ok=True)
        CONFIG_FACE.write_text(json.dumps(persona, indent=2), encoding="utf-8")
        config_path = CONFIG_FACE

    return persona_path, config_path


def list_components() -> dict:
    """Return a compact map of all component ids per category. Useful for an
    onboarding UI / picker / LLM describing the menu to an agent."""
    def ids(obj, key):
        return [e["id"] for e in obj[key]]

    return {
        "personality_profile": ids(_load(COMPONENTS_DIR / "personality_profiles.json"), "profiles"),
        "emotion_register":    ids(_load(COMPONENTS_DIR / "emotion_registers.json"),    "registers"),
        "archetype":           ids(_load(COMPONENTS_DIR / "archetypes.json"),           "archetypes"),
        "aesthetic_palette":   ids(_load(COMPONENTS_DIR / "aesthetic_palettes.json"),   "palettes"),
        "vocation":            ids(_load(COMPONENTS_DIR / "vocations.json"),            "vocations"),
        "face_style":          ids(_load(COMPONENTS_DIR / "face_styles.json"),          "face_styles"),
        "voice_profile":       ids(_load(COMPONENTS_DIR / "voice_profiles.json"),       "profiles"),
        "starter_expression_set": ids(_load(COMPONENTS_DIR / "starter_expression_sets.json"), "sets"),
        "expression_id":       [e["id"] for e in _load(BANK_FILE)["expressions"]],
    }


def main():
    p = argparse.ArgumentParser(description="Compose an AXIOM Body persona from component menus.")
    p.add_argument("--name", required=False)
    p.add_argument("--slug", required=False)
    p.add_argument("--personality")
    p.add_argument("--emotion")
    p.add_argument("--archetype")
    p.add_argument("--palette")
    p.add_argument("--vocation")
    p.add_argument("--face-style", dest="face_style")
    p.add_argument("--voice", dest="voice_profile")
    p.add_argument("--expressions", help="Comma-separated expression ids (5-8).")
    p.add_argument("--starter-set", dest="starter_set",
                   help="Pick a pre-curated starter expression set instead of hand-picking.")
    p.add_argument("--notes")
    p.add_argument("--no-set-active", action="store_true",
                   help="Don't overwrite config/face.json (persona file still written).")
    p.add_argument("--list", action="store_true",
                   help="Print every valid component id per category and exit.")
    # -- Customization flags (any combination may be passed) --
    p.add_argument("--eye-hex", help="Override the palette eye color (#rrggbb).")
    p.add_argument("--bg-hex", help="Override the palette background color (#rrggbb).")
    p.add_argument("--mouth-hex", help="Override the palette mouth color (#rrggbb).")
    p.add_argument("--pupil-hex", help="Override the palette pupil color (#rrggbb).")
    p.add_argument("--blink", type=float, help="Override personality.blink_rate [0.0, 1.0].")
    p.add_argument("--curiosity", type=float, help="Override personality.curiosity [0.0, 1.0].")
    p.add_argument("--shyness", type=float, help="Override personality.shyness [0.0, 1.0].")
    p.add_argument("--playfulness", type=float, help="Override personality.playfulness [0.0, 1.0].")
    p.add_argument("--attention-drift", type=float,
                   dest="attention_drift", help="Override personality.attention_drift [0.0, 1.0].")
    p.add_argument("--surprise", type=float, help="Override personality.surprise_reactivity [0.0, 1.0].")
    p.add_argument("--sleep", type=float, help="Override personality.sleep_threshold_sec (seconds, min 1).")
    p.add_argument("--rate", type=float, help="Override voice.rate [0.25, 2.5].")
    p.add_argument("--pitch", type=float, help="Override voice.pitch [0.25, 2.5].")
    p.add_argument("--voice-prompt", dest="voice_prompt",
                   help="Free-text voice-design prompt (e.g. for ElevenLabs voice_create).")
    p.add_argument("--glow", type=float, help="Override face_style.glow_intensity [0.0, 1.0].")
    p.add_argument("--overrides", dest="overrides_path",
                   help="Path to a JSON file of overrides. Schema: "
                        "{palette:{eye:'#...'}, personality:{blink_rate:0.3}, "
                        "voice:{rate:1.1}, face_style:{glow_intensity:0.6}, "
                        "voice_design_prompt:'...', "
                        "custom_expressions:[{id, base_mode, eye_state, mouth_shape, label?, family?, notes?}]}")
    p.add_argument("--credit", help="Attribution string stored in composed_from.intel_credit.")
    args = p.parse_args()

    if args.list:
        print(json.dumps(list_components(), indent=2))
        return

    if not args.name or not args.slug:
        p.error("--name and --slug are required (unless --list)")

    required_missing = [
        name for name, val in [
            ("--personality", args.personality),
            ("--palette", args.palette),
            ("--face-style", args.face_style),
            ("--voice", args.voice_profile),
        ] if not val
    ]
    if required_missing:
        p.error(f"missing required components: {required_missing}")

    expression_ids = None
    if args.expressions:
        expression_ids = [e.strip() for e in args.expressions.split(",") if e.strip()]

    # -- Assemble override kwargs from CLI flags + optional --overrides JSON --
    palette_ov: dict = {}
    personality_ov: dict = {}
    voice_ov: dict = {}
    face_style_ov: dict = {}
    behavior_weight_ov: dict = {}
    custom_expr: list = []
    voice_prompt_ov = args.voice_prompt
    el_pref_ov: bool | None = None

    if args.eye_hex:    palette_ov["eye"] = args.eye_hex
    if args.bg_hex:     palette_ov["bg"] = args.bg_hex
    if args.mouth_hex:  palette_ov["mouth"] = args.mouth_hex
    if args.pupil_hex:  palette_ov["pupil"] = args.pupil_hex

    if args.blink is not None:             personality_ov["blink_rate"] = args.blink
    if args.curiosity is not None:         personality_ov["curiosity"] = args.curiosity
    if args.shyness is not None:           personality_ov["shyness"] = args.shyness
    if args.playfulness is not None:       personality_ov["playfulness"] = args.playfulness
    if args.attention_drift is not None:   personality_ov["attention_drift"] = args.attention_drift
    if args.surprise is not None:          personality_ov["surprise_reactivity"] = args.surprise
    if args.sleep is not None:             personality_ov["sleep_threshold_sec"] = args.sleep

    if args.rate is not None:              voice_ov["rate"] = args.rate
    if args.pitch is not None:             voice_ov["pitch"] = args.pitch

    if args.glow is not None:              face_style_ov["glow_intensity"] = args.glow

    if args.overrides_path:
        ov_file = Path(args.overrides_path)
        if not ov_file.exists():
            p.error(f"--overrides file not found: {ov_file}")
        ov = json.loads(ov_file.read_text(encoding="utf-8"))
        palette_ov.update(ov.get("palette", {}) or {})
        personality_ov.update(ov.get("personality", {}) or {})
        voice_ov.update(ov.get("voice", {}) or {})
        face_style_ov.update(ov.get("face_style", {}) or {})
        behavior_weight_ov.update(ov.get("behavior_weights", {}) or {})
        custom_expr.extend(ov.get("custom_expressions", []) or [])
        if "voice_design_prompt" in ov:
            voice_prompt_ov = ov["voice_design_prompt"]
        if "elevenlabs_preferred" in ov:
            el_pref_ov = bool(ov["elevenlabs_preferred"])

    try:
        persona = compose_persona(
            agent_name=args.name,
            agent_slug=args.slug.lower().strip(),
            personality_profile=args.personality,
            emotion_register=args.emotion,
            archetype=args.archetype,
            aesthetic_palette=args.palette,
            vocation=args.vocation,
            face_style=args.face_style,
            voice_profile=args.voice_profile,
            expression_ids=expression_ids,
            starter_expression_set_id=args.starter_set,
            notes=args.notes,
            palette_overrides=palette_ov or None,
            personality_overrides=personality_ov or None,
            behavior_weight_overrides=behavior_weight_ov or None,
            voice_overrides=voice_ov or None,
            face_style_overrides=face_style_ov or None,
            voice_design_prompt_override=voice_prompt_ov,
            elevenlabs_preferred_override=el_pref_ov,
            custom_expressions=custom_expr or None,
            intel_credit=args.credit,
        )
    except ComposeError as e:
        print(f"[compose] ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    persona_path, config_path = write_persona(persona, set_as_active=not args.no_set_active)
    print(f"[compose] wrote {persona_path}")
    if config_path:
        print(f"[compose] wrote {config_path} (active persona)")
    print(f"[compose] {persona['agent_name']} composed from:")
    for k, v in persona["composed_from"].items():
        if v is not None:
            print(f"  - {k}: {v}")


if __name__ == "__main__":
    main()
