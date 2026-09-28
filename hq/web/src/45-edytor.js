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
const ED_FONTS = [
  ["system-ui, 'Segoe UI', Roboto, sans-serif", "Bezszeryfowy"], ["'Bricolage Grotesque', system-ui, sans-serif", "Display"],
  ["Georgia, 'Times New Roman', serif", "Szeryfowy"], ["'JetBrains Mono', ui-monospace, monospace", "Mono"],
];
const ED_STYLES = [["shadow", "Cień", "Shadow"], ["box", "Tło", "Box"], ["outline", "Obrys", "Outline"], ["plain", "Zwykły", "Plain"]];
const ED_MIN = 0.1;
const ED_COLORS = ["#FFFFFF", "#000000", "#FFD60A", "#FF453A", "#32D74B", "#0A84FF", "#BF5AF2", "#FF9F0A"];
const ED_CAP = { x: 0.5, y: 0.84, size: 58, color: "#FFFFFF", bg: "#000000", style: "outline", bold: true, align: "center", maxw: 0.84,
  font: "'Bricolage Grotesque', system-ui, sans-serif" };
const plNapisy = (n) => (n === 1 ? "napis" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "napisy" : "napisów");
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

// ------------------------------------------------------------------ napisy: jedna funkcja rysująca
function textFont(t, H, W) {
  const px = Math.max(6, (t.size || 64) * Math.min(W, H) / 1080);
  return { px, font: `${t.bold === false ? 500 : 800} ${px}px ${t.font || ED_FONTS[0][0]}` };
}
function wrapLines(ctx, text, maxW) {
  const out = [];
  for (const para of String(text || "").split("\n")) {
    let line = "";
    for (const word of para.split(/\s+/).filter(Boolean)) {
      const test = line ? `${line} ${word}` : word;
      if (line && ctx.measureText(test).width > maxW) { out.push(line); line = word; } else line = test;
    }
    out.push(line);
  }
  return out;
}
// Prostokąt napisu na kanwie W×H (do trafiania myszą i rysowania).
function textBox(ctx, t, W, H) {
  const { px, font } = textFont(t, H, W);
  ctx.font = font;
  const lines = wrapLines(ctx, t.text, (t.maxw || 0.86) * W);
  const lh = px * 1.18;
  const w = Math.max(...lines.map((l) => ctx.measureText(l).width), px * 0.5);
  const h = lines.length * lh;
  const cx = (t.x ?? 0.5) * W, cy = (t.y ?? 0.8) * H;
  const pad = t.style === "box" ? px * 0.35 : px * 0.1;
  return { px, font, lines, lh, w, h, cx, cy, x0: cx - w / 2 - pad, y0: cy - h / 2 - pad, x1: cx + w / 2 + pad, y1: cy + h / 2 + pad };
}
function drawText(ctx, t, W, H) {
  const b = textBox(ctx, t, W, H);
  ctx.save();
  ctx.font = b.font;
  ctx.textBaseline = "middle";
  const align = t.align || "center";
  ctx.textAlign = align;
  const ax = align === "left" ? b.cx - b.w / 2 : align === "right" ? b.cx + b.w / 2 : b.cx;
  if (t.style === "box") {
    const r = b.px * 0.22;
    ctx.fillStyle = t.bg || "rgba(0,0,0,0.72)";
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0, r); else ctx.rect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0);
    ctx.fill();
  }
  b.lines.forEach((line, i) => {
    const y = b.cy - b.h / 2 + b.lh * (i + 0.5);
    if (t.style === "outline") {
      ctx.lineJoin = "round"; ctx.lineWidth = Math.max(2, b.px * 0.14); ctx.strokeStyle = t.bg || "#000";
      ctx.strokeText(line, ax, y);
    }
    if (t.style === "shadow") { ctx.shadowColor = "rgba(0,0,0,0.65)"; ctx.shadowBlur = b.px * 0.18; ctx.shadowOffsetY = b.px * 0.05; }
    ctx.fillStyle = t.color || "#fff";
    ctx.fillText(line, ax, y);
    ctx.shadowColor = "transparent";
  });
  ctx.restore();
  return b;
}
async function textPng(t, W, H) {
  try { await document.fonts.load(textFont(t, H, W).font); } catch (_) { /* czcionka systemowa */ }
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  drawText(c.getContext("2d"), t, W, H);
  return c.toDataURL("image/png");
}

// ------------------------------------------------------------------ media: adresy blob i miniatury
const edUrls = new Map();       // src → Promise<blob url>
function mediaUrl(src) {
  if (!edUrls.has(src)) {
    const p = api.fileBlob(src).then((b) => URL.createObjectURL(b));
    p.catch(() => edUrls.delete(src));
    edUrls.set(src, p);
  }
  return edUrls.get(src);
}
function releaseMedia() {
  for (const p of edUrls.values()) p.then((u) => URL.revokeObjectURL(u)).catch(() => {});
  edUrls.clear();
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
    v.style.objectFit = c.fit === "cover" ? "cover" : "contain";
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
      if (imgRef.current) imgRef.current.style.objectFit = s.c.fit === "cover" ? "cover" : "contain";
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
  useEffect(() => () => releaseMedia(), []);

  const addMeta = useCallback((list) => setMeta((m) => { const n = { ...m }; for (const x of list) n[x.path] = x; return n; }), []);
  useEffect(() => {
    let alive = true;
    if (!api.editInfo) { setErr(L("Edytor działa w zainstalowanym Jarvo.", "The editor runs in an installed Jarvo.")); return undefined; }
    api.editInfo(path).then(async (d) => {
      if (!alive) return;
      addMeta([d.file, ...d.media]);
      let proj = d.project && Array.isArray(d.project.clips) && d.project.clips.length ? d.project : initialProject(d.file);
      // pliki z zapisanego projektu, których nie ma w katalogu: dopytujemy, brakujące odrzucamy
      const known = new Set([d.file.path, ...d.media.map((x) => x.path)]);
      const need = [...new Set([...proj.clips, ...(proj.audio || [])].map((c) => c.src).filter((s) => !known.has(s)))];
      const extra = await Promise.all(need.map((s) => api.editMedia(s).catch(() => null)));
      addMeta(extra.filter(Boolean));
      const ok = new Set([...known, ...extra.filter(Boolean).map((x) => x.path)]);
      proj = { ...proj, texts: (proj.texts || []).map((x) => ({ ...x, id: x.id || edId("t") })),
        clips: proj.clips.filter((c) => ok.has(c.src)).map((c) => ({ ...c, id: c.id || edId("c") })),
        audio: (proj.audio || []).filter((c) => ok.has(c.src)).map((c) => ({ ...c, id: c.id || edId("a") })) };
      if (!proj.clips.length) proj = initialProject(d.file);
      H.reset(proj);
      setInfo(d);
    }).catch((e) => alive && setErr(e.message || String(e)));
    return () => { alive = false; };
  }, [path]);

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
      const b = drawText(g, x, w, h);
      const s = selRef.current;
      if (s && s.type === "text" && s.id === x.id) {
        g.save(); g.strokeStyle = "#3BA9FF"; g.lineWidth = Math.max(2, w / 480); g.setLineDash([w / 90, w / 140]);
        g.strokeRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0); g.restore();
      }
    }
  }
  useEffect(() => { drawOverlay(); }, [p, sel]);
  useEffect(() => { onTick(tRef.current, false); }, [pps]);
  // po zmianie projektu odtwarzacz pokazuje właściwą klatkę (zatrzymany)
  useEffect(() => { if (p && !player.playing) player.seek(Math.min(tRef.current, Math.max(0, projTotal(p) - 0.001))); }, [p && p.clips]);

  // autozapis projektu obok filmu
  useEffect(() => {
    if (!p || !info) return undefined;
    setSaved(L("zmiany…", "changes…"));
    const id = setTimeout(() => {
      api.editSave(path, p).then(() => setSaved(L("zapisano", "saved"))).catch((e) => setSaved(L(`nie zapisano: ${e.message}`, `not saved: ${e.message}`)));
    }, 1200);
    return () => clearTimeout(id);
  }, [p]);

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
      const pngs = [];
      for (const x of texts) pngs.push(await textPng(x, w, h));
      const r = await api.editExport(path, { ...p, texts }, pngs);
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
      else if (e.key === "Escape") { if (ask) setAsk(null); else if (sel) setSel(null); }
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
      if (edge === "l") upd("text", x.id, { start: clamp(snap(a + d, [a]), 0, b - ED_MIN) }, true);
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
    if (mobileRef.current) setTool(type === "clip" ? "edit" : type);
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
    const look = old ? { x: old.x, y: old.y, size: old.size, color: old.color, bg: old.bg, style: old.style, font: old.font, bold: old.bold, maxw: old.maxw } : {};
    H.apply((P) => ({ ...P, texts: [...P.texts.filter((x) => !x.cap),
      ...list.map((k) => ({ ...ED_CAP, ...look, id: edId("t"), cap: true, start: k.start, end: k.end, text: k.text }))] }));
  }
  async function autoCaptions(force) {
    if (capJob && capJob.state === "running") return;
    const srcs = [...new Set(p.clips.filter((c) => c.kind === "video").map((c) => c.src))];
    setCapJob({ state: "running" });
    try {
      let all = [];
      for (const src of srcs) {
        let j = await api.editCaptions(src, force);
        while (j.state === "running") { await edSleep(1500); j = await api.editJob(j.id); }
        if (j.state !== "done") throw new Error(j.error || L("Rozpoznawanie mowy nie wyszło.", "Speech recognition failed."));
        all = all.concat(mapCaptions(j.captions || [], src));
      }
      if (!all.length) throw new Error(L("Nie znalazłem mowy w klipach na osi.", "No speech found in the timeline clips."));
      setCaptions(all);
      setCapJob({ state: "done", n: all.length });
    } catch (e) { setCapJob({ state: "error", error: e.message || String(e) }); }
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
    ${info.stt ? html`<button type="button" class="thq-ed-btn is-main is-wide" disabled=${capJob && capJob.state === "running"} onClick=${() => autoCaptions(false)}>
        ${ED_ICON.spark} ${capJob && capJob.state === "running" ? L("Rozpoznaję mowę…", "Recognising speech…") : caps.length ? L("Rozpoznaj napisy jeszcze raz", "Recognise captions again") : L("Automatyczne napisy z mowy", "Auto captions from speech")}</button>
        <p class="thq-ed-note">${L("Rozpoznawanie działa na serwerze (Parakeet, bez internetu). Pierwszy raz trwa dłużej: pobiera się model.", "Recognition runs on the server (Parakeet, offline). The first run downloads the model.")}</p>`
      : html`<p class="thq-ed-note">${L("Rozpoznawanie mowy jest niedostępne w tej instalacji. Możesz wczytać gotowy plik .srt.", "Speech recognition is not available here. You can load a .srt file.")}</p>`}
    ${(info.subs || []).length > 0 && html`<p class="thq-ed-note">${L("Z pliku napisów:", "From a subtitle file:")}</p>
      <ul class="thq-ed-list">${info.subs.map((f) => html`<li key=${f}><button type="button" onClick=${() => srtCaptions(f)}><span class="thq-ed-mk is-text">CC</span><span class="thq-ed-mn">${f.split("/").pop()}</span><span class="thq-ed-plus">+</span></button></li>`)}</ul>`}
    ${capJob && capJob.state === "error" && html`<p class="thq-ed-bad">${capJob.error}</p>`}
    ${capJob && capJob.state === "done" && html`<p class="thq-ed-ok">✓ ${L(`Dodano ${capJob.n} ${plNapisy(capJob.n)}`, `Added ${capJob.n} captions`)}</p>`}
    ${caps.length > 0 && html`
      <label>${L("Styl napisów", "Caption style")}${seg(ED_STYLES.map(([k2, pl, en]) => [k2, L(pl, en)]), caps[0].style, (v) => setCapLook({ style: v }))}</label>
      <label>${L("Położenie", "Position")}${seg([[0.16, L("Góra", "Top")], [0.5, L("Środek", "Middle")], [0.84, L("Dół", "Bottom")]], [0.16, 0.5, 0.84].find((y) => Math.abs(y - caps[0].y) < 0.02), (v) => setCapLook({ y: v }))}</label>
      <label>${L("Kolor", "Color")}${swatches(caps[0].color, (v, lv) => setCapLook({ color: v }, lv))}</label>
      <label>${L("Rozmiar", "Size")} · ${Math.round(caps[0].size)}<input type="range" min="24" max="140" value=${caps[0].size} onInput=${(e) => setCapLook({ size: +e.target.value }, true)} onChange=${H.commit}/></label>
      <p class="thq-ed-note">${L(`${caps.length} ${plNapisy(caps.length)}. Pojedynczy napis poprawisz, dotykając go na osi czasu.`, `${caps.length} captions. Tap one on the timeline to fix its text.`)}</p>
      <div class="thq-ed-acts">${act("trash", L("Usuń napisy", "Remove captions"), () => H.apply((P) => ({ ...P, texts: P.texts.filter((x) => !x.cap) })), { bad: true })}</div>`}
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
      <video ref=${player.vids[0]} class="thq-ed-v" playsinline preload="auto" onError=${() => setCodecErr(true)}></video>
      <video ref=${player.vids[1]} class="thq-ed-v" playsinline preload="auto" onError=${() => setCodecErr(true)}></video>
      <img ref=${player.imgRef} class="thq-ed-v" alt=""/>
      <canvas ref=${overlayRef} class="thq-ed-overlay" onPointerDown=${stagePointer}></canvas>
      ${codecErr && html`<p class="thq-ed-codec">${L("Ta przeglądarka nie odtwarza kodeka tego filmu (np. Chromium bez H.264). Montaż i eksport działają; do podglądu użyj Chrome, Edge albo Safari.",
        "This browser cannot decode the video codec (e.g. Chromium without H.264). Editing and export still work; use Chrome, Edge or Safari to preview.")}</p>`}
    </div></div>
    ${p.audio.map((m) => html`<${EdAudio} key=${m.id} m=${m} audios=${player.audios}/>`)}`;

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
  const timeline = html`<div class="thq-ed-tlwrap">
    <div class="thq-ed-tl" ref=${tlRef} onScroll=${onTlScroll} ...${mobile ? tlTouch : {}}
      onWheel=${(e) => { if (e.ctrlKey) { e.preventDefault(); setPps((x) => clamp(x * (e.deltaY < 0 ? 1.15 : 1 / 1.15), 4, 400)); } }}>
      <div class="thq-ed-tl-in" style=${{ width: `${width}px`, padding: `0 ${pad}px 10px` }}>
        <div class="thq-ed-ruler" onPointerDown=${rulerDown}>
          ${ticks.map((s) => html`<span key=${s} style=${{ left: `${s * pps}px` }}>${step < 1 ? `${fmtT(s)}${(s % 1 ? ".5" : "")}` : fmtT(s)}</span>`)}
        </div>
        ${mobile ? [videoTrack, audioTrack, textTrack] : [textTrack, videoTrack, audioTrack]}
        ${!mobile && html`<div class="thq-ed-head" ref=${headRef} style=${{ left: `${pad}px`, transform: `translateX(${t * pps}px)` }}><i></i></div>`}
      </div>
    </div>
    ${mobile && html`<div class="thq-ed-center"><i></i></div>`}
  </div>`;
  const askBox = ask && html`<${AskAgent} ask=${ask} setAsk=${setAsk} path=${path} project=${p} time=${tRef.current} sel=${sel && selItem ? { ...sel, item: selItem } : null} onOpen=${(f) => { onClose(); openFile && openFile(f); }}/>`;
  const exportBox = job && html`<${ExportBox} job=${job} onClose=${() => setJob(null)} onOpen=${(f) => { onClose(); openFile && openFile(f); }}/>`;
  const exportBtn = html`<button type="button" class="thq-ed-btn is-main" disabled=${running || !info.ffmpeg} onClick=${doExport}
    title=${info.ffmpeg ? L("Zapisz nową wersję filmu (oryginał zostaje)", "Save a new version (the original stays)") : L("Brak ffmpeg w kontenerze", "ffmpeg is missing in the container")}>${mobile ? L("Eksport", "Export") : `⤓ ${L("Eksportuj", "Export")}`}</button>`;

  // ---- telefon: układ jak w CapCut
  if (mobile) {
    const TOOLS = [["edit", L("Edytuj", "Edit")], ["audio", L("Audio", "Audio")], ["text", L("Tekst", "Text")], ["captions", L("Napisy", "Captions")], ["format", L("Format", "Format")]];
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
      ${askBox}
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
    ${askBox}
    <div class="thq-ed-body">
      <aside class="thq-ed-side">
        <div class="thq-ed-tabs">
          <button type="button" class=${cx(side === "media" && "is-on")} onClick=${() => setSide("media")}>${L("Media", "Media")}</button>
          <button type="button" class=${cx(side === "captions" && "is-on")} onClick=${() => setSide("captions")}>${L("Napisy", "Captions")}</button>
          <button type="button" class=${cx(side === "inspect" && "is-on")} onClick=${() => setSide("inspect")}>${L("Ustawienia", "Settings")}</button>
        </div>
        ${side === "media" ? html`<div class="thq-ed-media">
          <button type="button" class="thq-ed-btn is-wide" onClick=${addText}>T ${L("Dodaj napis", "Add text")}</button>
          ${uploadBtn("video/*,audio/*,image/png,image/jpeg,image/webp")}
          <p class="thq-ed-note">${L("Z katalogu filmu", "From the film's folder")}</p>
          ${mediaList(["video", "image", "audio"])}
          ${act(allMuted ? "mute" : "volume", allMuted ? L("Włącz dźwięk filmu", "Unmute video") : L("Wycisz dźwięk filmu", "Mute video audio"),
            () => H.apply((P) => ({ ...P, clips: P.clips.map((c) => ({ ...c, muted: !allMuted })) })), { on: allMuted })}
        </div>` : side === "captions" ? captionTools() : inspector()}
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
function AskAgent({ ask, setAsk, path, project, time, sel, onOpen }) {
  const send = async () => {
    const text = ask.text.trim();
    if (!text || ask.busy) return;
    const projFile = path.replace(/\.[^./]+$/, ".edycja.json");
    const where = sel ? (sel.type === "text" ? `napis „${sel.item.text}” (${fmtT(sel.item.start, true)}–${fmtT(sel.item.end, true)})`
      : sel.type === "clip" ? `klip ${sel.item.src.split("/").pop()} (${fmtT(sel.item.in, true)}–${fmtT(sel.item.out, true)} źródła)` : `muzyka ${sel.item.src.split("/").pop()}`) : "nic";
    const msg = [`Edycja filmu w edytorze HQ: \`${path}\``, `Projekt montażu (JSON, oś czasu): \`${projFile}\` · kursor ${fmtT(time, true)} · zaznaczone: ${where}.`,
      `Prośba: ${text}`, "Nową wersję zapisz obok oryginału i podaj ścieżkę w linii MEDIA:."].join("\n");
    setAsk((a) => ({ ...a, busy: true, reply: "", error: null }));
    try {
      await api.editSave(path, project).catch(() => {});
      for await (const { event, data } of api.send(ED_AGENT, msg)) {
        if (event === "assistant.delta") setAsk((a) => a && { ...a, reply: (a.reply || "") + (data.delta || "") });
        else if (event === "assistant.completed" && typeof data.content === "string") setAsk((a) => a && { ...a, reply: data.content });
        else if (event === "run.failed" || event === "error") setAsk((a) => a && { ...a, error: data.message || data.error || "błąd" });
      }
    } catch (e) { setAsk((a) => a && { ...a, error: e.message || String(e) }); }
    setAsk((a) => a && { ...a, busy: false });
  };
  const vids = [...new Set(((ask.reply || "").match(/\/opt\/data\/jarvo\/(?:workspaces|missions|knowledge|inbox)\/[^\s`'"<>()]+\.(?:mp4|webm|mov)/g) || []))];
  return html`<div class="thq-ed-ask">
    <p class="thq-ed-note">${L("Wideograf dostanie film, projekt montażu i miejsce na osi. Np. „dodaj lektora”, „zrób wersję 15 s”, „podmień muzykę na spokojniejszą”.",
      "The video agent gets the film, the edit project and your timeline position. E.g. “add a voice-over”, “make a 15 s cut”, “calmer music”.")}</p>
    <div class="thq-ed-row"><textarea rows="2" value=${ask.text} placeholder=${L("Co zmienić?", "What should change?")}
      onInput=${(e) => { const v = e.target.value; setAsk((a) => ({ ...a, text: v })); }}
      onKeyDown=${(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}></textarea>
      <button type="button" class="thq-ed-btn is-main" disabled=${ask.busy || !ask.text.trim()} onClick=${send}>${ask.busy ? "…" : L("Wyślij", "Send")}</button></div>
    ${(ask.reply || ask.busy) && html`<div class="thq-ed-reply"><${Markdown} text=${ask.reply || L("Wideograf pracuje…", "Working…")}/></div>`}
    ${ask.error && html`<p class="thq-ed-bad">${ask.error}</p>`}
    ${vids.map((v) => html`<button key=${v} type="button" class="thq-ed-btn" onClick=${() => onOpen(fileFromPath(v))}>▶ ${v.split("/").pop()}</button>`)}
  </div>`;
}
