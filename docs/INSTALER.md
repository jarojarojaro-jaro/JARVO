# Instalator: jedno polecenie na Linuksie, macOS i Windowsie

Cel: użytkownik wkleja **jedno polecenie** do terminala, a po kilku minutach ma działającą flotę
i otwarty dashboard. Bez ręcznego instalowania Dockera, bez czytania dokumentacji. Ten dokument
opisuje, co już działa, czego brakuje na każdym systemie, jak to zbudować i ile to kosztuje pracy.

Stan: plan z 2026-09-30; **etap 1 (Linux) zbudowany i przetestowany 2026-09-30** (§4a), etapy 2–5 do zrobienia.

---

## 1. Co jest dziś

| Element | Plik | Co robi |
|---|---|---|
| Instalator Linux/WSL/macOS | [`install.sh`](../install.sh) | Linux i WSL: sprawdza sprzęt, doinstalowuje `git curl python3 openssl` i Docker Engine, grupa `docker`, klon do `~/jarvo`, polecenie `jarvo`, `jarvo up`, autostart pomocnika, dashboard w przeglądarce; ponowne wklejenie = aktualizacja. macOS: sprawdza git, bash 4+ (Homebrew) i działający Docker (etap 3 doda instalację) |
| Instalator Windows | [`install.ps1`](../install.ps1) | sprawdza WSL i Docker Desktop, odpala `install.sh` w WSL (etap 4 doda instalację WSL i Dockera) |
| Polecenie użytkownika | [`bin/jarvo`](../bin/jarvo) | `up`, `down`, `status`, `logs`, `update`, `chat`, `open`, `pliki`, `autostart on\|off\|status`, `uninstall [--yes] [--all]`, `version`; sam sięga po grupę `docker` przez `sg`, gdy sesja jeszcze jej nie ma |
| Postawienie floty | [`scripts/local-up.sh`](../scripts/local-up.sh) | pyta o dostawcę modeli i klucz (albo bierze z `JARVO_PROVIDER`/`JARVO_KEY`/`JARVO_YES=1`), tworzy `~/jarvo-local` (`compose/`, `secrets/`, `build/`, `data/`), buduje obraz (albo `JARVO_NO_BUILD=1`), woła `deploy.sh`, startuje pomocnika aktualizacji; `--prepare` tylko przygotowuje katalog |
| Autostart | [`infra/autostart/jarvo-updater.service`](../infra/autostart/jarvo-updater.service) | szablon usługi `systemd --user` pomocnika aktualizacji (`jarvo autostart on` renderuje i włącza linger); kontenery wstają same (`restart: unless-stopped`) |
| Wdrożenie | [`scripts/deploy.sh`](../scripts/deploy.sh) | compose build/up, build dystrybucji i instalacja profili w kontenerze, healthchecki |
| Serwer (VPS) | [`scripts/bootstrap-vps.sh`](../scripts/bootstrap-vps.sh) | jednorazowe przygotowanie Ubuntu/Debian (Docker, użytkownik, UFW, Tailscale) |
| Testy | [`tests/test_installer.py`](../tests/test_installer.py), [`scripts/install-test.sh`](../scripts/install-test.sh) | pytest: składnia, shellcheck, próby na sucho na udawanych dystrybucjach, sprzęt, `jarvo`, `local-up.sh --prepare`; piaskownica: instalacja od zera w świeżym kontenerze Ubuntu/Debian z własnym Dockerem |

Polecenia ze strony: `curl -fsSL …/install.sh | bash` oraz `irm …/install.ps1 | iex`.

**Gdy czegoś brakuje:** na Linuksie i w WSL instalator doinstalowuje to sam (etap 1). Na macOS i Windowsie
nadal kończy się komunikatem „zainstaluj Docker Desktop…”, i to jest krok, który mają usunąć etapy 3 i 4.

Obraz `jarvo-hermes:local` buduje się lokalnie (pierwszy raz kilka–kilkanaście minut, ok. 6 GB).
Obrazy bazowe są wieloarchitekturowe (`nousresearch/hermes-agent` i `lightpanda/browser`:
`linux/amd64` i `linux/arm64`), a jedyna binarka zależna od procesora w `Dockerfile` (agent-browser)
ma wariant arm64, więc Apple Silicon **powinien** działać; nikt tego jeszcze nie sprawdził.

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

(`jarvo.pl/install.sh` to przekierowanie na raw GitHub; do czasu domeny działa adres z `README.md`:
`…/JARVO/main/install.sh`; instalator klonuje gałąź `main`, `JARVO_BRANCH=…` wybiera inną.)

### Linux (zrobione, §4a)
1. Menedżer pakietów (`apt`, `dnf`/`yum`, `pacman`, `zypper`) doinstalowuje `git curl python3 openssl`.
2. Docker Engine z oficjalnego skryptu (`get.docker.com`; Arch i openSUSE z pakietów), `docker compose` v2,
   użytkownik do grupy `docker`; do ponownego zalogowania polecenie `jarvo` samo uruchamia się przez
   `sg docker`, więc instalacja nie czeka na wylogowanie.
3. `jarvo up` (`local-up.sh`) jak dotąd. Autostart: kontenery wstają same z Dockerem
   (`restart: unless-stopped`), a pomocnik aktualizacji jako usługa `systemd --user`
   `jarvo-updater` z `loginctl enable-linger` (`jarvo autostart on|off|status`).

### macOS
1. Xcode Command Line Tools (bez okna: `softwareupdate` z plikiem `.xcode-select-installing`), Homebrew, gdy
   brak (oficjalny skrypt, jedno hasło `sudo`), `brew install bash git python openssl`.
2. Runtime Dockera: **jeśli `docker info` już działa** (Docker Desktop, OrbStack), używamy go. Jeśli nie,
   **Colima** (`brew install colima docker docker-compose`, `colima start --cpu 4 --memory 8 --disk 60 --vm-type vz
   --mount-type virtiofs`): darmowa, bez klikania, bez licencji, autostart przez `brew services start colima`.
3. Dane floty na macOS w **nazwanym wolumenie Dockera** zamiast katalogu `~/jarvo-local/data`
   (decyzja I1): znika problem mapowania uid 10000 między macOS a VM. Wyniki agentów użytkownik
   ogląda w dashboardzie (jak teraz) albo przez `jarvo pliki` (`docker cp` do `~/Jarvo`).
4. Autostart: `launchd` (`~/Library/LaunchAgents/pl.jarvo.fleet.plist`).

### Windows
1. `install.ps1` bez uprawnień administratora sprawdza WSL. Brak → `wsl --install --no-distribution`
   (UAC raz), wpis w `RunOnce`, żeby **po restarcie instalator sam wystartował** i dokończył.
2. Ubuntu w WSL (`wsl --install -d Ubuntu`); pierwsze uruchomienie z użytkownikiem `jarvo` bez pytań
   (`ubuntu.exe install --root` + `useradd`), `/etc/wsl.conf` z `systemd=true`.
3. **Docker Engine wewnątrz WSL** zamiast Docker Desktop (decyzja I2): ten sam skrypt co na Linuksie,
   zero klikania, zero licencji. Jeśli Docker Desktop już jest i działa, używamy go.
4. `install.sh` w WSL jak na Linuksie; dashboard pod `http://localhost:9119` (WSL przekazuje porty).
5. Autostart: zadanie Harmonogramu zadań przy logowaniu (`wsl -d Ubuntu --exec systemctl start jarvo`),
   pomocnik `updater.py` już umie otwierać Eksplorator na plikach wyników.

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
| 2. Obraz w GHCR | workflow `build-image.yml` (buildx amd64+arm64, tag = commit i wersja), `deploy.sh --pull-image`, `local-up.sh` pobiera zamiast budować | CI buduje; `install.sh` na Linuksie w trybie pobierania | 1 dzień |
| 3. macOS | Xcode CLT, Homebrew, Colima albo istniejący runtime, wolumen zamiast katalogu, launchd, test na Apple Silicon | **ręczny na prawdziwym Macu** (Intel i M-series); CI: `shellcheck` + próba na sucho (`JARVO_DRY_RUN=1`), bo runnery GitHuba na macOS arm64 nie mają zagnieżdżonej wirtualizacji | 2–3 dni + Twój Mac |
| 4. Windows | `install.ps1`: WSL bez dystrybucji, RunOnce po restarcie, Ubuntu bez pytań, Docker Engine w WSL, Harmonogram zadań, Eksplorator | **ręczny na prawdziwym Windowsie 11** (masz WSL: test aktualizacji istniejącej instalacji też); CI: PSScriptAnalyzer + próba na sucho | 3–5 dni + Twój Windows |
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
  proxy z środowiska przekazywane pod `sudo`. Zmienne: `JARVO_PROVIDER`, `JARVO_KEY`, `JARVO_YES=1`,
  `JARVO_SETUP_ONLY=1`, `JARVO_NO_AUTOSTART=1`, `JARVO_FORCE=1`, `JARVO_DRY_RUN=1`, `JARVO_DIR`, `JARVO_LOCAL`,
  `JARVO_REPO`, `JARVO_BRANCH`.
- `bin/jarvo` (lista poleceń w §1); `uninstall` usuwa kontenery, obraz, usługę i polecenie, o dane, klucze
  i repo pyta osobno (`--all` usuwa też je; samo `--yes` ich nie rusza).
- `scripts/local-up.sh`: dostawca i klucz z env, `--prepare`, `JARVO_NO_BUILD=1`, bez `sudo` u roota,
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

Wymagania sprzętowe pozostają: 8 GB RAM (kontener ma limit 5 GB), 20 GB dysku (obraz 4,4 GB + dane),
procesor x86_64 albo arm64. Na słabszej maszynie instalator ma to powiedzieć na starcie, nie po
20 minutach.

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
| I3 | Obraz: budować lokalnie czy pobierać z GHCR? | **GHCR** (etap 2); wymaga publicznego pakietu w GHCR albo tokenu przy repo prywatnym |
| I4 | Autostart po restarcie domyślnie włączony? | **Tak** (flota to usługa, jak na VPS); `jarvo autostart off` wyłącza |
| I5 | Nazwa polecenia w terminalu | `jarvo` |
| I6 | Kolejność | Linux → GHCR → macOS → Windows (od najpewniejszego do najtrudniejszego; Windows testujemy na Twoim komputerze) |

## 8. Pliki

| Plik | Rola | Stan |
|---|---|---|
| `install.sh` | bootstrap: system, pakiety, Docker (Engine / Colima / istniejący), klon, `jarvo up`, autostart, dashboard | ✅ Linux/WSL; macOS: Docker ręcznie (etap 3) |
| `install.ps1` | bootstrap Windows: WSL, restart + `RunOnce`, Ubuntu, `install.sh` w WSL, Harmonogram zadań | ⬜ (dziś: sprawdza WSL i Docker Desktop) |
| `scripts/local-up.sh` | postawienie floty; tryb bez pytań, `--prepare`, `JARVO_NO_BUILD`; wolumen na macOS i pobieranie obrazu | ✅ / ⬜ (etapy 2–3) |
| `bin/jarvo` | polecenie użytkownika (`up`, `down`, `status`, `logs`, `update`, `chat`, `open`, `pliki`, `autostart`, `uninstall`, `version`) | ✅ |
| `infra/autostart/` | `jarvo-updater.service` (systemd user) ✅; `pl.jarvo.fleet.plist` (launchd), `jarvo-task.xml` (Harmonogram zadań) ⬜ | |
| `scripts/install-test.sh` | instalacja od zera w świeżym kontenerze Ubuntu/Debian z własnym Dockerem (piaskownica) | ✅ |
| `tests/test_installer.py` | składnia, shellcheck, próby na sucho, `jarvo`, `local-up.sh --prepare` | ✅ |
| `.github/workflows/build-image.yml` | obraz amd64+arm64 do GHCR | ⬜ (etap 2) |
| `.github/workflows/installer.yml` | `shellcheck`, PSScriptAnalyzer, test `install.sh` w kontenerze Ubuntu/Debian | ⬜ |
