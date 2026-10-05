#!/usr/bin/env python3
"""Narzędzia „wideo z kodu”: sprawdzenie i instalacja raz, we wspólnym katalogu.

    python3 narzedzia.py sprawdz                 # co jest gotowe, czego brak (JSON)
    python3 narzedzia.py instaluj [motion|lemo|anidoodle|animacja|remotion|shotcraft|html|lottie|mg|mgaudio|wszystko]
    python3 narzedzia.py env <narzedzie>         # zmienne środowiska do wklejenia: eval "$(python3 narzedzia.py env motion)"
    python3 narzedzia.py link <katalog>          # <katalog>/node_modules → wspólne (skrypty .mjs nie czytają NODE_PATH)
    python3 narzedzia.py kroje <katalog>         # brakujące kroje z <katalog>/fonts.css: google/fonts (OFL) + polskie znaki

Narzędzia: motion (motion-broll), lemo (lemo-opuscar), anidoodle, remotion (skill remotion-best-practices, iart),
shotcraft (video-shotcraft na Remotion), html (html_wideo.py: animacja HTML → klatki / MP4; pixel2motion, iart,
bang-motion), lottie (oficjalny player Skottie do text-to-lottie + eksport przez html_wideo.py lottie),
mg (mg-styles-15: kod 15 filmów-wzorów stylów motion design, notatki stylów, okładki, tekstury, kroje wzorów),
mgaudio (dodatek: muzyka i efekty pisane kodem z mg-styles-15 dla muzyka.py; własny venv ok. 390 MB i sample 56 MB).

Zasady (VPS 8 GB, bez dubli):
- przeglądarka: Chromium headless z obrazu Hermesa (PLAYWRIGHT_BROWSERS_PATH), nic nie pobieramy; wersja
  playwright (Node i Python) przypięta do tej przeglądarki (PW_VERSION),
- pakiety npm i Python raz do /opt/data/jarvo/narzedzia (przeżywają restart), a nie w każdym projekcie,
- biblioteki z repo (lemo-opuscar, video-shotcraft, player Lottie) przypięte do commitów z vendor/skills.lock.yaml
  (bez samoczynnych aktualizacji; nowy commit w repo Jarva → `instaluj` przenosi istniejący klon na niego);
  video-shotcraft z indeksem kart galerii, bez jej filmów, edytora workbench i eksportu JianYing;
  mg-styles-15 bez filmów (okładki zostają), strony pokazowej, zdjęć bez opisanego źródła i modeli do Blendera,
  z krojami wzorów z google/fonts (OFL, Apache-2.0; chińskie spoza google/fonts zastępuje Noto Sans SC);
  HDRI do stylów 3D lemo (~12 MB) zawsze; ciężkie assety lemo (głos Kokoro ~340 MB, sample ~1,4 GB) tylko
  z JARVO_EXTRAS „lemo”; mgaudio w `wszystko` tylko z JARVO_EXTRAS „mgaudio” (osobno: `instaluj mgaudio`).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("JARVO_NARZEDZIA", "/opt/data/jarvo/narzedzia" if Path("/opt/data/jarvo").is_dir()
                           else str(Path.home() / ".cache" / "jarvo-narzedzia")))
NODE = ROOT / "node"                  # wspólne node_modules (playwright dla motion-broll, cache npm dla projektów)
VENV = ROOT / "venv"                  # Python z numpy/pillow/playwright… dla skryptów narzędzi
PW_VERSION = "1.63.0"                 # = chromium_headless_shell z obrazu Hermesa (Node i Python)

LEMO = ROOT / "lemo-opuscar"
LEMO_REPO = "https://github.com/lemomo-ai/lemo-opuscar.git"
LEMO_REV = "b65efe6ea393fdc71212898ea4c57c754cfefa46"        # vendor/skills.lock.yaml → lemo-opuscar
# jak sparse-checkout setup.sh skilla: bez źródeł dem, galerii i dużych obrazów; dema dodane przez
# `setup.sh demo <slug>` (LEMO_DODANE) zostają przy aktualizacji
LEMO_POMIN = ["/styles/*/demo/", "/styleboard/", "/docs/frames/", "/docs/cover.jpg", "/docs/opuscar98.jpg",
              "/styles/*/poster.jpg"]
LEMO_DODANE = re.compile(r"/styles/[^/*]+/(demo/|poster\.jpg)")
# poziomy zależności Pythona biblioteki (= `setup.sh deps [voice] [music]`): plik requirements i znacznik .venv/.lemo-<poziom>;
# core: efekty, miks, napisy; music: numba dla instrumentów proceduralnych pluck.py; voice (Kokoro, Whisper) tylko z dodatkami
LEMO_POZIOMY = {"core": "requirements.txt", "music": "requirements-music.txt", "voice": "requirements-voice.txt"}
SHOTCRAFT = ROOT / "video-shotcraft"
SHOTCRAFT_REPO = "https://github.com/Vincentwei1021/video-shotcraft.git"
SHOTCRAFT_REV = "e2d8928c57ef84701f9b0119ca4a1c28a62050c1"   # vendor/skills.lock.yaml → video-shotcraft
# galeria zostaje (gallery/api/library.json = indeks 157 kart, ~1,2 MB); bez filmów galerii, ich edytora (workbench)
# i eksportu do JianYing – Jarvo ma własny edytor HQ
SHOTCRAFT_POMIN = ["/gallery/media/", "/gallery/og-image.jpg", "/workbench/", "/jianying-export/"]
MGSTYLES = ROOT / "mg-styles-15"
MGSTYLES_REPO = "https://github.com/Vincentwei1021/mg-styles-15.git"
MGSTYLES_REV = "49052d80bfaf9fa8412cc9710530e5e95a3b8d8c"   # vendor/skills.lock.yaml → mg-styles-15
# zostaje kod 15 dem, prompty (notatki stylów), okładki (videos/*.jpg), tekstury (papier CC0; ziarno, kurz i washi
# bez podanego źródła: tylko do podglądu wzoru) i kod mgaudio (~55 MB); bez filmów (420 MB), strony pokazowej,
# zdjęć bez opisanego źródła (koty 18-hanazi, wycinki 06-collage, naklejki 19-paperclip), modeli i siatek
# do Blendera (04-3d-render) i sampli mgaudio (56 MB: dochodzą z dodatkiem `instaluj mgaudio`)
MGSTYLES_POMIN = ["/videos/*.mp4", "/docs/", "/site/", "/index.html", "/.nojekyll", "/demos/18-hanazi/assets/",
                  "/demos/06-collage/assets/", "/demos/04-3d-render/assets/", "/demos/19-paperclip/assets/stickers/",
                  "/lib/audio/samples/"]
# biblioteki, które importują dema (importmap → /node_modules/…); three jest w HTML_LIBS w tej samej wersji
MG_LIBS = ["d3@7.9.0", "opentype.js@2.0.0", "simplex-noise@4.0.3", "topojson-client@3.1.0"]
# mgaudio (lib/audio wzorów, MIT): muzyka i efekty pisane kodem (muzyka.py). Własny venv, bo numba/llvmlite,
# scipy i pedalboard to ok. 390 MB, których reszta narzędzi nie potrzebuje; wersje jak w requirements.txt wzorów
# (bez matplotlib i librosa: spektrogram PNG i zmiana wysokości dźwięku, których muzyka.py nie używa).
# Sample VCSL (CC0, 56 MB, 15 instrumentów) dochodzą do klonu wzorów jako dodany wpis sparse-checkout.
MGAUDIO_VENV = ROOT / "venv-mgaudio"
MGAUDIO_PY = ["numpy==2.4.6", "scipy==1.16.3", "soundfile==0.14.0", "numba==0.66.0", "pedalboard==0.9.25",
              "pyloudnorm==0.2.0"]
MG_SAMPLE = "/lib/audio/samples/"
MG_DODANE = re.compile(re.escape(MG_SAMPLE))
LOTTIE = ROOT / "lottie-player"
LOTTIE_REPO = "https://github.com/diffusionstudio/lottie.git"
LOTTIE_REV = "3c72912fad543897f90045ed4d355813837927fc"      # vendor/skills.lock.yaml → lottie

# = wersja skilli remotion-dev/skills z locka i szablonu `create-video@4.0.529`; rozgrzany cache npm dla nowych projektów
# (video-shotcraft ma własny package-lock na 4.0.484 i instaluje go `npm ci`)
REMOTION_VERSION = "4.0.529"
REMOTION_PKGS = [f"remotion@{REMOTION_VERSION}", f"@remotion/cli@{REMOTION_VERSION}", "react@19.2.3", "react-dom@19.2.3"]
# skrypty z repo (bang-motion snap/export-frames, shotcraft capture-template) importują `puppeteer`; bez pobierania
# przeglądarki (PUPPETEER_SKIP_DOWNLOAD), uruchamiany na tej z obrazu (PUPPETEER_EXECUTABLE_PATH)
PUPPETEER = "puppeteer@24.43.1"
# biblioteki własnych animacji HTML (kontrakt `jarvo`): html_wideo.py serwuje je pod /_lib/, bez CDN
# (three: MIT; gsap: „Standard no-charge license”, darmowa także komercyjnie)
HTML_LIBS = ["three@0.186.1", "gsap@3.15.0", "p5@2.3.4"]   # p5: algorithmic-art
# nasze moduły JS do animacji HTML (ruch.js: charaktery ruchu, smugi; kreska, morph, crt, plotno, piksel: techniki
# stylów motion design z wzorów mg-styles-15; os_czasu.js: chwile lektora po nazwie z film.py narracja): kopia obok node_modules, bo npm usuwa
# z node_modules obce katalogi; html_wideo.py i podgląd HQ serwują ją pod /_lib/jarvo/
JARVO_JS = ROOT / "jarvo-js"
JARVO_JS_PLIKI = ["ruch.js", "kreska.js", "morph.js", "crt.js", "plotno.js", "piksel.js", "os_czasu.js", "strona.js", "ujecia.js"]
PY_BASE = ["numpy", "pillow"]
PY_HTML = [f"playwright=={PW_VERSION}", "imageio"]   # imageio: slack-gif-creator (GIF przez Pillow)
PY_MODULES = {"pillow": "PIL", "kokoro-onnx": "kokoro_onnx", "faster-whisper": "faster_whisper"}
NO_DOWNLOAD = {"PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1", "PUPPETEER_SKIP_DOWNLOAD": "1"}
# puppeteer i `chrome --headless --screenshot` nie dodają --no-sandbox, a Chromium jako root bez niego nie wstaje
# (playwright i Remotion dodają same); nakładka czyta prawdziwą ścieżkę z JARVO_CHROME_REAL (env), więc nie starzeje się
CHROME_WRAPPER = ROOT / "bin" / "chrome-no-sandbox"
CHROME_WRAPPER_SH = """#!/bin/sh
# Chromium z obrazu Hermesa z --no-sandbox (narzedzia.py env ustawia JARVO_CHROME_REAL)
exec "${JARVO_CHROME_REAL:?brak JARVO_CHROME_REAL: najpierw eval narzedzia.py env html}" --no-sandbox "$@"
"""

# układy katalogów przeglądarki w PLAYWRIGHT_BROWSERS_PATH (nowy: chrome-headless-shell, starszy: headless_shell)
SHELL_LAYOUTS = (("chrome-headless-shell-linux64", "chrome-headless-shell"), ("chrome-linux", "headless_shell"))


def browsers_path() -> str:
    return os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/hermes/.playwright")


def _build_no(d: Path) -> int:
    m = re.search(r"-(\d+)$", d.name)
    return int(m.group(1)) if m else -1


def headless_shell() -> str | None:
    base = Path(browsers_path())
    for d in sorted(base.glob("chromium_headless_shell-*"), key=_build_no, reverse=True):
        for sub, exe in SHELL_LAYOUTS:
            path = d / sub / exe
            if path.exists():
                return str(path)
    return None


def dodatek(nazwa: str) -> bool:
    return nazwa in os.environ.get("JARVO_EXTRAS", "").replace(",", " ").split()


def full_extras() -> bool:
    return dodatek("lemo")


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print("▶", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, env={**os.environ, **(env or {})})


def py() -> str:
    return str(VENV / "bin" / "python")


def wymagaj_playwright(skrypt: str, flaga: str, komunikat: str = "brak playwright w Pythonie", dopisek: str = "") -> None:
    """Playwright jest w venv narzędzi: bez niego skrypt raz uruchamia się od nowa tamtym Pythonem (`flaga` w env
    blokuje pętlę), a gdy i tam go nie ma, kończy się poleceniem instalacji."""
    try:
        import playwright.sync_api  # noqa: F401
        return
    except ImportError:
        pass
    venv_py = Path(py())
    if venv_py.exists() and Path(sys.prefix).resolve() != VENV.resolve() and not os.environ.get(flaga):
        os.environ[flaga] = "1"
        os.execv(str(venv_py), [str(venv_py), str(Path(skrypt).resolve()), *sys.argv[1:]])
    raise SystemExit(f"{komunikat}: python3 $HERMES_HOME/scripts/narzedzia.py instaluj html{dopisek}")


def py_name(spec: str) -> str:
    """Nazwa paczki ze specyfikacji pip („playwright==1.63.0” → playwright)."""
    return re.split(r"[=<>!~\[]", spec, maxsplit=1)[0].strip()


def py_module(spec: str) -> str:
    """Nazwa modułu do importu dla specyfikacji pip („playwright==1.63.0” → playwright, „pillow” → PIL)."""
    name = py_name(spec)
    return PY_MODULES.get(name, name.replace("-", "_"))


def uv_exempt(pkgs: list[str]) -> list[str]:
    """Obraz Hermesa ma w uv kwarantannę nowych wydań (exclude-newer: 14 dni). Paczki przypięte co do wersji
    (==X.Y.Z) zwalniamy z niej, jak robi to sam Hermes dla swoich pinów: dokładny pin nie „pływa”, więc kwarantanna
    nic nie chroni, a potrafi zablokować instalację (np. playwright wydany tydzień przed zmianą Chromium w obrazie).
    Paczki bez pinu (numpy, pillow) zostają pod kwarantanną."""
    out = []
    for spec in pkgs:
        if "==" in spec:
            out += ["--exclude-newer-package", f"{py_name(spec)}=false"]
    return out


def pip_install(python: str, pkgs: list[str]) -> None:
    if shutil.which("uv"):
        run(["uv", "pip", "install", "--quiet", "--python", python, *uv_exempt(pkgs), *pkgs])
    else:
        run([python, "-m", "pip", "install", "--quiet", *pkgs])


def py_ma(python: Path, spec: str) -> bool:
    """Paczka jest w tym Pythonie; przy pinie (==X.Y.Z) dokładnie w tej wersji (zmiana pinu = doinstaluj)."""
    if "==" in spec:
        kod = f"import importlib.metadata as m; print(m.version({py_name(spec)!r}))"
        p = subprocess.run([str(python), "-c", kod], capture_output=True, text=True)
        return p.returncode == 0 and p.stdout.strip() == spec.split("==", 1)[1]
    return subprocess.run([str(python), "-c", f"import {py_module(spec)}"], capture_output=True).returncode == 0


def ensure_venv(pkgs: list[str], venv: Path = VENV) -> None:
    python = venv / "bin" / "python"
    if not python.exists():
        if shutil.which("uv"):
            run(["uv", "venv", "--quiet", "--python", "3.12", str(venv)])
        else:
            run([sys.executable, "-m", "venv", str(venv)])
    missing = [p for p in pkgs if not py_ma(python, p)]
    if missing:
        pip_install(str(python), missing)


def npm_name(spec: str) -> str:
    """„@remotion/cli@4.0.484” → @remotion/cli, „remotion@4.0.484” → remotion, „esbuild” → esbuild."""
    scoped = spec.startswith("@")
    head = (spec[1:] if scoped else spec).partition("@")[0]
    return "@" + head if scoped else head


def npm_installed(spec: str, node_modules: Path) -> bool:
    """Pakiet jest w node_modules, a gdy spec ma dokładną wersję (x.y.z), to właśnie ta (zmiana wersji = doinstaluj)."""
    name = npm_name(spec)
    meta = node_modules / name / "package.json"
    if not meta.exists():
        return False
    want = spec[len(name) + 1:] if len(spec) > len(name) else ""
    if not re.fullmatch(r"\d+\.\d+\.\d+", want):
        return True
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("version") == want
    except (OSError, ValueError):
        return False


def ensure_node(pkgs: list[str]) -> None:
    NODE.mkdir(parents=True, exist_ok=True)
    if not (NODE / "package.json").exists():
        (NODE / "package.json").write_text('{"private": true}\n', encoding="utf-8")
    missing = [p for p in pkgs if not npm_installed(p, NODE / "node_modules")]
    if missing:
        run(["npm", "install", "--no-audit", "--no-fund", "--silent", *missing], cwd=NODE, env=NO_DOWNLOAD)


def git_head(dest: Path) -> str:
    return subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def clone_pinned(repo: str, rev: str, dest: Path, exclude: list[str], keep: re.Pattern | None = None) -> None:
    """Klon bez historii plików (blob:none) i bez ścieżek `exclude`, na przypiętym commicie. Klon na innym commicie
    przechodzi na nowy: nowy `rev` w repo Jarva = aktualizacja przy następnym `instaluj`; zmieniona lista `exclude`
    trafia też do klonu na tym samym commicie. Wpisy sparse-checkout pasujące do `keep` (np. dema dodane później) zostają."""
    if (dest / ".git").exists():
        if git_head(dest) != rev:
            run(["git", "-C", str(dest), "fetch", "--quiet", "--filter=blob:none", "origin", rev])
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", "--filter=blob:none", "--sparse", "--no-checkout", repo, str(dest)])
    lista = subprocess.run(["git", "-C", str(dest), "sparse-checkout", "list"], capture_output=True, text=True).stdout
    dodane = [w for w in lista.splitlines() if keep and keep.fullmatch(w)]
    wzorce = ["/*", *[f"!{e}" for e in exclude], *dodane]
    if git_head(dest) == rev and lista.splitlines() == wzorce:
        return
    run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone", *wzorce])
    run(["git", "-C", str(dest), "checkout", "--quiet", "--force", rev])


def install_motion() -> None:
    ensure_node([f"playwright@{PW_VERSION}"])
    ensure_venv(PY_BASE)


def ensure_chrome_wrapper() -> Path:
    CHROME_WRAPPER.parent.mkdir(parents=True, exist_ok=True)
    if not CHROME_WRAPPER.exists() or CHROME_WRAPPER.read_text(encoding="utf-8") != CHROME_WRAPPER_SH:
        CHROME_WRAPPER.write_text(CHROME_WRAPPER_SH, encoding="utf-8")
    CHROME_WRAPPER.chmod(0o755)
    return CHROME_WRAPPER


def install_html() -> None:
    ensure_chrome_wrapper()
    ensure_venv(PY_BASE + PY_HTML)
    ensure_node([PUPPETEER, *HTML_LIBS])
    sync_jarvo_js()


def sync_jarvo_js() -> Path:
    """Moduły JS Jarva (JARVO_JS_PLIKI ze scripts/) do JARVO_JS, gdy ich tam nie ma albo się zmieniły."""
    JARVO_JS.mkdir(parents=True, exist_ok=True)
    for nazwa in JARVO_JS_PLIKI:
        tresc = (Path(__file__).resolve().parent / nazwa).read_bytes()
        cel = JARVO_JS / nazwa
        if not cel.exists() or cel.read_bytes() != tresc:
            # własny plik tymczasowy: kilka przeglądarek renderu naraz synchronizuje ten sam moduł
            fd, tmp = tempfile.mkstemp(dir=JARVO_JS, prefix=f".{nazwa}.")
            with os.fdopen(fd, "wb") as f:
                f.write(tresc)
            os.chmod(tmp, 0o644)
            os.replace(tmp, cel)
    return JARVO_JS


def lemo_sig(*files: Path) -> str:
    """Suma plików jak `sig` w setup.sh skilla (cat | cksum): te same znaczniki = setup.sh uznaje pakiety za gotowe."""
    out = subprocess.run(["sh", "-c", 'cat "$@" 2>/dev/null | cksum | cut -d" " -f1', "sh", *map(str, files)],
                         capture_output=True, text=True).stdout
    return out.strip()


def lemo_znacznik(poziom: str | None) -> tuple[Path, str]:
    """(plik znacznika, oczekiwana treść): None = pakiety npm, inaczej poziom Pythona (suma pliku + wersja Pythona)."""
    if poziom is None:
        return LEMO / "node_modules" / ".lemo-ok", lemo_sig(LEMO / "package.json", LEMO / "package-lock.json")
    p = subprocess.run([str(LEMO / ".venv" / "bin" / "python"), "-V"], capture_output=True, text=True)
    wersja = ".".join((p.stdout or p.stderr).strip().split(".")[:2])          # „Python 3.12”, jak `cut -d. -f1,2`
    return LEMO / ".venv" / f".lemo-{poziom}", f"{lemo_sig(LEMO / LEMO_POZIOMY[poziom])}-{wersja}"


def lemo_gotowe(poziom: str | None) -> bool:
    plik, tresc = lemo_znacznik(poziom)
    return plik.exists() and plik.read_text(encoding="utf-8").strip() == tresc


def lemo_poziomy() -> list[str]:
    return ["core", "music"] + (["voice"] if full_extras() else [])


def install_lemo() -> None:
    clone_pinned(LEMO_REPO, LEMO_REV, LEMO, LEMO_POMIN, keep=LEMO_DODANE)
    # przypięta wersja: skill-owy setup.sh nie aktualizuje biblioteki, której nie oznaczył jako swojej
    subprocess.run(["git", "-C", str(LEMO), "config", "--unset", "lemo.managed"], capture_output=True)
    if not lemo_gotowe(None):
        run(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=LEMO, env=NO_DOWNLOAD)
        # npm potrafi przepisać package-lock.json: wersja z repo, żeby suma zgadzała się z setup.sh
        subprocess.run(["git", "-C", str(LEMO), "checkout", "-q", "--", "package.json", "package-lock.json"], capture_output=True)
        plik, tresc = lemo_znacznik(None)
        plik.write_text(tresc + "\n", encoding="utf-8")
    lemo_venv = LEMO / ".venv"
    if not (lemo_venv / "bin" / "python").exists():
        run(["uv", "venv", "--quiet", "--python", "3.12", str(lemo_venv)] if shutil.which("uv")
            else [sys.executable, "-m", "venv", str(lemo_venv)])
    for poziom in lemo_poziomy():
        if not lemo_gotowe(poziom):
            pip_install(str(lemo_venv / "bin" / "python"), ["-r", str(LEMO / LEMO_POZIOMY[poziom])])
            plik, tresc = lemo_znacznik(poziom)
            plik.write_text(tresc + "\n", encoding="utf-8")
    # HDRI (Poly Haven, CC0, ~12 MB): światło i odbicia w stylach 3D (brick-toy, paper-popup, paper-lantern…) – zawsze
    if not (LEMO / "core" / "assets" / "polyhaven").is_dir() or not any((LEMO / "core" / "assets" / "polyhaven").glob("*.hdr")):
        run(["sh", "tools/fetch.sh", "hdri"], cwd=LEMO)
    if full_extras():
        for what in (["voice"], ["instruments", "all"]):
            run(["sh", "tools/fetch.sh", *what], cwd=LEMO)


def install_remotion() -> None:
    # Remotion pobrałby własną przeglądarkę; podajemy tę z obrazu (--browser-executable, env niżej)
    ensure_node(REMOTION_PKGS)


def install_shotcraft() -> None:
    install_remotion()
    ensure_node([PUPPETEER])
    ensure_chrome_wrapper()
    clone_pinned(SHOTCRAFT_REPO, SHOTCRAFT_REV, SHOTCRAFT, SHOTCRAFT_POMIN)
    tpl = SHOTCRAFT / "template"
    if not (tpl / "node_modules" / ".jarvo-ok").exists():
        run(["npm", "ci", "--no-audit", "--no-fund", "--silent"], cwd=tpl, env=NO_DOWNLOAD)
        (tpl / "node_modules" / ".jarvo-ok").touch()


def install_mg() -> None:
    install_html()
    ensure_node(MG_LIBS)
    clone_pinned(MGSTYLES_REPO, MGSTYLES_REV, MGSTYLES, MGSTYLES_POMIN, keep=MG_DODANE)
    napraw_indeks_sampli()
    for uwaga in kroje_mg(MGSTYLES):
        print(f"! {uwaga}", file=sys.stderr)


def sample_mg() -> Path:
    return MGSTYLES / MG_SAMPLE.strip("/")


def napraw_indeks_sampli(katalog: Path | None = None) -> int:
    """index.json sampli mgaudio wymienia 598 plików z 40 instrumentów, a repo ma 102 z 15: przepis, który sięgnie
    po brakujący (np. lofi po kalimbę, guofeng po cytrę dantranh), kończy się błędem otwarcia pliku. Zostawiamy
    w indeksie tylko pliki, które są; instrument bez plików znika, więc mgaudio bierze wtedy swoją syntezę
    (`available()` = False). Zwraca liczbę usuniętych wpisów (0 = indeks już zgodny albo sampli nie ma)."""
    katalog = katalog or sample_mg()
    plik = katalog / "index.json"
    if not plik.exists():
        return 0
    indeks = json.loads(plik.read_text(encoding="utf-8"))
    zgodny = {k: [w for w in v if (katalog / w["file"]).is_file()] for k, v in indeks.items()}
    zgodny = {k: v for k, v in zgodny.items() if v}
    usuniete = sum(map(len, indeks.values())) - sum(map(len, zgodny.values()))
    if usuniete:
        plik.write_text(json.dumps(zgodny, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"↪ indeks sampli mgaudio: {usuniete} wpisów bez pliku usunięte, zostało {len(zgodny)} instrumentów", flush=True)
    return usuniete


def indeks_sampli_zgodny(katalog: Path | None = None) -> bool:
    katalog = katalog or sample_mg()
    try:
        indeks = json.loads((katalog / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(indeks) and all((katalog / w["file"]).is_file() for v in indeks.values() for w in v)


def mgaudio_gotowe() -> bool:
    """Kod i sample z przypiętego commitu, indeks sampli bez brakujących plików i venv z pakietami mgaudio."""
    pakiety = ("numba", "scipy", "pedalboard", "pyloudnorm", "soundfile")
    return ((MGSTYLES / ".git").exists() and git_head(MGSTYLES) == MGSTYLES_REV
            and (MGSTYLES / "lib/audio/mgaudio/__init__.py").exists() and indeks_sampli_zgodny()
            and (MGAUDIO_VENV / "bin" / "python").exists()
            and all(any((MGAUDIO_VENV / "lib").glob(f"python3*/site-packages/{m}*")) for m in pakiety))


def install_mgaudio() -> None:
    clone_pinned(MGSTYLES_REPO, MGSTYLES_REV, MGSTYLES, MGSTYLES_POMIN, keep=MG_DODANE)
    lista = subprocess.run(["git", "-C", str(MGSTYLES), "sparse-checkout", "list"], capture_output=True, text=True).stdout
    if MG_SAMPLE not in lista.splitlines():
        run(["git", "-C", str(MGSTYLES), "sparse-checkout", "add", MG_SAMPLE])
    napraw_indeks_sampli()
    ensure_venv(MGAUDIO_PY, MGAUDIO_VENV)


def install_lottie() -> None:
    install_html()
    clone_pinned(LOTTIE_REPO, LOTTIE_REV, LOTTIE, ["/assets/", "/skills/"])
    if not (LOTTIE / "public" / "canvaskit.wasm").exists():    # postinstall kopiuje canvaskit.wasm do public/
        run(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=LOTTIE, env=NO_DOWNLOAD)


def install_anidoodle() -> None:
    # projekt anidoodle ma własne package.json (scaffold); tu tylko rozgrzewamy cache npm, żeby `npm install` w projekcie
    # szło bez sieci, i sprawdzamy, że przeglądarka z obrazu pasuje do playwright-core z projektu
    ensure_node([f"playwright-core@{PW_VERSION}", "esbuild@0.25.12", "typescript@5.9.3"])


ANIMACJA_SKILL = Path(os.environ.get("HERMES_HOME", str(Path.home()))) / "skills" / "video" / "claude-animation"


def install_animacja() -> None:
    # claude-animation: Node canvas bez przeglądarki; jedyna zależność @napi-rs/canvas (prebuilt, bez kompilacji).
    # Importy ESM szukają pakietów obok pliku, więc skill dostaje link node_modules → wspólne node_modules.
    ensure_node(["@napi-rs/canvas@0.1.80"])
    if ANIMACJA_SKILL.is_dir():
        link(ANIMACJA_SKILL)


def canvaskit_dir() -> Path:
    return LOTTIE / "node_modules" / "canvaskit-wasm" / "bin" / "full"


def venv_has(module: str) -> bool:
    return any((VENV / "lib").glob(f"python3*/site-packages/{module}/__init__.py")) if (VENV / "lib").is_dir() else False


def status() -> dict:
    ff = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout if shutil.which("ffmpeg") else ""
    node_v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip() if shutil.which("node") else None
    hdri = LEMO / "core" / "assets" / "polyhaven"
    instruments = LEMO / "core" / "audio" / "instruments"
    return {
        "katalog": str(ROOT), "node": node_v, "ffmpeg": bool(ff), "prores_ks": "prores_ks" in ff,
        "przegladarka": headless_shell(), "playwright": (NODE / "node_modules" / "playwright").exists(),
        "venv": (VENV / "bin" / "python").exists(),
        "motion": (NODE / "node_modules" / "playwright").exists() and (VENV / "bin" / "python").exists(),
        "html": venv_has("playwright") and venv_has("PIL"),
        "html_biblioteki": all(npm_installed(p, NODE / "node_modules") for p in HTML_LIBS)
                           and all((JARVO_JS / n).exists() for n in JARVO_JS_PLIKI),
        # gotowe = przypięty commit i pakiety ze znacznikami setup.sh; po zmianie LEMO_REV → `instaluj lemo` aktualizuje
        "lemo": (LEMO / ".git").exists() and git_head(LEMO) == LEMO_REV and all(map(lemo_gotowe, [None, *lemo_poziomy()])),
        "lemo_hdri": hdri.is_dir() and any(hdri.glob("*.hdr")),
        "lemo_glos_kokoro": (LEMO / "core" / "tts" / "kokoro-v1.0.onnx").exists(),
        "lemo_sample": instruments.is_dir() and any(instruments.iterdir()),
        "anidoodle": (NODE / "node_modules" / "esbuild").exists(),
        "animacja": (NODE / "node_modules" / "@napi-rs" / "canvas").exists(),
        "remotion": (NODE / "node_modules" / "@remotion" / "cli").exists(),
        "puppeteer": (NODE / "node_modules" / "puppeteer").exists(),
        # indeks kart galerii: bez niego skill nie sprawdzi nazwy karty (starsze instalacje go pomijały)
        "shotcraft": (SHOTCRAFT / "template" / "node_modules" / ".jarvo-ok").exists()
                     and (SHOTCRAFT / "gallery" / "api" / "library.json").exists(),
        "lottie": (LOTTIE / "public" / "canvaskit.wasm").exists() and (canvaskit_dir() / "canvaskit.js").exists(),
        # wzory stylów: przypięty commit, notatki stylów i biblioteki dem
        "mg": (MGSTYLES / ".git").exists() and git_head(MGSTYLES) == MGSTYLES_REV and (MGSTYLES / "prompts").is_dir()
              and (MGSTYLES / MG_CJK).exists() and all(npm_installed(p, NODE / "node_modules") for p in MG_LIBS),
        # muzyka kodem (dodatek): kod i sample z przypiętego commitu, indeks sampli bez brakujących plików, venv
        "mgaudio": mgaudio_gotowe(),
        "pelne_lemo": full_extras(),
    }


TOOLS = ("motion", "lemo", "anidoodle", "animacja", "remotion", "shotcraft", "html", "lottie", "mg", "mgaudio")


def env_for(tool: str) -> dict:
    base = {"PLAYWRIGHT_BROWSERS_PATH": browsers_path(), **NO_DOWNLOAD}
    shell = headless_shell() or ""
    chrome = str(CHROME_WRAPPER) if shell and CHROME_WRAPPER.exists() else shell     # dla puppeteer i CHROME_BIN
    real = {"JARVO_CHROME_REAL": shell} if shell else {}
    if tool in ("motion", "html", "mg"):
        env = {**base, "NODE_PATH": str(NODE / "node_modules"), "PYTHON": py(),
               "PATH": f"{VENV / 'bin'}:{os.environ.get('PATH', '')}"}
        if tool == "motion":
            return env
        env = {**env, **real, "CHROME_BIN": chrome, "PUPPETEER_EXECUTABLE_PATH": chrome}
        return {**env, "MGSTYLES": str(MGSTYLES)} if tool == "mg" else env
    if tool == "lemo":
        return {**base, "LEMO_OPUSCAR_HOME": str(LEMO), "LIB": str(LEMO), **({"PLAYWRIGHT_CHROME": shell} if shell else {})}
    if tool == "anidoodle":
        return {**base, "npm_config_prefer_offline": "true", "npm_config_omit": "optional"}
    if tool == "animacja":
        if ANIMACJA_SKILL.is_dir():
            link(ANIMACJA_SKILL)
        return {"NODE_PATH": str(NODE / "node_modules"), "ANIM": str(ANIMACJA_SKILL),
                "CLAUDE_ANIMATION_LIB": str(ANIMACJA_SKILL / "lib")}
    if tool in ("remotion", "shotcraft"):
        env = {**base, "NODE_PATH": str(NODE / "node_modules"), **real, "CHROME_BIN": chrome, "PUPPETEER_EXECUTABLE_PATH": chrome,
               "REMOTION_BROWSER_EXECUTABLE": shell, "npm_config_prefer_offline": "true"}
        return {**env, "SHOTCRAFT": str(SHOTCRAFT)} if tool == "shotcraft" else env
    if tool == "lottie":
        return {**base, "LOTTIE_PLAYER": str(LOTTIE), "PYTHON": py(), **real, "CHROME_BIN": chrome,
                "PATH": f"{VENV / 'bin'}:{os.environ.get('PATH', '')}"}
    if tool == "mgaudio":
        # muzyka.py sama przechodzi na ten Python; MGAUDIO = katalog do sys.path przy własnym kodzie z mgaudio
        return {"MGAUDIO": str(MGSTYLES / "lib" / "audio"), "MGAUDIO_PY": str(MGAUDIO_VENV / "bin" / "python")}
    raise SystemExit(f"nieznane narzędzie: {tool!r} ({' | '.join(TOOLS)})")


def link(target: Path) -> Path:
    """<katalog>/node_modules → wspólne node_modules (import w .mjs szuka pakietów obok pliku, nie w NODE_PATH)."""
    target.mkdir(parents=True, exist_ok=True)
    nm = target / "node_modules"
    if nm.is_symlink() or not nm.exists():
        if nm.is_symlink():
            nm.unlink()
        nm.symlink_to(NODE / "node_modules", target_is_directory=True)
    return nm


POLSKIE = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
GOOGLE_FONTS_REPO = "https://github.com/google/fonts.git"


def znaki_kroju(path: Path) -> set[int]:
    """Kody znaków z tabeli cmap pliku TTF/OTF (formaty 4 i 12), bez dodatkowych bibliotek."""
    data = path.read_bytes()
    u16 = lambda o: struct.unpack_from(">H", data, o)[0]                  # noqa: E731
    cmap = next((struct.unpack_from(">II", data, 12 + 16 * i + 8) for i in range(u16(4))
                 if data[12 + 16 * i:16 + 16 * i] == b"cmap"), None)
    kody: set[int] = set()
    if not cmap:
        return kody
    off = cmap[0]
    for i in range(u16(off + 2)):
        s = off + struct.unpack_from(">I", data, off + 8 + 8 * i)[0]
        fmt = u16(s)
        if fmt == 4:
            seg = u16(s + 6) // 2
            ends, starts = s + 14, s + 16 + 2 * seg
            deltas, ranges = starts + 2 * seg, starts + 4 * seg
            for k in range(seg):
                a, b = u16(starts + 2 * k), u16(ends + 2 * k)
                delta, ro = struct.unpack_from(">h", data, deltas + 2 * k)[0], u16(ranges + 2 * k)
                for c in range(a, min(b, 0xFFFE) + 1):
                    g = (c + delta) & 0xFFFF if ro == 0 else u16(ranges + 2 * k + ro + 2 * (c - a))
                    if g:
                        kody.add(c)
        elif fmt == 12:
            for k in range(struct.unpack_from(">I", data, s + 12)[0]):
                a, b, _ = struct.unpack_from(">III", data, s + 16 + 12 * k)
                kody.update(range(a, b + 1))
    return kody


class GoogleFonts:
    """Kroje OFL z repo google/fonts przez git (bez API GitHuba, które ma limit zapytań): płytki klon bez plików
    w ROOT/google-fonts (same drzewa katalogów), plik kroju dociągany dopiero przy odczycie."""

    def __init__(self, repo: Path | None = None) -> None:
        self.repo = repo or ROOT / "google-fonts"
        self.odswiezone = False

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True)

    def pliki(self, rodzina: str, licencja: str = "ofl") -> list[str]:
        if not (self.repo / "HEAD").exists():
            self.repo.parent.mkdir(parents=True, exist_ok=True)
            run(["git", "clone", "--quiet", "--bare", "--depth=1", "--filter=blob:none", GOOGLE_FONTS_REPO, str(self.repo)])
            self.odswiezone = True
        out = self._git("ls-tree", "--name-only", "HEAD", f"{licencja}/{rodzina}/").stdout.decode()
        if not out and not self.odswiezone:                  # rodzina nowsza niż nasza kopia: raz odśwież
            self._git("fetch", "--quiet", "--depth=1", "origin", "+HEAD:HEAD")
            self.odswiezone = True
            out = self._git("ls-tree", "--name-only", "HEAD", f"{licencja}/{rodzina}/").stdout.decode()
        return [line.rsplit("/", 1)[-1] for line in out.splitlines()]

    def plik(self, rodzina: str, nazwa: str, licencja: str = "ofl") -> bytes:
        p = self._git("cat-file", "blob", f"HEAD:{licencja}/{rodzina}/{nazwa}")
        if p.returncode:
            raise OSError(p.stderr.decode().strip() or f"brak {licencja}/{rodzina}/{nazwa}")
        return p.stdout


def dopasuj_kroj(nazwa: str, pliki: list[str]) -> str | None:
    """Plik z katalogu google/fonts dla nazwy z fonts.css: dokładny, a inaczej zmienny (`Rodzina[wght].ttf`,
    z kursywą, gdy nazwa ją ma), a gdy go brak, statyczny o tym samym stylu (`-Bold`); nazwa bez stylu bierze
    Regular/Italic. Innej grubości nie podstawia (Black zamiast Regular zmieniłby wygląd po cichu)."""
    if nazwa in pliki:
        return nazwa
    kursywa = "italic" in nazwa.lower()
    ttf = sorted(p for p in pliki if p.lower().endswith((".ttf", ".otf")) and ("italic" in p.lower()) == kursywa)
    zmienne = [p for p in ttf if "[" in p]
    if zmienne:
        return zmienne[0]
    styl = re.search(r"-([A-Za-z]+)\.(?:ttf|otf)$", nazwa)
    kandydat = styl.group(1) if styl else ("Italic" if kursywa else "Regular")
    trafione = [p for p in ttf if p.rsplit(".", 1)[0].endswith("-" + kandydat)]
    if trafione:
        return trafione[0]
    return None if styl or len(ttf) != 1 else ttf[0]


def kroje(katalog: Path, zrodlo: GoogleFonts | None = None) -> list[str]:
    """Kroje wymienione w <katalog>/fonts.css, których nie ma obok: pobiera z github.com/google/fonts (OFL) razem
    z licencją i sprawdza polskie znaki w każdym. Zwraca uwagi; pusta lista = wszystko jest i ma polskie znaki."""
    css = (katalog / "fonts.css").read_text(encoding="utf-8")
    zrodlo = zrodlo or GoogleFonts()
    uwagi, katalogi = [], {}
    for nazwa in dict.fromkeys(re.findall(r"url\(\s*['\"]?([^'\")]+?)['\"]?\s*\)", css)):
        if "/" in nazwa or not nazwa.lower().endswith((".ttf", ".otf")):
            continue
        cel = katalog / nazwa
        if not cel.exists():
            rodzina = re.split(r"[-.\[]", nazwa)[0].lower()
            if rodzina not in katalogi:
                katalogi[rodzina] = zrodlo.pliki(rodzina)
            pliki = katalogi[rodzina]
            wybor = dopasuj_kroj(nazwa, pliki)
            if not wybor:
                uwagi.append(f"{nazwa}: nie ma go w google/fonts (ofl/{rodzina}); pobierz ręcznie albo zmień krój")
                continue
            cel.write_bytes(zrodlo.plik(rodzina, wybor))
            licencje = {p.name.lower() for p in katalog.glob("*.txt")}       # OFL-Rodzina.txt albo OFL.txt obok
            if "OFL.txt" in pliki and not licencje & {f"ofl-{rodzina}.txt", "ofl.txt"}:
                (katalog / f"OFL-{rodzina}.txt").write_bytes(zrodlo.plik(rodzina, "OFL.txt"))
            print(f"↓ {nazwa} ← google/fonts ofl/{rodzina}/{wybor}", flush=True)
        brak = [z for z in POLSKIE if ord(z) not in znaki_kroju(cel)]
        if brak:
            uwagi.append(f"{nazwa}: brak polskich znaków {''.join(brak)} (przeglądarka podstawi inny krój): "
                         "zmień krój na taki z polskimi znakami")
    return uwagi


MG_CJK = "assets/fonts/cjk/notosanssc/NotoSansSC-VF.ttf"   # jeden krój chiński zamiast tych spoza google/fonts
MG_BEZ_POBIERANIA = {"notoserifsc"}                         # 25 MB tylko na chińskie podpisy: zastępuje go MG_CJK


def kroje_mg(mg: Path, zrodlo: GoogleFonts | None = None) -> list[str]:
    """Kroje wzorów mg-styles-15 (autor nie dał plików, a bez nich część wzorów nie startuje): z fonts.css
    i ścieżek w kodzie wzorów (`/demos/<wzór>/…ttf`). Każdy, który jest w google/fonts (OFL albo Apache-2.0),
    pobiera z licencją obok; chińskie spoza google/fonts (licencje producentów: Alibaba, Huawei, Douyin…)
    to dowiązania do jednego Noto Sans SC. Nasze filmy piszemy po polsku, chiński krój wzoru jest tylko
    do obejrzenia. Zwraca uwagi o krojach, których nie ma skąd wziąć."""
    zrodlo = zrodlo or GoogleFonts()
    url = r"url\(\s*['\"]?(/[^'\")]+?\.(?:ttf|otf))['\"]?\s*\)"
    sciezki = re.findall(url, (mg / "assets/fonts/fonts.css").read_text(encoding="utf-8"))
    for kod in sorted((mg / "demos").glob("*/**/*")):
        if kod.suffix in (".html", ".js", ".mjs", ".css") and kod.is_file():
            sciezki += re.findall(r"['\"(](/demos/[^'\")]+?\.(?:ttf|otf))['\")]", kod.read_text(encoding="utf-8", errors="replace"))
    uwagi, zastepcze = [], []
    for sciezka in dict.fromkeys(sorted(sciezki, key=lambda s: s != "/" + MG_CJK)):     # najpierw krój zastępczy
        cel = mg / sciezka.lstrip("/")
        if cel.exists() or cel.is_symlink():
            continue
        grupa = cel.parent.parent.name
        rodzina = cel.parent.name if grupa in ("latin", "cjk") else re.split(r"[-.\[]", cel.name)[0].lower()
        wybor, licencja = None, "ofl"
        if rodzina not in MG_BEZ_POBIERANIA:
            for licencja in ("ofl", "apache"):
                wybor = dopasuj_kroj(cel.name, zrodlo.pliki(rodzina, licencja))
                if wybor:
                    break
        cel.parent.mkdir(parents=True, exist_ok=True)
        if wybor:
            cel.write_bytes(zrodlo.plik(rodzina, wybor, licencja))
            lic = "OFL.txt" if licencja == "ofl" else "LICENSE.txt"
            nazwa_lic = lic if grupa in ("latin", "cjk") else f"{lic[:-4]}-{rodzina}.txt"
            if not (cel.parent / nazwa_lic).exists():
                (cel.parent / nazwa_lic).write_bytes(zrodlo.plik(rodzina, lic, licencja))
            print(f"↓ {sciezka} ← google/fonts {licencja}/{rodzina}/{wybor}", flush=True)
        elif grupa == "cjk" and (mg / MG_CJK).exists():
            cel.symlink_to(os.path.relpath(mg / MG_CJK, cel.parent))
            zastepcze.append(cel.name)
        else:
            uwagi.append(f"{sciezka}: nie ma go w google/fonts; wzór narysuje go krojem zastępczym albo nie wystartuje")
    if zastepcze:
        print(f"↪ Noto Sans SC zamiast: {', '.join(zastepcze)}", flush=True)
    return uwagi


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    cmd = args[0]
    if cmd == "sprawdz":
        print(json.dumps(status(), ensure_ascii=False, indent=1))
        return 0
    if cmd == "env":
        for k, v in env_for(args[1] if len(args) > 1 else "").items():
            print(f"export {k}={json.dumps(v)}")
        return 0
    if cmd == "kroje":
        if len(args) < 2:
            raise SystemExit("kroje <katalog z fonts.css>")
        try:
            uwagi = kroje(Path(args[1]))
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"! nie mogę pobrać krojów z google/fonts: {e}", file=sys.stderr)
            return 1
        print("\n".join(f"! {u}" for u in uwagi) or "kroje gotowe, wszystkie z polskimi znakami")
        return 1 if uwagi else 0
    if cmd == "link":
        if len(args) < 2:
            raise SystemExit("link <katalog>")
        print(link(Path(args[1])))
        return 0
    if cmd == "instaluj":
        what = args[1] if len(args) > 1 else "wszystko"
        steps = {"motion": [install_motion], "lemo": [install_lemo], "anidoodle": [install_anidoodle], "animacja": [install_animacja],
                 "remotion": [install_remotion], "shotcraft": [install_shotcraft], "html": [install_html],
                 "lottie": [install_lottie], "mg": [install_mg], "mgaudio": [install_mgaudio],
                 "wszystko": [install_motion, install_html, install_anidoodle, install_animacja, install_lemo, install_shotcraft,
                              install_lottie, install_mg, *([install_mgaudio] if dodatek("mgaudio") else [])]}.get(what)
        if not steps:
            raise SystemExit(f"instaluj: {' | '.join(TOOLS)} | wszystko")
        if not headless_shell():
            print(f"! brak chromium_headless_shell w {browsers_path()}: narzędzia pobiorą własną przeglądarkę", file=sys.stderr)
        for step in steps:
            step()
        print(json.dumps(status(), ensure_ascii=False, indent=1))
        return 0
    raise SystemExit(f"nieznane polecenie: {cmd}")


if __name__ == "__main__":
    sys.exit(main())
