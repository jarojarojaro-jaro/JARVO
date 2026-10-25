"""Sprawdzenie `jarvo doctor` dla wtyczki zgód (docs/NATYWNIE.md, sekcja (d) i ryzyko Z39).

Bez kontenera zgody są główną ochroną, więc każdy profil, który obsługuje brama Jarva (host i profile w
`<dane>/profiles`), ma mieć jarvo-zgody: włączoną w `plugins.enabled` swojego config.yaml i leżącą w swoim
`plugins/jarvo-zgody`. Hermes trzyma menedżera wtyczek osobno dla każdego katalogu profilu i wypełnia go, gdy
działająca brama zobaczy profil, więc wtyczka dodana później działa w bramie dopiero po jej restarcie (do tego czasu
zapisy w tym profilu idą bez pytania). Config czyta Python Hermesa (PyYAML), jednym procesem dla wszystkich profili.

Wynik: profil floty albo host bez wtyczki = blad (instalacja dodaje ją każdemu profilowi floty), inny profil bez
wtyczki = uwaga, wtyczka nowsza niż start działającej bramy = uwaga z radą `jarvo serwis --restart brama`.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Callable

from . import flota, instalator, nadzorca, srodowisko
from .sciezki import Uklad

NAZWA = "jarvo-zgody"
SPRAWDZENIE = "zgody w profilach"
# Python Hermesa: dla hosta i każdego profilu z config.yaml {profil, wlaczona, jest, wtyczka_od, blad}; wtyczka_od =
# czas powstania dowiązania wtyczki (profile floty mają dowiązanie do <dane>/plugins, a jego mtime to chwila dodania).
# Kopia katalogu (host) nie mówi, kiedy doszła: mtime katalogu wtyczki zmienia import (__pycache__), a mtime plugins/
# podmiana innej wtyczki (np. samego panelu bez restartu bramy); CI natywnie: fałszywe uwagi dla hosta. Bez configu.
SKRYPT = r"""
import json, os, sys
from pathlib import Path
import yaml
dane, nazwa = Path(sys.argv[1]), sys.argv[2]
domy = [("host", dane)] + sorted((p.name, p) for p in (dane / "profiles").glob("*") if (p / "config.yaml").is_file())
wynik = []
for imie, dom in domy:
    wl, blad = [], None
    try:
        cfg = yaml.safe_load((dom / "config.yaml").read_text(encoding="utf-8")) or {}
        wl = (cfg.get("plugins") or {}).get("enabled") or [] if isinstance(cfg, dict) else []
    except Exception as e:
        blad = type(e).__name__
    wt = dom / "plugins" / nazwa
    lacze = os.path.islink(wt) or getattr(os.path, "isjunction", lambda _p: False)(wt)   # Windows: junction
    od = os.lstat(wt).st_mtime if lacze else None
    wynik.append({"profil": imie, "wlaczona": isinstance(wl, list) and nazwa in [str(x) for x in wl],
                  "jest": (wt / "plugin.yaml").is_file(), "wtyczka_od": od, "blad": blad})
print(json.dumps(wynik))
"""


def _wynik(stan: str, opis: str, rada: str = "") -> dict:
    return {"nazwa": SPRAWDZENIE, "stan": stan, "opis": opis, "rada": rada}


def _python_hermesa(u: Uklad) -> Path | None:
    c = srodowisko.biezace(u).get("hermes")
    p = srodowisko.hermes_python(Path(c)) if c else None
    return p if p and p.is_file() else None


def start_bramy(u: Uklad) -> float | None:
    """Kiedy wystartowała działająca brama (epoka, z `<stan>/nadzorca.json`); None, gdy brama nie działa."""
    stan = nadzorca.stan_z_pliku(u)
    brama = (stan.get("uslugi") or {}).get("brama") or {}
    if not stan.get("dziala") or brama.get("stan") != "dziala" or not brama.get("od"):
        return None
    try:
        return dt.datetime.fromisoformat(str(brama["od"])).timestamp()
    except ValueError:
        return None


def profile(u: Uklad, uruchom: Callable | None = None) -> list[dict] | str:
    """Stan wtyczki w hoście i każdym profilu (lista) albo opis, czemu nie dało się sprawdzić (napis)."""
    python = _python_hermesa(u)
    if python is None:
        return "brak środowiska Hermesa"
    try:
        r = (uruchom or instalator._uruchom)([python, "-I", "-X", "utf8", "-c", SKRYPT, str(u.dane), NAZWA])
        wynik = json.loads((r.stdout or "").strip() or "null")
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return f"Python Hermesa: {type(e).__name__}"
    return wynik if isinstance(wynik, list) else "Python Hermesa nie odpowiedział"


def sprawdzenie(u: Uklad, *, uruchom: Callable | None = None, flota_agenci: list[str] | None = None,
                start: float | None = ...) -> dict:
    """Jeden wiersz doctora: wtyczka zgód w każdym profilu i w hoście, widziana przez działającą bramę."""
    if not (u.dane / "config.yaml").is_file():
        return _wynik("uwaga", "nie sprawdzone (brak <dane>/config.yaml: Jarvo nie jest zainstalowane)")
    stan = profile(u, uruchom)
    if isinstance(stan, str):
        return _wynik("uwaga", f"nie sprawdzone ({stan})", "Uruchom instalację ponownie.")
    floty = set(flota.agenci_buildu(u) if flota_agenci is None else flota_agenci) | {"host"}
    start = start_bramy(u) if start is ... else start
    bez_floty, bez_innych, po_starcie = [], [], []
    for p in stan:
        if not isinstance(p, dict):
            continue
        imie = str(p.get("profil"))
        if not (p.get("wlaczona") and p.get("jest")):
            (bez_floty if imie in floty else bez_innych).append(imie)
        elif start is not None and isinstance(p.get("wtyczka_od"), (int, float)) and p["wtyczka_od"] > start + 1:
            po_starcie.append(imie)
    if bez_floty:
        return _wynik("blad", f"bez {NAZWA}: {', '.join(bez_floty)} (zapisy plików i polecenia bez pytania)",
                      "Uruchom instalację ponownie: instalator dodaje wtyczkę zgód hostowi i każdemu profilowi floty.")
    if po_starcie:
        return _wynik("uwaga", f"brama nie widzi jeszcze wtyczki zgód w: {', '.join(po_starcie)} (doszła po jej starcie; "
                               "Hermes wczytuje wtyczki profilu raz)", "jarvo serwis --restart brama")
    if bez_innych:
        return _wynik("uwaga", f"profile spoza floty bez {NAZWA}: {', '.join(bez_innych)} (tam zapisy bez pytania)",
                      "Usuń taki profil albo skopiuj do niego wtyczkę z <dane>/plugins i włącz ją w jego config.yaml; "
                      "potem jarvo serwis --restart brama.")
    profili = sum(1 for p in stan if isinstance(p, dict) and p.get("profil") != "host")
    return _wynik("ok", f"host i {profili} profili z {NAZWA}" + ("" if start is None else "; brama je widzi"))
