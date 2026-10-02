// Animacja HTML Wideografa w HQ: podgląd na żywo (przewijanie przez window.__seek, bez renderu MP4), suwaki
// i kolory z parametry.json (zmiana widoczna od razu), zapis parametrów, raport pomiaru (klik = przejście do chwili)
// i prośba do Wideografa. Strona działa na serwerze podglądu :9120 w piaskownicy (inne pochodzenie), więc rozmawiamy
// z nią przez postMessage: mostek /_jarvo/most.js wstrzykuje serwer tylko w tym trybie (hq/plugin/animacja.py).

const AnimCtx = React.createContext(null);
const AN_EASE = [["łagodne wyjście", "ease out", [0.16, 1, 0.3, 1]], ["wejście i wyjście", "in-out", [0.65, 0, 0.35, 1]],
  ["sprężyste", "springy", [0.34, 1.56, 0.64, 1]], ["liniowe", "linear", [0, 0, 1, 1]]];

function anValuesOf(pola) { return Object.fromEntries((pola || []).map((p) => [p.klucz, p.wartosc])); }
function anSame(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
function anShow(v) { return Array.isArray(v) ? `[${v.join(", ")}]` : typeof v === "boolean" ? (v ? "tak" : "nie") : String(v); }

// Edytor krzywej cubic-bezier: dwa uchwyty do przeciągania (x 0–1, y −0,5–1,5 w polu), gotowe krzywe obok.
function AnCurve({ value, onChange }) {
  const ref = useRef(null);
  const S = 150, pad = 10, y0 = -0.5, y1 = 1.5;
  const X = (x) => pad + x * (S - 2 * pad), Y = (y) => pad + (1 - (y - y0) / (y1 - y0)) * (S - 2 * pad);
  const v = value || [0.16, 1, 0.3, 1];
  const drag = (k) => (e) => {
    e.preventDefault();
    const box = ref.current.getBoundingClientRect();
    const move = (ev) => {
      const x = Math.min(1, Math.max(0, ((ev.clientX - box.left) / box.width * S - pad) / (S - 2 * pad)));
      const y = Math.min(y1, Math.max(y0, y1 - ((ev.clientY - box.top) / box.height * S - pad) / (S - 2 * pad) * (y1 - y0)));
      const n = v.slice(); n[k] = Math.round(x * 100) / 100; n[k + 1] = Math.round(y * 100) / 100; onChange(n, true);
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); onChange(null, false); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  return html`<div class="thq-an-curve">
    <svg ref=${ref} viewBox=${`0 0 ${S} ${S}`} width=${S} height=${S} role="img" aria-label=${`cubic-bezier(${v.join(", ")})`}>
      <rect x=${pad} y=${Y(1)} width=${S - 2 * pad} height=${Y(0) - Y(1)} class="thq-an-curve-box"/>
      <line x1=${X(0)} y1=${Y(0)} x2=${X(v[0])} y2=${Y(v[1])} class="thq-an-curve-arm"/>
      <line x1=${X(1)} y1=${Y(1)} x2=${X(v[2])} y2=${Y(v[3])} class="thq-an-curve-arm"/>
      <path d=${`M${X(0)},${Y(0)} C${X(v[0])},${Y(v[1])} ${X(v[2])},${Y(v[3])} ${X(1)},${Y(1)}`} class="thq-an-curve-line"/>
      <circle cx=${X(v[0])} cy=${Y(v[1])} r="7" class="thq-an-curve-h" onPointerDown=${drag(0)}/>
      <circle cx=${X(v[2])} cy=${Y(v[3])} r="7" class="thq-an-curve-h" onPointerDown=${drag(2)}/>
    </svg>
    <div class="thq-an-curve-pre">${AN_EASE.map(([pl, en, c]) => html`<button type="button" key=${pl} class=${cx("thq-ed-btn", anSame(c, v) && "is-on")}
      onClick=${() => { onChange(c, true); onChange(null, false); }}>${L(pl, en)}</button>`)}</div>
  </div>`;
}

function AnField({ p, value, saved, onChange }) {
  const changed = !anSame(value, saved);
  const set = (v) => onChange(p.klucz, v);
  let control;
  if (p.typ === "liczba") {
    control = html`<span class="thq-an-row"><input type="range" min=${p.min} max=${p.max} step=${p.krok} value=${value}
      onInput=${(e) => set(+e.target.value)} aria-label=${p.etykieta}/><output>${+(+value).toFixed(3)}</output></span>`;
  } else if (p.typ === "kolor") {
    control = html`<span class="thq-an-row"><input type="color" value=${value} onInput=${(e) => set(e.target.value.toUpperCase())} aria-label=${p.etykieta}/>
      <code>${value}</code></span>`;
  } else if (p.typ === "tekst") {
    control = html`<textarea rows="2" value=${value} maxlength="400" onInput=${(e) => set(e.target.value)} aria-label=${p.etykieta}></textarea>`;
  } else if (p.typ === "przelacznik") {
    control = html`<label class="thq-an-row"><input type="checkbox" checked=${!!value} onChange=${(e) => set(e.target.checked)}/> ${value ? L("tak", "on") : L("nie", "off")}</label>`;
  } else if (p.typ === "wybor") {
    control = html`<select value=${value} onChange=${(e) => set(e.target.value)} aria-label=${p.etykieta}>${p.opcje.map((o) => html`<option key=${o} value=${o}>${o}</option>`)}</select>`;
  } else {
    control = html`<${AnCurve} value=${value} onChange=${(v, live) => v && set(v)}/>`;
  }
  return html`<div class=${cx("thq-an-field", changed && "is-changed")}>
    <div class="thq-an-label"><span>${p.etykieta}</span>${changed && html`<button type="button" class="thq-an-undo" onClick=${() => set(saved)}
      title=${L(`Przywróć: ${anShow(saved)}`, `Restore: ${anShow(saved)}`)}>↺</button>`}</div>
    ${p.opis && html`<p class="thq-ed-note">${p.opis}</p>`}${control}</div>`;
}

function AnimStudio({ path, onClose }) {
  const me = useRef({});
  const frameRef = useRef(null), boxRef = useRef(null);
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState(null);
  const [ready, setReady] = useState(null);       // {W, H, DUR, parametry} z mostka strony
  const [pageErr, setPageErr] = useState(null);
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(10);
  const [playing, setPlaying] = useState(false);
  const [vals, setVals] = useState({});
  const [base, setBase] = useState({});
  const [note, setNote] = useState("");
  const [busySave, setBusySave] = useState(false);
  const [ask, setAsk] = useState({ text: "", reply: "", busy: false, error: null });
  const [box, setBox] = useState({ w: 0, h: 0 });
  const tRef = useRef(0), valsRef = useRef({}), seek = useRef({ busy: false, next: null, id: 0 }), play = useRef({ raf: 0, t0: 0, s0: 0 });
  valsRef.current = vals;

  useEffect(() => { MODAL_STACK.push(me.current); return () => { const i = MODAL_STACK.indexOf(me.current); if (i >= 0) MODAL_STACK.splice(i, 1); }; }, []);
  useOverDashboard();
  useEffect(() => {
    let alive = true;
    api.animInfo(path).then((d) => {
      if (!alive) return;
      setInfo(d);
      const v = anValuesOf(d.parametry && d.parametry.pola);
      setVals(v); setBase(v);
      const dl = d.pomiar && d.pomiar.pokrycie && d.pomiar.pokrycie.do;
      if (dl) setDur(dl);
    }).catch((e) => alive && setErr(e.message || String(e)));
    return () => { alive = false; cancelAnimationFrame(play.current.raf); };
  }, [path]);
  useEffect(() => {
    const el = boxRef.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(() => setBox({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [info]);

  // ---- rozmowa ze stroną: jedna klatka naraz; gdy strona rysuje, czekamy i wysyłamy tylko najnowszy czas
  const post = (m) => { const w = frameRef.current && frameRef.current.contentWindow; if (w) w.postMessage({ jarvo: "hq", ...m }, "*"); };
  function seekTo(x, withParams) {
    tRef.current = x; setT(x);
    const S = seek.current;
    if (S.busy) { S.next = { t: x, p: withParams || (S.next && S.next.p) }; return; }
    S.busy = true; S.id += 1;
    post(withParams ? { typ: "params", t: x, id: S.id, wartosci: valsRef.current } : { typ: "seek", t: x, id: S.id });
  }
  useEffect(() => {
    const onMsg = (e) => {
      if (!frameRef.current || e.source !== frameRef.current.contentWindow) return;
      const d = e.data || {};
      if (d.jarvo !== "anim") return;
      const S = seek.current;
      if (d.typ === "gotowe") {
        setReady({ W: +d.W || 1920, H: +d.H || 1080, DUR: +d.DUR || null, parametry: !!d.parametry });
        if (+d.DUR > 0) setDur((x) => (info && info.pomiar && info.pomiar.pokrycie ? x : +d.DUR));
        S.busy = false; S.next = null;
        seekTo(tRef.current, true);
      } else if (d.typ === "klatka" || d.typ === "blad") {
        if (d.typ === "blad") setPageErr(String(d.tekst || "").slice(0, 300));
        S.busy = false;
        if (S.next) { const n = S.next; S.next = null; seekTo(n.t, n.p); }
      }
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [info]);

  const stop = () => { cancelAnimationFrame(play.current.raf); setPlaying(false); };
  const start = () => {
    if (!ready) return;
    const P = play.current;
    P.t0 = performance.now(); P.s0 = tRef.current >= dur - 0.02 ? 0 : tRef.current;
    setPlaying(true);
    const step = (now) => {
      let x = P.s0 + (now - P.t0) / 1000;
      if (x >= dur) { x = 0; P.s0 = 0; P.t0 = now; }          // pętla jak podgląd strony
      seekTo(x);
      P.raf = requestAnimationFrame(step);
    };
    P.raf = requestAnimationFrame(step);
  };
  const toggle = () => (playing ? stop() : start());
  const change = (k, v) => { const n = { ...valsRef.current, [k]: v }; valsRef.current = n; setVals(n); seekTo(tRef.current, true); };

  useEffect(() => {
    const onKey = (e) => {
      if (MODAL_STACK[MODAL_STACK.length - 1] !== me.current) return;
      const tag = (e.target && e.target.tagName) || "";
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault(); stop();
        seekTo(Math.min(dur, Math.max(0, tRef.current + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 1 : 1 / 30))));
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const pola = (info && info.parametry && info.parametry.pola) || [];
  const zmiany = pola.filter((p) => !anSame(vals[p.klucz], base[p.klucz]));
  async function save() {
    if (!zmiany.length || busySave) return;
    setBusySave(true); setNote("");
    try {
      const r = await api.animParams(path, Object.fromEntries(zmiany.map((p) => [p.klucz, vals[p.klucz]])));
      const v = anValuesOf(r.pola);
      setBase(v); setInfo((d) => ({ ...d, parametry: { pola: r.pola }, pomiar: r.pomiar }));
      setNote(L("Zapisano parametry.json. Pomiar jest teraz nieaktualny: poproś Wideografa o pomiar i render.",
        "Saved parametry.json. The measurement is now stale: ask the video agent to measure and render."));
    } catch (e) { setNote(`✗ ${e.message || e}`); }
    setBusySave(false);
  }
  async function sendAsk() {
    const text = ask.text.trim();
    if (!text || ask.busy) return;
    const dir = path.replace(/\/[^/]+$/, "");
    const msg = [`Animacja HTML w HQ: \`${path}\`${pola.length ? ` (parametry: \`${dir}/parametry.json\`)` : ""} · kursor ${edClock(tRef.current)}.`,
      zmiany.length ? `Niezapisane zmiany parametrów w HQ: ${zmiany.map((p) => `${p.klucz}: ${anShow(base[p.klucz])} → ${anShow(vals[p.klucz])}`).join("; ")}.` : "",
      `Prośba: ${text}`,
      `Pracuj na tej stronie i jej parametrach (kontrakt-html.md); potem \`python3 $HERMES_HOME/scripts/html_wideo.py pomiar ${path} --preset jarvo --dlugosc ${+dur.toFixed(2)}\` (pełny, bez błędów albo z wyjątkami z powodem) i render \`html_wideo.py wideo …\` z linią MEDIA:.`]
      .filter(Boolean).join("\n");
    setAsk((a) => ({ ...a, busy: true, reply: "", error: null }));
    try {
      for await (const { event, data } of api.send(ED_AGENT, msg)) {
        if (event === "assistant.delta") setAsk((a) => ({ ...a, reply: (a.reply || "") + (data.delta || "") }));
        else if (event === "assistant.completed" && typeof data.content === "string") setAsk((a) => ({ ...a, reply: data.content }));
        else if (event === "run.failed" || event === "error") setAsk((a) => ({ ...a, error: data.message || data.error || "błąd" }));
      }
      setAsk((a) => ({ ...a, text: "" }));
    } catch (e) { setAsk((a) => ({ ...a, error: e.message || String(e) })); }
    setAsk((a) => ({ ...a, busy: false }));
  }

  if (err) return html`<div class="thq-ed thq-an" role="dialog" aria-modal="true"><div class="thq-ed-msg"><p class="thq-ed-bad">${err}</p>
    <button type="button" class="thq-ed-btn" onClick=${onClose}>${L("Zamknij", "Close")}</button></div></div>`;
  if (!info) return html`<div class="thq-ed thq-an" role="dialog" aria-modal="true"><div class="thq-ed-msg"><span class="thq-ed-spin"></span></div></div>`;

  const W = (ready && ready.W) || 1920, H = (ready && ready.H) || 1080;
  const k = box.w && box.h ? Math.min(box.w / W, box.h / H) : 0.3;
  const src = `${location.protocol}//${location.hostname}:${info.podglad.port}${info.podglad.path}`;
  const pm = info.pomiar;
  const name = path.split("/").pop();
  const dirName = path.split("/").slice(-2, -1)[0] || "";
  return html`<div class="thq-ed thq-an" role="dialog" aria-modal="true" aria-label=${L("Animacja", "Animation")}>
    <header class="thq-ed-top">
      <button type="button" class="thq-ed-btn is-ghost" onClick=${() => { stop(); onClose(); }}>← ${L("Wróć", "Back")}</button>
      <strong class="thq-ed-title" title=${path}>${dirName ? `${dirName}/` : ""}${name}</strong>
      <span class="thq-ed-saved">${zmiany.length ? L(`${zmiany.length} niezapisane`, `${zmiany.length} unsaved`) : pola.length ? L("parametry zapisane", "parameters saved") : ""}</span>
      <span class="thq-ed-grow"></span>
      ${pola.length > 0 && html`<button type="button" class="thq-ed-btn" disabled=${!zmiany.length} onClick=${() => { setVals(base); valsRef.current = base; seekTo(tRef.current, true); }}>↺ ${L("Cofnij zmiany", "Revert")}</button>
        <button type="button" class="thq-ed-btn is-main" disabled=${!zmiany.length || busySave} onClick=${save}>${busySave ? "…" : L("Zapisz parametry", "Save parameters")}</button>`}
    </header>
    ${note && html`<div class=${cx("thq-ed-banner", !note.startsWith("✗") && "is-ok")} role="status"><span>${note}</span></div>`}
    <div class="thq-an-body">
      <section class="thq-an-main">
        <div class="thq-an-stage" ref=${boxRef}>
          <div class="thq-an-frame" style=${{ width: `${W * k}px`, height: `${H * k}px` }}>
            <iframe ref=${frameRef} src=${src} title=${L("Podgląd animacji", "Animation preview")} sandbox="allow-scripts"
              style=${{ width: `${W}px`, height: `${H}px`, transform: `scale(${k})` }}></iframe>
          </div>
          ${!ready && html`<p class="thq-an-wait"><span class="thq-ed-spin is-small"></span> ${L("Wczytuję animację…", "Loading the animation…")}</p>`}
        </div>
        ${pageErr && html`<p class="thq-ed-bad">${L("Błąd na stronie:", "Page error:")} ${pageErr}</p>`}
        <div class="thq-an-transport">
          <button type="button" class="thq-ed-play" onClick=${toggle} disabled=${!ready} aria-label=${playing ? L("Pauza", "Pause") : L("Odtwórz", "Play")}>${playing ? "❚❚" : "▶"}</button>
          <span class="thq-ed-time">${edClock(t)} / ${edClock(dur)}</span>
          <input type="range" class="thq-an-scrub" min="0" max=${dur} step="0.01" value=${t} disabled=${!ready}
            onInput=${(e) => { stop(); seekTo(+e.target.value); }} aria-label=${L("Czas", "Time")}/>
          <label class="thq-an-dur">${L("długość", "length")} <input type="number" min="0.5" max="600" step="0.5" value=${dur}
            onChange=${(e) => setDur(Math.max(0.5, Math.min(600, +e.target.value || 10)))}/> s</label>
        </div>
      </section>
      <aside class="thq-an-side">
        <h4>${L("Parametry", "Parameters")}</h4>
        ${info.parametry && info.parametry.blad && html`<p class="thq-ed-bad">${info.parametry.blad}</p>`}
        ${!pola.length ? html`<p class="thq-ed-note">${L("Ta animacja nie ma parametry.json. Poproś Wideografa: „wystaw kolory, teksty i tempo jako parametry” (kontrakt HTML, reguła 7).",
          "This animation has no parametry.json. Ask the video agent to expose colors, texts and timing as parameters.")}</p>`
          : pola.map((p) => html`<${AnField} key=${p.klucz} p=${p} value=${vals[p.klucz]} saved=${base[p.klucz]} onChange=${change}/>`)}
        ${pola.length > 0 && ready && !ready.parametry && html`<p class="thq-ed-bad">${L("Strona nie wystawia window.__params: zmiany nie będą widoczne na żywo.", "The page has no window.__params: changes won't show live.")}</p>`}
        <h4>${L("Pomiar", "Measurement")}</h4>
        ${!pm ? html`<p class="thq-ed-note">${L("Brak pomiaru (html_wideo.py pomiar).", "No measurement yet (html_wideo.py pomiar).")}</p>`
          : html`<p class=${cx("thq-an-pm", pm.aktualny ? "is-ok" : "is-stale")}>${pm.aktualny ? "✓ " + L("aktualny, bez błędów", "current, no errors")
              : "✗ " + (pm.powody || []).join("; ")}</p>
            <ol class="thq-an-findings">${(pm.ustalenia || []).map((u, i) => html`<li key=${i} class=${cx(u.wyjatek ? "is-exc" : u.waga === "blad" ? "is-bad" : "is-warn")}>
              <button type="button" onClick=${() => { stop(); seekTo(Math.min(dur, (u.od || 0) + 0.05)); }} title=${u.poprawka || ""}>
                <b>${edClock(u.od || 0)}</b> ${u.opis}${u.wyjatek ? html`<small> · ${L("wyjątek", "exception")}: ${u.wyjatek}</small>` : ""}</button></li>`)}</ol>`}
        <h4>${L("Poproś Wideografa", "Ask the video agent")}</h4>
        <textarea rows="2" value=${ask.text} placeholder=${L("Np. „wolniejsze wejście tytułu”, „zrób wersję 16:9”, „zmierz i wyrenderuj”.", "E.g. “slower title entry”, “make a 16:9 version”, “measure and render”.")}
          onInput=${(e) => { const v = e.target.value; setAsk((a) => ({ ...a, text: v })); }}
          onKeyDown=${(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendAsk(); } }}></textarea>
        <button type="button" class="thq-ed-btn is-main" disabled=${ask.busy || !ask.text.trim()} onClick=${sendAsk}>${ask.busy ? "…" : L("Wyślij", "Send")}</button>
        ${(ask.reply || ask.busy) && html`<div class="thq-ed-reply"><${Markdown} text=${ask.reply || L("Wideograf pracuje…", "Working…")}/></div>`}
        ${ask.error && html`<p class="thq-ed-bad">${ask.error}</p>`}
      </aside>
    </div>
  </div>`;
}
