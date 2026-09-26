// TARS HQ: wspólne podstawy. Pliki src/*.js są sklejane (w kolejności nazw) w jedno IIFE
// przez scripts/build.py, więc stałe z tego pliku są widoczne w następnych.

const SDK = window.__HERMES_PLUGIN_SDK__;
const React = SDK.React;
const { useState, useEffect, useRef, useMemo, useCallback } = SDK.hooks;
const html = htm.bind(React.createElement);

const PLUGIN = "tars-hq";

const cx = (...xs) => xs.filter(Boolean).join(" ");

const STATUS = {
  working: { label: "Pracuje", tone: "work" },
  judging: { label: "Ocenia", tone: "work" },
  blocked: { label: "Czeka na decyzję", tone: "bad" },
  review: { label: "Czeka na ocenę", tone: "warn" },
  queued: { label: "Ma kolejkę", tone: "info" },
  idle: { label: "Wolny", tone: "idle" },
  offline: { label: "Poza siecią", tone: "idle" },
};

const CARD_STATUS = {
  triage: "triage", todo: "w planie", ready: "gotowa", scheduled: "zaplanowana", running: "w toku",
  review: "ocena", blocked: "blokada", done: "zrobione", archived: "archiwum",
};

function ago(ts, now) {
  if (!ts) return "";
  const s = Math.max(0, Math.round((now || Date.now() / 1000) - ts));
  if (s < 45) return "teraz";
  if (s < 3600) return `${Math.round(s / 60)} min temu`;
  if (s < 86400) return `${Math.round(s / 3600)} h temu`;
  return `${Math.round(s / 86400)} d temu`;
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
  return d.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
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
        if (alive) { setData(d); setError(null); }
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

// Minimalny, bezpieczny markdown dla odpowiedzi agentów: akapity, listy, **pogrubienie**, `kod`, linki.
function renderInline(text, keyBase) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\((https?:\/\/[^)\s]+)\))/g;
  let last = 0, m, i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    const k = `${keyBase}-${i++}`;
    if (tok.startsWith("**")) out.push(html`<strong key=${k}>${tok.slice(2, -2)}</strong>`);
    else if (tok.startsWith("`")) out.push(html`<code key=${k}>${tok.slice(1, -1)}</code>`);
    else {
      const label = tok.slice(1, tok.indexOf("]"));
      out.push(html`<a key=${k} href=${m[2]} target="_blank" rel="noopener noreferrer">${label}</a>`);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Markdown({ text }) {
  const blocks = String(text || "").replace(/\r/g, "").split(/\n{2,}/);
  return html`<div class="thq-md">${blocks.map((b, bi) => {
    const lines = b.split("\n");
    if (lines.every((l) => /^\s*([-*]|\d+\.)\s+/.test(l))) {
      const ordered = /^\s*\d+\./.test(lines[0]);
      const items = lines.map((l, li) => html`<li key=${li}>${renderInline(l.replace(/^\s*([-*]|\d+\.)\s+/, ""), `${bi}-${li}`)}</li>`);
      return ordered ? html`<ol key=${bi}>${items}</ol>` : html`<ul key=${bi}>${items}</ul>`;
    }
    if (/^```/.test(b)) return html`<pre key=${bi}><code>${b.replace(/^```\w*\n?|```$/g, "")}</code></pre>`;
    const h = /^(#{1,3})\s+(.*)/.exec(b);
    if (h && lines.length === 1) return html`<p key=${bi} class="thq-md-h">${renderInline(h[2], bi)}</p>`;
    return html`<p key=${bi}>${lines.map((l, li) => html`<span key=${li}>${li ? html`<br/>` : null}${renderInline(l, `${bi}-${li}`)}</span>`)}</p>`;
  })}</div>`;
}
