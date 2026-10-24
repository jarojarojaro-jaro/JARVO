#!/usr/bin/env bash
# Jarvo natywnie: instalacja jednym poleceniem na macOS (Apple Silicon) i Linuksie (docs/NATYWNIE.md, L02 i c3).
#
#   curl -fsSL https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/jarvo/bootstrap/install.sh | bash
#
# Bez sudo, bez Homebrew i bez Dockera. Skrypt zna tylko dwa pliki dla platformy: uv i Pythona 3.13
# (python-build-standalone). Adresy i sumy sha256 są wpisane niżej, te same co w vendor/natywne.lock.json
# (tests/test_natywne_cli.py pilnuje zgodności). Kroki jak w install.ps1:
#   1. platforma: macOS arm64 (Mac z Intelem: odmowa, decyzja I06; Terminal pod Rosettą nie myli wykrycia), Linux
#      x64 i arm64 z glibc; korzeń: $JARVO_ROOT albo ~/.jarvo (macOS), ${XDG_DATA_HOME:-~/.local/share}/jarvo
#      (Linux), jak jarvo/sciezki.py; cudze polecenie ~/.local/bin/jarvo (stara instalacja) = odmowa (migracja E12),
#   2. uv i Python do <root>/program/narzedzia/<nazwa>/<wersja>: curl -fL#, suma (sha256sum albo shasum -a 256)
#      przed rozpakowaniem, tar; znacznik .jarvo-suma jak w jarvo/pobieracz.py, więc instalator w Pythonie
#      niczego nie pobiera drugi raz,
#   3. kod Jarva: ref ($JARVO_REF albo main) -> SHA przez API GitHuba, archiwum commitu do <root>/program/app/<sha12>,
#   4. python3 -I -X utf8 <app>/jarvo/start.py instaluj: dalej instalator w Pythonie (jarvo/instalator.py).
#
# Zmienne (opcjonalne): JARVO_ROOT, JARVO_REF (gałąź, tag albo pełny SHA), JARVO_TOKEN (klucz do prywatnej kopii
# repo: curl dostaje go na wejściu (-K -), więc nie widać go w liście procesów ani na ekranie), JARVO_NO_AUTOSTART=1,
# JARVO_WEB_LOKALNIE=1, JARVO_BEZ_PATH=1 (polecenie jarvo tylko w <root>/bin, bez ~/.local/bin i plików startowych
# powłoki: próby), JARVO_DRY_RUN=1 (tylko plan, bez pobierania i zapisu).
# Bash 3.2 (macOS): bez tablic asocjacyjnych, ${x,,} i mapfile. Całość siedzi w funkcji main, więc ucięty transfer
# `curl | bash` niczego nie uruchomi; wczytany przez `source` (testy) skrypt tylko definiuje funkcje.
if [ -z "${BASH_VERSION:-}" ]; then              # `curl … | sh` (dash): czytelna odmowa zamiast błędu pipefail
  echo "JARVO: uruchom ten skrypt przez bash: curl -fsSL <adres>/install.sh | bash" >&2
  exit 1
fi
set -euo pipefail

REPO_GH="jarojarojaro-jaro/JARVO"
ZNACZNIK="Jarvo natywnie (jarvo instaluj)"      # ten sam co w jarvo/instalator.py

say() { printf '[jarvo] %s\n' "$*"; }
plan() { printf '  (na sucho) %s\n' "$*"; }
die() { printf 'JARVO: %s\n' "$*" >&2; exit 1; }

# plik <platforma> <nazwa>: ustawia U (adres), S (sha256), P (ile katalogów zdjąć), K (katalog wersji), F (format)
# z vendor/natywne.lock.json: uv 0.12.13, python313 3.13.17+20261021
plik() {
  case "$1:$2" in
    macos-arm64:uv) K=0.12.13; P=1; F=tar.gz
      U='https://github.com/astral-sh/uv/releases/download/0.12.13/uv-aarch64-apple-darwin.tar.gz'
      S=7e6ddb9316acc00f2296c82ff4d99977870ee34b2f0ddcae9444d714db9364ed ;;
    macos-arm64:python313) K=3.13.17; P=1; F=tar.gz
      U='https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.13.17%2B20261021-aarch64-apple-darwin-install_only_stripped.tar.gz'
      S=8dc60610a82f1e73be7faf964383e02520f95f6e39592a5c37c3809f5a7b798e ;;
    linux-x64:uv) K=0.12.13; P=1; F=tar.gz
      U='https://github.com/astral-sh/uv/releases/download/0.12.13/uv-x86_64-unknown-linux-gnu.tar.gz'
      S=745765a3b6e360ad76743599ae5c42e9278c7edf8bbff9fc76d05bf2623a04dd ;;
    linux-x64:python313) K=3.13.17; P=1; F=tar.gz
      U='https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.13.17%2B20261021-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz'
      S=f829adc9d888e76c8801b4799ed444188d35239fcae3a9808a99ec5cb0d8d92c ;;
    linux-arm64:uv) K=0.12.13; P=1; F=tar.gz
      U='https://github.com/astral-sh/uv/releases/download/0.12.13/uv-aarch64-unknown-linux-gnu.tar.gz'
      S=2eaa5d94f5db7b3a1a092156b9420459e42ab0217d917fe74a876309cef9b5e9 ;;
    linux-arm64:python313) K=3.13.17; P=1; F=tar.gz
      U='https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.13.17%2B20261021-aarch64-unknown-linux-gnu-install_only_stripped.tar.gz'
      S=c6857c65b996701a5da104cbb49b35249c0c026dc0664239b04f7156aa88326a ;;
    *) return 1 ;;
  esac
}

platforma() {   # ustawia PLATFORMA
  local s m
  s="$(uname -s)"
  m="$(uname -m)"
  case "$s" in
    Darwin)
      # Terminal pod Rosettą podaje x86_64 także na Apple Silicon; sysctl mówi, jaki jest procesor
      if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || true)" = "1" ]; then m=arm64; fi
      case "$m" in
        arm64|aarch64) PLATFORMA=macos-arm64 ;;
        *) die "Jarvo nie działa na Macach z procesorem Intel: Hermes ich nie wspiera (docs/NATYWNIE.md, decyzja I06). Potrzebny Mac z Apple Silicon (M1 i nowsze)." ;;
      esac ;;
    Linux)
      case "$m" in
        x86_64|amd64) PLATFORMA=linux-x64 ;;
        aarch64|arm64) PLATFORMA=linux-arm64 ;;
        *) die "Jarvo na Linuksie działa na x86_64 i aarch64, a ten komputer ma $m." ;;
      esac
      if ls /lib/ld-musl-* >/dev/null 2>&1 && ! ls /lib/ld-linux* /lib64/ld-linux* >/dev/null 2>&1; then
        die "Ten Linux używa biblioteki musl (np. Alpine), a Python Jarva potrzebuje glibc."
      fi ;;
    *) die "Ten skrypt jest dla macOS i Linuksa (system: $s). Na Windows: irm https://raw.githubusercontent.com/$REPO_GH/main/jarvo/bootstrap/install.ps1 | iex" ;;
  esac
}

katalogi() {   # ROOT, PROGRAM, POBRANE jak jarvo/sciezki.py
  local cache
  if [ -n "${JARVO_ROOT:-}" ]; then
    ROOT="$JARVO_ROOT"
    case "$ROOT" in "~"/*) ROOT="$HOME/${ROOT#\~/}" ;; esac
    case "$ROOT" in /*) ;; *) ROOT="$PWD/$ROOT" ;; esac
    export JARVO_ROOT="$ROOT"
    cache="$ROOT/cache"
  elif [ "$PLATFORMA" = macos-arm64 ]; then
    ROOT="$HOME/.jarvo"            # bez spacji (nie ~/Library/Application Support): skille mają niecytowane ścieżki
    cache="$ROOT/cache"
  else
    ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/jarvo"
    cache="${XDG_CACHE_HOME:-$HOME/.cache}/jarvo"
  fi
  PROGRAM="$ROOT/program"
  POBRANE="$cache/pobrane"
}

stara_instalacja() {   # cudze ~/.local/bin/jarvo (np. dowiązanie starej instalacji z Dockerem): nie nadpisujemy
  local cel="$HOME/.local/bin/jarvo"
  if [ "${JARVO_BEZ_PATH:-}" = 1 ]; then return 0; fi     # polecenie idzie wtedy do <root>/bin
  if [ -L "$cel" ] || { [ -e "$cel" ] && ! grep -qsF "$ZNACZNIK" "$cel"; }; then
    die "$cel należy do innej instalacji Jarvo (np. starej z Dockerem). Migracja (jarvo migruj) przyjdzie w etapie E12; do tego czasu przenieś stare polecenie (np. mv $cel ${cel}-docker) i uruchom instalację ponownie."
  fi
}

suma() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

pobierz() {   # <adres> <cel> <sha256>: plik z dobrą sumą zostaje; zła suma = plik usunięty i koniec
  local url="$1" cel="$2" sha="$3" jest
  if [ -f "$cel" ] && [ "$(suma "$cel")" = "$sha" ]; then return 0; fi
  mkdir -p "$(dirname "$cel")"
  rm -f "$cel.czesc"
  curl -fL# --retry 3 --retry-delay 2 -o "$cel.czesc" "$url" || die "Nie udało się pobrać $url (sieć?). Uruchom polecenie ponownie."
  jest="$(suma "$cel.czesc")"
  if [ "$jest" != "$sha" ]; then
    rm -f "$cel.czesc"
    die "Suma sha256 pliku $url się nie zgadza (jest ${jest:0:12}…, ma być ${sha:0:12}…). Plik usunięty, niczego nie uruchomiłem."
  fi
  mv -f "$cel.czesc" "$cel"
}

narzedzie() {   # <nazwa>: do $PROGRAM/narzedzia/<nazwa>/<wersja>; ustawia KAT
  local nazwa="$1" arch
  plik "$PLATFORMA" "$nazwa" || die "Brak pliku $nazwa dla $PLATFORMA w tym skrypcie."
  KAT="$PROGRAM/narzedzia/$nazwa/$K"
  if [ -f "$KAT/.jarvo-suma" ] && [ "$(tr -d '[:space:]' < "$KAT/.jarvo-suma")" = "$S" ]; then
    say "$nazwa $K: już jest"
    return 0
  fi
  arch="$POBRANE/${S:0:16}-${U##*/}"
  if [ "$DRY" = 1 ]; then
    plan "pobierz $U"
    plan "  sha256 $S -> $arch"
    plan "  rozpakuj ($F, poziom $P) -> $KAT"
    return 0
  fi
  say "pobieram $nazwa $K"
  pobierz "$U" "$arch" "$S"
  rm -rf "$KAT.new"
  mkdir -p "$KAT.new"
  tar -xzf "$arch" -C "$KAT.new" --strip-components="$P" || die "Nie udało się rozpakować $arch."
  printf '%s\n' "$S" > "$KAT.new/.jarvo-suma"
  rm -rf "$KAT"
  mv "$KAT.new" "$KAT"
  say "$nazwa $K: $KAT"
}

naglowki() {   # konfiguracja curl na wejście (-K -): klucz nie trafia do argv (ps) ani na ekran
  if [ -n "${JARVO_TOKEN:-}" ]; then printf 'header = "Authorization: Bearer %s"\n' "$JARVO_TOKEN"; fi
}

ukryty() { if [ -n "${JARVO_TOKEN:-}" ]; then printf ' (Authorization: Bearer <ukryty>)'; fi; }

wersja() {   # ustawia SHA: pełny SHA z JARVO_REF albo z API (Accept: application/vnd.github.sha = sam SHA, bez JSON)
  local ref="${JARVO_REF:-main}" adres
  if printf '%s' "$ref" | grep -Eq '^[0-9a-fA-F]{40}$'; then
    SHA="$(printf '%s' "$ref" | tr 'A-F' 'a-f')"
    return 0
  fi
  adres="https://api.github.com/repos/$REPO_GH/commits/$ref"
  if [ "$DRY" = 1 ]; then
    plan "GET $adres$(ukryty)"
    SHA="SHA-z-${ref//\//_}"
    return 0
  fi
  SHA="$(naglowki | curl -fsSL -K - -H 'Accept: application/vnd.github.sha' -H 'User-Agent: jarvo-instalator' "$adres")" \
    || die "Nie znalazłem wersji '$ref' w $REPO_GH. Prywatna kopia repo: ustaw JARVO_TOKEN."
  printf '%s' "$SHA" | grep -Eq '^[0-9a-f]{40}$' || die "API GitHuba nie podało SHA dla '$ref'."
}

adres_kodu() {   # archiwum commitu $1. Prywatna kopia: API przekierowuje na jednorazowy adres codeload; curl od 7.58
  # nie przenosi nagłówka Authorization na inny host po przekierowaniu, więc klucz trafia tylko do api.github.com
  if [ -n "${JARVO_TOKEN:-}" ]; then printf '%s\n' "https://api.github.com/repos/$REPO_GH/tarball/$1"
  else printf '%s\n' "https://codeload.github.com/$REPO_GH/tar.gz/$1"; fi
}

kod() {   # kod Jarva z commitu $SHA do $PROGRAM/app/<sha12> (bez .git); ustawia APP
  local adres arch
  APP="$PROGRAM/app/${SHA:0:12}"
  adres="$(adres_kodu "$SHA")"
  arch="$POBRANE/jarvo-$SHA.tar.gz"
  if [ "$DRY" = 1 ]; then
    plan "pobierz $adres$(ukryty)"
    plan "  rozpakuj (tar.gz, poziom 1) -> $APP"
    return 0
  fi
  if [ -f "$APP/jarvo/start.py" ]; then
    say "kod Jarva ${SHA:0:12}: już jest"
    return 0
  fi
  say "pobieram kod Jarva ${SHA:0:12}"
  mkdir -p "$POBRANE"
  rm -f "$arch"
  naglowki | curl -fL# -K - -H 'User-Agent: jarvo-instalator' -o "$arch" "$adres" \
    || die "Nie udało się pobrać kodu Jarva ($adres). Uruchom polecenie ponownie."
  rm -rf "$APP.new"
  mkdir -p "$APP.new"
  tar -xzf "$arch" -C "$APP.new" --strip-components=1 || die "Nie udało się rozpakować kodu Jarva."
  [ -f "$APP.new/jarvo/start.py" ] || die "Archiwum $adres nie ma jarvo/start.py (zły ref? ustaw JARVO_REF)."
  printf '%s\n' "$SHA" > "$APP.new/.jarvo-wersja"
  rm -rf "$APP"                    # niepełny katalog po przerwanej próbie: mv wsunąłby nowy do środka
  mv "$APP.new" "$APP"
  rm -f "$arch"
}

instalator() {   # python -I -X utf8 <app>/jarvo/start.py instaluj [opcje]
  local py="$PY_KAT/bin/python3"
  set -- -I -X utf8 "$APP/jarvo/start.py" instaluj ${1+"$@"}
  if [ "${JARVO_NO_AUTOSTART:-}" = 1 ]; then set -- "$@" --bez-autostartu; fi
  if [ "${JARVO_WEB_LOKALNIE:-}" = 1 ]; then set -- "$@" --web-lokalnie; fi
  if [ "${JARVO_BEZ_PATH:-}" = 1 ]; then set -- "$@" --bez-path; fi
  if [ "$DRY" = 1 ]; then
    plan "$py $*"
    return 0
  fi
  # przy `curl | bash` wejściem jest sam skrypt: pytania instalatora czytają z terminala, a bez niego z /dev/null
  if [ -t 0 ]; then
    "$py" "$@" || die "Instalator Jarva zakończył się błędem (opis wyżej)."
  elif (: < /dev/tty) 2>/dev/null; then
    "$py" "$@" < /dev/tty || die "Instalator Jarva zakończył się błędem (opis wyżej)."
  else
    "$py" "$@" < /dev/null || die "Instalator Jarva zakończył się błędem (opis wyżej)."
  fi
}

main() {
  DRY="${JARVO_DRY_RUN:-0}"
  say "Jarvo natywnie: instalacja bez Dockera i bez Homebrew"
  command -v curl >/dev/null 2>&1 || die "Brak programu curl: zainstaluj go menedżerem pakietów i uruchom polecenie ponownie."
  command -v tar >/dev/null 2>&1 || die "Brak programu tar: zainstaluj go menedżerem pakietów i uruchom polecenie ponownie."
  platforma
  katalogi
  say "platforma $PLATFORMA, katalog $ROOT"
  stara_instalacja
  narzedzie uv
  narzedzie python313
  PY_KAT="$KAT"
  wersja
  kod
  instalator ${1+"$@"}
  if [ "$DRY" = 1 ]; then return 0; fi
  if [ "${JARVO_BEZ_PATH:-}" = 1 ]; then
    say "Gotowe. Polecenie: $ROOT/bin/jarvo (PATH bez zmian: JARVO_BEZ_PATH=1)."
    return 0
  fi
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) say "Gotowe. Polecenie jarvo: jarvo chat, jarvo panel, jarvo status." ;;
    *) say "Gotowe. Otwórz nowy terminal (albo: export PATH=\"\$HOME/.local/bin:\$PATH\"), żeby działało polecenie jarvo." ;;
  esac
}

if [ -n "${BASH_SOURCE[0]:-}" ] && [ "${BASH_SOURCE[0]}" != "$0" ]; then
  return 0          # wczytany przez source (testy): tylko funkcje
fi
main ${1+"$@"}
