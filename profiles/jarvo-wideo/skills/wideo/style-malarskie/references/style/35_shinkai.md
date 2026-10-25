# Światło Makoto Shinkaia (`35_shinkai`)

Japońska animacja kinowa z 2016 roku: prawie fotograficzne tło, niebo z wielkimi chmurami cumulonimbus, snopy
światła (efekt Tyndalla), postać rysunkowa z twardymi pasmami cienia i jasną obwódką od światła (cel-shading), flara
obiektywu, poświata (bloom) i drobinki światła w powietrzu. Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną
słabością); słabość wzoru: tło we wnętrzu ma za mało szczegółów (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 35_shinkai --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-35_shinkai.jpg`;
kod `$HUASHU/scripts/engine/scenes/35_shinkai.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Marka lifestyle, turystyka, nieruchomości „z widokiem”, uczelnia: 15–45 s, emocjonalnie, z muzyką.
- Teledysk, lyric video, zapowiedź premiery: pętle 8–15 s.
- Kampania o lecie, młodości, marzeniach; film rekrutacyjny: 30 s.

## Nie do
- Mroczny, kameralny nastrój: `32_rembrandt` albo `24_hopper`.
- Pełne anime z ruchem postaci i dialogami: `lemo-opuscar` (`film-z-kodu`), styl anime.
- Akwarelowe tło w stylu Ghibli: `25_ghibli`.

## Cechy stylu (sprawdzalne)
- Cel-shading `cel(c, p, base, shade, rim, {sd, rw, lx, ly})` (w bibliotece `PAINT.cel`, domyślnie `sd = 22`,
  `rw = 7`, `line = '#6a4632'`, `lw = 2.2`, `lx = -1`, `ly = -0.55`):
  - cień = `clip(p) ∩ ¬(p przesunięte o (lx·sd, ly·sd))`; robisz to `evenodd` (duży prostokąt + przesunięte p) jako
    `clip`;
  - jasna obwódka = `clip(p) ∩ ¬(p przesunięte w przeciwną stronę o rw)`;
  - światło od okna lx=−1, ly=−0.55, więc cień ląduje z prawej u dołu. sd: duże części 22–30, twarz 10, małe 8;
    rw 3–9;
  - linia `#6a4632`, 2,2 px. Części po kolei „wypełnij → cień → obwódka → linia”; zasłanianie wychodzi samo,
    `visibleLines` niepotrzebne.
- Kot pod oknem pod światło: lx=0.5, ly=1 (cień na dole), na głowie i grzbiecie ciepła obwódka `lighter`
  rgba(255,220,160,.55).
- Kolory postaci: skóra `#ffe8dc` / `#f2b6a8`; blond `#f8d681` / `#d8a050`; biały mundurek `#fbfbfe` / `#b9c3dc`;
  granat `#2c3a66` / `#1b2446`. „Aureola” na włosach: jasny łuk 9 px rgba(255,250,226,.85) na tyle głowy.
- Oczy anime: biel 8×12, tęczówka w pionowym gradiencie `#1f3f7a → #3f7fd0 → #9fd4ff`, dwa odblaski, górna powieka
  3,4 px i jedna rzęsa w kąciku.
- Cumulonimbus: 70+12 kłębów.
  1. Wszystkie kłęby jako niebiesko-szara sylwetka (gradient liniowy `#b7c6e6 → #8297c6`).
  2. W każdym kłębie, przesunięta ku słońcu o (+0.22r, −0.3r), biała radialna kula 0.82r.
  3. Cała warstwa rozmyta 3 px, na nią 55% ostrej warstwy.
- Flara (`PAINT.lensFlare(c, sun, t)`): rdzeń r130; 10 promieni długości 90/170, obrót 0,25 rad/s; pozioma smuga
  840×4; 5 sześciokątnych plam na linii słońce → środek kadru w 0.45/0.75/1.25/1.6/2.0 tej odległości, α 0.04–0.12.
- Tyndall: 3 kliny, blur 18 px, w cache, `screen`, α `0.75 + 0.25·sin(3.4t)`. 60 drobin światła (radialny gradient,
  migotanie).
- Bloom (`PAINT.bloom`): cała klatka do płótna 480×270 → blur 6 px, brightness 1.1 → `screen` α0.28 z powrotem
  w pełnym rozmiarze.
- Na końcu `soft-light` z rozdziałem ciepłe/zimne.
- Krój plakietki we wzorze: `Poppins-600`; ma polskie znaki.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 35_shinkai`. `P` = `PAINT`
   (`paint.js`, `render.js` z `P.cel`, `post.js` z `P.lensFlare`/`P.bloom`), `RIG`.
2. Realistyczne wnętrze (ściana z gradientem ciepło-zimnym, perspektywiczne szczeliny podłogi z odbiciem, aluminiowa
   rama okna, kalendarz, biurko) raz do cache (`sk_room`).
3. Niebo: przezroczysty niebieski gradient, cumulonimbusy, słupy i druty, dachy w oddali, smuga samolotu, ptaki.
4. Krople na szybie → biała firanka → plamy światła w kształcie okna na podłodze i ścianie (cache `sk_floorlight`;
   na ścianie dorysuj kołyszący się cień firanki).
5. Doniczka → kot i dziewczyna przez `P.cel` → para.
6. Snopy Tyndalla (cache `sk_beams`) i drobiny → `P.lensFlare(c, SUN, t)` → `P.bloom(c, { key })` → `soft-light`.

## Co się rusza
- Ruch główny: picie herbaty; włosy na wietrze.
- Kłęby chmur oddychają (promień `0.05·sin(1.3t)`), całe niebo dryfuje 10 px/s; smuga samolotu, stado ptaków macha
  skrzydłami.
- Kropla spływa po szybie i zostawia ślad; firanka i jej cień na ścianie się kołyszą; liście w doniczce się ruszają.
- Promienie flary się obracają, snopy pulsują, drobiny migoczą.
- Pole ruchu 3,0%.

## Przejście-podpis (wejście w ten styl)
- `flareSweep`, 0,38 s: prześwietlenie i błysk. Skośna granica (k=0.35) przejeżdża od −500 do W+700 (`inOut`);
  po lewej nowy obraz, po prawej stary. Na granicy 3 pasy `lighter`: 520 px α0.55 ciepły, 160 px α0.85 biały,
  60 px α0.6 cyjanowy. Do tego pozioma smuga, 40 drobin światła i 3 sześciokątne plamy.

## Wydajność
- Ok. 71 ms na klatkę.
- Cache: wnętrze (`sk_room`), plamy światła (`sk_floorlight`), snopy z blur 18 px liczone raz (`sk_beams`). Bloom
  działa na płótnie 480×270, nie na pełnym kadrze.

## Pułapki
- Słońce na rogu ramy okna: flara wylewa się na ścianę i wygląda jak lampa na ścianie. Słońce zawsze wewnątrz szyby,
  flara r ≤130.
- Chmura jako jeden radialny gradient na kłąb plus łuk światła wygląda jak kupa baniek mydlanych. Rób „sylwetka +
  przesunięta jasna kula + warstwa rozmyta i ostra”.
- Pozioma smuga przez cały kadr (1800 px) wyglądała jak błąd renderu. Tylko przy słońcu: 840 px, α0.35.
- Kropla jako pełne koło wygląda jak bańka na niebie. Tylko dolny łuk, przezroczysta bryła α0.22 i jeden odblask.
- Konflikt nazw zmiennych (dwa `const cg`) wyłożył całą scenę, a silnik źródłowy po cichu wstawił zaślepkę.
  Po każdej zmianie sprawdź w konsoli, że scena się wczytała; nie oceniaj po tym, że „coś się wyrenderowało”.
- Słabość wzoru: wnętrze za puste. Dodaj gęstość: przedmioty na biurku, plakaty, kable, odbicia na podłodze.

## Kontrola
- Czy cienie na postaci to twarde pasma bez gradientu, po stronie przeciwnej do światła, z jasną obwódką od światła?
- Czy chmury mają jasną stronę od słońca i nie wyglądają jak bańki?
- Czy słońce jest w szybie, a flara nie wychodzi na ścianę?
- Czy tło ma dość szczegółów?
- Czy bloom i flara nie wybielają napisów?
