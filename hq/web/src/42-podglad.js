// Okno podglądu na żywo (pakiet na żądanie „podglad”, docs/HQ.md „Podgląd na żywo”): jeden WebSocket
// /podglad/ws (hq/plugin/podglad_zywo.py) z tokenem sesji panelu, obraz telefonu w H.264 dekodowany przez WebCodecs
// (VideoDecoder z optimizeForLatency, rysowanie na canvas zaraz po dekodzie), JPEG Komputera, pulpitu i zrzutów
// telefonu przez createImageBitmap. Na komputerze (≥ 900 px) panel po prawej stronie rozmowy z dziennikiem działań
// agenta pod obrazem, na telefonie pływający podgląd w rogu (przeciąganie palcem, stuknięcie = pełny ekran, zrzucenie
// w dół = zamknij). Stany zawsze słowami, nigdy czarny ekran; znak NA ŻYWO bez liczby ms (24.11 właściciel: liczba
// myliła); krótki okrąg w miejscu stuknięcia agenta; zakładki urządzeń z kropką przy tym, na którym agent pracuje,
// i „Za agentem”. „Przejmij” daje właścicielowi klik, kółko i klawiaturę w Komputerze; schowana karta panelu nie
// patrzy (serwer gasi strumień, zero kosztu).

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

// kadr obrazu wpisany w pole (contain, także w górę) z ramką `ramka` px wokół; całe piksele; null bez pola
const RAMKA_TELEFONU = 5;
function kadrObrazu(pole, obraz, ramka) {
  if (!pole || !obraz || !obraz.w || !obraz.h || pole.w <= 2 * ramka || pole.h <= 2 * ramka) return null;
  const skala = Math.min((pole.w - 2 * ramka) / obraz.w, (pole.h - 2 * ramka) / obraz.h);
  return { w: Math.floor(obraz.w * skala) + 2 * ramka, h: Math.floor(obraz.h * skala) + 2 * ramka };
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
    : s.u === "pulpit" ? L("Pulpit nie odpowiada, łączę ponownie", "The desktop does not answer, reconnecting")
    : L("Telefon poza siecią, łączę ponownie", "Phone offline, reconnecting");
  if (s.ekran && s.ekran.wlaczony === false) return L("Ekran wygaszony", "Screen is off");
  if (!s.klatka) return L(`Łączę z: ${nazwa}`, `Connecting to ${nazwa}`);
  if (koniecS != null) return L(`Skończył ${koniecS} s temu`, `Finished ${koniecS} s ago`);
  return null;
}

// Dziennik działań agenta obok obrazu (wzór dashboardu agent-browser): ostatnie kroki narzędzi pracujących przebiegów
// otwartej rozmowy `wid` (sklep, na żywo), a gdy nikt nie pracuje, ostatniej tury z osi rozmowy (`pozycje` z krokami
// tego samego przebiegu); najstarszy u góry. {agent, wpis_id: wiadomość, od której tura ruszyła, wpisy}
const KROKI_DZIENNIKA = 12;
function dziennikDzialan(przebiegi, wid, pozycje, ile = KROKI_DZIENNIKA) {
  const pusty = { agent: null, wpis_id: null, wpisy: [] };
  if (!wid) return pusty;
  const kroki = (lista) => (lista || []).filter((k) => k && k.komentarz == null && k.narzedzie);
  const wpis = (k, agent, koniec) => ({ ts: k.ts || 0, agent, krok: k, urz: (NaZywo.urzadzenie(k) || {}).u || null,
    wynik: k.blad ? "blad" : k.czas_ms == null && !koniec ? "trwa" : "ok", czas_ms: k.czas_ms });
  const poCzasie = (a, b) => a.ts - b.ts;
  const pracuja = (przebiegi || []).filter((p) => p && p.watek_id === wid && p.stan === "pracuje");
  if (pracuja.length) {
    const ost = pracuja.reduce((a, p) => ((p.utworzony_at || 0) >= (a.utworzony_at || 0) ? p : a));
    const wpisy = pracuja.flatMap((p) => kroki(p.kroki).map((k) => wpis(k, p.agent, false))).sort(poCzasie);
    return { agent: ost.agent, wpis_id: ost.wpis_id || null, wpisy: wpisy.slice(-ile) };
  }
  const lista = pozycje || [];
  let i = lista.length - 1;
  while (i >= 0 && !kroki(lista[i] && lista[i].kroki).length) i--;
  if (i < 0) return pusty;
  const ost = lista[i];
  const tejTury = (x) => !!x && x.rodzaj !== "wlasciciel" && (ost.przebieg_id ? x.przebieg_id === ost.przebieg_id : x.agent === ost.agent);
  let j = i;
  while (j > 0 && tejTury(lista[j - 1])) j--;
  let w = j - 1;
  while (w >= 0 && lista[w].rodzaj !== "wlasciciel") w--;
  const wpisy = lista.slice(j, i + 1).flatMap((x) => kroki(x.kroki).map((k) => wpis(k, x.agent || ost.agent, true))).sort(poCzasie);
  return { agent: ost.agent, wpis_id: w >= 0 ? lista[w].id : null, wpisy: wpisy.slice(-ile) };
}
// nazwa zadania: pierwsza linia wiadomości, od której przebieg się zaczął (`wpis_id` na osi rozmowy), do 90 znaków
function nazwaZadania(pozycje, wpisId) {
  const p = wpisId ? (pozycje || []).find((x) => x && x.id === wpisId) : null;
  const t = p && typeof p.tekst === "string" ? p.tekst.trim().split("\n")[0].trim() : "";
  return t.length > 90 ? `${t.slice(0, 89)}…` : t;
}
const dwie = (x) => String(x).padStart(2, "0");
const godzinaSek = (ts) => { if (!ts) return ""; const d = new Date(ts * 1000); return `${dwie(d.getHours())}:${dwie(d.getMinutes())}:${dwie(d.getSeconds())}`; };
const czasKroku = (ms) => (ms == null ? "" : ms < 60000 ? `${(ms / 1000).toFixed(1).replace(".", L(",", "."))} s` : Czas.trwanie(ms / 1000));
// pulpit: agent działa w obrazie 1280 px szerokości (narzędzie `pulpit`), klatka mówi o ekranie w pikselach
const ekranPulpitu = (o) => (o && o.szer && o.wys ? { szer: Math.min(1280, o.szer), wys: Math.round(o.wys * Math.min(1280, o.szer) / o.szer) } : null);

// „Przejmij”: punkt kliknięcia jako ułamek obrazu (0 do 1) albo null poza obrazem
function punktKlikniecia(r, x, y) {
  if (!r || !r.width || !r.height) return null;
  const fx = (x - r.left) / r.width, fy = (y - r.top) / r.height;
  return fx >= 0 && fx <= 1 && fy >= 0 && fy <= 1 ? { x: fx, y: fy } : null;
}
// klawisz właściciela → działanie sterownika (sterownik_cdp KLAWISZE): znak bez Ctrl, Alt i Cmd (także z AltGr, np. ą)
// to tekst, reszta klawisz z modyfikatorami; same modyfikatory nic nie wysyłają
const KLAWISZE_STEROWNIKA = { Enter: "enter", Tab: "tab", Escape: "escape", Backspace: "backspace", Delete: "delete",
  ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Home: "home", End: "end",
  PageUp: "page_up", PageDown: "page_down", Insert: "insert" };
function zdarzenieKlawisza(e) {
  const altgr = !!(e.getModifierState && e.getModifierState("AltGraph"));
  const skrot = !altgr && (e.ctrlKey || e.altKey || e.metaKey);
  if (e.key && e.key.length === 1 && !skrot) return { typ: "tekst", tekst: e.key };
  const k = KLAWISZE_STEROWNIKA[e.key] || (/^F([1-9]|1[0-2])$/.test(e.key || "") ? e.key.toLowerCase()
    : e.key === " " ? "space" : e.key && e.key.length === 1 ? e.key.toLowerCase() : null);
  if (!k) return null;
  return { typ: "klawisz", klawisz: k, modyfikatory: [e.ctrlKey && "ctrl", e.altKey && "alt", e.metaKey && "cmd", e.shiftKey && "shift"].filter(Boolean) };
}

// Połączenie poza Reactem: WebSocket, dekoder i rysowanie; `zmien(stan)` daje Reactowi zmiany; ping co 10 s
// podtrzymuje połączenie, gdy obraz stoi (ekran wygaszony); schowana karta panelu wysyła „stop” (serwer gasi strumień
// bez widzów), widoczna znowu „patrz”
class PolaczeniePodgladu {
  constructor(canvas, zmien) {
    Object.assign(this, { canvas, zmien, u: undefined, proby: 0, koniec: false,
      dekoder: null, kodek: null, config: null, czekaKlucza: true, jpegZajety: false, jpegNastepny: null });
    this.widocznosc = () => {
      if (document.hidden) this.wyslij({ typ: "stop" });
      else if (this.u !== undefined) this.wyslij({ typ: "patrz", u: this.u });
    };
    document.addEventListener("visibilitychange", this.widocznosc);
    this.otworz();
  }
  otworz() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = this.ws = new WebSocket(`${proto}://${location.host}${basePath()}${API_ROOT}/podglad/ws?token=${encodeURIComponent(window.__HERMES_SESSION_TOKEN__ || "")}`);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      this.proby = 0;
      this.zmien({ polaczenie: "otwarte" });
      this.zegar = setInterval(() => this.wyslij({ typ: "ping", t: Date.now() }), 10000);
      if (this.u !== undefined && !document.hidden) this.wyslij({ typ: "patrz", u: this.u });
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
    this.zmien({ klatka: false, sesja: null, ekran: null, obrazOpis: null, stan: "laczy", opis: "" });
    if (!document.hidden) this.wyslij({ typ: "patrz", u });
  }
  tekst(d) {
    if (d.typ === "witaj") this.zmien({ telefony: d.telefony || [], komputerJest: !!d.komputer, pulpitJest: !!d.pulpit, agent: d.agent, przydzialy: d.przydzialy || {} });
    else if (d.typ === "agent") this.zmien({ agent: d.agent });
    else if (d.typ === "stan") this.zmien({ u: d.u, stan: d.stan, opis: d.opis || "" });
    else if (d.typ === "ekran") this.zmien({ ekran: { wlaczony: d.wlaczony, zablokowany: d.zablokowany, szer: d.szer, wys: d.wys } });
    else if (d.typ === "sesja") this.zmien({ u: d.u, sesja: { w: d.w, h: d.h } });
    else if (d.typ === "klatka") this.zmien({ obrazOpis: { u: d.u, szer: d.w_css, wys: d.h_css, tytul: d.tytul }, ...(d.przejete != null ? { przejete: !!d.przejete } : {}) });
    else if (d.typ === "ster") this.zmien({ ...(d.przejete != null ? { przejete: !!d.przejete } : {}), bladSteru: d.ok ? null : d.blad || L("Komputer nie przyjął działania.", "The Computer refused the action.") });
  }
  binarne(buf) {
    const v = new DataView(buf), typ = v.getUint8(0), pts = Number(v.getBigInt64(9));
    const dane = new Uint8Array(buf, 17);
    if (typ === 4) return this.jpeg(dane);
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
    d.decode(new EncodedVideoChunk({ type: typ === 2 ? "key" : "delta", timestamp: pts, data: dane2 }));
    return undefined;
  }
  nowyDekoder(kodek) {
    this.zamknijDekoder();
    if (typeof VideoDecoder === "undefined") { this.zmien({ bladObrazu: true }); return; }
    this.kodek = kodek;
    const d = this.dekoder = new VideoDecoder({
      output: (f) => { this.rysuj(f, f.displayWidth, f.displayHeight); f.close(); },
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
  jpeg(dane) {
    if (this.jpegZajety) { this.jpegNastepny = dane; return; }
    this.jpegZajety = true;
    createImageBitmap(new Blob([dane], { type: "image/jpeg" })).then((b) => { this.rysuj(b, b.width, b.height); b.close(); },
      () => {}).finally(() => {
      this.jpegZajety = false;
      const n = this.jpegNastepny;
      this.jpegNastepny = null;
      if (n) this.jpeg(n);
    });
  }
  rysuj(obraz, w, h) {
    const c = this.canvas;
    if (!c || this.koniec) return;
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; this.zmien({ obraz: { w, h } }); }
    c.getContext("2d").drawImage(obraz, 0, 0);
    if (!this.maKlatke) { this.maKlatke = true; this.zmien({ klatka: true }); }
  }
  zamknij() {
    this.koniec = true;
    clearTimeout(this.ponow);
    clearInterval(this.zegar);
    document.removeEventListener("visibilitychange", this.widocznosc);
    this.zamknijDekoder();
    try { this.ws.close(); } catch (_) { /* już zamknięte */ }
  }
}

const SZEROKI_PODGLAD = "(min-width: 900px)";
const SZER_KLUCZ = "jarvo.podglad.szer";
const szerPodgladu = (w) => Math.round(Math.max(320, Math.min(w, window.innerWidth * 0.7)));

function PodgladOkno({ stan, biezacy, wid }) {
  const szeroki = useMedia(SZEROKI_PODGLAD);
  const [szer, setSzer] = useState(() => szerPodgladu(Number(localStorage.getItem(SZER_KLUCZ)) || 460));
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
    const ekran = widac === "komputer" ? s.obrazOpis : widac === "pulpit" ? ekranPulpitu(s.obrazOpis) : s.ekran;
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
  // panel po prawej obok rozmowy (rozmowa robi mu miejsce), szerokość z uchwytu na lewej krawędzi
  React.useLayoutEffect(() => {
    const k = document.querySelector("[data-jarvo-korzen]");
    if (!k || !szeroki) return undefined;
    k.classList.add("is-podglad-bok");
    return () => k.classList.remove("is-podglad-bok");
  }, [szeroki]);
  React.useLayoutEffect(() => {
    const k = document.querySelector("[data-jarvo-korzen]");
    if (k) k.style.setProperty("--j-pz-szer", `${szer}px`);
  }, [szer]);
  const uchwyt = {
    onPointerDown: (e) => { e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId); e.currentTarget.dataset.ciagnie = "1"; },
    onPointerMove: (e) => { if (e.currentTarget.dataset.ciagnie) setSzer(szerPodgladu(window.innerWidth - e.clientX - 8)); },
    onPointerUp: (e) => { delete e.currentTarget.dataset.ciagnie; localStorage.setItem(SZER_KLUCZ, String(szerPodgladu(window.innerWidth - e.clientX - 8))); },
  };
  // telefon: przeciąganie po rogach, stuknięcie = pełny ekran, zrzucenie na dół = zamknij
  const [rog, setRog] = useState("dp");     // dół prawo; klasy rogów: gl, gp, dl, dp (25.11: „pd” bez klasy = okno pod ekranem)
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
  const urzadzenia = [...(s.telefony || []).map((t) => t.id), ...(s.komputerJest ? ["komputer"] : []), ...(s.pulpitJest ? ["pulpit"] : [])];
  const nazwa = nazwaUrzadzenia(widac);
  const napis = napisPodgladu({ ...s, u: widac }, nazwa, koniecS);
  const naZywo = s.klatka && s.stan === "dziala" && !(s.ekran && s.ekran.wlaczony === false) && koniecS == null;
  const ruchAgenta = biezacy ? `${nazwaAgenta(biezacy.agent)}: ${czasownik(biezacy.krok)}${biezacy.krok.detail ? ` ${biezacy.krok.detail}` : ""}` : "";
  const tytulObrazu = s.obrazOpis && s.obrazOpis.u === widac && s.obrazOpis.tytul
    ? (widac === "pulpit" ? L(`pracuje: ${s.obrazOpis.tytul}`, `in use by ${s.obrazOpis.tytul}`) : s.obrazOpis.tytul) : "";
  const podpis = ruchAgenta || tytulObrazu;
  const pionowy = s.obraz ? s.obraz.h >= s.obraz.w : widac !== "komputer" && widac !== "pulpit";
  // kadr: obraz wpisany w wolne miejsce (także powiększony), ramka telefonu wokół; bez pasów pod i nad telefonem
  const ekranRef = useRef(null);
  const [pole, setPole] = useState(null);
  useEffect(() => {
    const el = ekranRef.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(([e]) => setPole({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const kadr = kadrObrazu(pole, s.obraz || (pionowy ? { w: 9, h: 19.5 } : { w: 16, h: 10 }), pionowy ? RAMKA_TELEFONU : 0);
  const nrTelefonu = (id) => (s.telefony || []).findIndex((t) => t.id === id) + 1;
  // dziennik działań: kroki przebiegów tej rozmowy, nazwa zadania (wiadomość, od której przebieg ruszył) i rozmowy
  const przebiegi = useSklep((x) => x.przebiegi);
  const tytulRozmowy = useSklep((x) => (wid && x.watki && x.watki[wid] && x.watki[wid].tytul) || "");
  const pozycje = useSklep((x) => (wid && x.os && x.os[wid] && x.os[wid].pozycje) || null);
  const dz = dziennikDzialan(Object.values(przebiegi || {}), wid, pozycje);
  const zadanie = nazwaZadania(pozycje, dz.wpis_id);
  const naglowekDz = [dz.agent && html`<b key="a">${nazwaAgenta(dz.agent)}</b>`, zadanie && html`<span key="z">${zadanie}</span>`,
    tytulRozmowy && html`<span key="r" class="j-pz-dz-r">${L("rozmowa", "chat")}: ${tytulRozmowy}</span>`].filter(Boolean);
  const dzRef = useRef(null);
  const ostatniWpis = dz.wpisy.length ? `${dz.wpisy[dz.wpisy.length - 1].ts}:${dz.wpisy[dz.wpisy.length - 1].wynik}` : "";
  useEffect(() => { const el = dzRef.current; if (el) el.scrollTop = el.scrollHeight; }, [ostatniWpis]);
  // „Przejmij” (Komputer): klik, prawy klik, kółko i klawiatura idą do karty, agent czeka do „Oddaj”
  const steruje = !!(s.przejete && widac === "komputer" && (szeroki || pelny));
  const kolko = useRef({ dx: 0, dy: 0, t: null, p: null });
  const wejscie = (z) => pol.current && pol.current.wyslij({ typ: "wejscie", z });
  const naObrazie = (e) => punktKlikniecia(canvas.current && canvas.current.getBoundingClientRect(), e.clientX, e.clientY);
  useEffect(() => { if (steruje && ekranRef.current) ekranRef.current.focus(); }, [steruje]);
  const sterowanie = !steruje ? {} : {
    tabIndex: 0,
    onClick: (e) => { const p = naObrazie(e); if (p) wejscie({ typ: "klik", x: p.x, y: p.y }); },
    onContextMenu: (e) => { e.preventDefault(); const p = naObrazie(e); if (p) wejscie({ typ: "klik", x: p.x, y: p.y, przycisk: "right" }); },
    onWheel: (e) => {
      const k = kolko.current, p = naObrazie(e);
      if (!p) return;
      k.dx += e.deltaX; k.dy += e.deltaY; k.p = p;
      if (k.t) return;
      k.t = setTimeout(() => { wejscie({ typ: "kolko", x: k.p.x, y: k.p.y, dx: Math.round(k.dx), dy: Math.round(k.dy) }); Object.assign(k, { dx: 0, dy: 0, t: null }); }, 80);
    },
    onKeyDown: (e) => { const z = zdarzenieKlawisza(e); if (z) { e.preventDefault(); wejscie(z); } },
    onPaste: (e) => { const t = e.clipboardData && e.clipboardData.getData("text"); if (t) { e.preventDefault(); wejscie({ typ: "tekst", tekst: t }); } },
  };
  const przejmij = () => pol.current && pol.current.wyslij({ typ: s.przejete ? "oddaj" : "przejmij" });
  return html`<aside class=${cx("j-pz", szeroki ? "is-bok" : "is-pip", !szeroki && `is-${rog}`, pelny && "is-pelny", koniecS != null && "is-koniec")}
      aria-label=${L("Podgląd na żywo", "Live view")} data-urzadzenie=${widac || ""}
      style=${przes ? { transform: `translate(${przes.x}px, ${przes.y}px)` } : undefined}>
    ${szeroki && html`<div class="j-pz-uchwyt" role="separator" aria-orientation="vertical" aria-label=${L("Szerokość podglądu", "Live view width")} ...${uchwyt}></div>`}
    <header class="j-pz-g">
      ${(szeroki || pelny) && urzadzenia.length > 0 ? html`<nav class="j-pz-z" aria-label=${L("Urządzenia", "Devices")}>
        ${urzadzenia.map((id) => {
          const opis = nazwaUrzadzenia(id);
          return html`<button type="button" key=${id} class="j-ma-tip" aria-pressed=${String(id === widac)} aria-label=${opis}
            onClick=${() => { setZaAgentem(false); setU(id); }}>
            <${Ikona} n=${ikonaUrzadzenia(id)} r=${16}/>${id !== "komputer" && id !== "pulpit" && html`<span class="j-pz-nr">${nrTelefonu(id) || ""}</span>`}
            ${id === agentU && biezacy && html`<span class="j-pz-tu" aria-hidden="true"></span>`}<${Podpowiedz} tekst=${opis}/></button>`;
        })}
        <span class="j-pz-kreska" aria-hidden="true"></span>
        <button type="button" class="j-ma-tip" aria-pressed=${String(zaAgentem)} aria-label=${L("Za agentem", "Follow agent")}
          onClick=${() => setZaAgentem(!zaAgentem)}><${Ikona} n="pin" r=${16}/><${Podpowiedz} tekst=${L("Za agentem: przełączam sam na urządzenie, na którym pracuje", "Follow agent: switch to the device it works on")}/></button>
      </nav>` : html`<b class="j-pz-n">${nazwa}</b>`}
      ${widac === "komputer" && s.komputerJest && (szeroki || pelny) && html`<${Przycisk} maly rodzaj=${s.przejete ? "mocny" : "cichy"} klasa="j-pz-przejmij"
        aria-pressed=${String(!!s.przejete)} onClick=${przejmij}>${s.przejete ? L("Oddaj", "Hand back") : L("Przejmij", "Take over")}</${Przycisk}>`}
      ${naZywo && html`<span class="j-pz-zywo" role="status"><span class="j-na-zywo-k" aria-hidden="true"></span>${L("NA ŻYWO", "LIVE")}</span>`}
      ${pelny && !szeroki && html`<${Przycisk} maly rodzaj="cichy" ikona="down" etykieta=${L("Mniejszy podgląd", "Smaller view")} onClick=${() => setPelny(false)}/>`}
      <${Przycisk} maly rodzaj="cichy" ikona="x" etykieta=${L("Zamknij podgląd", "Close live view")} onClick=${() => NaZywo.zamknij()}/>
    </header>
    ${(szeroki || pelny) && html`<p class=${cx("j-pz-ruch", steruje && "is-ty")} title=${podpis}>${steruje
      ? html`<b>${L("Sterujesz Ty", "You are in control")}</b> · ${s.bladSteru || L("klik, kółko i klawiatura idą do Komputera, agent czeka do „Oddaj”", "clicks, wheel and keys go to the Computer, the agent waits for Hand back")}`
      : html`<b>${nazwa}</b>${podpis && ` · ${podpis}`}`}</p>`}
    <div class=${cx("j-pz-ekran", pionowy ? "is-pion" : "is-poziom", widac === "komputer" && "is-komputer", steruje && "is-steruje")} ref=${ekranRef}
      aria-label=${steruje ? L("Ekran Komputera: klikasz i piszesz Ty", "Computer screen: you click and type") : undefined} ...${dotyk} ...${sterowanie}>
      <div class="j-pz-kadr" style=${kadr ? { width: `${kadr.w}px`, height: `${kadr.h}px` } : undefined}>
        <canvas ref=${canvas} class=${cx(!s.klatka && "is-pusty")}></canvas>
        ${kregi.map((k) => html`<span key=${k.id} class="j-pz-krag" style=${{ left: `${k.x * 100}%`, top: `${k.y * 100}%` }} aria-hidden="true"></span>`)}
      </div>
      ${napis && html`<p class="j-pz-napis" role="status">${s.polaczenie !== "otwarte" || (!s.klatka && s.stan !== "niedostepny") ? html`<${Spinner}/>` : null}${napis}</p>`}
    </div>
    ${(szeroki || pelny) && html`<section class="j-pz-dz" aria-label=${L("Dziennik działań agenta", "Agent action log")}>
      <p class="j-pz-dz-g" title=${[zadanie, tytulRozmowy].filter(Boolean).join(" · ")}>${naglowekDz.map((c, i) => [i ? " · " : "", c])}</p>
      ${dz.wpisy.length ? html`<ol ref=${dzRef}>${dz.wpisy.map((w, i) => html`<li key=${`${w.ts}:${i}`} class=${`is-${w.wynik}`}>
          <time>${godzinaSek(w.ts)}</time><span class="j-pz-dz-i">${w.urz ? html`<${Ikona} n=${ikonaUrzadzenia(w.urz)} r=${12}/>` : null}</span>
          <span class="j-pz-dz-o"><b>${czasownik(w.krok)}</b>${w.krok.detail ? ` ${w.krok.detail}` : ""}</span>
          <span class="j-pz-dz-w">${w.wynik === "blad" ? L("błąd", "error") : w.wynik === "trwa" ? L("trwa", "running") : czasKroku(w.czas_ms)}</span></li>`)}</ol>`
        : html`<p class="j-pz-dz-pusto">${L("W tej rozmowie agent jeszcze nic nie zrobił.", "No agent actions in this chat yet.")}</p>`}
    </section>`}
  </aside>`;
}

// Podagenci w tle (delegate_task) pod wiadomością agenta: „Podagenci Jarva: 2 z 3 gotowe”, lista z celem i stanem,
// klik pokazuje koniec dziennika podagenta. Odpytuje co 3 s tylko, dopóki któraś delegacja trwa (24.11: właściciel
// nie widział w panelu pracy podagentów, bo agent skończył turę, a oni pracowali dalej).
function stanPodagentow(delegacje) {
  const zad = (delegacje || []).flatMap((d) => d.zadania || []);
  const przerwane = zad.filter((z) => z.stan === "interrupted").length;
  return { gotowe: zad.filter((z) => z.koniec).length - przerwane, przerwane, razem: zad.length,
    trwa: (delegacje || []).some((d) => !d.koniec) };
}

function DziennikPodagenta({ watek, did, nr, trwa }) {
  const [linie, setLinie] = useState(null);
  useEffect(() => {
    let zyje = true, t = null;
    const pobierz = () => zadanie("GET", `/rozmowy/${encodeURIComponent(watek)}/podagenci/${did}/${nr}`)
      .then((d) => { if (zyje) setLinie(d.linie || []); }).catch(() => { if (zyje) setLinie([]); })
      .finally(() => { if (zyje && trwa) t = setTimeout(pobierz, 3000); });
    pobierz();
    return () => { zyje = false; clearTimeout(t); };
  }, [watek, did, nr, trwa]);
  return html`<pre class="j-pa-log">${linie == null ? L("Wczytuję…", "Loading…") : linie.length ? linie.join("\n") : L("Dziennik jest pusty.", "The log is empty.")}</pre>`;
}

function PodagenciLinia({ watek, pidy, agent }) {
  const [delegacje, setDelegacje] = useState(null);
  const [otwarte, setOtwarte] = useState(false);
  const [log, setLog] = useState(null);
  const klucz = (pidy || []).join(",");
  useEffect(() => {
    let zyje = true, t = null;
    const pobierz = () => zadanie("GET", `/rozmowy/${encodeURIComponent(watek)}/podagenci`)
      .then((d) => {
        if (!zyje) return;
        const moje = (d.delegacje || []).filter((x) => (pidy || []).includes(x.przebieg_id));
        setDelegacje(moje);
        if (moje.some((x) => !x.koniec)) t = setTimeout(pobierz, 3000);
      })
      .catch(() => { if (zyje) t = setTimeout(pobierz, 10000); });
    pobierz();
    return () => { zyje = false; clearTimeout(t); };
  }, [watek, klucz]);
  if (!delegacje || !delegacje.length) return null;
  const s = stanPodagentow(delegacje);
  return html`<div class=${cx("j-pa", s.trwa && "is-trwa")}>
    <button type="button" class="j-pa-g" aria-expanded=${String(otwarte)} onClick=${() => setOtwarte(!otwarte)}>
      <span class=${cx("j-na-zywo-k", !s.trwa && "is-stoi")} aria-hidden="true"></span>
      ${L(`Podagenci: ${s.gotowe} z ${s.razem} gotowe`, `Subagents: ${s.gotowe} of ${s.razem} done`)}${s.przerwane
        ? L(`, ${s.przerwane} przerwane`, `, ${s.przerwane} interrupted`) : ""}
    </button>
    ${s.trwa && html`<${PrzyciskNaZywo} urz=${{ rodzaj: "telefon", u: null }}/>`}
    ${otwarte && html`<ul class="j-pa-l">${delegacje.flatMap((d) => d.zadania.map((z) => {
      const k = `${d.id}:${z.nr}`;
      const stan = z.stan === "interrupted" ? L("przerwane", "interrupted") : z.koniec ? L("gotowe", "done") : L("pracuje", "working");
      return html`<li key=${k}><button type="button" class=${cx("j-pa-z", z.koniec ? "is-gotowe" : "is-pracuje")}
          aria-expanded=${String(log === k)} onClick=${() => setLog(log === k ? null : k)}>
          <b>${stan}</b> ${z.cel}</button>
        ${log === k && html`<${DziennikPodagenta} watek=${watek} did=${d.id} nr=${z.nr} trwa=${!z.koniec}/>`}</li>`;
    }))}</ul>`}
  </div>`;
}

Zasoby.daj({ PodgladOkno, PodagenciLinia, stanPodagentow, spsZKonfiguracji, kodekAvc, punktNaObrazie, kadrObrazu, napisPodgladu,
  dziennikDzialan, nazwaZadania, czasKroku, ekranPulpitu, punktKlikniecia, zdarzenieKlawisza });
