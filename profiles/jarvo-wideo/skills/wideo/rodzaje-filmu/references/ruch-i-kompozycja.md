# Ruch i kompozycja (każdy film z kodu)

Czytasz przy każdej własnej animacji (HTML, Remotion, lemo) obok pliku rodzaju. Skąd: video-shotcraft (Apache-2.0:
charaktery ruchu, oddech, tempo, uderzenia, jeden bohater na otwarcie, blask), video-talkcraft i anything2explainer
(licencja niekomercyjna: wzięte tylko pomysły i liczby, opisane po naszemu, bez ich kodu i tekstu).
Kod: `/_lib/jarvo/ruch.js` (charaktery, lądowanie, wyjście, smugi), kontrola: `html_wideo.py pomiar`.

## 1. Charakter ruchu z marki (przed pierwszą klatką)
Jedna marka = jeden charakter: te same czasy i krzywe dla wejść, przejść i spoczynku. Dwa charaktery w jednym filmie
wyglądają jak składanka. Wybór: najpierw **energia** (spokojna, ekskluzywna ↔ sport, startup, rozrywka: długość
ruchu i przestrzelenie), potem **ton** (poważny: finanse, zdrowie, prawo ↔ wesoły: konsument, dzieci: krzywe
i ilość ruchów pobocznych). Dowodem jest wygląd produktu (ostre kształty → precyzja, zaokrąglone i jasne → miękko);
słowa właściciela o marce wygrywają z Twoją oceną.

| Charakter (`ruch.js`) | Dla kogo | Główny ruch | Krzywa wejścia | Przestrzelenie | Ściśnięcie |
|---|---|---|---|---|---|
| `zaufanie` | B2B, finanse, prawo, usługi dla firm | 0,7 s | `0, 0, 0.2, 1` | brak | brak |
| `luksus` | premium, moda, biżuteria, hotele | 1,6 s | `0.4, 0, 0.6, 1` | ≤ 1,02 | brak |
| `odwazny` | sport, gry, startupy | 0,6 s | `0.16, 1, 0.3, 1` | 1,12 | 0,25 |
| `zabawny` | produkty konsumenckie, social, dzieci | 0,9 s | `0.34, 1.56, 0.64, 1` | 1,08 | 0,18 |
| `spokojny` | zdrowie, edukacja, opieka | 1,4 s | `0.42, 0, 0.58, 1` | brak | ≤ 0,04 |
| `przyjazny` | mała firma, lokalne usługi, społeczność | 0,87 s | `0.25, 0.46, 0.45, 0.94` | 1,04 | 0,08 |

```js
import { ladowanie, wyjscie } from '/_lib/jarvo/ruch.js';
const CH = 'przyjazny';                                  // z BRIEF.md: „Charakter ruchu: przyjazny (piekarnia)”
const l = ladowanie(t, 1.2, CH);                          // {p, skala, sx, sy, u}; u = 1 → wylądował
el.style.transform = `translateY(${(1 - l.p) * 80}px) scale(${l.skala * l.sx}, ${l.skala * l.sy})`;
const w = wyjscie(t, 4.6, CH);                            // wyjście szybsze (połowa czasu), krycie w.krycie
```
Podpowiedź z wyglądu strony: `assety.py` zapisuje w `marka.json` pole `charakter` (z rogów przycisków, nasycenia
akcentu i kroju nagłówka, dowód w `dlaczego`). Sprawdzian: opisz ruch gotowego filmu trzema słowami; mają pasować do słów marki. Wyjątek: element, który ma
„spaść” albo „przybić pieczątkę”, może się odbić także w charakterze `zaufanie`.

## 2. Oddech i tempo
- **Ważne rzeczy stoją po wylądowaniu.** Logo, liczba, hasło: po ostatnim ruchu co najmniej 1 s bez ruchu, zanim
  zniknie ujęcie. Logo na otwarciu i na końcu tak samo. Po serii szybkich cięć dłuższa pauza.
- **Koniec ujęcia:** ostatni element wylądował → 1–1,5 s spokoju (bez nowych elementów, bez ruchu kamery; trwająca
  czynność, np. płynące kropki, może trwać) → wyjście. Ruch kamery kończy się co najmniej 1 s przed wyjściem.
- **Pierwsza wersja jest prawie zawsze za szybka:** zwolnij o jeden stopień. Główna akcja otwarcia trwa ≥ 3 s,
  pisanie, klikanie i filtrowanie idą w tempie człowieka (widz ma zdążyć to powtórzyć).
- **Szybkość z przyspieszenia, nie ze stałej prędkości.** Żadnego ruchu liniowego. Seria elementów wchodzi coraz
  szybciej (jak rozdawanie kart), potem 0,5 s spokoju.
- **Nic nie stoi martwe dłużej niż 3 s:** czasownik z lektora ma swoją czynność na ekranie (dane płyną, kropki biegną,
  coś się zapełnia). Ale bez sztucznego „pływania” i „oddychania” elementów, żeby tylko coś się ruszało.

## 3. Bez efektu PowerPointa (lektor, explainer)
Skąd się bierze: kadr stoi, elementy tylko wjeżdżają i zamierają, sceny zmieniają się jak slajdy, a treść piętrzy się
jak w dokumencie. Zasady:
- **Warstwa kamery:** jeden bardzo wolny najazd na ujęcie (100% → 104–106%) albo odjazd; najwyżej jeden ruch kamery
  na ujęcie, nigdy najazd i odjazd pod rząd.
- **Nowy element tylko na ważnym zdaniu** (nowa teza, liczba, kontrast, wniosek), nie na każdym zdaniu.
  Przebudowa układu 2–4 razy na minutę.
- **Stary ustępuje nowemu:** gdy nie wróci, wychodzi (0,15–0,5 s); gdy za chwilę do niego wrócisz, zostaje
  przygaszony (skala 0,92, ciemniej, lekkie rozmycie). Poprzedni bohater może się zmniejszyć i odsunąć, robiąc miejsce
  nowemu, zamiast zniknąć i pojawić się od nowa.
- **Kolejność:** stary panel wychodzi całkiem → nowy bohater wchodzi → panel pomocniczy. Nie naraz.
- **Budżet kadru:** najwyżej 3 grupy naraz (przygaszone też się liczą), jedna ćwiartka kadru pusta, jedna duża liczba
  na ekran. Tekst na ekranie to skrót ≤ 12 słów, nigdy to samo co napisy lektora.

## 4. Kompozycja: jeden bohater
- **Każde ujęcie ma jednego bohatera:** element ≥ 1/4 krótszego boku kadru (duża liczba, przedmiot, zrzut, postać),
  wchodzi w pierwszym albo drugim bicie, reszta układa się wokół niego. Trzy rozmiary i nie więcej: bohater, elementy
  pomocnicze (do 4), podpisy (do 6). Napisy ≥ 5% wysokości kadru, inne teksty do czytania ≥ 3%.
- **Mały temat dostaje bohatera:** oś czasu, wzór, tabela czy proces są same za małe; dołóż dużą liczbę, powiększony
  bieżący element (×1,15) albo lupę. „Dużo” pokazuj równą siatką, która zapala się w rytm, a nie rozsypanymi ikonkami.
- **Światło idzie za bohaterem:** poświata tylko na nim (i najwyżej na jednym „bieżącym” elemencie); gdy uwaga
  przechodzi dalej, poprzednie światło gaśnie w ~0,25 s. Przed wyjściem gaśnie światło, potem znika element.
- **Najdroższy chwyt najwyżej 2 razy na film** (przelot światła, wielki błysk, efektowne wejście tytułu): pierwsze
  pojawienie się głównego pojęcia i ewentualnie puenta. Pozostałe ważne chwile mają skromniejsze wersje.
- **Uderzenia całego kadru najwyżej 3 na film** (pompa skali całego obrazu, wstrząs, klatka błysku, negatyw):
  tylko na najmocniejszych bitach, daleko od siebie. Pozostałe bity ruszają same elementy, nie cały kadr.
- **Kamera stoi pewnie:** w filmie produktu bez drgań „z ręki”. Odblask przesuwający się po elemencie raz na ujęcie,
  tylko na bohaterze, przycięty do jego zaokrąglonych rogów.

## 5. Przejścia (słownik)
Każda granica ujęć ma zaplanowane przejście (w mapie bitów BRIEF.md). Ten sam rodzaj powtarzany w filmie wygląda
spójniej niż wszystkie po kolei; na 100 s wystarczy 5–7 granic. Ujęcia zachodzą na siebie o 0,4–0,5 s, a ruch
kamery po obu stronach biegnie w tę samą stronę.

| Przejście | Wyjście z ujęcia | Wejście w następne | W montażu (`projekt.py przejscie`) |
|---|---|---|---|
| Najazd na wylot | kamera przyspiesza w bohatera | zaczyna przybliżone i osiada | `zoomin` |
| Prześwietlenie | najazd na jasny punkt, biały błysk 0,3 s w górę | wyłania się ze światła (0,3 s w dół) | `fadewhite` |
| Rzut kamery | szybki ruch w bok ze smugą (rozdz. 6) | wjeżdża z tej samej strony, hamuje w 0,35 s | `smoothleft`, `slideleft` |
| Czarne uderzenie | mocna klatka, potem 1 klatka czerni | startuje pełne i już w ruchu | `fadeblack` krótkie |
| Odjazd w chłód | wszystko gaśnie, barwa chłodnieje | start z mniejszej skali, odjazd | `fadeblack` długie |
| Rozsypanie | bohater rozpada się na drobiny | nowa scena składa się z drobin w tym samym miejscu | brak (tylko w kodzie) |

- **Czarne uderzenie raz na film**, na największym zwrocie. Odjazd w chłód pasuje na koniec i do spokojnych marek.
- **Ukryte cięcia:** przez przedmiot z pierwszego planu (przesłania kadr i odsłania nowy), dopasowanie kształtu
  (koło → koło w tym samym miejscu i rozmiarze), linia, która przechodzi w ramkę następnego ujęcia (raz na film,
  jako znak rozpoznawczy).
- **Jedno długie ujęcie** zamiast cięć: cała treść na jednym dużym płótnie, kamera jedzie od miejsca do miejsca
  (≤ 1,5 szerokości kadru na sekundę), treść pojawia się, gdy kamera się zbliża.

## 6. Szybki ruch bez motion bluru
Rozmycie ruchu (`html_wideo.py --subklatki N`) wydłuża render N razy, więc go nie używamy (tylko na wyraźną prośbę
właściciela). Szybki ruch rysujesz sam, w animacji:
- **Smuga** (`smuga(g, poz, t, r, kolor)`): kapsuła od pozycji sprzed 1/30 s do obecnej, ogon przezroczysty,
  głowa pełna; na niej ostry kształt. Tylko gdy element przelatuje szybciej niż ~0,8 szerokości kadru na sekundę.
- **Duchy** (`duchy(t, rysuj, n)`): 2–4 słabnące kopie za obiektem przez 1–3 klatki najszybszego ruchu (uderzenie,
  rzut).
- **Rozciągnięcie** (`rozciagniecie(v)`): element DOM rozciągnięty wzdłuż ruchu według prędkości (najwyżej +25%),
  w spoczynku wraca do kształtu.
- **Linie prędkości:** 3–6 cienkich kresek za obiektem przez 0,1–0,2 s.
Nigdy na tekście, który widz ma przeczytać.

## 7. Kontrola
`html_wideo.py pomiar` (ostrzeżenia, nie blokują): `pusta_scena` (największy obiekt < 15% krótszego boku
dłużej niż 1,5 s), `bez_oddechu` (ujęcie ≥ 2 s ma < 0,8 s spokoju przed przejściem; wyjście starego i wejście
nowego do 1,2 s się nie liczą; koniec filmu stoi < 0,8 s, film w pętli pomijany), `uderzenia_kadru` (> 3 uderzenia całego kadru). To przybliżenia z małych klatek: zanim
poprawisz, obejrzyj klatki z podanych sekund; świadomy wyjątek opisujesz `--wyjatek` z powodem.
Na arkuszu klatek sprawdzasz sam: jeden bohater w każdym ujęciu, światło tylko na nim, jeden charakter ruchu.
