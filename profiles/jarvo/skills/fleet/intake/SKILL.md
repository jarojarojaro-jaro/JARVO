---
name: intake
description: "Każda nowa wiadomość: sklasyfikuj i wybierz ścieżkę."
version: 1.2.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, intake, routing]
    related_skills: [wywiad, dispatch-playbook, decision-queue, mission-ledger, roster]
  jarvo:
    agent: jarvo
    autonomy: A1
    reviewed: "2026-11-05"
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
„Wytłumacz mi to filmem” to zlecenie jednego agenta: wzorzec „Wyjaśnij mi filmem” w `dispatch-playbook`.
„Pokaż to na schemacie” to rozmowa: rysujesz sam narzędziem `schemat` (skill `schemat`), bez kart.

## Krok 2. Sprawdź, czy odpowiedź już istnieje

Zanim zlecisz research albo pracę:
- `session_search` i pamięć: czy już o tym rozmawialiście?
- `@@MISSIONS_DIR@@/INDEX.md`: czy podobna misja jest w toku albo zakończona?
- zakończone raporty w `@@MISSIONS_DIR@@/*/` (szczególnie raporty Sherlocka).

Relacjonujesz istniejący wynik tylko wtedy, gdy **sędzia go zaakceptował** (`kanban_show`: `review_outcome:
approved`, zamknął recenzent, nie wykonawca) i jest świeży: konkurencja, ceny, leady i audyt strony do 7 dni, reszta
do 30. Wynik bez akceptacji sędziego albo starszy to tylko wejście dla nowej karty (WEJŚCIA), nie odpowiedź dla
właściciela. Gdy relacjonujesz, podaj datę wyniku jednym zdaniem.

## Krok 3. Dopytaj tylko, gdy musisz

**Bramka wywiadu.** Skill `wywiad` (pytania po kolei, najwyżej 6) uruchamiasz tylko, gdy **wszystko** jest prawdą:
- typ to **Misja** (≥ 2 agentów albo kilka etapów),
- co najmniej **dwie** z trzech rzeczy są nieznane i nie da się ich rozsądnie przyjąć: *efekt* (co ma powstać),
  *granice* (czego nie robimy, marka, termin, budżet), *po czym poznamy, że gotowe*,
- zgadnięcie zmieniłoby, którzy agenci pracują albo co powstaje (a nie tylko szczegół wykonania),
- użytkownik nie napisał „rób”, „bez pytań”, „sam zdecyduj”.

| Wiadomość | Ścieżka |
|---|---|
| „Zrób landing dla Ziarno z brand kitem, otwarcie 19.10” | bez pytań, start |
| „Przygotuj kampanię na Black Friday dla Nova” | najwyżej jedno zbiorcze pytanie z domyślnymi (niżej) |
| „Zrób mi marketing”, „rozkręć mi sprzedaż”, „wymyśl strategię dla nowego biznesu” | `wywiad` |

W pozostałych przypadkach obowiązują zasady poniżej.

Pytaj **wyłącznie**, gdy brak informacji zmieniłby to, *co* powstanie (odbiorca, marka, język, zakres,
termin, budżet, platforma). Zasady:
- jedno zbiorcze pytanie, maksymalnie 3 punkty, każdy z **rekomendowaną odpowiedzią domyślną**,
- jeśli domyślne odpowiedzi są rozsądne, powiedz „ruszam z domyślnymi, chyba że zmienisz” i **ruszaj**,
- nigdy nie pytaj o rzeczy, które agent ustali sam (np. framework strony, kolejność kroków researchu).

**„Działaj” albo „zrób jak uważasz”, a faktów brakuje** (np. nie wiesz, czym zajmuje się firma, dla której ma powstać
strona). Wynik ma się nadawać do pokazania, nie być szkieletem:
- najpierw szukasz faktów sam: `USER.md`, skarbiec, strona i konta firmy, wcześniejsze rozmowy i misje;
- brakuje faktu, bez którego wynik nie ma sensu (branża, nazwa) → **jedno** pytanie z gotową odpowiedzią domyślną
  („Czym się zajmuje i jak się nazywa? Jeśli nie odpiszesz, zrobię przykładową wersję dla salonu kosmetycznego.”);
- właściciel nie chce pytań → zlecasz **pełną wersję z wiarygodną treścią przykładową** (realistyczne nazwy, oferta,
  ceny), oznaczoną raz w raporcie jako przykład do podmiany. **Nigdy** nie zamawiasz szkieletu z treścią zastępczą
  („[TU WPISZ…]”): strażnik i sędzia go odrzucą, a właściciel dostałby pustą stronę;
- „nie wymyślaj” dotyczy faktów podawanych jako prawdziwe (dane kontaktowe, opinie, nagrody, liczby); treść
  przykładowa jawnie oznaczona jako przykład to nie kłamstwo.

**Kontynuacja po rozmowie z agentem:** gdy właściciel pisał wcześniej wprost do agenta (`@web` itp.), a teraz do
Ciebie („działaj”), w KONTEKŚCIE karty przepisujesz pytania agenta i to, co właściciel już odpowiedział. Nowa karta
nie może zaczynać od zera.

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
- Zamówienie szkieletu z „[TU WPISZ…]”, bo brakuje faktów → pełna wersja z treścią przykładową albo jedno pytanie.
