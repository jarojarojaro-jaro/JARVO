// Wspólny graf wiedzy (docs/HQ.md „Mózg”, docs/WIEDZA.md): ten sam plik dołącza build do zakładki Wiedza
// (scripts/build.py) i do pakietu „mozg” aplikacji HQ (scripts/hqbuild.py). Canvas, własny układ sił, bez bibliotek
// i bez Reacta: utworzGraf(canvas, opcje) zwraca sterownik, a otoczka widoku (wiedza/web/src/30-graph.js,
// hq/web/src/63-mozg.js) podaje dane i kolory.
//
// - Dane: {wezly: [{id, tytul, krotki, folder, hub, we, typ, status, zmieniono}], linki: [{z, do, auto}]}.
//   Pola dla skupisk (Mózg): `grupa` (węzły jednej grupy odpychają się tylko między sobą i ciągną do wspólnej
//   kotwicy, kotwice leżą na okręgu na miarę skupisk; linki między grupami bez sprężyny, rysowane jednym mostem na
//   parę skupisk), `stale` (węzeł przybity do kotwicy: etykieta skupiska), `r` (własny promień), `etykieta` (napis
//   zamiast `krotki`), `napis` (etykieta zawsze widoczna).
// - Układ: kroki w budżecie ~10 ms na klatkę; odpychanie przez drzewo czwórkowe (Barnes-Hut, θ = 0,8), więc 800+
//   węzłów liczy się płynnie. Rysowanie staje, gdy układ się uspokoił i nic się nie rusza (bateria telefonu),
//   a ukryte płótno (0 × 0) nie liczy nic, dopóki znów się nie pokaże.
// - Linki jedną ścieżką na styl, węzły poza ekranem pomijane, etykiety tylko po przybliżeniu, przy hubie (bez
//   skupisk), skupisku, węźle wskazanym myszą i zaznaczonym (jego linki w kolorze zaznaczenia). Widok sam obejmuje
//   cały graf (po wysrodkuj: trzyma węzeł w środku, calosc() wraca do całości), dopóki ktoś go nie ruszy.
// - Mysz: przeciąganie = przesuwanie, kółko = przybliżanie, klik w węzeł = otwarcie,
//   wybór z listy = wyśrodkowanie (wysrodkuj). Dotyk: dwa palce przybliżają i przesuwają.
// - opcje: {kolor(węzeł) → css, motyw() → {link, linkAuto, hub, sierota, sprzeczna, zaznaczony, tekst, font, tlo?}
//   (pusta `sierota`: bez obwódki sierot; tlo: obwódka napisów), otworz(id)}.
// Testy: tests/test_mozg_zrodla.py (node, 1200 węzłów, skupiska).

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

// jeden krok układu sił; false = uspokojony. Odpychanie i grawitacja w obrębie skupiska (bez grup jedno, w środku),
// więc skupiska się nie mieszają, a co 4 kroki kotwice rozstawiają się na miarę obecnych promieni skupisk.
function grafKrok(sim) {
  if (sim.alpha <= 0.003) return false;
  const a = sim.alpha, k = 900 * a, wiele = sim.grupy.length > 1, G = (wiele ? 0.3 : 0.08) * a;
  if (wiele && sim.krok++ % 4 === 0) grafRozstaw(sim.grupy);
  for (const g of sim.grupy) {
    const drzewo = grafDrzewo(g.nodes);
    for (const n of g.nodes) { n.fx = (g.x - n.x) * G; n.fy = (g.y - n.y) * G; grafOdpychaj(drzewo, n, k); }
  }
  for (const { a: p, b: q, auto, obca } of sim.links) {
    if (obca) continue;   // link między skupiskami tylko rysujemy: sprężyna ciągnęłaby skupiska do siebie
    const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 1, f = ((d - (p.hub || q.hub ? 70 : 45)) / d) * (auto ? 0.16 : 0.48) * a;
    p.fx += dx * f; p.fy += dy * f; q.fx -= dx * f; q.fy -= dy * f;
  }
  for (const n of sim.nodes) {
    if (n.stale) { n.x = n.g.x; n.y = n.g.y; continue; }
    n.vx = (n.vx + n.fx) * 0.55; n.vy = (n.vy + n.fy) * 0.55;
    const sp = Math.hypot(n.vx, n.vy) / 30;
    if (sp > 1) { n.vx /= sp; n.vy /= sp; }
    n.x += n.vx; n.y += n.vy;
  }
  sim.alpha *= 0.985;
  return true;
}

// kotwice skupisk na okręgu: łuk na miarę promienia skupiska, promień okręgu taki, że sąsiednie skupiska się nie
// stykają (cięciwa między środkami ≥ suma promieni). Skupisko jedzie razem z kotwicą (bez zostawania w tyle).
function grafRozstaw(grupy) {
  for (const g of grupy) {
    let r = 0;
    for (const n of g.nodes) if (!n.stale) r = Math.max(r, Math.hypot(n.x - g.x, n.y - g.y) + n.r);
    g.r = (g.r ? Math.max(r, 60) : 30 + 15 * Math.sqrt(g.ile)) + 26;   // pierwsze rozstawienie: z liczności; 60: miejsce na napis
  }
  const suma = grupy.reduce((s, g) => s + g.r, 0), kat = grupy.map((g) => (2 * Math.PI * g.r) / suma);
  let R = 0, t = -Math.PI / 2;
  grupy.forEach((g, i) => { const j = (i + 1) % grupy.length; R = Math.max(R, (g.r + grupy[j].r) / (2 * Math.sin((kat[i] + kat[j]) / 4))); });
  grupy.forEach((g, i) => {
    t += kat[i] / 2;
    const x = Math.cos(t) * R, y = Math.sin(t) * R;
    for (const n of g.nodes) { n.x += x - g.x; n.y += y - g.y; }
    g.x = x; g.y = y; t += kat[i] / 2;
  });
}

// węzły w kole wokół kotwic, promień od liczby linków wchodzących (filtr folderów i dat robi otoczka widoku)
function grafSymulacja(dane) {
  const wsz = dane.wezly || [], grupy = new Map();
  for (const n of wsz) { const g = grupy.get(n.grupa) || { nodes: [], x: 0, y: 0, r: 0, ile: 0, i: grupy.size }; g.ile++; grupy.set(n.grupa, g); }
  const wiele = grupy.size > 1;
  if (wiele) grafRozstaw([...grupy.values()]);
  const nodes = wsz.map((n, i) => {
    const g = grupy.get(n.grupa), a = (i / wsz.length) * 6.283, r = n.stale ? 0 : wiele ? 10 + Math.random() * 30 : 120 + Math.random() * 120;
    const w = { ...n, g, x: g.x + Math.cos(a) * r, y: g.y + Math.sin(a) * r, vx: 0, vy: 0, r: n.r || (n.hub ? 9 : 3.5 + Math.log(1 + (n.we || 0)) * 1.6) };
    g.nodes.push(w);
    return w;
  });
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const links = (dane.linki || []).map((l) => ({ a: byId.get(l.z), b: byId.get(l.do), auto: !!l.auto })).filter((l) => l.a && l.b && l.a !== l.b);
  // linki między skupiskami: jeden most na parę skupisk (grubość od liczby linków), pojedyncze tylko przy zaznaczonym
  const mosty = new Map();
  for (const l of links) {
    l.obca = l.a.g !== l.b.g;
    if (!l.obca) continue;
    const [p, q] = l.a.g.i < l.b.g.i ? [l.a.g, l.b.g] : [l.b.g, l.a.g];
    const m = mosty.get(p) || new Map();
    mosty.set(p, m.set(q, (m.get(q) || 0) + 1));
  }
  const reczne = new Set(links.filter((l) => !l.auto).map((l) => l.b));
  // sierota = brak linku pisanego ręcznie; węzły skilli robi zasiew (linki z hubów agentów), więc nie są sierotami
  for (const n of nodes) n.orphan = !n.hub && !n.stale && n.typ !== "skill" && !reczne.has(n);
  return { nodes, links, alpha: 1, byId, grupy: [...grupy.values()], krok: 0, mosty: [...mosty].flatMap(([p, m]) => [...m].map(([q, c]) => ({ p, q, c }))) };
}

function utworzGraf(canvas, o) {
  const v = { x: 0, y: 0, k: 1, fit: 1 }, palce = new Map();   // fit: 1 = cały graf, id = ten węzeł w środku, 0 = ręcznie
  let sim = null, raf = 0, ciag = null, wezel = null, ruch = false, szczyp = null, zazn = null, nad = null;

  function rysuj() {
    raf = 0;
    const t0 = performance.now(), dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight, W = Math.round(w * dpr), H = Math.round(h * dpr);
    if (!w || !h) return;   // ukryte płótno: nic nie liczymy, ResizeObserver wznowi po pokazaniu
    let rusza = false;
    while (sim && performance.now() - t0 < 10 && (rusza = grafKrok(sim)));
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    const c = canvas.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const sl = typeof v.fit === "string" && sim && sim.byId.get(v.fit);   // wysrodkuj: węzeł w środku, póki układ się rusza
    if (sl) { v.x = -sl.x * v.k; v.y = -sl.y * v.k; }
    if (sim && v.fit === 1 && sim.nodes.length) {
      let a = Infinity, b = Infinity, p = -Infinity, q = -Infinity;
      for (const n of sim.nodes) { a = Math.min(a, n.x - n.r); b = Math.min(b, n.y - n.r); p = Math.max(p, n.x + n.r); q = Math.max(q, n.y + n.r + 14); }
      // zapas w pikselach ekranu: napisy pod węzłami na brzegu też się mieszczą
      v.k = Math.min(2, Math.max(w / 2, w - 110) / (p - a + 1), Math.max(h / 2, h - 40) / (q - b + 1)); v.x = -v.k * (a + p) / 2; v.y = -v.k * (b + q) / 2;
    }
    if (sim) {
      const k = v.k, m = o.motyw(), sciezka = (fn, styl, gr) => {
        c.beginPath();
        for (const l of sim.links) if (fn(l)) { c.moveTo(l.a.x, l.a.y); c.lineTo(l.b.x, l.b.y); }
        c.strokeStyle = styl; c.lineWidth = gr / k; c.stroke();
      };
      const przy = (l) => zazn && (l.a.id === zazn || l.b.id === zazn);
      c.translate(w / 2 + v.x, h / 2 + v.y);
      c.scale(k, k);
      // mosty między skupiskami: łuk przez okolice środka, grubość od liczby linków
      c.globalAlpha = 0.35; c.strokeStyle = m.link;
      for (const { p, q, c: ile } of sim.mosty) {
        c.beginPath(); c.moveTo(p.x, p.y); c.quadraticCurveTo((p.x + q.x) / 4, (p.y + q.y) / 4, q.x, q.y);
        c.lineWidth = (0.6 + Math.log2(ile)) / k; c.stroke();
      }
      c.globalAlpha = 1;
      sciezka((l) => l.auto && !l.obca && !przy(l), m.linkAuto, 1);
      sciezka((l) => !l.auto && !l.obca && !przy(l), m.link, 1);
      if (zazn) sciezka(przy, m.zaznaczony, 1.6);
      const wiele = sim.grupy.length > 1;
      // widoczny wycinek świata: węzłów poza ekranem nie rysujemy
      const x0 = (-w / 2 - v.x) / k - 20, x1 = (w / 2 - v.x) / k + 20, y0 = (-h / 2 - v.y) / k - 20, y1 = (h / 2 - v.y) / k + 20, napisy = [];
      for (const n of sim.nodes) {
        if (n.x < x0 || n.x > x1 || n.y < y0 || n.y > y1) continue;
        const z = n.id === zazn;
        c.beginPath(); c.arc(n.x, n.y, n.r, 0, 7);
        if (n.stale) {
          c.globalAlpha = 0.16; c.fillStyle = o.kolor(n); c.fill(); c.globalAlpha = 1;
          c.strokeStyle = o.kolor(n); c.lineWidth = 2 / k; c.stroke();
        } else {
          c.fillStyle = n.hub ? m.hub : o.kolor(n);
          c.fill();
          if (n.hub) { c.strokeStyle = o.kolor(n); c.lineWidth = 2 / k; c.stroke(); }
        }
        if ((n.orphan && m.sierota) || n.status === "sprzeczna" || z) {
          c.strokeStyle = z ? m.zaznaczony : n.status === "sprzeczna" ? m.sprzeczna : m.sierota;
          c.lineWidth = 2 / k; c.beginPath(); c.arc(n.x, n.y, n.r + 2.5 / k, 0, 7); c.stroke();
        }
        // przy skupiskach napisy mają tylko skupiska (huby milczą, póki ktoś nie przybliży)
        if ((n.hub && !wiele) || n.stale || n.napis || k > 1.4 || z || n === nad) napisy.push(n);
      }
      // napisy od najważniejszego; ten, który nachodzi na już postawiony, czeka na przybliżenie albo mysz
      const pierwszenstwo = (n) => (n.id === zazn || n === nad ? 0 : n.stale ? 1 : n.hub ? 2 : n.napis ? 3 : 4), zajete = [];
      napisy.sort((a, b) => pierwszenstwo(a) - pierwszenstwo(b) || b.g.ile - a.g.ile || b.r - a.r);
      c.fillStyle = m.tekst; c.textAlign = "center"; c.textBaseline = "top"; c.lineJoin = "round";
      for (const n of napisy) {
        const t = n.etykieta || n.krotki || n.id.split("/").pop(), sz = (n.stale ? 13.5 : n.hub ? 12 : 11) / k;
        c.font = `${n.stale || n === nad || n.id === zazn ? "600 " : ""}${sz}px ${m.font}`;
        const s = t.length > (n.stale ? 30 : 42) ? t.slice(0, n.stale ? 28 : 40) + "…" : t, y = n.y + n.r + 3 / k;
        // napis przy brzegu przesunięty do środka, żeby nie uciekał poza płótno
        const mt = c.measureText(s), pol = ((mt && mt.width) || s.length * sz * 0.55) / 2 + 3 / k, lx = Math.max(x0 + 20 + pol, Math.min(x1 - 20 - pol, n.x));
        const r = [lx - pol, y, lx + pol, y + sz * 1.2];
        if (pierwszenstwo(n) && zajete.some((z) => z[0] < r[2] && r[0] < z[2] && z[1] < r[3] && r[1] < z[3])) continue;
        zajete.push(r);
        if (m.tlo) { c.strokeStyle = m.tlo; c.lineWidth = 3.5 / k; c.strokeText(s, lx, y); }
        c.fillText(s, lx, y);
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
      // mysz nad węzłem: jego nazwa i kursor „wskaż”
      const n = e.pointerType === "mouse" ? wezelW(swiat(e)) : null;
      if (n !== nad) { nad = n; canvas.style.cursor = n ? "pointer" : ""; odswiez(); }
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
    if (!n) return;
    if (sim.nodes.length <= 40) { v.fit = 1; return odswiez(); }   // mały graf widać cały: tylko zaznaczenie
    v.fit = id; v.k = Math.max(v.k, 1.6); odswiez();
  }
  return {
    dane(d) { sim = d ? grafSymulacja(d) : null; v.fit = 1; nad = null; odswiez(); return { wezly: sim ? sim.nodes.length : 0, linki: sim ? sim.links.length : 0 }; },
    zaznacz(id) { zazn = id; odswiez(); },
    calosc() { v.fit = 1; odswiez(); },   // znów cały graf w widoku (po zamknięciu notatki)
    wysrodkuj,
    stan: () => [v, sim],   // testy
    zniszcz() { cancelAnimationFrame(raf); raf = 1; if (ro) ro.disconnect(); for (const n in zd) canvas.removeEventListener(n, zd[n]); },
  };
}
