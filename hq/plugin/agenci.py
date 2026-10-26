"""Lista agentów aplikacji Jarvo: flota z fleet.json wtyczki (generowany z fleet.yaml przez hqbuild) i, tylko przy
`JARVO_E2E=1`, agenci testowi z /opt/data/jarvo/state/agenci.json (wpisy `"test": true`, profile `test-e2e-*`
zakładane i sprzątane przez test E2E). Własni agenci właściciela (`agenci.json` bez `test`) przyjdą w etapie 8;
do tego czasu takie wpisy są pomijane.

Z listy korzystają: mapa aliasów wzmianek (`wzmianki.mapa_aliasow`), nazwy wyświetlane (blok kontekstu, tytuły),
sprawdzenie nazwy profilu przed zbudowaniem ścieżki (czytnik, ochrona) i `GET /agenci`. Plik czytany z pamięcią po
mtime. Czysty Python; testy: tests/test_agenci.py.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable

_H = Path(os.environ.get("HERMES_HOME", "/opt/data"))
HOME = _H.parent.parent if _H.parent.name == "profiles" else _H
JARVO_DIR = Path(os.environ.get("JARVO_DATA_DIR", str(HOME / "jarvo")))
AGENCI_JSON = JARVO_DIR / "state" / "agenci.json"
FLEET_JSON = Path(__file__).with_name("fleet.json")
PROFIL_RE = re.compile(r"^[a-z0-9-]+$")
UCHWYT_RE = re.compile(r"^[a-z][a-z0-9]{1,15}$")
TEST_RE = re.compile(r"^test-e2e-[a-z0-9]{1,12}$")       # tylko takie profile mogą być agentami testowymi
POKOJE = {"bridge", "study", "devlab", "atelier", "filmstudio", "workshop", "office", "radar", "apps", "control"}   # = fleetlib.HQ_ROOMS


def e2e() -> bool:
    return os.environ.get("JARVO_E2E") == "1"


def _czytaj(sciezka: Path) -> object:
    try:
        return json.loads(Path(sciezka).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def z_floty(dane: object) -> list[dict]:
    """Agenci floty w kształcie aplikacji (Agent, docs/HQ.md „Rozmowy”); kolejność jak we fleet.yaml."""
    out = []
    for a in (dane or {}).get("agents", []) if isinstance(dane, dict) else []:
        if not isinstance(a, dict) or not a.get("name"):
            continue
        en = a.get("en") or {}
        out.append({
            "name": a["name"], "handle": a.get("handle") or "", "aliasy": list(a.get("aliasy") or []),
            "nazwa": a.get("short") or a.get("title") or a["name"], "nazwa_en": en.get("title") or a.get("short") or "",
            "emoji": a.get("emoji") or "", "rodzaj": a.get("kind") or "", "opis": a.get("description") or "",
            "opis_en": en.get("description") or "", "rola": a.get("rola") or "", "rola_en": en.get("rola") or "",
            "pokoj": a.get("room") or "", "model": a.get("model") or "", "autonomia": a.get("autonomy_max") or "",
            "temat_tg": a.get("telegram_topic"), "wlasny": False, "test": False, "stan": "aktywny",
        })
    return out


def testowi(dane: object, zajete: set[str]) -> list[dict]:
    """Wpisy `"test": true` z agenci.json (klucz = nazwa profilu `test-e2e-*`); uchwyt zajęty przez flotę albo
    alias innego agenta odpada (mapa wzmianek ma zostać jednoznaczna)."""
    out = []
    if not isinstance(dane, dict):
        return out
    for nazwa_profilu, w in sorted(dane.items()):
        if not isinstance(w, dict) or w.get("test") is not True or not TEST_RE.fullmatch(str(nazwa_profilu)):
            continue
        uchwyt = str(w.get("handle") or "")
        if not UCHWYT_RE.fullmatch(uchwyt) or uchwyt in zajete or nazwa_profilu in zajete:
            continue
        zajete.update({uchwyt, nazwa_profilu})
        out.append({
            "name": nazwa_profilu, "handle": uchwyt, "aliasy": [uchwyt, nazwa_profilu],
            "nazwa": str(w.get("nazwa") or nazwa_profilu), "nazwa_en": str(w.get("nazwa") or nazwa_profilu),
            "emoji": "🧪", "rodzaj": "test", "opis": str(w.get("opis") or "Agent testowy E2E"), "opis_en": "E2E test agent",
            "rola": str(w.get("rola") or "")[:80], "rola_en": "",
            "pokoj": str(w.get("pokoj")) if w.get("pokoj") in POKOJE else "",
            "model": "", "autonomia": "", "temat_tg": None, "wlasny": False, "test": True, "stan": "aktywny",
        })
    return out


class Agenci:
    """Lista agentów z pamięcią po mtime obu plików. `e2e` domyślnie z env `JARVO_E2E`."""

    def __init__(self, fleet_json: Path | str = FLEET_JSON, agenci_json: Path | str = AGENCI_JSON, *,
                 e2e: Callable[[], bool] = e2e):
        self.fleet_json = Path(fleet_json)
        self.agenci_json = Path(agenci_json)
        self.e2e = e2e
        self._klucz: tuple | None = None
        self._lista: list[dict] = []

    def _mtime(self, p: Path) -> float:
        try:
            return p.stat().st_mtime_ns
        except OSError:
            return -1

    def lista(self) -> list[dict]:
        """Flota, a z `JARVO_E2E=1` także agenci testowi."""
        tryb = self.e2e()
        klucz = (self._mtime(self.fleet_json), self._mtime(self.agenci_json) if tryb else None, tryb)
        if klucz != self._klucz:
            flota = z_floty(_czytaj(self.fleet_json))
            zajete = {x for a in flota for x in (a["name"], a["handle"], *a["aliasy"]) if x}
            self._lista = flota + (testowi(_czytaj(self.agenci_json), zajete) if tryb else [])
            self._klucz = klucz
        return [dict(a) for a in self._lista]

    def nazwy(self) -> list[str]:
        return [a["name"] for a in self.lista()]

    def agent(self, nazwa: str) -> dict | None:
        return next((a for a in self.lista() if a["name"] == nazwa), None)

    def profil(self, nazwa: str) -> str:
        """Nazwa profilu sprawdzona przed zbudowaniem ścieżki (`^[a-z0-9-]+$` i na liście), inaczej ValueError."""
        if not PROFIL_RE.fullmatch(str(nazwa or "")) or self.agent(nazwa) is None:
            raise ValueError(f"nieznany agent {nazwa!r}")
        return nazwa

    def recenzent(self) -> str:
        """Recenzent kart floty (fleet.json `reviewer`, bez niego koordynator `orchestrator`, w ostateczności jarvo)."""
        d = _czytaj(self.fleet_json)
        d = d if isinstance(d, dict) else {}
        r = d.get("reviewer") or d.get("orchestrator") or "jarvo"
        return r if isinstance(r, str) and PROFIL_RE.fullmatch(r) else "jarvo"

    def nazwy_wyswietlane(self) -> dict[str, str]:
        return {a["name"]: a["nazwa"] for a in self.lista()}

    def moze_koordynowac(self, nazwa: str) -> bool:
        """Koordynator wątku: `jarvo` zawsze, agent testowy tylko w trybie E2E (wątki `[E2E]`)."""
        if nazwa == "jarvo":
            return True
        a = self.agent(nazwa)
        return bool(a and a["test"] and self.e2e())
