// Figurki agentów w aplikacji: kafel ze ścianą pokoju i postacią z wieży (silnik pikseli z 20-art.js), jak w makiecie V2.
// Pokój agenta = `hq_room` z fleet.yaml (pole `pokoj` z GET /app); agent bez pokoju (testowy, własny) dostaje pokój
// z sumy nazwy, więc wygląda tak samo w każdym miejscu i po każdym przeładowaniu.
// Etap 7 (usunięcie Starej Bazy) zostawia z 20-art.js to, czego używa ten plik: Pix, Layers, shade, LOOKS, drawFigure.

const WYGLAD_POKOJU = {
  bridge:     { look: "boss",       sciana: "#B81D36", sciana2: "#A51830", wzor: "panels" },
  study:      { look: "study",      sciana: "#22513E", sciana2: "#2B604A", wzor: "stripes" },
  devlab:     { look: "devlab",     sciana: "#2155AA", sciana2: "#2B62BA", wzor: "panels" },
  atelier:    { look: "atelier",    sciana: "#C2507A", sciana2: "#AD4469", wzor: "bricks" },
  filmstudio: { look: "filmstudio", sciana: "#423B5E", sciana2: "#363050", wzor: "foam" },
  office:     { look: "office",     sciana: "#2F4058", sciana2: "#384B66", wzor: "panels" },
  radar:      { look: "radar",      sciana: "#22423E", sciana2: "#2B504B", wzor: "panels" },
  apps:       { look: "apps",       sciana: "#3E3772", sciana2: "#4A4284", wzor: "panels" },
  control:    { look: "control",    sciana: "#21405A", sciana2: "#2A4D6B", wzor: "ribs" },
  workshop:   { look: "workshop",   sciana: "#C96A22", sciana2: "#B25B18", wzor: "ribs" },
};
const POKOJE_ZAPASOWE = ["office", "devlab", "study", "radar", "apps", "control", "atelier", "workshop", "filmstudio"];

function pokojAgenta(a) {
  if (!a) return "office";
  if (a.pokoj && WYGLAD_POKOJU[a.pokoj]) return a.pokoj;
  if (a.rodzaj === "orchestrator") return "bridge";
  const suma = [...String(a.name || "")].reduce((s, c) => (s * 31 + c.charCodeAt(0)) >>> 0, 7);
  return POKOJE_ZAPASOWE[suma % POKOJE_ZAPASOWE.length];
}

// wzór ściany kafla (24×24 piksele), ten sam co w makiecie V2
function scianaFigurki(g, w, W, H) {
  g.r(0, 0, W, H, w.sciana);
  const c = w.sciana2;
  if (w.wzor === "stripes") for (let x = 1; x < W; x += 3) g.r(x, 0, 1, H, c);
  else if (w.wzor === "bricks") for (let y = 1; y < H; y += 4) { g.r(0, y, W, 1, c); for (let x = (y >> 2) % 2 ? 1 : 5; x < W; x += 8) g.r(x, y, 1, 4, c); }
  else if (w.wzor === "foam") for (let y = 1; y < H; y += 4) for (let x = (y >> 2) % 2 ? 0 : 2; x < W; x += 4) g.r(x, y, 2, 2, c);
  else if (w.wzor === "ribs") for (let x = 1; x < W; x += 4) { g.r(x, 0, 1, H, shade(w.sciana, 0.1)); g.r(x + 1, 0, 1, H, c); }
  else for (let x = 3; x < W; x += 8) { g.r(x, 0, 1, H, c); for (let y = 4; y < H; y += 9) { g.p(x - 2, y, c); g.p(x + 2, y, c); } }
}

// gotowy rysunek na pokój (elementy React są niezmienne, więc jeden obiekt służy wszystkim kaflom)
const FIGURKI = new Map();
function rysunekFigurki(pokoj) {
  let r = FIGURKI.get(pokoj);
  if (!r) {
    const w = WYGLAD_POKOJU[pokoj] || WYGLAD_POKOJU.office;
    const L = new Layers();
    scianaFigurki(L.get("tlo"), w, 24, 24);
    drawFigure(L, "f", 12, 31, w.look, { legs: false });
    r = L.render();
    FIGURKI.set(pokoj, r);
  }
  return r;
}

const scianaAgenta = (a) => (WYGLAD_POKOJU[pokojAgenta(a)] || WYGLAD_POKOJU.office).sciana;
