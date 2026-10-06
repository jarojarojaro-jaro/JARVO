# Rytm i muzyka: siatka bitów, krótsze odcinki, motyw na instrument stylu

Jak ułożyć czas filmu ze stylami (przegląd epok, montaż, długi zwój) i muzykę pisaną kodem. Źródło: rozpis
15-sekundowego „Art History Speedrun” (Tak, @cherry_mx_reds), którego muzyka też była zaprogramowana. Zostają
zasady i liczby z rozpisu, nie nuty oryginału. Mechanizm obrazu: `metoda.md`.

## Narzędzia Jarva

| Zadanie | Polecenie |
|---|---|
| Rozpis filmu-wzoru: klatki co 1/fps s, cięcia, rytm muzyki, starty przejść i ich siatka (krok, tempo, odstające, `przypadek`), mapa ruchu, klatki kluczowe (`wzor.json`) | `python3 $HERMES_HOME/scripts/kadry.py wzor film-wzor.mp4 --fps 2 -o out/wideo/wzor` |
| Tempo, pierwszy bit (faza), bity, takty, perkusja w trzech pasmach | `python3 $HERMES_HOME/scripts/rytm.py muzyka.mp3 --json out/wideo/src/rytm.json` |
| Po renderze: cięcia filmu kontra bity (błąd w klatkach: do 1,5 idealnie, do 3 dobrze) | `python3 $HERMES_HOME/scripts/rytm.py sprawdz out/wideo/film.mp4 --ciecia 1.2,3.4` |
| Muzyka pisana kodem pod obraz, efekty w chwilach z cues.json | `python3 $HERMES_HOME/scripts/muzyka.py zrob out/wideo/film.mp4 -o out/wideo/final.mp4 --cues cues.json --tempo 128` |
| Głośność, szczyt, pasma, najdłuższa cisza | `python3 $HERMES_HOME/scripts/muzyka.py sprawdz muzyka.wav --lufs -14` |

`muzyka.py` gra jednym tempem i układa formę z przepisu (`muzyka.py przepisy`): wstęp → narastanie → kulminacja
(`--kulminacja T`) → koniec (`--koniec T`, końcowy akord do ostatniej klatki); mastering do −14 LUFS i szczytu
prawdziwego ≤ −1 dBTP. Motywu zmieniającego instrument w każdym odcinku (zasada 3) sam nie napisze: to wzorzec do
własnej ścieżki na silniku mgaudio (`narzedzia.py env mgaudio` → `$MGAUDIO`, `$MGAUDIO_PY`). Skrypt źródła
`$HUASHU/scripts/audio/synth_艺术史速通.py` (oryginalny przykład, D-moll, Dm–B♭–F–C) czytasz jako wzór budowy
instrumentów i łańcucha miksu; nie uruchamiamy go przez ich `uv`.

## Zasady (do przepisania wprost)

1. **Najpierw siatka BPM; obraz i muzyka leżą na siatce.** 128 BPM, ósemka 0,234 s: dobre do przeglądu i montażu.
   Każde cięcie, wejście dźwięku i efekt w chwili `t0 + n·E`, gdzie `E = 60 / BPM / 2` (ósemka). Wtedy jakkolwiek
   tniesz obraz, muzyka nie brzmi chaotycznie. We wzorze resztki czasu mieściły się w ±4 ms; ta „maszynowa
   dokładność” jest częścią stylu. W tabeli odcinków silnika huashu (`eras.js`) pole `eighths` to liczba ósemek
   odcinka; zmiana rytmu = zmiana tylko tego pola.
2. **Przyspieszasz skracaniem odcinków, nie podnoszeniem tempa.** Wzór: 6 → 4×5 → 3×4 → 2×3 → 1×3, ostatni odcinek
   znów dłuższy (9), żeby widz odetchnął i była przestrzeń na puentę. Pełny układ 17 odcinków w ósemkach:
   6, 4, 4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2, 1, 1, 1, 9. Tempo stałe, a słychać coraz większy pośpiech; każdy odcinek
   jest na siatce, więc cięcia obrazu same są zsynchronizowane. Rób tak: wypisz długości odcinków obrazu, zaokrąglij
   do ósemek, wyrównaj w regularny spadek. Przejścia skracaj razem z odcinkami (0,4 s → 0,13 s).
3. **Jeden motyw z trzech dźwięków, nowy instrument w każdym stylu, transpozycja za akordem.** Krótka komórka
   o wyrazistym rytmie (w przykładzie ♪♪♩: krok w górę, potem skok w dół), w każdej scenie zagrana instrumentem
   typowym dla epoki albo stylu, wysokość za akordem odcinka. Harmonia: jedna pętla czterech akordów wystarcza
   (przykład: Dm–B♭–F–C). Odcinek „poza szereg” (egzotyczny, awangardowy): zmień tylko skalę albo dodaj tryton;
   rytm i siatka bez zmian. Otwarcie może zagrać odwrócenie albo augmentację motywu (w przykładzie jaskinia:
   opadająca ćwierćnuta z kropką), żeby motyw się ustalił.
4. **Między odcinkami twarde wejście, bez przenikania.** Nowy odcinek wchodzi na siatce od razu; nuty poprzedniego
   wybrzmiewają naturalnie (szarpane 30–300 ms, wytrzymane ok. 150 ms wybrzmienia). Odcinki może zszyć jeden niski
   dźwięk trzymany przez granicę. Każda zmiana sceny ma wyraźne „klik” i nic się nie urywa. Nie dodawaj „świstu”
   przejścia do każdego odcinka (wzór nie ma ani jednego).
5. **Efekty końca: stop → zawieszenie → uderzenie → reakcja → domknięcie.** Wszystkie chwile z arkusza klatek obrazu
   (co 0,1 s), zgodność z klatką zdarzenia do 3 klatek.
   - Stop: muzyka staje na siatce z szybkim wygaszeniem ok. 150 ms, bez twardego cięcia.
   - Zawieszenie: małe „dzyń” (kilka nieharmonicznych dzwonień 5–7 kHz i trochę 1,5 kHz, razem wysoki szum ruchu
     łapy), potem gwizdek suwakowy w dół: czysty sinus, wykładniczo ok. 1550 → 325 Hz, ok. 0,35 s (ponad 2 oktawy).
   - Uderzenie: głuche ok. 80 Hz + szum szerokopasmowy (środek ciężkości 5–7 kHz, wygasa w ok. 0,45 s) +
     nieharmoniczne alikwoty ceramiki + kilka drobnych stuknięć odłamków.
   - Reakcja: głos postaci (we wzorze „miau” z linią wysokości w górę i w dół, dwa formanty) ok. 0,5 s po
     uderzeniu, najgłośniejszy dźwięk całego filmu.
   - Domknięcie: jedno albo dwa ciche „pyk” ok. 90 Hz przy podpisie, na końcu niski szarpany dźwięk na tonice albo
     dominancie.

   W `cues.json` dla `muzyka.py` najbliżej: `{"mg": "ding", "t": …}` (dzyń), `{"sfx": "fall", "t": …, "dur": 0.35}`
   (gwizdek w dół = `slide_whistle`), `{"mg": "impact", "t": …, "opcje": {"kind": "thud"}}` z
   `{"mg": "drums.crash", "t": …}` (uderzenie), `{"sfx": "pop", "t": …}` (pyk); końcowy akord daje `--koniec`.
   Gotowego głosu zwierzęcia mgaudio nie ma: reakcję daj własnym dźwiękiem albo efektem z rodziny „kreskówka”
   (`muzyka.py efekty`).
6. **Głośność wyrównuj względnie.** Najpierw zmierz wzór całościowo (zintegrowane LUFS, LRA, szczyt prawdziwy;
   wzór: −14,3 LUFS, LRA 0,9 LU, szczyt −2,4 dBTP; „średnio −16,6 dB” to średnia RMS, inna miara). Potem po
   odcinkach głośność K-ważoną i różnice pasm 2–6 kHz, > 6 kHz i 40–220 Hz względem głośności odcinka. Po syntezie:
   ciepły dół per odcinek → dynamiczny EQ środka per odcinek → „powietrze” per odcinek → wyrównanie głośności per
   odcinek (3–4 iteracje, wygładzenie wzmocnienia 10 ms przeciw „suwakowi”) → przy wzorze w AAC dolnoprzepustowy
   16 kHz → wyrównanie całości do LUFS i limiter z wyprzedzeniem. Zawsze różnice względem głośności odcinka, nie
   wartości bezwzględne: zmiana materiału albo głośności całości nie wymaga ponownej kalibracji.
7. **Szablon syntezy (cztery bloki danych, reszta bez zmian):** `T0, E` (zero siatki i ósemka, `E = 60 / BPM / 2`);
   granice i wartości odcinków (`edges / target / MID_ORIG / HF_ORIG / LOW_FLOOR_ORIG / BED_ROOT`; bez wzoru
   `target` jedną wartością, np. −14, pozostałe trzy „bez korekty”); nuty w blokach `era(n0, items)` (każdy element
   `(pozycja w ósemkach, funkcja instrumentu, wzmocnienie, panorama)`; biblioteka: rodzina `pluck` szarpane,
   `additive` wytrzymane, `kick / clap / hat / taiko` perkusja, `chip / supersaw` syntezatory; nowy styl zwykle
   wymaga tylko tabeli harmonicznych i wygaszania `pluck`); efekty (`tink / slide_whistle / crash / meow /
   end_thump` w chwilach zdarzeń). Łańcuch miksu w drugiej połowie zostaje bez zmian.
8. **Kolejność rozpisu cudzej muzyki:** wejścia (strumień widmowy) dopasowane do siatki daje BPM i t0 → na siatce
   szesnastek wykrywanie nowych nut przez FFT, sprawdzone transkrypcją polifoniczną → barwa z proporcji
   harmonicznych i obwiedni → perkusja ze skoków energii > 6 kHz i < 150 Hz → model multimodalny tylko jako
   kandydat do sprawdzenia. W teście dobrze rozpoznał instrumenty, a pomylił tempo (podał 120, zmierzone 128),
   liczbę nut motywu, „świsty przejść” i czasy efektów.

## Liczby z rozpisu wzoru

- Siatka: ósemka E = 0,23431 s → **128,04 BPM**, zero siatki t0 = 0,028 s; 28 wejść, wszystkie resztki w ±4 ms
  (człowiek tak nie zagra: to programowe rozmieszczenie).
- Granice odcinków z trzech źródeł: pozycja na siatce, szczyt krzywej nowości MFCC (średnie 0,2 s przed i po),
  szczyt różnicy klatek obrazu. Granice dźwięku i szczyty MFCC różnią się o ≤ 20 ms; przejścia obrazu spóźniają się
  0–0,2 s wobec dźwięku (przejścia obrazu to wycierania i przemiany 0,1–0,2 s).
- Czy muzyka jest z kodu: resztki czasu w ±5 ms, barwy z podręcznikowych klocków (sinus, prostokąt, piła, wygaszanie
  wykładnicze), brak szumu nagrania w ciszy.
- Barwę najpewniej ocenia się z amplitud harmonicznych 20–220 ms po wejściu i wygaszania wąskopasmowej obwiedni.
- Dopasowanie siatki: największy krok, przy którym ≥ 80% punktów to punkty wewnętrzne (najmniejsza suma błędów
  wybiera za mały krok i dopasowuje wszystko na siłę). W teście z 16 wykrytych punktów wyszło 14,1 klatki (ósemka
  przy 128 BPM), 3 fałszywe punkty oznaczone jako odstające. Nasz `rytm.py` sprawdza siatkę na prawdziwych
  uderzeniach (0,5×, 1× i 2× tempa).
- Przykładowa synteza: 48 kHz stereo, 15,06 s, −14,0 LUFS, szczyt −1,5 dBTP.

## Miks (gdy piszesz własną ścieżkę)

1. Pogłos małego pomieszczenia 0,5 s, opóźnienie wstępne 12 ms, 9% sygnału mokrego.
2. Ciepły dół per odcinek: na prymie akordu (`BED_ROOT`) trójkąt + sinus oktawę niżej, dolnoprzepustowy 250 Hz;
   poziom liczony z różnicy „podłoga względem głośności odcinka”, odcinek, który ma dość, nie dostaje nic.
3. Dynamiczny EQ 2–6 kHz per odcinek (`MID_ORIG`).
4. „Powietrze” > 6 kHz per odcinek (`HF_ORIG`).
5. Wyrównanie głośności K-ważonej per odcinek do `target`, 4 iteracje, wygładzenie wzmocnienia 10 ms.
6. Opcjonalnie stromy dolnoprzepustowy 15,8 kHz (udaje AAC serwisów).
7. Całość do LUFS, potem limiter szczytów z wyprzedzeniem.

Miękkie wejście szarpanego dźwięku: twarde 2 ms brzmi „punktowo”; lepiej 10 ms liniowo, wyższe harmoniczne wchodzą
później (×1,6 na każdą kolejną, najwyżej 35 ms), szum ataku o połowę ciszej i przez dolnoprzepustowy 7 kHz. Całość
brzmi wtedy dużo spójniej.

## Synchronizacja z obrazem

- Początek przejścia = punkt siatki; uderzenie kamery (warstwa sceny `1.03` → `1.0` w 20 klatek) w tym samym punkcie:
  „klik” w uchu i szarpnięcie w oku to jedno zdarzenie.
- Ruchy puenty (trzecie trącenie filiżanki, upadek) zgodne z wejściem dźwięku, błąd do 3 klatek.
- Bez filmu-wzoru: najpierw tabela odcinków (ile ósemek każdy), z niej jednocześnie oś obrazu i muzyka; zmiana
  rytmu potem tylko w `eighths`.
- Po renderze: `rytm.py sprawdz` z chwilami granic odcinków (`--ciecia`); wszystkie cięcia przesunięte o tyle samo
  to przesunięcie dźwięku przy kodowaniu AAC: poprawiasz jednym przesunięciem całej ścieżki.
- Długi zwój (`dlugi-zwoj.md`): tempo per odcinek 86–104 BPM, cała liczba taktów na odcinek, granice na pierwszej
  mierze (największy błąd 11,7 ms na 24 granicach; jedno tempo dla wszystkich dawało w najlepszym razie 112 ms).
  `muzyka.py` gra jednym tempem: przy zmiennym tempie licz je sam (BPM odcinka = 60 × liczba bitów / długość
  odcinka w s) i sprawdź granice przez `rytm.py sprawdz --ciecia`.

## Kontrola
- Czy każde cięcie, wejście i efekt leży na siatce (`rytm.py sprawdz`: ≤ 1,5 klatki idealnie, ≤ 3 dobrze)?
- Czy przyspieszenie robią krótsze odcinki, a tempo stoi?
- Czy granice odcinków mają twarde wejście bez przenikania i bez dokładanych świstów?
- Czy efekty końca idą w kolejności stop → zawieszenie → uderzenie → reakcja → domknięcie i trafiają w klatki
  zdarzeń (≤ 3 klatki)?
- Czy głośność całości to ok. −14 LUFS, a szczyt prawdziwy ≤ −1 dBTP (`muzyka.py sprawdz`)?
