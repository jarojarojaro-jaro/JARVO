---
name: grafika-social
description: "Grafiki social/OG z kodu HTML→PNG w brand kicie, warianty."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [design, social, graphics, html-to-png, brand]
    related_skills: [formaty-platform, canvas-design, theme-factory, image, generacja-ai]
  tars:
    agent: tars-studio
    autonomy: A1
    reviewed: "2026-09-26"
---

# Grafiki social z kodu

Grafiki z tekstem, logo i danymi robisz jako **HTML/CSS renderowany do PNG**: ostre litery, dokładne kolory
marki, łatwe warianty i wersje językowe. Zdjęcia/ilustracje z AI (`generacja-ai`) wstawiasz jako tło lub element.

## Kroki
1. **Brief grafiki:** cel, platforma (`formaty-platform`), komunikat (1 myśl), CTA, elementy obowiązkowe (logo, cena, data).
2. **Szablon:** skopiuj `$HERMES_HOME/skills/studio/grafika-social/templates/base.html` do workspace (zmienne CSS z tokenów marki: `--brand-primary`, `--brand-bg`,
   `--font-heading`…). Tokeny weź z `@@KNOWLEDGE_DIR@@/brands/<marka>/tokens.json` / `DESIGN.md`.
3. **Kompozycja:** hierarchia (nagłówek → wsparcie → CTA), siatka z marginesem ≥ 64 px, maksymalnie 2 kroje pisma,
   kontrast AA, logo w stałym miejscu. Zasady estetyki: `canvas-design`, `theme-factory`.
4. **Render:**
   ```bash
   node $HERMES_HOME/scripts/render_html.cjs grafika.html out/grafiki/post --size 1080x1350 --size 1080x1920 --size 1200x630
   ```
   Jeden plik HTML, wiele formatów: layout reaguje na proporcje (CSS `@container` / media queries po `aspect-ratio`).
5. **Kontrola:** `check_media.py` + obejrzenie każdego PNG (vision): czytelność na telefonie, obcięcia, literówki.
6. **Warianty:** 2–3 dla grafiki głównej (inny nagłówek albo inny układ), z rekomendacją w RAPORT.md.

## Wyjścia
`out/grafiki/<nazwa>-<szer>x<wys>.png`, źródła HTML w `out/grafiki/src/`, opis w `out/INDEX.md`.
