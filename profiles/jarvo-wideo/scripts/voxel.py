#!/usr/bin/env python3
"""Voxel ASCII (silnikjava, MIT): diorama z klocków 3D z cieniami i okluzją, animacja (woda, światła, snop latarni,
śnieg, liście, ptaki, najazd kamery) i filtr ASCII z tilt-shiftem; rolka 1080×1920, 30 kl./s, bez dźwięku.
Pipeline w Pythonie (numpy, scipy, Pillow) z .claude/skills/voxel-ascii; ten skrypt go woła i oddaje film jako projekt.

    voxel.py sceny                                              # gotowe sceny i ich warianty
    voxel.py podglad lighthouse [--wariant noc] [--t 8] [--out out/wideo/src/voxel]   # raw_*.png (3D) + ascii_*.png
    voxel.py arkusz lighthouse [--wariant noc] [--out …]        # 6 klatek z całego filmu w jednym PNG
    voxel.py film lighthouse -o out/wideo/latarnia.mp4 [--wariant noc] [--sekundy 8] [--watki 2]
    voxel.py film lighthouse -o out/wideo/latarnia.mp4 --surowy pobrane/lighthouse.mp4   # render z InstaBox → projekt

Scena to plik .py (`build()` + CONFIG, wzór: $VOXEL/scenes/lighthouse.py) albo nazwa gotowej. Wyniki w --out
(domyślnie out/wideo/src/voxel/<scena>[-wariant]); świat i render 3D w cache obok (zmiana samego `look` nie liczy
cieni od nowa, ok. 3 min za pierwszym razem). Na tym komputerze render idzie z `nice -n 15` i najwyżej --watki 2
(domyślnie 2), BLAS po jednym wątku; pełny film 20 s to ok. 10 min na 4 rdzeniach, więc pełne filmy na InstaBox
(skill voxel-ascii: `zapas-mocy`), a tu podgląd, arkusz i krótkie próby. `film` składa projekt edytora
(`projekt.py z-kodu <film> --obraz <surowy> --render`; muzyka po `--`, np. -- --muzyka podklad.wav).
Krój ASCII: DejaVu Sans Mono Bold z systemu albo z instalacji Jarva (JARVO_FONTY_DEJAVU). Wymaga
`narzedzia.py instaluj silnikjava`. Kod wyjścia: 0 ok, 1 błąd renderu, 2 złe wejście.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import narzedzia as nz  # noqa: E402

KROJ_SILNIKA = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"     # FONT w voxlib/look.py
WATKI = 2
# jeden wątek BLAS na proces: run.py liczy klatki w puli procesów (--jobs)
JEDEN_WATEK = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
# uruchomienie run.py z podmienionym krojem ASCII (look.FONT), gdy krój silnika nie leży w systemie
START = ("import runpy, sys; sys.path.insert(0, sys.argv[1]); import voxlib.look as L; L.FONT = sys.argv[2]; "
         "sys.argv = [sys.argv[1] + '/run.py', *sys.argv[3:]]; runpy.run_path(sys.argv[0], run_name='__main__')")


def kroj() -> str | None:
    """Krój ASCII: ten z kodu silnika, a gdy go nie ma, DejaVu Sans Mono Bold z instalacji Jarva albo z systemu."""
    kandydaci = [Path(KROJ_SILNIKA)]
    if os.environ.get("JARVO_FONTY_DEJAVU"):
        kandydaci.insert(1, Path(os.environ["JARVO_FONTY_DEJAVU"]) / "DejaVuSansMono-Bold.ttf")
    kandydaci += [Path(d) / "DejaVuSansMono-Bold.ttf" for d in ("/usr/share/fonts/TTF", "/usr/share/fonts/dejavu")]
    return next((str(k) for k in kandydaci if k.is_file()), None)


def sceny(voxel: Path) -> list[dict]:
    out = []
    for p in sorted((voxel / "scenes").glob("*.py")):
        tekst = p.read_text(encoding="utf-8")
        warianty = []
        if "VARIANTS" in tekst:
            import ast
            for n in ast.parse(tekst).body:
                if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "VARIANTS" for t in n.targets) \
                        and isinstance(n.value, ast.Dict):
                    warianty = [k.value for k in n.value.keys if isinstance(k, ast.Constant)]
        opis = (tekst.split('"""')[1].strip().splitlines()[0] if tekst.lstrip().startswith('"""') else "")
        out.append({"scena": p.stem, "warianty": warianty, "opis": opis})
    return out


def polecenie(voxel: Path, scena: str, argv: list[str], font: str | None) -> list[str]:
    python = nz.py() if Path(nz.py()).exists() else sys.executable
    if font and font != KROJ_SILNIKA:
        return [python, "-c", START, str(voxel), font, scena, *argv]
    return [python, str(voxel / "run.py"), scena, *argv]


def uruchom(cmd: list[str]) -> int:
    """Render z niskim priorytetem (nice 15 na POSIX) i jednym wątkiem BLAS na proces."""
    pre = (lambda: os.nice(15)) if hasattr(os, "nice") else None
    print("▶ " + " ".join(cmd[-6:]), file=sys.stderr, flush=True)
    return subprocess.run(cmd, env={**os.environ, **JEDEN_WATEK}, preexec_fn=pre).returncode


def katalog_wyniku(a) -> Path:
    tag = Path(a.scena).stem + (f"-{a.wariant}" if a.wariant else "")
    return Path(a.out) if a.out else Path("out/wideo/src/voxel") / tag


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    z_kodu: list[str] = []
    if "--" in args:
        i = args.index("--")
        args, z_kodu = args[:i], args[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sceny")
    for nazwa in ("podglad", "arkusz", "film"):
        s = sub.add_parser(nazwa)
        s.add_argument("scena", help="lighthouse | shrine | plik sceny .py")
        s.add_argument("--wariant")
        s.add_argument("--out", help="katalog wyników (domyślnie out/wideo/src/voxel/<scena>[-wariant])")
        s.add_argument("--odnowa", action="store_true", help="świat i render 3D od nowa (--force)")
        if nazwa == "podglad":
            s.add_argument("--t", default="8", help="sekundy po przecinku (domyślnie 8)")
        if nazwa == "film":
            s.add_argument("-o", required=True, help="film .mp4 (obok projekt <film>.edycja.json)")
            s.add_argument("--sekundy", type=float, help="długość (domyślnie z konfiguracji sceny, zwykle 20)")
            s.add_argument("--watki", type=int, default=WATKI, help=f"procesy klatek (domyślnie {WATKI})")
            s.add_argument("--surowy", help="gotowy MP4 z run.py (np. z InstaBox): tylko projekt edytora")
    a = ap.parse_args(args)
    if a.cmd != "film" and z_kodu:
        raise SystemExit("opcje po `--` tylko przy `film` (idą do projekt.py z-kodu)")
    if not nz.silnikjava_gotowe():
        raise SystemExit("✗ brak silnikjava: python3 $HERMES_HOME/scripts/narzedzia.py instaluj silnikjava")
    voxel = nz.VOXEL
    if a.cmd == "sceny":
        print(json.dumps(sceny(voxel), ensure_ascii=False, indent=1))
        return 0
    scena = str(Path(a.scena).resolve()) if a.scena.endswith(".py") else a.scena
    out = katalog_wyniku(a)
    if a.cmd == "film" and a.surowy:
        surowy = Path(a.surowy)
        if not surowy.is_file():
            raise SystemExit(f"✗ brak {surowy}")
    else:
        font = kroj()
        if not font:
            raise SystemExit("✗ brak kroju DejaVu Sans Mono Bold (instalacja Jarva: JARVO_FONTY_DEJAVU, Linux: fonts-dejavu-core)")
        opcje = ["--out", str(out), *(["--variant", a.wariant] if a.wariant else []), *(["--force"] if a.odnowa else [])]
        if a.cmd == "podglad":
            opcje += ["--preview", *[t.strip() for t in a.t.split(",") if t.strip()]]
        elif a.cmd == "arkusz":
            opcje += ["--sheet"]
        else:
            opcje += ["--video", "--jobs", str(max(1, a.watki)), *(["--seconds", f"{a.sekundy:g}"] if a.sekundy else [])]
        if uruchom(polecenie(voxel, scena, opcje, font)):
            return 1
        if a.cmd != "film":
            pliki = sorted(p.as_posix() for p in out.glob("*.png"))
            print(json.dumps({"katalog": out.as_posix(), "pliki": pliki}, ensure_ascii=False))
            return 0
        surowy = out / f"{Path(a.scena).stem}{f'-{a.wariant}' if a.wariant else ''}.mp4"
    cmd = [sys.executable, str(HERE / "projekt.py"), "z-kodu", a.o, "--obraz", str(surowy), *z_kodu, "--render"]
    print("▶ projekt edytora: " + " ".join(cmd[1:]), file=sys.stderr, flush=True)
    if subprocess.run(cmd).returncode:
        return 1
    print(json.dumps({"film": a.o, "projekt": str(Path(a.o).with_suffix(".edycja.json")), "obraz": surowy.as_posix()},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
