// Klient API pluginu. W trybie demo (window.TARS_HQ_MOCK) te same wywołania obsługuje symulator.

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
  site: (path) => SDK.fetchJSON(`${API_ROOT}/site`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }),
  reveal: (path) => SDK.fetchJSON(`${API_ROOT}/reveal`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }),
  host: () => SDK.fetchJSON(`${API_ROOT}/host`),
  async fileBlob(path) {
    const res = await rawFetch(`${API_ROOT}/file?path=${encodeURIComponent(path)}`);
    return res.blob();
  },
  async *send(name, message) {
    const res = await rawFetch(`${API_ROOT}/chat/${encodeURIComponent(name)}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ message }),
    });
    yield* readSSE(res);
  },
};

const api = window.TARS_HQ_MOCK || liveApi;

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
  const w = window.open("", "_blank");
  if (w) { w.opener = null; w.document.title = "Uruchamiam…"; }
  try {
    const r = await api.site(path);
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
