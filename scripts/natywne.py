#!/usr/bin/env python3
"""Manifest narzędzi instalacji natywnej (docs/NATYWNIE.md, L03): vendor/natywne.yaml → vendor/natywne.lock.json.

    python scripts/natywne.py sprawdz      # kompletność wpisów (url https, sha256, rozmiar, format, źródło w spisie)
    python scripts/natywne.py generuj      # zapis vendor/natywne.lock.json (czyta go instalator bez YAML)

validate.py woła `bledy()` i porównuje lock z wygenerowanym, więc zmiana manifestu bez nowego locka nie przejdzie.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

MANIFEST = fl.REPO_ROOT / "vendor" / "natywne.yaml"
LOCK = fl.REPO_ROOT / "vendor" / "natywne.lock.json"
ZRODLA = fl.REPO_ROOT / "vendor" / "zrodla.yaml"
DOCKERFILE = fl.REPO_ROOT / "infra" / "Dockerfile"
PLATFORMY = ("windows-x64", "windows-arm64", "macos-arm64", "linux-x64", "linux-arm64")
FORMATY = {"zip", "tar.gz", "tar.xz", "tar.bz2", "plik"}
KIEDY = {"instalacja", "przy-uzyciu", "dodatek"}
POLA_PLIKU = {"url", "sha256", "rozmiar", "format", "usun_poziom", "bin", "env", "nazwa_pliku", "brak", "zamiast"}
NAZWA = re.compile(r"^[a-z][a-z0-9-]*$")
SHA = re.compile(r"^[0-9a-f]{64}$")


def wczytaj(path: Path | None = None) -> dict:
    return fl.load_yaml(path or MANIFEST) or {}


def bledy(dane: dict, zrodla: dict | None = None) -> list[str]:
    """Lista problemów manifestu (pusta = dobrze). `zrodla` = słownik `zrodla` z vendor/zrodla.yaml."""
    wynik: list[str] = []
    if dane.get("version") != 1:
        wynik.append("natywne.yaml: version musi być 1")
    h = dane.get("hermes") or {}
    if not re.match(r"^https://github\.com/[\w.-]+/[\w.-]+$", str(h.get("repo") or "")):
        wynik.append("natywne.yaml/hermes: repo musi być adresem https://github.com/<właściciel>/<repo>")
    if not re.match(r"^[0-9a-f]{40}$", str(h.get("commit") or "")):
        wynik.append("natywne.yaml/hermes: commit musi być pełnym SHA (40 znaków)")
    if not str(h.get("tag") or "").strip() or not str(h.get("wersja") or "").strip():
        wynik.append("natywne.yaml/hermes: brak tagu albo wersji")
    if not isinstance(h.get("dodatki"), list) or not all(isinstance(x, str) for x in h["dodatki"]):
        wynik.append("natywne.yaml/hermes: dodatki to lista nazw extras z pyproject.toml Hermesa")
    obraz = DOCKERFILE.read_text(encoding="utf-8") if DOCKERFILE.is_file() else ""
    m = re.search(r"^ARG HERMES_IMAGE=[^:\s]+:([^@\s]+)", obraz, re.M)
    if m and h.get("tag") and m.group(1) != h["tag"]:
        wynik.append(f"natywne.yaml/hermes: tag {h['tag']} różni się od obrazu VPS ({m.group(1)} w infra/Dockerfile)")
    narzedzia = dane.get("narzedzia") or {}
    if not isinstance(narzedzia, dict) or not narzedzia:
        return wynik + ["natywne.yaml: brak sekcji narzedzia"]
    for nazwa, wpis in narzedzia.items():
        gdzie = f"natywne.yaml/{nazwa}"
        if not NAZWA.match(str(nazwa)):
            wynik.append(f"{gdzie}: nazwa tylko z małych liter, cyfr i myślników")
        if not isinstance(wpis, dict):
            wynik.append(f"{gdzie}: wpis musi być słownikiem")
            continue
        for pole in ("zrodlo", "wersja", "licencja", "rola"):
            if not str(wpis.get(pole) or "").strip():
                wynik.append(f"{gdzie}: brak pola {pole}")
        if zrodla is not None and wpis.get("zrodlo") and wpis["zrodlo"] not in zrodla:
            wynik.append(f"{gdzie}: źródła {wpis['zrodlo']!r} nie ma w vendor/zrodla.yaml (przegląd z docs/SOURCES.md)")
        if (wpis.get("kiedy") or "instalacja") not in KIEDY:
            wynik.append(f"{gdzie}: kiedy spoza {sorted(KIEDY)}")
        pliki = wpis.get("pliki") or {}
        for platforma in PLATFORMY:
            p = pliki.get(platforma)
            gp = f"{gdzie}/{platforma}"
            if not isinstance(p, dict):
                wynik.append(f"{gp}: brak pliku (podaj plik albo `brak: <powód>`)")
                continue
            obce = set(p) - POLA_PLIKU
            if obce:
                wynik.append(f"{gp}: nieznane pola {sorted(obce)}")
            if "brak" in p:
                if not str(p.get("brak") or "").strip():
                    wynik.append(f"{gp}: `brak` wymaga powodu")
                continue
            url = str(p.get("url") or "")
            if not url.startswith("https://") or "latest" in url.split("?")[0].split("/"):
                wynik.append(f"{gp}: url musi być dokładnym adresem https (bez latest)")
            if not SHA.match(str(p.get("sha256") or "")):
                wynik.append(f"{gp}: sha256 musi mieć 64 znaki hex")
            if not isinstance(p.get("rozmiar"), int) or p["rozmiar"] <= 0:
                wynik.append(f"{gp}: rozmiar w bajtach (liczba)")
            if p.get("format") not in FORMATY:
                wynik.append(f"{gp}: format spoza {sorted(FORMATY)}")
            if not isinstance(p.get("usun_poziom", 0), int) or p.get("usun_poziom", 0) < 0:
                wynik.append(f"{gp}: usun_poziom to liczba >= 0")
            for k in p.get("bin") or []:
                if str(k).startswith(("/", "\\")) or ".." in str(k).replace("\\", "/").split("/"):
                    wynik.append(f"{gp}: bin {k!r} ma być ścieżką względną w katalogu narzędzia")
        for platforma in set(pliki) - set(PLATFORMY):
            wynik.append(f"{gdzie}: nieznana platforma {platforma}")
    return wynik


def lock(dane: dict) -> dict:
    """Postać dla instalatora: tylko to, czego potrzebuje pobieracz, posortowane (stabilny diff)."""
    out = {}
    for nazwa in sorted(dane.get("narzedzia") or {}):
        w = dane["narzedzia"][nazwa]
        pliki = {}
        for platforma in PLATFORMY:
            p = dict((w.get("pliki") or {}).get(platforma) or {})
            pliki[platforma] = {k: p[k] for k in sorted(p)}
        out[nazwa] = {"wersja": str(w["wersja"]), "kiedy": w.get("kiedy") or "instalacja",
                      "licencja": str(w["licencja"]), "zrodlo": str(w["zrodlo"]), "pliki": pliki}
    h = dane.get("hermes") or {}
    hermes = {k: h[k] for k in ("repo", "tag", "commit", "wersja", "dodatki") if k in h}
    return {"version": 1, "hermes": hermes, "narzedzia": out}


def tekst_locka(dane: dict) -> str:
    return json.dumps(lock(dane), ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main(argv: list[str]) -> int:
    polecenie = argv[1] if len(argv) > 1 else "sprawdz"
    dane = wczytaj()
    zrodla = (fl.load_yaml(ZRODLA) or {}).get("zrodla") or {}
    problemy = bledy(dane, zrodla)
    for p in problemy:
        print(f"✗ {p}")
    if problemy:
        return 1
    if polecenie == "generuj":
        LOCK.write_text(tekst_locka(dane), encoding="utf-8", newline="\n")
        print(f"✓ {LOCK.relative_to(fl.REPO_ROOT).as_posix()}: {len(dane['narzedzia'])} narzędzi")
        return 0
    if polecenie == "sprawdz":
        aktualny = LOCK.is_file() and LOCK.read_text(encoding="utf-8") == tekst_locka(dane)
        print("✓ manifest kompletny" + ("" if aktualny else "; lock nieaktualny: python scripts/natywne.py generuj"))
        return 0 if aktualny else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
