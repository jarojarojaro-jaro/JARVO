---
name: przeglad-okazji
description: "Przegląd: nowe okazje, terminy 30 dni, stare wpisy."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fundraising, monitoring, deadlines, routine]
    related_skills: [baza-okazji, ocena-okazji]
  jarvo:
    agent: jarvo-bigshort
    autonomy: A1
    reviewed: "2026-11-25"
---

# Przegląd okazji

## Kiedy użyć
- Rutyna (zakłada ją Jarvo za zgodą właściciela, np. raz w tygodniu) albo prośba „co nowego”, „jakie terminy”.

## Kiedy NIE używać
- Pierwsza mapa dla projektu → `mapa-finansowania`.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| baza okazji z ocenami projektów | tak | najpierw `mapa-finansowania` |
| lista obserwowanych źródeł `baza/zrodla.md` | nie | utwórz ze startowej listy w `references/zrodla-obserwowane.md` |

## Kroki
1. `okazje.py terminy --dni 30` i `okazje.py stare --dni 60`.
2. Wpisy stare: otwórz stronę programu, popraw termin i kwotę (`dodaj` z tym samym `id`), zamknięte → `status zamkniete`.
3. Obserwowane źródła: przejdź listę z `baza/zrodla.md` (strony programów, kanały RSS, konta zbierające okazje),
   tylko wpisy od daty ostatniego przeglądu; każda nowa okazja przez `ocena-okazji` w skrócie (źródło pierwotne!).
   - ✅ Punkt kontrolny: nic nie trafia do bazy bez strony programu.
4. Wiadomość: najwyżej 8 linii, najpierw terminy ≤ 14 dni z oceną ≥ 7, potem nowe okazje ≥ 7, na końcu liczby
   (sprawdzone, nowe, zamknięte). Nic ważnego → jedna linia „bez zmian, najbliższy termin: …”.

## Wyjścia
- zaktualizowana baza, `out/PRZEGLAD-<data>.md`, wiadomość.

## Definition of Done
- [ ] terminy i stare wpisy sprawdzone,
- [ ] każde obserwowane źródło przejrzane albo zapisane, czemu nie,
- [ ] wiadomość w limicie 8 linii.

## Wiedza
- `references/zrodla-obserwowane.md`: startowa lista źródeł do śledzenia (strony programów, agregatory, konta na X).
