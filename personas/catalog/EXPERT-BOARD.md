# AXIOM Body — Persona Expert Board

The catalog is not a grab-bag. Every persona has been designed under the lens of
one or more named experts so that an agent picking a starter persona lands on a
coherent, psychologically-grounded face — not a cartoon stereotype. This file
documents the experts we convene, the frames they bring, and how those frames
map onto the engine's renderable primitives.

## Who is on the board

### Personality & temperament

- **Isabel Briggs Myers** — MBTI 16 types. Frame: cognitive-function axes
  (I/E, N/S, T/F, J/P). We ship one persona per type so operators can slot any
  MBTI-aligned agent without design work.
- **Robert McCrae & Paul Costa** — Big Five / OCEAN. Frame: five orthogonal
  trait axes (Openness, Conscientiousness, Extraversion, Agreeableness,
  Neuroticism). We pick ten distinctive axial profiles — not all 32 — because
  low-O/low-C/low-E/low-A/high-N ("the burned-out cynic") is a real texture
  worth having even if MBTI doesn't name it.
- **Claudio Naranjo / Riso & Hudson** — Enneagram 9 types plus select wings.
  Frame: core motivations + avoidance patterns. These land closer to "how an
  agent handles pressure" than MBTI does.
- **Michael Ashton & Kibeom Lee** — HEXACO. Frame: adds honesty-humility as a
  sixth trait. We use this to distinguish "earnest" from "charming" personas
  where Big Five would conflate them.
- **Erik Erikson** — 8 psychosocial stages. Frame: life-stage archetypes
  (trust vs mistrust, identity vs confusion, generativity vs stagnation).
  Useful for assigning agents a developmental voice, not a birth-year.
- **John Bowlby / Mary Ainsworth** — 4 attachment styles. Frame: how the
  persona relates to its operator when the operator is absent, upset, or
  returning. Critical for caregiver / assistant roles.
- **David Keirsey** — 4 temperaments (Artisan, Guardian, Idealist, Rational).
  Frame: meta-layer over MBTI that groups functions by core values.

### Emotion & facial expression

- **Paul Ekman** — 7 basic emotions (joy, anger, fear, disgust, sadness,
  surprise, contempt) and FACS (Facial Action Coding System). Frame: maps
  emotion → specific muscle actions. We use Ekman's canonical expression
  vocabulary to pick `eye_state` + `mouth_shape` combos that actually read
  as the intended emotion to a human viewer.
- **Robert Plutchik** — 8 primary emotions on a wheel with 3 intensities each.
  Frame: adjacent emotions blend into nameable compound emotions
  (joy+trust = love, surprise+sadness = disappointment). We ship affect-
  driven personas whose resting state *is* a specific emotion rather than a
  role.
- **Carroll Izard** — Differential Emotions Theory. Frame: discrete emotions
  as biological universals. Backstops Ekman on cross-cultural legibility.

### Archetypes & story

- **Carl Jung** — 12 archetypes (Self, Shadow, Anima/Animus + 8 others like
  Hero, Sage, Jester, Creator). Frame: deep-pattern characters humans
  recognise immediately.
- **Joseph Campbell / Christopher Vogler** — Hero's Journey roles
  (Hero, Mentor, Threshold Guardian, Herald, Shapeshifter, Shadow, Trickster,
  Ally). Frame: narrative function rather than personality trait.
- **Vladimir Propp** — 7 character types in folktales (villain, donor, helper,
  princess-or-prize, dispatcher, hero, false-hero). Frame: role a character
  plays inside a plot.

### Cultural masks & theatrical archetypes

- **Commedia dell'arte stock characters** — Arlecchino, Pantalone, Dottore,
  Columbina, Pulcinella, Brighella, Capitano, Pierrot. Frame: live-theatre
  characters whose body language and face are the whole character.
- **Noh / Kabuki mask canon** — Ko-omote (young woman), Hannya (jealous
  demon), Jo (old man), Aragoto (rough hero), Onnagata (feminine). Frame:
  traditional Japanese expressive grammar; each mask is a precise emotional
  mode.
- **Tarot Major Arcana** — 22 archetypal figures. Frame: symbolic roles
  (Fool, Magician, High Priestess, Hermit, Star, Moon, Sun, World). We ship
  the six most legible.

### Character design & visual language

- **Disney's Nine Old Men (Ollie Johnston, Frank Thomas)** — character-design
  fundamentals: silhouette-first readability, principal of shape (round =
  warm, square = reliable, triangle = threat). Frame: every palette we
  choose has to read the intended emotion *in the first 500 ms*, because
  that's roughly when an operator glances at the face.
- **Daniel Arriaga / Don Shank (Pixar)** — colour scripts. Frame: a colour
  palette is a narrative. We assign each persona a coherent 8-colour palette
  (bg, eye, pupil, mouth, tongue, listening-accent, thinking-accent,
  surprised-accent) that tells a short internal story.
- **Bruno Munari** — minimalist graphic design. Frame: reduction to essentials
  so 64×64 still carries a persona's soul. Every palette choice has to
  survive the lowest-resolution renderer.

### Neurodiversity & non-canonical textures

- **Temple Grandin / Devon Price** — authentic autistic inner-life writers.
  Frame: treat pattern-focus, hyperempathy, hyperfocus as genuine personality
  textures, not clinical deficits.
- **Russell Barkley** — ADHD researcher. Frame: time-blindness, hyperfocus,
  executive-function variance as distinct cognitive styles that deserve a
  face of their own.

## How the board's frames become engine primitives

Every persona must compile down to renderable values the engine supports:

```
valid_base_modes:   idle, surprised, attentive, curious, tongue, eye_tag,
                    listening, thinking, speaking, sleep
valid_eye_states:   open, wide, half, squint, closed, wink_left, wink_right,
                    droop, heart, static
valid_mouth_shapes: flat, soft_small, smile, wide_smile, asymmetric_smile,
                    small_o, big_o, down_curve, zigzag
```

Mapping conventions the board agreed:

| Expert frame           | Maps to                                             |
| ---------------------- | --------------------------------------------------- |
| Ekman emotion          | resting `eye_state` + `mouth_shape` combo per       |
|                        | emotion (e.g. disgust → half + down_curve).         |
| MBTI `J` vs `P`        | `behavior_weights` — J lean attentive+chill, P lean |
|                        | curious+eye_tag.                                    |
| Enneagram core type    | `sleep_threshold_sec` + `shyness` + idle base mode. |
| Big Five Openness      | `curiosity` (direct map).                           |
| Big Five Extraversion  | inverse of `shyness` + `behavior_weights.eye_tag`.  |
| Big Five Neuroticism   | `surprise_reactivity` and glow wobble.              |
| Attachment style       | `sleep_threshold_sec` + absence-reactive behavior.  |
| Campbell role          | principal expression set + accent palette.          |
| Commedia mask          | `face_style.mouth_shape` style hint (exaggerated    |
|                        | for Arlecchino, flat for Pierrot).                  |
| Ekman FACS AU          | per-expression `eye_state` + `mouth_shape`.         |
| Disney principal shape | overall `glow_intensity` + palette warmth.          |
| Pixar colour-script    | the 8 palette hex values as a narrative unit.       |

## Quality gates every persona must pass

1. **Engine compatibility** — every `base_mode`, `eye_state`, `mouth_shape`
   comes from the supported sets. Palette values are valid RGB triplets.
   Personality floats are in range. Generator validates on write; a persona
   that fails does not land in the catalog.
2. **Silhouette test** — palette reads as the intended emotional family on a
   glance. No muddy "purple-ish, I guess?" palettes.
3. **Expression distinctness** — every persona's 5-8 expressions must be
   visibly different from each other on the same face. No two expressions
   compile to the same (base_mode, eye_state, mouth_shape) triple.
4. **Voice coherence** — voice rate + pitch match the face (frenetic face
   shouldn't ship with a slow voice unless intentional contrast).
5. **Agent-type fit** — the persona has a best-fit-agent-type so an operator
   picking for a role lands somewhere reasonable, not randomly.

## How to add a new persona

The catalog is generator-driven. Add a dictionary entry to the appropriate
seed file under `personas/catalog/_gen/seed_*.py`, then run:

```
python personas/catalog/_gen/generate.py
```

The generator expands hex colour codes to RGB lists, fills in structural
defaults (schema version, voice provider, eye shape, resolution), resolves
`expressions` entries against `onboard/expressions-bank.json`, validates
against the engine's supported sets, and writes one JSON per persona.

Any entry that fails validation is reported and the run halts. Broken
catalog never ships.
