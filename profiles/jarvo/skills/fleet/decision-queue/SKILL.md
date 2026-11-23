---
name: decision-queue
description: "Decyzje dla użytkownika: zbierz, zapytaj zbiorczo, wdroż."
version: 1.5.0
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
    reviewed: "2026-11-14"
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
- pytasz tylko o sprawę, która nas dotyczy: zanim ją wpiszesz, sprawdzasz w konfigu, kodzie albo skarbcu, że tego używamy, bo wniosek z raportu agenta to nie dowód,
- każda pozycja ma **rekomendację** i uzasadnienie w 1 zdaniu,
- nieodwracalne rzeczy (A2) **nigdy** nie przechodzą domyślnie; czekają na wyraźne „tak”,
- pozycja A2 niesie **odcisk wersji** z prośby wykonawcy (`odcisk.py`, 12 znaków): zgoda dotyczy dokładnie tych plików.
  Wykonawca nie podał odcisku → dopytaj go (komentarz w karcie), zanim zapytasz człowieka,
- maksymalnie 5 pozycji naraz; resztę zostaw na następną wiadomość albo poranny brief,
- prosty polski (skill `prosty-polski`): pytanie i uzasadnienie po jednym krótkim zdaniu, ryzyko A2 jako „⛔ OSTRZEŻENIE”.

## Wdrożenie odpowiedzi
Odpowiedź na brief („1 ok, 2 nie” po porannym briefie albo „B-2026-11-12/3 ok” po czasie): numer briefu bierzesz
z jego nagłówka w historii rozmowy albo z cytatu, a pozycje z `@@KNOWLEDGE_DIR@@/briefy/<numer>.md`.
Dla każdej odpowiedzi:
1. `kanban_comment(task_id, "Decyzja właściciela (<data> <godzina>): „<jego słowa z wiadomości>”")`; przy A2 z odciskiem:
   „… tak, wersja <odcisk>”,
2. `kanban_unblock(task_id)` (karta wraca do wykonawcy z komentarzem w kontekście),
3. wpis w MISSION.md (tabela *Decyzje*, z jego słowami w kolumnie „Słowa właściciela”), status misji z powrotem na `w toku`,
4. dla A2: zlecenie wykonania akcji (np. karta „wdrożenie” dla `jarvo-web` z wyraźnym „właściciel zatwierdził
   (<data> <godzina>): „<jego słowa>”, wersja <odcisk>”). Wykonawca sprawdza odcisk przed akcją; niezgodny = pliki
   zmieniły się po zgodzie = nowe pytanie,
5. **brief w skarbcu:** odpowiedź właściciela kod wpisuje do tabeli briefu sam (dopisek w turze mówi, co zapisał), a Ty
   wpisujesz `@@PY@@ "$HERMES_HOME/scripts/briefy.py" zrobione B-…/n "co zrobione"` i, dla wiersza, którego kod nie przypisał, `… odpowiedz B-…/n "jego słowa"`.
6. **trwałe ustalenie** (cena, zasada, kierunek, „nie robimy X”): jeden szkic `wiedza_zapisz(typ="decyzja", …,
   zrodlo="brief B-…/n, odpowiedź właściciela RRRR-MM-DD")`; korekta faktu o właścicielu albo jego pracy: `wiedza_orzeczenie`.
   Jednorazowe „ok, rób” bez ustalenia na przyszłość: bez szkicu (zapis jest w tabeli briefu).
Pozycja „🛠” (pomysł z kopalni): „ok” → budowa według skilla `kopalnia-pomyslow` (sekcja „Po ok”), „nie” → tylko wiersz
w tabeli briefu (kopalnia nie wraca z odrzuconym pomysłem).
Niejasna odpowiedź → dopytaj tylko o niejasną pozycję. Resztę wdroż od razu.

**Decyzja właściciela = jego słowa.** „Decyzja właściciela”, „właściciel zdecydował / zgodził się / zatwierdził” albo
„właściciel” w kolumnie „Kto” piszesz tylko z jego słowami w cudzysłowie i godziną jego wiadomości (karta, komentarz,
powód blokady, MISSION.md, DLA-CLAUDE.md, raport). Wybrałeś sam (rekomendacja bez odpowiedzi, domyślna, „ruszam”)?
To `decyzja Jarva: …`, a gdy potrzebne jest jego „tak”, pytasz. Wtyczka `jarvo-zgody` odrzuca przypisanie bez cytatu
i czasu. 16.11: „Decyzja Jarva: zaznaczyć NDA” w komentarzu, a 27 min później w raporcie „decyzja właściciela
z 23:15”, choć właściciel nic wtedy nie napisał.

Odpowiedzi przychodzą też z **Jarvo HQ** (panel „Decyzje” w dashboardzie) jako wiadomość w formacie
`Decyzja do karty <task_id> („<tytuł>”, <agent>): <treść>`. Traktuj ją tak samo jak odpowiedź na liście:
wykonaj kroki 1–4 dla wskazanej karty i potwierdź jednym zdaniem, co odblokowałeś.

## Przypomnienia
Nieodpowiedziane decyzje wracają w porannym briefie (`daily-brief`). Po 3 dniach bez odpowiedzi
zapytaj, czy misja jest nadal aktualna.
