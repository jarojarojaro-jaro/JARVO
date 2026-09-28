# Explainer

Wyjaśnia jedną rzecz tak, że widz ją rozumie po 30–90 s: zjawisko, proces, usługę, pojęcie.
Nie to: sprzedaż produktu z UI → `promo-produktu.md`; sam wykres → `dane.md`; stock z lektorem → `krotki-film`.

## Wynik
- 30–60 s na social (9:16 albo 1:1), 60–90 s na YouTube i stronę (16:9); lektor PL + napisy wypalone.
- Muzyka pod lektorem, efekty zsynchronizowane z akcją, miks −14 LUFS; źródła faktów w RAPORT.

## Silnik
| Styl | Silnik |
|---|---|
| diagramy, ikony, schematy, „studio motion design” | własny HTML Canvas/SVG (`kontrakt-html.md`) albo HyperFrames `faceless-explainer` |
| rysowany, tablica, szkicownik | `anidoodle` |
| matematyka, algorytm, fizyka | `manim-video` |
| liczby i wykresy w centrum | `dane.md` (+ ten plik dla narracji) |
| kinowy, markowy („premium”) | `lemo-opuscar` |

## Struktura
| 60 s | 30 s | Scena |
|---|---|---|
| 0–3 | 0–2 | **Hak:** pytanie, paradoks albo zaskakująca liczba („Światło, które widzisz, błądziło w Słońcu tysiące lat”) |
| 3–10 | 2–6 | **Stawka:** dlaczego to ważne dla widza |
| 10–45 | 6–24 | **Mechanizm** w 3–4 krokach; krok = scena = jedna idea formalna (zoom, przekrój, licznik, porównanie) |
| 45–55 | 24–28 | **Przykład z życia** albo zaskakujący wniosek |
| 55–60 | 28–30 | **Jedno zdanie podsumowania** + CTA (jeśli karta go chce) |

## Rzemiosło
- Symuluj zamiast rysować: błądzenie losowe to prawdziwe błądzenie (z ziarnem), orbita liczona z prawa, nie klatki z ręki.
- Liczby prawdziwe, ze źródłem i uczciwą niepewnością (zakres zamiast jednej liczby, gdy szacunki się różnią).
- Bohater albo obiekt prowadzi przez cały film (foton, kropla, paczka danych); ma osobowość (mimika, reakcje).
- Zwroty akcji i callbacki: coś z haka wraca w puencie; drobne gagi (onomatopeje) trzymają uwagę.
- Lektor najpierw (`film.py lektor` → czasy słów), animacja pod słowa; na ekranie ≤ 6 słów naraz (reszta w napisach).
- Jedna metafora wizualna na pojęcie; porównania do rzeczy znanych („jak stadion pełen…”).

## Brief (`out/wideo/src/BRIEF.md`)
```
Temat i jedno zdanie, które widz ma zapamiętać:
Widz (co już wie, czego nie):
Fakty i źródła (z karty / raportu Sherlocka), niepewności:
Bohater / obiekt prowadzący:          Styl i silnik:
Sceny (czas → idea formalna → zdanie lektora):
Format, długość, CTA:                 Dźwięk (muzyka, efekty):
```

## Pułapki
- Ściana tekstu na ekranie; lektor szybszy niż 2,7 słowa/s; trzy pojęcia w jednej scenie.
- Zmyślone liczby albo liczby bez źródła; uproszczenie, które jest nieprawdą (zapisz uproszczenia w RAPORT).
- Zmiana stylu między scenami; ozdobniki bez funkcji; hak, który obiecuje coś, czego film nie dowozi.

## Kontrola
- Arkusz 1 klatka na scenę: czy każda scena ma jedną czytelną ideę; paski klatek na przejściach.
- Każda liczba na ekranie i w lektorze zgodna ze źródłem; napisy = lektor (nazwy, liczby, polskie znaki).
- Test „wyciszony telefon”: bez dźwięku film nadal da się zrozumieć z obrazu i napisów.

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py explainer --ile 3` (albo `--szukaj whiteboard`, `--tag threejs`).
