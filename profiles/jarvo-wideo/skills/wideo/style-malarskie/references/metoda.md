# Metoda: żywy obraz w stylu malarskim, z kodu

Jak zbudować scenę, która jest „żywym obrazem” w danym stylu, i jak złożyć z takich scen film (przegląd stylów,
przemiana jednego miejsca, podróż przez epoki). Źródło: repo huashu-art-motion (MIT). Kod biblioteki:
`@@PY@@ "$HERMES_HOME/scripts/narzedzia.py" instaluj huashu`; katalog biblioteki
`$HUASHU` = `@@TOOLS_DIR@@/huashu-art-motion` (pliki czytasz wprost), silnik w `$HUASHU/scripts/engine/`.
Postacie: `postacie.md`. Długi zwój (bohater idzie przez obrazy): `dlugi-zwoj.md`. Rytm i muzyka: `rytm.md`.
Sprawdzone zasady z dowodami: `zasady-huashu.md`.

Wzorem metody jest 15-sekundowy film „Art History Speedrun” (Tak, @cherry_mx_reds) i jego replika w bibliotece:
16 epok w jednym pokoju z oknem, stołem, kotem i dziewczyną. Bierzesz mechanizm, nie scenę.

## 1. Pięć warstw mechanizmu (dlaczego to działa)

Ten sam układ pięciu warstw działa przy każdym temacie: historia technologii, przemiana miasta, życie jednej osoby
od 18 do 80 lat.

1. **Stały szkielet sceny.** 16 epok, a okno, stół, kot, postać i tabliczka z rokiem stoją prawie w tym samym
   miejscu (±40 px). Oko ma kotwicę, więc widzi, że zmienia się styl. Stałe pozycje pozwalają też zaczynać przejście
   od przedmiotu w kadrze (mozaika rozlewa się od kota, krąg światła rozwija się od filiżanki).
   Rób tak: najpierw ustal współrzędne kompozycji wzorcowej i wyrównaj do nich wszystkie epoki. W kodzie to jedna
   stała, nie osobny rysunek w każdym odcinku.
2. **Każda epoka to żywy obraz.** Postój trwa 0,25–1,4 s, ale obraz cały czas się rusza: bohater wykonuje jeden
   ciągły ruch (podnosi filiżankę i pije) i do tego 2–4 małe pętle **wzięte z motywów wizualnych tej epoki**.
   Zwierzęta z malowidła naskalnego biegną na „dwóch pozach na zmianę” (wiele nóg z malowideł, zamienione w animację),
   egipski skarabeusz toczy słońce, grecki meander się przewija, rzymski wulkan dymi, gotyckie złoto błyszczy, nad
   renesansem leci maszyna latająca, w ukiyo-e przetacza się wielka fala, u Van Gogha kręci się gwiaździste niebo,
   w Bauhausie obraca się wskazówka, w pop-arcie cztery pola zmieniają kolor.
   Rób tak: dla każdego odcinka wypisz 3 najbardziej rozpoznawalne elementy formalne epoki i każ im się ruszać.
   Ruch ma być widoczny w oknie postoju (krótki odcinek = szybki rytm ruchu).
3. **Przejście = język-podpis następnej epoki.** Do Egiptu wchodzi się przez spadające bloki kamienia albo gobelin,
   do Grecji przez obrót wazy jak walca, do Rzymu przez odwracające się kostki mozaiki, do gotyku przez odwrócenie
   karty pergaminu, do renesansu przez boskie światło, do ukiyo-e przez falę z Kanagawy, do impresjonizmu przez
   plamki koloru, które pokrywają kadr, do Van Gogha przez wir gwiaździstego nieba, do secesji przez rosnące formy
   organiczne ze złotym brzegiem, do kubizmu przez geometryczne odłamki, do Bauhausu przez obrót i powiększenie figur
   w czerwieni, żółci i błękicie, do pop-artu przez błyskawicę i raster, do 8-bit przez pikselizację, do ray tracingu
   przez zieloną siatkę i renderowanie linia po linii, do 2026 przez trzy kolorowe koncentryczne pierścienie.
   Rób tak: nie bierz przejścia z ogólnej biblioteki przejść. Wyhoduj je z najbardziej rozpoznawalnego elementu
   formalnego nowego stylu. W pierwszej klatce każdego przejścia daj uderzenie kamery: warstwa sceny powiększona do
   `1.03` wraca do `1.0` w ok. 20 klatek (tabliczka roku się nie skaluje). Z tego bierze się „szarpnięcie” na bicie.
   W silniku: `transition.punch` albo `window.PUNCH` (domyślnie 0.03; film objaśniający, prezentacja, dane:
   `window.PUNCH = 0`).
4. **Przyspieszenie siatką bitów.** Tempo stałe, 128 BPM, a liczba ósemek na odcinek maleje: 6 → 4×5 → 3×4 → 2×3 →
   1×3 → koniec wydłużony do 9 i więcej. Tempo się nie zmienia, a słychać i widać coraz większy pośpiech; ostatni
   odcinek jest dłuższy, żeby zrobić miejsce na puentę. Przejścia skracają się razem z odcinkami (0,4 s → 0,13 s),
   przewijanie roku też (0,55 s → 0,07 s).
   Rób tak: wypisz docelowe długości odcinków, zaokrąglij do ósemek, potem wyrównaj w regularny spadek. Wszystkie
   cięcia, wejścia muzyki i efekty leżą na siatce. Szczegóły: `rytm.md`.
5. **Jedna ciągła kotwica narracji i puenta postaci na końcu.** Licznik roku to jedyna ciągła rzecz w filmie:
   jego wartość zależy tylko od czasu całego filmu. W przejściu stara i nowa warstwa pokazują tę samą przewijaną
   liczbę, każda swoim krojem (40,000 BC pisane jak malowidło naskalne → 1350 BC trzcinowym piórem → … → 2026
   geometrycznym bezszeryfowym). Na końcu postać dostaje puentę: kot trzy razy trąca filiżankę i zrzuca ją ze stołu,
   dziewczyna krzyczy, pojawia się podpis. Graj ją pełnymi zasadami animacji: przygotowanie, zgniecenie
   i rozciągnięcie, podążanie, ruch wtórny. Pierwsze 11 s to „patrzenie”, ostatnie 4 s to „śmiech”, a śmiech
   sprawia, że film się udostępnia.

### Uzupełnienia z testów przeniesienia (A–D)
- **Ruch bohatera jest ciągły między odcinkami.** Kotwicą jest nie tylko licznik: ruch bohatera też idzie z czasem
  całego filmu. Gdy każdy odcinek zaczyna ruch od nowa, widz widzi „podniosła filiżankę pięć razy”, a nie „tę samą
  chwilę w pięciu stylach”.
- **Licznik z latami wymaga odcinków w kolejności chronologicznej.** Jeśli kolejność jest inna, zamień znacznik na
  numer albo nazwę stylu (znacznik w silniku jest wymienny). W połowie przejścia przełącz stary i nowy znacznik
  twardo, bez nakładania napisów.
- **Pierwszy odcinek nie ma przejścia: niech obraz „namaluje się sam”** (pociągnięcia się wypisują, kolory druku
  spadają warstwa po warstwie, piksele zapalają się wiersz po wierszu).
- **Im bardziej złożone przejście-podpis, tym dłuższe.** W oryginale kształty są proste i 0,4 s wystarcza; złoto,
  wstęgi koloru, szarfy potrzebują 0,48–0,5 s.

### Nowy temat na tym samym mechanizmie

| Warstwa | Wzór | „100 lat jednej ulicy” |
|---|---|---|
| Szkielet | okno, stół, kot, postać | ten sam róg ulicy: latarnia, szyld sklepu, przechodnie, linia dachów |
| Żywy obraz | małe pętle motywów epoki | przejeżdża pojazd z danej dekady, migają litery szyldu, w niebie coś leci (latawiec → samolot → dron) |
| Przejście | język-podpis następnej epoki | nośnik następnej dekady: przepalona taśma filmowa, śnieg telewizora, piksele, linie skanowania |
| Rytm | 128 BPM, coraz krótsze odcinki | to samo |
| Kotwica i puenta | licznik roku, kot zrzuca filiżankę | licznik roku, ten sam gołąb w każdej dekadzie coś podkrada |

### Nie ucz się krzywo
- 16 epok to nie norma. Mechanizm to „zmienia się styl, szkielet zostaje”; działa i przy 3 epokach.
- Nie kopiuj filmu-wzoru piksel po pikselu. Replika to sposób nauki mechanizmu, a oddajesz własną wersję (replika
  w bibliotece też podmieniła postacie na własne, zostawiając szkielet oryginału).

## 2. Najpierw jedna klatka, potem ruch: cztery drogi

Zasada: najpierw zaprojektuj jedną klatkę, która jest obrazem, dopiero potem każ jej się ruszać. Wszystkie cztery
drogi przeszły realny test w jednym projekcie; każda ma swoje miejsce.

| Droga | Kto maluje | Kto rusza | Test | Kiedy wybrać |
|---|---|---|---|---|
| **A Sam kod** | Canvas proceduralnie + renderer stylu | kod (krzywe choreografii, IK, cząstki, wrząca linia) | główna linia repliki | chcesz animacji artystycznej wprost z kodu; precyzyjna kontrola ruchu każdego elementu; dziesiątki stylów (zmiana renderera = zmiana stylu); synchronizacja z lektorem co do klatki |
| **B Warstwy AI + ruch kodem** | model obrazu maluje warstwy na zielonym tle, we współrzędnych klatki (Studio, skill `generacja-ai`) | kod (przesunięcie, łuk, zgniecenie, fizyka, efekty) | zakończenie „2026”: 11 warstw złożonych za pierwszym razem | najwyższa jakość obrazu, złożona gra postaci; styl realistyczny albo ilustracyjny, którego kod nie namaluje |
| **C Obraz → wideo, ta sama klatka na początku i końcu** | model obrazu maluje klatkę | model wideo z klatką pierwszą i ostatnią (Wideograf, skill `wideo-ai`) | próbka Van Gogha (Seedance 2.0): dziewczyna odstawia i podnosi filiżankę, niebo się kręci, kot macha ogonem, kompozycja trzymana do końca | chcesz, żeby „cały obraz płynął” organicznie, bez precyzyjnej kontroli; ujęcia przykładowe i klimatyczne |
| **D Mieszana** | tło z B/C, postać z A (albo odwrotnie) | kod układa wspólną oś czasu | – | duża produkcja: tło z fakturą, postać sterowalna |

### Wspólny pierwszy krok: klatka koncepcyjna
Niezależnie od drogi najpierw powstaje jedna „właściwa” klatka.
- **Jest film-wzór:** ostatnią klatkę odcinka przed przejściem podaj modelowi obrazu jako referencję. Prompt:
  „zachowaj dokładnie kompozycję, kadr, położenie i wielkość każdego przedmiotu, kolory i pociągnięcia z obrazu
  referencyjnego; zmień tylko dwie rzeczy: …”. W teście nałożenie 50% na oryginał pokrywa się prawie piksel
  w piksel. Kompozycję trzyma obraz referencyjny, nie współrzędne opisane w tekście. Ostatnie klatki odcinków
  w pełnym kadrze: `@@PY@@ "$HERMES_HOME/scripts/kadry.py" wzor film-wzor.mp4 -o out/wideo/wzor` → `ref/odc01.png` ….
- **Nie ma wzoru:** najpierw ustal szkielet sceny (współrzędne kompozycji wzorcowej), zrób zrzut makiety szkieletu
  i użyj go jako referencji.
- **Bramka trzech kierunków:** interpretację postaci (w replice: strój epoki / ta sama osoba w podróży / oryginał
  z podmienioną głową) pokaż w trzech wariantach na tej samej klatce. Różnice najlepiej widać na klatce, na której
  oryginał ma postać męską. Gdy właściciela nie ma: rozdział 10.

Pułapki klatki koncepcyjnej:
- Postać niepełnoletnia (17 lat) i jakiekolwiek słowo o krótkiej spódnicy: moderacja odrzuca cały obraz jako
  treść seksualną. Strój zawsze długi, dopisz „strój skromny”.
- Umaszczenie opisuj partiami ciała: „kot rudo-biały (czubek głowy, grzbiet i ogon rude w pręgi; pysk, pierś,
  brzuch i łapy białe)”. Samo „rudy kot” daje kota rudego w całości.
- Czynność w opisie („pije herbatę z filiżanki”) wygrywa z pozą z referencji. Żeby zachować pozę, pisz tylko
  „zachowaj gest z obrazu referencyjnego”.
- Tekst, który ma się ruszać (rok, tytuł): model ma go usunąć i zostawić czyste tło, rysuje go kod. Dekoracyjne
  napisy w obrazie wpisz do promptu znak po znaku.
- Generacje uruchamiaj po kolei, nie równolegle. Sprawdź, czy to naprawdę generacje: nowych plików jest tyle, ile
  obrazów, a PNG nie ma w metadanych `date:create` z ImageMagick (to znak sklejki, nie generacji). Każdą generację
  wpisz do rejestru (`out/wideo/src/generacje.jsonl`, jak w `wideo-ai`).
- W prompcie opisuj gramatykę formy (materiał, pociągnięcie, paleta, motyw), nie „w stylu <żyjący artysta>”
  (zasada `generacja-ai`).

### Droga B: zielone tło, współrzędne z klatki
Klatka koncepcyjna idzie jako referencja, prompt: „Namaluj tylko XX z obrazu referencyjnego… Cała reszta to
jednolite #00FF00, bez cienia, podłoża i tekstu. Położenie, wielkość i kierunek dokładnie jak na referencji.”
Wygenerowana postać stoi już we współrzędnych klatki. Przy wycinaniu **nie przycinaj do ramki obiektu bez zapisania
pozycji**: `malarz.py wytnij` (port ich `key_green.py`) przycina i zapisuje lewy górny róg w `sprites.json` (`x`, `y`, `w`, `h` w kadrze
1920×1080), więc przy składaniu wklejasz w oryginalne miejsce i wszystko trafia za pierwszym razem:
```sh
@@PY@@ "$HERMES_HOME/scripts/malarz.py" wytnij out/wideo/src/surowe/*.png --out out/wideo/src/sprites [--soft 40 --hard 110]
```
(Domyślnie `--soft 30 --hard 100 --pad 4`; numpy i Pillow bierze z Pythona narzędzi sam. W `sprites.json` jest też
`kadr` = rozmiar klatki źródłowej.)

### Droga C: ta sama klatka na początku i końcu
Model wideo z klatką pierwszą i ostatnią (frames2video, np. Seedance 2.0/2.5; czy model przyjmuje klatkę końcową,
sprawdź w schemacie `video_generate`). Ta sama klatka koncepcyjna na początku i końcu: rzeczy w obrazie ruszają
się i wracają do kompozycji, więc początek i koniec klipu łączą się bez szwu z przejściem. Prompt w trzech częściach:
1. kamera całkowicie nieruchoma (bez najazdu, odjazdu, panoramy, zoomu, drgań);
2. przez cały czas ta sama kompozycja, styl i kolory; bez urealniania, bez dodawania i usuwania przedmiotów, bez
   nowego tekstu;
3. punkt po punkcie: co w obrazie się rusza i jak (z listy ruchu z rozpisu wzoru).

Generuj 5 s, wybierz najlepszą ok. 1 s i zmień jej tempo pod rytm. Liczy się prompt, nie konkretny dostawca. Każda
generacja kosztuje: najpierw jedna krótka próba; limity z `wideo-ai` (domyślnie 3 klipy na kartę).

### Droga A
Rozdziały 3–9. W jednym zdaniu: ten sam szkielet sceny × wspólna choreografia × jeden renderer na styl × postać
w osobnej warstwie, malowana później × na końcu dorysowane linie.

## 3. Szkielet silnika (droga A)

Silnik leży w `$HUASHU/scripts/engine/` (czytasz go, nie modyfikujesz):
```
index.html      kolejność ładowania: lib/fonts → lib/util → lib/paint → lib/rig → eras → transitions → scenes/index → engine
eras.js         tabela odcinków: id, liczba ósemek (eighths), przejście {type, dur, delay, cx, cy}, wygląd tabliczki roku
scenes/<id>.js  jeden plik na odcinek: SCENES['<id>'] = { draw(c, lt, t) }   ← tu jest większość pracy
transitions.js  biblioteka przejść: (c, A stary, B nowy, p, o) → rysuje jedną klatkę
engine.js       siatka bitów → t0/t1 każdego odcinka; w przejściu stary i nowy odcinek rysowane poza ekranem i oddane
                przejściu; uderzenie kamery na bicie; licznik roku (wartość tylko z globalnego t)
lib/paint.js    szum, tekstury, ręczna „wrząca” linia, renderery stylów, paleta regionu swatch, wspólna choreografia
                choreo, para, cząstki
lib/rig.js      szkielet postaci: RIG.girl / RIG.cat → Path2D każdej części + punkty zaczepienia; drawGirl/drawCat
                (mode: fill/line); ik2, smooth, taper
```
Obecna wersja ładuje też wspólne biblioteki `lib/brush.js` (pędzle), `lib/render.js` (renderery), `lib/post.js`
(postprodukcja) i `lib/kit.js` (narzędzia).

W Jarvie nie używamy ich `render.py` ani `compare.py`:
- szkielet naszej strony (kontrakt jarvo, `window.__seek(t)`):
  `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl <id>[,<id>…]` robi `index.html`
  (biblioteki z `/_lib/huashu/`, polska nakładka `/_lib/jarvo/huashu_pl.js`, ich `transitions.js`,
  `scenes/index.js` i `engine.js`; bez `lib/rig_huashu.js`, czyli postaci autora), `eras.js` (Twoja tabela
  odcinków: ósemki przy `window.BPM`, przejście-podpis wchodzącego stylu z galerii) i `sceny/<id>.js` (kopia
  sceny-wzoru z nagłówkiem licencji: punkt startu, który przerabiasz). Kadr 1920×1080 na sztywno (stałe `W, H`
  w bibliotekach, scenach i przejściach); film pionowy: `SKILL.md`, „Pion 9:16”;
- katalog i galeria: `malarz.py style [--szukaj …]`, `malarz.py galeria -o out/wideo/galeria-stylow.jpg`
  (jeden kadr każdego z 35 stylów z podpisem);
- stopklatki sceny-wzoru w czasie lokalnym odcinka:
  `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor <id> --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-<id>.jpg`;
- klatki i film z naszej strony: `@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" klatki out/wideo/src/film/index.html
  --preset jarvo --czasy … --arkusz …` oraz `html_wideo.py wideo … --dlugosc <s> -o out/wideo/film.mp4`
  (klatki w kilku przeglądarkach naraz same, `--rownolegle N`; bez motion bluru, `--subklatki` zostaje 1);
- porównanie wzoru i Twojej wersji obok siebie (zamiast `compare.py`): `@@PY@@ "$HERMES_HOME/scripts/kadry.py"
  arkusz wzor.mp4 moja.mp4 --klatek 6 -o out/wideo/porownanie.jpg` (każdy klip w jednym rzędzie).

Szybkość w źródle: cały film 15 s w 60 kl./s ok. 90 s (Mac z procesorem serii M); pojedynczy odcinek zwykle
5–40 ms na klatkę, najcięższy Van Gogh 110 ms. Na naszej maszynie zmierz sam na kilku klatkach.

## 4. Jak namalować jeden styl: pięć warstw (wzorzec `scenes/09_postimp.js`)

Pięć warstw to domyślna kolejność dla olejnych i graficznych stylów, nie reguła dla wszystkich:
- **tusz (malarstwo chińskie)** odwrotnie: papier jest podkładem, tusz tylko dochodzi, dużo pustego miejsca, nic
  nie zalewasz na start;
- **style wzorów** (Kusama, Bauhaus): płaskie kolory, na nich rozsypany wzór; sam wzór jest rendererem;
- **światłocień**: najpierw namaluj jasną wersję, potem pomnóż przez mapę światła.

1. **Płaski podkład.** Duże płaszczyzny (ściana, podłoga, niebo, widok za oknem) czystym kolorem albo gradientem,
   we właściwym miejscu i jasności. Ta warstwa ustala kompozycję; stylu jeszcze nie ma.
2. **Renderer stylu maluje od nowa.** Podkład służy jako źródło kolorów, a renderer maluje cały kadr techniką stylu:
   długie pociągnięcia po polu kierunków u Van Gogha, krótkie plamki impresjonizmu, kamienie mozaiki, przesunięte
   kolory druku i wzory ukiyo-e, płaszczyzny kubizmu, raster pop-artu, piksele w niskiej rozdzielczości 8-bit,
   odbicia piksel po pikselu w ray tracingu. Renderer decyduje, „czyj to obraz”.
3. **Małe przedmioty w osobnej warstwie.** Stół, krzesła, wazon, rama obrazu: wrzucone do renderera razem z dużymi
   płaszczyznami rozpadną się w bezkształtną plamę. Maluj je osobno, drobniejszymi parametrami, z `source-atop`, tylko
   na nich samych.
4. **Postać.** Ten sam szkielet (RIG), ta sama choreografia, inna technika: płaskie kolory, na nich drobna faktura
   stylu, na końcu wyraźny kontur i rysy twarzy. Na postaci ląduje wzrok widza: musi być czytelne, kto to jest.
5. **Ruchome akcenty.** Małe pętle motywów epoki (rozdział 1). Ruch ciągły liczony z ciągłego czasu. Ręczne linie
   „wrzą”: nowe ziarno 8–12 razy na sekundę daje wrażenie ręcznej roboty.

## 5. Renderery stylów (w `lib/paint.js` albo pisane w scenie)

| Renderer | Do czego | Klucz |
|---|---|---|
| `strokes` pociągnięcia po polu kierunków | Van Gogh, ekspresjonizm, obraz olejny | pole kierunków pisane per region (ściana pionowo, podłoga wzdłuż perspektywy, niebo po wirze); **paleta regionu** ważniejsza niż drganie koloru; każde pociągnięcie z ciemnym obrysem, wtedy jest grube |
| `dabs` plamki koloru | impresjonizm | krótkie eliptyczne plamki przesunięte w ciepło i chłód; **to nie puentylizm** (brak czystej palety, plamki nierówne: wychodzi impresjonizm) |
| optyczne mieszanie kropek (29_seurat) | Seurat, neoimpresjonizm | czysta paleta zestawiana w proporcjach, równe kropki, kropki dopełniające, przenikanie światła na granicy światła i cienia |
| mozaika (04_roman, pisana w scenie) | mozaika, witraż | układ liczony raz, kolor co klatkę płynie przez kamienie; kamienie ułożone wzdłuż konturu (linie stałej wartości pola odległości); kamień o 8–28% większy niż połowa odstępu, żeby dwusieczne wycięły fugę |
| druk wielobarwny + wzory (07_ukiyoe; tej sceny nie ma wśród 35 scen biblioteki) | ukiyo-e, drzeworyt, sitodruk | kolor przesunięty względem linii tuszu o (3,2) px; wzory jako CanvasPattern; poziome smugi pędzla do cieniowania |
| `facets` płaszczyzny | kubizm, low poly | półprzezroczyste płaszczyzny z gradientem budują przestrzeń; trójkąty bez przycinania, wtedy kontur robi się prostymi krawędziami |
| `halftone` raster | pop-art, stary druk | mały kafel przez `createPattern` jest 10× szybszy niż kropka po kropce; siatka 45° |
| niska rozdzielczość piksel po pikselu (14_8bit) | piksel, retro gry | maluj w 240×135, powiększ metodą najbliższego sąsiada; paleta 14 kolorów; każda część z czarnym obrysem 1 px |
| cieniowanie piksel po pikselu (15_raytrace) | wczesne CGI, plastik, metal | jedno cieniowanie plastiku (kolor + ciemny brzeg promieniowy + odbicie otoczenia + twardy blask); odbicie w podłodze lustrzanie |
| złoto (05_gothic) | złocenia, ikony, ornament | szlif piksel po pikselu + ciemna linia tłoczenia z jasną linią przesuniętą o 1 px; blask tylko na masce „złotości” |
| sfumato (06_renaissance) | klasyczny obraz olejny | lekkie rozmycie całej warstwy + półprzezroczysta ostra warstwa; spękania, faktura płótna, winieta, żółty werniks |
| ścieżka o zmiennej grubości (10_nouveau) | secesja, kaligrafia, grafika | z listy punktów wielokąt przesunięty w obie strony o szerokość; sylwetka w ciemnym kolorze przesunięta pod spód = grube na zewnątrz, cienkie w środku |
| ziarniste kropki (16_2026) | współczesna płaska ilustracja | kropki rozsypane w kształcie, gęstość jako funkcja położenia; wszystko statyczne w cache |
| sucha kreska pędzla + rozlany tusz (17_ink) | tusz, kaligrafia, malarstwo chińskie | nacisk i zwolnienie pędzla, próbkowanie co równy odcinek łuku daje suchą kreskę; rozlewanie przez `filter='blur()'` (w Chromium deterministyczne); papier jest podkładem, tusz tylko dochodzi |
| długie wygięte pociągnięcia + falowanie wierszami (19_munch) | ekspresjonizm, poczucie płynięcia | długie pociągnięcie 20–30 kroków po polu kierunków; cały kadr przesuwany sinusoidą wiersz po wierszu (margines ≥ największego przesunięcia, żeby nie odsłonić szczeliny) |
| akwarela (25_ghibli) | tła Ghibli, akwarela | przezroczyste nakładanie koloru + brzeg zacieku; krycie obrysu zacieku maleje w miarę rozlewania |
| raster ze zdjęcia w szarości (22_constructivism) | konstruktywizm, stara gazeta, fotomontaż | średnica kropki z jasności, siatka 45°, wszystkie kropki w jednej ścieżce i jednym `fill` |
| dwie wersje światła z przycięciem + długi cień ścinaniem (24_hopper, 23_dali) | Hopper, surrealizm, ostre światło | jasna i ciemna wersja malowane osobno, przycinane plamami światła; cień przez afiniczne ścinanie |
| VHS z rozdzieleniem kanałów (26_vaporwave) | vaporwave, retro wideo | przesunięcie RGB, linie skanowania, pas szumu śledzenia jako warstwa postprodukcji |
| mnożenie przez mapę światła (32_rembrandt) | światłocień, noc, świeca | najpierw jasna wersja, potem mnożenie przez mapę światła (światło okna + promieniowe światło świecy) |
| twarde pasy cienia jak w celuloidzie (35_shinkai) | anime, Shinkai | część minus jej przesunięta kopia = twardy pas cienia; jasny brzeg po stronie światła |
| skokowy klatkaż `stepTime(t, fps)` (33_rubberhose, 34_shadowpuppet) | stara animacja, teatr cieni, poklatkowa | 12 kl./s i 10 kl./s „szarpane” to połowa stylu, nie przycięcie |

(`stepTime` jest w `U` z `lib/util.js`: `U.stepTime`.)

## 6. Postacie: jeden szkielet, kilkanaście technik

- Współrzędnych szkieletu nie zgaduj. Weź klatkę koncepcyjną z AI (albo inną referencję), nałóż siatkę 20 px,
  odczytaj kluczowe punkty każdej części i wygładź je krzywą Catmulla-Roma do Path2D (`RIG.smooth`). Pierwsza
  wersja z ręcznie wpisanych współrzędnych wyglądała jak chłopiec; po odczycie punktów od razu czytała się jako
  17-letnia dziewczyna o blond włosach.
- Pozycja siedząca: nogi schowane w długiej sukni wyglądają najnaturalniej. Filiżanka: IK na dwóch kościach
  (ramię 165 / przedramię 122), łokieć zawsze w dół.
- Punkty zaczepienia `G.A` (czubek głowy, czoło, szyja, pierś, talia, kolana, dłonie…) służą do strojów stylu:
  egipski szeroki kołnierz, gotycka aureola, japońska fryzura shimada w ukiyo-e, krążki stawów w Bauhausie, wielkie
  fale włosów w pop-arcie.
- Styl może stylizować szkielet (egipski profil z okiem en face, czarna sylwetka z wazy czarnofigurowej, kubistyczna
  twarz z niebieską połową, pikselizacja), ale miejsce i rytm ruchu zostają jak w szkielecie. Stąd bierze się
  wrażenie „ta sama para w podróży przez style”.
- Dużych ruchów puenty (skok, położenie się, wyciągnięcie łapy, okrzyk) nie wciskaj w ogólny szkielet. `16_2026`
  ma własną bibliotekę póz (każda poza to zestaw lokalnych punktów kluczowych, interpolowany wartość po wartości);
  zgniecenie i rozciągnięcie z osią w stopach, odwrócenie postaci w najbardziej spłaszczonej klatce.
- Ludzie i postacie uczłowieczone: lepiej klatki z biblioteki albo klatki AI w stylu filmu (`postacie.md`).
  Szkielet RIG zostaje do postaci geometrycznych, makiety ruchu i jako punkt odniesienia ruchu.

## 7. Ożyw obraz: lista ruchu i pomiar

- Każdy odcinek ma co najmniej jeden ciągły ruch główny bohatera (`choreo.cup`, podnoszenie filiżanki) i 2–4 małe
  pętle motywów. Krótki odcinek (< 0,5 s): ruch skokowy 15–30 kl./s, żeby był szybki.
- Zmierz ilość ruchu: dwie klatki i ich różnica. **Omijaj 0,35 s po przejściu** (uderzenie kamery: wtedy rusza się
  cały kadr). Pierwsze pomiary (po końcu skalowania, 0,45 ↔ 0,9 s): jaskinia 2,8%, Egipt 3,4%, Rzym 6,4%, Grecja
  9,9%; ten sam fragment oryginału na mapie ruchu: 6,9%, 6,2%, 17,3%, 11,6%. Za statycznie: dodaj ruch motywów.
  W Jarvie: `html_wideo.py klatki out/wideo/src/film/index.html --preset jarvo --czasy <t0+0.45>,<t0+0.9>` i porównanie
  obu klatek okiem i liczbą (udział zmienionych pikseli); na gotowym klipie `krytyka.py martwe` (odcinki bez zmiany
  obrazu) i `krytyka.py puls` (gdzie film zwalnia).
- To, co się rusza, ma leżeć w punkcie skupienia wzroku: postać, kot, okno.

## 8. Pułapki (każda już się zdarzyła)

- **Tryby składania.** `source-in` dla każdego wzoru osobno: wzory wzajemnie się kasują (złota szata u Klimta
  zniknęła cała). Najpierw namaluj wszystkie wzory na jednej warstwie roboczej, potem raz `source-in` po sylwetce.
  `destination-out` na płótnie odcinka wycina przezroczyste dziury, które w wideo są czarne: wytnij w warstwie poza
  ekranem i dopiero ją wklej. Faktury papieru i ziarna na postaci nie nakładaj przez `source-atop` (kolor papieru
  przykrywa postać, robi się blada): warstwę faktury przytnij `destination-in` do sylwetki i nałóż z `multiply`.
- Własne glify: dwie kreski o przeciwnym kierunku w jednej ścieżce przy regule nonzero znoszą się i robią dziurę.
  Każdą część wypełniaj osobno.
- Przejście „topnienie”: nowy obraz spływa z góry kroplami o okrągłych czołach (profil `(1-u²)^0.3`). Stary obraz
  ciągnięty w dół daje kolce, nie krople.
- Długość przejścia licz z tego, co widać. Przy krzywej inOut oba końce prawie się nie zmieniają; złożone
  przejście-podpis 0,34 s jest czytelne tylko przez 0,2 s i wygląda jak zwykłe wycieranie. Daj 0,48–0,5 s.
- Półprzezroczyste nakładki (teatr cieni, wycinanki): w miejscach nakładania mnożenie daje czerń. Kolejność
  i krycie warstw dobierz do materiału.
- `putImageData` prosto na docelowe płótno omija uderzenie kamery i przycięcie przejścia. Najpierw do warstwy poza
  ekranem, potem `drawImage`.
- Warstwa poza ekranem, z której czytasz piksele: kontekst z `{willReadFrequently:true}`; co klatkę `g.reset()`,
  inaczej zostaje stan poprzedniej klatki (lineJoin i inne) i pierwsza klatka różni się od kolejnych.
- `drawGirl(mode:'line')` na samej górze rysuje kontury części zasłoniętych (dalszy rękaw przez tułów, tylna część
  nakrycia głowy przez włosy). Użyj `RIG.visibleLines(key, (g, lineColor) => pełne rysowanie, prawdziwy kolor
  linii, box)`: ta sama technika dwa razy, raz z białą linią jako strażnikiem; piksele różne w obu przebiegach to
  linie niezasłonięte (z liniami twarzy). Kolejność: wypełnienie → faktura stylu → visibleLines dorysowuje linie.
- **Uderzenie kamery działa na obie warstwy, starą i nową.** Gdy uderza tylko nowa, na początku przejścia jej
  jeszcze nie widać, kadr w klatce bitu stoi i „dźwięk wyprzedza obraz” (w pierwszej wersji spóźnienie
  0,1–0,17 s).
- **Cały kadr z nowym ziarnem pociągnięć 8 razy na sekundę = migotanie, nie życie.** Różnica klatek przy takim
  skoku 18–20, więcej niż w przejściu. Pociągnięcia zostają na miejscu, a pole kierunków zmienia się w czasie
  w sposób ciągły (jak płomień); „wrzenie” tylko dla linii rysunku.
- Nie zmieniaj osobno parametrów w obszarze ruchu (wielkość kamieni, gęstość pociągnięć): gdy stoi, wygląda jak łata.
- W stylach z grubym ziarnem (mozaika, piksel) litery rysuj jednakowo grubą kreską (każda kreska ≥ 2 ziarna
  szerokości). Cienki krój się porwie.
- Małe rzeczy rób większe, niż Ci się wydaje: pazury fali ukiyo-e w 22–50 px są nieczytelne, w 44–74 px to dopiero
  „Wielka fala w Kanagawie”.
- Deterministyczność: każdy los z ziarnem; ten sam t renderowany dwa razy musi dać identyczne piksele, inaczej film
  migocze.

## 9. Podział pracy między kilku wykonawców

Gdy style malują równolegle podagenci: najpierw spisz specyfikację autora stylu (interfejs, dostępne biblioteki,
wzorzec, wymagania twarde, materiały, polecenia samokontroli, notatki do oddania; rozdział 10), potem rozdziel
odcinki po 4 na wykonawcę. W specyfikacji: „nie zmieniasz `lib/` ani cudzych plików”. Każda grupa oddaje pracę po
30–35 minutach, a notatki od razu stają się kartami stylów. Za pierwszym razem wszystkie 16 odcinków przeszło
od razu, głównie dzięki specyfikacji i wzorcowej scenie.

## 10. Specyfikacja autora stylu (dla piszącego scenę i dla podagenta)

### Interfejs
Odcinek stylu to plik sceny:
```js
SCENES['<id>'] = { draw(c, lt, t) { /* maluje cały kadr 1920×1080 */ }, init(IMG) { /* opcjonalnie: jednorazowe obliczenia */ } };
```
- `c` docelowy kontekst 2D; `lt` czas lokalny odcinka (s, od początku jego przejścia); `t` czas całego filmu.
- Tabela odcinków `eras.js`: `{ id, eighths albo dur, transition: { type, dur }, counter: {...} }`. Długość filmu
  liczy się sama z tabeli.
- Przejście w `transitions.js`: `TRANSITIONS.<nazwa> = (c, A stary, B nowy, p, o) => {}`.
- Brak pliku sceny, błąd składni, scena niezarejestrowana: silnik nie startuje. W Jarvie zgłosi to render
  (`html_wideo.py`) i pomiar (`blad_js`). Nie oceniaj sukcesu po tym, że „coś się wyrenderowało”.

### Najpierw przeczytaj (w tej kolejności)
1. Tę kartę (mechanizm, potok, renderery, pułapki) i `zasady-huashu.md`.
2. Kartę najbliższego stylu (`<id>.md` w tym skillu) jako punkt startu.
3. Wzorcową scenę `$HUASHU/scripts/engine/scenes/09_postimp.js` i kod sceny najbliższego stylu
   (stopklatki: `malarz.py wzor <id>`).
4. `$HUASHU/scripts/engine/lib/`: `paint.js` (szum, tekstury, renderery, palety, choreografia), `rig.js` (szkielet
   postaci, visibleLines), `kit.js` i inne. **Najpierw sprawdź, czy biblioteka to ma, dopiero potem pisz sam.**

### Dwa punkty startu
**Jest film-wzór:** `@@PY@@ "$HERMES_HOME/scripts/kadry.py" wzor film-wzor.mp4 -o out/wideo/wzor` daje arkusze klatek
z czasem, cięcia, rytm i rozbiór ruchu (port ich `breakdown.py`): starty przejść na siatce bitów, arkusz każdego
przejścia co 2 klatki (`przejscia/P01.jpg`), mapę ruchu odcinków (`ruch-1.jpg`) i klatki kluczowe (`ref/odc01.png`
w pełnym kadrze). Klatki wzoru decydują o kompozycji, motywach i kolorach; co w obrazie się rusza, pokazuje mapa
ruchu, szczegół akcji gęstszy arkusz (`--fps`) i `krytyka.py pasek`.

**Nie ma wzoru** (częściej):
1. Zapisz 3–5 najbardziej rozpoznawalnych elementów formalnych stylu (materiał, pociągnięcie, paleta, motyw, ślady
   nośnika). Sprawdź w źródłach (reprodukcje oryginałów, opisy historyków sztuki), nie z pamięci.
2. Każdemu elementowi daj sposób ruchu, jaki ma w świecie tego obrazu (woda drży, papier fruwa, złoto błyska,
   druk się przesuwa, taśma drga).
3. Ustal, jak taki obraz powstaje naprawdę (malowanie, ryt, druk, klejenie, inkrustacja, natrysk, rendering) i ten
   fizyczny proces zapisz jako renderer.
4. Najpierw jedna klatka: arkusz stopklatek obok oryginału; dopiero gdy styl rozpoznajesz od razu, ruch.

### Wymagania twarde
1. **Szkielet sceny:** pozycje według współrzędnych kompozycji projektu (wspólne dla wszystkich odcinków; na nich
   opierają się przejścia i „ta sama postać w podróży”).
2. **Postać:** szkielet `RIG` i wspólna choreografia; zmieniasz technikę, nie miejsce ani ruch. **Postać też
   przechodzi przez materiał stylu** (pociągnięcia, ziarno, papier przez `multiply`, rozlany brzeg tuszu, raster,
   przesunięcie kolorów druku…), inaczej wygląda jak naklejony wycinek; to najczęstsza słabość w 36 stylach. Linie
   rysunku: `drawGirl/drawCat` z `mode:'line'` (w środku już działa visibleLines, nie przebija).
3. **Obraz żyje:** ruch główny i 2–4 pętle motywów, widoczne w oknie postoju. W przeglądzie i podróży przez style
   ruch postaci idzie z czasem całego filmu (`PAINT.cupCycle(t)` i podobne), bez zerowania na zmianie odcinka.
4. **Płynność:** nie zmieniaj ziarna całego kadru w niskim klatkażu (czyta się jako migotanie); „wrzenie” tylko dla
   linii rysunku albo obszarów motywów. Celowy klatkaż skokowy (rubber hose 12 kl./s, teatr cieni 10 kl./s) przez
   `stepTime`: to styl, nie przycięcie. Okres modulo przewijanego wzoru = prawdziwy okres wzoru.
5. **Deterministyczność:** każdy los z ziarnem; ten sam t dwa razy = identyczne piksele.
6. **Wydajność:** statyczne części przez `PAINT.cached`; warstwa, z której czytasz piksele, z `willReadFrequently`
   i `g.reset()` co klatkę; cel ≤ 150 ms na klatkę (prawdziwy czas renderu, nie sam czas JS).
7. **Tekst:** napisy stylu najlepiej jako ścieżki w materiale stylu. Krój: najpierw `U.assertGlyphs` (brak glifu =
   cichy zamiennik systemowy). Polskie znaki: nakładka `huashu_pl.js` podmienia kroje bez nich (np. PuHui-* →
   Inter, LXGWWenKai-500 → Caveat-600, Rye → Alfa Slab One); sprawdź „Zażółć gęślą jaźń” na arkuszu, a kroje kanwy
   wczytaj przed gotowością z próbką polskich liter (`document.fonts.load('64px "Inter"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`).
8. **Postarzanie nie na postaci:** łuszczenie, plamy, rysy tylko w tle; wokół postaci strefa ochronna (plama
   łuszczenia z Dunhuangu na plecach czytała się jako „dziura w ubraniu”).

### Samokontrola i oddanie
```sh
# stopklatki Twojej sceny (czas lokalny odcinka)
@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" klatki out/wideo/src/film/index.html --preset jarvo \
  --czasy 0.4,0.6,0.8,1.0 --arkusz out/wideo/klatki-<id>.jpg
# wzór do porównania
@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor <id> --czasy 0.4,0.6,0.8,1.0 --arkusz out/wideo/wzor-<id>.jpg
# deterministyczność: ta sama klatka 2× = ten sam obraz
@@PY@@ "$HERMES_HOME/scripts/krytyka.py" determinizm out/wideo/src/film/index.html --czasy 1.3,4.2 --preset jarvo
# liczby: błędy JS, kroje zastępcze, martwe odcinki; po renderze duchy, skoki i zamrożone klatki
@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" pomiar out/wideo/src/film/index.html --preset jarvo --dlugosc <s>
@@PY@@ "$HERMES_HOME/scripts/qa_wideo.py" out/wideo/film.mp4 --json
```
Każdy odcinek co najmniej 3 rundy: stopklatki obok oryginału albo wzoru → liczby (ruch, statyczne pary klatek,
skoki, czas, deterministyczność) → poprawka. Cztery pytania:
1. Czy od razu widać, który to styl?
2. Czy postać jest właściwa i zlewa się z tłem?
3. Czy w oknie postoju widać, że obraz się rusza, bez migotania i szarpania?
4. Czy nie ma wpadek (zasłanianie, przerwane linie, przesunięcia, puste miejsca, nakładające się napisy)?

Oddajesz: scenę i notatki stylu w RAPORT.md w układzie karty stylu (potok, kluczowe parametry i kolory, jak
animujesz motywy, przejście-podpis, wydajność, pułapki, co jeszcze do poprawy), konkretnie i z liczbami. **Film
z wielu odcinków przed oddaniem ogląda niezależny recenzent, który go nie robił, tylko gotowy film** (podagent,
skill `kontrola-wideo`).

### Bramka trzech kierunków bez właściciela
- Właściciel jest dostępny i czeka na wybór: nowy kierunek stylu i interpretację postaci pokaż najpierw w trzech
  wariantach na tej samej klatce.
- Nikogo nie ma (automat, praca nocna, karta bez rozmowy): wykonaj kierunek z briefu i w RAPORT.md wypisz dwa inne
  kierunki, które można było dać, po jednym zdaniu każdy. Właściciel wybierze po powrocie.
