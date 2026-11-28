// Oś floty (#/os[/<dzień>], docs/HQ.md „Oś floty”, 28.11 JARO): każde zlecenie floty jako jedna linia od chwili
// zlecenia do końca, dzień po dniu. Na górze w toku i PYTANIE (od najstarszego startu), niżej reszta dnia od najnowszej;
// linia: godzina startu, „kto → komu”, tytuł, stan (etykieta .j-st jak u rozmówców), urządzenia, czas trwania albo
// „od HH:MM” z upływem tykającym co minutę, wynik skrótem. Klik rozwija pełny wpis (GET /flota/os/{id}: prompt, wynik
// w Markdown, kanał, wywołania, „Otwórz rozmowę”). Wpisy z `rodzic` wcięte pod rodzicem, filtr agentów chipami (po
// stronie przeglądarki, więc chipy pokazują wszystkich agentów dnia). Zdarzenie `flota.os` scala wpisy po id bez
// przeładowania. Dzień z ‹ › i ←/→ po dniach z wpisami (`dni` z serwera), kalendarz z boku jak w Aktualizacjach.
// Pakiet `osfloty` (ten plik) ładuje się po wejściu w widok razem z pakietem `raporty` (kalendarz, daty i ich style);
// własne style w bloku „@@pakiet osfloty” style.css. Dane: GET /flota/os?dzien=, GET /flota/os/{id}.

// ------------------------------------------------------------------------------------------------- teksty
// Teksty widoku idą z pakietem (28.11: rdzeń ponad budżetem gzip); w rdzeniu (04-i18n.js) zostaje tylko „osf.tytul”
// pozycji paska. Oba języki tutaj: pakiet „en” ich nie ma. Testy kluczy czytają te bloki razem z 04-i18n.js.
Object.assign(SLOWNIK.pl, {
  "osf.teraz": "Teraz", "osf.reszta": "Reszta dnia", "osf.caly_dzien": "Zadania dnia",
  "osf.st_w_toku": "w toku", "osf.st_pytanie": "pytanie", "osf.st_gotowe": "gotowe", "osf.st_przerwane": "przerwane", "osf.st_blad": "błąd",
  "osf.od": "od {godz}", "osf.chwila": "<1 min", "osf.min": "{n} min", "osf.godz": "{h} h {m} min",
  "osf.z_telefon": "telefon {nazwa}", "osf.z_komputer": "komputer", "osf.z_pulpit": "pulpit", "osf.rutyna": "rutyna",
  "osf.rodzaj": "Rodzaj", "osf.r_panel": "rozmowa w panelu", "osf.r_karta": "karta", "osf.r_rutyna": "rutyna",
  "osf.r_telegram": "Telegram", "osf.r_omp": "sesja terminala (omp)",
  "osf.kanal": "Kanał", "osf.k_panel": "panel", "osf.k_telegram": "Telegram", "osf.k_lista": "lista zadań",
  "osf.k_cron": "harmonogram (cron)", "osf.k_terminal": "terminal",
  "osf.start": "Start", "osf.koniec": "Koniec", "osf.wywolania": "Wywołania", "osf.urzadzenia": "Urządzenia",
  "osf.prompt": "Prompt", "osf.wynik": "Wynik", "osf.brak_wyniku": "Jeszcze bez wyniku.", "osf.otworz": "Otwórz rozmowę",
  "osf.pod": "podzadanie", "osf.dzien_ma": "{dzien}: są zadania",
  "osf.agenci": "Agenci", "osf.wszyscy": "Wszyscy", "osf.dzis": "Dziś",
  "osf.poprzedni": "Poprzedni dzień z zadaniami (←)", "osf.nastepny": "Następny dzień z zadaniami (→)",
  "osf.pusto": "Tego dnia flota nie miała zadań.", "osf.pusto_filtr": "Wybrani agenci nie mieli tego dnia zadań.",
  "osf.zadania": { one: "{n} zadanie", few: "{n} zadania", many: "{n} zadań", other: "{n} zadania" },
  "osf.w_toku_n": { one: "{n} w toku", few: "{n} w toku", many: "{n} w toku", other: "{n} w toku" },
  "osf.pytania_n": { one: "{n} pytanie", few: "{n} pytania", many: "{n} pytań", other: "{n} pytania" },
});
Object.assign(SLOWNIK.en, {
  "osf.teraz": "Now", "osf.reszta": "Rest of the day", "osf.caly_dzien": "Tasks of the day",
  "osf.st_w_toku": "in progress", "osf.st_pytanie": "question", "osf.st_gotowe": "done", "osf.st_przerwane": "stopped", "osf.st_blad": "error",
  "osf.od": "since {godz}", "osf.chwila": "<1 min", "osf.min": "{n} min", "osf.godz": "{h} h {m} min",
  "osf.z_telefon": "phone {nazwa}", "osf.z_komputer": "computer", "osf.z_pulpit": "desktop", "osf.rutyna": "routine",
  "osf.rodzaj": "Kind", "osf.r_panel": "panel conversation", "osf.r_karta": "card", "osf.r_rutyna": "routine",
  "osf.r_telegram": "Telegram", "osf.r_omp": "terminal session (omp)",
  "osf.kanal": "Channel", "osf.k_panel": "panel", "osf.k_telegram": "Telegram", "osf.k_lista": "task list",
  "osf.k_cron": "schedule (cron)", "osf.k_terminal": "terminal",
  "osf.start": "Start", "osf.koniec": "End", "osf.wywolania": "Calls", "osf.urzadzenia": "Devices",
  "osf.prompt": "Prompt", "osf.wynik": "Result", "osf.brak_wyniku": "No result yet.", "osf.otworz": "Open conversation",
  "osf.pod": "subtask", "osf.dzien_ma": "{dzien}: has tasks",
  "osf.agenci": "Agents", "osf.wszyscy": "All", "osf.dzis": "Today",
  "osf.poprzedni": "Previous day with tasks (←)", "osf.nastepny": "Next day with tasks (→)",
  "osf.pusto": "The fleet had no tasks on this day.", "osf.pusto_filtr": "The selected agents had no tasks on this day.",
  "osf.zadania": { one: "{n} task", other: "{n} tasks" },
  "osf.w_toku_n": { one: "{n} in progress", other: "{n} in progress" },
  "osf.pytania_n": { one: "{n} question", other: "{n} questions" },
});

// trasy osi przy widoku, nie w 10-api.js (28.11: rdzeń ponad budżetem gzip)
const osfApi = {
  lista: (p) => zadanie("GET", `/flota/os${zapytanieUrl(p)}`),     // {dzien, agent} → {dzien, dni, zadania}
  wpis: (id) => zadanie("GET", `/flota/os/${kodujUrl(id)}`),       // → {zadanie}
};

// ------------------------------------------------------------------------------------------------- wpisy (czyste)
// stan wpisu → klasa etykiety `.j-st` (kolory stanów rozmówców: czerwień pracy, pomarańczowe pulsujące pytanie)
const OSF_STANY = { w_toku: "pracuje", pytanie: "czeka", gotowe: "wolny", przerwane: "przerwane", blad: "blad" };
const OSF_ZASOBY = ["telefon", "komputer", "pulpit"];
const OSF_KANALY = ["panel", "telegram", "lista", "cron", "terminal"];
const OSF_RODZAJE = ["panel", "karta", "rutyna", "telegram", "omp"];
const osfAktywny = (w) => w.stan === "w_toku" || w.stan === "pytanie";
// rutyna nie ma startu: jej chwilą jest koniec
const osfStart = (w) => w.start_at || w.koniec_at || 0;

// zasoby wpisu: lista z serwera (albo jej zapis JSON) → ["telefon:first", …]
function osfZasoby(w) {
  let z = w && w.zasoby;
  if (typeof z === "string") { try { z = JSON.parse(z); } catch (_) { z = []; } }
  return Array.isArray(z) ? z.filter((x) => typeof x === "string" && x) : [];
}
// "telefon:first" → „telefon first”, "pulpit" → „pulpit”; nieznany rodzaj zostaje jak jest
function osfNazwaZasobu(z) {
  const i = z.indexOf(":"), rodzaj = i < 0 ? z : z.slice(0, i), nazwa = i < 0 ? "" : z.slice(i + 1);
  return OSF_ZASOBY.includes(rodzaj) ? T(`osf.z_${rodzaj}`, { nazwa }).trim() : z.replace(":", " ");
}

// 40 s → „<1 min”, 1500 s → „25 min”, 3900 s → „1 h 05 min”
function osfTrwanie(sekundy) {
  const s = Math.max(0, Math.floor(sekundy || 0));
  if (s < 60) return T("osf.chwila");
  if (s < 3600) return T("osf.min", { n: Math.floor(s / 60) });
  return T("osf.godz", { h: Math.floor(s / 3600), m: String(Math.floor((s % 3600) / 60)).padStart(2, "0") });
}
// czas wpisu w linii: w toku „od 14:02 · 23 min”, skończony sam czas trwania, rutyna (start = koniec) nic
function osfCzas(w, teraz) {
  if (osfAktywny(w)) return w.start_at ? `${T("osf.od", { godz: Czas.godzina(w.start_at) })} · ${osfTrwanie(teraz - w.start_at)}` : "";
  return w.start_at && w.koniec_at && w.koniec_at > w.start_at ? osfTrwanie(w.koniec_at - w.start_at) : "";
}

// kolejność serwera: w toku i pytanie od najstarszego startu, potem reszta od najnowszej (remis: id, stała kolejność)
const osfPorownaj = (a, b) => {
  const x = osfAktywny(a), y = osfAktywny(b);
  if (x !== y) return x ? -1 : 1;
  const d = x ? osfStart(a) - osfStart(b) : osfStart(b) - osfStart(a);
  return d || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
};
function osfPorzadek(zadania) {
  return (zadania || []).slice().sort(osfPorownaj);
}

// Lista do rysowania: [{w, poziom, aktywna}] w kolejności osi. Wpis, którego rodzic jest na liście, stoi pod nim
// (dzieci od najstarszego startu, poziom + 1); rodzica spoza listy (inny dzień, filtr agenta) nie ma, więc dziecko jest
// zwykłą linią. Grupa (rodzic z potomkami) z czymkolwiek w toku albo z pytaniem idzie na górę cała, bo aktywne dziecko
// pod skończonym rodzicem inaczej ginęłoby w reszcie dnia. Pętla rodziców (błąd danych) nie gubi wpisów.
function osfDrzewo(zadania) {
  const wg = new Map((zadania || []).map((w) => [w.id, w]));
  const wPetli = (w) => {
    const byly = new Set([w.id]);
    for (let r = wg.get(w.rodzic); r; r = wg.get(r.rodzic)) {
      if (r.id === w.id) return true;
      if (byly.has(r.id)) return false;
      byly.add(r.id);
    }
    return false;
  };
  const dzieci = new Map(), korzenie = [];
  for (const w of wg.values()) {
    if (w.rodzic && w.rodzic !== w.id && wg.has(w.rodzic) && !wPetli(w)) {
      if (!dzieci.has(w.rodzic)) dzieci.set(w.rodzic, []);
      dzieci.get(w.rodzic).push(w);
    } else korzenie.push(w);
  }
  const aktywnaGrupa = (w, byly = new Set()) => {
    if (byly.has(w.id)) return false;
    byly.add(w.id);
    return osfAktywny(w) || (dzieci.get(w.id) || []).some((d) => aktywnaGrupa(d, byly));
  };
  const grupy = korzenie.map((w) => ({ w, aktywna: aktywnaGrupa(w) }));
  grupy.sort((a, b) => (a.aktywna !== b.aktywna ? (a.aktywna ? -1 : 1)
    : (a.aktywna ? osfStart(a.w) - osfStart(b.w) : osfStart(b.w) - osfStart(a.w)) || osfPorownaj(a.w, b.w)));
  const out = [], widziane = new Set();
  const dodaj = (w, poziom, aktywna) => {
    if (widziane.has(w.id)) return;
    widziane.add(w.id);
    out.push({ w, poziom, aktywna });
    const d = (dzieci.get(w.id) || []).slice().sort((a, b) => osfStart(a) - osfStart(b) || (a.id < b.id ? -1 : 1));
    for (const x of d) dodaj(x, poziom + 1, aktywna);
  };
  for (const g of grupy) dodaj(g.w, 0, g.aktywna);
  return out;
}

// Zdarzenie `flota.os` ({zadania: [skrót…]}): znany wpis podmieniony po id (starsza zmiana nie cofa nowszej), nowy
// dopisany, gdy należy do oglądanego dnia (wpis w toku zawsze na dzisiejszym widoku). Bez zmian: ta sama tablica.
function osfScal(zadania, nowe, { dzien, dzis }) {
  const wg = new Map((zadania || []).map((w) => [w.id, w]));
  let zmiana = false;
  for (const n of nowe || []) {
    if (!n || !n.id) continue;
    const byl = wg.get(n.id);
    if (byl) {
      if ((n.zmieniono_at || 0) < (byl.zmieniono_at || 0)) continue;
      wg.set(n.id, { ...byl, ...n });
      zmiana = true;
    } else if ((osfStart(n) ? kluczDnia(osfStart(n)) : dzis) === dzien || (dzien === dzis && osfAktywny(n))) {
      wg.set(n.id, n);
      zmiana = true;
    }
  }
  return zmiana ? osfPorzadek([...wg.values()]) : zadania;
}

// sąsiednie dni dla ‹ › i ←/→: dni z wpisami (serwer, malejąco) i dziś; {poprzedni, nastepny} albo null
function osfSasiedzi(dni, dzien, dzis) {
  const wszystkie = [...new Set([...(dni || []), dzis])].filter((k) => k <= dzis).sort();
  return { poprzedni: wszystkie.filter((k) => k < dzien).pop() || null, nastepny: wszystkie.find((k) => k > dzien) || null };
}

// kto zlecił: JARO i Operator wprost, rutyna słowem, agent nazwą w bieżącym języku
const osfKto = (z) => (!z || z === "JARO" || z === "Operator" ? z || "" : z === "rutyna" ? T("osf.rutyna") : nazwaAgenta(z));
const osfSlowo = (znane, przedrostek, v) => (znane.includes(v) ? T(`${przedrostek}${v}`) : v || "");

// ------------------------------------------------------------------------------------------------- linia i rozwinięcie
function OsfPelny({ w, id }) {
  const [pelny, setPelny] = useState(null);
  const [blad, setBlad] = useState(null);
  // pełny wpis przy rozwinięciu i po każdej zmianie wpisu (stan, wynik) ze strumienia
  useEffect(() => {
    let zywy = true;
    osfApi.wpis(w.id).then((d) => { if (zywy) { setPelny((d && d.zadanie) || null); setBlad(null); } },
      (e) => { if (zywy) setBlad(e.message || String(e)); });
    return () => { zywy = false; };
  }, [w.id, w.zmieniono_at]);
  const p = { ...w, ...(pelny || {}) };
  const zasoby = osfZasoby(p);
  const kiedy = (ts) => (ts ? `${Czas.data(ts)}, ${new Date(ts * 1000).toLocaleTimeString(isPL() ? "pl-PL" : "en-GB")}` : "");
  const wynik = p.wynik_pelny || p.wynik || "";
  return html`<div class="j-osf-pelny" id=${id}>
    <dl class="j-osf-dane">
      <dt>${T("osf.rodzaj")}</dt><dd>${osfSlowo(OSF_RODZAJE, "osf.r_", p.rodzaj)}</dd>
      <dt>${T("osf.kanal")}</dt><dd>${osfSlowo(OSF_KANALY, "osf.k_", p.kanal)}</dd>
      ${p.start_at && html`<dt>${T("osf.start")}</dt><dd>${kiedy(p.start_at)}</dd>`}
      ${p.koniec_at && !osfAktywny(p) && html`<dt>${T("osf.koniec")}</dt><dd>${kiedy(p.koniec_at)}</dd>`}
      ${p.wywolania != null && html`<dt>${T("osf.wywolania")}</dt><dd>${p.wywolania}</dd>`}
      ${zasoby.length > 0 && html`<dt>${T("osf.urzadzenia")}</dt><dd>${zasoby.map(osfNazwaZasobu).join(", ")}</dd>`}
      <dt>Id</dt><dd><code>${p.id}</code></dd>
    </dl>
    ${p.watek_id && html`<p class="j-osf-akcje"><a class="j-link" href=${Trasa.zbuduj({ widok: "watek", watek: p.watek_id })}>${T("osf.otworz")} →</a></p>`}
    <h4 class="j-osf-h">${T("osf.prompt")}</h4>
    ${pelny ? html`<pre class="j-osf-prompt">${p.prompt || p.tytul}</pre>`
      : blad ? html`<p class="j-pasek-pusto" role="alert">${blad}</p>` : html`<p class="j-pasek-pusto"><${Spinner}/></p>`}
    <h4 class="j-osf-h">${T("osf.wynik")}</h4>
    ${wynik ? html`<${TrescMd} tekst=${wynik} klasa="j-msg-t"/>` : html`<p class="j-osf-brak">${T("osf.brak_wyniku")}</p>`}
  </div>`;
}

function OsfWiersz({ r, otwarty, przelacz, teraz }) {
  const w = r.w, id = `j-osf-p-${w.id.replace(/[^A-Za-z0-9_-]/g, "_")}`;
  const zasoby = osfZasoby(w).map(osfNazwaZasobu).join(", ");
  const st = OSF_STANY[w.stan] || "przerwane";
  return html`<li class=${cx("j-osf-w", `is-${st}`, r.poziom > 0 && "is-dziecko", otwarty && "is-otwarty")} data-zadanie=${w.id}
      style=${r.poziom > 0 ? { "--j-osf-poziom": Math.min(r.poziom, 4) } : undefined}>
    <button type="button" class="j-osf-l" aria-expanded=${String(otwarty)} aria-controls=${id} onClick=${() => przelacz(w.id)}>
      <time class="j-osf-godz" datetime=${osfStart(w) ? new Date(osfStart(w) * 1000).toISOString() : undefined}>
        ${r.poziom > 0 && html`<span class="j-sr">${T("osf.pod")}: </span>`}${osfStart(w) ? Czas.godzina(osfStart(w)) : ""}</time>
      <span class="j-osf-kto">${osfKto(w.zlecil)} → ${nazwaAgenta(w.agent)}</span>
      <span class="j-osf-tytul" title=${w.tytul}>${w.tytul}</span>
      <em class=${`j-st is-${st}`}>${osfSlowo(Object.keys(OSF_STANY), "osf.st_", w.stan)}</em>
      <span class="j-osf-zas">${zasoby}</span>
      <span class="j-osf-czas">${osfCzas(w, teraz)}</span>
      <span class="j-osf-wynik" title=${w.wynik || undefined}>${w.wynik}</span>
    </button>
    ${otwarty && html`<${OsfPelny} w=${w} id=${id}/>`}
  </li>`;
}

// kalendarz miesiąca wybranego dnia (siatka i style z Aktualizacji): dzień z zadaniami jasny z kropką
function OsfKalendarz({ wybrany, dni, dzis, idzDo }) {
  const [r, m] = wybrany.split("-").map(Number);
  const komorki = useMemo(() => siatkaMiesiaca(r, m - 1), [r, m]);
  const ma = useMemo(() => new Set(dni), [dni]);
  const tytul = new Date(r, m - 1, 1).toLocaleDateString(isPL() ? "pl-PL" : "en-GB", { month: "long", year: "numeric" }).replace(/^./, (z) => z.toUpperCase());
  return html`<div class="j-kal" role="group" aria-label=${T("rap.kalendarz")}>
    <div class="j-kal-g"><b class="j-kal-t" aria-live="polite">${tytul}</b></div>
    <div class="j-kal-siatka">
      ${DNI_TYGODNIA[isPL() ? "pl" : "en"].map((n) => html`<span key=${n} class="j-kal-dt" aria-hidden="true">${n}</span>`)}
      ${komorki.map((c) => html`<button type="button" key=${c.klucz} data-dzien=${c.klucz} disabled=${c.klucz > dzis}
          class=${cx("j-kal-d", !c.wMiesiacu && "is-obok", c.klucz === wybrany && "is-wybrany", c.klucz === dzis && "is-dzis", ma.has(c.klucz) && "is-ma")}
          aria-pressed=${String(c.klucz === wybrany)} aria-current=${c.klucz === dzis ? "date" : undefined}
          aria-label=${ma.has(c.klucz) ? T("osf.dzien_ma", { dzien: nazwaDnia(c.klucz).pod || c.klucz }) : nazwaDnia(c.klucz).pod || c.klucz}
          onClick=${() => idzDo(c.klucz)}>
        <span>${c.dzien}</span><i class="j-kal-kropki" aria-hidden="true">${ma.has(c.klucz) && html`<b class="j-osf-kropka"></b>`}</i>
      </button>`)}
    </div>
  </div>`;
}

// ------------------------------------------------------------------------------------------------- widok
function OsFloty({ trasa }) {
  const dzis = kluczDnia(Date.now() / 1000);
  const [st, setSt] = useState({ zadania: [], dni: [], laduje: true, blad: null });
  const [otwarte, setOtwarte] = useState(() => new Set());
  const [agenci, setAgenci] = useState(() => new Set());        // filtr: puste = wszyscy
  const [teraz, setTeraz] = useState(() => Date.now() / 1000);
  const [kalOtwarty, setKalOtwarty] = useState(false);
  const zywy = useRef(true);
  const lista = useRef(null);
  const numer = useRef(0);                 // ostatnie zapytanie: spóźniona odpowiedź poprzedniego dnia nie wygrywa
  useEffect(() => () => { zywy.current = false; }, []);
  const dzien = trasa.dzien || dzis;

  const wczytaj = async () => {
    const n = ++numer.current;
    setSt((s) => ({ ...s, laduje: true, blad: null }));
    try {
      const d = await osfApi.lista({ dzien: trasa.dzien || undefined });
      if (!zywy.current || n !== numer.current) return;
      setSt({ zadania: osfPorzadek(d.zadania || []), dni: d.dni || [], laduje: false, blad: null });
      setTeraz(Date.now() / 1000);
    } catch (e) {
      if (zywy.current && n === numer.current) setSt((s) => ({ ...s, laduje: false, blad: e.message || String(e) }));
    }
  };
  useEffect(() => { wczytaj(); }, [trasa.dzien]);
  useEffect(() => { if (lista.current) lista.current.scrollTop = 0; }, [trasa.dzien]);

  // żywa oś: zmienione wpisy scalone po id; po ponownym połączeniu strumienia (hello) dzień od nowa, bo zdarzenia
  // z przerwy nie doszły
  const biezacy = useRef({});
  biezacy.current = { dzien, dzis, wczytaj };
  useEffect(() => {
    const zdejmij = [
      Strumien.naZdarzenie("flota.os", (d) => setSt((s) => {
        const b = biezacy.current;
        if (s.laduje && !s.zadania.length) return s;
        const zadania = osfScal(s.zadania, d && d.zadania, { dzien: b.dzien, dzis: b.dzis });
        if (zadania === s.zadania) return s;
        return { ...s, zadania, dni: s.dni.includes(b.dzien) ? s.dni : [b.dzien, ...s.dni] };
      })),
      Strumien.naZdarzenie("hello", () => biezacy.current.wczytaj()),
    ];
    return () => zdejmij.forEach((f) => f && f());
  }, []);

  // upływ zadań w toku tyka co minutę
  const saAktywne = st.zadania.some(osfAktywny);
  useEffect(() => {
    if (!saAktywne) return undefined;
    const t = setInterval(() => setTeraz(Date.now() / 1000), 60000);
    return () => clearInterval(t);
  }, [saAktywne]);

  const idzDo = (k) => { setKalOtwarty(false); Trasa.idz({ widok: "os", dzien: k === dzis ? undefined : k }); };
  const { poprzedni, nastepny } = osfSasiedzi(st.dni, dzien, dzis);
  // ←/→ poprzedni / następny dzień jak w Aktualizacjach (nie w polach tekstowych, menu i oknach)
  const sasiedzi = useRef({});
  sasiedzi.current = { poprzedni, nastepny, idzDo };
  useEffect(() => {
    const klawisz = (e) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], [role=menu], [role=listbox], [role=dialog]")) return;
      const s = sasiedzi.current, cel = e.key === "ArrowLeft" ? s.poprzedni : e.key === "ArrowRight" ? s.nastepny : null;
      if (cel) { e.preventDefault(); s.idzDo(cel); }
    };
    document.addEventListener("keydown", klawisz);
    return () => document.removeEventListener("keydown", klawisz);
  }, []);

  // chipy: agenci dnia od najczęstszego
  const agenciDnia = useMemo(() => {
    const ile = new Map();
    for (const w of st.zadania) ile.set(w.agent, (ile.get(w.agent) || 0) + 1);
    return [...ile].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]))).map(([a]) => a);
  }, [st.zadania]);
  const widoczne = useMemo(() => osfDrzewo(agenci.size ? st.zadania.filter((w) => agenci.has(w.agent)) : st.zadania), [st.zadania, agenci]);
  const naGorze = widoczne.filter((r) => r.aktywna), reszta = widoczne.filter((r) => !r.aktywna);
  const przelacz = (id) => setOtwarte((o) => { const n = new Set(o); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const wybierz = (a) => setAgenci((s) => { const n = new Set(s); if (n.has(a)) n.delete(a); else n.add(a); return n; });

  const nd = nazwaDnia(dzien);
  const wToku = st.zadania.filter((w) => w.stan === "w_toku").length, pytania = st.zadania.filter((w) => w.stan === "pytanie").length;
  const opis = st.zadania.length ? [T("osf.zadania", { n: st.zadania.length }), wToku > 0 && T("osf.w_toku_n", { n: wToku }),
    pytania > 0 && T("osf.pytania_n", { n: pytania })].filter(Boolean).join(" · ") : null;
  const wiersze = (rz) => rz.map((r) => html`<${OsfWiersz} key=${r.w.id} r=${r} otwarty=${otwarte.has(r.w.id)} przelacz=${przelacz} teraz=${teraz}/>`);
  return html`<section class="j-rap j-osf" aria-label=${T("osf.tytul")}>
    <${NaglowekWidoku} ikona=${IKONY_WIDOKOW.os} tytul=${T("osf.tytul")} opis=${opis}>
      <div class="j-rap-nawig">
        ${dzien !== dzis && html`<${Przycisk} rodzaj="cichy" maly klasa="j-rap-najnowsze" onClick=${() => idzDo(dzis)}>${T("osf.dzis")}</${Przycisk}>`}
        <${Przycisk} rodzaj="cichy" ikona="back" etykieta=${T("osf.poprzedni")} disabled=${!poprzedni} onClick=${() => idzDo(poprzedni)}/>
        <button type="button" class="j-rap-data" aria-expanded=${String(kalOtwarty)} aria-controls="jarvo-os-floty-bok" onClick=${() => setKalOtwarty(!kalOtwarty)}>
          <b>${nd.glowna}</b>${nd.pod && html`<small>${nd.pod}</small>`}<${Ikona} n="down" r=${14} klasa="j-rap-data-i"/></button>
        <${Przycisk} rodzaj="cichy" ikona="right" etykieta=${T("osf.nastepny")} disabled=${!nastepny} onClick=${() => idzDo(nastepny)}/>
      </div>
    </${NaglowekWidoku}>
    <div class="j-rap-tresc" ref=${lista}><div class="j-rap-uklad">
      <div class="j-osf-lista">
        ${(agenciDnia.length > 1 || agenci.size > 0) && html`<div class="j-osf-filtr" role="group" aria-label=${T("osf.agenci")}>
          <${Chip} wybrany=${!agenci.size} onClick=${() => setAgenci(new Set())}>${T("osf.wszyscy")}</${Chip}>
          ${[...agenciDnia, ...[...agenci].filter((a) => !agenciDnia.includes(a))].map((a) => html`<${Chip} key=${a} wybrany=${agenci.has(a)}
            onClick=${() => wybierz(a)}>${nazwaAgenta(a)}</${Chip}>`)}
        </div>`}
        ${naGorze.length > 0 && html`<h2 class="j-osf-sekcja">${T("osf.teraz")}</h2><ul class="j-osf-ul">${wiersze(naGorze)}</ul>`}
        ${reszta.length > 0 && html`<h2 class="j-osf-sekcja">${T(dzien === dzis ? "osf.reszta" : "osf.caly_dzien")}</h2><ul class="j-osf-ul">${wiersze(reszta)}</ul>`}
        ${st.blad && html`<p class="j-pasek-pusto" role="alert">${st.blad}
          <button type="button" class="j-link" onClick=${() => wczytaj()}>${T("ui.ponow")}</button></p>`}
        ${!st.blad && !st.laduje && !widoczne.length && html`<${Pusto} ikona=${IKONY_WIDOKOW.os} tytul=${T(agenci.size ? "osf.pusto_filtr" : "osf.pusto")}/>`}
        ${st.laduje && !st.zadania.length && html`<p class="j-pasek-pusto"><${Spinner}/></p>`}
      </div>
      <aside class=${cx("j-rap-bok", kalOtwarty && "is-otwarty")} id="jarvo-os-floty-bok">
        <${OsfKalendarz} wybrany=${dzien} dni=${st.dni} dzis=${dzis} idzDo=${idzDo}/>
      </aside>
    </div></div>
  </section>`;
}

// rdzeń montuje widok przez Zasoby.wez("OsFloty") po wczytaniu pakietu (docs/HQ.md „Pakiety”)
if (typeof Zasoby !== "undefined" && Zasoby.daj) Zasoby.daj({ OsFloty, osfPorzadek, osfDrzewo, osfScal, osfSasiedzi });
