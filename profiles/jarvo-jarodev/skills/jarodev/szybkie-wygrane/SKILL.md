---
name: szybkie-wygrane
description: "Szybki audyt strony firmy: 3 łatwe wygrane z dowodem."
version: 0.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [seo, performance, audit, sales]
    related_skills: [mapy-firmy, oferta-szkic, lejek]
  jarvo:
    agent: jarvo-jarodev
    autonomy: A0
    reviewed: "2026-11-14"
---

# Szybki audyt publicznej strony: trzy łatwe wygrane

Cel to argument do oferty, nie pełny audyt: trzy konkretne rzeczy, które jarodev poprawi szybko i które właściciel
firmy zrozumie („strona ładuje się 6,8 s na telefonie”, „brak opisu w Google”). Pełny audyt (dostępność, linki,
bezpieczeństwo) to praca `jarvo-web` po podpisaniu zlecenia.

## Kiedy użyć
- firma z Map ma stronę, firma z posta podała adres, właściciel pyta „co poprawić na <url>”.

## Kiedy NIE używać
- pełny audyt, wdrożenie, poprawki na stronie → `jarvo-web` przez Jarva.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| adres strony (http/https) | tak | z wizytówki albo z posta |
| limit `audyty` dziennie | tak | domyślny z `lejek.py` |

## Kroki
1. `lejek.py licz audyty --limit <limity.audyty>` (kod 3 = nie dziś).
2. Audyt (ok. 10 s; z Lighthouse ok. 1 min, jeden przebieg mobilny):
   ```bash
   @@PY@@ "$HERMES_HOME/scripts/wygrane.py" <url> --web-skrypty "@@REPO_DIR@@/profiles/jarvo-web/scripts" \
     --lighthouse --out out/audyty/<domena>
   ```
   Skrypt woła `seo_check.py` Web (strona, robots.txt, sitemap, 404, obraz OG: kilka zapytań, bez pełzania)
   i jeden Lighthouse; układa wygrane: wolna strona na telefonie → błędy SEO → ostrzeżenia, najwyżej jedna z obszaru
   w trójce. Kod 3 = strona nie odpowiada: zapisz to jako fakt („strona nie działa: <błąd>”), bez zgadywania przyczyny.
   - ✅ Każda z trzech wygranych ma liczbę albo cytat ze strony i źródło (`dowod`).
3. Sprawdź jedną wygraną sam (protokół floty, zasada 12): np. `web_extract` strony i title/description w treści,
   zanim napiszesz ją w ofercie. Wynik niesprawdzony = „niesprawdzone” w raporcie.
4. Wpis w lejku: `lejek.py dodaj --zrodlo audyt --rodzaj firma --nazwa "<firma>" --miasto <m> --link <url>
   --potrzeba "<wygrana nr 1 w jednym zdaniu>"` (albo `--uwaga` przy istniejącym wpisie z Map).
5. Strona w dobrym stanie (brak wygranych) → nie dodajesz wpisu; to też liczba w raporcie.

## Wyjścia
- `out/audyty/<domena>/WYGRANE.md`, `wygrane.json`, `seo.json`, `lighthouse.json` (gdy był).

## Definition of Done
- [ ] trzy wygrane z dowodem (albo zapis „brak łatwych wygranych”), jedna sprawdzona ręcznie,
- [ ] żadnej obietnicy pozycji w Google ani ceny w tekście wygranych,
- [ ] audyt policzony w `licz`; bez Lighthouse uwaga „szybkość niezmierzona” w raporcie.

## Typowe błędy
- Wygrana bez liczby („strona jest wolna”) → bierzesz liczbę z `wygrane.json` albo jej nie piszesz.
- Pełny `audit.py` Web na stronie obcej firmy → za ciężki i pełza po witrynie; tu tylko `wygrane.py`.
