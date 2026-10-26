// Pierwsze spotkanie (docs/HQ.md „Pierwsze spotkanie”): rozmowa z Jarvem bez modelu, zaraz po instalacji, na całym
// ekranie (bez paska rozmów i górnej belki, 90-app.js). Jarvo mówi (36-glos.js), pyta o imię, firmę, linki i cel,
// a z odpowiedzi rośnie zdanie z czerwonymi podkreśleniami i notkami („Bohater: Kuba.”). Zapis: POST /app/poznanie →
// USER.md (pola skillu onboarding-interview), więc cała flota wie, dla kogo pracuje. Potem „Brakuje mi tylko mózgu”
// w tej samej karcie: konto ChatGPT (kod urządzenia przez trasy Hermesa) albo klucz API (POST /app/klucz, dostawca
// po przedrostku). W chwili podłączenia: „Mam mózg. Zaczynam pierwszą sesję.” i przejście do wątku „Pierwsza sesja”
// (POST /app/pierwsza-sesja, raz na instalację). Pokazuje się sam, dopóki USER.md nie ma imienia i właściciel nie
// kliknął „Pomiń”; z linii gotowości na starcie otwiera się od razu na kroku „mózg” (sklep.poznanie = "mozg").

const POZNANIE_KROKI = ["witaj", "imie", "firma", "linki", "cele", "mozg"];
const POZNANIE_CELE = ["klienci", "rolki", "strona", "reklamy", "papiery"];
const POZNANIE_POMINIETE = "jarvo.poznanie.pominiete.v1";

// czyste pomocniki (testy: tests/js/hq_front.test.cjs)
const Poznanie = {
  // rodzaj linku z wpisu: @konto = Instagram, domeny serwisów, Mapy Google, inna domena = strona; null = nie link
  link(wpis) {
    const w = String(wpis || "").trim().replace(/^[<(]+|[>),.;]+$/g, "");
    if (!w || w.length > 200 || /\s/.test(w)) return null;
    if (/^@[A-Za-z0-9._]{2,30}$/.test(w)) return { rodzaj: "instagram", wartosc: w };
    const bez = w.replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/+$/, "");
    const [host, ...reszta] = bez.split("/");
    const h = host.toLowerCase();
    if (!/^[a-z0-9ąćęłńóśźż-]+(\.[a-z0-9ąćęłńóśźż-]+)*\.[a-z]{2,}$/.test(h)) return null;
    const sciezka = reszta.join("/");
    const konto = (reszta[0] || "").replace(/^@/, "");
    if (/(^|\.)instagram\.com$/.test(h)) return { rodzaj: "instagram", wartosc: konto ? `@${konto}` : bez };
    if (/(^|\.)tiktok\.com$/.test(h)) return { rodzaj: "tiktok", wartosc: konto ? `@${konto}` : bez };
    if (/(^|\.)(facebook\.com|fb\.com)$/.test(h)) return { rodzaj: "facebook", wartosc: bez };
    if (/(^|\.)(youtube\.com|youtu\.be)$/.test(h)) return { rodzaj: "youtube", wartosc: bez };
    if (/(^|\.)linkedin\.com$/.test(h)) return { rodzaj: "linkedin", wartosc: bez };
    if (/^(maps\.app\.goo\.gl|goo\.gl|g\.page|maps\.google\.[a-z.]+)$/.test(h) || (/^google\.[a-z.]+$/.test(h) && /^maps/.test(sciezka)))
      return { rodzaj: "mapy", wartosc: bez };
    return { rodzaj: "strona", wartosc: bez };
  },
  // wszystkie linki z tekstu (spacje, przecinki, nowe linie), bez powtórek, najwyżej 6
  linki(tekst) {
    const out = [];
    for (const k of String(tekst || "").split(/[\s,;]+/)) {
      const l = Poznanie.link(k);
      if (l && !out.some((x) => x.wartosc.toLowerCase() === l.wartosc.toLowerCase())) out.push(l);
      if (out.length >= 6) break;
    }
    return out;
  },
  // dostawca klucza API po przedrostku (jak hq/plugin/mozg.py rozpoznaj): nazwa do pokazania albo null
  dostawca(klucz) {
    const k = String(klucz || "").trim();
    if (!/^[A-Za-z0-9_.-]{20,300}$/.test(k)) return null;
    if (k.startsWith("sk-or-")) return "OpenRouter";
    if (k.startsWith("sk-ant-")) return "Anthropic";
    if (k.startsWith("sk-")) return "OpenAI";
    return null;
  },
  // jedna linia: bez znaków sterujących, spacje złączone, przycięta
  pole(s, maks = 80) { return String(s || "").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, maks).trim(); },
  imie(s) { return Poznanie.pole(s, 40).replace(/[.,;:!?]+$/, ""); },
  // „a”, „a i b”, „a, b i c”
  wyliczenie(lista, i) { return lista.length < 2 ? lista.join("") : `${lista.slice(0, -1).join(", ")} ${i} ${lista[lista.length - 1]}`; },
  // rosnące zdanie: kawałki {t} (zwykły tekst) i {t, notka} (podkreślone, z notką pod spodem)
  zdanie(d, pl = true) {
    const W = pl ? { hej: "Cześć, jestem ", firma: "Mam firmę ", zaj: "Zajmuję się: ", linki: "Znajdziesz mnie tu: ", cele: "Zależy mi na: ", i: "i" }
      : { hej: "Hi, I'm ", firma: "I run ", zaj: "What I do: ", linki: "Find me at: ", cele: "What matters most: ", i: "and" };
    const k = [];
    if (!d.imie) return k;
    k.push({ t: W.hej }, { t: d.imie, notka: "imie" }, { t: ". " });
    if (d.firma) {
      k.push({ t: W.firma }, { t: d.firma, notka: "firma" });
      if (d.zajecie) k.push({ t: ": " }, { t: d.zajecie, notka: "zajecie" });
      k.push({ t: ". " });
    } else if (d.zajecie) k.push({ t: W.zaj }, { t: d.zajecie, notka: "zajecie" }, { t: ". " });
    const lista = (napis, el) => {
      if (!el.length) return;
      k.push({ t: napis });
      el.forEach((e, n) => {
        if (n > 0) k.push({ t: n === el.length - 1 ? ` ${W.i} ` : ", " });
        k.push(e);
      });
      k.push({ t: ". " });
    };
    lista(W.linki, (d.linki || []).map((l) => ({ t: l.wartosc, notka: l.rodzaj })));
    lista(W.cele, (d.cele || []).map((c) => ({ t: c, notka: "cel" })));
    if (k.length) k[k.length - 1] = { t: k[k.length - 1].t.trimEnd() };
    return k;
  },
};

const poznanieOtwarte = (got) => !!got && !got.profil_wlasciciela && !Pamiec.wez(POZNANIE_POMINIETE, false);

// kwestie Jarva na każdy krok (to samo idzie na ekran i do lektora)
function kwestiePoznania(krok, d, n) {
  if (krok === "witaj") return [T("poz.witaj1"), `${T("poz.intro_zespol", { n })}.`];
  if (krok === "imie") return [T("poz.imie")];
  if (krok === "firma") return [T("poz.milo", { imie: d.imie }), T("poz.firma")];
  if (krok === "linki") return [T("poz.linki")];
  if (krok === "cele") return [T("poz.cele")];
  if (krok === "mozg") {
    if (d.start) return [T("poz.mam_mozg")];
    if (d.model) return [T("poz.gotowe")];
    return d.zapisane ? [T("poz.zapisane"), T("poz.mozg")] : [T("poz.mozg")];
  }
  return [];
}

// ---- karta „Mózg”: konto ChatGPT (kod urządzenia: otwórz stronę, wpisz kod, czekamy na zalogowanie) albo klucz API.
// Klucz idzie tylko do POST /app/klucz (pole hasła, bez podpowiedzi przeglądarki) i nie zostaje w stanie po wysłaniu.
function MozgChatgpt({ gotowe, wejscie }) {
  const [st, setSt] = useState({ etap: "start", kod: "", url: "", sid: "", co: 5, blad: null });
  const [skopiowane, setSkopiowane] = useState(false);
  const sid = useRef("");
  useEffect(() => () => { if (sid.current) api.chatgpt.anuluj(sid.current).catch(() => {}); }, []);
  // czekamy na zalogowanie: odpytanie co `poll_interval` s; zatwierdzone = flota na ChatGPT, potem pierwsza sesja
  useEffect(() => {
    if (st.etap !== "czeka") return undefined;
    let stop = false, t = 0;
    const krok = async () => {
      if (stop) return;
      try {
        const r = await api.chatgpt.stan(st.sid);
        if (stop) return;
        if (r.status === "approved") {
          sid.current = "";
          setSt((x) => ({ ...x, etap: "laczy" }));
          await api.mozgChatgpt();
          if (!stop) gotowe("ChatGPT");
          return;
        }
        if (r.status !== "pending") { sid.current = ""; setSt((x) => ({ ...x, etap: "blad", blad: T(r.status === "expired" ? "poz.chatgpt_wygasl" : "poz.chatgpt_blad") })); return; }
      } catch (e) {
        if (stop) return;
        if (e.status === 404) { sid.current = ""; setSt((x) => ({ ...x, etap: "blad", blad: T("poz.chatgpt_wygasl") })); return; }
        if (e.status && e.status !== 0) { setSt((x) => ({ ...x, etap: "blad", blad: e.tekst() })); return; }
      }
      t = setTimeout(krok, Math.max(3, st.co) * 1000);
    };
    t = setTimeout(krok, Math.max(3, st.co) * 1000);
    return () => { stop = true; clearTimeout(t); };
  }, [st.etap, st.sid]);
  const zacznij = async () => {
    setSt({ etap: "startuje", kod: "", url: "", sid: "", co: 5, blad: null });
    try {
      const r = await api.chatgpt.start();
      sid.current = r.session_id;
      setSt({ etap: "czeka", kod: r.user_code, url: r.verification_url, sid: r.session_id, co: r.poll_interval || 5, blad: null });
      try { window.open(r.verification_url, "_blank", "noopener"); } catch (_) { /* blokada okien: zostaje przycisk */ }
    } catch (e) {
      setSt({ etap: "blad", kod: "", url: "", sid: "", co: 5, blad: e.status ? e.tekst() : T("blad.siec") });
    }
  };
  const kopiuj = () => {
    try { navigator.clipboard.writeText(st.kod).then(() => { setSkopiowane(true); setTimeout(() => setSkopiowane(false), 2000); }); } catch (_) { /* brak schowka */ }
  };
  if (st.etap === "start" || st.etap === "startuje") {
    return html`<div class="j-mozg-tresc"><button type="button" class="j-btn j-btn-glowny" ref=${wejscie} onClick=${zacznij}
        disabled=${st.etap === "startuje"}>${st.etap === "startuje" ? html`<${Spinner}/>` : null}${T("poz.chatgpt_zaloguj")}<${Ikona} n="right" r=${16}/></button>
      <p class="j-mozg-o">${T("poz.chatgpt_jak")}</p></div>`;
  }
  if (st.etap === "blad") {
    return html`<div class="j-mozg-tresc"><p class="j-poz-blad" role="alert">${st.blad}</p>
      <button type="button" class="j-btn" ref=${wejscie} onClick=${zacznij}>${T("poz.ponow")}</button></div>`;
  }
  return html`<div class="j-mozg-tresc">
    <ol class="j-mozg-kroki">
      <li><span>${T("poz.chatgpt_krok1")}</span>
        <a class="j-btn" href=${st.url} target="_blank" rel="noopener noreferrer">${T("poz.chatgpt_otworz")}<${Ikona} n="ext" r=${14}/></a></li>
      <li><span>${T("poz.chatgpt_krok2")}</span>
        <span class="j-mozg-kod" data-kod="">${st.kod}</span>
        <button type="button" class="j-btn" onClick=${kopiuj}>${skopiowane ? T("poz.chatgpt_skopiowane") : T("poz.chatgpt_kopiuj")}</button></li>
    </ol>
    <p class="j-mozg-czeka" role="status"><${Spinner}/>${st.etap === "laczy" ? T("poz.chatgpt_laczy") : T("poz.chatgpt_czekam")}</p>
  </div>`;
}

function MozgKlucz({ gotowe, wejscie }) {
  const [klucz, setKlucz] = useState("");
  const [st, setSt] = useState({ trwa: false, blad: null });
  const nazwa = Poznanie.dostawca(klucz);
  // bez własnego <form>: karta siedzi w formularzu rozmowy, a zagnieżdżony formularz nie wysyła się w React;
  // Enter w polu robi to samo co „Podłącz” i nie wysyła formularza rozmowy
  const wyslij = async (e) => {
    if (e) e.preventDefault();
    if (!nazwa || st.trwa) return;
    setSt({ trwa: true, blad: null });
    try {
      const r = await api.klucz(klucz.trim());
      setKlucz("");
      gotowe(r.nazwa || nazwa);
    } catch (err) {
      setSt({ trwa: false, blad: err.status ? err.tekst() : T("blad.siec") });
    }
  };
  return html`<div class="j-mozg-tresc">
    <label class="j-poz-pole"><span class="j-poz-e">${T("poz.klucz_etykieta")}</span>
      <input ref=${wejscie} type="password" value=${klucz} maxLength="400" autoComplete="off" spellCheck="false"
        autoCapitalize="off" placeholder=${T("poz.klucz_przyklad")} data-klucz="" disabled=${st.trwa}
        onInput=${(e) => { setKlucz(e.target.value); setSt({ trwa: false, blad: null }); }}
        onKeyDown=${(e) => { if (e.key === "Enter") wyslij(e); }}/></label>
    <p class="j-mozg-o" aria-live="polite">${klucz.trim()
      ? (nazwa ? html`<span class="j-poz-znacznik"><${Ikona} n="check" r=${13}/>${nazwa}</span>` : T("poz.klucz_nieznany"))
      : html`${T("poz.klucz_brak")} <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer">openrouter.ai/keys</a>`}</p>
    ${st.blad && html`<p class="j-poz-blad" role="alert">${st.blad}</p>`}
    <div class="j-poz-akcje"><button type="button" class="j-btn j-btn-glowny" disabled=${!nazwa || st.trwa} onClick=${wyslij}>
      ${st.trwa ? html`<${Spinner}/>${T("poz.klucz_sprawdzam", { nazwa })}` : T("poz.klucz_podlacz")}${st.trwa ? null : html`<${Ikona} n="right" r=${16}/>`}</button></div>
  </div>`;
}

function KartaMozgu({ gotowe, pozniej, wejscie }) {
  const [tryb, setTryb] = useState(null);
  const opcja = (t, tytul, opis) => html`<button type="button" class=${cx("j-poz-kupon", tryb === t && "is-wybrany")}
      aria-pressed=${tryb === t} ref=${t === "chatgpt" && !tryb ? wejscie : undefined} onClick=${() => setTryb(t)}>
    <b>${tytul}</b><small>${opis}</small></button>`;
  return html`<div class="j-mozg" data-tryb=${tryb || ""}>
    <div class="j-poz-kupony" role="group" aria-label=${T("poz.mozg_wybor")}>
      ${opcja("chatgpt", T("poz.kupon_chatgpt"), T("poz.kupon_chatgpt_o"))}
      ${opcja("klucz", T("poz.kupon_klucz"), T("poz.kupon_klucz_o"))}
    </div>
    ${tryb === "chatgpt" && html`<${MozgChatgpt} gotowe=${gotowe} wejscie=${wejscie}/>`}
    ${tryb === "klucz" && html`<${MozgKlucz} gotowe=${gotowe} wejscie=${wejscie}/>`}
    <button type="button" class="j-link j-poz-pozniej" onClick=${pozniej}>${T("poz.pozniej")}</button>
  </div>`;
}

function ZdaniePoznania({ d }) {
  const k = Poznanie.zdanie(d, isPL());
  if (!k.length) return html`<p class="j-poz-zd is-puste">${T("poz.zdanie_puste")}</p>`;
  return html`<p class="j-poz-zd">${k.map((x, i) => (x.notka
    ? html`<span key=${i} class="j-poz-u" data-notka=${x.notka}>${x.t}<small>${T(`poz.notka.${x.notka}`)}</small></span>`
    : html`<span key=${i}>${x.t}</span>`))}</p>`;
}

// Powitanie (krok „witaj”): robot i „Cześć. Jestem Jarvo.” wchodzą animacją, a po chwili (albo po kliknięciu,
// Enter, spacji) zjeżdżają w górę i zaczyna się rozmowa od pytania o imię. Bez ruchu (prefers-reduced-motion)
// od razu cały tekst i krótsza pauza.
const INTRO_MS = 3600, INTRO_BEZ_RUCHU_MS = 1200, INTRO_WYJSCIE_MS = 420;
function PoznanieIntro({ n, mowi, dalej }) {
  const ruch = !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [wyjscie, setWyjscie] = useState(false);
  const raz = useRef(false);
  const idz = () => {
    if (raz.current) return;
    raz.current = true;
    Glos.odblokuj();
    setWyjscie(true);
    setTimeout(dalej, ruch ? INTRO_WYJSCIE_MS : 0);
  };
  useEffect(() => {
    const t = setTimeout(idz, ruch ? INTRO_MS : INTRO_BEZ_RUCHU_MS);
    const klawisz = (e) => { if (["Enter", " ", "Escape"].includes(e.key)) { e.preventDefault(); idz(); } };
    window.addEventListener("keydown", klawisz);
    return () => { clearTimeout(t); window.removeEventListener("keydown", klawisz); };
  }, []);
  const slowa = (tekst, od) => tekst.split(" ").map((s, i) => html`<span key=${`${od}:${i}`} class="j-intro-s"
    style=${{ "--i": od + i }}>${s}</span>`);
  const czesc = T("poz.intro_czesc").split(" ");
  return html`<div class=${cx("j-intro", wyjscie && "is-wyjscie")} onClick=${idz} data-intro="">
    <${Robot} r=${132} mowi=${mowi} klasa="j-intro-robot"/>
    <h1 class="j-intro-t">${slowa(czesc.join(" "), 0)}<br/>${slowa(T("poz.intro_jestem"), czesc.length)}${" "}<em
      class="j-intro-s j-intro-imie" style=${{ "--i": czesc.length + 1 }}>Jarvo.</em></h1>
    <p class="j-intro-o">${T("poz.intro_zespol", { n })}</p>
    <p class="j-intro-d">${T("poz.intro_dalej")}</p>
  </div>`;
}

function Poznajmy({ koniec, poczatek = "witaj" }) {
  const got = useSklep((s) => s.gotowosc);
  const wlasciciel = useSklep((s) => s.wlasciciel);
  const ileAgentow = useSklep((s) => s.kolejnosc.filter((n) => n !== "jarvo").length);
  const { mowi } = useGlos();
  const [krok, setKrok] = useState(poczatek);
  const [d, setD] = useState(() => ({ imie: (poczatek === "mozg" && wlasciciel && wlasciciel.imie) || "",
    firma: (poczatek === "mozg" && wlasciciel && wlasciciel.firma) || "", zajecie: "", linki: [], cele: [] }));
  const [zapisane, setZapisane] = useState(false);
  const [sesja, setSesja] = useState({ start: false, blad: null });   // „Mam mózg. Zaczynam pierwszą sesję.”
  const [pole, setPole] = useState("");
  const [pole2, setPole2] = useState("");
  const [inny, setInny] = useState("");
  const [zapis, setZapis] = useState({ trwa: false, blad: null });
  const wejscie = useRef(null);
  const model = !!(got && got.model && got.model.polaczony);
  const bylaSesja = !!(got && got.pierwsza_sesja);
  const kwestie = kwestiePoznania(krok, { ...d, model, zapisane, start: sesja.start }, ileAgentow || 9);

  // stałe kwestie do lektora od razu (wsad w tle), żeby grały bez czekania
  useEffect(() => {
    if (poczatek !== "mozg") sklep.ustaw({ poznanie: "trwa" });
    Glos.przygotuj([T("poz.witaj1"), `${T("poz.intro_zespol", { n: ileAgentow || 9 })}.`, T("poz.imie"), T("poz.firma"), T("poz.linki"),
      T("poz.cele"), T("poz.zapisane"), T("poz.mozg"), T("poz.mam_mozg")]);
    return () => Glos.ucisz();
  }, []);
  // każdy krok: Jarvo mówi, fokus na polu odpowiedzi
  useEffect(() => {
    Glos.powiedz(kwestie);
    // bez zabierania kursora z pola, w którym właściciel już pisze (inaczej reszta tekstu wpadłaby do pierwszego pola)
    const t = setTimeout(() => {
      const a = document.activeElement;
      if (wejscie.current && !(a && /^(INPUT|TEXTAREA)$/.test(a.tagName))) wejscie.current.focus({ preventScroll: true });
    }, 60);
    return () => clearTimeout(t);
  }, [krok]);
  // imię wpisane: „Miło mi, Kuba.” robi się w tle, zanim padnie
  useEffect(() => {
    if (krok !== "imie") return undefined;
    const imie = Poznanie.imie(pole);
    if (!imie) return undefined;
    const t = setTimeout(() => Glos.pobierz(T("poz.milo", { imie })).catch(() => {}), 700);
    return () => clearTimeout(t);
  }, [pole, krok]);
  // „Brakuje mi tylko mózgu”: gotowość odświeżana co 5 s (model mógł zostać podłączony w innej karcie albo w panelu)
  useEffect(() => {
    if (krok !== "mozg" || model) return undefined;
    const t = setInterval(() => { if (document.visibilityState !== "hidden") akcje.wczytajAplikacje(); }, 5000);
    return () => clearInterval(t);
  }, [krok, model]);
  // mózg jest, a pierwszej sesji jeszcze nie było: Jarvo mówi „Mam mózg. Zaczynam pierwszą sesję.” i po chwili
  // (lektor zaczyna mówić) przechodzi do wątku; błąd zostawia „Do pracy”. Bez profilu (spotkanie pominięte, mózg
// z linii gotowości) sesji nie ma: serwer chce imienia z USER.md, więc zostaje „Do pracy”.
  const profil = !!(got && got.profil_wlasciciela);
  const zacznijSesje = () => {
    if (sesja.start || !profil) return;
    setSesja({ start: true, blad: null });
    setTimeout(() => {
      akcje.zacznijPierwszaSesje().catch((e) => setSesja({ start: false, blad: e.status ? e.tekst() : T("blad.siec") }));
    }, 1600);
  };
  useEffect(() => {
    if (krok !== "mozg" || !model) return;
    if (!bylaSesja && !sesja.blad) zacznijSesje();
  }, [krok, model, profil]);
  useEffect(() => { if (sesja.start) Glos.powiedz([T("poz.mam_mozg")]); }, [sesja.start]);
  const podlaczony = () => { akcje.wczytajAplikacje(); zacznijSesje(); };

  const dalej = (nastepny, zmiana) => {
    Glos.odblokuj();
    if (zmiana) setD((x) => ({ ...x, ...zmiana }));
    setPole(""); setPole2("");
    setKrok(nastepny);
  };
  const zapisz = async (dane) => {
    Glos.odblokuj();
    setZapis({ trwa: true, blad: null });
    try {
      const w = await api.poznanie({ imie: dane.imie, firma: dane.firma, zajecie: dane.zajecie, linki: dane.linki, cele: dane.cele });
      sklep.ustaw({ wlasciciel: w.wlasciciel || null, gotowosc: w.gotowosc || got });
      setZapis({ trwa: false, blad: null });
      setD(dane);
      setZapisane(true);
      setKrok("mozg");
    } catch (e) {
      setZapis({ trwa: false, blad: e.status ? T("poz.blad_zapisu") : T("blad.siec") });
    }
  };
  const pomin = () => { Pamiec.daj(POZNANIE_POMINIETE, true); Glos.ucisz(); koniec(); };
  const wyslij = (e) => {
    e.preventDefault();
    if (krok === "imie") { const imie = Poznanie.imie(pole); return imie ? dalej("firma", { imie }) : null; }
    if (krok === "firma") return dalej("linki", { firma: Poznanie.pole(pole), zajecie: Poznanie.pole(pole2, 120) });
    if (krok === "linki") return dalej("cele", { linki: Poznanie.linki(pole) });
    if (krok === "cele") {
      const cele = [...d.cele, ...(Poznanie.pole(inny) ? [Poznanie.pole(inny)] : [])].slice(0, 6);
      return zapisz({ ...d, cele });
    }
    return null;
  };
  const przelaczCel = (c) => setD((x) => ({ ...x, cele: x.cele.includes(c) ? x.cele.filter((y) => y !== c) : [...x.cele, c].slice(0, 6) }));
  const nr = POZNANIE_KROKI.indexOf(krok);
  const linkiTeraz = krok === "linki" ? Poznanie.linki(pole) : [];
  const podglad = krok === "linki" ? { ...d, linki: linkiTeraz } : krok === "imie" ? { ...d, imie: Poznanie.imie(pole) }
    : krok === "firma" ? { ...d, firma: Poznanie.pole(pole), zajecie: Poznanie.pole(pole2, 120) } : d;

  return html`<div class="j-poz" data-krok=${krok}>
    <header class="j-poz-gora">
      <${Robot} r=${52} mowi=${mowi}/>
      <div class="j-poz-kto"><b>Jarvo</b><${GlosFala}/></div>
      <${ZmienGlos} probka=${T("glos.probka")}/>
      ${krok !== "mozg" && html`<button type="button" class="j-link j-poz-pomin" onClick=${pomin}>${T("poz.pomin")}</button>`}
    </header>
    ${krok === "witaj" ? html`<${PoznanieIntro} n=${ileAgentow || 9} mowi=${mowi} dalej=${() => dalej("imie")}/>` : html`
    <div class="j-poz-in">
      <section class="j-poz-arkusz" aria-label=${T("poz.arkusz")}>
        <p class="j-poz-kicker">${T("poz.kicker")}</p>
        <h1 class="j-poz-boh">${T("poz.bohater")} <em class=${cx(!podglad.imie && "is-puste")}>${podglad.imie ? `${podglad.imie}.` : ""}</em></h1>
        <${ZdaniePoznania} d=${podglad}/>
      </section>
      <form class="j-poz-rozm" onSubmit=${wyslij} aria-live="polite">
        <div class="j-poz-mowa">${kwestie.map((z, i) => html`<p key=${`${krok}:${i}`} class=${cx(i === kwestie.length - 1 && "is-pytanie")}>${z}</p>`)}</div>
        ${krok === "imie" && html`<label class="j-poz-pole"><span class="j-sr">${T("poz.imie")}</span>
          <input ref=${wejscie} value=${pole} maxLength="40" autoComplete="given-name" placeholder=${T("poz.imie_przyklad")}
            onInput=${(e) => setPole(e.target.value)}/></label>`}
        ${krok === "firma" && html`<label class="j-poz-pole"><span class="j-poz-e">${T("poz.firma_nazwa")}</span>
            <input ref=${wejscie} value=${pole} maxLength="80" autoComplete="organization" placeholder=${T("poz.firma_przyklad")}
              onInput=${(e) => setPole(e.target.value)}/></label>
          <label class="j-poz-pole"><span class="j-poz-e">${T("poz.zajecie")}</span>
            <input value=${pole2} maxLength="120" placeholder=${T("poz.zajecie_przyklad")} onInput=${(e) => setPole2(e.target.value)}/></label>`}
        ${krok === "linki" && html`<label class="j-poz-pole"><span class="j-sr">${T("poz.linki")}</span>
            <textarea ref=${wejscie} value=${pole} rows="2" maxLength="600" placeholder=${T("poz.linki_przyklad")}
              onInput=${(e) => setPole(e.target.value)}
              onKeyDown=${(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form.requestSubmit(); } }}></textarea></label>
          ${linkiTeraz.length > 0 && html`<p class="j-poz-rozpoznane">${linkiTeraz.map((l) => html`<span key=${l.wartosc} class="j-poz-znacznik">
            <${Ikona} n="check" r=${13}/>${T(`poz.notka.${l.rodzaj}`)}</span>`)}</p>`}`}
        ${krok === "cele" && html`<div class="j-poz-cele" role="group" aria-label=${T("poz.cele")}>
            ${POZNANIE_CELE.map((c) => { const t = T(`poz.cel.${c}`); return html`<button type="button" key=${c} aria-pressed=${d.cele.includes(t)}
              class=${cx("j-poz-cel", d.cele.includes(t) && "is-wybrany")} ref=${c === POZNANIE_CELE[0] ? wejscie : undefined}
              onClick=${() => przelaczCel(t)}>${t}</button>`; })}
          </div>
          <label class="j-poz-pole"><span class="j-poz-e">${T("poz.cel_inny")}</span>
            <input value=${inny} maxLength="80" placeholder=${T("poz.cel_inny_przyklad")} onInput=${(e) => setInny(e.target.value)}/></label>`}
        ${krok === "mozg" && (sesja.start
          ? html`<p class="j-mozg-czeka" role="status"><${Spinner}/>${T("poz.otwieram")}</p>`
          : model || sesja.blad
            ? html`${sesja.blad && html`<p class="j-poz-blad" role="alert">${sesja.blad}</p>`}
                <div class="j-poz-akcje"><button type="button" class="j-btn j-btn-glowny" ref=${wejscie} onClick=${() => koniec()}>${T("poz.do_pracy")}<${Ikona} n="right" r=${16}/></button></div>`
            : html`<${KartaMozgu} gotowe=${podlaczony} pozniej=${() => koniec()} wejscie=${wejscie}/>`)}
        ${zapis.blad && html`<p class="j-poz-blad" role="alert">${zapis.blad}</p>`}
        ${krok !== "mozg" && html`<div class="j-poz-akcje">
          <button type="submit" class="j-btn j-btn-glowny" disabled=${(krok === "imie" && !Poznanie.imie(pole)) || zapis.trwa}>
            ${krok === "cele" ? T("poz.zapisz") : T("poz.dalej")}<${Ikona} n="right" r=${16}/></button>
          ${["firma", "linki", "cele"].includes(krok) && html`<button type="button" class="j-link"
              onClick=${() => (krok === "cele" ? zapisz(d) : dalej(krok === "firma" ? "linki" : "cele"))}>${T("poz.pomin_pytanie")}</button>`}
        </div>`}
        <ol class="j-poz-kroki" aria-label=${T("poz.postep", { n: nr + 1, z: POZNANIE_KROKI.length })}>
          ${POZNANIE_KROKI.map((k, i) => html`<li key=${k} class=${cx(i < nr && "is-zrobiony", i === nr && "is-teraz")}>${String(i + 1).padStart(2, "0")}</li>`)}
        </ol>
      </form>
    </div>`}
  </div>`;
}
