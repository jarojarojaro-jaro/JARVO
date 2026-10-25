# Kubizm analityczny (`11_cubism`)

Obraz kubizmu analitycznego (1912, w duchu Picassa i Braque'a): przestrzeń z nachodzących na siebie półprzezroczystych
płaszczyzn, każda z jasną i ciemną stroną, w brązach, ochrach i szarościach; postacie pocięte na trójkątne ściany,
które wystają poza kontur; szablonowe litery, gazeta, imitacja drewna. Poznasz go po przezroczystych, przenikających
się płaszczyznach, prostych krawędziach zamiast krzywych i twarzy z dwóch punktów widzenia naraz. Jakość wzoru: ★★
(rozpoznawalny, ale z wyraźną słabością); słabość wzoru: za jasny, za mało dużych ciemnobrązowych płaszczyzn (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 11_cubism --czasy 0.34,0.4,0.46 --arkusz out/wideo/wzor-11_cubism.jpg`; kod
`$HUASHU/scripts/engine/scenes/11_cubism.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Galeria, kawiarnia artystyczna, festiwal sztuki: spot 5–15 s.
- Prasa, wydawnictwo, media („gazeta” w kadrze, nagłówki): zapowiedź 5–10 s.
- Metafora „wielu punktów widzenia” (analiza, badanie, doradztwo, debata): przerywnik 3–6 s w explainerze.
- Marka designerska albo meblowa (drewno, faktury): reklama 10–15 s.

## Nie do
- Czytelne emocje i mimika postaci: `16_2026` albo `25_ghibli`.
- Radosne, nasycone kolory: `13_pop` albo `30_matisse`.
- Długie ujęcia: styl pracuje krótko (w filmie źródłowym 0,47 s); na dłuższe ujęcia najpierw zrób go ciemniejszym
  i bardziej zróżnicowanym (słabość wzoru).

## Cechy stylu (sprawdzalne)
- Płaszczyzny półprzezroczyste z gradientem liniowym: od wierzchołka 0 do losowego innego, trzy przystanki: 25%
  zmieszane z kremem → kolor → 40% zmieszane z ciemnym brązem; α 0,18–0,7.
- Układ tła: 18 dużych płaszczyzn ułożonych ręcznie + 9 wachlarzowych płaszczyzn pod stołem z punktu (1000, 1090)
  (na zmianę jasne i ciemne, α 0,3) + 70 losowych 3- i 4-kątów (poza prawym górnym rogiem na plakietkę).
- Faktury: 4 płaszczyzny kropkowane (siatka rombów 9 px, r 1,6), 4 kreskowane (ukośne linie co 7 px), kartka w linie
  przy lewym brzegu; 9000 krótkich kresek 3–8×1,5 px w stylu Braque'a (55% kremowe α 0,28, 45% ciemnobrązowe α 0,16);
  46 cienkich prostych linii 1,3 px α 0,55 przez cały obraz (passage).
- Imitacja drewna `wood()`: falujące linie wzdłuż dłuższego boku (S/6 linii), przy sękach garb gaussowski
  `14·exp(-(u-k)²/0.01)`, sęk to 4 elipsy. Na stole i desce z prawej (fałszywe drewno grzebieniem jak u Braque'a).
  Oparcie z wikliny: kropki w rombach 10 px + skośne linie w dwie strony.
- Postać pocięta na trójkąty (`facetize`): duże ściany (cell 58), włosy dodatkowo cell 26; kot cell 26. Trójkąty
  wystają poza sylwetkę – brzeg staje się postrzępiony, prostymi odcinkami.
- Twarz jak u Picassa: dwie płaszczyzny skóry jasna i ciemna, przednia połowa twarzy niebieskoszara α 0,82, oko en face
  na profilu, spiralne ucho, czerwone usta; biały kołnierz z dwóch trójkątów i trzech guzików; spódnica z 8 promieni
  od talii i klinów jasnych i ciemnych. Kontur z prostych odcinków (`segs()`), każdy wystaje 10–16 px poza punkty końcowe.
- Kot: sześciokątny kontur głowy z prostych odcinków, ciało z prostych odcinków `bodyPts`, żółte rombowe oczy
  z pionową źrenicą, trójkątny nos z profilu.
- Napisy: „CAFÉ” szablonowe `AlfaSlabOne-400` 104 px z wyciętymi przerwami; gazeta „JOU” `LibreBaskerville-700` 84 px
  + nagłówek 12 px; oba kroje mają polskie znaki. Plakietka roku z filmu źródłowego: `AlfaSlabOne-400` 98 px
  `#1e1b18`, podpis 27 px.
- Paleta: papier `#d6c8ac`, krem `#ece3cf`, ochra `#b8975f`, brąz `#6e5538`, ciemny brąz `#3a2c1e`, szarość `#a8a395`,
  niebieskoszary `#8e9eab`, ciemna szarość `#5a5852`; okno `#c9d3da #8fa3b3 #e4e6e2 #6f8597 #b4c1cb #5f7385`;
  spódnica `#6a7a8b`, rękaw `#3c4857` (ciemniejszy niż spódnica), skóra `#e2cfae`, włosy `#c9a256`; kot `#c8773a` /
  `#e8dfc9`.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 11_cubism`; `P` = `PAINT`, `RIG`, `U`.
2. Tło w całości do cache `cb_bg`: `plane(g, pts, col, alpha, r, dark = 0.4, light = 0.25)` dla wszystkich płaszczyzn,
   potem faktury, kreski Braque'a, passage, `wood(g, x, y, w, h, vertical, seed)`, wiklina.
3. Okno: widok w cache 560×540 (`cb_win`: 55 niebieskoszarych ścian, 3 ukośne smugi światła, wieża Eiffla, łuki mew);
   każda z 4 szyb ma własny clip i inne przesunięcie widoku – ten sam widok przesunięty w czterech szybach = wiele
   punktów widzenia naraz.
4. „CAFÉ”: litery do małej warstwy poza ekranem, potem `destination-out` wycina poziome i pionowe przerwy (litera
   szablonowa; w przerwach prześwitują płaszczyzny tła).
5. Gazeta „JOU” w cache `cb_jou` 300×190 (nagłówek, trzy kolumny szarego „tekstu”).
6. `facetize`: postacie płasko (`RIG` w trybie `fill`, bez linii) do własnej warstwy z
   `getContext('2d', { willReadFrequently: true })`; odczytaj piksele ramki ograniczającej; siatka trójkątów
   z drżeniem (w każdej komórce losowa przekątna); kolor każdego trójkąta z jego środka ciężkości
   ×`(0.8+0.38·rand)`, do tego gradient jasny → ciemny od wierzchołka 0 do 2; trójkąty rysuj bez przycinania
   do sylwetki (pomiń te, których środek ma α<120). Włosy: drugi raz cell 26 tylko na kolorach włosów
   (`only: R>150 && B<130 && R-B>60`).
7. Po pocięciu dorysuj strukturę: twarz, kołnierz, spódnicę, kontur `segs()`; kot jak w Cechach.
8. Na wierzchu 5 płaszczyzn α 0,2 na postaciach (`overPlanes`) – osadzają je w przestrzeni.
9. Każdą klatkę zaczynaj od `g.reset()` na warstwach z odczytem pikseli (nie `clearRect`).

## Co się rusza
- „CAFÉ”: 12 kroków na sekundę (`st=floor(lt·12)`), kolejność liter `CAFÉ / ACFÉ / CAÉF / CFAÉ` na zmianę, w każdym
  kroku każda litera y ±13 px i obrót ±0,11 rad (z hasha).
- Szyby okna: przesunięcie widoku `dx = sin(9lt+1.7i)·18` + drżenie ±3 px 10 razy na sekundę, `dy = cos(7lt+i)·8`;
  w każdej szybie półprzezroczysty trójkąt przesuwa się poziomo 260 px/s.
- Gazeta drży 8 razy na sekundę (obrót ±0,0125 rad, x ±1,5 px), róg zagina się `sin(20lt)`.
- Postacie „gotują się”: wierzchołki trójkątów drżą ±8% komórki 8 razy na sekundę, 16–35% trójkątów zmienia jasność
  ±12%.
- Płaszczyzny na wierzchu przesuwają się `sin(6lt)·8`. Picie z `P.choreo`.
- Odcinek w filmie źródłowym: 0,47 s (2 ósemki).
- Dowód: między lt 0,34 a 0,46 zmienia się 6,9% pikseli.

## Przejście-podpis (wejście w ten styl)
- `shards`, 0,24 s: siatka 9×6 z drżeniem daje 108 trójkątów. Stare kawałki odjeżdżają i obracają się (dx ±80,
  dy ±60, obrót ±0,25, przyciemnienie), nowe lądują z przesunięcia na miejsce (`ease.out`); tło `#cbbfa8`, krawędzie
  2 px `rgba(40,30,20,.35)`.

## Wydajność
- Ciepła klatka: średnio 13 ms, maks. 19 ms; pierwsza (budowa cache) ≈100 ms. Determinizm sprawdzony hashem trzech
  renderów tej samej lt.
- Cache: `cb_bg`, `cb_win`, `cb_jou`; co klatkę tylko szyby, litery, gazeta, cięcie postaci i płaszczyzny na wierzchu.

## Pułapki
- Pierwsza klatka inna niż następne: (1) warstwa z `getImageData` przy pierwszym rysowaniu idzie przez GPU, po odczycie
  Chrome przechodzi na CPU z innym wygładzaniem, więc kolory środków trójkątów są inne; (2) stan kontekstu
  (`lineJoin = 'round'` z `facetize`, `lineCap = 'round'` z `segs`) zostaje do następnej klatki, a pierwsza ma domyślne miter/butt.
  Lekarstwo: własna warstwa z `{willReadFrequently:true}` i `g.reset()` na początku każdej klatki.
- Komórka 34 daje mnóstwo małych trójkątów – wygląda jak model low-poly 3D, nie kubizm. 58 daje duże płaszczyzny
  światła i cienia.
- Drugie cięcie włosów z okrągłym clipem zamieniło pół twarzy w złoto; filtruj kolorem (`only`).
- Rękaw w kolorze spódnicy znika w jej ścianach podczas picia; rękaw ciemniejszy.
- Do poprawy (ze źródła): sylwetka to nadal realistyczne krzywe `RIG`, cięcie zmienia tylko brzeg; głębiej – szkielet
  z łamanych w ramionach, łokciach i kolanach przed cięciem. Oryginał jest ciemniejszy i bardziej kontrastowy.

## Kontrola
- Czy płaszczyzny są półprzezroczyste, przenikają się i każda ma stronę jasną i ciemną?
- Czy w obrazie są duże ciemnobrązowe płaszczyzny (a nie tylko jasne beże)?
- Czy postać jest pocięta na duże ściany, które wystają poza kontur, a krawędzie są proste?
- Czy twarz pokazuje dwa punkty widzenia (profil z okiem en face, niebieska połowa)?
- Czy pierwsza klatka jest identyczna przy powtórnym renderze?
