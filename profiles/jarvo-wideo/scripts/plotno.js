// Wykończenie kadru (Canvas 2D): papier (ząbek i chmurki z szumu), ziarno filmu zmieniane co klatkę, kurz,
// winieta, druk z przesuniętych płyt (riso, Bauhaus, sitodruk) i raster półtonowy (gazeta, kolaż). Wszystko z kodu:
// bez cudzych tekstur, więc wolno tego użyć w każdym filmie klienta. Ta sama klatka = ten sam wynik.
// Strona: import { papier, ziarno, kurz, winieta, druk, polton } from '/_lib/jarvo/plotno.js';
// (html_wideo.py i podgląd HQ serwują ten plik pod /_lib/jarvo/; zasady stylów: style-motion/references/)
//
// Liczby za mg-styles-15 (MIT, Vincentwei1021): papier mnożony z siłą 0,5, kurz 0,22, przesunięcie płyt druku
// 1–1,3 px na kolor, raster 45° co 6,5 px (demos/05-cel-boil, 09-bauhaus, 06-collage). Tekstury liczone tu, nie z repo.

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));

export function hash(...liczby) {
  let h = 2166136261 >>> 0;
  for (const v of liczby) {
    h = Math.imul(h ^ ((Math.round(v * 997) | 0) >>> 0), 16777619) >>> 0;
    h ^= h >>> 13; h = Math.imul(h, 0x5bd1e995) >>> 0; h ^= h >>> 15;
  }
  return (h >>> 0) / 4294967296;
}

// Szum wartości zawinięty na kafel n×n (oczko `oczko` px dzieli n): kafel powtarza się bez szwu. Wartości węzłów
// liczone raz (siatka m×m), potem tylko gładkie przejście między nimi.
function szumKafla(n, oczko, ziarno) {
  const m = n / oczko, siatka = new Float32Array(m * m);
  for (let j = 0; j < m; j++) for (let i = 0; i < m; i++) siatka[j * m + i] = hash(i, j, oczko, ziarno);
  return (x, y) => {
    const gx = x / oczko, gy = y / oczko, x0 = Math.floor(gx), y0 = Math.floor(gy), fx = gx - x0, fy = gy - y0;
    const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy), i0 = x0 % m, i1 = (x0 + 1) % m, j0 = (y0 % m) * m, j1 = ((y0 + 1) % m) * m;
    const a = siatka[j0 + i0] + (siatka[j0 + i1] - siatka[j0 + i0]) * sx, b = siatka[j1 + i0] + (siatka[j1 + i1] - siatka[j1 + i0]) * sx;
    return a + (b - a) * sy;
  };
}

const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

// Kafel papieru (RGBA n×n): kolor papieru × (1 − zab·(1 − szum drobny)) × (1 − chmury·(1 − szum duży)).
export function kafelPapieru(n = 1024, { kolor = '#f4ead6', zab = 0.10, chmury = 0.05, ziarno = 1 } = {}) {
  const [r, g, b] = hexRgb(kolor), dane = new Uint8ClampedArray(n * n * 4);
  const s4 = szumKafla(n, 4, ziarno), s16 = szumKafla(n, 16, ziarno + 1), s128 = szumKafla(n, 128, ziarno + 2);
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      const k = (1 - zab * (1 - (0.6 * s4(x, y) + 0.4 * s16(x, y)))) * (1 - chmury * (1 - s128(x, y)));
      const i = (y * n + x) * 4;
      dane[i] = r * k; dane[i + 1] = g * k; dane[i + 2] = b * k; dane[i + 3] = 255;
    }
  }
  return dane;
}

// Kafel ziarna (szary 128 ± szum o rozkładzie zbliżonym do normalnego), nakładany trybem overlay.
export function kafelZiarna(n = 256, ziarno = 1) {
  const dane = new Uint8ClampedArray(n * n * 4);
  for (let i = 0; i < n * n; i++) {
    const v = (hash(i, ziarno) + hash(i, ziarno + 7) + hash(i, ziarno + 13)) / 3;   // suma trzech = dzwon
    const s = 128 + (v - 0.5) * 255 * 1.6;
    dane[4 * i] = dane[4 * i + 1] = dane[4 * i + 2] = s; dane[4 * i + 3] = 255;
  }
  return dane;
}

// Promień kropki rastra dla jasności 0–1 (0 = czerń): pole kropki ∝ ciemność, przy czerni kropki się stykają.
export const promienKropki = (jasnosc, krok) => 0.5 * krok * Math.SQRT2 * Math.sqrt(clamp(1 - jasnosc));

// ---------------------------------------------------------------- rysowanie (przeglądarka)
const _kafle = new Map();
function kafel(klucz, n, dane) {
  if (!_kafle.has(klucz)) {
    const c = typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(n, n) : Object.assign(document.createElement('canvas'), { width: n, height: n });
    c.getContext('2d').putImageData(new ImageData(dane(), n, n), 0, 0);
    _kafle.set(klucz, c);
  }
  return _kafle.get(klucz);
}

// Papier pod rysunkiem (albo nad nim: tryb 'multiply', sila 0,5 = ząbek widoczny też na kolorze). `kartka` = numer
// rysunku: każda kartka przesunięta inaczej (jak nowy arkusz w animacji rysunkowej); stała kartka = stały papier.
export function papier(g, w, h, { kolor = '#f4ead6', zab = 0.10, chmury = 0.05, kartka = 0, tryb = 'source-over', sila = 1 } = {}) {
  const n = 1024, t = kafel(`p|${kolor}|${zab}|${chmury}`, n, () => kafelPapieru(n, { kolor, zab, chmury }));
  rysujKafel(g, t, w, h, Math.floor(hash(kartka, 51) * n), Math.floor(hash(kartka, 52) * n), tryb, sila);
}

// Ziarno filmu: nowy rozkład co klatkę (przesunięty kafel), tryb overlay. sila 0,04–0,08 (taśma), 0,1–0,15 (gruba).
export function ziarno(g, w, h, klatka, sila = 0.06) {
  const n = 256, t = kafel('z', n, () => kafelZiarna(n));
  rysujKafel(g, t, w, h, Math.floor(hash(klatka, 3) * n), Math.floor(hash(klatka, 4) * n), 'overlay', sila);
}

function rysujKafel(g, t, w, h, ox, oy, tryb, sila) {
  g.save();
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalCompositeOperation = tryb;
  g.globalAlpha = sila;
  g.fillStyle = g.createPattern(t, 'repeat');
  g.translate(-ox, -oy);
  g.fillRect(ox, oy, w, h);
  g.restore();
}

// Kurz i włoski skanera: `ile` drobin i kilka włosków, układ zależny od `kartka` (zmieniaj co rysunek, nie co klatkę).
export function kurz(g, w, h, kartka = 0, { ile = 40, sila = 0.22, kolor = '#1c1613' } = {}) {
  g.save();
  g.globalAlpha = sila;
  g.fillStyle = kolor; g.strokeStyle = kolor; g.lineCap = 'round';
  for (let i = 0; i < ile; i++) {
    const x = hash(kartka, i, 1) * w, y = hash(kartka, i, 2) * h, r = 0.4 + 1.6 * Math.pow(hash(kartka, i, 3), 3);
    g.beginPath(); g.ellipse(x, y, r, r * (0.5 + 0.5 * hash(kartka, i, 4)), hash(kartka, i, 5) * Math.PI, 0, 2 * Math.PI); g.fill();
  }
  for (let i = 0; i < Math.ceil(ile / 15); i++) {
    const x = hash(kartka, i, 11) * w, y = hash(kartka, i, 12) * h, d = 12 + 30 * hash(kartka, i, 13), a = hash(kartka, i, 14) * Math.PI * 2;
    g.lineWidth = 0.6 + 0.5 * hash(kartka, i, 15);
    g.beginPath(); g.moveTo(x, y);
    g.quadraticCurveTo(x + Math.cos(a + 0.8) * d * 0.6, y + Math.sin(a + 0.8) * d * 0.6, x + Math.cos(a) * d, y + Math.sin(a) * d);
    g.stroke();
  }
  g.restore();
}

// Winieta: przyciemnienie rogów o `sila` (0,1–0,3), od `od` promienia (0–1) do rogu; kolor ciepły dla papieru.
export function winieta(g, w, h, { sila = 0.22, od = 0.45, kolor = '40, 20, 5' } = {}) {
  const r = Math.hypot(w, h) / 2, gr = g.createRadialGradient(w / 2, h / 2, r * od, w / 2, h / 2, r);
  gr.addColorStop(0, `rgba(${kolor}, 0)`);
  gr.addColorStop(1, `rgba(${kolor}, ${sila})`);
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.fillStyle = gr; g.fillRect(0, 0, w, h); g.restore();
}

// Druk z płyt: każda płyta (canvas z jednym kolorem farby na przezroczystym tle) mnożona na papier z własnym
// przesunięciem {dx, dy} px: tak wychodzi riso i Bauhaus (np. czerwona 1,3/−0,9, niebieska −1/1,2, czarna 0,5/0,4).
// rozjazd 0–1 mnoży przesunięcia (rozjeżdżanie się płyt przed finałem, potem „docisk” do 0).
export function druk(g, plyty, { rozjazd = 1, krycie = 1 } = {}) {
  g.save();
  g.globalCompositeOperation = 'multiply';
  g.globalAlpha = krycie;
  for (const p of plyty) g.drawImage(p.obraz, (p.dx || 0) * rozjazd, (p.dy || 0) * rozjazd);
  g.restore();
}

// Raster półtonowy: obraz `zrodlo` (canvas/obraz w rozmiarze kadru) jako kropki co `krok` px pod kątem `kat` (stopnie);
// kropka tym większa, im ciemniej. Gazeta: 45°, 6,5 px, tusz; kolor CMYK: osobno na płytę z kątami 15/75/0/45.
export function polton(g, zrodlo, { krok = 6.5, kat = 45, kolor = '#16130f', w = null, h = null } = {}) {
  w = w ?? zrodlo.width; h = h ?? zrodlo.height;
  const sw = Math.max(1, Math.ceil(w / krok * 2)), sh = Math.max(1, Math.ceil(h / krok * 2));
  const maly = typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(sw, sh) : Object.assign(document.createElement('canvas'), { width: sw, height: sh });
  const mg = maly.getContext('2d', { willReadFrequently: true });
  mg.drawImage(zrodlo, 0, 0, sw, sh);
  const px = mg.getImageData(0, 0, sw, sh).data, a = kat * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
  const R = Math.hypot(w, h) / 2 + krok, cx = w / 2, cy = h / 2;
  g.save();
  g.fillStyle = kolor;
  g.beginPath();
  for (let v = -R; v <= R; v += krok) {
    for (let u = -R; u <= R; u += krok) {
      const x = cx + u * c - v * s, y = cy + u * s + v * c;
      if (x < -krok || y < -krok || x > w + krok || y > h + krok) continue;
      const i = (clamp(Math.floor(y / h * sh), 0, sh - 1) * sw + clamp(Math.floor(x / w * sw), 0, sw - 1)) * 4;
      const jasnosc = (0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2]) / 255 * (px[i + 3] / 255) + (1 - px[i + 3] / 255);
      const r = promienKropki(jasnosc, krok);
      if (r < 0.3) continue;
      g.moveTo(x + r, y); g.arc(x, y, r, 0, 2 * Math.PI);
    }
  }
  g.fill();
  g.restore();
}
