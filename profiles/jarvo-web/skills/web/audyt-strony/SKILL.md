---
name: audyt-strony
description: "Audyt strony: Lighthouse, a11y, SEO, linki, obrazy, mobile."
version: 1.4.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [web, audit, lighthouse, seo, accessibility, performance]
    related_skills: [web-quality-audit, seo-technical, seo-page, core-web-vitals, accessibility, optymalizacja-obrazow]
  jarvo:
    agent: jarvo-web
    autonomy: A0
    reviewed: "2026-10-14"
---

# Audyt strony

Łączy automaty (skrypty) z oceną eksperta (skille `web-quality-audit`, `seo-technical`, `seo-page`).
Wynik: raport priorytetów, który da się od razu zamienić na karty poprawek.

## Kroki
1. **Automaty:** `bash "$HERMES_HOME/scripts/audit.sh" <url> out/audyt`
   - Lighthouse mobile + desktop (JSON + HTML); w `summary.json` także waga strony (`strona_kb`) i firmy trzecie
     (`firmy_trzecie`: analityka, czaty, piksele, CDN; KB i czas na wątku głównym),
   - axe-core (pełna lista naruszeń WCAG),
   - linkinator (martwe linki, do 2 poziomów),
   - `seo_check.py` (head, meta, OG, JSON-LD, H1, alt, wymiary obrazów, linki wewnętrzne, czyste adresy, robots,
     sitemap, llms.txt, strona 404, obraz OG, landmarki, hreflang); pełna lista widoczności (23 punkty, llms.txt, 404, linki zewnętrzne): `references/widocznosc.md`,
   - `security_check.py url` (nagłówki, HTTPS, wycieki, GPS w zdjęciach; szczegóły: skill `bezpieczenstwo-aplikacji`),
   - zrzuty 375/768/1440 + wykrywanie poziomego przewijania.
   - ✅ Punkt kontrolny: `out/audyt/summary.json` istnieje; błędy narzędzi są opisane, nie przemilczane.
2. **Ocena eksperta:** przejdź checklisty `web-quality-audit` i `seo-technical` z wynikami automatów w ręku.
   Obejrzyj zrzuty (vision): czytelność, hierarchia, CTA, spójność z marką.
   Odporność: `node "$HERMES_HOME/scripts/hostile.cjs" <url> out/audyt/wrogie` (wolne łącze, słaby telefon w działaniu:
   procesor 4× wolniejszy, 4G, klikanie i pisanie, czas reakcji jak INP ≤ 200 ms; brak JS, 320 px, klawiatura, długie
   polskie słowa, reduced motion, konsola); porażki trafiają do priorytetów jak inne problemy. Lighthouse mobile mierzy
   samo wejście na stronę (też na udawanym słabym telefonie), `lowend` w `hostile.cjs` mierzy używanie jej.
   Karta prosi o ocenę designu → dodaj werdykt z `bramka-jakosci` (bez pętli poprawek: audyt nie zmienia strony).
   **Aplikacja z backendem** (logowanie, baza, API): lista `references/wydajnosc-aplikacji.md` (11 punktów: indeksy,
   polityki RLS, N+1, stronicowanie, zapytania równolegle, praca w tle, region serwera przy bazie, cache, treść
   z serwera, szkielety, strumień odpowiedzi AI) z kodem w ręku i `security_check.py repo` (wolne polityki RLS w `*.sql`).
3. **Priorytety:**
   - **P0**: blokuje użytkowników albo indeksowanie (noindex przez pomyłkę, błędy 5xx, brak mobile, formularz nie działa),
   - **P1**: duży wpływ (LCP > 4 s, CLS > 0,25, brak title/description na kluczowych stronach, krytyczne a11y),
   - **P2**: średni (obrazy bez AVIF/WebP, brak schema, drobne a11y, skrypt firmy trzeciej > 100 KB albo > 100 ms
     wątku bez decyzji: usunąć, odłożyć po załadowaniu strony (analityka, czat) albo zostawić z powodem),
   - **P3**: kosmetyka.
4. **Raport:** `out/RAPORT.md`, w nim tabela: problem · dowód (liczba/zrzut/linia) · wpływ · poprawka · wysiłek (S/M/L).
   Na górze: 3 najważniejsze rzeczy do zrobienia i oczekiwany efekt.

## DoD
- [ ] wyniki Lighthouse mobile i desktop (4 kategorie) w raporcie,
- [ ] lista naruszeń axe pogrupowana (krytyczne/poważne),
- [ ] martwe linki (albo „brak”),
- [ ] każdy problem ma dowód i konkretną poprawkę,
- [ ] priorytety P0–P3 i top 3 na górze,
- [ ] aplikacja z backendem: sekcja „Wydajność backendu” z 11 punktami (✓ z dowodem, ✗ z poprawką, n/d z powodem).

## Uwagi
- Audytujesz **tylko** wskazane strony. Gdy karta prosi o całą witrynę: weź URL-e z `sitemap.xml`, wybierz
  reprezentatywne (strona główna, po 1–2 z każdego typu, maks. 10) i puść `audit.sh` **po kolei**, nie równolegle
  (jedna Chromium naraz: każda bierze kilkaset MB pamięci, a komputer może mieć tylko 8 GB).
- Wyniki Lighthouse wahają się: przy wątpliwościach 3 pomiary i mediana.
