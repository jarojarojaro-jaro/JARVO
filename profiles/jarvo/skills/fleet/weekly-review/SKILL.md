---
name: weekly-review
description: "Przegląd tygodnia: jakość floty, wnioski, propozycje."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, retro, quality, cron]
    related_skills: [fleet-improvement, mission-ledger]
  jarvo:
    agent: jarvo
    autonomy: A0
    reviewed: "2026-09-28"
---

# Przegląd tygodnia

Rutyna cron (niedziela wieczorem). Skrypt `fleet_report.py --mode weekly` dał Ci dane z 7 dni,
w tym `quality`: dla każdego agenta liczba zakończonych kart, recenzji, poprawek i akceptacji
za pierwszym razem.

## Co przygotować
1. **Wynik tygodnia:** zamknięte misje (efekty, nie karty), co utknęło i dlaczego.
2. **Jakość agentów:** akceptacja za 1. razem = `first_pass / done`. Poniżej 60% → przejrzyj
   komentarze sędziego z tych kart (`kanban_show`) i znajdź **powtarzający się** wzorzec błędu.
3. **Wnioski → księga lekcji → propozycje** (skill `fleet-improvement`): nowe obserwacje dopisz do
   `@@KNOWLEDGE_DIR@@/fleet/lekcje.md`, usuń lekcje bez potwierdzenia od 60 dni; propozycje (maks. 3) tylko
   dla lekcji z ≥ 3 potwierdzeniami, każda z dowodem (które karty, jaki błąd).
4. **Pamięć:** przejrzyj wpisy swojej pamięci. Wpis bez źródła i daty uzupełnij albo usuń; wpis, który przeczy
   nowszym faktom, popraw. Nic nie usuwasz z `USER.md` bez pytania użytkownika.
5. **Koszty** (jeśli dostępne przez `/insights` albo raport OpenRouter): krótko, bez wyliczanek.

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
