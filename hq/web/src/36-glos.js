// Głos Jarva (docs/HQ.md „Pierwsze spotkanie”): zdania z lokalnego lektora (POST /app/glos: Matcha-TTS-PL, bez sieci)
// grane przez Web Audio z analizatorem, więc fala przy robocie idzie za prawdziwym dźwiękiem. Gdy instalacja nie ma
// lektora (503, stary obraz), mówi głos przeglądarki (speechSynthesis) w języku aplikacji, a bez niego zostaje tekst.
// Wybór głosu (męski / damski), tempa i wyciszenie: localStorage tej przeglądarki („jarvo.glos.v1”).
// Przeglądarka nie gra dźwięku przed pierwszym kliknięciem: wtedy `zablokowany` i przycisk „Włącz głos”.

const GLOS_DOMYSLNY = { glos: "meski", tempo: "normalnie", cisza: false };
const GLOS_TEMPO_MOWY = { spokojnie: 0.92, normalnie: 1.0, zwawo: 1.12 };   // speechSynthesis.rate

const Glos = {
  _sl: new Set(),
  _stan: { mowi: false, zablokowany: false, wersja: 0 },
  _ctx: null, _an: null, _zrodlo: null, _nr: 0, _bufory: new Map(), _brakLektora: false, _ostatnie: null,

  ustawienia() { return { ...GLOS_DOMYSLNY, ...(Pamiec.wez("jarvo.glos.v1", null) || {}) }; },
  zmien(zmiana) {
    Pamiec.daj("jarvo.glos.v1", { ...Glos.ustawienia(), ...zmiana });
    if (zmiana.cisza) Glos.ucisz();
    Glos._ustaw({ wersja: Glos._stan.wersja + 1 });
  },
  stan: () => Glos._stan,
  subskrybuj(f) { Glos._sl.add(f); return () => Glos._sl.delete(f); },
  _ustaw(z) { Glos._stan = { ...Glos._stan, ...z }; Glos._sl.forEach((f) => f()); },

  // kontekst audio po geście właściciela (klik, Enter): bez tego przeglądarka trzyma go w stanie „suspended”
  odblokuj() {
    try {
      if (!Glos._ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        Glos._ctx = new AC();
        Glos._an = Glos._ctx.createAnalyser();
        Glos._an.fftSize = 256;
        Glos._an.smoothingTimeConstant = 0.7;
        Glos._an.connect(Glos._ctx.destination);
      }
      if (Glos._ctx.state === "suspended") Glos._ctx.resume().catch(() => {});
    } catch (_) { /* bez Web Audio: głos przeglądarki */ }
  },

  _klucz(tekst, u) { return `${u.glos}|${u.tempo}|${isPL() ? "pl" : "en"}|${tekst}`; },
  _cialo(tekst, u) { return { tekst, glos: u.glos, tempo: u.tempo, jezyk: isPL() ? "pl" : "en" }; },

  // dźwięk zdania (Promise<ArrayBuffer>), raz na tekst i głos w tej karcie; 503 = instalacja bez lektora
  pobierz(tekst) {
    const u = Glos.ustawienia();
    const k = Glos._klucz(tekst, u);
    if (!Glos._bufory.has(k)) {
      if (Glos._bufory.size > 40) Glos._bufory.delete(Glos._bufory.keys().next().value);
      const p = api.glos(Glos._cialo(tekst, u));
      p.catch((e) => { Glos._bufory.delete(k); if (e && (e.status === 503 || e.status === 404)) Glos._brakLektora = true; });
      Glos._bufory.set(k, p);
    }
    return Glos._bufory.get(k);
  },

  // stałe kwestie rozmowy: serwer robi je jednym wsadem w tle, zanim padną
  przygotuj(teksty) {
    if (Glos._brakLektora || Glos.ustawienia().cisza) return;
    const u = Glos.ustawienia();
    api.glosPrzygotuj({ teksty: teksty.slice(0, 12), glos: u.glos, tempo: u.tempo, jezyk: isPL() ? "pl" : "en" })
      .catch((e) => { if (e && (e.status === 503 || e.status === 404)) Glos._brakLektora = true; });
  },

  ucisz() {
    Glos._nr++;
    try { if (Glos._zrodlo) Glos._zrodlo.stop(); } catch (_) { /* już skończone */ }
    Glos._zrodlo = null;
    try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch (_) { /* brak */ }
    if (Glos._stan.mowi) Glos._ustaw({ mowi: false });
  },

  // zdania po kolei; nowe powiedz() przerywa poprzednie. Zwraca Promise, który kończy się po ostatnim zdaniu.
  async powiedz(zdania) {
    const lista = (Array.isArray(zdania) ? zdania : [zdania]).map((z) => String(z || "").trim()).filter(Boolean);
    Glos.ucisz();
    Glos._ostatnie = lista;
    if (!lista.length || Glos.ustawienia().cisza) return;
    const nr = Glos._nr;
    if (!Glos._brakLektora) lista.forEach((z) => Glos.pobierz(z).catch(() => {}));
    for (const z of lista) {
      if (nr !== Glos._nr) return;
      const ok = Glos._brakLektora ? false : await Glos._grajLektor(z, nr);
      if (nr !== Glos._nr) return;
      if (!ok && Glos._brakLektora) await Glos._grajPrzegladarka(z, nr);
    }
  },
  powtorz() { Glos.odblokuj(); if (Glos._ostatnie) Glos.powiedz(Glos._ostatnie); },

  async _grajLektor(tekst, nr) {
    let dane;
    try { dane = await Glos.pobierz(tekst); } catch (_) { return false; }
    if (nr !== Glos._nr) return true;
    Glos.odblokuj();
    const ctx = Glos._ctx;
    if (!ctx) return false;
    if (ctx.state !== "running") { Glos._ustaw({ zablokowany: true, mowi: false }); Glos._nr++; return true; }
    let bufor;
    try { bufor = await ctx.decodeAudioData(dane.slice(0)); } catch (_) { return false; }
    if (nr !== Glos._nr) return true;
    return new Promise((gotowe) => {
      const zr = ctx.createBufferSource();
      zr.buffer = bufor;
      zr.connect(Glos._an);
      zr.onended = () => { if (Glos._zrodlo === zr) { Glos._zrodlo = null; Glos._ustaw({ mowi: false }); } gotowe(true); };
      Glos._zrodlo = zr;
      Glos._ustaw({ mowi: true, zablokowany: false });
      zr.start();
    });
  },

  _grajPrzegladarka(tekst, nr) {
    const s = window.speechSynthesis;
    if (!s || !window.SpeechSynthesisUtterance) return Promise.resolve(false);
    const jezyk = isPL() ? "pl" : "en";
    const u = Glos.ustawienia();
    return new Promise((gotowe) => {
      const w = new SpeechSynthesisUtterance(tekst);
      w.lang = jezyk === "pl" ? "pl-PL" : "en-US";
      w.rate = GLOS_TEMPO_MOWY[u.tempo] || 1;
      const glosy = (s.getVoices() || []).filter((v) => (v.lang || "").toLowerCase().startsWith(jezyk));
      const zenski = /zofia|paulina|ewa|female|kobiet|woman|samantha|ava/i;
      const wybrany = glosy.find((v) => (u.glos === "damski") === zenski.test(v.name)) || glosy[0];
      if (wybrany) w.voice = wybrany;
      w.onstart = () => { if (nr === Glos._nr) Glos._ustaw({ mowi: true, zablokowany: false }); };
      w.onend = w.onerror = () => { if (nr === Glos._nr) Glos._ustaw({ mowi: false }); gotowe(true); };
      try { s.speak(w); } catch (_) { gotowe(false); }
    });
  },

  // poziomy pasm 0..1 do fali (n pasków); bez analizatora (głos przeglądarki) fala z czasu, gdy Jarvo mówi
  widmo(n) {
    const out = new Array(n).fill(0);
    if (!Glos._stan.mowi) return out;
    if (Glos._an && Glos._zrodlo) {
      const d = new Uint8Array(Glos._an.frequencyBinCount);
      Glos._an.getByteFrequencyData(d);
      const pasmo = Math.max(1, Math.floor((d.length * 0.6) / n));
      for (let i = 0; i < n; i++) {
        let s = 0;
        for (let j = 0; j < pasmo; j++) s += d[i * pasmo + j] || 0;
        out[i] = Math.min(1, s / pasmo / 180);
      }
      return out;
    }
    const t = performance.now() / 1000;
    for (let i = 0; i < n; i++) out[i] = 0.35 + 0.3 * Math.sin(t * 9 + i * 1.7) * Math.sin(t * 2.3 + i);
    return out;
  },
};

const useGlos = () => React.useSyncExternalStore(Glos.subskrybuj, Glos.stan);

// fala głosu: n pasków skalowanych w klatkach animacji (bez renderu Reacta w każdej klatce)
function GlosFala({ n = 9 }) {
  const ref = useRef(null);
  const { mowi } = useGlos();
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const paski = [...el.children];
    if (!mowi) { paski.forEach((p) => { p.style.transform = ""; }); return undefined; }
    let ramka = 0;
    const krok = () => {
      const w = Glos.widmo(paski.length);
      paski.forEach((p, i) => { p.style.transform = `scaleY(${(0.18 + 0.82 * w[i]).toFixed(3)})`; });
      ramka = requestAnimationFrame(krok);
    };
    ramka = requestAnimationFrame(krok);
    return () => cancelAnimationFrame(ramka);
  }, [mowi]);
  return html`<span class=${cx("j-fala", mowi && "is-mowi")} ref=${ref} aria-hidden="true">
    ${Array.from({ length: n }, (_, i) => html`<i key=${i}></i>`)}</span>`;
}

// „Zmień mój głos”: głos, tempo i wyciszenie; po zmianie Jarvo mówi próbkę nowym głosem
function ZmienGlos({ probka }) {
  const [otwarty, setOtwarty] = useState(false);
  const { zablokowany } = useGlos();
  const u = Glos.ustawienia();
  const id = useIdJarvo();
  const ustaw = (z) => {
    Glos.odblokuj();
    Glos.zmien(z);
    if (!z.cisza && probka) Glos.powiedz(probka);
  };
  const wybor = (nazwa, pole, opcje) => html`<div class="j-glos-w" role="radiogroup" aria-label=${nazwa}>
    <span class="j-glos-e">${nazwa}</span>
    ${opcje.map(([v, etykieta]) => html`<button type="button" key=${v} role="radio" aria-checked=${u[pole] === v}
        class=${cx("j-glos-o", u[pole] === v && "is-wybrany")} onClick=${() => ustaw({ [pole]: v, cisza: false })}>${etykieta}</button>`)}
  </div>`;
  return html`<div class="j-glos">
    ${zablokowany && !u.cisza && html`<button type="button" class="j-glos-wlacz" onClick=${() => Glos.powtorz()}>
      <${Ikona} n="play" r=${14}/>${T("glos.wlacz")}</button>`}
    <button type="button" class="j-link j-glos-b" aria-expanded=${otwarty} aria-controls=${`${id}-g`}
      onClick=${() => setOtwarty((o) => !o)}><${Ikona} n="mic" r=${15}/>${T("glos.zmien")}</button>
    ${otwarty && html`<div class="j-glos-p" id=${`${id}-g`}>
      ${wybor(T("glos.glos"), "glos", [["meski", T("glos.meski")], ["damski", T("glos.damski")]])}
      ${wybor(T("glos.tempo"), "tempo", [["spokojnie", T("glos.spokojnie")], ["normalnie", T("glos.normalnie")], ["zwawo", T("glos.zwawo")]])}
      <button type="button" class="j-link" onClick=${() => ustaw({ cisza: !u.cisza })}>${u.cisza ? T("glos.wlacz") : T("glos.wycisz")}</button>
      <p class="j-glos-i">${T("glos.info")}</p>
    </div>`}
  </div>`;
}
