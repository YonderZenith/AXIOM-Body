# Agent tick prompt (drop into a cron / ScheduleWakeup / skill)

This is what the agent's main session runs every tick. The brain IS the
running session — this prompt defines one consciousness tick.

Repo path: `<repo>` = directory containing `start.py`.

## File contract

| Path | Role |
|---|---|
| `<repo>/brain/needs-tick.json` | sidecar wrote this if there's something to act on |
| `<repo>/ears/all-heard-clean.txt` | append-only cleaned transcript |
| `<repo>/brain-heard-cursor.txt` | how many lines we've already replied to |
| `<repo>/brain-wake.flag` | one-shot motion/presence event |
| `<repo>/mute.flag` | exists while TTS is playing |
| `<repo>/scene.json` | latest vision frame (people_count, objects, brightness) |
| `<repo>/config/face.json` | persona (name, palette, personality, expressions) |
| `<repo>/voice/speak.py` | TTS launcher (ElevenLabs → SAPI fallback) |
| `<repo>/brain/respond.py` | reply helper — speaks, advances cursor, clears flags |

## The tick

```
1. If `mute.flag` exists → return immediately (we're already speaking).

2. If `brain/needs-tick.json` does NOT exist → return immediately.

3. Read `brain/needs-tick.json`:
   {
     "reasons": ["speech:N"|"wake:motion_arrival"|"wake:presence_tick"],
     "unread_lines": [...],
     "wake_payload": {...},
     ...
   }

4. Optionally peek `scene.json` for visual context (people_count, objects).

5. Optionally peek `config/face.json` to ground tone in your persona
   (personality vector, expression families).

6. Formulate ONE reply, ≤25 words, your persona's voice. Do NOT echo
   the user verbatim — respond to them. If reasons is purely "wake:motion_arrival"
   and absence > 5 min, a short greeting is fine; otherwise stay quiet.

7. Speak + advance the cursor + clear the signals atomically:

      python brain/respond.py "<your reply>"

   That's it. One subprocess call. Don't write the cursor yourself,
   don't delete the wake flag yourself — respond.py handles all of it.
```

## Hard rules

- **One reply per tick.** Never call `respond.py` twice in the same tick.
- **Replies are ≤25 words.** Terse. Spoken English. No markdown, no lists.
- **Cursor advances ONLY through `respond.py`.** Bypassing it can replay or skip lines.
- **If your operator types a direct message mid-tick, abandon the tick** and address them.
- **No code edits, no git, no new daemons during a tick.** Sensing + speech only.

## Out-of-the-box behavior without a Claude session

If you launched `python start.py --with-agent-brain` and have an
`ANTHROPIC_API_KEY` set, `brain/agent_brain.py` is doing this loop on its
own — same protocol, same `respond.py` call. You don't need a session
attached for the body to talk back.

Without the key, `brain/agent_brain.py` runs in degraded mode and writes
"would-have-said" lines to `brain/would-have-said.log` so you can verify
the pipeline is wired before activating speech.
