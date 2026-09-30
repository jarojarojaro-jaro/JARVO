"""Zakładka „Wiedza” w dashboardzie Hermesa: logika bez FastAPI (testowana w tests/test_wiedza_panel.py).

Czyta skarbiec przez wiedza.py (indeks FTS5, notatki, linki, lint, graf, LOG). Zapisuje tylko: orzeczenia (formularz),
uwagi do notatek (szkic w skrzynce), a kompilację i reindeks uruchamia jako osobne procesy/wywołania. Ścieżki notatek
przechodzą przez Skarbiec.plik() (nic spoza skarbca).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).resolve().parent
LOG_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] (\w+) \| (.*)$")


def _lib():
    mod = sys.modules.get("jarvo_wiedza_lib")
    if mod is not None:
        return mod
    for kandydat in (_HERE / "wiedza.py", _HERE.parent / "wiedza.py", _HERE.parent.parent / "wiedza.py"):
        if kandydat.exists():
            spec = importlib.util.spec_from_file_location("jarvo_wiedza_lib", kandydat)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["jarvo_wiedza_lib"] = mod
            spec.loader.exec_module(mod)
            return mod
    raise ImportError("jarvo-wiedza: brak wiedza.py")


def korzen_danych(hermes_home: str) -> Path:
    h = Path(hermes_home)
    return h.parent.parent if h.parent.name == "profiles" else h


class Panel:
    def __init__(self, skarbiec: str | Path, stan: str | Path, repo: str | Path = "/opt/jarvo/repo", profil_kompilacji: str = "jarvo"):
        self.lib = _lib()
        self.sk = self.lib.Skarbiec(skarbiec, stan)
        self.repo = Path(repo)
        self.profil = profil_kompilacji
        self._lint_cache: tuple[float, dict] = (0.0, {})
        self._kompilacja: Dict[str, Any] = {"trwa": False, "start": 0.0, "koniec": 0.0, "wynik": None, "blad": ""}
        self._lock = threading.Lock()

    # ---- pomocnicze
    def _ix(self):
        ix = self.lib.Indeks(self.sk)
        ix.odswiez()
        return ix

    def _ostatnia_kompilacja(self) -> dict:
        try:
            return json.loads((self.sk.stan / "wiedza-kompilacja.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _log_wpisy(self, n: int = 30) -> List[dict]:
        p = self.sk.root / "LOG.md"
        if not p.exists():
            return []
        wpisy: List[dict] = []
        for linia in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LOG_RE.match(linia)
            if m:
                wpisy.append({"data": m.group(1), "rodzaj": m.group(2), "tresc": m.group(3), "szczegoly": []})
            elif wpisy and linia.startswith("- "):
                wpisy[-1]["szczegoly"].append(linia[2:])
        return wpisy[-n:][::-1]

    # ---- odczyt
    def overview(self) -> dict:
        ix = self._ix()
        try:
            wg: Dict[str, int] = {}
            statusy: Dict[str, int] = {}
            for r in ix.notatki():
                if r["sciezka"].startswith(self.lib.POZA_WYSZUKIWANIEM):
                    continue
                wg[r["folder"] or "/"] = wg.get(r["folder"] or "/", 0) + 1
                if r["status"]:
                    statusy[r["status"]] = statusy.get(r["status"], 0) + 1
            linki = ix.db.execute("SELECT COUNT(*) FROM linki WHERE rozwiazany = 1").fetchone()[0]
        finally:
            ix.zamknij()
        szkice = len(list((self.sk.root / "skrzynka").glob("*.md"))) if (self.sk.root / "skrzynka").is_dir() else 0
        lint = self.lint()
        komp = self._ostatnia_kompilacja()
        return {"skarbiec": str(self.sk.root), "notatek": sum(wg.values()), "wg_folderu": wg, "statusy": statusy, "linki": linki,
                "szkice": szkice, "lint": {"bledy": len(lint.get("bledy") or []), "ostrzezenia": len(lint.get("ostrzezenia") or []),
                                           "informacje": len(lint.get("informacje") or [])},
                "kompilacja": {"ostatnia": komp.get("ostatnia") or 0, "data": komp.get("data") or "", "raport": komp.get("raport") or {},
                               "trwa": self._kompilacja["trwa"]},
                "git": (self.sk.root / ".git").exists(), "dziennik": self._log_wpisy(8)}

    def tree(self) -> dict:
        ix = self._ix()
        try:
            wiersze = ix.notatki()
        finally:
            ix.zamknij()
        foldery: Dict[str, dict] = {}
        for r in wiersze:
            folder = r["folder"] or ""
            if folder in ("zrodla", "skrzynka"):
                continue
            f = foldery.setdefault(folder, {"folder": folder, "nazwa": self.lib.HUBY.get(folder, (None, folder or "Skarbiec"))[1], "hub": None, "notatki": []})
            wpis = {"sciezka": r["sciezka"], "tytul": r["tytul"], "typ": r["typ"], "status": r["status"], "zmieniono": r["zmieniono"],
                    "agent": r["agent"], "hub": bool(r["hub"]), "streszczenie": (r["streszczenie"] or "")[:160]}
            if r["hub"] and r["sciezka"].count("/") <= 1:
                f["hub"] = wpis
            else:
                f["notatki"].append(wpis)
        kolejnosc = [""] + [k for k in self.lib.HUBY if k] + sorted(k for k in foldery if k and k not in self.lib.HUBY)
        return {"foldery": [foldery[k] for k in kolejnosc if k in foldery]}

    def note(self, sciezka: str) -> dict:
        n = self.sk.wczytaj(sciezka)
        ix = self._ix()
        try:
            we = [dict(r) for r in ix.db.execute("SELECT l.z, p.tytul, l.auto FROM linki l JOIN pliki p ON p.sciezka = l.z WHERE l.do_ = ? AND l.rozwiazany = 1 ORDER BY l.auto, l.z", (n.sciezka,))]
            tytuly = {r["sciezka"]: r["tytul"] for r in ix.notatki()}
        finally:
            ix.zamknij()
        wy = []
        for cel, etykieta, auto in n.linki:
            r = self.sk.rozwiaz(cel)
            wy.append({"cel": r or cel, "etykieta": etykieta, "istnieje": r is not None, "auto": auto, "tytul": tytuly.get(r or "", "")})
        zrodlo = str(n.fm.get("zrodlo") or "")
        zrodla = [{"tekst": z.strip(), "sciezka": z.strip() if self.sk.istnieje(z.strip()) else None} for z in zrodlo.split(";") if z.strip()]
        return {"sciezka": n.sciezka, "tytul": n.tytul, "streszczenie": n.streszczenie, "frontmatter": n.fm, "tresc": n.tresc,
                "slowa": n.slowa, "hub": n.hub, "folder": n.folder, "linki_wy": wy,
                "linki_we": [{"z": r["z"], "tytul": r["tytul"], "auto": bool(r["auto"])} for r in we],
                "zrodla": zrodla, "historia": self.historia(n.sciezka)}

    def historia(self, sciezka: str, n: int = 8) -> List[dict]:
        if not (self.sk.root / ".git").exists():
            return []
        r = self.sk.git("log", f"-{n}", "--format=%h%x09%ad%x09%s", "--date=short", "--", f"{sciezka}.md")
        if r is None or r.returncode != 0:
            return []
        out = []
        for linia in r.stdout.splitlines():
            czesci = linia.split("\t", 2)
            if len(czesci) == 3:
                out.append({"rev": czesci[0], "data": czesci[1], "opis": czesci[2]})
        return out

    def graph(self) -> dict:
        ix = self._ix()
        try:
            return ix.graf()
        finally:
            ix.zamknij()

    def search(self, q: str, folder: Optional[str] = None, limit: int = 12) -> List[dict]:
        ix = self._ix()
        try:
            return ix.szukaj(q[:300], limit=max(1, min(limit, 30)), folder=folder or None)
        finally:
            ix.zamknij()

    def inbox(self) -> dict:
        kat = self.sk.root / "skrzynka"
        szkice = []
        if kat.is_dir():
            for p in sorted(kat.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
                fm, body = self.lib.podziel(p.read_text(encoding="utf-8", errors="replace"))
                szkice.append({"plik": p.name, "tytul": str(fm.get("tytul") or p.stem), "typ": str(fm.get("typ") or ""), "agent": str(fm.get("agent") or ""),
                               "zrodlo": str(fm.get("zrodlo") or ""), "skad": str(fm.get("skad") or ""), "proby": int(fm.get("proby") or 0),
                               "mtime": p.stat().st_mtime, "podglad": re.sub(r"^# .*\n", "", body, count=1).strip()[:400]})
        zrobione = len(list((kat / "zrobione").glob("*.md"))) if (kat / "zrobione").is_dir() else 0
        return {"szkice": szkice, "zrobione": zrobione, "kompilacja": {**self._ostatnia_kompilacja(), "trwa": self._kompilacja["trwa"],
                                                                      "blad": self._kompilacja["blad"], "start": self._kompilacja["start"]}}

    def log(self, n: int = 40) -> List[dict]:
        return self._log_wpisy(n)

    def lint(self, odswiez: bool = False) -> dict:
        ts, cache = self._lint_cache
        if cache and not odswiez and time.time() - ts < 60:
            return cache
        ix = self.lib.Indeks(self.sk)
        try:
            raport = self.lib.lint(self.sk, ix)
        finally:
            ix.zamknij()
        self._lint_cache = (time.time(), raport)
        return raport

    def rulings(self) -> List[dict]:
        kat = self.sk.root / "orzeczenia"
        out = []
        if not kat.is_dir():
            return out
        for p in sorted(kat.rglob("*.md")):
            rel = self.sk.rel(p)
            if p.name.startswith("_hub-"):
                continue
            n = self.sk.wczytaj(rel)
            linie = [l[2:] for l in n.tresc.splitlines() if l.startswith("- ") and " · [" in l]
            out.append({"sciezka": rel, "tytul": n.tytul, "kogo": p.stem if p.parent.name != "marki" else f"marki/{p.stem}",
                        "linie": linie[::-1], "zmieniono": str(n.fm.get("zmieniono") or "")})
        return out

    # ---- zapis (tylko orzeczenia i uwagi)
    def add_ruling(self, kogo: str, tresc: str, zrodlo: str = "") -> dict:
        kogo = re.sub(r"[^\w/ -]", "", str(kogo or "wszyscy").strip().lower())[:60] or "wszyscy"
        linia = self.lib.dodaj_orzeczenie(self.sk, kogo, str(tresc or ""), " ".join(str(zrodlo or "człowiek, zakładka Wiedza").split())[:120])
        self._lint_cache = (0.0, {})
        return {"orzeczenie": linia}

    def add_remark(self, sciezka: str, uwaga: str) -> dict:
        n = self.sk.wczytaj(sciezka)
        uwaga = " ".join(str(uwaga or "").split())[:2000]
        if len(uwaga) < 5:
            raise ValueError("uwaga jest za krótka")
        typ = n.typ if n.typ in self.lib.TYPY - {"hub", "orzeczenia", "zrodlo"} else "fakt"
        rel = self.lib.zapisz_szkic(self.sk, typ, f"Poprawka: {n.tytul}"[:70], f"{uwaga}\n\nDotyczy notatki [[{n.sciezka}]].",
                                    f"człowiek, zakładka Wiedza ({self.lib.dzis()})", "czlowiek", ["uwaga"], skad="zakładka Wiedza")
        return {"szkic": rel}

    def reindex(self) -> dict:
        ix = self.lib.Indeks(self.sk)
        try:
            r = ix.odswiez(pelny=True)
            n = self.lib.zbuduj_index(self.sk, ix)
            h = self.lib.odswiez_listy_hubow(self.sk, ix)
            ix.odswiez()
        finally:
            ix.zamknij()
        self._lint_cache = (0.0, {})
        return {**r, "index": n, "huby": h}

    # ---- kompilacja jako osobny proces (model z profilu `jarvo`: scripts/wiedza-kompiluj.sh)
    def compile_command(self) -> Optional[List[str]]:
        skrypt = self.repo / "scripts" / "wiedza-kompiluj.sh"
        if skrypt.exists():
            return ["bash", str(skrypt), "--json"]
        return None

    def compile_start(self) -> dict:
        with self._lock:
            if self._kompilacja["trwa"]:
                return {"trwa": True, "start": self._kompilacja["start"]}
            cmd = self.compile_command()
            if not cmd:
                return {"trwa": False, "blad": "brak scripts/wiedza-kompiluj.sh (repo poza kontenerem?)"}
            self._kompilacja.update({"trwa": True, "start": time.time(), "koniec": 0.0, "wynik": None, "blad": ""})
            threading.Thread(target=self._compile_run, args=(cmd,), name="jarvo-wiedza-kompilacja", daemon=True).start()
            return {"trwa": True, "start": self._kompilacja["start"]}

    def _compile_run(self, cmd: List[str]) -> None:
        try:
            env = {**os.environ, "JARVO_WIEDZA_PROFIL": self.profil}
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
            wynik = None
            try:
                wynik = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else None
            except (ValueError, IndexError):
                wynik = None
            blad = "" if r.returncode == 0 else (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else f"kod {r.returncode}")
            self._kompilacja.update({"wynik": wynik, "blad": blad[:300]})
        except Exception as e:
            self._kompilacja.update({"blad": str(e)[:300]})
        finally:
            self._kompilacja.update({"trwa": False, "koniec": time.time()})
            self._lint_cache = (0.0, {})

    def compile_status(self) -> dict:
        return {**self._kompilacja, "ostatnia": self._ostatnia_kompilacja()}
