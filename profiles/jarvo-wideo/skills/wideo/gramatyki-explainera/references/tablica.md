# Tablica rysowana ręcznie, typ RSA (`tablica`, w kodzie `y3_whiteboard`)

Lektor mówi zdanie, a ręka z markerem pisze je i rysuje obok na jednej dużej białej tablicy; kamera idzie za argumentem, a na końcu oddala się i cały wywód widać jako jedną mapę. Wzór: `python3 $HERMES_HOME/scripts/gramatyka.py wzor tablica --arkusz out/wideo/wzor-tablica.jpg`; start: `python3 $HERMES_HOME/scripts/gramatyka.py szablon tablica [--format 9:16] -o out/wideo/src/klip-tablica/spec.json`.

Kod: klip `$HUASHU/scripts/engine/clips/y3_whiteboard.js`, przykład `$HUASHU/scripts/engine/examples/y3_whiteboard.json` (tytuł, trzy punkty z ikonami `stack`, `network`, `chat`, `highlight`), film pokazowy `$HUASHU/scripts/engine/demos/y3_whiteboard/` (MIT). Film pokazowy ma 8 s, 3 bloki (ok. 2,5 razy gęściej niż prawdziwy film), a pióro jedzie 2 razy szybciej niż w RSA: bierz technikę, nie tempo.
Potok: `szablon` → polskie teksty i `slowo` → `gramatyka.py sprawdz` → `gramatyka.py render … --klatki 0.5,2,4` → pełny `render`.

**Najpierw wybierz jeden typ i ich nie mieszaj.** Typ RSA: jedna wielka tablica, kamera jeździ po niej, 5,3 ruchu na minutę. Typ Minute Physics: jedna kartka na stronę, twarde cięcia na nową kartkę, 8,1 na minutę, kamera stoi. Klip i ta karta to typ RSA.

## Kiedy
- Treść argumentacyjna: wystąpienie, opinia, łańcuch przyczyn, rys historyczny. Najlepiej, gdy pojęcia mają relacje i da się je narysować jako mapę („rozłożyć informację w przestrzeni, żeby było widać relacje” – Andrew Park, RSA).
- Krótkie wyjaśnienie z jednym łańcuchem rozumowania (wtedy raczej typ Minute Physics).
- Spokojna narracja z wyraźnymi słowami kluczowymi. W RSA pisanie ma tempo mowy, jak napisy pisane ręcznie.
- Przykłady: „dlaczego warto pisać testy” w kursie online (1–3 min), wyjaśnienie procesu decyzji klienta dla usługi B2B, lekcja „skąd się bierze inflacja” krok po kroku, wywód eksperta w filmie na LinkedIn 16:9.

## Nie do
- Dokładne wykresy danych: ręka rysuje z dużym błędem. Użyj `wykresy`.
- Złożony ruch i relacje przestrzenne: tablica nie ma głębi. Użyj `kurzgesagt`.
- Silne emocje: jednobarwny rysunek oddaje je słabo. Użyj `historyjka`.
- Gdy celem ma być „lepsze zrozumienie”: eksperyment Türkay (2016) nie wykazał, że animacja tablicowa uczy lepiej niż inne formy. Jej wartość to przyciąganie uwagi i poczucie, że ktoś tłumaczy obok.

## Gramatyka (z pomiarów)
Źródła: RSA Animate „Changing Education Paradigms” i Minute Physics „Why is it Dark at Night?” mierzone klatka po klatce, dokumentacja VideoScribe i Doodly, wypowiedzi Andrew Parka i Henry’ego Reicha.

- **Długość bloków.** RSA: między dwoma ruchami kamery mediana 6,6 s (kwartyle 4,0–13,8 s). Minute Physics: mediana ujęcia 7,1 s.
- **Tempo pisania (9 przypadków).** Tekst główny: mediana ok. 16 znaków/s. Tytuł na otwarcie wolniej o połowę, ok. 7,5 znaku/s („stawia temat”). Narracja ok. 13 znaków/s, więc pisanie ≈ mowa. W klipie: `title` od 7,5 znaku/s, `point` i podpisy od 16 znaków/s; tempo rośnie samo, gdy do następnego cue zostało mniej czasu (tempo = max(bazowe, znaki / (czas do następnego cue − 0,15 s, dla `point` jeszcze − 0,15 s))).
- **Tempo rysowania.** Mała ikona 0,5–1 s, głowa postaci ok. 2 s. W RSA przybywa mediana 0,25% kadru tuszu na sekundę. Złożonej ilustracji nie rysuj przy widzu: albo jest narysowana wcześniej i kamera ją odsłania, albo wchodzi w całości cięciem, a ręka tylko dokłada kolor. Przyspieszenie nagrań: Henry Reich robi 1 zdjęcie na sekundę i trzyma je 2 klatki (ok. 12×), RSA szacunkowo 5–8×.
- **Pióro w kodzie.** Prędkość 2600 px świata/s (ok. 2× RSA; w prawdziwym filmie zwolnij). Czas pociągnięcia = długość / prędkość, co najmniej 0,04 s, przerwa na podniesienie pióra 0,02 s; wewnątrz pociągnięcia `MO.sineInOut` (wolny start i koniec). Litery nie mają danych o kolejności kresek, więc tekst odsłania zygzak: pióro jedzie po każdym znaku tam i z powrotem (we wzorze 3 rzędy na znak, postać 8 rzędów w 0,7 s, `DG.revealMask` + `DG.zigzag`), czubek zawsze na krawędzi odsłonięcia. Zasada z recenzji wzoru: pióro ma prowadzić linię; kilka kresek pojawiających się naraz od razu zdradza efekt.
- **Ruch ręki.** Pomiar: prawdziwa prawa ręka z czarnym markerem wchodzi z prawego dołu, przedramię ukośnie w prawy dół, zasłania 15–25% kadru; gdy nie rysuje, wychodzi z kadru całkiem. Ręka w kadrze: RSA 49% czasu, Minute Physics 40%. We wzorze przerwa < 0,25 s: pióro sunie łukiem do początku następnej kreski (sineInOut, uniesione 30 px); dłuższa: ręka wychodzi 0,35 s cubicIn w prawy dół poza kadr, 0,3 s przed następną kreską wraca cubicOut. W klipie: łuk przy przerwie ≤ 0,6 s, poza tym wyjście 0,35 s i powrót 0,3 s przed kreską; po ostatniej kresce pióro zawsze wychodzi. W klipie widać sam marker (bez przedramienia) z lekkim kołysaniem (7 rad/s); we wzorze to gołe przedramię z markerem w skali 0,82.
- **Ciągły ruch.** Tablica żyje, bo ręka cały czas rysuje: w RSA aktywność rysowania prawie nie zależy od gęstości słów (|r| < 0,07), w pauzach mowy ręka też rysuje.
- **Wyskok bez ręki.** Część pomarańczowych słów kluczowych RSA wyskakuje w całości w postprodukcji (ANAESTHETIC, CREATIVITY). We wzorze 0,3 s `backOut(2.2)`, bez ręki. Klip nie ma takiego cue (wszystko pisze pióro); w scenie pisanej samodzielnie służy do tego `B.pop` z `DG.board`.
- **Przejścia.**
  1. Płynny przejazd albo zoom po tablicy (RSA, 41 razy): 1,2–2,4 s, `MO.sineInOut` (zmierzony stosunek prędkości szczytowej do średniej 1,49, teoria dla sinusa 1,57). Jeden przejazd to ok. 0,23 szerokości kadru, nowy blok nachodzi na stary w ok. 75%: widz zawsze widzi brzeg poprzedniego.
  2. Szarpnięcie kamery z rozmyciem: ok. 0,8 s, 0,5–1,2 szerokości kadru, do dalekich miejsc tablicy (RSA, 15 razy). We wzorze 0,8 s cubicInOut o ok. cały ekran, rozmycie 9 kopii tylko w tych 0,8 s.
  3. Oddalenie do całości na zakończenie: w RSA szary kolor wypełnia ekran → 0,6 s szybkiego oddalenia → ok. 9 s panoramy po długim zwoju → oddalenie do całości. VideoScribe ma domyślnie zaznaczone „Zoom at end?”. We wzorze 6,85→7,5 s sineInOut do 0,45×, postój 0,5 s, tablica w 0,5 s przykryta bardzo jasną szarością `#EEEEEC`.
  4. Wymazanie chmurą albo wybuchem: kreskówkowa chmura wypełnia kadr i się rozwiewa, ok. 1 s (RSA raz).
  5. Twarde cięcie: na wcześniej narysowany obraz (RSA rzadko); zmiana kartki w typie Minute Physics (główne przejście, 8,1 na minutę); odwrócenie kolorów całej klatki (Minute Physics, odcinek o nocy).
  „Najazd w ramkę albo dymek” i „przewracanie strony” nie wystąpiły w żadnym filmie.
- **Kamera w klipie.** Gdy treść wychodzi poza pas kadru, kamera zjeżdża w dół przed następnym wpisem (0,6 s, `MO.sineInOut`). Na koniec, jeśli po ostatniej kresce zostało ≥ 0,6 s, oddala się w 0,8 s `MO.sineInOut` do całości (tylko w pasie `safe`, z ≤ 0,94); gdy kamera wcześniej zjeżdżała, oddala się w ostatnich 0,8 s nawet przy ciasnym czasie.
- **Zgranie z narracją – rdzeń (pomiar).** Pisanie zaczyna się 0,2–0,8 s po początku frazy, mediana +0,5 s, i kończy w ciągu 1 s po jej końcu: pisze w trakcie mowy, lekko za nią, **nigdy przed**. Wyjątek: przygotowanie wizualne (fiolka, strzałka) rysuje się kilka sekund wcześniej i czeka na kwestię. Minute Physics: rysunek ląduje, gdy pada rzeczownik, mediana +0,3 s. Przejście daj przy zmianie tematu, nie w pauzie: nowy blok = nowy argument. Muzyka: RSA nie ma muzyki pod mową; Minute Physics ma ją cały czas, ok. 9 dB ciszej niż głos. Domyślne wartości narzędzi: VideoScribe postój po rysowaniu 0,5 s, ruch kamery 1 s; Doodly 3 s rysowania na element.
- **Paleta (pomiar RSA).** Tło czysta biel `#FBFBFB`, linia czerń `#0A0503`, jedyny akcent pomarańczowy: tekst `#EB701F`, wypełnienie `#F3742D`, jasnopomarańczowe kreskowanie ok. `#E9A67C`. Pomarańcz to ok. 22% pikseli tuszu, tylko słowa kluczowe i kreskowanie. Minute Physics: różowawa złamana biel `#E7DBE1`, kredkowy jasnożółty `#EDE6A2` i jasnoniebieski `#B5CBE8`. W klipie: tablica `#FBFBFB`, tusz `#0A0503`, akcent `#EF7226`, wypełnienie akcentu `rgba(239,114,38,.22)`.
- **Grubość linii.** RSA: kreska 0,6–0,7% wysokości kadru (6–7 px w 1080p), kreskowanie ok. 0,3%, wysokość liter tytułu ok. 5,5% wysokości kadru. Minute Physics grubiej, ok. 0,8%. Klip: 6,5 px.
- **Kompozycja.** RSA najpierw planuje cały obraz końcowy, potem rysuje go „od tyłu”. Każdy blok ma 3–6 grup tekst + rysunek, zapełnij go i dopiero przejedź dalej. Zakończenie odsłania długi poziomy zwój. Układ w klipie: w poziomie z `draw`/`image` tekst po lewej, rysunki po prawej (od 0,55 szerokości); w pionie z `draw` ikony w wąskiej prawej kolumnie obok swojego zdania; w poziomie sam tekst i ≥ 5 punktów → dwie kolumny. Rozmiar tekstu dobiera się sam ze współczynnikiem 1,2 → 0,72: mało treści powiększa, dużo pomniejsza, dopiero gdy się nie mieści, kamera zjeżdża.
- **Krój.** RSA pisze wersalikami pisma ręcznego (jak w komiksie). Klip: `LXGWWenKai-500` (tytuł do 112 px, punkty do 74 px, razy współczynnik); w Jarvie nakładka `huashu_pl.js` podmienia go na Caveat-600.
- **Pomiar wzoru (qa).** Żadnych skoków obrazu w 3 ujęciach: każde „przejście” to ruch kamery po tej samej tablicy, więc rysunki nie przeskakują. Poniżej 10 ms na klatkę, bo to same wektory.

## Cue w spec
`data` całego spec: brak. Każdy cue ma `at` (s, w tej klatce pada pierwszy punkt kreski) albo nasze `slowo` (+ `nth`, `offset`). `kind` spoza tabeli nie daje błędu i nic nie rysuje (tu nie ma `number`, `dur` nie jest czytane). Cue z `at` > `duration` jest odrzucany z ostrzeżeniem.

| kind | pola | co robi | przykład |
|---|---|---|---|
| `title` | `text` | Pisze tytuł od 7,5 znaku/s (przyspiesza, żeby skończyć przed następnym cue). Najpierw zmniejsza krój do 1 linii (do 0,72), potem łamie na równe linie. | `{"at":0,"kind":"title","text":"Po co pisać testy"}` |
| `point` | `text` | Rysuje pomarańczowe kółko-punktor, potem pisze od 16 znaków/s. Wszystkie punkty mają jeden rozmiar. | `{"at":1.5,"kind":"point","text":"Pilnują kodu przy zmianach"}` |
| `draw` | `data.icon` (`person cat network doc chat bulb check cross screen stack gear target clock chart`; zła nazwa → ostrzeżenie, sam podpis), `text` (podpis: w poziomie z prawej, w pionie pod ikoną; za długi → mniejszy krój), `data.arrow: false` (bez strzałki) | Rysuje ikonę obok ostatnio napisanego punktu. Kolejne `draw` łączy pomarańczowa strzałka w dół. | `{"at":2.5,"kind":"draw","text":"Kontrola","data":{"icon":"check"}}` |
| `image` | `image` (ścieżka względem spec) | Odsłania obraz zygzakiem (7 rzędów, 0,4–1,0 s), potem obrysowuje ręczną ramką. Proporcjonalnie, bez kadrowania. | `{"at":4,"kind":"image","image":"szkic.png"}` |
| `highlight` | `data.index` (od 0; bez `target` liczy `point`), `data.target`: `"title"` / `"draw"` / `"image"`, `data.style: "underline"` | Pomarańczowe kółko wokół wpisu albo podkreślenie. Bez `index`: ostatnio napisany wpis (z `target` – ostatni tego rodzaju). Brak wpisu → ostrzeżenie. | `{"at":5,"kind":"highlight","data":{"index":0,"style":"underline"}}` |

## Minimalny spec (po polsku)
Drugi cue jest przypięty do słowa „pilnują” w narracji z `offset` 0,5 s, bo pisanie startuje ok. 0,5 s po początku frazy. `gramatyka.py` liczy `at` z `os_czasu.json` (`film.py narracja`); `nth` (od 1) wybiera wystąpienie.

```json
{"grammar":"y3_whiteboard","duration":8,"cues":[
  {"at":0,"kind":"title","text":"Po co pisać testy"},
  {"slowo":"pilnują","offset":0.5,"kind":"point","text":"Pilnują kodu przy zmianach"},
  {"at":3.8,"kind":"draw","text":"Kontrola","data":{"icon":"check"}},
  {"at":6,"kind":"highlight","data":{"index":0}}]}
```

## Pułapki
- **Cała tablica przed mową albo mowa przed rysunkiem.** Sedno to „mówi zdanie, pisze zdanie”, ok. 0,5 s za lektorem (`slowo` + `offset: 0.5`). Rysunek przed słowami każe widzowi czekać, rysunek po słowach jest zbędnym powtórzeniem. Złożoną ilustrację daj jako `image`.
- **Za każdym razem cały nowy pusty ekran.** W RSA przejazd to 0,23 szerokości kadru z dużym nakładaniem; szarpnięcie tylko do dalekich miejsc. Zakończ oddaleniem do całości: klip robi je tylko, gdy po ostatniej kresce zostaje ≥ 0,6 s (chyba że kamera wcześniej zjeżdżała), więc zostaw na końcu ok. 1 s.
- **Dużo kolorów, cienka albo równa linia, ręka wisi w kadrze.** Tylko czerń i jeden akcent, linia ok. 0,65% wysokości kadru; ręka wchodzi tylko do rysowania.
- **Mieszanie RSA i Minute Physics.** Albo jedna tablica i ruch kamery, albo kartka na stronę i cięcia.
- **Za gęste cue.** Pisanie i rysowanie przyspieszają. Polskie zdania mają więcej znaków niż chińskie: trzymaj punkt do ok. 30 znaków i daj mu czas – przy 16 znakach/s potrzeba (odstęp do następnego cue − 0,3 s) ≥ znaki / 16, a dla tytułu (odstęp − 0,15 s) ≥ znaki / 7,5. W 3–8 s najlepiej 2–5 cue.
- **Tekst w kadrze konkuruje z wypalanymi napisami.** Przesuń napisy albo nie wypalaj ich w tym fragmencie; ustaw `safe.bottom` (pion 1080×1920: 490–570, poziom: 160–220), klip układa treść tylko w tym pasie.
- **Zła nazwa ikony** daje sam podpis bez rysunku (ostrzeżenie). Nazwy tylko z listy.
- **Tryb `--alfa`:** tusz dostaje białą obwódkę (8 kierunków), żeby był widoczny na ciemnym obrazie.

## Kontrola
- Czy każdy wpis zaczyna się ok. 0,5 s po swojej frazie i kończy najpóźniej 1 s po jej końcu?
- Czy czubek pióra zawsze prowadzi linię, a ręka wychodzi z kadru, gdy nie rysuje?
- Czy są tylko czerń i pomarańcz, a pomarańcz tylko na słowach kluczowych, strzałkach i zaznaczeniach?
- Czy film kończy się oddaleniem do całości i nic nie jest ucięte u góry (tytuł)?
- Czy cała treść jest nad pasem napisów i czytelna na stopklatkach w pionie?
