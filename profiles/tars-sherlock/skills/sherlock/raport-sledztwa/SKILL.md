---
name: raport-sledztwa
description: "Format raportu: odpowiedź, dowody, pewność, luki, źródła."
version: 1.0.0
author: "Jarvo (zasady cytowania inspirowane open_deep_research, MIT)"
license: MIT
metadata:
  hermes:
    tags: [research, report, citations]
    related_skills: [metoda-sherlocka, weryfikacja-faktow, grounded-citations]
  tars:
    agent: tars-sherlock
    autonomy: A1
    reviewed: "2026-09-26"
---

# Raport śledztwa

Plik: `out/RAPORT.md`. Szablon: `references/RAPORT.template.md`.

## Zasady
1. **Odpowiedź najpierw.** Pierwszy akapit odpowiada na pytanie z karty, z poziomem pewności.
2. **Każde twierdzenie faktograficzne ma przypis** `[n]` do listy źródeł. Bez przypisu = opinia, oznaczona jako opinia.
3. **Numeracja źródeł ciągła** (1, 2, 3…), jedno źródło = jeden numer; lista generowana przez `sources.py cite`.
4. **Nie gub informacji:** jeśli 3 źródła mówią X, napisz „trzy niezależne źródła podają X [2][5][7]”.
5. **Sprzeczności i luki mają własną sekcję.** „Nie udało się ustalić” to wynik, nie porażka.
6. **Daty:** przy danych zmiennych w czasie zawsze „stan na <data>”.
7. **Rekomendacja** (jeśli karta prosi o decyzję) oddzielona od faktów.
8. Długość: tyle, ile trzeba. Streszczenie ≤ 10 zdań; szczegóły w sekcjach.

## Dla Jarva
Jarvo relacjonuje wyniki użytkownikowi, więc pierwszy akapit i sekcja „Rekomendacja” muszą być
zrozumiałe bez reszty raportu.
