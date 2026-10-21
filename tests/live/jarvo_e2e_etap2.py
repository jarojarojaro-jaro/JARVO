#!/usr/bin/env python3
"""Pomocnik testu E2E etapu 2 (silnik rozmów, docs/HQ.md §2e): wszystko, czego Playwright nie zrobi ze strony.
Uruchamiają go scripts/jarvo-e2e.sh i tests/live/jarvo_e2e.cjs w kontenerze jarvo-hermes jako hermes (Python
z /opt/hermes/.venv: yaml, Hermes). Każda komenda drukuje jeden JSON na stdout.

Klucze `API_SERVER_KEY` profili testowych powstają tu i czyta je tylko ten proces: nigdy nie trafiają na stdout,
do wyjątku ani do dziennika (błędy drukujemy jako nazwę typu, bez treści).

    przygotuj --atrapa URL           profile test-e2e-a/b/j (atrapa modelu z obsługą obrazów, zgody ręczne 20 s, świeży klucz),
                                     wpisy "test": true w agenci.json
    brama-gotowa [--czekaj S]        czy brama obsługuje nowe profile bez restartu (/p/<profil>/v1/capabilities)
    sprzataj                         profile, wpisy w agenci.json, tablica kanbana testu, resztki wątków [E2E],
                                     nagrobki sesji profili testu, dzienniki ich bram, nadzorcy s6 bez katalogu usługi
    stan-db PROFIL SESJA             sesja (pinned, title) i jej wiersze w state.db (tylko do odczytu)
    brama PROFIL METODA SCIEZKA [JSON]  surowe żądanie do bramy profilu (status + JSON odpowiedzi)
    obca-tura PROFIL SESJA TEKST     POST /v1/runs do sesji członka (tura „innego klienta”); wraca po 202
    zapchaj PROFIL N TEKST           N równoległych POST /v1/runs (limit bramy, 429)
    budzenie PROFIL SESJA TYTUL      karta na tablicy testu, subskrypcja sesji członka (wake), karta zakończona
    czekaj-budzenie PROFIL SESJA ZADANIE [--czekaj S]   wiersz „[kanban] Task …” w sesji (tura budzenia ruszyła)
    import SESJA                     §18.2 na tymczasowym rozmowy.db: fiksturka, dwa przebiegi importu
    czytnik PROFIL SESJA             projekcja Hermesa = odczyt zapasowy, state.db bajtowo bez zmian
    meta-obrazy 0|1                  wynik próby obrazów wprost w meta.obrazy_wprost (rozmowy.db)
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("JARVO_E2E_HERMES_HOME", "/opt/data"))
PROFILE = HOME / "profiles"
STAN = HOME / "jarvo" / "state"
AGENCI_JSON = STAN / "agenci.json"
ROZMOWY_DB = STAN / "rozmowy.db"
WTYCZKA = Path(os.environ.get("JARVO_E2E_WTYCZKA", str(HOME / "plugins" / "jarvo-hq" / "dashboard")))
BRAMA = (os.environ.get("JARVO_HQ_API_BASE") or f"http://127.0.0.1:{os.environ.get('API_SERVER_PORT', '8642')}").rstrip("/")
TABLICA = "jarvo-e2e"
TESTOWI = {   # profil → (uchwyt, nazwa, narzędzia api_server)
    "test-e2e-a": ("teste2ea", "Test A", ["terminal"]),
    "test-e2e-b": ("teste2eb", "Test B", ["terminal"]),
    "test-e2e-j": ("teste2ej", "Test J", ["kanban"]),
}


def wypisz(dane) -> None:
    print(json.dumps(dane, ensure_ascii=False))


def hermes(*arg: str, czas: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["hermes", *arg], capture_output=True, text=True, timeout=czas)


def modul(nazwa: str):
    """Moduł wtyczki zainstalowany w kontenerze (ten sam kod, który działa w dashboardzie)."""
    spec = importlib.util.spec_from_file_location(f"e2e_{nazwa}", WTYCZKA / f"{nazwa}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def klucz(profil: str) -> str:
    for linia in (PROFILE / profil / ".env").read_text(encoding="utf-8").splitlines():
        if linia.startswith("API_SERVER_KEY="):
            return linia.split("=", 1)[1].strip()
    return ""


def zadanie(profil: str, metoda: str, sciezka: str, dane=None, *, czas: float = 15) -> tuple[int, object]:
    """Żądanie do bramy z kluczem profilu; (status, JSON albo początek tekstu). Bez nagłówków w wyniku."""
    cialo = json.dumps(dane).encode() if dane is not None else None
    z = urllib.request.Request(f"{BRAMA}/p/{profil}{sciezka}", data=cialo, method=metoda,
                               headers={"Authorization": "Bearer " + klucz(profil),
                                        **({"Content-Type": "application/json"} if cialo is not None else {})})
    try:
        with urllib.request.urlopen(z, timeout=czas) as r:
            status, tekst = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, tekst = e.code, e.read().decode("utf-8", "replace")
    except Exception as e:                       # bez treści wyjątku: mogłaby nieść nagłówek
        return 0, type(e).__name__
    try:
        return status, json.loads(tekst)
    except ValueError:
        return status, tekst[:300]


# ----------------------------------------------------------------------------------------------- profile

def przygotuj(a) -> None:
    import yaml  # noqa: PLC0415 (Python Hermesa)

    for profil, (uchwyt, nazwa, narzedzia) in TESTOWI.items():
        if (PROFILE / profil).exists():
            hermes("profile", "delete", "-y", profil)
        r = hermes("profile", "create", profil, "--no-alias", "--no-skills")
        if r.returncode != 0 or not (PROFILE / profil).is_dir():
            wypisz({"ok": False, "blad": f"hermes profile create {profil}: kod {r.returncode}"})
            sys.exit(1)
        p = PROFILE / profil
        cfg = yaml.safe_load((p / "config.yaml").read_text(encoding="utf-8")) or {}
        # supports_vision: Hermes podaje obrazy modelowi wprost (bez tego opisuje je modelem pomocniczym)
        cfg["model"] = {"provider": "custom", "base_url": a.atrapa, "default": "atrapa", "supports_vision": True}
        cfg["approvals"] = {**(cfg.get("approvals") or {}), "mode": "manual", "timeout": 20}
        cfg["platform_toolsets"] = {**(cfg.get("platform_toolsets") or {}), "api_server": narzedzia}
        (p / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        env = p / ".env"
        linie = [x for x in (env.read_text(encoding="utf-8").splitlines() if env.exists() else [])
                 if not x.startswith("API_SERVER_KEY=")]
        linie.append("API_SERVER_KEY=" + secrets.token_hex(32))
        env.write_text("\n".join(linie) + "\n", encoding="utf-8")
        os.chmod(env, 0o600)
    STAN.mkdir(parents=True, exist_ok=True)
    try:
        dane = json.loads(AGENCI_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dane = {}
    if not isinstance(dane, dict):
        dane = {}
    for profil, (uchwyt, nazwa, _n) in TESTOWI.items():
        dane[profil] = {"handle": uchwyt, "nazwa": nazwa, "test": True}
    tmp = AGENCI_JSON.with_suffix(".e2e.tmp")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(AGENCI_JSON)
    wypisz({"ok": True, "profile": list(TESTOWI), "atrapa": a.atrapa})


def brama_gotowa(a) -> None:
    """Brama mnoży profile per żądanie (profiles_to_serve), więc nowy profil powinien odpowiadać bez restartu.
    Drugie sprawdzenie to baza sesji (`GET /api/sessions`): brama trzyma otwarty state.db profilu przez cały czas
    życia procesu, więc po usunięciu i ponownym założeniu profilu o tej samej nazwie (poprzedni przebieg testu) ma
    w pamięci stary plik i każda tura kończy się „state.db was replaced underneath the gateway” (tu: 500)."""
    out, t0 = {}, time.monotonic()
    for profil in TESTOWI:
        start = time.monotonic()
        status, _d = 0, None
        while time.monotonic() - t0 < a.czekaj:
            status, _d = zadanie(profil, "GET", "/v1/capabilities", czas=5)
            if status == 200:
                break
            time.sleep(0.5)
        baza, _d = zadanie(profil, "GET", "/api/sessions?limit=1", czas=10) if status == 200 else (0, None)
        out[profil] = {"status": status, "ms": int((time.monotonic() - start) * 1000), "baza": baza}
    ok = all(v["status"] == 200 and v["baza"] == 200 for v in out.values())
    wypisz({"ok": ok, "profile": out})
    sys.exit(0 if ok else 1)


def sprzataj(_a) -> None:
    out: dict = {"profile": [], "watki": 0}
    # resztki wątków testu (normalnie usuwa je sam test przez API): koordynator albo członek test-e2e-*
    if ROZMOWY_DB.exists():
        try:
            c = sqlite3.connect(f"file:{ROZMOWY_DB}?mode=ro", uri=True)
            wids = [r[0] for r in c.execute(
                "SELECT id FROM watki WHERE koordynator LIKE 'test-e2e-%' OR id IN "
                "(SELECT watek_id FROM czlonkowie WHERE agent LIKE 'test-e2e-%')")]
            c.close()
            if wids:
                db = modul("rozmowy").Rozmowy(ROZMOWY_DB)
                for w in wids:
                    db.usun(w, trwale=True)
                db.zamknij()
            out["watki"] = len(wids)
        except Exception as e:
            out["watki_blad"] = type(e).__name__
    for profil in TESTOWI:
        if (PROFILE / profil).exists():
            hermes("profile", "delete", "-y", profil)
            out["profile"].append(profil)
    try:
        dane = json.loads(AGENCI_JSON.read_text(encoding="utf-8"))
        if isinstance(dane, dict):
            reszta = {k: v for k, v in dane.items() if k not in TESTOWI}
            if reszta:
                AGENCI_JSON.write_text(json.dumps(reszta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            else:
                AGENCI_JSON.unlink()
    except (OSError, ValueError):
        pass
    r = hermes("kanban", "boards", "list")
    if TABLICA in (r.stdout or ""):
        hermes("kanban", "boards", "rm", "--delete", TABLICA)
        out["tablica"] = TABLICA
    # nagrobki sesji (wiersze `sesje` bez wątku) usuniętych profili testu: nikt ich już nie odepnie
    if ROZMOWY_DB.exists():
        try:
            db = modul("rozmowy").Rozmowy(ROZMOWY_DB)
            out["nagrobki"] = sum(db.usun_nagrobki(profil) for profil in TESTOWI)
            db.zamknij()
        except Exception as e:
            out["nagrobki_blad"] = type(e).__name__
    # dzienniki bram usuniętych profili i nadzorcy s6 po ich katalogach usług (restart bramy w trakcie testu)
    logi = HOME / "logs" / "gateways"
    out["logi"] = 0
    for k in sorted(logi.glob("test-e2e-*")) if logi.is_dir() else []:
        shutil.rmtree(k, ignore_errors=True)
        out["logi"] += 1
    if Path("/command/s6-svscanctl").exists() and Path("/run/service").is_dir():
        try:
            r = subprocess.run(["/command/s6-svscanctl", "-an", "/run/service"], capture_output=True, timeout=10)
            out["s6"] = "ok" if r.returncode == 0 else "brak_uprawnien"
        except (OSError, subprocess.SubprocessError) as e:
            out["s6"] = type(e).__name__
    wypisz(out)


# ----------------------------------------------------------------------------------------------- state.db

def ro(profil: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{PROFILE / profil / 'state.db'}?mode=ro", uri=True, timeout=5)


def stan_db(a) -> None:
    c = ro(a.profil)
    s = c.execute("SELECT id, pinned, title, title_source FROM sessions WHERE id = ?", (a.sesja,)).fetchone()
    m = c.execute("SELECT id, role, content FROM messages WHERE session_id = ? ORDER BY id", (a.sesja,)).fetchall()
    c.close()
    wypisz({"sesja": {"id": s[0], "pinned": s[1], "title": s[2], "title_source": s[3]} if s else None,
            "wiersze": [{"id": i, "rola": r, "tresc": (t or "")[:2000]} for i, r, t in m]})


def czekaj_budzenie(a) -> None:
    """Czeka, aż tura budzenia ruszy: wiersz użytkownika „[kanban] Task <id>” w sesji członka."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < a.czekaj:
        try:
            c = ro(a.profil)
            r = c.execute("SELECT id FROM messages WHERE session_id = ? AND role = 'user' AND content LIKE ? "
                          "ORDER BY id DESC LIMIT 1", (a.sesja, f"[kanban] Task {a.zadanie}%")).fetchone()
            d = c.execute("SELECT holder FROM session_turn_leases WHERE conversation_id = ? AND expires_at > ?",
                          (a.sesja, time.time())).fetchone()
            c.close()
        except sqlite3.Error:
            r = d = None
        if r:
            wypisz({"ok": True, "wiersz": r[0], "dzierzawa": bool(d), "ms": int((time.monotonic() - t0) * 1000)})
            return
        time.sleep(0.1)
    wypisz({"ok": False, "ms": int((time.monotonic() - t0) * 1000)})
    sys.exit(1)


# ----------------------------------------------------------------------------------------------- brama

def brama(a) -> None:
    status, d = zadanie(a.profil, a.metoda.upper(), a.sciezka, json.loads(a.json) if a.json else None)
    wypisz({"status": status, "odp": d})


def obca_tura(a) -> None:
    """Tura „innego klienta” w sesji członka (POST /v1/runs z session_id). Brama odpowiada 202 przed zbudowaniem
    agenta i dzierżawą tury, więc wysyłka aplikacji tuż po tym przechodzi kontrolę dzierżawy, a tura czeka na tę."""
    status, d = zadanie(a.profil, "POST", "/v1/runs", {"input": a.tekst, "session_id": a.sesja})
    wypisz({"ok": status == 202, "status": status,
            "run_id": d.get("run_id") if isinstance(d, dict) else None, "o": time.time()})


def zapchaj(a) -> None:
    """N równoległych przebiegów (każdy we własnej nowej sesji) — zajmują miejsca w limicie bramy. Wraca, gdy
    przyjęte pracują (`running`): brama buduje agentów kilka sekund i w tym czasie nowe żądania czekają, zamiast
    od razu dostać 429."""
    bariera = threading.Barrier(a.n)

    def jeden(i: int):
        bariera.wait()
        return zadanie(a.profil, "POST", "/v1/runs", {"input": f"{a.tekst} #{i}"})

    with concurrent.futures.ThreadPoolExecutor(a.n) as ex:
        wyniki = list(ex.map(jeden, range(a.n)))
    statusy = [s for s, _d in wyniki]
    ids = [d.get("run_id") for s, d in wyniki if s == 202 and isinstance(d, dict)]
    t0, stany = time.monotonic(), []
    while time.monotonic() - t0 < 30:
        stany = []
        for rid in ids:
            _s, d = zadanie(a.profil, "GET", f"/v1/runs/{rid}", czas=5)
            stany.append(d.get("status") if isinstance(d, dict) else None)
        if all(x not in (None, "queued") for x in stany):
            break
        time.sleep(0.5)
    wypisz({"statusy": statusy, "przyjete": statusy.count(202), "odrzucone_429": statusy.count(429), "run_id": ids,
            "pracuja": stany.count("running"), "czekanie_ms": int((time.monotonic() - t0) * 1000)})


# ----------------------------------------------------------------------------------------------- kanban

def budzenie(a) -> None:
    """Karta bez wykonawcy na tablicy testu, subskrypcja sesji członka w trybie `wake`, karta zakończona: notifier
    bramy (co ~5 s) budzi sesję turą „[kanban] Task … completed.”; tytuł z `[wolno:<s>]` wydłuża tę turę."""
    if TABLICA not in (hermes("kanban", "boards", "list").stdout or ""):
        hermes("kanban", "boards", "create", TABLICA, "--name", "Jarvo E2E")
    r = hermes("kanban", "--board", TABLICA, "create", a.tytul, "--created-by", "jarvo-e2e", "--json")
    try:
        zad = json.loads(r.stdout)
        tid = zad.get("id") or zad.get("task_id") or (zad.get("task") or {}).get("id")
    except ValueError:
        tid = None
    if not tid:
        wypisz({"ok": False, "blad": f"kanban create: kod {r.returncode}"})
        sys.exit(1)
    s = hermes("-p", a.profil, "kanban", "--board", TABLICA, "notify-subscribe", "--platform", "api_server",
               "--chat-id", a.sesja, "--delivery-mode", "wake", "--notifier-profile", a.profil, tid)
    k = hermes("kanban", "--board", TABLICA, "complete", tid, "--result", "[E2E] karta zakończona")
    wypisz({"ok": s.returncode == 0 and k.returncode == 0, "zadanie": tid, "subskrypcja": s.returncode,
            "koniec": k.returncode, "o": time.time()})


# ----------------------------------------------------------------------------------------------- import i czytnik

def importuj(a) -> None:
    """§18.2 izolacja testu: tymczasowe rozmowy.db i fiksturka hq-sessions.json; prawdziwe pliki nietknięte."""
    rozmowy = modul("rozmowy")
    katalog = Path(tempfile.mkdtemp(prefix="jarvo-e2e-import-"))
    try:
        plik = katalog / "hq-sessions.json"
        plik.write_text(json.dumps({"test-e2e-a": a.sesja, "test-e2e-b": "None", "jarvo-nieznany": "sesja_x"}),
                        encoding="utf-8")
        db = rozmowy.Rozmowy(katalog / "rozmowy.db")
        db.migruj()
        agenci = {p: n for p, (_u, n, _t) in TESTOWI.items()}
        pierwszy = rozmowy.migruj_hq_sessions(db, plik, PROFILE, agenci=agenci)
        drugi = rozmowy.migruj_hq_sessions(db, plik, PROFILE, agenci=agenci)
        watki, _k = db.lista(filtr="rozmowy", limit=50)
        sesje = db.sesje_watku(watki[0]["id"]) if watki else []
        db.zamknij()
        wypisz({"pierwszy": pierwszy, "drugi": drugi,
                "watki": [{k: w.get(k) for k in ("id", "tytul", "rodzaj", "tytul_zrodlo")} for w in watki],
                "sesje": [{k: s.get(k) for k in ("agent", "sesja_id", "powod")} for s in sesje]})
    finally:
        shutil.rmtree(katalog, ignore_errors=True)


def meta_obrazy(a) -> None:
    """Wynik próby obrazów (spec §10.6: „the result is recorded in meta.obrazy_wprost”) w rozmowy.db."""
    db = modul("rozmowy").Rozmowy(ROZMOWY_DB)
    try:
        przed = db.meta("obrazy_wprost")
        db.ustaw_meta("obrazy_wprost", a.wartosc)
    finally:
        db.zamknij()
    wypisz({"ok": True, "przed": przed, "po": a.wartosc})


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def czytnik(a) -> None:
    """czytnik.porownaj (projekcja Hermesa kontra odczyt zapasowy) plus własny odcisk state.db przed i po
    (sha256 pliku i -wal, mtime): oba odczyty muszą dać to samo, a baza zostać bajtowo ta sama."""
    czyt = modul("czytnik")
    db = PROFILE / a.profil / "state.db"
    przed = {s: _sha(db.with_name(db.name + s)) for s in ("", "-wal")}
    mtime = db.stat().st_mtime_ns
    wynik = czyt.porownaj(db, a.sesja)
    pozycje = czyt.czytaj_zapasowo(db, a.sesja) or []
    po = {s: _sha(db.with_name(db.name + s)) for s in ("", "-wal")}
    wypisz({"rowne": wynik.get("rowne"), "hermes": wynik.get("hermes"), "zapasowo": wynik.get("zapasowo"),
            "blad_hermesa": wynik.get("blad_hermesa"), "roznice": wynik.get("roznice") or [],
            "state_db_bez_zmian": wynik.get("state_db_bez_zmian"), "sha_rowne": przed[""] == po[""],
            "mtime_rowny": mtime == db.stat().st_mtime_ns, "wal_rowny": przed["-wal"] == po["-wal"],
            "rodzaje": sorted({f"{x.get('rodzaj')}/{x.get('rola')}" for x in pozycje if isinstance(x, dict)})})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("przygotuj"); p.add_argument("--atrapa", required=True); p.set_defaults(fn=przygotuj)
    p = sub.add_parser("brama-gotowa"); p.add_argument("--czekaj", type=float, default=20); p.set_defaults(fn=brama_gotowa)
    p = sub.add_parser("sprzataj"); p.set_defaults(fn=sprzataj)
    p = sub.add_parser("stan-db"); p.add_argument("profil"); p.add_argument("sesja"); p.set_defaults(fn=stan_db)
    p = sub.add_parser("brama"); p.add_argument("profil"); p.add_argument("metoda"); p.add_argument("sciezka")
    p.add_argument("json", nargs="?"); p.set_defaults(fn=brama)
    p = sub.add_parser("obca-tura"); p.add_argument("profil"); p.add_argument("sesja"); p.add_argument("tekst")
    p.set_defaults(fn=obca_tura)
    p = sub.add_parser("zapchaj"); p.add_argument("profil"); p.add_argument("n", type=int); p.add_argument("tekst")
    p.set_defaults(fn=zapchaj)
    p = sub.add_parser("budzenie"); p.add_argument("profil"); p.add_argument("sesja"); p.add_argument("tytul")
    p.set_defaults(fn=budzenie)
    p = sub.add_parser("czekaj-budzenie"); p.add_argument("profil"); p.add_argument("sesja"); p.add_argument("zadanie")
    p.add_argument("--czekaj", type=float, default=30); p.set_defaults(fn=czekaj_budzenie)
    p = sub.add_parser("import"); p.add_argument("sesja"); p.set_defaults(fn=importuj)
    p = sub.add_parser("czytnik"); p.add_argument("profil"); p.add_argument("sesja"); p.set_defaults(fn=czytnik)
    p = sub.add_parser("meta-obrazy"); p.add_argument("wartosc", choices=["0", "1"]); p.set_defaults(fn=meta_obrazy)
    a = ap.parse_args(argv)
    for profil in (getattr(a, "profil", None),):
        if profil is not None and profil not in TESTOWI:
            wypisz({"ok": False, "blad": "tylko profile test-e2e-*"})
            sys.exit(2)
    a.fn(a)


if __name__ == "__main__":
    main()
