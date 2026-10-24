"""Budowa modelu build123d i eksport. Uruchamia go cad.py w venvie CAD (nie Ty):

    /opt/jarvo/venvs/cad/bin/python -I cad_model.py <zadanie.json>     → raport JSON w ostatniej linii stdout

Zadanie: {"model": "model.py", "out": "katalog", "nazwa": "czesc", "formaty": ["step", "stl", "glb", "3mf"],
          "dokladnosc": 0.05, "katowa": 0.2, "gestosc": 1.24}
Skrypt modelu to zwykły kod build123d, który na końcu przypisuje gotowy kształt do zmiennej `wynik`
(Part, Solid albo Compound; kilka części: lista albo Compound z nazwanymi częściami). Wymiary w milimetrach.
Bez sieci: gniazda są zablokowane, a export_to_pcbway (wysyłka pliku do PCBWay) zgłasza błąd.
"""

from __future__ import annotations

import json
import math
import re
import runpy
import socket
import sys
import time
from pathlib import Path


class BezSieci(PermissionError):
    pass


def _odmow(*_a, **_k):
    raise BezSieci("warsztat 3D działa bez sieci (model nie łączy się z internetem)")


def zablokuj_siec() -> None:
    socket.socket.connect = _odmow          # type: ignore[method-assign]
    socket.socket.connect_ex = _odmow       # type: ignore[method-assign]
    socket.create_connection = _odmow       # type: ignore[assignment]
    socket.getaddrinfo = _odmow             # type: ignore[assignment]


def _r(x: float, n: int = 2) -> float:
    return round(float(x), n)


def raport_ksztaltu(bd, ksztalt, gestosc: float) -> dict:
    bb = ksztalt.bounding_box()
    bryly = ksztalt.solids()
    objetosc = ksztalt.volume
    poprawne = bool(ksztalt.is_valid)
    r = {
        "wymiary_mm": [_r(bb.size.X), _r(bb.size.Y), _r(bb.size.Z)],
        "min_mm": [_r(bb.min.X), _r(bb.min.Y), _r(bb.min.Z)],
        "max_mm": [_r(bb.max.X), _r(bb.max.Y), _r(bb.max.Z)],
        "objetosc_mm3": _r(objetosc, 1),
        "pole_mm2": _r(ksztalt.area, 1),
        "bryly": len(bryly),
        "sciany": len(ksztalt.faces()),
        "krawedzie": len(ksztalt.edges()),
        "poprawny": poprawne,
        "masa_g": _r(objetosc / 1000 * gestosc, 1),
        "gestosc_g_cm3": gestosc,
    }
    if bryly:
        c = ksztalt.center(bd.CenterOf.MASS) if len(bryly) == 1 else ksztalt.center()
        r["srodek_masy_mm"] = [_r(c.X), _r(c.Y), _r(c.Z)]
    return r


def czesci(ksztalt) -> list:
    """Części zestawu: dzieci Compound (lista w `wynik` albo Compound(children=[…]) z nazwami w .label)."""
    dzieci = list(getattr(ksztalt, "children", ()) or ())
    return dzieci if len(dzieci) > 1 else []


def nazwy_czesci(cz: list) -> list[str]:
    """Nazwy do plików z .label części (bez polskich liter i spacji); bez nazwy albo powtórzona → numer."""
    nazwy = [re.sub(r"[^A-Za-z0-9_-]+", "-", str(getattr(c, "label", "") or "")).strip("-")[:40] or f"czesc{i + 1}"
             for i, c in enumerate(cz)]
    if len(set(nazwy)) < len(nazwy):
        nazwy = [f"{n}-{i + 1}" for i, n in enumerate(nazwy)]
    return nazwy


def uwagi(r: dict) -> tuple[list[str], list[str]]:
    bledy, ostrzezenia = [], []
    if not r["poprawny"]:
        bledy.append("kształt niepoprawny (BRepCheck): popraw model, zanim pójdzie do druku albo klienta")
    if r["bryly"] == 0:
        bledy.append("brak bryły (same powierzchnie albo szkic): do druku i STL potrzebna bryła")
    elif r["objetosc_mm3"] <= 0:
        bledy.append("objętość ≤ 0: bryła odwrócona albo pusta")
    if r["bryly"] > 1 and not r.get("czesci"):
        ostrzezenia.append(f"{r['bryly']} osobne bryły: przy jednej części to zwykle zapomniane połączenie (fuzja +)")
    najw = max(r["wymiary_mm"])
    if r["bryly"] and najw < 0.5:
        ostrzezenia.append(f"największy wymiar {najw} mm: czy model jest w milimetrach?")
    if najw > 5000:
        ostrzezenia.append(f"największy wymiar {najw} mm (> 5 m): czy model jest w milimetrach?")
    return bledy, ostrzezenia


def ksztalt_wyniku(bd, wynik):
    if wynik is None:
        raise ValueError("skrypt modelu nie ustawił zmiennej `wynik` (na końcu: wynik = czesc.part)")
    if isinstance(wynik, (bd.BuildPart, bd.BuildSketch, bd.BuildLine)):
        wynik = wynik.part if isinstance(wynik, bd.BuildPart) else (
            wynik.sketch if isinstance(wynik, bd.BuildSketch) else wynik.line)
    if isinstance(wynik, (list, tuple)):
        if not wynik:
            raise ValueError("`wynik` to pusta lista")
        wynik = bd.Compound(children=[ksztalt_wyniku(bd, w) for w in wynik])
    if not isinstance(wynik, bd.Shape):
        raise ValueError(f"`wynik` ma typ {type(wynik).__name__}, a ma być kształtem build123d (Part, Solid, Compound)")
    return wynik


def eksportuj(bd, ksztalt, out: Path, nazwa: str, formaty: list[str], dokl: float, katowa: float) -> dict:
    pliki = {}
    for f in formaty:
        p = out / f"{nazwa}.{f}"
        if f == "step":
            bd.export_step(ksztalt, p)
        elif f == "stl":
            bd.export_stl(ksztalt, p, tolerance=dokl, angular_tolerance=katowa)
        elif f == "glb":
            bd.export_gltf(ksztalt, str(p), binary=True, linear_deflection=dokl, angular_deflection=katowa)
        elif f == "3mf":
            m = bd.Mesher()
            m.add_shape(ksztalt, linear_deflection=dokl, angular_deflection=katowa)
            m.write(str(p))
        else:
            raise ValueError(f"nieznany format {f}")
        pliki[f] = {"plik": p.as_posix(), "bajty": p.stat().st_size}
    if "stl" in pliki:
        pliki["stl"]["trojkaty"] = max(0, (pliki["stl"]["bajty"] - 84) // 50)   # STL binarny: 84 B nagłówka + 50 B/trójkąt
        # zestaw: każda część także osobno (do druku część idzie sama, ułożona przez slicer)
        cz = czesci(ksztalt)
        for c, n in zip(cz, nazwy_czesci(cz)):
            p = out / f"{nazwa}-{n}.stl"
            bd.export_stl(c, p, tolerance=dokl, angular_tolerance=katowa)
            pliki[f"stl:{n}"] = {"plik": p.as_posix(), "bajty": p.stat().st_size}
    return pliki


def main(argv: list[str]) -> int:
    z = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    model, out = Path(z["model"]).resolve(), Path(z["out"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    zablokuj_siec()
    t0 = time.monotonic()
    import build123d as bd
    bd.export_to_pcbway = _odmow
    t1 = time.monotonic()
    sys.path.insert(0, str(model.parent))               # moduły pomocnicze obok skryptu modelu
    sys.argv = [str(model)]
    wynik = {"model": model.as_posix(), "bledy": [], "ostrzezenia": []}   # ścieżki w raporcie z „/” (też Windows)
    try:
        g = runpy.run_path(str(model), run_name="__main__")
        ksztalt = ksztalt_wyniku(bd, g.get("wynik"))
        t2 = time.monotonic()
        wynik.update(raport_ksztaltu(bd, ksztalt, z.get("gestosc", 1.24)))
        if cz := czesci(ksztalt):
            pola = ("wymiary_mm", "objetosc_mm3", "masa_g", "bryly", "poprawny")
            wynik["czesci"] = [{"nazwa": n, **{k: v for k, v in raport_ksztaltu(bd, c, z.get("gestosc", 1.24)).items()
                                              if k in pola}} for c, n in zip(cz, nazwy_czesci(cz))]
        wynik["bledy"], wynik["ostrzezenia"] = uwagi(wynik)
        if not wynik["bledy"] or z.get("mimo_bledow"):
            wynik["pliki"] = eksportuj(bd, ksztalt, out, z["nazwa"], z["formaty"], z.get("dokladnosc", 0.05),
                                       z.get("katowa", 0.2))
        wynik["czas_s"] = {"import": _r(t1 - t0), "model": _r(t2 - t1), "eksport": _r(time.monotonic() - t2)}
    except BezSieci as e:
        wynik["bledy"].append(str(e))
    except Exception as e:  # noqa: BLE001 - błąd skryptu modelu wraca do agenta jako raport
        import traceback
        ramki = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == str(model)]
        gdzie = f" (linia {ramki[-1].lineno}: {ramki[-1].line})" if ramki else ""
        wynik["bledy"].append(f"{type(e).__name__}: {e}{gdzie}")
    for k in ("objetosc_mm3", "pole_mm2"):
        if isinstance(wynik.get(k), float) and not math.isfinite(wynik[k]):
            wynik[k] = None
    print(json.dumps(wynik, ensure_ascii=False))
    return 1 if wynik["bledy"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
