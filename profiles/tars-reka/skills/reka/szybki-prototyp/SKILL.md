---
name: szybki-prototyp
description: "Mały skrypt/narzędzie/automat: działa, sprawdzony, opisany."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [prototype, scripting, automation]
    related_skills: [kiedy-oddac-snajperowi]
  tars:
    agent: tars-reka
    autonomy: A1
    reviewed: 2026-09-26
---

# Szybki prototyp

Dla „zrób mi coś, co…”: jednorazowe narzędzie, przeliczenie, automat, arkusz.

## Zasady
1. **Najmniejsza rzecz, która działa:** Python/Bash z biblioteki standardowej, zanim sięgniesz po zależności.
2. **Uruchom i pokaż wynik** na prawdziwych danych albo przykładzie; wynik w RAPORT.md.
3. **README w 5 liniach:** co robi, jak uruchomić, wejście, wyjście, ograniczenia.
4. **Bez sekretów w kodzie**; klucze tylko przez zmienne środowiskowe.
5. **Bez akcji zewnętrznych** (wysyłki, zapisy do cudzych systemów) bez zgody (A2); prototyp domyślnie działa „na sucho”.
6. Gdy prototyp ma stać się czymś stałym (strona, rutyna, produkt), zaproponuj to TARS-owi jako osobne zlecenie.
