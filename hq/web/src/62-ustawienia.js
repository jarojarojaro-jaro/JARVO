// Strona Ustawień (centrum §2.4, docs/HQ.md „Aplikacja”): #/ustawienia[/<sekcja>[/<pod>]], wejście kołem zębatym,
// Ctrl/⌘+, i pozycją pod rozmówcami. Sekcje: Rozmówcy (kafle, lustro do Telegrama), Model (Klucze i Modele jako
// osadzone strony Hermesa), Telegram (tematy, tylko odczyt), Powiadomienia, Dostęp (panel w sieci, tylko odczyt),
// Wygląd (motyw i palety Fosforu), Język, Zespół, System (aktualizacja, wylogowanie, klasyczny panel, wersja,
// skróty) i Stara Baza. Szeroko: nawigacja z lewej i treść; na telefonie (390 px) lista sekcji, potem sekcja z „Wróć”.

const SEKCJE_USTAWIEN = [
  { id: "rozmowcy", ikona: "msg" },
  { id: "model", ikona: "cpu" },
  { id: "telegram", ikona: "tg" },
  { id: "powiadomienia", ikona: "alert" },
  { id: "dostep", ikona: "globe" },
  { id: "wyglad", ikona: "palette" },
  { id: "jezyk", ikona: "book" },
  { id: "zespol", ikona: "users" },
  { id: "system", ikona: "wrench" },
  { oddzielnik: true },
  { id: "stara-baza", ikona: "monitor" },
];
// palety Fosforu z branding/fosfor/palettes.yaml (test pilnuje zgodności); kolory dają zmienne --j-* w style.css
const PALETY = [
  { id: "jarvo", kolor: "#D4213D", pl: "Jarvo · biało-czerwony", en: "Jarvo · white and red" },
  { id: "fosfor", kolor: "#89cff0", pl: "Fosfor · błękit", en: "Phosphor · blue" },
  { id: "fosfor-bursztyn", kolor: "#ffb000", pl: "Fosfor · bursztyn", en: "Phosphor · amber" },
  { id: "fosfor-zielen", kolor: "#41ff7a", pl: "Fosfor · zieleń", en: "Phosphor · green" },
  { id: "fosfor-biel", kolor: "#eef3ff", pl: "Fosfor · biel", en: "Phosphor · white" },
];
const ZALADOWANO_S = Date.now() / 1000;
const OSADZONE = { klucze: "/env", modele: "/models" };

// strona Hermesa w ramce (data-jarvo-embed: bez menu Hermesa); Esc w ramce wraca do sekcji
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
// Zespół: krótko, jak to działa, i lista agentów (figurka, rola, @uchwyt, „Napisz” = nowa rozmowa z tym agentem)
function SekcjaZespol() {
  const agenci = useSklep((s) => s.agenci);
  const kolejnosc = useSklep((s) => s.kolejnosc);
  const lista = kolejnosc.map((n) => agenci[n]).filter((a) => a && a.stan !== "archiwum");
  // nowa rozmowa (wyjście ze strony Ustawień); fokus w kompozytorze startu
  const napisz = (a) => { Fokus.odloz("kompozytor"); Trasa.idz(a.rodzaj === "orchestrator" ? { widok: "start" } : { widok: "nowa", agent: a.name }); };
  return html`<h3>${T("ust.zespol")}</h3><p class="j-sz-lead">${T("zespol.p1")}</p>
    <p class="j-sz-uwaga">${T("zespol.p2")}</p><p class="j-sz-uwaga">${T("zespol.p3")}</p>
    <p class="j-sz-sub">${T("zespol.agenci")}</p>
    <ul class="j-karta j-zespol-l">${lista.map((a) => html`<li key=${a.name} data-agent=${a.name}>
      <${Awatar} agent=${a} r=${30}/><span class="j-zespol-t"><b>${nazwaAgenta(a.name)}${a.handle ? html` <small>@${a.handle}</small>` : ""}</b>
      <small>${rolaAgenta(a)}</small></span>
      <${Przycisk} maly rodzaj="cichy" etykieta=${T("zespol.napisz_do", { agent: nazwaAgenta(a.name) })} onClick=${() => napisz(a)}>${T("zespol.napisz")}</${Przycisk}></li>`)}</ul>`;
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

function Aktualizacja() {
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
  return html`
<p class="j-sz-sub">${T("akt.tytul")}</p>
    <div class="j-karta j-akt" data-stan=${a.po_pracy ? "czeka" : aktualizuje ? "trwa" : a.state || "brak"}>${stan}
      ${akcjeSekcji && html`<div class="j-sz-akcje">${akcjeSekcji}</div>`}</div>
    ${okno && html`<${OknoAktualizacji} praca=${praca} onWybor=${wyslij} onZamknij=${() => setOkno(false)}/>`}`;
}

// przełącznik wł./wył. (role=switch: Spacja i Enter z przycisku)
function Przelacznik({ wl, etykieta, onZmien, ...reszta }) {
  return html`<button type="button" role="switch" class="j-ust-sw" aria-checked=${String(!!wl)} aria-label=${etykieta}
    onClick=${() => onZmien(!wl)} ...${reszta}><span aria-hidden="true"></span></button>`;
}

const Naglowek = ({ id }) => html`<h3 tabindex="-1">${T(`ust.${id}`)}</h3><p class="j-sz-lead">${T(`ust.${id}_opis`)}</p>`;

// Rozmówcy: kafel na rozmówcę (stan, zaplecze, temat w Telegramie) i lustro panel → Telegram (PATCH /rozmowcy/<klucz>)
function SekcjaRozmowcy() {
  const rozmowcy = useSklep((s) => s.rozmowcy) || [];
  return html`<${Naglowek} id="rozmowcy"/>
    ${rozmowcy.length === 0 ? html`<p class="j-sz-uwaga">${T("rozm.brak")}</p>` : html`<ul class="j-ust-kafle">${rozmowcy.map((r) => html`
      <li key=${r.klucz} class=${cx("j-ust-kafel", `is-${stanRozmowcy(r)}`)} data-rozmowca=${r.klucz}>
        <a class="j-ust-kafel-t" href=${Trasa.zbuduj({ widok: "rozmowca", rozmowca: r.klucz })}>
          <b>${nazwaRozmowcy(r)}</b><small>${slowoStanu(r)} · ${r.zaplecze === "omp" ? T("ust.zaplecze_omp") : T("ust.zaplecze_hermes")}</small></a>
        <span class="j-ust-kafel-tg">${r.temat ? T("ust.temat_jest") : T("ust.temat_brak")}</span>
        <label class="j-ust-kafel-l"><span>${T("ust.lustro")}</span>
          <${Przelacznik} wl=${r.lustro} etykieta=${T("ust.lustro_dla", { nazwa: nazwaRozmowcy(r) })}
            onZmien=${(v) => akcje.zmienRozmowce(r.klucz, { lustro: v })}/></label>
      </li>`)}</ul>`}
    <p class="j-sz-uwaga">${T("ust.lustro_opis")}</p>`;
}

// Model: Klucze i Modele (osadzone strony Hermesa); klasaBledu (15-os.js) prowadzi tu z błędu klucza albo modelu
function SekcjaModel({ pod, idz, zamknij }) {
  if (OSADZONE[pod]) {
    return html`<div class="j-sz-osadzona">
      <div class="j-sz-pasek"><button type="button" class="j-link" onClick=${() => idz("model")}>
        <${Ikona} n="back" r=${16}/>${T("ust.model")}</button>
        <a class="j-link" href=${basePath() + OSADZONE[pod]} target="_blank" rel="noopener">${T("szuflada.pelne_okno")}<${Ikona} n="ext" r=${14}/></a></div>
      <${Osadzona} key=${pod} sciezka=${OSADZONE[pod]} tytul=${T(`szuflada.${pod}`)} onEsc=${zamknij}/></div>`;
  }
  return html`<${Naglowek} id="model"/>
    <div class="j-karta">
      ${["klucze", "modele"].map((p) => html`<${Wiersz} key=${p} ikona=${p === "klucze" ? "plug" : "cpu"} tytul=${T(`szuflada.${p}`)} opis=${T(`szuflada.${p}_opis`)}>
        <${Przycisk} maly data-pod=${p} onClick=${() => idz("model", p)}>${T("ui.otworz")}</${Przycisk}></${Wiersz}>`)}
    </div>`;
}

// Telegram (tylko odczyt): każdy rozmówca ma swój temat w grupie Jarvo; lustro zmienia się w sekcji Rozmówcy
function SekcjaTelegram({ idz }) {
  const rozmowcy = useSklep((s) => s.rozmowcy) || [];
  return html`<${Naglowek} id="telegram"/>
    <div class="j-karta">${rozmowcy.map((r) => html`<${Wiersz} key=${r.klucz} ikona="tg" tytul=${nazwaRozmowcy(r)}
      opis=${`${r.temat ? T("ust.temat_jest") : T("ust.temat_brak")} · ${T(r.lustro ? "ust.lustro_wl" : "ust.lustro_wyl")}`}/>`)}
    </div>
    <div class="j-sz-akcje"><${Przycisk} maly onClick=${() => idz("rozmowcy")}>${T("ust.lustro_zmien")}</${Przycisk}></div>`;
}

// Powiadomienia: dźwięk i powiadomienia przeglądarki („czeka na Ciebie”, koniec długiej pracy; 30-pasek.js)
function SekcjaPowiadomienia() {
  const u = useSklep((s) => s.ustawienia);
  const wspiera = typeof window !== "undefined" && "Notification" in window;
  const [zgoda, setZgoda] = useState(wspiera ? Notification.permission : "brak");
  const powiadomienia = async (v) => {
    sklep.zmien("ustawienia", { powiadomienia: v, zapytano_o_powiadomienia: true });
    if (v && wspiera && Notification.permission === "default") setZgoda(await Notification.requestPermission());
  };
  return html`<${Naglowek} id="powiadomienia"/>
    <div class="j-karta">
      <${Wiersz} ikona="alert" tytul=${T("ust.powiadomienia_przegladarki")} opis=${T(`ust.zgoda_${zgoda}`)}>
        <${Przelacznik} wl=${u.powiadomienia && wspiera} disabled=${!wspiera || zgoda === "denied"} etykieta=${T("ust.powiadomienia_przegladarki")}
          onZmien=${powiadomienia}/></${Wiersz}>
      <${Wiersz} ikona="play" tytul=${T("ust.dzwiek")} opis=${T("ust.dzwiek_opis")}>
        <${Przelacznik} wl=${u.dzwiek} etykieta=${T("ust.dzwiek")} onZmien=${(v) => sklep.zmien("ustawienia", { dzwiek: v })}/></${Wiersz}>
    </div>`;
}

// Dostęp (tylko odczyt, GET /app `dostep`): panel w sieci; klucz jednorazowy wydaje `jarvo panel klucz`
function SekcjaDostep() {
  const d = useSklep((s) => s.dostep);
  const adres = d && (d.nazwa || d.adres) ? `http://${d.nazwa || d.adres}${d.port ? `:${d.port}` : ""}` : "";
  const stan = !d ? "brak" : !d.wlaczony ? "wyl" : d.blad ? "blad" : d.nasluch ? "ok" : "czeka";
  return html`<${Naglowek} id="dostep"/>
    <div class="j-karta" data-stan=${stan}>
      <${Wiersz} ikona="globe" tytul=${T(`ust.dostep_${stan}`)} opis=${d && d.blad ? String(d.blad) : adres}>
        ${adres && stan === "ok" && html`<code class="j-sz-kod">${adres}</code>`}</${Wiersz}>
    </div>
    <p class="j-sz-uwaga">${T("ust.dostep_klucz")}</p>
    <${Polecenie} etykieta=${T("akt.na_serwerze")} kod="jarvo panel klucz"/>`;
}

function SekcjaWyglad() {
  const motyw = useSklep((s) => s.ustawienia.motyw);
  const paleta = useSklep((s) => s.ustawienia.paleta) || "jarvo";
  return html`<${Naglowek} id="wyglad"/>
    <p class="j-sz-sub">${T("szuflada.motyw")}</p>
    <${Wybor} etykieta=${T("szuflada.motyw")} wartosc=${motyw} onWybierz=${(m) => sklep.zmien("ustawienia", { motyw: m })}
      opcje=${Motyw.WYBORY.map((m) => [m, T(`motyw.${m}`)])}/>
    <p class="j-sz-sub">${T("ust.paleta")}</p>
    <div class="j-wybor j-ust-palety" role="radiogroup" aria-label=${T("ust.paleta")}>${PALETY.map((p) => html`<button type="button"
      key=${p.id} role="radio" aria-checked=${String(p.id === paleta)} data-paleta=${p.id}
      onClick=${() => sklep.zmien("ustawienia", { paleta: p.id })}><span class="j-ust-probka" style=${{ background: p.kolor }}></span>${isPL() ? p.pl : p.en}</button>`)}</div>
    <p class="j-sz-uwaga">${T("ust.paleta_opis")}</p>`;
}

// język: przez i18n dashboardu (setLocale), więc klasyczne strony Hermesa mówią tym samym językiem; bez niego
// hermes-locale w localStorage i odświeżenie
function SekcjaJezyk() {
  const i18n = useHostI18n();
  const ustawJezyk = (j) => {
    if (i18n && i18n.setLocale) { i18n.setLocale(j); return; }
    try { localStorage.setItem("hermes-locale", j); } catch (_) { /* zablokowane */ }
    location.reload();
  };
  return html`<${Naglowek} id="jezyk"/>
    <${Wybor} etykieta=${T("ust.jezyk")} wartosc=${isPL() ? "pl" : "en"} onWybierz=${ustawJezyk} opcje=${[["pl", "Polski"], ["en", "English"]]}/>
    <p class="j-sz-uwaga">${T("szuflada.jezyk_opis")}</p>`;
}

// System: aktualizacja, konto (wylogowanie), klasyczny panel, wersja i skróty pod „Pokaż”
function SekcjaSystem() {
  return html`<${Naglowek} id="system"/>
    <${Aktualizacja}/>
    <p class="j-sz-sub">${T("szuflada.konto")}</p>
    <div class="j-karta">
      ${bezLogowania()
        ? html`<${Wiersz} ikona="logout" tytul=${T("szuflada.bez_logowania")} opis=${T("szuflada.bez_logowania_opis")}/>`
        : html`<${Wiersz} ikona="logout" tytul=${T("szuflada.wyloguj")} opis=${T("szuflada.wyloguj_opis")}>
          <${Przycisk} maly data-akcja="wyloguj" onClick=${() => api.wyloguj()}>${T("szuflada.wyloguj")}</${Przycisk}></${Wiersz}>`}
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

function SekcjaStaraBaza() {
  return html`<${Naglowek} id="stara-baza"/>
    <div class="j-sz-akcje"><${Przycisk} rodzaj="mocny" onClick=${() => sklep.ustaw({ stara_baza: true })}>${T("szuflada.stara_baza_otworz")}</${Przycisk}></div>`;
}

function Ustawienia({ trasa }) {
  const sekcja = SEKCJE_USTAWIEN.some((s) => s.id === trasa.sekcja) ? trasa.sekcja : null;   // null: lista (telefon)
  const aktywna = sekcja || "rozmowcy";
  const waski = useWaskiEkran();
  const osadzona = aktywna === "model" && OSADZONE[trasa.pod];
  const idz = (s, pod) => Trasa.idz({ widok: "ustawienia", sekcja: s, pod }, { zastap: !waski });
  const wyjdz = () => Trasa.idz({ widok: "start" });
  // telefon: lista sekcji i sekcja to dwa ekrany; fokus na nagłówek sekcji, a po „Wróć” na jej przycisk
  const wejdz = (s) => { Fokus.odloz(".j-sz-tresc h3"); idz(s); };
  const wroc = () => { Fokus.odloz(`.j-sz-p[data-sekcja="${aktywna}"]`); Trasa.idz({ widok: "ustawienia" }); };
  // strzałki góra/dół (Home/End) po liście sekcji
  const klawisz = (e) => {
    const p = [...e.currentTarget.querySelectorAll(".j-sz-p")];
    const i = p.indexOf(document.activeElement);
    const j = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: p.length - 1 }[e.key];
    if (i < 0 || j == null) return;
    e.preventDefault();
    p[(j + p.length) % p.length].focus();
  };
  // Esc (poza oknem i ramką) wychodzi ze strony; w osadzonej stronie wraca do sekcji Model
  const esc = (e) => { if (e.key === "Escape" && !e.defaultPrevented && !e.target.closest(".j-okno")) { e.preventDefault(); osadzona ? idz("model") : wyjdz(); } };
  const tresc = {
    rozmowcy: html`<${SekcjaRozmowcy}/>`,
    model: html`<${SekcjaModel} pod=${trasa.pod} idz=${idz} zamknij=${() => idz("model")}/>`,
    telegram: html`<${SekcjaTelegram} idz=${idz}/>`,
    powiadomienia: html`<${SekcjaPowiadomienia}/>`,
    dostep: html`<${SekcjaDostep}/>`,
    wyglad: html`<${SekcjaWyglad}/>`,
    jezyk: html`<${SekcjaJezyk}/>`,
    zespol: html`<${SekcjaZespol}/>`,
    system: html`<${SekcjaSystem}/>`,
    "stara-baza": html`<${SekcjaStaraBaza}/>`,
  }[aktywna];
  const tytul = T("szuflada.tytul");
  return html`<section class=${cx("j-ust", osadzona && "is-szeroka")} data-widok=${sekcja ? "sekcja" : "lista"} data-region="ustawienia" aria-label=${tytul} onKeyDown=${esc}>
    <${NaglowekWidoku} ikona=${IKONY_WIDOKOW.ustawienia} tytul=${tytul} opis=${waski && !sekcja ? null : T(`ust.${aktywna}`)} klasa="j-ust-gora">
      <${Przycisk} rodzaj="cichy" ikona="x" etykieta=${T("ui.zamknij")} klasa="j-na-telefonie" onClick=${wyjdz}/>
    </${NaglowekWidoku}>
    <nav class="j-sz-nav" aria-label=${tytul} onKeyDown=${klawisz}>
      ${SEKCJE_USTAWIEN.map((s, i) => (s.oddzielnik ? html`<div key=${i} class="j-sz-sep"></div>` : html`<button type="button"
        key=${s.id} class="j-sz-p" data-sekcja=${s.id} aria-current=${s.id === aktywna ? "true" : undefined} data-fokus=${s.id === aktywna ? "" : undefined}
        onClick=${() => wejdz(s.id)}><${Ikona} n=${s.ikona}/><span>${T(`ust.${s.id}`)}</span><${Ikona} n="right" r=${16} klasa="j-sz-dalej"/></button>`))}
    </nav>
    <div class="j-sz-glowna">
      <div class="j-sz-mgora j-na-telefonie"><button type="button" class="j-sz-wroc" onClick=${wroc}>
        <${Ikona} n="back"/>${tytul}</button></div>
      <div class=${cx("j-sz-tresc", osadzona && "is-osadzona")}>${tresc}</div>
    </div>
  </section>`;
}

Zasoby.daj({ Ustawienia });
