// Aplikacja TARS HQ: budynek + panel (agent albo Centrala) + dock czatu.

function App() {
  const [state, error] = usePoll(() => api.state(), 3000, []);
  const [fleet, setFleet] = useState([]);
  const [selected, setSelected] = useState(null);
  const [tab, setTab] = useState("now");
  const [target, setTarget] = useState(null);
  // czat rozwinięty na start tylko na wysokim ekranie: wieża ma się mieścić bez przewijania
  const [dockOpen, setDockOpen] = useState(() => (typeof window === "undefined" ? true : window.innerWidth > 720 && window.innerHeight >= 1000));
  const [pending, setPending] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [file, setFile] = useState(null);   // okna renderujemy tu, nad całym HQ (panel i dock mają własne warstwy)
  const [focus, setFocus] = useState(null);
  const now = Date.now() / 1000;

  useEffect(() => { (api.fleet ? api.fleet() : Promise.resolve({ agents: [] })).then((f) => setFleet(f.agents || [])).catch(() => {}); }, []);

  const agents = (state && state.agents) || fleet.map((a) => ({ ...a, status: "idle", counts: {} }));
  const boss = agents.find((a) => a.kind === "orchestrator") || agents[0];
  const chatTarget = target || (boss && boss.name);
  const header = usePageHeader();
  const openDecisions = () => { setSelected(null); setFocus("decisions"); setTimeout(() => setFocus(null), 600); };
  const nDecisions = ((state && state.decisions) || []).length;

  // tytuł, liczniki i przycisk decyzji w górnym pasku dashboardu (zamiast osobnego nagłówka HQ)
  useEffect(() => {
    if (!header) return;
    header.setTitle("TARS HQ");
    header.setAfterTitle(html`<${HeadStats} state=${state} error=${error}/>`);
    header.setEnd(html`<${HeadDecisions} count=${nDecisions} onClick=${openDecisions}/>`);
  }, [header, state, error, nDecisions]);
  useEffect(() => () => { if (header) { header.setTitle(null); header.setAfterTitle(null); header.setEnd(null); } }, [header]);

  const select = (name) => {
    setSelected((cur) => (cur === name ? null : name));
    setTab("now");
  };

  const answer = (item, text) => {
    if (!boss) return;
    const who = agents.find((a) => a.name === item.assignee);
    const msg = `Decyzja do karty ${item.task_id} („${item.title}”, ${who ? who.short || who.name : item.assignee}): ${text}`;
    setTarget(boss.name);
    setDockOpen(true);
    setPending({ agent: boss.name, text: msg });
  };

  if (!state && !fleet.length) {
    return html`<div class="thq-root"><div class="thq-loading">
      <span class="thq-brand-mark" aria-hidden="true"><span></span><span></span><span></span><span></span></span>
      <p>${error ? `Nie mogę połączyć się z flotą: ${error}` : "Otwieram kwaterę…"}</p>
    </div></div>`;
  }

  return html`<div class=${cx("thq-root", selected && "has-selection")}>
    ${!header && html`<${Hud} state=${state} error=${error} now=${now} onDecisions=${openDecisions}/>`}
    <main class="thq-main">
      <div class="thq-left">
        <div class="thq-scene">
          <${Building} agents=${agents} board=${(state && state.board) || {}} selected=${selected} onSelect=${select} online=${!error}/>
          <p class="thq-hint">Kliknij pokój, żeby zobaczyć, nad czym pracuje agent. Na telefonie przesuń wieżę palcem.</p>
        </div>
        <${ChatDock} agents=${agents} target=${chatTarget} setTarget=${setTarget} open=${dockOpen} setOpen=${setDockOpen}
          pending=${pending} onPendingDone=${() => setPending(null)}/>
      </div>
      ${selected
        ? html`<${AgentPanel} key=${selected} name=${selected} agents=${agents} fleet=${fleet} tab=${tab} setTab=${setTab}
            onClose=${() => setSelected(null)} onOpenTask=${setTaskId} onOpenFile=${setFile} pending=${pending} onPendingDone=${() => setPending(null)}/>`
        : html`<${Center} state=${state} agents=${agents} onAnswer=${answer} onOpenTask=${setTaskId} onOpenFile=${setFile} focus=${focus}/>`}
    </main>
    ${taskId && html`<${TaskModal} taskId=${taskId} agents=${agents} onClose=${() => setTaskId(null)} onOpenFile=${setFile}/>`}
    ${file && html`<${FilePreview} file=${file} onClose=${() => setFile(null)}/>`}
  </div>`;
}

if (window.__HERMES_PLUGINS__ && window.__HERMES_PLUGINS__.register) {
  window.__HERMES_PLUGINS__.register(PLUGIN, App);
}
