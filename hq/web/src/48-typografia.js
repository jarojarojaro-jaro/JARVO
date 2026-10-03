// Typografia jak z montażu: słowo po słowie, różne wielkości, kroje, kolory, głębia, skos i perspektywa 3D.
// Jeden renderer na kanwie (czysty JS, bez zależności), jak 44-napisy.js: podgląd edytora HQ, eksport z edytora
// i render Wideografa (projekt.py w przeglądarce bez okna). Plan bloków układa typografia.py (reżyser), a człowiek
// poprawia go w edytorze. Czas słowa liczony od początku bloku: przesunięcie bloku zabiera słowa ze sobą.
//
// projekt.typo = {motyw, akcent, bloki: [{id, start, end, uklad, x, y, w, rot, tilt, warstwa, wejscie, wyjscie,
//                 rozmiar, slowa: [{t, k, tekst, waga 0–3, linia, glebia −1|0|1, kolor, kroj, styl}]}]}

const TYPO_KROJE = {   // klucz → [rodzina CSS, grubość, kursywa, nazwa]; pliki w fonts/kroje (OFL)
  bricolage: ["'Bricolage Grotesque', system-ui, sans-serif", 800, false, "Bricolage"],
  bricolageL: ["'Bricolage Grotesque', system-ui, sans-serif", 500, false, "Bricolage lekki"],
  anton: ["'Anton', Impact, sans-serif", 400, false, "Anton"],
  bebas: ["'Bebas Neue', Impact, sans-serif", 400, false, "Bebas"],
  barlow: ["'Barlow Condensed', 'Arial Narrow', sans-serif", 800, false, "Barlow"],
  barlowI: ["'Barlow Condensed', 'Arial Narrow', sans-serif", 800, true, "Barlow kursywa"],
  barlowL: ["'Barlow Condensed', 'Arial Narrow', sans-serif", 600, false, "Barlow lekki"],
  oswald: ["'Oswald', 'Arial Narrow', sans-serif", 700, false, "Oswald"],
  playfair: ["'Playfair Display', Georgia, serif", 800, false, "Playfair"],
  playfairI: ["'Playfair Display', Georgia, serif", 500, true, "Playfair kursywa"],
  caveat: ["'Caveat', cursive", 700, false, "Odręczny"],
  grunge: ["'Rubik Dirt', Impact, sans-serif", 400, false, "Grunge"],
  mono: ["'JetBrains Mono', ui-monospace, monospace", 700, false, "Mono"],
};
// Motyw = zestaw decyzji: kroje (główny, mały do słów funkcyjnych, drugi do słów „z tyłu”), kolory, wejście/wyjście,
// styl najmocniejszego słowa, tekstura, skala skosu (stopnie; reżyser typografia.py ma tę samą tabelę SKOS).
// Kolor marki nadpisuje akcent (projekt.typo.akcent).
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
};
const TYPO_UKLADY = ["kolumna", "schodki", "srodek", "skos", "3d", "za", "rozrzut"];
const TYPO_WEJSCIA = { ciecie: 0, pop: 0.14, kontur: 0.24, maska: 0.18, pisanie: 0.3, zjazd: 0.16 };
const TYPO_WYJSCIA = { ciecie: 0, zanik: 0.16, smuga: 0.14 };
const TYPO_STYLE = ["wypelnij", "kontur", "3d", "blask", "tlo"];
const TYPO_WAGA = [0.58, 1, 1.45, 2.1];            // mnożnik rozmiaru: słowo funkcyjne, zwykłe, ważne, uderzenie
const TYPO_CEL = [0.62, 0.62, 0.8, 1];             // część szerokości bloku (w), którą wypełnia blok, wg najmocniejszego słowa
const TYPO_LEAD = 0.03;                            // słowo pojawia się tuż przed dźwiękiem (oko wyprzedza ucho)
const TYPO_SCHODKI = [0, 1, 0.3, 0.85, 0.15];      // wyrównanie kolejnych linii w układzie „schodki”

function typoMotyw(P) {
  const t = (P && P.typo) || {};
  const m = TYPO_MOTYWY[t.motyw] || TYPO_MOTYWY.czysty;
  return t.akcent ? { ...m, akcent: t.akcent } : m;
}
function typoBloki(P) { return ((P && P.typo && P.typo.bloki) || []).filter((b) => b && Array.isArray(b.slowa) && b.slowa.length); }
function typoAktywne(P, now) { return typoBloki(P).filter((b) => now >= b.start + Math.max(0, +(b.slowa[0].t) || 0) - TYPO_LEAD && now < b.end); }
function typoKroj(key) { return TYPO_KROJE[key] || TYPO_KROJE.bricolage; }
function typoFont(key, px) { const k = typoKroj(key); return `${k[2] ? "italic " : ""}${k[1]} ${Math.max(4, px).toFixed(1)}px ${k[0]}`; }
function typoClamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
function typoEaseOut(a) { return 1 - Math.pow(1 - typoClamp(a, 0, 1), 3); }
function typoEaseBack(a) { const c = 1.9, x = typoClamp(a, 0, 1) - 1; return 1 + (c + 1) * x * x * x + c * x * x; }
function typoHash(s) { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; }

// Wygląd słowa po motywie i nadpisaniach: krój, kolor, styl, wielkie litery.
function typoSlowo(w, m, uklad) {
  const waga = typoClamp(Math.round(+w.waga || 0), 0, 3);
  const glebia = typoClamp(Math.round(+w.glebia || 0), -1, 1);
  const kroj = w.kroj && TYPO_KROJE[w.kroj] ? w.kroj : waga === 0 ? m.maly : glebia < 0 ? m.drugi : m.kroj;
  const kolor = w.kolor || (waga === 3 ? m.akcent : m.kolor);   // akcent tylko na uderzeniu: kolor ma znaczyć, nie zdobić
  const styl = TYPO_STYLE.includes(w.styl) ? w.styl : waga === 3 && uklad !== "za" ? m.hit : "wypelnij";
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
  const miara = (row) => {
    for (const s of row) { ctx.font = typoFont(s.kroj, s.px); s.w = ctx.measureText(s.tekst).width; }
    const gap = Math.min(...row.map((s) => s.px)) * 0.26;
    return { gap, lw: row.reduce((a, s) => a + s.w, 0) + gap * (row.length - 1), lh: Math.max(...row.map((s) => s.px)) * m.lh };
  };
  const nat = rows.map(miara);
  const natW = Math.max(1, ...nat.map((r) => r.lw)), natH = Math.max(1, nat.reduce((a, r) => a + r.lh, 0));
  const cel = maxW * (b.uklad === "za" ? 1 : TYPO_CEL[Math.max(...rows.flat().map((s) => s.waga))]);
  const k = typoClamp(Math.min(cel / natW, ((H > W ? 0.3 : 0.5) * H) / natH), 0.4, 3.4) * (+b.rozmiar || 1);
  const limit = Math.min(maxW * Math.max(1, +b.rozmiar || 1), W * 0.96);
  const out = [];
  let y = 0, width = 0;
  rows.forEach((row) => {
    for (const s of row) s.px *= k;
    let { gap, lw } = miara(row);
    const fit = lw > limit ? limit / lw : 1;         // za długa linia: cała linia mniejsza, nie poza kadr
    if (fit < 1) { for (const s of row) { s.px *= fit; s.w *= fit; } lw *= fit; gap *= fit; }
    const lh = Math.max(...row.map((s) => s.px)) * m.lh;
    row.lh = lh; row.lw = lw; row.gap = gap; row.y = y + lh * 0.8;
    y += lh; width = Math.max(width, lw);
  });
  rows.forEach((row, r) => {
    const f = b.uklad === "kolumna" || b.uklad === "3d" ? 0 : b.uklad === "schodki" ? TYPO_SCHODKI[r % TYPO_SCHODKI.length]
      : b.uklad === "rozrzut" ? typoHash(`${b.id}:${r}`) : 0.5;
    let x = (width - row.lw) * f - width / 2;
    for (const s of row) {
      out.push({ ...s, x, y: row.y - y / 2, h: s.px });
      x += s.w + row.gap;
    }
  });
  return { slowa: out.sort((a, c) => a.i - c.i), w: width, h: y, cx: (+b.x || 0.5) * W, cy: (+b.y || 0.3) * H, S };
}

// Ramka bloku na kanwie (do trafiania myszą i strzałek w edytorze); bez obrotu i perspektywy.
function typoRamka(ctx, b, P, W, H) {
  const u = typoUklad(ctx, b, P, W, H);
  const pad = 12 * u.S;
  return { x0: u.cx - u.w / 2 - pad, y0: u.cy - u.h / 2 - pad, x1: u.cx + u.w / 2 + pad, y1: u.cy + u.h / 2 + pad, u };
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
    if (warstwa && (b.warstwa === "tyl" ? "tyl" : "przod") !== warstwa) continue;
    const s = typoStan(b, P, now);
    parts.push(`${b.id}:${s.slowa.map((a) => (a < 0 ? "-" : a >= 1 ? "F" : Math.round(a * 1000))).join(",")}:${Math.round(s.e * 1000)}`);
  }
  return parts.join("|");
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
function typoCiemniej(hex, k) {
  const h = String(hex || "#ffffff").replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((x) => x + x).join("") : h.slice(0, 6), 16) || 0xffffff;
  const r = (n >> 16) & 255, g = (n >> 8) & 255, bb = n & 255;
  return `rgb(${Math.round(r * k)},${Math.round(g * k)},${Math.round(bb * k)})`;
}

// Jedno słowo na kanwie bloku (współrzędne bloku), z wejściem a (0–1).
function typoRysujSlowo(g, s, a, wejscie, m) {
  const px = s.px;
  let tekst = s.tekst;
  if (wejscie === "pisanie" && a < 1) tekst = Array.from(tekst).slice(0, Math.max(1, Math.ceil(Array.from(tekst).length * a))).join("");
  g.save();
  g.font = typoFont(s.kroj, px);
  g.textBaseline = "alphabetic";
  let x = s.x, y = s.y, alpha = s.glebia < 0 ? 0.8 : 1;
  if (wejscie === "pop" && a < 1) {
    const k = 1 + 0.38 * (1 - typoEaseBack(a));
    g.translate(x + s.w / 2, y - px * 0.35); g.scale(k, k); g.translate(-(x + s.w / 2), -(y - px * 0.35));
    alpha *= typoClamp(a * 3, 0, 1);
  } else if (wejscie === "zjazd" && a < 1) {
    x += (1 - typoEaseOut(a)) * px * 0.5; alpha *= a;
  } else if (wejscie === "maska" && a < 1) {
    g.beginPath(); g.rect(x - px, y - px * 1.05, s.w + px * 2, px * 1.3); g.clip();
    y += (1 - typoEaseOut(a)) * px * 1.1;
  }
  g.globalAlpha = alpha;
  if (s.glebia < 0) g.filter = `blur(${Math.min(2.5, px * 0.012).toFixed(1)}px)`;   // dalej = lekko miękko, ale czytelnie
  const fill = s.kolor;
  const konturFaza = wejscie === "kontur" && a < 1;
  const cien = () => { g.shadowColor = "rgba(0,0,0,0.55)"; g.shadowBlur = px * 0.16; g.shadowOffsetY = px * 0.04; };
  const bezCienia = () => { g.shadowColor = "transparent"; g.shadowBlur = 0; g.shadowOffsetY = 0; };
  if (s.styl === "tlo") {
    g.fillStyle = m.akcent;
    g.fillRect(x - px * 0.12, y - px * 0.82, s.w + px * 0.24, px * 1.02);
  }
  if (s.styl === "3d" && !konturFaza) {          // wyciągnięcie w głąb: kopie w ciemniejszym kolorze, potem lico
    const n = Math.max(3, Math.round(px * 0.09));
    g.fillStyle = typoCiemniej(fill, 0.32);
    for (let i = n; i >= 1; i--) g.fillText(tekst, x + i * 0.75, y + i);
  }
  if (s.styl === "kontur" || konturFaza) {
    g.lineJoin = "round"; g.lineWidth = Math.max(1.5, px * 0.045); g.strokeStyle = fill;
    cien(); g.strokeText(tekst, x, y); bezCienia();
  }
  if (s.styl !== "kontur") {
    const fa = konturFaza ? typoClamp((a - 0.45) / 0.55, 0, 1) : 1;
    if (fa > 0) {
      g.globalAlpha = alpha * fa;
      g.fillStyle = s.styl === "tlo" ? "#111111" : fill;
      if (s.styl === "blask") { g.shadowColor = fill; g.shadowBlur = px * 0.38; g.fillText(tekst, x, y); }
      if (s.styl !== "3d" && s.styl !== "tlo" && s.styl !== "blask") cien();
      g.fillText(tekst, x, y);
      bezCienia();
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
function typoRysujBlok(ctx, b, P, W, H, now) {
  const m = typoMotyw(P);
  const st = typoStan(b, P, now);
  if (!st.slowa.some((a) => a >= 0)) return null;
  const u = typoUklad(ctx, b, P, W, H);
  const pad = Math.ceil(Math.max(...u.slowa.map((s) => s.px)) * 0.5);
  const bw = Math.ceil(u.w + pad * 2), bh = Math.ceil(u.h + pad * 2);
  const c = document.createElement("canvas");
  c.width = Math.max(1, bw); c.height = Math.max(1, bh);
  const g = c.getContext("2d");
  g.translate(bw / 2, bh / 2);
  u.slowa.forEach((s, j) => { if (st.slowa[j] >= 0) typoRysujSlowo(g, s, st.slowa[j], typoWejscie(b, s.src, m), m); });
  ctx.save();
  ctx.translate(u.cx, u.cy);
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

// Wszystkie aktywne bloki (opcjonalnie tylko jedna warstwa: "przod" albo "tyl" = za osobą).
function typoRysuj(ctx, P, W, H, now, warstwa) {
  const out = [];
  for (const b of typoAktywne(P, now)) {
    if (warstwa && (b.warstwa === "tyl" ? "tyl" : "przod") !== warstwa) continue;
    const u = typoRysujBlok(ctx, b, P, W, H, now);
    if (u) out.push([b, u]);
  }
  return out;
}
// Teksty bloków do wczytania krojów (krój + tekst: polskie znaki z podzbioru latin-ext).
function typoFonty(P, W, H) {
  const m = typoMotyw(P);
  const out = new Map();
  for (const b of typoBloki(P)) for (const w of b.slowa) {
    const s = typoSlowo(w, m, b.uklad);
    const f = typoFont(s.kroj, 64);
    out.set(f, (out.get(f) || "") + s.tekst);
  }
  return [...out.entries()];
}
