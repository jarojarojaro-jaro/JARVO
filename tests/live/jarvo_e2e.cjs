#!/usr/bin/env node
/* Test aplikacji Jarvo na żywo w przeglądarce (docs/HQ.md §2c). Uruchamia go scripts/jarvo-e2e.sh w kontenerze
   jarvo-hermes jako hermes; sam: node tests/live/jarvo_e2e.cjs etap1 (z JARVO_E2E_DIR, JARVO_E2E_INBOX).

   Przeglądarka: playwright-core z /opt/jarvo/node/node_modules i /usr/local/bin/chromium. Logowanie loginem
   i hasłem dashboardu z env kontenera (HERMES_DASHBOARD_BASIC_AUTH_*); hasła i ciasteczek nigdy nie wypisujemy.
   Wynik: raport JSON na stdout, kod 1 przy pierwszym nieudanym punkcie i dalej (punkty są niezależne, ile się da).
   Zrzuty ekranu nieudanych punktów: $JARVO_E2E_DIR (jarvo-e2e.sh kasuje katalog po udanym przebiegu). */
"use strict";
const fs = require("fs");
const path = require("path");
const http = require("http");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright-core");

const ETAP = process.argv[2] || "etap1";
const BASE = (process.env.JARVO_E2E_URL || "http://localhost:9119").replace(/\/+$/, "");
const DIR = process.env.JARVO_E2E_DIR || fs.mkdtempSync("/tmp/jarvo-e2e-");
const INBOX = process.env.JARVO_E2E_INBOX || "";                       // fiksturki w inbox (sprząta jarvo-e2e.sh)
const STRONA = (process.env.JARVO_E2E_STRONA || "http://localhost:9188").replace(/\/+$/, "");   // zwykła strona tej samej witryny
const PODGLAD = process.env.JARVO_E2E_PODGLAD || "http://localhost:9120";                      // serwer podglądu „▶ Odpal”
const KNOWLEDGE = process.env.JARVO_KNOWLEDGE_DIR || "/opt/data/jarvo/knowledge";
const REPO = path.resolve(__dirname, "..", "..");
const PRZEGLADARKA = process.env.JARVO_E2E_CHROMIUM || "/usr/local/bin/chromium";
const USER = process.env.HERMES_DASHBOARD_BASIC_AUTH_USERNAME || "";
const PASS = process.env.HERMES_DASHBOARD_BASIC_AUTH_PASSWORD || "";
const ZNACZNIK = `jarvo-e2e-${path.basename(DIR)}`;                  // nazwy plików i treść prób CSRF
const APP_JS = /\/api\/plugins\/jarvo-hq\/zasoby\/app-[0-9a-f]{12}\.js$/;
const SELEKTORY = JSON.parse(fs.readFileSync(path.join(REPO, "branding", "powloka.json"), "utf8")).css.map((c) => c.selektor);

const wyniki = [];
let aktywna = null;                                                    // strona do zrzutu przy błędzie

const bezHasla = (s) => {                                              // hasło nigdy nie trafia do raportu
  const t = String(s == null ? "" : s);
  return PASS ? t.split(PASS).join("***") : t;
};
const czysc = (s) => bezHasla(s).slice(0, 800);
function musi(warunek, opis) { if (!warunek) throw new Error(opis); }

async function krok(id, nazwa, fn) {
  const t0 = Date.now();
  try {
    const szczegoly = await fn();
    wyniki.push({ id, nazwa, ok: true, ms: Date.now() - t0, ...(szczegoly ? { szczegoly } : {}) });
  } catch (e) {
    wyniki.push({ id, nazwa, ok: false, ms: Date.now() - t0, blad: czysc(e && e.message ? e.message : e) });
    if (aktywna) await aktywna.screenshot({ path: path.join(DIR, `punkt-${id}.png`) }).catch(() => {});
  }
}

// zwykłe żądanie HTTP bez przeglądarki (jak curl): żadnych Origin ani Sec-Fetch-*
function zadanie(metoda, url, { naglowki = {}, tresc } = {}) {
  return new Promise((ok, nie) => {
    const u = new URL(url);
    const r = http.request({ method: metoda, hostname: u.hostname, port: u.port, path: u.pathname + u.search,
      headers: naglowki, family: u.hostname === "localhost" ? 4 : undefined }, (res) => {
      let d = "";
      res.on("data", (c) => { d += c; });
      res.on("end", () => ok({ status: res.statusCode, naglowki: res.headers, tresc: d }));
    });
    r.on("error", nie);
    if (tresc != null) r.write(tresc);
    r.end();
  });
}

const sciezka = (p) => p.evaluate(() => location.pathname);
const atrybuty = (p) => p.evaluate(() => [...document.documentElement.attributes].map((a) => a.name).filter((n) => n.startsWith("data-jarvo")).sort());
const pasekWidoczny = (p) => p.evaluate(() => {
  const s = document.getElementById("app-sidebar");
  return !!s && getComputedStyle(s).display !== "none" && s.getBoundingClientRect().width > 0;
});
const czekajNa = (p, cel, ms = 15000) => p.waitForFunction((c) => location.pathname === c, cel, { timeout: ms });
const czekajGotowe = (p, ms = 15000) => p.waitForFunction(() => {
  const d = document.documentElement;
  return d.hasAttribute("data-jarvo-gotowe") && !d.hasAttribute("data-jarvo-wstepnie");
}, null, { timeout: ms, polling: "raf" });

// strony prób w katalogu inbox (serwer podglądu :9120 z linkiem z tokenem i zwykły serwer :9188 jarvo-e2e.sh)
function fiksturki() {
  if (!INBOX) return;
  fs.mkdirSync(INBOX, { recursive: true });
  // CSRF: fetch text/plain (no-cors), formularz text/plain i to samo z ramki sandbox (Origin: null); cel to dashboard
  // na porcie 9119 tej samej witryny; treść z ZNACZNIK, żeby sprawdzić, że w skarbcu nic nie powstało
  fs.writeFileSync(path.join(INBOX, "csrf.html"), `<!doctype html><html lang="pl"><head><meta charset="utf-8">
<title>Próba CSRF (Jarvo E2E)</title></head><body><p>Próba CSRF (test Jarvo E2E)</p>
<iframe name="zlew" title="zlew"></iframe>
<form id="f" method="post" enctype="text/plain" target="zlew"><input name="x" value="${ZNACZNIK}"></form>
<script>
(function () {
  var D = location.protocol + "//" + location.hostname + ":9119";
  var cele = ["/api/plugins/jarvo-hq/csrf-proba", "/api/plugins/jarvo-wiedza/remark"];
  var tresc = JSON.stringify({ path: "index.md", uwaga: "${ZNACZNIK}" });
  function wyslij(c) {
    fetch(D + c, { method: "POST", mode: "no-cors", credentials: "include", headers: { "Content-Type": "text/plain" }, body: tresc })
      .catch(function () {});
  }
  cele.forEach(wyslij);
  var f = document.getElementById("f"); f.action = D + cele[1]; f.submit();
  var r = document.createElement("iframe");
  r.setAttribute("sandbox", "allow-scripts");
  r.srcdoc = "<script>var D=" + JSON.stringify(D) + ",t=" + JSON.stringify(tresc) + ";" + JSON.stringify(cele) +
    ".forEach(function(c){fetch(D+c,{method:'POST',mode:'no-cors',credentials:'include',headers:{'Content-Type':'text/plain'},body:t}).catch(function(){})})</" + "script>";
  document.body.appendChild(r);
})();
</script></body></html>
`);
  // dashboard w ramce strony z innego pochodzenia (ochrona przed clickjackingiem)
  fs.writeFileSync(path.join(INBOX, "ramka.html"), `<!doctype html><html lang="pl"><head><meta charset="utf-8">
<title>Ramka obca (Jarvo E2E)</title></head><body><script>
var f = document.createElement("iframe"); f.width = 900; f.height = 600;
f.src = location.protocol + "//" + location.hostname + ":9119/sessions"; document.body.appendChild(f);
</script></body></html>
`);
}

// ------------------------------------------------------------------------------------------------ etap 1

async function etap1(browser) {
  fiksturki();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "pl-PL" });
  const page = await ctx.newPage();
  aktywna = page;

  await krok("1", "bez logowania /jarvo → logowanie → z powrotem na /jarvo", async () => {
    const r = await zadanie("GET", BASE + "/jarvo", { naglowki: { Accept: "text/html" } });
    const gdzie = (r.naglowki.location || "").replace(BASE, "");
    musi(r.status === 302 && gdzie.startsWith("/login?next=%2Fjarvo"), `GET /jarvo bez sesji: ${r.status} → ${gdzie}`);
    musi(USER && PASS, "brak HERMES_DASHBOARD_BASIC_AUTH_USERNAME/PASSWORD w env");
    await page.goto(BASE + "/jarvo");
    const form = "form.provider-form:has(input[name=password])";
    await page.waitForSelector(form, { timeout: 15000 });
    await page.fill(`${form} input[name=username]`, USER);
    await page.fill(`${form} input[name=password]`, PASS);
    await Promise.all([czekajNa(page, "/jarvo", 20000), page.click(`${form} button[type=submit]`)]);
    return { bez_sesji: `${r.status} ${gdzie}`, po_logowaniu: await sciezka(page) };
  });
  if (!wyniki[0].ok) return ctx;

  await krok("2", "/, stary adres Bazy i nieznany adres prowadzą na /jarvo", async () => {
    const out = {};
    for (const z of ["/", "/base", "/nieznane"]) {
      await page.goto(BASE + z);
      await czekajNa(page, "/jarvo");
      out[z] = await sciezka(page);
    }
    return out;
  });

  await krok("3", "bez wtyczki /jarvo → /sessions bez pętli; bez skryptu powłoki przekierowania Hermesa idą na /sessions", async () => {
    const p = await ctx.newPage();
    aktywna = p;
    await p.addInitScript(() => {                     // każda zmiana adresu z historii (SPA)
      window.__nawigacje = [];
      for (const f of ["pushState", "replaceState"]) {
        const o = history[f];
        history[f] = function (s, t, u) { window.__nawigacje.push(String(u)); return o.apply(this, arguments); };
      }
    });
    let usuniete = 0;
    await p.route((u) => u.pathname === "/api/dashboard/plugins", async (route) => {
      const r = await route.fetch();
      const j = await r.json();
      const filtr = (lista) => lista.filter((x) => { const ma = x && x.name === "jarvo-hq"; usuniete += ma ? 1 : 0; return !ma; });
      const nowe = Array.isArray(j) ? filtr(j) : { ...j, plugins: filtr(j.plugins || []) };
      await route.fulfill({ response: r, json: nowe });
    });
    await p.goto(BASE + "/jarvo");
    await czekajNa(p, "/sessions");
    const tSesje = Date.now();
    // zasłona startowa nie zakrywa klasycznej strony: znika razem z przejściem, nie dopiero po 8 s bezpiecznika
    await p.waitForFunction(() => !document.documentElement.hasAttribute("data-jarvo-wstepnie"), null, { timeout: 1000 })
      .catch(() => { throw new Error("zasłona startowa nadal zakrywa /sessions po 1 s (bez wtyczki)"); });
    const zaslonaBezWtyczkiMs = Date.now() - tSesje;
    musi(await pasekWidoczny(p), "bez wtyczki: menu Hermesa niewidoczne na /sessions");
    await p.waitForTimeout(2000);
    const nav = await p.evaluate(() => window.__nawigacje);
    // przekierowanie = zmiana ścieżki; same dopiski ?profile= Hermesa (i wpis bez adresu) się nie liczą
    const sciezki = ["/jarvo"];
    for (const u of nav) {
      if (!u || u === "undefined") continue;
      const s = new URL(u, BASE).pathname;
      if (s !== sciezki[sciezki.length - 1]) sciezki.push(s);
    }
    musi(usuniete >= 1, "lista wtyczek bez jarvo-hq: nic nie usunięto (inny adres /api/dashboard/plugins?)");
    musi(await sciezka(p) === "/sessions" && sciezki.length - 1 < 3, `pętla przekierowań: ${JSON.stringify(nav)}`);
    await p.close();
    // index.html bez skryptu powłoki: przekierowania Hermesa są strzeżone i idą na /sessions jak w czystym Hermesie.
    // "/" (RootRedirect) przechodzi na /sessions, ale czysty Hermes 0.21.5 sam cofa to w tej samej klatce na
    // /?profile=default (ProfileProvider, adres sprzed przekierowania); dlatego "/" sprawdza samo przejście,
    // a do końca prowadzi nieznany adres (UnknownRouteFallback czeka na wtyczki, więc bez tego wyścigu).
    const bezSkryptu = {};
    for (const z of ["/", "/nieznane"]) {
      const p2 = await ctx.newPage();
      aktywna = p2;
      await p2.addInitScript(() => {
        window.__nawigacje = [];
        const o = history.replaceState;
        history.replaceState = function (s, t, u) { window.__nawigacje.push(String(u)); return o.apply(this, arguments); };
      });
      await p2.route((u) => u.pathname === z, async (route) => {
        const r = await route.fetch();
        const html = (await r.text()).replace(/<script id="jarvo-powloka-js">[\s\S]*?<\/script>/, "");
        await route.fulfill({ response: r, body: html });
      });
      await p2.goto(BASE + z);
      if (z === "/") {
        await p2.waitForFunction(() => window.__nawigacje.some((u) => u.split("?")[0] === "/sessions"), null, { timeout: 15000 });
      } else {
        await czekajNa(p2, "/sessions");
      }
      musi(await p2.evaluate(() => typeof window.__JARVO_CEL__) === "undefined", "skrypt powłoki nie został usunięty z próby");
      bezSkryptu[z] = { koniec: await sciezka(p2), nawigacje: await p2.evaluate(() => window.__nawigacje.filter((u) => u !== "undefined")) };
      await p2.close();
    }
    aktywna = page;
    return { przekierowania_bez_wtyczki: sciezki, zasłona_bez_wtyczki_ms: zaslonaBezWtyczkiMs, bez_skryptu: bezSkryptu };
  });

  await krok("4", "stara Baza na /jarvo z menu Hermesa; zasady chowania powłoki; /sessions z Jarvo na górze menu", async () => {
    await page.goto(BASE + "/jarvo", { waitUntil: "domcontentloaded" });
    await czekajGotowe(page);
    const zaslonaMs = Math.round(await page.evaluate(() => performance.now()));
    await page.waitForSelector(".thq-root", { state: "visible", timeout: 15000 });
    musi(zaslonaMs <= 2000, `zasłona zeszła po ${zaslonaMs} ms (limit 2000)`);
    musi(await pasekWidoczny(page), "menu Hermesa niewidoczne na /jarvo");
    const atr = await atrybuty(page);
    musi(!atr.includes("data-jarvo-app"), `stara Baza chowa powłokę: ${atr}`);
    await page.waitForFunction(() => !!document.querySelector("#app-sidebar .thq-upd, aside.fixed .thq-upd"), null, { timeout: 6000 });
    const sprawdz = () => page.evaluate((sel) => {
      const d = document.documentElement;
      const thq = document.querySelector(".thq-root");
      const host = thq ? thq.parentElement : document.body;
      const wyswietlanie = () => sel.map((s) => [...document.querySelectorAll(s)].map((e) => getComputedStyle(e).display));
      const przed = wyswietlanie();
      d.setAttribute("data-jarvo-app", "");
      if (thq) thq.style.display = "none";
      const k = document.createElement("div");
      k.id = "jarvo-e2e-korzen";
      k.setAttribute("data-jarvo-korzen", "");          // korzeń aplikacji: reszta strony dostaje inert (powłoka)
      k.style.cssText = "position:fixed;inset:0;z-index:30;background:#202024";
      for (const n of ["a", "b"]) { const b = document.createElement("button"); b.id = `e2e-${n}`; b.textContent = n; k.appendChild(b); }
      host.appendChild(k);
      const po = wyswietlanie();
      const W = innerWidth, H = innerHeight, punkty = [];
      for (const fx of [0.02, 0.5, 0.98]) for (const fy of [0.02, 0.5, 0.98]) {
        const e = document.elementFromPoint(fx * W, fy * H);
        punkty.push(!!e && k.contains(e) ? 1 : (e ? (e.id || e.tagName) : "brak"));
      }
      return { przed, po, punkty };
    }, SELEKTORY);
    const sprzataj = () => page.evaluate(() => {
      document.documentElement.removeAttribute("data-jarvo-app");
      const k = document.getElementById("jarvo-e2e-korzen"); if (k) k.remove();
      const thq = document.querySelector(".thq-root"); if (thq) thq.style.display = "";
    });
    const uspione = () => page.evaluate(() => document.querySelectorAll("[inert]").length);
    const biurko = await sprawdz();
    const tab = [];
    await page.focus("#e2e-a");
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press("Tab");
      tab.push(await page.evaluate((sel) => {
        const a = document.activeElement, k = document.getElementById("jarvo-e2e-korzen");
        if (!a || a === document.body) return "body";
        if (k.contains(a)) return "app";
        const opis = `${a.tagName.toLowerCase()}${a.id ? "#" + a.id : ""} „${(a.textContent || "").trim().slice(0, 20)}”`;
        return sel.some((s) => a.closest(s)) ? `POWLOKA ${opis}` : `POZA ${opis}`;
      }, SELEKTORY));
    }
    const inertZApp = await uspione();
    await sprzataj();
    await page.waitForTimeout(100);
    const inertPo = await uspione();
    // telefon: z otwartym menu Hermesa (wtedy jest zasłona menu, czwarty selektor)
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const telefonZamkniete = await sprawdz();
    await sprzataj();
    await page.click("header.lg\\:hidden.fixed.top-0 button");
    await page.waitForTimeout(300);
    const telefon = await sprawdz();
    await sprzataj();
    await page.keyboard.press("Escape");
    await page.setViewportSize({ width: 1280, height: 800 });
    // na każdym ekranie: każdy selektor pasuje do najwyżej jednego elementu i z data-jarvo-app jest ukryty
    const stany = [["biurko", biurko], ["telefon", telefonZamkniete], ["telefon z menu", telefon]];
    for (const [nazwa, w] of stany) {
      w.po.forEach((lista, i) => {
        musi(lista.length <= 1, `${nazwa}: ${SELEKTORY[i]} pasuje do ${lista.length} elementów`);
        musi(lista.every((x) => x === "none"), `${nazwa}: ${SELEKTORY[i]} widoczny mimo data-jarvo-app (${lista})`);
      });
      musi(w.punkty.every((x) => x === 1), `${nazwa}: elementFromPoint poza aplikacją: ${JSON.stringify(w.punkty)}`);
    }
    // każdy selektor z powloka.json trafia dokładnie jeden element przynajmniej w jednym stanie (inaczej zły selektor)
    SELEKTORY.forEach((s, i) => musi(stany.some(([, w]) => w.przed[i].length === 1), `${s}: nie trafia żadnego elementu w DOM`));
    musi(telefon.przed[1].some((x) => x !== "none"), "telefon: nagłówek Hermesa nie był widoczny przed data-jarvo-app (zły selektor?)");
    musi(telefon.przed[2].some((x) => x !== "none"), "telefon: zasłona menu niewidoczna przy otwartym menu (zły selektor?)");
    // Tab zostaje w aplikacji (najwyżej wychodzi z dokumentu): reszta strony ma inert, a po zejściu data-jarvo-app go nie ma
    musi(tab.every((x) => x === "app" || x === "body"), `Tab wychodzi poza aplikację: ${JSON.stringify(tab)}`);
    musi(inertZApp > 0 && inertPo === 0, `inert: z aplikacją ${inertZApp}, po zejściu ${inertPo}`);
    // /sessions: menu Hermesa z Jarvo na pierwszym miejscu
    await page.goto(BASE + "/sessions");
    await page.waitForSelector("#app-sidebar nav a", { timeout: 15000 });
    const menu = await page.evaluate(() => [...document.querySelectorAll("#app-sidebar nav a")].slice(0, 3)
      .map((a) => [a.getAttribute("href"), a.textContent.trim()]));
    musi(await pasekWidoczny(page), "menu Hermesa niewidoczne na /sessions");
    musi(/\/jarvo$/.test(menu[0][0]) && /jarvo/i.test(menu[0][1]), `pierwsza pozycja menu: ${JSON.stringify(menu[0])}`);
    return { zaslona_ms: zaslonaMs, tab, inert: inertZApp, elementy_biurko: biurko.przed, elementy_telefon: telefon.przed, menu };
  });

  await krok("5", "bez pustego ekranu: pakiet się nie wczytuje albo rzuca błąd", async () => {
    // a) pakiet wisi: po 8 s bezpiecznik zdejmuje zasłonę, menu Hermesa widać
    const p = await ctx.newPage();
    aktywna = p;
    await p.route(APP_JS, () => {});                       // bez odpowiedzi
    await p.goto(BASE + "/jarvo", { waitUntil: "domcontentloaded" });
    await p.waitForTimeout(1000);
    const naStarcie = await atrybuty(p);
    const t0 = Date.now();
    await p.waitForFunction(() => !document.documentElement.hasAttribute("data-jarvo-wstepnie"), null, { timeout: 9500 });
    const poMs = Date.now() - t0 + 1000;
    musi(naStarcie.includes("data-jarvo-wstepnie"), `brak zasłony na starcie: ${naStarcie}`);
    musi(await pasekWidoczny(p), "po bezpieczniku nie widać menu Hermesa");
    // pole Jarva nie jest puste: po 7 s bez pakietu loader pokazuje ekran błędu z Odśwież
    await p.waitForSelector(".jarvo-blad-ladowania", { timeout: 3000 });
    await p.close();
    // a'') arkusz stylów nie odpowiada, pakiet jest: aplikacja rusza po najwyżej 3 s
    const ps = await ctx.newPage();
    aktywna = ps;
    await ps.route(/\/api\/plugins\/jarvo-hq\/zasoby\/app-[0-9a-f]{12}\.css$/, () => {});
    const tCss = Date.now();
    await ps.goto(BASE + "/jarvo", { waitUntil: "domcontentloaded" });
    await ps.waitForSelector(".thq-root", { state: "visible", timeout: 8000 });
    const bezStyluMs = Date.now() - tCss;
    await ps.close();
    // a') pakiet nie istnieje (błąd sieci): ekran błędu od razu
    const p1 = await ctx.newPage();
    aktywna = p1;
    let zadaniaPakietu = 0;
    await p1.route(APP_JS, (r) => (++zadaniaPakietu === 1 ? r.abort() : r.continue()));
    await p1.goto(BASE + "/jarvo");
    await p1.waitForSelector(".jarvo-blad-ladowania", { timeout: 10000 });
    // ta sama karta: Sesje i z powrotem przez menu (SPA) = nowa próba wczytania, tym razem udana
    await p1.click("#app-sidebar a[href$='/sessions']");
    await czekajNa(p1, "/sessions");
    await p1.click("#app-sidebar a[href$='/jarvo']");
    await p1.waitForSelector(".thq-root", { state: "visible", timeout: 15000 });
    musi(zadaniaPakietu === 2, `ponowna próba: pakiet pobrany ${zadaniaPakietu} raz(y)`);
    await p1.close();
    // b) pakiet rzuca przy renderze: osłona błędów, ekran z Odśwież i klasycznym panelem, powłoka wraca
    const p2 = await ctx.newPage();
    aktywna = p2;
    await p2.route(APP_JS, (r) => r.fulfill({ contentType: "text/javascript; charset=utf-8",
      body: "window.__JARVO_APP__={wersja:2,App:function(){document.documentElement.setAttribute('data-jarvo-app','');" +
            "throw new Error('jarvo-e2e: błąd renderu')}};" }));
    await p2.goto(BASE + "/jarvo");
    const blad = await p2.waitForSelector(".jarvo-blad-ladowania", { timeout: 10000 });
    const tekst = await blad.innerText();
    const link = await p2.getAttribute(".jarvo-blad-ladowania a:last-of-type", "href");
    await p2.waitForTimeout(300);
    const atr = await atrybuty(p2);
    musi(/Odśwież/.test(tekst) && /Otwórz klasyczny panel/.test(tekst), `ekran błędu: ${tekst}`);
    musi(/\/sessions$/.test(link || ""), `link klasycznego panelu: ${link}`);
    musi(!atr.includes("data-jarvo-app") && !atr.includes("data-jarvo-wstepnie"), `atrybuty po błędzie: ${atr}`);
    musi(await pasekWidoczny(p2), "po błędzie nie widać menu Hermesa");
    await p2.close();
    aktywna = page;
    return { bezpiecznik_ms: poMs, bez_stylu_ms: bezStyluMs, ponowna_proba: "udana", ekran_bledu: tekst.replace(/\s+/g, " ").trim() };
  });

  await krok("6", "/logs w ramce data-jarvo-embed: bez menu, także po przejściu w ramce; ramka obcej strony zablokowana", async () => {
    await page.goto(BASE + "/jarvo");
    await page.evaluate((base) => {
      const f = document.createElement("iframe");
      f.id = "e2e-ramka"; f.setAttribute("data-jarvo-embed", ""); f.src = base + "/logs";
      f.style.cssText = "position:fixed;right:0;bottom:0;width:900px;height:600px;z-index:99;border:0";
      document.body.appendChild(f);
    }, BASE);
    const ramka = await (await page.waitForSelector("#e2e-ramka")).contentFrame();
    const stan = async () => {
      await ramka.waitForSelector("#app-sidebar", { state: "attached", timeout: 15000 });
      return ramka.evaluate(() => ({ sciezka: location.pathname, embed: document.documentElement.hasAttribute("data-jarvo-embed"),
        pasek: getComputedStyle(document.getElementById("app-sidebar")).display }));
    };
    const s1 = await stan();
    await ramka.goto(BASE + "/sessions");                  // nowy dokument w tej samej ramce
    const s2 = await stan();
    await ramka.evaluate(() => { history.pushState({}, "", "/config"); dispatchEvent(new PopStateEvent("popstate")); });
    await ramka.waitForTimeout(500);
    const s3 = await stan();
    for (const s of [s1, s2, s3]) musi(s.embed && s.pasek === "none", `ramka bez osadzenia: ${JSON.stringify(s)}`);
    musi(s1.sciezka === "/logs", `ramka przekierowana z /logs: ${s1.sciezka}`);
    // ?jarvo-embed=1 działa tylko w ramce: w zwykłej karcie menu Hermesa zostaje
    const pk = await ctx.newPage();
    aktywna = pk;
    await pk.goto(BASE + "/logs?jarvo-embed=1");
    await pk.waitForSelector("#app-sidebar", { state: "attached", timeout: 15000 });
    musi(!(await atrybuty(pk)).includes("data-jarvo-embed") && await pasekWidoczny(pk), "?jarvo-embed=1 w zwykłej karcie chowa menu");
    await pk.close();
    aktywna = page;
    // dashboard w ramce strony z innego pochodzenia (tu :9188, ta sama witryna): ukryty
    const p = await ctx.newPage();
    aktywna = p;
    await p.goto(`${STRONA}/ramka.html`);
    const obca = await (await p.waitForSelector("iframe")).contentFrame();
    await obca.waitForLoadState("domcontentloaded");
    const zablokowana = await obca.evaluate(() => document.documentElement.hasAttribute("data-jarvo-zablokuj")
      && getComputedStyle(document.body).display === "none");
    musi(zablokowana, "dashboard w ramce obcej strony nie jest zablokowany");
    await p.close();
    aktywna = page;
    return { logi: s1, po_przejsciu: s2, spa: s3, karta_z_zapytaniem: "menu zostaje", ramka_obca: "zablokowana" };
  });

  await krok("7", "rozmiary: /sessions tylko loader ≤ 4 KB; /jarvo pakiet gzip i immutable; po odświeżeniu z cache", async () => {
    const p = await ctx.newPage();
    aktywna = p;
    const cdp = await ctx.newCDPSession(p);
    await cdp.send("Network.enable");
    let log = new Map();
    const wpis = (id) => { if (!log.has(id)) log.set(id, {}); return log.get(id); };
    cdp.on("Network.requestWillBeSent", (e) => { wpis(e.requestId).url = e.request.url; });
    cdp.on("Network.requestServedFromCache", (e) => { wpis(e.requestId).zPamieci = true; });
    cdp.on("Network.responseReceived", (e) => {
      const w = wpis(e.requestId);
      w.url = e.response.url; w.status = e.response.status; w.zDysku = !!e.response.fromDiskCache;
      w.naglowki = Object.fromEntries(Object.entries(e.response.headers || {}).map(([k, v]) => [k.toLowerCase(), String(v)]));
    });
    cdp.on("Network.loadingFinished", (e) => { wpis(e.requestId).bajty = e.encodedDataLength; });
    const nasze = () => [...log.values()].filter((w) => w.url && /jarvo-hq/.test(w.url));
    await p.goto(BASE + "/sessions");
    await p.waitForTimeout(3000);
    const sesje = nasze();
    const loader = sesje.find((w) => /\/dashboard-plugins\/jarvo-hq\/dist\/index\.js/.test(w.url));
    musi(loader, `/sessions nie pobrało loadera: ${JSON.stringify(sesje.map((w) => w.url))}`);
    const dlugosc = Number(loader.naglowki && loader.naglowki["content-length"]) ||
      fs.statSync("/opt/data/plugins/jarvo-hq/dashboard/dist/index.js").size;
    musi(dlugosc <= 4096, `loader ${dlugosc} B > 4096 B`);
    musi(!sesje.some((w) => /\/zasoby\/|style\.css/.test(w.url)), `/sessions pobrało pakiet: ${sesje.map((w) => w.url)}`);
    log = new Map();
    await p.goto(BASE + "/jarvo");
    await czekajGotowe(p);
    const app = nasze().find((w) => APP_JS.test(w.url));
    musi(app && app.status === 200, `brak pakietu app-*.js na /jarvo`);
    musi(app.naglowki["content-encoding"] === "gzip", `pakiet bez gzip: ${app.naglowki["content-encoding"]}`);
    musi(/immutable/.test(app.naglowki["cache-control"] || ""), `cache-control: ${app.naglowki["cache-control"]}`);
    log = new Map();
    await p.reload();
    await czekajGotowe(p);
    const znowu = nasze().find((w) => APP_JS.test(w.url));
    musi(znowu && (znowu.zDysku || znowu.zPamieci), `po odświeżeniu pakiet z sieci: ${JSON.stringify(znowu)}`);
    await p.close();
    aktywna = page;
    return { loader_b: dlugosc, loader_transfer_b: loader.bajty, pakiet_transfer_b: app.bajty,
             cache_control: app.naglowki["cache-control"], po_odswiezeniu: znowu.zDysku ? "dysk" : "pamięć" };
  });

  await krok("8", "CSRF: strona agenta (:9120), zwykła strona tej witryny i ramka sandbox odrzucone; panel i curl", async () => {
    musi(INBOX, "brak JARVO_E2E_INBOX");
    const ciastka = (await ctx.cookies(BASE)).map((c) => `${c.name}=${c.value}`).join("; ");
    const cele = ["/api/plugins/jarvo-hq/csrf-proba", "/api/plugins/jarvo-wiedza/remark"];
    const statusy = [];
    const sluchaj = (r) => {
      const u = new URL(r.url());
      if (cele.includes(u.pathname) && r.request().method() === "POST") {
        statusy.push({ cel: u.pathname, status: r.status(), z: (r.frame() && r.frame().url() || "").replace(/\/[A-Za-z0-9_-]{20,}\//, "/<token>/").slice(0, 80) });
      }
    };
    ctx.on("response", sluchaj);
    const link = execFileSync("python3", [path.join(REPO, "scripts", "jarvo_link.py"), path.join(INBOX, "csrf.html")], { encoding: "utf8" }).trim();
    const naPodgladzie = PODGLAD + new URL(link).pathname;     // ta sama witryna co dashboard (localhost)
    for (const adres of [naPodgladzie, `${STRONA}/csrf.html`]) {
      const p = await ctx.newPage();
      aktywna = p;
      await p.goto(adres);
      await p.waitForTimeout(3000);
      await p.close();
    }
    ctx.off("response", sluchaj);
    aktywna = page;
    musi(statusy.length >= 6, `za mało prób (${statusy.length}): ${JSON.stringify(statusy)}`);
    musi(statusy.every((s) => s.status === 401 || s.status === 403), `zapis przeszedł: ${JSON.stringify(statusy)}`);
    musi(statusy.some((s) => s.status === 403 && s.cel.endsWith("csrf-proba")) && statusy.some((s) => s.status === 403 && s.cel.endsWith("remark")),
      `ochrona zapisu nie zadziałała (same 401 z bramki logowania): ${JSON.stringify(statusy)}`);
    let slad = "";
    try { slad = execFileSync("grep", ["-rl", ZNACZNIK, KNOWLEDGE], { encoding: "utf8" }); } catch (_) { slad = ""; }
    musi(!slad.trim(), `uwaga z próby CSRF zapisana w skarbcu: ${slad}`);
    // panel (/jarvo) z nagłówkiem: 200
    await page.goto(BASE + "/jarvo");
    const zPanelu = await page.evaluate((u) => fetch(u, { method: "POST", headers: { "X-Jarvo-Request": "1" } }).then((r) => r.status), cele[0]);
    musi(zPanelu === 200, `csrf-proba z panelu: ${zPanelu}`);
    // curl: z ciasteczkiem sesji, bez nagłówków przeglądarki i bez X-Jarvo-Request → 403 w obu wtyczkach
    const curl = {};
    for (const c of cele) {
      const r = await zadanie("POST", BASE + c, { naglowki: { Cookie: ciastka, "Content-Type": "text/plain" }, tresc: ZNACZNIK });
      let kod = "";
      try { kod = JSON.parse(r.tresc).blad.kod; } catch (_) { kod = ""; }
      curl[c] = `${r.status} ${kod}`;
      musi(r.status === 403 && kod === "csrf", `curl ${c}: ${r.status} ${czysc(r.tresc).slice(0, 120)}`);
    }
    const bezSesji = await zadanie("POST", BASE + cele[0], { naglowki: { "X-Jarvo-Request": "1" } });
    return { proby: statusy, z_panelu: zPanelu, curl, bez_sesji: bezSesji.status };
  });

  await krok("9", "stara Baza działa: panel agenta, cele konwertera, podgląd pliku", async () => {
    await page.goto(BASE + "/jarvo");
    await page.waitForSelector(".thq-room", { timeout: 20000 });
    const pokoj = page.locator(".thq-room").first();
    await pokoj.click();
    const panel = await page.waitForSelector("aside.thq-panel", { state: "visible", timeout: 10000 });
    const agent = await panel.getAttribute("aria-label");
    await pokoj.click();                                       // drugi klik zamyka panel: wraca Centrala
    await page.waitForSelector(".thq-konw", { timeout: 10000 });
    const png = path.join(DIR, `${ZNACZNIK}.png`);
    fs.writeFileSync(png, Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGO4omgLRAwQCgAj4gTJ7mOUbAAAAABJRU5ErkJggg==", "base64"));
    await page.setInputFiles(".thq-konw input[type=file]", png);
    await page.waitForSelector(".thq-konw-grupa .thq-act-btn", { timeout: 30000 });
    const celeKonw = await page.$$eval(".thq-konw-grupa .thq-act-btn", (b) => b.map((x) => x.textContent.trim()));
    musi(celeKonw.length > 0, "konwerter bez celów dla PNG");
    const jpg = page.locator(".thq-konw-grupa .thq-act-btn", { hasText: /^JPE?G$/i }).first();
    await ((await jpg.count()) ? jpg : page.locator(".thq-konw-grupa .thq-act-btn").first()).click();
    await page.waitForSelector(".thq-konw-wynik .thq-link", { timeout: 60000 });
    await page.click(".thq-konw-wynik .thq-link");
    await page.waitForSelector(".thq-preview-img", { state: "visible", timeout: 15000 });
    await page.keyboard.press("Escape");
    return { panel: agent, cele_konwertera: celeKonw.slice(0, 8), podglad: "obraz" };
  });
  return ctx;
}

// ------------------------------------------------------------------------------------------------ start

(async () => {
  const etapy = { etap1 };
  if (!etapy[ETAP]) { console.error(`nieznany etap ${ETAP} (są: ${Object.keys(etapy)})`); process.exit(2); }
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ executablePath: PRZEGLADARKA, args: ["--no-sandbox"] });
  let ctx = null;
  try {
    ctx = await etapy[ETAP](browser);
  } catch (e) {
    wyniki.push({ id: "-", nazwa: "przebieg", ok: false, blad: czysc(e && e.message ? e.message : e) });
  } finally {
    if (ctx) await ctx.close().catch(() => {});
    await browser.close().catch(() => {});
  }
  const ok = wyniki.length > 0 && wyniki.every((w) => w.ok);
  console.log(bezHasla(JSON.stringify({ etap: ETAP, ok, wyniki, zrzuty: ok ? null : DIR }, null, 1)));
  process.exit(ok ? 0 : 1);
})();
