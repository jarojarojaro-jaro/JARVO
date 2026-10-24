#!/usr/bin/env python3
"""Warsztat 3D floty: model z kodu build123d → STEP, STL, GLB, 3MF + raport, podgląd PNG i film obrotu.

    python3 cad.py zbuduj model.py -o out/ [--nazwa czesc] [--formaty step,stl,glb,3mf] [--dokladnosc 0.05]
                          [--material pla|petg|abs|asa|tpu|nylon|aluminium|stal|drewno | --gestosc 1.24]
                          [--podglad] [--mimo-bledow] [--limit 300] [--json]
    python3 cad.py podglad czesc.glb -o czesc.png [--rozmiar 1600x1200] [--kat 35] [--wysokosc 25] [--kolor "#9AA4B2"]
                           [--tlo "#F4F4F2" | --przezroczyste] [--siatka] [--bez-krawedzi] [--skala 1]
    python3 cad.py obrot czesc.glb -o obrot.mp4 [--sekundy 6] [--fps 30] [--rozmiar 1080x1080] [opcje jak w podglad]
    python3 cad.py stan [--json]

Silnik: build123d (Apache-2.0) na OpenCascade (cadquery-ocp, LGPL-2.1) w osobnym venvie obrazu
(/opt/jarvo/venvs/cad, albo JARVO_CAD_PYTHON); skrypt modelu przypisuje gotowy kształt do zmiennej `wynik`,
wymiary w milimetrach. Budowa idzie bez sieci (cad_model.py blokuje gniazda). Podgląd i film: Three.js (MIT,
/opt/jarvo/node) w Chromium z obrazu Hermesa (cad_render.cjs, WebGL na CPU przez SwiftShader), film sklejany ffmpeg.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL_PY = HERE / "cad_model.py"
RENDER_JS = HERE / "cad_render.cjs"
CAD_PYTHON = "/opt/jarvo/venvs/cad/bin/python"
FORMATY = ("step", "stl", "glb", "3mf")
# gęstość w g/cm³ (masa w raporcie: szacunek dla 100% wypełnienia; wydruk z wypełnieniem 15–20% waży mniej)
MATERIALY = {"pla": 1.24, "petg": 1.27, "abs": 1.04, "asa": 1.07, "tpu": 1.21, "nylon": 1.14,
             "aluminium": 2.70, "stal": 7.85, "drewno": 0.60}
KOLOR = re.compile(r"#[0-9a-fA-F]{6}")


class Blad(Exception):
    pass


def cad_python() -> str:
    for k in (os.environ.get("JARVO_CAD_PYTHON"), CAD_PYTHON):
        if k and Path(k).exists():
            return k
    raise Blad("brak silnika CAD (venv /opt/jarvo/venvs/cad z obrazu Jarva; poza kontenerem: JARVO_CAD_PYTHON)")


def _formaty(s: str) -> list[str]:
    f = [x.strip().lower() for x in s.split(",") if x.strip()]
    zle = [x for x in f if x not in FORMATY]
    if zle or not f:
        raise Blad(f"formaty: {', '.join(zle) or 'pusto'}; dostępne: {', '.join(FORMATY)}")
    return list(dict.fromkeys(f))


def _nazwa(s: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", s) or s.endswith("."):
        raise Blad(f"nazwa {s!r}: litery łacińskie, cyfry, _ . - (bez spacji i ukośników)")
    return s


def _rozmiar(s: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{2,4})x(\d{2,4})", s.strip().lower())
    if not m or not (64 <= int(m.group(1)) <= 4096 and 64 <= int(m.group(2)) <= 4096):
        raise Blad(f"rozmiar {s!r}: SZERxWYS od 64 do 4096, np. 1600x1200")
    return int(m.group(1)), int(m.group(2))


def _kolor(s: str | None, nazwa: str) -> str | None:
    if s is None:
        return None
    if not KOLOR.fullmatch(s):
        raise Blad(f"{nazwa} {s!r}: kolor jako #RRGGBB")
    return s.upper()


def zadanie_modelu(a: argparse.Namespace) -> dict:
    model = Path(a.model)
    if not model.is_file() or model.suffix != ".py":
        raise Blad(f"{model}: potrzebny skrypt modelu .py")
    gestosc = a.gestosc if a.gestosc is not None else MATERIALY[a.material]
    if not 0.05 <= gestosc <= 25:
        raise Blad(f"gęstość {gestosc} g/cm³ poza zakresem 0,05–25")
    if not 0.001 <= a.dokladnosc <= 5:
        raise Blad("dokładność siatki 0,001–5 mm (mniej = gładziej i większy plik)")
    return {"model": str(model.resolve()), "out": str(Path(a.out).resolve()), "nazwa": _nazwa(a.nazwa or model.stem),
            "formaty": _formaty(a.formaty), "dokladnosc": a.dokladnosc, "katowa": 0.2, "gestosc": gestosc,
            "material": a.material if a.gestosc is None else None, "mimo_bledow": a.mimo_bledow}


def _utf8() -> list[str]:
    """Windows: -I pomija PYTHONUTF8, a raport w potoku byłby w stronie kodowej ANSI; -X utf8 trzyma go w UTF-8."""
    return ["-X", "utf8"] if os.name == "nt" else []


def zbuduj(zadanie: dict, limit: int = 300, python: str | None = None) -> dict:
    py = python or cad_python()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(zadanie, f)
    try:
        p = subprocess.run([py, "-I", *_utf8(), str(MODEL_PY), f.name], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=limit, cwd=str(Path(zadanie["model"]).parent))
    except subprocess.TimeoutExpired:
        return {"model": zadanie["model"], "bledy": [f"budowa trwała ponad {limit} s (prostszy model albo --limit)"],
                "ostrzezenia": []}
    finally:
        os.unlink(f.name)
    linie = [x for x in p.stdout.strip().splitlines() if x.startswith("{")]
    if not linie:
        return {"model": zadanie["model"], "bledy": [(p.stderr or p.stdout).strip()[-800:] or "cad_model.py: brak raportu"],
                "ostrzezenia": []}
    r = json.loads(linie[-1])
    if zadanie.get("material"):
        r["material"] = zadanie["material"]
    raport = Path(zadanie["out"]) / f"{zadanie['nazwa']}.json"
    raport.parent.mkdir(parents=True, exist_ok=True)
    raport.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    r["raport"] = raport.as_posix()
    return r


# ---------------------------------------------------------------- podgląd i film (cad_render.cjs)

def opcje_widoku(a: argparse.Namespace) -> dict:
    if a.przezroczyste and a.tlo:
        raise Blad("--tlo albo --przezroczyste, nie oba")
    if not -89 <= a.wysokosc <= 89:
        raise Blad("--wysokosc: kąt kamery nad podłogą od -89 do 89 stopni")
    if not 0.5 <= a.skala <= 3:
        raise Blad("--skala 0,5–3")
    w, h = _rozmiar(a.rozmiar)
    return {"w": w, "h": h, "kat": a.kat % 360, "wysokosc": a.wysokosc, "kolor": _kolor(a.kolor, "--kolor"),
            "tlo": None if a.przezroczyste else (_kolor(a.tlo, "--tlo") or "#F4F4F2"), "siatka": a.siatka,
            "krawedzie": not a.bez_krawedzi, "skala": a.skala}


def _glb(s: str) -> Path:
    p = Path(s)
    if not p.is_file() or p.suffix.lower() not in (".glb", ".gltf"):
        raise Blad(f"{p}: potrzebny model .glb (cad.py zbuduj robi go razem ze STEP i STL)")
    if p.suffix.lower() == ".gltf":
        raise Blad(f"{p}: .gltf z osobnymi plikami nie przejdzie; użyj .glb (jeden plik)")
    return p.resolve()


def _node(zadanie: dict, limit: int = 900) -> dict:
    node = shutil.which("node")
    if not node:
        raise Blad("brak node (w kontenerze Jarva jest w obrazie)")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(zadanie, f)
    try:
        p = subprocess.run([node, str(RENDER_JS), f.name], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=limit)
    finally:
        os.unlink(f.name)
    if p.returncode:
        raise Blad((p.stderr or p.stdout).strip()[-800:] or "cad_render.cjs: błąd")
    return json.loads(p.stdout.strip().splitlines()[-1])


def polecenie_ffmpeg(fps: float, out: Path, klatki: str) -> list[str]:
    return ["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps:g}", "-i", klatki,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out)]


def podglad(glb: Path, out: Path, widok: dict) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    return _node({"tryb": "png", "glb": str(glb), "out": str(out.resolve()), **widok})


def obrot(glb: Path, out: Path, widok: dict, sekundy: float, fps: float) -> dict:
    if not 1 <= sekundy <= 60 or not 10 <= fps <= 60:
        raise Blad("--sekundy 1–60, --fps 10–60")
    if widok["tlo"] is None:
        raise Blad("film obrotu ma pełne tło (MP4 nie ma przezroczystości): bez --przezroczyste")
    if not shutil.which("ffmpeg"):
        raise Blad("brak ffmpeg (w kontenerze Jarva jest w obrazie)")
    klatek = round(sekundy * fps)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cad-obrot-") as t:
        r = _node({"tryb": "obrot", "glb": str(glb), "katalog": t, "klatek": klatek, **widok}, limit=1800)
        p = subprocess.run(polecenie_ffmpeg(fps, out.resolve(), str(Path(t) / "k%05d.png")), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if p.returncode or not out.exists():
            raise Blad(f"ffmpeg: {(p.stderr or '').strip()[-400:]}")
    return {**r, "plik": out.as_posix(), "klatek": klatek, "sekundy": sekundy, "fps": fps, "bajty": out.stat().st_size}


# ---------------------------------------------------------------- CLI

def stan() -> dict:
    node, ffmpeg = shutil.which("node"), shutil.which("ffmpeg")
    r = {"silnik": None, "node": node and Path(node).as_posix(), "ffmpeg": ffmpeg and Path(ffmpeg).as_posix()}
    try:
        py = cad_python()
        p = subprocess.run([py, "-I", "-c", "import importlib.metadata as m; print(m.version('build123d'))"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        r["silnik"] = {"python": Path(py).as_posix(), "build123d": p.stdout.strip() or None}
    except Blad as e:
        r["blad"] = str(e)
    return r


def _wypisz_model(r: dict) -> None:
    if "wymiary_mm" in r:
        x, y, z = r["wymiary_mm"]
        print(f"wymiary: {x} × {y} × {z} mm, objętość {r['objetosc_mm3']} mm³, masa ~{r['masa_g']} g "
              f"({r.get('material') or str(r['gestosc_g_cm3']) + ' g/cm³'}), bryły: {r['bryly']}, "
              f"poprawny: {'tak' if r['poprawny'] else 'NIE'}")
    for k, v in (r.get("pliki") or {}).items():
        print(f"→ {v['plik']} ({v['bajty'] // 1024} KB" + (f", {v['trojkaty']} trójkątów" if "trojkaty" in v else "") + ")")
    if r.get("podglad"):
        print(f"→ {r['podglad']}")
    for t in r.get("ostrzezenia", []):
        print(f"! {t}")
    for t in r.get("bledy", []):
        print(f"✗ {t}")


def _widok_args(p: argparse.ArgumentParser, rozmiar: str) -> None:
    p.add_argument("glb")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--rozmiar", default=rozmiar)
    p.add_argument("--kat", type=float, default=35, help="obrót kamery wokół modelu (stopnie)")
    p.add_argument("--wysokosc", type=float, default=25, help="kamera nad podłogą (stopnie)")
    p.add_argument("--kolor", help="jeden kolor całego modelu #RRGGBB (bez: kolory z modelu albo szary)")
    p.add_argument("--tlo")
    p.add_argument("--przezroczyste", action="store_true")
    p.add_argument("--siatka", action="store_true", help="siatka podłogi co 10 mm (skala przy częściach do druku)")
    p.add_argument("--bez-krawedzi", action="store_true")
    p.add_argument("--skala", type=float, default=1, help="gęstość pikseli (2 = ostrzej, 2× większy plik)")
    p.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cad.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zbuduj", help="skrypt build123d → STEP, STL, GLB, 3MF + raport (wymiary, objętość, masa)")
    z.add_argument("model")
    z.add_argument("-o", "--out", required=True, help="katalog wyników")
    z.add_argument("--nazwa", help="nazwa plików (domyślnie nazwa skryptu)")
    z.add_argument("--formaty", default=",".join(FORMATY))
    z.add_argument("--dokladnosc", type=float, default=0.05, help="odchyłka siatki STL/GLB/3MF w mm")
    z.add_argument("--material", choices=sorted(MATERIALY), default="pla")
    z.add_argument("--gestosc", type=float, help="g/cm³ zamiast --material")
    z.add_argument("--podglad", action="store_true", help="od razu PNG z GLB (domyślny widok)")
    z.add_argument("--mimo-bledow", action="store_true", help="eksport także przy błędach kształtu (do obejrzenia)")
    z.add_argument("--limit", type=int, default=300, help="sekundy na budowę")
    z.add_argument("--json", action="store_true")
    _widok_args(sub.add_parser("podglad", help="GLB → PNG (Three.js w Chromium)"), "1600x1200")
    o = sub.add_parser("obrot", help="GLB → film MP4: model obraca się o 360°")
    _widok_args(o, "1080x1080")
    o.add_argument("--sekundy", type=float, default=6)
    o.add_argument("--fps", type=float, default=30)
    s = sub.add_parser("stan", help="czy silnik CAD, node i ffmpeg są na miejscu")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "zbuduj":
            zad = zadanie_modelu(a)
            if a.podglad and "glb" not in zad["formaty"]:
                raise Blad("--podglad potrzebuje formatu glb")
            r = zbuduj(zad, a.limit)
            glb = (r.get("pliki") or {}).get("glb")
            if a.podglad and glb:
                ns = argparse.Namespace(rozmiar="1600x1200", kat=35, wysokosc=25, kolor=None, tlo=None,
                                        przezroczyste=False, siatka=False, bez_krawedzi=False, skala=1)
                png = Path(zad["out"]) / f"{zad['nazwa']}.png"
                wr = podglad(Path(glb["plik"]), png, opcje_widoku(ns))
                r["podglad"] = png.as_posix()
                r["ostrzezenia"] += [f"podgląd: {b}" for b in wr.get("bledy", [])]
            print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else _wypisz_model(r)
            return 1 if r["bledy"] else 0
        if a.cmd == "stan":
            r = stan()
            print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else
                  f"silnik: {r['silnik'] or r.get('blad')}\nnode: {r['node']}\nffmpeg: {r['ffmpeg']}")
            return 0 if r["silnik"] and r["silnik"]["build123d"] and r["node"] and r["ffmpeg"] else 1
        widok = opcje_widoku(a)
        glb, out = _glb(a.glb), Path(a.out)
        r = podglad(glb, out, widok) if a.cmd == "podglad" else obrot(glb, out, widok, a.sekundy, a.fps)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f"→ {out.as_posix()}" + (f" ({r['klatek']} klatek, {r['sekundy']:g} s)" if a.cmd == "obrot" else ""))
            for b in r.get("bledy", []):
                print(f"! {b}")
        return 1 if r.get("bledy") else 0
    except Blad as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
