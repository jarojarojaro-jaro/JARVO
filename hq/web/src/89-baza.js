// Stara Baza: wieża z pokojami agentów, Centrala i dock czatu (dawny widok /jarvo). Na etapy 3–6 zostaje w pakiecie:
// aplikacja otwiera ją z szuflady (Ustawienia › Stara Baza) na cały ekran, demo (hq/web/demo) pokazuje tylko ją.
// Usuwana w etapie 7 razem z 20-art.js, 30-building.js i 60-hud.js (docs/HQ.md „Aplikacja”).

const useHostI18n = (SDK && SDK.useI18n) || (() => null);

// naStart="decyzje": otwarta z „Czeka na Ciebie” w aplikacji, od razu na decyzjach w Centrali
function StaraBaza({ wlasnyNaglowek = false, naStart = null }) {
  // język dashboardu: zmiana w przełączniku przerysowuje całe HQ
  const i18n = useHostI18n();
  HQ_LANG = (i18n && i18n.locale) || null;
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
  const [editing, setEditing] = useState(null);   // ścieżka filmu otwartego w edytorze
  const openEditor = useCallback((f) => { setFile(null); setEditing(f.path); }, []);
  const [animating, setAnimating] = useState(null);   // ścieżka animacji HTML otwartej w podglądzie na żywo
  const openAnim = useCallback((f) => { setFile(null); setAnimating(f.path); }, []);
  const now = Date.now() / 1000;

  useEffect(() => { (api.fleet ? api.fleet() : Promise.resolve({ agents: [] })).then((f) => setFleet(f.agents || [])).catch(() => {}); }, []);

  const agents = ((state && state.agents) || fleet.map((a) => ({ ...a, status: "idle", counts: {} }))).map(localAgent);
  const fleetL = fleet.map(localAgent);
  const boss = agents.find((a) => a.kind === "orchestrator") || agents[0];
  const chatTarget = target || (boss && boss.name);
  // w aplikacji (wersja ≥ 2) pasek Hermesa leży pod jej warstwą: Stara Baza rysuje wtedy własny nagłówek (Hud)
  const naglowekHermesa = usePageHeader();
  const header = wlasnyNaglowek ? null : naglowekHermesa;
  const openDecisions = () => { setSelected(null); setFocus("decisions"); setTimeout(() => setFocus(null), 600); };
  const nDecisions = ((state && state.decisions) || []).length;
  useEffect(() => { if (naStart === "decyzje" && state) openDecisions(); }, [naStart, !!state]);

  // tytuł, liczniki i przycisk decyzji w górnym pasku dashboardu (zamiast osobnego nagłówka HQ)
  useEffect(() => {
    if (!header) return;
    header.setTitle("Jarvo HQ");
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
      <p>${error ? L(`Nie mogę połączyć się z flotą: ${error}`, `Cannot reach the fleet: ${error}`) : L("Otwieram kwaterę…", "Opening headquarters…")}</p>
    </div></div>`;
  }

  return html`<${FileCtx.Provider} value=${setFile}><${EditCtx.Provider} value=${openEditor}><${AnimCtx.Provider} value=${openAnim}><div class=${cx("thq-root", selected && "has-selection")}>
    ${!header && html`<${Hud} state=${state} error=${error} now=${now} onDecisions=${openDecisions}/>`}
    <main class="thq-main">
      <div class="thq-left">
        <div class="thq-scene">
          <${Building} agents=${agents} board=${(state && state.board) || {}} selected=${selected} onSelect=${select} online=${!error}/>
          <p class="thq-hint">${L("Kliknij pokój, żeby zobaczyć, nad czym pracuje agent. Na telefonie przesuń wieżę palcem.", "Click a room to see what the agent is working on. On a phone, swipe the tower.")}</p>
        </div>
        <${ChatDock} agents=${agents} target=${chatTarget} setTarget=${setTarget} open=${dockOpen} setOpen=${setDockOpen}
          pending=${pending} onPendingDone=${() => setPending(null)}/>
      </div>
      ${selected
        ? html`<${AgentPanel} key=${selected} name=${selected} agents=${agents} fleet=${fleetL} tab=${tab} setTab=${setTab}
            onClose=${() => setSelected(null)} onOpenTask=${setTaskId} onOpenFile=${setFile} pending=${pending} onPendingDone=${() => setPending(null)}/>`
        : html`<${Center} state=${state} agents=${agents} onAnswer=${answer} onOpenTask=${setTaskId} onOpenFile=${setFile} focus=${focus}/>`}
    </main>
    ${taskId && html`<${TaskModal} taskId=${taskId} agents=${agents} onClose=${() => setTaskId(null)} onOpenFile=${setFile}/>`}
    ${file && html`<${FilePreview} file=${file} onClose=${() => setFile(null)}/>`}
    ${editing && html`<${VideoEditor} key=${editing} path=${editing} onClose=${() => setEditing(null)}/>`}
    ${animating && html`<${AnimStudio} key=${animating} path=${animating} onClose=${() => setAnimating(null)}/>`}
  </div></${AnimCtx.Provider}></${EditCtx.Provider}></${FileCtx.Provider}>`;
}
