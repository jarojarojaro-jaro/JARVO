"""Narzędzia npm floty natywnie (docs/NATYWNIE.md P02, M02, I32): infra/node → `<program>/node-floty/<skrót locka>`.

    zainstaluj(program, npm, *, cache, bin_ffmpeg=(), log=print) -> (wpis, zmiana)   # wpis narzedzia.json "node-floty"
    python -I node_floty.py <program> --npm <npm> --cache <root>/cache [--ffmpeg <katalog bin> …]

W obrazie te same paczki z tego samego locka instaluje infra/Dockerfile (`npm ci` w /opt/jarvo/node; globalny bin
npm ma tylko dowiązanie do tej kopii HyperFrames, żeby `npx hyperframes` ze skilli nie pobierał paczki). Natywnie
krok instalatora „Narzędzia npm floty” (jarvo/instalator.py) kopiuje package.json i package-lock.json tej wersji kodu
do `<program>/node-floty/<12 znaków sumy locka>` i woła `npm ci --ignore-scripts --omit=dev` (npm i node z Node.js
z manifestu, bez konfiguracji npm właściciela): same paczki z locka, każda z sumą integrity z registry.npmjs.org, bez
skryptów instalacyjnych (agent-browser przychodzi z manifestu jako binarka, esbuild bierze program z paczki swojej
platformy, onnxruntime-node niczego nie pobiera). Potem znika onnxruntime-node i onnxruntime-common (model ML
dembrandta tylko dla flagi --ai, ok. 0,5 GB, jak w obrazie), a znacznik `.jarvo-lock` z sumą locka mówi, że katalog
jest gotowy: drugi przebieg z tym samym lockiem niczego nie robi, a nowy lock trafia do nowego katalogu obok (na
Windows załadowanych plików .node nie da się nadpisać). `<program>/node-floty/node_modules` to stała ścieżka
(alias_biezacy: junction na Windows, dowiązanie względne na macOS i Linuksie) do node_modules bieżącego locka: tę
ścieżkę wpisuje build floty (scripts/build.py, domyślne `--node-modules`, bo jarvo/flota.py nie przekazuje mu
NODE_PATH) w polecenia serwerów MCP z Node (inspo-mcp Weba).

Wpis dla `<stan>/narzedzia.json` (jarvo/srodowisko.py składa z niego środowisko procesów Jarva):
  bin  node_modules/.bin w PATH: `hyperframes`, `lighthouse`, `svgo`… (na Windows pliki .cmd, w Git Bash skrypty sh),
  env  NODE_PATH (playwright-core i three dla skryptów floty, serwery MCP z Node, build.py), HYPERFRAMES_NO_TELEMETRY
       i HYPERFRAMES_NO_UPDATE_CHECK (jak ENV w obrazie: bez PostHoga i bez pytania npm o nowszą wersję; przy
       NO_UPDATE_CHECK hyperframes 0.8.78 nie instaluje też nowszej wersji w tle), do tego HYPERFRAMES_NO_AUTO_INSTALL
       na wypadek nowszej wersji, która rozdzieli te przełączniki; na Windows i macOS HYPERFRAMES_RENDER_DETACHED
       (strażnik przodków renderu bez sprawdzania tożsamości procesów myli odzyskane PID-y i przerywa render; na
       Linuksie i w obrazie sprawdza czas startu, więc zostaje); HYPERFRAMES_FFMPEG_PATH i HYPERFRAMES_FFPROBE_PATH na
       programy z katalogów `bin_ffmpeg` (ffmpeg z manifestu; na macOS ffmpeg i ffprobe są w osobnych katalogach),
       HYPERFRAMES_EXTRACT_CACHE_DIR w `<root>/cache/hyperframes` (domyślnie %TEMP%, czyli zwykle dysk C:);
       przeglądarkę daje już wpis chrome-headless-shell (HYPERFRAMES_BROWSER_PATH); npm_config_prefix na
       `<katalog>/npm-prefix` (prefix_npm: globalny bin npm z `hyperframes`, jak dowiązanie w obrazie), bo `npx
       hyperframes` ze skilli HyperFrames szuka programu w globalnym bin npm, nie w PATH, a bez niego pobrałby z
       rejestru najnowszą wersję; `npm install -g` agenta zostaje wtedy w katalogu Jarva, nie w profilu właściciela.
Cache npm: `<root>/cache/npm-floty` (CACHE_NPM), osobno od cache frontu panelu (`<root>/cache/npm`, jarvo/hermes.py):
po udanej instalacji instalator go usuwa, bo gotowy katalog wersji go nie potrzebuje. Sama biblioteka standardowa:
moduł ładuje instalator po ścieżce, jak infra/bin/agent_browser.py.
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
CACHE_NPM = "npm-floty"                                  # <root>/cache/npm-floty: paczki z locka na czas npm ci
CIEZKIE = ("onnxruntime-node", "onnxruntime-common")     # tylko dla `dembrandt --ai`, którego flota nie używa
# paczki, które muszą być po npm ci (three: podgląd warsztatu 3D, cad.py; playwright-core: skrypty .cjs floty)
SPRAWDZ = ("hyperframes", "inspo-mcp", "lighthouse", "playwright-core", "sharp", "three")
# globalny prefix npm procesów Jarva (npm_config_prefix) z programami, które skille wołają przez npx: `npx hyperframes`
# szuka programu w node_modules/.bin projektu i w globalnym bin npm, nie w PATH, więc bez tego wpisu pobrałby najnowszą
# wersję z rejestru (bez przeglądu i bez sumy z locka); `npm install -g` agenta trafia tu, a nie do profilu właściciela
PREFIX = "npm-prefix"
GLOBALNE = ("hyperframes", "hyperframes-localize-fonts")
ALIAS = "node_modules"                 # <program>/node-floty/node_modules → node_modules bieżącego locka
WINDOWS = os.name == "nt"
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


class BladNodeFloty(RuntimeError):
    """npm ci się nie udał albo czegoś brak (komunikat po polsku)."""


def suma_locka(katalog: Path = TU) -> str:
    """sha256 package-lock.json z LF (kopia z core.autocrlf=true miałaby CRLF i inną sumę)."""
    return hashlib.sha256((Path(katalog) / "package-lock.json").read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def katalog_wersji(program: Path, suma: str) -> Path:
    return Path(program) / "node-floty" / suma[:12]


def _zapisz(p: Path, tresc: str, nowa_linia: str) -> bool:
    try:
        if p.read_bytes() == tresc.encode("utf-8"):
            return False
    except OSError:
        pass
    p.write_text(tresc, encoding="utf-8", newline=nowa_linia)
    return True


def prefix_npm(katalog: Path, *, windows: bool = WINDOWS) -> bool:
    """`<katalog>/npm-prefix`: globalny bin npm z programami GLOBALNE tej kopii (Windows: `<prefix>\\<program>.cmd`
    i plik bez rozszerzenia, który sprawdza npx; macOS i Linux: `<prefix>/bin/<program>`, dowiązanie względne do
    node_modules/.bin). Ścieżki względne: katalog działa po zmianie nazwy z `.new`. True = coś zapisano."""
    p = Path(katalog) / PREFIX
    zmiana = False
    for program in GLOBALNE:
        if not (Path(katalog) / "node_modules" / ".bin" / (f"{program}.cmd" if windows else program)).exists():
            continue
        if windows:
            p.mkdir(parents=True, exist_ok=True)
            zmiana |= _zapisz(p / f"{program}.cmd", f'@"%~dp0..\\node_modules\\.bin\\{program}.cmd" %*\r\n', "")
            zmiana |= _zapisz(p / program, f'#!/bin/sh\nexec "$(dirname "$0")/../node_modules/.bin/{program}" "$@"\n',
                              "\n")
            continue
        (p / "bin").mkdir(parents=True, exist_ok=True)
        cel, wskazanie = p / "bin" / program, f"../../node_modules/.bin/{program}"
        if cel.is_symlink() and os.readlink(cel) == wskazanie:
            continue
        if cel.is_symlink() or cel.exists():
            cel.unlink()
        os.symlink(wskazanie, cel)
        zmiana = True
    return zmiana


def _dowiazanie(p: Path) -> bool:
    """Dowiązanie symboliczne albo (Windows) junction, także wiszące; zwykły katalog i plik = False."""
    try:
        st = os.lstat(p)
    except OSError:
        return False
    if os.path.islink(p):
        return True
    return bool(WINDOWS and getattr(st, "st_reparse_tag", 0) == 0xA0000003)     # IO_REPARSE_TAG_MOUNT_POINT


def alias_biezacy(katalog: Path) -> bool:
    """`<program>/node-floty/node_modules` → `<katalog>/node_modules` (katalog wersji bieżącego locka): Windows
    junction (bez uprawnień administratora), macOS i Linux dowiązanie względne. Stary alias (inny lock, wiszący)
    zastępuje; zwykłego katalogu z plikami nie rusza (BladNodeFloty). True = coś zmieniono."""
    link = Path(katalog).parent / ALIAS
    cel = Path(katalog) / "node_modules"
    if _dowiazanie(link):
        try:
            if os.path.samefile(link, cel):
                return False
        except OSError:                              # wiszący alias (usunięty katalog wersji)
            pass
        if WINDOWS:
            os.rmdir(link)                           # junction: znika sam wpis, nie zawartość celu
        else:
            os.unlink(link)
    elif os.path.lexists(link):
        raise BladNodeFloty(f"{link} jest zwykłym katalogiem, a nie dowiązaniem do narzędzi npm floty: usuń go "
                            "i uruchom instalację jeszcze raz")
    if WINDOWS:
        import _winapi
        _winapi.CreateJunction(str(cel), str(link))
    else:
        os.symlink(f"{Path(katalog).name}/node_modules", link, target_is_directory=True)
    return True


def wpis(katalog: Path, suma: str, bin_ffmpeg: Iterable[Path] = (), cache: Path | None = None) -> dict:
    """Wpis narzedzia.json dla gotowego katalogu (bez sprawdzania dysku); `cache` = `<root>/cache`."""
    nm = Path(katalog) / "node_modules"
    env = {"NODE_PATH": str(nm), "HYPERFRAMES_NO_TELEMETRY": "1", "HYPERFRAMES_NO_UPDATE_CHECK": "1",
           "HYPERFRAMES_NO_AUTO_INSTALL": "1", "npm_config_prefix": str(Path(katalog) / PREFIX)}
    if WINDOWS or sys.platform == "darwin":
        # strażnik renderu HyperFrames 0.8.78 poza Linuksem sprawdza tylko, czy PID-y przodków żyją: łańcuch rodziców
        # z migawki procesów sięga przez martwy proces (np. ten, który uruchomił nadzorcę) do obcego procesu
        # o odzyskanym PID-zie, a jego koniec przerywa render („render_cancelled_parent_exited”, próba na Windows 11)
        env["HYPERFRAMES_RENDER_DETACHED"] = "1"
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
    `cache` = `<root>/cache` (paczki npm w `npm-floty/`, klatki HyperFrames w `hyperframes/`)."""
    for plik in PLIKI:
        if not (TU / plik).is_file():
            raise BladNodeFloty(f"brak {TU / plik} w kodzie Jarva")
    suma = suma_locka()
    bin_ffmpeg = list(bin_ffmpeg)
    katalog = katalog_wersji(program, suma)
    if gotowy(katalog, suma):                        # katalog sprzed prefiksu i aliasu dostaje je teraz (bez npm)
        zmiana = prefix_npm(katalog)
        return wpis(katalog, suma, bin_ffmpeg, cache), alias_biezacy(katalog) or zmiana
    nowy = katalog.with_name(katalog.name + ".new")
    if nowy.exists():
        shutil.rmtree(nowy, ignore_errors=True)
    nowy.mkdir(parents=True, exist_ok=True)
    try:
        for plik in PLIKI:                           # z LF, jak w repo (suma locka liczona tak samo)
            (nowy / plik).write_bytes((TU / plik).read_bytes().replace(b"\r\n", b"\n"))
        npm_cache = Path(cache) / CACHE_NPM
        npm_cache.mkdir(parents=True, exist_ok=True)
        log(f"narzędzia npm floty: npm ci z package-lock.json ({suma[:12]}, bez skryptów instalacyjnych)…")
        argv = [str(npm), "ci", "--ignore-scripts", "--omit=dev", "--no-audit", "--no-fund", "--loglevel=error"]
        try:
            r = subprocess.run(argv, cwd=nowy, env=env_npm(npm, npm_cache, nowy), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", creationflags=BEZ_OKNA, timeout=1800)
        except subprocess.TimeoutExpired:
            raise BladNodeFloty(f"npm ci w {nowy} trwał ponad 30 min (wolna albo przerwana sieć)") from None
        except OSError as e:
            raise BladNodeFloty(f"nie uruchomię {npm} ({e.strerror or e})") from None
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
        prefix_npm(nowy)
        (nowy / ZNACZNIK).write_text(suma + "\n", encoding="utf-8")
    except BaseException:                            # niepełny katalog nie zostaje (paczki są w cache npm)
        shutil.rmtree(nowy, ignore_errors=True)
        raise
    if katalog.exists():
        shutil.rmtree(katalog, ignore_errors=True)
    os.replace(nowy, katalog)
    alias_biezacy(katalog)
    return wpis(katalog, suma, bin_ffmpeg, cache), True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("program", help="katalog <program> instalacji Jarva")
    ap.add_argument("--npm", required=True, help="npm z Node z manifestu (Windows: npm.cmd)")
    ap.add_argument("--cache", required=True,
                    help="cache Jarva (<root>/cache: paczki npm w npm-floty/, HyperFrames w hyperframes/)")
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
