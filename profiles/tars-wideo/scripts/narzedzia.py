#!/usr/bin/env python3
"""Narzędzia „wideo z kodu”: sprawdzenie i instalacja raz, we wspólnym katalogu.

    python3 narzedzia.py sprawdz                 # co jest gotowe, czego brak (JSON)
    python3 narzedzia.py instaluj [motion|lemo|anidoodle|remotion|shotcraft|html|lottie|wszystko]
    python3 narzedzia.py env <narzedzie>         # zmienne środowiska do wklejenia: eval "$(python3 narzedzia.py env motion)"
    python3 narzedzia.py link <katalog>          # <katalog>/node_modules → wspólne (skrypty .mjs nie czytają NODE_PATH)

Narzędzia: motion (motion-broll), lemo (lemo-opuscar), anidoodle, remotion (skill remotion-best-practices, iart),
shotcraft (video-shotcraft na Remotion), html (html_wideo.py: animacja HTML → klatki / MP4; pixel2motion, iart,
bang-motion), lottie (oficjalny player Skottie do text-to-lottie + eksport przez html_wideo.py lottie).

Zasady (VPS 8 GB, bez dubli):
- przeglądarka: Chromium headless z obrazu Hermesa (PLAYWRIGHT_BROWSERS_PATH), nic nie pobieramy; wersja
  playwright (Node i Python) przypięta do tej przeglądarki (PW_VERSION),
- pakiety npm i Python raz do /opt/data/tars/narzedzia (przeżywają restart), a nie w każdym projekcie,
- biblioteki z repo (lemo-opuscar, video-shotcraft, player Lottie) przypięte do commitów z vendor/skills.lock.yaml
  (bez samoczynnych aktualizacji); HDRI do stylów 3D lemo (~12 MB) zawsze; ciężkie assety lemo (głos Kokoro
  ~340 MB, sample ~1,35 GB) tylko z TARS_EXTRAS „lemo”.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("TARS_NARZEDZIA", "/opt/data/tars/narzedzia" if Path("/opt/data/tars").is_dir()
                           else str(Path.home() / ".cache" / "tars-narzedzia")))
NODE = ROOT / "node"                  # wspólne node_modules (playwright dla motion-broll, cache npm dla projektów)
VENV = ROOT / "venv"                  # Python z numpy/pillow/playwright… dla skryptów narzędzi
PW_VERSION = "1.63.0"                 # = chromium_headless_shell z obrazu Hermesa (Node i Python)

LEMO = ROOT / "lemo-opuscar"
LEMO_REPO = "https://github.com/lemomo-ai/lemo-opuscar.git"
LEMO_REV = "108fa78e8468df90a94f3860099484e412447199"        # vendor/skills.lock.yaml → lemo-opuscar
SHOTCRAFT = ROOT / "video-shotcraft"
SHOTCRAFT_REPO = "https://github.com/Vincentwei1021/video-shotcraft.git"
SHOTCRAFT_REV = "e2d8928c57ef84701f9b0119ca4a1c28a62050c1"   # vendor/skills.lock.yaml → video-shotcraft
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
# biblioteki własnych animacji HTML (kontrakt `tars`): html_wideo.py serwuje je pod /_lib/, bez CDN
# (three: MIT; gsap: „Standard no-charge license”, darmowa także komercyjnie)
HTML_LIBS = ["three@0.186.1", "gsap@3.15.0"]
PY_BASE = ["numpy", "pillow"]
PY_HTML = [f"playwright=={PW_VERSION}"]
PY_LEMO = ["scipy", "soundfile", "soxr", "librosa"]
PY_LEMO_FULL = ["kokoro-onnx", "faster-whisper"]
PY_MODULES = {"pillow": "PIL", "kokoro-onnx": "kokoro_onnx", "faster-whisper": "faster_whisper"}
NO_DOWNLOAD = {"PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1", "PUPPETEER_SKIP_DOWNLOAD": "1"}
# puppeteer i `chrome --headless --screenshot` nie dodają --no-sandbox, a Chromium jako root bez niego nie wstaje
# (playwright i Remotion dodają same); nakładka czyta prawdziwą ścieżkę z TARS_CHROME_REAL (env), więc nie starzeje się
CHROME_WRAPPER = ROOT / "bin" / "chrome-no-sandbox"
CHROME_WRAPPER_SH = """#!/bin/sh
# Chromium z obrazu Hermesa z --no-sandbox (narzedzia.py env ustawia TARS_CHROME_REAL)
exec "${TARS_CHROME_REAL:?brak TARS_CHROME_REAL: najpierw eval narzedzia.py env html}" --no-sandbox "$@"
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


def full_extras() -> bool:
    return "lemo" in os.environ.get("TARS_EXTRAS", "").replace(",", " ").split()


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print("▶", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, env={**os.environ, **(env or {})})


def py() -> str:
    return str(VENV / "bin" / "python")


def py_module(spec: str) -> str:
    """Nazwa modułu do importu dla specyfikacji pip („playwright==1.63.0” → playwright, „pillow” → PIL)."""
    name = re.split(r"[=<>!~\[]", spec, maxsplit=1)[0].strip()
    return PY_MODULES.get(name, name.replace("-", "_"))


def pip_install(python: str, pkgs: list[str]) -> None:
    if shutil.which("uv"):
        run(["uv", "pip", "install", "--quiet", "--python", python, *pkgs])
    else:
        run([python, "-m", "pip", "install", "--quiet", *pkgs])


def ensure_venv(pkgs: list[str]) -> None:
    if not (VENV / "bin" / "python").exists():
        if shutil.which("uv"):
            run(["uv", "venv", "--quiet", "--python", "3.12", str(VENV)])
        else:
            run([sys.executable, "-m", "venv", str(VENV)])
    missing = [p for p in pkgs if subprocess.run([py(), "-c", f"import {py_module(p)}"], capture_output=True).returncode != 0]
    if missing:
        pip_install(py(), missing)


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


def clone_pinned(repo: str, rev: str, dest: Path, exclude: list[str]) -> None:
    if (dest / ".git").exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--quiet", "--filter=blob:none", "--sparse", "--no-checkout", repo, str(dest)])
    run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone", "/*", *[f"!{e}" for e in exclude]])
    run(["git", "-C", str(dest), "checkout", "--quiet", rev])


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


def install_lemo() -> None:
    clone_pinned(LEMO_REPO, LEMO_REV, LEMO, ["/styles/*/demo/", "/styleboard/"])
    # przypięta wersja: skill-owy setup.sh nie aktualizuje biblioteki, której nie oznaczył jako swojej
    subprocess.run(["git", "-C", str(LEMO), "config", "--unset", "lemo.managed"], capture_output=True)
    if not (LEMO / "node_modules" / ".lemo-ok").exists():
        run(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=LEMO, env=NO_DOWNLOAD)
        (LEMO / "node_modules" / ".lemo-ok").touch()
    lemo_venv = LEMO / ".venv"
    if not (lemo_venv / ".lemo-ok").exists():
        if not (lemo_venv / "bin" / "python").exists():
            run(["uv", "venv", "--quiet", "--python", "3.12", str(lemo_venv)] if shutil.which("uv")
                else [sys.executable, "-m", "venv", str(lemo_venv)])
        pip_install(str(lemo_venv / "bin" / "python"), PY_BASE + PY_LEMO + (PY_LEMO_FULL if full_extras() else []))
        (lemo_venv / ".lemo-ok").touch()
    # HDRI (Poly Haven, CC0, ~12 MB): światło i odbicia w stylach 3D (brick-toy, paper-popup, paper-lantern…) – zawsze
    if not (LEMO / "core" / "assets" / "polyhaven").is_dir() or not any((LEMO / "core" / "assets" / "polyhaven").glob("*.hdr")):
        run(["sh", "tools/fetch.sh", "hdri"], cwd=LEMO)
    if full_extras():
        for what in ("voice", "instruments"):
            run(["sh", "tools/fetch.sh", what], cwd=LEMO)


def install_remotion() -> None:
    # Remotion pobrałby własną przeglądarkę; podajemy tę z obrazu (--browser-executable, env niżej)
    ensure_node(REMOTION_PKGS)


def install_shotcraft() -> None:
    install_remotion()
    ensure_node([PUPPETEER])
    ensure_chrome_wrapper()
    clone_pinned(SHOTCRAFT_REPO, SHOTCRAFT_REV, SHOTCRAFT, ["/gallery/"])
    tpl = SHOTCRAFT / "template"
    if not (tpl / "node_modules" / ".tars-ok").exists():
        run(["npm", "ci", "--no-audit", "--no-fund", "--silent"], cwd=tpl, env=NO_DOWNLOAD)
        (tpl / "node_modules" / ".tars-ok").touch()


def install_lottie() -> None:
    install_html()
    clone_pinned(LOTTIE_REPO, LOTTIE_REV, LOTTIE, ["/assets/", "/skills/"])
    if not (LOTTIE / "public" / "canvaskit.wasm").exists():    # postinstall kopiuje canvaskit.wasm do public/
        run(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=LOTTIE, env=NO_DOWNLOAD)


def install_anidoodle() -> None:
    # projekt anidoodle ma własne package.json (scaffold); tu tylko rozgrzewamy cache npm, żeby `npm install` w projekcie
    # szło bez sieci, i sprawdzamy, że przeglądarka z obrazu pasuje do playwright-core z projektu
    ensure_node([f"playwright-core@{PW_VERSION}", "esbuild@0.25.12", "typescript@5.9.3"])


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
        "html_biblioteki": all(npm_installed(p, NODE / "node_modules") for p in HTML_LIBS),
        "lemo": (LEMO / "node_modules" / ".lemo-ok").exists() and (LEMO / ".venv" / ".lemo-ok").exists(),
        "lemo_hdri": hdri.is_dir() and any(hdri.glob("*.hdr")),
        "lemo_glos_kokoro": (LEMO / "core" / "tts" / "kokoro-v1.0.onnx").exists(),
        "lemo_sample": instruments.is_dir() and any(instruments.iterdir()),
        "anidoodle": (NODE / "node_modules" / "esbuild").exists(),
        "remotion": (NODE / "node_modules" / "@remotion" / "cli").exists(),
        "puppeteer": (NODE / "node_modules" / "puppeteer").exists(),
        "shotcraft": (SHOTCRAFT / "template" / "node_modules" / ".tars-ok").exists(),
        "lottie": (LOTTIE / "public" / "canvaskit.wasm").exists() and (canvaskit_dir() / "canvaskit.js").exists(),
        "pelne_lemo": full_extras(),
    }


TOOLS = ("motion", "lemo", "anidoodle", "remotion", "shotcraft", "html", "lottie")


def env_for(tool: str) -> dict:
    base = {"PLAYWRIGHT_BROWSERS_PATH": browsers_path(), **NO_DOWNLOAD}
    shell = headless_shell() or ""
    chrome = str(CHROME_WRAPPER) if shell and CHROME_WRAPPER.exists() else shell     # dla puppeteer i CHROME_BIN
    real = {"TARS_CHROME_REAL": shell} if shell else {}
    if tool in ("motion", "html"):
        env = {**base, "NODE_PATH": str(NODE / "node_modules"), "PYTHON": py(),
               "PATH": f"{VENV / 'bin'}:{os.environ.get('PATH', '')}"}
        return {**env, **real, "CHROME_BIN": chrome, "PUPPETEER_EXECUTABLE_PATH": chrome} if tool == "html" else env
    if tool == "lemo":
        return {**base, "LEMO_OPUSCAR_HOME": str(LEMO), "LIB": str(LEMO), **({"PLAYWRIGHT_CHROME": shell} if shell else {})}
    if tool == "anidoodle":
        return {**base, "npm_config_prefer_offline": "true", "npm_config_omit": "optional"}
    if tool in ("remotion", "shotcraft"):
        env = {**base, "NODE_PATH": str(NODE / "node_modules"), **real, "CHROME_BIN": chrome, "PUPPETEER_EXECUTABLE_PATH": chrome,
               "REMOTION_BROWSER_EXECUTABLE": shell, "npm_config_prefer_offline": "true"}
        return {**env, "SHOTCRAFT": str(SHOTCRAFT)} if tool == "shotcraft" else env
    if tool == "lottie":
        return {**base, "LOTTIE_PLAYER": str(LOTTIE), "PYTHON": py(), **real, "CHROME_BIN": chrome,
                "PATH": f"{VENV / 'bin'}:{os.environ.get('PATH', '')}"}
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
    if cmd == "link":
        if len(args) < 2:
            raise SystemExit("link <katalog>")
        print(link(Path(args[1])))
        return 0
    if cmd == "instaluj":
        what = args[1] if len(args) > 1 else "wszystko"
        steps = {"motion": [install_motion], "lemo": [install_lemo], "anidoodle": [install_anidoodle],
                 "remotion": [install_remotion], "shotcraft": [install_shotcraft], "html": [install_html],
                 "lottie": [install_lottie],
                 "wszystko": [install_motion, install_html, install_anidoodle, install_lemo, install_shotcraft,
                              install_lottie]}.get(what)
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
