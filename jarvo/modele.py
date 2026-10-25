"""Modele z manifestu do `<dane>/jarvo/models` (docs/NATYWNIE.md: V02, V03, V07, V10, D06, I39; c3 krok 8).

Sekcja `modele` manifestu: pliki niezależne od platformy z przypiętej rewizji repo modelu (adres z commitem, sha256,
rozmiar). Instalator pobiera modele z `kiedy: instalacja` (bez pola: instalacja): lektory Matcha-TTS-PL i Paradee,
Indra OCR, języki Tesseracta i fonty Noto; Parakeet, Silero, MODNet i YuNet przyjdą przy pierwszym użyciu.
Każdy plik przez jarvo/pobieracz.py (suma przed użyciem, pasek, wznawianie). Obok plików `JARVO-ZRODLO.txt` jak
w obrazie (skąd, która rewizja, licencja) i znacznik `.jarvo-model.json` z sumami: drugi przebieg sprawdza same
rozmiary plików, bez liczenia sum i bez sieci.

Wpis `model-<nazwa>` w `<stan>/narzedzia.json` daje procesom Jarva katalog modelu w zmiennej, której szukają skrypty
floty (ZMIENNE: jarvo-tts, ocr.py, Tesseract); pozostałe modele czytają JARVO_MODELS_DIR.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from . import pobieracz, przenosne, srodowisko

ZNACZNIK = ".jarvo-model.json"
ZRODLO = "JARVO-ZRODLO.txt"
# zmienne procesów Jarva z katalogiem modelu (domyślne wartości skryptów to ścieżki obrazu /opt/jarvo/models)
ZMIENNE = {"matcha-pl": "JARVO_TTS_MATCHA_DIR", "paradee": "JARVO_TTS_MODEL_DIR", "indra-ocr": "INDRA_OCR_MODEL_DIR",
           "fonty-noto-sans": "JARVO_FONTY_NOTO_SANS", "fonty-noto-emoji": "JARVO_FONTY_NOTO_EMOJI"}


class BladModelu(RuntimeError):
    """Model się nie pobrał (komunikat po polsku)."""


def do_instalacji(modele: dict) -> list[str]:
    return [n for n, m in modele.items() if isinstance(m, dict) and (m.get("kiedy") or "instalacja") == "instalacja"]


def katalog(katalog_modeli: Path, model: dict) -> Path:
    return Path(katalog_modeli) / str(model["katalog"])


def _opis(nazwa: str, model: dict) -> str:
    return (f"{nazwa}: pliki bez zmian z {model.get('zrodlo', '?')} w rewizji {model.get('rewizja', '?')}.\n"
            f"Licencja: {model.get('licencja', '?')}. Rola: {model.get('rola', '?')}.\n"
            "Pobrane przez instalator Jarva z sumą sha256 każdego pliku (vendor/natywne.yaml, sekcja modele; "
            "przegląd: vendor/zrodla.yaml).\n")


def _znacznik(model: dict) -> dict:
    return {"rewizja": model.get("rewizja"), "pliki": {p["cel"]: [p["sha256"], p.get("rozmiar")]
                                                       for p in model.get("pliki") or []}}


def gotowy(kat: Path, model: dict) -> bool:
    """Znacznik z tymi samymi sumami i pliki o rozmiarach z manifestu (bez liczenia sum)."""
    if srodowisko.wczytaj_json(Path(kat) / ZNACZNIK) != json.loads(json.dumps(_znacznik(model))):
        return False
    for p in model.get("pliki") or []:
        plik = Path(kat) / p["cel"]
        try:
            if not plik.is_file() or (p.get("rozmiar") and plik.stat().st_size != int(p["rozmiar"])):
                return False
        except OSError:
            return False
    return True


def wpis_spisu(nazwa: str, model: dict, kat: Path) -> dict:
    zmienna = ZMIENNE.get(nazwa)
    return {"wersja": str(model.get("rewizja") or "?")[:12], "katalog": str(kat), "bin": [],
            "env": {zmienna: str(kat)} if zmienna else {}}


def zainstaluj(nazwa: str, model: dict, katalog_modeli: Path, *, log: Callable[[str], None] = print,
               pasek: bool = True) -> tuple[dict, bool]:
    """Model `nazwa` do `<katalog_modeli>/<katalog>`; zwraca (wpis narzedzia.json, czy coś pobrano/zapisano)."""
    kat = katalog(katalog_modeli, model)
    if gotowy(kat, model):
        return wpis_spisu(nazwa, model, kat), False
    mb = sum(int(p.get("rozmiar") or 0) for p in model.get("pliki") or []) / 1e6
    log(f"model {nazwa}: {len(model.get('pliki') or [])} plików, {mb:.0f} MB (rewizja "
        f"{str(model.get('rewizja'))[:12]})")
    try:
        pobieracz.zainstaluj_model(nazwa, model, katalog_modeli, pasek=pasek)
    except pobieracz.BladPobierania as e:
        raise BladModelu(str(e)) from None
    przenosne.zapisz_atomowo(kat / ZRODLO, _opis(nazwa, model))
    przenosne.zapisz_atomowo(kat / ZNACZNIK, json.dumps(_znacznik(model), ensure_ascii=False, indent=2) + "\n")
    return wpis_spisu(nazwa, model, kat), True
