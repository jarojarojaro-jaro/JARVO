---
name: nowa-strona
description: "Nowa strona od briefu do podglądu (Astro, mobile-first)."
version: 1.5.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [web, astro, build, frontend]
    related_skills: [systematic-debugging, inspiracje-stron, frontend-design, design-md, popular-web-designs, favicon-i-meta, optymalizacja-obrazow, audyt-strony, wdrozenie, animate, gsap-core, gsap-scrolltrigger, threejs-fundamentals]
  jarvo:
    agent: jarvo-web
    autonomy: A1
    reviewed: "2026-10-05"
---

# Nowa strona

## Kroki
1. **Brief → plan strony** (`out/PLAN.md`): cel, odbiorca, sekcje (kolejność i treść każdej), CTA, brand kit, języki.
   Brak treści? Roboczy tekst oznaczony `[SZKIC]` (copy docelowe robi `jarvo-studio`).
2. **Inspiracje → kierunek wizualny.** Najpierw skill `inspiracje-stron`: 3–5 prawdziwych stron z branży klienta
   (katalog Inspo, serwer MCP `inspo`, albo własna baza w skarbcu) i sekcja „Inspiracje” w PLAN.md: co bierzemy, czego nie.
   Potem brand kit (`DESIGN.md`, tokeny) → zasady z `frontend-design`; z inspiracji tylko układ, rytm i skala, nic kopiowanego.
   Brak brand kitu → wybierz bazę z `popular-web-designs`, uzasadnij w PLAN.md i zapytaj przez
   `kanban_block(kind="needs_input")`, jeśli wybór jest kluczowy.
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
5. **Head i widoczność:** skill `favicon-i-meta` (komplet ikon, manifest, OG, JSON-LD Organization/WebSite, canonical,
   lang) w jednym layoucie; każda podstrona podaje własny `title` i `description` (nigdy kopii ze strony głównej).
   Layout ma landmarki: `<header>`, `<nav>`, jeden `<main>`, `<footer>`. Do tego, zanim powstanie pierwszy podgląd:
   - `site: "https://domena.pl"` w `astro.config.mjs` (brak domeny: adres z karty, notatka w RAPORT.md)
     i `npx astro add sitemap --yes` (`sitemap-index.xml` w buildzie),
   - `public/robots.txt`: `User-agent: *`, `Allow: /`, `Sitemap: https://domena.pl/sitemap-index.xml`,
   - `public/llms.txt` wg szablonu z `audyt-strony/references/widocznosc.md`,
   - `src/pages/404.astro`: ten sam layout, krótki tekst, link do strony głównej, `<meta name="robots" content="noindex">`,
   - obraz OG 1200×630 (PNG albo JPEG) w `public/og.png`: od `jarvo-studio` albo roboczy (zrzut sekcji hero
     przycięty do 1200×630), roboczy oznaczony w RAPORT.md.
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
- [ ] widoczność: `seo_check.py --dir dist --base-url <adres produkcyjny>` bez błędów (każda strona: własny title
  i description, canonical, obraz OG 1200×630, landmarki; witryna: `404.html`, `robots.txt` bez `Disallow: /`, sitemap,
  `llms.txt`) i `seo_check.py <adres podglądu> --podglad` bez błędów (nieistniejący adres daje 404, obraz OG się
  pobiera), czyste adresy, ≥ 3 linki wewnętrzne (lista: skill `audyt-strony`, `widocznosc.md`),
- [ ] bezpieczeństwo: `security_check.py url` bez KRYTYCZNYCH i WYSOKICH, `security_check.py repo` bez zdjęć z GPS; aplikacja z backendem: skill `bezpieczenstwo-aplikacji`,
- [ ] zgodność z brand kitem, tekst roboczy oznaczony `[SZKIC]`,
- [ ] `bramka-jakosci`: ostatnia runda ≥ 90 (`out/jakosc/werdykt-runda-N.json`), testy wrogie bez porażek albo opisane.
