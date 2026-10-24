"""Straż plików wsadowych na Windows (BatBadBut): argument ze znakami cmd.exe nie trafia do npm.cmd, npx.cmd
ani node_modules/.bin/*.cmd. Te same reguły w mobile_lib, narzedzia (Wideograf) i lemo_wake (Studio)."""
from __future__ import annotations

import os

import pytest

from conftest import load_script

MODULY = [load_script("profiles/jarvo-mobile/scripts/mobile_lib.py", "jarvo_test_wsad_mobile"),
          load_script("profiles/jarvo-wideo/scripts/narzedzia.py", "jarvo_test_wsad_narzedzia"),
          load_script("profiles/jarvo-studio/scripts/lemo_wake.py", "jarvo_test_wsad_lemo")]


@pytest.mark.parametrize("modul", MODULY, ids=["mobile", "wideo", "studio"])
def test_plik_wsadowy_bez_znakow_cmd(modul, monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    assert modul.bez_wsadu([r"C:\node\npx.cmd", "expo", "start", "--port", "8081"])[0].endswith("npx.cmd")
    for zly in ("a&calc", "x|y", "<in", "100%", "!x!", 'a"b', "linia\nnowa", "^c"):
        with pytest.raises(SystemExit, match="plik wsadowy cmd.exe"):
            modul.bez_wsadu([r"C:\node\npm.CMD", "view", zly])
    assert modul.bez_wsadu([r"C:\node\node.exe", "-e", "a&b|c"])[2] == "a&b|c"     # .exe: bez cmd.exe


@pytest.mark.parametrize("modul", MODULY, ids=["mobile", "wideo", "studio"])
def test_poza_windows_bez_zmian(modul, monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    assert modul.bez_wsadu(["/usr/bin/npm.cmd", "a&b"]) == ["/usr/bin/npm.cmd", "a&b"]


@pytest.mark.windows_only
def test_lemo_wake_bash_tylko_z_git_bash():
    lw = MODULY[2]
    b = lw.program("bash")
    assert "system32" not in b.lower() and b.lower().endswith("bash.exe")
