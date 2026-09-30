---
name: monitoring-leadow
description: "Monitoring leadów: rutyna, tylko nowe firmy od bazy."
version: 1.0.0
author: "Jarvo (metoda za superdesigndev/treg lead-signals, Apache-2.0)"
license: MIT
metadata:
  hermes:
    tags: [leads, monitoring, cron, signals]
    related_skills: [sygnaly, lista-leadow]
  jarvo:
    agent: jarvo-lowca
    autonomy: A1
    reviewed: "2026-09-30"
---

# Monitoring leadów

„Pilnuj przetargów na…”, „co tydzień nowe spółki z…”. Monitoring to rutyna cron (tworzy ją Jarvo po zgodzie
użytkownika, dostarcza wynik), która raportuje **tylko nowe firmy** względem bazy (`baza.json` w projekcie).

## Konfiguracja (jednorazowo, w karcie)
1. Projekt z `ICP.yaml` w `@@WORKSPACES_DIR@@/jarvo-lowca/leady/<projekt>/` (skill `profil-klienta`).
2. Przepis przebiegu w `<projekt>/PRZEBIEG.md`: te same polecenia `krs.py`, `przetargi.py`, wyszukiwania co w `sygnaly`,
   z oknem równym częstotliwości (codziennie: wczorajszy biuletyn; co tydzień: 7 dni BZP).
3. **Pierwszy przebieg to baza:** `leady.py ocen <projekt> --monitoring` zapisuje klucze i mówi „to jest baza”.
   Zmierz koszt (zapytania, czas) i podaj go jako cenę jednego przebiegu.
4. Zaproponuj harmonogram (domyślnie dni robocze rano) z kosztem; Jarvo tworzy rutynę po akceptacji użytkownika.

## Każde uruchomienie
1. Sygnały z okna → `leady.py dodaj` → `leady.py ocen <projekt> --monitoring --top 15`.
2. Kontakt (`kontakt-firmy`) tylko dla nowych firm z czołówki.
3. Nic nowego → `[SILENT]`. Nowe firmy → 3–8 linii: firma, dlaczego teraz, kontakt, źródło; link do `LEADY.md`.
4. Źródło odmówiło (kod 3) → jedna linia w raporcie; bez obchodzenia.

## Definition of Done
- [ ] baza zapisana w pierwszym przebiegu, koszt przebiegu podany,
- [ ] kolejne przebiegi pokazują tylko nowe klucze (albo `[SILENT]`),
- [ ] harmonogram zaakceptowany przez użytkownika (rutyna przez Jarva).
