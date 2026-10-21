#!/usr/bin/env bash
# Instalator Jarvo: Linux, WSL2, macOS. Jedno polecenie ze strony:
#
#   curl -fsSL https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.sh | bash   (albo jarvo.pl/install.sh)
#   (jarvo.pl/install.sh przekierowuje na ten adres, gdy strona jest wgrana: site/.htaccess)
#
# Linux i WSL: sprawdza sprzęt (procesor, RAM, dysk), doinstalowuje brakujące programy (git, curl, python3,
# openssl) menedżerem pakietów dystrybucji (apt, dnf/yum, pacman, zypper), instaluje Docker Engine
# (get.docker.com; Arch i openSUSE z pakietów), uruchamia demona, dodaje Cię do grupy docker, pobiera repo
# do ~/jarvo (albo je aktualizuje), instaluje polecenie `jarvo` i uruchamia `jarvo up` (scripts/local-up.sh):
# pytania o dostawcę modeli, flota w Dockerze, healthchecki, pomocnik aktualizacji jako usługa systemd
# użytkownika, otwarcie dashboardu. Ponowne wklejenie tego samego polecenia = aktualizacja.
# macOS: doinstalowuje Homebrew (razem z narzędziami Xcode), basha 4+, gita i Pythona; Docker działający już
# (Docker Desktop, OrbStack, Colima) zostaje, a bez niego instaluje Colimę (darmowa maszyna wirtualna z Dockerem,
# bez okien i licencji) i włącza jej start przy logowaniu. Dane floty na macOS trzyma w wolumenach Dockera.
# Windows: install.ps1 (WSL, restart, osobna dystrybucja Jarvo, ten skrypt w środku). Opis: docs/INSTALER.md.
#
# Zmienne (wszystkie opcjonalne):
#   JARVO_DIR, JARVO_LOCAL       katalog repo (~/jarvo) i instalacji floty (~/jarvo-local)
#   JARVO_REPO, JARVO_BRANCH     adres git i gałąź (main)
#   JARVO_PROVIDER, JARVO_KEY    dostawca modeli (openrouter, commandcode-anthropic, commandcode, openai-codex)
#                                i klucz; z JARVO_YES=1 instalator o nic nie pyta (bez klucza: GUI działa,
#                                klucz dodasz w dashboardzie)
#   JARVO_SETUP_ONLY=1           system, Docker i repo tak, floty nie uruchamiaj (potem: jarvo up)
#   JARVO_NO_AUTOSTART=1         bez usługi systemd pomocnika aktualizacji
#   JARVO_FORCE=1                mimo za małego RAM albo dysku
#   JARVO_TOKEN                  klucz dostępu do prywatnej kopii repo (token GitHub od właściciela); publiczne
#                                repo go nie potrzebuje, a gdy repo nie da się pobrać anonimowo, instalator zapyta
#   JARVO_NO_OPEN=1              nie otwieraj dashboardu na końcu (jarvo update)
#   JARVO_DRY_RUN=1              tylko pokaż, co by zrobił (nic nie instaluje)
#
# Cały skrypt siedzi w funkcji main, więc bash wykonuje go dopiero po pobraniu w całości: ucięty transfer
# nic nie uruchomi. Hasło sudo i pytania czyta z terminala (/dev/tty), nie z potoku curl | bash; sudo pyta
# o hasło raz, na początku. Klucze nigdy nie trafiają do logu (~/jarvo-local/install.log).
set -euo pipefail

REPO="${JARVO_REPO:-https://github.com/jarojarojaro-jaro/JARVO.git}"
BRANCH="${JARVO_BRANCH:-main}"      # pusta = gałąź główna repo (klon bez -b, aktualizacja bieżącej)
DIR="${JARVO_DIR:-$HOME/jarvo}"
L="${JARVO_LOCAL:-$HOME/jarvo-local}"
DRY="${JARVO_DRY_RUN:-0}"
FORCE="${JARVO_FORCE:-0}"
OS_RELEASE="${JARVO_OS_RELEASE:-/etc/os-release}"   # testy: udawana dystrybucja
MEMINFO="${JARVO_MEMINFO:-/proc/meminfo}"             # testy: udawany RAM
# dysk: obraz floty 2,5 GB pobrania, 7,3 GB po rozpakowaniu (magazyn containerd z Dockera 29 trzyma też spakowane
# warstwy: 9,8 GB), Komputer Jarva 1,6 GB, dane; budowa na miejscu (bez rejestru) dokłada ok. 8 GB cache
MIN_RAM_GB=4; REC_RAM_GB=8; MIN_DISK_GB=20; REC_DISK_GB=30
PORT=9119
DOCKER_SCRIPT="https://get.docker.com"
DOCKER_RPM_REPO="https://download.docker.com/linux/centos/docker-ce.repo"
DISTRO=""
BREW_SCRIPT="https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
# wersja wymagań hosta (programy poza obrazem floty: Docker, Colima, git, Python…). Zmiana tego, co ten skrypt
# instaluje na komputerze = +1; deploy.sh porównuje ją z zapisaną przy instalacji i prosi o `jarvo update`.
HOST_VERSION=4
TOKEN="${JARVO_TOKEN:-}"

if [[ -t 1 ]]; then R=$'\e[38;2;212;33;61m'; W=$'\e[1;38;2;242;241;232m'; G=$'\e[38;2;184;255;61m'; Y=$'\e[33m'; D=$'\e[2m'; N=$'\e[0m'
else R=; W=; G=; Y=; D=; N=; fi
say() { printf '%s▌%s %s\n' "$R" "$N" "$*"; }
warn() { printf '%s!%s %s\n' "$Y" "$N" "$*"; }
die() { printf '%s✗%s %s\n' "$R" "$N" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
# na sucho: pokaż polecenie zamiast je wykonać
run() { if [[ $DRY == 1 ]]; then printf '%s  $ %s%s\n' "$D" "${*/#git_auth/git}" "$N"; else "$@"; fi; }
as_root() { if [[ -n $SUDO ]]; then need_root; run $SUDO "$@"; else run "$@"; fi; }
# hasło administratora dopiero, gdy naprawdę coś instalujemy: aktualizacja bez nowych programów nie pyta o nic
SUDO_ASKED=0
need_root() { [[ -n $SUDO && $SUDO_ASKED == 0 ]] || return 0; SUDO_ASKED=1; sudo_check; }
# proxy (np. firmowe) ma działać także pod sudo, które czyści środowisko: as_root env "${PROXY_ENV[@]}" polecenie
PROXY_ENV=()
proxy_setup() {
  local v
  for v in HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy; do
    [[ -n "${!v:-}" ]] && PROXY_ENV+=("$v=${!v}")
  done
  return 0
}
# bash 3.2 (macOS) nie znosi "${tablica[@]}" pustej tablicy przy set -u
penv() { as_root env ${PROXY_ENV[@]+"${PROXY_ENV[@]}"} "$@"; }

OS=; ARCH=; PKG=; SUDO=; NEWBASH=; NEED_GROUP=0; BREW=; MACVER=0

sudo_check() {   # hasło administratora raz, na początku; kolejne sudo (pakiety, Docker, chown danych floty) idą z pamięci
  [[ -n $SUDO ]] || return 0
  if [[ $DRY != 1 ]] && $SUDO -n true 2>/dev/null; then return 0; fi   # uprawnienia już zapamiętane (albo NOPASSWD)
  say "Potrzebne hasło administratora (sudo), zwykle tylko raz:"
  if ! run $SUDO -v; then
    [[ $OS == wsl ]] && die "sudo nie przyjęło hasła. W WSL to hasło użytkownika Linuksa $(id -un) ustawione przy pierwszym uruchomieniu Ubuntu, nie hasło ani PIN Windowsa. Nie pamiętasz? W PowerShellu: wsl -u root passwd $(id -un)   (albo uruchom instalator z PowerShella: irm …/install.ps1 | iex, wtedy hasło nie jest potrzebne)."
    [[ $OS == macos ]] && die "macOS nie przyjął hasła. Podaj hasło, którym logujesz się do Maca (konto musi być administratorem: Ustawienia systemowe → Użytkownicy i grupy)."
    die "sudo nie przyjęło hasła albo $(id -un) nie ma uprawnień sudo."
  fi
}

detect_os() {
  case "$(uname -s)" in
    Darwin) OS=macos ;;
    Linux) OS=linux; grep -qi microsoft /proc/version 2>/dev/null && OS=wsl ;;
    *) die "Nieobsługiwany system: $(uname -s). Na Windowsie uruchom polecenie PowerShell ze strony." ;;
  esac
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) ARCH=x86_64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) die "Nieobsługiwany procesor: $ARCH (potrzebny x86_64 albo arm64)." ;;
  esac
  if [[ $OS == macos ]]; then
    MACVER="$( (sw_vers -productVersion 2>/dev/null || echo 0) | cut -d. -f1)"
    say "System: macOS $(sw_vers -productVersion 2>/dev/null || echo '?') ($ARCH)"
    (( MACVER == 0 || MACVER >= 12 )) || die "Potrzebny macOS 12 albo nowszy (masz $(sw_vers -productVersion)): Homebrew i Colima nie wspierają starszych."
    # Homebrew (docs.brew.sh/Support-Tiers, od 09.2026): gotowe paczki tylko dla Apple Silicon z macOS 15+;
    # Intel i macOS 12–14 to Tier 3, więc część programów kompiluje się na miejscu
    if [[ $ARCH == x86_64 ]]; then
      warn "Mac z Intelem: Homebrew nie buduje już dla niego gotowych paczek, część programów skompiluje się na miejscu (dłużej, czasem z błędem). Krócej z działającym Docker Desktop albo OrbStack."
    elif (( MACVER > 0 && MACVER < 15 )); then
      warn "macOS $MACVER: Homebrew ma gotowe paczki dla macOS 15 i nowszego, część programów skompiluje się na miejscu (dłużej). Polecamy aktualizację macOS."
    fi
    # Homebrew, tymczasowe uprawnienia dla sekretów floty (grupa 10000) i polecenie jarvo potrzebują administratora
    [[ $(id -u) -eq 0 ]] && die "Na macOS uruchom instalator jako zwykły użytkownik (bez sudo): Homebrew odmawia pracy jako root."
    SUDO=sudo
    return
  fi
  say "System: $OS ($ARCH)"
  if [[ $OS != macos ]]; then
    if [[ $(id -u) -eq 0 ]]; then
      SUDO=
      warn "Uruchamiasz jako root: flota trafi do $DIR. Na serwerze polecamy scripts/bootstrap-vps.sh (użytkownik bez roota, firewall)."
    elif have sudo; then SUDO=sudo
    else die "Potrzebne uprawnienia administratora: zainstaluj sudo albo uruchom jako root."
    fi
  fi
}

detect_pkg() {
  local ID="" ID_LIKE=""
  if [[ -r $OS_RELEASE ]]; then
    ID="$(sed -n 's/^ID=//p' "$OS_RELEASE" | tr -d '"')"; DISTRO="$ID"
    ID_LIKE="$(sed -n 's/^ID_LIKE=//p' "$OS_RELEASE" | tr -d '"')"
  fi
  case " $ID $ID_LIKE " in
    *" ubuntu "*|*" debian "*|*" raspbian "*) PKG=apt ;;
    *" fedora "*|*" rhel "*|*" centos "*) PKG=dnf; have dnf || PKG=yum ;;
    *" arch "*) PKG=pacman ;;
    *" opensuse "*|*" suse "*) PKG=zypper ;;
    *) PKG= ;;
  esac
  say "Dystrybucja: ${ID:-nieznana}${PKG:+ (pakiety: $PKG)}"
}

pkg_install() {   # pkg_install nazwa...
  case "$PKG" in
    # świeży Ubuntu w pierwszych minutach robi aktualizacje w tle (unattended-upgrades): czekamy na blokadę dpkg
    apt) penv DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 update -q
         penv DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 install -y -q "$@" ;;
    dnf|yum) penv "$PKG" install -y "$@" ;;
    pacman) penv pacman -Sy --noconfirm --needed "$@" ;;
    zypper) penv zypper -n install "$@" ;;
    *) die "Nieznana dystrybucja: zainstaluj sam: $* (oraz Docker: https://docs.docker.com/engine/install/) i uruchom ponownie." ;;
  esac
}

# nazwa pakietu z programem (różni się tylko python3 na Archu)
pkg_name() { if [[ $1 == python3 && $PKG == pacman ]]; then echo python; else echo "$1"; fi; }

hw_check() {
  local ram disk msg soft="$FORCE"
  # aktualizacja (jarvo update): flota już stoi na tym sprzęcie, a obraz zajmuje już swoje miejsce na dysku,
  # więc za mało RAM albo dysku tylko ostrzega zamiast przerywać
  [[ -f "$L/.installed" ]] && soft=1
  if [[ $OS == macos ]]; then ram=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
  # MemTotal jest mniejszy od kupionej pamięci (jądro rezerwuje część): „4 GB” to ok. 3,8 GB, więc zaokrąglamy
  else ram="$(awk '/^MemTotal:/ {print int($2/1048576 + 0.5)}' "$MEMINFO" 2>/dev/null || true)"; fi
  ram="${ram:-0}"
  disk="${JARVO_DISK_GB:-$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print int($4/1024/1024)}' || true)}"   # testy: udawany dysk
  say "RAM: ${ram} GB, wolne miejsce w $HOME: ${disk:-?} GB"
  if (( ram > 0 && ram < MIN_RAM_GB )); then
    msg="Za mało RAM (${ram} GB): flota potrzebuje ${REC_RAM_GB} GB (minimum ${MIN_RAM_GB})."
    if [[ $soft == 1 ]]; then warn "$msg"; else die "$msg JARVO_FORCE=1 wymusza."; fi
  elif (( ram > 0 && ram < REC_RAM_GB )); then warn "Polecamy ${REC_RAM_GB} GB RAM (masz ${ram} GB): agenci mogą działać wolniej."; fi
  if [[ -n $disk ]] && (( disk < MIN_DISK_GB )); then
    msg="Za mało miejsca (${disk} GB): obraz i dane floty potrzebują ${REC_DISK_GB} GB (minimum ${MIN_DISK_GB})."
    if [[ $soft == 1 ]]; then warn "$msg"; else die "$msg JARVO_FORCE=1 wymusza."; fi
  elif [[ -n $disk ]] && (( disk < REC_DISK_GB )); then warn "Polecamy ${REC_DISK_GB} GB wolnego miejsca (masz ${disk} GB)."; fi
}

tools_check() {
  local missing=() t
  for t in git curl python3 openssl; do have "$t" || missing+=("$(pkg_name "$t")"); done
  if [[ $OS == macos ]]; then mac_tools; return; fi
  if (( ${#missing[@]} )); then
    say "Doinstalowuję: ${missing[*]}"
    [[ $PKG == apt ]] && missing+=(ca-certificates)
    pkg_install "${missing[@]}"
  fi
}

# ---------------------------------------------------------------- macOS
brew_find() {
  BREW="$(command -v brew 2>/dev/null || true)"
  [[ -n $BREW ]] || for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [[ -x $b ]] && BREW=$b && break; done
  [[ -n $BREW ]]
}

brew_shellenv() {   # brew, bash, git, python z Homebrew w PATH tej sesji i każdego nowego terminala
  [[ $DRY == 1 && ! -x $BREW ]] && return 0
  eval "$("$BREW" shellenv)"
  local rc="$HOME/.zprofile" line
  line="eval \"\$($BREW shellenv)\""
  [[ $DRY == 1 ]] && return 0
  grep -qsF "$line" "$rc" || printf '\n# Homebrew (dodane przez instalator Jarvo)\n%s\n' "$line" >> "$rc"
  # bash czyta przy logowaniu pierwszy istniejący z .bash_profile, .bash_login, .profile: nowy .bash_profile
  # przesłoniłby czyjś .profile, więc dopisujemy do tego, który już jest
  rc="$HOME/.profile"; [[ -f $HOME/.bash_profile ]] && rc="$HOME/.bash_profile"
  grep -qsF "$line" "$rc" || printf '\n%s\n' "$line" >> "$rc"
}

mac_tools() {   # Homebrew (z narzędziami Xcode), bash 4+, git, Python 3, openssl
  if ! brew_find; then
    say "Instaluję Homebrew (menedżer programów macOS; dociąga narzędzia Xcode, kilka minut)…"
    need_root   # instalator Homebrew w trybie bez pytań wymaga zapamiętanego hasła sudo
    if [[ $DRY == 1 ]]; then run env NONINTERACTIVE=1 /bin/bash -c "\$(curl -fsSL $BREW_SCRIPT)"; BREW=/opt/homebrew/bin/brew
    else
      NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL "$BREW_SCRIPT")" < /dev/null \
        || die "Instalacja Homebrew się nie udała (log wyżej). Spróbuj ręcznie: https://brew.sh i uruchom polecenie ponownie."
      brew_find || die "Homebrew zainstalowany, ale nie widzę polecenia brew (/opt/homebrew/bin/brew)."
    fi
  fi
  brew_shellenv
  local f need=()
  # bash: skrypty floty potrzebują 4+ (macOS ma 3.2 z 2007 r.); python: Python z narzędzi Xcode bywa za stary
  for f in bash git python openssl@3; do
    if [[ $DRY == 1 ]] || ! "$BREW" list --formula "$f" >/dev/null 2>&1; then need+=("$f"); fi
  done
  if (( ${#need[@]} )); then
    say "Doinstalowuję: ${need[*]} (brew)"
    run env HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 "$BREW" install -q "${need[@]}" \
      || die "brew install ${need[*]} się nie udało."
  fi
  NEWBASH="$("$BREW" --prefix 2>/dev/null || echo /opt/homebrew)/bin/bash"
  if [[ $DRY != 1 ]]; then
    hash -r
    have python3 || die "Brak python3 po instalacji (brew install python)."
  fi
}

mac_vm_size() {   # procesory i pamięć dla maszyny wirtualnej Colimy: połowa Maca, flota potrzebuje ~6 GB
  local cpu ram
  cpu="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"; ram=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 8589934592) / 1073741824 ))
  COLIMA_CPU=$(( cpu / 2 )); (( COLIMA_CPU < 2 )) && COLIMA_CPU=2; (( COLIMA_CPU > 6 )) && COLIMA_CPU=6
  if (( ram >= 16 )); then COLIMA_MEM=8; elif (( ram >= 12 )); then COLIMA_MEM=6; else COLIMA_MEM=5; fi
}

mac_compose_plugin() {   # docker compose i buildx z Homebrew to wtyczki CLI: Docker musi wiedzieć, gdzie ich szukać
  local cfg="$HOME/.docker/config.json" dir
  dir="$("$BREW" --prefix 2>/dev/null || echo /opt/homebrew)/lib/docker/cli-plugins"
  [[ $DRY == 1 ]] && { run python3 - "$cfg" "$dir"; return; }
  mkdir -p "$HOME/.docker"
  python3 - "$cfg" "$dir" <<'PY'
import json, sys, pathlib
import shutil
p, d = pathlib.Path(sys.argv[1]), sys.argv[2]
c = json.loads(p.read_text() or "{}") if p.exists() else {}
dirs = c.setdefault("cliPluginsExtraDirs", [])
if d not in dirs:
    dirs.append(d)
# po odinstalowanym Docker Desktop zostaje credsStore "desktop": bez jego programu docker pull kończy się błędem
if c.get("credsStore") == "desktop" and not shutil.which("docker-credential-desktop"):
    del c["credsStore"]
p.write_text(json.dumps(c, indent=2) + "\n")
PY
}

mac_docker() {
  if have docker && docker info >/dev/null 2>&1; then
    local brak=()
    docker compose version >/dev/null 2>&1 || brak+=(docker-compose)
    docker buildx version >/dev/null 2>&1 || brak+=(docker-buildx)   # Colima postawiona wcześniej bez buildx
    if (( ${#brak[@]} )); then run "$BREW" install -q "${brak[@]}"; mac_compose_plugin; fi
    say "Docker: $(docker version -f '{{.Server.Version}}' 2>/dev/null || echo ok) (już działa: $(docker context show 2>/dev/null || echo domyślny))"
    return
  fi
  # OrbStack albo Docker Desktop zainstalowany, ale wyłączony: uruchamiamy go zamiast stawiać drugi silnik
  local app nazwa
  for app in OrbStack Docker; do
    [[ -d /Applications/$app.app ]] && ! have colima || continue
    nazwa=$app; [[ $app == Docker ]] && nazwa="Docker Desktop"
    say "Uruchamiam $nazwa…"
    run open -a "$app"
    [[ $app == OrbStack && -x $HOME/.orbstack/bin/docker ]] && PATH="$HOME/.orbstack/bin:$PATH"
    if [[ $DRY != 1 ]]; then
      for _ in $(seq 90); do docker info >/dev/null 2>&1 && break; sleep 2; done
      if docker info >/dev/null 2>&1; then
        say "Docker: $nazwa"
        docker buildx version >/dev/null 2>&1 || warn "$nazwa bez docker buildx: zaktualizuj $nazwa (budowa Komputera Jarva go wymaga)."
        return
      fi
      warn "$nazwa nie wstał w 3 minuty (pierwsze uruchomienie czeka na akceptację licencji w jego oknie). Instaluję Colimę."
    fi
    break
  done
  local need=() f nowa=0
  # docker-buildx: docker compose build (Komputer Jarva, obraz floty bez rejestru) bez tej wtyczki nie ruszy
  for f in colima docker docker-compose docker-buildx; do
    # polecenie docker z Docker Desktop (/usr/local/bin/docker na Macu z Intelem): brew go nie nadpisze, więc zostaje
    [[ $f == docker && $DRY != 1 ]] && have docker && continue
    if [[ $DRY == 1 ]] || ! "$BREW" list --formula "$f" >/dev/null 2>&1; then
      need+=("$f"); [[ $f == colima ]] && nowa=1
    fi
  done
  # Virtualization.framework (vz) jest od macOS 13; starszy system potrzebuje QEMU
  local vm=(--vm-type vz --mount-type virtiofs)
  if (( MACVER > 0 && MACVER < 13 )); then vm=(--vm-type qemu); need+=(qemu); fi
  if (( ${#need[@]} )); then
    say "Instaluję Docker bez Docker Desktop: ${need[*]} (Colima: darmowa maszyna wirtualna z Dockerem)…"
    # po Docker Desktop zostają jego dowiązania w /usr/local/bin (docker-compose…): brew instaluje, ale nie podlinkuje
    run env HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 "$BREW" install -q "${need[@]}" \
      || run "$BREW" link --overwrite "${need[@]}" \
      || die "brew install ${need[*]} się nie udało."
  fi
  mac_compose_plugin
  mac_vm_size
  if [[ $DRY == 1 ]] || ! colima status >/dev/null 2>&1; then
    say "Uruchamiam Colimę (${COLIMA_CPU} procesory, ${COLIMA_MEM} GB RAM, dysk do 60 GB; pierwszy raz 1–3 minuty)…"
    run colima start --cpu "$COLIMA_CPU" --memory "$COLIMA_MEM" --disk 60 "${vm[@]}" \
      || die "Colima nie wstała (colima status; log: ~/.colima/_lima/colima/ha.stderr.log). Włącz wirtualizację i spróbuj ponownie."
  fi
  # start Colimy przy logowaniu włącza `jarvo autostart on` (LaunchAgent); kontenery wstają same (restart: unless-stopped)
  if [[ $DRY != 1 ]]; then
    for _ in $(seq 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
    docker info >/dev/null 2>&1 || die "Docker w Colimie nie odpowiada (colima status, docker context ls)."
    docker compose version >/dev/null 2>&1 || die "Brak docker compose (brew install docker-compose; ~/.docker/config.json: cliPluginsExtraDirs)."
    docker buildx version >/dev/null 2>&1 || die "Brak docker buildx (brew install docker-buildx; ~/.docker/config.json: cliPluginsExtraDirs)."
    # Colimę zainstalował instalator: jarvo uninstall --all może usunąć jej maszynę wirtualną (colima_usun w bin/jarvo)
    [[ $nowa == 1 && -d $L ]] && touch "$L/.colima"
  fi
  say "Docker: Colima ($(docker version -f '{{.Server.Version}}' 2>/dev/null || echo ok))"
}

docker_start_bg() {   # bez systemd i bez działającego skryptu init (kontener, minimalny system): demon w tle
  warn "Uruchamiam dockerd w tle (po restarcie komputera: sudo dockerd &)."
  as_root sh -c 'nohup dockerd >/var/log/dockerd.log 2>&1 </dev/null &' || true
}

docker_start() {   # nigdy nie przerywa instalacji: docker_wait sprawdza wynik
  if [[ -d /run/systemd/system ]] && have systemctl; then
    as_root systemctl enable --now docker >/dev/null 2>&1 || as_root systemctl start docker || true
  elif have service && [[ -e /etc/init.d/docker ]]; then
    as_root service docker start >/dev/null 2>&1 || docker_start_bg
  else
    docker_start_bg
  fi
}

docker_wait() {   # docker_wait [sekundy]: demon gotowy? (jako root: grupa docker może jeszcze nie działać w tej sesji)
  need_root
  for _ in $(seq "${1:-30}"); do
    if [[ -n $SUDO ]]; then $SUDO docker info >/dev/null 2>&1 && return 0
    else docker info >/dev/null 2>&1 && return 0; fi
    sleep 1
  done
  return 1
}

rpm_docker() {   # AlmaLinux, Oracle Linux: repo Dockera dla CentOS (get.docker.com zna tylko centos, rhel, rocky, fedora)
  say "Instaluję Docker Engine (repo download.docker.com dla CentOS)…"
  pkg_install dnf-plugins-core
  penv dnf config-manager --add-repo "$DOCKER_RPM_REPO" 2>/dev/null \
    || penv dnf config-manager addrepo --from-repofile="$DOCKER_RPM_REPO"   # dnf5
  pkg_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

docker_install() {
  local tmp apt_cfg
  case "$DISTRO" in
    almalinux|ol) rpm_docker; return ;;
    amzn) die "Amazon Linux: zainstaluj Dockera sam (sudo dnf install -y docker) z wtyczkami compose i buildx (https://docs.docker.com/compose/install/linux/) i uruchom polecenie ponownie. Prościej: serwer z Ubuntu 24.04." ;;
  esac
  say "Instaluję Docker Engine ($( [[ $PKG == pacman || $PKG == zypper ]] && echo "pakiety $PKG" || echo "get.docker.com" ))…"
  case "$PKG" in
    apt|dnf|yum)
      tmp="$(mktemp)"; apt_cfg="$(mktemp)"
      if [[ $DRY == 1 ]]; then printf '%s  $ curl -fsSL %s -o %s%s\n' "$D" "$DOCKER_SCRIPT" "$tmp" "$N"
      else curl -fsSL "$DOCKER_SCRIPT" -o "$tmp" || die "Nie udało się pobrać $DOCKER_SCRIPT."; fi
      # apt-get w skrypcie Dockera też czeka na blokadę dpkg (aktualizacje w tle świeżego systemu)
      printf 'DPkg::Lock::Timeout "600";\n' > "$apt_cfg"; chmod 644 "$apt_cfg"
      penv APT_CONFIG="$apt_cfg" sh "$tmp" \
        || die "Instalacja Dockera skryptem get.docker.com się nie udała (log wyżej). Zainstaluj Dockera według https://docs.docker.com/engine/install/ i uruchom polecenie ponownie."
      rm -f "$tmp" "$apt_cfg" ;;
    pacman) pkg_install docker docker-compose docker-buildx ;;
    zypper) pkg_install docker docker-compose ;;
    *) die "Nie umiem zainstalować Dockera na tej dystrybucji. Zainstaluj sam: https://docs.docker.com/engine/install/ i uruchom polecenie ponownie." ;;
  esac
}

compose_install() {
  say "Doinstalowuję docker compose v2…"
  case "$PKG" in
    # repo Dockera (docker-ce) ma docker-compose-plugin; Docker z dystrybucji: Ubuntu/Debian docker-compose-v2, Fedora docker-compose
    apt) pkg_install docker-compose-plugin || pkg_install docker-compose-v2 ;;
    dnf|yum) pkg_install docker-compose-plugin || pkg_install docker-compose ;;
    pacman|zypper) pkg_install docker-compose ;;
    *) die "Brak docker compose v2. Zaktualizuj Dockera: https://docs.docker.com/compose/install/" ;;
  esac
}

buildx_install() {   # wtyczka buildx: bez niej docker compose build (Komputer Jarva, obraz floty bez rejestru) nie ruszy
  say "Doinstalowuję docker buildx (budowa obrazów)…"
  case "$PKG" in
    apt|dnf|yum) pkg_install docker-buildx-plugin || pkg_install docker-buildx ;;   # repo Dockera albo pakiet dystrybucji
    pacman|zypper) pkg_install docker-buildx ;;
    *) false ;;
  esac || warn "Bez docker buildx: obraz floty pobierzesz z rejestru, ale budowa na miejscu (jarvo komputer on) nie ruszy. Zainstaluj pakiet docker-buildx i uruchom polecenie ponownie."
}

docker_group() {   # użytkownik bez roota dostaje grupę docker; ta sesja logowania jeszcze jej nie ma (jarvo radzi sobie przez sg)
  [[ -n $SUDO ]] || return 0
  local me; me="$(id -un)"
  getent group docker >/dev/null 2>&1 || as_root groupadd docker
  if ! getent group docker 2>/dev/null | cut -d: -f4 | tr ',' '\n' | grep -qx "$me"; then
    say "Dodaję $me do grupy docker"; as_root usermod -aG docker "$me"
  fi
  id -nG | tr ' ' '\n' | grep -qx docker || NEED_GROUP=1
}

wsl_iptables_fix() {   # WSL bez systemd: Docker potrzebuje iptables-legacy (nft w WSL nie działa)
  [[ $OS == wsl ]] || return 1
  [[ -x /usr/sbin/iptables-legacy ]] || return 1
  warn "Docker nie wstał: przełączam iptables na wariant legacy (WSL)"
  as_root update-alternatives --set iptables /usr/sbin/iptables-legacy >/dev/null 2>&1 || true
  as_root update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy >/dev/null 2>&1 || true
  docker_start
}

docker_check() {
  if [[ $OS == macos ]]; then mac_docker; return; fi
  # Docker już działa jako Ty (Docker Desktop z integracją WSL, wcześniejsza instalacja): nic do roboty, zero sudo
  if have docker && docker info >/dev/null 2>&1; then
    # Docker bez roota (rootless, userns-remap): uid 10000 w kontenerze to inny uid na dysku, a dane floty
    # i klucze należą do uid 10000 hosta, więc flota nie zapisze danych; mówimy to od razu, nie w połowie
    if docker info -f '{{.SecurityOptions}}' 2>/dev/null | grep -qE 'rootless|userns'; then
      die "Docker działa bez roota (rootless albo userns-remap): flota go nie obsługuje (dane należą do uid 10000). Użyj zwykłego Dockera (https://docs.docker.com/engine/install/) i uruchom polecenie ponownie."
    fi
    docker compose version >/dev/null 2>&1 || compose_install
    docker buildx version >/dev/null 2>&1 || buildx_install
    say "Docker: $(docker version -f '{{.Server.Version}}' 2>/dev/null || echo ok)"
    return
  fi
  if ! have docker; then
    docker_install
    [[ $DRY == 1 ]] && return
  fi
  docker compose version >/dev/null 2>&1 || compose_install
  docker buildx version >/dev/null 2>&1 || buildx_install
  docker_group
  if ! docker_wait 3; then
    docker_start
    if ! docker_wait; then
      wsl_iptables_fix || true
      docker_wait 10 || { docker_start_bg; docker_wait; } \
        || die "Docker nie wstał. Sprawdź: sudo systemctl status docker (bez systemd: sudo dockerd; log: /var/log/dockerd.log)."
    fi
  fi
  if [[ -n $SUDO ]]; then say "Docker: $($SUDO docker version -f '{{.Server.Version}}' 2>/dev/null || echo ok)"
  else say "Docker: $(docker version -f '{{.Server.Version}}' 2>/dev/null || echo ok)"; fi
}

port_check() {
  [[ $DRY == 1 ]] && return 0
  # własny kontener na tym porcie to nie konflikt (ponowna instalacja = aktualizacja)
  if docker info >/dev/null 2>&1; then docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx jarvo-hermes && return 0
  elif [[ -n $SUDO ]]; then need_root; $SUDO docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx jarvo-hermes && return 0; fi
  local p
  for p in "$PORT" 9120 9122; do   # dashboard, podgląd stron agentów, ekran telefonu testowego (docker-compose.yml)
    if (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then
      die "Port $p jest zajęty przez inny program. Zwolnij go ($( [[ $OS == macos ]] && echo "lsof -i :$p" || echo "ss -ltnp | grep $p" )) i uruchom polecenie ponownie."
    fi
  done
  return 0
}

GITAUTH=()
token_use() {   # klucz dostępu do prywatnego repo: nagłówek dla gita (jak actions/checkout), nigdy w logu
  [[ -n $TOKEN ]] || return 0
  GITAUTH=(-c "http.https://github.com/.extraheader=AUTHORIZATION: basic $(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')")
}
token_ask() {   # repo nie daje się pobrać anonimowo: pytamy o klucz (tylko w terminalu)
  [[ -z $TOKEN && $DRY != 1 ]] || return 1
  { : < /dev/tty; } 2>/dev/null || return 1
  warn "Nie mogę pobrać Jarvo anonimowo (prywatna kopia repo albo brak dostępu)."
  read -rsp "Wklej klucz dostępu od właściciela (token GitHub; nie będzie widoczny): " TOKEN < /dev/tty; echo
  [[ -n $TOKEN ]] || return 1
  token_use
}
token_save() {   # aktualizacje (jarvo update, przycisk w dashboardzie) pobierają tym samym kluczem
  [[ -n $TOKEN && $DRY != 1 ]] || return 0
  git -C "$DIR" config --local "http.https://github.com/.extraheader" "AUTHORIZATION: basic $(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')"
  chmod 600 "$DIR/.git/config"
}
git_auth() { GIT_TERMINAL_PROMPT=0 git ${GITAUTH[@]+"${GITAUTH[@]}"} "$@"; }
GIT_ERR=""
git_try() {   # git_try polecenie…: do 3 prób. Chwilowy błąd (sieć, równoległy git fetch pomocnika aktualizacji
  # updater.py starej instalacji: „incorrect old value provided”, „cannot lock ref”) mija; odmowa dostępu nie, więc bez ponawiania
  local i
  for i in 1 2 3; do
    GIT_ERR="$("$@" 2>&1 >/dev/null)" && return 0
    git_auth_error && return 1
    if [[ $i != 3 ]]; then warn "Git: chwilowy błąd ($(git_err)), próbuję jeszcze raz…"; sleep "${JARVO_GIT_PAUSE:-3}"; fi
  done
  return 1
}
git_auth_error() {   # GitHub odmówił dostępu (prywatna kopia repo, zły klucz): tylko wtedy pytamy o klucz
  case "$GIT_ERR" in
    *"could not read Username"*|*"Authentication failed"*|*"Repository not found"*|*"returned error: 401"*|*"returned error: 403"*) return 0 ;;
  esac
  return 1
}
git_err() { printf '%s\n' "$GIT_ERR" | sed '/^[[:space:]]*$/d' | tail -1; }
repo_clone() { rm -rf "$DIR"; git_auth clone -q --depth 50 "$@" "$REPO" "$DIR"; }

repo_sync() {
  token_use
  if [[ -d "$DIR/.git" ]]; then
    [[ -n $BRANCH ]] || BRANCH="$(git -C "$DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
    say "Aktualizuję $DIR (gałąź $BRANCH)"
    if [[ $DRY != 1 && -n "$(git -C "$DIR" status --porcelain 2>/dev/null)" ]]; then
      die "W $DIR są lokalne zmiany. Zapisz je (git -C $DIR stash) albo ustaw JARVO_DIR=inny/katalog."
    fi
    token_save
    if [[ $DRY == 1 ]]; then run git_auth -C "$DIR" fetch -q origin "$BRANCH"
    elif ! git_try git_auth -C "$DIR" fetch -q origin "$BRANCH"; then
      { git_auth_error && token_ask && token_save && git_try git_auth -C "$DIR" fetch -q origin "$BRANCH"; } \
        || die "Nie udało się pobrać $REPO ($BRANCH): $(git_err)"
    fi
    run git -C "$DIR" checkout -q "$BRANCH" || die "Nie udało się przełączyć na gałąź $BRANCH."
    run git -C "$DIR" merge -q --ff-only "origin/$BRANCH" || die "Nie udało się zaktualizować $DIR (git -C $DIR status)."
  else
    [[ -e "$DIR" ]] && die "$DIR istnieje i nie jest repozytorium Jarvo. Ustaw JARVO_DIR=inny/katalog."
    say "Pobieram Jarvo do $DIR${BRANCH:+ (gałąź $BRANCH)}"
    local b=(); [[ -n $BRANCH ]] && b=(-b "$BRANCH")
    if [[ $DRY == 1 ]]; then run git_auth clone -q --depth 50 ${b[@]+"${b[@]}"} "$REPO" "$DIR"
    elif ! git_try repo_clone ${b[@]+"${b[@]}"}; then
      { git_auth_error && token_ask && git_try repo_clone ${b[@]+"${b[@]}"}; } \
        || { rm -rf "$DIR"; die "Nie udało się pobrać $REPO${BRANCH:+ ($BRANCH)}: $(git_err). Sprawdź internet albo klucz dostępu (JARVO_TOKEN)."; }
    fi
    token_save
  fi
  # własny katalog instalacji zapamiętany dla polecenia jarvo (bez zmiennej w każdym terminalu)
  if [[ -n "${JARVO_LOCAL:-}" && $DRY != 1 ]]; then printf '%s\n' "$L" > "$DIR/.jarvo-local"; fi
}

link_cli() {
  local target="$DIR/bin/jarvo" l
  for l in /usr/local/bin/jarvo "$HOME/.local/bin/jarvo" /opt/homebrew/bin/jarvo; do   # już jest (aktualizacja)
    if [[ -L $l && "$(readlink "$l")" == "$target" ]]; then say "Polecenie jarvo: $l"; return; fi
  done
  if [[ $OS == macos && -n $BREW ]]; then   # katalog Homebrew jest w PATH i należy do Ciebie: bez sudo
    local bin; bin="$("$BREW" --prefix 2>/dev/null || echo /opt/homebrew)/bin"
    run ln -sfn "$target" "$bin/jarvo"; say "Polecenie jarvo: $bin/jarvo"; return
  fi
  if [[ -d /usr/local/bin ]] && as_root ln -sfn "$target" /usr/local/bin/jarvo 2>/dev/null; then
    say "Polecenie jarvo: /usr/local/bin/jarvo"
  else
    run mkdir -p "$HOME/.local/bin"; run ln -sfn "$target" "$HOME/.local/bin/jarvo"
    say "Polecenie jarvo: ~/.local/bin/jarvo"
    case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) warn "Dodaj ~/.local/bin do PATH (nowy terminal zwykle robi to sam)." ;; esac
  fi
}

fleet_up() {
  local jarvo="$DIR/bin/jarvo" TTY=/dev/null
  if { : < /dev/tty; } 2>/dev/null; then TTY=/dev/tty; fi
  if [[ "${JARVO_SETUP_ONLY:-0}" == 1 ]]; then
    say "JARVO_SETUP_ONLY=1: system i repo gotowe. Flotę uruchomisz poleceniem: jarvo up"; return
  fi
  if [[ $DRY == 1 ]]; then run "$jarvo" up; return; fi
  # wymagania hosta są już spełnione: zapis przed `jarvo up`, żeby deploy.sh nie prosił o jarvo update
  mkdir -p "$L/compose" && printf '%s\n' "$HOST_VERSION" > "$L/compose/.host-version"
  if [[ -f "$L/.installed" ]]; then say "Aktualizuję flotę…"; else
    say "Stawiam flotę (pierwszy raz kilka–kilkanaście minut: budowa obrazu)…"
    # local-up.sh nadaje plikom z kluczami grupę kontenera (sudo): hasło sprawdzamy teraz, nie w połowie
    # (sudo pamięta je kilka minut, a Homebrew, Colima i Docker trwają dłużej)
    SUDO_ASKED=0; need_root
  fi
  # pytania instalatora czytamy z terminala, nie z potoku curl | bash; jarvo sam sięga po grupę docker (sg)
  # klucz dostępu trafia do jarvo up tylko jako zmienna: obraz z prywatnego rejestru (scripts/obraz.sh)
  JARVO_TOKEN="$TOKEN" JARVO_LOCAL="$L" "${NEWBASH:-bash}" "$jarvo" up < "$TTY"
  if [[ "${JARVO_NO_AUTOSTART:-0}" != 1 ]]; then
    "${NEWBASH:-bash}" "$jarvo" autostart on 2>/dev/null \
      || if [[ $OS == macos ]]; then warn "LaunchAgent się nie włączył (launchctl): flota działa, ale po restarcie Maca uruchom ją: jarvo up (albo jarvo autostart on)."
         else warn "Bez autostartu (brak usług systemd użytkownika): pomocnik aktualizacji działa w tle do wylogowania (jarvo autostart on, gdy zechcesz)."; fi
  fi
  [[ "${JARVO_NO_OPEN:-0}" == 1 ]] || "${NEWBASH:-bash}" "$jarvo" open >/dev/null 2>&1 || true
}

main() {
  [[ "${JARVO_NO_BANNER:-0}" == 1 ]] || printf '\n%s  ██████  %sJ A R V O%s\n%s  ██████  %sfrom idea to reality.%s\n\n' "$W" "$W" "$N" "$R" "$D" "$N"
  [[ $DRY == 1 ]] && warn "Na sucho (JARVO_DRY_RUN=1): tylko pokazuję, co bym zrobił."
  # curl | bash: stdin to potok z pobranym skryptem; hasło sudo i pytania czytamy z terminala
  if [[ ! -t 0 ]] && { : < /dev/tty; } 2>/dev/null; then exec < /dev/tty; fi
  detect_os
  proxy_setup
  [[ $OS == macos ]] || detect_pkg
  hw_check
  if [[ $DRY != 1 ]]; then
    # log całej instalacji (bez kluczy: local-up.sh czyta je bez echa)
    mkdir -p "$L"
    exec > >(tee -a "$L/install.log") 2>&1
    printf '== %s install.sh %s/%s\n' "$(date '+%F %T')" "$OS" "$ARCH"
  fi
  tools_check
  docker_check
  port_check
  repo_sync
  link_cli
  fleet_up
  if [[ $DRY == 1 ]]; then say "Koniec próby na sucho."; return; fi
  printf '\n%s▌%s Gotowe. Dashboard: %shttp://localhost:%s/jarvo%s   (polecenia: jarvo help)\n' "$G" "$N" "$W" "$PORT" "$N"
  [[ $NEED_GROUP == 1 ]] && warn "Docker bez sudo w nowych terminalach zadziała po ponownym zalogowaniu (jarvo radzi sobie już teraz)."
  sleep 0.2   # tee ma zdążyć wypisać ostatnie linie
}

main "$@"; exit   # exit od razu: po przepięciu stdin na terminal bash nie może czytać z niego poleceń
