# Historia

Krótka animowana historia z bohaterem: bajka, reklama fabularna, scenka, „w stylu Pixara”, storybook.
Nie to: wyjaśnianie zjawiska z bohaterem-maskotką → `explainer.md`; trailer gry → `interaktywne.md`.

## Wynik
- 20–60 s; 16:9 albo 9:16; muzyka i efekty prowadzą emocję; lektor albo dialogi tylko, gdy historia ich potrzebuje.
- Bohater własny (zero cudzych postaci i marek), spójny wygląd w każdej scenie.

## Silnik
| Styl | Silnik |
|---|---|
| 39 stylów kina (akwarela, anime, papier, klocki, pixel RPG…) z reżyserią | `lemo-opuscar` |
| rysunek, bajka szkicowana, timelapse rysowania | `anidoodle` |
| własna postać w Canvas / Three.js | własny HTML (`kontrakt-html.md`) |
| realistyczne ujęcia (tylko za zgodą, płatne) | `wideo-ai` (limit z karty) |

## Struktura (45 s)
| 45 s | Akt |
|---|---|
| 0–6 | **Świat i bohater z pragnieniem** (co chce, jednym obrazem) |
| 6–30 | **Przeszkoda i próby**: 2–3 narastające, każda gorsza od poprzedniej |
| 30–38 | **Zwrot**: bohater zmienia sposób (albo pomaga mu to, co reklamujemy, subtelnie) |
| 38–45 | **Rozwiązanie i puenta** (obraz, który zostaje; logo dopiero po puencie) |
Warsztat: `sw-premise-theme` (jedna myśl), `sw-scene-craft` (scena = zmiana wartości), `sw-character-conflict`.

## Rzemiosło
- Storyboard najpierw: 1 klatka kluczowa na scenę (arkusz), dopiero potem animacja.
- Zasady animacji postaci: przygotowanie ruchu, squash & stretch z umiarem, follow-through, staging (sylwetka
  czytelna na czarno), emocja w pozie i oczach, nie w podpisie.
- Dwa–trzy ustawienia kamery i cięcia między nimi (plan ogólny → bliski na emocję); oś akcji zachowana.
- Rytm: cisza przed zwrotem, dźwięk na każdym ważnym ruchu; muzyka zmienia się z aktem.
- Jeden spójny styl (paleta, grubość linii, światło) przez cały film.

## Brief (`out/wideo/src/BRIEF.md`)
```
Premisa (jedno zdanie) i emocja końcowa:       Bohater: wygląd, pragnienie, cecha:
Akty (czas → co się dzieje → obraz kluczowy):  Styl i silnik:
Dźwięk (muzyka, efekty, głos):                  Marka (czy i gdzie, subtelnie):
```

## Pułapki
- Historia bez przeszkody (ładne ujęcia bez napięcia); bohater zmieniający wygląd między scenami.
- Reklama wypowiedziana zamiast pokazana; logo w pierwszych sekundach; cudze postacie („jak Myszka Miki”).

## Kontrola
- Arkusz klatek kluczowych: emocja czytelna bez dźwięku; bohater spójny; zwrot widoczny.
- Test opowiedzenia: czy da się streścić film jednym zdaniem zgodnym z premisą z briefu.

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py fabula --ile 3` (albo `--szukaj storybook`).
