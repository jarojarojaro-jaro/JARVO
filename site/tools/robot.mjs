// Robot na telefon: pozy z karty postaci (03_POSTAC/JARVO-karta-postaci-czerwona.png) bez jasnego tła.
// Tło znika zalewaniem od krawędzi (biała głowa w konturze zostaje), potem pyłki i cień podłogi,
// a na końcu jasna „aureola” na krawędzi (piksele pośrednie między konturem a tłem planszy).
// Z pozy FRONT osobno oczy (do mrugania).
//
//   node site/tools/robot.mjs <karta-postaci.png> site/assets
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const [src, out] = process.argv.slice(2);
if (!src || !out) { console.error("użycie: node robot.mjs <karta-postaci.png> <katalog>"); process.exit(2); }
// pozy w planszy 1536×1024: prostokąt i punkty tła zamknięte w konturze (np. między nogami)
const POSES = {
  front:  { box: [92, 118, 325, 489], holes: [[214, 448]] },
  think:  { box: [70, 578, 295, 930], holes: [[205, 900], [205, 890], [200, 905]] },
  build:  { box: [436, 592, 712, 930], holes: [] },
  review: { box: [800, 582, 1088, 930], holes: [[945, 905], [943, 895], [948, 912]] },
  ship:   { box: [1186, 566, 1474, 930], holes: [[1330, 900], [1325, 890], [1335, 908]] },
};
const EYES = [160, 205, 255, 258];   // oczy pozy FRONT (współrzędne planszy)

const b = await chromium.launch();
const p = await b.newPage();
const data = "data:image/png;base64," + fs.readFileSync(src).toString("base64");
const res = await p.evaluate(async ({ data, POSES, EYES }) => {
  const img = new Image(); img.src = data; await img.decode();
  const outp = {};
  for (const [name, { box, holes }] of Object.entries(POSES)) {
    const [x0, y0, x1, y1] = box, W = x1 - x0, H = y1 - y0;
    const c = document.createElement("canvas"); c.width = W; c.height = H;
    const g = c.getContext("2d"); g.drawImage(img, x0, y0, W, H, 0, 0, W, H);
    const px = g.getImageData(0, 0, W, H); const d = px.data;
    const bg = [d[0], d[1], d[2]];
    const lum = (i) => (d[i] + d[i + 1] + d[i + 2]) / 3;
    const sat = (i) => Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2]);
    const isBg = (k) => {
      const i = k * 4;
      if (Math.abs(d[i] - bg[0]) < 26 && Math.abs(d[i + 1] - bg[1]) < 26 && Math.abs(d[i + 2] - bg[2]) < 26) return true;
      return (k / W | 0) > H - 22 && lum(i) > 105 && lum(i) < 225 && sat(i) < 22;   // cień podłogi pod butami
    };
    const stack = [];
    for (let x = 0; x < W; x++) stack.push(x, (H - 1) * W + x);
    for (let y = 0; y < H; y++) stack.push(y * W, y * W + W - 1);
    for (const [hx, hy] of holes) stack.push((hy - y0) * W + (hx - x0));
    const seen = new Uint8Array(W * H);
    while (stack.length) {
      const k = stack.pop(); if (seen[k] || !isBg(k)) continue;
      seen[k] = 1; d[k * 4 + 3] = 0;
      const x = k % W, y = k / W | 0;
      if (x > 0) stack.push(k - 1); if (x < W - 1) stack.push(k + 1);
      if (y > 0) stack.push(k - W); if (y < H - 1) stack.push(k + W);
    }
    // największy kawałek = robot
    const comp = new Int32Array(W * H).fill(-1); const sizes = [];
    for (let k = 0; k < W * H; k++) {
      if (comp[k] >= 0 || d[k * 4 + 3] === 0) continue;
      const id = sizes.length; let n = 0; const st = [k]; comp[k] = id;
      while (st.length) {
        const q = st.pop(); n++; const x = q % W, y = q / W | 0;
        for (const r of [x > 0 ? q - 1 : -1, x < W - 1 ? q + 1 : -1, y > 0 ? q - W : -1, y < H - 1 ? q + W : -1])
          if (r >= 0 && comp[r] < 0 && d[r * 4 + 3] !== 0) { comp[r] = id; st.push(r); }
      }
      sizes.push(n);
    }
    const main = sizes.indexOf(Math.max(...sizes));
    for (let k = 0; k < W * H; k++) if (d[k * 4 + 3] !== 0 && comp[k] !== main) d[k * 4 + 3] = 0;
    // aureola: jasne/szare piksele stykające się z przezroczystością (3 przejścia, od zewnątrz do konturu)
    for (let pass = 0; pass < 3; pass++) {
      const kill = [];
      for (let k = 0; k < W * H; k++) {
        const i = k * 4; if (d[i + 3] === 0) continue;
        const x = k % W, y = k / W | 0;
        const edge = x === 0 || y === 0 || x === W - 1 || y === H - 1 || d[i - 1] === 0 || d[i + 7] === 0 ||
                     d[i - W * 4 + 3] === 0 || d[i + W * 4 + 3] === 0;
        if (edge && lum(i) > 95 && sat(i) < 45) kill.push(i);
      }
      for (const i of kill) d[i + 3] = 0;
    }
    let mnx = W, mny = H, mxx = 0, mxy = 0;
    for (let k = 0; k < W * H; k++) if (d[k * 4 + 3]) { const x = k % W, y = k / W | 0; mnx = Math.min(mnx, x); mny = Math.min(mny, y); mxx = Math.max(mxx, x); mxy = Math.max(mxy, y); }
    let eyes = null;
    if (name === "front") {
      const e = document.createElement("canvas"); e.width = W; e.height = H;
      const eg = e.getContext("2d"); const ed = eg.createImageData(W, H);
      const si = ((232 - y0) * W + (200 - x0)) * 4; const screen = [d[si], d[si + 1], d[si + 2]];
      const lime = [];
      for (let y = EYES[1] - y0; y < EYES[3] - y0; y++) for (let x = EYES[0] - x0; x < EYES[2] - x0; x++) {
        const i = (y * W + x) * 4;
        if (d[i + 1] > 120 && d[i + 2] < 150 && d[i + 1] > d[i + 2] + 40) lime.push([x, y, i]);
      }
      for (const [, , i] of lime) ed.data.set([d[i], d[i + 1], d[i + 2], 255], i);
      for (const [x, y] of lime) for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const j = ((y + dy) * W + x + dx) * 4; d[j] = screen[0]; d[j + 1] = screen[1]; d[j + 2] = screen[2];
      }
      eg.putImageData(ed, 0, 0); eyes = e;
    }
    g.putImageData(px, 0, 0);
    const cw = mxx - mnx + 1, ch = mxy - mny + 1;
    const crop = (cv) => { const o = document.createElement("canvas"); o.width = cw; o.height = ch; o.getContext("2d").drawImage(cv, mnx, mny, cw, ch, 0, 0, cw, ch); return o.toDataURL("image/png"); };
    outp[name] = { png: crop(c), eyes: eyes && crop(eyes), w: cw, h: ch };
  }
  return outp;
}, { data, POSES, EYES });
await b.close();
const meta = {};
for (const [name, r] of Object.entries(res)) {
  fs.writeFileSync(path.join(out, `robot-${name}.png`), Buffer.from(r.png.split(",")[1], "base64"));
  if (r.eyes) fs.writeFileSync(path.join(out, "robot-eyes.png"), Buffer.from(r.eyes.split(",")[1], "base64"));
  meta[name] = { w: r.w, h: r.h };
}
fs.writeFileSync(path.join(out, "robot.json"), JSON.stringify(meta) + "\n");
console.log(meta);
