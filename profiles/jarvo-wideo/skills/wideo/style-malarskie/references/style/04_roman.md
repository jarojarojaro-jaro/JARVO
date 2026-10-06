# Mozaika rzymska (`04_roman`)

Mozaika z Pompejów (79 r. n.e.): obraz z tysięcy kamyczków ułożonych rzędami wzdłuż konturów (andamento), z fugą
zaprawy, białą obwódką wokół postaci i przedmiotów oraz bordiurą z fali witruwiańskiej. Poznasz go po rzędach kamieni
biegnących równolegle do brzegu każdego kształtu, nierównych fugach 1,5–2,5 px i skosie światła na kamieniach.
Ruch wygląda jak w mozaice: kamienie stoją, kolor przepływa przez nie. Jakość wzoru: ★★★ (rozpoznawalny od razu,
gotowy do użycia); słabość wzoru: w małej skali twarz ma mało szczegółów (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 04_roman --czasy 0.4,0.65,0.9 --arkusz out/wideo/wzor-04_roman.jpg`; kod
`$HUASHU/scripts/engine/scenes/04_roman.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Firma od płytek, kamieniarz, łazienki, posadzki: spot 10–20 s, logo albo hasło ułożone z kamyków.
- Restauracja włoska, pizzeria, winiarnia: reklama 10–15 s.
- Muzeum, miasto z historią, przewodnik turystyczny: film 30–60 s.
- Ozdobna rama z płynącą bordiurą wokół ogłoszenia albo tytułu: pętla 5–10 s.

## Nie do
- Drobny tekst, małe ikony, szczegółowe twarze (kamienie je zjadają): `16_2026` albo `style-motion`.
- Sceny z dużymi przemieszczeniami postaci (strefa ruchu rośnie razem z kosztem klatki): `13_pop` albo `16_2026`.
- Złoto i iluminacja zamiast kamienia: `05_gothic`.

## Cechy stylu (sprawdzalne)
- Kamienie według klasy:

  | Klasa | Bok kamienia (px) | Rzędy wzdłuż konturu | Drżenie koloru |
  |---|---|---|---|
  | Ściana | 12 | 1, dalej rzędy regularne | ±8%, 7% kamieni ciemniejszych o 12% |
  | Obwódka (białe halo postaci i przedmiotów) | 11 | 9 (cała obwódka po konturze) | ±5% |
  | Ciało postaci / przedmioty | 10 | wszystkie | ±5% |
  | Twarz postaci, głowa kota | 5 (po poprawce; było 6) | wszystkie | ±4% |
  | Włosy | 8 | wszystkie | ±5% |
  | Obraz z wulkanem | 9 | 2 | ±6% |
  | Bordiura | 7,6 | rzędy wzdłuż boku | ±5% |
  | Napis | 7 | wszystkie | ±5% |
  | Pas ziemi | 13 | 1 | ±6,5% |

- Do tego na każdy kamień szum szarości ±7; 9% kamieni cieplejszych (+12,+4,−8), 7% chłodniejszych (−6,0,+9).
- Fuga `rgb(112,103,92)` ±8, szerokość ~1,5–2,5 px; kamienie „przycięte” przez sąsiadów jak ciosane.
- Skos: do 2,2 px od krawędzi ±16% jasności według iloczynu normalnej ze światłem `(−0.6,−0.8)` (lewa góra jaśniejsza,
  prawa dół ciemniejsza), kopułka `−5%·D1²`, ziarno ±3%.
- Obwódka 44–50 px `#f5f1e8` wokół każdej postaci i przedmiotu (kamienie układają z niej biały brzeg), kontur
  `#46322a` 8 px (twarz 10 px).
- Napis: własne litery o stałej grubości (C z łuku elipsy, A, V, E, T, M z łamanych), kreska 14 px, wysokość 60,
  odstęp 16, rozciągnięty do 600 px; każda kreska ≈2 kamienie szerokości.
- Bordiura: fala witruwiańska od wewnętrznego czarnego pasa, spirala r 24→5, 2,25 obrotu, linia 13, okres 81 px;
  11 rzędów kamieni 7,6 px, narożniki 11×11.
- Paleta: ściana `#e4ddcd`, obwódka `#f5f1e8`, kontur `#46322a`; rama czerwona `#a8322a`, ku środkowi linia ciemnej
  czerwieni `#7c221d`, złota `#d0a23c` i ciemna; wulkan jasny `#7c84b8`, średni `#4e5796`, ciemny `#2f3672`; niebo
  `#9ec0d8`→`#d3e3e4`; stoki `#6f9341` / `#92b254`; ziemia `#cba344`; cyprys `#2b5a2f`; lawa `#d64a22` / `#f2952c`.
  Postać: stola `#efe7d5` z dwoma czerwonymi pasami `#a8322a`, czerwony szal (fałdy `#7c221d`) ze złotą broszą,
  włosy `#dcaa42` z liniami `#9c6c1c`, usta `#a8282a`. Kot `#dc8530`, grzbiet `#c06a24`, pręgi `#9c4818`,
  biel `#f7f2e8`, oczy `#e9c22c`, obroża `#b02a22` ze złotym wisiorkiem.
- Napisy (plakietka roku z filmu źródłowego): `Cinzel-400` 96 px `#1d1a17` w ramce `#f4ede0` z obrysem `#2b2724`,
  podpis `Cinzel-400` 26 px; Cinzel ma polskie znaki, ale napisów w samej mozaice nie składaj krojem (Pułapki).

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 04_roman`; `P` = `PAINT`, `RIG`, `U`.
   Zasada: układ kamieni liczony raz (`build()` w `init`, 206 ms), kolor co klatkę.
2. Wynik `build()`: `ID` (Int32, numer kamienia dla każdego piksela, −1 = fuga) i `SH` (Uint8, jasność skosu,
   128 = 1,0).
3. Mapa struktury: płaski podkład + postacie z klatki 0 (bez ruchomej ręki), zmniejszone do 960×540. Krawędź tam,
   gdzie suma różnic RGB sąsiednich pikseli >34; granice pasów bordiury też są krawędzią.
4. Mapa odległości: dokładna euklidesowa transformata Felzenszwalba–Huttenlochera (dwa przejścia 1D), ~20 ms
   w pół rozdzielczości.
5. Kamienie wzdłuż konturu: kandydaci `|d−(k+½)s|<1.5` dla k < liczba rzędów klasy (pasy poziomic mapy odległości).
   Od nieodwiedzonego kandydata idź po 8 sąsiadach, wybierając kierunek najbliższy poprzedniemu (wygładzenie
   0,6/0,4); kamień stawiaj, gdy odległość od poprzedniego ≥s. Kierunek kamienia = styczna do gradientu odległości.
   Hash przestrzenny pilnuje odstępu ≥0,8× średniego rozmiaru.
6. Dziury: w każdej klasie siatka w cegiełkę (rzędy ±5%, kolumny ±9%), minimalny odstęp 0,86; kamień stawiaj
   wszędzie, gdzie się mieści (bez warunku „tylko daleko od konturu”).
7. Bordiura osobno: każdy bok we własnym układzie, 11 rzędów, kamienie 7,6 px, szerokość wzdłuż boku 0,86–1,14;
   narożniki 11×11.
8. Kształt kamienia i fuga (ważony Voronoi L∞): obrócony kwadrat, każda z czterech półosi `s/2×(1.08–1.28)`, kąt
   ±0,06 rad. Odległość piksela od kamienia `D=max(|u|/h±, |v|/h±)`. Rasteryzacja (w ramce 1,5h) trzyma najmniejsze
   D1, drugie D2 i numer kamienia. Fuga, gdy `D1>1` albo `(D2−D1)·h/2 < g`, `g = clamp(0.1s, 0.75, 1.25)` px.
9. Co klatkę: przerysuj płaski podkład, raz `getImageData`, w strefie ruchu pobierz kolor ze środka każdego kamienia
   (+ stały szum kamienia), wypełnij piksele `kolor×SH>>7`, `putImageData` do własnego płótna poza ekranem, na koniec
   `drawImage` na `c`. Konteksty z `{willReadFrequently:true}`. Około 1 mln pikseli w pętli JS to ~5 ms.
10. Strefy ruchu: w `init` z ramek ograniczających próbek pozy (cup 0→1 co 0,05, sip 0 i 0,15, ogon ±0,75) + 58 px
    zapasu (obwódka i para). Poza nimi statyczna mozaika z klatki 0.
11. Bordiura jako taśma: w `init` pas 2106 px (26 okresów); w każdym rzędzie 11 kamieni o losowych szerokościach
    znormalizowanych do 81 px, więc taśma łączy się bez szwu przy każdej fazie. Co klatkę dla każdego boku
    `c.transform(układ boku)`, clip, `drawImage(strip, BW−2·81+faza, 0)`; narożniki statyczne.
12. Małe rekwizyty jako wklejki (emblema): kubek to `cupSprite` z kamieni 4,4 px (kubek powiększony 1,3×: ciemny kontur,
    złote ciało ciemniejsze z prawej, jasny brzeg, ciemne wnętrze, dwa ucha, stopka), naklejany co klatkę w pozycji
    i kącie z `armPose`. Para: dwie kolumny białych kamieni po sinusoidzie z fugą (`steamTiles`). W podkładzie zostaje
    tylko białe halo kubka.
13. Twarz: kamienie 5 px; oko białe 13×7 + ciemne 8×7 (~3 ciemne kamienie i biel), usta elipsa 8,5×6 (~2 kamienie),
    brwi 6 px ciemnobrązowe. Oczy we wcześniejszej wersji: białe 10×6 + ciemne r 5,5, czyli dokładnie dwa kamienie
    po 6 px.
14. Ręka: własne `armPose`. Kubek po krzywej Béziera 2. stopnia „stół → (1150, 470) → przed usta”, na końcu prawy
    brzeg kubka przy `G.lips[0]`, kąt 0,15 rad (8,6°); dłoń pod stopką (przesunięcie (28, 34) → (3, 44)); IK z ramieniem
    165 / 122 i tym samym kierunkiem łokcia.
15. Kot: skala 0,85 wokół stóp (540, 905) (mapa klas i strefy ruchu skalowane razem), głowa en face: dwa duże żółte
    oczy R17 z czarną pionową źrenicą i ciemną obwódką 7 px, kontur głowy 11 px, w mapie klas kamienie 6 px.
    Ciało `RIG.smooth(K.bodyPts)` (gruszka), pierścienie ogona `setLineDash([9,13])`.

## Co się rusza
- Bordiura płynie zgodnie z ruchem wskazówek zegara: faza `15·lt + 81·easeInOut((lt−0.485)/0.365)` (wolny dryf
  + jeden okres naraz); kamienie jadą razem z wzorem jak na taśmie.
- Wezuwiusz: pas szarej chmury dryfuje w prawo 55 px/s (okres 380 px), 9 kłębów dymu (`#3f3c3a`→`#a29c94`) nisko
  przy niebie w prawo, 12 iskier (kwadraty 10 px, tor paraboliczny), pulsująca lawa w kraterze.
- Picie: `choreo.cup/sip`, kubek po trasie `armPose`; para z białych kamieni, α `1−0.85·cup`.
- Kot: ogon `choreo.tail×1.6` (przy kamieniach 9 px zwykłe wahnięcie ginie); mrugnięcie = pomarańczowe kamienie
  i ciemna linia.
- Odcinek w filmie źródłowym: 4 ósemki (lt 0–0,94 s); w przejściu do następnego stylu scena rysuje się do 1,29 s.
- Dowody: między 0,4 a 0,9 s zmienia się 6,2% obrazu (bordiura 20,4%, postać 8,4%, obraz z wulkanem 4,4%,
  kot 0,8%). Średnia różnica klatek 480×270 w odcinku (klatki 222–253) wzrosła z 1,98 do 4,62 po przejściu na taśmę
  (oryginał 2,90; przy dryfie 42 px/s było 5,5).

## Przejście-podpis (wejście w ten styl)
- `mosaic`, 0,38 s: kafelki 18×34 obracają się jak karty falą od punktu kota `(W·0.27, H·0.72)`; odległość liczona
  z y×1,3, start `d·0.75 + los·0.25`. Każdy obrót trwa 0,16 postępu: szerokość ×|cos|, w pierwszej połowie ciemny
  spód `#2a1c14` na tle `#17110d`, w drugiej nowy kafelek.

## Wydajność
- Po ostatnich poprawkach ciepła klatka: maks. 20,9 ms, p90 17,4 ms, średnio 13,9 ms (1920×1080). `init` 206 ms
  (raz, przy starcie silnika), 17 871 kamieni, z tego 13 067 w strefach ruchu.
- W pełnym filmie klatki z mozaiką (z dwoma przejściami, oba style rysowane naraz) mieszczą się w 40 ms, poza pierwszym
  wejściem w zimny cache innych stylów.
- Cache: warstwa statyczna `rm_static`, `ID`, `SH`, taśma bordiury, `cupSprite`.

## Pułapki
- `putImageData` prosto na `c` omija uderzeniowy zoom na takcie i przycięcie przejścia. Pisz do płótna poza ekranem,
  potem `drawImage`.
- Półosie `s/2×(0.9–1.1)` (kamień mniejszy niż odstęp) dają ~40% fugi i rzadki obraz. Kamień ma być o 8–28% większy
  niż pół odstępu; niech dwusieczna go przytnie. To klucz do faktury.
- Osobny, drobniejszy rozmiar kamieni w strefie ruchu (8,5 px) w spoczynku wygląda jak biała łata. Jedna wielkość na
  całej ścianie (12 px); strefa ruchu ma ten sam układ, tylko co klatkę nowy kolor.
- Za mała strefa ruchu: kamienie na granicy są w połowie nowe, w połowie stare.
- Wolny wzór przesuwany „tylko kolorem” o mniej niż rozmiar kamienia ginie w kwantyzacji. Albo kamienie jadą z wzorem,
  albo przesunięcie jest dużo większe niż kamień.
- Rekwizyt węższy niż 3 kamienie w stałym układzie jest nieczytelny: zrób z niego wklejkę.
- Krój przez `fillText` (np. `Cinzel-700`) w kamieniach 7–9 px łamie cienkie poprzeczki (E wygląda jak F, A traci
  poprzeczkę), a przy ciasnym odstępie litery się sklejają. Tylko grube litery o stałej grubości, kreska ≥2 kamienie.
- Krater 70 px pod ramą obrazu: dym w górę od razu znika za clipem. Prowadź chmury w bok.
- Kamienie ściany 15 px zlewają dłoń i kubek w jedną plamę.
- Pomiar w lt <0,37 s psuje uderzeniowy zoom (wychodzi 68%); mierz 0,4↔0,9.

## Kontrola
- Czy kamienie biegną rzędami wzdłuż konturów, a nie zwykłą siatką?
- Czy fuga ma 1,5–2,5 px i nie zajmuje dużej części powierzchni?
- Czy bordiura w dwóch odległych klatkach jest wyraźnie przesunięta, a kamienie jadą razem z wzorem?
- Czy oko, usta i kubek czytają się na podglądzie w połowie rozdzielczości?
- Czy każdy napis jest z grubych kresek ≥2 kamienie, bez złamanych liter?
