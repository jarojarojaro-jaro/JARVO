#!/usr/bin/env python3
"""Narzędzia „wideo z kodu” (motion-broll, lemo-opuscar, anidoodle): sprawdzenie i instalacja raz, we wspólnym katalogu.

    python3 narzedzia.py sprawdz                 # co jest gotowe, czego brak (JSON)
    python3 narzedzia.py instaluj [motion|lemo|anidoodle|wszystko]
    python3 narzedzia.py env <narzedzie>         # zmienne środowiska do wklejenia: eval "$(python3 narzedzia.py env motion)"

Zasady (VPS 8 GB, bez dubli):
- przeglądarka: Chromium headless z obrazu Hermesa (PLAYWRIGHT_BROWSERS_PATH), nic nie pobieramy; wersja
  playwright przypięta do tej przeglądarki (PW_VERSION),
- pakiety npm i Python raz do /opt/data/tars/narzedzia (przeżywają restart), a nie w każdym projekcie,
- biblioteka lemo-opuscar przypięta do commita z vendor/skills.lock.yaml (bez samoczynnych aktualizacji);
  HDRI do stylów 3D (~12 MB) zawsze; ciężkie assety (głos Kokoro ~340 MB, sample ~1,35 GB) tylko z TARS_EXTRAS „lemo”.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("TARS_NARZEDZIA", "/opt/data/tars/narzedzia" if Path("/opt/data/tars").is_dir()
                           else str(Path.home() / ".cache" / "tars-narzedzia")))
NODE = ROOT / "node"                  # wspólne node_modules (playwright dla motion-broll, three dla lemo)
VENV = ROOT / "venv"                  # Python z numpy/scipy/pillow… dla skryptów narzędzi
LEMO = ROOT / "lemo-opuscar"
PW_VERSION = "1.63.0"                 # = chromium_headless_shell z obrazu Hermesa
LEMO_REPO = "https://github.com/lemomo-ai/lemo-opuscar.git"
LEMO_REV = "108fa78e8468df90a94f3860099484e412447199"   # vendor/skills.lock.yaml → lemo-opuscar
PY_BASE = ["numpy", "pillow"]
PY_LEMO = ["scipy", "soundfile", "soxr", "librosa"]
PY_LEMO_FULL = ["kokoro-onnx", "faster-whisper"]


def browsers_path() -> str:
    return os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/hermes/.playwright")


def headless_shell() -> str | None:
    base = Path(browsers_path())
    for d in sorted(base.glob("chromium_headless_shell-*"), reverse=True):
        exe = d / "chrome-headless-shell-linux64" / "chrome-headless-shell"
        if exe.exists():
            return str(exe)
    return None


def full_extras() -> bool:
    return "lemo" in os.environ.get("TARS_EXTRAS", "").replace(",", " ").split()


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print("▶", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, env={**os.environ, **(env or {})})


def py() -> str:
    return str(VENV / "bin" / "python")


def ensure_venv(pkgs: list[str]) -> None:
    if not (VENV / "bin" / "python").exists():
        if shutil.which("uv"):
            run(["uv", "venv", "--quiet", "--python", "3.12", str(VENV)])
        else:
            run([sys.executable, "-m", "venv", str(VENV)])
    mods = {"pillow": "PIL", "kokoro-onnx": "kokoro_onnx", "faster-whisper": "faster_whisper"}
    missing = [p for p in pkgs if subprocess.run([py(), "-c", f"import {mods.get(p, p)}"], capture_output=True).returncode != 0]
    if missing:
        if shutil.which("uv"):
            run(["uv", "pip", "install", "--quiet", "--python", py(), *missing])
        else:
            run([py(), "-m", "pip", "install", "--quiet", *missing])


def ensure_node(pkgs: list[str]) -> None:
    NODE.mkdir(parents=True, exist_ok=True)
    if not (NODE / "package.json").exists():
        (NODE / "package.json").write_text('{"private": true}\n', encoding="utf-8")
    missing = [p for p in pkgs if not (NODE / "node_modules" / p.rsplit("@", 1)[0]).exists()]
    if missing:
        run(["npm", "install", "--no-audit", "--no-fund", "--silent", *missing], cwd=NODE,
            env={"PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1"})


def install_motion() -> None:
    ensure_node([f"playwright@{PW_VERSION}"])
    ensure_venv(PY_BASE)


def install_lemo() -> None:
    if not (LEMO / "AGENTS.md").exists():
        LEMO.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", "--filter=blob:none", "--sparse", "--no-checkout", LEMO_REPO, str(LEMO)])
        run(["git", "-C", str(LEMO), "sparse-checkout", "set", "--no-cone", "/*", "!/styles/*/demo/", "!/styleboard/"])
        run(["git", "-C", str(LEMO), "checkout", "--quiet", LEMO_REV])
    # przypięta wersja: skill-owy setup.sh nie aktualizuje biblioteki, której nie oznaczył jako swojej
    subprocess.run(["git", "-C", str(LEMO), "config", "--unset", "lemo.managed"], capture_output=True)
    if not (LEMO / "node_modules" / ".lemo-ok").exists():
        run(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=LEMO, env={"PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1"})
        (LEMO / "node_modules" / ".lemo-ok").touch()
    lemo_venv = LEMO / ".venv"
    if not (lemo_venv / ".lemo-ok").exists():
        if not (lemo_venv / "bin" / "python").exists():
            run(["uv", "venv", "--quiet", "--python", "3.12", str(lemo_venv)] if shutil.which("uv")
                else [sys.executable, "-m", "venv", str(lemo_venv)])
        pkgs = PY_BASE + PY_LEMO + (PY_LEMO_FULL if full_extras() else [])
        run(["uv", "pip", "install", "--quiet", "--python", str(lemo_venv / "bin" / "python"), *pkgs] if shutil.which("uv")
            else [str(lemo_venv / "bin" / "python"), "-m", "pip", "install", "--quiet", *pkgs])
        (lemo_venv / ".lemo-ok").touch()
    # HDRI (Poly Haven, CC0, ~12 MB): światło i odbicia w stylach 3D (brick-toy, paper-popup, paper-lantern…) – zawsze
    if not (LEMO / "core" / "assets" / "polyhaven").is_dir() or not any((LEMO / "core" / "assets" / "polyhaven").glob("*.hdr")):
        run(["sh", "tools/fetch.sh", "hdri"], cwd=LEMO)
    if full_extras():
        for what in ("voice", "instruments"):
            run(["sh", "tools/fetch.sh", what], cwd=LEMO)


def install_anidoodle() -> None:
    # projekt anidoodle ma własne package.json (scaffold); tu tylko rozgrzewamy cache npm, żeby `npm install` w projekcie
    # szło bez sieci, i sprawdzamy, że przeglądarka z obrazu pasuje do playwright-core z projektu
    ensure_node([f"playwright-core@{PW_VERSION}", "esbuild@0.25.12", "typescript@5.9.3"])


def status() -> dict:
    ff = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout if shutil.which("ffmpeg") else ""
    node_v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip() if shutil.which("node") else None
    return {
        "katalog": str(ROOT), "node": node_v, "ffmpeg": bool(ff), "prores_ks": "prores_ks" in ff,
        "przegladarka": headless_shell(), "playwright": (NODE / "node_modules" / "playwright").exists(),
        "venv": (VENV / "bin" / "python").exists(),
        "motion": (NODE / "node_modules" / "playwright").exists() and (VENV / "bin" / "python").exists(),
        "lemo": (LEMO / "node_modules" / ".lemo-ok").exists() and (LEMO / ".venv" / ".lemo-ok").exists(),
        "lemo_hdri": any((LEMO / "core" / "assets" / "polyhaven").glob("*.hdr")) if (LEMO / "core" / "assets" / "polyhaven").is_dir() else False,
        "lemo_glos_kokoro": (LEMO / "core" / "tts" / "kokoro-v1.0.onnx").exists(),
        "lemo_sample": (LEMO / "core" / "audio" / "instruments").is_dir() and any((LEMO / "core" / "audio" / "instruments").iterdir()),
        "anidoodle": (NODE / "node_modules" / "esbuild").exists(),
        "pelne_lemo": full_extras(),
    }


def env_for(tool: str) -> dict:
    base = {"PLAYWRIGHT_BROWSERS_PATH": browsers_path(), "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1"}
    if tool == "motion":
        return {**base, "NODE_PATH": str(NODE / "node_modules"), "PYTHON": py(), "PATH": f"{VENV / 'bin'}:{os.environ.get('PATH', '')}"}
    if tool == "lemo":
        shell = headless_shell()
        return {**base, "LEMO_OPUSCAR_HOME": str(LEMO), "LIB": str(LEMO), **({"PLAYWRIGHT_CHROME": shell} if shell else {})}
    if tool == "anidoodle":
        return {**base, "npm_config_prefer_offline": "true", "npm_config_omit": "optional"}
    raise SystemExit(f"nieznane narzędzie: {tool} (motion | lemo | anidoodle)")


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
    if cmd == "instaluj":
        what = args[1] if len(args) > 1 else "wszystko"
        steps = {"motion": [install_motion], "lemo": [install_lemo], "anidoodle": [install_anidoodle],
                 "wszystko": [install_motion, install_anidoodle, install_lemo]}.get(what)
        if not steps:
            raise SystemExit("instaluj: motion | lemo | anidoodle | wszystko")
        if not headless_shell():
            print(f"! brak chromium_headless_shell w {browsers_path()}: narzędzia pobiorą własną przeglądarkę", file=sys.stderr)
        for step in steps:
            step()
        print(json.dumps(status(), ensure_ascii=False, indent=1))
        return 0
    raise SystemExit(f"nieznane polecenie: {cmd}")


if __name__ == "__main__":
    sys.exit(main())
