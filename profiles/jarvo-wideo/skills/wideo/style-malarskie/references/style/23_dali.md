# Dalí, surrealizm „Trwałości pamięci” (1931) (`23_dali`)

Pusta złota równina pod granatowo-żółtym niebem, długie cienie, które rosną, miękkie zegary spływające z krawędzi
i słoń na szczudłowatych nogach na horyzoncie. Bryła akademicka, bez konturów: tylko gradient i rozmyty ciemny brzeg
od środka. Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną słabością); słabość wzoru: postać wygląda jak ilustracja
wektorowa (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 23_dali --czasy 0.1,0.6,1.1 --arkusz out/wideo/wzor-23_dali.jpg`;
kod `$HUASHU/scripts/engine/scenes/23_dali.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę,
nie scenę.

## Do czego
- Czas w komunikacji: termin, deadline, oszczędzanie, ubezpieczenia, zegarki, produktywność, prokrastynacja: 5–15 s.
- Surrealistyczny zwiastun: sztuka, festiwal, wydarzenie kulturalne, Hiszpania: 10–20 s.
- Puenta „czas się rozpływa” w filmie o pracy, odpoczynku albo śnie: 3–6 s.

## Nie do
- Postać realistyczna w zbliżeniu (słabość wzoru).
- Intensywne, nasycone kolory i grube kontury: `13_pop`.
- Długi film przy napiętym czasie renderu: 47 ms na klatkę.

## Cechy stylu (sprawdzalne)
- Paleta: niebo `#22407c → #5f88bd → #e9dcae`; morze `#8aa6b8 → #4f6f86`; skały `#e8c27a / #9a6a34`; ziemia
  `#d2ad70 → #7a5129`; mur `#f4ead2 → #cdbf9f`; złoto zegara `#f0d27c / #9a7426`, tarcza `#f6efd6`.
- Brak konturów: bryła z `PAINT.vol(c, path, x0,y0,x1,y1, a, b, occl, blur)` = gradient liniowy + w `clip` rozmyty
  ciemny obrys (cień od środka przez `shadowBlur`). Cała akademicka okrągłość bierze się z tego.
- Długie cienie: sylwetki rzutowane na ziemię ścięciem afinicznym `setTransform(1, 0, −kx, ky, kx·yg, yg·(1−ky))`,
  `yg` to linia styku obiektu z ziemią (mur 700, stół i kot 905, postać 930), `ky` 0.22; całość α 0.55, blur 1,5 px,
  tylko na ziemi (y > 594). Cienie leżą w prawo do tyłu (słońce nisko z lewej, z przodu).
- Miękki zegar `softMap(o, sag)`: współrzędne tarczy (u,v) → ekran. Część v ≤ fold leży na blacie (y ściśnięte do
  0.28–0.32), część v > fold zwisa: `X = cx + u·(1 − flare·q)`, `Y = … + d·(0.62 + 0.3·sag) + zwis Gaussa w środku
  + fala sin`. Rama, tarcza, 12 kresek, dwie wskazówki (próbkowane wzdłuż odwzorowania, więc miękkie) i blik idą
  przez to samo odwzorowanie.
- `flare = −0.12`: ujemne, więc zwisająca część rozkłada się jak miękka tkanina, dolny brzeg okrągły; `drip`
  0.18–0.4. Trzy zegary: na parapecie R72, na brzegu stołu R88, na suchej gałęzi R64 (fold −34, prawie cały zwisa).
- Postać: hiszpańska dziewczyna, jasnoniebieska suknia, biały wykładany kołnierz, złoty kok, rysy cienką
  ciemnobrązową linią. Kot: pomarańczowy gradient, pręgi miękkim półprzezroczystym pędzlem z blur 2 px, oczy
  gradientem radialnym, biała pierś jako gładka elipsa (606,768) 40×92 (nie `K.white`).
- Napisy w filmie pokazowym: `PlayfairDisplay-700i / 400i` (mają polskie znaki), jasne litery z ciemnym cieniem.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 23_dali`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js` (`PAINT.cached`, `PAINT.steam`, `PAINT.grain`, `PAINT.choreo`),
   `render.js` (`PAINT.vol`, `PAINT.castShadow`), `rig.js` (`RIG.drawCup`). Ze sceny skopiuj `softMap`,
   `softClock`, `elephant`, `antWatch`.
2. Tło w trzech cache, bo cień musi leżeć pomiędzy nimi: `dali_bg` (niebo, morze, skały, ziemia) → co klatkę cienie
   → `dali_wall` (fragment muru z oknem i suche gałęzie) → `dali_block` (kamienny stół i stołek) → miękkie zegary →
   postacie.
3. Cienie: `PAINT.castShadow(c, [[yg, g => { sylwetki na czarno }], …], {kx, ky: 0.22, clipY, alpha: 0.55,
   blur: 1.5})`. Wszystkie sylwetki najpierw na jedno płótno, potem całość raz z kryciem, więc na nakładaniu się nie
   ciemnieje.
4. Długość cienia: `kx = 0.85 + 0.6·easeInOut(lt/1.2)`, cień wyraźnie wydłuża się w 1,2 s.
5. Zegary: `sag` rośnie w 1,2 s od 0.1 do 1.4 (`0.1 + 1.3·easeInOut(lt/1.2)`).
6. Postacie: każda część `PAINT.vol`, bez konturów; rysy cienką linią. Na końcu winieta (obraz pod muzealną lampą).

## Co się rusza
- Trzy zegary spływają, wskazówki kręcą się 4,5–6,5 rad/s (w scenie jeden zegar −2,4 rad/s, do tyłu).
- Słoń na szczudłach na horyzoncie: 4 cienkie nogi z przesunięciem fazy π/2 stąpają na zmianę, kolano lekko zgięte
  na 0,52 wysokości, ciało podskakuje 14 Hz, na grzbiecie obelisk; idzie w lewo 70 px/s.
- 9 mrówek chodzi po elipsie wokół pomarańczowego zegarka kieszonkowego.
- Cienie się wydłużają; ogon kota mięknie i opada (koniec `y + q²·34`).
- Picie z kubka; para to dwie bardzo blade smugi.

## Przejście-podpis (wejście w ten styl)
- `melt`, 0,36 s (`TRANSITIONS.melt`): stary obraz zwisa kolumnami po 4 px (`sag = 0.22·edge·e`, rozciągnięcie
  0.3); nowy obraz jest nad powierzchnią cieczy `edge(x)` = opadająca linia (−160 → H+40, easeInOut) + 26 kropli
  z okrągłą główką (szerokość 10–32, długość 60–280, profil `(1−u²)^0.3`, każda z własną fazą) + sinus. Brzeg cieczy
  ma ciemną krawędź (blur 3) i blik. Wyrasta z topnienia: nowy obraz spływa z góry jak ciecz.

## Wydajność
- Mediana 47 ms na klatkę, pierwsza klatka 84 ms. Przejście `melt` 86 ms na klatkę.
- Cache: `dali_bg`, `dali_wall`, `dali_block`; cienie i zegary rysujesz co klatkę.

## Pułapki
- Cień rzucany do widza (`ky > 0`, w dół) zjada dolna krawędź kadru. Słońce nisko z lewej z przodu, cienie w prawo do
  tyłu (`y′ = yg − ky·(yg − y)`).
- Cień leży na ziemi, więc musi być pod murem i stołem: tła nie zamkniesz w jednym cache.
- `flare > 0` z dużym `drip` daje rożek lodów, a nie miękki zegar.
- Za mały zakres `sag` (0.35→1.0) nie daje wrażenia spływania; zostań przy 0.1→1.4 w 1,2 s.
- Ciemny napis na granatowym niebie znika: jasne litery z ciemnym cieniem.
- W przejściu nowy obraz ma spływać kroplami z okrągłą główką; ciągnięcie starego obrazu w dół daje kolce, nie krople.
- Słabość wzoru to postać. Najczęstszy problem wzorów: tło przepuszczone przez renderer wygląda jak styl, a postać
  z samego szkieletu wygląda na doklejoną. Dodaj postaci drobne blaski i odbite światło w cieniach.

## Kontrola
- Czy zegary wyraźnie spływają w 1,2 s i mają okrągły dolny brzeg?
- Czy cienie wydłużają się, leżą w prawo do tyłu i nie ciemnieją tam, gdzie się nakładają?
- Czy nigdzie nie ma konturów (bryła z gradientu i cienia od środka)?
- Czy słoń i mrówki ruszają się w pierwszej sekundzie?
- Dowód z wzoru: różnica klatek 4,6%.
