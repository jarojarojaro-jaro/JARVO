---
name: intake
description: "Każda nowa wiadomość: sklasyfikuj i wybierz ścieżkę."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [fleet, intake, routing]
    related_skills: [dispatch-playbook, decision-queue, mission-ledger, roster]
  tars:
    agent: tars
    autonomy: A1
    reviewed: "2026-09-26"
---

# Intake: przyjęcie zlecenia

Używaj przy **każdej** nowej wiadomości od użytkownika, zanim cokolwiek zlecisz.

## Krok 1. Sklasyfikuj

| Typ | Rozpoznanie | Ścieżka |
|---|---|---|
| **Rozmowa** | opinia, rada, szybki fakt z wiedzy, żart, plan dnia | odpowiadasz sam, bez kart |
| **Status** | „co się dzieje?”, „jak idzie X?” | czytasz `@@MISSIONS_DIR@@/INDEX.md` + `kanban_list`, raport w stylu efektów |
| **Decyzja** | odpowiedź na pytania z kolejki („1 ok, 2: B”) | skill `decision-queue` |
| **Zlecenie jednego agenta** | jedno wyraźne zadanie w zakresie jednego agenta | 1 karta (skill `dispatch-playbook`, wariant „pojedyncze”) |
| **Misja** | cel wymagający ≥2 agentów albo kilku etapów | misja + plan + karty (`mission-ledger` + `dispatch-playbook`) |
| **Zmiana w toku** | „zmień to w landingu”, „dodaj jeszcze…” | komentarz do istniejącej karty albo nowa karta w tej samej misji; nie zakładaj nowej misji |
| **Anulowanie** | „stop”, „odpuść X” | archiwizuj karty misji, oznacz misję jako anulowaną, potwierdź jednym zdaniem |

Gdy nie jesteś pewien między „zleceniem jednego agenta” a „misją”, wybierz prostsze.

## Krok 2. Sprawdź, czy odpowiedź już istnieje

Zanim zlecisz research albo pracę:
- `session_search` i pamięć: czy już o tym rozmawialiście?
- `@@MISSIONS_DIR@@/INDEX.md`: czy podobna misja jest w toku albo zakończona?
- zakończone raporty w `@@MISSIONS_DIR@@/*/` (szczególnie raporty Sherlocka).

Jeśli odpowiedź istnieje i jest świeża, zrelacjonuj ją. Ewentualnie zaproponuj aktualizację zamiast zlecać drugi raz.

## Krok 3. Dopytaj tylko, gdy musisz

Pytaj **wyłącznie**, gdy brak informacji zmieniłby to, *co* powstanie (odbiorca, marka, język, zakres,
termin, budżet, platforma). Zasady:
- jedno zbiorcze pytanie, maksymalnie 3 punkty, każdy z **rekomendowaną odpowiedzią domyślną**,
- jeśli domyślne odpowiedzi są rozsądne, powiedz „ruszam z domyślnymi, chyba że zmienisz” i **ruszaj**,
- nigdy nie pytaj o rzeczy, które agent ustali sam (np. framework strony, kolejność kroków researchu).

## Krok 4. Ustal granice

Zapisz (w misji albo w karcie):
- czego użytkownik **dosłownie** chce (cytat), czego nie ruszać, termin, budżet, poziom autonomii,
- czy wynik ma być szkicem/podglądem (A1), czy wymaga publikacji/wdrożenia (A2 → decyzja użytkownika na końcu).

## Krok 5. Potwierdź start jednym zdaniem

Przykład: „Ruszam: Sherlock bada konkurencję, potem Web buduje landing, a Studio robi grafiki. Pierwsze wyniki za około godzinę.”
Bez listy kart, bez identyfikatorów.

## Typowe błędy
- Zakładanie misji dla prostego pytania → odpowiedz sam.
- Dopytywanie o wszystko → rusz z domyślnymi i je nazwij.
- Poszerzanie zakresu („przy okazji zrobię też…”) → do sekcji *Propozycje na później*.
