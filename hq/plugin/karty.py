"""Karty pracy w wątku (docs/HQ.md „Rozmowy”, „Karty pracy”): stan przekazań Jarva na żywo z tablicy kanbana
i z sesji pracowników, żeby właściciel widział, kto pracuje, co robi teraz i co zrobił.

Oś wątku ma pozycje `przekazanie` (kanban_create Jarva, scalanie.py) z `task_id`. Aplikacja pyta o nie
`GET /karty?id=…` (co kilka sekund, dopóki któraś pracuje) i `GET /karty/{id}` (rozwinięta karta: przebieg pracy).

Karta: {task_id, tytul, agent (wykonawca: profil pierwszego przebiegu, bez niego przypisany), etap, od, koniec,
ostatnio (ostatni znak życia), notatka (ostatnia notatka heartbeat wykonawcy), teraz (ostatni krok jego sesji, gdy
pracuje), podsumowanie (co zrobił: ostatnie podsumowanie wykonawcy), ocena (werdykt sędziego), pliki (artefakty),
proby (liczba przebiegów pracy), powod (blokada albo uwagi do poprawki)}. Etapy: `czeka`, `pracuje`, `do_oceny`
(oddana, sędzia jeszcze nie zaczął), `ocena` (sędzia sprawdza), `poprawki` (sędzia odesłał, wykonawca znowu
pracuje), `zablokowana`, `gotowe`, `porzucona`.
`przebieg(…)`: kroki i wypowiedzi wykonawcy i sędziego z ich sesji kanbana (hq_core.activity_from_messages), po
kolei, z nazwą profilu, do rozwiniętej karty („jak pracuje”). Sesję przebiegu znajdujemy po profilu, źródle
`kanban` i czasie startu (Hermes nie zapisuje przy przebiegu identyfikatora sesji).
Czysty Python (sqlite3 tylko do odczytu); testy: tests/test_karty.py.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable, Iterable

ID_RE = re.compile(r"^t_[0-9a-f]{4,32}$")
NAJWIECEJ = 40                 # kart w jednym pytaniu
OKNO_SESJI = 120.0             # sesja pracownika startuje najwyżej tyle sekund po przebiegu
KROKI_PRZEBIEGU = 80
PODSUMOWANIE_MAKS = 1600
NOTATKA_MAKS = 400


def _polacz(db: Path | str) -> sqlite3.Connection | None:
    p = Path(db)
    if not p.is_file():
        return None
    try:
        conn = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return None
    conn.row_factory = sqlite3.Row
    return conn


def _json(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def _przytnij(tekst: Any, n: int) -> str:
    t = " ".join(str(tekst or "").split()) if n <= NOTATKA_MAKS else str(tekst or "").strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def poprawne_id(ids: Iterable[str]) -> list[str]:
    """Identyfikatory kart z zapytania: tylko `t_<hex>`, bez powtórek, najwyżej NAJWIECEJ."""
    out: list[str] = []
    for i in ids:
        i = str(i or "").strip()
        if ID_RE.fullmatch(i) and i not in out:
            out.append(i)
    return out[:NAJWIECEJ]


def _pliki(*metadane: dict) -> list[str]:
    out: list[str] = []
    for m in metadane:
        for p in m.get("artifacts") or []:
            if isinstance(p, str) and p.strip() and p not in out:
                out.append(p.strip())
    return out[:12]


def _etap(status: str, assignee: str, wykonawca: str, recenzent: str | None, ostatnie: str | None) -> str:
    if status in ("done", "archived"):
        return "gotowe"
    if status == "review":
        return "do_oceny"
    if status == "blocked":
        return "porzucona" if ostatnie == "gave_up" else "zablokowana"
    if status == "running":
        if recenzent and assignee == recenzent and wykonawca != recenzent:
            return "ocena"
        return "poprawki" if ostatnie == "changes_requested" else "pracuje"
    return "poprawki" if ostatnie == "changes_requested" else "czeka"


def _sesja_przebiegu(state_db: Path, run: sqlite3.Row, tytul: str) -> tuple[str | None, sqlite3.Connection | None]:
    """Sesja kanbana profilu, która ruszyła razem z przebiegiem (najbliższa po starcie; tytuł karty wygrywa)."""
    conn = _polacz(state_db)
    if conn is None or not run["started_at"]:
        return None, conn
    try:
        rows = conn.execute(
            "SELECT id, title, started_at FROM sessions WHERE source = 'kanban' AND started_at >= ? AND started_at <= ? "
            "ORDER BY started_at", (float(run["started_at"]) - 5, float(run["started_at"]) + OKNO_SESJI)).fetchall()
    except sqlite3.Error:
        return None, conn
    if not rows:
        return None, conn
    po_tytule = [r for r in rows if (r["title"] or "").strip() == tytul.strip()]
    return (po_tytule or rows)[0]["id"], conn


def _ostatni_krok(conn: sqlite3.Connection, sesja: str, etykieta: Callable) -> dict | None:
    try:
        r = conn.execute("SELECT content, tool_calls, timestamp FROM messages WHERE session_id = ? AND role = 'assistant' "
                         "ORDER BY id DESC LIMIT 1", (sesja,)).fetchone()
    except sqlite3.Error:
        return None
    if r is None:
        return None
    try:
        wywolania = json.loads(r["tool_calls"]) if r["tool_calls"] else []
    except ValueError:
        wywolania = []
    for tc in reversed(wywolania if isinstance(wywolania, list) else []):
        fn = (tc or {}).get("function") or {}
        if fn.get("name"):
            e = etykieta(fn["name"], fn.get("arguments"))
            return {"ts": r["timestamp"], "verb": e.get("verb"), "verb_en": e.get("verb_en"), "detail": e.get("detail", ""),
                    "ikona": e.get("icon")}
    tekst = r["content"] if isinstance(r["content"], str) else ""
    return {"ts": r["timestamp"], "tekst": _przytnij(tekst, 200)} if tekst.strip() else None


def stan_kart(kanban_db: Path | str, ids: Iterable[str], *, recenzent: str | None,
              state_db: Callable[[str], Path | None], etykieta: Callable, utajnij: Callable[[str], str] = str) -> dict:
    """{task_id: karta} dla kart, które są na tablicy (nieznane pominięte)."""
    ids = poprawne_id(ids)
    conn = _polacz(kanban_db) if ids else None
    if conn is None:
        return {}
    out: dict[str, dict] = {}
    try:
        znak = ",".join("?" * len(ids))
        zadania = conn.execute(f"SELECT * FROM tasks WHERE id IN ({znak})", ids).fetchall()
        for t in zadania:
            tid = t["id"]
            runs = conn.execute("SELECT * FROM task_runs WHERE task_id = ? ORDER BY id", (tid,)).fetchall()
            zdarzenia = conn.execute("SELECT kind, payload, run_id, created_at FROM task_events WHERE task_id = ? "
                                     "ORDER BY id", (tid,)).fetchall()
            assignee = t["assignee"] or ""
            wykonawca = next((r["profile"] for r in runs if r["profile"] and r["profile"] != recenzent), None) \
                or (runs[0]["profile"] if runs and runs[0]["profile"] else assignee)
            prace = [r for r in runs if r["profile"] == wykonawca]
            sedzia = [r for r in runs if recenzent and r["profile"] == recenzent and wykonawca != recenzent]
            istotne = [z["kind"] for z in zdarzenia if z["kind"] in ("review_requested", "changes_requested", "completed",
                                                                     "blocked", "gave_up", "unblocked", "crashed",
                                                                     "timed_out")]
            ostatnie = istotne[-1] if istotne else None
            notatka, powod = "", ""
            for z in zdarzenia:
                p = _json(z["payload"])
                if z["kind"] == "heartbeat" and p.get("note"):
                    notatka = p["note"]
                if z["kind"] in ("blocked", "changes_requested", "gave_up") and (p.get("reason") or p.get("summary")):
                    powod = p.get("reason") or p.get("summary")
            podsumowanie = next((r["summary"] for r in reversed(prace) if r["summary"]), "") or ""
            ocena = next((r["summary"] for r in reversed(sedzia) if r["summary"]), "") or ""
            pliki = _pliki(*(_json(r["metadata"]) for r in reversed(runs)))
            etap = _etap(t["status"] or "", assignee, wykonawca or "", recenzent, ostatnie)
            karta = {
                "task_id": tid, "tytul": t["title"] or "", "agent": wykonawca or assignee, "przypisany": assignee,
                "etap": etap, "od": t["started_at"], "koniec": t["completed_at"] if etap == "gotowe" else None,
                "ostatnio": t["last_heartbeat_at"], "notatka": utajnij(_przytnij(notatka, NOTATKA_MAKS)),
                "podsumowanie": utajnij(_przytnij(podsumowanie, PODSUMOWANIE_MAKS)),
                "ocena": utajnij(_przytnij(ocena, NOTATKA_MAKS)) if etap == "gotowe" else "",
                "pliki": pliki, "proby": len(prace), "powod": utajnij(_przytnij(powod, NOTATKA_MAKS)),
                "teraz": None,
            }
            if t["status"] == "running" and runs:
                biezacy = next((r for r in runs if r["id"] == t["current_run_id"]), runs[-1])
                sciezka = state_db(biezacy["profile"] or assignee)
                if sciezka is not None:
                    sesja, sconn = _sesja_przebiegu(sciezka, biezacy, t["title"] or "")
                    try:
                        if sesja and sconn is not None:
                            krok = _ostatni_krok(sconn, sesja, etykieta)
                            if krok:
                                karta["teraz"] = {k: (utajnij(v) if isinstance(v, str) else v) for k, v in krok.items()}
                    finally:
                        if sconn is not None:
                            sconn.close()
            out[tid] = karta
    except sqlite3.Error:
        return out
    finally:
        conn.close()
    return out


def przebieg(kanban_db: Path | str, tid: str, *, recenzent: str | None, state_db: Callable[[str], Path | None],
             wiadomosci: Callable[[Path, str], list[dict]], aktywnosc: Callable[[list[dict]], list[dict]],
             utajnij: Callable[[str], str] = str) -> list[dict]:
    """Przebieg pracy karty: [{profil, rola (praca|ocena), od, koniec, wynik, kroki: [...]}] po kolei, najwyżej
    KROKI_PRZEBIEGU kroków razem (najnowsze). `wiadomosci(state_db, sesja)` czyta wiersze sesji, `aktywnosc` to
    hq_core.activity_from_messages."""
    if not poprawne_id([tid]):
        return []
    conn = _polacz(kanban_db)
    if conn is None:
        return []
    try:
        t = conn.execute("SELECT title FROM tasks WHERE id = ?", (tid,)).fetchone()
        runs = conn.execute("SELECT * FROM task_runs WHERE task_id = ? ORDER BY id", (tid,)).fetchall() if t else []
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    wykonawca = next((r["profile"] for r in runs if r["profile"] and r["profile"] != recenzent), None)
    out: list[dict] = []
    for r in runs:
        sciezka = state_db(r["profile"] or "") if r["profile"] else None
        kroki: list[dict] = []
        if sciezka is not None:
            sesja, sconn = _sesja_przebiegu(sciezka, r, t["title"] or "")
            if sconn is not None:
                sconn.close()
            if sesja:
                for k in aktywnosc(wiadomosci(sciezka, sesja)):
                    if k.get("kind") == "brief":
                        continue                      # treść zlecenia jest na karcie, nie powtarzamy jej
                    kroki.append({x: (utajnij(v) if isinstance(v, str) else v) for x, v in k.items()})
        out.append({"profil": r["profile"], "rola": "ocena" if recenzent and r["profile"] == recenzent and wykonawca
                    and wykonawca != recenzent else "praca", "od": r["started_at"], "koniec": r["ended_at"],
                    "wynik": r["outcome"], "kroki": kroki})
    zostalo = KROKI_PRZEBIEGU
    for p in reversed(out):
        p["kroki"] = p["kroki"][-zostalo:] if zostalo > 0 else []
        p["ukryte"] = 0
        zostalo -= len(p["kroki"])
    return out
