---
name: kontakt-firmy
description: "Kontakt opublikowany przez firmę: e-mail, tel., formularz."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [leads, contact, company-website, gdpr]
    related_skills: [kwalifikacja, lista-leadow]
  jarvo:
    agent: jarvo-lowca
    autonomy: A1
    reviewed: "2026-09-30"
---

# Kontakt do firmy

Kontakt szukasz **tylko dla firm, które przeszły kwalifikację**, i bierzesz wyłącznie to, co firma sama opublikowała
(strona, stopka, zespół, kontakt) albo co jest w rejestrze (KRS: e-mail i strona, jeśli firma je podała). Każdy kontakt
ma adres źródła. Adresów nie zgadujesz, nie kupujesz, nie wyciągasz z serwisów za logowaniem.

## Kroki
1. Strona firmy: z sygnału (`www`), z KRS (`krs.py odpis <KRS> --json`) albo z wyszukiwarki (`"<nazwa firmy>" <miasto>`;
   sprawdź NIP w stopce, zanim uznasz stronę za tej firmy).
2. `python3 $HERMES_HOME/scripts/strona.py kontakt <www> --json > <projekt>/strony/<domena>.json`: e-maile (z typem
   i kontekstem, np. „Anna Nowak, dyrektor sprzedaży”), telefony, formularz, kariera, technologie, NIP, social.
   Kod 3 = strona odmówiła (ochrona, `robots.txt`): zostaje bez kontaktu, nie próbujesz innej drogi.
3. `python3 $HERMES_HOME/scripts/leady.py kontakt <projekt> <projekt>/strony/*.json`, potem `leady.py ocen` od nowa.
4. Kolejność w liście: ogólny (`biuro@`) → rolowy (`sprzedaz@`, `marketing@`) → osobowy (imię i nazwisko albo skrzynka
   darmowa: to dane osobowe). Osobę z imienia i nazwiska podajesz tylko wtedy, gdy firma pokazuje ją jako kontakt.
5. Brak e-maila → telefon albo formularz ze strony; brak wszystkiego → „brak opublikowanego kontaktu” (to też wynik).

## Zasady
- Profil na LinkedInie możesz podać jako link do strony firmy (z jej strony www), ale go nie czytasz i nie scrapujesz.
- Nic nie wysyłasz i nie wypełniasz formularzy. Wysyłka to decyzja człowieka (A2).

## Definition of Done
- [ ] każdy kontakt ma źródło (adres strony albo odpis KRS) i typ,
- [ ] zero adresów zgadniętych albo spoza strony firmy i rejestru,
- [ ] firmy bez kontaktu opisane, a nie pominięte.
