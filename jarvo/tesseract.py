"""Tesseract z conda-forge przez pixi (docs/NATYWNIE.md: E05, L04, I22, I23; vendor/pixi/tesseract).

pixi z manifestu (wpis pixi, z sumą) instaluje dokładnie to, co jest w vendor/pixi/tesseract/pixi.lock (każda paczka
z sha256 i md5): `pixi install --locked` w kopii projektu w `<program>/narzedzia/tesseract/<12 znaków sha256
locka>` (pixi.toml, pixi.lock, .pixi/config.toml bez skryptów post-link i bez detektorów pakietów kanału), bez
`pixi run` i bez aktywacji środowiska. Windows arm64: `--platform win-64` (emulacja x64, I27: conda-forge nie ma
Tesseracta win-arm64). Środowisko pixi: PIXI_NO_TELEMETRY, PIXI_NO_CONFIG (z manifestu), cache pakietów
w `<cache>/pixi`, PIXI_HOME w `<cache>/pixi-home` (nic w katalogu domowym właściciela).

Języki: TESSDATA_PREFIX wskazuje model tessdata-fast z manifestu (`<dane>/jarvo/models/tessdata-fast`: pol, eng,
osd z sumami). Paczka conda ma ok. 125 języków (340 MB), więc pliki .traineddata ze środowiska pixi usuwamy,
a konfiguracje Tesseracta (configs/ z tsv, hocr, txt, pdf…, tessconfigs/ i pdf.ttf, licencja Apache-2.0 jak
program) kopiujemy obok modeli: bez nich `tesseract … tsv` (skill odczyt-ekranu, ocr.py) nie znajdzie konfiguracji.
Znacznik `.jarvo-tesseract.json` mówi, że instalacja jest gotowa: drugi przebieg nie woła pixi i nie potrzebuje sieci.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Callable

from . import przenosne, srodowisko
from .sciezki import WINDOWS, Uklad

PROJEKT = Path("vendor") / "pixi" / "tesseract"
PLIKI_PROJEKTU = ("pixi.toml", "pixi.lock", ".pixi/config.toml")
ZNACZNIK = ".jarvo-tesseract.json"
KONFIGURACJE = ("configs", "tessconfigs", "pdf.ttf")       # z share/tessdata paczki do katalogu TESSDATA_PREFIX
MODEL = "tessdata-fast"                                    # katalog modelu języków w <dane>/jarvo/models
CZAS_PIXI = 3600


class BladTesseracta(RuntimeError):
    """Tesseract się nie zainstalował (komunikat po polsku)."""


def _sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def projekt(app: Path) -> Path | None:
    """Projekt pixi w kodzie Jarva albo None (wersja bez Tesseracta z pixi)."""
    p = Path(app) / PROJEKT
    return p if all((p / f).is_file() for f in PLIKI_PROJEKTU) else None


def wersja(app: Path) -> str:
    """Wersja Tesseracta z pixi.toml (`tesseract = "==5.5.3"`)."""
    try:
        for linia in (Path(app) / PROJEKT / "pixi.toml").read_text(encoding="utf-8").splitlines():
            if linia.strip().startswith("tesseract") and "=" in linia:
                return linia.split("=", 1)[1].strip().strip('"').lstrip("=").strip() or "?"
    except OSError:
        pass
    return "?"


def katalog(u: Uklad, app: Path) -> Path:
    return u.program / "narzedzia" / "tesseract" / _sha256(Path(app) / PROJEKT / "pixi.lock")[:12]


def srodowisko_pixi(kat: Path) -> Path:
    return Path(kat) / ".pixi" / "envs" / "default"


def program(kat: Path) -> Path:
    env = srodowisko_pixi(kat)
    return env / "Library" / "bin" / "tesseract.exe" if WINDOWS else env / "bin" / "tesseract"


def katalogi_tessdata(kat: Path) -> list[Path]:
    """Katalogi tessdata paczki: na Windows conda ma konfiguracje w Library/share/tessdata, a języki
    w share/tessdata (sprawdzone 2026-10-25, tesseract 5.5.3 he87eeb8_0); na POSIX jedno share/tessdata."""
    env = srodowisko_pixi(kat)
    return [k for k in (env / "Library" / "share" / "tessdata", env / "share" / "tessdata") if k.is_dir()]


def _porzadki(kat: Path, modele: Path, log: Callable[[str], None] | None = None) -> bool:
    """Konfiguracje paczki obok języków z modelu, języki paczki usunięte. True = coś zmieniono."""
    zmiana = False
    for tessdata in katalogi_tessdata(kat):
        zmiana |= _kopiuj_konfiguracje(tessdata, Path(modele) / MODEL)
        mb = _usun_jezyki(tessdata)
        if mb:
            zmiana = True
            if log:
                log(f"Tesseract: języki z paczki usunięte ({mb} MB); języki z modelu {MODEL} (pol, eng, osd)")
    return zmiana


def wpis_spisu(app: Path, kat: Path, modele: Path) -> dict:
    """Wpis `tesseract` dla narzedzia.json: bez katalogu w PATH (bin-floty ma shim `tesseract`), program i języki."""
    return {"wersja": wersja(app), "katalog": str(kat), "program": str(program(kat)), "bin": [],
            "env": {"TESSDATA_PREFIX": str(Path(modele) / MODEL)}}


def env_pixi(u: Uklad, env_narzedzia: dict) -> dict[str, str]:
    """Środowisko pixi: bez PIXI_*, RATTLER_* i CONDA_* właściciela, zmienne z manifestu (PIXI_NO_TELEMETRY,
    PIXI_NO_CONFIG), cache i PIXI_HOME w katalogu Jarva."""
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("PIXI_", "RATTLER_", "CONDA_", "MAMBA_")) and k.upper() not in
           {o.upper() for o in srodowisko.OBCE}}
    env.update({str(k): str(v) for k, v in (env_narzedzia or {}).items()})
    # PIXI_NO_PROGRESS przyjmuje tylko true/false (pixi 0.83.0: „invalid value '1' for '--no-progress'”)
    env.update({"PIXI_NO_TELEMETRY": "1", "PIXI_NO_CONFIG": "1", "PIXI_CACHE_DIR": str(u.cache / "pixi"),
                "RATTLER_CACHE_DIR": str(u.cache / "pixi"), "PIXI_HOME": str(u.cache / "pixi-home"),
                "PIXI_NO_PROGRESS": "true", "NO_COLOR": "1"})
    if WINDOWS:
        env["NoDefaultCurrentDirectoryInExePath"] = "1"
    return env


def gotowy(kat: Path, suma_locka: str) -> bool:
    return srodowisko.wczytaj_json(Path(kat) / ZNACZNIK).get("lock_sha256") == suma_locka and program(kat).is_file()


def _kopiuj_konfiguracje(zrodlo: Path, cel: Path) -> bool:
    """configs/, tessconfigs/ i pdf.ttf z paczki do katalogu języków (tylko przy innej treści). True = zmiana."""
    zmiana = False
    for nazwa in KONFIGURACJE:
        z = zrodlo / nazwa
        if not z.exists():
            continue
        pliki = [z] if z.is_file() else sorted(p for p in z.rglob("*") if p.is_file())
        for p in pliki:
            c = cel / p.relative_to(zrodlo)
            dane = p.read_bytes()
            if c.is_file() and c.read_bytes() == dane:
                continue
            przenosne.zapisz_atomowo(c, dane)
            zmiana = True
    return zmiana


def _usun_jezyki(tessdata: Path) -> int:
    """Usuwa pliki .traineddata ze środowiska pixi (języki bierzemy z modelu tessdata-fast); zwraca liczbę MB."""
    razem = 0
    for p in sorted(Path(tessdata).glob("*.traineddata")):
        try:
            razem += p.stat().st_size
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            p.unlink()
        except OSError:
            pass
    return round(razem / 1e6)


def zainstaluj(u: Uklad, app: Path, *, pixi: Path, env_narzedzia: dict, platforma: str, modele: Path,
               log: Callable[[str], None] = print) -> tuple[dict, bool]:
    """Tesseract z pixi.lock do `<program>/narzedzia/tesseract/<skrót locka>`; zwraca (wpis narzedzia.json, czy
    coś zainstalowano). Gotowa instalacja (znacznik z tą samą sumą locka) = bez pixi i bez sieci."""
    zrodlo = projekt(app)
    if zrodlo is None:
        raise BladTesseracta(f"brak projektu {PROJEKT} w kodzie Jarva")
    suma = _sha256(zrodlo / "pixi.lock")
    kat = katalog(u, app)
    if gotowy(kat, suma):
        return wpis_spisu(app, kat, modele), _porzadki(kat, modele, log)
    if not Path(pixi).is_file():
        raise BladTesseracta(f"brak programu pixi ({pixi}): krok narzędzi się nie wykonał")
    with przenosne.Zamek(u.stan / "tesseract.lock"):
        if kat.exists() and not gotowy(kat, suma):
            log("Tesseract: resztka przerwanej instalacji, instaluję od nowa")
            shutil.rmtree(kat, onexc=lambda f, p, _e: (os.chmod(p, stat.S_IWRITE | stat.S_IREAD), f(p)))
        for rel in PLIKI_PROJEKTU:
            dane = (zrodlo / rel).read_bytes()
            przenosne.zapisz_atomowo(kat / rel, dane)
        argv = [str(pixi), "install", "--locked", "--manifest-path", str(kat / "pixi.toml")]
        if platforma == "windows-arm64":
            argv += ["--platform", "win-64"]                  # conda-forge nie ma tesseracta win-arm64 (I27)
        log(f"Tesseract {wersja(app)}: pixi install --locked (paczki conda-forge z sumami z pixi.lock)…")
        from .hermes import _strumien
        kod, ogon = _strumien(argv, cwd=kat, env=env_pixi(u, env_narzedzia), log=log)
        if kod or not program(kat).is_file():
            raise BladTesseracta(f"pixi install --locked nie przeszedł (kod {kod}); nie instaluję niczego spoza "
                                 "pixi.lock. Ostatnie linie:\n" + "\n".join(f"    {x}" for x in ogon[-8:]))
        _porzadki(kat, modele, log)
        przenosne.zapisz_atomowo(kat / ZNACZNIK, json.dumps({"lock_sha256": suma, "wersja": wersja(app),
                                                              "platforma": platforma}, indent=2) + "\n")
    log(f"Tesseract {wersja(app)}: gotowy ({program(kat)})")
    return wpis_spisu(app, kat, modele), True


def sprawdz(tess: Path, tessdata: Path, czas: float = 60) -> tuple[bool, str]:
    """`tesseract --list-langs` z TESSDATA_PREFIX (doctor i próba po instalacji): (ok, opis)."""
    env = {**os.environ, "TESSDATA_PREFIX": str(tessdata)}
    try:
        w = subprocess.run([str(tess), "--list-langs"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=czas, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)[:200]
    jezyki = [x.strip() for x in w.stdout.splitlines()[1:] if x.strip()]
    ok = w.returncode == 0 and {"pol", "eng"} <= set(jezyki)
    return ok, ", ".join(jezyki) if jezyki else (w.stderr.strip()[:200] or f"kod {w.returncode}")
