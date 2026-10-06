# Kurzgesagt – płaska animacja popularnonaukowa (`kurzgesagt`, w kodzie `y1_kurzgesagt`)

Pojęcie staje się świecącą planetą w świecie, który da się powiększać bez końca: kamera przechodzi między skalami, a w kadrze zawsze coś lekko się rusza. Wzór: `python3 $HERMES_HOME/scripts/gramatyka.py wzor kurzgesagt --arkusz out/wideo/wzor-kurzgesagt.jpg`; start: `python3 $HERMES_HOME/scripts/gramatyka.py szablon kurzgesagt [--format 9:16] -o out/wideo/src/klip-kurzgesagt/spec.json`.

Kod: klip `$HUASHU/scripts/engine/clips/y1_kurzgesagt.js`, przykład `$HUASHU/scripts/engine/examples/y1_kurzgesagt.json` (wnętrze dużego modelu: 3 punkty, `enter` w jedną warstwę, 2 punkty, `highlight`), film pokazowy `$HUASHU/scripts/engine/demos/y1_kurzgesagt/` (MIT). Film pokazowy ma 8 s, 3 ujęcia i 2 przejścia, czyli ok. 3 razy gęściej niż prawdziwy film: bierz technikę, nie tempo.
Potok: `szablon` → polskie teksty i `slowo` → `gramatyka.py sprawdz` → `gramatyka.py render … --klatki 0.5,2,4` (stopklatki) → pełny `render`.

## Kiedy
- Skala i „co jest w środku”: od komórki do galaktyki, od piksela do modelu, „po powiększeniu widać…”. Przejście przez skalę to znak rozpoznawczy tej gramatyki.
- Mechanizmy i systemy: sieć neuronowa, układ odpornościowy, przepływ energii. Niewidoczny proces rysujesz jako świecące cząstki i połączenia.
- Spokojna, popularnonaukowa narracja. Kurzgesagt mówi ok. 168 słów/min, jedno ujęcie między twardymi cięciami to ok. 2 zdania.
- Ton „poważnie, ale sympatycznie”.
- Przykłady: „co jest w środku modelu językowego” (60–90 s, 16:9), jak przelew przechodzi przez system banku (segment 20–40 s explainera fintechu), jak działa szczepionka (lekcja online), architektura produktu B2B w onboardingu, rolka 9:16 „zajrzyjmy do środka…”.

## Nie do
- Prawdziwe osoby, wydarzenia, dowody z archiwum: płaska kreskówka osłabia wiarygodność. Użyj `vox`.
- Kroki i łańcuch rozumowania: lepiej pisać krok po kroku. Użyj `tablica`.
- Wyprowadzenie ze wzorami: `3b1b`. Liczby, które widz będzie sprawdzał: `wykresy`.
- Scena bez ciągłego ruchu. Jakość stylu stoi na tym, że w każdej klatce coś się rusza (oficjalnie ponad 1200 h pracy na jeden film). Okrojony Kurzgesagt wygląda jak tania prezentacja.

## Gramatyka (z pomiarów)
Źródła: dwa filmy z 2025 r. i „The Immune System Explained I” (2014), pomiar klatka po klatce, oraz transkrypcje oficjalnego kursu Kurzgesagt na Skillshare.

- **Długość ujęć.** Ujęcie między twardymi cięciami: mediana 7–9 s, średnio ok. 11,5 s. „Jednostka wizualna” zmienia się jednak co 4,6–6,7 s dzięki przejściom projektowym 0,3–0,6 s. Każde zdanie lektora ma co najmniej jedną zmianę stanu: wyskok etykiety, nowy opis, przekształcenie albo przejście.
- **Cięcia.** Mało: ok. 5 na minutę, na początku zdania lektora, 0–0,2 s przed nim. Muzykę (Epic Mountain) komponuje się do gotowego obrazu.
- **Krzywe (kurs).** Zwykły ruch: 50 klatek (0,83 s przy 60 fps), szybciej 30/20/10 klatek, wyskok 5–10 klatek. Ruch: `MO.k75` = bezier(.75,0,.25,1) (75% influence: miękki start, szybki środek, miękki koniec). Pętle: `MO.easyEase` = bezier(.333,0,.667,1) (Easy Ease 33,3%).
- **Wyskok (pomiar).** Karta rośnie do 90% w 0,25 s, w 20. klatce przestrzał 108% (karta detektora 114%), po ok. 0,5 s wraca do 100%. W klipie etykiety i węzły: `MO.backOut(q, 1.1)`, 0,5 s.
- **Przesunięcia w czasie (kurs).** Elementy tego samego typu co 10–20 klatek, kończyny co 3–4 klatki, przerwa między akcjami 20 klatek. We wzorze: tytuł litera po literze co 45 ms (każda 0,5 s cubicOut), 144 bloki kota z pikseli co 35 ms wg odległości od środka (każdy 0,5 s `backOut(1.4)`), warstwy sieci zapalane co 0,32 s, węzeł wyskakuje w 0,35 s.
- **Stały mikroruch – najważniejsze.** W filmach z 2025 r. odcinki 0,5 s całkiem bez ruchu to tylko 0,3% czasu. Każdy element po wejściu przechodzi w pętlę: pływanie ping-pong 50 klatek, migotanie gwiazd, oddech poświaty, dryf cząstek. Mruganie: 5 klatek zamykanie, 10 otwieranie, w nieregularnych odstępach, oko nigdy nie zamyka się do zera. W klipie: 160 gwiazd migocze z własną fazą (1–3,5 rad/s), planeta pływa 6 px w okresie 4 s, węzły 8 px w okresie 3,4 s + 0,4 s na kolejny węzeł, poświata oddycha, 24 świetliki dryfują, impulsy płyną po liniach.
- **Kamera (pomiar).** Ok. 1/3 czasu zoom, ok. 10% panorama, ok. 5% obrót, częściej oddalanie niż najazd. Powolny najazd w spoczynku: mediana 3–4,5%/s (wzór: 1,00→1,10 w 2,6 s sineInOut, ok. 3,8%/s). W klipie: najazd ok. 2%/s; `highlight` przybliża ok. ×1,45 (pion ×1,35) w 1,2 s `MO.sineInOut`, cel przesunięty o 35% w stronę planety, żeby jej nie uciąć.
- **Skala zawsze logarytmicznie.** `CAM.at` / `CAM.zlerp` dają ten sam przyrost powiększenia w każdej klatce; liniowa interpolacja z jest wolna na początku i gwałtowna na końcu. Scena rysuje się wektorowo od nowa przy każdym z, nigdy nie powiększaj bitmapy. Wejście w okrągły otwór o promieniu r wymaga zoomu ≥ odległość środka otworu od najdalszego rogu ekranu / r (wycentrowany: ok. 1100/r, `CAM.coverZoom`).
- **Przejścia.** Pomiar: przejście skali w „Immune System” trwa ok. 1,4 s, przyspiesza i zwalnia, szczyt prędkości w środku.
  - `matchCut` – najazd do pełnego koloru i wyjazd z nowego świata: we wzorze logarytmiczny najazd na świecący węzeł 0,45 s cubicIn do pełnej żółci, przenikanie ±3 klatki w środku w żółte oko robota (oba światła w lewym górnym rogu, cięcia nie widać), potem wyjazd cubicInOut 1,45 s (42→1) do nowej, dziennej palety. Nie używaj expoOut: pierwsza klatka przeskakuje z 42× na 15×.
  - `lensReveal` – wejście w obiektyw, 1,0 s: logarytmiczny najazd `MO.k75` na obiektyw (1,1→60); następne ujęcie widać tylko w kole obiektywu, koło rośnie do pełnego ekranu, na krawędzi cyjanowa obwódka; nowa scena wypływa z 0,42× expoOut.
  - Szybkie oddalenie odsłaniające: 0,2–2 s, szybki start, długi ogon (pomiar przyrostu zoomu co 0,2 s: 1,074→1,040→…→1,0006). Łączy mikro i makro.
  - Błysk światła ze źródła w kadrze, ok. 0,5 s; ukośne przetarcie obiektem lub pasem światła z liniami prędkości, ok. 0,4 s; powielanie aż do wypełnienia („tyle, że…”), 3–6 s.
  - W klipie `enter`: najazd na węzeł (mieszanka cubicIn i cubicInOut), ok. at + 0,55 × dur pełny ekran w kolorze węzła i przenikanie ±0,05 s do nowej warstwy, do at + dur wyjazd cubicInOut z nowej planety w tym samym kolorze.
- **Paleta 2025 (ciemna, pomiar).** Ciemne piksele 61–68%, mediana nasycenia 0,84–0,89.
  - tło `#05020F` / `#0E0631` / `#25155E`; drugi plan `#191670`, `#3826A3`, `#5F58DB`
  - cyjan `#32BAEE`, `#7DD3DC`; pomarańcz i żółć świecących obiektów `#F48301`, `#E07919`, `#FACC12`, rdzeń poświaty `#F9EF93`
  - magenta `#BE3A95`, `#C83C7F`; światła i biały tekst `#E7DFE1`, `#F9FCFB`
  - zasada: jedno ciemne tło + 2–3 nasycone akcenty w kontraście (pomarańcz–indygo, cyjan–magenta). Rok 2014 to jasnoszare tło i niskie nasycenie; epok nie mieszaj. Zmiana części filmu może zmienić całą temperaturę barw (wzór: trzecie ujęcie w jasnej, dziennej palecie).
  - w klipie: niebo `#05020F` → `#0E0631` → `#2a1a6e`, planeta `#F48301`, linie `rgba(125,211,220,.35)`, impulsy `#32BAEE`, węzły po kolei `#32BAEE`, `#FACC12`, `#BE3A95`, `#5CD0B3`, `#FC6255`, `#8A6CF0` (albo `data.color`).
- **Kształty.** Bez obrysów. Cień to ten sam odcień o stopień ciemniej, światło to biała elipsa albo łuk. Wszędzie zaokrąglenia, organiczne bryły, okrągłe głowy, kończyny jak rurki z zaokrąglonymi końcami. Świecący obiekt zawsze ma poświatę radialną (po to jest ciemne tło). Dwubarwne cieniowanie `TOON.flat`: pas cienia v ≈ (10, 12) px, krawędź światła w ≈ (4, 5) px.
- **Kompozycja.** Obiekt na dolnej linii trójpodziału, nad nim niebo na tytuł i gwiazdy. Paralaksa `CAM.layer` w 5–6 warstwach: gwiazdy d = 0,05, księżyc 0,12, dalekie góry 0,3, bliskie zbocze 0,65, obiekt 1,0, liście na pierwszym planie 1,5 (ciemne, rozmyte `blur(7px)`). Pomiar w filmach: 2–5 warstw.
- **Tekst.** Opis: najpierw cienka biała linia odniesienia, potem tekst znak po znaku ok. 40 znaków/s; jedno zdanie lektora = jeden opis, stoi ok. 3 s, potem znika znak po znaku. Plansza rozdziału co 2–3 min: pełny ekran, słowo po słowie, rozmyte tło. Kapsułka etykiety: duże zaokrąglenie, nasycony jednolity kolor, gruby krój bezszeryfowy.
- **Kroje.** Klip: tytuł `PuHui-Heavy` 76 px (pion 84 px), etykiety `PuHui-Medium` 38 px (pion 44 px), nazwa planety `PuHui-Heavy` 56 px. W Jarvie nakładka `huashu_pl.js` podmienia je na Inter tej samej grubości (800 i 500).
- **Pomiar wzoru (qa).** We wszystkich 3 ujęciach 0% par identycznych klatek (pomiar 2025: 0,3%). 8 klatek skoku w ujęciu 3 (1,04–1,28 s) to zaprojektowany środek wyjazdu 42→1. Ujęcie 1 kosztuje 33 ms/klatkę przez `blur(7px)` (bez rozmycia 9 ms), limit 150 ms.

## Cue w spec
`data` całego spec: `center` (nazwa planety pierwszej warstwy), `flow: true` (węzły w łańcuchu środek→1→2→3, sygnał płynie po kolei, numery na węzłach; do opowieści o kolejności). Każdy cue ma `at` (s, klatka, w której element pierwszy raz widać) albo nasze `slowo` (+ `nth`, `offset`). `kind` spoza tabeli nie daje błędu i nic nie rysuje (tu nie ma `number` ani `image`). Cue z `at` > `duration` jest odrzucany z ostrzeżeniem.

| kind | pola | co robi | przykład |
|---|---|---|---|
| `title` | `text` | Tytuł u góry wjeżdża litera po literze (0,5 s na literę, co 45 ms); za długi: mniejszy krój, najwyżej 2 linie. Znika w 0,5 s (sineInOut) od pierwszego `highlight` albo `enter`. Rysuje się tylko pierwszy `title`. | `{"at":0,"kind":"title","text":"Co jest w środku modelu"}` |
| `point` | `text`, `data.color` (hex akcentu) | Satelita bieżącej warstwy: linia od środka, węzeł i kapsułka z etykietą (wyskok 0,5 s, przestrzał ok. 108%), impulsy na linii. ≤3 węzły na górnym półkolu od lewej, ≥4 na całym okręgu od lewej zgodnie z ruchem wskazówek zegara. Długą etykietę zmniejsza (1 linia) i dociska do kadru. | `{"at":1.4,"kind":"point","text":"Parametry"}` |
| `highlight` | `data.index` (tylko `point` bieżącej warstwy, od 0; domyślnie najnowszy) | Kamera najeżdża na węzeł w 1,2 s, węzeł rośnie i dostaje obwódkę, reszta przygasa w 0,6 s. | `{"at":5,"kind":"highlight","data":{"index":1}}` |
| `enter` | `data.index` (domyślnie najnowszy węzeł), `text` (nazwa nowego środka; domyślnie nazwa węzła), `dur` (domyślnie `1.6`) | Przejście skali: od `at` najazd, ok. `at + 0.55×dur` pełny ekran w kolorze węzła i nowa warstwa, do `at + dur` wyjazd z nowej planety. Kolejne `point` należą do nowej warstwy. | `{"at":4,"kind":"enter","data":{"index":0},"text":"Jedna warstwa"}` |

## Minimalny spec (po polsku)
Lektor: „…najpierw pobieranie, potem indeks, na końcu ranking. To ranking decyduje, co zobaczysz.” Ostatni cue jest przypięty do drugiego „ranking” w narracji: `gramatyka.py` liczy jego `at` z `os_czasu.json` (`film.py narracja`). `slowo` piszesz w formie z narracji, `nth` liczy wystąpienia od 1, `offset` przesuwa w sekundach.

```json
{"grammar":"y1_kurzgesagt","duration":7,"data":{"center":"Wyszukiwarka","flow":true},"cues":[
  {"at":0,"kind":"title","text":"Co się dzieje, gdy szukasz"},
  {"at":1.2,"kind":"point","text":"Pobieranie"},
  {"at":2,"kind":"point","text":"Indeks"},
  {"at":2.8,"kind":"point","text":"Ranking"},
  {"slowo":"ranking","nth":2,"kind":"highlight","data":{"index":2}}]}
```

## Pułapki
- **Obraz staje.** Po wejściu nic się nie rusza i od razu robi się prezentacja. Klip ma mikroruch wbudowany, ale bez nowego cue przez dłużej niż ujęcie (7–9 s) widz traci wątek: każde zdanie lektora ma dostać zmianę stanu. W scenie pisanej samodzielnie każdy element po wejściu przechodzi w pętlę; po wylądowaniu dodaj powolny najazd (we wzorze 4%/s na końcu, bo ostatnie 0,9 s prawie stało).
- **Liniowy zoom albo powiększona bitmapa.** Liniowe z rwie przejście, a zrzut poprzedniego ujęcia powiększony 20 razy rozmywa się w mozaikę. Tylko `CAM.zlerp` i ponowne rysowanie sceny. W przejściu skali nie stosuj expoOut (skok 42→15 w pierwszej klatce), stosuj cubicInOut.
- **Jasna, pstrokata paleta albo obrysy.** Czarny kontur albo średnio jasne tło spychają styl w stronę książeczki dla dzieci lub korporacyjnej ilustracji flat. Cień w tym samym odcieniu, nie szary. Trawa jako wypełnione cienkie trójkąty, nie linie; ciemny liść w rogu wygląda jak plama, więc rozmyj go i rozjaśnij (we wzorze do `#0E0631`).
- **Indeksy liczą tylko bieżącą warstwę.** `highlight` i `enter` z `data.index` wskazującym `point`, który jeszcze się nie pokazał, prowadzą kamerę do pustego miejsca. Dawaj `highlight` po `point`, który wskazuje.
- **Po `enter` pierwszy `point` dopiero po `at + dur`,** inaczej wyskoczy w trakcie wyjazdu z nowej planety.
- **Tytuł znika przy pierwszym `highlight` albo `enter`.** Jeśli ma stać dłużej, przesuń ten cue.
- **Polskie etykiety są dłuższe niż chińskie.** Etykieta ma 1 linię i zmniejsza się, aż się zmieści; trzymaj 1–2 słowa. Nazwa planety (`center`, `text` w `enter`) mieści się w kole: najpierw mniejszy krój, potem 2 linie.
- **Napisy wypalane.** Pod napisy ustaw `safe.bottom` (pion 1080×1920: 700, poziom: 250); klip układa węzły i etykiety tylko między `safe.top` a H − `safe.bottom`.

## Kontrola
- Czy w każdym oknie 0,5 s coś się rusza (`qa_wideo.py`, pary identycznych klatek ok. 0%)?
- Czy przejście skali jest płynne (logarytmiczne), bez mozaiki i bez przeskoku w pierwszej klatce?
- Czy paleta to ciemne tło i 2–3 świecące akcenty, bez obrysów i szarych cieni?
- Czy każda etykieta jest w kadrze i nad pasem napisów (stopklatki `--klatki` przy każdym `highlight` i po `enter`)?
- Czy wyskok węzła i najazd `highlight` padają na słowo lektora (porównaj `at` z `os_czasu.json`)?
