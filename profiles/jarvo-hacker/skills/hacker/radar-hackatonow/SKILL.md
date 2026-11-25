---
name: radar-hackatonow
description: "Szukaj hackathonów i konkursów do wygrania, do bazy."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [hackathon, bounty, kaggle, radar, research]
    related_skills: [ocena-hackatonu, przeglad-hackatonow]
  jarvo:
    agent: jarvo-hacker
    autonomy: A1
    reviewed: "2026-11-25"
---

# Radar hackathonów

## Kiedy użyć
- „Znajdź hackathony”, „co jest do wygrania”, pierwsza praca radaru albo poszerzenie bazy o nową kategorię.

## Kiedy NIE używać
- Jeden konkretny hackathon → `ocena-hackatonu`; rutynowy przegląd → `przeglad-hackatonow`.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| zakres (kategorie, okno dat) | nie | wszystkie kategorie z `references/platformy.md`, zgłoszenia w ciągu 90 dni |

## Kroki
1. `hackatony.py lista` (co już mamy) i `references/platformy.md` (gdzie szukać i jak czytać automatycznie).
2. **Fan-out:** do 3 subagentów naraz, każdy na grupę platform (AI i agenty; web3; Kaggle, dane i GPU; Polska i UE;
   bounty), z formatem JSONL z `references/format.md` i wymogiem strony zasad jako źródła.
   - ✅ Punkt kontrolny: każda grupa ma wpisy albo zdanie, dlaczego nic nie pasuje.
3. **Sprawdzenie:** dla każdego wpisu strona hackathonu i zasady (rules, FAQ, terms): termin zgłoszenia w UTC (strefę
   z regulaminu przelicz), pula i tracki, solo, kod AI, kod sprzed hackathonu, kraj, KYC, tryb.
4. **Baza:** `hackatony.py dodaj out/nowe.jsonl`; od razu szybka ocena 0–10 z powodem (`hackatony.py ocen`), pełna
   tylko dla ≥ 6 (`ocena-hackatonu`).
5. `hackatony.py eksport out/` i `out/RADAR.md`: top 5 do startu (termin, pula, dlaczego wygramy), terminy 14 dni,
   co odrzucone i dlaczego (KYC, onsite, zakaz AI).

## Wyjścia
- `out/nowe.jsonl`, `out/HACKATONY.md`, `out/hackatony.csv`, `out/RADAR.md`.

## Definition of Done
- [ ] ≥ 20 hackathonów w bazie ze stroną zasad, terminem w UTC i datą sprawdzenia,
- [ ] każda grupa platform sprawdzona,
- [ ] top 5 z oceną i powodem, terminy 14 dni osobno.

## Typowe błędy
- Termin w strefie organizatora wpisany jako UTC → zawsze przelicz.
- Pula z posta na X bez strony hackathonu → tylko trop, `[niezweryfikowane]` w notatkach.
- „Online” bez sprawdzenia finału na miejscu → sprawdź, czy finał lub odbiór nagrody wymaga obecności.

## Wiedza
- `references/platformy.md`: platformy, kalendarze, konta na X, kanały do automatycznego czytania.
- `references/format.md`: format wpisu JSONL.
