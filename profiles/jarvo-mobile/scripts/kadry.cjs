#!/usr/bin/env node
/**
 * Kadry do sklepów: render stron HTML (nagłówek, kolory marki, ekran aplikacji w ramce) w dokładnych wymiarach
 * i zapis PNG bez kanału alfa (sharp: removeAlpha), plus ikona Google 512×512 z ikony aplikacji.
 *
 *   node kadry.cjs <zadania.json>
 *
 * zadania.json: [{ "html": "/abs/kadr.html", "out": "/abs/01.png", "w": 1320, "h": 2868 },
 *                { "ikona": "/abs/assets/icon.png", "out": "/abs/icon.png", "rozmiar": 512 }]
 * Strona może ustawić window.KADR_GOTOWY = true, gdy skończy rysować (np. próbkowanie koloru paska stanu);
 * render czeka na to i na wczytanie obrazów. Wynik: lista {out, w, h, alfa, bajty} na stdout (JSON).
 * Kod 1, gdy którykolwiek plik ma złe wymiary.
 */
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const { chromium } = require('playwright-core');

function browserPath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const f = '/etc/hermes/agent-browser-executable-path';
  if (fs.existsSync(f)) return fs.readFileSync(f, 'utf8').trim();
  return undefined;
}

(async () => {
  const plik = process.argv[2];
  if (!plik) { console.error('Użycie: node kadry.cjs <zadania.json>'); process.exit(2); }
  const zadania = JSON.parse(fs.readFileSync(plik, 'utf8'));
  const wyniki = [];
  let browser = null;
  try {
    for (const z of zadania) {
      fs.mkdirSync(path.dirname(z.out), { recursive: true });
      let bufor;
      if (z.ikona) {
        bufor = await sharp(z.ikona).resize(z.rozmiar, z.rozmiar, { fit: 'cover' }).removeAlpha().png({ compressionLevel: 9 }).toBuffer();
      } else {
        if (!browser) browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox', '--allow-file-access-from-files'] });
        const page = await browser.newPage({ viewport: { width: z.w, height: z.h }, deviceScaleFactor: 1 });
        await page.goto('file://' + z.html, { waitUntil: 'load', timeout: 60000 });
        await page.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth > 0), null, { timeout: 30000 });
        await page.waitForFunction(() => window.KADR_GOTOWY !== false, null, { timeout: 10000 }).catch(() => {});
        await page.evaluate(() => document.fonts.ready);
        const png = await page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: z.w, height: z.h } });
        await page.close();
        bufor = await sharp(png).removeAlpha().png({ compressionLevel: 9 }).toBuffer();
      }
      fs.writeFileSync(z.out, bufor);
      const m = await sharp(bufor).metadata();
      wyniki.push({ out: z.out, w: m.width, h: m.height, alfa: !!m.hasAlpha, bajty: bufor.length,
        ok: m.width === (z.w || z.rozmiar) && m.height === (z.h || z.rozmiar) && !m.hasAlpha });
    }
  } finally {
    if (browser) await browser.close();
  }
  console.log(JSON.stringify(wyniki));
  process.exit(wyniki.every((w) => w.ok) ? 0 : 1);
})().catch((e) => { console.error(e && e.stack ? e.stack : String(e)); process.exit(2); });
