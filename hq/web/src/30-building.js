// Wieża TARS: scena pixel-art (20-art.js) + warstwa HTML nad pokojami (kliknięcie, szyld, dymek).
// Mostek szefa na górze, pokoje załogi po dwa na piętro wokół szybu windy, maszynownia w piwnicy.

const ICON = {
  search: "⌕", page: "▤", terminal: "›_", file: "▤", write: "✎", browser: "◍", eye: "◉", image: "▦",
  video: "▶", audio: "♪", book: "❏", memory: "◈", check: "✓", question: "?", team: "⇄", card: "▭",
  done: "✔", block: "■", review: "⚖", clock: "◷", tool: "⚙",
};

const pct = (v, total) => `${(100 * v) / total}%`;

function Bubble({ agent }) {
  const st = agent.status;
  let tone = "", verb = "", detail = "";
  if (st === "working" && agent.tool) {
    verb = agent.tool.verb; detail = agent.tool.detail || "";
  } else if (st === "working") {
    verb = agent.quiet ? "cisza…" : "myśli…";
  } else if (st === "judging") {
    verb = "ocenia"; detail = agent.headline;
  } else if (st === "blocked") {
    tone = "bad"; verb = "pytanie"; detail = agent.reason || "potrzebna decyzja";
  } else if (st === "review") {
    tone = "warn"; verb = "czeka na ocenę";
  } else {
    return null;
  }
  const r = ROOMS[agent.room] || ROOMS.office;
  const [fx, fy] = r.fig;
  const icon = st === "working" && agent.tool ? ICON[agent.tool.icon] || ICON.tool : st === "blocked" ? "!" : st === "review" ? "?" : "⚖";
  // dymek nad głową postaci; strzałka wskazuje głowę
  const side = r.bubble === "side";
  const pos = side ? { left: `calc(${fx}% + 34px)`, top: `${fy}%` } : { left: `${fx}%`, bottom: `calc(${100 - fy}% + 6px)` };
  return html`<div class=${cx("thq-bubble", tone && `is-${tone}`, side ? "is-side" : (r.bubble === "left" || fx > 60) && "is-left")}
      style=${pos} title=${detail ? `${verb}: ${detail}` : verb}>
    <span class="thq-bubble-icon" aria-hidden="true">${icon}</span>
    <span class="thq-bubble-body"><span class="thq-bubble-verb">${verb}</span>${detail && html`<span class="thq-bubble-detail">${detail}</span>`}</span>
  </div>`;
}

function RoomSign({ agent }) {
  const s = STATUS[agent.status] || STATUS.idle;
  const c = agent.counts || {};
  return html`<div class="thq-sign">
    <span class="thq-sign-emoji" aria-hidden="true">${agent.emoji}</span>
    <span class="thq-sign-name" title=${agent.label || agent.title}>${agent.short || agent.label || agent.title}</span>
    <span class=${cx("thq-pill", `is-${s.tone}`)} title=${s.label}><span class="thq-pill-text">${s.label}</span></span>
    ${(c.ready > 0 || c.done_today > 0) && html`<span class="thq-sign-meta">
      ${c.ready > 0 && html`<span title="Karty w kolejce">▭ ${c.ready}</span>`}
      ${c.done_today > 0 && html`<span title="Zrobione dziś">✔ ${c.done_today}</span>`}
    </span>`}
  </div>`;
}

function Room({ agent, box, lay, selected, onSelect }) {
  const wide = agent.room === "bridge";
  const onKey = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(agent.name); } };
  const style = { left: pct(box.x, lay.W), top: pct(box.y, lay.H), width: pct(box.w, lay.W), height: pct(box.h, lay.H) };
  return html`<div role="button" tabIndex="0" style=${style}
      class=${cx("thq-room", wide && "is-wide", selected && "is-selected", `is-${agent.status}`)}
      onClick=${() => onSelect(agent.name)} onKeyDown=${onKey} aria-pressed=${selected}
      aria-label=${`${agent.label || agent.title}, ${(STATUS[agent.status] || STATUS.idle).label}. Otwórz szczegóły.`}>
    <${RoomSign} agent=${agent}/>
    <${Bubble} agent=${agent}/>
  </div>`;
}

function Building({ agents, board, selected, onSelect, online = true }) {
  const boss = agents.find((a) => a.room === "bridge") || agents[0];
  const crew = agents.filter((a) => a !== boss);
  const lay = towerLayout(crew.length);
  const moving = agents.some((a) => isBusy(a.status));
  const slots = crew.map((a, i) => ({ agent: a, box: lay.rooms[i] }));
  const spare = lay.rooms.slice(crew.length);
  const ref = useRef(null);
  // na wąskim ekranie scena przewija się w bok: na start pokazujemy środek (mostek szefa)
  useEffect(() => {
    const sc = ref.current && ref.current.parentElement;
    if (sc && sc.scrollWidth > sc.clientWidth) sc.scrollLeft = (sc.scrollWidth - sc.clientWidth) / 2;
  }, []);
  return html`<div class="thq-building thq-tower" ref=${ref}>
    <svg class="thq-tower-art" viewBox=${`0 0 ${lay.W} ${lay.H}`} aria-hidden="true">
      <${TowerBackdrop} floors=${lay.floors}/>
      <${TowerMachines} floors=${lay.floors} moving=${moving} online=${online}/>
      ${boss && html`<${PixRoom} box=${lay.bridge} agent=${boss} board=${board} crew=${crew}/>`}
      ${slots.map(({ agent, box }) => html`<${PixRoom} key=${agent.name} box=${box} agent=${agent} board=${board}/>`)}
      ${spare.map((box, i) => html`<${StorageRoom} key=${`spare-${i}`} box=${box}/>`)}
    </svg>
    <div class="thq-tower-hits">
      ${boss && html`<${Room} agent=${boss} box=${lay.bridge} lay=${lay} selected=${selected === boss.name} onSelect=${onSelect}/>`}
      ${slots.map(({ agent, box }) => html`<${Room} key=${agent.name} agent=${agent} box=${box} lay=${lay} selected=${selected === agent.name} onSelect=${onSelect}/>`)}
    </div>
  </div>`;
}
