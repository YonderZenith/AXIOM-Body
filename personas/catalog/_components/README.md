# Persona Components — the mix-and-match menus

This directory is a set of independent category menus. An agent designs its
persona by picking **one** entry from each required category, producing a
composed persona. This replaces any notion of a fixed, pre-baked catalog — the
catalog is now the *ingredients*, not the dishes.

## Combinatorial scope

| Menu | File | Count | Pick |
|------|------|-------|------|
| Personality profile | `personality_profiles.json` | 20 | required, 1 |
| Emotion register | `emotion_registers.json` | 10 | optional, 1 |
| Archetype | `archetypes.json` | 16 | optional, 1 |
| Aesthetic palette | `aesthetic_palettes.json` | 14 | required, 1 |
| Vocation | `vocations.json` | 10 | optional, 1 |
| Face style | `face_styles.json` | 8 | required, 1 |
| Voice profile | `voice_profiles.json` | 8 | required, 1 |
| Expressions | `../../../onboard/expressions-bank.json` | 60 atoms | required, pick 5-8 |
| Starter set (optional shortcut) | `starter_expression_sets.json` | 10 bundles | optional |

Full combinatorial space: roughly

    20 × 10 × 16 × 14 × 10 × 8 × 8 × C(60, 6) ≈ 3 × 10^12

(that's with exactly 6 expressions; picking 5-8 multiplies further). The point
isn't that every combination is meaningfully distinct — it's that an agent
never sees a persona-menu of "pick one of 76". Every agent lands on something
that feels authored-for-them because they authored it themselves from menus
broad enough that collision is unlikely.

## Who's on the expert board

See `../EXPERT-BOARD.md` for the full list. Every menu here is designed under
the lens of one or more of those experts:

- Personality profiles: Myers (MBTI), McCrae & Costa (Big Five), Naranjo /
  Riso-Hudson (Enneagram), Ashton & Lee (HEXACO), Bowlby / Ainsworth
  (attachment), Keirsey.
- Emotion registers: Ekman, Plutchik, Izard.
- Archetypes: Jung, Campbell / Vogler (Hero's Journey), Propp (folktale).
- Aesthetic palettes: Arriaga / Shank (Pixar color-scripts), Disney Nine Old
  Men shape theory, Munari minimalism.
- Face styles: Disney silhouette-first readability, Noh / Kabuki mask canon.
- Voice profiles: informed by EL voice-design prompt patterns + Piper /
  Kokoro free-tier voice IDs.

## Engine compatibility

Every picked component must compile into the engine's supported enum sets
(`valid_base_modes`, `valid_eye_states`, `valid_mouth_shapes`). The composer
(`../_gen/compose.py`) validates every pick; invalid ids raise with the list
of valid ones. A persona that fails validation is never written.

## How to compose

CLI (quick for humans or scripts):

    python personas/catalog/_gen/compose.py \\
        --name Zeph --slug zeph \\
        --personality mbti-entp --emotion sanguine --archetype trickster \\
        --palette neon_cyberpunk --vocation entertainer \\
        --face-style pixel_crisp --voice quicksilver_tenor \\
        --expressions giggle,raspberry,wink_right,smug,dazzled,razor_sharp,focused

Library (what onboarding code actually calls):

    from personas.catalog._gen.compose import compose_persona, write_persona

Listing the menu (for an onboarding UI / LLM-agent picker):

    python personas/catalog/_gen/compose.py --list

## Mandatory vs. optional picks

- **Required** (composer will reject missing): personality_profile,
  aesthetic_palette, face_style, voice_profile, and either expression_ids or
  starter_expression_set_id.
- **Optional** (skip to keep persona simple): emotion_register, archetype,
  vocation. Skipping any of these just means that component's biases aren't
  overlaid. The persona stays valid.

## How to add to a menu

Add a new entry to the appropriate JSON file, following the existing schema
for that category. Every entry needs a stable `id`. Re-run any composed
persona that referenced an id you renamed — the composer will raise
`ComposeError` until the reference is fixed.

For the expression bank (`onboard/expressions-bank.json`), every new atom
must include `base_mode` and should include `eye_state` + `mouth_shape`. See
`authoring_schema` at the bottom of that file.

## Pre-mixed catalog entries

`../*.json` (the per-slug persona files in the parent `catalog/` dir) are
**pre-mixed examples** showing curators' taste — they illustrate what
specific combinations of components produce. They are not the primary
surface; new agents should compose, not copy.

## Pointing at the bulletin-sourced intel

`Z:\BULLETINS HERE ONLY!\2026-04-21T03-15-00Z_ysmara-AXIOM-BODY-EXPRESSION-INTEL-REQUESTED.json`
asks every active agent for their expression + personality self-descriptions.
As responses land in `Z:\inbox\ysmara\`, new expressions get added to the
bank; new personality textures may add fields to `personality_profiles.json`
or spawn new menus entirely.
