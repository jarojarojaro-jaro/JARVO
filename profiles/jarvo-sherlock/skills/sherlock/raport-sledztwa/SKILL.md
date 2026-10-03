---
name: raport-sledztwa
description: "Format raportu: odpowiedź, dowody, pewność, luki, źródła."
version: 1.1.0
author: "Jarvo (zasady cytowania inspirowane open_deep_research, MIT)"
license: MIT
metadata:
  hermes:
    tags: [research, report, citations]
    related_skills: [metoda-sherlocka, weryfikacja-faktow, cytowania]
  jarvo:
    agent: jarvo-sherlock
    autonomy: A1
    reviewed: "2026-10-03"
---

# Raport śledztwa

Plik: `out/RAPORT.md`. Szablon: `references/RAPORT.template.md`.

## Zasady
1. **Odpowiedź najpierw.** Pierwszy akapit odpowiada na pytanie z karty, z poziomem pewności.
2. **Każde twierdzenie faktograficzne ma przypis** `[n]` z rejestru źródeł (skill `cytowania`). Twierdzenie bez
   źródła ma znacznik `[niezweryfikowane]`; opinia jest oznaczona jako opinia.
3. **Numery z rejestru, stałe:** jedno źródło = jeden numer od pobrania do oddania. Mogą mieć przerwy (źródło
   przeczytane, ale niewykorzystane). Blok „Źródła” generuje `sources.py render --replace-in out/RAPORT.md`.
4. **Nie gub informacji:** jeśli 3 źródła mówią X, napisz „trzy niezależne źródła podają X [2][5][7]”.
5. **Sprzeczności i luki mają własną sekcję.** „Nie udało się ustalić” to wynik, nie porażka.
6. **Daty:** przy danych zmiennych w czasie zawsze „stan na <data>”.
7. **Rekomendacja** (jeśli karta prosi o decyzję) oddzielona od faktów.
8. Długość: tyle, ile trzeba. Streszczenie ≤ 10 zdań; szczegóły w sekcjach.
9. **Sprawdzenie przed oddaniem:** `sources.py verify out/RAPORT.md --min-coverage 0.5` kończy się „cytowania OK”,
   a linia `info:` z wyniku trafia do sekcji „Metoda”.

## Dla Jarva
Jarvo relacjonuje wyniki użytkownikowi, więc pierwszy akapit i sekcja „Rekomendacja” muszą być
zrozumiałe bez reszty raportu.
