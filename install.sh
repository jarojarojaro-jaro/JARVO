#!/usr/bin/env bash
# Instalator Jarvo: Linux, WSL2, macOS. Jedno polecenie ze strony:
#
#   curl -fsSL https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/HEAD/install.sh | bash
#
# Linux i WSL: sprawdza sprzęt (procesor, RAM, dysk), doinstalowuje brakujące programy (git, curl, python3,
# openssl) menedżerem pakietów dystrybucji (apt, dnf/yum, pacman, zypper), instaluje Docker Engine
# (get.docker.com; Arch i openSUSE z pakietów), uruchamia demona, dodaje Cię do grupy docker, pobiera repo
# do ~/jarvo (albo je aktualizuje), instaluje polecenie `jarvo` i uruchamia `jarvo up` (scripts/local-up.sh):
# pytania o dostawcę modeli, flota w Dockerze, healthchecki, pomocnik aktualizacji jako usługa systemd
# użytkownika, otwarcie dashboardu. Ponowne wklejenie tego samego polecenia = aktualizacja.
# macOS: git (Xcode CLT), bash 4+ z Homebrew i działający Docker (Docker Desktop/OrbStack) muszą już być;
# automatyczna instalacja Dockera na macOS i pełny Windows: docs/INSTALER.md (etapy 3 i 4).
#
# Zmienne (wszystkie opcjonalne):
#   JARVO_DIR, JARVO_LOCAL       katalog repo (~/jarvo) i instalacji floty (~/jarvo-local)
#   JARVO_REPO, JARVO_BRANCH     adres git i gałąź (domyślnie gałąź główna repo)
#   JARVO_PROVIDER, JARVO_KEY    dostawca modeli (openrouter, commandcode-anthropic, commandcode, openai-codex)
#                                i klucz; z JARVO_YES=1 instalator o nic nie pyta (bez klucza: GUI działa,
#                                klucz dodasz w dashboardzie)
#   JARVO_SETUP_ONLY=1           system, Docker i repo tak, floty nie uruchamiaj (potem: jarvo up)
#   JARVO_NO_AUTOSTART=1         bez usługi systemd pomocnika aktualizacji
#   JARVO_FORCE=1                mimo za małego RAM albo dysku
#   JARVO_DRY_RUN=1              tylko pokaż, co by zrobił (nic nie instaluje)
#
# Cały skrypt siedzi w funkcji main, więc bash wykonuje go dopiero po pobraniu w całości: ucięty transfer
# nic nie uruchomi. Pytania czyta z terminala (/dev/tty), nie z potoku curl | bash. Klucze nigdy nie trafiają
# do logu (~/jarvo-local/install.log).
set -euo pipefail

REPO="${JARVO_REPO:-https://github.com/jarojarojaro-jaro/JARVO.git}"
BRANCH="${JARVO_BRANCH:-}"          # pusta = gałąź główna repo (klon bez -b, aktualizacja bieżącej)
DIR="${JARVO_DIR:-$HOME/jarvo}"
L="${JARVO_LOCAL:-$HOME/jarvo-local}"
DRY="${JARVO_DRY_RUN:-0}"
FORCE="${JARVO_FORCE:-0}"
OS_RELEASE="${JARVO_OS_RELEASE:-/etc/os-release}"   # testy: udawana dystrybucja
MEMINFO="${JARVO_MEMINFO:-/proc/meminfo}"             # testy: udawany RAM
MIN_RAM_GB=4; REC_RAM_GB=8; MIN_DISK_GB=10; REC_DISK_GB=20
PORT=9119
DOCKER_SCRIPT="https://get.docker.com"

if [[ -t 1 ]]; then R=$'\e[38;2;212;33;61m'; W=$'\e[1;38;2;242;241;232m'; G=$'\e[38;2;184;255;61m'; Y=$'\e[33m'; D=$'\e[2m'; N=$'\e[0m'
else R=; W=; G=; Y=; D=; N=; fi
say() { printf '%s▌%s %s\n' "$R" "$N" "$*"; }
warn() { printf '%s!%s %s\n' "$Y" "$N" "$*"; }
die() { printf '%s✗%s %s\n' "$R" "$N" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
# na sucho: pokaż polecenie zamiast je wykonać
run() { if [[ $DRY == 1 ]]; then printf '%s  $ %s%s\n' "$D" "$*" "$N"; else "$@"; fi; }
as_root() { if [[ -n $SUDO ]]; then run $SUDO "$@"; else run "$@"; fi; }
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

OS=; ARCH=; PKG=; SUDO=; NEWBASH=; NEED_GROUP=0

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
    ID="$(sed -n 's/^ID=//p' "$OS_RELEASE" | tr -d '"')"
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
    apt) penv DEBIAN_FRONTEND=noninteractive apt-get update -q
         penv DEBIAN_FRONTEND=noninteractive apt-get install -y -q "$@" ;;
    dnf|yum) penv "$PKG" install -y "$@" ;;
    pacman) penv pacman -Sy --noconfirm --needed "$@" ;;
    zypper) penv zypper -n install "$@" ;;
    *) die "Nieznana dystrybucja: zainstaluj sam: $* (oraz Docker: https://docs.docker.com/engine/install/) i uruchom ponownie." ;;
  esac
}

# nazwa pakietu z programem (różni się tylko python3 na Archu)
pkg_name() { if [[ $1 == python3 && $PKG == pacman ]]; then echo python; else echo "$1"; fi; }

hw_check() {
  local ram disk
  if [[ $OS == macos ]]; then ram=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
  else ram="$(awk '/^MemTotal:/ {print int($2/1024/1024)}' "$MEMINFO" 2>/dev/null || true)"; fi
  ram="${ram:-0}"
  disk="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print int($4/1024/1024)}' || true)"
  say "RAM: ${ram} GB, wolne miejsce w $HOME: ${disk:-?} GB"
  if (( ram > 0 && ram < MIN_RAM_GB )); then
    [[ $FORCE == 1 ]] || die "Za mało RAM (${ram} GB): flota potrzebuje ${REC_RAM_GB} GB (minimum ${MIN_RAM_GB}). JARVO_FORCE=1 wymusza."
  elif (( ram > 0 && ram < REC_RAM_GB )); then warn "Polecamy ${REC_RAM_GB} GB RAM (masz ${ram} GB): agenci mogą działać wolniej."; fi
  if [[ -n $disk ]] && (( disk < MIN_DISK_GB )); then
    [[ $FORCE == 1 ]] || die "Za mało miejsca (${disk} GB): obraz i dane floty potrzebują ${REC_DISK_GB} GB (minimum ${MIN_DISK_GB}). JARVO_FORCE=1 wymusza."
  elif [[ -n $disk ]] && (( disk < REC_DISK_GB )); then warn "Polecamy ${REC_DISK_GB} GB wolnego miejsca (masz ${disk} GB)."; fi
}

tools_check() {
  local missing=() t
  for t in git curl python3 openssl; do have "$t" || missing+=("$(pkg_name "$t")"); done
  if [[ $OS == macos ]]; then
    have git || die "Brak gita. Zainstaluj narzędzia Xcode: xcode-select --install (potem uruchom polecenie ponownie)."
    have python3 || die "Brak Pythona 3: brew install python (albo xcode-select --install)."
    have openssl || die "Brak openssl: brew install openssl."
    # macOS ma basha 3.2 z 2007 roku; skrypty floty potrzebują basha 4+
    if (( BASH_VERSINFO[0] < 4 )); then
      NEWBASH="$(command -v /opt/homebrew/bin/bash /usr/local/bin/bash 2>/dev/null | head -1 || true)"
      if [[ -z $NEWBASH ]]; then
        have brew || die "Potrzebny nowszy bash. Zainstaluj Homebrew (https://brew.sh) i uruchom polecenie ponownie."
        say "Instaluję nowszego basha (brew install bash)…"; run brew install bash >/dev/null
        NEWBASH="$(brew --prefix)/bin/bash"
      fi
    fi
    return
  fi
  if (( ${#missing[@]} )); then
    say "Doinstalowuję: ${missing[*]}"
    [[ $PKG == apt ]] && missing+=(ca-certificates)
    pkg_install "${missing[@]}"
  fi
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
  for _ in $(seq "${1:-30}"); do
    if [[ -n $SUDO ]]; then $SUDO docker info >/dev/null 2>&1 && return 0
    else docker info >/dev/null 2>&1 && return 0; fi
    sleep 1
  done
  return 1
}

docker_install() {
  local tmp
  say "Instaluję Docker Engine ($( [[ $PKG == pacman || $PKG == zypper ]] && echo "pakiety $PKG" || echo "get.docker.com" ))…"
  case "$PKG" in
    apt|dnf|yum)
      tmp="$(mktemp)"
      if [[ $DRY == 1 ]]; then printf '%s  $ curl -fsSL %s -o %s%s\n' "$D" "$DOCKER_SCRIPT" "$tmp" "$N"
      else curl -fsSL "$DOCKER_SCRIPT" -o "$tmp" || die "Nie udało się pobrać $DOCKER_SCRIPT."; fi
      penv sh "$tmp"
      rm -f "$tmp" ;;
    pacman) pkg_install docker docker-compose ;;
    zypper) pkg_install docker docker-compose ;;
    *) die "Nie umiem zainstalować Dockera na tej dystrybucji. Zainstaluj sam: https://docs.docker.com/engine/install/ i uruchom polecenie ponownie." ;;
  esac
}

compose_install() {
  say "Doinstalowuję docker compose v2…"
  case "$PKG" in
    apt|dnf|yum) pkg_install docker-compose-plugin ;;
    pacman|zypper) pkg_install docker-compose ;;
    *) die "Brak docker compose v2. Zaktualizuj Dockera: https://docs.docker.com/compose/install/" ;;
  esac
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
  if [[ $OS == macos ]]; then
    have docker || die "Brak Dockera. Zainstaluj Docker Desktop (https://www.docker.com/products/docker-desktop/) albo OrbStack i uruchom polecenie ponownie."
    docker info >/dev/null 2>&1 || die "Docker nie działa. Uruchom Docker Desktop (albo OrbStack) i spróbuj ponownie."
    docker compose version >/dev/null 2>&1 || die "Brak docker compose v2. Zaktualizuj Docker Desktop."
    say "Docker: $(docker version -f '{{.Server.Version}}' 2>/dev/null || echo ok)"
    return
  fi
  if ! have docker; then
    docker_install
    [[ $DRY == 1 ]] && return
  fi
  docker compose version >/dev/null 2>&1 || compose_install
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
  if [[ -n $SUDO ]]; then $SUDO docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx jarvo-hermes && return 0
  else docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx jarvo-hermes && return 0; fi
  if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
    die "Port $PORT jest zajęty przez inny program. Zwolnij go (ss -ltnp | grep $PORT) i uruchom polecenie ponownie."
  fi
  return 0
}

repo_sync() {
  if [[ -d "$DIR/.git" ]]; then
    [[ -n $BRANCH ]] || BRANCH="$(git -C "$DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
    say "Aktualizuję $DIR (gałąź $BRANCH)"
    if [[ $DRY != 1 && -n "$(git -C "$DIR" status --porcelain 2>/dev/null)" ]]; then
      die "W $DIR są lokalne zmiany. Zapisz je (git -C $DIR stash) albo ustaw JARVO_DIR=inny/katalog."
    fi
    run git -C "$DIR" fetch -q origin "$BRANCH" || die "Nie udało się pobrać $REPO ($BRANCH)."
    run git -C "$DIR" checkout -q "$BRANCH" || die "Nie udało się przełączyć na gałąź $BRANCH."
    run git -C "$DIR" merge -q --ff-only "origin/$BRANCH" || die "Nie udało się zaktualizować $DIR (git -C $DIR status)."
  else
    [[ -e "$DIR" ]] && die "$DIR istnieje i nie jest repozytorium Jarvo. Ustaw JARVO_DIR=inny/katalog."
    say "Pobieram Jarvo do $DIR${BRANCH:+ (gałąź $BRANCH)}"
    if [[ -n $BRANCH ]]; then run git clone -q --depth 50 -b "$BRANCH" "$REPO" "$DIR" || die "Nie udało się pobrać $REPO ($BRANCH)."
    else run git clone -q --depth 50 "$REPO" "$DIR" || die "Nie udało się pobrać $REPO."; fi
  fi
  # własny katalog instalacji zapamiętany dla polecenia jarvo (bez zmiennej w każdym terminalu)
  if [[ -n "${JARVO_LOCAL:-}" && $DRY != 1 ]]; then printf '%s\n' "$L" > "$DIR/.jarvo-local"; fi
}

link_cli() {
  local target="$DIR/bin/jarvo"
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
  if [[ -f "$L/.installed" ]]; then say "Aktualizuję flotę…"; else say "Stawiam flotę (pierwszy raz kilka–kilkanaście minut: budowa obrazu)…"; fi
  # pytania instalatora czytamy z terminala, nie z potoku curl | bash; jarvo sam sięga po grupę docker (sg)
  JARVO_LOCAL="$L" "${NEWBASH:-bash}" "$jarvo" up < "$TTY"
  if [[ $OS != macos && "${JARVO_NO_AUTOSTART:-0}" != 1 ]]; then
    "${NEWBASH:-bash}" "$jarvo" autostart on 2>/dev/null \
      || warn "Bez usług systemd użytkownika: pomocnik aktualizacji działa w tle do wylogowania (jarvo autostart on, gdy zechcesz)."
  fi
  "${NEWBASH:-bash}" "$jarvo" open >/dev/null 2>&1 || true
}

main() {
  printf '\n%s  ██████  %sJ A R V O%s\n%s  ██████  %sfrom idea to reality.%s\n\n' "$W" "$W" "$N" "$R" "$D" "$N"
  [[ $DRY == 1 ]] && warn "Na sucho (JARVO_DRY_RUN=1): tylko pokazuję, co bym zrobił."
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
  printf '\n%s▌%s Gotowe. Dashboard: %shttp://localhost:%s/base%s   (polecenia: jarvo help)\n' "$G" "$N" "$W" "$PORT" "$N"
  [[ $NEED_GROUP == 1 ]] && warn "Docker bez sudo w nowych terminalach zadziała po ponownym zalogowaniu (jarvo radzi sobie już teraz)."
  sleep 0.2   # tee ma zdążyć wypisać ostatnie linie
}

main "$@"
