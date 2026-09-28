#!/usr/bin/env node
/**
 * Testy „wrogie” strony: warunki, w których strona zwykle się sypie, a zwykły zrzut tego nie pokaże.
 *
 *   node hostile.cjs <url> <outdir> [--only slow3g,offline,...]
 *
 * Scenariusze (każdy: co robi, czego oczekujemy, co znaczy porażka):
 *   slow3g      wolne łącze (~400 kb/s, 400 ms RTT): czas do treści i czy treść w ogóle się pojawia
 *   offline     zasoby z innych serwerów zablokowane (CDN, fonty, skrypty): czy strona dalej działa sama
 *   nojs        JavaScript wyłączony: czy widać treść (nagłówek i tekst), a nie pustą stronę
 *   zoom200     szerokość 320 px CSS (= 1280 px przy powiększeniu 400% / 640 px przy 200%): poziome przewijanie (WCAG 1.4.10)
 *   keyboard    tylko Tab: czy fokus jest widoczny i czy każdy link/przycisk jest osiągalny
 *   longwords   długie polskie słowa i pełne diakrytyki w nagłówkach i akapitach: czy tekst nie wychodzi poza ekran
 *   reducedmotion  prefers-reduced-motion: czy animacje CSS się wyłączają
 *   console     błędy konsoli i nieudane żądania przy zwykłym wejściu (375 px)
 *
 * Używa playwright-core z Chromium z obrazu (jak screenshots.cjs). Wynik: <outdir>/hostile.json + zrzuty.
 * Strony nie zmienia (longwords podmienia tekst tylko w kopii w przeglądarce).
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const ALL = ['console', 'slow3g', 'offline', 'nojs', 'zoom200', 'keyboard', 'longwords', 'reducedmotion'];
const LONG_WORD = 'Konstantynopolitańczykowianeczka';
const DIACRITICS = 'Zażółć gęślą jaźń. ŻÓŁĆ GĘŚLĄ JAŹŃ.';

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
}

function browserPath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const f = '/etc/hermes/agent-browser-executable-path';
  if (fs.existsSync(f)) return fs.readFileSync(f, 'utf8').trim();
  return undefined;
}

// elementy wychodzące poza szerokość okna (jak w screenshots.cjs)
// + elementy, z których wylewa się tekst (pudełko ma szerokość ekranu, a słowo z niego wystaje)
const OVERFLOW = () => {
  const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '');
  const all = [...document.querySelectorAll('body *')];
  return {
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    overflowing: all.filter((el) => el.getBoundingClientRect().right > window.innerWidth + 1).slice(0, 8).map(name),
    text_spilling: all.filter((el) => el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX === 'visible'
      && el.clientWidth > 0).slice(0, 8).map(name),
  };
};

const TEXT = () => {
  const h = document.querySelector('h1, h2');
  const body = (document.body && document.body.innerText) || '';
  return { heading: h ? h.innerText.trim().slice(0, 80) : '', chars: body.trim().length };
};

async function run(browser, name, url, outdir) {
  // zrzut pomocniczy: jego brak (np. strona błędu Chromium offline) nie jest wynikiem scenariusza
  const shot = (page, suffix = '') => page.screenshot({ path: path.join(outdir, `${name}${suffix}.png`) }).catch(() => null);
  const r = { scenario: name, pass: false, observed: {}, broken: '' };
  if (name === 'console') {
    const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
    const errors = [], failed = [], notes = [];
    page.on('console', (m) => {
      if (m.type() !== 'error') return;
      const src = (m.location() && m.location().url) || '';
      // przeglądarka sama pyta o /favicon.ico; brak faviconu to uwaga (rubryka „head”), nie błąd strony
      if (/\/favicon\.ico(\?|$)/.test(src)) { notes.push('brak /favicon.ico (przeglądarka pyta sama)'); return; }
      errors.push(m.text().slice(0, 200) + (src ? ` [${src.slice(0, 100)}]` : ''));
    });
    page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 200)));
    page.on('requestfailed', (q) => failed.push(`${q.failure() ? q.failure().errorText : '?'} ${q.url().slice(0, 120)}`));
    page.on('response', (s) => { if (s.status() >= 400) failed.push(`${s.status()} ${s.url().slice(0, 120)}`); });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    r.observed = { console_errors: errors.slice(0, 10), failed_requests: failed.slice(0, 10), notes };
    r.pass = errors.length === 0 && failed.length === 0;
    r.broken = r.pass ? '' : 'błędy w konsoli albo nieudane żądania (zasoby 404, CORS)';
    await page.close();
  } else if (name === 'slow3g') {
    const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 400, downloadThroughput: 50 * 1024, uploadThroughput: 25 * 1024 });
    const t0 = Date.now();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 });
    const dcl = Date.now() - t0;
    let firstText = null;
    for (let i = 0; i < 60 && firstText === null; i++) {
      const t = await page.evaluate(TEXT);
      if (t.chars > 40) firstText = Date.now() - t0; else await page.waitForTimeout(250);
    }
    await shot(page);
    r.observed = { dom_ready_ms: dcl, text_visible_ms: firstText };
    r.pass = firstText !== null && firstText < 8000;
    r.broken = r.pass ? '' : 'na wolnym łączu treść nie pojawia się w 8 s (blokujące skrypty, fonty bez fallbacku, ciężki hero)';
    await page.close();
  } else if (name === 'offline') {
    // „działa offline / jako jeden plik”: strona nie może niczego ciągnąć z innych serwerów (CDN, fonty, skrypty)
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const page = await ctx.newPage();
    const origin = new URL(url).origin;
    const external = [];
    await page.route('**/*', (route) => {
      const u = route.request().url();
      if (/^(data|blob):/.test(u) || u.startsWith(origin)) return route.continue();
      external.push(u.slice(0, 120));
      return route.abort();
    });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    const t = await page.evaluate(TEXT);
    await shot(page);
    r.observed = { external_requests_blocked: external.slice(0, 10), heading: t.heading, chars: t.chars };
    r.pass = external.length === 0 && t.chars > 40;
    r.broken = r.pass ? '' : 'strona ciągnie zasoby z innych serwerów (CDN, Google Fonts, skrypty): bez internetu wygląd albo działanie się rozsypie';
    // istotne, gdy DoD mówi „offline”, „jeden plik”, „bez zależności zewnętrznych”; inaczej informacja
    r.info_only = true;
    await ctx.close();
  } else if (name === 'nojs') {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: 'load', timeout: 60000 });
    const t = await page.evaluate(TEXT);
    await shot(page);
    r.observed = t;
    r.pass = t.chars > 80 && t.heading.length > 0;
    r.broken = r.pass ? '' : 'bez JavaScriptu strona jest pusta: treść renderowana tylko w JS szkodzi SEO i dostępności';
    await ctx.close();
  } else if (name === 'zoom200') {
    const page = await browser.newPage({ viewport: { width: 320, height: 640 } });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    const m = await page.evaluate(OVERFLOW);
    await shot(page);
    r.observed = m;
    r.pass = m.scrollWidth <= m.innerWidth + 1;
    r.broken = r.pass ? '' : 'przy 320 px CSS (powiększenie) pojawia się poziome przewijanie';
    await page.close();
  } else if (name === 'keyboard') {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    const total = await page.evaluate(() => [...document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])')]
      .filter((el) => { const s = getComputedStyle(el); const b = el.getBoundingClientRect(); return s.visibility !== 'hidden' && s.display !== 'none' && b.width > 0 && b.height > 0; }).length);
    const seen = new Set(); let noRing = []; let steps = 0;
    for (; steps < Math.min(total + 5, 200); steps++) {
      await page.keyboard.press('Tab');
      const f = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const s = getComputedStyle(el);
        const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none';
        return { key: el.tagName.toLowerCase() + ':' + (el.getAttribute('href') || el.id || el.textContent.trim().slice(0, 30)), ring };
      });
      if (!f) continue;
      if (seen.has(f.key)) break;
      seen.add(f.key);
      if (!f.ring) noRing.push(f.key);
    }
    r.observed = { focusable: total, reached_by_tab: seen.size, without_visible_focus: noRing.slice(0, 10) };
    r.pass = seen.size >= total && noRing.length === 0;
    r.broken = r.pass ? '' : 'nie każdy element jest osiągalny Tabem albo fokus jest niewidoczny (outline: none bez zamiennika)';
    await page.close();
  } else if (name === 'longwords') {
    const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.evaluate(([w, d]) => {
      document.querySelectorAll('h1, h2, h3, p, li, a, button').forEach((el, i) => {
        if (i > 60 || el.children.length > 0) return;
        el.textContent = (i % 2 ? d + ' ' : '') + w + ' ' + el.textContent;
      });
    }, [LONG_WORD, DIACRITICS]);
    const m = await page.evaluate(OVERFLOW);
    await shot(page);
    r.observed = m;
    r.pass = m.scrollWidth <= m.innerWidth + 1;
    r.broken = r.pass ? '' : 'długie polskie słowo rozpycha układ: brak overflow-wrap/hyphens (lang="pl") w nagłówkach albo przyciskach';
    await page.close();
  } else if (name === 'reducedmotion') {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    const running = await page.evaluate(() => (document.getAnimations ? document.getAnimations() : [])
      .filter((a) => a.playState === 'running' && (a.effect && a.effect.getTiming().iterations === Infinity || (a.effect && a.effect.getTiming().duration > 300)))
      .map((a) => (a.effect && a.effect.target ? a.effect.target.tagName.toLowerCase() : '?') + ':' + (a.animationName || a.id || 'anim')).slice(0, 10));
    r.observed = { running_long_or_infinite: running };
    r.pass = running.length === 0;
    r.broken = r.pass ? '' : 'przy prefers-reduced-motion nadal kręcą się długie albo nieskończone animacje';
    await ctx.close();
  }
  return r;
}

(async () => {
  const [url, outdir] = process.argv.slice(2).filter((a) => !a.startsWith('--') && a !== arg('--only'));
  if (!url || !outdir) {
    console.error('Użycie: node hostile.cjs <url> <outdir> [--only ' + ALL.join(',') + ']');
    process.exit(2);
  }
  const only = arg('--only', '') ? arg('--only').split(',') : ALL;
  fs.mkdirSync(outdir, { recursive: true });
  const browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox'] });
  const results = [];
  try {
    for (const name of only.filter((n) => ALL.includes(n))) {
      try {
        results.push(await run(browser, name, url, outdir));
      } catch (e) {
        results.push({ scenario: name, pass: false, error: e.message.split('\n')[0].slice(0, 200), broken: 'scenariusz nie wykonał się (to nie jest wynik strony)' });
      }
    }
  } finally {
    await browser.close();
  }
  const report = { url, results };
  fs.writeFileSync(path.join(outdir, 'hostile.json'), JSON.stringify(report, null, 1));
  const failed = results.filter((x) => !x.pass && !x.info_only && !x.error).map((x) => x.scenario);
  const info = results.filter((x) => !x.pass && x.info_only).map((x) => x.scenario);
  const errors = results.filter((x) => x.error).map((x) => x.scenario);
  console.log(JSON.stringify({ ok: failed.length === 0 && errors.length === 0, failed, info, not_run: errors, outdir }, null, 1));
})().catch((e) => { console.error(e.message); process.exit(1); });
