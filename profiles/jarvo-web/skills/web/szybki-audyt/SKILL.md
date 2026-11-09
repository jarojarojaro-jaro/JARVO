---
name: szybki-audyt
description: "Pierwszy audyt strony: podstawy w kilka minut, raport 1 str."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [web, audit, seo, images, responsive]
    related_skills: [audyt-strony, optymalizacja-obrazow]
  jarvo:
    agent: jarvo-web
    autonomy: A0
    reviewed: "2026-11-09"
---

# Szybki audyt strony

**Kiedy:** pierwszy audyt strony albo karta mówi „szybki audyt” / „audyt podstaw”. Pełny `audyt-strony`
tylko wtedy, gdy karta wprost go zamawia (głęboki audyt).

Wynik skryptu **jest** audytem. Ty dokładasz najwyżej 2 uwagi wizualne i jedną linię „Do głębszej analizy”.
Budżet: ok. 6 wywołań narzędzi i 10 minut.

## Kroki
1. `@@PY@@ "$HERMES_HOME/scripts/szybki_audyt.py" <katalog strony> --out out/`: klon repo strony
   (`public_html` z `.strona.json`, z niego domena) albo `dist/` projektu. Ok. 3–10 s; tworzy `out/raport.md`,
   `out/audyt.json`, `out/zrzuty/` i `out/zrzuty.jpg` (telefon 390 px i komputer 1440 px obok siebie, razem 1600 px).
2. **Jedno** wywołanie wzroku na `out/zrzuty.jpg`. Coś wyraźnie zepsute (nakładające się elementy, ucięty
   tekst, pusty ekran)? Dopisz do `raport.md` sekcję `## Uwagi wizualne` z najwyżej 2 punktami. Nic → nic nie dopisujesz.
   Twardy limit karty: **2 wywołania wzroku** (`vision_analyze` i `browser_vision` razem): montaż i najwyżej jedno
   przybliżenie (`out/zrzuty/390.png` albo `1440.png`), gdy montaż pokazuje podejrzany problem. Trzecie blokuje
   strażnik wtyczki `jarvo-wiedza`; czego nie rozstrzygniesz, zapisz słowami jako podejrzenie w „Uwagi wizualne”
   albo „Do głębszej analizy” i oddaj kartę.
3. Dopisz na końcu `raport.md` jedną linię `Do głębszej analizy: …` (tematy spoza podstaw, np. dostępność,
   Core Web Vitals na żywo, treści).
4. Oddaj kartę: `raport.md` i `audyt.json` w `out/` karty.

## Granice
- Bez Lighthouse, axe, crawla, własnych skryptów i przeglądania repo (`ls`, `grep`, `cat`).
- Najwyżej 1 zapytanie HEAD do strony na żywo, opcjonalnie.
- Strony nie zmieniasz.
- Raport zostaje na ok. 1 stronę; liczb skryptu nie przepisujesz ani nie poprawiasz ręcznie.

## DoD
1. `out/raport.md` istnieje i ma tabelę 9 obszarów oraz `## 5 najważniejszych poprawek` (5 albo mniej, gdy mniej problemów).
2. Liczby w `raport.md` są te same co w `out/audyt.json` (raport nie edytowany poza uwagami wizualnymi i linią „Do głębszej analizy”).
3. Zrzuty są w `out/zrzuty/` i `out/zrzuty.jpg` albo `raport.md` podaje powód ich braku („Zrzuty pominięte: …”).
