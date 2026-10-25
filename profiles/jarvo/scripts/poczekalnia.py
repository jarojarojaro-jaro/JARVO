#!/usr/bin/env python3
"""Poczekalnia skilli floty (docs/RSI.md §R1): skille, które agenci chcą sobie dopisać albo zmienić, czekają na zgodę
właściciela, zanim trafią do profilu. Bez modelu (0 tokenów).

Specjaliści mają w config.yaml `skills.write_approval: true`: zapis `skill_manage` Hermes odkłada do
`<profil>/pending/skills/<id>.json` zamiast do katalogu skilli. Ten skrypt zbiera poczekalnie wszystkich profili,
skanuje treść tymi samymi wzorcami co skille zewnętrzne (`scripts/skan_skilli.py`: wstrzyknięcia, sekrety,
pobierz-i-uruchom, ukryte znaki, groźny kod) i zatwierdza albo odrzuca wpis po decyzji właściciela.

    python3 poczekalnia.py lista [--json]
    python3 poczekalnia.py zatwierdz <agent> <id> --odcisk <12 znaków z listy>
    python3 poczekalnia.py odrzuc <agent> <id> [--powod "…"]

- Odcisk = SHA-256 agenta, id i treści zmiany. Zgoda dotyczy dokładnie tej wersji: inna treść = inny odcisk = brak zgody.
- Ustalenie skanu `high`/`critical` blokuje zatwierdzenie (wpis do odrzucenia albo do przeglądu w repo).
- `brama_wylaczona`: profil, który sam tworzy skille (`creation_nudge_interval` > 0), a nie ma `write_approval`.
  Wdrożenie przywraca config z repo; do tego czasu zapisy omijają poczekalnię.
- Każda decyzja trafia do `<dane>/jarvo/poczekalnia.jsonl`.
Ostatnia linia wyjścia `lista` to JSON.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sciezki  # noqa: E402  (katalogi z HERMES_HOME, nie z /opt)

BLOKUJE = {"high", "critical"}
POLA_TEKSTU = ("content", "file_content", "new_string")
STARE_DNI = 14


def dane_domyslne() -> Path:
    """`<dane>` = HERMES_HOME Jarva (także z HERMES_HOME profilu); JARVO_DATA_DIR to `<dane>/jarvo` (_sciezki.py)."""
    return _sciezki.dane()


def _skan():
    """`scripts/skan_skilli.py` z repo floty (kontener: /opt/jarvo/repo; repo: trzy katalogi wyżej)."""
    for kandydat in (os.environ.get("JARVO_REPO", "/opt/jarvo/repo"), str(Path(__file__).resolve().parents[3])):
        p = Path(kandydat) / "scripts"
        if (p / "skan_skilli.py").is_file():
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
            import skan_skilli
            return skan_skilli
    return None


def odcisk(agent: str, rekord: dict) -> str:
    tresc = json.dumps({"agent": agent, "id": rekord.get("id"), "payload": rekord.get("payload")},
                       sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(tresc.encode("utf-8")).hexdigest()[:12]


def teksty(payload: dict) -> list[tuple[str, str]]:
    """(plik, tekst) z każdego pola zmiany, które trafi do skilla."""
    nazwa = payload.get("name") or "?"
    plik = payload.get("file_path") or "SKILL.md"
    out = [(f"{nazwa}/{plik}", payload[k]) for k in POLA_TEKSTU if isinstance(payload.get(k), str) and payload[k]]
    for i, op in enumerate(payload.get("operations") or []):
        if isinstance(op, dict):
            out += [(f"{nazwa}/{op.get('file_path') or plik}#op{i + 1}", op[k])
                    for k in POLA_TEKSTU if isinstance(op.get(k), str) and op[k]]
    return out


def skanuj(payload: dict, skan=None) -> list[dict]:
    skan = skan or _skan()
    if skan is None:
        return [{"waga": "high", "regula": "brak-skanera", "opis": "nie znalazłem scripts/skan_skilli.py, nie zatwierdzaj"}]
    out = []
    for rel, tekst in teksty(payload):
        for u in skan.skanuj_tekst(tekst, rel):
            out.append({"waga": u.waga, "regula": u.regula, "plik": u.plik, "linia": u.linia, "opis": u.opis})
    return out


def _yaml(path: Path) -> dict:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def brama(profil: Path) -> dict:
    skills = (_yaml(profil / "config.yaml").get("skills") or {})
    wlaczona = str(skills.get("write_approval", False)).strip().lower() in {"true", "on", "yes", "1", "approve", "enabled"}
    try:
        tworzy = int(skills.get("creation_nudge_interval") or 0) > 0
    except (TypeError, ValueError):
        tworzy = False
    return {"wlaczona": wlaczona, "tworzy": tworzy}


def profile(dane: Path) -> dict[str, Path]:
    d = dane / "profiles"
    return {p.name: p for p in sorted(d.iterdir()) if p.is_dir()} if d.is_dir() else {}


def wpisy(dane: Path, teraz: float | None = None, skan=None) -> list[dict]:
    teraz = teraz or time.time()
    out = []
    for agent, profil in profile(dane).items():
        for plik in sorted((profil / "pending" / "skills").glob("*.json")):
            try:
                r = json.loads(plik.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                out.append({"agent": agent, "id": plik.stem, "blad": "nieczytelny wpis"})
                continue
            p = r.get("payload") or {}
            ustalenia = skanuj(p, skan)
            dni = int((teraz - float(r.get("created_at") or teraz)) // 86400)
            out.append({
                "agent": agent, "id": r.get("id") or plik.stem, "akcja": p.get("action", r.get("action", "")),
                "skill": p.get("name", ""), "plik": p.get("file_path") or "", "opis": r.get("summary", ""),
                "skad": "sam po zadaniu" if r.get("origin") == "background_review" else "w rozmowie",
                "dni": dni, "stary": dni > STARE_DNI, "odcisk": odcisk(agent, r),
                "rozmiar": sum(len(t) for _, t in teksty(p)), "ustalenia": ustalenia,
                "blokuje": any(u["waga"] in BLOKUJE for u in ustalenia),
            })
    return out


def podsumuj(dane: Path | None = None, teraz: float | None = None) -> dict:
    """Dla przeglądu tygodnia (fleet_report.py): wpisy poczekalni i profile z wyłączoną bramą."""
    dane = dane or dane_domyslne()
    w = wpisy(dane, teraz)
    wylaczone = [a for a, p in profile(dane).items() if (b := brama(p))["tworzy"] and not b["wlaczona"]]
    return {"razem": len(w), "blokuje": sum(1 for x in w if x.get("blokuje")), "wpisy": w, "brama_wylaczona": wylaczone}


def _log(dane: Path, wpis: dict) -> None:
    plik = dane / "jarvo" / "poczekalnia.jsonl"
    plik.parent.mkdir(parents=True, exist_ok=True)
    with plik.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"data": dt.datetime.now().isoformat(timespec="seconds"), **wpis}, ensure_ascii=False) + "\n")


def _rekord(dane: Path, agent: str, pid: str) -> tuple[Path, dict]:
    profil = profile(dane).get(agent)
    if profil is None:
        raise SystemExit(f"nie ma profilu {agent}")
    plik = profil / "pending" / "skills" / f"{Path(pid).name}.json"
    try:
        return profil, json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit(f"nie ma wpisu {pid} w poczekalni {agent}")


# Zastosowanie zmiany kodem Hermesa (to samo co `/skills approve <id>` w czacie agenta), w HERMES_HOME profilu.
_ZASTOSUJ = """
import json, sys
from tools import write_approval as wa
from tools.skill_manager_tool import apply_skill_pending
rec = wa.get_pending(wa.SKILLS, sys.argv[1])
if not rec:
    print(json.dumps({"success": False, "error": "wpis zniknął"})); sys.exit(0)
res = json.loads(apply_skill_pending(rec["payload"]))
if res.get("success"):
    wa.discard_pending(wa.SKILLS, rec["id"])
print(json.dumps(res, ensure_ascii=False))
"""


def python_hermesa(src: str) -> str:
    """Python z venvu Hermesa (POSIX: .venv/bin/python, Windows: .venv\\Scripts\\python.exe), inaczej bieżący."""
    for py in (Path(src) / ".venv" / "bin" / "python", Path(src) / ".venv" / "Scripts" / "python.exe"):
        if py.exists():
            return str(py)
    return sys.executable


def zastosuj(profil: Path, pid: str) -> dict:
    src = os.environ.get("HERMES_SRC", "/opt/hermes")
    py = os.environ.get("HERMES_PY") or python_hermesa(src)
    env = {**os.environ, "HERMES_HOME": str(profil), "PYTHONPATH": src}
    r = subprocess.run([py, "-c", _ZASTOSUJ, pid], cwd=src, env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"success": False, "error": (r.stderr or r.stdout).strip()[-300:]}


def zatwierdz(dane: Path, agent: str, pid: str, oczekiwany: str, skan=None, wykonaj=zastosuj) -> dict:
    profil, r = _rekord(dane, agent, pid)
    teraz = odcisk(agent, r)
    if teraz != oczekiwany:
        return {"ok": False, "powod": f"odcisk {teraz} ≠ {oczekiwany}: wpis zmienił się po zgodzie, poproś o nową"}
    ustalenia = skanuj(r.get("payload") or {}, skan)
    if any(u["waga"] in BLOKUJE for u in ustalenia):
        _log(dane, {"agent": agent, "id": pid, "decyzja": "zablokowane", "odcisk": teraz, "ustalenia": ustalenia})
        return {"ok": False, "powod": "skan znalazł ustalenia high/critical: odrzuć wpis", "ustalenia": ustalenia}
    wynik = wykonaj(profil, r["id"])
    ok = bool(wynik.get("success"))
    _log(dane, {"agent": agent, "id": pid, "decyzja": "zatwierdzone" if ok else "błąd", "odcisk": teraz,
                "skill": (r.get("payload") or {}).get("name", ""), "wynik": str(wynik.get("message") or wynik.get("error") or "")[:200]})
    return {"ok": ok, "wynik": wynik}


def odrzuc(dane: Path, agent: str, pid: str, powod: str = "") -> dict:
    profil, r = _rekord(dane, agent, pid)
    (profil / "pending" / "skills" / f"{Path(pid).name}.json").unlink()
    _log(dane, {"agent": agent, "id": pid, "decyzja": "odrzucone", "odcisk": odcisk(agent, r),
                "skill": (r.get("payload") or {}).get("name", ""), "powod": powod[:200]})
    return {"ok": True}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dane", type=Path, default=None, help="katalog danych Hermesa (domyślnie z HERMES_HOME)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("lista")
    l.add_argument("--json", action="store_true")
    z = sub.add_parser("zatwierdz")
    z.add_argument("agent")
    z.add_argument("id")
    z.add_argument("--odcisk", required=True)
    o = sub.add_parser("odrzuc")
    o.add_argument("agent")
    o.add_argument("id")
    o.add_argument("--powod", default="")
    args = ap.parse_args(argv)
    dane = args.dane or dane_domyslne()

    if args.cmd == "lista":
        w = podsumuj(dane)
        if not args.json:
            print(f"Poczekalnia skilli: {w['razem']} (blokuje skan: {w['blokuje']})")
            for x in w["wpisy"]:
                znak = "⛔" if x.get("blokuje") else "·"
                print(f"{znak} {x['agent']} {x['id']} [{x.get('akcja')}] {x.get('skill')}: {x.get('opis', '')[:80]} "
                      f"({x.get('skad')}, {x.get('dni')} dni, odcisk {x.get('odcisk')})")
            for a in w["brama_wylaczona"]:
                print(f"⚠ {a}: brama wyłączona (skills.write_approval), zapisy skilli omijają poczekalnię")
        print(json.dumps(w, ensure_ascii=False))
        return 0
    if args.cmd == "zatwierdz":
        w = zatwierdz(dane, args.agent, args.id, args.odcisk)
    else:
        w = odrzuc(dane, args.agent, args.id, args.powod)
    print(json.dumps(w, ensure_ascii=False))
    return 0 if w["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
