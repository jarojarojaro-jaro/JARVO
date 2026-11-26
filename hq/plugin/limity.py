"""Limity planów modeli (Claude, Command Code…) w pasku panelu (docs/HQ.md „Limity planów”).

Źródła, każde konto raz:
- **flota**: konto dostawcy, na którym pracuje Jarvo (`model.provider` w config.yaml profilu jarvo). Command Code
  (`commandcode`, `commandcode-anthropic`): klucz `COMMANDCODE_API_KEY` ze środowiska albo `.env` profilu (wartość
  zostaje w procesie), `GET /alpha/billing/credits` (okna 5 h i tygodnia: used, cap, resetAt) i
  `/alpha/billing/subscriptions` (planId, np. individual-goat → GOAT);
- **omp**: `omp usage --json` (konta zalogowane w omp na tym komputerze, np. subskrypcja Claude; omp sam trzyma
  poświadczenia). Okna wspólne całego konta: `window.id` 5h i 7d, bez okien jednego modelu (`scope.tier`).
  Dostawca, którego konto podaje flota, z omp odpada (flota pokazuje konto, na którym naprawdę pracuje).
Błąd źródła = brak jego kont; bez żadnego konta pasek nie pokazuje sekcji. Wynik w pamięci przez CZAS_S, więc karta
odpytuje często, a dostawcy dostają najwyżej jedno zapytanie na CZAS_S.

Trasa: `GET /limity` (tylko z karty panelu: `Sec-Fetch-Site` same-origin/none) → {dostawcy: [{id, nazwa, plan,
okna: [{id, procent, reset}]}], czas}. Testy: tests/test_limity_planow.py.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

CZAS_S = 300.0                      # świeżość odpowiedzi omp
LIMIT_S = 45.0                      # najdłuższe czekanie na `omp usage`
OKNA = ("5h", "7d")                 # okna konta w kolejności pokazywania
NAZWY = {"anthropic": "Claude", "commandcode": "Command Code", "openai-codex": "ChatGPT", "google-antigravity": "Antigravity"}
ODCZYT_ZRODLA = frozenset({"same-origin", "none"})
CC_API = "https://api.commandcode.ai"
CC_DOSTAWCY = ("commandcode", "commandcode-anthropic")
CC_OKNA = (("fiveHour", "5h"), ("weekly", "7d"))
SIEC_S = 20.0


def program_omp() -> str | None:
    """omp z JARVO_OMP, z PATH albo z ~/.local/bin (usługa dashboardu ma krótszy PATH niż terminal)."""
    zapas = Path.home() / ".local" / "bin" / "omp"
    return os.environ.get("JARVO_OMP") or shutil.which("omp") or (str(zapas) if zapas.is_file() else None)


def _procent(amount: dict) -> float | None:
    frakcja = amount.get("usedFraction")
    if isinstance(frakcja, (int, float)):
        return round(max(0.0, min(1.0, float(frakcja))) * 100, 1)
    uzyte, limit = amount.get("used"), amount.get("limit")
    if isinstance(uzyte, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
        return round(max(0.0, min(1.0, uzyte / limit)) * 100, 1)
    return None


def z_raportow(dane: dict) -> list[dict]:
    """Raporty `omp usage --json` → dostawcy z oknami 5 h i tygodnia; dostawca bez żadnego z nich odpada."""
    dostawcy = []
    for raport in (dane or {}).get("reports") or []:
        if not isinstance(raport, dict):
            continue
        okna = {}
        for lim in raport.get("limits") or []:
            okno = (lim.get("window") or {}) if isinstance(lim, dict) else {}
            zakres = lim.get("scope") or {}
            if okno.get("id") not in OKNA or zakres.get("tier") or okno["id"] in okna:
                continue
            procent = _procent(lim.get("amount") or {})
            if procent is None:
                continue
            reset = okno.get("resetsAt")
            okna[okno["id"]] = {"id": okno["id"], "procent": procent,
                                "reset": reset / 1000 if isinstance(reset, (int, float)) else None}
        if not okna:
            continue
        pid = str(raport.get("provider") or "")
        plan = (raport.get("metadata") or {}).get("subscriptionPlan")
        dostawcy.append({"id": pid, "nazwa": NAZWY.get(pid, pid), "plan": plan if isinstance(plan, str) else None,
                         "okna": [okna[i] for i in OKNA if i in okna]})
    return dostawcy


def wartosc_zmiennej(profil: Path, nazwa: str) -> str | None:
    """Wartość zmiennej ze środowiska albo z `.env` profilu (tylko dla zapytania do dostawcy, nigdzie nie wychodzi)."""
    if (os.environ.get(nazwa) or "").strip():
        return os.environ[nazwa].strip()
    try:
        linie = (Path(profil) / ".env").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for linia in linie:
        m = re.match(rf"\s*(?:export\s+)?{re.escape(nazwa)}\s*=\s*(.*)$", linia)
        if m and m.group(1).strip().strip("'\"").strip():
            return m.group(1).strip().strip("'\"").strip()
    return None


def _cc_get(sciezka: str, klucz: str) -> dict:
    req = urllib.request.Request(CC_API + sciezka, headers={"Authorization": f"Bearer {klucz}", "Accept": "application/json",
                                                            "User-Agent": "jarvo-hq/limity"})
    with urllib.request.urlopen(req, timeout=SIEC_S) as odp:
        return json.load(odp)


def z_commandcode(kredyty: dict, subskrypcja: dict | None) -> dict | None:
    """Odpowiedzi Command Code → dostawca z oknami 5 h i tygodnia (used / cap); bez okien = None."""
    okna = []
    for klucz, oid in CC_OKNA:
        o = ((kredyty or {}).get("windowLimits") or {}).get(klucz) or {}
        procent = _procent({"used": o.get("used"), "limit": o.get("cap")})
        if procent is not None:
            reset = o.get("resetAt")
            okna.append({"id": oid, "procent": procent, "reset": reset / 1000 if isinstance(reset, (int, float)) else None})
    if not okna:
        return None
    plan = str(((subskrypcja or {}).get("data") or {}).get("planId") or "")
    return {"id": "commandcode", "nazwa": NAZWY["commandcode"], "plan": plan.rsplit("-", 1)[-1].upper() or None, "okna": okna}


def z_floty(profil: Path, dostawca: Callable[[Path], tuple]) -> list[dict]:
    """Konto dostawcy, na którym pracuje Jarvo (dziś: Command Code); inny dostawca albo błąd = pusta lista."""
    if dostawca(profil)[0] not in CC_DOSTAWCY:
        return []
    klucz = wartosc_zmiennej(profil, "COMMANDCODE_API_KEY")
    if not klucz:
        return []
    try:
        kredyty = _cc_get("/alpha/billing/credits", klucz)
    except (OSError, ValueError):
        return []
    try:
        subskrypcja = _cc_get("/alpha/billing/subscriptions", klucz)
    except (OSError, ValueError):
        subskrypcja = None
    cc = z_commandcode(kredyty, subskrypcja)
    return [cc] if cc else []


class Limity:
    """Ostatnia odpowiedź źródeł w pamięci; jedno odpytanie naraz (równoległe karty czekają na ten sam wynik)."""

    def __init__(self, program: Callable[[], str | None] = program_omp, czas_s: float = CZAS_S,
                 flota: Callable[[], list[dict]] | None = None):
        self.program, self.czas_s, self.flota = program, czas_s, flota
        self._lock = threading.Lock()
        self._wynik: dict | None = None
        self._kiedy = 0.0

    def _omp(self) -> list[dict]:
        omp = self.program()
        if not omp:
            return []
        try:
            p = subprocess.run([omp, "usage", "--json"], capture_output=True, timeout=LIMIT_S, check=False,
                               stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return z_raportow(json.loads(p.stdout or b"{}")) if p.returncode == 0 else []
        except (OSError, subprocess.SubprocessError, ValueError):
            return []

    def _zapytaj(self) -> list[dict]:
        try:
            flota = self.flota() if self.flota else []
        except Exception:                     # noqa: BLE001 - źródło pomocnicze: błąd = brak jego kont
            flota = []
        ids = {d["id"] for d in flota}
        return flota + [d for d in self._omp() if d["id"] not in ids]

    def pobierz(self) -> dict:
        with self._lock:
            teraz = time.time()
            if self._wynik is None or teraz - self._kiedy >= self.czas_s:
                self._wynik = {"dostawcy": self._zapytaj(), "czas": teraz}
                self._kiedy = teraz
            return self._wynik


def dolacz(router, *, limity: Limity, log: Callable[[str], None] | None = None) -> None:
    """Trasa `GET /limity` na routerze wtyczki."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    log = log or (lambda _m: None)

    @router.get("/limity")
    async def limity_planow(request: Request):
        skad = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if skad and skad not in ODCZYT_ZRODLA:
            log(f"jarvo-hq: odczyt odrzucony GET /limity (sec-fetch-site={skad[:20]})")
            return JSONResponse({"blad": {"kod": "csrf", "komunikat": "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                                          "komunikat_en": "Read refused: the request did not come from the Jarvo dashboard."}},
                                status_code=403)
        return await asyncio.to_thread(limity.pobierz)
