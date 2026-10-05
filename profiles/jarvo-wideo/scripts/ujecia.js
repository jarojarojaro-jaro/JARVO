// Ujęcia z kart video-shotcraft przeniesione do kontraktu jarvo: czyste funkcje czasu t (sekundy), bez Remotion.
// Strona: import { rozdanie, stos, wiersz, pisanie, tytulPapier, licznikBebnowy, … } from '/_lib/jarvo/ujecia.js';
// Liczby (klatki przy 30 kl./s, krzywe, przestrzelenia) z kart i dem Vincent Wei, video-shotcraft (Apache-2.0):
// deck-deal-flyin, list-stack-press, row-embed, type-and-filter, paper-title-card, odometer-digit-roll,
// beat-cut-moves, speed-ramp-freeze, depth-layer-moves, outro-group-photo-launch, spotlight-hero-card.
// Kod jest nasz. Karta: `inspiracje.py ujecia --karta <nazwa>`; opis po polsku: film-z-kodu/references/ujecia.md.

import { bezier } from './ruch.js';

export const KL = 1 / 30;                            // klatka karty w sekundach
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, u) => a + (b - a) * u;
const r9 = (x) => Math.round(x * 1e9) / 1e9;          // szum zmiennoprzecinkowy na granicy klatki
const postep = (t, od, czas) => clamp(r9((t - od) / czas));
const wyjscieCubic = (u) => 1 - Math.pow(1 - u, 3);
const hash = (i, s = 1) => { const x = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return x - Math.floor(x); };   // deterministyczne

// Ujęcia mocne działają raz: drugi raz w tym samym filmie to już tik. sprawdzUjecia(['flesz', 'dollyZoom', …], {dlugosc})
// zwraca uwagi; stop-klatki liczy się jako 'stop' (najwyżej 2 na 30 s filmu).
export const RAZ_NA_FILM = ['przyspieszenie', 'flesz', 'dollyZoom', 'reflektor', 'grupa'];
export function sprawdzUjecia(uzyte, { dlugosc = 30 } = {}) {
  const ile = (n) => uzyte.filter(u => u === n).length, uwagi = [];
  for (const n of RAZ_NA_FILM) if (ile(n) > 1) uwagi.push(`${n} ${ile(n)}×, najwyżej raz na film`);
  if (ile('przyspieszenie') && ile('flesz')) uwagi.push('przyspieszenie i flesz to dwa warianty cięć na bit: wybierz jeden');
  const stopy = Math.floor(2 * Math.max(1, dlugosc / 30));
  if (ile('stop') > stopy) uwagi.push(`stop-klatek ${ile('stop')}, najwyżej ${stopy} na ${dlugosc} s`);
  return uwagi;
}

// Cień zależny od wysokości: w powietrzu szeroki i miękki, na ziemi krótki (ta sama mowa co w kartach shotcraft)
export function cien(uniesienie, kolor = '0,0,0') {
  const a = clamp(uniesienie);
  return `0 ${(2 + 30 * a).toFixed(1)}px ${(8 + 56 * a).toFixed(1)}px rgba(${kolor},${(0.14 + 0.1 * a).toFixed(3)})`;
}

// ---------------------------------------------------------------- deck-deal-flyin: rozdanie kart do siatki
// Karta k startuje z talii coraz szybciej (odstęp 4 klatki maleje do 0,2), leci 8 klatek, osiada 4 klatki
// z przestrzeleniem i dociska się 2 klatki. Zwraca {start, p (0 → 1 drogi, chwilę > 1 przy osiadaniu), z (łuk w px),
// skala, uniesienie (do cienia), wyladowala}. Pozycja: lerp(talia, slot, p). Po pełnej siatce 0,5 s spokoju.
const DEAL = bezier(0.3, 0, 0.2, 1), SETTLE = bezier(0.3, 0, 0.25, 1.15);
export function startRozdania(k) {
  let f = 0;
  for (let j = 0; j < k; j++) f += Math.max(0.2, 4 - 0.1584 * j);
  return f * KL;
}
export function rozdanie(t, k, { od = 0, luk = 90 } = {}) {
  const start = od + startRozdania(k);
  const u = postep(t, start, 8 * KL), s = postep(t, start + 8 * KL, 4 * KL), d = postep(t, start + 12 * KL, 2 * KL);
  const p = s > 0 ? lerp(0.97, 1, SETTLE(s)) : 0.97 * DEAL(u);
  const lot = t >= start && u < 1 ? Math.sin(Math.PI * u) : 0;
  const skala = (1 + 0.06 * lot) * (s >= 1 && d < 1 ? lerp(0.996, 1, d) : 1);
  return { start, p, z: luk * lot, skala, uniesienie: lot, wyladowala: d >= 1 };
}
// Zapowiedź rozdania (raz na serię, 12 klatek przed pierwszą kartą): talia wciśnięta, górna karta cofnięta.
export function zapowiedzRozdania(t, od) {
  const u = postep(t, od - 12 * KL, 12 * KL);
  const w = t < od ? wyjscieCubic(u) : 0;
  return { wcisniecie: 45 * w, cofniecie: 30 * w };
}

// ---------------------------------------------------------------- list-stack-press: stos z dociskiem
// Karta i wjeżdża od dołu co 12 klatek, lot 22 klatki z przestrzeleniem, na zmianę ±2° przechylenia, skala 1,06 → 1.
// Każde lądowanie dociska cały stos o 6 px (8 klatek). Podświetlenie rośnie 3 klatki po lądowaniu.
const STOS = bezier(0.45, 0.05, 0.25, 1.12);
export function stos(t, i, { od = 0, odstep = 12 * KL, lot = 22 * KL, wysokosc = 600 } = {}) {
  const start = od + i * odstep, u = postep(t, start, lot), e = STOS(u);
  const przechyl = (i % 2 ? -2 : 2) * (1 - e);
  return { start, ladowanie: start + lot, y: wysokosc * (1 - e), obrot: przechyl, skala: lerp(1.06, 1, e),
           krycie: t >= start ? 1 : 0, uniesienie: 1 - e };
}
export function docisk(t, n, opcje = {}) {
  let y = 0;
  for (let i = 0; i < n; i++) {
    const l = stos(0, i, opcje).ladowanie, u = (t - l) / (8 * KL);
    if (u > 0 && u < 1) y = Math.max(y, 6 * (u < 0.5 ? u * 2 : (1 - u) * 2));
  }
  return y;
}
export function podswietlenie(t, i, opcje = {}) {
  const l = stos(0, i, opcje).ladowanie + 3 * KL;
  return { szer: 0.4 * wyjscieCubic(postep(t, l, 7 * KL)), krycie: t < l ? 0 : 1 - 0.5 * postep(t, l + 7 * KL, 5 * KL) };
}

// Licznik w rytm lądowań: ciągła pozycja (krok 8 klatek, krzywa 0.25, 0.8, 0.25, 1); cyfra = pozycja % 10,
// pasek „0–9 0–9” przesuwasz o −(pozycja % 10) wierszy (tabular-nums, bez skakania szerokości).
const KROK = bezier(0.25, 0.8, 0.25, 1);
export function licznikZdarzen(t, chwile, { krok = 8 * KL, od = 0 } = {}) {
  return od + chwile.reduce((s, c) => s + KROK(postep(t, c, krok)), 0);
}

// ---------------------------------------------------------------- row-embed: wiersz wpada w swoje miejsce
// Wiersz i co 9 klatek spada z góry (12 klatek) i kładzie się z przechylenia 16°; skala 1,06 → 0,995 → 1 (4 klatki).
// Do lądowania + 2 klatki miejsce przykrywa łatka koloru strony (w zrzucie wiersz już jest). Szew akcentu
// 2 px na dole rozchodzi się od środka w 5 klatek i gaśnie w 8.
const WIERSZ = bezier(0.3, 0, 0.2, 1);
export function wiersz(t, i, { od = 0, odstep = 9 * KL, lot = 12 * KL } = {}) {
  const start = od + i * odstep, u = postep(t, start, lot), e = WIERSZ(u), powietrze = 1 - e;
  const l = start + lot, dociskU = postep(t, l, 4 * KL);
  const skala = u < 1 ? lerp(1.06, 0.995, e) : lerp(0.995, 1, Math.sin(dociskU * Math.PI / 2));
  const szew = postep(t, l, 5 * KL), gasnie = postep(t, l + 5 * KL, 8 * KL);
  return { start, y: -120 * powietrze, obrotX: 16 * powietrze, skala, krycie: t >= start ? 1 : 0,
           latka: t < l + 2 * KL, szew: { szer: wyjscieCubic(szew), krycie: t < l ? 0 : 1 - gasnie } };
}

// ---------------------------------------------------------------- type-and-filter: pisanie, filtr, klik
// Pisanie 3 klatki na znak (tempo człowieka); kursor stały przy pisaniu, potem miga co 8 klatek.
export function pisanie(t, tekst, { od = 0, naZnak = 3 * KL } = {}) {
  const n = Math.max(0, Math.min(tekst.length, Math.floor(r9((t - od) / naZnak))));
  const koniec = od + tekst.length * naZnak;
  const kursor = t < koniec ? t >= od : Math.floor(r9((t - koniec) / (8 * KL))) % 2 === 0;
  return { tekst: tekst.slice(0, n), kursor, koniec, oddech: koniec + 11 * KL };
}
// Filtr: karty spoza wyniku gasną w kolejności czytania co 0,4 klatki, każda 5 klatek, opadając o 8 px.
export function filtr(t, i, { od = 0 } = {}) {
  const u = postep(t, od + i * 0.4 * KL, 5 * KL);
  return { krycie: 1 - u, y: 8 * u };
}
// Wynik jedzie na pierwsze miejsce w siatce (10 klatek), unosząc się po drodze; p = droga 0 → 1.
const SLOT = bezier(0.35, 0, 0.2, 1);
export function doSlotu(t, { od = 0, czas = 10 * KL } = {}) {
  const u = postep(t, od, czas), lot = Math.sin(Math.PI * u);
  return { p: SLOT(u), z: 18 * lot, skala: 1 + 0.02 * lot, uniesienie: 0.4 * lot };
}
// Klik: dwa koncentryczne kręgi akcentu (drugi 3 klatki później), każdy 10 klatek, promień 14 → 54 / 78.
export function klik(t, od) {
  return [[0, 54], [3, 78]].map(([op, r]) => {
    const u = postep(t, od + op * KL, 10 * KL);
    return { r: lerp(14, r, wyjscieCubic(u)), krycie: t < od + op * KL || u >= 1 ? 0 : 1 - u };
  });
}

// ---------------------------------------------------------------- paper-title-card: tytuł wciskany w papier
// Słowo i: start 4 + 4·i klatek, 9 klatek krzywą 0.2, 0.75, 0.3, 1: skala 1,28 → 1, rozmycie 7 → 0 px, krycie 0 → 1.
// Jedno słowo-akcent na zdanie (kursywa, kolor akcentu). Kreska akcentu po ostatnim słowie (18 klatek), karta
// trwa 50–55 klatek i gaśnie przez ostatnie 8.
const DRUK = bezier(0.2, 0.75, 0.3, 1);
export function tytulPapier(t, slowa, { od = 0, dlugosc = 54 * KL, akcent = -1 } = {}) {
  const lista = slowa.map((slowo, i) => {
    const e = DRUK(postep(t, od + (4 + 4 * i) * KL, 9 * KL));
    return { slowo, akcent: i === akcent, skala: lerp(1.28, 1, e), rozmycie: 7 * (1 - e), krycie: e };
  });
  const kreskaOd = od + Math.max(16, 4 + 4 * (slowa.length - 1) + 9) * KL;
  return { slowa: lista, kreska: wyjscieCubic(postep(t, kreskaOd, 18 * KL)),
           krycie: 1 - postep(t, od + dlugosc - 8 * KL, 8 * KL), koniec: od + dlugosc };
}

// ---------------------------------------------------------------- odometer-digit-roll: licznik bębnowy
// Każda cyfra jedzie od 0 przez pełny obrót do swojej wartości: start 20 + 7·i klatek (od lewej), 16 klatek
// hamowania z przestrzeleniem o pół wiersza, 6 klatek powrotu = „klik” cyfry. Kropka, przecinek, % i spacja stoją.
// Po ostatniej cyfrze puls 8 klatek: ciemniej i skala 1,035; potem prawdziwy spokój ≥ 45 klatek. Do 6 cyfr.
export function licznikBebnowy(t, wartosc, { od = 0 } = {}) {
  const znaki = [...String(wartosc)];
  let i = 0, ostatni = od;
  const cyfry = znaki.map((z) => {
    if (!/\d/.test(z)) return { znak: z, cyfra: false };
    const start = od + (20 + 7 * i++) * KL, cel = Number(z) + 10;
    const hamuje = postep(t, start, 16 * KL), wraca = postep(t, start + 16 * KL, 6 * KL);
    const pos = wraca > 0 ? lerp(cel + 0.5, cel, wyjscieCubic(wraca)) : (cel + 0.5) * wyjscieCubic(hamuje);
    const v = hamuje > 0 && hamuje < 1 ? 3 * Math.pow(1 - hamuje, 2) * (cel + 0.5) / 16 : 0;   // wiersze na klatkę
    ostatni = Math.max(ostatni, start + 22 * KL);
    return { znak: z, cyfra: true, pos, wiersz: ((pos % 10) + 10) % 10, predkosc: v, duchy: v > 0.15,
             zablokowana: wraca >= 1 };
  });
  const uwaga = i > 6 ? `licznikBebnowy: ${i} cyfr, najwyżej 6 (12,4 mln zamiast 12 400 000)` : '';
  const p = postep(t, ostatni, 8 * KL), puls = t >= ostatni && p < 1 ? Math.sin(Math.PI * p) : 0;
  return { cyfry, puls: { skala: 1 + 0.035 * puls, ciemniej: puls }, koniec: ostatni + 8 * KL, spokoj: ostatni + 53 * KL, uwaga };
}

// ---------------------------------------------------------------- beat-cut-moves: cięcia jako perkusja
// A, przyspieszenie: cięcia w 0/49/65/77/85/91/95 klatce (odstępy 16 → 4), na klatce cięcia błysk 1 klatka
// (jasność 1,05 + 6% bieli); po ostatnim 35 klatek spokoju z najazdem 1 → 1,06 w 20 klatek. Raz na film.
// B, flesz: trzy białe błyski (30/52/70) z kadrem coraz bliżej (1 / 2,3 / 4), biel 0,95 → 0 w 4 klatki,
// kadr osiada ze skali 1,03 i −16 px w 6 klatek; po trzecim 60 klatek spokoju.
export const CIECIA_PRZYSPIESZENIE = [0, 49, 65, 77, 85, 91, 95];
export const CIECIA_FLESZ = [30, 52, 70];
export function przyspieszenie(t, { od = 0, ciecia = CIECIA_PRZYSPIESZENIE } = {}) {
  const f = r9((t - od) / KL);
  const widok = Math.max(0, ciecia.filter(c => f >= c).length - 1);
  const odCiecia = f - ciecia[widok];
  const ostatnie = ciecia[ciecia.length - 1];
  const najazd = f >= ostatnie ? lerp(1, 1.06, wyjscieCubic(clamp((f - ostatnie) / 20))) : 1;
  return { widok, blysk: widok > 0 && odCiecia < 1 ? 1 : 0, skala: najazd, koniec: od + (ostatnie + 35) * KL };
}
export function flesz(t, { od = 0, ciecia = CIECIA_FLESZ, skale = [1, 2.3, 4] } = {}) {
  const f = r9((t - od) / KL);
  const n = ciecia.filter(c => f >= c).length;
  if (!n) return { widok: -1, biel: 0, skala: 1, y: 0, koniec: od + (ciecia[ciecia.length - 1] + 60) * KL };
  const od_ = f - ciecia[n - 1];
  const u = clamp(od_ / 4), osiada = wyjscieCubic(clamp(od_ / 6));
  return { widok: n - 1, przyblizenie: skale[n - 1], biel: 0.95 * (1 - wyjscieCubic(u)), skala: lerp(1.03, 1, osiada),
           y: lerp(-16, 0, osiada), drgniecie: od_ < 1 ? (hash(n) - 0.5) * 4 : 0, koniec: od + (ciecia[ciecia.length - 1] + 60) * KL };
}

// ---------------------------------------------------------------- speed-ramp-freeze: zmiana tempa i stop-klatka
// Czas filmu → czas akcji, odcinkami liniowo (nachylenie = tempo). Szybko ≥ 2, wolno ≈ 0,2 (różnica ≥ 10×),
// wolne okno ≥ 40 klatek, stop-klatka (nachylenie 0) ≥ 45 klatek, najwyżej 2 stop-klatki na 30 s.
export const ZWOLNIENIE = [[0, 0], [40 * KL, 88 * KL], [85 * KL, 97 * KL], [135 * KL, 207 * KL]];
export function przemapuj(t, klucze) {
  if (t <= klucze[0][0]) return klucze[0][1];
  for (let i = 1; i < klucze.length; i++) {
    const [t0, s0] = klucze[i - 1], [t1, s1] = klucze[i];
    if (t <= t1) return lerp(s0, s1, (t - t0) / (t1 - t0));
  }
  const [ta, sa] = klucze[klucze.length - 2], [tb, sb] = klucze[klucze.length - 1];
  return sb + (t - tb) * (sb - sa) / (tb - ta);
}
export function sprawdzTempo(klucze) {
  const uwagi = [], tempa = [];
  for (let i = 1; i < klucze.length; i++) {
    const dt = klucze[i][0] - klucze[i - 1][0], v = (klucze[i][1] - klucze[i - 1][1]) / dt;
    tempa.push(v);
    if (v === 0 && dt < 45 * KL - 1e-9) uwagi.push(`stop-klatka ${dt.toFixed(2)} s, najmniej 1,5 s (45 klatek)`);
    if (v > 0 && v < 0.5 && dt < 40 * KL - 1e-9) uwagi.push(`wolne okno ${dt.toFixed(2)} s, najmniej 1,33 s (40 klatek)`);
  }
  const ruch = tempa.filter(v => v > 0);
  if (ruch.length > 1 && Math.max(...ruch) / Math.min(...ruch) < 10) uwagi.push('różnica tempa < 10×: widz nie poczuje zwolnienia');
  return uwagi;
}
// Kółko markerem wokół celu w stop-klatce: obrys 8 klatek (stroke-dashoffset 1 → 0), znika w 8 klatek.
export function kolko(t, od, dlugosc) {
  return { obrys: 1 - wyjscieCubic(postep(t, od, 8 * KL)), krycie: t < od ? 0 : 1 - postep(t, od + dlugosc - 8 * KL, 8 * KL) };
}

// ---------------------------------------------------------------- depth-layer-moves: warstwy głębi
// Paralaksa: ta sama droga razy współczynnik warstwy. Tło 0,35 (rozmycie 2 px, nasycenie 0,92, krycie 0,85),
// środek 0,7 (tu czyta widz: ostro), przód 1,4 (rozmycie 3 px). Najwyżej 4 warstwy.
export const WARSTWY = [
  { nazwa: 'tlo', wsp: 0.35, rozmycie: 2, nasycenie: 0.92, krycie: 0.85 },
  { nazwa: 'srodek', wsp: 0.7, rozmycie: 0, nasycenie: 1, krycie: 1 },
  { nazwa: 'przod', wsp: 1.4, rozmycie: 3, nasycenie: 1, krycie: 1 },
];
export function paralaksa(droga, warstwy = WARSTWY) {
  if (warstwy.length > 4) throw new Error('paralaksa: najwyżej 4 warstwy');
  return warstwy.map(w => ({ ...w, x: droga * w.wsp, filtr: `blur(${w.rozmycie}px) saturate(${w.nasycenie})` }));
}
// Fałszywy dolly zoom (raz na film): bohater stoi w miejscu, tło rośnie 1 → 2,25 i rozmywa się do 3,5 px,
// cień bohatera wydłuża się 12 → 28 px.
export function dollyZoom(t, { od = 0, czas = 3.5, skala = 2.25 } = {}) {
  const u = bezier(0.42, 0, 0.58, 1)(postep(t, od, czas));
  return { skalaTla: lerp(1, skala, u), rozmycieTla: 3.5 * u, cien: lerp(12, 28, u) };
}

// ---------------------------------------------------------------- outro-group-photo-launch: zdjęcie grupowe
// Element i wlatuje co 3 klatki (od 4.), 12 klatek krzywą z prawdziwym przestrzeleniem (0.34, 1.4, 0.44, 1),
// z 360–500 px w kierunku z ziarna, obrót ×2 → swój (±5°), skala 1,12 → 1; po lądowaniu poświata 6 klatek.
// Litery znaku: 42 + 1,8·i klatek, po 8 klatek; wtedy reszta przygasa (−12% krycia, −8% nasycenia).
// Kamera: rotateX 4° → 0 i skala 1,06 → 1 przez 40 klatek, potem wolny najazd +0,035. Po znaku 30 klatek spokoju.
const GRUPA = bezier(0.34, 1.4, 0.44, 1);
export function grupaElement(t, i, { od = 0 } = {}) {
  const start = od + (4 + 3 * i) * KL, u = postep(t, start, 12 * KL), e = GRUPA(u);
  const kat = hash(i, 2) * Math.PI * 2, dyst = 360 + 140 * hash(i, 3), obrot = (hash(i, 4) - 0.5) * 10;
  const blask = postep(t, start + 12 * KL, 6 * KL);
  const przygas = postep(t, od + 42 * KL, 8 * KL);
  return { x: Math.cos(kat) * dyst * (1 - e), y: Math.sin(kat) * dyst * (1 - e), obrot: obrot * lerp(2, 1, e),
           skala: lerp(1.12, 1, e), krycie: t >= start ? 1 - 0.12 * przygas : 0, nasycenie: 1 - 0.08 * przygas,
           poswiata: t >= start + 12 * KL ? 0.35 * (1 - blask) : 0 };
}
export function grupaLitera(t, i, { od = 0 } = {}) {
  const e = DRUK(postep(t, od + (42 + 1.8 * i) * KL, 8 * KL));
  return { skala: lerp(1.28, 1, e), rozmycie: 7 * (1 - e), krycie: e };
}
export function grupaKamera(t, { od = 0 } = {}) {
  const e = bezier(0.2, 0.7, 0.3, 1)(postep(t, od, 40 * KL));
  return { obrotX: lerp(4, 0, e), skala: lerp(1.06, 1, e) + 0.035 * postep(t, od + 40 * KL, 105 * KL),
           rozmycieTla: 14 * postep(t, od + 42 * KL, 24 * KL) };
}

// ---------------------------------------------------------------- spotlight-hero-card: reflektor na bohaterze
// Światło błądzi przez 4 przystanki (44 klatki) i staje na celu: promień 620 → 420 → 360, przy zatrzymaniu
// puls +6%, winieta 0,16 → 0,42. Karta wstaje 10 klatek z przestrzeleniem, unosi się 54 klatki (±4 px, okres
// 40 klatek), siada 18 klatek z dociskiem 0,997. Obwódka światła okrąża kartę dwa razy: 14 klatek mocno,
// 20 klatek słabiej (0,62). Od zatrzymania światła do lądowania ~3,3 s: ujęcie jakości ma być wolne.
const WSTAJE = bezier(0.2, 1.25, 0.3, 1);
export function reflektor(t, { od = 0, cel, start = { x: 0, y: 0 }, przystanki = 4 } = {}) {
  const f = r9((t - od) / KL);
  const stacje = [start, ...Array.from({ length: przystanki - 1 }, (_, k) => ({
    x: lerp(start.x, cel.x, (k + 1) / przystanki) + (hash(k, 5) - 0.5) * 500,
    y: lerp(start.y, cel.y, (k + 1) / przystanki) + (hash(k, 6) - 0.5) * 300 })), cel];
  const seg = Math.min(stacje.length - 2, Math.max(0, Math.floor(f / (44 / (stacje.length - 1)))));
  const u = clamp((f - seg * 44 / (stacje.length - 1)) / (44 / (stacje.length - 1)));
  const e = bezier(0.42, 0, 0.58, 1)(u);
  const a = stacje[seg], b = stacje[seg + 1];
  const zebrany = clamp(f / 44);
  const r = f < 22 ? lerp(620, 420, f / 22) : lerp(420, 360, clamp((f - 22) / 22));
  const puls = f >= 44 && f < 52 ? Math.sin(Math.PI * (f - 44) / 8) * 0.06 : 0;
  const swiatlo = f >= 44 ? { ...cel } : { x: lerp(a.x, b.x, e), y: lerp(a.y, b.y, e) };
  return { swiatlo: { ...swiatlo, r: r * (1 + puls) }, winieta: lerp(0.16, 0.42, zebrany), stoi: f >= 44 };
}
export function kartaBohatera(t, { od = 0 } = {}) {
  const f = r9((t - od) / KL);                     // od = chwila zatrzymania światła
  const wstaje = WSTAJE(clamp(f / 10));
  const unosi = f >= 10 && f < 64 ? Math.sin(2 * Math.PI * (f - 10) / 40) * 4 * Math.sin(Math.PI * (f - 10) / 54) : 0;
  const siada = clamp((f - 64) / 18);
  const uniesienie = f < 64 ? wstaje : 1 - bezier(0.42, 0, 0.2, 1)(siada);
  const docisk = f >= 82 && f < 86 ? lerp(0.997, 1, (f - 82) / 4) : 1;
  const okrazenie = f < 14 ? { nr: 1, postep: clamp(f / 14), krycie: f >= 0 ? 1 : 0 }
    : f < 20 ? { nr: 1, postep: 1, krycie: 0 }
    : { nr: 2, postep: clamp((f - 20) / 20), krycie: f < 40 ? 0.62 : 0 };
  return { uniesienie, z: 110 * uniesienie, bob: unosi, skala: docisk, obwodka: okrazenie, koniec: od + 86 * KL };
}
