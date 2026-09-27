---
name: optymalizacja-obrazow
description: "Obrazy: AVIF/WebP, srcset, wymiary, lazy loading, kompresja."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [web, images, performance, avif, webp, srcset]
    related_skills: [seo-images, core-web-vitals, performance]
  tars:
    agent: tars-web
    autonomy: A1
    reviewed: "2026-09-26"
---

# Optymalizacja obrazów

```bash
node $HERMES_HOME/scripts/images.cjs <plik|katalog> out/img --widths 480,960,1440,1920 --formats avif,webp,jpg --quality 70
```
Wynik: warianty plików + `out/img/manifest.json` (dla każdego obrazu: wymiary, warianty, gotowy `<picture>`).

## Zasady
- **Format:** AVIF (pierwszy) → WebP → JPEG/PNG (fallback). Grafiki z przezroczystością: AVIF/WebP/PNG. Ikony i logo: SVG (`svgo`).
- **Szerokości:** tylko te, które strona naprawdę wyświetla (hero pełnej szerokości: 480–1920; miniatury: 320–640).
- **`sizes`** zgodne z layoutem (np. `(max-width: 768px) 100vw, 50vw`), inaczej przeglądarka pobiera za dużo.
- **Wymiary** (`width`/`height`) zawsze, bo zapobiegają skokom layoutu (CLS).
- **LCP:** obraz hero bez lazy loading, z `fetchpriority="high"`; pozostałe `loading="lazy"` + `decoding="async"`.
- **Jakość:** zacznij od 70 (AVIF 50–60), porównaj wizualnie (vision) przy zdjęciach produktów.
- **Alt:** opisowy dla treści, pusty (`alt=""`) dla dekoracji.

## DoD
- [ ] każdy obraz ma AVIF i WebP (albo uzasadnienie),
- [ ] `<picture>`/`srcset`/`sizes` i wymiary w kodzie,
- [ ] łączna waga obrazów strony w raporcie przed/po.
