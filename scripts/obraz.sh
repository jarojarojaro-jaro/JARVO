#!/usr/bin/env bash
# Gotowy obraz floty z rejestru zamiast budowy na miejscu (kilkanaście minut i 8 GB RAM → 2–3 minuty pobierania).
#
#   bash scripts/obraz.sh klucz              # klucz obrazu z tego, z czego się go buduje (infra/ i branding/)
#   bash scripts/obraz.sh pobierz [katalog]  # pobierz obraz dla klucza i nazwij go jarvo-hermes:local
#   bash scripts/obraz.sh jest               # czy rejestr ma obraz dla bieżącego klucza (kod 0 = tak)
#
# Obraz buduje GitHub Actions (.github/workflows/obraz.yml) dla amd64 i arm64 przy każdej zmianie infra/
# albo branding/ i publikuje jako $JARVO_IMAGE_REPO:src-<klucz>. Ten sam klucz liczy tu i tam ta sama funkcja,
# więc instalacja dostaje dokładnie obraz zbudowany z jej wersji repo. `pobierz` zapisuje klucz w
# <katalog>/.image-key (katalog compose); nie ma obrazu (świeży push, CI jeszcze buduje, brak dostępu do
# rejestru) → kod 1 i deploy.sh buduje na miejscu jak dawniej. Obrazu jeszcze nie ma, a infra/ albo branding/
# zmieniły się w ostatniej godzinie → najpierw czekamy na CI (JARVO_IMAGE_WAIT); zerwane pobieranie → druga próba.
#
# Zmienne: JARVO_IMAGE_REPO (domyślnie ghcr.io/jarojarojaro-jaro/jarvo-hermes),
#          JARVO_BUILD_IMAGE=1 (zawsze buduj na miejscu: `pobierz` od razu zwraca 1; tak samo przy własnym
#          HERMES_IMAGE w <katalog>/.env, bo obraz z rejestru ma Hermesa przypiętego w infra/Dockerfile),
#          JARVO_TOKEN (klucz dostępu z instalatora: logowanie do rejestru, gdy obraz nie jest publiczny),
#          JARVO_IMAGE_WAIT (ile sekund czekać na obraz budowany przez CI, domyślnie 1200; 0 = od razu buduj),
#          JARVO_IMAGE_POLL (co ile sekund pytać rejestr, domyślnie 30).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_IMG="${JARVO_IMAGE_REPO:-ghcr.io/jarojarojaro-jaro/jarvo-hermes}"
# to, co kopiuje infra/Dockerfile (i sam Dockerfile); zmiana czegokolwiek tutaj = nowy obraz
SRC=(infra/Dockerfile infra/node infra/python infra/bin branding)

klucz() { git -C "$ROOT" ls-tree -r HEAD -- "${SRC[@]}" | git hash-object --stdin | cut -c1-12; }

case "${1:-}" in
  klucz) klucz ;;
  jest) docker manifest inspect "$REPO_IMG:src-$(klucz)" >/dev/null 2>&1 ;;
  pobierz)
    [[ "${JARVO_BUILD_IMAGE:-0}" == 1 ]] && exit 1
    # własny HERMES_IMAGE w compose/.env: obraz z rejestru ma Hermesa z repo, więc budujemy na miejscu
    if [[ -n "${2:-}" ]] && grep -q '^HERMES_IMAGE=.' "$2/.env" 2>/dev/null; then
      echo "ℹ Własny HERMES_IMAGE w $2/.env: buduję obraz na miejscu."; exit 1
    fi
    k="$(klucz)"; img="$REPO_IMG:src-$k"
    echo "▶ Pobieram gotowy obraz floty ($img, ok. 2,5 GB)"
    blad=""
    pull() {   # postęp: pobrane warstwy zamiast kilku minut ciszy; komunikat rejestru trafia do $blad
      local err; err="$(mktemp)"
      if docker pull "$img" 2>"$err" \
         | awk '/Pulling fs layer/ {n++} /Pull complete/ {d++; printf "  pobrane warstwy: %d/%d\n", d, n; fflush()}'; then
        rm -f "$err"; return 0
      fi
      blad="$(cat "$err")"; rm -f "$err"; return 1
    }
    # rejestr prywatnego repo: jednorazowe logowanie kluczem dostępu z instalatora (zostaje w ~/.docker/config.json)
    login() { [[ -n "${JARVO_TOKEN:-}" ]] \
      && printf '%s' "$JARVO_TOKEN" | docker login "${REPO_IMG%%/*}" -u jarvo --password-stdin >/dev/null 2>&1; }
    odmowa() { grep -qiE 'denied|unauthorized|authentication required' <<<"$blad"; }
    ok=0
    if pull || { login && pull; }; then ok=1
    elif grep -qiE 'not found|manifest unknown' <<<"$blad"; then
      # świeża zmiana infra/ albo branding/: GitHub Actions buduje obraz kilka–kilkanaście minut, a budowa na miejscu
      # trwa dłużej i potrzebuje 8 GB RAM, więc czekamy na CI (JARVO_IMAGE_WAIT sekund, domyślnie 20 min; 0 = nie czekaj)
      zmiana="$(git -C "$ROOT" log -1 --format=%ct -- "${SRC[@]}" 2>/dev/null || true)"
      wiek=$(( $(date +%s) - ${zmiana:-0} )); czekaj="${JARVO_IMAGE_WAIT:-1200}"
      if (( wiek < 3600 && czekaj > 0 )); then
        echo "ℹ GitHub Actions jeszcze buduje obraz tej wersji (zmiana sprzed $(( wiek / 60 )) min): czekam do $(( czekaj / 60 )) min."
        koniec=$(( SECONDS + czekaj ))
        while (( SECONDS < koniec )); do
          sleep "${JARVO_IMAGE_POLL:-30}"
          if docker manifest inspect "$img" >/dev/null 2>&1; then pull && ok=1; break; fi
        done
      fi
    elif ! odmowa; then
      # zerwana sieć w trakcie: druga próba dociąga tylko brakujące warstwy
      echo "ℹ Pobieranie przerwane, próbuję jeszcze raz…"; sleep "${JARVO_IMAGE_POLL:-5}"
      pull && ok=1
    fi
    if [[ $ok != 1 ]]; then
      # odmowa (pakiet w rejestrze nie jest publiczny) to co innego niż brak obrazu (CI jeszcze buduje)
      if odmowa; then
        echo "ℹ Rejestr odmówił pobrania $img (pakiet nie jest publiczny): buduję na miejscu."
      else
        echo "ℹ Brak gotowego obrazu dla tej wersji (CI jeszcze buduje albo brak sieci): buduję na miejscu."
      fi
      exit 1
    fi
    docker tag "$img" jarvo-hermes:local
    # stary obraz z rejestru zostaje bez nazwy jarvo-hermes:local; usuwamy jego tag, warstwy wspólne zostają
    docker images --format '{{.Repository}}:{{.Tag}}' "$REPO_IMG" | while read -r stary; do
      [[ $stary == "$img" ]] || docker rmi "$stary" >/dev/null 2>&1 || true
    done
    [[ -n "${2:-}" ]] && echo "$k" > "$2/.image-key"
    echo "✓ Obraz gotowy: jarvo-hermes:local ← $img" ;;
  *) echo "użycie: obraz.sh klucz | jest | pobierz [katalog-compose]" >&2; exit 2 ;;
esac
