// Kreska rysowana ręcznie (animacja rysunkowa, „cel”): linia z piórka (zwężenie na końcach, nacisk, cięższa strona
// cienia), wrzenie linii (line boil: każdy rysunek trochę inny), kolor przesunięty względem konturu jak przy ręcznym
// kolorowaniu i arkusz ekspozycji (rysunek na jedynkach, dwójkach, trójkach). Same czyste funkcje: ta sama klatka
// daje ten sam rysunek, więc render klatka po klatce i w kilku przeglądarkach naraz zgadza się z podglądem.
// Strona: import { ekspozycja, kreska, petla, wypelnij, kreskowanie, PRZESUNIECIE } from '/_lib/jarvo/kreska.js';
// (html_wideo.py i podgląd HQ serwują ten plik pod /_lib/jarvo/; zasady stylu: style-motion/references/kreska.md)
//
// Przeniesione z mg-styles-15 (MIT, Vincentwei1021, demos/05-cel-boil: js/engine.js i arkusz z js/scene.js);
// szum własny zamiast biblioteki simplex-noise, nazwy i opcje po polsku.

export const TUSZ = '#1c1613';
export const PRZESUNIECIE = Object.freeze({ dx: -5, dy: 4 });   // kolor względem konturu (px przy 1920×1080)

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, u) => a + (b - a) * u;
const gladko = (a, b, x) => { const u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u); };

// Liczby → [0, 1): ta sama lista liczb zawsze daje to samo (losowość bez Math.random).
export function hash(...liczby) {
  let h = 2166136261 >>> 0;
  for (const v of liczby) {
    h = Math.imul(h ^ ((Math.round(v * 997) | 0) >>> 0), 16777619) >>> 0;
    h ^= h >>> 13; h = Math.imul(h, 0x5bd1e995) >>> 0; h ^= h >>> 15;
  }
  return (h >>> 0) / 4294967296;
}

// Szum gradientowy 3D (Perlin, stała permutacja): gładki, w przybliżeniu −1…1, ten sam w każdej przeglądarce.
const PERM = (() => {
  const p = Array.from({ length: 256 }, (_, i) => i);
  let a = 0x5eed1e;
  const los = () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  for (let i = 255; i > 0; i--) { const j = Math.floor(los() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; }
  return Uint8Array.from([...p, ...p]);
})();
const fade = (t) => t * t * t * (t * (t * 6 - 15) + 10);
const grad = (h, x, y, z) => {
  const k = h & 15, u = k < 8 ? x : y, v = k < 4 ? y : (k === 12 || k === 14 ? x : z);
  return ((k & 1) ? -u : u) + ((k & 2) ? -v : v);
};
export function szum(x, y, z) {
  const X = Math.floor(x) & 255, Y = Math.floor(y) & 255, Z = Math.floor(z) & 255;
  x -= Math.floor(x); y -= Math.floor(y); z -= Math.floor(z);
  const u = fade(x), v = fade(y), w = fade(z), P = PERM;
  const A = P[X] + Y, AA = P[A] + Z, AB = P[A + 1] + Z, B = P[X + 1] + Y, BA = P[B] + Z, BB = P[B + 1] + Z;
  return lerp(lerp(lerp(grad(P[AA], x, y, z), grad(P[BA], x - 1, y, z), u),
                   lerp(grad(P[AB], x, y - 1, z), grad(P[BB], x - 1, y - 1, z), u), v),
              lerp(lerp(grad(P[AA + 1], x, y, z - 1), grad(P[BA + 1], x - 1, y, z - 1), u),
                   lerp(grad(P[AB + 1], x, y - 1, z - 1), grad(P[BB + 1], x - 1, y - 1, z - 1), u), v), w);
}

// ---------------------------------------------------------------- arkusz ekspozycji
// plan = [[od_klatki, krok], …] rosnąco: krok 2 = rysunek na dwójkach (12 rysunków/s przy 24 kl./s), 1 = na jedynkach
// (szybka akcja: uderzenie, obrót), 3 = na trójkach (zawieszenie, „ta-da”). Zwraca {f: klatka rysunku (do niej liczysz
// ruch postaci), id: numer rysunku, krok, wariant: 0–3 (0–2 na trójkach) dla rzeczy stojących: wrzenie w pętli}.
export function ekspozycja(klatka, plan = [[0, 2]]) {
  let id = 0;
  for (let i = 0; i < plan.length; i++) {
    const [a, krok] = plan[i], b = i + 1 < plan.length ? plan[i + 1][0] : Infinity;
    if (klatka >= b) { id += Math.ceil((b - a) / krok); continue; }
    const k = Math.floor((Math.max(klatka, a) - a) / krok);
    return { f: a + k * krok, id: id + k, krok, wariant: (id + k) % (krok === 3 ? 3 : 4) };
  }
  return { f: klatka, id, krok: 1, wariant: id % 4 };
}

// To samo w sekundach: {...ekspozycja, t: czas rysunku (ruch postaci), t1: czas klatki (szybkie efekty, iskry)}.
export function rysunek(t, fps = 24, plan = [[0, 2]]) {
  const klatka = Math.round(t * fps), e = ekspozycja(klatka, plan);
  return { ...e, t: e.f / fps, t1: klatka / fps };
}

// ---------------------------------------------------------------- geometria
// Splajn Catmull-Rom (dośrodkowy, bez pętelek) przez punkty [x, y, naroznik?]; naroznik = ostry róg zamiast łuku.
function crp(p0, p1, p2, p3, t) {
  const d = (p, q) => Math.sqrt(Math.hypot(q[0] - p[0], q[1] - p[1])) + 1e-4;
  const t1 = d(p0, p1), t2 = t1 + d(p1, p2), t3 = t2 + d(p2, p3), tt = t1 + (t2 - t1) * t;
  const L = (a, b, ta, tb) => { const w = (tt - ta) / (tb - ta); return [a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w]; };
  const A1 = L(p0, p1, 0, t1), A2 = L(p1, p2, t1, t2), A3 = L(p2, p3, t2, t3);
  return L(L(A1, A2, 0, t2), L(A2, A3, t1, t3), t1, t2);
}
export function splajn(P, zamkniety = false, krok = 5) {
  const n = P.length, out = [];
  if (n < 2) return P.map((p) => [p[0], p[1]]);
  for (let i = 0; i < (zamkniety ? n : n - 1); i++) {
    const p1 = P[i], p2 = P[(i + 1) % n];
    let p0 = zamkniety ? P[(i - 1 + n) % n] : P[Math.max(0, i - 1)];
    let p3 = zamkniety ? P[(i + 2) % n] : P[Math.min(n - 1, i + 2)];
    if (p1[2]) p0 = p1;
    if (p2[2]) p3 = p2;
    const m = Math.max(1, Math.ceil(Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / krok));
    for (let k = 0; k < m; k++) out.push(crp(p0, p1, p2, p3, k / m));
  }
  if (!zamkniety) out.push([P[n - 1][0], P[n - 1][1]]);
  return out;
}

export function dlugosci(pts, zamkniety = false) {
  const L = [0];
  for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  if (zamkniety && pts.length > 1) L.push(L.at(-1) + Math.hypot(pts[0][0] - pts.at(-1)[0], pts[0][1] - pts.at(-1)[1]));
  return L;
}

// Punkty co `krok` px wzdłuż linii (gęsta, równa linia pod wrzenie i piórko).
export function rownomiernie(pts, krok = 3.5, zamkniety = false) {
  const src = zamkniety ? [...pts, pts[0]] : pts, L = dlugosci(src), cala = L.at(-1);
  if (cala < 1e-6) return [src[0].slice(0, 2)];
  const n = Math.max(2, Math.round(cala / krok)), out = [];
  let j = 1;
  for (let i = 0; i < (zamkniety ? n : n + 1); i++) {
    const s = cala * i / n;
    while (j < L.length - 1 && L[j] < s) j++;
    const a = src[j - 1], b = src[j], u = (s - L[j - 1]) / Math.max(1e-9, L[j] - L[j - 1]);
    out.push([a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u]);
  }
  return out;
}

// Początek linii do `czesc` jej długości (0–1): rysowanie linii na oczach widza.
export function poczatek(pts, czesc) {
  if (czesc >= 1) return pts;
  const L = dlugosci(pts), s = L.at(-1) * Math.max(0, czesc), out = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    if (L[i] <= s) { out.push(pts[i]); continue; }
    const u = (s - L[i - 1]) / Math.max(1e-9, L[i] - L[i - 1]);
    out.push([lerp(pts[i - 1][0], pts[i][0], u), lerp(pts[i - 1][1], pts[i][1], u)]);
    break;
  }
  return out;
}

// Skala (sx, sy), pochylenie kx, obrót r (rad), przesunięcie (x, y): punkty postaci w jej pozie.
export function przeksztalc(P, { x = 0, y = 0, r = 0, sx = 1, sy = 1, kx = 0 } = {}) {
  const c = Math.cos(r), s = Math.sin(r);
  return P.map((p) => { const px = p[0] * sx - kx * p[1] * sy, py = p[1] * sy; return [x + px * c - py * s, y + px * s + py * c, p[2]]; });
}

export function okrag(cx, cy, r, n = 0, rx = null) {
  n = n || Math.max(10, Math.round(2 * Math.PI * r / 5));
  return Array.from({ length: n }, (_, i) => { const a = i / n * 2 * Math.PI; return [cx + (rx ?? r) * Math.cos(a), cy + r * Math.sin(a)]; });
}

// ---------------------------------------------------------------- wrzenie i piórko
// Wrzenie: każdy punkt przesunięty polem szumu w przestrzeni kadru; nowe `ziarno` = nowy rysunek. Rzeczy w ruchu:
// ziarno = id rysunku; rzeczy stojące: ziarno = wariant (pętla 4 rysunków). amp 2,2–2,4 px, skala 70 px (1920×1080);
// napisy spokojniej (1,6 przy 80), małe litery 0,9 przy 30. W zbliżeniu mnóż amp przez skalę kadru (0,55–0,7).
export function wrzenie(pts, ziarno, amp = 2.4, skala = 70) {
  if (!amp) return pts.map((p) => [p[0], p[1]]);
  const z = ziarno * 2.371 + 0.5;
  return pts.map(([x, y]) => [x + amp * szum(x / skala, y / skala, z), y + amp * szum(x / skala + 41.3, y / skala - 17.9, z)]);
}

// Obrys linii o zmiennej szerokości: szer(u, s, i, tx, ty) → px (u = 0–1 wzdłuż, s = px od początku, t = kierunek).
export function obrys(pts, szer, konce = true) {
  const n = pts.length;
  if (n < 2) return [];
  const L = dlugosci(pts), cala = L[n - 1] || 1, lewa = [], prawa = [];
  let w0 = 0, wN = 0;
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
    let tx = b[0] - a[0], ty = b[1] - a[1];
    const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
    const w = Math.max(0, szer(L[i] / cala, L[i], i, tx, ty)) / 2;
    if (i === 0) w0 = w;
    if (i === n - 1) wN = w;
    lewa.push([pts[i][0] - ty * w, pts[i][1] + tx * w]);
    prawa.push([pts[i][0] + ty * w, pts[i][1] - tx * w]);
  }
  const poly = [...lewa];
  const koniec = (c, a0, w) => {
    if (w < 0.6 || !konce) return;
    for (let k = 1; k < 8; k++) { const a = a0 - Math.PI * k / 8; poly.push([c[0] + Math.cos(a) * w, c[1] + Math.sin(a) * w]); }
  };
  koniec(pts[n - 1], Math.atan2(pts[n - 1][1] - pts[n - 2][1], pts[n - 1][0] - pts[n - 2][0]) + Math.PI / 2, wN);
  for (let i = n - 1; i >= 0; i--) poly.push(prawa[i]);
  koniec(pts[0], Math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]) - Math.PI / 2, w0);
  return poly;
}

export function sciezka(g, poly, zamknij = true) {
  if (!poly.length) return;
  g.moveTo(poly[0][0], poly[0][1]);
  for (let i = 1; i < poly.length; i++) g.lineTo(poly[i][0], poly[i][1]);
  if (zamknij) g.closePath();
}
export function wielokat(g, poly, kolor, regula = 'nonzero') {
  g.beginPath(); sciezka(g, poly); g.fillStyle = kolor; g.fill(regula);
}

// Piórko: szerokość w (px) × nacisk (±35% szumem wzdłuż linii) × cięższa strona cienia (prawy dół, +35%)
// × zwężenie: `wejscie` px na początku, `wyjscie` px na końcu, do `min` (25%) szerokości. waga = skala kadru.
export function piorko({ w = 6, ziarno = 1, wejscie = 14, wyjscie = 26, nacisk = 0.35, min = 0.25, cien = 0.35,
                         lx = 0.55, ly = 0.83, dlugosc = null, zwezenie = true, waga = 1 } = {}) {
  return (u, s, i, tx, ty) => {
    let k = 1 + nacisk * szum(s / 60, ziarno * 1.37, 3.1);
    k *= 1 + cien * Math.max(0, ty * lx - tx * ly);
    if (zwezenie && dlugosc) k *= min + (1 - min) * Math.min(gladko(0, wejscie, s), gladko(0, wyjscie, dlugosc - s));
    return w * k * waga;
  };
}

// Otwarta kreska przez punkty kontrolne P (splajn → równo co 3,2 px → wrzenie → piórko). Zwraca punkty linii.
export function kreska(g, P, o = {}) {
  const { ziarno = 1, amp = 2.2, skala = 70, krok = 5, kolor = TUSZ, gesta = false, waga = 1 } = o;
  let pts = gesta ? P : splajn(P, false, krok);
  pts = wrzenie(rownomiernie(pts, 3.2), ziarno, amp * waga, skala);
  const dlugosc = dlugosci(pts).at(-1);
  wielokat(g, obrys(pts, o.szer ? o.szer(dlugosc) : piorko({ ...o, dlugosc }), o.konce ?? true), kolor);
  return pts;
}

// Zamknięty kontur (gęste punkty, np. z okrag albo splajn(P, true)) narysowany 1–2 pociągnięciami pióra, które
// zachodzą na siebie o `zakladka` obwodu i wyjeżdżają `wyjazd` px poza linię: tak wygląda ręczny tusz.
export function petla(g, gesta, o = {}) {
  const { ziarno = 1, amp = 2.2, skala = 70, kolor = TUSZ, pociagniecia = 1, zakladka = 0.05, wyjazd = 2.5, waga = 1 } = o;
  const pts = wrzenie(rownomiernie(gesta, 3.2, true), ziarno, amp * waga, skala), n = pts.length;
  if (n < 6) return pts;
  let pole = 0;
  for (let i = 0; i < n; i++) { const p = pts[i], q = pts[(i + 1) % n]; pole += p[0] * q[1] - q[0] * p[1]; }
  const znak = pole > 0 ? 1 : -1, s0 = Math.floor(hash(ziarno, 7) * n), ciecia = [];
  for (let k = 0; k < pociagniecia; k++) ciecia.push(Math.floor(s0 + n * k / pociagniecia + (hash(ziarno, 9, k) - 0.5) * n * 0.15));
  for (let k = 0; k < pociagniecia; k++) {
    const a = ciecia[k], b = k + 1 < pociagniecia ? ciecia[k + 1] : ciecia[0] + n, ext = Math.max(2, Math.floor(n * zakladka));
    const odc = [];
    for (let j = a; j <= b + ext; j++) {
      const p = pts[((j % n) + n) % n];
      if (j <= b) { odc.push(p); continue; }
      const q = pts[(((j + 1) % n) + n) % n], r0 = pts[(((j - 1) % n) + n) % n];
      let tx = q[0] - r0[0], ty = q[1] - r0[1];
      const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
      const off = (j - b) / ext * wyjazd * znak;
      odc.push([p[0] - ty * off, p[1] + tx * off]);
    }
    const sz = piorko({ ...o, ziarno: ziarno + k * 13, dlugosc: dlugosci(odc).at(-1), wejscie: o.wejscie ?? 10, wyjscie: o.wyjscie ?? 22 });
    wielokat(g, obrys(odc, znak > 0 ? sz : (u, s, i, tx, ty) => sz(u, s, i, -tx, -ty)), kolor);
  }
  return pts;
}

// Płaski kolor pod konturem: własne wrzenie (inne ziarno niż tusz) i przesunięcie {dx, dy} (PRZESUNIECIE).
export function wypelnij(g, gesta, kolor, o = {}) {
  const { ziarno = 1, amp = 2.2, skala = 70, dx = 0, dy = 0, waga = 1 } = o;
  const pts = wrzenie(gesta, ziarno + 0.5, amp * waga, skala).map((p) => [p[0] + dx, p[1] + dy]);
  wielokat(g, pts, kolor);
  return pts;
}

// Kreskowanie (cień rysowany ręcznie) wewnątrz wielokąta: linie co `odstep` px pod kątem `kat` (rad).
export function kreskowanie(g, poly, o = {}) {
  const { ziarno = 1, odstep = 14, kat = -0.9, w = 2.2, kolor = TUSZ, amp = 1.6, rozrzut = 0.35 } = o;
  g.save();
  g.beginPath(); sciezka(g, poly); g.clip();
  const c = Math.cos(kat), s = Math.sin(kat);
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of poly) { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); }
  const R = Math.hypot(x1 - x0, y1 - y0) / 2 + 10, mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
  let k = 0;
  for (let d = -R; d <= R; d += odstep, k++) {
    const off = d + (hash(ziarno, k) - 0.5) * odstep * rozrzut, px = mx - s * off, py = my + c * off;
    kreska(g, [[px - c * R * 1.1, py - s * R * 1.1], [px + c * R * 1.1, py + s * R * 1.1]],
           { ziarno: ziarno * 31 + k, amp, w: w * (0.8 + 0.4 * hash(ziarno, k, 2)), wejscie: 8, wyjscie: 8, nacisk: 0.3, cien: 0, kolor });
  }
  g.restore();
}
