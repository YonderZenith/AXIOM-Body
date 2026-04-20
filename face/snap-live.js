const path = require('path');
const puppeteer = require(path.resolve('C:/Users/ctt03/Desktop/hive-test/node_modules/puppeteer'));

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 400, height: 400, deviceScaleFactor: 2 });
  await page.goto('http://localhost:7897/face/web-face.html', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 600));
  const out = path.resolve(__dirname, '..', 'face-screenshots', 'ysmara-live.png');
  await page.screenshot({ path: out, clip: { x: 0, y: 0, width: 400, height: 400 } });
  const state = await page.evaluate(() => ({ mode: window.state?.mode, eye: window.state?.eye_state, people: window.state?.people_count, agent: window.state?.agent_name }));
  console.log('snap:', out, state);
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
