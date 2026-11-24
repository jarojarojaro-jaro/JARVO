---
name: dispatch-playbook
description: "Rozdawanie pracy: karty z kontraktem, zależności, misje."
version: 1.9.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, kanban, dispatch, orchestration]
    requires_toolsets: [kanban]
    related_skills: [intake, mission-ledger, roster]
  jarvo:
    agent: jarvo
    autonomy: A1
    reviewed: "2026-11-24"
---

# Dispatch: jak rozdać pracę

Używaj, gdy intake zdecydował: **zlecenie jednego agenta** albo **misja**.

## Zasady nadrzędne
1. **Najwęższy agent, który w pełni pokrywa zadanie** (skill `roster`). Nikt nie pasuje → robisz sam (dokumenty,
   konwersje i prototypy: skille `dokumenty`, `szybki-prototyp`) albo pytasz użytkownika, czy stworzyć specjalizację.
   Praca ogólna do zrobienia naraz (przesiew listy, wiele stron, zbieranie danych) idzie do Twoich podagentów
   `delegate_task` (do 3 naraz, każdy z pełnym opisem i częścią listy), nigdy na karty specjalistów spoza ich dziedziny.
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
KONTEKST: <najwyżej 5 punktów: dla kogo i po co, decyzje już podjęte, ograniczenia, czego NIE robić, znane braki
          wykonawcy (1–3 z `liczby.py --json` → `braki[<agent>]`)>
WEJŚCIA: <pliki/URL; brand kit: @@KNOWLEDGE_DIR@@/brands/<marka>/; wyniki rodziców: ścieżka do ich out/, nie treść;
         zdjęcia i pliki od użytkownika: pełne ścieżki @@INBOX_DIR@@/… (z linii 📎 w rozmowie)>
DoD:
- <mierzalny warunek 1>
- <mierzalny warunek 2>
WYJŚCIA: <pliki w out/ (nazwy, formaty)>
GRANICE: autonomia A1 (bez publikacji/wdrożeń); budżet <czas>; nie ruszać <…>
STOP: KONTROLA <nazwa>: NIE — <błąd> w notatce postępu; ta sama kontrola 3× z rzędu → kanban_block z dowodem, bez 4. próby
ZGODA WŁAŚCICIELA: <konto|platnosc|wysylka|publikacja|usuniecie_konta|wszystko> — „<cytat polecenia>” (<RRRR-MM-DD>)
```
Karta to kontrakt, nie streszczenie rozmowy: historia rozmowy i warianty, które rozważałeś, idą do `MISSION.md`
(wykonawca czyta kartę w każdej turze, więc każde zbędne zdanie płaci wielokrotnie; próba M-261116-koszt-kontekstu-kart,
paper „Agency”: czytanie kontekstu do 73% kosztu). Znane braki wykonawcy wpisujesz, żeby nie powtórzył ich w rundzie 1
(2/11 kart za 1. razem w tygodniu do 16.11); bierzesz je z `@@PY@@ "$HERMES_HOME/scripts/liczby.py" --json` (klucz `braki`).
Linia `ZGODA WŁAŚCICIELA`, gdy właściciel kazał założyć konto (`konto`), zapłacić, wysłać, opublikować albo usunąć
konto: cytujesz jego słowa. Czyta ją kod (Komputer Jarva, bramka telefonu), nie model; bez niej taki klik na karcie
oddajesz właścicielowi (`oddaj-ekran`). W Komputerze logowanie i rejestracja przechodzą i bez niej, na telefonie zgoda na regulamin
potrzebuje `konto`.
Linia `STOP` to próg „trzy rundy i stop” (zespół Claude Code o weryfikacji: kontrola, która po trzech rundach dalej
nie przechodzi, zatrzymuje pracę i woła człowieka; 16.11 karta t_87d11e3a klikała Cloudflare 26 min). Wykonawca każdą
nieudaną kontrolę zapisuje notatką postępu (`kanban_heartbeat`, note) w formacie `KONTROLA <nazwa>: NIE — <błąd>`.
Gdy ta sama kontrola nie przejdzie w trzech kolejnych notatkach, nie ponawia jej, tylko `kanban_block` z dowodem:
nazwa kontroli, trzy godziny notatek, ostatni komunikat błędu. Patrol czyta te notatki i zrobi to samo, gdy wykonawca nie zdąży.

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
- `goal_mode=True` tylko dla kart otwartych („iteruj, aż…”). Wtedy DoD musi być bardzo konkretne i w GRANICE nazwać,
  czego nie wolno ruszyć, żeby je zaliczyć (testy, progi, skrypty kontroli): pętla „aż przejdzie” kusi osłabieniem kontroli.

## Wzorce misji (szczegóły: `references/patterns.md`)

| Wzorzec | Karty |
|---|---|
| **Research → decyzja** | sherlock (`szybki-research`: 10–15 min, raport na jedną stronę, DoD 2–4 punkty, bez tabel „wszystkiego” i CSV; `metoda-sherlocka` tylko, gdy właściciel zamówił pełny albo głęboki research) → Jarvo relacjonuje, pyta o decyzję |
| **Landing produktu** | sherlock (rynek + słowa kluczowe) → web (landing) ∥ studio (grafiki + posty) ∥ wideo (film, opcjonalnie) → jarvo (złożenie) |
| **Audyt + naprawa strony** | web (audyt) → [decyzja użytkownika, co naprawiać] → web (poprawki) |
| **Kampania** | sherlock (grupa docelowa, konkurencja) → studio (pakiet + brief wideo) → wideo (filmy) → jarvo (złożenie + kalendarz) |
| **Film** | [sherlock (fakty), gdy film podaje liczby] → wideo (film, warianty, montaż, klipy) |
| **Wyjaśnij mi filmem** | [sherlock (fakty), gdy tematu nie ma w skarbcu ani w misjach] → wideo (explainer dla Ciebie, 60–90 s, bez publikacji) |
| **Nowa marka / brand kit** | web (brand z URL) → studio (weryfikacja tonu i wizualiów) |
| **Leady** | lowca (ICP → sygnały → ranking z kontaktem) → [decyzja użytkownika, do kogo] → studio (szkic wiadomości, opcjonalnie) |
| **Aplikacja mobilna** | mobile (natywna czy PWA, koszty) → [decyzja użytkownika] → web (strona, PWA) albo mobile (Wallet, aplikacja) |
| **Audyt mobilny** | mobile (audyt: sklepy, linki, PWA, opinie) → [decyzja użytkownika] → web ∥ studio (poprawki) |
| **Zadanie na ekranie** | [droga bez ekranu: `web_extract`, sherlock albo web] → robisz sam (`praca-na-ekranie`); dłużej niż kilka minut → karta dla siebie (`assignee="jarvo"`, jedna naraz, jeden ekran); płatność, wysyłka, publikacja: linia ZGODA WŁAŚCICIELA albo prośba do właściciela |
| **Konto w serwisie** (mail, usługa, klucz API) | robisz sam: rejestracja w Komputerze Jarva albo na telefonie („przez Google/GitHub”, kod SMS z telefonu), hasło w menedżerze haseł przeglądarki, zrzut każdego kroku; CAPTCHA próbujesz sam, nie przejdzie → prośba do właściciela o klik przez VNC. Klucz API: CLI usługi w terminalu (logowanie agenta, np. `instabox login --agent`) prosto do sejfu (`secret-tool`), nigdy do czatu ani pliku; klucz tylko w panelu WWW: klikasz „utwórz”, kopiuje właściciel przez VNC (Komputer ukrywa klucze przed agentem). Film z procesu: → wideo (motion graphic ze zrzutów, 30–45 s, do 15 MB) |

**Karta „złożenie”** (dla misji z ≥2 agentami): `assignee="jarvo"`, `parents` = wszystkie karty merytoryczne, skill
`zlozenie-pakietu`; cel: jeden pakiet w `@@MISSIONS_DIR@@/<MISJA>/zlozenie/out/` (INDEX.md z opisem i ścieżkami, bez
przerabiania treści).

## Po utworzeniu kart
1. Zapisz plan w `MISSION.md` (tabela kart: id, agent, zależy od, status) i dopisz misję do `INDEX.md` (skill `mission-ledger`).
2. Odpowiedz użytkownikowi jednym zdaniem: kto co robi, kiedy wynik. **Zakończ turę**: nie czekaj
   (`sleep`), nie odpytuj tablicy w pętli; zdarzenia z tablicy obudzą Cię same.

## Zdarzenia z tablicy (budzą Cię automatycznie)

| Zdarzenie | Twoja reakcja |
|---|---|
| `review_requested` | nic: recenzję robi tor review. Odpowiedź: `[SILENT]` |
| `changes_requested` (ocena odesłała do poprawki) | nic: wykonawca poprawia, tor review oceni ponownie. Odpowiedź: `[SILENT]`. Nie oceniasz karty drugi raz w rozmowie (SOUL, zasada 12) |
| `completed` karty pośredniej | zaktualizuj tabelę w MISSION.md. Odpowiedź: `[SILENT]` |
| `completed` ostatniej karty misji (zwykle „złożenie”) | zamknij misję i wyślij raport końcowy (`mission-ledger`) |
| `blocked` z `needs_input` | dodaj do kolejki decyzji i wyślij zbiorcze pytanie (`decision-queue`) |
| `blocked` z `capability` | przenieś: `kanban_create` dla właściwego agenta (ta sama treść + uwaga wykonawcy), potem `kanban_comment` na starej karcie („przeniesione do <nowa>”) i `kanban_complete(task_id=<stara>, summary="Przeniesione do <nowa>: <powód>")`. Nikt nie pasuje → zapytaj użytkownika |
| `gave_up`, `crashed`, `timed_out` | przeczytaj `kanban_show`: przejściowe → `kanban_unblock`; powtarzalne → eskalacja z dowodem |
| `block_loop_detected` (triage) | nie odblokowuj w ciemno: ustal przyczynę; jeśli potrzebny człowiek → decyzja |

Nie relacjonuj każdego zdarzenia. Mów tylko wtedy, gdy to zmienia coś dla użytkownika.

**Zatrzymanie karty w pracy** (właściciel mówi „stop”, karta utknęła, ekran przejmujesz sam):
`kanban_block(task_id, kind="needs_input", reason="<co dalej i kto>")`; pracownika zamknie dyspozytor. Pracownik
karty kończy swoją kartę sam: `kanban_block` albo `kanban_complete`. Nigdy `kill`, `pkill` ani `killall` procesu
pracownika: dyspozytor uznaje to za awarię i uruchamia kartę od nowa (16.11 t_87d11e3a trzy razy z rzędu); wtyczka
`jarvo-zgody` takie polecenie blokuje. `kill` wolno tylko na proces, który sam uruchomiłeś (nagrywanie, serwer).

## Typowe błędy
- Karta bez DoD → recenzja nie ma wobec czego oceniać. Zawsze mierzalne DoD.
- Dwie równoległe karty wymyślające tę samą rzecz → zdecyduj wcześniej.
- Karta dla nieistniejącego agenta → dispatcher jej nie wykona. Tylko nazwy z rosteru.
- `scratch` workspace dla wyników misji → pliki znikną po akceptacji. Używaj `dir` w katalogu misji.
- KONTEKST przepisany z rozmowy (historia, warianty, cudze wyniki wklejone treścią) → podwójny koszt w każdej turze
  wykonawcy. Najwyżej 5 punktów, wyniki rodziców ścieżką.
- „Decyzja właściciela” albo „właściciel zdecydował” w karcie, komentarzu, powodzie blokady, MISSION.md bez jego
  słów w cudzysłowie i godziny → przypisujesz mu coś, czego nie powiedział. Bez cytatu to `decyzja Jarva: …`
  (`decision-queue`, „Decyzja właściciela = jego słowa”); wtyczka `jarvo-zgody` odrzuca taki zapis.
