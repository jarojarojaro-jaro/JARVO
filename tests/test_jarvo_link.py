"""Linki podglądu dla agentów: adres działa w przeglądarce użytkownika, tylko dla wyników floty."""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def load(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVO_DATA_DIR", str(tmp_path / "jarvo"))
    monkeypatch.setenv("JARVO_PREVIEW_URL", "http://100.64.0.7:9120")
    spec = importlib.util.spec_from_file_location("jarvo_link_t", REPO / "scripts" / "jarvo_link.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_link_for_page_and_refusal(tmp_path, monkeypatch, capsys):
    tl = load(tmp_path, monkeypatch)
    out = tmp_path / "jarvo" / "missions" / "M-1" / "zlozenie" / "out" / "pakiet" / "landing"
    out.mkdir(parents=True)
    (out / "index.html").write_text("<h1>Ziarno</h1>", encoding="utf-8")
    (tmp_path / "secret.env").write_text("K=1", encoding="utf-8")
    assert tl.main([str(out.parent.parent)]) == 1          # katalog out/ bez index.html
    capsys.readouterr()
    assert tl.main([str(out)]) == 0
    url = capsys.readouterr().out.strip()
    # od najbliższego out/: linki między plikami pakietu działają
    assert url.startswith("http://100.64.0.7:9120/") and url.endswith("/pakiet/landing/index.html")
    token = url.split("/")[3]
    assert tl.core.link_root(tl.core.LINKS_FILE, token, 0) == (out.parents[1]).resolve()
    assert tl.main([str(tmp_path / "secret.env")]) == 1
    assert "poza" in capsys.readouterr().err


def test_link_works_from_agent_profile_home(tmp_path, monkeypatch, capsys):
    """Dispatcher uruchamia wykonawcę z HERMES_HOME=<root>/profiles/<agent>; dane floty i tak są w <root>/jarvo."""
    monkeypatch.delenv("JARVO_DATA_DIR", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-wideo"))
    monkeypatch.setenv("JARVO_PREVIEW_URL", "http://100.64.0.7:9120")
    spec = importlib.util.spec_from_file_location("jarvo_link_profil", REPO / "scripts" / "jarvo_link.py")
    tl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tl)
    assert tl.core.JARVO_DIR == tmp_path / "jarvo"
    film = tmp_path / "jarvo" / "workspaces" / "jarvo-wideo" / "karta" / "out" / "demo.mp4"
    film.parent.mkdir(parents=True)
    film.write_bytes(b"\0")
    assert tl.main([str(film)]) == 0 and capsys.readouterr().out.strip().endswith("/demo.mp4")

