#!/usr/bin/env bash
# Kuźnia skilli (docs/RSI.md §6): poprawka jednego skilla agenta → pojedynek w evals na stagingu → bramki → raport
# i karta decyzji dla właściciela. Niczego nie wdraża: zmiana wchodzi do repo dopiero po Twoim „ok”.
#
#   bash scripts/kuznia.sh --agent jarvo-web --skill web/nowa-strona --proponuj            # proponuje model (evals.proposer)
#   bash scripts/kuznia.sh --agent jarvo-web --skill web/nowa-strona --kandydat moj.md     # własna wersja SKILL.md
#        [--powtorzenia 3] [--budzet 5] [--bez-karty]
#
# Kroki: start (koszt, budżet, sędzia innej rodziny niż proponujący i agent) → [kandydat własny: limity] → evals bazy
# (obecny build, oba zbiory, powtórzenia) → [--proponuj: propozycja z porażek zbioru roboczego] → limity (przyrost
# ≤ 20%, nazwa, skan, bez odwołań i cytatów z evals) → build kandydata (ten sam build.py, podmieniony jeden SKILL.md)
# → evals kandydata → bramki → raport. Dane: ${JARVO_STAGING:-/srv/jarvo/staging}/kuznia/<agent>-<skill>-<czas>;
# wyniki kuźni nie trafiają do historii evals floty. Raport, patch i wynik: /opt/data/jarvo/kuznia/<id> w jarvo-hermes,
# a przy werdykcie „do decyzji” karta needs_input dla Jarva (decyzja w HQ). Kod wyjścia: 0 do decyzji, 1 odrzucony
# albo bez pomiaru, 2 błąd.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${JARVO_COMPOSE_DIR:-/srv/jarvo/compose}"
STAGING="${JARVO_STAGING:-/srv/jarvo/staging}"
BUILD="${JARVO_BUILD:-/srv/jarvo/build}"
AGENT="" SKILL="" KANDYDAT="" PROPONUJ=0 POWT=3 BUDZET=5 KARTA=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENT="$2"; shift 2 ;;
    --skill) SKILL="$2"; shift 2 ;;
    --kandydat) KANDYDAT="$2"; shift 2 ;;
    --proponuj) PROPONUJ=1; shift ;;
    --powtorzenia) POWT="$2"; shift 2 ;;
    --budzet) BUDZET="$2"; shift 2 ;;
    --bez-karty) KARTA=0; shift ;;
    *) echo "Nieznana opcja: $1"; exit 2 ;;
  esac
done
[[ -n "$AGENT" && -n "$SKILL" ]] || { echo "Podaj --agent i --skill (np. --skill web/nowa-strona)"; exit 2; }
[[ $PROPONUJ -eq 1 || -n "$KANDYDAT" ]] || { echo "Podaj --proponuj albo --kandydat <SKILL.md>"; exit 2; }
[[ $PROPONUJ -eq 1 && -n "$KANDYDAT" ]] && { echo "Albo --proponuj, albo --kandydat"; exit 2; }
[[ "$AGENT" =~ ^[a-z0-9-]+$ && "$SKILL" =~ ^[a-z0-9_/-]+$ && "$SKILL" != *..* ]] || { echo "Zła nazwa agenta albo skilla"; exit 2; }
[[ -f "$ROOT/profiles/$AGENT/skills/$SKILL/SKILL.md" ]] || { echo "Nie ma skilla profiles/$AGENT/skills/$SKILL"; exit 2; }
[[ -f "$BUILD/BUILD.json" ]] || { echo "Brak buildu: najpierw scripts/deploy.sh"; exit 2; }

ID="$AGENT-${SKILL//\//-}-$(date +%Y%m%d-%H%M%S)"
W="$STAGING/kuznia/$ID"
sudo install -d -m 755 -o 10000 -g 10000 "$STAGING/kuznia" "$W" "$W/build" "$W/baza" "$W/kandydat"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$COMPOSE_DIR/.env")
PY=/opt/hermes/.venv/bin/python
ONEOFF=(run --rm --no-deps -T --entrypoint "" -u 10000:10000 -e HOME=/tmp -v "$W:/kuznia")
kuznia() { "${COMPOSE[@]}" "${ONEOFF[@]}" hermes "$PY" /opt/jarvo/repo/scripts/kuznia.py "$@"; }
koniec() { echo "Katalog kuźni: $W"; exit "$1"; }

echo "▶ Kuźnia $ID"
kuznia start --agent "$AGENT" --skill "$SKILL" --powtorzenia "$POWT" --budzet "$BUDZET" --out /kuznia \
  | sudo tee "$W/start.txt" || koniec 1
SEDZIA="$(sudo tail -n 1 "$W/start.txt")"

if [[ -n "$KANDYDAT" ]]; then
  sudo install -m 644 -o 10000 -g 10000 "$KANDYDAT" "$W/kandydat.md"
  echo "▶ Limity kandydata (przed evals)"
  kuznia sprawdz --agent "$AGENT" --skill "$SKILL" --kandydat /kuznia/kandydat.md --out /kuznia || koniec 1
fi

# evals jednego buildu na osobnych danych stagingu; kod 1 (coś nie przeszło) i 3 (kanarek) oceniają bramki
evals() {  # <katalog danych> [JARVO_BUILD]
  local rc=0
  JARVO_STAGING="$1" JARVO_BUILD="${2:-$BUILD}" bash "$ROOT/scripts/evals-staging.sh" --bez-publikacji \
    --agent "$AGENT" --powtorzenia "$POWT" --judge-model "$SEDZIA" || rc=$?
  [[ $rc -eq 2 ]] && { echo "✗ evals nie ruszyły (kod 2)"; koniec 2; }
  return 0
}
przebieg() {  # najnowszy <agent>.jsonl w wynikach danego stagingu (ścieżka w kontenerze)
  local d
  d="$(sudo find "$W/$1/hermes/eval-results" -mindepth 1 -maxdepth 1 -type d -name '2*' | sort | tail -n 1)"
  [[ -n "$d" && -f "$d/$AGENT.jsonl" ]] || { echo "✗ brak wyników evals ($1)"; koniec 2; }
  echo "/kuznia/$1/hermes/eval-results/$(basename "$d")/$AGENT.jsonl"
}

echo "▶ Evals bazy (obecny build)"
evals "$W/baza"
BAZA="$(przebieg baza)"

if [[ $PROPONUJ -eq 1 ]]; then
  echo "▶ Propozycja z porażek zbioru roboczego"
  LEKCJE=()
  if docker ps --format '{{.Names}}' | grep -qx jarvo-hermes \
      && docker exec jarvo-hermes test -f /opt/data/jarvo/knowledge/fleet/lekcje.md; then
    docker exec jarvo-hermes cat /opt/data/jarvo/knowledge/fleet/lekcje.md | sudo tee "$W/lekcje.md" >/dev/null
    LEKCJE=(--lekcje /kuznia/lekcje.md)
  fi
  kuznia proponuj --agent "$AGENT" --skill "$SKILL" --przebieg "$BAZA" "${LEKCJE[@]+"${LEKCJE[@]}"}" \
    --out /kuznia/kandydat.md || koniec 1
  echo "▶ Limity kandydata"
  kuznia sprawdz --agent "$AGENT" --skill "$SKILL" --kandydat /kuznia/kandydat.md --out /kuznia || koniec 1
fi

echo "▶ Build kandydata (podmieniony jeden SKILL.md)"
"${COMPOSE[@]}" run --rm --no-deps -T --entrypoint "" -u 10000:10000 -e HOME=/tmp \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/opt/jarvo/repo \
  -v "$W/build:/out" -v "$COMPOSE_DIR:/opt/jarvo/compose:ro" \
  -v "$W/kandydat.md:/opt/jarvo/repo/profiles/$AGENT/skills/$SKILL/SKILL.md:ro" \
  -e JARVO_HERMES_PYTHON="$PY" \
  hermes "$PY" /opt/jarvo/repo/scripts/build.py --hermes-src /opt/hermes --out /out \
  --env-file /opt/jarvo/compose/jarvo.env --runtime-build-dir /opt/jarvo/build >"$W/build.log" 2>&1 \
  || { tail -n 20 "$W/build.log"; echo "✗ build kandydata"; koniec 2; }
if sudo cmp -s "$BUILD/profiles/$AGENT/skills/$SKILL/SKILL.md" "$W/build/profiles/$AGENT/skills/$SKILL/SKILL.md"; then
  echo "✗ build kandydata ma ten sam SKILL.md co baza (podmiana nie zadziałała)"; koniec 2
fi

echo "▶ Evals kandydata"
evals "$W/kandydat" "$W/build"
KAND="$(przebieg kandydat)"

echo "▶ Bramki"
RC=0
kuznia ocen --agent "$AGENT" --skill "$SKILL" --baza "$BAZA" --kandydat-wyniki "$KAND" --out /kuznia \
  --katalog-prod "/opt/data/jarvo/kuznia/$ID" || RC=$?

# raport do działającej floty (HQ, Jarvo); przy werdykcie „do decyzji” karta needs_input dla Jarva
if docker ps --format '{{.Names}}' | grep -qx jarvo-hermes; then
  PLIKI=(raport.md meta.json)
  for f in zmiana.patch limity.json wynik.json kandydat.md; do sudo test -f "$W/$f" && PLIKI+=("$f"); done
  sudo tar -C "$W" -cf - "${PLIKI[@]}" | docker exec -i -u 10000:10000 jarvo-hermes \
    sh -c "mkdir -p /opt/data/jarvo/kuznia/$ID && tar -C /opt/data/jarvo/kuznia/$ID -xf -" \
    && echo "✓ Raport w działającej flocie: /opt/data/jarvo/kuznia/$ID/raport.md"
  if [[ $RC -eq 0 && $KARTA -eq 1 ]] && sudo test -f "$W/karta.md"; then
    TID="$(sudo cat "$W/karta.md" | docker exec -i -u hermes jarvo-hermes bash -c \
      "export PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:\$PATH; hermes kanban create 'Kuźnia: $AGENT / $SKILL, decyzja' \
       --assignee jarvo --body-file - --initial-status blocked --idempotency-key 'kuznia-$ID' --created-by kuznia --json" \
      | sed -n 's/.*"id": *"\([^"]*\)".*/\1/p' | head -n 1)"
    if [[ -n "$TID" ]]; then
      docker exec -u hermes jarvo-hermes bash -c "export PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:\$PATH; \
        hermes kanban block '$TID' --kind needs_input 'Wprowadzić poprawkę skilla $SKILL ($AGENT) z kuźni? Raport: /opt/data/jarvo/kuznia/$ID/raport.md'" >/dev/null \
        && echo "✓ Karta decyzji $TID (HQ → Decyzje)"
    else
      echo "! Nie udało się założyć karty decyzji; raport jest w /opt/data/jarvo/kuznia/$ID"
    fi
  fi
fi
koniec "$RC"
