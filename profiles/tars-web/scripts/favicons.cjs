#!/usr/bin/env node
/**
 * Komplet faviconów, ikon PWA i manifestu z jednego logo (pakiet `favicons`).
 *
 *   node favicons.cjs <logo.svg|png> <outdir> --name "Nazwa" [--short "Krótka"] [--color "#0b5fff"]
 *                     [--bg "#ffffff"] [--lang pl]
 *
 * Wynik: pliki ikon, site.webmanifest, head.html (tagi do <head>), a jeśli wejście to SVG, także favicon.svg.
 */
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

// `favicons` jest tylko ESM; import() ignoruje NODE_PATH, więc szukamy pakietu ręcznie.
async function importGlobal(name) {
  const dirs = (process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean);
  dirs.push(path.join(__dirname, 'node_modules'), '/opt/tars/node/node_modules', '/usr/local/lib/node_modules');
  for (const dir of dirs) {
    const pkgDir = path.join(dir, name);
    const pkgFile = path.join(pkgDir, 'package.json');
    if (!fs.existsSync(pkgFile)) continue;
    const pkg = JSON.parse(fs.readFileSync(pkgFile, 'utf8'));
    let entry = pkg.main || 'index.js';
    const exp = pkg.exports && (pkg.exports['.'] || pkg.exports);
    if (typeof exp === 'string') entry = exp;
    else if (exp) entry = (exp.import && (exp.import.default || exp.import)) || exp.default || entry;
    return import(pathToFileURL(path.join(pkgDir, entry)).href);
  }
  return import(name);
}

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
}

(async () => {
  const [src, outdir] = process.argv.slice(2).filter((a, i, all) => !a.startsWith('--') && !(all[i - 1] || '').startsWith('--'));
  if (!src || !outdir) { console.error('Użycie: node favicons.cjs <logo> <outdir> --name "Nazwa"'); process.exit(2); }
  const mod = await importGlobal('favicons');
  const favicons = mod.favicons || mod.default;
  const name = arg('--name', 'Strona');
  const config = {
    path: '/', appName: name, appShortName: arg('--short', name), lang: arg('--lang', 'pl'),
    background: arg('--bg', '#ffffff'), theme_color: arg('--color', '#111111'),
    display: 'standalone', start_url: '/',
    icons: { android: true, appleIcon: true, appleStartup: false, favicons: true, windows: false, yandex: false },
  };
  const res = await favicons(src, config);
  fs.mkdirSync(outdir, { recursive: true });
  for (const img of res.images) fs.writeFileSync(path.join(outdir, img.name), img.contents);
  for (const f of res.files) fs.writeFileSync(path.join(outdir, f.name === 'manifest.webmanifest' ? 'site.webmanifest' : f.name), f.contents);
  let head = res.html.join('\n').replace(/manifest\.webmanifest/g, 'site.webmanifest');
  if (src.toLowerCase().endsWith('.svg')) {
    fs.copyFileSync(src, path.join(outdir, 'favicon.svg'));
    head = '<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n' + head;
  }
  fs.writeFileSync(path.join(outdir, 'head.html'), head + '\n');
  console.log(JSON.stringify({ ok: true, files: fs.readdirSync(outdir).sort(), head: path.join(outdir, 'head.html') }, null, 1));
})().catch((e) => { console.error(e.message); process.exit(1); });
