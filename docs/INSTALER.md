# Instalator: jedno polecenie na Linuksie, macOS i Windowsie

Cel: użytkownik wkleja **jedno polecenie** do terminala, a po kilku minutach ma działającą flotę
i otwarty dashboard. Bez ręcznego instalowania Dockera, bez czytania dokumentacji. Ten dokument
opisuje, co już działa, czego brakuje na każdym systemie, jak to zbudować i ile to kosztuje pracy.

Stan: plan z 2026-09-30; **etap 1 (Linux) zbudowany i przetestowany 2026-09-30** (§4a), **etap 2 (obraz w GHCR)
i etap 3 (macOS) zbudowane 2026-10-09** (§4b; macOS czeka na próbę na prawdziwym Macu), **etap 4 (Windows)
zbudowany 2026-10-09** (§4c; czeka na próbę na prawdziwym Windowsie), etap 5 w toku.

---

## 1. Co jest dziś

| Element | Plik | Co robi |
|---|---|---|
| Instalator Linux/WSL/macOS | [`install.sh`](../install.sh) | Linux i WSL: sprawdza sprzęt, doinstalowuje `git curl python3 openssl` i Docker Engine, grupa `docker`, klon do `~/jarvo`, polecenie `jarvo`, `jarvo up`, autostart pomocnika, dashboard w przeglądarce; ponowne wklejenie = aktualizacja. macOS (12+): Homebrew (z narzędziami Xcode), `bash git python openssl@3`, Docker w Colimie (działający Docker Desktop/OrbStack zostaje), dane w wolumenach, LaunchAgent. Prywatne repo: klucz dostępu (`JARVO_TOKEN` albo pytanie, gdy klon bez klucza się nie uda), zapisany tylko w `.git/config` repo (0600). `sudo` dopiero wtedy, gdy coś naprawdę go wymaga |
| Instalator Windows | [`install.ps1`](../install.ps1) | Windows 10 2004+ / 11, x64 i ARM64: WSL2 bez dystrybucji (jedno okno zgody administratora), restart i dalszy ciąg sam (RunOnce), własna dystrybucja `Jarvo` z oficjalnego obrazu Ubuntu 24.04 (SHA256), użytkownik `jarvo` z sudo bez hasła i systemd, w środku `install.sh` (Docker Engine, obraz, flota), autostart z folderu Autostart, dashboard. Bez Docker Desktop i Microsoft Store. Istniejąca instalacja w innej dystrybucji (np. Ubuntu z Docker Desktop) jest aktualizowana na miejscu |
| Polecenie użytkownika | [`bin/jarvo`](../bin/jarvo) | `up`, `down`, `status`, `logs`, `update` (`git pull` + ten sam `install.sh`, więc nowe wymagania hosta też dochodzą), `chat`, `open`, `pliki` (macOS: `docker cp` z wolumenu do `~/Jarvo`), `autostart on\|off\|status`, `android on\|off\|status` (telefon testowy Twórcy aplikacji, [MOBILE.md](MOBILE.md) §5), `uninstall [--yes] [--all]`, `version`; sam sięga po grupę `docker` przez `sg`, gdy sesja jeszcze jej nie ma |
| Postawienie floty | [`scripts/local-up.sh`](../scripts/local-up.sh) | pyta o dostawcę modeli i klucz (albo bierze z `JARVO_PROVIDER`/`JARVO_KEY`/`JARVO_YES=1`), tworzy `~/jarvo-local` (`compose/`, `secrets/`, `build/`, `data/`), buduje obraz (albo `JARVO_NO_BUILD=1`), woła `deploy.sh`, startuje pomocnika aktualizacji; `--prepare` tylko przygotowuje katalog |
| Autostart | [`infra/autostart/jarvo-updater.service`](../infra/autostart/jarvo-updater.service), [`infra/autostart/pl.jarvo.updater.plist`](../infra/autostart/pl.jarvo.updater.plist) | Linux: usługa `systemd --user` pomocnika aktualizacji (`jarvo autostart on` renderuje i włącza linger). macOS: LaunchAgent `pl.jarvo.updater` uruchamia przy logowaniu `jarvo updater`, który najpierw stawia Dockera (`colima start` albo Docker Desktop). Kontenery wstają same (`restart: unless-stopped`) |
| Wdrożenie | [`scripts/deploy.sh`](../scripts/deploy.sh) | compose build/up, build dystrybucji i instalacja profili w kontenerze, healthchecki |
| Gotowy obraz | [`scripts/obraz.sh`](../scripts/obraz.sh), [`.github/workflows/obraz.yml`](../.github/workflows/obraz.yml) | GitHub Actions buduje `jarvo-hermes` dla amd64 i arm64 i publikuje w GHCR jako `src-<klucz>` (klucz = skrót `infra/Dockerfile`, `infra/node`, `infra/python`, `infra/bin`, `branding`); `deploy.sh` najpierw pobiera obraz dla klucza swojej wersji repo, a buduje na miejscu tylko, gdy go nie ma (`JARVO_BUILD_IMAGE=1`: zawsze buduj). Wersja Hermesa przypięta w `infra/Dockerfile` (tag + digest), więc klucz obejmuje i ją; własny `HERMES_IMAGE` w `compose/.env` = budowa na miejscu |
| Serwer (VPS) | [`scripts/bootstrap-vps.sh`](../scripts/bootstrap-vps.sh) | jednorazowe przygotowanie Ubuntu/Debian (Docker, użytkownik, UFW, Tailscale) |
| Testy | [`tests/test_installer.py`](../tests/test_installer.py), [`tests/test_install_ps1.py`](../tests/test_install_ps1.py), [`scripts/install-test.sh`](../scripts/install-test.sh), [`.github/workflows/installer.yml`](../.github/workflows/installer.yml) | pytest: składnia, shellcheck, próby na sucho na udawanych dystrybucjach, macOS i Windowsie, sprzęt, `jarvo`, `local-up.sh --prepare`; instalacja od zera w świeżym kontenerze Ubuntu/Debian z własnym Dockerem (piaskownica i CI z obrazem z GHCR); CI na prawdziwym macOS i Windowsie |

Polecenia ze strony: `curl -fsSL …/install.sh | bash` oraz `irm …/install.ps1 | iex`.

**Gdy czegoś brakuje:** instalator doinstalowuje to sam na każdym systemie: Linux i WSL (etap 1), macOS (etap 3),
Windows (etap 4: WSL, Linux i Docker). Człowiek potrzebny jest tylko do hasła / zgody administratora i restartu
Windowsa po włączeniu WSL.

Obraz `jarvo-hermes:local` instalator pobiera gotowy z GHCR (etap 2, amd64 i arm64, ~2–3 minuty);
buduje na miejscu tylko, gdy obrazu dla tej wersji jeszcze nie ma (kilka–kilkanaście minut, 8 GB RAM).
Obraz arm64 (Apple Silicon, Windows na ARM) buduje i uruchamia CI na natywnym runnerze arm64.

**Aktualizacje i nowe zależności.** Każda nowa zależność floty trafia do obrazu (`infra/Dockerfile`,
`infra/node`, `infra/python`): CI buduje nowy obraz, a `deploy.sh` u każdego go pobiera, więc użytkownik
nie robi nic. Zmiana tego, co musi być na komputerze (program hosta, wersja Dockera, autostart), idzie do
`install.sh` / `install.ps1` z podbiciem `HOST_VERSION` w `install.sh`: `jarvo update` uruchamia nowy
instalator, a `deploy.sh` przypomina „uruchom jarvo update”, gdy `compose/.host-version` jest starsza. Na Windowsie
`jarvo update` w Linuksie odświeża wszystko poza samym Windowsem; zmiana w `install.ps1` (WSL, autostart) wymaga
ponownego `irm https://jarvo.pl/install.ps1 | iex` (drugie uruchomienie = aktualizacja).

## 2. Diagnoza: co przeszkadza na każdym systemie

| | Linux | macOS | Windows |
|---|---|---|---|
| Docker | trzeba mieć; instalator nie instaluje | trzeba mieć Docker Desktop (klikanie, licencja w firmach >250 osób) | trzeba mieć Docker Desktop + WSL2 |
| git, python3, openssl | zwykle są; brak = koniec | brak `git` bez Xcode CLT (`xcode-select --install` otwiera okno) | w WSL Ubuntu są |
| bash | ok | 3.2 z 2007 r.; instalator już radzi sobie przez Homebrew | w WSL ok |
| `sudo chown 10000` (dane kontenera) | ok (pyta o hasło) | działa, ale mapowanie uid w VM zależy od runtime'u (Docker Desktop mapuje, Colima nie zawsze) | ok w WSL |
| Restart komputera | nie | nie | **tak**, po włączeniu WSL (nie do ominięcia) |
| Autostart floty po restarcie | brak | brak | brak (WSL nie wstaje sam) |
| Aktualizacja | `install.sh` ponownie albo przycisk w dashboardzie | jw. | jw. |
| Odinstalowanie | brak | brak | brak |

Wniosek: **najtrudniejszy jest Windows** (restart w środku instalacji, WSL, autostart),
**macOS** ma jeden twardy próg (Homebrew i VM Dockera wymagają hasła administratora i pierwszego
uruchomienia), **Linux** jest prosty.

## 3. Projekt: jak wygląda „jedna komenda” docelowo

Zasada: instalator sam instaluje wszystko, czego brakuje, zatrzymuje się tylko tam, gdzie system
wymaga człowieka (hasło `sudo`, restart Windowsa), i po powrocie **kontynuuje sam**.

```
Linux    curl -fsSL https://jarvo.pl/install.sh | bash
macOS    curl -fsSL https://jarvo.pl/install.sh | bash
Windows  irm https://jarvo.pl/install.ps1 | iex        (PowerShell, jako zwykły użytkownik)
```

(Repo jest publiczne. `jarvo.pl/install.sh` i `jarvo.pl/install.ps1` to przekierowanie w `site/.htaccess` na
`https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.sh` (i `.ps1`), więc domena zawsze podaje
najnowszy instalator z `main` bez ponownego wgrywania strony; `curl -L`, `wget` i `irm` idą za przekierowaniem.
Instalator klonuje gałąź `main`, `JARVO_BRANCH=…` wybiera inną; przy prywatnej kopii repo pyta o klucz dostępu.)

### Linux (zrobione, §4a)
1. Menedżer pakietów (`apt`, `dnf`/`yum`, `pacman`, `zypper`) doinstalowuje `git curl python3 openssl`.
2. Docker Engine z oficjalnego skryptu (`get.docker.com`; Arch i openSUSE z pakietów), `docker compose` v2,
   użytkownik do grupy `docker`; do ponownego zalogowania polecenie `jarvo` samo uruchamia się przez
   `sg docker`, więc instalacja nie czeka na wylogowanie.
3. `jarvo up` (`local-up.sh`) jak dotąd. Autostart: kontenery wstają same z Dockerem
   (`restart: unless-stopped`), a pomocnik aktualizacji jako usługa `systemd --user`
   `jarvo-updater` z `loginctl enable-linger` (`jarvo autostart on|off|status`).

### macOS (zbudowane, §4b)
1. Homebrew, gdy brak (oficjalny skrypt w trybie `NONINTERACTIVE=1`; sam instaluje narzędzia Xcode bez okna;
   jedno hasło `sudo`), potem `brew install bash git python openssl@3` i `brew shellenv` w `~/.zprofile`.
   macOS starszy niż 12 kończy się komunikatem (Homebrew i Colima go nie wspierają); instalacja jako root odmawia.
2. Runtime Dockera: **jeśli `docker info` już działa** (Docker Desktop, OrbStack, Colima), używamy go; jest
   Docker Desktop, ale wyłączony → `open -a Docker`. Inaczej **Colima** (`brew install colima docker docker-compose`,
   `colima start --cpu N --memory M --disk 60 --vm-type vz --mount-type virtiofs`; macOS 12: `qemu`):
   darmowa, bez klikania, bez licencji. Rozmiar VM z maszyny: procesory połowa (2–6), RAM 8 GB przy ≥16 GB,
   6 GB przy ≥12 GB, inaczej 5 GB. Wtyczka `docker compose` z Homebrew dopisana do `~/.docker/config.json`.
3. Dane floty w **nazwanych wolumenach Dockera** (`jarvo-hermes-data`, `jarvo-valkey-data`, `jarvo-build`) zamiast
   katalogów `~/jarvo-local/data` (decyzja I1): znika problem uid 10000 między macOS a VM. Ten sam
   `docker-compose.yml` (`${JARVO_VOL_HERMES:-…}`); wybór przy pierwszym `jarvo up` (`JARVO_VOLUMES=1`, na macOS
   domyślnie). Wyniki agentów: dashboard albo `jarvo pliki` (`docker cp` do `~/Jarvo`).
4. Autostart: LaunchAgent `~/Library/LaunchAgents/pl.jarvo.updater.plist` (`jarvo autostart on|off|status`):
   przy logowaniu `jarvo updater` stawia Dockera (Colima / Docker Desktop) i pomocnika aktualizacji;
   kontenery wstają z Dockerem same.

### Windows (zbudowane, §4c)
1. `install.ps1` jako zwykły użytkownik: Windows 10 2004+ (kompilacja 19041) albo 11, x64 lub ARM64, RAM i dysk.
   Brak WSL → `wsl --install --no-distribution` (jedno okno UAC; starszy Windows 10: DISM), przy 8–15 GB RAM
   `~/.wslconfig` z `memory=RAM−3GB` (domyślna połowa to za mało), wpis `RunOnce` z kopią instalatora
   w `%LOCALAPPDATA%\Jarvo` (z BOM dla PowerShella 5.1; klucz dostępu zaszyfrowany DPAPI), restart, a po
   zalogowaniu **instalator rusza sam**. WSL dalej nie działa po restarcie → `wsl --update`, potem jasny komunikat.
2. Własna dystrybucja `Jarvo` zamiast Ubuntu ze Store: oficjalny obraz Canonical
   (`cloud-images.ubuntu.com/wsl/releases/24.04/current`, suma z `SHA256SUMS`), `wsl --import`, użytkownik `jarvo`
   z sudo bez hasła (Windows i tak wchodzi do WSL jako root, a hasła Linuksa ludzie zapominają), `/etc/wsl.conf`
   z `systemd=true` i `default=jarvo`. Wyłączona wirtualizacja (`0x80370102`) → komunikat, co włączyć w BIOS.
   Inne dystrybucje użytkownika zostają nietknięte.
3. **Docker Engine wewnątrz WSL** zamiast Docker Desktop (decyzja I2): `install.sh` jak na Linuksie,
   zero klikania, zero licencji. Jarvo zainstalowane już w innej dystrybucji (np. Ubuntu z Docker Desktop):
   aktualizacja tam, z tymczasowym sudo bez hasła (`/etc/sudoers.d/zz-jarvo-install`, usuwane na końcu).
4. Zmienne (`JARVO_TOKEN`, `JARVO_PROVIDER`, `JARVO_KEY`, `JARVO_YES`, `JARVO_BRANCH`, `JARVO_FORCE`) przechodzą
   do Linuksa przez `WSLENV`, nie przez wiersz poleceń. Dashboard pod `http://localhost:9119` (WSL przekazuje porty).
5. Autostart: `Jarvo.vbs` w folderze Autostart uruchamia ukryty `wsl.exe -d Jarvo -u root -e sleep infinity`,
   który trzyma dystrybucję przy życiu; systemd w niej stawia Dockera, kontenery i pomocnika aktualizacji.
6. `JARVO_UNINSTALL=1` usuwa dystrybucję `Jarvo`, autostart i `%LOCALAPPDATA%\Jarvo`; `JARVO_DRY_RUN=1` pokazuje kroki.
7. PowerShell 5.1: plik bez BOM (BOM psuje `irm | iex`), w kodzie tylko ASCII (PowerShell czyta „ ” jak cudzysłów),
   programy (`wsl.exe`, `curl.exe`) z `ErrorActionPreference=Continue` (stderr nie przerywa), błąd przy `irm | iex`
   nie zamyka okna, a ustawienia sesji wracają po instalacji.

### Wspólne (każdy system)
- **Tryb bez pytań:** `JARVO_PROVIDER=openrouter JARVO_KEY=… JARVO_YES=1` dla skryptów i testów;
  domyślnie pytania jak dziś (dostawca modeli, klucz), czytane z `/dev/tty`, nie z potoku `curl | bash`.
- **Polecenie `jarvo`** (`~/jarvo/bin/jarvo` na PATH): `up`, `down`, `status`, `logs`, `update`, `chat`,
  `pliki`, `uninstall` (kontenery, obraz, `~/jarvo-local`, autostart; repo i klucze pyta osobno).
- **Idempotencja:** ponowne wklejenie tego samego polecenia = aktualizacja, nigdy druga instalacja.
- **Test dymny na końcu:** healthchecki z `deploy.sh`, otwarcie dashboardu w przeglądarce
  (`xdg-open` / `open` / `Start-Process`), hasło wypisane raz i zapisane w `~/jarvo-local/compose/.env`.
- **Onboarding po instalacji** (pomysł z [PLAN.md](PLAN.md#6-roadmapa), „Pomysły do zbadania”): pierwsze wejście do dashboardu
  prowadzi przez klucz modelu, opcjonalny Telegram i wywiad `onboarding-interview`.
- **Obraz gotowy do pobrania** (decyzja I3): GitHub Actions buduje `jarvo-hermes` dla `amd64` i `arm64`
  i publikuje w GHCR; instalator pobiera obraz zamiast budować (kilkanaście minut → 2–3 minuty,
  bez 8 GB RAM potrzebnych do budowy). Lokalna budowa zostaje jako `JARVO_BUILD_IMAGE=1`.

## 4. Etapy

| Etap | Zakres | Test | Nakład |
|---|---|---|---|
| 1. Linux ✅ | auto-instalacja pakietów i Docker Engine, `sg docker`, tryb bez pytań, `jarvo` CLI, autostart systemd, `uninstall` | automatyczny: `scripts/install-test.sh` (świeży `ubuntu:24.04` z własnym `dockerd`, w piaskownicy Claude Code) i `tests/test_installer.py`; do zrobienia ręcznie: świeży VPS z systemd (autostart, linger) | zrobione 2026-09-30 |
| 2. Obraz w GHCR ✅ | workflow `obraz.yml` (amd64 i arm64 na natywnych runnerach, tag `src-<klucz>` z plików obrazu), `deploy.sh` pobiera przez `scripts/obraz.sh`, buduje tylko bez obrazu; Hermes przypięty w `infra/Dockerfile` | CI buduje; `install.sh` pobiera | zrobione 2026-10-09 |
| 3. macOS 🟡 | Homebrew (z narzędziami Xcode), Colima albo istniejący runtime, wolumeny zamiast katalogów, LaunchAgent, klucz dostępu, `jarvo update` przez instalator | `tests/test_installer.py` (próby na sucho na udawanym macOS: Apple Silicon, 8 GB i macOS 12 → qemu, macOS 11 odmowa, działający Docker zostaje); do zrobienia: **ręczny na prawdziwym Macu** (Intel i M-series), bo runnery GitHuba na macOS nie mają zagnieżdżonej wirtualizacji | kod 2026-10-09; czeka na Maca |
| 4. Windows 🟡 | `install.ps1`: WSL bez dystrybucji, RunOnce po restarcie, własna dystrybucja `Jarvo` z obrazu Ubuntu, Docker Engine w WSL, autostart, aktualizacja istniejącej instalacji, odinstalowanie | `tests/test_install_ps1.py` (PowerShell 7 z `make dev-pwsh`: składnia, PSScriptAnalyzer, próby na sucho na udawanym Windowsie, `irm \| iex`); do zrobienia: **ręczny na prawdziwym Windowsie 11** (świeży i z istniejącą instalacją w Ubuntu) | kod 2026-10-09; czeka na Windowsa |
| 5. Wykończenie | strona `jarvo.pl/install`, onboarding w dashboardzie, `RUNBOOK.md` i `README.md` z jedną sekcją „Instalacja” dla trzech systemów | protokół testu ręcznego (checklista w tym pliku, §6) | 1–2 dni |

Razem: **około dwóch tygodni pracy**, z czego Linux i obraz w GHCR da się zrobić i przetestować
w całości z tej sesji, a macOS i Windows wymagają Twoich maszyn do testów (ja przygotuję skrypty
i checklistę, Ty wklejasz polecenie i przysyłasz log).

### 4a. Etap 1 (Linux): co zbudowano i jak sprawdzono

Zbudowane 2026-09-30 (pliki w §1):
- `install.sh` od nowa: całość w `main()` (bash wykonuje dopiero po pobraniu w całości), wykrywanie systemu,
  procesora i dystrybucji, sprawdzenie RAM (minimum 4 GB, polecane 8) i dysku (minimum 10 GB, polecane 20;
  `JARVO_FORCE=1` wymusza), doinstalowanie brakujących programów, Docker Engine + start demona (systemd,
  `service`, w ostateczności `dockerd` w tle; WSL bez systemd dostaje `iptables-legacy`), grupa `docker`,
  wolny port 9119, klon albo aktualizacja repo (`fetch` + `checkout` + `merge --ff-only`; lokalne zmiany
  zatrzymują), `/usr/local/bin/jarvo` (albo `~/.local/bin`), log `~/jarvo-local/install.log` bez kluczy,
  proxy z środowiska przekazywane pod `sudo`; wejście przepięte na terminal (`curl | bash` daje potok, więc hasło
  `sudo` i odpowiedzi muszą iść z `/dev/tty`), hasło `sudo` raz na początku (`sudo -v`), Docker działający już
  jako użytkownik (Docker Desktop w WSL) nie wymaga ani `sudo`, ani grupy. Zmienne: `JARVO_PROVIDER`, `JARVO_KEY`, `JARVO_YES=1`,
  `JARVO_SETUP_ONLY=1`, `JARVO_NO_AUTOSTART=1`, `JARVO_FORCE=1`, `JARVO_DRY_RUN=1`, `JARVO_DIR`, `JARVO_LOCAL`,
  `JARVO_REPO`, `JARVO_BRANCH`.
- `bin/jarvo` (lista poleceń w §1); `uninstall` usuwa kontenery, obraz, usługę i polecenie, o dane, klucze
  i repo pyta osobno (`--all` usuwa też je; samo `--yes` ich nie rusza).
- `scripts/local-up.sh`: dostawca i klucz z env, `--prepare`, `JARVO_NO_BUILD=1`, `JARVO_RESUME_CRON=1` (rutyny Jarva), bez `sudo` u roota,
  restart usługi `jarvo-updater` zamiast procesu w tle, gdy usługa jest włączona.
- macOS bez regresji: te same sprawdzenia co wcześniej (git, Docker, bash 4+), `bin/jarvo` sam przechodzi
  na basha z Homebrew.

Sprawdzone:
- `tests/test_installer.py` (13 testów): składnia, shellcheck bez ostrzeżeń, próby na sucho na udawanych
  dystrybucjach (Ubuntu, Fedora, Arch, nieznana), obecny Docker pomijany, za mało RAM, `JARVO_SETUP_ONLY`,
  klucz nigdy w wyjściu, `jarvo help/version/autostart print`, katalog z `.jarvo-local`,
  `local-up.sh --prepare` bez pytań (env, sekrety 640/gid 10000, dane uid 10000).
- `scripts/install-test.sh ubuntu:24.04` w piaskownicy: świeży kontener bez gita, curla, Pythona, Dockera;
  użytkownik bez roota z sudo; `cat install.sh | bash` → pakiety, Docker Engine z `get.docker.com`, grupa
  `docker`, repo, `jarvo`; obrazy wczytane `docker load` (compose nie widzi proxy piaskownicy); `jarvo up`
  bez pytań przez `sg docker`; dashboard odpowiada; ponowne `install.sh` = aktualizacja; `jarvo status`,
  `down`, `uninstall --yes` (dane zostają), `uninstall --all`.

Czego etap 1 nie obejmuje (świadomie): autostart bez systemd (WSL bez `systemd=true`, kontenery testowe),
instalacja Dockera na macOS (etap 3), WSL i restart Windowsa (etap 4), obraz z rejestru (etap 2).

### 4b. Etapy 2–3 (obraz, macOS, klucz, aktualizacja): co zbudowano i jak sprawdzono

Zbudowane 2026-10-09:
- **Gotowy obraz** (§1): `obraz.yml` buduje `jarvo-hermes` na natywnych runnerach amd64 i arm64 i łączy je w jeden
  tag `src-<klucz>`; `deploy.sh` pobiera go przez `scripts/obraz.sh pobierz`, a przy prywatnym pakiecie loguje się
  do GHCR kluczem z instalatora. Hermes przypięty w `infra/Dockerfile` (tag + digest), żeby CI i budowa na miejscu
  dawały ten sam obraz.
- **macOS** (§3): `install.sh` z gałęzią macOS (Homebrew, Colima, rozmiar VM, wtyczka compose), `local-up.sh` z trybem
  wolumenów (`JARVO_VOLUMES`), `deploy.sh` nadaje wolumenom właściciela 10000 jednorazowym kontenerem,
  `bin/jarvo` z LaunchAgentem, `pliki` przez `docker cp`, `uninstall --all` usuwa też wolumeny.
- **Prywatne repo** (dziś repo jest publiczne; zostaje dla prywatnych kopii): `JARVO_TOKEN` (albo pytanie z terminala, ukryte, gdy anonimowy klon się nie uda); klucz trafia
  tylko do nagłówka git w `.git/config` repo (0600) i do `docker login ghcr.io`, nigdy do logu ani na ekran.
- **Aktualizacja:** `jarvo update` = `git pull --ff-only` + `exec bash install.sh` (nowa wersja instalatora, bez
  banera i bez otwierania przeglądarki); `sudo` tylko, gdy trzeba coś doinstalować. `install.sh` zapisuje
  `HOST_VERSION` w `compose/.host-version`; starsza wersja → `deploy.sh` prosi o `jarvo update`.

Sprawdzone: `tests/test_installer.py` (Homebrew przed Colimą, `sudo -v` przed Homebrew, mała maszyna i macOS 12 → qemu
i 5 GB, macOS 11 → odmowa, działający Docker zostaje, klucz nigdy w wyjściu i użyty do gita, `local-up.sh --prepare`
w trybie wolumenów, `docker compose config` dla katalogów i wolumenów), shellcheck, pełny pytest.
Czego nie sprawdzono: instalacji na prawdziwym Macu (protokół §6).

### 4c. Etap 4 (Windows): co zbudowano i jak sprawdzono

Zbudowane 2026-10-09: `install.ps1` od nowa (§3 Windows), `scripts/dev-pwsh.sh` (`make dev-pwsh`: PowerShell 7.5.5
i PSScriptAnalyzer 1.24.0, przypięte sumami, do `.tools/`), `PSScriptAnalyzerSettings.psd1` (wyłączone reguły
z uzasadnieniem), `tests/test_install_ps1.py`, instalatory na jarvo.pl (`scripts/deploy-site.sh`, typ
`text/plain; charset=utf-8` i `no-cache` w `site/.htaccess`).

Sprawdzone (PowerShell 7 na Linuksie, Windows udawany zmiennymi `JARVO_FAKE_*`): składnia, PSScriptAnalyzer bez
uwag, świeży Windows (WSL z UAC, `.wslconfig` przy 8 GB, RunOnce, restart), gotowy WSL (pobranie i import
dystrybucji amd64 / arm64, konfiguracja, `install.sh` jako `jarvo`, autostart, dashboard), istniejąca instalacja
w Ubuntu (aktualizacja z tymczasowym sudo), własna dystrybucja już jest, odmowy (stary Windows, mało RAM, mało
dysku, procesor x86), klucz nigdy na ekranie, odinstalowanie, `irm | iex` nie zamyka sesji.
Czego nie sprawdzono: prawdziwego `wsl.exe`, UAC, restartu i Windows PowerShell 5.1 (protokół §6).

## 5. Czy to jest ciężkie? (uczciwa ocena)

- **Linux: łatwe.** Wszystko jest skryptowalne, Docker Engine instaluje się jednym poleceniem.
- **macOS: średnie.** Nie ma Dockera bez maszyny wirtualnej. Colima załatwia to bez klikania, ale
  Homebrew i VM wymagają hasła administratora (raz). Ryzyka: mapowanie uid (rozwiązane wolumenem),
  Apple Silicon nigdy nie testowany (obrazy bazowe są arm64, więc raczej zadziała), Gatekeeper przy
  pierwszym `colima`. Najwięcej czasu zajmą testy na prawdziwym Macu, nie kod.
- **Windows: najtrudniejsze.** Twarde ograniczenia: restart po włączeniu WSL (systemowy, nie do ominięcia)
  i to, że WSL nie startuje sam po restarcie (Harmonogram zadań). Do tego dwie różne powłoki
  (PowerShell + bash), UAC i antywirusy, które lubią blokować `wsl --install`. Ścieżka bez Docker Desktop
  usuwa najgorszy krok (ręczne włączanie integracji WSL w ustawieniach Dockera).
- **Czego jedna komenda nie usunie nigdzie:** hasła administratora (Docker musi mieć uprawnienia),
  restartu na Windowsie, wpisania klucza do modelu (albo logowania do ChatGPT w dashboardzie).
  Wszystko inne da się zautomatyzować.

Wymagania sprzętowe pozostają: 8 GB RAM (kontener ma limit 5 GB), 20 GB dysku (obraz 4,8 GB + dane),
procesor x86_64 albo arm64. Na słabszej maszynie instalator ma to powiedzieć na starcie, nie po
20 minutach. Sufit CPU kontenerów (`HERMES_CPUS`, `ANDROID_CPUS`) `deploy.sh` obniża do liczby procesorów,
które widzi Docker (laptop z 2 rdzeniami, mały VPS, Colima z 2 CPU), bo większego Docker nie uruchomi.

## 6. Protokół testu ręcznego (macOS, Windows)

Na świeżym koncie użytkownika (albo maszynie wirtualnej), bez Dockera:
1. Wklej polecenie ze strony. Zapisz, ile razy pytało o hasło i o co jeszcze pytało.
2. Po zakończeniu: dashboard otwarty sam? Logowanie działa? Czat z Jarvem odpowiada (z kluczem)?
3. Restart komputera → flota wstaje sama (`jarvo status`)?
4. Wklej polecenie drugi raz → aktualizacja bez pytań, dane i klucze zachowane?
5. `jarvo uninstall` → brak kontenerów, obrazu i autostartu.
6. Log instalacji (`~/jarvo-local/install.log`) do repo jako załącznik zgłoszenia.

## 7. Decyzje do podjęcia

| # | Pytanie | Rekomendacja |
|---|---|---|
| I1 | Dane na macOS: katalog `~/jarvo-local/data` (jak dziś) czy wolumen Dockera? | **Wolumen** (bez problemów z uid), wyniki przez dashboard i `jarvo pliki` |
| I2 | Windows: Docker Desktop czy Docker Engine w WSL? | **Engine w WSL**; istniejący Docker Desktop wykrywany i używany |
| I3 | Obraz: budować lokalnie czy pobierać z GHCR? | **GHCR** (etap 2); repo jest publiczne, więc pakiet `jarvo-hermes` w GHCR też ma być publiczny (bez tego instalator buduje obraz na miejscu, kilkanaście minut) |
| I4 | Autostart po restarcie domyślnie włączony? | **Tak** (flota to usługa, jak na VPS); `jarvo autostart off` wyłącza |
| I5 | Nazwa polecenia w terminalu | `jarvo` |
| I6 | Kolejność | Linux → GHCR → macOS → Windows (od najpewniejszego do najtrudniejszego; Windows testujemy na Twoim komputerze) |

## 8. Pliki

| Plik | Rola | Stan |
|---|---|---|
| `install.sh` | bootstrap: system, pakiety, Docker (Engine / Colima / istniejący), klucz dostępu, klon, `jarvo up`, autostart, dashboard, `HOST_VERSION` | ✅ Linux/WSL; ✅ macOS (czeka na próbę na Macu) |
| `install.ps1` | bootstrap Windows: WSL, restart + `RunOnce`, dystrybucja `Jarvo`, `install.sh` w WSL, autostart (`Jarvo.vbs`), odinstalowanie | ✅ (czeka na próbę na Windowsie) |
| `scripts/dev-pwsh.sh`, `PSScriptAnalyzerSettings.psd1`, `tests/test_install_ps1.py` | PowerShell 7 i PSScriptAnalyzer do testów, reguły lintu, próby na sucho `install.ps1` | ✅ |
| `scripts/local-up.sh` | postawienie floty; tryb bez pytań, `--prepare`, `JARVO_NO_BUILD`, wolumeny (`JARVO_VOLUMES`, macOS domyślnie) | ✅ |
| `bin/jarvo` | polecenie użytkownika (`up`, `down`, `status`, `logs`, `update`, `chat`, `open`, `pliki`, `autostart`, `uninstall`, `version`); macOS: Colima, LaunchAgent, wolumeny | ✅ |
| `infra/autostart/` | `jarvo-updater.service` (systemd user), `pl.jarvo.updater.plist` (LaunchAgent macOS) | ✅ |
| `scripts/install-test.sh` | instalacja od zera w świeżym kontenerze Ubuntu/Debian z własnym Dockerem: piaskownica (obrazy z zewnętrznego Dockera) albo CI / zwykła maszyna (`JARVO_TEST_PULL=1`: `jarvo up` pobiera obraz z GHCR) | ✅ |
| `tests/test_installer.py` | składnia, shellcheck, próby na sucho (Linux i macOS), klucz dostępu, `jarvo`, `local-up.sh --prepare`, wolumeny, przypięty Hermes | ✅ |
| `.github/workflows/obraz.yml`, `scripts/obraz.sh` | obraz amd64+arm64 do GHCR, pobieranie zamiast budowy | ✅ |
| `.github/workflows/installer.yml` | przy każdej zmianie instalatora i obrazu floty (`infra/Dockerfile`, `infra/node`, `infra/python`, `infra/bin`): Linux od zera w świeżym Ubuntu z obrazem z GHCR (`install-test.sh`, `JARVO_TEST_PULL=1`), macOS (bash 3.2, próba na sucho, `jarvo` i plik LaunchAgent sprawdzony `plutil`; pełna instalacja z Colimą na żądanie: `mac_pelna`), Windows (testy `install.ps1` w PowerShell 5.1 i 7, PSScriptAnalyzer) | ✅ |
