# Kusama, nieskończone kropki (`21_kusama`)

Czerwony pokój cały w białych kropkach, które oddychają falą rozchodzącą się od jednego punktu, żółta dynia w czarne
kropki i okno jak lustrzany pokój nieskończoności z kolorowymi światłami („Infinity Mirror Room”, dynia z 1994).
Jedna funkcja fali ożywia cały ekran. Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru:
postać ma ten sam kolor co ściana i trzyma się tylko na konturze (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 21_kusama --czasy 0.3,0.9,1.15 --arkusz out/wideo/wzor-21_kusama.jpg`;
kod `$HUASHU/scripts/engine/scenes/21_kusama.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę,
nie scenę.

## Do czego
- Moda, kosmetyki, sztuka współczesna, galeria, concept store, festiwal: 5–10 s.
- Hipnotyczna pętla do social 9:16 (kropki oddychają bez końca): 6–15 s.
- Finał „rozpuszczenia w kropki” jako wejście do logo albo hasła: ostatnie 0,3–0,5 s.

## Nie do
- Pop art z rastrem Ben-Day i komiksowym konturem: `13_pop`; puentylizm: `29_seurat`.
- Kadr, w którym postać musi być wyraźna na tle (słabość wzoru), jeśli nie zmienisz kolorów tła albo stroju.
- Podpisywanie filmu nazwiskiem artystki albo sugerowanie jej udziału: bierzesz technikę, nie nazwisko.

## Cechy stylu (sprawdzalne)
- Fala na wszystkich kropkach: promień × `wave = 0.82 + 0.28·sin(dist·0.012 − 6t)`, `dist` liczone od kota
  (540,760). Cały pokój pulsuje kręgami od tego punktu, jakby oddychał.
- Ściana: dwie siatki sześciokątne, duże kropki 30 px co 104 px i małe 10 px przesunięte, rozrzut ±25–50%; każda
  kropka lekko eliptyczna z losowym obrotem (jak malowana ręcznie).
- Podłoga: 9 rzędów, bliżej większe (6→28 px) i rzadsze, spłaszczone do 0,42 (perspektywa).
- Kolory: czerwień `#d8181e`, ciemna czerwień `#a80e14`, biel `#fbf6ee`, żółć `#f6d02a`, czerń `#141210`, skóra
  `#f6dcc8`.
- Czerwona sukienka w białe kropki 13 px co 52 px; kot: na pomarańczowym białe kropki, na białym czerwone. Kropka na
  policzku (malowanie ciała jak u Kusamy), kokarda czerwona w białe kropki. Stół i rama okna żółte w czarne kropki.
- Okno: siatka świateł 13×7×3 w 6 kolorach (`#ff3a4a #ffd43a #3aa8ff #6aff7a #ff7ad0 #ffffff`), leci do kamery 0,3/s
  w pętli, rzut perspektywiczny F150; każde światło to mały pełny rdzeń + poświata 3,2× w `lighter`.
- Dynia: 5 płatów-elips rysowanych od zewnętrznych do środkowego; kropki w rzędach, największe w środkowej kolumnie
  (9,5 px), mniejsze ku brzegom i w górę/dół; rozmiar też idzie za falą.
- Postacie: płaski kolor + cienka czarna linia (u postaci 4,5 px).
- Napisy wzoru: tytuł `LXGWWenKai-500` → u nas `Caveat-600` (nakładka), podtytuł `Poppins-800` (ma polskie znaki);
  tabliczka to żółta pigułka w czarne kropki.

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 21_kusama`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js` (`PAINT.scratch`), `kit.js` (`KIT.nearArm`, `KIT.choreo`,
   `KIT.label`), `rig.js` (`RIG.girl`, `RIG.cat`, `RIG.drawGirl`, `RIG.drawCat`). Ze sceny skopiuj `wave`, `grid`
   (siatka sześciokątna z rozrzutem) i `dot` (elipsa z obrotem).
2. Położenia kropek (ściana, podłoga, światła) policz raz przy starcie; co klatkę liczysz tylko promień z falą.
3. Kolejność: pokój → okno-lustro (światła posortowane od najdalszych) → stół w kropki → dynia → postacie → para
   z kropek → finał.
4. Postacie na osobnym płótnie: wypełnienie (`RIG.drawCat` / `RIG.drawGirl` w `mode: 'fill'`), kropki w `clip` do
   sylwetki, kontur `mode: 'line'`, bliższa ręka `KIT.nearArm` z tym samym wzorem kropek.
5. Kropki na sukience przesuwaj w dół: `clip` do sylwetki, przesunięcie `y` modulo okres dwóch rzędów.

## Co się rusza
- Cała przestrzeń oddycha falą od kota (jedna funkcja na wszystkie kropki).
- Kropki na sukience pełzną w dół 46 px/s (wychodzą dołem, wracają od talii), na kocie też w dół.
- Światła w oknie lecą do kamery (0,3/s, pętla).
- Dynia oddycha: skala `1 ± 0.025·sin(5t)` od podstawy.
- Para: 7 białych kropek rośnie i blednie w drodze w górę.
- Finał „samorozpuszczenie”: `lt` 1,0–1,26 czerwona warstwa narasta, siatka sześciokątna 120 px rośnie kręgami od
  kota do 0,47 odstępu; potem ok. 0,15 s same kropki lekko oddychają. Ostatnia klatka: czerwone tło w białe kropki.

## Przejście-podpis (wejście w ten styl)
- `dotBloom`, 0,48 s, środek (540,760) (`TRANSITIONS.dotBloom`): siatka sześciokątna 58 px, kropki rosną od kota
  według odległości (`outBack`, do 0,74 odstępu, czyli do pełnego pokrycia), w kropkach (`clip`) jest nowy obraz.
  Niepełne kropki mają biały obrys, który znika. Wyrasta z kropek zarastających świat.

## Wydajność
- 4–28 ms JS na klatkę.
- Położenia kropek liczone raz; najdroższe są kropki w `clip` postaci i światła z poświatą.

## Pułapki
- Fala bez górnej granicy promienia daje biały ekran. Ogranicz promień i skończ na siatce kropek, nie na jednolitym
  kolorze.
- Finał potrzebuje klatek stojących: zostaw ok. 0,15 s spokojnego oddechu na końcu (pierwsza wersja go nie miała).
- Losowo rozrzucone światła z dużą poświatą to bokeh, a nie lustro: regularna siatka i małe pełne rdzenie dają
  wrażenie nieskończonych odbić.
- Sukienka i ściana są czerwone w białe kropki, więc postać rozpływa się w tle. Kontur postaci 4,5 px, a z białej
  części kota usuń czerwone kropki, żeby granica pomarańczowe/białe została czytelna.
- Okres przesuwu kropek na sukience to dwa rzędy (`52·0.87·2`), bo co drugi rząd jest przesunięty. Okres 52 daje
  skok całego wzoru przy zawinięciu.

## Kontrola
- Czy wszystkie kropki oddychają jedną falą z jednego punktu?
- Czy postać jest czytelna na tle (kontur, kontrast)?
- Czy przesuw kropek na sukience nie skacze przy zawinięciu?
- Czy finał kończy się na siatce kropek, a nie na jednolitym ekranie?
- Dowód z wzoru: różnica klatek 0,45↔0,9 s = 17,3%, mediana sąsiednich 2,98%.
