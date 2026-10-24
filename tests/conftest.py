"""Wspólne narzędzia testów floty Jarvo: import skryptów po ścieżce, kopia repo do modyfikacji i znaczniki systemów.

Znaczniki (docs/NATYWNIE.md, etap E1): `posix_only` (Linux i macOS), `windows_only`, `linux_only`, `wymaga_bash`
(prawdziwy bash: na Windows tylko Git Bash, nigdy System32\\bash.exe, który uruchamia WSL), `wymaga_symlinku`
(zwykły użytkownik Windows nie tworzy symlinków bez trybu dewelopera). Test na złym systemie jest pomijany z powodem.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))      # tests/atrapy.py
# import wtyczki HQ w testach nie startuje silnika rozmów (wątek tła, rozmowy.db w /opt/data, dziennik w pliku);
# testy silnika budują go same na katalogu tymczasowym (tests/test_silnik_rozmow.py)
os.environ.setdefault("JARVO_HQ_SILNIK", "0")

WINDOWS = os.name == "nt"
LINUX = sys.platform.startswith("linux")
ZNACZNIKI = {
    "posix_only": "tylko Linux i macOS (np. skrypty bash instalatora z kontenerem)",
    "windows_only": "tylko Windows",
    "linux_only": "tylko Linux",
    "wymaga_bash": "potrzebny prawdziwy bash (na Windows Git Bash)",
    "wymaga_symlinku": "potrzebne symlinki (Windows bez trybu dewelopera ich nie tworzy)",
}


@lru_cache(maxsize=1)
def bash() -> str | None:
    """Ścieżka prawdziwego basha albo None. Na Windows tylko Git Bash (obok git.exe albo ze standardowej instalacji):
    `bash` z PATH bywa System32\\bash.exe, a ten uruchamia WSL (u właściciela budzi to starą flotę)."""
    if not WINDOWS:
        return shutil.which("bash")
    kandydaci = []
    git = shutil.which("git")
    if git:                                     # Git\cmd\git.exe albo Git\mingw64\bin\git.exe
        for przodek in list(Path(git).resolve().parents)[:3]:
            kandydaci += [przodek / "bin" / "bash.exe", przodek / "usr" / "bin" / "bash.exe"]
    for zmienna in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA"):
        if os.environ.get(zmienna):
            kandydaci.append(Path(os.environ[zmienna]) / ("Programs/Git" if zmienna == "LOCALAPPDATA" else "Git")
                             / "bin" / "bash.exe")
    for k in kandydaci:
        if k.is_file() and "system32" not in str(k).lower():
            return str(k)
    return None


@lru_cache(maxsize=1)
def symlinki() -> bool:
    """Czy ten użytkownik może tworzyć symlinki (Windows: tryb dewelopera albo administrator)."""
    if not WINDOWS:
        return True
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        try:
            os.symlink(d, os.path.join(d, "proba"), target_is_directory=True)
            return True
        except OSError:
            return False


def pytest_configure(config):
    for nazwa, opis in ZNACZNIKI.items():
        config.addinivalue_line("markers", f"{nazwa}: {opis}")


def pytest_collection_modifyitems(config, items):
    for item in items:
        powod = None
        if "posix_only" in item.keywords and WINDOWS:
            powod = ZNACZNIKI["posix_only"]
        elif "windows_only" in item.keywords and not WINDOWS:
            powod = ZNACZNIKI["windows_only"]
        elif "linux_only" in item.keywords and not LINUX:
            powod = ZNACZNIKI["linux_only"]
        elif "wymaga_bash" in item.keywords and bash() is None:
            powod = ZNACZNIKI["wymaga_bash"]
        elif "wymaga_symlinku" in item.keywords and not symlinki():
            powod = ZNACZNIKI["wymaga_symlinku"]
        if powod:
            item.add_marker(pytest.mark.skip(reason=powod))


def uruchom_bash(*argv: str, **kw) -> subprocess.CompletedProcess:
    """`bash argv...` prawdziwym bashem (test z `wymaga_bash`), domyślnie z przechwyceniem wyjścia w UTF-8."""
    b = bash()
    if b is None:
        pytest.skip(ZNACZNIKI["wymaga_bash"])
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    if kw.get("text"):
        kw.setdefault("encoding", "utf-8")
    return subprocess.run([b, *argv], **kw)


def load_script(rel: str, name: str | None = None):
    """Importuje skrypt (np. profiles/jarvo/scripts/patrol.py) jako moduł, bez uruchamiania main()."""
    path = REPO / rel
    mod_name = name or "jarvo_test_" + rel.replace("/", "_").replace("-", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo_copy(tmp_path, monkeypatch):
    """Kopia części repo, na której walidator i build działają jak na oryginale.

    Zwraca katalog kopii; fleetlib wskazuje na nią przez monkeypatch stałych ścieżek.
    """
    import fleetlib as fl

    dst = tmp_path / "repo"
    dst.mkdir()
    for rel in ["fleet.yaml", "profiles", "shared", "vendor", "evals", "knowledge", "docs", "README.md"]:
        src = REPO / rel
        if src.is_dir():
            shutil.copytree(src, dst / rel, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif src.exists():
            shutil.copy2(src, dst / rel)
    monkeypatch.setattr(fl, "REPO_ROOT", dst)
    monkeypatch.setattr(fl, "PROFILES_DIR", dst / "profiles")
    monkeypatch.setattr(fl, "SHARED_DIR", dst / "shared")
    monkeypatch.setattr(fl, "VENDOR_LOCK", dst / "vendor" / "skills.lock.yaml")
    monkeypatch.setattr(fl, "FLEET_FILE", dst / "fleet.yaml")
    # składnię skryptów (53 procesy bash -n / node --check) sprawdza test_repo_is_valid na prawdziwym repo;
    # testy na kopii zmieniają konfigurację floty, nie skrypty
    import validate
    monkeypatch.setattr(validate, "check_scripts", lambda r: None)
    return dst
