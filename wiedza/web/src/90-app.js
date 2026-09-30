// Aplikacja zakładki „Wiedza”: lewy panel (szukaj, karty: graf, foldery, orzeczenia, skrzynka, lint, dziennik),
// środek (graf albo widok karty), prawy panel z notatką. Tytuł i statystyki w górnym pasku dashboardu, gdy jest.

const useHostI18n = (SDK && SDK.useI18n) || (() => null);
const useHeader = (SDK && SDK.usePageHeader) || (() => null);
const VIEWS = ["graph", "tree", "rulings", "inbox", "lint", "log"];
const VIEW_TEXT = bilingual({ graph: ["Graf", "Graph"], tree: ["Foldery", "Folders"], rulings: ["Orzeczenia", "Rulings"], inbox: ["Skrzynka", "Inbox"], lint: ["Lint", "Lint"], log: ["Dziennik", "Log"] });

function GraphFilters({ filter, setFilter, folders }) {
  const toggle = (f) => setFilter({ ...filter, folders: filter.folders.includes(f) ? filter.folders.filter((x) => x !== f) : [...filter.folders, f] });
  return html`<div class="twz-filters">
    <div class="twz-legend">${folders.map((f) => html`<button key=${f} type="button" class=${cx("twz-legend-item", filter.folders.length && !filter.folders.includes(f) && "is-off")} onClick=${() => toggle(f)}>
      <i class="twz-dot" style=${{ background: folderColor(f) }}></i>${folderName(f)}</button>`)}
      ${filter.folders.length > 0 && html`<button type="button" class="twz-legend-item is-reset" onClick=${() => setFilter({ ...filter, folders: [] })}>${L("wszystkie", "all")}</button>`}
    </div>
    <label class="twz-days">${L("Zmiany z", "Changed within")}
      <select value=${filter.days} onChange=${(e) => setFilter({ ...filter, days: Number(e.target.value) })}>
        <option value="0">${L("całość", "everything")}</option><option value="7">${L("7 dni", "7 days")}</option><option value="30">${L("30 dni", "30 days")}</option><option value="90">${L("90 dni", "90 days")}</option>
      </select></label>
    <span class="twz-legend-note"><i class="twz-dot is-hub"></i>${L("hub", "hub")} · <i class="twz-ring is-orphan"></i>${L("sierota", "orphan")} · <i class="twz-ring is-conflict"></i>${L("sprzeczna", "contradictory")}</span>
  </div>`;
}

function App() {
  const i18n = useHostI18n();
  WZ_LANG = (i18n && i18n.locale) || null;
  const [ov, ovErr, reloadOv] = usePoll(() => api.overview(), 20000, []);
  const [tree, , reloadTree] = usePoll(() => api.tree(), 0, []);
  const [graph, , reloadGraph] = usePoll(() => api.graph(), 0, []);
  const [view, setView] = useState("graph");
  const [note, setNote] = useState(null);
  const [filter, setFilter] = useState({ folders: [], days: 0 });
  const changed = useCallback(() => { reloadOv(); reloadTree(); reloadGraph(); }, []);
  const open = useCallback((path) => setNote(path), []);
  const header = useHeader();
  useEffect(() => {
    if (!header) return;
    header.setTitle(L("Wiedza", "Knowledge"));
    header.setAfterTitle && header.setAfterTitle(html`<${Stats} ov=${ov}/>`);
  }, [header, ov]);
  const folders = useMemo(() => Array.from(new Set(((graph && graph.wezly) || []).map((n) => n.folder))).sort(), [graph]);
  return html`<div class=${cx("twz-root", note && "has-note")}>
    ${!header && html`<div class="twz-headbar"><h1>${L("Wiedza", "Knowledge")}</h1><${Stats} ov=${ov}/></div>`}
    ${ovErr && html`<p class="twz-error">${ovErr}</p>`}
    <div class="twz-main">
      <nav class="twz-side" aria-label=${L("Skarbiec", "Vault")}>
        <${Search} onOpen=${open}/>
        <div class="twz-tabs" role="tablist">${VIEWS.map((v) => html`<button key=${v} type="button" role="tab" aria-selected=${view === v} class=${cx("twz-tab", view === v && "is-active")} onClick=${() => setView(v)}>${VIEW_TEXT[v]}${v === "inbox" && ov && ov.szkice > 0 && html`<span class="twz-count">${ov.szkice}</span>`}${v === "lint" && ov && ov.lint && ov.lint.bledy > 0 && html`<span class="twz-count is-bad">${ov.lint.bledy}</span>`}</button>`)}</div>
        <div class="twz-side-body">
          ${view === "tree" && html`<${Tree} tree=${tree} onOpen=${open} selected=${note}/>`}
          ${view === "graph" && html`<${GraphFilters} filter=${filter} setFilter=${setFilter} folders=${folders}/>`}
          ${view === "rulings" && html`<${Rulings} onOpen=${open} onChanged=${changed}/>`}
          ${view === "inbox" && html`<${Inbox} onChanged=${changed}/>`}
          ${view === "lint" && html`<${LintView} onOpen=${open}/>`}
          ${view === "log" && html`<${LogView}/>`}
        </div>
      </nav>
      <section class="twz-center">
        ${graph ? html`<${Graph} data=${graph} onOpen=${open} filter=${filter} selected=${note}/>` : html`<p class="twz-muted twz-center-msg">${L("Wczytuję graf…", "Loading the graph…")}</p>`}
      </section>
      ${note && html`<${NoteView} key=${note} path=${note} onOpen=${open} onClose=${() => setNote(null)} onChanged=${changed}/>`}
    </div>
  </div>`;
}

if (window.__HERMES_PLUGINS__ && window.__HERMES_PLUGINS__.register) {
  window.__HERMES_PLUGINS__.register(PLUGIN, App);
}
