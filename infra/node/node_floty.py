"""Narzędzia npm floty natywnie (docs/NATYWNIE.md P02, M02, I32): infra/node → `<program>/node-floty/<skrót locka>`.

    zainstaluj(program, npm, *, cache, bin_ffmpeg=(), log=print) -> (wpis, zmiana)   # wpis narzedzia.json "node-floty"
    python -I node_floty.py <program> --npm <npm> --cache <root>/cache [--ffmpeg <katalog bin> …]

W obrazie te paczki instaluje infra/Dockerfile (`npm install` w /opt/jarvo/node, HyperFrames globalnie). Natywnie
instalator kopiuje package.json i package-lock.json tej wersji kodu do `<program>/node-floty/<12 znaków sumy locka>`
i woła `npm ci --ignore-scripts --omit=dev` (npm i node z Node.js z manifestu, bez konfiguracji npm właściciela):
same paczki z locka, każda z sumą integrity z registry.npmjs.org, bez skryptów instalacyjnych (agent-browser
przychodzi z manifestu jako binarka, esbuild bierze program z paczki swojej platformy, onnxruntime-node niczego nie
pobiera). Potem znika onnxruntime-node i onnxruntime-common (model ML dembrandta tylko dla flagi --ai, ok. 0,5 GB,
jak w obrazie), a znacznik `.jarvo-lock` z sumą locka mówi, że katalog jest gotowy: drugi przebieg z tym samym
lockiem niczego nie robi, a nowy lock trafia do nowego katalogu obok (na Windows załadowanych plików .node nie da się
nadpisać).

Wpis dla `<stan>/narzedzia.json` (jarvo/srodowisko.py składa z niego środowisko procesów Jarva):
  bin  node_modules/.bin w PATH: `hyperframes`, `lighthouse`, `svgo`… (na Windows pliki .cmd, w Git Bash skrypty sh),
  env  NODE_PATH (serwery MCP z Node, build.py), HYPERFRAMES_NO_TELEMETRY, HYPERFRAMES_NO_UPDATE_CHECK
       i HYPERFRAMES_NO_AUTO_INSTALL (jak ENV w obrazie: bez PostHoga, bez pytania npm o nowszą wersję i bez jej
       instalacji w tle, którą hyperframes 0.8.78 robi sam), HYPERFRAMES_FFMPEG_PATH i HYPERFRAMES_FFPROBE_PATH na
       programy z katalogów `bin_ffmpeg` (ffmpeg z manifestu; na macOS ffmpeg i ffprobe są w osobnych katalogach),
       HYPERFRAMES_EXTRACT_CACHE_DIR w `<root>/cache/hyperframes` (domyślnie %TEMP%, czyli zwykle dysk C:);
       przeglądarkę daje już wpis chrome-headless-shell (HYPERFRAMES_BROWSER_PATH).
Cache npm: `<root>/cache/npm`, jak dla frontu panelu (jarvo/hermes.py). Sama biblioteka standardowa: moduł ładuje
instalator po ścieżce, jak infra/bin/agent_browser.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable

TU = Path(os.path.abspath(__file__)).parent              # infra/node tej wersji kodu Jarva
PLIKI = ("package.json", "package-lock.json")
ZNACZNIK = ".jarvo-lock"
CIEZKIE = ("onnxruntime-node", "onnxruntime-common")     # tylko dla `dembrandt --ai`, którego flota nie używa
SPRAWDZ = ("hyperframes", "inspo-mcp", "lighthouse", "playwright-core", "sharp")   # paczki, które muszą być po npm ci
WINDOWS = os.name == "nt"
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


class BladNodeFloty(RuntimeError):
    """npm ci się nie udał albo czegoś brak (komunikat po polsku)."""


def suma_locka(katalog: Path = TU) -> str:
    """sha256 package-lock.json z LF (kopia z core.autocrlf=true miałaby CRLF i inną sumę)."""
    return hashlib.sha256((Path(katalog) / "package-lock.json").read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def katalog_wersji(program: Path, suma: str) -> Path:
    return Path(program) / "node-floty" / suma[:12]


def wpis(katalog: Path, suma: str, bin_ffmpeg: Iterable[Path] = (), cache: Path | None = None) -> dict:
    """Wpis narzedzia.json dla gotowego katalogu (bez sprawdzania dysku); `cache` = `<root>/cache`."""
    nm = Path(katalog) / "node_modules"
    env = {"NODE_PATH": str(nm), "HYPERFRAMES_NO_TELEMETRY": "1", "HYPERFRAMES_NO_UPDATE_CHECK": "1",
           "HYPERFRAMES_NO_AUTO_INSTALL": "1"}
    rozsz = ".exe" if WINDOWS else ""
    katalogi = [Path(k) for k in bin_ffmpeg]
    for program, zmienna in (("ffmpeg", "HYPERFRAMES_FFMPEG_PATH"), ("ffprobe", "HYPERFRAMES_FFPROBE_PATH")):
        p = next((k / f"{program}{rozsz}" for k in katalogi if (k / f"{program}{rozsz}").is_file()), None)
        if p:
            env[zmienna] = str(p)
    if cache:
        env["HYPERFRAMES_EXTRACT_CACHE_DIR"] = str(Path(cache) / "hyperframes")
    return {"wersja": suma[:12], "katalog": str(katalog), "bin": [str(nm / ".bin")], "env": env}


def gotowy(katalog: Path, suma: str) -> bool:
    """Znacznik z tą samą sumą locka i paczki z SPRAWDZ na dysku."""
    try:
        if (Path(katalog) / ZNACZNIK).read_text(encoding="utf-8").strip() != suma:
            return False
    except OSError:
        return False
    nm = Path(katalog) / "node_modules"
    return all((nm / p / "package.json").is_file() for p in SPRAWDZ)


def env_npm(npm: Path | str, cache: Path, katalog: Path) -> dict:
    """npm bez konfiguracji właściciela (~/.npmrc i globalny npmrc zastępują puste pliki w `katalog`), bez pytania
    o nowszego npm, z cache Jarva; node obok npm na początku PATH (na POSIX npm to skrypt `#!/usr/bin/env node`)."""
    puste = []
    for nazwa in (".npmrc-uzytkownika", ".npmrc-globalny"):
        p = Path(katalog) / nazwa
        p.write_text("", encoding="utf-8")
        puste.append(str(p))
    env = {k: v for k, v in os.environ.items() if not k.lower().startswith("npm_config_") and k.upper() != "NODE_ENV"}
    env.update({"npm_config_cache": str(cache), "npm_config_userconfig": puste[0], "npm_config_globalconfig": puste[1],
                "npm_config_update_notifier": "false", "npm_config_fund": "false", "npm_config_audit": "false",
                "PUPPETEER_SKIP_DOWNLOAD": "1", "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1"})
    klucz = next((k for k in env if k.upper() == "PATH"), "PATH")
    env[klucz] = os.pathsep.join([str(Path(npm).parent), env.get(klucz, "")]).rstrip(os.pathsep)
    return env


def zainstaluj(program: Path, npm: Path | str, *, cache: Path, bin_ffmpeg: Iterable[Path] = (),
               log: Callable[[str], None] = print) -> tuple[dict, bool]:
    """npm ci z locka tej wersji do `<program>/node-floty/<skrót>`; (wpis narzedzia.json, czy coś zainstalowano).
    `cache` = `<root>/cache` (npm w `npm/`, klatki HyperFrames w `hyperframes/`)."""
    for plik in PLIKI:
        if not (TU / plik).is_file():
            raise BladNodeFloty(f"brak {TU / plik} w kodzie Jarva")
    suma = suma_locka()
    bin_ffmpeg = list(bin_ffmpeg)
    katalog = katalog_wersji(program, suma)
    if gotowy(katalog, suma):
        return wpis(katalog, suma, bin_ffmpeg, cache), False
    nowy = katalog.with_name(katalog.name + ".new")
    if nowy.exists():
        shutil.rmtree(nowy, ignore_errors=True)
    nowy.mkdir(parents=True, exist_ok=True)
    for plik in PLIKI:                               # z LF, jak w repo (suma locka liczona tak samo)
        (nowy / plik).write_bytes((TU / plik).read_bytes().replace(b"\r\n", b"\n"))
    npm_cache = Path(cache) / "npm"
    npm_cache.mkdir(parents=True, exist_ok=True)
    log(f"narzędzia npm floty: npm ci z package-lock.json ({suma[:12]}, bez skryptów instalacyjnych)…")
    argv = [str(npm), "ci", "--ignore-scripts", "--omit=dev", "--no-audit", "--no-fund", "--loglevel=error"]
    r = subprocess.run(argv, cwd=nowy, env=env_npm(npm, npm_cache, nowy), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=BEZ_OKNA, timeout=1800)
    if r.returncode != 0:
        ogon = "\n".join(f"    {x}" for x in (r.stderr or r.stdout or "").strip().splitlines()[-8:])
        raise BladNodeFloty(f"npm ci w {nowy} nie przeszedł (kod {r.returncode}):\n{ogon}")
    for paczka in CIEZKIE:
        shutil.rmtree(nowy / "node_modules" / paczka, ignore_errors=True)
    brak = [p for p in SPRAWDZ if not (nowy / "node_modules" / p / "package.json").is_file()]
    if brak:
        raise BladNodeFloty(f"po npm ci brak paczek: {', '.join(brak)}")
    for plik in (".npmrc-uzytkownika", ".npmrc-globalny"):
        (nowy / plik).unlink(missing_ok=True)
    (nowy / ZNACZNIK).write_text(suma + "\n", encoding="utf-8")
    if katalog.exists():
        shutil.rmtree(katalog, ignore_errors=True)
    os.replace(nowy, katalog)
    return wpis(katalog, suma, bin_ffmpeg, cache), True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("program", help="katalog <program> instalacji Jarva")
    ap.add_argument("--npm", required=True, help="npm z Node z manifestu (Windows: npm.cmd)")
    ap.add_argument("--cache", required=True, help="cache Jarva (<root>/cache: npm w npm/, HyperFrames w hyperframes/)")
    ap.add_argument("--ffmpeg", action="append", default=[],
                    help="katalog bin z ffmpeg albo ffprobe z manifestu (HYPERFRAMES_FFMPEG_PATH, _FFPROBE_PATH)")
    a = ap.parse_args(argv)
    try:
        spis, zmiana = zainstaluj(Path(a.program), a.npm, cache=Path(a.cache), bin_ffmpeg=[Path(k) for k in a.ffmpeg],
                                  log=lambda t: print(t, file=sys.stderr))
    except (BladNodeFloty, OSError, subprocess.SubprocessError) as e:
        print(f"node_floty: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"zmiana": zmiana, "wpis": spis}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
