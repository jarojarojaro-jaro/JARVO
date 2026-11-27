---
name: kdenlive
description: "Montaż w Kdenlive: najpierw melt (MLT) skryptem, okno Kdenlive na pulpicie do podglądu i poprawek."
version: 1.0.0
author: "Jarvo (program: Kdenlive i MLT, KDE, GPL-3.0)"
license: MIT
metadata:
  hermes:
    tags: [video, kdenlive, mlt, melt, montage, vertical, captions, desktop]
  jarvo:
    autonomy: A1
    reviewed: "2026-11-27"
---

# Kdenlive i melt

Kdenlive 26.08 to AppImage z manifestu (pobiera się przy pierwszym użyciu); w środku jest `melt`, który renderuje to samo co okno Kdenlive.

## Najpierw melt
```bash
M="$HERMES_HOME/skills/pulpit/kdenlive/scripts/melt.py"
# pionowa wersja 9:16 z napisem (kadr ze środka), eksport MP4
@@PY@@ "$M" wejscie.mp4 -profile vertical_hd_30 -filter crop center=1 \
  -attach dynamictext:"Tekst napisu" geometry=0%/75%:100%x15% halign=center valign=middle size=72 fgcolour=0xffffffff \
  -consumer avformat:out/pion.mp4 vcodec=libx264 acodec=aac preset=veryfast threads=2
# fragment: in i out w klatkach źródła; kilka plików po kolei to po prostu kilka plików w poleceniu
@@PY@@ "$M" a.mp4 in=0 out=299 b.mp4 -mix 15 -mixer luma -profile vertical_hd_30 -consumer avformat:out/film.mp4 vcodec=libx264 acodec=aac
# zapis planu jako projekt MLT (XML), który otworzysz w Kdenlive albo wyrenderujesz później
@@PY@@ "$M" wejscie.mp4 -profile vertical_hd_30 -filter crop center=1 -consumer xml:out/plan.mlt
@@PY@@ "$M" out/plan.mlt -consumer avformat:out/pion.mp4 vcodec=libx264 acodec=aac
```
- Profile: `vertical_hd_30` (1080×1920, 30 kl./s), `atsc_1080p_30` (1920×1080), `square_1080p_30` (1080×1080).
- Render długi (więcej niż kilka minut): najpierw mówisz właścicielowi, ile potrwa.
- Wynik sprawdzasz `ffprobe` (rozmiar, długość, dźwięk) i klatką `ffmpeg -ss 2 -frames:v 1`, zanim go oddasz.

## Okno Kdenlive (pulpit)
- `pulpit` akcja `uruchom` z `program: kdenlive` i `argumenty: [pełna ścieżka projektu .kdenlive albo .mlt]` otwiera go do podglądu.
- Kdenlive (Qt) daje drzewo elementów dla menu, przycisków i pól; oś czasu i monitor to płótno, więc tam klikasz `xy` z obrazu i powiększasz `obszar`.
- Skróty: spacja odtwarza, ctrl+enter renderuje (okno Render), ctrl+s zapisuje, shift+r tnie klip pod głowicą.
- Poprawki z okna zapisujesz jako projekt i renderujesz melt z tego projektu, żeby wynik był powtarzalny.
- Filmy floty montuje Wideograf w swoim projekcie edytora (`projekt.py`); Kdenlive jest do zleceń, które go wprost wymagają, i do formatów, których edytor nie ma.
