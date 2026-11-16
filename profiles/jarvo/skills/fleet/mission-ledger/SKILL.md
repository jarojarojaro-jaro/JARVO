---
name: mission-ledger
description: "Dziennik misji: MISSION.md, INDEX.md, raport końcowy."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, missions, ledger, memory]
    related_skills: [dispatch-playbook, decision-queue, intake]
  jarvo:
    agent: jarvo
    autonomy: A1
    reviewed: "2026-09-26"
---

# Dziennik misji

Dziennik to **pamięć zewnętrzna Jarva**. Tablica kanban pamięta pracę; dziennik pamięta,
*po co* ta praca jest, co postanowiliście i co obiecałeś użytkownikowi.

## Pliki
- `@@MISSIONS_DIR@@/INDEX.md`: jedna tabela wszystkich misji i zleceń (szablon: `references/INDEX.template.md`).
- `@@MISSIONS_DIR@@/<ID>/MISSION.md`: dziennik misji (szablon: `references/MISSION.template.md`).
- `@@MISSIONS_DIR@@/<ID>/<rola>/`: katalogi robocze kart (wyniki w `out/`).

ID: `M-RRMMDD-slug` (misja) albo `Z-RRMMDD-slug` (pojedyncze zlecenie). Slug: 2–4 słowa, małe litery, myślniki.

## Kiedy pisać
| Moment | Co zapisać |
|---|---|
| start misji | MISSION.md (intencja dosłownie, granice, decyzje, plan kart) + wiersz w INDEX.md (`w toku`) |
| decyzja użytkownika | wiersz w tabeli *Decyzje* (co, kto, kiedy, jego słowa w cudzysłowie) |
| zmiana zakresu | nowa decyzja + aktualizacja planu; stary plan zostaje w historii |
| karta zaakceptowana | status i link do wyniku w tabeli *Plan* |
| czeka na użytkownika | status misji `czeka na decyzję` w INDEX.md |
| zamknięcie | *Artefakty*, *Raport końcowy*, status `zakończona`, data w INDEX.md |

Zapisuj od razu, nie „na końcu tury”. Jeśli rozmowa się urwie, dziennik ma być aktualny.

**Kto zdecydował.** W kolumnie „Kto” „właściciel” tylko z jego słowami w cudzysłowie („Słowa właściciela”) i godziną
jego wiadomości; co wybrałeś sam (domyślnie, z rekomendacji, bez odpowiedzi), to „Jarvo”. To samo w raporcie, w `DLA-CLAUDE.md`
i na kartach: bez cytatu i czasu piszesz „decyzja Jarva”, nie „decyzja właściciela” (wtyczka `jarvo-zgody` odrzuca
taki zapis; 16.11 raport misji podał „decyzja właściciela z 23:15”, choć właściciel nic nie napisał).

## Odtwarzanie stanu (po restarcie, kompresji, nowej sesji)
1. Przeczytaj `INDEX.md`: misje `w toku` i `czeka na decyzję`.
2. Dla każdej: `MISSION.md` + `kanban_list` / `kanban_show` kart z planu.
3. Rozbieżności (karta zakończona, a w dzienniku „w toku”) → popraw dziennik i ewentualnie działaj (np. raport końcowy).

## Zamknięcie misji: raport końcowy

Wysyłasz **jedną** wiadomość, która stoi sama:
```
✅ <Nazwa misji>: gotowe
Co powstało:
• <artefakt 1: krótko + ścieżka/link>
• <artefakt 2>
Jakość: <co zweryfikowano, liczby: Lighthouse, liczba źródeł, wymiary, długość filmu…>
Do decyzji: <np. „publikacja postów: tak/nie?”, „wdrożenie na produkcję?”> albo „nic”
Dalej proponuję: <maks. 2 propozycje, opcjonalnie>
```
Potem: raport do MISSION.md, status w INDEX.md, trwałe wnioski o preferencjach użytkownika do pamięci.

## Anulowanie
Użytkownik odwołuje → karty w pracy (`running`): `kanban_block(task_id, reason="anulowane przez właściciela:
„<jego słowa>” (<godzina>)")`, pracownika zamknie dyspozytor; pozostałe karty: `kanban_comment` („anulowane przez
użytkownika”) + `kanban_complete` z adnotacją. Nigdy `kill` pracownika (dyspozytor uruchamia kartę od nowa); misja:
status `anulowana` + powód. Potwierdź jednym zdaniem.
