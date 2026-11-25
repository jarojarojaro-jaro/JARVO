---
name: lista-inwestorow
description: "Fundusze VC i aniołowie pod tezę projektu, z dowodami."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fundraising, vc, angels, investors, thesis]
    related_skills: [mapa-finansowania, baza-okazji, pakiet-aplikacji]
  jarvo:
    agent: jarvo-bigshort
    autonomy: A1
    reviewed: "2026-11-25"
---

# Lista inwestorów

## Kiedy użyć
- „Do jakich funduszy iść”, „kto inwestuje w X”, przygotowanie rundy pre-seed albo seed.

## Kiedy NIE używać
- Granty, kredyty, akceleratory → `mapa-finansowania`.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| profil projektu (`projekty/<projekt>.yaml`) | tak | zbuduj jak w `mapa-finansowania` krok 1 |
| region inwestorów | nie | Polska i CEE + globalni z otwartym formularzem |

## Kroki
1. **Teza projektu jednym zdaniem** i 3–5 słów kluczowych tezy (np. „inferencja LLM lokalnie”, „agenci AI dla MŚP”).
2. **Kandydaci** z darmowych źródeł (plik `narzedzia-i-bazy.md` w wiedzy skillu `mapa-finansowania`: OpenVC, Signal,
   listy funduszy PFR i Dealroom w wersji publicznej, strony funduszy, ogłoszenia rund w portfolio).
3. **Dowód dopasowania dla każdego:** inwestycja z ostatnich 24 miesięcy w podobnej tezie (link do ogłoszenia albo
   portfolio), etap, typowy czek, czy przyjmuje zgłoszenia bez poleceń (formularz, mail, „no warm intro needed”).
   - ✅ Punkt kontrolny: fundusz bez dowodu z ostatnich 24 miesięcy nie trafia do top 10.
4. **Ranking:** dopasowanie tezy, etap i czek, droga wejścia (formularz > polecenie możliwe > tylko ciepłe intro);
   osoba kontaktowa tylko w roli publicznej (partner na stronie funduszu), bez prywatnych danych.
5. **Baza:** fundusze jako okazje typu `vc`/`aniol`/`syndykat` z `termin: rolling`, `okazje.py ocen`.

## Wyjścia
- `out/INWESTORZY.md` (top 10 z dowodami, reszta w tabeli), wpisy w bazie.

## Definition of Done
- [ ] ≥ 20 kandydatów sprawdzonych, top 10 z dowodem dopasowania i drogą wejścia,
- [ ] czek i etap z datą źródła, przy braku danych „nie podano”,
- [ ] nic nie wysłane i żaden fundusz nie dostał danych projektu.

## Typowe błędy
- Fundusz z listy „top VC” bez inwestycji w tezie → odpada albo niska ocena z powodem.
- Mail partnera z wycieków albo zgadywania adresów → zakazane; tylko kanały opublikowane przez fundusz.
