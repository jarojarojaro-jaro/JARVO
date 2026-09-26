// Panel agenta (po kliknięciu pokoju) i okna podglądu: karta kanbana, plik wynikowy.

const TABS = [["now", "Teraz"], ["cards", "Karty"], ["outputs", "Wyniki"], ["chat", "Czat"], ["about", "O agencie"]];

function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return html`<div class="thq-modal-back" onClick=${(e) => e.target === e.currentTarget && onClose()}>
    <div class=${cx("thq-modal", wide && "is-wide")} role="dialog" aria-modal="true" aria-label=${title}>
      <header class="thq-modal-head"><h3>${title}</h3>
        <button type="button" class="thq-icon-btn" onClick=${onClose} aria-label="Zamknij">×</button></header>
      <div class="thq-modal-body">${children}</div>
    </div>
  </div>`;
}

function TaskModal({ taskId, agents, onClose }) {
  const [t, setT] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api.task(taskId).then(setT).catch((e) => setErr(e.message)); }, [taskId]);
  const who = (n) => { const a = agents.find((x) => x.name === n); return a ? `${a.emoji} ${a.short || a.name}` : n || "—"; };
  return html`<${Modal} title=${t ? t.title : "Karta"} onClose=${onClose} wide=${true}>
    ${err && html`<p class="thq-error">${err}</p>`}
    ${!t && !err && html`<p class="thq-muted">Wczytuję kartę…</p>`}
    ${t && html`<div class="thq-task">
      <dl class="thq-facts">
        <div><dt>Stan</dt><dd><span class=${cx("thq-pill", `is-card-${t.status}`)}>${CARD_STATUS[t.status] || t.status}</span></dd></div>
        <div><dt>Wykonawca</dt><dd>${who(t.assignee)}</dd></div>
        <div><dt>Założona</dt><dd>${ago(t.created_at)}</dd></div>
        ${t.completed_at && html`<div><dt>Zakończona</dt><dd>${ago(t.completed_at)}</dd></div>`}
        <div><dt>ID</dt><dd><code>${t.id}</code></dd></div>
      </dl>
      ${t.body && html`<section><h4>Zlecenie</h4><${Markdown} text=${t.body}/></section>`}
      ${t.result && html`<section><h4>Wynik</h4><${Markdown} text=${t.result}/></section>`}
      ${t.comments && t.comments.length > 0 && html`<section><h4>Komentarze</h4>
        ${t.comments.map((c, i) => html`<div key=${i} class="thq-comment"><strong>${who(c.author)}</strong> <span class="thq-muted">${ago(c.created_at)}</span><${Markdown} text=${c.body}/></div>`)}
      </section>`}
      <section><h4>Historia</h4><ol class="thq-timeline">
        ${(t.events || []).map((e, i) => html`<li key=${i}><span class="thq-muted">${clock(e.created_at)}</span> ${EVENT_PL[e.kind] || e.kind}
          ${e.payload && e.payload.reason ? html`<em> „${e.payload.reason}”</em>` : null}
          ${e.payload && e.payload.summary ? html`<em> ${e.payload.summary}</em>` : null}</li>`)}
      </ol></section>
    </div>`}
  </${Modal}>`;
}

const EVENT_PL = {
  created: "założona", promoted: "gotowa do pracy", promoted_manual: "gotowa do pracy", claimed: "przejęta przez pracownika",
  spawned: "pracownik wystartował", completed: "zakończona", blocked: "zablokowana", unblocked: "odblokowana",
  review_requested: "oddana do oceny", changes_requested: "odesłana do poprawki", commented: "komentarz",
  archived: "zarchiwizowana", timed_out: "przekroczony czas", gave_up: "porzucona po błędach", stale: "brak sygnału",
  reclaimed: "przejęta ponownie", edited: "edytowana", linked: "powiązana", scheduled: "zaplanowana",
};

function FilePreview({ file, onClose }) {
  const url = useBlobUrl(file.path);
  const [text, setText] = useState(null);
  useEffect(() => {
    if (file.kind !== "text" && file.kind !== "html") return;
    api.fileBlob(file.path).then((b) => b.text()).then((t) => setText(t.slice(0, 60000))).catch(() => setText("Nie udało się wczytać pliku."));
  }, [file.path]);
  return html`<${Modal} title=${file.name} onClose=${onClose} wide=${true}>
    <p class="thq-muted thq-path">${file.path} · ${bytes(file.size)}</p>
    ${file.kind === "image" && (url ? html`<img class="thq-preview-img" src=${url} alt=${file.name}/>` : html`<p class="thq-muted">Wczytuję…</p>`)}
    ${file.kind === "video" && url && html`<video class="thq-preview-img" src=${url} controls></video>`}
    ${file.kind === "pdf" && url && html`<iframe class="thq-preview-pdf" src=${url} title=${file.name}></iframe>`}
    ${(file.kind === "text" || file.kind === "html") && html`<pre class="thq-preview-text">${text == null ? "Wczytuję…" : text}</pre>`}
    ${["archive", "doc", "other"].includes(file.kind) && html`<p>Tego typu pliku nie da się podejrzeć w przeglądarce. Leży na serwerze pod ścieżką powyżej.</p>`}
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
  if (!items || !items.length) return html`<p class="thq-muted">Brak zapisanych kroków w tej sesji.</p>`;
  return html`<ol class="thq-activity">${items.slice().reverse().map((it, i) => html`<li key=${i} class=${cx(`is-${it.kind}`, it.status && `is-${it.status}`)}>
    <span class="thq-act-time">${clock(it.ts)}</span>
    ${it.kind === "tool" && html`<span class="thq-act-body"><span class="thq-act-icon" aria-hidden="true">${ICON[it.icon] || ICON.tool}</span>
      <strong>${it.verb}</strong>${it.detail ? html` <code>${it.detail}</code>` : null}
      ${it.status === "running" && html`<span class="thq-live-dot" aria-label="w toku"></span>`}
      ${it.status === "error" && html`<span class="thq-pill is-bad">błąd</span>`}</span>`}
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
        <span class="thq-eyebrow">${a.status === "judging" || running.assignee !== a.name ? "Ocenia kartę" : "Pracuje nad"}</span>
        <strong>${running.title}</strong>
        <span class="thq-muted">od ${duration(running.started_at, now)}${a.quiet ? " · brak sygnału od kilku minut" : ""}</span>
      </button>
      <h4 class="thq-h4">Na żywo</h4>
      <${Activity} items=${data.activity} now=${now}/>
    </div>`;
  }
  const blocked = data.cards.blocked[0];
  const review = data.cards.review[0];
  return html`<div class="thq-now">
    ${blocked && html`<button type="button" class="thq-now-card is-bad" onClick=${() => onOpenTask(blocked.id)}>
      <span class="thq-eyebrow">Zablokowane</span><strong>${blocked.title}</strong>
      <span class="thq-muted">${a.reason ? `Pytanie: ${a.reason}` : "Czeka na decyzję albo brakujący dostęp."}</span></button>`}
    ${review && html`<button type="button" class="thq-now-card is-warn" onClick=${() => onOpenTask(review.id)}>
      <span class="thq-eyebrow">Czeka na ocenę TARS-a</span><strong>${review.title}</strong></button>`}
    ${data.cards.judging.length > 0 && html`<div><h4 class="thq-h4">Do oceny (${data.cards.judging.length})</h4>
      ${data.cards.judging.map((c) => html`<${CardRow} key=${c.id} card=${c} agents=${agents} onOpen=${onOpenTask}/>`)}</div>`}
    ${!blocked && !review && data.cards.judging.length === 0 && html`<div class="thq-idle">
      <p><strong>${data.cards.ready.length ? `W kolejce: ${data.cards.ready.length}` : "Wolne biurko."}</strong></p>
      <p class="thq-muted">${data.cards.ready.length ? "Dispatcher przydzieli następną kartę w ciągu minuty." : "Nie ma teraz zadań. Zlecenia daje TARS albo Ty w czacie."}</p>
    </div>`}
    ${data.cards.done.length > 0 && html`<div><h4 class="thq-h4">Ostatnio zrobione</h4>
      ${data.cards.done.slice(0, 5).map((c) => html`<${CardRow} key=${c.id} card=${c} agents=${agents} onOpen=${onOpenTask}/>`)}</div>`}
  </div>`;
}

function CardsTab({ data, agents, onOpenTask }) {
  const groups = [["running", "W toku"], ["judging", "Do oceny"], ["blocked", "Zablokowane"], ["review", "Czeka na ocenę"],
    ["ready", "W kolejce"], ["triage", "Triage"], ["done", "Zrobione (7 dni)"]];
  const any = groups.some(([k]) => data.cards[k] && data.cards[k].length);
  if (!any) return html`<p class="thq-muted">Ten agent nie ma kart z ostatnich 7 dni.</p>`;
  return html`<div class="thq-groups">${groups.map(([k, label]) => data.cards[k] && data.cards[k].length > 0 && html`<section key=${k}>
    <h4 class="thq-h4">${label} <span class="thq-count">${data.cards[k].length}</span></h4>
    ${data.cards[k].map((c) => html`<${CardRow} key=${c.id} card=${c} agents=${agents} onOpen=${onOpenTask}/>`)}
  </section>`)}</div>`;
}

function OutputsTab({ data, onOpenFile }) {
  if (!data.outputs.length) return html`<p class="thq-muted">Brak plików wynikowych w katalogach roboczych tego agenta.</p>`;
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
      <div><dt>Maks. autonomia</dt><dd>${a.autonomy_max} <span class="thq-muted">(publikacje, wdrożenia i płatności tylko za Twoją zgodą)</span></dd></div>
      ${info.telegram_topic && html`<div><dt>Telegram</dt><dd>${info.telegram_topic === "general" ? "DM i wątek General w TARS HQ" : `wątek „${info.telegram_topic}” w TARS HQ`}</dd></div>`}
      <div><dt>7 dni</dt><dd>${s.done_7d || 0} zamkniętych kart${pct != null ? `, ${pct}% przyjętych za pierwszym razem` : ""}</dd></div>
    </dl>
    ${info.personality && html`<div class="thq-dials">${info.personality.map(([k, v]) => html`<div key=${k} class="thq-dial">
      <span>${k}</span><span class="thq-dial-bar"><span style=${{ width: `${v}%` }}></span></span><strong>${v}%</strong></div>`)}</div>`}
    ${info.skills && info.skills.length > 0 && html`<section><h4 class="thq-h4">Workflowy</h4>
      <div class="thq-tags">${info.skills.map((s) => html`<span key=${s} class="thq-tag">${s}</span>`)}</div></section>`}
    ${info.vendored > 0 && html`<p class="thq-muted">+ ${info.vendored} skilli zewnętrznych (open source, przypięte wersje).</p>`}
  </div>`;
}

function AgentPanel({ name, agents, fleet, onClose, onOpenTask, onOpenFile, pending, onPendingDone, tab, setTab }) {
  const [data, err] = usePoll(() => api.agent(name), 2500, [name]);
  const listed = agents.find((a) => a.name === name);
  const info = fleet.find((a) => a.name === name);
  const head = (data && data.agent) || listed || { name };
  const s = STATUS[head.status] || STATUS.idle;
  return html`<aside class="thq-panel" aria-label=${`Agent ${head.label || name}`}>
    <header class="thq-panel-head">
      <span class="thq-avatar" aria-hidden="true">${head.emoji}</span>
      <div class="thq-panel-title"><h2>${head.label || head.title}</h2>
        <p class="thq-muted">${head.title} · <span class=${cx("thq-pill", `is-${s.tone}`)}>${s.label}</span></p></div>
      <button type="button" class="thq-icon-btn" onClick=${onClose} aria-label="Zamknij panel">×</button>
    </header>
    <nav class="thq-tabs" role="tablist">${TABS.map(([k, label]) => html`<button key=${k} type="button" role="tab"
        aria-selected=${tab === k} class=${cx("thq-tab", tab === k && "is-active")} onClick=${() => setTab(k)}>${label}
        ${k === "cards" && data && html`<span class="thq-count">${Object.values(data.cards).reduce((n, l) => n + l.length, 0)}</span>`}
      </button>`)}</nav>
    <div class="thq-panel-body">
      ${err && !data && html`<p class="thq-error">${err}</p>`}
      ${!data && !err && html`<p class="thq-muted">Wczytuję…</p>`}
      ${data && tab === "now" && html`<${NowTab} data=${data} agents=${agents} onOpenTask=${onOpenTask}/>`}
      ${data && tab === "cards" && html`<${CardsTab} data=${data} agents=${agents} onOpenTask=${onOpenTask}/>`}
      ${data && tab === "outputs" && html`<${OutputsTab} data=${data} onOpenFile=${onOpenFile}/>`}
      ${tab === "chat" && html`<${ChatView} agent=${head} agents=${agents} pending=${pending} onPendingDone=${onPendingDone} compact=${true}/>`}
      ${data && tab === "about" && html`<${AboutTab} data=${data} fleetInfo=${info}/>`}
    </div>
  </aside>`;
}
