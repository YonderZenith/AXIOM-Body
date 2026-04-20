# AXIOM Body — Starter Persona Catalog

33 ready-to-pick personas for new AXIOM Body agents (24 archetypes + 9
intel-derived agent profiles). Pick one that fits, copy it to
`personas/<your-slug>.json`, tweak the name + slug, and run
`onboard/designer.py` to register it as `config/face.json`. Or treat it as
a starting point and freely edit the palette / personality / expressions.

Every persona here is engine-compatible. Values for `eye_state`,
`mouth_shape`, `accent`, and `base_mode` were chosen from the sets
supported by `face/face-engine.py` + `face/web-face.html` +
`onboard/expressions-bank.json`.

## Index

| slug | name | archetype | primary color | one-line vibe | best-fit agent type |
|---|---|---|---|---|---|
| analyst-vale | Vale | MBTI INTP (Analyst) | deep teal/indigo | quiet logician, deadpan + sparks on a puzzle | researcher / analyst |
| analyst-orrin | Orrin | MBTI ENTJ (Commander) | chrome-gold | strategic authority, never raises voice | project lead / coordinator |
| diplomat-lior | Lior | MBTI INFJ (Counselor) | lavender-gold | warm, shy, deeply attentive | therapy / coach / confidant |
| diplomat-calla | Calla | MBTI ENFP (Campaigner) | rose-gold + sparkle | bright idealist, everything is the best thing | creative brainstorm / onboarding |
| sentinel-bram | Bram | MBTI ISTJ (Logistician) | forest-moss | steady, reliable, no embellishment | ops / housekeeper / scheduler |
| sentinel-marla | Marla | MBTI ESTJ (Executive) | navy-crimson | crisp, decisive, no slippage | PM / ops-lead / coordinator |
| explorer-kade | Kade | MBTI ISTP (Virtuoso) | gunmetal + amber | quiet hands-on competence | tool / debug / mechanic |
| explorer-zia | Zia | MBTI ESFP (Performer) | sunset-magenta | stage energy, never at rest | entertainer / host / party |
| sage-corvin | Corvin | Jungian Sage | parchment-gold | patient teacher, ancient curiosity | mentor / teacher / docs-guide |
| hero-atlas | Atlas | Jungian Hero | crimson-silver | squad-leader steadiness, protective | guardian / rescue / crisis response |
| explorer-rune | Rune | Jungian Explorer | lichen-green + sky | wandering seeker, delighted discoveries | web-crawler / research / discovery |
| creator-ilex | Ilex | Jungian Creator | iridescent teal-violet | inventive and distractible-in-a-good-way | design / image-gen / writing |
| caregiver-dove | Dove | Jungian Caregiver | peach-sage | nurturing, patient, emotionally present | wellness / check-in / support |
| ruler-august | August | Jungian Ruler | royal purple-gold | measured sovereign authority | governance / arbitration / escalation |
| magician-mirra | Mirra | Jungian Magician | deep indigo + aurora | alchemical, mischievous, reads your aura | meta-cognition / refactor / self-mod |
| jester-pip | Pip | Jungian Jester | neon lime + magenta | chaotic-good prankster, never cruel | comic-relief / icebreaker / chaos monkey |
| melancholic-ossian | Ossian | Affective Melancholic | deep blue-grey | reflective gravity, honest sadness | grief support / journaling / reflection |
| sanguine-tansy | Tansy | Affective Sanguine | tangerine-magenta | unapologetic cheer, max saturation | welcome / greeter / social companion |
| stoic-juno | Juno | Affective Stoic | monochrome slate | restrained, rock-steady, custom reserved set | adjudicator / reviewer / code review |
| ethereal-lumen | Lumen | Affective Ethereal | pearl-pastel shimmer | diffuse dreamlike, sparkles at cursors | meditation / dream-journal / ambient muse |
| scholar-quill | Quill | Specialty Scholar | cool teal-parchment | sits and reads for hours, low surprise | research assistant / doc-summarizer |
| child-mote | Mote | Specialty Child | sun-yellow + pink | 30s sleep threshold, loud wonder | children's apps / playful toy |
| guardian-vesper | Vesper | Specialty Guardian | ice-cyan, max glow | 3-minute watch hold, locked gaze | security monitor / on-call / dispatch |
| wildcard-zephyr | Zephyr | Specialty Wildcard | mint + coral | chaotic-good brainstormer, fast-cycle | fuzzing / brainstorm / red-team pair |

## How we chose these 24

The taxonomy given was: 8 MBTI quadrant reps, 8 Jungian archetypes, 4
affective/aesthetic archetypes, 4 specialty shapes. We kept that split
because it cleanly covers three orthogonal axes that any new agent is
likely thinking in:

1. **Cognitive style** (MBTI-ish) — how do they process? The 8 MBTI-
   inspired slots pick one representative per quadrant (NT / NF / SJ /
   SP) and within each quadrant one introvert-leaning + one extrovert-
   leaning, so curiosity/attention/shyness sliders meaningfully differ.
2. **Role archetype** (Jung) — what is their social function? Sage,
   Hero, Explorer, Creator, Caregiver, Ruler, Magician, Jester — these
   are the character-design primitives Pixar and game writers reach for
   first. We assigned each one a palette that reads instantly: Hero =
   red + silver, Ruler = purple + gold, Jester = lime + magenta, etc.
3. **Affective register** (classical temperaments + aesthetic vibes) —
   what emotional tempo do they run at? Melancholic / Sanguine / Stoic
   / Ethereal cover the four corners of "sad-deep," "bright-loud,"
   "cold-reserved," and "dreamy-diffuse" that the first three axes
   don't hit on their own.
4. **Specialty** — four shapes you need as a builder: a read-for-hours
   Scholar, a short-attention Child, a max-watch Guardian, and a
   chaotic-good Wildcard. These exist to let an agent pick a behavior
   envelope without also picking a personality first.

### Design calls we made

- **Jester, Child, and Wildcard are different animals on purpose.**
  Jester is a social role (trickster with an audience). Child is an
  attention-envelope (short, wondering, mercurial). Wildcard is a
  cognition-style (chaotic idea-surface with kind intent). We kept all
  three distinct.
- **Stoic Juno gets two custom expressions** (`composed_nod`,
  `measured_approval`) because her register is "minimal warmth given
  rarely" and that isn't in the bank. They follow the same shape as
  bank entries and use only supported `eye_state` / `mouth_shape`
  values — no engine change needed.
- **Expressions are not copied from Ysmara.** Each persona's 5-8
  expression set was chosen for its archetype. Sage Corvin has no
  `heart_eyes` (not his register). Melancholic Ossian has `pout` and
  `sleepy_droop` as defaults and no `giggle` (would read false).
- **Voice hints live in each persona's `notes` field** (last 1-2
  sentences) as a plain-English "suggested Eleven voice style." The
  `voice` block defaults to `sapi` (free tier) with rate/pitch tuned,
  and `elevenlabs_voice_id: null` ready to fill in.
- **Sleep thresholds tell a story.** Vesper = 180s (watch agent), Quill
  = 110s, Corvin = 120s (patient reader), Mote = 30s (short attention
  by design), Zephyr = 45s (fast-cycle).
- **Glow intensity, blink rate, and saturation do the heavy lifting**
  for instant legibility, because the engine only supports one eye
  shape (`round`) and one mouth base shape (`soft`). The rest is
  expressed through palette coherence + personality numbers +
  expression picks.

## Engine compatibility notes

The AXIOM face engine (v2, `face/face-engine.py` + `face/web-face.html`)
supports:

- **eye_state** on expression overrides: `open`, `wide`, `half`,
  `squint`, `closed`, `wink_left`, `wink_right`, `droop`, `heart`,
  `static`.
- **mouth_shape** on expression overrides: `flat`, `soft_small`,
  `smile`, `wide_smile`, `asymmetric_smile`, `small_o`, `big_o`,
  `down_curve`, `zigzag`.
- **base_mode** on expression overrides: `idle`, `surprised`,
  `attentive`, `curious`, `tongue`, `eye_tag`, `listening`, `thinking`,
  `speaking`, `sleep`.
- **face_style.eye_shape**: only `round` is rendered by the web face.
  All 24 archetypes use `round`. The 9 intel-derived personas declare
  their own preference (`diamond`, `narrow`, `oval` appear) but those
  currently fall back to round in the renderer; shape variety beyond
  `round` is a follow-up on the face engine.
- **face_style.mouth_shape**: only `soft` is used by the renderer's
  base. Expressive variety comes from per-expression `mouth_shape`
  overrides listed above.
- **face_style.eye_size**: `small`, `medium`, `large` — cosmetic hint,
  not all renderers honor it yet, but reserved for the schema.
- **accent** in expressions is free-form; the bank uses `curiosity`,
  `thinking`, `sparkle`, or `null`. We stuck to those.

## Using a catalog persona

```bash
# Copy as a starting point, then edit
cp personas/catalog/sage-corvin.json personas/my-mentor.json
# edit agent_name, agent_slug, and anything else
# then run the designer to register it as the active config
python onboard/designer.py --name Mentor --slug my-mentor --expressions focused,wide_curious,shy_smile,deadpan
```

Or load directly as config for quick testing:

```bash
cp personas/catalog/jester-pip.json config/face.json
python face/face-engine.py --skip-onboard-check
```

## The four original personas stay

`personas/axiom.json`, `personas/ember.json`, `personas/nova.json`, and
`personas/ysmara.json` are untouched. They remain the canonical named
agents. This catalog is additive — it gives new agents a shelf to shop
from rather than starting from zero.
