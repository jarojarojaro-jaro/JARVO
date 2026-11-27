#!/usr/bin/env python3
"""melt (MLT 7) z AppImage Kdenlive: render i sprawdzenie projektu `.kdenlive` / `.mlt` bez okna.

    python3 melt.py projekt.kdenlive -consumer avformat:film.mp4 vcodec=libx264 acodec=aac
    python3 melt.py film.mp4 -profile vertical_hd_30 -filter crop center=1 \
        -attach dynamictext:"Napis" geometry=0%/75%:100%x15% halign=center size=72 \
        -consumer avformat:pion.mp4 vcodec=libx264 acodec=aac preset=veryfast threads=2
    python3 melt.py --program          # ścieżka AppImage Kdenlive (pobiera ją przy pierwszym użyciu)

AppImage Kdenlive (vendor/natywne.yaml `kdenlive`) ma w środku melt, ffmpeg i moduły MLT; skrypt montuje go
(FUSE 2), ustawia otoczenie jak AppRun paczki (moduły MLT, Qt bez ekranu) i uruchamia melt z podanymi argumentami.
Bez FUSE rozpakowuje paczkę raz obok programu. Kod wyjścia = kod melt.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

URUCHOM = ('this_dir="$1"; shift; for h in "$this_dir"/apprun-hooks/*.sh; do . "$h"; done; '
           'exec "$this_dir/usr/bin/melt" "$@"')


def program() -> Path:
    """AppImage Kdenlive: z PATH procesów floty, a gdy go brak, z manifestu instalacji (pobranie z sumą)."""
    p = os.environ.get("JARVO_KDENLIVE") or shutil.which("kdenlive")
    if p:
        return Path(p)
    root = Path(os.environ.get("JARVO_ROOT") or Path.home() / ".local" / "share" / "jarvo")
    try:
        app = json.loads((root / "program" / "current.json").read_text(encoding="utf-8"))["app"]
    except (OSError, ValueError, KeyError):
        sys.exit(f"BŁĄD: brak instalacji Jarva w {root}, więc nie ma skąd wziąć Kdenlive")
    sys.path.insert(0, app)
    from jarvo import przy_uzyciu
    u = przy_uzyciu.uklad()
    p = przy_uzyciu.program_narzedzia(przy_uzyciu.narzedzie(u, "kdenlive"), "kdenlive")
    if not p:
        sys.exit("BŁĄD: Kdenlive pobrany, ale bez programu w katalogu (zgłoś to)")
    return p


def main(argv: list[str]) -> int:
    prog = program()
    if argv[:1] == ["--program"]:
        print(prog)
        return 0
    if not argv:
        print(__doc__)
        return 2
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    montaz = None
    try:
        montaz = subprocess.Popen([str(prog), "--appimage-mount"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True)
        katalog = Path((montaz.stdout.readline() or "").strip())
        if not (katalog / "usr" / "bin" / "melt").is_file():
            montaz.terminate()
            montaz = None
            katalog = prog.parent / "rozpakowany" / "squashfs-root"
            if not (katalog / "usr" / "bin" / "melt").is_file():
                print("bez FUSE: rozpakowuję Kdenlive raz (ok. 1 min)", file=sys.stderr)
                katalog.parent.mkdir(exist_ok=True)
                subprocess.run([str(prog), "--appimage-extract"], cwd=katalog.parent, check=True,
                               stdout=subprocess.DEVNULL)
        return subprocess.run(["bash", "-c", URUCHOM, "melt", str(katalog), *argv], env=env).returncode
    finally:
        if montaz is not None:
            montaz.terminate()
            try:
                montaz.wait(timeout=10)
            except subprocess.TimeoutExpired:
                montaz.kill()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
