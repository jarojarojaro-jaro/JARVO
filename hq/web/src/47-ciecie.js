// ------------------------------------------------------------------ edytor: szybkie cięcie
// Bez Reacta i bez DOM (testy w node: tests/test_edytor_ciecie.py). Te same reguły u Wideografa: projekt.py tnij
// (podział) i wytnij (odcinek osi). Przejście (transition) zostaje zawsze na ostatniej części, czyli na tym samym cięciu.

// Klip c podzielony na n równych części (np. 7,5 s → 3 × 2,5 s); pierwsza część zostawia id klipu.
function podzielKlip(c, n, noweId) {
  const d = (c.out - c.in) / n;
  return Array.from({ length: n }, (_, k) => ({ ...c, id: k ? noweId() : c.id, in: k ? +(c.in + k * d).toFixed(4) : c.in,
    out: k === n - 1 ? c.out : +(c.in + (k + 1) * d).toFixed(4), transition: k === n - 1 ? c.transition : undefined }));
}

// Usuń z lewej ("l": od początku klipu do wskaźnika, chwili osi t) albo z prawej ("r": od t do końca klipu).
// s = odcinek osi klipu z layoutClips ({c, start, end}); null, gdy t nie leży w klipie z zapasem min.
function przytnijKlip(s, t, side, min = 0.1) {
  if (!s || t <= s.start + min / 2 || t >= s.end - min / 2) return null;
  const cut = +(s.c.in + (t - s.start) * (s.c.speed || 1)).toFixed(4);
  return side === "l" ? { ...s.c, in: cut } : { ...s.c, out: cut };
}
