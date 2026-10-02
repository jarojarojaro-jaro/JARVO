---
name: decision-queue
description: "Decyzje dla użytkownika: zbierz, zapytaj zbiorczo, wdroż."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, decisions, escalation, human-in-the-loop]
    requires_toolsets: [kanban]
    related_skills: [mission-ledger, intake]
  jarvo:
    agent: jarvo
    autonomy: A1
    reviewed: "2026-10-02"
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
3. <Misja>: publikacja 5 postów na IG i LinkedIn (wersja <odcisk>)? Rekomenduję tak, bo <1 zdanie>.
Odpowiedz np. „1 ok, 2 A”. Bez odpowiedzi do <jutra 10:00> ruszam z rekomendacjami tylko tam, gdzie to odwracalne.
```
Zasady:
- każda pozycja ma **rekomendację** i uzasadnienie w 1 zdaniu,
- nieodwracalne rzeczy (A2) **nigdy** nie przechodzą domyślnie; czekają na wyraźne „tak”,
- pozycja A2 niesie **odcisk wersji** z prośby wykonawcy (`odcisk.py`, 12 znaków): zgoda dotyczy dokładnie tych plików.
  Wykonawca nie podał odcisku → dopytaj go (komentarz w karcie), zanim zapytasz człowieka,
- maksymalnie 5 pozycji naraz; resztę zostaw na następną wiadomość albo poranny brief,
- prosty polski (skill `prosty-polski`): pytanie i uzasadnienie po jednym krótkim zdaniu, ryzyko A2 jako „⛔ OSTRZEŻENIE”.

## Wdrożenie odpowiedzi
Dla każdej odpowiedzi:
1. `kanban_comment(task_id, "Decyzja użytkownika (<data>): <treść>")`; przy A2 z odciskiem: „… tak, wersja <odcisk>”,
2. `kanban_unblock(task_id)` (karta wraca do wykonawcy z komentarzem w kontekście),
3. wpis w MISSION.md (tabela *Decyzje*), status misji z powrotem na `w toku`,
4. dla A2: zlecenie wykonania akcji (np. karta „wdrożenie” dla `jarvo-web` z wyraźnym „użytkownik zatwierdził <data>,
   wersja <odcisk>”). Wykonawca sprawdza odcisk przed akcją; niezgodny = pliki zmieniły się po zgodzie = nowe pytanie.

Niejasna odpowiedź → dopytaj tylko o niejasną pozycję. Resztę wdroż od razu.

Odpowiedzi przychodzą też z **Jarvo HQ** (panel „Decyzje” w dashboardzie) jako wiadomość w formacie
`Decyzja do karty <task_id> („<tytuł>”, <agent>): <treść>`. Traktuj ją tak samo jak odpowiedź na liście:
wykonaj kroki 1–4 dla wskazanej karty i potwierdź jednym zdaniem, co odblokowałeś.

## Przypomnienia
Nieodpowiedziane decyzje wracają w porannym briefie (`daily-brief`). Po 3 dniach bez odpowiedzi
zapytaj, czy misja jest nadal aktualna.
