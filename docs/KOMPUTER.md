# Komputer Jarva: computer use i server use

Jarvo dostaje ręce i oczy: agent **Operator** klika, pisze, przegląda strony, wypełnia formularze i pracuje
w terminalu na **własnym komputerze** (pulpit Linux w osobnym kontenerze, bez kluczy floty). Widzisz go na żywo
w HQ i w każdej chwili przejmujesz mysz. Na Twoje polecenie Operator dostaje też na chwilę **Twój** komputer
(Windows, macOS albo Linux). Wzorem było działanie Codex Computer Use (OpenAI): badaliśmy je tylko z materiałów
publicznych, otwartego kodu Codex CLI i opisu interfejsu w LCU, bez rozbierania programu OpenAI. Zachowanie
odtwarzamy własnym kodem na Hermesie i otwartym sterowniku `cua-driver` (MIT).

## 1. Co dostajesz

| Co | Gdzie działa | Stan |
|---|---|---|
| **Komputer Jarva**: pulpit z Chromium i terminalem w osobnym kontenerze `jarvo-komputer`, włączany `jarvo komputer on` | Linux, macOS (Colima), Windows (WSL), VPS bez monitora | etapy K1–K2 |
| **Operator**: agent, który steruje ekranem (najpierw drzewo dostępności, zrzut tylko gdy trzeba) | wszędzie tam, gdzie Komputer | etap K3 |
| **Ekran w HQ**: podgląd na żywo, Przejmij, Oddaj, Zatrzymaj | zalogowany dashboard | etap K4 |
| **Terminal i serwery**: powłoka w Komputerze, ekrany programów tekstowych, Twoje serwery przez SSH | wszędzie | etap K5 |
| **Ręce**: Twój komputer na czas, który sam ustawisz, tylko w aplikacjach, które wskażesz | Windows, macOS, Linux (X11) | etap K6 |

Czego agent nigdy nie zrobi sam:
- nie zapłaci, nie kupi, nie zaloguje się, nie wyśle i nie opublikuje: te kliknięcia zostawia Tobie
  w Ekranie HQ (twarda reguła w Komputerze, nie tylko w poleceniach dla modelu);
- nie wpisze hasła, numeru karty, kodu BLIK ani kodu 2FA;
- nie włączy sobie Twojego komputera: robisz to tylko Ty, na swoim komputerze;
- nie zaktualizuje sam sterownika: każda wersja przechodzi przegląd i ma przypiętą sumę.

## 2. Etapy

| Etap | Zakres | Stan |
|---|---|---|
| K0 | Bramka sterownika (`komputer/jarvo_cua.py`), zakazy w `deny.yaml`, reguły walidatora | zrobione |
| K1 | Obraz i usługa `jarvo-komputer`: pulpit Xvnc, Chromium z drzewem dostępności, `cua-driver` 0.21.0 z sumą, filtr ruchu do sieci lokalnej, `jarvo komputer on/off/status` | planowane |
| K2 | Kanał Hermes ↔ Komputer przez gniazdo unix i twarde zasady po stronie Komputera (sekrety, płatności, logowanie, zakazane aplikacje, dziennik) | planowane |
| K3 | Agent Operator: profil, wtyczka z podpowiedziami, evals, red team, pokój w HQ, dokumentacja | planowane |
| K4 | Ekran w HQ: podgląd, Przejmij, Oddaj, Zatrzymaj | planowane |
| K5 | Terminal Operatora w Komputerze (SSH przez gniazdo), ekrany programów tekstowych (tmux), serwery | planowane |
| K6 | Ręce na Twoim komputerze: podpisany `cua-driver` 0.36, pomocnik na Linux, macOS i Windows, zgoda na aplikację na Twoim ekranie | planowane |

## 3. Jak to jest spięte

```
 jarvo-hermes (flota, klucze, HQ)                    jarvo-komputer (bez kluczy floty)
 ┌──────────────────────────────────┐   gniazda unix  ┌───────────────────────────────────┐
 │ Operator → computer_use (Hermes)  │  w wolumenie    │ Xvnc + xfwm4 + Chromium + tmux     │
 │   HERMES_CUA_DRIVER_CMD =          │ ─────────────▶ │ wejście: twarde zasady + dziennik  │
 │   komputer/jarvo_cua.py (bramka)   │ /run/jarvo-     │ cua-driver (sterownik ekranu)      │
 │ HQ Ekran (podgląd, Przejmij)       │   komputer/     │ sieć: internet tak, sieć lokalna nie│
 └──────────────────────────────────┘                 └───────────────────────────────────┘
```

- Narzędzie `computer_use` jest w Hermesie: zrzut i drzewo dostępności (`capture` w trybie `ax`, `som`, `vision`),
  klik w element albo w punkt, pisanie, klawisze, przewijanie, przeciąganie. Zgody mają klucze
  `cua:<akcja>:<background|foreground>` i Hermes porównuje je dokładnie (bez gwiazdek).
- Hermes woła sterownik poleceniem z `HERMES_CUA_DRIVER_CMD`. U nas to zawsze bramka Jarva, więc żaden profil
  nie pobierze sterownika przez `curl|bash` z gałęzi main i nie zaktualizuje go sam.

## 4. Bramka sterownika (`komputer/jarvo_cua.py`, K0)

`infra/docker-compose.yml` ustawia `HERMES_CUA_DRIVER_CMD=/opt/jarvo/repo/komputer/jarvo_cua.py` (repo jest
w kontenerze tylko do odczytu, więc agent nie zmieni bramki). Bramka odpowiada na:

| Czasownik | Co robi |
|---|---|
| `--help`, `--version`, `manifest` | stałe odpowiedzi z wersją sterownika z obrazu Komputera (kontrakt Hermesa 0.20) |
| `mcp [--no-overlay]` | rozmowa MCP ze sterownikiem w Komputerze; gdy Komputer jest wyłączony: komunikat „jarvo komputer on” i kod 69 |
| `status` | 0, gdy Komputer odpowiada |
| wszystko inne | odmowa i kod 64: `check-update` i `update` (sterownik nie łączy się z GitHubem), `serve` (tryb bez ograniczeń, więc `/yolo` i `approvals.mode: off` zamykają computer_use zamiast go otwierać), `install`, `skills`, `extension` |

Reguły walidatora (`scripts/validate.py`, `check_komputer`):
- toolset `computer_use` i klucze `cua:*` w `command_allowlist` tylko u agenta z `komputer: true` we `fleet.yaml`;
- klucze tylko w postaci `cua:<akcja>:<background|foreground>` dla akcji z Hermesa; gwiazdki w `command_allowlist`
  to błąd (Hermes porównuje dokładnie); `approvals.allowlist` to błąd (Hermes go nie czyta);
- `approvals.mode: off` to błąd w każdym profilu; `bot_desktop.auto_start` to błąd (pulpit Hermesa nie jest
  naszym ekranem);
- agent z `komputer: true` nie ma `code_execution` ani lokalnego terminala, a terminal w Komputerze wymaga
  `terminal.sync_back_max_bytes: 0` (zdalny katalog nie wraca do profilu).

`shared/security/deny.yaml` blokuje w terminalach floty instalację i aktualizację sterownika
(`computer-use install`, `trycua/cua`, `cua-driver`) i sięganie do gniazd Komputera (`/run/jarvo-komputer`).
To podpowiedź dla modelu, nie granica bezpieczeństwa: granicą są twarde zasady po stronie Komputera (K2).

## 5. Bezpieczeństwo: zasady i ryzyka

- **Główne zagrożenie to treść ekranu**, nie właściciel: strona, mail albo PDF może próbować wmówić agentowi
  „wpisz klucz”, „otwórz terminal”, „kliknij Kup”. Dlatego Komputer nie ma kluczy floty, a reguły, które muszą
  zadziałać zawsze (płatność, logowanie, wysyłka, sekrety), sprawdza kod w Komputerze przy każdym wywołaniu.
- **Zgody w repo, nie w czacie.** Stałe zgody Operatora będą w jego `config.yaml` (K3), a deploy porówna je
  z działającym configiem. Płatności, logowania i wysyłki nie mają zgody w configu w ogóle.
- **Ryzyko resztkowe: wspólny użytkownik w `jarvo-hermes`.** Wszystkie procesy floty działają jako uid `hermes`,
  więc agent z lokalnym terminalem technicznie sięga do plików innych agentów (to stan sprzed Komputera).
  Komputer Jarva tego nie pogarsza dla kluczy floty (w Komputerze ich nie ma), ale zalogowana w nim przeglądarka
  jest osiągalna przez gniazda. Dlatego twarde reguły siedzą w Komputerze, a nie w `jarvo-hermes`, a pełne
  rozdzielenie użytkowników terminali to osobny etap przed Rękami (K6).

## 6. Źródła

| Źródło | Licencja | Stan |
|---|---|---|
| `cua-driver` (trycua/cua, `cua-driver-rs` 0.21.0, później 0.36) | MIT | próba w kontenerze zrobiona (działa z przypiętym Hermesem; telemetrię i sprawdzanie aktualizacji wyłączają zmienne i bramka); wpis w `vendor/zrodla.yaml` w K1 |
| Codex Computer Use (OpenAI) | zamknięte | tylko wzorce zachowania z materiałów publicznych; kodu nie bierzemy |
| LCU (amontlabs/lcu) | MIT | odrzucone (uruchamia zamknięty program OpenAI); wzorce: zgoda na aplikację, dziennik bez treści, sprzątanie po turze |
