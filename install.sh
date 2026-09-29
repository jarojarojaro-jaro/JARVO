#!/usr/bin/env bash
# Instalator Jarvo: macOS, Linux, Windows (WSL2). Jedno polecenie ze strony:
#
#   curl -fsSL https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.sh | bash
#
# Sprawdza wymagania (git, Docker, python3, openssl), pobiera repo do ~/jarvo (albo je aktualizuje)
# i uruchamia scripts/local-up.sh, który pyta o dostawcę modeli i stawia flotę w Dockerze.
# Zmienne: JARVO_DIR (katalog repo), JARVO_REPO (adres git), JARVO_BRANCH (gałąź).
set -euo pipefail

REPO="${JARVO_REPO:-https://github.com/jarojarojaro-jaro/JARVO.git}"
BRANCH="${JARVO_BRANCH:-main}"
DIR="${JARVO_DIR:-$HOME/jarvo}"

if [[ -t 1 ]]; then R=$'\e[38;2;212;33;61m'; W=$'\e[1;38;2;242;241;232m'; G=$'\e[38;2;184;255;61m'; D=$'\e[2m'; N=$'\e[0m'
else R=; W=; G=; D=; N=; fi
say() { printf '%s▌%s %s\n' "$R" "$N" "$*"; }
die() { printf '%s✗%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

printf '\n%s  ██████  %sJ A R V O%s\n%s  ██████  %sfrom idea to reality.%s\n\n' "$W" "$W" "$N" "$R" "$D" "$N"

case "$(uname -s)" in
  Darwin) OS=macos ;;
  Linux) OS=linux; grep -qi microsoft /proc/version 2>/dev/null && OS=wsl ;;
  *) die "Nieobsługiwany system: $(uname -s). Na Windowsie uruchom polecenie PowerShell ze strony." ;;
esac
say "System: $OS"

need() { command -v "$1" >/dev/null 2>&1 || die "Brak programu: $1. $2"; }
case "$OS" in
  macos)
    need git "Zainstaluj: xcode-select --install"
    need docker "Zainstaluj Docker Desktop: https://www.docker.com/products/docker-desktop/"
    # macOS ma basha 3.2 z 2007 roku; skrypty floty potrzebują basha 4+
    if (( BASH_VERSINFO[0] < 4 )); then
      NEWBASH="$(command -v /opt/homebrew/bin/bash /usr/local/bin/bash 2>/dev/null | head -1 || true)"
      if [[ -z "$NEWBASH" ]]; then
        command -v brew >/dev/null || die "Potrzebny nowszy bash. Zainstaluj Homebrew (https://brew.sh) i uruchom ponownie."
        say "Instaluję nowszego basha (brew install bash)…"; brew install bash >/dev/null
        NEWBASH="$(brew --prefix)/bin/bash"
      fi
    fi
    ;;
  linux|wsl)
    need git "Zainstaluj: sudo apt install git (albo menedżer pakietów Twojej dystrybucji)"
    need docker "Zainstaluj Docker: https://docs.docker.com/engine/install/ (w WSL: Docker Desktop z integracją WSL)"
    ;;
esac
need python3 "Zainstaluj Python 3."
need openssl "Zainstaluj openssl."
docker info >/dev/null 2>&1 || die "Docker nie działa. Uruchom Docker Desktop (w WSL: Settings → Resources → WSL integration) i spróbuj ponownie."
docker compose version >/dev/null 2>&1 || die "Brak docker compose v2. Zaktualizuj Dockera."

if [[ -d "$DIR/.git" ]]; then
  say "Aktualizuję $DIR"
  git -C "$DIR" pull --ff-only -q origin "$BRANCH" || die "Nie udało się zaktualizować $DIR (lokalne zmiany?)."
else
  [[ -e "$DIR" ]] && die "$DIR istnieje i nie jest repozytorium Jarvo. Ustaw JARVO_DIR=inny/katalog."
  say "Pobieram Jarvo do $DIR"
  git clone -q --depth 50 -b "$BRANCH" "$REPO" "$DIR" || die "Nie udało się pobrać $REPO."
fi

say "Stawiam flotę (pierwszy raz kilka–kilkanaście minut: budowa obrazu)…"
# pytania instalatora czytamy z terminala, nie z potoku curl | bash
TTY=/dev/tty; [[ -r /dev/tty ]] || TTY=/dev/null
"${NEWBASH:-bash}" "$DIR/scripts/local-up.sh" < "$TTY"

printf '\n%s▌%s Gotowe. Otwórz %shttp://localhost:9119/base%s\n' "$G" "$N" "$W" "$N"
