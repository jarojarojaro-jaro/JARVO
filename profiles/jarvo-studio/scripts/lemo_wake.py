#!/usr/bin/env python3
"""lemo-wake dla Studia: jedno zdjęcie albo grafika → pętla ok. 5 s (MP4, GIF, WebP) i rozbicie na warstwy (PSD).

    python3 lemo_wake.py sprawdz        # co gotowe (JSON): biblioteka, Python, playwright, przeglądarka, modele, zgoda
    python3 lemo_wake.py instaluj       # raz: klon na przypiętym commicie + pakiety (ok. 350 MB, bez modeli)
    python3 lemo_wake.py env            # eval "$(python3 lemo_wake.py env)": LW, LW_WARSTWY, LW_PY, LEMO_WAKE_MODELS, LW_HISTORIA

Biblioteka to sam skill z github.com/lemomo-ai/lemo-wake (wake + layers, bez upload: publikuje w cudzej galerii),
na tym samym commicie co kopia skilla w profilu (vendor/skills.lock.yaml → lemo-wake). Zasady jak narzedzia.py
Wideografa: wszystko raz do /opt/data/jarvo/narzedzia (przeżywa restart i wdrożenie), przeglądarka z obrazu Hermesa,
Python z przypiętymi pakietami zamiast `uv run --script` (ten bierze najnowsze wersje przy każdym uruchomieniu).
Modele ONNX (ok. 600 MB z Hugging Face) pobierają same skrypty skilla dopiero po zgodzie właściciela
(`models.py consent yes`); trzymamy je poza klonem, więc aktualizacja biblioteki ich nie rusza.
Licencja CC BY-NC 4.0: użycie komercyjne tylko za zgodą autora (skill `zywy-obraz`).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("JARVO_NARZEDZIA", "/opt/data/jarvo/narzedzia" if Path("/opt/data/jarvo").is_dir()
                           else str(Path.home() / ".cache" / "jarvo-narzedzia")))
LIB = ROOT / "lemo-wake"
DANE = ROOT / "lemo-wake-dane"          # modele, zgoda (models/consent.json) i historia filmów: poza klonem
REPO = "https://github.com/lemomo-ai/lemo-wake.git"
REV = "ebb758c66c61cf571b57d341ec3f5cbb4bf74d08"   # vendor/skills.lock.yaml → lemo-wake
# bez skilla upload (publikacja w galerii autora przez gh) i bez wersji chińskiej README
POMIN = ["/skills/upload/", "/README.zh-CN.md", "/.github/", "/.claude-plugin/"]
VENV = LIB / ".venv"
# zależności ze skryptów (`# /// script`), przypięte; opencv w linii 4.x (5.0 to nowa główna wersja)
PY_PAKIETY = ["numpy==2.5.3", "pillow==12.3.0", "pillow-heif==1.8.0", "psd-tools==1.23.0",
              "opencv-python-headless==4.14.0.94", "onnxruntime==1.30.0"]
SKRYPTY = LIB / "skills" / "wake" / "scripts"
PW_VERSION = "1.63.0"                   # = package-lock.json skilla = Chromium headless z obrazu Hermesa
# pliki modeli jak w _models.py skilla (nazwa: pliki)
MODELE = {
    "depth": ["depth_anything_v2_small.onnx"],
    "general": ["birefnet_lite.onnx"],
    "portrait": ["modnet.onnx"],
    "sam": ["mobile_sam_image_encoder.onnx", "sam_mask_decoder_multi.onnx"],
    "lama": ["lama_fp32.onnx"],
}


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("▶", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def git_head(dest: Path) -> str:
    return subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def klon(repo: str = REPO, rev: str = REV, dest: Path = LIB, pomin: list[str] = POMIN) -> None:
    """Klon bez historii plików, bez ścieżek `pomin`, na przypiętym commicie; nowy `rev` w repo Jarva przenosi klon."""
    if (dest / ".git").exists():
        if git_head(dest) != rev:
            run(["git", "-C", str(dest), "fetch", "--quiet", "--filter=blob:none", "origin", rev])
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", "--filter=blob:none", "--sparse", "--no-checkout", repo, str(dest)])
    wzorce = ["/*", *[f"!{p}" for p in pomin]]
    lista = subprocess.run(["git", "-C", str(dest), "sparse-checkout", "list"], capture_output=True, text=True).stdout
    if git_head(dest) == rev and lista.splitlines() == wzorce:
        return
    run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone", *wzorce])
    run(["git", "-C", str(dest), "checkout", "--quiet", "--force", rev])


def podpis(*czesci: str) -> str:
    return hashlib.sha256("\n".join(czesci).encode()).hexdigest()[:16]


def znacznik_py() -> Path:
    return VENV / ".jarvo-ok"           # podpis listy pinów: zmiana pinu w repo Jarva = doinstaluj


def znacznik_node() -> Path:
    return SKRYPTY / "node_modules" / ".jarvo-ok"   # podpis package-lock skilla


def python_gotowy() -> bool:
    return (VENV / "bin" / "python").exists() and _czytaj(znacznik_py()) == podpis(*PY_PAKIETY)


def node_gotowy() -> bool:
    lock = SKRYPTY / "package-lock.json"
    return lock.exists() and _czytaj(znacznik_node()) == podpis(lock.read_text(encoding="utf-8"))


def _czytaj(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def uv_zwolnienia(pakiety: list[str]) -> list[str]:
    """Obraz Hermesa trzyma nowe wydania w kwarantannie uv (14 dni); dokładne piny z niej zwalniamy (jak narzedzia.py)."""
    out: list[str] = []
    for spec in pakiety:
        if "==" in spec:
            out += ["--exclude-newer-package", f"{spec.split('==', 1)[0]}=false"]
    return out


def instaluj_python() -> None:
    python = VENV / "bin" / "python"
    if not python.exists():
        run(["uv", "venv", "--quiet", "--python", "3.12", str(VENV)] if shutil.which("uv")
            else [sys.executable, "-m", "venv", str(VENV)])
    if shutil.which("uv"):
        run(["uv", "pip", "install", "--quiet", "--python", str(python), *uv_zwolnienia(PY_PAKIETY), *PY_PAKIETY])
    else:
        run([str(python), "-m", "pip", "install", "--quiet", *PY_PAKIETY])
    znacznik_py().write_text(podpis(*PY_PAKIETY) + "\n", encoding="utf-8")


def instaluj_node() -> None:
    lock = SKRYPTY / "package-lock.json"
    wersja = json.loads(lock.read_text(encoding="utf-8")).get("packages", {}).get("node_modules/playwright-core", {}).get("version")
    if wersja != PW_VERSION:
        raise SystemExit(f"package-lock skilla ma playwright-core {wersja}, a przeglądarka z obrazu pasuje do {PW_VERSION}")
    # bez pobierania przeglądarek: Chromium headless jest w obrazie (PLAYWRIGHT_BROWSERS_PATH)
    os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    run(["npm", "ci", "--omit=dev", "--no-audit", "--no-fund", "--silent"], cwd=SKRYPTY)
    znacznik_node().write_text(podpis(lock.read_text(encoding="utf-8")) + "\n", encoding="utf-8")


def instaluj() -> None:
    klon()
    if not python_gotowy():
        instaluj_python()
    if not node_gotowy():
        instaluj_node()
    (DANE / "models").mkdir(parents=True, exist_ok=True)
    print(json.dumps(status(), ensure_ascii=False, indent=2))


def przegladarka() -> str | None:
    base = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/hermes/.playwright"))
    for d in sorted(base.glob("chromium_headless_shell-*"), key=lambda p: int(re.sub(r"\D", "", p.name) or 0), reverse=True):
        exe = d / "chrome-headless-shell-linux64" / "chrome-headless-shell"
        if exe.exists():
            return str(exe)
    return None


def zgoda() -> str:
    """Odpowiedź właściciela na pobranie modeli (consent.json skilla): tak / nie / nie-pytano."""
    try:
        odp = json.loads((DANE / "models" / "consent.json").read_text(encoding="utf-8"))["download"]
    except (OSError, ValueError, KeyError, TypeError):
        return "nie-pytano"
    return "tak" if odp is True else "nie" if odp is False else "nie-pytano"


def status() -> dict:
    modele = DANE / "models"
    return {
        "biblioteka": (LIB / ".git").exists() and git_head(LIB) == REV,
        "python": python_gotowy(),
        "playwright": node_gotowy(),
        "przegladarka": przegladarka(),
        "ffmpeg": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        "modele": {k: all((modele / f).exists() for f in pliki) for k, pliki in MODELE.items()},
        "zgoda_na_modele": zgoda(),
        "katalog": str(LIB),
    }


def env() -> dict[str, str]:
    out = {
        "LW": str(LIB / "skills" / "wake"),
        "LW_WARSTWY": str(LIB / "skills" / "layers"),
        "LW_PY": str(VENV / "bin" / "python"),
        "LEMO_WAKE_MODELS": str(DANE / "models"),
        "LW_HISTORIA": str(DANE / "history.jsonl"),
    }
    chrome = przegladarka()
    if chrome:
        out["CHROME"] = chrome
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "sprawdz"
    if cmd == "sprawdz":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    elif cmd == "instaluj":
        instaluj()
    elif cmd == "env":
        print("\n".join(f"export {k}={json.dumps(v)}" for k, v in env().items()))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
