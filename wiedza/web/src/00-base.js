// Zakładka „Wiedza” (skarbiec wiedzy floty): wspólne podstawy. Pliki src/*.js są sklejane (w kolejności nazw)
// w jedno IIFE przez scripts/build.py (jak Jarvo HQ), więc stałe z tego pliku są widoczne w następnych.

const SDK = window.__HERMES_PLUGIN_SDK__;
const React = SDK.React;
const { useState, useEffect, useRef, useMemo, useCallback } = SDK.hooks;
const html = htm.bind(React.createElement);

const PLUGIN = "jarvo-wiedza";
const API_ROOT = `/api/plugins/${PLUGIN}`;
const cx = (...xs) => xs.filter(Boolean).join(" ");

// Język = język dashboardu Hermesa (przełącznik w lewym dolnym rogu): polski albo angielski.
let WZ_LANG = null;
function chosenLocale() {
  try { return localStorage.getItem("hermes-locale"); } catch (_) { return null; }
}
const isPL = () => { const c = chosenLocale(); return !c || String(WZ_LANG || c).toLowerCase().startsWith("pl"); };
const L = (pl, en) => (isPL() ? pl : en);
const bilingual = (pairs) => Object.defineProperties({}, Object.fromEntries(
  Object.entries(pairs).map(([k, [pl, en]]) => [k, { get: () => L(pl, en), enumerable: true }])));

const FOLDER_NAMES = bilingual({
  "": ["Skarbiec", "Vault"], agenci: ["Agenci", "Agents"], projekty: ["Projekty", "Projects"], brands: ["Marki", "Brands"],
  user: ["Ty", "You"], podmioty: ["Podmioty", "Entities"], pojecia: ["Pojęcia", "Concepts"], orzeczenia: ["Orzeczenia", "Rulings"],
  rozmowy: ["Rozmowy", "Conversations"], fleet: ["Flota", "Fleet"],
});
const FOLDER_COLORS = {
  agenci: "#2C6ED5", projekty: "#D98A00", brands: "#C2185B", user: "#1E9A61", podmioty: "#7B4FCF", pojecia: "#00897B",
  orzeczenia: "#D2392E", rozmowy: "#8793A2", fleet: "#5D4037", "": "#9AA6B4",
};
const folderName = (f) => FOLDER_NAMES[f] || f;
const folderColor = (f) => FOLDER_COLORS[f] || "#9AA6B4";

const TYPE_NAMES = bilingual({
  hub: ["hub", "hub"], agent: ["agent", "agent"], projekt: ["projekt", "project"], podmiot: ["podmiot", "entity"], pojecie: ["pojęcie", "concept"],
  fakt: ["fakt", "fact"], decyzja: ["decyzja", "decision"], lekcja: ["lekcja", "lesson"], zrodlo: ["źródło", "source"], rozmowa: ["rozmowa", "conversation"],
  orzeczenia: ["orzeczenia", "rulings"],
});
const STATUS_NAMES = bilingual({
  aktualna: ["aktualna", "current"], "do-sprawdzenia": ["do sprawdzenia", "to verify"], sprzeczna: ["sprzeczna", "contradictory"],
  przestarzala: ["przestarzała", "outdated"], generowane: ["generowane", "generated"],
});

function agoIso(iso) {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const d = Math.round((Date.now() - t) / 86400000);
  if (d <= 0) return L("dziś", "today");
  if (d === 1) return L("wczoraj", "yesterday");
  if (d < 30) return L(`${d} dni temu`, `${d} days ago`);
  return iso;
}
function agoTs(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return L("przed chwilą", "just now");
  if (s < 3600) return L(`${Math.round(s / 60)} min temu`, `${Math.round(s / 60)} min ago`);
  if (s < 86400) return L(`${Math.round(s / 3600)} h temu`, `${Math.round(s / 3600)} h ago`);
  return L(`${Math.round(s / 86400)} d temu`, `${Math.round(s / 86400)} d ago`);
}

function usePoll(fn, ms, deps) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true, timer = null;
    const run = () => fn().then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e) => { if (alive) setError(e.message || String(e)); })
      .finally(() => { if (alive && ms) timer = setTimeout(run, ms); });
    run();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [...(deps || []), tick]);
  return [data, error, () => setTick((t) => t + 1)];
}

const post = (path, body) => SDK.fetchJSON(`${API_ROOT}${path}`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}),
});
const api = {
  overview: () => SDK.fetchJSON(`${API_ROOT}/overview`),
  tree: () => SDK.fetchJSON(`${API_ROOT}/tree`),
  note: (path) => SDK.fetchJSON(`${API_ROOT}/note?path=${encodeURIComponent(path)}`),
  graph: () => SDK.fetchJSON(`${API_ROOT}/graph`),
  search: (q, folder) => SDK.fetchJSON(`${API_ROOT}/search?q=${encodeURIComponent(q)}${folder ? `&folder=${encodeURIComponent(folder)}` : ""}`),
  inbox: () => SDK.fetchJSON(`${API_ROOT}/inbox`),
  log: () => SDK.fetchJSON(`${API_ROOT}/log?n=60`),
  lint: (refresh) => SDK.fetchJSON(`${API_ROOT}/lint${refresh ? "?refresh=1" : ""}`),
  rulings: () => SDK.fetchJSON(`${API_ROOT}/rulings`),
  addRuling: (kogo, tresc) => post("/rulings", { kogo, tresc, zrodlo: "człowiek, zakładka Wiedza" }),
  remark: (path, uwaga) => post("/remark", { path, uwaga }),
  compile: () => post("/compile"),
  compileStatus: () => SDK.fetchJSON(`${API_ROOT}/compile`),
  reindex: () => post("/reindex"),
};
