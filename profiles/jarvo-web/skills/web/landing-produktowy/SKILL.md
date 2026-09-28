---
name: landing-produktowy
description: "Landing produktu pod SEO i konwersję, z danymi z researchu."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [web, landing, seo, cro, product]
    related_skills: [nowa-strona, seo-page, seo-schema, seo-content-brief, cro, site-architecture]
  jarvo:
    agent: jarvo-web
    autonomy: A1
    reviewed: "2026-09-28"
---

# Landing produktowy

Wariant `nowa-strona` nastawiony na **jedną frazę główną i jedną konwersję**.

## Wejścia (z karty)
- raport `jarvo-sherlock` (rynek + `slowa-kluczowe.csv`), brand kit, nazwa produktu, CTA, ewentualnie copy od `jarvo-studio`.
- Brak researchu słów kluczowych → nie zgaduj. `kanban_block(kind="needs_input")`: „potrzebny research SEO albo fraza główna”.

## Struktura (domyślna, dopasuj do produktu)
1. **Hero:** H1 z frazą główną w naturalnym brzmieniu, obietnica w 1 zdaniu, CTA, wizual produktu.
2. **Problem → rozwiązanie** (język klienta z „głosu klienta” w raporcie Sherlocka).
3. **Korzyści** (3–5, konkretne), **jak to działa** (3 kroki).
4. **Dowody:** opinie, liczby, logotypy, certyfikaty (tylko prawdziwe, z karty/brand kitu).
5. **Oferta/cena** (jeśli jest), **FAQ** z pytań z researchu SEO (schema FAQPage tylko przy prawdziwych FAQ).
6. **CTA końcowe.**

## SEO on-page (skill `seo-page`)
- title ≤ 60 znaków (fraza główna na początku), description 140–160 znaków z korzyścią i CTA,
- jeden H1; H2 z fraz pobocznych, jeśli naturalne; URL krótki z frazą,
- schema `Product` (+ `Offer`, jeśli cena), `Organization`, `BreadcrumbList`, `FAQPage` (skill `seo-schema`),
- obrazy: alt opisowe, nazwy plików opisowe, AVIF/WebP, OG image 1200×630 (od `jarvo-studio` albo roboczy),
- linkowanie wewnętrzne, jeśli strona jest częścią serwisu (`site-architecture`).

## Konwersja (skill `cro`)
Jedno główne CTA powtórzone 2–3 razy, formularz minimalny, brak rozpraszaczy (menu uproszczone), zaufanie przy CTA.

## DoD
DoD z `nowa-strona` (w tym `bramka-jakosci` ≥ 90) + fraza główna w title/H1/URL/description, schema przechodzi walidację (JSON-LD poprawny składniowo, typy zgodne z treścią).
