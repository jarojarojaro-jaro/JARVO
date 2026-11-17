// Silnik pikseli w rdzeniu: figurki rozmówców (22-figurka.js) i wieża Starej Bazy (20-art.js, pakiet „baza”).
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
  apps:     { fig: [60, 44], bubble: "left", wall: "#2E2A52", wall2: "#352F5E", side: "#26224A", ceil: "#1F1C3E", floor: "#D6D9E0", floor2: "#CBCED6", trim: "#1A1736", wallType: "panels", floorType: "checker" },
  control:  { fig: [60, 44], bubble: "left", wall: "#1C3346", wall2: "#172B3C", side: "#152839", ceil: "#10202E", floor: "#3B4654", floor2: "#343E4B", trim: "#0C1824", wallType: "ribs", floorType: "grid" },
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
  apps:     { coat: "#5B3FA8", coat2: "#45308A", pants: "#2B2F36", shoes: "#EDEFF2", hair: "#2A1C14", hairStyle: "messy", outfit: "hoodie", phones: "#B48CFF" },
  control:  { coat: "#22345A", coat2: "#182746", pants: "#2E3440", shoes: "#15171C", hair: "#3A2418", hairStyle: "short", outfit: "tie", tie: "#22345A", shirt: "#3A5A8C", phones: "#C9D3DE" },
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

