"""Instalacja przy pierwszym użyciu (docs/NATYWNIE.md: c3 pkt 9, etap E11: E11, E13, M04, U05).

Instalator bierze z manifestu (vendor/natywne.lock.json) tylko wpisy `kiedy: instalacja`. Wpisy `kiedy: przy-uzyciu`
instaluje program, który ich potrzebuje, w chwili pierwszego użycia, tą samą drogą co instalator:

  narzędzie  plik z manifestu przez jarvo/pobieracz.py (suma sha256 przed rozpakowaniem, katalog wersji, pasek na
             stderr) do `<program>/narzedzia/<nazwa>/<wersja>`: platform-tools i scrcpy (`jarvo android`, po
             akceptacji licencji Google), three (podgląd warsztatu 3D bez Node.js),
  venv       lock z sumami przez jarvo/venvy.py (uv i Python z instalacji, --require-hashes) do
             `<program>/venvs/<nazwa>-<12 znaków sumy locka>`: cad (warsztat 3D), manimgx (Wideograf).

Wynik trafia do `<stan>/narzedzia.json` (ten sam wpis co z instalatora: wersja, katalog, bin, env; venv także python)
pod blokadą i zapisem atomowym, w tym samym formacie co instalator, a `<stan>/srodowisko.json` dostaje jego zmienne
tak, jak zapisałby je instalator: następny przebieg instalacji niczego tu nie zmienia (zachowuje te wpisy, bo czyta
narzedzia.json i dokłada swoje). Procesy Jarva uruchomione później mają te programy w PATH i ich zmienne (np.
JARVO_CAD_PYTHON, ADB_MDNS); procesy, które już działają (brama i panel), dostają je dopiero po restarcie, dlatego
programy floty pytają o narzędzie tym modułem (`gotowe_narzedzie`, `gotowy_venv`), a nie tylko o zmienną.

Wołają go procesy Jarva i floty (`jarvo android`, cad.py w terminalu agenta, manimgx): korzeń z JARVO_ROOT albo
domyślny (jarvo/sciezki.py), kod aktywnej wersji z `<program>/current.json`. Bez instalacji natywnej (kontener:
narzędzia są w obrazie) `natywnie()` daje False i nic nie instalujemy. Sama biblioteka standardowa.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable

from . import manifest, pobieracz, przenosne, sciezki, srodowisko, venvy
from .sciezki import WINDOWS, Uklad

SPIS = "narzedzia.json"
ZAMEK_SPISU = "narzedzia.lock"          # zapis wpisu w <stan>/narzedzia.json (odczyt, zmiana, zapis atomowy)
ZAMEK = "przy-uzyciu.lock"              # jedno pobieranie narzędzia naraz (dwa terminale agentów przy pierwszym użyciu)
APP = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # bez resolve(): krótka nazwa 8.3 (c1)


class BladPrzyUzyciu(RuntimeError):
    """Narzędzia albo venvu nie da się zainstalować (komunikat po polsku z radą, bez sekretów)."""


def _stderr(tekst: str) -> None:
    print(tekst, file=sys.stderr, flush=True)


def uklad(env: dict | None = None) -> Uklad:
    """Układ katalogów instalacji: JARVO_ROOT z otoczenia (procesy Jarva i floty go mają) albo domyślny korzeń."""
    return sciezki.uklad(env)


def natywnie(u: Uklad) -> bool:
    """Czy to instalacja natywna (jest `<program>/current.json`), a nie kontener albo kopia repo bez instalacji."""
    return (u.program / "current.json").is_file()


def app_instalacji(u: Uklad) -> Path:
    """Kod aktywnej wersji Jarva (manifest i locki venvów), a bez current.json katalog tego modułu."""
    a = srodowisko.biezace(u).get("app")
    return Path(a) if a else APP


def _json(dane: dict) -> str:
    return json.dumps(dane, ensure_ascii=False, indent=2, sort_keys=True) + "\n"   # jak instalator._json


def wpis(u: Uklad, klucz: str) -> dict | None:
    w = srodowisko.narzedzia(u).get(klucz)
    return w if isinstance(w, dict) else None


def zapisz_wpis(u: Uklad, klucz: str, nowy: dict) -> bool:
    """Wpis `klucz` w `<stan>/narzedzia.json` (reszta pliku bez zmian), potem `<stan>/srodowisko.json` z jego
    zmiennymi, tak jak zapisałby go instalator. True = plik się zmienił."""
    with przenosne.Zamek(u.stan / ZAMEK_SPISU):
        dane = srodowisko.narzedzia(u)
        if dane.get(klucz) == nowy:
            return False
        dane[klucz] = nowy
        przenosne.zapisz_atomowo(u.stan / SPIS, _json(dane))
        odswiez_srodowisko(u, dane)
    return True


def odswiez_srodowisko(u: Uklad, narz: dict | None = None) -> bool:
    """`<stan>/srodowisko.json` (programy uruchamiane poza procesami Jarva biorą z niego brakujące zmienne) z nowym
    wpisem: ta sama treść, którą zapisałby krok „Środowisko procesów” instalatora (baza = ustawienia instalacji),
    więc następny przebieg instalacji niczego tu nie zmienia. Bez pliku (instalacja niedokończona) nic nie robimy."""
    cel = u.stan / "srodowisko.json"
    if not cel.is_file():
        return False
    from .instalator import USTAWIENIA
    ust = {k: str(v).strip() for k, v in srodowisko.wczytaj_json(u.stan / "ustawienia.json").items()
           if k in USTAWIENIA and str(v or "").strip()}
    narz = srodowisko.narzedzia(u) if narz is None else narz
    przed = cel.read_bytes()
    srodowisko.zapisz(u, srodowisko.srodowisko(u, dict(ust), narz=narz), narz=narz)
    return cel.read_bytes() != przed


def program_narzedzia(wpis_narzedzia: dict | None, nazwa: str) -> Path | None:
    """Program z katalogów `bin` wpisu (Windows: .exe), np. adb z platform-tools, scrcpy, uv."""
    if not isinstance(wpis_narzedzia, dict):
        return None
    katalogi = list(wpis_narzedzia.get("bin") or []) or [wpis_narzedzia.get("katalog") or ""]
    for k in katalogi:
        p = Path(str(k)) / (f"{nazwa}.exe" if WINDOWS else nazwa)
        if str(k) and p.is_file():
            return p
    return None


def python_narzedzia(wpis_narzedzia: dict | None) -> Path | None:
    """python.exe (Windows) albo bin/python3 z wpisu Pythona z manifestu (python312, python313)."""
    if not isinstance(wpis_narzedzia, dict) or not wpis_narzedzia.get("katalog"):
        return None
    k = Path(str(wpis_narzedzia["katalog"]))
    p = k / "python.exe" if WINDOWS else k / "bin" / "python3"
    return p if p.is_file() else None


# ---------------------------------------------------------------- narzędzia z manifestu

def _plik(app: Path, nazwa: str, platforma: str | None) -> tuple[str, dict]:
    """(wersja, wpis pliku dla platformy) albo BladPrzyUzyciu z powodem z manifestu (`brak: …`)."""
    try:
        narz = manifest.wczytaj(app)
    except (OSError, ValueError, KeyError) as e:
        raise BladPrzyUzyciu(f"manifest narzędzi {Path(app) / manifest.LOCK} jest nieczytelny ({e}): uruchom "
                             "instalację Jarva jeszcze raz") from None
    if nazwa not in narz:
        raise BladPrzyUzyciu(f"{nazwa}: nie ma go w manifeście tej wersji Jarva ({Path(app) / manifest.LOCK})")
    try:
        plik = manifest.plik(narz, nazwa, platforma or sciezki.platforma())
    except manifest.BrakNarzedzia as e:
        raise BladPrzyUzyciu(str(e)) from None
    return manifest.wersja(narz, nazwa), plik


def _spis_narzedzia(wersja: str, plik: dict, katalog: Path) -> dict:
    """Wpis jak instalator._Instalacja.narzedzie: wersja, katalog, bin, env ({katalog} rozwinięty)."""
    return {"wersja": wersja, "katalog": str(katalog),
            "bin": [str(katalog / b) for b in plik.get("bin") or []],
            "env": {str(k): str(v).replace("{katalog}", str(katalog)) for k, v in (plik.get("env") or {}).items()}}


def _gotowy_katalog(katalog: Path, plik: dict) -> bool:
    try:
        return (katalog / ".jarvo-suma").read_text(encoding="utf-8").strip() == plik["sha256"]
    except OSError:
        return False


def rozmiar_mb(app: Path, nazwa: str, platforma: str | None = None) -> float | None:
    """Ile MB pobierze narzędzie (rozmiar pliku z manifestu) albo None."""
    try:
        return round(int(_plik(app, nazwa, platforma)[1].get("rozmiar") or 0) / 1e6, 1) or None
    except BladPrzyUzyciu:
        return None


def gotowe_narzedzie(u: Uklad, nazwa: str, *, app: Path | None = None, platforma: str | None = None) -> dict | None:
    """Wpis narzędzia, gdy jest na dysku w wersji z manifestu (bez sieci i bez zapisu), inaczej None."""
    app = Path(app) if app else app_instalacji(u)
    try:
        wersja, plik = _plik(app, nazwa, platforma)
    except BladPrzyUzyciu:
        return None
    katalog = u.program / "narzedzia" / nazwa / pobieracz.katalog_wersji(wersja)
    return _spis_narzedzia(wersja, plik, katalog) if _gotowy_katalog(katalog, plik) else None


def narzedzie(u: Uklad, nazwa: str, *, app: Path | None = None, platforma: str | None = None,
              log: Callable[[str], None] = _stderr, pasek: bool = True) -> dict:
    """Narzędzie `nazwa` z manifestu: gotowe zostaje (bez sieci), inaczej pobranie z sumą i wpis w narzedzia.json.
    Zwraca wpis (wersja, katalog, bin, env). BladPrzyUzyciu, gdy manifest go nie ma albo pobranie się nie uda."""
    if not natywnie(u):
        raise BladPrzyUzyciu(f"{nazwa}: brak instalacji natywnej Jarva w {u.root} (instalacja przy pierwszym użyciu "
                             "działa tylko w niej)")
    app = Path(app) if app else app_instalacji(u)
    wersja, plik = _plik(app, nazwa, platforma)
    katalog = u.program / "narzedzia" / nazwa / pobieracz.katalog_wersji(wersja)
    spis = _spis_narzedzia(wersja, plik, katalog)
    if _gotowy_katalog(katalog, plik):
        if wpis(u, nazwa) != spis:
            zapisz_wpis(u, nazwa, spis)
        return spis
    with przenosne.Zamek(u.stan / ZAMEK):
        if not _gotowy_katalog(katalog, plik):          # drugi proces mógł skończyć, gdy czekaliśmy
            log(f"{nazwa} {wersja}: pierwsze użycie, pobieram z sumą z manifestu "
                f"({round(int(plik.get('rozmiar') or 0) / 1e6, 1)} MB)")
            try:
                pobieracz.zainstaluj(nazwa, wersja, plik, u.program / "narzedzia", u.cache / "pobrane", pasek=pasek,
                                     wyjscie=sys.stderr)
            except pobieracz.BladPobierania as e:
                raise BladPrzyUzyciu(f"{str(e).rstrip('.')}. Przy błędzie sieci spróbuj jeszcze raz (pobieranie "
                                     "wznowi się); inna suma albo uszkodzone archiwum to sprawa do zgłoszenia, "
                                     "nie do obejścia.") from None
            except OSError as e:
                raise BladPrzyUzyciu(f"{nazwa}: instalacja w {katalog} się nie udała ({e.strerror or e})") from None
        zapisz_wpis(u, nazwa, spis)
    log(f"{nazwa} {wersja}: gotowe ({katalog})")
    return spis


# ---------------------------------------------------------------- venvy z locków

def _wpis_venvu(app: Path, nazwa: str) -> dict:
    try:
        w = manifest.venvy(app).get(nazwa)
    except (OSError, ValueError) as e:
        raise BladPrzyUzyciu(f"manifest narzędzi {Path(app) / manifest.LOCK} jest nieczytelny ({e})") from None
    if not isinstance(w, dict):
        raise BladPrzyUzyciu(f"venv {nazwa}: nie ma go w manifeście tej wersji Jarva ({Path(app) / manifest.LOCK})")
    return w


def _programy_venvu(u: Uklad, w: dict, nazwa: str) -> tuple[Path, Path]:
    narz = srodowisko.narzedzia(u)
    py_nazwa = str(w.get("python") or "python312")
    uv = program_narzedzia(narz.get("uv"), "uv")
    py = python_narzedzia(narz.get(py_nazwa))
    if uv is None or py is None:
        brak = " i ".join(n for n, p in (("uv", uv), (py_nazwa, py)) if p is None)
        raise BladPrzyUzyciu(f"venv {nazwa} potrzebuje {brak} z instalacji Jarva, a nie ma ich w "
                             f"{u.stan / SPIS}: uruchom instalację jeszcze raz")
    return uv, py


def gotowy_venv(u: Uklad, nazwa: str, *, app: Path | None = None) -> dict | None:
    """Wpis venvu `nazwa`, gdy jest gotowy dla locka z manifestu tej wersji (znacznik venvu), inaczej None."""
    app = Path(app) if app else app_instalacji(u)
    try:
        w = _wpis_venvu(app, nazwa)
        _uv, py = _programy_venvu(u, w, nazwa)
    except BladPrzyUzyciu:
        return None
    kat = venvy.katalog(u, nazwa, w)
    return venvy.wpis_spisu(nazwa, w, kat) if venvy.gotowy(kat, w, py) else None


def opis_venvu(u: Uklad, nazwa: str, *, app: Path | None = None, platforma: str | None = None) -> dict:
    """Co zainstaluje pierwsze użycie: {"venv", "python", "pobranie_mb", "venv_mb", "paczek"} (bez sieci)."""
    app = Path(app) if app else app_instalacji(u)
    w = _wpis_venvu(app, nazwa)
    platforma = platforma or sciezki.platforma()
    return {"venv": nazwa, "python": w.get("python"), "pobranie_mb": (w.get("pobranie_mb") or {}).get(platforma),
            "venv_mb": w.get("venv_mb"), "paczek": w.get("paczek")}


def venv(u: Uklad, nazwa: str, *, app: Path | None = None, log: Callable[[str], None] = _stderr) -> dict:
    """Venv `nazwa` z locka manifestu: gotowy zostaje (bez uv i bez sieci), inaczej instalacja przez jarvo/venvy.py
    z wyjściem uv w `log` i wpis `venv-<nazwa>` w narzedzia.json. Zwraca wpis (katalog, python, env)."""
    if not natywnie(u):
        raise BladPrzyUzyciu(f"venv {nazwa}: brak instalacji natywnej Jarva w {u.root}")
    app = Path(app) if app else app_instalacji(u)
    w = _wpis_venvu(app, nazwa)
    uv, py = _programy_venvu(u, w, nazwa)
    kat = venvy.katalog(u, nazwa, w)
    if not venvy.gotowy(kat, w, py):
        o = opis_venvu(u, nazwa, app=app)
        log(f"venv {nazwa}: pierwsze użycie, instaluję z locka z sumami ({o['paczek'] or '?'} paczek, ok. "
            f"{o['pobranie_mb'] or '?'} MB pobrania, ok. {o['venv_mb'] or '?'} MB na dysku; zwykle 1–3 min)")
    try:
        spis, _zmiana = venvy.zainstaluj(u, app, nazwa, w, uv=uv, python=py, log=log)
    except venvy.BladVenvu as e:
        raise BladPrzyUzyciu(str(e)) from None
    zapisz_wpis(u, f"venv-{nazwa}", spis)
    return spis


if __name__ == "__main__":                                   # pragma: no cover - moduł biblioteki
    sys.exit("jarvo/przy_uzyciu.py to moduł Jarva (jarvo android, cad.py, manimgx)")
