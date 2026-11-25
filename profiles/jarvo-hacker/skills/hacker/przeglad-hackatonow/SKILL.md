---
name: przeglad-hackatonow
description: "Raport dnia: nowe hackathony, do wzięcia, nasze starty."
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
- Codzienna rutyna `hacker-terminy` (8:30) albo „co nowego”, „w co wchodzimy”, „jak idą nasze hackathony”.
- Cel (właściciel 25.11): jest hackathon, do którego możemy wejść i wygrać, to działamy; w którym startujemy, ten śledzisz.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| baza hackathonów | tak | najpierw `radar-hackatonow` |
| `baza/zrodla.md` (kanały radaru) | nie | utwórz z pliku `platformy.md` w wiedzy skillu `radar-hackatonow` |

## Kroki
1. `hackatony.py stare --dni 14`; stare wpisy: strona zasad, poprawka przez `dodaj` (zmieniony termin, pula,
   tracki, pole `wyniki`); hackathon po terminie wejścia albo poza naszym zasięgiem → `status … odpuszczony` z powodem.
2. Kanały z `baza/zrodla.md` od daty ostatniego przeglądu; nowe przez szybką ocenę (strona zasad, termin w UTC,
   `ocen` z powodem).
   - ✅ Punkt kontrolny: nic nie trafia do bazy bez strony zasad.
3. `hackatony.py raport` i wiadomość najwyżej 15 linii:
   - **Do wzięcia teraz:** do 5 najlepszych z raportu, numer, nazwa z linkiem, pula, termin wejścia w UTC, ocena
     i jedno zdanie, czemu możemy wygrać; nowe z doby oznacz „nowy”;
   - **Nasze starty:** każdy z następnym krokiem i terminem (`ustaw krok=… krok_do=…` przed raportem, gdy brak);
   - na końcu jedno pytanie: w który wchodzimy (numer), albo decyzja potrzebna w naszym starcie.

## Wyjścia
- zaktualizowana baza, `out/PRZEGLAD-<data>.md`, wiadomość.

## Definition of Done
- [ ] terminy i stare wpisy sprawdzone, każdy kanał przejrzany albo zapisany powód,
- [ ] wiadomość w limicie 15 linii, z listą do wzięcia i naszymi startami.
