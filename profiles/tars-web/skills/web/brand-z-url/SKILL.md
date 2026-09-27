---
name: brand-z-url
description: "Brand kit z istniejącej strony: logo, kolory, fonty, ton."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [web, brand, design-tokens, design-md]
    related_skills: [design-md, audyt-strony]
  tars:
    agent: tars-web
    autonomy: A1
    reviewed: "2026-09-26"
---

# Brand kit z URL

Wynik: `@@KNOWLEDGE_DIR@@/brands/<slug>/` (wspólna wiedza: korzysta też `tars-studio`).
Szablon: `@@KNOWLEDGE_DIR@@/brands/_szablon/BRAND.md`.

## Kroki
1. **Slug marki:** małe litery, myślniki (np. `nova-kosmetyki`). Sprawdź, czy kit już istnieje. Jeśli tak, aktualizujesz go, nie nadpisujesz w ciemno.
2. **Ekstrakcja tokenów:** `bash $HERMES_HOME/scripts/brand_extract.sh <url> <slug>`. Skrypt uruchamia dembrandt
   (`--design-md --dtcg --wcag --crawl 3`), zapisuje `DESIGN.md`, `tokens.json`, raport kontrastu i zrzuty.
   - ✅ Punkt kontrolny: `DESIGN.md` i `tokens.json` istnieją, paleta ma kolor główny i kolor tekstu.
3. **Logo:** znajdź w `<head>` (favicon, apple-touch-icon, `og:image`) i w nagłówku strony (SVG/PNG).
   Zapisz do `logo/` (oryginały + `logo.svg` jeśli jest wektor). Nie generuj logo od nowa.
4. **Zrzuty:** `node $HERMES_HOME/scripts/screenshots.cjs <url> <kit>/screenshots` (375/768/1440).
5. **Ton komunikacji:** przeczytaj stronę główną i 2–3 podstrony (`extract`/przeglądarka): forma zwracania się,
   długość zdań, słowa charakterystyczne, obietnice. Wpisz do BRAND.md → „Ton komunikacji”. Nie wymyślaj; tylko to, co widać.
6. **BRAND.md:** wypełnij szablon (tożsamość, wizualne, ton, produkty). `approved_by_owner: false`.
7. **product-marketing.md:** kontekst produktu dla skilli marketingowych (kim jest klient, problem, obietnica,
   wyróżniki, dowody), tylko z tego, co wynika ze strony, a braki oznacz `TODO`.

## Wyjścia
`BRAND.md`, `DESIGN.md`, `tokens.json`, `product-marketing.md`, `logo/`, `screenshots/`, `wcag.json` + `out/RAPORT.md` z listą braków.

## DoD
- [ ] kolory (≥ główny, akcent, tło, tekst) z kodami HEX i źródłem (token CSS / obserwacja),
- [ ] fonty z nazwą i źródłem (Google Fonts / self-hosted / systemowy),
- [ ] logo w najlepszej dostępnej jakości,
- [ ] ton opisany na podstawie cytatów ze strony,
- [ ] braki jawnie oznaczone `TODO` (np. brak wersji ciemnej logo).
