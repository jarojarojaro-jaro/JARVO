// ------------------------------------------------------------------ edytor: korekcja koloru klipu
// Ten sam przepis co edytor.kolor_tabele w Pythonie (testy w node: tests/test_edytor_kolor.py): krzywa każdego kanału
// w pięciu punktach (0, ¼, ½, ¾, 1) i macierz nasycenia. Podgląd: filtr SVG (feComponentTransfer „table” +
// feColorMatrix, przestrzeń sRGB) na warstwie klipu; eksport: lutrgb + colorchannelmixer z tych samych liczb, więc
// kolor w podglądzie i w gotowym filmie jest ten sam. Style za browser-use/video-use (grade.py) i filtrami CapCut.
const ED_KOLOR_STYLE = {
  naturalny: { contrast: 8, saturation: 6, krzywa: 0.5 },
  cieply: { contrast: 10, saturation: -6, temperature: 30, krzywa: 0.6 },
  chlodny: { contrast: 6, saturation: -4, temperature: -28 },
  kinowy: { contrast: 14, saturation: -16, temperature: 10, krzywa: 1.0 },
  zywy: { contrast: 10, saturation: 30 },
  czb: { contrast: 18, saturation: -100, krzywa: 0.6 },
  wyblakly: { contrast: -18, saturation: -24, lift: 0.07 },
};
const ED_KOLOR_NAZWY = [["naturalny", "Naturalny", "Natural"], ["cieply", "Ciepły", "Warm"], ["chlodny", "Chłodny", "Cool"],
  ["kinowy", "Kinowy", "Cinematic"], ["zywy", "Żywy", "Vivid"], ["czb", "Czarno-biały", "Black & white"], ["wyblakly", "Wyblakły", "Faded"]];
const ED_KOLOR_SUWAKI = [["brightness", "Jasność", "Brightness"], ["contrast", "Kontrast", "Contrast"],
  ["saturation", "Nasycenie", "Saturation"], ["temperature", "Temperatura", "Temperature"]];
const ED_KOLOR_X = [0, 0.25, 0.5, 0.75, 1];
const ED_KOLOR_S = [0, -0.04, 0, 0.04, 0];          // krzywa S: cienie w dół, światła w górę
const kolorR4 = (v) => Math.floor(v * 10000 + 0.5) / 10000;

// styl ze słownika i suwaki całkowite −100…100 (zera odpadają); null = bez korekty (edytor.kolor_norm)
function kolorNorm(raw) {
  if (!raw || typeof raw !== "object") return null;
  const out = Object.prototype.hasOwnProperty.call(ED_KOLOR_STYLE, raw.look) ? { look: raw.look } : {};
  for (const [k] of ED_KOLOR_SUWAKI) {
    const x = raw[k], n = Number.isFinite(+x) && x !== null && x !== "" ? +x : 0;
    const v = Math.floor(Math.min(100, Math.max(-100, n)) + 0.5);
    if (v) out[k] = v;
  }
  return Object.keys(out).length ? out : null;
}
// suwaki, które ustawia wybór stylu (edytor.kolor_domyslne)
function kolorDomyslne(look) {
  const st = ED_KOLOR_STYLE[look] || {};
  return Object.fromEntries(ED_KOLOR_SUWAKI.filter(([k]) => st[k] !== undefined).map(([k]) => [k, st[k]]));
}
// krzywe R, G, B (5 punktów 0…1) i nasycenie s; ta sama kolejność działań co edytor.kolor_tabele
function kolorTabele(raw) {
  const k = kolorNorm(raw);
  if (!k) return null;
  const st = ED_KOLOR_STYLE[k.look] || {};
  const a = st.krzywa || 0, lift = st.lift || 0;
  const kon = 1 + (k.contrast || 0) / 100 * 0.35;
  const jas = (k.brightness || 0) / 100 * 0.2;
  const t = (k.temperature || 0) / 100;
  const zysk = { r: 1 + 0.10 * t, g: 1 + 0.02 * t, b: 1 - 0.12 * t };
  const sn = (k.saturation || 0) / 100;
  const tab = {};
  for (const ch of ["r", "g", "b"]) {
    tab[ch] = ED_KOLOR_X.map((x, i) => {
      let y = lift + (1 - lift) * (x + a * ED_KOLOR_S[i]);
      y = (y - 0.5) * kon + 0.5 + jas;
      return kolorR4(Math.min(1, Math.max(0, y * zysk[ch])));
    });
  }
  return { ...tab, s: kolorR4(sn < 0 ? 1 + sn : 1 + 0.8 * sn) };
}
// macierz nasycenia z Filter Effects (jak CSS saturate): wiersze R, G, B
const kolorMacierz = (s) => [[0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s],
  [0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s], [0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s]];

// CSS `filter` warstwy klipu: url(#…) do filtra SVG z tym przepisem ("" = bez korekty). Jeden filtr na każde
// inne ustawienie, w ukrytym <svg> strony; podgląd, miniatura stylu i kanwa (ctx.filter) biorą ten sam.
const kolorFiltry = new Map();
function kolorFiltr(c) {
  const t = kolorTabele(c && c.color);
  if (!t || typeof document === "undefined") return "";
  const klucz = JSON.stringify(t);
  let id = kolorFiltry.get(klucz);
  if (id) return `url(#${id})`;
  const NS = "http://www.w3.org/2000/svg";
  let svg = document.getElementById("thq-kolor-defs");
  if (!svg) {
    svg = document.createElementNS(NS, "svg");
    svg.id = "thq-kolor-defs";
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("style", "position:absolute;width:0;height:0;overflow:hidden");
    document.body.appendChild(svg);
  }
  id = `thq-kolor-${kolorFiltry.size + 1}`;
  const f = document.createElementNS(NS, "filter");
  f.id = id;
  f.setAttribute("color-interpolation-filters", "sRGB");
  const ct = document.createElementNS(NS, "feComponentTransfer");
  for (const ch of ["r", "g", "b"]) {
    const fn = document.createElementNS(NS, `feFunc${ch.toUpperCase()}`);
    fn.setAttribute("type", "table");
    fn.setAttribute("tableValues", t[ch].join(" "));
    ct.appendChild(fn);
  }
  f.appendChild(ct);
  if (Math.abs(t.s - 1) > 1e-6) {
    const m = kolorMacierz(t.s);
    const cm = document.createElementNS(NS, "feColorMatrix");
    cm.setAttribute("type", "matrix");
    cm.setAttribute("values", [...m.map((w) => [...w.map((v) => v.toFixed(6)), "0", "0"].join(" ")), "0 0 0 1 0"].join(" "));
    f.appendChild(cm);
  }
  svg.appendChild(f);
  kolorFiltry.set(klucz, id);
  return `url(#${id})`;
}
