---
name: audyt-strony
description: "Audyt strony: Lighthouse, a11y, SEO, linki, obrazy, mobile."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [web, audit, lighthouse, seo, accessibility, performance]
    related_skills: [web-quality-audit, seo-technical, seo-page, core-web-vitals, accessibility, optymalizacja-obrazow]
  tars:
    agent: tars-web
    autonomy: A0
    reviewed: 2026-09-26
---

# Audyt strony

Łączy automaty (skrypty) z oceną eksperta (skille `web-quality-audit`, `seo-technical`, `seo-page`).
Wynik: raport priorytetów, który da się od razu zamienić na karty poprawek.

## Kroki
1. **Automaty:** `bash $HERMES_HOME/scripts/audit.sh <url> out/audyt`
   - Lighthouse mobile + desktop (JSON + HTML),
   - axe-core (pełna lista naruszeń WCAG),
   - linkinator (martwe linki, do 2 poziomów),
   - `seo_check.py` (head, meta, OG, JSON-LD, H1, alt, wymiary obrazów, robots, sitemap, hreflang),
   - zrzuty 375/768/1440 + wykrywanie poziomego przewijania.
   - ✅ Punkt kontrolny: `out/audyt/summary.json` istnieje; błędy narzędzi są opisane, nie przemilczane.
2. **Ocena eksperta:** przejdź checklisty `web-quality-audit` i `seo-technical` z wynikami automatów w ręku.
   Obejrzyj zrzuty (vision): czytelność, hierarchia, CTA, spójność z marką.
3. **Priorytety:**
   - **P0**: blokuje użytkowników albo indeksowanie (noindex przez pomyłkę, błędy 5xx, brak mobile, formularz nie działa),
   - **P1**: duży wpływ (LCP > 4 s, CLS > 0,25, brak title/description na kluczowych stronach, krytyczne a11y),
   - **P2**: średni (obrazy bez AVIF/WebP, brak schema, drobne a11y),
   - **P3**: kosmetyka.
4. **Raport:** `out/RAPORT.md`, w nim tabela: problem · dowód (liczba/zrzut/linia) · wpływ · poprawka · wysiłek (S/M/L).
   Na górze: 3 najważniejsze rzeczy do zrobienia i oczekiwany efekt.

## DoD
- [ ] wyniki Lighthouse mobile i desktop (4 kategorie) w raporcie,
- [ ] lista naruszeń axe pogrupowana (krytyczne/poważne),
- [ ] martwe linki (albo „brak”),
- [ ] każdy problem ma dowód i konkretną poprawkę,
- [ ] priorytety P0–P3 i top 3 na górze.

## Uwagi
- Audytujesz **tylko** wskazane strony. Gdy karta prosi o całą witrynę: weź URL-e z `sitemap.xml`, wybierz
  reprezentatywne (strona główna, po 1–2 z każdego typu, maks. 10) i puść `audit.sh` **po kolei**, nie równolegle
  (jedna Chromium naraz; VPS ma 8 GB RAM).
- Wyniki Lighthouse wahają się: przy wątpliwościach 3 pomiary i mediana.
