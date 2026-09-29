// Robot na telefon: poza FRONT z karty postaci (03_POSTAC/JARVO-karta-postaci-czerwona.png) bez jasnego tła
// (zalewanie od krawędzi, więc biała głowa zostaje) i osobno jego oczy (limonkowe piksele) do mrugania.
//
//   node site/tools/robot.mjs <karta-postaci.png> site/assets
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const [src, out] = process.argv.slice(2);
if (!src || !out) { console.error("użycie: node robot.mjs <karta-postaci.png> <katalog>"); process.exit(2); }
const BOX = { x: 92, y: 118, w: 233, h: 371 };   // poza FRONT w planszy 1536×1024
const EYES = [160, 205, 255, 258];               // obszar oczu (współrzędne planszy)
const GAP = [122, 330];                          // punkt w tle między nogami (współrzędne wycinka)

const b = await chromium.launch();
const p = await b.newPage();
const data = "data:image/png;base64," + fs.readFileSync(src).toString("base64");
const res = await p.evaluate(async ({ data, BOX, EYES, GAP }) => {
  const img = new Image(); img.src = data; await img.decode();
  const c = document.createElement("canvas"); c.width = BOX.w; c.height = BOX.h;
  const g = c.getContext("2d"); g.drawImage(img, BOX.x, BOX.y, BOX.w, BOX.h, 0, 0, BOX.w, BOX.h);
  const px = g.getImageData(0, 0, BOX.w, BOX.h); const d = px.data; const W = BOX.w, H = BOX.h;
  const bg = [d[0], d[1], d[2]];
  // tło planszy albo szary cień podłogi (jasnoszary, bez nasycenia); kontury i spodnie są dużo ciemniejsze
  const isBg = (i) => {
    const [r, gg, bb] = [d[i], d[i + 1], d[i + 2]];
    const floor = i / 4 / W > H - 20;             // szary cień tylko pod butami
    if (Math.abs(r - bg[0]) < 26 && Math.abs(gg - bg[1]) < 26 && Math.abs(bb - bg[2]) < 26) return true;
    const lum = (r + gg + bb) / 3;
    return floor && lum > 105 && lum < 225 && Math.max(r, gg, bb) - Math.min(r, gg, bb) < 22;
  };
  // zalewanie tła od krawędzi
  const seen = new Uint8Array(W * H); const stack = [];
  for (let x = 0; x < W; x++) stack.push(x, (H - 1) * W + x);
  for (let y = 0; y < H; y++) stack.push(y * W, y * W + W - 1);
  stack.push(GAP[1] * W + GAP[0]);               // tło zamknięte między nogami
  while (stack.length) {
    const k = stack.pop(); if (seen[k]) continue;
    if (!isBg(k * 4)) continue;
    seen[k] = 1; d[k * 4 + 3] = 0;
    const x = k % W, y = (k / W) | 0;
    if (x > 0) stack.push(k - 1); if (x < W - 1) stack.push(k + 1);
    if (y > 0) stack.push(k - W); if (y < H - 1) stack.push(k + W);
  }
  // zostaje tylko największy kawałek (robot); pyłki i cień podłogi znikają
  const comp = new Int32Array(W * H).fill(-1); const sizes = [];
  for (let k = 0; k < W * H; k++) {
    if (comp[k] >= 0 || d[k * 4 + 3] === 0) continue;
    const id = sizes.length; let n = 0; const st = [k]; comp[k] = id;
    while (st.length) {
      const q = st.pop(); n++;
      const x = q % W, y = (q / W) | 0;
      for (const r of [x > 0 ? q - 1 : -1, x < W - 1 ? q + 1 : -1, y > 0 ? q - W : -1, y < H - 1 ? q + W : -1])
        if (r >= 0 && comp[r] < 0 && d[r * 4 + 3] !== 0) { comp[r] = id; st.push(r); }
    }
    sizes.push(n);
  }
  const main = sizes.indexOf(Math.max(...sizes));
  for (let k = 0; k < W * H; k++) if (d[k * 4 + 3] !== 0 && comp[k] !== main) d[k * 4 + 3] = 0;
  // oczy: limonkowe piksele w obszarze oczu → osobna warstwa; w robocie zamalowane kolorem ekranu
  const e = document.createElement("canvas"); e.width = W; e.height = H;
  const eg = e.getContext("2d"); const ed = eg.createImageData(W, H);
  const sx = 200 - BOX.x, sy = 232 - BOX.y, si = (sy * W + sx) * 4; const screen = [d[si], d[si + 1], d[si + 2]];
  const lime = [];
  for (let y = EYES[1] - BOX.y; y < EYES[3] - BOX.y; y++) for (let x = EYES[0] - BOX.x; x < EYES[2] - BOX.x; x++) {
    const i = (y * W + x) * 4;
    if (d[i + 1] > 120 && d[i + 2] < 150 && d[i + 1] > d[i + 2] + 40) lime.push([x, y, i]);
  }
  for (const [, , i] of lime) ed.data.set([d[i], d[i + 1], d[i + 2], 255], i);
  for (const [x, y] of lime) for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
    const j = ((y + dy) * W + x + dx) * 4; d[j] = screen[0]; d[j + 1] = screen[1]; d[j + 2] = screen[2];
  }
  g.putImageData(px, 0, 0); eg.putImageData(ed, 0, 0);
  return { robot: c.toDataURL("image/png"), eyes: e.toDataURL("image/png"), bg, screen };
}, { data, BOX, EYES, GAP });
await b.close();
for (const [n, u] of [["robot.png", res.robot], ["robot-eyes.png", res.eyes]])
  fs.writeFileSync(path.join(out, n), Buffer.from(u.split(",")[1], "base64"));
console.log("tło", res.bg, "ekran", res.screen, `${BOX.w}×${BOX.h}`);
