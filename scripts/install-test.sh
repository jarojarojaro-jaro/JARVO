#!/usr/bin/env bash
# Test instalatora (install.sh) od zera: świeży kontener Ubuntu/Debian z prawem do własnego dockerd, użytkownik
# bez roota z sudo. Dwa tryby:
#  - piaskownica Claude Code (HTTPS_PROXY i certyfikat proxy): obraz jarvo-hermes:local i obrazy sidecarów
#    wczytujemy z zewnętrznego dockera (budowanie przez compose nie widzi proxy);
#  - zwykła maszyna / CI (bez proxy, JARVO_TEST_PULL=1): obraz floty instalator pobiera z GHCR jak u użytkownika
#    (JARVO_TOKEN = klucz z dostępem do pakietu, np. GITHUB_TOKEN w Actions; nigdy nie trafia do logu).
#
#   bash scripts/install-test.sh [ubuntu:24.04|debian:12] [--keep]
#
# Sprawdza po kolei: pakiety (git, curl, python3, openssl) i Docker Engine z get.docker.com, grupa docker i sg,
# klon repo z /mnt/jarvo (kopia bieżącego drzewa roboczego jako gałąź main, więc także zmian sprzed commita), `jarvo up` bez pytań (JARVO_YES=1, JARVO_NO_BUILD=1), dashboard
# odpowiada, ponowne install.sh = aktualizacja, jarvo status / down / uninstall --yes.
# Na zwykłym komputerze użytkownika: bash install.sh (ten skrypt to test, nie instalacja).
set -euo pipefail   # uwaga: na hoście żadnych potoków „| grep -q” (pipefail + SIGPIPE), wyniki do zmiennej
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMG="${1:-ubuntu:24.04}"; KEEP=0; [[ "${2:-}" == --keep ]] && KEEP=1
CA="${JARVO_PROXY_CA:-/root/.ccr/ca-bundle.crt}"
L="${JARVO_LOCAL:-$HOME/jarvo-local}"
NAME="jarvo-install-test"
VAR="$L/install-test/var-lib-docker"       # /var/lib/docker kontenera testowego (overlay2 nie działa na overlay2)
BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
log() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m✗ %s\033[0m\n' "$*"; exit 1; }

PULL="${JARVO_TEST_PULL:-0}"; SANDBOX=0
[[ -n "${HTTPS_PROXY:-}" && -f "$CA" ]] && SANDBOX=1
[[ $SANDBOX == 1 || $PULL == 1 ]] || fail "Poza piaskownicą Claude Code tylko z JARVO_TEST_PULL=1 (obraz z GHCR)."
docker info >/dev/null 2>&1 || fail "dockerd nie działa (scripts/sandbox-up.sh)."
[[ $PULL == 1 ]] || docker image inspect jarvo-hermes:local >/dev/null 2>&1 || fail "Brak obrazu jarvo-hermes:local (scripts/sandbox-up.sh)."

# proxy piaskownicy słucha tylko na 127.0.0.1: przekaźnik na adresie mostka Dockera, żeby kontener testowy go widział
PORT="${HTTPS_PROXY:-}"; PORT="${PORT##*:}"; BRIDGE=172.17.0.1; PROXY="http://$BRIDGE:$PORT"
RELAY=""
if [[ $SANDBOX == 1 ]] && ! (exec 3<>"/dev/tcp/$BRIDGE/$PORT") 2>/dev/null; then
  python3 - "$PORT" "$BRIDGE" <<'PY' &
import asyncio, sys
PORT, BIND = int(sys.argv[1]), sys.argv[2]
async def pipe(r, w):
    try:
        while (d := await r.read(65536)):
            w.write(d); await w.drain()
    except Exception: pass
    finally:
        try: w.close()
        except Exception: pass
async def handle(cr, cw):
    try: ur, uw = await asyncio.open_connection("127.0.0.1", PORT)
    except Exception: cw.close(); return
    await asyncio.gather(pipe(cr, uw), pipe(ur, cw))
async def main():
    srv = await asyncio.start_server(handle, BIND, PORT); await srv.serve_forever()
asyncio.run(main())
PY
  RELAY=$!; sleep 1
fi
cleanup() {
  [[ -n $RELAY ]] && kill "$RELAY" 2>/dev/null || true
  if [[ $KEEP -eq 0 ]]; then docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$VAR" "$SRC" 2>/dev/null || true; fi
}
trap cleanup EXIT

# repo do klonowania = bieżące drzewo robocze (także zmiany jeszcze niezacommitowane), nie HEAD
SRC="$L/install-test/repo"
log "Repo testowe z drzewa roboczego ($BRANCH): $SRC"
rm -rf "$SRC"; mkdir -p "$SRC"
git -C "$ROOT" ls-files -co --exclude-standard -z | tar -C "$ROOT" --null -T - -cf - | tar -C "$SRC" -xf -
git -C "$SRC" init -q -b main                 # instalator domyślnie klonuje main
git -C "$SRC" -c user.name=test -c user.email=test@example.invalid add -A
git -C "$SRC" -c user.name=test -c user.email=test@example.invalid commit -q -m "drzewo robocze do testu instalatora"

log "Kontener testowy: $IMG"
docker rm -f "$NAME" >/dev/null 2>&1 || true
mkdir -p "$VAR"
NET=()
[[ $SANDBOX == 1 ]] && NET=(-v "$CA:/usr/local/share/ca-certificates/proxy-ca.crt:ro"
  -e HTTP_PROXY="$PROXY" -e HTTPS_PROXY="$PROXY" -e http_proxy="$PROXY" -e https_proxy="$PROXY"
  -e NO_PROXY="localhost,127.0.0.1" -e no_proxy="localhost,127.0.0.1")
docker run -d --privileged --name "$NAME" -h jarvo-test \
  -v "$SRC:/mnt/jarvo:ro" -v "$VAR:/var/lib/docker" ${NET[@]+"${NET[@]}"} \
  "$IMG" sleep infinity >/dev/null
R() { docker exec "$NAME" bash -c "$*"; }                    # jako root
# jako zwykły użytkownik (bash -l: profil z proxy); JARVO_TOKEN przechodzi bez wartości w wierszu poleceń
U() { docker exec -u tester -w /home/tester -e HOME=/home/tester ${JARVO_TOKEN:+-e JARVO_TOKEN} "$NAME" bash -lc "$*"; }

log "Przygotowanie świeżego systemu (sudo, certyfikat proxy, użytkownik tester; bez gita, curla, Pythona i Dockera; openssl przychodzi z ca-certificates)"
# proxy piaskownicy przepuszcza tylko HTTPS: mirrory apt na https z certyfikatem proxy (na zwykłym komputerze zbędne)
if [[ $SANDBOX == 1 ]]; then
R "sed -i 's#http://#https://#g' /etc/apt/sources.list.d/*.sources /etc/apt/sources.list 2>/dev/null || true
   echo 'Acquire::https::CAInfo \"/usr/local/share/ca-certificates/proxy-ca.crt\";' > /etc/apt/apt.conf.d/98ca
   export DEBIAN_FRONTEND=noninteractive; apt-get update -q >/dev/null && apt-get install -y -q ca-certificates sudo >/dev/null
   update-ca-certificates >/dev/null 2>&1 && rm -f /etc/apt/apt.conf.d/98ca
   printf 'Acquire::http::Proxy \"%s\";\nAcquire::https::Proxy \"%s\";\n' '$PROXY' '$PROXY' > /etc/apt/apt.conf.d/99proxy
   for v in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy; do echo \"export \$v=$PROXY\"; done > /etc/profile.d/proxy.sh
   echo 'export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1' >> /etc/profile.d/proxy.sh"
else
R "export DEBIAN_FRONTEND=noninteractive; apt-get update -q >/dev/null && apt-get install -y -q ca-certificates sudo >/dev/null"
fi
# Docker w kontenerze na hoście z cgroup v2 (runner GitHuba): procesy kontenera do podgrupy i włączone kontrolery,
# inaczej runc odmawia ("cannot enter cgroupv2 /sys/fs/cgroup/docker ... invalid state"); to samo robi skrypt
# dind z oficjalnego obrazu docker:dind. Dotyczy tylko testu (Docker w Dockerze), nie komputerów użytkowników.
R "if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
     mkdir -p /sys/fs/cgroup/init
     xargs -rn1 < /sys/fs/cgroup/cgroup.procs > /sys/fs/cgroup/init/cgroup.procs 2>/dev/null || true
     sed -e 's/ / +/g' -e 's/^/+/' < /sys/fs/cgroup/cgroup.controllers > /sys/fs/cgroup/cgroup.subtree_control
   fi"
R "useradd -m -s /bin/bash tester
   printf 'tester ALL=(ALL) NOPASSWD:ALL\nDefaults env_keep += \"HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy\"\n' > /etc/sudoers.d/tester
   printf '[safe]\n\tdirectory = /mnt/jarvo\n\tdirectory = /mnt/jarvo/.git\n' > /home/tester/.gitconfig && chown tester:tester /home/tester/.gitconfig
   for t in git curl python3 docker; do command -v \$t >/dev/null && { echo \"\$t już jest: to nie świeży system\"; exit 1; }; done; true"

log "1/6 install.sh jak z curl | bash (JARVO_SETUP_ONLY=1: pakiety, Docker Engine, grupa docker, repo, polecenie jarvo)"
# JARVO_FORCE=1: dysk piaskownicy bywa pełny (kopia obrazu zajmuje 6 GB); sprawdzenie sprzętu testuje pytest
U "cat /mnt/jarvo/install.sh | JARVO_SETUP_ONLY=1 JARVO_FORCE=1 JARVO_REPO=/mnt/jarvo bash"
cloned="$(U "git -C ~/jarvo rev-parse --abbrev-ref HEAD")"
[[ $cloned == main ]] || fail "Klon bez JARVO_BRANCH ma być na gałęzi main, jest: $cloned"
U "for t in git curl python3 openssl docker; do command -v \$t >/dev/null || exit 1; done; sudo docker info >/dev/null && test -x /usr/local/bin/jarvo && test -d ~/jarvo/.git" \
  || fail "Po install.sh brakuje narzędzi, Dockera, repo albo polecenia jarvo"
U "getent group docker | grep -q tester" || fail "tester nie jest w grupie docker"
U "grep -q 'install.sh' ~/jarvo-local/install.log" || fail "Brak logu instalacji"

if [[ $PULL == 1 ]]; then
  log "2/6 obraz floty pobierze jarvo up z GHCR (jak u użytkownika)"
  NB=""
else
  log "2/6 obrazy z zewnętrznego dockera (bez budowy)"
  NB="JARVO_NO_BUILD=1"
  docker save jarvo-hermes:local searxng/searxng:latest valkey/valkey:8-alpine | docker exec -i "$NAME" docker load >/dev/null
  R "docker image inspect jarvo-hermes:local >/dev/null"
fi

log "3/6 jarvo up bez pytań (sesja bez grupy docker → sg)"
U "JARVO_YES=1 $NB jarvo up"
# obraz z rejestru, nie zbudowany na miejscu (obraz.sh zapisuje klucz tylko po pobraniu)
[[ $PULL == 1 ]] && { U "test -s ~/jarvo-local/compose/.image-key" || fail "jarvo up zbudował obraz zamiast pobrać go z GHCR"; }
status="$(U "jarvo status")"; echo "$status"
grep -q "jarvo-hermes" <<<"$status" || fail "jarvo status nie widzi kontenera"
code="$(R "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9119/base")"
[[ $code == 200 || $code == 30? ]] || fail "Dashboard nie odpowiada (HTTP $code)"
U "test -f ~/jarvo-local/updater.pid && kill -0 \$(cat ~/jarvo-local/updater.pid)" || fail "Pomocnik aktualizacji nie działa"
U "jarvo autostart on" && fail "autostart on bez systemd powinien się nie udać" || true
U "jarvo open | grep -q 9119 && jarvo pliki | grep -q jarvo-local/data" || fail "jarvo open/pliki"

log "4/6 ponowne install.sh = aktualizacja (bez pytań, bez budowy)"
U "cat /mnt/jarvo/install.sh | JARVO_YES=1 $NB JARVO_FORCE=1 JARVO_REPO=/mnt/jarvo bash" | tail -5
status="$(U "jarvo status")"
grep -q "jarvo-hermes.*Up" <<<"$status" || fail "Flota nie działa po aktualizacji"

log "5/6 jarvo down"
U "jarvo down"
R "docker ps --format '{{.Names}}' | grep -q jarvo" && fail "Kontenery dalej działają" || true

log "6/6 jarvo uninstall --yes (dane zostają)"
U "jarvo uninstall --yes"
R "docker image inspect jarvo-hermes:local >/dev/null 2>&1" && fail "Obraz nie usunięty" || true
U "test ! -e /usr/local/bin/jarvo && test -f ~/jarvo-local/compose/.env && test -d ~/jarvo/.git" || fail "uninstall: polecenie ma zniknąć, dane i repo zostać"
U "JARVO_YES=1 bash ~/jarvo/bin/jarvo uninstall --yes --all"
U "test ! -e ~/jarvo-local && test ! -e ~/jarvo" || fail "uninstall --all: dane i repo mają zniknąć"

printf '\n✅ Instalator przeszedł test od zera na %s (gałąź %s).\n' "$IMG" "$BRANCH"
