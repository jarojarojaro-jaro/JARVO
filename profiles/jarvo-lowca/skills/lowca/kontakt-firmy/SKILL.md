---
name: kontakt-firmy
description: "Kontakt opublikowany przez firmę: e-mail, tel., formularz."
version: 1.2.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [leads, contact, company-website, ceidg, gdpr]
    related_skills: [kwalifikacja, lista-leadow]
  jarvo:
    agent: jarvo-lowca
    autonomy: A1
    reviewed: "2026-10-05"
---

# Kontakt do firmy

Kontakt szukasz **tylko dla firm, które przeszły kwalifikację**, i bierzesz wyłącznie to, co firma sama opublikowała
(strona, stopka, zespół, kontakt) albo co jest w rejestrze (KRS: e-mail i strona, jeśli firma je podała; CEIDG: telefon,
e-mail i strona, jeśli przedsiębiorca je podał). Każdy kontakt ma adres źródła. Adresów nie zgadujesz, nie kupujesz, nie wyciągasz z serwisów za logowaniem.

## Kroki
1. Strona firmy: z sygnału (`www`), z KRS (`krs.py odpis <KRS> --json`) albo z wyszukiwarki (`"<nazwa firmy>" <miasto>`;
   sprawdź NIP w stopce, zanim uznasz stronę za tej firmy).
2. `python3 $HERMES_HOME/scripts/strona.py kontakt <www> --json > <projekt>/strony/<domena>.json`: e-maile (z typem
   i kontekstem, np. „Anna Nowak, dyrektor sprzedaży”), telefony, formularz, kariera, technologie, NIP, social.
   Skrypt czyta też dane ukryte w HTML (schema.org JSON-LD, `__NEXT_DATA__`, Nuxt, React Server Components):
   nazwa i adres firmy, telefon, e-mail i NIP, których strona nie pokazuje w tekście. Takie pole ma `skad`
   (np. `json-ld`) i adres strony, a `ukryte` mówi, który ładunek co zawierał. To nadal dane, które firma sama
   opublikowała: ten sam dokument, tylko zapis dla maszyn.
   Kod 3 = strona odmówiła (ochrona, `robots.txt`): zostaje bez kontaktu, nie próbujesz innej drogi.
3. `python3 $HERMES_HOME/scripts/leady.py kontakt <projekt> <projekt>/strony/*.json`, potem `leady.py ocen` od nowa.
   **Jednoosobowa działalność** (NIP bez KRS, np. zwycięzca przetargu): `python3 $HERMES_HOME/scripts/ceidg.py firma
   --nip <NIP> -o <projekt>/ceidg.jsonl` i `leady.py dodaj`: wpis `ceidg-firma` dokłada PKD i kontakt z CEIDG (ze
   źródłem i `stan_na`) bez podbijania oceny. Brak tokenu (kod 2): kontakt tylko ze strony, w raporcie „CEIDG bez tokenu”.
4. Kolejność w liście: ogólny (`biuro@`) → rolowy (`sprzedaz@`, `marketing@`) → osobowy (imię i nazwisko albo skrzynka
   darmowa: to dane osobowe). Osobę z imienia i nazwiska podajesz tylko wtedy, gdy firma pokazuje ją jako kontakt.
5. Brak e-maila → telefon albo formularz ze strony; brak wszystkiego → „brak opublikowanego kontaktu” (to też wynik).

## Zasady
- Profil na LinkedInie możesz podać jako link do strony firmy (z jej strony www), ale go nie czytasz i nie scrapujesz.
- Kontakt z CEIDG to dane osoby fizycznej (często prywatny telefon albo skrzynka `@gmail.com`, typ `osobowy`). E-mail
  i telefon z rejestru to nie zgoda: informacja handlowa tymi kanałami wymaga wcześniejszej zgody odbiorcy (art. 398 PKE).
  Adres do e-Doręczeń służy korespondencji urzędowej, nie bierzesz go. Imienia i nazwiska właściciela nie podajesz osobno.
- Nic nie wysyłasz i nie wypełniasz formularzy. Wysyłka to decyzja człowieka (A2).

## Definition of Done
- [ ] każdy kontakt ma źródło (adres strony albo odpis KRS) i typ,
- [ ] zero adresów zgadniętych albo spoza strony firmy i rejestru (KRS, CEIDG),
- [ ] firmy bez kontaktu opisane, a nie pominięte.
