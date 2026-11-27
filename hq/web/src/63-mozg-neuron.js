// Mózg jako neuron (#/mozg, docs/HQ.md „Mózg”). 22.11 właściciel: „niech będzie neural, to wszystko połączone… smooth”,
// „widać od razu wszystkie kropki i jak się klika, to przybliża na te kropki”, potem: „za dużo naraz… koneksje tylko jak
// się najedzie… najpierw klik w sekcję, później w poszczególne… zoom smooth”, a na koniec: „linie od notatek do środka
// wyglądają jak baloniki… ma być męsko, 007… czemu tak daleko, bardziej compacted, tylko lekkie nuty kolorów”.
// Jeden spokojny obraz: JARVO (albo KERNEL) w środku, wokół zwarte skupiska kropek (grupy notatek) w wycinkach części,
// kropki w jasnej stali z nutą koloru części. Linki (włókna z gradientem, między częściami wiązką przez okolice środka)
// i biegnące po nich impulsy widać tylko przy najechaniu na część albo kropkę. Poziomy to kamera: klik w część
// przybliża część, w niej klik w grupę przybliża grupę, dopiero tam kropka otwiera notatkę. Karta pod kursorem (tytuł,
// streszczenie) to HTML widoku: `o.dymek`. `neuronUklad` (czysty, testowany w tests/test_mozg_zrodla.py) liczy świat
// z mozgMapa; `utworzNeuron` rysuje go w WebGL (kropki, włókna) i w Canvas 2D (środek, napisy, obwódki), obsługuje mysz,
// płynne kółko, dotyk i lot kamery. Rysuje tylko na żądanie; pętla (do 30 klatek/s) tylko przy najechaniu (impulsy).

// zwarty układ (22.11 właściciel: „czemu tak daleko… bardziej compacted”): skupiska tuż za ciałem komórki
const NEURON = { soma: 56, pien: 16, krok: 6.6, przerwa: 9, wloknoKroki: 2, maksNapisow: 18 };

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
    // rzędy: każdy rząd to łuk o promieniu R, zapełniany do szerokości wycinka (z zapasem na przerwę między częściami),
    // środek rzędu na osi części; grupa szersza niż wycinek odsuwa swój rząd od środka, aż się w nim zmieści
    const rzedy = [], dostepny = Math.max(0.35, wycinek * 0.8);
    let R = soma + pien + 12, rzad = [], szer = 0;
    const zamknij = () => { if (rzad.length) { rzedy.push({ R: R + Math.max(...rzad.map((g) => g.r)), grupy: rzad }); R += 2 * Math.max(...rzad.map((g) => g.r)) + przerwa; } rzad = []; szer = 0; };
    for (const g of [...grupy].sort((x, y) => y.r - x.r)) {
      let w = (2 * g.r + przerwa) / (R + g.r);
      if (rzad.length && szer + w > dostepny) { zamknij(); w = (2 * g.r + przerwa) / (R + g.r); }
      if (!rzad.length && w > dostepny) { R = (2 * g.r + przerwa) / dostepny - g.r; w = dostepny; }
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
  else if (a.p === b.p) pk = [[a.x, a.y], ga ? [ga.x, ga.y] : null, gb ? [gb.x, gb.y] : null, [b.x, b.y]].filter(Boolean);
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
// włókna jednym programem: `uWsz` 1 = rysuj wszystko (włókna najechanej albo otwartej kropki), 0 = tylko włókna
// dotykające najechanej części `uNad` (bez najechania włókien nie widać: 22.11 właściciel „koneksje tylko jak się
// najedzie”); impuls biegnie tylko po widocznych włóknach
const NEURON_VS_LINIA = `precision highp float;
attribute vec2 p; attribute vec3 c; attribute vec3 m;
uniform vec4 uKam; uniform vec2 uWid; uniform float uFok, uNad; uniform mediump float uWsz;   // uWsz też we fragmentach: ta sama precyzja
varying vec3 vC; varying float vT, vF, vD;
void main() {
  float pa = floor(m.z / 64.0), pb = m.z - pa * 64.0;
  float dotyka = (uNad >= 0.0 && (abs(pa - uNad) < 0.5 || abs(pb - uNad) < 0.5)) ? 1.0 : 0.0;
  float jas = uWsz > 0.5 ? ((uFok < 0.0 || abs(pa - uFok) < 0.5) ? 1.0 : 0.35) * ((uNad >= 0.0 && dotyka < 0.5) ? 0.55 : 1.0) : dotyka;
  vC = c; vT = m.x; vF = m.y; vD = jas;
  gl_Position = vec4((p.x - uKam.x) * uKam.z * 2.0 / uWid.x, -(p.y - uKam.y) * uKam.z * 2.0 / uWid.y, 0.0, 1.0);
}`;
const NEURON_FS_LINIA = `precision mediump float;
varying vec3 vC; varying float vT, vF, vD;
uniform float uCzas, uA, uPuls, uMocne, uWsz;
void main() {
  if (vD < 0.01) discard;
  float cykl = uCzas * 0.22 + vF * 13.0, f = fract(cykl);
  float los = fract(sin((floor(cykl) + vF * 91.0) * 12.9898) * 43758.5453);
  float on = uPuls * (uMocne > 0.5 ? 1.0 : (uWsz > 0.5 ? 0.0 : step(0.55, los)));
  float d = vT - (f * 1.4 - 0.2);
  float puls = on * exp(-d * d * 700.0);
  vec3 k = vC * (uA * vD * (1.0 + uMocne * 3.0)) + (vC * 1.3 + vec3(0.2)) * puls * (0.5 + uMocne * 0.5) * vD;
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
  gl_FragColor = vec4((vC * (rdzen * 0.95 + blask)) * vD, 1.0);
}`;

// kolor części z motywu tylko jako lekka nuta (22.11 właściciel: „bardziej compacted, tylko lekkie nuty kolorów”,
// „męsko, 007”): jasna stal z domieszką odcienia części
const neuronRgb = (hex) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  const v = m ? parseInt(m[1], 16) : 0x999999, c = [((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255];
  const s = (c[0] + c[1] + c[2]) / 3;
  return c.map((x) => Math.max(0, Math.min(1, 0.5 * 0.8 + 0.5 * (s + (x - s) * 1.5))));
};

function utworzNeuron(pudlo, o) {
  const cgl = document.createElement("canvas"), c2 = document.createElement("canvas");
  cgl.className = "j-neuron-gl"; c2.className = "j-neuron-2d";
  cgl.setAttribute("aria-hidden", "true"); c2.setAttribute("aria-hidden", "true");
  pudlo.append(cgl, c2);
  const x2 = c2.getContext("2d");
  const gl = cgl.getContext("webgl", { antialias: true, alpha: false, premultipliedAlpha: false, preserveDrawingBuffer: false });
  const bezRuchu = matchMedia("(prefers-reduced-motion: reduce)");
  let W = 1, H = 1, dpr = 1, u = null, kolory = [], prog = null, bufory = null, raf = 0, ostatnia = 0, zywy = true;
  const kam = { x: 0, y: 0, k: 1 }, stan = { fok: -1, grupa: -1, wybrana: null, nad: null, nadP: -1, traf: null, mysz: null };
  let dymek = "";   // ostatnio zgłoszona karta pod kursorem (o.dymek), żeby nie zgłaszać co klatkę tego samego
  let lot = null, napisy = [], t0 = performance.now(), k0 = 1;

  // ---- programy i bufory
  function program(vs, fs) {
    const p = gl.createProgram();
    for (const [t, s] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
      const sh = gl.createShader(t); gl.shaderSource(sh, s); gl.compileShader(sh); gl.attachShader(p, sh);
    }
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) console.error("Mózg: program WebGL", gl.getProgramInfoLog(p));
    const atr = {}, uni = {};
    for (let i = 0; i < gl.getProgramParameter(p, gl.ACTIVE_ATTRIBUTES); i++) { const a = gl.getActiveAttrib(p, i); atr[a.name] = gl.getAttribLocation(p, a.name); }
    for (let i = 0; i < gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS); i++) { const a = gl.getActiveUniform(p, i); uni[a.name] = gl.getUniformLocation(p, a.name); }
    return { p, atr, uni };
  }
  function bufor(dane) { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, dane, gl.STATIC_DRAW); return b; }
  function zbuduj() {
    if (!gl || !u) return;
    if (!prog) prog = { linia: program(NEURON_VS_LINIA, NEURON_FS_LINIA), kropka: program(NEURON_VS_KROPKA, NEURON_FS_KROPKA) };
    if (bufory) for (const b of [bufory.linie, bufory.kropki]) gl.deleteBuffer(b);
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
    const K = [];
    const maks = Math.max(1, ...u.kropki.map((k) => k.waga));
    for (const k of u.kropki) {
      // kolor części; grupy w części lekko jaśniejsze albo ciemniejsze na zmianę, żeby skupiska dało się odróżnić
      const odcien = k.g < 0 ? 1 : [1, 1.08, 0.92][k.g % 3];
      const c = mozgWycofana(k.n) ? [0.4, 0.4, 0.43] : kol(k.p).map((v) => Math.min(1, v * odcien)), w = Math.sqrt(k.waga / maks);
      k.r = 1.4 + 2.8 * w;
      K.push(k.x, k.y, c[0] * (0.72 + 0.28 * w), c[1] * (0.72 + 0.28 * w), c[2] * (0.72 + 0.28 * w), k.r, k.p);
    }
    bufory = { linie: bufor(new Float32Array(L)), nLinie: L.length / 9, kropki: bufor(new Float32Array(K)), nKropki: K.length / 7, zakresy };
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
  function trafKropke(sx, sy, palec = false) {
    const [x, y] = swiat(sx, sy), zasieg = Math.max((palec ? 20 : 9) / kam.k, 3), cx = Math.floor(x / 24), cy = Math.floor(y / 24);
    let naj = null, nd = Infinity;
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) for (const k of komorki.get(cx + i + ":" + (cy + j)) || []) {
      const d = Math.hypot(k.x - x, k.y - y);
      if (d < Math.max(zasieg, k.r) && d < nd) { nd = d; naj = k; }
    }
    return naj;
  }
  // kropka „pod ręką” dopiero na swoim poziomie (22.11 właściciel: „najpierw się klika na sekcję, później na
  // poszczególne”): część w kadrze i (jedna grupa, grupa w kadrze albo przybliżenie ×5); inaczej klik przybliża
  // o poziom: część, potem grupa
  function dostepna(k) {
    const cz = u.czesci[k.p];
    return stan.fok === k.p && (cz.grupy.length < 2 || k.g < 0 || stan.grupa === k.g || kam.k / k0 > 5);
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
  // m = marginesy ekranu {l, r, t, b}: kadr to to, co zostaje między nimi (na telefonie pole szukania u góry i panel
  // poziomu u dołu zasłaniają mapę, więc część przybliża się w wolne miejsce, a nie pod nie)
  const dopasuj = (bb, m, kmaks) => {
    const w = Math.max(40, W - m.l - m.r), h = Math.max(40, H - m.t - m.b);
    const k = Math.min(w / (bb[2] - bb[0]), h / (bb[3] - bb[1]), kmaks);
    return { x: (bb[0] + bb[2]) / 2 - (m.l + w / 2 - W / 2) / k, y: (bb[1] + bb[3]) / 2 - (m.t + h / 2 - H / 2) / k, k };
  };
  const waski = () => W < 700;   // jak @container app (max-width: 700px) w style.css
  // marginesy poziomu: na telefonie wąsko w bok (napisy części dociskają się do brzegu) i z zasłonami widoku (o.zaslony)
  function marginesy(bok, gora) {
    if (!waski()) return { l: bok, r: bok, t: gora, b: gora };
    const z = (o.zaslony && o.zaslony()) || { t: 0, b: 0 };
    return { l: 16, r: 16, t: Math.max(24, z.t + 12), b: Math.max(24, z.b + 12) };
  }
  function cel() {
    if (!u) return kam;
    const calosc = marginesy(Math.min(240, W * 0.2), 70);
    k0 = dopasuj(u.bb, waski() ? { ...calosc, l: 64, r: 64 } : calosc, 6).k;
    // otwarta notatka: kropka w środku tego, co zostaje obok panelu notatki (panel z prawej, do 480 px; telefon: cały ekran)
    if (stan.wybrana) {
      const k = u.byId.get(stan.wybrana), kz = Math.max(k0 * 5, kam.k), panel = W > 700 ? Math.min(480, W - 24) + 12 : 0;
      if (k) return { x: k.x + panel / 2 / kz, y: k.y, k: kz };
    }
    const cz = stan.fok >= 0 && u.czesci[stan.fok];
    if (cz && stan.grupa >= 0 && cz.grupy[stan.grupa]) return dopasuj(cz.grupy[stan.grupa].bb, marginesy(120, 90), k0 * 14);
    if (cz) return dopasuj(cz.bb, marginesy(150, 80), k0 * 9);
    return dopasuj(u.bb, waski() ? { ...calosc, l: 64, r: 64 } : calosc, 6);
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
    if (!gl) return;
    gl.viewport(0, 0, cgl.width, cgl.height);
    gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT);
    if (!bufory || !u) return;
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
    const puls = bezRuchu.matches ? 0 : 1, nadP = stan.nad ? (u.byId.get(stan.nad) || {}).p ?? -1 : stan.nadP;
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
    // w spoczynku same kropki; włókna tylko najechanej części albo kropki (i otwartej notatki)
    wiaz(bufory.linie); gl.uniform1f(L.uni.uWsz, 1); gl.uniform1f(L.uni.uMocne, 0);
    const jasne = stan.nad || stan.wybrana;
    if (jasne && bufory.zakresy.has(jasne)) {
      gl.uniform1f(L.uni.uMocne, 1); gl.uniform1f(L.uni.uFok, -1); gl.uniform1f(L.uni.uNad, -1); gl.uniform1f(L.uni.uA, 0.35);
      const z = bufory.zakresy.get(jasne);
      for (let i = 0; i < z.length; i += 2) gl.drawArrays(gl.LINES, z[i], z[i + 1]);
    } else if (nadP >= 0) {
      gl.uniform1f(L.uni.uWsz, 0); gl.uniform1f(L.uni.uA, Math.min(0.2, 7 / Math.sqrt(u.linki.length + 1)));
      gl.drawArrays(gl.LINES, 0, bufory.nLinie);
    }
    const K = prog.kropka;
    gl.useProgram(K.p);
    gl.uniform4f(K.uni.uKam, kam.x, kam.y, kam.k, 0); gl.uniform2f(K.uni.uWid, W, H); gl.uniform1f(K.uni.uFok, stan.fok);
    gl.uniform1f(K.uni.uNad, nadP); gl.uniform1f(K.uni.uDpr, dpr); gl.uniform1f(K.uni.uCzas, czas); gl.uniform1f(K.uni.uPuls, 0);
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
    // środek: czarna tarcza z cienkim stalowym pierścieniem i drugim, ledwie widocznym; nazwa i liczba notatek
    const [sx, sy] = ekran(0, 0), R = NEURON.soma * kam.k;
    if (sx > -R && sx < W + R && sy > -R && sy < H + R) {
      x2.fillStyle = "#06070A"; x2.beginPath(); x2.arc(sx, sy, R, 0, 2 * Math.PI); x2.fill();
      x2.strokeStyle = "rgba(237,235,230,.55)"; x2.lineWidth = 1; x2.beginPath(); x2.arc(sx, sy, R, 0, 2 * Math.PI); x2.stroke();
      x2.strokeStyle = "rgba(237,235,230,.12)"; x2.beginPath(); x2.arc(sx, sy, R + 6, 0, 2 * Math.PI); x2.stroke();
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
    // karta pod kursorem (HTML w widoku: tytuł, miejsce, streszczenie): kropka zakotwiczona w swoim miejscu na ekranie,
    // część przy kursorze; zgłaszana tylko przy zmianie
    let d = null;
    if (stan.nad && u.byId.has(stan.nad)) {
      const k = u.byId.get(stan.nad), [x, y] = ekran(k.x, k.y), r = Math.max(7, k.r * kam.k + 5);
      obw(k, m.tekst, r);
      d = { id: k.id, x: Math.round(x), y: Math.round(y), r: Math.round(r) };
    } else if (stan.nadP >= 0 && stan.mysz) d = { czesc: u.czesci[stan.nadP].k, x: Math.round(stan.mysz[0]), y: Math.round(stan.mysz[1]), r: 14 };
    const klucz = d ? `${d.id || d.czesc}:${d.x}:${d.y}` : "";
    if (klucz !== dymek) { dymek = klucz; o.dymek(d); }
    // nazwy części: za skupiskami części; nazwa, która wpadłaby na inną, schodzi o wiersz od środka
    // telefon: mniejsze napisy dociśnięte do brzegu ekranu (wcześniej uciekały za brzeg, 23.11 właściciel: „Mózg na
    // mobile trochę zbugowany”), a w przybliżonej części tylko jej napis, bez szarych napisów sąsiadów na kropkach
    x2.textAlign = "left";
    const fN = waski() ? 13 : 15, fL = waski() ? 11 : 12;
    for (const cz of u.czesci) {
      if (waski() && stan.fok >= 0 && stan.fok !== cz.p) continue;
      const d = cz.zasieg + 22 / Math.min(kam.k, 1.5), ca = Math.cos(cz.a), sa = Math.sin(cz.a);
      let [x, y] = ekran(d * ca, d * sa);
      if (x < -200 || x > W + 200 || y < -40 || y > H + 40) continue;
      const wyr = Math.abs(ca) < 0.25 ? "center" : ca > 0 ? "left" : "right", fok = stan.fok < 0 || stan.fok === cz.p;
      const nazwa = o.nazwa(cz.d), ile = String(cz.d.ile);
      x2.font = `600 ${fN}px ${font}`; const wn = x2.measureText(nazwa).width; x2.font = `500 ${fL}px ${mono}`; const wl = x2.measureText(ile).width;
      const cala = 14 + wn + 8 + wl;
      let x0 = wyr === "center" ? x - cala / 2 : wyr === "right" ? x - cala : x;
      if (waski()) x0 = Math.max(8, Math.min(W - cala - 8, x0));
      let r = { x0: x0 - 6, y0: y - 16, x1: x0 + cala + 6, y1: y + 8, cel: { czesc: cz.p } };
      for (let i = 0; i < 4 && napisy.some((n) => r.x0 < n.x1 && r.x1 > n.x0 && r.y0 < n.y1 && r.y1 > n.y0); i++) {
        const dy = sa >= 0 ? 22 : -22; y += dy; r = { ...r, y0: r.y0 + dy, y1: r.y1 + dy };
      }
      napisy.push(r);
      x2.globalAlpha = fok ? (cz.d.drugorzedna ? 0.72 : 1) : 0.4;
      x2.fillStyle = css(cz.p); x2.beginPath(); x2.arc(x0 + 4, y - 4.5, 4, 0, 2 * Math.PI); x2.fill();
      if (waski()) { x2.lineJoin = "round"; x2.lineWidth = 4; x2.strokeStyle = "rgba(0,0,0,.85)"; x2.font = `600 ${fN}px ${font}`; x2.strokeText(nazwa, x0 + 14, y); }
      x2.fillStyle = m.tekst; x2.font = `600 ${fN}px ${font}`; x2.fillText(nazwa, x0 + 14, y);
      x2.fillStyle = m.tekst2; x2.font = `500 ${fL}px ${mono}`; x2.fillText(ile, x0 + 14 + wn + 8, y);
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
      const kand = u.kropki.filter((k) => { const [x, y] = ekran(k.x, k.y); return x > 0 && x < W - (waski() ? 100 : 40) && y > 10 && y < H - 10 && (stan.fok < 0 || k.p === stan.fok); })
        .sort((a, b) => b.waga - a.waga);
      let n = 0;
      const fT = `500 12px ${font}`, maks = waski() ? 10 : NEURON.maksNapisow;
      x2.font = fT;
      for (const k of kand) {
        if (n >= maks) break;
        const [x, y] = ekran(k.x, k.y), tx = x + Math.max(6, k.r * kam.k) + 4, miejsce = Math.min(300, W - tx - 8);
        // tytuł kończy się przed brzegiem ekranu (telefon: wcześniej był ucięty w pół słowa za krawędzią)
        let t = o.tytul(k.n);
        if (x2.measureText(t).width > miejsce) { while (t.length > 4 && x2.measureText(t + "…").width > miejsce) t = t.slice(0, -1); t = t.trimEnd() + "…"; }
        if (napis(t, tx, y + 4, { font: fT, kolor: m.tekst2, cel: { notatka: k.id } })) n++;
      }
    }
  }

  // ---- pętla: lot kamery w pełnym tempie, impulsy najechanych włókien do 30 klatek/s; bez ruchu i bez najechania
  // jedna klatka na żądanie (CPU w spoczynku = 0)
  function klatka(teraz) {
    raf = 0;
    if (!zywy) return;
    if (lot) {
      const t = Math.min(1, (teraz - lot.t) / lot.ms);
      const e = lot.kolo ? 1 - Math.pow(1 - t, 3) : t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      kam.k = Math.exp(Math.log(lot.z.k) + (Math.log(lot.c.k) - Math.log(lot.z.k)) * e);
      kam.x = lot.z.x + (lot.c.x - lot.z.x) * e; kam.y = lot.z.y + (lot.c.y - lot.z.y) * e;
      if (t >= 1) lot = null;
    }
    const czas = (teraz - t0) / 1000;
    rysujGL(czas); rysuj2D(czas);
    ostatnia = teraz;
    if (lot) zamow();
    else if (!bezRuchu.matches && !document.hidden && (stan.nad || stan.nadP >= 0))
      raf = requestAnimationFrame((t) => (t - ostatnia < 31 ? (raf = requestAnimationFrame(klatka)) : klatka(t)));
  }
  function zamow() { if (!raf && zywy) raf = requestAnimationFrame(klatka); }

  // ---- wejście: mysz, kółko, dotyk
  const wsk = new Map();
  let ciag = null, klikOk = true;
  const poz = (e) => { const r = c2.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  // kółko: płynnie (krótki lot 0,26 s do nowej skali wokół kursora; kolejne obroty liczą od celu bieżącego lotu),
  // dwa palce: od razu
  function zoom(sx, sy, f, plynnie) {
    const b = lot && lot.kolo ? lot.c : kam, x = b.x + (sx - W / 2) / b.k, y = b.y + (sy - H / 2) / b.k;
    const k = Math.max(k0 * 0.6, Math.min(k0 * 40, b.k * f)), c = { x: x - (sx - W / 2) / k, y: y - (sy - H / 2) / k, k };
    if (!plynnie || bezRuchu.matches) { Object.assign(kam, c); lot = null; } else lot = { z: { ...kam }, c, t: performance.now(), ms: 260, kolo: true };
    zamow();
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
        if (Math.hypot(p[0] - ciag.p[0], p[1] - ciag.p[1]) > (e.pointerType === "touch" ? 10 : 5)) klikOk = false;
        if (!klikOk) { kam.x -= (p[0] - stary[0]) / kam.k; kam.y -= (p[1] - stary[1]) / kam.k; lot = null; c2.style.cursor = "grabbing"; zamow(); }
        return;
      }
      const tk = trafKropke(p[0], p[1]), k = tk && dostepna(tk) ? tk : null, n = k ? null : trafNapis(p[0], p[1]);
      const cz = k || n ? null : tk ? { cz: u.czesci[tk.p] } : trafCzesc(p[0], p[1]);
      // w przybliżonej części ruch myszy nie zapala wszystkich jej włókien (spokój), tylko kropka pod ręką
      const nad = k ? k.id : null, nadC = k ? -1 : n && n.cel && n.cel.czesc != null ? n.cel.czesc : cz ? cz.cz.p : -1, nadP = nadC === stan.fok ? -1 : nadC;
      c2.style.cursor = k || n || cz ? "pointer" : "grab";
      stan.mysz = p;
      if (nad !== stan.nad || nadP !== stan.nadP || (nadP >= 0 && !nad)) { stan.nad = nad; stan.nadP = nadP; zamow(); }
    },
    pointerup: (e) => {
      const p = poz(e); wsk.delete(e.pointerId); c2.style.cursor = "grab";
      if (!klikOk || wsk.size) return;
      const k = trafKropke(p[0], p[1], e.pointerType === "touch");   // palec jest grubszy niż kursor
      if (k && dostepna(k)) return o.notatka(k.id);
      if (k) { const cz = u.czesci[k.p]; return o.czesc(cz.k, stan.fok === k.p && k.g >= 0 ? cz.grupy[k.g].k : ""); }
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
    pointerleave: () => { stan.mysz = null; if (stan.nad || stan.nadP >= 0) { stan.nad = null; stan.nadP = -1; zamow(); } },
    wheel: (e) => { e.preventDefault(); const p = poz(e); zoom(p[0], p[1], Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0016)), true); },
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
    // nowe dane (np. przełączenie Skarbiec Jarva ↔ Wiedza Kernela): przerwany lot kamery, kadr całości nowej mapy;
    // null = mapa pusta do czasu nowych danych (27.11: stara mapa pod nazwą nowego źródła i kadr poza środkiem)
    dane(uklad, barwy) {
      u = uklad || null; lot = null; stan.nad = null; stan.nadP = -1;
      if (u) { kolory = barwy.map(neuronRgb); zbuduj(); Object.assign(kam, cel()); }
      zamow();
    },
    // stan widoku z adresu: część (indeks), grupa (indeks w części), notatka; zmiana = lot kamery
    ustaw({ fok = -1, grupa = -1, wybrana = null, traf = null }, animuj = true) {
      const zmiana = fok !== stan.fok || grupa !== stan.grupa || wybrana !== stan.wybrana;
      Object.assign(stan, { fok, grupa, wybrana, traf });
      // nowy poziom: najechanie (włókna, karta) gaśnie do następnego ruchu myszy, żeby po przybliżeniu był spokój
      if (zmiana) { stan.nad = null; stan.nadP = -1; }
      if (zmiana) lec(cel(), animuj ? 900 : 0); else zamow();
    },
    zniszcz() {
      zywy = false; if (raf) cancelAnimationFrame(raf);
      ro.disconnect(); document.removeEventListener("visibilitychange", widocznosc);
      for (const [n, f] of Object.entries(zd)) c2.removeEventListener(n, f);
      const ext = gl && gl.getExtension("WEBGL_lose_context"); if (ext) ext.loseContext();
      cgl.remove(); c2.remove();
    },
  };
}
