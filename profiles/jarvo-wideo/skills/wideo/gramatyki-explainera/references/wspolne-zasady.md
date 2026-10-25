# Wspólne zasady gramatyk explainera

Zasady wyciągnięte z kart gramatyk, które działają po zmianie gramatyki. W nawiasie karty, z których pochodzą. Wybór gramatyki: `wybor.md`; kontrakt klipu: `kontrakt-spec.md`.

## 12 zasad

1. **Kamera zależy tylko od czasu, a scena rysuje się od nowa wektorowo pod kamerę.** Najazd, przesunięcie i przelot to ten sam świat-płótno narysowany pod inną kamerą, więc nawet przy 60× powiększenia obraz jest ostry; w przejściu poprzednie ujęcie dalej prowadzi kamerę w czasie (`zoomThrough` z `live:true`). (`kurzgesagt`, `tablica`, `3b1b`)
2. **Zoom interpoluj logarytmicznie, a przez okrągły otwór przechodź z wystarczającym powiększeniem.** `CAM.zlerp` daje w każdej klatce ten sam mnożnik powiększenia; interpolacja liniowa jest na początku wolna, a na końcu gwałtowna. Przelot przez otwór o promieniu r: powiększenie ≥ odległość od środka otworu do najdalszego rogu ekranu / r (dla otworu w środku ok. 1100/r, `CAM.coverZoom`). (`kurzgesagt`, `3b1b`)
3. **Klatka odsłonięcia trafia w akcent albo w słowo lektora.** Przejście liczy się od początku nowego odcinka, a klatka, w której pokazuje się nowy obraz, ma wypaść na kresce taktu: początek odcinka = kreska taktu − punkt odsłonięcia × czas przejścia (`MO.onBeat`). Liczba staje w chwili, gdy lektor ją wypowiada: start liczenia = chwila słowa − czas liczenia. Na tablicy pisanie zaczyna się ok. 0,5 s po odpowiedniej frazie. W klipie robi to `slowo` z `offset` (`kontrakt-spec.md`). (`kinetyczna`, `prezentacja`, `wykresy`, `tablica`)
4. **Najpierw struktura, potem dane, na końcu oznaczenie.** Najpierw układ współrzędnych, potem rosną dane, na końcu oznaczenie, jedno na ujęcie. W `3b1b` najpierw pisze się pytanie, potem pokaz; w `prezentacja` nadtytuł → nazwa produktu → podtytuł. (`wykresy`, `3b1b`, `prezentacja`)
5. **Jeden punkt uwagi na ekranie.** W danej chwili wchodzi jedna rzecz, reszta stoi; słowo główne do zdania pomocniczego co najmniej 3:1; tło ma nasycenie, kontrast i grubość linii o stopień niższe niż bohater. (`kinetyczna`, `prezentacja`, `historyjka`)
6. **Wejście wolne, wyjście szybkie, po zatrzymaniu postój.** Wejście 0,3–0,4 s, wyjście ok. 0,18 s. Po zatrzymaniu liczby co najmniej 0,5 s postoju, po puencie zamrożenie ≥ 0,9 s, w `3b1b` po każdej animacji ok. 1 s postoju. (`kinetyczna`, `wykresy`, `historyjka`, `3b1b`)
7. **„Ciągle w ruchu” albo „szybkie cięcie i zamrożenie” – według gramatyki, bez mieszania.** W Kurzgesagt odcinki 0,5 s zupełnego bezruchu to 0,3% czasu; w `historyjka` 70% klatek stoi zupełnie, a życie dają szybkie cięcia i zamrożenia. (`kurzgesagt`, `historyjka`)
8. **Dwa klatkaże: kamera płynnie, elementy skokowo.** `vox`: kamera płynna, wycinki, zakreślacz i pisanie co 12 fps („na dwójkach”); `historyjka`: postać 24 fps, kamera 60 fps. Wszystko płynne wygląda jak film korporacyjny, wszystko skokowe – drży. (`vox`, `historyjka`)
9. **Kolor = pojęcie, mało akcentów.** Jeden kolor to jedno pojęcie (W we wzorze i połączenia w sieci – oba niebieskie); ponad 3–4 kolory znaczeniowe są nie do zapamiętania. `vox`: czerń, biel papieru i jedna czerwień; `tablica`: czerń i jeden pomarańczowy. (`3b1b`, `wykresy`, `vox`, `tablica`)
10. **Przejście w oddechu i przy zmianie tematu, nie w środku zdania.** Przerzut kamery tnij między zdaniami, zbliżenie reakcji kładź w ciszy; przesunięcie tablicy otwiera nowy argument; twarde cięcie `vox` wypada na znaku przestankowym. (`historyjka`, `tablica`, `vox`)
11. **Odbiór sprawdza logikę i sens liczb, nie tylko wygląd.** Wyłapane w testach: „wzrost o 8,7 raza” zamiast „8,7 razy tyle co na początku”; po rozwinięciu karty na pełny ekran licznik liczył od nowa od 0; lektor mówił o warstwie ukrytej, a połączenia szły do pikseli. Mnożnik musi się dać policzyć z liczb na obrazie. (`wykresy`, `prezentacja`, `3b1b`)
12. **Prawdziwy materiał zostaje taki, jaki jest.** Zrzuty proporcjonalnie, bez ucinania kluczowego UI; animacja zmienia tylko sposób pojawienia się danych, nie ich wartość; słupki zawsze od 0, oś nie od 0 – napisana; dane zmyślone mają w każdym ujęciu znaczek „dane przykładowe”, prawdziwe nigdy. Fakty i liczby z `fakty.json` (brief Sherlocka). (`wykresy`, `kontrakt-spec.md`)

## Biblioteka – ściąga

Strona filmu (kontrakt jarvo) ładuje biblioteki z `/_lib/huashu/` (= `$HUASHU/scripts/engine/`, instalacja: `@@PY@@ "$HERMES_HOME/scripts/narzedzia.py" instaluj huashu`). Ładuj wszystkie w kolejności z ich `clip.html`, bo wołają się nawzajem (`CH` i `TOON` używają `TY`, `DG` używa `CAM`, `TY` używa `CL`): `lib/fonts.js`, `lib/util.js` (`U`: `clamp/lerp/hash/rng`…), `lib/paint.js` (`PAINT`: `hex/cached`…), `lib/kit.js`, potem pliki z tabeli; do tego polska nakładka `/_lib/jarvo/huashu_pl.js` (kroje z polskimi znakami, polski `TY.fmt`).

```html
<script src="/_lib/huashu/lib/fonts.js"></script>
<script src="/_lib/huashu/lib/util.js"></script>
<script src="/_lib/huashu/lib/paint.js"></script>
<script src="/_lib/huashu/lib/kit.js"></script>
<script src="/_lib/huashu/lib/motion.js"></script>
<script src="/_lib/huashu/lib/camera.js"></script>
<script src="/_lib/huashu/lib/diagram.js"></script>
<script src="/_lib/huashu/lib/typo.js"></script>
<script src="/_lib/huashu/lib/chart.js"></script>
<script src="/_lib/huashu/lib/ui.js"></script>
<script src="/_lib/huashu/lib/collage.js"></script>
<script src="/_lib/huashu/lib/toon.js"></script>
<script src="/_lib/huashu/transitions.js"></script>   <!-- gdy używasz przejść -->
<script src="/_lib/jarvo/huashu_pl.js"></script>
```

Płótno inne niż 1920×1080 (pion): raz na starcie `U.setStage(W, H)`, wtedy `CAM`, `UI`, `CH`, `DG`, `CL` przeliczą rozmiar. `paint.js`, `kit.js` i `transitions.js` mają 1920×1080 wpisane na sztywno: w pionie sprawdź je na stopklatkach.

| Plik | Przestrzeń | Co ma |
|---|---|---|
| `/_lib/huashu/lib/motion.js` | `MO` | `seg/at/anim/step` (krok 12 fps), z manim `smooth/thereAndBack/rushInto/rushFrom/doubleSmooth/wiggle/lagged`, `sineInOut/cubic*/quart/quint/expo*/backOut/elasticOut`, `bezier` oraz `appleOut/emphasized/k75/easyEase/longTail`, sprężyny SwiftUI `spring/smoothSpring/snappy/bouncy`, `springHz/settle`, `float`, `invert` (odwrotność krzywej), `beat/onBeat` (wyrównanie do taktu); `U.setStage/onStage` (rozmiar płótna) |
| `/_lib/huashu/lib/camera.js` | `CAM` | `apply/with`, `toScreen/toWorld`, `zlerp` (zoom logarytmiczny), `coverZoom`, `anchor`, `pushTo` (najazd na punkt: punkt płynnie do środka albo powiększenie w miejscu), `at` (klatki kluczowe, przesunięcie po ścieżce), `layer` (paralaksa), `velocity/motionBlur` (rozmycie przerzutu), `drift` (lekki dryf „z ręki”) |
| `/_lib/huashu/lib/diagram.js` | `DG` | Punkty `cum/len/pointAt/drawPartial` (rysowanie kreski po kawałku), `xform/arcPts/ellipsePts/hand` (drżenie ręki), `revealMask/zigzag` (odsłanianie); Transform `rectPts/circlePts/morph/shape`; kolory `mix/mixA/rgba`; paleta 3b1b `MANIM` (już ×1,5 nasycenia) i `saturate`; `math/write` (manim Write: najpierw kontur, potem wypełnienie); `neuron/edgeEnds/edge/flash`; `indicate/circumscribe/brace`; tablica `board` (oś czasu kresek i przesuw między nimi), `pen` (marker) |
| `/_lib/huashu/lib/typo.js` | `TY` | `text/width/font`; `wrap/fit` (łamanie; `fit` zmniejsza krój, aż tekst naprawdę się mieści: liczba linii ≤ `maxLines` i zmierzona szerokość każdej linii, także jednego długiego słowa; `soft:true` – gdy się nie mieści, zwraca `ok:false`, żebyś zmienił plan; `balance:true` – linie równej długości); `charsIn` (litery wypływają po kolei), `rise` (wynurzenie z maski), `pop`, `blurIn` (wyłanianie z rozmycia), `typed/typedCount` (pisanie), `marker/underline`, `slam` (uderzenie słowa głównego), `keyword/keywordMarker` (wyróżnienie słowa), `fmt/count/tabular` (przewijanie liczb, cyfry o stałej szerokości; `TY.fmt` w nakładce po polsku: przecinek dziesiętny, spacja tysięcy) |
| `/_lib/huashu/lib/chart.js` | `CH` | `lin/ticks`, `grid/xLabels` (osie najpierw), `bars` (od 0, liczenie razem z wierzchołkiem, wyróżnienie i wyszarzenie), `line/yAt`, `candles`, `callout` (kropka → linia odniesienia → tekst), `tag/demoBadge/frame` (układ jak The Economist) |
| `/_lib/huashu/lib/ui.js` | `UI` | `mesh` (tło z plam światła), `grainTex`, `backdrop`, `shadow`, `glass` (matowe szkło), `sheen` (przelot odblasku), `persp` (pseudo-3D), `icon`, `rr/rrPath/scratch` |
| `/_lib/huashu/lib/collage.js` | `CL` | `paperTile/fillPaper` (faktura papieru), `tornEdge/tornRect` (darte krawędzie), `halftone/photo` (zdjęcie w rastrze), `placed/shadowed/slideIn` (wjazd pod kątem i położenie płasko), `tape/pin`, `stringPts/string` (czerwona nić), `highlight` (zakreślacz z postrzępioną krawędzią), `stickerEdge` (biała krawędź wycinanki) |
| `/_lib/huashu/lib/toon.js` | `TOON` | `flat` (dwutonowe płaszczyzny), `glow/vgrad/circle/ellipse`, `bean` (postać-fasolka) i `POSES`, `poseAt` (od pozy do pozy z odbiciem), `blinkAt`, `alive`, `env/mouth` (usta z obwiedni lektora), `sweat/mark`. Postać u nas neutralna albo w kolorach marki. |

**Przejścia:** `/_lib/huashu/transitions.js`, sekcja na końcu pliku (przejścia gramatyk explainera). Każde to funkcja `(c, A, B, p, o)`: `A` stary obraz (canvas), `B` nowy, `p` 0..1, `o` parametry. Zasada: przejście nie kradnie uwagi i trzyma ciągłość przestrzeni (widz wie, dokąd poszła kamera); ruch kamery liczy scena (`CAM`), przejście tylko łączy A i B. Twarde cięcie: `cut`.

| Przejście | Co robi |
|---|---|
| `same` | A i B to ten sam świat (kamera ciągła): po prostu B. Szybka panorama `vox`, przesunięcie `tablica`. |
| `lensReveal` | Kamera w A wykładniczo najeżdża na krąg (oko, soczewkę), B widać tylko w nim; krąg rośnie do pełnego ekranu, z pierścieniem światła. `o.lens(t)` → `{x, y, r}`, `o.ring`; powiększenie ≥ `CAM.coverZoom(r)`. (`kurzgesagt`) |
| `matchCut` | A najeżdża, aż plama koloru wypełni ekran, B wyjeżdża z czegoś w tym samym kolorze; przenikanie tylko ±3 klatki wokół `o.at` (domyślnie środek). (`kurzgesagt`) |
| `whip` | Stary obraz wylatuje z przyspieszeniem, nowy wlatuje z hamowaniem, w środku poziome rozmycie ruchu (próbki co ≤8 px); `o.dir=1` w lewo. (`historyjka`) |
| `smash` | Od pierwszej klatki nowy obraz z powiększeniem 1,22 gaszonym sprężyną, dwie pierwsze klatki biały błysk. Do zbliżeń reakcji. (`historyjka`) |
| `fillZoom` | Kamera wpada w kształt w A (`o.cx`, `o.cy`; jego kolor `o.fill` = tło B), po wypełnieniu B opada z 1,25 do 1; punkt odsłonięcia `o.k` (domyślnie .55), `o.maxZoom`. (`kinetyczna`) |
| `bands` | Kilka ukośnych pasów `o.colors` przelatuje sztafetą (odstęp `o.gap`), za ostatnim B; odsłonięcie ≈ .6. (`kinetyczna`) |
| `push` | A i B przesuwają się razem (expoInOut), `o.dir`: `'left'` (domyślnie) albo `'up'`; 90% przesunięcia przy p ≈ .58. (`kinetyczna`) |
| `zoomThrough` | Przelot: `{cx, cy, zoom, r0, live, bg, focus, bScale0, ease}`; szczegóły w `3b1b.md` i `wykresy.md`. |
| `blurPush` | A cofa się do 0,92 z rozmyciem i przyciemnieniem, B z 1,06 w rozmyciu ląduje ostro na 1,0; pod spodem powiększona, mocno rozmyta kopia A (bez czarnych krawędzi). (`prezentacja`) |
| `expandRect` | Karta `o.rect={x,y,w,h}` z zaokrągleniem `o.r` rozwija się sprężyną na pełny ekran, w niej B (od pierwszej klatki nieprzezroczyste), A cofa się i ciemnieje. (`prezentacja`) |
| `slidePush` | B wjeżdża z prawej, A wyjeżdża w lewo (bezier .7,0,.2,1), prowadzi pionowy pasek koloru marki `o.bar`. (`wykresy`) |
| `fadeShift` | Manim FadeOut/FadeIn z przesunięciem w górę, `o.shift` w px. (`3b1b`) |

**Kroje** (`lib/fonts.js`; każdy plik to osobna rodzina, np. `ctx.font = '96px "Inter"'`). Oryginał: chiński bezszeryfowy PuHui-Medium/Bold/Heavy/Black (w otwartej wersji Noto Sans SC 500/700/800/900), tablica LXGWWenKai-500, wzory `CMU-rm`/`CMU-it`, prezentacja Inter, liczby finansowe `RobotoCondensed`. W Jarvie nakładka podmienia PuHui-* → Inter (te same grubości), NotoSansSC → Inter, NotoSerifSC → EB Garamond, LXGWWenKai-500 → Caveat-600. Kontrola glifów w klipie sprawdza tylko znaki CJK: polskie ogonki sprawdzaj na stopklatkach.
