// Typografia jak z montażu: słowo po słowie, różne wielkości, kroje, kolory, głębia, skos i perspektywa 3D.
// Jeden renderer na kanwie (czysty JS, bez zależności), jak 44-napisy.js: podgląd edytora HQ, eksport z edytora
// i render Wideografa (projekt.py w przeglądarce bez okna). Plan bloków układa typografia.py (reżyser), a człowiek
// poprawia go w edytorze. Czas słowa liczony od początku bloku: przesunięcie bloku zabiera słowa ze sobą.
//
// projekt.typo = {motyw, akcent, paleta, odstep, kamera, bloki: [{id, start, end, uklad, x, y, w, rot, tilt, warstwa, wejscie,
//                 wyjscie, rozmiar, z, kamera, efekt, slowa: [{t, k, tekst, waga 0–3, linia, glebia −1|0|1, kolor, kroj, styl,
//                 plyta, z}]}]}  (kamera i głębia: niżej „wirtualna kamera”; efekt: „efekty”)
// odstep: "tusz" (nowe plany: reżyser i edytor) = słowa bloku nigdy się nie stykają: odstęp między słowami w linii
// i między liniami liczony z tuszu liter razem z obrysem stylu (ogonki, kreski nad Ż, Ś, Ć, obrys, cień 3D, płytka),
// więc małe słowo obok albo nad uderzeniem nie wchodzi w nie literami. Plany bez pola (starsze filmy) rysują się
// jak dawniej, piksel w piksel.

const TYPO_KROJE = {   // klucz → [rodzina CSS, grubość, kursywa, nazwa, grupa]; pliki w fonts/kroje (OFL, polskie znaki)
  bricolage: ["'Bricolage Grotesque', system-ui, sans-serif", 800, false, "Bricolage", "mocne"],
  bricolageL: ["'Bricolage Grotesque', system-ui, sans-serif", 500, false, "Bricolage lekki", "mocne"],
  montserrat: ["'Montserrat', 'Arial Black', sans-serif", 900, false, "Montserrat", "mocne"],
  montserratI: ["'Montserrat', 'Arial Black', sans-serif", 900, true, "Montserrat kursywa", "mocne"],
  montserratL: ["'Montserrat', Arial, sans-serif", 600, false, "Montserrat lekki", "mocne"],
  unbounded: ["'Unbounded', 'Arial Black', sans-serif", 800, false, "Unbounded", "mocne"],
  unboundedL: ["'Unbounded', Arial, sans-serif", 500, false, "Unbounded lekki", "mocne"],
  poppins: ["'Poppins', 'Arial Black', sans-serif", 800, false, "Poppins", "mocne"],
  poppinsL: ["'Poppins', Arial, sans-serif", 500, false, "Poppins lekki", "mocne"],
  inter: ["'Inter', 'Arial Black', sans-serif", 800, false, "Inter", "mocne"],
  interL: ["'Inter', Arial, sans-serif", 500, false, "Inter lekki", "mocne"],
  archivo: ["'Archivo Black', 'Arial Black', sans-serif", 400, false, "Archivo", "mocne"],
  rubik: ["'Rubik', 'Arial Black', sans-serif", 800, false, "Rubik", "mocne"],
  spartan: ["'League Spartan', 'Arial Black', sans-serif", 800, false, "Spartan", "mocne"],
  kanit: ["'Kanit', 'Arial Black', sans-serif", 800, false, "Kanit", "mocne"],
  kanitI: ["'Kanit', 'Arial Black', sans-serif", 800, true, "Kanit kursywa", "mocne"],
  outfit: ["'Outfit', 'Arial Black', sans-serif", 800, false, "Outfit", "mocne"],
  syne: ["'Syne', 'Arial Black', sans-serif", 800, false, "Syne", "mocne"],
  raleway: ["'Raleway', 'Arial Black', sans-serif", 800, false, "Raleway", "mocne"],
  anton: ["'Anton', Impact, sans-serif", 400, false, "Anton", "waskie"],
  bebas: ["'Bebas Neue', Impact, sans-serif", 400, false, "Bebas", "waskie"],
  barlow: ["'Barlow Condensed', 'Arial Narrow', sans-serif", 800, false, "Barlow", "waskie"],
  barlowI: ["'Barlow Condensed', 'Arial Narrow', sans-serif", 800, true, "Barlow kursywa", "waskie"],
  barlowL: ["'Barlow Condensed', 'Arial Narrow', sans-serif", 600, false, "Barlow lekki", "waskie"],
  oswald: ["'Oswald', 'Arial Narrow', sans-serif", 700, false, "Oswald", "waskie"],
  teko: ["'Teko', 'Arial Narrow', sans-serif", 600, false, "Teko", "waskie"],
  fjalla: ["'Fjalla One', 'Arial Narrow', sans-serif", 400, false, "Fjalla", "waskie"],
  staatliches: ["'Staatliches', 'Arial Narrow', sans-serif", 400, false, "Staatliches", "waskie"],
  shoulders: ["'Big Shoulders Display', 'Arial Narrow', sans-serif", 800, false, "Big Shoulders", "waskie"],
  saira: ["'Saira Condensed', 'Arial Narrow', sans-serif", 800, false, "Saira", "waskie"],
  titan: ["'Titan One', 'Arial Rounded MT Bold', sans-serif", 400, false, "Titan", "okragle"],
  baloo: ["'Baloo 2', 'Arial Rounded MT Bold', sans-serif", 800, false, "Baloo", "okragle"],
  balooL: ["'Baloo 2', 'Arial Rounded MT Bold', sans-serif", 600, false, "Baloo lekki", "okragle"],
  nunito: ["'Nunito', 'Arial Rounded MT Bold', sans-serif", 900, false, "Nunito", "okragle"],
  paytone: ["'Paytone One', 'Arial Rounded MT Bold', sans-serif", 400, false, "Paytone", "okragle"],
  dynapuff: ["'DynaPuff', 'Arial Rounded MT Bold', sans-serif", 700, false, "DynaPuff", "okragle"],
  coiny: ["'Coiny', 'Arial Rounded MT Bold', sans-serif", 400, false, "Coiny", "okragle"],
  grandstander: ["'Grandstander', 'Arial Rounded MT Bold', sans-serif", 800, false, "Grandstander", "okragle"],
  playfair: ["'Playfair Display', Georgia, serif", 800, false, "Playfair", "szeryfowe"],
  playfairI: ["'Playfair Display', Georgia, serif", 500, true, "Playfair kursywa", "szeryfowe"],
  instrument: ["'Instrument Serif', Georgia, serif", 400, false, "Instrument", "szeryfowe"],
  instrumentI: ["'Instrument Serif', Georgia, serif", 400, true, "Instrument kursywa", "szeryfowe"],
  abril: ["'Abril Fatface', Georgia, serif", 400, false, "Abril", "szeryfowe"],
  dmserif: ["'DM Serif Display', Georgia, serif", 400, false, "DM Serif", "szeryfowe"],
  dmserifI: ["'DM Serif Display', Georgia, serif", 400, true, "DM Serif kursywa", "szeryfowe"],
  lora: ["'Lora', Georgia, serif", 700, false, "Lora", "szeryfowe"],
  bodoni: ["'Bodoni Moda', Georgia, serif", 800, false, "Bodoni", "szeryfowe"],
  cormorant: ["'Cormorant Garamond', Georgia, serif", 600, false, "Cormorant", "szeryfowe"],
  cormorantI: ["'Cormorant Garamond', Georgia, serif", 600, true, "Cormorant kursywa", "szeryfowe"],
  fraunces: ["'Fraunces', Georgia, serif", 800, false, "Fraunces", "szeryfowe"],
  alfaslab: ["'Alfa Slab One', Georgia, serif", 400, false, "Alfa Slab", "szeryfowe"],
  yeseva: ["'Yeseva One', Georgia, serif", 400, false, "Yeseva", "szeryfowe"],
  caveat: ["'Caveat', cursive", 700, false, "Odręczny", "odreczne"],
  pacifico: ["'Pacifico', cursive", 400, false, "Pacifico", "odreczne"],
  dancing: ["'Dancing Script', cursive", 700, false, "Dancing", "odreczne"],
  lobster: ["'Lobster', cursive", 400, false, "Lobster", "odreczne"],
  kaushan: ["'Kaushan Script', cursive", 400, false, "Kaushan", "odreczne"],
  greatvibes: ["'Great Vibes', cursive", 400, false, "Great Vibes", "odreczne"],
  amatic: ["'Amatic SC', cursive", 700, false, "Amatic", "odreczne"],
  brush: ["'Caveat Brush', cursive", 400, false, "Pędzel", "odreczne"],
  patrick: ["'Patrick Hand', cursive", 400, false, "Patrick", "odreczne"],
  graffiti: ["'Sedgwick Ave', cursive", 400, false, "Graffiti", "odreczne"],
  shrikhand: ["'Shrikhand', Georgia, serif", 400, false, "Retro", "ozdobne"],
  bangers: ["'Bangers', Impact, sans-serif", 400, false, "Komiks", "ozdobne"],
  neon: ["'Tilt Neon', system-ui, sans-serif", 400, false, "Neon", "ozdobne"],
  grunge: ["'Rubik Dirt', Impact, sans-serif", 400, false, "Grunge", "ozdobne"],
  righteous: ["'Righteous', Impact, sans-serif", 400, false, "Righteous", "ozdobne"],
  bungee: ["'Bungee', Impact, sans-serif", 400, false, "Bungee", "ozdobne"],
  monoton: ["'Monoton', Impact, sans-serif", 400, false, "Monoton", "ozdobne"],
  pixel: ["'Press Start 2P', ui-monospace, monospace", 400, false, "Piksel", "ozdobne"],
  glitch: ["'Rubik Glitch', Impact, sans-serif", 400, false, "Glitch", "ozdobne"],
  bubbles: ["'Rubik Bubbles', Impact, sans-serif", 400, false, "Bąbelki", "ozdobne"],
  russo: ["'Russo One', Impact, sans-serif", 400, false, "Russo", "ozdobne"],
  blackops: ["'Black Ops One', Impact, sans-serif", 400, false, "Szablon", "ozdobne"],
  sigmar: ["'Sigmar', Impact, sans-serif", 400, false, "Sigmar", "ozdobne"],
  rammetto: ["'Rammetto One', Impact, sans-serif", 400, false, "Rammetto", "ozdobne"],
  space: ["'Space Grotesk', system-ui, sans-serif", 700, false, "Space", "techniczne"],
  spaceL: ["'Space Grotesk', system-ui, sans-serif", 500, false, "Space lekki", "techniczne"],
  mono: ["'JetBrains Mono', ui-monospace, monospace", 700, false, "Mono", "techniczne"],
  audiowide: ["'Audiowide', system-ui, sans-serif", 400, false, "Audiowide", "techniczne"],
  chakra: ["'Chakra Petch', system-ui, sans-serif", 700, false, "Chakra", "techniczne"],
  spaceMono: ["'Space Mono', ui-monospace, monospace", 700, false, "Space Mono", "techniczne"],
  majorMono: ["'Major Mono Display', ui-monospace, monospace", 400, false, "Major Mono", "techniczne"],
};
const TYPO_KROJE_GRUPY = { mocne: ["Mocne", "Bold"], waskie: ["Wąskie", "Condensed"], okragle: ["Okrągłe", "Rounded"],
  szeryfowe: ["Szeryfowe", "Serif"], odreczne: ["Odręczne", "Script"], ozdobne: ["Ozdobne", "Display"],
  techniczne: ["Techniczne", "Tech"] };
// Motyw (styl filmu) = zestaw decyzji: kroje (główny, mały do słów funkcyjnych, drugi do słów „z tyłu”), kolory,
// wejście/wyjście, styl słów (`styl`, domyślnie wypełnienie) i najmocniejszego słowa (`hit`), tekstura, skala skosu
// (stopnie). Reżyser typografia.py ma te same wartości w MOTYW_CECHY (skos, wyjście, style), test pilnuje zgodności.
// Kolor marki nadpisuje akcent (projekt.typo.akcent), a bez marki akcentem jest pierwszy kolor palety z kadru
// (projekt.typo.paleta, typografia.py); kolor motywu zostaje tylko, gdy palety nie ma.
const TYPO_MOTYWY = {
  czysty: { nazwa: ["Czysty", "Clean"], kroj: "bricolage", maly: "bricolageL", drugi: "playfairI", akcent: "#FFD400",
    kolor: "#FFFFFF", wielkie: false, wejscie: "pop", wyjscie: "zanik", hit: "wypelnij", skos: 5, lh: 1.0 },
  kino: { nazwa: ["Kino", "Cinema"], kroj: "barlowI", maly: "barlowI", drugi: "playfairI", akcent: "#E5383B",
    kolor: "#FFFFFF", wielkie: true, wejscie: "kontur", wyjscie: "smuga", hit: "3d", skos: 7, lh: 0.92 },
  ulica: { nazwa: ["Ulica", "Street"], kroj: "anton", maly: "anton", drugi: "grunge", akcent: "#C8102E",
    kolor: "#F2F2F2", wielkie: true, wejscie: "ciecie", wyjscie: "ciecie", hit: "wypelnij", tekstura: true, skos: 4, lh: 0.95 },
  energia: { nazwa: ["Energia", "Energy"], kroj: "bebas", maly: "caveat", drugi: "caveat", akcent: "#FFE14D", akcent2: "#38D9FF",
    kolor: "#FFFFFF", wielkie: true, wejscie: "pop", wyjscie: "smuga", hit: "blask", skos: 10, lh: 0.9 },
  elegancki: { nazwa: ["Elegancki", "Elegant"], kroj: "playfair", maly: "playfairI", drugi: "playfairI", akcent: "#E8C872",
    kolor: "#FFFFFF", wielkie: false, wejscie: "maska", wyjscie: "zanik", hit: "wypelnij", skos: 3, lh: 1.05 },
  podcast: { nazwa: ["Podcast", "Podcast"], kroj: "montserrat", maly: "montserratL", drugi: "montserratI", akcent: "#FFD400",
    kolor: "#FFFFFF", wielkie: true, wejscie: "pop", wyjscie: "ciecie", styl: "obrys", hit: "obrys", skos: 3, lh: 0.95 },
  vlog: { nazwa: ["Vlog", "Vlog"], kroj: "titan", maly: "balooL", drugi: "baloo", akcent: "#FF7AC6",
    kolor: "#FFFFFF", wielkie: false, wejscie: "pop", wyjscie: "zanik", styl: "obrys", hit: "3d", skos: 8, lh: 1.0 },
  komiks: { nazwa: ["Komiks", "Comic"], kroj: "bangers", maly: "bangers", drugi: "bangers", akcent: "#FFE14D",
    kolor: "#FFFFFF", wielkie: true, wejscie: "pop", wyjscie: "smuga", styl: "obrys", hit: "3d", skos: 10, lh: 0.95 },
  magazyn: { nazwa: ["Magazyn", "Magazine"], kroj: "instrument", maly: "instrumentI", drugi: "instrumentI", akcent: "#F2C94C",
    kolor: "#FFFFFF", wielkie: false, wejscie: "maska", wyjscie: "zanik", hit: "wypelnij", skos: 2, lh: 0.92 },
  tech: { nazwa: ["Tech", "Tech"], kroj: "space", maly: "mono", drugi: "spaceL", akcent: "#5EEAD4",
    kolor: "#FFFFFF", wielkie: false, wejscie: "pisanie", wyjscie: "ciecie", hit: "tlo", skos: 0, lh: 1.0 },
  nowoczesny: { nazwa: ["Nowoczesny", "Modern"], kroj: "unbounded", maly: "unboundedL", drugi: "spaceL", akcent: "#B79CFF",
    kolor: "#FFFFFF", wielkie: true, wejscie: "kontur", wyjscie: "smuga", hit: "wypelnij", skos: 4, lh: 0.98 },
  retro: { nazwa: ["Retro", "Retro"], kroj: "shrikhand", maly: "pacifico", drugi: "pacifico", akcent: "#FF8A3D",
    kolor: "#FFF4E0", wielkie: false, wejscie: "pop", wyjscie: "zanik", hit: "3d", skos: 6, lh: 1.05 },
  neon: { nazwa: ["Neon", "Neon"], kroj: "neon", maly: "neon", drugi: "neon", akcent: "#FF7AC6",
    kolor: "#FFFFFF", wielkie: true, wejscie: "pop", wyjscie: "zanik", hit: "blask", skos: 5, lh: 1.0 },
  // napisy jak z programu rozrywkowego (za mg-styles-15, MIT, demos/18-hanazi): obrys uderzenia `obrys`, reszty `obrys2`
  show: { nazwa: ["Show", "Show"], kroj: "titan", maly: "balooL", drugi: "baloo", akcent: "#FFE14D", obrys: "#FF3D7F",
    obrys2: "#1E2A78", kolor: "#FFFFFF", wielkie: false, wejscie: "skok", wyjscie: "zanik", styl: "show", hit: "show", skos: 6, lh: 0.95 },
};
const TYPO_UKLADY = ["kolumna", "schodki", "srodek", "skos", "3d", "za", "rozrzut"];
const TYPO_WEJSCIA = { ciecie: 0, pop: 0.14, kontur: 0.24, maska: 0.18, pisanie: 0.3, zjazd: 0.16, skok: 0.4 };
const TYPO_WYJSCIA = { ciecie: 0, zanik: 0.16, smuga: 0.14 };
const TYPO_STYLE = ["wypelnij", "kontur", "3d", "blask", "tlo", "obrys", "show"];
const TYPO_WAGA = [0.58, 1, 1.45, 2.1];            // mnożnik rozmiaru: słowo funkcyjne, zwykłe, ważne, uderzenie
const TYPO_CEL = [0.62, 0.62, 0.8, 1];             // część szerokości bloku (w), którą wypełnia blok, wg najmocniejszego słowa
const TYPO_ODSTEP = 0.12;                          // „tusz”: najmniejszy odstęp = 12% mniejszego z dwóch słów (co najmniej 10 px przy 1080)
// „tusz”: ile rysunek wychodzi poza literę w danym stylu (obrys, cień 3D, poświata), w ułamku rozmiaru: [boki, góra, dół]
const TYPO_HALO = { wypelnij: [0.02, 0.02, 0.04], kontur: [0.03, 0.03, 0.03], obrys: [0.09, 0.09, 0.09],
  show: [0.18, 0.16, 0.26], "3d": [0.08, 0.02, 0.11], blask: [0.1, 0.1, 0.1], tlo: [0.02, 0.02, 0.02] };
// Tusz słowa względem początku i linii bazowej, w px: {l, r, g, d} (lewo, prawo, góra, dół), z obrysem stylu i płytką.
function typoTuszSlowa(ctx, s) {
  ctx.font = typoFont(s.kroj, s.px);
  const mt = ctx.measureText(s.tekst), [hx, hg, hd] = TYPO_HALO[s.styl] || TYPO_HALO.wypelnij;
  let l = mt.actualBoundingBoxLeft ?? 0, r = mt.actualBoundingBoxRight ?? s.w;
  let g = mt.actualBoundingBoxAscent ?? s.px * 0.8, d = mt.actualBoundingBoxDescent ?? s.px * 0.22;
  if (s.styl === "tlo") { l = Math.max(l, s.px * 0.12); r = Math.max(r, s.w + s.px * 0.12); g = Math.max(g, s.px * 0.82); d = Math.max(d, s.px * 0.2); }
  return { l: l + hx * s.px, r: r + hx * s.px, g: g + hg * s.px, d: d + hd * s.px };
}
const TYPO_LEAD = 0.03;                            // słowo pojawia się tuż przed dźwiękiem (oko wyprzedza ucho)
const TYPO_SCHODKI = [0, 1, 0.3, 0.85, 0.15];      // wyrównanie kolejnych linii w układzie „schodki”

function typoMotyw(P) {
  const t = (P && P.typo) || {};
  const m = TYPO_MOTYWY[t.motyw] || TYPO_MOTYWY.czysty;
  const akcent = t.akcent || (Array.isArray(t.paleta) && t.paleta[0]);
  return akcent ? { ...m, akcent } : m;
}
function typoBloki(P) { return ((P && P.typo && P.typo.bloki) || []).filter((b) => b && Array.isArray(b.slowa) && b.slowa.length); }
function typoAktywne(P, now) { return typoBloki(P).filter((b) => now >= b.start + Math.max(0, +(b.slowa[0].t) || 0) - TYPO_LEAD && now < b.end); }
function typoKroj(key) { return TYPO_KROJE[key] || TYPO_KROJE.bricolage; }
function typoFont(key, px) { const k = typoKroj(key); return `${k[2] ? "italic " : ""}${k[1]} ${Math.max(4, px).toFixed(1)}px ${k[0]}`; }
function typoClamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
function typoEaseOut(a) { return 1 - Math.pow(1 - typoClamp(a, 0, 1), 3); }
function typoEaseBack(a) { const c = 1.9, x = typoClamp(a, 0, 1) - 1; return 1 + (c + 1) * x * x * x + c * x * x; }
// Skok od zera (sprężyna tłumiona ζ 0,517, ω 22, za mg-styles-15 demos/18-hanazi): szczyt 1,15 po 0,167 s (5. klatka
// przy 30 fps), ~1,01 po 0,27 s; t w sekundach od początku wejścia.
function typoSkok(t) {
  const z = 0.517, w = 22, wd = w * Math.sqrt(1 - z * z);
  return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + (z * w / wd) * Math.sin(wd * t));
}
function typoHash(s) { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; }

// Wygląd słowa po motywie i nadpisaniach: krój, kolor, styl, wielkie litery.
function typoSlowo(w, m, uklad) {
  const waga = typoClamp(Math.round(+w.waga || 0), 0, 3);
  const glebia = typoClamp(Math.round(+w.glebia || 0), -1, 1);
  const kroj = w.kroj && TYPO_KROJE[w.kroj] ? w.kroj : waga === 0 ? m.maly : glebia < 0 ? m.drugi : m.kroj;
  const kolor = w.kolor || (waga === 3 ? m.akcent : m.kolor);   // akcent tylko na uderzeniu: kolor ma znaczyć, nie zdobić
  const auto = waga === 3 && uklad !== "za" ? m.hit : m.styl || "wypelnij";
  // `plyta`: kolor słabo odcina się od tła (typografia.py) → płytka, a w motywie z obrysem (obrys, show) obrys wystarczy
  const styl = TYPO_STYLE.includes(w.styl) ? w.styl : w.plyta && auto !== "obrys" && auto !== "show" && uklad !== "za" ? "tlo" : auto;
  const wielkie = w.wielkie ?? (m.wielkie || waga === 3);
  const tekst = String(w.tekst || "");
  return { waga, glebia, kroj, kolor, styl, tekst: wielkie ? tekst.toLocaleUpperCase("pl-PL") : tekst };
}

// Układ bloku w pikselach kanwy W×H, względem kotwicy (środka bloku): słowa z pozycją linii bazowej i rozmiarem.
// Blok wypełnia część swojej szerokości (TYPO_CEL wg najmocniejszego słowa, „za” całą), jak skład w montażu:
// krótka mocna fraza jest duża, długa mniejsza; wysokość ma limit (pion 30%, poziom 50% kadru), `rozmiar` mnoży wynik.
function typoUklad(ctx, b, P, W, H) {
  const m = typoMotyw(P);
  const S = Math.min(W, H) / 1080;
  const maxW = typoClamp(+b.w || 0.62, 0.15, 1) * W;
  const lines = [];
  b.slowa.forEach((w, i) => {
    const s = typoSlowo(w, m, b.uklad);
    const glebiaSkala = s.glebia < 0 ? 0.82 : s.glebia > 0 ? 1.12 : 1;
    const px = 66 * S * TYPO_WAGA[s.waga] * glebiaSkala * (+w.skala || 1);
    const li = Number.isFinite(+w.linia) ? Math.max(0, Math.round(+w.linia)) : i;
    (lines[li] = lines[li] || []).push({ ...s, i, px, src: w });
  });
  const rows = lines.filter(Boolean);
  const tusz = P && P.typo && P.typo.odstep === "tusz";
  const odstep = (a, b) => Math.max(TYPO_ODSTEP * Math.min(a, b), 10 * S);
  const miara = (row) => {
    for (const s of row) { ctx.font = typoFont(s.kroj, s.px); s.w = ctx.measureText(s.tekst).width; }
    const gap = Math.min(...row.map((s) => s.px)) * 0.26;
    const lh = Math.max(...row.map((s) => s.px)) * m.lh;
    if (!tusz) return { gap, lw: row.reduce((a, s) => a + s.w, 0) + gap * (row.length - 1), lh };
    // odstęp słów w linii: tusz z obrysem obu słów i 12% mniejszego (małe „a” przy dużym „SCROLL”)
    const ink = row.map((s) => typoTuszSlowa(ctx, s));
    const gaps = row.slice(0, -1).map((s, i) => Math.max(gap, ink[i].r + ink[i + 1].l - s.w + odstep(s.px, row[i + 1].px)));
    return { gap, gaps, lw: row.reduce((a, s) => a + s.w, 0) + gaps.reduce((a, g) => a + g, 0), lh };
  };
  const nat = rows.map(miara);
  const natW = Math.max(1, ...nat.map((r) => r.lw)), natH = Math.max(1, nat.reduce((a, r) => a + r.lh, 0));
  const cel = maxW * (b.uklad === "za" ? 1 : TYPO_CEL[Math.max(...rows.flat().map((s) => s.waga))]);
  const k = typoClamp(Math.min(cel / natW, ((H > W ? 0.3 : 0.5) * H) / natH), 0.4, 3.4) * (+b.rozmiar || 1);
  const limit = Math.min(maxW * Math.max(1, +b.rozmiar || 1), W * 0.96);
  const out = [];
  let y = 0, width = 0, prev = null;
  rows.forEach((row) => {
    for (const s of row) s.px *= k;
    let { gap, gaps, lw } = miara(row);
    const fit = lw > limit ? limit / lw : 1;         // za długa linia: cała linia mniejsza, nie poza kadr
    if (fit < 1 && tusz) { for (const s of row) s.px *= fit; ({ gap, gaps, lw } = miara(row)); }
    else if (fit < 1) { for (const s of row) { s.px *= fit; s.w *= fit; } lw *= fit; gap *= fit; }
    const lh = Math.max(...row.map((s) => s.px)) * m.lh;
    row.lh = lh; row.lw = lw; row.gap = gap; row.gaps = gaps; row.y = y + lh * 0.8;
    if (tusz) {                                      // tusz liter tej linii nad i pod linią bazową, z obrysem stylu
      const ink = row.map((s) => typoTuszSlowa(ctx, s));
      row.asc = Math.max(...ink.map((t) => t.g)); row.desc = Math.max(...ink.map((t) => t.d));
      row.min = Math.min(...row.map((s) => s.px));
      const min = prev ? prev.y + prev.desc + row.asc + odstep(prev.min, row.min) : -Infinity;
      if (row.y < min) { y += min - row.y; row.y = min; }   // rozsuwa tylko linie, które by się stykały
      prev = row;
    }
    y += lh; width = Math.max(width, lw);
  });
  rows.forEach((row, r) => {
    const f = b.uklad === "kolumna" || b.uklad === "3d" ? 0 : b.uklad === "schodki" ? TYPO_SCHODKI[r % TYPO_SCHODKI.length]
      : b.uklad === "rozrzut" ? typoHash(`${b.id}:${r}`) : 0.5;
    let x = (width - row.lw) * f - width / 2;
    row.forEach((s, i) => {
      out.push({ ...s, x, y: row.y - y / 2, h: s.px });
      x += s.w + (row.gaps ? row.gaps[i] : row.gap);
    });
  });
  return { slowa: out.sort((a, c) => a.i - c.i), w: width, h: y, cx: (+b.x || 0.5) * W, cy: (+b.y || 0.3) * H, S };
}

// Ramka bloku na kanwie (do trafiania myszą i strzałek w edytorze); bez obrotu i perspektywy.
// `now` (opcjonalnie): ramka tam, gdzie blok widać przez kamerę w tej chwili (środek cx, cy i skala s), z efektem
// (przejście jedzie, pierścień idzie za głową); pierścień: całe koło z literami (osoba stoi na z = 1).
function typoRamka(ctx, b, P, W, H, now) {
  const e = typoEfekt(b), pier = e && e.rodzaj === "pierscien";
  const u = pier ? null : typoUklad(ctx, b, P, W, H);
  const k = now === undefined ? null : typoKamera(P, now);
  let cx, cy, s = 1, uu = u, z = typoZ(b);
  if (pier) {
    const U = typoPierscienUklad(ctx, b, e, P, W, H), Q = typoPierscienStan(b, e, U, W, H, now === undefined ? b.start : now);
    const maxPx = Math.max(1, ...U.gl.map((q) => q.px)), sn = Math.abs(Math.sin((e.nachylenie * Math.PI) / 180));
    uu = { slowa: [], w: 2 * (U.R + maxPx * 0.6), h: 2 * (U.R * sn + maxPx * 1.1), S: U.S, pierscien: U };
    cx = now === undefined ? typoLiczba(b.x, 0.5) * W : Q.cx; cy = now === undefined ? typoLiczba(b.y, 0.3) * H : Q.cy; z = 1;
  } else if (e && now !== undefined) {
    const q = typoPrzejscieStan(b, e, u.w, W, now);
    cx = q.x * W; cy = u.cy + q.dy * H;
  } else { cx = u.cx; cy = u.cy; }
  uu.cx = cx; uu.cy = cy;
  const pad = 12 * uu.S;
  if (k) { const r = typoRzut(k, cx / W, cy / H, z); cx = r.x * W; cy = r.y * H; s = r.s; }
  const u2 = uu;
  return { x0: cx - (u2.w / 2) * s - pad, y0: cy - (u2.h / 2) * s - pad, x1: cx + (u2.w / 2) * s + pad, y1: cy + (u2.h / 2) * s + pad, u: u2, cx, cy, s };
}

// Stan animacji w chwili now: [słowo widoczne?, postęp wejścia 0–1] i postęp wyjścia bloku. Z tego samego liczy się
// podpis klatki do eksportu (te same podpisy = ta sama klatka), więc eksport renderuje tylko klatki, które się różnią.
function typoWejscie(b, w, m) { return w.wejscie || b.wejscie || m.wejscie; }
function typoCzasWejscia(b, w, m) {
  const k = typoWejscie(b, w, m);
  if (k === "pisanie") return typoClamp((+w.k || 0) - (+w.t || 0), 0.1, 0.35);
  return TYPO_WEJSCIA[k] ?? 0.14;
}
function typoStan(b, P, now) {
  const m = typoMotyw(P);
  const rel = now - b.start;
  const slowa = b.slowa.map((w) => {
    const od = (+w.t || 0) - TYPO_LEAD;
    if (rel < od) return -1;
    const d = typoCzasWejscia(b, w, m);
    return d > 0 ? typoClamp((rel - od) / d, 0, 1) : 1;
  });
  const wy = b.wyjscie || m.wyjscie, dw = TYPO_WYJSCIA[wy] ?? 0;
  const e = dw > 0 ? typoClamp((now - (b.end - dw)) / dw, 0, 1) : 0;
  return { slowa, e, wy };
}
function typoPodpis(P, now, warstwa) {
  const parts = [];
  for (const b of typoAktywne(P, now)) {
    if (warstwa && !typoWarstwyBloku(b).includes(warstwa)) continue;
    const s = typoStan(b, P, now);
    parts.push(`${b.id}:${s.slowa.map((a) => (a < 0 ? "-" : a >= 1 ? "F" : Math.round(a * 1000))).join(",")}:${Math.round(s.e * 1000)}`
      + (typoEfekt(b) ? `@${now.toFixed(4)}` : ""));      // efekt rusza się co klatkę (pierścień, przejście)
  }
  const k = parts.length ? typoKamera(P, now) : null;     // kamera w ruchu: każda klatka inna (w spoczynku stała)
  return parts.join("|") + (k ? `~${[k.z, k.x, k.y].map((v) => v.toFixed(5)).join(",")},${k.f.toFixed(4)}` : "");
}
// Odcinki osi z tą samą klatką warstwy: [{od, do, podpis}] w numerach klatek (fps), pusty podpis = przezroczysta.
function typoOdcinki(P, fps, total, warstwa) {
  const n = Math.max(1, Math.round(total * fps));
  const out = [];
  for (let f = 0; f < n; f++) {
    const sig = typoPodpis(P, (f + 0.5) / fps, warstwa);
    const last = out[out.length - 1];
    if (last && last.podpis === sig) last.do = f + 1; else out.push({ od: f, do: f + 1, podpis: sig });
  }
  return out;
}

// ---------------------------------------------------------------- wirtualna kamera z głębią
// projekt.typo.kamera = {styl: brak|spokojna|dynamiczna, przyslona 0–1, ostrosc: napis|osoba}; blok.z = głębia bloku,
// blok.kamera = własny ruch {ruch: najazd|odjazd|przesuniecie|brak, sila 0–1, krzywa: plynnie|uderzenie,
// kierunek: lewo|prawo|gora|dol, slowo: numer słowa, od którego rusza}; słowo.z = własna głębia słowa.
// Osoba (film) stoi na z = 1, napis przed nią ma z < 1, za nią z > 1 (bez pola: przód 0,8, za osobą 1,3; słowo z
// `glebia` ±1 o 15% bliżej albo dalej niż blok). Kamera: przejazd w głąb kz (0 = spoczynek) i przesunięcie kx, ky
// (część kadru). Punkt w spoczynku (x, y) na głębokości z widać w 0,5 + ((x − 0,5)·z − kx) / (z − kz) w skali
// z / (z − kz) (za camera-3d-captions, HeyGen, Apache-2.0: screen = C + (ref − C)·D0 / (D0 − cz)): bliższy napis
// rośnie i przesuwa się mocniej niż film (paralaksa), a w spoczynku wszystko stoi tam, gdzie w planie. Ostrość:
// płaszczyzna na głębokości najnowszego bloku (napis; zmiana w 0,3 s) albo osoby; rozmycie σ = 13,4·przysłona·|d − df| / d
// px przy 1080 (przysłona 0,5 = 6,7 jak u nich), dla słów bez własnej głębi najwyżej 6·przysłona px (czytelne).
// Ruchy ze stylu i odcinki liczy tak samo edytor.py (kamera_ruchy, kamera_odcinki: ten sam ruch filmu w eksporcie
// przez ffmpeg `perspective`), test pilnuje zgodności. Plan bez kamery rysuje się jak dawniej, piksel w piksel.
const TYPO_KAMERY = ["brak", "spokojna", "dynamiczna"];
const TYPO_RUCHY = ["najazd", "odjazd", "przesuniecie", "brak"];
const TYPO_KIERUNKI = ["lewo", "prawo", "gora", "dol"];
const TYPO_KRZYWE = ["plynnie", "uderzenie"];
const TYPO_OSTROSC = ["napis", "osoba"];
const TYPO_KAMERA = { z: { przod: 0.8, tyl: 1.3 }, zmax: 0.25, sila: { spokojna: 0.35, dynamiczna: 0.6 }, uderzenie: 0.4,
  minBlok: 0.6, trzymaj: 2.5, skala: 1.15, ostrosc: 0.3, rozmycie: 13.4, plaski: 6, wlasne: 12, glebiaSlowa: 0.15 };
function typoLiczba(v, d) { return v === null || v === undefined || v === "" || typeof v === "boolean" || !Number.isFinite(+v) ? d : +v; }
function typoZ(b) {                       // głębia bloku: pole z albo domyślna warstwy
  return b && b.z !== undefined && b.z !== null && b.z !== "" ? typoClamp(typoLiczba(b.z, 1), 0.3, 3) : TYPO_KAMERA.z[b && b.warstwa === "tyl" ? "tyl" : "przod"];
}
function typoZSlowa(b, w) {               // głębia słowa: własna albo bloku przesunięta przez `glebia`
  if (w && w.z !== undefined && w.z !== null && w.z !== "") return typoClamp(typoLiczba(w.z, 1), 0.3, 3);
  return typoZ(b) * (1 - TYPO_KAMERA.glebiaSlowa * typoClamp(Math.round(+(w && w.glebia) || 0), -1, 1));
}
function typoRuch(b) {                    // własny ruch bloku w bezpiecznej postaci (edytor.kamera_ruch_norm) albo null
  const r = b && b.kamera;
  if (!r || typeof r !== "object" || !TYPO_RUCHY.includes(r.ruch)) return null;
  if (r.ruch === "brak") return { ruch: "brak" };
  const o = { ruch: r.ruch, sila: typoClamp(typoLiczba(r.sila, 0.5), 0.05, 1), krzywa: TYPO_KRZYWE.includes(r.krzywa) ? r.krzywa : "plynnie" };
  if (r.ruch === "przesuniecie") o.kierunek = TYPO_KIERUNKI.includes(r.kierunek) ? r.kierunek : "prawo";
  if (Number.isInteger(r.slowo) && r.slowo >= 0 && r.slowo < b.slowa.length) o.slowo = r.slowo;
  return o;
}
// Ruch ze stylu kamery dla bloku bez własnego (edytor.kamera_auto): za osobą najazd; kamera w głębi odjeżdża
// (dynamiczna: przy następnym bloku, spokojna: po `trzymaj` s); w spoczynku uderzenie = najazd (dynamiczna: szybki,
// od słowa), co trzeci spokojny blok (dynamiczna: każdy) przesunięcie. `stan` = {wcisnieta, od, spokoj}.
function typoKameraAuto(b, styl, stan) {
  if (b.end - b.start < TYPO_KAMERA.minBlok) return null;
  const sila = TYPO_KAMERA.sila[styl], hit = b.slowa.findIndex((w) => +w.waga === 3);
  if (b.warstwa === "tyl") return { ruch: "najazd", sila, krzywa: "plynnie" };
  if (stan.wcisnieta) return styl === "dynamiczna" || b.start - stan.od >= TYPO_KAMERA.trzymaj ? { ruch: "odjazd", sila, krzywa: "plynnie" } : null;
  if (hit >= 0) return styl === "dynamiczna" ? { ruch: "najazd", sila, krzywa: "uderzenie", slowo: hit } : { ruch: "najazd", sila, krzywa: "plynnie" };
  stan.spokoj++;
  if (styl === "dynamiczna" || stan.spokoj % 3 === 0) return { ruch: "przesuniecie", sila, krzywa: "plynnie", kierunek: typoLiczba(b.x, 0.5) >= 0.5 ? "prawo" : "lewo" };
  return null;
}
function typoKameraRuchy(T) {             // [[blok, ruch]] po czasie (edytor.kamera_ruchy)
  const styl = T.kamera && T.kamera.styl, out = [], stan = { wcisnieta: false, od: 0, spokoj: 0 };
  for (const b of typoBloki({ typo: T }).slice().sort((a, c) => a.start - c.start)) {
    let r = typoRuch(b);
    if (!r && TYPO_KAMERA.sila[styl]) r = typoKameraAuto(b, styl, stan);
    if (!r || r.ruch === "brak") continue;
    out.push([b, r]);
    if (r.ruch === "najazd" && !stan.wcisnieta) stan.od = b.start;
    stan.wcisnieta = r.ruch === "najazd" || (stan.wcisnieta && r.ruch === "przesuniecie");
  }
  return out;
}
function typoKrzywa(k, p) { const x = typoClamp(p, 0, 1); return k === "uderzenie" ? 1 - Math.pow(1 - x, 3) : x * x * (3 - 2 * x); }
function typoKameraStanOdc(odc, t) {      // [kz, kx, ky] w chwili t (edytor.kamera_stan)
  let s = [0, 0, 0];
  for (const o of odc) {
    if (t < o.a) break;
    const e = typoKrzywa(o.krzywa, o.b <= o.a ? 1 : (Math.min(t, o.c) - o.a) / (o.b - o.a));
    s = o.s0.map((v, i) => v + (o.s1[i] - v) * e);
  }
  return s;
}
// Ruchy → odcinki {a, b, c, s0, s1, krzywa} (edytor.kamera_odcinki: te same liczby, więc film i napisy jadą razem).
function typoKameraOdcinki(T) {
  const odc = [], r5 = (v) => Math.round(v * 1e5) / 1e5, z2 = (z, v) => typoClamp(v, -z / 2, z / 2);
  for (const [b, r] of typoKameraRuchy(T)) {
    let a = b.start;
    if (r.slowo !== undefined && r.slowo < b.slowa.length) a += Math.max(0, (+b.slowa[r.slowo].t || 0) - TYPO_LEAD);
    if (odc.length) a = Math.max(a, odc[odc.length - 1].a);
    let koniec = r.krzywa === "uderzenie" ? Math.min(a + TYPO_KAMERA.uderzenie, b.end) : b.end;
    koniec = Math.max(koniec, a + 0.1);
    if (odc.length) odc[odc.length - 1].c = Math.min(odc[odc.length - 1].b, a);
    let [z0, x0, y0] = typoKameraStanOdc(odc, a), z1, x1, y1;
    const sila = typoLiczba(r.sila, 0.5), dz = 0.04 + 0.12 * sila, dp = 0.015 + 0.05 * sila;
    if (r.ruch === "najazd") {
      z1 = Math.min(TYPO_KAMERA.zmax, z0 + dz, Math.max(z0, typoZ(b) * (1 - 1 / TYPO_KAMERA.skala)));   // napis bloku ≤ ×skala
      x1 = x0 + (typoLiczba(b.x, 0.5) - 0.5) * dz * 0.5; y1 = y0 + (typoLiczba(b.y, 0.5) - 0.5) * dz * 0.5;
    } else if (r.ruch === "odjazd") {
      if (z0 < dz / 2) z0 = Math.min(TYPO_KAMERA.zmax, z0 + dz);   // ze spoczynku: skok w głąb, potem odjazd
      z1 = 0; x1 = 0; y1 = 0;
    } else {
      const k = r.kierunek || "prawo";
      x1 = k === "lewo" || k === "prawo" ? (k === "prawo" ? dp : -dp) : x0;
      y1 = k === "gora" || k === "dol" ? (k === "dol" ? dp : -dp) : y0;
      z1 = Math.min(TYPO_KAMERA.zmax, Math.max(z0, 2 * Math.abs(x1) + 0.01, 2 * Math.abs(y1) + 0.01));
    }
    x1 = z2(z1, x1); y1 = z2(z1, y1); x0 = z2(z0, x0); y0 = z2(z0, y0);
    const r4 = (v) => Math.round(v * 1e4) / 1e4;
    odc.push({ a: r4(a), b: r4(koniec), c: r4(koniec), krzywa: r.krzywa, s0: [z0, x0, y0].map(r5), s1: [z1, x1, y1].map(r5) });
  }
  return odc;
}
const TYPO_KAMERA_CACHE = new WeakMap();  // plan → odcinki i bloki (plan w edytorze zmienia się nowym obiektem)
function typoKameraDane(T) {
  let d = TYPO_KAMERA_CACHE.get(T);
  if (!d) {
    const bloki = typoBloki({ typo: T }).map((b) => ({ ts: b.start + Math.max(0, +b.slowa[0].t || 0) - TYPO_LEAD, z: typoZ(b) }))
      .sort((a, c) => a.ts - c.ts);
    d = { odc: typoKameraOdcinki(T), bloki };
    TYPO_KAMERA_CACHE.set(T, d);
  }
  return d;
}
function typoOstrosc(d, t) {              // głębia ostrości: najnowszy widoczny blok, przejście w 0,3 s
  let f = 1, cel = null, od = 0;
  for (const b of d.bloki) {
    if (b.ts > t) break;
    if (cel === null) { f = b.z; cel = b.z; od = b.ts; continue; }
    f += (cel - f) * typoKrzywa("plynnie", (b.ts - od) / TYPO_KAMERA.ostrosc);
    cel = b.z; od = b.ts;
  }
  return cel === null ? 1 : f + (cel - f) * typoKrzywa("plynnie", (t - od) / TYPO_KAMERA.ostrosc);
}
// Kamera w chwili t: {z, x, y (kz, kx, ky), f (głębia ostrości), a (przysłona)} albo null (plan bez kamery).
function typoKamera(P, t) {
  const T = P && P.typo, K = T && T.kamera;
  if (!K || typeof K !== "object") return null;
  const d = typoKameraDane(T), [z, x, y] = typoKameraStanOdc(d.odc, t);
  return { z, x, y, f: K.ostrosc === "osoba" ? 1 : typoOstrosc(d, t), a: typoClamp(typoLiczba(K.przyslona, 0.5), 0, 1) };
}
// Punkt w spoczynku (x, y: część kadru) na głębokości z → miejsce na ekranie (część kadru) i skala.
function typoRzut(k, x, y, z) {
  const d = Math.max(0.05, z - k.z);
  return { x: 0.5 + ((x - 0.5) * z - k.x) / d, y: 0.5 + ((y - 0.5) * z - k.y) / d, s: z / d };
}
// Rozmycie z głębi ostrości (σ w px przy krótszym boku 1080); słowo bez własnej głębi czytelne (limit `plaski`).
function typoRozmycie(k, z, wlasna) {
  const d = Math.max(0.05, z - k.z), df = Math.max(0.05, k.f - k.z);
  return Math.min((wlasna ? TYPO_KAMERA.wlasne : TYPO_KAMERA.plaski) * k.a, TYPO_KAMERA.rozmycie * k.a * Math.abs(d - df) / d);
}
function typoKameraSpoczynek(k) { return !k || (Math.abs(k.z) < 1e-6 && Math.abs(k.x) < 1e-6 && Math.abs(k.y) < 1e-6); }
// Przekształcenie kanwy W×H tak, jak kamera widzi film (z = 1); wołający robi save/restore.
function typoKameraNa(g, k, W, H) {
  const s = 1 / Math.max(0.05, 1 - k.z);
  g.translate(W / 2, H / 2); g.scale(s, s); g.translate(-W / 2 - k.x * W, -H / 2 - k.y * H);
}
// Obraz filmu (z = 1) przez kamerę: klatka arkusza, sylwetka osoby; bez kamery zwykłe drawImage.
function typoKameraObraz(g, img, P, W, H, t) {
  const k = typoKamera(P, t);
  if (typoKameraSpoczynek(k)) { g.drawImage(img, 0, 0, W, H); return; }
  g.save(); typoKameraNa(g, k, W, H); g.drawImage(img, 0, 0, W, H); g.restore();
}
// To samo jako CSS transform (podgląd edytora: warstwy wideo, transform-origin na środku).
function typoKameraCss(k) {
  if (typoKameraSpoczynek(k)) return "";
  const s = 1 / Math.max(0.05, 1 - k.z);
  return `scale(${s.toFixed(5)}) translate(${(-k.x * 100).toFixed(4)}%, ${(-k.y * 100).toFixed(4)}%)`;
}

// ---------------------------------------------------------------- efekty: pierścień wokół głowy, przejście przez osobę
// blok.efekt = {rodzaj: pierscien|przejscie, kierunek: lewo|prawo, sledz: [[t, dx, dy]]}, pierścień: predkosc (°/s),
// nachylenie (°), powtorz (napis dookoła koła, domyślnie tak); przejście: kolejnosc za-przod|przod-za. Normalizuje
// edytor.efekt_norm (te same listy i liczby, test pilnuje zgodności). `sledz`: przesunięcie środka (część kadru) od
// początku bloku, za ruchem głowy (typografia.py efekt liczy je z maski osoby). Blok z efektem rysuje się w obu
// warstwach: część „tyl” idzie pod sylwetkę osoby (maska.py), część „przod” nad nią.
//   pierścień   napis na poziomym kole wokół głowy: środek koła = x, y bloku, średnica = w · szerokość kadru, litery
//               ~0,11 średnicy (× rozmiar, waga słowa). Litera na kącie θ stoi na głębi z = 1 − ρ·sin θ (osoba z = 1,
//               ρ = 0,35 · średnica / szerokość kadru, rzut 1 / z wokół środka koła): przednia połowa (sin θ > 0)
//               jest bliżej, szersza i większa, w warstwie „przod” (przed twarzą), tylna w „tyl” (osoba ją zasłania).
//               Litera leży w płaszczyźnie stycznej do koła: z tyłu w lustrze i ciemniej, bokiem do widza znika, więc
//               zmiana warstwy jest niewidoczna. Koło rozwija się w 0,35 s; `kierunek` lewo = przód jedzie w lewo
//               (czyta się jak pasek wiadomości), pierwsze słowo zaczyna na środku przodu. Kamera planu działa na
//               każdą literę (rzut z jej głębi).
//   przejście   blok jedzie poziomo przez szew (x bloku = środek ciała) w pierwszych 70% swojego czasu, od strony wejścia
//               do całości po drugiej stronie, i tam zostaje do czytania; po stronie wejścia jest w jednej warstwie,
//               za szwem w drugiej (za-przod: wchodzi za osobę, wychodzi przed nią).
const TYPO_EFEKTY = ["pierscien", "przejscie"];
const TYPO_EFEKT_KIERUNKI = ["lewo", "prawo"];
const TYPO_EFEKT_KOLEJNOSC = ["za-przod", "przod-za"];
const TYPO_EFEKT = { predkosc: 40, predkoscMin: 5, predkoscMax: 180, nachylenie: 14, nachylenieMax: 40, sledz: 40,
  litera: 0.11, glebia: 0.35, rozwin: 0.35, tyl: 0.75, zapas: 0.03, droga: 0.7 };
const TYPO_EFEKT_WAGA = [0.8, 1, 1.12, 1.25];   // litery pierścienia wg wagi słowa (mniejsza rozpiętość niż w bloku)
function typoEfekt(b) {                   // efekt bloku w bezpiecznej postaci (edytor.efekt_norm) albo null
  const e = b && b.efekt;
  if (!e || typeof e !== "object" || !TYPO_EFEKTY.includes(e.rodzaj)) return null;
  const E = TYPO_EFEKT, pier = e.rodzaj === "pierscien";
  const o = { rodzaj: e.rodzaj, kierunek: TYPO_EFEKT_KIERUNKI.includes(e.kierunek) ? e.kierunek : pier ? "lewo" : "prawo" };
  if (pier) {
    o.predkosc = typoClamp(typoLiczba(e.predkosc, E.predkosc), E.predkoscMin, E.predkoscMax);
    o.nachylenie = typoClamp(typoLiczba(e.nachylenie, E.nachylenie), -E.nachylenieMax, E.nachylenieMax);
    o.powtorz = e.powtorz !== false;
  } else o.kolejnosc = TYPO_EFEKT_KOLEJNOSC.includes(e.kolejnosc) ? e.kolejnosc : "za-przod";
  o.sledz = (Array.isArray(e.sledz) ? e.sledz : [])
    .filter((q) => Array.isArray(q) && q.length === 3 && q.every((v) => typeof v === "number" && Number.isFinite(v)))
    .sort((a, c) => a[0] - c[0]).slice(0, E.sledz);
  return o;
}
function typoSledz(e, rel) {              // [dx, dy] środka efektu w chwili rel od początku bloku (liniowo między punktami)
  const s = e && e.sledz;
  if (!s || !s.length) return [0, 0];
  if (rel <= s[0][0]) return [s[0][1], s[0][2]];
  for (let i = 1; i < s.length; i++) {
    if (rel >= s[i][0]) continue;
    const [t0, x0, y0] = s[i - 1], [t1, x1, y1] = s[i], f = (rel - t0) / Math.max(1e-6, t1 - t0);
    return [x0 + (x1 - x0) * f, y0 + (y1 - y0) * f];
  }
  const l = s[s.length - 1];
  return [l[1], l[2]];
}
// Warstwa słowa: własna głębia z decyduje (z > 1 = za osobą), bez niej warstwa bloku (edytor.typo_warstwy).
function typoWarstwaSlowa(b, w) {
  if (w && w.z !== undefined && w.z !== null && w.z !== "") return typoZSlowa(b, w) > 1 ? "tyl" : "przod";
  return b.warstwa === "tyl" ? "tyl" : "przod";
}
function typoWarstwyBloku(b) {            // warstwy, w których blok coś rysuje: ["tyl"], ["przod"] albo obie
  if (typoEfekt(b)) return ["tyl", "przod"];
  const s = new Set(b.slowa.map((w) => typoWarstwaSlowa(b, w)));
  return ["tyl", "przod"].filter((k) => s.has(k));
}
// Przejście w chwili now: szew (x środka ciała, część kadru), środek bloku x, kierunek i średnia prędkość (kadry/s).
function typoPrzejscieStan(b, e, uw, W, now) {
  const [dx, dy] = typoSledz(e, now - b.start), szew = typoLiczba(b.x, 0.5) + dx, dir = e.kierunek === "lewo" ? -1 : 1;
  const pol = uw / 2 / W + TYPO_EFEKT.zapas, dl = Math.max(0.1, (b.end - b.start) * TYPO_EFEKT.droga);
  const p = typoKrzywa("plynnie", (now - b.start) / dl);
  return { szew, dy, dir, x: szew + dir * pol * (2 * p - 1), v: (2 * pol) / dl };
}
// Układ pierścienia: promień R (px), litery po kolei z pozycją `a` na obwodzie (środek litery, px łuku), słowa (od, do),
// powtórzenia n i długość łuku na powtórzenie (nadmiar w odstępie z kropką). Napis dłuższy niż obwód: mniejsze litery.
function typoPierscienUklad(ctx, b, e, P, W, H) {
  const m = typoMotyw(P), R = (typoClamp(typoLiczba(b.w, 0.5), 0.15, 1) * W) / 2;
  const baza = TYPO_EFEKT.litera * 2 * R * typoClamp(typoLiczba(b.rozmiar, 1), 0.3, 3);
  const miara = (s, px, t) => { ctx.font = typoFont(s.kroj, px); return ctx.measureText(t).width; };
  const zbuduj = (k) => {
    const gl = [], slowa = [];
    let x = 0;
    b.slowa.forEach((w, j) => {
      // płytka (`plyta`: słaby kontrast) nie pod każdą literą koła; styl `tlo` ustawiony ręcznie zostaje
      const s = typoSlowo({ ...w, plyta: false }, m, b.uklad), px = baza * k * TYPO_EFEKT_WAGA[s.waga] * typoClamp(typoLiczba(w.skala, 1), 0.3, 3);
      if (j) x += miara(s, px, " ");
      const od = x;
      for (const ch of Array.from(s.tekst)) { const adv = miara(s, px, ch); gl.push({ ch, j, adv, px, s, src: w, a: x + adv / 2 }); x += adv; }
      slowa.push({ od, do: x, px, tekst: w.tekst });
    });
    const s = typoSlowo({ tekst: "•", waga: 0 }, m, b.uklad), px = baza * k * TYPO_EFEKT_WAGA[0], adv = miara(s, px, "•");
    return { gl, slowa, dl: x, sep: { ch: "•", j: -1, adv, px, s, src: {} }, odstep: 2 * miara(s, px, " ") + adv };
  };
  const obw = 2 * Math.PI * R;
  let L = zbuduj(1);
  if (L.dl + (e.powtorz ? L.odstep : 0) > obw * 0.96) L = zbuduj((obw * 0.95) / (L.dl + (e.powtorz ? L.odstep : 0)));
  const n = e.powtorz ? Math.max(1, Math.floor(obw / (L.dl + L.odstep))) : 1;
  return { ...L, R, n, krok: obw / n, S: Math.min(W, H) / 1080 };
}
let TYPO_PLOTNO = null;                   // wspólna kanwa robocza pierścienia (rysowany litera po literze)
function typoPlotno(w, h) {
  const c = TYPO_PLOTNO || (TYPO_PLOTNO = document.createElement("canvas"));
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; } else c.getContext("2d").clearRect(0, 0, w, h);
  return c;
}
// Środek pierścienia w chwili now (px, z `sledz`), kąt pierwszej litery i postęp rozwinięcia.
function typoPierscienStan(b, e, U, W, H, now) {
  const rel = now - b.start, [dx, dy] = typoSledz(e, rel), w0 = U.slowa.length ? (U.slowa[0].od + U.slowa[0].do) / 2 : 0;
  return { cx: (typoLiczba(b.x, 0.5) + dx) * W, cy: (typoLiczba(b.y, 0.3) + dy) * H, roz: typoEaseOut(rel / TYPO_EFEKT.rozwin),
    th0: Math.PI / 2 + w0 / U.R + (e.kierunek === "prawo" ? -1 : 1) * ((e.predkosc * Math.PI) / 180) * rel };
}
// Litery pierścienia w chwili now (bez rysowania; test liczy na nich podział warstw): {U, Q, rot, sn, cn, lit: [{q, w
// (postęp wejścia słowa), s, c (sin i cos kąta), z, warstwa, x, y (px kadru), sc (skala), alfa}]}, tył przed przodem.
function typoPierscienLitery(ctx, b, e, P, W, H, now, st) {
  const U = typoPierscienUklad(ctx, b, e, P, W, H), Q = typoPierscienStan(b, e, U, W, H, now);
  const k = typoKamera(P, now), R = U.R * (0.6 + 0.4 * Q.roz);
  const nach = (e.nachylenie * Math.PI) / 180, sn = Math.sin(nach), cn = Math.cos(nach);
  const rot = (typoLiczba(b.rot, 0) * Math.PI) / 180, cr = Math.cos(rot), sr = Math.sin(rot);
  const rho = TYPO_EFEKT.glebia * ((2 * U.R) / W), wy = st.wy === "zanik" || st.wy === "smuga" ? 1 - st.e : 1;
  const lit = [];
  for (let r = 0; r < U.n; r++) {
    for (const q of U.gl) if (st.slowa[q.j] >= 0) lit.push([r * U.krok + q.a, q, st.slowa[q.j]]);
    if (e.powtorz) lit.push([r * U.krok + U.dl + (U.krok - U.dl) / 2, U.sep, 1]);
  }
  const out = lit.map(([a, q, w]) => {
    const th = Q.th0 - a / U.R, s = Math.sin(th), c = Math.cos(th);
    const z = 1 - rho * s, pz = 1 / z;                                   // perspektywa koła: przód szerszy i większy
    const X0 = R * c * pz, Y0 = R * sn * s * pz;                         // przód (sin θ > 0) niżej przy nachyleniu > 0
    let x = Q.cx + X0 * cr - Y0 * sr, y = Q.cy + X0 * sr + Y0 * cr, sc = (pz * R) / U.R;   // rozwijanie: litery rosną z kołem
    if (k) { const p = typoRzut(k, x / W, y / H, z); x = p.x * W; y = p.y * H; sc *= p.s; }
    const kraw = typoClamp((Math.abs(s) - 0.05) / 0.2, 0, 1);            // bokiem do widza: znika
    return { q, w, s, c, z, x, y, sc, warstwa: s > 0 ? "przod" : "tyl", alfa: kraw * Q.roz * wy * (s > 0 ? 1 : TYPO_EFEKT.tyl) };
  }).sort((p1, p2) => p1.s - p2.s);
  return { U, Q, rot, sn, cn, lit: out };
}
function typoRysujPierscien(ctx, b, e, P, W, H, now, st, warstwa) {
  const m = typoMotyw(P), L = typoPierscienLitery(ctx, b, e, P, W, H, now, st);
  const M = Math.round(Math.min(W, H) * 0.25), c = typoPlotno(W + 2 * M, H + 2 * M), g = c.getContext("2d");
  for (const o of L.lit) {
    if (o.alfa <= 0 || (warstwa && o.warstwa !== warstwa)) continue;
    const q = o.q, gs = { ...q.s, tekst: q.ch, px: q.px, w: q.adv, x: -q.adv / 2, y: q.px * 0.35, src: q.src, alfa: o.alfa };
    g.save();       // litera w płaszczyźnie stycznej do koła: oś x wzdłuż obwodu (z tyłu w lustrze), oś y pionowo
    g.translate(o.x + M, o.y + M); g.rotate(L.rot); g.transform(o.sc * o.s, -o.sc * L.sn * o.c, 0, o.sc * L.cn, 0, 0);
    typoRysujSlowo(g, gs, o.w, typoWejscie(b, q.src, m), m);
    g.restore();
  }
  ctx.drawImage(c, -M, -M);
  const maxPx = Math.max(1, ...L.U.gl.map((q) => q.px));
  return { slowa: [], w: 2 * (L.U.R + maxPx * 0.6), h: 2 * (L.U.R * Math.abs(L.sn) + maxPx * 1.1), cx: L.Q.cx, cy: L.Q.cy, S: L.U.S, pierscien: L.U };
}

let TYPO_SZUM = null;   // tekstura „ulica”: stały szum (deterministyczny), wycinany z liter jak zdarta farba
function typoSzum() {
  if (TYPO_SZUM) return TYPO_SZUM;
  const c = document.createElement("canvas");
  c.width = c.height = 192;
  const g = c.getContext("2d");
  let seed = 7;
  const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  for (let i = 0; i < 2000; i++) {
    const r = rnd() < 0.92 ? 0.4 + rnd() * 1.1 : 1.6 + rnd() * 2.6;
    g.fillStyle = `rgba(0,0,0,${0.25 + rnd() * 0.6})`;
    g.beginPath(); g.arc(rnd() * 192, rnd() * 192, r, 0, Math.PI * 2); g.fill();
  }
  TYPO_SZUM = c;
  return c;
}
function typoRgb(hex) {                  // "#RGB" / "#RRGGBB" → [r, g, b]; błędny kolor = biały (czarny zostaje czarny)
  const h = String(hex || "#ffffff").replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((x) => x + x).join("") : h.slice(0, 6), 16);
  const v = Number.isNaN(n) ? 0xffffff : n;
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}
function typoJasnosc(hex) {               // względna luminancja WCAG (0–1), ta sama co luminancja() w typografia.py
  const f = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  const [r, g, b] = typoRgb(hex);
  return 0.2126 * f(r / 255) + 0.7152 * f(g / 255) + 0.0722 * f(b / 255);
}
function typoJasniej(hex, k) {           // kolor przesunięty o k (0–1) w stronę bieli
  return `rgb(${typoRgb(hex).map((c) => Math.round(c + (255 - c) * k)).join(",")})`;
}
function typoMieszaj(a, b, k) {          // kolor a przesunięty o k (0–1) w stronę b
  const B = typoRgb(b);
  return `rgb(${typoRgb(a).map((c, i) => Math.round(c + (B[i] - c) * k)).join(",")})`;
}
function typoCiemniej(hex, k) {
  return `rgb(${typoRgb(hex).map((c) => Math.round(c * k)).join(",")})`;
}

// Jedno słowo na kanwie bloku (współrzędne bloku), z wejściem a (0–1); `rozm` = rozmycie z głębi ostrości (px kanwy).
function typoRysujSlowo(g, s, a, wejscie, m, rozm = 0) {
  const px = s.px;
  let tekst = s.tekst;
  if (wejscie === "pisanie" && a < 1) tekst = Array.from(tekst).slice(0, Math.max(1, Math.ceil(Array.from(tekst).length * a))).join("");
  g.save();
  g.font = typoFont(s.kroj, px);
  g.textBaseline = "alphabetic";
  let x = s.x, y = s.y, alpha = (s.glebia < 0 ? 0.8 : 1) * (s.alfa ?? 1);   // alfa: krycie litery pierścienia
  if (wejscie === "pop" && a < 1) {
    const k = 1 + 0.38 * (1 - typoEaseBack(a));
    g.translate(x + s.w / 2, y - px * 0.35); g.scale(k, k); g.translate(-(x + s.w / 2), -(y - px * 0.35));
    alpha *= typoClamp(a * 3, 0, 1);
  } else if (wejscie === "zjazd" && a < 1) {
    x += (1 - typoEaseOut(a)) * px * 0.5; alpha *= a;
  } else if (wejscie === "skok" && a < 1) {     // rośnie od zera z przeskokiem, oparte o linię pisma
    const k = Math.max(0.001, typoSkok(a * TYPO_WEJSCIA.skok));
    g.translate(x + s.w / 2, y); g.scale(k, k); g.translate(-(x + s.w / 2), -y);
  } else if (wejscie === "maska" && a < 1) {
    g.beginPath(); g.rect(x - px, y - px * 1.05, s.w + px * 2, px * 1.3); g.clip();
    y += (1 - typoEaseOut(a)) * px * 1.1;
  }
  g.globalAlpha = alpha;
  const miekko = s.glebia < 0 ? Math.min(2.5, px * 0.012) : 0;    // dalej = lekko miękko, ale czytelnie
  const blur = rozm >= 0.05 ? Math.hypot(miekko, rozm) : miekko;   // plus głębia ostrości kamery
  if (blur > 0) g.filter = `blur(${blur.toFixed(1)}px)`;
  const fill = s.kolor;
  const konturFaza = wejscie === "kontur" && a < 1;
  const cien = () => { g.shadowColor = "rgba(0,0,0,0.55)"; g.shadowBlur = px * 0.16; g.shadowOffsetY = px * 0.04; };
  const bezCienia = () => { g.shadowColor = "transparent"; g.shadowBlur = 0; g.shadowOffsetY = 0; };
  const plyta = s.styl === "tlo" ? (s.src && s.src.kolor) || m.akcent : null;   // płytka w kolorze słowa
  if (plyta) {
    g.fillStyle = plyta;
    g.fillRect(x - px * 0.12, y - px * 0.82, s.w + px * 0.24, px * 1.02);
  }
  const obw = s.waga === 3 ? m.obrys || "#FF3D7F" : m.obrys2 || "#1E2A78";   // kolor obrysu w stylu show
  if (s.styl === "show" && !konturFaza) {       // program rozrywkowy: dwie kopie w głąb, obrys w kolorze, biały obrys
    const bialy = px * 0.075, zew = px * 0.07, ext = Math.max(2, px * 0.09);   // jak 13/12/16 px przy 172 px
    g.lineJoin = "round"; g.lineWidth = 2 * (bialy + zew);
    g.shadowColor = "rgba(26,10,40,0.36)"; g.shadowBlur = px * 0.064; g.shadowOffsetY = px * 0.07;
    g.strokeStyle = typoCiemniej(obw, 0.62);
    for (const d of [ext, ext / 2]) g.strokeText(tekst, x + d * 0.3, y + d);
    bezCienia();
    g.strokeStyle = obw; g.strokeText(tekst, x, y);
    g.lineWidth = 2 * bialy; g.strokeStyle = "#FFFFFF"; g.strokeText(tekst, x, y);
  }
  if (s.styl === "3d" && !konturFaza) {          // wyciągnięcie w głąb: kopie w ciemniejszym kolorze, potem lico
    const n = Math.max(3, Math.round(px * 0.09));
    g.fillStyle = typoCiemniej(fill, 0.32);
    for (let i = n; i >= 1; i--) g.fillText(tekst, x + i * 0.75, y + i);
  }
  if (s.styl === "obrys" && !konturFaza) {      // gruby obrys pod literą (napisy z social): czytelne na każdym tle
    g.lineJoin = "round"; g.lineWidth = Math.max(2, px * 0.15);
    g.strokeStyle = typoJasnosc(fill) > 0.18 ? "#0B0B0B" : "#FFFFFF";   // ciemne słowo: biały obrys jak naklejka
    cien(); g.strokeText(tekst, x, y); bezCienia();
  }
  if (s.styl === "kontur" || konturFaza) {
    g.lineJoin = "round"; g.lineWidth = Math.max(1.5, px * 0.045); g.strokeStyle = fill;
    cien(); g.strokeText(tekst, x, y); bezCienia();
  }
  if (s.styl !== "kontur") {
    const fa = konturFaza ? typoClamp((a - 0.45) / 0.55, 0, 1) : 1;
    if (fa > 0) {
      g.globalAlpha = alpha * fa;
      g.fillStyle = plyta ? (typoJasnosc(plyta) > 0.36 ? "#111111" : "#FFFFFF") : fill;   // napis na płytce: kontrast
      if (s.styl === "blask") {                  // neon: poświata w kolorze, jasny rdzeń (ciemny kolor nie gaśnie)
        g.shadowColor = fill; g.shadowBlur = px * 0.38; g.fillText(tekst, x, y);
        if (typoJasnosc(fill) < 0.3) g.fillStyle = typoJasniej(fill, 0.55);
      }
      if (s.styl === "show") {                   // gradient z góry na dół: jaśniej → kolor → w stronę obrysu
        const gr = g.createLinearGradient(0, y - px * 0.8, 0, y + px * 0.1);
        gr.addColorStop(0, typoJasniej(fill, 0.75)); gr.addColorStop(0.5, fill); gr.addColorStop(1, typoMieszaj(fill, obw, 0.35));
        g.fillStyle = gr;
      }
      if (s.styl !== "3d" && s.styl !== "tlo" && s.styl !== "blask" && s.styl !== "obrys" && s.styl !== "show") cien();
      g.fillText(tekst, x, y);
      bezCienia();
      if (s.styl === "show") {                   // połysk: biel 0,55 u góry litery, znika w 46% wysokości
        const gl = g.createLinearGradient(0, y - px * 0.8, 0, y + px * 0.1);
        gl.addColorStop(0, "rgba(255,255,255,0.55)"); gl.addColorStop(0.46, "rgba(255,255,255,0)");
        g.fillStyle = gl; g.fillText(tekst, x, y);
      }
    }
  }
  if (m.tekstura && s.kroj !== "grunge") {        // zdarta farba w skali słowa: małe słowo dalej czytelne
    const k = typoClamp(px / 110, 0.35, 3);
    g.globalAlpha = 1; g.filter = "none";
    g.globalCompositeOperation = "destination-out";
    g.beginPath(); g.rect(x - px * 0.3, y - px * 1.15, s.w + px * 0.6, px * 1.6); g.clip();
    g.translate(x, y); g.scale(k, k);
    g.fillStyle = g.createPattern(typoSzum(), "repeat");
    g.fillRect((-px * 0.3) / k, (-px * 1.15) / k, (s.w + px * 0.6) / k, (px * 1.6) / k);
  }
  g.restore();
}

// Blok na osobnej kanwie (tekstura, perspektywa i smuga działają na całości), potem na kanwę główną z obrotem.
// `stan` (opcjonalnie) zamiast stanu w chwili now: kontrola rysuje tak pojedyncze słowa bloku.
// Kamera (plan z `kamera`): blok rysowany od razu w skali, w której go widać (ostre litery przy najeździe), w miejscu
// z rzutu swojej głębi; słowo z inną głębią niż blok (glebia, z) ma własny rzut (paralaksa w bloku) i rozmycie.
// `warstwa` (opcjonalnie, blok w obu warstwach): tylko ta część bloku — słowa tej warstwy, przy przejściu strona
// szwu, przy pierścieniu połowa koła. Bez niej cały blok (kontrola, karta stylu).
function typoRysujBlok(ctx, b, P, W, H, now, stan, warstwa) {
  const m = typoMotyw(P);
  const st = stan || typoStan(b, P, now);
  if (!st.slowa.some((a) => a >= 0)) return null;
  const e = typoEfekt(b);
  if (e && e.rodzaj === "pierscien") return typoRysujPierscien(ctx, b, e, P, W, H, now, st, warstwa);
  const u = typoUklad(ctx, b, P, W, H);
  const k = typoKamera(P, now), zb = typoZ(b), prz = e ? typoPrzejscieStan(b, e, u.w, W, now) : null;
  const bx = prz ? prz.x * W : u.cx, by = prz ? u.cy + prz.dy * H : u.cy;      // środek bloku w spoczynku kamery
  let cx = bx, cy = by, sk = 1;
  if (k) { const r = typoRzut(k, bx / W, by / H, zb); cx = r.x * W; cy = r.y * H; sk = r.s; }
  const maxPx = Math.max(...u.slowa.map((s) => s.px));
  const pad = Math.ceil(maxPx * (k ? 0.8 : 0.5) + (k ? 40 * u.S : 0));   // kamera: zapas na paralaksę słów i rozmycie
  const bw = Math.ceil((u.w + pad * 2) * sk), bh = Math.ceil((u.h + pad * 2) * sk);
  const c = document.createElement("canvas");
  c.width = Math.max(1, bw); c.height = Math.max(1, bh);
  const g = c.getContext("2d");
  g.translate(bw / 2, bh / 2);
  if (sk !== 1) g.scale(sk, sk);
  u.slowa.forEach((s, j) => {
    if (st.slowa[j] < 0) return;
    if (warstwa && !prz && typoWarstwaSlowa(b, s.src) !== warstwa) return;   // słowo z głębią po drugiej stronie osoby
    const wej = typoWejscie(b, s.src, m);
    if (!k) { typoRysujSlowo(g, s, st.slowa[j], wej, m); return; }
    const zw = typoZSlowa(b, s.src), wlasna = s.src.z !== undefined && s.src.z !== null && s.src.z !== "";
    const rozm = typoRozmycie(k, zw, wlasna) * u.S;
    if (Math.abs(zw - zb) < 1e-4) { typoRysujSlowo(g, s, st.slowa[j], wej, m, rozm); return; }
    const lx = s.x + s.w / 2, ly = s.y - s.px * 0.35, r = typoRzut(k, (bx + lx) / W, (by + ly) / H, zw);
    const q = r.s / sk;
    g.save(); g.translate((r.x * W - cx) / sk, (r.y * H - cy) / sk); g.scale(q, q); g.translate(-lx, -ly);
    typoRysujSlowo(g, s, st.slowa[j], wej, m, rozm);
    g.restore();
  });
  ctx.save();
  if (prz && warstwa) {                    // przejście: po stronie wejścia jedna warstwa, za szwem (środek ciała) druga
    const wej = e.kolejnosc === "przod-za" ? "przod" : "tyl", sx = (k ? typoRzut(k, prz.szew, by / H, 1).x : prz.szew) * W;
    const lewa = (warstwa === wej) === (prz.dir > 0), B = 4 * Math.max(W, H);
    ctx.beginPath(); ctx.rect(lewa ? sx - B : sx, -B, B, 3 * B); ctx.clip();
  }
  ctx.translate(cx, cy);
  ctx.rotate(((+b.rot || 0) * Math.PI) / 180);
  let alpha = 1, dx = 0;
  if (st.wy === "zanik") alpha = 1 - st.e;
  if (st.wy === "smuga") dx = st.e * st.e * W * 0.4;
  const tilt = typoClamp(+b.tilt || 0, -45, 45) * Math.PI / 180;
  const kopie = st.wy === "smuga" && st.e > 0 ? 7 : 1;
  for (let k = 0; k < kopie; k++) {
    ctx.globalAlpha = alpha / (kopie === 1 ? 1 : kopie * 0.55);
    const ox = dx * (kopie === 1 ? 1 : k / (kopie - 1));
    if (Math.abs(tilt) < 0.01) ctx.drawImage(c, -bw / 2 + ox, -bh / 2);
    else typoPerspektywa(ctx, c, bw, bh, tilt, ox);
  }
  ctx.restore();
  return u;
}
// Obrót wokół osi pionowej z perspektywą: pionowe paski obrazu skalowane jak w rzucie (bliższa krawędź większa).
function typoPerspektywa(ctx, c, bw, bh, tilt, ox) {
  const D = bw * 1.7, cos = Math.cos(tilt), sin = Math.sin(tilt);
  const X = (u) => (u * bw * cos * D) / (D + u * bw * sin);
  const step = Math.max(2, Math.round(bw / 160));
  for (let sx = 0; sx < bw; sx += step) {
    const u0 = sx / bw - 0.5, u1 = Math.min(bw, sx + step) / bw - 0.5;
    const k = D / (D + ((u0 + u1) / 2) * bw * sin);
    const x0 = X(u0), x1 = X(u1);
    ctx.drawImage(c, sx, 0, Math.min(step, bw - sx), bh, x0 + ox, (-bh / 2) * k, Math.max(0.5, x1 - x0 + 0.35), bh * k);
  }
}

// Wszystkie aktywne bloki (opcjonalnie tylko jedna warstwa: "przod" albo "tyl" = za osobą, pod sylwetką).
function typoRysuj(ctx, P, W, H, now, warstwa) {
  const out = [];
  for (const b of typoAktywne(P, now)) {
    const ws = typoWarstwyBloku(b);       // blok z efektem albo słowem z głębią po drugiej stronie osoby: obie warstwy
    if (warstwa && !ws.includes(warstwa)) continue;
    const u = typoRysujBlok(ctx, b, P, W, H, now, undefined, warstwa && ws.length > 1 ? warstwa : undefined);
    if (u) out.push([b, u]);
  }
  return out;
}
// Klucz osi dla sylwetek osoby (maska.py): ten sam napis co edytor.maska_klucz w Pythonie. Inny klucz = klipy
// zmieniły się po liczeniu maski, więc jej klatki nie pasują i napis „za osobą” zostaje w całości widoczny.
function maskaKlucz(P) {
  const k3 = (x, d) => { const v = Number.isFinite(+x) && x !== null && x !== "" ? +x : d; return v.toFixed(3); };
  const czesci = ((P && P.clips) || []).map((c) => {
    const fit = c.fit === "cover" || c.fit === "blur" ? c.fit : "contain";
    const kadr = fit === "cover" ? `,${k3(c.fx, 0.5)},${k3(c.fy, 0.5)},${k3(c.zoom, 1)}` : "";
    return `${c.src}|${k3(c.in, 0)}|${k3(c.out, 0)}|${k3(c.speed, 1)}|${fit}${kadr}`;
  });
  const cv = (P && P.canvas) || {};
  return `${czesci.join(";")}#${Math.trunc(+cv.w || 0)}x${Math.trunc(+cv.h || 0)}@${k3(cv.fps, 30)}`;
}
// Teksty bloków do wczytania krojów (krój + tekst: polskie znaki z podzbioru latin-ext).
function typoFonty(P, W, H) {
  const m = typoMotyw(P);
  const out = new Map();
  for (const b of typoBloki(P)) for (const w of [...b.slowa, ...(typoEfekt(b) ? [{ tekst: "•", waga: 0 }] : [])]) {
    const s = typoSlowo(w, m, b.uklad);               // pierścień: kropka między powtórzeniami krojem małych słów
    const f = typoFont(s.kroj, 64);
    out.set(f, (out.get(f) || "") + s.tekst);
  }
  return [...out.entries()];
}

// ---------------------------------------------------------------- kontrola napisów
// Mierzy tusz liter (nie ramkę bloku) tym samym rendererem co podgląd i eksport, za wzorcami frame-bounds.js
// i glyph-gaps.js z camera-3d-captions (HeyGen, hyperframes-community-skills, Apache-2.0):
//   poza kadrem        tusz bloku za krawędzią kadru przez `kroki` kroków po 1/15 s z rzędu (wyjście bloku się nie liczy),
//   bloki na sobie     tusz dwóch bloków widocznych naraz bliżej niż `styk`,
//   słowa się stykają  tusz dwóch słów pełnego bloku bliżej niż `styk` (słowa rysowane osobno, ten sam układ),
//   za osobą           widać mniej niż `widac` tuszu napisu z tyłu albo osoba go wcale nie zasłania (efekt niewidoczny),
//   strefa, mały       pełny blok pod interfejsem platformy, słowo mniejsze niż `maly` (uwagi),
//   kamera             blok, który w spoczynku jest w kadrze, a ruch kamery go wypycha (osobny kod i rada), słowo
//                      rozmyte głębią ostrości ponad `rozmyte` wysokości liter przez `kroki` kroków (błąd), uderzenie
//                      (waga 3) rozmyte co najmniej `ostre` px (uwaga: ostrość jest gdzie indziej),
//   efekty             pierścień szybszy niż `obroty` wysokości liter na sekundę z przodu albo słowo dłuższe niż przód
//                      koła (łuk 120°: zawija się za głowę), przejście szybsze niż `przejscie` szerokości kadru na
//                      sekundę (błędy), efekt bez sylwetek osoby (błąd: tył napisu szedłby po twarzy) i efekt obok osoby
//                      (uwaga: sylwetka nie zasłania nawet `dotyka` tylnej części, więc efektu nie widać).
// Miary w pikselach przy krótszym boku 1080, skalowane do kanwy pomiaru; tusz = krycie ≥ `prog` (bez cienia i poświaty).
const TYPO_KONTROLA = { krok: 1 / 15, kroki: 5, poza: 3, styk: 4, widac: 0.6, dotyka: 0.03, maly: 30, prog: 160, rozmyte: 0.08, ostre: 2,
  obroty: 6, przejscie: 1 };
const TYPO_RUCHY_OPIS = { najazd: ["najazd", "push-in"], odjazd: ["odjazd", "pull-out"], przesuniecie: ["przesunięcie", "pan"] };
const TYPO_STRONY = { lewo: ["z lewej", "left"], prawo: ["z prawej", "right"], gora: ["u góry", "top"], dol: ["na dole", "bottom"] };

function typoTusz(g, w, h, prog) {          // kanwa → maska 0/1 tuszu
  const d = g.getImageData(0, 0, w, h).data, m = new Uint8Array(w * h);
  for (let i = 0; i < m.length; i++) m[i] = d[i * 4 + 3] >= prog ? 1 : 0;
  return m;
}
function typoRamkaTuszu(m, w, h) {          // {x0, y0, x1, y1} tuszu (x1, y1 tuż za ostatnim pikselem) albo null
  let x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let y = 0; y < h; y++) {
    const o = y * w;
    for (let x = 0; x < w; x++) if (m[o + x]) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; y1 = y; }
  }
  return x1 < 0 ? null : { x0, y0, x1: x1 + 1, y1: y1 + 1 };
}
// Tusz a i b bliżej niż r pikseli (okno kwadratowe)? ra, rb = ich ramki; suma z obrazu całkowego tylko przy styku ramek.
function typoStyk(a, ra, b, rb, w, h, r) {
  if (!ra || !rb) return false;
  const x0 = Math.max(rb.x0, ra.x0 - r), y0 = Math.max(rb.y0, ra.y0 - r);
  const x1 = Math.min(rb.x1, ra.x1 + r), y1 = Math.min(rb.y1, ra.y1 + r);
  if (x0 >= x1 || y0 >= y1) return false;
  const cx0 = Math.max(0, x0 - r), cy0 = Math.max(0, y0 - r), cx1 = Math.min(w, x1 + r), cy1 = Math.min(h, y1 + r);
  const cw = cx1 - cx0, ch = cy1 - cy0, I = new Int32Array((cw + 1) * (ch + 1));
  for (let y = 0; y < ch; y++) {
    let s = 0;
    for (let x = 0; x < cw; x++) { s += a[(cy0 + y) * w + cx0 + x]; I[(y + 1) * (cw + 1) + x + 1] = I[y * (cw + 1) + x + 1] + s; }
  }
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
    if (!b[y * w + x]) continue;
    const xa = Math.max(cx0, x - r) - cx0, xb = Math.min(cx1, x + r + 1) - cx0;
    const ya = Math.max(cy0, y - r) - cy0, yb = Math.min(cy1, y + r + 1) - cy0;
    if (I[yb * (cw + 1) + xb] - I[ya * (cw + 1) + xb] - I[yb * (cw + 1) + xa] + I[ya * (cw + 1) + xa] > 0) return true;
  }
  return false;
}
function typoPokrycie(tusz, sylwetka) {      // część tuszu pod sylwetką (0–1); bez tuszu = 0
  let n = 0, pod = 0;
  for (let i = 0; i < tusz.length; i++) if (tusz[i]) { n++; if (sylwetka[i]) pod++; }
  return n ? pod / n : 0;
}
function typoChwilaPelna(b, m) {            // pełny blok: ostatnie słowo weszło, wyjście jeszcze nie (jak chwile_arkusza)
  const wy = TYPO_WYJSCIA[b.wyjscie || m.wyjscie] ?? 0, ost = b.start + (+b.slowa[b.slowa.length - 1].t || 0);
  return Math.max(ost, Math.min(b.end - wy - 0.03, ost + 0.3));
}

// Kontrola planu na kanwie W×H. opt: {strefy: [{k, x0, y0, x1, y1, nazwa: [pl, en]}] (interfejs platformy w kadrze),
// sylwetka: async (t) => obraz osoby z kanałem alfa albo null (maska.py; bez niej napisy za osobą bez pomiaru)}.
// Wynik: {bloki, problemy: [{poziom: "blad"|"uwaga", kod, blok, t, opis: [pl, en]}]} po czasie.
async function typoKontrola(P, W, H, opt = {}) {
  const K = TYPO_KONTROLA, S = Math.min(W, H) / 1080, m = typoMotyw(P), bloki = typoBloki(P);
  if (typeof fontLoad === "function") for (const [f, txt] of typoFonty(P, W, H)) await fontLoad(f, txt);
  const r = Math.max(1, Math.round(K.styk * S)), tol = Math.max(1, Math.round(K.poza * S));
  const pad = Math.round(Math.min(W, H) * 0.2), cw = W + 2 * pad, ch = H + 2 * pad;
  const c = document.createElement("canvas"); c.width = cw; c.height = ch;
  const g = c.getContext("2d", { willReadFrequently: true });
  const out = [];
  const px = (v) => Math.round(v / S);
  const dodaj = (poziom, kod, b, t, pl, en) => out.push({ poziom, kod, blok: b ? b.id : null, t: Math.round(t * 100) / 100, opis: [pl, en] });
  const tekst = (b) => b.slowa.map((w) => w.tekst).join(" ");
  const rysuj = (b, t, stan, PP = P, warstwa) => {    // tusz bloku na kanwie z marginesem (kadr przesunięty o pad)
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, cw, ch); g.translate(pad, pad);
    typoRysujBlok(g, b, PP, W, H, t, stan, warstwa);
    g.setTransform(1, 0, 0, 1, 0, 0);
    const mk = typoTusz(g, cw, ch, K.prog);
    return { m: mk, r: typoRamkaTuszu(mk, cw, ch) };
  };
  const zaKadr = (q) => q ? { lewo: pad - q.x0, prawo: q.x1 - pad - W, gora: pad - q.y0, dol: q.y1 - pad - H } : {};
  // Kamera: plan bez niej (czy blok w spoczynku jest w kadrze), ruch, który trwa w chwili t, i rozmycie słów bloku.
  const P0 = P.typo && P.typo.kamera ? { ...P, typo: { ...P.typo, kamera: undefined } } : null;
  const ruchy = P0 ? typoKameraRuchy(P.typo) : [];
  const ruchW = (t) => ruchy.reduce((a, x) => (x[0].start <= t + 1e-6 ? x : a), null);
  const uklady = new Map();
  const rozmycie = (b, st, kam) => {          // najgorsze słowo: σ / wysokość liter (px przy 1080) i najbardziej rozmyte uderzenie
    let u = uklady.get(b.id);
    if (!u) { u = typoUklad(g, b, P, W, H); uklady.set(b.id, u); }
    let zle = null, hit = null;
    u.slowa.forEach((sl, j) => {
      if (st.slowa[j] < 0.999) return;                         // słowo jeszcze wchodzi albo go nie ma
      const zw = typoZSlowa(b, sl.src), wl = sl.src.z !== undefined && sl.src.z !== null && sl.src.z !== "";
      const sig = typoRozmycie(kam, zw, wl), wys = (sl.px / u.S) * typoRzut(kam, 0.5, 0.5, zw).s, q = sig / Math.max(1, wys);
      if (!zle || q > zle.q) zle = { q, sig, tekst: sl.src.tekst };
      if (+sl.src.waga === 3 && (!hit || sig > hit.sig)) hit = { sig, tekst: sl.src.tekst };
    });
    return { zle, hit };
  };
  const serie = (klucz, warunek, t, dane, zglos) => {          // `kroki` kroków z rzędu → jedno zgłoszenie na blok
    if (!warunek) { seria.delete(klucz); return; }
    const s0 = seria.get(klucz) || { od: t, n: 0, dane };
    s0.n++; seria.set(klucz, s0);
    if (s0.n === K.kroki && !zgloszone.has(klucz)) { zgloszone.add(klucz); zglos(s0); }
  };

  // 1. Oś po 1/15 s: poza kadrem (seria kroków) i bloki na sobie; tusz liczony tylko przy zmianie stanu bloku.
  const biez = new Map(), seria = new Map(), zgloszone = new Set();
  const koniec = Math.max(0, ...bloki.map((b) => b.end));
  for (let k = 0; k * K.krok < koniec; k++) {
    if (k % 30 === 29) await new Promise((ok) => setTimeout(ok, 0));   // edytor HQ: strona nie zamiera na długim filmie
    const t = (k + 0.5) * K.krok, akt = [];
    for (const b of typoAktywne(P, t)) {
      const st = typoStan(b, P, t);
      if (st.e > 0) { seria.delete(b.id); continue; }          // wyjście (smuga, zanik) może wyjść za kadr
      const kam = typoKamera(P, t), ef = typoEfekt(b);         // kamera w ruchu, efekt: blok w innym miejscu co krok
      const klucz = st.slowa.map((a) => (a < 0 ? "-" : a.toFixed(3))).join(",") + (kam ? `~${[kam.z, kam.x, kam.y, kam.f].map((v) => v.toFixed(4)).join(",")}` : "")
        + (ef ? `@${t.toFixed(4)}` : "");
      let x = biez.get(b.id);
      if (!x || x.klucz !== klucz) { x = { klucz, ...rysuj(b, t, st) }; biez.set(b.id, x); }
      akt.push([b, x]);
      const z = zaKadr(x.r), [str, ile] = Object.entries(z).sort((p, q) => q[1] - p[1])[0] || ["", 0];
      if (ile > tol) {
        const s0 = seria.get(b.id) || { od: t, n: 0, ile: 0, str };
        s0.n++; if (ile > s0.ile) { s0.ile = ile; s0.str = str; }
        seria.set(b.id, s0);
        if (s0.n === K.kroki && !zgloszone.has(`poza:${b.id}`)) {
          zgloszone.add(`poza:${b.id}`);
          const rw = ruchW(t), bez = P0 && !typoKameraSpoczynek(kam) ? zaKadr(rysuj(b, t, st, P0).r) : null;
          if (bez && Math.max(0, ...Object.values(bez)) <= tol && rw) {     // w spoczynku w kadrze: wypycha go kamera
            const [rb, rr] = rw, n = TYPO_RUCHY_OPIS[rr.ruch] || [rr.ruch, rr.ruch];
            dodaj("blad", "poza-kadrem-kamera", b, s0.od, `ruch kamery (${n[0]} z ${rb.id}) wypycha „${tekst(b)}” poza kadr ${TYPO_STRONY[s0.str][0]} (${px(s0.ile)} px): słabszy ruch (siła), blok bliżej środka albo dalej w głąb (większe z)`,
              `the camera move (${n[1]} from ${rb.id}) pushes "${tekst(b)}" out of frame ${TYPO_STRONY[s0.str][1]} (${px(s0.ile)} px): weaker move (strength), block nearer the centre or deeper (larger z)`);
          } else dodaj("blad", "poza-kadrem", b, s0.od, `„${tekst(b)}” wychodzi poza kadr ${TYPO_STRONY[s0.str][0]} (${px(s0.ile)} px): przesuń blok do środka (x, y) albo zmniejsz (rozmiar, w)`,
            `"${tekst(b)}" leaves the frame ${TYPO_STRONY[s0.str][1]} (${px(s0.ile)} px): move it inwards or make it smaller`);
        }
      } else seria.delete(b.id);
      if (!kam || (ef && ef.rodzaj === "pierscien")) continue;   // litery pierścienia bez rozmycia głębi
      const { zle, hit } = rozmycie(b, st, kam);
      serie(`roz:${b.id}`, zle && zle.q > K.rozmyte, t, zle, (s0) => dodaj("blad", "rozmyte", b, s0.od,
        `„${s0.dane.tekst}” w ${b.id} rozmyte ponad czytelność (${s0.dane.sig.toFixed(1)} px, ${Math.round(s0.dane.q * 100)}% wysokości liter): mniejsza przysłona, ostrość na napisie albo głębia z bliżej ostrości`,
        `"${s0.dane.tekst}" in ${b.id} is blurred past readability (${s0.dane.sig.toFixed(1)} px, ${Math.round(s0.dane.q * 100)}% of letter height): lower the aperture, focus on the text or move z closer to focus`));
      serie(`ud:${b.id}`, hit && hit.sig >= K.ostre, t, hit, (s0) => dodaj("uwaga", "uderzenie-rozmyte", b, s0.od,
        `uderzenie „${s0.dane.tekst}” w ${b.id} jest poza ostrością (${s0.dane.sig.toFixed(1)} px): ostrość na napisie, mniejsza przysłona albo słowo na głębi bloku`,
        `the hit word "${s0.dane.tekst}" in ${b.id} is out of focus (${s0.dane.sig.toFixed(1)} px): focus on the text, lower the aperture or keep the word at the block depth`));
    }
    for (let i = 0; i < akt.length; i++) for (let j = i + 1; j < akt.length; j++) {
      const [a, xa] = akt[i], [b, xb] = akt[j], id = `styk:${a.id}:${b.id}`;
      if (zgloszone.has(id) || !typoStyk(xa.m, xa.r, xb.m, xb.r, cw, ch, r)) continue;
      zgloszone.add(id);
      dodaj("blad", "bloki-na-sobie", b, t, `bloki ${a.id} i ${b.id} nachodzą na siebie („${tekst(a)}” / „${tekst(b)}”): rozsuń je (y) albo skróć pierwszy`,
        `blocks ${a.id} and ${b.id} overlap: move them apart or shorten the first one`);
    }
    for (const id of [...biez.keys()]) if (!akt.some(([b]) => b.id === id)) biez.delete(id);
  }

  // Efekt bloku: czytelna prędkość, słowo na przodzie pierścienia, sylwetki osoby i czy osoba zasłania tylną część.
  const kontrolaEfektu = async (b, ef) => {
    const tf = typoChwilaPelna(b, m);
    if (ef.rodzaj === "pierscien") {
      const U = typoPierscienUklad(g, b, ef, P, W, H), lit = U.gl.reduce((a, q) => a + q.px, 0) / Math.max(1, U.gl.length);
      const v = (U.R * ef.predkosc * Math.PI) / 180 / Math.max(1, lit), max = Math.floor((K.obroty * lit * 180) / Math.PI / U.R);
      if (v > K.obroty) dodaj("blad", "pierscien-szybko", b, b.start, `pierścień „${tekst(b)}” kręci się za szybko: przód jedzie ${v.toFixed(1)} wysokości liter na sekundę (najwyżej ${K.obroty}): prędkość do ${max}°/s albo większe litery`,
        `the ring "${tekst(b)}" spins too fast: the front moves ${v.toFixed(1)} letter heights per second (max ${K.obroty}): speed up to ${max}°/s or bigger letters`);
      const luk = ((2 * Math.PI) / 3) * U.R, dl = U.slowa.reduce((a, s) => (s.do - s.od > a.do - a.od ? s : a), U.slowa[0]);
      if (dl && dl.do - dl.od > luk) dodaj("blad", "pierscien-nieczytelny", b, tf, `w pierścieniu ${b.id} „${dl.tekst}” jest dłuższe niż przód koła (${Math.round(((dl.do - dl.od) / luk) * 100)}%): zawija się za głowę, nie da się go przeczytać: większe koło (szerokość), mniejsze litery (rozmiar) albo krótsze słowo`,
        `in ring ${b.id} "${dl.tekst}" is longer than the front of the ring (${Math.round(((dl.do - dl.od) / luk) * 100)}%): it wraps behind the head: a bigger ring (width), smaller letters (size) or a shorter word`);
    } else {
      const q = typoPrzejscieStan(b, ef, typoUklad(g, b, P, W, H).w, W, b.start), v = q.v * 1.5;   // szczyt płynnego ruchu
      if (v > K.przejscie) dodaj("blad", "przejscie-szybko", b, b.start, `„${tekst(b)}” przechodzi przez osobę za szybko (${v.toFixed(2)} szerokości kadru na sekundę, najwyżej ${K.przejscie}): dłuższy blok albo węższy napis`,
        `"${tekst(b)}" crosses the person too fast (${v.toFixed(2)} frame widths per second, max ${K.przejscie}): a longer block or narrower text`);
    }
    const nazwa = ef.rodzaj === "pierscien" ? ["pierścień", "the ring"] : ["przejście", "the crossing"];
    const sc = document.createElement("canvas"); sc.width = cw; sc.height = ch;
    const sg = sc.getContext("2d", { willReadFrequently: true });
    let ile = 0, zaslania = 0;
    const krok = Math.max(0.15, (b.end - b.start) / 8);
    for (let t = b.start + 0.1; t < b.end - 0.03 && opt.sylwetka && ile < 8; t += krok) {
      const obraz = await opt.sylwetka(t);
      if (!obraz) continue;
      sg.clearRect(0, 0, cw, ch); sg.drawImage(obraz, pad, pad, W, H);
      const tyl = rysuj(b, t, typoStan(b, P, t), P, "tyl");
      if (tyl.r) { ile++; zaslania = Math.max(zaslania, typoPokrycie(tyl.m, typoTusz(sg, cw, ch, 128))); }
    }
    if (!ile) dodaj("blad", "efekt-bez-sylwetek", b, tf, `${nazwa[0]} ${b.id} („${tekst(b)}”) nie ma sylwetek osoby (typografia.py sylwetki <film>): bez nich tył napisu idzie po twarzy`,
      `${nazwa[1]} ${b.id} ("${tekst(b)}") has no person silhouettes: without them the back of the text runs over the face`);
    else if (zaslania < K.dotyka) dodaj("uwaga", "efekt-obok-osoby", b, tf, `${nazwa[0]} ${b.id} („${tekst(b)}”) mija osobę: sylwetka nie zasłania tyłu napisu (ustaw środek na głowie albo ciele: typografia.py efekt)`,
      `${nazwa[1]} ${b.id} ("${tekst(b)}") misses the person: the silhouette covers no part of the back (centre it on the head or body)`);
  };

  // 2. Pełny blok: słowa się stykają, strefy interfejsu, małe słowa, efekt, napis za osobą.
  for (const b of bloki) {
    const tf = typoChwilaPelna(b, m), wy = b.wyjscie || m.wyjscie, ef = typoEfekt(b), pier = ef && ef.rodzaj === "pierscien";
    const n = pier ? 0 : b.slowa.length;                      // pierścień: odstępy liter wyznacza koło
    const pelny = { slowa: b.slowa.map(() => 1), e: 0, wy };
    const slowa = n > 1 ? b.slowa.map((_w, j) => rysuj(b, tf, { slowa: b.slowa.map((_x, i) => (i === j ? 1 : -1)), e: 0, wy })) : [];
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      if (!typoStyk(slowa[i].m, slowa[i].r, slowa[j].m, slowa[j].r, cw, ch, r)) continue;
      const sty = [i, j].map((q) => typoSlowo(b.slowa[q], m, b.uklad).styl);
      const plyta = sty.some((s) => s === "tlo" || s === "show");      // płytki i naklejki mogą się dotykać
      dodaj(plyta ? "uwaga" : "blad", "slowa-sie-stykaja", b, tf, `w ${b.id} „${b.slowa[i].tekst}” i „${b.slowa[j].tekst}” stykają się literami: rozsuń linie (linia słowa), zmniejsz słowo (skala) albo zmień układ`,
        `in ${b.id} "${b.slowa[i].tekst}" and "${b.slowa[j].tekst}" touch: split the lines, scale down or change the layout`);
    }
    const caly = rysuj(b, tf, pelny);
    if (caly.r && opt.strefy && opt.strefy.length) {
      const q = { x0: caly.r.x0 - pad, y0: caly.r.y0 - pad, x1: caly.r.x1 - pad, y1: caly.r.y1 - pad };
      const pod = opt.strefy.filter((s) => q.x0 < s.x1 && q.x1 > s.x0 && q.y0 < s.y1 && q.y1 > s.y0);
      if (pod.length) dodaj("uwaga", "strefa", b, tf, `„${tekst(b)}” wchodzi pod interfejs platformy (${pod.map((s) => s.nazwa[0]).join(", ")}): przesuń blok`,
        `"${tekst(b)}" sits under the platform interface (${pod.map((s) => s.nazwa[1]).join(", ")}): move it`);
    }
    const u = pier ? { slowa: typoPierscienUklad(g, b, ef, P, W, H).gl } : typoUklad(g, b, P, W, H);
    const mini = u.slowa.reduce((a, s) => (s.px < a.px ? s : a), u.slowa[0]);
    if (mini && px(mini.px) < K.maly) dodaj("uwaga", "male-slowo", b, tf, `„${mini.src.tekst}” w ${b.id} ma tylko ${px(mini.px)} px: na telefonie ledwo widać (powiększ blok albo słowo)`,
      `"${mini.src.tekst}" in ${b.id} is only ${px(mini.px)} px: hard to read on a phone`);
    if (ef) { await kontrolaEfektu(b, ef); continue; }
    if (b.warstwa !== "tyl" || !opt.sylwetka) continue;
    const sc = document.createElement("canvas"); sc.width = cw; sc.height = ch;
    const sg = sc.getContext("2d", { willReadFrequently: true });
    let widac = 1, zaslania = 0, ile = 0, tMin = tf;
    for (let t = tf; t <= Math.max(tf, b.end - (TYPO_WYJSCIA[wy] ?? 0) - 0.03) && ile < 8; t += 0.2) {
      const obraz = await opt.sylwetka(t);
      if (!obraz) continue;
      sg.clearRect(0, 0, cw, ch); sg.drawImage(obraz, pad, pad, W, H);
      const pok = typoPokrycie(rysuj(b, t, pelny).m, typoTusz(sg, cw, ch, 128));
      ile++; zaslania = Math.max(zaslania, pok);
      if (1 - pok < widac) { widac = 1 - pok; tMin = t; }
    }
    if (!ile) dodaj("uwaga", "brak-sylwetek", b, tf, `${b.id} stoi za osobą, ale nie ma sylwetek (typografia.py sylwetki <film>): w eksporcie napis będzie w całości przed osobą`,
      `${b.id} is behind the person but has no silhouettes: it will render fully in front`);
    else if (widac < K.widac) dodaj("blad", "za-osoba-nieczytelne", b, tMin, `„${tekst(b)}” za osobą: widać tylko ${Math.round(widac * 100)}% liter (min. ${Math.round(K.widac * 100)}%): przesuń wyżej (y), zmniejsz albo daj przed osobę`,
      `"${tekst(b)}" behind the person: only ${Math.round(widac * 100)}% visible: move it up, shrink it or put it in front`);
    else if (zaslania < K.dotyka) dodaj("uwaga", "za-osoba-niewidoczne", b, tf, `„${tekst(b)}” stoi za osobą, ale osoba go nie zasłania: efektu nie widać (przesuń niżej, żeby głowa zakryła dół liter)`,
      `"${tekst(b)}" is behind the person but nothing covers it: move it down so the head covers the bottom`);
  }
  out.sort((a, b) => a.t - b.t || (a.poziom === b.poziom ? 0 : a.poziom === "blad" ? -1 : 1));
  return { bloki: bloki.length, problemy: out };
}
