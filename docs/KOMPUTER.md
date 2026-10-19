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
| **Komputer Jarva**: pulpit z Chromium i terminalem w osobnym kontenerze `jarvo-komputer`, włączany `jarvo komputer on` | Linux, macOS (Colima), Windows (WSL), VPS bez monitora | pulpit, wejście sterownika i twarde zasady działają (K1, K2) |
| **Operator**: agent, który steruje ekranem (najpierw drzewo dostępności, zrzut tylko gdy trzeba) | wszędzie tam, gdzie Komputer | etap K3 |
| **Ekran w HQ**: podgląd na żywo, Przejmij, Oddaj, Zatrzymaj | zalogowany dashboard | etap K4 |
| **Terminal i serwery**: powłoka w Komputerze, ekrany programów tekstowych, Twoje serwery przez SSH | wszędzie | etap K5 |
| **Ręce**: Twój komputer na czas, który sam ustawisz, tylko w aplikacjach, które wskażesz | Windows, macOS, Linux (X11) | etap K6 |

Czego agent nigdy nie zrobi sam:
- nie zapłaci, nie kupi, nie zaloguje się, nie wyśle i nie opublikuje: te kliknięcia zostawia Tobie
  w Ekranie HQ (twarda reguła w Komputerze, nie tylko w poleceniach dla modelu);
- nie wpisze hasła, numeru karty, kodu BLIK ani kodu 2FA;
- nie zdejmie sobie pauzy: `jarvo komputer pauza` zatrzymuje go od razu, wznawiasz tylko Ty;
- nie włączy sobie Twojego komputera: robisz to tylko Ty, na swoim komputerze;
- nie zaktualizuje sam sterownika: każda wersja przechodzi przegląd i ma przypiętą sumę.

## 2. Etapy

| Etap | Zakres | Stan |
|---|---|---|
| K0 | Bramka sterownika (`komputer/jarvo_cua.py`), zakazy w `deny.yaml`, reguły walidatora | zrobione |
| K1 | Obraz i usługa `jarvo-komputer`: pulpit Xvnc, Chromium z drzewem dostępności, `cua-driver` 0.21.0 z sumą, filtr ruchu do sieci lokalnej, `jarvo komputer on/off/status/wyczysc/odswiez` | zrobione |
| K2 | Wejście sterownika w Komputerze (`wejscie.py`, `zasady.py`): kanał MCP przez gniazdo unix, twarde zasady (płatności, logowanie, hasła, karty, kody, sekrety, zakazane narzędzia i aplikacje), ukrywanie sekretów w odpowiedziach, pauza tylko do zdjęcia przez właściciela, dziennik bez treści, `jarvo komputer pauza/wznow/dziennik`, test na żywo `scripts/komputer-test.sh` | zrobione |
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
`/run/jarvo-komputer`. Leżą w nim tylko gniazda: `rfb.sock` (ekran, K1), `cua.sock` (wejście sterownika, K2)
i `ster.sock` (pauza, stan i dziennik wejścia, K2).
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
| `mcp [--no-overlay]` | przepuszcza rozmowę MCP (bajty w obie strony) do wejścia w Komputerze na `cua.sock`; zasady sprawdza wejście (§6), bramka nie zna treści. Gdy Komputer jest wyłączony: komunikat „jarvo komputer on” i kod 69; gdy pulpit działa, ale wejście nie odpowiada: komunikat z `jarvo komputer status` i `jarvo logs komputer` i kod 69 |
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
To podpowiedź dla modelu, nie granica bezpieczeństwa: granicą są twarde zasady po stronie Komputera (§6).

## 5. Komputer Jarva (`infra/komputer`, K1)

Komputer jest profilem compose `komputer`: nie działa, dopóki go nie włączysz. Polecenia na komputerze z Jarvem:

| Polecenie | Co robi |
|---|---|
| `jarvo komputer on` | buduje obraz `jarvo-komputer:local` (pierwszy raz kilka minut, ok. 400 MB pobrania), dopisuje profil do `COMPOSE_PROFILES` i czeka, aż pulpit będzie zdrowy; potem ok. 3 s. Odmawia, gdy Docker ma mniej niż 4 GB pamięci (na macOS podpowiada `colima start --memory 8`) |
| `jarvo komputer off` | zatrzymuje Komputer i zdejmuje profil; stan przeglądarki zostaje |
| `jarvo komputer status` | włączony czy nie, zdrowie pulpitu, wersja sterownika, stan wejścia (pauza, sesje agentów, AT-SPI), pamięć, czy flota widzi gniazdo Komputera |
| `jarvo komputer pauza` | zatrzymuje agenta od razu: patrzeć może, klikać i pisać nie; pauza trwa także po restarcie |
| `jarvo komputer wznow` | zdejmuje pauzę; robi to tylko właściciel (agent floty dostaje odmowę) |
| `jarvo komputer dziennik [N]` | ostatnie N decyzji wejścia (domyślnie 30): narzędzie, decyzja, zasada, cel, bez wpisywanych treści |
| `jarvo komputer wyczysc` | po potwierdzeniu kasuje stan pulpitu (wolumen `jarvo-komputer-dom`: zalogowania, ciasteczka, historia, pobrane pliki) |
| `jarvo komputer odswiez` | buduje obraz od nowa z bieżącymi poprawkami Debiana i Chromium |

`scripts/deploy.sh` (a więc `jarvo update`) przebudowuje obraz po zmianie `infra/komputer/` i po healthcheckach
sprawdza, czy pulpit i wejście działają i czy flota widzi `rfb.sock` i `cua.sock`. `jarvo uninstall` usuwa obraz, a `--all` także wolumeny.

**Co jest w środku** (Debian trixie-slim przypięty sumą): Xvnc (TigerVNC) 1440×900 (`KOMPUTER_EKRAN`), xfwm4
z kompozytorem, sesyjny D-Bus z włączonym AT-SPI, Chromium z polskim interfejsem (`LANGUAGE=pl`) i drzewem
dostępności (flagi w `/etc/chromium.d/jarvo` z `infra/komputer/chromium-flagi`, także dla okien otwieranych przez
sterownik), `cua-driver` 0.21.0 z GitHuba sprawdzany sumą SHA-256 przy budowie, wejście sterownika (`wejscie.py`,
`zasady.py`, Python z `python3-gi` do AT-SPI). Po restarcie kontenera Chromium nie pyta o przywrócenie kart. Procesy
pulpitu działają jako użytkownik `pulpit` (uid 10101), bez uprawnień i bez nowych uprawnień (`setpriv`), a PID 1
to `tini`. Telemetria i sprawdzanie aktualizacji sterownika są wyłączone zmiennymi i plikami konfiguracji.

**Ekran tylko przez gniazdo.** Xvnc nie słucha na TCP ani na abstrakcyjnym gnieździe X; RFB jest na
`rfb.sock` (0660, grupa 10000, czyli `hermes`), a X wymaga ciasteczka z `~/.Xauthority`. Kontener nie ma portów.

**Chromium** ma politykę `/etc/chromium/policies/managed/jarvo.json` (`infra/komputer/chromium.json`): bez
menedżera haseł, autouzupełniania kart i adresów, logowania do przeglądarki i synchronizacji, rozszerzeń
i narzędzi deweloperskich; bez `file://`, `javascript:`, `chrome://flags`, `chrome://inspect` i `devtools://`; pobrane pliki tylko do `~/Pobrane`, bez pytania
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

## 6. Wejście sterownika i twarde zasady (`infra/komputer/wejscie.py`, `zasady.py`, K2)

Flota nie rozmawia ze sterownikiem bezpośrednio. Każde połączenie z `cua.sock` to jedna sesja MCP w procesie
wejścia (użytkownik `pulpit`, wznawiany przez `start.sh` po awarii, uruchamiany przed Chromium). Wejście startuje
`cua-driver mcp` dopiero przy pierwszej wiadomości, przepuszcza rozmowę w obie strony i po drodze:

- **sprawdza każde `tools/call` w `zasady.ocen`, zanim dostanie je sterownik.** Odmowa wraca do agenta jako wynik
  narzędzia z `isError` i `structuredContent`: `code` (`wymaga_czlowieka`, `wstrzymane`, `zablokowane`),
  `rule` (zasada), `decision` i `next_step` (`ask_owner`, `wait_for_owner`, `wait_and_retry`, `choose_another_way`);
- **pokazuje tylko dopuszczone narzędzia** (`tools/list`): odczyt (stan okna, drzewo, zrzut, okna, aplikacje),
  sesja (kursor, `set_config` tylko dla `capture_scope`, `capture_mode`, `max_image_dimension`, okno na wierzch)
  i działania (klik, podwójny i prawy klik, przeciąganie, przewijanie, pisanie, klawisze, `set_value`,
  `launch_app`, `kill_app`, menu). Bez `page` i `browser_*` (JavaScript, DevTools), schowka, `mouse_button_*`
  i `mouse_drag`, nagrywania i odtwarzania, aktualizacji oraz każdego nowego narzędzia, dopóki go nie przejrzymy;
- **dopisuje zasady do instrukcji serwera** (`initialize`), po polsku i po angielsku;
- **ukrywa sekrety w każdej odpowiedzi** (tekst, drzewo dostępności, komunikaty błędów, także odpowiedzi bez
  znanego id): klucze API i tokeny (OpenAI, Anthropic, OpenRouter, GitHub, GitLab, AWS, Slack, Google,
  Hugging Face, npm, Stripe, token bota Telegrama), JWT, klucze prywatne, numery kart (z sumą Luhna) i wartości pól haseł zastępuje
  znacznik `[ukryte przez Komputer Jarva]`;
- **pilnuje protokołu**: tylko pojedyncze wiadomości (bez batch), tylko `initialize`, `ping`, `tools/list`,
  `tools/call` (argumenty jako obiekt) i powiadomienia; sterownik dostaje wiadomość zapisaną od nowa z tego,
  co ocenił, a nie surowe bajty agenta; id żądania w toku nie da się użyć drugi raz (odpowiedź zawsze trafia do swojego
  wywołania); do 1 MB na wiadomość, do 4 sesji naraz, do 120 działań na minutę;
- **daje ekran jednej sesji naraz** (K3): patrzeć może każda, ale klikać, pisać i przestawiać okna tylko ta,
  która działała ostatnio. Druga sesja Operatora (np. druga karta kanbana albo rozmowa w HQ w trakcie karty)
  dostaje odmowę `zajete` z `next_step: wait_and_retry`. Ekran zwalnia koniec tamtej sesji albo 120 s bez jej działań.

**Twarde zasady** (`infra/komputer/zasady.py`, czyste funkcje, testy w `tests/test_komputer_zasady.py`):

| Zasada | Decyzja |
|---|---|
| klik, podwójny klik, przeciągnięcie zaczęte albo skończone na przycisku, Enter, spacja albo pisanie na przycisku z fokusem, gdy przycisk lub link to „Kup”, „Zamów”, „Zapłać”, „BLIK”, „Przelew”, „Subskrybuj”, „Zaloguj”, „Zarejestruj”, „Utwórz konto”, „Autoryzuj”, „Wyślij”, „Opublikuj”, „Udostępnij”, „Usuń konto” (i angielskie odpowiedniki), także na tekście wewnątrz takiego przycisku; zgoda „Zezwól” / „Allow” jako cały napis. Napisy porównujemy po normalizacji NFKC, bez znaków niewidocznych | robi właściciel (`przycisk_wrazliwy`) |
| Enter w polu formularza, w którym jest taki przycisk (wysłałby formularz), poza polem wieloliniowym | robi właściciel (`formularz_wrazliwy`) |
| pisanie, wklejanie i Enter w polu hasła, karty, CVV, BLIK, PIN, kodu SMS, 2FA, jednorazowego, tokenu | robi właściciel (`pole_wrazliwe`) |
| numer karty w dowolnym tekście | robi właściciel (`karta`) |
| klucz, token albo klucz prywatny w tekście; adres `javascript:`, `data:`, `file:`, `chrome:`, `devtools:`, `view-source:` | zablokowane |
| pisanie, gdy nie wiadomo, gdzie trafi tekst (brak fokusu); klik w element spoza migawek tej sesji albo w punkt bez działającego AT-SPI; element i punkt naraz | zablokowane (`brak_fokusu`, `nieznany_cel`, `cel`) |
| `launch_app` innego programu niż Chromium, z `launch_path` lub flagami, z adresem innym niż http(s); `kill_app` innego procesu niż Chromium | zablokowane |
| narzędzia deweloperskie i systemowe skróty (Ctrl+Shift+I/J/C/O, F12, Ctrl+Shift+Delete, Alt+F2); klik po `zoom`; zapis zrzutu do pliku | zablokowane |
| wszystko poza odczytem przy pauzie | wstrzymane |
| działanie, gdy ekranem steruje inna sesja (ostatnie działanie mniej niż 120 s temu) | zablokowane (`zajete`, czekaj i spróbuj znowu) |

**Skąd wejście wie, w co trafi działanie.** Nie z deklaracji agenta: element ze `element_token` bierze z migawek
sterownika z tej sesji (rola, napis, przodkowie, przyciski formularza), punkt `x, y` przelicza na ekran i pyta
AT-SPI o najgłębszy element w tym miejscu (ok. 20 ms), a pole z fokusem klawiatury zna ze zdarzeń AT-SPI
(rola, nazwa, atrybuty HTML: `tag`, `html-input-name`, `text-input-type`, `autocomplete`). Gdy tego nie da się
ustalić, działanie nie przechodzi.

**Pauza i dziennik** (`ster.sock`, polecenia JSON w jednej linii: `stan`, `pauza`, `wznow`, `dziennik`). Pauzę
włączy każdy, kto widzi gniazdo (flota, HQ w K4); zdjąć ją może tylko właściciel: wejście sprawdza nadawcę
(`SO_PEERCRED`) i przepuszcza tylko proces pulpitu albo root w kontenerze Komputera, czyli `jarvo komputer wznow`.
Pauza ma autora i powód (`{"polecenie": "pauza", "powod": "…"}`): pauza od floty to **prośba Operatora do
właściciela** („Operator czeka na właściciela: zaloguj się do panelu sklepu”), pauza od właściciela to
„właściciel zatrzymał Komputer”. Prośba floty nie nadpisze pauzy właściciela. Powód (jedna linia, do 300 znaków,
bez sekretów) widać w `jarvo komputer status` i w odmowie `wstrzymane`, którą dostaje agent; do dziennika nie trafia.
Pauza jest zapisana w `~/.jarvo/pauza` (JSON: kto, od kiedy, powód) i trwa po restarcie. Dziennik `~/.jarvo/dziennik.jsonl` (wolumen
`jarvo-komputer-dom`, 2 MB i jedna kopia) ma każde działanie i każdą odmowę: czas, sesja, narzędzie, decyzja,
zasada, cel (rola i napis), liczba wpisanych znaków albo naciśnięte klawisze, liczba ukrytych sekretów. Wpisanego
tekstu w nim nie ma.

**Test na żywo**: `bash scripts/komputer-test.sh` (Komputer włączony) stawia w Komputerze stronę testową
(wyszukiwarka i koszyk z polami hasła, karty, BLIK, przyciskami płatności i kluczem API w treści) i prowadzi
rozmowę MCP z `jarvo-hermes` jako `hermes`, tą samą drogą co Hermes: 61 sprawdzeń (narzędzia, aplikacje,
ukrywanie, kliknięcia elementem i w punkt, pisanie, Enter w formularzach, skróty, powtórzone id, druga sesja
naraz, prośba Operatora, pauza i wznowienie, dziennik).

## 7. Bezpieczeństwo: zasady i ryzyka

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
- **Ryzyka resztkowe wejścia (K2):** Chromium działa z `--no-sandbox` (piaskownica wymaga przestrzeni nazw
  użytkownika, a kontener ma `no-new-privileges`; granicą jest kontener bez kluczy i z filtrem ruchu); strony
  rysowane w całości na `canvas` nie mają drzewa dostępności, więc wrażliwy przycisk bez napisu przejdzie jak
  zwykły klik; wysyłkę formularza skryptem strony (bez `<form>`) wejście rozpozna tylko po napisie przycisku;
  zwykłe przejście pod adres (link, pasek adresu) nie jest blokowane; agent z terminalem we flocie może włączyć
  pauzę i czytać dziennik (bez treści), ale nie zdejmie pauzy. Schowek przy przejęciu ekranu w HQ ustali K4.

## 8. Źródła

| Źródło | Licencja | Stan |
|---|---|---|
| `cua-driver` (trycua/cua, `cua-driver-rs` 0.21.0, później 0.36) | MIT | w obrazie `jarvo-komputer` (K1): przegląd, próba w kontenerze, sumy SHA-256 dla amd64 i arm64 w `vendor/zrodla.yaml`; 0.21.0, bo z nią działa przypięty Hermes (nowsze zmieniają argumenty kliknięcia); telemetrię i sprawdzanie aktualizacji wyłączają zmienne, pliki konfiguracji i bramka |
| Codex Computer Use (OpenAI) | zamknięte | tylko wzorce zachowania z materiałów publicznych; kodu nie bierzemy |
| Pakiety Debiana w obrazie (TigerVNC, xfwm4, Chromium, D-Bus, AT-SPI, `python3-gi` z `gir1.2-atspi-2.0`, iptables) | GPL-2.0, BSD, LGPL i inne | `docs/SOURCES.md`, tabela komponentów obrazu `jarvo-komputer` |
| LCU (amontlabs/lcu) | MIT | odrzucone (uruchamia zamknięty program OpenAI); wzorce: zgoda na aplikację, dziennik bez treści, sprzątanie po turze |
