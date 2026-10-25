#!/usr/bin/env node
/**
 * Nagranie ruchu strony do HAR (wywołuje go `zrodlo.py nagraj`, który najpierw sprawdza robots.txt).
 *
 *   node har.cjs <url> <plik.har> [--czekaj 3000] [--przewin]
 *
 * Chromium z CHROME_PATH (chrome-headless-shell z instalacji; w obrazie Hermesa zapasowo z /etc/hermes),
 * playwright-core z NODE_PATH; bez obrazków, fontów i multimediów.
 * User-Agent uczciwy (JARVO_UA od zrodlo.py: jarvo-lowca). Odmowa (401/403/429/503) albo strona ochrony
 * antybotowej = kod 3: to blokada, nie zagadka; nie obchodzimy jej.
 */
const fs = require('fs');
const { chromium } = require('playwright-core');

const Z_WARTOSCIA = new Set(['--czekaj']);

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
}

function pozycyjne() {
  const a = process.argv.slice(2);
  return a.filter((x, i) => !x.startsWith('--') && !(i > 0 && Z_WARTOSCIA.has(a[i - 1])));
}

function browserPath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const f = '/etc/hermes/agent-browser-executable-path';
  if (fs.existsSync(f)) return fs.readFileSync(f, 'utf8').trim();
  return undefined; // playwright-core spróbuje domyślnej instalacji
}

// --no-sandbox tylko tam, gdzie piaskownica Chromium nie ruszy (jak audit.py i Hermes): Linux jako root, w kontenerze
// albo z zakazem przestrzeni nazw użytkownika bez profilu AppArmor (Ubuntu 23.10+). Windows i macOS: z piaskownicą.
function argsPiaskownicy() {
  if (process.platform !== 'linux') return [];
  const czytaj = (p) => { try { return fs.readFileSync(p, 'utf8'); } catch { return ''; } };
  const bez = (process.getuid && process.getuid() === 0) || fs.existsSync('/.dockerenv')
    || czytaj('/proc/1/cgroup').includes('docker')
    || czytaj('/proc/sys/kernel/apparmor_restrict_unprivileged_userns').trim() === '1';
  return bez ? ['--no-sandbox'] : [];
}

(async () => {
  const [url, out] = pozycyjne();
  if (!url || !out) {
    console.error('Użycie: node har.cjs <url> <plik.har> [--czekaj 3000] [--przewin]');
    process.exit(2);
  }
  const browser = await chromium.launch({ executablePath: browserPath(), args: argsPiaskownicy() });
  const ctx = await browser.newContext({
    userAgent: process.env.JARVO_UA || 'Mozilla/5.0 (compatible; jarvo-lowca/1.0; +https://jarvo.pl)',
    locale: 'pl-PL',
    recordHar: { path: out, content: 'embed' },
  });
  await ctx.route('**/*', (r) => (['image', 'font', 'media'].includes(r.request().resourceType()) ? r.abort() : r.continue()));
  const page = await ctx.newPage();
  let kod = 0;
  try {
    const odp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    const st = odp ? odp.status() : 0;
    const tytul = await page.title().catch(() => '');
    if ([401, 403, 429, 503].includes(st) || /captcha|access denied|attention required|just a moment|dost[eę]p zablokowany/i.test(tytul)) {
      console.error(`✗ blokada: ${url} odpowiedział ${st} „${tytul}”; nie obchodzimy ochrony, zgłoś blokadę`);
      kod = 3;
    } else {
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
      if (process.argv.includes('--przewin')) {
        for (let i = 0; i < 6; i++) {
          await page.mouse.wheel(0, 1500);
          await page.waitForTimeout(600);
        }
      }
      await page.waitForTimeout(Number(arg('--czekaj', 3000)));
    }
  } catch (e) {
    console.error(`✗ ${url}: ${String(e.message).split('\n')[0]}`);
    kod = 1;
  }
  await ctx.close(); // HAR zapisuje się przy zamknięciu kontekstu
  await browser.close();
  if (!kod) {
    const n = JSON.parse(fs.readFileSync(out, 'utf8')).log.entries.length;
    console.log(`✓ ${out}: ${n} żądań`);
  }
  process.exit(kod);
})();
