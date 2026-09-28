#!/usr/bin/env node
/**
 * Optymalizacja obrazów (sharp): warianty szerokości × formaty + gotowe <picture>.
 *
 *   node images.cjs <plik|katalog> <outdir> [--widths 480,960,1440] [--formats avif,webp,jpg]
 *                   [--quality 70] [--sizes "(max-width: 768px) 100vw, 50vw"]
 *
 * Wynik: pliki <nazwa>-<szer>.<format> + manifest.json (wymiary, rozmiary przed/po, snippet HTML).
 */
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
}

const EXT = new Set(['.jpg', '.jpeg', '.png', '.webp', '.avif', '.tif', '.tiff', '.gif']);

(async () => {
  const positional = process.argv.slice(2).filter((a, i, all) => !a.startsWith('--') && !(all[i - 1] || '').startsWith('--'));
  const [input, outdir] = positional;
  if (!input || !outdir) { console.error('Użycie: node images.cjs <plik|katalog> <outdir>'); process.exit(2); }
  const widths = arg('--widths', '480,960,1440,1920').split(',').map(Number);
  const formats = arg('--formats', 'avif,webp,jpg').split(',');
  const quality = Number(arg('--quality', '70'));
  const sizes = arg('--sizes', '100vw');
  const files = fs.statSync(input).isDirectory()
    ? fs.readdirSync(input).filter((f) => EXT.has(path.extname(f).toLowerCase())).map((f) => path.join(input, f))
    : [input];
  fs.mkdirSync(outdir, { recursive: true });
  const manifest = [];
  for (const file of files) {
    const base = path.basename(file, path.extname(file)).toLowerCase().replace(/[^a-z0-9-]+/g, '-');
    const meta = await sharp(file).metadata();
    const before = fs.statSync(file).size;
    const usable = widths.filter((w) => w <= (meta.width || w));
    if (!usable.length) usable.push(meta.width);
    const variants = {};
    for (const fmt of formats) {
      variants[fmt] = [];
      for (const w of usable) {
        const out = path.join(outdir, `${base}-${w}.${fmt}`);
        let pipe = sharp(file).resize({ width: w, withoutEnlargement: true });
        if (fmt === 'avif') pipe = pipe.avif({ quality: Math.max(30, quality - 15) });
        else if (fmt === 'webp') pipe = pipe.webp({ quality });
        else if (fmt === 'png') pipe = pipe.png({ compressionLevel: 9, palette: true });
        else pipe = pipe.jpeg({ quality, mozjpeg: true });
        const info = await pipe.toFile(out);
        variants[fmt].push({ file: path.basename(out), width: info.width, height: info.height, bytes: info.size });
      }
    }
    const largest = usable[usable.length - 1];
    const h = Math.round((meta.height / meta.width) * largest);
    const srcset = (fmt) => variants[fmt].map((v) => `/img/${v.file} ${v.width}w`).join(', ');
    const fallback = formats.includes('jpg') ? 'jpg' : formats[formats.length - 1];
    const html = [
      '<picture>',
      ...formats.filter((f) => f !== fallback).map((f) => `  <source type="image/${f}" srcset="${srcset(f)}" sizes="${sizes}">`),
      `  <img src="/img/${variants[fallback].slice(-1)[0].file}" srcset="${srcset(fallback)}" sizes="${sizes}" width="${largest}" height="${h}" alt="TODO" loading="lazy" decoding="async">`,
      '</picture>',
    ].join('\n');
    const after = Math.min(...Object.values(variants).map((vs) => vs[vs.length - 1].bytes));
    manifest.push({ source: file, width: meta.width, height: meta.height, bytes_before: before, smallest_full_bytes: after, variants, html });
  }
  fs.writeFileSync(path.join(outdir, 'manifest.json'), JSON.stringify(manifest, null, 1));
  console.log(JSON.stringify({ ok: true, images: manifest.length, manifest: path.join(outdir, 'manifest.json') }, null, 1));
})().catch((e) => { console.error(e.message); process.exit(1); });
