---
name: kwalifikacja
description: "Kwalifikacja: odsiew szumu, dopasowanie, świeżość, siła."
version: 1.0.0
author: "Jarvo (metoda za superdesigndev/treg lead-signals, Apache-2.0)"
license: MIT
metadata:
  hermes:
    tags: [leads, qualification, scoring, b2b]
    related_skills: [sygnaly, profil-klienta, lista-leadow]
  jarvo:
    agent: jarvo-lowca
    autonomy: A1
    reviewed: "2026-09-30"
---

# Kwalifikacja

Lista sygnałów to nie lista leadów: zwykle **odpada ponad połowa**. Kolejność oceny: najpierw **dopasowanie** (brak
dopasowania = brak wiersza), potem **świeżość** (sygnał sprzed tygodnia bije sygnał sprzed kwartału), potem **siła**
(dwa niezależne sygnały na jednej firmie biją jeden); przy remisie wyżej firma z opublikowanym kontaktem. Liczy to `leady.py ocen` według `ICP.yaml`; Ty sprawdzasz,
czy liczby mają sens.

## Kroki
1. `python3 $HERMES_HOME/scripts/leady.py ocen <projekt> --top 30` → `leady.csv`, `LEADY.md`.
2. Przejrzyj czołówkę (top 30) i próbkę odrzuconych: szukasz fałszywych dopasowań (nazwa zawiera słowo, ale to inna
   branża; firma w likwidacji; konkurent użytkownika; własny klient). Poprawiasz **ICP** (wykluczenia, próg, wagi),
   nie wynik ręcznie, i liczysz od nowa.
3. Dla czołówki zweryfikuj sygnał w źródle (otwórz link): czy data i treść się zgadzają.
4. „Dlaczego teraz” słowami użytkownika dla czołówki: `leady.py powod <projekt> <klucz> "nowa spółka IT bez strony,
   założona 3 dni temu"`. Jedno zdanie, konkretne, bez przymiotników.
5. Zapisz pokrycie z `LEADY.md` („N sygnałów → M firm → K po dopasowaniu”) i powody największych odrzutów.

## Definition of Done
- [ ] czołówka sprawdzona w źródłach, fałszywe dopasowania usunięte przez poprawkę ICP (zapisaną w `ICP.md`),
- [ ] „dlaczego teraz” własnymi słowami dla co najmniej 10 pierwszych firm (albo wszystkich, jeśli mniej),
- [ ] pokrycie i główne powody odrzutów w raporcie.
