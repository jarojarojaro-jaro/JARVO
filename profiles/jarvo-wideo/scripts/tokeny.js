// Tokeny ruchu z biblioteki ruchów (cinetic, MIT, Copyright (c) 2026 Leonxlnx): nazwane krzywe E, sprężyny SPR,
// puls uderzenia i mieszanie kolorów w OKLab, przeniesione do kontraktu `jarvo`. Przepisy z `ruchy.py` mówią tymi
// nazwami (`E.out`, `prog`, `lmix`, `hitPulse`, `mixColor`…), więc tu znaczą to samo, tylko czas jest w SEKUNDACH:
// liczby klatek z przepisu (60 kl./s) zamieniasz przez f(n) = n / 60. Same czyste funkcje: każdą klatkę da się policzyć osobno.
// Strona: import { E, SPR, prog, f } from '/_lib/jarvo/tokeny.js';   (tłumaczenie: losowanie-ruchow/references/przepisy.md)

import { bezier } from './ruch.js';

/** Klatki przepisu (60 kl./s) → sekundy: f(18) = 0,3 s. */
export const f = (n) => n / 60;
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const mix = (a, b, u) => a + (b - a) * u;
/** Skala i zoom w przestrzeni logarytmicznej: równe proporcje na klatkę, zoom nigdy nie „pędzi” na końcu. */
export const lmix = (a, b, u) => Math.exp(mix(Math.log(a), Math.log(b), u));

function wykladnicza(k) {
  const n = 1 - Math.exp(-k);
  return (p) => (p <= 0 ? 0 : p >= 1 ? 1 : (1 - Math.exp(-k * p)) / n);
}

// Krzywe nazwane od odczucia. Wejścia hamują (out), wyjścia przyspieszają (in, exit); w obie strony tylko kamera.
export const E = Object.freeze({
  out: bezier(0.16, 1, 0.3, 1),          // przybycia i odsłony (nigdy zanik)
  outSoft: bezier(0.22, 1, 0.36, 1),     // łagodne osiadanie, słowa
  in: bezier(0.7, 0, 0.84, 0),           // implozje, twarde wyjścia
  exit: bezier(0.55, 0.055, 0.675, 0.19), // wyjście w cięcie: najszybsza klatka na cięciu
  inOut: bezier(0.87, 0, 0.13, 1),       // śmignięcia, przesunięcia blokady
  smooth: bezier(0.65, 0, 0.35, 1),      // zaniki 10–14 kl., dryf, oddech
  ui: bezier(0.4, 0, 0.2, 1),            // małe zmiany UI: przełącznik, chip, wiersz
  cam: bezier(0.48, 0.1, 0, 0.9),        // kamera: wolny start, szczyt ~27%, długie osiadanie
  glide: bezier(0.47, 0.2, 0.15, 1),     // przesunięcia 150–350 px z miękkim lądowaniem
  rest: bezier(0.45, 0, 0.1, 1),         // ruch kończący się w spoczynku; łańcuch po innym ruchu
  contact: bezier(0.55, 0, 0.9, 0.55),   // przyspiesza W uderzenie (kończy z prędkością)
  whip: bezier(0.6, 0, 0.15, 1),         // śmignięcie z funkcji do funkcji, 24–30 kl.
  dolly: bezier(0.35, 0, 0.65, 1),       // powolny najazd przez trzymanie
  type: bezier(0.5, 1, 0.89, 1),         // liczba znaków pisanego tekstu
  expo: wykladnicza(6),                  // wyśrodkowanie linii budowanej (połowa w 12% czasu)
  linear: (p) => clamp(p),               // tylko dryf i zegary
});

/** Postęp 0–1 między chwilami a i b po krzywej (zawsze przycięty). Jednostki dowolne, byle te same co t. */
export const prog = (t, a, b, krzywa = E.out) => krzywa(clamp((t - a) / (b - a)));
/** Wartość od v0 do v1 między chwilami a i b po krzywej (przycięta). */
export const tw = (t, a, b, v0, v1, krzywa = E.out) => mix(v0, v1, prog(t, a, b, krzywa));

/** Ruch pionowy tekstu kończy się w k krzywej, gdy jeszcze jedzie ~1 px/kl. (Chromium dosuwa tekst do pełnych pikseli). */
export const arrive = (p, k = 0.94) => clamp(p / k);
/** Wyjście pomija powolny start krzywej. */
export const depart = (q, k = 0.06) => clamp((q - k) / (1 - k));
/** Rozmycie wejścia znika do 60% ruchu (Chromium rysuje promień skokami ~0,5 px, poniżej ~0,75 px ostro). */
export const blurIn = (p, px) => px * clamp(1 - p / 0.6);
/** Rozmycie wyjścia dopiero, gdy element już jedzie. */
export const blurOut = (q, px) => px * clamp((q - 0.3) / 0.7);
/** Oddech trzymanego kadru: 1 + amount · u (u = prog trzymania po E.smooth). */
export const breath = (u, amount = 0.025) => 1 + amount * u;
/** Przesunięcie startu elementu i z n rozłożone na `rozpietosc` (krzywa kształtuje odstępy). */
export const stagger = (i, n, rozpietosc, krzywa = E.linear) => (n > 1 ? rozpietosc * krzywa(clamp(i / (n - 1))) : 0);
/** Klatka całkowita dla stanów dyskretnych (liczone znaki, liczniki): fd(t * 60) / 60. */
export const fd = Math.round;

/** Puls uderzenia: 0 → 1 w `attack` (ćwiartka sinusa), potem e^(−(t−attack)/tau); znika po attack + 6·tau. Sekundy. */
export function hitPulse(t, attack = f(2), tau = f(5)) {
  return t <= 0 || t > attack + 6 * tau ? 0 : t < attack ? Math.sin((t / attack) * (Math.PI / 2)) : Math.exp(-(t - attack) / tau);
}
/** Docisk przy lądowaniu `t` s po kontakcie: 10% płaściej wzdłuż uderzenia, 8% szerzej w poprzek. */
export function squash(t) {
  const k = hitPulse(t, f(1), f(4));
  return { along: 1 - 0.1 * k, across: 1 + 0.08 * k };
}

/** Przewijanie z bezwładnością od chwili t0 z prędkością v0 (px/s), traci (1 − decay) prędkości na klatkę 60 kl./s. */
export function inertia(t, t0, v0, decay = 0.89) {
  const tau = -1 / Math.log(clamp(decay, 1e-6, 0.999999)) / 60;   // sekundy
  const n = t - t0;
  const total = v0 * tau;
  if (n <= 0) return { x: v0 * n, v: v0, total };
  const k = Math.exp(-n / tau);
  return { x: total * (1 - k), v: v0 * k, total };
}

// Sprężyny (masa, tłumienie, sztywność) jak w przepisach. Tekst nigdy nie przestrzeliwuje: słowa po krzywej
// albo SPR.calm; przestrzelenie tylko przy prawdziwym lądowaniu (najwyżej 2 na film).
export const SPR = Object.freeze({
  snap: { damping: 18, stiffness: 260, mass: 0.7 },   // zatrzask z małym przestrzeleniem (6%)
  pop: { damping: 11, stiffness: 180, mass: 0.6 },    // 14%: mały przedmiot ląduje w gnieździe
  land: { damping: 14.5, stiffness: 200, mass: 1 },   // 15%: prawdziwe odbicie przy lądowaniu
  micro: { damping: 30, stiffness: 500, mass: 0.6 },  // chipy, plakietki
  firm: { damping: 24, stiffness: 140, mass: 1 },     // bez przestrzelenia: wejścia UI
  soft: { damping: 26, stiffness: 120, mass: 1 },     // ciężkie: panele, karty, duży tekst
  heavy: { damping: 30, stiffness: 90, mass: 1.4 },   // całe płaszczyzny
  word: { damping: 20, stiffness: 170, mass: 0.9 },   // słowa dosuwane do blokady (przycinaj przestrzelenie)
  detent: { damping: 24, stiffness: 380, mass: 0.6 }, // bęben albo wybierak klika na miejsce
  calm: { damping: 16, stiffness: 64, mass: 1 },      // krytycznie tłumiona: jedyna sprężyna dla tekstu
});

/** Położenie sprężyny od spoczynku do 1 po `t` s (wzór zamknięty, bez stanu między klatkami). */
export function sprezyna(t, cfg = SPR.firm) {
  if (t <= 0) return 0;
  const k = cfg.stiffness ?? 100, c = cfg.damping ?? 10, m = cfg.mass ?? 1;
  const w0 = Math.sqrt(k / m), zeta = c / (2 * Math.sqrt(k * m));
  let x;
  if (zeta < 1) {
    const wd = w0 * Math.sqrt(1 - zeta * zeta);
    x = 1 - Math.exp(-zeta * w0 * t) * (Math.cos(wd * t) + ((zeta * w0) / wd) * Math.sin(wd * t));
  } else {
    x = 1 - Math.exp(-w0 * t) * (1 + w0 * t);
  }
  return Math.abs(1 - x) < 0.001 ? 1 : x;     // ogon do spoczynku: napis nie pełznie subpikselowo przez cięcie
}
/** spr(t, t0, cfg) z przepisów: sprężyna startująca w chwili t0. */
export const spr = (t, t0, cfg = SPR.firm) => sprezyna(t - t0, cfg);

/** Liczba z [0, 1) z ziarna (liczba albo tekst): ten sam wynik w każdej klatce i przeglądarce (Math.random zakazany). */
export function rand(ziarno) {
  const s = String(ziarno);
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  h ^= h >>> 16; h = Math.imul(h, 2246822507);
  h ^= h >>> 13; h = Math.imul(h, 3266489909);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

// Kolory w OKLab: przejście akcent → tło bez szarego błota w połowie, zaokrąglone raz na końcu.
function rgb01(kolor) {
  const m = String(kolor).match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i);
  if (m) return [m[1], m[2], m[3]].map((v) => Number(v) / 255);
  const h = String(kolor).replace('#', '');
  const p = h.length === 3 ? h.split('').map((c) => c + c).join('') : h.slice(0, 6);
  return [0, 2, 4].map((i) => parseInt(p.slice(i, i + 2), 16) / 255);
}
const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const gam = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);
function doLab(kolor) {
  const [r, g, b] = rgb01(kolor).map(lin);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
function zLab([L, A, B]) {
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3;
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3;
  const s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3;
  return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s].map((c) => Math.round(clamp(gam(c)) * 255));
}
/** Mieszanie dwóch kolorów (hex albo 'rgb(…)') w OKLab, u 0–1 → 'rgb(r, g, b)'. Można zagnieżdżać. */
export function mixColor(a, b, u) {
  const A = doLab(a), B = doLab(b), k = clamp(u);
  const [r, g, bl] = zLab([0, 1, 2].map((i) => A[i] + (B[i] - A[i]) * k));
  return `rgb(${r}, ${g}, ${bl})`;
}
