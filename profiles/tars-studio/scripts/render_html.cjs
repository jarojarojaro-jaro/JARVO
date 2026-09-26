#!/usr/bin/env node
/**
 * Render grafiki HTML/CSS do PNG w dokładnych wymiarach (Chromium z obrazu Hermesa).
 *
 *   node render_html.cjs <plik.html> <out-prefix> --size 1080x1350 [--size 1080x1920 ...] [--scale 1]
 *
 * Wynik: <out-prefix>-<szer>x<wys>.png dla każdego rozmiaru. Czeka na fonty (document.fonts.ready).
 */
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('playwright-core');

function browserPath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const f = '/etc/hermes/agent-browser-executable-path';
  return fs.existsSync(f) ? fs.readFileSync(f, 'utf8').trim() : undefined;
}

(async () => {
  const args = process.argv.slice(2);
  const sizes = [];
  let scale = 1;
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--size') sizes.push(args[++i]);
    else if (args[i] === '--scale') scale = Number(args[++i]);
    else positional.push(args[i]);
  }
  const [input, prefix] = positional;
  if (!input || !prefix || !sizes.length) {
    console.error('Użycie: node render_html.cjs <plik.html> <out-prefix> --size 1080x1350 [--size ...]');
    process.exit(2);
  }
  fs.mkdirSync(path.dirname(path.resolve(prefix)), { recursive: true });
  const browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox'] });
  const outputs = [];
  try {
    for (const s of sizes) {
      const [w, h] = s.toLowerCase().split('x').map(Number);
      const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: scale });
      await page.goto(pathToFileURL(path.resolve(input)).href, { waitUntil: 'networkidle' });
      await page.evaluate(() => document.fonts && document.fonts.ready);
      const file = `${prefix}-${w}x${h}.png`;
      await page.screenshot({ path: file, clip: { x: 0, y: 0, width: w, height: h } });
      outputs.push({ file, width: w * scale, height: h * scale, bytes: fs.statSync(file).size });
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ok: true, outputs }, null, 1));
})().catch((e) => { console.error(e.message); process.exit(1); });
