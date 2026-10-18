---
source: "cinetic (Leonxlnx, MIT): references/taste-and-slop.md i assets/critics/director.md, przepisane po polsku na nasze narzędzia i czas w sekundach; bez zakazów kolorów i krojów"
reviewed: "2026-10-18"
---
# Tanie chwyty: katalog dla krytyka

Wszystko, przez co film wygląda tanio, szablonowo albo „z generatora”, z poprawką. Czytasz przy briefie, zanim
powstanie mapa bitów, i przeszukujesz w każdej rundzie krytyki (`kontrola-wideo` krok 4a). Liczby to sprawdzone
punkty startu przy 1080 px i czasie w sekundach, nie dogmat.

**Jak używać**
- **Podaj ID** na początku problemu w `kontrola.json` i `krytyka.md`: `"problem": "F4: wyjście tytułu na E.out,
  w 1 klatce znika 55%"`. Po ID widać, który chwyt wraca z rundy na rundę.
- **Marka i karta wygrywają.** Gdy właściciel albo kit marki zamawia coś, co tu jest chwytem, robisz to i wpisujesz
  do RAPORT.md: „celowo, bo …”. Reszta katalogu obowiązuje dalej.
- **Szukaj po grupie** (`grep -n '^- \*\*F' tanie-chwyty.md` = ruch) albo po słowie (`grep -n -i 'licznik'`).
- **Szukaj poprawki, nie tylko chwytu.** Każda poprawka ma liczbę albo narzędzie, którym to sprawdzisz.
- Krótka lista domyślnych chwytów z osią kompozycji (maks. 6/10) jest w `zakazane.md`; ten katalog jest pełny.

**Czego tu nie ma (świadomie):** zakazów kolorów i krojów z cinetic (pomarańcz, beż i krem, fiolet, neon, szkło,
gradienty wielu barw, „niebieski z frameworka”, szeryfy, kursywa, kroje wąskie). Kolor i krój wybiera marka
(`assety.py`, `marka.css`, `typografia-edit`). Zostają chwyty rzemiosła: kolor bez znaczenia, krój zastępczy,
tekst nieczytelny. Bez motion bluru (nasza zasada szybkiego renderu): smugi i duchy z `ruch.js`.

**Grupy:** [A Pomysł](#a-pomysł-i-historia) · [B Tekst](#b-tekst) · [C Litery](#c-litery-i-skala) ·
[D Kolor](#d-kolor-i-powierzchnia) · [E Kadr](#e-kadr-i-układ) · [F Ruch](#f-ruch-i-krzywe) ·
[G Przejścia](#g-przejścia) · [H Kamera](#h-kamera) · [I Interfejs](#i-interfejs-produktu) · [J Dźwięk](#j-dźwięk) ·
[K Tempo](#k-tempo) · [L Wykończenie](#l-wykończenie)

## Jak krytyk patrzy (za soczewką „reżyser” cinetic)
1. **Najpierw oglądasz, potem czytasz kod.** Arkusze klatek (`krytyka.py telefon`, `pasek`, `qa.jpg`) w kolejności,
   pierwsze wrażenia zapisane, zanim otworzysz kod: po kodzie wybaczasz to, czego widz nie wybaczy.
2. **Najsłabsze 3 sekundy:** które i dlaczego. Potem tanie, szablonowe, wolne, niejasne i martwe chwile z tego katalogu.
3. **Konkret:** czy film byłby tak samo prawdziwy o prostszym produkcie? Jeśli tak, dowód pokazuje wersję naiwną (A9).
4. **Bez dźwięku:** czy historia czyta się z wyłączonym głosem? Czy rzecz-nośnik idei nie znika na cięciach (A6)?
5. **Priorytet:** **P0** widać w kluczowej chwili (hook, puenta, logo) albo psuje historię; **P1** widać przy zwykłym
   oglądaniu; **P2** tylko na pauzie. Najwyżej 12 zmian, od największego zysku na minutę poprawki; każda z plikiem
   i wartościami („`odslona: 2.4 → 2.0` w `sceny.js`”, nie „popraw tempo”). Nie dopisujesz tekstu, nie zgłaszasz
   tego, co już poprawione, i nie wypisujesz, co jest dobrze.

## A. Pomysł i historia
- **A1 Wycieczka po funkcjach.** Funkcja, funkcja, funkcja, logo: widz nic nie zapamięta. **Poprawka:** problem → zwrot → obietnica; test usunięcia w obie strony (`rodzaje-filmu`).
- **A2 Zła pierwsza klatka.** „Przedstawiamy…”, pytanie, logo albo pusta klatka na start. **Poprawka:** start w środku problemu; czuć go w 1 s, pada w 2 s (`krytyka.py tempo`, oś hook).
- **A3 Pożyczone rekwizyty.** Rakieta, żarówka, globus z łukami, wykres w górę, lewitujący telefon, iskierki „AI”, tarcza „bezpieczeństwo”. **Poprawka:** test własności: obraz z przedmiotów produktu (`assety.py`).
- **A4 Styl udający pomysł.** „Odważnie, kinetycznie, minimalistycznie”. **Poprawka:** najpierw idea, nośnik i gramatyka ruchu w BRIEF; styl z nich wynika.
- **A5 Pokaz bez przyczyny albo pospieszny wynik.** Interfejs rusza się, bo tak każe oś, wynik znika po 0,2 s. **Poprawka:** przyczyna → akcja → wynik; wynik stoi ≥ 0,6 s + 0,1 s na słowo.
- **A6 Nośnik znika.** Rzecz niosąca ideę gaśnie na cięciu albo zmienia rozmiar i kolor na szwie. **Poprawka:** pełna widoczność przez każdy szew; przekazanie na wspólnym przedmiocie.
- **A7 Klatki przeczą obietnicy.** Przekreślenie na haśle, nachodzące kafle w ujęciu „wszystko się mieści”, sukces w kolorze błędu. **Poprawka:** każdą klatkę kluczową czytasz dosłownie, jak stopklatkę.
- **A8 Plansza końcowa z odzysku albo martwa.** Powtarza odsłonę ze środka, stoi 2,7 s, ściemnia do czerni, ostatnia klatka bez marki. **Poprawka:** nośnik staje się znakiem; 1,5–2 s, które rosną o 10–20%; ostatnia klatka to plakat.
- **A9 Funkcja spłaszczona.** Film byłby tak samo prawdziwy o głupszym produkcie (równy podział zamiast pozycji, lista zamiast rankingu). **Poprawka:** dowód pokazuje nieoczywiste zachowanie.
- **A10 Produkt bez nazwy.** Funkcja nienazwana, nic nie mówi, że to aplikacja. **Poprawka:** nazwa funkcji raz (etykieta w UI, zdanie albo plansza) i tyle prawdziwego interfejsu, by czytał się jak aplikacja.
- **A11 Plansza bez faktu z briefu.** Brief mówi „od przyszłego tygodnia”, „już jest” albo podaje adres, a film kończy się samą nazwą. **Poprawka:** ten jeden fakt pod znakiem, mniejszym stopniem, czytelny ≥ 1,7 s.

## B. Tekst
- **B1 Gramatyka strony docelowej.** Nadtytuły nad nagłówkiem („NOWOŚĆ”, „01 / SZYBKOŚĆ”), hasło pod hasłem, drobne etykiety wersalikami. **Poprawka:** usuń; hierarchia z wielkości i kolejności wejścia.
- **B2 Frazy z magazynu.** „Bezproblemowo”, „odblokuj”, „rewolucja”, „oparte na AI”, „przyszłość …”; wykrzykniki, emoji, pytania retoryczne. **Poprawka:** słowa z własnego filmu; zdania kończą się kropką.
- **B3 Nazwa funkcji jako nagłówek.** „Smart Split”. **Poprawka:** co zmienia się dla widza, w ≤ 5 słowach.
- **B4 Ściana tekstu.** Dwa zdania do przeczytania naraz, akapity, listy, wypełniacze (fałszywe liczby, numery wersji, lorem). **Poprawka:** jedna linia naraz, kawałki 1–5 słów (`pomiar.py`: `kawalek`, `slow_naraz`, `tempo_slow`).
- **B5 Ponad budżet.** Ponad 35 słów na 30 s, ponad 5 słów w linii, ponad 2 linie w ujęciu. **Poprawka:** najpierw przymiotniki, potem całe linie.
- **B6 Mikrotekst niesie treść.** Komunikat 14–16 px czytelny przez 0,1 s. **Poprawka:** ≥ 22 px przy 1080 i czas na przeczytanie (`krytyka.py telefon`), albo to faktura, która nic nie niesie.
- **B7 Błędy korekty.** „1 elementów”, różna pisownia marki, proste cudzysłowy, „Jan Kowalski”, przykładowe domeny. **Poprawka:** odmiana liczebników, cudzysłowy „ ”, przegląd każdego napisu z planu.

## C. Litery i skala
- **C1 Krój, którego nikt nie wybrał, albo zastępczy.** Domyślny krój systemu albo zastępczy na którejkolwiek klatce. **Poprawka:** krój z marki albo wybrany świadomie, lokalnie z `/_lib/kroje/` (`pomiar.py`: kroje zastępcze = błąd).
- **C2 Prawie te same tokeny.** Grubości 590, 600 i 620 albo odstęp −0,04, −0,05, −0,06 em w różnych scenach. **Poprawka:** jeden token nagłówka (np. 600 / −0,045 em) wszędzie.
- **C3 Płaska skala.** Wszystko 48–64 px. **Poprawka:** zdania 88–128 px, akcent 1,5–1,7× tego, nagłówek do podrzędnego ≥ 2:1.
- **C4 Pochylenie z obrotu 3D.** Obrót przed pochyleniem kładzie cały tekst UI o ~18°. **Poprawka:** kolejność `perspective() rotateZ() rotateX()`; łączne pochylenie ≤ 7°.
- **C5 Kolizje liter.** Przestrzelenie zamyka spację („Wszystkosięmieści”), kropka wisi pod linią, zasłona odsłania czubki liter. **Poprawka:** tekst bez przestrzelenia (`E.outSoft`, `SPR.calm`), miejsce z ramki tuszu po załadowaniu kroju, zasłona z zapasem 8 px (`typografia.py sprawdz`).
- **C6 Rozmycie na każdym słowie.** Albo czytelny tekst rozmyty dłużej niż 0,1 s. **Poprawka:** rozmycie tylko na wejściu (`blurIn` z `tokeny.js`, ostre przed 60% ruchu); ląduje ostre.
- **C7 Drżące liczby.** Licznik zmienia szerokość, znaczniki czasu monospace w aplikacji dla ludzi. **Poprawka:** cyfry tabelaryczne tej samej rodziny; cyfra toczy się 0,1–0,13 s (`licznikBebnowy` z `ujecia.js`).
- **C8 Sztuczki z literami.** Pisanie po literze w nagłówkach, podskok każdej litery, „dekodowanie”, szeroki odstęp w spoczynku. **Poprawka:** odsłona słowami; ruch liter tylko dla jednego słowa-bohatera, wraca do zwykłego odstępu.
- **C9 Odsłona, która myli słowa.** Odsłona po literze przechodzi przez inne słowo, w pół narysowana litera czyta się jak inna. **Poprawka:** nazwy całymi słowami albo maską; sprawdź klatki każdego przedrostka.

## D. Kolor i powierzchnia
- **D1 Akcent bez znaczenia.** Wszędzie, w dwóch przeciwnych znaczeniach albo dwa prawie te same czerwone w kodzie. **Poprawka:** jeden token, jedno znaczenie, ≤ 8% pikseli, jedno zalanie.
- **D2 Ozdoby-wypełniacze.** Cząsteczki, bokeh, gwiazdy, deszcz kodu, tekst-duch na 3–8%, ziarno bez zadania albo inne w każdej scenie. **Poprawka:** każdy element ma zadanie (odsłania, prowadzi, potwierdza, podkreśla) albo wylatuje; ziarno: brak albo jedno na cały film, 1,5–2% (`plotno.js`).
- **D3 Brudne zalania.** Biała poświata zmienia ciemne karty w szare przyciski, szare tło z zabarwieniem. **Poprawka:** ciemne zostaje ciemne; welon 80–85% tylko pod tekstem.
- **D4 Czyste czarne dziury.** Całe tło `#000`, które koder rozjeżdża w bloki. **Poprawka:** ciemne tło z odrobiną barwy akcentu (OKLCH L 0,15–0,18, nasycenie 0,003–0,008).
- **D5 Film bez barwy marki.** Kadr ze środka w 480 px nie ma koloru marki, akcent nie niesie akcji produktu. **Poprawka:** akcent widocznie znaczy kluczowe chwile (produkt działa, puenta), tło ma ton ze świata marki.
- **D6 Znak, który się myli.** W 64 px przez pół sekundy czyta się jak minus, plus, emotka, menu, kłódka, przycisk „play”. **Poprawka:** test pomyłki na arkuszu znaku; asymetryczne pęknięcie zwykle wystarcza.

## E. Kadr i układ
- **E1 Układ SaaS.** Tekst z lewej, karta UI z prawej na bieli albo wszystko na środku, lewitujące. **Poprawka:** produkt na cały kadr, tekst przy linii oczu albo w dolnej trzeciej, jedna akcja w ujęciu.
- **E2 Pustki i pasy przy krawędzi.** 20% kadru pustego pod produktem, ciemna krawędź okna 20–130 px, nagłówek UI nad niczym. **Poprawka:** kamera tak, by produkt kładł kadr; ruchome warstwy 5–8% większe od kadru.
- **E3 Bez marginesów.** Mniej niż 96 px z boków i 64 px góra-dół, mniej niż 24 px zapasu przy najmocniejszym uderzeniu. **Poprawka:** strefy w klatce uderzenia (`pomiar.py`: poza kadrem, pod UI platformy).
- **E4 Kadr tnie litery.** „ftu”, „:00”, tekst przecięty przesuwaną krawędzią karty. **Poprawka:** cięcie w odstępach kolumn; tekst odsłaniasz po przejściu krawędzi.
- **E5 Wersje wycięte z jednej.** 9:16 albo 1:1 wycięte z 16:9. **Poprawka:** osobny układ na każdy format z tej samej osi (`formaty-wideo`).
- **E6 Znak zgubiony w pustce.** Gotowy znak zajmuje mniej niż ćwierć szerokości i nie czyta się w 480 px. **Poprawka:** 28–45% szerokości kadru.
- **E7 Mała karta w pustym polu.** Produkt jako lewitująca karta z tekstem nieczytelnym na telefonie. **Poprawka:** na cały kadr albo najazd, aż pracująca część wypełni kadr.
- **E8 Pusty pion.** 9:16 ułożone jak poziom: pasek treści na środku, dolne 40% puste, stopnie z 16:9. **Poprawka:** masa treści w środku pasa bezpiecznego (y 270–1500 przy 1080×1920), tekst 1,3–1,5× stopni z 16:9.

## F. Ruch i krzywe
- **F1 Domyślne wejście.** Wszystko zanika do widoczności albo wjeżdża z dołu o 30 px. **Poprawka:** jeden system odsłon na rolę, wejścia fizyczne (maska, narodziny ze szczeliny, przemiana); ruchy z `ruchy.py losuj`.
- **F2 Ten sam czas wszędzie.** Każdy ruch 0,4–0,5 s na jednej krzywej. **Poprawka:** czas = 0,35 s + 1,35 ms na px drogi (kamera 0,6–2,4 s); najwolniejszy ≥ 3× najszybszy; ok. 3 charaktery krzywych na film.
- **F3 Sprężynka wszędzie.** Odbicie, elastic, przestrzelenie na każdej karcie, „wesoły” podskok plakietki. **Poprawka:** wyhamowanie bez przestrzelenia; 1–7% przestrzelenia tylko przy prawdziwym lądowaniu, najwyżej 2 na film (`ladowanie` z `ruch.js`).
- **F4 Krzywa w złą stronę.** Wejścia z przyspieszeniem, wyjścia z hamowaniem, zanik na `E.out` (połowa znika w 1 klatce). **Poprawka:** wejścia hamują, wyjścia przyspieszają; zanik 0,17–0,23 s na `E.smooth`.
- **F5 Uderzenie połówką sinusa.** Puls w twardym oknie: szarpie na obu końcach, szczyt 0,1 s po dźwięku. **Poprawka:** `hitPulse` z `tokeny.js` dla każdego uderzenia i tyknięcia.
- **F6 Liniowy zoom i ściana.** Skala liczona liniowo, kamera staje w miejscu z pełnej prędkości. **Poprawka:** `lmix` dla skali, krzywa z miękkim końcem dla ruchów do spoczynku.
- **F7 Stop, potem szarpnięcie.** Dwa ruchy hamują do zera, następny rusza z pełną prędkością. **Poprawka:** kolejne ruchy zachodzą na siebie o ~0,33 s albo drugi startuje na krzywej z płaskim początkiem.
- **F8 Wszystko rusza się naraz.** Kołysanie w spoczynku, pulsujące plakietki, zoom w każdej scenie. **Poprawka:** jeden ruch-bohater i najwyżej 2 pomocnicze; bezruch po ruchu to narzędzie.
- **F9 Lądowania hurtem.** 6–7 rzeczy uderza w tej samej klatce. **Poprawka:** rozsunięcie 0–0,05 s w grupie, pierwsza na bicie (`stagger`).
- **F10 Kształt przeskakuje.** Proporcje zmieniają się w ostatnich 1–2 klatkach, bo jedna krzywa liczy rozmiar i pozycję. **Poprawka:** kształt osiada 0,1 s przed pozycją; lądowanie z dociskiem (`squash`: 1,08 / 0,9 → 1 w 0,13 s).

## G. Przejścia
- **G1 Przenikanie domyślnie.** Albo dwa niedopasowane kontury nałożone na 0,4 s. **Poprawka:** przemiana pojemnika albo maska z wcięciem; zawsze widać jeden kontur (`morph.js`).
- **G2 Gotowce i powtórki.** Glitch, rozszczepienie RGB, flara, spalenie taśmy, wir, fala, „senny” zoom, błysk do bieli; ta sama tęczówka trzy razy. **Poprawka:** 6–8 umotywowanych rodzajów, każdy ≤ 2 razy, plus jeden ruch-podpis ze znaku na początku, w środku i na końcu (`ruchy.py losuj --kategoria przejscie`).
- **G3 Przeskok zamiast ruchu.** Znak znika w 2 klatki, plakietka zmienia stan w 1 klatce. **Poprawka:** wyjście = odwrócone wejście albo świadome cięcie na bicie (`qa_wideo.py`: skok).
- **G4 Prędkość nie pasuje na cięciu.** **Poprawka:** ujęcie wychodzące przyspiesza przez ostatnie 0,4–0,5 s, cięcie w szczycie prędkości, wchodzące hamuje.
- **G5 Zacięcie na szwie i spadki.** Powtórzona klatka na szwie (stop, stoi, rusza) albo przenikanie przez czerń z ~25% spadkiem jasności. **Poprawka:** pozycję spoczynku pokazujesz raz (`qa_wideo.py`: zamrożona klatka); zmianę jasności niesie ruchomy kształt.

## H. Kamera
- **H1 Lewitujące zrzuty.** Pochylone karty zrzutów, przelot przez pole zrzutów, makieta urządzenia krążąca w pustce. **Poprawka:** prawdziwe elementy w 3D, perspektywa 1800–2600 px, jedna oś kamery na akt; sprzęt tylko, gdy sprzęt jest produktem.
- **H2 Kamera na statywie.** Średnia zmiana klatki ~0,1 przez ponad 1,5 s. **Poprawka:** najazd 2–3%/s i ~16 px dryfu z paralaksą (`ujecia.js` `paralaksa`, `strona.js` `najazd`).
- **H3 Niewidoczny dryf.** 1 → 1,05 przez 2 s na logo czyta się jak martwe. **Poprawka:** krótki bezruch znaku (0,6–1,3 s po złożeniu w 1–1,3 s) albo najazd 10–20% przy dłuższym; dryf interfejsu 30–90 px/s.
- **H4 Ruch za szybki na oko.** Element pokonuje 150–1000 px w klatce: przy naszym renderze bez motion bluru to schodki kopii. **Poprawka:** jeden element do ok. 4000 px/s przy 1080; szybciej: cięcie na bit, cięcie dopasowane, maska albo krótsza droga. Od ok. 700 px/s smuga albo duchy z `ruch.js` (`predkosc` mówi, kiedy).

## I. Interfejs produktu
- **I1 Interfejs z wyobraźni.** Fałszywe wskaźniki, wykres w górę, losowe liczby, ikony z banku, zrzut powiększony do rozmycia. **Poprawka:** prawdziwe powierzchnie produktu (`assety.py --film`), dane z jednego pliku.
- **I2 Dane się kłócą.** Data w zły dzień tygodnia, licznik 7 przy 12 elementach, etykiety sprzed ruchu. **Poprawka:** każda etykieta liczona z danych; liczby kontra `fakty.json` (`pomiar.py`).
- **I3 Stan, który nie liczy.** Licznik stoi w czasie akcji i przeskakuje w jednej klatce albo zmienia się bit po zdarzeniu. **Poprawka:** zmiana w klatce lądowania każdego zdarzenia, liczona w całych klatkach (`fd`), z tych samych chwil co dźwięk.
- **I4 Zła kolejność warstw.** Plakietka przykryta następnym awatarem, uniesiona karta pod leżącą, komunikat na wyniku. **Poprawka:** rysowanie po z; plakietka z obwódką 2 px w kolorze tła.
- **I5 Czego żadna aplikacja nie ma.** Kursor tekstowy 8–75 px od tekstu, etykieta, której grubość się animuje i przestawia linię. **Poprawka:** wypełnienie rośnie z odsłoną, grubość stała; animujesz tylko wypełnienie i kolor.
- **I6 Robotyczny kursor.** Proste drogi ze stałą prędkością, kursor zaparkowany, kursor przy produkcie, który działa sam. **Poprawka:** łuk 15–25% drogi, przejazd 0,6–0,8 s, wciśnięcie do 0,88 w 0,07 s, ≤ 1 klik na 0,5 s; bez kursora, gdy produkt działa sam (`klik` z `ujecia.js`).
- **I7 Historia i dane się kłócą.** Kto zapłacił, ten pokazany jako dłużnik; proporcja nie pasuje do liczb obok. **Poprawka:** fakty historii sprawdzone w danych przed renderem.
- **I8 Tekst przykryty ruchem.** Karta przejeżdża po etykiecie, którą widz właśnie czyta. **Poprawka:** droga przez odstępy albo tekst nad ruchomym elementem (`pomiar.py`: napisy na sobie).

## J. Dźwięk
- **J1 Dźwięki z biblioteki na wszystkim.** Szum na każdym cięciu, efekty-memy, narastanie → uderzenie wszędzie. **Poprawka:** ok. 2 „whoosh” na film, tylko na ruchach kamery i najazdach na znak, start 0,1–0,45 s przed szczytem ruchu; narastanie kończy się stopem albo ciszą (`lektor-i-dzwiek`, `projekt.py zdanie`).
- **J2 Poza synchronem.** Dźwięk przed obrazem o ponad 45 ms, uderzenie na osiadaniu zamiast kontaktu, część akcji jednego rodzaju bez dźwięku. **Poprawka:** chwile z kodu obrazu (`cues.json`), uderzenie w klatce kontaktu, ±1 klatka; każda akcja rodzaju na jednym poziomie.
- **J3 Efekty zagłuszone.** 13–25 dB pod muzyką w swoim paśmie. **Poprawka:** ≥ +6 dB w paśmie efektu, muzyka −3 dB na 150 ms wokół kluczowych uderzeń (`projekt.py slychac`).
- **J4 Nie w tonacji.** Niestrojone uderzenia i tyknięcia, narastanie lądujące o trytom obok. **Poprawka:** efekty z wysokością strojone do podstawy akordu (`muzyka.py`).
- **J5 Złe zakończenie.** Trzask na końcu bufora, koniec urwany w pół nuty, logo jako najgłośniejsza chwila. **Poprawka:** najgłośniej przy odsłonie bohatera; na końcu muzyka cichnie, gdy znak się składa, 0,2–0,7 s prawie ciszy, jeden miękki dźwięk na znaku, wybrzmienie 0,5–2,5 s.
- **J6 Terkot pisania.** Jasny klik na każdy znak zlewa się w brzęczenie. **Poprawka:** ciemny, stały dźwięk na klawisz (±1,2% wysokości), muzyka −10 dB pod pisaniem, najwyżej ok. 12 uderzeń/s.
- **J7 Dźwięk na każde zdarzenie obrazu.** Albo odwrotnie: cięcie spóźnione ćwierć sekundy za bitem. **Poprawka:** cięcia i szczyty prędkości na siatce, niesie je muzyka; ok. 5 efektów na 10 s na wyraźnych zmianach stanu (`rytm.py sprawdz`).
- **J8 Płaski miks.** Rozpiętość głośności poniżej 5 LU w filmie od 20 s, puenta prawie nie głośniejsza. **Poprawka:** przerzedzenie przed zwrotem, cisza przed wejściem, puenta 2–3 LU nad medianą (`qa_wideo.py`: LRA).
- **J9 Miękki hook dźwięku.** Muzyka narasta z ok. −25 dB przez pierwszy takt, pierwsza sekunda brzmi jak nic. **Poprawka:** dźwięk z widoczną przyczyną od klatki 0; wstęp może być cichszy, ale wchodzi z zamiarem.
- **J10 Zła energia do marki.** Zwiastunowe basy i narastania pod spokojną marką albo nieśmiały podkład pod szybką premierą. **Poprawka:** najpierw charakter ruchu marki (`ruch-i-kompozycja.md`), spokojnym markom miękkie uderzenia i jeden łagodny akord.

## K. Tempo
- **K1 Słaby hook.** 1–2 s prawie pustego kadru, który wyciszony feed czyta jak zawieszony odtwarzacz. **Poprawka:** klatka 0 skomponowana i w ruchu; widoczna zmiana co ok. 0,5 s.
- **K2 Martwe postoje.** Ponad 0,8 s bez widocznego życia, np. logo stoi 1,6–2,4 s. **Poprawka:** każdy postój rośnie; zaprojektowana stopklatka ≤ 0,25 s i dokładnie na ciszy (`krytyka.py tempo`, `martwe`).
- **K3 Upychanie.** 17 scen w 32 s albo 3 funkcje w 5 s. **Poprawka:** 8–10 bitów historii na 30 s i 1–2 możliwości produktu.
- **K4 Płaska energia.** Środek 10× spokojniejszy od reszty albo szczyty bez spokoju między nimi. **Poprawka:** jeden szczyt ruchu na takt i 0,5–1,2 s spokoju między; pierwsze 6 s ok. 2× gęstsze niż środek.
- **K5 Poza siatką.** Cięcia i uderzenia ignorują muzykę. **Poprawka:** siatka BPM; zmiany części na mocnych częściach taktu, cięcia na ósemkach (`rytm.py`).
- **K6 Miękka pierwsza sekunda.** Klatka 0 skomponowana, ale rusza się tylko pierwsza linia i problemu nie czuć w 1 s. **Poprawka:** nośnik i stan produktu ruszają od klatki 0, zmiana co ok. 0,5 s.

## L. Wykończenie
- **L1 Duchy i mrugnięcia.** Pojedyncze klatki inne niż sąsiednie, stany zgubione przy seek. **Poprawka:** czyste funkcje czasu, `krytyka.py determinizm`, `qa_wideo.py`: duch.
- **L2 Schodkowe rozmycie.** Animowane rozmycie CSS przeskakuje z ostrego na miękkie w jednej klatce. **Poprawka:** przenikanie ostrej kopii i kopii o stałym rozmyciu.
- **L3 Schodki pikseli.** Powolny ruch skacze całymi pikselami co 0,1–0,13 s (ułamkowe `left`/`top` z `transform`). **Poprawka:** całe przesunięcie w jednym `transform` (`qa_wideo.py`: drgania).
- **L4 Pełzające włoski.** Linie cieńsze niż 1,5 px albo przerwy poniżej 8 jednostek pełzną jak kreski przy skali i perspektywie. **Poprawka:** grubsze linie, szersze przerwy, włoski wygaszone przy małej skali.
- **L5 Pasy.** Gradient CSS na mniej niż ~30 poziomach jasności pokazuje pierścienie. **Poprawka:** ziarno 1–2% na gradiencie albo tło z ditheringiem (`qa_wideo.py`: pasy).
- **L6 Niedbałe oddanie.** Podgląd bez znaczników koloru, pośrednie JPEG q80, wysokie CRF. **Poprawka:** BT.709, JPEG q95, CRF 14–16; oddanie przez nasze render i `qa_wideo.py`.
- **L7 Bałagan w folderze oddania.** Arkusze, próby i raporty obok filmu. **Poprawka:** do oddania tylko film i raport; materiały kontroli w `out/wideo/<film>/qa/`.
