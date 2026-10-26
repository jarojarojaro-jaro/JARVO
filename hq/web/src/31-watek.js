// Widok wątku (docs/HQ.md „Aplikacja”): oś czasu (role=log) z wiadomościami z 32-wiadomosc.js, „Nowe od tąd” (stała
// granica z liczby nieprzeczytanych przy otwarciu), przyklejenie do dołu przy nowych treściach (ResizeObserver),
// przycisk „Na dół”, wcześniejsze wiadomości przewijaniem w górę albo przyciskiem (pozycja przewijania zostaje),
// komunikaty dla czytnika ekranu (stan pracy, najwyżej jeden na 3 s) i kompozytor na dole. Menu wątku w nagłówku
// (Zmień nazwę, Przypnij, Szczegóły pracy, Eksportuj, Archiwizuj, Usuń) i okno pytań (praca w toku, trwałe usunięcie,
// wysyłka do więcej niż 3 agentów).

const OGLOSZENIA = { gotowe: "ogl.gotowe", czeka_na_zgode: "ogl.zgoda", blad: "ogl.blad", przerwane: "ogl.blad", zgubione: "ogl.blad" };

// region aria-live: jedno ogłoszenie na 3 s (późniejsze czeka i zastępuje wcześniejsze z kolejki)
function useOgloszenia() {
  const [tekst, setTekst] = useState("");
  const st = useRef({ ostatnie: 0, czeka: null, czas: 0 });
  useEffect(() => () => clearTimeout(st.current.czas), []);
  const oglos = useCallback((t) => {
    const s = st.current, teraz = Date.now();
    if (teraz - s.ostatnie >= 3000) { s.ostatnie = teraz; setTekst(t); return; }
    s.czeka = t;
    clearTimeout(s.czas);
    s.czas = setTimeout(() => { s.ostatnie = Date.now(); setTekst(s.czeka); s.czeka = null; }, 3000 - (teraz - s.ostatnie));
  }, []);
  return [tekst, oglos];
}

function Watek({ id, panel = 0 }) {
  const watek = useSklep((s) => s.watki[id] || (s.lista.wg_klucza[`w:${id}`] || {}).watek || null);
  const os = useSklep((s) => s.os[id]);
  const przebiegi = useSklep((s) => Object.values(s.przebiegi).filter((p) => p.watek_id === id), plytko);
  const oczekujace = useSklep((s) => s.wysylane[id]);
  const szczegoly = useSklep((s) => s.ustawienia.szczegoly);
  const [blad, setBlad] = useState(null);
  const koordynator = (watek && watek.koordynator) || "jarvo";
  const scroller = useRef(null), tresc = useRef(null), gora = useRef(null);
  const naDole = useRef(true), wysokoscPrzed = useRef(null), stanOsi = useRef(null);
  const [pokazDol, setPokazDol] = useState(false);
  const [ogloszenie, oglos] = useOgloszenia();

  useEffect(() => {
    let zywy = true;
    setBlad(null);
    const wczytaj = () => akcje.otworzWatek(id).catch((e) => { if (zywy) setBlad(e); });
    Strumien.subskrybuj([id]).then(() => { if (zywy) wczytaj(); });
    const haki = [
      Strumien.naZdarzenie("watek.os", (d) => d.watek_id === id && akcje.dociagnijOs(id, d.pelny)),
      Strumien.naZdarzenie("przebieg.koniec", (d) => d.watek_id === id && akcje.dociagnijOs(id)),
      Strumien.naZdarzenie("reset", wczytaj),
    ];
    return () => { zywy = false; haki.forEach((f) => f()); Strumien.subskrybuj([]); akcje.zapomnijWatek(id); };
  }, [id]);

  // przeczytane: wątek otwarty i widoczny (także po powrocie do karty). Granica „do” = później z aktywności wątku
  // i zegara przeglądarki: nowa aktywność po wysłaniu (koniec przebiegu, druga odpowiedź) nie zostawia licznika
  const nieprzeczytane = watek && watek.nieprzeczytane;
  const aktywnosc = watek && watek.aktywnosc_at;
  useEffect(() => {
    const oznacz = () => {
      if (nieprzeczytane > 0 && document.visibilityState === "visible") {
        api.rozmowy.przeczytane(id, Math.max(aktywnosc || 0, Date.now() / 1000)).catch(() => {});
      }
    };
    oznacz();
    document.addEventListener("visibilitychange", oznacz);
    return () => document.removeEventListener("visibilitychange", oznacz);
  }, [id, nieprzeczytane, aktywnosc]);

  // „Nowe od tąd”: liczba nieprzeczytanych z chwili otwarcia, granica liczona raz po pierwszej stronie osi
  const nieprzeczytane0 = useRef(null);
  if (nieprzeczytane0.current === null && watek) nieprzeczytane0.current = watek.nieprzeczytane || 0;
  const [granica, setGranica] = useState(undefined);
  useEffect(() => {
    if (granica === undefined && os && !os.laduje) setGranica(Os.noweOdTad(os.pozycje, nieprzeczytane0.current || 0));
  }, [os, granica]);

  const pozycje = useMemo(() => Os.widok(os ? os.pozycje : [], przebiegi, { szczegoly, oczekujace }),
    [os, przebiegi, szczegoly, oczekujace]);
  // karty pracy przekazane w wątku: stan z tablicy na żywo (35-karty.js)
  const idsKart = useMemo(() => [...Os.kartyWatku(os ? os.pozycje : [])], [os]);
  useKartyWatku(id, idsKart);
  // ostatnia pozycja każdego przebiegu: pod nią zostaje wygasła zgoda
  const ostatnie = useMemo(() => {
    const m = {};
    for (const x of pozycje) if (x.rodzaj === "agent" && x.przebieg_id) m[x.przebieg_id] = x.id;
    return m;
  }, [pozycje]);
  stanOsi.current = os;

  // komunikaty czytnika: zmiana stanu przebiegu (gotowe, czeka na zgodę, błąd); pierwszy odczyt bez ogłoszeń
  const stany = useRef(null);
  useEffect(() => {
    const byly = stany.current || {}, nowe = {};
    for (const p of przebiegi) {
      nowe[p.id] = p.stan;
      if (stany.current && byly[p.id] !== p.stan && OGLOSZENIA[p.stan]) oglos(T(OGLOSZENIA[p.stan], { agent: nazwaAgenta(p.agent) }));
    }
    stany.current = nowe;
  }, [przebiegi]);

  // przewijanie: przyklejone do dołu, dopóki właściciel sam nie przewinie w górę
  const naDol = (gladko) => {
    const el = scroller.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: gladko ? Ruch.zachowanie() : "auto" });
    naDole.current = true;
    setPokazDol(false);
  };
  const naScroll = () => {
    const el = scroller.current;
    const d = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    naDole.current = d;
    if (d === pokazDol) setPokazDol(!d);
  };
  useEffect(() => {
    const el = tresc.current;
    if (!el || !window.ResizeObserver) return undefined;
    const ro = new ResizeObserver(() => { if (naDole.current && wysokoscPrzed.current == null) naDol(false); });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // pierwsze ustawienie: na granicę „Nowe od tąd” albo na dół
  React.useLayoutEffect(() => {
    if (granica === undefined) return;
    const el = scroller.current, g = el && el.querySelector(".j-nowe");
    if (!g) { naDol(false); return; }
    // granica w górnej trzeci części; przewija tylko oś (scrollIntoView przesunąłby też korzeń aplikacji)
    el.scrollTop += g.getBoundingClientRect().top - el.getBoundingClientRect().top - el.clientHeight / 3;
    naDole.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    setPokazDol(!naDole.current);
  }, [granica]);
  // własna wiadomość zawsze przewija na dół
  const ileOczekuje = (oczekujace || []).length;
  useEffect(() => { if (ileOczekuje > 0) naDol(true); }, [ileOczekuje]);
  // wcześniejsze: zapamiętana odległość od dołu, po dopisaniu na początku ta sama treść zostaje na miejscu
  const wczesniej = () => {
    const el = scroller.current, o = stanOsi.current;
    if (!o || !o.przed || o.laduje || wysokoscPrzed.current != null) return;
    wysokoscPrzed.current = el ? el.scrollHeight - el.scrollTop : null;
    akcje.wczesniejsze(id);
  };
  const pierwsza = pozycje.length ? pozycje[0].id : null;
  React.useLayoutEffect(() => {
    const el = scroller.current;
    if (el && wysokoscPrzed.current != null && os && !os.laduje) {
      el.scrollTop = el.scrollHeight - wysokoscPrzed.current;
      wysokoscPrzed.current = null;
    }
  }, [pierwsza, os && os.laduje]);
  useEffect(() => {
    const el = gora.current;
    if (!el || granica === undefined || !window.IntersectionObserver) return undefined;
    const io = new IntersectionObserver((w) => { if (w.some((x) => x.isIntersecting)) wczesniej(); }, { root: scroller.current, rootMargin: "200px 0px 0px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [granica, id]);

  // upuszczone pliki gdziekolwiek w wątku trafiają do kompozytora
  const [nad, setNad] = useState(false);
  const zPlikami = (e) => e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files");
  const upusc = (e) => {
    if (!zPlikami(e)) return;
    e.preventDefault();
    setNad(false);
    akcje.doKompozytora(id, { pliki: [...e.dataTransfer.files], fokus: true });
  };

  if (blad) {
    return html`<${Pusto} ikona="alert" tytul=${blad.status === 404 ? T("watek.brak") : blad.tekst ? blad.tekst() : String(blad)}>
      <a class="j-link" href="#/">${T("watek.do_startu")}</a></${Pusto}>`;
  }
  // ctx stały między renderami (ElementOsi jest memo): nowy tylko przy zmianie wątku, ustawień albo języka
  const pl = isPL();
  const ctx = useMemo(() => ({ watek: id, k: id, koordynator, szczegoly, panel, pl }), [id, koordynator, szczegoly, panel, pl]);
  const wKoszu = !!(watek && watek.usuniety_at);
  return html`<div class=${cx("j-watek", nad && "is-nad")} onDragOver=${(e) => { if (zPlikami(e)) { e.preventDefault(); setNad(true); } }}
      onDragLeave=${(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setNad(false); }} onDrop=${upusc}>
    <div class="j-watek-s" ref=${scroller} onScroll=${naScroll}>
      <div class="j-os" role="log" aria-live="off" tabIndex="0" aria-label=${(watek && watek.tytul) || T("watek.bez_tytulu")} ref=${tresc}>
        <div ref=${gora} class="j-os-gora"></div>
        ${os && os.przed && html`<button type="button" class="j-link j-wczesniej" disabled=${os.laduje} onClick=${wczesniej}>
          ${os.laduje ? html`<${Spinner}/>` : null}${T("os.wczesniejsze")}</button>`}
        ${!os && html`<p class="j-pasek-pusto"><${Spinner}/></p>`}
        ${os && !pozycje.length && html`<p class="j-os-pusto">${T("watek.pusty")}</p>`}
        ${pozycje.map((x) => html`<${React.Fragment} key=${x.id}>
          ${granica && granica === x.id && html`<div class="j-nowe" role="separator"><span>${T("watek.nowe_od_tad")}</span></div>`}
          <${ElementOsi} x=${x} ctx=${ctx} ostatniaPrzebiegu=${ostatnie[x.przebieg_id] === x.id}/></${React.Fragment}>`)}
      </div>
    </div>
    ${pokazDol && html`<button type="button" class="j-dodolu" onClick=${() => naDol(true)} aria-label=${T("watek.na_dol")}>
      <${Ikona} n="down" r=${18}/></button>`}
    <p class="j-sr" aria-live="polite" aria-atomic="true">${ogloszenie}</p>
    <div class="j-dok">
      ${wKoszu ? html`<div class="j-kosz-uwaga"><${Ikona} n="trash" r=${16}/><span>${T("watek.w_koszu_opis")}</span>
          <${Przycisk} maly onClick=${() => akcje.przywroc(id)}>${T("watek.przywroc")}</${Przycisk}></div>`
        : html`<${Kompozytor} key=${id} watek=${id} panel=${panel} koordynator=${koordynator}/>`}
    </div>
  </div>`;
}

// ------------------------------------------------------------------------------------------------- nagłówek wątku
// tytuł do zmiany w miejscu: Enter zapisuje, Esc wraca, pusty tytuł nie przechodzi (serwer też go odrzuca)
// fokusPo: selektor, na który wraca fokus po zapisie albo Esc (wiersz listy, nagłówek wątku)
function EdycjaTytulu({ watek, onKoniec, klasa, fokusPo }) {
  const [t, setT] = useState(watek.tytul || "");
  const ref = useRef(null), klawisz = useRef(false);
  useEffect(() => { if (ref.current) { ref.current.focus(); ref.current.select(); } }, []);
  // fokus wraca tylko po Enter/Esc; klik gdzie indziej zostawia go tam, gdzie właściciel kliknął
  const koniec = () => { if (fokusPo && (klawisz.current || ref.current === document.activeElement)) Fokus.odloz(fokusPo); onKoniec(); };
  const zapisz = async () => {
    const nowy = t.trim().slice(0, 120);
    koniec();
    if (nowy && nowy !== watek.tytul) await akcje.zmienWatek(watek.id, { tytul: nowy });
  };
  return html`<input ref=${ref} class=${cx("j-tytul-pole", klasa)} value=${t} maxLength="120" aria-label=${T("watek.zmien_nazwe")}
    onInput=${(e) => setT(e.target.value)} onBlur=${zapisz}
    onKeyDown=${(e) => {
      if (e.key === "Enter") { e.preventDefault(); klawisz.current = true; e.currentTarget.blur(); }
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setT(watek.tytul || ""); koniec(); }
    }}/>`;
}

function MenuWatku({ watek, onZmienNazwe }) {
  const [kotwica, setKotwica] = useState(null);
  const szczegoly = useSklep((s) => s.ustawienia.szczegoly);
  const pozycje = pozycjeMenuWatku(watek, { onZmienNazwe });
  // wąski ekran: koło zębate z nagłówka wątku jest tutaj (mniej ikon w nagłówku telefonu)
  if (window.innerWidth < 1024) {
    pozycje.push({ oddzielnik: true }, { id: "ustawienia", ikona: "gear", tekst: T("pasek.ustawienia"),
      akcja: () => Trasa.idz({ u: "ustawienia", pod: undefined }, { scal: true }) });
  }
  pozycje.splice(watek.usuniety_at ? 0 : 2, 0,
    { id: "szczegoly", ikona: "spark", tekst: T(szczegoly ? "watek.prosty" : "watek.szczegoly"),
      akcja: () => sklep.zmien("ustawienia", { szczegoly: !szczegoly }) },
    { id: "eksport", ikona: "dl", tekst: T("watek.eksportuj"), akcja: () => akcje.eksport(watek.id) });
  return html`<${Przycisk} rodzaj="cichy" ikona="more" etykieta=${T("watek.menu")} aria-haspopup="menu"
      aria-expanded=${kotwica ? "true" : "false"} onClick=${(e) => setKotwica(e.currentTarget)}/>
    ${kotwica && html`<${Menu} kotwica=${kotwica} etykieta=${T("watek.menu")} pozycje=${pozycje} onZamknij=${() => setKotwica(null)}/>`}`;
}

// ------------------------------------------------------------------------------------------------- okno pytań
// praca w toku przy archiwum lub koszu (zatrzymać czy pozwolić skończyć), wysyłka do wielu agentów i trwałe usunięcie
function OknoPytania() {
  const p = useSklep((s) => s.pytanie);
  if (!p) return null;
  const nie = () => p.odpowiedz(null);
  if (p.rodzaj === "praca") {
    const d = p.dane || {};
    const n = (d.przebiegi || []).length + (d.karty || []).length;
    return html`<${Okno} tytul=${T("pytanie.praca_t")} onZamknij=${nie} stopka=${html`
      <${Przycisk} rodzaj="cichy" onClick=${nie}>${T("ui.anuluj")}</${Przycisk}>
      <${Przycisk} onClick=${() => p.odpowiedz("zostaw")}>${T("pytanie.zostaw")}</${Przycisk}>
      <${Przycisk} rodzaj="mocny" data-fokus="" onClick=${() => p.odpowiedz("zatrzymaj")}>${T("pytanie.zatrzymaj")}</${Przycisk}>`}>
      <p class="j-okno-p">${T("pytanie.praca", { n: Math.max(1, n) })}</p></${Okno}>`;
  }
  if (p.rodzaj === "wielu") {
    return html`<${Okno} tytul=${T("pytanie.wielu_t", { n: (p.dane || {}).n || 0 })} onZamknij=${nie} stopka=${html`
      <${Przycisk} rodzaj="cichy" onClick=${nie}>${T("ui.anuluj")}</${Przycisk}>
      <${Przycisk} rodzaj="mocny" data-fokus="" onClick=${() => p.odpowiedz(true)}>${T("kompozytor.wyslij")}</${Przycisk}>`}>
      <p class="j-okno-p">${T("pytanie.wielu_opis")}</p></${Okno}>`;
  }
  return html`<${Okno} tytul=${T("pytanie.usun_t")} onZamknij=${nie} stopka=${html`
    <${Przycisk} rodzaj="cichy" data-fokus="" onClick=${nie}>${T("ui.anuluj")}</${Przycisk}>
    <${Przycisk} rodzaj="niebezpieczny" ikona="trash" onClick=${() => p.odpowiedz(true)}>${T("pytanie.usun")}</${Przycisk}>`}>
    <p class="j-okno-p">${T("pytanie.usun_opis")}</p></${Okno}>`;
}
