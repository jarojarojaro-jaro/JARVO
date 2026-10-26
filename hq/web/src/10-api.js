// Klient API pluginu. W trybie demo (window.JARVO_HQ_MOCK) te same wywołania obsługuje symulator.

const API_ROOT = `/api/plugins/${PLUGIN}`;

function basePath() {
  const raw = window.__HERMES_BASE_PATH__ || "";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

// Dashboard z logowaniem rozpoznaje sesję po ciasteczku (credentials: "include"); bez logowania (tylko 127.0.0.1)
// Hermes wstrzykuje token sesji, którego wymaga każda trasa /api/. Nagłówek X-Jarvo-Request mówi ochronie zapisu
// (hq/plugin/ochrona.py), że żądanie przyszło z panelu: strona z innego pochodzenia nie może go dodać bez zapytania
// wstępnego CORS, którego dashboard z ciasteczkiem nie przepuści.
function authHeaders(extra) {
  const h = Object.assign({ "X-Jarvo-Request": "1" }, extra || {});
  const token = window.__HERMES_SESSION_TOKEN__;
  if (token) h["X-Hermes-Session-Token"] = token;
  return h;
}

// SDK.fetchJSON (JSON z obsługą wylogowania) z nagłówkiem panelu; tym idą wszystkie trasy JSON pluginu
const jsonFetch = (url, init) => SDK.fetchJSON(url, { ...(init || {}), headers: authHeaders(init && init.headers) });

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
      msg = (body.blad && body.blad.komunikat) || body.detail || body.error || msg;
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
  state: () => jsonFetch(`${API_ROOT}/state`),
  fleet: () => jsonFetch(`${API_ROOT}/fleet`),
  agent: (name) => jsonFetch(`${API_ROOT}/agent/${encodeURIComponent(name)}`),
  task: (id) => jsonFetch(`${API_ROOT}/task/${encodeURIComponent(id)}`),
  history: (name) => jsonFetch(`${API_ROOT}/chat/${encodeURIComponent(name)}/history`),
  reset: (name) => jsonFetch(`${API_ROOT}/chat/${encodeURIComponent(name)}/reset`, { method: "POST" }),
  retry: (id) => jsonFetch(`${API_ROOT}/task/${encodeURIComponent(id)}/retry`, { method: "POST" }),
  async upload(file) {
    const res = await rawFetch(`${API_ROOT}/upload`, {
      method: "POST", headers: { "Content-Type": "application/octet-stream", "X-File-Name": encodeURIComponent(file.name || "plik") }, body: file,
    });
    return res.json();
  },
  // konwerter w Centrali: wysyłka z postępem (XHR; fetch nie mówi, ile już poszło), cele, zadanie w tle
  konwUpload(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${basePath()}${API_ROOT}/konwerter/upload`);
      xhr.withCredentials = true;
      const h = authHeaders({ "Content-Type": "application/octet-stream", "X-File-Name": encodeURIComponent(file.name || "plik") });
      Object.entries(h).forEach(([k, v]) => xhr.setRequestHeader(k, v));
      xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
      xhr.onload = () => {
        let body = null;
        try { body = JSON.parse(xhr.responseText); } catch (_) { /* nie-JSON */ }
        if (xhr.status >= 200 && xhr.status < 300 && body) resolve(body);
        else reject(new Error((body && (body.detail || body.error)) || `HTTP ${xhr.status}`));
      };
      xhr.onerror = () => reject(new Error(L("Wysyłka przerwana", "Upload interrupted")));
      xhr.send(file);
    });
  },
  async konwCele(path) {
    const res = await rawFetch(`${API_ROOT}/konwerter/cele?path=${encodeURIComponent(path)}`);
    return res.json();
  },
  async konwStart(body) {
    const res = await rawFetch(`${API_ROOT}/konwerter`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    return res.json();
  },
  async konwJob(id) {
    const res = await rawFetch(`${API_ROOT}/konwerter/job/${encodeURIComponent(id)}`);
    return res.json();
  },
  site: (path) => jsonFetch(`${API_ROOT}/site`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }),
  android: () => jsonFetch(`${API_ROOT}/android`, { method: "POST" }),
  flota: () => jsonFetch(`${API_ROOT}/flota`),       // figura floty w Centrali: {port, path} serwera podglądu
  reveal: (path) => jsonFetch(`${API_ROOT}/reveal`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }),
  host: () => jsonFetch(`${API_ROOT}/host`),
  async fileBlob(path) {
    const res = await rawFetch(`${API_ROOT}/file?path=${encodeURIComponent(path)}`);
    return res.blob();
  },
  editInfo: (path) => jsonFetch(`${API_ROOT}/edit/info?path=${encodeURIComponent(path)}`),
  editMedia: (path) => jsonFetch(`${API_ROOT}/edit/media?path=${encodeURIComponent(path)}`),
  editMaska: (path) => jsonFetch(`${API_ROOT}/edit/maska?path=${encodeURIComponent(path)}`),
  // menu Audio: biblioteka CC0, muzyka ze skarbca, wyodrębnienie, lektor, nagranie (każde zwraca opis pliku obok filmu)
  editDzwieki: () => jsonFetch(`${API_ROOT}/edit/dzwieki`),
  async dzwiekBlob(id) {
    const res = await rawFetch(`${API_ROOT}/edit/dzwiek-plik?id=${encodeURIComponent(id)}`);
    return res.blob();
  },
  editDzwiek: (path, id) => jsonFetch(`${API_ROOT}/edit/dzwiek`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, id }) }),
  editMuzyka: () => jsonFetch(`${API_ROOT}/edit/muzyka`),
  async editWyodrebnij(path, src) {
    const res = await rawFetch(`${API_ROOT}/edit/wyodrebnij`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, src }) });
    return res.json();
  },
  async editKolorAuto(src, inn, out) {
    const res = await rawFetch(`${API_ROOT}/edit/kolor-auto`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ src, in: inn, out }) });
    return res.json();
  },
  // czysty głos klipu albo audio: tło nagrania i poziom „Auto”, odsłuch 8 s po czyszczeniu (edytor.glos_filter)
  async editGlosTlo(src, inn, out) {
    const res = await rawFetch(`${API_ROOT}/edit/glos-tlo`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ src, in: inn, out }) });
    return res.json();
  },
  async editGlosProbka(src, inn, out, voice, od) {
    const res = await rawFetch(`${API_ROOT}/edit/glos-probka`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ src, in: inn, out, voice, od }) });
    return res.blob();
  },
  async editLektor(path, text, glos, tempo) {
    const res = await rawFetch(`${API_ROOT}/edit/lektor`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, text, glos, tempo }) });
    return res.json();
  },
  async editNagranie(path, blob) {
    const res = await rawFetch(`${API_ROOT}/edit/nagranie`, { method: "POST", headers: { "Content-Type": "application/octet-stream", "X-Film-Path": encodeURIComponent(path) }, body: blob });
    return res.json();
  },
  async editSave(path, project, base, force) {
    const res = await fetch(`${basePath()}${API_ROOT}/edit/save`, { method: "POST", credentials: "include",
      headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ path, project, base, force: !!force }) });
    if (res.status === 409) { const e = new Error("conflict"); e.conflict = true; throw e; }
    if (!res.ok) { let m = `HTTP ${res.status}`; try { m = (await res.json()).detail || m; } catch (_) { /* nie-JSON */ } throw new Error(m); }
    return res.json();
  },
  editStamp: (path) => jsonFetch(`${API_ROOT}/edit/stamp?path=${encodeURIComponent(path)}`),
  async editExport(path, project, texts, karaoke, typo) {
    const res = await rawFetch(`${API_ROOT}/edit/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, project, texts, karaoke: karaoke || {}, typo: typo || {} }) });
    return res.json();
  },
  editSrt: (path) => jsonFetch(`${API_ROOT}/edit/srt?path=${encodeURIComponent(path)}`),
  editSpeechGet: (src) => jsonFetch(`${API_ROOT}/edit/speech?src=${encodeURIComponent(src)}`),
  editSpeech: (src, force) => jsonFetch(`${API_ROOT}/edit/speech`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ src, force: !!force }) }),
  editProxy: (src) => jsonFetch(`${API_ROOT}/edit/proxy`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ src }) }),
  async proxyBlob(src) {
    const res = await rawFetch(`${API_ROOT}/edit/proxy-file?src=${encodeURIComponent(src)}`);
    return res.blob();
  },
  editJob: (id) => jsonFetch(`${API_ROOT}/edit/job/${encodeURIComponent(id)}`),
  // POST: wydaje link podglądu z tokenem (zapis w state/preview-links.json), więc idzie przez ochronę zapisu
  animInfo: (path) => jsonFetch(`${API_ROOT}/anim/info`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }),
  animCheck: (path) => jsonFetch(`${API_ROOT}/anim/check?path=${encodeURIComponent(path)}`),
  async animParams(path, wartosci) {
    const res = await fetch(`${basePath()}${API_ROOT}/anim/params`, { method: "POST", credentials: "include",
      headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ path, wartosci }) });
    if (!res.ok) { let m = `HTTP ${res.status}`; try { m = (await res.json()).detail || m; } catch (_) { /* nie-JSON */ } throw new Error(m); }
    return res.json();
  },
  editCancel: (id) => jsonFetch(`${API_ROOT}/edit/job/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  async *send(name, message, extra) {
    const res = await rawFetch(`${API_ROOT}/chat/${encodeURIComponent(name)}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ message, ...(extra || {}) }),
    });
    yield* readSSE(res);
  },
};

// ---- klient silnika rozmów (docs/HQ.md „Rozmowy” i „Aplikacja”) ----------------------------------------------------
// Błąd trasy: {"blad": {kod, komunikat, komunikat_en, ...dane}}. kod "siec" = brak połączenia, "http_<status>" = odpowiedź
// bez opisu. 429 niesie ponow_za_s, 409 praca_trwa {przebiegi, karty}, 413 za_duze, 507 dysk, 503 silnik.
class BladApi extends Error {
  constructor(status, cialo) {
    const b = (cialo && cialo.blad) || {};
    super(b.komunikat || `HTTP ${status}`);
    this.status = status;
    this.kod = b.kod || (status ? `http_${status}` : "siec");
    this.komunikat = b.komunikat || "";
    this.komunikat_en = b.komunikat_en || "";
    this.dane = b;
    this.ponow_za_s = b.ponow_za_s || null;
  }
  // tekst dla właściciela w bieżącym języku: z serwera, a bez opisu ogólny z słownika
  tekst() {
    const t = isPL() ? this.komunikat : this.komunikat_en || this.komunikat;
    return t || T(this.kod === "siec" ? "blad.siec" : "blad.ogolny");
  }
}

// Panel bez logowania (instalacja natywna na 127.0.0.1, docs/NATYWNIE.md I11): Hermes nie ma wtedy strony logowania,
// tylko wstrzykuje token sesji do index.html, a token żyje tyle, co proces dashboardu.
const bezLogowania = () => window.__HERMES_AUTH_REQUIRED__ === false;
const KLUCZ_ODSWIEZENIA = "jarvo.odswiezenie_401";

// 401: sesja wygasła albo wylogowano w innej karcie. Hash zostaje w sessionStorage i wraca po zalogowaniu.
// Tylko jedno przejście: kilka zapytań z 401 naraz (lista, strumień, subskrypcje) dałoby kilka location.assign,
// a każde następne przerywa poprzednie; powrót z bfcache (pageshow) znów pozwala przejść.
// Bez logowania 401 znaczy, że panel wstał od nowa z nowym tokenem: świeża strona go ma, więc przeładowanie /jarvo
// (hash wraca z sessionStorage); najwyżej raz na 20 s, żeby 401 z innej przyczyny nie kręciło stroną w kółko (W11).
let wLogowaniu = false;
function naLogowanie() {
  if (wLogowaniu) return;
  if (bezLogowania()) {
    let ostatnie = 0;
    try { ostatnie = Number(sessionStorage.getItem(KLUCZ_ODSWIEZENIA)) || 0; } catch (_) { /* tryb prywatny */ }
    if (Date.now() - ostatnie < 20000) return;
    try { sessionStorage.setItem(KLUCZ_ODSWIEZENIA, String(Date.now())); } catch (_) { /* jw. */ }
    wLogowaniu = true;
    Trasa.zapamietaj();
    location.replace(`${basePath()}/jarvo`);
    return;
  }
  wLogowaniu = true;
  Trasa.zapamietaj();
  location.assign(`${basePath()}/login?next=${encodeURIComponent(basePath() + "/jarvo")}`);
}
if (typeof window !== "undefined") window.addEventListener("pageshow", (e) => { if (e.persisted) wLogowaniu = false; });

// JSON w obie strony. Zapisy niosą X-Jarvo-Request (authHeaders). `ponawiaj`: 429 czeka ponow_za_s i próbuje
// najwyżej dwa razy (tylko żądania z kluczem, które serwer rozpoznaje jako powtórkę).
// `korzen`: "" = trasa Hermesa (/api/…), nie pluginu; błąd Hermesa ({detail}) w kształcie błędów aplikacji
async function zadanie(metoda, sciezka, cialo, { ponawiaj = false, bez401 = false, korzen = API_ROOT } = {}) {
  const init = { method: metoda, credentials: "include", cache: "no-store",
    headers: authHeaders(cialo === undefined ? null : { "Content-Type": "application/json" }) };
  if (cialo !== undefined) init.body = JSON.stringify(cialo);
  for (let proba = 0; ; proba++) {
    let r;
    try { r = await fetch(`${basePath()}${korzen}${sciezka}`, init); } catch (_) { throw new BladApi(0, null); }
    if (r.status === 204) return null;
    let d = null;
    try { d = await r.json(); } catch (_) { /* puste albo nie-JSON */ }
    if (r.ok) return d;
    if (r.status === 401 && !bez401) naLogowanie();
    const b = new BladApi(r.status, d && !d.blad && typeof d.detail === "string" ? { blad: { komunikat: d.detail } } : d);
    if (r.status === 429 && ponawiaj && proba < 2) {
      await new Promise((ok) => setTimeout(ok, Math.min(10, Math.max(1, b.ponow_za_s || 1)) * 1000));
      continue;
    }
    throw b;
  }
}

const zapytanieUrl = (p) => {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(p || {})) if (v != null && v !== "") q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : "";
};
const kodujUrl = encodeURIComponent;

Object.assign(liveApi, {
  rozmowy: {
    lista: (p) => zadanie("GET", `/rozmowy${zapytanieUrl(p)}`),                 // {filtr, q, limit, przed}
    utworz: (cialo) => zadanie("POST", "/rozmowy", cialo, { ponawiaj: !!cialo.wiadomosc }),   // {tytul, koordynator, wiadomosc?}
    wez: (id) => zadanie("GET", `/rozmowy/${kodujUrl(id)}`),
    zmien: (id, zmiana) => zadanie("PATCH", `/rozmowy/${kodujUrl(id)}`, zmiana),   // {tytul?, przypiety?, archiwum?, praca?}
    usun: (id, { trwale = false, praca } = {}) => zadanie("DELETE", `/rozmowy/${kodujUrl(id)}${zapytanieUrl({ trwale: trwale ? 1 : 0, praca })}`),
    przywroc: (id) => zadanie("POST", `/rozmowy/${kodujUrl(id)}/przywroc`),
    przeczytane: (id, doAt) => zadanie("POST", `/rozmowy/${kodujUrl(id)}/przeczytane`, { do_at: doAt }),
    os: (id, p) => zadanie("GET", `/rozmowy/${kodujUrl(id)}/os${zapytanieUrl(p)}`),   // {przed, po, limit}
    wyslij: (id, cialo) => zadanie("POST", `/rozmowy/${kodujUrl(id)}/wiadomosci`, cialo, { ponawiaj: true }),
    eksportUrl: (id) => `${basePath()}${API_ROOT}/rozmowy/${kodujUrl(id)}/eksport`,
    // plik Markdown całej rozmowy: {blob, nazwa} (pobranie przez <a download>, nazwa z Content-Disposition)
    async eksport(id) {
      let r;
      try { r = await fetch(liveApi.rozmowy.eksportUrl(id), { credentials: "include", cache: "no-store", headers: authHeaders() }); } catch (_) { throw new BladApi(0, null); }
      if (!r.ok) { let d = null; try { d = await r.json(); } catch (_) { /* nie-JSON */ } if (r.status === 401) naLogowanie(); throw new BladApi(r.status, d); }
      const m = /filename="([^"]+)"/.exec(r.headers.get("content-disposition") || "");
      return { blob: await r.blob(), nazwa: m ? m[1] : "rozmowa.md" };
    },
  },
  przebiegi: {
    wez: (id) => zadanie("GET", `/przebiegi/${kodujUrl(id)}`),
    stop: (id) => zadanie("POST", `/przebiegi/${kodujUrl(id)}/stop`),
    anuluj: (id) => zadanie("POST", `/przebiegi/${kodujUrl(id)}/anuluj`),
    wyslijTeraz: (id) => zadanie("POST", `/przebiegi/${kodujUrl(id)}/wyslij`),
    zgoda: (id, wybor, requestId) => zadanie("POST", `/przebiegi/${kodujUrl(id)}/zgoda`, { wybor, request_id: requestId }),
    dopisz: (id, tekst, klucz) => zadanie("POST", `/przebiegi/${kodujUrl(id)}/dopisz`, { tekst, klucz }, { ponawiaj: !!klucz }),
    ponow: (id) => zadanie("POST", `/przebiegi/${kodujUrl(id)}/ponow`),
    nadzor: (id) => zadanie("POST", `/przebiegi/${kodujUrl(id)}/nadzor`),
  },
  // karty pracy w wątku (przekazania Jarva): stan z tablicy i sesji pracownika; {karty: {id: karta}} / {karta}
  karty: {
    stan: (ids) => zadanie("GET", `/karty${zapytanieUrl({ id: (ids || []).join(",") })}`),
    wez: (id) => zadanie("GET", `/karty/${kodujUrl(id)}`),
  },
  // trasy z kolejnych etapów (§6.3): klient gotowy, serwer odpowie 404, dopóki ich nie ma
  sesje: {
    os: (profil, id, p) => zadanie("GET", `/sesje/${kodujUrl(profil)}/${kodujUrl(id)}/os${zapytanieUrl(p)}`),
    kontynuuj: (profil, id, wiadomosc) => zadanie("POST", `/sesje/${kodujUrl(profil)}/${kodujUrl(id)}/kontynuuj`, { wiadomosc }),
    kopiuj: (profil, id) => zadanie("POST", `/sesje/${kodujUrl(profil)}/${kodujUrl(id)}/kopiuj`, {}),
  },
  efekty: { lista: (p) => zadanie("GET", `/efekty${zapytanieUrl(p)}`) },
  aplikacja: () => zadanie("GET", "/app"),
  agenci: () => zadanie("GET", "/agenci"),
  flotaAgenci: () => zadanie("GET", "/fleet"),
  aktualizacjaStan: () => zadanie("GET", "/update"),
  // {action: update|cancel|check, gdy: teraz|wolne} (§15.3): „wolne” = po końcu pracy agentów
  aktualizacja: (action, gdy) => zadanie("POST", "/update", gdy ? { action, gdy } : { action }),
  podpowiedzi: (miejsce = "start") => zadanie("GET", `/podpowiedzi${zapytanieUrl({ miejsce })}`),
  reakcja: (id, rodzaj, klucz) => zadanie("POST", `/podpowiedzi/${kodujUrl(id)}/reakcja`, klucz ? { rodzaj, klucz } : { rodzaj }),
  // pierwsze spotkanie (37-poznajmy.js): {imie, firma, zajecie, linki: [{rodzaj, wartosc}], cele} → USER.md
  poznanie: (cialo) => zadanie("POST", "/app/poznanie", cialo),
  // mózg z karty pierwszego spotkania (hq/plugin/mozg.py): klucz API (nigdy w dzienniku ani w odpowiedzi) albo ChatGPT
  // kodem urządzenia przez trasy Hermesa; po zalogowaniu /app/mozg/chatgpt przełącza flotę na openai-codex
  klucz: (klucz) => zadanie("POST", "/app/klucz", { klucz }),
  mozgChatgpt: () => zadanie("POST", "/app/mozg/chatgpt", {}),
  chatgpt: {
    start: () => zadanie("POST", "/api/providers/oauth/openai-codex/start", undefined, { korzen: "" }),
    stan: (sid) => zadanie("GET", `/api/providers/oauth/openai-codex/poll/${kodujUrl(sid)}`, undefined, { korzen: "" }),
    anuluj: (sid) => zadanie("DELETE", `/api/providers/oauth/sessions/${kodujUrl(sid)}`, undefined, { korzen: "" }),
  },
  // pierwsza sesja: raz na instalację wątek „Pierwsza sesja” z pracą Jarva (skill pierwsza-sesja) → {watek_id, nowa}
  pierwszaSesja: (jezyk) => zadanie("POST", "/app/pierwsza-sesja", { jezyk }),
  // głos Jarva (36-glos.js): {tekst, glos, tempo, jezyk} → WAV (ArrayBuffer); 503 = instalacja bez lektora
  async glos(cialo) {
    let r;
    try {
      r = await fetch(`${basePath()}${API_ROOT}/app/glos`, { method: "POST", credentials: "include", cache: "no-store",
        headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(cialo) });
    } catch (_) { throw new BladApi(0, null); }
    if (!r.ok) { let d = null; try { d = await r.json(); } catch (_) { /* nie-JSON */ } if (r.status === 401) naLogowanie(); throw new BladApi(r.status, d); }
    return r.arrayBuffer();
  },
  glosPrzygotuj: (cialo) => zadanie("POST", "/app/glos/przygotuj", cialo),
  subskrypcje: (klient, cialo) => zadanie("POST", `/strumien/${kodujUrl(klient)}/subskrypcje`, cialo),
  // jak AuthWidget Hermesa: POST /auth/logout; pozostałe karty dostają „wyloguj” przez BroadcastChannel i idą na
  // logowanie z next=/jarvo (hash zostaje w sessionStorage każdej karty), ta karta też. Bez logowania (127.0.0.1) nie
  // ma z czego się wylogować: szuflada nie pokazuje wtedy przycisku, a wywołanie nic nie robi.
  async wyloguj() {
    if (bezLogowania()) return;
    try { await fetch(`${basePath()}/auth/logout`, { method: "POST", credentials: "include" }); } catch (_) { /* i tak na logowanie */ }
    try { const k = new BroadcastChannel("jarvo"); k.postMessage({ t: "wyloguj" }); k.close(); } catch (_) { /* bez kanału: karty pójdą na 401 */ }
    naLogowanie();
  },
});

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

// Co umie host (Eksplorator w WSL, podgląd stron, korzeń danych): pytamy raz na pół minuty, wszystkie okna dzielą
// wynik. Korzeń danych (`katalog_danych`) trafia do Sciezki: po nim rozpoznajemy ścieżki floty w tekście.
let hostCache = { at: 0, p: null };
function hostInfo() {
  if (!hostCache.p || Date.now() - hostCache.at > 30000) {
    hostCache = { at: Date.now(), p: api.host().then((h) => { if (h && h.katalog_danych) Sciezki.ustaw(h.katalog_danych); return h; })
      .catch(() => ({})) };
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
    const url = adresPodgladu(await get());
    if (w) w.location.href = url; else window.open(url, "_blank", "noopener");
  } catch (e) {
    if (w) w.close();
    throw e;
  }
}

async function downloadFile(file) {
  pobierzBlob(await api.fileBlob(file.path), file.name);
}

// blob tylko jako <a download> (docs/HQ.md „Aplikacja”, bezpieczeństwo: blob nigdy nie staje się stroną)
function pobierzBlob(b, nazwa) {
  const u = URL.createObjectURL(b);
  const a = document.createElement("a");
  a.href = u; a.download = nazwa || "plik";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(u), 5000);
}

// adres pliku floty na /file (CSP sandbox, nosniff, HTML jako tekst): „Otwórz w nowej karcie”, SVG w <img>, PDF
// w <iframe sandbox>. Dashboard z logowaniem rozpoznaje sesję po ciasteczku, więc zwykły adres działa.
const urlPliku = (path, pobierz) => `${basePath()}${API_ROOT}/file?path=${encodeURIComponent(path)}${pobierz ? "&download=1" : ""}`;

// Bez logowania (127.0.0.1, docs/NATYWNIE.md W11) /api/ wpuszcza tylko z nagłówkiem tokenu sesji, a <img>, <iframe>
// i nowa karta go nie wyślą. Wtedy SVG idzie jako data: (otwarty osobno ma nieprzezroczyste pochodzenie; blob miałby
// pochodzenie panelu i jego skrypty działałyby w sesji), a nowa karta i PDF przez link podglądu :9120 (CSP sandbox,
// osobny port, jak „Odpal”). Z logowaniem (ciasteczko) wszystko zostaje na /file.
const zTokenem = () => !!window.__HERMES_SESSION_TOKEN__;

function adresPodgladu(r) {
  return r.url || `${location.protocol}//${location.hostname}:${r.port}${r.path}`;
}

async function svgDataUrl(path) {
  const b = await api.fileBlob(path);
  return new Promise((ok, bad) => {
    const r = new FileReader();
    r.onload = () => ok(r.result);
    r.onerror = bad;
    r.readAsDataURL(new Blob([b], { type: "image/svg+xml" }));
  });
}

// adres obrazu SVG z dysku floty do <img>: /file albo (bez logowania) data:
function useSvgUrl(path) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!path) return undefined;
    if (!zTokenem()) { setUrl(urlPliku(path)); return undefined; }
    let alive = true;
    svgDataUrl(path).then((u) => alive && setUrl(u), () => alive && setUrl(null));
    return () => { alive = false; };
  }, [path]);
  return url;
}

// adres pliku do ramki i linku „w nowej karcie”: /file albo (bez logowania) link podglądu :9120; null = jeszcze nie
// ma, false = nie da się (podgląd stron nie działa)
function useAdresPliku(path) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!path) return undefined;
    if (!zTokenem()) { setUrl(urlPliku(path)); return undefined; }
    let alive = true;
    api.site(path).then((r) => alive && setUrl(adresPodgladu(r)), () => alive && setUrl(false));
    return () => { alive = false; };
  }, [path]);
  return url;
}

// „Otwórz w nowej karcie”: /file albo (bez logowania) link podglądu :9120 w karcie odciętej od panelu
function otworzPlik(path) {
  if (!zTokenem()) { window.open(urlPliku(path), "_blank", "noopener,noreferrer"); return Promise.resolve(); }
  return openTokenLink(() => api.site(path));
}

// Ścieżka do wklejenia w Eksploratorze/terminalu: po stronie Windows (WSL), hosta albo kontenera; w instalacji
// natywnej ścieżka na tym komputerze (stare /opt/data/… pod faktycznym korzeniem, na dysku Windows z „\”).
function hostPathOf(path, host) {
  const rest = path.startsWith("/opt/data/") ? path.slice("/opt/data/".length) : null;
  if (rest != null && host.data_win) return `${host.data_win.replace(/\\$/, "")}\\${rest.split("/").join("\\")}`;
  if (rest != null && host.data_host) return `${host.data_host.replace(/\/$/, "")}/${rest}`;
  return Sciezki.doSystemu(Sciezki.naDysk(path));
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
