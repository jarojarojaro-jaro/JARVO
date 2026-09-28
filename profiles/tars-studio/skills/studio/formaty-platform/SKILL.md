---
name: formaty-platform
description: "Wymiary, długości i limity znaków platform social i web."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [marketing, social, formats, specs]
    related_skills: [grafika-social, copy-pl]
  tars:
    agent: tars-studio
    autonomy: A0
    reviewed: "2026-09-26"
---

# Formaty platform

Tabela: `references/specs.md` (sprawdzana co kwartał; platformy zmieniają zasady, więc przy wątpliwościach
sprawdź aktualną dokumentację platformy i zaktualizuj tabelę w repo).

## Użycie
1. Z karty ustal platformy i typ publikacji (post, karuzela, stories/reels, miniatura, OG, reklama).
2. Z tabeli weź wymiary, proporcje, długość, limity tekstu i **bezpieczne strefy** (UI platformy zasłania krawędzie w 9:16).
3. Po wyprodukowaniu: `python3 $HERMES_HOME/scripts/check_media.py out/ --spec <klucz>` sprawdza wymiary, długość i wagę plików.

## Zasady ogólne
- Projektuj w natywnej rozdzielczości (1080 px szerokości dla social), eksport PNG dla grafik z tekstem, JPEG/WebP dla zdjęć.
- Tekst na grafikach: min. ~40 px przy 1080 px szerokości; kontrast WCAG AA.
- 9:16: kluczowa treść w środkowym obszarze ~1080×1420 (margines ~250 px góra i dół na UI).
- Wideo: robi `tars-wideo` (skill `formaty-wideo`); tabela niżej służy do briefu i kontroli okładek.
