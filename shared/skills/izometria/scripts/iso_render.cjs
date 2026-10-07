#!/usr/bin/env node
/**
 * Figury iso-glow w przeglądarce (Chromium z obrazu Hermesa): PNG w chwili t i kontrola każdej figury.
 * Woła go iso.py (nie Ty):  node iso_render.cjs <zadanie.json>   → wynik JSON na stdout.
 *
 *   {"tryb": "png", "zadania": [{"url", "out", "w", "h", "skala", "czas", "alfa"}]}
 *   {"tryb": "sprawdz", "url", "czas", "w", "h"}   (url z ?render=1; każda figura osobno, z demo)
 *
 * Czas to czas strony (zegar wirtualny z iso_jarvo.js: window.__seek), nie ściany, więc zrzut zawsze ten sam.
 */
const fs = require('fs');

function playwright() {
  for (const name of [process.env.ISO_PLAYWRIGHT, 'playwright-core', 'playwright'].filter(Boolean)) {
    try { return require(name); } catch (e) { /* następny */ }
  }
  throw new Error('brak playwright-core (Node); w kontenerze Jarva jest w obrazie');
}

function browserPath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const f = '/etc/hermes/agent-browser-executable-path';
  return fs.existsSync(f) ? fs.readFileSync(f, 'utf8').trim() || undefined : undefined;
}

const RAF2 = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

async function otworz(browser, url, w, h, skala, bledy) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: skala || 1 });
  page.on('pageerror', e => bledy.push(String(e.message || e)));
  page.on('console', m => { if (m.type() === 'error') bledy.push(m.text()); });
  page.on('requestfailed', r => { if (!r.url().startsWith('data:')) bledy.push(`nie wczytano ${r.url()}`); });
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction('window.__ready === true', null, { timeout: 30000 });
  return page;
}

async function png(browser, zadania) {
  const pliki = [], bledy = [];
  for (const z of zadania) {
    const page = await otworz(browser, z.url, z.w, z.h, z.skala, bledy);
    await page.evaluate(t => window.__seek(t), z.czas || 0);
    await page.evaluate(RAF2);
    await page.screenshot({ path: z.out, omitBackground: !!z.alfa });
    await page.close();
    pliki.push(z.out);
  }
  return { pliki, bledy: [...new Set(bledy)] };
}

const POMIAR = () => {
  const svg = document.getElementById('stage');
  if (!svg) return { elementow: 0, tekstow: [], poza: [] };
  const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
  // obszar rysunku w svg (viewBox dopasowany środkiem: meet)
  const s = Math.min(r.width / vb.width, r.height / vb.height);
  const x0 = r.left + (r.width - vb.width * s) / 2, y0 = r.top + (r.height - vb.height * s) / 2;
  const kadr = { l: x0 - 1, t: y0 - 1, r: x0 + vb.width * s + 1, b: y0 + vb.height * s + 1 };
  const teksty = [...svg.querySelectorAll('text')].filter(t => t.textContent.trim());
  const poza = teksty.filter(t => { const b = t.getBoundingClientRect();
    return b.width && (b.left < kadr.l || b.top < kadr.t || b.right > kadr.r || b.bottom > kadr.b); })
    .map(t => t.textContent.trim().slice(0, 40));
  // wysokość kroju na ekranie: rozmiar × skala płaszczyzny (ściana izometryczna ściska i skośnie kładzie tekst)
  const rozmiary = teksty.map(t => { const m = t.getScreenCTM(); if (!m) return 0;
    return parseFloat(getComputedStyle(t).fontSize) * Math.sqrt(Math.abs(m.a * m.d - m.b * m.c)); }).filter(Boolean);
  return {
    elementow: svg.querySelectorAll('*').length,
    tekstow: teksty.length,
    najmniejszy_tekst_px: rozmiary.length ? Math.round(Math.min(...rozmiary) * 10) / 10 : null,
    poza,
    swieci: svg.querySelectorAll('.hot, .lit, .latched, .go').length,
    aria: svg.getAttribute('aria-label') || '',
    odczyt: (document.getElementById('readout') || {}).textContent || '',
  };
};

async function sprawdz(browser, z) {
  const bledyStartu = [];
  const page = await otworz(browser, z.url, z.w || 1600, z.h || 1200, 1, bledyStartu);
  const figury = await page.evaluate(() => (window.__isoFigury ? window.__isoFigury() : []));
  await page.close();
  const wynik = { figury: [], bledy: [...new Set(bledyStartu)] };
  for (const f of figury) {
    const bledy = [];
    const sep = z.url.includes('?') ? '&' : '?';
    const url = z.url.replace(/#.*$/, '') + `${sep}demo=1&figura=${encodeURIComponent(f.id)}`;
    const p = await otworz(browser, url, z.w || 1600, z.h || 1200, 1, bledy);
    const start = await p.evaluate(POMIAR);
    await p.evaluate(t => window.__seek(t), z.czas || 3);
    await p.evaluate(RAF2);
    const po = await p.evaluate(POMIAR);
    bledy.push(...(await p.evaluate(() => window.__isoBledy || [])));
    await p.close();
    wynik.figury.push({ id: f.id, nazwa: f.name, start, po_demo: po, bledy: [...new Set(bledy)] });
  }
  return wynik;
}

(async () => {
  const z = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const { chromium } = playwright();
  const browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox'] });
  try {
    const out = z.tryb === 'png' ? await png(browser, z.zadania) : await sprawdz(browser, z);
    process.stdout.write(JSON.stringify(out) + '\n');
  } finally {
    await browser.close();
  }
})().catch(e => { process.stderr.write(`iso_render: ${e.message || e}\n`); process.exit(1); });
