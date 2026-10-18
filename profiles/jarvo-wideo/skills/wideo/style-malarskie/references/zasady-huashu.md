# Zasady huashu: co się sprawdziło (z dowodami)

Surowiec do naszych reguł: zasady z repo huashu-art-motion (MIT), które zadziałały w praktyce. Każda ma postać
**zasada → dowód (liczba, jedno zdanie) → kiedy stosować**, czasem z „dlaczego”, jeśli źródło je podaje. Pułapki są
w kartach metody (`metoda.md`, rozdz. 8). Gdy zasada zadziała u nas ponownie, dopisz dowód; gdy zawiedzie, opisz
granicę.
Zasady ogólne (nie tylko dla stylów malarskich) są też w skillach ruchu i kontroli: `ruch-i-kompozycja.md`
(skill `rodzaje-filmu`; rozdz. 2: 4, 5, 28; rozdz. 4: 11, 31, 46; rozdz. 5: 3, 27, 43; rozdz. 7: 12, 13, 14, 19, 29),
`film-z-kodu` prawa 14–17 (15, 41, 37, 39, 49), `kontrola-wideo` kroki 2 i 4a (16, 25, 30, 48).

Numeracja jest ciągła. W źródle numery 33–35 występują dwa razy, a jeden wpis nie ma numeru: tu to zasady 33–40.
Litery A, B, G1–G3 to niezależne grupy wykonawców testów (A, B: nowe style; G1, G2: gramatyki z YouTube;
G3: gramatyki nauki i finansów). `qa.py` źródła odpowiada u nas zestaw: `krytyka.py determinizm`, `qa_wideo.py`,
`krytyka.py martwe` / `puls`, `html_wideo.py pomiar`; ich `breakdown.py` to u nas `kadry.py wzor`.

## I. Reżyseria i mechanizm

**1. Przejście = język-podpis następnego stylu.**
- Dowód: tak zbudowano 15 przejść repliki; 2 niezależnych wykonawców uznało to zdanie za najcenniejsze
  i najbardziej przenośne w całym skillu, a 9 nowych przejść (złoto rozwijane spiralą, wstęgi koloru z „Krzyku”
  spychające w dół, szarfy apsar zdzierające stary obraz, rosnące kropki, topniejące krople, twarde światło słońca,
  rozlewanie po mokrym papierze, rwanie VHS…) wyprowadzili z niego bez błądzenia.
- Dlaczego: przejście robi dwie rzeczy naraz, żegna stary styl i zapowiada nowy; widz w 0,3 s wie, „kto następny”.
- Kiedy: każde przejście między stylami. Wypisz najbardziej rozpoznawalne elementy nowego stylu (materiał,
  pociągnięcie, motyw, usterka nośnika), wybierz ten, który może urosnąć „od zera do pełna”, i zrób z niego proces
  wyrastający z przedmiotu w kadrze (kot, filiżanka, głowa).

**2. Jeden szkielet, jedna choreografia, N technik = „ta sama para w podróży” za darmo.**
- Dowód: `RIG.girl` / `RIG.cat` zwracają Path2D i punkty zaczepienia, użyte we wszystkich 36 stylach; A i B
  zgodnie: przy zmianie stylu postać i kot stoją na miejscu, a pozycje i ruch zgadzają się same.
- Kiedy: najpierw szkielet postaci i krzywe ruchu, potem style; styl zmienia tylko „jak malować”, nie „gdzie
  i jak się rusza”.

**3. Ruch bohatera jest ciągły między odcinkami, z czasu całego filmu.**
- Dowód: w pierwszej wersji A każdy odcinek zaczynał picie od nowa (czas lokalny) i recenzja napisała, że widz widzi
  „5 razy podnosi filiżankę”, a nie tę samą chwilę w 5 stylach; po przejściu na czas filmu (`PAINT.cupCycle(t)`)
  poza zgadza się po obu stronach przejścia, a wpadka „dwie głowy” znika.
- Kiedy: przegląd i podróż przez style: ruch postaci zawsze z `t` filmu; czas lokalny `lt` tylko dla występu
  przypisanego jednemu odcinkowi.

**4. Siatka bitów i uderzenie kamery na obu warstwach, starej i nowej.**
- Dowód: v1 uderzała tylko nową warstwą i 6 z 15 przejść spóźniało się o 0,1–0,17 s; po uderzeniu obu warstw
  pierwsza zmiana obrazu we wszystkich 15 przejściach wypada na bicie (±2 klatki), różnica klatek na bicie 7–33.
- Kiedy: każdy montaż pod bit: w klatce bitu musi być zmiana widoczna na całym ekranie.

**5. Otwarcie: pierwszy obraz „maluje się sam”.**
- Dowód: w teście A odcinek tuszu przez pierwsze 0,45 s wypisuje pociągnięcia i rozlewa tusz; recenzja przyjęła,
  klatka 0 nie jest już pustym papierem.
- Kiedy: pierwszy odcinek nie ma przejścia, z którego mógłby wyjść: otwórz procesem tworzenia tego stylu
  (pociągnięcia się wypisują, kolory druku spadają warstwa po warstwie, piksele zapalają się wiersz po wierszu).

## II. Piękno obrazu

**6. Paleta regionu jest ważniejsza niż drganie koloru.**
- Dowód: pierwszy Van Gogh z samym drganiem koloru był „szumem jednego niebieskiego”; dopiero 7–8 kolorów na
  region (`P.swatch`) dało Van Gogha, a Munch w A (niebo, fiord, góry, ściana, ziemia, każde z osobną grupą)
  przeniósł to wprost z sukcesem.
- Kiedy: każdy styl pociągnięć i plamek: najpierw grupy kolorów regionów, każde pociągnięcie losuje kolor z grupy,
  potem domieszaj 30–45% koloru podkładu, żeby zachować jasności.

**7. Duże płaszczyzny rendererowi, małe przedmioty i postać osobno, linie na końcu.**
- Dowód: słoneczniki i nogi stołu duże pociągnięcia rozbijały w plamę, po rozdzieleniu warstw są czytelne;
  „dwie wersje światła z przycięciem” Hoppera w B to uogólnienie tej zasady.
- Kiedy: style olejne i graficzne. Granica: tusz, grafika i style wzorów mają inną kolejność (papier jest podkładem,
  tusz tylko dochodzi; wzór sam jest rendererem), `metoda.md` rozdz. 4.

**8. Postać przechodzi przez ten sam renderer, inaczej wygląda jak naklejony wycinek.**
- Dowód: w 36 stylach najlepiej zlewają się postacie przepuszczone przez renderer (drobne pociągnięcia Van Gogha,
  kamienie mozaiki, piksele 8-bit, płaszczyzny kubizmu, sylwetka czarnofigurowa, ażur teatru cieni), a postacie
  tylko płasko wektorowe to najsłabsze miejsca odcinków (postać w tuszu 6/10, Ghibli „jak płaski wektor”, Dalí
  „za bardzo ilustracja wektorowa”).
- Kiedy: zawsze; po płaskich kolorach postaci co najmniej jedna obróbka materiałem stylu: pociągnięcia, ziarno,
  papier przez `multiply`, rozlany brzeg tuszu, raster, przesunięcie kolorów druku.

**9. Napisy stylu rysowane ścieżką mają więcej stylu niż krój.**
- Dowód: w B cyrylica z modułów 5×7 i kana z rurek neonu, w Rzymie litery mozaiki (jednakowo gruba kreska, każda
  ≥ 2 kamienie szerokości); podzbiór kroju bez znaku po cichu spada na krój systemowy i na innej maszynie wygląda
  inaczej.
- Kiedy: tytuł, szyld, podpis najlepiej ścieżką w materiale stylu; jeśli krój, najpierw sprawdź glify (u nas też
  polskie znaki: nakładka `huashu_pl.js`, `html_wideo.py pomiar` → `czcionka_zastepcza`).

**10. Fizyczny proces powstawania materiału to renderer.**
- Dowód: ukiyo-e „kolor przesunięty o (3,2) px wobec linii + poziome smugi cieniowania” = druk z wielu klocków;
  mozaika „układ liczony raz, kolor co klatkę płynie przez kamienie” = prawdziwy sposób animowania mozaiki; złoto
  „szum szczotkowania z częstotliwością w osi y 20× większą niż w x” dało metal za pierwszym razem, a Klimt w A wziął
  to wprost.
- Kiedy: zanim napiszesz renderer, zapytaj, jak taki obraz robi się naprawdę, i zapisz ten proces w kodzie.

**11. Małe rzeczy rób większe, niż podpowiada intuicja.**
- Dowód: pazury fali ukiyo-e w 22–50 px są nieczytelne, w 44–74 px to dopiero „Wielka fala w Kanagawie”; A powiększył
  krewetkę Qi Baishiego 1,45× i apsarę 1,35×, zanim się czytały.
- Kiedy: każdy rozpoznawalny motyw i rekwizyt; czytelność sprawdzasz na stopklatce w rozmiarze docelowym.

## III. Ruch

**12. Każda scena = ruch główny + 2–4 pętle wzięte z motywów stylu.**
- Dowód: samo przełączanie obrazów nie pokazuje ruchu w obrazie; 16 odcinków zrobionych według tej zasady ma obszar
  ruchu 1,6–14% i zero skoków.
- Kiedy: listę ruchów motywów weź z rozpisu wzoru; bez wzoru wypisz 3 najbardziej rozpoznawalne elementy formalne
  stylu i każdemu daj sposób ruchu.

**13. Pole kierunków zmienia się w czasie płynnie, zamiast nowego ziarna 8 razy na sekundę.**
- Dowód: przetasowanie całego kadru 8 kl./s dawało różnicę klatek 18–20 (więcej niż przejście) i recenzja czytała to
  jako „obraz migocze”; z pociągnięciami w miejscu i płynnie falującym polem kierunków: 0 skoków, obszar ruchu 9%.
- Kiedy: każdy styl pociągnięć na całym kadrze; „wrzenie” zostaje tylko dla linii rysunku.

**14. Okres modulo przewijanego wzoru = prawdziwy okres wzoru.**
- Dowód: w A sukienka w kropki liczona modulo odstępu kropek skakała w klatce zawinięcia (różnica klatek 2,7×
  większa); modulo dwóch rzędów siatki sześciokątnej skok znika.
- Kiedy: każdy przewijany wzór (meander, kropki, fryz, taśma).

## IV. Stabilność i wydajność

**15. Specyfikacja + wzorcowa scena + równoległe grupy wykonawców = odbiór za pierwszym razem.**
- Dowód: 16 epok w 4 równoległych grupach po 30–35 minut, wszystkie przyjęte za pierwszym razem; potem 4 grupy
  testów przeniesienia (20 nowych stylów) tak samo.
- Kiedy: praca dzielona między podagentów: specyfikacja z interfejsem, bibliotekami, wymaganiami twardymi,
  samokontrolą i notatkami do oddania (`metoda.md` rozdz. 10); wzorcowa scena pozwala skopiować „pięć warstw”.

**16. Przed oddaniem zawsze niezależny recenzent, który ogląda tylko gotowy film.**
- Dowód: recenzja repliki v1 złapała 4 typy błędów (spóźnienie na bicie, migotanie całego kadru, za mało ruchu, kot
  wypadający z roli), w A „5 razy podnosi filiżankę”, „dwie głowy”, „przezroczyste ramię”, w B „ЧАЙ czytane jako
  ЧАИ” i „różowy strój wygląda jak brak ubrania”; autorzy nie zauważyli tego w 3 rundach.
- Kiedy: każdy film z wielu odcinków (u nas podagent bez wiedzy o kodzie i skill `kontrola-wideo`).

**17. Odbiór liczbami.**
- Dowód: `qa.py` w 40 s mierzy 16 odcinków (obszar ruchu, statyczne pary klatek, skoki, prawdziwy czas z wymuszonym
  GPU flush, deterministyczność); sama różnica początku i końca przeoczy zacięcie (A: Klimt zmienia się w 33%, a 14
  z 48 par klatek stoi), a sam czas JS daje fałszywe 1 ms (B).
- Kiedy: każdy odcinek. U nas `krytyka.py determinizm`, `qa_wideo.py` (duchy, skoki, zamrożone klatki),
  `krytyka.py martwe` i `puls`, `html_wideo.py pomiar`; czas klatki mierzysz prawdziwym renderem.

**18. Każdy los z ziarnem; ta sama chwila dwa razy = identyczne piksele.**
- Dowód: wszystkie 36 stylów przeszło porównanie renderu „na zimno” i „na ciepło”; render nie migocze, a film można
  renderować kawałkami i sklejać.
- Kiedy: zawsze (`krytyka.py determinizm … --preset jarvo`).

**19. Statyczne części w cache, co klatkę rysujesz tylko to, co się rusza.**
- Dowód: Bauhaus 2,5 ms, pop-art 5 ms, 8-bit 3 ms na klatkę; w B 4 z 5 odcinków ma całe tło w cache; najcięższy
  Van Gogh (trzy przebiegi pociągnięć na całym kadrze) 117 ms, a cały film 60 kl./s renderuje się w mniej niż
  2 minuty.
- Kiedy: każda scena (`PAINT.cached`).

## V. Rozpis i wzory

**20. Klatka wzoru jako referencja generacji trzyma kompozycję; klatkę koncepcyjną czytasz przez siatkę.**
- Dowód: model obrazu z klatką oryginału jako referencją daje przy nałożeniu 50% prawie piksel w piksel; szkielet
  dziewczyny z ręcznych współrzędnych wyglądał jak chłopiec, a po odczycie punktów przez siatkę 20 px od razu był
  17-letnią blondynką.
- Kiedy: klatka koncepcyjna (`metoda.md` rozdz. 2) i współrzędne szkieletu postaci (rozdz. 6).

**21. Mapa ruchu przed startem pokazuje, że „obraz żyje”.**
- Dowód: mapa ruchu wzoru pokazała, że w każdym odcinku rusza się 2,5–34% powierzchni (a nie stoi jeden obraz),
  i to przesądziło o całej drodze produkcji.
- Kiedy: przed każdym filmem ze wzoru: `kadry.py wzor` → `ruch-1.jpg` (na czerwono, co się rusza w odcinku)
  i `ruch_proc` każdego odcinka w `wzor.json`; szczegół akcji: gęsty arkusz `--fps …` i `krytyka.py pasek`.

**22. Siatkę dopasowujesz jako „największy krok przy ≥ 80% punktów wewnętrznych”.**
- Dowód: najmniejsza suma błędów wybiera bardzo mały krok i na siłę dopasowuje wszystko; po zmianie z 16 wykrytych
  punktów wyszło 14,1 klatki (ósemka przy 128 BPM), a 3 fałszywe punkty oznaczone jako odstające.
- Kiedy: rozpis rytmu cudzej muzyki albo montażu (`rytm.md`); u nas `kadry.py wzor` (pole `siatka`). Przy kilku
  startach siatka bywa przypadkowa: `przypadek` mówi, jak często losowe starty dają równie duży krok; tempo bierzesz
  z niej tylko przy `pewna` (≤ 5% albo krok pasuje do tempa muzyki z `rytm.py`).

## VI. Skala (scalenie 36 stylów)

**23. Najpierw niech niezależni wykonawcy zrobią własne narzędzia, potem zbierz je do biblioteki.**
- Dowód: 4 grupy testów napisały własne pędzle, renderery i postprodukcję; przy scaleniu powstały `brush.js` (7),
  `render.js` (14) i `post.js` (6), a po przeniesieniu 20 odcinków na wspólną bibliotekę 16 z nich poza ramką
  postaci jest identycznych piksel w piksel z oryginałem.
- Dlaczego: biblioteka zrobiona z góry ma abstrakcje, których nikt nie używa; do biblioteki trafia to, co
  powtórzyło się co najmniej 2 razy, a trzecie powtórzenie to znak, że czas zebrać.
- Kiedy: rozbudowa wspólnych bibliotek (u nas `/_lib/jarvo/`).

**24. Test przeniesienia to najlepsza specyfikacja potrzeb.**
- Dowód: zadanie „przeczytaj tylko skill, zrób styl, którego skill nie ma, napisz uwagi” dało od 4 wykonawców
  ponad 60 konkretnych problemów (ciche degradacje, długość filmu na sztywno, pomiar czasu bez flush, błąd szkieletu,
  źle opisane `dabs`), każdy z odtworzeniem; autor używający skillu sam nie trafił na żaden.
- Kiedy: po każdej dużej nowej zdolności skillu 2 wykonawców, którzy czytają tylko skill, robi nieznane zadanie
  i oddaje „co pomogło / gdzie utknąłem”.

**25. Narzędzie odbioru też trzeba odebrać.**
- Dowód: `qa.py` świecił na zielono, ale nie wykonywał kodu przejść, więc przejście z nieistniejącą funkcją
  wywalało całą klatkę bez zgłoszenia (dopiero test dymny przejść to złapał); sprawdzanie glifów przez
  `measureText` nie zgłaszało braków na Macu i zostało zastąpione czytaniem tablicy znaków pliku kroju.
- Kiedy: każdy punkt kontroli raz celowo zepsuj (usuń scenę, popsuj przejście, użyj brakującego znaku) i sprawdź,
  że naprawdę świeci na czerwono.

## VII. Gramatyki filmu objaśniającego (5 z YouTube, 3 z nauki i finansów)

**26. Najpierw zmierz próbki, potem ustal gramatykę.**
- Dowód: pierwszy Vox w G1 miał przejście darciem papieru, którego w 5 policzonych klatka po klatce filmach Vox nie
  ma ani razu, a pierwsza tablica miała dymki myśli, których nie ma w próbkach RSA; G2 zmierzył film TheOdd1sOut:
  średnie ujęcie 2,4 s, 70% sąsiednich klatek bez żadnej zmiany.
- Kiedy: przed nową gramatyką weź 2–5 reprezentatywnych filmów i zmierz długość ujęć, udział bezruchu i typy przejść
  (`kadry.py wzor`: `sr_odcinek_s`, `bez_zmian_proc`, arkusze `przejscia/`), dopiero potem pisz kartę. Zapamiętane „cechy stylu” często należą do kogoś innego.

**27. Kamera zależy tylko od czasu filmu; funkcja przejścia tylko składa dwa ujęcia.**
- Dowód: przejazd ze skalą ×60 w Kurzgesagt jest w całości przerysowywany wektorowo i się nie rozmywa; w Vox
  „przejście” biurko → tablica to sam ruch kamery, 0 skoków; w G3 przejście najazdem prowadzi dalej kamerę starego
  ujęcia zamiast powiększać zrzut, a przy przejściu przez okrągły obiekt powiększenie musi być ≥ 1100/promień, inaczej
  ostatnia klatka skacze.
- Kiedy: płótno świata + wizjer kamery; nie rób przejścia skalowaniem wyrenderowanej bitmapy.

**28. Akcentem jest klatka „odsłonięcia”.**
- Dowód: w G2 (typografia kinetyczna) początek odcinka = kreska taktowa − punkt odsłonięcia × długość przejścia
  i wszystkie zdarzenia wizualne są w tej samej klatce co stopa; to ta sama zasada co nr 4 w innym przypadku.
- Kiedy: każde wejście tekstu albo obiektu pod bit: na bicie ma wypaść odsłonięcie, nie start animacji.

**29. Bezruch to nie zacięcie: gęstość ruchu wynika z gramatyki.**
- Dowód: w storytime 70% klatek stoi i to jest styl (puenta to cięcie na zbliżenie reakcji i milczenie); w kinetic
  napis po wylądowaniu już się nie rusza, ruch dają kamera i tło; próg „statyczne pary > 40% = zacięcie” tych dwóch
  nie dotyczy.
- Kiedy: liczby czytaj według gramatyki: przegląd stylów „żyje cały czas”, opowieść i tekst „ruszają się w węzłach,
  stoją na puencie” (u nas świadomy wyjątek z powodem: `html_wideo.py pomiar --wyjatek`).

**30. Recenzja sprawdza logikę i znaczenie liczb, nie tylko obraz.**
- Dowód: w G3 recenzja złapała trzy błędy przy idealnym obrazie: „neuron wyjściowy połączony z warstwą ukrytą,
  a nie z pikselami”, „»wzrosło o 9 razy« powinno brzmieć »wzrosło do 9-krotności«”, „koniec linii miesięcznej ¥268
  nie zgadza się z końcem świec dziennych ¥286.40”.
- Kiedy: każdy film z danymi. Wykres finansowy: oś bez mylącego ucięcia (ucięcie podpisane „oś pionowa nie zaczyna
  się od 0”), jednostki, źródło, znacznik danych przykładowych; u nas liczby z `fakty.json`
  (`html_wideo.py pomiar --fakty`).

**31. Jeden kadr, jeden punkt skupienia: najpierw struktura, potem dane, na końcu oznacz jedną rzecz.**
- Dowód: 3 gramatyki doszły do tego niezależnie: kinetic („słowo główne wpada, reszta wyjeżdża z maski”), finanse
  („najpierw osie, potem dane, na końcu oznacz jedną rzecz”), 3b1b („jeden kolor = jedno pojęcie, przemiana zamienia
  poprzednie pojęcie w następne, prawie bez cięć”).
- Kiedy: każdy kadr z informacją.

## VIII. Postacie

**32. Ludzi maluje model, kod tylko składa; dzielisz pracę według tego, kto co robi lepiej.**
- Dowód: w porównaniu trzech kierunków na tej samej klatce postać chibi rysowana kodem wypadła najgorzej, a klatki
  z biblioteki (G2) i klatki AI przemalowane w stylu filmu dobrze; postać to też najczęstsza słabość 36 stylów.
- Dlaczego: kod jest dobry w regularności (pole pociągnięć, geometria, kamera, czas, fizyka, deterministyczność),
  model w tym, żeby twarz i sylwetka człowieka były „właściwe”.
- Kiedy: `postacie.md`; dla każdej warstwy najpierw pytanie, kto namaluje ją najlepiej, potem wybór narzędzia.

## IX. Potok z lektorem

**33. Klip renderuj w liczbie klatek gotowego filmu, okno bierz z osi gotowego filmu.**
- Dowód: między dwoma podmienianymi fragmentami był wycięty w zgrubnym montażu postój 3,65 s, a montaż był
  przyspieszony; render tego jako jednego ciągłego fragmentu osi gotowego filmu (119 klatek) dał ujęcie z `rate = 1.0`
  i 119 klatek = 119 klatek ujęcia, przerenderowany został tylko 1 rozdział (30–57 s) z 8, a klatki w ruchu (28/29,
  127/137) mają przesunięcie 0.
- Dlaczego: reżyseria potoku liczy w sekundach oryginału, gotowy film w sekundach gotowego filmu, a animacja żyje
  tylko w gotowym filmie; okno z osi gotowego filmu omija trzy przeliczenia (tempo, cięcia, „koniec fragmentu =
  początek następnego”).
- Kiedy: każda animacja wstawiana w film z lektorem. U nas oś to `os_czasu.json` (`film.py narracja`), klip robi
  `gramatyka.py` (szablon → `sprawdz` → `render`), synchronizację sprawdzasz klatka po klatce.

**34. Cue pisze „które słowo”, nie „która sekunda”; na klatki przelicza skrypt przed renderem.**
- Dowód: 5 cue (słupek rośnie, etykieta wyskakuje, wycinek się odsłania, dwa zakreślenia) trafia w początek słowa
  z błędem −0,48 do +0,09 klatki, całym z zaokrąglenia do klatek; gdy zmienił się lektor i długość okna, render
  odmówił, zamiast cicho się rozjechać.
- Dlaczego: sekunda to liczba przepisana z listy słów (każde przepisanie to szansa na błąd), a słowo to prawdziwy
  zamiar reżysera.
- Kiedy: każdy cue pod lektora. U nas `{"slowo": "7.8", "kind": "highlight"}` (`gramatyka.py` liczy `at` z osi
  lektora); to samo słowo kilka razy: `nth`; wcześniej niż słowo: `offset`.

**35. Pion z prawdziwym zrzutem: dwa zakreślenia, po jednym na półzdanie, które czyta lektor.**
- Dowód: ramka na cały akapit (szerokość 0,93) nie mieściła czerwonego kółka, kamera nie mogła się zbliżyć, a tekst
  miał ok. 20 px wysokości (na telefonie nieczytelny); dwie ramki na dwa półzdania, każda na słowie kluczowym, dały
  zbliżenie 2,4× i tekst ok. 50 px; gdy druga ramka jest poza kadrem, kamera najpierw do niej jedzie, potem odsłania.
- Dlaczego: w pionie wąskim gardłem jest szerokość, więc punktem skupienia może być tylko półzdanie; Vox to gramatyka
  „spójrz na to zdanie”, więc zakreślanie zdanie po zdaniu za lektorem pasuje do niej.
- Kiedy: zrzut przycinasz z klatki bez zmian (zachowaj kopię klatki źródłowej), prostokąt najpierw sprawdzasz na
  stopklatce (`gramatyka.py render … --klatki`); ocena na oko myli się zwykle o 20–30%.

**36. Gramatyka z tekstem ustępuje pasowi napisów, a nie napisy animacji.**
- Dowód: w pionie etykieta wykresu t3 wypadała na y≈1460, na wypalonych napisach (1400–1520 w ich filmie; u nas pas napisów to 1220–1440,
  `safe.bottom` 700); z `safe` wykres leży w 300–1430 (ich wartości), w tym samym obszarze co inne materiały, zero zasłonięć w próbkach klatek; po uwadze recenzji, że biel na
  cały ekran między ciemnymi zrzutami to największy skok jasności, `safe.fill` = kolor tła filmu i wykres stał się
  kartą w tym samym miejscu i na tym samym tle co zrzuty obok.
- Dlaczego: napisy wypala eksport jednolicie, przesuwanie ich dla jednego fragmentu rusza cały łańcuch eksportu;
  animacja jest sparametryzowana, więc przesunąć ją najtaniej.
- Kiedy: każdy klip z tekstem w filmie z napisami: w spec `safe` (w źródle wylicza go szkic potoku z pliku napisów
  i ramki materiału).

## X. Od filmu pokazowego do klipu wielokrotnego użytku

**37. Dobry film pokazowy ≠ dobry klip po sparametryzowaniu; parametryzację recenzuj osobno.**
- Dowód: 8 filmów pokazowych gramatyk przeszło recenzję, a po przerobieniu na klipy ze spec tylko 3 nadawały się
  wprost: prawdziwe dane odsłoniły złe zaokrąglenie skali, zgubione etykiety kategorii i wielką liczbę na linii;
  parametr ustąpienia napisom ignorowało 6/8; karta z tekstem odjeżdżała przed końcem pisania; na tablicy ostatnia
  klatka pisaka zasłaniała „nie” i odwracała sens.
- Kiedy: każdy klip sterowany spec. Recenzję rób na innych danych: ujemne, ułamki, długi tytuł, pion, brak zrzutu,
  przezroczyste tło, bardzo długi tekst; co najmniej jeden „nieprzyjazny” spec na każdy przypadek; materiały
  przykładowe do odbioru też czyste (nie zrzut spisu treści). U nas `gramatyka.py sprawdz` i `render --klatki`.

## XI. Klip animacji w filmie z lektorem

**38. Odcinek animacji renderujesz w długości gotowego filmu i z czasami słów; kluczowe klatki na słowach
kluczowych.**
- Dowód: w kopii pionowego filmu z lektorem dwa fragmenty jednego rozdziału zastąpiono animacją (t3 wykres
  finansowy z porównaniem liczb, y2 Vox z oficjalnym zrzutem); liczba klatek równa ujęciom, 7 słów kluczowych
  z błędem −0,48 do +0,09 klatki.
- Dlaczego: animacja wchodzi tylko tam, gdzie nagranie ekranu nie wyjaśni (porównanie liczb, oficjalne zdanie),
  przed i po zostaje człowiek i nagranie; zdarzenie odsłania się, gdy lektor dochodzi do słowa, jakby pokazywał
  palcem.
- Kiedy: fragment → długość i czasy słów z osi gotowego filmu → spec → render → zamrożenie i wstawienie; liczby
  tylko z tabeli źródeł, źródło na obrazie (u nas `fakty.json`).

**39. Nie dodawaj gagów narracyjnych, o które właściciel nie prosił.**
- Dowód (doświadczenie): ozdoby dokładane postaci jedna po drugiej zabierają uwagę scenie; gag najpierw sprawdza
  się na próbce.
- Kiedy: uwaga recenzji „czegoś brakuje” to informacja dla właściciela, nie zgoda na dokładanie. Gag strukturalny
  najpierw pokaż na próbce albo w opisie kierunku i czekaj na zgodę; bez właściciela zapisz go w RAPORT.md jako
  propozycję.

**40. Jedna narracja: gramatykę dobierasz do zadania objaśnienia.**
- Zasada: prawdziwe posty i dokumenty pokazuje biurko materiałów Vox (prowadzenie linią, zakreślenie); reguły,
  zmienne kontrolne i relację dźwięku z obrazem ciągła przemiana obiektów 3b1b. Najpierw blokujesz dźwięk, napisy
  i oś czasu, potem wymieniasz obraz.
- Dowód: 467,8 s lektora i 270 napisów jednego filmu przeszło bez zmian przez całkowitą przebudowę stylu, a surowe
  pakiety AAC obu wersji MP4 mają ten sam hash co zablokowany miks (danych o retencji po publikacji jeszcze nie ma).
- Dlaczego: obraz wykonuje czynność objaśnienia danego fragmentu, a materiał służy czytelności; gramatyka dopuszcza
  bezruch po odczycie albo wyprowadzeniu, nie trzeba drobnego ruchu tła dla samej liczby ruchu.
- Kiedy: filmy z lektorem, w których prawdziwy materiał przeplata się z objaśnieniem mechanizmu.

## XII. Długi zwój

**41. Jeden plik szkieletu + odcinki równolegle: 24 światy od 4 grup sklejone za pierwszym razem.**
- Dowód: `lib/world.js` definiuje tylko interfejs odcinka (szerokość, linia gruntu, klatki marszu, interakcja
  `at`/`dur`/`frame`, `back`/`front`/`seam`), marsz, bohatera przyciętego na granicy i znacznik; 4 grupy po 6
  odcinków po ułożeniu chronologicznym dały 123,7 s za pierwszym razem, deterministyczność zaliczona, 0 skoków, a recenzja
  23 granic (wysokość gruntu, ciągłość bohatera) nie miała uwag. Klucz: wspólne stałe (grunt 760, wzrost 300,
  prędkość) wpisane w szkielet.
- Kiedy: długi film: najpierw szkielet i interfejs, potem podział pracy; wszystkie zdarzenia od początku interakcji
  (`WORLD.actT`, `item.atAct`), nie „sekunda X od wejścia w odcinek”. Prędkość marszu podniesiono potem z 330 na
  560 i żaden odcinek nie wymagał zmiany czasu (`dlugi-zwoj.md`).

**42. Tempo stroisz per odcinek, aż granice muzyki wypadną na pierwszą miarę taktu.**
- Dowód: przy 24 stałych granicach jedno BPM w najlepszym razie myli się o 112 ms; cała liczba bitów na odcinek
  i tempo 86–104 BPM per odcinek dały wszystkie 24 granice na pierwszej mierze, błąd największy 11,7 ms, średni 3 ms.
- Kiedy: obraz najpierw, muzyka potem; nie wymuszaj jednego tempa. Ucho nie słyszy ±8% różnicy tempa między
  odcinkami, a słyszy zmianę instrumentu poza mocną miarą (`rytm.md`).

**43. Kamera tylko do przodu.**
- Dowód: v1 przy interakcji odsuwała kamerę do przodu i na końcu ją cofała: w 17 z 24 odcinków „przewijanie wstecz”
  o 68–256 px, którego qa nie mierzył, a recenzja widziała od razu; po zmianie na „cel = maksimum dotychczasowych
  wartości + wygładzenie Gaussem” 0 cofnięć, zatrzymanie i ruszenie bez szarpnięcia.
- Kiedy: poziomy zwój z kamerą za bohaterem: funkcja pozycji kamery monotoniczna; dobrze dodać do kontroli liczbę
  cofnięć kamery.

## XIII. Cały film z lektorem i powrót doświadczeń

Te zasady źródło podaje bez liczb (liczby są w 33–38), więc mają postać „zasada → kiedy”.

**44. Od lektora do obrazu: najpierw skrypt, lektor i czasy słów, potem tabela stylów i lista akcentów.**
- Zasada: ruchy przypinasz do słów kluczowych (jak `TM.cue` w kodzie wzorcowym), nie wpisujesz czasów na sztywno.
  Kamera idzie za ramką treści; pas napisów to ograniczenie w przestrzeni kamery i przy zbliżeniu też trzeba go
  ominąć.
- Kiedy: każdy film z lektorem (u nas cue ze `slowo`, oś z `film.py narracja`).

**45. Tablica: jedno duże płótno, które się zapełnia.**
- Zasada: pierwsza kreska bloku zaczyna się razem z dojazdem kamery, w bloku piszesz w tempie mowy. Po
  `const B = DG.board(...)` prostokąty rysuj przez `B.line(points, {smooth:false})`, bo wygładzony splajn nadyma
  prostokąt w elipsę. Czas czytania pełnej listy liczysz od chwili, gdy ostatni punkt jest gotowy; czas rysowania to
  nie czas na czytanie.
- Kiedy: gramatyka `tablica` i każda lista rysowana na ekranie.

**46. Najpierw konstrukcja kadru, potem faktura.**
- Zasada: kolaż Vox: najpierw obiekty, relacje i kamera, dopiero potem faktura papieru i ozdoby. Film
  z prowadzącym: najpierw różne układy i plany; jednostajnego scenopisu nie naprawi potem przesuwanie postaci.
- Kiedy: gramatyki `vox` i `prowadzacy`, każdy film z wieloma ujęciami.

**47. Kontrola mierzy, oko rozstrzyga.**
- Zasada: kontrola daje deterministyczność, wydajność, ruch, płynność i wskazówki kadrowania tekstu (tekst ucięty,
  nakładanie się napisów, pas napisów, prawie pusty kadr); duże ozdobne litery mogą dać fałszywy alarm, więc
  oglądasz wskazaną klatkę. Jasne tło: osobne sprawdzenie, czy grafika wchodzi w pas napisów (w źródle
  `subzone_gate.py`, próg ciemnych pikseli; na tle z fakturą nie działa).
- Kiedy: przed oddaniem. U nas `html_wideo.py pomiar` (tekst poza kadrem, strefy platformy, kontrast, napisy na sobie, tekst w pasie
  napisów lektora `--napisy`; grafika bez tekstu w pasie: oko na arkuszu) i arkusz
  `qa_wideo.py --arkusz`.

**48. Niezależna recenzja z dziennikiem problemów.**
- Zasada: przed oddaniem film ogląda wykonawca, który go nie robił; długi film co najmniej dwóch. Każdy problem
  zapisujesz z kodem czasu, przyczyną, zmianą i ponownym sprawdzeniem; powrót starego problemu osobno od nowego.
  Odbiór według konkretnych problemów, nie pogoń za łączną oceną. Trzy rundy z rzędu ten sam typ problemu i dwie
  różne poprawki nie działają: wracasz do materiału albo możliwości silnika; problem ze skryptu wraca do skryptu.
- Kiedy: każdy film z wielu odcinków i każdy dłuższy film (u nas `kontrola-wideo`).

**49. Zamrożenie po wyborze właściciela.**
- Zasada: gdy właściciel wybrał wersję, zamrażasz razem kod, oś czasu, miks i napisy. Kandydaci i wersja zamrożona
  zostają w projekcie; bez potwierdzenia nic nie nadpisujesz.
- Kiedy: każda wersja zaakceptowana przez właściciela.

**50. Doświadczenie wraca do skillu.**
- Zasada: każda runda zapisuje zjawisko → przyczynę → poprawkę → sprawdzenie → miejsce docelowe. Problem jednego
  stylu idzie do karty stylu albo gramatyki, metoda wspólna dla stylów do `metoda.md`, postacie do `postacie.md`, to,
  co da się zmierzyć maszyną, do kontroli. Pułapka, która wraca, staje się punktem sprawdzenia przed startem; gdy
  silnik dostanie odpowiednią zdolność, regułę tekstową usuwasz. Po zmianie niezależny wykonawca ją sprawdza, a wpis
  trafia do CHANGELOG.
- Kiedy: po każdym filmie. Prywatne uwagi z projektu, opisy wyglądu konkretnych osób i niepublikowane materiały
  zostają w projekcie; skill dostaje tylko metodę i niezbędne dowody.
