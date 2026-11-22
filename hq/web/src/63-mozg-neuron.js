// Mózg jako neuron (#/mozg, docs/HQ.md „Mózg”). 22.11 właściciel: „niech będzie neural, to wszystko połączone… stylowe,
// szykowne, smooth”, „każda sekcja swój kolor… jak się łączą, to gradientowo”, „widać od razu wszystkie kropki i jak się
// klika, to przybliża na te kropki”. Jeden obraz na wszystkich poziomach: JARVO (albo KERNEL) to ciało komórki, każda
// część to dendryt we własnym kolorze, który rozgałęzia się na grupy, a grupa to skupisko kropek (notatek). Linki to
// włókna z gradientem od koloru części jednej notatki do drugiej, między częściami wiązką przez pnie przy środku; po
// włóknach i dendrytach biegną impulsy. Poziomy to tylko kamera: część, grupa i notatka przybliżają ten sam obraz.
// `neuronUklad` (czysty, testowany w tests/test_mozg_zrodla.py) liczy świat z mozgMapa; `utworzNeuron` rysuje go
// w WebGL (kropki, włókna, dendryty, impulsy w shaderze) i w Canvas 2D (ciało komórki, napisy, obwódki), obsługuje
// mysz, kółko, dotyk i lot kamery. Impulsy: pętla do 30 klatek/s tylko przy widocznym Mózgu (ukryta karta, otwarta
// notatka albo `prefers-reduced-motion` = bez pętli, rysowanie na żądanie).

const NEURON = { soma: 74, pien: 150, krok: 7.5, przerwa: 16, wloknoKroki: 2, maksNapisow: 18 };

// ------------------------------------------------------------------------------------------------------- układ
// mapa (mozgMapa) → { czesci, kropki, byId, linki, bb }. Część: kąt na okręgu (szerokość wycinka z pierwiastka liczby
// notatek), węzeł J na końcu pnia, grupy w rzędach łuków za J (największa w środku), w grupie słonecznik notatek
// w kolejności `kolejnosc(grupa)` (pierwsza w środku). Notatki części bez grupy (hub części) siedzą przy J.
function neuronUklad(mapa, linki, kolejnosc) {
  const { soma, pien, krok, przerwa } = NEURON;
  const czesci = mapa.kat.filter((d) => d.ile > 0), wagi = czesci.map((d) => 0.8 + Math.sqrt(d.ile)), suma = wagi.reduce((a, b) => a + b, 0) || 1;
  const kropki = [], byId = new Map(), wynik = [];
  const promien = (n) => krok * Math.sqrt(n) * 0.92 + 5;
  const slonecznik = (lista, cx, cy, p, g) => lista.forEach((n, i) => {
    const r = i === 0 ? 0 : krok * Math.sqrt(i + 0.3) * 0.92, a = i * 2.399963 + p * 0.7;
    const kr = { id: n.id, n, x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), p, g, waga: (n.we || 0) + 0.5 * (n.wy || 0) + (n.hub ? 25 : 0) };
    kropki.push(kr); byId.set(n.id, kr);
  });
  let kat = -Math.PI / 2 - (Math.PI * wagi[0]) / suma;
  czesci.forEach((d, p) => {
    const wycinek = (2 * Math.PI * wagi[p]) / suma, a = kat + wycinek / 2;
    kat += wycinek;
    const ca = Math.cos(a), sa = Math.sin(a), J = { x: (soma + pien) * ca, y: (soma + pien) * sa };
    const grupy = d.grupy.map((g, i) => ({ k: g.k, nazwa: g.nazwa, ile: g.ile, wezly: kolejnosc(g), i, r: promien(g.wezly.length) }));
    // rzędy: każdy rząd to łuk o promieniu R, zapełniany do szerokości wycinka (z zapasem), środek rzędu na osi części
    const rzedy = [], dostepny = Math.max(0.5, wycinek * 0.86);
    let R = soma + pien + 26, rzad = [], szer = 0;
    const zamknij = () => { if (rzad.length) { rzedy.push({ R: R + Math.max(...rzad.map((g) => g.r)), grupy: rzad }); R += 2 * Math.max(...rzad.map((g) => g.r)) + przerwa; } rzad = []; szer = 0; };
    for (const g of [...grupy].sort((x, y) => y.r - x.r)) {
      const w = (2 * g.r + przerwa) / (R + g.r);
      if (rzad.length && szer + w > dostepny) zamknij();
      rzad.push(g); szer += w;
    }
    zamknij();
    for (const rz of rzedy) {
      // największa w środku, dalej na przemian po bokach
      const uk = []; rz.grupy.forEach((g, i) => (i % 2 ? uk.push(g) : uk.unshift(g)));
      const katy = uk.map((g) => (2 * g.r + przerwa) / rz.R), cala = katy.reduce((x, y) => x + y, 0);
      let b = a - cala / 2;
      uk.forEach((g, i) => { const ag = b + katy[i] / 2; b += katy[i]; g.a = ag; g.x = rz.R * Math.cos(ag); g.y = rz.R * Math.sin(ag); });
    }
    grupy.forEach((g, i) => slonecznik(g.wezly, g.x, g.y, p, i));
    const luzem = d.wezly.filter((n) => !byId.has(n.id) && (mapa.gdzie.get(n.id) || {}).kat === d.k);
    slonecznik(luzem, J.x, J.y, p, -1);
    const pk = kropki.filter((k) => k.p === p), zasieg = Math.max(...grupy.map((g) => Math.hypot(g.x, g.y) + g.r), soma + pien);
    wynik.push({ k: d.k, d, p, a, J, grupy, zasieg, bb: neuronBb(pk.map((k) => [k.x, k.y]).concat([[J.x, J.y]]), 10) });
  });
  for (const cz of wynik) for (const g of cz.grupy) g.bb = neuronBb(kropki.filter((k) => k.p === cz.p && k.g === g.i).map((k) => [k.x, k.y]), 6);
  // linki bez kierunku i bez dubli; tylko między narysowanymi notatkami
  const pary = new Map();
  for (const l of linki) {
    const a = byId.get(l.z), b = byId.get(l.do);
    if (!a || !b || a === b) continue;
    const k = a.id < b.id ? a.id + "\n" + b.id : b.id + "\n" + a.id;
    if (!pary.has(k)) pary.set(k, [a, b]);
  }
  return { czesci: wynik, kropki, byId, linki: [...pary.values()], bb: neuronBb(kropki.map((k) => [k.x, k.y]).concat([[-soma, -soma], [soma, soma]]), 20) };
}

function neuronBb(pkt, m) {
  if (!pkt.length) return [-m, -m, m, m];
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pkt) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return [x0 - m, y0 - m, x1 + m, y1 + m];
}

// trasa włókna (punkty kontrolne): w grupie łuk przez jej środek, między grupami części przez węzeł J, między
// częściami przez J obu części i pnie przy ciele komórki (wiązka); potem przyciągnięcie do prostej (ściśnięcie
// wiązki 0,82) i wygładzenie Chaikina
function neuronTrasa(u, a, b) {
  const A = u.czesci[a.p], B = u.czesci[b.p], s = NEURON.soma + 18;
  const ga = a.g >= 0 && A.grupy[a.g], gb = b.g >= 0 && B.grupy[b.g];
  let pk;
  if (a.p === b.p && a.g === b.g) pk = [[a.x, a.y], [ga ? ga.x : A.J.x, ga ? ga.y : A.J.y], [b.x, b.y]];
  else if (a.p === b.p) pk = [[a.x, a.y], ga ? [ga.x, ga.y] : null, [A.J.x, A.J.y], gb ? [gb.x, gb.y] : null, [b.x, b.y]].filter(Boolean);
  else pk = [[a.x, a.y], ga ? [ga.x, ga.y] : null, [A.J.x, A.J.y], [s * Math.cos(A.a), s * Math.sin(A.a)], [s * Math.cos(B.a), s * Math.sin(B.a)],
    [B.J.x, B.J.y], gb ? [gb.x, gb.y] : null, [b.x, b.y]].filter(Boolean);
  const n = pk.length - 1, beta = pk.length > 3 ? 0.82 : 0.6;
  pk = pk.map(([x, y], i) => [beta * x + (1 - beta) * (a.x + ((b.x - a.x) * i) / n), beta * y + (1 - beta) * (a.y + ((b.y - a.y) * i) / n)]);
  for (let it = 0; it < NEURON.wloknoKroki; it++) {
    const w = [pk[0]];
    for (let i = 0; i < pk.length - 1; i++) {
      const [x0, y0] = pk[i], [x1, y1] = pk[i + 1];
      w.push([0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1], [0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1]);
    }
    w.push(pk[pk.length - 1]);
    pk = w;
  }
  return pk;
}

// ------------------------------------------------------------------------------------------------------- WebGL
const NEURON_VS_LINIA = `precision highp float;
attribute vec2 p; attribute vec3 c; attribute vec3 m;
uniform vec4 uKam; uniform vec2 uWid; uniform float uFok, uNad;
varying vec3 vC; varying float vT, vF, vD;
void main() {
  float pa = floor(m.z / 64.0), pb = m.z - pa * 64.0;
  float jas = (uFok < 0.0 || abs(pa - uFok) < 0.5 || abs(pb - uFok) < 0.5) ? 1.0 : 0.22;
  if (uNad >= 0.0) jas *= (abs(pa - uNad) < 0.5 || abs(pb - uNad) < 0.5) ? 1.6 : 0.45;
  vC = c; vT = m.x; vF = m.y; vD = jas;
  gl_Position = vec4((p.x - uKam.x) * uKam.z * 2.0 / uWid.x, -(p.y - uKam.y) * uKam.z * 2.0 / uWid.y, 0.0, 1.0);
}`;
const NEURON_FS_LINIA = `precision mediump float;
varying vec3 vC; varying float vT, vF, vD;
uniform float uCzas, uA, uPuls, uMocne;
void main() {
  float cykl = uCzas * 0.16 + vF * 13.0, f = fract(cykl);
  float los = fract(sin((floor(cykl) + vF * 91.0) * 12.9898) * 43758.5453);
  float on = uPuls * (uMocne > 0.5 ? 1.0 : step(0.8, los));
  float d = vT - (f * 1.4 - 0.2);
  float puls = on * exp(-d * d * 900.0);
  vec3 k = vC * (uA * vD * (1.0 + uMocne * 4.0)) + (vC * 1.4 + vec3(0.25)) * puls * (0.55 + uMocne) * vD;
  gl_FragColor = vec4(k, 1.0);
}`;
const NEURON_VS_KROPKA = `precision highp float;
attribute vec2 p; attribute vec3 c; attribute vec2 m;
uniform vec4 uKam; uniform vec2 uWid; uniform float uFok, uNad, uDpr, uCzas, uPuls;
varying vec3 vC; varying float vD;
void main() {
  float jas = (uFok < 0.0 || abs(m.y - uFok) < 0.5) ? 1.0 : 0.3;
  if (uNad >= 0.0) jas *= abs(m.y - uNad) < 0.5 ? 1.35 : 0.55;
  vC = c * (0.92 + 0.08 * uPuls * sin(uCzas * 1.7 + p.x * 0.07 + p.y * 0.05)); vD = jas;
  gl_PointSize = clamp(m.x * uKam.z, 1.7, 7.5) * 3.0 * uDpr;
  gl_Position = vec4((p.x - uKam.x) * uKam.z * 2.0 / uWid.x, -(p.y - uKam.y) * uKam.z * 2.0 / uWid.y, 0.0, 1.0);
}`;
const NEURON_FS_KROPKA = `precision mediump float;
varying vec3 vC; varying float vD;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  float rdzen = smoothstep(0.36, 0.26, d), blask = exp(-d * d * 7.0) * 0.5;
  gl_FragColor = vec4((vC * (rdzen * 1.1 + blask) + vec3(rdzen * 0.06)) * vD, 1.0);
}`;

const neuronRgb = (hex) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  const v = m ? parseInt(m[1], 16) : 0x999999;
  return [((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255];
};

function utworzNeuron(pudlo, o) {
  const cgl = document.createElement("canvas"), c2 = document.createElement("canvas");
  cgl.className = "j-neuron-gl"; c2.className = "j-neuron-2d";
  cgl.setAttribute("aria-hidden", "true"); c2.setAttribute("aria-hidden", "true");
  pudlo.append(cgl, c2);
  const x2 = c2.getContext("2d");
  const gl = cgl.getContext("webgl", { antialias: true, alpha: false, premultipliedAlpha: false, preserveDrawingBuffer: false });
  const bezRuchu = matchMedia("(prefers-reduced-motion: reduce)");
  let W = 1, H = 1, dpr = 1, u = null, kolory = [], prog = null, bufory = null, raf = 0, ostatnia = 0, wstrzymany = false, zywy = true;
  const kam = { x: 0, y: 0, k: 1 }, stan = { fok: -1, grupa: -1, wybrana: null, nad: null, nadP: -1, traf: null };
  let lot = null, napisy = [], t0 = performance.now(), k0 = 1;

  // ---- programy i bufory
  function program(vs, fs) {
    const p = gl.createProgram();
    for (const [t, s] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
      const sh = gl.createShader(t); gl.shaderSource(sh, s); gl.compileShader(sh); gl.attachShader(p, sh);
    }
    gl.linkProgram(p);
    const atr = {}, uni = {};
    for (let i = 0; i < gl.getProgramParameter(p, gl.ACTIVE_ATTRIBUTES); i++) { const a = gl.getActiveAttrib(p, i); atr[a.name] = gl.getAttribLocation(p, a.name); }
    for (let i = 0; i < gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS); i++) { const a = gl.getActiveUniform(p, i); uni[a.name] = gl.getUniformLocation(p, a.name); }
    return { p, atr, uni };
  }
  function bufor(dane) { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, dane, gl.STATIC_DRAW); return b; }
  function zbuduj() {
    if (!gl || !u) return;
    if (!prog) prog = { linia: program(NEURON_VS_LINIA, NEURON_FS_LINIA), kropka: program(NEURON_VS_KROPKA, NEURON_FS_KROPKA) };
    if (bufory) for (const b of [bufory.linie, bufory.den, bufory.kropki]) gl.deleteBuffer(b);
    const kol = (p) => kolory[p % kolory.length] || [0.7, 0.7, 0.7];
    // włókna: gl.LINES, wierzchołek = x, y, r, g, b, t, faza, części (pa*64+pb); zakres każdej notatki do podświetlenia
    const L = [], zakresy = new Map();
    const dodajZakres = (id, od, ile) => { if (!zakresy.has(id)) zakresy.set(id, []); zakresy.get(id).push(od, ile); };
    for (const [a, b] of u.linki) {
      const pk = neuronTrasa(u, a, b), ca = kol(a.p), cb = kol(b.p), faza = Math.random(), pp = a.p * 64 + b.p, od = L.length / 9;
      for (let i = 0; i < pk.length - 1; i++) for (const j of [i, i + 1]) {
        const t = j / (pk.length - 1);
        L.push(pk[j][0], pk[j][1], ca[0] + (cb[0] - ca[0]) * t, ca[1] + (cb[1] - ca[1]) * t, ca[2] + (cb[2] - ca[2]) * t, t, faza, pp);
        L.push(0);   // wyrównanie do 9 pól (miejsce na przyszłe pole bez zmiany kroku)
      }
      const ile = L.length / 9 - od;
      dodajZakres(a.id, od, ile); dodajZakres(b.id, od, ile);
    }
    // dendryty: trójkąty zwężające się od ciała komórki do J i od J do grup (impuls biegnie do środka: t rośnie ku somie)
    const D = [], tasma = (pk, w0, w1, c, p, faza) => {
      for (let i = 0; i < pk.length - 1; i++) {
        const [x0, y0] = pk[i], [x1, y1] = pk[i + 1], dx = x1 - x0, dy = y1 - y0, l = Math.hypot(dx, dy) || 1, nx = -dy / l, ny = dx / l;
        const s0 = i / (pk.length - 1), s1 = (i + 1) / (pk.length - 1), a0 = (w0 + (w1 - w0) * s0) / 2, a1 = (w0 + (w1 - w0) * s1) / 2;
        const v = (x, y, s) => D.push(x, y, c[0], c[1], c[2], 1 - s, faza, p * 64 + p, 0);
        v(x0 + nx * a0, y0 + ny * a0, s0); v(x0 - nx * a0, y0 - ny * a0, s0); v(x1 + nx * a1, y1 + ny * a1, s1);
        v(x1 + nx * a1, y1 + ny * a1, s1); v(x0 - nx * a0, y0 - ny * a0, s0); v(x1 - nx * a1, y1 - ny * a1, s1);
      }
    };
    const krzywa = (a, b, c, n = 10) => Array.from({ length: n + 1 }, (_, i) => { const t = i / n, s = 1 - t; return [s * s * a[0] + 2 * s * t * b[0] + t * t * c[0], s * s * a[1] + 2 * s * t * b[1] + t * t * c[1]]; });
    for (const cz of u.czesci) {
      const c = kol(cz.p), so = NEURON.soma * 0.86, S = [so * Math.cos(cz.a), so * Math.sin(cz.a)], J = [cz.J.x, cz.J.y];
      const odg = 0.18 * (cz.p % 2 ? 1 : -1), M = [(S[0] + J[0]) / 2 - Math.sin(cz.a) * odg * 40, (S[1] + J[1]) / 2 + Math.cos(cz.a) * odg * 40];
      tasma(krzywa(S, M, J), 9 + Math.min(10, Math.sqrt(cz.d.ile)), 3.2, c, cz.p, Math.random());
      for (const g of cz.grupy) {
        const G = [g.x, g.y], K = [J[0] + (G[0] - J[0]) * 0.5 + Math.cos(cz.a) * 10, J[1] + (G[1] - J[1]) * 0.5 + Math.sin(cz.a) * 10];
        tasma(krzywa(G, K, J, 8), 1.2, 2.6 + Math.min(3, Math.sqrt(g.ile) * 0.4), c, cz.p, Math.random());
      }
    }
    const K = [];
    const maks = Math.max(1, ...u.kropki.map((k) => k.waga));
    for (const k of u.kropki) {
      const c = mozgWycofana(k.n) ? [0.45, 0.45, 0.48] : kol(k.p), w = Math.sqrt(k.waga / maks);
      k.r = 1.5 + 3.2 * w;
      K.push(k.x, k.y, c[0] * (0.75 + 0.25 * w), c[1] * (0.75 + 0.25 * w), c[2] * (0.75 + 0.25 * w), k.r, k.p);
    }
    bufory = { linie: bufor(new Float32Array(L)), nLinie: L.length / 9, den: bufor(new Float32Array(D)), nDen: D.length / 9,
      kropki: bufor(new Float32Array(K)), nKropki: K.length / 7, zakresy };
    siatka();
  }

  // ---- siatka do trafień (świat, komórka 24)
  let komorki = new Map();
  function siatka() {
    komorki = new Map();
    for (const k of u.kropki) { const key = Math.floor(k.x / 24) + ":" + Math.floor(k.y / 24); if (!komorki.has(key)) komorki.set(key, []); komorki.get(key).push(k); }
  }
  const swiat = (sx, sy) => [kam.x + (sx - W / 2) / kam.k, kam.y + (sy - H / 2) / kam.k];
  const ekran = (x, y) => [W / 2 + (x - kam.x) * kam.k, H / 2 + (y - kam.y) * kam.k];
  function trafKropke(sx, sy) {
    const [x, y] = swiat(sx, sy), zasieg = Math.max(9 / kam.k, 3), cx = Math.floor(x / 24), cy = Math.floor(y / 24);
    let naj = null, nd = Infinity;
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) for (const k of komorki.get(cx + i + ":" + (cy + j)) || []) {
      const d = Math.hypot(k.x - x, k.y - y);
      if (d < Math.max(zasieg, k.r) && d < nd) { nd = d; naj = k; }
    }
    return naj;
  }
  function trafNapis(sx, sy) { for (let i = napisy.length - 1; i >= 0; i--) { const n = napisy[i]; if (sx >= n.x0 && sx <= n.x1 && sy >= n.y0 && sy <= n.y1) return n; } return null; }
  function trafCzesc(sx, sy) {
    const [x, y] = swiat(sx, sy);
    for (const cz of u.czesci) for (const g of cz.grupy) if (Math.hypot(g.x - x, g.y - y) < g.r + 10 / kam.k) return { cz, g };
    const r = Math.hypot(x, y), a = Math.atan2(y, x);
    if (r < NEURON.soma) return null;
    for (const cz of u.czesci) { const d = Math.abs((((a - cz.a) % (2 * Math.PI)) + 3 * Math.PI) % (2 * Math.PI) - Math.PI); if (d < 0.12 && r < cz.zasieg + 20) return { cz, g: null }; }
    return null;
  }

  // ---- kamera
  const dopasuj = (bb, mx, my, kmaks) => ({ x: (bb[0] + bb[2]) / 2, y: (bb[1] + bb[3]) / 2, k: Math.min((W - 2 * mx) / (bb[2] - bb[0]), (H - 2 * my) / (bb[3] - bb[1]), kmaks) });
  function cel() {
    if (!u) return kam;
    k0 = dopasuj(u.bb, Math.min(240, W * 0.2), 70, 6).k;
    if (stan.wybrana) { const k = u.byId.get(stan.wybrana); if (k) return { x: k.x, y: k.y, k: Math.max(k0 * 5, kam.k) }; }
    const cz = stan.fok >= 0 && u.czesci[stan.fok];
    if (cz && stan.grupa >= 0 && cz.grupy[stan.grupa]) return dopasuj(cz.grupy[stan.grupa].bb, 120, 90, k0 * 14);
    if (cz) return dopasuj(cz.bb, 150, 80, k0 * 9);
    return dopasuj(u.bb, Math.min(240, W * 0.2), 70, 6);
  }
  function lec(c, ms = 900) {
    if (bezRuchu.matches || !ms) { Object.assign(kam, c); lot = null; } else lot = { z: { ...kam }, c, t: performance.now(), ms };
    zamow();
  }

  // ---- rysowanie
  function rozmiar() {
    const r = pudlo.getBoundingClientRect();
    dpr = Math.min(2, window.devicePixelRatio || 1); W = Math.max(1, r.width); H = Math.max(1, r.height);
    for (const c of [cgl, c2]) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); c.style.width = W + "px"; c.style.height = H + "px"; }
  }
  function rysujGL(czas) {
    if (!gl || !bufory) return;
    gl.viewport(0, 0, cgl.width, cgl.height);
    gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
    const puls = bezRuchu.matches ? 0 : 1, nadP = stan.nad ? -1 : stan.nadP;
    const L = prog.linia;
    gl.useProgram(L.p);
    gl.uniform4f(L.uni.uKam, kam.x, kam.y, kam.k, 0); gl.uniform2f(L.uni.uWid, W, H);
    gl.uniform1f(L.uni.uFok, stan.fok); gl.uniform1f(L.uni.uNad, nadP); gl.uniform1f(L.uni.uCzas, czas); gl.uniform1f(L.uni.uPuls, puls);
    const wiaz = (b) => {
      gl.bindBuffer(gl.ARRAY_BUFFER, b);
      gl.enableVertexAttribArray(L.atr.p); gl.vertexAttribPointer(L.atr.p, 2, gl.FLOAT, false, 36, 0);
      gl.enableVertexAttribArray(L.atr.c); gl.vertexAttribPointer(L.atr.c, 3, gl.FLOAT, false, 36, 8);
      gl.enableVertexAttribArray(L.atr.m); gl.vertexAttribPointer(L.atr.m, 3, gl.FLOAT, false, 36, 20);
    };
    // dendryty, potem włókna (jasność włókna maleje z ich liczbą, żeby gęsty mózg nie był białą plamą)
    wiaz(bufory.den); gl.uniform1f(L.uni.uA, 0.3); gl.uniform1f(L.uni.uMocne, 0); gl.drawArrays(gl.TRIANGLES, 0, bufory.nDen);
    wiaz(bufory.linie); gl.uniform1f(L.uni.uA, Math.min(0.15, 5.5 / Math.sqrt(u.linki.length + 1)) * Math.min(1.25, 0.9 + kam.k / k0 * 0.05));
    gl.drawArrays(gl.LINES, 0, bufory.nLinie);
    const jasne = stan.nad || stan.wybrana;
    if (jasne && bufory.zakresy.has(jasne)) {
      gl.uniform1f(L.uni.uMocne, 1); gl.uniform1f(L.uni.uFok, -1); gl.uniform1f(L.uni.uNad, -1);
      const z = bufory.zakresy.get(jasne);
      for (let i = 0; i < z.length; i += 2) gl.drawArrays(gl.LINES, z[i], z[i + 1]);
    }
    const K = prog.kropka;
    gl.useProgram(K.p);
    gl.uniform4f(K.uni.uKam, kam.x, kam.y, kam.k, 0); gl.uniform2f(K.uni.uWid, W, H); gl.uniform1f(K.uni.uFok, stan.fok);
    gl.uniform1f(K.uni.uNad, nadP); gl.uniform1f(K.uni.uDpr, dpr); gl.uniform1f(K.uni.uCzas, czas); gl.uniform1f(K.uni.uPuls, puls);
    gl.bindBuffer(gl.ARRAY_BUFFER, bufory.kropki);
    gl.enableVertexAttribArray(K.atr.p); gl.vertexAttribPointer(K.atr.p, 2, gl.FLOAT, false, 28, 0);
    gl.enableVertexAttribArray(K.atr.c); gl.vertexAttribPointer(K.atr.c, 3, gl.FLOAT, false, 28, 8);
    gl.enableVertexAttribArray(K.atr.m); gl.vertexAttribPointer(K.atr.m, 2, gl.FLOAT, false, 28, 20);
    gl.drawArrays(gl.POINTS, 0, bufory.nKropki);
  }

  const css = (k) => `rgb(${kolory[k % kolory.length].map((v) => Math.round(v * 255)).join(",")})`;
  function napis(t, x, y, { font, kolor, wyr = "left", tlo = false, cel: c = null, pad = 4 }) {
    x2.font = font;
    const w = x2.measureText(t).width, x0 = wyr === "center" ? x - w / 2 : wyr === "right" ? x - w : x, h = parseFloat(font.match(/(\d+(?:\.\d+)?)px/)[1]);
    const r = { x0: x0 - pad, y0: y - h * 0.8 - pad, x1: x0 + w + pad, y1: y + h * 0.3 + pad, cel: c };
    if (napisy.some((n) => r.x0 < n.x1 && r.x1 > n.x0 && r.y0 < n.y1 && r.y1 > n.y0) && !tlo) return null;
    if (tlo) { x2.fillStyle = "rgba(8,9,12,.86)"; x2.fillRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0); }
    x2.textAlign = "left";
    if (!tlo) { x2.lineJoin = "round"; x2.lineWidth = 4; x2.strokeStyle = "rgba(0,0,0,.85)"; x2.strokeText(t, x0, y); }
    x2.fillStyle = kolor; x2.fillText(t, x0, y);
    napisy.push(r);
    return r;
  }
  function rysuj2D(czas) {
    x2.setTransform(dpr, 0, 0, dpr, 0, 0);
    x2.clearRect(0, 0, W, H);
    napisy = [];
    if (!u) return;
    const m = o.motyw(), z = kam.k / k0, font = m.font || "sans-serif", mono = m.mono || "monospace";
    // ciało komórki: tarcza z pierścieniem w kolorach części (każda w swoim kącie), nazwa i liczba notatek
    const [sx, sy] = ekran(0, 0), R = NEURON.soma * kam.k;
    if (sx > -R && sx < W + R && sy > -R && sy < H + R) {
      const g = x2.createRadialGradient(sx, sy, R * 0.2, sx, sy, R * 1.6);
      g.addColorStop(0, "rgba(255,255,255,.07)"); g.addColorStop(0.6, "rgba(255,255,255,.025)"); g.addColorStop(1, "rgba(255,255,255,0)");
      x2.fillStyle = g; x2.beginPath(); x2.arc(sx, sy, R * 1.6, 0, 2 * Math.PI); x2.fill();
      x2.fillStyle = "#07080B"; x2.beginPath(); x2.arc(sx, sy, R, 0, 2 * Math.PI); x2.fill();
      if (x2.createConicGradient) {
        const cg = x2.createConicGradient(0, sx, sy), kat = (cz) => (((cz.a % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)) / (2 * Math.PI);
        const pierwsza = [...u.czesci].sort((a, b) => kat(a) - kat(b))[0];
        cg.addColorStop(0, css(pierwsza.p)); cg.addColorStop(1, css(pierwsza.p));
        for (const cz of u.czesci) cg.addColorStop(kat(cz), css(cz.p));
        x2.strokeStyle = cg;
      } else x2.strokeStyle = m.tekst;
      x2.lineWidth = Math.max(1.5, R * 0.035); x2.beginPath(); x2.arc(sx, sy, R, 0, 2 * Math.PI); x2.stroke();
      const fs = Math.max(12, Math.min(40, R * 0.3));
      x2.textAlign = "center"; x2.fillStyle = m.tekst; x2.font = `700 ${fs}px ${m.naglowek || font}`;
      x2.save(); if ("letterSpacing" in x2) x2.letterSpacing = `${fs * 0.12}px`; x2.fillText(o.centrum(), sx, sy + fs * 0.25); x2.restore();
      x2.font = `500 ${Math.max(10, fs * 0.36)}px ${mono}`; x2.fillStyle = m.tekst2; x2.fillText(o.podpis(), sx, sy + fs * 0.25 + fs * 0.62);
      napisy.push({ x0: sx - R, y0: sy - R, x1: sx + R, y1: sy + R, cel: { soma: 1 } });
    }
    // obwódki: wybrana notatka, trafienia szukania
    const obw = (k, kolor, r) => { const [x, y] = ekran(k.x, k.y); x2.strokeStyle = kolor; x2.lineWidth = 1.5; x2.beginPath(); x2.arc(x, y, r, 0, 2 * Math.PI); x2.stroke(); };
    if (stan.traf) for (const id of stan.traf) { const k = u.byId.get(id); if (k) obw(k, m.uwaga, Math.max(6, k.r * kam.k + 4)); }
    if (stan.wybrana && u.byId.has(stan.wybrana)) { const k = u.byId.get(stan.wybrana); obw(k, m.tekst, Math.max(8, k.r * kam.k + 6)); }
    // podpowiedź najechanej kropki: tytuł i miejsce (najpierw, żeby inne napisy jej nie zasłoniły)
    if (stan.nad && u.byId.has(stan.nad)) {
      const k = u.byId.get(stan.nad), [x, y] = ekran(k.x, k.y);
      obw(k, css(k.p), Math.max(7, k.r * kam.k + 5));
      const t = o.tytul(k.n), gd = o.miejsce(k.n.id);
      const r = napis(t.length > 60 ? t.slice(0, 58) + "…" : t, x + 14, y - 4, { font: `600 13px ${font}`, kolor: m.tekst, tlo: true, pad: 6 });
      if (gd && r) napis(gd, x + 14, r.y1 + 12, { font: `400 11.5px ${font}`, kolor: m.tekst2, tlo: true, pad: 5 });
    }
    // nazwy części: na końcu dendrytu, poza skupiskami; nazwa, która wpadłaby na inną, schodzi o wiersz od środka
    x2.textAlign = "left";
    for (const cz of u.czesci) {
      const d = cz.zasieg + 22 / Math.min(kam.k, 1.5), ca = Math.cos(cz.a), sa = Math.sin(cz.a);
      let [x, y] = ekran(d * ca, d * sa);
      if (x < -200 || x > W + 200 || y < -40 || y > H + 40) continue;
      const wyr = Math.abs(ca) < 0.25 ? "center" : ca > 0 ? "left" : "right", fok = stan.fok < 0 || stan.fok === cz.p;
      const nazwa = o.nazwa(cz.d), ile = String(cz.d.ile);
      x2.font = `600 15px ${font}`; const wn = x2.measureText(nazwa).width; x2.font = `500 12px ${mono}`; const wl = x2.measureText(ile).width;
      const cala = 14 + wn + 8 + wl, x0 = wyr === "center" ? x - cala / 2 : wyr === "right" ? x - cala : x;
      let r = { x0: x0 - 6, y0: y - 16, x1: x0 + cala + 6, y1: y + 8, cel: { czesc: cz.p } };
      for (let i = 0; i < 4 && napisy.some((n) => r.x0 < n.x1 && r.x1 > n.x0 && r.y0 < n.y1 && r.y1 > n.y0); i++) {
        const dy = sa >= 0 ? 22 : -22; y += dy; r = { ...r, y0: r.y0 + dy, y1: r.y1 + dy };
      }
      napisy.push(r);
      x2.globalAlpha = fok ? (cz.d.drugorzedna ? 0.72 : 1) : 0.4;
      x2.fillStyle = css(cz.p); x2.beginPath(); x2.arc(x0 + 4, y - 4.5, 4, 0, 2 * Math.PI); x2.fill();
      x2.fillStyle = m.tekst; x2.font = `600 15px ${font}`; x2.fillText(nazwa, x0 + 14, y);
      x2.fillStyle = m.tekst2; x2.font = `500 12px ${mono}`; x2.fillText(ile, x0 + 14 + wn + 8, y);
      x2.globalAlpha = 1;
    }
    // nazwy grup: od przybliżenia ×1,7 (część w kadrze), nad skupiskiem
    if (z > 1.7) for (const cz of u.czesci) {
      if (stan.fok >= 0 && cz.p !== stan.fok) continue;
      for (const g of cz.grupy) {
        if (cz.grupy.length < 2) continue;
        const [x, y] = ekran(g.x, g.y - g.r), wybrana = stan.grupa === g.i && stan.fok === cz.p;
        if (x < -100 || x > W + 100 || y < -20 || y > H + 40) continue;
        napis(`${g.nazwa}  ${g.ile}`, x, y - 10, { font: `600 ${wybrana ? 14 : 12.5}px ${font}`, kolor: wybrana ? m.tekst : css(cz.p), wyr: "center", cel: { czesc: cz.p, grupa: g.i } });
      }
    }
    // tytuły notatek: od przybliżenia ×3, najważniejsze w kadrze, bez nachodzenia
    if (z > 3) {
      const kand = u.kropki.filter((k) => { const [x, y] = ekran(k.x, k.y); return x > 0 && x < W - 40 && y > 10 && y < H - 10 && (stan.fok < 0 || k.p === stan.fok); })
        .sort((a, b) => b.waga - a.waga);
      let n = 0;
      for (const k of kand) {
        if (n >= NEURON.maksNapisow) break;
        const [x, y] = ekran(k.x, k.y), t = o.tytul(k.n);
        if (napis(t.length > 42 ? t.slice(0, 40) + "…" : t, x + Math.max(6, k.r * kam.k) + 4, y + 4, { font: `500 12px ${font}`, kolor: m.tekst2, cel: { notatka: k.id } })) n++;
      }
    }
  }

  // ---- pętla: impulsy do 30 klatek/s; lot kamery w pełnym tempie; bez ruchu = jedna klatka na żądanie
  function klatka(teraz) {
    raf = 0;
    if (!zywy) return;
    if (lot) {
      const t = Math.min(1, (teraz - lot.t) / lot.ms), e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      kam.k = Math.exp(Math.log(lot.z.k) + (Math.log(lot.c.k) - Math.log(lot.z.k)) * e);
      kam.x = lot.z.x + (lot.c.x - lot.z.x) * e; kam.y = lot.z.y + (lot.c.y - lot.z.y) * e;
      if (t >= 1) lot = null;
    }
    const czas = (teraz - t0) / 1000;
    rysujGL(czas); rysuj2D(czas);
    ostatnia = teraz;
    if (lot) zamow();
    else if (!wstrzymany && !bezRuchu.matches && !document.hidden) raf = requestAnimationFrame((t) => (t - ostatnia < 31 ? (raf = requestAnimationFrame(klatka)) : klatka(t)));
  }
  function zamow() { if (!raf && zywy && !wstrzymany) raf = requestAnimationFrame(klatka); }

  // ---- wejście: mysz, kółko, dotyk
  const wsk = new Map();
  let ciag = null, klikOk = true;
  const poz = (e) => { const r = c2.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  function zoom(sx, sy, f) {
    const [x, y] = swiat(sx, sy), k = Math.max(k0 * 0.6, Math.min(k0 * 40, kam.k * f));
    kam.k = k; kam.x = x - (sx - W / 2) / k; kam.y = y - (sy - H / 2) / k; lot = null; zamow();
  }
  const zd = {
    pointerdown: (e) => { c2.setPointerCapture && c2.setPointerCapture(e.pointerId); wsk.set(e.pointerId, poz(e)); ciag = { p: poz(e), kam: { ...kam }, d: null }; klikOk = true; },
    pointermove: (e) => {
      const p = poz(e);
      if (wsk.has(e.pointerId)) {
        const stary = wsk.get(e.pointerId); wsk.set(e.pointerId, p);
        if (wsk.size === 2) {
          const [a, b] = [...wsk.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]), d0 = ciag.d || d;
          ciag.d = d; klikOk = false; zoom((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, d / d0); return;
        }
        if (Math.hypot(p[0] - ciag.p[0], p[1] - ciag.p[1]) > 5) klikOk = false;
        if (!klikOk) { kam.x -= (p[0] - stary[0]) / kam.k; kam.y -= (p[1] - stary[1]) / kam.k; lot = null; c2.style.cursor = "grabbing"; zamow(); }
        return;
      }
      const k = trafKropke(p[0], p[1]), n = k ? null : trafNapis(p[0], p[1]), cz = k || n ? null : trafCzesc(p[0], p[1]);
      const nad = k ? k.id : null, nadP = k ? -1 : n && n.cel && n.cel.czesc != null ? n.cel.czesc : cz ? cz.cz.p : -1;
      c2.style.cursor = k || n || cz ? "pointer" : "grab";
      if (nad !== stan.nad || nadP !== stan.nadP) { stan.nad = nad; stan.nadP = nadP; zamow(); }
    },
    pointerup: (e) => {
      const p = poz(e); wsk.delete(e.pointerId); c2.style.cursor = "grab";
      if (!klikOk || wsk.size) return;
      const k = trafKropke(p[0], p[1]);
      if (k) return o.notatka(k.id);
      const n = trafNapis(p[0], p[1]);
      if (n && n.cel) {
        if (n.cel.notatka) return o.notatka(n.cel.notatka);
        if (n.cel.czesc != null) return o.czesc(u.czesci[n.cel.czesc].k, n.cel.grupa != null ? u.czesci[n.cel.czesc].grupy[n.cel.grupa].k : "");
        if (n.cel.soma) return o.wyzej(true);
      }
      const cz = trafCzesc(p[0], p[1]);
      if (cz) return o.czesc(cz.cz.k, cz.g && (stan.fok === cz.cz.p || cz.cz.grupy.length === 1) ? cz.g.k : "");
      o.wyzej(false);
    },
    pointercancel: (e) => { wsk.delete(e.pointerId); },
    pointerleave: () => { if (stan.nad || stan.nadP >= 0) { stan.nad = null; stan.nadP = -1; zamow(); } },
    wheel: (e) => { e.preventDefault(); const p = poz(e); zoom(p[0], p[1], Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0016))); },
  };
  for (const [n, f] of Object.entries(zd)) c2.addEventListener(n, f, n === "wheel" ? { passive: false } : undefined);
  const ro = new ResizeObserver(() => { rozmiar(); if (u) Object.assign(kam, cel()); zamow(); });
  ro.observe(pudlo);
  const widocznosc = () => zamow();
  document.addEventListener("visibilitychange", widocznosc);
  const utrata = (e) => { e.preventDefault(); prog = null; bufory = null; };
  const powrot = () => { zbuduj(); zamow(); };
  cgl.addEventListener("webglcontextlost", utrata); cgl.addEventListener("webglcontextrestored", powrot);
  rozmiar();

  return {
    gl: !!gl,
    dane(uklad, barwy) { u = uklad; kolory = barwy.map(neuronRgb); zbuduj(); Object.assign(kam, cel()); zamow(); },
    // stan widoku z adresu: część (indeks), grupa (indeks w części), notatka; zmiana = lot kamery
    ustaw({ fok = -1, grupa = -1, wybrana = null, traf = null }, animuj = true) {
      const zmiana = fok !== stan.fok || grupa !== stan.grupa || wybrana !== stan.wybrana;
      Object.assign(stan, { fok, grupa, wybrana, traf });
      if (zmiana) lec(cel(), animuj ? 900 : 0); else zamow();
    },
    wstrzymaj(t) { wstrzymany = t; if (!t) zamow(); else if (raf) { cancelAnimationFrame(raf); raf = 0; } },
    zniszcz() {
      zywy = false; if (raf) cancelAnimationFrame(raf);
      ro.disconnect(); document.removeEventListener("visibilitychange", widocznosc);
      for (const [n, f] of Object.entries(zd)) c2.removeEventListener(n, f);
      const ext = gl && gl.getExtension("WEBGL_lose_context"); if (ext) ext.loseContext();
      cgl.remove(); c2.remove();
    },
  };
}
