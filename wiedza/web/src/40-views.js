// Widoki zakładki: pasek statystyk, drzewo folderów, szukanie, notatka, skrzynka, orzeczenia, lint, dziennik.

function Chip({ label, n, tone, title }) {
  return html`<li class=${cx("twz-stat", n > 0 && tone && `is-${tone}`)} title=${title || `${label}: ${n}`}><strong>${n}</strong><span>${label}</span></li>`;
}

function Stats({ ov }) {
  if (!ov) return null;
  const k = ov.kompilacja || {}, lint = ov.lint || {};
  return html`<ul class="twz-stats" aria-label=${L("Stan skarbca", "Vault status")}>
    <${Chip} label=${L("notatek", "notes")} n=${ov.notatek || 0}/>
    <${Chip} label=${L("linków", "links")} n=${ov.linki || 0}/>
    <${Chip} label=${L("szkiców", "drafts")} n=${ov.szkice || 0} tone="info"/>
    <${Chip} label=${L("błędów lintu", "lint errors")} n=${lint.bledy || 0} tone="bad"/>
    <${Chip} label=${L("ostrzeżeń", "warnings")} n=${lint.ostrzezenia || 0} tone="warn"/>
    <li class="twz-stat" title=${L("ostatnia kompilacja", "last compile")}><strong>${k.trwa ? "…" : (k.ostatnia ? agoTs(k.ostatnia) : "–")}</strong><span>${L("kompilacja", "compile")}</span></li>
  </ul>`;
}

function NoteRow({ n, onOpen, selected }) {
  return html`<li class=${cx("twz-note-row", selected === n.sciezka && "is-selected", n.hub && "is-hub")}>
    <button type="button" onClick=${() => onOpen(n.sciezka)} title=${n.streszczenie || n.sciezka}>
      <i class="twz-dot" style=${{ background: n.hub ? "#fff" : folderColor(n.sciezka.split("/")[0] === n.sciezka ? "" : n.sciezka.split("/")[0]) }}></i>
      <span class="twz-note-title">${n.tytul}</span>
      ${n.status === "sprzeczna" && html`<span class="twz-tag is-warn">${STATUS_NAMES.sprzeczna}</span>`}
      ${n.status === "do-sprawdzenia" && html`<span class="twz-tag">${STATUS_NAMES["do-sprawdzenia"]}</span>`}
    </button>
  </li>`;
}

function Tree({ tree, onOpen, selected }) {
  const [open, setOpen] = useState({});
  if (!tree) return html`<p class="twz-muted">${L("Wczytuję…", "Loading…")}</p>`;
  return html`<div class="twz-tree">${tree.foldery.map((f) => {
    const isOpen = open[f.folder] !== false;
    return html`<section key=${f.folder || "root"} class="twz-folder">
      <header>
        <button type="button" class="twz-folder-toggle" onClick=${() => setOpen({ ...open, [f.folder]: !isOpen })} aria-expanded=${isOpen}>
          <i class="twz-dot" style=${{ background: folderColor(f.folder) }}></i>${f.nazwa}<span class="twz-count">${f.notatki.length}</span></button>
        ${f.hub && html`<button type="button" class="twz-hub-btn" onClick=${() => onOpen(f.hub.sciezka)} title=${f.hub.sciezka}>hub</button>`}
      </header>
      ${isOpen && html`<ul>${f.notatki.map((n) => html`<${NoteRow} key=${n.sciezka} n=${n} onOpen=${onOpen} selected=${selected}/>`)}
        ${!f.notatki.length && html`<li class="twz-muted twz-empty">${L("jeszcze pusto", "empty so far")}</li>`}</ul>`}
    </section>`;
  })}</div>`;
}

function Search({ onOpen }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (q.trim().length < 2) { setRes(null); return undefined; }
    let alive = true;
    setBusy(true);
    const t = setTimeout(() => api.search(q.trim()).then((r) => alive && setRes(r.wyniki || [])).catch(() => alive && setRes([])).finally(() => alive && setBusy(false)), 250);
    return () => { alive = false; clearTimeout(t); };
  }, [q]);
  return html`<div class="twz-search">
    <input type="search" value=${q} onInput=${(e) => setQ(e.target.value)} placeholder=${L("Szukaj w skarbcu (jak agent)…", "Search the vault (as an agent would)…")} aria-label=${L("Szukaj", "Search")}/>
    ${res && html`<ul class="twz-results" aria-live="polite">
      ${busy && html`<li class="twz-muted">…</li>`}
      ${res.map((r) => html`<li key=${r.sciezka}><button type="button" onClick=${() => onOpen(r.sciezka)}>
        <span class="twz-note-title">${r.tytul}</span><span class="twz-tag">${TYPE_NAMES[r.typ] || r.typ}</span>
        ${r.streszczenie && html`<small>${r.streszczenie}</small>`}<code>${r.sciezka}</code></button></li>`)}
      ${!res.length && !busy && html`<li class="twz-muted">${L("nic nie znaleziono", "nothing found")}</li>`}
    </ul>`}
  </div>`;
}

function Meta({ fm, note }) {
  const rows = [
    [L("typ", "type"), TYPE_NAMES[fm.typ] || fm.typ], [L("status", "status"), STATUS_NAMES[fm.status] || fm.status],
    [L("utworzono", "created"), fm.utworzono], [L("zmieniono", "changed"), fm.zmieniono ? `${fm.zmieniono} (${agoIso(fm.zmieniono)})` : ""],
    [L("agent", "agent"), fm.agent], [L("ważne do", "valid until"), fm.wazne_do], [L("tagi", "tags"), Array.isArray(fm.tagi) ? fm.tagi.join(", ") : fm.tagi],
    [L("słów", "words"), note.slowa],
  ].filter(([, v]) => v);
  return html`<dl class="twz-meta">${rows.map(([k, v]) => html`<div key=${k}><dt>${k}</dt><dd>${String(v)}</dd></div>`)}</dl>`;
}

function NoteView({ path, onOpen, onClose, onChanged }) {
  const [note, setNote] = useState(null);
  const [err, setErr] = useState(null);
  const [remark, setRemark] = useState("");
  const [msg, setMsg] = useState(null);
  useEffect(() => { setNote(null); setErr(null); setMsg(null); api.note(path).then(setNote).catch((e) => setErr(e.message || String(e))); }, [path]);
  const send = async () => {
    try { const r = await api.remark(path, remark); setMsg({ ok: true, text: L(`Uwaga zgłoszona jako szkic: ${r.szkic}`, `Remark filed as a draft: ${r.szkic}`) }); setRemark(""); onChanged && onChanged(); }
    catch (e) { setMsg({ ok: false, text: e.message || String(e) }); }
  };
  if (err) return html`<aside class="twz-panel"><header><h2>${path}</h2><button type="button" class="twz-icon-btn" onClick=${onClose} aria-label=${L("Zamknij", "Close")}>×</button></header><p class="twz-error">${err}</p></aside>`;
  if (!note) return html`<aside class="twz-panel"><header><h2>${path}</h2><button type="button" class="twz-icon-btn" onClick=${onClose} aria-label=${L("Zamknij", "Close")}>×</button></header><p class="twz-muted">${L("Wczytuję…", "Loading…")}</p></aside>`;
  const fm = note.frontmatter || {};
  return html`<aside class="twz-panel" aria-label=${note.tytul}>
    <header>
      <div><span class="twz-crumb"><i class="twz-dot" style=${{ background: folderColor(note.folder) }}></i>${folderName(note.folder)}</span><h2>${note.tytul}</h2><code>${note.sciezka}</code></div>
      <button type="button" class="twz-icon-btn" onClick=${onClose} aria-label=${L("Zamknij", "Close")}>×</button>
    </header>
    <${Meta} fm=${fm} note=${note}/>
    <${Markdown} text=${note.tresc} onOpen=${onOpen}/>
    ${note.zrodla && note.zrodla.length > 0 && html`<section class="twz-links"><h3>${L("Źródła", "Sources")}</h3><ul>${note.zrodla.map((z, i) => html`<li key=${i}>
      ${z.sciezka ? html`<button type="button" class="twz-wikilink" onClick=${() => onOpen(z.sciezka)}>${z.tekst}</button>` : z.tekst}</li>`)}</ul></section>`}
    <section class="twz-links"><h3>${L("Linkuje do", "Links to")} (${note.linki_wy.length})</h3>
      <ul>${note.linki_wy.map((l, i) => html`<li key=${i} class=${cx(!l.istnieje && "is-dead", l.auto && "is-auto")}>
        ${l.istnieje ? html`<button type="button" class="twz-wikilink" onClick=${() => onOpen(l.cel)}>${l.tytul || l.etykieta}</button>` : html`<span title=${L("martwy link", "dead link")}>${l.etykieta} ✗</span>`}
        ${l.auto && html`<small>${L("lista automatyczna", "automatic list")}</small>`}</li>`)}
        ${!note.linki_wy.length && html`<li class="twz-muted">${L("brak", "none")}</li>`}</ul></section>
    <section class="twz-links"><h3>${L("Linkują tutaj", "Linked from")} (${note.linki_we.length})</h3>
      <ul>${note.linki_we.map((l, i) => html`<li key=${i} class=${cx(l.auto && "is-auto")}><button type="button" class="twz-wikilink" onClick=${() => onOpen(l.z)}>${l.tytul || l.z}</button>${l.auto && html`<small>${L("lista automatyczna", "automatic list")}</small>`}</li>`)}
        ${!note.linki_we.length && html`<li class="twz-muted">${L("nikt (sierota)", "nobody (orphan)")}</li>`}</ul></section>
    ${note.historia && note.historia.length > 0 && html`<section class="twz-links"><h3>${L("Historia", "History")}</h3><ul class="twz-history">${note.historia.map((h) => html`<li key=${h.rev}><code>${h.rev}</code> ${h.data} · ${h.opis}</li>`)}</ul></section>`}
    ${!note.hub && html`<section class="twz-remark"><h3>${L("Zgłoś uwagę", "Report an issue")}</h3>
      <p class="twz-muted">${L("Uwaga trafia do skrzynki jako szkic; kompilacja poprawi notatkę.", "The remark goes to the inbox as a draft; the compile pass fixes the note.")}</p>
      <textarea value=${remark} onInput=${(e) => setRemark(e.target.value)} rows="3" placeholder=${L("Co jest nie tak albo czego brakuje?", "What is wrong or missing?")}></textarea>
      <button type="button" class="twz-btn" disabled=${remark.trim().length < 5} onClick=${send}>${L("Wyślij do skrzynki", "Send to inbox")}</button>
      ${msg && html`<p class=${msg.ok ? "twz-ok" : "twz-error"} role="status">${msg.text}</p>`}</section>`}
  </aside>`;
}

function Inbox({ onChanged }) {
  const [data, err, reload] = usePoll(() => api.inbox(), 5000, []);
  const [msg, setMsg] = useState(null);
  const compile = async () => { try { const r = await api.compile(); setMsg(r.blad ? { ok: false, text: r.blad } : { ok: true, text: L("Kompilacja uruchomiona.", "Compile started.") }); reload(); } catch (e) { setMsg({ ok: false, text: e.message || String(e) }); } };
  const reindex = async () => { try { const r = await api.reindex(); setMsg({ ok: true, text: L(`Indeks odświeżony: ${r.pliki} plików, INDEX ${r.index} notatek.`, `Index refreshed: ${r.pliki} files, INDEX ${r.index} notes.`) }); onChanged && onChanged(); } catch (e) { setMsg({ ok: false, text: e.message || String(e) }); } };
  if (err) return html`<p class="twz-error">${err}</p>`;
  if (!data) return html`<p class="twz-muted">${L("Wczytuję…", "Loading…")}</p>`;
  const k = data.kompilacja || {}, r = k.raport || {};
  return html`<div class="twz-inbox">
    <div class="twz-toolbar">
      <button type="button" class="twz-btn" onClick=${compile} disabled=${k.trwa}>${k.trwa ? L("Kompilacja trwa…", "Compiling…") : L("Skompiluj teraz", "Compile now")}</button>
      <button type="button" class="twz-btn is-ghost" onClick=${reindex}>${L("Odśwież indeks", "Refresh index")}</button>
      <span class="twz-muted">${L("ostatnia kompilacja", "last compile")}: ${k.ostatnia ? `${agoTs(k.ostatnia)} · ${r.nowe || 0} ${L("nowych", "new")}, ${r.aktualizacje || 0} ${L("aktualizacji", "updates")}, ${r.sprzeczne || 0} ${L("sprzecznych", "contradictions")}, ${r.odrzucone || 0} ${L("odrzuconych", "rejected")}` : L("jeszcze nie było", "none yet")}${k.blad && html` · <span class="twz-error">${k.blad}</span>`}</span>
    </div>
    ${msg && html`<p class=${msg.ok ? "twz-ok" : "twz-error"} role="status">${msg.text}</p>`}
    <p class="twz-muted">${L(`Szkice czekające: ${data.szkice.length} · po kompilacji: ${data.zrobione}`, `Drafts waiting: ${data.szkice.length} · compiled: ${data.zrobione}`)}</p>
    <ul class="twz-drafts">${data.szkice.map((s) => html`<li key=${s.plik}>
      <div class="twz-draft-head"><span class="twz-tag">${TYPE_NAMES[s.typ] || s.typ}</span><strong>${s.tytul}</strong><span class="twz-muted">${s.agent} · ${agoTs(s.mtime)}${s.proby ? ` · ${L("prób", "attempts")}: ${s.proby}` : ""}</span></div>
      <small class="twz-muted">${L("źródło", "source")}: ${s.zrodlo}${s.skad ? ` · ${s.skad}` : ""}</small>
      <p>${s.podglad}</p></li>`)}
      ${!data.szkice.length && html`<li class="twz-muted twz-empty">${L("Skrzynka pusta: wszystko skompilowane.", "Inbox empty: everything compiled.")}</li>`}</ul>
  </div>`;
}

function Rulings({ onOpen, onChanged }) {
  const [data, err, reload] = usePoll(() => api.rulings(), 0, []);
  const [kogo, setKogo] = useState("wszyscy");
  const [tresc, setTresc] = useState("");
  const [msg, setMsg] = useState(null);
  const send = async () => {
    try { const r = await api.addRuling(kogo, tresc); setMsg({ ok: true, text: r.orzeczenie }); setTresc(""); reload(); onChanged && onChanged(); }
    catch (e) { setMsg({ ok: false, text: e.message || String(e) }); }
  };
  if (err) return html`<p class="twz-error">${err}</p>`;
  const pliki = (data && data.pliki) || [];
  const opcje = ["wszyscy", ...pliki.map((p) => p.kogo).filter((k) => k !== "wszyscy")];
  return html`<div class="twz-rulings">
    <form class="twz-ruling-form" onSubmit=${(e) => { e.preventDefault(); send(); }}>
      <label>${L("Kogo dotyczy", "Applies to")}<select value=${kogo} onChange=${(e) => setKogo(e.target.value)}>${opcje.map((o) => html`<option key=${o} value=${o}>${o}</option>`)}<option value="__inne">${L("inny (wpisz niżej)", "other (type below)")}</option></select></label>
      ${kogo === "__inne" && html`<input type="text" placeholder=${L("np. web albo marki/acme", "e.g. web or marki/acme")} onInput=${(e) => setKogo(e.target.value || "__inne")}/>`}
      <label>${L("Orzeczenie (jedno zdanie w trybie rozkazującym)", "Ruling (one imperative sentence)")}<textarea rows="2" value=${tresc} onInput=${(e) => setTresc(e.target.value)} maxlength="400"></textarea></label>
      <button type="submit" class="twz-btn" disabled=${tresc.trim().length < 5 || kogo === "__inne"}>${L("Dodaj orzeczenie", "Add ruling")}</button>
      ${msg && html`<p class=${msg.ok ? "twz-ok" : "twz-error"} role="status">${msg.text}</p>`}
    </form>
    ${pliki.map((p) => html`<section key=${p.sciezka} class="twz-ruling-file">
      <header><h3>${p.tytul}</h3><button type="button" class="twz-hub-btn" onClick=${() => onOpen(p.sciezka)}>${L("plik", "file")}</button></header>
      <ul>${p.linie.map((l, i) => html`<li key=${i}>${l}</li>`)}${!p.linie.length && html`<li class="twz-muted">${L("brak orzeczeń", "no rulings")}</li>`}</ul>
    </section>`)}
  </div>`;
}

function LintView({ onOpen }) {
  const [data, err, reload] = usePoll(() => api.lint(), 0, []);
  const [busy, setBusy] = useState(false);
  const refresh = () => { setBusy(true); api.lint(true).finally(() => { setBusy(false); reload(); }); };
  if (err) return html`<p class="twz-error">${err}</p>`;
  if (!data) return html`<p class="twz-muted">${L("Sprawdzam skarbiec…", "Checking the vault…")}</p>`;
  const linkify = (s) => inline(s, onOpen, "lint");
  const grupy = [[L("Błędy", "Errors"), data.bledy, "bad"], [L("Ostrzeżenia", "Warnings"), data.ostrzezenia, "warn"], [L("Informacje", "Info"), data.informacje, ""]];
  return html`<div class="twz-lint">
    <div class="twz-toolbar"><button type="button" class="twz-btn is-ghost" onClick=${refresh} disabled=${busy}>${busy ? "…" : L("Sprawdź ponownie", "Check again")}</button><span class="twz-muted">${data.data} · ${data.notatek} ${L("notatek", "notes")}</span></div>
    ${grupy.map(([t, lista, tone]) => html`<section key=${t}><h3 class=${tone && `is-${tone}`}>${t} (${(lista || []).length})</h3>
      <ul>${(lista || []).map((x, i) => html`<li key=${i}>${linkify(x)}</li>`)}${!(lista || []).length && html`<li class="twz-muted">${L("brak", "none")}</li>`}</ul></section>`)}
  </div>`;
}

function LogView({ onOpen }) {
  const [data, err] = usePoll(() => api.log(), 15000, []);
  const [recall, recallErr] = usePoll(() => api.recall(), 15000, []);
  const [which, setWhich] = useState("log");
  if (err) return html`<p class="twz-error">${err}</p>`;
  return html`<div>
    <div class="twz-toolbar">
      <button type="button" class=${cx("twz-tab", which === "log" && "is-active")} onClick=${() => setWhich("log")}>${L("Zmiany skarbca", "Vault changes")}</button>
      <button type="button" class=${cx("twz-tab", which === "recall" && "is-active")} onClick=${() => setWhich("recall")}>${L("Co dostali agenci", "What agents received")}</button>
    </div>
    ${which === "log" && (!data ? html`<p class="twz-muted">${L("Wczytuję…", "Loading…")}</p>` : html`<ul class="twz-log">${data.wpisy.map((w, i) => html`<li key=${i}><span class="twz-tag">${w.rodzaj}</span><strong>${w.data}</strong> ${w.tresc}
      ${w.szczegoly.length > 0 && html`<ul>${w.szczegoly.slice(0, 12).map((s, j) => html`<li key=${j}>${inline(s, onOpen, `log-${i}-${j}`)}</li>`)}${w.szczegoly.length > 12 && html`<li class="twz-muted">…</li>`}</ul>`}</li>`)}
      ${!data.wpisy.length && html`<li class="twz-muted">${L("pusty dziennik", "empty log")}</li>`}</ul>`)}
    ${which === "recall" && (recallErr ? html`<p class="twz-error">${recallErr}</p>` : !recall ? html`<p class="twz-muted">${L("Wczytuję…", "Loading…")}</p>` : html`<ul class="twz-log">
      <li class="twz-muted twz-empty">${L("Każda linia = przypomnienie wstrzyknięte agentowi przed turą (plik state/wiedza-przypomnienia.jsonl).", "Each line = a recall injected into an agent's turn (file state/wiedza-przypomnienia.jsonl).")}</li>
      ${recall.wpisy.map((w, i) => html`<li key=${i}><span class="twz-tag">${w.agent}</span><strong>${w.data}</strong> ${L("pytanie", "query")}: „${w.zapytanie}” · ${w.orzeczen} ${L("orzeczeń", "rulings")} · ${w.znakow} ${L("znaków", "chars")}
        ${(w.notatki || []).length > 0 && html`<ul>${w.notatki.map((n, j) => html`<li key=${j}><button type="button" class="twz-wikilink" onClick=${() => onOpen(n)}>${n}</button></li>`)}</ul>`}</li>`)}
      ${!recall.wpisy.length && html`<li class="twz-muted">${L("jeszcze żadnych przypomnień", "no recalls yet")}</li>`}</ul>`)}
  </div>`;
}
