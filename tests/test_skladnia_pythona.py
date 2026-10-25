"""Każdy plik .py w repo kompiluje się bez ostrzeżeń: SyntaxWarning (np. „\\J” w zwykłym napisie z %LOCALAPPDATA%\\Jarvo)
Python wypisuje dopiero przy imporcie w procesie Hermesa, a w kolejnej wersji to SyntaxError."""
from __future__ import annotations

import subprocess
import warnings

from conftest import REPO


def test_pliki_python_bez_ostrzezen_kompilacji():
    pliki = subprocess.run(["git", "-C", str(REPO), "ls-files", "*.py"], capture_output=True, text=True,
                           encoding="utf-8", check=True).stdout.split()
    assert pliki
    zle = []
    for p in pliki:
        zrodlo = (REPO / p).read_text(encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            try:
                compile(zrodlo, p, "exec", dont_inherit=True)
            except (SyntaxError, SyntaxWarning, DeprecationWarning) as e:
                zle.append(f"{p}: {type(e).__name__}: {e}")
    assert not zle, zle
