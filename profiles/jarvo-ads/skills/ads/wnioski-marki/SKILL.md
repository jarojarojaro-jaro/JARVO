---
name: wnioski-marki
description: "Wnioski z reklam do brand kitu: co działa, z dowodem."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, learnings]
    related_skills: [raport-reklam, plan-testu]
  jarvo:
    agent: jarvo-ads
    autonomy: A1
    reviewed: "2026-09-29"
---

# Wnioski marki

Pamięć reklamowa marki, z której korzystają Studio i Wideograf przed nową kreacją.

## Gdzie
`@@KNOWLEDGE_DIR@@/brands/<marka>/reklamy/WNIOSKI.md` (utwórz, jeśli brak; marka = katalog brand kitu).

## Format wpisu
```
## <RRRR-MM-DD> · <test/kampania> · pewność: wysoka|średnia|niska
Wniosek: <jedno zdanie, co działa lepiej>
Dowód: <metryka, wartości A vs B, P(najlepszy), okres, wydatek>, raport: <ścieżka>
Zakres: <platforma, odbiorcy, format>; jedna zmienna / pakiet
Dla kreacji: <konkretna wskazówka: np. „ruch w 1. sekundzie, bez planszy logo na starcie”>
```

## Zasady
- pewność wysoka tylko przy P ≥ 95% i ≥ 2 testach w tym samym kierunku; jeden test = średnia; sygnał/remis = niska,
- wniosek sprzeczny z wcześniejszym: nie kasuj starego, dopisz nowy i oznacz konflikt,
- na górze pliku sekcja „Najważniejsze” (maks. 7 punktów), aktualizowana przy każdym wpisie.

## Definition of Done
- [ ] wpis po każdym zakończonym teście i kampanii,
- [ ] dowód z liczbami i ścieżką raportu,
- [ ] „Najważniejsze” aktualne.
