---
name: szybki-fakt
description: "Jedno pytanie o bieżący fakt: jedna runda szukania, cytat."
version: 1.0.0
author: "Jarvo (na bazie oh-my-hermes web-research, MIT)"
license: MIT
metadata:
  hermes:
    tags: [research, facts, citations, lookup]
    related_skills: [metoda-sherlocka, weryfikacja-faktow, grounded-citations, searxng-search]
  tars:
    agent: tars-sherlock
    autonomy: A1
    reviewed: "2026-09-28"
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
3. **Każde zdanie odpowiedzi ma źródło** z tierem A–D (skala z `weryfikacja-faktow`) i datą publikacji.
4. **Sporne?** (źródła się różnią albo jest tylko tier C/D) → drugie niezależne źródło z innej domeny.
   Nadal sporne → piszesz „niepotwierdzone” z opisem rozbieżności, nie wybierasz po cichu.
5. **Stop na odpowiedzi.** Lista tropów rośnie zamiast maleć → to nie jest szybki fakt: `kanban_comment` z jednym
   zdaniem dlaczego i dalej `metoda-sherlocka`.
6. Czego nie znalazłeś, tego nie uzupełniasz z pamięci modelu: piszesz, czego brakuje.

## Wynik
`out/FAKT.md`:
```
Odpowiedź: <1–3 zdania>
Pewność: wysoka / średnia / niska · stan na: RRRR-MM-DD (data sprawdzenia)
Źródła:
[1] <tytuł>, <wydawca>, <data> (tier A) <URL>
Braki: <czego nie udało się potwierdzić albo „brak”>
```

## Definition of Done
- odpowiedź na dokładnie zadane pytanie, z datą „stan na”,
- każde zdanie z przypisem; pewność zgodna ze skalą z `weryfikacja-faktow`,
- sporne twierdzenie potwierdzone drugim niezależnym źródłem albo oznaczone jako niepotwierdzone.
