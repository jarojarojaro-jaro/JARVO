# Kontrakt spec klipu gramatyki

Klip = jedna gramatyka i jeden plik spec (JSON) → odcinek animacji o dokładnie zadanej długości, do wstawienia we fragment filmu z lektorem. Spec czyta ich `clip.js` (`$HUASHU/scripts/engine/clip.js`), więc klucze zostają w oryginale; piszemy go, sprawdzamy i renderujemy przez `gramatyka.py`. Które gramatyki do czego: `wybor.md`; pola `data` i tabela cue każdej gramatyki: jej karta.

## Polecenia
```bash
G=$HERMES_HOME/scripts/gramatyka.py
python3 $G szablon wykresy [--format 9:16] -o out/wideo/src/klip-wykres/spec.json     # szkielet spec po polsku
python3 $G sprawdz out/wideo/src/klip-wykres/spec.json                                 # przed każdym renderem
python3 $G render out/wideo/src/klip-wykres/spec.json --klatki 0.5,2,4        # stopklatki → klatki/spec-arkusz.jpg
python3 $G render out/wideo/src/klip-wykres/spec.json -o out/wideo/klip.mp4            # bez dźwięku, H.264 yuv420p
python3 $G render out/wideo/src/klip-wykres/spec.json -o out/wideo/klip.mov --alfa     # ProRes 4444 z przezroczystym tłem
python3 $G pomiar out/wideo/src/klip-wykres/spec.json [--platforma tiktok]    # html_wideo.py pomiar strony klipu
python3 $G strona out/wideo/src/klip-wykres/spec.json                          # sama strona spec.html (podgląd, własny render)
```
Kolejność: `szablon` → teksty po polsku i `slowo` → `sprawdz` → `render --klatki` (vision, poprawki) → `pomiar` → pełny `render` → kontrola (`qa_wideo.py`, skill `kontrola-wideo`).

**Jeden klip = jeden katalog** (`out/wideo/src/klip-<nazwa>/spec.json`, obrazy obok): strona klipu (`spec.html`) powstaje obok spec, pomiar (`pomiar.json`) i jego odcisk są per katalog, a `fakty.json` i `os_czasu.json` są w nim albo katalog wyżej (`out/wideo/src/`). Przykłady z ich repo: `$HUASHU/scripts/engine/examples/<id>.json` (teksty chińskie, materiały w `examples/assets/`).

## Zasady renderu
- **Długość dokładnie `duration`:** liczba klatek = round(duration × fps), klatka i to czas i / fps. Klip idzie potem do montażu (`projekt.py`, `film.py`), który koduje całość od nowa.
- **Rozmiar i fps ze spec**, domyślnie 1920×1080 przy 30 fps. Pion: `"width": 1080, "height": 1920` (każda gramatyka ma osobny układ pionowy; `szablon --format 9:16`).
- **Obrazy względem pliku spec** (albo ścieżka bezwzględna, `data:`, `http(s):`). Strona klipu leży obok spec, a serwer renderu podaje tylko ten katalog: obraz spoza niego `sprawdz` odrzuca (skopiuj go obok), obraz z sieci tylko ostrzega (render jest offline).
- **Błąd strony = brak filmu.** Błąd w pliku gramatyki, brakujący obraz, brak `grammar`, `duration` ≤ 0, nieznana gramatyka → render kończy się kodem ≠ 0 i nic nie zapisuje.
- **Brakujące glify tylko ostrzegają** (zastępczy krój systemu, na innej maszynie inny wygląd). Klip sprawdza wyłącznie znaki CJK: polskie ogonki sprawdzaj na stopklatkach.
- **`alpha: true` = bez tła** (`--alfa` ustawia to sam). Znika tylko warstwa tła, cienie elementów zostają: papier `vox` i szklane karty `prezentacja` na przezroczystym tle czytają się jak karty unoszące się nad obrazem; `wykresy` (czarne na białym) dostają białą poświatę wokół tekstu, czytelną na ciemnym obrazie; `3b1b` – biały tekst z ciemną obwódką. Pasów `safe.fill` w trybie alfa się nie maluje.

## Spec
Schemat (komentarze tylko tutaj; w pliku JSON ich nie pisz). Dodatki Jarva w spec: `od` (gdzie klip zaczyna się na osi lektora: sekundy albo chwila `u3`, `r2`, `u3.mowa`; domyślnie 0), `do` (koniec, zamiast `duration`), `os` (ścieżka `os_czasu.json`), `postac` (kolory postaci `historyjka`); `grammar` może być nazwą po polsku (`wykresy`). `gramatyka.py` zdejmuje je przed stroną.
```js
{
  "grammar": "t3_finance_chart",          // id z kodu (tabela niżej), bo clip.js ładuje clips/<grammar>.js
  "duration": 7, "fps": 30, "width": 1920, "height": 1080,
  "safe": { "top": 140, "bottom": 700 },     // opcjonalnie: krawędzie do ominięcia (px), niżej
  "alpha": false,                          // opcjonalnie: true = bez tła
  "data": { },                             // parametry gramatyki (karta); nieznane pola są ignorowane
  "cues": [ { "at": 1.2, "kind": "bar", "text": "…", "sub": "…", "data": { }, "image": "zrzut.png", "dur": 1.0 } ]
}
```

| Nazwa w Jarvie | `grammar` (id z kodu) | `data` całego spec | `kind` |
|---|---|---|---|
| `kurzgesagt` | `y1_kurzgesagt` | `center`, `flow` | `title`, `point`, `highlight`, `enter` |
| `vox` | `y2_vox` | — | `image` (= `clip`), `title`, `point`, `highlight` |
| `tablica` | `y3_whiteboard` | — | `title`, `point`, `draw`, `image`, `highlight` |
| `historyjka` | `y4_storytime` | — | `point` (= `title`), `highlight`, `react`, `insert` |
| `kinetyczna` | `y5_kinetic_type` | `palette` | `title` / `point`, `number`, `highlight` |
| `3b1b` | `t1_3b1b` | — | `title`, `equation`, `point`, `line`, `highlight` |
| `prezentacja` | `t2_keynote_ui` | `eyebrow`, `title`, `subtitle`, `accent` | `title`, `card` (= `step` = `image`), `highlight`, `number` |
| `wykresy` | `t3_finance_chart` | `title`, `unit`, `source`, `badge`, `chart`, `series`, `decimals`, `prefix`, `suffix`, `highlight`, `colors`, `upDown`, `xAxis` | `title`, `bar` / `line` / `candle`, `highlight`, `number` |

`prowadzacy` (`y6_presenter_explainer`) nie ma klipu: `prowadzacy.md`.

## Wspólne pola cue
Które pola czyta dana gramatyka – tabela w jej karcie.

| Pole | Znaczenie |
|---|---|
| `at` | Sekundy. **„Klatka odsłonięcia”:** element jest pierwszy raz widoczny w klatce t = `at` (wewnętrzny czas animacji liczy się od klatki przed `at`). Wyjątek: w `number` `at` to chwila, gdy liczba **staje**. Kolejność cue w pliku dowolna (klip sortuje). Cue z `at` > `duration` daje ostrzeżenie i jest odrzucany (niewidoczny, nie zajmuje miejsca w układzie). Wymagane, chyba że cue ma `slowo`. |
| `slowo` | Dodatek Jarva: słowo lektora zamiast `at`. `gramatyka.py` liczy z niego `at` z osi lektora (`os_czasu.json` z `film.py narracja`): `at` = początek słowa + `offset` − `od`. Szuka tylko w oknie klipu (`od` … `od` + `duration`). Fraza = kilka słów po spacji; `*` na końcu = początek słowa (odmiana: `rekord*`). Nie ma słowa → błąd z listą słów w oknie. |
| `nth` | Dodatek Jarva: które wystąpienie `slowo` w oknie klipu, od 1 (bez `nth` – pierwsze). |
| `offset` | Dodatek Jarva: przesunięcie w sekundach względem słowa (np. `-0.25`). |
| `kind` | Wymagane. **Rodzaj, którego gramatyka nie zna, nie daje błędu i nic nie rysuje** – pisz według tabeli w karcie. |
| `text` | Tekst główny: tytuł, teza, etykieta, oryginał wypowiedzi w dymku, wielki napis we wstawce. |
| `sub` | Tekst pomocniczy: opis karty w `prezentacja`, zdanie pomocnicze w `kinetyczna`, krótkie zdanie widoczne w dymku `historyjka`, linijka pisana na komputerze we wstawce `historyjka`. |
| `image` | Ścieżka obrazu względem pliku spec (albo bezwzględna, `data:`, `http(s):`). Brak pliku → render odmawia. |
| `data` | Parametry tego cue (`index`, `rect`, `icon`…), w kartach. |
| `dur` | Czytają tylko: `3b1b` (`title`, `point`, `equation`, `line`), `wykresy` (`bar`, `line`, `candle`), `kurzgesagt` (`enter`), `historyjka` (`react`, `insert`). W innych miejscach ignorowane. |

**`offset` dla `slowo`** (zasada Jarva: element wchodzi od 0,2 s przed do 0,1 s po swoim słowie):

| Sytuacja | `offset` |
|---|---|
| zwykły element | od `-0.2` do `0.1` |
| `prezentacja`: tytuł i karta (wyłanianie trwa 0,7 s, przy słowie ma być ostro) | `-0.2` do `-0.3` |
| `tablica`: pisanie zaczyna się po frazie | ok. `0.5` |
| `number`: `at` = chwila, gdy pada liczba (liczenie startuje wcześniej samo) | `0` |
| `3b1b`: animacja rusza na czasowniku czynności | `0`, `slowo` = czasownik |

## `safe`
`{top, bottom, left, right, fill?}` w px, domyślnie 0. Klip przekazuje gramatyce `safe` i pole treści po odjęciu krawędzi `ctx.box = {x, y, w, h}`. `fill` (opcjonalny kolor) po renderze zamalowuje odsunięte krawędzie: w pionowym filmie wykres staje się „kartą” w tym samym miejscu i na tym samym tle co sąsiedni zrzut w trybie contain (przy `--alfa` nie maluje).

- **Wszystkie 8 gramatyk honoruje `top` i `bottom`:** treść tylko między top a H − bottom. `wykresy` – układ współrzędnych i wiersz źródła; `vox` – powiększenie kamery i środek kadru; `3b1b`, `prezentacja`, `kurzgesagt`, `tablica`, `kinetyczna` – cały układ; `historyjka` – dymki i wielki napis wstawki (postać, stół i twarz w zbliżeniu reakcji to grafika: w pionie wchodzą w pas napisów; napisy na ciele są czytelne, ale grafika się nie odsunie).
- **`left` i `right` nie zmieniają układu w żadnej gramatyce**: działają tylko z `fill` (zamalowanie), treść i tak dochodzi do krawędzi.
- **Wartości:** pas napisów lektora (edytor HQ, `projekt.py` i napisy ASS, do dwóch wierszy) to w pionie 1080×1920
  y 1220–1440 px, więc `bottom` 700; w poziomie 1920×1080 y 830–1005 px, `bottom` 250 (stała `PAS_NAPISOW`
  w `wideo_lib.py`; szablon `--format 9:16` wpisuje `top` 140 i `bottom` 700, 16:9 `bottom` 250, a `sprawdz` ostrzega
  przy mniejszym). `top` pod zakładki platformy: TikTok 140, Shorts 180, Reels 270. `gramatyka.py pomiar` sprawdza
  pas napisów sam (`--napisy tak`): tekst klipu w pasie dłużej niż 0,3 s to błąd.
- **Prawy pasek przycisków TikToka** (ok. 13% szerokości) zasłania to, co gramatyka stawia przy prawej krawędzi
  (w `wykresy` etykiety osi Y i wielka liczba), a `right` tego nie przesunie. `gramatyka.py pomiar --platforma tiktok`
  to pokaże: albo klip w montażu mniejszy i przesunięty w lewo (projekt edytora), albo świadomy wyjątek
  (`--wyjatek`) z powodem w RAPORT.md.

## `number` (wielka liczba)
Tylko `prezentacja`, `wykresy` i `kinetyczna`; w pozostałych 5 gramatykach `number` nic nie pokazuje.

| Element | Zasada |
|---|---|
| Wartość | `data.value` (liczba, może być ujemna; brak = 0). Liczy od 0 do `value` (`expoOut`: najpierw szybko, potem wolno); ujemna z prawdziwym minusem „−”, część całkowita z separatorem tysięcy. W Jarvie `TY.fmt` z nakładki pisze po polsku: przecinek dziesiętny, spacja tysięcy (`1 234,5`). |
| Format | `data.prefix` (np. `"$"`), `data.suffix` (np. `" zł"`, `" mln"`, `"%"`, `" razy"`; spację wpisujesz sam), `data.decimals` (domyślnie **0**; w `wykresy` `data.decimals` całego spec dotyczy tylko etykiet słupków – `number` go nie dziedziczy, wpisz w cue jeszcze raz). |
| Opis | `text`, `sub` albo `data.text` – dowolne z nich (klip je ujednolica). |
| Mała etykieta | `data.label`: `prezentacja` nad liczbą, `kinetyczna` w lewym górnym rogu strony; `wykresy` jej nie rysuje. |
| Czas | `at` = chwila, gdy liczba staje. `prezentacja` i `wykresy` zaczynają liczyć w `at` − 0,9 s; `kinetyczna` zmienia stronę i zaczyna liczyć w `at` − 0,7 s. Dlatego `at` ≥ 0,9 (`kinetyczna` ≥ 0,7), inaczej w klatce 0 liczba jest już w większości przewinięta. |
| Miejsce | `prezentacja`: osobny ekran, poprzedni zaczyna schodzić w `at` − 0,9 s i nie nakłada się na karty; `wykresy`: zarezerwowany pasek nad wykresem, do prawej, opis z lewej strony liczby; `kinetyczna`: osobna strona. |

## Wskazówki
- **Gęstość:** klip 3–8 s mieści wygodnie 2–5 cue. Gęściej: pisanie przyspiesza, kamera nie zdąży dojechać.
- **Wszystko, co się nie mieści, ma wyjście awaryjne:** najpierw mniejszy krój, potem łamanie, potem ustąpienie miejsca, na końcu ostrzeżenie. Układ dopasowany do długości przykładu psuje się przy prawdziwym lektorze i w pionie: sprawdzaj stopklatki z prawdziwymi, polskimi (dłuższymi) tekstami w obu formatach.
- **Tekst w kadrze kontra wypalone napisy:** `3b1b`, `wykresy`, `tablica` i `kinetyczna` same piszą tekst i walczą o wzrok z napisami lektora. Przy nakładaniu przesuń napisy, ustaw `safe` albo w tym fragmencie napisów nie wypalaj.
- **Pion i zrzut: zaznacz pół zdania, które lektor właśnie czyta.** Zrzut na biurku w pionie ma ok. 900 px szerokości; tekst strony 16 px trzeba przybliżyć 2–2,5×, żeby był czytelny. Ramka na cały szeroki akapit (prawie szerokość kadru) nie zmieści czerwonego kółka i kamera nie najedzie. Zdanie na dwie linie → dwa `highlight`, każdy na jedno słowo-klucz (test: najazd 2,4×, wysokość liter ok. 50 px). `rect` na oko myli się o 20–30%: najpierw `render --klatki`.
- **Skok klatek w kodzie gramatyki liczy się od `at`:** `MO.step(t − at, 12)`, nie `MO.step(t, 12)`; z bezwzględnej siatki element pokaże się do jednego kroku za wcześnie (przy 30 fps do 2 klatek). `historyjka` bierze klatki postaci z bezwzględnej siatki 24 fps, więc cue może przesunąć się o 1 klatkę: sprawdź.
- **Fakty:** każda liczba i nazwa na ekranie z `out/wideo/src/fakty.json` (brief Sherlocka); dane zmyślone tylko ze znaczkiem „dane przykładowe”.
