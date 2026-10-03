// Edytor filmów (styl CapCut): podgląd, oś czasu z miniaturami, napisy, muzyka, eksport ffmpeg na serwerze.
// Bez bibliotek: dwie warstwy (<video> albo <img>) na zmianę, płynne cięcia i przejścia między klipami (49-przejscia.js),
// napisy rysowane na kanwie tą samą funkcją w podglądzie i przy eksporcie (PNG na napis), więc plik wygląda jak podgląd.

const EditCtx = React.createContext(null);
const ED_AGENT = "jarvo-wideo";
const ED_SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4];
const ED_FORMATS = [
  ["orig", "Oryginał", "Original"], ["16:9", "16:9 · YouTube", "16:9 · YouTube"], ["9:16", "9:16 · Reels/TikTok", "9:16 · Reels/TikTok"],
  ["1:1", "1:1 · kwadrat", "1:1 · square"], ["4:5", "4:5 · post", "4:5 · post"],
];
const ED_SIZES = { "16:9": [1920, 1080], "9:16": [1080, 1920], "1:1": [1080, 1080], "4:5": [1080, 1350] };
// Strefy interfejsu w kadrze pionowym (ułamki kadru 1080×1920, przegląd 2026): góra = zakładki i nazwa konta,
// dół = opis, konto i dźwięk, boki = przyciski (serce, komentarze, udostępnij) i margines. Tylko podgląd, bez eksportu.
// TikTok 130/484/44/140 px, Shorts 180/390/60/120 px, Reels: zalecenie Meta 14% / 35% / 6%. Te same liczby: wideo_lib.STREFY_UI.
const ED_STREFY = {
  tiktok: { name: "TikTok", t: 0.068, b: 0.252, l: 0.041, r: 0.13 },
  reels: { name: "Reels", t: 0.14, b: 0.35, l: 0.06, r: 0.06 },
  shorts: { name: "Shorts", t: 0.094, b: 0.203, l: 0.056, r: 0.111 },
};
const ED_STREFY_OPIS = { top: ["góra: zakładki, nazwa konta", "top: tabs, account name"], bottom: ["dół: opis, konto, dźwięk", "bottom: caption, account, sound"],
  left: ["lewy margines", "left margin"], right: ["prawo: przyciski", "right: buttons"] };
// Prostokąty stref platformy `pf` na kanwie W×H; tylko kadr pionowy jak 9:16 (4:5 i poziomy: brak stref).
function strefyUI(W, H, pf) {
  const z = ED_STREFY[pf];
  if (!z || W / H > 0.65) return [];
  const t = z.t * H, b = H - z.b * H;
  return [{ k: "top", x0: 0, y0: 0, x1: W, y1: t }, { k: "bottom", x0: 0, y0: b, x1: W, y1: H },
    { k: "left", x0: 0, y0: t, x1: z.l * W, y1: b }, { k: "right", x0: W - z.r * W, y0: t, x1: W, y1: b }];
}
// Strefy, w które wchodzi prostokąt napisu (textBox): np. ["bottom", "right"].
const strefyKolizja = (box, W, H, pf) => strefyUI(W, H, pf)
  .filter((s) => box.x0 < s.x1 && box.x1 > s.x0 && box.y0 < s.y1 && box.y1 > s.y0).map((s) => s.k);

// Klip o innych proporcjach niż kadr: czarne pasy, rozmyte tło z tego samego ujęcia albo wypełnienie (przycięcie).
const ED_FITS = [["contain", "Pasy", "Bars"], ["blur", "Rozmyte tło", "Blurred"], ["cover", "Wypełnij", "Fill"]];
const ED_STYLES = [["shadow", "Cień", "Shadow"], ["box", "Tło", "Box"], ["outline", "Obrys", "Outline"], ["plain", "Zwykły", "Plain"]];
const ED_MIN = 0.1;
const ED_COLORS = ["#FFFFFF", "#000000", "#FFD60A", "#FF453A", "#32D74B", "#0A84FF", "#BF5AF2", "#FF9F0A"];
const ED_CAP = { x: 0.5, y: 0.84, size: 58, color: "#FFFFFF", bg: "#000000", style: "outline", bold: true, align: "center", maxw: 0.84,
  font: "'Bricolage Grotesque', system-ui, sans-serif" };
const ED_HL = "#FFE14D";   // domyślny kolor aktywnego słowa (karaoke)
// Tekst i napisy w kadrze pionowym startują nad opisem TikToka i Shorts i węższe niż kolumna przycisków
// (dwie linie mieszczą się w strefach); to samo projekt.PION u agenta i w klipy.py.
const ED_PION = { y: 0.68, maxw: 0.74 };
// polska forma liczebnika: plForma(3, ["uwaga", "uwagi", "uwag"]) → "uwagi"
const plForma = (n, [jeden, kilka, wiele]) => (n === 1 ? jeden : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? kilka : wiele);
const NAPISY = ["napis", "napisy", "napisów"];
const BLOKI = ["blok", "bloki", "bloków"];
const ED_FILLER = /^(y+|e+|ee+m*|m+|h?m+|ym+|em+|uh+m*|um+|eh+m*|ah+|yhm+|mhm+)$/;
const isFiller = (w) => { const x = String(w).toLowerCase().replace(/[^\p{L}\p{N}]/gu, ""); return !!x && ED_FILLER.test(x); };
// Słowa (czas osi) → linie napisów: nowa linia po pauzie, końcu zdania, za długim tekście albo czasie (jak edytor.py).
function groupLines(ws, maxChars = 32, maxGap = 0.6, maxDur = 3.5) {
  const out = [];
  let cur = [];
  const flush = () => {
    if (cur.length) out.push({ start: cur[0].t0, end: cur[cur.length - 1].t1, text: cur.map((w) => w.text).join(" "),
      words: cur.map((w) => [+(w.t0 - cur[0].t0).toFixed(3), +(w.t1 - cur[0].t0).toFixed(3), w.text]) });
    cur = [];
  };
  for (const w of ws) {
    if (isFiller(w.text)) continue;
    const last = cur[cur.length - 1];
    if (last && (w.t0 - last.t1 > maxGap + 1e-6 || cur.map((x) => x.text).join(" ").length + 1 + w.text.length > maxChars || w.t1 - cur[0].t0 > maxDur)) flush();
    cur.push(w);
    if (/[.!?…]$/.test(w.text)) flush();
  }
  flush();
  return out;
}
const edSleep = (ms) => new Promise((ok) => setTimeout(ok, ms));
const svgI = (body) => html`<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
const ED_ICON = {
  edit: svgI(html`<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>`),
  audio: svgI(html`<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>`),
  text: svgI(html`<path d="M4 7V4h16v3M9 20h6M12 4v16"/>`),
  captions: svgI(html`<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 15h4M13 15h4M7 11h10"/>`),
  format: svgI(html`<rect x="7" y="3" width="10" height="18" rx="1.5"/><path d="M3 8v8M21 8v8"/>`),
  close: svgI(html`<path d="M6 6l12 12M18 6 6 18"/>`),
  undo: svgI(html`<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>`),
  redo: svgI(html`<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>`),
  plus: svgI(html`<path d="M12 5v14M5 12h14"/>`),
  check: svgI(html`<path d="M5 12l5 5 9-10"/>`),
  spark: svgI(html`<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>`),
  split: svgI(html`<path d="M12 3v18M8 7l-4 5 4 5M16 7l4 5-4 5"/>`),
  trans: svgI(html`<path d="M4 5.5 12 12l-8 6.5zM20 5.5 12 12l8 6.5z"/>`),
  speed: svgI(html`<path d="M12 14l4-4"/><path d="M3.3 17a9 9 0 1 1 17.4 0"/>`),
  volume: svgI(html`<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>`),
  mute: svgI(html`<path d="M11 5 6 9H3v6h3l5 4z"/><path d="m16 9 6 6M22 9l-6 6"/>`),
  copy: svgI(html`<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>`),
  trash: svgI(html`<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>`),
  speech: svgI(html`<path d="M3 12h2M7 8v8M11 5v14M15 9v6M19 7v10M21 12h0"/>`),
  upload: svgI(html`<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>`),
  back: svgI(html`<path d="m15 18-6-6 6-6"/>`),
  camera: svgI(html`<path d="M14.5 4h-5L7.5 6.5H4.5A1.5 1.5 0 0 0 3 8v10a1.5 1.5 0 0 0 1.5 1.5h15A1.5 1.5 0 0 0 21 18V8a1.5 1.5 0 0 0-1.5-1.5h-3z"/><circle cx="12" cy="12.5" r="3.5"/>`),
  pin: svgI(html`<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>`),
  film: svgI(html`<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>`),
  image: svgI(html`<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.8"/><path d="m21 16-5.2-5.2L5.5 20"/>`),
  sliders: svgI(html`<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>`),
  alignL: svgI(html`<path d="M4 6h16M4 10h10M4 14h16M4 18h10"/>`),
  alignC: svgI(html`<path d="M4 6h16M7 10h10M4 14h16M7 18h10"/>`),
  alignR: svgI(html`<path d="M4 6h16M10 10h10M4 14h16M10 18h10"/>`),
  minus: svgI(html`<path d="M5 12h14"/>`),
  fit: svgI(html`<path d="M4 9V5h4M20 9V5h-4M4 15v4h4M20 15v4h-4"/>`),
  reset: svgI(html`<path d="M4 4v6h6"/><path d="M4.6 15a8 8 0 1 0 1.8-8.3L4 10"/>`),
  play: html`<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M8 5.6v12.8a1 1 0 0 0 1.5.86l10.2-6.4a1 1 0 0 0 0-1.72L9.5 4.74A1 1 0 0 0 8 5.6z"/></svg>`,
  pause: html`<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><rect x="6.5" y="5" width="3.6" height="14" rx="1.2"/><rect x="13.9" y="5" width="3.6" height="14" rx="1.2"/></svg>`,
};
// typografia (48-typografia.js): nazwy w panelu bloku i słowa; puste = z motywu
const TYPO_UKLAD_NAZWY = { kolumna: ["Kolumna", "Column"], schodki: ["Schodki", "Steps"], srodek: ["Środek", "Center"], skos: ["Skos", "Slant"],
  "3d": ["3D", "3D"], za: ["Za osobą", "Behind"], rozrzut: ["Rozrzut", "Scatter"] };
const TYPO_WEJSCIA_NAZWY = { ciecie: ["Cięcie", "Cut"], pop: ["Pop", "Pop"], kontur: ["Kontur", "Outline"], maska: ["Wysuw", "Reveal"],
  pisanie: ["Pisanie", "Typing"], zjazd: ["Wjazd", "Slide"] };
const TYPO_WYJSCIA_NAZWY = { ciecie: ["Cięcie", "Cut"], zanik: ["Zanik", "Fade"], smuga: ["Smuga", "Smear"] };
const TYPO_STYLE_NAZWY = { wypelnij: ["Pełny", "Fill"], kontur: ["Kontur", "Outline"], "3d": ["3D", "3D"], blask: ["Blask", "Glow"], tlo: ["Tło", "Box"], obrys: ["Obrys", "Stroke"] };
const TYPO_WAGI_NAZWY = [["Małe", "Small"], ["Zwykłe", "Normal"], ["Ważne", "Strong"], ["Uderzenie", "Hit"]];
const typoBez = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined && v !== null));
const typoNoweId = (ids, base) => { let k = 1; while (ids.has(`${base}${String.fromCharCode(97 + k)}`)) k++; return `${base}${String.fromCharCode(97 + k)}`; };
const typoTekst = (b) => b.slowa.map((w) => w.tekst).join(" ");

// czas osi jak w CapCut: 00:05.20 (minuty zawsze dwucyfrowe, setne do precyzyjnego montażu)
function edTC(s, fine = true) {
  s = Math.max(0, s || 0);
  const m = Math.floor(s / 60), r = s - m * 60;
  return `${String(m).padStart(2, "0")}:${fine ? r.toFixed(2).padStart(5, "0") : String(Math.floor(r)).padStart(2, "0")}`;
}
function useMedia(q) {
  const get = () => typeof window !== "undefined" && window.matchMedia && window.matchMedia(q).matches;
  const [m, setM] = useState(get);
  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener ? mq.addEventListener("change", on) : mq.addListener(on);
    return () => (mq.removeEventListener ? mq.removeEventListener("change", on) : mq.removeListener(on));
  }, [q]);
  return m;
}

let edSeq = 0;
const edId = (p) => `${p}${Date.now().toString(36)}${(edSeq++).toString(36)}`;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const even = (n) => { n = Math.round(n); return Math.max(2, n - (n % 2)); };
// kadr o proporcjach źródła z krótszym bokiem najwyżej 1080 px (4K z iPhone'a → 1080×1920): platformy pokazują
// najwyżej 1080p, a eksport 4K z warstwami typografii i maską nie mieści się w pamięci VPS. Ta sama reguła:
// edytor.kadr_eksportu (serwer i Wideograf); napisy i typografia skalują się z krótszym bokiem kadru.
const ED_KROTSZY = 1080;
function edKadr(w, h) {
  const k = Math.min(1, ED_KROTSZY / Math.max(1, Math.min(w, h)));
  return [even(Math.floor(w * k + 0.5)), even(Math.floor(h * k + 0.5))];
}
const clipDur = (c) => (c.out - c.in) / (c.speed || 1);
const audioDur = (m) => m.out - m.in;
function fmtT(s, fine) {
  s = Math.max(0, s || 0);
  const m = Math.floor(s / 60), r = s - m * 60;
  return fine ? `${m}:${r.toFixed(2).padStart(5, "0")}` : `${m}:${String(Math.floor(r)).padStart(2, "0")}`;
}
const fmtSek = (d) => `${L(String(+(+d).toFixed(2)).replace(".", ","), String(+(+d).toFixed(2)))} s`;
const trNazwa = (type) => { const r = ED_PRZEJSCIA.find(([k]) => k === type); return r ? L(r[1], r[2]) : type; };
function layoutClips(clips) {
  let t = 0;
  return clips.map((c) => { const s = t; t += clipDur(c); return { c, start: s, end: t }; });
}
// Oś magnetyczna (jak CapCut): po każdej zmianie klipów (usunięcie, wstawienie, przycięcie, tempo, przestawienie) napisy
// i uwagi idą za materiałem, z którego pochodzą (czas źródła klipu), a muzyka i lektor przesuwają się o wycięty albo
// wstawiony czas. Przy samym przestawieniu napis jedzie w całości z klipem, w którym leży, a audio stoi.
// Ta sama reguła w edytor.py remap_times (zmiany agenta przez projekt.py).
function remapTimes(P0, P1) {
  const L0 = layoutClips(P0.clips), L1 = layoutClips(P1.clips);
  const tot0 = L0.length ? L0[L0.length - 1].end : 0, tot1 = L1.length ? L1[L1.length - 1].end : 0;
  const ids0 = new Set(P0.clips.map((c) => c.id));
  const key = (c) => `${c.id}|${c.in}|${c.out}|${c.speed || 1}`;
  const reorder = P0.clips.length === P1.clips.length && P0.clips.map(key).sort().join() === P1.clips.map(key).sort().join();
  const map = (t) => {
    if (t >= tot0 - 1e-9) return t + tot1 - tot0;
    const i = Math.max(0, L0.findIndex((s) => t < s.end));
    const s0 = L0[i], sp0 = s0.c.speed || 1;
    const u = s0.c.in + (t - s0.start) * sp0;
    const hit = (s) => s.c.src === s0.c.src && u >= s.c.in - 1e-6 && u <= s.c.out + 1e-6;
    const same = L1.find((s) => s.c.id === s0.c.id);
    const s1 = (same && hit(same) ? same : null) || L1.find((s) => !ids0.has(s.c.id) && hit(s));
    if (s1) return s1.start + (u - s1.c.in) / (s1.c.speed || 1);
    if (same) return u < same.c.in ? same.start : same.end;            // wycięty fragment klipu: na jego krawędź
    const next = L0.slice(i + 1).map((s) => L1.find((x) => x.c.id === s.c.id)).find(Boolean);
    return next ? next.start : tot1;                                    // klip usunięty: tam, gdzie był
  };
  const r = (x) => +x.toFixed(3);
  const texts = (P1.texts || []).map((x) => {
    if (reorder) { const mid = (x.start + x.end) / 2, d = map(mid) - mid; return { ...x, start: r(x.start + d), end: r(x.end + d) }; }
    return { ...x, start: r(map(x.start)), end: r(map(x.end)) };
  }).filter((x) => x.end - x.start >= 0.05);
  const typo = typoPrzesun(P1.typo, (b) => {
    if (!reorder) return typoNaOsi(b, map);
    const mid = (b.start + b.end) / 2, d = map(mid) - mid;
    return typoNaOsi(b, (x) => x + d);
  });
  return { ...P1, texts,
    audio: reorder ? P1.audio : (P1.audio || []).map((m) => ({ ...m, start: r(map(m.start)) })),
    notes: (P1.notes || []).map((n) => ({ ...n, t: r(map(n.t)) })), ...(typo ? { typo } : {}) };
}
// Blok typografii po zmianie osi: początek, koniec i każde słowo (czas od początku bloku) przez tę samą funkcję czasu,
// więc słowo zostaje przy swoim dźwięku; blok z wyciętego fragmentu (krótszy niż 0,05 s) wypada.
function typoNaOsi(b, f) {
  const r = (x) => +x.toFixed(3);
  const s = f(b.start), e = f(b.end);
  return { ...b, start: r(s), end: r(e), slowa: (b.slowa || []).map((w) => ({ ...w,
    t: r(Math.max(0, f(b.start + (+w.t || 0)) - s)), k: r(Math.max(0, f(b.start + (+w.k || 0)) - s)) })) };
}
function typoPrzesun(typo, fn) {
  if (!typo || !Array.isArray(typo.bloki)) return typo;
  return { ...typo, bloki: typo.bloki.map(fn).filter((b) => b.end - b.start >= 0.05) };
}
const projTotal = (p) => p.clips.reduce((a, c) => a + clipDur(c), 0);

async function textPng(t, W, H, hi = -1) {
  await fontLoad(textFont(t, H, W).font, t.text);
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  drawText(c.getContext("2d"), t, W, H, hi);
  return c.toDataURL("image/png");
}

// ------------------------------------------------------------------ media: adresy blob i miniatury
const edUrls = new Map();       // src → Promise<blob url>
// Kodeki: czego przeglądarka nie odtworzy (np. H.264 w Chromium, ProRes wszędzie), to gra z kopii WebM z serwera.
const CODEC_TYPE = { h264: 'video/mp4; codecs="avc1.42E01E"', hevc: 'video/mp4; codecs="hvc1.1.6.L93.B0"', vp9: 'video/webm; codecs="vp9"',
  vp8: 'video/webm; codecs="vp8"', av1: 'video/mp4; codecs="av01.0.05M.08"' };
function canPlayVideo(m) {
  if (!m || m.kind !== "video" || !m.vcodec) return true;
  const type = CODEC_TYPE[m.vcodec];
  try { return !!type && document.createElement("video").canPlayType(type) !== ""; } catch (_) { return true; }
}
const edProxyNeed = new Set();
const edProxy = { busy: 0, onChange: null };
async function proxyUrl(src) {
  edProxy.busy++; edProxy.onChange && edProxy.onChange(edProxy.busy);
  try {
    let j = await api.editProxy(src);
    while (j.state === "running") { await edSleep(800); j = await api.editJob(j.id); }
    if (j.state !== "done") throw new Error(j.error || "proxy");
    return URL.createObjectURL(await api.proxyBlob(src));
  } finally { edProxy.busy--; edProxy.onChange && edProxy.onChange(edProxy.busy); }
}
function mediaUrl(src) {
  if (!edUrls.has(src)) {
    const p = edProxyNeed.has(src) && api.editProxy ? proxyUrl(src) : api.fileBlob(src).then((b) => URL.createObjectURL(b));
    p.catch(() => edUrls.delete(src));
    edUrls.set(src, p);
  }
  return edUrls.get(src);
}
function releaseMedia() {
  for (const p of edUrls.values()) p.then((u) => URL.revokeObjectURL(u)).catch(() => {});
  edUrls.clear();
  edProxyNeed.clear();
}
// Pasek miniatur źródła: jedna kanwa, N klatek (kolejno, jeden dekoder naraz).
const THUMB_H = 64;
let thumbQueue = Promise.resolve();
function filmstrip(src, meta) {
  const job = thumbQueue.then(async () => {
    const url = await mediaUrl(src);
    if (meta.kind === "image") return { url, n: 1, w: 0 };
    const dur = meta.duration || 1;
    const aspect = meta.w && meta.h ? meta.w / meta.h : 16 / 9;
    const tw = Math.round(THUMB_H * aspect);
    const n = clamp(Math.ceil(dur / 1.5), 6, 40);
    const v = document.createElement("video");
    v.muted = true; v.preload = "auto"; v.src = url;
    await new Promise((ok, bad) => { v.onloadeddata = ok; v.onerror = bad; setTimeout(ok, 6000); });
    const c = document.createElement("canvas");
    c.width = tw * n; c.height = THUMB_H;
    const g = c.getContext("2d");
    for (let i = 0; i < n; i++) {
      const at = Math.min(dur - 0.05, (i + 0.5) * dur / n);
      await new Promise((ok) => { const done = () => { v.removeEventListener("seeked", done); ok(); }; v.addEventListener("seeked", done); v.currentTime = at; setTimeout(done, 1500); });
      try { g.drawImage(v, i * tw, 0, tw, THUMB_H); } catch (_) { /* klatka niedostępna */ }
    }
    v.removeAttribute("src"); v.load();
    return new Promise((ok) => c.toBlob((b) => ok({ url: b ? URL.createObjectURL(b) : null, n, w: tw, dur }), "image/jpeg", 0.72));
  });
  thumbQueue = job.catch(() => {});
  return job;
}
// Fala dźwięku źródła audio (jak w CapCut): szczyty co 1/60 s na przezroczystej kanwie; klip na osi przesuwa ją
// tak jak pasek miniatur. Dekodowanie od razu w 8 kHz (mało pamięci); bardzo długie pliki zostają bez fali.
const WAVE_H = 48, WAVE_PPS = 60;
// Fala w decybelach (jak w OpenCut): wysokość = poziom szczytu w dBFS od −48 (cisza) do 0, bez wyrównania do
// najgłośniejszego miejsca, więc cichy plik wygląda cicho, a ciche fragmenty są widoczne.
const waveH = (peak) => clamp((20 * Math.log10(Math.max(peak, 1e-6)) + 48) / 48, 0, 1);
// Linia głośności na klipie: położenie 0–1 (dół = cisza, góra = +6 dB, 0 dB na 5/6 wysokości); głośność w projekcie
// zostaje liniowa (0–2), jak w eksporcie ffmpeg `volume=`.
const ED_DB = [-30, 20 * Math.log10(2)];   // góra = głośność 2 (+6 dB), maks. projektu
const volDb = (v) => (v > 0 ? 20 * Math.log10(v) : -Infinity);
const volPos = (v) => clamp((volDb(v) - ED_DB[0]) / (ED_DB[1] - ED_DB[0]), 0, 1);
function posVol(pos) {
  if (pos <= 0.02) return 0;
  const db = ED_DB[0] + pos * (ED_DB[1] - ED_DB[0]);
  return Math.abs(db) < 0.75 ? 1 : +Math.min(2, 10 ** (db / 20)).toFixed(3);   // przyciąga do 0 dB
}
const fmtDb = (v) => (v > 0 ? `${volDb(v) >= 0.05 ? "+" : ""}${volDb(v).toFixed(1)} dB`.replace("-", "−") : "−∞ dB");
async function decodeSmall(buf) {
  const AC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  for (const rate of [8000, 44100]) {
    try { return await new AC(1, 1, rate).decodeAudioData(buf.slice(0)); } catch (_) { /* inna częstotliwość */ }
  }
  return null;
}
function waveform(src, meta) {
  const job = thumbQueue.then(async () => {
    if (!meta || !(meta.duration > 0) || meta.duration > 1800 || !(window.OfflineAudioContext || window.webkitOfflineAudioContext)) return null;
    const buf = await (await fetch(await mediaUrl(src))).arrayBuffer();
    if (buf.byteLength > 150e6) return null;
    const a = await decodeSmall(buf);
    if (!a) return null;
    const n = clamp(Math.ceil(a.duration * WAVE_PPS), 1, 12000), per = Math.max(1, Math.floor(a.length / n));
    const chans = Array.from({ length: Math.min(2, a.numberOfChannels) }, (_, i) => a.getChannelData(i));
    const peaks = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      let m = 0;
      for (const ch of chans) for (let j = i * per, e = Math.min(ch.length, j + per); j < e; j++) { const v = Math.abs(ch[j]); if (v > m) m = v; }
      peaks[i] = m;
    }
    const c = document.createElement("canvas");
    c.width = n; c.height = WAVE_H;
    const g = c.getContext("2d");
    g.fillStyle = "rgba(255,255,255,0.62)";
    for (let i = 0; i < n; i++) {
      const h = Math.max(1, waveH(peaks[i]) * (WAVE_H - 4));
      g.fillRect(i, (WAVE_H - h) / 2, 1, h);
    }
    return new Promise((ok) => c.toBlob((b) => ok({ url: b ? URL.createObjectURL(b) : null, dur: a.duration }), "image/png"));
  });
  thumbQueue = job.catch(() => {});
  return job;
}

// ------------------------------------------------------------------ historia (cofnij / ponów)
function useHistory(initial) {
  const [h, setH] = useState({ past: [], present: initial, future: [] });
  const base = useRef(null);   // stan przed przeciąganiem: cały gest to jeden krok cofania
  const apply = useCallback((fn) => setH((s) => {
    const next = fn(s.present);
    if (next === s.present) return s;
    return { past: [...s.past.slice(-99), s.present], present: next, future: [] };
  }), []);
  const live = useCallback((fn) => setH((s) => {
    if (!base.current) base.current = s.present;
    return { ...s, present: fn(s.present) };
  }), []);
  // jak live, ale zawsze od stanu sprzed gestu (przeciąganie liczy całą zmianę od początku, np. przesunięcie osi)
  const liveFrom = useCallback((fn) => setH((s) => {
    if (!base.current) base.current = s.present;
    return { ...s, present: fn(base.current) };
  }), []);
  const commit = useCallback(() => setH((s) => {
    const b = base.current; base.current = null;
    if (!b || b === s.present) return s;
    return { past: [...s.past.slice(-99), b], present: s.present, future: [] };
  }), []);
  const undo = useCallback(() => setH((s) => (s.past.length ? { past: s.past.slice(0, -1), present: s.past[s.past.length - 1], future: [s.present, ...s.future] } : s)), []);
  const redo = useCallback(() => setH((s) => (s.future.length ? { past: [...s.past, s.present], present: s.future[0], future: s.future.slice(1) } : s)), []);
  const reset = useCallback((p) => setH({ past: [], present: p, future: [] }), []);
  return { p: h.present, apply, live, liveFrom, commit, undo, redo, reset, canUndo: h.past.length > 0, canRedo: h.future.length > 0 };
}

// ------------------------------------------------------------------ odtwarzacz: dwie warstwy na zmianę
// Warstwa = rozmyte tło klipu (fit "blur"), <video> i <img>. Klip gra w jednej warstwie, następny czeka w drugiej
// (cięcie bez mrugnięcia). Na cięciu z przejściem grają obie: A dalej za cięciem, B od chwili przed cięciem, a wygląd
// warstw (krycie, przesunięcie, maska, rozmycie) liczy przejscieStyl, tak jak xfade w eksporcie. W oknie przejścia
// czas płynie z zegara, poza nim z bieżącego wideo (tempo, zacięcia dekodera).
function usePlayer(proj, meta, onTick) {
  const vids = [useRef(null), useRef(null)];
  const imgs = [useRef(null), useRef(null)];
  const layers = [useRef(null), useRef(null)];
  const blurs = [useRef(null), useRef(null)];
  const pixRef = useRef(null);
  const audios = useRef(new Map());
  // seg[k] = odcinek osi w warstwie k, tok[k] = numer wstawienia (późne wczytanie starego klipu nie nadpisze nowego)
  // hold: po przejściu czas nie cofa się, gdy wideo B ruszyło z opóźnieniem (play() ~0,1 s), tylko czeka na nie
  const st = useRef({ t: 0, playing: false, slot: 0, idx: -1, url: [null, null], seg: [null, null], tok: [0, 0], tr: null,
    stopAt: null, last: 0, raf: 0, hold: null });
  const projRef = useRef(proj);
  projRef.current = proj;
  const [playing, setPlaying] = useState(false);

  const segs = () => layoutClips(projRef.current.clips);
  const trs = () => przejsciaOsi(projRef.current.clips, (projRef.current.canvas || {}).fps);
  const total = () => projTotal(projRef.current);
  const findSeg = (t) => {
    const L = segs();
    for (let i = 0; i < L.length; i++) if (t < L[i].end - 1e-6) return [i, L[i]];
    return L.length ? [L.length - 1, L[L.length - 1]] : [-1, null];
  };
  const lokal = (s, t) => s.c.in + (t - s.start) * (s.c.speed || 1);
  const slotOf = (s) => [0, 1].find((k) => st.current.seg[k] && st.current.seg[k].c.id === s.c.id) ?? -1;
  const elOf = (k) => (st.current.seg[k] && st.current.seg[k].c.kind === "image" ? imgs[k].current : vids[k].current);
  // kadr jak w eksporcie (edytor.py cover_filter): object-position = punkt skupienia, scale(zoom) wokół niego
  function applyFit(el, c) {
    const cover = c.fit === "cover";
    const fx = cover ? clamp(c.fx ?? 0.5, 0, 1) : 0.5, fy = cover ? clamp(c.fy ?? 0.5, 0, 1) : 0.5;
    const z = cover ? clamp(c.zoom ?? 1, 1, 3) : 1;
    el.style.objectFit = cover ? "cover" : "contain";
    el.style.objectPosition = `${fx * 100}% ${fy * 100}%`;
    el.style.transformOrigin = `${fx * 100}% ${fy * 100}%`;
    el.style.transform = z !== 1 ? `scale(${z})` : "";
  }
  // odcinek s w warstwie k w chwili osi t (także poza klipem: zapas przed nim i za nim w oknie przejścia)
  async function place(k, s, t, play) {
    const S = st.current, v = vids[k].current, im = imgs[k].current;
    if (!v || !im || !s) return;
    const tok = ++S.tok[k];
    S.seg[k] = s;
    const url = await mediaUrl(s.c.src);
    if (S.tok[k] !== tok) return;
    if (s.c.kind === "image") {
      if (im.getAttribute("src") !== url) im.src = url;
      applyFit(im, s.c);
      im.classList.add("is-on"); v.classList.remove("is-on");
      v.pause();
      return;
    }
    if (S.url[k] !== url) { v.src = url; S.url[k] = url; }
    if (v.readyState < 1) await new Promise((ok) => { v.addEventListener("loadedmetadata", ok, { once: true }); setTimeout(ok, 4000); });
    if (S.tok[k] !== tok) return;
    const u = lokal(s, t), dur = Number.isFinite(v.duration) ? v.duration : Infinity;
    const loc = clamp(u, 0, Math.max(0, dur - 0.001));
    if (Math.abs(v.currentTime - loc) > 0.02) v.currentTime = loc;
    v.playbackRate = s.c.speed || 1;
    v.muted = !!s.c.muted;
    applyFit(v, s.c);
    v.classList.add("is-on"); im.classList.remove("is-on");
    if (play && u >= 0 && u < dur) await v.play().catch(() => {});
    else v.pause();
  }
  // wygląd obu warstw w chwili t: jedna widoczna, a w oknie przejścia obie według przejscieStyl
  function render(t) {
    const S = st.current, P = projRef.current, box = layers[0].current && layers[0].current.parentElement;
    if (!box || !P) return;
    const L = segs(), W = przejscieW(L, trs(), t);
    const ka = W ? (S.seg[1] && S.seg[1].c.id === L[W.i].c.id ? 1 : 0) : S.slot, kb = 1 - ka;
    const styl = W ? przejscieStyl(W.type, W.q) : null;
    const px = (box.clientWidth / Math.max(1, P.canvas.w)) * Math.max(2, Math.round(Math.min(P.canvas.w, P.canvas.h) / ED_PRZ_ROZMYCIE));
    for (const k of [0, 1]) {
      const el = layers[k].current;
      if (!el) continue;
      const on = styl ? true : k === S.slot;
      const css = styl ? przejscieCss(k === ka ? styl.a : styl.b, px) : {};
      el.style.visibility = on ? "visible" : "hidden";
      el.style.zIndex = k === (styl ? kb : S.slot) ? "2" : "1";
      el.style.opacity = css.opacity || "";
      el.style.transform = css.transform || "";
      el.style.clipPath = css.clipPath || "";
      el.style.maskImage = css.maskImage || "";
      el.style.webkitMaskImage = css.webkitMaskImage || "";
      el.style.filter = css.filter || "";
      const s = S.seg[k], v = vids[k].current;     // dźwięk klipów przenika się jak acrossfade w eksporcie
      if (s && v && s.c.kind !== "image") v.volume = clamp(s.c.volume ?? 1, 0, 1) * (!styl ? 1 : k === ka ? 1 - W.q : W.q);
    }
    box.style.background = styl ? styl.tlo : "";
    const pc = pixRef.current;
    if (pc) {
      pc.classList.toggle("is-on", !!(styl && styl.piksel));
      if (styl && styl.piksel) piksele(pc, styl.piksel, ka, kb, W.q);
    }
  }
  // „Piksele”: obie warstwy na małej kanwie (bok piksela z przejscieStyl), CSS powiększa ją bez wygładzania
  const pixTmp = useRef(null);
  function piksele(pc, bok, ka, kb, q) {
    const P = projRef.current, W = P.canvas.w, H = P.canvas.h, b = Math.max(1, bok * Math.min(W, H));
    const w = Math.max(2, Math.round(W / b)), h = Math.max(2, Math.round(H / b));
    if (pc.width !== w || pc.height !== h) { pc.width = w; pc.height = h; }
    const tmp = pixTmp.current || (pixTmp.current = document.createElement("canvas"));
    if (tmp.width !== w || tmp.height !== h) { tmp.width = w; tmp.height = h; }
    const g = pc.getContext("2d"), o = tmp.getContext("2d");
    g.globalAlpha = 1;
    for (const [k, al] of [[ka, 1], [kb, q]]) {
      const s = st.current.seg[k], el = elOf(k);
      o.fillStyle = "#000"; o.fillRect(0, 0, w, h);
      const vw = el && (el.videoWidth || el.naturalWidth), vh = el && (el.videoHeight || el.naturalHeight);
      if (s && vw && vh) {
        if (s.c.fit === "blur" && blurs[k].current && blurs[k].current.width) o.drawImage(blurs[k].current, -w * 0.04, -h * 0.04, w * 1.08, h * 1.08);
        const r = fitBox(vw, vh, w, h, s.c);
        try { o.drawImage(el, r.x, r.y, r.w, r.h); } catch (_) { /* klatka jeszcze niegotowa */ }
      }
      g.globalAlpha = al;
      g.drawImage(tmp, 0, 0);
    }
    g.globalAlpha = 1;
  }
  function syncAudio(t, play) {
    const items = projRef.current.audio || [];
    for (const m of items) {
      const a = audios.current.get(m.id);
      if (!a) continue;
      const local = m.in + (t - m.start);
      const inside = t >= m.start && local < m.out;
      a.volume = clamp(m.volume ?? 1, 0, 1);
      if (inside && play) {
        if (Math.abs(a.currentTime - local) > 0.25) a.currentTime = local;
        if (a.paused) a.play().catch(() => {});
      } else {
        if (!a.paused) a.pause();
        if (inside && Math.abs(a.currentTime - local) > 0.05) a.currentTime = local;
      }
    }
  }
  // następny klip czeka w drugiej warstwie od chwili, w której się pokaże (przy przejściu: przed cięciem)
  function preloadNext(i) {
    const L = segs(), n = L[i + 1], tr = trs()[i];
    if (n) place(1 - st.current.slot, n, tr ? L[i].end - tr.d / 2 : n.start, false);
  }
  // stan warstw w chwili t (przewinięcie, start, zmiana projektu)
  async function sync(t, play) {
    const S = st.current, L = segs(), W = przejscieW(L, trs(), t);
    if (W) {
      const A = L[W.i], B = L[W.i + 1];
      let ka = slotOf(A);
      if (ka < 0) ka = slotOf(B) >= 0 ? 1 - slotOf(B) : S.slot;
      S.tr = W.i;
      S.idx = t < W.T ? W.i : W.i + 1;
      S.slot = t < W.T ? ka : 1 - ka;
      render(t);
      await Promise.all([place(ka, A, t, play), place(1 - ka, B, t, play)]);
    } else {
      const [i, s] = findSeg(t);
      if (!s) return;
      const k = slotOf(s) >= 0 ? slotOf(s) : S.slot;
      S.tr = null; S.idx = i; S.slot = k;
      render(t);
      await place(k, s, t, play);
      const o = vids[1 - k].current;
      if (o) o.pause();
      preloadNext(i);
    }
    render(t);
  }
  function frame(now) {
    const S = st.current;
    if (!S.playing) return;
    const dt = Math.min(0.1, (now - S.last) / 1000);
    S.last = now;
    const L = segs(), T = trs(), tot = total();
    const s = L[S.idx];
    if (!s) { stop(); return; }
    const v = vids[S.slot].current;
    if (S.tr !== null || s.c.kind === "image" || !v) S.t += dt;
    else {
      S.t = s.start + (v.currentTime - s.c.in) / (s.c.speed || 1);
      if (v.ended) S.t = Math.max(S.t, s.end);
      if (S.hold !== null) { if (S.t < S.hold) S.t = S.hold; else S.hold = null; }
    }
    if (S.stopAt !== null && S.t >= S.stopAt) { S.t = S.stopAt; stop(); onTick(S.t, true); return; }
    if (S.t >= tot - 0.005) { S.t = tot; stop(); onTick(S.t, true); return; }
    const W = przejscieW(L, T, S.t);
    if (W) {
      const A = L[W.i], B = L[W.i + 1];
      let ka = slotOf(A);
      if (ka < 0) ka = S.slot;
      const kb = 1 - ka;
      if (S.tr !== W.i) {                         // wejście w przejście: B rusza w drugiej warstwie
        S.tr = W.i;
        place(kb, B, S.t, true);
      }
      const vb = vids[kb].current;                // B bez materiału przed sobą stoi na pierwszej klatce, aż dojdzie czas
      if (B.c.kind !== "image" && vb && vb.paused && st.current.seg[kb] === B && lokal(B, S.t) >= 0) vb.play().catch(() => {});
      if (S.t >= W.T && S.idx === W.i) { S.idx = W.i + 1; S.slot = kb; }
    } else if (S.tr !== null) {                   // koniec przejścia: dalej gra B
      S.tr = null;
      S.hold = S.t;
      const k = slotOf(L[S.idx]);
      if (k >= 0) S.slot = k;
      const o = vids[1 - S.slot].current;
      if (o) o.pause();
      preloadNext(S.idx);
    } else if (S.t >= s.end - 0.01 && S.idx + 1 < L.length) {   // zwykłe cięcie: następny klip czeka w drugiej warstwie
      S.t = s.end;
      const i = S.idx + 1, n = L[i];
      S.idx = i;
      const k = slotOf(n) >= 0 ? slotOf(n) : S.slot;
      S.slot = k;
      place(k, n, n.start, true).then(() => { const o = vids[1 - k].current; if (o && st.current.tr === null) o.pause(); preloadNext(i); });
    }
    render(S.t);
    syncAudio(S.t, true);
    onTick(S.t, false);
    S.raf = requestAnimationFrame(frame);
  }
  function stop() {
    const S = st.current;
    S.playing = false;
    S.stopAt = null;
    cancelAnimationFrame(S.raf);
    vids.forEach((r) => r.current && r.current.pause());
    syncAudio(S.t, false);
    setPlaying(false);
  }
  async function seek(t) {
    const S = st.current;
    S.t = clamp(t, 0, Math.max(0, total() - 0.001));
    S.hold = null;
    onTick(S.t, false);            // kursor i czas od razu, klatka dociąga się w tle
    await sync(S.t, S.playing);
    syncAudio(S.t, S.playing);
    onTick(S.t, true);
  }
  async function play() {
    const S = st.current;
    if (S.playing || !projRef.current.clips.length) return;
    if (S.t >= total() - 0.02) S.t = 0;
    S.playing = true;
    setPlaying(true);
    await seek(S.t);
    S.last = performance.now();
    S.raf = requestAnimationFrame(frame);
  }
  // odcinek a–b (np. podgląd wybranego przejścia) i pauza na końcu
  async function playRange(a, b) {
    stop();
    st.current.t = clamp(a, 0, Math.max(0, total() - 0.001));
    await play();
    st.current.stopAt = Math.min(b, total());
  }
  const toggle = () => (st.current.playing ? stop() : play());
  // nowe elementy <video> (np. przełączenie układu telefon/komputer): zapomnij stare źródła
  const remount = () => { const S = st.current; S.url = [null, null]; S.seg = [null, null]; S.tr = null; S.idx = -1; };
  useEffect(() => () => { cancelAnimationFrame(st.current.raf); }, []);
  return { vids, imgs, layers, blurs, pixRef, audios, st, playing, play, stop, toggle, seek, playRange, remount, elOf, render };
}

// ------------------------------------------------------------------ edytor
function initialProject(file) {
  const [w, h] = edKadr(even(file.w || 1920), even(file.h || 1080));
  return {
    version: 1, format: "orig", canvas: { w, h, fps: [24, 25, 30, 50, 60].reduce((a, f) => (Math.abs(f - (file.fps || 30)) < Math.abs(a - (file.fps || 30)) ? f : a), 30) },
    clips: [{ id: edId("c"), src: file.path, kind: "video", in: 0, out: file.duration || 5, speed: 1, volume: 1, muted: false, fit: "contain" }],
    texts: [], audio: [],
  };
}

// Dashboard trzyma wtyczkę w warstwie z własnym z-index (np. 2), a menu boczne ma wyższy (50): okno „fixed” na cały
// ekran (edytor, animacja) zostałoby pod menu. Na czas okna podnosimy przodków z z-index nad resztę strony, po
// zamknięciu przywracamy.
function useOverDashboard() {
  useEffect(() => {
    const raised = [];
    let el = document.querySelector(".thq-root");
    while (el && el !== document.body) {
      const cs = getComputedStyle(el);
      if (cs.zIndex !== "auto" && cs.position !== "static") {
        raised.push([el, el.style.zIndex]);
        el.style.zIndex = "2147483000";
      }
      el = el.parentElement;
    }
    return () => raised.forEach(([node, prev]) => { node.style.zIndex = prev; });
  }, []);
}

// Miniatura przejścia w panelu: kafelki A i B animowane tym samym przejscieStyl co podgląd. Jeden zegar rAF
// dla wszystkich miniatur, style ustawiane wprost (bez renderu); zegar staje, gdy panel się zamknie.
const trMini = new Set();
let trMiniRaf = 0;
function trMiniTick(now) {
  const x = (now % 1800) / 1800, q = Math.min(1, Math.max(0, (x - 0.2) / 0.6));
  for (const f of trMini) f(q);
  trMiniRaf = trMini.size ? requestAnimationFrame(trMiniTick) : 0;
}
function TrMini({ type }) {
  const box = useRef(null), a = useRef(null), b = useRef(null);
  useEffect(() => {
    const f = (q) => {
      const s = przejscieStyl(type, q);
      for (const [el, o] of [[a.current, s.a], [b.current, s.b]]) {
        if (!el) continue;
        const css = przejscieCss(o, 6);
        el.style.opacity = css.opacity; el.style.transform = css.transform; el.style.clipPath = css.clipPath;
        el.style.maskImage = css.maskImage; el.style.webkitMaskImage = css.webkitMaskImage;
        el.style.filter = s.piksel ? `blur(${(s.piksel * 30).toFixed(1)}px)` : css.filter;   // piksele w miniaturze: zmiękczenie
      }
      if (box.current) box.current.style.background = s.tlo;
    };
    trMini.add(f);
    if (!trMiniRaf) trMiniRaf = requestAnimationFrame(trMiniTick);
    return () => { trMini.delete(f); };
  }, [type]);
  return html`<span class="thq-ed-trmini" ref=${box} aria-hidden="true"><i ref=${a} class="is-a">A</i><i ref=${b} class="is-b">B</i></span>`;
}

function VideoEditor({ path, onClose }) {
  const openFile = React.useContext(FileCtx);
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState(null);
  const [meta, setMeta] = useState({});
  const [strips, setStrips] = useState({});
  const [waves, setWaves] = useState({});        // fala dźwięku każdego pliku audio na osi
  const H = useHistory(null);
  const p = H.p;
  const [sel, setSel] = useState(null);        // {type:"clip"|"text"|"audio", id}
  const [t, setT] = useState(0);
  const [pps, setPps] = useState(60);          // pikseli na sekundę osi
  const [saved, setSaved] = useState("");
  const [job, setJob] = useState(null);
  const [ask, setAsk] = useState(null);
  const [shot, setShot] = useState(null);      // zaznaczanie kadru: {a, b} w ułamkach podglądu (null = wyłączone)
  const [noteHi, setNoteHi] = useState(null);  // uwaga podświetlona na osi i w panelu prośby
  // strefy platformy na podglądzie kadru pionowego: wybór zapamiętany w tej przeglądarce, nie w projekcie
  const [strefa, setStrefa] = useState(() => { try { return localStorage.getItem("thq-ed-strefy") || "tiktok"; } catch (_) { return "tiktok"; } });
  const pickStrefa = (v) => { setStrefa(v); try { localStorage.setItem("thq-ed-strefy", v); } catch (_) { /* bez pamięci przeglądarki */ } };
  const shotUrls = useRef(new Map());          // ścieżka kadru → obraz (data URL) z tej sesji edytora
  const [side, setSide] = useState("media");
  const [codecErr, setCodecErr] = useState(false);
  const mobile = useMedia("(max-width: 860px)");
  const [tool, setTool] = useState(null);      // telefon: otwarty panel narzędzia
  const [capJob, setCapJob] = useState(null);
  const [tlW, setTlW] = useState(800);
  const mobileRef = useRef(mobile);
  mobileRef.current = mobile;
  const autoScroll = useRef(-1);
  const scrollRaf = useRef(0);
  const pinch = useRef(null);
  const wrapRef = useRef(null);
  const [box, setBox] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || !window.ResizeObserver) return undefined;
    const ro = new ResizeObserver(([e]) => setBox({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [!!info, mobile]);
  const stageRef = useRef(null), overlayRef = useRef(null), tlRef = useRef(null), headRef = useRef(null), timeRef = useRef(null);
  const tRef = useRef(0);
  const me = useRef({});

  // okno na wierzchu stosu: Escape w podglądzie pod spodem nas nie zamyka
  useEffect(() => { MODAL_STACK.push(me.current); return () => { const i = MODAL_STACK.indexOf(me.current); if (i >= 0) MODAL_STACK.splice(i, 1); }; }, []);
  useOverDashboard();
  useEffect(() => () => releaseMedia(), []);

  const addMeta = useCallback((list) => {
    for (const x of list) if (x && !canPlayVideo(x)) edProxyNeed.add(x.path);   // zanim ktokolwiek poprosi o adres
    setMeta((m) => { const n = { ...m }; for (const x of list) n[x.path] = x; return n; });
  }, []);
  const [proxying, setProxying] = useState(0);
  useEffect(() => { edProxy.onChange = setProxying; return () => { edProxy.onChange = null; }; }, []);
  // mowa: analiza per źródło (czas źródła), pauzy i wtrącenia jako znaczniki na osi
  const [speech, setSpeech] = useState({});
  const [speechJob, setSpeechJob] = useState(null);
  const [minPause, setMinPause] = useState(0.6);
  const [cutNote, setCutNote] = useState("");
  const [ignored, setIgnored] = useState(() => new Set());
  const speechTried = useRef(new Set());
  useEffect(() => {
    let alive = true;
    if (!api.editInfo) { setErr(L("Edytor działa w zainstalowanym Jarvo.", "The editor runs in an installed Jarvo.")); return undefined; }
    api.editInfo(path).then(async (d) => {
      if (!alive) return;
      const proj = await prepare(d);
      baseRef.current = d.project_mtime || 0;
      H.reset(proj);
      setInfo(d);
    }).catch((e) => alive && setErr(e.message || String(e)));
    return () => { alive = false; };
  }, [path]);

  // projekt z serwera → gotowy do edycji (id elementów, brakujące pliki odrzucone)
  async function prepare(d) {
      addMeta([d.file, ...d.media]);
      let proj = d.project && Array.isArray(d.project.clips) && d.project.clips.length ? d.project : initialProject(d.file);
      // pliki z zapisanego projektu, których nie ma w katalogu: dopytujemy, brakujące odrzucamy
      const known = new Set([d.file.path, ...d.media.map((x) => x.path)]);
      const need = [...new Set([...proj.clips, ...(proj.audio || [])].map((c) => c.src).filter((s) => !known.has(s)))];
      const extra = await Promise.all(need.map((s) => api.editMedia(s).catch(() => null)));
      addMeta(extra.filter(Boolean));
      const ok = new Set([...known, ...extra.filter(Boolean).map((x) => x.path)]);
      proj = { ...proj, texts: (proj.texts || []).map((x) => ({ ...x, id: x.id || edId("t") })),
        notes: (proj.notes || []).filter((n) => n && Number.isFinite(+n.t)).map((n) => ({ ...n, t: +n.t, id: n.id || edId("n") })),
        clips: proj.clips.filter((c) => ok.has(c.src)).map((c) => ({ ...c, id: c.id || edId("c") })),
        audio: (proj.audio || []).filter((c) => ok.has(c.src)).map((c) => ({ ...c, id: c.id || edId("a") })) };
      if (!proj.clips.length) proj = initialProject(d.file);
      const [cw, ch] = edKadr(even(+(proj.canvas || {}).w || 1920), even(+(proj.canvas || {}).h || 1080));   // stary projekt 4K → 1080p
      return { ...proj, canvas: { ...(proj.canvas || {}), w: cw, h: ch } };
  }
  // zmiany z zewnątrz (Wideograf przez projekt.py): wczytujemy jako zwykły krok, więc ↶ cofa zmiany agenta
  const baseRef = useRef(0);
  const dirtyRef = useRef(false);
  const [conflict, setConflict] = useState(null);
  const [toast, setToast] = useState("");
  async function reloadProject(who) {
    const d = await api.editInfo(path);
    const proj = await prepare(d);
    baseRef.current = d.project_mtime || 0;
    dirtyRef.current = false;
    speechTried.current = new Set();
    H.apply(() => proj);
    setInfo(d);
    setConflict(null);
    setToast(who === "jarvo-wideo" ? L("Wideograf zmienił projekt: wczytano jego wersję (↶ cofa).", "The video agent changed the project: loaded (undo reverts).")
      : L("Wczytano nowszą wersję projektu.", "Loaded the newer project version."));
    setTimeout(() => setToast(""), 6000);
  }
  useEffect(() => {
    if (!info || !api.editStamp) return undefined;
    let alive = true;
    const id = setInterval(async () => {
      if (conflict || document.hidden) return;              // ukryta karta: zmiany agenta wczytamy po powrocie
      try {
        const st = await api.editStamp(path);
        if (!alive || !(st.mtime > baseRef.current + 1e-3)) return;
        if (dirtyRef.current) setConflict({ kto: st.kto, mtime: st.mtime });
        else await reloadProject(st.kto);
      } catch (_) { /* sieć: następnym razem */ }
    }, 3000);
    return () => { alive = false; clearInterval(id); };
  }, [info, conflict]);

  // miniatury dla każdego źródła na osi
  useEffect(() => {
    if (!p) return;
    for (const c of p.clips) {
      if (strips[c.src] !== undefined || !meta[c.src]) continue;
      setStrips((s) => ({ ...s, [c.src]: null }));
      filmstrip(c.src, meta[c.src]).then((r) => setStrips((s) => ({ ...s, [c.src]: r }))).catch(() => {});
    }
  }, [p && p.clips, meta]);
  useEffect(() => {
    if (!p) return;
    for (const m of p.audio) {
      if (waves[m.src] !== undefined || !meta[m.src]) continue;
      setWaves((w) => ({ ...w, [m.src]: null }));
      waveform(m.src, meta[m.src]).then((r) => setWaves((w) => ({ ...w, [m.src]: r }))).catch(() => {});
    }
  }, [p && p.audio, meta]);

  const onTick = useCallback((time, commitState) => {
    tRef.current = time;
    if (headRef.current) headRef.current.style.transform = `translateX(${time * ppsRef.current}px)`;
    const tl = tlRef.current;
    if (mobileRef.current && tl) {
      // telefon: oś przesuwa się pod wskaźnikiem na środku (jak w CapCut)
      const x = time * ppsRef.current;
      if (Math.abs(tl.scrollLeft - x) > 1) { autoScroll.current = x; tl.scrollLeft = x; autoScroll.current = tl.scrollLeft; }
    }
    if (timeRef.current) timeRef.current.textContent = edTC(time);
    drawOverlay();
    drawBlur();
    if (commitState) setT(time);
  }, []);
  const ppsRef = useRef(pps);
  ppsRef.current = pps;
  const player = usePlayer(p || { clips: [], texts: [], audio: [] }, meta, onTick);
  // element (wideo albo obraz) z klatką odcinka seg: jego warstwa, a gdy jeszcze się nie wczytał, bieżąca
  const elSeg = (seg) => {
    const S = player.st.current, k = [0, 1].find((j) => S.seg[j] && S.seg[j].c.id === seg.c.id);
    return player.elOf(k ?? S.slot);
  };
  const projRef = useRef(p);
  projRef.current = p;
  const selRef = useRef(sel);
  selRef.current = sel;
  const strefaRef = useRef(strefa);
  strefaRef.current = strefa;

  const typoFontRef = useRef("");
  // sylwetka osoby (maska.py Wideografa): napis z warstwy „tyl” chowa się za osobą także w podglądzie
  const maskaRef = useRef({ info: null, img: new Map(), oc: null });
  const [maskaV, setMaskaV] = useState(0);     // nowy indeks sylwetek: panel bloku wie, czy osoba zasłoni napis
  // bloki za osobą (czas): indeks pobieramy po ich zmianie i po wczytaniu projektu (np. Wideograf policzył sylwetki),
  // a nie przy każdym ruchu suwaka
  const typoTylKey = p ? typoBloki(p).filter((b) => b.warstwa === "tyl").map((b) => `${b.id}@${b.start}-${b.end}`).join() : "";
  useEffect(() => {
    if (!typoTylKey || !api.editMaska) { maskaRef.current.info = null; return undefined; }
    let live = true;
    api.editMaska(path).then((d) => {
      if (!live) return;
      const m = maskaRef.current;
      if (!d || !d.klucz || !m.info || m.info.klucz !== d.klucz) m.img.clear();
      m.info = d && d.klucz ? { ...d, set: new Set(d.klatki) } : null;
      setMaskaV((v) => v + 1);
      drawOverlay();
    }).catch(() => {});
    return () => { live = false; };
  }, [typoTylKey, info, path]);
  // czy sylwetki pokrywają blok za osobą (aktualny klucz osi i ≥ 90% jego klatek)
  function maskaBloku(b) {
    const inf = maskaRef.current.info, P = projRef.current;
    if (!inf || !P || inf.klucz !== maskaKlucz(P)) return false;
    const F = +inf.fps || P.canvas.fps || 30, a = Math.floor(b.start * F), z = Math.max(a + 1, Math.round(b.end * F));
    let n = 0;
    for (let k = a; k < z; k++) if (inf.set.has(k)) n++;
    return n >= 0.9 * (z - a);
  }
  const WCZYTUJE = "…";
  function maskaKlatka(k) {          // ImageBitmap sylwetki klatki k albo null (wczytuje w tle i rysuje ponownie)
    const m = maskaRef.current, inf = m.info;
    if (!inf || !inf.set.has(k)) return null;
    const hit = m.img.get(k);
    if (hit && hit !== WCZYTUJE) return hit;
    if (!hit) {
      if (m.img.size > 600) m.img.clear();
      m.img.set(k, WCZYTUJE);
      api.fileBlob(`${inf.dir}/k${String(k).padStart(6, "0")}.png`).then((b) => createImageBitmap(b))
        .then((bm) => { m.img.set(k, bm); drawOverlay(); }).catch(() => m.img.delete(k));
    }
    return null;
  }
  // osoba z bieżącej klatki (kadr jak w podglądzie: fitBox) przycięta sylwetką, nad warstwą „tyl”;
  // w strefach platformy przyciemniona jak reszta wideo pod nimi (zs, cien: te same co w drawOverlay)
  function osobaNaWierzch(g, P, w, h, now, zs, cien) {
    const m = maskaRef.current, inf = m.info;
    if (!inf || inf.klucz !== maskaKlucz(P) || !typoAktywne(P, now).some((b) => b.warstwa === "tyl")) return;
    const k = Math.floor(now * (+inf.fps || P.canvas.fps || 30) + 1e-6);
    for (let j = 1; j <= 12; j++) maskaKlatka(k + j);     // kolejne klatki z wyprzedzeniem (odtwarzanie)
    const bm = maskaKlatka(k);
    if (!bm) return;
    const L2 = layoutClips(P.clips);
    const seg = L2.find((x) => now < x.end - 1e-6) || L2[L2.length - 1];
    const el = seg && elSeg(seg);
    const vw = el && (el.videoWidth || el.naturalWidth), vh = el && (el.videoHeight || el.naturalHeight);
    if (!vw || !vh) return;
    const oc = m.oc || (m.oc = document.createElement("canvas"));
    if (oc.width !== w || oc.height !== h) { oc.width = w; oc.height = h; }
    const o = oc.getContext("2d");
    o.globalCompositeOperation = "source-over";
    o.clearRect(0, 0, w, h);
    const r = fitBox(vw, vh, w, h, seg.c);
    try { o.drawImage(el, r.x, r.y, r.w, r.h); } catch (_) { return; }
    o.globalCompositeOperation = "destination-in";
    o.drawImage(bm, 0, 0, w, h);
    if (zs.length) {
      o.globalCompositeOperation = "source-atop"; o.fillStyle = cien;
      for (const z of zs) o.fillRect(z.x0, z.y0, z.x1 - z.x0, z.y1 - z.y0);
    }
    o.globalCompositeOperation = "source-over";
    g.drawImage(oc, 0, 0);
  }
  function drawOverlay() {
    const c = overlayRef.current, P = projRef.current;
    if (!c || !P) return;
    const { w, h } = P.canvas;
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    const g = c.getContext("2d");
    g.clearRect(0, 0, w, h);
    const now = tRef.current;
    const pf = strefaRef.current, zs = strefyUI(w, h, pf), cien = "rgba(0,0,0,0.38)";
    if (zs.length) {
      // strefy interfejsu platformy: tylko na podglądzie (eksport i kadr dla agenta rysują napisy osobno)
      g.save();
      g.fillStyle = cien; g.strokeStyle = "rgba(255,69,58,0.85)"; g.lineWidth = Math.max(1, w / 540); g.setLineDash([w / 90, w / 140]);
      for (const z of zs) { g.fillRect(z.x0, z.y0, z.x1 - z.x0, z.y1 - z.y0); g.strokeRect(z.x0, z.y0, z.x1 - z.x0, z.y1 - z.y0); }
      const fs = Math.round(w / 26);
      g.setLineDash([]); g.font = `600 ${fs}px system-ui, sans-serif`; g.fillStyle = "rgba(255,255,255,0.9)"; g.textBaseline = "top";
      for (const z of zs) if (z.k === "top" || z.k === "bottom") g.fillText(`${ED_STREFY[pf].name} · ${L(...ED_STREFY_OPIS[z.k])}`, w * 0.05, z.k === "top" ? fs * 0.6 : h - fs * 1.8);
      g.restore();
    }
    // typografia (słowo po słowie) pod zwykłymi tekstami; kroje wczytują się raz na zmianę planu
    if (typoBloki(P).length) {
      const fk = typoFonty(P, w, h).map(([f, txt]) => f + txt).join("|");
      if (typoFontRef.current !== fk) {
        typoFontRef.current = fk;
        Promise.all(typoFonty(P, w, h).map(([f, txt]) => fontLoad(f, txt))).then(() => drawOverlay());
      }
      typoRysuj(g, P, w, h, now, "tyl");
      osobaNaWierzch(g, P, w, h, now, zs, cien);
      typoRysuj(g, P, w, h, now, "przod");
      const s = selRef.current, b = s && s.type === "typo" && typoAktywne(P, now).find((x) => x.id === s.id);
      if (b) {                                       // zaznaczony blok: ramka w jego obrocie
        const f = typoRamka(g, b, P, w, h);
        g.save(); g.translate(f.u.cx, f.u.cy); g.rotate(((+b.rot || 0) * Math.PI) / 180);
        g.strokeStyle = b.warstwa === "tyl" ? "#B78CFF" : "#3BA9FF"; g.lineWidth = Math.max(2, w / 480); g.setLineDash([w / 90, w / 140]);
        g.strokeRect(f.x0 - f.u.cx, f.y0 - f.u.cy, f.x1 - f.x0, f.y1 - f.y0); g.restore();
      }
    }
    for (const x of P.texts) {
      if (now < x.start || now >= x.end) continue;
      const fnt = textFont(x, h, w).font;
      if (!fontGotowy(fnt, x.text)) fontLoad(fnt, x.text).then(() => drawOverlay());
      const b = drawText(g, x, w, h, karaokeIndex(x, now));
      const s = selRef.current, hit = zs.length && strefyKolizja(b, w, h, pf).length;
      if (hit || (s && s.type === "text" && s.id === x.id)) {
        g.save(); g.strokeStyle = hit ? "#FF453A" : "#3BA9FF"; g.lineWidth = Math.max(2, w / 480); g.setLineDash([w / 90, w / 140]);
        g.strokeRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0); g.restore();
      }
    }
  }
  useEffect(() => { drawOverlay(); }, [p, sel, strefa]);
  // rozmyte tło klipu w każdej warstwie (fit "blur"): mała kanwa pod wideo, rozmyta i powiększona w CSS
  function drawBlur() {
    const P = projRef.current, S = player.st.current;
    if (!P) return;
    for (const k of [0, 1]) {
      const c = player.blurs[k].current, s = S.seg[k];
      if (!c) continue;
      const on = !!s && s.c.fit === "blur";
      c.classList.toggle("is-on", on);
      if (!on) continue;
      const el = player.elOf(k), vw = el && (el.videoWidth || el.naturalWidth), vh = el && (el.videoHeight || el.naturalHeight);
      if (vw && vh) blurBg(c, el, vw, vh, P.canvas.w, P.canvas.h);
    }
  }
  useEffect(() => { drawBlur(); }, [p]);
  useEffect(() => {      // po przewinięciu i wczytaniu klatki (pauza): tło, przejście i osoba za napisem z nowej klatki
    const els = [...player.vids, ...player.imgs].map((r) => r.current).filter(Boolean);
    const on = () => { drawBlur(); player.render(tRef.current); drawOverlay(); };
    for (const e of els) for (const ev of ["seeked", "loadeddata", "load"]) e.addEventListener(ev, on);
    return () => { for (const e of els) for (const ev of ["seeked", "loadeddata", "load"]) e.removeEventListener(ev, on); };
  }, [!!p, mobile]);
  // tekst w strefie platformy: nazwy stref do ostrzeżenia w panelu (pusto = poza strefami albo kadr poziomy)
  const measure = useRef(null);
  function strefyTekstu(x) {
    const { w, h } = projRef.current.canvas;
    if (!strefyUI(w, h, strefa).length) return [];
    if (!measure.current) measure.current = document.createElement("canvas").getContext("2d");
    return strefyKolizja(textBox(measure.current, x, w, h), w, h, strefa);
  }
  const strefaUwaga = (hits, kto, rada) => hits.length > 0 && html`<p class="thq-ed-note is-warn">⚠ ${kto} ${L("wchodzi pod interfejs", "sits under the interface of")} ${ED_STREFY[strefa].name} (${[...new Set(hits)].map((k) => L(...ED_STREFY_OPIS[k])).join(", ")}). ${rada}</p>`;

  // ---------------------------------------------------------------- kadr do Wideografa i uwagi na osi
  // bieżąca klatka podglądu (wideo albo obraz klipu pod wskaźnikiem) z jej klipem; null = jeszcze niewczytana
  function klatkaPodgladu() {
    const P = projRef.current, now = tRef.current;
    const L2 = layoutClips(P.clips);
    const seg = L2.find((x) => now < x.end - 1e-6) || L2[L2.length - 1];
    const el = seg && elSeg(seg);
    const vw = el && (el.videoWidth || el.naturalWidth), vh = el && (el.videoHeight || el.naturalHeight);
    return vw && vh ? { el, vw, vh, c: seg.c } : null;
  }
  // Kadr składamy jak podgląd: klatka w tym samym kadrze (fitBox = applyFit) i napisy tą samą funkcją drawText.
  async function captureFrame(a, b) {
    const P = projRef.current;
    const { w: W, h: Hh } = P.canvas;
    const c = document.createElement("canvas");
    c.width = W; c.height = Hh;
    const g = c.getContext("2d");
    g.fillStyle = "#000"; g.fillRect(0, 0, W, Hh);
    const now = tRef.current;
    const { el, vw, vh, c: clip } = klatkaPodgladu() || {};
    if (vw && vh) {
      if (clip.fit === "blur") {
        const s = blurBg(document.createElement("canvas"), el, vw, vh, W, Hh);
        g.save(); g.filter = `blur(${Math.round(Math.max(W, Hh) / 160)}px) brightness(0.92)`;
        g.drawImage(s, -W * 0.06, -Hh * 0.06, W * 1.12, Hh * 1.12); g.restore();
      }
      const r = fitBox(vw, vh, W, Hh, clip);
      try { g.drawImage(el, r.x, r.y, r.w, r.h); } catch (_) { /* klatka jeszcze niegotowa: zostaje czarne tło */ }
    }
    for (const x of P.texts) if (now >= x.start && now < x.end) drawText(g, x, W, Hh, karaokeIndex(x, now));
    const r = shotRect(a, b, W, Hh);
    const [ow, oh] = shotSize(r.w, r.h);
    const out = document.createElement("canvas");
    out.width = ow; out.height = oh;
    out.getContext("2d").drawImage(c, r.x, r.y, r.w, r.h, 0, 0, ow, oh);
    const url = out.toDataURL("image/jpeg", 0.86);
    const blob = await new Promise((ok) => out.toBlob(ok, "image/jpeg", 0.86));
    const name = `kadr-${path.split("/").pop().replace(/\.[^.]+$/, "")}-${edClock(now).replace(/[:.]/g, "")}.jpg`;
    const up = await api.upload(new File([blob], name, { type: "image/jpeg" }));
    if (!up || !up.path) throw new Error((up && (up.detail || up.error)) || L("Nie udało się zapisać kadru.", "Could not save the frame."));
    shotUrls.current.set(up.path, url);
    return { path: up.path, url, t: now, full: r.full };
  }
  const startShot = () => { player.stop(); setShot({}); };
  function shotDown(e) {
    e.preventDefault(); e.stopPropagation();
    const box = e.currentTarget.getBoundingClientRect();
    const at = (ev) => ({ x: (ev.clientX - box.left) / box.width, y: (ev.clientY - box.top) / box.height });
    const a = at(e);
    setShot({ a, b: a });
    const move = (ev) => setShot((x) => x && { ...x, b: at(ev) });
    const up = async (ev) => {
      window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
      const b = at(ev);
      setShot({ a, b, busy: true });
      const base = { text: "", reply: "", busy: false };
      try {
        const k = await captureFrame(a, b);
        setAsk((x) => ({ ...(x || base), shot: k, error: null }));
      } catch (err) {
        setAsk((x) => ({ ...(x || base), error: err.message || String(err) }));
      }
      setShot(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }
  function addNote(text, img) {
    const n = { id: edId("n"), t: Math.round(tRef.current * 100) / 100, text: String(text || "").trim(), img: img || null, done: false };
    H.apply((P) => ({ ...P, notes: [...(P.notes || []), n] }));
    setNoteHi(n.id);
  }
  const removeNote = (id) => H.apply((P) => ({ ...P, notes: (P.notes || []).filter((n) => n.id !== id) }));
  useEffect(() => { onTick(tRef.current, false); }, [pps]);
  // po zmianie projektu odtwarzacz pokazuje właściwą klatkę (zatrzymany)
  useEffect(() => { if (p && !player.playing) player.seek(Math.min(tRef.current, Math.max(0, projTotal(p) - 0.001))); }, [p && p.clips]);

  // autozapis projektu obok filmu
  useEffect(() => {
    if (!p || !info) return undefined;
    if (conflict) return undefined;
    dirtyRef.current = true;
    setSaved(L("zmiany…", "changes…"));
    const id = setTimeout(() => {
      api.editSave(path, p, baseRef.current).then((r) => {
        if (r && r.mtime) baseRef.current = r.mtime;
        dirtyRef.current = false;
        setSaved(L("zapisano", "saved"));
      }).catch((e) => {
        if (e.conflict) {
          setSaved("");
          api.editStamp(path).then((st) => setConflict({ kto: st.kto, mtime: st.mtime })).catch(() => setConflict({}));
          return;
        }
        setSaved(L(`nie zapisano: ${e.message}`, `not saved: ${e.message}`));
      });
    }, 1200);
    return () => clearTimeout(id);
  }, [p, conflict]);
  // zapis „teraz” (np. przed prośbą do agenta) tą samą drogą co autozapis: edytor zna wersję, którą sam zapisał
  async function saveNow() {
    const r = await api.editSave(path, projRef.current, baseRef.current);
    if (r && r.mtime) baseRef.current = r.mtime;
    dirtyRef.current = false;
    setSaved(L("zapisano", "saved"));
  }
  async function keepMine() {
    const r = await api.editSave(path, projRef.current, baseRef.current, true);
    if (r && r.mtime) baseRef.current = r.mtime;
    dirtyRef.current = false;
    setConflict(null);
    setSaved(L("zapisano", "saved"));
  }

  const total = p ? projTotal(p) : 0;
  const segs = p ? layoutClips(p.clips) : [];
  const trsOsi = p ? przejsciaOsi(p.clips, p.canvas.fps) : [];
  const selItem = !p || !sel ? null : (sel.type === "clip" || sel.type === "tr" ? p.clips : sel.type === "text" ? p.texts : sel.type === "typo" ? typoBloki(p)
    : sel.type === "audio" ? p.audio : []).find((x) => x.id === sel.id) || null;

  // ---------------------------------------------------------------- operacje
  const upd = (type, id, patch, liveMode) => (liveMode ? H.live : H.apply)((P) => {
    const key = type === "clip" ? "clips" : type === "text" ? "texts" : "audio";
    return { ...P, [key]: P[key].map((x) => (x.id === id ? { ...x, ...(typeof patch === "function" ? patch(x) : patch) } : x)) };
  });
  // typografia: blok (pola bloku) i słowo (pola słowa); undefined usuwa pole, więc wraca wartość z motywu
  const typoApply = (fn, lv) => (lv ? H.live : H.apply)((P) => {
    const T = P.typo || { motyw: "czysty", bloki: [] };
    return { ...P, typo: { ...T, ...fn({ ...T, bloki: T.bloki || [] }) } };
  });
  // kolor palety filmu (typografia.py: z kontrastu z kadrem) zmieniony tu: słowa w starym kolorze idą za nim
  const typoPaletaUpd = (i, v, lv) => typoApply((T) => {
    const stary = String((T.paleta || [])[i] || "").toUpperCase(), nowy = String(v).toUpperCase();
    return { paleta: (T.paleta || []).map((x, k) => (k === i ? nowy : x)),
      bloki: T.bloki.map((b) => ({ ...b, slowa: b.slowa.map((w) => (stary && String(w.kolor || "").toUpperCase() === stary ? { ...w, kolor: nowy } : w)) })) };
  }, lv);
  const typoUpd = (id, patch, lv) => typoApply((T) => ({ bloki: T.bloki.map((b) => (b.id === id ? typoBez({ ...b, ...(typeof patch === "function" ? patch(b) : patch) }) : b)) }), lv);
  const slowoUpd = (id, j, patch, lv) => typoUpd(id, (b) => ({ slowa: b.slowa.map((w, k) => (k === j ? typoBez({ ...w, ...patch }) : w)) }), lv);
  const [typoW, setTypoW] = useState(null);      // numer zaznaczonego słowa w bloku (panel słowa)
  function typoPodziel(b, now) {                  // nowy blok od słowa pod wskaźnikiem (albo od następnego, gdy wskaźnik jest w przerwie)
    const j = b.slowa.findIndex((w, k) => k > 0 && b.start + Math.max(+w.t || 0, +w.k || 0) > now + 1e-6);
    if (j <= 0) return false;
    const d = +b.slowa[j].t || 0, li = Math.round(+b.slowa[j].linia || 0);
    const nid = typoNoweId(new Set(typoBloki(p).map((x) => x.id)), b.id);
    typoApply((T) => ({ bloki: T.bloki.flatMap((x) => (x.id !== b.id ? [x] : [
      { ...x, slowa: x.slowa.slice(0, j), end: +(x.start + d - 0.02).toFixed(3), wyjscie: "ciecie" },
      { ...x, id: nid, start: +(x.start + d).toFixed(3), slowa: x.slowa.slice(j).map((w) => ({ ...w, t: +((+w.t || 0) - d).toFixed(3),
        k: +((+w.k || 0) - d).toFixed(3), linia: Math.max(0, Math.round(+w.linia || 0) - li) })) }])) }));
    setSel({ type: "typo", id: nid });
    setTypoW(null);
    return true;
  }
  function typoPolacz(b) {                        // z następnym blokiem w jedną frazę (jego słowa w nowych liniach)
    const nast = typoBloki(p).filter((x) => x.id !== b.id && x.start >= b.start).sort((x, y) => x.start - y.start)[0];
    if (!nast) return;
    const d = nast.start - b.start, li = Math.max(...b.slowa.map((w) => Math.round(+w.linia || 0))) + 1;
    typoApply((T) => ({ bloki: T.bloki.filter((x) => x.id !== nast.id).map((x) => (x.id !== b.id ? x : { ...x, end: Math.max(x.end, nast.end),
      wyjscie: nast.wyjscie || x.wyjscie, slowa: [...x.slowa, ...nast.slowa.map((w) => ({ ...w, t: +((+w.t || 0) + d).toFixed(3),
        k: +((+w.k || 0) + d).toFixed(3), linia: Math.round(+w.linia || 0) + li }))] })) }));
  }
  function typoDodaj() {                           // własny blok w miejscu wskaźnika: jedno mocne słowo do wpisania
    const start = clamp(tRef.current, 0, Math.max(0, total - 0.5)), H2 = p.canvas.h > p.canvas.w;
    const b = { id: typoNoweId(new Set(typoBloki(p).map((x) => x.id)), "w"), start: +start.toFixed(3), end: +Math.min(total, start + 1.5).toFixed(3),
      uklad: "srodek", x: 0.5, y: H2 ? 0.62 : 0.7, w: H2 ? 0.7 : 0.5, rot: 0, tilt: 0, warstwa: "przod",
      slowa: [{ t: 0, k: 0.4, tekst: L("TEKST", "TEXT"), waga: 3, linia: 0 }] };
    typoApply((T) => ({ bloki: [...T.bloki, b].sort((x, y) => x.start - y.start) }));
    setSel({ type: "typo", id: b.id }); setTypoW(0);
    if (mobileRef.current) setTool("typo"); else setSide("inspect");
  }
  // zmiana długości albo kolejności klipów: napisy, uwagi i audio idą za materiałem (remapTimes)
  const clipsChange = (fn, liveMode) => (liveMode ? H.liveFrom : H.apply)((B) => remapTimes(B, { ...B, clips: fn(B.clips) }));
  const clipPatch = (id, patch, liveMode) => clipsChange((cs) => cs.map((c) => (c.id === id ? { ...c, ...patch } : c)), liveMode);
  // klip o innych proporcjach niż kadr W×H (z metadanych pliku; nieznane = pasuje)
  const innyKadr = (src, W, H) => { const m = meta[src]; return !!(m && m.w && m.h) && Math.abs(m.w / m.h - W / H) > 0.02 * (W / H); };
  const setCanvas = (format) => H.apply((P) => {
    const f = meta[path] || {};
    const [w, h] = format === "orig" ? edKadr(even(f.w || 1920), even(f.h || 1080)) : ED_SIZES[format];
    // klip, który pasował do starego kadru, a do nowego nie: rozmyte tło zamiast czarnych pasów (wybrane Pasy zostają)
    const clips = P.clips.map((c) => ((c.fit || "contain") === "contain" && !innyKadr(c.src, P.canvas.w, P.canvas.h) && innyKadr(c.src, w, h) ? { ...c, fit: "blur" } : c));
    return { ...P, format, canvas: { ...P.canvas, w, h }, clips };
  });
  function split() {
    if (!p) return;
    const now = tRef.current;
    if (sel && sel.type === "typo" && selItem && now >= selItem.start && now <= selItem.end) { typoPodziel(selItem, now); return; }   // w bloku tnie tylko blok
    if (sel && sel.type === "text") {
      const x = p.texts.find((y) => y.id === sel.id);
      if (x && now > x.start + ED_MIN && now < x.end - ED_MIN) {
        H.apply((P) => ({ ...P, texts: P.texts.flatMap((y) => (y.id === x.id ? [{ ...y, end: now }, { ...y, id: edId("t"), start: now }] : [y])) }));
        return;
      }
    }
    if (sel && sel.type === "audio") {
      const m = p.audio.find((y) => y.id === sel.id);
      const cut = m && m.in + (now - m.start);
      if (m && cut > m.in + ED_MIN && cut < m.out - ED_MIN) {
        H.apply((P) => ({ ...P, audio: P.audio.flatMap((y) => (y.id === m.id ? [{ ...y, out: cut }, { ...y, id: edId("a"), in: cut, start: now }] : [y])) }));
        return;
      }
    }
    const s = segs.find((x) => now > x.start + ED_MIN / 2 && now < x.end - ED_MIN / 2);
    if (!s) return;
    const cut = s.c.in + (now - s.start) * (s.c.speed || 1);
    const right = { ...s.c, id: edId("c"), in: cut };
    H.apply((P) => ({ ...P, clips: P.clips.flatMap((c) => (c.id === s.c.id ? [{ ...c, out: cut, transition: undefined }, right] : [c])) }));
    setSel({ type: "clip", id: right.id });
  }
  function remove() {
    if (!sel || !p) return;
    if (sel.type === "mark") {
      const m = speechMarks().find((x) => x.key === sel.id);
      if (m) cutTimeline([[m.t0, m.t1]]);
      setSel(null);
      if (mobileRef.current) setTool("speech");
      return;
    }
    if (sel.type === "clip" && p.clips.length <= 1) return;
    if (sel.type === "tr") { upd("clip", sel.id, { transition: undefined }); setSel(null); if (mobileRef.current) setTool(null); return; }
    if (sel.type === "typo") typoApply((T) => ({ bloki: T.bloki.filter((x) => x.id !== sel.id) }));
    else if (sel.type === "clip") clipsChange((cs) => cs.filter((x) => x.id !== sel.id));   // reszta osi dosuwa się z napisami
    else {
      const key = sel.type === "text" ? "texts" : "audio";
      H.apply((P) => ({ ...P, [key]: P[key].filter((x) => x.id !== sel.id) }));
    }
    setSel(null);
  }
  function duplicate() {
    if (!sel || !selItem || sel.type === "tr") return;
    if (sel.type === "typo") {                    // kopia bloku zaraz po nim (ta sama długość, w filmie)
      const d = selItem.end - selItem.start, st = Math.min(selItem.end, Math.max(0, total - d));
      const copy = { ...selItem, id: typoNoweId(new Set(typoBloki(p).map((x) => x.id)), selItem.id), start: +st.toFixed(3), end: +(st + d).toFixed(3) };
      typoApply((T) => ({ bloki: [...T.bloki, copy].sort((x, y) => x.start - y.start) }));
      setSel({ type: "typo", id: copy.id });
      return;
    }
    const key = sel.type === "clip" ? "clips" : sel.type === "text" ? "texts" : "audio";
    const copy = { ...selItem, id: edId(sel.type[0]) };
    if (sel.type === "text") { const d = copy.end - copy.start; copy.start = Math.min(copy.end, total - d); copy.end = copy.start + d; }
    if (sel.type === "audio") copy.start = selItem.start + audioDur(selItem);
    const ins = (arr0) => { const arr = arr0.slice(); arr.splice(arr.findIndex((x) => x.id === sel.id) + 1, 0, copy); return arr; };
    if (sel.type === "clip") clipsChange(ins);
    else H.apply((P) => ({ ...P, [key]: ins(P[key]) }));
    setSel({ type: sel.type, id: copy.id });
  }
  function addText() {
    const start = clamp(tRef.current, 0, Math.max(0, total - 0.5));
    const x = { id: edId("t"), text: L("Twój tekst", "Your text"), start, end: Math.min(total, start + 3), x: 0.5, y: 0.78, size: 72,
      color: "#FFFFFF", bg: "#000000", style: "shadow", font: ED_FONTS[0][0], bold: true, align: "center", maxw: 0.86,
      ...(projRef.current.canvas.h > projRef.current.canvas.w ? ED_PION : {}) };
    H.apply((P) => ({ ...P, texts: [...P.texts, x] }));
    setSel({ type: "text", id: x.id });
    setSide("inspect");
  }
  function addMedia(m) {
    if (m.kind === "audio") {
      const x = { id: edId("a"), src: m.path, start: clamp(tRef.current, 0, total), in: 0, out: m.duration || 10, volume: 0.6 };
      H.apply((P) => ({ ...P, audio: [...P.audio, x] }));
      setSel({ type: "audio", id: x.id });
      return;
    }
    const c = { id: edId("c"), src: m.path, kind: m.kind, in: 0, out: m.kind === "image" ? 3 : (m.duration || 3), speed: 1, volume: 1, muted: false,
      fit: innyKadr(m.path, projRef.current.canvas.w, projRef.current.canvas.h) ? "blur" : "contain" };
    clipsChange((cs) => {
      const i = sel && sel.type === "clip" ? cs.findIndex((x) => x.id === sel.id) + 1 : cs.length;
      const arr = cs.slice(); arr.splice(i || cs.length, 0, c);
      return arr;
    });
    setSel({ type: "clip", id: c.id });
  }
  async function uploadMedia(files) {
    for (const f of files) {
      try {
        const up = await api.upload(f);
        const m = await api.editMedia(up.path);
        addMeta([m]);
        setInfo((d) => ({ ...d, media: [m, ...d.media] }));
      } catch (e) { alert(e.message || String(e)); }
    }
  }

  // ---------------------------------------------------------------- eksport
  async function doExport() {
    if (!p || (job && job.state === "running")) return;
    player.stop();
    setJob({ state: "prep", progress: 0 });
    try {
      const { w, h } = p.canvas;
      const texts = p.texts.filter((x) => x.end - x.start >= 0.04 && x.start < total && String(x.text || "").trim());
      const pngs = [], karaoke = {};
      for (const [i, x] of texts.entries()) {
        pngs.push(await textPng(x, w, h));
        const ws = karaokeWords(x);
        if (ws) { karaoke[i] = []; for (let k = 0; k < ws.length; k++) karaoke[i].push(await textPng(x, w, h, k)); }
      }
      // typografia: klatka tylko tam, gdzie obraz warstwy się zmienia (typoOdcinki), reszta to długie odcinki
      const typo = {};
      if (typoBloki(p).length) {
        for (const [f, txt] of typoFonty(p, w, h)) await fontLoad(f, txt);
        const fps = p.canvas.fps || 30;
        const warstwy = ["tyl", "przod"].filter((k) => typoBloki(p).some((b) => (b.warstwa === "tyl" ? "tyl" : "przod") === k));
        const plan = warstwy.map((k) => [k, typoOdcinki(p, fps, total, k)]);
        const ile = plan.reduce((a, [, segs]) => a + segs.filter((s) => s.podpis).length, 0);
        const c = document.createElement("canvas"); c.width = w; c.height = h;
        const g = c.getContext("2d");
        let gotowe = 0;
        for (const [k, segs] of plan) {
          typo[k] = [];
          for (const s of segs) {
            let png = null;
            if (s.podpis) {
              g.clearRect(0, 0, w, h);
              typoRysuj(g, p, w, h, (s.od + 0.5) / fps, k);
              png = c.toDataURL("image/webp", 0.92);   // WebP ~3,5× lżejszy od PNG, tak samo ostry; bez WebP przeglądarka da PNG
              if (++gotowe % 10 === 0) { setJob({ state: "prep", progress: gotowe / ile }); await new Promise((r) => setTimeout(r, 0)); }
            }
            typo[k].push([s.od, s.do, png]);
          }
        }
        g.clearRect(0, 0, w, h);
        typo.pusty = c.toDataURL("image/webp", 0.92);   // pusta klatka w tym samym formacie co klatki (lista concat)
      }
      const r = await api.editExport(path, { ...p, texts }, pngs, karaoke, typo);
      setJob(r);
    } catch (e) { setJob({ state: "error", error: e.message || String(e) }); }
  }
  useEffect(() => {
    if (!job || job.state !== "running" || !job.id) return undefined;
    const id = setTimeout(() => api.editJob(job.id).then(setJob).catch((e) => setJob({ ...job, state: "error", error: e.message })), 600);
    return () => clearTimeout(id);
  }, [job]);

  // ---------------------------------------------------------------- klawiatura
  useEffect(() => {
    const onKey = (e) => {
      if (MODAL_STACK[MODAL_STACK.length - 1] !== me.current) return;
      const tag = (e.target && e.target.tagName) || "";
      if (/INPUT|TEXTAREA|SELECT/.test(tag) && e.key !== "Escape") return;
      const mod = e.ctrlKey || e.metaKey;
      if (e.key === " ") { e.preventDefault(); player.toggle(); }
      else if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? H.redo() : H.undo(); }
      else if (mod && e.key.toLowerCase() === "y") { e.preventDefault(); H.redo(); }
      else if (mod && e.key.toLowerCase() === "d") { e.preventDefault(); duplicate(); }
      else if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); }
      else if (e.key.toLowerCase() === "s" && !mod) { e.preventDefault(); split(); }
      else if (e.key.toLowerCase() === "t" && !mod) { e.preventDefault(); addText(); }
      else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); remove(); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        const step = e.shiftKey ? 1 : 1 / ((p && p.canvas.fps) || 30);
        player.seek(tRef.current + (e.key === "ArrowLeft" ? -step : step));
      } else if (e.key === "Home") player.seek(0);
      else if (e.key === "End") player.seek(total);
      else if (e.key === "Escape") { if (shot) setShot(null); else if (ask) setAsk(null); else if (sel) setSel(null); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  // ---------------------------------------------------------------- przeciąganie napisu na podglądzie
  function stagePointer(e) {
    const c = overlayRef.current;
    if (!c || !p) return;
    const r = c.getBoundingClientRect();
    const k = p.canvas.w / r.width;
    const px = (e.clientX - r.left) * k, py = (e.clientY - r.top) * k;
    const g = c.getContext("2d");
    const hits = p.texts.filter((x) => tRef.current >= x.start && tRef.current < x.end)
      .filter((x) => { const b = textBox(g, x, p.canvas.w, p.canvas.h); return px >= b.x0 && px <= b.x1 && py >= b.y0 && py <= b.y1; });
    const hit = hits[hits.length - 1];
    if (!hit) { typoPointer(e, px, py, r); return; }
    setSel({ type: "text", id: hit.id });
    selRef.current = { type: "text", id: hit.id };
    const sx = hit.x ?? 0.5, sy = hit.y ?? 0.8;
    const move = (ev) => {
      const dx = (ev.clientX - e.clientX) / r.width, dy = (ev.clientY - e.clientY) / r.height;
      let nx = clamp(sx + dx, 0, 1), ny = clamp(sy + dy, 0, 1);
      if (Math.abs(nx - 0.5) < 0.015) nx = 0.5;     // przyciąganie do środka
      if (Math.abs(ny - 0.5) < 0.015) ny = 0.5;
      upd("text", hit.id, { x: nx, y: ny }, true);
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); H.commit(); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  // blok typografii pod kursorem (przód nad tyłem): zaznaczenie i przeciąganie kotwicy, przyciąganie do środka
  function typoPointer(e, px, py, r) {
    const g = overlayRef.current.getContext("2d"), { w: W, h: Hh } = p.canvas;
    const akt = typoAktywne(p, tRef.current).sort((a, b) => (a.warstwa === "tyl") - (b.warstwa === "tyl"));
    const hit = akt.find((b) => { const f = typoRamka(g, b, p, W, Hh); return px >= f.x0 && px <= f.x1 && py >= f.y0 && py <= f.y1; });
    if (!hit) { setSel(null); return; }
    if (!(sel && sel.type === "typo" && sel.id === hit.id)) setTypoW(null);
    setSel({ type: "typo", id: hit.id });
    selRef.current = { type: "typo", id: hit.id };
    if (!mobileRef.current) setSide("inspect");
    const sx = hit.x ?? 0.5, sy = hit.y ?? 0.3;
    const move = (ev) => {
      let nx = clamp(sx + (ev.clientX - e.clientX) / r.width, 0, 1), ny = clamp(sy + (ev.clientY - e.clientY) / r.height, 0, 1);
      if (Math.abs(nx - 0.5) < 0.015) nx = 0.5;
      if (Math.abs(ny - 0.5) < 0.015) ny = 0.5;
      typoUpd(hit.id, { x: +nx.toFixed(4), y: +ny.toFixed(4) }, true);
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); H.commit(); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  // ---------------------------------------------------------------- oś czasu: przeciąganie
  const snapPts = () => {
    const pts = [0, tRef.current, total];
    for (const s of segs) pts.push(s.start, s.end);
    for (const x of p.texts) pts.push(x.start, x.end);
    for (const b of typoBloki(p)) pts.push(b.start, b.end);
    for (const m of p.audio) pts.push(m.start, m.start + audioDur(m));
    return pts;
  };
  const snap = (v, skip) => {
    const tol = 8 / pps;
    let best = v, bd = tol;
    for (const q of snapPts()) { if (skip && skip.includes(q)) continue; const d = Math.abs(q - v); if (d < bd) { bd = d; best = q; } }
    return best;
  };
  function drag(e, onMove) {
    e.stopPropagation(); e.preventDefault();
    player.stop();
    const x0 = e.clientX;
    const move = (ev) => onMove((ev.clientX - x0) / pps, ev);
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); H.commit(); setDragIdx(null); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }
  const [dragIdx, setDragIdx] = useState(null);
  function clipDown(e, s, i, edge) {
    if (e.pointerType === "touch" && !edge) return;   // palcem: dotknięcie zaznacza (onClick), przesunięcie przewija oś
    setSel({ type: "clip", id: s.c.id });
    const c0 = { ...s.c };
    const srcDur = c0.kind === "image" ? 600 : ((meta[c0.src] || {}).duration || c0.out);
    if (edge === "l") drag(e, (d) => clipPatch(c0.id, { in: clamp(c0.in + d * c0.speed, 0, c0.out - ED_MIN) }, true));
    else if (edge === "r") drag(e, (d) => {
      const end = snap(s.start + (c0.out - c0.in) / c0.speed + d, [s.end]);
      clipPatch(c0.id, { out: clamp(c0.in + (end - s.start) * c0.speed, c0.in + ED_MIN, srcDur) }, true);
    });
    else {
      // przestawianie: klip idzie tam, gdzie jest kursor (środek innego klipu = zamiana miejsc)
      const mid = s.start + (s.end - s.start) / 2;
      setDragIdx(i);
      drag(e, (d) => {
        const at = mid + d;
        // od układu sprzed gestu: klip trafia między pozostałe tam, gdzie jest kursor; napisy jadą z klipami
        clipsChange((cs) => {
          const rest = cs.filter((x) => x.id !== c0.id);
          let target = layoutClips(rest).findIndex((x) => at < x.start + (x.end - x.start) / 2);
          if (target < 0) target = rest.length;
          rest.splice(target, 0, cs.find((x) => x.id === c0.id));
          return rest;
        }, true);
      });
    }
  }
  function textDown(e, x, edge) {
    if (e.pointerType === "touch" && !edge) return;
    setSel({ type: "text", id: x.id });
    const a = x.start, b = x.end;
    drag(e, (d) => {
      if (edge === "l") {
        const ns = clamp(snap(a + d, [a]), 0, b - ED_MIN);
        upd("text", x.id, { start: ns, ...(x.words ? { words: x.words.map((w) => [+(w[0] - (ns - a)).toFixed(3), +(w[1] - (ns - a)).toFixed(3), w[2]]) } : {}) }, true);
      }
      else if (edge === "r") upd("text", x.id, { end: clamp(snap(b + d, [b]), a + ED_MIN, total) }, true);
      else { const len = b - a; const s = clamp(snap(a + d, [a, b]), 0, Math.max(0, total - len)); upd("text", x.id, { start: s, end: s + len }, true); }
    });
  }
  function typoDown(e, b, edge) {
    if (e.pointerType === "touch" && !edge) return;
    if (!(sel && sel.id === b.id)) setTypoW(null);
    setSel({ type: "typo", id: b.id });
    const a = b.start, z = b.end, s0 = b.slowa;
    drag(e, (d) => {
      if (edge === "l") {                         // początek: słowa zostają przy swoim czasie w filmie
        const ns = clamp(snap(a + d, [a]), 0, z - ED_MIN), dd = ns - a;
        typoUpd(b.id, { start: +ns.toFixed(3), slowa: s0.map((w) => ({ ...w, t: +Math.max(0, (+w.t || 0) - dd).toFixed(3), k: +Math.max(0, (+w.k || 0) - dd).toFixed(3) })) }, true);
      } else if (edge === "r") typoUpd(b.id, { end: +clamp(snap(z + d, [z]), a + ED_MIN, total).toFixed(3) }, true);
      else { const len = z - a, ns = clamp(snap(a + d, [a, z]), 0, Math.max(0, total - len)); typoUpd(b.id, { start: +ns.toFixed(3), end: +(ns + len).toFixed(3) }, true); }
    });
  }
  function audioDown(e, m, edge) {
    if (e.pointerType === "touch" && !edge) return;
    setSel({ type: "audio", id: m.id });
    const m0 = { ...m };
    const srcDur = (meta[m.src] || {}).duration || m.out;
    drag(e, (d) => {
      if (edge === "l") { const dd = clamp(d, -m0.in, audioDur(m0) - ED_MIN); upd("audio", m.id, { in: m0.in + dd, start: Math.max(0, m0.start + dd) }, true); }
      else if (edge === "r") upd("audio", m.id, { out: clamp(m0.out + d, m0.in + ED_MIN, srcDur) }, true);
      else upd("audio", m.id, { start: clamp(snap(m0.start + d, [m0.start]), 0, total) }, true);
    });
  }
  // linia głośności klipu albo audio: przeciąganie w pionie (palcem dopiero na zaznaczonym elemencie)
  function volDown(e, type, item) {
    if (e.pointerType === "touch" && !(sel && sel.id === item.id)) return;
    e.stopPropagation(); e.preventDefault();
    setSel({ type, id: item.id });
    const hgt = e.currentTarget.parentElement.getBoundingClientRect().height || 1;
    const y0 = e.clientY, p0 = volPos(item.muted ? 0 : item.volume ?? 1);
    const move = (ev) => {
      const v = posVol(clamp(p0 + (y0 - ev.clientY) / hgt, 0, 1));
      upd(type, item.id, type === "clip" ? { volume: v, muted: false } : { volume: v }, true);
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); H.commit(); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }
  const volLine = (type, item) => { const k = volPos(item.muted ? 0 : item.volume ?? 1); return html`<b class=${cx("thq-ed-vol", item.muted && "is-mute")} style=${{ bottom: `calc(${k * 100}% - ${k * 2}px)` }}
    title=${`${L("Głośność", "Volume")} ${fmtDb(item.muted ? 0 : item.volume ?? 1)} · ${L("przeciągnij w górę albo w dół", "drag up or down")}`}
    onPointerDown=${(e) => volDown(e, type, item)} onClick=${(e) => e.stopPropagation()}></b>`; };
  function rulerDown(e) {
    if (mobileRef.current) return;
    const r = tlRef.current.getBoundingClientRect();
    const at = (ev) => clamp((ev.clientX - r.left + tlRef.current.scrollLeft - pad) / pps, 0, total);
    player.seek(at(e));
    const move = (ev) => player.seek(at(ev));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }
  const fitZoom = () => {
    const w = (tlRef.current && tlRef.current.clientWidth) || 800;
    setPps(mobileRef.current ? clamp(w / 6, 20, 400) : clamp((w - 60) / Math.max(1, total), 4, 400));
  };
  useEffect(() => { if (info) setTimeout(fitZoom, 0); }, [info, mobile]);
  useEffect(() => {
    const el = tlRef.current;
    if (!el || !window.ResizeObserver) return undefined;
    const ro = new ResizeObserver(([e]) => setTlW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, [!!info, mobile]);
  const pad = mobile ? Math.round(tlW / 2) : 12;
  const firstLayout = useRef(true);
  useEffect(() => {
    if (firstLayout.current) { firstLayout.current = false; return; }
    player.stop(); player.remount();
    setTimeout(() => player.seek(tRef.current), 0);
  }, [mobile]);
  function onTlScroll() {
    const tl = tlRef.current;
    if (!mobileRef.current || !tl || Math.abs(tl.scrollLeft - autoScroll.current) <= 2) return;
    autoScroll.current = -1;
    if (player.st.current.playing) player.stop();
    cancelAnimationFrame(scrollRaf.current);
    scrollRaf.current = requestAnimationFrame(() => player.seek(tl.scrollLeft / ppsRef.current));
  }
  const dist = (e) => Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
  const tlTouch = {
    onTouchStart: (e) => { if (e.touches.length === 2) pinch.current = { d: dist(e), pps }; },
    onTouchMove: (e) => { if (pinch.current && e.touches.length === 2) setPps(clamp(pinch.current.pps * dist(e) / pinch.current.d, 4, 400)); },
    onTouchEnd: () => { pinch.current = null; },
  };
  // dotknięcie elementu osi: zaznaczenie i (na telefonie) jego narzędzia
  const pick = (e, type, id) => {
    e.stopPropagation();
    if (type === "typo") {                          // wskaźnik w bloku (wszystkie słowa już widać), żeby go było widać
      const b = typoBloki(projRef.current).find((x) => x.id === id), now = tRef.current;
      const ost = b ? Math.max(...b.slowa.map((w) => +w.t || 0)) : 0;
      if (b && (now < b.start + ost || now >= b.end)) player.seek(Math.min(b.end - 0.04, b.start + ost + 0.08));
      if (!(sel && sel.id === id)) setTypoW(null);
    }
    setSel({ type, id });
    if (mobileRef.current) setTool(type === "clip" ? "edit" : type);   // "mark" → panel znacznika, "tr" → przejścia
    else setSide("inspect");
  };

  // ---------------------------------------------------------------- napisy
  function mapCaptions(caps, src) {
    const out = [];
    for (const s of layoutClips(projRef.current.clips)) {
      if (s.c.src !== src) continue;
      for (const k of caps) {
        const a = Math.max(k.start, s.c.in), b = Math.min(k.end, s.c.out);
        if (b - a < 0.05) continue;
        out.push({ start: s.start + (a - s.c.in) / s.c.speed, end: s.start + (b - s.c.in) / s.c.speed, text: k.text });
      }
    }
    return out;
  }
  function setCaptions(list) {
    const old = projRef.current.texts.find((x) => x.cap);
    const look = old ? { x: old.x, y: old.y, size: old.size, color: old.color, bg: old.bg, style: old.style, font: old.font, bold: old.bold, maxw: old.maxw, hl: old.hl || "" } : {};
    H.apply((P) => ({ ...P, texts: [...P.texts.filter((x) => !x.cap),
      ...list.map((k) => ({ ...ED_CAP, ...(P.canvas.h > P.canvas.w ? ED_PION : {}), ...look, id: edId("t"), cap: true, start: k.start, end: k.end, text: k.text, ...(k.words ? { words: k.words } : {}) }))] }));
  }
  async function autoCaptions(force) {
    let sp = speech;
    const srcs = [...new Set(p.clips.filter((c) => c.kind === "video").map((c) => c.src))];
    if (force || srcs.some((x) => !sp[x] || !(sp[x].words || []).length)) {
      const got = await analyzeSpeech(force);
      if (!got) return;
      sp = { ...sp, ...got };
    }
    const all = groupLines(timelineWords(sp));
    if (!all.length) { setCapJob({ state: "error", error: L("Nie znalazłem mowy w klipach na osi.", "No speech found in the timeline clips.") }); return; }
    setCaptions(all);
    setCapJob({ state: "done", n: all.length });
  }
  async function srtCaptions(file) {
    try {
      const r = await api.editSrt(file);
      let list = mapCaptions(r.captions || [], path);
      // napisy do gotowego filmu, którego nie ma już na osi: czasy wprost
      if (!list.length) list = (r.captions || []).filter((k) => k.start < total).map((k) => ({ ...k, end: Math.min(k.end, total) }));
      if (!list.length) throw new Error(L("Plik nie ma napisów w czasie tego filmu.", "The file has no captions within this film."));
      setCaptions(list);
      setCapJob({ state: "done", n: list.length });
    } catch (e) { setCapJob({ state: "error", error: e.message || String(e) }); }
  }
  // przeglądarka nie odtworzyła pliku mimo deklaracji kodeka: przechodzimy na kopię podglądową
  function codecFallback() {
    const srcs = [...new Set(projRef.current.clips.filter((c) => c.kind === "video").map((c) => c.src))].filter((x) => !edProxyNeed.has(x));
    if (!srcs.length || !api.editProxy) { setCodecErr(true); return; }
    for (const x of srcs) {
      edProxyNeed.add(x);
      const u = edUrls.get(x);
      edUrls.delete(x);
      if (u) u.then((v) => URL.revokeObjectURL(v)).catch(() => {});
    }
    setStrips((st) => { const n = { ...st }; for (const x of srcs) delete n[x]; return n; });
    player.remount();
    setTimeout(() => player.seek(tRef.current), 0);
  }

  // ---------------------------------------------------------------- mowa: pauzy, wtrącenia, wycinanie
  const PAD = 0.12;   // tyle ciszy zostawiamy po obu stronach cięcia (oddech, naturalny rytm)
  function speechMarks() {
    const out = [];
    for (const s of layoutClips(projRef.current ? projRef.current.clips : [])) {
      const d = speech[s.c.src];
      if (!d) continue;
      const toT = (x) => s.start + (x - s.c.in) / s.c.speed;
      for (const [a, b] of d.silences || []) {
        if (b - a < minPause) continue;
        const a2 = Math.max(a <= s.c.in + 0.01 ? s.c.in : a + PAD, s.c.in), b2 = Math.min(b >= s.c.out - 0.01 ? s.c.out : b - PAD, s.c.out);
        if (b2 - a2 < 0.1) continue;
        const key = `p:${s.c.src}:${a}`;
        if (!ignored.has(key)) out.push({ key, kind: "pause", t0: toT(a2), t1: toT(b2) });
      }
      for (const i of d.fillers || []) {
        const w = d.words[i];
        const a2 = Math.max(w[0] - 0.03, s.c.in), b2 = Math.min(w[1] + 0.03, s.c.out);
        if (b2 - a2 < 0.05) continue;
        const key = `f:${s.c.src}:${w[0]}`;
        if (!ignored.has(key)) out.push({ key, kind: "filler", t0: toT(a2), t1: toT(b2), label: w[2] });
      }
    }
    return out.sort((x, y) => x.t0 - y.t0);
  }
  // słowa ze wszystkich klipów w czasie osi (słowo należy do klipu, w którym jest jego środek)
  function timelineWords(sp) {
    const out = [];
    for (const s of layoutClips(projRef.current ? projRef.current.clips : [])) {
      const d = (sp || speech)[s.c.src];
      if (!d) continue;
      for (const [a, b, w] of d.words || []) {
        const mid = (a + b) / 2;
        if (mid < s.c.in || mid >= s.c.out) continue;
        const a2 = Math.max(a, s.c.in), b2 = Math.min(b, s.c.out);
        out.push({ t0: s.start + (a2 - s.c.in) / s.c.speed, t1: s.start + (b2 - s.c.in) / s.c.speed, text: w });
      }
    }
    return out;
  }
  function speechBars() {
    return groupLines(timelineWords()).map((k) => ({ t0: k.start, t1: k.end, text: k.text }));
  }
  // wycięcie przedziałów osi: klipy dzielą się jak przy zwykłym cięciu, napisy i muzyka przesuwają się w lewo
  function cutTimeline(ranges) {
    const rs = ranges.filter((r) => r[1] - r[0] > 0.02).sort((x, y) => x[0] - y[0])
      .reduce((acc, r) => { const l = acc[acc.length - 1]; if (l && r[0] <= l[1]) l[1] = Math.max(l[1], r[1]); else acc.push([...r]); return acc; }, []);
    if (!rs.length) return 0;
    const clips = [];
    for (const s of layoutClips(projRef.current.clips)) {
      let pieces = [[s.start, s.end]];
      for (const [a, b] of rs) pieces = pieces.flatMap(([x, y]) => (b <= x || a >= y ? [[x, y]] : [[x, Math.min(a, y)], [Math.max(b, x), y]]).filter(([u, v]) => v - u >= 0.04));
      pieces.forEach(([x, y], k) => clips.push({ ...s.c, id: k ? edId("c") : s.c.id, in: s.c.in + (x - s.start) * s.c.speed, out: s.c.in + (y - s.start) * s.c.speed,
        transition: k === pieces.length - 1 ? s.c.transition : undefined }));
    }
    if (!clips.length) return 0;
    const shift = (t) => { let d = 0; for (const [a, b] of rs) { if (t >= b) d += b - a; else if (t > a) d += t - a; } return t - d; };
    H.apply((P) => ({ ...P, clips,
      texts: P.texts.map((x) => ({ ...x, start: shift(x.start), end: shift(x.end) })).filter((x) => x.end - x.start >= 0.05),
      audio: P.audio.map((m) => ({ ...m, start: shift(m.start) })),
      notes: (P.notes || []).map((n) => ({ ...n, t: shift(n.t) })),
      ...(P.typo ? { typo: typoPrzesun(P.typo, (b) => typoNaOsi(b, shift)) } : {}) }));
    return rs.reduce((a, [x, y]) => a + y - x, 0);
  }
  const loadSpeech = (src, data) => setSpeech((sp) => ({ ...sp, [src]: data }));
  useEffect(() => {
    if (!p || !api.editSpeechGet) return;
    for (const c of p.clips) {
      if (c.kind !== "video" || speechTried.current.has(c.src)) continue;
      speechTried.current.add(c.src);
      api.editSpeechGet(c.src).then((d) => loadSpeech(c.src, d)).catch(() => {});
    }
  }, [p && p.clips]);
  async function analyzeSpeech(force) {
    if (speechJob && speechJob.state === "running") return false;
    const srcs = [...new Set(p.clips.filter((c) => c.kind === "video").map((c) => c.src))];
    setSpeechJob({ state: "running" });
    try {
      const got = {};
      for (const src of srcs) {
        let j = await api.editSpeech(src, force);
        while (j.state === "running") { await edSleep(1200); j = await api.editJob(j.id); }
        if (j.state !== "done") throw new Error(j.error || L("Analiza mowy nie wyszła.", "Speech analysis failed."));
        got[src] = j.speech;
      }
      setSpeech((sp) => ({ ...sp, ...got }));
      setIgnored(new Set());
      setSpeechJob({ state: "done" });
      return got;
    } catch (e) { setSpeechJob({ state: "error", error: e.message || String(e) }); return false; }
  }
  const setCapLook = (patch, lv) => (lv ? H.live : H.apply)((P) => ({ ...P, texts: P.texts.map((x) => (x.cap ? { ...x, ...patch } : x)) }));

  // ---------------------------------------------------------------- widok
  if (err) return html`<div class="thq-ed"><div class="thq-ed-msg"><p>${err}</p><button type="button" class="thq-ed-btn" onClick=${onClose}>${L("Zamknij", "Close")}</button></div></div>`;
  if (!p || !info) return html`<div class="thq-ed"><div class="thq-ed-msg"><span class="thq-ed-spin"></span><p>${L("Otwieram edytor…", "Opening the editor…")}</p></div></div>`;

  const { w: CW, h: CH } = p.canvas;
  const k = box.w && box.h ? Math.min(box.w / CW, box.h / CH) : 0;
  const stageSize = k ? { width: `${Math.floor(CW * k)}px`, height: `${Math.floor(CH * k)}px` } : { width: "100%", aspectRatio: `${CW} / ${CH}` };
  const lanes = [];
  const textLane = {};
  for (const x of p.texts.slice().sort((a, b) => a.start - b.start)) {
    let li = lanes.findIndex((end) => end <= x.start + 1e-6);
    if (li < 0) { li = lanes.length; lanes.push(0); }
    lanes[li] = x.end; textLane[x.id] = li;
  }
  const nLanes = Math.max(1, lanes.length);
  const width = Math.max(total, 1) * pps + pad * 2 + (mobile ? 0 : 120);
  const step = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300].find((s) => s * pps >= 70) || 600;
  const ticks = [];
  for (let s = 0; s <= total + step; s += step) ticks.push(s);
  const media = info.media || [];
  const running = job && (job.state === "running" || job.state === "prep");
  const caps = p.texts.filter((x) => x.cap);
  const capYs = p.canvas.h > p.canvas.w ? [0.2, 0.5, ED_PION.y] : [0.16, 0.5, 0.84];   // góra / środek / dół napisów
  const capHitList = tool === "captions" || side === "captions" ? caps.map(strefyTekstu).filter((x) => x.length) : [];
  const capHits = capHitList.flat(), capHitN = capHitList.length;
  const allMuted = p.clips.filter((c) => c.kind !== "image").every((c) => c.muted);
  const hasSpeech = p.clips.some((c) => speech[c.src]);
  const speechBusy = !!(speechJob && speechJob.state === "running");
  const marks = hasSpeech ? speechMarks() : [];
  const bars = hasSpeech ? speechBars() : [];
  const markSel = sel && sel.type === "mark" ? marks.find((m) => m.key === sel.id) : null;

  // ---- panele narzędzi (te same na komputerze i telefonie)
  const seg = (items, cur, set) => html`<div class="thq-ed-seg">${items.map(([k2, label]) => html`<button type="button" key=${k2} class=${cx(cur === k2 && "is-on")} onClick=${() => set(k2)}>${label}</button>`)}</div>`;
  // kroje: siatka z nazwą pisaną danym krojem (lista ED_FONTS w 44-napisy.js, pliki lokalnie w fonts/kroje)
  // z nagłówkami grup jak siatka krojów typografii (TYPO_KROJE_GRUPY w 48-typografia.js); pole przewija się samo
  // do wybranego kroju przy pierwszym pokazaniu
  const fontBox = (el) => {
    if (!el || el.dataset.przewiniete) return;
    el.dataset.przewiniete = "1";
    const on = el.querySelector(".is-on");
    if (on) el.scrollTop = Math.max(0, on.offsetTop - el.clientHeight / 2 + on.offsetHeight / 2);
  };
  const fontPick = (cur, set) => html`<div class="thq-ed-fonts" ref=${fontBox}>${ED_FONTS.map(([f, n, g, waga], i) => {
    const btn = html`<button type="button" key=${f} class=${cx(cur === f && "is-on")} style=${{ fontFamily: f, fontWeight: waga }} onClick=${() => set(f)}>${n}</button>`;
    return i === 0 || g !== ED_FONTS[i - 1][2] ? [html`<span key=${`g${g}`} class="thq-ed-fonts-gr">${L(...(g === "systemowe" ? ["Systemowe", "System"] : TYPO_KROJE_GRUPY[g]))}</span>`, btn] : btn;
  })}</div>`;
  // pal: kolory palety filmu (typografia) w osobnym rzędzie nad stałymi kolorami
  const swatches = (cur, set, pal) => html`${(pal || []).length > 0 && html`<div class="thq-ed-sw is-pal">${pal.map((c) => html`<button type="button" key=${c}
    class=${cx(String(cur).toLowerCase() === c.toLowerCase() && "is-on")} style=${{ background: c }} onClick=${() => set(c)} aria-label=${c}
    title=${L("Paleta z filmu", "Palette from the film")}></button>`)}</div>`}<div class="thq-ed-sw">${ED_COLORS.map((c) => html`<button type="button" key=${c} class=${cx(String(cur).toLowerCase() === c.toLowerCase() && "is-on")}
    style=${{ background: c }} onClick=${() => set(c)} aria-label=${c}></button>`)}<label class="thq-ed-sw-more" title=${L("Inny kolor", "Other color")}>+<input type="color" value=${cur || "#ffffff"} onInput=${(e) => set(e.target.value, true)} onChange=${H.commit}/></label></div>`;
  const act = (icon, label, fn, opts = {}) => html`<button type="button" class=${cx("thq-ed-act", opts.bad && "is-bad", opts.on && "is-on")} disabled=${opts.disabled} onClick=${fn}>${ED_ICON[icon]}<span>${label}</span></button>`;
  const mediaList = (kinds) => html`<ul class="thq-ed-list">${media.filter((m) => kinds.includes(m.kind)).map((m) => html`<li key=${m.path}><button type="button" onClick=${() => { addMedia(m); if (mobile) setTool(m.kind === "audio" ? "audio" : "edit"); }} title=${L("Dodaj do osi czasu", "Add to the timeline")}>
    <span class=${cx("thq-ed-mk", `is-${m.kind}`)}>${m.kind === "audio" ? ED_ICON.audio : m.kind === "image" ? ED_ICON.image : ED_ICON.film}</span>
    <span class="thq-ed-mn">${m.name}</span><span class="thq-ed-md">${m.duration ? edTC(m.duration, false) : ""}</span><span class="thq-ed-plus">${ED_ICON.plus}</span></button></li>`)}</ul>`;
  const uploadBtn = (accept) => html`<label class="thq-ed-btn is-wide thq-ed-upload">${ED_ICON.upload} ${L("Dodaj z urządzenia", "Add from device")}
    <input type="file" multiple accept=${accept} onChange=${(e) => { uploadMedia(Array.from(e.target.files || [])); e.target.value = ""; }}/></label>`;

  const clipTools = (c) => html`<div class="thq-ed-form">
    <div class="thq-ed-acts">
      ${act("split", L("Tnij", "Split"), split)}
      ${act("copy", L("Duplikuj", "Duplicate"), duplicate)}
      ${p.clips[p.clips.length - 1].id !== c.id && act("trans", L("Przejście", "Transition"), () => { setSel({ type: "tr", id: c.id }); if (mobile) setTool("tr"); }, { on: !!c.transition })}
      ${c.kind !== "image" && act(c.muted ? "mute" : "volume", c.muted ? L("Włącz dźwięk", "Unmute") : L("Wycisz", "Mute"), () => upd("clip", c.id, { muted: !c.muted }))}
      ${act("trash", L("Usuń", "Delete"), remove, { bad: true, disabled: p.clips.length <= 1 })}
    </div>
    <label>${L("Kadr", "Framing")}${seg(ED_FITS.map(([k2, pl, en]) => [k2, L(pl, en)]), c.fit || "contain", (v) => upd("clip", c.id, { fit: v }))}</label>
    ${c.fit === "cover" && html`<div class="thq-ed-crop">
      <label>${L("Kadr: poziomo", "Frame: horizontal")} · ${Math.round((c.fx ?? 0.5) * 100)}%
        <input type="range" min="0" max="1" step="0.01" value=${c.fx ?? 0.5} onInput=${(e) => upd("clip", c.id, { fx: +e.target.value }, true)} onChange=${H.commit}/></label>
      <label>${L("Kadr: pionowo", "Frame: vertical")} · ${Math.round((c.fy ?? 0.5) * 100)}%
        <input type="range" min="0" max="1" step="0.01" value=${c.fy ?? 0.5} onInput=${(e) => upd("clip", c.id, { fy: +e.target.value }, true)} onChange=${H.commit}/></label>
      <label>${L("Przybliżenie", "Zoom")} · ${(c.zoom ?? 1).toFixed(2)}×
        <input type="range" min="1" max="3" step="0.05" value=${c.zoom ?? 1} onInput=${(e) => upd("clip", c.id, { zoom: +e.target.value }, true)} onChange=${H.commit}/></label>
    </div>`}
    ${c.kind !== "image" && html`<label>${L("Tempo", "Speed")} · ${c.speed}×${seg(ED_SPEEDS.map((s) => [s, `${s}×`]), c.speed, (v) => clipPatch(c.id, { speed: v }))}</label>`}
    ${c.kind !== "image" && html`<label>${L("Głośność", "Volume")} · ${Math.round((c.muted ? 0 : c.volume) * 100)}% (${fmtDb(c.muted ? 0 : c.volume)})
      <input type="range" min="0" max="2" step="0.05" value=${c.volume} onInput=${(e) => upd("clip", c.id, { volume: +e.target.value, muted: false }, true)} onChange=${H.commit}/></label>`}
    ${c.kind === "image" && html`<label>${L("Czas planszy", "Still duration")} · ${(c.out - c.in).toFixed(1)} s
      <input type="range" min="0.5" max="15" step="0.5" value=${c.out - c.in} onInput=${(e) => clipPatch(c.id, { out: c.in + +e.target.value }, true)} onChange=${H.commit}/></label>`}
    <p class="thq-ed-note">${(meta[c.src] || {}).name || c.src.split("/").pop()}${c.kind !== "image" ? ` · ${fmtT(c.in, true)} – ${fmtT(c.out, true)}` : ""}</p>
  </div>`;

  // przejście po klipie c (na cięciu z następnym): rodzaj z animowaną miniaturą, długość, podgląd, do wszystkich cięć
  const trTools = (c) => {
    const i = p.clips.findIndex((x) => x.id === c.id), n = p.clips[i + 1];
    if (!n) return html`<div class="thq-ed-form"><p class="thq-ed-note">${L("Za ostatnim klipem nie ma cięcia.", "There is no cut after the last clip.")}</p></div>`;
    const F = p.canvas.fps || 30, cur = c.transition, ef = trsOsi[i];
    const maxD = Math.min(3, Math.floor(Math.min(przDur(c), przDur(n)) * 10) / 10);
    const za_krotkie = 2 * Math.floor(Math.min(przDur(c), przDur(n)) * F / 2 + 1e-6) < 2;
    const setTr = (patch, lv) => upd("clip", c.id, (x) => ({ transition: patch && { type: "fade", dur: ED_PRZ_D, ...(x.transition || {}), ...patch } }), lv);
    const T = layoutClips(p.clips)[i].end;
    const podglad = () => { const d = ef ? ef.d : ED_PRZ_D; player.playRange(Math.max(0, T - d / 2 - 0.8), T + d / 2 + 0.8); };
    const doWszystkich = () => H.apply((P) => ({ ...P, clips: P.clips.map((x, k) => (k < P.clips.length - 1 ? { ...x, transition: cur ? { ...cur } : undefined } : x)) }));
    return html`<div class="thq-ed-form">
      ${za_krotkie ? html`<p class="thq-ed-note is-warn">${L("Klipy przy tym cięciu są za krótkie na przejście.", "The clips at this cut are too short for a transition.")}</p>` : html`
      <div class="thq-ed-trgrid">
        <button type="button" class=${cx(!cur && "is-on")} onClick=${() => setTr(null)}><span class="thq-ed-trmini is-none">${ED_ICON.close}</span><small>${L("Brak", "None")}</small></button>
        ${ED_PRZEJSCIA.map(([k2, pl, en]) => html`<button type="button" key=${k2} class=${cx(cur && cur.type === k2 && "is-on")} onClick=${() => setTr({ type: k2 })}>
          <${TrMini} type=${k2}/><small>${L(pl, en)}</small></button>`)}
      </div>
      ${cur && html`<label>${L("Długość", "Duration")} · ${fmtSek(ef ? ef.d : cur.dur)}
        <input type="range" min="0.1" max=${Math.max(0.1, maxD)} step="0.1" value=${Math.min(cur.dur ?? ED_PRZ_D, maxD)}
          onInput=${(e) => setTr({ dur: +e.target.value }, true)} onChange=${H.commit}/></label>`}
      <div class="thq-ed-acts">
        ${act("play", L("Podgląd", "Preview"), podglad)}
        ${act("copy", L("Do wszystkich cięć", "Apply to all cuts"), doWszystkich, { disabled: p.clips.length < 3 })}
        ${cur && act("trash", L("Usuń", "Remove"), remove, { bad: true })}
      </div>
      <p class="thq-ed-note">${L("Przejście leży na środku cięcia i nie skraca filmu: napisy i muzyka zostają na miejscu.",
        "The transition sits on the middle of the cut and does not shorten the film: texts and music stay in place.")}</p>`}
    </div>`;
  };

  const textTools = (x) => {
    const u = (patch, lv) => upd("text", x.id, patch, lv);
    return html`<div class="thq-ed-form">
      <textarea rows="2" value=${x.text} placeholder=${L("Wpisz tekst", "Type text")} onInput=${(e) => u({ text: e.target.value }, true)} onBlur=${H.commit}></textarea>
      ${strefaUwaga(strefyTekstu(x), x.cap ? L("Napis", "The caption") : L("Tekst", "The text"), L("Przesuń go na podglądzie.", "Move it on the preview."))}
      <label>${L("Styl", "Style")}${seg(ED_STYLES.map(([k2, pl, en]) => [k2, L(pl, en)]), x.style, (v) => u({ style: v }))}</label>
      <label>${L("Kolor", "Color")}${swatches(x.color, (v, lv) => u({ color: v }, lv))}</label>
      ${(x.style === "box" || x.style === "outline") && html`<label>${x.style === "box" ? L("Tło", "Box") : L("Obrys", "Outline")}${swatches(x.bg || "#000000", (v, lv) => u({ bg: v }, lv))}</label>`}
      <label>${L("Rozmiar", "Size")} · ${Math.round(x.size)}<input type="range" min="16" max="220" value=${x.size} onInput=${(e) => u({ size: +e.target.value }, true)} onChange=${H.commit}/></label>
      <div class="thq-ed-field"><span>${L("Krój", "Font")}</span>${fontPick(x.font, (v) => u({ font: v }))}</div>
      <div class="thq-ed-row">
        ${seg([["left", ED_ICON.alignL], ["center", ED_ICON.alignC], ["right", ED_ICON.alignR]], x.align, (v) => u({ align: v }))}
        <label class="thq-ed-check"><input type="checkbox" checked=${x.bold !== false} onChange=${(e) => u({ bold: e.target.checked })}/> ${L("Gruby", "Bold")}</label>
      </div>
      ${!mobile && html`<label>${L("Szerokość", "Width")} · ${Math.round((x.maxw || 0.86) * 100)}%<input type="range" min="0.2" max="1" step="0.01" value=${x.maxw || 0.86} onInput=${(e) => u({ maxw: +e.target.value }, true)} onChange=${H.commit}/></label>`}
      <p class="thq-ed-note">${fmtT(x.start, true)} – ${fmtT(x.end, true)} · ${L("przeciągnij napis na podglądzie, żeby go przesunąć", "drag the text on the preview to move it")}</p>
      <div class="thq-ed-acts">${act("split", L("Tnij", "Split"), split)}${act("copy", L("Duplikuj", "Duplicate"), duplicate)}${act("trash", L("Usuń", "Delete"), remove, { bad: true })}</div>
    </div>`;
  };

  const audioTools = (m) => html`<div class="thq-ed-form">
    <p class="thq-ed-sub thq-ed-subi">${ED_ICON.audio}<span>${(meta[m.src] || {}).name || m.src.split("/").pop()}</span></p>
    <label>${L("Głośność", "Volume")} · ${Math.round(m.volume * 100)}% (${fmtDb(m.volume)})<input type="range" min="0" max="2" step="0.05" value=${m.volume} onInput=${(e) => upd("audio", m.id, { volume: +e.target.value }, true)} onChange=${H.commit}/></label>
    <p class="thq-ed-note">${L("Od", "From")} ${fmtT(m.start, true)} · ${L("długość", "length")} ${fmtT(audioDur(m), true)}</p>
    <div class="thq-ed-acts">${act("split", L("Tnij", "Split"), split)}${act("copy", L("Duplikuj", "Duplicate"), duplicate)}${act("trash", L("Usuń", "Delete"), remove, { bad: true })}</div>
  </div>`;

  const audioAdd = () => html`<div class="thq-ed-form">
    <div class="thq-ed-acts">${act(allMuted ? "mute" : "volume", allMuted ? L("Włącz dźwięk filmu", "Unmute video") : L("Wycisz dźwięk filmu", "Mute video audio"),
      () => H.apply((P) => ({ ...P, clips: P.clips.map((c) => ({ ...c, muted: !allMuted })) })), { on: allMuted })}</div>
    <p class="thq-ed-note">${L("Muzyka i dźwięki z katalogu filmu:", "Music and sounds from the film's folder:")}</p>
    ${media.some((m) => m.kind === "audio") ? mediaList(["audio"]) : html`<p class="thq-ed-note">${L("Brak plików audio w katalogu.", "No audio files in the folder.")}</p>`}
    ${uploadBtn("audio/*")}
  </div>`;

  const captionTools = () => html`<div class="thq-ed-form">
    ${info.stt ? html`<button type="button" class="thq-ed-btn is-main is-wide" disabled=${speechBusy} onClick=${() => autoCaptions(false)}>
        ${ED_ICON.spark} ${speechBusy ? L("Rozpoznaję mowę…", "Recognising speech…") : caps.length ? L("Wstaw napisy ze słów jeszcze raz", "Insert captions from words again") : L("Automatyczne napisy (zgrane ze słowami)", "Auto captions (synced to words)")}</button>
        <p class="thq-ed-note">${L("Rozpoznawanie działa na serwerze (Parakeet, bez internetu). Pierwszy raz trwa dłużej: pobiera się model.", "Recognition runs on the server (Parakeet, offline). The first run downloads the model.")}</p>`
      : html`<p class="thq-ed-note">${L("Rozpoznawanie mowy jest niedostępne w tej instalacji. Możesz wczytać gotowy plik .srt.", "Speech recognition is not available here. You can load a .srt file.")}</p>`}
    ${(info.subs || []).length > 0 && html`<p class="thq-ed-note">${L("Z pliku napisów:", "From a subtitle file:")}</p>
      <ul class="thq-ed-list">${info.subs.map((f) => html`<li key=${f}><button type="button" onClick=${() => srtCaptions(f)}><span class="thq-ed-mk is-text">${ED_ICON.captions}</span><span class="thq-ed-mn">${f.split("/").pop()}</span><span class="thq-ed-plus">+</span></button></li>`)}</ul>`}
    ${capJob && capJob.state === "error" && html`<p class="thq-ed-bad">${capJob.error}</p>`}
    ${speechJob && speechJob.state === "error" && html`<p class="thq-ed-bad">${speechJob.error}</p>`}
    ${capJob && capJob.state === "done" && html`<p class="thq-ed-ok">✓ ${L(`Dodano ${capJob.n} ${plForma(capJob.n, NAPISY)}`, `Added ${capJob.n} captions`)}</p>`}
    ${caps.length > 0 && html`
      <label>${L("Styl napisów", "Caption style")}${seg(ED_STYLES.map(([k2, pl, en]) => [k2, L(pl, en)]), caps[0].style, (v) => setCapLook({ style: v }))}</label>
      <label>${L("Położenie", "Position")}${seg([[capYs[0], L("Góra", "Top")], [0.5, L("Środek", "Middle")], [capYs[2], L("Dół", "Bottom")]], capYs.find((y) => Math.abs(y - caps[0].y) < 0.02), (v) => setCapLook({ y: v }))}</label>
      ${strefaUwaga(capHits, L(`${capHitN} z ${caps.length} ${plForma(caps.length, NAPISY)}`, `${capHitN} of ${caps.length} captions`), L("Ustaw położenie wyżej albo zmniejsz napisy.", "Move them up or make them smaller."))}
      <label>${L("Kolor", "Color")}${swatches(caps[0].color, (v, lv) => setCapLook({ color: v }, lv))}</label>
      ${caps.some((x) => (x.words || []).length) ? html`<label class="thq-ed-check"><input type="checkbox" checked=${!!caps[0].hl}
          onChange=${(e) => setCapLook({ hl: e.target.checked ? (caps[0].hlLast || ED_HL) : "", hlLast: caps[0].hl || caps[0].hlLast })}/> ${L("Karaoke: aktywne słowo w kolorze", "Karaoke: highlight the spoken word")}</label>
        ${caps[0].hl && html`<label>${L("Kolor aktywnego słowa", "Active word color")}${swatches(caps[0].hl, (v, lv) => setCapLook({ hl: v }, lv))}</label>`}`
        : html`<p class="thq-ed-note">${L("Karaoke działa z napisami ze słów (automatyczne napisy), nie z pliku .srt.", "Karaoke works with word-synced auto captions, not .srt files.")}</p>`}
      <label>${L("Rozmiar", "Size")} · ${Math.round(caps[0].size)}<input type="range" min="24" max="140" value=${caps[0].size} onInput=${(e) => setCapLook({ size: +e.target.value }, true)} onChange=${H.commit}/></label>
      <p class="thq-ed-note">${L(`${caps.length} ${plForma(caps.length, NAPISY)}. Pojedynczy napis poprawisz, dotykając go na osi czasu.`, `${caps.length} captions. Tap one on the timeline to fix its text.`)}</p>
      <div class="thq-ed-acts">${act("trash", L("Usuń napisy", "Remove captions"), () => H.apply((P) => ({ ...P, texts: P.texts.filter((x) => !x.cap) })), { bad: true })}</div>`}
    ${typoPlanTools()}
  </div>`;

  // ---- typografia: plan (motyw, akcent) i blok ze słowami (48-typografia.js rysuje, tu tylko dane);
  // sekcja planu siedzi w formularzu panelu Napisy i bloku, żeby całość przewijała się jednym paskiem
  const typoPlanTools = () => {
    const T = p.typo || {}, n = typoBloki(p).length, m = typoMotyw(p);
    return html`<div class="thq-ed-typo-plan">
      <p class="thq-ed-sub">${L("Typografia słowo po słowie", "Word-by-word typography")}${n ? ` · ${n} ${L(plForma(n, BLOKI), n === 1 ? "block" : "blocks")}` : ""}</p>
      ${n ? html`
        <div class="thq-ed-field"><span>${L("Styl filmu", "Film style")} · ${L(...(TYPO_MOTYWY[T.motyw] || TYPO_MOTYWY.czysty).nazwa)}</span>
          <${TypoStyle} P=${p} klatka=${klatkaPodgladu} onPick=${(v) => typoApply(() => ({ motyw: v }))}/>
          <p class="thq-ed-note">${L("Styl zmienia kroje, obrys, ruch i uderzenie w całym filmie. Układ bloków, kolory i Twoje poprawki zostają.",
            "A style changes fonts, stroke, motion and the hit word across the film. Block layout, colors and your edits stay.")}</p></div>
        ${(T.paleta || []).length > 0 && html`<label>${L("Paleta z filmu", "Palette from the film")}<div class="thq-ed-sw is-pal">${T.paleta.map((c, i) => html`<label key=${i}
          class="thq-ed-sw-pal" style=${{ background: c }} title=${L("Zmień kolor: wszystkie słowa w nim pójdą za nim", "Change the color: every word in it follows")}>
          <input type="color" value=${c} onInput=${(e) => typoPaletaUpd(i, e.target.value, true)} onChange=${H.commit}/></label>`)}</div></label>
        <p class="thq-ed-note">${L("Wideograf dobrał te kolory do kadru (kontrast z barwami sceny) i rozłożył je na mocne słowa.", "The video agent picked these colors to contrast with the footage and spread them over the strong words.")}</p>`}
        <label>${L("Akcent: kolor uderzenia", "Accent: hit word color")}${swatches(m.akcent, (v, lv) => typoApply(() => ({ akcent: v }), lv), T.paleta)}</label>
        ${T.akcent && html`<button type="button" class="thq-ed-btn is-wide" onClick=${() => typoApply(() => ({ akcent: undefined }))}>${ED_ICON.reset} ${L("Akcent z motywu", "Theme accent")}</button>`}
        <p class="thq-ed-note">${L("Kliknij blok na osi albo na podglądzie, żeby zmienić słowa, układ, głębię i ruch.", "Click a block on the timeline or the preview to change words, layout, depth and motion.")}</p>
        <div class="thq-ed-acts">
          ${act("plus", L("Dodaj blok", "Add block"), typoDodaj)}
          ${act("trash", L("Usuń typografię", "Remove typography"), () => { H.apply(({ typo: _t, ...rest }) => rest); setSel(null); }, { bad: true })}
        </div>`
      : html`<p class="thq-ed-note">${L("Napisy jak z montażu: każde słowo w swoim czasie, różne wielkości, kroje, kolory, głębia, skos i 3D, mocne słowo czasem za osobą. Plan układa Wideograf z mowy filmu, a Ty poprawiasz tu każdy blok i słowo.",
          "Edit-style captions: every word on its beat, different sizes, fonts, colors, depth, slant and 3D, a strong word sometimes behind the person. The video agent plans it from the speech; you fine-tune every block and word here.")}</p>
        <button type="button" class="thq-ed-btn is-main is-wide" onClick=${() => setAsk({ text: L("Ułóż typografię słowo po słowie do tego filmu.", "Lay out word-by-word typography for this film."), reply: "", busy: false })}>${ED_ICON.spark} ${L("Poproś Wideografa o typografię", "Ask the video agent for typography")}</button>
        <button type="button" class="thq-ed-btn is-wide" onClick=${typoDodaj}>${ED_ICON.plus} ${L("Dodaj blok ręcznie", "Add a block by hand")}</button>`}
    </div>`;
  };
  const typoTools = (b) => {
    const m = typoMotyw(p), auto = L("Auto", "Auto");
    const u = (patch, lv) => typoUpd(b.id, patch, lv);
    const naj = b.slowa.reduce((a, x, k) => ((+x.waga || 0) > (+b.slowa[a].waga || 0) ? k : a), 0);
    const j = typoW !== null && typoW < b.slowa.length ? typoW : naj;
    const w = b.slowa[j], wyg = typoSlowo(w, m, b.uklad);       // wygląd słowa teraz (z motywu albo nadpisany)
    const su = (patch, lv) => slowoUpd(b.id, j, patch, lv);
    const tyl = b.warstwa === "tyl", li = Math.round(+w.linia || 0);
    const suwak = (label, v, min, max, step, fn, fmt) => html`<label>${label} · ${fmt(v)}
      <input type="range" min=${min} max=${max} step=${step} value=${v} onInput=${(e) => fn(+e.target.value, true)} onChange=${H.commit}/></label>`;
    return html`<div class="thq-ed-form">
      <p class="thq-ed-sub">${L("Blok typografii", "Typography block")} · ${fmtT(b.start, true)} – ${fmtT(b.end, true)}</p>
      <div class="thq-ed-typo-slowa" role="group" aria-label=${L("Słowa bloku", "Block words")}>${b.slowa.map((x, k) => html`<button type="button" key=${k}
        class=${cx(`is-w${typoClamp(Math.round(+x.waga || 0), 0, 3)}`, k === j && "is-on")} onClick=${() => setTypoW(k)}>${x.tekst}</button>`)}</div>
      <input class="thq-ed-input" type="text" value=${w.tekst} aria-label=${L("Tekst słowa", "Word text")} onInput=${(e) => su({ tekst: e.target.value }, true)} onBlur=${H.commit}/>
      <label>${L("Waga słowa", "Word weight")}${seg(TYPO_WAGI_NAZWY.map(([pl, en], k2) => [k2, L(pl, en)]), wyg.waga, (v) => su({ waga: v }))}</label>
      <label>${L("Kolor", "Color")}${swatches(wyg.kolor, (v, lv) => su({ kolor: v }, lv), (p.typo || {}).paleta)}</label>
      ${w.kolor && html`<button type="button" class="thq-ed-btn is-wide" onClick=${() => su({ kolor: undefined })}>${ED_ICON.reset} ${L("Kolor z motywu (akcent tylko na uderzeniu)", "Theme color (accent only on the hit)")}</button>`}
      <div class="thq-ed-field"><span>${L("Krój", "Font")}</span><div class="thq-ed-fonts" ref=${fontBox}>${[["", auto, ""], ...Object.entries(TYPO_KROJE).map(([k2, f]) => [k2, f[3], f[4]])].map(([k2, n, g], i, all) => {
        const f = k2 && TYPO_KROJE[k2];
        const btn = html`<button type="button" key=${k2 || "auto"} class=${cx((w.kroj || "") === k2 && "is-on")} onClick=${() => su({ kroj: k2 || undefined })}
          style=${f ? { fontFamily: f[0], fontWeight: f[1], fontStyle: f[2] ? "italic" : "normal" } : {}}>${n}</button>`;
        return g && g !== all[i - 1][2] ? [html`<span key=${`g${g}`} class="thq-ed-fonts-gr">${L(...TYPO_KROJE_GRUPY[g])}</span>`, btn] : btn;
      })}</div></div>
      <label>${L("Styl", "Style")}${seg([["", auto], ...TYPO_STYLE.map((k2) => [k2, L(...TYPO_STYLE_NAZWY[k2])])], w.styl || "", (v) => su({ styl: v || undefined }))}</label>
      <label>${L("Głębia słowa", "Word depth")}${seg([[-1, L("Dalej", "Back")], [0, L("Zwykła", "Normal")], [1, L("Bliżej", "Front")]], wyg.glebia, (v) => su({ glebia: v || undefined }))}</label>
      <label>${L("Wielkie litery", "Capitals")}${seg([["", auto], ["tak", "AA"], ["nie", "Aa"]], w.wielkie === true ? "tak" : w.wielkie === false ? "nie" : "", (v) => su({ wielkie: v === "tak" ? true : v === "nie" ? false : undefined }))}</label>
      ${suwak(L("Skala słowa", "Word scale"), +w.skala || 1, 0.3, 3, 0.05, (v, lv) => su({ skala: Math.abs(v - 1) < 0.001 ? undefined : v }, lv), (v) => `${Math.round(v * 100)}%`)}
      <div class="thq-ed-row"><span class="thq-ed-note">${L("Linia", "Line")} ${li + 1}</span>
        ${seg([["gora", L("↑ wyżej", "↑ up")], ["dol", L("↓ niżej", "↓ down")]], null, (v) => su({ linia: Math.max(0, li + (v === "dol" ? 1 : -1)) }))}</div>

      <p class="thq-ed-sub">${L("Blok", "Block")}</p>
      <label>${L("Układ", "Layout")}${seg(TYPO_UKLADY.map((k2) => [k2, L(...TYPO_UKLAD_NAZWY[k2])]), b.uklad, (v) => u(v === "za" ? { uklad: v, warstwa: "tyl", rot: 0, tilt: 0 } : { uklad: v }))}</label>
      <label>${L("Głębia bloku", "Block depth")}${seg([["przod", L("Przed osobą", "In front")], ["tyl", L("Za osobą", "Behind")]], tyl ? "tyl" : "przod", (v) => u({ warstwa: v }))}</label>
      ${tyl && !maskaBloku(b) && html`<p class="thq-ed-note is-warn">⚠ ${L("Osoba zasłoni ten napis, gdy Wideograf policzy jej sylwetkę w tym fragmencie. Do tego czasu napis widać w całości.",
          "The person will cover this text once the video agent computes their silhouette here. Until then the text is fully visible.")}</p>
        <button type="button" class="thq-ed-btn is-wide" onClick=${() => setAsk({ text: L(`Policz sylwetkę osoby dla bloku typografii „${typoTekst(b)}” (${fmtT(b.start, true)}–${fmtT(b.end, true)}), żeby napis był za osobą.`,
          `Compute the person's silhouette for the typography block "${typoTekst(b)}" (${fmtT(b.start, true)}–${fmtT(b.end, true)}) so the text sits behind them.`), reply: "", busy: false })}>${ED_ICON.spark} ${L("Poproś Wideografa o sylwetkę", "Ask the video agent for the silhouette")}</button>`}
      ${suwak(L("Rozmiar", "Size"), +b.rozmiar || 1, 0.3, 3, 0.05, (v, lv) => u({ rozmiar: v }, lv), (v) => `${Math.round(v * 100)}%`)}
      ${suwak(L("Szerokość", "Width"), +b.w || 0.62, 0.15, 1, 0.01, (v, lv) => u({ w: v }, lv), (v) => `${Math.round(v * 100)}%`)}
      ${suwak(L("Obrót", "Rotation"), +b.rot || 0, -45, 45, 1, (v, lv) => u({ rot: v }, lv), (v) => `${v}°`)}
      ${suwak(L("Perspektywa 3D", "3D perspective"), +b.tilt || 0, -45, 45, 1, (v, lv) => u({ tilt: v }, lv), (v) => `${v}°`)}
      <label>${L("Wejście słów", "Word entrance")}${seg([["", auto], ...Object.keys(TYPO_WEJSCIA).map((k2) => [k2, L(...TYPO_WEJSCIA_NAZWY[k2])])], b.wejscie || "", (v) => u({ wejscie: v || undefined }))}</label>
      <label>${L("Wyjście bloku", "Block exit")}${seg([["", auto], ...Object.keys(TYPO_WYJSCIA).map((k2) => [k2, L(...TYPO_WYJSCIA_NAZWY[k2])])], b.wyjscie || "", (v) => u({ wyjscie: v || undefined }))}</label>
      <p class="thq-ed-note">${L("Przeciągnij blok na podglądzie, żeby go przesunąć; na osi zmienisz jego czas. Tnij dzieli blok na słowie pod wskaźnikiem.",
        "Drag the block on the preview to move it; change its timing on the timeline. Split cuts the block at the word under the playhead.")}</p>
      <div class="thq-ed-acts">
        ${act("split", L("Tnij", "Split"), split)}${act("copy", L("Duplikuj", "Duplicate"), duplicate)}
        ${act("plus", L("Połącz z następnym", "Merge with next"), () => typoPolacz(b), { disabled: !typoBloki(p).some((x) => x.id !== b.id && x.start >= b.start) })}
        ${act("trash", L("Usuń", "Delete"), remove, { bad: true })}
      </div>
      ${typoPlanTools()}
    </div>`;
  };

  const speechTools = () => {
    const pauses = marks.filter((m) => m.kind === "pause"), fillers = marks.filter((m) => m.kind === "filler");
    const sum = (xs) => xs.reduce((a, m) => a + m.t1 - m.t0, 0);
    const cutAll = (xs) => { const d = cutTimeline(xs.map((m) => [m.t0, m.t1])); setSel(null); setCutNote(d ? L(`Wycięto ${d.toFixed(1)} s. Ctrl+Z / ↶ cofa.`, `Cut ${d.toFixed(1)} s. Undo brings it back.`) : ""); };
    return html`<div class="thq-ed-form">
      ${!hasSpeech ? html`<p class="thq-ed-note">${L("Wykryję, co i kiedy jest mówione, gdzie są pauzy i wtrącenia („yyy”, „eee”), i zaznaczę to na osi czasu. Każdy fragment wytniesz jednym dotknięciem albo wszystkie naraz.",
          "I will detect what is said and when, where the pauses and fillers are, and mark them on the timeline. Cut one with a tap or all at once.")}</p>
        <button type="button" class="thq-ed-btn is-main is-wide" disabled=${speechBusy} onClick=${() => analyzeSpeech(false)}>${ED_ICON.speech} ${speechBusy ? L("Analizuję mowę…", "Analysing speech…") : L("Wykryj mowę i pauzy", "Detect speech and pauses")}</button>
        ${!info.stt && html`<p class="thq-ed-note">${L("Bez rozpoznawania mowy w tej instalacji wykryję same pauzy (cisza w dźwięku).", "Without speech recognition here I can detect pauses only (silence).")}</p>`}`
      : html`
        <div class="thq-ed-stats">
          <span><i class="is-pause"></i>${L("Pauzy", "Pauses")} <b>${pauses.length}</b> · ${sum(pauses).toFixed(1)} s</span>
          <span><i class="is-filler"></i>${L("Wtrącenia", "Fillers")} <b>${fillers.length}</b></span>
        </div>
        <label>${L("Pauza dłuższa niż", "Pause longer than")} · ${minPause.toFixed(1)} s<input type="range" min="0.3" max="2" step="0.1" value=${minPause} onInput=${(e) => setMinPause(+e.target.value)}/></label>
        <div class="thq-ed-acts">
          ${act("split", L(`Wytnij pauzy (${pauses.length})`, `Cut pauses (${pauses.length})`), () => cutAll(pauses), { disabled: !pauses.length })}
          ${act("trash", L(`Wytnij „yyy” (${fillers.length})`, `Cut fillers (${fillers.length})`), () => cutAll(fillers), { disabled: !fillers.length })}
          ${act("check", L("Wytnij wszystko", "Cut all"), () => cutAll(marks), { disabled: !marks.length })}
        </div>
        ${cutNote && html`<p class="thq-ed-ok">✓ ${cutNote}</p>`}
        <p class="thq-ed-note">${L("Na osi: czerwone = pauzy, pomarańczowe = wtrącenia, szare paski = wypowiedzi. Dotknij znacznika, żeby go wyciąć albo zostawić.",
          "On the timeline: red = pauses, orange = fillers, grey bars = speech. Tap a mark to cut or keep it.")}</p>
        <button type="button" class="thq-ed-btn is-wide" disabled=${speechBusy} onClick=${() => analyzeSpeech(true)}>${speechBusy ? L("Analizuję…", "Analysing…") : L("Wykryj ponownie", "Detect again")}</button>`}
      ${speechJob && speechJob.state === "error" && html`<p class="thq-ed-bad">${speechJob.error}</p>`}
    </div>`;
  };
  const markTools = (m) => html`<div class="thq-ed-form">
    <p class="thq-ed-sub">${m.kind === "pause" ? L("Pauza", "Pause") : L(`Wtrącenie „${m.label}”`, `Filler “${m.label}”`)} · ${fmtT(m.t0, true)} – ${fmtT(m.t1, true)} (${(m.t1 - m.t0).toFixed(2)} s)</p>
    <div class="thq-ed-acts">
      ${act("split", L("Wytnij", "Cut"), remove)}
      ${act("check", L("Zostaw", "Keep"), () => { setIgnored((g) => new Set([...g, m.key])); setSel(null); if (mobile) setTool("speech"); })}
      ${act("speech", L("Odsłuchaj", "Listen"), () => { player.seek(Math.max(0, m.t0 - 1)); setTimeout(() => player.play(), 50); })}
    </div>
  </div>`;

  const inne = p.clips.filter((c) => innyKadr(c.src, CW, CH));
  const formatTools = () => html`<div class="thq-ed-form">
    <div class="thq-ed-ratios">${ED_FORMATS.map(([k2, pl, en]) => {
      const [w, h] = k2 === "orig" ? [(meta[path] || {}).w || 16, (meta[path] || {}).h || 9] : ED_SIZES[k2];
      const r = w / h, bw = r >= 1 ? 30 : Math.round(30 * r), bh = r >= 1 ? Math.round(30 / r) : 30;
      return html`<button type="button" key=${k2} class=${cx((p.format || "orig") === k2 && "is-on")} onClick=${() => setCanvas(k2)}>
        <i style=${{ width: `${bw}px`, height: `${bh}px` }}></i><span>${k2 === "orig" ? L("Oryginał", "Original") : k2}</span><small>${L(pl, en).split("· ")[1] || ""}</small></button>`;
    })}</div>
    ${strefyUI(CW, CH, "tiktok").length > 0 && html`<label>${L("Strefy platformy · tylko podgląd", "Platform safe zones · preview only")}${seg([["off", L("Wył.", "Off")],
      ...Object.entries(ED_STREFY).map(([k2, z]) => [k2, z.name])], ED_STREFY[strefa] ? strefa : "off", pickStrefa)}</label>`}
    ${inne.length > 0 && html`<label>${L(`Klipy o innych proporcjach (${inne.length})`, `Clips with other proportions (${inne.length})`)}${seg(ED_FITS.map(([k2, pl, en]) => [k2, L(pl, en)]),
      inne.every((c) => (c.fit || "contain") === (inne[0].fit || "contain")) ? inne[0].fit || "contain" : null,
      (v) => H.apply((P) => ({ ...P, clips: P.clips.map((c) => (innyKadr(c.src, P.canvas.w, P.canvas.h) ? { ...c, fit: v } : c)) })))}</label>
      <p class="thq-ed-note">${CH > CW ? L("Kadr pionowy. Film ma zostać poziomy? Wybierz 16:9 albo Oryginał powyżej.", "Vertical frame. Want a horizontal film? Pick 16:9 or Original above.")
        : L("Kadr poziomy. Film na TikToka, Reels albo Shorts? Wybierz 9:16 powyżej.", "Horizontal frame. For TikTok, Reels or Shorts pick 9:16 above.")}</p>`}
    <label>${L("Klatki na sekundę", "Frame rate")}${seg([24, 25, 30, 50, 60].map((f) => [f, String(f)]), p.canvas.fps, (v) => H.apply((P) => ({ ...P, canvas: { ...P.canvas, fps: v } })))}</label>
    <p class="thq-ed-note">${CW}×${CH} · ${fmtT(total, true)}</p>
  </div>`;

  // ---- wspólne elementy: scena, oś czasu
  const stage = html`<div class="thq-ed-fit" ref=${wrapRef}>
    <div class="thq-ed-stage" ref=${stageRef} style=${stageSize}>
      ${[0, 1].map((k) => html`<div key=${k} ref=${player.layers[k]} class="thq-ed-layer">
        <canvas ref=${player.blurs[k]} class="thq-ed-blur" aria-hidden="true"></canvas>
        <video ref=${player.vids[k]} class="thq-ed-v" playsinline preload="auto" onError=${codecFallback}></video>
        <img ref=${player.imgs[k]} class="thq-ed-v" alt=""/>
      </div>`)}
      <canvas ref=${player.pixRef} class="thq-ed-pix" aria-hidden="true"></canvas>
      ${proxying > 0 && html`<p class="thq-ed-codec is-info"><span class="thq-ed-spin is-small"></span> ${L("Przygotowuję podgląd dla tej przeglądarki (kopia WebM na serwerze, raz)…", "Preparing a preview this browser can play (one-time WebM copy)…")}</p>`}
      <canvas ref=${overlayRef} class="thq-ed-overlay" onPointerDown=${stagePointer}></canvas>
      ${shot && html`<div class=${cx("thq-ed-shot", shot.a && "is-drag", shot.busy && "is-busy")} onPointerDown=${shot.busy ? null : shotDown}>
        ${shot.a && html`<i style=${{ left: `${Math.min(shot.a.x, shot.b.x) * 100}%`, top: `${Math.min(shot.a.y, shot.b.y) * 100}%`,
          width: `${Math.abs(shot.b.x - shot.a.x) * 100}%`, height: `${Math.abs(shot.b.y - shot.a.y) * 100}%` }}></i>`}</div>`}
      ${codecErr && html`<p class="thq-ed-codec">${L("Ta przeglądarka nie odtwarza kodeka tego filmu (np. Chromium bez H.264). Montaż i eksport działają; do podglądu użyj Chrome, Edge albo Safari.",
        "This browser cannot decode the video codec (e.g. Chromium without H.264). Editing and export still work; use Chrome, Edge or Safari to preview.")}</p>`}
    </div></div>
    ${p.audio.map((m) => html`<${EdAudio} key=${m.id} m=${m} audios=${player.audios}/>`)}`;

  const notes = p.notes || [];
  const noteTrack = notes.length > 0 && html`<div class="thq-ed-track is-notes" onPointerDown=${rulerDown}>
    ${notes.map((n) => html`<button type="button" key=${n.id} class=${cx("thq-ed-pin", n.done && "is-done", noteHi === n.id && "is-sel")}
      style=${{ left: `${n.t * pps}px` }} title=${`${edClock(n.t)} · ${n.text || L("kadr", "frame")}${n.done ? ` · ✓ ${n.odp || ""}` : ""}`}
      aria-label=${`${L("Uwaga", "Note")} ${edClock(n.t)}`} onPointerDown=${(e) => e.stopPropagation()}
      onClick=${(e) => { e.stopPropagation(); player.seek(n.t); setNoteHi(n.id); if (!ask) setAsk({ text: "", reply: "", busy: false }); }}>${n.done ? "✓" : ""}</button>`)}
  </div>`;
  const textTrack = html`<div class="thq-ed-track is-text" style=${{ height: `${(p.texts.length ? nLanes : 1) * 26 + 6}px` }} onPointerDown=${rulerDown} onClick=${() => mobile && setSel(null)}>
    ${mobile && html`<button type="button" class="thq-ed-lane" onPointerDown=${(e) => e.stopPropagation()} onClick=${(e) => { e.stopPropagation(); addText(); setTool("text"); }} aria-label=${L("Dodaj tekst", "Add text")}>${ED_ICON.text}</button>`}
    ${p.texts.map((x) => html`<div key=${x.id} class=${cx("thq-ed-item is-text", x.cap && "is-cap", sel && sel.id === x.id && "is-sel")}
      style=${{ left: `${x.start * pps}px`, width: `${Math.max(6, (x.end - x.start) * pps)}px`, top: `${3 + textLane[x.id] * 26}px` }}
      onPointerDown=${(e) => textDown(e, x)} onClick=${(e) => pick(e, "text", x.id)}>
      <i class="thq-ed-h is-l" onPointerDown=${(e) => textDown(e, x, "l")}></i><span>${x.text}</span><i class="thq-ed-h is-r" onPointerDown=${(e) => textDown(e, x, "r")}></i></div>`)}
    ${mobile && !p.texts.length && html`<button type="button" class="thq-ed-add" style=${{ left: `${t * pps}px` }} onClick=${(e) => { e.stopPropagation(); addText(); setTool("text"); }}>${ED_ICON.plus}${L("Dodaj tekst", "Add text")}</button>`}
  </div>`;
  const typoLane = {}, tLanes = [];
  for (const b of typoBloki(p).slice().sort((a, c) => a.start - c.start)) {
    let li = tLanes.findIndex((end) => end <= b.start + 1e-6);
    if (li < 0) { li = tLanes.length; tLanes.push(0); }
    tLanes[li] = b.end; typoLane[b.id] = li;
  }
  const typoTrack = tLanes.length > 0 && html`<div class="thq-ed-track is-typo" style=${{ height: `${tLanes.length * 26 + 6}px` }} onPointerDown=${rulerDown} onClick=${() => mobile && setSel(null)}>
    ${typoBloki(p).map((b) => html`<div key=${b.id} class=${cx("thq-ed-item is-typo", b.warstwa === "tyl" && "is-tyl", sel && sel.type === "typo" && sel.id === b.id && "is-sel")}
      style=${{ left: `${b.start * pps}px`, width: `${Math.max(6, (b.end - b.start) * pps)}px`, top: `${3 + typoLane[b.id] * 26}px` }}
      title=${`${typoTekst(b)}${b.warstwa === "tyl" ? ` · ${L("za osobą", "behind the person")}` : ""}`}
      onPointerDown=${(e) => typoDown(e, b)} onClick=${(e) => pick(e, "typo", b.id)}>
      <i class="thq-ed-h is-l" onPointerDown=${(e) => typoDown(e, b, "l")}></i><span>${b.slowa.map((w, k) => html`<b key=${k} class=${`is-w${typoClamp(Math.round(+w.waga || 0), 0, 3)}`}>${w.tekst} </b>`)}</span><i class="thq-ed-h is-r" onPointerDown=${(e) => typoDown(e, b, "r")}></i></div>`)}
  </div>`;
  const videoTrack = html`<div class="thq-ed-track is-video" onPointerDown=${rulerDown} onClick=${() => mobile && setSel(null)}>
    ${segs.map((s, i) => {
      const strip = strips[s.c.src];
      const wpx = (s.end - s.start) * pps;
      let bg = {};
      if (strip && strip.url) {
        bg = s.c.kind === "image" ? { backgroundImage: `url(${strip.url})`, backgroundSize: "auto 100%", backgroundRepeat: "repeat-x" }
          : { backgroundImage: `url(${strip.url})`, backgroundSize: `${strip.dur / s.c.speed * pps}px 100%`, backgroundPosition: `${-s.c.in / s.c.speed * pps}px 0` };
      }
      return html`<div key=${s.c.id} class=${cx("thq-ed-item is-clip", sel && sel.type === "clip" && sel.id === s.c.id && "is-sel", dragIdx === i && "is-drag")}
        style=${{ left: `${s.start * pps}px`, width: `${Math.max(4, wpx)}px`, ...bg }} onPointerDown=${(e) => clipDown(e, s, i)} onClick=${(e) => pick(e, "clip", s.c.id)}>
        <i class="thq-ed-h is-l" onPointerDown=${(e) => clipDown(e, s, i, "l")}></i>
        <span class="thq-ed-cl">${s.c.muted && ED_ICON.mute}${s.c.speed !== 1 ? `${s.c.speed}× · ` : ""}${!s.c.muted && Math.abs((s.c.volume ?? 1) - 1) > 0.01 ? `${fmtDb(s.c.volume)} · ` : ""}${fmtT(s.end - s.start, true)}</span>
        ${s.c.kind !== "image" && volLine("clip", s.c)}
        <i class="thq-ed-h is-r" onPointerDown=${(e) => clipDown(e, s, i, "r")}></i></div>`;
    })}
    ${segs.slice(0, -1).map((s, i) => {          // cięcie: okno przejścia (pasek) i przycisk wyboru
      const tr = trsOsi[i], on = sel && sel.type === "tr" && sel.id === s.c.id;
      return html`${tr && html`<i key=${`w${s.c.id}`} class="thq-ed-trw" style=${{ left: `${(s.end - tr.d / 2) * pps}px`, width: `${tr.d * pps}px` }}></i>`}
        <button type="button" key=${`t${s.c.id}`} class=${cx("thq-ed-trb", tr && "is-set", on && "is-sel")} style=${{ left: `${s.end * pps}px` }}
          onPointerDown=${(e) => e.stopPropagation()} onClick=${(e) => pick(e, "tr", s.c.id)}
          title=${tr ? `${L("Przejście", "Transition")}: ${trNazwa(tr.type)} · ${fmtSek(tr.d)}` : L("Dodaj przejście", "Add a transition")}
          aria-label=${tr ? `${L("Przejście", "Transition")}: ${trNazwa(tr.type)}` : L("Dodaj przejście", "Add a transition")}>${tr ? ED_ICON.trans : ED_ICON.plus}</button>`;
    })}
    ${mobile && html`<button type="button" class="thq-ed-addclip" style=${{ left: `${total * pps + 8}px` }} onClick=${(e) => { e.stopPropagation(); setSel(null); setTool("media"); }}
      aria-label=${L("Dodaj klip", "Add clip")}>${ED_ICON.plus}</button>`}
  </div>`;
  const audioTrack = html`<div class="thq-ed-track is-audio" onPointerDown=${rulerDown} onClick=${() => mobile && setSel(null)}>
    ${mobile && html`<button type="button" class="thq-ed-lane" onPointerDown=${(e) => e.stopPropagation()} onClick=${(e) => { e.stopPropagation(); setSel(null); setTool("audio"); }} aria-label=${L("Audio", "Audio")}>${ED_ICON.audio}</button>`}
    ${p.audio.map((m) => {
      const w = waves[m.src];
      const wave = w && w.url ? { backgroundImage: `url(${w.url})`, backgroundSize: `${w.dur * pps}px 100%`, backgroundPosition: `${-m.in * pps}px 0`, backgroundRepeat: "no-repeat" } : {};
      return html`<div key=${m.id} class=${cx("thq-ed-item is-audio", sel && sel.id === m.id && "is-sel")}
      style=${{ left: `${m.start * pps}px`, width: `${Math.max(6, audioDur(m) * pps)}px`, ...wave }} onPointerDown=${(e) => audioDown(e, m)} onClick=${(e) => pick(e, "audio", m.id)}>
      <i class="thq-ed-h is-l" onPointerDown=${(e) => audioDown(e, m, "l")}></i><span>${(meta[m.src] || {}).name || ""}${Math.abs(m.volume - 1) > 0.01 ? ` · ${fmtDb(m.volume)}` : ""}</span>${volLine("audio", m)}
      <i class="thq-ed-h is-r" onPointerDown=${(e) => audioDown(e, m, "r")}></i></div>`;
    })}
    ${!p.audio.length && (mobile
      ? html`<button type="button" class="thq-ed-add" style=${{ left: `${t * pps}px` }} onClick=${(e) => { e.stopPropagation(); setSel(null); setTool("audio"); }}>${ED_ICON.plus}${L("Dodaj audio", "Add audio")}</button>`
      : html`<span class="thq-ed-hint">${L("Muzyka: dodaj plik audio z panelu Media", "Music: add an audio file from the Media panel")}</span>`)}
  </div>`;
  const speechTrack = hasSpeech && html`<div class="thq-ed-track is-speech" onPointerDown=${rulerDown} onClick=${() => mobile && setSel(null)}>
    ${bars.map((b, i) => html`<div key=${`b${i}`} class="thq-ed-bar-say" style=${{ left: `${b.t0 * pps}px`, width: `${Math.max(2, (b.t1 - b.t0) * pps)}px` }} title=${b.text}><span>${b.text}</span></div>`)}
    ${marks.map((m) => html`<button type="button" key=${m.key} class=${cx("thq-ed-mark", `is-${m.kind}`, sel && sel.id === m.key && "is-sel")}
      style=${{ left: `${m.t0 * pps}px`, width: `${Math.max(6, (m.t1 - m.t0) * pps)}px` }} title=${m.kind === "pause" ? L("Pauza: kliknij, żeby wyciąć", "Pause: click to cut") : `„${m.label}”`}
      onPointerDown=${(e) => e.stopPropagation()} onClick=${(e) => pick(e, "mark", m.key)}>${m.kind === "filler" ? m.label : ""}</button>`)}
  </div>`;
  const timeline = html`<div class="thq-ed-tlwrap">
    <div class="thq-ed-tl" ref=${tlRef} onScroll=${onTlScroll} ...${mobile ? tlTouch : {}}
      onWheel=${(e) => { if (e.ctrlKey) { e.preventDefault(); setPps((x) => clamp(x * (e.deltaY < 0 ? 1.15 : 1 / 1.15), 4, 400)); } }}>
      <div class="thq-ed-tl-in" style=${{ width: `${width}px`, padding: `0 ${pad}px 10px` }}>
        <div class="thq-ed-ruler" onPointerDown=${rulerDown}>
          ${ticks.map((s) => html`<span key=${s} style=${{ left: `${s * pps}px` }}>${step < 1 ? `${edTC(s, false)}${(s % 1 ? ".5" : "")}` : edTC(s, false)}</span>`)}
          ${ticks.map((s) => html`<b key=${`d${s}`} style=${{ left: `${(s + step / 2) * pps}px` }}></b>`)}
        </div>
        ${mobile ? [noteTrack, videoTrack, speechTrack, audioTrack, textTrack, typoTrack] : [noteTrack, typoTrack, textTrack, videoTrack, speechTrack, audioTrack]}
        ${!mobile && html`<div class="thq-ed-head" ref=${headRef} style=${{ left: `${pad}px`, transform: `translateX(${t * pps}px)` }}><i></i></div>`}
      </div>
    </div>
    ${mobile && html`<div class="thq-ed-center"><i></i></div>`}
  </div>`;
  const banner = shot ? html`<div class="thq-ed-banner is-shot" role="status">
      <span>${shot.busy ? L("Zapisuję kadr…", "Saving the frame…") : L("Przeciągnij prostokąt na podglądzie albo kliknij, żeby wziąć cały kadr.", "Drag a box on the preview, or click to take the whole frame.")}</span>
      <button type="button" class="thq-ed-btn" onClick=${() => setShot(null)}>${L("Anuluj", "Cancel")}</button></div>`
    : conflict ? html`<div class="thq-ed-banner" role="alert">
      <span>${conflict.kto === "jarvo-wideo" ? L("Wideograf zmienił ten projekt, a Ty masz niezapisane zmiany.", "The video agent changed this project while you have unsaved changes.")
        : L("Projekt zmienił się poza edytorem.", "The project changed outside the editor.")}</span>
      <button type="button" class="thq-ed-btn is-main" onClick=${() => reloadProject(conflict.kto)}>${L("Wczytaj jego wersję", "Load theirs")}</button>
      <button type="button" class="thq-ed-btn" onClick=${keepMine}>${L("Zostaw moją", "Keep mine")}</button></div>`
    : toast ? html`<div class="thq-ed-banner is-ok" role="status">${ED_ICON.check}<span>${toast}</span></div>` : null;
  const askBox = ask && !shot && html`<${AskAgent} ask=${ask} setAsk=${setAsk} path=${path} saveNow=${saveNow} time=${tRef.current} sel=${sel && selItem ? { ...sel, item: selItem } : null}
    onOpen=${(f) => { onClose(); openFile && openFile(f); }} notes=${notes} addNote=${addNote} removeNote=${removeNote} noteHi=${noteHi}
    onSeek=${(x) => player.seek(x)} startShot=${startShot} urls=${shotUrls}/>`;
  const exportBox = job && html`<${ExportBox} job=${job} onClose=${() => setJob(null)} onOpen=${(f) => { onClose(); openFile && openFile(f); }}/>`;
  const exportBtn = html`<button type="button" class="thq-ed-btn is-main" disabled=${running || !info.ffmpeg} onClick=${doExport}
    title=${info.ffmpeg ? L("Zapisz nową wersję filmu (oryginał zostaje)", "Save a new version (the original stays)") : L("Brak ffmpeg w kontenerze", "ffmpeg is missing in the container")}>${L("Eksportuj", "Export")}</button>`;

  // ---- telefon: układ jak w CapCut
  if (mobile) {
    const TOOLS = [["edit", L("Edytuj", "Edit")], ["audio", L("Audio", "Audio")], ["text", L("Tekst", "Text")], ["captions", L("Napisy", "Captions")], ["speech", L("Mowa", "Speech")], ["format", L("Format", "Format")]];
    const openTool = (k2) => {
      if (tool === k2) { setTool(null); return; }
      if (k2 === "edit" && !(sel && sel.type === "clip")) {
        const s = segs.find((x) => t >= x.start && t < x.end) || segs[segs.length - 1];
        if (s) setSel({ type: "clip", id: s.c.id });
      }
      if (k2 === "text" && !(sel && sel.type === "text")) { addText(); }
      if (k2 === "audio" && !(sel && sel.type === "audio")) setSel(null);
      setTool(k2);
    };
    let sheet = null, title = "";
    if (tool === "edit" && selItem && sel.type === "clip") { sheet = clipTools(selItem); title = L("Klip", "Clip"); }
    else if (tool === "text" && selItem && sel.type === "text") { sheet = textTools(selItem); title = selItem.cap ? L("Napis", "Caption") : L("Tekst", "Text"); }
    else if (tool === "audio") { sheet = selItem && sel.type === "audio" ? audioTools(selItem) : audioAdd(); title = L("Audio", "Audio"); }
    else if (tool === "captions") { sheet = captionTools(); title = L("Napisy", "Captions"); }
    else if (tool === "speech") { sheet = speechTools(); title = L("Mowa, pauzy i wtrącenia", "Speech, pauses and fillers"); }
    else if (tool === "mark" && markSel) { sheet = markTools(markSel); title = L("Znacznik", "Mark"); }
    else if (tool === "typo" && selItem && sel.type === "typo") { sheet = typoTools(selItem); title = L("Typografia", "Typography"); }
    else if (tool === "tr" && selItem && sel.type === "tr") { sheet = trTools(selItem); title = L("Przejście", "Transition"); }
    else if (tool === "format") { sheet = formatTools(); title = L("Format", "Format"); }
    else if (tool === "media") { sheet = html`<div class="thq-ed-form">${mediaList(["video", "image"])}${uploadBtn("video/*,image/png,image/jpeg,image/webp")}</div>`; title = L("Dodaj klip", "Add clip"); }
    return html`<div class=${cx("thq-ed is-mobile", sheet && "has-sheet")} role="dialog" aria-modal="true" aria-label=${L("Edytor filmu", "Video editor")}>
      <header class="thq-ed-top">
        <button type="button" class="thq-ed-ico" onClick=${() => { player.stop(); onClose(); }} aria-label=${L("Zamknij edytor", "Close the editor")}>${ED_ICON.close}</button>
        <span class="thq-ed-saved">${saved}</span>
        <span class="thq-ed-grow"></span>
        <button type="button" class=${cx("thq-ed-pill", ask && "is-on")} onClick=${() => setAsk(ask ? null : { text: "", reply: "", busy: false })} aria-label=${L("Poproś agenta", "Ask the agent")}>${ED_ICON.spark}<span>${L("Agent", "Agent")}</span></button>
        ${exportBtn}
      </header>
      ${askBox}${banner}
      <section class="thq-ed-stage-wrap">${stage}</section>
      <div class="thq-ed-transport">
        <span class="thq-ed-time"><span ref=${timeRef}>${edTC(t)}</span><span class="thq-ed-dur"> / ${edTC(total)}</span></span>
        <button type="button" class="thq-ed-play" onClick=${player.toggle} aria-label=${player.playing ? L("Pauza", "Pause") : L("Odtwórz", "Play")}>${player.playing ? ED_ICON.pause : ED_ICON.play}</button>
        <span class="thq-ed-undo">
          <button type="button" class="thq-ed-ico" disabled=${!H.canUndo} onClick=${H.undo} aria-label=${L("Cofnij", "Undo")}>${ED_ICON.undo}</button>
          <button type="button" class="thq-ed-ico" disabled=${!H.canRedo} onClick=${H.redo} aria-label=${L("Ponów", "Redo")}>${ED_ICON.redo}</button>
        </span>
      </div>
      ${timeline}
      ${sheet && html`<div class="thq-ed-sheet">
        <header><strong>${title}</strong><button type="button" class="thq-ed-ico" onClick=${() => { setTool(null); if (tool !== "captions" && tool !== "format") setSel(null); }} aria-label=${L("Gotowe", "Done")}>${ED_ICON.check}</button></header>
        ${sheet}
      </div>`}
      <nav class="thq-ed-nav">${TOOLS.map(([k2, label]) => html`<button type="button" key=${k2} class=${cx(tool === k2 && "is-on")} onClick=${() => openTool(k2)}>${ED_ICON[k2]}<span>${label}</span></button>`)}</nav>
      ${exportBox}
    </div>`;
  }

  // ---- komputer
  const inspector = () => {
    if (markSel) return markTools(markSel);
    if (!selItem) {
      return html`<div>${formatTools()}
        <div class="thq-ed-form"><p class="thq-ed-note">${L("Kliknij klip, napis albo muzykę na osi, żeby je ustawić.", "Click a clip, text or music on the timeline to adjust it.")}</p>
        <div class="thq-ed-keys">
          <p><kbd>Spacja</kbd> ${L("odtwórz", "play")}</p><p><kbd>S</kbd> ${L("tnij", "split")}</p><p><kbd>T</kbd> ${L("napis", "text")}</p>
          <p><kbd>Del</kbd> ${L("usuń", "delete")}</p><p><kbd>Ctrl Z</kbd> ${L("cofnij", "undo")}</p><p><kbd>Ctrl D</kbd> ${L("duplikuj", "duplicate")}</p>
          <p><kbd>← →</kbd> ${L("klatka", "frame")}</p>
        </div></div></div>`;
    }
    return sel.type === "clip" ? clipTools(selItem) : sel.type === "tr" ? trTools(selItem) : sel.type === "text" ? textTools(selItem)
      : sel.type === "typo" ? typoTools(selItem) : audioTools(selItem);
  };
  return html`<div class="thq-ed" role="dialog" aria-modal="true" aria-label=${L("Edytor filmu", "Video editor")}>
    <header class="thq-ed-top">
      <button type="button" class="thq-ed-ico" onClick=${() => { player.stop(); onClose(); }} title=${L("Zamknij edytor (projekt jest zapisany)", "Close the editor (the project is saved)")} aria-label=${L("Wróć", "Back")}>${ED_ICON.back}</button>
      <strong class="thq-ed-title" title=${path}>${path.split("/").pop()}</strong>
      <span class="thq-ed-saved">${saved}</span>
      <span class="thq-ed-grow"></span>
      <button type="button" class="thq-ed-ico" disabled=${!H.canUndo} onClick=${H.undo} title=${`${L("Cofnij", "Undo")} (Ctrl+Z)`} aria-label=${L("Cofnij", "Undo")}>${ED_ICON.undo}</button>
      <button type="button" class="thq-ed-ico" disabled=${!H.canRedo} onClick=${H.redo} title=${`${L("Ponów", "Redo")} (Ctrl+Shift+Z)`} aria-label=${L("Ponów", "Redo")}>${ED_ICON.redo}</button>
      <span class="thq-ed-sep"></span>
      <button type="button" class=${cx("thq-ed-pill", ask && "is-on")} onClick=${() => setAsk(ask ? null : { text: "", reply: "", busy: false })}>${ED_ICON.spark}<span>${L("Poproś agenta", "Ask the agent")}</span></button>
      ${exportBtn}
    </header>
    ${askBox}${banner}
    <div class="thq-ed-body">
      <aside class="thq-ed-side">
        <div class="thq-ed-tabs">
          <button type="button" class=${cx(side === "media" && "is-on")} onClick=${() => setSide("media")}>${ED_ICON.film}<span>${L("Media", "Media")}</span></button>
          <button type="button" class=${cx(side === "captions" && "is-on")} onClick=${() => setSide("captions")}>${ED_ICON.captions}<span>${L("Napisy", "Captions")}</span></button>
          <button type="button" class=${cx(side === "speech" && "is-on")} onClick=${() => setSide("speech")}>${ED_ICON.speech}<span>${L("Mowa", "Speech")}</span></button>
          <button type="button" class=${cx(side === "inspect" && "is-on")} onClick=${() => setSide("inspect")}>${ED_ICON.sliders}<span>${L("Ustawienia", "Settings")}</span></button>
        </div>
        ${side === "media" ? html`<div class="thq-ed-media">
          <button type="button" class="thq-ed-btn is-wide" onClick=${addText}>${ED_ICON.text} ${L("Dodaj napis", "Add text")}</button>
          ${uploadBtn("video/*,audio/*,image/png,image/jpeg,image/webp")}
          <p class="thq-ed-note">${L("Z katalogu filmu", "From the film's folder")}</p>
          ${mediaList(["video", "image", "audio"])}
          ${act(allMuted ? "mute" : "volume", allMuted ? L("Włącz dźwięk filmu", "Unmute video") : L("Wycisz dźwięk filmu", "Mute video audio"),
            () => H.apply((P) => ({ ...P, clips: P.clips.map((c) => ({ ...c, muted: !allMuted })) })), { on: allMuted })}
        </div>` : side === "captions" ? captionTools() : side === "speech" ? speechTools() : inspector()}
      </aside>
      <section class="thq-ed-stage-wrap">
        ${stage}
        <div class="thq-ed-transport">
          <button type="button" class="thq-ed-play" onClick=${player.toggle} aria-label=${player.playing ? L("Pauza", "Pause") : L("Odtwórz", "Play")}>${player.playing ? ED_ICON.pause : ED_ICON.play}</button>
          <span class="thq-ed-time"><span ref=${timeRef}>${edTC(t)}</span><span class="thq-ed-dur"> / ${edTC(total)}</span></span>
        </div>
      </section>
    </div>
    <div class="thq-ed-tools">
      <button type="button" class="thq-ed-tool" onClick=${split} title=${`${L("Tnij", "Split")} (S)`}>${ED_ICON.split}<span>${L("Tnij", "Split")}</span></button>
      <button type="button" class="thq-ed-tool" onClick=${addText} title=${`${L("Napis", "Text")} (T)`}>${ED_ICON.text}<span>${L("Napis", "Text")}</span></button>
      <button type="button" class="thq-ed-tool" disabled=${!sel || sel.type === "tr"} onClick=${duplicate} title=${`${L("Duplikuj", "Duplicate")} (Ctrl+D)`}>${ED_ICON.copy}<span>${L("Duplikuj", "Duplicate")}</span></button>
      <button type="button" class="thq-ed-tool" disabled=${!sel || (sel.type === "clip" && p.clips.length <= 1)} onClick=${remove} title=${`${L("Usuń", "Delete")} (Del)`}>${ED_ICON.trash}<span>${L("Usuń", "Delete")}</span></button>
      <span class="thq-ed-grow"></span>
      <button type="button" class="thq-ed-ico is-sm" onClick=${() => setPps((x) => clamp(x / 1.4, 4, 400))} aria-label=${L("Oddal", "Zoom out")} title=${L("Oddal", "Zoom out")}>${ED_ICON.minus}</button>
      <button type="button" class="thq-ed-ico is-sm" onClick=${fitZoom} aria-label=${L("Cała oś", "Fit")} title=${L("Cała oś", "Fit")}>${ED_ICON.fit}</button>
      <button type="button" class="thq-ed-ico is-sm" onClick=${() => setPps((x) => clamp(x * 1.4, 4, 400))} aria-label=${L("Przybliż", "Zoom in")} title=${L("Przybliż", "Zoom in")}>${ED_ICON.plus}</button>
    </div>
    ${timeline}
    ${exportBox}
  </div>`;
}

// Karty stylów typografii: blok filmu (z uderzeniem; bez planu przykład) w każdym motywie na kadrze z podglądu,
// narysowany tym samym rendererem co podgląd i eksport. Klik zmienia motyw całego filmu (układ i kolory zostają).
const TYPO_KARTA = [480, 300];   // piksele kanwy karty (2× wielkość na ekranie)
function typoProbka(P) {
  const ocena = (b) => {    // bez ręcznego kroju i stylu (nie zmieniają się z motywem), z uderzeniem, różne wagi
    const w = new Set(b.slowa.map((x) => Math.round(+x.waga || 0)));
    return (b.slowa.some((x) => x.kroj || x.styl) ? 0 : 1000) + (w.has(3) ? 100 : 0) + w.size * 10 + Math.min(b.slowa.length, 4);
  };
  const b = typoBloki(P).filter((x) => x.warstwa !== "tyl" && x.slowa.length <= 5).reduce((a, x) => (!a || ocena(x) > ocena(a) ? x : a), null);
  const slowa = b ? b.slowa : [{ tekst: L("to", "it"), waga: 0, linia: 0 }, { tekst: L("działa", "works"), waga: 1, linia: 0 }, { tekst: L("świetnie", "great"), waga: 3, linia: 1 }];
  return { id: "styl", start: 0, end: 10, uklad: "srodek", x: 0.5, y: 0.5, w: 0.9, rozmiar: 1.75, warstwa: "przod",   // na całą kartę
    zrodloY: b ? +b.y || 0.5 : 0.5, slowa: slowa.map((x) => ({ ...x, t: 0, k: 0.2 })) };
}
function TypoStyle({ P, klatka, onPick }) {
  const T = P.typo || {}, cur = TYPO_MOTYWY[T.motyw] ? T.motyw : "czysty";
  const probka = typoProbka(P);
  const klucz = JSON.stringify([probka.slowa, T.akcent || "", T.paleta || []]);
  const [tlo, setTlo] = useState(null);
  useEffect(() => {        // tło kart: pas klatki podglądu na wysokości bloku (kontrast jak w filmie)
    const f = klatka();
    if (!f) return;
    const [W, H] = TYPO_KARTA, c = document.createElement("canvas");
    c.width = W; c.height = H;
    const k = Math.max(W / f.vw, H / f.vh), sh = H / k;
    const sy = typoClamp(probka.zrodloY * f.vh - sh / 2, 0, f.vh - sh);
    try { c.getContext("2d").drawImage(f.el, (f.vw - W / k) / 2, sy, W / k, sh, 0, 0, W, H); setTlo(c); } catch (_) { /* klatka niegotowa: szare tło */ }
  }, [cur]);
  return html`<div class="thq-ed-style" role="group" aria-label=${L("Styl filmu", "Film style")}>${Object.keys(TYPO_MOTYWY).map((k) => html`<${TypoStylKarta}
    key=${k} k=${k} T=${T} probka=${probka} klucz=${klucz} tlo=${tlo} on=${k === cur} onPick=${onPick}/>`)}</div>`;
}
function TypoStylKarta({ k, T, probka, klucz, tlo, on, onPick }) {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return undefined;
    let alive = true;
    const [W, H] = TYPO_KARTA;
    const Pk = { typo: { ...T, motyw: k, bloki: [probka] } };
    const draw = () => {
      if (!alive) return;
      if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
      const g = c.getContext("2d");
      g.fillStyle = "#3a3d42"; g.fillRect(0, 0, W, H);
      if (tlo) g.drawImage(tlo, 0, 0, W, H);
      typoRysuj(g, Pk, W, H, 1);
    };
    draw();
    Promise.all(typoFonty(Pk, W, H).map(([f, t]) => fontLoad(f, t))).then(draw);
    return () => { alive = false; };
  }, [k, klucz, tlo]);
  return html`<button type="button" class=${cx("thq-ed-styl", on && "is-on")} aria-pressed=${on} onClick=${() => onPick(k)}>
    <canvas ref=${ref}></canvas><span>${L(...TYPO_MOTYWY[k].nazwa)}</span></button>`;
}

function EdAudio({ m, audios }) {
  const ref = useRef(null);
  const [url, setUrl] = useState(null);
  useEffect(() => { let alive = true; mediaUrl(m.src).then((u) => alive && setUrl(u)).catch(() => {}); return () => { alive = false; }; }, [m.src]);
  useEffect(() => { if (ref.current) audios.current.set(m.id, ref.current); return () => audios.current.delete(m.id); }, [m.id, url]);
  return url ? html`<audio ref=${ref} src=${url} preload="auto"></audio>` : null;
}

function ExportBox({ job, onClose, onOpen }) {
  const pct = Math.round((job.progress || 0) * 100);
  const done = job.state === "done", bad = job.state === "error" || job.state === "cancelled";
  const file = done ? { ...fileFromPath(job.out), size: job.size } : null;
  return html`<div class="thq-ed-export" role="status">
    ${!done && !bad && html`<p><strong>${job.state === "prep" ? (job.progress ? L(`Rysuję typografię ${pct}%`, `Drawing typography ${pct}%`) : L("Przygotowuję napisy…", "Preparing texts…")) : L(`Eksport ${pct}%`, `Exporting ${pct}%`)}</strong></p>
      <div class="thq-ed-bar"><i style=${{ width: `${pct}%` }}></i></div>
      ${job.id && html`<button type="button" class="thq-ed-btn" onClick=${() => api.editCancel(job.id).catch(() => {})}>${L("Przerwij", "Cancel")}</button>`}`}
    ${done && html`<p class="thq-ed-subi">${ED_ICON.check}<span><strong>${L("Gotowe", "Done")}</strong> · ${file.name} · ${bytes(job.size)}</span></p>
      <div class="thq-ed-row"><button type="button" class="thq-ed-btn is-main" onClick=${() => onOpen(file)}>${L("Obejrzyj", "Watch")}</button>
        <button type="button" class="thq-ed-btn" onClick=${() => downloadFile(file)}>${L("Pobierz", "Download")}</button>
        <button type="button" class="thq-ed-btn is-ghost" onClick=${onClose}>${L("Edytuj dalej", "Keep editing")}</button></div>`}
    ${bad && html`<p class="thq-ed-bad">${job.state === "cancelled" ? L("Przerwano eksport.", "Export cancelled.") : `${L("Eksport nie wyszedł", "Export failed")}: ${job.error || ""}`}</p>
      <button type="button" class="thq-ed-btn" onClick=${onClose}>OK</button>`}
  </div>`;
}

// Prośba do Wideografa z kontekstem montażu: agent widzi film, projekt i miejsce na osi.
// Miniatura kadru uwagi: obraz z tej sesji albo plik z inboxu (po ponownym otwarciu edytora).
function NoteThumb({ path, url }) {
  const disk = useBlobUrl(url ? null : path);
  const src = url || disk;
  return src ? html`<img src=${src} alt=${L("Kadr uwagi", "Note frame")}/>` : html`<span class="thq-ed-note-pic" title=${path}>${ED_ICON.camera}</span>`;
}
function AskAgent({ ask, setAsk, path, saveNow, time, sel, onOpen, notes, addNote, removeNote, noteHi, onSeek, startShot, urls }) {
  const open = openNotes(notes);
  const where = sel ? (sel.type === "text" ? `napis „${sel.item.text}” (${fmtT(sel.item.start, true)}–${fmtT(sel.item.end, true)})`
    : sel.type === "typo" ? `blok typografii ${sel.item.id} „${typoTekst(sel.item)}” (${fmtT(sel.item.start, true)}–${fmtT(sel.item.end, true)}${sel.item.warstwa === "tyl" ? ", za osobą" : ""})`
    : sel.type === "clip" ? `klip ${sel.item.src.split("/").pop()} (${fmtT(sel.item.in, true)}–${fmtT(sel.item.out, true)} źródła)`
    : sel.type === "tr" ? `cięcie po klipie ${sel.item.id} (${sel.item.src.split("/").pop()}), przejście: ${sel.item.transition ? `${sel.item.transition.type}, ${sel.item.transition.dur ?? ED_PRZ_D} s` : "brak"}`
    : `muzyka ${sel.item.src.split("/").pop()}`) : "nic";
  const text = (ask.text || "").trim();
  const canSend = !ask.busy && (text || open.length || ask.shot);
  const send = async () => {
    if (!canSend) return;
    const { message, attachments, images } = askMessage({ path, cursor: time, where, text, shot: ask.shot, notes, urls: (x) => urls.current.get(x) });
    setAsk((a) => ({ ...a, busy: true, reply: "", error: null }));
    try {
      await saveNow().catch(() => {});
      const extra = attachments.length ? { attachments, images } : undefined;
      for await (const { event, data } of api.send(ED_AGENT, message, extra)) {
        if (event === "assistant.delta") setAsk((a) => a && { ...a, reply: (a.reply || "") + (data.delta || "") });
        else if (event === "assistant.completed" && typeof data.content === "string") setAsk((a) => a && { ...a, reply: data.content });
        else if (event === "run.failed" || event === "error") setAsk((a) => a && { ...a, error: data.message || data.error || "błąd" });
      }
      setAsk((a) => a && { ...a, text: "", shot: null });
    } catch (e) { setAsk((a) => a && { ...a, error: e.message || String(e) }); }
    setAsk((a) => a && { ...a, busy: false });
  };
  const pin = () => {
    if (!text && !ask.shot) return;
    addNote(text, ask.shot && ask.shot.path);
    setAsk((a) => ({ ...a, text: "", shot: null }));
  };
  const vids = [...new Set(((ask.reply || "").match(/\/opt\/data\/jarvo\/(?:workspaces|missions|knowledge|inbox)\/[^\s`'"<>()]+\.(?:mp4|webm|mov)/g) || []))];
  const sorted = [...(notes || [])].sort((a, b) => a.t - b.t);
  return html`<div class="thq-ed-ask">
    <header class="thq-ed-pop-head"><strong>${ED_ICON.spark}${L("Poproś Wideografa", "Ask the video agent")}</strong>
      <button type="button" class="thq-ed-ico is-sm" onClick=${() => setAsk(null)} aria-label=${L("Zamknij", "Close")}>${ED_ICON.close}</button></header>
    <p class="thq-ed-note">${L("Dostanie film, projekt montażu, miejsce na osi, uwagi i kadry. Uwaga przypina prośbę do chwili filmu, kadr dołącza zaznaczony fragment podglądu.",
      "It gets the film, the edit project, your timeline position, notes and frames. A note pins a request to a moment; a frame attaches part of the preview.")}</p>
    ${sorted.length > 0 && html`<ol class="thq-ed-notes">${sorted.map((n) => html`<li key=${n.id} class=${cx(n.done && "is-done", noteHi === n.id && "is-sel")}>
      <button type="button" class="thq-ed-note-t" onClick=${() => onSeek(n.t)} title=${L("Przejdź do tego miejsca", "Go to this moment")}>${edClock(n.t)}</button>
      <span class="thq-ed-note-x">${n.text || L("(kadr)", "(frame)")}${n.done && html`<small>${ED_ICON.check}${n.odp || L("zrobione", "done")}</small>`}</span>
      ${n.img && html`<${NoteThumb} path=${n.img} url=${urls.current.get(n.img)}/>`}
      <button type="button" class="thq-ed-note-del" onClick=${() => removeNote(n.id)} aria-label=${L("Usuń uwagę", "Remove note")}>${ED_ICON.close}</button></li>`)}</ol>`}
    <textarea rows="2" value=${ask.text} placeholder=${L("Co zmienić? Np. „tu za szybko”, „literówka w napisie”, „dodaj lektora”.", "What should change? E.g. “too fast here”, “typo in the caption”, “add a voice-over”.")}
      onInput=${(e) => { const v = e.target.value; setAsk((a) => ({ ...a, text: v })); }}
      onKeyDown=${(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}></textarea>
    ${ask.shot && html`<div class="thq-ed-shotprev"><img src=${ask.shot.url} alt=${L("Kadr", "Frame")}/>
      <span>${L("Kadr", "Frame")} ${edClock(ask.shot.t)}${ask.shot.full ? "" : L(" · fragment", " · crop")}</span>
      <button type="button" class="thq-ed-note-del" onClick=${() => setAsk((a) => ({ ...a, shot: null }))} aria-label=${L("Usuń kadr", "Remove frame")}>${ED_ICON.close}</button></div>`}
    <div class="thq-ed-row is-actions">
      <button type="button" class="thq-ed-btn" onClick=${startShot} disabled=${ask.busy}>${ED_ICON.camera}${L("Kadr", "Frame")}</button>
      <button type="button" class="thq-ed-btn" onClick=${pin} disabled=${ask.busy || (!text && !ask.shot)}
        title=${L("Zapisz jako uwagę w tym miejscu osi (wyślesz kilka naraz)", "Save as a note at this moment (send several at once)")}>${ED_ICON.pin}${L("Uwaga w", "Note at")} ${edClock(time)}</button>
      <span class="thq-ed-grow"></span>
      <button type="button" class="thq-ed-btn is-main" disabled=${!canSend} onClick=${send}>${ask.busy ? "…"
        : open.length ? L(`Wyślij (${open.length} ${plForma(open.length, ["uwaga", "uwagi", "uwag"])})`, `Send (${open.length} note${open.length === 1 ? "" : "s"})`) : L("Wyślij", "Send")}</button>
    </div>
    ${(ask.reply || ask.busy) && html`<div class="thq-ed-reply"><${Markdown} text=${ask.reply || L("Wideograf pracuje…", "Working…")}/></div>`}
    ${ask.error && html`<p class="thq-ed-bad">${ask.error}</p>`}
    ${vids.map((v) => html`<button key=${v} type="button" class="thq-ed-btn" onClick=${() => onOpen(fileFromPath(v))}>${ED_ICON.film}${v.split("/").pop()}</button>`)}
  </div>`;
}
