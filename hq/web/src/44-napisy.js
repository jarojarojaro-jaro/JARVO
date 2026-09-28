// Napisy edytora filmów: jedna funkcja rysująca na kanwie. Bez zależności (czysty JS), bo używają jej
// trzy miejsca: podgląd w edytorze, eksport z edytora (PNG na napis) i Wideograf (projekt.py render przez
// przeglądarkę bez okna). Dzięki temu napis wygląda tak samo w podglądzie, w pliku z edytora i w pliku od agenta.

const ED_FONTS = [
  ["system-ui, 'Segoe UI', Roboto, sans-serif", "Bezszeryfowy"], ["'Bricolage Grotesque', system-ui, sans-serif", "Display"],
  ["Georgia, 'Times New Roman', serif", "Szeryfowy"], ["'JetBrains Mono', ui-monospace, monospace", "Mono"],
];

function textFont(t, H, W) {
  const px = Math.max(6, (t.size || 64) * Math.min(W, H) / 1080);
  return { px, font: `${t.bold === false ? 500 : 800} ${px}px ${t.font || ED_FONTS[0][0]}` };
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
function drawText(ctx, t, W, H) {
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
  b.lines.forEach((line, i) => {
    const y = b.cy - b.h / 2 + b.lh * (i + 0.5);
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
