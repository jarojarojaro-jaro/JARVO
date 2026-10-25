#!/usr/bin/env python3
"""Warsztat 3D floty: model z kodu build123d → STEP, STL, GLB, 3MF + raport, podgląd PNG i film obrotu.

    python3 cad.py zbuduj model.py -o out/ [--nazwa czesc] [--formaty step,stl,glb,3mf] [--dokladnosc 0.05]
                          [--material pla|petg|abs|asa|tpu|nylon|aluminium|stal|drewno | --gestosc 1.24]
                          [--podglad] [--mimo-bledow] [--limit 300] [--json]
    python3 cad.py podglad czesc.glb -o czesc.png [--rozmiar 1600x1200] [--kat 35] [--wysokosc 25] [--kolor "#9AA4B2"]
                           [--tlo "#F4F4F2" | --przezroczyste] [--siatka] [--bez-krawedzi] [--skala 1]
    python3 cad.py obrot czesc.glb -o obrot.mp4 [--sekundy 6] [--fps 30] [--rozmiar 1080x1080] [opcje jak w podglad]
    python3 cad.py stan [--json]
    python3 cad.py zainstaluj [--json]      # instalacja natywna: silnik CAD teraz, zamiast przy pierwszym `zbuduj`

Silnik: build123d (Apache-2.0) na OpenCascade (cadquery-ocp, LGPL-2.1) w osobnym venvie: w obrazie /opt/jarvo/venvs/cad,
w instalacji natywnej venv `cad` z manifestu (vendor/natywne.yaml, `kiedy: przy-uzyciu`: pierwsze `zbuduj` instaluje
go przez jarvo/przy_uzyciu.py z locka z sumami, ok. 215 MB pobrania), albo JARVO_CAD_PYTHON. Skrypt modelu przypisuje
gotowy kształt do zmiennej `wynik`, wymiary w milimetrach. Budowa idzie bez sieci (cad_model.py blokuje gniazda).
Podgląd i film: Three.js (MIT) na stronie cad_podglad.html, WebGL na CPU przez SwiftShader, film sklejany ffmpeg.
Paczki three i playwright-core to narzędzia npm floty z infra/node/package-lock.json: w obrazie /opt/jarvo/node,
natywnie `<program>/node-floty/<skrót locka>` z instalacji (NODE_PATH, wpis `node-floty` w narzedzia.json). Gdy Node
je widzi (próba `cad_render.cjs --sprawdz`, ta sama ścieżka wyszukiwania co render), podgląd robi cad_render.cjs
w Chromium z obrazu albo w chrome-headless-shell z instalacji (CHROME_PATH). Inaczej (np. proces bez środowiska Jarva)
cad_render.py: Playwright dla Pythona z venvu narzędzi i Three.js z katalogu node-floty z narzedzia.json albo
z NODE_PATH. JARVO_CAD_RENDER=node|python wymusza sposób podglądu.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
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
RENDER_PY = HERE / "cad_render.py"
CAD_PYTHON = "/opt/jarvo/venvs/cad/bin/python"
THREE_KONTENER = "/opt/jarvo/node/node_modules/three"
PRZEGLADARKA_KONTENER = Path("/etc/hermes/agent-browser-executable-path")
FORMATY = ("step", "stl", "glb", "3mf")
# gęstość w g/cm³ (masa w raporcie: szacunek dla 100% wypełnienia; wydruk z wypełnieniem 15–20% waży mniej)
MATERIALY = {"pla": 1.24, "petg": 1.27, "abs": 1.04, "asa": 1.07, "tpu": 1.21, "nylon": 1.14,
             "aluminium": 2.70, "stal": 7.85, "drewno": 0.60}
KOLOR = re.compile(r"#[0-9a-fA-F]{6}")


class Blad(Exception):
    pass


def _log(tekst: str) -> None:
    """Postęp instalacji przy pierwszym użyciu: na stderr (stdout zostaje dla raportu i --json)."""
    print(tekst, file=sys.stderr, flush=True)


def _czytaj_json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _przy_uzyciu():
    """(moduł jarvo/przy_uzyciu.py aktywnej wersji Jarva, układ katalogów) w instalacji natywnej (JARVO_ROOT
    z program/current.json), inaczej (None, None): w obrazie silnik i Three.js są gotowe. Pakiet jarvo ładujemy
    z kodu instalacji (JARVO_REPO albo current.json) bez dopisywania katalogu kodu do sys.path. Moduł daje też wpisy
    `<stan>/narzedzia.json` (`wpis`: node-floty z Three.js, chrome-headless-shell)."""
    korzen = os.environ.get("JARVO_ROOT")
    biezace = Path(korzen) / "program" / "current.json" if korzen else None
    if biezace is None or not biezace.is_file():
        return None, None
    sciezka_app = str(os.environ.get("JARVO_REPO") or _czytaj_json(biezace).get("app") or "")
    app = Path(sciezka_app)
    if not os.path.isabs(sciezka_app) or not (app / "jarvo" / "przy_uzyciu.py").is_file():
        return None, None                  # nigdy kod z katalogu bieżącego (pusta albo względna ścieżka)
    if "jarvo" not in sys.modules:
        spec = importlib.util.spec_from_file_location("jarvo", app / "jarvo" / "__init__.py",
                                                      submodule_search_locations=[str(app / "jarvo")])
        modul = importlib.util.module_from_spec(spec)
        sys.modules["jarvo"] = modul
        spec.loader.exec_module(modul)
    try:
        pu = importlib.import_module("jarvo.przy_uzyciu")
    except ImportError:                    # starsza wersja Jarva bez instalacji przy pierwszym użyciu
        return None, None
    return pu, pu.uklad({"JARVO_ROOT": korzen})          # z JARVO_ROOT układ nie zależy od innych zmiennych


def cad_python(instaluj: bool = True) -> str:
    """Python venvu CAD. Instalacja natywna: venv `cad` dla locka tej wersji Jarva (po aktualizacji locka nowy venv,
    a nie stary ze zmiennej sprzed restartu bramy), przy pierwszym użyciu instalowany teraz, gdy `instaluj`. Poza nią:
    JARVO_CAD_PYTHON, potem venv obrazu Jarva."""
    pu, u = _przy_uzyciu()
    if pu is not None:
        gotowy = pu.gotowy_venv(u, "cad")
        if gotowy:
            return gotowy["python"]
        if not instaluj:
            raise Blad("silnik CAD nie jest jeszcze zainstalowany: pierwsze `cad.py zbuduj` (albo `cad.py zainstaluj`) "
                       "pobierze go z sumami (ok. 215 MB, 1–3 min)")
        try:
            return pu.venv(u, "cad", log=_log)["python"]
        except pu.BladPrzyUzyciu as e:
            raise Blad(f"silnik CAD: {e}") from None
    for k in (os.environ.get("JARVO_CAD_PYTHON"), CAD_PYTHON):
        if k and Path(k).exists():
            return k
    raise Blad("brak silnika CAD (venv /opt/jarvo/venvs/cad z obrazu Jarva; poza kontenerem: instalacja natywna "
               "Jarva albo JARVO_CAD_PYTHON)")


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


def node_podglad() -> str | None:
    """node, gdy cad_render.cjs znajdzie three i playwright-core (`cad_render.cjs --sprawdz`: te same funkcje
    i ta sama ścieżka wyszukiwania modułów co render, czyli katalog skryptu, NODE_PATH i katalogi globalne Node,
    a nie node_modules katalogu, w którym akurat pracuje agent)."""
    node = shutil.which("node")
    if not node:
        return None
    try:
        p = subprocess.run([node, str(RENDER_JS), "--sprawdz"], capture_output=True, timeout=60, cwd=str(HERE))
    except (OSError, subprocess.TimeoutExpired):
        return None
    return node if p.returncode == 0 else None


def _three_ok(p: Path) -> bool:
    return ((p / "build" / "three.module.js").is_file()
            and (p / "examples" / "jsm" / "loaders" / "GLTFLoader.js").is_file())


def _node_modules_floty() -> str | None:
    """node_modules narzędzi npm floty instalacji natywnej z `<stan>/narzedzia.json` (wpis node-floty, NODE_PATH):
    aktualna wersja także w procesie uruchomionym przed aktualizacją albo bez środowiska Jarva."""
    pu, u = _przy_uzyciu()
    if pu is None:
        return None
    return ((pu.wpis(u, "node-floty") or {}).get("env") or {}).get("NODE_PATH")


def three_root() -> Path:
    """Katalog paczki three dla cad_render.py: narzędzia npm floty instalacji natywnej (wpis node-floty
    w narzedzia.json), JARVO_THREE_DIR, NODE_PATH (w obrazie /opt/jarvo/node/node_modules), narzędzia Wideografa
    (JARVO_NARZEDZIA/node), obraz Jarva. Niczego nie pobiera: three przychodzi z instalacją (infra/node, lock)."""
    kandydaci = [str(Path(k) / "three") for k in (_node_modules_floty() or "").split(os.pathsep) if k]
    kandydaci.append(os.environ.get("JARVO_THREE_DIR"))
    kandydaci += [str(Path(k) / "three") for k in os.environ.get("NODE_PATH", "").split(os.pathsep) if k]
    narzedzia_floty = os.environ.get("JARVO_NARZEDZIA")
    if narzedzia_floty:
        kandydaci.append(str(Path(narzedzia_floty) / "node" / "node_modules" / "three"))
    kandydaci.append(THREE_KONTENER)
    for k in kandydaci:
        if k and _three_ok(Path(k)):
            return Path(k)
    if _przy_uzyciu()[0] is not None:
        raise Blad("brak Three.js do podglądu: w instalacji Jarva paczkę three dają narzędzia npm floty (krok "
                   "instalacji „Narzędzia npm floty”, infra/node/package-lock.json). Zgłoś to właścicielowi: polecenie "
                   "instalacji Jarva uruchomione jeszcze raz (albo `jarvo update`) je doinstaluje")
    raise Blad("brak Three.js do podglądu (paczka three: w obrazie /opt/jarvo/node; poza instalacją Jarva NODE_PATH "
               "z paczką three albo JARVO_THREE_DIR)")


def przegladarka() -> str | None:
    """Chromium do podglądu: CHROME_PATH (natywnie chrome-headless-shell z instalacji), wpis narzędzia z CHROME_PATH
    w narzedzia.json (proces bez środowiska Jarva), plik Hermesa z obrazu."""
    c = os.environ.get("CHROME_PATH")
    if c and Path(c).is_file():
        return c
    pu, u = _przy_uzyciu()
    if pu is not None:
        for nazwa in ("chrome-headless-shell",):
            sciezka = ((pu.wpis(u, nazwa) or {}).get("env") or {}).get("CHROME_PATH")
            if sciezka and Path(sciezka).is_file():
                return sciezka
    if PRZEGLADARKA_KONTENER.is_file():
        return PRZEGLADARKA_KONTENER.read_text(encoding="utf-8").strip() or None
    return None


def python_playwright() -> str | None:
    """Python z paczką playwright do cad_render.py: ten interpreter (natywnie skille wołają cad.py Pythonem venvu
    narzędzi Jarva) albo JARVO_TOOLS_PYTHON."""
    if importlib.util.find_spec("playwright") is not None:
        return sys.executable
    py = os.environ.get("JARVO_TOOLS_PYTHON")
    return py if py and Path(py).is_file() else None


def _uruchom_render(argv: list[str], zadanie: dict, limit: int, nazwa: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(zadanie, f)
    try:
        p = subprocess.run([*argv, f.name], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=limit)
    except subprocess.TimeoutExpired:
        raise Blad(f"{nazwa}: podgląd trwał ponad {limit} s") from None
    finally:
        os.unlink(f.name)
    linie = [x for x in p.stdout.strip().splitlines() if x.startswith("{")]
    if p.returncode or not linie:
        raise Blad((p.stderr or p.stdout).strip()[-800:] or f"{nazwa}: błąd")
    return json.loads(linie[-1])


def _node(zadanie: dict, limit: int = 900, node: str | None = None) -> dict:
    node = node or shutil.which("node")
    if not node:
        raise Blad("brak node (w kontenerze Jarva jest w obrazie, natywnie w instalacji)")
    zadanie = {**zadanie, "chrome": przegladarka()}       # natywnie chrome-headless-shell z instalacji
    return _uruchom_render([node, str(RENDER_JS)], zadanie, limit, "cad_render.cjs")


def _python(zadanie: dict, limit: int = 900) -> dict:
    py = python_playwright()
    if not py:
        raise Blad("brak Playwright dla Pythona do podglądu (natywnie: venv narzędzi Jarva, JARVO_TOOLS_PYTHON; "
                   "w obrazie: Node)")
    chrome = przegladarka()
    if not chrome:
        raise Blad("brak Chromium do podglądu (natywnie chrome-headless-shell z instalacji: CHROME_PATH)")
    zadanie = {**zadanie, "three": str(three_root()), "chrome": chrome}
    return _uruchom_render([py, "-I", *_utf8(), str(RENDER_PY)], zadanie, limit, "cad_render.py")


def render(zadanie: dict, limit: int = 900) -> dict:
    """Podgląd PNG albo klatki filmu: Node z cad_render.cjs, gdy widzi three i playwright-core (obraz Jarva
    i instalacja natywna z narzędziami npm floty), inaczej Playwright dla Pythona z cad_render.py;
    JARVO_CAD_RENDER=node|python wymusza sposób."""
    tryb = os.environ.get("JARVO_CAD_RENDER", "").strip().lower()
    node = node_podglad() if tryb in ("", "node") else None
    if node:
        return _node(zadanie, limit, node)
    if tryb == "node":
        raise Blad("JARVO_CAD_RENDER=node, a Node nie ma paczek three i playwright-core")
    return _python(zadanie, limit)


def program_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def polecenie_ffmpeg(fps: float, out: Path, klatki: str, ffmpeg: str = "ffmpeg") -> list[str]:
    return [ffmpeg, "-y", "-loglevel", "error", "-framerate", f"{fps:g}", "-i", klatki,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out)]


def podglad(glb: Path, out: Path, widok: dict) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    return render({"tryb": "png", "glb": str(glb), "out": str(out.resolve()), **widok})


def obrot(glb: Path, out: Path, widok: dict, sekundy: float, fps: float) -> dict:
    if not 1 <= sekundy <= 60 or not 10 <= fps <= 60:
        raise Blad("--sekundy 1–60, --fps 10–60")
    if widok["tlo"] is None:
        raise Blad("film obrotu ma pełne tło (MP4 nie ma przezroczystości): bez --przezroczyste")
    ffmpeg = program_ffmpeg()
    if not ffmpeg:
        raise Blad("brak ffmpeg (w kontenerze Jarva jest w obrazie, natywnie w instalacji)")
    klatek = round(sekundy * fps)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cad-obrot-") as t:
        r = render({"tryb": "obrot", "glb": str(glb), "katalog": t, "klatek": klatek, **widok}, limit=1800)
        p = subprocess.run(polecenie_ffmpeg(fps, out.resolve(), str(Path(t) / "k%05d.png"), ffmpeg),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode or not out.exists():
            raise Blad(f"ffmpeg: {(p.stderr or '').strip()[-400:]}")
    return {**r, "plik": out.as_posix(), "klatek": klatek, "sekundy": sekundy, "fps": fps, "bajty": out.stat().st_size}


# ---------------------------------------------------------------- CLI

def stan_podgladu() -> dict:
    """Czym zrobimy podgląd (bez instalowania): Node z three i playwright-core (obraz, instalacja z narzędziami npm
    floty) albo Playwright dla Pythona z Chromium i Three.js; `blad` mówi, czego brak."""
    tryb = os.environ.get("JARVO_CAD_RENDER", "").strip().lower()
    if tryb in ("", "node") and node_podglad():
        return {"sposob": "node", "gotowy": True, "przegladarka": przegladarka()}
    r = {"sposob": "python", "python": python_playwright(), "przegladarka": przegladarka(), "three": None}
    try:
        r["three"] = three_root().as_posix()
    except Blad as e:
        r["blad"] = str(e)
    r["gotowy"] = bool(r["python"] and r["przegladarka"] and r["three"])
    return r


def stan() -> dict:
    node, ffmpeg = shutil.which("node"), program_ffmpeg()
    r = {"silnik": None, "node": node and Path(node).as_posix(), "ffmpeg": ffmpeg and Path(ffmpeg).as_posix()}
    try:
        py = cad_python(instaluj=False)
        p = subprocess.run([py, "-I", "-c", "import importlib.metadata as m; print(m.version('build123d'))"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        r["silnik"] = {"python": Path(py).as_posix(), "build123d": p.stdout.strip() or None}
    except Blad as e:
        r["blad"] = str(e)
        pu, u = _przy_uzyciu()
        if pu is not None:
            try:
                r["silnik_przy_uzyciu"] = pu.opis_venvu(u, "cad")
            except pu.BladPrzyUzyciu:
                pass
    r["podglad"] = stan_podgladu()
    return r


def stan_gotowy(r: dict) -> bool:
    """Wszystko jest albo pobierze się przy pierwszym użyciu: silnik, podgląd i ffmpeg."""
    silnik = (r.get("silnik") or {}).get("build123d") or r.get("silnik_przy_uzyciu")
    return bool(silnik and (r.get("podglad") or {}).get("gotowy") and r.get("ffmpeg"))


def _opis_stanu(r: dict) -> str:
    s = r.get("silnik")
    if s and s.get("build123d"):
        silnik = f"build123d {s['build123d']} ({s['python']})"
    elif r.get("silnik_przy_uzyciu"):
        o = r["silnik_przy_uzyciu"]
        silnik = (f"pobierze się przy pierwszym `zbuduj` albo `zainstaluj` (ok. {o.get('pobranie_mb') or '?'} MB, "
                  f"{o.get('paczek') or '?'} paczek z sumami)")
    else:
        silnik = r.get("blad") or "brak"
    p = r.get("podglad") or {}
    if p.get("sposob") == "node":
        podglad = (f"Node z three i playwright-core (cad_render.cjs), Chromium "
                   f"{p.get('przegladarka') or 'z obrazu'}")
    else:
        podglad = (f"Chromium {p.get('przegladarka') or 'brak'} z Playwright dla Pythona "
                   f"({p.get('python') or 'brak'}), Three.js: {p.get('three') or 'brak'}")
        if p.get("blad"):
            podglad += f"\n  ! {p['blad']}"
    return f"silnik: {silnik}\npodgląd: {podglad}\nffmpeg: {r['ffmpeg']}"


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
    s = sub.add_parser("stan", help="czy silnik CAD, podgląd i ffmpeg są na miejscu (albo pobiorą się przy użyciu)")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("zainstaluj", help="instalacja natywna: silnik CAD teraz (z sumami), zamiast przy pierwszym "
                                          "`zbuduj`; Three.js do podglądu przychodzi z instalacją Jarva")
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
                try:
                    wr = podglad(Path(glb["plik"]), png, opcje_widoku(ns))
                except Blad as e:            # pliki CAD są gotowe: raport zostaje, podgląd to ostrzeżenie
                    r["ostrzezenia"].append(f"podgląd się nie udał: {e}")
                else:
                    r["podglad"] = png.as_posix()
                    r["ostrzezenia"] += [f"podgląd: {b}" for b in wr.get("bledy", [])]
            print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else _wypisz_model(r)
            return 1 if r["bledy"] else 0
        if a.cmd == "stan":
            r = stan()
            print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else _opis_stanu(r))
            return 0 if stan_gotowy(r) else 1
        if a.cmd == "zainstaluj":
            r = {"silnik": Path(cad_python()).as_posix()}       # Three.js przyszedł z instalacją (narzędzia npm)
            r["stan"] = stan()
            print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else _opis_stanu(r["stan"]))
            return 0 if stan_gotowy(r["stan"]) else 1
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
