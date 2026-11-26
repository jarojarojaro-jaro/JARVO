# API sceny (silnikjava) dla `scena.js`

Scena to moduł ES z `export function zbuduj(glos)` zwracającym `Storyboard`; `glos` to wynik `rysowany.py glos` albo `null`.
Import zawsze: `import { Storyboard, rect, line, curve, ellipse, polyline, arc, star, svgPath, chain } from '/_lib/silnikjava/src/index.js';`.
Czas kroku liczy model ręki, więc `dur` podajesz tylko świadomie; pełny opis: `@@TOOLS_DIR@@/silnikjava/README.md`.

## Storyboard
`new Storyboard({ theme: 'chalk' })` to kadr 1280×720, a `{ format: 'reel', theme: 'neon' }` to rolka 720×1280 (strefa x 36 do 640, y 150 do 900).
Opcje: `speed` (px/s, np. 900 w rolce), `handGaps`, `idle: 'boil'`.

## Kroki
| Krok | Co robi | Opcje |
|---|---|---|
| `sb.pen(ścieżka, o)` | kreska | `color`, `w`, `seed`, `dash`, `sketchy`, `taper` |
| `sb.strokes([ścieżki], o)` | kilka kresek jedną ręką | jak `pen` |
| `sb.arrow(ścieżka, o)` | strzałka | `head`, `color`, `w` |
| `sb.crayon(wielokąt, o)` | zamalowanie kredką | `color`, `alpha`, `spacing`, `w`, `angle` |
| `sb.fill(wielokąt, o)` | kryjące wypełnienie | `color` |
| `sb.liquid(wielokąt, o)` | napełnianie od dołu | `color`, `level` |
| `sb.highlight(ścieżka, szer, o)` | zakreślacz | `color` |
| `sb.write(tekst, x, y, o)` | pismo odręczne, `\n` nowa linia | `size`, `font` (`hand`, `title`, `mono`), `align`, `color`, `fit` |
| `sb.dot(x, y, r, o)` | kropka | `color` |
| `sb.pop(x, y, fn, o)` | wyskok (z `magic`) | |
| `sb.custom(fn(sk, p, t), o)` | własny rysunek | `trace(p) => {x, y}`, `dur` |
| `sb.camera({x, y, zoom}, {dur})` | najazd i zjazd | `dur` (1,2 s) |
| `sb.clear()` | gąbka ściera tablicę i tnie ujęcie | `keep: true` zostaje |
| `sb.wait(s)`, `sb.mark(nazwa)` | pauza, znacznik | |

Opcje czasu: `cue: 'słowo'` (`cueNth`), `at`, `with`, `after`, `gap`, `name`, `keep`, `z`, `pencil: false`.
Wyjątki od ręki: `ambient: true`, `magic: true`, `fast: true`, `revisit: true`.

## Lektor
```js
sb.say(glos.beat(1), () => {
  sb.write('Jak działa agent?', 640, 120, { size: 64, font: 'title', align: 'center', cue: 'agent' });
  sb.pen(rect(520, 260, 240, 160), { color: 'ink', w: 4, cue: 'patrzy' });
});
glos.beats.slice(1).forEach((b, i) => sb.say(b, () => { /* jeden obiekt na zdanie */ }));
```
Gdy rysunek nie zdąży na pierwszą kotwicę, silnik przesuwa zdanie najwyżej o 1,5 s, a `rysowany.py film` układa tam nagranie.
`glos.beat(n).words` to słowa z czasem (`w`, `s`, `e`); opcje `say`: `lead`, `after`, `maxWait`, `voiceWaits: false`.

## Ścieżki
`line(x1, y1, x2, y2, {bow, seed})`, `polyline(punkty, {closed, seed, overshoot})`, `rect(x, y, w, h, {seed, overshoot})`, `ellipse(cx, cy, rx, ry, {seed})`, `arc(cx, cy, r, a0, a1)`, `polygon(punkty, {wobble})`, `star(cx, cy, r1, r2, n)`, `wave(x1, y, x2, amp, freq)`, `spiral(cx, cy, r0, r1, obroty)`, `curve([[x, y], …])`, `svgPath('M…')`, `chain([ścieżki])`, `rotate`, `bounds`, `pointInPoly`.
Bryły 3D: `isoCamera({az, k, S, ox, oy})`, `iso.solid(cam, {x0, y0, x1, y1, z1, r})`, `iso.cylinder(cam, {x, y, R, z1})`, `iso.visible(ścieżka, [sylwetki])`; wzór `examples/scenes/styles/iso.js`.

## Kolory
Tylko paleta: `ink`, `inkSoft`, `pen` (jeden akcent), `teal`, `sky`, `ochre`, `coral`, `plum`, `white`.

## Wzory
Postać: `@@TOOLS_DIR@@/silnikjava/examples/scenes/mascot.js`; kamera i ścieranie: `examples/scenes/explainer.js`; lektor: `examples/scenes/narrated.js`; rolki: `examples/scenes/reels/<id>.js`.
