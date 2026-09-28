---
name: daily-brief
description: "Poranny brief: co w toku, co gotowe, jakie decyzje."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, brief, cron, report]
    related_skills: [decision-queue, mission-ledger]
  jarvo:
    agent: jarvo
    autonomy: A0
    reviewed: "2026-09-26"
---

# Poranny brief

Rutyna cron (dni robocze, rano). Skrypt `fleet_report.py --mode daily` dał Ci dane z ostatnich 24 h.
Jeśli nic się nie dzieje, skrypt nie budzi modelu.

## Format (maks. ~12 linii)
```
☀️ Dzień dobry. Stan floty:
Gotowe od wczoraj: <1 linia na wynik, z efektem, nie z nazwą karty>
W toku: <misje: co, kto, kiedy wynik>
Czeka na Ciebie: <numerowane decyzje z rekomendacją> albo „nic”
Dziś w planie: <rutyny / terminy z misji, jeśli są>
```

## Zasady
- Decyzje z kolejki zawsze na górze sekcji „Czeka na Ciebie” (skill `decision-queue`), z rekomendacjami.
- Liczby tylko, gdy coś znaczą („3 posty gotowe”, nie „2 karty w statusie review”).
- Bez żargonu tablicy. Bez powtarzania wczorajszego briefu, jeśli nic się nie zmieniło.
- Jeśli dane pokazują problem (zablokowane > 1 dnia, awarie), zacznij od niego.
- Skrypt zgłosił błąd → jedna linia: „Nie mogę odczytać tablicy: <błąd>. Sprawdź serwer.”
