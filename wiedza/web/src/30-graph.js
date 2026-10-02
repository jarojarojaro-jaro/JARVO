// Graf skarbca na canvasie: kropka = notatka podpisana nazwą pliku, linia = link, kolor = folder, huby białe i większe.
// Układ sił liczony w małych krokach na klatkę (budżet ~12 ms); powyżej 800 węzłów odpychanie przez drzewo czwórkowe
// (Barnes-Hut, θ = 0,8). Przeciąganie tła = przesuwanie, kółko = przybliżanie, przeciąganie węzła = przestawianie,
// klik = otwarcie notatki. Bez bibliotek.

const GRAPH_THEME = { hub: "#FFFFFF", hubInk: "#17212C", orphan: "#D2392E", conflict: "#F0A020", link: "rgba(140,160,190,0.35)", autoLink: "rgba(140,160,190,0.14)" };

function quadtree(nodes) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const n of nodes) { if (n.x < x0) x0 = n.x; if (n.y < y0) y0 = n.y; if (n.x > x1) x1 = n.x; if (n.y > y1) y1 = n.y; }
  const size = Math.max(x1 - x0, y1 - y0, 1);
  const root = { x: x0, y: y0, s: size, mass: 0, cx: 0, cy: 0, node: null, kids: null };
  const insert = (q, n) => {
    if (q.mass === 0 && !q.kids) { q.node = n; q.mass = 1; q.cx = n.x; q.cy = n.y; return; }
    if (!q.kids) {
      q.kids = [null, null, null, null];
      const old = q.node; q.node = null;
      if (old) place(q, old);
    }
    place(q, n);
    q.cx = (q.cx * q.mass + n.x) / (q.mass + 1); q.cy = (q.cy * q.mass + n.y) / (q.mass + 1); q.mass += 1;
  };
  const place = (q, n) => {
    const h = q.s / 2, ix = n.x >= q.x + h ? 1 : 0, iy = n.y >= q.y + h ? 1 : 0, idx = iy * 2 + ix;
    if (!q.kids[idx]) q.kids[idx] = { x: q.x + ix * h, y: q.y + iy * h, s: h, mass: 0, cx: 0, cy: 0, node: null, kids: null };
    if (q.s < 1e-3) return;   // zdegenerowane: punkty w tym samym miejscu
    insert(q.kids[idx], n);
  };
  for (const n of nodes) insert(root, n);
  return root;
}

function repelFromTree(q, n, k, theta, out) {
  if (!q || q.mass === 0 || q.node === n) return;
  let dx = n.x - q.cx, dy = n.y - q.cy;
  let d2 = dx * dx + dy * dy;
  if (d2 < 1e-4) { dx = (Math.random() - 0.5) * 0.1; dy = (Math.random() - 0.5) * 0.1; d2 = dx * dx + dy * dy + 1e-3; }
  if (!q.kids || (q.s * q.s) / d2 < theta * theta) {
    const f = (k * q.mass) / d2;
    out.fx += dx * f; out.fy += dy * f;
    return;
  }
  for (const c of q.kids) repelFromTree(c, n, k, theta, out);
}

function stepLayout(sim, budgetMs) {
  const { nodes, links } = sim;
  const t0 = performance.now();
  const useTree = nodes.length > 800;
  while (sim.alpha > 0.003 && performance.now() - t0 < budgetMs) {
    const k = 900 * sim.alpha, tree = useTree ? quadtree(nodes) : null;
    for (const n of nodes) {
      n.fx = 0; n.fy = 0;
      if (useTree) { const o = { fx: 0, fy: 0 }; repelFromTree(tree, n, k, 0.8, o); n.fx += o.fx; n.fy += o.fy; }
    }
    if (!useTree) {
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
        if (d2 < 1e-4) { dx = (Math.random() - 0.5) * 0.1; dy = (Math.random() - 0.5) * 0.1; d2 = 1e-3; }
        const f = k / d2;
        a.fx += dx * f; a.fy += dy * f; b.fx -= dx * f; b.fy -= dy * f;
      }
    }
    for (const l of links) {
      const a = l.a, b = l.b, dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
      const rest = a.hub || b.hub ? 70 : 45, strength = (l.auto ? 0.02 : 0.06) * sim.alpha * 8;
      const f = ((d - rest) / d) * strength;
      a.fx += dx * f; a.fy += dy * f; b.fx -= dx * f; b.fy -= dy * f;
    }
    for (const n of nodes) {
      if (n.pinned) continue;
      n.fx -= n.x * 0.01 * sim.alpha * 8; n.fy -= n.y * 0.01 * sim.alpha * 8;       // grawitacja do środka
      n.vx = (n.vx + n.fx) * 0.55; n.vy = (n.vy + n.fy) * 0.55;
      const sp = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
      if (sp > 30) { n.vx *= 30 / sp; n.vy *= 30 / sp; }
      n.x += n.vx; n.y += n.vy;
    }
    sim.alpha *= 0.985;
  }
}

function buildSim(data, filter) {
  const days = filter.days || 0;
  const cutoff = days ? Date.now() - days * 86400000 : 0;
  const allowed = new Set(filter.folders || []);
  const nodes = (data.wezly || []).filter((n) => (!allowed.size || allowed.has(n.folder) || n.hub) &&
    (!cutoff || n.hub || (n.zmieniono && Date.parse(n.zmieniono) >= cutoff)))
    .map((n, i) => {
      const a = (i / Math.max(1, (data.wezly || []).length)) * Math.PI * 2, r = 120 + Math.random() * 120;
      return { ...n, x: Math.cos(a) * r, y: Math.sin(a) * r, vx: 0, vy: 0, fx: 0, fy: 0, r: n.hub ? 9 : 3.5 + Math.log(1 + (n.we || 0)) * 1.6 };
    });
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const links = (data.linki || []).map((l) => ({ a: byId.get(l.z), b: byId.get(l.do), auto: l.auto })).filter((l) => l.a && l.b && l.a !== l.b);
  const deg = new Map();
  for (const l of links) { if (!l.auto) deg.set(l.b.id, (deg.get(l.b.id) || 0) + 1); }
  // sierota = brak linku pisanego ręcznie; węzły skilli robi zasiew (linki z hubów agentów), więc nie są sierotami
  for (const n of nodes) n.orphan = !n.hub && n.typ !== "skill" && !(deg.get(n.id) > 0);
  return { nodes, links, alpha: 1, byId };
}

function Graph({ data, onOpen, filter, selected }) {
  const canvasRef = useRef(null);
  const simRef = useRef(null);
  const viewRef = useRef({ x: 0, y: 0, k: 1, hover: null, drag: null, dragNode: null, moved: false });
  const [, force] = useState(0);
  useEffect(() => { simRef.current = data ? buildSim(data, filter) : null; viewRef.current.hover = null; force((t) => t + 1); }, [data, filter.days, (filter.folders || []).join(",")]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    let raf = 0, alive = true;
    const draw = () => {
      if (!alive) return;
      const sim = simRef.current, v = viewRef.current;
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
      const ctx = canvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      if (sim) {
        stepLayout(sim, 12);
        ctx.save();
        ctx.translate(w / 2 + v.x, h / 2 + v.y);
        ctx.scale(v.k, v.k);
        const hover = v.hover, near = new Set();
        if (hover) for (const l of sim.links) { if (l.a === hover) near.add(l.b); if (l.b === hover) near.add(l.a); }
        ctx.lineWidth = 1 / v.k;
        for (const l of sim.links) {
          const hot = hover && (l.a === hover || l.b === hover);
          ctx.strokeStyle = hot ? folderColor(hover.folder) : (l.auto ? GRAPH_THEME.autoLink : GRAPH_THEME.link);
          ctx.lineWidth = (hot ? 1.8 : 1) / v.k;
          ctx.beginPath(); ctx.moveTo(l.a.x, l.a.y); ctx.lineTo(l.b.x, l.b.y); ctx.stroke();
        }
        for (const n of sim.nodes) {
          const dim = hover && n !== hover && !near.has(n);
          ctx.globalAlpha = dim ? 0.25 : 1;
          ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
          ctx.fillStyle = n.hub ? GRAPH_THEME.hub : folderColor(n.folder);
          ctx.fill();
          if (n.hub) { ctx.strokeStyle = folderColor(n.folder); ctx.lineWidth = 2 / v.k; ctx.stroke(); }
          if (n.orphan || n.status === "sprzeczna" || n.id === selected) {
            ctx.strokeStyle = n.id === selected ? "#FFD54F" : (n.status === "sprzeczna" ? GRAPH_THEME.conflict : GRAPH_THEME.orphan);
            ctx.lineWidth = 2 / v.k; ctx.beginPath(); ctx.arc(n.x, n.y, n.r + 2.5 / v.k, 0, Math.PI * 2); ctx.stroke();
          }
          const label = n.hub || v.k > 1.4 || n === hover || near.has(n) || n.id === selected;
          if (label) {
            ctx.globalAlpha = dim ? 0.25 : 1;
            ctx.font = `${(n.hub ? 12 : 10.5) / v.k}px "Atkinson Hyperlegible", "Segoe UI", system-ui, sans-serif`;
            ctx.fillStyle = "#E6ECF3";
            ctx.textAlign = "center"; ctx.textBaseline = "top";
            const t = n.id.split("/").pop();
            ctx.fillText(t.length > 42 ? t.slice(0, 40) + "…" : t, n.x, n.y + n.r + 2 / v.k);
          }
        }
        ctx.globalAlpha = 1;
        ctx.restore();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { alive = false; cancelAnimationFrame(raf); };
  }, [selected]);

  const toWorld = (e) => {
    const canvas = canvasRef.current, rect = canvas.getBoundingClientRect(), v = viewRef.current;
    return { x: (e.clientX - rect.left - rect.width / 2 - v.x) / v.k, y: (e.clientY - rect.top - rect.height / 2 - v.y) / v.k };
  };
  const nodeAt = (p) => {
    const sim = simRef.current;
    if (!sim) return null;
    let best = null, bd = Infinity;
    for (const n of sim.nodes) { const dx = n.x - p.x, dy = n.y - p.y, d = dx * dx + dy * dy, rr = (n.r + 4 / viewRef.current.k) ** 2; if (d < rr && d < bd) { best = n; bd = d; } }
    return best;
  };
  const onDown = (e) => {
    const v = viewRef.current, p = toWorld(e), n = nodeAt(p);
    v.moved = false;
    if (n) { v.dragNode = n; n.pinned = true; } else v.drag = { x: e.clientX - v.x, y: e.clientY - v.y };
    e.currentTarget.setPointerCapture && e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove = (e) => {
    const v = viewRef.current, p = toWorld(e);
    if (v.dragNode) { v.dragNode.x = p.x; v.dragNode.y = p.y; v.moved = true; if (simRef.current) simRef.current.alpha = Math.max(simRef.current.alpha, 0.05); return; }
    if (v.drag) { v.x = e.clientX - v.drag.x; v.y = e.clientY - v.drag.y; v.moved = true; return; }
    const n = nodeAt(p);
    if (n !== v.hover) { v.hover = n; e.currentTarget.style.cursor = n ? "pointer" : "grab"; e.currentTarget.title = n ? n.tytul : ""; }
  };
  const onUp = (e) => {
    const v = viewRef.current;
    if (v.dragNode) { const n = v.dragNode; n.pinned = false; v.dragNode = null; if (!v.moved) onOpen(n.id); return; }
    v.drag = null;
  };
  const onWheel = (e) => {
    e.preventDefault();
    const v = viewRef.current, canvas = canvasRef.current, rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left - rect.width / 2, my = e.clientY - rect.top - rect.height / 2;
    const k2 = Math.min(6, Math.max(0.2, v.k * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
    v.x = mx - ((mx - v.x) * k2) / v.k; v.y = my - ((my - v.y) * k2) / v.k; v.k = k2;
  };
  const onDblClick = (e) => { const n = nodeAt(toWorld(e)); const v = viewRef.current; if (n) { v.x = -n.x * v.k; v.y = -n.y * v.k; } else { v.x = 0; v.y = 0; v.k = 1; } };
  const n = simRef.current ? simRef.current.nodes.length : 0, l = simRef.current ? simRef.current.links.length : 0;
  return html`<div class="twz-graph">
    <canvas ref=${canvasRef} onPointerDown=${onDown} onPointerMove=${onMove} onPointerUp=${onUp} onPointerLeave=${onUp} onWheel=${onWheel} onDblClick=${onDblClick}
      role="img" aria-label=${L(`Graf skarbca: ${n} notatek, ${l} linków`, `Vault graph: ${n} notes, ${l} links`)}></canvas>
    <div class="twz-graph-meta">${n} ${L("notatek", "notes")} · ${l} ${L("linków", "links")} · ${L("klik: notatka · dwuklik: wyśrodkuj · kółko: zoom", "click: note · double-click: center · wheel: zoom")}</div>
  </div>`;
}
