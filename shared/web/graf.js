// Wspólny graf wiedzy (docs/HQ.md „Mózg”, docs/WIEDZA.md): ten sam plik dołącza build do zakładki Wiedza
// (scripts/build.py) i do pakietu „mozg” aplikacji HQ (scripts/hqbuild.py). Canvas, własny układ sił, bez bibliotek
// i bez Reacta: utworzGraf(canvas, opcje) zwraca sterownik, a otoczka widoku (wiedza/web/src/30-graph.js,
// hq/web/src/63-mozg.js) podaje dane i kolory.
//
// - Dane: {wezly: [{id, tytul, krotki, folder, hub, we, typ, status, zmieniono}], linki: [{z, do, auto}]}.
// - Układ: kroki w budżecie ~10 ms na klatkę; odpychanie przez drzewo czwórkowe (Barnes-Hut, θ = 0,8), więc 800+
//   węzłów liczy się płynnie. Rysowanie staje, gdy układ się uspokoił i nic się nie rusza (bateria telefonu).
// - Linki jedną ścieżką na styl, węzły poza ekranem pomijane, etykiety tylko po przybliżeniu, przy hubie
//   i zaznaczonym węźle. Widok sam obejmuje cały graf, dopóki ktoś go nie przesunie albo przybliży.
// - Mysz: przeciąganie = przesuwanie, kółko = przybliżanie, klik w węzeł = otwarcie,
//   wybór z listy = wyśrodkowanie (wysrodkuj). Dotyk: dwa palce przybliżają i przesuwają.
// - opcje: {kolor(węzeł) → css, motyw() → {link, linkAuto, hub, sierota, sprzeczna, zaznaczony, tekst, font} (wszystkie
//   pola), otworz(id)}.
// Testy: tests/test_mozg_zrodla.py (node, 1200 węzłów).

function grafDrzewo(nodes) {
  let x0 = Infinity, y0 = Infinity, s = 1;
  for (const n of nodes) { x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y); }
  for (const n of nodes) s = Math.max(s, n.x - x0, n.y - y0);
  const kom = (x, y, s) => ({ x, y, s, m: 0, cx: 0, cy: 0, n: null, d: null });
  const wloz = (q, n) => {
    if (!q.m && !q.d) { q.n = n; q.m = 1; q.cx = n.x; q.cy = n.y; return; }
    if (!q.d) { q.d = []; const st = q.n; q.n = null; if (st) dziecko(q, st); }
    dziecko(q, n);
    q.cx = (q.cx * q.m + n.x) / (q.m + 1); q.cy = (q.cy * q.m + n.y) / (q.m + 1); q.m++;
  };
  const dziecko = (q, n) => {
    if (q.s < 1e-3) return;   // zdegenerowane: punkty w tym samym miejscu
    const h = q.s / 2, ix = n.x >= q.x + h ? 1 : 0, iy = n.y >= q.y + h ? 1 : 0, i = iy * 2 + ix;
    wloz(q.d[i] || (q.d[i] = kom(q.x + ix * h, q.y + iy * h, h)), n);
  };
  const root = kom(x0, y0, s);
  for (const n of nodes) wloz(root, n);
  return root;
}

function grafOdpychaj(q, n, k) {
  if (!q || !q.m || q.n === n) return;
  const dx = n.x - q.cx || 0.01, dy = n.y - q.cy, d2 = dx * dx + dy * dy + 0.01;
  if (!q.d || (q.s * q.s) / d2 < 0.64) { const f = (k * q.m) / d2; n.fx += dx * f; n.fy += dy * f; return; }
  for (const c of q.d) grafOdpychaj(c, n, k);
}

// jeden krok układu sił; false = uspokojony
function grafKrok(sim) {
  if (sim.alpha <= 0.003) return false;
  const a = sim.alpha, k = 900 * a, drzewo = grafDrzewo(sim.nodes);
  for (const n of sim.nodes) { n.fx = -n.x * 0.08 * a; n.fy = -n.y * 0.08 * a; grafOdpychaj(drzewo, n, k); }
  for (const { a: p, b: q, auto } of sim.links) {
    const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 1, f = ((d - (p.hub || q.hub ? 70 : 45)) / d) * (auto ? 0.16 : 0.48) * a;
    p.fx += dx * f; p.fy += dy * f; q.fx -= dx * f; q.fy -= dy * f;
  }
  for (const n of sim.nodes) {
    n.vx = (n.vx + n.fx) * 0.55; n.vy = (n.vy + n.fy) * 0.55;
    const sp = Math.hypot(n.vx, n.vy) / 30;
    if (sp > 1) { n.vx /= sp; n.vy /= sp; }
    n.x += n.vx; n.y += n.vy;
  }
  sim.alpha *= 0.985;
  return true;
}

// węzły w kole, promień od liczby linków wchodzących (filtr folderów i dat robi otoczka widoku)
function grafSymulacja(dane) {
  const wsz = dane.wezly || [];
  const nodes = wsz.map((n, i) => {
    const a = (i / wsz.length) * 6.283, r = 120 + Math.random() * 120;
    return { ...n, x: Math.cos(a) * r, y: Math.sin(a) * r, vx: 0, vy: 0, r: n.hub ? 9 : 3.5 + Math.log(1 + (n.we || 0)) * 1.6 };
  });
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const links = (dane.linki || []).map((l) => ({ a: byId.get(l.z), b: byId.get(l.do), auto: !!l.auto })).filter((l) => l.a && l.b && l.a !== l.b);
  const reczne = new Set(links.filter((l) => !l.auto).map((l) => l.b));
  // sierota = brak linku pisanego ręcznie; węzły skilli robi zasiew (linki z hubów agentów), więc nie są sierotami
  for (const n of nodes) n.orphan = !n.hub && n.typ !== "skill" && !reczne.has(n);
  return { nodes, links, alpha: 1, byId };
}

function utworzGraf(canvas, o) {
  const v = { x: 0, y: 0, k: 1, fit: 1 }, palce = new Map();   // fit: widok sam obejmuje cały graf, dopóki ktoś go nie ruszy
  let sim = null, raf = 0, ciag = null, wezel = null, ruch = false, szczyp = null, zazn = null;

  function rysuj() {
    raf = 0;
    const t0 = performance.now(), dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight, W = Math.round(w * dpr), H = Math.round(h * dpr);
    let rusza = false;
    while (sim && performance.now() - t0 < 10 && (rusza = grafKrok(sim)));
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    const c = canvas.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    if (sim && v.fit && sim.nodes.length) {
      let a = Infinity, b = Infinity, p = -Infinity, q = -Infinity;
      for (const n of sim.nodes) { a = Math.min(a, n.x); b = Math.min(b, n.y); p = Math.max(p, n.x); q = Math.max(q, n.y); }
      v.k = Math.min(2, 0.9 * Math.min(w / (p - a + 40), h / (q - b + 40))); v.x = -v.k * (a + p) / 2; v.y = -v.k * (b + q) / 2;
    }
    if (sim) {
      const k = v.k, m = o.motyw(), sciezka = (fn, styl, gr) => {
        c.beginPath();
        for (const l of sim.links) if (fn(l)) { c.moveTo(l.a.x, l.a.y); c.lineTo(l.b.x, l.b.y); }
        c.strokeStyle = styl; c.lineWidth = gr / k; c.stroke();
      };
      c.translate(w / 2 + v.x, h / 2 + v.y);
      c.scale(k, k);
      sciezka((l) => l.auto, m.linkAuto, 1);
      sciezka((l) => !l.auto, m.link, 1);
      // widoczny wycinek świata: węzłów poza ekranem nie rysujemy
      const x0 = (-w / 2 - v.x) / k - 20, x1 = (w / 2 - v.x) / k + 20, y0 = (-h / 2 - v.y) / k - 20, y1 = (h / 2 - v.y) / k + 20, napisy = [];
      for (const n of sim.nodes) {
        if (n.x < x0 || n.x > x1 || n.y < y0 || n.y > y1) continue;
        const z = n.id === zazn;
        c.beginPath(); c.arc(n.x, n.y, n.r, 0, 7);
        c.fillStyle = n.hub ? m.hub : o.kolor(n);
        c.fill();
        if (n.hub) { c.strokeStyle = o.kolor(n); c.lineWidth = 2 / k; c.stroke(); }
        if (n.orphan || n.status === "sprzeczna" || z) {
          c.strokeStyle = z ? m.zaznaczony : n.status === "sprzeczna" ? m.sprzeczna : m.sierota;
          c.lineWidth = 2 / k; c.beginPath(); c.arc(n.x, n.y, n.r + 2.5 / k, 0, 7); c.stroke();
        }
        if (n.hub || k > 1.4 || z) napisy.push(n);
      }
      c.fillStyle = m.tekst; c.textAlign = "center"; c.textBaseline = "top";
      for (const n of napisy) {
        const t = n.krotki || n.id.split("/").pop();
        c.font = `${(n.hub ? 12 : 10.5) / k}px ${m.font}`;
        c.fillText(t.length > 42 ? t.slice(0, 40) + "…" : t, n.x, n.y + n.r + 2 / k);
      }
    }
    if (rusza || ciag || szczyp) odswiez();
  }
  const odswiez = () => { raf = raf || requestAnimationFrame(rysuj); };

  const ekran = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left - r.width / 2, e.clientY - r.top - r.height / 2]; };
  const swiat = (e) => { const [x, y] = ekran(e); return { x: (x - v.x) / v.k, y: (y - v.y) / v.k }; };
  function wezelW(p) {
    let best = null, bd = Infinity;
    for (const n of sim ? sim.nodes : []) { const d = (n.x - p.x) ** 2 + (n.y - p.y) ** 2; if (d < (n.r + 6 / v.k) ** 2 && d < bd) { best = n; bd = d; } }
    return best;
  }
  // przybliżenie z punktem (mx, my) ekranu w miejscu
  function przybliz(mx, my, k2, z = v) {
    k2 = Math.min(6, Math.max(0.05, k2)); v.fit = 0;
    v.x = mx - ((mx - z.x) * k2) / z.k; v.y = my - ((my - z.y) * k2) / z.k; v.k = k2;
    odswiez();
  }
  const dwa = () => { const [a, b] = [...palce.values()]; return { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, e: { clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 } }; };

  const zd = {
    pointerdown(e) {
      palce.set(e.pointerId, { x: e.clientX, y: e.clientY });
      try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* atrapa albo puszczony */ }
      if (palce.size > 1) { wezel = ciag = null; szczyp = { ...dwa(), v: { ...v } }; return; }
      wezel = wezelW(swiat(e)); ruch = false;
      v.fit = 0; ciag = { x: e.clientX - v.x, y: e.clientY - v.y, sx: e.clientX, sy: e.clientY };
    },
    pointermove(e) {
      if (palce.has(e.pointerId)) palce.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (szczyp) {
        if (palce.size < 2) return;
        const p = dwa(), [mx, my] = ekran(szczyp.e), [px, py] = ekran(p.e);
        przybliz(mx, my, szczyp.v.k * (p.d / szczyp.d), szczyp.v);
        v.x += px - mx; v.y += py - my;
        return;
      }
      if (ciag) { ruch = ruch || Math.abs(e.clientX - ciag.sx) + Math.abs(e.clientY - ciag.sy) > 3; v.x = e.clientX - ciag.x; v.y = e.clientY - ciag.y; return odswiez(); }
    },
    pointerup(e) {
      palce.delete(e.pointerId);
      if (szczyp) { if (!palce.size) szczyp = null; return; }
      if (wezel && !ruch) o.otworz(wezel.id);
      wezel = ciag = null;
    },
    wheel(e) { e.preventDefault(); const [x, y] = ekran(e); przybliz(x, y, v.k * (e.deltaY < 0 ? 1.15 : 1 / 1.15)); },
  };
  zd.pointercancel = zd.pointerup;
  for (const n in zd) canvas.addEventListener(n, zd[n], { passive: n !== "wheel" });
  const ro = window.ResizeObserver ? new ResizeObserver(odswiez) : null;
  if (ro) ro.observe(canvas);

  function wysrodkuj(id) {
    const n = sim && sim.byId.get(id);
    if (n) { v.fit = 0; v.k = Math.max(v.k, 1.6); v.x = -n.x * v.k; v.y = -n.y * v.k; odswiez(); }
  }
  return {
    dane(d) { sim = d ? grafSymulacja(d) : null; v.fit = 1; odswiez(); return { wezly: sim ? sim.nodes.length : 0, linki: sim ? sim.links.length : 0 }; },
    zaznacz(id) { zazn = id; odswiez(); },
    wysrodkuj,
    stan: () => [v, sim],   // testy
    zniszcz() { cancelAnimationFrame(raf); raf = 1; if (ro) ro.disconnect(); for (const n in zd) canvas.removeEventListener(n, zd[n]); },
  };
}
