# Rubryka designu: 10 osi

Pytanie brzmi nie „czy to jest poprawne?”, tylko „czy senior product designer z firmy klasy Linear / Stripe /
Supabase by to podpisał?”. Każda oś: **zaliczona** albo **różnica** z dowodem (zrzut, szerokość, miejsce) i najmniejszą
zmianą, która ją naprawi. Zaliczenie bez nazwanego dowodu na każdej osi to nie recenzja.

| Oś | Zaliczona, gdy | Różnica, gdy |
|---|---|---|
| 1. **Hierarchia** | jedno spojrzenie mówi, co prowadzi, co wspiera, co jest w tle | sąsiednie elementy konkurują z równą wagą; nagłówki nie porządkują skanowania |
| 2. **Typografia** | modułowa skala; nagłówki i tekst zachowują się inaczej celowo; płynne rozmiary (`clamp()`) | przypadkowe rozmiary, jeden stopień do trzech ról, zła interlinia |
| 3. **Rytm odstępów** | wartości ze skali (tokeny), rodzeństwo ma równe odstępy, sekcje oddychają proporcjonalnie do wagi | wartości spoza skali, sklejone sekcje, nierówne paddingi |
| 4. **System kolorów** | warstwy tła, hierarchia tekstu kolorem, świadomie oszczędny akcent, stany semantyczne; kontrast ≥ AA | jeden kolor zalewający wszystko plus szarość; gradienty bez roli; kontrast pod progiem |
| 5. **Stany** | linki, przyciski i pola mają hover, widoczny fokus, active, disabled, loading, błąd, pusty stan | element interaktywny tylko ze stanem domyślnym |
| 6. **Coś własnego** | co najmniej jeden świadomy element, którego nie ma szablon (zgodny z brand kitem) | nic nie odróżnia strony od przykładowej aplikacji frameworka |
| 7. **Ruch z umiarem** | animacja mówi o stanie albo przyczynie, ma krótkie czasy i respektuje `prefers-reduced-motion` | ruch dekoracyjny, przejęte przewijanie, zignorowane reduced motion |
| 8. **Polski tekst** | `lang="pl"`, diakrytyki w foncie (ąęłńóśźż), długie słowa się łamią (`overflow-wrap`, `hyphens`), cudzysłowy „”, twarde spacje po spójnikach w nagłówkach | brakujące glify, rozpychające słowa (test `longwords`), angielskie cudzysłowy |
| 9. **Bez domyślnego gustu modelu** | styl wynika z marki i kierunku | kremowe tło, szeryfowy nagłówek i terakotowy akcent na stronie, która tego nie uzasadnia (np. narzędzie, fintech) |
| 10. **Wybrane, nie odziedziczone** | niebieski frameworka, szkło, gradienty, domyślny krój, cień na każdej karcie, równa siatka kolumn: każde ma powód albo jest zastąpione | domyślne ustawienie bez uzasadnienia |

## Punkty
Start 100. Za każdą różnicę odejmujesz: **−8** oś 1–5 (podstawy), **−5** oś 6–10. Blokujące z rubryki Sędziego
(kontrast pod AA, poziome przewijanie, brak fokusu) to **−15** każde. Wynik < 90 → `REVISE`.

Źródło: oh-my-hermes, `omh-design-quality-gate/references/design-critique-rubric.md` (MIT), przełożone i dopasowane
do polskich stron (oś 8) i brand kitów floty.
