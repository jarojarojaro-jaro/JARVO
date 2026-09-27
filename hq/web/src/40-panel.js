// Panel agenta (po kliknięciu pokoju) i okna podglądu: karta kanbana, plik wynikowy.

const TAB_TEXT = bilingual({ now: ["Teraz", "Now"], cards: ["Karty", "Cards"], outputs: ["Wyniki", "Results"], chat: ["Czat", "Chat"], about: ["O agencie", "About"] });
const TABS = ["now", "cards", "outputs", "chat", "about"];

// Otwarte okna jedno na drugim (karta → podgląd pliku): Escape zamyka tylko to na wierzchu.
const MODAL_STACK = [];

function Modal({ title, onClose, children, wide }) {
  const me = useRef({});
  useEffect(() => {
    MODAL_STACK.push(me.current);
    return () => { const i = MODAL_STACK.indexOf(me.current); if (i >= 0) MODAL_STACK.splice(i, 1); };
  }, []);
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && MODAL_STACK[MODAL_STACK.length - 1] === me.current && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return html`<div class="thq-modal-back" onClick=${(e) => e.target === e.currentTarget && onClose()}>
    <div class=${cx("thq-modal", wide && "is-wide")} role="dialog" aria-modal="true" aria-label=${title}>
      <header class="thq-modal-head"><h3>${title}</h3>
        <button type="button" class="thq-icon-btn" onClick=${onClose} aria-label=${L("Zamknij", "Close")}>×</button></header>
      <div class="thq-modal-body">${children}</div>
    </div>
  </div>`;
}

// Akcje pliku wynikowego: podgląd, „Odpal” (HTML w nowej karcie), folder w Eksploratorze, pobranie.
function FileActions({ file, onPreview, compact }) {
  const host = useHost();
  const [note, setNote] = useState(null);
  const say = (text, bad) => { setNote({ text, bad }); setTimeout(() => setNote(null), bad ? 6000 : 3500); };
  const run = (fn, okText) => async (e) => {
    e.stopPropagation();
    try { await fn(); if (okText) say(okText); } catch (err) { say(err.message || String(err), true); }
  };
  const copy = run(() => copyText(hostPathOf(file.path, host)), L("Ścieżka skopiowana", "Path copied"));
  return html`<span class=${cx("thq-file-acts", compact && "is-compact")}>
    ${file.kind === "html" && html`<button type="button" class="thq-act-btn is-run" onClick=${run(() => openSite(file.path))}
      title=${L("Otwórz stronę w nowej karcie przeglądarki", "Open the page in a new browser tab")}>▶ ${L("Odpal", "Run")}</button>`}
    ${onPreview && html`<button type="button" class="thq-act-btn" onClick=${(e) => { e.stopPropagation(); onPreview(file); }}
      title=${L("Podgląd w oknie", "Preview in a window")}>${file.kind === "html" ? L("Kod", "Code") : L("Podgląd", "Preview")}</button>`}
    ${host.explorer
      ? html`<button type="button" class="thq-act-btn" onClick=${run(() => api.reveal(file.path), L("Otwieram Eksplorator…", "Opening Explorer…"))}
          title=${hostPathOf(file.path, host)}>${L("Pokaż w folderze", "Show in folder")}</button>`
      : html`<button type="button" class="thq-act-btn" onClick=${copy} title=${hostPathOf(file.path, host)}>${L("Kopiuj ścieżkę", "Copy path")}</button>`}
    ${file.kind === "image" && html`<button type="button" class="thq-act-btn" onClick=${run(() => copyImage(file), L("Obraz w schowku: wklej go w czacie", "Image copied: paste it into a chat"))}
      title=${L("Skopiuj obraz do schowka (np. do Telegrama)", "Copy the image to the clipboard (e.g. for Telegram)")}>${L("Kopiuj obraz", "Copy image")}</button>`}
    ${!compact && html`<button type="button" class="thq-act-btn" onClick=${run(() => downloadFile(file))} title=${L("Zapisz plik na dysku", "Save the file to disk")}>${L("Pobierz", "Download")}</button>`}
    ${note && html`<span class=${cx("thq-act-note", note.bad && "is-bad")} role="status">${note.text}</span>`}
  </span>`;
}

function OutRow({ f, onOpenFile, small }) {
  return html`<li class=${cx("thq-out", f.main && "is-main")}>
    <button type="button" class="thq-out-name" onClick=${() => onOpenFile(f)} title=${f.path}>${f.main ? "★ " : ""}${f.rel}</button>
    <span class="thq-out-meta">${bytes(f.size)} · ${ago(f.mtime)}</span>
    <${FileActions} file=${f} onPreview=${onOpenFile} compact=${small}/>
  </li>`;
}

// Plik w wiadomości (MEDIA: od agenta, 📎 od Ciebie): obraz jako miniatura, inny plik jako nazwa z akcjami.
function MediaFile({ path }) {
  const open = React.useContext(FileCtx);
  const f = fileFromPath(path);
  const [url, setUrl] = useState(null);
  const [bad, setBad] = useState(false);
  useEffect(() => {
    if (f.kind !== "image") return undefined;
    let alive = true, made = null;
    api.fileBlob(path).then((b) => { if (alive) { made = URL.createObjectURL(b); setUrl(made); } }).catch(() => alive && setBad(true));
    return () => { alive = false; if (made) URL.revokeObjectURL(made); };
  }, [path]);
  if (bad) return html`<span class="thq-media-file is-bad" title=${path}>${f.name} · ${L("poza katalogami floty albo nie istnieje", "outside fleet folders or missing")}</span>`;
  if (f.kind === "image") {
    return html`<button type="button" class="thq-media-img" onClick=${() => open && open(f)} title=${`${f.name} · ${L("kliknij: podgląd, kopiuj, pobierz", "click: preview, copy, download")}`}>
      ${url ? html`<img src=${url} alt=${f.name}/>` : html`<span class="thq-muted">${f.name}</span>`}</button>`;
  }
  return html`<span class="thq-media-file"><button type="button" class="thq-pathlink" onClick=${() => open && open(f)}>${f.name}</button>
    <${FileActions} file=${f} compact=${true}/></span>`;
}

function TaskOutputs({ t, onOpenFile }) {
  const files = t.outputs || [];
  const missing = (t.expected || []).filter((w) => !files.some((f) => f.rel === w || f.rel.endsWith(`/${w}`) || f.name === w));
  if (!files.length && !missing.length) return null;
  // na wierzchu to, co zamówiono w WYJŚCIA (albo katalog out/); pliki pomocnicze zwinięte
  const hasMain = files.some((f) => f.main);
  const top = files.filter((f) => (hasMain ? f.main : f.in_out));
  const shown = top.length ? top : files.slice(0, 3);
  const other = files.filter((f) => !shown.includes(f));
  return html`<section class="thq-task-sec"><h4>${L("Wynik", "Result")}</h4>
    <ul class="thq-outs">
      ${shown.map((f) => html`<${OutRow} key=${f.path} f=${f} onOpenFile=${onOpenFile}/>`)}
      ${missing.map((w) => html`<li key=${w} class="thq-out is-missing"><span class="thq-out-name">${w}</span>
        <span class="thq-out-meta">${t.status === "done" ? L("nie ma w katalogu karty", "not in the card folder") : L("jeszcze nie ma", "not there yet")}</span></li>`)}
    </ul>
    ${other.length > 0 && html`<details class="thq-more thq-more-files"><summary>${L("Pozostałe pliki", "Other files")} <span class="thq-count">${other.length}</span></summary>
      <ul class="thq-outs is-small">${other.map((f) => html`<${OutRow} key=${f.path} f=${f} onOpenFile=${onOpenFile} small=${true}/>`)}</ul>
    </details>`}
  </section>`;
}

const BRIEF_TEXT = bilingual({ wejscia: ["Wejścia", "Inputs"], dod: ["Kryteria gotowości (DoD)", "Definition of done"], wyjscia: ["Wyjścia", "Outputs"], granice: ["Granice", "Boundaries"] });
const BRIEF_REST = ["wejscia", "dod", "wyjscia", "granice"];

function TaskModal({ taskId, agents, onClose, onOpenFile }) {
  const [t, setT] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api.task(taskId).then(setT).catch((e) => setErr(e.message)); }, [taskId]);
  const who = (n) => { const a = agents.find((x) => x.name === n); return a ? `${a.emoji} ${a.short || a.name}` : n || "—"; };
  const b = (t && t.brief) || {};
  const structured = !!(b.cel || b.kontekst);
  const rest = BRIEF_REST.filter((k) => b[k]);
  const failed = t && t.last_failure_error && t.status !== "done";
  return html`<${Modal} title=${t ? t.title : L("Karta", "Card")} onClose=${onClose} wide=${true}>
    ${err && html`<p class="thq-error">${err}</p>`}
    ${!t && !err && html`<p class="thq-muted">${L("Wczytuję kartę…", "Loading card…")}</p>`}
    ${t && html`<div class="thq-task">
      <p class="thq-task-meta">
        <span class=${cx("thq-pill", `is-card-${t.status}`)}>${CARD_STATUS[t.status] || t.status}</span>
        <span>${who(t.assignee)}</span>
        <span class="thq-muted">${t.completed_at ? `${L("zakończona", "finished")} ${ago(t.completed_at)}` : `${L("założona", "created")} ${ago(t.created_at)}`}</span>
        <code class="thq-muted">${t.id}</code>
      </p>
      ${structured && b.cel && html`<section class="thq-goal" aria-label=${L("Cel", "Goal")}><span class="thq-goal-label">${L("Cel", "Goal")}</span>
        <${Markdown} text=${b.cel}/></section>`}
      ${structured && b.kontekst && html`<section class="thq-task-sec"><h4>${L("Kontekst", "Context")}</h4><${Markdown} text=${b.kontekst}/></section>`}
      ${failed && html`<section class="thq-task-sec is-bad"><h4>${L("Ostatni błąd", "Last error")}</h4><pre class="thq-decision-err">${t.last_failure_error}</pre></section>`}
      <${TaskOutputs} t=${t} onOpenFile=${onOpenFile}/>
      ${t.result && html`<section class="thq-task-sec"><h4>${L("Raport wykonawcy", "Worker report")}</h4><${Markdown} text=${t.result}/></section>`}
      ${structured && (rest.length > 0 || b.intro) && html`<details class="thq-more"><summary>${L("Pełne zlecenie", "Full brief")}
          <span class="thq-muted">${rest.map((k) => BRIEF_TEXT[k].split(" (")[0].toLowerCase()).join(", ")}</span></summary>
        ${b.intro && html`<${Markdown} text=${b.intro}/>`}
        ${rest.map((k) => html`<div key=${k} class="thq-brief-part"><h4>${BRIEF_TEXT[k]}</h4><${Markdown} text=${b[k]}/></div>`)}
      </details>`}
      ${!structured && t.body && html`<details class="thq-more" open=${t.body.length < 500}><summary>${L("Zlecenie", "Brief")}</summary>
        <${Markdown} text=${t.body}/></details>`}
      ${t.comments && t.comments.length > 0 && html`<details class="thq-more"><summary>${L("Komentarze", "Comments")} <span class="thq-count">${t.comments.length}</span></summary>
        ${t.comments.map((c, i) => html`<div key=${i} class="thq-comment"><strong>${who(c.author)}</strong> <span class="thq-muted">${ago(c.created_at)}</span><${Markdown} text=${c.body}/></div>`)}
      </details>`}
      <details class="thq-more"><summary>${L("Historia", "History")} <span class="thq-count">${(t.events || []).length}</span></summary><ol class="thq-timeline">
        ${(t.events || []).map((e, i) => html`<li key=${i}><span class="thq-muted">${clock(e.created_at)}</span> ${EVENT_PL[e.kind] || e.kind}
          ${e.payload && e.payload.reason ? html`<em> „${e.payload.reason}”</em>` : null}
          ${e.payload && e.payload.summary ? html`<em> ${e.payload.summary}</em>` : null}</li>`)}
      </ol></details>
    </div>`}
  </${Modal}>`;
}

const EVENT_PL = bilingual({
  created: ["założona", "created"], promoted: ["gotowa do pracy", "ready to work"], promoted_manual: ["gotowa do pracy", "ready to work"],
  claimed: ["przejęta przez pracownika", "claimed by a worker"], spawned: ["pracownik wystartował", "worker started"],
  completed: ["zakończona", "finished"], blocked: ["zablokowana", "blocked"], unblocked: ["odblokowana", "unblocked"],
  review_requested: ["oddana do oceny", "sent for review"], changes_requested: ["odesłana do poprawki", "sent back for changes"],
  commented: ["komentarz", "comment"], archived: ["zarchiwizowana", "archived"], timed_out: ["przekroczony czas", "timed out"],
  gave_up: ["porzucona po błędach", "gave up after errors"], stale: ["brak sygnału", "no signal"], reclaimed: ["przejęta ponownie", "reclaimed"],
  edited: ["edytowana", "edited"], linked: ["powiązana", "linked"], scheduled: ["zaplanowana", "scheduled"],
});

function FilePreview({ file, onClose }) {
  const url = useBlobUrl(["image", "video", "pdf"].includes(file.kind) ? file.path : null);
  const [text, setText] = useState(null);
  useEffect(() => {
    if (file.kind !== "text" && file.kind !== "html") return;
    api.fileBlob(file.path).then((b) => b.text()).then((t) => setText(t.slice(0, 60000))).catch(() => setText(L("Nie udało się wczytać pliku.", "Could not load the file.")));
  }, [file.path]);
  return html`<${Modal} title=${file.name} onClose=${onClose} wide=${true}>
    <div class="thq-preview-bar"><p class="thq-muted thq-path">${file.path}${file.size != null ? ` · ${bytes(file.size)}` : ""}</p><${FileActions} file=${file}/></div>
    ${file.kind === "image" && (url ? html`<img class="thq-preview-img" src=${url} alt=${file.name}/>` : html`<p class="thq-muted">${L("Wczytuję…", "Loading…")}</p>`)}
    ${file.kind === "video" && url && html`<video class="thq-preview-img" src=${url} controls></video>`}
    ${file.kind === "pdf" && url && html`<iframe class="thq-preview-pdf" src=${url} title=${file.name}></iframe>`}
    ${(file.kind === "text" || file.kind === "html") && html`<pre class="thq-preview-text">${text == null ? L("Wczytuję…", "Loading…") : text}</pre>`}
    ${["archive", "doc", "other"].includes(file.kind) && html`<p>${L("Tego typu pliku nie da się podejrzeć w przeglądarce. Pobierz go albo otwórz folder przyciskami wyżej.", "This file type cannot be previewed in the browser. Download it or open its folder with the buttons above.")}</p>`}
  </${Modal}>`;
}

function Thumb({ file, onOpen }) {
  const url = useBlobUrl(file.kind === "image" ? file.path : null);
  const label = { image: "Obraz", video: "Wideo", pdf: "PDF", text: "Tekst", html: "HTML", archive: "Paczka", doc: "Dokument", other: "Plik" }[file.kind];
  return html`<button type="button" class="thq-file" onClick=${() => onOpen(file)} title=${file.rel}>
    <span class=${cx("thq-file-thumb", `is-${file.kind}`)}>${url ? html`<img src=${url} alt=""/>` : html`<span>${label}</span>`}</span>
    <span class="thq-file-name">${file.name}</span>
    <span class="thq-file-meta">${bytes(file.size)} · ${ago(file.mtime)}</span>
  </button>`;
}

function CardRow({ card, onOpen, agents }) {
  const a = agents.find((x) => x.name === card.assignee);
  return html`<button type="button" class="thq-card-row" onClick=${() => onOpen(card.id)}>
    <span class=${cx("thq-dot", `is-card-${card.status}`)} aria-hidden="true"></span>
    <span class="thq-card-title">${card.title}</span>
    <span class="thq-card-meta">${a && card.assignee !== undefined ? `${a.emoji} ` : ""}${ago(card.completed_at || card.started_at || card.created_at)}</span>
  </button>`;
}

function Activity({ items, now }) {
  if (!items || !items.length) return html`<p class="thq-muted">${L("Brak zapisanych kroków w tej sesji.", "No recorded steps in this session.")}</p>`;
  return html`<ol class="thq-activity">${items.slice().reverse().map((it, i) => html`<li key=${i} class=${cx(`is-${it.kind}`, it.status && `is-${it.status}`)}>
    <span class="thq-act-time">${clock(it.ts)}</span>
    ${it.kind === "tool" && html`<span class="thq-act-body"><span class="thq-act-icon" aria-hidden="true">${ICON[it.icon] || ICON.tool}</span>
      <strong>${it.verb}</strong>${it.detail ? html` <code>${it.detail}</code>` : null}
      ${it.status === "running" && html`<span class="thq-live-dot" aria-label="w toku"></span>`}
      ${it.status === "error" && html`<span class="thq-pill is-bad">${L("błąd", "error")}</span>`}</span>`}
    ${it.kind === "say" && html`<span class="thq-act-body thq-act-say"><${Markdown} text=${it.text}/></span>`}
    ${it.kind === "brief" && html`<span class="thq-act-body thq-muted">Zlecenie: ${it.text.slice(0, 180)}${it.text.length > 180 ? "…" : ""}</span>`}
  </li>`)}</ol>`;
}

function NowTab({ data, agents, onOpenTask }) {
  const a = data.agent;
  const now = data.ts;
  const running = data.cards.running[0];
  if (running) {
    return html`<div class="thq-now">
      <button type="button" class="thq-now-card" onClick=${() => onOpenTask(running.id)}>
        <span class="thq-eyebrow">${a.status === "judging" || running.assignee !== a.name ? L("Ocenia kartę", "Reviewing card") : L("Pracuje nad", "Working on")}</span>
        <strong>${running.title}</strong>
        <span class="thq-muted">${L("od", "for")} ${duration(running.started_at, now)}${a.quiet ? L(" · brak sygnału od kilku minut", " · no signal for a few minutes") : ""}</span>
      </button>
      <h4 class="thq-h4">${L("Na żywo", "Live")}</h4>
      <${Activity} items=${data.activity} now=${now}/>
    </div>`;
  }
  const blocked = data.cards.blocked[0];
  const review = data.cards.review[0];
  return html`<div class="thq-now">
    ${blocked && html`<button type="button" class="thq-now-card is-bad" onClick=${() => onOpenTask(blocked.id)}>
      <span class="thq-eyebrow">${L("Zablokowane", "Blocked")}</span><strong>${blocked.title}</strong>
      <span class="thq-muted">${a.reason ? `${L("Pytanie", "Question")}: ${a.reason}` : L("Czeka na decyzję albo brakujący dostęp.", "Waiting for a decision or missing access.")}</span></button>`}
    ${review && html`<button type="button" class="thq-now-card is-warn" onClick=${() => onOpenTask(review.id)}>
      <span class="thq-eyebrow">${L("Czeka na ocenę TARS-a", "Waiting for TARS to review")}</span><strong>${review.title}</strong></button>`}
    ${data.cards.judging.length > 0 && html`<div><h4 class="thq-h4">Do oceny (${data.cards.judging.length})</h4>
      ${data.cards.judging.map((c) => html`<${CardRow} key=${c.id} card=${c} agents=${agents} onOpen=${onOpenTask}/>`)}</div>`}
    ${!blocked && !review && data.cards.judging.length === 0 && html`<div class="thq-idle">
      <p><strong>${data.cards.ready.length ? `${L("W kolejce", "Queued")}: ${data.cards.ready.length}` : L("Wolne biurko.", "Free desk.")}</strong></p>
      <p class="thq-muted">${data.cards.ready.length ? L("Dispatcher przydzieli następną kartę w ciągu minuty.", "The dispatcher assigns the next card within a minute.") : L("Nie ma teraz zadań. Zlecenia daje TARS albo Ty w czacie.", "No tasks right now. Work comes from TARS or from you in the chat.")}</p>
    </div>`}
    ${data.cards.done.length > 0 && html`<div><h4 class="thq-h4">Ostatnio zrobione</h4>
      ${data.cards.done.slice(0, 5).map((c) => html`<${CardRow} key=${c.id} card=${c} agents=${agents} onOpen=${onOpenTask}/>`)}</div>`}
  </div>`;
}

function CardsTab({ data, agents, onOpenTask }) {
  const groups = [["running", L("W toku", "In progress")], ["judging", L("Do oceny", "To review")], ["blocked", L("Zablokowane", "Blocked")], ["review", L("Czeka na ocenę", "Awaiting review")],
    ["ready", L("W kolejce", "Queued")], ["triage", L("Do rozpisania", "Triage")], ["done", L("Zrobione (7 dni)", "Done (7 days)")]];
  const any = groups.some(([k]) => data.cards[k] && data.cards[k].length);
  if (!any) return html`<p class="thq-muted">${L("Ten agent nie ma kart z ostatnich 7 dni.", "This agent has no cards from the last 7 days.")}</p>`;
  return html`<div class="thq-groups">${groups.map(([k, label]) => data.cards[k] && data.cards[k].length > 0 && html`<section key=${k}>
    <h4 class="thq-h4">${label} <span class="thq-count">${data.cards[k].length}</span></h4>
    ${data.cards[k].map((c) => html`<${CardRow} key=${c.id} card=${c} agents=${agents} onOpen=${onOpenTask}/>`)}
  </section>`)}</div>`;
}

function OutputsTab({ data, onOpenFile }) {
  if (!data.outputs.length) return html`<p class="thq-muted">${L("Brak plików wynikowych w katalogach roboczych tego agenta.", "No result files in this agent's work folders.")}</p>`;
  return html`<div class="thq-files">${data.outputs.map((f) => html`<${Thumb} key=${f.path} file=${f} onOpen=${onOpenFile}/>`)}</div>`;
}

function AboutTab({ data, fleetInfo }) {
  const a = data.agent;
  const info = fleetInfo || {};
  const s = data.stats || {};
  const pct = s.done_7d ? Math.round((100 * s.first_pass_7d) / s.done_7d) : null;
  return html`<div class="thq-about">
    <p>${info.description || a.description || ""}</p>
    <dl class="thq-facts">
      <div><dt>Model</dt><dd>${info.model || a.model_tier}</dd></div>
      <div><dt>${L("Maks. autonomia", "Max autonomy")}</dt><dd>${a.autonomy_max} <span class="thq-muted">${L("(publikacje, wdrożenia i płatności tylko za Twoją zgodą)", "(publishing, deployments and payments only with your approval)")}</span></dd></div>
      ${info.telegram_topic && html`<div><dt>Telegram</dt><dd>${info.telegram_topic === "general" ? L("DM i wątek General w TARS HQ", "DM and the General topic in TARS HQ") : L(`wątek „${info.telegram_topic}” w TARS HQ`, `the “${info.telegram_topic}” topic in TARS HQ`)}</dd></div>`}
      <div><dt>${L("7 dni", "7 days")}</dt><dd>${s.done_7d || 0} ${L("zamkniętych kart", "cards closed")}${pct != null ? L(`, ${pct}% przyjętych za pierwszym razem`, `, ${pct}% accepted first time`) : ""}</dd></div>
    </dl>
    ${info.personality && html`<div class="thq-dials">${info.personality.map(([k, v]) => html`<div key=${k} class="thq-dial">
      <span>${k}</span><span class="thq-dial-bar"><span style=${{ width: `${v}%` }}></span></span><strong>${v}%</strong></div>`)}</div>`}
    ${info.skills && info.skills.length > 0 && html`<section><h4 class="thq-h4">${L("Workflowy", "Workflows")}</h4>
      <div class="thq-tags">${info.skills.map((s) => html`<span key=${s} class="thq-tag">${s}</span>`)}</div></section>`}
    ${info.vendored > 0 && html`<p class="thq-muted">+ ${info.vendored} ${L("skilli zewnętrznych (open source, przypięte wersje).", "external skills (open source, pinned versions).")}</p>`}
  </div>`;
}

function AgentPanel({ name, agents, fleet, onClose, onOpenTask, onOpenFile, pending, onPendingDone, tab, setTab }) {
  const [data, err] = usePoll(() => api.agent(name), 2500, [name]);
  const listed = agents.find((a) => a.name === name);
  const info = fleet.find((a) => a.name === name);
  const head = localAgent((data && data.agent) || listed || { name });
  const s = STATUS[head.status] || STATUS.idle;
  return html`<aside class="thq-panel" aria-label=${`Agent ${head.label || name}`}>
    <header class="thq-panel-head">
      <span class="thq-avatar" aria-hidden="true">${head.emoji}</span>
      <div class="thq-panel-title"><h2>${head.label || head.title}</h2>
        <p class="thq-muted">${head.title} · <span class=${cx("thq-pill", `is-${s.tone}`)}>${s.label}</span></p></div>
      <button type="button" class="thq-icon-btn" onClick=${onClose} aria-label=${L("Zamknij panel", "Close panel")}>×</button>
    </header>
    <nav class="thq-tabs" role="tablist">${TABS.map((k) => html`<button key=${k} type="button" role="tab"
        aria-selected=${tab === k} class=${cx("thq-tab", tab === k && "is-active")} onClick=${() => setTab(k)}>${TAB_TEXT[k]}
        ${k === "cards" && data && html`<span class="thq-count">${Object.values(data.cards).reduce((n, l) => n + l.length, 0)}</span>`}
      </button>`)}</nav>
    <div class="thq-panel-body">
      ${err && !data && html`<p class="thq-error">${err}</p>`}
      ${!data && !err && html`<p class="thq-muted">${L("Wczytuję…", "Loading…")}</p>`}
      ${data && tab === "now" && html`<${NowTab} data=${data} agents=${agents} onOpenTask=${onOpenTask}/>`}
      ${data && tab === "cards" && html`<${CardsTab} data=${data} agents=${agents} onOpenTask=${onOpenTask}/>`}
      ${data && tab === "outputs" && html`<${OutputsTab} data=${data} onOpenFile=${onOpenFile}/>`}
      ${tab === "chat" && html`<${ChatView} agent=${head} agents=${agents} pending=${pending} onPendingDone=${onPendingDone} compact=${true}/>`}
      ${data && tab === "about" && html`<${AboutTab} data=${data} fleetInfo=${info}/>`}
    </div>
  </aside>`;
}
