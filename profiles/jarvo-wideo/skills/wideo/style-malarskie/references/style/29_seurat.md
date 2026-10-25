# Puentylizm Seurata (`29_seurat`)

Neoimpresjonizm z 1884 roku („Niedzielne popołudnie na wyspie Grande Jatte”): obraz z jednakowych kropek czystych
farb, które mieszają się dopiero w oku (mieszanie optyczne), z kropkami barwy dopełniającej, prześwitem światła na
granicach jasne/ciemne i kropkowaną ramą malowaną przez samego Seurata. Spokojny, prawie nieruchomy. Jakość wzoru:
★★ (rozpoznawalny, ale z wyraźną słabością); słabość wzoru: za statyczny, siatka kropek zbyt regularna (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 29_seurat --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-29_seurat.jpg`;
kod `$HUASHU/scripts/engine/scenes/29_seurat.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Muzeum, wystawa, lekcja o sztuce albo o kolorze (jak oko miesza barwy): 15–45 s z lektorem.
- Marka „z klasą” i spokojem: herbaciarnia, winiarnia, piknik, park miejski: tło 10–20 s.
- Przekaz „całość z małych części” (społeczność, dane, piksele): odsłona albo przejście 1–3 s.

## Nie do
- Szybki, dynamiczny film: styl jest statyczny (różnica klatek 7,4%). Wybierz `31_haring` albo `26_vaporwave`.
- Swobodny impresjonizm z krótkimi pociągnięciami: `08_impressionism` albo `28_monet`.
- Raster drukarski, pop-art: `13_pop` albo `27_kirby`.

## Cechy stylu (sprawdzalne)
- Stała siatka heksagonalna, wszystkie kropki tej samej wielkości: pitch 10, odstęp rzędów 8.66, r 4.5, każda
  kropka ma stałe przesunięcie ±1,2 px. Ok. 24 tys. kropek.
- 21 czystych kolorów:
  - 14 nasyconych: `#1a2058 #2a3a9a #3f6fd0 #6aaee6 #1f6a52 #2f9a5a #a8c83a #f2cf3a #f08a2a #e0432a #c0306a #7a4aa8 #f8f4e8 #e8b48a`;
  - 7 jasnych (u Seurata „zmieszane z bielą”): `#f6e49a #f6c48a #cfe08a #b0cff0 #f2b8c8 #c99a4a #9a7ac8`.
- Kropki dopełniające: 8% kropek zamienionych na kolor przeciwny (niebieski↔pomarańczowy, zielony↔czerwono-fioletowy,
  żółty↔fioletowy…; razem 21 przypisań).
- Prześwit światła: porównanie z punktem przesuniętym o (+14,+6); gdy różnica jasności >45, z prawdopodobieństwem 45%
  biała kropka po jasnej stronie i ciemnoniebieska po ciemnej.
- Między kropkami widać podkład: podkład z filtrem `blur(4px) saturate(.85) brightness(1.06)`.
- Rama: pas ciemnoniebieski 28 px dookoła, też przepuszczony przez kropki (pojawiają się w nim pomarańczowe kropki
  dopełniające), od środka cienka ciemna linia 3 px.
- Postać we wzorze: granatowo-fioletowa suknia z lat 80. XIX wieku z turniurą (łuk w haku `back`), biały wysoki
  kołnierz, pomarańczowe guziki, mały okrągły kapelusz z czerwonym piórem; o krzesło oparta zwinięta czerwona
  parasolka.
- Krój plakietki we wzorze: `Marcellus-400`; ma polskie znaki.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 29_seurat`. `P` = `PAINT`
   (`paint.js` + `render.js` z `P.pointillism`).
2. Cały podkład płasko, razem z postacią, na płótnie poza ekranem (`P.scratch`, kontekst `willReadFrequently`,
   co klatkę `g.reset()`); ok. 3 ms na klatkę.
3. Pod spód podkład z filtrem `blur(4px) saturate(.85) brightness(1.06)`.
4. Kropki: `P.pointillism(c, podklad, { pal: PAL, comp: COMP, t, fps: 6, shimmer: naWodzie, white: 12, dark: 0 })`.
   Domyślnie `pitch = 10`, `rad = 4.5`, `posJitter = 2.4`, `colorJitter = 40`, `compRate = 0.08`, `flicker = 0.07`,
   `bleed = 45`. `white`/`dark` to indeksy koloru białego i ciemnoniebieskiego w palecie (prześwit światła),
   `shimmer(x,y)` zaznacza wodę. Kropki zbierane w 21 `Path2D` (po jednej na kolor), każda wypełniana raz.
5. Co robi renderer (żebyś wiedział, co stroić):
   - dla każdej pary kolorów (i,j) rzutuje kolor docelowy na odcinek Pj→Pi → ciągła proporcja w, `clamp` do
     [.2,.8]; do odległości dodaje karę `0.004·|Pi−Pj|²`, żeby nie mieszać szarości z czerni i bieli; bierze parę
     o najmniejszej odległości; kropka dostaje Pi, gdy `hash(i,j) < w`, inaczej Pj;
   - wynik trzyma w `Map` pod kolorem skwantowanym do 15 bitów;
   - przed wyborem dodaje do koloru docelowego drganie hash ±20 (R+dj, G+0.8dj, B−0.6dj), więc granice par to
     przeplatane kropki, a nie pionowe pasy;
   - potem kropki dopełniające i prześwit światła.
6. Ramę 28 px rysuj w podkładzie, żeby też przeszła przez kropki.

## Co się rusza
- Ruch główny: picie herbaty. Kropki stoją w miejscu; zmieniają kolor tylko tam, gdzie zmienił się podkład.
- Drżenie powietrza: w 6 fps 7% kropek przeskakuje na kolor pary (średnia różnica sąsiednich klatek 0,45).
- Za oknem Sekwana: żaglówka płynie 40 px/s, parowiec dymi, sylwetka pani z parasolką i małpką. Kropki na wodzie
  losowane od nowa w 6 fps – to połysk wody.
- W pokoju pomarańczowo-czerwony motyl krąży nad stołem (`sin(2.6t)·120`), macha skrzydłami `|sin(20t)|`.
- Różnica klatek 7,4%.

## Przejście-podpis (wejście w ten styl)
- `pointill`, 0,34 s: obraz „krystalizuje się” w kropki jednej wielkości. Siatka pitch 14; kropki rosną od 0 do
  r=6.4 (pierwsze 30% czasu), stary obraz pod nimi blednie do koloru papieru. Moment zmiany koloru kropki
  `0.5·(0.6x/W+0.4y/H)+0.25·hash+0.15` – lewy górny róg pierwszy, z losowością; w chwili zmiany kropka podskakuje
  do ×1.35. Od p>.6 nowy obraz wywołuje się pod kropkami, od p>.7 kropki się zwijają. Co klatkę `getImageData`
  z A i z B (ok. 10 ms każde).

## Wydajność
- Ok. 100 ms na klatkę (ok. 24 tys. kropek).
- Dobór par trzymany w `Map` po kolorze 15-bitowym – nie licz go od nowa w każdej klatce.

## Pułapki
- Kara za mieszanie dalekich kolorów (żeby nie robić szarości z czerni i bieli) potrafi pociąć gradientową ścianę
  na kilka pionowych pasów jednego koloru.
- Nawet przy ciągłej proporcji cała kolumna zmienia parę na granicy i wychodzą pasy. Lekarstwo: drganie koloru
  docelowego (krok 5).
- Paleta bez jasnych kolorów rozkłada jasną ścianę na biel, kolor skóry i rozrzucone niebieskie kropki – wygląda
  jak śnieg. Trzymaj 7 jasnych kolorów.
- 4 fps i 3% zmienianych kropek to prawie stopklatka (różnica sąsiednich klatek 0,1–0,2). 6 fps i 7% dają 0,45.
- Słabość wzoru: siatka jest zbyt regularna. Większe `posJitter` albo lekko różne pitch w strefach to kierunek do
  sprawdzenia na stopklatce.

## Kontrola
- Czy wszystkie kropki mają tę samą wielkość i stoją w miejscu?
- Czy z daleka kolory się mieszają, a z bliska widać czyste barwy i kropki dopełniające?
- Czy na gradientach nie ma pionowych pasów?
- Czy jasne płaszczyzny nie wyglądają jak śnieg?
- Czy w kadrze coś się rusza (woda, motyl, drżenie 6 fps), choć całość jest spokojna?
