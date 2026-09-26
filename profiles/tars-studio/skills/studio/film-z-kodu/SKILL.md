---
name: film-z-kodu
description: "Film z kodu: scenariusz, storyboard, render, napisy, QA."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [video, hyperframes, manim, ffmpeg, captions]
    related_skills: [hyperframes, product-launch-video, faceless-explainer, motion-graphics, embedded-captions, manim-video, generacja-ai]
  tars:
    agent: tars-studio
    autonomy: A1
    reviewed: 2026-09-26
---

# Film z kodu

## Wybór silnika
| Potrzeba | Silnik |
|---|---|
| promo produktu, reels z tekstem i animacją, launch | **HyperFrames** (`hyperframes`, `product-launch-video`, `motion-graphics`) |
| explainer bez nagrań (tekst → wideo) | HyperFrames `faceless-explainer` |
| matematyka, algorytmy, wykresy w ruchu | **Manim** (`manim-video`) |
| cięcie nagrań, łączenie, napisy, formaty | **FFmpeg** (+ `auto-editor`, `scripts/subtitles.py`) |
| ujęcia fotorealistyczne / b-roll | generacja AI (`generacja-ai`), potem montaż |

HyperFrames: `media-use` (muzyka, lektor, stock) wymaga zalogowanego CLI HeyGen. Bez tego używaj własnych
materiałów, zdjęć/ilustracji z AI i lektora TTS (narzędzie `text_to_speech`).

## Kroki
1. **Brief:** platforma i format (`formaty-platform`), długość, cel, jedno przesłanie, CTA, brand kit.
2. **Scenariusz** (`out/wideo/SCENARIUSZ.md`): hook 0–2 s → problem → rozwiązanie → dowód → CTA; tekst lektora i napisy.
3. **Storyboard:** tabela scen (czas, obraz, tekst na ekranie, animacja, dźwięk). Maksymalnie 1 myśl na scenę.
4. **Budowa:** kompozycja HyperFrames/Manim zgodnie ze skillem silnika; kolory i fonty z brand kitu.
5. **Render:** MP4 H.264/AAC, 30 fps, docelowa rozdzielczość. Najpierw podgląd w niskiej jakości, potem finał.
6. **Napisy:** `python3 $HERMES_HOME/scripts/subtitles.py wideo.mp4 --burn` (transkrypcja faster-whisper → SRT → wypalenie),
   korekta tekstu SRT przed wypaleniem.
7. **QA:** `check_media.py` (rozdzielczość, długość, waga), obejrzyj klatki kluczowe (vision): pierwsza klatka jako
   miniatura, czytelność napisów, brak obciętych elementów w bezpiecznej strefie.

## DoD (domyślne)
- [ ] format i długość zgodne z platformą, plik odtwarzalny (ffprobe bez błędów),
- [ ] hook w pierwszych 2 s, CTA na końcu, zgodność z marką,
- [ ] napisy poprawne (PL), czytelne na telefonie,
- [ ] scenariusz i źródła kompozycji w `out/wideo/src/`.
