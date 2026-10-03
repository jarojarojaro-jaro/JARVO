---
name: szybki-fakt
description: "Jedno pytanie o bieżący fakt: jedna runda szukania, cytat."
version: 1.1.0
author: "Jarvo (na bazie oh-my-hermes web-research, MIT)"
license: MIT
metadata:
  hermes:
    tags: [research, facts, citations, lookup]
    related_skills: [metoda-sherlocka, weryfikacja-faktow, cytowania, searxng-search]
  jarvo:
    agent: jarvo-sherlock
    autonomy: A1
    reviewed: "2026-10-03"
---

# Szybki fakt

Karta pyta o **jeden bieżący fakt** (limit, cena, data, stawka, wersja, przepis, godziny otwarcia) i nie potrzebuje
porównań ani raportu. Odpowiedź z cytatem w jednej rundzie wyszukiwania, bez pełnej metody śledztwa.

## Kiedy NIE
- pytanie „jak jest naprawdę”, porównanie kilku rzeczy, rynek, konkurencja → `metoda-sherlocka`,
- kilka twierdzeń do sprawdzenia → `weryfikacja-faktow`.

## Kroki
1. **Zakres przed szukaniem** (jedna linia w `notes/brief.md`): dokładne pytanie, okno aktualności („stan na
   2026”), jurysdykcja albo wersja („Polska”, „Astro 5”).
2. **Jedna runda:** 1–3 zapytania, najpierw źródło pierwotne (ustawa, rejestr, dokumentacja, strona producenta).
   Strony czytasz przez `extract.py <url> --tier … --type …`: rejestruje źródło i podaje jego numer `[n]`.
3. **Każde zdanie odpowiedzi ma numer źródła** z rejestru, z tierem A–D (skala z `weryfikacja-faktow`) i datą
   publikacji. Kluczowe zdanie dostaje cytat-dowód: `sources.py quote <n> --text "…"` (skill `cytowania`).
4. **Sporne?** (źródła się różnią albo jest tylko tier C/D) → drugie niezależne źródło z innej domeny.
   Nadal sporne → piszesz „niepotwierdzone” z opisem rozbieżności, nie wybierasz po cichu.
5. **Stop na odpowiedzi.** Lista tropów rośnie zamiast maleć → to nie jest szybki fakt: `kanban_comment` z jednym
   zdaniem dlaczego i dalej `metoda-sherlocka`.
6. Czego nie znalazłeś, tego nie uzupełniasz z pamięci modelu: piszesz, czego brakuje.

## Wynik
`out/FAKT.md`:
```
Odpowiedź: <1–3 zdania, każde z numerem [n] z rejestru>
Pewność: wysoka / średnia / niska · stan na: RRRR-MM-DD (data sprawdzenia)
Braki: <czego nie udało się potwierdzić albo „brak”>

## Źródła
<blok z `sources.py render --replace-in out/FAKT.md --styl dowody`>
```
Przed oddaniem `sources.py verify out/FAKT.md --dowody` kończy się „cytowania OK”.

## Definition of Done
- odpowiedź na dokładnie zadane pytanie, z datą „stan na”,
- każde zdanie z przypisem z rejestru; pewność zgodna ze skalą z `weryfikacja-faktow`,
- `sources.py verify out/FAKT.md --dowody` bez błędów,
- sporne twierdzenie potwierdzone drugim niezależnym źródłem albo oznaczone jako niepotwierdzone.
