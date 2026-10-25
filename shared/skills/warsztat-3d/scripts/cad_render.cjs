#!/usr/bin/env node
/**
 * Podgląd modelu GLB w przeglądarce (Chromium z obrazu Hermesa, WebGL na CPU przez SwiftShader): PNG albo klatki
 * filmu obrotu. Woła go cad.py (nie Ty):  node cad_render.cjs <zadanie.json>   → wynik JSON na stdout.
 *
 *   {"tryb": "png", "glb", "out", "w", "h", "kat", "wysokosc", "kolor", "tlo", "siatka", "krawedzie", "skala"}
 *   {"tryb": "obrot", "glb", "katalog", "klatek", ...}    → katalog/k00000.png … (360° w `klatek` krokach)
 *
 * Jedna przeglądarka: SwiftShader sam liczy na wszystkich rdzeniach (proces GPU ~260% CPU na 4 rdzeniach), więc
 * kilka przeglądarek naraz nie przyspiesza filmu (pomiar: 3 przeglądarki wolniej niż jedna).
 *
 * Strona (cad_podglad.html), Three.js (paczka `three` z /opt/jarvo/node) i model idą z adresu http://cad.jarvo/
 * podanego przez page.route; każdy inny adres jest odrzucany, więc podgląd nie wychodzi do sieci.
 */
const fs = require('fs');
const path = require('path');

function playwright() {
  for (const name of [process.env.CAD_PLAYWRIGHT, 'playwright-core', 'playwright'].filter(Boolean)) {
    try { return require(name); } catch (e) { /* następny */ }
  }
  throw new Error('brak playwright-core (Node); w kontenerze Jarva jest w obrazie');
}

function browserPath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const f = '/etc/hermes/agent-browser-executable-path';
  return fs.existsSync(f) ? fs.readFileSync(f, 'utf8').trim() || undefined : undefined;
}

function threeRoot() {
  // paczka three nie wystawia package.json w `exports`: katalog paczki z pliku głównego
  let p;
  try { p = path.dirname(require.resolve('three')); } catch (e) {
    throw new Error('brak paczki three (Node); w kontenerze Jarva jest w /opt/jarvo/node');
  }
  while (!fs.existsSync(path.join(p, 'package.json')) && path.dirname(p) !== p) p = path.dirname(p);
  return p;
}

const TYPY = { '.js': 'text/javascript', '.html': 'text/html', '.glb': 'model/gltf-binary' };
const ARGS = ['--enable-webgl', '--ignore-gpu-blocklist', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'];

// Piaskownica Chromium tam, gdzie działa (jak cad_render.py i audit.py Weba): bez niej tylko na Linuksie jako root,
// w kontenerze Dockera (obraz Jarva: jak dotąd --no-sandbox) albo z zakazem przestrzeni nazw użytkownika bez profilu
// AppArmor (Ubuntu 23.10+). Playwright domyślnie sam dodaje --no-sandbox, więc chromiumSandbox ustawiamy jawnie.
function bezPiaskownicy() {
  if (process.platform !== 'linux') return false;
  const czytaj = (p) => { try { return fs.readFileSync(p, 'utf8'); } catch (e) { return ''; } };
  return (process.getuid && process.getuid() === 0) || fs.existsSync('/.dockerenv')
    || czytaj('/proc/sys/kernel/apparmor_restrict_unprivileged_userns').trim() === '1';
}

async function strona(browser, z, bledy) {
  const three = threeRoot();
  const page = await browser.newPage({ viewport: { width: z.w, height: z.h }, deviceScaleFactor: z.skala || 1 });
  page.on('pageerror', e => bledy.push(String(e.message || e)));
  page.on('console', m => { if (m.type() === 'error') bledy.push(m.text()); });
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.host !== 'cad.jarvo') return route.abort();
    let plik = null;
    if (u.pathname === '/') plik = path.join(__dirname, 'cad_podglad.html');
    else if (u.pathname === '/model.glb') plik = z.glb;
    else if (u.pathname.startsWith('/three/')) {
      const p = path.resolve(three, '.' + decodeURIComponent(u.pathname.slice('/three'.length)));
      if (p.startsWith(three + path.sep)) plik = p;
    }
    if (!plik || !fs.existsSync(plik)) return route.fulfill({ status: 404, body: 'brak' });
    return route.fulfill({ status: 200, body: fs.readFileSync(plik),
                           contentType: TYPY[path.extname(plik)] || 'application/octet-stream' });
  });
  const opcje = { w: z.w, h: z.h, kat: z.kat, wysokosc: z.wysokosc, kolor: z.kolor, tlo: z.tlo, siatka: z.siatka,
                  krawedzie: z.krawedzie, skala: z.skala, obrot: z.tryb === 'obrot' };
  await page.addInitScript(o => { window.__opcje = o; }, opcje);
  await page.goto('http://cad.jarvo/', { waitUntil: 'load' });
  try {
    await page.waitForFunction('window.__ready === true', null, { timeout: 120000 });
  } catch (e) {
    throw new Error(`podgląd się nie wczytał: ${[...new Set(bledy)].join('; ') || e.message}`);
  }
  return page;
}

(async () => {
  const z = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const { chromium } = playwright();
  const bez = bezPiaskownicy();
  const browser = await chromium.launch({ executablePath: browserPath(), args: bez ? ['--no-sandbox', ...ARGS] : ARGS,
                                          chromiumSandbox: !bez });
  const bledy = [];
  try {
    const page = await strona(browser, z, bledy);
    const info = await page.evaluate(() => window.__info);
    const t0 = Date.now();
    let wynik;
    if (z.tryb === 'png') {
      await page.screenshot({ path: z.out, omitBackground: !z.tlo });
      wynik = { plik: z.out };
    } else if (z.tryb === 'obrot') {
      for (let i = 0; i < z.klatek; i++) {
        await page.evaluate(k => window.__ustaw(k), z.kat + 360 * i / z.klatek);
        await page.screenshot({ path: path.join(z.katalog, `k${String(i).padStart(5, '0')}.png`) });
      }
      wynik = { katalog: z.katalog };
    } else {
      throw new Error(`nieznany tryb ${z.tryb}`);
    }
    console.log(JSON.stringify({ ...wynik, info, render_s: (Date.now() - t0) / 1000, bledy: [...new Set(bledy)] }));
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(String(e.message || e)); process.exit(1); });
