// Pasek stanu floty i Centrala (decyzje, misje, zdarzenia), widoczna, gdy nie wybrano pokoju.

function Hud({ state, error, onDecisions, now }) {
  const b = (state && state.board) || {};
  const d = (state && state.decisions) || [];
  const stale = !state || (now - state.ts > 20);
  const chips = [
    ["W toku", b.running || 0, "work"],
    ["Ocena", b.review || 0, "warn"],
    ["Blokady", b.blocked || 0, "bad"],
    ["Kolejka", b.ready || 0, "info"],
    ["Zrobione dziś", b.done_today || 0, "good"],
  ];
  return html`<header class="thq-hud">
    <div class="thq-brand">
      <span class="thq-brand-mark" aria-hidden="true"><span></span><span></span><span></span><span></span></span>
      <div><h1>TARS HQ</h1><p class="thq-muted">${stale ? (error ? `Brak połączenia: ${error}` : "Łączę z flotą…") : `Na żywo · ${clock(state.ts)}`}</p></div>
    </div>
    <ul class="thq-stats" aria-label="Stan tablicy">
      ${chips.map(([label, n, tone]) => html`<li key=${label} class=${cx("thq-stat", n > 0 && `is-${tone}`)}>
        <strong>${n}</strong><span>${label}</span></li>`)}
    </ul>
    <button type="button" class=${cx("thq-decisions-btn", d.length > 0 && "has-items")} onClick=${onDecisions}>
      Decyzje <span class="thq-badge">${d.length}</span>
    </button>
  </header>`;
}

function Decision({ item, agents, onAnswer }) {
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  const a = agents.find((x) => x.name === item.assignee);
  const submit = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    onAnswer(item, text.trim());
    setSent(true);
  };
  return html`<li class="thq-decision">
    <p class="thq-decision-q">${item.reason || "Agent czeka na Twoją decyzję."}</p>
    <p class="thq-muted">${a ? `${a.emoji} ${a.short || a.name}` : item.assignee} · ${item.title} · ${ago(item.since)}</p>
    ${sent ? html`<p class="thq-ok">Przekazane TARS-owi. On odblokuje kartę i da znać agentowi.</p>`
      : html`<form class="thq-decision-form" onSubmit=${submit}>
        <label class="thq-sr" for=${`thq-dec-${item.task_id}`}>Odpowiedź</label>
        <input id=${`thq-dec-${item.task_id}`} value=${text} onInput=${(e) => setText(e.target.value)} placeholder="Twoja odpowiedź"/>
        <button type="submit" class="thq-send" disabled=${!text.trim()}>Odpowiedz</button>
      </form>`}
  </li>`;
}

function MissionRow({ m, agents, onOpenTask }) {
  const pct = m.total ? Math.round((100 * m.done) / m.total) : 0;
  return html`<li class="thq-mission">
    <div class="thq-mission-head"><strong>${m.title}</strong><span class="thq-muted">${m.id}</span></div>
    <div class="thq-progress" role="progressbar" aria-valuenow=${pct} aria-valuemin="0" aria-valuemax="100"
      aria-label=${`Postęp: ${m.done} z ${m.total} kart`}><span style=${{ width: `${pct}%` }}></span></div>
    <div class="thq-mission-cards">
      ${m.cards.map((c) => {
        const a = agents.find((x) => x.name === c.assignee);
        return html`<button key=${c.id} type="button" class=${cx("thq-mcard", `is-card-${c.status}`)} onClick=${() => onOpenTask(c.id)}
          title=${`${c.title} · ${CARD_STATUS[c.status] || c.status}`}>${a ? a.emoji : "▭"}</button>`;
      })}
      <span class="thq-muted">${m.done}/${m.total} kart</span>
    </div>
  </li>`;
}

function Center({ state, agents, onAnswer, onOpenTask, focus }) {
  const d = (state && state.decisions) || [];
  const missions = (state && state.missions) || [];
  const feed = (state && state.feed) || [];
  const decRef = useRef(null);
  useEffect(() => { if (focus === "decisions" && decRef.current) decRef.current.scrollIntoView({ behavior: "smooth", block: "start" }); }, [focus]);
  return html`<aside class="thq-panel thq-center" aria-label="Centrala">
    <section ref=${decRef}>
      <h2 class="thq-h2">Decyzje <span class="thq-count">${d.length}</span></h2>
      ${d.length === 0 ? html`<p class="thq-muted">Nic nie czeka na Ciebie. Agenci pytają tylko o to, czego nie da się rozstrzygnąć bez Ciebie.</p>`
        : html`<ul class="thq-list">${d.map((it) => html`<${Decision} key=${it.task_id} item=${it} agents=${agents} onAnswer=${onAnswer}/>`)}</ul>`}
    </section>
    <section>
      <h2 class="thq-h2">Misje <span class="thq-count">${missions.length}</span></h2>
      ${missions.length === 0 ? html`<p class="thq-muted">Brak aktywnych misji. Napisz do TARS-a, czego potrzebujesz.</p>`
        : html`<ul class="thq-list">${missions.map((m) => html`<${MissionRow} key=${m.id} m=${m} agents=${agents} onOpenTask=${onOpenTask}/>`)}</ul>`}
    </section>
    <section>
      <h2 class="thq-h2">Na bieżąco</h2>
      ${feed.length === 0 ? html`<p class="thq-muted">Tablica jest spokojna.</p>`
        : html`<ol class="thq-feed">${feed.slice(0, 18).map((e, i) => {
          const a = agents.find((x) => x.name === e.agent);
          return html`<li key=${i} class=${cx(`is-${e.tone}`)}>
            <span class="thq-muted thq-feed-time">${clock(e.ts)}</span>
            <span>${a ? html`<span aria-hidden="true">${a.emoji}</span> ` : null}<button type="button" class="thq-link" onClick=${() => onOpenTask(e.task_id)}>${e.title}</button>
              <span class="thq-muted"> ${e.text}</span></span>
          </li>`;
        })}</ol>`}
    </section>
  </aside>`;
}
