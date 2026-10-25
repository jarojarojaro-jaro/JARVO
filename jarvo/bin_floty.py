"""Programy floty w `<program>/bin-floty` (docs/NATYWNIE.md: S01, F12, V11, E05; kontrakt z scripts/build.py).

bin-floty jest tylko w PATH procesów Jarva (jarvo/srodowisko.py: pierwszy katalog), nigdy w PATH właściciela. Build
wpisuje programy z tego katalogu do poleceń bramy pełną ścieżką (`--bin-dir`: HERMES_LOCAL_STT_COMMAND z jarvo-stt,
tts.providers.matcha.command z jarvo-tts; na Windows z .exe). Zawartość:

  python3                 Python venvu narzędzi (@@PY@@ skilli to ten sam interpreter): agent i skille wołają python3
  jarvo-tts, jarvo-stt,   skrypty `<app>/infra/bin` aktywnej wersji, uruchamiane Pythonem venvu narzędzi
  jarvo-klucz
  tesseract               Tesseract z pixi (bez całego katalogu Library/bin conda w PATH: openssl, kinit, zstd…)

Windows: CreateProcess nie uruchomi skryptu z shebangiem, a .cmd idzie przez cmd.exe (cytowanie argumentów), więc
programy to trampoliny uv: koło `jarvo_programy_floty` (jarvo/programy_floty.py z punktami wejścia) instalujemy
w venvie narzędzi bez sieci (`uv pip install --offline --no-index --no-deps`), a uv robi z punktów wejścia pliki
`Scripts\\<nazwa>.exe` ze ścieżką Pythona venvu; kopie tych plików trafiają do bin-floty (sprawdzone 2026-10-25 na
Windows 11 z uv 0.12.13: kopia trampoliny poza venvem uruchamia Python venvu). Git Bash znajduje `python3.exe` także
pod nazwą `python3`. Koło jest odtwarzalne (stałe daty w zipie), więc drugi przebieg niczego nie instaluje.
POSIX: kopia jarvo/programy_floty.py jako bin-floty/jarvo_programy_floty.py i skrypty sh z `exec` (bez procesu
pośredniego): python3 → Python venvu, jarvo-* → ten plik Pythonem venvu, tesseract → program z pixi.
Pliki zapisujemy tylko przy innej treści; programy, których już nie ma w instalacji (np. tesseract), znikają.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shlex
import stat
import zipfile
from pathlib import Path
from typing import Callable

from . import przenosne, srodowisko
from .sciezki import WINDOWS, Uklad

MODUL = "jarvo_programy_floty"
WERSJA_KOLA = "1.0"
ZRODLO = Path(__file__).with_name("programy_floty.py")
ZNACZNIK = ".jarvo-programy-floty.json"          # w venvie narzędzi: suma zainstalowanego koła
ZNACZNIK_SH = "# Jarvo: program floty (jarvo/bin_floty.py). Instalator nadpisuje ten plik."
SKRYPTY = ("jarvo-tts", "jarvo-stt", "jarvo-klucz")
NA_ZYWO = ("python3", *SKRYPTY)                  # zawsze; tesseract tylko z instalacją pixi
WSZYSTKIE = (*NA_ZYWO, "tesseract")
_DATA_ZIP = (1980, 1, 1, 0, 0, 0)


class BladProgramow(RuntimeError):
    """Programów floty nie da się przygotować (komunikat po polsku)."""


def nazwa_pliku(nazwa: str) -> str:
    return f"{nazwa}.exe" if WINDOWS else nazwa


def _zrodlo() -> bytes:
    """jarvo/programy_floty.py z LF (kopia z core.autocrlf=true miałaby CRLF i inną sumę koła)."""
    return ZRODLO.read_bytes().replace(b"\r\n", b"\n")


def zbuduj_kolo() -> tuple[str, bytes]:
    """(nazwa pliku, treść) koła `jarvo_programy_floty`: moduł z jarvo/programy_floty.py i punkty wejścia
    console_scripts; stałe daty i kolejność, więc ta sama treść źródła = te same bajty."""
    from .programy_floty import PUNKTY_WEJSCIA
    dist = f"{MODUL}-{WERSJA_KOLA}.dist-info"
    punkty = "".join(f"{n} = {MODUL}:{f}\n" for n, f in PUNKTY_WEJSCIA.items())
    pliki = {
        f"{MODUL}.py": _zrodlo(),
        f"{dist}/METADATA": (f"Metadata-Version: 2.1\nName: {MODUL}\nVersion: {WERSJA_KOLA}\n"
                             "Summary: Programy floty Jarva (python3, jarvo-tts, jarvo-stt, jarvo-klucz, tesseract)\n"
                             ).encode(),
        f"{dist}/WHEEL": b"Wheel-Version: 1.0\nGenerator: jarvo\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{dist}/entry_points.txt": f"[console_scripts]\n{punkty}".encode(),
    }
    rekordy = []
    for n, b in pliki.items():
        skrot = base64.urlsafe_b64encode(hashlib.sha256(b).digest()).rstrip(b"=").decode()
        rekordy.append(f"{n},sha256={skrot},{len(b)}")
    rekordy.append(f"{dist}/RECORD,,")
    pliki[f"{dist}/RECORD"] = ("\n".join(rekordy) + "\n").encode()
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in pliki.items():
            info = zipfile.ZipInfo(n, date_time=_DATA_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, b)
    return f"{MODUL}-{WERSJA_KOLA}-py3-none-any.whl", bufor.getvalue()


def _zapisz_jesli_inne(cel: Path, tresc: bytes, wykonywalny: bool = False) -> bool:
    try:
        if cel.is_file() and cel.read_bytes() == tresc:
            if wykonywalny and not WINDOWS and not os.access(cel, os.X_OK):
                os.chmod(cel, 0o755)
                return True
            return False
    except OSError:
        pass
    przenosne.zapisz_atomowo(cel, tresc, tryb=0o755 if wykonywalny else None)
    return True


def _sh(*argv: str) -> bytes:
    """Skrypt sh: `exec <argv> "$@"` (sygnały i kod wyjścia idą wprost)."""
    return (f"#!/bin/sh\n{ZNACZNIK_SH}\nexec {' '.join(shlex.quote(a) for a in argv)} \"$@\"\n").encode("utf-8")


def trampolina(venv_python: Path, nazwa: str) -> Path:
    """Program `nazwa` z bin-floty w Scripts venvu narzędzi: trampolina uv punktu wejścia (python3 i tesseract pod
    nazwą z przedrostkiem jarvo-: uv nie przyjmuje nazwy python3)."""
    from .programy_floty import WEJSCIE_PROGRAMU
    return Path(venv_python).parent / nazwa_pliku(WEJSCIE_PROGRAMU[nazwa])


def zainstaluj_kolo(u: Uklad, venv_python: Path, uv: Path, log: Callable[[str], None]) -> bool:
    """Koło programów w venvie narzędzi (Windows). True = zainstalowano (inna treść niż w znaczniku venvu)."""
    nazwa, tresc = zbuduj_kolo()
    suma = hashlib.sha256(tresc).hexdigest()
    venv = Path(venv_python).parent.parent
    znacznik = venv / ZNACZNIK
    if srodowisko.wczytaj_json(znacznik).get("sha256") == suma and all(
            trampolina(venv_python, n).is_file() for n in WSZYSTKIE):
        return False
    plik = u.cache / "bin-floty" / nazwa
    _zapisz_jesli_inne(plik, tresc)
    from .hermes import _strumien
    from .venvy import env_uv
    log(f"programy floty: koło {nazwa} w venvie narzędzi (bez sieci)")
    kod, ogon = _strumien([str(uv), "pip", "install", "--no-config", "--python", str(venv_python), "--offline",
                           "--no-index", "--no-deps", "--no-cache", "--reinstall", str(plik)],
                          cwd=u.stan, env=env_uv(u, Path(venv_python)), log=log)
    if kod:
        raise BladProgramow(f"uv pip install {nazwa} nie przeszedł (kod {kod}):\n"
                            + "\n".join(f"    {x}" for x in ogon[-6:]))
    przenosne.zapisz_atomowo(znacznik, json.dumps({"kolo": nazwa, "sha256": suma}, indent=2) + "\n")
    return True


def przygotuj(u: Uklad, *, venv_python: Path, uv: Path | None = None, tesseract: Path | None = None,
              log: Callable[[str], None] = print) -> list[str]:
    """Programy floty w `u.bin_floty` dla venvu narzędzi `venv_python` (i Tesseracta, gdy jest). Zwraca nazwy
    zmienionych plików (pusta lista = bez zmian). BladProgramow, gdy venvu albo uv nie ma."""
    venv_python = Path(venv_python)
    if not venv_python.is_file():
        raise BladProgramow(f"brak Pythona venvu narzędzi {venv_python} (krok venvów się nie wykonał)")
    bin_dir = u.bin_floty
    bin_dir.mkdir(parents=True, exist_ok=True)
    chce = [*NA_ZYWO, *(["tesseract"] if tesseract and Path(tesseract).is_file() else [])]
    zmiany: list[str] = []
    if WINDOWS:
        if uv is None or not Path(uv).is_file():
            raise BladProgramow("brak uv (krok narzędzi się nie wykonał): programy floty na Windows robi uv")
        if zainstaluj_kolo(u, venv_python, Path(uv), log):
            zmiany.append(f"koło {MODUL}")
        for nazwa in chce:
            zrodlo = trampolina(venv_python, nazwa)
            if not zrodlo.is_file():
                raise BladProgramow(f"uv nie zrobił programu {zrodlo}")
            if _zapisz_jesli_inne(bin_dir / nazwa_pliku(nazwa), zrodlo.read_bytes()):
                zmiany.append(nazwa_pliku(nazwa))
    else:
        dyspozytor = bin_dir / f"{MODUL}.py"
        if _zapisz_jesli_inne(dyspozytor, _zrodlo()):
            zmiany.append(dyspozytor.name)
        for nazwa in chce:
            if nazwa == "python3":
                tresc = _sh(str(venv_python))
            elif nazwa == "tesseract":
                tresc = _sh(str(tesseract))
            else:
                tresc = _sh(str(venv_python), str(dyspozytor), nazwa)
            if _zapisz_jesli_inne(bin_dir / nazwa, tresc, wykonywalny=True):
                zmiany.append(nazwa)
    for nazwa in WSZYSTKIE:                              # program, którego ta instalacja już nie ma
        p = bin_dir / nazwa_pliku(nazwa)
        if nazwa not in chce and p.is_file():
            p.unlink()
            zmiany.append(f"-{p.name}")
    for z in zmiany:
        log(f"programy floty: {z}")
    return zmiany


def sprawdz(u: Uklad) -> dict[str, bool]:
    """Który program floty jest w bin-floty i da się go uruchomić (doctor)."""
    def jest(p: Path) -> bool:
        return p.is_file() and (WINDOWS or bool(p.stat().st_mode & stat.S_IXUSR))
    return {n: jest(u.bin_floty / nazwa_pliku(n)) for n in WSZYSTKIE}
