# Zasady rysownika (silnikjava, docs/ZASADY.md)

Prompt źródłowy autora silnika dla każdego, kto pisze scenę (`scena.js`). Rozdziały 1 do 7 to treść autora z commitu
`f63c094` (zakresy liczb zapisane słowem „do”, odnośniki jako nazwy plików; `tests/test_silnikjava.py` pilnuje
zgodności po podbiciu wersji), rozdział 8 to procedura u nas. Reguły oznaczone **[lint]** sprawdza
`rysowany.py sprawdz`, więc złamanie ich to błąd, a nie kwestia gustu.

Wyobraź sobie jednego rysownika z jedną ręką przy tablicy. Wszystko, co widz
zobaczy, ten rysownik musi fizycznie zrobić, po kolei i w ludzkim tempie.
A zanim zacznie, wie już, jak każda rzecz ma wyglądać na końcu.

## 1. Fizyka ręki

1. **[lint] Nic nie pojawia się samo.** Każdy ślad robi ręka z narzędziem:
   ołówkiem albo kredką w kolorze kreski, zakreślaczem albo gąbką (w motywie
   kredą, pędzlem, markerem…). Wyjątki trzeba nazwać: `ambient: true` dla
   animacji już narysowanego elementu, `magic: true` dla świadomego efektu bez
   ręki.
2. **[lint] Jedna ręka.** Nie rysuj dwóch rzeczy naraz. Każdy krok zaczyna się,
   gdy ręka dojedzie, a narzędzie zmienia się w powietrzu.
3. **[lint] Ludzkie tempo.** Ręka po kartce ma najwyżej ~3200 px/s, w powietrzu
   4500 px/s, a pismo ma własne tempo. Nie skracaj kroków na siłę (`dur`).
   Silnik sam wydłuży za krótki krok, a lint zgłosi za szybkie pismo.
   **[lint, ostrzeżenie]** Ręka porusza się płynnie: nie przeskakuje w jednej
   klatce (30 kl./s) o więcej niż 70 px. Długie przeloty skracaj kolejnością
   rysowania (`chain` dla kresek bez kierunku), a nie przyspieszaniem.

## 2. Kompletność obiektu (najważniejsza reguła kolejności)

4. **[lint] Obiekt rysujesz w całości, zanim zaczniesz następny.** Jeśli
   wiesz, że słońce będzie żółte, malujesz je **zaraz po obrysie**, a nie po
   narysowaniu morza i pary. Kolejność wewnątrz obiektu:

   **kontur → kolor → detale wewnątrz → podpis**

   Dopiero potem rysujesz następny obiekt. Lint zgłasza „obiekt przerwany”,
   gdy między konturem a kolorem tego samego obiektu (w dowolnej kolejności)
   ręka narysowała coś poza nim.
5. **Zaplanuj obiekt, zanim go narysujesz.** Dla każdego obiektu ustal od razu:
   kształt, kolor wypełnienia (albo „bez koloru”), detale, podpis i słowo
   lektora, na które się pojawia. W kodzie najlepiej jedna funkcja na obiekt
   (np. `sun()` rysuje obrys i zaraz kolor). Wtedy nie da się go rozdzielić.
6. **Zaznaczenia to nowe obiekty.** Zakreślenie, kółko wokół czegoś czy
   strzałka „patrz tutaj” rysuje się po tym, jak cel jest gotowy, i nie
   łamie reguły 4.
7. **Świadomy powrót do obiektu tylko z powodu fabularnego** (np. kawa nalewa
   się do filiżanki „po trzech minutach”). Oznacz go `revisit: true`
   i komentarzem, dlaczego. Na pewno nie po to, żeby zdążyć z lektorem.
   Wtedy zmień kolejność albo tekst (reguła 12).

## 3. Kolejność w kadrze

8. Pierwszy plan rysuj najpierw: linie tła chowają się wtedy za nim i nie
   trzeba niczego wymazywać. Nie rysuj linii, które byłyby zakryte.
9. Strzałka pojawia się, gdy istnieje jej początek. Cel rysuje się w tym samym
   albo następnym zdaniu, nigdy „strzałka w pustkę” na koniec.
10. Kreskę konstrukcyjną (oś, linia podłoża, ramka) rysuj przed tym, co na
    niej stoi.

## 4. Lektor i tempo

11. **Słowo-kotwica (`cue`) przy obiekcie, który lektor nazywa.** Ręka dotyka
    kartki ~0,3 s przed słowem. Kotwica należy do **pierwszego** kroku obiektu
    (konturu), a nie do koloru czy podpisu.
12. **[lint, ostrzeżenie] Rysunek i głos idą razem.** Gdy rysunek jest dłuższy
    niż zdanie, **dopisz lektorowi kilka naturalnych słów** albo przesuń część
    rysunku do następnego zdania. Nie przyspieszaj ręki i nie łam reguły 4.
    Film ma być bez ostrzeżeń o ciszy i spóźnionych kotwicach.
13. **[lint, ostrzeżenie] Coś dzieje się cały czas.** Widz nie może patrzeć
    na stojący kadr, a już na pewno nie na początku filmu. W pierwszych
    sekundach (do 6 s) ręka rysuje bez przerwy: przestój dłuższy niż 1 s to
    ostrzeżenie. Później dopuszczalny jest krótki oddech (np. po dużym
    rysunku albo gdy lektor coś dopowiada), ale najwyżej 3 s. Gdy lektor mówi,
    a ręka nie ma nic do rysowania:
    * przesuń kotwicę następnego obiektu na **pierwsze słowo** zdania,
    * dorysuj to, o czym lektor właśnie mówi (data, znak zapytania, ludzie
      na rynku, podkreślenie tytułu, podpis części),
    * dopiero na końcu skróć tekst lektora.

    Przelot ręki między krokami wlicza się do przestoju: ruch ręki w powietrzu
    to za mało, na kartce musi przybywać rysunku.
14. Na tablicy tylko słowa-klucze. Pełne zdania są w głosie i w napisach.

## 5. Wygląd

15. Kolory tylko z nazw palety (`ink`, `pen`, `teal`, `sky`, `ochre`, `coral`,
    `plum`, `inkSoft`, `white`). Wtedy ta sama scena działa w każdym motywie
    (STYLE.md).
16. Wielokąty „z linijki” (trójkąt, kwadrat, schemat) rysuj przez `polyline`
    (ostre rogi), a nie przez `polygon` (zaokrąglony szkic).
17. Treść nie dotyka krawędzi kadru (margines ≥ 60 px) i wypełnia kadr
    równo, bez pustej połowy.

## 6. Rolka 9:16

18. **[lint, ostrzeżenie] Rysuj tylko w strefie bezpiecznej** (720×1280:
    x 36 do 640, y 150 do 900). Wyżej, niżej i przy prawej krawędzi interfejs
    aplikacji zasłoni rysunek. Pod rysunkiem są napisy.
19. Pierwsze zdanie to hak: pytanie albo problem widza, a nie „dzisiaj
    opowiem o…”. Coś musi się rysować od pierwszej sekundy.
20. Elementy duże i proste: tytuł ≥ 60 px, podpisy ≥ 36 px, najwyżej 3 do 4
    obiekty w kadrze. Układ pionowy (z góry na dół), a nie w rzędzie.

## 7. Bryły w izometrii (szkice przedmiotów)

Przedmioty w 3D (laptop, router, szafa z serwerami, sejf) rysuj przez
`src/iso.js`: `isoCamera`, `solid`, `cylinder`, `visible`. Zasady wzięte
z Hairline (MIT, Lucas Marques), przełożone na rękę rysownika:

21. **Mniej kresek.** Bryła to jej sylwetka i jedna krawędź górnej ścianki.
    Bez pionowych narożników i bez dwunastu krawędzi pudełka. Rogi zawsze
    zaokrąglone. Detale tylko takie, jakie przedmiot naprawdę ma (szczeliny,
    diody, ekran), cienko.
22. **Mocno na zewnątrz, blado w środku.** Sylwetka kolorem `ink`, krawędź
    i detale kolorem `inkSoft` i cieńszą kreską. Ta hierarchia to większość
    wrażenia porządnego rysunku.
23. **Nie rysuj tego, czego nie widać.** Najpierw bliższa bryła, potem dalsza,
    przycięta do widocznych kawałków: `visible(ścieżka, [sylwetki bliższych])`
    i `sb.strokes(...)`. Ręka podnosi się nad zasłoniętym fragmentem
    (reguła 8). Linie pomocnicze (przerywana droga na ziemi) też przycinasz.
24. **Jeden akcent.** Kolor `pen` znaczy w całym filmie jedną rzecz, tę,
    której losy śledzi lektor (np. wiadomość: dymek → paczki → złożona
    całość). Reszta jest w `ink` i `inkSoft`. Akcent to kreska, nie wielka
    plama koloru. Rysunku nie da się przemalować, więc nie wyróżniaj
    pomarańczem rzeczy, która nie jest tym wątkiem.

## 8. Procedura u nas (zawsze w tej kolejności)

```bash
N="@@REPO_DIR@@/profiles/jarvo-wideo/scripts"; F=out/wideo/src/<film>
@@PY@@ "$N/rysowany.py" sprawdz $F                 # 0 błędów i 0 uwag lintu, audyt bez skoków ręki i w budżecie klatki
@@PY@@ "$N/html_wideo.py" klatki $F/index.html --preset jarvo --czasy 1,2,3,4,6,8,10 --arkusz $F/klatki.jpg
@@PY@@ "$N/rysowany.py" film $F -o out/wideo/<film>.mp4 --arkusz $F/arkusz.jpg   # dopiero teraz film
```

Czasy kroków (start, długość, zdanie, kotwica) zapisuje `sprawdz` w `$F/sprawdzenie.json` (`kroki`). Na arkuszu
klatek sprawdź szczególnie: czy każdy obiekt jest skończony, zanim ręka przejdzie dalej; czy nic nie nachodzi na
podpisy; czy kompozycja jest równa; czy polskie litery wyszły krojem stylu.
