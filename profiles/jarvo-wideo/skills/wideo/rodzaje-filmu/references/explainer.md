# Explainer

Wyjaśnia jedną rzecz tak, że widz ją rozumie po 30–90 s: zjawisko, proces, usługę, pojęcie.
Nie to: sprzedaż produktu z UI → `promo-produktu.md`; sam wykres → `dane.md`; stock z lektorem → `krotki-film`.

## Wynik
- 30–60 s na social (9:16 albo 1:1), 60–90 s na YouTube i stronę (16:9); lektor PL + napisy wypalone.
- Muzyka pod lektorem, efekty zsynchronizowane z akcją, miks −14 LUFS; źródła faktów w RAPORT.
- **Wariant „dla właściciela”** (karta „wyjaśnij mi filmem” od Jarva): ma tłumaczyć, nie sprzedawać. Bez haka
  sprzedażowego i CTA; fakty tylko z WEJŚĆ karty, zwykle brief Sherlocka `fakty.json` (lista fakt → plik w RAPORT,
  brak faktu = pytanie do Jarva); lektor prostym polskim (zdanie ≤ 20 słów); 60–90 s, 16:9; bez płatnej AI (0 zł).

## Silnik
| Styl | Silnik |
|---|---|
| diagramy, ikony, schematy, „studio motion design” | własny HTML Canvas/SVG (`kontrakt-html.md`) albo HyperFrames `faceless-explainer` |
| rysowany, tablica, szkicownik | `anidoodle` |
| matematyka, algorytm, fizyka | `manim-video` |
| liczby i wykresy w centrum | `dane.md` (+ ten plik dla narracji) |
| kinowy, markowy („premium”) | `lemo-opuscar` |
| instrukcja krok po kroku (montaż, konfiguracja, przepis), spokojny lektor „jak w szkolnym filmie” | `lemo-opuscar` `midcentury-toon` (kreskówka lat 50.) |
| nauka, historia, muzeum, dziedzictwo marki (rycina, która rysuje się sama) | `lemo-opuscar` `engraving` (miedzioryt) |

## Struktura
| 60 s | 30 s | Scena |
|---|---|---|
| 0–3 | 0–2 | **Hak:** sytuacja widza, pytanie, paradoks albo zaskakująca liczba („Światło, które widzisz, błądziło w Słońcu tysiące lat”); nie definicja, nie powitanie |
| 3–10 | 2–6 | **Stawka:** dlaczego to ważne dla widza |
| 10–45 | 6–24 | **Mechanizm** w 3–4 krokach; krok = scena = jedna idea formalna (zoom, przekrój, licznik, porównanie) |
| 45–55 | 24–28 | **Przykład z życia** albo zaskakujący wniosek |
| 55–60 | 28–30 | **Puenta:** koniec odwraca początek (wraca do sytuacji z haka i pokazuje ją inaczej), nie streszcza; CTA tylko, gdy karta go chce |

Tekst lektora według zasad narracji (`scenariusz/references/narracja.md`: start w sytuacji, jedna linia opowieści,
liczba w skali, którą czuć, koniec odwraca początek); `film.py narracja --sprawdz` łapie to, co widać ze słów.

## Rzemiosło
- Symuluj zamiast rysować: błądzenie losowe to prawdziwe błądzenie (z ziarnem), orbita liczona z prawa, nie klatki z ręki.
- Liczby prawdziwe, ze źródłem i uczciwą niepewnością (zakres zamiast jednej liczby, gdy szacunki się różnią).
- Bohater albo obiekt prowadzi przez cały film (foton, kropla, paczka danych); ma osobowość (mimika, reakcje).
- Zwroty akcji i callbacki: coś z haka wraca w puencie; drobne gagi (onomatopeje) trzymają uwagę.
- Lektor najpierw: `narracja.txt` (zdanie w linii, akapit = ujęcie) → `film.py narracja` → `lektor.wav` z pauzami
  z akapitów i `os_czasu.json`; animacja bierze chwile po nazwie (`kontrakt-html.md`, „Film z lektorem”), więc nowe
  nagranie lektora jej nie psuje. `fakty.json` w `src/`: trudne nazwy lektor czyta ze słowniczka briefu (`wymowa`).
- Na ekranie ≤ 6 słów naraz (reszta w napisach). Jedna analogia na film (z briefu, nie dalej niż jej `psuje_sie`),
  jedna metafora wizualna na pojęcie; porównania do znanych („jak stadion…”).
- **Bez efektu PowerPointa** (`ruch-i-kompozycja.md` rozdz. 3): jeden wolny najazd kamery na ujęcie, nowy element
  tylko na ważnym zdaniu (między nimi tempo trzymają zmiany stanu i lektor: zasada tempa, rozdz. 2), stary ustępuje nowemu, ≤ 3 grupy naraz, jeden bohater ≥ 1/4 krótszego boku kadru.

## Brief (`out/wideo/src/BRIEF.md`)
```
Temat i jedno zdanie, które widz ma zapamiętać:
Widz (co już wie, czego nie):
Fakty (`src/fakty.json` od Sherlocka albo lista z WEJŚĆ), analogia, niepewności:
Bohater / obiekt prowadzący:          Styl i silnik:          Charakter ruchu (ruch-i-kompozycja.md):
Sceny (czas → idea formalna → zdanie lektora):
Format, długość, CTA:                 Dźwięk (muzyka, efekty):
```

## Pułapki
- Ściana tekstu na ekranie; lektor szybszy niż 2,7 słowa/s; trzy pojęcia w jednej scenie.
- Zmyślone liczby albo liczby bez źródła; uproszczenie, które jest nieprawdą (zapisz uproszczenia w RAPORT).
- Zmiana stylu między scenami; ozdobniki bez funkcji; hak, który obiecuje coś, czego film nie dowozi.

## Kontrola
- Arkusz 1 klatka na scenę: czy każda scena ma jedną czytelną ideę; paski klatek na przejściach.
- Liczby lektora i ekranu kontra `fakty.json` (`film.py narracja`, `pomiar`): ostrzeżenie wyjaśniasz w RAPORT; napisy = lektor.
- Test „wyciszony telefon”: bez dźwięku film nadal da się zrozumieć z obrazu i napisów.

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py explainer --ile 3` (albo `--szukaj whiteboard`, `--tag threejs`).
