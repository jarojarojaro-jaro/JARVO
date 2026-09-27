#!/usr/bin/env python3
"""Link do obejrzenia wyniku w przeglądarce użytkownika (serwer podglądu TARS HQ, port 9120).

    python3 /opt/tars/repo/scripts/tars_link.py <plik albo katalog> [...]

Dla agentów: flota działa w kontenerze, więc serwer uruchomiony w terminalu (python -m http.server,
npm run dev, localhost:8000…) jest dla użytkownika NIEOSIĄGALNY. Zamiast tego ten skrypt wypisuje adres,
który działa w przeglądarce użytkownika: strona HTML z CSS/JS/obrazkami obok, obraz, PDF, wideo, tekst.
Katalog = jego index.html. Tylko pliki z /opt/data/tars/{workspaces,missions,knowledge,inbox}.
Link jest ważny 7 dni; ten sam katalog dostaje ten sam link.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("tars_hq_core_link", HERE.parent / "hq" / "plugin" / "hq_core.py")
core = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = core   # dataclass w hq_core potrzebuje modułu w sys.modules
_spec.loader.exec_module(core)


def base_url() -> str:
    """Adres serwera podglądu, jak widzi go przeglądarka (compose: TARS_PREVIEW_URL)."""
    url = os.environ.get("TARS_PREVIEW_URL")
    if not url:
        try:
            url = json.loads((core.TARS_DIR / "state" / "preview.json").read_text(encoding="utf-8")).get("url")
        except (OSError, ValueError):
            url = None
    return (url or "http://localhost:9120").rstrip("/")


def link(raw: str, roots: "core.Roots", now: float) -> str:
    p = Path(raw).expanduser()
    if p.is_dir():
        p = p / "index.html"
    f = core.safe_path(str(p), roots)
    if f is None:
        raise ValueError(f"{raw}: nie istnieje albo leży poza /opt/data/tars/{{workspaces,missions,knowledge,inbox}}")
    root = core.site_root(f, roots)
    token = core.link_for(core.LINKS_FILE, root, now)
    return f"{base_url()}/{token}/{f.relative_to(root).as_posix()}"


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    roots, now, bad = core.Roots(), time.time(), 0
    for raw in argv:
        try:
            print(link(raw, roots, now))
        except ValueError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
