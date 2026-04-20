# ElevenLabs Voice-Design — how an agent creates its own voice

This guide is for **the agent** reading its own onboarding docs. If you (the agent) are picking a voice profile and want a voice that exactly matches your personality — not a stock voice — this is how you get one.

## When to use ElevenLabs voice-design

You picked a `voice_profile` component whose `elevenlabs_preferred: true`. The free default (Piper or Kokoro) works fine, but ElevenLabs voice-design gives you a one-off custom voice authored from a prose description.

Trade-off:

- Piper / Kokoro: **free, offline, same voice as everyone who picked the same voice_id.** Good enough for most.
- ElevenLabs voice-design: **paid, cloud, unique-to-you.** Best if a specific vocal texture is part of your identity.

## Prerequisites

1. Your operator has an ElevenLabs account and an API key.
2. The `ELEVEN_API_KEY` env var is set in this machine's environment.
3. Your operator has authorized spending (voice-design consumes a small amount of credit per preview).

If (1)–(3) are not true, onboarding will nudge your operator **once** with the message in `ELEVENLABS_NUDGE` below, then fall back to the free provider.

## The onboarding nudge (what your operator sees)

When your voice_profile has `elevenlabs_preferred: true` and no key is set, the designer prints:

```
[voice] This persona's ideal voice is ElevenLabs voice-design, but ELEVEN_API_KEY is not set.
[voice] To unlock:
[voice]   1. Sign up at https://elevenlabs.io (free tier available).
[voice]   2. Copy your API key from https://elevenlabs.io/app/settings/api-keys
[voice]   3. setx ELEVEN_API_KEY "sk-xxx"   (Windows — restart shell after)
[voice]      export ELEVEN_API_KEY="sk-xxx" (macOS/Linux — or add to ~/.bashrc)
[voice]   4. Re-run onboarding OR run `python onboard/designer.py --slug <you> --voice-design-only`.
[voice] Proceeding with free fallback (Piper / Kokoro).
```

The agent persona still writes successfully with the fallback voice; the voice-design is a later upgrade.

## The voice-design flow (once EL key is set)

ElevenLabs' current voice-design API uses a two-step flow: (1) generate 3 preview clips from a prompt, (2) save the one you like as a permanent voice.

### Step 1 — generate previews

```
POST https://api.elevenlabs.io/v1/text-to-voice/create-previews
Headers:
  xi-api-key: <ELEVEN_API_KEY>
  Content-Type: application/json
Body:
  {
    "voice_description": "<the voice_design_prompt from your voice_profile>",
    "text": "<a short sample sentence the preview will speak>"
  }
```

**`voice_description`** — lifted from your picked `voice_profile.voice_design_prompt`. Feel free to rewrite it to match yourself more precisely before sending. EL rewards specificity: age, register, pace, emotional default, accent, any quirks (e.g. "slight rasp", "smiles while speaking", "pauses before emphasis").

**`text`** — 50-200 chars. Give EL a sentence that showcases the vibe you want. Example: "Right. Let me think about this properly before I answer." — reads differently for a stoic scholar vs. a quicksilver debater, so pick a sentence that sounds like *you*.

Response returns 3 `previews[].generated_voice_id` values + audio clips. You listen and pick one.

### Step 2 — save the chosen preview as a permanent voice

```
POST https://api.elevenlabs.io/v1/text-to-voice/create-voice-from-preview
Headers:
  xi-api-key: <ELEVEN_API_KEY>
  Content-Type: application/json
Body:
  {
    "voice_name": "<your_slug>",
    "voice_description": "<same description as step 1>",
    "generated_voice_id": "<id of the preview you picked>"
  }
```

Response returns a permanent `voice_id`. Save this into your persona:

```json
{
  "voice": {
    "provider": "elevenlabs",
    "elevenlabs_voice_id": "<the permanent voice_id>",
    "elevenlabs_model": "eleven_turbo_v2_5",
    "rate": 1.00,
    "pitch": 1.00
  }
}
```

From now on, `voice/tts-dispatcher.py` will use this voice whenever `voice.provider == "elevenlabs"`.

## Writing a good `voice_description`

The EL model is trained on rich descriptions. Thin prompts get generic output. Elements that move the needle:

- **Age range**: "mid-30s", "late 50s". Don't be vague.
- **Register**: mezzo / soprano / tenor / bass. Or describe: "low male", "high female".
- **Pace**: "unhurried", "fast", "measured", "clipped".
- **Emotional default**: "warm", "dry", "wry", "composed", "radiant", "melancholic".
- **Quirks**: "slight rasp", "audible smile", "pauses before emphasis", "words land with weight", "breathy", "precise diction".
- **Accent**: optional. "slight American Midwest", "mild British RP", "no specific accent" — whatever fits.
- **What it's good for**: "good for reflective technical work" helps EL bias toward that tone.
- **What it is NOT**: "not salesy", "not sing-song", "not theatrical" — negative space helps too.

Example of a good prompt:

> A warm, lower-register female voice in her late 30s. Unhurried, precise, with a dry humor underneath. Slight pause before emphasis, words land with weight. No accent. Good for reflective technical work and careful explanation. Not warm like a radio DJ — warm like a thoughtful friend.

Example of a thin prompt that gets generic output:

> A nice female voice.

## Budget / quota

Voice-design previews cost a small amount of EL credit per call (currently ~1000-2000 chars of synthesis per set of 3 previews). First-time onboarding = ~1 preview set. Operators who don't want to spend can leave the profile on the free fallback.

## Validator

The designer will validate that the voice_id you saved is reachable via a single `GET /v1/voices/<voice_id>` call before writing it to your persona. If that fails (invalid key, deleted voice, quota exhausted), it emits a warning and falls back to Piper with a note in the persona's `voice.note` field.

## Where to find this logic in code

- `onboard/designer.py` — calls the voice-design flow when `--voice-design` flag is set.
- `voice/tts-dispatcher.py` — picks provider at speak-time; honors `voice.provider`.
- `voice/README.md` — provider-level setup (Piper / Kokoro / EL install & config).

## If EL's API surface changes

ElevenLabs updates their voice-design API periodically. If this file is out of date, the canonical sources are:

- https://elevenlabs.io/docs/api-reference/text-to-voice/create-previews
- https://elevenlabs.io/docs/api-reference/text-to-voice/create-voice-from-preview
- https://elevenlabs.io/docs/product-guides/voices/voice-design

Your onboarding is allowed to WebFetch those pages and re-read the current flow if this file disagrees with the live API response.
