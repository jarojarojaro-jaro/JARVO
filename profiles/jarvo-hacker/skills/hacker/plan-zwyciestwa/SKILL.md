---
name: plan-zwyciestwa
description: "Plan pod jury: pomysł, tracki, zakres na godziny, podział."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [hackathon, strategy, judging, sponsor-tracks, planning]
    related_skills: [ocena-hackatonu, budowa-projektu, zgloszenie]
  jarvo:
    agent: jarvo-hacker
    autonomy: A1
    reviewed: "2026-11-25"
---

# Plan zwycięstwa

## Kiedy użyć
- Hackathon oceniony ≥ 6 i @@WLASCICIEL@@ albo Jarvo mówi „startujemy” (status `kandydat` → `zapisani` po rejestracji).

## Kiedy NIE używać
- Hackathon nieoceniony → najpierw `ocena-hackatonu`.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| wpis w bazie z oceną | tak | `ocena-hackatonu` |
| kryteria jury, tracki, wymagania | tak | ze strony zasad; brak kryteriów = użyj typowych z `references/jak-wygrywac.md` |

## Kroki
1. **Jury i sponsorzy:** kryteria z wagami, kto ocenia, tracki z warunkami (wymagane API, SDK, sieć), które tracki się
   łączą; zwycięzcy poprzedniej edycji (galeria projektów) i co ich łączyło.
2. **3 pomysły**, każdy z mapą „funkcja → kryterium / track”; wybierz jeden: największe pokrycie kryteriów, demo
   widoczne w 30 sekund, wykonalny w 60% czasu.
   - ✅ Punkt kontrolny: każda funkcja MVP ma kryterium albo track; funkcje bez nich wypadają.
3. **Harmonogram w UTC** od teraz do terminu: MVP (60%), demo i film (20%), README, opis, zgłoszenie (20%);
   zgłoszenie gotowe 6 h przed terminem.
4. **Podział pracy:** co buduję sam (`budowa-projektu`), co zamawiam przez Jarva (Web: frontend; Wideograf: film demo
   ze scenariusza; Studio: deck i grafiki); każda część z terminem.
5. **Ryzyka i cięcia:** lista funkcji do wycięcia w kolejności, plan B dla zależności (API sponsora, limity, klucze).
6. `out/<id>/PLAN.md`, status `budujemy`, oddanie do oceny Jarva (z prośbą o karty dla floty).
7. **Udział człowieka:** wymagania regulaminu (narracja głosem, uzasadnienie pomysłu, obecność) to osobne zadania dla
   @@WLASCICIEL@@ z godziną w harmonogramie; limit nagród na projekt (Devpost często 1, ETHGlobal do 3 partnerów)
   decyduje, ile tracków ma sens.

## Wyjścia
- `out/<id>/PLAN.md` (pomysł, mapa kryteriów, harmonogram UTC, podział, cięcia).

## Definition of Done
- [ ] mapa funkcja → kryterium/track,
- [ ] harmonogram w UTC z buforem 6 h,
- [ ] podział pracy z terminami i lista cięć.

## Wiedza
- `references/jak-wygrywac.md`: kryteria jury, wzorce zwycięzców, sponsor tracki, ryzyka dyskwalifikacji.
