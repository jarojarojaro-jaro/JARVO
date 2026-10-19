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
| **Komputer Jarva**: pulpit z Chromium i terminalem w osobnym kontenerze `jarvo-komputer`, włączany `jarvo komputer on` | Linux, macOS (Colima), Windows (WSL), VPS bez monitora | pulpit działa (K1), kanał sterownika w K2 |
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
| K1 | Obraz i usługa `jarvo-komputer`: pulpit Xvnc, Chromium z drzewem dostępności, `cua-driver` 0.21.0 z sumą, filtr ruchu do sieci lokalnej, `jarvo komputer on/off/status/wyczysc/odswiez` | zrobione |
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
 │   komputer/jarvo_cua.py (bramka)   │ jarvo-komputer- │ cua-driver (sterownik ekranu)      │
 │ HQ Ekran (podgląd, Przejmij)       │   gniazda       │ sieć: internet tak, sieć lokalna nie│
 └──────────────────────────────────┘                 └───────────────────────────────────┘
```

Wolumen `jarvo-komputer-gniazda` jest w `jarvo-hermes` pod `/opt/jarvo/komputer`, a w Komputerze pod
`/run/jarvo-komputer`. Leżą w nim tylko gniazda: `rfb.sock` (ekran, K1), `cua.sock` (sterownik, K2).
Kontenery nie mają wspólnej sieci, więc poza gniazdami nie widzą się wcale.

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
| `mcp [--no-overlay]` | rozmowa MCP ze sterownikiem w Komputerze; gdy Komputer jest wyłączony: komunikat „jarvo komputer on” i kod 69; gdy pulpit działa, ale nie ma jeszcze kanału sterownika (`cua.sock`, K2): komunikat o etapie K2 i kod 69 |
| `status` | 0, gdy sterownik w Komputerze odpowiada; inaczej 1 i ten sam komunikat co `mcp` |
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
(`computer-use install`, `trycua/cua`, `cua-driver`) i sięganie do gniazd Komputera (`/opt/jarvo/komputer`).
To podpowiedź dla modelu, nie granica bezpieczeństwa: granicą są twarde zasady po stronie Komputera (K2).

## 5. Komputer Jarva (`infra/komputer`, K1)

Komputer jest profilem compose `komputer`: nie działa, dopóki go nie włączysz. Polecenia na komputerze z Jarvem:

| Polecenie | Co robi |
|---|---|
| `jarvo komputer on` | buduje obraz `jarvo-komputer:local` (pierwszy raz kilka minut, ok. 400 MB pobrania), dopisuje profil do `COMPOSE_PROFILES` i czeka, aż pulpit będzie zdrowy; potem ok. 3 s. Odmawia, gdy Docker ma mniej niż 4 GB pamięci (na macOS podpowiada `colima start --memory 8`) |
| `jarvo komputer off` | zatrzymuje Komputer i zdejmuje profil; stan przeglądarki zostaje |
| `jarvo komputer status` | włączony czy nie, zdrowie pulpitu, wersja sterownika, pamięć, czy flota widzi gniazdo ekranu |
| `jarvo komputer wyczysc` | po potwierdzeniu kasuje stan pulpitu (wolumen `jarvo-komputer-dom`: zalogowania, ciasteczka, historia, pobrane pliki) |
| `jarvo komputer odswiez` | buduje obraz od nowa z bieżącymi poprawkami Debiana i Chromium |

`scripts/deploy.sh` (a więc `jarvo update`) przebudowuje obraz po zmianie `infra/komputer/` i po healthcheckach
sprawdza, czy pulpit działa i czy flota widzi `rfb.sock`. `jarvo uninstall` usuwa obraz, a `--all` także wolumeny.

**Co jest w środku** (Debian trixie-slim przypięty sumą): Xvnc (TigerVNC) 1440×900 (`KOMPUTER_EKRAN`), xfwm4
z kompozytorem, sesyjny D-Bus z włączonym AT-SPI, Chromium z polskim interfejsem i drzewem dostępności
(`--force-renderer-accessibility`), `cua-driver` 0.21.0 z GitHuba sprawdzany sumą SHA-256 przy budowie. Procesy
pulpitu działają jako użytkownik `pulpit` (uid 10101), bez uprawnień i bez nowych uprawnień (`setpriv`), a PID 1
to `tini`. Telemetria i sprawdzanie aktualizacji sterownika są wyłączone zmiennymi i plikami konfiguracji.

**Ekran tylko przez gniazdo.** Xvnc nie słucha na TCP ani na abstrakcyjnym gnieździe X; RFB jest na
`rfb.sock` (0660, grupa 10000, czyli `hermes`), a X wymaga ciasteczka z `~/.Xauthority`. Kontener nie ma portów.

**Chromium** ma politykę `/etc/chromium/policies/managed/jarvo.json` (`infra/komputer/chromium.json`): bez
menedżera haseł, autouzupełniania kart i adresów, logowania do przeglądarki i synchronizacji, rozszerzeń
i narzędzi deweloperskich; bez `file://` i `javascript:`; pobrane pliki tylko do `~/Pobrane`, bez pytania
i bez automatycznego otwierania; WebRTC tylko przez publiczny interfejs. Okno wraca po zamknięciu.

**Filtr ruchu** (iptables w przestrzeni sieci kontenera, ustawiany przed pulpitem): internet tak; nie wolno
do zakresów prywatnych (RFC 1918), link-local z metadanymi chmury (`169.254.169.254`), CGNAT i Tailscale
(`100.64.0.0/10`), pętli zwrotnej poza samym kontenerem, zakresów specjalnych i multicastu, do publicznych adresów
hosta (`KOMPUTER_BLOKADA`, uzupełniane przez `jarvo komputer on` i deploy na Linuksie) ani na port 25. IPv6
działa tylko lokalnie. Start sam próbuje połączyć się z metadanymi chmury i z hostem (porty 9119 i 22); jeśli
filtr przepuści, albo iptables nie działa, Komputer nie wstaje. Potem `start.sh` uruchamia się ponownie bez
`NET_ADMIN`, więc nic w kontenerze filtra już nie zmieni. Komputer ma własną sieć `jarvo-komputer-net`, bez floty.

**Zasoby** (zmierzone w piaskownicy): ok. 0,25–0,3 GB pamięci w spoczynku, ok. 0,66 GB z pięcioma otwartymi
stronami (szczyt 0,83 GB). Limity w `compose/.env`: `KOMPUTER_MEM_LIMIT` (domyślnie 2g), `KOMPUTER_CPUS`
(2, deploy przycina do liczby rdzeni), 2048 procesów, 1 GB `/dev/shm`. Uprawnienia kontenera: wszystkie zdjęte,
dodane tylko te do filtra, katalogów i zmiany użytkownika; `no-new-privileges`.

## 6. Bezpieczeństwo: zasady i ryzyka

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

## 7. Źródła

| Źródło | Licencja | Stan |
|---|---|---|
| `cua-driver` (trycua/cua, `cua-driver-rs` 0.21.0, później 0.36) | MIT | w obrazie `jarvo-komputer` (K1): przegląd, próba w kontenerze, sumy SHA-256 dla amd64 i arm64 w `vendor/zrodla.yaml`; telemetrię i sprawdzanie aktualizacji wyłączają zmienne, pliki konfiguracji i bramka |
| Codex Computer Use (OpenAI) | zamknięte | tylko wzorce zachowania z materiałów publicznych; kodu nie bierzemy |
| Pakiety Debiana w obrazie (TigerVNC, xfwm4, Chromium, D-Bus, AT-SPI, iptables) | GPL-2.0, BSD, LGPL i inne | `docs/SOURCES.md`, tabela komponentów obrazu `jarvo-komputer` |
| LCU (amontlabs/lcu) | MIT | odrzucone (uruchamia zamknięty program OpenAI); wzorce: zgoda na aplikację, dziennik bez treści, sprzątanie po turze |
