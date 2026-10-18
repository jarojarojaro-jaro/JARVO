# Ruch i kompozycja (każdy film z kodu)

Czytasz przy każdej własnej animacji (HTML, Remotion, lemo) obok pliku rodzaju. Skąd: video-shotcraft (Apache-2.0:
charaktery ruchu, oddech, tempo, uderzenia, jeden bohater na otwarcie, blask), video-talkcraft i anything2explainer
(licencja niekomercyjna: wzięte tylko pomysły i liczby, opisane po naszemu, bez ich kodu i tekstu), huashu-art-motion
(MIT: zasady sprawdzone na 36 stylach i 8 gramatykach, z dowodami w `style-malarskie/references/zasady-huashu.md`).
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
**Zasada tempa (nadrzędna; filmy idą na social media, więc muszą trzymać widza):**
- **Nigdy ≥ 2 s bez mowy i bez nowej rzeczy na ekranie.** Gdy obraz stoi (element wylądował, widz czyta), mówi lektor;
  gdy lektor robi pauzę, na ekranie wchodzi coś nowego. Wyjątek: spokojna plansza końcowa do 2 s.
- **Pod mową nowa rzecz co ok. 2 s, najdalej co 6 s:** wejście, zmiana stanu, cięcie, liczba, ruch kamery z celem.
- **Rysujesz tylko to, co główne.** Szczegółowe rysowanie (kreska, szraf, grawer, pisanie odręczne) dostaje jeden
  główny element ujęcia i trwa ≤ 1–1,5 s; reszta wchodzi szybko (≤ 0,4 s) albo już stoi. Wszystkiego dokładnie
  narysować się nie da i nie trzeba.
- **Powtarzalne naraz:** ziarna, ikony, kafle, punkty listy wchodzą po 2–3 jednocześnie (przesunięcie 0,1–0,2 s),
  nie jedno po drugim.
- **Ale nie na przesadę:** jedna główna akcja naraz, cięcia nie częściej niż co ok. 0,8 s, tekst stoi tyle, ile trwa
  przeczytanie, ważna rzecz po wylądowaniu stoi ≥ 1 s (pod mową albo na końcu).
- **Sprawdza** `krytyka.py tempo <film.mp4> [--mowa lektor.srt]` (`.srt` obok filmu bierze sam): błąd = przestój ≥ 2 s
  albo luka obrazu > 6 s pod mową; poprawka przed oddaniem. Puszczasz na animaticu albo szkicu, nie dopiero na finale.
  Progi z pomiaru: „Młyn” (za wolny w ocenie właściciela) miał przestoje 2,2–3,6 s, dobre filmy żadnego.

- **Tekst w kawałkach** (za cinetic, MIT): zdanie nigdy nie ląduje blokiem. Kawałek = 1–5 słów (najlepiej 2–3) wchodzących
  razem; dłuższa myśl to łańcuch 2–4 kawałków (najwyżej 12 słów) z obrazem między nimi, w trybie „dopisz” (kawałki
  dochodzą do jednej linii, ≤ 10 słów naraz) albo „podmień” (każdy schodzi, następny wchodzi na to samo miejsce).
  Dziel na granicy gramatyki, nigdy liczby od jednostki („2184 linii”) ani nazwy. Animacja jest czasownikiem: słowa
  przed i po pokazie, nie opis tego, co widać. Po przeczytaniu kawałka nic nowego nie startuje, dopóki trwa czytanie;
  czytany tekst nie jedzie szybciej niż ~1200 px/s (przy 1080); tekst bez sprężyny i przestrzelenia. Bez lektora
  obraz dostaje chwile bez słów: ≥ 1,5 s w każdych 10 s, tekst na ≤ 80% filmu. Najwyżej ~10 nowych słów na 5 s.
- **Ważne rzeczy stoją po wylądowaniu.** Logo, liczba, hasło: po ostatnim ruchu co najmniej 1 s bez ruchu, zanim
  zniknie ujęcie. Logo na otwarciu i na końcu tak samo. Po serii szybkich cięć dłuższa pauza.
- **Koniec ujęcia:** ostatni element wylądował → 1–1,5 s spokoju (bez nowych elementów, bez ruchu kamery; trwająca
  czynność, np. płynące kropki, może trwać) → wyjście. Ruch kamery kończy się co najmniej 1 s przed wyjściem.
- **Pojedynczy ruch w pierwszej wersji bywa za szybki:** zwolnij go o jeden stopień (sprężyna, wyhamowanie), ale
  nie dokładaj spokoju, bo tempo trzyma zasada wyżej. Pisanie, klikanie i filtrowanie idą w tempie człowieka (widz ma
  zdążyć to powtórzyć); główna akcja otwarcia może trwać ≥ 3 s, gdy co chwilę coś się w niej zmienia.
- **Szybkość z przyspieszenia, nie ze stałej prędkości.** Żadnego ruchu liniowego. Seria elementów wchodzi coraz
  szybciej (jak rozdawanie kart), potem 0,5 s spokoju.
- **Na bicie odsłonięcie, nie start ruchu.** Wejście pod bit zaczyna się wcześniej: start = bit − chwila odsłonięcia
  w ruchu × długość ruchu, a w klatce bitu widać zmianę na całym ekranie (przy przejściu ruszają obie warstwy, stara
  i nowa). W huashu uderzenie samą nową warstwą spóźniało 6 z 15 przejść o 0,1–0,17 s.
- **Otwarcie maluje się samo:** pierwszy obraz powstaje procesem swojego materiału (kreska się wypisuje, kolory druku
  spadają warstwami, piksele zapalają się wierszami, wykres najpierw stawia osie). Klatka 0 nie jest pustym tłem.
- **Ruch z treści, nie wypełniacz:** czasownik z lektora ma swoją czynność na ekranie (dane płyną, kropki biegną,
  coś się zapełnia). Bez sztucznego „pływania” i „oddychania” elementów, żeby tylko coś się ruszało.

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
- **Kadr z informacją składasz po kolei:** najpierw struktura (osie, układ, płótno), potem dane, na końcu oznaczasz
  jedną rzecz. Tak samo przy budowie: najpierw obiekty, relacje i kamera, faktura i ozdoby na końcu.
- **Małe rzeczy rób większe, niż podpowiada intuicja:** rozpoznawalny motyw i rekwizyt sprawdzasz na stopklatce
  w rozmiarze docelowym (w testach huashu motywy trzeba było powiększyć 1,35–2×, zanim dało się je odczytać).
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

- **Kamera to funkcja czasu filmu, przejście tylko składa dwa ujęcia.** Najazd w przejściu prowadzi dalej kamerę
  starego ujęcia (w wektorach), nie powiększa wyrenderowanej klatki. Najazd przez okrągły obiekt kończy się
  powiększeniem ≥ połowa przekątnej kadru / promień obiektu (1920×1080: ≥ 1100 / r), inaczej ostatnia klatka skacze.
- **Ruch ciągły przez cięcie:** postać albo przedmiot widoczny po obu stronach przejścia liczy ruch z czasu całego
  filmu `t`, nie od nowa w każdym ujęciu (inaczej widz widzi „pięć razy podnosi filiżankę” zamiast jednej chwili).
- **Czarne uderzenie raz na film**, na największym zwrocie. Odjazd w chłód pasuje na koniec i do spokojnych marek.
- **Ukryte cięcia:** przez przedmiot z pierwszego planu (przesłania kadr i odsłania nowy), dopasowanie kształtu
  (koło → koło w tym samym miejscu i rozmiarze), linia, która przechodzi w ramkę następnego ujęcia (raz na film,
  jako znak rozpoznawczy).
- **Jedno długie ujęcie** zamiast cięć: cała treść na jednym dużym płótnie, kamera jedzie od miejsca do miejsca
  (≤ 1,5 szerokości kadru na sekundę), treść pojawia się, gdy kamera się zbliża. Kamera jedzie tylko do przodu:
  jej pozycja to największa dotąd wartość celu z wygładzeniem, więc na postojach nie cofa się (w huashu cofanie
  o 68–256 px w 17 z 24 odcinków widz zauważył od razu).

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

## 7. Obraz żyje, ale nie migocze
- **Ruch główny i 2–4 pętle z motywów treści** (żywy obraz, scena stylu, tło pod lektora): jedna czynność główna,
  w tle małe pętle wzięte z tego, co jest w kadrze (para z filiżanki, liście, światło na wodzie). W huashu 16 scen
  według tej zasady ruszało 1,6–14% kadru bez skoków. Pętla bez związku z treścią to wypełniacz (rozdz. 2).
- **Bez nowego losu co kilka klatek:** faktura i pole kierunków zmieniają się płynnie z czasem (szum od `t`),
  pociągnięcia i ziarno stoją. Nowe ziarno całego kadru 8 razy na sekundę zmienia więcej pikseli niż przejście i widz
  widzi migotanie. „Wrzenie” tylko linii rysunku (`style-motion`, `kreska.js`).
- **Przewijany wzór zawijasz modulo jego prawdziwego okresu** (kropki w siatce sześciokątnej: dwa rzędy, nie odstęp
  kropek; meander, fryz, taśma: cały powtarzalny kawałek), inaczej w klatce zawinięcia wzór skacze.
- **Bezruch z gramatyki to nie zacięcie:** napis po wylądowaniu stoi, opowieść stoi na puencie, a ruch dają kamera
  i tło. Pod mową wolno (przestoje pilnuje zasada tempa, rozdz. 2); ostrzeżenie `martwy_odcinek` przy takim bezruchu
  opisujesz wyjątkiem z powodem.
- **Nieruchome raz, co klatkę tylko to, co się rusza:** tło i stałe warstwy rysujesz raz na osobną kanwę i kopiujesz;
  czas klatki mierzysz prawdziwym renderem (`html_wideo.py klatki --czasy`), nie czasem samego JS.

## 8. Kontrola
`krytyka.py tempo` (zasada tempa, rozdz. 2) blokuje: przestój ≥ 2 s albo luka obrazu > 6 s pod mową to poprawka.
`html_wideo.py pomiar` (ostrzeżenia, nie blokują): `pusta_scena` (największy obiekt < 15% krótszego boku
dłużej niż 1,5 s), `bez_oddechu` (ujęcie ≥ 2 s ma < 0,8 s spokoju przed przejściem; wyjście starego i wejście
nowego do 1,2 s się nie liczą; koniec filmu stoi < 0,8 s, film w pętli pomijany), `uderzenia_kadru` (> 3 uderzenia całego kadru),
tekst w kawałkach (rozdz. 2): `kawalek` (> 5 słów wchodzi razem), `slow_naraz` (> 10 słów filmu w klatce, z napisami
produktu `data-ui` > 14), `tempo_slow` (> 10 nowych słów w 5 s), `tekst_szybki` (czytelny tekst > 1200 px/s przez
≥ 0,3 s), bez lektora `tekst_caly_czas` (> 80% filmu) i `bez_przerwy_od_tekstu` (10 s bez 1,5 s samego obrazu). To przybliżenia z małych klatek: zanim
poprawisz, obejrzyj klatki z podanych sekund; świadomy wyjątek opisujesz `--wyjatek` z powodem.
Na arkuszu klatek sprawdzasz sam: jeden bohater w każdym ujęciu, światło tylko na nim, jeden charakter ruchu.
