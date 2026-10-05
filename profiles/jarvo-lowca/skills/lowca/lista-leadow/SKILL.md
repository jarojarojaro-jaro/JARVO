---
name: lista-leadow
description: "Lista leadów: ranking z „dlaczego teraz”, pokrycie, raport."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [leads, report, csv, b2b, sales]
    related_skills: [kwalifikacja, kontakt-firmy, monitoring-leadow]
  jarvo:
    agent: jarvo-lowca
    autonomy: A1
    reviewed: "2026-10-05"
---

# Lista leadów

Oddanie: ranking firm, z którymi warto porozmawiać teraz, z powodem i kontaktem ze źródłem. `leady.py ocen` pisze
`leady.csv` (pełna lista) i `LEADY.md` (czołówka, pokrycie, przypomnienie o zgodach); Ty dopisujesz wnioski i kroki.

## Kroki
1. `leady.py ocen <projekt> --top 30` po kwalifikacji i kontaktach.
2. `out/leady/<projekt>/`: kopia `ICP.yaml`, `ICP.md`, `leady.csv`, `LEADY.md` (katalog projektu zostaje w
   `@@WORKSPACES_DIR@@/jarvo-lowca/leady/` dla monitoringu).
3. `out/RAPORT.md`: 3–5 zdań wniosków (skąd najlepsze leady, co odpadło i dlaczego), pokrycie, koszt przebiegu
   (zapytania, czas), blokady źródeł, propozycja: monitoring (jak często) i kolejny krok. Dane z CEIDG mają
   „stan na” dzień pobrania (`stan_na` w `sygnaly.jsonl`): podaj go; brak tokenu CEIDG to jedna linia w raporcie.
   Przy firmie jednoosobowej kontakt z rejestru to dane osoby: legalny kanał to odpowiedź na jej zapytanie, list
   albo spotkanie; e-mail i telefon dopiero po zgodzie (art. 398 PKE).
4. Kolejny krok to propozycja dla Jarva, nie akcja: szkic pierwszej wiadomości do czołówki → `jarvo-studio`
   (`copy-pl`, z „dlaczego teraz” każdej firmy); wysyłka zawsze przez człowieka.
5. Przypomnienie o zgodach i RODO jest w `LEADY.md` (dopisuje je `leady.py`); nie usuwasz go.

## Definition of Done
- [ ] `LEADY.md` z pokryciem, czołówką (ocena, dlaczego teraz, kontakt, źródło) i przypomnieniem o zgodach,
- [ ] `leady.csv` z kluczami, sygnałami z datą, źródłami i kontaktami ze źródłem (`email_zrodlo`, `telefon_zrodlo`),
- [ ] `RAPORT.md` z kosztem przebiegu, blokadami i propozycją monitoringu; nic nie zostało wysłane.
