"""Manifest narzędzi z sumami (vendor/natywne.lock.json, generowany z vendor/natywne.yaml przez scripts/natywne.py).

Instalator czyta go samą biblioteką standardową. Wpis platformy to plik do pobrania (url, sha256, rozmiar, format,
opcjonalnie usun_poziom, nazwa_pliku, usun, zmien_nazwe, bin, env: wszystko to wykonuje jarvo/pobieracz.py) albo
`brak` z powodem: wtedy narzędzia na tym systemie nie ma i `jarvo doctor` mówi to wprost. Sekcja `venvy` mówi,
z którego locka w infra/python/ i na którym Pythonie z sekcji narzedzia zbudować venv (c3, krok 6).
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


def modele(app: Path) -> dict:
    """Modele niezależne od platformy: {nazwa: {"rewizja", "katalog", "kiedy", "pliki": [{"cel", "url", "sha256",
    "rozmiar"}]}}."""
    return json.loads((Path(app) / LOCK).read_text(encoding="utf-8")).get("modele") or {}


def venvy(app: Path) -> dict:
    """Venvy Jarva: {nazwa: {"python", "lock", "sha256", "paczek", "kiedy", "bez", "pobranie_mb", opcjonalnie
    "venv_mb", "torch_backend"}}. `lock` to ścieżka od korzenia kodu, `sha256` = suma tego pliku (instalator
    sprawdza ją przed `uv pip install` i bierze 12 znaków do nazwy katalogu venvu); `torch_backend` przekazuje
    jako `uv pip install --torch-backend <wartość>`."""
    return json.loads((Path(app) / LOCK).read_text(encoding="utf-8")).get("venvy") or {}


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
