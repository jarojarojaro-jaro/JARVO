#!/usr/bin/env node
/**
 * Zrzuty strony na wielu szerokościach + wykrywanie poziomego przewijania.
 *
 *   node screenshots.cjs <url> <outdir> [--widths 375,768,1440] [--full]
 *
 * Używa playwright-core z przeglądarką Chromium z obrazu Hermesa
 * (/etc/hermes/agent-browser-executable-path) albo CHROME_PATH.
 * Wynik: <outdir>/<szerokość>.png + <outdir>/screenshots.json
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
}

function browserPath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const f = '/etc/hermes/agent-browser-executable-path';
  if (fs.existsSync(f)) return fs.readFileSync(f, 'utf8').trim();
  return undefined; // playwright-core spróbuje domyślnej instalacji
}

(async () => {
  const [url, outdir] = process.argv.slice(2).filter((a) => !a.startsWith('--'));
  if (!url || !outdir) {
    console.error('Użycie: node screenshots.cjs <url> <outdir> [--widths 375,768,1440] [--full]');
    process.exit(2);
  }
  const widths = arg('--widths', '375,768,1440').split(',').map(Number);
  const full = process.argv.includes('--full');
  fs.mkdirSync(outdir, { recursive: true });
  const browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox'] });
  const report = { url, results: [] };
  try {
    for (const width of widths) {
      const page = await browser.newPage({ viewport: { width, height: width < 800 ? 812 : 900 }, deviceScaleFactor: 1 });
      const t0 = Date.now();
      const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
      const metrics = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
        title: document.title,
        overflowing: [...document.querySelectorAll('body *')]
          .filter((el) => el.getBoundingClientRect().right > window.innerWidth + 1)
          .slice(0, 10)
          .map((el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '')),
      }));
      const file = path.join(outdir, `${width}.png`);
      await page.screenshot({ path: file, fullPage: full });
      report.results.push({
        width, file, status: resp ? resp.status() : null, load_ms: Date.now() - t0,
        horizontal_scroll: metrics.scrollWidth > metrics.innerWidth + 1,
        scroll_width: metrics.scrollWidth, overflowing_elements: metrics.overflowing, title: metrics.title,
      });
      await page.close();
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(path.join(outdir, 'screenshots.json'), JSON.stringify(report, null, 1));
  const bad = report.results.filter((r) => r.horizontal_scroll).map((r) => r.width);
  console.log(JSON.stringify({ ok: bad.length === 0, horizontal_scroll_at: bad, outdir }, null, 1));
})().catch((e) => { console.error(e.message); process.exit(1); });
