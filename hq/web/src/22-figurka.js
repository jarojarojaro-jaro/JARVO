// Znak agenta w aplikacji (motyw TARS, docs/HQ.md §5a): monolit z czterech pionowych segmentów, każdy agent w swojej
// pozie i w swoim odcieniu (--j-barwa-N tylko na dwóch segmentach), jeden segment z „ekranem danych”. Zastępuje pikselowe
// figurki pokoi w liście, wątku, kompozytorze, kartach i Ustawieniach; pikselowe figurki zostają w Starej Bazie (wieża).
// Poza i odcień z nazwy, roli albo pokoju agenta (`hq_room` z fleet.yaml), więc znak jest ten sam w każdym miejscu.

// [góra, wysokość] czterech segmentów w polu 19×20
const POZY_ZNAKU = {
  stoi:    [[2, 16], [2, 16], [2, 16], [2, 16]],     // szef floty
  schody:  [[11, 7], [8, 10], [5, 13], [2, 16]],     // przepustowość (silnik, GPU)
  brama:   [[6, 12], [2, 16], [2, 16], [6, 12]],     // buduje (strony, aplikacje)
  sciezki: [[2, 11], [7, 11], [2, 11], [7, 11]],     // dwie ścieżki (głos i napisy, obraz i dźwięk)
  kursor:  [[2, 16], [12, 6], [12, 6], [2, 16]],     // terminal
  szczyt:  [[8, 10], [2, 16], [8, 10], [12, 6]],     // szuka (leady, śledztwo)
  fala:    [[6, 12], [10, 8], [4, 14], [8, 10]],     // reklama, kampanie
};
const EKRAN_ZNAKU = { stoi: 1, schody: 3, brama: 2, sciezki: 0, kursor: 3, szczyt: 1, fala: 2 };
const POZY_KOLEJNO = ["fala", "szczyt", "brama", "sciezki", "schody", "kursor"];
// słowo w nazwie, roli albo pokoju → [poza, odcień]; kolejność ma znaczenie (pierwsze trafienie)
const ZNAKI_AGENTOW = [
  [/^(jarvo|bridge)$|orchestrator/, "stoi", 0], [/kernel|gpu|inferenc/, "schody", 1], [/dev|web|devlab|apps|mobile|aplikac/, "brama", 2],
  [/transl|napis|dubb|wideo|film|studio|atelier/, "sciezki", 3], [/operator|terminal|control|omp/, "kursor", 4],
  [/lowca|łowca|lead|radar|sherlock|study|detekt/, "szczyt", 5], [/ads|reklam|office|kampan/, "fala", 6],
];

function znakAgenta(a) {
  const n = String((a && a.name) || "").toLowerCase();
  const slowa = [n, String((a && a.nazwa) || "").toLowerCase(), String((a && a.rodzaj) || ""), String((a && a.pokoj) || "")];
  for (const [wz, poza, barwa] of ZNAKI_AGENTOW) if (slowa.some((s) => wz.test(s))) return { poza, barwa };
  const suma = [...n].reduce((s, c) => (s * 31 + c.charCodeAt(0)) >>> 0, 7);
  return { poza: POZY_KOLEJNO[suma % POZY_KOLEJNO.length], barwa: a && a.barwa != null ? a.barwa % 10 : suma % 10 };
}

// gotowy rysunek na pozę (elementy React są niezmienne, więc jeden obiekt służy wszystkim znakom)
const RYSUNKI_ZNAKU = new Map();
function rysunekZnaku(poza) {
  let r = RYSUNKI_ZNAKU.get(poza);
  if (!r) {
    r = [];
    POZY_ZNAKU[poza].forEach(([y, h], i) => {
      const x = i * 5;
      r.push(html`<rect key=${i} class=${i % 2 ? "j-zn-b" : "j-zn-a"} x=${x} y=${y} width="4" height=${h}/>`);
      if (EKRAN_ZNAKU[poza] === i) r.push(html`<rect key="e" class="j-zn-o" x=${x + 1} y=${y + 2} width="2" height="2"/>`);
    });
    RYSUNKI_ZNAKU.set(poza, r);
  }
  return r;
}
