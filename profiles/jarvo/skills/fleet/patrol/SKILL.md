---
name: patrol
description: "Patrol floty: reaguj na anomalie tablicy i misji."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, supervision, heartbeat, cron]
    requires_toolsets: [kanban]
    related_skills: [decision-queue, mission-ledger, dispatch-playbook]
  jarvo:
    agent: jarvo
    autonomy: A1
    reviewed: "2026-11-19"
---

# Patrol floty

Rutyna cron co 30 minut. Skrypt `scripts/patrol.py` sprawdza tablicę **bez modelu**. Budzi Cię
tylko wtedy, gdy są nowe sygnały; ich lista jest w kontekście tej tury (sekcja z wyjściem skryptu).

## Co robisz z każdym sygnałem

| Sygnał | Działanie |
|---|---|
| `blocked` z `needs_input` | dołącz do kolejki decyzji (`decision-queue`). Wiadomość do użytkownika tylko, jeśli to nowa decyzja |
| `blocked` z `capability` | przenieś do właściwego agenta (`dispatch-playbook` → zdarzenia) |
| `blocked` bez rodzaju / `transient` | `kanban_show`: przejściowe (limit API, timeout) → `kanban_unblock`; inaczej → decyzja albo przeniesienie |
| `triage` | ustal przyczynę z historii karty. Popraw kontrakt (komentarz z doprecyzowaniem) i `kanban_unblock`, albo eskaluj |
| `ready_stale` | kilka kart naraz = dispatcher/gateway nie działa → **pilny komunikat** do użytkownika („flota stoi, sprawdź serwer”) |
| `review_stale` | recenzja nie ruszyła: `kanban_show`; jeśli sędzia padł, `kanban_comment` + informacja w raporcie; przy powtórce eskalacja |
| `running_long` | `kanban_show`: widać heartbeaty → zostaw; cisza → komentarz z pytaniem o status; przy powtórce eskalacja |
| `check_loop` | karta pracuje >5 min, a trzy kolejne notatki postępu mówią o tym samym niepowodzeniu kontroli: **od razu** `kanban_block` (rodzaj `needs_input`), bez czekania na właściciela i bez ponawiania. Powód = dowód z sygnału: nazwa kontroli, trzy godziny notatek, ostatni błąd. Potem jedna wiadomość do właściciela, czego potrzeba |
| `mission_ready` | zamknij misję i wyślij raport końcowy (`mission-ledger`) |
| `mission_inconsistent` | popraw INDEX.md / MISSION.md |
| `diagnostic` | zastosuj się do komunikatu Hermesa; jeśli to problem infrastruktury, powiedz użytkownikowi, co sprawdzić |
| `patrol_error` | patrol nie mógł odczytać tablicy: jedna krótka wiadomość do użytkownika z błędem |

Próg `check_loop` to „trzy rundy i stop” z kontraktu karty (`dispatch-playbook`, linia `STOP`); źródło: zespół
Claude Code o weryfikacji („if a check is still failing after three rounds, Claude stops and brings in a human”).

## Wynik tury
- Jeśli nic nie wymaga uwagi użytkownika (wszystko naprawiłeś sam), odpowiedz dokładnie `[SILENT]`.
- Jeśli wymaga: **jedna** wiadomość w stylu efektów (co się stało, co zrobiłeś, czego potrzebujesz).
- Nie opisuj mechaniki patrolu.

Patrol nie zastępuje reakcji na zdarzenia. Łapie to, co umknęło: restart, zgubione powiadomienie, utknięty proces.
