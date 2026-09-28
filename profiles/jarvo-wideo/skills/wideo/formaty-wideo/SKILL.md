---
name: formaty-wideo
description: "Formaty wideo platform: wymiary, długość, strefy UI."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, formats, platforms, safe-zones, specs]
    related_skills: [krotki-film, kontrola-wideo, napisy, montaz-nagran]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Formaty wideo platform

Format przed kreacją: najpierw platforma, proporcje, długość i strefy interfejsu, potem scenariusz i kadry.
Tabela platform: `references/specs.md` (zgodna z `qa_wideo.py --platforma`).

## Kiedy użyć
- Na starcie każdego filmu, przy zamianie formatu (16:9 → 9:16) i przy pakiecie na kilka platform.

## Zasady techniczne (wszystkie platformy)
- MP4, H.264 High, `yuv420p`, 30 fps (24/25 dla materiału filmowego, 60 dla gier/sportu), AAC 48 kHz 192 kb/s,
  `+faststart`. `film.py` i `montaz.py` robią to domyślnie.
- Głośność −14 LUFS, true peak ≤ −1 dBTP.
- Pierwsza klatka = miniatura w wielu miejscach: hook i tekst od klatki 0, nie czarna plansza.
- Plik < 250 MB dla krótkich formatów (zwykle 5–30 MB).

## Strefy interfejsu 9:16 (TikTok, Reels, Shorts)
- góra ~10%: zakładki i status; dół ~20%: opis, nazwa konta, dźwięk; prawy pasek (od ~45% do ~80% wysokości,
  ostatnie ~14% szerokości): przyciski. Ważny tekst i logo w środkowym obszarze.
- `qa_wideo.py --arkusz` zaznacza te strefy na czerwono; napisy `film.py` i `napisy.py` omijają je domyślnie.

## Wiele platform z jednego materiału
- Kręcone/generowane pod 9:16 → 1:1 i 4:5 przez przycięcie góry i dołu (tekst w środku kadru!).
- 16:9 → 9:16: `montaz.py kadr --x <środek obiektu>` albo `--tryb rozmyte` (slajdy, ekran, dwie osoby).
- `film.py render --format 9:16,16:9`: osobne ujęcia stock dla każdej orientacji (lepsze niż przycinanie).

## Definition of Done
- [ ] format, długość i parametry zgodne z tabelą dla każdej platformy z karty,
- [ ] ważne elementy poza strefami UI (arkusz `qa_wideo.py` obejrzany),
- [ ] osobny plik na platformę, gdy wymagania się różnią; nazwa pliku zawiera format.
