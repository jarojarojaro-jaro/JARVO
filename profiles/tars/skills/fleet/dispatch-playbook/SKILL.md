---
name: dispatch-playbook
description: "Rozdawanie pracy: karty z kontraktem, zależności, misje."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [fleet, kanban, dispatch, orchestration]
    requires_toolsets: [kanban]
    related_skills: [intake, mission-ledger, roster]
  tars:
    agent: tars
    autonomy: A1
    reviewed: 2026-09-26
---

# Dispatch: jak rozdać pracę

Używaj, gdy intake zdecydował: **zlecenie jednego agenta** albo **misja**.

## Zasady nadrzędne
1. **Najwęższy agent, który w pełni pokrywa zadanie** (skill `roster`). Nikt nie pasuje →
   `tars-reka` z adnotacją „poza snajperami” albo zapytaj użytkownika, czy stworzyć specjalizację.
2. **Decyzje przekrojowe przed rozdaniem.** Jeśli dwie karty musiałyby wybrać to samo (nazwa, paleta,
   język, format pliku, struktura URL), decydujesz raz i wpisujesz to do **obu** kart.
   Agenci nie widzą kart rodzeństwa.
3. **Każda karta jest samowystarczalna.** Wykonawca nie zna Twojej rozmowy z użytkownikiem.
4. **Równolegle, gdy się da; sekwencyjnie, gdy musi.** Zależność (`parents`) tylko wtedy, gdy karta
   naprawdę potrzebuje wyniku rodzica.

## Kontrakt karty (treść `body`)

Szablon: `references/card-template.md`. Minimum:
```
CEL: <co ma powstać, 1–2 zdania>
KONTEKST: <dla kogo, po co, decyzje już podjęte, marka, ton, ograniczenia>
WEJŚCIA: <pliki/URL; brand kit: @@KNOWLEDGE_DIR@@/brands/<marka>/; wyniki rodziców: ich katalogi out/>
DoD:
- <mierzalny warunek 1>
- <mierzalny warunek 2>
WYJŚCIA: <pliki w out/ (nazwy, formaty)>
GRANICE: autonomia A1 (bez publikacji/wdrożeń); budżet <czas>; nie ruszać <…>
```

## Wywołanie `kanban_create`

```
kanban_create(
  title="[<MISJA>] <krótko, co powstaje>",
  assignee="<agent z rosteru>",
  body="<kontrakt>",
  parents=[<id kart, których wynik jest potrzebny>],
  skills=[<skille z rosteru, które chcesz wymusić>],
  workspace_kind="dir",
  workspace_path="@@MISSIONS_DIR@@/<MISJA>/<rola>",
  idempotency_key="<MISJA>-<rola>",
  max_runtime_seconds=<np. 5400>,
)
```
- `<MISJA>` = ID misji (`M-RRMMDD-slug`) albo `Z-RRMMDD-slug` dla pojedynczego zlecenia.
- `<rola>` = krótki slug zadania, np. `research`, `landing`, `grafiki`, `zlozenie`.
- Katalog workspace musi istnieć: utwórz go przez narzędzie plików (np. zapisując `README.md` z celem karty).
- `goal_mode=True` tylko dla kart otwartych („iteruj, aż…”). Wtedy DoD musi być bardzo konkretne.

## Wzorce misji (szczegóły: `references/patterns.md`)

| Wzorzec | Karty |
|---|---|
| **Research → decyzja** | sherlock (raport) → TARS relacjonuje, pyta o decyzję |
| **Landing produktu** | sherlock (rynek + słowa kluczowe) → web (landing) ∥ studio (grafiki + posty) → reka (złożenie pakietu) |
| **Audyt + naprawa strony** | web (audyt) → [decyzja użytkownika, co naprawiać] → web (poprawki) |
| **Kampania** | sherlock (grupa docelowa, konkurencja) → studio (pakiet kampanii) → reka (złożenie + kalendarz) |
| **Nowa marka / brand kit** | web (brand z URL) → studio (weryfikacja tonu i wizualiów) |

**Karta „złożenie”** (dla misji z ≥2 agentami): `assignee="tars-reka"`, `parents` = wszystkie karty merytoryczne,
cel: jeden pakiet w `@@MISSIONS_DIR@@/<MISJA>/zlozenie/out/` (INDEX.md z opisem i ścieżkami, bez przerabiania treści).

## Po utworzeniu kart
1. Zapisz plan w `MISSION.md` (tabela kart: id, agent, zależy od, status) i dopisz misję do `INDEX.md` (skill `mission-ledger`).
2. Odpowiedz użytkownikowi jednym zdaniem: kto co robi, kiedy wynik.

## Zdarzenia z tablicy (budzą Cię automatycznie)

| Zdarzenie | Twoja reakcja |
|---|---|
| `review_requested` | nic: recenzję robi tor review. Odpowiedź: `[SILENT]` |
| `completed` karty pośredniej | zaktualizuj tabelę w MISSION.md. Odpowiedź: `[SILENT]` |
| `completed` ostatniej karty misji (zwykle „złożenie”) | zamknij misję i wyślij raport końcowy (`mission-ledger`) |
| `blocked` z `needs_input` | dodaj do kolejki decyzji i wyślij zbiorcze pytanie (`decision-queue`) |
| `blocked` z `capability` | przenieś: `kanban_create` dla właściwego agenta (ta sama treść + uwaga wykonawcy), potem `kanban_comment` na starej karcie („przeniesione do <nowa>”) i `kanban_complete(task_id=<stara>, summary="Przeniesione do <nowa>: <powód>")`. Nikt nie pasuje → zapytaj użytkownika |
| `gave_up`, `crashed`, `timed_out` | przeczytaj `kanban_show`: przejściowe → `kanban_unblock`; powtarzalne → eskalacja z dowodem |
| `block_loop_detected` (triage) | nie odblokowuj w ciemno: ustal przyczynę; jeśli potrzebny człowiek → decyzja |

Nie relacjonuj każdego zdarzenia. Mów tylko wtedy, gdy to zmienia coś dla użytkownika.

## Typowe błędy
- Karta bez DoD → recenzja nie ma wobec czego oceniać. Zawsze mierzalne DoD.
- Dwie równoległe karty wymyślające tę samą rzecz → zdecyduj wcześniej.
- Karta dla nieistniejącego agenta → dispatcher jej nie wykona. Tylko nazwy z rosteru.
- `scratch` workspace dla wyników misji → pliki znikną po akceptacji. Używaj `dir` w katalogu misji.
