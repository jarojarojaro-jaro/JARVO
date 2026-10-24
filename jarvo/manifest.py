"""Manifest narzędzi z sumami (vendor/natywne.lock.json, generowany z vendor/natywne.yaml przez scripts/natywne.py).

Instalator czyta go samą biblioteką standardową. Wpis platformy to plik do pobrania (url, sha256, rozmiar, format)
albo `brak` z powodem: wtedy narzędzia na tym systemie nie ma i `jarvo doctor` mówi to wprost.
"""
from __future__ import annotations

import json
from pathlib import Path

LOCK = Path("vendor") / "natywne.lock.json"


class BrakNarzedzia(LookupError):
    """Narzędzia albo pliku dla tej platformy nie ma w manifeście."""


def wczytaj(app: Path) -> dict:
    """Manifest z katalogu kodu Jarva (`app` = korzeń repo albo rozpakowanej wersji)."""
    dane = json.loads((Path(app) / LOCK).read_text(encoding="utf-8"))
    if dane.get("version") != 1:
        raise ValueError("natywne.lock.json: nieznana wersja formatu")
    return dane["narzedzia"]


def hermes(app: Path) -> dict:
    """Przypięcie Hermesa: {"repo", "tag", "commit", "wersja", "dodatki"} (jedno miejsce: vendor/natywne.yaml)."""
    return json.loads((Path(app) / LOCK).read_text(encoding="utf-8"))["hermes"]


def plik(narzedzia: dict, nazwa: str, platforma: str) -> dict:
    """Wpis pliku narzędzia dla platformy; BrakNarzedzia, gdy narzędzia nie ma albo platforma ma `brak`."""
    wpis = narzedzia.get(nazwa)
    if wpis is None:
        raise BrakNarzedzia(f"{nazwa}: nie ma w manifeście")
    p = (wpis.get("pliki") or {}).get(platforma)
    if not p:
        raise BrakNarzedzia(f"{nazwa}: brak pliku dla {platforma}")
    if "brak" in p:
        raise BrakNarzedzia(f"{nazwa} na {platforma}: {p['brak']}")
    return p


def wersja(narzedzia: dict, nazwa: str) -> str:
    return str(narzedzia[nazwa]["wersja"])
