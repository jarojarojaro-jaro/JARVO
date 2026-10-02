"""Wspólne narzędzia testów floty Jarvo: import skryptów po ścieżce i kopia repo do modyfikacji."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))


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
