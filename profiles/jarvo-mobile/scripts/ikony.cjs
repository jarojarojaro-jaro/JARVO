#!/usr/bin/env node
/**
 * Ikony i ekran startowy aplikacji Expo z logo albo z inicjałów (sharp z obrazu floty).
 *
 *   node ikony.cjs --out <katalog assets> --kolor "#C2185B" [--logo logo.png|logo.svg] [--litery SO]
 *
 * Pliki (wymogi sklepów):
 *   icon.png                     1024×1024, BEZ kanału alfa (App Store odrzuca ikonę z przezroczystością)
 *   android-icon-foreground.png  1024×1024, logo w bezpiecznym środku (Android przycina ikonę adaptacyjną do koła/kwadratu)
 *   android-icon-background.png  1024×1024, kolor marki
 *   android-icon-monochrome.png  1024×1024, biała sylwetka (ikony tematyczne Androida 13+)
 *   splash-icon.png              1024×1024, przezroczyste tło (kolor tła ekranu startowego ustawia app.config.ts)
 *   favicon.png                  48×48 (wersja webowa)
 * Wynik: JSON z listą plików i rozmiarami na stdout; kod 1 przy błędzie.
 */
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
}

function luminancja(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const naKolorze = (hex) => (luminancja(hex) > 0.4 ? '#111318' : '#FFFFFF');
const esc = (s) => String(s).replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[c]));

function svgLitery(litery, kolor, rozmiar) {
  const fs_ = Math.round(rozmiar * (litery.length > 1 ? 0.36 : 0.46));
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${rozmiar}" height="${rozmiar}">
  <text x="50%" y="50%" dy="0.36em" text-anchor="middle" font-family="Inter, DejaVu Sans, sans-serif" font-weight="700"
   font-size="${fs_}" fill="${kolor}">${esc(litery)}</text></svg>`);
}

async function znak(logo, litery, kolorLiter, bok) {
  // logo albo inicjały wpasowane w kwadrat `bok` (przezroczyste tło)
  if (logo) {
    return sharp(logo, { density: 600 }).resize(bok, bok, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } }).png().toBuffer();
  }
  return sharp(svgLitery(litery, kolorLiter, bok)).png().toBuffer();
}

(async () => {
  const out = arg('--out');
  const kolor = arg('--kolor');
  const logo = arg('--logo');
  const litery = (arg('--litery', 'A') || 'A').slice(0, 2);
  if (!out || !/^#[0-9A-Fa-f]{6}$/.test(kolor || '')) {
    console.error('Użycie: node ikony.cjs --out <assets> --kolor "#RRGGBB" [--logo plik] [--litery AB]');
    process.exit(2);
  }
  if (logo && !fs.existsSync(logo)) { console.error(`Brak pliku logo: ${logo}`); process.exit(2); }
  fs.mkdirSync(out, { recursive: true });
  const N = 1024;
  const tlo = { create: { width: N, height: N, channels: 3, background: kolor } };
  const naTle = naKolorze(kolor);
  const wynik = {};
  const zapisz = async (nazwa, obraz) => {
    const p = path.join(out, nazwa);
    await obraz.toFile(p);
    const m = await sharp(p).metadata();
    wynik[nazwa] = { szer: m.width, wys: m.height, alfa: !!m.hasAlpha };
  };

  // App Store: ikona bez przezroczystości; logo w 66% powierzchni
  const zIkona = await znak(logo, litery, naTle, Math.round(N * 0.66));
  await zapisz('icon.png', sharp(tlo).composite([{ input: zIkona, gravity: 'center' }]).flatten({ background: kolor }).removeAlpha().png());
  // Android: ikona adaptacyjna (bezpieczne koło ≈ 66% → znak 56%, żeby nic nie ucięło)
  const zFg = await znak(logo, litery, naTle, Math.round(N * 0.56));
  const pusty = { create: { width: N, height: N, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } };
  const fg = await sharp(pusty).composite([{ input: zFg, gravity: 'center' }]).png().toBuffer();
  await zapisz('android-icon-foreground.png', sharp(fg));
  await zapisz('android-icon-background.png', sharp(tlo).png());
  const alfa = await sharp(fg).ensureAlpha().extractChannel(3).toBuffer();
  await zapisz('android-icon-monochrome.png',
    sharp({ create: { width: N, height: N, channels: 3, background: '#FFFFFF' } }).joinChannel(alfa).png());
  // ekran startowy: znak w kolorze marki na przezroczystym tle
  const zSplash = await znak(logo, litery, kolor, Math.round(N * 0.8));
  await zapisz('splash-icon.png', sharp(pusty).composite([{ input: zSplash, gravity: 'center' }]).png());
  await zapisz('favicon.png', sharp(path.join(out, 'icon.png')).resize(48, 48).png());
  console.log(JSON.stringify({ out, logo: logo || null, litery: logo ? null : litery, pliki: wynik }));
})().catch((e) => { console.error(e && e.stack ? e.stack : String(e)); process.exit(1); });
