"""Głos Jarva w aplikacji (docs/HQ.md „Pierwsze spotkanie”): krótkie zdania z lokalnego lektora `jarvo-tts` z instalacji
Jarva (polski Matcha-TTS-PL v2, dwa głosy; angielski Paradee), bez sieci i bez modelu językowego. W obrazie
/opt/jarvo/bin/jarvo-tts, natywnie program floty `<program>/bin-floty/jarvo-tts(.exe)` w PATH panelu.

- `POST /app/glos` `{tekst, glos, tempo, jezyk}` → WAV. Głos `meski` / `damski` (polski), tempo `spokojnie` /
  `normalnie` / `zwawo` (szybkość 0,9 / 1,0 / 1,12); `jezyk: en` = Paradee niezależnie od głosu.
- `POST /app/glos/przygotuj` `{teksty, glos, tempo, jezyk}` → 202: brakujące zdania jednym wsadem w tle (`--wsad`,
  model ładowany raz), żeby stałe kwestie rozmowy grały od razu.
- Pamięć podręczna: `<katalog>/<sha256(wersja|głos|szybkość|tekst)>.wav`, najwyżej PLIKI_MAKS plików (najstarsze
  użycie znika). Jeden proces lektora naraz (zamek), limit czasu, tekst najwyżej TEKST_MAKS znaków jednej linii.
- Na Windows lektor dostaje własny Job Object (edytor.przypnij_drzewo): limit czasu i restart dashboardu kończą też
  jego Pythona.
- Brak programu (stary obraz, testy na hoście) = `BrakGlosu`: trasa odpowiada 503 `brak_glosu`, a aplikacja mówi
  głosem przeglądarki (speechSynthesis) albo pokazuje sam tekst.
Testy: tests/test_aplikacja.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Awaitable, Callable

GLOSY = {"meski": "pl-PL-Matcha-Meski", "damski": "pl-PL-Matcha-Damski"}
GLOS_EN = "en-US-Paradee"
TEMPA = {"spokojnie": 0.9, "normalnie": 1.0, "zwawo": 1.12}
TEKST_MAKS = 400
PRZYGOTUJ_MAKS = 12
PLIKI_MAKS = 200
TIMEOUT_S = 90.0
WERSJA = "1"
PROGRAM_OBRAZU = "/opt/jarvo/bin/jarvo-tts"


class BrakGlosu(RuntimeError):
    """Nie ma lektora `jarvo-tts` w tej instalacji."""


class BladGlosu(RuntimeError):
    """Lektor nie zrobił pliku (błąd albo limit czasu)."""


def tekst_mowy(s: object) -> str:
    """Jedna linia do przeczytania: bez znaków sterujących, spacje złączone, najwyżej TEKST_MAKS znaków."""
    s = re.sub(r"[\x00-\x1f\x7f]", " ", str(s or ""))
    return " ".join(s.split())[:TEKST_MAKS].strip()


def model_glosu(glos: str, jezyk: str = "pl") -> str:
    return GLOS_EN if jezyk == "en" else GLOSY.get(glos, GLOSY["meski"])


def szybkosc(tempo: str) -> float:
    return TEMPA.get(tempo, TEMPA["normalnie"])


def plik(katalog: Path | str, tekst: str, model: str, szybkosc_: float) -> Path:
    h = hashlib.sha256(f"{WERSJA}|{model}|{szybkosc_:.2f}|{tekst}".encode()).hexdigest()[:32]
    return Path(katalog) / f"{h}.wav"


def program_glosu() -> str | None:
    """`JARVO_TTS`, potem lektor z obrazu, potem `jarvo-tts` z PATH (natywnie bin-floty, na Windows `jarvo-tts.exe`);
    None = nie ma."""
    for kandydat in (os.environ.get("JARVO_TTS"), PROGRAM_OBRAZU):
        if kandydat and os.path.isfile(kandydat) and os.access(kandydat, os.X_OK):
            return kandydat
    return shutil.which("jarvo-tts")


def sprzataj(katalog: Path | str, maks: int = PLIKI_MAKS) -> int:
    """Najstarsze (po czasie ostatniego użycia) pliki ponad `maks` i porzucone pliki robocze znikają."""
    k = Path(katalog)
    try:
        pliki = [p for p in k.iterdir() if p.is_file()]
    except OSError:
        return 0
    usuniete = 0
    for p in pliki:
        if p.name.startswith("."):
            p.unlink(missing_ok=True)
            usuniete += 1
    wav = sorted((p for p in pliki if p.suffix == ".wav" and not p.name.startswith(".")),
                 key=lambda p: p.stat().st_mtime, reverse=True)
    for p in wav[maks:]:
        p.unlink(missing_ok=True)
        usuniete += 1
    return usuniete


def _modul(nazwa: str, plik: str):
    """Moduł wtyczki załadowany przez plugin_api (`nazwa` w sys.modules) albo z pliku obok."""
    mod = sys.modules.get(nazwa)
    if mod is None:
        spec = importlib.util.spec_from_file_location(nazwa, Path(__file__).with_name(plik))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[nazwa] = mod
        spec.loader.exec_module(mod)
    return mod


def _przenosne():
    """przenosne.py wtyczki (załadowany przez plugin_api jako jarvo_hq_przenosne albo z pliku obok)."""
    return _modul("jarvo_hq_przenosne", "przenosne.py")


def _edytor():
    """edytor.py wtyczki (jarvo_hq_edytor): przypnij_drzewo, Job Object programu na Windows."""
    return _modul("jarvo_hq_edytor", "edytor.py")


async def _uruchom(argv: list[str], timeout: float) -> int:
    """Lektor w wątku (przenosne.uruchom: także na Windows, gdzie pętla dashboardu nie ma podprocesów asyncio);
    po limicie czasu program jest zabity i skończony. Na Windows program dostaje od razu własny Job Object
    (edytor.przypnij_drzewo): padnięty albo zrestartowany dashboard nie zostawia lektora z Pythonem w tle, a limit
    czasu i przerwane żądanie kończą całe drzewo (edytor.zabij_drzewo), bez czekania na sprzątanie uchwytu."""
    p = _przenosne()
    try:
        e = _edytor()
        przypnij, zabij = e.przypnij_drzewo, e.zabij_drzewo
    except (OSError, ImportError, AttributeError):
        przypnij = zabij = None
    uruchomione = []

    def start(proc) -> None:
        uruchomione.append(proc)
        if przypnij is not None:
            przypnij(proc)

    def koniec_drzewa() -> None:
        for proc in uruchomione:
            if zabij is not None:
                zabij(proc)
    try:
        kod, _out, _err = await p.uruchom(argv, timeout=timeout, stdin=p.DEVNULL, stdout=p.DEVNULL, stderr=p.DEVNULL,
                                          przy_starcie=start)
    except asyncio.TimeoutError:
        koniec_drzewa()
        raise BladGlosu("limit czasu") from None
    except BaseException:
        koniec_drzewa()
        raise
    return kod


class Glos:
    """Lektor aplikacji z pamięcią podręczną; jeden proces `jarvo-tts` naraz."""

    def __init__(self, katalog: Path | str, *, program: Callable[[], str | None] = program_glosu,
                 uruchom: Callable[[list[str], float], Awaitable[int]] = _uruchom, timeout: float = TIMEOUT_S):
        self.katalog, self.program, self.uruchom, self.timeout = Path(katalog), program, uruchom, timeout
        self._zamek: asyncio.Lock | None = None
        self._w_tle: set[asyncio.Task] = set()

    def _lock(self) -> asyncio.Lock:
        if self._zamek is None:
            self._zamek = asyncio.Lock()
        return self._zamek

    def _bin(self) -> str:
        b = self.program()
        if not b:
            raise BrakGlosu("brak jarvo-tts")
        return b

    async def mow(self, tekst: str, glos: str = "meski", tempo: str = "normalnie", jezyk: str = "pl") -> Path:
        """Plik WAV z tym zdaniem (z pamięci albo nowy)."""
        tekst = tekst_mowy(tekst)
        if not tekst:
            raise ValueError("pusty tekst")
        model, sz = model_glosu(glos, jezyk), szybkosc(tempo)
        cel = plik(self.katalog, tekst, model, sz)
        if cel.is_file():
            os.utime(cel)
            return cel
        b = self._bin()
        async with self._lock():
            if cel.is_file():                              # zrobił go wsad albo inne żądanie
                return cel
            self.katalog.mkdir(parents=True, exist_ok=True)
            tmp = cel.with_name(f".{cel.stem}.{os.getpid()}.wav")
            try:
                kod = await self.uruchom([b, tekst, "-o", str(tmp), "--glos", model, "--szybkosc", f"{sz:.2f}"], self.timeout)
                if kod != 0 or not tmp.is_file() or tmp.stat().st_size < 64:
                    raise BladGlosu(f"kod {kod}")
                os.replace(tmp, cel)
            finally:
                tmp.unlink(missing_ok=True)
            sprzataj(self.katalog)
        return cel

    def przygotuj(self, teksty: list[str], glos: str = "meski", tempo: str = "normalnie", jezyk: str = "pl") -> int:
        """Brakujące zdania jednym wsadem w tle; zwraca, ile trafiło do wsadu (0 = wszystko już jest)."""
        model, sz = model_glosu(glos, jezyk), szybkosc(tempo)
        brak: dict[Path, str] = {}
        for t in list(teksty)[:PRZYGOTUJ_MAKS]:
            t = tekst_mowy(t)
            if t:
                cel = plik(self.katalog, t, model, sz)
                if not cel.is_file():
                    brak[cel] = t
        if not brak:
            return 0
        b = self._bin()
        zadanie = asyncio.get_running_loop().create_task(self._wsad(b, brak, model, sz))
        self._w_tle.add(zadanie)
        zadanie.add_done_callback(self._w_tle.discard)
        return len(brak)

    async def _wsad(self, b: str, brak: dict[Path, str], model: str, sz: float) -> None:
        async with self._lock():
            brak = {c: t for c, t in brak.items() if not c.is_file()}
            if not brak:
                return
            self.katalog.mkdir(parents=True, exist_ok=True)
            pid = os.getpid()
            tmp = {c: c.with_name(f".{c.stem}.{pid}.wav") for c in brak}
            lista = self.katalog / f".wsad.{pid}.json"
            lista.write_text(json.dumps([{"tekst": t, "wyjscie": str(tmp[c]), "szybkosc": round(sz, 2), "glos": model}
                                         for c, t in brak.items()], ensure_ascii=False), encoding="utf-8")
            try:
                await self.uruchom([b, "--wsad", str(lista)], self.timeout * 2)
            except BladGlosu:
                pass
            finally:
                for c, p in tmp.items():
                    if p.is_file() and p.stat().st_size >= 64:
                        os.replace(p, c)
                    p.unlink(missing_ok=True)
                lista.unlink(missing_ok=True)
            sprzataj(self.katalog)
