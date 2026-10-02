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
    reviewed: "2026-10-02"
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
- TikTok: góra ~7% (zakładki), dół ~25% (opis, nazwa konta, dźwięk), prawo ~13% (przyciski), lewo ~4%.
  Shorts: góra ~9%, dół ~20%, prawo ~11%. Reels (zalecenie Meta): góra 14%, dół 35%, boki 6%.
  Ważny tekst i logo w środkowym obszarze. Liczby: `wideo_lib.STREFY_UI` (te same pokazuje edytor HQ).
- `qa_wideo.py --arkusz` zaznacza na czerwono strefy `--platforma` (bez niej TikTok), `pomiar.py` zgłasza tekst pod nimi;
  napisy `film.py` i `napisy.py` omijają je domyślnie, tekst z `projekt.py` startuje na 0,68 wysokości.

## Wiele platform z jednego materiału
- Kręcone/generowane pod 9:16 → 1:1 i 4:5 przez przycięcie góry i dołu (tekst w środku kadru!).
- 16:9 → 9:16: `montaz.py kadr --x <środek obiektu>` albo `--tryb rozmyte` (slajdy, ekran, dwie osoby); w projekcie edytora
  `projekt.py kadr <id> --wypelnij --fx X` albo `--rozmyte` (nowy klip o innych proporcjach dostaje rozmyte tło sam).
- `film.py render --format 9:16,16:9`: osobne ujęcia stock dla każdej orientacji (lepsze niż przycinanie).

## Definition of Done
- [ ] format, długość i parametry zgodne z tabelą dla każdej platformy z karty,
- [ ] ważne elementy poza strefami UI (arkusz `qa_wideo.py` obejrzany),
- [ ] osobny plik na platformę, gdy wymagania się różnią; nazwa pliku zawiera format.
