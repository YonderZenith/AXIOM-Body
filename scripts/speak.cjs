// AXIOM Voice — speaks text via ElevenLabs (with timestamps for exact duration)
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const text = process.argv.slice(2).join(' ');
if (!text) { process.exit(0); }

const BASE_DIR = path.resolve(__dirname, '..');
const AUDIO = path.join(BASE_DIR, 'axiom', 'voice-now-' + Date.now() + '.mp3');
const SIGNAL = path.join(BASE_DIR, 'axiom', 'voice-playing.signal');

(async () => {
  const apiStart = Date.now();
  const res = await fetch('https://api.elevenlabs.io/v1/text-to-speech/cjVigY5qzO86Huf0OWal/with-timestamps', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'xi-api-key': process.env.ELEVENLABS_API_KEY || fs.readFileSync(path.resolve(__dirname, '..', 'config', 'elevenlabs_api_key.txt'), 'utf-8').trim(),
    },
    body: JSON.stringify({ text, model_id: 'eleven_monolingual_v1', voice_settings: { stability: 0.5, similarity_boost: 0.75 } }),
  });

  const data = await res.json();
  const apiTime = Date.now() - apiStart;

  // Extract audio (base64) and alignment data
  const audioBase64 = data.audio_base64;
  const alignment = data.alignment || {};
  const buffer = Buffer.from(audioBase64, 'base64');
  fs.writeFileSync(AUDIO, buffer);

  // Calculate exact audio duration and word-level timing from alignment
  const chars = alignment.characters || [];
  const starts = alignment.character_start_times_seconds || [];
  const ends = alignment.character_end_times_seconds || [];

  let exactDurationSec = 0;
  if (ends.length > 0) {
    exactDurationSec = ends[ends.length - 1];
  }

  // Build word-level timing for mouth animation
  const words = [];
  let currentWord = '';
  let wordStart = 0;
  for (let i = 0; i < chars.length; i++) {
    if (chars[i] === ' ' || i === chars.length - 1) {
      if (i === chars.length - 1 && chars[i] !== ' ') currentWord += chars[i];
      if (currentWord) {
        words.push({ w: currentWord, s: wordStart, e: ends[i === chars.length - 1 ? i : i - 1] });
      }
      currentWord = '';
      wordStart = starts[Math.min(i + 1, chars.length - 1)];
    } else {
      if (!currentWord) wordStart = starts[i];
      currentWord += chars[i];
    }
  }

  // Signal with exact duration + word timing from ElevenLabs timestamps
  fs.writeFileSync(SIGNAL, JSON.stringify({
    ts: Date.now(),
    chars: text.length,
    apiMs: apiTime,
    exactDurationSec: exactDurationSec,
    words: words,
  }));

  // Play with ffplay — use large buffer for smooth BT playback
  // Ensure ffplay is on PATH (install via your package manager)
  execSync(`ffplay -nodisp -autoexit -loglevel quiet -infbuf -framedrop "${AUDIO}"`, { timeout: 120000 });

  // Write done signal
  fs.writeFileSync(SIGNAL, 'DONE');

  // Cleanup
  try { fs.unlinkSync(AUDIO); } catch {}
})();
