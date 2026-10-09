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
# rejestru) → kod 1 i deploy.sh buduje na miejscu jak dawniej.
#
# Zmienne: JARVO_IMAGE_REPO (domyślnie ghcr.io/jarojarojaro-jaro/jarvo-hermes),
#          JARVO_BUILD_IMAGE=1 (zawsze buduj na miejscu: `pobierz` od razu zwraca 1; tak samo przy własnym
#          HERMES_IMAGE w <katalog>/.env, bo obraz z rejestru ma Hermesa przypiętego w infra/Dockerfile).
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
    echo "▶ Pobieram gotowy obraz floty ($img)"
    if ! docker pull -q "$img" >/dev/null 2>&1; then
      echo "ℹ Brak gotowego obrazu dla tej wersji (CI jeszcze buduje albo brak dostępu do rejestru): buduję na miejscu."
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
