# Bauhaus – plakat i figury Schlemmera (`12_bauhaus`)

Plakat Bauhausu (1923): czysta geometria (koła, kwadraty, trójkąty, grube drążki) w czerwieni, żółci, błękicie i czerni
na kremowym, postarzonym papierze, pionowy napis bezszeryfowy, krata w duchu Mondriana, postacie jak lalki Oskara
Schlemmera z tarczami w stawach. Poznasz go po tym, że nie ma ani jednej krzywej linii obrysu: tylko figury i drążki.
Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: głowa kota przesunięta względem szkieletu
(przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 12_bauhaus --czasy 0.2,0.34,0.46 --arkusz out/wideo/wzor-12_bauhaus.jpg`; kod
`$HUASHU/scripts/engine/scenes/12_bauhaus.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Architektura, wzornictwo, meble, szkoła projektowania: ilustrowana scena 5–15 s z postaciami.
- Wystawa, muzeum, teatr (postacie-lalki jak w „Balecie triadycznym”): zapowiedź 6–15 s.
- Przerywnik w filmie o historii designu albo marki: 2–4 s.
- Bardzo lekki render (5 ms na klatkę): dłuższe pętle i warianty formatu bez kosztu.

## Nie do
- Animowany plakat typograficzny, logo w siatce, hasło na kolorowych blokach bez postaci: `style-motion`
  (`references/bauhaus.md`).
- Propaganda, ukośna dynamika, fotomontaż: `22_constructivism`.
- Ciepło, faktura, ręczna robota: `30_matisse` albo `01_cave`.

## Cechy stylu (sprawdzalne)
- Same figury: koła, kwadraty, trójkąty, grube drążki z zaokrąglonymi końcami; zero krzywych obrysów.
- Papier `#ebe3cf` postarzony mapą fbm 320×180 powiększoną (α 0,5) i dwiema warstwami ziarna (ciemne punkty gęstość
  0,02, α 0,35 – plamy starego druku).
- Kompozycja: cienka ukośna linia (40, 170)→(1900, 840) za oknem, czarny poziomy pas (60, 61, 256, 13), czerwony pionowy
  (292, 105, 24, 468), szare kwadraciki, linia podłogi (345, 898)–(1860, 915), żółty trójkąt prostokątny.
- Typografia: pionowy napis „bauhaus” `Poppins-800` 210 px obrócony `rotate(-π/2)`, rozciągnięty w poziomie do
  dokładnie 820 px, początek (262, 1000), czytany od dołu; drugi napis `Poppins-800` 150 px czerwony `#d3262b`; dwa
  wiersze `Poppins-600` 31 px w prawym dolnym rogu. Poppins ma polskie znaki. Plakietka roku z filmu źródłowego:
  `ArchivoBlack-400` 104 px `#151515`, podpis `Poppins-800` 36 px `#c4202b`.
- Czerwone koło z nierównym tuszem (sitodruk/litografia): kolor + `source-atop` jasne plamy fbm α 0,55.
- Krata Mondriana 4×4 w oknie (wnętrze 366..794 × 126..561, komórki 100×101, szczeliny 9,5); jedna komórka w kratkę
  9 px (papier milimetrowy), jedna z ćwiartką koła.
- Stół z czarnym blatem i chromowanymi rurkami (gradient trzech barw), wspornikowe krzesło Breuera (ta sama ścieżka:
  15 px ciemnoszara, 10 px chrom, 3 px blask przesunięty o 2 px).
- Lalka Schlemmera: głowa koło r70 (`G.A.headC + (14,-18)`); złote „włosy” z figur: wycinek koła na tyle głowy
  (−1,95→1,15 rad), trójkąt nad czołem, kok koło r34, półkole na plecach (`G.A.back`); twarz: czarne pionowe kreski
  oczu (przy mrugnięciu poziome), czerwony kwadrat policzka, krótka czarna kreska ust wewnątrz głowy. Tułów niebieski
  trapez + czarny trapez z tyłu (z oddechem); spódnica czarny wachlarz r178 + niebieski trapez; ręce i nogi to grube
  czarne drążki z zaokrąglonymi końcami, stawy to kremowe tarcze z czarnym pierścieniem 5 px i czarnym środkiem.
  Bliższa ręka z `G.A.shoulder/elbow/hand` (IK picia z `RIG`), dalsza leży płasko na stole.
- Kot z figur: ciało koło r100 (z `K.box`, ok. (536, 805), skaluje się z oddechem), 4 ciemnopomarańczowe poziome pasy
  z lewej (clip do koła), kremowy wycinek z prawej u dołu; głowa kwadrat 104 (`K.headC + (14,48)`, obrót ±0,08 rad
  z fazą ogona), żółte trójkątne uszy, kremowa dolna połowa twarzy, ciemnopomarańczowa opaska na czole, oczy białe
  koła z czarną pionową źrenicą.
- Paleta: papier `#ebe3cf`; czerń `#161514`; czerwień `#d3262b`; błękit `#2a58b4`; żółć `#efc12f`; jasnoniebieski
  `#b9cee0` / `#a6c0da`; szarość `#c6c3bb`; krem `#f2ecdf`; pomarańcz `#ee8a2a` / `#c25a14`; chrom `#c9c9c6`.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 12_bauhaus`; `P` = `PAINT`, `RIG`, `U`.
2. Tło w całości do cache `bh_bg` (papier, plamy `mottle`, linie, pasy, napisy, trójkąt, stół `tube`, krzesło, ziarno).
3. Czerwone koło osobno do cache `bh_red` (520²).
4. Co klatkę: krata (`grid`), drążek-wskazówka (`rod`), łuki (`arcs`), lalka (`doll`, stawy `joint`, drążki `bar`),
   kubek (`mug`), kot (`cat`). Kotwice wyłącznie z `RIG.girl` / `RIG.cat` i `P.choreo`; z `RIG` bierzesz punkty,
   rysujesz figury.
5. Wymiar komórek kraty licz z „szerokość wnętrza − 3 szczeliny”, nie na oko.

## Co się rusza
- Długi czarny ukośny drążek obraca się jak wskazówka: `deg = 28 + 21.5·easeOut(clamp((lt-0.26)/0.22))` (kąty
  zmierzone klatka po klatce w oryginale: 28° → 49,5°). Oś w piaście (1125, 195): piasta stoi, dolny koniec zamiata
  w dół. Drążek 27 px od −432 do +150, równoległa cienka linia przesunięta o 30 px, krótki czerwony drążek o −30 px,
  łuk w piaście obraca się razem.
- Krata Mondriana zmienia kolory: 6 komórek, 13 kroków na sekundę (`step=floor(lt·13)`), każda komórka z inną fazą
  i zmienia się tylko, gdy `(step+2·sw)%9 < 6` (rytm nie jest mechaniczny); kolory tylko czerwony, żółty, niebieski,
  krem, jasnoniebieski, szary.
- 6 współśrodkowych łuków przy czerwonym kole: faza początku `sin(9lt-0.7i)·0.05`, promień ±3 (oddech), długość łuku
  w 0,4 s od 55% do 100% – jak fala dźwięku.
- Para nad kubkiem: jedna sinusoida 2,2 px (26 okresów na 170 px, fala `-18t`), zanikająca gradientem.
- Kot trąca piłkę: prawa przednia łapa `tap = sin(clamp((lt-0.05)/0.16)·π)` wysuwa się 36 px i wraca; niebieska piłka
  r31 w lt 0,13→0,47 toczy się `easeOut` z x 712 do 816, obrót = przesunięcie/promień (widać białą średnicę i kropkę);
  za nią dwie linie ruchu. Ogon: łuk 26 px pomarańczowy + przerywane ciemnopomarańczowe pręgi tej samej szerokości,
  kąt `choreo.tail·0.5`.
- Lalka pije (IK z `RIG`), głowa odchyla się wokół `G.A.neck` o `G.tilt`.
- Odcinek w filmie źródłowym: 0,47 s (2 ósemki).
- Dowód: między lt 0,34 a 0,46 zmienia się 4,9% pikseli (drążek, krata, łuki, kot, piłka, lalka).

## Przejście-podpis (wejście w ten styl)
- `bauhaus`, 0,20 s, środek (1330, 590) – mniej więcej środek czerwonego koła: kompozycja niebieski kwadrat 340
  `#1d4fa3` + czerwone koło r150 `#d0262b` + żółty trójkąt `#f2c81c` obraca się i rośnie wykładniczo
  (`30^e·0.35`), potem odjeżdża w lewo (−1600 px); koło w środku, w którym widać nowy obraz (kremowy papier),
  rośnie (`40^…·30`), aż wypełni ekran.

## Wydajność
- Ciepła klatka: średnio 5 ms, maks. 9,5 ms; pierwsza (budowa cache) ≈85 ms. Determinizm sprawdzony.
- Cache: `bh_bg`, `bh_red`, plamy `bh_m_*`; co klatkę same proste figury.

## Pułapki
- Komórki kraty policzone na 107 px wystają 16 px poza czarną ramę; licz z wnętrza minus szczeliny.
- Czerń wśród kolorów zmiany: gdy komórka staje się czarna, cała krata nagle ciężka, jak zepsuta. Bez czerni.
- Długa czarna kreska ust wystająca poza głowę (jak w oryginale) wygląda na twarzy postaci jak papieros; krótka
  kreska wewnątrz głowy.
- Głowa i ciało kota przesunięte w dół względem szkieletu (kwadratowa głowa na okrągłym ciele); w przejściach głowa
  kota skacze ~50 px względem sąsiednich stylów (słabość wzoru).

## Kontrola
- Czy w kadrze nie ma żadnej krzywej linii obrysu, tylko figury i drążki?
- Czy paleta to tylko czerwień, żółć, błękit, czerń, krem i szarości?
- Czy krata mieści się w ramie i zmienia kolory nierówno (nie wszystkie komórki naraz)?
- Czy stawy postaci to tarcze z pierścieniem, a twarz ma krótkie kreski wewnątrz głowy?
- Czy polski napis jest w `Poppins` (polskie znaki), dokładnie rozciągnięty na zaplanowaną długość?
