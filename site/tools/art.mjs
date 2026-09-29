// Warstwy ilustracji landingu z grafiki marki (04_STRONA_I_APLIKACJA/JARVO-landing-page-koncepcja.png):
// tło sceny bez ruchomych elementów + osobne sprite'y (panele, oczy, dłonie), żeby robot mógł się ruszać.
// Nagłówek „FROM IDEA TO REALITY.” jako wektor (piksele obrysowane z grafiki), ostry w każdej skali.
//
//   node site/tools/art.mjs <koncepcja.png> site/assets
//
// Wymaga Playwright (Chromium). Współrzędne to piksele grafiki 1536×1024 (tak jak w CSS strony).
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const [src, out] = process.argv.slice(2);
if (!src || !out) { console.error("użycie: node art.mjs <koncepcja.png> <katalog-wyjściowy>"); process.exit(2); }
fs.mkdirSync(out, { recursive: true });

// scena: prawa część grafiki, pod nagłówkiem strony i nad terminalem
const SCENE = { x: 770, y: 70, w: 735, h: 570 };
const SPRITES = {
  // panele pływające nad biurkiem (prostokąty obejmujące panel; tło wokół staje się przezroczyste)
  "panels-l": { rects: [[862, 72, 1013, 318], [864, 318, 923, 349]], key: "bg" },
  "panels-r": { rects: [[1286, 134, 1488, 290], [1293, 290, 1488, 375], [1446, 375, 1488, 393]], key: "bg" },
  // oczy na ekranie-twarzy: tylko limonkowe piksele
  "eye-l": { rects: [[1066, 218, 1089, 270]], key: "lime", fill: "screen" },
  "eye-r": { rects: [[1118, 227, 1155, 279]], key: "lime", fill: "screen" },
  // dłonie w rękawiczkach: tylko jasne piksele (klawiatura zostaje na miejscu)
  "hand-l": { rects: [[1090, 392, 1158, 434]], key: "glove" },
  "hand-r": { rects: [[1136, 378, 1186, 431]], key: "glove" },
};
// śmieci z makiety, których strona nie potrzebuje (przycisk „Open JARVO” i ramka nagłówka nad sceną)
const ERASE = [[1240, 70, 1505, 119], [770, 104, 790, 120]];

const b = await chromium.launch();
const p = await b.newPage();
const data = "data:image/png;base64," + fs.readFileSync(src).toString("base64");
const result = await p.evaluate(async ({ data, SCENE, SPRITES, ERASE }) => {
  const img = new Image(); img.src = data; await img.decode();
  const W = img.width, H = img.height;
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const g = c.getContext("2d"); g.drawImage(img, 0, 0);
  const px = g.getImageData(0, 0, W, H); const d = px.data;
  const at = (x, y) => (y * W + x) * 4;
  // kolor tła: najczęstszy (kwantyzowany) w pasie między sceną a nagłówkiem
  const hist = new Map();
  for (let y = 120; y < 640; y += 3) for (let x = 740; x < 1500; x += 3) {
    const i = at(x, y); const k = (d[i] >> 2) << 16 | (d[i + 1] >> 2) << 8 | (d[i + 2] >> 2);
    hist.set(k, (hist.get(k) || 0) + 1);
  }
  const top = [...hist.entries()].sort((a, b) => b[1] - a[1])[0][0];
  const bg = [((top >> 16) & 255) * 4 + 2, ((top >> 8) & 255) * 4 + 2, (top & 255) * 4 + 2];
  const screenAt = at(1100, 250); const screen = [d[screenAt], d[screenAt + 1], d[screenAt + 2]];
  const near = (i, col, t) => Math.abs(d[i] - col[0]) < t && Math.abs(d[i + 1] - col[1]) < t && Math.abs(d[i + 2] - col[2]) < t;
  const keys = {
    bg: (i) => !near(i, bg, 7),
    lime: (i) => d[i + 1] > 150 && d[i] > 110 && d[i + 2] < 140 && d[i + 1] > d[i + 2] + 60,
    glove: (i) => d[i] > 150 && d[i + 1] > 150 && d[i + 2] > 140 && Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2]) < 45,
  };
  const inRects = (x, y, rects) => rects.some(([x0, y0, x1, y1]) => x >= x0 && x < x1 && y >= y0 && y < y1);
  const sprites = {};
  for (const [name, s] of Object.entries(SPRITES)) {
    const x0 = Math.min(...s.rects.map(r => r[0])), y0 = Math.min(...s.rects.map(r => r[1]));
    const x1 = Math.max(...s.rects.map(r => r[2])), y1 = Math.max(...s.rects.map(r => r[3]));
    const sc = document.createElement("canvas"); sc.width = x1 - x0; sc.height = y1 - y0;
    const sg = sc.getContext("2d"); const sd = sg.createImageData(sc.width, sc.height);
    const taken = [];
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
      if (!inRects(x, y, s.rects)) continue;
      const i = at(x, y);
      if (!keys[s.key](i)) continue;
      const o = ((y - y0) * sc.width + (x - x0)) * 4;
      // panele: piksele bliskie tła półprzezroczyste (miękka krawędź zamiast szumu z prostokąta)
      const dist = Math.max(Math.abs(d[i] - bg[0]), Math.abs(d[i + 1] - bg[1]), Math.abs(d[i + 2] - bg[2]));
      const a = s.key === "bg" ? Math.min(1, (dist - 4) / 14) : 1;
      sd.data[o] = d[i]; sd.data[o + 1] = d[i + 1]; sd.data[o + 2] = d[i + 2]; sd.data[o + 3] = Math.round(255 * a);
      taken.push([x, y]);
    }
    sg.putImageData(sd, 0, 0);
    sprites[name] = { x: x0 - SCENE.x, y: y0 - SCENE.y, w: sc.width, h: sc.height, png: sc.toDataURL("image/png") };
    // w tle: tam, gdzie był element, kolor tła (panele) albo ekranu (oczy, z 1 px zapasu na miękkie krawędzie);
    // dłonie zostają też w tle (pod nimi nie ma czego pokazać)
    if (s.key === "glove") continue;
    if (s.key === "bg") {   // panel: całe prostokąty do koloru tła (sprite ma już wszystko, co nie jest tłem)
      for (const [rx0, ry0, rx1, ry1] of s.rects) for (let y = ry0; y < ry1; y++) for (let x = rx0; x < rx1; x++) {
        const i = at(x, y); d[i] = bg[0]; d[i + 1] = bg[1]; d[i + 2] = bg[2];
      }
      continue;
    }
    const col = s.fill === "screen" ? screen : bg, pad = s.fill === "screen" ? 1 : 0;
    for (const [x, y] of taken) for (let dy = -pad; dy <= pad; dy++) for (let dx = -pad; dx <= pad; dx++) {
      const i = at(x + dx, y + dy); d[i] = col[0]; d[i + 1] = col[1]; d[i + 2] = col[2];
    }
  }
  for (const [x0, y0, x1, y1] of ERASE) for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
    const i = at(x, y); d[i] = bg[0]; d[i + 1] = bg[1]; d[i + 2] = bg[2];
  }
  g.putImageData(px, 0, 0);
  const scene = document.createElement("canvas"); scene.width = SCENE.w; scene.height = SCENE.h;
  scene.getContext("2d").drawImage(c, SCENE.x, SCENE.y, SCENE.w, SCENE.h, 0, 0, SCENE.w, SCENE.h);

  // nagłówek: jasne piksele w obszarze tytułu → ścieżka SVG (poziome odcinki scalone w prostokąty)
  const T = { x: 55, y: 205, w: 715, h: 220 };
  const lit = (x, y) => { const i = at(x, y); return img && (d[i] + d[i + 1] + d[i + 2]) / 3 > 150 && d[i + 2] > 120; };
  const runs = [];
  for (let y = T.y; y < T.y + T.h; y++) {
    let x = T.x;
    while (x < T.x + T.w) {
      if (lit(x, y)) { const s = x; while (x < T.x + T.w && lit(x, y)) x++; runs.push([s - T.x, y - T.y, x - s]); } else x++;
    }
  }
  // pionowe scalanie identycznych odcinków z kolejnych wierszy
  const open = new Map(), rects = [];
  const byRow = new Map(); for (const r of runs) { if (!byRow.has(r[1])) byRow.set(r[1], []); byRow.get(r[1]).push(r); }
  for (let y = 0; y <= T.h; y++) {
    const row = byRow.get(y) || []; const seen = new Set();
    for (const [x, , w] of row) {
      const k = x + ":" + w; seen.add(k);
      if (open.has(k)) open.get(k)[3]++; else open.set(k, [x, y, w, 1]);
    }
    for (const [k, r] of [...open]) if (!seen.has(k)) { rects.push(r); open.delete(k); }
  }
  const dpath = rects.map(([x, y, w, h]) => `M${x} ${y}h${w}v${h}h-${w}z`).join("");
  return { bg, screen, sprites, scene: scene.toDataURL("image/png"), title: { ...T, d: dpath } };
}, { data, SCENE, SPRITES, ERASE });
await b.close();

const write = (name, url) => fs.writeFileSync(path.join(out, name), Buffer.from(url.split(",")[1], "base64"));
write("scene.png", result.scene);
const meta = { scene: SCENE, bg: result.bg, sprites: {} };
for (const [name, s] of Object.entries(result.sprites)) {
  write(`${name}.png`, s.png);
  meta.sprites[name] = { x: s.x, y: s.y, w: s.w, h: s.h };
}
fs.writeFileSync(path.join(out, "title.svg"),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${result.title.w} ${result.title.h}" shape-rendering="crispEdges">` +
  `<title>FROM IDEA TO REALITY.</title><path fill="#F2F1E8" d="${result.title.d}"/></svg>\n`);
fs.writeFileSync(path.join(out, "art.json"), JSON.stringify(meta, null, 1) + "\n");
console.log("tło", result.bg, "ekran", result.screen, "sprite'y", Object.keys(meta.sprites).join(", "));
