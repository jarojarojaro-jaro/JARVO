---
name: klipy-z-dlugiego
description: "Klipy z długiego nagrania: transkrypcja, wybór, cięcie."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [video, repurpose, clips, podcast, webinar, shorts]
    related_skills: [montaz-nagran, napisy, scenariusz, kontrola-wideo, formaty-wideo]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Klipy z długiego nagrania

Podcast, webinar, wywiad, live (10–120 min) → 3–10 krótkich klipów 9:16 z napisami. Wybór fragmentów robię ja,
na podstawie transkrypcji z czasami; cięcie, kadr i napisy robią skrypty.

## Kiedy użyć
- „Zrób shorty z tego podcastu”, „wytnij najlepsze momenty”, „klipy z webinaru na LinkedIn”.

## Kiedy NIE używać
- Nagranie krótsze niż ~3 min → `montaz-nagran`. Materiał z YouTube cudzego kanału bez praw → nie tniemy (blokada z powodem).

## Kroki
1. **Transkrypcja:** `python3 $HERMES_HOME/scripts/montaz.py transkrypcja <nagranie> -o out/wideo/src/transkrypcja --co 20`
   (Parakeet, ~1–2 min na 10 min nagrania; `.txt` z czasami do czytania, `.slowa.json` do napisów).
2. **Kandydaci** (czytam `.txt`): fragmenty 20–60 s, które stoją same bez kontekstu. Szukam: mocna teza,
   liczba/konkret, historia z puentą, kontrowersja, praktyczna rada, zabawna wymiana. Dla każdego: start, koniec,
   hook (pierwsze zdanie), ocena 1–10 i jedno zdanie „dlaczego zadziała”. Min. 2× więcej kandydatów niż klipów.
   - ✅ Punkt kontrolny: klip zaczyna się od zdania-hooka (nie od „no i”, „tak jak mówiłem”), kończy puentą.
   - Nagranie z wypalonymi napisami: nie dodawaj drugich (kolizja po zmianie kadru); poproś o wersję „czystą”.
3. **Wybór** najlepszych N (różne tematy, nie 3 × to samo); tabela w `out/wideo/KLIPY.md`.
4. **Kadr mówcy:** `kadry.py arkusz <nagranie> --klatek 6` → `vision_analyze`: gdzie jest twarz (x 0–1); zmiana ujęć
   w nagraniu: `kadry.py sceny <nagranie>`.
5. **Dla każdego klipu:**
   `montaz.py wytnij <nagranie> -o out/wideo/src/klip-N.mp4 --zakresy "<start>-<koniec>"` →
   `montaz.py kadr out/wideo/src/klip-N.mp4 -o out/wideo/src/klip-N-pion.mp4 --x <x>` (dwie osoby: `--tryb rozmyte`) →
   `napisy.py out/wideo/src/klip-N-pion.mp4` → korekta SRT → `napisy.py … --srt <poprawiony> --wypal` →
   `montaz.py glosnosc … --lufs -14`.
6. **Kontrola** (`kontrola-wideo`) każdego klipu; tytuł i 1-zdaniowy opis każdego klipu (szkic) w KLIPY.md.

## Wyjścia
- `out/wideo/klipy/klip-N-<slug>.mp4` (+ `.srt`), `out/wideo/KLIPY.md` (kandydaci, wybrane, czasy, oceny, opisy),
  transkrypcja w `out/wideo/src/`.

## Definition of Done
- [ ] każdy klip zrozumiały bez reszty nagrania, z hookiem na starcie i puentą na końcu,
- [ ] mówca w kadrze przez cały klip; napisy poprawione ręcznie (nazwy własne, liczby),
- [ ] `qa_wideo.py` bez błędów dla każdego klipu; KLIPY.md z czasami źródła (do weryfikacji kontekstu).
