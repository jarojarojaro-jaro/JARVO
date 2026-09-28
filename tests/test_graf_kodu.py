"""Skill graf-kodu: przypięty silnik z sumą SHA-256, katalog narzędzi floty, czytelne wyniki."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("graf_kodu", ROOT / "shared" / "skills" / "graf-kodu" / "scripts" / "graf_kodu.py")
gk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gk)


def test_home_uses_fleet_tools_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("JARVO_GRAF_KODU", raising=False)
    monkeypatch.setenv("JARVO_NARZEDZIA", str(tmp_path))
    assert gk.home() == tmp_path / "graf-kodu"
    monkeypatch.setenv("JARVO_GRAF_KODU", str(tmp_path / "x"))
    assert gk.home() == tmp_path / "x"


def test_refuses_binary_with_wrong_checksum(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVO_GRAF_KODU", str(tmp_path))
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = b"#!/bin/sh\necho podmieniony\n"
        info = tarfile.TarInfo("codebase-memory-mcp")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    monkeypatch.setattr(gk.urllib.request, "urlopen", lambda url, timeout=0: io.BytesIO(buf.getvalue()))
    with pytest.raises(SystemExit, match="SHA-256"):
        gk.binary()
    assert not (tmp_path / gk.VERSION / "codebase-memory-mcp").exists()      # nic nie zostało zainstalowane


def test_ambiguous_name_lists_qualified_names(monkeypatch, tmp_path):
    monkeypatch.setattr(gk, "ensure", lambda repo, refresh=False: "proj")
    out = json.dumps({"status": "ambiguous", "suggestions": [{"qualified_name": "proj.a.normalize"},
                                                             {"qualified_name": "proj.b.normalize"}]})
    monkeypatch.setattr(gk, "run", lambda args, quiet=False: type("R", (), {"stdout": out, "stderr": "", "returncode": 0})())
    text = gk.trace(tmp_path, "normalize", "inbound", 2)
    assert "proj.a.normalize" in text and "proj.b.normalize" in text and "pełną nazwę" in text


def test_pinned_version_and_checksums_are_complete():
    assert gk.VERSION.count(".") == 2 and set(gk.SHA256) == {"amd64", "arm64"}
    assert all(len(v) == 64 and int(v, 16) >= 0 for v in gk.SHA256.values())


@pytest.mark.skipif(not os.environ.get("JARVO_TEST_GRAF_KODU"), reason="ustaw JARVO_TEST_GRAF_KODU (katalog z pobranym silnikiem)")
def test_live_callers_of_known_function(monkeypatch):
    monkeypatch.setenv("JARVO_GRAF_KODU", os.environ["JARVO_TEST_GRAF_KODU"])
    out = gk.trace(ROOT, "home-user-TARS.profiles.jarvo-wideo.scripts.wideo_lib.probe", "inbound", 1)
    assert "qa_wideo" in out and "kadry" in out


def test_unknown_function_gives_hint(monkeypatch, tmp_path):
    monkeypatch.setattr(gk, "ensure", lambda repo, refresh=False: "proj")
    out = json.dumps({"error": "function not found", "function_name": "nieMa"})
    monkeypatch.setattr(gk, "run", lambda args, quiet=False: type("R", (), {"stdout": "", "stderr": out, "returncode": 1})())
    text = gk.trace(tmp_path, "nieMa", "inbound", 2)
    assert "szukaj" in text and "nieMa" in text and "{" not in text
