#!/usr/bin/env node
/**
 * Render grafiki HTML/CSS do PNG w dokładnych wymiarach (Chromium z obrazu Hermesa albo natywnie chrome-headless-shell
 * z instalacji Jarva: CHROME_PATH; playwright-core z NODE_PATH narzędzi npm floty).
 *
 *   node render_html.cjs <plik.html> <out-prefix> --size 1080x1350 [--size 1080x1920 ...] [--scale 1]
 *
 * Wynik: <out-prefix>-<szer>x<wys>.png dla każdego rozmiaru (ścieżki z „/” także na Windows). Czeka na fonty
 * (document.fonts.ready).
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

// Piaskownica Chromium tam, gdzie działa (jak cad_render.cjs i audit.py): bez niej tylko Linux jako root, w kontenerze
// albo z zakazem przestrzeni nazw użytkownika bez profilu AppArmor (Ubuntu 23.10+). Windows i macOS (instalacja
// natywna): z piaskownicą. playwright-core sam dodaje --no-sandbox, gdy chromiumSandbox nie jest true, więc o
// piaskownicy decyduje jawne chromiumSandbox, a nie sama lista argumentów.
function bezPiaskownicy() {
  if (process.platform !== 'linux') return false;
  const czytaj = (p) => { try { return fs.readFileSync(p, 'utf8'); } catch { return ''; } };
  return Boolean((process.getuid && process.getuid() === 0) || fs.existsSync('/.dockerenv')
    || czytaj('/proc/1/cgroup').includes('docker')
    || czytaj('/proc/sys/kernel/apparmor_restrict_unprivileged_userns').trim() === '1');
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
  const bez = bezPiaskownicy();
  const browser = await chromium.launch({ executablePath: browserPath(), args: bez ? ['--no-sandbox'] : [],
                                          chromiumSandbox: !bez });
  const outputs = [];
  try {
    for (const s of sizes) {
      const [w, h] = s.toLowerCase().split('x').map(Number);
      const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: scale });
      await page.goto(pathToFileURL(path.resolve(input)).href, { waitUntil: 'networkidle' });
      await page.evaluate(() => document.fonts && document.fonts.ready);
      const file = `${prefix}-${w}x${h}.png`;
      await page.screenshot({ path: file, clip: { x: 0, y: 0, width: w, height: h } });
      outputs.push({ file: file.split(path.sep).join('/'), width: w * scale, height: h * scale,
                     bytes: fs.statSync(file).size });
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ok: true, outputs }, null, 1));
})().catch((e) => { console.error(e.message); process.exit(1); });
