// ------------------------------------------------------------------ edytor: przejścia między klipami
// Bez Reacta i bez DOM (testy w node: tests/test_edytor_przejscia.py). Przejście leży na środku cięcia i nie skraca
// filmu: od T − d/2 do T + d/2 klip A gra dalej (materiał za przycięciem, a gdy go brak, stoi ostatnia klatka),
// a klip B zaczyna wcześniej (materiał przed przycięciem albo pierwsza klatka). Napisy i muzyka zostają na miejscu.
// Eksport: xfade i acrossfade z FFmpeg na wydłużonych odcinkach (edytor.py build_command). Podgląd: dwie warstwy
// stylowane przez przejscieStyl tymi samymi wzorami co xfade (q = 1 − progress), więc film wygląda jak podgląd.
// „Rozmycie” jest nasze: przenikanie i rozmycie Gaussa rosnące do cięcia na A, malejące od cięcia na B.
const ED_PRZEJSCIA = [
  ["fade", "Przenikanie", "Dissolve"], ["fadeblack", "Przez czerń", "Dip to black"], ["fadewhite", "Przez biel", "Dip to white"],
  ["blur", "Rozmycie", "Blur"], ["zoomin", "Przybliżenie", "Zoom in"], ["pixelize", "Piksele", "Pixelate"],
  ["slideleft", "Przesuń w lewo", "Push left"], ["slideright", "Przesuń w prawo", "Push right"],
  ["slideup", "Przesuń w górę", "Push up"], ["slidedown", "Przesuń w dół", "Push down"],
  ["coverleft", "Najazd z prawej", "Slide in, right"], ["coverright", "Najazd z lewej", "Slide in, left"],
  ["wipeleft", "Zasłona w lewo", "Wipe left"], ["wiperight", "Zasłona w prawo", "Wipe right"],
  ["smoothleft", "Miękka zasłona", "Soft wipe"], ["circleopen", "Koło", "Circle"],
];
const ED_PRZ_D = 0.5;              // domyślna długość przejścia (s)
const ED_PRZ_ROZMYCIE = 40;        // σ rozmycia przy cięciu = krótszy bok kadru / 40 (edytor.ROZMYCIE_PRZEJSCIA)
const przSmooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const przDur = (c) => (c.out - c.in) / (c.speed || 1);

// Przejście po każdym klipie ({type, d} albo null = zwykłe cięcie): parzysta liczba klatek (połowa przed cięciem,
// połowa za nim), najwyżej tyle, ile trwa krótszy z sąsiednich klipów. Ta sama reguła: edytor.przejscia_osi.
function przejsciaOsi(clips, fps) {
  const F = fps || 30;
  return clips.map((c, i) => {
    const tr = c.transition, n = clips[i + 1];
    if (!n || !tr || !ED_PRZEJSCIA.some(([k]) => k === tr.type)) return null;
    const d = Math.min(3, Math.max(0.1, Number.isFinite(+tr.dur) && tr.dur !== null && tr.dur !== "" ? +tr.dur : ED_PRZ_D));
    const cap = 2 * Math.floor(Math.min(przDur(c), przDur(n)) * F / 2 + 1e-6);
    const k = Math.min(2 * Math.floor(d * F / 2 + 0.5), cap);
    return k >= 2 ? { type: tr.type, d: k / F } : null;
  });
}

// Okno przejścia pod czasem t: {i (klip A), q 0–1, type, d, T (cięcie)} albo null. segs = layoutClips(clips).
function przejscieW(segs, trs, t) {
  for (let i = 0; i < trs.length; i++) {
    const tr = trs[i];
    if (!tr || !segs[i + 1]) continue;
    const T = segs[i].end, a = T - tr.d / 2;
    if (t >= a - 1e-9 && t < a + tr.d - 1e-9) return { i, q: (t - a) / tr.d, type: tr.type, d: tr.d, T };
  }
  return null;
}

// Wygląd obu warstw w chwili q (0 = sam A, 1 = sam B) jako liczby: op (krycie), dx/dy (przesunięcie w ułamkach kadru),
// sc (powiększenie wokół środka), clip [góra, prawo, dół, lewo] (ułamki), mask {lin|rad: krycie w 11 punktach 0..1},
// blur (ułamek pełnego rozmycia); tlo = kolor pod warstwami, piksel = bok piksela w ułamkach krótszego boku (0 = brak).
// B leży nad A. Wzory: xfade w FFmpeg, mix(a, b, p) = a·p + b·(1 − p), progress p = 1 − q.
function przejscieStyl(type, q) {
  q = Math.min(1, Math.max(0, q));
  const p = 1 - q, a = {}, b = {}, out = { a, b, tlo: "#000", piksel: 0 };
  const pkt = (f) => Array.from({ length: 11 }, (_, k) => +f(k / 10).toFixed(4));
  switch (type) {
    case "fadeblack": case "fadewhite": {
      // A' = A gaśnie do tła w pierwszych 20%, B' = B wyłania się z tła; wynik A'·p + B'·q
      const cA = przSmooth(0.8, 1, p) * p, cB = (1 - przSmooth(0.2, 1, p)) * q;
      b.op = cB; a.op = cB < 1 ? cA / (1 - cB) : 0;
      if (type === "fadewhite") out.tlo = "#fff";
      break;
    }
    case "blur": b.op = q; a.blur = q; b.blur = p; break;
    case "zoomin": {
      const zf = przSmooth(0.5, 1, p);
      a.sc = 1 / Math.max(zf, 0.02); b.op = 1 - przSmooth(0, 0.5, p);
      break;
    }
    case "pixelize": {
      const dist = Math.ceil(Math.min(p, q) * 50) / 50;
      b.op = q; out.piksel = (2 * dist) / 20;
      break;
    }
    case "slideleft": a.dx = -q; b.dx = p; break;
    case "slideright": a.dx = q; b.dx = -p; break;
    case "slideup": a.dy = -q; b.dy = p; break;
    case "slidedown": a.dy = q; b.dy = -p; break;
    case "coverleft": b.dx = p; break;
    case "coverright": b.dx = -p; break;
    case "wipeleft": b.clip = [0, 0, 0, p]; break;
    case "wiperight": b.clip = [0, p, 0, 0]; break;
    case "smoothleft": b.mask = { lin: pkt((u) => przSmooth(0, 1, u + 2 * q - 1)) }; break;
    case "circleopen": b.mask = { rad: pkt((r) => 1 - przSmooth(0, 1, r + 1.5 - 3 * q)) }; break;
    default: b.op = q;                                   // fade: przenikanie
  }
  return out;
}

// Liczby z przejscieStyl → style CSS warstwy (px = pełne rozmycie w pikselach ekranu). Pusty obiekt = warstwa bez zmian.
function przejscieCss(o, px) {
  const pr = (x) => `${+(x * 100).toFixed(3)}%`;
  const tr = [];
  if (o.dx || o.dy) tr.push(`translate(${pr(o.dx || 0)}, ${pr(o.dy || 0)})`);
  if (o.sc && o.sc !== 1) tr.push(`scale(${+o.sc.toFixed(4)})`);
  const stopy = (v) => v.map((x, k) => `rgba(0,0,0,${x}) ${k * 10}%`).join(", ");
  const mask = o.mask ? (o.mask.lin ? `linear-gradient(to right, ${stopy(o.mask.lin)})`
    : `radial-gradient(circle farthest-corner at 50% 50%, ${stopy(o.mask.rad)})`) : "";
  return {
    opacity: o.op === undefined ? "" : String(+o.op.toFixed(4)),
    transform: tr.join(" "),
    clipPath: o.clip ? `inset(${o.clip.map(pr).join(" ")})` : "",
    maskImage: mask, webkitMaskImage: mask,
    filter: o.blur ? `blur(${+(o.blur * px).toFixed(2)}px)` : "",
  };
}
