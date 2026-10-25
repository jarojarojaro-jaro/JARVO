// Strumień zdarzeń silnika rozmów (docs/HQ.md „Aplikacja”): jeden EventSource na przeglądarkę, nie na kartę.
// Chromium ma 6 połączeń HTTP/1.1 na host dla wszystkich kart i ramek, więc karty wybierają lidera zamkiem Web Locks
// („jarvo-strumien”): lider otwiera strumień i rozsyła ramki przez BroadcastChannel("jarvo"), pozostałe karty podają
// mu swoje subskrypcje wątków, a lider wysyła ich sumę (POST /strumien/<klient>/subskrypcje). Każda karta stosuje
// tylko ramki wątków, które sama subskrybuje, i pamięta kursor <epoka>.<seq> ostatniej ramki: duplikaty odpadają,
// a nowy lider (zamknięta karta lidera) otwiera strumień od tego kursora (?od=). Własne ponowne otwarcie zawsze niesie
// ?od= (nowy EventSource nie wysyła Last-Event-ID): pies ciszy (30 s bez ramki), powrót karty, sieć. Strumień zamknięty
// błędem (odpowiedź inna niż 200) → sprawdzenie sesji: 401 = logowanie z zachowanym hashem, inaczej ponowienie po
// 1, 2, 4, 8, 15 s i pasek „Połączenie przerwane” po 5 s. Migawki (GET z `seq`) nie rwą tekstu: ramki wątku z czasu
// pobierania czekają w buforze i po migawce wchodzą tylko te o kursorze późniejszym niż jej `seq`.
// Bez logowania (127.0.0.1, docs/NATYWNIE.md W11) EventSource nie wyśle nagłówka z tokenem sesji, a Hermes wpuszcza
// wtedy /api/ tylko z nim: lider czyta ten sam strumień przez fetch (ZrodloFetch, ten sam interfejs); jego koniec
// albo błąd sieci to readyState 2 i to samo ponowienie z ?od= co po zamkniętym EventSource.

const WERSJA_PAKIETU = (() => {
  try {
    const m = /app-([0-9a-f]{12})\.js/.exec((document.currentScript && document.currentScript.src) || "");
    return m ? m[1] : null;
  } catch (_) { return null; }
})();

// Strumień SSE przez fetch z nagłówkami panelu (authHeaders: token sesji i X-Jarvo-Request). Interfejs jak EventSource
// w tym pliku: addEventListener(typ, f), onerror, readyState (0 łączy, 1 otwarty, 2 zamknięty), close(), do tego status
// odpowiedzi; zdarzenie ma data i lastEventId (ostatnie id zostaje dla kolejnych zdarzeń bez id, jak w EventSource).
// Parser: „event:”, „data:” (kilka wierszy łączy „\n”), „id:”; komentarze „:” i „retry:” pomijane, pusty wiersz kończy
// zdarzenie. Koniec odpowiedzi, błąd sieci albo status inny niż 200 = readyState 2 i jedno onerror.
class ZrodloFetch {
  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.status = 0;
    this.onerror = null;
    this.lastEventId = "";
    this.sluchacze = new Map();
    this.przerwij = new AbortController();
    this.czytaj();
  }

  addEventListener(typ, f) {
    if (!this.sluchacze.has(typ)) this.sluchacze.set(typ, []);
    this.sluchacze.get(typ).push(f);
  }

  close() {
    this.readyState = 2;
    try { this.przerwij.abort(); } catch (_) { /* już przerwane */ }
  }

  koniec() {
    if (this.readyState === 2) return;
    this.close();
    if (this.onerror) this.onerror({ type: "error" });
  }

  nadaj(typ, data) {
    for (const f of this.sluchacze.get(typ) || []) f({ type: typ, data, lastEventId: this.lastEventId });
  }

  async czytaj() {
    let r;
    try {
      r = await fetch(this.url, { credentials: "include", cache: "no-store", signal: this.przerwij.signal,
        headers: authHeaders({ Accept: "text/event-stream" }) });
    } catch (_) { this.koniec(); return; }
    this.status = r.status;
    if (!r.ok || !r.body || this.readyState === 2) { this.koniec(); return; }
    this.readyState = 1;
    const czytnik = r.body.getReader(), dek = new TextDecoder();
    let bufor = "", typ = "", dane = [];
    try {
      for (;;) {
        const { value, done } = await czytnik.read();
        if (done) break;
        bufor += dek.decode(value, { stream: true });
        for (let i = bufor.indexOf("\n"); i >= 0; i = bufor.indexOf("\n")) {
          const linia = bufor.slice(0, i).replace(/\r$/, "");
          bufor = bufor.slice(i + 1);
          if (!linia) {
            if (dane.length) this.nadaj(typ || "message", dane.join("\n"));
            typ = ""; dane = [];
          } else if (linia[0] !== ":") {
            const d = linia.indexOf(":");
            const pole = d < 0 ? linia : linia.slice(0, d);
            const wartosc = d < 0 ? "" : linia.slice(d + (linia[d + 1] === " " ? 2 : 1));
            if (pole === "event") typ = wartosc;
            else if (pole === "data") dane.push(wartosc);
            else if (pole === "id" && !wartosc.includes("\0")) this.lastEventId = wartosc;
          }
        }
      }
    } catch (_) { /* przerwane: close() albo sieć */ }
    this.koniec();
  }
}

const Strumien = (() => {
  const ZDARZENIA = ["hello", "reset", "kursor", "watek.zmiana", "watek.usuniety", "watek.wpis", "watek.os", "przebieg.stan",
    "przebieg.delta", "przebieg.komentarz", "przebieg.mysl", "przebieg.narzedzie", "przebieg.podagent", "przebieg.zgoda",
    "przebieg.koniec", "przebieg.nadzor", "karta.zmiana", "decyzje.zmiana", "flota.stan", "lista.zmiana", "sesja.os",
    "misje.zmiana", "aktualizacja", "agenci.zmiana", "efekty.zmiana"];
  const CISZA_MS = 30000, PRZERWA_MS = 5000, PONOW_S = [1, 2, 4, 8, 15];
  // karta, która zniknęła bez „zegnaj” (zamrożona, zabita), wypada z sumy: karty co 20 s powtarzają „sub”,
  // a wpis starszy niż 60 s nie liczy się do subskrypcji lidera
  const SUB_CO_MS = 20000, SUB_WAZNY_MS = 60000;
  const losowe = (n) => Array.from(crypto.getRandomValues(new Uint8Array(n)), (b) => (b % 36).toString(36)).join("");
  const karta = `t${losowe(8)}`;
  const moje = new Set();            // wątki tej karty
  const inne = new Map();            // karta → {watki, at}: wątki pozostałych kart (zna je każda karta: nowy lider ma sumę od razu)
  const bufory = new Map();          // wątek → ramki z czasu pobierania migawki
  const kolejkiMigawek = new Map();  // wątek → obietnica poprzedniej migawki (jedna naraz na wątek)
  const haki = new Map();            // typ → Set(fn(dane, ramka))
  const czekajacy = [];              // {watki, ok}: subskrypcje czekające na potwierdzenie lidera
  let dziala = false, bc = null, es = null, lider = false, klient = null, kursor = null, ostatnia = 0;
  let zwolnij = null, przerwij = null, proba = 0, wyslane = "", stan = "laczy";
  let czasCiszy = 0, czasPonow = 0, czasSub = 0, czasPrzerwy = 0, czasPowtorz = 0;

  const watekRamki = (d) => (d && (d.watek_id || (d.przebieg && d.przebieg.watek_id))) || null;
  const nadaj = (m) => { if (bc) bc.postMessage(m); };

  // „Nowa wersja” liczy każda karta sama: lider rozsyła wersję serwera, a karta otwarta przed aktualizacją
  // porównuje ją ze swoją paczką (karta lidera mogła się już przeładować na nową)
  const wersjaSerwera = (w) => (w ? { wersja: w, nowa_wersja: !!(WERSJA_PAKIETU && w !== WERSJA_PAKIETU) } : {});

  function ustawStan(nowy, dodatki) {
    stan = nowy;
    clearTimeout(czasPrzerwy);
    czasPrzerwy = 0;
    sklep.zmien("strumien", { stan: nowy, ...(dodatki || {}) });
    if (lider) { const { nowa_wersja: _n, ...reszta } = dodatki || {}; nadaj({ t: "stan", stan: nowy, kursor, ...reszta }); }
  }

  // ---------------------------------------------------------------------------------------------- stosowanie ramek
  function wykonaj(z) {
    sklep.ustaw((s) => Os.zastosujZdarzenie(s, z.typ, z.dane, z.id));
    for (const typ of [z.typ, "*"]) for (const f of haki.get(typ) || []) { try { f(z.dane, z); } catch (e) { console.error("Jarvo:", e); } }
  }

  function zastosuj(z) {
    const d = z.dane || {};
    if (z.typ === "hello") {
      if (!kursor && d.kursor) kursor = d.kursor;
      ustawStan("ok", { epoka: d.epoka || null, ...wersjaSerwera(d.wersja) });
      wykonaj(z);
      return;
    }
    if (z.id) {
      if (kursor && Os.porownaj(z.id, kursor) <= 0) return;     // już zastosowana (powtórka po zmianie lidera)
      kursor = z.id;
    }
    if (z.typ === "kursor") return;
    const w = watekRamki(d);
    if (w && !moje.has(w)) return;                                 // ramka wątku innej karty
    if (w && bufory.has(w)) { bufory.get(w).push(z); return; }
    wykonaj(z);
  }

  // ---------------------------------------------------------------------------------------------- lider: EventSource
  function zamknijEs() {
    clearTimeout(czasCiszy); clearTimeout(czasPonow);
    if (es) { es.onerror = null; es.close(); es = null; }
  }

  function pilnuj() {
    clearTimeout(czasCiszy);
    czasCiszy = setTimeout(() => { if (lider && dziala) otworz(); }, CISZA_MS);
  }

  function przerwa() {
    if (stan === "przerwany" || czasPrzerwy) return;
    czasPrzerwy = setTimeout(() => { czasPrzerwy = 0; if (Date.now() - ostatnia > PRZERWA_MS) ustawStan("przerwany"); }, PRZERWA_MS);
  }

  function otworz() {
    zamknijEs();
    const watki = [...suma()].sort().slice(0, 200);
    wyslane = watki.join(",");
    const od = kursor ? `&od=${encodeURIComponent(kursor)}` : "";
    const url = `${basePath()}${API_ROOT}/strumien?klient=${klient}&watki=${wyslane}${od}`;
    const zrodlo = es = zTokenem() ? new ZrodloFetch(url) : new EventSource(url);
    for (const typ of ZDARZENIA) {
      zrodlo.addEventListener(typ, (e) => {
        if (zrodlo !== es) return;
        ostatnia = Date.now();
        proba = 0;
        pilnuj();
        let dane = null;
        try { dane = JSON.parse(e.data); } catch (_) { return; }
        // hello bez id: przeglądarka podaje w lastEventId poprzedni kursor, więc go nie bierzemy
        const z = { typ, dane, id: typ === "hello" ? null : e.lastEventId || null };
        nadaj({ t: "ramka", z });
        zastosuj(z);
        if (typ === "hello") { potwierdz(watki); nadaj({ t: "wyslane", watki }); }
      });
    }
    zrodlo.onerror = () => {
      if (zrodlo !== es) return;
      przerwa();
      if (zrodlo.readyState === 2) { zamknijEs(); sprawdz(); }   // CLOSED: przeglądarka sama już nie wznowi
    };
    pilnuj();
  }

  async function sprawdz() {
    let status = 0;
    try {
      status = (await fetch(`${basePath()}${API_ROOT}/update`, { credentials: "include", cache: "no-store", headers: authHeaders() })).status;
    } catch (_) { /* sieć */ }
    if (!dziala || !lider) return;
    if (status === 401) { nadaj({ t: "wyloguj" }); naLogowanie(); return; }
    const s = PONOW_S[Math.min(proba++, PONOW_S.length - 1)];
    czasPonow = setTimeout(() => { if (dziala && lider) otworz(); }, s * 1000);
  }

  // ---------------------------------------------------------------------------------------------- subskrypcje
  function suma() {
    const s = new Set(moje);
    const teraz = Date.now();
    inne.forEach((v) => { if (teraz - v.at <= SUB_WAZNY_MS) v.watki.forEach((w) => s.add(w)); });
    return s;
  }

  function potwierdz(watki) {
    const jest = new Set(watki);
    for (let i = czekajacy.length - 1; i >= 0; i--) {
      if (czekajacy[i].watki.every((w) => jest.has(w))) { czekajacy[i].ok(); czekajacy.splice(i, 1); }
    }
  }

  function planujSub() {
    clearTimeout(czasSub);
    czasSub = setTimeout(async () => {
      if (!lider || !klient) return;
      const watki = [...suma()].sort().slice(0, 200), k = watki.join(",");
      if (k === wyslane) { potwierdz(watki); nadaj({ t: "wyslane", watki }); return; }
      try {
        await api.subskrypcje(klient, { watki });
        wyslane = k;
        potwierdz(watki);
        nadaj({ t: "wyslane", watki });
      } catch (_) { /* następna zmiana albo nowe połączenie wyśle znowu */ }
    }, 100);
  }

  // wątki tej karty; obietnica spełnia się, gdy lider zgłosił je serwerowi (najwyżej 2 s czekania)
  function subskrybuj(watki) {
    moje.clear();
    for (const w of watki || []) moje.add(w);
    const lista = [...moje];
    const obietnica = new Promise((ok) => {
      const wpis = { watki: lista, ok };
      czekajacy.push(wpis);
      setTimeout(() => { const i = czekajacy.indexOf(wpis); if (i >= 0) { czekajacy.splice(i, 1); ok(); } }, 2000);
    });
    if (lider) planujSub();
    else nadaj({ t: "sub", karta, watki: lista });
    return obietnica;
  }

  // ---------------------------------------------------------------------------------------------- migawki
  // pobierz() → odpowiedź z `seq`; wgraj(odpowiedź) wkłada ją do sklepu; potem ramki z bufora późniejsze niż seq
  function migawka(watek, pobierz, wgraj) {
    const poprzednia = kolejkiMigawek.get(watek) || Promise.resolve();
    const ta = poprzednia.catch(() => {}).then(async () => {
      const bufor = [];
      bufory.set(watek, bufor);
      try {
        const wynik = await pobierz();
        wgraj(wynik);
        const seq = wynik && wynik.seq;
        bufory.delete(watek);
        for (const z of bufor) if (!seq || !z.id || Os.porownaj(z.id, seq) > 0) wykonaj(z);
        return wynik;
      } catch (e) {
        bufory.delete(watek);
        bufor.forEach(wykonaj);
        throw e;
      }
    });
    kolejkiMigawek.set(watek, ta);
    ta.finally(() => { if (kolejkiMigawek.get(watek) === ta) kolejkiMigawek.delete(watek); }).catch(() => {});
    return ta;
  }

  // ---------------------------------------------------------------------------------------------- karty i zamek
  function wiadomosc(m) {
    switch (m.t) {
      case "ramka": if (!lider && m.z) zastosuj(m.z); break;
      case "witaj":
        if (!navigator.locks) sklep.zmien("strumien", { wielokarty: true });
      // fall through: nowa karta podaje swoje wątki
      case "sub":
        inne.set(m.karta, { watki: m.watki || [], at: Date.now() });
        if (lider) planujSub();
        if (m.t === "witaj") {
          nadaj({ t: "sub", karta, watki: [...moje] });
          const st = sklep.stan().strumien;
          if (lider) nadaj({ t: "stan", stan, kursor, epoka: st.epoka, ...(st.wersja ? { wersja: st.wersja } : {}) });
        }
        break;
      case "zegnaj": inne.delete(m.karta); if (lider) planujSub(); break;
      case "stan":
        if (lider) break;
        // kursor lidera: nowa karta bez żadnej ramki też przejmie strumień od właściwego miejsca (?od=)
        if (m.kursor && (!kursor || Os.porownaj(m.kursor, kursor) > 0)) kursor = m.kursor;
        sklep.zmien("strumien", { stan: m.stan, ...(m.epoka ? { epoka: m.epoka } : {}), ...wersjaSerwera(m.wersja) });
        break;
      case "wyslane": potwierdz(m.watki || []); break;
      case "wyloguj": naLogowanie(); break;
      default: break;
    }
  }

  function zostanLiderem() {
    if (!dziala) return;
    lider = true;
    klient = `k_${losowe(16)}`;
    sklep.zmien("strumien", { lider: true });
    otworz();
  }

  const ozyw = () => {
    if (lider && dziala && (!es || es.readyState === 2 || Date.now() - ostatnia > CISZA_MS)) otworz();
  };
  const widoczna = () => { if (document.visibilityState === "visible") ozyw(); };
  const zegnaj = () => nadaj({ t: "zegnaj", karta });
  // karta wróciła z pamięci przeglądarki (bfcache): lider jej nie zna, więc wita się jeszcze raz
  const powrot = (e) => { if (e && e.persisted) nadaj({ t: "witaj", karta, watki: [...moje] }); ozyw(); };
  function powtarzaj() {
    clearTimeout(czasPowtorz);
    if (!dziala) return;
    if (!lider) nadaj({ t: "sub", karta, watki: [...moje] });
    else {
      const teraz = Date.now();
      let byly = false;
      inne.forEach((v, k) => { if (teraz - v.at > SUB_WAZNY_MS) { inne.delete(k); byly = true; } });
      if (byly) planujSub();
    }
    czasPowtorz = setTimeout(powtarzaj, SUB_CO_MS);
  }

  function start() {
    if (dziala) return;
    dziala = true;
    if (window.BroadcastChannel) {
      bc = new BroadcastChannel("jarvo");
      bc.onmessage = (e) => wiadomosc(e.data || {});
      nadaj({ t: "witaj", karta, watki: [...moje] });
    }
    document.addEventListener("visibilitychange", widoczna);
    window.addEventListener("online", ozyw);
    window.addEventListener("pageshow", powrot);
    czasPowtorz = setTimeout(powtarzaj, SUB_CO_MS);
    window.addEventListener("pagehide", zegnaj);
    if (!navigator.locks || !bc) {                  // bez zamka albo kanału: każda karta ma własny strumień
      zostanLiderem();
      return;
    }
    const ac = new AbortController();
    przerwij = () => ac.abort();
    navigator.locks.request("jarvo-strumien", { signal: ac.signal }, () => new Promise((ok) => {
      zwolnij = ok;
      zostanLiderem();
    })).catch(() => { /* przerwane przez stop() */ });
  }

  function stop() {
    if (!dziala) return;
    dziala = false;
    zamknijEs();
    clearTimeout(czasSub); clearTimeout(czasPrzerwy);
    zegnaj();
    if (bc) { bc.close(); bc = null; }
    document.removeEventListener("visibilitychange", widoczna);
    window.removeEventListener("online", ozyw);
    window.removeEventListener("pageshow", powrot);
    clearTimeout(czasPowtorz);
    window.removeEventListener("pagehide", zegnaj);
    if (zwolnij) zwolnij();
    if (przerwij) przerwij();
    zwolnij = przerwij = null;
    lider = false;
    klient = null;
    inne.clear();
    sklep.zmien("strumien", { stan: "laczy", lider: false });
    stan = "laczy";
  }

  // hak na zdarzenie (typ albo "*"): skutki uboczne poza sklepem, np. pobranie osi po watek.os
  function naZdarzenie(typ, f) {
    if (!haki.has(typ)) haki.set(typ, new Set());
    haki.get(typ).add(f);
    return () => haki.get(typ).delete(f);
  }

  return { start, stop, subskrybuj, migawka, naZdarzenie, kursor: () => kursor, jestLiderem: () => lider };
})();
