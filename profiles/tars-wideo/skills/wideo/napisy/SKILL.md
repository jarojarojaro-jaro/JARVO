---
name: napisy
description: "Napisy PL: z lektora albo transkrypcji, korekta, wypalenie."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [video, captions, subtitles, srt, ass, karaoke]
    related_skills: [krotki-film, montaz-nagran, klipy-z-dlugiego, embedded-captions, formaty-wideo]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Napisy PL

Większość krótkich filmów oglądana jest bez dźwięku, więc napisy są częścią obrazu, nie dodatkiem.
Źródła czasu słów: lektor Edge TTS (w `film.py` automatycznie, co do słowa) albo transkrypcja Parakeet (`tars-stt`).

## Kiedy użyć
- Każdy film z mową. Film z `film.py` ma napisy od razu (`napisy.styl` w planie); ten skill służy nagraniom
  użytkownika, klipom i poprawkom.

## Style
| Styl | Wygląd | Kiedy |
|---|---|---|
| `karaoke` | 1–3 słowa, aktywne w kolorze akcentu, WIELKIE LITERY | TikTok/Reels/Shorts (domyślny) |
| `zwykle` | do 2 linii zdania | LinkedIn, YouTube 16:9, treści eksperckie |
| SRT „miękkie” | plik `.srt` wgrywany na platformę | YouTube, LinkedIn, FB (dostępność, SEO) |

Pozycja domyślna: dół poza strefą opisu i przycisków (9:16: 24% od dołu, szerszy margines z prawej).
Tekst ekranowy (hook) jest u góry i nie koliduje z napisami.

## Kroki
1. **Transkrypcja:** `python3 $HERMES_HOME/scripts/napisy.py <wideo>` → `<wideo>.srt` (+ `.ass`).
2. **Korekta SRT** (obowiązkowa): nazwy własne i marki (z brand kitu), liczby i jednostki, polskie znaki, wulgaryzmy
   (wyciąć albo wygwiazdkować wg karty), podział na sensowne frazy. Czasów nie ruszam, chyba że linia jest pusta.
3. **Wypalenie:** `napisy.py <wideo> --srt <poprawiony.srt> --wypal [--styl zwykle] [--akcent "#FFD400"]
   [--font-plik <font marki>] [--pozycja srodek] [--male]` → `<wideo>.napisy.mp4`.
   Czasy słów z lektora (`film.py lektor` → `.slowa.json`): `--slowa <plik>` zamiast `--srt` (karaoke co do słowa).
4. **Kontrola:** `qa_wideo.py <wynik> --arkusz out/wideo/qa-napisy.jpg` → `vision_analyze`: czytelność na telefonie,
   brak kolizji ze strefami UI (czerwone pola na arkuszu), polskie znaki renderują się poprawnie.

## Wyjścia
- `<wideo>.napisy.mp4`, poprawiony `.srt` (do wgrania na platformę), `.ass` (styl, do poprawek).

## Definition of Done
- [ ] SRT poprawiony ręcznie: zero błędów w nazwach własnych, liczbach i polskich znakach,
- [ ] napisy czytelne na telefonie (kontrast, obrys), poza strefami UI, bez emoji,
- [ ] zsynchronizowane z mową (przesunięcie < 0,3 s na arkuszu i w szkicu).
