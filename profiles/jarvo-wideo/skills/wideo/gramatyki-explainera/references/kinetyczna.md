# Typografia kinetyczna (`kinetyczna`, w kodzie `y5_kinetic_type`)

Słowa są aktorami: każde kluczowe słowo wpada na akcent, główne słowo jest tak duże, że czyta się je w mgnieniu oka, a w kadrze zawsze jest jeden punkt skupienia; kamera i tło ciągle się ruszają, słowa po wylądowaniu stoją. Wzór: `@@PY@@ "$HERMES_HOME/scripts/gramatyka.py" wzor kinetyczna --arkusz out/wideo/wzor-kinetyczna.jpg`; start: `@@PY@@ "$HERMES_HOME/scripts/gramatyka.py" szablon kinetyczna [--format 9:16] -o out/wideo/src/klip-kinetyczna/spec.json`.

Kod: klip `$HUASHU/scripts/engine/clips/y5_kinetic_type.js`, przykład `$HUASHU/scripts/engine/examples/y5_kinetic_type.json` (tytuł z `sub`, trzy etapy z `label` i `key`, `highlight` na ostatnim), film pokazowy `$HUASHU/scripts/engine/demos/y5_kinetic_type/` (MIT). Film pokazowy: 8,5 s, 60 fps, muzyka 120 BPM, 4 ujęcia; jego gęstość zdarzeń (jedno na ósemkę) jest dwa razy większa niż w filmach z tekstem piosenek: bierz technikę, nie tempo.
Potok: `szablon` → polskie teksty i `slowo` → `gramatyka.py sprawdz` → `gramatyka.py render … --klatki 0.5,2,4` → pełny `render`.

Rodowód: czołówka Saula Bassa do „Północ, północny zachód” (1959) uchodzi za pierwsze duże użycie ruchomej typografii w filmie fabularnym; po 2008 r. teledyski z tekstem w After Effects zrobiły z niej standard explainerów, list, cytatów i otwarć z liczbą.

## Kiedy
- Otwarcia i plansze rozdziałów explainera, listy, „X etapów”, „3 powody”: informacja to **struktura** (ile, który, od czego do czego), nie obraz.
- Cytaty, hasła, wniosek w jednym zdaniu: widz zapamięta lepiej, gdy przeczyta, niż gdy tylko usłyszy.
- Liczby: jedna liczba, jedno ujęcie, liczba gra główną rolę.
- Narracja z wyraźnymi słowami akcentowanymi („to nie pisanie kodu, tylko **mówienie, czego chcesz**”).
- Przykłady: otwarcie webinaru (5–10 s), rolka 9:16 „3 błędy przy…”, plansza rozdziału w kursie, liczba na otwarcie raportu (z `fakty.json`), hasło na końcu spotu.

## Nie do
- Opowieść i emocje: bez twarzy trudno o empatię. Użyj `historyjka`.
- Długie wyjaśnienia z pełnym ekranem tekstu: widz czyta zamiast słuchać i nie nadąża. Ponad 30–60 s samej typografii męczy; używaj jej na otwarcie, plansze rozdziałów i wniosek.
- Listy dłuższe niż 5 punktów: statyczna infografika omawiana spokojnie.
- Produkt i kroki: `prezentacja`; dane z osiami: `wykresy`.

## Gramatyka (z pomiarów)
Źródła: dwa teledyski z tekstem (DISCORD, Charlie Puth „We Don’t Talk Anymore”, kopie 30 fps) mierzone klatka po klatce, kursy School of Motion, wyrażenie sprężyny Dana Ebbertsa, wytyczne czytelności SSW, norma EBU R37.

- **Długość ujęć.** Jeden takt = jedno ujęcie (przy 120 BPM ok. 2 s). Wzór: 4 takty + 1 uderzenie (8,5 s): tytuł, etap 1, etap 2, etap 3.
- **Stała siatka uderzeń w każdym ujęciu (wzór).** Uderzenie 1: główne słowo wpada (+ wielki numer etapu w tle); 1,5: „dowód” (karta kodu, dymek, lista); 2: zdanie pomocnicze; 3: akcja dowodu; 3,5: powiększenie słowa kluczowego + zakreślenie; 4: oddech albo wyjście. Ostatnie uderzenie 16 (8,0 s) to mocne zakończenie, potem 0,5 s postoju. Wszystkie ujęcia mają te same pozycje, zmienia się tylko strona i treść: od drugiego ujęcia widz „wie, gdzie będzie następne uderzenie”.
- **Akcenty.** Główne słowo na mocną część taktu (pierwsze uderzenie) z niskim uderzeniem dźwięku; drobne elementy na ósemkach z „pop”; 0,3 s przed przejściem narastający szum prowadzi ucho do następnego taktu. Każde lądowanie ma dźwięk, każdy akcent ma obraz.
- **Pomiar oryginałów.** Całkiem nieruchome sąsiednie klatki: tylko 10,3% (DISCORD) i 21,2% (Charlie Puth) – odwrotnie niż historyjka (71%). Duże zdarzenia wizualne (szczyty zmiany > 1,5% kadru) średnio co 0,66 s i 0,83 s, czyli prawie jedno na uderzenie (tempa ok. 105 i 99 BPM, uderzenie 0,57 i 0,60 s). Wzór ma jedno zdarzenie na ósemkę (0,25 s): w otwarciu można tak gęsto, w dłuższym filmie jedno na uderzenie.
- **Czytelność.** Angielskie wytyczne dla tekstu w wideo: co najmniej 13 znaków/s (SSW) – tej granicy trzymaj się dla polskiego. Wzór: główne słowo stoi co najmniej 0,5 s, zdanie pomocnicze co najmniej 1,0 s.
- **Zgranie z narracją.** Główne słowo = słowo akcentowane przez lektora. Obraz raczej wcześniej niż później, **najwyżej 1 klatkę przed dźwiękiem**: ludzie łatwiej wyłapują dźwięk, który wyprzedza obraz (EBU R37: dźwięk najwyżej 40 ms przed obrazem, najwyżej 60 ms po nim).
- **Skala krojów (wzór).** Główne słowo 340 px (Black) : zdanie pomocnicze 96 px (Heavy) : etykieta 40 px (Bold, rozstrzelenie 6 px) ≈ **3,4 : 1 : 0,4**. Główne słowo ma się przeczytać w 0,3 s, dlatego we wzorze ma 2 znaki chińskie. Klip: główne słowo 300 px (pion 250 px); za długie zmniejsza się w 1 linii do 0,55, potem łamie na 2 linie (do 0,3); zdanie pomocnicze 80 px (pion 64 px), najwyżej 2 linie; etykieta 52 px (pion 56 px), rozstrzelenie 6 px.
- **Kroje.** `PuHui-Black` / `PuHui-Heavy` / `PuHui-Bold`; w Jarvie nakładka `huashu_pl.js` podmienia je na Inter tej samej grubości (900 / 800 / 700). Liczby po polsku: `TY.fmt` w nakładce daje przecinek dziesiętny i spację tysięcy.
- **Kompozycja.** Jedno główne słowo na ekran. Wzór: słowo wyrównane do lewej w lewej 1/3–1/2 kadru (albo lustrzanie z prawej), zdanie pomocnicze tuż pod nim, po drugiej stronie „dowód” (karta kodu, dymek czatu, lista); w górnym rogu mała etykieta („Etap 01”) i pasek postępu; marginesy co najmniej 130 px. Klip: blok słowa na środku pasa `safe` (w pionie na 44% jego wysokości).
- **Paleta.** Każdy rozdział ma swoje tło na cały ekran; zmiana rozdziału = zmiana tła (kolor sam jest numerem rozdziału). Wzór: tytuł – tło żółte `#FFD23F`, słowo atrament `#111111`, akcent biała „3” w koralowym kole `#FF5A36`; etap 01 – koral `#FF5A36`, białe słowo, żółty zakreślacz `#FFD23F`; etap 02 – granat `#14213D`, żółte słowo, żółty zakreślacz, niebieski dymek `#3A86FF`; etap 03 – złamana biel `#F4EFE6`, atrament, koralowe podkreślenie, zielony znacznik `#2BB673`. Razem 4 tła + atrament + biel, akcent zawsze tylko jeden. Klip: `data.palette` domyślnie te 4 pary [tło, tekst] po kolei na każdą stronę; kolor `data.key` to `#FF5A36` na tle żółtym albo złamanej bieli i gdy tekst jest żółty, w innych razach `#FFD23F`.
- **Kształty.** Tekst to największy kształt. Pomocnicze tylko: zaokrąglone prostokąty (karta r = 26, dymek r = 30, klawisz r = 22), koła (pod liczby), ukośne bloki (zakreślacz, nachylenie 0,18). Tło: siatka kropek co 64 px, krycie 6–10% (klip 7%), sunie ukośnie 36 px/s. Bez tekstu z obrysem i bez cieni pod tekstem (jedyny cień to przesunięty cień karty, 8–18%).
- **Wejścia według ważności (wzór).**
  - Główne słowo **wpada**: z 1,7× do 1, krycie 0→1 w pierwszych 0,06 s; sprężyna niedotłumiona 1 − e^(−10t)·cos(2π·2,2t), przestrzał ok. 8%, stoi po ≈ 0,35 s (`TY.slam`, `MO.springHz` 2,2 / 10). Pierwsze słowo tytułu dodatkowo obraca się z −8° do 0.
  - Zdanie pomocnicze i etykieta **wyrastają ze szczeliny**: maska pod linią bazową, z +1,2 wysokości znaku do 0, `MO.expoOut` 0,30–0,35 s (`TY.rise`).
  - Liczby, ikony, dymki, klawisze **wyskakują**: skala 0→1, `MO.backOut` s = 2,6–3,0 (przestrzał 17–20%), 0,30–0,42 s.
  - Karty **wsuwają się** z +700 px albo +260 px od dołu, z obrotem 3,4° do 0, `MO.expoOut` 0,40 s.
  - Pisanie: 13 znaków w 0,5 s (26 znaków/s), kursor miga 2 Hz. Podpowiedź kodu: szary tekst pojawia się w 0 klatek → Tab → pełny kolor; klawisz wciśnięty o 14%, odbicie e^(−18t).
  - Zakreślacz i podkreślenie od lewej do prawej, `MO.expoOut` 0,30 s, 1–3 ósemki po pojawieniu się słowa.
  - Słowo kluczowe na akcencie rośnie do 1,35× i zostaje (sprężyna freq 2,5 / decay 9, `TY.keyword`), razem z akcją, o której mówi (Tab, odhaczenie).
  - Wielki numer etapu: 900 px, krycie 5–13%, prawy dół, z 1,35× do 1 (sprężyna freq 2 / decay 8), potem dryf ukośny 14 / 10 px/s.
  - Odhaczenie: kreska po długości łuku, ramka 1→1,25→1, 0,22 s; przekreślenie 0,08 s później.
- **Wyjścia.** Szybsze od wejść i przyspieszające: `MO.expoIn` 0,18 s, odstęp 0,03 s między elementami, zmniejszenie do 0,6, opadnięcie o 60 px, zanik. Uwaga widza odchodzi, zanim wyjście się zacznie. Rozłożenie w czasie: słowa w jednej linii co ósemkę (0,25 s przy 120 BPM), grupa drobnych elementów też.
- **Ciągły ruch (słowa po wylądowaniu stoją).** Wzór: dryf kamery z dwóch sinusów, amplituda 5 px, okresy ok. 7 s i 2,7 s; bardzo wolny obrót ±0,5°; na każdą ćwierćnutę cały kadr powiększa się o 1,2% i wraca jak e^(−25t) (≈ 0,12 s); kropki suną 36 px/s; na ostatnie uderzenie kamera oddala się o 6% (`MO.expoOut` 0,5 s). Klip: na każdy cue powiększenie 1,5% wygasające jak e^(−22t) (ok. 0,15 s), dryf 5 px, obrót 0,008 rad × sin(0,8t).
- **Przejścia.**
  1. `fillZoom` (przelot przez kształt): kamera wpada w kształt z poprzedniego ekranu, którego kolor = tło następnego; po wypełnieniu nowy ekran opada z 1,25× do 1. Pierwsze 55% czasu `MO.expoIn` do 30×, ostatnie 45% `MO.expoOut`. Parametry `cx, cy, k, maxZoom, fill`.
  2. `bands` (przetarcie pasami): trzy ukośne pasy (żółty → biały → granat) jeden po drugim od lewej do prawej, odstęp 12%, ostatni ma kolor nowego tła i odsłania nowy ekran. 0,5 s `MO.expoInOut`.
  3. `push` (pchnięcie): stary i nowy ekran przesuwają się razem jak po długim płótnie. 0,35 s `MO.expoInOut`.
  4. Maska rosnąca z kształtu (koło, pasek, sama litera) – istniejący `iris`.
  5. Litera jako przejście: litera rośnie do pełnego ekranu albo wylatuje i zabiera stary obraz.
  Klip: zmiana strony to dwa pasy (akcent inny niż oba tła + nowe tło), start 0,3 s przed `at`, 0,36 s, `MO.expoInOut`, odstęp 0,12; nowa strona odsłania się w klatce `at`.
- **Trafianie w takt (najcenniejsze).** Przejście startuje na początku nowego odcinka, więc żeby nowy obraz odsłonił się na kresce taktowej: początek odcinka = kreska taktowa − punkt odsłonięcia × czas przejścia (`MO.onBeat`). Wzór: `fillZoom` p = 0,55, 0,45 s → start 1,75 (odsłonięcie 2,00); `bands` p ≈ 0,6, 0,5 s → 3,70; `push` z expoInOut – oko widzi „na miejscu” przy 90% drogi (p ≈ 0,58), nie przy p = 1 → 5,80 (liczenie z p = 1 dało 8 klatek za wcześnie). Lądowania w ujęciu zapisuj w uderzeniach (`KT.b(n)` we wzorze), nie w sekundach.
- **Pomiar wzoru (qa).** Skoki obrazu tylko na zamierzonych akcentach (wyjście tytułu, wyrastanie dymka, mocne zakończenie); skok spoza siatki taktów to błąd. 1–3 ms na klatkę.

## Cue w spec
`data` całego spec: `palette: [[tło, tekst], …]` (strony po kolei). Każdy cue ma `at` (s, klatka, w której element pierwszy raz widać) albo nasze `slowo` (+ `nth`, `offset`). `kind` spoza tabeli nie daje błędu i nic nie rysuje (tu nie ma `image`, `dur` nie jest czytane). Cue z `at` > `duration` jest odrzucany z ostrzeżeniem. Każdy cue daje też lekkie „uderzenie” całego kadru.

| kind | pola | co robi | przykład |
|---|---|---|---|
| `title` / `point` | `text` (główne słowo; za długie → mniejszy krój, najwyżej 2 linie), `sub` (zdanie pomocnicze, najwyżej 2 linie), `data.label` (mała etykieta w lewym górnym rogu), `data.key` (słowo z `sub` w kolorze akcentu), `data.num` (wielki numer w tle zamiast kolejnego) | Jedna strona. W `at` główne słowo wpada (sprężyna, przestrzał ok. 8%, każda następna linia +0,08 s), `sub` wyrasta od +0,35 s, etykieta od `at`. Zmiana strony to przetarcie pasami od `at − 0.3`. Co najmniej 2 `point` = lista: pasek postępu 01/02/03 (poziomo prawy górny róg, pionowo na dole) i wielki numer w tle (12% krycia, dryf). | `{"at":1.8,"kind":"point","text":"Wolno","sub":"Jedna zmiana naraz","data":{"label":"01","key":"Jedna zmiana"}}` |
| `number` | `data.value`, `data.prefix`, `data.suffix` (spację wpisz sam), `data.decimals` (domyślnie 0), `data.label`; podpis w `text`, `sub` albo `data.text` | Strona z dużą liczbą: wchodzi w `at − 0.7` i liczy od 0 (`MO.expoOut`, 0,7 s); `at` = chwila, gdy liczba staje. Liczba nie łamie się na linie, tylko zmniejsza. | `{"at":4,"kind":"number","sub":"wdrożeń bez poprawek","data":{"value":87.5,"decimals":1,"suffix":" %"}}` |
| `highlight` | `data.word` (słowo z głównego słowa; bez niego całe główne słowo) | Zakreślacz pod słowem (0,3 s) i krótkie powiększenie o 6% (sprężyna). Gdy zakreślacz ma kolor tekstu (granatowa strona z żółtym tekstem), tekst pod nim przyjmuje kolor tła. Słowo spoza głównego słowa → ostrzeżenie, nic się nie dzieje (słowo z `sub` koloruj przez `data.key`). Działa pierwszy `highlight` na danej stronie. | `{"at":3,"kind":"highlight","data":{"word":"Wolno"}}` |

## Minimalny spec (po polsku)
Lektor: „Wolno znaczy szybko. Wolno, bo jedna zmiana naraz…”. Drugi cue jest przypięty do drugiego „wolno” w narracji, z `offset` −0,03 s (jedna klatka przy 30 fps przed dźwiękiem). `gramatyka.py` liczy `at` z `os_czasu.json` (`film.py narracja`); `nth` liczy wystąpienia od 1.

```json
{"grammar":"y5_kinetic_type","duration":5,"cues":[
  {"at":0,"kind":"title","text":"Wolno znaczy szybko"},
  {"slowo":"wolno","nth":2,"offset":-0.03,"kind":"point","text":"Wolno","sub":"Jedna zmiana naraz","data":{"key":"Jedna zmiana"}},
  {"at":3.3,"kind":"point","text":"Szybko","sub":"Działa za pierwszym razem","data":{"key":"za pierwszym razem"}}]}
```

## Pułapki
- **Wszystkie słowa tej samej wielkości i ruszają się razem.** Bez hierarchii nie ma punktu skupienia. Główne : pomocnicze co najmniej 3 : 1, w danej chwili wchodzi tylko jedna rzecz, reszta stoi.
- **Tekst ciągle pływa.** Czytanego tekstu nie wolno ruszać. Ciągły ruch oddaj kamerze, uderzeniom i kropkom; słowo stoi 0,35 s po wpadnięciu.
- **Animacja poza taktem albo akcent na starcie przejścia.** Akcentem jest klatka odsłonięcia, nie pierwsza klatka przejścia. W klipie odsłonięcie = `at`, pasy ruszają 0,3 s wcześniej; w scenie pisanej samodzielnie przesuń start odcinka o punkt odsłonięcia × czas przejścia. Każde lądowanie poza siatką rozbija rytm.
- **Polskie główne słowo jest dłuższe niż chińskie.** We wzorze ma 2 znaki; po polsku daj jedno krótkie słowo. Długie słowo zmniejsza krój (do 0,55 w jednej linii, potem 2 linie do 0,3) i traci siłę uderzenia.
- **`number` z `at` < 0,7** jest w pierwszej klatce już w połowie liczenia. Ustaw `at` na chwilę, w której lektor wypowiada liczbę.
- **Za mało czasu na czytanie.** Główne słowo co najmniej 0,5 s, zdanie pomocnicze co najmniej liczba znaków / 13 s, nie krócej niż 1,0 s.
- **Lista dłuższa niż 5 punktów:** pasek postępu zwęża odcinki, ale treść robi się nieczytelna. Przejdź na infografikę.
- **Tekst w kadrze konkuruje z wypalanymi napisami.** Przesuń napisy albo nie wypalaj ich w tym fragmencie; ustaw `safe.bottom` (pion 1080×1920: 700, poziom: 250), blok słowa i pasek postępu zostają w tym pasie.
- **Tryb `--alfa`:** bez tła i kropek; tekst biały z ciemnym obrysem, zakreślacz koralowy.

## Kontrola
- Czy w każdej chwili jest jeden punkt skupienia, a główne słowo jest co najmniej 3 razy większe od pomocniczego?
- Czy każde główne słowo ląduje na słowie akcentowanym przez lektora, najwyżej 1 klatkę przed dźwiękiem (`os_czasu.json` i stopklatki)?
- Czy tekst stoi po 0,35 s, a ruch daje tylko kamera, kropki i uderzenia?
- Czy czasy czytania wystarczają (główne ≥ 0,5 s, pomocnicze ≥ znaki / 13 s)?
- Czy każdy rozdział ma swoje tło, akcent jest jeden, a `data.key` i zakreślenie są widoczne na tym tle?
