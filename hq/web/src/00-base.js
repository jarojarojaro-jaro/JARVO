// Jarvo HQ: wspólne podstawy. Pliki src/*.js są sklejane (w kolejności nazw) w jedno IIFE
// przez scripts/build.py, więc stałe z tego pliku są widoczne w następnych.

const SDK = window.__HERMES_PLUGIN_SDK__;
const React = SDK.React;
const { useState, useEffect, useRef, useMemo, useCallback } = SDK.hooks;
const html = htm.bind(React.createElement);

const PLUGIN = "jarvo-hq";

const cx = (...xs) => xs.filter(Boolean).join(" ");

// Język HQ = język dashboardu Hermesa (przełącznik w lewym dolnym rogu). Polski albo angielski:
// każdy inny język dashboardu dostaje angielskie HQ. Bez jawnego wyboru w przełączniku: polski.
// App ustawia HQ_LANG z kontekstu i18n przy każdym renderze (<html lang> zmienia się dopiero po renderze).
let HQ_LANG = null;
function chosenLocale() {
  try { return localStorage.getItem("hermes-locale"); } catch (_) { return null; }
}
const isPL = () => {
  const chosen = chosenLocale();
  return !chosen || String(HQ_LANG || chosen).toLowerCase().startsWith("pl");
};
const L = (pl, en) => (isPL() ? pl : en);
const txt = L;   // dla funkcji rysujących wieżę (tam `L` to warstwy sceny)
// język dashboardu Hermesa (kontekst i18n); pakiet Starej Bazy ustawia go tą funkcją, bo nie widzi `let` rdzenia
const useHostI18n = (SDK && SDK.useI18n) || (() => null);
function ustawJezyk(l) { HQ_LANG = l; }

// Pakiety na żądanie (docs/HQ.md §2f): build (scripts/hqbuild.py) wstawia mapę {nazwa: {js, css, zalezy}} w miejsce
// znacznika; w pełnym pakiecie (demo, testy) mapy nie ma i wszystko jest już wczytane. Pakiet rejestruje swoje nazwy
// przez W.__pakiet; zależności (Stara Baza ↔ edytor) ładują się równolegle, a nazwy z drugiego pakietu dostają
// wartość, gdy ten dojdzie. Wejście pakietu (komponent) bierze się przez Zasoby.wez po Zasoby.daj w pliku pakietu.
const Zasoby = (() => {
  const P = ((m) => (typeof m === "object" ? m : null))("@@PAKIETY@@");
  const W = window.__JARVO_W__ = window.__JARVO_W__ || {};
  const skrypt = document.currentScript;
  const baza = ((skrypt && skrypt.src) || "").replace(/[^/]*$/, "");
  const pliki = {}, uzup = [], gotowe = new Set();
  W.__pakiet = (nazwa, eksport, uzupelnij) => {
    Object.assign(W, eksport);
    uzup.push(uzupelnij);
    uzup.forEach((f) => f());
    gotowe.add(nazwa);
  };
  const plik = (url, css) => pliki[url] || (pliki[url] = new Promise((ok, nie) => {
    const el = document.createElement(css ? "link" : "script");
    if (css) { el.rel = "stylesheet"; el.href = url; setTimeout(ok, 3000); } else { el.src = url; el.async = true; }
    el.onload = ok;
    el.onerror = () => (css ? ok() : nie(new Error(`nie wczytano ${url}`)));
    (css ? document.head : document.body).appendChild(el);
  }).catch((e) => { delete pliki[url]; throw e; }));
  const zbior = (nazwa) => {
    const z = new Set(), kolejka = [nazwa];
    while (kolejka.length) {
      const n = kolejka.shift();
      if (z.has(n) || !P[n]) continue;
      z.add(n);
      kolejka.push(...(P[n].zalezy || []));
    }
    return [...z];
  };
  return {
    gotowy: (nazwa) => !P || !P[nazwa] || zbior(nazwa).every((n) => gotowe.has(n) || !P[n].js),
    wczytaj(nazwa) {
      if (!P || !P[nazwa]) return Promise.resolve();
      return Promise.all(zbior(nazwa).flatMap((n) => [P[n].js && plik(baza + P[n].js), P[n].css && plik(baza + P[n].css, true)]
        .filter(Boolean))).then(() => undefined);
    },
    daj: (nazwy) => Object.assign(W, nazwy),
    wez: (nazwa) => W[nazwa],
  };
})();

// Pakiet na żądanie w komponencie: "ok" | "laduje" | "blad"; null = nic nie trzeba.
function usePakiet(nazwa) {
  const [stan, ustaw] = useState(() => (!nazwa || Zasoby.gotowy(nazwa) ? "ok" : "laduje"));
  useEffect(() => {
    if (!nazwa || Zasoby.gotowy(nazwa)) { ustaw("ok"); return undefined; }
    let zywy = true;
    ustaw("laduje");
    Zasoby.wczytaj(nazwa).then(() => zywy && ustaw("ok"), () => zywy && ustaw("blad"));
    return () => { zywy = false; };
  }, [nazwa]);
  return stan;
}

// Komponent z pakietu na żądanie: rysuje `zastepczy`, dopóki pakiet się wczytuje (albo gdy się nie wczytał).
function Leniwy({ pakiet, nazwa, zastepczy = null, ...p }) {
  const C = usePakiet(pakiet) === "ok" ? Zasoby.wez(nazwa) : null;
  return C ? html`<${C} ...${p}/>` : zastepczy;
}

// Agent w bieżącym języku: po angielsku nazwa pokoju, rola, opis i cechy z fleet.yaml (pole `en`).
const localAgent = (a) => (!a || isPL() || !a.en ? a : { ...a, ...a.en });

// Słownik z tekstami w obu językach: obj.klucz zwraca tekst w bieżącym języku.
const bilingual = (pairs) => Object.defineProperties({}, Object.fromEntries(
  Object.entries(pairs).map(([k, [pl, en]]) => [k, { get: () => L(pl, en), enumerable: true }])));

const STATUS_TEXT = bilingual({
  working: ["Pracuje", "Working"], judging: ["Ocenia", "Reviewing"], blocked: ["Czeka na decyzję", "Needs a decision"],
  review: ["Czeka na ocenę", "Awaiting review"], queued: ["Ma kolejkę", "Has a queue"], idle: ["Wolny", "Idle"],
  offline: ["Poza siecią", "Offline"],
});
const STATUS_TONE = { working: "work", judging: "work", blocked: "bad", review: "warn", queued: "info", idle: "idle", offline: "idle" };
const STATUS = Object.fromEntries(Object.keys(STATUS_TONE).map((k) => [k, { tone: STATUS_TONE[k], get label() { return STATUS_TEXT[k]; } }]));

const CARD_STATUS = bilingual({
  triage: ["do rozpisania", "triage"], todo: ["w planie", "planned"], ready: ["gotowa", "ready"], scheduled: ["zaplanowana", "scheduled"],
  running: ["w toku", "in progress"], review: ["ocena", "review"], blocked: ["blokada", "blocked"], done: ["zrobione", "done"],
  archived: ["archiwum", "archived"],
});

function ago(ts, now) {
  if (!ts) return "";
  const s = Math.max(0, Math.round((now || Date.now() / 1000) - ts));
  if (s < 45) return L("teraz", "now");
  if (s < 3600) return L(`${Math.round(s / 60)} min temu`, `${Math.round(s / 60)} min ago`);
  if (s < 86400) return L(`${Math.round(s / 3600)} h temu`, `${Math.round(s / 3600)} h ago`);
  return L(`${Math.round(s / 86400)} d temu`, `${Math.round(s / 86400)} d ago`);
}

function duration(ts, now) {
  if (!ts) return "";
  const s = Math.max(0, Math.round((now || Date.now() / 1000) - ts));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
}

function clock(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString(L("pl-PL", "en-GB"), { hour: "2-digit", minute: "2-digit" });
}

function bytes(n) {
  if (n == null) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}

function usePoll(fn, ms, deps) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let alive = true;
    let timer = null;
    const tick = async () => {
      try {
        const d = await fn();
        if (alive) { setData(d); setError(null); usePoll.lastOk = Date.now() / 1000; }
      } catch (e) {
        if (alive) setError(e && e.message ? e.message : String(e));
      }
      if (alive) timer = setTimeout(tick, document.hidden ? ms * 4 : ms);
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, deps);
  return [data, error];
}

// Rodzaj pliku po rozszerzeniu (jak KIND_BY_EXT w hq_core.py).
const KIND_BY_EXT = {
  png: "image", jpg: "image", jpeg: "image", webp: "image", avif: "image", gif: "image", svg: "image",
  mp4: "video", webm: "video", mov: "video", mp3: "audio", wav: "audio", m4a: "audio", aac: "audio", ogg: "audio", flac: "audio", opus: "audio", pdf: "pdf", md: "text", txt: "text", csv: "text", json: "text", srt: "text",
  html: "html", htm: "html", zip: "archive", docx: "doc", xlsx: "doc", pptx: "doc",
};
const kindOf = (path) => KIND_BY_EXT[String(path).split(".").pop().toLowerCase()] || "other";
// nazwa: ostatni człon ścieżki (Sciezki.nazwa: przy korzeniu z literą dysku także po „\”)
const fileFromPath = (path) => ({ path, name: Sciezki.nazwa(path), rel: Sciezki.nazwa(path), kind: kindOf(path) });

// Otwieranie plików floty z dowolnego miejsca (czat, karta): App podaje funkcję przez kontekst.
const FileCtx = React.createContext(null);

function PathLink({ path }) {
  const open = React.useContext(FileCtx);
  const clean = path.replace(/[.,;:!?)]+$/, "");
  const tail = path.slice(clean.length);
  if (!open) return html`<code>${path}</code>`;
  return html`<span><button type="button" class="thq-pathlink" onClick=${() => open(fileFromPath(clean))}
    title=${L("Otwórz podgląd", "Open preview")}>${Sciezki.krotka(clean)}</button>${tail}</span>`;
}

// Minimalny, bezpieczny markdown dla odpowiedzi agentów: akapity, listy, **pogrubienie**, `kod`, linki,
// gołe adresy http(s), ścieżki plików floty (klik = podgląd) i obrazy data:image (z odpowiedzi gatewaya).
// FLOTA w wzorze = początek ścieżki floty: /opt/data i korzeń instalacji natywnej (Sciezki.wzor, 07-sciezki.js).
const WZOR_LINII_BAZY = /(!\[[^\]]*\]\((data:image\/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=]+)\)|\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\((https?:\/\/[^)\s]+)\)|https?:\/\/[^\s<>()`]+[^\s<>()`.,;:!?'"]|FLOTA[^\s`'"<>()]+)/.source;

function renderInline(text, keyBase) {
  const out = [];
  const re = new RegExp(Sciezki.wzor("baza.linia", ({ poczatek }) => WZOR_LINII_BAZY.replace("FLOTA", () => poczatek)), "g");
  let last = 0, m, i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    const k = `${keyBase}-${i++}`;
    if (tok.startsWith("![")) out.push(html`<img key=${k} class="thq-md-img" src=${m[2]} alt=""/>`);
    else if (tok.startsWith("**")) out.push(html`<strong key=${k}>${tok.slice(2, -2)}</strong>`);
    else if (tok.startsWith("`")) {
      const inner = tok.slice(1, -1);
      out.push(Sciezki.flota(inner, false) ? html`<${PathLink} key=${k} path=${inner}/>` : html`<code key=${k}>${inner}</code>`);
    } else if (tok.startsWith("[")) {
      const label = tok.slice(1, tok.indexOf("]"));
      out.push(html`<a key=${k} href=${m[3]} target="_blank" rel="noopener noreferrer">${label}</a>`);
    } else if (tok.startsWith("http")) {
      out.push(html`<a key=${k} href=${tok} target="_blank" rel="noopener noreferrer">${tok}</a>`);
    } else out.push(html`<${PathLink} key=${k} path=${tok}/>`);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

// Linia „MEDIA:/ścieżka” (plik od agenta, konwencja Hermesa) albo „📎 /ścieżka” (załącznik od Ciebie): Sciezki.linia.
function Markdown({ text }) {
  const MEDIA_LINE = Sciezki.linia();
  const blocks = String(text || "").replace(/\r/g, "").split(/\n{2,}/);
  return html`<div class="thq-md">${blocks.map((b, bi) => {
    const lines = b.split("\n").filter((l) => l.trim());
    if (!lines.length) return null;
    if (/^```/.test(b)) return html`<pre key=${bi}><code>${b.replace(/^```\w*\n?|```$/g, "")}</code></pre>`;
    // pliki (MEDIA: / 📎) wyjmujemy z akapitu jako miniatury, reszta akapitu zostaje tekstem
    const media = lines.filter((l) => MEDIA_LINE.test(l));
    if (media.length) {
      const rest = lines.filter((l) => !MEDIA_LINE.test(l) && !/^Załączniki \(pliki na dysku floty\):\s*$/.test(l)).join("\n");
      return html`<div key=${bi}>${rest ? html`<${Markdown} text=${rest}/>` : null}
        <div class="thq-media-row">${media.map((l, li) => html`<${MediaFile} key=${li} path=${MEDIA_LINE.exec(l)[1]}/>`)}</div></div>`;
    }
    if (lines.every((l) => /^\s*([-*]|\d+\.)\s+/.test(l))) {
      const ordered = /^\s*\d+\./.test(lines[0]);
      const items = lines.map((l, li) => html`<li key=${li}>${renderInline(l.replace(/^\s*([-*]|\d+\.)\s+/, ""), `${bi}-${li}`)}</li>`);
      return ordered ? html`<ol key=${bi}>${items}</ol>` : html`<ul key=${bi}>${items}</ul>`;
    }
    const h = /^(#{1,3})\s+(.*)/.exec(b);
    if (h && lines.length === 1) return html`<p key=${bi} class="thq-md-h">${renderInline(h[2], bi)}</p>`;
    return html`<p key=${bi}>${lines.map((l, li) => html`<span key=${li}>${li ? html`<br/>` : null}${renderInline(l, `${bi}-${li}`)}</span>`)}</p>`;
  })}</div>`;
}
