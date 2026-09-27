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
