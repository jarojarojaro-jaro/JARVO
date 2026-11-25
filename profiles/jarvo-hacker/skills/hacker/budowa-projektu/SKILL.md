---
name: budowa-projektu
description: "Buduj projekt na hackathon: MVP, demo, testy, w terminie."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [hackathon, build, mvp, demo, coding]
    related_skills: [plan-zwyciestwa, zgloszenie]
  jarvo:
    agent: jarvo-hacker
    autonomy: A1
    reviewed: "2026-11-25"
---

# Budowa projektu

## Kiedy użyć
- Jest `out/<id>/PLAN.md` i status `budujemy`.

## Kiedy NIE używać
- Brak planu → `plan-zwyciestwa`. Frontend ponad MVP, film, grafiki → zamówienie przez Jarva.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| plan z harmonogramem | tak | `plan-zwyciestwa` |
| klucze API sponsorów | gdy plan ich wymaga | `kanban_block` `needs_input` z dokładnym kluczem i powodem; nigdy w treści karty |

## Kroki
1. **Repo** w `projekty/<id>/` (git, licencja zgodna z regulaminem, `README.md` od pierwszej godziny), pierwszy commit
   z datą w oknie hackathonu; zależności i nasze wcześniejsze skrypty wypisane w `README.md` („co istniało wcześniej”).
2. **Najkrótsza ścieżka demo** najpierw: jedna historia użytkownika od początku do końca, potem reszta funkcji
   w kolejności z planu.
   - ✅ Punkt kontrolny co 25% czasu: demo działa od zera (`make demo` albo jedno polecenie z README); jeśli nie,
     tniesz następną funkcję z listy cięć.
3. **Integracje sponsorów** zgodnie z warunkami tracków (dowód użycia w kodzie i w demo).
4. **Testy dymne** i nagranie surowego przebiegu demo (zrzuty, log) jako materiał dla Wideografa.
5. **Zamrożenie** 8 h przed terminem: od tej chwili tylko poprawki, które ratują demo.

## Wyjścia
- `projekty/<id>/` (kod, README, polecenie demo), `out/<id>/demo/` (zrzuty, przebieg demo, log).

## Definition of Done
- [ ] demo działa od zera jednym poleceniem,
- [ ] każda funkcja z planu albo zbudowana, albo jawnie wycięta,
- [ ] wcześniejszy kod i AI ujawnione w README zgodnie z regulaminem,
- [ ] zamrożenie 8 h przed terminem.

## Typowe błędy
- Budowanie infrastruktury zamiast demo → jedna historia end to end najpierw.
- Klucz API w repo → zmienne środowiskowe, `.env` w `.gitignore`, sprawdzenie przed pierwszym pushem.
- Cudzy kod skopiowany bez licencji → zależność z licencją albo własny kod.
