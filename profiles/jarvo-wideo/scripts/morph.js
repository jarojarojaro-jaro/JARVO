// Przemiana kształtu w kształt (morph): obrysy próbkowane do tej samej liczby punktów, w tym samym kierunku,
// z najlepiej dobranym punktem startu; przejście przez koło (A → koło → B), żeby po drodze nie było supła;
// ściśnięcie przy uderzeniu bez zmiany pola; kolory mieszane w OKLab (bez szarego środka); smuga kropki.
// Strona: import { probkuj, przemiana, uderzenie, macierzScisku, mieszajKolor } from '/_lib/jarvo/morph.js';
// (html_wideo.py i podgląd HQ serwują ten plik pod /_lib/jarvo/; zasady stylu: style-motion/references/morph.md)
//
// Przeniesione z mg-styles-15 (MIT, Vincentwei1021, demos/08-morph/index.html), nazwy i opcje po polsku.

const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
const lerp = (a, b, u) => a + (b - a) * u;

// cubic-bezier jak w CSS (x → y). Krzywa przemiany ze wzoru: (0,7, 0, 0,3, 1): wolny start i koniec, szybki środek.
export function bezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx, cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const sx = (t) => ((ax * t + bx) * t + cx) * t, sy = (t) => ((ay * t + by) * t + cy) * t;
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let lo = 0, hi = 1, t = x;
    for (let i = 0; i < 40; i++) { const v = sx(t); if (Math.abs(v - x) < 1e-7) break; if (v < x) lo = t; else hi = t; t = (lo + hi) / 2; }
    return sy(t);
  };
}
export const KRZYWA = bezier(0.7, 0, 0.3, 1);

// ---------------------------------------------------------------- obrysy
// Ścieżka SVG (atrybut d) → n punktów co równą długość (potrzebny DOM: ukryty <svg> tworzony raz).
let _svg = null;
export function probkuj(d, n = 240, zamkniety = true) {
  if (!_svg) {
    _svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    _svg.setAttribute('style', 'position:absolute;width:0;height:0;overflow:hidden');
    document.body.appendChild(_svg);
  }
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', d);
  _svg.appendChild(p);
  const L = p.getTotalLength(), mian = zamkniety ? n : n - 1, out = [];
  for (let i = 0; i < n; i++) { const q = p.getPointAtLength(L * i / mian); out.push([q.x, q.y]); }
  _svg.removeChild(p);
  return zamkniety ? kierunek(out) : out;
}

export function pole(P) {
  let a = 0;
  for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; }
  return a / 2;
}
// Wszystkie obrysy w jednym kierunku (dodatnie pole), inaczej przemiana wywraca kształt na lewą stronę.
export const kierunek = (P) => (pole(P) < 0 ? P.slice().reverse() : P);
export function srodek(P) {
  let x = 0, y = 0;
  for (const p of P) { x += p[0]; y += p[1]; }
  return [x / P.length, y / P.length];
}

// Zamknięty wielokąt → n punktów co równą długość obwodu.
export function rownomiernie(P, n) {
  const L = [0];
  for (let i = 1; i <= P.length; i++) { const a = P[i - 1], b = P[i % P.length]; L.push(L[i - 1] + Math.hypot(b[0] - a[0], b[1] - a[1])); }
  const cala = L[P.length], out = [];
  let j = 0;
  for (let i = 0; i < n; i++) {
    const s = cala * i / n;
    while (L[j + 1] < s) j++;
    const a = P[j], b = P[(j + 1) % P.length], u = (s - L[j]) / ((L[j + 1] - L[j]) || 1);
    out.push([lerp(a[0], b[0], u), lerp(a[1], b[1], u)]);
  }
  return out;
}

export const kolo = (cx, cy, r, n) => Array.from({ length: n }, (_, i) => { const a = 2 * Math.PI * i / n; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; });

// Przesunięcie startu B, przy którym punkty B leżą najbliżej punktów A (suma kwadratów odległości).
export function najlepszePrzesuniecie(A, B) {
  const n = A.length;
  let naj = Infinity, ns = 0;
  for (let s = 0; s < n; s++) {
    let e = 0;
    for (let i = 0; i < n; i += 2) {
      const b = B[(i + s) % n], dx = A[i][0] - b[0], dy = A[i][1] - b[1];
      e += dx * dx + dy * dy;
      if (e >= naj) break;
    }
    if (e < naj) { naj = e; ns = s; }
  }
  return ns;
}
export const przesun = (B, s) => B.map((_, i) => B[(i + s) % B.length]);
export const dopasuj = (A, B) => przesun(B, najlepszePrzesuniecie(A, B));
export const mieszaj = (A, B, u) => A.map((a, i) => [lerp(a[0], B[i][0], u), lerp(a[1], B[i][1], u)]);

// Przygotowanie pary do przemiany (raz, przed renderem): ta sama liczba punktów, kierunek, start; przezKolo =
// koło o polu średnim z A i B w połowie drogi między ich środkami. Zwraca {A, B, kA, kB} dla przemiana().
export function para(A, B, { n = 240, przezKolo = true } = {}) {
  const a = kierunek(rownomiernie(A, n)), b = kierunek(rownomiernie(B, n));
  if (!przezKolo) return { A: a, B: dopasuj(a, b), kA: null, kB: null };
  const [ax, ay] = srodek(a), [bx, by] = srodek(b);
  const r = Math.sqrt((Math.abs(pole(a)) + Math.abs(pole(b))) / 2 / Math.PI);
  const k = kolo((ax + bx) / 2, (ay + by) / 2, r, n);
  return { A: a, B: dopasuj(k, b), kA: dopasuj(a, k), kB: k };
}

// Kształt w chwili u (0–1, liniowy postęp czasu przemiany). Każda połowa 9–12 klatek przy 30 kl./s (cała 0,6–0,8 s).
export function przemiana(p, u, krzywa = KRZYWA) {
  if (!p.kA) return mieszaj(p.A, p.B, krzywa(clamp(u)));
  return u < 0.5 ? mieszaj(p.A, p.kA, krzywa(clamp(u / 0.5))) : mieszaj(p.kB, p.B, krzywa(clamp((u - 0.5) / 0.5)));
}

// ---------------------------------------------------------------- uderzenie i ściśnięcie
// Drganie po uderzeniu (q: + ściśnięty wzdłuż osi, − wyciągnięty): A·sin(2πτ/okres)·e^(−tłumienie·τ), zaczyna się
// `wyprzedzenie` s przed chwilą lądowania t0 (2 klatki), żeby oko zobaczyło ściśnięcie razem z kontaktem.
export function uderzenie(t, t0, { A = 0.2, okres = 0.28, tlumienie = 7.5, wyprzedzenie = 2 / 30 } = {}) {
  const tau = t - (t0 - wyprzedzenie);
  if (tau < 0 || tau > 1.2) return 0;
  return A * Math.sin(2 * Math.PI * tau / okres) * Math.exp(-tau * tlumienie);
}

// Macierz [a, b, c, d] rozciągnięcia k wzdłuż kierunku phi (rad) i 1/k w poprzek: pole bez zmian.
// Lot: k = 1 + sq·sin(π·g) (sq 0,05–0,14), phi = kierunek ruchu. Canvas: g.transform(a, c, b, d, x, y).
export function macierzScisku(phi, k) {
  const cp = Math.cos(phi), sp = Math.sin(phi), ik = 1 / k;
  return [cp * cp * k + sp * sp * ik, cp * sp * (k - ik), cp * sp * (k - ik), sp * sp * k + cp * cp * ik];
}
export function przeksztalc(P, [a, b, c, d], [ox, oy] = [0, 0], [x, y] = [0, 0]) {
  return P.map(([px, py]) => { const u = px - ox, v = py - oy; return [x + ox + a * u + b * v, y + oy + c * u + d * v]; });
}

// ---------------------------------------------------------------- kolor i rysowanie
const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
const lin = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
const srgb = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055);
export function oklab(h) {
  const [r, g, b] = hexRgb(h).map(lin);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
          0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
export function zOklab([L, a, b]) {
  const l = Math.pow(L + 0.3963377774 * a + 0.2158037573 * b, 3), m = Math.pow(L - 0.1055613458 * a - 0.0638541728 * b, 3);
  const s = Math.pow(L - 0.0894841775 * a - 1.291485548 * b, 3);
  const rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
               -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
  return '#' + rgb.map((c) => Math.round(clamp(srgb(clamp(c))) * 255).toString(16).padStart(2, '0')).join('');
}
export function mieszajKolor(h1, h2, u) {
  if (u <= 0) return h1;
  if (u >= 1) return h2;
  const a = oklab(h1), b = oklab(h2);
  return zOklab(a.map((v, i) => lerp(v, b[i], u)));
}
export const ton = (h, dL) => { const a = oklab(h); a[0] += dL; return zOklab(a); };   // jaśniej (+) / ciemniej (−)

export function rysuj(g, P, kolor) {
  g.beginPath();
  g.moveTo(P[0][0], P[0][1]);
  for (let i = 1; i < P.length; i++) g.lineTo(P[i][0], P[i][1]);
  g.closePath();
  g.fillStyle = kolor;
  g.fill();
}

// Ścieżka SVG wielokąta z zaokrąglonymi rogami (r px albo lista r na róg): ikony z jednym promieniem rogu.
export function zaokraglony(pts, r) {
  const n = pts.length;
  let d = '';
  for (let i = 0; i < n; i++) {
    const p = pts[i], a = pts[(i - 1 + n) % n], b = pts[(i + 1) % n], rr = Array.isArray(r) ? r[i] : r;
    const da = Math.hypot(a[0] - p[0], a[1] - p[1]), db = Math.hypot(b[0] - p[0], b[1] - p[1]);
    const k1 = Math.min(rr, da / 2) / da, k2 = Math.min(rr, db / 2) / db;
    d += `${i ? 'L' : 'M'}${p[0] + (a[0] - p[0]) * k1},${p[1] + (a[1] - p[1]) * k1}Q${p[0]},${p[1]} ${p[0] + (b[0] - p[0]) * k2},${p[1] + (b[1] - p[1]) * k2}`;
  }
  return d + 'Z';
}

// Smuga kropki (Canvas 2D): krążek o promieniu r przesunięty z pA do pB w czasie migawki = kapsuła z liniowym
// zanikiem na końcach (tak wygląda prawdziwe rozmycie ruchu krążka). Zamiast motion bluru, bez kosztu renderu.
export function smugaKropki(g, pA, pB, r, kolor) {
  const dx = pB[0] - pA[0], dy = pB[1] - pA[1], L = Math.hypot(dx, dy), mx = (pA[0] + pB[0]) / 2, my = (pA[1] + pB[1]) / 2;
  if (L < 1.5) { g.fillStyle = kolor; g.beginPath(); g.arc(mx, my, r, 0, 2 * Math.PI); g.fill(); return; }
  const [R, G, B] = hexRgb(kolor).map((v) => Math.round(v * 255)), c = (a) => `rgba(${R},${G},${B},${a})`;
  const ux = dx / L, uy = dy / L, T = L + 2 * r, am = Math.min(1, 2 * r / L), o1 = Math.min(2 * r, L) / T, kat = Math.atan2(dy, dx);
  const gr = g.createLinearGradient(mx - ux * T / 2, my - uy * T / 2, mx + ux * T / 2, my + uy * T / 2);
  gr.addColorStop(0, c(0)); gr.addColorStop(o1, c(am)); gr.addColorStop(1 - o1, c(am)); gr.addColorStop(1, c(0));
  g.fillStyle = gr;
  g.beginPath();
  g.arc(pA[0], pA[1], r, kat + Math.PI / 2, kat + 3 * Math.PI / 2);
  g.arc(pB[0], pB[1], r, kat - Math.PI / 2, kat + Math.PI / 2);
  g.closePath();
  g.fill();
}
