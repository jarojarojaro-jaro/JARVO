# Komiks Jacka Kirby'ego, Marvel 1966 (`27_kirby`)

Kosmiczna era komiksu Marvela w druku czterema farbami: papier w kolorze kości słoniowej, płaskie kolory z rastrem
Ben-Day, warstwa koloru przesunięta względem rysunku (niedokładne pasowanie), grube czarne kontury, czarne plamy
cienia z kreskowaniem i „krackle” Kirby'ego – skupiska czarnych kropek energii. Do tego kadry, onomatopeja
i ramki narratora. Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną słabością); słabość wzoru: wygląda bardziej
jak czysty pop-art Lichtensteina niż Kirby – brak kanciastych dłoni, przesadzonej perspektywy i napięcia mięśni
(przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 27_kirby --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-27_kirby.jpg`;
kod `$HUASHU/scripts/engine/scenes/27_kirby.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Zapowiedź premiery gry, komiksu, serialu, konwentu fantastyki: Reels 9:16, 10–20 s.
- Reklama „z przytupem” dla marki młodzieżowej: napój energetyczny, sklep z figurkami, siłownia, e-sport: 15 s.
- Zwrot akcji w explainerze („ALE…!”): wstawka 1–3 s z onomatopeją.
- Wejście bohatera albo maskotki marki: intro 3–5 s.

## Nie do
- Sam pop-art z rastrem, bez akcji i energii: `13_pop` (Lichtenstein, Warhol).
- Spokojna, elegancka marka premium: `24_hopper` albo `30_matisse`.
- Dużo tekstu: ramka narratora mieści jedno krótkie zdanie, onomatopeja jedno słowo.

## Cechy stylu (sprawdzalne)
- Papier `#f4ecd6`, tusz `#141212`.
- Raster Ben-Day (`PAINT.dotPattern(c, key, pitch, r, col, bg, angleDeg)`): ściana jasnoniebieska z rastrem cyjan
  (pitch 9, r 2.7, 15°), podłoga ciemnoniebieska z rastrem fioletowym (pitch 9, r 3.2, 75°), skóra w czerwone kropki
  (pitch 7, r 1.5, 75°).
- Niedokładne pasowanie: cała warstwa koloru narysowana z przesunięciem `drawImage(color, 4, 3)`.
- Kontur 6 px.
- Cień Kirby'ego, światło od okna `LIGHT=(-0.86,-0.5)`:
  - czarny sierp: `path ∩ ¬translate(path, LIGHT·d1)`, d1=14;
  - pas kreskowania: to samo z d2=30, w pasie równoległe linie wzdłuż kierunku światła (odstęp 9 px, grubość 2.6);
  - d1/d2 we wzorze: spódnica 16/34, tułów 14/30, rękaw 10/22, włosy 12/26, kot 16/34, blat 10/18.
- Krackle: skupisko 16–26 czarnych kółek.
- Paleta (z kodu): cyjan `#2a9fd8`, niebieski `#1f3f9e`, magenta `#e0287a`, czerwień `#e3262d`, żółć `#ffd62a`,
  pomarańcz `#f6921e` / `#d2541c`, skóra `#fbd9b8`, ściana `#cfe7f2`, podłoga `#2b3f9c`, drewno `#f2a524`, kosmos
  `#121a52`, energia `#ffe14a` / `#ff8a2a`, planeta `#b04ac8`.
- Kadry: główny kadr 24..1534, po prawej wąski kadr ze zbliżeniem oczu kota.
- Postać we wzorze: czerwona trapezowa sukienka z lat 60., biały kołnierz Piotrusia Pana (dwie elipsy), trzy czarne
  guziki z przodu, czarna opaska (łuk elipsy w układzie obróconej głowy, grubość 11), podwinięte końce włosów
  (rysowane w haku `skirt`, za tułowiem). Krzesło-tulipan Saarinena.
- Krój: `Bangers-400` (onomatopeja 132 px × 0.82, ramki 38 i 34 px). Ma polskie znaki, nie jest podmieniany.

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 27_kirby`. `P` = `PAINT`
   (`/_lib/huashu/lib/paint.js` + `render.js` z `dotPattern`), `RIG` (`lib/rig.js`).
2. Ta sama geometria dwa razy, na dwóch płótnach poza ekranem (`P.scratch`):
   - warstwa koloru: papier, płaskie kolory, raster; potem całą warstwę narysuj z przesunięciem (4,3);
   - warstwa tuszu: białe tło, każda część po kolei „wypełnij białym → cień → czarny obrys 6 px”. Białe wypełnienie
     następnej części zasłania linie poprzednich, więc zostają tylko widoczne linie – `visibleLines` niepotrzebne.
3. Złóż: warstwa koloru, na nią warstwa tuszu w `multiply` (biel tuszu jest przezroczysta).
4. Cień dla dowolnej `Path2D` jedną funkcją (we wzorze `shade(g, path, d1 = 14, d2 = 30, gap = 9)`): `clip(path)`,
   potem drugi `clip` z regułą `'evenodd'` dla „prostokąt pełnoekranowy + ścieżka przesunięta o LIGHT·d”, w środku
   `fillRect` czarnym (sierp) albo równoległe linie (pas kreskowania z d2).
5. Krackle: odległość od środka `R·rnd^0.7`, promień tym większy, im bliżej środka (`R·(0.05+0.2·(1-d/R))`),
   nowe losowanie 12 razy na sekundę, promień pulsuje z `sin(18t+i)`.
6. Kadr ze zbliżeniem: tło magenta + żółty raster + 44 czarne trójkąty linii fokusowych (losowane 12 fps)
   + 6 skupisk krackle wokół głowy kota. Ramki narratora po polsku, np. na dole „ALE KOT PATRZY!”, w lewym górnym
   rogu „TYMCZASEM, PRZY HERBACIE…”. Plakietka z rokiem we wzorze to żółta ramka z czarnym obrysem i przesuniętym
   czarnym cieniem, w szczelinie prawego górnego kadru.
7. Onomatopeja (po polsku, np. „SIORB!”): od lt 0,52 wyskakuje z `outBack`, `Bangers-400` 132 px (×0.82); czarna
   ekstruzja z 7 warstw (każda przesunięta o (0.8d, d)) daje klockowe litery Kirby'ego; górne 46 px czerwonego
   napisu przycięte i wypełnione żółtym (napis dwukolorowy); pod spodem żółta gwiazda wybuchu z 26 szpicami; całość
   drga ±3 px w 12 fps.

## Co się rusza
- Ruch główny: picie herbaty. Linie prędkości: prędkość `|sin(min(1,lt/0.9)π)|`, pod filiżanką 9 czarnych linii
  długości 70–180·v drgających w 12 fps; za łokciem dwa łuki ruchu.
- Krackle: 6 skupisk płynie po strumieniu energii w kształcie S za oknem (`(k/6+0.42t)%1`). Strumień to pas
  z pomarańczową krawędzią i żółtym rdzeniem, z ząbkowanym obrysem tuszem. Para z filiżanki to 4 małe skupiska
  krackle unoszące się w górę.
- Zbliżenie kota: źrenice idą za filiżanką (`lerp(14,-18,cup)`) i patrzą w lewo; linie fokusowe zmieniają się 12 fps.
- Onomatopeja wyskakuje w lt 0,52 i drga 12 fps.
- Różnica klatek 7,5%.

## Przejście-podpis (wejście w ten styl)
- `comicPanels`, 0,42 s: stary obraz najpierw przykrywa raster magenta (`P.dotPattern`, pitch 12, r 3.4, 75°,
  α do 0,85), potem nowy obraz wpada kadr po kadrze – 5 kadrów, start w p 0 / 0.12 / 0.24 / 0.34 / 0.44, każdy
  ze skali 1.18 do 1 z `outBack`; czarne linie kadrów 14 px znikają w p 0,8–1. W indeksie źródła ten styl stoi
  jako „otwarcie” (bez przejścia); `comicPanels` dopisano później. Prostokąty kadrów są wpisane na sztywno
  pod 1920×1080.

## Wydajność
- Ok. 20 ms na klatkę.
- Nic nie trzeba trzymać w cache poza wzorami rastra: `dotPattern` trzyma `CanvasPattern` pod kluczem (wzór zamiast
  rysowania kropka po kropce).

## Pułapki
- Onomatopeja w pełnym rozmiarze w (1000,300) zasłoniła okno i twarz. Przesunięta na (990,318) i zmniejszona do
  0,82. Nie kładź jej na twarzy.
- Duża czarna elipsa po prawej stronie kota w zbliżeniu robiła z niego kota szylkretowego. Daj wąski sierp przy
  krawędzi.
- Pierścień planety rozbij na tylną połowę (rysuj przed planetą) i przednią (po planecie), inaczej pierścień
  przebija planetę.
- Słabość wzoru: obraz jest „czystym pop-artem”. Żeby był Kirby, dodaj kanciaste, klockowe palce, mocniejszą
  perspektywę (skrót, obiekt lecący w widza) i napięcie mięśni.

## Kontrola
- Czy warstwa koloru jest przesunięta o (4,3) względem rysunku (przy krawędziach widać prześwit)?
- Czy cienie to czarne sierpy po stronie przeciwnej do okna, z pasem kreskowania?
- Czy jest krackle i czy zmienia się 12 fps?
- Czy to Kirby, a nie Lichtenstein: dynamiczna perspektywa, kanciaste dłonie, energia?
- Czy onomatopeja i ramki są po polsku i nie zasłaniają twarzy?
