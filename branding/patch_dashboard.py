#!/usr/bin/env python3
"""Branding TARS w statycznych zasobach dashboardu Hermesa (uruchamiane przy budowie obrazu).

    python3 patch_dashboard.py <katalog-z-favicon>

Zmienia wyłącznie teksty i ikony widoczne dla użytkownika (tytuł karty, logo w menu, nazwę marki,
etykiety motywów, stronę logowania). Kod Hermesa zostaje bez zmian; licencja MIT i autorzy:
docs/SOURCES.md. Każda podmiana jest opcjonalna: nowa wersja Hermesa z innym układem plików
nie wywraca budowy, tylko wypisuje, czego nie znalazła (wyjątek: tytuł karty, bo to podstawa).
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

HERMES = Path("/opt/hermes")
WEB = HERMES / "hermes_cli" / "web_dist"


def sub_all(files, pattern: str, repl: str, label: str, flags=0) -> int:
    n = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        new, k = re.subn(pattern, repl, text, flags=flags)
        if k:
            f.write_text(new, encoding="utf-8")
            n += k
    print(f"  {'✓' if n else '·'} {label}: {n}")
    return n


def main(argv: list[str]) -> int:
    brand = Path(argv[0])
    for d in (WEB, HERMES / "web" / "public"):
        if d.is_dir():
            for name in ("favicon.ico", "favicon.svg"):
                shutil.copy(brand / name, d / name)
    assets = sorted((WEB / "assets").glob("*.js"))
    index = [WEB / "index.html"]
    print("Branding TARS w dashboardzie:")
    if not sub_all(index, r"<title>[^<]*</title>", "<title>TARS</title>", "tytuł karty"):
        print("Nie znaleziono <title> w index.html", file=sys.stderr)
        return 1
    sub_all(index, r'<link rel="icon"[^>]*>', '<link rel="icon" href="/favicon.ico" />', "favicon")
    # logo w menu: dwie linie tekstu "Hermes" / "Agent"
    sub_all(assets, r"children:\[`Hermes`,(\(0,[\w$]+\.jsx\)\(`br`,\{\}\)),`Agent`\]",
            r"children:[`TARS`,\1,`HQ`]", "logo w menu")
    sub_all(assets, r"brand:`Hermes Agent`,brandShort:`HA`", "brand:`TARS`,brandShort:`T`", "nazwa marki (i18n)")
    sub_all(assets, r"label:`Hermes Teal", "label:`TARS Teal", "etykiety motywów")
    themes = HERMES / "hermes_cli" / "web_server_dashboard.py"
    if themes.is_file():
        sub_all([themes], r'"label": "Hermes Teal', '"label": "TARS Teal', "etykiety motywów (serwer)")
    login = HERMES / "hermes_cli" / "dashboard_auth" / "login_page.py"
    if login.is_file():
        sub_all([login], r"the Hermes Agent dashboard", "TARS HQ", "strona logowania (opis)")
        sub_all([login], r" — Hermes Agent<", " — TARS<", "strona logowania (tytuł)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
