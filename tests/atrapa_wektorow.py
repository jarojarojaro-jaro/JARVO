"""Atrapa osadzania dla testów skarbca (docs/WIEDZA.md §7): deterministyczne wektory bez modelu i bez numpy.

Wektor tekstu to worek rdzeni słów (4 pierwsze litery bez ogonków) rozrzuconych skrótem po WYMIAR wymiarach,
znormalizowany; SYNONIMY udają „znaczenie” (słowo z pytania trafia w rdzeń słowa z notatki), żeby test pokazał
trafienie, którego BM25 nie ma. Ten sam kod służy w procesie (AtrapaWektorow: interfejs KlientWektorow) i jako koder
prawdziwego serwera HTTP usługi (usluga_atrapy: wiedza/wektory.py SerwerWektorow z tym koderem).
"""
from __future__ import annotations

import array
import contextlib
import hashlib
import importlib.util
import math
import re
import sys
import threading
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL = "atrapa-e5@test"
WYMIAR = 64
SYNONIMY = {"automaty": "spam", "boty": "spam", "botami": "spam", "komorce": "tele", "komorka": "tele"}


def _rdzenie(tekst: str) -> list[str]:
    t = re.sub(r"^(query|passage): ", "", tekst)
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).replace("ł", "l").lower()
    return [SYNONIMY.get(s, s)[:4] for s in re.findall(r"\w+", t) if len(s) >= 3]


def wektor(tekst: str) -> list[float]:
    v = [0.0] * WYMIAR
    for r in _rdzenie(tekst):
        v[int(hashlib.sha256(r.encode("utf-8")).hexdigest(), 16) % WYMIAR] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def koder(teksty: list[str]) -> bytes:
    """Koder dla SerwerWektorow: float32 little-endian, wiersz na tekst."""
    a = array.array("f", [x for t in teksty for x in wektor(t)])
    if sys.byteorder == "big":
        a.byteswap()
    return a.tobytes()


class AtrapaWektorow:
    """Interfejs wiedza.KlientWektorow (`model`, `osadz`) w procesie; `padnij` = usługa nie odpowiada (None),
    `padnij_po` = tyle udanych wywołań, potem None; `wywolania` = listy tekstów z każdego wywołania."""

    def __init__(self, model: str = MODEL, padnij: bool = False, padnij_po: int | None = None):
        self.model, self.padnij, self.padnij_po = model, padnij, padnij_po
        self.wywolania: list[list[str]] = []

    def osadz(self, teksty: list[str], czas_s: float | None = None):
        if self.padnij or (self.padnij_po is not None and len(self.wywolania) >= self.padnij_po):
            return None
        self.wywolania.append(list(teksty))
        return [array.array("f", wektor(t)) for t in teksty]


def modul_wektorow():
    """wiedza/wektory.py (sama biblioteka standardowa na poziomie modułu; numpy tylko w ModelE5)."""
    mod = sys.modules.get("jarvo_wiedza_wektory")
    if mod is None:
        spec = importlib.util.spec_from_file_location("jarvo_wiedza_wektory", REPO / "wiedza" / "wektory.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["jarvo_wiedza_wektory"] = mod
        spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def usluga_atrapy(stan: Path, koder_=koder, model: str = MODEL):
    """Prawdziwy serwer usługi wektorów (HTTP na 127.0.0.1, token w <stan>/wektory.json) z atrapą zamiast modelu."""
    serwer = modul_wektorow().SerwerWektorow(koder_, model, WYMIAR, stan, log=lambda _s: None)
    watek = threading.Thread(target=serwer.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    watek.start()
    try:
        yield serwer
    finally:
        serwer.shutdown()
        watek.join(5)
        serwer.zamknij()


def wolny_koder(opoznienie_s: float):
    def k(teksty: list[str]) -> bytes:
        time.sleep(opoznienie_s)
        return koder(teksty)
    return k
