// Edytor filmów (styl CapCut): podgląd, oś czasu z miniaturami, napisy, muzyka, eksport ffmpeg na serwerze.
// Bez bibliotek: dwa elementy <video> na zmianę (płynne przejścia między klipami), napisy rysowane na
// kanwie tą samą funkcją w podglądzie i przy eksporcie (PNG na napis), więc plik wygląda jak podgląd.

const EditCtx = React.createContext(null);
const ED_AGENT = "jarvo-wideo";
const ED_SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4];
const ED_FORMATS = [
  ["orig", "Oryginał", "Original"], ["16:9", "16:9 · YouTube", "16:9 · YouTube"], ["9:16", "9:16 · Reels/TikTok", "9:16 · Reels/TikTok"],
  ["1:1", "1:1 · kwadrat", "1:1 · square"], ["4:5", "4:5 · post", "4:5 · post"],
];
const ED_SIZES = { "16:9": [1920, 1080], "9:16": [1080, 1920], "1:1": [1080, 1080], "4:5": [1080, 1350] };

const ED_STYLES = [["shadow", "Cień", "Shadow"], ["box", "Tło", "Box"], ["outline", "Obrys", "Outline"], ["plain", "Zwykły", "Plain"]];
const ED_MIN = 0.1;
const ED_COLORS = ["#FFFFFF", "#000000", "#FFD60A", "#FF453A", "#32D74B", "#0A84FF", "#BF5AF2", "#FF9F0A"];
const ED_CAP = { x: 0.5, y: 0.84, size: 58, color: "#FFFFFF", bg: "#000000", style: "outline", bold: true, align: "center", maxw: 0.84,
  font: "'Bricolage Grotesque', system-ui, sans-serif" };
const ED_HL = "#FFE14D";   // domyślny kolor aktywnego słowa (karaoke)
const plNapisy = (n) => (n === 1 ? "napis" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "napisy" : "napisów");
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
  speed: svgI(html`<path d="M12 14l4-4"/><path d="M3.3 17a9 9 0 1 1 17.4 0"/>`),
  volume: svgI(html`<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>`),
  mute: svgI(html`<path d="M11 5 6 9H3v6h3l5 4z"/><path d="m16 9 6 6M22 9l-6 6"/>`),
  crop: svgI(html`<path d="M6 2v16h16M2 6h16v16"/>`),
  copy: svgI(html`<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>`),
  trash: svgI(html`<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>`),
  speech: svgI(html`<path d="M3 12h2M7 8v8M11 5v14M15 9v6M19 7v10M21 12h0"/>`),
  upload: svgI(html`<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>`),
};
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
const clipDur = (c) => (c.out - c.in) / (c.speed || 1);
const audioDur = (m) => m.out - m.in;
function fmtT(s, fine) {
  s = Math.max(0, s || 0);
  const m = Math.floor(s / 60), r = s - m * 60;
  return fine ? `${m}:${r.toFixed(2).padStart(5, "0")}` : `${m}:${String(Math.floor(r)).padStart(2, "0")}`;
}
function layoutClips(clips) {
  let t = 0;
  return clips.map((c) => { const s = t; t += clipDur(c); return { c, start: s, end: t }; });
}
const projTotal = (p) => p.clips.reduce((a, c) => a + clipDur(c), 0);

async function textPng(t, W, H, hi = -1) {
  try { await document.fonts.load(textFont(t, H, W).font); } catch (_) { /* czcionka systemowa */ }
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
  const commit = useCallback(() => setH((s) => {
    const b = base.current; base.current = null;
    if (!b || b === s.present) return s;
    return { past: [...s.past.slice(-99), b], present: s.present, future: [] };
  }), []);
  const undo = useCallback(() => setH((s) => (s.past.length ? { past: s.past.slice(0, -1), present: s.past[s.past.length - 1], future: [s.present, ...s.future] } : s)), []);
  const redo = useCallback(() => setH((s) => (s.future.length ? { past: [...s.past, s.present], present: s.future[0], future: s.future.slice(1) } : s)), []);
  const reset = useCallback((p) => setH({ past: [], present: p, future: [] }), []);
  return { p: h.present, apply, live, commit, undo, redo, reset, canUndo: h.past.length > 0, canRedo: h.future.length > 0 };
}

// ------------------------------------------------------------------ odtwarzacz: dwa <video> na zmianę
function usePlayer(proj, meta, onTick) {
  const vids = [useRef(null), useRef(null)];
  const imgRef = useRef(null);
  const audios = useRef(new Map());
  const st = useRef({ t: 0, playing: false, slot: 0, idx: -1, loaded: [null, null], last: 0, raf: 0 });
  const projRef = useRef(proj);
  projRef.current = proj;
  const [playing, setPlaying] = useState(false);

  const segs = () => layoutClips(projRef.current.clips);
  const total = () => projTotal(projRef.current);
  const findSeg = (t) => {
    const L = segs();
    for (let i = 0; i < L.length; i++) if (t < L[i].end - 1e-6) return [i, L[i]];
    return L.length ? [L.length - 1, L[L.length - 1]] : [-1, null];
  };
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
  async function load(slot, c, local) {
    const v = vids[slot].current;
    if (!v) return;
    const url = await mediaUrl(c.src);
    if (st.current.loaded[slot] !== url) { v.src = url; st.current.loaded[slot] = url; }
    if (v.readyState < 1) await new Promise((ok) => { v.addEventListener("loadedmetadata", ok, { once: true }); setTimeout(ok, 4000); });
    if (Math.abs(v.currentTime - local) > 0.02) v.currentTime = local;
    v.playbackRate = c.speed || 1;
    v.volume = clamp(c.volume ?? 1, 0, 1);
    v.muted = !!c.muted;
    applyFit(v, c);
  }
  function show(kind, slot) {
    vids.forEach((r, i) => r.current && r.current.classList.toggle("is-on", kind === "video" && i === slot));
    if (imgRef.current) imgRef.current.classList.toggle("is-on", kind === "image");
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
  async function preloadNext(i) {
    const L = segs();
    const n = L[i + 1];
    if (n && n.c.kind !== "image") await load(1 - st.current.slot, n.c, n.c.in);
  }
  async function enter(i, local, play) {
    const L = segs();
    const s = L[i];
    if (!s) return;
    const S = st.current;
    S.idx = i;
    if (s.c.kind === "image") {
      const url = await mediaUrl(s.c.src);
      if (imgRef.current && imgRef.current.getAttribute("src") !== url) imgRef.current.src = url;
      if (imgRef.current) applyFit(imgRef.current, s.c);
      show("image");
      vids.forEach((r) => r.current && r.current.pause());
    } else {
      // gotowy slot (przeładowany wcześniej) = przejście bez mrugnięcia
      const other = 1 - S.slot;
      const ready = vids[other].current && S.loaded[other] === (await mediaUrl(s.c.src)) && Math.abs(vids[other].current.currentTime - local) < 0.08;
      if (ready) S.slot = other;
      await load(S.slot, s.c, local);
      show("video", S.slot);
      vids[1 - S.slot].current && vids[1 - S.slot].current.pause();
      if (play) await vids[S.slot].current.play().catch(() => {});
    }
    preloadNext(i);
  }
  function frame(now) {
    const S = st.current;
    if (!S.playing) return;
    const dt = Math.min(0.1, (now - S.last) / 1000);
    S.last = now;
    const L = segs();
    const s = L[S.idx];
    if (!s) { stop(); return; }
    if (s.c.kind === "image") S.t += dt;
    else {
      const v = vids[S.slot].current;
      S.t = s.start + (v.currentTime - s.c.in) / (s.c.speed || 1);
      if (v.ended) S.t = s.end;
    }
    if (S.t >= s.end - 0.01) {
      if (S.idx + 1 >= L.length) { S.t = total(); stop(); onTick(S.t, true); return; }
      S.t = s.end;
      const i = S.idx + 1;
      S.idx = i;
      enter(i, L[i].c.in, true);
    }
    syncAudio(S.t, true);
    onTick(S.t, false);
    S.raf = requestAnimationFrame(frame);
  }
  function stop() {
    const S = st.current;
    S.playing = false;
    cancelAnimationFrame(S.raf);
    vids.forEach((r) => r.current && r.current.pause());
    syncAudio(S.t, false);
    setPlaying(false);
  }
  async function seek(t) {
    const S = st.current;
    S.t = clamp(t, 0, Math.max(0, total() - 0.001));
    onTick(S.t, false);            // kursor i czas od razu, klatka dociąga się w tle
    const [i, s] = findSeg(S.t);
    if (s) await enter(i, s.c.in + (S.t - s.start) * (s.c.speed || 1), S.playing);
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
  const toggle = () => (st.current.playing ? stop() : play());
  // nowe elementy <video> (np. przełączenie układu telefon/komputer): zapomnij stare źródła
  const remount = () => { st.current.loaded = [null, null]; st.current.idx = -1; };
  useEffect(() => () => { cancelAnimationFrame(st.current.raf); }, []);
  return { vids, imgRef, audios, st, playing, play, stop, toggle, seek, remount };
}

// ------------------------------------------------------------------ edytor
function initialProject(file) {
  const w = file.w || 1920, h = file.h || 1080;
  return {
    version: 1, format: "orig", canvas: { w: even(w), h: even(h), fps: [24, 25, 30, 50, 60].reduce((a, f) => (Math.abs(f - (file.fps || 30)) < Math.abs(a - (file.fps || 30)) ? f : a), 30) },
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

function VideoEditor({ path, onClose }) {
  const openFile = React.useContext(FileCtx);
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState(null);
  const [meta, setMeta] = useState({});
  const [strips, setStrips] = useState({});
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
      return proj;
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
      if (conflict) return;
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

  const onTick = useCallback((time, commitState) => {
    tRef.current = time;
    if (headRef.current) headRef.current.style.transform = `translateX(${time * ppsRef.current}px)`;
    const tl = tlRef.current;
    if (mobileRef.current && tl) {
      // telefon: oś przesuwa się pod wskaźnikiem na środku (jak w CapCut)
      const x = time * ppsRef.current;
      if (Math.abs(tl.scrollLeft - x) > 1) { autoScroll.current = x; tl.scrollLeft = x; autoScroll.current = tl.scrollLeft; }
    }
    if (timeRef.current) timeRef.current.textContent = fmtT(time, true);
    drawOverlay();
    if (commitState) setT(time);
  }, []);
  const ppsRef = useRef(pps);
  ppsRef.current = pps;
  const player = usePlayer(p || { clips: [], texts: [], audio: [] }, meta, onTick);
  const projRef = useRef(p);
  projRef.current = p;
  const selRef = useRef(sel);
  selRef.current = sel;

  function drawOverlay() {
    const c = overlayRef.current, P = projRef.current;
    if (!c || !P) return;
    const { w, h } = P.canvas;
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    const g = c.getContext("2d");
    g.clearRect(0, 0, w, h);
    const now = tRef.current;
    for (const x of P.texts) {
      if (now < x.start || now >= x.end) continue;
      const b = drawText(g, x, w, h, karaokeIndex(x, now));
      const s = selRef.current;
      if (s && s.type === "text" && s.id === x.id) {
        g.save(); g.strokeStyle = "#3BA9FF"; g.lineWidth = Math.max(2, w / 480); g.setLineDash([w / 90, w / 140]);
        g.strokeRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0); g.restore();
      }
    }
  }
  useEffect(() => { drawOverlay(); }, [p, sel]);

  // ---------------------------------------------------------------- kadr do Wideografa i uwagi na osi
  // Kadr składamy jak podgląd: klatka w tym samym kadrze (fitBox = applyFit) i napisy tą samą funkcją drawText.
  async function captureFrame(a, b) {
    const P = projRef.current;
    const { w: W, h: Hh } = P.canvas;
    const c = document.createElement("canvas");
    c.width = W; c.height = Hh;
    const g = c.getContext("2d");
    g.fillStyle = "#000"; g.fillRect(0, 0, W, Hh);
    const now = tRef.current;
    const L2 = layoutClips(P.clips);
    const seg = L2.find((x) => now < x.end - 1e-6) || L2[L2.length - 1];
    const el = seg && seg.c.kind === "image" ? player.imgRef.current : player.vids[player.st.current.slot].current;
    const vw = el && (el.videoWidth || el.naturalWidth), vh = el && (el.videoHeight || el.naturalHeight);
    if (vw && vh) {
      const r = fitBox(vw, vh, W, Hh, seg.c);
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
  const selItem = !p || !sel ? null : (sel.type === "clip" ? p.clips : sel.type === "text" ? p.texts : p.audio).find((x) => x.id === sel.id) || null;

  // ---------------------------------------------------------------- operacje
  const upd = (type, id, patch, liveMode) => (liveMode ? H.live : H.apply)((P) => {
    const key = type === "clip" ? "clips" : type === "text" ? "texts" : "audio";
    return { ...P, [key]: P[key].map((x) => (x.id === id ? { ...x, ...(typeof patch === "function" ? patch(x) : patch) } : x)) };
  });
  const setCanvas = (format) => H.apply((P) => {
    const f = meta[path] || {};
    const [w, h] = format === "orig" ? [even(f.w || 1920), even(f.h || 1080)] : ED_SIZES[format];
    return { ...P, format, canvas: { ...P.canvas, w, h } };
  });
  function split() {
    if (!p) return;
    const now = tRef.current;
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
    H.apply((P) => ({ ...P, clips: P.clips.flatMap((c) => (c.id === s.c.id ? [{ ...c, out: cut }, right] : [c])) }));
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
    const key = sel.type === "clip" ? "clips" : sel.type === "text" ? "texts" : "audio";
    H.apply((P) => ({ ...P, [key]: P[key].filter((x) => x.id !== sel.id) }));
    setSel(null);
  }
  function duplicate() {
    if (!sel || !selItem) return;
    const key = sel.type === "clip" ? "clips" : sel.type === "text" ? "texts" : "audio";
    const copy = { ...selItem, id: edId(sel.type[0]) };
    if (sel.type === "text") { const d = copy.end - copy.start; copy.start = Math.min(copy.end, total - d); copy.end = copy.start + d; }
    if (sel.type === "audio") copy.start = selItem.start + audioDur(selItem);
    H.apply((P) => { const arr = P[key].slice(); arr.splice(arr.findIndex((x) => x.id === sel.id) + 1, 0, copy); return { ...P, [key]: arr }; });
    setSel({ type: sel.type, id: copy.id });
  }
  function addText() {
    const start = clamp(tRef.current, 0, Math.max(0, total - 0.5));
    const x = { id: edId("t"), text: L("Twój tekst", "Your text"), start, end: Math.min(total, start + 3), x: 0.5, y: 0.78, size: 72,
      color: "#FFFFFF", bg: "#000000", style: "shadow", font: ED_FONTS[0][0], bold: true, align: "center", maxw: 0.86 };
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
    const c = { id: edId("c"), src: m.path, kind: m.kind, in: 0, out: m.kind === "image" ? 3 : (m.duration || 3), speed: 1, volume: 1, muted: false, fit: "contain" };
    H.apply((P) => {
      const i = sel && sel.type === "clip" ? P.clips.findIndex((x) => x.id === sel.id) + 1 : P.clips.length;
      const arr = P.clips.slice(); arr.splice(i || P.clips.length, 0, c);
      return { ...P, clips: arr };
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
      const r = await api.editExport(path, { ...p, texts }, pngs, karaoke);
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
    if (!hit) { setSel(null); return; }
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

  // ---------------------------------------------------------------- oś czasu: przeciąganie
  const snapPts = () => {
    const pts = [0, tRef.current, total];
    for (const s of segs) pts.push(s.start, s.end);
    for (const x of p.texts) pts.push(x.start, x.end);
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
    if (edge === "l") drag(e, (d) => upd("clip", c0.id, { in: clamp(c0.in + d * c0.speed, 0, c0.out - ED_MIN) }, true));
    else if (edge === "r") drag(e, (d) => {
      const end = snap(s.start + (c0.out - c0.in) / c0.speed + d, [s.end]);
      upd("clip", c0.id, { out: clamp(c0.in + (end - s.start) * c0.speed, c0.in + ED_MIN, srcDur) }, true);
    });
    else {
      // przestawianie: klip idzie tam, gdzie jest kursor (środek innego klipu = zamiana miejsc)
      const mid = s.start + (s.end - s.start) / 2;
      setDragIdx(i);
      drag(e, (d) => {
        const at = mid + d;
        const L2 = layoutClips(projRef.current.clips);
        const cur = L2.findIndex((x) => x.c.id === c0.id);
        let target = L2.findIndex((x) => at < x.start + (x.end - x.start) / 2);
        if (target < 0) target = L2.length;
        if (target > cur) target -= 1;
        if (target !== cur) H.live((P) => { const arr = P.clips.slice(); const [it] = arr.splice(cur, 1); arr.splice(target, 0, it); return { ...P, clips: arr }; });
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
    setSel({ type, id });
    if (mobileRef.current) setTool(type === "clip" ? "edit" : type);   // "mark" → panel znacznika
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
      ...list.map((k) => ({ ...ED_CAP, ...look, id: edId("t"), cap: true, start: k.start, end: k.end, text: k.text, ...(k.words ? { words: k.words } : {}) }))] }));
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
      pieces.forEach(([x, y], k) => clips.push({ ...s.c, id: k ? edId("c") : s.c.id, in: s.c.in + (x - s.start) * s.c.speed, out: s.c.in + (y - s.start) * s.c.speed }));
    }
    if (!clips.length) return 0;
    const shift = (t) => { let d = 0; for (const [a, b] of rs) { if (t >= b) d += b - a; else if (t > a) d += t - a; } return t - d; };
    H.apply((P) => ({ ...P, clips,
      texts: P.texts.map((x) => ({ ...x, start: shift(x.start), end: shift(x.end) })).filter((x) => x.end - x.start >= 0.05),
      audio: P.audio.map((m) => ({ ...m, start: shift(m.start) })),
      notes: (P.notes || []).map((n) => ({ ...n, t: shift(n.t) })) }));
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
  const allMuted = p.clips.filter((c) => c.kind !== "image").every((c) => c.muted);
  const hasSpeech = p.clips.some((c) => speech[c.src]);
  const speechBusy = !!(speechJob && speechJob.state === "running");
  const marks = hasSpeech ? speechMarks() : [];
  const bars = hasSpeech ? speechBars() : [];
  const markSel = sel && sel.type === "mark" ? marks.find((m) => m.key === sel.id) : null;

  // ---- panele narzędzi (te same na komputerze i telefonie)
  const seg = (items, cur, set) => html`<div class="thq-ed-seg">${items.map(([k2, label]) => html`<button type="button" key=${k2} class=${cx(cur === k2 && "is-on")} onClick=${() => set(k2)}>${label}</button>`)}</div>`;
  const swatches = (cur, set) => html`<div class="thq-ed-sw">${ED_COLORS.map((c) => html`<button type="button" key=${c} class=${cx(String(cur).toLowerCase() === c.toLowerCase() && "is-on")}
    style=${{ background: c }} onClick=${() => set(c)} aria-label=${c}></button>`)}<label class="thq-ed-sw-more" title=${L("Inny kolor", "Other color")}>+<input type="color" value=${cur || "#ffffff"} onInput=${(e) => set(e.target.value, true)} onChange=${H.commit}/></label></div>`;
  const act = (icon, label, fn, opts = {}) => html`<button type="button" class=${cx("thq-ed-act", opts.bad && "is-bad", opts.on && "is-on")} disabled=${opts.disabled} onClick=${fn}>${ED_ICON[icon]}<span>${label}</span></button>`;
  const mediaList = (kinds) => html`<ul class="thq-ed-list">${media.filter((m) => kinds.includes(m.kind)).map((m) => html`<li key=${m.path}><button type="button" onClick=${() => { addMedia(m); if (mobile) setTool(m.kind === "audio" ? "audio" : "edit"); }} title=${L("Dodaj do osi czasu", "Add to the timeline")}>
    <span class=${cx("thq-ed-mk", `is-${m.kind}`)}>${m.kind === "audio" ? "♪" : m.kind === "image" ? "▣" : "▶"}</span>
    <span class="thq-ed-mn">${m.name}</span><span class="thq-ed-md">${m.duration ? fmtT(m.duration) : ""}</span><span class="thq-ed-plus">+</span></button></li>`)}</ul>`;
  const uploadBtn = (accept) => html`<label class="thq-ed-btn is-wide thq-ed-upload">${ED_ICON.upload} ${L("Dodaj z urządzenia", "Add from device")}
    <input type="file" multiple accept=${accept} onChange=${(e) => { uploadMedia(Array.from(e.target.files || [])); e.target.value = ""; }}/></label>`;

  const clipTools = (c) => html`<div class="thq-ed-form">
    <div class="thq-ed-acts">
      ${act("split", L("Tnij", "Split"), split)}
      ${act("copy", L("Duplikuj", "Duplicate"), duplicate)}
      ${c.kind !== "image" && act(c.muted ? "mute" : "volume", c.muted ? L("Włącz dźwięk", "Unmute") : L("Wycisz", "Mute"), () => upd("clip", c.id, { muted: !c.muted }))}
      ${act("crop", c.fit === "cover" ? L("Wypełnij", "Fill") : L("Dopasuj", "Fit"), () => upd("clip", c.id, { fit: c.fit === "cover" ? "contain" : "cover" }), { on: c.fit === "cover" })}
      ${act("trash", L("Usuń", "Delete"), remove, { bad: true, disabled: p.clips.length <= 1 })}
    </div>
    ${c.fit === "cover" && html`<div class="thq-ed-crop">
      <label>${L("Kadr: poziomo", "Frame: horizontal")} · ${Math.round((c.fx ?? 0.5) * 100)}%
        <input type="range" min="0" max="1" step="0.01" value=${c.fx ?? 0.5} onInput=${(e) => upd("clip", c.id, { fx: +e.target.value }, true)} onChange=${H.commit}/></label>
      <label>${L("Kadr: pionowo", "Frame: vertical")} · ${Math.round((c.fy ?? 0.5) * 100)}%
        <input type="range" min="0" max="1" step="0.01" value=${c.fy ?? 0.5} onInput=${(e) => upd("clip", c.id, { fy: +e.target.value }, true)} onChange=${H.commit}/></label>
      <label>${L("Przybliżenie", "Zoom")} · ${(c.zoom ?? 1).toFixed(2)}×
        <input type="range" min="1" max="3" step="0.05" value=${c.zoom ?? 1} onInput=${(e) => upd("clip", c.id, { zoom: +e.target.value }, true)} onChange=${H.commit}/></label>
    </div>`}
    ${c.kind !== "image" && html`<label>${L("Tempo", "Speed")} · ${c.speed}×${seg(ED_SPEEDS.map((s) => [s, `${s}×`]), c.speed, (v) => upd("clip", c.id, { speed: v }))}</label>`}
    ${c.kind !== "image" && html`<label>${L("Głośność", "Volume")} · ${Math.round((c.muted ? 0 : c.volume) * 100)}%
      <input type="range" min="0" max="2" step="0.05" value=${c.volume} onInput=${(e) => upd("clip", c.id, { volume: +e.target.value, muted: false }, true)} onChange=${H.commit}/></label>`}
    ${c.kind === "image" && html`<label>${L("Czas planszy", "Still duration")} · ${(c.out - c.in).toFixed(1)} s
      <input type="range" min="0.5" max="15" step="0.5" value=${c.out - c.in} onInput=${(e) => upd("clip", c.id, { out: c.in + +e.target.value }, true)} onChange=${H.commit}/></label>`}
    <p class="thq-ed-note">${(meta[c.src] || {}).name || c.src.split("/").pop()}${c.kind !== "image" ? ` · ${fmtT(c.in, true)} – ${fmtT(c.out, true)}` : ""}</p>
  </div>`;

  const textTools = (x) => {
    const u = (patch, lv) => upd("text", x.id, patch, lv);
    return html`<div class="thq-ed-form">
      <textarea rows="2" value=${x.text} placeholder=${L("Wpisz tekst", "Type text")} onInput=${(e) => u({ text: e.target.value }, true)} onBlur=${H.commit}></textarea>
      <label>${L("Styl", "Style")}${seg(ED_STYLES.map(([k2, pl, en]) => [k2, L(pl, en)]), x.style, (v) => u({ style: v }))}</label>
      <label>${L("Kolor", "Color")}${swatches(x.color, (v, lv) => u({ color: v }, lv))}</label>
      ${(x.style === "box" || x.style === "outline") && html`<label>${x.style === "box" ? L("Tło", "Box") : L("Obrys", "Outline")}${swatches(x.bg || "#000000", (v, lv) => u({ bg: v }, lv))}</label>`}
      <label>${L("Rozmiar", "Size")} · ${Math.round(x.size)}<input type="range" min="16" max="220" value=${x.size} onInput=${(e) => u({ size: +e.target.value }, true)} onChange=${H.commit}/></label>
      <label>${L("Krój", "Font")}${seg(ED_FONTS.map(([f, n]) => [f, n]), x.font, (v) => u({ font: v }))}</label>
      <div class="thq-ed-row">
        ${seg([["left", "⯇"], ["center", "≡"], ["right", "⯈"]], x.align, (v) => u({ align: v }))}
        <label class="thq-ed-check"><input type="checkbox" checked=${x.bold !== false} onChange=${(e) => u({ bold: e.target.checked })}/> ${L("Gruby", "Bold")}</label>
      </div>
      ${!mobile && html`<label>${L("Szerokość", "Width")} · ${Math.round((x.maxw || 0.86) * 100)}%<input type="range" min="0.2" max="1" step="0.01" value=${x.maxw || 0.86} onInput=${(e) => u({ maxw: +e.target.value }, true)} onChange=${H.commit}/></label>`}
      <p class="thq-ed-note">${fmtT(x.start, true)} – ${fmtT(x.end, true)} · ${L("przeciągnij napis na podglądzie, żeby go przesunąć", "drag the text on the preview to move it")}</p>
      <div class="thq-ed-acts">${act("split", L("Tnij", "Split"), split)}${act("copy", L("Duplikuj", "Duplicate"), duplicate)}${act("trash", L("Usuń", "Delete"), remove, { bad: true })}</div>
    </div>`;
  };

  const audioTools = (m) => html`<div class="thq-ed-form">
    <p class="thq-ed-sub">♪ ${(meta[m.src] || {}).name || m.src.split("/").pop()}</p>
    <label>${L("Głośność", "Volume")} · ${Math.round(m.volume * 100)}%<input type="range" min="0" max="2" step="0.05" value=${m.volume} onInput=${(e) => upd("audio", m.id, { volume: +e.target.value }, true)} onChange=${H.commit}/></label>
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
      <ul class="thq-ed-list">${info.subs.map((f) => html`<li key=${f}><button type="button" onClick=${() => srtCaptions(f)}><span class="thq-ed-mk is-text">CC</span><span class="thq-ed-mn">${f.split("/").pop()}</span><span class="thq-ed-plus">+</span></button></li>`)}</ul>`}
    ${capJob && capJob.state === "error" && html`<p class="thq-ed-bad">${capJob.error}</p>`}
    ${speechJob && speechJob.state === "error" && html`<p class="thq-ed-bad">${speechJob.error}</p>`}
    ${capJob && capJob.state === "done" && html`<p class="thq-ed-ok">✓ ${L(`Dodano ${capJob.n} ${plNapisy(capJob.n)}`, `Added ${capJob.n} captions`)}</p>`}
    ${caps.length > 0 && html`
      <label>${L("Styl napisów", "Caption style")}${seg(ED_STYLES.map(([k2, pl, en]) => [k2, L(pl, en)]), caps[0].style, (v) => setCapLook({ style: v }))}</label>
      <label>${L("Położenie", "Position")}${seg([[0.16, L("Góra", "Top")], [0.5, L("Środek", "Middle")], [0.84, L("Dół", "Bottom")]], [0.16, 0.5, 0.84].find((y) => Math.abs(y - caps[0].y) < 0.02), (v) => setCapLook({ y: v }))}</label>
      <label>${L("Kolor", "Color")}${swatches(caps[0].color, (v, lv) => setCapLook({ color: v }, lv))}</label>
      ${caps.some((x) => (x.words || []).length) ? html`<label class="thq-ed-check"><input type="checkbox" checked=${!!caps[0].hl}
          onChange=${(e) => setCapLook({ hl: e.target.checked ? (caps[0].hlLast || ED_HL) : "", hlLast: caps[0].hl || caps[0].hlLast })}/> ${L("Karaoke: aktywne słowo w kolorze", "Karaoke: highlight the spoken word")}</label>
        ${caps[0].hl && html`<label>${L("Kolor aktywnego słowa", "Active word color")}${swatches(caps[0].hl, (v, lv) => setCapLook({ hl: v }, lv))}</label>`}`
        : html`<p class="thq-ed-note">${L("Karaoke działa z napisami ze słów (automatyczne napisy), nie z pliku .srt.", "Karaoke works with word-synced auto captions, not .srt files.")}</p>`}
      <label>${L("Rozmiar", "Size")} · ${Math.round(caps[0].size)}<input type="range" min="24" max="140" value=${caps[0].size} onInput=${(e) => setCapLook({ size: +e.target.value }, true)} onChange=${H.commit}/></label>
      <p class="thq-ed-note">${L(`${caps.length} ${plNapisy(caps.length)}. Pojedynczy napis poprawisz, dotykając go na osi czasu.`, `${caps.length} captions. Tap one on the timeline to fix its text.`)}</p>
      <div class="thq-ed-acts">${act("trash", L("Usuń napisy", "Remove captions"), () => H.apply((P) => ({ ...P, texts: P.texts.filter((x) => !x.cap) })), { bad: true })}</div>`}
  </div>`;

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

  const formatTools = () => html`<div class="thq-ed-form">
    <div class="thq-ed-ratios">${ED_FORMATS.map(([k2, pl, en]) => {
      const [w, h] = k2 === "orig" ? [(meta[path] || {}).w || 16, (meta[path] || {}).h || 9] : ED_SIZES[k2];
      const r = w / h, bw = r >= 1 ? 30 : Math.round(30 * r), bh = r >= 1 ? Math.round(30 / r) : 30;
      return html`<button type="button" key=${k2} class=${cx((p.format || "orig") === k2 && "is-on")} onClick=${() => setCanvas(k2)}>
        <i style=${{ width: `${bw}px`, height: `${bh}px` }}></i><span>${k2 === "orig" ? L("Oryginał", "Original") : k2}</span><small>${L(pl, en).split("· ")[1] || ""}</small></button>`;
    })}</div>
    <label>${L("Klatki na sekundę", "Frame rate")}${seg([24, 25, 30, 50, 60].map((f) => [f, String(f)]), p.canvas.fps, (v) => H.apply((P) => ({ ...P, canvas: { ...P.canvas, fps: v } })))}</label>
    <p class="thq-ed-note">${CW}×${CH} · ${fmtT(total, true)}</p>
  </div>`;

  // ---- wspólne elementy: scena, oś czasu
  const stage = html`<div class="thq-ed-fit" ref=${wrapRef}>
    <div class="thq-ed-stage" ref=${stageRef} style=${stageSize}>
      <video ref=${player.vids[0]} class="thq-ed-v" playsinline preload="auto" onError=${codecFallback}></video>
      <video ref=${player.vids[1]} class="thq-ed-v" playsinline preload="auto" onError=${codecFallback}></video>
      ${proxying > 0 && html`<p class="thq-ed-codec is-info"><span class="thq-ed-spin is-small"></span> ${L("Przygotowuję podgląd dla tej przeglądarki (kopia WebM na serwerze, raz)…", "Preparing a preview this browser can play (one-time WebM copy)…")}</p>`}
      <img ref=${player.imgRef} class="thq-ed-v" alt=""/>
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
    ${p.texts.map((x) => html`<div key=${x.id} class=${cx("thq-ed-item is-text", x.cap && "is-cap", sel && sel.id === x.id && "is-sel")}
      style=${{ left: `${x.start * pps}px`, width: `${Math.max(6, (x.end - x.start) * pps)}px`, top: `${3 + textLane[x.id] * 26}px` }}
      onPointerDown=${(e) => textDown(e, x)} onClick=${(e) => pick(e, "text", x.id)}>
      <i class="thq-ed-h is-l" onPointerDown=${(e) => textDown(e, x, "l")}></i><span>${x.cap ? "CC" : "T"} ${x.text}</span><i class="thq-ed-h is-r" onPointerDown=${(e) => textDown(e, x, "r")}></i></div>`)}
    ${mobile && !p.texts.length && html`<button type="button" class="thq-ed-add" style=${{ left: `${t * pps}px` }} onClick=${(e) => { e.stopPropagation(); addText(); setTool("text"); }}>+ ${L("Dodaj tekst", "Add text")}</button>`}
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
      return html`<div key=${s.c.id} class=${cx("thq-ed-item is-clip", sel && sel.id === s.c.id && "is-sel", dragIdx === i && "is-drag")}
        style=${{ left: `${s.start * pps}px`, width: `${Math.max(4, wpx)}px`, ...bg }} onPointerDown=${(e) => clipDown(e, s, i)} onClick=${(e) => pick(e, "clip", s.c.id)}>
        <i class="thq-ed-h is-l" onPointerDown=${(e) => clipDown(e, s, i, "l")}></i>
        <span class="thq-ed-cl">${s.c.speed !== 1 ? `${s.c.speed}× · ` : ""}${s.c.muted ? "🔇 " : ""}${fmtT(s.end - s.start, true)}</span>
        <i class="thq-ed-h is-r" onPointerDown=${(e) => clipDown(e, s, i, "r")}></i></div>`;
    })}
    ${mobile && html`<button type="button" class="thq-ed-addclip" style=${{ left: `${total * pps + 8}px` }} onClick=${(e) => { e.stopPropagation(); setSel(null); setTool("media"); }}
      aria-label=${L("Dodaj klip", "Add clip")}>${ED_ICON.plus}</button>`}
  </div>`;
  const audioTrack = html`<div class="thq-ed-track is-audio" onPointerDown=${rulerDown} onClick=${() => mobile && setSel(null)}>
    ${p.audio.map((m) => html`<div key=${m.id} class=${cx("thq-ed-item is-audio", sel && sel.id === m.id && "is-sel")}
      style=${{ left: `${m.start * pps}px`, width: `${Math.max(6, audioDur(m) * pps)}px` }} onPointerDown=${(e) => audioDown(e, m)} onClick=${(e) => pick(e, "audio", m.id)}>
      <i class="thq-ed-h is-l" onPointerDown=${(e) => audioDown(e, m, "l")}></i><span>♪ ${(meta[m.src] || {}).name || ""} · ${Math.round(m.volume * 100)}%</span>
      <i class="thq-ed-h is-r" onPointerDown=${(e) => audioDown(e, m, "r")}></i></div>`)}
    ${!p.audio.length && (mobile
      ? html`<button type="button" class="thq-ed-add" style=${{ left: `${t * pps}px` }} onClick=${(e) => { e.stopPropagation(); setSel(null); setTool("audio"); }}>+ ${L("Dodaj audio", "Add audio")}</button>`
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
          ${ticks.map((s) => html`<span key=${s} style=${{ left: `${s * pps}px` }}>${step < 1 ? `${fmtT(s)}${(s % 1 ? ".5" : "")}` : fmtT(s)}</span>`)}
        </div>
        ${mobile ? [noteTrack, videoTrack, speechTrack, audioTrack, textTrack] : [noteTrack, textTrack, videoTrack, speechTrack, audioTrack]}
        ${!mobile && html`<div class="thq-ed-head" ref=${headRef} style=${{ left: `${pad}px`, transform: `translateX(${t * pps}px)` }}><i></i></div>`}
      </div>
    </div>
    ${mobile && html`<div class="thq-ed-center"><i></i></div>`}
  </div>`;
  const banner = shot ? html`<div class="thq-ed-banner is-shot" role="status">
      <span>${shot.busy ? L("Zapisuję kadr…", "Saving the frame…") : L("📷 Przeciągnij prostokąt na podglądzie albo kliknij, żeby wziąć cały kadr.", "📷 Drag a box on the preview, or click to take the whole frame.")}</span>
      <button type="button" class="thq-ed-btn" onClick=${() => setShot(null)}>${L("Anuluj", "Cancel")}</button></div>`
    : conflict ? html`<div class="thq-ed-banner" role="alert">
      <span>${conflict.kto === "jarvo-wideo" ? L("Wideograf zmienił ten projekt, a Ty masz niezapisane zmiany.", "The video agent changed this project while you have unsaved changes.")
        : L("Projekt zmienił się poza edytorem.", "The project changed outside the editor.")}</span>
      <button type="button" class="thq-ed-btn is-main" onClick=${() => reloadProject(conflict.kto)}>${L("Wczytaj jego wersję", "Load theirs")}</button>
      <button type="button" class="thq-ed-btn" onClick=${keepMine}>${L("Zostaw moją", "Keep mine")}</button></div>`
    : toast ? html`<div class="thq-ed-banner is-ok" role="status"><span>✓ ${toast}</span></div>` : null;
  const askBox = ask && !shot && html`<${AskAgent} ask=${ask} setAsk=${setAsk} path=${path} saveNow=${saveNow} time=${tRef.current} sel=${sel && selItem ? { ...sel, item: selItem } : null}
    onOpen=${(f) => { onClose(); openFile && openFile(f); }} notes=${notes} addNote=${addNote} removeNote=${removeNote} noteHi=${noteHi}
    onSeek=${(x) => player.seek(x)} startShot=${startShot} urls=${shotUrls}/>`;
  const exportBox = job && html`<${ExportBox} job=${job} onClose=${() => setJob(null)} onOpen=${(f) => { onClose(); openFile && openFile(f); }}/>`;
  const exportBtn = html`<button type="button" class="thq-ed-btn is-main" disabled=${running || !info.ffmpeg} onClick=${doExport}
    title=${info.ffmpeg ? L("Zapisz nową wersję filmu (oryginał zostaje)", "Save a new version (the original stays)") : L("Brak ffmpeg w kontenerze", "ffmpeg is missing in the container")}>${mobile ? L("Eksport", "Export") : `⤓ ${L("Eksportuj", "Export")}`}</button>`;

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
    else if (tool === "format") { sheet = formatTools(); title = L("Format", "Format"); }
    else if (tool === "media") { sheet = html`<div class="thq-ed-form">${mediaList(["video", "image"])}${uploadBtn("video/*,image/png,image/jpeg,image/webp")}</div>`; title = L("Dodaj klip", "Add clip"); }
    return html`<div class=${cx("thq-ed is-mobile", sheet && "has-sheet")} role="dialog" aria-modal="true" aria-label=${L("Edytor filmu", "Video editor")}>
      <header class="thq-ed-top">
        <button type="button" class="thq-ed-ico" onClick=${() => { player.stop(); onClose(); }} aria-label=${L("Zamknij edytor", "Close the editor")}>${ED_ICON.close}</button>
        <span class="thq-ed-saved">${saved}</span>
        <span class="thq-ed-grow"></span>
        <button type="button" class="thq-ed-ico" onClick=${() => setAsk(ask ? null : { text: "", reply: "", busy: false })} aria-label=${L("Poproś agenta", "Ask the agent")}>${ED_ICON.spark}</button>
        ${exportBtn}
      </header>
      ${askBox}${banner}
      <section class="thq-ed-stage-wrap">${stage}</section>
      <div class="thq-ed-transport">
        <span class="thq-ed-time"><span ref=${timeRef}>${fmtT(t, true)}</span> / ${fmtT(total, true)}</span>
        <button type="button" class="thq-ed-play" onClick=${player.toggle} aria-label=${player.playing ? L("Pauza", "Pause") : L("Odtwórz", "Play")}>${player.playing ? "❚❚" : "▶"}</button>
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
    return sel.type === "clip" ? clipTools(selItem) : sel.type === "text" ? textTools(selItem) : audioTools(selItem);
  };
  return html`<div class="thq-ed" role="dialog" aria-modal="true" aria-label=${L("Edytor filmu", "Video editor")}>
    <header class="thq-ed-top">
      <button type="button" class="thq-ed-btn is-ghost" onClick=${() => { player.stop(); onClose(); }} title=${L("Zamknij edytor (projekt jest zapisany)", "Close the editor (the project is saved)")}>← ${L("Wróć", "Back")}</button>
      <strong class="thq-ed-title" title=${path}>${path.split("/").pop()}</strong>
      <span class="thq-ed-saved">${saved}</span>
      <span class="thq-ed-grow"></span>
      <button type="button" class="thq-ed-btn is-ghost" disabled=${!H.canUndo} onClick=${H.undo} title="Ctrl+Z">↶</button>
      <button type="button" class="thq-ed-btn is-ghost" disabled=${!H.canRedo} onClick=${H.redo} title="Ctrl+Shift+Z">↷</button>
      <button type="button" class="thq-ed-btn" onClick=${() => setAsk(ask ? null : { text: "", reply: "", busy: false })}>✦ ${L("Poproś agenta", "Ask the agent")}</button>
      ${exportBtn}
    </header>
    ${askBox}${banner}
    <div class="thq-ed-body">
      <aside class="thq-ed-side">
        <div class="thq-ed-tabs">
          <button type="button" class=${cx(side === "media" && "is-on")} onClick=${() => setSide("media")}>${L("Media", "Media")}</button>
          <button type="button" class=${cx(side === "captions" && "is-on")} onClick=${() => setSide("captions")}>${L("Napisy", "Captions")}</button>
          <button type="button" class=${cx(side === "speech" && "is-on")} onClick=${() => setSide("speech")}>${L("Mowa", "Speech")}</button>
          <button type="button" class=${cx(side === "inspect" && "is-on")} onClick=${() => setSide("inspect")}>${L("Ustawienia", "Settings")}</button>
        </div>
        ${side === "media" ? html`<div class="thq-ed-media">
          <button type="button" class="thq-ed-btn is-wide" onClick=${addText}>T ${L("Dodaj napis", "Add text")}</button>
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
          <button type="button" class="thq-ed-play" onClick=${player.toggle} aria-label=${player.playing ? L("Pauza", "Pause") : L("Odtwórz", "Play")}>${player.playing ? "❚❚" : "▶"}</button>
          <span class="thq-ed-time"><span ref=${timeRef}>${fmtT(t, true)}</span> / ${fmtT(total, true)}</span>
        </div>
      </section>
    </div>
    <div class="thq-ed-tools">
      <button type="button" class="thq-ed-btn is-ghost" onClick=${split} title="S">✂ ${L("Tnij", "Split")}</button>
      <button type="button" class="thq-ed-btn is-ghost" onClick=${addText} title="T">T ${L("Napis", "Text")}</button>
      <button type="button" class="thq-ed-btn is-ghost" disabled=${!sel} onClick=${duplicate} title="Ctrl+D">⧉</button>
      <button type="button" class="thq-ed-btn is-ghost" disabled=${!sel || (sel.type === "clip" && p.clips.length <= 1)} onClick=${remove} title="Delete">🗑</button>
      <span class="thq-ed-grow"></span>
      <button type="button" class="thq-ed-btn is-ghost" onClick=${() => setPps((x) => clamp(x / 1.4, 4, 400))} aria-label=${L("Oddal", "Zoom out")}>−</button>
      <button type="button" class="thq-ed-btn is-ghost" onClick=${fitZoom}>${L("Całość", "Fit")}</button>
      <button type="button" class="thq-ed-btn is-ghost" onClick=${() => setPps((x) => clamp(x * 1.4, 4, 400))} aria-label=${L("Przybliż", "Zoom in")}>+</button>
    </div>
    ${timeline}
    ${exportBox}
  </div>`;
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
    ${!done && !bad && html`<p><strong>${job.state === "prep" ? L("Przygotowuję napisy…", "Preparing texts…") : L(`Eksport ${pct}%`, `Exporting ${pct}%`)}</strong></p>
      <div class="thq-ed-bar"><i style=${{ width: `${pct}%` }}></i></div>
      ${job.id && html`<button type="button" class="thq-ed-btn" onClick=${() => api.editCancel(job.id).catch(() => {})}>${L("Przerwij", "Cancel")}</button>`}`}
    ${done && html`<p><strong>✓ ${L("Gotowe", "Done")}:</strong> ${file.name} · ${bytes(job.size)}</p>
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
  return src ? html`<img src=${src} alt=${L("Kadr uwagi", "Note frame")}/>` : html`<span class="thq-ed-note-pic" title=${path}>📷</span>`;
}
const plUwag = (n) => (n === 1 ? "uwaga" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "uwagi" : "uwag");
function AskAgent({ ask, setAsk, path, saveNow, time, sel, onOpen, notes, addNote, removeNote, noteHi, onSeek, startShot, urls }) {
  const open = openNotes(notes);
  const where = sel ? (sel.type === "text" ? `napis „${sel.item.text}” (${fmtT(sel.item.start, true)}–${fmtT(sel.item.end, true)})`
    : sel.type === "clip" ? `klip ${sel.item.src.split("/").pop()} (${fmtT(sel.item.in, true)}–${fmtT(sel.item.out, true)} źródła)` : `muzyka ${sel.item.src.split("/").pop()}`) : "nic";
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
    <p class="thq-ed-note">${L("Wideograf dostanie film, projekt montażu, miejsce na osi, uwagi i kadry. 📌 przypina prośbę do chwili filmu, 📷 dołącza zaznaczony fragment podglądu.",
      "The video agent gets the film, the edit project, your timeline position, notes and frames. 📌 pins a request to a moment, 📷 attaches a part of the preview.")}</p>
    ${sorted.length > 0 && html`<ol class="thq-ed-notes">${sorted.map((n) => html`<li key=${n.id} class=${cx(n.done && "is-done", noteHi === n.id && "is-sel")}>
      <button type="button" class="thq-ed-note-t" onClick=${() => onSeek(n.t)} title=${L("Przejdź do tego miejsca", "Go to this moment")}>${edClock(n.t)}</button>
      <span class="thq-ed-note-x">${n.text || L("(kadr)", "(frame)")}${n.done && html`<small>✓ ${n.odp || L("zrobione", "done")}</small>`}</span>
      ${n.img && html`<${NoteThumb} path=${n.img} url=${urls.current.get(n.img)}/>`}
      <button type="button" class="thq-ed-note-del" onClick=${() => removeNote(n.id)} aria-label=${L("Usuń uwagę", "Remove note")}>×</button></li>`)}</ol>`}
    <textarea rows="2" value=${ask.text} placeholder=${L("Co zmienić? Np. „tu za szybko”, „literówka w napisie”, „dodaj lektora”.", "What should change? E.g. “too fast here”, “typo in the caption”, “add a voice-over”.")}
      onInput=${(e) => { const v = e.target.value; setAsk((a) => ({ ...a, text: v })); }}
      onKeyDown=${(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}></textarea>
    ${ask.shot && html`<div class="thq-ed-shotprev"><img src=${ask.shot.url} alt=${L("Kadr", "Frame")}/>
      <span>${L("Kadr", "Frame")} ${edClock(ask.shot.t)}${ask.shot.full ? "" : L(" · fragment", " · crop")}</span>
      <button type="button" class="thq-ed-note-del" onClick=${() => setAsk((a) => ({ ...a, shot: null }))} aria-label=${L("Usuń kadr", "Remove frame")}>×</button></div>`}
    <div class="thq-ed-row is-actions">
      <button type="button" class="thq-ed-btn" onClick=${startShot} disabled=${ask.busy}>📷 ${L("Kadr", "Frame")}</button>
      <button type="button" class="thq-ed-btn" onClick=${pin} disabled=${ask.busy || (!text && !ask.shot)}
        title=${L("Zapisz jako uwagę w tym miejscu osi (wyślesz kilka naraz)", "Save as a note at this moment (send several at once)")}>📌 ${L("Uwaga w", "Note at")} ${edClock(time)}</button>
      <span class="thq-ed-grow"></span>
      <button type="button" class="thq-ed-btn is-main" disabled=${!canSend} onClick=${send}>${ask.busy ? "…"
        : open.length ? L(`Wyślij (${open.length} ${plUwag(open.length)})`, `Send (${open.length} note${open.length === 1 ? "" : "s"})`) : L("Wyślij", "Send")}</button>
    </div>
    ${(ask.reply || ask.busy) && html`<div class="thq-ed-reply"><${Markdown} text=${ask.reply || L("Wideograf pracuje…", "Working…")}/></div>`}
    ${ask.error && html`<p class="thq-ed-bad">${ask.error}</p>`}
    ${vids.map((v) => html`<button key=${v} type="button" class="thq-ed-btn" onClick=${() => onOpen(fileFromPath(v))}>▶ ${v.split("/").pop()}</button>`)}
  </div>`;
}
