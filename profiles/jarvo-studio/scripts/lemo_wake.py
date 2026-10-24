#!/usr/bin/env python3
"""lemo-wake dla Studia: jedno zdjęcie albo grafika → pętla ok. 5 s (MP4, GIF, WebP) i rozbicie na warstwy (PSD).

    python3 lemo_wake.py sprawdz        # co gotowe (JSON): biblioteka, Python, playwright, przeglądarka, modele, zgoda
    python3 lemo_wake.py instaluj       # raz: klon na przypiętym commicie + pakiety (ok. 350 MB, bez modeli)
    python3 lemo_wake.py env            # eval "$(python3 lemo_wake.py env)": LW, LW_WARSTWY, LW_PY, LEMO_WAKE_MODELS, LW_HISTORIA
    python3 lemo_wake.py uruchom -- <polecenie> [argumenty]   # to samo bez eval; {LW}, {LW_PY}… w argumentach

Biblioteka to sam skill z github.com/lemomo-ai/lemo-wake (wake + layers, bez upload: publikuje w cudzej galerii),
na tym samym commicie co kopia skilla w profilu (vendor/skills.lock.yaml → lemo-wake). Zasady jak narzedzia.py
Wideografa: wszystko raz do /opt/data/jarvo/narzedzia (przeżywa restart i wdrożenie), przeglądarka z obrazu Hermesa,
Python z przypiętymi pakietami zamiast `uv run --script` (ten bierze najnowsze wersje przy każdym uruchomieniu).
Modele ONNX (ok. 600 MB z Hugging Face) pobierają same skrypty skilla dopiero po zgodzie właściciela
(`models.py consent yes`); trzymamy je poza klonem, więc aktualizacja biblioteki ich nie rusza.
Licencja CC BY-NC 4.0: użycie komercyjne tylko za zgodą autora (skill `zywy-obraz`).
Linux, macOS i Windows: venv w bin/ albo Scripts\\, npm (.cmd) przez PATH, `env` na Windows ze ścieżkami
dla Git Bash (z „/”), `uruchom` bez powłoki.
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

WINDOWS = os.name == "nt"

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
# przeglądarka w PLAYWRIGHT_BROWSERS_PATH: katalog i plik jak w rejestrze playwright (jak narzedzia.py Wideografa)
POWLOKA = {"darwin": [("chrome-headless-shell-mac-arm64", "chrome-headless-shell"),
                      ("chrome-headless-shell-mac-x64", "chrome-headless-shell")],
           "win32": [("chrome-headless-shell-win64", "chrome-headless-shell.exe")]}.get(
    sys.platform, [("chrome-headless-shell-linux64", "chrome-headless-shell")])
# pliki modeli jak w _models.py skilla (nazwa: pliki)
MODELE = {
    "depth": ["depth_anything_v2_small.onnx"],
    "general": ["birefnet_lite.onnx"],
    "portrait": ["modnet.onnx"],
    "sam": ["mobile_sam_image_encoder.onnx", "sam_mask_decoder_multi.onnx"],
    "lama": ["lama_fp32.onnx"],
}


# Znaki, które cmd.exe interpretuje w argumentach pliku wsadowego (.cmd, .bat, np. npm.cmd i npx.cmd na Windows).
# Python ich tam nie cytuje (klasa BatBadBut), więc taki argument odrzucamy, zamiast ryzykować cudze polecenie.
ZNAKI_CMD = frozenset('&|<>^%!"' + chr(13) + chr(10))


def bez_wsadu(argv: list[str]) -> list[str]:
    """argv bez zmian; na Windows błąd, gdy program to plik wsadowy, a argument ma znaki interpretowane przez cmd.exe."""
    if os.name == "nt" and argv and str(argv[0]).lower().endswith((".cmd", ".bat")):
        zle = next((a for a in argv[1:] if ZNAKI_CMD & set(str(a))), None)
        if zle is not None:
            raise SystemExit(f"✗ {Path(str(argv[0])).name} to plik wsadowy cmd.exe, a argument {str(zle)[:60]!r} ma znaki, "
                             "które cmd.exe wykonałby jako polecenie (& | < > ^ % ! \"). Podaj go bez nich (np. w pliku).")
    return argv


def git_bash() -> str | None:
    """Git Bash na Windows (obok git.exe albo w standardowym katalogu); nigdy System32\bash.exe, który uruchamia WSL."""
    kandydaci = []
    git = shutil.which("git")
    if git:                                     # Git\cmd\git.exe albo Git\mingw64\bin\git.exe
        for przodek in list(Path(git).resolve().parents)[:3]:
            kandydaci += [przodek / "bin" / "bash.exe", przodek / "usr" / "bin" / "bash.exe"]
    for zmienna, podkatalog in (("ProgramFiles", "Git"), ("ProgramW6432", "Git"), ("LOCALAPPDATA", "Programs/Git")):
        if os.environ.get(zmienna):
            kandydaci.append(Path(os.environ[zmienna]) / podkatalog / "bin" / "bash.exe")
    return next((str(k) for k in kandydaci if k.is_file() and "system32" not in str(k).lower()), None)


def program(nazwa: str, path: str | None = None) -> str:
    """Program do argv: na Windows pełna ścieżka z PATH (npm to plik .cmd, którego CreateProcess nie znajdzie
    po gołej nazwie), a `bash` i `sh` tylko z Git Bash; na POSIX nazwa bez zmian."""
    if not WINDOWS or os.path.dirname(nazwa):
        return nazwa
    if nazwa.lower() in ("bash", "bash.exe", "sh", "sh.exe"):
        b = git_bash()
        if not b:
            raise SystemExit("brak Git Bash: na Windows polecenia bash potrzebują Git for Windows (bash z System32 to WSL)")
        return b
    return shutil.which(nazwa, path=path) or nazwa


def venv_python(venv: Path) -> Path:
    """Python w venvie: bin/python na POSIX, Scripts\\python.exe na Windows."""
    return venv / "Scripts" / "python.exe" if WINDOWS else venv / "bin" / "python"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("▶", " ".join(cmd), flush=True)
    subprocess.run([program(cmd[0]), *cmd[1:]], cwd=cwd, check=True)


def git_head(dest: Path) -> str:
    return subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def klon(repo: str = REPO, rev: str = REV, dest: Path = LIB, pomin: list[str] = POMIN) -> None:
    """Klon bez historii plików, bez ścieżek `pomin`, na przypiętym commicie; nowy `rev` w repo Jarva przenosi klon."""
    if (dest / ".git").exists():
        if git_head(dest) != rev:
            run(["git", "-C", str(dest), "fetch", "--quiet", "--filter=blob:none", "origin", rev])
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", "--filter=blob:none", "--sparse", "--no-checkout", repo, str(dest)])
    wzorce = ["/*", *[f"!{p}" for p in pomin]]
    lista = subprocess.run(["git", "-C", str(dest), "sparse-checkout", "list"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout
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
    return venv_python(VENV).exists() and _czytaj(znacznik_py()) == podpis(*PY_PAKIETY)


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
    python = venv_python(VENV)
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
        for katalog, plik in POWLOKA:
            exe = d / katalog / plik
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
        "katalog": LIB.as_posix(),
    }


def env() -> dict[str, str]:
    out = {
        "LW": str(LIB / "skills" / "wake"),
        "LW_WARSTWY": str(LIB / "skills" / "layers"),
        "LW_PY": str(venv_python(VENV)),
        "LEMO_WAKE_MODELS": str(DANE / "models"),
        "LW_HISTORIA": str(DANE / "history.jsonl"),
    }
    chrome = przegladarka()
    if chrome:
        out["CHROME"] = chrome
    return out


def dla_powloki(wartosc: str) -> str:
    """Ścieżka do `export` w bashu: na POSIX bez zmian, na Windows z „/” (Git Bash; programy Windows też ją rozumieją)."""
    return wartosc.replace("\\", "/") if WINDOWS else wartosc


def uruchom(polecenie: list[str]) -> int:
    """Polecenie ze zmiennymi lemo-wake (env()) bez `eval` w powłoce; `{LW}`, `{LW_PY}`… w argumentach to ich wartości
    (powłoka rozwija `$LW`, zanim zmienna istnieje). Kod wyjścia polecenia."""
    zmienne = env()
    srodowisko = {**os.environ, **zmienne}
    argv = [re.sub(r"\{([A-Z_][A-Z0-9_]*)\}", lambda m: zmienne.get(m.group(1), m.group(0)), a) for a in polecenie]
    return subprocess.run(bez_wsadu([program(argv[0], srodowisko.get("PATH")), *argv[1:]]), env=srodowisko).returncode


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "sprawdz"
    if cmd == "sprawdz":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    elif cmd == "instaluj":
        instaluj()
    elif cmd == "env":
        print("\n".join(f"export {k}={json.dumps(dla_powloki(v), ensure_ascii=False)}" for k, v in env().items()))
    elif cmd == "uruchom":
        polecenie = argv[2:] if argv[1:2] == ["--"] else argv[1:]
        if not polecenie:
            raise SystemExit("uruchom -- <polecenie> [argumenty]")
        return uruchom(polecenie)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
