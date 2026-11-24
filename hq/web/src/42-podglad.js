// Okno podglądu na żywo (pakiet na żądanie „podglad”, docs/HQ.md „Podgląd na żywo”): jeden WebSocket
// /podglad/ws (hq/plugin/podglad_zywo.py) z tokenem sesji panelu, obraz telefonu w H.264 dekodowany przez WebCodecs
// (VideoDecoder z optimizeForLatency, rysowanie na canvas zaraz po dekodzie), JPEG Komputera przez createImageBitmap.
// Na komputerze (≥ 1100 px) panel po prawej stronie rozmowy, na telefonie pływający podgląd w rogu (przeciąganie
// palcem, stuknięcie = pełny ekran, zrzucenie w dół = zamknij). Stany zawsze słowami, nigdy czarny ekran; opóźnienie
// z czasu odbioru ramki na serwerze i różnicy zegarów (ping przy połączeniu); krótki okrąg w miejscu stuknięcia
// agenta; zakładki urządzeń z kropką przy tym, na którym agent pracuje, i „Za agentem”. Tylko podgląd, bez sterowania.

// SPS z konfiguracji H.264 (Annex B): pierwsza jednostka NAL typu 7, bez kodu startu
function spsZKonfiguracji(b) {
  for (let i = 0; i + 3 < b.length; i++) {
    if (b[i] === 0 && b[i + 1] === 0 && b[i + 2] === 1) {
      if ((b[i + 3] & 0x1f) === 7) return b.subarray(i + 3);
      i += 2;
    }
  }
  return null;
}
// kodek WebCodecs z SPS: avc1.<profil><ograniczenia><poziom> w hex
const kodekAvc = (sps) => `avc1.${[sps[1], sps[2], sps[3]].map((x) => x.toString(16).padStart(2, "0")).join("")}`;

// punkt agenta (piksele ekranu telefonu albo CSS strony Komputera) jako ułamek obrazu; telefon po obrocie: wymiary
// ekranu zamienione, gdy obraz jest poziomy, a ekran opisany pionowo
function punktNaObrazie(punkt, ekran, obraz) {
  if (!punkt || !ekran || !ekran.szer || !ekran.wys || !obraz || !obraz.w || !obraz.h) return null;
  let { szer, wys } = ekran;
  if ((obraz.w > obraz.h) !== (szer > wys)) [szer, wys] = [wys, szer];
  const x = punkt.x / szer, y = punkt.y / wys;
  return x >= 0 && x <= 1 && y >= 0 && y <= 1 ? { x, y } : null;
}

// który napis zamiast obrazu (albo null, gdy obraz jest i nic nie trzeba mówić)
function napisPodgladu(s, nazwa, koniecS) {
  if (s.bladObrazu) return typeof window !== "undefined" && !window.isSecureContext
    ? L("Obraz telefonu działa tylko w panelu z kłódką, pod adresem https.",
      "The phone view needs the panel over https.")
    : L("Ta przeglądarka nie pokaże obrazu telefonu. Otwórz panel w Chrome, Edge albo Safari 17.",
      "This browser cannot show the phone. Open the panel in Chrome, Edge or Safari 17.");
  if (s.polaczenie !== "otwarte") return L("Łączę…", "Connecting…");
  if (s.stan === "niedostepny") return s.opis || L("Podgląd tego urządzenia jest niedostępny.", "Live view of this device is unavailable.");
  if (s.stan === "poza_siecia") return s.u === "komputer" ? L("Komputer nie odpowiada, łączę ponownie", "The Computer does not answer, reconnecting")
    : L("Telefon poza siecią, łączę ponownie", "Phone offline, reconnecting");
  if (s.ekran && s.ekran.wlaczony === false) return L("Ekran wygaszony", "Screen is off");
  if (!s.klatka) return L(`Łączę z: ${nazwa}`, `Connecting to ${nazwa}`);
  if (koniecS != null) return L(`Skończył ${koniecS} s temu`, `Finished ${koniecS} s ago`);
  return null;
}

// Połączenie poza Reactem: WebSocket, dekoder, rysowanie i zegar; `zmien(stan)` daje Reactowi zmiany (opóźnienie
// najwyżej 4 razy na sekundę)
class PolaczeniePodgladu {
  constructor(canvas, zmien) {
    Object.assign(this, { canvas, zmien, u: undefined, przesuniecie: 0, rtt: Infinity, proby: 0, koniec: false, czasy: new Map(),
      dekoder: null, kodek: null, config: null, czekaKlucza: true, jpegZajety: false, jpegNastepny: null, ostatniZnak: 0 });
    this.otworz();
  }
  otworz() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = this.ws = new WebSocket(`${proto}://${location.host}${basePath()}${API_ROOT}/podglad/ws?token=${encodeURIComponent(window.__HERMES_SESSION_TOKEN__ || "")}`);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      this.proby = 0;
      this.zmien({ polaczenie: "otwarte" });
      [0, 150, 400, 900].forEach((t) => setTimeout(() => this.wyslij({ typ: "ping", t: Date.now() }), t));
      this.zegar = setInterval(() => this.wyslij({ typ: "ping", t: Date.now() }), 10000);
      if (this.u !== undefined) this.wyslij({ typ: "patrz", u: this.u });
    };
    ws.onmessage = (e) => (typeof e.data === "string" ? this.tekst(JSON.parse(e.data)) : this.binarne(e.data));
    ws.onclose = () => {
      clearInterval(this.zegar);
      if (this.koniec) return;
      this.zmien({ polaczenie: "laczy" });
      this.ponow = setTimeout(() => this.otworz(), Math.min(5000, 500 * 2 ** this.proby++));
    };
  }
  wyslij(d) { if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(d)); }
  patrz(u) {
    this.u = u;
    this.zamknijDekoder();
    this.config = null;
    const g = this.canvas && this.canvas.getContext("2d");
    if (g) g.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.zmien({ klatka: false, sesja: null, ekran: null, komputer: null, stan: "laczy", opis: "", opoznienie: null });
    this.wyslij({ typ: "patrz", u });
  }
  tekst(d) {
    if (d.typ === "pong") {
      const teraz = Date.now(), rtt = teraz - d.t;
      if (rtt < this.rtt) { this.rtt = rtt; this.przesuniecie = d.s - (d.t + teraz) / 2; }
    } else if (d.typ === "witaj") this.zmien({ telefony: d.telefony || [], komputerJest: !!d.komputer, agent: d.agent, przydzialy: d.przydzialy || {} });
    else if (d.typ === "agent") this.zmien({ agent: d.agent });
    else if (d.typ === "stan") this.zmien({ u: d.u, stan: d.stan, opis: d.opis || "" });
    else if (d.typ === "ekran") this.zmien({ ekran: { wlaczony: d.wlaczony, zablokowany: d.zablokowany, szer: d.szer, wys: d.wys } });
    else if (d.typ === "sesja") this.zmien({ u: d.u, sesja: { w: d.w, h: d.h } });
    else if (d.typ === "klatka") this.zmien({ komputer: { szer: d.w_css, wys: d.h_css, tytul: d.tytul } });
  }
  binarne(buf) {
    const v = new DataView(buf), typ = v.getUint8(0), czas = v.getFloat64(1), pts = Number(v.getBigInt64(9));
    const dane = new Uint8Array(buf, 17);
    if (typ === 4) return this.jpeg(dane, czas);
    if (typ === 1) {
      this.config = dane.slice();
      const sps = spsZKonfiguracji(this.config), kodek = sps && kodekAvc(sps);
      if (kodek && (kodek !== this.kodek || !this.dekoder || this.dekoder.state !== "configured")) this.nowyDekoder(kodek);
      this.czekaKlucza = true;
      return undefined;
    }
    const d = this.dekoder;
    if (!d || d.state !== "configured" || (typ === 3 && this.czekaKlucza)) return undefined;
    let dane2 = dane;
    if (typ === 2) {                                   // konfiguracja przed klatką kluczową (Annex B bez opisu)
      dane2 = new Uint8Array(this.config.length + dane.length);
      dane2.set(this.config);
      dane2.set(dane, this.config.length);
      this.czekaKlucza = false;
    } else if (d.decodeQueueSize > 30) {               // dekoder nie nadąża: do następnej klatki kluczowej
      this.czekaKlucza = true;
      return undefined;
    }
    this.czasy.set(pts, czas);
    if (this.czasy.size > 300) this.czasy.delete(this.czasy.keys().next().value);
    d.decode(new EncodedVideoChunk({ type: typ === 2 ? "key" : "delta", timestamp: pts, data: dane2 }));
    return undefined;
  }
  nowyDekoder(kodek) {
    this.zamknijDekoder();
    if (typeof VideoDecoder === "undefined") { this.zmien({ bladObrazu: true }); return; }
    this.kodek = kodek;
    const d = this.dekoder = new VideoDecoder({
      output: (f) => { const czas = this.czasy.get(f.timestamp); this.czasy.delete(f.timestamp); this.rysuj(f, f.displayWidth, f.displayHeight, czas); f.close(); },
      // błąd dekodera: od nowa od serwera (sesja, konfiguracja i klatka kluczowa z pamięci strumienia)
      error: () => { if (this.dekoder === d) { this.dekoder = null; this.kodek = null; this.wyslij({ typ: "patrz", u: this.u }); } },
    });
    d.configure({ codec: kodek, optimizeForLatency: true });
  }
  zamknijDekoder() {
    const d = this.dekoder;
    this.dekoder = null;
    this.kodek = null;
    this.czekaKlucza = true;
    try { if (d && d.state !== "closed") d.close(); } catch (_) { /* już zamknięty */ }
  }
  jpeg(dane, czas) {
    if (this.jpegZajety) { this.jpegNastepny = [dane, czas]; return; }
    this.jpegZajety = true;
    createImageBitmap(new Blob([dane], { type: "image/jpeg" })).then((b) => { this.rysuj(b, b.width, b.height, czas); b.close(); },
      () => {}).finally(() => {
      this.jpegZajety = false;
      const n = this.jpegNastepny;
      this.jpegNastepny = null;
      if (n) this.jpeg(n[0], n[1]);
    });
  }
  rysuj(obraz, w, h, czas) {
    const c = this.canvas;
    if (!c || this.koniec) return;
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; this.zmien({ obraz: { w, h } }); }
    c.getContext("2d").drawImage(obraz, 0, 0);
    const teraz = Date.now();
    if (!this.maKlatke) { this.maKlatke = true; this.zmien({ klatka: true }); }
    if (czas != null && teraz - this.ostatniZnak > 250) {
      this.ostatniZnak = teraz;
      this.zmien({ klatka: true, opoznienie: Math.max(0, Math.round(teraz + this.przesuniecie - czas)) });
    }
  }
  zamknij() {
    this.koniec = true;
    clearTimeout(this.ponow);
    clearInterval(this.zegar);
    this.zamknijDekoder();
    try { this.ws.close(); } catch (_) { /* już zamknięte */ }
  }
}

const SZEROKI_PODGLAD = "(min-width: 1100px)";

function PodgladOkno({ stan, biezacy }) {
  const szeroki = useMedia(SZEROKI_PODGLAD);
  const canvas = useRef(null), pol = useRef(null);
  const [s, setS] = useState({ polaczenie: "laczy", telefony: [], klatka: false });
  const [u, setU] = useState(stan.u || (biezacy && biezacy.u) || null);
  const [zaAgentem, setZaAgentem] = useState(true);
  const [pelny, setPelny] = useState(false);
  const [kregi, setKregi] = useState([]);
  const [koniecAt, setKoniecAt] = useState(null);
  const byl = useRef(!!biezacy);
  useEffect(() => {
    const p = pol.current = new PolaczeniePodgladu(canvas.current, (z) => {
      if (z.klatka === false) p.maKlatke = false;
      setS((x) => ({ ...x, ...z }));
    });
    return () => p.zamknij();
  }, []);
  useEffect(() => { if (stan.u) { setU(stan.u); setZaAgentem(true); } }, [stan.od]);
  // urządzenie agenta: z kroku, a telefon bez argumentu phone: pliki .busy PhoneUse (serwer), przydział agenta
  const agentU = biezacy ? biezacy.u || s.agent || (s.przydzialy || {})[biezacy.agent] || null : s.agent || null;
  useEffect(() => { if (zaAgentem && agentU && agentU !== u) setU(agentU); }, [zaAgentem, agentU]);
  useEffect(() => { if (pol.current) pol.current.patrz(u); }, [u]);
  const widac = s.u || u;
  // krąg w miejscu stuknięcia albo kliknięcia agenta (gdy krok ma współrzędne)
  useEffect(() => {
    if (!biezacy || !biezacy.punkt || (biezacy.u || agentU) !== widac) return undefined;
    const ekran = widac === "komputer" ? s.komputer : s.ekran;
    const p = punktNaObrazie(biezacy.punkt, ekran, s.obraz);
    if (!p) return undefined;
    const k = { id: `${biezacy.krok.ts}`, ...p };
    setKregi((x) => [...x.slice(-3), k]);
    const t = setTimeout(() => setKregi((x) => x.filter((y) => y !== k)), 900);
    return () => clearTimeout(t);
  }, [biezacy && biezacy.krok]);
  // „Skończył N s temu”: ostatnia klatka przyciemniona, po 30 s okno samo się chowa
  useEffect(() => {
    if (biezacy) { byl.current = true; setKoniecAt(null); } else if (byl.current) setKoniecAt(Date.now() / 1000);
  }, [!!biezacy]);
  const teraz = useTeraz(1000, koniecAt != null);
  const koniecS = koniecAt != null ? Math.max(0, Math.round(teraz - koniecAt)) : null;
  useEffect(() => { if (koniecS != null && koniecS >= 30) NaZywo.zamknij(); }, [koniecS]);
  // panel po prawej: rozmowa robi mu miejsce
  React.useLayoutEffect(() => {
    const k = document.querySelector("[data-jarvo-korzen]");
    if (!k || !szeroki) return undefined;
    k.classList.add("is-podglad-bok");
    return () => k.classList.remove("is-podglad-bok");
  }, [szeroki]);
  // telefon: przeciąganie po rogach, stuknięcie = pełny ekran, zrzucenie na dół = zamknij
  const [rog, setRog] = useState("pd");
  const [przes, setPrzes] = useState(null);
  const ruch = useRef(null);
  const dotyk = szeroki || pelny ? {} : {
    onPointerDown: (e) => { ruch.current = { x: e.clientX, y: e.clientY, t: Date.now() }; e.currentTarget.setPointerCapture(e.pointerId); },
    onPointerMove: (e) => { const r = ruch.current; if (r) setPrzes({ x: e.clientX - r.x, y: e.clientY - r.y }); },
    onPointerUp: (e) => {
      const r = ruch.current;
      ruch.current = null;
      setPrzes(null);
      if (!r) return;
      const dx = e.clientX - r.x, dy = e.clientY - r.y;
      if (Math.hypot(dx, dy) < 10 && Date.now() - r.t < 500) setPelny(true);
      else if (e.clientY > window.innerHeight - 48 && dy > 40) NaZywo.zamknij();
      else setRog(`${e.clientY < window.innerHeight / 2 ? "g" : "d"}${e.clientX < window.innerWidth / 2 ? "l" : "p"}`);
    },
    onPointerCancel: () => { ruch.current = null; setPrzes(null); },
  };
  const urzadzenia = [...(s.telefony || []).map((t) => t.id), ...(s.komputerJest ? ["komputer"] : [])];
  const nazwa = nazwaUrzadzenia(widac);
  const napis = napisPodgladu({ ...s, u: widac }, nazwa, koniecS);
  const naZywo = s.klatka && s.stan === "dziala" && !(s.ekran && s.ekran.wlaczony === false) && koniecS == null;
  const ruchAgenta = biezacy ? `${nazwaAgenta(biezacy.agent)}: ${czasownik(biezacy.krok)}${biezacy.krok.detail ? ` ${biezacy.krok.detail}` : ""}` : "";
  const pionowy = s.obraz ? s.obraz.h >= s.obraz.w : widac !== "komputer";
  return html`<aside class=${cx("j-pz", szeroki ? "is-bok" : "is-pip", !szeroki && `is-${rog}`, pelny && "is-pelny", koniecS != null && "is-koniec")}
      aria-label=${L("Podgląd na żywo", "Live view")} data-urzadzenie=${widac || ""}
      style=${przes ? { transform: `translate(${przes.x}px, ${przes.y}px)` } : undefined}>
    <header class="j-pz-g">
      <b class="j-pz-n">${nazwa}</b>
      ${naZywo && html`<span class="j-pz-zywo" role="status"><span class="j-na-zywo-k" aria-hidden="true"></span>${L("NA ŻYWO", "LIVE")}${s.opoznienie != null ? ` ${s.opoznienie} ms` : ""}</span>`}
      ${pelny && !szeroki && html`<${Przycisk} maly rodzaj="cichy" ikona="down" etykieta=${L("Mniejszy podgląd", "Smaller view")} onClick=${() => setPelny(false)}/>`}
      <${Przycisk} maly rodzaj="cichy" ikona="x" etykieta=${L("Zamknij podgląd", "Close live view")} onClick=${() => NaZywo.zamknij()}/>
    </header>
    ${ruchAgenta && html`<p class="j-pz-ruch" title=${ruchAgenta}>${ruchAgenta}</p>`}
    ${(szeroki || pelny) && urzadzenia.length > 0 && html`<nav class="j-pz-z" aria-label=${L("Urządzenia", "Devices")}>
      ${urzadzenia.map((id) => html`<button type="button" key=${id} aria-pressed=${String(id === widac)}
        onClick=${() => { setZaAgentem(false); setU(id); }}>${id === "komputer" ? L("Komputer", "Computer") : id}
        ${id === agentU && biezacy && html`<span class="j-na-zywo-k" title=${L("Agent pracuje tutaj", "The agent works here")}></span>`}</button>`)}
      <button type="button" class="j-pz-za" aria-pressed=${String(zaAgentem)} onClick=${() => setZaAgentem(!zaAgentem)}>${L("Za agentem", "Follow agent")}</button>
    </nav>`}
    <div class=${cx("j-pz-ekran", pionowy ? "is-pion" : "is-poziom", widac === "komputer" && "is-komputer")} ...${dotyk}>
      <canvas ref=${canvas} class=${cx(!s.klatka && "is-pusty")}></canvas>
      ${kregi.map((k) => html`<span key=${k.id} class="j-pz-krag" style=${{ left: `${k.x * 100}%`, top: `${k.y * 100}%` }} aria-hidden="true"></span>`)}
      ${napis && html`<p class="j-pz-napis" role="status">${s.polaczenie !== "otwarte" || (!s.klatka && s.stan !== "niedostepny") ? html`<${Spinner}/>` : null}${napis}</p>`}
    </div>
  </aside>`;
}

Zasoby.daj({ PodgladOkno, spsZKonfiguracji, kodekAvc, punktNaObrazie, napisPodgladu });
