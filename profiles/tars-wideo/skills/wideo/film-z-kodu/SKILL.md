---
name: film-z-kodu
description: "Film z kodu: HyperFrames, Manim; scenariusz, render, QA."
version: 2.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, hyperframes, manim, motion-graphics, code]
    related_skills: [hyperframes, product-launch-video, faceless-explainer, motion-graphics, slideshow, manim-video, scenariusz, napisy, kontrola-wideo]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Film z kodu

Animacje, typografia w ruchu, interfejs produktu, wykresy i wzory: renderowane z kodu, więc tekst i liczby są ostre
i poprawne. Film z ujęć, lektora i napisów bez animacji → `krotki-film`.

## Wybór silnika
| Potrzeba | Silnik |
|---|---|
| promo produktu, launch, reels z animowanym tekstem | **HyperFrames** (`hyperframes`, `product-launch-video`, `motion-graphics`) |
| explainer bez nagrań (tekst → wideo) | HyperFrames `faceless-explainer` |
| pokaz zdjęć/slajdów z przejściami | HyperFrames `slideshow` |
| matematyka, algorytmy, wykresy w ruchu | **Manim** (`manim-video`; dodatek obrazu `manim`, sprawdź `command -v manim`) |
| animacja + prawdziwe ujęcia | render z kodu jako `plik` sceny w planie `krotki-film` |

HyperFrames `media-use` (muzyka, lektor, stock) wymaga zalogowanego CLI HeyGen. Bez niego: lektor
`film.py lektor` (Edge TTS, z czasem słów), ujęcia `material-stock`, napisy `napisy`.

## Kroki
1. **Brief i format** (`formaty-wideo`): platforma, długość, cel, jedno przesłanie, CTA, brand kit.
2. **Scenariusz** (`scenariusz`) → `out/wideo/SCENARIUSZ.md`; **storyboard**: tabela scen (czas, obraz, tekst na ekranie,
   animacja, dźwięk). Jedna myśl na scenę.
3. **Lektor najpierw** (gdy jest): `python3 $HERMES_HOME/scripts/film.py lektor "<tekst>" -o out/wideo/src/lektor.mp3`
   → czasy słów w `.slowa.json`: animacje ustawiam pod te czasy (zamiast zgadywać).
4. **Budowa:** kompozycja HyperFrames/Manim zgodnie ze skillem silnika; kolory i fonty z brand kitu; źródła w `out/wideo/src/`.
5. **Render:** najpierw podgląd w niskiej jakości, potem MP4 H.264/AAC, 30 fps, docelowa rozdzielczość.
6. **Dźwięk i napisy:** podłożenie lektora/muzyki (`lektor-i-dzwiek`), napisy `napisy.py <film> --slowa out/wideo/src/lektor.slowa.json --wypal`
   (gdy tekst nie jest już animowany na ekranie).
7. **Kontrola** (`kontrola-wideo`): pierwsza klatka jako miniatura, czytelność na telefonie, strefy UI.

## Definition of Done
- [ ] format i długość zgodne z platformą, plik odtwarzalny (`qa_wideo.py` bez błędów),
- [ ] hook w pierwszych 2 s, CTA na końcu, zgodność z marką,
- [ ] tekst na ekranie bez błędów, animacje zsynchronizowane z lektorem,
- [ ] scenariusz i źródła kompozycji w `out/wideo/src/`, `kontrola.json` ≥ 85.
