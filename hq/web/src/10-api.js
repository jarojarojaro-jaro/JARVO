// Klient API pluginu. W trybie demo (window.JARVO_HQ_MOCK) te same wywołania obsługuje symulator.

const API_ROOT = `/api/plugins/${PLUGIN}`;

function basePath() {
  const raw = window.__HERMES_BASE_PATH__ || "";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

function authHeaders(extra) {
  const h = Object.assign({}, extra || {});
  const token = window.__HERMES_SESSION_TOKEN__;
  if (token) h["X-Hermes-Session-Token"] = token;
  return h;
}

async function rawFetch(path, init) {
  const res = await fetch(`${basePath()}${path}`, {
    credentials: "include",
    ...init,
    headers: authHeaders(init && init.headers),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      msg = body.detail || body.error || msg;
    } catch (_) { /* nie-JSON */ }
    throw new Error(msg);
  }
  return res;
}

// Strumień SSE z fetch (EventSource nie wysyła POST ani nagłówków).
async function* readSSE(res) {
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message", data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try { yield { event, data: JSON.parse(data) }; } catch (_) { yield { event, data: { text: data } }; }
    }
  }
}

const liveApi = {
  state: () => SDK.fetchJSON(`${API_ROOT}/state`),
  fleet: () => SDK.fetchJSON(`${API_ROOT}/fleet`),
  agent: (name) => SDK.fetchJSON(`${API_ROOT}/agent/${encodeURIComponent(name)}`),
  task: (id) => SDK.fetchJSON(`${API_ROOT}/task/${encodeURIComponent(id)}`),
  history: (name) => SDK.fetchJSON(`${API_ROOT}/chat/${encodeURIComponent(name)}/history`),
  reset: (name) => SDK.fetchJSON(`${API_ROOT}/chat/${encodeURIComponent(name)}/reset`, { method: "POST" }),
  retry: (id) => SDK.fetchJSON(`${API_ROOT}/task/${encodeURIComponent(id)}/retry`, { method: "POST" }),
  async upload(file) {
    const res = await rawFetch(`${API_ROOT}/upload`, {
      method: "POST", headers: { "Content-Type": "application/octet-stream", "X-File-Name": encodeURIComponent(file.name || "plik") }, body: file,
    });
    return res.json();
  },
  site: (path) => SDK.fetchJSON(`${API_ROOT}/site`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }),
  android: () => SDK.fetchJSON(`${API_ROOT}/android`, { method: "POST" }),
  reveal: (path) => SDK.fetchJSON(`${API_ROOT}/reveal`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }),
  host: () => SDK.fetchJSON(`${API_ROOT}/host`),
  async fileBlob(path) {
    const res = await rawFetch(`${API_ROOT}/file?path=${encodeURIComponent(path)}`);
    return res.blob();
  },
  editInfo: (path) => SDK.fetchJSON(`${API_ROOT}/edit/info?path=${encodeURIComponent(path)}`),
  editMedia: (path) => SDK.fetchJSON(`${API_ROOT}/edit/media?path=${encodeURIComponent(path)}`),
  async editSave(path, project, base, force) {
    const res = await fetch(`${basePath()}${API_ROOT}/edit/save`, { method: "POST", credentials: "include",
      headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ path, project, base, force: !!force }) });
    if (res.status === 409) { const e = new Error("conflict"); e.conflict = true; throw e; }
    if (!res.ok) { let m = `HTTP ${res.status}`; try { m = (await res.json()).detail || m; } catch (_) { /* nie-JSON */ } throw new Error(m); }
    return res.json();
  },
  editStamp: (path) => SDK.fetchJSON(`${API_ROOT}/edit/stamp?path=${encodeURIComponent(path)}`),
  async editExport(path, project, texts, karaoke, typo) {
    const res = await rawFetch(`${API_ROOT}/edit/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, project, texts, karaoke: karaoke || {}, typo: typo || {} }) });
    return res.json();
  },
  editSrt: (path) => SDK.fetchJSON(`${API_ROOT}/edit/srt?path=${encodeURIComponent(path)}`),
  editSpeechGet: (src) => SDK.fetchJSON(`${API_ROOT}/edit/speech?src=${encodeURIComponent(src)}`),
  editSpeech: (src, force) => SDK.fetchJSON(`${API_ROOT}/edit/speech`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ src, force: !!force }) }),
  editProxy: (src) => SDK.fetchJSON(`${API_ROOT}/edit/proxy`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ src }) }),
  async proxyBlob(src) {
    const res = await rawFetch(`${API_ROOT}/edit/proxy-file?src=${encodeURIComponent(src)}`);
    return res.blob();
  },
  editJob: (id) => SDK.fetchJSON(`${API_ROOT}/edit/job/${encodeURIComponent(id)}`),
  animInfo: (path) => SDK.fetchJSON(`${API_ROOT}/anim/info?path=${encodeURIComponent(path)}`),
  animCheck: (path) => SDK.fetchJSON(`${API_ROOT}/anim/check?path=${encodeURIComponent(path)}`),
  async animParams(path, wartosci) {
    const res = await fetch(`${basePath()}${API_ROOT}/anim/params`, { method: "POST", credentials: "include",
      headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ path, wartosci }) });
    if (!res.ok) { let m = `HTTP ${res.status}`; try { m = (await res.json()).detail || m; } catch (_) { /* nie-JSON */ } throw new Error(m); }
    return res.json();
  },
  editCancel: (id) => SDK.fetchJSON(`${API_ROOT}/edit/job/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  async *send(name, message, extra) {
    const res = await rawFetch(`${API_ROOT}/chat/${encodeURIComponent(name)}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ message, ...(extra || {}) }),
    });
    yield* readSSE(res);
  },
};

const api = window.JARVO_HQ_MOCK || liveApi;

// Obiekt URL dla podglądu pliku (pobierany z autoryzacją, więc działa w każdym trybie logowania).
function useBlobUrl(path) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!path) return undefined;
    let alive = true, made = null;
    api.fileBlob(path).then((b) => {
      if (!alive) return;
      made = URL.createObjectURL(b);
      setUrl(made);
    }).catch(() => alive && setUrl(null));
    return () => { alive = false; if (made) URL.revokeObjectURL(made); };
  }, [path]);
  return url;
}

// Co umie host (Eksplorator w WSL, podgląd stron): pytamy raz na pół minuty, wszystkie okna dzielą wynik.
let hostCache = { at: 0, p: null };
function hostInfo() {
  if (!hostCache.p || Date.now() - hostCache.at > 30000) {
    hostCache = { at: Date.now(), p: api.host().catch(() => ({})) };
  }
  return hostCache.p;
}

function useHost() {
  const [h, setH] = useState({});
  useEffect(() => { let alive = true; hostInfo().then((x) => alive && setH(x || {})); return () => { alive = false; }; }, []);
  return h;
}

// „Odpal”: strona w nowej karcie z serwera podglądu (osobny port, link z tokenem). Kartę otwieramy od razu
// (blokada wyskakujących okien), odcinamy jej dostęp do dashboardu (opener) i dopiero potem ładujemy adres.
async function openSite(path) {
  return openTokenLink(() => api.site(path));
}

// Ekran telefonu testowego (Redroid przez ws-scrcpy): to samo, link z proxy na osobnym porcie.
function openAndroidScreen() {
  return openTokenLink(() => api.android());
}

async function openTokenLink(get) {
  const w = window.open("", "_blank");
  if (w) { w.opener = null; w.document.title = "Uruchamiam…"; }
  try {
    const r = await get();
    const url = r.url || `${location.protocol}//${location.hostname}:${r.port}${r.path}`;
    if (w) w.location.href = url; else window.open(url, "_blank", "noopener");
  } catch (e) {
    if (w) w.close();
    throw e;
  }
}

async function downloadFile(file) {
  const b = await api.fileBlob(file.path);
  const u = URL.createObjectURL(b);
  const a = document.createElement("a");
  a.href = u; a.download = file.name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(u), 5000);
}

// Ścieżka do wklejenia w Eksploratorze/terminalu: po stronie Windows (WSL), hosta albo kontenera.
function hostPathOf(path, host) {
  const rest = path.startsWith("/opt/data/") ? path.slice("/opt/data/".length) : null;
  if (rest != null && host.data_win) return `${host.data_win.replace(/\\$/, "")}\\${rest.split("/").join("\\")}`;
  if (rest != null && host.data_host) return `${host.data_host.replace(/\/$/, "")}/${rest}`;
  return path;
}

// Schowek: na http (np. adres Tailscale) przeglądarka nie daje navigator.clipboard, stąd zapas dla tekstu.
async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return; }
  const t = document.createElement("textarea");
  t.value = text; t.style.position = "fixed"; t.style.opacity = "0";
  document.body.appendChild(t); t.select();
  const ok = document.execCommand("copy");
  t.remove();
  if (!ok) throw new Error(L("Przeglądarka nie pozwoliła skopiować.", "The browser blocked copying."));
}

async function toPng(blob) {
  if (blob.type === "image/png") return blob;
  const bmp = await createImageBitmap(blob);
  const c = document.createElement("canvas");
  c.width = bmp.width; c.height = bmp.height;
  c.getContext("2d").drawImage(bmp, 0, 0);
  return new Promise((ok, bad) => c.toBlob((b) => (b ? ok(b) : bad(new Error("PNG"))), "image/png"));
}

// Obraz do schowka: wklejasz go potem w Telegramie, mailu, innym czacie (jak „Kopiuj obraz” w przeglądarce).
async function copyImage(file) {
  if (!(navigator.clipboard && navigator.clipboard.write && window.ClipboardItem && window.isSecureContext)) {
    throw new Error(L("Kopiowanie obrazu działa na localhost albo https. Użyj „Pobierz”.", "Copying images needs localhost or https. Use “Download”."));
  }
  const png = await toPng(await api.fileBlob(file.path));
  await navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
}

// Zdjęcie do wiadomości: najwyżej 1600 px po dłuższym boku, JPEG (mały plik mieści się w limicie gatewaya).
async function imageDataUrl(file) {
  const small = file.size < 400 * 1024 && /^image\/(png|jpeg|webp|gif)$/.test(file.type);
  if (small) return new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = bad; r.readAsDataURL(file); });
  const bmp = await createImageBitmap(file);
  const k = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
  const g = c.getContext("2d");
  g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);
  g.drawImage(bmp, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.85);
}
