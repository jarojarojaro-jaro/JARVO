// Ruch Jarva dla własnych animacji HTML (kontrakt `jarvo`): charakter ruchu z marki, lądowanie, wyjście i smugi
// zamiast motion bluru. Same czyste funkcje czasu `t` (sekundy): każdą klatkę da się policzyć osobno.
// Strona: import { CHARAKTERY, ladowanie, wyjscie, smuga } from '/_lib/jarvo/ruch.js';
// (html_wideo.py i podgląd HQ serwują ten plik pod /_lib/jarvo/; zasady: rodzaje-filmu/references/ruch-i-kompozycja.md)
//
// Liczby charakterów za video-shotcraft (Apache-2.0, Vincent Wei, „品牌→动效参数”): czas głównego ruchu przy 30 kl./s,
// krzywa wejścia, przestrzelenie skali i ściśnięcie przy lądowaniu.

export const CHARAKTERY = Object.freeze({
  zaufanie:  Object.freeze({ dla: 'B2B, finanse, prawo, usługi dla firm', czas: 0.70, krzywa: [0, 0, 0.2, 1], przestrzal: 1.00, sciskanie: 0 }),
  luksus:    Object.freeze({ dla: 'premium, moda, biżuteria, hotele', czas: 1.60, krzywa: [0.4, 0, 0.6, 1], przestrzal: 1.02, sciskanie: 0 }),
  odwazny:   Object.freeze({ dla: 'sport, gry, startupy, energia', czas: 0.60, krzywa: [0.16, 1, 0.3, 1], przestrzal: 1.12, sciskanie: 0.25 }),
  zabawny:   Object.freeze({ dla: 'produkty konsumenckie, social, dzieci', czas: 0.90, krzywa: [0.34, 1.56, 0.64, 1], przestrzal: 1.08, sciskanie: 0.18 }),
  spokojny:  Object.freeze({ dla: 'zdrowie, edukacja, opieka', czas: 1.40, krzywa: [0.42, 0, 0.58, 1], przestrzal: 1.00, sciskanie: 0.04 }),
  przyjazny: Object.freeze({ dla: 'mała firma, lokalne usługi, społeczność', czas: 0.87, krzywa: [0.25, 0.46, 0.45, 0.94], przestrzal: 1.04, sciskanie: 0.08 }),
});

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, u) => a + (b - a) * u;

// cubic-bezier jak w CSS: x (postęp czasu 0–1) → y (postęp ruchu; krzywa z y > 1 przestrzeliwuje)
export function bezier(x1, y1, x2, y2) {
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let a = 0, b = 1, t = x;
    for (let i = 0; i < 30; i++) {
      t = (a + b) / 2;
      const u = 1 - t, bx = 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t;
      if (bx < x) a = t; else b = t;
    }
    const u = 1 - t;
    return 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t;
  };
}

export function charakter(nazwa) {
  const c = typeof nazwa === 'string' ? CHARAKTERY[nazwa] : nazwa;
  if (!c) throw new Error(`nieznany charakter ruchu: ${nazwa} (${Object.keys(CHARAKTERY).join(', ')})`);
  return c;
}

// Wejście elementu od chwili t0. Zwraca {p, skala, sx, sy, u}:
//   p      postęp drogi 0 → 1 (pozycja: lerp(start, cel, p); krzywa „zabawny” chwilę przestrzeli),
//   skala  od `od` (domyślnie 0,92, nigdy od 0) do `przestrzal` w 3/4 czasu, potem osiada na 1,
//   sx, sy rozciągnięcie w locie i ściśnięcie przy lądowaniu (oś ruchu = sy; stała objętość), 1 bez ściskania,
//   u      postęp czasu 0 → 1 (1 = wylądował: od tej chwili liczy się oddech).
export function ladowanie(t, t0, nazwa, opcje = {}) {
  const c = charakter(nazwa);
  const czas = (opcje.czas ?? c.czas) * (opcje.tempo ?? 1);
  const u = clamp((t - t0) / czas);
  const p = bezier(...c.krzywa)(u);
  const od = opcje.od ?? 0.92;
  const skala = u < 0.75 ? lerp(od, c.przestrzal, clamp(bezier(...c.krzywa)(u / 0.75)))
                         : lerp(c.przestrzal, 1, bezier(0.42, 0, 0.58, 1)((u - 0.75) / 0.25));
  let sy = 1;
  if (c.sciskanie && u > 0 && u < 1) {
    sy = u < 0.7 ? 1 + 0.5 * c.sciskanie * Math.sin(Math.PI * u / 0.7)     // lot: wyciągnięty wzdłuż ruchu
                 : 1 - 0.6 * c.sciskanie * Math.sin(Math.PI * (u - 0.7) / 0.3);   // lądowanie: ściśnięty
  }
  return { p, skala, sx: 1 / sy, sy, u };
}

// Wyjście od chwili t1: szybsze i lżejsze niż wejście (połowa czasu, przyspiesza). Zwraca {p: 1 → 0, krycie, u}.
export function wyjscie(t, t1, nazwa, opcje = {}) {
  const c = charakter(nazwa);
  const czas = (opcje.czas ?? c.czas * 0.5) * (opcje.tempo ?? 1);
  const u = clamp((t - t1) / czas);
  const p = 1 - bezier(0.4, 0, 1, 1)(u);
  return { p, krycie: p, u };
}

// Szybkość (jednostki/s) pozycji `poz(t)` → do decyzji, czy rysować smugę (np. > 0,8 szerokości kadru na sekundę).
export function predkosc(poz, t, dt = 1 / 60) {
  const a = poz(t - dt), b = poz(t);
  const dx = (b[0] ?? b.x) - (a[0] ?? a.x), dy = (b[1] ?? b.y) - (a[1] ?? a.y);
  return Math.hypot(dx, dy) / dt;
}

// Smuga (Canvas 2D) zamiast motion bluru: kapsuła od pozycji sprzed `migawka` s do teraz, ogon przezroczysty,
// głowa pełna, a na niej ostry kształt. Tylko przy szybkim ruchu; nigdy na tekście do czytania.
export function smuga(g, poz, t, r, kolor, migawka = 1 / 30) {
  const a = poz(t - migawka), b = poz(t);
  const ax = a[0] ?? a.x, ay = a[1] ?? a.y, bx = b[0] ?? b.x, by = b[1] ?? b.y;
  if (Math.hypot(bx - ax, by - ay) < 0.5) return false;
  g.save();
  const grad = g.createLinearGradient(ax, ay, bx, by);
  grad.addColorStop(0, przezroczysty(kolor));
  grad.addColorStop(1, kolor);
  g.strokeStyle = grad; g.lineCap = 'round'; g.lineWidth = 2 * r;
  g.beginPath(); g.moveTo(ax, ay); g.lineTo(bx, by); g.stroke();
  g.restore();
  return true;
}

// Duchy („multiples” z animacji rysunkowej): `n` kopii za obiektem co `odstep` s, coraz słabszych.
// rysuj(t_kopii, krycie) rysuje obiekt w jego położeniu z chwili t_kopii. Najpierw duchy, na końcu obiekt.
export function duchy(t, rysuj, n = 3, odstep = 1 / 60, krycie = 0.5) {
  for (let i = n; i >= 1; i--) rysuj(t - i * odstep, krycie * Math.pow(0.5, i - 1));
  rysuj(t, 1);
}

// Rozciągnięcie wzdłuż ruchu dla elementu DOM/SVG: {sx, sy} przy szybkości v (px/s); spoczynek = 1, najwyżej +25%.
// transform: `rotate(${kąt}rad) scale(${sx}, ${sy}) rotate(${-kąt}rad)`, kąt = kierunek ruchu.
export function rozciagniecie(v, k = 0.00025, max = 0.25) {
  const s = Math.min(max, Math.abs(v) * k);
  return { sx: 1 + s, sy: 1 / (1 + s) };
}

function przezroczysty(kolor) {
  const m = /^#([0-9a-f]{6})$/i.exec(kolor);
  if (m) return `#${m[1]}00`;
  const r = /^rgba?\(([^)]+)\)$/i.exec(kolor);
  if (r) { const [x, y, z] = r[1].split(/[ ,/]+/); return `rgba(${x}, ${y}, ${z}, 0)`; }
  return 'rgba(0, 0, 0, 0)';
}
