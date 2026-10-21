// Szuflada ustawień (docs/HQ.md „Aplikacja”): arkusz z prawej, otwierany kołem zębatym, Ctrl/⌘+, i adresem
// …?u=<sekcja>[/<pod>] (zamknięcie zdejmuje u). Etap 3 ma wersję minimalną, żeby po schowaniu menu Hermesa nic nie
// zostało bez wejścia: Połączenia (Klucze i Modele jako osadzone strony Hermesa), Zespół (kto co robi, jak pisać wprost),
// Wygląd, Konto (język, wylogowanie, klasyczny panel, wersja, skróty pod „Pokaż”), System › Aktualizacja (bezpieczna
// aktualizacja, spec §15.3) i Stara Baza.
// Na telefonie: lista sekcji, potem sekcja z „Wróć”.

const SEKCJE_SZUFLADY = [
  { id: "polaczenia", ikona: "plug" },
  { id: "zespol", ikona: "users" },
  { id: "wyglad", ikona: "palette" },
  { id: "konto", ikona: "user" },
  { id: "system", ikona: "wrench" },
  { oddzielnik: true },
  { id: "stara-baza", ikona: "monitor" },
];
const ZALADOWANO_S = Date.now() / 1000;
const OSADZONE = { klucze: "/env", modele: "/models" };

// strona Hermesa w ramce (data-jarvo-embed: bez menu Hermesa); Esc w ramce zamyka szufladę
function Osadzona({ sciezka, tytul, onEsc }) {
  const ref = useRef(null);
  const zaladowana = () => {
    try {
      ref.current.contentDocument.addEventListener("keydown", (e) => { if (e.key === "Escape") onEsc(); });
    } catch (_) { /* inna domena: bez mostu Esc */ }
  };
  return html`<iframe class="j-osadzona" ref=${ref} src=${basePath() + sciezka} title=${tytul} data-jarvo-embed="" onLoad=${zaladowana}></iframe>`;
}

const Wiersz = ({ ikona, tytul, opis, children }) => html`<div class="j-wiersz">
  ${ikona && html`<span class="j-wiersz-i"><${Ikona} n=${ikona}/></span>`}
  <span class="j-wiersz-t"><b>${tytul}</b>${opis && html`<small>${opis}</small>`}</span>${children}</div>`;

function Wybor({ etykieta, wartosc, opcje, onWybierz }) {
  return html`<div class="j-wybor" role="group" aria-label=${etykieta}>${opcje.map(([v, tekst]) => html`<button type="button"
    key=${v} aria-pressed=${String(v === wartosc)} onClick=${() => onWybierz(v)}>${tekst}</button>`)}</div>`;
}

function SekcjaPolaczenia({ pod, idz, zamknij }) {
  if (OSADZONE[pod]) {
    return html`<div class="j-sz-osadzona">
      <div class="j-sz-pasek"><button type="button" class="j-link" onClick=${() => idz("polaczenia")}>
        <${Ikona} n="back" r=${16}/>${T("szuflada.polaczenia")}</button>
        <a class="j-link" href=${basePath() + OSADZONE[pod]} target="_blank" rel="noopener">${T("szuflada.pelne_okno")}<${Ikona} n="ext" r=${14}/></a></div>
      <${Osadzona} key=${pod} sciezka=${OSADZONE[pod]} tytul=${T(`szuflada.${pod}`)} onEsc=${zamknij}/></div>`;
  }
  return html`<h3>${T("szuflada.polaczenia")}</h3><p class="j-sz-lead">${T("szuflada.polaczenia_opis")}</p>
    <div class="j-karta">
      ${["klucze", "modele"].map((p) => html`<${Wiersz} key=${p} ikona=${p === "klucze" ? "plug" : "cpu"} tytul=${T(`szuflada.${p}`)} opis=${T(`szuflada.${p}_opis`)}>
        <${Przycisk} maly onClick=${() => idz("polaczenia", p)}>${T("ui.otworz")}</${Przycisk}></${Wiersz}>`)}
    </div>`;
}

// Zespół: krótko, jak to działa, i lista agentów (figurka, rola, @uchwyt, „Napisz” = nowa rozmowa z tym agentem)
function SekcjaZespol() {
  const agenci = useSklep((s) => s.agenci);
  const kolejnosc = useSklep((s) => s.kolejnosc);
  const lista = kolejnosc.map((n) => agenci[n]).filter((a) => a && a.stan !== "archiwum");
  // nowa rozmowa (szuflada znika razem z `u` w adresie); fokus w kompozytorze startu
  const napisz = (a) => { Fokus.odloz("kompozytor"); Trasa.idz(a.rodzaj === "orchestrator" ? { widok: "start" } : { widok: "nowa", agent: a.name }); };
  return html`<h3>${T("szuflada.zespol")}</h3><p class="j-sz-lead">${T("zespol.p1")}</p>
    <p class="j-sz-uwaga">${T("zespol.p2")}</p><p class="j-sz-uwaga">${T("zespol.p3")}</p>
    <p class="j-sz-sub">${T("zespol.agenci")}</p>
    <ul class="j-karta j-zespol-l">${lista.map((a) => html`<li key=${a.name} data-agent=${a.name}>
      <${Awatar} agent=${a} r=${30}/><span class="j-zespol-t"><b>${nazwaAgenta(a.name)}${a.handle ? html` <small>@${a.handle}</small>` : ""}</b>
      <small>${rolaAgenta(a)}</small></span>
      <${Przycisk} maly rodzaj="cichy" etykieta=${T("zespol.napisz_do", { agent: nazwaAgenta(a.name) })} onClick=${() => napisz(a)}>${T("zespol.napisz")}</${Przycisk}></li>`)}</ul>`;
}

function SekcjaWyglad() {
  const motyw = useSklep((s) => s.ustawienia.motyw);
  return html`<h3>${T("szuflada.wyglad")}</h3><p class="j-sz-lead">${T("szuflada.wyglad_opis")}</p>
    <p class="j-sz-sub">${T("szuflada.motyw")}</p>
    <${Wybor} etykieta=${T("szuflada.motyw")} wartosc=${motyw} onWybierz=${(m) => sklep.zmien("ustawienia", { motyw: m })}
      opcje=${Motyw.WYBORY.map((m) => [m, T(`motyw.${m}`)])}/>`;
}

// język: przez i18n dashboardu (setLocale), więc klasyczne strony Hermesa mówią tym samym językiem; bez niego
// hermes-locale w localStorage i odświeżenie
function SekcjaKonto() {
  const i18n = useHostI18n();
  const jezyk = isPL() ? "pl" : "en";
  const ustawJezyk = (j) => {
    if (i18n && i18n.setLocale) { i18n.setLocale(j); return; }
    try { localStorage.setItem("hermes-locale", j); } catch (_) { /* zablokowane */ }
    location.reload();
  };
  return html`<h3>${T("szuflada.konto")}</h3><p class="j-sz-lead">${T("szuflada.konto_opis")}</p>
    <p class="j-sz-sub">${T("szuflada.jezyk")}</p>
    <${Wybor} etykieta=${T("szuflada.jezyk")} wartosc=${jezyk} onWybierz=${ustawJezyk} opcje=${[["pl", "Polski"], ["en", "English"]]}/>
    <p class="j-sz-uwaga">${T("szuflada.jezyk_opis")}</p>
    <div class="j-karta">
      <${Wiersz} ikona="logout" tytul=${T("szuflada.wyloguj")} opis=${T("szuflada.wyloguj_opis")}>
        <${Przycisk} maly data-akcja="wyloguj" onClick=${() => api.wyloguj()}>${T("szuflada.wyloguj")}</${Przycisk}></${Wiersz}>
      <${Wiersz} ikona="ext" tytul=${T("szuflada.klasyczny")} opis=${T("szuflada.klasyczny_opis")}>
        <a class="j-btn j-btn-zwykly is-maly" data-akcja="klasyczny" href=${`${basePath()}/sessions`}>${T("ui.otworz")}</a></${Wiersz}>
      <${Wiersz} ikona="spark" tytul=${T("szuflada.wersja")} opis=${T("szuflada.wersja_opis")}>
        <code class="j-sz-kod" title=${WERSJA_PAKIETU || ""}>${String(WERSJA_PAKIETU || "—").slice(0, 10)}</code></${Wiersz}>
    </div>
    <details class="j-sz-det">
      <summary><${Ikona} n="right" r=${16}/>${T("szuflada.skroty_pokaz")}</summary>
      <div class="j-karta j-skroty" aria-label=${T("szuflada.skroty")}>${Skroty.lista().map((s) => html`<div key=${s.komb} class="j-skrot"><span>${T(s.opis)}</span><${Klawisz} k=${s.komb}/></div>`)}</div>
    </details>`;
}

// polecenie do skopiowania (pomocnik aktualizacji): opis, kod, „Kopiuj”
function Polecenie({ etykieta, kod }) {
  const [ok, setOk] = useState(false);
  const kopiuj = async () => {
    try { await navigator.clipboard.writeText(kod); setOk(true); setTimeout(() => setOk(false), 1500); } catch (_) { /* bez schowka */ }
  };
  return html`<div class="j-polecenie"><small>${etykieta}</small><code>${kod}</code>
    <${Przycisk} maly rodzaj="cichy" onClick=${kopiuj}>${T(ok ? "md.skopiowano" : "md.kopiuj")}</${Przycisk}></div>`;
}
const POLECENIA_POMOCNIKA = (start) => html`<div class="j-polecenia">
  <${Polecenie} etykieta=${T("akt.na_komputerze")} kod="jarvo updater"/>
  <${Polecenie} etykieta=${T("akt.na_serwerze")} kod=${`sudo systemctl ${start ? "start" : "restart"} jarvo-updater`}/></div>`;

// ---- System › Aktualizacja (spec §15.3). Przy pracy agentów (praca.json silnika) „Aktualizuj” pyta: „Zaktualizuj,
// gdy skończą” (domyślny fokus; update-request dopiero po 30 s bez pracy), „Aktualizuj teraz” albo „Anuluj”. Czekająca
// aktualizacja ma „Aktualizuj teraz” i „Nie aktualizuj”. Nowa wersja: pasek „Odśwież”; sama odświeża się tylko karta
// schowana i bezczynna (useNowaWersja w 90-app.js).
function OknoAktualizacji({ praca, onWybor, onZamknij }) {
  return html`<${Okno} tytul=${T("akt.okno_t")} onZamknij=${onZamknij} klasa="j-okno-akt" stopka=${html`
      <${Przycisk} rodzaj="cichy" onClick=${onZamknij}>${T("ui.anuluj")}</${Przycisk}>
      <${Przycisk} data-akcja="teraz" onClick=${() => onWybor("teraz")}>${T("akt.teraz")}</${Przycisk}>
      <${Przycisk} rodzaj="mocny" data-fokus="" data-akcja="wolne" onClick=${() => onWybor("wolne")}>${T("akt.gdy_skoncza")}</${Przycisk}>`}>
    <p class="j-okno-p" data-praca=${praca.aktywne}>${T("akt.pracuje", { n: praca.aktywne })}</p>
    ${praca.opis.length > 0 && html`<ul class="j-akt-opis">${praca.opis.map((o, i) => html`<li key=${i}>${o}</li>`)}</ul>`}
  </${Okno}>`;
}

function SekcjaSystem() {
  const a = useSklep((s) => s.aktualizacja) || {};
  const [okno, setOkno] = useState(false);
  const [trwa, setTrwa] = useState(false);
  useEffect(() => { akcje.wczytajAktualizacje(); }, []);
  const praca = { aktywne: 0, opis: [], ...(a.praca || {}) };
  const wyslij = async (gdy) => {
    setOkno(false);
    setTrwa(true);
    await akcje.aktualizuj("update", gdy);
    setTrwa(false);
  };
  // świeży stan przed decyzją: liczba pracujących z praca.json (silnik odświeża go przy każdej zmianie)
  const aktualizuj = async () => {
    setTrwa(true);
    await akcje.wczytajAktualizacje();
    setTrwa(false);
    const st = sklep.stan().aktualizacja || {};
    if (((st.praca || {}).aktywne || 0) > 0) setOkno(true);
    else wyslij("teraz");
  };
  const odwolaj = async () => { setTrwa(true); await akcje.aktualizuj("cancel"); setTrwa(false); };
  const aktualizuje = a.state === "updating" || (a.pending && !["done", "stalled", "failed"].includes(a.state));
  const zrobiona = a.state === "done" && (a.finished_at || 0) > ZALADOWANO_S;
  let stan, akcjeSekcji = null;
  if (aktualizuje) stan = html`<p class="j-akt-stan is-trwa" role="status"><${Spinner}/><span>${T("akt.trwa")}</span></p>`;
  else if (a.po_pracy) {
    stan = html`<p class="j-akt-stan is-czeka" role="status"><${Ikona} n="alert" r=${16}/><span>${T("akt.czeka", { n: praca.aktywne })}</span></p>
      <p class="j-sz-uwaga">${T("akt.czeka_opis")}</p>`;
    akcjeSekcji = html`<${Przycisk} data-akcja="teraz" disabled=${trwa} onClick=${() => wyslij("teraz")}>${T("akt.teraz")}</${Przycisk}>
      <${Przycisk} rodzaj="cichy" data-akcja="nie" disabled=${trwa} onClick=${odwolaj}>${T("akt.nie")}</${Przycisk}>`;
  } else if (zrobiona) stan = html`<p class="j-akt-stan is-ok" role="status"><${Ikona} n="check" r=${16}/><span>${T("akt.zrobiona", { wersja: a.current || "" })}</span></p>`;
  else if (a.state === "stalled" || a.state === "failed") {
    stan = html`<p class="j-akt-stan is-zle" role="status"><${Ikona} n="alert" r=${16}/><span>${a.state === "stalled"
      ? T("akt.utknela", { min: Math.round((a.silent_for || 0) / 60) }) : T("akt.nieudana")}</span></p>
      ${a.state === "stalled" && POLECENIA_POMOCNIKA(false)}`;
    akcjeSekcji = html`<${Przycisk} rodzaj="mocny" data-akcja="aktualizuj" disabled=${trwa} onClick=${aktualizuj}>${T("ui.ponow")}</${Przycisk}>`;
  } else if (!a.online) stan = html`<p class="j-akt-stan" role="status"><span>${T("akt.offline")}</span></p>${POLECENIA_POMOCNIKA(true)}`;
  else if ((a.behind || 0) > 0) {
    stan = html`<p class="j-akt-stan is-nowa" role="status"><${Ikona} n="up" r=${16}/><span>${T("akt.dostepna", { n: a.behind })}</span></p>
      ${a.branch && a.current && a.latest && html`<p class="j-sz-uwaga">${T("akt.galaz", { galaz: a.branch, z: a.current, na: a.latest })}</p>`}`;
    akcjeSekcji = html`<${Przycisk} rodzaj="mocny" data-akcja="aktualizuj" disabled=${trwa} onClick=${aktualizuj}>${T("akt.aktualizuj")}</${Przycisk}>`;
  } else stan = html`<p class="j-akt-stan is-ok" role="status"><${Ikona} n="check" r=${16}/><span>${T("akt.aktualna")}</span></p>`;
  return html`<h3>${T("szuflada.system")}</h3><p class="j-sz-lead">${T("szuflada.system_opis")}</p>
    <p class="j-sz-sub">${T("akt.tytul")}</p>
    <div class="j-karta j-akt" data-stan=${a.po_pracy ? "czeka" : aktualizuje ? "trwa" : a.state || "brak"}>${stan}
      ${akcjeSekcji && html`<div class="j-sz-akcje">${akcjeSekcji}</div>`}</div>
    ${okno && html`<${OknoAktualizacji} praca=${praca} onWybor=${wyslij} onZamknij=${() => setOkno(false)}/>`}`;
}

function SekcjaStaraBaza({ zamknij }) {
  return html`<h3>${T("szuflada.stara-baza")}</h3><p class="j-sz-lead">${T("szuflada.stara_baza_opis")}</p>
    <div class="j-sz-akcje"><${Przycisk} rodzaj="mocny" onClick=${() => { zamknij(); sklep.ustaw({ stara_baza: true }); }}>${T("szuflada.stara_baza_otworz")}</${Przycisk}></div>`;
}

function Szuflada({ trasa }) {
  const sekcja = SEKCJE_SZUFLADY.some((s) => s.id === trasa.u) ? trasa.u : null;   // null: lista sekcji (telefon)
  const aktywna = sekcja || "polaczenia";
  const zamknij = () => Trasa.idz({ ...trasa, u: undefined, pod: undefined });
  const idz = (u, pod) => Trasa.idz({ ...trasa, u, pod }, { zastap: true });
  // telefon: lista sekcji i sekcja to dwa ekrany; fokus idzie na nagłówek sekcji, a po „Wróć” na jej przycisk
  const waski = useWaskiEkran();
  const wejdz = (u) => { if (waski) Fokus.odloz(".j-sz-tresc h3"); idz(u); };
  const wroc = () => { Fokus.odloz(`.j-sz-p[data-sekcja="${aktywna}"]`); idz("ustawienia"); };
  const tresc = {
    polaczenia: html`<${SekcjaPolaczenia} pod=${trasa.pod} idz=${idz} zamknij=${zamknij}/>`,
    zespol: html`<${SekcjaZespol}/>`,
    wyglad: html`<${SekcjaWyglad}/>`,
    konto: html`<${SekcjaKonto}/>`,
    system: html`<${SekcjaSystem}/>`,
    "stara-baza": html`<${SekcjaStaraBaza} zamknij=${zamknij}/>`,
  }[aktywna];
  const tytul = T("szuflada.tytul");
  return html`<${Arkusz} tytul=${tytul} onZamknij=${zamknij} klasa=${cx("j-szuflada", OSADZONE[trasa.pod] && "is-szeroka")}
      data-widok=${sekcja ? "sekcja" : "lista"} data-region="szuflada">
    <nav class="j-sz-nav" aria-label=${tytul}>
      <div class="j-sz-gora"><h2>${tytul}</h2>
        <${Przycisk} rodzaj="cichy" ikona="x" etykieta=${T("ui.zamknij")} klasa="j-na-telefonie" onClick=${zamknij}/></div>
      ${SEKCJE_SZUFLADY.map((s, i) => (s.oddzielnik ? html`<div key=${i} class="j-sz-sep"></div>` : html`<button type="button"
        key=${s.id} class="j-sz-p" data-sekcja=${s.id} aria-current=${s.id === aktywna ? "true" : undefined} data-fokus=${s.id === aktywna ? "" : undefined}
        onClick=${() => wejdz(s.id)}><${Ikona} n=${s.ikona}/><span>${T(`szuflada.${s.id}`)}</span><${Ikona} n="right" r=${16} klasa="j-sz-dalej"/></button>`))}
    </nav>
    <div class="j-sz-glowna">
      <div class="j-sz-mgora j-na-telefonie"><button type="button" class="j-sz-wroc" onClick=${wroc}>
        <${Ikona} n="back"/>${tytul}</button></div>
      <${Przycisk} rodzaj="cichy" ikona="x" etykieta=${T("ui.zamknij")} klasa="j-sz-x" onClick=${zamknij}/>
      <div class=${cx("j-sz-tresc", OSADZONE[trasa.pod] && "is-osadzona")}>${tresc}</div>
    </div>
  </${Arkusz}>`;
}
