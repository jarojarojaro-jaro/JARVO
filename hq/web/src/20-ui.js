// Prymitywy interfejsu aplikacji (docs/HQ.md „Aplikacja”): Ikona, Przycisk, Chip, Awatar, ZnakStanu, Podpowiedz,
// Menu, Okno, Arkusz, Toasty, Spinner, Klawisz, Pusto i Warstwy (stos warstw: Esc zamyka tylko tę na wierzchu,
// fokus wraca do przycisku, który ją otworzył, Tab nie wychodzi z okna). Klasy z przedrostkiem j-, tokeny --j-*.

const Warstwy = (() => {
  const stos = [];
  const naKlawisz = (e) => {
    if (e.key !== "Escape" || !stos.length || e.defaultPrevented) return;
    e.preventDefault();
    stos[stos.length - 1].zamknij();
  };
  function dodaj(zamknij) {
    const w = { zamknij };
    if (!stos.length) document.addEventListener("keydown", naKlawisz);
    stos.push(w);
    return () => {
      const i = stos.indexOf(w);
      if (i >= 0) stos.splice(i, 1);
      if (!stos.length) document.removeEventListener("keydown", naKlawisz);
    };
  }
  return { dodaj, ile: () => stos.length };
})();

// Fokus odłożony na po zmianie widoku: akcja (wysłanie ze startu, odpowiedź na zgodę, kosz, Alt+↑/↓, wyjście ze Starej
// Bazy, „Napisz” w Zespole) mówi, dokąd ma trafić fokus, gdy nowy widok się wyrenderuje. Cel: "kompozytor" albo
// selektor CSS; próby co 60 ms przez najwyżej 1,5 s. Zamykana warstwa nie oddaje wtedy fokusu swojemu przyciskowi.
const Fokus = (() => {
  const CELE = { kompozytor: "[data-kompozytor]" };
  let cel = null, od = 0, t = 0;
  function sprobuj() {
    clearTimeout(t);
    if (!cel || Date.now() - od > 1500) { cel = null; return; }
    const el = [...document.querySelectorAll(CELE[cel] || cel)].find((x) => x.offsetParent !== null && !x.closest("[inert]"));
    if (el) {
      if (!el.matches(FOKUSOWALNE) && !el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");   // nagłówek, linia
      el.focus({ preventScroll: true }); if (document.activeElement === el) { cel = null; return; } }
    t = setTimeout(sprobuj, 60);
  }
  return {
    odloz(c) { cel = c; od = Date.now(); clearTimeout(t); t = setTimeout(sprobuj, 30); },
    czeka: () => !!cel && Date.now() - od <= 1500,
  };
})();

const FOKUSOWALNE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),iframe,[tabindex]:not([tabindex="-1"])';

// warstwa otwarta: Esc ją zamyka, fokus wchodzi do środka i wraca po zamknięciu, Tab krąży w środku
function useWarstwa(otwarta, zamknij, ref, { pulapka = true } = {}) {
  const z = useRef(zamknij);
  z.current = zamknij;
  useEffect(() => {
    if (!otwarta) return undefined;
    const poprzedni = document.activeElement;
    const usun = Warstwy.dodaj(() => z.current());
    const el = ref && ref.current;
    if (el && !el.contains(document.activeElement)) {
      ([...el.querySelectorAll("[data-fokus]")].find((x) => x.offsetParent !== null) || el).focus({ preventScroll: true });
    }
    const tab = (e) => {
      if (!pulapka || e.key !== "Tab" || !el) return;
      const f = [...el.querySelectorAll(FOKUSOWALNE)].filter((x) => x.offsetParent !== null || x === document.activeElement);
      if (!f.length) return;
      const a = document.activeElement;
      if (e.shiftKey && (a === f[0] || a === el)) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && a === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    };
    if (el) el.addEventListener("keydown", tab);
    return () => {
      usun();
      if (el) el.removeEventListener("keydown", tab);
      // fokus wraca do przycisku tylko wtedy, gdy był w warstwie (albo spadł na <body>); gdy właściciel przeszedł
      // Tabem albo kliknięciem gdzie indziej, zostaje tam
      const a = document.activeElement, wSrodku = !a || a === document.body || (el && el.contains(a));
      if (wSrodku && !Fokus.czeka() && poprzedni && poprzedni.focus && document.contains(poprzedni)) poprzedni.focus({ preventScroll: true });
    };
  }, [otwarta]);
}

function Ikona({ n, r = 18, klasa }) {
  const d = IKONY[n];
  if (!d) return null;
  const pelna = IKONY_PELNE.has(n);
  return html`<svg class=${cx("j-i", klasa)} viewBox="0 0 24 24" width=${r} height=${r} aria-hidden="true" focusable="false">
    <path d=${d} fill=${pelna ? "currentColor" : "none"} stroke=${pelna ? "none" : "currentColor"}/></svg>`;
}

const Podpowiedz = ({ tekst }) => html`<span class="j-tip" aria-hidden="true">${tekst}</span>`;

// rodzaj: zwykly | glowny (karmazyn: Wyślij, Opublikuj) | mocny | cichy | niebezpieczny. Bez treści = sama ikona:
// wtedy etykieta (albo podpowiedź) staje się aria-label, a podpowiedź pokazuje się po najechaniu i przy fokusie.
function Przycisk({ rodzaj = "zwykly", maly, ikona, etykieta, podpowiedz, klasa, children, ...reszta }) {
  const sama = children == null || children === false;
  if (sama && !podpowiedz) podpowiedz = etykieta;   // sama ikona: nazwa widać po najechaniu i przy fokusie
  return html`<button type="button" class=${cx("j-btn", `j-btn-${rodzaj}`, maly && "is-maly", sama && "is-ikona", podpowiedz && "j-ma-tip", klasa)}
    aria-label=${sama ? etykieta || podpowiedz : etykieta} ...${reszta}>
    ${ikona && html`<${Ikona} n=${ikona} r=${maly ? 16 : 18}/>`}${!sama && children}
    ${podpowiedz && html`<${Podpowiedz} tekst=${podpowiedz}/>`}
  </button>`;
}

const Chip = ({ wybrany, ikona, children, klasa, ...reszta }) => html`<button type="button"
  class=${cx("j-chip", klasa)} aria-pressed=${wybrany == null ? undefined : String(!!wybrany)} ...${reszta}>
  ${ikona && html`<${Ikona} n=${ikona} r=${16}/>`}${children}</button>`;

const Spinner = ({ r = 12 }) => html`<span class="j-spin" style=${{ width: `${r}px`, height: `${r}px` }} aria-hidden="true"></span>`;

// stan nigdy nie jest samym kolorem: kształt (kropka, kręciołek, trójkąt) i tekst dla czytnika ekranu
function ZnakStanu({ stan }) {
  if (!stan || stan === "cisza" || stan === "wolny") return null;
  const ksztalt = stan === "czeka" ? html`<span class="j-kropka"></span>`
    : stan === "pracuje" ? html`<${Spinner} r=${10}/>` : html`<${Ikona} n="alert" r=${14}/>`;
  return html`<span class=${cx("j-stan", `j-stan-${stan}`)} title=${T(`stan.${stan}`)}>${ksztalt}<span class="j-sr">${T(`stan.${stan}`)}</span></span>`;
}

function Awatar({ agent, r = 28, stan, klasa }) {
  // figurka z pokoju agenta na tle jego ściany (22-figurka.js); ta sama w liście, wątku, kompozytorze i na starcie
  const a = agent || {};
  const pokoj = pokojAgenta(a);
  return html`<span class=${cx("j-awatar", klasa)} data-pokoj=${pokoj} style=${{ "--s": `${r}px`, "--sciana": scianaAgenta(a) }}>
    <svg class="j-awatar-f" viewBox="2 0 20 20" aria-hidden="true" focusable="false">${rysunekFigurki(pokoj)}</svg>
    <${ZnakStanu} stan=${stan}/></span>`;
}

const Klawisz = ({ k }) => html`<kbd class="j-kbd">${Skroty.opis(k)}</kbd>`;

const Pusto = ({ ikona, tytul, children }) => html`<div class="j-pusto">
  ${ikona && html`<${Ikona} n=${ikona} r=${22}/>`}${tytul && html`<p class="j-pusto-t">${tytul}</p>`}${children}</div>`;

// menu podręczne: role=menu, strzałki, Home/End, Esc i klik obok zamykają; kotwica = element albo DOMRect
function Menu({ kotwica, pozycje, onZamknij, etykieta }) {
  const ref = useRef(null);
  useWarstwa(true, onZamknij, ref, { pulapka: false });   // Tab zamyka menu (wzorzec ARIA), nie krąży w nim
  const r = kotwica && (kotwica.getBoundingClientRect ? kotwica.getBoundingClientRect() : kotwica);
  const [gora, setGora] = useState(null);
  const miejsce = r ? { top: gora != null ? gora : Math.min(r.bottom + 4, window.innerHeight - 16), left: Math.max(8, Math.min(r.left, window.innerWidth - 248)) } : {};
  // menu przy dolnej krawędzi (kompozytor, karta pliku, koniec listy) otwiera się nad kotwicą
  React.useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !r) return;
    const h = el.offsetHeight, dol = window.innerHeight - 8;
    if (r.bottom + 4 + h <= dol) return;
    setGora(r.top - 4 - h >= 8 ? r.top - 4 - h : Math.max(8, dol - h));
  }, []);
  useEffect(() => {
    const el = ref.current;
    const pierwszy = el && el.querySelector('[role="menuitem"]');
    if (pierwszy) pierwszy.focus();
    const obok = (e) => { if (el && !el.contains(e.target)) onZamknij(); };
    const t = setTimeout(() => document.addEventListener("pointerdown", obok), 0);
    return () => { clearTimeout(t); document.removeEventListener("pointerdown", obok); };
  }, []);
  const klawisz = (e) => {
    const p = [...ref.current.querySelectorAll('[role="menuitem"]:not([disabled])')];
    const i = p.indexOf(document.activeElement);
    if (e.key === "Tab") { e.preventDefault(); onZamknij(); return; }
    const cel = { ArrowDown: p[(i + 1) % p.length], ArrowUp: p[(i - 1 + p.length) % p.length], Home: p[0], End: p[p.length - 1] }[e.key];
    if (cel) { e.preventDefault(); cel.focus(); }
  };
  return html`<div class="j-menu" role="menu" aria-label=${etykieta} ref=${ref} tabIndex="-1" style=${miejsce} onKeyDown=${klawisz}>
    ${pozycje.map((p, i) => (p.oddzielnik ? html`<hr key=${i}/>` : html`<button key=${p.id || i} type="button" role="menuitem"
      class=${cx("j-menu-p", p.niebezpieczna && "is-niebezpieczna")} disabled=${p.wylaczona}
      onClick=${() => { onZamknij(); p.akcja(); }}>${p.ikona && html`<${Ikona} n=${p.ikona} r=${16}/>`}<span>${p.tekst}</span></button>`))}
  </div>`;
}

// okno dialogowe na środku (na telefonie pełny ekran)
function Okno({ tytul, onZamknij, children, stopka, klasa }) {
  const ref = useRef(null);
  useWarstwa(true, onZamknij, ref);
  React.useLayoutEffect(() => { Bezwladnosc.okno(1); return () => Bezwladnosc.okno(-1); }, []);
  return html`<div class="j-scrim" onClick=${onZamknij}></div>
    <div class=${cx("j-okno", klasa)} role="dialog" aria-modal="true" aria-label=${tytul} ref=${ref} tabIndex="-1">
      <header class="j-okno-g"><h2>${tytul}</h2>
        <${Przycisk} rodzaj="cichy" ikona="x" etykieta=${T("ui.zamknij")} onClick=${onZamknij}/></header>
      <div class="j-okno-t">${children}</div>${stopka && html`<footer class="j-okno-s">${stopka}</footer>`}
    </div>`;
}

// arkusz z prawej (szuflada ustawień, podgląd na telefonie): pod nim zasłona, na telefonie cały ekran
function Arkusz({ tytul, onZamknij, children, klasa, ...reszta }) {
  const ref = useRef(null);
  useWarstwa(true, onZamknij, ref);
  return html`<div class="j-scrim" onClick=${onZamknij}></div>
    <section class=${cx("j-arkusz", klasa)} role="dialog" aria-modal="true" aria-label=${tytul} ref=${ref} tabIndex="-1" ...${reszta}>
      ${children}</section>`;
}

// krótkie komunikaty na dole ekranu (najwyżej 3); akcja opcjonalna („Cofnij”)
// Układ pod oknem dialogowym jest nieaktywny (inert): okna (Okno) liczone tutaj, warstwy aplikacji (szuflada, Stara
// Baza, wysunięty pasek na telefonie) ustawia AppJarvo. Jedno miejsce decyduje, żeby jedno nie zdejmowało drugiego.
const Bezwladnosc = (() => {
  let okna = 0, warstwa = false, pasek = false;
  function odswiez() {
    const uklad = document.querySelector("[data-jarvo-korzen] > .j-uklad");
    const glowna = uklad && uklad.querySelector(".j-glowna");
    if (uklad) uklad.toggleAttribute("inert", warstwa || okna > 0);
    if (glowna) glowna.toggleAttribute("inert", pasek);
  }
  return {
    okno(d) { okna = Math.max(0, okna + d); odswiez(); },
    warstwa(t) { warstwa = !!t; odswiez(); },
    pasek(t) { pasek = !!t; odswiez(); },
  };
})();

// krótkie komunikaty na dole ekranu (najwyżej 3); akcja opcjonalna („Cofnij”). 5 s, z akcją 10 s; najechanie albo
// fokus wstrzymuje odliczanie wszystkich (WCAG 2.2.1). Błędy idą do regionu role=alert, reszta do role=status.
const Komunikaty = (() => {
  let licznik = 0, pauza = false;
  const czasy = new Map();           // id → {zostalo, od, t}
  const zamknij = (id) => {
    const c = czasy.get(id);
    if (c) clearTimeout(c.t);
    czasy.delete(id);
    sklep.ustaw((s) => ({ ...s, toasty: s.toasty.filter((t) => t.id !== id) }));
  };
  const odliczaj = (id, ms) => { czasy.set(id, { zostalo: ms, od: Date.now(), t: pauza ? 0 : setTimeout(() => zamknij(id), ms) }); };
  function pokaz(tekst, { akcja, etykieta, czas, rodzaj } = {}) {
    const id = ++licznik;
    sklep.ustaw((s) => ({ ...s, toasty: s.toasty.concat([{ id, tekst, akcja, etykieta, rodzaj }]).slice(-3) }));
    odliczaj(id, czas || (akcja ? 10000 : 5000));
    return id;
  }
  function wstrzymaj(tak) {
    if (pauza === !!tak) return;
    pauza = !!tak;
    for (const [id, c] of czasy) {
      if (pauza) { clearTimeout(c.t); c.zostalo = Math.max(1500, c.zostalo - (Date.now() - c.od)); }
      else odliczaj(id, c.zostalo);
    }
  }
  return { pokaz, zamknij, wstrzymaj };
})();

function Toasty() {
  const toasty = useSklep((s) => s.toasty);
  const toast = (t) => html`<div key=${t.id} class=${cx("j-toast", t.rodzaj && `is-${t.rodzaj}`)}><span>${t.tekst}</span>
    ${t.akcja && html`<button type="button" onClick=${() => { Komunikaty.zamknij(t.id); t.akcja(); }}>${t.etykieta}</button>`}</div>`;
  const pauza = { onMouseEnter: () => Komunikaty.wstrzymaj(true), onMouseLeave: () => Komunikaty.wstrzymaj(false),
    onFocus: () => Komunikaty.wstrzymaj(true), onBlur: () => Komunikaty.wstrzymaj(false) };
  return html`<div class="j-toasty" ...${pauza}>
    <div class="j-toasty-r" role="alert">${toasty.filter((t) => t.rodzaj === "blad").map(toast)}</div>
    <div class="j-toasty-r" role="status" aria-live="polite">${toasty.filter((t) => t.rodzaj !== "blad").map(toast)}</div></div>`;
}
