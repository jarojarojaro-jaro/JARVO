# Interfejs z premiery (`prezentacja`, w kodzie `t2_keynote_ui`)

Ciemne tło z wolno dryfującymi plamami koloru i jedna rzecz na ekran: tekst wyłania się z rozmycia, interfejs leży w szklanej karcie, która ląduje w 3D na sprężynie bez odbicia albo z lekkim odbiciem, liczby się odliczają, przelatuje odblask, a przejście rozwija tę samą taflę szkła. Wzór: `python3 $HERMES_HOME/scripts/gramatyka.py wzor prezentacja --arkusz out/wideo/wzor-prezentacja.jpg`; start: `python3 $HERMES_HOME/scripts/gramatyka.py szablon prezentacja [--format 9:16] -o out/wideo/src/klip-prezentacja/spec.json`.

Kod: klip `$HUASHU/scripts/engine/clips/t2_keynote_ui.js`, przykład `$HUASHU/scripts/engine/examples/t2_keynote_ui.json` (trzy karty funkcji, wielka liczba, karta ze zrzutem i ramką), film pokazowy `$HUASHU/scripts/engine/demos/t2_keynote_ui/` (MIT). Film pokazowy ma 8 s i 3 ujęcia (2,6/3,0/2,4 s), gęściej niż prawdziwa prezentacja: bierz technikę, nie tempo.
Potok: `szablon` → polskie teksty, zrzuty i `slowo` → `gramatyka.py sprawdz` → `gramatyka.py render … --klatki 0.5,2,4` (sprawdź `rect`) → pełny `render`.

## Kiedy
- Premiera produktu albo funkcji, nowa wersja, „trzy nowe funkcje”, ogłoszenie ceny i parametrów, intro marki, fragment „czym jest ten produkt”.
- Lektor mówi rzeczownikami i liczbami („Plover 2”, „opóźnienie 320 ms”, „milion tokenów”): jedno zdanie = jeden ekran; rzeczownik wyłania się, gdy pada, liczba staje, gdy pada.
- Zrzut interfejsu ma wyglądać jak z premiery: w szklanej karcie, obrócony w 3D do frontu.
- Kroki samouczka na zrzutach (czysto, bez „dowodowego” klimatu `vox`).
- Przykłady: film o nowej wersji aplikacji SaaS (30–60 s), samouczek „trzy kroki w panelu klienta” 16:9, rolka 9:16 z ceną i parametrami nowego planu, ekran powitalny w onboardingu.

## Nie do
- Mechanizm i zasada działania: szkło i plamy nie niosą logiki. Użyj `3b1b`.
- Trend w danych: `wykresy`.
- Poważny wypadek, zły wynik finansowy: ten język sam niesie nastrój „dobrej wiadomości”.
- Treść bez bohatera, którego można powiększyć (nazwy, liczby, karty): zostaje pusty ekran z plamami.
- Osobista historia z puentą: `historyjka`.

## Gramatyka (z pomiarów)
Źródła: CSS apple.com i linear.app, gradient Stripe 2021, WWDC 2018/2023/2025, Apple HIG (Motion, Materials, Typography), NN/g o glassmorphizmie, filmy premier Apple, OpenAI i Linear.

- **Długość.** Ekran prezentacji 5–8 s (Jobs, iPhone 2007: 70 s, 9 ekranów ≈ 7,8 s na ekran); szybki montaż produktowy 1,5–3 s.
- **Jedna rzecz na ekran.** Jedna nazwa, jedna liczba albo jedna karta. Po gęstym fragmencie daj pusty ekran na oddech (przeciwwaga z Presentation Zen).
- **Sprężyna (główny ruch).** `MO.spring(t, {duration, bounce})` jak w SwiftUI: masa 1, sztywność (2π/d)², tłumienie 4π(1−bounce)/d, czyli współczynnik tłumienia ζ = 1−bounce. **Domyślnie bounce 0.** 0,15 = sprężyście, prawie bez odbicia (we wzorze wejście kart d = 0,75, dymek d = 0,5); 0,3 = wyraźne odbicie; powyżej 0,4 interfejs wygląda tanio. `.smooth/.snappy/.bouncy` mają d = 0,5.
- **Krzywe (bez sprężyny).** Nawigacja apple.com: 0,32 s `cubic-bezier(.4,0,.6,1)`; wyłanianie tekstu we wzorze: CSS `ease` = `(.25,.1,.25,1)` (`MO.appleOut`); Linear: ease-out-quad `(.25,.46,.45,.94)`, 0,16 s; Stripe: poniżej 500 ms, `(.2,1,.2,1)`. `MO.bezier(x1,y1,x2,y2)` obsłuży każdą.
- **Wejście tekstu.** Rozmycie 18–26 px → 0, przesunięcie w górę 16–40 px → 0, krycie → 1, w 0,7–1,0 s (`TY.blurIn`). Nadtytuł → nazwa produktu → podtytuł z odstępem 0,2–0,4 s.
- **Wejście karty.** Z 170 px niżej, obrót wokół osi Y ±0,55 rad (≈31°, karty boczne odwrócone na zewnątrz), skala 0,9 → sprężyna na miejsce; trzy karty co 0,1 s. 3D przez `UI.persp` (perspektywa z pionowych pasków, persp 1800 px; Stripe 600, Linear 1000).
- **Ciągły drobny ruch.** Karty pływają 7 px z okresami 3,4/3,85/4,3 s (dwie częstotliwości, `MO.float`) i lekko kołyszą się wokół Y (±0,06 rad); plamy dryfują; kamera najeżdża równo 1→1,045 (**liniowo**: hamowanie do zera „uśmierca” obraz).
- **Plamy (tło).** 4 promieniste gradienty w trybie screen → rozmycie 90 px na 1/4 rozmiaru → skalowanie na cały kadr → 3,5% statycznego ziarna przeciw pasmom. Barwy z rodziny Stripe: fiolet `(150,90,238)`, niebieski `(56,104,255)`, błękit `(120,214,255)`, odrobina ciepłej czerwieni `(255,96,84)`; na środku 38% czarnego gradientu pod biały tekst. Dryf każdej plamy 90–260 px, okres 9,5–13 s; **omijaj okres 5 s** (HIG: unikaj ciągłego kołysania ~0,2 Hz).
- **Szklana karta.** Tło pod kartą rozmyte 40 px (nawigacja Apple: `saturate(180%) blur(20px)`; NN/g: im mocniej, tym lepiej), 7,5% białego wypełnienia, u góry 14% białego gradientu (pas światła), obrys 1,5 px z gradientem (lewa góra jasna, prawy dół ciemny), duży cień (rozmycie 70–80, y +30–40, α 0,5).
- **Zaokrąglenia.** Karta 36 px; **zaokrąglenia współśrodkowe**: tło ikony w środku = 36 − margines 14 = 22 (WWDC25: promień dziecka = promień rodzica − padding).
- **Paleta.** Tło prawie czarne: we wzorze `#050508`; Apple `#000/#161617/#1d1d1f`; Linear `#08090a` (poziom wyżej `#0f1011/#141516`, tekst `#f7f8f8`, obrys `#ffffff14`). Tekst: główny biały `#f5f5f7`, drugi `rgba(235,235,245,.6)`, nadtytuł `#a7a7b4` (rozstrzelenie +6 px); nazwa produktu z poziomym gradientem biały → jasny fiolet → jasny błękit. Akcent klipu: `#3d6bff` (`data.accent`).
- **Kroje.** Inter (najbliższy otwarty odpowiednik SF Pro; używa go Linear). Tytuły 600; **duże litery ze ściśniętym rozstrzeleniem −0,02 do −0,03 em** (Apple 96 px −0,015 em, Linear 64 px −0,022 em, OpenAI 64 px −0,03 em). Chińskie PuHui-Medium/PuHui-Bold z klipu → w Jarvie Inter 500/700, więc cały tekst idzie Interem.
- **Kompozycja.** Jeden punkt uwagi, środek, symetria; trzy karty po 480 px szerokości, odstęp 52 px; wielka liczba zajmuje ponad 55% szerokości kadru. Kształty: zaokrąglone prostokąty, kapsuły, cienkie ikony liniowe o okrągłych końcach (w duchu SF Symbols, `UI.icon`).
- **Liczenie.** Od 0,25 s po wylądowaniu karty przez 0,9 s, `MO.expoOut` (domyślna krzywa CountUp.js): ostatnia cyfra dochodzi powoli. **Ta sama liczba liczy się raz** (po rozwinięciu na pełny ekran zostaje ta sama wartość, bez liczenia od 0). Cyfry o stałej szerokości (`TY.tabular`; canvas nie włączy `tnum`, bez tego cyfry drgają).
- **Odblask.** Jasny pas pod kątem −20°, szerokości 110–140 px, przelatuje w 0,8–0,9 s; na tekście w trybie `source-atop` (świeci tylko na literach), na kartach `lighter`; postęp liczony z pozycji każdej karty na ekranie, więc trzy karty przecina jeden i ten sam odblask.
- **Przejścia (5).**
  1. **`blurPush` (rozmyte pchnięcie):** stary obraz cofa się do 0,92 z rozmyciem 24 px i gaśnie, nowy z 1,06 w rozmyciu ląduje ostro na 1,0; 0,55 s, `ease`. **Pod spodem leży powiększony 1,08× i mocno rozmyty (30 px) stary obraz**, inaczej przy zmniejszeniu widać czarne krawędzie.
  2. **`expandRect` (rozwinięcie wspólnej karty):** wybrana karta rośnie do 1,06, boczne cofają się i ciemnieją do 45%, potem karta rozwija się ze swojego prostokąta na pełny ekran, zaokrąglenie 38 → 0, sprężyna d = 0,55, bounce 0. Nowy obraz od pierwszej klatki leży w karcie **nieprzezroczyście** (karta jest półprzezroczysta: każde przenikanie pokaże dwie warstwy tekstu). Wybrana karta przestaje pływać przed rozwinięciem, żeby start był z nieruchomego prostokąta.
  3. **Cięcie dopasowane:** ten sam obiekt w tym samym miejscu przed i po (nazwa produktu → miejsce tytułu karty).
  4. **Maska albo cięcie odblaskiem:** obraz zmienia się za przelatującym pasem światła.
  5. **Załamanie zamiast przenikania** (Liquid Glass): element znika przez zmianę rozmycia i załamania, nie przez samo krycie (wyłanianie tekstu z rozmycia to ta sama myśl).
- **Zgranie z lektorem.** Rzeczownik zaczyna się wyłaniać 0,2–0,3 s przed wypowiedzeniem (wyłanianie trwa 0,7 s, w chwili słowa jest ostro). Liczba **staje** w chwili, gdy lektor ją wypowiada: start liczenia = chwila słowa − czas liczenia. Trzy karty wchodzą na „po pierwsze, po drugie, po trzecie”.
- **Ilość tekstu.** Tytuł: nazwa produktu albo bardzo krótkie hasło (oryginał: do 6 znaków chińskich). Podtytuł: jedno krótkie zdanie (oryginał: do 16 znaków). Karta: krótki tytuł, jedna linia opisu, jedna wielka liczba z jednostką (jednostka o stopień mniejsza i szarsza).
- **Wydajność.** Plamy (1/4 rozmiaru) i rozmyta kopia tła co klatkę: 40–60 ms na klatkę (qa z GPU), 8 s w 60 fps ok. 1 min; `blurPush` do ok. 137 ms na klatkę (dwa pełne rozmycia). Na serwerze bez GPU zmierz najpierw jedną klatkę. Render deterministyczny.
- **W klipie.** Tytuł: nadtytuł od `at` (0,7 s), tytuł od `at`+0,15 s (1,0 s, rozmycie 26 px, przesunięcie 40 px), kolejne linie co 0,12 s, podtytuł od `at`+0,5 s (0,9 s). Gdy wchodzi pierwszy ekran z kartami: w poziomie tytuł cofa się (0,92, rozmycie 20 px) i gaśnie; w pionie kurczy się do nagłówka (≈68 px) u góry. Karta: sprężyna 0,7 s, bounce 0,15, z 170 px niżej, obrót −0,45 rad → 0, skala 0,9 → 1; pływa 5 px z okresem 3,6 s; odblask 0,4–1,2 s po wejściu. Nowa karta obok: stare przesuwają się sprężyną 0,7 s, bounce 0,12. Ekran schodzi w lewo i w tył w 0,65 s, gdy zaczyna się następny (przed ekranem liczby w 0,45 s).

## Cue w spec
`data` całego spec: `eyebrow` (mały tekst nad tytułem), `title`, `subtitle`, `accent` (kolor akcentu, domyślnie `#3d6bff`). Każdy cue ma `at` (s, klatka, w której element pierwszy raz widać) albo nasze `slowo` (+ `nth`, `offset`); reszta w `kontrakt-spec.md`. `dur` nie jest czytane. Treść tylko między `safe.top` a H − `safe.bottom`; w pionie karty rosną na wolną wysokość. Przy `--alfa` nie ma plam, karty dostają ciemny podkład, tekst cień.

| kind | pola | co robi | przykład |
|---|---|---|---|
| `title` | `text`/`sub` zastępują `data.title`/`data.subtitle`; `data.eyebrow` (w cue albo w spec) | Od `at` nadtytuł, tytuł i podtytuł wyłaniają się z rozmycia. Za długi tytuł: najpierw mniejszy w jednej linii (do 0,55×), potem dwie linie. Przy pierwszym ekranie kart: w poziomie cofa się i znika, w pionie zostaje jako nagłówek u góry. | `{"at":0,"kind":"title"}` |
| `card` / `step` / `image` (to samo) | `text` tytuł karty, `sub` opis, `image` zrzut (względem spec); `data.step` numer kroku (domyślnie 01, 02… w kolejności); bez zrzutu: `data.icon` (`wave memory agent clock phone layers chart code check play bolt lock`; bez ikony numer kroku), `data.value/prefix/suffix/decimals/label` (liczba na karcie) | Od `at` karta wjeżdża sprężyną z dołu z obrotem 3D i przelotem odblasku. **Ze zrzutem:** jedna karta na ekran, zrzut proporcjonalnie (contain, bez kadrowania); zrzut pionowy w poziomym filmie = tekst z lewej, zrzut z prawej na całą wysokość karty. **Bez zrzutu:** karta funkcji; kolejne (najwyżej 3) stają obok siebie na jednym ekranie, starsze ustępują miejsca (w pionie jedna pod drugą). Liczba na karcie liczy od 0,35 s po wejściu przez 0,9 s; `data.label` pod liczbą. | `{"at":2,"kind":"card","text":"Obraz z jednego zdania","sub":"Bez pisania promptów","data":{"icon":"bolt"}}` |
| `highlight` | `data.rect=[x,y,w,h]` (0..1 względem zrzutu), `text` opcjonalna etykieta | Ramka w kolorze akcentu wokół fragmentu bieżącego zrzutu (sprężyna 0,45 s, bounce 0,25, pulsująca poświata), reszta zrzutu przyciemniona o 38%, w ramce przelatuje odblask; etykieta w kapsule pod ramką (albo nad, gdy brak miejsca). Działa tylko na karcie ze zrzutem i tylko gdy `at` wypada, zanim wejdzie następna karta albo liczba. | `{"at":5,"kind":"highlight","data":{"rect":[0.6,0.2,0.2,0.1]},"text":"Tutaj"}` |
| `number` | jak w `kontrakt-spec.md`: `data.value`, `prefix`, `suffix`, `decimals` (domyślnie 0), `label`; opis w `text` albo `sub` | Osobny ekran z wielką liczbą (do 88% szerokości). Liczy od `at`−0,9 s, staje w `at`; poprzedni ekran zaczyna schodzić w `at`−0,9 s i nie nakłada się na karty. `data.label` nad liczbą, opis pod nią. | `{"at":4,"kind":"number","text":"Aktywni użytkownicy co miesiąc","data":{"value":1.2,"decimals":1,"suffix":" mln"}}` |

## Minimalny spec (po polsku)
```json
{"grammar":"t2_keynote_ui","duration":6,"data":{"title":"Trzy nowe funkcje"},"cues":[
  {"at":0,"kind":"title"},
  {"at":1.8,"kind":"card","text":"Dyktowanie","sub":"Mówisz, a tekst się pisze","data":{"icon":"wave"}},
  {"at":2.6,"kind":"card","text":"Pamięć","sub":"Pamięta, co mówiłeś ostatnio","data":{"icon":"memory"}},
  {"at":3.4,"kind":"card","text":"Automatyzacja","sub":"Klika za ciebie resztę","data":{"icon":"agent"}}]}
```
Samouczek na zrzutach, przypięty do słów lektora (karta wyłania się 0,25 s przed słowem, liczba staje na słowie):
```json
{"grammar":"t2_keynote_ui","duration":10,"data":{"eyebrow":"NOWOŚĆ","title":"Rezerwacja w trzech krokach"},"cues":[
  {"at":0,"kind":"title"},
  {"slowo":"kalendarz","offset":-0.25,"kind":"card","text":"Otwórz kalendarz","sub":"Zakładka Wizyty","image":"zrzuty/kalendarz.png"},
  {"slowo":"godzinę","kind":"highlight","data":{"rect":[0.648,0.245,0.104,0.105]},"text":"Wolne terminy"},
  {"slowo":"trzydzieści","kind":"number","text":"Tyle trwa rezerwacja","data":{"value":30,"suffix":" s"}}]}
```

## Pułapki
- **Szkło bez niczego za nim.** Matowe szkło rozmywa tylko to, co leży pod nim; na gładkiej ciemnej plamie „szkło” to szary prostokąt. Najpierw kolorowe, pofalowane plamy, potem rozmycie tła w miejscu karty na ekranie.
- **Za sprężyście i za dużo ruchu.** bounce domyślnie 0, przy wejściu najwyżej 0,15–0,3; powyżej 0,4 od razu tanio. Naraz rusza się jedna grupa elementów.
- **Duży tekst bez ściśnięcia i brudne plamy.** Od 64 px rozstrzelenie −0,015 do −0,03 em. Każda plama ma swój kolor (screen + duże rozmycie); uśrednienie kolorów liniowo daje szaro-fioletowe błoto.
- **Czarne krawędzie w przejściu** (`blurPush`, `expandRect`): pod spodem musi leżeć powiększona 1,08× i rozmyta (30 px) kopia starego obrazu.
- **Dwie warstwy tekstu i liczenie od nowa po rozwinięciu karty.** Nowy obraz w karcie od pierwszej klatki nieprzezroczysty; ta sama liczba w tym samym zapisie (we wzorze najpierw „1 mln” na karcie, a na pełnym ekranie „1 000 000” liczone od 0 – błąd). Liczenie, które w jednej klatce przeskakuje z 999 023 na 1 000 000 i ściska jednostkę: mierz szerokość liczby, jednostki i odstępu osobno.
- **Plansza końcowa za krótko i poza strefą bezpieczną.** We wzorze widoczna 0,4 s i za nisko; poprawka: wyłanianie 1,2–1,8 s, postój 0,6 s, wyżej.
- **Rozmycie wciąga przezroczyste piksele spoza płótna.** Rysowane do bufora, którego nie czyścisz, kumuluje się klatka po klatce i render przestaje być deterministyczny (klip co klatkę czyści bufor tła, inaczej ta sama chwila różni się o 1 poziom koloru). We własnej stronie: czyść bufory, pod rozmycie podkładaj nierozmyty oryginał.
- **„Martwy” obraz w pomiarze.** Wolny dryf plam i najazd 4,5% zmieniają mniej pikseli niż próg pomiaru (we wzorze 35% „stojących” par klatek, choć w odstępie 1 s 26,8% pikseli zmienia się o ponad 12 poziomów). Zanim uznasz ujęcie za zamrożone, porównaj klatki odległe o 1 s.
- **Zrzuty.** Zawsze proporcjonalnie (contain), bez ucinania kluczowego UI. `rect` na oko myli się o 20–30%: najpierw `--klatki`.
- **Zły nastrój do tematu.** Ta gramatyka brzmi jak dobra wiadomość; złe wieści i powagę opowiadaj inną.

## Kontrola
- Czy na każdym ekranie jest jedna rzecz i bohater (nazwa, liczba albo karta), a po gęstym fragmencie oddech?
- Czy rzeczownik wyłania się 0,2–0,3 s przed słowem, a liczba staje dokładnie na słowie, policzona raz i w polskim zapisie (przecinek dziesiętny, spacja tysięcy)?
- Czy sprężyny mają bounce ≤ 0,15–0,3, a przejścia są bez czarnych krawędzi i podwójnego tekstu?
- Czy duży tekst ma ściśnięte rozstrzelenie, a plamy są kolorowe, nie szare?
- Czy zrzuty są całe, a ramka `highlight` obejmuje właściwy fragment (stopklatki)?
