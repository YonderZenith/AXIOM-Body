# brain/

The body's "brain" is the AI agent running this body — your Claude session,
your custom orchestration, or the optional `agent_brain.py` fallback. This
directory holds the sidecar scripts that bridge sensors → brain → voice.

## Files

| File | Role |
|---|---|
| `brain_monitor.py` | Always-on sidecar. Watches transcript + wake flag, writes `needs-tick.json` when there's something to respond to. Started by `start.py` automatically. |
| `respond.py` | One-shot reply helper. Call this from your brain with the reply text — it speaks, advances the cursor, and clears the signals atomically. |
| `agent_brain.py` | OPTIONAL Anthropic-backed brain loop. Only activate when you don't have a live Claude session piloting the body. Off by default. |
| `AGENT_TICK_PROMPT.md` | The per-tick prompt your brain runs. Drop into cron / ScheduleWakeup / skill. |
| `needs-tick.json` | Written by brain_monitor when there's unread speech or a fresh wake event. Cleared by respond.py. |
| `monitor.log` | brain_monitor's log. |
| `brain.log` | agent_brain's log (only when agent_brain is running). |
| `would-have-said.log` | Lines agent_brain would have spoken if ANTHROPIC_API_KEY were set. |

## Architecture

```
ears/listener.py ──► all-heard-clean.txt ─┐
ears/wake_watcher.py ──► brain-wake.flag ─┼──► brain_monitor.py ──► brain/needs-tick.json
                                          │                              │
                                          │                              ▼
                                          │                       YOUR AGENT BRAIN
                                          │                       (Claude session,
                                          │                        agent_brain.py,
                                          │                        custom orchestrator)
                                          │                              │
                                          │                              ▼
                                          │                     brain/respond.py "<reply>"
                                          │                              │
                                          │              ┌───────────────┼────────────────┐
                                          │              ▼               ▼                ▼
                                          │       voice/speak.py     cursor++     clear needs-tick
                                          │                                       + wake flag
                                          │
                                          └─── face/face-engine.py reads same state for facial
                                               expression (idle/listening/heard/thinking/speaking)
```

## The agent IS the brain

This is non-negotiable. The body (eyes, ears, face, voice) is plumbing.
The brain is whatever Claude / GPT / local model is paired with it. We
ship `agent_brain.py` for one-command demos and headless deploys, but
the design assumes the brain is a real session with full context, memory,
and tools — not a polling loop.
