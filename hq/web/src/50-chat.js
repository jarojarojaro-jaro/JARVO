// Czat z agentem: historia z Hermesa + strumień odpowiedzi (delty tekstu i chipy narzędzi na żywo),
// załączniki (📎, Ctrl+V, przeciągnięcie) i pliki w odpowiedziach (MEDIA:, ścieżki floty).

const TOOL_VERBS = {
  web_search: ["search", "szuka", "searching"], web_extract: ["page", "czyta stronę", "reading page"], terminal: ["terminal", "terminal", "terminal"],
  read_file: ["file", "czyta", "reading"], write_file: ["write", "pisze", "writing"], patch: ["write", "poprawia", "editing"],
  browser_navigate: ["browser", "otwiera stronę", "opening page"], image_generate: ["image", "generuje obraz", "generating image"],
  video_generate: ["video", "generuje wideo", "generating video"], skill_view: ["book", "czyta skill", "reading skill"], memory: ["memory", "pamięć", "memory"],
  delegate_task: ["team", "deleguje", "delegating"], kanban_create: ["card", "zakłada kartę", "creating card"], kanban_comment: ["card", "komentuje kartę", "commenting"],
  kanban_complete: ["done", "zamyka kartę", "closing card"], kanban_list: ["card", "przegląda tablicę", "checking board"], kanban_show: ["card", "czyta kartę", "reading card"],
  kanban_request_changes: ["review", "odsyła do poprawki", "requesting changes"], todo: ["check", "planuje", "planning"], session_search: ["memory", "szuka w historii", "searching history"],
  vision_analyze: ["image", "ogląda obraz", "looking at image"],
};

function toolChip(name, preview) {
  const v = TOOL_VERBS[name];
  const icon = v ? v[0] : String(name || "").startsWith("kanban_") ? "card" : "tool";
  const verb = v ? L(v[1], v[2]) : String(name || L("narzędzie", "tool")).replace(/_/g, " ");
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
      ${open ? html`<button type="button" class="thq-chips-toggle" onClick=${() => setOpen(false)}>${L("zwiń", "collapse")}</button>` : null}
    </div>`;
  }
  const last = tools[tools.length - 1];
  return html`<div class="thq-chips">
    <button type="button" class="thq-chips-toggle" onClick=${() => setOpen(true)} aria-expanded="false">▸ ${tools.length} ${L("kroków", "steps")}</button>
    <${ToolChip} t=${last}/>
  </div>`;
}

const MAX_ATTACH = 8;

// Załączniki w polu wiadomości: wysyłane od razu do tars/inbox, zdjęcia dodatkowo jako obraz dla modelu.
function useAttachments() {
  const [items, setItems] = useState([]);
  const add = useCallback((files) => {
    const list = Array.from(files || []).slice(0, MAX_ATTACH);
    for (const file of list) {
      const id = `${Date.now()}-${Math.random()}`;
      const isImg = /^image\//.test(file.type);
      const item = { id, file, name: file.name || (isImg ? "obraz.png" : "plik"), isImg, preview: isImg ? URL.createObjectURL(file) : null, status: "up" };
      setItems((xs) => (xs.length >= MAX_ATTACH ? xs : [...xs, item]));
      const named = file.name ? file : new File([file], item.name, { type: file.type });
      api.upload(named)
        .then((r) => setItems((xs) => xs.map((x) => (x.id === id ? { ...x, status: "ok", path: r.path, name: r.name } : x))))
        .catch((e) => setItems((xs) => xs.map((x) => (x.id === id ? { ...x, status: "err", error: e.message } : x))));
    }
  }, []);
  const remove = (id) => setItems((xs) => { const x = xs.find((i) => i.id === id); if (x && x.preview) URL.revokeObjectURL(x.preview); return xs.filter((i) => i.id !== id); });
  const clear = () => setItems([]);
  return { items, add, remove, clear };
}

function AttachChips({ items, onRemove }) {
  if (!items.length) return null;
  return html`<ul class="thq-attach" aria-label=${L("Załączniki", "Attachments")}>${items.map((a) => html`<li key=${a.id} class=${cx("thq-attach-item", `is-${a.status}`)}
      title=${a.error || a.name}>
    ${a.preview ? html`<img src=${a.preview} alt=""/>` : html`<span class="thq-attach-ic" aria-hidden="true">▤</span>`}
    <span class="thq-attach-name">${a.name}</span>
    <span class="thq-attach-st">${a.status === "up" ? L("wysyłam…", "uploading…") : a.status === "err" ? L("błąd", "error") : ""}</span>
    <button type="button" class="thq-attach-x" onClick=${() => onRemove(a.id)} aria-label=${L("Usuń załącznik", "Remove attachment")}>×</button>
  </li>`)}</ul>`;
}

function ChatView({ agent, agents, pending, onPendingDone, compact }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [text, setText] = useState("");
  const [drag, setDrag] = useState(false);
  const listRef = useRef(null);
  const fileRef = useRef(null);
  const att = useAttachments();
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

  const uploading = att.items.some((a) => a.status === "up");
  const ready = att.items.filter((a) => a.status === "ok");

  const send = useCallback(async (raw, files) => {
    const msg = String(raw || "").trim();
    const atts = files || [];
    if ((!msg && !atts.length) || busy || !name) return;
    setBusy(true); setError(null); setText("");
    let images = [];
    try {
      images = await Promise.all(atts.filter((a) => a.isImg).slice(0, 4).map((a) => imageDataUrl(a.file)));
    } catch (_) { images = []; }   // obraz, którego przeglądarka nie odczyta, i tak jest w pliku
    const shown = [msg, ...atts.map((a) => `📎 ${a.path}`)].filter(Boolean).join("\n");
    att.clear();
    setMessages((m) => [...m, { role: "user", text: shown, ts: Date.now() / 1000 }, { role: "assistant", text: "", tools: [], live: true }]);
    const patch = (fn) => setMessages((m) => {
      const copy = m.slice();
      const last = { ...copy[copy.length - 1] };
      fn(last);
      copy[copy.length - 1] = last;
      return copy;
    });
    try {
      const extra = atts.length ? { attachments: atts.map((a) => a.path), images } : undefined;
      for await (const { event, data } of api.send(name, msg, extra)) {
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
        else if (event === "run.failed" || event === "error") setError(data.message || data.error || L("Agent nie dokończył odpowiedzi.", "The agent did not finish its reply."));
        else if (event === "run.cancelled") setError(L("Przerwano.", "Cancelled."));
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

  const submit = () => { if (!uploading) send(text, ready); };
  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };
  // Ctrl+V: zrzut ekranu albo skopiowany plik trafia jako załącznik (tekst wkleja się normalnie)
  const onPaste = (e) => {
    const files = Array.from((e.clipboardData && e.clipboardData.files) || []);
    if (files.length) { e.preventDefault(); att.add(files); }
  };
  const onDrop = (e) => {
    e.preventDefault(); setDrag(false);
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) att.add(e.dataTransfer.files);
  };
  const onDragOver = (e) => {
    if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) { e.preventDefault(); setDrag(true); }
  };

  const who = agent ? agent.label || agent.title : "";
  const canSend = !busy && !uploading && (text.trim() || ready.length);
  return html`<div class=${cx("thq-chat", compact && "is-compact", drag && "is-drop")}
      onDragOver=${onDragOver} onDragLeave=${(e) => e.currentTarget === e.target && setDrag(false)} onDrop=${onDrop}>
    <div class="thq-chat-list" ref=${listRef} aria-live="polite">
      ${loading && html`<p class="thq-muted">${L("Wczytuję rozmowę…", "Loading conversation…")}</p>`}
      ${!loading && messages.length === 0 && html`<div class="thq-chat-empty">
        <p><strong>${agent && agent.emoji} ${who}</strong></p>
        <p class="thq-muted">${agent && agent.kind === "orchestrator"
          ? L("Napisz, co chcesz osiągnąć. TARS rozpisze misję i przydzieli pracę. Zdjęcia i pliki wklejasz Ctrl+V albo przeciągasz tutaj.",
              "Say what you want to achieve. TARS will plan the mission and assign the work. Paste photos and files with Ctrl+V or drop them here.")
          : L("Rozmowa bezpośrednia. Większe zlecenia lepiej dawać przez TARS-a: on pilnuje całości.",
              "Direct conversation. Bigger jobs are better sent through TARS: he keeps track of the whole.")}</p>
      </div>`}
      ${messages.map((m, i) => html`<div key=${i} class=${cx("thq-msg", `is-${m.role}`, m.live && "is-live")}>
        ${m.role === "assistant" && html`<span class="thq-msg-who" aria-hidden="true">${agent && agent.emoji}</span>`}
        <div class="thq-msg-body">
          ${m.role === "assistant" && html`<${ToolChips} tools=${m.tools}/>`}
          ${m.text ? html`<${Markdown} text=${m.text}/>`
            : m.live ? html`<p class="thq-typing" aria-label=${L("pisze", "typing")}><span></span><span></span><span></span></p>` : null}
        </div>
      </div>`)}
    </div>
    ${error && html`<p class="thq-error" role="alert">${error}</p>`}
    <${AttachChips} items=${att.items} onRemove=${att.remove}/>
    <form class="thq-chat-form" onSubmit=${(e) => { e.preventDefault(); submit(); }}>
      <input ref=${fileRef} type="file" multiple hidden onChange=${(e) => { att.add(e.target.files); e.target.value = ""; }}/>
      <button type="button" class="thq-ghost thq-attach-btn" onClick=${() => fileRef.current && fileRef.current.click()} disabled=${!name}
        title=${L("Dodaj zdjęcie albo plik (możesz też wkleić Ctrl+V lub przeciągnąć)", "Add a photo or file (you can also paste with Ctrl+V or drag it here)")}
        aria-label=${L("Dodaj załącznik", "Add attachment")}>📎</button>
      <label class="thq-sr" for=${`thq-input-${name}`}>${L("Wiadomość do", "Message to")}: ${who}</label>
      <textarea id=${`thq-input-${name}`} rows="1" value=${text} placeholder=${L(`Napisz do: ${who}`, `Message ${who}`)}
        onInput=${(e) => setText(e.target.value)} onKeyDown=${onKey} onPaste=${onPaste} disabled=${!name}></textarea>
      <button type="submit" class="thq-send" disabled=${!canSend}>${busy ? "…" : L("Wyślij", "Send")}</button>
      <button type="button" class="thq-ghost" onClick=${reset} disabled=${busy || !messages.length} title=${L("Zacznij nową rozmowę", "Start a new conversation")}>${L("Nowa", "New")}</button>
    </form>
  </div>`;
}

function ChatDock({ agents, target, setTarget, open, setOpen, pending, onPendingDone }) {
  const agent = agents.find((a) => a.name === target) || agents[0];
  return html`<section class=${cx("thq-dock", open && "is-open")} aria-label=${L("Rozmowa", "Conversation")}>
    <header class="thq-dock-head">
      <button type="button" class="thq-dock-toggle" onClick=${() => setOpen(!open)} aria-expanded=${open}>
        ${open ? "▾" : "▴"} ${L("Rozmowa", "Conversation")}
      </button>
      <div class="thq-dock-targets" role="tablist" aria-label=${L("Z kim rozmawiasz", "Who you talk to")}>
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
