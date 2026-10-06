# Kolaż Vox (`vox`, w kodzie `y2_vox`)

Argument leży na biurku z prawdziwymi materiałami (wycinki, zdjęcia, dokumenty, zrzuty ekranu), kamera jeździ po nim jak oko dziennikarza śledczego, a linie i zakreślacz rysują się skokowo; wiarygodność bierze się z tego, że te rzeczy naprawdę tu położono. Wzór: `python3 $HERMES_HOME/scripts/gramatyka.py wzor vox --arkusz out/wideo/wzor-vox.jpg`; start: `python3 $HERMES_HOME/scripts/gramatyka.py szablon vox [--format 9:16] -o out/wideo/src/klip-vox/spec.json`.

Kod: klip `$HUASHU/scripts/engine/clips/y2_vox.js`, przykład `$HUASHU/scripts/engine/examples/y2_vox.json` (tytuł, dwa zrzuty wykresów z `examples/assets/`, `highlight` z najazdem, fiszka), film pokazowy `$HUASHU/scripts/engine/demos/y2_vox/` (MIT). Film pokazowy ma 8 s, 3 ujęcia i 2 przejścia (ok. 2,5–3 razy gęściej niż prawdziwy film): bierz technikę, nie tempo. Jego fakty to prawdziwe liczby z pracy Google o rozpoznawaniu kotów z 2012 r. (arXiv:1112.6209 i blog Google).
Potok: `szablon` → polskie teksty, prawdziwe zrzuty i `slowo` → `gramatyka.py sprawdz` → `gramatyka.py render … --klatki 0.5,2,4` (sprawdź `rect`) → pełny `render`.

## Kiedy
- Prawdziwe archiwa, wiadomości, historia, mapy, ludzie: „jak do tego doszło”, „kto, kiedy i co powiedział”.
- Narracja dziennikarska: cytat, dowód, przyczyna i skutek. Gdy lektor mówi „spójrz na to zdanie”, „zwróć uwagę na tę liczbę”, obraz zakreśla to miejsce.
- Cytat, liczba albo rok, przy których widz ma zobaczyć źródło na własne oczy.
- Przykłady: analiza podwyżki cen ze zrzutami pism i cenników (segment 30–60 s), historia firmy na archiwalnych zdjęciach, przegląd zmian regulaminu ze zrzutami stron, materiał śledczy na YouTube 16:9, rolka 9:16 „trzy ślady, że…”.

## Nie do
- Czysty mechanizm albo pojęcie bez prawdziwych materiałów: wyjdzie „fałszywe archiwum”. Użyj `kurzgesagt` (albo `3b1b`, gdy są wzory).
- Wyprowadzenia i kroki: `tablica`.
- Dużo gry postaci: wycinanki ruszają się tylko skokowo. Użyj `historyjka`.
- Czysty samouczek produktu na zrzutach: `prezentacja` (czysto). `vox` bierz, gdy zrzut ma być dowodem.

## Gramatyka (z pomiarów)
Źródła: 5 filmów (Missing Chapter 2022, film o psychodelicznych plakatach 2019, Vox Borders 2018, Johnny Harris 2026, film aktorski Vox 2026 dla porównania); 13 ruchów kamery dopasowanych do krzywych, kolory pobrane z kadrów.

- **Długość ujęć (kolaż).** Dwa tempa. Wolne (Missing Chapter): mediana 3,3 s, ok. 12 cięć/min, jedna karta stoi 3–7 s i trzyma ją rysowanie linii i zakreślanie na karcie. Szybkie (plakaty 1,8 s, Johnny Harris 1,4 s): ok. 25–33 cięć/min, obrazy prawie stoją, rytm robią cięcia.
- **Dwa klatkaże – rdzeń stylu.** Kamera jedzie płynnie (w oryginałach 24 fps; w klipie liczona w każdej klatce). Elementy na biurku (wsuwanie, wzrost plam na mapie, rysowanie czerwonej nici, pisanie, ręczne kółka) idą skokowo 12 fps, „na dwójkach”: `MO.step(t − at, 12)`. W filmie o plakatach 52% klatek z ruchem ma odcisk „ruch – stop – ruch”. Pary identycznych klatek z tego skoku to styl, nie zacięcie (wzór: 16,9% przed dodaniem najazdu na otwarcie, 3,1% po).
- **Krzywe kamery (13 ruchów).** Czas: mediana 1,29 s, zakres 0,71–1,96 s, żaden nie jest liniowy. 7 symetrycznych easeInOutSine (`MO.sineInOut`, domyślne Easy Ease w AE) do długich przejazdów „do następnej karty”. 6 z szybkim startem i długim ogonem ≈ cubic-bezier(.33,0,.2,1) (`MO.longTail`) do „odsłonięcia przez oddalenie” i „jazdy wzdłuż tropu”.
- **Kamera w klipie.** Do każdego nowego materiału rusza ok. 0,95 s przed jego `at` i ląduje w `at − 0.05` (`MO.longTail`), z krótkim rozmyciem ruchu wzdłuż prędkości (`CAM.motionBlur`, 7 kopii, współczynnik 0,6). Nie odjeżdża od karty tekstowej, zanim tekst się nie wpisze i nie postoi 0,5 s (najpóźniej rusza w `at − 0.4` następnego cue). Najazd `highlight`: `MO.sineInOut`, 1,0 s. Po ostatnim ruchu powolny najazd 1%/s.
- **Wejścia (pomiar).** Zdjęcia archiwalne i wycinki są w kadrze od cięcia, bez wyskoku i opadania. Tylko przy jeździe po osi czasu następna karta wsuwa się spoza kadru z przechyłem 5–15° i prostuje, ok. 0,8 s. W klipie każdy materiał i karta: `CL.slideIn` 0,55 s z przechyłem (`tilt: 0.2`), skokowo 12 fps.
- **Linie i pisaki (pomiar).** Czerwone podkreślenie 0,5–1 s. Czerwona elipsa ok. 1 s, jedno pociągnięcie, końce niedomknięte, lekko się krzyżują. Zakreślacz jednej linii 1,5–3 s, w tempie czytanych słów. Pisanie ok. 13 znaków/s na dwójkach. W klipie: zakreślacz 0,6 s, czerwone kółko od +0,5 s przez 0,6 s (cubicOut), pisanie 13 znaków/s (do 40, gdy następny cue jest blisko), czerwona nić rysuje się 0,7 s i rusza 0,9 s przed następnym materiałem; we wzorze nić 0,5 s na odcinek, odstęp 0,15 s, licznik 1,4 s cubicOut do 10 000 000.
- **Powolny dryf w spoczynku.** Opcjonalny. Gdy na karcie coś się dzieje, kamera stoi. Dopiero statyczny obraz trzymany ≥3 s dostaje dryf 0,5–1%/s.
- **Przejścia.**
  1. Twarde cięcie (`cut`): zdecydowana większość, na znakach przestankowych narracji.
  2. Jazda wzdłuż czerwonej nici (śledzenie osi czasu): 1,3–1,8 s, długi ogon; następna karta wsuwa się ukosem z prawej i prostuje. We wzorze `same` (to samo biurko, ruch robi kamera), 1,1 s, rozmycie ruchu 7 kopii, 0,6.
  3. Najazd w papier albo zdjęcie → twarde cięcie na skan tego samego obrazu w wysokiej rozdzielczości: 1,0–1,4 s, krzywa S. We wzorze logarytmiczny najazd do z ≈ 9,6 i `cut` w klatce pełnego wypełnienia.
  4. Oddalenie od jednego zdjęcia, które odsłania cały kolaż: ok. 1,0 s, szybki start, długi ogon.
  5. Rosnące plamy koloru na mapie i rysowanie trasy: 2,5–3,5 s, na dwójkach, na czubku linii pełna czerwona kropka.
  6. Prawdziwa ręka przewraca kartkę albo wyciąga papier (znak Missing Chapter); w kodzie: papier wsuwa się po łuku ze zmiennym cieniem.
  Przejście „darty papier” nie wystąpiło ani razu w 5 filmach. To chwyt stron z szablonami, nie gramatyka Vox.
- **Paleta (pomiar, Missing Chapter).** Prawie czarne tło `#171716`; papierowa biel `#E0DCDA`–`#EEEDED`; jedna czerwień w dwóch tonach: jasna `#B65255` do linii, ciemna `#93403C` do wypełnień; zakreślacz `#DACF08` (ciemniejszy i bardziej oliwkowy niż żółć logo `#FFF200`, która rzadko pojawia się na dużej powierzchni); stary papier mapy `#E4DCCF`, pergamin `#CFB195`. Nie ma czystej bieli ani czystej czerni. W klipie: biurko `#e4ddcf`, tusz `#171716`, czerwień `#b8433f` (trochę jaśniejsza niż pomiar, żeby była czytelna w 1080p), papier `#eeedeb`, fiszka `#f6f4ee`; we wzorze zakreślacz `rgba(218,207,8,.9)` w trybie multiply, czarna karta `#1b1b1a`.
- **Materiały.** Zdjęcia w szarym rastrze 45° z białą ramką i dwoma półprzezroczystymi taśmami. Wycinki z poszarpaną krawędzią, pożółkłe, tytuł szeryfowy. Etykiety jak w Vox Borders: czarny pasek, biały gruby tekst. Fiszki w linie. Faktura papieru jest **statyczna** (różnica klatek w postoju 0,0–0,1); ziarno zmieniane co klatkę to styl filmowy Johnny’ego Harrisa z 2026 r., nie Vox. W klipie zrzut zachowuje kolory, raster tylko z `data.halftone: true`; na wierzch idzie warstwa starego papieru `rgba(214,205,185,.18)` (multiply) i winieta.
- **Cienie słabe.** W 360p cień karty na czarnym tle prawie niewidoczny. Wzór: rozmycie 10, przesunięcie (3, 6), krycie 0,28; klip: obrazy rozmycie 12, przesunięcie (3, 7), karty rozmycie 10, przesunięcie (3, 6).
- **Celowa niedoskonałość.** Dyrektor artystyczny Vox: nie ma wyglądać idealnie, bo wtedy wygląda jak reklama, a nie materiał redakcyjny.
- **Tekst.** Imiona i miejsca: mały biały krój szeryfowy pod zdjęciem. Czarny tytuł osi czasu wpisywany 13 znaków/s z czerwoną linią przez cały kadr. Cytat wyłania się jak rozlewający się atrament pisma ręcznego (ok. 2 s), potem czerwony pasek czyta go linijka po linijce.
- **Kroje.** Klip: `title` `PuHui-Heavy` 64 px, fiszka `PuHui-Bold` 48 px, etykieta pod obrazem `PuHui-Bold` 34 px. W Jarvie nakładka `huashu_pl.js` podmienia je na Inter tej samej grubości (800 i 700). Wzór używał systemowego Songti SC i Anton; klip już ich nie potrzebuje.
- **Zgranie z narracją.** Zakreślacz, pisanie i rysowanie linii idą w tempie czytanych słów, nie w rytmie muzyki. Johnny Harris: każde słowo ma odpowiadać ruchowi albo akcji w animacji; scenariusz pisze w dwóch kolumnach. Joss Fong zmienia muzykę co ok. 20 s.
- **Pomiar wzoru (qa).** Skoki obrazu tylko w zaprojektowanych ruchach kamery: ujęcie 2 (0,6 s najazdu do 9,6×) i ujęcie 3 (0,85 s oddalenia po cięciu). Ujęcie 3 kosztuje 73/89 ms na klatkę (śr./szczyt), bo naklejka postaci robi 16 przesunięć białej obwódki co klatkę: obwódkę licz raz i trzymaj w pamięci podręcznej.

## Cue w spec
`data` całego spec: brak. Każdy cue ma `at` (s, klatka, w której element pierwszy raz widać) albo nasze `slowo` (+ `nth`, `offset`). `kind` spoza tabeli nie daje błędu i nic nie rysuje (tu nie ma `number`, `dur` nie jest czytane). Cue z `at` > `duration` jest odrzucany z ostrzeżeniem. Materiały i karty (`image`, `title`, `point`) leżą w kolejności `at`: w poziomie od lewej do prawej, w pionie z góry na dół, połączone czerwoną nicią.

| kind | pola | co robi | przykład |
|---|---|---|---|
| `image` / `clip` (to samo) | `image` (ścieżka względem spec), `text` (czarna etykieta pod obrazem; za długa → mniejszy krój, 1 linia), `data.halftone: true` (szary raster 45°; domyślnie oryginalne kolory) | Od `at` wsuwa się na biurko, proporcjonalnie i bez kadrowania, z białą ramką papieru i dwiema taśmami. Brak pliku → render odmówiony. | `{"at":1,"kind":"image","image":"zrzut.png","text":"Strona główna"}` |
| `title` | `text` (pusty albo same spacje → ostrzeżenie i pominięcie) | Czarny pasek z białym tekstem (Borders), wpisywany 13 znaków/s; gdy następny cue jest blisko, przyspiesza do 40 znaków/s. | `{"at":0,"kind":"title","text":"Trzy ślady tej podwyżki"}` |
| `point` | `text` (pusty → jak wyżej) | Fiszka w linie, tekst wpisywany jak w `title`. | `{"at":4,"kind":"point","text":"Cennik zmienił się dzień przed ogłoszeniem"}` |
| `highlight` | `data.rect=[x,y,w,h]` (0..1 względem **bieżącego obrazu**, czyli ostatniego `image` z `at` ≤ `at` tego cue) | Zakreślacz (0,6 s, 12 fps, multiply) → ręczne czerwone kółko (od +0,5 s) → najazd kamery na ten fragment (najwyżej 2,6 razy bliżej niż dotąd, kółko zostaje w kadrze). Gdy początek ramki jest poza kadrem, kamera najpierw tam jedzie i staje klatkę przed `at`. Następne kółko na tym samym obrazie przygasza poprzednie do 25%. Ramka szersza niż pół obrazu → bez najazdu bliżej niż na szerokość obrazu. Na kartach tekstowych nie działa; gdy po obrazie przyszła już karta, zakreślenie rysuje się na obrazie, ale kamera do niego nie wraca. | `{"at":2.5,"kind":"highlight","data":{"rect":[0.1,0.2,0.3,0.1]}}` |

## Minimalny spec (po polsku)
Bez zrzutów też działa: tytuł i fiszki. Ostatni cue jest przypięty do słowa „cennik” w narracji: `gramatyka.py` liczy jego `at` z `os_czasu.json` (`film.py narracja`); `nth` (od 1) wybiera wystąpienie, `offset` przesuwa w sekundach.

```json
{"grammar":"y2_vox","duration":8,"cues":[
  {"at":0,"kind":"title","text":"Trzy ślady podwyżki"},
  {"at":2.6,"kind":"point","text":"Najpierw pismo od dostawcy"},
  {"slowo":"cennik","kind":"point","text":"Po dwóch tygodniach nowy cennik"}]}
```

## Pułapki
- **Wszystko płynnie w 60 fps** wygląda jak firmowa reklama; wszystko w 12 fps przyprawia kamerę o zawrót głowy. Kamera płynna, elementy skokowe. W scenie pisanej samodzielnie skok licz od `at` (`MO.step(t − at, 12)`), nie z bezwzględnej siatki 12 fps: inaczej element pokazuje się do jednego kroku za wcześnie (przy 30 fps 2 klatki).
- **Chwyty z szablonów:** darty papier, wyskok każdego zdjęcia, faktura drgająca co klatkę. W pomiarach ich nie ma; zdjęcia są w kadrze od cięcia, papier stoi, przejścia to głównie cięcia i najazdy. Im więcej efektownych wejść, tym mniej „redakcyjnie”.
- **Żółć logo Vox jako duże tło i za dużo kolorów.** Żółty to zakreślacz w tonie `#DACF08`, tylko do podkreśleń. Podstawa: czerń, papierowa biel, jedna czerwień i najwyżej jeden akcent.
- **`rect` na oko myli się o 20–30%.** Najpierw stopklatki (`gramatyka.py render … --klatki`), potem poprawka.
- **Pion: zakreślaj półzdanie, które lektor właśnie czyta.** Zrzut na biurku w pionie ma ok. 900 px szerokości; tekst strony 16 px trzeba przybliżyć 2–2,5 razy, żeby był czytelny. Ramka na prawie całą szerokość nie zmieści kółka i kamera nie najedzie. Zdanie na dwie linie rozbij na dwa `highlight`, każdy na jedno słowo kluczowe (pomiar: najazd 2,4×, wysokość liter ok. 50 px).
- **Polskie karty są dłuższe.** Żeby pisanie zostało przy 13 znakach/s, odstęp do następnego cue ma wynosić co najmniej liczba znaków / 13 + 1,45 s; krótszy odstęp przyspiesza pisanie (najwyżej 40 znaków/s). Gęste cue każą też kamerze ruszać, zanim dojedzie.
- **Prawdziwe materiały zostają prawdziwe.** Zrzuty proporcjonalnie, bez ucinania kluczowego UI; nie podrabiaj archiwum, którego nie ma.
- **Tryb `--alfa`** usuwa tylko biurko; cienie kart zostają, karty czytają się jak „unoszące się nad obrazem”.
- **Napisy wypalane.** Pod napisy ustaw `safe.bottom` (pion 1080×1920: 700, poziom: 250); klip przesuwa środek obrazu i liczy powiększenie tylko w pasie między `safe.top` a H − `safe.bottom`.

## Kontrola
- Czy kamera jedzie płynnie, a elementy na biurku skokowo w 12 fps, licząc od `at`?
- Czy każdy materiał jest prawdziwy, ma podpis albo źródło, proporcje są zachowane, a kluczowe UI nie jest ucięte?
- Czy zakreślacz i kółko trafiają w tekst (stopklatka) i padają na słowo, które czyta lektor?
- Czy paleta to papier, czerń, jedna czerwień, a żółty tylko jako zakreślacz?
- Czy w pionie kółko mieści się w kadrze, a litery po najeździe mają ok. 50 px wysokości?
