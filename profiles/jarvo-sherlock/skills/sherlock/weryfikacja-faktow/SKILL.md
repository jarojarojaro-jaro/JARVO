---
name: weryfikacja-faktow
description: "Fact-check: twierdzenie → źródła pierwotne → werdykt."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [research, fact-checking, verification, sources]
    related_skills: [metoda-sherlocka, grounded-citations, raport-sledztwa]
  jarvo:
    agent: jarvo-sherlock
    autonomy: A1
    reviewed: "2026-09-26"
---

# Weryfikacja faktów

Dla każdego **kluczowego** twierdzenia (od którego zależy odpowiedź albo decyzja użytkownika).

## Tabela twierdzeń
Prowadź `notes/twierdzenia.md`:

| # | Twierdzenie (dosłownie) | Źródła [n] | Pierwotne? | Data | Werdykt | Pewność |
|---|---|---|---|---|---|---|

Werdykty: **potwierdzone** · **częściowo** (z doprecyzowaniem) · **niepotwierdzone** (brak dowodów) ·
**fałszywe** (dowód przeciw) · **nieaktualne** (było prawdą do <data>).

## Procedura dla jednego twierdzenia
1. **Rozbij** na sprawdzalne elementy: kto, co, kiedy, ile, gdzie.
2. **Źródło pierwotne:** gdzie to pierwszy raz ogłoszono (dokument, rejestr, dane, oficjalny komunikat)?
   Czytaj oryginał (`extract.py`, PDF → `read_file` albo Docling, jeśli jest; wideo → `youtube-content`).
3. **Czytanie lateralne:** zamiast wierzyć stronie, sprawdź, co **inni** mówią o niej i o twierdzeniu.
4. **Drugie niezależne źródło:** niezależne = nie cytuje pierwszego i nie jest przedrukiem.
5. **Liczby:** przelicz (procenty, sumy, waluty, jednostki). Sprawdź, czy porównywane okresy są porównywalne.
6. **Cytaty:** znajdź dokładne brzmienie w oryginale, z kontekstem.
7. **Aktualność:** data źródła vs data zdarzenia; czy od tego czasu coś się zmieniło?
8. **Zdjęcia/dokumenty:** metadane (`exiftool`), wyszukiwanie obrazem (przeglądarka), archiwum (Wayback) dla zmian na stronach.

## Skala wiarygodności źródeł (tier)
| Tier | Źródła | Waga |
|---|---|---|
| **A** | oficjalne rejestry, akty prawne, dane statystyczne, dokumenty pierwotne firm, recenzowane badania | wysoka |
| **B** | renomowane media i media branżowe z redakcją, raporty z opisaną metodologią | średnio-wysoka |
| **C** | blogi ekspertów z nazwiskiem, fora branżowe, wywiady | niska–średnia, wymaga potwierdzenia |
| **D** | anonimowe, afiliacyjne rankingi, farmy treści, media społecznościowe bez weryfikacji | tylko jako sygnał |

Konflikt interesów (źródło zarabia na twierdzeniu) obniża tier o jeden poziom.

## Pewność
- **wysoka:** ≥ 2 niezależne źródła A/B, w tym pierwotne; brak wiarygodnych zaprzeczeń,
- **średnia:** 1 źródło A albo 2 źródła B/C; drobne rozbieżności,
- **niska:** tylko C/D, sprzeczności albo brak źródła pierwotnego.

## Sprzeczności
Nie wybieraj po cichu. Opisz: kto twierdzi co, na jakiej podstawie, komu ufasz bardziej i dlaczego.
