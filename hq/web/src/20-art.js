// Grafika HQ: „Wieża Jarvo” w pixel arcie. Przekrój bazy jak model z klocków: płaskie cięcie,
// a pokoje mają głębię (perspektywa jednego punktu). Wszystko rysowane w siatce pikseli logicznych
// (scena 400 px szerokości) i skalowane w SVG z crispEdges, więc piksele zostają ostre w każdym rozmiarze.
// Rysunek łączy prostokąty tego samego koloru w jedną ścieżkę (mało węzłów DOM, szybki rerender).

// ------------------------------------------------------------------ silnik pikseli

// font 3×5 (wielkie litery, cyfry, kilka znaków); polskie litery rysujemy bez ogonków
const PX_FONT = {
  A: [".#.", "#.#", "###", "#.#", "#.#"], B: ["##.", "#.#", "##.", "#.#", "##."], C: [".##", "#..", "#..", "#..", ".##"],
  D: ["##.", "#.#", "#.#", "#.#", "##."], E: ["###", "#..", "##.", "#..", "###"], F: ["###", "#..", "##.", "#..", "#.."],
  G: [".##", "#..", "#.#", "#.#", ".##"], H: ["#.#", "#.#", "###", "#.#", "#.#"], I: ["###", ".#.", ".#.", ".#.", "###"],
  J: ["..#", "..#", "..#", "#.#", ".#."], K: ["#.#", "#.#", "##.", "#.#", "#.#"], L: ["#..", "#..", "#..", "#..", "###"],
  M: ["#.#", "###", "###", "#.#", "#.#"], N: ["##.", "#.#", "#.#", "#.#", "#.#"], O: [".#.", "#.#", "#.#", "#.#", ".#."],
  P: ["##.", "#.#", "##.", "#..", "#.."], Q: [".#.", "#.#", "#.#", "##.", ".##"], R: ["##.", "#.#", "##.", "#.#", "#.#"],
  S: [".##", "#..", ".#.", "..#", "##."], T: ["###", ".#.", ".#.", ".#.", ".#."], U: ["#.#", "#.#", "#.#", "#.#", "###"],
  V: ["#.#", "#.#", "#.#", ".#.", ".#."], W: ["#.#", "#.#", "###", "###", "#.#"], X: ["#.#", "#.#", ".#.", "#.#", "#.#"],
  Y: ["#.#", "#.#", ".#.", ".#.", ".#."], Z: ["###", "..#", ".#.", "#..", "###"],
  0: ["###", "#.#", "#.#", "#.#", "###"], 1: [".#.", "##.", ".#.", ".#.", "###"], 2: ["##.", "..#", ".#.", "#..", "###"],
  3: ["##.", "..#", ".#.", "..#", "##."], 4: ["#.#", "#.#", "###", "..#", "..#"], 5: ["###", "#..", "##.", "..#", "##."],
  6: [".##", "#..", "###", "#.#", "###"], 7: ["###", "..#", ".#.", ".#.", ".#."], 8: ["###", "#.#", "###", "#.#", "###"],
  9: ["###", "#.#", "###", "..#", "##."], "<": ["..#", ".#.", "#..", ".#.", "..#"], ">": ["#..", ".#.", "..#", ".#.", "#.."],
  "/": ["..#", "..#", ".#.", "#..", "#.."], "+": ["...", ".#.", "###", ".#.", "..."], "-": ["...", "...", "###", "...", "..."],
  "!": [".#.", ".#.", ".#.", "...", ".#."], "?": ["##.", "..#", ".#.", "...", ".#."], ".": ["...", "...", "...", "...", ".#."],
  ":": ["...", ".#.", "...", ".#.", "..."],
};
const PX_FOLD = { "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N", "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z" };
const pxTextW = (str, s = 1) => Math.max(0, String(str).length * 4 * s - s);

class Pix {
  // Prostokąty tego samego koloru łączymy w jedną ścieżkę, ale tylko gdy nic narysowane później
  // ich nie przykrywa (inaczej zmieniłaby się kolejność warstw).
  constructor(ox = 0, oy = 0) { this.ox = ox; this.oy = oy; this.segs = []; this.last = new Map(); }
  r(x, y, w, h, c) {
    if (!c || w <= 0 || h <= 0) return this;
    const X = Math.round(x + this.ox), Y = Math.round(y + this.oy), W = Math.round(w), H = Math.round(h);
    const idx = this.last.get(c);
    let seg = idx === undefined ? null : this.segs[idx];
    if (seg) {
      for (let i = idx + 1; i < this.segs.length; i++) {
        const o = this.segs[i];
        if (X >= o.x1 || X + W <= o.x0 || Y >= o.y1 || Y + H <= o.y0) continue;
        if (o.rects.some(([a, b, cw, ch]) => X < a + cw && a < X + W && Y < b + ch && b < Y + H)) { seg = null; break; }
      }
    }
    if (!seg) {
      seg = { c, d: [], rects: [], x0: X, y0: Y, x1: X + W, y1: Y + H };
      this.segs.push(seg); this.last.set(c, this.segs.length - 1);
    }
    seg.d.push(`M${X} ${Y}h${W}v${H}h${-W}z`); seg.rects.push([X, Y, W, H]);
    seg.x0 = Math.min(seg.x0, X); seg.y0 = Math.min(seg.y0, Y); seg.x1 = Math.max(seg.x1, X + W); seg.y1 = Math.max(seg.y1, Y + H);
    return this;
  }
  p(x, y, c) { return this.r(x, y, 1, 1, c); }
  line(x0, y0, x1, y1, c) {
    x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1);
    const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    for (let i = 0; i < 400; i++) {
      this.p(x0, y0, c);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
    return this;
  }
  circle(cx, cy, rad, c) {
    for (let dy = -rad; dy <= rad; dy++) {
      const half = Math.round(Math.sqrt(rad * rad - dy * dy));
      this.r(cx - half, cy + dy, half * 2 + 1, 1, c);
    }
    return this;
  }
  text(x, y, str, c, s = 1) {
    let cx = x;
    for (const raw of String(str).toUpperCase()) {
      const gl = PX_FONT[PX_FOLD[raw] || raw];
      if (gl) gl.forEach((row, j) => { for (let i = 0; i < 3; i++) if (row[i] === "#") this.r(cx + i * s, y + j * s, s, s, c); });
      cx += 4 * s;
    }
    return this;
  }
  get empty() { return this.segs.length === 0; }
  paths() { return this.segs.map((sg, i) => html`<path key=${i} fill=${sg.c} d=${sg.d.join("")}/>`); }
}

// warstwy rysunku w kolejności tworzenia; każda może mieć klasę animacji
class Layers {
  constructor(ox = 0, oy = 0) { this.ox = ox; this.oy = oy; this.list = []; this.by = new Map(); }
  get(name, cls = "", style = null) {
    let l = this.by.get(name);
    if (!l) { l = { cls, style, g: new Pix(this.ox, this.oy) }; this.by.set(name, l); this.list.push(l); }
    return l.g;
  }
  insert(node) { this.list.push({ node }); }
  render() {
    return this.list.filter((l) => l.node || !l.g.empty).map((l, i) => l.node
      ? html`<g key=${i}>${l.node}</g>`
      : html`<g key=${i} class=${l.cls || null} style=${l.style}>${l.g.paths()}</g>`);
  }
}

function shade(hex, t) {
  const n = parseInt(hex.slice(1), 16);
  const f = (v) => Math.max(0, Math.min(255, Math.round(t < 0 ? v * (1 + t) : v + (255 - v) * t)));
  return "#" + [n >> 16, (n >> 8) & 255, n & 255].map((v) => f(v).toString(16).padStart(2, "0")).join("");
}
function rng(seed) { let s = seed >>> 0; return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296); }

// ------------------------------------------------------------------ pokoje i postacie

// Motywy pokoi (klucze = fleetlib.HQ_ROOMS). fig: [x postaci w % szerokości, czubek głowy w % wysokości],
// bubble: strona dymka. Kolory: ściana, wzór ściany, boki, sufit, podłoga (2 odcienie), listwy.
const ROOMS = {
  bridge:   { fig: [50, 22], bubble: "side", wall: "#232B36", wall2: "#2C3643", side: "#1A2029", ceil: "#141A22", floor: "#1C232D", floor2: "#212935", trim: "#0F141B", wallType: "panels", floorType: "grid" },
  study:    { fig: [68, 50], wall: "#1F4D3A", wall2: "#255A44", side: "#183F30", ceil: "#133325", floor: "#6B4426", floor2: "#5E3B20", trim: "#3E2614", wallType: "stripes", floorType: "planks" },
  devlab:   { fig: [63, 44], bubble: "left", wall: "#1F4F9E", wall2: "#1A4488", side: "#183E7C", ceil: "#143670", floor: "#C9D1DA", floor2: "#BCC5CF", trim: "#10306A", wallType: "panels", floorType: "checker" },
  filmstudio: { fig: [60, 46], bubble: "left", wall: "#2E2A3A", wall2: "#262233", side: "#231F30", ceil: "#1C1927", floor: "#4A3B32", floor2: "#42342C", trim: "#16131E", wallType: "foam", floorType: "planks" },
  atelier:  { fig: [55, 48], wall: "#C2507A", wall2: "#AD4469", side: "#9C3D61", ceil: "#8A3556", floor: "#D9BF8F", floor2: "#CDB07E", trim: "#7E2E4E", wallType: "bricks", floorType: "planks" },
  workshop: { fig: [35, 46], wall: "#C96A22", wall2: "#B25B18", side: "#A9571B", ceil: "#944C16", floor: "#8F979F", floor2: "#838B93", trim: "#6E3A10", wallType: "ribs", floorType: "concrete" },
  office:   { fig: [54, 44], bubble: "left", wall: "#26303F", wall2: "#212A38", side: "#1C2430", ceil: "#171E28", floor: "#333C4A", floor2: "#2D3542", trim: "#12171F", wallType: "panels", floorType: "grid" },
  radar:    { fig: [60, 44], bubble: "left", wall: "#1B2E2C", wall2: "#203634", side: "#162624", ceil: "#11201E", floor: "#2E3D3B", floor2: "#283634", trim: "#0D1816", wallType: "panels", floorType: "grid" },
};
const STORAGE = { wall: "#3A414C", wall2: "#343B45", side: "#2E343D", ceil: "#272C34", floor: "#5A6068", floor2: "#535960", trim: "#22272E", wallType: "panels", floorType: "concrete" };

const SKIN = "#F2CD37", SKIN2 = "#D9B21E", INK = "#15171C";
const LOOKS = {
  boss:     { coat: "#1D2129", coat2: "#111419", pants: "#1D2129", shoes: "#08090B", hair: "#17120E", hairStyle: "slick", outfit: "suit", tie: "#C62828", shirt: "#F1F3F5" },
  study:    { coat: "#6B4A2E", coat2: "#523820", pants: "#3B2F25", shoes: "#241A12", hair: "#4A3020", hat: "deerstalker", hatC: "#A07C4C", hatC2: "#7A5C36", outfit: "scarf", accent: "#C9A26B" },
  devlab:   { coat: "#27406A", coat2: "#1B2E4E", pants: "#2B2F36", shoes: "#EDEFF2", hair: "#3A2418", hairStyle: "messy", outfit: "hoodie", phones: "#1FB6A6" },
  atelier:  { coat: "#F4F4F2", coat2: "#D8D8D2", pants: "#3B3F8C", shoes: "#1E1E24", hair: "#6B3A1E", hat: "beret", hatC: "#B0306A", hatC2: "#8C2455", outfit: "stripes", accent: "#1E1E24" },
  filmstudio: { coat: "#2B2B33", coat2: "#1E1E24", pants: "#3E4A5C", shoes: "#1A1A1F", hair: "#2A1C14", hat: "cap", hatC: "#D62D20", hatC2: "#A51F16", outfit: "vest", vest: "#8C7A55", vest2: "#6E5F40" },
  workshop: { coat: "#D9661F", coat2: "#B85414", pants: "#2F5D9E", shoes: "#3A2A1A", hair: "#3A2A1A", hat: "hardhat", hatC: "#F2B01E", hatC2: "#C98E0E", outfit: "overalls" },
  office:   { coat: "#5A6472", coat2: "#454E5A", pants: "#2E3440", shoes: "#15171C", hair: "#6B4226", hairStyle: "short", outfit: "tie", tie: "#2C6ED5", shirt: "#F1F3F5" },
  radar:    { coat: "#4B5B34", coat2: "#3A4728", pants: "#2E3440", shoes: "#15171C", hair: "#5A3A22", hat: "cap", hatC: "#F26B1D", hatC2: "#C9540F", outfit: "vest", vest: "#F26B1D", vest2: "#C9540F", phones: "#1FB6A6" },
};

const STATUS_PX = { working: "#3DDC84", judging: "#3DDC84", blocked: "#FF4D3D", review: "#FFC53D", queued: "#5AA9FF", idle: "#56606E", offline: "#3A414C" };
const isBusy = (s) => s === "working" || s === "judging";

function figHair(g, x, hy, k, facing) {
  if (k.hat) return;
  const h = k.hair;
  if (facing === "back") {
    g.r(x - 4, hy - 1, 8, 7, h);
    if (k.hairStyle === "messy") { g.r(x - 5, hy - 2, 10, 5, h); [-4, -1, 2].forEach((d) => g.p(x + d, hy - 3, h)); }
    g.r(x - 4, hy + 5, 8, 1, shade(h, -0.3));
    return;
  }
  if (k.hairStyle === "slick") {
    g.r(x - 4, hy - 1, 8, 2, h); g.r(x - 4, hy + 1, 1, 2, h); g.r(x + 3, hy + 1, 1, 1, h);
    g.p(x - 1, hy - 1, shade(h, 0.3)); g.r(x - 3, hy - 2, 6, 1, h);
  } else if (k.hairStyle === "messy") {
    g.r(x - 4, hy - 2, 8, 3, h); [-4, -1, 2].forEach((d) => g.p(x + d, hy - 3, h));
    g.r(x - 5, hy, 1, 3, h); g.r(x + 4, hy, 1, 3, h); g.p(x - 3, hy + 1, h); g.p(x, hy + 1, h);
  } else {
    g.r(x - 4, hy - 1, 8, 2, h); g.p(x - 4, hy + 1, h); g.p(x + 3, hy + 1, h);
  }
}

function figHat(g, x, hy, k, facing) {
  if (k.hat === "deerstalker") {
    g.r(x - 5, hy - 2, 10, 4, k.hatC);
    for (let j = 0; j < 4; j++) for (let i = (j % 2); i < 10; i += 2) g.p(x - 5 + i, hy - 2 + j, k.hatC2);
    g.p(x, hy - 3, k.hatC2); g.r(x - 6, hy + 1, 1, 3, k.hatC2); g.r(x + 5, hy + 1, 1, 3, k.hatC2);
    if (facing === "front") g.r(x - 3, hy + 2, 6, 1, k.hatC2);
  } else if (k.hat === "beret") {
    g.r(x - 5, hy - 2, 11, 2, k.hatC); g.r(x - 4, hy - 3, 8, 1, k.hatC); g.p(x + 5, hy - 1, k.hatC2);
    g.p(x, hy - 4, k.hatC2); g.r(x - 5, hy, 10, 1, k.hatC2);
  } else if (k.hat === "cap") {   // daszkiem do tyłu: z przodu widać pasek regulacji
    g.r(x - 4, hy - 3, 8, 3, k.hatC); g.r(x - 5, hy - 1, 10, 2, k.hatC); g.r(x - 2, hy - 3, 3, 1, shade(k.hatC, 0.3));
    if (facing === "back") g.r(x - 3, hy + 1, 7, 1, k.hatC2);
    else { g.r(x - 1, hy, 3, 1, k.hatC2); g.p(x, hy - 4, k.hatC2); }
    g.r(x - 5, hy + 1, 1, 3, k.hair); g.r(x + 4, hy + 1, 1, 3, k.hair);
  } else if (k.hat === "hardhat") {
    g.r(x - 4, hy - 3, 8, 3, k.hatC); g.r(x - 5, hy - 1, 10, 1, k.hatC); g.r(x - 6, hy, 12, 1, k.hatC2);
    g.r(x - 3, hy - 3, 2, 1, shade(k.hatC, 0.4)); g.r(x - 1, hy - 3, 2, 3, k.hatC2);
  }
  if (k.phones) {
    g.r(x - 5, hy - 3, 10, 1, k.phones); g.r(x - 6, hy - 2, 1, 3, k.phones); g.r(x + 5, hy - 2, 1, 3, k.phones);
    g.r(x - 6, hy + 1, 2, 3, k.phones); g.r(x + 4, hy + 1, 2, 3, k.phones); g.p(x - 6, hy + 1, shade(k.phones, 0.35));
  }
}

function figOutfit(g, x, y, k, facing) {
  const o = k.outfit;
  if (facing === "back") {
    if (o === "suit") { g.r(x - 2, y - 17, 4, 1, k.shirt); g.r(x, y - 12, 1, 4, k.coat2); }
    if (o === "scarf") { g.r(x - 4, y - 17, 8, 2, k.accent); g.r(x - 5, y - 8, 10, 3, k.coat); g.r(x - 5, y - 10, 10, 1, k.coat2); }
    if (o === "hoodie") g.r(x - 4, y - 17, 8, 3, k.coat2);
    if (o === "stripes") [16, 14, 12, 10].forEach((d) => g.r(x - 5, y - d, 10, 1, k.accent));
    if (o === "overalls") { g.r(x - 3, y - 17, 1, 5, k.pants); g.r(x + 2, y - 17, 1, 5, k.pants); g.r(x - 5, y - 12, 10, 4, k.pants); }
    if (o === "tie") g.r(x - 2, y - 17, 4, 1, k.shirt);
    if (o === "vest") { g.r(x - 5, y - 17, 10, 9, k.vest); g.r(x - 5, y - 17, 10, 1, k.vest2); }
    return;
  }
  if (o === "suit") {
    g.r(x - 2, y - 17, 4, 2, k.shirt); g.r(x - 1, y - 15, 2, 2, k.shirt);
    g.r(x - 1, y - 17, 2, 1, shade(k.tie, -0.25)); g.r(x - 1, y - 16, 2, 6, k.tie);
    g.p(x - 3, y - 16, k.coat2); g.p(x + 2, y - 16, k.coat2); g.p(x + 3, y - 14, k.shirt);
    g.p(x - 3, y - 11, k.coat2); g.p(x - 3, y - 13, k.coat2);
  } else if (o === "scarf") {
    g.r(x - 5, y - 8, 10, 3, k.coat); g.r(x - 5, y - 10, 10, 1, k.coat2); g.r(x, y - 10, 1, 6, k.coat2);
    g.r(x - 4, y - 17, 8, 2, k.accent); g.r(x + 1, y - 15, 2, 4, k.accent); g.r(x + 1, y - 11, 2, 1, shade(k.accent, -0.25));
  } else if (o === "hoodie") {
    g.r(x - 4, y - 17, 8, 1, k.coat2); g.r(x - 3, y - 12, 6, 3, k.coat2);
    g.r(x - 2, y - 16, 1, 3, "#EDEFF2"); g.r(x + 1, y - 16, 1, 3, "#EDEFF2");
  } else if (o === "stripes") {
    [16, 14, 12, 10].forEach((d) => g.r(x - 5, y - d, 10, 1, k.accent));
  } else if (o === "overalls") {
    g.r(x - 3, y - 14, 6, 6, k.pants); g.r(x - 4, y - 17, 1, 3, k.pants); g.r(x + 3, y - 17, 1, 3, k.pants);
    g.p(x - 3, y - 14, "#F2B01E"); g.p(x + 2, y - 14, "#F2B01E"); g.r(x - 1, y - 12, 2, 2, shade(k.pants, -0.25));
  } else if (o === "tie") {
    g.r(x - 1, y - 17, 2, 1, k.shirt); g.r(x - 1, y - 16, 2, 5, k.tie);
  } else if (o === "vest") {
    g.r(x - 5, y - 17, 3, 9, k.vest); g.r(x + 2, y - 17, 3, 9, k.vest);
    g.r(x - 5, y - 13, 2, 2, k.vest2); g.r(x + 3, y - 13, 2, 2, k.vest2); g.p(x - 4, y - 16, k.vest2); g.p(x + 3, y - 16, k.vest2);
  }
}

// Postać-minifigurka (27 px). (x, y) = środek stóp. pose: rest | type | raise | hold | hammer; item: magnifier | palette | clipboard | camera | clipper
function drawFigure(L, id, x, y, look, o = {}) {
  const k = LOOKS[look] || LOOKS.office;
  const facing = o.facing || "front";
  const pose = o.pose || "rest";
  const sleep = !!o.sleep;
  const busy = !!o.busy;
  const hy = y - 26 + (sleep ? 1 : 0);
  const body = L.get(`${id}-body`);
  body.r(x - 7, y, 14, 1, "rgba(0,0,0,.3)");
  if (o.legs !== false) {
    body.r(x - 5, y - 8, 10, 2, k.pants);
    body.r(x - 5, y - 6, 4, 5, k.pants); body.r(x + 1, y - 6, 4, 5, k.pants); body.r(x + 3, y - 6, 1, 5, shade(k.pants, -0.25));
    body.r(x - 5, y - 1, 4, 1, k.shoes); body.r(x + 1, y - 1, 4, 1, k.shoes);
  }
  body.r(x - 5, y - 17, 10, 9, k.coat); body.r(x + 4, y - 17, 1, 9, k.coat2);
  figOutfit(body, x, y, k, facing);
  body.r(x - 1, y - 18, 2, 1, SKIN2);

  const head = L.get(`${id}-head`, busy ? "thq-px-bob" : "");
  head.r(x - 4, hy, 8, 8, SKIN); head.r(x + 3, hy, 1, 8, SKIN2); head.r(x - 2, hy - 1, 4, 1, SKIN2);
  if (facing === "front") {
    if (sleep) { head.r(x - 3, hy + 4, 2, 1, INK); head.r(x + 1, hy + 4, 2, 1, INK); }
    else { head.p(x - 2, hy + 3, INK); head.p(x + 1, hy + 3, INK); }
    if (o.worried) head.r(x - 1, hy + 6, 2, 1, INK);
    else { head.p(x - 2, hy + 5, INK); head.r(x - 1, hy + 6, 2, 1, INK); head.p(x + 1, hy + 5, INK); }
  }
  figHair(head, x, hy, k, facing);
  figHat(head, x, hy, k, facing);
  if (facing === "front" && !sleep) L.get(`${id}-lid`, "thq-px-lid").r(x - 2, hy + 3, 1, 1, SKIN).r(x + 1, hy + 3, 1, 1, SKIN);

  const armL = L.get(`${id}-armL`, busy && (pose === "type") ? "thq-px-tap" : "");
  const armR = L.get(`${id}-armR`, busy && (pose === "type" || pose === "hold") ? "thq-px-tap2" : "");
  const sleeve = k.coat, sleeve2 = k.coat2;
  const restL = () => armL.r(x - 7, y - 17, 2, 7, sleeve).r(x - 7, y - 10, 2, 2, SKIN);
  const restR = () => armR.r(x + 5, y - 17, 2, 7, sleeve).r(x + 6, y - 17, 1, 7, sleeve2).r(x + 5, y - 10, 2, 2, SKIN);
  if (pose === "type" && facing === "back") {
    armL.r(x - 7, y - 16, 2, 4, sleeve); armR.r(x + 5, y - 16, 2, 4, sleeve);
  } else if (pose === "type") {
    armL.r(x - 7, y - 17, 2, 5, sleeve).r(x - 6, y - 12, 2, 2, SKIN);
    armR.r(x + 5, y - 17, 2, 5, sleeve).r(x + 4, y - 12, 2, 2, SKIN);
  } else if (pose === "raise") {
    restL(); armR.r(x + 5, y - 24, 2, 8, sleeve).r(x + 5, y - 26, 2, 2, SKIN);
  } else if (pose === "hammer") {
    restL();
    if (busy) {
      L.get(`${id}-f1`, "thq-px-f1").r(x + 5, y - 22, 2, 6, sleeve).r(x + 5, y - 24, 2, 2, SKIN).r(x + 4, y - 27, 1, 5, "#9AA3AE").r(x + 3, y - 28, 3, 2, "#9AA3AE");
      L.get(`${id}-f2`, "thq-px-f2").r(x + 5, y - 17, 2, 5, sleeve).r(x + 4, y - 12, 2, 2, SKIN).r(x + 1, y - 12, 3, 1, "#9AA3AE").r(x + 0, y - 13, 2, 3, "#9AA3AE");
    } else restR();
  } else if (pose === "hold") {
    restL();
    armR.r(x + 5, y - 17, 2, 4, sleeve).r(x + 4, y - 13, 2, 2, SKIN);
    const it = o.item;
    if (it === "magnifier") {
      armR.r(x + 6, y - 15, 1, 3, "#5A3A22");
      armR.r(x + 7, y - 20, 1, 3, "#C9A24C").r(x + 11, y - 20, 1, 3, "#C9A24C").r(x + 8, y - 21, 3, 1, "#C9A24C").r(x + 8, y - 17, 3, 1, "#C9A24C").r(x + 8, y - 20, 3, 3, "#BFE3F2");
    } else if (it === "palette") {
      armR.r(x + 3, y - 12, 7, 3, "#D9B887").p(x + 4, y - 12, "#E63946").p(x + 6, y - 12, "#2A9D8F").p(x + 8, y - 11, "#F4A261").p(x + 5, y - 10, "#264653");
      armL.r(x - 8, y - 13, 1, 4, "#8A5A33").p(x - 8, y - 14, "#E63946");
    } else if (it === "camera") {
      armR.r(x + 3, y - 18, 8, 5, "#23272E").r(x + 11, y - 17, 2, 3, "#3A404A").p(x + 12, y - 16, "#6D8BB0").r(x + 5, y - 20, 4, 2, "#23272E");
      L.get(`${id}-rec`, o.busy ? "thq-px-rec is-on" : "thq-px-rec").p(x + 4, y - 17, "#FF3B30");
    } else if (it === "clipper") {
      armR.r(x + 3, y - 15, 8, 6, "#15171C").r(x + 3, y - 17, 8, 2, "#EDEFF2");
      for (let i = 0; i < 8; i += 2) armR.p(x + 3 + i, y - 17, "#15171C").p(x + 4 + i, y - 16, "#15171C");
      armR.r(x + 4, y - 13, 5, 1, "#8A94A3");
    } else if (it === "clipboard") {
      armR.r(x + 3, y - 15, 6, 7, "#8A5A33").r(x + 4, y - 14, 4, 5, "#FFFFFF").r(x + 4, y - 13, 3, 1, "#8A94A3").r(x + 4, y - 11, 3, 1, "#8A94A3").r(x + 5, y - 16, 2, 1, "#C9A24C");
    }
  } else {
    restL(); restR();
  }
  if (sleep) {
    ["thq-px-z thq-px-z1", "thq-px-z thq-px-z2", "thq-px-z thq-px-z3"].forEach((cls, i) =>
      L.get(`${id}-z${i}`, cls).text(x + 5 + i * 3, hy - 4 - i * 5, "Z", "#E4E9EF"));
  }
  if (o.alert) L.get(`${id}-alert`, "thq-px-blink").text(x - 1, hy - 9, "!", "#FF4D3D").r(x - 2, hy - 10, 5, 1, "#FF4D3D");
}

// Jarvo: robot-monolit (cztery płyty i pasek wyświetlacza); pracuje, gdy flota pracuje
function drawRobot(L, x, y, state) {
  const g = L.get("robot");
  g.r(x - 14, y, 30, 1, "rgba(0,0,0,.35)");
  [-12, -6, 0, 6].forEach((dx) => {
    const sx = x + dx;
    g.r(sx, y - 34, 5, 34, "#9AA4B0"); g.r(sx, y - 34, 1, 34, "#C2CAD3"); g.r(sx + 4, y - 34, 1, 34, "#6E7884");
    g.r(sx, y - 20, 5, 1, "#7C8692"); g.r(sx, y - 10, 5, 1, "#7C8692");
  });
  g.r(x - 12, y - 30, 23, 5, "#0D1117");
  if (state === "blocked") L.get("robot-screen", "thq-px-blink").text(x - 1, y - 30, "!", "#FF4D3D");
  else {
    const bars = L.get("robot-bars", state === "working" ? "thq-px-eq" : "");
    for (let i = 0; i < 7; i++) bars.r(x - 11 + i * 3, y - 29, 2, 3, state === "working" ? (i % 2 ? "#7CF0B4" : "#3DDC84") : "#3A4452");
  }
}

// ------------------------------------------------------------------ skorupa pokoju (2.5D)

const CREW_GEO = { d: 10, dt: 5, db: 12 };
const BRIDGE_GEO = { d: 14, dt: 6, db: 14 };

function drawShell(g, w, h, t, geo) {
  const { d, dt, db } = geo;
  g.r(0, 0, w, h, t.side);
  g.r(0, 0, 2, h, shade(t.side, -0.25)); g.r(w - 2, 0, 2, h, shade(t.side, -0.25));
  for (let i = 0; i < dt; i++) { const ins = Math.round((i / dt) * d); g.r(ins, i, w - 2 * ins, 1, i === dt - 1 ? shade(t.ceil, -0.2) : t.ceil); }
  for (let i = 0; i < db; i++) {
    const ins = Math.round((i / db) * d), yy = h - 1 - i, x0 = ins, x1 = w - ins;
    g.r(x0, yy, x1 - x0, 1, t.floor);
    if (t.floorType === "planks") { if (Math.floor(i / 2) % 2) g.r(x0, yy, x1 - x0, 1, t.floor2); for (let x = x0 + ((i >> 1) % 2 ? 5 : 11); x < x1; x += 16) g.p(x, yy, shade(t.floor, -0.3)); }
    else if (t.floorType === "checker") { for (let x = x0 + (((i >> 1) % 2) ? 4 : 0) - (x0 % 8); x < x1; x += 8) g.r(Math.max(x, x0), yy, Math.min(4, x1 - Math.max(x, x0)), 1, t.floor2); }
    else if (t.floorType === "grid") { if (i % 3 === 0) g.r(x0, yy, x1 - x0, 1, t.floor2); for (let x = x0 + 6; x < x1; x += 10) g.p(x, yy, t.floor2); }
    else { const rnd = rng(i * 97 + w); for (let x = x0; x < x1; x += 3) if (rnd() < 0.18) g.p(x, yy, rnd() < 0.5 ? t.floor2 : shade(t.floor, 0.12)); }
  }
  const bx = d, by = dt, bw = w - 2 * d, bh = h - dt - db;
  g.r(bx, by, bw, bh, t.wall);
  if (t.wallType === "stripes") for (let x = bx + 2; x < bx + bw; x += 4) g.r(x, by, 1, bh, t.wall2);
  else if (t.wallType === "bricks") for (let yy = by; yy < by + bh; yy += 4) { g.r(bx, yy, bw, 1, t.wall2); for (let x = bx + ((yy / 4) % 2 ? 0 : 4); x < bx + bw; x += 8) g.r(x, yy, 1, 4, t.wall2); }
  else if (t.wallType === "foam") for (let yy = by + 1; yy < by + bh - 3; yy += 4) for (let x = bx + ((yy >> 2) % 2 ? 0 : 2); x < bx + bw - 1; x += 4) { g.r(x, yy, 2, 2, t.wall2); g.p(x, yy, shade(t.wall, 0.08)); }
  else if (t.wallType === "ribs") for (let x = bx + 1; x < bx + bw; x += 4) { g.r(x, by, 1, bh, shade(t.wall, 0.12)); g.r(x + 1, by, 1, bh, t.wall2); }
  else for (let x = bx + 15; x < bx + bw; x += 16) { g.r(x, by, 1, bh, t.wall2); for (let yy = by + 3; yy < by + bh; yy += 12) { g.p(x - 2, yy, t.wall2); g.p(x + 2, yy, t.wall2); } }
  g.r(bx, by, bw, 1, shade(t.wall, -0.3));
  g.r(bx, by + bh - 2, bw, 2, t.trim);
  g.r(bx - 1, by, 1, bh, shade(t.side, -0.35)); g.r(bx + bw, by, 1, bh, shade(t.side, -0.35));
  const lx = Math.round(w / 2);
  g.r(lx - 6, dt, 12, 1, "#2B2F36"); g.r(lx - 4, dt + 1, 8, 1, "#FFE7A8");
}

function drawLight(L, w, h, geo, on) {
  const g = L.get("light", cx("thq-px-light", on && "is-on"));
  const lx = Math.round(w / 2);
  for (let yy = geo.dt + 2; yy < h; yy++) { const half = Math.round(5 + (yy - geo.dt) * 0.85); g.r(lx - half, yy, half * 2, 1, "rgba(255,226,150,.07)"); }
}

// ------------------------------------------------------------------ wnętrza

function booksRow(g, x0, x1, yTop, yBot, seed) {
  const rnd = rng(seed), cols = ["#C0392B", "#2C3E50", "#E0B84C", "#6C8EBF", "#8E5B3C", "#3E7B5A", "#B85C8A", "#D98E32", "#EDE3CC"];
  for (let x = x0; x < x1;) { const bw = rnd() < 0.3 ? 1 : 2, bh = Math.round((yBot - yTop) * (0.6 + rnd() * 0.4)); g.r(x, yBot - bh, bw, bh, cols[Math.floor(rnd() * cols.length)]); x += bw + (rnd() < 0.15 ? 1 : 0); }
}

function roomStudy(L, a, queue) {
  const g = L.get("props"), st = a.status;
  g.r(10, 44, 110, 14, "#4A2E18"); g.r(10, 44, 110, 1, "#6E4628");
  for (let x = 14; x < 116; x += 26) g.r(x, 47, 20, 8, "#553418");
  g.r(13, 10, 24, 48, "#4A2E18"); g.r(15, 12, 20, 44, "#24160B");
  [[12, 21], [23, 32], [34, 43], [45, 55]].forEach(([t, b], i) => { booksRow(g, 15, 35, t, b, 11 + i); g.r(15, b, 20, 1, "#6E4628"); });
  g.r(44, 12, 36, 24, "#5A3A22"); g.r(45, 13, 34, 22, "#B08450");
  const rnd = rng(7); for (let i = 0; i < 40; i++) g.p(45 + Math.floor(rnd() * 34), 13 + Math.floor(rnd() * 22), "#9C7244");
  g.r(47, 15, 7, 5, "#F4EEDC"); g.r(58, 14, 7, 6, "#FFF3C4"); g.r(70, 16, 6, 5, "#FFFFFF"); g.r(49, 25, 7, 7, "#8A94A3"); g.r(50, 26, 5, 3, "#C9D3DE");
  g.r(62, 26, 8, 6, "#F4EEDC"); g.r(71, 25, 6, 7, "#E6F0FF");
  const pins = [[50, 16], [61, 15], [73, 17], [52, 26], [66, 27], [74, 26]];
  const s = L.get("strings");
  [[0, 4], [4, 2], [1, 3], [3, 5], [2, 5]].forEach(([p, q]) => s.line(pins[p][0], pins[p][1], pins[q][0], pins[q][1], "#D62D20"));
  pins.forEach(([px, py]) => s.p(px, py, "#FF3B30"));
  g.circle(101, 17, 4, "#6E4628"); g.circle(101, 17, 3, "#EDE3CC"); g.r(101, 14, 1, 3, INK); g.r(101, 17, 2, 1, INK);
  g.r(40, 62, 52, 5, "#6E1F1F"); g.r(42, 63, 48, 3, "#8A2A2A"); g.r(44, 64, 44, 1, "#C9A24C");
  g.r(46, 57, 1, 6, "#6E4628"); g.r(44, 63, 5, 1, "#553418"); g.circle(46, 53, 4, "#3E7BB0"); g.r(44, 51, 3, 2, "#4E9A5A"); g.r(46, 55, 3, 1, "#4E9A5A");
  const ch = L.get("chair");
  ch.r(80, 39, 17, 18, "#7A2E2E"); ch.r(81, 38, 15, 1, "#7A2E2E"); ch.r(82, 40, 2, 15, "#9A3E3E"); ch.r(78, 47, 3, 10, "#662424"); ch.r(96, 47, 3, 10, "#662424");
  const lookup = { working: { pose: "hold", item: "magnifier" }, judging: { pose: "hold", item: "magnifier" }, review: { pose: "hold", item: "clipboard" }, blocked: { pose: "raise", alert: true, worried: true } };
  drawFigure(L, "fig", 88, 64, "study", { busy: isBusy(st), sleep: st === "idle", ...(lookup[st] || {}) });
  const d = L.get("desk");
  d.r(64, 50, 52, 3, "#6E4628"); d.r(64, 50, 52, 1, "#8A5A33"); d.r(66, 53, 48, 11, "#553418"); d.r(68, 56, 20, 1, "#46290F"); d.r(92, 56, 20, 1, "#46290F");
  d.p(78, 58, "#C9A24C"); d.p(102, 58, "#C9A24C"); d.r(66, 64, 3, 2, "#3E2614"); d.r(111, 64, 3, 2, "#3E2614");
  for (let i = 0; i < Math.min(queue, 6); i++) d.r(70, 49 - i, 10, 1, i % 2 ? "#F4EEDC" : "#FFFFFF");
  d.r(104, 43, 8, 3, "#2E7D4F"); d.r(104, 43, 8, 1, "#3E9A62"); d.r(107, 46, 1, 4, "#C9A24C"); d.r(105, 49, 5, 1, "#C9A24C");
  const glow = L.get("lamp-glow", cx("thq-px-glow", isBusy(st) && "is-on"));
  for (let j = 0; j < 5; j++) glow.r(103 - j, 46 + j, 10 + 2 * j, 1, "rgba(255,227,154,.28)");
  if (!isBusy(st)) { d.r(94, 48, 1, 2, "#5A3A22"); d.r(93, 45, 3, 3, "#C9A24C"); d.p(94, 46, "#BFE3F2"); }
}

function roomDevlab(L, a) {
  const g = L.get("props"), st = a.status, on = isBusy(st);
  g.r(13, 18, 14, 40, "#20252D"); g.r(14, 19, 12, 38, "#12161C");
  for (let i = 0; i < 9; i++) { g.r(15, 20 + i * 4, 10, 3, "#2B313A"); g.r(22, 21 + i * 4, 2, 1, "#10141A"); }
  const led1 = L.get("leds1", "thq-px-led1"), led2 = L.get("leds2", "thq-px-led2");
  for (let i = 0; i < 9; i++) { (i % 2 ? led1 : led2).p(16, 21 + i * 4, i % 3 ? "#3DDC84" : "#FFC53D"); (i % 2 ? led2 : led1).p(18, 21 + i * 4, "#3DDC84"); }
  g.r(32, 11, 34, 20, "#9AA4B0"); g.r(33, 12, 32, 18, "#F4F7FA"); g.r(35, 14, 28, 3, "#C9D8EE"); g.r(35, 19, 12, 9, "#DCE6F3");
  g.r(49, 19, 14, 4, "#DCE6F3"); g.r(49, 24, 14, 4, "#DCE6F3"); g.line(37, 21, 44, 26, "#E05A4F"); g.r(40, 30, 16, 1, "#7C8692");
  L.get("neon", cx("thq-px-neon", on && "is-on")).text(74, 12, "</>", "#7FF3FF", 2);
  g.r(62, 44, 56, 2, "#E9EDF2"); g.r(62, 46, 56, 1, "#AEB7C2"); g.r(64, 47, 2, 11, "#AEB7C2"); g.r(114, 47, 2, 11, "#AEB7C2");
  const code = [[0, 12, "#7FB4FF"], [2, 9, "#FFD36E"], [2, 13, "#9BE3A7"], [4, 7, "#FF9BB0"], [2, 11, "#7FB4FF"]];
  const f1 = L.get("code1", on ? "thq-px-f1" : "thq-px-off", { "--thq-d": "1.1s" }), f2 = on ? L.get("code2", "thq-px-f2", { "--thq-d": "1.1s" }) : null;
  [68, 92].forEach((mx, m) => {
    g.r(mx, 29, 20, 14, "#1D232C"); g.r(mx + 1, 30, 18, 11, "#0B0F15"); g.r(mx + 9, 43, 2, 1, "#2A313B");
    code.forEach(([ix, w, c], i) => f1.r(mx + 2 + ix, 31 + i * 2, Math.min(w, 16 - ix), 1, c));
    if (f2) code.forEach(([ix, w, c], i) => f2.r(mx + 2 + ((ix + 2 + m) % 5), 31 + i * 2, Math.min(w - 3 + i, 15), 1, code[(i + 2) % 5][2]));
  });
  g.r(76, 43, 14, 1, "#3A424D"); g.r(106, 40, 3, 4, "#FFFFFF"); g.p(109, 41, "#FFFFFF");
  if (on) L.get("steam", "thq-px-f1", { "--thq-d": "1.4s" }).p(107, 38, "#E8EEF6").p(108, 36, "#E8EEF6").p(107, 34, "#E8EEF6");
  g.r(111, 52, 6, 6, "#C8693C"); g.r(111, 52, 6, 1, "#A8552C"); g.r(110, 45, 3, 7, "#2F8F4E"); g.r(114, 42, 3, 10, "#3AA85C"); g.r(117, 46, 2, 6, "#2F8F4E");
  const lookup = { working: { pose: "type" }, judging: { pose: "type" }, blocked: { pose: "raise", alert: true } };
  drawFigure(L, "fig", 82, 60, "devlab", { facing: "back", legs: false, busy: on, sleep: st === "idle", ...(lookup[st] || {}) });
  const c = L.get("chair");
  c.r(76, 46, 13, 9, "#2D3440"); c.r(77, 45, 11, 1, "#2D3440"); c.r(77, 47, 11, 1, "#3A4350"); c.r(81, 55, 3, 4, "#555E6B"); c.r(76, 59, 13, 1, "#555E6B");
  c.p(76, 60, INK); c.p(82, 60, INK); c.p(88, 60, INK);
}

function roomAtelier(L, a) {
  const g = L.get("props"), st = a.status, on = isBusy(st);
  g.r(58, 7, 44, 2, "#6E747D"); g.r(60, 9, 40, 49, "#3AA6A0"); g.r(99, 9, 1, 49, "#2E8A85"); g.r(60, 50, 40, 8, "#43B3AC");
  g.r(60, 58, 40, 5, "#4CBDB6"); g.r(60, 62, 40, 1, "#2E8A85");
  g.r(24, 29, 1, 29, "#3A3F48"); g.line(24, 50, 19, 58, "#3A3F48"); g.line(24, 50, 29, 58, "#3A3F48");
  g.r(16, 14, 17, 15, "#2A2F37"); g.r(17, 15, 15, 13, "#EDF1F5"); g.r(17, 15, 15, 1, "#FFFFFF");
  const glow = L.get("soft-glow", cx("thq-px-glow", on && "is-on"));
  for (let j = 0; j < 30; j++) glow.r(32 + j, 16 + Math.round(j * 0.25), 1, 12 + Math.round(j * 0.6), "rgba(255,243,196,.10)");
  g.r(40, 24, 1, 34, "#8A5A33"); g.r(51, 24, 1, 34, "#8A5A33"); g.r(45, 20, 1, 38, "#7A4E2B"); g.r(38, 40, 16, 1, "#8A5A33");
  g.r(36, 22, 20, 17, "#FFFFFF"); g.r(37, 23, 18, 15, "#F2E8D5");
  g.r(37, 23, 18, 6, "#F4A261"); g.r(37, 29, 18, 3, "#E76F51"); g.circle(46, 29, 3, "#FFD166"); g.r(37, 32, 18, 6, "#264653"); g.r(40, 34, 6, 1, "#2A9D8F");
  g.r(111, 40, 1, 18, "#3A3F48"); g.line(111, 50, 106, 58, "#3A3F48"); g.line(111, 50, 116, 58, "#3A3F48");
  g.r(104, 32, 12, 8, "#23272E"); g.r(100, 34, 4, 4, "#3A404A"); g.p(101, 35, "#6D8BB0"); g.r(107, 30, 4, 2, "#23272E");
  L.get("rec", cx("thq-px-rec", on && "is-on")).r(114, 33, 1, 1, "#FF3B30");
  g.r(104, 11, 13, 17, "#1E1E24"); g.r(105, 12, 11, 15, "#E9C46A"); g.text(106, 14, "TAR", "#1E1E24"); g.r(106, 21, 9, 4, "#B0306A");
  g.r(18, 62, 9, 4, "#23272E"); g.r(18, 60, 9, 2, "#FFFFFF"); g.p(20, 60, "#23272E"); g.p(23, 60, "#23272E"); g.p(26, 60, "#23272E");
  const lookup = { working: { pose: "hold", item: "palette" }, judging: { pose: "hold", item: "palette" }, review: { pose: "hold", item: "clipboard" }, blocked: { pose: "raise", alert: true, worried: true } };
  drawFigure(L, "fig", 72, 64, "atelier", { busy: on, sleep: st === "idle", ...(lookup[st] || {}) });
}

function roomWorkshop(L, a, queue) {
  const g = L.get("props"), st = a.status, on = isBusy(st);
  g.r(14, 10, 40, 22, "#CFA56A"); g.r(14, 10, 40, 1, "#E0B97E");
  for (let x = 16; x < 54; x += 4) for (let y = 12; y < 32; y += 4) g.p(x, y, "#8A6A3C");
  g.r(18, 13, 2, 12, "#5B6470"); g.r(17, 12, 4, 2, "#5B6470"); g.p(18, 12, "#CFA56A");
  g.r(25, 15, 2, 12, "#8A5A33"); g.r(22, 13, 8, 3, "#4A515C");
  g.r(32, 13, 10, 6, "#AEB7C2"); for (let x = 32; x < 42; x += 2) g.p(x, 19, "#AEB7C2"); g.r(41, 12, 4, 4, "#C0392B");
  g.r(47, 13, 1, 8, "#C0392B"); g.r(47, 21, 1, 3, "#9AA3AE"); g.r(50, 13, 1, 8, "#2F5D9E"); g.r(50, 21, 1, 3, "#9AA3AE");
  g.r(24, 42, 56, 3, "#6B4A2D"); g.r(24, 42, 56, 1, "#8A6040"); g.r(26, 45, 3, 13, "#553A22"); g.r(75, 45, 3, 13, "#553A22"); g.r(26, 52, 52, 1, "#553A22");
  g.r(30, 38, 6, 4, "#4A515C"); g.r(29, 37, 8, 1, "#5B6470"); g.r(40, 40, 5, 2, "#9AA3AE"); g.r(47, 39, 3, 3, "#C0392B");
  g.r(62, 40, 8, 2, "#3C434D");
  const arm1 = L.get("arm1", on ? "thq-px-f1" : ""), arm2 = on ? L.get("arm2", "thq-px-f2") : null;
  arm1.r(65, 30, 2, 10, "#F2B64C").r(64, 29, 4, 2, "#3C434D").r(66, 28, 9, 2, "#F2B64C").r(75, 27, 2, 1, "#3C434D").r(75, 30, 2, 1, "#3C434D");
  if (arm2) arm2.r(65, 32, 2, 8, "#F2B64C").r(64, 31, 4, 2, "#3C434D").r(66, 33, 8, 2, "#F2B64C").r(73, 35, 1, 3, "#3C434D").r(75, 35, 1, 3, "#3C434D");
  const n = Math.max(1, Math.min(queue + 1, 6));
  [[90, 48], [105, 48], [97, 38], [90, 28], [105, 38], [97, 28]].slice(0, n).forEach(([bx, by]) => {
    g.r(bx, by, 14, 10, "#C8955A"); g.r(bx, by, 14, 2, "#B07E45"); g.r(bx + 6, by, 2, 10, "#E3C28C"); g.r(bx, by + 9, 14, 1, "#8F6436");
  });
  g.r(14, 50, 8, 10, "#2F5D9E"); g.r(14, 52, 8, 1, "#244C83"); g.r(14, 57, 8, 1, "#244C83"); g.r(14, 50, 8, 1, "#4A78B8");
  const hz = L.get("hazard"); for (let x = 2; x < 128; x += 8) { hz.r(x, 66, 4, 2, "#F5C400"); hz.r(x + 4, 66, 4, 2, "#1E1E1E"); }
  const lookup = { working: { pose: "hammer" }, judging: { pose: "hammer" }, blocked: { pose: "raise", alert: true } };
  drawFigure(L, "fig", 46, 62, "workshop", { facing: "back", busy: on, sleep: st === "idle", ...(lookup[st] || {}) });
}

// Sala operacyjna (Ads): ściana ekranów z wynikami kampanii (słupki wariantów, linia wydatków, pasek ROAS),
// biurko z dwoma monitorami i czerwony STOP. Gdy agent pracuje, monitory na biurku żyją.
function roomOffice(L, a) {
  const g = L.get("props"), st = a.status, on = isBusy(st);
  // duży ekran: słupki wariantów A–D (zwycięzca limonkowy, przegrany czerwony)
  g.r(10, 9, 44, 26, "#1D232C"); g.r(11, 10, 42, 24, "#0B0F15"); g.r(13, 12, 14, 1, "#3A4452");
  [[14, 9, "#5A6472"], [22, 14, "#5A6472"], [30, 19, "#B8FF3D"], [38, 7, "#D4213D"]].forEach(([x, h, c]) => g.r(x, 31 - h, 5, h, c));
  g.r(12, 31, 40, 1, "#3A4452");
  // drugi ekran: wydatki rosną pod czerwoną linią koperty
  g.r(58, 9, 34, 18, "#1D232C"); g.r(59, 10, 32, 16, "#0B0F15"); g.r(60, 13, 30, 1, "#D4213D");
  [[60, 23], [65, 21], [70, 22], [75, 19], [80, 18], [85, 16], [89, 15]].reduce((p, q) => (p && g.line(p[0], p[1], q[0], q[1], "#F2F1E8"), q), null);
  // tablica wyniku
  g.r(96, 9, 22, 8, "#1D232C"); g.r(97, 10, 20, 6, "#0B0F15");
  L.get("ads-ticker", cx("thq-px-neon", on && "is-on")).text(98, 11, "ROAS", "#B8FF3D");
  // biurko z dwoma monitorami
  g.r(50, 44, 60, 2, "#E9EDF2"); g.r(52, 46, 2, 12, "#AEB7C2"); g.r(106, 46, 2, 12, "#AEB7C2");
  g.r(58, 31, 18, 13, "#1D232C"); g.r(59, 32, 16, 10, on ? "#16324A" : "#0B0F15");
  g.r(78, 31, 18, 13, "#1D232C"); g.r(79, 32, 16, 10, on ? "#1E2A12" : "#0B0F15");
  if (on) {
    for (let i = 0; i < 4; i++) g.r(61, 34 + i * 2, 6 + (i * 5) % 9, 1, "#9CC3FF");
    [[81, 4], [84, 6], [87, 3], [90, 7]].forEach(([x, h]) => g.r(x, 41 - h, 2, h, "#B8FF3D"));
  }
  // czerwony STOP na biurku i roślinka
  g.r(99, 41, 5, 3, "#3A3F48"); L.get("ads-stop", cx("thq-px-rec", on && "is-on")).r(100, 40, 3, 2, "#FF3B30");
  g.r(18, 50, 6, 8, "#C8693C"); g.r(17, 42, 3, 8, "#2F8F4E"); g.r(21, 40, 3, 10, "#3AA85C");
  const lookup = { working: { pose: "type" }, judging: { pose: "type" }, blocked: { pose: "raise", alert: true } };
  drawFigure(L, "fig", 70, 60, "office", { facing: "back", legs: false, busy: on, sleep: st === "idle", ...(lookup[st] || {}) });
  const c = L.get("chair"); c.r(64, 46, 13, 9, "#2D3440"); c.r(69, 55, 3, 4, "#555E6B"); c.r(64, 59, 13, 1, "#555E6B");
}

// Radar sprzedaży (Łowca leadów): ekran radaru (wiązka i migające cele, gdy agent pracuje), mapa Polski
// z pinezkami firm, neon LEADY, biurko z listą leadów i stosem kart (kolejka).
function roomRadar(L, a, queue) {
  const g = L.get("props"), st = a.status, on = isBusy(st);
  // radar: ramka, pierścienie, krzyż
  g.circle(26, 25, 15, "#1D232C"); g.circle(26, 25, 13, "#0B2A18");
  g.circle(26, 25, 12, "#06140C"); g.circle(26, 25, 8, "#0B2A18"); g.circle(26, 25, 7, "#06140C"); g.circle(26, 25, 3, "#0B2A18"); g.circle(26, 25, 2, "#06140C");
  g.r(14, 25, 25, 1, "#12402A"); g.r(26, 13, 1, 25, "#12402A");
  const sweep = L.get("radar-sweep", cx("thq-px-holo", on && "is-on"));
  sweep.line(26, 25, 35, 16, "#7CF0B4"); sweep.line(26, 25, 36, 18, "rgba(124,240,180,.45)"); sweep.line(26, 25, 34, 15, "rgba(124,240,180,.35)");
  L.get("radar-blip1", on ? "thq-px-led1" : "thq-px-off").r(31, 19, 2, 2, "#B8FF3D");
  L.get("radar-blip2", on ? "thq-px-led2" : "thq-px-off").r(19, 30, 2, 2, "#B8FF3D").r(30, 32, 1, 1, "#7CF0B4");
  // mapa Polski na tablicy + pinezki firm
  g.r(46, 9, 40, 28, "#1D232C"); g.r(47, 10, 38, 26, "#0E1A1C");
  const kraj = [[55, 12, 20], [52, 13, 27], [50, 14, 31], [49, 16, 33], [49, 18, 34], [50, 20, 33], [50, 22, 32], [51, 24, 30], [52, 26, 28], [53, 28, 25], [55, 30, 20], [58, 32, 13]];
  kraj.forEach(([x, y, w]) => g.r(x, y, w, 2, "#2C4A46"));
  g.r(57, 12, 6, 1, "#3E6A64"); g.r(70, 12, 3, 1, "#3E6A64");
  const piny = L.get("pins", cx("thq-px-neon", on && "is-on"));
  [[58, 17], [67, 21], [74, 15], [62, 27], [76, 25], [70, 30]].forEach(([x, y]) => { piny.r(x, y, 2, 2, "#FF3B30"); piny.p(x, y + 2, "#8A1F18"); });
  // neon LEADY
  g.r(92, 9, 26, 8, "#1D232C"); g.r(93, 10, 24, 6, "#0B0F15");
  L.get("lowca-ticker", cx("thq-px-neon", on && "is-on")).text(95, 11, "LEADY", "#F26B1D");
  // biurko: monitor z listą leadów, drugi z oceną, stos kart
  g.r(50, 44, 62, 2, "#E9EDF2"); g.r(52, 46, 2, 12, "#AEB7C2"); g.r(108, 46, 2, 12, "#AEB7C2");
  g.r(58, 31, 18, 13, "#1D232C"); g.r(59, 32, 16, 10, on ? "#10262A" : "#0B0F15");
  g.r(80, 31, 18, 13, "#1D232C"); g.r(81, 32, 16, 10, on ? "#2A1A0E" : "#0B0F15");
  if (on) {
    for (let i = 0; i < 4; i++) { g.r(61, 34 + i * 2, 2, 1, "#B8FF3D"); g.r(64, 34 + i * 2, 5 + (i * 3) % 6, 1, "#9CC3FF"); }
    [[83, 7], [86, 5], [89, 4], [92, 2]].forEach(([x, h]) => g.r(x, 41 - h, 2, h, "#F26B1D"));
  }
  for (let i = 0; i < Math.min(queue, 6); i++) g.r(100, 43 - i, 8, 1, i % 2 ? "#F4EEDC" : "#FFFFFF");
  // telefon i roślinka
  g.r(38, 50, 6, 8, "#C8693C"); g.r(37, 42, 3, 8, "#2F8F4E"); g.r(41, 40, 3, 10, "#3AA85C");
  g.r(12, 58, 18, 2, "#3A3F48"); g.r(14, 55, 6, 3, "#1D232C"); g.r(15, 54, 4, 1, "#F26B1D");
  const lookup = { working: { pose: "type" }, judging: { pose: "type" }, review: { pose: "hold", item: "clipboard" }, blocked: { pose: "raise", alert: true, worried: true } };
  drawFigure(L, "fig", 72, 60, "radar", { facing: "back", legs: false, busy: on, sleep: st === "idle", ...(lookup[st] || {}) });
  const c = L.get("chair"); c.r(66, 46, 13, 9, "#2D3440"); c.r(71, 55, 3, 4, "#555E6B"); c.r(66, 59, 13, 1, "#555E6B");
}

// Studio filmowe (Wideograf): zielone tło z softboxem, kamera na statywie z lampką REC, stół montażowy
// z osią czasu (głowica przesuwa się, gdy agent pracuje), klaps i szpula na ścianie.
function roomFilmstudio(L, a) {
  const g = L.get("props"), st = a.status, on = isBusy(st);
  // green screen z łagodnym przejściem na podłogę
  g.r(14, 7, 40, 2, "#6E747D"); g.r(15, 9, 38, 49, "#2FA84F");
  for (let x = 20; x < 53; x += 7) g.r(x, 9, 1, 49, "#2A9647");
  g.r(15, 58, 38, 3, "#34B056"); g.r(14, 61, 40, 3, "#37B85A");
  // softbox na statywie (świeci na tło, gdy trwa praca)
  g.r(8, 34, 1, 30, "#3A3F48"); g.line(8, 58, 4, 64, "#3A3F48"); g.line(8, 58, 12, 64, "#3A3F48");
  g.r(2, 22, 14, 12, "#2A2F37"); g.r(3, 23, 12, 10, "#EDF1F5"); g.r(3, 23, 12, 1, "#FFFFFF");
  const glow = L.get("soft-glow", cx("thq-px-glow", on && "is-on"));
  for (let j = 0; j < 24; j++) glow.r(15 + j, 24 + Math.round(j * 0.2), 1, 10 + Math.round(j * 0.9), "rgba(255,248,220,.10)");
  // szpula filmu i lampka REC na ścianie
  g.circle(104, 14, 5, "#8A93A0"); g.circle(104, 14, 1, "#2E2A3A");
  [[-3, -2], [3, -2], [0, 3]].forEach(([dx, dy]) => g.r(104 + dx - 1, 14 + dy - 1, 2, 2, "#2E2A3A"));
  g.r(62, 11, 17, 8, "#3A1E1E"); g.r(63, 12, 15, 6, "#1A0E0E");
  L.get("rec-sign", cx("thq-px-neon", on && "is-on")).text(65, 13, "REC", "#FF4D3D");
  // kamera na statywie, obiektyw w stronę tła
  g.line(66, 47, 60, 64, "#3A3F48"); g.line(66, 47, 72, 64, "#3A3F48"); g.r(66, 47, 1, 17, "#4A515C");
  g.r(60, 39, 13, 8, "#23272E"); g.r(60, 39, 13, 1, "#3A404A"); g.r(55, 41, 5, 4, "#3A404A"); g.r(54, 42, 1, 2, "#6D8BB0");
  g.r(63, 37, 6, 2, "#23272E"); g.r(73, 40, 3, 3, "#2A2F37");
  L.get("rec", cx("thq-px-rec", on && "is-on")).r(71, 40, 1, 1, "#FF3B30");
  // stół montażowy: monitor z podglądem 9:16 i osią czasu (wideo, audio, napisy)
  g.r(84, 45, 36, 2, "#3A3F48"); g.r(84, 45, 36, 1, "#5A616C"); g.r(86, 47, 2, 12, "#2A2F37"); g.r(116, 47, 2, 12, "#2A2F37");
  g.r(87, 25, 30, 18, "#1D232C"); g.r(88, 26, 28, 15, "#0B0F15"); g.r(101, 43, 2, 2, "#2A313B");
  g.r(90, 27, 5, 8, "#E76F51"); g.r(90, 31, 5, 4, "#264653"); g.r(96, 28, 18, 1, "#3A4452"); g.r(96, 30, 12, 1, "#3A4452");
  [[90, 5, "#5AA9FF"], [96, 7, "#7CF0B4"], [104, 6, "#5AA9FF"], [111, 4, "#7CF0B4"]].forEach(([x, w, c]) => g.r(x, 36, w, 1, c));
  [[90, 21, "#FFC53D"]].forEach(([x, w, c]) => { for (let i = 0; i < w; i += 2) g.r(x + i, 38 - (i % 4 ? 1 : 0), 1, 1 + (i % 4 ? 1 : 0), c); });
  [[92, 3], [98, 4], [106, 3], [111, 3]].forEach(([x, w]) => g.r(x, 40, w, 1, "#FF8A7A"));
  const ph1 = L.get("playhead1", on ? "thq-px-f1" : "", { "--thq-d": "0.9s" }), ph2 = on ? L.get("playhead2", "thq-px-f2", { "--thq-d": "0.9s" }) : null;
  ph1.r(99, 35, 1, 6, "#FFFFFF");
  if (ph2) ph2.r(106, 35, 1, 6, "#FFFFFF");
  // klaps na stole
  g.r(104, 41, 10, 4, "#15171C"); g.r(104, 39, 10, 2, "#EDEFF2");
  for (let i = 0; i < 10; i += 3) g.r(104 + i, 39, 1, 2, "#15171C");
  g.r(105, 42, 6, 1, "#8A94A3");
  // wideograf między kamerą a stołem
  const lookup = { working: { pose: "hold", item: "camera" }, judging: { pose: "hold", item: "camera" }, review: { pose: "hold", item: "clipper" }, blocked: { pose: "raise", alert: true, worried: true } };
  drawFigure(L, "fig", 79, 64, "filmstudio", { busy: on, sleep: st === "idle", ...(lookup[st] || {}) });
}

function roomStorage(L) {
  const g = L.get("props");
  [[14, 12], [70, 12]].forEach(([sx]) => {
    g.r(sx, 12, 44, 46, "#2A2F37");
    [22, 34, 46].forEach((yy) => g.r(sx, yy, 44, 1, "#4A515C"));
    const rnd = rng(sx);
    [[13, 22], [25, 34], [37, 46], [49, 57]].forEach(([t, b]) => { for (let x = sx + 2; x < sx + 40; x += 9) if (rnd() < 0.8) { const bh = Math.min(8, b - t); g.r(x, b - bh, 8, bh, "#B07E45"); g.r(x + 3, b - bh, 2, bh, "#D4A870"); } });
  });
  g.text(52, 60, txt("MAGAZYN", "STORAGE"), "#8A93A0");
}

function roomBridge(L, a, board, crew, box) {
  const g = L.get("props"), st = a.status, on = isBusy(st);
  // okno: miasto nocą
  g.r(20, 12, 40, 40, "#3A4452"); g.r(22, 14, 36, 36, "#0A1326");
  const sk = rng(3), tw = L.get("win-stars", "thq-px-tw");
  for (let i = 0; i < 18; i++) (i % 3 ? g : tw).p(22 + Math.floor(sk() * 36), 14 + Math.floor(sk() * 18), i % 4 ? "#C9D3DE" : "#FFFFFF");
  g.circle(50, 21, 4, "#E9D8A6"); g.p(48, 20, "#CDBB86"); g.p(51, 23, "#CDBB86");
  let bx = 22;
  [10, 16, 12, 20, 9, 14, 18].forEach((hh, i) => {
    const bw = 4 + (i % 3), w = Math.min(bw, 58 - bx);
    if (w <= 0) return;
    g.r(bx, 50 - hh, w, hh, i % 2 ? "#131B30" : "#0F1628");
    for (let yy = 50 - hh + 2; yy < 49; yy += 3) for (let xx = bx + 1; xx < bx + w - 1; xx += 2) if ((xx * 7 + yy * 3 + i) % 5 === 0) g.p(xx, yy, "#F5C85A");
    bx += bw;
  });
  g.r(40, 14, 1, 36, "#3A4452"); g.r(22, 32, 36, 1, "#3A4452"); g.r(18, 52, 44, 2, "#4A5566");
  // ekran floty: kolumny tablicy kanban (kolejka, w toku, ocena, blokady)
  const frame = (x, y, w, h) => { g.r(x, y, w, h, "#3A4452"); g.r(x + 1, y + 1, w - 2, h - 2, "#0E131B"); };
  frame(65, 9, 62, 42);
  g.text(68, 12, txt("TABLICA FLOTY", "FLEET BOARD"), "#8FA3B8");
  [["ready", "#9CC3FF"], ["running", "#7CF0B4"], ["review", "#FFD36E"], ["blocked", "#FF8A7A"]].forEach(([key, color], i) => {
    const x0 = 68 + i * 14, n = (board && board[key]) || 0;
    g.r(x0, 19, 12, 1, color);
    g.text(x0, 21, String(Math.min(n, 99)), color);
    for (let j = 0; j < Math.min(n, 5); j++) g.r(x0, 28 + j * 4, 12, 3, color);
    if (n > 5) g.r(x0 + 5, 48, 3, 1, color);
  });
  // panel załogi: lampka statusu każdego agenta (7 wierszy; wyżej niż tablica floty, bo pod spodem stoi pulpit)
  frame(159, 4, 66, 52);
  g.text(162, 6, txt("ZALOGA", "CREW"), "#8FA3B8");
  crew.slice(0, 7).forEach((c, i) => {
    const color = STATUS_PX[c.status] || STATUS_PX.idle;
    (c.status === "blocked" ? L.get("crew-alarm", "thq-px-blink") : g).r(162, 14 + i * 6, 3, 3, color);
    g.text(168, 13 + i * 6, String(c.short || c.name).slice(0, 13), c.status === "idle" ? "#6E7A8A" : "#C9D3DE");
  });
  // czerwony dywan i fotel szefa
  for (let yy = 70; yy < 84; yy++) { const ins = Math.round((83 - yy) * 0.35); g.r(124 + ins, yy, 36 - 2 * ins, 1, "#7A1C22"); g.p(124 + ins, yy, "#C9A24C"); g.p(159 - ins, yy, "#C9A24C"); }
  g.r(128, 16, 28, 42, "#3A1E1E"); g.r(130, 15, 24, 1, "#3A1E1E"); g.r(131, 18, 3, 38, "#5A2E2E"); g.r(151, 18, 3, 38, "#2A1414");
  for (let yy = 20; yy < 56; yy += 7) for (let xx = 136; xx < 150; xx += 7) g.p(xx, yy, "#C9A24C");
  // roślina i flaga
  g.r(26, 68, 8, 8, "#5A3A22"); g.r(26, 68, 8, 1, "#7A5232"); g.r(24, 56, 4, 12, "#2F8F4E"); g.r(28, 52, 3, 16, "#3AA85C"); g.r(32, 58, 4, 10, "#2F8F4E"); g.r(30, 54, 2, 2, "#4CC070");
  g.r(264, 28, 1, 46, "#8A93A0"); g.r(262, 74, 5, 2, "#5A6574");
  const fl1 = L.get("flag1", "thq-px-f1", { "--thq-d": "1.6s" }), fl2 = L.get("flag2", "thq-px-f2", { "--thq-d": "1.6s" });
  fl1.r(265, 28, 12, 9, "#C62828").text(269, 30, "J", "#FFFFFF");
  fl2.r(265, 29, 12, 8, "#C62828").r(276, 28, 1, 1, "#C62828").r(265, 36, 11, 1, "#A11F1F").text(269, 30, "J", "#FFFFFF");
  // szef Jarvo: dwa razy większy od załogi, za pulpitem; robot-monolit jako ochrona
  const standing = st === "working" || st === "judging" || st === "blocked";
  const pose = st === "judging" ? { pose: "hold", item: "clipboard" } : st === "blocked" ? { pose: "raise", alert: true, worried: true } : standing ? { pose: "type" } : {};
  const BL = new Layers();
  drawFigure(BL, "boss", 0, 0, "boss", { busy: on, ...pose });
  const fy = standing ? 72 : 78;
  L.insert(html`<g transform=${`translate(${box.x + 142} ${box.y + fy}) scale(2)`}>${BL.render()}</g>`);
  const fleetWorking = crew.some((c) => isBusy(c.status)) || on;
  drawRobot(L, 244, 77, crew.some((c) => c.status === "blocked") ? "blocked" : fleetWorking ? "working" : "idle");
  // pulpit dowodzenia (przed szefem)
  const d = L.get("desk");
  d.r(104, 58, 76, 3, "#3A4350"); d.r(104, 58, 76, 1, "#6B7482"); d.r(106, 61, 72, 10, "#252C36"); d.r(106, 61, 72, 1, "#1A2029");
  d.r(112, 64, 18, 4, "#1A2029"); d.r(154, 64, 18, 4, "#1A2029"); d.r(116, 55, 8, 3, "#1E2A36"); d.r(114, 57, 12, 1, "#3A4350");
  d.r(163, 55, 3, 3, "#FFFFFF"); d.p(166, 56, "#FFFFFF"); d.r(169, 56, 7, 2, "#F1F3F5");
  const btn = L.get("buttons", "thq-px-led1");
  ["#FF6B5E", "#FFD36E", "#7CF0B4", "#9CC3FF", "#FF6B5E", "#7CF0B4"].forEach((c, i) => btn.r(111 + i * 12, 59, 3, 1, c));
  const holo = L.get("holo", cx("thq-px-holo", on && "is-on"));
  for (let j = 0; j < 12; j++) holo.r(120 - Math.round(j * 0.5) - 1, 54 - j, 2 + Math.round(j * 1), 1, "rgba(120,240,255,.22)");
  holo.circle(120, 44, 3, "rgba(120,240,255,.45)");
}

const ROOM_DRAW = { study: roomStudy, devlab: roomDevlab, atelier: roomAtelier, filmstudio: roomFilmstudio, workshop: roomWorkshop, office: roomOffice, radar: roomRadar };

function PixRoom({ box, agent, board, crew }) {
  const kind = agent.room === "bridge" ? "bridge" : ROOM_DRAW[agent.room] ? agent.room : "office";
  const t = ROOMS[kind];
  const geo = kind === "bridge" ? BRIDGE_GEO : CREW_GEO;
  const L = new Layers(box.x, box.y);
  drawShell(L.get("shell"), box.w, box.h, t, geo);
  const lit = agent.status !== "idle" && agent.status !== "offline";
  drawLight(L, box.w, box.h, geo, lit || kind === "bridge");
  const queue = (agent.counts && agent.counts.ready) || 0;
  if (kind === "bridge") roomBridge(L, agent, board, crew || [], box);
  else ROOM_DRAW[kind](L, agent, queue);
  const lamp = L.get("status-lamp", agent.status === "blocked" ? "thq-px-blink" : "");
  lamp.r(box.w - 9, 1, 6, 3, "#1A1F27").r(box.w - 8, 2, 4, 1, STATUS_PX[agent.status] || STATUS_PX.idle);
  L.get("dim", cx("thq-px-dim", !lit && kind !== "bridge" && "is-on")).r(0, 0, box.w, box.h, "#03050C");
  return html`<g class="thq-px-room">${L.render()}</g>`;
}

function StorageRoom({ box }) {
  const L = new Layers(box.x, box.y);
  drawShell(L.get("shell"), box.w, box.h, STORAGE, CREW_GEO);
  roomStorage(L);
  L.get("dim", "thq-px-dim is-on").r(0, 0, box.w, box.h, "#03050C");
  return html`<g>${L.render()}</g>`;
}

// ------------------------------------------------------------------ wieża, miasto, maszynownia

const TW = 400;
// Układ wieży we własnych współrzędnych (400 px); W ≥ 400 to szerokość sceny: nadmiar wypełnia miasto,
// a wieża stoi na środku (ox = przesunięcie). Dzięki temu scena mieści się na ekranie bez pustych pasów.
function towerLayout(crewCount, W = TW) {
  const floors = Math.max(1, Math.ceil(crewCount / 2));
  const roofY = 40, bridge = { x: 58, y: 46, w: 284, h: 84 };
  const crewY0 = bridge.y + bridge.h + 6;
  const rooms = [];
  for (let i = 0; i < floors; i++) {
    const y = crewY0 + i * 76;
    rooms.push({ x: 58, y, w: 130, h: 70 }, { x: 212, y, w: 130, h: 70 });
  }
  const baseY = crewY0 + floors * 76;
  const groundY = baseY - 6;
  const base = { x: 58, y: baseY, w: 284, h: 40 };
  const w = Math.max(TW, Math.round(W));
  // viewH: kadr widoczny (do linii ulicy, bez ziemi i piwnicy); H: pełna scena do rysowania
  return { W: w, ox: Math.round((w - TW) / 2), H: baseY + 52, viewH: groundY + 4, floors, roofY, bridge, crewY0, rooms, baseY, groundY, base,
    shaft: { x: 188, y: crewY0, w: 24, h: baseY + 40 - crewY0 } };
}

function drawSky(L, lay) {
  const g = L.get("sky");
  const bands = ["#070A18", "#0A0F22", "#0D142D", "#111A39", "#152046"];
  const bh = Math.ceil(lay.groundY / bands.length);
  const W = lay.W, mx = lay.ox + 370;
  bands.forEach((c, i) => g.r(0, i * bh, W, bh, c));
  for (let i = 1; i < bands.length; i++) for (let row = 0; row < 2; row++) for (let x = row; x < W; x += 2) g.p(x, i * bh - 1 - row, row ? bands[i - 1] : bands[i]);
  const rnd = rng(42), tw = [L.get("tw1", "thq-px-tw"), L.get("tw2", "thq-px-tw thq-px-tw2"), L.get("tw3", "thq-px-tw thq-px-tw3")];
  for (let i = 0; i < Math.round(70 * W / TW); i++) {
    const x = Math.floor(rnd() * W), y = Math.floor(rnd() * (lay.groundY - 60));
    (i % 4 === 0 ? tw[i % 3] : g).p(x, y, rnd() < 0.3 ? "#FFFFFF" : "#8C9BC4");
  }
  g.circle(mx, 21, 8, "#E9D8A6"); g.circle(mx + 4, 18, 6, bands[0]); g.p(mx - 3, 24, "#CDBB86"); g.p(mx - 5, 20, "#CDBB86");
}

function drawCity(L, lay) {
  const far = L.get("city-far"), near = L.get("city-near"), win = L.get("city-win"), blink = L.get("city-blink", "thq-px-win");
  const gy = lay.groundY;
  const rnd = rng(9);
  const block = (x0, x1, g, cMain, minH, maxH, lightP) => {
    for (let x = x0; x < x1;) {
      const bw = 8 + Math.floor(rnd() * 9), bh = minH + Math.floor(rnd() * (maxH - minH));
      const w = Math.min(bw, x1 - x);
      g.r(x, gy - bh, w, bh, cMain);
      if (rnd() < 0.3) g.r(x + Math.floor(w / 2), gy - bh - 6, 1, 6, cMain);
      for (let yy = gy - bh + 3; yy < gy - 3; yy += 4) for (let xx = x + 2; xx < x + w - 2; xx += 3) {
        const r = rnd();
        if (r < lightP) (r < lightP * 0.15 ? blink : win).r(xx, yy, 1, 2, r < lightP * 0.5 ? "#F5C85A" : "#B98E3C");
      }
      x += w + (rnd() < 0.3 ? 1 : 0);
    }
  };
  const ox = lay.ox, W = lay.W;
  block(0, ox + 58, far, "#10162B", 90, lay.groundY - 40, 0.18);
  block(ox + 342, W, far, "#10162B", 90, lay.groundY - 40, 0.18);
  block(0, ox + 50, near, "#0A0E1C", 30, 140, 0.28);
  block(ox + 350, W, near, "#0A0E1C", 30, 140, 0.28);
}

function drawGround(L, lay) {
  const g = L.get("ground"), gy = lay.groundY, W = lay.W;
  g.r(0, gy, W, lay.H - gy, "#241A14");
  const rnd = rng(5);
  for (let i = 0; i < Math.round(120 * W / TW); i++) g.p(Math.floor(rnd() * W), gy + 6 + Math.floor(rnd() * (lay.H - gy - 6)), rnd() < 0.5 ? "#33261D" : "#1B130E");
  for (let i = 0; i < Math.round(10 * W / TW); i++) { const x = Math.floor(rnd() * W), y = gy + 14 + Math.floor(rnd() * (lay.H - gy - 20)); g.r(x, y, 3, 2, "#4A4038"); }
  g.r(0, gy, W, 2, "#3A3F4A"); g.r(0, gy + 2, W, 3, "#15181E");
  for (let x = 4; x < W; x += 14) g.r(x, gy + 3, 6, 1, "#C9A24C");
  const lamps = [];
  for (let x = lay.ox + 18; x > 0; x -= 90) lamps.push([x]);
  for (let x = lay.ox + 382; x < W; x += 90) lamps.push([x]);
  lamps.forEach(([x]) => {
    g.r(x, gy - 24, 1, 24, "#3A4350"); g.r(x - 2, gy - 25, 5, 2, "#F5E6A8");
    for (let j = 0; j < 22; j++) g.r(x - 2 - Math.round(j * 0.4), gy - 23 + j, 5 + Math.round(j * 0.8), 1, "rgba(245,230,168,.05)");
  });
}

function drawHull(L, lay) {
  const g = L.get("hull"), top = lay.bridge.y, bot = lay.base.y + lay.base.h + 6;
  [52, 342].forEach((x) => {
    g.r(x, top, 6, bot - top, "#5D6573"); g.r(x, top, 1, bot - top, "#7A8391"); g.r(x + 5, top, 1, bot - top, "#3F4652");
    for (let y = top + 4; y < bot; y += 8) g.p(x + 3, y, "#8A93A0");
  });
  const slab = (y, h, seed) => {
    g.r(52, y, 296, h, "#4B5360"); g.r(52, y, 296, 1, "#6B7482"); g.r(52, y + h - 1, 296, 1, "#353B46");
    const r = rng(seed);
    g.r(58, y + 2, 130, 1, "#D9822B"); g.r(212, y + 3, 130, 1, "#3FB6C8"); g.r(58, y + 4, 284, 1, "#2F3540");
    for (let x = 60; x < 340; x += 24) g.r(x + Math.floor(r() * 10), y + 2, 3, 3, "#5D6573");
  };
  slab(lay.bridge.y + lay.bridge.h, 6, 1);
  for (let i = 0; i < lay.floors; i++) slab(lay.crewY0 + i * 76 + 70, 6, 2 + i);
  slab(lay.base.y + lay.base.h, 6, 9);
  // dach: płyta, klocki na attyce, antena, talerz, zbiornik, neon Jarvo
  const roof = L.get("roof");
  roof.r(50, 40, 300, 6, "#5D6573"); roof.r(50, 40, 300, 1, "#8A93A0"); roof.r(50, 45, 300, 1, "#3F4652");
  for (let x = 52; x < 346; x += 6) { roof.r(x, 38, 4, 2, "#6B7482"); roof.p(x, 38, "#9AA4B0"); }
  roof.r(300, 5, 2, 33, "#7A8391"); roof.r(296, 14, 10, 1, "#7A8391"); roof.r(297, 22, 8, 1, "#7A8391"); roof.r(298, 30, 6, 1, "#7A8391");
  roof.line(301, 8, 290, 38, "#4A5361"); roof.line(301, 8, 312, 38, "#4A5361");
  L.get("beacon", "thq-px-beacon").r(299, 1, 4, 3, "#FF3B30").r(298, 2, 6, 1, "rgba(255,59,48,.5)");
  roof.r(88, 26, 14, 2, "#DDE3EA"); roof.r(90, 28, 10, 2, "#C7CFD8"); roof.r(92, 30, 6, 2, "#B3BCC7"); roof.line(95, 26, 102, 20, "#8A93A0"); roof.p(102, 19, "#FF3B30");
  roof.r(94, 32, 3, 6, "#5A6574");
  roof.r(116, 18, 20, 14, "#8A5A33"); roof.r(116, 21, 20, 1, "#6E4628"); roof.r(116, 28, 20, 1, "#6E4628"); roof.r(118, 16, 16, 2, "#6E4628"); roof.r(121, 14, 10, 2, "#6E4628");
  roof.r(119, 32, 1, 6, "#4A515C"); roof.r(132, 32, 1, 6, "#4A515C");
  roof.r(248, 30, 20, 8, "#9AA4B0"); roof.r(248, 30, 20, 1, "#C2CAD3"); for (let x = 251; x < 266; x += 3) roof.r(x, 32, 1, 5, "#6E7884");
  roof.r(172, 30, 2, 8, "#4A515C"); roof.r(226, 30, 2, 8, "#4A515C"); roof.r(165, 12, 70, 20, "#141922"); roof.r(165, 12, 70, 1, "#2B3441");
  const neon = L.get("neon-sign", "thq-px-sign");
  neon.text(171, 15, "JARVO", "rgba(242,193,78,.35)", 3); neon.text(172, 15, "JARVO", "#F2C14E", 3);
}

function drawShaft(L, lay, moving) {
  const g = L.get("shaft"), s = lay.shaft;
  g.r(s.x, s.y, s.w, s.h, "#0B0E14"); g.r(s.x, s.y, 2, s.h, "#3F4652"); g.r(s.x + s.w - 2, s.y, 2, s.h, "#3F4652");
  g.r(s.x + 4, s.y, 1, s.h, "#2E3540"); g.r(s.x + s.w - 5, s.y, 1, s.h, "#2E3540"); g.r(s.x + 11, s.y, 1, s.h, "#3A414C"); g.r(s.x + 13, s.y, 1, s.h, "#3A414C");
  for (let i = 0; i < lay.floors; i++) { const y = lay.crewY0 + i * 76; g.r(s.x + 9, y + 3, 6, 3, "#1A1F27"); g.r(s.x + 10, y + 4, 4, 1, moving ? "#3DDC84" : "#56606E"); }
  const stop0 = lay.crewY0 + 44, stop1 = lay.base.y + 14;
  const car = L.get("lift", moving ? "thq-px-lift" : "", { "--thq-lift": `${stop1 - stop0}px` });
  const x = s.x + 2, y = stop0;
  car.r(x, y, 20, 22, "#9AA4B0"); car.r(x, y, 20, 1, "#C2CAD3"); car.r(x + 2, y + 2, 16, 18, "#1D2733");
  car.r(x + 3, y + 3, 14, 7, moving ? "#FFE7A8" : "#3A4452"); car.r(x + 9, y + 10, 2, 10, "#6E7884"); car.r(x + 8, y - 30, 1, 30, "#2E3540"); car.r(x + 11, y - 30, 1, 30, "#2E3540");
}

function drawBasement(L, lay, online) {
  const g = L.get("base"), b = lay.base;
  g.r(b.x, b.y, b.w, b.h, "#1A1F27");
  for (let x = b.x + 12; x < b.x + b.w; x += 16) g.r(x, b.y, 1, b.h - 6, "#20262F");
  g.r(b.x, b.y + b.h - 6, b.w, 6, "#2A313B"); for (let x = b.x; x < b.x + b.w; x += 3) g.p(x, b.y + b.h - 4, "#1A1F27");
  g.r(b.x, b.y + 2, b.w, 2, "#6E3A10"); g.r(b.x, b.y + 5, b.w, 1, "#2C6ED5"); g.r(b.x, b.y + 7, b.w, 1, "#4A515C");
  const leds1 = L.get("base-led1", "thq-px-led1"), leds2 = L.get("base-led2", "thq-px-led2");
  [b.x + 8, b.x + 24, b.x + 40, b.x + 56, b.x + 72, b.x + 90].forEach((rx, i) => {
    g.r(rx, b.y + 10, 12, 24, "#12161C"); g.r(rx, b.y + 10, 12, 1, "#2B313A");
    for (let j = 0; j < 5; j++) { g.r(rx + 1, b.y + 12 + j * 4, 10, 3, "#20262F"); (j % 2 ? leds1 : leds2).p(rx + 2 + (i % 3), b.y + 13 + j * 4, j === 2 ? "#5AA9FF" : "#3DDC84"); }
  });
  const cx0 = b.x + 150;
  g.r(cx0 - 12, b.y + 8, 24, 4, "#4A515C"); g.r(cx0 - 12, b.y + 30, 24, 4, "#4A515C"); g.r(cx0 - 9, b.y + 12, 18, 18, "#0D1117");
  const core = L.get("core", "thq-px-core"), col = online ? "#3DDC84" : "#FF4D3D";
  core.r(cx0 - 7, b.y + 12, 14, 18, online ? "rgba(61,220,132,.25)" : "rgba(255,77,61,.25)"); core.r(cx0 - 3, b.y + 12, 6, 18, col); core.r(cx0 - 1, b.y + 12, 2, 18, "#E8FFF2");
  g.r(cx0 - 10, b.y + 12, 1, 18, "#6B7482"); g.r(cx0 + 9, b.y + 12, 1, 18, "#6B7482");
  g.r(cx0 + 24, b.y + 12, 38, 9, "#0E131B"); g.text(cx0 + 26, b.y + 14, "GATEWAY", online ? "#3DDC84" : "#FF4D3D");
  g.r(cx0 + 24, b.y + 24, 38, 9, "#0E131B"); g.text(cx0 + 26, b.y + 26, online ? "ONLINE" : "OFFLINE", online ? "#7CF0B4" : "#FF8A7A");
  g.r(b.x + b.w - 30, b.y + 14, 22, 20, "#3A4350"); g.r(b.x + b.w - 28, b.y + 16, 18, 16, "#2A313B"); g.circle(b.x + b.w - 19, b.y + 24, 5, "#4A515C");
  L.get("fan", "thq-px-f1", { "--thq-d": ".3s" }).r(b.x + b.w - 24, b.y + 24, 10, 1, "#8A93A0");
  L.get("fan2", "thq-px-f2", { "--thq-d": ".3s" }).r(b.x + b.w - 19, b.y + 19, 1, 10, "#8A93A0");
}

// Statyczne tło (niebo, miasto, grunt, kadłub, dach): rysowane raz dla danej liczby pięter
const TowerBackdrop = React.memo(function TowerBackdrop({ floors, W }) {
  const lay = towerLayout(floors * 2, W);
  const L = new Layers();
  drawSky(L, lay); drawCity(L, lay); drawGround(L, lay);
  const T = new Layers(lay.ox, 0);
  drawHull(T, lay);
  return html`<g>${L.render()}${T.render()}</g>`;
});

function TowerMachines({ floors, W, moving, online }) {
  const lay = towerLayout(floors * 2, W);
  const L = new Layers(lay.ox, 0);
  drawShaft(L, lay, moving);
  drawBasement(L, lay, online);
  return html`<g>${L.render()}</g>`;
}
