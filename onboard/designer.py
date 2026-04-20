"""
AXIOM-Body Agent Onboarding Designer
=====================================
Every agent that boots AXIOM-Body runs through this BEFORE the engine starts.
There is no default face. Every agent designs their own.

The agent calls this with their own choices (it's not a human-interactive CLI
— agents drive it programmatically). For humans testing, pass --interactive
to get prompts.

Outputs:
  personas/<slug>.json   — full persona (palette, voice, personality, expressions)
  config/face.json       — points at the active persona (copy of the above, marked onboarded:true)

Usage (programmatic — the common path):
  python onboard/designer.py \\
      --name Ysmara --slug ysmara \\
      --eye "#ff8cdc" --pupil "#fff0fa" --mouth "#aa78ff" --tongue "#ff5aa0" \\
      --playfulness 0.8 --curiosity 0.85 --sleep-threshold 60 \\
      --expressions shy_smile,giggle,focused,determined \\
      --voice-provider sapi  (or elevenlabs)

Usage (interactive for humans):
  python onboard/designer.py --interactive

Usage (random persona — for quick bootstrap, still unique per-slug):
  python onboard/designer.py --name Rory --slug rory --random
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONAS_DIR = ROOT / "personas"
CONFIG_FILE = ROOT / "config" / "face.json"
BANK_FILE = Path(__file__).resolve().parent / "expressions-bank.json"


def load_bank():
    return json.loads(BANK_FILE.read_text(encoding="utf-8"))


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #rrggbb, got {h!r}")
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def hash_seed_palette(slug):
    """Deterministic-but-unique starter palette from slug hash. Agent will
    likely override, but this guarantees no two agents share a default."""
    h = hashlib.sha256(slug.encode("utf-8")).digest()
    # Eye hue from first 2 bytes
    eye_hue = h[0] / 255.0
    eye_sat = 0.6 + (h[1] / 255.0) * 0.35
    eye_val = 0.85 + (h[2] / 255.0) * 0.15
    # Mouth hue offset by golden-ratio conjugate for complement
    mouth_hue = (eye_hue + 0.618) % 1.0
    mouth_sat = 0.55 + (h[3] / 255.0) * 0.35
    mouth_val = 0.75 + (h[4] / 255.0) * 0.25

    def hsv_to_rgb(hue, sat, val):
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
        return [int(r * 255), int(g * 255), int(b * 255)]

    eye = hsv_to_rgb(eye_hue, eye_sat, eye_val)
    mouth = hsv_to_rgb(mouth_hue, mouth_sat, mouth_val)
    pupil = [min(255, c + 60) for c in eye]
    tongue = hsv_to_rgb((mouth_hue + 0.08) % 1.0, 0.85, 0.95)

    return {
        "bg": [8, 6, 14],
        "eye": eye,
        "pupil": pupil,
        "mouth": mouth,
        "tongue": tongue,
        "listening_accent": [min(255, eye[0] + 40), min(255, eye[1] + 40), min(255, eye[2] + 40)],
        "thinking_accent": [min(255, mouth[0] + 40), min(255, mouth[1] + 40), min(255, mouth[2] + 40)],
        "surprised_accent": [255, 220, 140],
    }


def hash_seed_personality(slug):
    h = hashlib.sha256(("personality:" + slug).encode("utf-8")).digest()
    return {
        "blink_rate": round(0.7 + (h[0] / 255.0) * 0.6, 2),
        "shyness": round(0.2 + (h[1] / 255.0) * 0.6, 2),
        "playfulness": round(0.3 + (h[2] / 255.0) * 0.6, 2),
        "attention_drift": round(0.3 + (h[3] / 255.0) * 0.5, 2),
        "curiosity": round(0.4 + (h[4] / 255.0) * 0.55, 2),
        "surprise_reactivity": round(0.4 + (h[5] / 255.0) * 0.5, 2),
        "sleep_threshold_sec": round(30 + (h[6] / 255.0) * 60, 1),
    }


def hash_seed_voice(slug):
    """SAPI voice is the free-tier default. Agent can override to ElevenLabs
    via --voice-provider elevenlabs + --voice-id if they have API credit."""
    h = hashlib.sha256(("voice:" + slug).encode("utf-8")).digest()
    return {
        "provider": "sapi",
        "sapi_voice_hint": "auto",
        "rate": round(0.85 + (h[0] / 255.0) * 0.3, 2),
        "pitch": round(0.9 + (h[1] / 255.0) * 0.2, 2),
        "elevenlabs_voice_id": None,
        "elevenlabs_model": "eleven_monolingual_v1",
    }


def validate_expressions(requested, bank):
    """Return the subset of requested IDs that exist in the bank, plus any warnings."""
    ids = {e["id"] for e in bank["expressions"]}
    kept = [e for e in requested if e in ids]
    rejected = [e for e in requested if e not in ids]
    return kept, rejected


def build_persona(args, bank):
    slug = args.slug.lower().strip()
    if not slug:
        raise SystemExit("slug is required")

    palette = hash_seed_palette(slug)
    personality = hash_seed_personality(slug)
    voice = hash_seed_voice(slug)

    # Manual overrides
    if args.eye:        palette["eye"] = hex_to_rgb(args.eye)
    if args.pupil:      palette["pupil"] = hex_to_rgb(args.pupil)
    if args.mouth:      palette["mouth"] = hex_to_rgb(args.mouth)
    if args.tongue:     palette["tongue"] = hex_to_rgb(args.tongue)

    if args.playfulness is not None:
        personality["playfulness"] = float(args.playfulness)
    if args.curiosity is not None:
        personality["curiosity"] = float(args.curiosity)
    if args.shyness is not None:
        personality["shyness"] = float(args.shyness)
    if args.sleep_threshold is not None:
        personality["sleep_threshold_sec"] = float(args.sleep_threshold)

    if args.voice_provider:
        voice["provider"] = args.voice_provider
    if args.voice_id:
        voice["elevenlabs_voice_id"] = args.voice_id
        if not args.voice_provider:
            voice["provider"] = "elevenlabs"
    if args.voice_rate is not None:
        voice["rate"] = float(args.voice_rate)
    if args.voice_pitch is not None:
        voice["pitch"] = float(args.voice_pitch)

    # Expression picks
    requested = []
    if args.expressions:
        requested = [e.strip() for e in args.expressions.split(",") if e.strip()]
    else:
        # Bank default: a varied starter set
        requested = ["shy_smile", "giggle", "focused", "determined", "wide_curious"]

    kept, rejected = validate_expressions(requested, bank)
    if rejected:
        print(f"[designer] dropping unknown expressions: {rejected}", file=sys.stderr)

    # Embed the actual preset bodies into the persona so agent can edit them
    expression_bodies = [e for e in bank["expressions"] if e["id"] in kept]

    persona = {
        "$schema_version": 2,
        "agent_name": args.name,
        "agent_slug": slug,
        "onboarded": True,
        "onboarded_version": "1.2.1",
        "palette": palette,
        "voice": voice,
        "personality": personality,
        "behavior_weights": {
            "eye_tag":   round(0.2 + personality["playfulness"] * 0.2, 2),
            "attentive": round(0.3 - personality["shyness"] * 0.2, 2),
            "tongue":    round(0.1 + personality["playfulness"] * 0.15, 2),
            "curious":   round(0.15 + personality["curiosity"] * 0.2, 2),
            "chill":     0.15,
        },
        "face_style": {
            "eye_shape": "round",
            "eye_size": "medium",
            "mouth_shape": "soft",
            "resolution": "64x64",
            "glow_intensity": round(0.85 + personality["surprise_reactivity"] * 0.1, 2),
        },
        "expressions": expression_bodies,
        "notes": args.notes or f"{args.name} — self-designed via onboard/designer.py.",
    }
    return persona


def write_persona(persona):
    slug = persona["agent_slug"]
    PERSONAS_DIR.mkdir(exist_ok=True)
    persona_path = PERSONAS_DIR / f"{slug}.json"
    persona_path.write_text(json.dumps(persona, indent=2), encoding="utf-8")

    CONFIG_FILE.parent.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(persona, indent=2), encoding="utf-8")
    return persona_path, CONFIG_FILE


def interactive(args, bank):
    print("=== AXIOM-Body onboarding ===")
    if not args.name:
        args.name = input("Agent name: ").strip()
    if not args.slug:
        args.slug = (args.name or "").lower().replace(" ", "-")
        args.slug = input(f"Slug [{args.slug}]: ").strip() or args.slug
    if not args.eye:
        args.eye = input("Eye color hex (blank = seeded): ").strip() or None
    if not args.mouth:
        args.mouth = input("Mouth color hex (blank = seeded): ").strip() or None
    if not args.expressions:
        print(f"Available expressions: {', '.join(e['id'] for e in bank['expressions'])}")
        args.expressions = input("Pick 3-7 (comma-separated): ").strip() or None
    if not args.voice_provider:
        args.voice_provider = input("Voice provider [sapi/elevenlabs]: ").strip() or "sapi"
    if args.voice_provider == "elevenlabs" and not args.voice_id:
        args.voice_id = input("ElevenLabs voice_id: ").strip() or None
    return args


def main():
    parser = argparse.ArgumentParser(description="Onboard a new AXIOM-Body agent.")
    parser.add_argument("--name", required=False)
    parser.add_argument("--slug", required=False)
    parser.add_argument("--eye", help="#rrggbb")
    parser.add_argument("--pupil", help="#rrggbb")
    parser.add_argument("--mouth", help="#rrggbb")
    parser.add_argument("--tongue", help="#rrggbb")
    parser.add_argument("--playfulness", type=float)
    parser.add_argument("--curiosity", type=float)
    parser.add_argument("--shyness", type=float)
    parser.add_argument("--sleep-threshold", type=float)
    parser.add_argument("--voice-provider", choices=["sapi", "elevenlabs"])
    parser.add_argument("--voice-id")
    parser.add_argument("--voice-rate", type=float)
    parser.add_argument("--voice-pitch", type=float)
    parser.add_argument("--expressions", help="Comma-separated bank ids.")
    parser.add_argument("--notes")
    parser.add_argument("--random", action="store_true", help="Skip overrides; seed everything from slug hash.")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    bank = load_bank()
    if args.interactive:
        args = interactive(args, bank)
    if not args.name or not args.slug:
        parser.error("--name and --slug are required (or use --interactive)")

    persona = build_persona(args, bank)
    persona_path, config_path = write_persona(persona)
    print(f"[designer] wrote {persona_path}")
    print(f"[designer] wrote {config_path}")
    print(f"[designer] {persona['agent_name']} is onboarded.")
    print(f"  palette.eye = {rgb_to_hex(persona['palette']['eye'])}")
    print(f"  palette.mouth = {rgb_to_hex(persona['palette']['mouth'])}")
    print(f"  voice = {persona['voice']['provider']} (rate={persona['voice']['rate']}, pitch={persona['voice']['pitch']})")
    print(f"  expressions = {[e['id'] for e in persona['expressions']]}")


if __name__ == "__main__":
    main()
