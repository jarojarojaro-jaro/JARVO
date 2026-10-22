// Pierwsze spotkanie (docs/HQ.md „Pierwsze spotkanie”): rozmowa z Jarvem bez modelu, zaraz po instalacji. Jarvo mówi
// (36-glos.js), pyta o imię, firmę, linki i cel, a z odpowiedzi rośnie zdanie z czerwonymi podkreśleniami i notkami
// („Bohater: Kuba.”). Zapis: POST /app/poznanie → USER.md (pola skillu onboarding-interview), więc cała flota wie,
// dla kogo pracuje. Potem „Brakuje mi tylko mózgu”: konto ChatGPT albo klucz API (Ustawienia › Połączenia); gdy model
// już działa, od razu „Do pracy”. Pokazuje się sam, dopóki USER.md nie ma imienia i właściciel nie kliknął „Pomiń”.

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
  if (krok === "witaj") return [T("poz.witaj1"), T("poz.witaj2", { n })];
  if (krok === "imie") return [T("poz.imie")];
  if (krok === "firma") return [T("poz.milo", { imie: d.imie }), T("poz.firma")];
  if (krok === "linki") return [T("poz.linki")];
  if (krok === "cele") return [T("poz.cele")];
  if (krok === "mozg") return d.model ? [T("poz.zapisane"), T("poz.gotowe")] : [T("poz.zapisane"), T("poz.mozg")];
  return [];
}

function ZdaniePoznania({ d }) {
  const k = Poznanie.zdanie(d, isPL());
  if (!k.length) return html`<p class="j-poz-zd is-puste">${T("poz.zdanie_puste")}</p>`;
  return html`<p class="j-poz-zd">${k.map((x, i) => (x.notka
    ? html`<span key=${i} class="j-poz-u" data-notka=${x.notka}>${x.t}<small>${T(`poz.notka.${x.notka}`)}</small></span>`
    : html`<span key=${i}>${x.t}</span>`))}</p>`;
}

function Poznajmy({ koniec }) {
  const got = useSklep((s) => s.gotowosc);
  const ileAgentow = useSklep((s) => s.kolejnosc.filter((n) => n !== "jarvo").length);
  const { mowi } = useGlos();
  const [krok, setKrok] = useState("witaj");
  const [d, setD] = useState({ imie: "", firma: "", zajecie: "", linki: [], cele: [] });
  const [pole, setPole] = useState("");
  const [pole2, setPole2] = useState("");
  const [inny, setInny] = useState("");
  const [zapis, setZapis] = useState({ trwa: false, blad: null });
  const wejscie = useRef(null);
  const model = !!(got && got.model && got.model.polaczony);
  const kwestie = kwestiePoznania(krok, { ...d, model }, ileAgentow || 9);

  // stałe kwestie do lektora od razu (wsad w tle), żeby grały bez czekania
  useEffect(() => {
    sklep.ustaw({ poznanie: "trwa" });
    Glos.przygotuj([T("poz.witaj1"), T("poz.witaj2", { n: ileAgentow || 9 }), T("poz.imie"), T("poz.firma"), T("poz.linki"),
      T("poz.cele"), T("poz.zapisane"), model ? T("poz.gotowe") : T("poz.mozg")]);
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
  // „Brakuje mi tylko mózgu”: po powrocie z Połączeń gotowość odświeżana, aż model zadziała
  useEffect(() => {
    if (krok !== "mozg" || model) return undefined;
    const t = setInterval(() => { if (document.visibilityState !== "hidden") akcje.wczytajAplikacje(); }, 5000);
    return () => clearInterval(t);
  }, [krok, model]);
  useEffect(() => { if (krok === "mozg" && model) Glos.powiedz([T("poz.gotowe")]); }, [model]);

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
      setKrok("mozg");
    } catch (e) {
      setZapis({ trwa: false, blad: e.status ? T("poz.blad_zapisu") : T("blad.siec") });
    }
  };
  const pomin = () => { Pamiec.daj(POZNANIE_POMINIETE, true); Glos.ucisz(); koniec(); };
  const wyslij = (e) => {
    e.preventDefault();
    if (krok === "witaj") return dalej("imie");
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
        ${krok === "mozg" && (model
          ? html`<div class="j-poz-akcje"><button type="button" class="j-btn j-btn-glowny" ref=${wejscie} onClick=${() => koniec()}>${T("poz.do_pracy")}<${Ikona} n="right" r=${16}/></button></div>`
          : html`<div class="j-poz-kupony">
              <button type="button" class="j-poz-kupon" ref=${wejscie}
                onClick=${() => Trasa.idz({ u: "polaczenia", pod: "modele" }, { scal: true })}>
                <b>${T("poz.kupon_chatgpt")}</b><small>${T("poz.kupon_chatgpt_o")}</small></button>
              <button type="button" class="j-poz-kupon" onClick=${() => Trasa.idz({ u: "polaczenia", pod: "klucze" }, { scal: true })}>
                <b>${T("poz.kupon_klucz")}</b><small>${T("poz.kupon_klucz_o")}</small></button>
              <button type="button" class="j-link j-poz-pozniej" onClick=${() => koniec()}>${T("poz.pozniej")}</button>
            </div>`)}
        ${zapis.blad && html`<p class="j-poz-blad" role="alert">${zapis.blad}</p>`}
        ${krok !== "mozg" && html`<div class="j-poz-akcje">
          ${krok === "witaj"
            ? html`<button type="submit" class="j-btn j-btn-glowny" ref=${wejscie}>${T("poz.zaczynamy")}<${Ikona} n="right" r=${16}/></button>`
            : html`<button type="submit" class="j-btn j-btn-glowny" disabled=${(krok === "imie" && !Poznanie.imie(pole)) || zapis.trwa}>
                ${krok === "cele" ? T("poz.zapisz") : T("poz.dalej")}<${Ikona} n="right" r=${16}/></button>`}
          ${["firma", "linki", "cele"].includes(krok) && html`<button type="button" class="j-link"
              onClick=${() => (krok === "cele" ? zapisz(d) : dalej(krok === "firma" ? "linki" : "cele"))}>${T("poz.pomin_pytanie")}</button>`}
        </div>`}
        <ol class="j-poz-kroki" aria-label=${T("poz.postep", { n: nr + 1, z: POZNANIE_KROKI.length })}>
          ${POZNANIE_KROKI.map((k, i) => html`<li key=${k} class=${cx(i < nr && "is-zrobiony", i === nr && "is-teraz")}>${String(i + 1).padStart(2, "0")}</li>`)}
        </ol>
      </form>
    </div>
  </div>`;
}
