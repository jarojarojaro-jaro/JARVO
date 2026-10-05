// Pixel art: mały bufor (np. 320×180) z numerami kolorów zamiast RGB, paleta z etapami (dzień → złota godzina →
// zmierzch → noc) i przejściem w kilku krokach, dithering Bayera 4×4, sprite'y pisane tekstem, kontur 1 px, napis
// z krojem rasteryzowanym do 1 bitu i obraz w skali całkowitej. Ekran kineskopu na wierzchu: crt.js, tryb 'crt'.
// Strona: import { bufor, sprite, obrysuj, nanies, paleta, ditheruj, pokaz } from '/_lib/jarvo/piksel.js';
// (html_wideo.py i podgląd HQ serwują ten plik pod /_lib/jarvo/; zasady stylu: style-motion/references/pixel.md)
//
// Przeniesione z mg-styles-15 (MIT, Vincentwei1021, demos/20-pixel/film.js), nazwy i opcje po polsku.

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

export const BAYER4 = Object.freeze([0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]);
// Próg Bayera w punkcie (x, y): 0–1. Piksel bierze kolor B, gdy postęp przejścia > próg (wzór krzyżykowy, bez szumu).
export const bayer = (x, y) => (BAYER4[(y & 3) * 4 + (x & 3)] + 0.5) / 16;

export function bufor(w, h, tlo = 0) {
  return { w, h, px: new Uint8Array(w * h).fill(tlo) };
}
export function kropka(b, x, y, k) {
  x |= 0; y |= 0;
  if (x >= 0 && y >= 0 && x < b.w && y < b.h) b.px[y * b.w + x] = k;
}
export function prostokat(b, x, y, w, h, k) {
  for (let j = Math.max(0, y | 0); j < Math.min(b.h, (y | 0) + h); j++)
    for (let i = Math.max(0, x | 0); i < Math.min(b.w, (x | 0) + w); i++) b.px[j * b.w + i] = k;
}
// Linia Bresenhama (bez wygładzania: pixel art nie ma półtonów na krawędziach).
export function linia(b, x0, y0, x1, y1, k) {
  x0 |= 0; y0 |= 0; x1 |= 0; y1 |= 0;
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let e = dx + dy;
  for (;;) {
    kropka(b, x0, y0, k);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * e;
    if (e2 >= dy) { e += dy; x0 += sx; }
    if (e2 <= dx) { e += dx; y0 += sy; }
  }
}
// Przejście kolorów kA → kB ditheringiem: postep(x, y) → 0–1 (np. gradient nieba, krawędź światła, mgła).
export function ditheruj(b, x, y, w, h, postep, kA, kB) {
  for (let j = Math.max(0, y); j < Math.min(b.h, y + h); j++)
    for (let i = Math.max(0, x); i < Math.min(b.w, x + w); i++) b.px[j * b.w + i] = postep(i, j) > bayer(i, j) ? kB : kA;
}

// Sprite z wierszy tekstu: każdy znak to kolor z `legenda` ({'#': 1, 'o': 5}), '.' i spacja = przezroczysty.
export function sprite(wiersze, legenda) {
  const h = wiersze.length, w = Math.max(...wiersze.map((r) => r.length)), px = new Int16Array(w * h).fill(-1);
  wiersze.forEach((r, y) => [...r].forEach((z, x) => { if (z in legenda) px[y * w + x] = legenda[z]; }));
  return { w, h, px };
}
// Kontur 1 px wokół sprite'a (każdy przezroczysty piksel przy pełnym, także po skosie): czytelność na każdym tle.
export function obrysuj(s, k, skos = false) {
  const w = s.w + 2, h = s.h + 2, px = new Int16Array(w * h).fill(-1);
  const pelny = (x, y) => x >= 0 && y >= 0 && x < s.w && y < s.h && s.px[y * s.w + x] >= 0;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const v = pelny(x - 1, y - 1) ? s.px[(y - 1) * s.w + x - 1] : -1;
    if (v >= 0) { px[y * w + x] = v; continue; }
    const sas = [[-1, 0], [1, 0], [0, -1], [0, 1], ...(skos ? [[-1, -1], [1, -1], [-1, 1], [1, 1]] : [])];
    if (sas.some(([dx, dy]) => pelny(x - 1 + dx, y - 1 + dy))) px[y * w + x] = k;
  }
  return { w, h, px };
}
// Sprite na bufor w (x, y): odbicie poziome, zamiana kolorów {stary: nowy} (np. drugi kolor stroju).
export function nanies(b, s, x, y, { odbicie = false, zamiana = null } = {}) {
  x |= 0; y |= 0;
  for (let j = 0; j < s.h; j++) for (let i = 0; i < s.w; i++) {
    let v = s.px[j * s.w + (odbicie ? s.w - 1 - i : i)];
    if (v < 0) continue;
    if (zamiana && v in zamiana) v = zamiana[v];
    kropka(b, x + i, y + j, v);
  }
}

// Napis krojem przeglądarki rasteryzowany do 1 bitu (próg krycia 110/255) jako sprite koloru k, z cieniem 1 px.
// Krój pikselowy z polskimi znakami (Press Start 2P z /_lib/kroje/, rozmiar 8 lub wielokrotność): przed pierwszym
// napisem `await document.fonts.load('8px "Press Start 2P"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`, bo bez próbki przeglądarka nie
// pobierze pliku z polskimi literami i podstawi inny krój (wyjdzie papka).
export function napis(tekst, kroj, rozmiar, k, { cien = null, prog = 110 } = {}) {
  const c = document.createElement('canvas'), g = c.getContext('2d', { willReadFrequently: true });
  g.font = `${rozmiar}px ${kroj}`;
  const w = Math.ceil(g.measureText(tekst).width) + 2, h = Math.ceil(rozmiar * 1.4) + 2;
  c.width = w; c.height = h;
  g.font = `${rozmiar}px ${kroj}`; g.textBaseline = 'top'; g.fillStyle = '#fff';
  g.fillText(tekst, 1, 1);
  const d = g.getImageData(0, 0, w, h).data, px = new Int16Array((w + 1) * (h + 1)).fill(-1), W = w + 1;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (d[(y * w + x) * 4 + 3] > prog) {
    if (cien !== null && px[(y + 1) * W + x + 1] < 0) px[(y + 1) * W + x + 1] = cien;
    px[y * W + x] = k;
  }
  return { w: W, h: h + 1, px };
}

// ---------------------------------------------------------------- paleta i etapy
const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

// Paleta: lista kolorów (hex) i etapy: {nazwa: [indeks palety dla każdego slotu]}. Sloty to znaczenia (niebo, trawa,
// woda), nie kolory: etap 'noc' mówi, którym kolorem palety jest niebo nocą. Zmiana etapu = zmiana tablicy, nie rysunku.
export function paleta(kolory, etapy) {
  const rgb = kolory.map(hexRgb);
  const najblizszy = ([r, g, b]) => {
    let naj = 0, d0 = Infinity;
    rgb.forEach(([R, G, B], i) => { const d = 0.3 * (R - r) ** 2 + 0.59 * (G - g) ** 2 + 0.11 * (B - b) ** 2; if (d < d0) { d0 = d; naj = i; } });
    return naj;
  };
  return {
    rgb, etapy,
    // Tablica slot → kolor palety w przejściu etapu A → B (u 0–1) w `krokach` stopniach (3 = 1/3 i 2/3 po drodze),
    // każdy stopień to najbliższy kolor palety: pixel art nie miesza kolorów spoza palety.
    tablica(a, b = a, u = 0, kroki = 3) {
      const A = etapy[a], B = etapy[b], q = Math.round(clamp(u, 0, 1) * kroki) / kroki;
      return Uint8Array.from(A, (ka, s) => {
        if (q <= 0) return ka;
        if (q >= 1) return B[s];
        const x = rgb[ka], y = rgb[B[s]];
        return najblizszy(x.map((v, i) => v + (y[i] - v) * q));
      });
    },
  };
}

// Cykl kolorów (woda, wodospad, gwiazdy): slot przechodzi po liście kolorów co `co_klatek` klatek.
export const cykl = (lista, klatka, co_klatek = 3, przesun = 0) => lista[(Math.floor(klatka / co_klatek) + przesun) % lista.length];

// Bufor → RGBA (Uint8ClampedArray do ImageData): slot → tablica → kolor palety.
export function naRGBA(b, pal, tablica, out = new Uint8ClampedArray(b.w * b.h * 4)) {
  for (let i = 0; i < b.w * b.h; i++) {
    const c = pal.rgb[tablica ? tablica[b.px[i]] : b.px[i]];
    out[4 * i] = c[0]; out[4 * i + 1] = c[1]; out[4 * i + 2] = c[2]; out[4 * i + 3] = 255;
  }
  return out;
}
// Bufor na canvas `cel` w skali całkowitej (bez wygładzania). Do crt.js podaj mały canvas (skalę zrobi filtr).
export function pokaz(cel, b, pal, tablica) {
  const g = cel.getContext('2d');
  if (cel.width === b.w && cel.height === b.h) { g.putImageData(new ImageData(naRGBA(b, pal, tablica), b.w, b.h), 0, 0); return; }
  const m = Object.assign(document.createElement('canvas'), { width: b.w, height: b.h });
  m.getContext('2d').putImageData(new ImageData(naRGBA(b, pal, tablica), b.w, b.h), 0, 0);
  const s = Math.max(1, Math.floor(Math.min(cel.width / b.w, cel.height / b.h)));
  g.imageSmoothingEnabled = false;
  g.drawImage(m, Math.floor((cel.width - b.w * s) / 2), Math.floor((cel.height - b.h * s) / 2), b.w * s, b.h * s);
}
