// Budynek: mostek TARS-a na piętrze, pokoje agentów na parterze (kolejni agenci dokładają pokoje).

const ICON = {
  search: "⌕", page: "▤", terminal: "›_", file: "▤", write: "✎", browser: "◍", eye: "◉", image: "▦",
  video: "▶", audio: "♪", book: "❏", memory: "◈", check: "✓", question: "?", team: "⇄", card: "▭",
  done: "✔", block: "■", review: "⚖", clock: "◷", tool: "⚙",
};

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
  const [fx] = r.fig;
  const icon = st === "working" && agent.tool ? ICON[agent.tool.icon] || ICON.tool : st === "blocked" ? "!" : st === "review" ? "?" : "⚖";
  // dymek wisi na ścianie nad figurką (nie zasłania szyldu), strzałka wskazuje głowę
  return html`<div class=${cx("thq-bubble", tone && `is-${tone}`, (r.bubble === "left" || fx > 55) && "is-left")}
      style=${{ left: `${fx}%` }} title=${detail ? `${verb}: ${detail}` : verb}>
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

function Room({ agent, board, selected, onSelect }) {
  const wide = agent.room === "bridge";
  const onKey = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(agent.name); } };
  return html`<div role="button" tabIndex="0" class=${cx("thq-room", wide && "is-wide", selected && "is-selected", `is-${agent.status}`)}
      onClick=${() => onSelect(agent.name)} onKeyDown=${onKey} aria-pressed=${selected}
      aria-label=${`${agent.label || agent.title}, ${(STATUS[agent.status] || STATUS.idle).label}. Otwórz szczegóły.`}>
    <${RoomSign} agent=${agent}/>
    <div class="thq-room-stage">
      <${RoomArt} agent=${agent} board=${board}/>
      <${Bubble} agent=${agent}/>
    </div>
  </div>`;
}

function Roof({ side }) {
  if (side === "left") {
    return html`<div class="thq-roof thq-roof-left" aria-hidden="true"><svg viewBox="0 0 400 300">
      <rect x="10" y="236" width="380" height="30" rx="3" fill="#8DA05A"/>
      ${Array.from({ length: 14 }).map((_, i) => html`<rect key=${i} x=${20 + i * 27} y="231" width="16" height="7" rx="2" fill="#8DA05A"/>`)}
      <rect x="120" y="150" width="14" height="86" fill="#7A5230"/>
      <circle cx="127" cy="120" r="42" fill="#3E9B57"/><circle cx="98" cy="146" r="28" fill="#358A4B"/><circle cx="158" cy="142" r="30" fill="#46A862"/>
      <rect x="220" y="206" width="100" height="10" rx="3" fill="#B5764A"/><rect x="228" y="216" width="8" height="20" fill="#8A5A33"/><rect x="304" y="216" width="8" height="20" fill="#8A5A33"/>
      <rect x="220" y="180" width="100" height="8" rx="3" fill="#B5764A"/>
    </svg></div>`;
  }
  return html`<div class="thq-roof thq-roof-right" aria-hidden="true"><svg viewBox="0 0 400 300">
    <rect x="10" y="236" width="380" height="30" rx="3" fill="#7C8896"/>
    ${Array.from({ length: 14 }).map((_, i) => html`<rect key=${i} x=${20 + i * 27} y="231" width="16" height="7" rx="2" fill="#7C8896"/>`)}
    <path d="M200 236 L200 70" stroke="#5A6574" stroke-width="6"/>
    <path d="M186 236 L200 150 L214 236" stroke="#5A6574" stroke-width="4" fill="none"/>
    <circle class="thq-beacon" cx="200" cy="64" r="8" fill="#FF3B30"/>
    <g transform="translate(300 180) rotate(-25)"><path d="M-40 0 Q0 40 40 0 Z" fill="#DDE3EA"/><path d="M0 18 L0 -18" stroke="#5A6574" stroke-width="3"/><circle cx="0" cy="-20" r="4" fill="#5A6574"/></g>
    <rect x="280" y="206" width="40" height="30" fill="#5A6574"/>
    <g transform="translate(80 150)"><rect x="0" y="0" width="4" height="86" fill="#5A6574"/>
      <path class="thq-flag" d="M4 2 L60 2 L52 16 L60 30 L4 30 Z" fill="#D6281E"/>
      <text x="12" y="21" font-size="12" font-weight="800" fill="#FFFFFF" font-family="sans-serif">TARS</text></g>
  </svg></div>`;
}

function Building({ agents, board, selected, onSelect }) {
  const boss = agents.find((a) => a.room === "bridge") || agents[0];
  const crew = agents.filter((a) => a !== boss);
  return html`<div class="thq-building">
    <div class="thq-floor thq-floor-top">
      <${Roof} side="left"/>
      ${boss && html`<${Room} agent=${boss} board=${board} selected=${selected === boss.name} onSelect=${onSelect}/>`}
      <${Roof} side="right"/>
    </div>
    <div class="thq-floor thq-floor-ground" style=${{ "--thq-cols": Math.min(Math.max(crew.length, 1), 4) }}>
      ${crew.map((a) => html`<${Room} key=${a.name} agent=${a} board=${board} selected=${selected === a.name} onSelect=${onSelect}/>`)}
    </div>
    <div class="thq-baseplate" aria-hidden="true"></div>
  </div>`;
}
