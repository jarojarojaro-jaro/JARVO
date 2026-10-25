"""Venvy Jarva z locków z sumami (docs/NATYWNIE.md: c3 krok 6, P01, P03, I31, E10, V01).

Sekcja `venvy` manifestu (vendor/natywne.lock.json) mówi, z którego locka (plik w infra/python/, każde wymaganie
z --hash) i na którym Pythonie z sekcji narzedzia zbudować venv. Instalator bierze venvy z `kiedy: instalacja`
(dziś narzedzia, ocr, claude-seo); dodatki i instalacje przy pierwszym użyciu przyjdą z `jarvo narzedzia dodaj`.

    uv venv --no-config --python <python312|python313> <program>/venvs/<nazwa>-<12 znaków sha256 locka>
    uv pip install --no-config --python <venv> --no-deps --require-hashes --only-binary :all: --compile-bytecode
                   [--torch-backend <torch_backend>] -r <lock>

Przed instalacją sprawdzamy sumę locka z manifestem (lock zmieniony bez `scripts/natywne.py generuj` zatrzymuje
instalację). Środowisko uv jak przy Hermesie (jarvo/hermes.py: bez zmiennych UV_* właściciela, UV_PYTHON_DOWNLOADS=
never, UV_CACHE_DIR w <cache>/uv, UV_LINK_MODE=copy, bo na Windows załadowanych .pyd nie da się nadpisać). Venvu nie
budujemy obok i nie przenosimy (ścieżki w pyvenv.cfg i programach venvu są bezwzględne), więc gotowość mówi znacznik
`.jarvo-venv.json` zapisany na końcu: venv bez znacznika to resztka przerwanej instalacji i budujemy go od nowa.
Drugi przebieg ze znacznikiem nie woła uv i nie potrzebuje sieci.

Wpis dla `<stan>/narzedzia.json`: `venv-<nazwa>` = {"wersja": skrót locka, "katalog", "python", "bin", "env"}.
`env` daje procesom floty interpreter venvu (JARVO_TOOLS_PYTHON, JARVO_OCR_PYTHON, CLAUDE_SEO_PYTHON…), a `bin`
(tylko venv narzędzi) dokłada jego programy (yt-dlp, trafilatura) do PATH procesów floty, jak /opt/jarvo/venv/bin
w obrazie. Python venvu narzędzi to też @@PY@@ skilli i shim python3 (jarvo/flota.py, jarvo/bin_floty.py, F12).

Miejsce (c3 pkt 11, Z31): `miejsce(wpis, platforma)` liczy venv i koła w cache uv z manifestu (pobranie_mb platformy,
venv_mb zmierzone na Windows 11 x64), a `sprzatnij_cache` po udanej instalacji robi `uv cache clean` w <cache>/uv:
venvy i .venv Hermesa mają własne kopie plików (UV_LINK_MODE=copy), a znaczniki sprawiają, że kolejny przebieg nie
woła uv, więc cache nie jest już potrzebny (nowy lock przy aktualizacji pobierze koła od nowa). Sprzątanie bierze
zamki instalatorów, które korzystają z tego cache (ZAMKI_CACHE: venvy, także przy pierwszym użyciu, i Hermes, którego
trzeci krok `uv sync --offline` bierze koła z cache), bez czekania: zajęty = drugi instalator właśnie z niego
korzysta, więc cache zostaje do następnej instalacji.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import przenosne, srodowisko
from .sciezki import WINDOWS, Uklad

ZNACZNIK = ".jarvo-venv.json"
KATALOG = "venvs"
ZAMEK = "venvy.lock"                     # w <stan>: budowa venvu (instalator i pierwsze użycie)
# zamki w <stan> instalatorów, które czytają i piszą cache uv (zainstaluj i hermes.zainstaluj): sprzątanie bierze
# oba, zawsze w tej kolejności i bez czekania, więc nie zakleszczy się z żadnym z nich
ZAMKI_CACHE = (ZAMEK, "hermes.lock")
# zmienna procesów floty z interpreterem venvu (skrypty i skille: ocr.py, cad.py, claude-seo, @@PY@@ z JARVO_TOOLS)
ZMIENNE = {"narzedzia": "JARVO_TOOLS_PYTHON", "ocr": "JARVO_OCR_PYTHON", "claude-seo": "CLAUDE_SEO_PYTHON",
           "cad": "JARVO_CAD_PYTHON", "manimgx": "JARVO_MANIMGX_PYTHON", "rembg": "JARVO_REMBG_PYTHON",
           "mgaudio": "JARVO_MGAUDIO_PYTHON", "lemo-wake": "JARVO_LEMO_WAKE_PYTHON",
           "docling": "JARVO_DOCLING_PYTHON"}
W_PATH = ("narzedzia",)                  # programy tego venvu w PATH procesów floty (jak /opt/jarvo/venv/bin)
CZAS_UV = 3600                           # s na jedno polecenie uv (pierwsza instalacja pobiera 150–400 MB kół)
CZAS_SPRZATANIA = 120                    # s na `uv cache clean` (czeka, gdy cache trzyma inny proces uv)
WZOR = "windows-x64"                     # platforma, na której zmierzono venv_mb
WSP_VENVU = 4.5                          # venv bez venv_mb: pobrane koła × tyle (zmierzone 2,7–4,5 na Windows 11 x64)
WSP_CACHE = 0.8                          # cache uv trzyma koła rozpakowane: venv bez .pyc (zmierzone 0,77 na Windows)


class BladVenvu(RuntimeError):
    """Venv się nie zbudował (komunikat po polsku z radą, bez sekretów)."""


def do_instalacji(venvy: dict) -> list[str]:
    """Venvy z `kiedy: instalacja` (bez pola: instalacja), w kolejności manifestu."""
    return [n for n, w in venvy.items() if isinstance(w, dict) and (w.get("kiedy") or "instalacja") == "instalacja"]


def katalog(u: Uklad, nazwa: str, wpis: dict) -> Path:
    """`<program>/venvs/<nazwa>-<12 znaków sha256 locka>`: nowy lock = nowy venv obok starego (c4: aktualizacja)."""
    return u.program / KATALOG / f"{nazwa}-{str(wpis['sha256'])[:12]}"


def python_venvu(kat: Path) -> Path:
    return Path(kat) / ("Scripts/python.exe" if WINDOWS else "bin/python")


def bin_venvu(kat: Path) -> Path:
    return Path(kat) / ("Scripts" if WINDOWS else "bin")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()


def wpis_spisu(nazwa: str, wpis: dict, kat: Path) -> dict:
    """Wpis `venv-<nazwa>` dla narzedzia.json."""
    py = python_venvu(kat)
    zmienna = ZMIENNE.get(nazwa)
    return {"wersja": str(wpis["sha256"])[:12], "katalog": str(kat), "python": str(py),
            "bin": [str(bin_venvu(kat))] if nazwa in W_PATH else [],
            "env": {zmienna: str(py)} if zmienna else {}}


def _usun(p: Path) -> None:
    def odblokuj(funkcja, sciezka, _blad):
        os.chmod(sciezka, stat.S_IWRITE | stat.S_IREAD)
        funkcja(sciezka)
    shutil.rmtree(p, onexc=odblokuj)


def _uruchom(argv: list, *, env: dict, cwd: Path, log: Callable[[str], None]) -> None:
    """Polecenie uv z wyjściem w logu (paski co 5 s, linie paczek „ + …” pomijane), błąd = BladVenvu z ogonem."""
    from .hermes import _linia_paczki, _strumien            # ten sam strumień co przy Hermesie (Ctrl+C: całe drzewo)
    kod, ogon = _strumien(argv, cwd=cwd, env=env, log=log, przemilcz=_linia_paczki)
    if kod:
        koniec = "\n".join(f"    {x}" for x in ogon[-8:])
        niski = "\n".join(ogon).lower()
        if "hash" in niski and ("mismatch" in niski or "does not match" in niski):
            powod = "suma pliku z PyPI nie zgadza się z lockiem"
        elif "no matching distribution" in niski or ("wheel" in niski and "platform" in niski):
            powod = "w locku nie ma gotowej paczki (koła) dla tego systemu"
        else:
            powod = "uv zakończył się błędem"
        raise BladVenvu(f"`{' '.join(str(a) for a in argv[1:4])} …` nie przeszedł (kod {kod}): {powod}. Nie instaluję "
                        f"niczego bez sum z locka. Ostatnie linie:\n{koniec}")


def env_uv(u: Uklad, python: Path) -> dict[str, str]:
    """Środowisko uv bez konfiguracji właściciela (jak hermes._env_uv: UV_* odcięte, pusty katalog konfiguracji)."""
    from .hermes import _env_uv
    return _env_uv(u, str(python))


def gotowy(kat: Path, wpis: dict, python: Path) -> bool:
    z = srodowisko.wczytaj_json(Path(kat) / ZNACZNIK)
    return (z.get("lock_sha256") == wpis.get("sha256") and z.get("torch_backend") == wpis.get("torch_backend")
            and os.path.normcase(str(z.get("python_bazowy") or "")) == os.path.normcase(str(python))
            and python_venvu(kat).is_file())


def zainstalowany(kat: Path, wpis: dict) -> bool:
    """Venv z tego locka już jest (znacznik i Python venvu), bez sprawdzania Pythona bazowego: do liczenia miejsca
    przed krokiem narzędzi, gdy Pythona z manifestu może jeszcze nie być."""
    z = srodowisko.wczytaj_json(Path(kat) / ZNACZNIK)
    return z.get("lock_sha256") == wpis.get("sha256") and python_venvu(kat).is_file()


def miejsce(wpis: dict, platforma: str) -> tuple[int, int]:
    """(venv, koła w cache uv) w bajtach z manifestu dla platformy: venv_mb (zmierzone na WZOR) przeliczone przez
    pobranie_mb tej platformy i WZOR, bez venv_mb pobranie_mb × WSP_VENVU; cache uv ok. WSP_CACHE venvu. Brak
    pobranie_mb dla platformy: największe z innych platform."""
    pobranie = wpis.get("pobranie_mb") if isinstance(wpis.get("pobranie_mb"), dict) else {}
    liczby = [float(v) for v in pobranie.values() if isinstance(v, (int, float))]
    mb = float(pobranie.get(platforma) or (max(liczby) if liczby else 0))
    wzor = pobranie.get(WZOR)
    if isinstance(wpis.get("venv_mb"), (int, float)):
        venv = float(wpis["venv_mb"]) * (mb / float(wzor) if isinstance(wzor, (int, float)) and wzor else 1.0)
    else:
        venv = mb * WSP_VENVU
    return int(venv * 10 ** 6), int(venv * WSP_CACHE * 10 ** 6)


def sprzatnij_cache(u: Uklad, uv: Path, *, log: Callable[[str], None] = print, czas: float = CZAS_SPRZATANIA) -> bool:
    """`uv cache clean` w <cache>/uv po udanej instalacji (docstring modułu), w środowisku uv instalacji (bez
    konfiguracji właściciela, UV_CACHE_DIR Jarva), pod zamkami ZAMKI_CACHE bez czekania. `uv cache prune` usunąłby
    tylko wpisy nieosiągalne, czyli prawie nic, bo wszystkie koła z locków są w indeksie. True = uv skończył bez
    błędu; zajęty zamek (drugi instalator buduje venv albo instaluje Hermesa), cache w użyciu przez inny proces uv
    (uv czeka wtedy na niego) albo limit czasu = False i wiersz w logu: cache zostaje do następnej instalacji."""
    from .hermes import BladHermesa, _wywolaj
    with contextlib.ExitStack() as zamki:
        try:
            for nazwa in ZAMKI_CACHE:
                zamki.enter_context(przenosne.Zamek(u.stan / nazwa, czekaj=False))
        except BlockingIOError:
            log("cache uv zostaje do następnej instalacji (drugi instalator właśnie buduje venv albo instaluje "
                "Hermesa)")
            return False
        env = env_uv(u, Path(uv))
        env.pop("UV_PYTHON", None)                # `cache clean` nie szuka Pythona
        try:
            w = _wywolaj([str(uv), "cache", "clean", "--no-config"], env=env, cwd=u.stan, opis="uv cache clean",
                         czas=int(czas))
        except BladHermesa as e:
            log(f"cache uv zostaje do następnej instalacji ({e})")
            return False
    linie = [x.strip() for x in f"{w.stdout}\n{w.stderr}".splitlines() if x.strip()]
    if w.returncode:
        log(f"cache uv zostaje do następnej instalacji (uv cache clean: kod {w.returncode}"
            + (f", {linie[-1][:160]}" if linie else "") + ")")
        return False
    log(f"cache uv: {linie[-1][:160]}" if linie else "cache uv: wyczyszczony")
    return True


def zainstaluj(u: Uklad, app: Path, nazwa: str, wpis: dict, *, uv: Path, python: Path,
               log: Callable[[str], None] = print) -> tuple[dict, bool]:
    """Venv `nazwa` z locka manifestu; zwraca (wpis do narzedzia.json, czy coś zainstalowano). Gotowy venv (znacznik
    z tą samą sumą locka i tym samym Pythonem) = bez żadnego wywołania i bez sieci. BladVenvu przy błędzie."""
    kat = katalog(u, nazwa, wpis)
    if gotowy(kat, wpis, python):
        return wpis_spisu(nazwa, wpis, kat), False
    lock = Path(app) / str(wpis["lock"])
    if not lock.is_file():
        raise BladVenvu(f"venv {nazwa}: brak locka {lock} w kodzie Jarva")
    suma = _sha256(lock)
    if suma != wpis["sha256"]:
        raise BladVenvu(f"venv {nazwa}: lock {wpis['lock']} ma sumę {suma[:12]}…, a manifest {wpis['sha256'][:12]}…. "
                        "Lock zmieniono bez `python scripts/natywne.py generuj`: nie instaluję go.")
    if not Path(python).is_file() or not Path(uv).is_file():
        raise BladVenvu(f"venv {nazwa}: brak {python if not Path(python).is_file() else uv} (krok narzędzi się nie "
                        "wykonał)")
    with przenosne.Zamek(u.stan / ZAMEK):
        if gotowy(kat, wpis, python):                         # drugi instalator skończył, gdy czekaliśmy
            return wpis_spisu(nazwa, wpis, kat), False
        if kat.exists():
            log(f"venv {nazwa}: resztka przerwanej instalacji, buduję od nowa")
            try:
                _usun(kat)
            except OSError as e:
                raise BladVenvu(f"nie usunę {kat} ({e.strerror or e}): zamknij programy, które z niego korzystają "
                                "(np. jarvo down), i uruchom instalację jeszcze raz") from None
        kat.parent.mkdir(parents=True, exist_ok=True)
        env = env_uv(u, Path(python))
        log(f"venv {nazwa}: Python {Path(python).parent.name}, lock {wpis['lock']} "
            f"({wpis.get('paczek', '?')} paczek, sumy sha256)")
        _uruchom([str(uv), "venv", "--no-config", "--python", str(python), str(kat)], env=env, cwd=u.stan, log=log)
        argv = [str(uv), "pip", "install", "--no-config", "--python", str(python_venvu(kat)), "--no-deps",
                "--require-hashes", "--only-binary", ":all:", "--compile-bytecode"]
        if wpis.get("torch_backend"):
            argv += ["--torch-backend", str(wpis["torch_backend"])]
        _uruchom([*argv, "-r", str(lock)], env=env, cwd=u.stan, log=log)
        if not python_venvu(kat).is_file():
            raise BladVenvu(f"venv {nazwa}: uv skończył bez błędu, ale nie ma {python_venvu(kat)}")
        przenosne.zapisz_atomowo(kat / ZNACZNIK, json.dumps({
            "nazwa": nazwa, "lock": wpis["lock"], "lock_sha256": wpis["sha256"], "python_bazowy": str(python),
            "torch_backend": wpis.get("torch_backend"), "paczek": wpis.get("paczek")}, ensure_ascii=False,
            indent=2) + "\n")
    log(f"venv {nazwa}: gotowy ({kat})")
    return wpis_spisu(nazwa, wpis, kat), True


def sprawdz(py: Path, kod: str = "import sys; print(sys.version.split()[0])", czas: float = 120) -> str:
    """Krótka próba interpretera venvu (doctor): wyjście albo pusty napis przy błędzie."""
    try:
        w = subprocess.run([str(py), "-I", "-c", kod], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=czas, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return ""
    return w.stdout.strip() if w.returncode == 0 else ""


if __name__ == "__main__":                                   # pragma: no cover - moduł biblioteki
    sys.exit("jarvo/venvy.py to moduł instalatora (jarvo instaluj)")
