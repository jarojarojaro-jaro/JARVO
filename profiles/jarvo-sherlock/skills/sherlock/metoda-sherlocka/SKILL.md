---
name: metoda-sherlocka
description: "Śledztwo: plan, wątki, źródła pierwotne, weryfikacja."
version: 1.1.0
author: "Jarvo (metodologia inspirowana: langchain-ai/open_deep_research MIT, dzhng/deep-research MIT, STORM MIT)"
license: MIT
metadata:
  hermes:
    tags: [research, investigation, verification, citations]
    related_skills: [szybki-fakt, weryfikacja-faktow, raport-sledztwa, research-rynku, research-seo, grounded-citations, searxng-search]
  jarvo:
    agent: jarvo-sherlock
    autonomy: A1
    reviewed: "2026-09-28"
---

# Metoda Sherlocka

Domyślny workflow każdego śledztwa. Wynik: `out/RAPORT.md` + `out/zrodla.jsonl`.
Karta pyta o jeden bieżący fakt (limit, cena, data, przepis) bez porównań → `szybki-fakt`, nie ta metoda.

## Faza 0. Brief śledztwa (≤ 5 min)
Zapisz w `notes/brief.md`:
- **Pytanie główne** (jedno zdanie) i **po co** (jaka decyzja od tego zależy),
- **kryteria odpowiedzi**: co musi zawierać raport, żeby był użyteczny (z DoD karty),
- **zakres**: czas (np. „dane 2025–2026”), geografia (PL/UE/świat), język źródeł,
- **hipotezy wstępne** (2–4): co może być prawdą, co mogłoby je obalić.

Brakuje czegoś, co zmienia kierunek? `kanban_block(kind="needs_input")` z pytaniem i propozycją domyślną.

## Faza 1. Dekompozycja na wątki
Rozbij pytanie na **niezależne, niepokrywające się** wątki (szczegóły: `references/dekompozycja.md`):
- proste fakty, listy, rankingi → 1 wątek,
- porównanie A vs B vs C → 1 wątek na element,
- „jak jest naprawdę” → wątek *za*, wątek *przeciw*, wątek *źródła pierwotne/dane*.

Limit: **maks. 5 wątków**. Więcej = źle zdefiniowane pytanie.

## Faza 2. Śledztwo w wątkach
Wątki niezależne → `delegate_task(tasks=[...])`. **Każdy subagent dostaje samowystarczalną instrukcję**
(nie widzi Twojej rozmowy ani innych wątków), bez skrótów i akronimów, z:
- dokładnym pytaniem wątku, zakresem czasu i geografii,
- poleceniem użycia `web_search` (SearXNG) + `$HERMES_HOME/scripts/extract.py` do czytania stron,
- wymaganiem zwrotu w formacie „learnings” (niżej) + listy URL-i z datami,
- budżetem: proste pytanie 2–3 wyszukiwania, złożone do 6, stop po 2 wyszukiwaniach bez nowych informacji.

Format „learnings” (dla każdego źródła):
```
- twierdzenie: <zwięzłe, gęste informacyjnie; z encjami, liczbami, datami>
  źródło: <URL> | data źródła: <RRRR-MM-DD> | typ: pierwotne/wtórne | cytat: "<dosłowny fragment>"
```
Plus: `pytania_pogłębiające` (maks. 3), czyli co warto sprawdzić dalej.

Wątki zależne albo jeden prosty wątek → rób sam, tym samym formatem.

Wyszukiwanie (szczegóły: `references/wyszukiwanie.md`): zaczynaj szeroko, potem zawężaj. Używaj operatorów
(`site:`, `filetype:pdf`, `"dokładna fraza"`, zakres dat), wersji PL i EN zapytania, źródeł specjalistycznych
(`arxiv`, `youtube-content`, `reddit-reading`, rejestry z `references/zrodla-pl.md`).

## Faza 3. Pogłębienie (maks. 1–2 rundy)
Po zebraniu wyników wątków zadaj sobie pytania:
- Czy mam odpowiedź na pytanie główne? Czego brakuje?
- Które kluczowe twierdzenia mają tylko 1 źródło?
- Czy są sprzeczności do rozstrzygnięcia?
Wybierz najważniejsze `pytania_pogłębiające` i zrób **jedną** rundę uzupełnień. Nie gonisz perfekcji.

## Faza 4. Weryfikacja
Skill `weryfikacja-faktow` na **kluczowych twierdzeniach** (tych, od których zależy odpowiedź):
≥ 2 niezależne źródła, źródło pierwotne, aktualność, przeliczone liczby, sprawdzone cytaty.
Każde źródło → `python3 $HERMES_HOME/scripts/sources.py add …` (dziennik z oceną wiarygodności). Kluczowe → `--archive`.

## Faza 5. Synteza i raport
Skill `raport-sledztwa`. Zasady syntezy:
- **nie zgub źródeł**: każde twierdzenie w raporcie ma numer źródła,
- łącz powtórzenia („3 niezależne źródła podają X [2][5][7]”),
- sprzeczności osobno, z oceną, komu ufać i dlaczego,
- odpowiedź i rekomendacja na górze, szczegóły niżej.

## Faza 6. Oddanie
Samokontrola DoD → `kanban_request_review(reviewer="@@REVIEWER@@", …)` zgodnie z protokołem floty.
`metadata.artifacts`: `out/RAPORT.md`, `out/zrodla.jsonl`; `metadata.dod_check`: każdy punkt DoD z dowodem.

## Kryteria stopu
- pewna odpowiedź na pytanie główne z ≥ 2 niezależnymi źródłami dla kluczowych twierdzeń, **albo**
- dwie kolejne rundy wyszukiwań bez nowych informacji → raport z jasno opisaną luką.
