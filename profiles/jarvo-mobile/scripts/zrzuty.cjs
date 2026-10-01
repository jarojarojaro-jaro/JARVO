#!/usr/bin/env node
/**
 * Zrzuty wersji webowej aplikacji w profilach telefonów + kontrole na każdym ekranie.
 *
 *   node zrzuty.cjs <url-bazowy> <outdir> [--trasy /,/wiecej] [--urzadzenia iphone,pixel] [--motywy jasny,ciemny]
 *
 * Profile: iPhone 17 Pro Max (440×956 @3 = 1320×2868, rozmiar zrzutów App Store 6,9″) i Pixel (412×915 @2,625).
 * Kontrole: błędy konsoli i strony, poziome przewijanie, cele dotyku mniejsze niż 44 px (przyciski, linki, zakładki),
 * axe-core (kontrast, etykiety, role). Wynik: <outdir>/<urządzenie>-<motyw>/<trasa>.png i <outdir>/zrzuty.json.
 * To wersja webowa (react-native-web): kontrole natywne (czcionka systemowa, przycisk wstecz, uprawnienia) robi bramka
 * aplikacji na urządzeniu. Kod 1, gdy są błędy konsoli albo poziome przewijanie.
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const URZADZENIA = {
  iphone: { nazwa: 'iPhone 17 Pro Max', viewport: { width: 440, height: 956 }, deviceScaleFactor: 3,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1' },
  pixel: { nazwa: 'Pixel 9', viewport: { width: 412, height: 915 }, deviceScaleFactor: 2.625,
    userAgent: 'Mozilla/5.0 (Linux; Android 16; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36' },
};

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

const nazwaPliku = (trasa) => (trasa === '/' ? 'start' : trasa.replace(/^\//, '').replace(/[^\w-]+/g, '_'));

(async () => {
  const poz = [];
  for (let i = 2; i < process.argv.length; i++) { if (process.argv[i].startsWith('--')) i++; else poz.push(process.argv[i]); }
  const [baza, outdir] = poz;
  if (!baza || !outdir) {
    console.error('Użycie: node zrzuty.cjs <url-bazowy> <outdir> [--trasy /,/wiecej] [--urzadzenia iphone,pixel] [--motywy jasny,ciemny]');
    process.exit(2);
  }
  const trasy = arg('--trasy', '/').split(',').filter(Boolean);
  const urzadzenia = arg('--urzadzenia', 'iphone,pixel').split(',').filter((u) => URZADZENIA[u]);
  const motywy = arg('--motywy', 'jasny,ciemny').split(',');
  const axePath = (() => { try { return require.resolve('axe-core/axe.min.js'); } catch { return null; } })();
  const browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox'] });
  const wyniki = [];
  try {
    for (const u of urzadzenia) {
      for (const motyw of motywy) {
        const d = URZADZENIA[u];
        const ctx = await browser.newContext({ viewport: d.viewport, deviceScaleFactor: d.deviceScaleFactor, isMobile: true,
          hasTouch: true, userAgent: d.userAgent, locale: 'pl-PL', colorScheme: motyw === 'ciemny' ? 'dark' : 'light' });
        const katalog = path.join(outdir, `${u}-${motyw}`);
        fs.mkdirSync(katalog, { recursive: true });
        for (const trasa of trasy) {
          const page = await ctx.newPage();
          const bledy = [];
          page.on('console', (m) => { if (m.type() === 'error') bledy.push(m.text().slice(0, 300)); });
          page.on('pageerror', (e) => bledy.push(String(e).slice(0, 300)));
          const url = baza.replace(/\/$/, '') + trasa;
          let status = null;
          try {
            const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
            status = resp ? resp.status() : null;
          } catch (e) { bledy.push(`nie wczytano: ${String(e).slice(0, 200)}`); }
          await page.waitForTimeout(1200);
          const plik = path.join(katalog, `${nazwaPliku(trasa)}.png`);
          await page.screenshot({ path: plik });
          const dom = await page.evaluate(() => {
            const widoczny = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
              return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
            const cele = [...document.querySelectorAll('[role=button],[role=link],[role=tab],a[href],button,input,select,textarea')]
              .filter(widoczny)
              .map((el) => { const r = el.getBoundingClientRect(); return { tekst: (el.innerText || el.getAttribute('aria-label') || el.tagName).trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) }; })
              .filter((c) => c.w < 44 || c.h < 44);
            return { przewijanie: document.documentElement.scrollWidth > window.innerWidth + 1,
              tekst: (document.body.innerText || '').trim().length, male_cele: cele.slice(0, 10), malych_celow: cele.length };
          });
          let axe = null;
          if (axePath) {
            try {
              await page.addScriptTag({ path: axePath });
              axe = await page.evaluate(async () => {
                const r = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag22aa'] } });
                return r.violations.map((v) => ({ id: v.id, wplyw: v.impact, wezly: v.nodes.length, opis: v.help }));
              });
            } catch (e) { axe = [{ id: 'axe-blad', wplyw: null, wezly: 0, opis: String(e).slice(0, 200) }]; }
          }
          wyniki.push({ urzadzenie: d.nazwa, motyw, trasa, url, status, plik, bledy, pusty: dom.tekst === 0, ...dom, axe });
          await page.close();
        }
        await ctx.close();
      }
    }
  } finally {
    await browser.close();
  }
  const bledyLacznie = wyniki.reduce((n, w) => n + w.bledy.length + (w.przewijanie ? 1 : 0) + (w.pusty ? 1 : 0), 0);
  const axeKrytyczne = wyniki.reduce((n, w) => n + (w.axe || []).filter((v) => v.wplyw === 'critical' || v.wplyw === 'serious').length, 0);
  const maleCele = wyniki.reduce((n, w) => n + w.malych_celow, 0);
  const raport = { baza, urzadzenia, motywy, trasy, wyniki, bledy_lacznie: bledyLacznie, axe_powazne: axeKrytyczne, male_cele: maleCele,
    podsumowanie: `${wyniki.length} zrzutów; błędy konsoli/przewijanie/puste: ${bledyLacznie}; axe (poważne): ${axeKrytyczne}; małe cele dotyku: ${maleCele}` };
  fs.writeFileSync(path.join(outdir, 'zrzuty.json'), JSON.stringify(raport, null, 2));
  console.log(raport.podsumowanie);
  process.exit(bledyLacznie ? 1 : 0);
})().catch((e) => { console.error(e && e.stack ? e.stack : String(e)); process.exit(2); });
