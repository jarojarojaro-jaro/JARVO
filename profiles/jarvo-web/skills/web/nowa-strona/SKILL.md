---
name: nowa-strona
description: "Nowa strona od briefu do podglądu (Astro, mobile-first)."
version: 1.2.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [web, astro, build, frontend]
    related_skills: [systematic-debugging, frontend-design, design-md, popular-web-designs, favicon-i-meta, optymalizacja-obrazow, audyt-strony, wdrozenie, animate, gsap-core, gsap-scrolltrigger, threejs-fundamentals]
  jarvo:
    agent: jarvo-web
    autonomy: A1
    reviewed: "2026-09-30"
---

# Nowa strona

## Kroki
1. **Brief → plan strony** (`out/PLAN.md`): cel, odbiorca, sekcje (kolejność i treść każdej), CTA, brand kit, języki.
   Brak treści? Roboczy tekst oznaczony `[SZKIC]` (copy docelowe robi `jarvo-studio`).
2. **Kierunek wizualny:** brand kit (`DESIGN.md`, tokeny) → zasady z `frontend-design`. Brak brand kitu → wybierz
   bazę z `popular-web-designs`, uzasadnij w PLAN.md i zapytaj przez `kanban_block(kind="needs_input")`, jeśli wybór jest kluczowy.
3. **Szkielet (Astro):**
   ```bash
   cd out && npm create astro@latest site -- --template minimal --no-install --no-git --skip-houston --yes
   cd site && npm install
   ```
   Tokeny marki jako CSS custom properties (`src/styles/tokens.css`). Bez ciężkich frameworków UI, jeśli niepotrzebne.
   Zanim powstanie pierwszy commit: `.gitignore` z `.env*` i `!.env.example`, sekrety tylko w `.env`, w repo `.env.example`
   z pustymi wartościami. Nowa zależność: najpierw sprawdź w rejestrze, że istnieje i jest znana (nie ufaj nazwie od modelu).
4. **Budowa sekcji:** semantyczny HTML, mobile-first, `<picture>` z AVIF/WebP (`optymalizacja-obrazow`),
   formularze z etykietami, widoczny fokus, `prefers-reduced-motion`.
5. **Head:** skill `favicon-i-meta` (komplet ikon, manifest, OG, JSON-LD Organization/WebSite, canonical, lang).
6. **Build i podgląd:** `npm run build` → `npx astro preview --host 0.0.0.0 --port 4321` (w tle) albo statyczny serwer z `dist/`.
   Build, skrypt albo test pada → `systematic-debugging`: najpierw przyczyna (odtworzenie, jedna hipoteza naraz),
   potem jedna poprawka; bez zgadywania kolejnych zmian.
7. **Kontrola jakości:** `audyt-strony` na podglądzie → popraw do budżetów → zapisz wyniki przed/po.
   Potem `bramka-jakosci`: rubryka designu (≥ 90) i testy wrogie, rundy poprawek do zaliczenia.
8. **Raport:** `out/RAPORT.md` (co powstało, jak uruchomić, wyniki, samokontrola DoD). Wdrożenie tylko przez `wdrozenie` (A2).

## DoD (domyślne, karta może zaostrzyć)
- [ ] `npm run build` bez błędów,
- [ ] Lighthouse mobile ≥ 90 × 4 kategorie,
- [ ] zrzuty 375/768/1440 bez poziomego przewijania,
- [ ] komplet head (favicony, manifest, OG, JSON-LD, canonical, lang),
- [ ] widoczność: `robots.txt` (bez `Disallow: /`), `sitemap.xml`, `llms.txt`, czyste adresy, ≥ 3 linki wewnętrzne
  (`seo_check.py` bez błędów; lista: skill `audyt-strony`, `widocznosc.md`),
- [ ] bezpieczeństwo: `security_check.py url` bez KRYTYCZNYCH i WYSOKICH; aplikacja z backendem: skill `bezpieczenstwo-aplikacji`,
- [ ] zgodność z brand kitem, tekst roboczy oznaczony `[SZKIC]`,
- [ ] `bramka-jakosci`: ostatnia runda ≥ 90 (`out/jakosc/werdykt-runda-N.json`), testy wrogie bez porażek albo opisane.
