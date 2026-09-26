---
name: weekly-review
description: "Przegląd tygodnia: jakość floty, wnioski, propozycje."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [fleet, retro, quality, cron]
    related_skills: [fleet-improvement, mission-ledger]
  tars:
    agent: tars
    autonomy: A0
    reviewed: 2026-09-26
---

# Przegląd tygodnia

Rutyna cron (niedziela wieczorem). Skrypt `fleet_report.py --mode weekly` dał Ci dane z 7 dni,
w tym `quality`: dla każdego agenta liczba zakończonych kart, recenzji, poprawek i akceptacji
za pierwszym razem.

## Co przygotować
1. **Wynik tygodnia:** zamknięte misje (efekty, nie karty), co utknęło i dlaczego.
2. **Jakość agentów:** akceptacja za 1. razem = `first_pass / done`. Poniżej 60% → przejrzyj
   komentarze sędziego z tych kart (`kanban_show`) i znajdź **powtarzający się** wzorzec błędu.
3. **Wnioski → propozycje** (skill `fleet-improvement`): maks. 3 konkretne propozycje zmian
   w skillach/SOUL/DoD agentów, każda z dowodem (które karty, jaki błąd).
4. **Koszty** (jeśli dostępne przez `/insights` albo raport OpenRouter): krótko, bez wyliczanek.

## Format
```
📊 Tydzień floty
Zrobione: <2–4 linie>
Jakość: sherlock 5/6 za 1. razem, web 3/5 (powtarza się: brak zrzutów mobile), studio 4/4
Proponuję ulepszyć:
1. <agent>: <zmiana> (<dowód>)
Decyzja: wdrożyć propozycje 1–2? (zmiany trafią do repo i na serwer po Twoim „ok”)
```

Brak aktywności w tygodniu → `[SILENT]`.
