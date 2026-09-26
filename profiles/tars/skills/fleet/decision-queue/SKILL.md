---
name: decision-queue
description: "Decyzje dla użytkownika: zbierz, zapytaj zbiorczo, wdroż."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [fleet, decisions, escalation, human-in-the-loop]
    requires_toolsets: [kanban]
    related_skills: [mission-ledger, intake]
  tars:
    agent: tars
    autonomy: A1
    reviewed: 2026-09-26
---

# Kolejka decyzji

Decyzja to **karta zablokowana** (`blocked`, powód `needs_input` albo eskalacja recenzenta)
albo **pozycja A2** (publikacja, wdrożenie, wydatek). Decyzje nie żyją w samej rozmowie,
więc nie giną.

## Zbieranie
Źródła decyzji:
1. `kanban_list(status="blocked")`, a dla każdej karty `kanban_show` (powód blokady, pytanie wykonawcy),
2. akcje A2 czekające na zgodę (raporty końcowe misji: sekcja *Do decyzji*),
3. eskalacje sędziego (3 odrzucenia tej samej karty).

## Pytanie (jedna wiadomość)
```
Potrzebuję <N> decyzji:
1. <Misja>: <pytanie konkretne>? Rekomenduję <X>, bo <1 zdanie>.
2. <Misja>: <pytanie>? Opcje: A) … B) … Rekomenduję B.
Odpowiedz np. „1 ok, 2 A”. Bez odpowiedzi do <jutra 10:00> ruszam z rekomendacjami tylko tam, gdzie to odwracalne.
```
Zasady:
- każda pozycja ma **rekomendację** i uzasadnienie w 1 zdaniu,
- nieodwracalne rzeczy (A2) **nigdy** nie przechodzą domyślnie; czekają na wyraźne „tak”,
- maksymalnie 5 pozycji naraz; resztę zostaw na następną wiadomość albo poranny brief.

## Wdrożenie odpowiedzi
Dla każdej odpowiedzi:
1. `kanban_comment(task_id, "Decyzja użytkownika (<data>): <treść>")`,
2. `kanban_unblock(task_id)` (karta wraca do wykonawcy z komentarzem w kontekście),
3. wpis w MISSION.md (tabela *Decyzje*), status misji z powrotem na `w toku`,
4. dla A2: zlecenie wykonania akcji (np. karta „wdrożenie” dla `tars-web` z wyraźnym „użytkownik zatwierdził <data>”).

Niejasna odpowiedź → dopytaj tylko o niejasną pozycję. Resztę wdroż od razu.

## Przypomnienia
Nieodpowiedziane decyzje wracają w porannym briefie (`daily-brief`). Po 3 dniach bez odpowiedzi
zapytaj, czy misja jest nadal aktualna.
