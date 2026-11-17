// Graf skarbca: otoczka Reacta na wspólnym grafie shared/web/graf.js (ten sam kod rysuje Mózg w aplikacji HQ).
// Kropka = notatka podpisana nazwą pliku, linia = link, kolor = folder, huby białe i większe.

const GRAPH_THEME = { hub: "#FFFFFF", sierota: "#D2392E", sprzeczna: "#F0A020", zaznaczony: "#FFD54F", link: "rgba(140,160,190,0.35)",
  linkAuto: "rgba(140,160,190,0.14)", tekst: "#E6ECF3", font: '"Atkinson Hyperlegible", "Segoe UI", system-ui, sans-serif' };

function Graph({ data, onOpen, filter, selected }) {
  const canvasRef = useRef(null);
  const grafRef = useRef(null);
  const otworzRef = useRef(onOpen);
  otworzRef.current = onOpen;
  const [liczby, setLiczby] = useState({ wezly: 0, linki: 0 });
  useEffect(() => {
    const g = utworzGraf(canvasRef.current, { kolor: (n) => folderColor(n.folder), motyw: () => GRAPH_THEME, otworz: (id) => otworzRef.current(id) });
    grafRef.current = g;
    return () => { g.zniszcz(); grafRef.current = null; };
  }, []);
  useEffect(() => {
    if (!grafRef.current) return;
    // filtr: wybrane foldery i zmiany z ostatnich dni; huby zostają zawsze
    const granica = filter.days ? Date.now() - filter.days * 86400000 : 0, dozw = new Set(filter.folders || []);
    const wezly = data ? (data.wezly || []).filter((n) => n.hub || ((!dozw.size || dozw.has(n.folder)) && (!granica || Date.parse(n.zmieniono) >= granica))) : [];
    setLiczby(grafRef.current.dane(data && { ...data, wezly }));
  }, [data, filter.days, (filter.folders || []).join(",")]);
  useEffect(() => { if (grafRef.current) grafRef.current.zaznacz(selected); }, [selected]);
  const n = liczby.wezly, l = liczby.linki;
  return html`<div class="twz-graph">
    <canvas ref=${canvasRef} role="img" aria-label=${L(`Graf skarbca: ${n} notatek, ${l} linków`, `Vault graph: ${n} notes, ${l} links`)}></canvas>
    <div class="twz-graph-meta">${n} ${L("notatek", "notes")} · ${l} ${L("linków", "links")} · ${L("klik: notatka · kółko: zoom", "click: note · wheel: zoom")}</div>
  </div>`;
}
