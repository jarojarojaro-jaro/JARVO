// ------------------------------------------------------------------ edytor: dźwięk (zanik i pasy audio)
// Bez Reacta i bez DOM (testy w node: tests/test_edytor_dzwiek.py). Narastanie (fadeIn) i wyciszanie (fadeOut) w sekundach
// liniowo, jak afade curve=tri w eksporcie (edytor.py build_command): ta sama głośność w podglądzie i w filmie.

const ZANIK_MAX = 10;              // najdłuższe narastanie albo wyciszanie (s); i tak najwyżej połowa elementu
const zanikMax = (d) => Math.max(0, Math.min(ZANIK_MAX, d / 2));

// Mnożnik głośności w chwili rel (s od początku elementu o długości d). Przed początkiem i po końcu (zapas przejścia)
// zanik daje ciszę, bez zaniku pełną głośność, jak afade w eksporcie.
function zanikGain(rel, d, fi, fo) {
  fi = Math.min(+fi || 0, zanikMax(d)); fo = Math.min(+fo || 0, zanikMax(d));
  let g = 1;
  if (fi > 0) g = Math.min(g, Math.max(0, Math.min(1, rel / fi)));
  if (fo > 0) g = Math.min(g, Math.max(0, Math.min(1, (d - rel) / fo)));
  return g;
}

// Pasy audio na osi (jak w CapCut): element trafia na pierwszy pas, na którym nie nachodzi na inny; muzyka, lektor
// i efekty grające naraz leżą jeden pod drugim. Tylko widok: w projekcie audio to dalej jedna lista (eksport miesza całość).
function pasyAudio(items) {
  const konce = [], pas = {};
  for (const m of [...items].sort((a, b) => a.start - b.start || String(a.id).localeCompare(String(b.id)))) {
    const end = m.start + (m.out - m.in);
    let k = konce.findIndex((e) => e <= m.start + 1e-6);
    if (k < 0) { k = konce.length; konce.push(end); } else konce[k] = end;
    pas[m.id] = k;
  }
  return { pas, n: Math.max(1, konce.length) };
}
