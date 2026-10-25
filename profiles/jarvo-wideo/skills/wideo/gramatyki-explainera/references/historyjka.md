# Historyjka z rysowaną postacią (`historyjka`, w kodzie `y4_storytime`)

Narracja gra główną rolę, a obraz jest do niej dobranym „memem”: postać przeskakuje między pozami w 0,1 s i zastyga, a puenta to cięcie na zbliżenie reakcji, w którym postać milknie. Wzór: `@@PY@@ "$HERMES_HOME/scripts/gramatyka.py" wzor historyjka --arkusz out/wideo/wzor-historyjka.jpg`; start: `@@PY@@ "$HERMES_HOME/scripts/gramatyka.py" szablon historyjka [--format 9:16] -o out/wideo/src/klip-historyjka/spec.json`.

Kod: klip `$HUASHU/scripts/engine/clips/y4_storytime.js`, przykład `$HUASHU/scripts/engine/examples/y4_storytime.json` (zdanie, `insert` z licznikiem 3000, `react`, zdanie z `pose: point`, znak zapytania), postać `TOON.bean` w `$HUASHU/scripts/engine/lib/toon.js`, film pokazowy `$HUASHU/scripts/engine/demos/y4_storytime/` (MIT). Film pokazowy: 8,75 s, 60 fps, 5 ujęć. **Postać jest u nas neutralna:** bez kapelusza i okularów autora oryginału, kolory postaci z marki klienta. Ruch ust idzie z obwiedni lektora (`window.VO_ENV`: `gramatyka.py` liczy ją sama z pliku lektora z `os_czasu.json`, od `od` przez `duration`, w klatkażu spec) albo, gdy lektora nie ma, z czasu wyliczonego z tekstu. Kolory postaci: `"postac": {"skora", "linia", "wlosy", "koszulka", "spodnie", "buty"}` w spec (marka klienta).
Potok: `szablon` → polskie teksty i `slowo` → `gramatyka.py sprawdz` → `gramatyka.py render … --klatki 0.5,2,4` → pełny `render`.

Wzorce gatunku: TheOdd1sOut, Jaiden Animations, Domics.

## Kiedy
- Pierwsza osoba: przygoda, wpadka, „mój pierwszy raz…”. Narracja ma początek, zwrot i puentę, przy której da się zrobić pauzę.
- Widz przychodzi dla „tej osoby”: postać twórcy wraca w każdym odcinku i rozpoznaje się ją po charakterze, nie po jakości rysunku (badanie gatunku Pappisa: awatary różnią się często tylko fryzurą).
- Mały budżet i stały rytm publikacji: jedna postać, pięć–sześć póz i trzy usta wystarczą na cały odcinek.
- Przykłady: historia założyciela w filmie SaaS („jak poprosiłem AI o literówkę…”), wpadka z wdrożenia w kampanii employer brandingu, rolka 9:16 na 20–40 s z puentą, felieton z własną postacią marki.

## Nie do
- Gęste instrukcje i dane: widz patrzy na postać i czeka na żart, liczb nie zapamięta. Użyj `kinetyczna` albo `wykresy`.
- Treść bez „ja” (wiadomości branżowe, porównanie produktów): postać nie ma stanowiska do zagrania i zostaje ruszającą ustami naklejką. Użyj `vox` albo `prezentacja`.
- Narracja bez humoru i bez pauz: ten styl wzmacnia narrację, nie ratuje jej.

## Gramatyka (z pomiarów)
Źródła: dwa filmy mierzone klatka po klatce (kopie 480p, bez 10 s na początku i końcu, różnica klatek w skali szarości 160×90), wywiad Toon Boom z zespołem serialu „Oddballs”, praca Pappisa o gatunku.

- **Długość ujęć (pomiar).**

  | | TheOdd1sOut (30 fps, 475 s) | Jaiden Animations (24 fps, 902 s) |
  |---|---|---|
  | średnia długość ujęcia (ASL) | **2,43 s** (mediana 1,87 s, kwartyle 1,03–3,07 s) | **5,73 s** (mediana 3,21 s, kwartyle 1,67–6,67 s) |
  | całkiem nieruchome sąsiednie klatki | **70,7%** | 51,2% |
  | odcinek bezruchu | mediana **0,40 s**, p75 0,70 s | mediana 0,08 s (pauza „na dwójkach”) |
  | odcinek ruchu | mediana **100 ms** (3 klatki) | mediana 42 ms (1 klatka) |

  TheOdd1sOut: szybki przeskok (0,1 s) → postój (0,4–0,7 s) → przeskok; 70% czasu obraz stoi. Jaiden: ciągły ruch na dwójkach (12 rysunków/s), dłuższe ujęcia. Animator „Oddballs”: „pose-to-pose, prawie bez animacji, w zasadzie przełączanie obrazków”; przy przeróbce na serial najtrudniej było zachować tę zadziorność i nie zrobić tego „za miękko, za wolno”. Gramatyka bierze środek: przeskoki póz jak TheOdd1sOut, oddech i usta jak Jaiden.
- **Dwa klatkaże.** Cały ruch postaci skokowo 24 fps (`MO.step(t, 24)`, domyślne we Flashu), kamera płynnie (we wzorze 60 fps).
- **Zmiana pozy.** Ręce do celu `MO.expoOut` w **0,10 s** (2–3 klatki przy 24 fps). W chwili zmiany ciało ściska się pionowo o 7% i odbija sprężyną z zachowaniem objętości: `MO.settle(dt, -0.07, 3.5, 9)`, stoi po ok. 0,35 s. Pozy (`TOON.POSES`): `rest`, `talk`, `point`, `type`, `shrug`, `stiff`; każda to tylko cele obu dłoni względem barków.
- **Usta.** Z obwiedni RMS lektora (`window.VO_ENV`, 60 fps): kształt zmienia się najwyżej co 1/12 s (na dwójkach), trzy usta: obwiednia < 0,06 zamknięte, < 0,22 półotwarte, wyżej otwarte (`TOON.mouth`). Bez obwiedni klip składa usta z czasu tekstu: ≈ 6,5 znaku/s od `at`, też na dwójkach. Przy otwartych ustach głowa opada o 0,015R × poziom ust (kiwanie przy mówieniu).
- **Życie w spoczynku.** Oddech: pionowo ±1,2%, okres 1,6 s. Mruganie: stały rozkład co 2,4–3,6 s, oczy zamknięte 2 klatki przy 24 fps (83 ms); „brak słów” to powolne mrugnięcie 3 klatki. Spojrzenie: źrenica przesuwa się o 0,09R w stronę rzeczy.
- **Kamera.** Wzór: plan średni powolny najazd +3,5% w 2,0 s; zbliżenie +6% w 1,2 s; plan ogólny 0,53→0,50 (quintOut); bliski 1,90→1,98; otwarcie 1,04→1,01 w 0,5 s expoOut zamiast nieruchomej pierwszej klatki. Klip: plan średni +3% (quintOut w 3 s), dryf 3 px; `react` to skok tej samej kamery do 1,9× z odbiciem sprężyny z ok. 2,2× (3 Hz, wygaszanie 11) i +3% w 1,5 s.
- **Wejścia i wyjścia.** Prawie nie ma animacji wejścia: postać stoi na miejscu i mówi od pierwszej klatki ujęcia. Wyskakują tylko rekwizyty i znaki (?, !, pot, liczby): `MO.backOut`, przestrzał 15–30%. „?” nad głową: przestrzał 30%, 0,26 s, potem kołysanie ±3°. Kropla potu: spływa po skroni 0,9 s (expoOut zmieszany z liniowym).
- **Przejścia.**
  1. Twarde cięcie (`cut`): zdecydowana większość, jedno zdanie lektora = jedno ujęcie, zmiana zdania = cięcie. Kontrast planów (zbliżenie → bardzo szeroki plan tego samego pokoju) robi żart.
  2. Cięcie-uderzenie na zbliżenie reakcji (`TRANSITIONS.smash`): nowy obraz od pierwszej klatki, z 1,22× sprężyną (freq 3, decay 11) do 1, przez 2 pierwsze klatki biały błysk 55%, niski dźwięk „dum”. Po zdaniu absurdalnym → twarz.
  3. Szarpnięcie kamery (`TRANSITIONS.whip`) w stronę tego, na co patrzy postać: `MO.expoInOut` 0,26 s, w środku 16 przesuniętych kopii jako poziome rozmycie, dźwięk „wziuu”. Do zmiany spojrzenia („otwieram komputer → ekran”).
  4. Skok bliżej: ta sama kamera, cięcie na ok. 2× bliższy plan, to samo tło. Do „powtórzył”, „zrozumiał”, zdania z puentą. Warunek: oba plany to ten sam świat, zmienia się tylko kamera; świat musi być większy niż najdalszy kadr, inaczej dryf pokazuje czarne brzegi.
  5. Przez ramię / subiektywnie: cięcie na to, co postać widzi (ekran, telefon, rozmówca), z tyłem głowy na pierwszym planie. Tył głowy nie jedzie z kamerą, tylko oddycha, więc powstaje paralaksa i obraz od razu ma głębię. Czarna sylwetka czyta się jak „inna osoba”: daj jej znaki rozpoznawcze tyłu głowy i obwódkę światła od ekranu.
- **Rytm.** Ujęcie idzie za zdaniem lektora, nie za muzyką. Wzór: 5 ujęć, średnio 1,75 s (2,0 / 2,4 / 1,2 / 1,65 / 1,5), w kwartylach TheOdd1sOut. Przejścia w oddechu między zdaniami; napis zmienia się w tej samej klatce co cięcie. Reakcja w ciszy między zdaniami: po zdaniu absurdalnym zostaw 0,8–1,5 s na twarz (wzór: 1,3 s bez słowa). Po puencie postój ≥ 0,9 s (wzór: „?” w 7,80 s, koniec 8,75 s).
- **Tekst w kadrze.** Natywne historyjki na YouTube nie wypalają napisów (są CC); w kadrze tylko to, co trzeba zobaczyć: tekst na ekranie, kluczowa liczba (wzór: „3000 wierszy” grubym krojem 230 px, `#FFCB6B`, przestrzał 23%). Liczba w kadrze, uderzenie dźwięku i drżenie ekranu (9 Hz, wygasa w 0,3 s) padają na tę samą sylabę lektora. Napisy wypalane: biały 50 px, czarny obrys 10 px, całe zdanie naraz, bez animacji (ruchome napisy walczą z postacią o uwagę).
- **Kompozycja.** Domyślnie plan średni (od pasa, głowa 25–35% wysokości kadru), postać z boku, druga strona dla tego, o czym mówi (komputer, rozmówca, przedmiot). Tło mówi tylko „gdzie”: ściana, stół, okno, 3–5 dużych plam koloru; białe albo jednolite tło też działa. Zbliżenie reakcji: twarz wypełnia kadr (promień głowy ≈ 1/3 wysokości kadru), tło jednolite z winietą. Żart często odwrotnie: cięcie na bardzo szeroki plan, postać mała i bezradna. Pokój w klipie: okno z wolno płynącymi chmurami, półka z książkami i roślina, stół z kubkiem i komputerem, na którego ekranie przewija się kod.
- **Paleta wzoru.** Skóra `#FFE2CC` (jasna, prawie biała), koszulka `#FFFFFF`, spodenki `#CDBB97`, linia postaci `#1B1B1F` (najciemniejsza w filmie); ściana / stół / podłoga `#DCE9EC` / `#E2C29B` / `#E8DCC8` (niskie nasycenie, wysoka jasność: tło zawsze „lżejsze” od postaci); linia tła `#5B6470` 3 px; pustka w zbliżeniu reakcji `#3D405B` + winieta radialna; usta / język / rumieniec `#6E2430` / `#F07B7B` / `rgba(255,140,120,.35)` (jedyny nasycony kolor w ustach, więc ich ruch widać). U nas kolory postaci bierzesz z marki, zasada zostaje: postać ciemniejsza i bardziej kontrastowa niż tło.
- **Grubość linii.** Linia postaci = promień głowy × 0,05 (co najmniej 4 px): plan średni R = 165 → 8 px, zbliżenie R = 360 → 12 px, plan ogólny R = 95 → 6 px; skaluje się z kamerą (jak we Flashu). Linia tła stała 3 px. **Linia postaci ≥ 2 × linia tła** – dlatego postać zawsze „wyskakuje” z tła.
- **Kształty.** Wszystko okrągłe i tępe. Głowa to lekko spłaszczone koło (szer. 1,0R × wys. 0,93R), ciało to fasolka (1,0R × 1,2R), cała postać 3,2R, głowa ok. 58% wysokości. Ręka to rurka z zaokrąglonymi końcami, bez łokcia i palców, dłoń to kółko. Kątów prostych nie ma, poza rekwizytami.
- **Mimika.** Głównie brwi: uniesione = zaskoczenie, uniesione wewnętrzne końce = żal, płaskie = brak słów. Usta: uśmiech, kreska, fala (niepokój), półotwarte, otwarte. Oczy: czarne kropki 0,075R z białym odblaskiem; „martwe oczy” w reakcji: kropka 0,035R bez odblasku.
- **Kroje.** Klip: dymek `PuHui-Bold` 62 px (pion 64 px, najwyżej 2 linie), napis w `insert` `PuHui-Black` 230 px (pion 200 px), `#FFCB6B`; znak nad głową `PuHui-Black`. W Jarvie nakładka `huashu_pl.js` podmienia je na Inter tej samej grubości (700 i 900).
- **Pomiar wzoru (qa).** 0 skoków obrazu po poprawkach, 2–11 ms na klatkę. Pary identycznych klatek 0–16% (oryginał TheOdd1sOut 70,7%): wzór jest bardziej „żywy”, bo bierze ciągły oddech od Jaiden. Próg qa „> 40% par identycznych = zacięcie” w tej gramatyce nie obowiązuje.

## Cue w spec
`data` całego spec: brak. Każdy cue ma `at` (s, klatka, w której element pierwszy raz widać) albo nasze `slowo` (+ `nth`, `offset`). `kind` spoza tabeli nie daje błędu i nic nie rysuje (tu nie ma `number` ani `image`). Cue z `at` > `duration` jest odrzucany z ostrzeżeniem. `dur` czytają tylko `react` i `insert`.

| kind | pola | co robi | przykład |
|---|---|---|---|
| `point` / `title` (to samo) | `text` = zdanie lektora (bez obwiedni wyznacza czas ruchu ust: znaki / 6,5 s), `sub` = krótki tekst w dymku (gdy brak, w dymku jest `text`), `data.pose`: `talk` / `point` / `shrug` / `type` (domyślnie na zmianę `talk` i `point`) | W `at` postać zmienia pozę (0,1 s), dymek wyskakuje (0,25 s) i zaczynają się usta. Dymek znika 0,6 s po końcu mówienia albo gdy zaczyna się następne zdanie; po `react` / `insert` wcześniejszy dymek nie wraca. | `{"at":0.1,"kind":"point","text":"Poprosiłem AI o poprawkę literówki","sub":"Tylko jedna literka!"}` |
| `highlight` | `data.mark` (domyślnie „？” pełnej szerokości; pisz `"?"` albo `"!"`) | Znak wyskakuje nad głową (0,26 s) i się kołysze, postać wzrusza ramionami (`shrug`) z zaniepokojoną miną. | `{"at":4,"kind":"highlight","data":{"mark":"!"}}` |
| `react` | `dur` (od `at`; domyślnie do następnego cue) | Skok do dużego zbliżenia twarzy: 1,9× z odbiciem, „martwe oczy”, kropla potu od +0,3 s, usta zamknięte, bez dymka. | `{"at":3,"kind":"react"}` |
| `insert` | `sub` = linijka, którą postać wpisuje (długa → do 3 linii), `text` = wielki napis, `data.hit` (sekundy **bezwzględne** od początku klipu; domyślnie `at + 1.3`, bez `sub` `at + 0.4`), `data.count` + `data.unit` (licznik w prawym górnym rogu staje na tej liczbie w chwili uderzenia; spację w `unit` wpisz sam), `data.app` (tytuł okna; domyślnie „AI助手”), `dur` (od `at`; domyślnie do następnego cue) | Zbliżenie ekranu komputera ze stołu, przez ramię: pisanie (ok. 14 znaków/s, najwyżej 0,9 s) → wysłanie (dymek robi się niebieski) → odpowiedź jak ściana kodu przewija się coraz szybciej → w `hit` (nie wcześniej niż 0,2 s po wysłaniu) wielki napis uderza, ekran drży 0,3 s, tył głowy odskakuje. | `{"at":2,"kind":"insert","sub":"Popraw literówkę w tytule","text":"40 zmienionych plików","data":{"hit":3.4,"app":"Asystent AI"}}` |

## Minimalny spec (po polsku)
Pierwszy cue jest przypięty do słowa „poprosiłem” w narracji: `gramatyka.py` liczy jego `at` z `os_czasu.json` (`film.py narracja`); `nth` (od 1) wybiera wystąpienie, `offset` przesuwa w sekundach. `data.hit` zostaje w sekundach bezwzględnych.

```json
{"grammar":"y4_storytime","duration":7,"cues":[
  {"slowo":"poprosiłem","kind":"point","text":"Poprosiłem AI o literówkę","sub":"Popraw jedną literkę!"},
  {"at":2,"kind":"insert","sub":"Popraw literówkę w tytule","text":"40 plików","data":{"hit":3.4,"app":"Asystent AI","count":40,"unit":" plików"}},
  {"at":4.6,"kind":"react"},
  {"at":5.9,"kind":"highlight","data":{"mark":"?"}}]}
```

## Pułapki
- **Robienie „pełnej animacji”, w której wszystko płynie.** Życie tego stylu to przeskok i postój: u TheOdd1sOut 70% klatek stoi. Ciągłe pływanie wygląda „za miękko, za wolno”. Zmiana pozy w 0,1 s i **naprawdę stój**; stały ruch tylko oddech, mruganie i drobiazgi w tle, najwyżej 1–2%.
- **Tło tak samo ciekawe jak postać.** Tło o stopień niżej w nasyceniu, kontraście i grubości linii (wzór: tło 3 px szare, postać 8 px czarna). Ruchliwe tło zabiera wzrok z twarzy i puenta ginie.
- **Reakcja bez ciszy.** Następne zdanie zaraz po absurdalnym zabija żart. `react` w ciszy narracji, co najmniej 0,8 s; kamera tylko bardzo wolno najeżdża, do tego 1–2 detale (pot, powolne mrugnięcie, opadająca brew).
- **Cięcie w środku zdania.** Szarpnięcie i cięcia w oddechu między zdaniami. Wzór najpierw ciął na pierwszych sylabach zdania; poprawka: koniec zdania 1,87 s → szarpnięcie 2,0 s → wylądowanie 2,26 s → nowe zdanie od 2,30 s.
- **Usta bez obwiedni w polskim tekście.** 6,5 znaku/s to tempo chińskich znaków; polskie zdanie ma ich znacznie więcej, więc bez obwiedni usta ruszają się dłużej niż lektor. Daj lektora (`os_czasu.json` obok spec albo katalog wyżej: `gramatyka.py` wstawi `window.VO_ENV`) albo skróć `text` tak, żeby znaki / 6,5 ≈ długość zdania w sekundach, a treść dymka wpisz w `sub`.
- **Chińskie wartości domyślne w kadrze.** Zawsze wpisz `data.app` po polsku (domyślnie „AI助手”) i `data.mark` (`"?"` albo `"!"`; domyślny „？” jest pełnej szerokości).
- **`data.hit` to sekundy bezwzględne,** nie względem `at`. Gdy `at` liczysz ze `slowo`, `hit` się z nim nie przesuwa: wpisz czas słowa z `os_czasu.json` (sylaba liczby) albo pomiń `hit` (domyślnie `at + 1.3`).
- **`safe` przesuwa tylko tekst** (dymki i wielki napis w `insert`). Postać, stół i twarz w `react` to grafika: w pionie wchodzą w pas napisów; napisy na ciele są czytelne, ale grafika się nie odsunie. Pas napisów: `safe.bottom` 700 w pionie 1080×1920, 250 w poziomie.
- **Klatki postaci liczone z bezwzględnej siatki 24 fps:** lądowanie cue może się różnić o 1 klatkę. Sprawdź na stopklatkach.
- **Tryb `--alfa`:** bez pokoju; postać i dymek rysują się normalnie, w `insert` tylko monitor i tył głowy.

## Kontrola
- Czy pozy zmieniają się w 0,1 s, a potem naprawdę stoją?
- Czy usta ruszają się tylko wtedy, gdy lektor mówi, i milkną w `react`?
- Czy po absurdalnym zdaniu jest ≥ 0,8 s ciszy na reakcję, a po puencie ≥ 0,9 s postoju?
- Czy cięcia padają w oddechu między zdaniami, a liczba w `insert` uderza na sylabę lektora?
- Czy postać jest neutralna (bez kapelusza i okularów, także tył głowy w `insert`), w kolorach marki, a w kadrze nie ma chińskich znaków?
