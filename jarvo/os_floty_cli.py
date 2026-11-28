"""`jarvo flota os`: oś zadań floty z `<dane>/jarvo/state/os-floty.db` (docs/HQ.md „Oś floty”), tylko do odczytu.

Agent widzi jednym poleceniem, co dziś (albo w podanym dniu) zlecono flocie, kto pracuje teraz i które urządzenia są
zajęte; `--pelne <id>` daje pełny prompt i wynik jednego wpisu. Bazę zbiera panel (silnik HQ), CLI jej nie zmienia.
Odczyt i kolejność z hq/plugin/os_floty.py (jedna definicja dla panelu i CLI).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

from .sciezki import Uklad

_REPO = Path(__file__).resolve().parents[1]
STANY = {"w_toku": "w toku", "pytanie": "pytanie", "gotowe": "gotowe", "przerwane": "przerwane", "blad": "błąd"}


def _os_floty():
    """hq/plugin/os_floty.py (jak sesje_omp._modul_hq: wtyczka HQ jest bez pakietu jarvo)."""
    nazwa = "jarvo_os_floty"
    if nazwa not in sys.modules:
        spec = importlib.util.spec_from_file_location(nazwa, _REPO / "hq" / "plugin" / "os_floty.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[nazwa] = mod
        spec.loader.exec_module(mod)
    return sys.modules[nazwa]


def plik_bazy(u: Uklad) -> Path:
    return u.jarvo_dane / "state" / "os-floty.db"


def _godz(ts) -> str:
    return time.strftime("%H:%M", time.localtime(float(ts))) if ts else ""


def _data(ts) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts))) if ts else "-"


def linia(z: dict) -> str:
    """Jedna linia skrótu: czas, stan, agent ← zlecił (kanał), tytuł, zasoby, id do --pelne."""
    czas = f"{_godz(z.get('start_at'))}-{_godz(z.get('koniec_at'))}"
    zasoby = f" [{', '.join(z['zasoby'])}]" if z.get("zasoby") else ""
    return (f"{czas:<11} {STANY.get(z['stan'], z['stan']):<9} {z['agent']} ← {z['zlecil']} ({z['kanal']})  "
            f"{z['tytul']}{zasoby}  #{z['id']}")


def tekst_dnia(d: dict) -> str:
    otwarte = [z for z in d["zadania"] if z["stan"] in ("w_toku", "pytanie")]
    reszta = [z for z in d["zadania"] if z["stan"] not in ("w_toku", "pytanie")]
    w = [f"Oś floty {d['dzien']}: {len(d['zadania'])} zadań"
         + (f" (dni z wpisami: {', '.join(d['dni'][:7])}{', …' if len(d['dni']) > 7 else ''})" if d["dni"] else "")]
    if otwarte:
        w += ["", "Teraz (w toku i pytania):"] + [linia(z) for z in otwarte]
    if reszta:
        w += ["", "Skończone tego dnia (od najnowszego):"] + [linia(z) for z in reszta]
    if not d["zadania"]:
        w.append("(brak wpisów; oś zbiera panel, gdy działa: jarvo up)")
    w += ["", "Pełny wpis: jarvo flota os --pelne <id>"]
    return "\n".join(w)


def tekst_wpisu(z: dict) -> str:
    w = [f"{z['id']}  {z['tytul']}",
         f"rodzaj {z['rodzaj']} · agent {z['agent']} · zlecił {z['zlecil']} · kanał {z['kanal']} · "
         f"stan {STANY.get(z['stan'], z['stan'])}",
         f"start {_data(z.get('start_at'))} · koniec {_data(z.get('koniec_at'))}"
         + (f" · wywołania {z['wywolania']}" if z.get("wywolania") is not None else "")]
    if z.get("zasoby"):
        w.append("zasoby: " + ", ".join(z["zasoby"]))
    if z.get("rodzic") or z.get("watek_id"):
        w.append(" · ".join(x for x in (f"rodzic {z['rodzic']}" if z.get("rodzic") else "",
                                         f"wątek {z['watek_id']}" if z.get("watek_id") else "") if x))
    w += ["", "Prompt:", z.get("prompt") or "(brak)", "", "Wynik:", z.get("wynik_pelny") or z.get("wynik") or "(brak)"]
    return "\n".join(w)


def polecenie_flota(u: Uklad, a, _reszta, _ot) -> int:
    if getattr(a, "flota_polecenie", None) != "os":
        print("Użycie: jarvo flota os [--dzien RRRR-MM-DD] [--agent a] [--pelne <id>] [--json]")
        return 2
    m = _os_floty()
    plik = plik_bazy(u)
    if a.pelne:
        z = m.wpis(plik, a.pelne)
        if z is None:
            print(f"Nie ma zadania {a.pelne} na osi floty.", file=sys.stderr)
            return 1
        print(json.dumps({"zadanie": z}, ensure_ascii=False, indent=1) if a.json else tekst_wpisu(z))
        return 0
    if a.dzien and not m.DZIEN_RE.match(a.dzien):
        print("Dzień podaj jako RRRR-MM-DD.", file=sys.stderr)
        return 2
    d = m.lista(plik, a.dzien or None, a.agent or None)
    print(json.dumps(d, ensure_ascii=False, indent=1) if a.json else tekst_dnia(d))
    return 0


def dodaj_polecenia(sub) -> None:
    s = sub.add_parser("flota", help="flota: oś zadań (flota os), tylko odczyt",
                       description="`jarvo flota os`: co zlecono flocie danego dnia, kto pracuje teraz i które "
                       "urządzenia są zajęte (baza zbierana przez panel).")
    fs = s.add_subparsers(dest="flota_polecenie", metavar="os")
    o = fs.add_parser("os", help="oś zadań floty: dzień (domyślnie dziś) albo pełny wpis",
                      description="Skrót dnia: w toku i pytania na górze, potem skończone od najnowszego. "
                      "Każda linia kończy się id do --pelne.")
    o.add_argument("--dzien", metavar="RRRR-MM-DD", help="dzień (domyślnie dziś, strefa tego komputera)")
    o.add_argument("--agent", metavar="AGENT", help="tylko zadania jednego agenta (profil albo klucz sesji omp)")
    o.add_argument("--pelne", metavar="ID", help="pełny wpis: prompt i wynik")
    o.add_argument("--json", action="store_true", help="wynik w JSON")
    s.set_defaults(funkcja=polecenie_flota)
