"""Atrapy programów w testach, przenośne między Linuksem, macOS i Windows (docs/NATYWNIE.md, etap E1, T09).

Atrapa to kod Pythona uruchamiany jak prawdziwy program (`sys.argv`, kod wyjścia, stdout). Na POSIX to plik
wykonywalny z shebangiem bieżącego interpretera. Na Windows to `nazwa.py` i `nazwa.cmd`, który go woła: CreateProcess
nie uruchomi pliku z shebangiem, a `shutil.which` znajduje `.cmd` przez PATHEXT. Dlatego kod pod testem szuka
programów przez `shutil.which` (albo pełną ścieżkę), a nie przez gołą nazwę w liście argv.
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


def program(katalog: Path, nazwa: str, kod: str) -> Path:
    """Tworzy atrapę `nazwa` w `katalog`, wykonującą `kod`; zwraca ścieżkę do uruchomienia (na Windows `.cmd`)."""
    katalog = Path(katalog)
    katalog.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        skrypt = katalog / f"{nazwa}.py"
        skrypt.write_text(kod, encoding="utf-8")
        cmd = katalog / f"{nazwa}.cmd"
        cmd.write_text(f'@"{sys.executable}" "{skrypt}" %*\r\n', encoding="utf-8", newline="")
        return cmd
    p = katalog / nazwa
    p.write_text(f"#!{sys.executable}\n{kod}", encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p


def sciezka(*katalogi: Path | str, reszta: bool = True) -> str:
    """Wartość PATH z `katalogi` na początku (separator systemu); `reszta=False` = tylko te katalogi."""
    czesci = [str(k) for k in katalogi]
    if reszta and os.environ.get("PATH"):
        czesci.append(os.environ["PATH"])
    return os.pathsep.join(czesci)
