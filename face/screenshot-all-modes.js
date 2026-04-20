// Render web-face.html in every mode and screenshot each.
// Requires puppeteer — falls back to pulling from hive-test/node_modules.
const path = require('path');
const fs = require('fs');
const puppeteer = require(path.resolve('C:/Users/ctt03/Desktop/hive-test/node_modules/puppeteer'));

const PALETTE_AXIOM = {
  bg: [10, 10, 15],
  eye: [0, 212, 255],
  pupil: [200, 255, 255],
  mouth: [16, 185, 129],
  tongue: [220, 60, 90],
  listening_accent: [120, 220, 255],
  thinking_accent: [180, 140, 255],
  surprised_accent: [255, 220, 100],
};

function baseState() {
  return {
    schema_version: 2,
    agent_name: 'Axiom',
    agent_slug: 'axiom',
    mode: 'idle',
    prev_mode: 'idle',
    mode_age_ms: 200,
    mouth: 0,
    mouth_openness: 0.0,
    look_x: 0,
    look_y: 0,
    eye_state: 'open',
    expression: 'neutral',
    glow: 0.85,
    blink_phase: 0,
    listening_intensity: 0,
    active_word_end_ms: null,
    people_count: 0,
    scene_gaze: { x: 0, y: 0 },
    palette: PALETTE_AXIOM,
    tick_ms: Date.now(),
  };
}

const modes = [
  { name: 'idle',       overrides: { mode: 'idle', eye_state: 'open', expression: 'smile' } },
  { name: 'surprised',  overrides: { mode: 'surprised', eye_state: 'wide', expression: 'neutral', look_x: 2, look_y: -1, glow: 0.95, people_count: 1 } },
  { name: 'attentive',  overrides: { mode: 'attentive', eye_state: 'open', expression: 'neutral', look_x: 1, look_y: 0, people_count: 1 } },
  { name: 'curious',    overrides: { mode: 'curious', eye_state: 'half', look_x: -2, look_y: 1, glow: 0.7, people_count: 1 } },
  { name: 'tongue',     overrides: { mode: 'tongue', eye_state: 'squint', expression: 'smile', mouth_openness: 0.9, people_count: 1 } },
  { name: 'eye_tag',    overrides: { mode: 'eye_tag', eye_state: 'open', expression: 'neutral', look_x: 3, look_y: 0, people_count: 1 } },
  { name: 'listening',  overrides: { mode: 'listening', eye_state: 'wide', listening_intensity: 0.8, glow: 0.95, people_count: 1 } },
  { name: 'thinking',   overrides: { mode: 'thinking', eye_state: 'half', expression: 'neutral', look_x: -1, look_y: -1, people_count: 1 } },
  { name: 'speaking',   overrides: { mode: 'speaking', eye_state: 'open', expression: 'smile', mouth_openness: 0.8, active_word_end_ms: Date.now() + 200, people_count: 1 } },
  { name: 'sleep',      overrides: { mode: 'sleep', eye_state: 'closed', expression: 'smile', glow: 0.25, people_count: 0 } },
];

const STATE_PATH = path.join(__dirname, 'face-state.json');
const OUT_DIR = path.join(__dirname, '..', 'face-screenshots');

function writeState(overrides) {
  const s = Object.assign(baseState(), overrides);
  fs.writeFileSync(STATE_PATH, JSON.stringify(s));
}

(async () => {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 400, height: 400, deviceScaleFactor: 2 });

  writeState(modes[0].overrides);
  await page.goto('http://localhost:7897/web-face.html', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 400));

  for (const m of modes) {
    writeState(m.overrides);
    await new Promise(r => setTimeout(r, 350));
    const out = path.join(OUT_DIR, `mode-${m.name}.png`);
    await page.screenshot({ path: out, clip: { x: 0, y: 0, width: 400, height: 400 } });
    const rendered = await page.evaluate(() => {
      return { mode: window.state?.mode, standalone: window.standalone };
    }).catch(() => null);
    console.log(`  ${m.name.padEnd(11)} -> ${out}`);
  }

  await browser.close();
  console.log('\nDONE — 10 modes screenshot.');
})().catch(e => { console.error(e); process.exit(1); });
