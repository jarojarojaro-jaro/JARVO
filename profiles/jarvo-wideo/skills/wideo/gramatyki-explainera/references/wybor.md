# Wybór gramatyki explainera

Osiem gramatyk animacji do filmów z lektorem (explainery YouTube, technologia, AI, finanse). Każda ma klip: plik spec (JSON) → odcinek animacji o dokładnej długości (`kontrakt-spec.md`). Dziewiąta, `prowadzacy`, to tylko wzór i metoda, bez klipu. Zasady wspólne dla wszystkich: `wspolne-zasady.md`; szczegóły jednej gramatyki: jej karta `<nazwa>.md`.

```bash
G="$HERMES_HOME/scripts/gramatyka.py"
@@PY@@ "$G" wzor <nazwa> --arkusz out/wideo/wzor-<nazwa>.jpg                 # stopklatki filmu pokazowego
@@PY@@ "$G" szablon <nazwa> [--format 9:16] -o out/wideo/src/klip-<nazwa>/spec.json       # start
```

Filmy pokazowe mają ok. 8 s i są 2,5–3 razy gęstsze niż prawdziwe tempo, żeby w krótkim pokazie zmieścić całą gramatykę. W filmie zwolnij do długości ujęć z tabeli.

## Przegląd

| Gramatyka | Do czego | Istota w jednym zdaniu | Typowe ujęcie | Główna krzywa | Główne przejścia |
|---|---|---|---|---|---|
| **`kurzgesagt`** (y1, płaska popularnonaukowa) | Skala, „co jest w środku”, mechanizmy i systemy; spokojny, gawędziarski ton | Abstrakcyjne pojęcie w świecącym świecie, który można powiększać bez końca; kamera przelatuje między skalami, obraz zawsze lekko się rusza | Twarde cięcia co 7–9 s, jednostka wizualna zmienia się co 4,6–6,7 s | `MO.k75` = bezier(.75,0,.25,1); pętle `MO.easyEase` | Wejście w soczewkę `lensReveal`, wypełnienie i wyjazd `matchCut` (kamera z logarytmicznym zoomem) |
| **`vox`** (y2, kolaż) | Argument z prawdziwymi archiwami, wiadomościami, zrzutami, ludźmi; „spójrz na to zdanie”, „zwróć uwagę na tę liczbę” | Argument leży na biurku z prawdziwymi materiałami; kamera jeździ po nim jak oko reportera śledczego, linie i pisak rysują się skokowo | Tempo wolne: mediana 3,3 s (karta 3–7 s); szybkie: 1,4–1,8 s | Kamera `MO.sineInOut` / długi ogon `MO.longTail`; elementy skokowo 12 fps | Twarde cięcie, jazda wzdłuż czerwonej nici `same`, najazd do pełna na zdjęcie → twarde `cut` |
| **`tablica`** (y3, rysowana tablica w stylu RSA) | Łańcuch rozumowania, kroki, „dlaczego”; wyprowadzanie na żywo | Zdanie powiedziane = zdanie napisane; kamera idzie za argumentem po wielkiej tablicy, na końcu odjeżdża na całość | Postój na bloku: mediana 6,6 s | Przesunięcie po tablicy `MO.sineInOut` 1,2–2,4 s; daleki skok 0,8 s z przerzutem i rozmyciem ruchu | Ta sama tablica `same` (ruch kamery jest przejściem), na końcu odjazd |
| **`historyjka`** (y4, prosta postać opowiada) | Przeżycia w pierwszej osobie, wpadki, puenty; widz chce „tego człowieka” | Lektor jest bohaterem, obraz to reakcje do jego słów: poza zmienia się w 0,1 s i zamiera, puenta to cięcie na zbliżenie reakcji i milczenie w tej chwili | ASL 2,43 s (mediana 1,87 s) | Zmiana pozy `MO.expoOut` 0,1 s + `MO.settle` (ściśnięcie i odbicie); postać 24 fps | Twarde `cut`, uderzenie `smash`, przerzut `whip`, skok na bliższy plan |
| **`kinetyczna`** (y5, typografia kinetyczna) | Listy, „X etapów”, zdanie-puenta, otwarcie liczbą, plansze rozdziałów | Słowa są aktorami: słowo-klucz wpada na akcent, słowo główne tak duże, że czyta się je w mgnieniu oka, zawsze jeden punkt uwagi | Jeden takt = jedno ujęcie (przy 120 BPM ok. 2 s) | Wejście `MO.expoOut`, uderzenie `MO.springHz`, wyjście `MO.expoIn` (szybsze) | Wpadnięcie w plamę koloru `fillZoom`, pasy koloru `bands`, przesunięcie strony `push` |
| **`3b1b`** (t1, 3Blue1Brown) | Jak mechanizm krok po kroku staje się czymś innym: sieci, macierze, gradienty, prawdopodobieństwo | Na czarnym tle tylko to, o czym mowa; Transform zamienia poprzednie pojęcie wprost w następne, kolor = nazwa pojęcia, prawie bez cięć | Animacja 1–3 s + 1 s postoju; jedno pojęcie 8–20 s | `MO.smooth` (6t⁵−15t⁴+10t³), prawie wyłącznie | Transform bez cięcia, przelot kamery `zoomThrough`, `fadeShift` |
| **`prezentacja`** (t2, interfejs z premiery) | Premiera produktu lub funkcji, nowa wersja, kroki samouczka, ogłoszenie parametrów | Ciemne tło z plamami światła, jedna rzecz na ekran; tekst wyłania się z rozmycia, interfejs w szklanej karcie ląduje na sprężynie z lekkim odbiciem, przejście rozwija tę samą taflę | Ekran prezentacji 5–8 s; szybki montaż produktowy 1,5–3 s | `MO.spring` z bounce 0–0,15, `MO.appleOut` | Rozmyte pchnięcie `blurPush`, rozwinięcie karty `expandRect` |
| **`wykresy`** (t3, wykresy finansowe) | Przychody, kursy, udziały, punkty zwrotne; liczby, które widz zrzuci i sprawdzi | Najpierw układ współrzędnych, potem dane rosną, na końcu jedno oznaczenie; wartości zawsze uczciwe, animacja decyduje tylko, jak się pojawiają | Jeden wykres 2,5–6 s | `MO.quintOut`, linia `MO.smooth` | Przesunięcie panelu `slidePush`, najazd na fragment `zoomThrough` (`live` + `bScale0`), twarde cięcie przy niezmiennym układzie |

Dziewiąta: **`prowadzacy`** (y6, rysunkowy prowadzący): historia firmy, mechanizm produktu, wyjaśnienia z reakcją; prowadzący łączy kartki, wykresy i słowa-klucze. Bez klipu: własna strona filmu, własne klatki postaci (`prowadzacy.md`).

## Która gramatyka do tego fragmentu lektora

Najpierw zobacz, co robi ten fragment lektora, potem wybierz sposób rysowania. Film może zmieniać gramatykę między fragmentami, ale w jednym fragmencie ich nie mieszaj.

| Ten fragment lektora… | Wybierz | Nie wybieraj | Dlaczego |
|---|---|---|---|
| wyjaśnia pojęcie albo mechanizm („jak działa sieć neuronowa…”) | **`3b1b`** (wyprowadzenie, wzory) albo **`kurzgesagt`** (skala, sympatyczny ton) | `vox` (bez prawdziwych materiałów wyjdzie fałszywe archiwum) | Mechanizm najlepiej tłumaczy przekształcenie i skala |
| opowiada wiadomość, wydarzenie, historię ze zrzutami i cytatami | **`vox`** | `kurzgesagt` (płaska kreskówka osłabia wiarygodność) | Widz chce zobaczyć źródło na własne oczy |
| opowiada własne przeżycie, wpadkę, puentę | **`historyjka`** | `prezentacja` (niesie nastrój dobrej wiadomości) | Puenta siedzi w pauzie na zbliżeniu reakcji |
| wylicza: listę, kilka punktów, etapy, jedno zdanie-puentę | **`kinetyczna`** | `3b1b` (nie ma czego przekształcać) | Informacja to struktura, nie obraz |
| mówi o produkcie, krokach samouczka, funkcjach, parametrach | **`prezentacja`** (zrzuty w szklanych kartach) | `3b1b` (szkło i plamy nie niosą logiki – i odwrotnie) | Jedna rzecz na ekran, rzeczowniki i liczby są bohaterami |
| mówi o liczbach, wzroście, trendzie, porównaniu | **`wykresy`** | wielka liczba z `prezentacja` (tylko gdy liczba jest jedna) | Potrzebny układ współrzędnych i jednostka; musi się dać sprawdzić |
| wyprowadza na żywo, argumentuje krok po kroku | **`tablica`** | zmiana całego ekranu naraz | Zdanie powiedziane = zdanie napisane, odjazd na końcu to puenta |

Dodatek Jarva: historia firmy albo produktu prowadzona przez postać marki, gdy masz jej klatki → `prowadzacy` (tylko wzór).

## Dwie zasady awaryjne
- **Są prawdziwe zrzuty do pokazania** → `prezentacja` (samouczek, czysto) albo `vox` (argument, poczucie dowodu). Zrzuty zawsze proporcjonalnie, bez ucinania kluczowego UI.
- **We fragmencie jest tylko jedna liczba** → bez wykresu: wielka liczba z odliczaniem w `prezentacja` albo `kinetyczna` (`number`), która staje w chwili, gdy lektor wypowiada wartość.
