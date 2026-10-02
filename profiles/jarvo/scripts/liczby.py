#!/usr/bin/env python3
"""Liczby floty bez modelu (0 tokenów): jakość, eskalacje, awarie, cisza i tokeny z kanban.db i state.db.

    python3 liczby.py [--dni 7] [--dane /opt/data] [--json]

Jedna definicja dla przeglądu tygodnia (fleet_report.py) i Jarvo HQ (hqbuild kopiuje ten plik do pluginu):
karta przyjęta za 1. razem = zakończona, oddana do recenzji i bez żadnego `changes_requested`; liczy się
wykonawcy (payload.implementer z recenzji), nie temu, kto ją akurat trzyma. Tokeny to suma sesji profilu
w oknie; złotówek tu nie liczymy (zależą od dostawcy i cennika, a na planie ChatGPT to zużycie limitu).
Ostatnia linia wyjścia to JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

DZIEN = 86400
CISZA_MIN = int(os.environ.get("JARVO_CISZA_MIN", "60"))      # run bez znaku życia dłużej = cisza
AWARIE = ("crashed", "timed_out", "spawn_failed", "reclaimed", "gave_up")


def _payload(e: dict) -> dict:
    p = e.get("payload")
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except ValueError:
            p = None
    return p if isinstance(p, dict) else {}


def jakosc(karty: list[dict], zdarzenia: dict[str, list[dict]]) -> dict[str, dict]:
    """Zakończone karty → na wykonawcę: done, reviews, first_pass, changes_requested (rundy), with_changes (karty)."""
    out: dict[str, dict] = {}
    for k in karty:
        ev = zdarzenia.get(k["id"]) or []
        rec = [e for e in ev if e.get("kind") == "review_requested"]
        rundy = sum(1 for e in ev if e.get("kind") == "changes_requested")
        kto = next((p["implementer"] for e in reversed(rec) if (p := _payload(e)).get("implementer")), None)
        s = out.setdefault(kto or k.get("assignee") or "?",
                           {"done": 0, "reviews": 0, "first_pass": 0, "changes_requested": 0, "with_changes": 0})
        s["done"] += 1
        s["reviews"] += len(rec)
        s["changes_requested"] += rundy
        s["with_changes"] += rundy > 0
        s["first_pass"] += bool(rec) and rundy == 0
    return out


def _ro(path: Path) -> sqlite3.Connection | None:
    if not path.is_file():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _w(ids: list[str]):
    for i in range(0, len(ids), 500):            # limit zmiennych SQLite
        part = ids[i:i + 500]
        yield part, ",".join("?" * len(part))


def zdarzenia_jakosci(conn: sqlite3.Connection, ids: list[str]) -> dict[str, list[dict]]:
    """Wszystkie recenzje i poprawki tych kart, bez względu na wiek zdarzenia (nie tylko z okna)."""
    out: dict[str, list[dict]] = {}
    for part, q in _w(ids):
        for r in conn.execute(f"SELECT task_id, kind, payload FROM task_events WHERE kind IN ('review_requested', "
                              f"'changes_requested') AND task_id IN ({q}) ORDER BY created_at, id", part):
            out.setdefault(r["task_id"], []).append(dict(r))
    return out


def _tokeny(dane: Path, od: float) -> dict[str, dict]:
    out = {}
    bazy = sorted((dane / "profiles").glob("*/state.db")) + [dane / "state.db"]
    for db in bazy:
        conn = _ro(db)
        if conn is None:
            continue
        try:
            r = conn.execute("SELECT count(*) AS sesje, sum(input_tokens) AS wejscie, sum(output_tokens) AS wyjscie, "
                             "sum(cache_read_tokens) AS cache_odczyt, sum(cache_write_tokens) AS cache_zapis, "
                             "sum(reasoning_tokens) AS rozumowanie FROM sessions WHERE started_at >= ?", (od,)).fetchone()
        except sqlite3.Error:
            continue
        finally:
            conn.close()
        if r and r["sesje"]:
            out[db.parent.name if db.parent != dane else "host"] = {k: int(r[k] or 0) for k in r.keys()}
    return out


def policz(dane: Path, teraz: float, dni: int = 7) -> dict:
    od = teraz - dni * DZIEN
    wynik: dict = {"okno_dni": dni, "jakosc": {}, "eskalacje": {}, "awarie": {}, "cisza": {}, "tokeny": {}}
    conn = _ro(dane / "kanban.db")
    if conn is not None:
        try:
            karty = [dict(r) for r in conn.execute(
                "SELECT id, assignee FROM tasks WHERE status IN ('done', 'archived') AND completed_at >= ?", (od,))]
            wynik["jakosc"] = jakosc(karty, zdarzenia_jakosci(conn, [k["id"] for k in karty]))
            esk = {"needs_input": 0, "capability": 0, "inne": 0, "gave_up": 0}
            for r in conn.execute("SELECT kind, payload FROM task_events WHERE created_at >= ? AND kind IN "
                                  "('blocked', 'gave_up')", (od,)):
                if r["kind"] == "gave_up":
                    esk["gave_up"] += 1
                else:
                    rodzaj = _payload(dict(r)).get("kind")
                    esk[rodzaj if rodzaj in ("needs_input", "capability") else "inne"] += 1
            wynik["eskalacje"] = esk
            wynik["awarie"] = {o: n for o, n in conn.execute(
                f"SELECT outcome, count(*) FROM task_runs WHERE started_at >= ? AND outcome IN "
                f"({','.join('?' * len(AWARIE))}) GROUP BY outcome", (od, *AWARIE))}
            granica = teraz - CISZA_MIN * 60
            cisza = [r["task_id"] for r in conn.execute(
                "SELECT task_id FROM task_runs WHERE ended_at IS NULL AND COALESCE(last_heartbeat_at, started_at) < ?",
                (granica,))]
            zablokowane = [r["id"] for r in conn.execute("SELECT id FROM tasks WHERE status = 'blocked'")]
            bez_powodu = []
            for part, q in _w(zablokowane):
                ostatnie: dict[str, dict] = {}
                for r in conn.execute(f"SELECT task_id, payload FROM task_events WHERE kind = 'blocked' "
                                      f"AND task_id IN ({q}) ORDER BY created_at, id", part):
                    ostatnie[r["task_id"]] = _payload(dict(r))
                bez_powodu += [t for t in part if not str(ostatnie.get(t, {}).get("reason") or "").strip()]
            wynik["cisza"] = {"bez_sygnalu": cisza, "blokady_bez_powodu": bez_powodu}
        except sqlite3.Error as exc:                  # starsza albo inna wersja tablicy: liczby częściowe, nie cisza
            wynik["blad"] = str(exc)[:200]
        finally:
            conn.close()
    wynik["tokeny"] = _tokeny(dane, od)
    zrobione = sum(s["done"] for s in wynik["jakosc"].values())
    przyjete = sum(s["first_pass"] for s in wynik["jakosc"].values())
    wynik["za_1_razem"] = {"przyjete": przyjete, "zrobione": zrobione,
                           "procent": round(100 * przyjete / zrobione) if zrobione else None}
    wynik["tokeny_na_karte"] = {a: round(sum(v for k, v in t.items() if k != "sesje") / wynik["jakosc"][a]["done"])
                                for a, t in wynik["tokeny"].items() if wynik["jakosc"].get(a, {}).get("done")}
    return wynik


def dane_domyslne() -> Path:
    if os.environ.get("JARVO_DATA_DIR"):
        return Path(os.environ["JARVO_DATA_DIR"])
    h = Path(os.environ.get("HERMES_HOME", "/opt/data"))
    return h.parent.parent if h.parent.name == "profiles" else h


def opis(w: dict) -> list[str]:
    z = w["za_1_razem"]
    linie = [f"Liczby floty, ostatnie {w['okno_dni']} dni:",
             f"- za 1. razem: {z['przyjete']}/{z['zrobione']}" + (f" ({z['procent']}%)" if z["procent"] is not None else "")]
    for a, s in sorted(w["jakosc"].items()):
        linie.append(f"  {a}: {s['first_pass']}/{s['done']}, rund poprawek {s['changes_requested']}")
    e = w["eskalacje"]
    if e:
        linie.append(f"- eskalacje: pytania {e['needs_input']}, poza zakresem {e['capability']}, inne {e['inne']}, "
                     f"porzucone {e['gave_up']}")
    linie.append("- awarie pracownika: " + (", ".join(f"{k} {v}" for k, v in w["awarie"].items()) or "brak"))
    c = w["cisza"]
    if c:
        linie.append(f"- cisza: bez sygnału > {CISZA_MIN} min {len(c['bez_sygnalu'])}, blokady bez powodu "
                     f"{len(c['blokady_bez_powodu'])}")
    for a, t in sorted(w["tokeny"].items()):
        linie.append(f"- tokeny {a}: wejście {t['wejscie']}, cache {t['cache_odczyt']}, wyjście {t['wyjscie']}, "
                     f"sesje {t['sesje']}" + (f", na kartę {w['tokeny_na_karte'][a]}" if a in w["tokeny_na_karte"] else ""))
    if w.get("blad"):
        linie.append(f"- uwaga: tablica odczytana częściowo ({w['blad']})")
    return linie


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dni", type=int, default=7)
    ap.add_argument("--dane", type=Path, default=None, help="katalog danych Hermesa (domyślnie z HERMES_HOME)")
    ap.add_argument("--teraz", type=float, default=None)
    ap.add_argument("--json", action="store_true", help="tylko JSON")
    a = ap.parse_args(argv)
    w = policz(a.dane or dane_domyslne(), a.teraz or time.time(), a.dni)
    if not a.json:
        print("\n".join(opis(w)))
    print(json.dumps(w, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
