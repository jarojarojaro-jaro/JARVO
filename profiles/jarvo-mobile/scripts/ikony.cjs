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
 * Logo może być: znakiem na przezroczystym tle (wpasowany w środek ikony na kolorze marki; jednobarwny znak w kolorze
 * tła przemalowany na czytelny), znakiem wielokolorowym (nigdy nie przemalowany) albo gotowym kafelkiem ikony
 * (np. SVG z własnym zaokrąglonym tłem): wtedy idzie na całą ikonę, a tłem Androida jest kolor kafelka.
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

const kontrast = (a, b) => {
  const [x, y] = [luminancja(a), luminancja(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};
const hex = (r, g, b) => '#' + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();

async function sredniKolor(png) {
  // średni kolor widocznych pikseli (alfa > 50%) znaku na przezroczystym tle
  const { data, info } = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  let r = 0, g = 0, b = 0, n = 0;
  for (let i = 0; i < data.length; i += info.channels) {
    if (data[i + 3] > 128) { r += data[i]; g += data[i + 1]; b += data[i + 2]; n++; }
  }
  return n ? hex(r / n, g / n, b / n) : null;
}

const PUSTE = { r: 0, g: 0, b: 0, alpha: 0 };
const odleglosc = (d, i, [r, g, b]) => Math.hypot(d[i] - r, d[i + 1] - g, d[i + 2] - b);
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

async function analiza(logo) {
  // Logo wpasowane w kwadrat: jak dużo go widać (kafelek = prawie cały kwadrat), czy jest jednobarwne i jaki kolor
  // ma brzeg kafelka (najczęstszy z próbek przy czterech krawędziach widocznej części).
  const S = 256;
  const { data, info } = await sharp(logo, { density: 300 }).resize(S, S, { fit: 'contain', background: PUSTE })
    .ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const c = info.channels;
  let n = 0, r = 0, g = 0, b = 0;
  for (let i = 0; i < data.length; i += c) if (data[i + 3] > 128) { r += data[i]; g += data[i + 1]; b += data[i + 2]; n++; }
  if (!n) return { pokrycie: 0, jednobarwne: true, kafelek: null };
  const sr = [r / n, g / n, b / n];
  let blisko = 0;
  for (let i = 0; i < data.length; i += c) if (data[i + 3] > 128 && odleglosc(data, i, sr) < 60) blisko++;
  const pokrycie = n / (S * S);
  let kafelek = null;
  if (pokrycie > 0.85) {
    const px = (x, y) => { const i = (y * S + x) * c; return data[i + 3] > 128 ? hex(data[i], data[i + 1], data[i + 2]) : null; };
    const m = Math.round(S * 0.05), s2 = S >> 1;
    const proby = [px(s2, m), px(s2, S - 1 - m), px(m, s2), px(S - 1 - m, s2)].filter(Boolean);
    const ile = {};
    for (const k of proby) ile[k] = (ile[k] || 0) + 1;
    kafelek = Object.entries(ile).sort((x, y) => y[1] - x[1])[0]?.[0] || null;
  }
  return { pokrycie, jednobarwne: blisko / n > 0.85, kafelek };
}

async function sylwetka(png, tloKafelka) {
  // biała sylwetka grafiki na kafelku (piksele wyraźnie inne niż kolor kafelka) dla ikon tematycznych Androida
  const { data, info } = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const t = rgb(tloKafelka), c = info.channels;
  const alfa = Buffer.alloc(info.width * info.height);
  for (let i = 0, j = 0; i < data.length; i += c, j++) alfa[j] = data[i + 3] > 128 && odleglosc(data, i, t) > 60 ? 255 : 0;
  return sharp({ create: { width: info.width, height: info.height, channels: 3, background: '#FFFFFF' } })
    .joinChannel(alfa, { raw: { width: info.width, height: info.height, channels: 1 } });
}

async function znak(logo, litery, kolorLiter, bok, tloHex, jednobarwne = true) {
  // logo albo inicjały wpasowane w kwadrat `bok` (przezroczyste tło). Jednobarwne logo w kolorze tła (np. brązowe
  // na brązowej ikonie) znikałoby: przy kontraście < 3:1 przemalowujemy je na kolor czytelny na tle, z tą samą
  // sylwetką. Wielokolorowego nie ruszamy (średni kolor nic o nim nie mówi), najwyżej ostrzegamy.
  if (logo) {
    const png = await sharp(logo, { density: 600 }).resize(bok, bok, { fit: 'contain', background: PUSTE }).png().toBuffer();
    const sredni = tloHex ? await sredniKolor(png) : null;
    if (sredni && kontrast(sredni, tloHex) < 3 && !jednobarwne) {
      UWAGI.push(`logo wielokolorowe słabo odcina się od tła ${tloHex}: zostaje w swoich kolorach (rozważ inny kolor tła ikony)`);
      return png;
    }
    if (sredni && kontrast(sredni, tloHex) < 3) {
      UWAGI.push(`logo (${sredni}) zlewa się z tłem ${tloHex}: przemalowane na ${kolorLiter}`);
      const alfa = await sharp(png).ensureAlpha().extractChannel(3).toBuffer();
      return sharp({ create: { width: bok, height: bok, channels: 3, background: kolorLiter } }).joinChannel(alfa).png().toBuffer();
    }
    return png;
  }
  return sharp(svgLitery(litery, kolorLiter, bok)).png().toBuffer();
}
const UWAGI = [];

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
  if (logo) {
    const m = await sharp(logo, { density: 72 }).metadata();
    if (m.width && m.height && Math.max(m.width / m.height, m.height / m.width) > 2) {
      UWAGI.push(`logo poziome (${m.width}×${m.height}): na ikonie będzie drobne; czytelniejszy jest kwadratowy sygnet od marki`);
    }
  }
  fs.mkdirSync(out, { recursive: true });
  const N = 1024;
  const A = logo ? await analiza(logo) : null;
  const kafelek = A && A.kafelek;                   // logo z własnym tłem ikony: idzie na całą ikonę
  if (kafelek) UWAGI.push(`logo to gotowy kafelek ikony (tło ${kafelek}): na całą ikonę, bez dodatkowego tła`);
  const tloIkony = kafelek || kolor;
  const tlo = { create: { width: N, height: N, channels: 3, background: tloIkony } };
  const naTle = naKolorze(kolor);
  const jedno = !A || A.jednobarwne;
  const wynik = {};
  const zapisz = async (nazwa, obraz) => {
    const p = path.join(out, nazwa);
    await obraz.toFile(p);
    const m = await sharp(p).metadata();
    wynik[nazwa] = { szer: m.width, wys: m.height, alfa: !!m.hasAlpha };
  };

  const pusty = { create: { width: N, height: N, channels: 4, background: PUSTE } };
  const wpasuj = (bok) => sharp(logo, { density: 600 }).resize(bok, bok, { fit: 'contain', background: PUSTE }).png().toBuffer();
  if (kafelek) {
    // App Store przycina rogi sam: kafelek na całą ikonę, przezroczyste rogi w kolorze kafelka
    await zapisz('icon.png', sharp(logo, { density: 600 }).resize(N, N, { fit: 'cover' }).flatten({ background: kafelek }).removeAlpha().png());
    // Android: tło w kolorze kafelka, kafelek w 80% (brzeg zlewa się z tłem, grafika w bezpiecznym kole)
    const fg = await sharp(pusty).composite([{ input: await wpasuj(Math.round(N * 0.8)), gravity: 'center' }]).png().toBuffer();
    await zapisz('android-icon-foreground.png', sharp(fg));
    await zapisz('android-icon-background.png', sharp(tlo).png());
    await zapisz('android-icon-monochrome.png', (await sylwetka(fg, kafelek)).png());
    await zapisz('splash-icon.png', sharp(pusty).composite([{ input: await wpasuj(Math.round(N * 0.6)), gravity: 'center' }]).png());
  } else {
    // App Store: ikona bez przezroczystości; logo w 66% powierzchni
    const zIkona = await znak(logo, litery, naTle, Math.round(N * 0.66), kolor, jedno);
    await zapisz('icon.png', sharp(tlo).composite([{ input: zIkona, gravity: 'center' }]).flatten({ background: kolor }).removeAlpha().png());
    // Android: ikona adaptacyjna (bezpieczne koło ≈ 66% → znak 56%, żeby nic nie ucięło)
    const zFg = await znak(logo, litery, naTle, Math.round(N * 0.56), kolor, jedno);
    const fg = await sharp(pusty).composite([{ input: zFg, gravity: 'center' }]).png().toBuffer();
    await zapisz('android-icon-foreground.png', sharp(fg));
    await zapisz('android-icon-background.png', sharp(tlo).png());
    const alfa = await sharp(fg).ensureAlpha().extractChannel(3).toBuffer();
    await zapisz('android-icon-monochrome.png',
      sharp({ create: { width: N, height: N, channels: 3, background: '#FFFFFF' } }).joinChannel(alfa).png());
    // ekran startowy: znak w kolorze marki na przezroczystym tle
    const zSplash = await znak(logo, litery, kolor, Math.round(N * 0.8), undefined, jedno);
    await zapisz('splash-icon.png', sharp(pusty).composite([{ input: zSplash, gravity: 'center' }]).png());
  }
  await zapisz('favicon.png', sharp(path.join(out, 'icon.png')).resize(48, 48).png());
  console.log(JSON.stringify({ out, logo: logo || null, litery: logo ? null : litery, pliki: wynik, uwagi: [...new Set(UWAGI)] }));
})().catch((e) => { console.error(e && e.stack ? e.stack : String(e)); process.exit(1); });
