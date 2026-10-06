# Wykresy finansowe (`wykresy`, w kodzie `t3_finance_chart`)

Najpierw układ współrzędnych, potem dane „rosną”, na końcu jedno oznaczenie; jeden kolor dla bohatera, reszta szara; wartości zawsze uczciwe (słupki od 0, jednostka i źródło na wykresie), a animacja decyduje tylko o tym, jak dane się pojawiają, nigdy o tym, ile wynoszą. Wzór: `python3 $HERMES_HOME/scripts/gramatyka.py wzor wykresy --arkusz out/wideo/wzor-wykresy.jpg`; start: `python3 $HERMES_HOME/scripts/gramatyka.py szablon wykresy [--format 9:16] -o out/wideo/src/klip-wykresy/spec.json`.

Kod: klip `$HUASHU/scripts/engine/clips/t3_finance_chart.js`, przykład `$HUASHU/scripts/engine/examples/t3_finance_chart.json` (przychody NVIDIA z pięciu lat obrotowych według raportów 10-K, prawdziwe dane, bez znaczka), film pokazowy `$HUASHU/scripts/engine/demos/t3_finance_chart/` (MIT; dane zmyślone, w każdym ujęciu znaczek). Film pokazowy ma 8 s i 3 ujęcia (2,8/2,7/2,5 s) – to wersja ściśnięta; w filmie jeden wykres to 1–2 zdania lektora. Bierz technikę, nie tempo.
Potok: liczby z `out/wideo/src/fakty.json` (brief Sherlocka) → `szablon` → polskie teksty i `slowo` → `gramatyka.py sprawdz` → `gramatyka.py render … --klatki 0.5,2,4` → pełny `render`.

## Kiedy
- Wzrost przychodów, zysku, liczby użytkowników; kurs akcji; udziały w rynku i zmiany w rankingu; porównanie regionów; punkt zwrotny przed i po wydarzeniu.
- Lektor podaje konkretne liczby, daty i porównania („w pięć lat 8,7 razy tyle co na początku”, „od marca 2023”).
- Fragment ma być wiarygodny: widz zrobi zrzut, prześle dalej i sprawdzi.
- Przykłady: wyniki kwartalne spółki w 60 s, film dla inwestorów, rolka 9:16 z danymi GUS albo NBP (z `safe` pod napisy), porównanie cen w materiale konsumenckim.

## Nie do
- Jedna liczba: bez wykresu, wielka liczba (`number` w `prezentacja` albo `kinetyczna`).
- Dane niepewne albo bez źródła, którego nie chcesz podać: lepiej żadnego wykresu.
- Zasada działania: `3b1b`.

## Gramatyka (z pomiarów)
Źródła: przewodnik stylu wykresów The Economist (2017), paleta FT (`o-colors`), Heer i Robertson 2007 (animowane przejścia w wykresach), D3 bar chart race, Correll i in. 2020 (ucięte osie), Datawrapper, CountUp.js, badanie różnic kulturowych kolorów wzrostu/spadku (Jiang i in. 2014).

- **Długość.** Jeden wykres 2,5–6 s. Struktura opowieści: wprowadzenie → zapalnik → szczyt → domknięcie (Amini i in. 2015, 50 profesjonalnych filmów z danymi).
- **Kolejność.** Układ 0–0,5 s → siatka rysuje się od lewej linia po linii (lag 0,12, `MO.quintOut`) → etykiety osi x wchodzą po kolei z lekkim uniesieniem → dane → zmiana koloru wyróżnienia → oznaczenie. Każdy etap ok. 0,5–1,3 s. Heer i Robertson: złożoną zmianę rozkładaj na etapy, zawsze ease-in-out, krok „tyle, ile trzeba”, ok. 1 s. Osie przed danymi to zwyczaj branży (bez badań, ale widz najpierw widzi „linijkę”, potem „ilość”).
- **Słupki.** Rosną od linii zera, `MO.quintOut`, po kolei (lag 0,22, razem 1,3 s); etykieta wartości jedzie z wierzchołkiem i liczy się razem z nim (`CH.bars`).
- **Linia.** Rysuje się **według x (czasu)**, nie według długości łuku: czas płynie równo, strome odcinki rysują się same szybciej i widać „skok”. Na czole kropka 9 px i etykieta ceny (cyfry o stałej szerokości); pod linią gradient α 0,14 → 0. We wzorze 1,5 s, `MO.smooth` (ostatnia cena „ląduje” na punkcie). Przykład D3 to 5000 ms liniowo – dobre dla samodzielnego wykresu, w filmie skróć do 1,5–2 s.
- **Oznaczenie.** Wyzwalane w chwili, gdy czoło linii **mija** punkt zdarzenia: `tHit = start + czas × smooth⁻¹(udział x zdarzenia)` (odwrotność krzywej przez bisekcję), więc zmiana czasu linii nie wymaga ręcznej poprawki. Kropka wyskakuje (sprężyna d 0,45, bounce 0,25) z jednym pulsem → po 0,12 s rysuje się linia odniesienia → po 0,3 s wchodzi tekst. **Jedno oznaczenie na ujęcie.**
- **Świece.** Po kolei (lag 0,06, w 0,2–1,3 s); korpus rośnie od otwarcia do zamknięcia, potem knoty; słupki wolumenu równolegle; cena w prawym górnym rogu idzie za ostatnią widoczną świecą, w kolorze wzrostu albo spadku względem początku zakresu.
- **Liczby.** Odliczanie `MO.expoOut` (CountUp.js domyślnie 2 s; w filmie 0,9–1,3 s); wszystkie przewijane liczby z cyframi o stałej szerokości (`TY.tabular`), inaczej drgają.
- **Kamera.** Równy, wolny najazd 1 → 1,03 na ujęcie, bez drgań i panoram. W przejściu-najeździe kamera dalej najeżdża wektorowo (nie powiększa bitmapy).
- **Wyścig słupków** (bar chart race; wzór go nie używa): D3 – 250 ms na klatkę kluczową, 10 klatek interpolacji liniowej, 12 słupków; zamiana miejsc ok. 0,5 s; zmiany pozycji rozłożone w czasie, żeby słupki nie skakały naraz.
- **Przejścia (5).**
  1. **`slidePush` (przesunięcie panelu):** nowy panel wjeżdża z prawej, stary wyjeżdża w lewo, prowadzi pionowy pasek w kolorze marki; 0,5 s, `cubic-bezier(.7,0,.2,1)`. Nowy panel buduje układ już w trakcie wjazdu (rośnie czerwona linia, wyłania się tytuł).
  2. **`zoomThrough` na fragment (`live` + `bScale0`):** kamera najeżdża 6× na ostatni punkt danych (stare ujęcie rysuje się dalej wektorowo), nowy obraz (np. ostatnie 20 dni świec) wchodzi przenikaniem z 0,6×, a jego główny obiekt (ostatnia świeca) stoi w punkcie najazdu. Bez okrągłego otworu **ustaw `bScale0`**, inaczej nowy obraz wygląda jak mała karta unosząca się w środku.
  3. **Przekształcenie wykresu (morph):** te same dane w innej formie (słupki → punkty → linia): najpierw przesuń na miejsce, potem zmień kształt (Heer i Robertson: punkty → słupki najpierw w poziomie, potem kształt; skumulowane → grupowane najpierw szerokość, potem opadanie). **Nigdy między różnymi wskaźnikami** (słupki przychodów w linię kursu sugerują tę samą skalę).
  4. **Nowa podziałka osi:** gdy zmienia się zakres, najpierw podziałka (stara gaśnie, nowa wchodzi), dopiero potem dane.
  5. **Twarde cięcie przy niezmiennym układzie:** ten sam układ, inny wykres; czerwona linia i tytuł stoją, zmienia się treść. Najczęstsze w filmach The Economist.
- **Układ.** **Czerwona linia u góry (8 px) + czerwona chorągiewka w lewym górnym rogu (96×22) + pogrubiony tytuł (jedno zdanie-wniosek) + podtytuł (wskaźnik i jednostka) + źródło w lewym dolnym rogu.**
- **Paleta.** Tło białe `#FFFFFF` (wykresy The Economist w sieci) albo łososiowe FT `#FFF1E5`. ECON RED `#E3120B`, niebieski `#006BA2`, turkus `#3EBCD2`, zielony `#379A8B`, żółty `#EBB434`, szary `#758D99`, czarny `#0C0C0C`. **Wyróżnienie: jeden kolor dla bohatera, reszta jasnoszara** (we wzorze ostatni słupek zostaje niebieski, reszta przechodzi w `#C6D2D8`; Datawrapper: „przygaś drugorzędne dane szarością”).
- **Siatka i linie.** Tylko poziome linie siatki, cienkie szare (α 0,13, 1,5 px); **tylko linia zera czarna i ciągła** (3 px); wartości osi y po prawej, nad liniami siatki. Główna linia danych 5 px, średnia krocząca 4 px, linia odniesienia oznaczenia 2 px. Kształty: prostokątne słupki, linia z kropką na końcu, świece z knotami, mała kropka z linią odniesienia.
- **Kolory wzrostu i spadku.** W Chinach kontynentalnych czerwony = wzrost (tak jest w oryginale); w Hongkongu, Europie i USA zielony = wzrost. **W Jarvie domyślnie `upDown: "us"`**: zielony `#1B9E5A` = wzrost, czerwony `#E3120B` = spadek. Wersja przyjazna daltonistom: niebieski/pomarańczowy i symbole ▲▼.
- **Źródło.** Szary źródła w oryginale `#7c868b` ma na bieli 3,7:1; nakładka rysuje go `#5f696e` (5,6:1, pomiar kontrastu przechodzi).
- **Kroje.** The Economist używa Econ Sans (Condensed). Klip: liczby i etykiety osi Roboto Condensed (`RobotoCondensed`), tekst PuHui-Medium/PuHui-Bold → w Jarvie Inter 500/700. Tytuł 700, podtytuł i osie 400; etykiety osi najmniejsze, źródło najmniejsze i najjaśniejsze (75% czerni).
- **Tekst.** Tytuł to wniosek; podtytuł to wskaźnik i jednostka („przychody roczne, mln zł”); mnożnik musi dać się policzyć z liczb na wykresie (107,9 ÷ 12,4 = 8,70); oś nie od 0 – napisane w podtytule („oś Y nie zaczyna się od 0”); źródło w lewym dolnym rogu; dane zmyślone mają w każdym ujęciu znaczek „dane przykładowe” w prawym dolnym rogu.
- **Zgranie z lektorem.** Liczba **staje w chwili, gdy lektor ją wypowiada**: słupek dorasta, a etykieta zatrzymuje się na 107,9 dokładnie na „sto siedem przecinek dziewięć”; oznaczenie wyskakuje, gdy czoło linii mija wydarzenie, dokładnie na „po premierze w marcu 2023”. Najpierw chwile z lektora, potem od nich początek animacji.
- **Wydajność (qa wzoru).** 1,3–1,9 ms na klatkę średnio, render deterministyczny. 3 „skoki” w ujęciu 1 to zamierzona zmiana koloru słupków i wyskok oznaczenia.

## Cue w spec
`data` całego spec:
- `title`, `unit` (podtytuł: wskaźnik i jednostka; za długi – najpierw trochę mniejszy, potem 2 linie), `source` (lewy dół; jak wyżej i omija znaczek), `badge` (rysowany tylko, gdy podany: prawy dolny róg, np. `"dane przykładowe"`; przy prawdziwych danych go nie pisz);
- `chart`: `"bar"|"line"|"candle"`; `series`: `[{label, value, color?}]` albo świece `[{label, o, h, l, c}]` (`color` = kolor tego słupka, żeby zgadzał się z tym samym wskaźnikiem w innych miejscach filmu);
- `decimals` (etykiety słupków i punktów, domyślnie 1), `prefix`, `suffix`; `highlight`: `{index, text, sub}`; `colors`: `{main, accent, dim}` (domyślnie słupki `#006BA2`, linia `#E3120B`, `dim` `#C6D2D8`);
- `upDown`: `"cn"` (czerwony = wzrost; domyślny w kodzie) albo `"us"` (**u nas zawsze**; `gramatyka.py` wstawia go sam, gdy go nie ma, a `cn` ostrzega); `xAxis`: `"category"|"time"` (słupki domyślnie kategorie, każdy ma nazwę; linia i świece domyślnie czas, etykiety przerzedzone).

Każdy cue ma `at` (s, klatka, w której element pierwszy raz widać) albo nasze `slowo` (+ `nth`, `offset`); reszta w `kontrakt-spec.md`. Treść tylko między `safe.top` a H − `safe.bottom` (wiersz źródła stoi nad pasem napisów). W pionie małe teksty są o 20% większe. Przy `--alfa` czarny tekst dostaje białą poświatę (czytelny na ciemnym tle).

| kind | pola | co robi | przykład |
|---|---|---|---|
| `title` | — | Od `at` układ: czerwona linia, chorągiewka, tytuł, podtytuł, źródło, znaczek (ok. 0,6 s). Bez cue `title` układ i tak stoi od 0 s. | `{"at":0,"kind":"title"}` |
| `bar` / `line` / `candle` | `dur` (domyślnie z liczby punktów: słupki 0,22 s × n, linia i świece 0,06 s × n, w granicach 0,9–2,2 s); słupki: kilka cue `bar`, każde z `data.index` (liczba albo tablica) = te słupki rosną dopiero od tego `at` (0,7 s albo `dur`), żeby każdy słupek trafił w swoje słowo | Siatka od min(`at` tytułu + 0,25, `at` − 0,4) przez 0,6 s, etykiety x 0,15 s później; od `at` rosną dane. Słupki zawsze od 0; linia i świece z osią nie od 0 dostają w podtytule dopisek automatycznie. Ujemny słupek: wartość pod nim, oznaczenie idzie w dół. Za długie nazwy kategorii: mniejszy krój, potem dwa rzędy na przemian; oznaczony słupek zawsze ma nazwę. Miejsca po przecinku na osi wynikają z kroku podziałki. Etykiety wartości tylko do 14 słupków. Pierwszy z tych cue ustala typ wykresu (przed `data.chart`). | `{"at":1.2,"kind":"bar"}` |
| `highlight` | `text`/`sub` zastępują `data.highlight`; `data.index` który punkt (domyślnie `data.highlight.index`, potem ostatni) | W klatce `at` wyskakuje kropka, potem linia odniesienia i tekst; bohater w kolorze `accent`, reszta przechodzi w `dim` (0,4 s). Gdy tekst ukośnie wpadłby na inne słupki albo ich wartości, staje prosto nad tym słupkiem; brak miejsca u góry → dodatkowa działka podziałki. **Liczy się tylko pierwszy `highlight` w spec.** | `{"at":4,"kind":"highlight","data":{"index":2},"text":"najwięcej"}` |
| `number` | jak w `kontrakt-spec.md`: `data.value`, `prefix`, `suffix`, `decimals` (domyślnie **0**, nie dziedziczy `data.decimals`); opis w `text` albo `sub` | Wielka czerwona liczba w pasku zarezerwowanym nad wykresem (150 px), do prawej, opis z lewej strony liczby; nie zasłania czoła linii. Liczy od `at` − 0,9 s, staje w `at`. `data.label` nie jest tu rysowany. | `{"at":5,"kind":"number","text":"ostatnie zamknięcie","data":{"value":259.97,"suffix":" zł","decimals":2}}` |

## Minimalny spec (po polsku)
Dane zmyślone, więc znaczek i źródło „dane przykładowe”:
```json
{"grammar":"t3_finance_chart","duration":6,"data":{"title":"Firma A wydaje na badania najwięcej","unit":"nakłady na badania w 2024 r., mln zł","source":"Źródło: dane przykładowe","badge":"dane przykładowe","chart":"bar","upDown":"us",
  "series":[{"label":"A","value":120},{"label":"B","value":86},{"label":"C","value":43}]},"cues":[
  {"at":0,"kind":"title"},{"at":1,"kind":"bar"},{"at":3.5,"kind":"highlight","data":{"index":0},"text":"najwięcej"}]}
```
Przy prawdziwych danych: `series` z `fakty.json`, `source` po polsku z nazwą raportu, bez `badge`, `data.highlight` z mnożnikiem policzonym z tych liczb. Każdy słupek rośnie na swoje słowo lektora (etykiety serii `2022`, `2023`, `2024`), oznaczenie na wniosku:
```json
"cues":[
  {"at":0,"kind":"title"},
  {"slowo":"2022","kind":"bar","data":{"index":0}},
  {"slowo":"2023","kind":"bar","data":{"index":1}},
  {"slowo":"2024","kind":"bar","data":{"index":2}},
  {"slowo":"rekord","kind":"highlight"}]
```

## Pułapki
- **Ucięta oś.** Słupki zawsze od 0; linia i świece mogą nie od 0, ale musi to stać na wykresie. Lie Factor Tufte'a (efekt na wykresie ÷ efekt w danych) poza 0,95–1,05 = zniekształcenie; znak przerwania osi nie ratuje przesady (Correll i in. 2020).
- **Automatyczny dopisek osi jest w kodzie po chińsku.** Klip sam dopisuje do podtytułu `纵轴未从 0 开始`; nakładka rysuje go po polsku („oś Y nie zaczyna się od 0”, zwykła spacja). Jeśli na stopklatce widzisz chińskie znaki, to tekst spoza słownika nakładki (`huashu_pl.js`, `SLOWNIK`): zgłoś, a do czasu poprawki nie oddawaj klipu.
- **Za dużo kolorów, wszyscy są bohaterami.** Jeden kolor opowiada, reszta szara; napisz, co znaczy czerwony i zielony.
- **Animacja tak efektowna, że nie da się odczytać liczby.** Bez skaczących słupków, słupków 3D i obracanych kół; etapy, ease-in-out, krok ok. 1 s; po zatrzymaniu liczby co najmniej 0,5 s postoju.
- **Mnożnik źle nazwany.** 8,7 razy tyle co na początku to wzrost **o** 770%, nie „wzrost o 8,7 raza” (wyłapane w odbiorze wzoru). Mnożnik z tytułu musi wyjść z liczb na wykresie.
- **Liczby między ujęciami się nie zgadzają.** We wzorze koniec linii miesięcznej (268) nie pasował do ceny z wykresu dziennego (286,40), choć najazd szedł właśnie na ten punkt. Liczby z sąsiednich ujęć muszą wynikać jedna z drugiej.
- **Dwie wielkie liczby naraz.** Etykieta czoła linii i licznik nachodziły na siebie; etykietę czoła zdejmij w 0,2 s od startu przejścia.
- **Etykiety na danych, za krótki postój.** Podpis „wolumen” zasłaniał świece, słupki wolumenu dochodziły do linii siatki; ekran świec był nie do przeczytania w 2 s. Poprawki: etykieta w pustym miejscu, wolumen znormalizowany z odstępem 6 px, bez średniej, świece w 1,3 s, oznaczenie w 1,75 s, postój 0,75 s.
- **Oznaczenie na linii nie czeka na czoło.** W klipie `highlight` wyskakuje w swoim `at`, a nie gdy linia dojdzie do punktu. Ustaw `at` nie wcześniej, niż czoło mija punkt (linia ma `MO.smooth`, więc jej środek przychodzi później niż przy ruchu liniowym; sprawdź `--klatki`).
- **Drugi `highlight` nic nie robi.** Klip bierze tylko pierwszy. Dwa wnioski = dwa klipy.
- **Kolor wzrostu kontra kolor marki.** Gdy marka jest czerwona albo zielona, rozważ niebieski/pomarańczowy z ▲▼ i napisz to w podtytule.
- **Pion i napisy.** We wzorze w pionie oznaczenie (y ≈ 1460) trafiało w pas napisów (1400–1520). Ustaw `safe.bottom` (pion 490–570, poziom 160–220).
- **Tekst w kadrze kontra wypalone napisy.** Przy nakładaniu przesuń napisy albo w tym fragmencie ich nie wypalaj.

## Kontrola
- Czy słupki zaczynają się od 0, a oś nie od 0 jest opisana po polsku?
- Czy tytuł to wniosek, a mnożnik z tytułu wychodzi z liczb na wykresie i jest dobrze nazwany („razy tyle” zamiast „o tyle razy”)?
- Czy jednostka i źródło stoją na wykresie, znaczek „dane przykładowe” jest tylko przy zmyślonych danych, a każda prawdziwa liczba zgadza się z `fakty.json`?
- Czy jest jedno oznaczenie, jeden kolor bohatera, reszta szara, a kolory wzrostu i spadku są takie, jak napisano?
- Czy liczba staje dokładnie na słowie lektora, stoi co najmniej 0,5 s i ma polski zapis (przecinek dziesiętny, spacja tysięcy)?
