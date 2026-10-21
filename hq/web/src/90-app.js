// Aplikacja Jarvo (wersja 2, docs/HQ.md „Aplikacja”): jeden czat na pierwszym planie, rozmowy po lewej, ustawienia
// w szufladzie z prawej, ekran startu w 38-start.js. Korzeń ma data-jarvo-korzen i leży nad całym dashboardem
// (position: fixed); na <html> stawia data-jarvo-app (powłoka Hermesa znika, reszta strony dostaje inert) i po
// pierwszym widoku data-jarvo-gotowe (zasłona startowa znika). Widoki z trasy (03-trasa.js): start, nowa, wątek,
// sesja; szuflada z ?u=.

// ---- paski stanu nad wszystkim (spec §13.12): „Łączę ponownie…” (strumień przerwany od 5 s; pisać można dalej),
// aktualizacja w toku (neutralnie, bez czerwieni), awaria silnika, nieudane wczytanie aplikacji z ponowieniem,
// nowa wersja z „Odśwież” i kilka kart bez zamka
function Pasy() {
  const st = useSklep((s) => s.strumien, plytko);
  const silnik = useSklep((s) => s.silnik);
  const aktualizuje = useSklep((s) => !!(s.aktualizacja && s.aktualizacja.state === "updating"));
  const bladApp = useSklep((s) => s.blad_aplikacji);
  const odswiez = [T("ui.odswiez"), () => location.reload()];
  const pasy = [];
  if (aktualizuje) pasy.push(["aktualizacja", T("pasy.aktualizacja"), null]);
  else if (st.stan === "przerwany") pasy.push(["polaczenie", T("pasy.przerwane"), null]);
  if (silnik === "awaria" && !aktualizuje) pasy.push(["silnik", T("pasy.silnik"), odswiez]);
  if (bladApp) pasy.push(["aplikacja", T("pasy.aplikacja"), [T("ui.ponow"), () => akcje.wczytajAplikacje()]]);
  if (st.nowa_wersja) pasy.push(["wersja", T("pasy.nowa_wersja"), odswiez]);
  if (st.wielokarty) pasy.push(["karty", T("pasy.wielokarty"), null]);
  if (!pasy.length) return null;
  return html`<div class="j-pasy" role="status">${pasy.map(([k, tekst, akcja]) => html`<div key=${k} class=${`j-pas is-${k}`} data-pas=${k}>
    ${(k === "polaczenie" || k === "aktualizacja") && html`<${Spinner}/>`}<span>${tekst}</span>
    ${akcja && html`<button type="button" class="j-link" onClick=${akcja[1]}>${akcja[0]}</button>`}</div>`)}</div>`;
}

// Nowa wersja (hello.wersja ≠ pakiet tej karty, spec §15.3): karta schowana, bez szkicu, bez wiadomości w drodze
// i bez pracy w toku w swoich wątkach odświeża się sama (szkice i tak zostają w localStorage); inaczej zostaje pasek
// „Odśwież”. Sprawdzenie przy zmianie, przy schowaniu karty i co 30 s, z drugim sprawdzeniem po 2 s. Jedno
// samodzielne odświeżenie na wersję serwera (sessionStorage), więc rozjechany pakiet nie zapętli odświeżania.
function kartaBezczynna() {
  const s = sklep.stan();
  if (Object.values(s.wysylane).some((l) => (l || []).length)) return false;
  if (Os.doZatrzymania(Object.values(s.przebiegi)).length) return false;
  const sz = s.szkice[Trasa.biezaca().watek || "nowa"];
  if (sz && (String(sz.tekst || "").trim() || (sz.pliki || []).length)) return false;
  return ![...document.querySelectorAll("[data-jarvo-korzen] [data-kompozytor]")].some((el) => String(el.value || "").trim());
}

function useNowaWersja() {
  const nowa = useSklep((s) => s.strumien.nowa_wersja);
  useEffect(() => {
    if (!nowa) return undefined;
    let t = 0;
    const wersja = () => String(sklep.stan().wersja || "");
    const juz = () => { try { return sessionStorage.getItem("jarvo.odswiezono_dla") === wersja(); } catch (_) { return true; } };
    const sprobuj = () => {
      clearTimeout(t);
      if (document.visibilityState !== "hidden" || juz() || !kartaBezczynna()) return;
      t = setTimeout(() => {
        if (document.visibilityState !== "hidden" || juz() || !kartaBezczynna()) return;
        try { sessionStorage.setItem("jarvo.odswiezono_dla", wersja()); } catch (_) { return; }
        location.reload();
      }, 2000);
    };
    sprobuj();
    const co = setInterval(sprobuj, 30000);
    document.addEventListener("visibilitychange", sprobuj);
    return () => { clearTimeout(t); clearInterval(co); document.removeEventListener("visibilitychange", sprobuj); };
  }, [nowa]);
}

// Stan aktualizacji (odznaka „⬆ N”, System): GET /update co minutę (karta schowana: tylko gdy coś trwa), co 5 s
// w trakcie i przy czekaniu na koniec pracy. Po 2 h czekania jedno przypomnienie na przeglądarkę (spec §15.3).
function useStanAktualizacji() {
  const poPracy = useSklep((s) => (s.aktualizacja && s.aktualizacja.po_pracy) || null);
  useEffect(() => {
    let t = 0, zyje = true;
    const krok = () => {
      const a = sklep.stan().aktualizacja || {};
      const szybko = a.state === "updating" || a.pending || !!a.po_pracy;
      t = setTimeout(async () => {
        if (szybko || document.visibilityState !== "hidden") await akcje.wczytajAktualizacje();
        if (zyje) krok();
      }, szybko ? 5000 : 60000);
    };
    krok();
    return () => { zyje = false; clearTimeout(t); };
  }, []);
  useEffect(() => {
    if (!poPracy || Pamiec.wez("jarvo.akt_przypomniano", null) === poPracy) return undefined;
    const t = setTimeout(() => {
      Pamiec.daj("jarvo.akt_przypomniano", poPracy);
      Komunikaty.pokaz(T("akt.wciaz_czeka"), { czas: 12000 });
    }, Math.max(0, (poPracy + 7200 - Date.now() / 1000) * 1000));
    return () => clearTimeout(t);
  }, [poPracy]);
}

// ---- Stara Baza na cały ekran (Ustawienia › Stara Baza); skróty aplikacji milkną, edytor ma własne
function OknoStarejBazy() {
  const ref = useRef(null);
  const naStart = useSklep((s) => (s.stara_baza === "decyzje" ? "decyzje" : null));
  // wyjście: fokus do kompozytora (przycisk, który ją otworzył, był w zamkniętej już szufladzie)
  const zamknij = () => { Fokus.odloz("kompozytor"); sklep.ustaw({ stara_baza: false }); };
  useEffect(() => {
    Skroty.wstrzymaj(true);
    if (ref.current) ref.current.focus();
    // Esc wraca do Jarva, chyba że pisze się w polu albo otwarte jest okno samej Starej Bazy
    const esc = (e) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      const a = document.activeElement;
      if (a && (/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) || a.isContentEditable)) return;
      if (ref.current && ref.current.querySelector('[role="dialog"], .thq-modal')) return;
      e.preventDefault();
      zamknij();
    };
    document.addEventListener("keydown", esc);
    return () => { Skroty.wstrzymaj(false); document.removeEventListener("keydown", esc); };
  }, []);
  return html`<div class="j-stara" role="dialog" aria-modal="true" aria-label=${T("szuflada.stara-baza")} ref=${ref} tabIndex="-1">
    <div class="j-stara-g"><${Przycisk} maly ikona="back" onClick=${zamknij}>${T("stara.wroc")}</${Przycisk}>
      <span>${T("szuflada.stara-baza")}</span></div>
    <div class="j-stara-t"><${StaraBaza} wlasnyNaglowek=${true} naStart=${naStart}/></div>
  </div>`;
}

function Gora({ trasa }) {
  const watek = useSklep((s) => (trasa.watek ? s.watki[trasa.watek] || (s.lista.wg_klucza[`w:${trasa.watek}`] || {}).watek : null));
  const otwarty = useSklep((s) => s.pasek.otwarty);
  const [edycja, setEdycja] = useState(false);
  useEffect(() => setEdycja(false), [trasa.watek]);
  const wWatku = trasa.widok === "watek";
  const tytul = wWatku ? (watek && watek.tytul) || T("watek.bez_tytulu") : "";
  // nagłówek h1 tylko w wątku (na starcie jest h1 powitania); tabIndex -1: tu wraca fokus po zmianie nazwy
  return html`<header class=${cx("j-gora", wWatku && "is-watek")}>
    <${Przycisk} rodzaj="cichy" ikona="menu" etykieta=${T("pasek.pokaz")} klasa="j-menu-btn" aria-expanded=${String(!!otwarty)}
      aria-controls="jarvo-pasek" onClick=${() => sklep.zmien("pasek", (p) => ({ ...p, otwarty: true, zwiniety: false }))}/>
    ${wWatku && watek && edycja ? html`<${EdycjaTytulu} watek=${watek} onKoniec=${() => setEdycja(false)} klasa="j-gora-pole" fokusPo=".j-gora-t"/>`
      : tytul ? html`<h1 class="j-gora-t" tabIndex="-1" onDoubleClick=${() => watek && !watek.usuniety_at && setEdycja(true)}>${tytul}</h1>` : null}
    ${wWatku && watek && watek.usuniety_at && html`<span class="j-tag">${T("watek.w_koszu_tag")}</span>`}
    <span class="j-rozpych"></span>
    ${wWatku && watek && html`<${MenuWatku} watek=${watek} onZmienNazwe=${() => setEdycja(true)}/>`}
    <${Przycisk} rodzaj="cichy" ikona="gear" etykieta=${T("pasek.ustawienia")} klasa="j-gora-ust"
      onClick=${() => Trasa.idz({ u: "ustawienia", pod: undefined }, { scal: true })}/>
  </header>`;
}

// regiony do F6 / Shift+F6: pasek → główna → szuflada
function przejdzRegion(wstecz) {
  const r = [...document.querySelectorAll("[data-jarvo-korzen] [data-region]")].filter((x) => x.offsetParent !== null);
  if (!r.length) return;
  const i = r.findIndex((x) => x.contains(document.activeElement));
  const cel = r[(i + (wstecz ? -1 : 1) + r.length) % r.length];
  (cel.querySelector("[data-fokus]") || cel).focus();
}

function useSkrotyAplikacji() {
  useEffect(() => {
    const doWatku = (krok) => {
      const s = sklep.stan(), t = Trasa.biezaca();
      const ids = s.lista.porzadek.map((k) => s.lista.wg_klucza[k].watek.id);
      if (!ids.length) return;
      const i = ids.indexOf(t.watek);
      const j = i < 0 ? (krok > 0 ? 0 : ids.length - 1) : Math.max(0, Math.min(ids.length - 1, i + krok));
      if (ids[j] === t.watek) return;
      Fokus.odloz("kompozytor");
      Trasa.idz({ widok: "watek", watek: ids[j] });
    };
    const usun = [
      Skroty.dodaj({ komb: "Mod+Shift+O", opis: "skroty.nowa", akcja: () => Trasa.idz({ widok: "start" }) }),
      Skroty.dodaj({ komb: "Mod+Shift+S", opis: "skroty.pasek", akcja: () => sklep.zmien("pasek", (p) => (window.innerWidth < 1024
        ? { ...p, otwarty: !p.otwarty } : { ...p, zwiniety: !p.zwiniety })) }),
      Skroty.dodaj({ komb: "Mod+,", opis: "skroty.ustawienia", akcja: () => Trasa.idz({ u: "ustawienia", pod: undefined }, { scal: true }) }),
      Skroty.dodaj({ komb: "Mod+/", opis: "skroty.pomoc", akcja: () => Trasa.idz({ u: "konto", pod: undefined }, { scal: true }) }),
      Skroty.dodaj({ komb: "Alt+ArrowUp", opis: "skroty.poprzedni", akcja: () => doWatku(-1) }),
      Skroty.dodaj({ komb: "Alt+ArrowDown", opis: "skroty.nastepny", akcja: () => doWatku(1) }),
      Skroty.dodaj({ komb: "F6", opis: "skroty.region", wPolu: true, akcja: () => przejdzRegion(false) }),
      Skroty.dodaj({ komb: "Shift+F6", opis: "skroty.region_wstecz", wPolu: true, akcja: () => przejdzRegion(true) }),
      Skroty.dodaj({ komb: "/", opis: "skroty.pisz", akcja: () => {
        const el = document.querySelector("[data-jarvo-korzen] [data-kompozytor]") || document.querySelector("[data-jarvo-korzen] [data-szukaj]");
        if (el) el.focus();
      } }),
    ];
    return () => usun.forEach((f) => f());
  }, []);
}

function AppJarvo() {
  const i18n = useHostI18n();
  HQ_LANG = (i18n && i18n.locale) || null;
  const trasa = useTrasa();
  const motyw = useMotyw(useSklep((s) => s.ustawienia.motyw));
  const pasek = useSklep((s) => s.pasek, plytko);
  const staraBaza = useSklep((s) => s.stara_baza);
  const korzen = useRef(null), uklad = useRef(null);
  useWidokTelefonu(korzen);
  useSkrotyAplikacji();
  useNowaWersja();
  useStanAktualizacji();

  React.useLayoutEffect(() => {
    const d = document.documentElement;
    d.setAttribute("data-jarvo-app", "");
    d.setAttribute("data-jarvo-gotowe", "");
    const t = setTimeout(() => d.removeAttribute("data-jarvo-wstepnie"), 200);
    if (window.performance && performance.mark) performance.mark("jarvo:gotowe");
    Trasa.przywroc();
    Strumien.start();
    akcje.wczytajAplikacje();
    akcje.wczytajListe();
    const haki = [
      Strumien.naZdarzenie("reset", () => akcje.wczytajListe()),
      Strumien.naZdarzenie("agenci.zmiana", () => akcje.wczytajAplikacje()),
    ];
    return () => {
      clearTimeout(t);
      haki.forEach((f) => f());
      Strumien.stop();
      ["data-jarvo-app", "data-jarvo-gotowe", "data-jarvo-wstepnie"].forEach((a) => d.removeAttribute(a));
    };
  }, []);

  // przejście w inne miejsce zamyka wysunięty pasek (telefon); ostatni wątek zostaje w pamięci przeglądarki
  useEffect(() => {
    sklep.zmien("pasek", { otwarty: false });
    if (trasa.watek) Pamiec.daj("jarvo.ostatni_watek", trasa.watek);
  }, [trasa.widok, trasa.watek]);

  // gotowość (karta na starcie): świeża po zamknięciu szuflady (model mógł zostać połączony) i co 10 s, dopóki brama
  // nie odpowiada
  const brama = useSklep((s) => (s.gotowosc && s.gotowosc.brama) || null);
  const bylaSzuflada = useRef(false);
  useEffect(() => {
    if (bylaSzuflada.current && !trasa.u) akcje.wczytajAplikacje();
    bylaSzuflada.current = !!trasa.u;
  }, [trasa.u]);
  useEffect(() => {
    if (!brama || brama === "ok") return undefined;
    const t = setInterval(() => akcje.wczytajAplikacje(), 10000);
    return () => clearInterval(t);
  }, [brama]);

  // pod warstwą (szuflada, Stara Baza) układ jest nieaktywny: Tab i czytnik zostają w warstwie. Efekt układu, bo
  // zamykana warstwa oddaje fokus w swoim sprzątaniu (efekt zwykły), a do elementu z inert fokus nie wróci.
  const warstwa = !!trasa.u || staraBaza;
  React.useLayoutEffect(() => { Bezwladnosc.warstwa(warstwa); }, [warstwa]);
  // wysunięty pasek na telefonie jest warstwą: treść obok nieaktywna, Esc zamyka, fokus wraca do przycisku menu
  const pasekWarstwa = useWaskiEkran() && pasek.otwarty;
  React.useLayoutEffect(() => { Bezwladnosc.pasek(pasekWarstwa); }, [pasekWarstwa]);
  // <main> powłoki Hermesa nad aplikacją: bez roli, żeby czytnik nie widział dwóch głównych obszarów
  React.useLayoutEffect(() => {
    const m = korzen.current && korzen.current.parentElement && korzen.current.parentElement.closest("main");
    if (!m || m.hasAttribute("role")) return undefined;
    m.setAttribute("role", "none");
    return () => m.removeAttribute("role");
  }, []);

  const widok = trasa.widok === "watek" ? html`<${Watek} key=${trasa.watek} id=${trasa.watek}/>`
    : trasa.widok === "sesja" ? html`<${Pusto} ikona="msg" tytul=${T("sesja.wkrotce")}/>`
      : html`<${EkranStartu} key=${trasa.agent || "start"} agent=${trasa.widok === "nowa" ? trasa.agent : null}/>`;
  return html`<div class="jarvo-app" data-jarvo-korzen="" data-motyw=${motyw} lang=${isPL() ? "pl" : "en"} ref=${korzen}>
    <div class=${cx("j-uklad", pasek.zwiniety && "is-zwiniety", pasek.otwarty && "is-wysuniety")} ref=${uklad}>
      <${Pasek} trasa=${trasa} warstwa=${pasekWarstwa}/>
      <div class="j-zaslona-paska" onClick=${() => sklep.zmien("pasek", { otwarty: false })}></div>
      <main class="j-glowna" data-region="glowna" tabIndex="-1" aria-label=${T("glowna.etykieta")}>
        <${Gora} trasa=${trasa}/>
        ${widok}
      </main>
    </div>
    ${trasa.u && html`<${Szuflada} trasa=${trasa}/>`}
    ${staraBaza && html`<${OknoStarejBazy}/>`}
    <${PodgladPliku}/>
    <${OknoPytania}/>
    <${Pasy}/>
    <${Toasty}/>
  </div>`;
}

// Zakładkę /jarvo rejestruje loader (dist/index.js ze scripts/hqbuild.py): wczytuje ten pakiet dopiero na /jarvo
// i owija App w osłonę błędów. Wersja 2: aplikacja sama chowa powłokę Hermesa i zdejmuje zasłonę startową.
window.__JARVO_APP__ = { App: AppJarvo, StaraBaza, wersja: 2 };
