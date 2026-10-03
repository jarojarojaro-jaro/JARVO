// Napisy edytora filmów: jedna funkcja rysująca na kanwie. Bez zależności (czysty JS), bo używają jej
// trzy miejsca: podgląd w edytorze, eksport z edytora (PNG na napis) i Wideograf (projekt.py render przez
// przeglądarkę bez okna). Dzięki temu napis wygląda tak samo w podglądzie, w pliku z edytora i w pliku od agenta.

// Kroje spoza systemu leżą lokalnie (hq/web/fonts/kroje, OFL, scripts/kroje.py): podgląd, eksport i render agenta
// mają te same pliki, bez Google Fonts.
// Kroje zwykłych napisów: [rodzina CSS, nazwa, grupa, grubość pogrubionego, grubość zwykłego]. Grubości to te, które
// mają pliki w fonts/kroje (kroje.py), więc przeglądarka nie pogrubia sztucznie kroju z jedną grubością.
const ED_FONTS = [
  ["system-ui, 'Segoe UI', Roboto, sans-serif", "Bezszeryfowy", "systemowe", 800, 500],
  ["Georgia, 'Times New Roman', serif", "Szeryfowy", "systemowe", 800, 500],
  ["'Bricolage Grotesque', system-ui, sans-serif", "Bricolage", "mocne", 800, 500],
  ["'Montserrat', 'Arial Black', sans-serif", "Montserrat", "mocne", 800, 500],
  ["'Unbounded', 'Arial Black', sans-serif", "Unbounded", "mocne", 800, 500],
  ["'Poppins', Arial, sans-serif", "Poppins", "mocne", 800, 500],
  ["'Inter', Arial, sans-serif", "Inter", "mocne", 800, 500],
  ["'Archivo Black', 'Arial Black', sans-serif", "Archivo", "mocne", 400, 400],
  ["'Rubik', Arial, sans-serif", "Rubik", "mocne", 800, 500],
  ["'League Spartan', Arial, sans-serif", "Spartan", "mocne", 800, 500],
  ["'Kanit', 'Arial Black', sans-serif", "Kanit", "mocne", 800, 800],
  ["'Outfit', Arial, sans-serif", "Outfit", "mocne", 800, 500],
  ["'Syne', Arial, sans-serif", "Syne", "mocne", 800, 500],
  ["'Raleway', Arial, sans-serif", "Raleway", "mocne", 800, 500],
  ["'Anton', Impact, sans-serif", "Anton", "waskie", 400, 400],
  ["'Bebas Neue', Impact, sans-serif", "Bebas", "waskie", 400, 400],
  ["'Barlow Condensed', 'Arial Narrow', sans-serif", "Barlow", "waskie", 800, 600],
  ["'Oswald', 'Arial Narrow', sans-serif", "Oswald", "waskie", 700, 500],
  ["'Teko', 'Arial Narrow', sans-serif", "Teko", "waskie", 700, 500],
  ["'Fjalla One', 'Arial Narrow', sans-serif", "Fjalla", "waskie", 400, 400],
  ["'Staatliches', 'Arial Narrow', sans-serif", "Staatliches", "waskie", 400, 400],
  ["'Big Shoulders Display', 'Arial Narrow', sans-serif", "Big Shoulders", "waskie", 800, 500],
  ["'Saira Condensed', 'Arial Narrow', sans-serif", "Saira", "waskie", 800, 800],
  ["'Titan One', 'Arial Rounded MT Bold', sans-serif", "Titan", "okragle", 400, 400],
  ["'Baloo 2', 'Arial Rounded MT Bold', sans-serif", "Baloo", "okragle", 800, 600],
  ["'Nunito', 'Arial Rounded MT Bold', sans-serif", "Nunito", "okragle", 900, 600],
  ["'Paytone One', 'Arial Rounded MT Bold', sans-serif", "Paytone", "okragle", 400, 400],
  ["'DynaPuff', 'Arial Rounded MT Bold', sans-serif", "DynaPuff", "okragle", 700, 500],
  ["'Coiny', 'Arial Rounded MT Bold', sans-serif", "Coiny", "okragle", 400, 400],
  ["'Grandstander', 'Arial Rounded MT Bold', sans-serif", "Grandstander", "okragle", 800, 500],
  ["'Playfair Display', Georgia, serif", "Playfair", "szeryfowe", 800, 500],
  ["'Instrument Serif', Georgia, serif", "Instrument", "szeryfowe", 400, 400],
  ["'Abril Fatface', Georgia, serif", "Abril", "szeryfowe", 400, 400],
  ["'DM Serif Display', Georgia, serif", "DM Serif", "szeryfowe", 400, 400],
  ["'Lora', Georgia, serif", "Lora", "szeryfowe", 700, 500],
  ["'Bodoni Moda', Georgia, serif", "Bodoni", "szeryfowe", 800, 500],
  ["'Cormorant Garamond', Georgia, serif", "Cormorant", "szeryfowe", 600, 600],
  ["'Fraunces', Georgia, serif", "Fraunces", "szeryfowe", 800, 500],
  ["'Alfa Slab One', Georgia, serif", "Alfa Slab", "szeryfowe", 400, 400],
  ["'Yeseva One', Georgia, serif", "Yeseva", "szeryfowe", 400, 400],
  ["'Caveat', cursive", "Odręczny", "odreczne", 700, 500],
  ["'Pacifico', cursive", "Pacifico", "odreczne", 400, 400],
  ["'Dancing Script', cursive", "Dancing", "odreczne", 700, 500],
  ["'Lobster', cursive", "Lobster", "odreczne", 400, 400],
  ["'Kaushan Script', cursive", "Kaushan", "odreczne", 400, 400],
  ["'Great Vibes', cursive", "Great Vibes", "odreczne", 400, 400],
  ["'Amatic SC', cursive", "Amatic", "odreczne", 700, 700],
  ["'Caveat Brush', cursive", "Pędzel", "odreczne", 400, 400],
  ["'Patrick Hand', cursive", "Patrick", "odreczne", 400, 400],
  ["'Sedgwick Ave', cursive", "Graffiti", "odreczne", 400, 400],
  ["'Shrikhand', Georgia, serif", "Retro", "ozdobne", 400, 400],
  ["'Bangers', Impact, sans-serif", "Komiks", "ozdobne", 400, 400],
  ["'Tilt Neon', system-ui, sans-serif", "Neon", "ozdobne", 400, 400],
  ["'Rubik Dirt', Impact, sans-serif", "Grunge", "ozdobne", 400, 400],
  ["'Righteous', Impact, sans-serif", "Righteous", "ozdobne", 400, 400],
  ["'Bungee', Impact, sans-serif", "Bungee", "ozdobne", 400, 400],
  ["'Monoton', Impact, sans-serif", "Monoton", "ozdobne", 400, 400],
  ["'Press Start 2P', ui-monospace, monospace", "Piksel", "ozdobne", 400, 400],
  ["'Rubik Glitch', Impact, sans-serif", "Glitch", "ozdobne", 400, 400],
  ["'Rubik Bubbles', Impact, sans-serif", "Bąbelki", "ozdobne", 400, 400],
  ["'Russo One', Impact, sans-serif", "Russo", "ozdobne", 400, 400],
  ["'Black Ops One', Impact, sans-serif", "Szablon", "ozdobne", 400, 400],
  ["'Sigmar', Impact, sans-serif", "Sigmar", "ozdobne", 400, 400],
  ["'Rammetto One', Impact, sans-serif", "Rammetto", "ozdobne", 400, 400],
  ["'Space Grotesk', system-ui, sans-serif", "Space", "techniczne", 700, 500],
  ["'JetBrains Mono', ui-monospace, monospace", "Mono", "techniczne", 800, 500],
  ["'Audiowide', system-ui, sans-serif", "Audiowide", "techniczne", 400, 400],
  ["'Chakra Petch', system-ui, sans-serif", "Chakra", "techniczne", 700, 700],
  ["'Space Mono', ui-monospace, monospace", "Space Mono", "techniczne", 700, 700],
  ["'Major Mono Display', ui-monospace, monospace", "Major Mono", "techniczne", 400, 400],
];
const ED_FONT_WAGI = new Map(ED_FONTS.map((f) => [f[0], f]));

function textFont(t, H, W) {
  const px = Math.max(6, (t.size || 64) * Math.min(W, H) / 1080);
  const f = ED_FONT_WAGI.get(t.font || ED_FONTS[0][0]);   // krój spoza listy (stary projekt, agent): 800 / 500
  return { px, font: `${f ? f[t.bold === false ? 4 : 3] : t.bold === false ? 500 : 800} ${px}px ${t.font || ED_FONTS[0][0]}` };
}
// Wczytanie kroju z TEKSTEM napisu: bez tekstu przeglądarka bierze tylko podzbiór „latin” i polskie znaki
// rysuje krojem zastępczym. `fontGotowy` = już wczytany (podgląd rysuje od razu, a po wczytaniu jeszcze raz).
function fontLoad(font, text) {
  try { return document.fonts.load(font, String(text || "") || " "); } catch (_) { return Promise.resolve([]); }
}
function fontGotowy(font, text) {
  try { return document.fonts.check(font, String(text || "") || " "); } catch (_) { return true; }
}
function wrapLines(ctx, text, maxW) {
  const out = [];
  for (const para of String(text || "").split("\n")) {
    let line = "";
    for (const word of para.split(/\s+/).filter(Boolean)) {
      const test = line ? `${line} ${word}` : word;
      if (line && ctx.measureText(test).width > maxW) { out.push(line); line = word; } else line = test;
    }
    out.push(line);
  }
  return out;
}
// Prostokąt napisu na kanwie W×H (do trafiania myszą i rysowania).
function textBox(ctx, t, W, H) {
  const { px, font } = textFont(t, H, W);
  ctx.font = font;
  const lines = wrapLines(ctx, t.text, (t.maxw || 0.86) * W);
  const lh = px * 1.18;
  const w = Math.max(...lines.map((l) => ctx.measureText(l).width), px * 0.5);
  const h = lines.length * lh;
  const cx = (t.x ?? 0.5) * W, cy = (t.y ?? 0.8) * H;
  const pad = t.style === "box" ? px * 0.35 : px * 0.1;
  return { px, font, lines, lh, w, h, cx, cy, x0: cx - w / 2 - pad, y0: cy - h / 2 - pad, x1: cx + w / 2 + pad, y1: cy + h / 2 + pad };
}
// Karaoke: napis ma `words` = [[od, do, słowo]] w sekundach OD POCZĄTKU napisu (przesunięcie napisu na osi
// zabiera czasy ze sobą) i `hl` = kolor aktywnego słowa. Poprawiony tekst z tą samą liczbą słów zachowuje czasy
// (literówka), inna liczba słów wyłącza karaoke tej linii. Ta sama reguła jest w edytor.py (eksport).
function karaokeWords(t) {
  if (!t || !t.hl || !Array.isArray(t.words) || !t.words.length) return null;
  const toks = String(t.text || "").split(/\s+/).filter(Boolean);
  if (toks.length !== t.words.length) return null;
  return t.words.map((w, i) => [Math.max(0, +w[0] || 0), Math.max(0, +w[1] || 0), toks[i]]);
}
// Numer aktywnego słowa w chwili `now` (czas osi): ostatnie, które już się zaczęło; przed pierwszym = 0.
function karaokeIndex(t, now) {
  const ws = karaokeWords(t);
  if (!ws) return -1;
  const rel = now - (t.start || 0);
  let k = 0;
  for (let i = 0; i < ws.length; i++) if (ws[i][0] <= rel + 1e-6) k = i;
  return k;
}
function drawText(ctx, t, W, H, hi = -1) {
  const b = textBox(ctx, t, W, H);
  ctx.save();
  ctx.font = b.font;
  ctx.textBaseline = "middle";
  const align = t.align || "center";
  ctx.textAlign = align;
  const ax = align === "left" ? b.cx - b.w / 2 : align === "right" ? b.cx + b.w / 2 : b.cx;
  if (t.style === "box") {
    const r = b.px * 0.22;
    ctx.fillStyle = t.bg || "rgba(0,0,0,0.72)";
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0, r); else ctx.rect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0);
    ctx.fill();
  }
  const kw = hi >= 0 ? karaokeWords(t) : null;
  let wi = 0;   // numer słowa w całym napisie (linie z wrapLines zachowują kolejność słów)
  b.lines.forEach((line, i) => {
    const y = b.cy - b.h / 2 + b.lh * (i + 0.5);
    if (kw) {   // słowo po słowie: aktywne w kolorze `hl`, reszta w kolorze napisu
      const lw = ctx.measureText(line).width;
      let x = align === "left" ? ax : align === "right" ? ax - lw : ax - lw / 2;
      ctx.textAlign = "left";
      for (const word of line.split(" ").filter(Boolean)) {
        if (t.style === "outline") {
          ctx.lineJoin = "round"; ctx.lineWidth = Math.max(2, b.px * 0.14); ctx.strokeStyle = t.bg || "#000";
          ctx.strokeText(word, x, y);
        }
        if (t.style === "shadow") { ctx.shadowColor = "rgba(0,0,0,0.65)"; ctx.shadowBlur = b.px * 0.18; ctx.shadowOffsetY = b.px * 0.05; }
        ctx.fillStyle = wi === hi ? t.hl : (t.color || "#fff");
        ctx.fillText(word, x, y);
        ctx.shadowColor = "transparent";
        x += ctx.measureText(word + " ").width;
        wi++;
      }
      return;
    }
    if (t.style === "outline") {
      ctx.lineJoin = "round"; ctx.lineWidth = Math.max(2, b.px * 0.14); ctx.strokeStyle = t.bg || "#000";
      ctx.strokeText(line, ax, y);
    }
    if (t.style === "shadow") { ctx.shadowColor = "rgba(0,0,0,0.65)"; ctx.shadowBlur = b.px * 0.18; ctx.shadowOffsetY = b.px * 0.05; }
    ctx.fillStyle = t.color || "#fff";
    ctx.fillText(line, ax, y);
    ctx.shadowColor = "transparent";
  });
  ctx.restore();
  return b;
}
