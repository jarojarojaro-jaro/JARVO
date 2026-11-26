# API sceny (silnikjava): co możesz napisać w `scena.js`

Scena to moduł ES z `export function zbuduj(glos)`, który zwraca `Storyboard`. Import zawsze z tego samego adresu co
strona (jedna kopia silnika): `import { Storyboard, rect, line, curve, ellipse, polyline, arc, star, svgPath, chain }
from '/_lib/silnikjava/src/index.js';`. `glos` to lektor z `rysowany.py glos` (albo `null`, gdy film jest bez lektora).
Czas kroku wynika z modelu ręki (długość kresek, przeloty, limit prędkości); `dur` podajesz tylko świadomie.
Pełny opis autora: `@@TOOLS_DIR@@/silnikjava/README.md`, kod pędzli `src/sketch.js`, ścieżek `src/paths.js`.

## Storyboard
`new Storyboard({ theme: 'chalk' })` = kadr 1280×720 (render 1920×1080); `{ format: 'reel', theme: 'neon' }` = rolka
720×1280 (render 1080×1920, strefa bezpieczna x 36 do 640, y 150 do 900). Opcje: `speed` (tempo ręki w px/s, np. 900
w rolce), `handGaps` (przerwa na przelot ręki, domyślnie tak), `idle` (`boil`: po końcu kreski dalej lekko drgają).

## Kroki (każdy robi ręka)
| Krok | Co robi | Ważne opcje |
|---|---|---|
| `sb.pen(ścieżka, o)` | kreska z naciskiem i drganiem | `color`, `w`, `seed`, `dash: [wł, wył]`, `sketchy`, `taper` |
| `sb.strokes([ścieżki], o)` | kilka kresek jedną ręką (podnosi narzędzie między nimi) | jak `pen` |
| `sb.arrow(ścieżka, o)` | trzon i dwa ramiona grota | `head`, `color`, `w` |
| `sb.crayon(wielokąt, o)` | zamalowanie kredką zygzakiem pod konturem | `color`, `alpha`, `spacing`, `w`, `angle` |
| `sb.fill(wielokąt, o)` | kryjące wypełnienie zakreślaczem | `color` |
| `sb.liquid(wielokąt, o)` | napełnianie od dołu z falą | `color`, `level` |
| `sb.highlight(ścieżka, szer, o)` | zakreślacz (mnożony) | `color` (`ochre` = żółty) |
| `sb.write(tekst, x, y, o)` | pismo odręczne kreskami liter (polskie znaki), `\n` = nowa linia | `size`, `font` (`hand`, `title`, `mono`), `align`, `color`, `fit` |
| `sb.dot(x, y, r, o)` | kropka małym kółkiem | `color` |
| `sb.pop(x, y, fn, o)` | wyskakuje z przestrzeleniem (efekt bez ręki: `magic`) | |
| `sb.custom(fn(sk, p, t), o)` | własny rysunek; ręka prowadzi go, gdy podasz `trace(p) => {x, y}` | `trace`, `dur` |
| `sb.camera({x, y, zoom}, {dur})` | najazd i zjazd kamery (środek kadru w jednostkach sceny) | `dur` (domyślnie 1,2 s) |
| `sb.clear()` | gąbka ściera tablicę pasami, zaczyna nowy rozdział (cięcie ujęcia w projekcie) | elementy z `keep: true` zostają |
| `sb.wait(s)`, `sb.mark(nazwa)` | pauza, znacznik czasu | |

Opcje czasu każdego kroku: `cue: 'słowo'` (kotwica do słowa lektora w bieżącym zdaniu, ręka dotyka kartki ok. 0,3 s
przed nim; `cueNth` = które wystąpienie), `at` (sekunda albo nazwa kroku), `with` (razem z krokiem), `after`, `gap`
(przesunięcie, może być ujemne), `name`, `keep`, `z` (warstwa), `pencil: false`. Świadome wyjątki: `ambient: true`
(ruch już narysowanego, np. para z kubka), `magic: true` (efekt bez ręki), `fast: true` (bez limitu prędkości),
`revisit: true` (fabularny powrót do obiektu).

## Lektor w scenie
```js
sb.say(glos.beat(1), () => {                       // zdanie 1 (beaty b1, b2… = zdania z narracji)
  sb.write('Jak działa agent?', 640, 120, { size: 64, font: 'title', align: 'center', cue: 'agent' });
  sb.pen(rect(520, 260, 240, 160), { color: 'ink', w: 4, cue: 'patrzy' });
});
glos.beats.slice(1).forEach((b, i) => sb.say(b, () => { /* jeden obiekt na zdanie */ }));
```
Głos zdania rusza 0,3 s po tym, jak ręka zacznie rysować; gdy rysunek nie zdąży na pierwszą kotwicę, silnik
przesuwa zdanie (najwyżej 1,5 s), a `rysowany.py film` układa nagranie lektora dokładnie tam. Następne zdanie
zaczyna się, gdy skończą się i głos, i rysunek. `glos.beat(n).words` to słowa zdania z czasem (`w`, `s`, `e`).
Opcje `say`: `lead` (0,3 s), `after` (pauza po zdaniu, 0,25 s), `maxWait` (1,5 s), `voiceWaits: false`.

## Ścieżki (`src/paths.js`)
`line(x1, y1, x2, y2, {bow, seed})`, `polyline(punkty, {closed, seed, overshoot})` (ostre rogi), `rect(x, y, w, h,
{seed, overshoot})`, `ellipse(cx, cy, rx, ry, {seed})`, `arc(cx, cy, r, a0, a1)`, `polygon(punkty, {wobble})`
(zaokrąglony szkic), `star(cx, cy, r1, r2, n)`, `wave(x1, y, x2, amp, freq)`, `spiral(cx, cy, r0, r1, obroty)`,
`curve([[x, y], …])` (gładka krzywa przez punkty), `svgPath('M…')` (rysunek z Figmy albo Inkscape jako ścieżka),
`chain([ścieżki])` (kolejność kresek z krótszymi przelotami ręki), `rotate`, `bounds`, `pointInPoly`.
Bryły 3D: `isoCamera({az, k, S, ox, oy})`, `iso.solid(cam, {x0, y0, x1, y1, z1, r})`, `iso.cylinder(cam, {x, y, R,
z1})`, `iso.visible(ścieżka, [sylwetki bliższych])` (zasady: rozdział 7 zasad rysownika, wzór `examples/scenes/styles/iso.js`).

## Kolory
Tylko nazwy z palety (scena działa wtedy w każdym stylu): `ink` (kontur), `inkSoft` (detale), `pen` (jeden akcent
filmu), `teal`, `sky`, `ochre`, `coral`, `plum`, `white`; styl przemalowuje je po swojemu (kreda, neon, tusz).

## Postać i własny rysunek
Przepis na postać (kontur `strokes`, zasłonięcie tła, kredka, detale, oddech i mruganie przez `ambient`):
`@@TOOLS_DIR@@/silnikjava/examples/scenes/mascot.js`. Wzory pełnych filmów: `examples/scenes/explainer.js` (kamera,
ścieranie), `examples/scenes/narrated.js` (lektor), `examples/scenes/styles/<id>.js` (21 stylów),
`examples/scenes/reels/<id>.js` (rolki: notebook, neon, comic).
