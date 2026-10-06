// Polska nakładka na silnik huashu-art-motion (MIT, 花叔 / alchaincyf) w kontrakcie HTML Jarva (`--preset jarvo`).
// Ładujesz ją po bibliotekach silnika, a przed clip.js / engine.js i własnym kodem strony:
//
//   <script src="/_lib/huashu/lib/fonts.js"></script>  … pozostałe /_lib/huashu/lib/*.js …
//   <script src="/_lib/jarvo/huashu_pl.js"></script>
//   <script>window.CLIP_SPEC = {…}</script><script src="/_lib/huashu/clip.js"></script>
//
// (silnik instaluje `narzedzia.py instaluj huashu`; html_wideo.py i podgląd HQ serwują go pod /_lib/huashu/)
// Co robi:
// 1. kroje: adresy FONT_FACES względem /_lib/huashu/ (window.HUASHU_BASE), a kroje bez polskich znaków (chińskie
//    PuHui/Noto Sans SC, pismo LXGW, Gochi Hand, Lilita One, Rye, Unifraktur, Noto Serif JP) podmienione na kroje
//    z tej samej paczki silnika, które mają ą–ż; nazwa rodziny zostaje, więc kod stylów i gramatyk się nie zmienia;
// 2. liczby po polsku: TY.fmt z przecinkiem dziesiętnym, twardą spacją tysięcy od 5 cyfr i znakiem minus „−”;
// 3. napisy wpisane w kod silnika („示意数据” itd.) po polsku, także przy pomiarze szerokości (measureText);
//    szary źródła pod wykresem ciemniejszy (#5f696e, 5,6:1 na bieli zamiast 3,7:1);
// 4. postać gramatyki historyjki (TOON.bean) neutralna: włosy zamiast kapelusza, bez okularów i zegarka autora,
//    kolory z window.POSTAC (marka klienta) albo spokojne domyślne;
// 5. kontrakt Jarva: window.__seek(t) (prepare + renderFrame), __W/__H z rozmiaru klipu, __teksty() z tekstu
//    rysowanego na kanwie filmu (fillText/strokeText, znaki jednej linii sklejone), błąd startu silnika jako błąd JS
//    (render przerywa się od razu, z powodem), plik gramatyki clips/<nazwa>.js z /_lib/huashu/.
(() => {
  const W = typeof window !== 'undefined' ? window : globalThis;
  const BAZA = () => W.HUASHU_BASE || '/_lib/huashu/';

  // ---------- 1. kroje ----------
  // rodzina silnika → kroje z polskimi znakami z lib/fonts/ (sprawdzone tablicą cmap); grubości przez opis FontFace
  const PODMIANY = {
    'PuHui-Medium': [['Inter-var.woff', { weight: '500' }]],
    'PuHui-Bold': [['Inter-var.woff', { weight: '700' }]],
    'PuHui-Heavy': [['Inter-var.woff', { weight: '800' }]],
    'PuHui-Black': [['Inter-var.woff', { weight: '900' }]],
    'NotoSansSC': [['Inter-var.woff', { weight: '100 900' }]],
    'NotoSerifSC': [['EBGaramond-400.woff', { weight: '100 500' }], ['EBGaramond-600.woff', { weight: '600 900' }]],
    'LXGWWenKai-500': [['Caveat-600.woff', {}]],
    'GochiHand-400': [['Caveat-600.woff', {}]],
    'LilitaOne-400': [['Poppins-800.woff', {}]],
    'Rye-400': [['AlfaSlabOne-400.woff', {}]],
    'UnifrakturMaguntia-400': [['IMFellEnglish-400.woff', {}]],
    'NotoSerifJP-600': [['CormorantGaramond-700.woff', {}]],
  };
  const adres = (url, baza) => (/^(data:|https?:|\/)/.test(url) ? url : baza + url);
  function fonty(lista, baza = BAZA()) {
    const out = [];
    for (const f of lista || []) {
      const zam = PODMIANY[f.family];
      if (zam) for (const [plik, desc] of zam) out.push({ family: f.family, url: baza + 'lib/fonts/' + plik, desc, pl: true });
      else out.push({ ...f, url: adres(f.url, baza) });
    }
    return out;
  }

  // ---------- 2. liczby ----------
  function fmt(v, dec = 0, sep = true) {
    const s = Math.abs(v).toFixed(dec);
    const [i, f] = s.split('.');
    const ii = sep && i.length >= 5 ? i.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') : i;
    return (v < 0 && +s !== 0 ? '−' : '') + ii + (f ? ',' + f : '');
  }

  // ---------- 3. napisy z kodu silnika ----------
  const SLOWNIK = [
    ['来源：示意数据', 'Źródło: dane przykładowe'],
    ['示意数据', 'dane przykładowe'],
    ['纵轴未从 0 开始', 'oś Y nie zaczyna się od 0'],
    ['AI助手', 'Asystent AI'],
    ['？', '?'],
    ['！', '!'],
    ['　', ' '],
  ];
  const CJK = /[　-〿㐀-鿿＀-￯]/;
  function pl(s) {
    if (typeof s !== 'string' || !CJK.test(s)) return s;
    for (const [a, b] of SLOWNIK) if (s.includes(a)) s = s.split(a).join(b);
    return s;
  }

  // ---------- 5. tekst kanwy dla pomiaru ----------
  // znaki rysowane osobno (liczniki TY.tabular, pisanie po literze) sklejamy w jedną linię: ten sam krój, kolor
  // i krycie, ta sama linia bazowa, kolejny znak tuż za poprzednim; kontur i wypełnienie tego samego tekstu = jeden
  function scal(zapis) {
    const grupy = [];
    for (const q of zapis) {
      const r = q.rozmiar || 16;
      const g = grupy.find((x) => x.font === q.font && x.kolor === q.kolor && Math.abs(x.krycie - q.krycie) < 0.05
        && Math.abs(x.by - q.by) <= 0.2 * r && ((q.x0 - x.x1 >= -0.35 * r && q.x0 - x.x1 <= 0.6 * r)
          || (x.ostatni === q.tekst && Math.abs(x.ox0 - q.x0) < 2 && Math.abs(x.y0 - q.y0) < 2 + 0.2 * r)));
      if (!g) { grupy.push({ ...q, ox0: q.x0, ostatni: q.tekst }); continue; }
      if (g.ostatni === q.tekst && Math.abs(g.ox0 - q.x0) < 2) continue;          // ten sam tekst drugi raz (kontur)
      // cyfry o stałej szerokości (TY.tabular: każda w swojej komórce) mają odstępy szersze niż litery: to wciąż jedna liczba
      const liczba = /[\d.,\u00a0−-]$/.test(g.tekst) && /^[\d.,%]/.test(q.tekst);
      g.tekst += (q.x0 - g.x1 > 0.18 * r && !liczba && !/^\s/.test(q.tekst) ? ' ' : '') + q.tekst;
      g.x0 = Math.min(g.x0, q.x0); g.y0 = Math.min(g.y0, q.y0); g.x1 = Math.max(g.x1, q.x1); g.y1 = Math.max(g.y1, q.y1);
      g.ox0 = q.x0; g.ostatni = q.tekst;
    }
    // cień albo obwódka w innym kolorze: ten sam tekst i krój, przesunięty najwyżej o 0,2 kroju, narysowany wcześniej (pod spodem)
    const cien = (g, i) => grupy.some((h, j) => j > i && h.tekst === g.tekst && h.font === g.font && h.kolor !== g.kolor
      && Math.abs(h.x0 - g.x0) <= 0.2 * (g.rozmiar || 16) && Math.abs(h.y0 - g.y0) <= 0.2 * (g.rozmiar || 16));
    return grupy.filter((g, i) => g.tekst.trim() && !cien(g, i)).map((g) => ({
      tekst: g.tekst, x: Math.round(g.x0 * 10) / 10, y: Math.round(g.y0 * 10) / 10,
      w: Math.round((g.x1 - g.x0) * 10) / 10, h: Math.round((g.y1 - g.y0) * 10) / 10,
      kolor: g.kolor || undefined, rozmiar: Math.round(g.rozmiar * 10) / 10, krycie: g.krycie, font: g.rodzina,
      waga: g.waga, klucz: g.font.replace(/[\d.]+px/, '#px') + '|' + g.kolor,     // napis rosnący przy wejściu to ten sam napis
    }));
  }

  // rodzina i grubość z ctx.font („bold 58px PuHui-Bold”, '96px "Cinzel-700", serif') dla kontroli krojów pomiaru
  const rodzinaZ = (f) => { const m = /[\d.]+px(?:\/\S+)?\s+(.+)$/.exec(f); return (m ? m[1] : f).split(',')[0].trim().replace(/^["']|["']$/g, ''); };
  const wagaZ = (f) => { const m = /(?:^|\s)(bold|[1-9]00)(?=\s)/.exec(f); return m ? (m[1] === 'bold' ? 700 : +m[1]) : 400; };

  // ten sam napis w kolejnych próbkach pomiaru dostaje to samo id (pomiar liczy czas czytania po id): ten sam krój
  // i kolor (bez rozmiaru), liczby zwinięte do „#” (licznik 8,9 → 130,5 to jeden napis), a tekst pisany po literze
  // (z kursorem „|” na końcu albo bez) to ten sam napis, dopóki jeden jest początkiem drugiego. Położenie się nie liczy: napis wjeżdżający z boku to wciąż ten sam napis.
  function nadajId(lista, pamiec) {
    const uzyte = new Set();
    return lista.map((q) => {
      const t = q.tekst.replace(/[−-]?\d[\d\u00a0 .,]*/g, '#').replace(/[|▌▍_]+$/, '').trim();   // bez kursora pisania
      let m = pamiec.find((p) => p.klucz === q.klucz && !uzyte.has(p.id) && (p.t.startsWith(t) || t.startsWith(p.t)));
      if (!m) { m = { id: 'k' + (pamiec.length + 1), klucz: q.klucz, t }; pamiec.push(m); } else if (t.length > m.t.length) m.t = t;
      uzyte.add(m.id);
      const { klucz, ...reszta } = q;
      return { ...reszta, id: m.id };
    });
  }

  // ---------- 4. postać ----------
  const POSTAC_DOMYSLNA = { skora: '#F2C9A6', linia: '#1B1B1F', wlosy: '#4A3426', koszulka: '#3D6FA8',
    spodnie: '#2F3640', buty: '#FAFAF6' };
  const postac = () => ({ ...POSTAC_DOMYSLNA, ...(W.POSTAC || {}) });

  // rysunek za TOON.bean z lib/toon.js (MIT, 花叔): ta sama budowa, pozy, mimika i usta; zamiast kapelusza, okularów
  // i zegarka autora zwykłe włosy z grzywką i oczy bez oprawek. Te same argumenty i ten sam wynik ({hl, hr, head}).
  function bean(c, o) {
    const P = postac(), LINE = P.linia, SK = P.skora;
    const lerp = (a, b, k) => a + (b - a) * k;
    const R = o.s, x = o.x, y = o.y, lw = o.lw || Math.max(4, R * 0.05), sq = o.squash || 1;
    const pose = o.pose || W.TOON.POSES.rest;
    c.save(); c.translate(x, y); c.scale(1 / Math.sqrt(sq), sq);
    c.lineJoin = 'round'; c.lineCap = 'round'; c.strokeStyle = LINE; c.lineWidth = lw;
    const bodyTop = -R * 1.32;
    const shoulderY = bodyTop + R * 0.32, shL = [-R * 0.42, shoulderY], shR = [R * 0.42, shoulderY];
    for (const sx of [-1, 1]) {                                         // nogi w spodniach + buty
      c.fillStyle = P.spodnie; c.beginPath(); c.roundRect(sx * R * 0.2 - R * 0.09, -R * 0.24, R * 0.18, R * 0.2, R * 0.05); c.fill(); c.stroke();
      c.fillStyle = P.buty; c.beginPath(); c.ellipse(sx * R * 0.22, -R * 0.03, R * 0.17, R * 0.08, 0, 0, Math.PI * 2); c.fill(); c.stroke();
    }
    const body = new Path2D();
    body.moveTo(-R * 0.5, -R * 0.2);
    body.bezierCurveTo(-R * 0.62, -R * 0.75, -R * 0.55, bodyTop + R * 0.05, 0, bodyTop);
    body.bezierCurveTo(R * 0.55, bodyTop + R * 0.05, R * 0.62, -R * 0.75, R * 0.5, -R * 0.2);
    body.bezierCurveTo(R * 0.3, -R * 0.12, -R * 0.3, -R * 0.12, -R * 0.5, -R * 0.2); body.closePath();
    c.fillStyle = P.koszulka; c.fill(body);
    c.save(); c.clip(body); c.fillStyle = P.spodnie; c.fillRect(-R, -R * 0.42, R * 2, R * 0.5);
    c.strokeStyle = LINE; c.lineWidth = lw * 0.6; c.beginPath(); c.moveTo(0, -R * 0.36); c.lineTo(0, -R * 0.12); c.stroke(); c.restore();
    c.stroke(body);
    c.beginPath(); c.moveTo(-R * 0.6, -R * 0.42); c.quadraticCurveTo(0, -R * 0.36, R * 0.6, -R * 0.42); c.lineWidth = lw * 0.8; c.stroke(); c.lineWidth = lw;
    const arm = (sh, tgt, side) => {
      const hx = sh[0] + tgt[0] * R * 0.62, hy = sh[1] + tgt[1] * R * 0.62;
      const mx = (sh[0] + hx) / 2 + side * R * 0.08, my = Math.max(sh[1], hy) + R * 0.12;
      c.beginPath(); c.moveTo(sh[0], sh[1]); c.quadraticCurveTo(mx, my, hx, hy);
      c.strokeStyle = LINE; c.lineWidth = R * 0.17 + lw; c.stroke(); c.strokeStyle = SK; c.lineWidth = R * 0.17; c.stroke();
      c.beginPath(); c.moveTo(sh[0], sh[1]); const q = 0.28; c.lineTo(lerp(sh[0], mx, q * 2), lerp(sh[1], my, q * 2));
      c.strokeStyle = LINE; c.lineWidth = R * 0.26 + lw; c.stroke(); c.strokeStyle = P.koszulka; c.lineWidth = R * 0.26; c.stroke();
      c.fillStyle = SK; c.strokeStyle = LINE; c.lineWidth = lw; c.beginPath(); c.arc(hx, hy, R * 0.13, 0, Math.PI * 2); c.fill(); c.stroke();
      return [hx, hy];
    };
    c.lineWidth = lw;
    const hl = arm(shL, pose.l, -1), hr = arm(shR, pose.r, 1);
    c.restore(); c.save(); c.translate(x, y); c.scale(1 / Math.sqrt(sq), sq);
    c.lineJoin = 'round'; c.lineCap = 'round'; c.strokeStyle = LINE; c.lineWidth = lw;
    const hy = bodyTop - R * 0.78 + (o.bob || 0);
    c.translate(0, hy); c.rotate(o.tilt || 0);
    c.fillStyle = P.wlosy;                                              // włosy za uszami
    for (const sx of [-1, 1]) { c.beginPath(); c.ellipse(sx * R * 0.88, -R * 0.2, R * 0.15, R * 0.32, sx * 0.2, 0, Math.PI * 2); c.fill(); }
    c.fillStyle = SK; c.beginPath(); c.ellipse(0, 0, R * 1.0, R * 0.93, 0, 0, Math.PI * 2); c.fill(); c.stroke();
    const hair = new Path2D();                                          // włosy z grzywką (zamiast kapelusza)
    hair.moveTo(-R * 1.02, -R * 0.05);
    hair.bezierCurveTo(-R * 1.08, -R * 1.32, R * 1.08, -R * 1.32, R * 1.02, -R * 0.05);
    hair.quadraticCurveTo(R * 0.86, -R * 0.42, R * 0.45, -R * 0.42);
    hair.quadraticCurveTo(R * 0.12, -R * 0.38, -R * 0.04, -R * 0.56);
    hair.quadraticCurveTo(-R * 0.38, -R * 0.36, -R * 0.8, -R * 0.4);
    hair.quadraticCurveTo(-R * 0.98, -R * 0.3, -R * 1.02, -R * 0.05);
    hair.closePath();
    c.fillStyle = P.wlosy; c.fill(hair); c.stroke(hair);
    const ex = o.expr || 'talk', lk = o.look || [0, 0];
    const brow = { talk: [0, 0], happy: [-0.05, 0.03], blank: [0.03, 0], worry: [-0.02, -0.11], shock: [-0.11, 0.02] }[ex] || [0, 0];
    if (o.browUp) brow[0] -= o.browUp;
    c.lineWidth = lw * 1.4;
    for (const sx of [-1, 1]) { const by = -R * 0.13 + brow[0] * R; c.beginPath(); c.moveTo(sx * R * 0.52, by); c.lineTo(sx * R * 0.2, by + brow[1] * R); c.stroke(); }
    c.lineWidth = lw;
    const gy = R * 0.16;                                                // oczy bez oprawek
    for (const sx of [-1, 1]) {
      const gx = sx * R * 0.35;
      const pr = ex === 'blank' ? R * 0.035 : ex === 'shock' ? R * 0.05 : R * 0.075;
      c.fillStyle = LINE;
      if (o.blink) { c.beginPath(); c.moveTo(gx - R * 0.08 + lk[0] * R * 0.08, gy + lk[1] * R * 0.06); c.lineTo(gx + R * 0.08 + lk[0] * R * 0.08, gy + lk[1] * R * 0.06); c.lineWidth = lw; c.stroke(); }
      else {
        c.beginPath(); c.ellipse(gx + lk[0] * R * 0.09, gy + lk[1] * R * 0.07, pr, pr * (ex === 'blank' ? 1 : 1.25), 0, 0, Math.PI * 2); c.fill();
        if (ex !== 'blank') { c.fillStyle = '#fff'; c.beginPath(); c.arc(gx + lk[0] * R * 0.09 - pr * 0.35, gy + lk[1] * R * 0.07 - pr * 0.45, pr * 0.32, 0, Math.PI * 2); c.fill(); }
      }
    }
    c.fillStyle = 'rgba(255,140,120,0.35)'; for (const sx of [-1, 1]) { c.beginPath(); c.ellipse(sx * R * 0.68, R * 0.5, R * 0.11, R * 0.06, 0, 0, Math.PI * 2); c.fill(); }
    const m = o.mouth || 0, my = R * 0.6;
    c.strokeStyle = LINE; c.lineWidth = lw;
    if (ex === 'blank' && !m) { c.beginPath(); c.moveTo(-R * 0.1, my); c.lineTo(R * 0.1, my); c.stroke(); }
    else if (ex === 'worry' && !m) { c.beginPath(); c.moveTo(-R * 0.13, my + R * 0.03); c.quadraticCurveTo(-R * 0.05, my - R * 0.04, 0, my + R * 0.01); c.quadraticCurveTo(R * 0.06, my + R * 0.05, R * 0.13, my - R * 0.01); c.stroke(); }
    else if (!m) { c.beginPath(); c.moveTo(-R * 0.13, my - R * 0.02); c.quadraticCurveTo(0, my + R * 0.1, R * 0.13, my - R * 0.02); c.stroke(); }
    else {
      const mh = m === 1 ? R * 0.1 : R * 0.2, mw = m === 1 ? R * 0.14 : R * 0.18;
      c.fillStyle = '#6E2430'; c.beginPath(); c.moveTo(-mw, my - R * 0.03); c.quadraticCurveTo(0, my - R * 0.06, mw, my - R * 0.03); c.quadraticCurveTo(mw * 0.9, my + mh, 0, my + mh); c.quadraticCurveTo(-mw * 0.9, my + mh, -mw, my - R * 0.03); c.closePath(); c.fill();
      c.save(); c.clip(); c.fillStyle = '#F07B7B'; c.beginPath(); c.ellipse(0, my + mh, mw * 0.6, mh * 0.45, 0, 0, Math.PI * 2); c.fill(); c.restore(); c.stroke();
    }
    c.restore();
    return { hl, hr, head: [x, y + hy * sq] };
  }

  // gramatyka historyjki rysuje też postać od tyłu (głowa przez ramię widza) wprost w swoim kodzie: kapelusz autora
  // i biała koszulka. Łatka podmienia ten fragment przy wczytaniu clips/y4_storytime.js (commit przypięty
  // w narzedzia.py); gdy kod się zmieni i fragment nie pasuje, strona rzuca błąd, zamiast pokazać postać autora
  const P_ = 'window.HUASHU_PL.postac()';
  const ZRODLO = '#5f696e';                      // 5,6:1 na bieli (WCAG AA dla małego tekstu)
  const LATKI = {
    y4_storytime: [
      ["c.fillStyle = '#FFFFFF'; c.beginPath(); c.ellipse(0, 300, 330, 200, 0, Math.PI, 0);",
        `c.fillStyle = ${P_}.koszulka; c.beginPath(); c.ellipse(0, 300, 330, 200, 0, Math.PI, 0);`],
      ["c.fillStyle = '#FFE2CC'; c.beginPath(); c.roundRect(-70, 120, 140, 110, 30);",
        `c.fillStyle = ${P_}.skora; c.beginPath(); c.roundRect(-70, 120, 140, 110, 30);`],
      ["c.fillStyle = '#1B1B1F'; c.beginPath(); c.ellipse(0, 40, 190, 175, 0, 0, 7); c.fill();",
        `c.fillStyle = ${P_}.wlosy; c.beginPath(); c.ellipse(0, 40, 190, 175, 0, 0, 7); c.fill(); c.stroke();`],
      ["c.fillStyle = '#FFFFFF'; c.beginPath(); c.moveTo(-180, -20); c.bezierCurveTo(-180, -290, 180, -290, 180, -20); c.closePath(); c.fill(); c.stroke();", ''],
      ["c.beginPath(); c.ellipse(0, -12, 280, 64, 0, 0, 7); c.fill(); c.stroke();", ''],
    ],
    // 3b1b: podział tekstu na tokeny wzoru (tokeny niżej) zamiast angielskiego [A-Za-z]{2,}
    // wykresy: źródło pod wykresem #7c868b na bieli ma 3,7:1 (pomiar: kontrast poniżej 4,5:1); ten sam szary ciemniej
    t3_finance_chart: [["c.fillStyle = '#7c868b';", `c.fillStyle = '${ZRODLO}';`]],
    t1_3b1b: [
      ["const toks = text => (String(text).match(/[A-Za-z]{2,}|./gu) || []).flatMap(s => s.length > 1 && !/[a-z]/.test(s) ? [...s] : [s])   // 全大写的一串（QK）是几个变量，拆开\n  .map(s => ({ s, zh: isZh(s), it: /^[a-zA-Z]$/.test(s), gap: 0 }));",
        "const toks = text => window.HUASHU_PL.tokeny(String(text)).map(([s, it]) => ({ s, zh: isZh(s), it, gap: 0 }));"],
    ],
  };

  // gramatyka 3b1b składa tekst z tokenów wzoru: słowo (≥ 2 litery) prostym krojem, pojedyncza litera kursywą jak
  // zmienna. Oryginał zna tylko [A-Za-z], więc „słowa” rozpada się na „s” (kursywa), „ł”, „owa”, a „w”, „z”, „i”
  // to zmienne. Tu słowem jest każdy ciąg liter łacińskich (z ą–ż), skróty wielkimi literami (AI, VAT) zostają
  // słowem, a jednoliterowe a, i, o, u, w, z przed słowem są spójnikiem. Macierze (QK) podajesz w data.tokens.
  function tokeny(tekst) {
    const a = String(tekst).match(/\p{Script=Latin}{2,}|./gu) || [];
    return a.map((s, i) => {
      let it = /^\p{Script=Latin}$/u.test(s);
      if (it && /^[aiouwzAIOUWZ]$/.test(s) && (i === 0 || a[i - 1] === ' ')) {
        let j = i + 1;
        while (a[j] === ' ') j++;
        if (j > i + 1 && a[j] && a[j].length > 1) it = false;
      }
      return [s, it];
    });
  }
  function latka(nazwa, kod) {
    for (const [a, b] of LATKI[nazwa] || []) {
      if (!kod.includes(a)) throw new Error(`huashu_pl: łatka ${nazwa} nie pasuje do kodu silnika (${a.slice(0, 60)}…)`);
      kod = kod.split(a).join(b);
    }
    return kod;
  }

  W.HUASHU_PL = { fonty, fmt, pl, scal, nadajId, rodzinaZ, wagaZ, postac, latka, tokeny, PODMIANY, SLOWNIK, ZRODLO };
  if (typeof document === 'undefined') return;                         // node (testy): same czyste funkcje

  // ---------- podpięcie w przeglądarce ----------
  if (W.FONT_FACES) W.FONT_FACES = fonty(W.FONT_FACES);
  if (W.TY) W.TY.fmt = fmt;
  if (W.CH && W.CH.bars) { const bars = W.CH.bars; W.CH.bars = (c, d, yS, bw, p, o = {}) => bars(c, d, yS, bw, p, { fmt: (v) => fmt(v, 0), ...o }); }
  if (W.TOON && W.TOON.bean) W.TOON.bean = bean;
  if (W.CH && W.CH.frame) { const frame = W.CH.frame; W.CH.frame = (c, lt, o = {}) => frame(c, lt, { srcCol: ZRODLO, ...o }); }

  // gramatyka clips/<nazwa>.js: clip.js pobiera ją adresem względnym (strona filmu leży w katalogu projektu)
  // synchronicznym XHR i wykonuje responseText; tu adres z /_lib/huashu/ i łatki postaci
  const XHR = XMLHttpRequest.prototype, open0 = XHR.open, tekst0 = Object.getOwnPropertyDescriptor(XHR, 'responseText').get;
  XHR.open = function (m, url, ...r) {
    const g = typeof url === 'string' && /^clips\/([a-z0-9_]+)\.js$/.exec(url);
    if (g && LATKI[g[1]]) {
      const xhr = this;
      Object.defineProperty(xhr, 'responseText', { configurable: true, get: () => latka(g[1], tekst0.call(xhr)) });
    }
    return open0.call(this, m, g ? BAZA() + url : url, ...r);
  };

  const ZAPIS = [];
  let skala = { x: 0, y: 0, sx: 1, sy: 1 };
  const nowaKlatka = () => {
    ZAPIS.length = 0;
    const cv = W.__canvas;
    if (cv && cv.width) { const b = cv.getBoundingClientRect(); skala = { x: b.left, y: b.top, sx: b.width / cv.width || 1, sy: b.height / cv.height || 1 }; }
  };
  const C2D = CanvasRenderingContext2D.prototype, fill0 = C2D.fillText, stroke0 = C2D.strokeText, measure0 = C2D.measureText;
  const zapisz = (ctx, s, x, y, styl) => {
    if (ctx.canvas !== W.__canvas || !String(s).trim() || ctx.globalAlpha < 0.02
      || String(ctx.globalCompositeOperation).startsWith('destination')) return;
    const m = measure0.call(ctx, s), t = ctx.getTransform();
    const xs = [x - m.actualBoundingBoxLeft, x + m.actualBoundingBoxRight], ys = [y - m.actualBoundingBoxAscent, y + m.actualBoundingBoxDescent];
    const px = [], py = [];
    for (const a of xs) for (const b of ys) { px.push((t.a * a + t.c * b + t.e) * skala.sx + skala.x); py.push((t.b * a + t.d * b + t.f) * skala.sy + skala.y); }
    const r = /([\d.]+)px/.exec(ctx.font);
    ZAPIS.push({ tekst: String(s), x0: Math.min(...px), x1: Math.max(...px), y0: Math.min(...py), y1: Math.max(...py),
      by: (t.b * x + t.d * y + t.f) * skala.sy + skala.y, font: ctx.font, rodzina: rodzinaZ(ctx.font), waga: wagaZ(ctx.font),
      kolor: typeof styl === 'string' ? styl : null, krycie: ctx.globalAlpha,
      rozmiar: (r ? +r[1] : 16) * Math.hypot(t.c, t.d) * skala.sy });
  };
  C2D.measureText = function (s, ...r) { return measure0.call(this, pl(s), ...r); };
  C2D.fillText = function (s, x, y, ...r) { s = pl(s); zapisz(this, s, x, y, this.fillStyle); return fill0.call(this, s, x, y, ...r); };
  C2D.strokeText = function (s, x, y, ...r) { s = pl(s); zapisz(this, s, x, y, this.strokeStyle); return stroke0.call(this, s, x, y, ...r); };

  // każda klatka (renderFrame z clip.js / engine.js, renderSolo wzoru stylu) zaczyna zapis tekstu od nowa
  for (const nazwa of ['renderFrame', 'renderSolo']) {
    let f = W[nazwa];
    Object.defineProperty(W, nazwa, { configurable: true, get: () => f,
      set: (g) => { f = typeof g === 'function' ? function (...a) { nowaKlatka(); return g.apply(this, a); } : g; } });
  }
  const PAMIEC = [];
  if (typeof W.__teksty !== 'function') W.__teksty = () => nadajId(scal(ZAPIS), PAMIEC);
  if (typeof W.__seek !== 'function') W.__seek = async (t) => { if (W.prepare) await W.prepare(t); W.renderFrame(t); };
  for (const [k, i] of [['__W', 0], ['__H', 1]]) {
    Object.defineProperty(W, k, { configurable: true, get: () => (W.__size || [1920, 1080])[i],
      set: (v) => Object.defineProperty(W, k, { value: v, writable: true, configurable: true }) });
  }
  // clip.js / engine.js łapią swój błąd startu (window.__bootFailed + console.error): rzucamy go dalej, żeby render
  // przerwał się od razu z powodem, a nie po minucie czekania na __ready
  let blad;
  Object.defineProperty(W, '__bootFailed', { configurable: true, get: () => blad,
    set: (v) => { blad = v; if (v) setTimeout(() => { throw new Error('huashu: ' + String(v).slice(0, 400)); }); } });
})();
