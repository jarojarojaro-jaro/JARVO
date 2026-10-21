#!/bin/bash
# Test aplikacji Jarvo na żywo w przeglądarce (docs/HQ.md §2c i §2e), w kontenerze jarvo-hermes jako hermes:
#   docker exec -u hermes jarvo-hermes sh -c 'PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:$PATH \
#     NODE_PATH=/opt/jarvo/node/node_modules bash /opt/jarvo/repo/scripts/jarvo-e2e.sh etap1'   # albo etap2
# Wymaga JARVO_E2E=1 w env kontenera (piaskownica: sandbox-up.sh wpisuje go do compose/.env), bo bez niego nie ma tras
# testowych (POST /csrf-proba). Uruchamia tests/live/jarvo_e2e.cjs (Playwright z obrazu, Chromium /usr/local/bin/chromium),
# loguje się loginem i hasłem dashboardu z env kontenera (nigdy ich nie wypisuje), drukuje raport JSON i kończy się
# kodem ≠ 0 przy każdym nieudanym punkcie. Zrzuty ekranu nieudanych punktów: /tmp/jarvo-e2e/<czas>/ (po udanym
# przebiegu katalog znika). Sprząta przy każdym wyjściu (także po błędzie i Ctrl+C): serwer strony prób, fiksturki
# w inbox, pliki konwertera z próby i link podglądu; następny przebieg zaczyna od usunięcia resztek po poprzednich.
# etap2 (silnik rozmów, punkty 1–15 etapu 2): własna atrapa modelu z --dziennik na 127.0.0.1:$JARVO_E2E_ATRAPA_PORT
# (9197; atrapa piaskownicy na 9199 zostaje nietknięta), trzy profile jednorazowe test-e2e-a, test-e2e-b, test-e2e-j
# (świeży API_SERVER_KEY każdy, zgody ręczne z czasem 20 s, wpisy "test": true w agenci.json) i sprawdzenie, że brama
# obsługuje nowy profil bez restartu (inaczej jeden restart bramy, zapisany w raporcie). Pułapka usuwa przy każdym
# wyjściu atrapę, profile, wpisy agenci.json, tablicę kanbana testu, resztki wątków [E2E], nagrobki sesji profili testu,
# dzienniki ich bram i (gdy wolno) nadzorców s6 po usuniętych usługach (tests/live/jarvo_e2e_etap2.py).
set -euo pipefail
ETAP="${1:-etap1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
die() { echo "jarvo-e2e: $*" >&2; exit 2; }

[[ "${JARVO_E2E:-}" == 1 ]] || die "brak JARVO_E2E=1 w env kontenera (piaskownica: sandbox-up.sh; inaczej JARVO_E2E=1 w compose/.env i deploy)"
[[ "$(id -un)" == hermes ]] || die "uruchom jako hermes: docker exec -u hermes jarvo-hermes …"
[[ -n "${HERMES_DASHBOARD_BASIC_AUTH_PASSWORD:-}" ]] || die "brak hasła dashboardu w env kontenera"
command -v node >/dev/null || die "brak node w PATH"
export NODE_PATH="${NODE_PATH:-/opt/jarvo/node/node_modules}"

case "$ETAP" in etap1|etap2) ;; *) die "nieznany etap $ETAP (są: etap1, etap2)" ;; esac

TS="$(date +%Y%m%d-%H%M%S)"
DANE="${JARVO_DATA_DIR:-/opt/data/jarvo}"
PORT_STRONY="${JARVO_E2E_PORT:-9188}"
PORT_ATRAPY="${JARVO_E2E_ATRAPA_PORT:-9197}"
POMOC="$ROOT/tests/live/jarvo_e2e_etap2.py"
export JARVO_E2E_DIR="/tmp/jarvo-e2e/$TS"
export JARVO_E2E_INBOX="$DANE/inbox/jarvo-e2e-$TS"
export JARVO_E2E_STRONA="http://localhost:$PORT_STRONY"
export JARVO_E2E_ATRAPA_DZIENNIK="$JARVO_E2E_DIR/atrapa.jsonl"
SERWER=""
ATRAPA=""
WYNIK=1

resztki() {
  # fiksturki, pliki konwertera z prób (nazwy jarvo-e2e-*) i linki podglądu do nich
  find "$DANE/inbox" -maxdepth 3 -name 'jarvo-e2e-*' -prune -exec rm -rf {} + 2>/dev/null || true
  python3 -I - "$DANE/state/preview-links.json" "$DANE/inbox/" <<'PY' || true
import fcntl, json, sys
from pathlib import Path
plik, przedrostek = Path(sys.argv[1]), sys.argv[2] + "jarvo-e2e-"
if plik.is_file():
    with open(plik.with_suffix(".lock"), "w") as blokada:
        fcntl.flock(blokada, fcntl.LOCK_EX)
        dane = json.loads(plik.read_text(encoding="utf-8") or "{}")
        nowe = {t: v for t, v in dane.items() if not str((v or {}).get("root", "")).startswith(przedrostek)}
        if len(nowe) != len(dane):
            tmp = plik.with_suffix(".tmp")
            tmp.write_text(json.dumps(nowe), encoding="utf-8")
            tmp.replace(plik)
PY
}
sprzataj() {
  [[ -n "$SERWER" ]] && kill "$SERWER" 2>/dev/null || true
  [[ -n "$ATRAPA" ]] && kill "$ATRAPA" 2>/dev/null || true
  if [[ "$ETAP" == etap2 ]]; then
    python3 "$POMOC" sprzataj >&2 || echo "jarvo-e2e: sprzątanie etapu 2 nieudane (profile test-e2e-*?)" >&2
    rm -rf /tmp/jarvo-e2e-zgoda* /tmp/jarvo-e2e-import-* 2>/dev/null || true
  fi
  resztki
  if [[ $WYNIK == 0 ]]; then rm -rf "$JARVO_E2E_DIR"; else echo "jarvo-e2e: zrzuty i raport: $JARVO_E2E_DIR" >&2; fi
  # starsze przebiegi zostawiają tylko ostatnie 3 katalogi zrzutów
  find /tmp/jarvo-e2e -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | head -n -3 | xargs -r rm -rf
}
trap sprzataj EXIT
trap 'exit 130' INT TERM

czekaj_na() {   # URL odpowiada (do 6 s)
  for _ in $(seq 1 30); do
    python3 -I -c "import urllib.request; urllib.request.urlopen('$1', timeout=1)" 2>/dev/null && return 0
    sleep 0.2
  done
  return 1
}

resztki
mkdir -p "$JARVO_E2E_DIR" "$JARVO_E2E_INBOX"
if [[ "$ETAP" == etap1 ]]; then
  # zwykła strona tej samej witryny co dashboard (localhost, inny port), bez CSP sandbox: próby CSRF i ramka obca
  python3 -I -m http.server "$PORT_STRONY" --bind 127.0.0.1 --directory "$JARVO_E2E_INBOX" >/dev/null 2>&1 &
  SERWER=$!
  czekaj_na "http://127.0.0.1:$PORT_STRONY/" || true
else
  python3 "$POMOC" sprzataj >/dev/null 2>&1 || true            # resztki po przerwanym przebiegu
  python3 -I "$ROOT/scripts/atrapa_modelu.py" --port "$PORT_ATRAPY" --dziennik "$JARVO_E2E_ATRAPA_DZIENNIK" >/dev/null 2>&1 &
  ATRAPA=$!
  czekaj_na "http://127.0.0.1:$PORT_ATRAPY/v1/models" || die "atrapa modelu nie wstała na porcie $PORT_ATRAPY"
  python3 "$POMOC" przygotuj --atrapa "http://127.0.0.1:$PORT_ATRAPY/v1" >&2 || die "profile testowe nie powstały"
  # nowy profil bez restartu bramy (profiles_to_serve liczone przy każdym żądaniu, klucz po fstat .env); restart
  # tylko, gdy brama trzyma w pamięci state.db profilu test-e2e-* z poprzedniego przebiegu (baza sesji: 500)
  if BRAMA="$(python3 "$POMOC" brama-gotowa --czekaj 20)"; then
    export JARVO_E2E_BRAMA="bez restartu: $BRAMA"
  else
    echo "jarvo-e2e: brama nie obsługuje nowych profili ($BRAMA) — restart bramy (tylko piaskownica)" >&2
    hermes gateway restart >/dev/null 2>&1 || true
    BRAMA="$(python3 "$POMOC" brama-gotowa --czekaj 90)" || die "brama nie obsługuje profili test-e2e-* także po restarcie"
    export JARVO_E2E_BRAMA="po restarcie bramy: $BRAMA"
  fi
  sleep 2                                                      # obserwator silnika widzi agenci.json
fi

set +e
node "$ROOT/tests/live/jarvo_e2e.cjs" "$ETAP" | tee "$JARVO_E2E_DIR/raport.json"
WYNIK=${PIPESTATUS[0]}
set -e
exit "$WYNIK"
