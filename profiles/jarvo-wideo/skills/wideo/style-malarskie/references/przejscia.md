# Przejścia-podpisy (`TRANSITIONS`)

Przejście między stylami to podpis następnego stylu, a nie ogólne wycieranie z biblioteki. Nowy obraz pojawia się
tak, jak w tym stylu obraz pojawia się naprawdę: topnienie to ciecz, Hopper to światło, akwarela to woda, VHS to
taśma, Matisse to arkusz papieru, teatr cieni to zapalona lampa. Przy wyborze albo pisaniu przejścia zadaj jedno
pytanie: „W jaki fizyczny sposób pojawia się obraz w tym stylu?”.
Kod: `$HUASHU/scripts/engine/transitions.js` (MIT, biblioteka huashu: `@@PY@@ "$HERMES_HOME/scripts/narzedzia.py"
instaluj huashu`; `$HUASHU` = `@@TOOLS_DIR@@/huashu-art-motion`). W naszej stronie:
`<script src="/_lib/huashu/transitions.js">`, po bibliotekach, których używa: `lib/util.js` (`U`), `lib/paint.js`
i `lib/render.js` (`PAINT`), `lib/rig.js` (`RIG`), `lib/kit.js` (`KIT`), `lib/motion.js` (`MO`).

## Jak zaprojektować przejście-podpis (4 kroki)
1. Znajdź w nowym stylu fizyczny proces, w którym coś „pojawia się, zapala albo przejeżdża” (płatek złota, fala,
   pędzel, przysłona, lampa, rozlewająca się plama).
2. Najpierw „zabrudź” nim stary obraz (stary obraz zapada w cień, robi się sepią, rozpada w kropki, faluje).
3. Nowy obraz wyłania się z kształtu tego procesu (z wnętrza plamy, spod pędzla, za arkuszem, w świetle lampy).
4. Na bit dodaj krótki rozbłysk albo przeskok (`outBack`, błysk `lighter`, uderzenie kamery).

Przejście może zaczynać się od przedmiotu w kadrze (kropki od kota, krąg od filiżanki, snop od okna) – działa to,
bo przedmioty stoją w tym samym miejscu we wszystkich stylach filmu. Ustaw wtedy `cx`, `cy` na swój przedmiot.

## Jak się je wywołuje
- Sygnatura: `TRANSITIONS.<nazwa>(c, A, B, p, o)`.
  - `c` – kontekst 2D kadru, do którego rysujesz;
  - `A` – płótno starego odcinka, `B` – płótno nowego (oba już narysowane w tej chwili czasu);
  - `p` ∈ [0,1] – postęp przejścia;
  - `o` – parametry z wpisu `transition` plus `id` (nowy odcinek), `from` (stary odcinek), `lt` (czas lokalny
    nowego odcinka), `t` (czas filmu), `W`, `H`, `tmp` (pomocnicze płótno W×H, przed użyciem `g.reset()`), `IMG`.
- Wpis w tabeli odcinków silnika huashu (`eras.js`): `{ id, eighths | dur, transition: { type, dur, delay, cx, cy,
  punch, counter, … } }`. Przejście zaczyna się w chwili startu nowego odcinka i trwa `dur` (+ `delay`);
  `p = clamp((lt − delay)/dur)`. W tym czasie silnik rysuje oba odcinki do buforów A i B i woła funkcję przejścia.
- W naszej stronie robisz to samo: dwa płótna poza ekranem (stara i nowa scena w tej samej chwili t), potem
  `TRANSITIONS.<nazwa>(ctx, A, B, p, { ...parametry, id, from, lt, t, W, H, tmp, IMG })`.
- Determinizm: losowość tylko z `U.rng(ziarno)`; ten sam t daje ten sam piksel.
- Pamięć podręczna `once(k, f, o)` tylko dla rzeczy niezależnych od obrazu (siatki, tablice kafli, płótna robocze).
  Niczego, co zależy od treści A albo B, nie trzymaj w cache. Jeśli musisz, przekaż `o` (klucz dostaje id odcinka).
  Inaczej drugie użycie tego samego przejścia w filmie narysuje treść z pierwszego, a przy renderze klatek
  w innej kolejności wynik zależy od kolejności.
- Własne przejście dopisz jako `TRANSITIONS.<nazwa> = (c, A, B, p, o) => { … }` po załadowaniu `transitions.js`;
  narzędzia: `TR_UTIL.once`, `TR_UTIL.seg` (`seg(p, a, b)` – odcinek [a,b] rozciągnięty do 0..1), `TR_UTIL.mkc`
  (nowe płótno).
- Plakietka, licznik albo tytuł w trakcie przejścia: domyślnie (`window.COUNTER_IN_TRANSITION = 'cut'`) nie rysuj
  ich na warstwach A i B, tylko raz na wierzchu, i przełącz stary na nowy przy p = 0,5. Przy odsłonach lokalnych
  (lampa, snop, fala) dwie plakietki o różnym układzie zlewają się w jedną plamę liter. `'layers'` zostawia plakietkę
  w warstwach – tylko gdy obie są w tym samym miejscu i tym samym kroju. Per przejście: `transition.counter`.

## Uderzenie na bit (punch)
- Pierwsza klatka przejścia to uderzenie kamery: warstwa sceny powiększona do 1.03 wraca do 1.0 w ok. 20 klatkach:
  `s(k) = 1 + amp·(1 − k/20)^1.5`, k = klatki od startu przejścia liczone w 60 fps (`k = (t − t0)·60`, czyli
  ok. 0,33 s niezależnie od klatkażu renderu). Skalowanie wokół środka kadru.
- **Na obu warstwach.** Stary odcinek też dostaje uderzenie od startu nowego. Gdy uderza tylko nowa warstwa, a nowy
  obraz na początku przejścia jeszcze nie wyszedł, klatka na bicie stoi i dźwięk wyprzedza obraz (zmierzone
  opóźnienie 0,1–0,17 s).
- Plakietki i licznika nie skaluj.
- Amplituda: `transition.punch` (liczba; `false` albo 0 wyłącza; `true` = 0.03) ma pierwszeństwo przed
  `window.PUNCH`, a domyślnie jest 0.03. Explainer, prezentacja, dane: `window.PUNCH = 0`.
- Start przejścia leży na siatce rytmu; „klik” w muzyce i uderzenie obrazu to ta sama chwila.
- Ruch w stylu mierz różnicą klatek dopiero 0,35 s po przejściu – wcześniej uderzenie rusza cały kadr.

## Czas trwania
- Liczy się część widoczna. Przy krzywej `inOut` początek i koniec prawie się nie ruszają: złożone przejście-podpis
  0,34 s czyta się jak 0,2 s i wygląda jak zwykłe wycieranie. Złożone (płatki złota, pasy koloru, wstęgi) dawaj
  **0,48–0,5 s**; proste kształty, jak w filmie źródłowym, wystarczą w 0,4 s. W galerii 35 stylów część złożonych
  przejść ma tylko 0,34–0,42 s (odcinki po 5 ósemek); gdy odcinek jest dłuższy, wydłuż je do 0,48–0,5 s.
- W filmie, który przyspiesza (128 BPM, coraz krótsze odcinki), czas przejścia maleje razem z odcinkami: od 0,4 s
  do 0,13 s (w źródłowym filmie 16 epok: `tiles` 0.42 … `pixelate` 0.12, `wireframe` 0.14, `iris` 0.183).
- Odsłonę na bit albo na słowo lektora wyrównujesz startem odcinka: start = kreska taktu − punkt odsłony × dur
  (`MO.onBeat(barTime, revealP, trDur)`). Punkty odsłony: `fillZoom` = `k` (domyślnie 0.55), `bands` ≈ 0.6,
  `push` ≈ 0.58 (90% przesunięcia; nie p = 1), `matchCut` = `at` (domyślnie 0.5).
- W explainerze przejście stawiaj w przerwie na oddech albo przy zmianie tematu, nie w środku zdania.

## Przejścia artystyczne (wejście w styl)
Kolejność według stylu, w który wchodzą. Czas to `dur` z galerii 35 stylów (`eras_gallery.js`), dla czterech
z grupy B także koszt klatki zmierzony w źródle. `o.cx, o.cy` to punkt startu; domyślne wartości pasują do kompozycji
wzoru (filiżanka ok. (1000,600), kot ok. (540,760), głowa ok. (1300,380), okno ok. (580,300)).

| Wchodzi w | Przejście | Co widać | Parametry `o` | Czas |
|---|---|---|---|---|
| `01_cave` | – | otwarcie filmu, bez przejścia | – | – |
| `02_egypt` | `tiles` | nowy obraz z bloków 240×180 (45% dzielonych na 4) wpada od lewej do prawej, każdy z przesunięcia i obrotu, skala 1.08→1, `outBack`, cień w locie; w indeksie źródła opisane jako „pasy gobelinu z odbiciem” | – | 0,42 s |
| `03_greek` | `cube` | sześcian obraca się wokół pionowej osi (stara ściana odchodzi w lewo, nowa wchodzi z prawej), 48 pasków, cieniowanie ścian; „obrót wazy” | – | 0,32 s |
| `04_roman` | `mosaic` | kafelki 18×34 obracają się jak tessery od kota (W·0.27, H·0.72) na zewnątrz, w połowie obrotu ciemny spód `#17110d` | – | 0,38 s |
| `05_gothic` | `pageTurn` | pergaminowa strona zawija się od prawej do lewej (pas 260 px), na odwrocie `#e9dcc0` z 18% odbiciem starego obrazu, cień 90 px | – | 0,32 s |
| `06_renaissance` | `godRays` | z okna wybucha złoty blask (r 520) i 34 promienie; nowy obraz wyłania się w p 0,05–0,5 | `cx, cy` (domyślnie 440,300; w galerii 560,290) | 0,4 s |
| (brak w 35) | `wave` | wielka fala Hokusaia przetacza się od lewej do prawej (pas 300 px `#1f3f8a`, pazury piany co 54 px, 70 kropel); po niej nowy obraz. Wejście w ukiyo-e, którego nie ma wśród 35 stylów | – | – |
| `08_impressionism` | `dabs` | 2600 krótkich eliptycznych pociągnięć „maluje” nowy obraz (p 0–0,7), na wierzchu 260 jasnych plamek `#f6e27a #f2a7c3 #b9d9f2 #c6e8a8 #ffffff`; od p>0,7 przenikanie | – | 0,28 s |
| `09_postimp` | `swirl` | wir gwiaździstej nocy wokół okna: stary obraz skręca się (do 5 rad), nowy odkręca się z 4.2 rad i obrotu −0.9; piksele w pół rozdzielczości, R 1100; od p>0,85 przenikanie | `cx, cy` (420,300; w galerii 560,340) | 0,28 s |
| `10_nouveau` | `organic` | organiczny kształt (suma sinusów 3/5/9) rośnie od głowy do R 2300, ze złotą obwódką `#6b4a24` 14 px + `#d9b25a` 8 px; w środku nowy obraz | `cx, cy` (1500,330; w galerii 1330,320) | 0,24 s |
| `11_cubism` | `shards` | kadr pęka na 108 trójkątów (siatka 9×6); stare odłamki rozjeżdżają się i obracają, nowe składają się na miejsce | – | 0,24 s |
| `12_bauhaus` | `bauhaus` | niebieski kwadrat, czerwone koło i żółty trójkąt obracają się i rosną wykładniczo, potem odjeżdżają w lewo; w rosnącym kole nowy obraz | `cx, cy` (1010,560; w galerii 1330,590) | 0,2 s |
| `13_pop` | `zigzag` | stary obraz → raster Ben-Day → raster nowego → nowy; żółta błyskawica z czarną obwódką (34/22 px) i gwiazda wybuchu | – | 0,16 s |
| `14_8bit` | `pixelate` | piksele starego obrazu rosną 1→72, po przełączeniu piksele nowego maleją 72→1 | – | 0,12 s |
| `15_raytrace` | `wireframe` | czarne tło, zielona neonowa siatka perspektywiczna i krawędzie nowego obrazu (Sobel), potem linia skanowania z góry na dół „renderuje” nowy obraz | – | 0,14 s |
| `16_2026` | `iris` | trzy koncentryczne pierścienie (granat, koral, krem; po 137 px) rosną liniowo od filiżanki; w najmniejszym nowy obraz | `cx, cy` (992,601) | 0,183 s |
| `17_ink` | `inkBloom` | stary obraz „spiera się” do papieru ryżowego (szarość, jaśniej, mniej kontrastu), 7 plam tuszu rozlewa się z poszarpanym brzegiem; ciemna obwódka tuszu gaśnie w miarę wzrostu; liczone w 1/4 rozdzielczości; od p>0,8 przenikanie | `cx, cy` (560,740) | 0,45 s |
| `18_klimt` | `goldLeaf` | kwadratowe płatki złota 72 px spadają po spirali od głowy (z 1.3, z obrotem, wytłoczona spirala, oko albo koła), potem złoto blednie i odsłania nowy obraz | `cx, cy` (1300,380) | 0,5 s |
| `19_munch` | `screamWarp` | krwawe niebo „Krzyku” spływa z góry: stary obraz faluje rzędami (do 70e), nad falistym frontem nowy obraz się uspokaja; na froncie 4 pasy 26 px `#b82a1e #e2541c #f08a24 #f4c03a` | – | 0,5 s |
| `20_dunhuang` | `apsara` | front wstęg apsary przejeżdża od prawej do lewej (3 wstęgi: zieleń, czerwień ziemi, błękit; 44/38/32 px, biały przerywany ornament); za nim nowe malowidło, przed nim odpadają kawałki starego | – | 0,5 s |
| `21_kusama` | `dotBloom` | kropki na siatce heksagonalnej 58 px rosną od kota (`outBack`, do 0.74 odstępu), w kropkach nowy obraz; niedorosłe mają gasnącą białą obwódkę | `cx, cy` (540,760) | 0,48 s |
| `22_constructivism` | `redWedge` | czerwony klin Lissitzky'ego `#c8231c` wbija się ukośnie od lewego dołu, za jego ostrzem nowy obraz; za klinem wpadają 3 czarne paski typograficzne z opóźnieniem 0 / 0.12 / 0.2 | – | 0,4 s |
| `23_dali` | `melt` | nowy obraz spływa z góry jak farba (linia spadku + 26 kropli z zaokrąglonym końcem, profil `(1−u²)^0.3`); stary obraz zwisa kolumnami po 4 px; na powierzchni ciemna krawędź i odblask | – | 0,36 s (ok. 86 ms/klatkę) |
| `24_hopper` | `sunShaft` | twardy skośny snop słońca (skos 260 px) przejeżdża przez kadr; w nim nowy obraz z ciepłym `screen`, poza nim stary zapada w zimną zieleń; w snopie cień szprosu | – | 0,34 s (ok. 76 ms) |
| `25_ghibli` | `bleed` | 5 plam akwareli rozlewa się po mokrym papierze (najpierw okno), brzeg poszarpany fbm; na zewnątrz jasna obwódka wody, na krawędzi brązowy ślad; w plamach nowy obraz | `cx, cy` (580,330) | 0,38 s (ok. 127 ms) |
| `26_vaporwave` | `vhs` | awaria taśmy: rozdarcia, rozjazd magenta/cyjan ±14, w p 0,38–0,62 cały obraz roluje z czarnym pasem 40 px, 160 kresek śniegu; pierwsza połowa stary, druga nowy | – | 0,30 s (ok. 88 ms) |
| `27_kirby` | `comicPanels` | stary obraz pod rastrem magenta, nowy wpada w 5 kadrach komiksu (z 1.18, `outBack`), czarne linie kadrów 14 px znikają na końcu; w indeksie źródła „otwarcie” | – | 0,42 s |
| `28_monet` | `ripple` | stary obraz faluje jak odbicie w wodzie, nowy odsłania się kręgami z 3600 poziomych krótkich pociągnięć od filiżanki, na froncie 3 przerywane elipsy | `cx, cy` (1000,600) | 0,34 s |
| `29_seurat` | `pointill` | obraz „krystalizuje się” w kropki (pitch 14, r do 6.4), kropki zmieniają kolor na nowy od lewego górnego rogu z podskokiem ×1.35, potem się zwijają | – | 0,34 s |
| `30_matisse` | `cutouts` | arkusz kobaltowego papieru 1100 px z wodorostami, gwiazdami i kołem przejeżdża od prawej do lewej, za nim nowy obraz | – | 0,36 s |
| `31_haring` | `radiant` | tańczący ludzik z rękami w V rośnie od filiżanki (`0.15·320^easeInOut(p)`), w jego ciele nowy obraz, wokół 16 kresek ruchu 8 fps | `cx, cy` (1000,600) | 0,32 s |
| `32_rembrandt` | `chiaroscuro` | stary obraz zapada w ciemny brąz (winieta), skośny snop z okna (blur 40 px) odsłania nowy, ciepły blask; w indeksie źródła przy Rembrandcie błędnie „przysłona starej taśmy” | `cx, cy` (580,300) | 0,45 s |
| `33_rubberhose` | `irisFilm` | stary obraz w sepii, czarna przysłona zamyka się do filiżanki i otwiera z przeskokiem `outBack` na nowym, drgający obwód 12 fps, rysy i kurz taśmy | `cx, cy` (960,540; w galerii 1236,420) | 0,4 s |
| `34_shadowpuppet` | `lampGlow` | stary obraz gaśnie do brązu, za ekranem zapala się lampa: nowy obraz w ciepłym kręgu (R do 1500, drganie płomienia ±7%) z płomykiem w środku | `cx, cy` (960,470) | 0,4 s |
| `35_shinkai` | `flareSweep` | skośny pas prześwietlenia (k 0.35) przejeżdża od lewej: 3 pasy `lighter` (520/160/60 px), smuga, 40 drobin, 3 sześciokątne plamy; po lewej nowy obraz | – | 0,38 s |
| `36_picasso_blue` | `blueBrush` | kolor starego obrazu zostaje wyssany do błękitu, 6 szerokich suchych pociągnięć (H/6+90) maluje nowy obraz od lewej, z włosiem za głową pędzla | – | 0,42 s |

Ogólne: `crossfade` (zwykłe przenikanie) i `cut` (twarde cięcie przy p = 0,5; w demach `dur: 1/60` albo `0.02`).

Rozbieżności indeksu źródła z kodem (wierz kodowi): `02_egypt` opisany jako gobelin, kod układa bloki; przy
`32_rembrandt` stoi przysłona taśmy, a to `irisFilm` do `33_rubberhose`; `17_ink`, `22_constructivism`, `27_kirby`
oznaczone jako „otwarcie”, ale mają już przejścia (`inkBloom`, `redWedge`, `comicPanels`).

## Przejścia explainera (13)
Zasada odwrotna niż w przeglądzie stylów: przejście nie kradnie uwagi i trzyma ciągłość przestrzeni – widz wie,
dokąd poszła kamera. Najczęściej to ruch kamery albo wspólny element. Ruch kamery liczysz w scenie (`CAM`),
przejście tylko łączy A i B. Uderzenie wyłączone: `window.PUNCH = 0` albo `punch: 0`.
Czas typowy = `dur` z dem źródła.

| Przejście | Gramatyka | Co robi | Parametry `o` | Czas |
|---|---|---|---|---|
| `same` | Vox, tablica | A i B to ten sam świat (ciągła kamera na jednym płótnie), rysuje tylko B; szybka panorama po biurku, przesunięcie po tablicy | – | 0,8–1,1 s |
| `lensReveal` | Kurzgesagt | kamera w A wykładniczo najeżdża na koło (oko, obiektyw); B widać tylko w tym kole, koło rośnie aż pokryje ekran; na brzegu świetlny pierścień | `lens(t) → {x, y, r}` (zsynchronizowane z najazdem w A), `ring`, `ring2` (RGB); powiększenie ≥ `CAM.coverZoom(r)` | 1,0 s |
| `matchCut` | Kurzgesagt | A najeżdża, aż plama koloru wypełni ekran; B wychodzi z czegoś w tym samym kolorze; przenikanie tylko w `at ± width/2` (ok. ±3 klatki), więc cięcia nie widać | `at` (0.5), `width` (0.06) | 0,9 s |
| `whip` | storytime | szybka panorama: stary wylatuje z przyspieszeniem, nowy wlatuje z hamowaniem (`MO.expoInOut`), w środku poziomy motion blur (do 41 kopii, rozrzut do 320 px) | `dir` (1 = w lewo) | 0,26 s |
| `smash` | storytime | od pierwszej klatki nowy obraz, ze skali 1.22 sprężyną do 1 (`MO.springHz`, skala ≥1), pierwsze 2 klatki biały błysk 55%; zbliżenie reakcji | `freq` (3), `decay` (11), `dur` | 0,32 s |
| `fillZoom` | kinetyczna | kamera wpada w kształt w A, którego kolor = tło B; po wypełnieniu B opada z 1.25 do 1 | `cx, cy`, `fill`, `k` (0.55 = punkt odsłony), `maxZoom` (40) | 0,45 s |
| `bands` | kinetyczna | kilka skośnych pasów koloru przejeżdża sztafetą (`MO.expoInOut`), za ostatnim nowy obraz; odsłona ≈ 0.6 | `colors` (`['#FFD23F', '#FF5A36', '#14213D']`), `gap` (0.13) | 0,5 s |
| `push` | kinetyczna | stary i nowy przesuwają się razem (`MO.expoInOut`), jak kamera na długim płótnie; 90% przesunięcia przy p≈0.58 | `dir`: `'left'` (domyślnie) albo `'up'` | 0,35 s |
| `zoomThrough` | 3b1b, wykresy | kamera najeżdża na (cx,cy), nowy obraz wyrasta z wnętrza obiektu | `cx, cy`, `zoom` (7), `r0` (promień otworu, 0 = bez przycinania), `live`, `bg`, `focus: [x,y]`, `bScale0`, `ease` (`MO.smooth`) | 0,6–0,75 s |
| `blurPush` | prezentacja | stary cofa się do 0.92 z rozmyciem i ściemnieniem, nowy z 1.06 i rozmyciem do 1.0 ostry (`MO.appleOut`); pod spodem powiększony, mocno rozmyty stary (bez czarnych brzegów) | – | 0,55 s |
| `expandRect` | prezentacja | karta z poprzedniego ujęcia rozwija się na pełny ekran (wspólny element, sprężyna bez odbicia), w niej nowy obraz, stary cofa się do 0.94 i ciemnieje | `rect: {x, y, w, h}` (karta na ostatniej klatce poprzedniego ujęcia), `r` (28), `dur` (0.6) | 0,6 s |
| `slidePush` | wykresy | nowy panel wjeżdża z prawej, stary wyjeżdża w lewo (`MO.bezier(0.7, 0, 0.2, 1)`), na czele pionowy pasek 14 px w kolorze marki | `bar` (kolor paska) | 0,5 s |
| `fadeShift` | 3b1b | jak manim `FadeOut(shift=UP)` + `FadeIn(shift=UP)`: stary blednie i jedzie w górę (p 0–0,6), nowy pojawia się od dołu (p 0,4–1) | `shift` (60 px), `bg` (`'#000'`) | brak w demach |

Twarde cięcie w explainerze: `cut` (stara nazwa `hardcut`). Stare nazwy z archiwum: `k_lens` → `lensReveal`,
`k_fill` → `matchCut`, `zoomThrough` z kinetycznej → `fillZoom`.

## Pułapki
- Kształt-suma wielu części (ludzik, wiele plam) jako jeden `clip(Path2D)`: przeciwne kierunki obrysu znoszą się
  i robią dziury. Rysuj kształt na białym płótnie poza ekranem, potem `source-in` nowy obraz (tak robi `radiant`).
- Przejścia na pikselach (`pointill`, `swirl`, `wireframe`) robią co klatkę `getImageData` z A i B: ok. 10 ms każde,
  do przyjęcia. Płótno do czytania: `{willReadFrequently: true}` i `g.reset()` w każdej klatce, inaczej stan z
  poprzedniej klatki zostaje.
- Nie trzymaj w cache niczego z A ani B. `wireframe` liczy krawędzie (Sobel w pół rozdzielczości, ok. 10 ms) co
  klatkę, bo cache mieszał odcinki.
- Obwódki rozlewających się plam (woda, tusz) gaś razem ze wzrostem plamy (`bleed`: tylko do q<0.55). Inaczej po
  urośnięciu zostaje pierścień przecinający nowy obraz.
- Odsłona musi pokryć kadr przed p = 1. `radiant` w pierwszych wersjach rósł za wolno (`0.08·40^…`: przez 80% czasu
  ludzik miał 300 px, na końcu twarde cięcie), potem `0.15·120^…` zostawiał szczeliny łatane przenikaniem przez
  ok. 1 klatkę – kontrola uznała to za błysk. Dobrane `0.15·320^easeInOut(p)`. Przenikanie na końcu (od p 0,7–0,85)
  tylko jako zabezpieczenie.
- Topnienie: nowy obraz spływa z góry z kroplami o zaokrąglonych końcach. Stary obraz ciągnięty w dół daje kolce,
  nie krople.
- Rozmycie w pełnej rozdzielczości kosztuje ok. 170 ms; miękkie maski licz w 1/4 rozdzielczości i powiększ (`inkBloom`).
- `putImageData` prosto na płótno kadru omija uderzenie kamery i przycięcie przejścia – pisz do płótna poza ekranem,
  potem `drawImage`. `destination-out` na płótnie kadru robi przezroczyste dziury, w filmie czarne – wycinaj poza
  ekranem.
- `whip`: przy rozmyciu ruchu przesunięcie między kopiami ≤8 px, rzadsze kopie czytają się jak duchy.
- `smash`: skala zawsze ≥1, inaczej widać czarne brzegi.
- `fillZoom`: skala wykładnicza już przyspiesza; nie dokładaj `expoIn`.
- `zoomThrough`: bez `live: true` stary obraz jest powiększaną bitmapą (powyżej 10× rozmyty). Z `r0` powiększenie
  musi być ≥ `CAM.coverZoom(r0, cx, cy)`, inaczej otwór do końca nie pokrywa ekranu i ostatnia klatka skacze.
- `expandRect`: nowy obraz od pierwszej klatki nieprzezroczysty w karcie; przy półprzezroczystym przenikaniu
  w karcie widać dwa nałożone teksty.
- Przejścia z `cx, cy` zakładają pozycje przedmiotów ze wzoru; w swojej kompozycji ustaw `cx, cy` na swój przedmiot.

## Format 9:16: założenia 1920×1080 w `transitions.js`
Przejść w obecnej postaci nie używaj w pionie bez przeróbki. Na płótnie 1080×1920 rysowałyby tylko górne 1080 px
i liczyły pozycje dla poziomego kadru.
- Linia 5: `const W = 1920, H = 1080;` – stałe modułu. Wszystkie przejścia używają ich zamiast `o.W, o.H`
  (silnik je podaje, ale funkcje ich nie czytają). `mkc()` tworzy płótna 1920×1080; tak samo silnik
  (`engine.js`: bufory A, B, tmp i uderzenie wokół (960,540)).
- Pełne wypełnienia i pętle po `W`, `H` (`fillRect(0,0,W,H)`, `for (y < H)`, `getImageData(0,0,W,H)`): siatki kafli
  i kropek (`tiles`, `mosaic`, `shards`, `dabs`, `goldLeaf`, `dotBloom`, `ripple`, `pointill`), `filmDirt`, `vhs`,
  `blueBrush` (6 pasów po H/6+90) w pionie pokryją tylko górę kadru.
- Środek skalowania `translate(W/2, H/2)` = (960,540): `smash`, `fillZoom`, `blurPush`, `expandRect` (rozwija się do
  0,0,W,H), `zoomThrough` (`focus` domyślnie [W/2,H/2]).
- Przesunięcia o całą szerokość lub wysokość: `whip` (W), `push` (W albo H), `slidePush` (W), `bands` (skos H·0.35,
  przejazd do W+sk+40), `apsara`, `cutouts`, `flareSweep`, `sunShaft`, `redWedge`, `screamWarp`, `melt` (zakresy
  przejazdu liczone od W lub H plus stałe zapasy: −500/W+700, −700/W+900, W+260/−300 itd.).
- Domyślne punkty startu dla kompozycji 1920×1080: `godRays` (440,300), `swirl` (420,300), `organic` (1500,330),
  `bauhaus` (1010,560), `iris` (992,601), `goldLeaf` (1300,380), `dotBloom` (540,760), `ripple` (1000,600),
  `radiant` (1000,600), `irisFilm` (960,540), `lampGlow` (960,470), `bleed` (580,330), `inkBloom` (560,740),
  `chiaroscuro` (580,300). W pionie x > 1080 jest poza kadrem (`organic`, `goldLeaf`).
- Stałe współrzędne bez parametru:
  - `comicPanels`: 5 prostokątów kadrów sumujących się dokładnie do 1920×1080 (`[0,0,820,520]`, `[820,0,1100,520]`,
    `[0,520,640,560]`, `[640,520,700,560]`, `[1340,520,580,560]`);
  - `redWedge`: obrót wokół (960,540), klin w y 540±330, paski w 540+dv;
  - `chiaroscuro`: winieta wokół (960,540), promienie 1100→80 i 1400→700, snop sięga +900 px w dół;
  - `bleed`: 4 dodatkowe plamy w (1300,420), (520,880), (1650,860), (1050,100), promień q·1400·k;
  - `inkBloom`: losowe plamy w 200–1720 × 120–960, promień q·1500·k, maski 480×270 (W/4 × H/4);
  - `zigzag`: błyskawica x 780→1450, gwiazda w (70,990);
  - `wireframe`: horyzont y = 640;
  - `iris`: zasięg `19 + p·(1159 − 19 + 3·137 + 900)` dobrany do przekątnej 1920×1080 od (992,601);
  - `cutouts`: arkusz 1100 px, przypięte wycinki na y 900, 1060, 260, 520, 300;
  - `flareSweep`: smuga na y 300 (1400 px), plamy y 300→780;
  - promienie dobrane do poziomego kadru: `lampGlow` R 1500, `organic` 2300, `godRays` 520 i promienie 2400,
    `ripple` mianownik 1700 i pierścienie front·2300, `swirl` R 1100, `bauhaus` odjazd −1600, `sunShaft` −900.
- Bez założeń rozmiaru: `cut`, `crossfade`, `same`, `matchCut`, `lensReveal` (koło z `o.lens`).
- `CAM.coverZoom` (z `camera.js`) idzie za `U.setStage`, ale „≈1100/r0” w opisie `zoomThrough` to pół przekątnej
  1920×1080.
