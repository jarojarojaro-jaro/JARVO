// Czat z agentem: historia z Hermesa + strumień odpowiedzi (delty tekstu i chipy narzędzi na żywo).

const TOOL_VERBS = {
  web_search: ["search", "szuka"], web_extract: ["page", "czyta stronę"], terminal: ["terminal", "terminal"],
  read_file: ["file", "czyta"], write_file: ["write", "pisze"], patch: ["write", "poprawia"],
  browser_navigate: ["browser", "otwiera stronę"], image_generate: ["image", "generuje obraz"],
  video_generate: ["video", "generuje wideo"], skill_view: ["book", "czyta skill"], memory: ["memory", "pamięć"],
  delegate_task: ["team", "deleguje"], kanban_create: ["card", "zakłada kartę"], kanban_comment: ["card", "komentuje kartę"],
  kanban_complete: ["done", "zamyka kartę"], kanban_list: ["card", "przegląda tablicę"], kanban_show: ["card", "czyta kartę"],
  kanban_request_changes: ["review", "odsyła do poprawki"], todo: ["check", "planuje"], session_search: ["memory", "szuka w historii"],
};

function toolChip(name, preview) {
  const [icon, verb] = TOOL_VERBS[name] || [String(name || "").startsWith("kanban_") ? "card" : "tool", String(name || "narzędzie").replace(/_/g, " ")];
  let detail = typeof preview === "string" ? preview.replace(/\s+/g, " ").trim() : "";
  if (detail.length > 90) detail = detail.slice(0, 89) + "…";
  return { tool: name, icon, verb, detail, status: "running" };
}

function ToolChip({ t }) {
  return html`<span class=${cx("thq-chip", t.status && `is-${t.status}`)} title=${t.detail || t.tool}>
    <span aria-hidden="true">${ICON[t.icon] || ICON.tool}</span> ${t.verb}${t.detail ? html`<em>${t.detail}</em>` : null}
  </span>`;
}

// Kroki agenta zwinięte do jednej linii (ostatni krok widać, reszta po kliknięciu): odpowiedź jest ważniejsza.
function ToolChips({ tools }) {
  const [open, setOpen] = useState(false);
  if (!tools || !tools.length) return null;
  if (tools.length <= 2 || open) {
    return html`<div class="thq-chips">
      ${tools.map((t, i) => html`<${ToolChip} key=${i} t=${t}/>`)}
      ${open ? html`<button type="button" class="thq-chips-toggle" onClick=${() => setOpen(false)}>zwiń</button>` : null}
    </div>`;
  }
  const last = tools[tools.length - 1];
  return html`<div class="thq-chips">
    <button type="button" class="thq-chips-toggle" onClick=${() => setOpen(true)} aria-expanded="false">▸ ${tools.length} kroków</button>
    <${ToolChip} t=${last}/>
  </div>`;
}

function ChatView({ agent, agents, pending, onPendingDone, compact }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [text, setText] = useState("");
  const listRef = useRef(null);
  const name = agent && agent.name;

  useEffect(() => {
    if (!name) return undefined;
    let alive = true;
    setLoading(true); setError(null);
    api.history(name).then((h) => {
      if (!alive) return;
      setMessages(h.messages || []);
      if (h.error) setError(h.error);
    }).catch((e) => alive && setError(e.message)).finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [name]);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  const send = useCallback(async (raw) => {
    const msg = String(raw || "").trim();
    if (!msg || busy || !name) return;
    setBusy(true); setError(null); setText("");
    setMessages((m) => [...m, { role: "user", text: msg, ts: Date.now() / 1000 }, { role: "assistant", text: "", tools: [], live: true }]);
    const patch = (fn) => setMessages((m) => {
      const copy = m.slice();
      const last = { ...copy[copy.length - 1] };
      fn(last);
      copy[copy.length - 1] = last;
      return copy;
    });
    try {
      for await (const { event, data } of api.send(name, msg)) {
        if (event === "assistant.delta") patch((l) => { l.text = (l.text || "") + (data.delta || ""); });
        else if (event === "tool.started") patch((l) => { l.tools = [...(l.tools || []), toolChip(data.tool_name, data.preview)]; });
        else if (event === "tool.completed" || event === "tool.failed") patch((l) => {
          const tools = (l.tools || []).slice();
          for (let i = tools.length - 1; i >= 0; i--) {
            if (tools[i].tool === data.tool_name && tools[i].status === "running") { tools[i] = { ...tools[i], status: event === "tool.failed" ? "error" : "done" }; break; }
          }
          l.tools = tools;
        });
        else if (event === "assistant.completed" && typeof data.content === "string") patch((l) => { l.text = data.content; });
        else if (event === "run.failed" || event === "error") setError(data.message || data.error || "Agent nie dokończył odpowiedzi.");
        else if (event === "run.cancelled") setError("Przerwano.");
      }
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      patch((l) => { l.live = false; l.tools = (l.tools || []).map((t) => (t.status === "running" ? { ...t, status: "done" } : t)); });
      setBusy(false);
    }
  }, [busy, name]);

  useEffect(() => {
    if (pending && pending.agent === name && pending.text && !busy && !loading) {
      send(pending.text);
      onPendingDone && onPendingDone();
    }
  }, [pending, name, busy, loading]);

  const reset = async () => {
    if (busy) return;
    await api.reset(name);
    setMessages([]); setError(null);
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); }
  };

  const who = agent ? agent.label || agent.title : "";
  return html`<div class=${cx("thq-chat", compact && "is-compact")}>
    <div class="thq-chat-list" ref=${listRef} aria-live="polite">
      ${loading && html`<p class="thq-muted">Wczytuję rozmowę…</p>`}
      ${!loading && messages.length === 0 && html`<div class="thq-chat-empty">
        <p><strong>${agent && agent.emoji} ${who}</strong></p>
        <p class="thq-muted">${agent && agent.kind === "orchestrator"
          ? "Napisz, co chcesz osiągnąć. TARS rozpisze misję i przydzieli pracę."
          : "Rozmowa bezpośrednia. Większe zlecenia lepiej dawać przez TARS-a: on pilnuje całości."}</p>
      </div>`}
      ${messages.map((m, i) => html`<div key=${i} class=${cx("thq-msg", `is-${m.role}`, m.live && "is-live")}>
        ${m.role === "assistant" && html`<span class="thq-msg-who" aria-hidden="true">${agent && agent.emoji}</span>`}
        <div class="thq-msg-body">
          ${m.role === "assistant" && html`<${ToolChips} tools=${m.tools}/>`}
          ${m.text ? (m.role === "assistant" ? html`<${Markdown} text=${m.text}/>` : html`<p>${m.text}</p>`)
            : m.live ? html`<p class="thq-typing" aria-label="pisze"><span></span><span></span><span></span></p>` : null}
        </div>
      </div>`)}
    </div>
    ${error && html`<p class="thq-error" role="alert">${error}</p>`}
    <form class="thq-chat-form" onSubmit=${(e) => { e.preventDefault(); send(text); }}>
      <label class="thq-sr" for=${`thq-input-${name}`}>Wiadomość do: ${who}</label>
      <textarea id=${`thq-input-${name}`} rows="1" value=${text} placeholder=${`Napisz do: ${who}`}
        onInput=${(e) => setText(e.target.value)} onKeyDown=${onKey} disabled=${!name}></textarea>
      <button type="submit" class="thq-send" disabled=${busy || !text.trim()}>${busy ? "…" : "Wyślij"}</button>
      <button type="button" class="thq-ghost" onClick=${reset} disabled=${busy || !messages.length} title="Zacznij nową rozmowę">Nowa</button>
    </form>
  </div>`;
}

function ChatDock({ agents, target, setTarget, open, setOpen, pending, onPendingDone }) {
  const agent = agents.find((a) => a.name === target) || agents[0];
  return html`<section class=${cx("thq-dock", open && "is-open")} aria-label="Rozmowa">
    <header class="thq-dock-head">
      <button type="button" class="thq-dock-toggle" onClick=${() => setOpen(!open)} aria-expanded=${open}>
        ${open ? "▾" : "▴"} Rozmowa
      </button>
      <div class="thq-dock-targets" role="tablist" aria-label="Z kim rozmawiasz">
        ${agents.map((a) => html`<button key=${a.name} type="button" role="tab" aria-selected=${a.name === (agent && agent.name)}
            class=${cx("thq-target", a.name === (agent && agent.name) && "is-active")}
            onClick=${() => { setTarget(a.name); setOpen(true); }}>
          <span aria-hidden="true">${a.emoji}</span> ${a.short || a.name}
        </button>`)}
      </div>
    </header>
    ${open && agent && html`<${ChatView} agent=${agent} agents=${agents} pending=${pending} onPendingDone=${onPendingDone}/>`}
  </section>`;
}
