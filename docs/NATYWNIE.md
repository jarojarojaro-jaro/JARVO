# Jarvo natywnie: plan przejścia bez Dockera i bez WSL

Plan z 2026-10-24, spisany przed pierwszą linią kodu. Stan repo: `main` 7289518. Hermes: v2026.9.24 = pakiet 0.21.5 =
commit `f97608f178d1ffeca59860195ab7da295f7c8e5f`.

**Cel właściciela.** Jarvo instaluje się jednym poleceniem i działa natywnie na Windows, macOS i Linuksie: bez Dockera,
bez WSL i bez kontenera na drodze użytkownika, z każdą funkcją, którą ma dziś. Ten dokument to mapa „co dziś robi
kontener → czym to zastępujemy”, architektura, etapy, ryzyka i decyzje. **Nic z tego nie jest jeszcze wdrożone.**
Stan etapów prowadzimy w sekcji (g) i w roadmapie [PLAN.md](PLAN.md); dzisiejszą instalację opisuje [INSTALER.md](INSTALER.md).

**Skąd to jest.** Rozpoznanie z 2026-10-24 objęło 14 przeglądów: obraz, paczki, usługi, instalator, Hermes (CLI i usługi),
panel, skarbiec, flotę, Komputer, testy, dokumenty i dystrybucję narzędzi. Do tego krytyk luk i 8 uzupełnień, próby
na Windows 11 właściciela (stara instalacja tylko do odczytu) i kod Hermesa z przypiętego commitu. Najważniejsze
ustalenia sprawdziłem jeszcze raz na żywo: lista jest w sekcji (l).

**Jak czytać**
- „niesprawdzone” znaczy, że nikt tego nie potwierdził ani w sieci, ani testem. Takie miejsce sprawdzamy, zanim stanie
  się kodem.
- Wersje i sumy (skrócone do 8 znaków) to wynik rozpoznania. Do `vendor/zrodla.yaml` trafiają dopiero po przeglądzie
  z [SOURCES.md](SOURCES.md), w etapie, który ich używa.
- `<root>`, `<program>`, `<dane>`, `<stan>` to katalogi z sekcji (c1). `<profil>` to katalog profilu agenta w `<dane>`.
- Kod wiersza (np. **H04**) to numer pozycji mapy. Etapy w (g) i ryzyka w (h) odwołują się do tych kodów.
- Skróty platform: W = Windows 10/11 x64 (arm64 przez emulację x64, jeśli nie napisano inaczej); mac = macOS arm64 (Apple Silicon; Intel nie jest wspierany, decyzja I06);
  Linux = x64 i arm64.

## (a) Cel i zasady

**Cel.** Jarvo instaluje się jednym poleceniem i działa natywnie.
- Windows 10/11: `irm https://jarvo.pl/install.ps1 | iex` w PowerShellu. Bez WSL, bez Dockera, bez admina, bez restartu.
- macOS arm64 (Apple Silicon): `curl -fsSL https://jarvo.pl/install.sh | bash`. Bez Homebrew i bez Colimy. macOS x64 (Intel) nie jest wspierany (decyzja I06): instalator mówi to wprost i kończy pracę.
- Linux x64 i arm64: to samo polecenie, bez Docker Engine. sudo najwyżej raz, na biblioteki Chromium, jeśli ich brak.

Ma działać wszystko, co działa dziś: czat w terminalu z trybami zgód, pierwsze uruchomienie (mózg, pierwsze spotkanie, pierwsza sesja), cała flota i zlecanie pracy specjalistom, panel w przeglądarce, skarbiec, rutyny, Telegram, ciężkie narzędzia, Komputer Jarva, polecenia `jarvo` i migracja ze starej instalacji.

**Zasady.**
1. Bez Dockera i WSL na ścieżce użytkownika. Docker zostaje tylko: na VPS do czasu przejścia, w teście migracji w CI i jako opcja „mocna izolacja” Komputera na Linuksie.
2. Każda funkcja działa albo ma zamiennik i jawny wpis „brak” z powodem (np. Lightpanda na Windows).
3. Każdy plik z sieci ma przypiętą wersję i sumę sha256, sprawdzaną przed rozpakowaniem. Bez „latest”. Bez winget, brew, apt i bez `irm | iex` cudzych instalatorów. Bez leniwych instalacji Hermesa.
4. Jedno źródło wersji: `vendor/zrodla.yaml`, z którego powstaje `vendor/natywne.lock.json`. Ten plik czyta PowerShell 5.1, bash i Python. Obraz dla VPS bierze piny z tego samego pliku.
5. Jarvo zostaje nadrzędny. Procesy nadzoruje nasz `jarvo serwis` (Python), a uruchamia go mechanizm systemu. Nie dokładamy NSSM, WinSW ani supervisord.
6. Jarvo nie miesza się z prywatnym Hermesem właściciela. Ma własny HERMES_HOME i własny katalog blokad bramy. `hermes` nie trafia do globalnego PATH. Nie ustawiamy zmiennych użytkownika.
7. Każde nowe źródło i każda nowa platforma starego źródła przechodzi przegląd z docs/SOURCES.md (rozszerzenie w R13).
8. Każdy etap to osobny commit z testem w CI na 5 runnerach i próbą w prawdziwej instalacji.
9. Mówimy uczciwie: natywnie nie ma izolacji kontenera. Terminal agenta działa z prawami właściciela. Zastępują ją tryby zgód i ograniczenia z sekcji (d).

## (b) Mapa: co dziś robi kontener → czym zastępujemy

### Hermes i procesy w tle

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **H01** Kod Hermesa | obraz `nousresearch/hermes-agent:v2026.9.24@sha256:fca358f1`, kod w /opt/hermes | `git clone` + checkout f97608f do `<program>\hermes\<commit>`; bez install.ps1 Hermesa | to samo; arm64 to Tier 1, Intel „Unsupported” (I06) | to samo; x64 i arm64 to Tier 1 | install.ps1 Hermesa pobiera uv, Node i PortableGit bez sum, nadpisuje HERMES_HOME użytkownika i zabija każdy hermes.exe, więc go nie używamy |
| **H02** Zależności Pythona Hermesa | `uv sync --frozen` w obrazie, extras: all, messaging, otlp, anthropic, bedrock, azure-identity, matrix, google-chat | `uv sync --locked` bez UV_NO_CONFIG, te same extras bez matrix (python-olm ma tylko sdist); koła win_amd64 są | arm64: koła są; Intel: cryptography 50.0.0 nie ma koła x86_64, potrzebne nasze koło z CI (I06) | koła manylinux są | błąd locka zatrzymuje instalację; nigdy nie schodzimy do PyPI bez sum (dziś install.ps1 Hermesa robi to po cichu) |
| **H03** Leniwe instalacje Hermesa | `HERMES_DISABLE_LAZY_INSTALLS=1` w obrazie | `security.allow_lazy_installs: false` + `HERMES_DISABLE_LAZY_INSTALLS=1`; Chromium, ddgs i edge-tts dostarczamy sami z sumą | to samo | to samo | bez tego Hermes sam ściąga `agent-browser install`, Node „latest” i ffmpeg z winget/brew/apt, bez sum |
| **H04** Brama (gateway, multipleks profili) | s6, slot gateway-default, `gateway run --replace` | `python -m hermes_cli.main gateway run --external-supervisor` pod `jarvo serwis`; nie `hermes gateway install` (zadanie z VBS nie podnosi bramy po awarii) | ten sam proces pod nadzorcą (LaunchAgent Jarva) | ten sam proces pod nadzorcą (systemd --user Jarva) | kod 75 = restart, 78 = postój; na Windows nie ma restartu przez SIGUSR1 |
| **H05** API server 127.0.0.1:8642 i klucze | klucz hosta generuje stage2-hook obrazu Hermesa | klucz hosta i kluczy profili generuje instalator (`secrets.token_hex(32)`); doctor sprawdza, czy port jest wolny | to samo | to samo | bez klucza nie ma `/v1/runs`, a wtedy HQ nie prowadzi rozmów |
| **H06** Rutyny (cron) | wątek w bramie; 4 rutyny Jarva, instalowane jako wstrzymane, wznawiane przez `--resume-cron` | ten sam wątek w natywnej bramie (blokada msvcrt jest w kodzie); działa tylko przy zalogowanym użytkowniku; po uśpieniu jeden przebieg nadrabiający | to samo (LaunchAgent działa po zalogowaniu) | to samo; linger, gdy ma działać bez logowania | skrypty rutyn biorą ścieżki z HERMES_HOME zamiast /opt; włączamy je po próbnej wiadomości na Telegram |
| **H07** Kanban: dyspozytor i pracownicy | dyspozytor w bramie; pracownik = podproces `-p <agent> --cli chat -q "work kanban task <id>"` | CREATE_NO_WINDOW jest w kodzie Hermesa; nadzorca bez Job Object z KILL_ON_JOB_CLOSE, bez `taskkill /T`, dzieci startują z BREAKAWAY | osobny PGID, pracownik przeżywa restart bramy (niesprawdzone na żywo) | wymaga user bus i `systemd-run --user --scope` (Hermes robi to sam) | max_in_progress liczony z RAM komputera; test: karta przeżywa restart bramy |
| **H08** Delegacja (delegate_task) | wątki w procesie agenta | bez zmian | bez zmian | bez zmian | bez człowieka prośby o zgodę kończą się odmową (sekcja d) |
| **H09** Dashboard 24/7 | usługa s6 na 0.0.0.0:9119, web_dist łatany w obrazie | nadzorca uruchamia `dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build` z `HERMES_WEB_DIST`; sam Hermes nie ma autostartu dashboardu | to samo | to samo | w procesie dashboardu działa silnik rozmów HQ, podgląd :9120 i rendery, więc bez niego nie ma aplikacji |
| **H10** Logowanie do panelu | basic auth (bind 0.0.0.0) + klucz jednorazowy przez łatkę dostawcy basic | loopback: bez hasła, token sesji w index.html; tryb LAN/telefon: własny dostawca hasła Jarva przez `register_dashboard_auth_provider` | to samo | to samo; VPS: bind na IP Tailscale z bramką | ryzyko: token przeczyta każdy lokalny proces, a CORS wpuszcza `localhost:*` (h) |
| **H11** Telegram | adapter w bramie; token z secrets/host.env, trasy z compose/jarvo.env | ten sam adapter; token i allowlista przez kreator QR Hermesa albo formularz HQ do `<dane>\.env`; trasy z pliku Jarva | to samo | to samo | na jednym tokenie słucha jedna instancja: przed startem wyłączyć starą flotę, inaczej błąd 409 |
| **H12** Jedna brama i jeden dashboard na użytkownika | osobny system plików kontenera | `HERMES_GATEWAY_LOCK_DIR=<stan>\gateway-locks` w środowisku procesów Jarva | to samo | to samo | bez tego Jarvo dołączy do prywatnego Hermesa albo wpadnie w pętlę kodu 75 |
| **H13** Polecenie hermes, PATH, HERMES_HOME | PATH=/opt/hermes/bin, HERMES_HOME=/opt/data | jarvo woła `<venv>\Scripts\python.exe -m hermes_cli.main` i ustawia HERMES_HOME oraz HERMES_GIT_BASH_PATH tylko w swoim procesie | to samo (`venv/bin/python`) | to samo | żadnych zmiennych użytkownika; `hermes uninstall` kasuje je bez sprawdzania wartości |
| **H14** Profile (`hermes -p`) | /opt/data/profiles/`<agent>` | `<dane>\profiles\<agent>`; bez `--alias`, bo alias zasłania polecenie jarvo | to samo | to samo | nazwy i układ jak dziś |
| **H15** Mózg: ChatGPT kodem urządzenia albo klucz API | trasy OAuth dashboardu, auth.json w /opt/data, mozg.py w HQ | to samo natywnie (czysty HTTP); `auth.adopt_external_logins: false` | to samo | to samo | jedno logowanie w korzeniu wystarcza całej flocie; przy migracji stare auth.json trzeba unieszkodliwić (f) |
| **H16** Aktualizacja Hermesa | podbicie `ARG HERMES_IMAGE` | nigdy `hermes update` (ciągnie main); `jarvo update` robi checkout nowego commitu w nowym katalogu i `uv sync --locked`; przycisk „Update now” ukryty w powłoce | to samo | to samo | doctor porównuje commit z pinem |
| **H17** TUI, PTY, zakładka /chat | ptyprocess w kontenerze | klasyczny CLI działa; most ConPTY dla /chat jest w kodzie (pywinpty 2.0.15, tylko win_amd64), a dokumentacja Hermesa mówi, że nie działa (niesprawdzone); na arm64 brak | ptyprocess | ptyprocess | HQ ma własny czat, więc /chat niczego nie blokuje |
| **H18** Narzędzie terminal | bash z Debiana w kontenerze | Git Bash (`bash.exe -c`) z PortableGit Jarva, MSYS_NO_PATHCONV=1; bash.exe z System32 (WSL) jest pomijany | bash z PATH (zwykle 3.2), procesy w tle przez zsh | bash 5 | skille muszą działać w Git Bash i w bash 3.2 (sekcja e) |
| **H19** Zgody: trzy tryby jak w Claude Code | `approvals.mode: smart`, odmowa dla cron, -q i pracy bez człowieka | wtyczka Jarva z hakiem `pre_tool_call` (sekcja d) | to samo | to samo | `mode: off` dalej zakazany w validate.py |
| **H20** Ochrona zapisu plików | `HERMES_WRITE_SAFE_ROOT=/opt/data` | `<dane>` (+ folder projektu w trybie „projekt”), separator `;` | separator `:` | separator `:` | to blokada, nie pytanie; nie chroni przed terminalem |
| **H21** Odinstalowanie Hermesa | brak | nie używamy `hermes uninstall` (kasuje cudze zmienne); własna procedura N11 | to samo | to samo | |
| **H22** Nadzór i autostart | s6 jako PID 1, `restart: unless-stopped`, pomocnik jarvo-updater (systemd --user albo LaunchAgent), na Windows Jarvo.vbs budzi WSL | `jarvo serwis` z zadania Harmonogramu (XML, szczegóły w c2); zapas: HKCU Run | LaunchAgent `pl.jarvo.nadzorca` | `jarvo.service` w systemd --user; VPS: jednostka systemowa | jeden nadzorca, jeden kod na 3 systemy |
| **H23** tirith (skaner poleceń Hermesa) | Hermes pobiera „latest” bez pinu do bin/ każdego profilu (u właściciela 38 MB × 10 profili) | wyłączyć: `security.tirith_enabled: false`; na Windows Hermes i tak go pomija, a Defender oznaczył zip v0.4.2 jako trojan | wyłączyć | wyłączyć | Hermes 0.22 usunął tirith; wyłączyć też w kontenerze (etap E0) |
| **H24** HOME agentów | HOME=/opt/data (konto hermes w kontenerze) | `terminal.home_mode: profile` (katalog `<profil>\home` zakłada instalator) + `shell_init_files` z USERPROFILE, APPDATA, LOCALAPPDATA, XDG_CONFIG_HOME oraz GH_CONFIG_DIR, CODEX_HOME, NPM_CONFIG_USERCONFIG | `home_mode: profile`, `auto_source_bashrc: false` | to samo | bez tego agent widzi ~/.ssh i ~/.codex/auth.json właściciela; na Windows `profile` izoluje tylko git i ssh z Git Bash |
| **H25** Kwarantanna paczek instalowanych przez agentów | projektowy .npmrc Hermesa (min-release-age=14), uv exclude-newer | `npm_config_min_release_age=14` i `UV_EXCLUDE_NEWER` w środowisku usług Jarva (npm co najmniej 11.17) | to samo | to samo | nie w .env profilu i nie w npmrc zarządzanego Node, bo trafiłoby do npm właściciela; czy UV_EXCLUDE_NEWER przyjmuje „14 days”, niesprawdzone |
| **H26** Kontener jarvo-hermes | compose: porty 9119/9120/9122 na 127.0.0.1, montowania /opt/data i /opt/jarvo/{repo,build,secrets}, limit 5 GB i 4 CPU, bez healthchecka | procesy H04 i H09 pod nadzorcą, porty na 127.0.0.1 | to samo | to samo | sufitu pamięci natywnie nie ma (S03) |
| **H27** Wtyczki Jarva w Hermesie | kopia do /opt/data/plugins i `ln -sfn` do profili | kopia (albo junction, bez admina) do `<dane>\plugins` i do każdego profilu, wpis w plugins.enabled | symlink | symlink | czy dostawca pamięci działa z junction: niesprawdzone |

### Toolchain bazowy

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **B01** Python | Hermes: python3 3.13 z Debiana + SQLite 3.53.4; venvy Jarva: PBS 3.12.13 przez uv 0.11.6 (SQLite 3.50.4) | python-build-standalone 20261021 przez uv: 3.13.17 dla Hermesa, wtyczek i ManimGX; 3.12.15 dla narzędzi, OCR, CAD i SEO (misaki wymaga <3.13); x64 `56cde3b1` | arm64 `8dc60610`, x64 `ce9c748c` | x64 `f829adc9`, arm64 `c6857c65` | lista pobrań z sumami przez UV_PYTHON_DOWNLOADS_JSON_URL; Windows arm64: Python x64 (tylko Windows 11), bo cryptography 50 nie ma koła win_arm64 |
| **B02** uv | 0.11.6 z obrazu Hermesa | 0.12.13 (tej wersji używa tests.yml Hermesa przy v2026.9.24; reszta jego workflowów ma 0.9.28), zip z .sha256 (x64 `a86c9dc7`); kopia też w `<dane>\bin` i w bin/ profili | arm64 `7e6ddb93`, x64 `5e287ef6` | x64 `745765a3`, arm64 `2eaa5d94` | sync Hermesa bez UV_NO_CONFIG; bez naszej kopii Hermes ściąga najnowszy uv bez sumy |
| **B03** Node.js i npm | Node 26 z obrazu Hermesa (26.5.1) | Node 26.x z SHASUMS256.txt (dziś 26.12.1, do przeglądu) w `<program>\node\<wersja>`, tylko w PATH procesów Jarva | darwin-arm64 i darwin-x64 | linux-x64 i linux-arm64 (glibc 2.28+) | npm co najmniej 11.17; Hermes odrzuca npm 11.10–11.16; którą wersję npm ma Node 26.12.1, niesprawdzone |
| **B04** git i Git Bash | git 2.47 z apt | PortableGit 2.54.0.windows.1 (x64 `bea006a6`, arm64 `f8e92cd3`) albo pełny tar.bz2 rozpakowany tar.exe (bez uruchamiania SFX; suma tar.bz2 niesprawdzona); HERMES_GIT_BASH_PATH tylko w procesie | git z Xcode CLT (systemowe okno, może prosić o hasło admina, niesprawdzone) albo conda-forge git 2.56.0 przez pixi; bash 5.2.37 z conda-forge | git z systemu; gdy brak, conda-forge git | potrzebny do checkoutu Hermesa, build.py (34 repo skilli) i gita skarbca |
| **B05** ripgrep | apt 14.1.1 | 15.2.0 msvc zip (`71b2fef8`) | arm64 `3750b2e9`, x64 `af7825fc` | x64 musl `33e15bcf`, arm64 `a740b91c` | gdy rg jest na PATH, instalator Hermesa nie idzie do winget |
| **B06** SQLite w Pythonie (błąd WAL-reset) | Hermes 3.53.4 (naprawione); venvy Jarva 3.50.4 (podatne) | PBS 20261021 ma 3.53.1 (naprawione od 3.51.3); Python z python.org 3.11–3.14 odpada (3.45–3.50.4) | to samo | to samo; Python systemowy (Debian 3.46.1) odpada | bramka w instalatorze i doctor (funkcja Hermesa sqlite_runtime); rozmowy.db i nawyki.db przechodzą w WAL tylko za bramką |
| **B07** sqlite3 CLI | apt 3.46.1 (podatne) | nie dostarczamy; backup.sh i restore-test.sh przechodzą na `sqlite3.Connection.backup()` w Pythonie | to samo | to samo | |
| **B08** jq | apt 1.7.1 | opcjonalnie jq 1.8.2 (sha256sum.txt) jako wygoda agentów | macos-arm64, macos-amd64 | linux-amd64, linux-arm64 | kod floty go nie używa |
| **B09** Reszta bazy obrazu Hermesa | s6-overlay 3.2.3.0, docker-cli, gcc, g++, make, cmake, python3-dev, libffi, libolm, procps, openssh-client, iputils, xz-utils, curl | niepotrzebne (same koła binarne); curl.exe i tar.exe są w Windows od 1803 | kompilacja tylko w CI (koło cryptography na Intela) | to samo; xz do Node .tar.xz albo bierzemy .tar.gz | ssh do gita: systemowy, opcjonalny |
| **B10** Pakiety apt Jarva | 17 paczek apt bez pinu i bez sumy (pandoc, qpdf, ocrmypdf, tesseract, exiftool, jq, sqlite3, adb, GTK3, dbus-x11, fonty; LibreOffice z dodatkiem office) | każda jako wpis manifestu (wiersze E, M03, B07, B08) | to samo | to samo | koniec z „wersją z dnia budowy” |
| **B11** Runtime VC++ (Windows) | nie dotyczy | onnxruntime, espeak-ng, spaCy, thinc i preshed importują MSVCP140*, a nie ma ich ani na czystym Windows, ani w PBS; kopiujemy DLL z conda-forge vc14_runtime 14.51.36247 (`4e4cb599`) obok bazowego python.exe; awaryjnie VC_redist z UAC | nie dotyczy | nie dotyczy | runnery GitHub mają VC++, więc CI tego nie pokaże: potrzebny test „zamknięcia DLL”; licencja redystrybucji do decyzji (I25) |
| **B12** Smart App Control i podpisy | nie dotyczy | niepodpisane są: python.exe z PBS, trampoliny uv, cv2.pyd, ffmpeg z BtbN; przy SAC włączonym są blokowane; na razie doctor wykrywa SAC i mówi wprost, co nie zadziała; później podpisywanie (I26) | pliki z curl i urllib nie dostają kwarantanny; binarki arm64 muszą mieć co najmniej podpis ad-hoc | nie dotyczy | Hermes ma ten sam problem (Hermes Desktop #536) |
| **B13** Ścieżki z polskimi znakami | konto hermes w kontenerze, ścieżki ASCII | `<program>` zawsze ASCII (krótka nazwa 8.3 albo `C:\ProgramData\Jarvo\<SID>`); Indra czyta plik przez np.fromfile + cv2.imdecode; Tesseract dostaje obraz przez stdin; dane espeak w ścieżce ASCII | NFC w nazwach skarbca | bez zmian | espeak-ng przy ścieżce nie-ASCII kończy proces exit(1); OpenCV imread nie otworzy „faktura_październik.png” |

### Przeglądarki

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **C01** Chromium do skryptów (chrome-headless-shell) | rewizja Playwrighta 1243 = Chrome for Testing 153.0.8010.12 z obrazu Hermesa; dowiązanie /usr/local/bin/chromium | CfT 153.0.8010.12 `chrome-headless-shell-win64.zip` (120 MB) w układzie `PLAYWRIGHT_BROWSERS_PATH\chromium_headless_shell-1243\...` z plikiem INSTALLATION_COMPLETE; win-arm64 nie istnieje, więc x64 | mac-arm64 (99 MB) i mac-x64 (104 MB); Playwright 1.63 wymaga macOS 14+ | linux64 i linux-arm64 (build Playwrighta); biblioteki systemu (libnss3, libgbm1…) wymagają sudo raz | Google nie publikuje sha256: liczymy ją przy przeglądzie (md5 z x-goog-hash do kontroli); CHROME_PATH, PUPPETEER_EXECUTABLE_PATH, HYPERFRAMES_BROWSER_PATH, PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1, PUPPETEER_SKIP_DOWNLOAD=1 |
| **C02** ffmpeg Playwrighta (nagrywanie stron) | z obrazu Hermesa | `cdn.playwright.dev/builds/ffmpeg/1011/ffmpeg-win64.zip`, sumę liczymy | ffmpeg-mac-arm64.zip, ffmpeg-mac.zip | ffmpeg-linux.zip, ffmpeg-linux-arm64.zip | używa go demo_strony.py; licencja niesprawdzona |
| **C03** Playwright (Python, Node) i puppeteer | playwright 1.63.0 (venv narzędzi), 1.62.0 (dla Camoufoxa), playwright-core 1.63.0 (Node), puppeteer 24.43.1 (narzedzia.py) | koła win_amd64 i win_arm64 instalowane z `--require-hashes`; npm z lockiem | koła macOS arm64 i x86_64 | koła manylinux x86_64 i aarch64 | trzy kopie muszą trafiać w jedną rewizję przeglądarki; test z Dockerfile:105-109 przenosimy do doctor |
| **C04** Lightpanda 1.0.0 | binarka skopiowana z obrazu lightpanda/browser:1.0.0, strip do 74 MB | brak wydania na Windows (są tylko Linux i macOS), więc silnik `chrome` (C06) | `lightpanda-aarch64-macos` (`95544005`), `lightpanda-x86_64-macos` (`e5102996`) | `lightpanda-x86_64-linux` (`aa5a4b8e`), `lightpanda-aarch64-linux` (`69791924`) | AGPL-3.0; plik z wydania to inny artefakt niż w obrazie (przegląd); telemetria wyłączona zmiennymi LIGHTPANDA_DISABLE_*; 1.0.2 ma osobne pliki .debug |
| **C05** agent-browser 0.38.1 i nakładka Jarva | z paczki npm zostaje binarka linux; nakładka bash wysyła `stream disable` | `agent-browser-win32-x64.exe` z paczki (integrity npm); nakładka przepisana na Pythona jako `agent-browser.exe`, pierwsza w PATH | `agent-browser-darwin-arm64` i `-darwin-x64` | `linux-x64` i `linux-arm64` | bez nakładki demon otwiera serwer podglądu bez hasła; win32-arm64 nie istnieje (emulacja niesprawdzona); paczkę instalujemy z `--ignore-scripts` |
| **C06** browser.engine w profilach | `lightpanda` w 9 plikach config.yaml | build.py wpisuje `chrome` i ustawia AGENT_BROWSER_EXECUTABLE_PATH na CfT z C01 | `lightpanda` | `lightpanda` | Hermes przyjmuje auto, lightpanda, chrome; Chromium bierze ok. 300 MB RAM na sesję zamiast 25–30 MB |
| **C07** Camoufox 152.0.4-beta.30 | zip lin.x86_64/lin.arm64 z sumą, bez fontów macOS i Windows; GTK3 i dbus-x11 z apt | `win.x86_64.zip` (`ea52a02f`, ok. 0,5 GB) pobierany przy pierwszym użyciu; bez fontów Apple (636 MB); `os=` = Windows | `mac.arm64.zip` (`3b43e766`), `mac.x86_64.zip` (`f12f90a3`); bez fontów Microsoft; Gatekeeper i podpis niesprawdzone | lin.* jak dziś; na serwerze bez pulpitu libgtk-3 wymaga sudo | MPL-2.0; ostrozna.py: `import fcntl` na górze pliku trzeba zastąpić przenośną blokadą, dopisać SYSTEMROOT/TEMP/APPDATA do białej listy zmiennych |

### Media i wideo

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **M01** FFmpeg i ffprobe | apt Debiana 7.1.5 z libass, fontconfig, zimg (zscale), vidstab, librsvg, x264, vpx, opus, svt-av1 | BtbN wariant gpl z buildu z końca miesiąca (np. `autobuild-2026-09-30-13-08`, n9.0.2 win64 `a0e45723`), checksums.sha256; jest też winarm64 | Martin Riedl 9.0.2 arm64 i amd64 (plik .sha256, podpis i notaryzacja); brak vidstab (montaz.py przejdzie na deshake) i librsvg | BtbN linux64 i linuxarm64 (statyczne, glibc 2.28+) | conda-forge ffmpeg odpada (bez zimg, a na Windows bez libass i libvpx); skok 7.1 → 9.0 wymaga testu filtrów; fonts.conf + fontsdir (M03); Intel: Riedl wydaje buildy do I 2027, zapas evermeet; licencja GPL |
| **M02** HyperFrames 0.8.78 | `npm install -g` bez locka | w package-lock infra/node, `npm ci --ignore-scripts`; HYPERFRAMES_FFMPEG_PATH, _FFPROBE_PATH, _BROWSER_PATH na narzędzia Jarva; wołamy z node_modules/.bin, nie przez npx | to samo (esbuild i sharp mają darwin) | to samo | render na Windows i macOS niesprawdzony; `npx hyperframes` bez lokalnej kopii ściąga najnowszą wersję |
| **M03** Fonty | apt: DejaVu, Noto, Noto Color Emoji, Inter; ścieżki /usr/share/fonts na sztywno w wideo_lib.py:290, krytyka.py:345, dwa_ekrany.py:80 | pliki TTF w paczce Jarva (Inter 4.1, DejaVu 2.37, Noto Sans 2.015, Noto Color Emoji 2.051) + fonts.conf przez FONTCONFIG_FILE; ffmpeg zawsze z fontsdir albo fontfile; bez instalacji w systemie | to samo | to samo | drawtext na Windows bez fonts.conf nie znajduje kroju; sumy liczymy sami (stare wydania nie mają digestów); filmy mogą wyglądać trochę inaczej niż w kontenerze |
| **M04** ManimGX 0.1.1 (dodatek manim) | venv na Pythonie 3.13 (lock z sumami), nakładka sh, cache w /opt/data | koło cp313-abi3 win_amd64 (suma jest w locku); `Scripts\manimgx.exe` + MANIMGX_CACHE_DIR; render przez GPU niesprawdzony | koła macosx_11_0 arm64 i x86_64; render przez Metal niesprawdzony | manylinux z lavapipe (render na CPU) | koła Windows i macOS to inne binarki niż przejrzane koło linuksowe: nowy przegląd licencji |
| **M05** mgaudio i muzyka.py | venv w /opt/data/jarvo/narzedzia, paczki bez sum, `os.execv` | koła numba 0.66.0 i pedalboard 0.9.25 dla win_amd64 (arm64 brak, więc Python x64); sumy w locku; execv → subprocess | arm64: jak dziś; Intel: numba 0.62.1 + llvmlite 0.45.1 + numpy <2.4 | bez zmian | pedalboard GPL-3.0 |
| **M06** narzedzia.py (wideo z kodu: lemo-opuscar, shotcraft, mg-styles-15, huashu, lottie, remotion, anidoodle, animacja) | klony git, npm i venvy w /opt/data/jarvo/narzedzia; symlinki, `sh`, `eval "$(... env ...)"` | resolver programów (.cmd), Scripts\python.exe, junction albo NODE_PATH zamiast symlinków, cksum w Pythonie, polecenie `narzedzia.py uruchom X -- ...` zamiast eval; fetch.sh z lemo przez Git Bash (niesprawdzone) | to samo bez .cmd; skrypty lemo w bash 3.2 niesprawdzone | ścieżki | node_modules z długimi ścieżkami: git `core.longpaths=true`; po migracji katalog budujemy od nowa (pliki z kontenera są linuksowe) |
| **M07** lemo-wake (Studio) | lemo_wake.py: venv, paczki bez sum, modele ok. 600 MB po zgodzie | sumy paczek, onnxruntime ujednolicony do 1.31.0, PLAYWRIGHT_BROWSERS_PATH z manifestu, `uruchom` zamiast eval | arm64: tak; Intel: brak onnxruntime, więc nie | bez zmian | licencja CC BY-NC 4.0; sumy modeli niesprawdzone |
| **M08** Dodatki JARVO_EXTRAS: rembg, media (auto-editor), docling, office | argumenty budowy obrazu; rembg 2.0.84, auto-editor 29.3.1, docling 2.126.0 bez sum | `jarvo narzedzia dodaj <nazwa>` w trakcie pracy, z paskiem postępu; auto-editor z binarki wydania (`windows-amd64.exe`, sha256), nie ze stuba z PyPI (pobiera bez sumy) | auto-editor macos-arm64 i macos-x86_64; docling na Intelu niemożliwy (torch 2.2.2, docling-parse) | auto-editor tylko x86_64 (na arm64 dodatek media wyłączony) | docling z modelami to 1–2 GB; office = E07 |
| **M09** Natywne paczki npm (sharp, @napi-rs/canvas, esbuild, kompozytor remotion) | sharp 0.35.4 w infra/node; reszta z narzedzia.py bez locka | prebuildy `@img/sharp-win32-x64`, `@napi-rs/canvas-win32-x64-msvc` (bez arm64), `@esbuild/win32-x64`, `@remotion/compositor-win32-x64-msvc` | darwin-arm64 i darwin-x64 | linux-x64 i linux-arm64 (gnu i musl) | lock musi mieć wpisy opcjonalne wszystkich platform; licencję Remotion (warunki komercyjne) trzeba sprawdzić |
| **M10** Edytor filmów HQ i eksport | `asyncio.create_subprocess_exec` w procesie dashboardu; ffmpeg z PATH; jarvo-stt w /opt/jarvo/bin | dashboard Hermesa na Windows działa na SelectorEventLoop, więc podprocesy asyncio rzucają NotImplementedError (sprawdzone); przejście na subprocess w wątkach (proc.py), CREATE_NO_WINDOW, Job Object dla dzieci ffmpeg; ffmpeg z manifestu; apostrof w listach ffconcat | działa po zmianie ścieżek | to samo | na Windows blokada pliku (WinError 32) przy podglądzie i nadpisywaniu wyniku |
| **M11** Wideograf: rdzeń renderu (wideo_lib, html_wideo, film, projekt) | wideo_lib.miejsce_renderu: fcntl i os.getuid; pamięć z /proc i cgroup; Lottie przez symlinki; ścieżki /opt | przenośna blokada, getpass.getuser(), psutil zamiast /proc, aliasy serwera HTTP zamiast symlinków, fontfile/fontsdir, ścieżki z warstwy ścieżek | psutil (bez /proc limit liczyłby zawsze 8 GB) | bez zmian po zmianie ścieżek | dziś każdy pełny render na Windows pada, zanim ruszy |
| **M12** Wideograf: pozostałe 20 skryptów | ffmpeg, Playwright, numpy, Pillow; drawtext bez fontfile; os.execv w qa_wideo, muzyka i typografia | większość zadziała po M01, M03 i M11; drawtext z fontfile (dwukropek po literze dysku zabezpieczony: `C\:/...`); execv → subprocess; maska i twarze z JARVO_MODELS_DIR | Intel: maska, twarze i muzyka bez kół | bez zmian | tabela zgodności w raporcie flota-2 |

### Dokumenty, OCR, 3D i inne narzędzia

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **E01** pandoc | apt 3.1.11 | 3.12.1 `windows-x86_64.zip` (`6ef431cb`); arm64 przez emulację x64 (niesprawdzone) | `arm64-macOS.zip` (`c2146cf3`), `x86_64-macOS.zip` (`81ed3e2c`) | `linux-amd64` (`d0c90410`), `linux-arm64` (`445d96fd`) | skok 3.1 → 3.12: przejść test_konwertuj i filtry Lua |
| **E02** qpdf | apt 12.2.0 | 12.4.2 `msvc64.zip` i `msvc-arm64.zip`, plik .sha256 podpisany sigstore | `bin-macos-arm64`, `bin-macos-x86_64` | `bin-linux-x86_64`, `bin-linux-aarch64` | niskie ryzyko |
| **E03** ExifTool | apt 13.25 (Perl) | `exiftool-13.59_64.zip` z wbudowanym Perlem (SHA-256 z checksums.txt); adres z SourceForge, bo exiftool.org trzyma tylko bieżącą wersję | conda-forge exiftool 13.59 z Perlem przez pixi; czy /usr/bin/perl jest w macOS 26, niesprawdzone | tar.gz + Perl z systemu albo conda-forge | |
| **E04** Ghostscript | zależność ocrmypdf w apt (10.05) | zastąpić w konwertuj.py i ocr.py przez pypdfium2 + pikepdf; zapas: conda-forge ghostscript 10.08.0 (daje gs.exe) | brak oficjalnej binarki: pypdfium2 albo conda-forge | to samo | AGPL-3.0; kod woła `gs`, a oficjalny instalator Windows daje gswin64c.exe |
| **E05** Tesseract z pol, eng, osd | apt 5.5.0 + tessdata_fast 4.1.0 | conda-forge tesseract 5.5.3 przez pixi (bez admina); oficjalny instalator NSIS 5.5.3 wymaga UAC | conda-forge osx-arm64 i osx-64 | conda-forge linux-64 i linux-aarch64 (albo pakiet systemu) | paczka ma wszystkie języki (180 MB), przycinamy do pol, eng, osd; Tesseract ma wąskie API ścieżek, więc obraz idzie przez stdin |
| **E06** OCRmyPDF | apt 16.7.0 | PyPI 17.13.0 w venvie narzędzi (pikepdf 10.17 ma win_amd64 i win_arm64) | arm64: tak; Intel: 17.12.1 + pikepdf 10.13.0.post1, tylko macOS 15 | PyPI | potrzebuje Tesseracta (E05); Ghostscript jest opcjonalny |
| **E07** LibreOffice (dodatek office) | apt 25.2.3 przy JARVO_EXTRAS=office | najpierw wykryć instalację właściciela; jeśli brak, MSI 26.8.1 przez `msiexec /a` do katalogu Jarva (bez admina niesprawdzone) | dmg 26.8.1, kopia LibreOffice.app do katalogu Jarva | `deb.tar.gz` rozpakowany bez dpkg i sudo | ok. 0,35 GB; stare wersje są tylko w downloadarchive.documentfoundation.org |
| **E08** ImageMagick | nie ma w obrazie, kod go nie używa | nie dostarczamy | nie dostarczamy | nie dostarczamy | |
| **E09** Konwerter plików (konwertuj.py, Centrala → Konwerter) | shutil.which: chromium, soffice, gs, qpdf, pandoc, exiftool, ffmpeg; `text=True` bez kodowania | resolver z manifestu (CHROME_PATH, soffice.exe, ścieżki narzędzi), `encoding="utf-8"`, CREATE_NO_WINDOW | ścieżka /Applications/LibreOffice.app niesprawdzona; SVG → PNG przez Chromium (Riedl bez librsvg) | PATH jak dziś | moduł działa też w procesie dashboardu |
| **E10** OCR odczyt-ekranu (Indra + Tesseract) | venv OCR 3.12 z sumami (indra-ocr 0.3.2, ORT 1.31.0, opencv 5.0.0.93, pypdfium2 5.14.0), modele z sumami, `os.execv` | lock jest uniwersalny (sumy win_amd64 już są); JARVO_OCR_PYTHON = `Scripts\python.exe`; execv → subprocess; np.fromfile + imdecode przy polskich nazwach; win_arm64: brak opencv, więc Python x64 | arm64: macOS 14+; Intel: ORT 1.23.2 i opencv 4.12, albo tylko Tesseract | bez zmian | strony PDF dla Tesseracta przez pypdfium2 zamiast gs |
| **E11** Warsztat 3D (build123d 0.13.0) | venv CAD 3.12, lock z sumami, podgląd przez three w Chromium | koła cadquery-ocp-novtk win_amd64 (sumy są w locku); JARVO_CAD_PYTHON, NODE_PATH, CHROME_PATH | arm64 i x86_64 | x86_64 i aarch64 | ładowanie DLL OCP na Windows niesprawdzone; win_arm64 brak |
| **E12** claude-seo | commit e77e783e, venv z zakresami bez sum, WeasyPrint (Pango przypadkiem z GTK3), launcher w bashu | lock z sumami; PDF przez Chromium zamiast WeasyPrint (rekomendacja) albo Pango z conda-forge; skille wołają runtime.py przez CLAUDE_SEO_PYTHON | Intel: ograniczenie cryptography ≥50, bo resolver cofa się do 48.0.1 | Pango z systemu | runtime.py umie sam zrobić `playwright install`: zablokować; najdłuższa ścieżka w kole google-ads ma 124 znaki |
| **E13** adb (Android platform-tools) | apt 34.0.5; łączy się z jarvo-android:5555 | platform-tools r37.0.1 dla Windows od Google; repozytorium podaje tylko SHA-1, sha256 liczymy | darwin | linux tylko x86_64; na arm64 pakiet systemu | pobieramy od Google (licencja SDK), nie z lustra |

### Głos i modele

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **V01** Lektor jarvo-tts (Matcha PL męski i damski, Paradee EN) | skrypt z shebangiem /opt/jarvo/venv, ORT 1.29.0, misaki 0.9.4, spaCy 3.8.16, espeakng-loader; używa go TTS Hermesa, Wideograf i głos w HQ | console-script `jarvo-tts.exe` w venvie 3.12; runtime VC++ (B11); dane espeak w ścieżce ASCII (B13); wyjście UTF-8 | arm64: macOS 14+; Intel: ORT 1.23.2 (formaty modeli zgodne według nagłówków, działanie niesprawdzone) | bez zmian | zapasem jest głos przeglądarki (już jest w HQ) |
| **V02** Model Matcha-TTS-PL (męski, damski) | adres `machinekind/Matcha-TTS-PL-v2/resolve/93744740...` zwraca 404 od 2026-10-23 | `huggingface.co/machinekind/Matcha-TTS-PL/resolve/93744740...` (ta sama rewizja i sumy `e2a2ea8b`, `1e228163`) | to samo | to samo | naprawić od razu, także w obrazie (E0); nowe repo „-v2” z innymi głosami to osobne źródło; CC BY-SA 4.0 pozwala na lustro |
| **V03** Paradee-8M v1.0 i spaCy en_core_web_sm 3.8.0 | HF `@v1.0` (tag), koło spaCy z GitHuba z sumą | przypiąć commit `8f34b01e...` zamiast tagu; pliki te same na każdym systemie | to samo | to samo | tag da się przesunąć |
| **V04** espeak-ng | koło espeakng-loader 0.2.4 w venvie narzędzi | koła win_amd64 i win_arm64 | macosx arm64 i x86_64 | manylinux x86_64 i aarch64 | espeak-ng to GPL-3.0; przy ścieżce nie-ASCII kończy proces exit(1) |
| **V05** STT jarvo-stt + Parakeet i Silero | fcntl, /tmp; model z HF bez rewizji i bez sumy przy pierwszym użyciu | przenośna blokada, tempfile; Parakeet `@8f23f0c0` (encoder `6139d2fa`, decoder `eea7483e`, nemo128 `a9fde148`) i Silero `@b3e3ee3c` (`1a153a22`) pobierane z sumą i ładowane z dysku | Intel: ORT 1.23.2 | bez zmian | 0,67 GB, więc przy pierwszym użyciu z paskiem; przy migracji kopia z kontenera sprawdzona sumą |
| **V06** Edge TTS (zapasowy lektor) | leniwa instalacja Hermesa do /opt/data/lazy-packages | edge-tts 7.2.7 z hashem w venvie narzędzi | to samo | to samo | nieoficjalne API Microsoftu, wymaga sieci |
| **V07** Modele Indra OCR | 15 plików z HF `@ed345c7f` z sumami w obrazie | te same pliki i sumy w `<dane>\jarvo\models\indra-ocr` | to samo | to samo | licencja zmodyfikowana OpenRAIL-M |
| **V08** Inne modele (MODNet, YuNet, rembg u2net, docling, lemo-wake) | MODNet i YuNet z sumą przy pierwszym użyciu; reszta bez pinu | JARVO_MODELS_DIR w `<dane>`; dodatki: przypiąć rewizje albo opisać jako nieprzypięte | to samo | to samo | |
| **V09** onnxruntime i inne koła z kodem natywnym | ORT 1.29.0 (narzędzia), 1.31.0 (OCR), 1.30.0 (lemo) | ujednolicić na 1.31.0; koła win_amd64 i win_arm64 | arm64 macOS 14+; Intel 1.23.2 przez marker platformy | manylinux_2_28 | ORT od 1.24 nie ma kół macOS x86_64 |
| **V10** Modele: jeden wpis manifestu | sumy w Dockerfile | jeden wpis na plik (adres `/resolve/<commit>/`, sha256, rozmiar), wspólny dla wszystkich systemów | to samo | to samo | małe pliki spoza LFS (config.json, vocab.txt) nie mają sumy w API, liczymy sami |
| **V11** STT i TTS wołane przez bramę | `HERMES_LOCAL_STT_COMMAND=/opt/jarvo/bin/jarvo-stt ...`, `tts.providers.matcha.command` | build.py wpisuje pełną ścieżkę `.exe`, z „/” i w cudzysłowie (Hermes dzieli polecenie przez shlex.split w trybie POSIX) | ścieżki Jarva | to samo | bez tego głosówki z Telegrama znikają bez śladu |

### Paczki i locki

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **P01** venv narzędzi (requirements-tools.txt) | 11 pinów, ok. 115 paczek po rozwiązaniu, bez locka i bez sum; uv czyta [tool.uv] Hermesa (exclude-newer) | lock `uv pip compile --universal --generate-hashes`, instalacja `--no-config --require-hashes --only-binary :all: --no-deps` (bez docopt, który ma tylko sdist) | to samo + marker dla darwin/x86_64 | to samo | w środku: trafilatura, yt-dlp, onnx-asr, onnxruntime, misaki, spaCy, espeakng-loader, camoufox, playwright 1.62, num2words, edge-tts, ddgs (jeśli U01) |
| **P02** Narzędzia npm (infra/node) | package.json bez locka: agent-browser, axe-core, dembrandt, favicons, html-validate, inspo-mcp, lighthouse, linkinator, playwright-core, sharp, svgo, three | package-lock.json w repo (próbny lock: 320 paczek z integrity), `npm ci --ignore-scripts`, onnxruntime-node usuwany po instalacji; pliki .bin to .cmd | to samo | to samo | NODE_PATH w środowisku usług (separator `;` na Windows); lighthouse ma pin 13.4.1, a toolbox podaje 13.5.0 |
| **P03** Locki per platforma | 3 locki z sumami (OCR, CAD, ManimGX), reszta bez | check-pins.py sprawdza koło i sumę dla win_amd64, macOS arm64 (MACOSX_DEPLOYMENT_TARGET=14.0), manylinux x86_64 i aarch64 oraz manifest | to samo | to samo | |
| **P04** Paczki per projekt (astro, expo-doctor, eas-cli) | `npm create astro@latest`, `npx --yes expo-doctor@1.21.1`, `eas-cli@24.7.0` | przypiąć create-astro; wołać przez resolver (`npx.cmd`) | to samo | to samo | `@latest` bez locka do usunięcia |
| **P05** npm Hermesa (ui-tui, web) | w obrazie | web: gotowy dist z CI (S12); ui-tui tylko gdy potrzebny `hermes --tui` (`npm ci --workspace ui-tui`) | to samo | to samo | install.ps1 Hermesa instaluje też Electron z apps/desktop: pomijamy |
| **P06** Serwer MCP inspo (jarvo-web) | `/opt/jarvo/node/node_modules/.bin/inspo-mcp`, NODE_EXTRA_CA_CERTS z Debiana | `node <node_modules>/inspo-mcp/inspo-mcp.mjs --stdio`; NODE_USE_SYSTEM_CA=1 (z Hermesem niesprawdzone) | to samo | to samo | katalog stron z CDN autorów nie ma sumy |

### Usługi z docker-compose

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **U01** SearXNG (wyszukiwarka floty) | kontener; `web.search_backend: searxng` w 10 profilach; search_fanout.py Sherlocka | SearXNG natywnie nie ruszy (import pwd); wtyczka Hermesa ddgs z ddgs 9.16.1 i primp 2.0.1 przypiętymi sumą; skill duckduckgo-search zamiast searxng-search | ddgs | ddgs; SearXNG zostaje tylko na VPS | inne wyniki; ryzyko CAPTCHA i regulaminów wyszukiwarek; alternatywa openai-native przy mózgu ChatGPT (I14) |
| **U02** Valkey | kontener dla SearXNG; limiter wyłączony, więc nikt go nie używa | usunąć | usunąć | usunąć, także na VPS | można od razu (E0) |
| **U03** Monitoring (Uptime Kuma, Beszel) | profil compose `monitoring` | nie przenosimy; zastępuje go `jarvo status` i `jarvo doctor` | to samo | tylko VPS | |
| **U04** Telefon testowy | Redroid (binder w jądrze) albo docker-android (KVM) | telefon właściciela przez adb (USB lub Wi-Fi); opcjonalnie Android Emulator z SDK (WHPX) | telefon albo emulator (Hypervisor.Framework) | telefon albo emulator (KVM); Redroid tylko na VPS | SDK i obrazy systemu to kilka GB, licencję trzeba zaakceptować; wersja emulatora niesprawdzona |
| **U05** Ekran telefonu (ws-scrcpy, proxy :9122) | obraz ws-scrcpy, proxy HQ z tokenem | scrcpy 5.0.1 w osobnym oknie (SHA256SUMS.txt); proxy :9122 wyłączone | scrcpy macos-aarch64 i macos-x86_64 | scrcpy linux-x86_64; arm64 brak | ws-scrcpy wymaga kompilacji node-pty; okno zamiast podglądu w HQ to zmiana funkcji (I24) |
| **U06** Kontener Komputera | jarvo-komputer: Xvnc, Chromium, cua-driver, iptables | wiersze J | wiersze J | wiersze J; kontener zostaje jako opcja „mocna izolacja” na Linuksie i VPS | |
| **U07** Sieci i wolumeny compose | jarvo-net, jarvo-komputer-net, wolumeny nazwane (macOS) | brak: 127.0.0.1 i zwykłe katalogi | brak | brak | adresy `searxng:8080` i `jarvo-android:5555` znikają z env i testów |
| **U08** Usługi obok Hermesa (zbiorczo) | compose up | żadnych sidecarów, tylko procesy nadzorcy | to samo | to samo | |

### Skrypty, budowa i środowisko

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **S01** infra/bin | jarvo-tts, jarvo-stt, jarvo-klucz (shebang /opt/jarvo/venv/bin/python), agent-browser (bash), manimgx (sh) | paczka Pythona z console_scripts (.exe); fcntl → przenośna blokada; jarvo-klucz tylko w trybie LAN | te same console_scripts | to samo | Windows nie uruchomi skryptu z shebangiem (WinError 193) |
| **S02** healthcheck.sh i healthchecki w toolbox.yaml | 95 wpisów healthcheck w 10 plikach, uruchamiane `bash -c` przez docker exec; część ze ścieżkami /opt | listy argv z miejscami na ścieżki ({python}, {repo}) i runner w Pythonie (`jarvo doctor`); nie wołamy `bash`, bo na Windows to WSL z System32 | to samo | to samo | zmiana formatu dotyka 10 profili, validate.py i evals |
| **S03** limity.py (sufity pamięci) | `docker update --memory` dla kontenerów | wyłączone; zamiast nich limity współbieżności (JARVO_HQ_MAX_PRZEBIEGOW, pracownicy kanbana, jedna Chromium naraz); Job Object po pomiarach | to samo | VPS zostaje przy limity.py; natywnie ewentualnie `systemd-run -p MemoryMax` (niesprawdzone) | ciężkie narzędzia mogą zająć RAM laptopa |
| **S04** local-up.sh → `jarvo instaluj` | ~/jarvo-local, hasła z `openssl rand`, `sudo chgrp 10000`, chown | Python: katalogi z (c1), `secrets.token_hex`, bez sudo i chown | to samo | to samo | |
| **S05** deploy.sh → `jarvo wdroz` | compose, kontenery jednorazowe (validate, build), docker exec (install-fleet, healthcheck) | stop usług, migracje danych, build.py, install_fleet.py, start, doctor; validate.py tylko w CI | to samo | to samo | idempotencja i komunikaty jak dziś |
| **S06** build.py natywnie | tokeny /opt/data/jarvo/…, `--runtime-build-dir /opt/jarvo/build`, lista usług z docker-compose.yml | `--dane` i ścieżki z instalacji, zapis przez as_posix() i w cudzysłowie; rejestr usług zamiast compose; wartości per system: silnik przeglądarki, wyszukiwarka, polecenia STT i TTS, zakazy | to samo | to samo | ścieżka z „\” w YAML w podwójnym cudzysłowie łamie plik (ScannerError, sprawdzone) |
| **S07** install-fleet.sh → install_fleet.py | bash + GNU: `sed -i`, `diff -rq`, `cp -r`, find + xargs + sha256sum, `ln -sfn`, `/command/s6-svc` | Python (ruamel/re, filecmp, shutil, hashlib), junction albo kopia, restart przez nadzorcę, bez `--alias`, generowanie kluczy API | symlink | symlink | |
| **S08** Pomocnicze skrypty Pythona (merge_env, merge_host_config, share_keys, profile_model, enable_plugin, install_themes, prune_skills, `wiedza.py zasiej`, jarvo_link) | uruchamiane Pythonem Hermesa na ścieżkach /opt | działają po zmianie ścieżek; chmod → ACL; replace z ponawianiem; jarvo_link bez fcntl | bez zmian | bez zmian | |
| **S09** updater.py (pomocnik aktualizacji) | proces hosta: docker exec, wslpath, explorer.exe, os.killpg | rola nadzorcy: czyta state/update-request i uruchamia `jarvo update` jako osobny proces | to samo | to samo | kontrakt plików z panelem zostaje bez zmian |
| **S10** obraz.sh, obraz.yml, check-pins.py, .dockerignore | obraz w GHCR, klucz z `git hash-object` | zostają tylko dla VPS i testu migracji; check-pins sprawdza też platformy i manifest | nie dotyczy | VPS | |
| **S11** Zmienne środowiska obrazu | ENV w Dockerfile i compose: PATH, CHROME_PATH, `PUPPETEER_*`, `HYPERFRAMES_*`, NODE_PATH, HERMES_LOCAL_STT_COMMAND, JARVO_MODELS_DIR, INDRA_OCR_MODEL_DIR, CLAUDE_PLUGIN_ROOT, JARVO_KNOWLEDGE_DIR, HERMES_WRITE_SAFE_ROOT… | plik środowiska bez sekretów `<stan>\srodowisko.json`, generowany przez instalator i stosowany przez nadzorcę i `jarvo chat` | to samo | to samo | pominięta zmienna wychodzi dopiero w jednym narzędziu, więc doctor działa w tym samym środowisku co brama |
| **S12** Branding dashboardu | patch_dashboard.py łata /opt/hermes przy budowie obrazu (web_dist i 3 pliki Pythona), timeout-kill s6 30 s | CI łata kopię web_dist dla przypiętego commitu i publikuje ją z sha256; dashboard dostaje HERMES_WEB_DIST i `--skip-build`; łatki Pythona na loopback zbędne, w trybie LAN jako wtyczka | to samo | to samo | checkout Hermesa zostaje czysty; ścisłe wzory powloka.json mają zatrzymać CI, nie instalację u użytkownika |
| **S13** VPS, piaskownica, reszta infra | bootstrap-vps.sh, backup.sh (restic, sqlite3), restore-test.sh, sandbox-up.sh (dockerd) | nie dotyczy | nie dotyczy | VPS: na razie Docker (zamrożony), potem natywny Linux; piaskownica Claude Code: natywna instalacja | sekcja (j) |
| **S14** validate.py i zrodla.py | `bash -n` przez CreateProcess (na Windows trafia w WSL); `paczka` tylko tar do 50 MB | jawny Git Bash albo pominięcie z ostrzeżeniem; parsowanie .ps1; nowe reguły: `pliki` per platforma, zgodność manifestu, brak poleceń kontenerowych w dokumentach; zrodla.py: zip, sha256 strumieniowo, tryb wydań (tagi) | to samo | to samo | Node dla macOS ma 58–60 MB, więc limit 50 MB nie wystarczy |
| **S15** vendor/zrodla.yaml | `repo` albo `paczka` + `przejrzane`; sumy per platforma w notatkach i w Dockerfile | nowe pola `wydanie` i `pliki` z kluczami windows-x64, windows-arm64, macos-arm64, linux-x64, linux-arm64 (url, sha256, rozmiar albo `brak:` z powodem); z nich `natywne.lock.json` | to samo | to samo | jedno repo = jeden wpis; dziś pola spoza listy przechodzą walidację bez kontroli |
| **S16** Pozostałe skrypty kontenerowe | sandbox-up.sh, install-test.sh, jarvo-e2e.sh, komputer-test.sh, evals-staging.sh, kuznia.sh, redteam.sh, wiedza-kompiluj.sh, backup.sh, restore-test.sh | wersje w Pythonie: `jarvo e2e`, staging w osobnym HERMES_HOME, `jarvo wiedza kompiluj`, kopia przez sqlite3.backup | to samo | to samo | |

### Wtyczki i panel

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **W01** jarvo-hq (zakładka Jarvo, trasy /api/plugins/jarvo-hq) | hqbuild.py buduje wtyczkę, install-fleet ją kopiuje i włącza | ten sam mechanizm; podmiana z atomową zmianą nazwy po zatrzymaniu dashboardu; artefakt z CI z sha256 | to samo | to samo | na Windows z core.autocrlf=true pakiet ma inny hash (CRLF) |
| **W02** jarvo-wiedza | w bramie (pamięć, haki, schemat) i w dashboardzie; `ln -sfn` do profili | kopia albo junction; strażnik i licznik generacji AI: get_hermes_home() zamiast /opt/data i blokada międzyprocesowa | symlink | symlink | |
| **W03** jarvo-komputer (narzędzie komputer) | AF_UNIX do ster.sock | wspólny moduł transportu: named pipe z DACL | gniazdo unix w katalogu 0700 | to samo | |
| **W04** Wtyczka zgód (nowa) | brak | hak `pre_tool_call` i polecenie `/tryb` (sekcja d) | to samo | to samo | |
| **W05** Panel: ścieżki danych i instalacji | /opt/data, /opt/jarvo/build/BUILD.json, /opt/jarvo/bin, /opt/hermes w kilku modułach | jeden moduł sciezki.py: HERMES_HOME z hermes_constants, JARVO_* z env, alias /opt/data → HERMES_HOME dla starych danych | to samo | to samo | bez wartości domyślnych /opt |
| **W06** Panel: podprocesy z tras | `asyncio.create_subprocess_exec` | proc.py: subprocess w wątkach, CREATE_NO_WINDOW, Job Object; dashboard pod python.exe (nie pythonw, bo każdy ffmpeg błyskałby oknem) | ta sama ścieżka kodu | to samo | bez tego na Windows nie działa edytor, lektor HQ ani „Ponów kartę” |
| **W07** Blokada linków podglądu (hq_core.link_for) | fcntl.flock | zamek.py: msvcrt.locking na Windows, fcntl na POSIX | fcntl | fcntl | |
| **W08** Zapisy atomowe | tmp + os.replace | zapisz_atomowo() z ponawianiem (wzór utils.atomic_replace Hermesa); odczyt .env z utf-8-sig | bez zmian | bez zmian | na Windows WinError 5/32/33, gdy ktoś czyta plik |
| **W09** Uprawnienia sekretów i baz | chmod 0600 i 0700 | ACL tylko dla właściciela (pywin32 win32security); testy czytają DACL | chmod | chmod; po migracji chown z uid 10000 | os.chmod na Windows ustawia tylko „tylko do odczytu” |
| **W10** Podgląd „Odpal” :9120 i proxy ekranu :9122 | bind 0.0.0.0, upstream jarvo-android-ekran:8000 | 127.0.0.1, SO_EXCLUSIVEADDRUSE, zapasowo port 0 przy WinError 10013 (porty Hyper-V); jawna mapa typów MIME; :9122 wyłączony | 127.0.0.1 | 127.0.0.1; :9122 tylko przy `jarvo android on` | 0.0.0.0 na Windows otwiera okno zapory i wystawia port w LAN |
| **W11** Front w trybie bez logowania (loopback) | EventSource i ciasteczko sesji | strumień przez fetch + ReadableStream z nagłówkiem tokenu; 401 → przeładowanie strony; pliki jako blob albo link przez :9120 | to samo | to samo | tryb z ciasteczkiem (LAN) dalej działa |
| **W12** Ścieżki w tekście i UI | regex tylko dla /opt/data/jarvo/…, split('/') | API zwraca as_posix(); regex z faktycznego korzenia (spacje, litera dysku) + alias /opt/data | `~/.jarvo` bez spacji | bez zmian | stare rozmowy i projekty dalej się otwierają |
| **W13** „Pokaż w folderze” | pomocnik hosta: wslpath + explorer.exe przez docker exec | `explorer.exe /select,<plik>` z procesu dashboardu | `open -R` | xdg-open katalogu; bez pulpitu wyłączone | |
| **W14** Dziennik jarvo-hq.log | RotatingFileHandler, stdout = docker logs | ConcurrentRotatingFileHandler (jest w Hermesie na win32); stdout do pliku nadzorcy | jak dziś | journald albo plik | |
| **W15** Bazy SQLite panelu | rozmowy.db i nawyki.db w WAL; odczyt kanban.db i state.db | URI przez Path.as_uri(); dane na lokalnym NTFS (nie OneDrive, nie dysk sieciowy); WAL tylko za bramką B06 | to samo | to samo | rozmowy.db u właściciela jest prawie cała w pliku -wal |
| **W16** „Ponów kartę” | `/opt/hermes/.venv/bin/hermes kanban unblock` | `[python.exe, -m, hermes_cli.main, kanban, unblock, id]` przez proc.py | sys.executable | to samo | |
| **W17** Karty zgody: zdania o ryzyku | wzorce rm, sudo, chmod, kill, systemctl | dodać icacls, takeown, reg delete, Set-ExecutionPolicy, Remove-Item, Stop-Process i zapis pliku | launchctl, diskutil | jak dziś | |
| **W18** Nazwy plików z przeglądarki (inbox) | safe_upload_name | nazwy zarezerwowane (CON, NUL, COM1…) z przedrostkiem `_`; krótki korzeń (MAX_PATH 260) | NFC (czy potrzebne, niesprawdzone) | bez zmian | |

### Skarbiec

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **K01** wiedza.py (zasiew, indeks, szukanie, orzeczenia, lint, cofnij) | /opt/data/jarvo/knowledge, git, SQLite FTS5 | domyślnie `<dane>\jarvo\knowledge`; stdout w UTF-8; git z `encoding="utf-8"`, CREATE_NO_WINDOW, `-c core.autocrlf=false -c core.longpaths=true`; os.replace z ponawianiem; odrzucać „:” i „\” w nazwach; zapis z `newline="\n"`; odświeżanie indeksu bez resolve() | NFC, `.DS_Store` w .gitignore | bez zmian po ścieżkach | sprawdzone na tym Windows: 32–33 z 34 testów przechodzi |
| **K02** Zasiew i lint przy instalacji | install-fleet.sh przez docker exec; zasiew bez blokady; lintu nikt nie uruchamia | install_fleet.py: zasiew + indeks + punkt zapisu pod blokadą, potem lint informacyjny | to samo | to samo | docs/WIEDZA.md obiecuje lint przed kompilacją: kod tego nie robi |
| **K03** Kompilacja skarbca | wątek wtyczki co godzinę i o 03:10; przycisk woła `bash scripts/wiedza-kompiluj.sh` (ścieżki /opt) | `jarvo wiedza kompiluj` i przycisk wołają kompilacja.py Pythonem z venvu; blokada msvcrt/fcntl; sortowanie po (mtime, nazwa); nocny przebieg nadrabiany po uśpieniu | to samo | to samo | dziś `bash` z Pythona na Windows uruchamia bash z WSL (sprawdzone) |
| **K04** Zakładka „Wiedza” | backend w dashboardzie, domyślne /opt | get_hermes_home(); historia notatki z poprawionym dekodowaniem gita (dziś błąd 500 na „Ł”) | to samo | to samo | |
| **K05** Narzędzie `schemat` (SVG → PNG) | preexec_fn, potoki na fd 3/4, select na potokach, chromium z PATH | `chrome-headless-shell --screenshot` albo CDP przez `--remote-debugging-io-pipes` z dziedziczonymi uchwytami | działa po ustawieniu JARVO_CHROMIUM | działa | regex MEDIA w HQ musi przyjmować ścieżki z literą dysku |
| **K06** Git w skarbcu | git z obrazu | PortableGit; usuwanie przez rmtree z onerror (obiekty .git są tylko do odczytu) | CLT albo conda-forge | systemowy | `hermes backup` pomija katalogi .git |
| **K07** Lint skarbca | tylko z panelu i CLI | po zasiewie i przed kompilacją; reguły nazw przenośnych (zarezerwowane, kropka lub spacja na końcu, ścieżka >240 znaków) | + NFC | to samo | na starych skarbcach pojawią się nowe ostrzeżenia |
| **K08** doctor: skarbiec, rutyny, Telegram | brak | FTS5 z remove_diacritics, git, LongPathsEnabled, skarbiec poza OneDrive, wiek ostatniej kompilacji, błędy lintu, rutyny wstrzymane, brama działa, 409 w logu | + iCloud | + linger | |

### Flota: agenci, skille i skrypty

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **F01** jarvo (Main Judge): 11 skryptów, 14 skilli, 4 rutyny | domyślne ścieżki /opt w patrol, fleet_report, lekcje, liczby, poczekalnia, swiezosc; `hermes` bez which | moduł jarvo_paths; `shutil.which` albo JARVO_HERMES_BIN (launcher bywa .cmd); sqlite przez as_uri; poczekalnia z `venv\Scripts` | `~/.jarvo` | bez zmian po ścieżkach | testy tych skryptów przechodzą natywnie na Windows (sprawdzone); patrol bez INDEX.md milczy, więc brak ma być zgłaszany |
| **F02** jarvo-web: 10 skryptów, 10 skilli, MCP inspo | audit.sh (bash 4, ścieżka z `pwd`), brand_extract.sh, skrypty .cjs z `--no-sandbox`, security_check.py woła `npm` | audit.py i brand_extract.py w Pythonie; CHROME_PATH; bez `--no-sandbox`; npm przez which; podgląd stron na 127.0.0.1 zamiast 0.0.0.0 | bash 3.2 nie zna `declare -A`, więc też Python | Ubuntu 24.04: piaskownica Chromium wymaga profilu AppArmor (sudo raz) | pierwsza sesja zleca audyt Webowi; skill audyt-strony opisuje security_check w audit.sh, a skrypt go nie woła |
| **F03** jarvo-sherlock: 4 skrypty, 8 skilli | SearXNG, `lightpanda fetch --dump markdown`, extract.py z os.execv do /opt/jarvo/venv, exiftool | wyszukiwarka z U01; bez `lightpanda fetch` (odczyt przez browser_*); extract.py bez execv, wynik przez as_posix | `lightpanda fetch` zostaje | to samo | pierwsza sesja (konkurencja) potrzebuje działającej wyszukiwarki |
| **F04** jarvo-lowca: 8 skryptów, 7 skilli | sama biblioteka standardowa + har.cjs (Playwright) | logika bez zmian; python3 i node w PATH procesów, CHROME_PATH, `"$HERMES_HOME"` w cudzysłowie, pamięć HTTP w `<dane>` zamiast ~/.cache | to samo | to samo | najłatwiejszy do przeniesienia; testy przechodzą natywnie |
| **F05** jarvo-reka: 2 skrypty, 4 skille | pack.py, to_pdf.py; pandoc, ocrmypdf, qpdf, LibreOffice; external_dirs w buildzie (:ro) | MANIFEST przez as_posix; CHROME_PATH i SOFFICE z instalacji; external_dirs z „/” | to samo | to samo | natywnie external_dirs przestają być tylko do odczytu (F16) |
| **F06** jarvo-studio: check_media.py, lemo_wake.py, render_html.cjs | ffprobe, Playwright z NODE_PATH, Postiz jako opcjonalny kontener AGPL | działa po CHROME_PATH i NODE_PATH; lemo w M07; Postiz tylko jako zewnętrzny POSTIZ_URL | to samo | to samo | |
| **F07** jarvo-ads: 5 skryptów | biblioteka standardowa; skille uruchamiają .py przez shebang | kod bez zmian; skille wołają interpreter jawnie | shebang trafiłby w zaślepkę /usr/bin/python3 | działa | Skarbiec (osobny kontener z budżetem) zostaje odłożony |
| **F08** jarvo-mobile: 15 .py, 4 .cjs + Node, npx, expo, eas-cli, adb | `subprocess.run(["npx", ...])` listą, adb do kontenera Redroid, tesseract w sklep_check | resolver programów (lista z `npx` daje WinError 2, pełna ścieżka .CMD działa; sprawdzone); telefon właściciela (U04); ścieżki z warstwy ścieżek | npm działa listą | adb na arm64 z systemu | iOS dalej przez GitHub Actions na macOS; przy .cmd ostrożne cytowanie argumentów |
| **F09** jarvo-operator | computer_use i narzędzie komputer w kontenerze; 18 stałych zgód `cua:*` | Komputer natywny (wiersze J); adres przez launch_app, działania w tle (zgody `:foreground` zbędne) | to samo | to samo | nigdy tryb pełny; scenariusze evals okno_nieaktywne i punkt_w_tle zmieniają oczekiwanie |
| **F10** shared: transkrybuj.py, iso.py z iso_render.cjs, graf_kodu.py, prosty.py | ścieżki /opt; graf_kodu zna tylko codebase-memory-mcp dla Linuksa | bin Jarva i rozszerzenie .exe; JARVO_REPO; sumy `windows-*.zip` i `darwin-*.tar.gz` z v0.11.0 | to samo | bez zmian | licencja codebase-memory-mcp: raporty podają MIT albo „niesprawdzone” |
| **F11** fleet.yaml | missions_dir i workspaces_dir = /opt/data/…, `infra.host: vps`, hermes_image (digest), usługi sprawdzane przez docker-compose.yml | ścieżki względne do `<dane>`; pin Hermesa tagiem i commitem; host: local albo vps; rejestr usług zamiast compose | to samo | to samo | zmiana dotyka walidatora, testów i dokumentów |
| **F12** python3 w skillach i skryptach | python3 = Python Hermesa w PATH kontenera | token `@@PY@@` (pełna ścieżka w cudzysłowie) w skillach + shim `python3` w PATH tylko procesów floty; skrypty przez sys.executable | /usr/bin/python3 to zaślepka CLT, więc shim | systemowy python3 nie ma paczek, więc shim | 53 ze 106 SKILL.md wołają python3; agent dopisuje python3 sam, więc potrzebne oba |
| **F13** Powłoka terminala | bash w kontenerze | Git Bash; ścieżek z `pwd` nie podajemy programom natywnym (`pwd -W`, `cygpath -m`); brak jq, flock, rsync, zip, make, bc | bash 3.2 (bez declare -A, mapfile) | bash 5 | zasada w validate.py: żadnych nowych .sh w profilach i shared (dziś są 2) |
| **F14** Komendy uniksowe w skillach | `python3 $HERMES_HOME/...`, `eval "$(... env ...)"` (22 razy), /tmp, /opt/data/jarvo/inbox, `cp -r`, `curl -L` | tokeny ścieżek w cudzysłowie, out/ w workspace zamiast /tmp, `uruchom` zamiast eval, `hyperframes` zamiast `npx hyperframes` | to samo | to samo | validate.py i lint skarbca łapią stare wzorce |
| **F15** Zakazy i polityki zgód (deny, smart_policy) | wzorce tylko dla /opt/data i /opt/jarvo/komputer | build generuje wzorce dla `<dane>` we wszystkich pisowniach (`C:/`, `C:\`, `/c/`, `~`, `$HERMES_HOME`) oraz polecenia Windows (Remove-Item, rmdir /s, del /s) | `~/.jarvo` | to samo | deny to podpowiedź dla modelu, nie granica |
| **F16** Izolacja po wyjściu z kontenera | repo i build `:ro`, osobny użytkownik, Chromium z `--no-sandbox` w kontenerze | tryby zgód (d), home_mode profile, HERMES_WRITE_SAFE_ROOT, piaskownica Chromium włączona; pełna izolacja tylko przez osobne konto systemowe (I09) | to samo | to samo; osobny użytkownik systemowy jest realny | red team pokazał agentów zmieniających swój config: test na natywnej flocie |
| **F17** Teksty SOUL, protokołu i skilli | „Pracuję w kontenerze”, `/opt/jarvo/repo/scripts/jarvo_link.py`, /opt/data/jarvo/inbox | tokeny `@@REPO_DIR@@` i `@@DATA_DIR@@`; reguła 9: localhost działa tylko na tym komputerze, na telefon i Telegram link przez jarvo_link | to samo | to samo | to zmiana zachowania: wpis w CHANGELOG każdego profilu i evals |

### Komputer Jarva

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **J01** Przeglądarka Jarva | Chromium z Debiana bez pinu, `--no-sandbox`, w Xvnc 1440×900 | pełny Chrome for Testing z własnym profilem, pin z sumą (dziś Stable 156.0.8078.47, ok. 200 MB), piaskownica włączona; arm64 przez x64 | mac-arm64 i mac-x64 (Gatekeeper niesprawdzony) | linux64 i linux-arm64; biblioteki systemu i AppArmor | CfT sam się nie aktualizuje: cotygodniowe podbicie w rutynie źródeł |
| **J02** Sterownik | cua-driver 0.21.0 (AT-SPI, X11), `cua-driver mcp` na sesję | własny sterownik CDP w usłudze Komputera (Playwright `launch_persistent_context`, CDP przez pipe), mówi tym samym MCP co cua-driver (structuredContent.elements, element_token, effect) | to samo | to samo | Accessibility.* i Input.insertText są „experimental”: test kontraktu przy każdym podbiciu CfT i Hermesa |
| **J03** Bramka jarvo_cua.py (K0) | AF_UNIX cua.sock; HERMES_CUA_DRIVER_CMD wskazuje plik .py | named pipe `\\.\pipe\jarvo-komputer-cua-<SID>` z DACL i PIPE_REJECT_REMOTE_CLIENTS; shim jarvo-cua.cmd; manifest z python.exe i argumentami | gniazdo w katalogu 0700 | gniazdo w XDG_RUNTIME_DIR | instalator Hermesa trzeba by wołać z -SkipComputerUse (inaczej sam instaluje cua-driver z gałęzi main przez irm i iex) |
| **J04** Wejście z twardymi zasadami (wejscie.py) | proces pulpitu w kontenerze: AT-SPI, X11, xprop, SO_PEERCRED | rdzeń bez zmian (sesja MCP, migawki, ukrywanie sekretów, dziennik, limit); nowy KontekstCDP: DOM.getNodeForLocation, odizolowany świat, Accessibility.getPartialAXTree | to samo | to samo; kontekst AT-SPI zostaje dla K6 na X11 | natywnie wejście to zwykły proces właściciela: agent z pełnym terminalem może je obejść |
| **J05** Twarde zasady (zasady.py) | role AT-SPI, ścieżka /usr/lib/chromium/chromium | mapa ról CDP na słownik zasad; nowe zasady: agent nie wkleja ze schowka właściciela, okna potwierdzeń z wrażliwym tekstem i wybór pliku robi człowiek | + skróty Cmd+Option+I/J/C | to samo | testy zasad dla każdego słownika ról |
| **J06** Filtr ruchu | iptables w kontenerze: LAN, metadane chmury, adresy hosta, port 25; samotest | lokalny proxy (asyncio ze stdlib) z własnym DNS i sprawdzaniem adresu; `--proxy-server`, `--proxy-bypass-list=<-loopback>`, WebRTC bez UDP poza proxy, bez QUIC; samotest: 169.254.169.254, 127.0.0.1:9119, brama LAN odrzucone | to samo | to samo | filtr w aplikacji, nie w jądrze, ale obejmuje cały ruch tej przeglądarki; nazwa przełącznika WebRTC niesprawdzona |
| **J07** Polityka przeglądarki | /etc/chromium/policies/managed (root): bez haseł, synchronizacji, rozszerzeń, DevTools, file:// | preferencje profilu, flagi i CDP: pobrane pliki do osobnego katalogu z anulowaniem typów wykonywalnych, odmowa kamery, mikrofonu, schowka i przechwytywania ekranu, przechwycenie wyboru pliku | to samo | to samo | polityki maszynowe wymagają HKLM (admin), więc ich nie używamy; z flag Playwrighta zdejmujemy wyłączenie ochrony przed phishingiem i blokady wyskakujących okien |
| **J08** Izolacja procesów i profil | osobny kontener, uid 10101, bez kluczy floty, limity compose | proces użytkownika ze środowiskiem bez kluczy; profil w `<dane>\komputer\profil` | to samo | to samo | flota z terminalem widzi profil z zalogowanymi kontami (decyzja I18) |
| **J09** Pauza, wznowienie, dziennik | ster.sock, wznawia tylko pulpit albo root (SO_PEERCRED) | ten sam protokół przez pipe; wznawia token właściciela (HQ po zalogowaniu albo `jarvo komputer wznow` z terminala właściciela) | to samo | to samo | token może przeczytać każdy proces właściciela, także agent w trybie pełnym |
| **J10** Podgląd i „Przejmij” w HQ (K4) | tylko RFB do podglądu | Page.startScreencast do HQ; „Przejmij” przez CDP Input.* z pauzą agenta | to samo | to samo | wejście właściciela omija twarde zasady, więc tylko z zalogowanej sesji HQ |
| **J11** Okno widoczne albo w tle | Xvnc 1440×900, nigdy na ekranie właściciela | okno CfT na pulpicie (właściciel sam się w nim loguje) albo `--headless=new` z podglądem w HQ | to samo | na VPS zawsze w tle | `jarvo komputer okno on/off` |
| **J12** Wdrożenie, autostart i aktualizacje Komputera | budowa obrazu, cotygodniowe KOMPUTER_POPRAWKI, healthcheck zdrowie.sh | usługa pod nadzorcą; `jarvo update` pobiera nowy pin CfT z sumą | to samo | to samo | |
| **J13** Test na żywo (79 sprawdzeń) | docker exec, xdotool, http.server w kontenerze | ten sam klient MCP przez bramkę; strona testowa przez Fetch.fulfillRequest; sprzątanie przez CDP | to samo | to samo | sprawdzenia związane z X11 zmieniają oczekiwany wynik |
| **J14** Ręce: ekran właściciela (K6) | w planie | cua-driver-rs 0.38.0 windows-x86_64 i -arm64 (podpis Authenticode „Cua AI, Inc.”, Sigstore), tryb bounded; okna administratora (UIPI) poza zasięgiem | CuaDriver.app (universal) w /Applications (wymaga admina), Dostępność i Nagrywanie ekranu ręcznie | x86_64 z X11 albo XWayland i AT-SPI2; arm64 jako preview | tylko po osobnej zgodzie; telemetria wyłączona; od 0.36 goła binarka na macOS nie działa |
| **J15** Osobna zgoda na ekran właściciela | brak; validate.py nie przepuszcza `plugin_rule:komputer` | `jarvo komputer rece on --aplikacje ... --na 30m` tworzy manifest bounded; bramka przepuszcza `serve` tylko z nim; ekran przełącza tylko właściciel | to samo | to samo | klucze zgód Hermesa (`cua:<akcja>:<tryb>`) nie mają celu, więc na ekranie właściciela bez stałych zgód |
| **J16** Migracja Komputera | wolumen jarvo-komputer-dom (profil, Pobrane, pauza, dziennik) | kopiujemy Pobrane, dziennik i stan pauzy; profilu nie (właściciel loguje się od nowa) | to samo | to samo | u właściciela jest tylko wolumen gniazd, kontenera nie było |
| **J17** Walidator, build i deny Komputera | check_komputer; deny `*/opt/jarvo/komputer*` | reguły walidatora zostają; deny dla katalogu Komputera, nazwy potoku i `--remote-debugging-port` | to samo | to samo | |

### Polecenia jarvo

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **N01** bin/jarvo | bash 4 (na macOS bash z Homebrew), compose i docker exec; na Windows jarvo.cmd woła WSL | jedno CLI w Pythonie (venv Jarva) + `<root>\bin\jarvo.cmd` w PATH użytkownika (polityka Restricted blokuje .ps1, nie blokuje .cmd) | `~/.local/bin/jarvo` + oznaczony blok PATH w ~/.zprofile | `~/.local/bin/jarvo` bez sudo | te same podpolecenia na 3 systemach; ten sam wpis PATH co dziś na Windows |
| **N02** jarvo up / down | compose up / down | start i stop nadzorcy; `up` bez instalacji robi instalację | to samo | to samo | |
| **N03** jarvo status | compose ps | PID-y z nadzorcy, stan bramy i panelu, wersje z locka, autostart, rutyny, Telegram, porty | to samo | to samo | WMIC jest usunięty z Windows 11, więc `hermes dashboard --status` nie widzi procesów: PID-y trzyma nadzorca |
| **N04** jarvo logs | compose logs | pliki logów nadzorcy (3 × 10 MB) i logi Hermesa | to samo | to samo | |
| **N05** jarvo chat | `docker exec -it -u hermes jarvo-hermes hermes -p <p> chat` | `hermes -p <profil> chat` w środowisku Jarva; `--tryb pytaj/projekt/pelny` | to samo | to samo | sekcja (d) |
| **N06** jarvo open / panel / link / haslo | klucz jednorazowy przez docker exec; hasło z compose/.env | `jarvo panel`: startuje panel, jeśli trzeba, i otwiera http://127.0.0.1:9119/jarvo bez klucza; `link` i `haslo` tylko w trybie LAN | to samo | to samo | |
| **N07** jarvo pliki | docker cp z wolumenu (macOS) | otwiera `<dane>\jarvo\workspaces` w Eksploratorze | Finder | xdg-open | |
| **N08** jarvo autostart on/off/status | systemd --user, LaunchAgent, Jarvo.vbs | zadanie Harmonogramu nadzorcy | LaunchAgent | systemd --user | linger tylko za zgodą i zapisany w dzienniku zmian hosta |
| **N09** jarvo update (+ przycisk w panelu, HOST_VERSION) | git fetch + ff-merge + install.sh; przycisk woła deploy.sh; HOST_VERSION=5 | procedura z (c4): nowa wersja obok starej, drenaż bramy, przełączenie, doctor, wycofanie | to samo | to samo | HOST_VERSION zastępuje numer schematu w manifeście |
| **N10** jarvo doctor (nowe) | brak (healthcheck.sh w kontenerze) | healthchecki argv, sumy narzędzi, porty, wersje, SQLite, zamknięcie DLL, SAC, strona kodowa, 8.3, LongPaths, Git Bash, rutyny, Telegram | + TCC, Gatekeeper | + user bus, linger, AppArmor | ten sam skaner śladów co uninstall |
| **N11** jarvo uninstall | compose down, usuwanie obrazów i wolumenów, autostart off; `--all` usuwa dane | stop → cofnięcie dziennika zmian hosta od końca → usunięcie `<program>`; dane tylko z `--all`; stara instalacja osobnym pytaniem | to samo | to samo | test migawki w CI (T08) |
| **N12** jarvo android on/off/status | Redroid albo docker-android, modprobe, apt | adb do telefonu właściciela albo emulatora; scrcpy | to samo | to samo; Redroid tylko na VPS | |
| **N13** jarvo komputer on/off/status/pauza/wznow/dziennik/wyczysc/odswiez | bash, docker buildx, docker exec, docker stats | Python; `on` = CfT z sumą + autostart + samotest proxy; nowe: `okno on/off`, `rece on/off` | to samo | to samo | |
| **N14** jarvo migruj (nowe) | brak (migrate_jarvo.py robi tylko TARS → Jarvo) | sekcja (f); instalator woła sam po wykryciu starej instalacji | to samo | to samo | |
| **N15** jarvo klucz (nowe, prywatna kopia repo) | JARVO_TOKEN zapisany jako nagłówek w .git/config albo token.dat | Menedżer poświadczeń; sprawdzenie przez GET /repos; stan bez sekretu w update.json | pęk kluczy | libsecret albo plik 0600 | repo jest dziś publiczne; dotyczy prywatnych kopii |
| **N16** jarvo version / updater / help | git i bash | wersja z locka; updater to rola nadzorcy | to samo | to samo | |
| **N17** Nowe polecenia pomocnicze | brak | `jarvo serwis`, `jarvo wiedza kompiluj`, `jarvo narzedzia instaluj/dodaj`, `jarvo e2e <etap>` | to samo | to samo | |

### Dane

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **D01** HERMES_HOME | /opt/data = ~/jarvo-local/data/hermes (uid 10000, 0700) albo wolumen na macOS; HOME konta hermes w danych (.npm, .cache, tirith) | `<dane>` = HERMES_HOME Jarva, ten sam układ; HOME agentów w `<profil>\home` | `~/.jarvo/dane` | `~/.local/share/jarvo/dane` | przy migracji pomijamy .npm, .cache, bin/, lazy-packages |
| **D02** Sekrety i konfiguracja hosta | secrets/*.env (grupa 10000, 640), compose/.env, compose/jarvo.env, auth.json; klucze w 3 kopiach | `<dane>\jarvo\konfig\` (jarvo.env i źródłowe sekrety) + .env w HERMES_HOME i profilach; ACL; bez SEARXNG_SECRET i BESZEL_AGENT_KEY; DASHBOARD_* tylko w trybie LAN | 0600 | 0600, bez chgrp | merge_env zostaje, ale z jednym źródłem prawdy |
| **D03** Repo i build | /opt/jarvo/repo:ro (54 MB), /opt/jarvo/build:ro (1,3 GB) | `<program>\app\<wersja>` (bez .git) i `<root>\build` (odtwarzalny) | to samo | to samo | builda nie migrujemy |
| **D04** Stara instalacja właściciela | Ubuntu w WSL z ~/jarvo-local; martwa kopia stosu w Docker Desktop; dystrybucja Jarvo z samym install.log | sekcja (f) | Colima i wolumeny | ~/jarvo-local | |
| **D05** Migracja skarbca i rutyn | skarbiec z .git w danych; stan rutyn w jobs.json profilu jarvo | kopia z .git, indeks od nowa (`indeksuj --pelny`), zasiew, lint, punkt zapisu „migracja z Dockera” | to samo | to samo | wiedza.db nie kopiujemy |
| **D06** Modele i narzędzia w danych | /opt/data/jarvo/models, /opt/data/jarvo/narzedzia | modele w `<dane>\jarvo\models` (przenośne, ze sumą); instalacje w locie w `<program>\narzedzia-floty` (ścieżka ASCII) | to samo | to samo | narzędzia z kontenera są linuksowe, nie migrujemy |
| **D07** Klucz do prywatnej kopii repo | nagłówek Authorization w .git/config, token.dat (DPAPI), docker login do GHCR | N15; zasoby wydań przez API z tokenem, przekierowanie bez nagłówka Authorization | to samo | to samo | klucz fine-grained: jedno repo, Contents: read, z datą ważności |
| **D08** Ślady poza katalogiem Jarva | linger, grupa docker, repo Dockera w apt, ~/.zprofile, ~/.docker/config.json, Jarvo.vbs, RunOnce, sudoers, .wslconfig | dziennik zmian hosta `<stan>\zmiany-hosta.jsonl`, cofany od końca; zmienne cache i HOME tylko w procesach Jarva | to samo | to samo | szczegóły w (c4) i (f) |

### Instalacja i dostarczanie narzędzi

| Element | Dziś | Windows | macOS | Linux | Uwagi |
|---|---|---|---|---|---|
| **L01** Bootstrap Windows (install.ps1) | WSL2 (UAC, restart, RunOnce), import Ubuntu, sudoers NOPASSWD, systemd, Docker w WSL, Jarvo.vbs | PS 5.1 (ASCII, bez BOM): uv z sumą wpisaną w skrypt, potem Python, potem instalator w Pythonie; bez admina i bez restartu | nie dotyczy | nie dotyczy | starą instalację wykrywa i proponuje migrację |
| **L02** Bootstrap Linux i macOS (install.sh) | pakiety systemowe, Docker z get.docker.com, Homebrew + Colima, grupa docker | nie dotyczy | bash 3.2: curl + `shasum -a 256` tylko dla uv, dalej Python; bez Homebrew; git z CLT albo pixi | bash: curl + sha256sum; sudo tylko na biblioteki Chromium | |
| **L03** Manifest i pobieracz | sumy tylko w Dockerfile | `vendor/zrodla.yaml` → `natywne.lock.json`; pobieracz ze stdlib: pasek postępu, wznawianie, sha256 przed rozpakowaniem, katalogi wersji | to samo | to samo | lustro dla plików, które znikają u źródła (I21) |
| **L04** pixi (dostęp do conda-forge) | nieużywane | pixi 0.83.0 (BSD-3, .sha256) z pixi.lock tylko dla tesseract (+ ewentualnie ghostscript) | tesseract, git, bash, exiftool z Perlem | tesseract | PIXI_NO_TELEMETRY=1; binarkę bierzemy sami, bez skryptu instalacyjnego; rattler w wersji z poprawkami CVE-2026 |

## (c) Architektura natywna

### c1. Katalogi

| Rola | Windows | macOS | Linux |
|---|---|---|---|
| Korzeń Jarva `<root>` | `%LOCALAPPDATA%\Jarvo` | `~/.jarvo` | `${XDG_DATA_HOME:-~/.local/share}/jarvo` |
| Program `<program>` (wymienny, wersje obok siebie, ścieżka ASCII) | `<root>\program` | `<root>/program` | `<root>/program` |
| … w nim | `app\<wersja>` (kod Jarva), `hermes\<commit>` (checkout Hermesa z venv), `python\` (PBS przez uv), `venvs\<nazwa>-<hash>`, `node\<wersja>`, `git\<wersja>`, `narzedzia\<nazwa>\<wersja>`, `web-dist\<hash>`, `narzedzia-floty\` (instalacje w locie), `bin-floty\` (python3, agent-browser, jarvo-tts…), `current.json` | to samo bez `git\` | to samo |
| Dane `<dane>` = HERMES_HOME | `<root>\dane` | `<root>/dane` | `<root>/dane` |
| … w nim | config.yaml, .env, auth.json, state.db, kanban.db, `profiles\`, `plugins\`, `skins\`, `cron\`, `sessions\`, `logs\`, `jarvo\` (knowledge, state, missions, workspaces, inbox, models, konfig, komputer) | to samo | to samo |
| Build (odtwarzalny) | `<root>\build` | `<root>/build` | `<root>/build` |
| Stan `<stan>` | `<root>\stan`: zmiany-hosta.jsonl, gateway-locks, srodowisko.json, narzedzia.json, potok nadzorcy | `<root>/stan` (gniazdo nadzorcy 0600) | `<root>/stan` |
| Logi | `<root>\logi` | `<root>/logi` | `${XDG_STATE_HOME:-~/.local/state}/jarvo/logi` |
| Cache (uv, npm, pip, HF, pobrania) | `<root>\cache` | `<root>/cache` | `${XDG_CACHE_HOME:-~/.cache}/jarvo` |
| Polecenie `jarvo` | `<root>\bin\jarvo.cmd` w PATH użytkownika (ten sam wpis co dziś) | `~/.local/bin/jarvo` + oznaczony blok w ~/.zprofile | `~/.local/bin/jarvo` |
| Wyniki dla właściciela | `<dane>\jarvo\workspaces`, otwierane przez `jarvo pliki` | to samo | to samo |

Zasady katalogów:
- `<program>` musi mieć ścieżkę ASCII. espeak-ng, OpenCV i Tesseract mają wąskie API ścieżek. Gdy `%LOCALAPPDATA%` ma polskie znaki, instalator bierze krótką nazwę 8.3 (jeśli jest i jest ASCII), a w ostateczności `C:\ProgramData\Jarvo\<SID>\program` z ACL tylko dla użytkownika (niesprawdzone w VM).
- Wszystko poza OneDrive i iCloud. Dane na lokalnym dysku, nie na dysku sieciowym (SQLite w WAL).
- Zmienne cache i HOME ustawia launcher tylko w swoich procesach: HERMES_HOME, HERMES_GATEWAY_LOCK_DIR, HERMES_GIT_BASH_PATH, PLAYWRIGHT_BROWSERS_PATH, npm_config_cache, UV_CACHE_DIR, UV_PYTHON_INSTALL_DIR, PIP_CACHE_DIR, HF_HOME, XDG_CACHE_HOME, FONTCONFIG_FILE, CUA_DRIVER_RS_HOME, PYTHONUTF8=1, PYTHONIOENCODING=utf-8. Dzięki temu odinstalowanie nie zostawia cache w profilu użytkownika.
- Dlaczego nie domyślny katalog Hermesa (`%LOCALAPPDATA%\hermes`, `~/.hermes`): Hermes pilnuje jednej bramy na użytkownika, install.ps1 Hermesa nadpisuje HERMES_HOME i zabija każdy hermes.exe, a `hermes uninstall` kasuje zmienne. Prywatny Hermes właściciela i Jarvo muszą się nie widzieć.
- Ryzyko nazwy `%LOCALAPPDATA%\Jarvo`: stary install.ps1 z JARVO_UNINSTALL=1 kasuje cały ten katalog (install.ps1:346-354), a w `wsl\` leży stara dystrybucja Jarvo. Nowy install.ps1 zastępuje stary pod tym samym adresem, więc stary deinstalator da się uruchomić tylko z przypiętego starego adresu. Alternatywa: dane poza tym katalogiem (decyzja I01).
- Dlaczego `~/.jarvo` na macOS, a nie `~/Library/Application Support/Jarvo`: spacja w ścieżce psuje wyrażenia regularne w HQ i niecytowane polecenia w skillach.

### c2. Procesy w tle i nadzór

```
autostart systemu (Harmonogram zadań / LaunchAgent / systemd --user)
  └─ jarvo serwis   (nadzorca, Python; na Windows pythonw.exe)
       ├─ brama:  python -m hermes_cli.main gateway run --external-supervisor
       │          Telegram, API 127.0.0.1:8642, cron, dyspozytor kanbana, wtyczka jarvo-wiedza
       │          └─ pracownicy kanbana: python -m hermes_cli.main -p <agent> --cli ... chat -q
       ├─ panel:  python -m hermes_cli.main dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build
       │          HERMES_WEB_DIST; jarvo-hq: silnik rozmów, podgląd :9120, rendery i konwersje
       ├─ Komputer (opcjonalnie): CfT przez Playwright + wejście z zasadami + proxy filtrujące
       └─ rola pomocnika aktualizacji: state/update-request → jarvo update (osobny proces)
```

Polityka nadzorcy:
- Kolejność startu: brama, potem panel, potem Komputer.
- Brama startuje z HERMES_GATEWAY_DETACHED=1 i HERMES_SUPERVISED_CHILD=1. Wtedy `/restart` z Telegrama kończy proces kodem 75, a nie odłączonym pomocnikiem.
- Kod 75: restart po ok. 5 s. Kod 78: postój i powód w `jarvo status`. Inne kody: ponowienie z rosnącą przerwą od 5 s do 5 min.
- Zatrzymanie: najpierw drenaż bramy przez jej potok sterujący (`pause-for-update`, czeka na trwające tury), potem znacznik planowanego zatrzymania, potem zabicie tylko procesu launchera (Windows) albo SIGTERM (POSIX). Limit 30 s, jak dziś w s6.
- Windows: dzieci startują z CREATE_BREAKAWAY_FROM_JOB, CREATE_NEW_PROCESS_GROUP i CREATE_NO_WINDOW. Bez Job Object z KILL_ON_JOB_CLOSE. Nigdy `taskkill /T`, bo zabiłby pracowników kanbana w trakcie karty. Nie wołamy `hermes gateway stop/restart` ani `hermes update`.
- Linux: pracownicy kanbana idą do `systemd-run --user --scope` (robi to Hermes). Bez user bus karta nie rusza, więc doctor to sprawdza.
- Logi stdout i stderr: pliki otwarte z FILE_SHARE_READ, WRITE i DELETE (pywin32), rotacja „kopiuj i przytnij” 3 × 10 MB.
- Kanał sterowania nadzorcy: named pipe z DACL tylko dla użytkownika (Windows), gniazdo 0600 (POSIX). Korzystają z niego `jarvo status`, `restart`, `update`, `stop`, `logs`.
- Sprawdzanie życia: `identify` przez potok bramy i plik heartbeat co 30 s.

Autostart:
- **Windows.** Zadanie Harmonogramu „Jarvo” z pliku XML: LogonTrigger z UserId (bez admina), opóźnienie PT15S, akcja `<program>\python\...\pythonw.exe -m jarvo.nadzorca` (synchronicznie, więc zadanie ma stan Running), Priority 5, DisallowStartIfOnBatteries=false, StopIfGoingOnBatteries=false, ExecutionTimeLimit=PT0S, IgnoreNew oraz zapasowe wyzwalacze SessionUnlock i co 5 minut. Rejestracja `schtasks /Create /TN Jarvo /XML plik /F` bez wcześniejszego kasowania, start `schtasks /Run /TN Jarvo`. Gdy polityka blokuje Harmonogram: wpis HKCU Run (bez podtrzymania). Bez usługi Windows, bo wymaga admina. Domyślne ustawienia `schtasks /SC ONLOGON` zatrzymałyby nadzorcę na baterii i po 72 godzinach.
- **macOS.** `~/Library/LaunchAgents/pl.jarvo.nadzorca.plist`: RunAtLoad, KeepAlive {SuccessfulExit=false}, ThrottleInterval 30, bez ProcessType Background (dławiłby render). System pokaże powiadomienie „Background Items” i to jest normalne.
- **Linux.** `~/.config/systemd/user/jarvo.service`: Restart=on-failure, KillMode=mixed, TimeoutStopSec dłuższy niż drenaż. Linger tylko za zgodą (praca bez zalogowania). VPS: jednostka systemowa i użytkownik `jarvo`.
- Konkurencja: doctor wykrywa i (za zgodą) usuwa Hermes_Gateway, ai.hermes.gateway, hermes-gateway.service, stary Startup\Jarvo.vbs i stary jarvo-updater.

### c3. Jak instalator pobiera narzędzia

Droga rekomendowana w raporcie „dystrybucja”: wydania u źródła + jeden manifest Jarva + jeden pobieracz w Pythonie. conda-forge (pixi) tylko na luki. winget, brew i apt nigdy.

1. **Bootstrap.** install.ps1 (PowerShell 5.1, ASCII, bez BOM) albo install.sh (bash 3.2). Plik serwuje jarvo.pl i repo (dziś jarvo.pl zwraca 404 dla install.*, poprawka w E0). Bootstrap zna tylko dwie sumy: uv dla tej platformy i manifestu wydania (albo archiwum aplikacji `jarvo-app-<wersja>.tar.gz`). Pobiera `curl.exe --progress-bar` albo `curl -#`, sprawdza Get-FileHash, `shasum -a 256` albo `sha256sum` i rozpakowuje tar.exe, Expand-Archive albo tar.
2. **Python.** `uv python install` z UV_PYTHON_DOWNLOADS_JSON_URL wskazującym naszą listę PBS 20261021 z sumami (uv sprawdza sumę tylko wtedy, gdy wpis ją ma). Katalog `<program>\python`, bez rejestru Windows i bez kopii w bin.
3. **Instalator w Pythonie.** `python -I -X utf8 -m jarvo instaluj`. Czyta `natywne.lock.json` i dla bieżącej platformy bierze: adres, sha256, rozmiar, format, ścieżki binarek w archiwum i adres zapasowy. Pokazuje pasek (%, MB, prędkość), wznawia pobieranie (nagłówek Range), sprawdza sumę przed rozpakowaniem, rozpakowuje do `<nazwa>\<wersja>.new` i dopiero potem zmienia nazwę. Na Windows bez symlinków. Wynik zapisuje w `<stan>\narzedzia.json`.
4. **Narzędzia z wydań u źródła:** Node, PortableGit (Windows), ripgrep, ffmpeg i ffprobe, chrome-headless-shell, qpdf, pandoc, ExifTool (Windows i Linux), fonty, platform-tools, scrcpy. **Przez pixi z pixi.lock:** tesseract, a na macOS także git, bash i exiftool z Perlem.
5. **Hermes.** `git clone` + checkout f97608f, potem `uv sync --locked` z extras jak w obrazie, bez UV_NO_CONFIG. Na POSIX z pustym XDG_CONFIG_HOME i XDG_CONFIG_DIRS. Błąd = koniec instalacji.
6. **Venvy Jarva.** `uv venv` z PBS 3.12.15 albo 3.13.17, potem `uv pip install --no-config --require-hashes --only-binary :all: --no-deps -r <lock>`. Na Windows kopia runtime VC++ obok bazowego python.exe (B11).
7. **npm.** `npm ci --ignore-scripts` z package-lock.json. Binarkę agent-browsera dla platformy wybiera instalator.
8. **Modele.** Hugging Face `/resolve/<commit>/` z sumą, do `<dane>\jarvo\models`.
9. **Leniwie, przy pierwszym użyciu, z paskiem i pytaniem:** Camoufox (0,3–0,5 GB), Parakeet (0,67 GB), LibreOffice, CAD, ManimGX, pełny Chrome dla Komputera i dodatki z M08.
10. **Prywatna kopia repo.** Najpierw anonimowo przez `releases/latest/download/<plik>`. Przy 404 klucz z magazynu systemu i API zasobów wydań (`Accept: application/octet-stream`); podpisany adres pobieramy już bez nagłówka Authorization. W urllib przez add_unredirected_header.
11. **Bezpieczeństwo.** W CI każdą przypiętą binarkę dla Windows skanuje Defender (tirith v0.4.2 został oznaczony jako trojan). Szacunek instalacji podstawowej: ok. 1,5–2 GB (niesprawdzone, z raportu dystrybucja).

### c4. Polecenia: update, doctor, status, panel, uninstall

**jarvo update** (CLI i przycisk w panelu to ta sama procedura):
1. Sprawdź wydanie i manifest.
2. Przygotuj nową wersję obok starej: aplikacja, brakujące narzędzia (po sumie), nowe venvy (UV_LINK_MODE=copy, bo na Windows załadowanych .pyd nie da się nadpisać), nowy checkout Hermesa z `uv sync --locked`, web_dist, build.py do nowego katalogu.
3. Drenaż bramy (`pause-for-update` przez potok), zatrzymanie panelu.
4. Przełączenie `current.json`, `install_fleet.py` (profile, wtyczki, klucze), `hermes config migrate`.
5. Start i `jarvo doctor`. Gdy coś nie działa: powrót do poprzedniego `current.json`.
6. Pracownicy kanbana kończą pracę na starej wersji. Starą usuwamy, gdy nic z niej nie działa (skan psutil).
7. Nadzorca na końcu uruchamia się ponownie z nowej wersji.

**jarvo doctor** sprawdza: healthchecki z toolbox.yaml (argv, w środowisku bramy), sumy zainstalowanych narzędzi, porty 9119, 9120, 9122 i 8642 (z nazwą programu, który trzyma port), commit Hermesa wobec pinu, SQLite ≥3.51.3 i FTS5 z remove_diacritics, Git Bash, wolny dysk. Na Windows dodatkowo: zamknięcie DLL (importy PE w drzewie Jarva), stan Smart App Control, strona kodowa, krótkie nazwy 8.3, LongPathsEnabled, OneDrive. Na macOS: TCC i Gatekeeper. Na Linuksie: user bus, linger, AppArmor. Na końcu skarbiec, rutyny i Telegram (K08) oraz konkurencyjne autostarty (c2). Ma tryb `--json` dla CI.

**jarvo status** pokazuje: PID-y i stan bramy, panelu i Komputera (z nadzorcy, bo WMIC już nie ma), wersje z locka, autostart, rutyny (włączone czy wstrzymane), Telegram, porty i ostatnią aktualizację.

**jarvo panel** startuje panel, jeśli nie działa, i otwiera http://127.0.0.1:9119/jarvo (adres 127.0.0.1, nie localhost). Na loopback nie ma hasła ani klucza. W trybie LAN (Tailscale, telefon) działa bramka z hasłem i klucz jednorazowy jako dostawca Jarva.

**jarvo uninstall**:
1. Stop nadzorcy i wszystkich procesów Jarva.
2. Reset TCC dla CuaDriver.app (jeśli był K6), zanim zniknie plik aplikacji.
3. Usunięcie autostartu, wpisów PATH, bloku w rc, skrótów i wpisu w „Aplikacje” (`HKCU\...\Uninstall\Jarvo`).
4. Cofnięcie dziennika `<stan>\zmiany-hosta.jsonl` od końca, tylko tam, gdzie nadal jest nasza wartość.
5. Usunięcie `<program>`, `<root>\build`, cache i logów. Na Windows z kopii w %TEMP%, a zablokowane .exe przez zmianę nazwy.
6. Dane (`<dane>`) tylko z `--all` i po pytaniu.
7. Starą instalację Docker/WSL sprzątamy osobnym pytaniem (f).
8. Na końcu skan śladów i raport tego, co zostaje celowo (np. reguły zapory, które wymagają admina).

## (d) Pozwolenia jak w Claude Code

**Co ma Hermes.** `approvals.mode` ma wartości manual, smart i off, do tego YOLO (`--yolo`, `/yolo`, HERMES_YOLO_MODE). Ale manual pyta tylko o polecenia pasujące do wzorców niebezpiecznych, a zapisów plików (write_file, patch) Hermes nie zatwierdza wcale (security.md:352-355). smart też ocenia tylko polecenia niebezpieczne. off wyłącza zgody na każdej powierzchni, także w kanbanie i cronie, i przestawia computer_use w tryb bez ograniczeń; validate.py:273-274 słusznie tego zabrania. Tryby podobne do Claude Code Hermes ma tylko w ACP (acp_adapter/server.py:240-251), nie w CLI, TUI ani bramie. Dlatego mapowanie „pytaj = manual, projekt = smart, pełny = off” odpada.

**Mechanizm Jarva: wtyczka z hakiem `pre_tool_call`.** Hak może zwrócić `{"action": "approve", "message": ..., "rule_key": ...}`. Taka prośba trafia do tej samej bramki co polecenia niebezpieczne: raz, na sesję, zawsze, odmowa. Bramka działa w CLI i TUI, w Telegramie (`/approve`) i w HQ przez /v1/runs (hermes_cli/plugins.py:1854-1974, tools/approval.py:951-1021). Jarvo używa już tego haka w strażniku jarvo-wiedza (wiedza/plugin/__init__.py:667-757).

| Tryb | Co robi hak | Co zostaje zawsze |
|---|---|---|
| **pytaj** | zwraca `approve` dla write_file, patch (także V4A z nagłówkami `*** Update/Add/Delete File`), execute_code, process_manage, cronjob_manage i terminala spoza listy poleceń tylko do odczytu; polecenia, które Hermes sam uzna za niebezpieczne, zostawia jego bramce (żeby nie pytać dwa razy) | twarde blokady, approvals.deny, zgoda na AGENTS.md, CLAUDE.md i SOUL.md, odrzucenie zapisu config.yaml |
| **projekt** (domyślny dla właściciela) | jak „pytaj”, ale bez pytania przepuszcza zapisy i proste polecenia plikowe (mkdir, touch, cp, mv, rm, rmdir, sed -i), gdy rzeczywista ścieżka leży w folderze projektu (TERMINAL_CWD = katalog startu czatu) albo w katalogu roboczym; ścieżki `/c/...` zamienia na `C:\...`, porównuje bez wielkości liter na Windows i macOS; poza folderem zwraca `approve` | jak wyżej, plus zawsze pyta przy: .git, .vscode, .idea, .claude, .gitconfig, .bashrc, .zshrc, .npmrc, .mcp.json, `<dane>` |
| **pełny** | proces czatu startuje z `--yolo` albo właściciel wpisuje `/yolo`; YOLO sam zatwierdza prośby wtyczki | to samo co wyżej; nigdy w config.yaml; nigdy dla jarvo-operator |

Szczegóły:
- **Przełączanie.** `jarvo chat --tryb pytaj/projekt/pelny` i `/tryb ...` w sesji (`ctx.register_command`). Stan trzymamy w pliku wtyczki per profil, nie w approvals.mode, bo merge_host_config.py nadpisuje approvals przy wdrożeniu.
- **Klucz reguły.** Odpowiedź „zawsze” zapisuje `plugin_rule:<rule_key>` w command_allowlist i ta reguła działa potem wszędzie, także bez człowieka. Dlatego rule_key musi być wąski: narzędzie, odcisk folderu projektu i skrót polecenia.
- **Bez człowieka** (pracownik kanbana, cron, `-q`, podagent delegate_task) wtyczka nigdy nie zwraca `approve`, bo Hermes od razu odpowiada BLOCKED. Rozpoznaje to po HERMES_KANBAN_TASK, HERMES_SINGLE_QUERY_SESSION, HERMES_CRON_SESSION i `delegation_context`. Zapis w HERMES_KANBAN_WORKSPACE, skarbcu i misjach przepuszcza. Poza nimi zwraca własny `block` z poleceniem `kanban_block(kind="needs_input")`. Komunikat BLOCKED Hermesa podsuwa modelowi `single_query_mode: approve`; tego nie włączamy.
- **Błąd we wtyczce** kończy się blokadą (Hermes blokuje przy wyjątku). Nie kopiujemy reguły „przy błędzie przepuść” ze strażnika wiedzy.
- **approvals.mode profilu czatu:** manual (jedno pytanie, ale zmienia też HQ i Telegram) albo smart (czasem dwa pytania). Decyzja I08.
- **HQ.** Do listy ryzyk (przebiegi.py:140-147, 15-os.js) dochodzi zapis pliku i wzorce Windows.

Warstwy, które zastępują kontener (bez nich tryby nic nie znaczą):
- `terminal.home_mode: profile` i `auto_source_bashrc: false` (H24). Na Windows plik `shell_init_files` Jarva z USERPROFILE, APPDATA, LOCALAPPDATA i XDG_CONFIG_HOME oraz GH_CONFIG_DIR, CODEX_HOME i NPM_CONFIG_USERCONFIG dla floty. Klucze ssh i logowanie gh tylko za zgodą.
- `HERMES_WRITE_SAFE_ROOT=<dane>` (w trybie „projekt” także folder projektu).
- Zakazy generowane per system (F15).
- `security.tirith_enabled: false`, `security.allow_lazy_installs: false`, `auth.adopt_external_logins: false`.
- Kwarantanna paczek (H25).
- Panel i serwery HQ tylko na 127.0.0.1.
- Profil przeglądarki Jarva w `<dane>`, żeby chroniły go narzędzia plików (terminal i tak go przeczyta).

Uczciwa granica: terminal agenta działa z prawami właściciela i może przeczytać wszystko, co właściciel. Zgody to kontrola, nie izolacja. Pełną izolację da tylko osobne konto systemowe dla bramy (decyzja I09; na Linuksie i macOS realne, na Windows drogie i niesprawdzone).

Testy (etap E4): każdy tryb na atrapie modelu, zgoda i odmowa, zapis w folderze i poza nim, karta kanbana, cron, delegate_task. Kryterium: w logach pracowników nie ma „single-query mode (-q) runs without a user present”. Wszystko to jest dziś analizą kodu; działania na żywo nikt nie sprawdził.

## (e) Zgodność skilli i skryptów floty (bash a Windows)

**Fakty.**
- Hermes na Windows wykonuje każde polecenie terminala przez Git Bash (`bash.exe -c`, tools/environments/local.py:936-956). Ustawia MSYS_NO_PATHCONV=1, więc /tmp i /opt trafiają do programów natywnych bez zamiany. Model dostaje instrukcję: składnia POSIX, programom natywnym ścieżki `C:/...`, bez /tmp (agent/prompt_builder.py:877-890). Składnia basha w skillach więc działa. Psują się ścieżki, interpreter i brakujące programy.
- Git Bash ma sed, gawk, grep, find, curl, perl, tar, xz, unzip, timeout, sha256sum, realpath, diff i patch. Nie ma jq, flock, rsync, zip, make, bc, setsid ani Pythona; `python3` w PATH to alias Sklepu.
- macOS ma /bin/bash 3.2 (bez `declare -A`, mapfile, `${x,,}`), a /usr/bin/python3 to zaślepka narzędzi Xcode.
- Liczby z repo (grep 2026-10-24): 53 ze 106 SKILL.md wołają `python3`, 14 SKILL.md ma ścieżki /opt, 171 plików poza docs/ i tests/ zawiera /opt, 95 wpisów healthcheck w 10 plikach toolbox.yaml, 2 skrypty .sh w profiles/ i shared/ (audit.sh, brand_extract.sh), 22 wywołania `eval "$(... env ...)"` w skillach Wideografa i Studia.
- Co już działa natywnie: testy skryptów pięciu profili (flota cz. 1) na tym Windows 11 z Pythonem 3.12 dają 116 OK i 4 błędy, wszystkie przez separator „\” w wynikach. Testy skarbca: 32–33 z 34.

**Podejście.**
1. **Jeden interpreter.** W SKILL.md token `@@PY@@` (pełna ścieżka Pythona z venvu narzędzi, w cudzysłowie, z „/”). Do tego shim `python3` w `<program>\bin-floty` (skrypt sh dla Git Bash i python3.cmd/exe dla CreateProcess), dopisany tylko do PATH procesów floty, nie do PATH właściciela. Agent i tak sam dopisuje `python3`, więc potrzebne są oba.
2. **Ścieżki jako tokeny build.py:** `@@DATA_DIR@@`, `@@REPO_DIR@@`, `@@KNOWLEDGE_DIR@@`, `@@MISSIONS_DIR@@`, `@@WORKSPACES_DIR@@`, `@@INBOX_DIR@@`, `@@TOOLS_DIR@@`. Zawsze przez as_posix() i w cudzysłowie, bo spacja w nazwie użytkownika rozbija niecytowane polecenie. `"$HERMES_HOME"` zawsze w cudzysłowie; validate.py to sprawdza.
3. **Przenośne moduły w fleetlib**, używane przez wszystkie skrypty: jarvo_paths (katalogi), zamek (msvcrt albo fcntl), zapisz_atomowo (ponawianie), proc (subprocess w wątku, CREATE_NO_WINDOW, `encoding="utf-8"`), uruchom (shutil.which z .cmd i .exe, ostrożne cytowanie dla cmd.exe), psutil zamiast /proc, Path.as_uri() dla SQLite i modułów ES, getpass zamiast os.getuid, `subprocess.run` + `sys.exit` zamiast os.execv, aliasy serwera HTTP albo junction zamiast symlinków, bez preexec_fn.
4. **Bash znika ze skryptów floty.** audit.sh i brand_extract.sh przechodzą na Pythona. To samo healthcheck.sh, wiedza-kompiluj.sh, install-fleet.sh i jarvo-e2e.sh. Nakładki z infra/bin stają się console_scripts. Reguła w validate.py: żadnych nowych .sh w profiles/ i shared/.
5. **Healthchecki** w toolbox.yaml jako listy argv z miejscami na ścieżki ({python}, {repo}, {narzedzia}). Uruchamia je runner w Pythonie z limitem czasu, w środowisku bramy (`jarvo doctor`).
6. **Komendy w skillach:** wyniki w out/ w katalogu roboczym zamiast /tmp; `narzedzia.py uruchom X -- <polecenie>` zamiast `eval "$(... env ...)"`; `hyperframes` z node_modules/.bin zamiast `npx hyperframes`; w bashu `pwd -W` albo `cygpath -m`, gdy ścieżka idzie do programu natywnego.
7. **Skille bez portu** dostają `platforms: [linux, macos]` w nagłówku SKILL.md; Hermes filtruje skille po platformie. Skill Hermesa searxng-search już ma takie ograniczenie, więc na Windows zastępuje go duckduckgo-search.
8. **bash 3.2 na macOS:** w skillach tylko proste konstrukcje; wszystko, co potrzebuje bash 4, idzie do Pythona.
9. **Końce linii:** `.gitattributes` z `* text=auto eol=lf`, `*.ps1`, `*.cmd` i `*.bat` z `eol=crlf`, binaria jako `binary`. Dziś core.autocrlf=true daje CRLF w 987 plikach na Windows: inne sumy plików i błędy `$'\r'` w bashu.
10. **Ścieżki w wiadomościach i UI:** HQ rozpoznaje ścieżki od faktycznego korzenia (litera dysku, spacje) i zachowuje alias /opt/data dla starych rozmów.

**Kolejność portowania**, według tego, co blokuje pierwszą sesję: Web (audyt), Sherlock (wyszukiwarka), Łowca, potem Wideograf (render), Ręka, Studio, Mobile, Ads, Operator.

**Testy.** pytest w macierzy z markerami windows_only, posix_only i linux_only. Job pada, gdy marker niczego nie wybrał (kod 5), żeby zielony wynik nie był pusty. Na każdej nodze testy z katalogiem danych ze spacją i polskimi znakami (`C:\Users\Michał Żółć\...`).

## (f) Migracja ze starej instalacji Docker

### f1. Zasady
- Nic nie kasujemy bez zgody. Stara instalacja zostaje do potwierdzenia, że natywna działa.
- Najpierw wyłączamy starą flotę, potem kopiujemy, potem startujemy nową. Nigdy obie naraz: jeden token Telegrama to jedna brama (inaczej 409 i podwójne rutyny), a token odświeżania OpenAI jest jednorazowy (ponowne użycie unieważnia całą rodzinę tokenów i wylogowuje obie kopie).
- Kopia musi być spójna: bazy SQLite razem z plikami -wal.
- Próba zawsze najpierw na kopii bez sekretów.
- Nie używamy starego deinstalatora install.ps1. Z JARVO_UNINSTALL=1 kasuje cały `%LOCALAPPDATA%\Jarvo`, a z JARVO_DISTRO=Ubuntu wyrejestrowałby cały system Ubuntu właściciela.
- Nie używamy `hermes backup`: pomija katalogi .git, więc skarbiec straciłby historię. Do tego `hermes import` sam stawia bramę.

### f2. Komputer właściciela: Windows 11 z WSL (stan z 2026-10-24, tylko odczyt)
- **Dane są tylko w dystrybucji Ubuntu**, w `~/jarvo-local`: data/hermes, compose/.env, compose/jarvo.env, secrets/
  i build/. Właściwe dane to ok. 0,1 GB. Reszta to cache npm, binarki w profilach i leniwe paczki, których nie
  przenosimy. build/ odtwarza się sam, więc go nie kopiujemy.
  - Skarbiec ma katalog .git: historia notatek musi przejść.
  - Są dwa auth.json: główny i w profilu jarvo (ten ma pierwszeństwo).
  - rozmowy.db jest prawie cała w pliku rozmowy.db-wal. Kopia bez -wal zgubiłaby ostatnie rozmowy.
- **Kopia stosu w Docker Desktop jest pusta.** Kontener jarvo-hermes nigdy tam nie wystartował, a montowania wskazują
  na katalogi Ubuntu (przy zatrzymanym Ubuntu to pusty tmpfs). Nie startujemy go i nie kopiujemy z niego.
- **Dystrybucja Jarvo** to przerwana druga instalacja: jest w niej tylko install.log i Docker. Nie ma czego przenosić.
- **Dwa silniki Dockera:** Docker Desktop (Windows) i Docker Engine w Ubuntu (docker.service, docker.socket i containerd
  są włączone). Flota działa w tym drugim.
- **Każde `wsl -d Ubuntu` budzi starą flotę**, bo włączone są docker.service, `restart: unless-stopped`, linger
  i jarvo-updater. Ubuntu jest dystrybucją domyślną, więc budzi ją też samo `wsl`, karta Ubuntu w terminalu i VS Code.
- Na dysku systemowym zostało kilka GB, na drugim dysku jest dużo miejsca. Eksport i kopię robimy na drugim dysku.
- Port 6379 zajmuje inny program właściciela. Po usunięciu Valkey nie ma to znaczenia.

### f3. Kolejność na Windows (`jarvo migruj`)
1. **Wykrycie:** Startup\Jarvo.vbs, `%LOCALAPPDATA%\Jarvo\bin\jarvo.cmd` wołający wsl.exe, dystrybucje z HKCU Lxss, plik `~/jarvo-local/compose/.env` w każdej dystrybucji, kontenery jarvo-* w Docker Desktop. Raport dla właściciela i pytanie o zgodę.
2. **Rozbrojenie po stronie Windows (bez startu WSL):**
   - W1: przenieść Jarvo.vbs do kopii zapasowej, zabić proces `sleep infinity`, jeśli działa.
   - W2: podmienić jarvo.cmd na natywny (ten sam wpis w PATH).
   - W3: `docker compose -p jarvo down` w Docker Desktop (kontenery z unless-stopped wstałyby z demonem). Sam Docker Desktop zostaje, bo właściciel ma w nim inne projekty.
   - W4: sprawdzić, że nie ma RunOnce ani .wslconfig od Jarva.
3. **Rozbrojenie w Ubuntu (jeden start, od razu jako root):**
   - U1: `docker stop jarvo-hermes`.
   - U2: `systemctl --user -M <użytkownik>@ disable --now jarvo-updater` i usunięcie jednostki; `loginctl disable-linger <użytkownik>`, jeśli nic innego go nie potrzebuje. Na prośbę z panelu pomocnik uruchomiłby deploy.sh, czyli `compose up`.
   - U3: `docker compose down`.
   - U4: `rm /usr/local/bin/jarvo`.
   - U5: za zgodą `systemctl disable --now docker.service docker.socket containerd.service`. Samo docker.service nie wystarczy, bo docker.socket uruchomi demona przy pierwszym poleceniu.
   - U6: `wsl --terminate Ubuntu`.
4. **Klucz prywatnego repo** (jeśli jest): odczyt nagłówka z `~/jarvo/.git/config` przez `wsl.exe -e git config --get`, sprawdzenie przez API, zapis do Menedżera poświadczeń. Niczego nie wypisujemy.
5. **Kopia:** `wsl --export Ubuntu -` strumieniem do Pythona (`tarfile` w trybie `r|`) z filtrem home/<użytkownik>/jarvo-local/{data/hermes, compose, secrets}, zapis na dysk z miejscem (np. D:) z sumą sha256. To jest też kopia do wycofania. Eksport nie uruchamia systemd. Nie przez potok PowerShella 5.1, bo zamienia dane binarne na tekst.
6. **Filtr kopii.** Pomijamy: `gateway_state.json`, `gateway.pid`, `cron.pid`, `gateway.lock`, `processes.json`, `*.lock`, `lazy-packages`, `bin/`, `node_modules`, venvy, `__pycache__`, `.npm`, `.cache` (poza obrazami, audio, wideo, dokumentami, zrzutami i cytatami), `runtime/`, `sandboxes/`, `jarvo/narzedzia`, `jarvo/state/{update,praca,preview*}.json`, `plugins/jarvo-*`, `skins/`, `build/`. Zachowujemy: `.git`, `*.db` razem z `*-wal`, `auth.json`, `.env`, `pairing/`, `cron/`, `memories/`, `sessions/`, `home/`. Dowiązania bezwzględne zapisujemy i odtwarzamy natywnie jako junction. Nazwy niedozwolone w NTFS albo kolizje wielkości liter: raport i stop.
7. **Próba na kopii bez sekretów** (bez auth.json, .env i secrets/) w `D:\JarvoMigracja\proba`: skrypt przepisania i tylko polecenia do odczytu (`hermes sessions list`, `kanban list`, `cron list`, `profile list`). Porównanie liczby sesji, wiadomości, kart i wpisów przed i po. Potem usunięcie próby.
8. **Import i przepisanie ścieżek** (najdłuższy prefiks najpierw, tylko na granicy ścieżki): /opt/data i ~/jarvo-local/data/hermes → `<dane>`, /opt/jarvo/build → build, /opt/jarvo/repo i ~/jarvo → repo, /opt/jarvo/bin, /opt/jarvo/node, /opt/hermes → katalogi natywne.
   - SQLite (w transakcji, z integrity_check przed i po, potem `wal_checkpoint(TRUNCATE)`): state.db (sessions.cwd, git_repo_root; tabeli messages nie ruszamy, bo ma wyzwalacze FTS), kanban.db (tasks.workspace_path, task_attachments.stored_path; na Windows ścieżka /opt/data nie jest bezwzględna i resolve_workspace rzuca błąd), projects.db (primary_path, path, root), rozmowy.db (tylko pola JSON z załącznikami).
   - Pliki: distribution.yaml (`source:`), cron/jobs.json (`workdir`), board.json (`default_workdir`), wartości /opt/... w .env (np. IMPECCABLE_HOME), bez wypisywania.
   - config.yaml, SOUL i skille odtwarza build. Linie MEDIA:/opt/data/... w historii zostają, bo HQ ma alias.
   - Raport resztek: liczba wystąpień „/opt/” w kolumnach tekstowych i plikach (same liczby).
   - Sekrety z `secrets/*.env` i `compose/jarvo.env` przez merge_env do `<dane>\jarvo\konfig`; z `compose/.env` tylko `DASHBOARD_*`, jeśli potrzebny tryb LAN.
   - Pliki z uid 10000 dostają właściciela i ACL użytkownika.
9. **Unieszkodliwienie starych logowań:** drugi start Ubuntu (flota już nie wstanie) i zmiana nazw `auth.json` oraz `.env` (główne i w `profiles/*`) na `*.przeniesione-<data>`.
10. **Kontrola przed startem:** `wsl -l --running` bez Ubuntu i Jarvo; porty 9119, 9120, 9122 i 8642 wolne; w Docker Desktop brak kontenerów jarvo-*.
11. **Pierwszy start natywny:** `jarvo serwis`, `hermes auth status` (tylko odczyt), pierwsze zapytanie do modelu, `jarvo doctor`, rozmowa ze starej historii widoczna w HQ, notatka ze skarbca widoczna. Rutyny zostają wstrzymane do próbnej wiadomości na Telegram.
12. **Wycofanie:** przywrócenie nazw `*.przeniesione`, `jarvo up` w starym systemie. Nigdy równolegle z wersją natywną.
13. **Sprzątanie, tylko za zgodą i po okresie przejściowym:** `wsl --unregister Jarvo`; projekt jarvo i obrazy w Docker Desktop (jarvo-hermes:local 9,78 GB, src-b4b5cfed5bf6 9,78 GB, tars-hermes:local 6,29 GB); obrazy w Docker Engine w Ubuntu (9,6 GB); stare dane w Ubuntu. Dysk ext4.vhdx sam się nie zmniejszy. Repo ~/jarvo i ~/TARS to osobna decyzja.

### f4. Inne systemy
- **macOS (Colima albo Docker Desktop):** dane są w wolumenie jarvo-hermes-data w maszynie wirtualnej. Docker musi działać raz: `docker cp jarvo-hermes:/opt/data -` (działa też na zatrzymanym kontenerze) do Pythona. Potem `compose down`, wyłączenie LaunchAgenta pl.jarvo.updater i autostartu Colimy. `colima delete --data` tylko za zgodą i tylko przy znaczniku `~/jarvo-local/.colima`. Bez `--data` Colima 0.9+ zostawia dysk z obrazami (ok. 10 GB). Ścieżka niesprawdzona na prawdziwym Macu.
- **Linux (komputer):** ~/jarvo-local/data/hermes należy do uid 10000. Kopia przez `sudo tar` albo `docker cp`, potem chown na użytkownika. `docker compose down`, `systemctl --user disable --now jarvo-updater`, decyzja o linger. Na podstawie install.log, zanim go usuniemy: grupa docker, repo Dockera w apt (docker.list, docker.asc), iptables-legacy, pliki jarvo-android.conf.
- **VPS:** zostaje na Dockerze do etapu „VPS natywnie” (j). Dane w /srv/jarvo/data/hermes.

### f5. Test migracji w CI
- Zamrozić ostatnią wersję z Dockerem: tag git `docker-ostatnia` i chroniony digest obrazu w GHCR. Repo nie ma dziś żadnych tagów.
- ubuntu-24.04 (ma Dockera): stary install.sh z tagu, potem zasiew z atrapą modelu (rozmowa, notatka w skarbcu, rutyna, karta kanbana z workspace_path /opt/data/…, fałszywy token Telegrama, rozmowy.db zapisana tylko w WAL, auth.json w profilu, dowiązanie bezwzględne, .git w skarbcu). Manifest przed. Nowy instalator migruje. Manifest po musi się zgadzać, `jarvo doctor` zielony, E2E widzi starą rozmowę i notatkę, stare kontenery stoją, kopia zostaje. Drugi przebieg niczego nie zmienia.
- Warianty: wolumeny (jak na macOS), stare nazwy TARS (~/tars-local), przerwanie `kill -9` w połowie i wznowienie.
- Windows: migawka danych z joba Linuksa jako artefakt, import jako dystrybucja WSL na samodzielnym runnerze Windows 11. Na runnerach GitHub WSL2 z Dockerem: niesprawdzone.

## (g) Etapy wdrożenia

**Stan (2026-10-24):** E0 🟡 (adres Matcha ✅, `.gitattributes` ✅, reszta ⬜); E1 🟡 w toku (znaczniki systemów i atrapy
w testach, bash tylko z Git Bash ✅); E2 🟡 (manifest `vendor/natywne.yaml`, pobieracz `jarvo/pobieracz.py`: uv 0.12.13
i Python 3.13.17 / 3.12.15 sprawdzone na Windows 11 ✅; pozostałe narzędzia ⬜); E3–E14 ⬜.

Każdy etap to mały, osobny commit (albo krótka seria), wypchnięty od razu, z dokumentami i skarbcem w tym samym commicie (zasady CLAUDE.md). Nowa ścieżka żyje za flagą `JARVO_NATYWNIE=1`, aż do etapu E13. Do tego czasu ludzie dostają dzisiejszą instalację.

**Runnery CI.** W64 = windows-2025 (PowerShell 5.1 i 7), WARM = windows-11-arm, MARM = macos-15 (arm64), L64 = ubuntu-24.04 (+ kontener debian:13 jako czysty system), LARM = ubuntu-24.04-arm.

**Kiedy co biegnie.** Szybki CI na każdy push i PR: L64 pełny pytest i validate, W64 i MARM testy jednostkowe z markerami. Pełna macierz (5 nóg, instalacja od zera, E2E) przy `workflow_dispatch`, przy pushu do main w plikach instalatora i manifestu, nocą i przy tagach `v*`. Repo jest publiczne, więc standardowe runnery są darmowe; w prywatnym ostatnie 4 tygodnie kosztowałyby ok. 3316 min, czyli więcej niż plan Free (2000) i Pro (3000).

### E0. Pilne poprawki w dzisiejszej instalacji (bez natywności)
- **Co:** każda pozycja osobnym commitem.
  1. Adres Matcha → `machinekind/Matcha-TTS-PL@93744740` (te same sumy) w infra/Dockerfile:298 i vendor/zrodla.yaml (V02). Dziś każda budowa obrazu pada na tym kroku.
  2. Usunięcie Valkey z compose (U02) i z dokumentów.
  3. `security.tirith_enabled: false` we wszystkich profilach (H23).
  4. Przypięcie Parakeet i Silero (rewizja + sumy) w jarvo-stt (V05) i commitu Paradee zamiast tagu (V03).
  5. `.gitattributes` (T04).
  6. Lock z sumami dla requirements-tools.txt i package-lock.json dla infra/node (P01, P02).
  7. Rozjazdy dokumentów (R21) i wyjaśnienie, który commit Hermesa jest „przejrzany” w zrodla.yaml (7157422… a f97608f).
  8. Adresy `https://jarvo.pl/install.sh` i `install.ps1` zwracają dziś 404, choć strona działa (sprawdzone,
     sekcja (l)). Na serwerze leży stara wersja strony z 2026-09-29: nie ma przekierowań ani nagłówków z
     `site/.htaccess`, w którym przekierowanie na raw.githubusercontent.com już jest. Naprawa: właściciel wgrywa stronę
     przez `scripts/deploy-site.sh` (hasło FTP zostaje u niego). Do tego czasu działa adres raw.githubusercontent.com
     z README (repo jest publiczne). Prywatna kopia repo i tak potrzebuje bootstrapu w publicznym miejscu, bo `irm | iex`
     nie doda klucza.
- **CI:** jak dziś (ci.yml na Linuksie, obraz.yml na amd64 i arm64) + budowa obrazu od zera.
- **Gotowe, gdy:** obraz buduje się od zera, `jarvo-tts --sprawdz` w kontenerze działa dla trzech głosów, healthchecki zielone.

### E1. Przenośny kod (bez zmiany zachowania na Linuksie)
- **Co:** moduły fleetlib (jarvo_paths, zamek, zapisz_atomowo, proc, uruchom, ACL) i ich użycie wszędzie, gdzie dziś są fcntl, AF_UNIX, preexec_fn, os.getuid, os.execv, symlinki, `text=True` bez kodowania, sqlite przez f-string, chmod jako ochrona. Dotyczy: hq_core, plugin_api, glos, edytor, wideo_lib, html_wideo, jarvo-stt, ostrozna, schemat, wiedza, kompilacja, skrypty pięciu pierwszych profili. tzdata do venvów. Testy node przez pliki zamiast `node -e`.
- **CI:** szybki job W64, MARM, L64: pytest z markerami i strażą na kod 5; na L64 bramka EncodingWarning (`-X warn_default_encoding -W error::EncodingWarning`).
- **Gotowe, gdy:** `python -m pytest` zbiera się bez błędów na trzech systemach (dziś na Windows padają 3 moduły, na macOS 1) i jest zielony; na Linuksie nic się nie zmienia.

### E2. Manifest i pobieracz
- **Co:** pola `wydanie` i `pliki` w vendor/zrodla.yaml, generator `natywne.lock.json`, nowe reguły validate.py, `zrodla.py sumy` (strumieniowo, zip, tryb wydań), `jarvo narzedzia instaluj` (stdlib, pasek, wznawianie, suma przed rozpakowaniem). Pierwsze wpisy: uv, lista PBS, Node, PortableGit, ripgrep.
- **CI:** 5 nóg: pobranie, kontrola sum i `--version` każdego narzędzia; na W64 skan Defenderem każdej binarki; test „zmieniony bajt zatrzymuje instalację”.
- **Gotowe, gdy:** każdy wpis ma sumę zgodną z plikiem, a brak platformy jest jawnym `brak:`.

### E3. Hermes natywnie, nadzorca i panel podstawowy
- **Co:** nowe install.ps1 i install.sh (za flagą), checkout f97608f i `uv sync --locked`, katalogi z (c1), HERMES_GATEWAY_LOCK_DIR, `jarvo serwis` z autostartem per system, web_dist z CI (S12), runtime VC++ na Windows (B11), `jarvo status`, `jarvo panel`, `jarvo doctor` w wersji podstawowej, klucze API (H05).
- **CI:** 5 nóg, instalacja od zera: http://127.0.0.1:9119/jarvo odpowiada; `hermes gateway status`; zabicie bramy → nadzorca ją podnosi; kod 78 → postój; na W64 zadanie Harmonogramu ma baterie wyłączone, PT0S i stan Running; na MARM LaunchAgent, na L64 systemd --user; drugi przebieg instalatora niczego nie zmienia; na W64 skan zamknięcia DLL.
- **Gotowe, gdy:** świeży runner ma działający panel po jednym poleceniu.

### E4. Flota natywnie, czat i zgody
- **Co:** build.py z tokenami i wartościami per system (S06), install_fleet.py (S07), wtyczki jako kopie albo junction (H27), healthchecki argv i `jarvo doctor` (S02), wtyczka zgód z trzema trybami (sekcja d), home_mode, zakazy per system (F15), kwarantanna paczek (H25), shim python3 (F12), Git Bash (B04).
- **CI:** atrapa modelu (scripts/atrapa_modelu.py): `jarvo chat` w trzech trybach (zgoda, odmowa, zapis w folderze i poza nim); karta kanbana do agenta, która przeżywa restart bramy; jednorazowa rutyna; delegate_task. W logach pracowników nie może być „runs without a user present”. 5 nóg.
- **Gotowe, gdy:** 10 agentów zainstalowanych, healthchecki zielone (poza jawnymi brakami platform).

### E5. Przeglądarki i wyszukiwarka (potrzebne do pierwszej sesji)
- **Co:** C01–C07, nakładka agent-browsera w Pythonie, audit.py i brand_extract.py (F02), wyszukiwarka z U01 i search_fanout.py (F03), har.cjs i Łowca (F04), MCP inspo (P06), Lighthouse.
- **CI:** browser_* na `chrome` (W) i `lightpanda` (mac, Linux); audyt strony testowej; Camoufox startuje (pobranie leniwe); inspo-mcp odpowiada na JSON-RPC; 5 nóg.
- **Gotowe, gdy:** Web, Sherlock i Łowca wykonują swoje karty z pierwszej sesji na atrapie modelu.

### E6. Panel pełny i pierwsze uruchomienie
- **Co:** front w trybie loopback (W11), podprocesy w wątkach (W06), :9120 na 127.0.0.1 (W10), ścieżki w UI (W12), „Pokaż w folderze” (W13), dziennik (W14), mózg kodem urządzenia i kluczem API (H15), pierwsze spotkanie, pierwsza sesja.
- **CI:** Playwright `jarvo e2e etap1..3` na W64, MARM i L64 (WARM i LARM nocą); zrzuty jasny i ciemny, 1440 i 390 px jako artefakty po skanie sekretów; atrapa serwera OAuth.
- **Uwaga:** pierwsze spotkanie mówi głosem przeglądarki, dopóki E9 nie dostarczy lokalnego lektora (ten zapas już jest w HQ: odpowiedź 503 `brak_glosu`).
- **Gotowe, gdy:** pierwsza sesja przechodzi na atrapie modelu; przed wydaniem ręczna próba z prawdziwym kontem ChatGPT.

### E7. Skarbiec, rutyny i Telegram
- **Co:** K01–K08, ścieżki skryptów rutyn (H06), konfiguracja Telegrama (H11), schemat (K05).
- **CI:** testy skarbca na 3 systemach (polskie znaki, CRLF, blokady, plik otwarty przez drugi proces); kompilacja na atrapie; rutyna patrol uruchomiona przez cron. Telegram: atrapa API (czy da się bez prawdziwego bota, niesprawdzone) i próba ręczna.
- **Gotowe, gdy:** lint bez błędów, rutyny działają, bot odpowiada (ręcznie).

### E8. Dokumenty i OCR
- **Co:** E01–E07, E09, E10; pypdfium2 i pikepdf zamiast Ghostscriptu; pixi dla Tesseracta; LibreOffice przy pierwszym użyciu.
- **CI:** test_konwertuj i test_ocr z prawdziwymi binarkami na 5 nogach; plik „faktura_październik.png” w katalogu „Michał Żółć”.
- **Gotowe, gdy:** konwerter i OCR działają na trzech systemach.

### E9. Media, głos, edytor
- **Co:** M01–M12, V01–V11, fonty (M03), runtime VC++ (B11), zasada ścieżek ASCII (B13), HyperFrames, edytor HQ.
- **CI:** krótki film (render, napisy ass z fontsdir), `jarvo-tts --sprawdz` dla trzech głosów, STT na nagraniu z polską nazwą pliku, eksport z edytora; na W64 skan zamknięcia DLL; 5 nóg.
- **Gotowe, gdy:** skill krotki-film i edytor działają na trzech systemach.

### E10. Komputer Jarva (przeglądarka Jarva)
- **Co:** J01–J13, J16, J17.
- **CI:** natywny komputer_test.py (adaptacja 79 sprawdzeń) na W64, MARM i L64; samotest proxy (169.254.169.254, 127.0.0.1:9119 i brama LAN odrzucone).
- **Gotowe, gdy:** Operator wypełnia formularz testowy, a wrażliwe pola i przyciski kończą się „oddaj”.

### E11. Mobile, 3D, ManimGX i dodatki
- **Co:** F08 (resolver npx, adb, scrcpy), E11, M04–M08, E13, U04, U05.
- **CI:** testy jednostkowe, `adb --version`, model CAD na próbę; ManimGX render na L64 (lavapipe), na W i mac niesprawdzone (GPU).
- **Gotowe, gdy:** Twórca aplikacji robi podgląd na telefonie właściciela (ręcznie).

### E12. Migracja
- **Co:** `jarvo migruj` z (f), tag `docker-ostatnia` i chroniony obraz.
- **CI:** test z (f5) na L64; Windows na samodzielnym runnerze z WSL.
- **Gotowe, gdy:** manifest przed i po się zgadza, a drugi przebieg niczego nie zmienia.

### E13. Przełączenie
- **Co:** install.ps1 i install.sh domyślnie natywne; CLAUDE.md i dokumenty (R01–R21); `jarvo uninstall` z dziennikiem zmian hosta; obraz już tylko dla VPS.
- **CI:** migawka systemu przed instalacją i po `uninstall --all --yes` na 5 nogach (różnica pusta poza listą wyjątków); w trakcie każde gniazdo nasłuchu tylko na 127.0.0.1 albo ::1.
- **Gotowe, gdy:** właściciel przeszedł migrację na swoim komputerze i zatwierdził sprzątanie.

### E14. Później
- Ekran właściciela (J14, J15), podpisywanie binarek dla Smart App Control (I26), VPS na natywnym Linuksie (j), emulator Androida.

### Zmiany w testach i CI

| Element | Dziś | Po zmianie | Uwagi |
|---|---|---|---|
| **T01** Szybki CI (ci.yml) | jeden job ubuntu-latest, `pip install` bez wersji, ten sam commit biegnie 2× (main i gałąź robocza) | L64 pełny + W64 i MARM jednostkowo; concurrency; push tylko na jedną gałąź + pull_request | run 40108728657: 1886 passed, 104 skipped w 340 s |
| **T02** Zależności testów | requirements-dev.txt z zakresami bez sum; ci.yml instaluje inny zestaw | `requirements-dev.lock` z `uv pip compile --universal --generate-hashes`, instalacja `--require-hashes`; dodać fastapi, httpx, tzdata, pytest-timeout | shellcheck-py nie ma kół dla linux aarch64 i win_arm64 |
| **T03** Uruchamianie Pythona i basha z testów | gołe `python3` i `bash` (32 wywołania) | sys.executable; bash z JARVO_BASH albo z `git --exec-path` | na Windows `bash` z System32 to WSL, także na runnerach |
| **T04** Końce linii i kodowanie | brak .gitattributes; 987 plików z CRLF na Windows; `text=True` bez kodowania | `.gitattributes`; PYTHONUTF8=1 w CI i w launcherach; bramka EncodingWarning | etap E0 |
| **T05** Testy node | `node -e` z 79 014 znakami (WinError 206), ESM ze str(ścieżki) | program w pliku tymczasowym; Path.as_uri() | |
| **T06** Lint powłoki | `bash -n` w validate.py i drugi raz w ci.yml | tylko dla skryptów, które zostają (install.sh, shim jarvo); shellcheck z przypiętej binarki | |
| **T07** PowerShell | testy install.ps1 na sucho wokół WSL; PSScriptAnalyzer 1.24.0 bez sumy | testy nowego install.ps1 w PS 5.1 i 7 na W64 i WARM; PSScriptAnalyzer z nupkg z sumą | |
| **T08** Testy instalatora | Docker w Dockerze (install-test.sh), macOS tylko na sucho, Windows tylko na sucho | prawdziwa instalacja od zera na 5 nogach (fazy: przygotowanie, instalacja, aktualizacja, odinstalowanie); próby JARVO_FAKE_* zostają jako jednostkowe | wzór: install-e2e*.yml Hermesa |
| **T09** Atrapy programów | pliki `#!/bin/sh` i PATH sklejany przez „:” | tests/atrapy.py (Python + .cmd, os.pathsep); w kodzie jawne ścieżki narzędzi | na Windows env nie zmienia PATH dla CreateProcess |
| **T10** Uprawnienia w testach | 26 plików sprawdza tryby 0600/0700 | wspólna funkcja ochrony + test DACL (windows_only) | |
| **T11** Symlinki w testach | 7 plików tworzy symlinki | marker `wymaga_symlinku`; nowe przypadki: C: i D:, UNC, strumienie ADS, 8.3, CON, wielkość liter | runner działa jako admin, więc nie wykryje błędów zwykłego użytkownika |
| **T12** IPC i blokady w testach | AF_UNIX i fcntl w testach | testy per system dla potoków i zamków | |
| **T13** Strefa czasowa | ZoneInfo bez tzdata na Windows | tzdata w venvie i locku testów | |
| **T14** Test aplikacji na żywo (Playwright) | tylko przez docker exec w jarvo-hermes (s6, /opt, /usr/local/bin/chromium) | `jarvo e2e <etap>` w Pythonie na instalacji natywnej | |
| **T15** Macierz runnerów | ubuntu, macos-15, macos-15-intel (na żądanie), windows-latest (na sucho) | 5 nóg z przypiętymi obrazami (bez Intela, I06); `*-latest` tylko jako noga ostrzegawcza | |
| **T16** Minuty i koszty | repo publiczne, więc 0 | pełna macierz tylko na etapach; pomiar `gh api /users/.../settings/billing/usage` wymaga zakresu `user` | |
| **T17** Akcje GitHub | tagi (checkout@v4, setup-python@v5…) | pełne SHA po przeglądzie: checkout v7.0.1, setup-python v7.1.0, setup-node v7.1.0, upload-artifact v7.0.2, download-artifact v8.0.2 | Node 20 w akcjach znika jesienią 2026 |
| **T18** Artefakty | tylko digest obrazu | zrzuty, trace Playwrighta, raport, log instalatora, `jarvo doctor --json`, zawsze (`if: always()`), retencja 14 dni, skan sekretów przed wysyłką | logi repo publicznego widzi każdy |
| **T19** Test migracji | brak | (f5) | |
| **T20** Testy kontraktu obrazu | 10 plików sprawdza treść Dockerfile i compose | testy manifestu: każde narzędzie ma wpis albo `brak:` per system; doctor w E2E | |
| **T21** Ścieżki /opt i healthchecki w kodzie testowanym | 29 stałych z /opt; regexy znają tylko /opt/data | katalog danych ze spacją i polskimi znakami na każdej nodze | |
| **T22** Piaskownica Claude Code | sandbox-up.sh: dockerd, obraz hermes-ca:test, deploy | natywna instalacja Linux w piaskownicy; certyfikat proxy przez SSL_CERT_FILE, REQUESTS_CA_BUNDLE, NODE_EXTRA_CA_CERTS i NSS | Windows i macOS testuje tylko CI albo komputer właściciela |
| **T23** Testy floty na trzech systemach | tylko ubuntu | macierz; 4 znane błędy separatora (security_check, extract, pack) do poprawy | |
| **T24** Testy, które dziś wymuszają kontener | test_installer.py:642-646 (ARG HERMES_IMAGE), test_site.py (dokładne polecenia), test_komputer_obraz.py | test jednego pinu Hermesa (tag + commit) w install.ps1, install.sh i jarvo update; obraz.yml i installer.yml wyłączamy dopiero po migracji ludzi | |

## (h) Ryzyka i blokery z planem

**Blokery twarde** (konfiguracją się ich nie obejdzie):

| Nr | Bloker | Plan |
|---|---|---|
| Z01 | Lightpanda nie ma wydania na Windows (1.0.0–1.0.2 tylko Linux i macOS) | na Windows `browser.engine: chrome` z CfT; mniej sesji naraz, bo Chromium bierze ok. 10× więcej RAM |
| Z02 | macOS Intel: Hermes v2026.9.24 ma go na liście „Unsupported”; cryptography 50 bez koła x86_64; onnxruntime od 1.24, pikepdf od 10.14 i numba od 0.63 bez kół; docling niemożliwy; buildy ffmpeg Riedla dla Intela do I 2027; runnery Intel znikają około jesieni 2027 | decyzja I06: rezygnacja; instalator na x86_64 kończy pracę z jasnym komunikatem; minimum macOS 14 |
| Z03 | Smart App Control na Windows 11 blokuje niepodpisane pliki: python.exe z PBS, trampoliny uv, cv2.pyd, ffmpeg z BtbN | teraz: doctor wykrywa SAC i mówi wprost; później podpisywanie (I26); Hermes ma ten sam problem |
| Z04 | Natywnie nie ma izolacji kontenera: terminal agenta działa z prawami właściciela | tryby zgód (d), home_mode profile, HERMES_WRITE_SAFE_ROOT, zakazy per system; pełna izolacja tylko przez osobne konto (I09); dokumenty mówią to wprost |
| Z05 | Komputer Jarva traci iptables, osobny uid, Xvnc i SO_PEERCRED | proxy filtrujące + sterownik CDP + named pipe z DACL; kontener jako opcja tylko na Linuksie i VPS (I18) |
| Z06 | SearXNG nie ruszy na Windows (import pwd), a skill searxng-search jest tylko dla Linuksa i macOS | ddgs z sumami (I14); SearXNG tylko na VPS |
| Z07 | Redroid wymaga bindera w jądrze Linuksa; ws-scrcpy wymaga kompilacji node-pty | telefon właściciela przez adb + scrcpy w oknie; emulator SDK opcjonalnie (I24) |
| Z08 | Windows ARM64: brak agent-browsera arm64, Camoufoxa arm64, pandoca arm64, cadquery-ocp i opencv win_arm64, cryptography win_arm64 | cały zestaw x64 w emulacji, tylko Windows 11 (I27); emulacja niesprawdzona |
| Z09 | Linux bez roota: Chromium potrzebuje bibliotek systemu, Camoufox GTK3, piaskownica Chromium na Ubuntu 24.04 profilu AppArmor | jedno pytanie o sudo w instalatorze; bez sudo `--no-sandbox` z ostrzeżeniem w status (I41) |
| Z10 | Chrome for Testing i Lightpanda nie publikują sha256 | sumy liczone przy przeglądzie i zapisane w manifeście; dla CfT kontrola md5 z x-goog-hash |
| Z11 | Pliki znikają u źródła: dzienne buildy BtbN po 14 dniach, exiftool.org trzyma tylko bieżącą wersję, LibreOffice zabiera stare z /stable | buildy BtbN z końca miesiąca (trzymane 2 lata), adresy SourceForge i downloadarchive, lustro tylko po decyzji o licencjach GPL (I21) |

**Ryzyka techniczne:**

| Nr | Ryzyko | Plan |
|---|---|---|
| Z12 | Na czystym Windows nie ma MSVCP140*, a importują je onnxruntime, espeak-ng i spaCy; runnery GitHub mają VC++, więc CI tego nie pokaże | kopia DLL z vc14_runtime obok bazowego python.exe (I25); test zamknięcia DLL w CI i w doctor; test w czystej maszynie wirtualnej |
| Z13 | Polskie znaki w ścieżce profilu: espeak-ng kończy proces exit(1), OpenCV nie otworzy pliku, Tesseract działa tylko przy stronie kodowej 1250 | `<program>` w ścieżce ASCII; Indra przez imdecode; Tesseract przez stdin; testy z „Michał Żółć” w CI i w maszynie wirtualnej pl-PL i en-US |
| Z14 | Błąd WAL-reset w SQLite (PBS do 20260510, wszystkie Pythony z python.org, Debian 3.46.1) | PBS 20261021 (SQLite 3.53.1) przez własną listę pobrań; bramka w instalatorze i doctor; bazy w WAL otwierane tylko na naprawionym SQLite |
| Z15 | Dashboard Hermesa na Windows działa na SelectorEventLoop, więc podprocesy asyncio rzucają NotImplementedError | proc.py w wątkach (W06, M10) |
| Z16 | fcntl, AF_UNIX, preexec_fn, os.getuid, os.execv i symlinki psują Windows w kilkunastu miejscach | moduły przenośne w E1, test zbierania pytest na trzech systemach |
| Z17 | Brama na Windows bez nadzoru awarii, brak restartu przez SIGUSR1, dashboard bez autostartu, WMIC usunięty | własny nadzorca z PID-ami (H22, c2) |
| Z18 | `hermes update` zrywa pin, a przycisk „Update now” w dashboardzie jest aktywny | nigdy nie wołamy; przycisk ukryty w powłoce; doctor porównuje commit |
| Z19 | Instalatory Hermesa pobierają bez sum; uv 0.12+ z UV_NO_CONFIG po cichu schodzi do PyPI bez sum | własny bootstrap; `uv sync --locked` bez UV_NO_CONFIG, błąd zatrzymuje instalację |
| Z20 | Dwie bramy na jednym tokenie Telegrama (409, podwójne rutyny) | `jarvo migruj` wyłącza starą flotę przed pierwszym startem (f3) |
| Z21 | Ponowne użycie tokenu odświeżania OpenAI unieważnia logowanie obu kopii, a awaria może przyjść po kilku dniach | stare auth.json dostają nową nazwę przed startem natywnym; `auth.adopt_external_logins: false` |
| Z22 | Token sesji panelu jest w index.html, a CORS dashboardu wpuszcza `localhost:*`; natywnie serwery deweloperskie agentów działają na tym samym komputerze | strony agentów tylko przez :9120 (sandbox CSP), serwery dev na 127.0.0.1, zgłoszenie do Hermesa (decyzja właściciela); test, czy strona z innego portu przeczyta token |
| Z23 | Defender oznaczył tirith v0.4.2 jako trojan | tirith wyłączony; skan Defenderem każdej przypiętej binarki w CI |
| Z24 | CRLF w klonie i kodowanie cp1250 w procesach bez trybu UTF-8 (także `python -I` ignoruje PYTHONUTF8) | .gitattributes; `-X utf8` obok `-I`; `encoding="utf-8"` w subprocess |
| Z25 | MAX_PATH 260 przy LongPathsEnabled=0 | zmierzone maks. 189 znaków dla „Michał Żółć”: na razie bez zmian; krótki korzeń; doctor ostrzega powyżej ok. 100 znaków w korzeniu |
| Z26 | Inne wersje narzędzi niż w kontenerze (ffmpeg 7.1 → 9.0, pandoc 3.1 → 3.12, LibreOffice 25.2 → 26.8, Node, Python 3.12 → 3.13 dla Hermesa) | testy floty i evals na każdej zmianie; obraz VPS na tych samych pinach |
| Z27 | Ślady po odinstalowaniu (cache, PATH, linger, reguły zapory, zgody TCC) | dziennik zmian hosta, zmienne cache tylko w procesach Jarva, test migawki w CI |
| Z28 | Rozjazd pinów między Dockerfile (VPS) a manifestem | jeden manifest dla obu |
| Z29 | Koszt CI, gdyby repo było prywatne; koniec runnerów Intel | pełna macierz tylko na etapach; bez Intela (I06) |
| Z30 | Prywatna kopia: zasoby wydań tylko przez API z tokenem; token może przeczytać każdy proces właściciela | magazyn systemu, mały klucz (jedno repo, Contents: read, data ważności), przekierowanie bez nagłówka (I34) |
| Z31 | Rozmiar i czas pierwszej instalacji (ok. 1,5–2 GB, 34 repo skilli klonowane przez build.py) | dodatki leniwie, cache pobrań po sumie, pasek postępu; opcja: gotowy pakiet skilli z CI |
| Z32 | ddgs to skrobanie wyszukiwarek (CAPTCHA, regulaminy) | przegląd źródła; alternatywa openai-native przy mózgu ChatGPT; SearXNG na VPS |
| Z33 | Zmiana zachowania agentów (reguła 9, ścieżki, tryby zgód) | CHANGELOG każdego profilu, evals, red team na natywnej flocie |
| Z34 | Migracja: zgubiony plik -wal, ścieżki /opt w bazach, stary deinstalator kasujący `%LOCALAPPDATA%\Jarvo` | skrypt z próbą na kopii, przepisanie w transakcjach, stary deinstalator nieużywany (f1) |
| Z35 | Dokumentacja Hermesa dla Windows jest częściowo nieaktualna (uv, Node, /chat) | opieramy się na kodzie przypiętego commitu i na testach, nie na dokumentach |

## (i) Decyzje

Wszystko, co bierzemy z Hermesa albo z obcych projektów, wymaga zgody właściciela przed kodem (zasada CLAUDE.md). Zebrane w I40.

**Decyzje właściciela z 2026-10-24:**
- **I40, zapożyczenia:** zgoda na całą listę. Każde źródło i tak przechodzi przegląd z [SOURCES.md](SOURCES.md)
  w etapie, który go używa.
- **I06, macOS Intel:** rezygnujemy. Instalator na Macu z Intelem kończy pracę z jasnym komunikatem, a w CI nie ma
  nogi z Intelem. Dopiski „Intel” w mapie zostają jako wiedza, ale ich nie realizujemy.
- **I08, zgody:** domyślny tryb `jarvo` to „projekt”. Tryb pełny zawsze tylko na jedną sesję.
- **I14, wyszukiwarka:** „najlepsza dostępna opcja”. Profile przestają wymuszać `web.search_backend: searxng`,
  a wybiera autodetekcja Hermesa (tools/web_tools.py w f97608f) w kolejności: wyszukiwarka z kluczem API, jeśli
  właściciel go poda (Tavily, Perplexity, Exa, Parallel, Keenable, Firecrawl, Brave), potem SearXNG, gdy jest
  `SEARXNG_URL` (VPS), potem ddgs (instalujemy z sumą), na końcu darmowy pierścień Hermesa. Przy mózgu ChatGPT
  dochodzi wyszukiwarka modelu (`openai-native`), ale tylko jeśli test w E5 pokaże, że przejście na model
  zapasowy innego dostawcy nie psuje wyszukiwania.
- Reszta tabeli idzie według rekomendacji, dopóki właściciel nie zdecyduje inaczej.

| Nr | Decyzja | Rekomendacja | Alternatywa |
|---|---|---|---|
| **I01** | Katalogi | własny korzeń `%LOCALAPPDATA%\Jarvo` (Windows), `~/.jarvo` (macOS), `~/.local/share/jarvo` (Linux); dane w `<root>\dane`; `<program>` zawsze w ścieżce ASCII | dane poza `%LOCALAPPDATA%\Jarvo` (np. osobny katalog), żeby stary deinstalator ich nie dotknął; albo domyślny katalog Hermesa (odradzam: kolizja z prywatnym Hermesem) |
| **I02** | Instalacja Hermesa | własny bootstrap: git checkout f97608f + `uv sync --locked`; zmiana zasady CLAUDE.md „Wersja Hermesa tylko przez ARG HERMES_IMAGE” na pin w manifeście | install.ps1/install.sh Hermesa z `-Commit` (pobiera bez sum, zmienia zmienne użytkownika, zabija hermes.exe) |
| **I03** | uv, Python | uv 0.12.13 + własna lista PBS 20261021 (UV_PYTHON_DOWNLOADS_JSON_URL); Hermes i wtyczki na 3.13.17; narzędzia, OCR, CAD i SEO na 3.12.15; ManimGX na 3.13.17 | uv 0.13.5 (ma 20261021 wbudowany, ale nikt nie sprawdzał go z lockiem Hermesa); Hermes na 3.11.17 jak upstream |
| **I04** | Node | 26.x (dziś 26.12.1) po przeglądzie; npm co najmniej 11.17 | 26.5.1 jak w obrazie; 24.22.1 LTS |
| **I05** | Git na Windows | zawsze własny PortableGit 2.54.0.windows.1 (ta sama wersja co u Hermesa) | systemowy Git, gdy działa (mniej przewidywalne) |
| **I06** | macOS Intel | **decyzja: rezygnacja**; instalator na x86_64 kończy pracę z jasnym komunikatem, CI bez nogi Intela | Tier 2 „bez gwarancji” do ok. IX 2027 (odrzucone: starsze paczki, bez docling i lemo-wake) |
| **I07** | Minimalny macOS | 14 (Sonoma); OCRmyPDF na Intelu tylko macOS 15 | 13 bez lokalnego głosu i OCR (tylko głos przeglądarki) |
| **I08** | Zgody: domyślny tryb i approvals.mode | **decyzja: „projekt”**; „pełny” tylko na sesję; profil czatu z `approvals.mode: manual` | smart (czasem dwa pytania); tryby także w HQ i Telegramie albo tylko w terminalu |
| **I09** | Izolacja | na start tryby zgód i ograniczenia z (d); osobne konto systemowe dla bramy później, najpierw na Linuksie i macOS | osobne konto od razu (na Windows drogie, niesprawdzone) |
| **I10** | Nadzór procesów | własny `jarvo serwis` na wszystkich systemach, z autostartem systemu | `hermes gateway install` na macOS i Linuksie + własny nadzór tylko na Windows (dwa modele) |
| **I11** | Logowanie do panelu | loopback bez hasła; tryb LAN (Tailscale, telefon) z bramką Hermesa i dostawcą Jarva (klucz jednorazowy) | wymuszać logowanie także lokalnie (przez `dashboard.public_url`, niesprawdzone w przeglądarkach) |
| **I12** | web_dist dashboardu | dist łatany w CI dla przypiętego commitu, z sha256, przez HERMES_WEB_DIST | budowa npm/vite u użytkownika (sieć, Node, kilka minut) |
| **I13** | Bezpieczne ustawienia Hermesa | `tirith_enabled: false`, `allow_lazy_installs: false`, `adopt_external_logins: false`, `home_mode: profile` we wszystkich profilach, także w kontenerze | zostawić domyślne (pobieranie bez pinów, podgląd kluczy właściciela) |
| **I14** | Wyszukiwarka natywnie | **decyzja: najlepsza dostępna**, czyli autodetekcja Hermesa (klucz API → SearXNG na VPS → ddgs 9.16.1 z primp 2.0.1 → darmowy pierścień); `openai-native` przy ChatGPT po teście w E5 | na sztywno ddgs; na sztywno openai-native (tylko z mózgiem ChatGPT) |
| **I15** | Valkey | usunąć wszędzie, od razu (limiter SearXNG jest wyłączony) | zostawić na VPS |
| **I16** | Silnik browser_* | Windows `chrome`; macOS i Linux `lightpanda` | Chromium wszędzie (prościej, więcej RAM) |
| **I17** | Piny Chromium | dwa: headless shell zgodny z Playwright 1.63 (153.0.8010.12) dla skryptów; pełny CfT Stable z cotygodniowym podbiciem dla Komputera | jeden pin 153 dla wszystkiego (mniej pobierania, starsze łatki w przeglądarce z kontami właściciela) |
| **I18** | Komputer Jarva | domyślnie przeglądarka Jarva na CDP z proxy; kontener jako „mocna izolacja” tylko na Linuksie i VPS; właściciel godzi się na słabszą izolację na Windows i macOS | własne narzędzie wtyczki zamiast computer_use (przepisanie warstwy Operatora); toolset browser Hermesa (odradzam: CDP po TCP, dowolny JS) |
| **I19** | Ekran właściciela (K6) | cua-driver-rs 0.38.0 po przeglądzie, tryb bounded z manifestem, osobna zgoda, telemetria wyłączona, bez stałych zgód | nie robić K6 |
| **I20** | FFmpeg | 9.0.2 wszędzie: BtbN (Windows, Linux) i Riedl (macOS); później własny statyczny build dla macOS z vidstab i librsvg | n8.1.3 na Windows i Linuksie (bliżej 7.1), inna wersja na macOS |
| **I21** | Lustro plików | na razie tylko adresy zapasowe u źródła; lustro w wydaniach Jarva dopiero po ocenie licencji (GPL wymaga udostępnienia źródeł); platform-tools nigdy | od razu osobne publiczne repo z lustrem |
| **I22** | Dostarczanie narzędzi | manifest + pobieracz dla wydań u źródła; pixi 0.83.0 tylko na luki (tesseract, na macOS git, bash, exiftool); nigdy winget, brew, apt | micromamba 2.9.0 z conda-lock; całość z conda-forge (odpada przez ffmpeg) |
| **I23** | Ghostscript, Tesseract, LibreOffice | Ghostscript zastąpić pypdfium2 + pikepdf; Tesseract z conda-forge; LibreOffice: najpierw instalacja właściciela, potem dodatek | oficjalny instalator Tesseracta (UAC); conda-forge ghostscript (AGPL) |
| **I24** | Telefon testowy i ekran | telefon właściciela + adb + scrcpy w oknie; podgląd w HQ (:9122) wyłączony natywnie | utrzymać podgląd w HQ (ws-scrcpy z kompilacją node-pty albo własne proxy strumienia) |
| **I25** | Runtime VC++ | kopia DLL z conda-forge vc14_runtime 14.51.36247 obok python.exe, sprawdzona sumą i podpisem Microsoft; pobierana przy instalacji, nie hostowana (warunki redystrybucji MS) | VC_redist z jednym UAC za zgodą |
| **I26** | Smart App Control | teraz wykrywanie i komunikat; później podpisywanie wszystkiego, co dostarczamy niepodpisane (np. Azure Artifact Signing), z sumami liczonymi po podpisie | Python z python.org (podpis PSF), ale ma podatny SQLite i nie rozwiązuje niepodpisanych .pyd z kół |
| **I27** | Windows ARM64 | Python i narzędzia x64 w emulacji, tylko Windows 11 | natywne arm64 z własnymi kołami dla brakujących paczek |
| **I28** | Fonty | paczka TTF (Inter, DejaVu, Noto Sans, Noto Color Emoji) + fonts.conf, bez instalacji w systemie | fonty systemu (inny wygląd filmów na każdym komputerze) |
| **I29** | VPS | teraz zamrozić ścieżkę Docker; potem VPS na natywnym Linuksie (jednostka systemowa, Tailscale z bramką); potem usunąć compose | dwie ścieżki na stałe (podwójne piny każdego narzędzia) |
| **I30** | HOST_VERSION | zastąpić numerem schematu w manifeście; jedna procedura `jarvo update` dla CLI i panelu | zostawić |
| **I31** | Locki Pythona | zostać przy `uv pip compile --universal --generate-hashes`, dodać kontrolę koła i sumy per platforma w check-pins.py | uv.lock per venv z `required-environments` |
| **I32** | Locki npm | package-lock.json w repo i `npm ci --ignore-scripts`; HyperFrames w tym samym locku | zostawić globalną instalację HyperFrames |
| **I33** | Migracja | `jarvo migruj` z (f): `wsl --export` strumieniem, próba bez sekretów, sprzątanie tylko za zgodą | `hermes backup` w kontenerze (gubi .git skarbca i sam stawia bramę) |
| **I34** | Klucz prywatnej kopii | magazyn systemu, klucz fine-grained od właściciela, osobny na osobę | GitHub App z kodem urządzenia (rejestracja aplikacji); biblioteka keyring 25.7.0 zamiast własnego modułu |
| **I35** | Zasady CLAUDE.md | przepisać pod natywność w jednym commicie z JARVO-CALOSC §9 (R01–R06) | zostawić do końca przejścia |
| **I36** | Rutyny po instalacji | wstrzymane, włączane automatycznie po udanej próbnej wiadomości na Telegram; przełącznik w HQ | włączone od razu z dostarczaniem lokalnym |
| **I37** | Monitoring | tylko VPS | Beszel na komputerze (zbędne) |
| **I38** | Sufit pamięci | limity współbieżności (przebiegi HQ, pracownicy kanbana, jedna Chromium); max_in_progress z RAM | Job Object i cgroups po pomiarach |
| **I39** | Modele | pobierane u źródła (HF, rewizja + suma), bez naszej redystrybucji; SOURCES §5 przepisać | własne kopie (zostają obowiązki CC BY-SA i OpenRAIL-M) |
| **I40** | Zapożyczenia do zatwierdzenia | **decyzja: zgoda na całą listę**: własny nadzorca zamiast usług Hermesa, Priority 5 i zapasowe wyzwalacze, wtyczka zgód wzorowana na Claude Code, ukrycie przycisków Hermesa, wersje obok siebie (podwójne miejsce w czasie aktualizacji), ddgs, pixi, CfT, cua-driver | — |
| **I41** | Linux bez roota | instalator raz pyta o sudo na biblioteki Chromium i profil AppArmor; bez zgody `--no-sandbox` z ostrzeżeniem | odmowa instalacji bez sudo |

### Sprzeczności z rozpoznania i jak je rozstrzygnąłem

1. **Matcha:** część raportów planuje stary adres. Rozstrzygnięcie: adres -v2 zwraca 404 (sprawdzone), ta sama rewizja jest pod machinekind/Matcha-TTS-PL z tymi samymi sumami → V02, etap E0. Uwaga: raport o Intelu sprawdzał formaty plików z nowego repo -v2 (rewizja d467aae), więc zgodność przypiętego pliku z onnxruntime 1.23.2 jest niesprawdzona.
2. **Tryby zgód:** mapowanie na manual/smart/off odpada (manual nie pyta o zapisy, off jest zakazany) → wtyczka z hakiem (d).
3. **Katalog danych:** jedne raporty chcą własnego korzenia, inne domyślnego katalogu Hermesa → własny korzeń (I01), z jawnym ryzykiem starego deinstalatora.
4. **Instalacja Hermesa:** install.ps1 z -Commit nie jest „bez zapisu HERMES_HOME” (ustawia go i PATH użytkownika) → własny bootstrap (I02).
5. **Wersja uv:** 0.11.6 a 0.13.5 → 0.12.13, jak w tests.yml Hermesa, z własną listą PBS 20261021 (I03).
6. **Python Hermesa:** 3.11, 3.12 czy 3.13 → 3.13.17 z PBS 20261021 (I03); kod Jarva kompiluje się też na 3.11, więc powrót to zmiana jednego klucza.
7. **Wersje Node i Gita:** 26.5.1, 26.12.1 albo 24.22.1; Git 2.54.0 albo 2.56.0 → Node 26.x po przeglądzie, Git 2.54.0 jak u Hermesa (I04, I05).
8. **Chromium:** jedna rewizja 153 czy Stable 156 dla Komputera → dwa piny (I17).
9. **FFmpeg:** n8.1.3 czy 9.0.2 → 9.0.2 wszędzie (I20).
10. **Zakładka /chat na Windows:** dokumentacja Hermesa mówi „nie działa”, kod ma most ConPTY (web_server_chat.py:26-33) → do sprawdzenia testem; HQ ma własny czat.
11. **Stan floty właściciela:** dwa silniki Dockera z tymi samymi katalogami; działająca flota jest w Docker Engine w Ubuntu, a kopia w Docker Desktop jest pusta (f2).
12. **Tesseract na Windows:** raporty widziały tylko instalator UB Mannheim 5.4.0, ale jest oficjalny 5.5.3.20260724 (NSIS, UAC) → conda-forge przez pixi, bez admina (I23).
13. **Autostart:** zadanie Hermes_Gateway nie nadzoruje bramy → własny nadzorca (I10).
14. **Komputer:** natywny cua-driver 0.21.0 czy własny sterownik CDP → CDP dla przeglądarki Jarva, cua-driver 0.38.0 tylko dla ekranu właściciela (I18, I19).
15. **Liczby i wartości:** Lightpanda jest w 9 profilach, SearXNG w 10 (sprawdzone grepem); dozwolone wartości silnika to auto, lightpanda i chrome, więc na Windows `chrome`; healthchecków jest 95 (raporty podawały 35, 43 i 95).

## (j) Co usuwamy po przejściu i co zostaje z infra/

### j1. Usuwamy z drogi użytkownika (po etapie E13)
- **install.ps1:** instalacja WSL (wsl --install, DISM, .wslconfig, RunOnce, restart), import rootfs Ubuntu, sudoers NOPASSWD, wsl.conf z systemd, Jarvo.vbs, WSLENV, uruchamianie install.sh w Linuksie, jarvo.cmd wołający wsl.exe. Zostaje tylko wykrywanie starej instalacji na potrzeby migracji.
- **install.sh:** Docker Engine (get.docker.com, compose, buildx, grupa docker, iptables-legacy), Homebrew, Colima, OrbStack i Docker Desktop, progi sprzętu liczone pod obraz 7,3–9,8 GB.
- **bin/jarvo w bashu** → CLI w Pythonie (zostaje cienki shim).
- **Skrypty kontenerowe na komputerze:** local-up.sh, deploy.sh, install-fleet.sh, healthcheck.sh, część updater.py z docker exec, limity.py, obraz.sh, sandbox-up.sh, install-test.sh, jarvo-e2e.sh, komputer-test.sh, wiedza-kompiluj.sh, evals-staging.sh i kuznia.sh w obecnej postaci → zamienniki w Pythonie (S04–S09, S16).
- **Bash w profilach:** audit.sh i brand_extract.sh → Python.
- **Nakładki:** infra/bin/agent-browser (bash) i infra/bin/manimgx (sh) → console_scripts.
- **infra/autostart** (jednostka i plist samego pomocnika aktualizacji) → szablony nadzorcy.
- **Sidecary na komputerze:** searxng, valkey (wszędzie), monitoring, android, android-ekran, komputer.
- **Łatki Pythona w kodzie Hermesa** (strona logowania, dostawca basic, motywy) w trybie loopback; łatanie /opt/hermes w miejscu.
- **Na komputerze:** pobieranie obrazu z GHCR, HOST_VERSION, założenia check-pins.py o obrazie, testy treści Dockerfile i compose (zastępują je testy manifestu).

### j2. Zostaje z infra/ na czas przejścia (VPS) i dlaczego
- **infra/Dockerfile, infra/docker-compose.yml, obraz.yml, obraz.sh, deploy.sh, install-fleet.sh, healthcheck.sh, bootstrap-vps.sh:** VPS działa na Dockerze, dopóki nie przejdzie na natywny Linux (I29). Dockerfile bierze piny z tego samego manifestu, żeby nie było dwóch źródeł prawdy.
- **Ostatni obraz i tag `docker-ostatnia`:** baza testu migracji (T19). Bez niego test straci punkt startu, gdy stare tagi `src-*` znikną z GHCR.
- **infra/komputer:** opcja „mocna izolacja” na Linuksie i VPS: osobny uid, iptables, brak kluczy floty. Natywnie tego nie odtworzymy bez admina.
- **infra/android (Redroid, ws-scrcpy):** telefon testowy na VPS bez KVM. Redroid wymaga bindera w jądrze Linuksa, więc tylko tam.
- **infra/searxng:** wyszukiwarka floty na VPS.
- **backup.sh i restore-test.sh:** kopie na VPS przez restic, ale z `sqlite3.Connection.backup()` w Pythonie zamiast CLI sqlite3 z błędem WAL-reset.
- **scripts/migrate_jarvo.py:** część migracji (TARS → Jarvo i Docker → natywnie).

Cel końcowy: VPS na natywnym Linuksie (jednostka systemowa, użytkownik `jarvo`, bind na IP Tailscale z bramką logowania, kopia przez restic na HERMES_HOME), potem usunięcie compose i Dockerfile z aktywnej ścieżki. Dwie ścieżki na stałe oznaczałyby podwójne piny każdego narzędzia i sprzeczność z zasadą CLAUDE.md „nowa zależność idzie do obrazu”.

### j3. Zostaje i jest potrzebne natywnie
- `infra/python/*.txt`: źródła pinów; dopisać sumy tam, gdzie ich nie ma.
- `infra/node`: package.json + nowy package-lock.json.
- `infra/bin/*.py`: jako paczka Pythona z console_scripts.
- `infra/env/*.example` i `secrets/*.example`: szablony konfiguracji.
- **branding/:** łatki dista w CI.
- **vendor/:** rozszerzony zrodla.yaml, skills.lock.yaml, skan-wyjatki.yaml.
- **hq/, wiedza/, komputer/, profiles/, shared/, scripts/build.py, fleetlib.py, validate.py, zrodla.py:** po zmianach z E1–E11.

### j4. Dokumenty i zasady do przepisania

| Element | Dziś | Po zmianie | Uwagi |
|---|---|---|---|
| **R01** CLAUDE.md:10-13, przegląd źródeł | „próba w kontenerze”, jedna suma na źródło | próba na każdym systemie docelowym (5 runnerów, także bez sieci), sumy per platforma albo `brak:`, podpis i notaryzacja w punkcie „Kod” | ta sama zmiana w SOURCES.md, TOOLBOX.md:394-395 i JARVO-CALOSC §9 |
| **R02** CLAUDE.md:20-31, skarbiec | /opt/data/jarvo/knowledge, grep w kontenerze | `<dane>/jarvo/knowledge`; sprawdzenie przez `jarvo doctor` i `wiedza.py lint` | tokeny KNOWLEDGE_DIR rozwiązywane na maszynie użytkownika |
| **R03** CLAUDE.md:32-36, instalacja jednym poleceniem | zależność do obrazu, HOST_VERSION, ARG HERMES_IMAGE | zależność = wpis w manifeście z sumą dla każdej platformy; Hermes = tag + commit; bez HOST_VERSION | validate.py:745-750 wymaga dziś napisu „`HOST_VERSION` N” |
| **R04** CLAUDE.md:37-39, przed commitem | python3, make dev-deps, „na czystym kontenerze” | polecenia per system (`py -3` na Windows), `scripts/dev.py deps/test/validate`, requirements-dev.lock z sumami | make nie istnieje na zwykłym Windows |
| **R05** CLAUDE.md:40-43, test po każdym dodaniu | wdrożenie i test w jarvo-hermes jako hermes | test w instalacji natywnej (osobny `<dane>` testowy, żeby nie ruszać działającej floty) + zielona macierz CI | |
| **R06** CLAUDE.md, pozostałe zasady | commity, autor, „Jarvo nadrzędny”, dokumentacja zgodna z kodem, filmy | bez zmian; dopisać nowe kontrole validate.py; zapożyczenia z Hermesa opisujemy właścicielowi (I40) | zasada o filmach nie zależy od kontenera |
| **R07** README.md | szybki start z Dockerem, WSL i Colimą; `jarvo update` opisane jako `git pull` | szybki start natywny dla 3 systemów, polecenia `jarvo`, uczciwie o Intelu i /chat | tests/test_site.py pilnuje dokładnych poleceń instalacji |
| **R08** docs/JARVO-CALOSC.md | §4 obraz i sidecary, §5–§6 ścieżki /opt, §9 kopia zasad CLAUDE.md | §4 „Instalacja natywna” z tabelą 5 platform; §9 w tym samym commicie co CLAUDE.md | kontekst startowy każdej sesji |
| **R09** docs/INSTALER.md | cały dokument o WSL, Dockerze, Colimie, GHCR, HOST_VERSION | nowy opis per system, migracja, odinstalowanie, lista śladów; etapy z 2026-09/10 do historii | zachować napisy sprawdzane przez testy albo zmienić testy w tym samym commicie |
| **R10** docs/RUNBOOK.md | VPS z Dockerem, 18 poleceń docker exec (lustro w skarbcu!) | rozdzielić „serwer z Dockerem” i komputer właściciela; polecenia `jarvo` | agenci czytają lustro i mogą powtarzać stare polecenia |
| **R11** docs/VPS.md | topologia na kontenerach, „kontener jest sandboxem” | najpierw opis zamrożonej ścieżki Docker, potem natywny Linux; uczciwie o braku sandboxu | kotwice §2 i §5 używane w innych dokumentach |
| **R12** docs/SOURCES.md §1, §2, §5 | „komponenty obrazu”, obowiązki licencyjne przez redystrybucję obrazu | „komponenty instalacji natywnej” z kolumną platform; obowiązki zależne od I21 i I39 | każdy nowy link GitHub wymaga wpisu w zrodla.yaml |
| **R13** docs/SOURCES.md:12-31, procedura przeglądu | 7 kroków, próba w kontenerze | te same kroki, a przy każdym: pochodzenie pliku dla platformy, podpis Authenticode lub notaryzacja, instalatory .exe/.msi/.7z.exe, glibc i biblioteki, próba na 6 runnerach, sumy per platforma, skan Defenderem | |
| **R14** docs/TOOLBOX.md | „Stan instalacji w obrazie”, ścieżki /opt/jarvo | „Stan instalacji natywnej”: narzędzie × 5 platform, źródło pliku, suma albo `brak:` z zamiennikiem | kotwica z SOURCES.md:45-46 |
| **R15** docs/HQ.md | łatki w obrazie, s6, logowanie kluczem przez kontener, „Pokaż w folderze” przez WSL | łatki dista w CI, restart przez nadzorcę, loopback bez hasła, tryb LAN, Eksplorator lokalnie | |
| **R16** docs/KOMPUTER.md | Komputer jako osobny kontener (Xvnc, iptables, gniazda w wolumenie) | przeglądarka Jarva na CDP z proxy, K6 przez cua-driver 0.38, uczciwie o słabszej izolacji; kontener jako opcja | największa zmiana obietnic bezpieczeństwa |
| **R17** docs/PROFILE-SPEC.md i docs/PLAN.md | §9 „sandbox w kontenerze”; roadmapa z Dockerem; stare liczby agentów | §9 tryby zgód; nowa pozycja roadmapy „Jarvo natywnie”; liczby z fleet.yaml | |
| **R18** docs/MOBILE.md | telefon testowy w Dockerze (Redroid, docker-android, ws-scrcpy) | telefon właściciela i emulator SDK; Redroid tylko na VPS | |
| **R19** docs/WIEDZA.md | ścieżki /opt, Obsidian przez `\\wsl$`, testy w kontenerze, lint „przed kompilacją” | ścieżki `<dane>`, Obsidian wprost, `jarvo wiedza kompiluj`, lint po zasiewie | |
| **R20** Pozostałe: FLEET, RSI, ADS, BOSS, EDYTOR-PLAN, KLIPY, LEADY, ROZWOJ-FLOTY | ścieżki /opt, „test w kontenerze”, Skarbiec ADS jako kontener | ścieżki `<dane>`, „test w instalacji natywnej”; Skarbiec ADS odłożony (zadanie #50) | |
| **R21** Rozjazdy dokumentów z kodem (niezależne od kontenera) | `jarvo update` = „git pull” (kod robi fetch + ff-merge); RUNBOOK „×8” i „5 snajperów”; PLAN „7” i „Osiem profili”; lustro paczki w build.py bez linku | poprawić od razu (E0) | validate.py tego nie łapie (liczby w zdaniach, dokumenty spoza listy) |

## (k) Nowe źródła do przeglądu

Każde przechodzi przegląd z docs/SOURCES.md i trafia do vendor/zrodla.yaml. Pliki dla nowych platform to nowe artefakty, nawet gdy wersja jest już przejrzana dla Linuksa.

| Nazwa | Wersja | Licencja | Platformy | Adres |
|---|---|---|---|---|
| Hermes Agent (pin natywny) | v2026.9.24 = 0.21.5 = f97608f (zrodla.yaml ma dziś przejrzany 7157422…) | MIT | Tier 1: Windows x64 i arm64, macOS arm64, Linux x64 i arm64; macOS Intel „Unsupported” | https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.24 |
| uv | 0.12.13 (alternatywy 0.11.6, 0.13.5) | MIT lub Apache-2.0 | 6 platform, .sha256 przy każdym pliku | https://github.com/astral-sh/uv/releases/tag/0.12.13 |
| python-build-standalone | 20261021: CPython 3.13.17 i 3.12.15, SQLite 3.53.1 | PSF + MPL-2.0 (skrypty) + biblioteki w paczce | 6 platform, SHA256SUMS | https://github.com/astral-sh/python-build-standalone/releases/tag/20261021 |
| Node.js | 26.12.1 (albo 26.5.1, 24.22.1) | MIT | win x64 i arm64, darwin arm64 i x64, linux x64 i arm64; SHASUMS256 + GPG | https://nodejs.org/dist/v26.12.1/ |
| Git for Windows (PortableGit, tar.bz2) | 2.54.0.windows.1 | GPL-2.0 | Windows x64 i arm64; sumy w notatkach wydania | https://github.com/git-for-windows/git/releases/tag/v2.54.0.windows.1 |
| ripgrep | 15.2.0 | MIT lub Unlicense | 6 platform, .sha256 | https://github.com/BurntSushi/ripgrep/releases/tag/15.2.0 |
| Chrome for Testing: headless shell (skrypty) | 153.0.8010.12 (rewizja Playwrighta 1243) | BSD-3 Chromium + warunki Google dla CfT (niesprawdzone) | win64, mac-arm64, mac-x64, linux64, linux-arm64; bez sha256 u źródła | https://googlechromelabs.github.io/chrome-for-testing/ |
| Chrome for Testing: pełny Chrome (Komputer) | Stable 156.0.8078.47, podbijany co tydzień | jak wyżej | jak wyżej (bez win-arm64) | https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json |
| ffmpeg Playwrighta | rewizja 1011 | niesprawdzone | win64, mac, mac-arm64, linux, linux-arm64 | https://cdn.playwright.dev/builds/ffmpeg/1011/ffmpeg-win64.zip |
| FFmpeg BtbN (gpl) | autobuild z końca miesiąca, n9.0.2 | GPL (x264, x265) | win64, winarm64, linux64, linuxarm64; checksums.sha256 | https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-09-30-13-08 |
| FFmpeg Martin Riedl | 9.0.2 | GPL (szczegóły buildu niesprawdzone) | macOS arm64 i amd64 (Intel do I 2027), Linux amd64 i arm64; .sha256, podpis | https://ffmpeg.martin-riedl.de/ |
| FFmpeg evermeet.cx (zapas na Intela) | 9.0.2 | GPL | tylko macOS x86_64; podpis GPG, bez sum | https://evermeet.cx/ffmpeg/ |
| FFmpeg Gyan.dev (zapas na Windows) | 9.0.2 essentials | GPLv3 | Windows x64; .sha256 | https://www.gyan.dev/ffmpeg/builds/ |
| Lightpanda (pliki z wydania) | 1.0.0 (nowsze 1.0.1, 1.0.2) | AGPL-3.0 | Linux x86_64 i aarch64, macOS x86_64 i aarch64; bez Windows; digesty GitHub | https://github.com/lightpanda-io/browser/releases/tag/1.0.0 |
| Camoufox (paczki Windows i macOS) | 152.0.4-beta.30 | MPL-2.0 + fonty na różnych licencjach | win x86_64 i i686, mac arm64 i x86_64, lin x86_64 i arm64 | https://github.com/daijro/camoufox/releases/tag/v152.0.4-beta.30 |
| agent-browser (binarki Windows i macOS) | 0.38.1 | Apache-2.0 | darwin arm64 i x64, linux x64 i arm64 (+musl), win32-x64; bez win32-arm64 | https://unpkg.com/agent-browser@0.38.1/bin/ |
| pandoc | 3.12.1 | GPL-2.0-or-later | Windows x86_64, macOS arm64 i x86_64, Linux amd64 i arm64 | https://github.com/jgm/pandoc/releases/tag/3.12.1 |
| qpdf | 12.4.2 | Apache-2.0 | msvc64, msvc-arm64, macOS arm64 i x86_64, Linux x86_64 i aarch64; .sha256 + sigstore | https://github.com/qpdf/qpdf/releases/tag/v12.4.2 |
| ExifTool | 13.59 | jak Perl (Artistic lub GPL) | Windows zip z Perlem, tar.gz | https://exiftool.org/checksums.txt |
| conda-forge exiftool (macOS) | 13.59 z Perlem 5.44 | GPL-1.0-or-later | win-64, osx-64, osx-arm64, linux-64, linux-aarch64 | https://anaconda.org/conda-forge/exiftool |
| conda-forge tesseract | 5.5.3 (z tessdata_fast 4.1.0) | Apache-2.0 | win-64, osx-64, osx-arm64, linux-64, linux-aarch64 | https://anaconda.org/conda-forge/tesseract |
| tessdata_fast (pol, eng, osd) | 4.1.0 | Apache-2.0 | dane, wszystkie systemy | https://github.com/tesseract-ocr/tessdata_fast |
| conda-forge ghostscript (tylko zapas) | 10.08.0 | AGPL-3.0 | 5 platform | https://anaconda.org/conda-forge/ghostscript |
| OCRmyPDF | 17.13.0 (Intel: 17.12.1) | MPL-2.0 | koło noarch; wymaga Tesseracta | https://ocrmypdf.readthedocs.io/en/latest/installation.html |
| pikepdf | 10.17.0 (Intel: 10.13.0.post1) | MPL-2.0 | win_amd64, win_arm64, macOS arm64, manylinux | https://pypi.org/project/pikepdf/#files |
| pypdfium2 (zamiast Ghostscriptu) | 5.14.0 | BSD-3 i Apache-2.0 | koła na 6 platform | https://pypi.org/project/pypdfium2/5.14.0/#files |
| LibreOffice | 26.8.1 | MPL-2.0 | Windows x86-64 i aarch64 (msi), macOS (dmg), Linux (deb, rpm); .sha256 + .asc | https://download.documentfoundation.org/libreoffice/stable/26.8.1/ |
| jq (opcjonalnie) | 1.8.2 | MIT | 6 platform, sha256sum.txt | https://github.com/jqlang/jq/releases/tag/jq-1.8.2 |
| Android platform-tools | r37.0.1 | Android SDK License | Windows, macOS, Linux x86_64; tylko SHA-1 u źródła | https://dl.google.com/android/repository/repository2-3.xml |
| scrcpy | 5.0.1 | Apache-2.0 | win64, winarm64, win32, macOS aarch64 i x86_64, Linux x86_64; SHA256SUMS | https://github.com/Genymobile/scrcpy/releases/tag/v5.0.1 |
| Android Emulator (SDK) | niesprawdzone | Android SDK License | Windows x64 (WHPX), macOS (Hypervisor.Framework), Linux x64 (KVM) | https://developer.android.com/studio/run/emulator-acceleration |
| pixi | 0.83.0 | BSD-3-Clause | 6 platform, .sha256 | https://github.com/prefix-dev/pixi/releases/tag/v0.83.0 |
| micromamba (alternatywa) | 2.9.0-0 | BSD-3-Clause | 5 platform + win-arm64 | https://github.com/mamba-org/micromamba-releases/releases/tag/2.9.0-0 |
| conda-forge vc14_runtime (DLL VC++) | 14.51.36247, build habf1de7_41 | licencja Microsoft (warunki redystrybucji do oceny) | win-64 | https://anaconda.org/conda-forge/vc14_runtime |
| conda-forge pango (tylko jeśli zostaje WeasyPrint) | 1.58.2 | LGPL-2.0-or-later | 5 platform | https://anaconda.org/conda-forge/pango |
| Fonty: Inter, DejaVu, Noto Sans, Noto Color Emoji | 4.1; 2.37; 2.015; 2.051 | OFL-1.1; licencja Bitstream/DejaVu; OFL; OFL | dane, wszystkie systemy | https://github.com/rsms/inter/releases/tag/v4.1 |
| Matcha-TTS-PL (nowa nazwa repo) | rewizja 93744740ae645648c003abb09e8c617d9c5e34cd | CC BY-SA 4.0 | model | https://huggingface.co/machinekind/Matcha-TTS-PL |
| Parakeet TDT 0.6B v3 ONNX | rewizja 8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce | CC-BY-4.0 | model | https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx |
| Silero VAD ONNX | rewizja b3e3ee3cce4c11ceb63b1a0b229d916069c1ddf6 | MIT | model | https://huggingface.co/istupakov/silero-vad-onnx |
| Paradee-8M (pin commitu) | 8f34b01ef8adcb0bec470b89bf2fd62a7b2369e6 | Apache-2.0 | model | https://huggingface.co/sahilmahendrakar/Paradee-8M-v1.0 |
| onnxruntime | 1.31.0 (Intel: 1.23.2) | MIT | win_amd64, win_arm64, macOS arm64 14+, manylinux; 1.23.2 dla macOS x86_64 | https://pypi.org/project/onnxruntime/1.31.0/#files |
| espeakng-loader (koła Windows i macOS) | 0.2.4 | MIT (loader) + GPL-3.0 (espeak-ng) | win_amd64, win_arm64, macOS, manylinux | https://pypi.org/project/espeakng-loader/0.2.4/#files |
| cadquery-ocp-novtk (koła Windows i macOS) | 8.0.1.1.0 | Apache-2.0 + OCCT LGPL-2.1 z wyjątkiem | win_amd64, macOS arm64 i x86_64, manylinux | https://pypi.org/project/cadquery-ocp-novtk/8.0.1.1.0/#files |
| manimgx (koła Windows i macOS) | 0.1.1 | wyrażenie MIT AND GPL-2.0-or-later AND … | win_amd64, macOS arm64 i x86_64, manylinux | https://pypi.org/project/manimgx/0.1.1/#files |
| numba i llvmlite (Intel) | 0.62.1 i 0.45.1 | BSD-2 | ostatnie z kołami macOS x86_64 | https://pypi.org/project/numba/0.62.1/#files |
| @img/sharp-* (prebuildy) | 0.35.4 (libvips 1.3.3) | Apache-2.0 + LGPL-3.0 (libvips) | win32 x64 i arm64, darwin, linux | https://www.npmjs.com/package/sharp/v/0.35.4 |
| @remotion/compositor-* i @napi-rs/canvas | 4.0.529 i 0.1.80 | Remotion: własna licencja (warunki komercyjne do sprawdzenia); MIT | win32-x64-msvc, darwin, linux | https://www.npmjs.com/package/@remotion/compositor-win32-x64-msvc/v/4.0.529 |
| auto-editor (binarki z wydania) | 29.3.1 | Unlicense | windows-amd64, macOS arm64 i x86_64, linux-x86_64 | https://github.com/WyattBlue/auto-editor/releases/tag/29.3.1 |
| codebase-memory-mcp (Windows i macOS) | 0.11.0 | MIT (w części raportów niesprawdzone) | windows amd64 i arm64, darwin, linux | https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.11.0 |
| ddgs + primp | 9.16.1 i 2.0.1 | MIT | czysty Python + koła abi3 na 6 platform | https://pypi.org/project/primp/2.0.1/ |
| edge-tts (pin z hashem) | 7.2.7 | LGPL-3.0 | czysty Python | https://pypi.org/project/edge-tts/7.2.7/ |
| cua-driver-rs (K6) | 0.38.0 (0.21.0 dziś w obrazie) | MIT | windows x86_64 i arm64 (Authenticode), darwin universal, linux x86_64 i arm64; SHA256SUMS + Sigstore | https://github.com/trycua/cua/releases/tag/cua-driver-rs-v0.38.0 |
| sigstore (Python, weryfikacja K6) | 4.5.1 | Apache-2.0 | czysty Python | https://pypi.org/project/sigstore/ |
| Playwright for Python | 1.62.0 (Camoufox) i 1.63.0 | Apache-2.0 | win_amd64, win_arm64, macOS, manylinux | https://pypi.org/project/playwright/1.62.0/#files |
| pywin32, psutil, concurrent-log-handler (już w locku Hermesa) | 311; 7.2.2; 0.9.29 | PSF; BSD-3; Apache-2.0 | Windows; wszystkie; Windows | https://pypi.org/project/pywin32/311/ |
| tzdata | 2026.5 | Apache-2.0 | czysty Python | https://pypi.org/project/tzdata/ |
| keyring (tylko przy I34 bez własnego modułu) | 25.7.0 (+ SecretStorage 3.5.0, jeepney 0.9.0, pywin32-ctypes 0.2.3) | MIT | czysty Python | https://pypi.org/project/keyring/25.7.0/ |
| Akcje GitHub (pełne SHA) | checkout v7.0.1, setup-python v7.1.0, setup-node v7.1.0, upload-artifact v7.0.2, download-artifact v8.0.2, setup-uv v10.3.2, setup-wsl v7.2.0 | MIT / Apache-2.0 | runnery | https://github.com/actions/checkout/releases/tag/v7.0.1 |
| Narzędzia CI | ShellCheck 0.11.0, PowerShell 7.6.8, PSScriptAnalyzer 1.25.0, pytest 9.1.1, pytest-timeout 2.4.0, pytest-xdist 3.8.0 | GPL-3.0 (ShellCheck), MIT | według narzędzia | https://github.com/PowerShell/PowerShell/releases/tag/v7.6.8 |
| tirith (do **odrzucenia**) | v0.4.2 | AGPL-3.0 | brak Windows ARM; zip Windows oznaczony przez Defender | https://github.com/sheeki03/tirith/releases/tag/v0.4.2 |

## (l) Sprawdzone na żywo 2026-10-24

Po rozpoznaniu sprawdziłem ponownie te ustalenia, od których zależą decyzje. Przy każdym podaję, czym to sprawdziłem.

| Ustalenie | Wynik | Czym |
|---|---|---|
| Widoczność repo | publiczne, więc standardowe runnery GitHub Actions (także macOS) są darmowe | `gh repo view` |
| `jarvo.pl/install.sh` i `install.ps1` | 404; strona główna 200, ale bez przekierowania na HTTPS, bez nagłówków bezpieczeństwa, plik z 2026-09-29 (stara wersja strony) | curl |
| `raw.githubusercontent.com/.../main/install.sh` i `install.ps1` | 200 | curl |
| Matcha-TTS-PL, rewizja 93744740 | pod `machinekind/Matcha-TTS-PL-v2` 404; pod `machinekind/Matcha-TTS-PL` 200, sumy obu plików ONNX takie jak w infra/Dockerfile | curl, API Hugging Face (paths-info) |
| Lightpanda 0.4.1–1.0.2 | pliki tylko dla Linuksa i macOS, bez Windows | API wydań GitHub |
| python-build-standalone 20261021 | jest (opublikowane 2026-10-21) | API wydań GitHub |
| Platformy Hermesa | Tier 1: macOS Apple Silicon, Windows 10/11 x86_64 i aarch64, Linux x86_64 i aarch64; macOS Intel na liście „Unsupported” | website/docs/getting-started/platform-support.md w f97608f |
| Instalator Hermesa na Windows | uv przez `irm https://astral.sh/uv/install.ps1 \| iex` bez sumy; ustawia HERMES_HOME i PATH użytkownika; `taskkill /F /T /IM hermes.exe` | scripts/install.ps1 w f97608f |
| Zgody Hermesa a zapis plików | zapis `write_file`/`patch` nie ma pytania o zgodę (blokada albo przepuszczenie) | website/docs/user-guide/security.md, „File Write Safety” |
| Hak `pre_tool_call` | może zwrócić `{"action": "approve", ...}` i podnieść każde narzędzie do bramki zgód | hermes_cli/plugins.py w f97608f |
| Dashboard Hermesa na Windows | uvicorn na SelectorEventLoop, na którym podprocesy asyncio nie działają | hermes_cli/web_server.py w f97608f |
| tirith | pobierany z `releases/latest`, bez pinu | tools/tirith_security.py w f97608f |
| Błąd WAL-reset w SQLite | Hermes uznaje za naprawione 3.51.3+, 3.50.7 i 3.44.6 | hermes_cli/doctor_platform.py w f97608f |
| uv w CI Hermesa | tests.yml 0.12.13, pozostałe workflowy 0.9.28 | .github/workflows w f97608f |
| Runnery GitHub | są windows-2025, windows-11-arm, macos-15 i macos-26 (arm64), macos-15-intel i macos-26-intel (x64), ubuntu-24.04 i ubuntu-24.04-arm | README actions/runner-images |

### Kiedy całość jest gotowa
- Ostatnia pełna macierz CI jest zielona na ostatnim commicie: instalacja, czat, pozwolenia, flota, panel, filmy, lektor,
  OCR, Komputer, update, uninstall i migracja.
- To samo przeszło ręcznie na Windowsie właściciela, ze zrzutami.
- README i [INSTALER.md](INSTALER.md) podają po jednym poleceniu instalacji na system, tym samym, które testuje CI.
- pytest, `validate.py`, testy node i `wiedza.py lint` są bez błędów na każdym systemie.
- Nie ma martwego kodu po Dockerze i WSL. To, co zostaje w infra/ (VPS), ma uzasadnienie w (j2).
- Raport końcowy po polsku: tabela funkcja × system z linkami do CI, zrzuty panelu, polecenia instalacji i migracji,
  co usunięto, znane ograniczenia z planem naprawy.
