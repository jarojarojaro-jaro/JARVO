#!/usr/bin/env node
/**
 * Testy „wrogie” aplikacji w wersji webowej (warstwa 1 bramki aplikacji). Warunki, w których aplikacje zwykle się sypią,
 * a zwykły zrzut tego nie pokaże. Warstwa 2 to urządzenie z Androidem (urzadzenie.py wrogie), warstwa 3 symulator iOS (CI).
 *
 *   node wrogie.cjs <url-bazowy> <outdir> [--trasy /,/wiecej] [--tylko konsola,maly-ekran,...]
 *
 * Scenariusze (w przeglądarce):
 *   konsola          zwykłe wejście (iPhone): błędy konsoli i strony, żądania 4xx/5xx
 *   maly-ekran       iPhone SE (375×667) i mały Android (360×640): poziome przewijanie, wylewający się tekst, cele < 44 px
 *   ciemny           tryb ciemny na każdej trasie: kontrast i etykiety (axe-core)
 *   offline          aplikacja traci sieć po starcie: pasek „Brak internetu” widoczny, nawigacja bez awarii
 *   dlugie-slowa     długie polskie słowa i pełne diakrytyki w tekstach: nic nie wychodzi poza ekran
 *   ograniczony-ruch prefers-reduced-motion: bez trwających animacji CSS
 *   nieznana-trasa   adres, którego nie ma: ekran „nie ma takiego ekranu”, nie pusta strona
 * Tylko na urządzeniu (tu `not_run` z powodem): duza-czcionka, klawiatura, wstecz, uprawnienia, smierc-procesu,
 * wyciecie-ekranu. `not_run` to brak pomiaru, nie zaliczenie.
 *
 * Wynik: <outdir>/wrogie.json + zrzuty. Kod 1, gdy którykolwiek scenariusz ma status `blad`.
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const WEB = ['konsola', 'maly-ekran', 'ciemny', 'offline', 'dlugie-slowa', 'ograniczony-ruch', 'nieznana-trasa'];
const TYLKO_URZADZENIE = {
  'duza-czcionka': 'czcionka systemowa (Dynamic Type, font_scale) działa tylko w aplikacji natywnej',
  klawiatura: 'klawiatura ekranowa zasłaniająca pola istnieje tylko na telefonie',
  wstecz: 'systemowe „wstecz” Androida (przycisk i gest) tylko na urządzeniu',
  uprawnienia: 'okna zgód i odmowa uprawnień tylko na urządzeniu',
  'smierc-procesu': 'zabicie aplikacji w tle i powrót tylko na urządzeniu',
  'wyciecie-ekranu': 'wycięcie ekranu i bezpieczne obszary tylko na urządzeniu albo symulatorze',
};
const DLUGIE = 'Konstantynopolitańczykowianeczka Zażółć gęślą jaźń ŻÓŁĆ GĘŚLĄ JAŹŃ';
const UA_IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1';
const UA_ANDROID = 'Mozilla/5.0 (Linux; Android 16; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36';
const IPHONE = { viewport: { width: 440, height: 956 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: UA_IPHONE, locale: 'pl-PL' };

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

const nazwa = (trasa) => (trasa === '/' ? 'start' : trasa.replace(/^\//, '').replace(/[^\w-]+/g, '_'));

// poziome przewijanie, tekst wylewający się z pudełek, cele dotyku < 44 px
const UKLAD = () => {
  const widoczny = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const opis = (el) => (el.innerText || el.getAttribute('aria-label') || el.tagName).trim().slice(0, 40);
  const all = [...document.querySelectorAll('body *')].filter(widoczny);
  const cele = [...document.querySelectorAll('[role=button],[role=link],[role=tab],a[href],button,input')].filter(widoczny)
    .map((el) => { const r = el.getBoundingClientRect(); return { opis: opis(el), w: Math.round(r.width), h: Math.round(r.height) }; })
    .filter((c) => c.w < 44 || c.h < 44);
  return {
    przewijanie: document.documentElement.scrollWidth > window.innerWidth + 1,
    poza_ekranem: all.filter((el) => el.getBoundingClientRect().right > window.innerWidth + 1).slice(0, 6).map(opis),
    wylewa_sie: all.filter((el) => el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX === 'visible' && el.clientWidth > 0)
      .slice(0, 6).map(opis),
    male_cele: cele.slice(0, 8),
    tekst: (document.body.innerText || '').trim().length,
  };
};

async function otworz(browser, opcje, url, bledy) {
  const ctx = await browser.newContext(opcje);
  const page = await ctx.newPage();
  if (bledy) {
    page.on('console', (m) => { if (m.type() === 'error') bledy.push(m.text().slice(0, 200)); });
    page.on('pageerror', (e) => bledy.push(String(e).slice(0, 200)));
  }
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(1000);
  return { ctx, page };
}

async function axe(page, axePath) {
  if (!axePath) return null;
  await page.addScriptTag({ path: axePath });
  return page.evaluate(async () => (await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag22aa'] } }))
    .violations.map((v) => ({ id: v.id, wplyw: v.impact, wezly: v.nodes.length })));
}

async function scenariusz(browser, id, baza, trasy, outdir, axePath) {
  const r = { id, warstwa: 'web', status: 'ok', obserwacje: {}, dlaczego: '' };
  const zrzut = (page, nazwaPliku) => page.screenshot({ path: path.join(outdir, `${id}-${nazwaPliku}.png`) }).catch(() => null);
  const url = (t) => baza.replace(/\/$/, '') + t;
  if (id === 'konsola') {
    const bledy = [], zle = [];
    const ctx = await browser.newContext(IPHONE);
    for (const t of trasy) {
      const page = await ctx.newPage();
      page.on('console', (m) => { if (m.type() === 'error') bledy.push(`${t}: ${m.text().slice(0, 160)}`); });
      page.on('pageerror', (e) => bledy.push(`${t}: ${String(e).slice(0, 160)}`));
      page.on('response', (s) => { if (s.status() >= 400) zle.push(`${t}: ${s.status()} ${s.url().slice(-80)}`); });
      await page.goto(url(t), { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(800);
      await page.close();
    }
    await ctx.close();
    r.obserwacje = { bledy: bledy.slice(0, 10), nieudane: zle.slice(0, 10) };
    if (bledy.length || zle.length) { r.status = 'blad'; r.dlaczego = 'błędy konsoli albo nieudane żądania'; }
  } else if (id === 'maly-ekran') {
    const profile = [['iphone-se', { ...IPHONE, viewport: { width: 375, height: 667 } }], ['android-maly', { ...IPHONE, userAgent: UA_ANDROID, viewport: { width: 360, height: 640 } }]];
    for (const [p, opcje] of profile) {
      for (const t of trasy) {
        const { ctx, page } = await otworz(browser, opcje, url(t));
        const u = await page.evaluate(UKLAD);
        await zrzut(page, `${p}-${nazwa(t)}`);
        r.obserwacje[`${p} ${t}`] = u;
        if (u.przewijanie || u.wylewa_sie.length || u.tekst === 0) { r.status = 'blad'; r.dlaczego = 'poziome przewijanie, wylewający się tekst albo pusty ekran na małym telefonie'; }
        else if (u.male_cele.length && r.status === 'ok') { r.status = 'blad'; r.dlaczego = 'cele dotyku mniejsze niż 44 px'; }
        await ctx.close();
      }
    }
  } else if (id === 'ciemny') {
    for (const t of trasy) {
      const { ctx, page } = await otworz(browser, { ...IPHONE, colorScheme: 'dark' }, url(t));
      const v = await axe(page, axePath);
      await zrzut(page, nazwa(t));
      const powazne = (v || []).filter((x) => x.wplyw === 'serious' || x.wplyw === 'critical');
      r.obserwacje[t] = v;
      if (powazne.length) { r.status = 'blad'; r.dlaczego = 'w trybie ciemnym poważne błędy dostępności (kontrast, etykiety)'; }
      await ctx.close();
    }
    if (!axePath) { r.status = 'not_run'; r.dlaczego = 'brak axe-core'; }
  } else if (id === 'offline') {
    const bledy = [];
    const { ctx, page } = await otworz(browser, IPHONE, url('/'), bledy);
    await ctx.setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event('offline')));
    await page.waitForTimeout(1500);
    const pasek = await page.getByText(/Brak internetu/i).first().isVisible().catch(() => false);
    await zrzut(page, 'start');
    if (trasy.length > 1) {
      const zakladka = page.getByRole('tab').last();
      if (await zakladka.count()) { await zakladka.click().catch(() => null); await page.waitForTimeout(800); await zrzut(page, 'po-nawigacji'); }
    }
    const tekst = await page.evaluate(() => (document.body.innerText || '').trim().length);
    r.obserwacje = { pasek_brak_sieci: pasek, bledy_strony: bledy.filter((b) => !/net::ERR_INTERNET_DISCONNECTED|Failed to fetch|NetworkError/i.test(b)).slice(0, 5), tekst };
    if (!pasek) { r.status = 'blad'; r.dlaczego = 'po utracie sieci brak komunikatu (szablon: BrakSieci)'; }
    if (r.obserwacje.bledy_strony.length || tekst === 0) { r.status = 'blad'; r.dlaczego = 'awaria albo pusty ekran bez sieci'; }
    await ctx.close();
  } else if (id === 'dlugie-slowa') {
    for (const t of trasy) {
      const { ctx, page } = await otworz(browser, { ...IPHONE, viewport: { width: 375, height: 812 } }, url(t));
      await page.evaluate((dlugie) => {
        const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        let n, i = 0;
        while ((n = w.nextNode())) { if (n.textContent.trim().length > 3 && i++ % 2 === 0) n.textContent = `${n.textContent} ${dlugie}`; }
      }, DLUGIE);
      await page.waitForTimeout(400);
      const u = await page.evaluate(UKLAD);
      await zrzut(page, nazwa(t));
      r.obserwacje[t] = { przewijanie: u.przewijanie, wylewa_sie: u.wylewa_sie };
      if (u.przewijanie || u.wylewa_sie.length) { r.status = 'blad'; r.dlaczego = 'długie polskie słowa wychodzą poza ekran (zawijanie, flexShrink)'; }
      await ctx.close();
    }
  } else if (id === 'ograniczony-ruch') {
    const { ctx, page } = await otworz(browser, { ...IPHONE, reducedMotion: 'reduce' }, url('/'));
    const anim = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running' && a.effect && a.effect.getTiming().iterations === Infinity).length);
    r.obserwacje = { nieskonczone_animacje: anim };
    if (anim > 0) { r.status = 'blad'; r.dlaczego = 'animacje w pętli mimo „ogranicz ruch”'; }
    await ctx.close();
  } else if (id === 'nieznana-trasa') {
    const { ctx, page } = await otworz(browser, IPHONE, url('/to-nie-istnieje-' + Date.now()));
    const tekst = await page.evaluate(() => (document.body.innerText || '').trim());
    await zrzut(page, 'ekran');
    r.obserwacje = { tekst: tekst.slice(0, 120) };
    if (!tekst) { r.status = 'blad'; r.dlaczego = 'nieznany adres daje pustą stronę'; }
    await ctx.close();
  }
  return r;
}

(async () => {
  const poz = [];
  for (let i = 2; i < process.argv.length; i++) { if (process.argv[i].startsWith('--')) i++; else poz.push(process.argv[i]); }
  const [baza, outdir] = poz;
  if (!baza || !outdir) {
    console.error('Użycie: node wrogie.cjs <url-bazowy> <outdir> [--trasy /,/wiecej] [--tylko konsola,offline]');
    process.exit(2);
  }
  const trasy = arg('--trasy', '/').split(',').filter(Boolean);
  const tylko = arg('--tylko', WEB.join(',')).split(',').filter((s) => WEB.includes(s));
  const axePath = (() => { try { return require.resolve('axe-core/axe.min.js'); } catch { return null; } })();
  fs.mkdirSync(outdir, { recursive: true });
  const browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox'] });
  const wyniki = [];
  try {
    for (const id of tylko) {
      try { wyniki.push(await scenariusz(browser, id, baza, trasy, outdir, axePath)); }
      catch (e) { wyniki.push({ id, warstwa: 'web', status: 'blad', obserwacje: {}, dlaczego: `scenariusz przerwany: ${String(e).slice(0, 200)}` }); }
    }
  } finally {
    await browser.close();
  }
  for (const [id, dlaczego] of Object.entries(TYLKO_URZADZENIE)) wyniki.push({ id, warstwa: 'urzadzenie', status: 'not_run', obserwacje: {}, dlaczego });
  const licz = (s) => wyniki.filter((w) => w.status === s).length;
  const raport = { baza, trasy, wyniki, podsumowanie: `web: ${licz('ok')} ok, ${licz('blad')} błędów, ${licz('not_run')} bez pomiaru (urządzenie)` };
  fs.writeFileSync(path.join(outdir, 'wrogie.json'), JSON.stringify(raport, null, 2));
  console.log(raport.podsumowanie);
  process.exit(licz('blad') ? 1 : 0);
})().catch((e) => { console.error(e && e.stack ? e.stack : String(e)); process.exit(2); });
