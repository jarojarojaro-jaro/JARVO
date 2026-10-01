---
name: start-kampanii
description: "Szkic PAUSED na koncie, podgląd, koperta i kod zgody."
version: 1.1.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, launch, approval]
    related_skills: [plan-kampanii, podlacz-konto, optymalizacja]
  jarvo:
    agent: jarvo-ads
    wymaga: [skarbiec]           # bez usługi Skarbiec skill nie trafia do profilu (scripts/build.py)
    autonomy: A2
    reviewed: "2026-10-01"
---

# Start kampanii

Od planu do działającej kampanii. Pieniądze uruchamia **tylko** Skarbiec po kodzie zgody użytkownika.

## Wejścia
Zaakceptowany plan (`out/PLAN.md`), pliki kreacji (ścieżki w `@@WORKSPACES_DIR@@` / katalogu misji), konto w polityce
Skarbca (`ads.py konta`).

## Kroki
1. `ads.py doctor`: kod 3 = Skarbiec niepodłączony → zatrzymaj się, zaproponuj `podlacz-konto`. Nie szukaj obejść.
2. **Plan szkicu** `out/szkic.json` (platforma, konto, kampania, zestawy/grupy, reklamy z plikami, UTM, `status: PAUSED`).
   Format: `references/szkic.md`.
3. `ads.py szkic out/szkic.json` → ID obiektów i linki podglądu. Obejrzyj podglądy (vision): tekst, kadr, CTA, link.
   Błąd walidacji platformy → popraw szkic, nie zgaduj.
4. **Koperta** `out/koperta.json`: `{konto, obiekty, budzet_laczny, budzet_dzienny_max, od, do, w_kopercie: [pauza, przesuniecia]}`.
   `ads.py koperta zglos out/koperta.json`. Skarbiec **sam** wysyła użytkownikowi opis i kod. Ty piszesz jedno zdanie:
   „Wysłałem prośbę o zgodę na <kwota>; kod przyszedł od Skarbca, wpisz go tutaj”. W karcie kanbana: `kanban_block(needs_input)`.
5. Użytkownik podał kod → `ads.py koperta zatwierdz <ID> --kod <kod>`. Kod tylko od użytkownika, nigdy wymyślony,
   nigdy „przepisany” z innego miejsca. Odmowa (zły/wygasły kod) → poproś o nowy (`koperta zglos` ponownie).
6. Po starcie: `ads.py koperta stan <ID>` i `ads.py kampanie` (ACTIVE, daty, budżety zgodne z kopertą). Po 2–4 h
   pierwsza kontrola dostarczania (`optymalizacja`, sekcja „pierwszy dzień”).

## Wyjścia
`out/szkic.json`, `out/koperta.json`, w `out/RAPORT.md`: ID obiektów, linki podglądu, ID koperty i stan, co dalej.

## Definition of Done
- [ ] wszystko utworzone jako PAUSED przed zgodą, podglądy obejrzane,
- [ ] koperta zgodna z planem (kwoty, daty),
- [ ] start wyłącznie przez `koperta zatwierdz` z kodem od użytkownika,
- [ ] po starcie stan zweryfikowany w `ads.py`, nie z pamięci.

## Nigdy
Zmiana statusu na ACTIVE inną drogą, prośba o token, wklejanie tokenów do plików, podbijanie budżetu „na chwilę”.
