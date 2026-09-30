#!/usr/bin/env bash
# Test instalatora (install.sh) od zera w piaskownce Claude Code: świeży kontener Ubuntu/Debian z prawem do
# własnego dockerd, użytkownik bez roota z sudo, proxy i certyfikat piaskownicy. Obraz jarvo-hermes:local
# i obrazy sidecarów wczytujemy z zewnętrznego dockera (budowanie przez compose nie widzi proxy).
#
#   bash scripts/install-test.sh [ubuntu:24.04|debian:12] [--keep]
#
# Sprawdza po kolei: pakiety (git, curl, python3, openssl) i Docker Engine z get.docker.com, grupa docker i sg,
# klon repo z /mnt/jarvo (kopia bieżącego drzewa roboczego, więc także zmian sprzed commita), `jarvo up` bez pytań (JARVO_YES=1, JARVO_NO_BUILD=1), dashboard
# odpowiada, ponowne install.sh = aktualizacja, jarvo status / down / uninstall --yes.
# Tylko piaskownica (HTTPS_PROXY i CA jak w sandbox-up.sh); na zwykłym komputerze: bash install.sh.
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

[[ -n "${HTTPS_PROXY:-}" && -f "$CA" ]] || fail "Brak HTTPS_PROXY albo $CA: to nie piaskownica Claude Code."
docker info >/dev/null 2>&1 || fail "dockerd nie działa (scripts/sandbox-up.sh)."
docker image inspect jarvo-hermes:local >/dev/null 2>&1 || fail "Brak obrazu jarvo-hermes:local (scripts/sandbox-up.sh)."

# proxy piaskownicy słucha tylko na 127.0.0.1: przekaźnik na adresie mostka Dockera, żeby kontener testowy go widział
PORT="${HTTPS_PROXY##*:}"; BRIDGE=172.17.0.1; PROXY="http://$BRIDGE:$PORT"
RELAY=""
if ! (exec 3<>"/dev/tcp/$BRIDGE/$PORT") 2>/dev/null; then
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
git -C "$SRC" init -q -b "$BRANCH"
git -C "$SRC" -c user.name=test -c user.email=test@example.invalid add -A
git -C "$SRC" -c user.name=test -c user.email=test@example.invalid commit -q -m "drzewo robocze do testu instalatora"

log "Kontener testowy: $IMG"
docker rm -f "$NAME" >/dev/null 2>&1 || true
mkdir -p "$VAR"
docker run -d --privileged --name "$NAME" -h jarvo-test \
  -v "$SRC:/mnt/jarvo:ro" -v "$CA:/usr/local/share/ca-certificates/proxy-ca.crt:ro" -v "$VAR:/var/lib/docker" \
  -e HTTP_PROXY="$PROXY" -e HTTPS_PROXY="$PROXY" -e http_proxy="$PROXY" -e https_proxy="$PROXY" \
  -e NO_PROXY="localhost,127.0.0.1" -e no_proxy="localhost,127.0.0.1" \
  "$IMG" sleep infinity >/dev/null
R() { docker exec "$NAME" bash -c "$*"; }                    # jako root
U() { docker exec -u tester -w /home/tester -e HOME=/home/tester "$NAME" bash -lc "$*"; }   # jako zwykły użytkownik (bash -l: profil z proxy)

log "Przygotowanie świeżego systemu (sudo, certyfikat proxy, użytkownik tester; bez gita, curla, Pythona i Dockera; openssl przychodzi z ca-certificates)"
# proxy piaskownicy przepuszcza tylko HTTPS: mirrory apt na https z certyfikatem proxy (na zwykłym komputerze zbędne)
R "sed -i 's#http://#https://#g' /etc/apt/sources.list.d/*.sources /etc/apt/sources.list 2>/dev/null || true
   echo 'Acquire::https::CAInfo \"/usr/local/share/ca-certificates/proxy-ca.crt\";' > /etc/apt/apt.conf.d/98ca
   export DEBIAN_FRONTEND=noninteractive; apt-get update -q >/dev/null && apt-get install -y -q ca-certificates sudo >/dev/null
   update-ca-certificates >/dev/null 2>&1 && rm -f /etc/apt/apt.conf.d/98ca
   printf 'Acquire::http::Proxy \"%s\";\nAcquire::https::Proxy \"%s\";\n' '$PROXY' '$PROXY' > /etc/apt/apt.conf.d/99proxy
   for v in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy; do echo \"export \$v=$PROXY\"; done > /etc/profile.d/proxy.sh
   echo 'export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1' >> /etc/profile.d/proxy.sh
   useradd -m -s /bin/bash tester
   printf 'tester ALL=(ALL) NOPASSWD:ALL\nDefaults env_keep += \"HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy\"\n' > /etc/sudoers.d/tester
   printf '[safe]\n\tdirectory = /mnt/jarvo\n\tdirectory = /mnt/jarvo/.git\n' > /home/tester/.gitconfig && chown tester:tester /home/tester/.gitconfig
   for t in git curl python3 docker; do command -v \$t >/dev/null && { echo \"\$t już jest: to nie świeży system\"; exit 1; }; done; true"

log "1/6 install.sh jak z curl | bash (JARVO_SETUP_ONLY=1: pakiety, Docker Engine, grupa docker, repo, polecenie jarvo)"
# JARVO_FORCE=1: dysk piaskownicy bywa pełny (kopia obrazu zajmuje 6 GB); sprawdzenie sprzętu testuje pytest
U "cat /mnt/jarvo/install.sh | JARVO_SETUP_ONLY=1 JARVO_FORCE=1 JARVO_REPO=/mnt/jarvo JARVO_BRANCH='$BRANCH' bash"
U "for t in git curl python3 openssl docker; do command -v \$t >/dev/null || exit 1; done; sudo docker info >/dev/null && test -x /usr/local/bin/jarvo && test -d ~/jarvo/.git" \
  || fail "Po install.sh brakuje narzędzi, Dockera, repo albo polecenia jarvo"
U "getent group docker | grep -q tester" || fail "tester nie jest w grupie docker"
U "grep -q 'install.sh' ~/jarvo-local/install.log" || fail "Brak logu instalacji"

log "2/6 obrazy z zewnętrznego dockera (bez budowy)"
docker save jarvo-hermes:local searxng/searxng:latest valkey/valkey:8-alpine | docker exec -i "$NAME" docker load >/dev/null
R "docker image inspect jarvo-hermes:local >/dev/null"

log "3/6 jarvo up bez pytań (sesja bez grupy docker → sg; JARVO_NO_BUILD=1)"
U "JARVO_YES=1 JARVO_NO_BUILD=1 jarvo up"
status="$(U "jarvo status")"; echo "$status"
grep -q "jarvo-hermes" <<<"$status" || fail "jarvo status nie widzi kontenera"
code="$(R "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9119/base")"
[[ $code == 200 || $code == 30? ]] || fail "Dashboard nie odpowiada (HTTP $code)"
U "test -f ~/jarvo-local/updater.pid && kill -0 \$(cat ~/jarvo-local/updater.pid)" || fail "Pomocnik aktualizacji nie działa"
U "jarvo autostart on" && fail "autostart on bez systemd powinien się nie udać" || true
U "jarvo open | grep -q 9119 && jarvo pliki | grep -q jarvo-local/data" || fail "jarvo open/pliki"

log "4/6 ponowne install.sh = aktualizacja (bez pytań, bez budowy)"
U "cat /mnt/jarvo/install.sh | JARVO_YES=1 JARVO_NO_BUILD=1 JARVO_FORCE=1 JARVO_REPO=/mnt/jarvo JARVO_BRANCH='$BRANCH' bash" | tail -5
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
