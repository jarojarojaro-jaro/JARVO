---
name: przeglad-hackatonow
description: "Przegląd: nowe hackathony, terminy 14 dni, stare wpisy."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [hackathon, monitoring, deadlines, routine]
    related_skills: [radar-hackatonow, ocena-hackatonu]
  jarvo:
    agent: jarvo-hacker
    autonomy: A1
    reviewed: "2026-11-25"
---

# Przegląd hackathonów

## Kiedy użyć
- Rutyna (zakłada ją Jarvo za zgodą właściciela, np. dwa razy w tygodniu) albo „co nowego”, „jakie terminy”.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| baza hackathonów | tak | najpierw `radar-hackatonow` |
| `baza/zrodla.md` (kanały radaru) | nie | utwórz z pliku `platformy.md` w wiedzy skillu `radar-hackatonow` |

## Kroki
1. `hackatony.py terminy --dni 14` i `hackatony.py stare --dni 14`; stare wpisy: strona zasad, poprawka przez `dodaj`
   (pole `wyniki`, gdy regulamin podaje datę ogłoszenia); na koniec `hackatony.py kalendarz out/`.
2. Kanały z `baza/zrodla.md` od daty ostatniego przeglądu; nowe przez szybką ocenę (strona zasad, termin w UTC).
   - ✅ Punkt kontrolny: nic nie trafia do bazy bez strony zasad.
3. Wiadomość najwyżej 8 linii: najpierw zgłoszenia w 72 h z oceną ≥ 6 (godziny do terminu), potem nowe ≥ 7, na
   końcu liczby; nic ważnego → jedna linia „bez zmian, najbliższy termin: …”.

## Wyjścia
- zaktualizowana baza, `out/PRZEGLAD-<data>.md`, wiadomość.

## Definition of Done
- [ ] terminy i stare wpisy sprawdzone, każdy kanał przejrzany albo zapisany powód,
- [ ] wiadomość w limicie 8 linii.
