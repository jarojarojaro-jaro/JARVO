"""Hermes natywnie z przypięcia (docs/NATYWNIE.md: H01, H02, H03, H13, H16, H23, H24, I13; c3 punkt 5, c4).

To, co w kontenerze robił obraz Hermesa, robimy sami, bez instalatorów Hermesa (scripts/install.ps1 i install.sh):
tamte pobierają uv, Node i PortableGit bez sum, ustawiają HERMES_HOME i PATH użytkownika, a gdy `uv sync --locked`
się nie uda, po cichu instalują z PyPI bez sum (H01, H02). Pin (repo, tag, commit, dodatki) jest w jednym miejscu:
vendor/natywne.yaml, czytany przez `manifest.hermes(app)`.

`zainstaluj`  `git clone --filter=blob:none --no-checkout` do `<program>/hermes/<commit[:12]>.new`, potem
              `git -c core.longpaths=true -c core.autocrlf=false checkout <commit>` i kontrola `rev-parse HEAD`;
              dopiero zgodny checkout dostaje nazwę `<commit[:12]>` (przerwany klon nie udaje gotowego). Potem
              `uv sync --locked --extra <dodatek>…` (venv w `.venv`, H02) z UV_PYTHON (nasz Python z PBS),
              UV_PYTHON_DOWNLOADS=never, UV_CACHE_DIR=<cache>/uv i UV_LINK_MODE=copy (c4: na Windows załadowanych .pyd
              nie da się nadpisać). BEZ UV_NO_CONFIG: z nim uv nie czyta [tool.uv] z pyproject.toml Hermesa (m.in.
              exclude-newer), więc lock nie pasuje (sprawdzone 2026-10-24 na f97608f: „The lockfile at `uv.lock` needs
              to be updated”), a instalator Hermesa schodzi wtedy do PyPI bez sum. Zmienne UV_* z otoczenia
              właściciela odcinamy (UV_NO_CONFIG, UV_INDEX_URL…), a uv.toml
              użytkownika zasłania pusty katalog: na Windows uv 0.12.13 czyta go z %APPDATA%\\uv (sprawdzone
              2026-10-24; XDG_CONFIG_HOME na Windows nie działa), na POSIX z XDG_CONFIG_HOME i XDG_CONFIG_DIRS
              (c3 punkt 5). Błąd locka albo sumy kończy instalację wyjątkiem: nigdy `uv pip install` w zastępstwie.
              Znacznik `.jarvo-hermes.json` (commit, dodatki, Python) sprawia, że drugi przebieg nic nie robi.
              Uwaga: build-system projektu (setuptools==83.0.0 i wheel bez wersji) uv pobiera do izolowanej budowy
              bez sum, bo uv.lock nie obejmuje zależności budowy; tak samo robi obraz Hermesa (`uv pip install -e .`).
`web_dist`    Front dashboardu z web/: `npm ci --ignore-scripts --no-audit --no-fund --include=dev` (package-lock.json
              z sumami integrity; --include=dev, bo odziedziczone NODE_ENV=production pomija tsc i vite, por.
              hermes_cli/main_web_build.py:317) i `npm run build` do hermes_cli/web_dist, cache npm w <cache>/npm.
              Docelowo dist z łatkami Jarva zbuduje CI (S12, P05); ta droga jest dla dewelopera i na zapas.
`konfiguracja_bezpieczna`  config.yaml w HERMES_HOME Jarva przez CLI Hermesa (`config get --json` i `config set`,
              hermes_cli/config.py:3479 i :3603). Klucze z f97608f (I13):
              - security.tirith_enabled: false (domyślne true, config_defaults.py:1753; czyta
                tools/tirith_security.py:53): tirith pobiera binarkę z releases/latest bez sumy (H23).
              - security.allow_lazy_installs: false (config_defaults.py:1765; tools/lazy_deps.py:325): blokuje
                doinstalowywanie paczek z PyPI w locie zawsze; samo HERMES_DISABLE_LAZY_INSTALLS=1 blokuje tylko
                bez trwałego katalogu docelowego (lazy_deps.py:335) (H03).
              - auth.adopt_external_logins: false (config_defaults.py:1724; agent/credential_sources.py:32):
                Jarvo nie pożycza logowań Codex CLI i Claude Code właściciela (H15).
              - updates.check: false (config_defaults.py:2314; hermes_cli/banner.py:388-391 zwraca wtedy None):
                bez pytania GitHuba i bez „Update available … run 'hermes update'” w `--version`
                (_startup_fast.py:214-219), w banerze CLI (banner.py:1011-1017) i w TUI (tui_gateway/server.py:86).
                Panel sam pyta /api/hermes/update/check na stronie System: to ukrywa powłoka Jarva (H16).
              - terminal.home_mode: profile, jeśli ta wersja go zna (config_defaults.py:315; czyta
                hermes_constants.py:1003 przez TERMINAL_HOME_MODE z gateway/run.py:1995 i cli_config_load.py:87).
                Działa tylko, gdy istnieje <HERMES_HOME>/home (hermes_constants.py:941-947), więc go zakładamy (H24).
              Każde wywołanie ma `-p default` (albo `-p <profil>`): bez niego lepki <HERMES_HOME>/active_profile
              przekierowałby zapis do profilu (hermes_cli/main.py:593). Klucz, którego dana wersja Hermesa nie zna,
              CLI zgłasza jako „Config key not set” (config.py:3626): tirith i home_mode wtedy pomijamy, a brak
              pozostałych zatrzymuje instalację (nowa wersja wymaga przeglądu, czym je zastąpiono).
`wersja`, `argv_hermesa`  `<venv>/python -m hermes_cli.main …` (H13): bez polecenia `hermes` w PATH i bez zmiennych
              użytkownika; HERMES_HOME tylko w środowisku procesu. Nigdy `hermes update` (H16).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from . import przenosne, srodowisko
from .sciezki import WINDOWS, Uklad

ZNACZNIK = ".jarvo-hermes.json"          # w checkoucie: commit, dodatki i Python zainstalowanego venvu
ZNACZNIK_WEB = ".jarvo-web-dist.json"    # w checkoucie: commit, z którego zbudowano hermes_cli/web_dist
# git: długie ścieżki i LF z repo na Windows; bez gc i maintenance w tle (trzymałyby pliki przy zmianie nazwy)
GIT_C = ("-c", "core.longpaths=true", "-c", "core.autocrlf=false", "-c", "gc.auto=0",
         "-c", "maintenance.auto=false", "-c", "advice.detachedHead=false")
# zmienne UV_* z otoczenia, które zostają: dotyczą sieci, nie tego, co i skąd instalujemy
UV_ZOSTAJE = ("UV_NATIVE_TLS", "UV_HTTP_TIMEOUT")
CZAS_CLI = 180                          # s na jedno wywołanie CLI Hermesa (config, --version)

# (klucz, wartość dla `config set`, wartość z `config get --json`, czy wymagany w każdej wersji)
BEZPIECZNE = (
    ("security.tirith_enabled", "false", False, False),
    ("security.allow_lazy_installs", "false", False, True),
    ("auth.adopt_external_logins", "false", False, True),
    ("updates.check", "false", False, True),
    ("terminal.home_mode", "profile", "profile", False),
)

_SHA = re.compile(r"[0-9a-f]{40}")
_DODATEK = re.compile(r"[a-z0-9][a-z0-9._-]*")
_PROFIL = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")      # jak hermes_cli/main.py (_PROFILE_NAME_RE)
_POSTEP = re.compile(r"\d{1,3}%")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")             # kolory i czyszczenie linii (vite, npm) poza logiem
_URL_Z_HASLEM = re.compile(r"(\w+://)[^/\s@:]+:[^/\s@]+@")
_WERSJA = re.compile(r"Hermes Agent v(\d[\w.+-]*)")
_FLAGI = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


class BladHermesa(RuntimeError):
    """Instalacja albo konfiguracja Hermesa się nie udała (komunikat po polsku, bez sekretów)."""


def argv_hermesa(checkout: Path, *argumenty: str) -> list[str]:
    """Polecenie CLI Hermesa: python venvu checkoutu + `-m hermes_cli.main` + argumenty (H13)."""
    return [str(srodowisko.hermes_python(Path(checkout))), "-m", "hermes_cli.main", *(str(a) for a in argumenty)]


def katalog_checkoutu(u: Uklad, commit: str) -> Path:
    """`<program>/hermes/<commit[:12]>`: wersje obok siebie, `jarvo update` robi nowy katalog (H16, c4)."""
    return u.program / "hermes" / commit[:12]


# --- pomocnicze ---------------------------------------------------------------------------------------------------

def _bez_sekretow(tekst: str) -> str:
    """Hasło albo token w adresie (https://ktoś:token@…) nie trafia do logu."""
    return _URL_Z_HASLEM.sub(r"\1***@", tekst)


def _ustaw(env: dict[str, str], klucz: str, wartosc: str) -> None:
    """Ustawia zmienną; na Windows usuwa najpierw tę samą nazwę inną wielkością liter (os.environ ma wielkie)."""
    if WINDOWS:
        for k in [k for k in env if k.upper() == klucz.upper()]:
            del env[k]
    env[klucz] = wartosc


def _bez(env: dict[str, str], *przedrostki: str, zostaw: Iterable[str] = ()) -> dict[str, str]:
    zostaw = {z.upper() for z in zostaw}
    return {k: v for k, v in env.items() if not k.upper().startswith(przedrostki) or k.upper() in zostaw}


def _baza() -> dict[str, str]:
    """os.environ bez zmiennych, które przestawiłyby narzędzia na cudzy Python, venv albo Hermesa (srodowisko.OBCE)."""
    obce = {o.upper() for o in srodowisko.OBCE}
    return {k: v for k, v in os.environ.items() if k.upper() not in obce}


def _program(sciezka: str | os.PathLike | None, nazwa: str) -> str:
    """Pełna ścieżka programu: podana ścieżka istniejącego pliku albo goła nazwa szukana w PATH (shutil.which zna
    .exe i .cmd na Windows). Goła nazwa nie trafia do pliku o tej nazwie w bieżącym katalogu."""
    if sciezka:
        tekst = str(sciezka)
        if os.path.dirname(tekst):
            if Path(tekst).is_file():
                return tekst
        else:
            znaleziony = przenosne.program(tekst)
            if znaleziony:
                return znaleziony
    raise BladHermesa(f"Nie znalazłem programu {nazwa}" + (f" ({sciezka})." if sciezka else "."))


def _teraz() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ta_sama(a, b) -> bool:
    if not a or not b:
        return False
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _strumien(argv: list, *, cwd: Path, env: dict, log: Callable[[str], None],
              przemilcz: Callable[[str], bool] | None = None) -> tuple[int, list[str]]:
    """Uruchamia program, a jego wyjście (stdout i stderr) przekazuje do `log` linia po linii; paski postępu co 5 s.
    Zwraca kod wyjścia i ostatnie linie (do komunikatu błędu)."""
    ogon: deque[str] = deque(maxlen=40)
    try:
        proc = subprocess.Popen([str(a) for a in argv], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", creationflags=_FLAGI)
    except OSError as e:
        raise BladHermesa(f"Nie uruchomię {Path(str(argv[0])).name}: {e}") from None
    ostatni_postep = 0.0
    with proc:
        for surowa in proc.stdout:
            linia = _bez_sekretow(_ANSI.sub("", surowa).rstrip())
            if not linia.strip():
                continue
            ogon.append(linia)
            if przemilcz and przemilcz(linia):
                continue
            if _POSTEP.search(linia) and "100%" not in linia:
                teraz = time.monotonic()
                if teraz - ostatni_postep < 5:
                    continue
                ostatni_postep = teraz
            log(f"    {linia}")
        kod = proc.wait()
    return kod, list(ogon)


def _wywolaj(argv: list, *, env: dict, cwd: Path, opis: str, czas: int = CZAS_CLI) -> subprocess.CompletedProcess:
    """Krótkie wywołanie z przechwyconym wyjściem i limitem czasu (stdin zamknięty: nic nie czeka na człowieka)."""
    try:
        return subprocess.run([str(a) for a in argv], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=czas,
                              creationflags=_FLAGI)
    except subprocess.TimeoutExpired:
        raise BladHermesa(f"{opis}: brak odpowiedzi po {czas} s.") from None
    except OSError as e:
        raise BladHermesa(f"{opis}: nie uruchomię {Path(str(argv[0])).name}: {e}") from None


def _koncowka(*teksty: str, linie: int = 8) -> str:
    wszystkie = [_bez_sekretow(x) for t in teksty if t for x in t.splitlines() if x.strip()]
    return "\n".join(f"    {x}" for x in wszystkie[-linie:])


def _usun_drzewo(p: Path) -> None:
    """rmtree, który radzi sobie z plikami tylko do odczytu (paczki gita na Windows)."""
    def odblokuj(funkcja, sciezka, _blad):
        os.chmod(sciezka, stat.S_IWRITE)
        funkcja(sciezka)
    shutil.rmtree(p, onexc=odblokuj)


def _przenies(z: Path, do: Path, proby: int = 40) -> None:
    """Zmiana nazwy katalogu; na Windows ponawia, gdy plik chwilowo trzyma antywirus albo indeksowanie."""
    for i in range(proby):
        try:
            os.replace(z, do)
            return
        except PermissionError as e:
            if not WINDOWS or i == proby - 1:
                raise BladHermesa(f"Nie mogę zmienić nazwy {z} na {do.name}: {e}. Zamknij programy, które "
                                  "mogą trzymać pliki w tym katalogu, i uruchom instalację jeszcze raz.") from None
            time.sleep(0.25)


def _wyklucz(checkout: Path, *nazwy: str) -> None:
    """Znaczniki Jarva w `.git/info/exclude`: `git status` checkoutu zostaje czysty (doctor może to sprawdzać)."""
    info = checkout / ".git" / "info"
    if not (checkout / ".git").is_dir():
        return
    plik = info / "exclude"
    try:
        tresc = plik.read_text(encoding="utf-8")
    except FileNotFoundError:
        tresc = ""
    brak = [f"/{n}" for n in nazwy if f"/{n}" not in tresc.splitlines()]
    if brak:
        if tresc and not tresc.endswith("\n"):
            tresc += "\n"
        przenosne.zapisz_atomowo(plik, tresc + "".join(f"{b}\n" for b in brak))


# --- git --------------------------------------------------------------------------------------------------------

def _env_git(sufit: Path) -> dict[str, str]:
    """Bez GIT_* z otoczenia (GIT_DIR, GIT_WORK_TREE, GIT_CONFIG_PARAMETERS, GIT_ASKPASS…) i bez okien z pytaniem
    o hasło; GIT_CEILING_DIRECTORIES nie pozwala wejść do repo nad katalogiem Jarva."""
    env = _bez(_baza(), "GIT_")
    env.pop("SSH_ASKPASS", None)
    _ustaw(env, "GIT_TERMINAL_PROMPT", "0")
    _ustaw(env, "GCM_INTERACTIVE", "never")
    _ustaw(env, "GIT_CEILING_DIRECTORIES", str(sufit))
    return env


def _head(git: str, katalog: Path, env: dict) -> str | None:
    if not (katalog / ".git").exists():
        return None
    w = _wywolaj([git, "rev-parse", "HEAD"], env=env, cwd=katalog, opis="git rev-parse")
    return w.stdout.strip().lower() if w.returncode == 0 else None


def _checkout(repo: str, commit: str, docelowy: Path, *, git: str, log) -> None:
    env = _env_git(docelowy.parent)
    if docelowy.exists():
        head = _head(git, docelowy, env)
        if head is None:
            raise BladHermesa(f"{docelowy} istnieje, ale nie jest checkoutem gita. Usuń ten katalog i uruchom "
                              "instalację jeszcze raz.")
        if head != commit:
            raise BladHermesa(f"{docelowy} ma commit {head[:12]}, a przypięty jest {commit[:12]}. Usuń ten katalog "
                              "i uruchom instalację jeszcze raz (nie poprawiam cudzych zmian w kodzie Hermesa).")
        _wyklucz(docelowy, ZNACZNIK, ZNACZNIK_WEB)
        return
    nowy = docelowy.with_name(docelowy.name + ".new")
    if nowy.exists():
        _usun_drzewo(nowy)
    nowy.parent.mkdir(parents=True, exist_ok=True)
    log(f"Hermes: pobieram kod z {_bez_sekretow(repo)} (git clone bez blobów historii)…")
    kod, ogon = _strumien([git, *GIT_C, "-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=120",
                           "clone", "--filter=blob:none", "--no-checkout", "--progress",
                           "-c", "core.longpaths=true", "-c", "core.autocrlf=false", repo, str(nowy)],
                          cwd=nowy.parent, env=env, log=log)
    if kod:
        raise BladHermesa(f"git clone {_bez_sekretow(repo)} nie przeszedł (kod {kod}):\n" + _koncowka(*ogon))
    w = _wywolaj([git, "cat-file", "-t", commit], env=env, cwd=nowy, opis="git cat-file")
    if w.returncode or w.stdout.strip() != "commit":
        log(f"Hermes: commitu {commit[:12]} nie ma w gałęziach repo, pobieram go wprost…")
        kod, ogon = _strumien([git, *GIT_C, "fetch", "--filter=blob:none", "origin", commit], cwd=nowy, env=env,
                              log=log)
        if kod:
            raise BladHermesa(f"Commitu {commit[:12]} nie ma w {_bez_sekretow(repo)} (git fetch: kod {kod}):\n"
                              + _koncowka(*ogon))
    log(f"Hermes: checkout {commit[:12]} (git dociąga pliki tego commitu, bez paska postępu)…")
    kod, ogon = _strumien([git, *GIT_C, "checkout", commit], cwd=nowy, env=env, log=log)
    if kod:
        raise BladHermesa(f"git checkout {commit[:12]} nie przeszedł (kod {kod}):\n" + _koncowka(*ogon))
    head = _head(git, nowy, env)
    if head != commit:
        raise BladHermesa(f"Po checkoucie HEAD to {head or 'nic'}, a przypięty jest {commit}: nie instaluję kodu "
                          "innego niż przypięty.")
    _wyklucz(nowy, ZNACZNIK, ZNACZNIK_WEB)
    _przenies(nowy, docelowy)


# --- uv ---------------------------------------------------------------------------------------------------------

def _env_uv(u: Uklad, python: str) -> dict[str, str]:
    env = _bez(_baza(), "UV_", zostaw=UV_ZOSTAJE)
    pusty = u.stan / "bez-konfiguracji-uv"      # zamiast uv.toml właściciela (zawsze pusty katalog)
    pusty.mkdir(parents=True, exist_ok=True)
    for klucz, wartosc in (("UV_PYTHON", python), ("UV_PYTHON_DOWNLOADS", "never"),
                           ("UV_CACHE_DIR", str(u.cache / "uv")), ("UV_LINK_MODE", "copy")):
        _ustaw(env, klucz, wartosc)
    if WINDOWS:
        _ustaw(env, "APPDATA", str(pusty))      # %APPDATA%\uv\uv.toml; przy okazji bez site-packages użytkownika
    else:
        _ustaw(env, "XDG_CONFIG_HOME", str(pusty))
        _ustaw(env, "XDG_CONFIG_DIRS", str(pusty))
    return env


def _linia_paczki(linia: str) -> bool:
    return linia.startswith((" + ", " - ", " ~ ", " Downloaded "))


def _powod_uv(kod: int, ogon: list[str]) -> str:
    tekst = "\n".join(ogon)
    niski = tekst.lower()
    if "needs to be updated" in niski or ("lockfile" in niski and "--locked" in niski):
        powod = "uv.lock nie pasuje do pyproject.toml tego commitu"
    elif "hash mismatch" in niski:
        powod = "suma pliku z PyPI nie zgadza się z uv.lock"
    elif "wheel for the current platform" in niski or "no wheels with a matching platform" in niski:
        powod = "w uv.lock nie ma gotowej paczki dla tego systemu"
    else:
        powod = "uv zakończył się błędem"
    return (f"Hermes: `uv sync --locked` nie przeszedł (kod {kod}): {powod}. Nie instaluję niczego bez sum z uv.lock "
            "(żadnego `uv pip install` z PyPI w zastępstwie). Ostatnie linie:\n" + _koncowka(*ogon))


def _gotowy(checkout: Path, commit: str, dodatki: list[str], python: str) -> bool:
    z = srodowisko.wczytaj_json(checkout / ZNACZNIK)
    return (z.get("commit") == commit and sorted(z.get("dodatki") or []) == sorted(dodatki)
            and _ta_sama(z.get("python"), python) and srodowisko.hermes_python(checkout).is_file())


def _pin(pin: dict) -> tuple[str, str, list[str], str]:
    commit = str(pin.get("commit") or "").lower()
    repo = str(pin.get("repo") or "")
    dodatki = pin.get("dodatki") or []
    if not _SHA.fullmatch(commit):
        raise BladHermesa(f"Pin Hermesa: commit musi być pełnym SHA (40 znaków), jest {commit[:44]!r}.")
    if not repo.startswith("https://"):
        raise BladHermesa(f"Pin Hermesa: repo tylko przez https (jest {_bez_sekretow(repo)[:60]!r}).")
    if not isinstance(dodatki, list) or not all(isinstance(d, str) and _DODATEK.fullmatch(d) for d in dodatki):
        raise BladHermesa(f"Pin Hermesa: dodatki to lista nazw extras z pyproject.toml (jest {dodatki!r}).")
    return commit, repo, list(dodatki), str(pin.get("tag") or commit[:12])


def zainstaluj(u: Uklad, pin: dict, *, git, uv, python, log: Callable[[str], None] = print) -> Path:
    """Checkout przypiętego commitu Hermesa i `uv sync --locked` z dodatkami z pinu; zwraca katalog checkoutu.
    `git`, `uv`, `python`: ścieżki programów (albo nazwy z PATH). Gotowa instalacja (znacznik z tym samym commitem,
    dodatkami i Pythonem) = bez żadnego wywołania. Każdy błąd to BladHermesa z polskim komunikatem."""
    commit, repo, dodatki, tag = _pin(pin)
    docelowy = katalog_checkoutu(u, commit)
    python = _program(python, "python")
    if _gotowy(docelowy, commit, dodatki, python):
        log(f"Hermes {tag} ({commit[:12]}): już zainstalowany w {docelowy}")
        return docelowy
    git, uv = _program(git, "git"), _program(uv, "uv")
    with przenosne.Zamek(u.stan / "hermes.lock"):
        if _gotowy(docelowy, commit, dodatki, python):        # drugi instalator skończył, gdy czekaliśmy
            return docelowy
        _checkout(repo, commit, docelowy, git=git, log=log)
        (docelowy / ZNACZNIK).unlink(missing_ok=True)
        log(f"Hermes: zależności z uv.lock (uv sync --locked, dodatki: {', '.join(dodatki) or 'brak'})…")
        argv = [uv, "sync", "--locked"]
        for d in dodatki:
            argv += ["--extra", d]
        kod, ogon = _strumien(argv, cwd=docelowy, env=_env_uv(u, python), log=log, przemilcz=_linia_paczki)
        if kod:
            raise BladHermesa(_powod_uv(kod, ogon))
        if not srodowisko.hermes_python(docelowy).is_file():
            raise BladHermesa(f"uv sync skończył się bez błędu, ale nie ma {srodowisko.hermes_python(docelowy)}.")
        przenosne.zapisz_atomowo(docelowy / ZNACZNIK, json.dumps({
            "commit": commit, "tag": pin.get("tag"), "wersja": pin.get("wersja"), "repo": _bez_sekretow(repo),
            "dodatki": dodatki, "python": python, "zainstalowano": _teraz(),
        }, ensure_ascii=False, indent=2) + "\n")
    log(f"Hermes {tag} ({commit[:12]}): gotowy w {docelowy}")
    return docelowy


# --- front dashboardu ---------------------------------------------------------------------------------------------

def _znajdz_npm(u: Uklad) -> str | None:
    """npm z Node Jarva (`<stan>/narzedzia.json`, wpis node), a gdy go nie ma, z PATH (droga dewelopera)."""
    narz = srodowisko.narzedzia(u)
    for nazwa in ("node", "nodejs"):
        wpis = narz.get(nazwa)
        katalogi = [str(Path(k)) for k in (wpis.get("bin") or [])] if isinstance(wpis, dict) else []
        if katalogi:
            znaleziony = przenosne.program("npm", os.pathsep.join(katalogi))
            if znaleziony:
                return znaleziony
    return przenosne.program("npm")


def _env_npm(u: Uklad, npm: str) -> dict[str, str]:
    env = {k: v for k, v in _baza().items() if k.upper() != "NODE_ENV"}
    _ustaw(env, "npm_config_cache", str(u.cache / "npm"))
    _ustaw(env, "npm_config_update_notifier", "false")
    _ustaw(env, "NO_COLOR", "1")
    sciezka = next((v for k, v in env.items() if k.upper() == "PATH"), "")
    _ustaw(env, "PATH", os.pathsep.join([str(Path(npm).parent), sciezka]).rstrip(os.pathsep))  # node obok npm
    return env


def _linia_vite(linia: str) -> bool:
    return bool(re.search(r"web_dist[\\/]", linia))


def _web_gotowy(checkout: Path, dist: Path, commit: str) -> bool:
    return (srodowisko.wczytaj_json(checkout / ZNACZNIK_WEB).get("commit") == commit
            and (dist / "index.html").is_file())


def web_dist(u: Uklad, checkout: Path, *, npm=None, log: Callable[[str], None] = print) -> Path:
    """Buduje front dashboardu z `web/` do `hermes_cli/web_dist` i zwraca ten katalog (HERMES_WEB_DIST panelu).
    Zbudowany front dla tego commitu (znacznik) = bez wywołań npm."""
    checkout = Path(checkout)
    dist = checkout / "hermes_cli" / "web_dist"
    commit = srodowisko.wczytaj_json(checkout / ZNACZNIK).get("commit")
    if not commit:
        raise BladHermesa(f"{checkout}: brak znacznika instalacji Hermesa ({ZNACZNIK}); najpierw zainstaluj().")
    if _web_gotowy(checkout, dist, commit):
        log(f"Hermes: front dashboardu już zbudowany ({dist})")
        return dist
    web = checkout / "web"
    if not (web / "package.json").is_file():
        raise BladHermesa(f"{checkout}: brak web/package.json, nie ma z czego zbudować frontu.")
    npm = _program(npm or _znajdz_npm(u), "npm")
    with przenosne.Zamek(u.stan / "hermes.lock"):
        if _web_gotowy(checkout, dist, commit):
            return dist
        (checkout / ZNACZNIK_WEB).unlink(missing_ok=True)
        env = _env_npm(u, npm)
        log("Hermes: zależności frontu (npm ci z package-lock.json, bez skryptów instalacyjnych)…")
        kod, ogon = _strumien([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--include=dev"],
                              cwd=web, env=env, log=log)
        if kod:
            raise BladHermesa(f"npm ci w {web} nie przeszedł (kod {kod}):\n" + _koncowka(*ogon))
        log("Hermes: budowa frontu (npm run build)…")
        kod, ogon = _strumien([npm, "run", "build"], cwd=web, env=env, log=log, przemilcz=_linia_vite)
        if kod:
            raise BladHermesa(f"npm run build w {web} nie przeszedł (kod {kod}):\n" + _koncowka(*ogon))
        if not (dist / "index.html").is_file():
            raise BladHermesa(f"npm run build skończył się bez błędu, ale nie ma {dist / 'index.html'}.")
        _wyklucz(checkout, ZNACZNIK, ZNACZNIK_WEB)
        przenosne.zapisz_atomowo(checkout / ZNACZNIK_WEB, json.dumps(
            {"commit": commit, "zbudowano": _teraz()}, indent=2) + "\n")
    log(f"Hermes: front dashboardu gotowy ({dist})")
    return dist


# --- konfiguracja ---------------------------------------------------------------------------------------------------

def _z_utf8(env: dict) -> dict[str, str]:
    """Kopia środowiska z wyjściem Pythona w UTF-8 (chyba że wywołujący ustawił inaczej)."""
    wynik = {str(k): str(v) for k, v in dict(env).items()}
    for klucz, wartosc in (("PYTHONUTF8", "1"), ("PYTHONIOENCODING", "utf-8")):
        if not any(k.upper() == klucz for k in wynik):
            wynik[klucz] = wartosc
    return wynik


def _env_hermesa(u: Uklad, env: dict) -> dict[str, str]:
    """Środowisko CLI Hermesa: zawsze HERMES_HOME Jarva, nigdy prywatny Hermes właściciela (c1)."""
    wynik = _z_utf8(env)
    _ustaw(wynik, "HERMES_HOME", str(u.dane))
    return wynik


def _config_get(checkout: Path, env: dict, cwd: Path, profil: str, klucz: str) -> tuple[bool, object]:
    """(czy ta wersja zna klucz, wartość z config.yaml albo domyślna) przez `config get --json`."""
    w = _wywolaj(argv_hermesa(checkout, "-p", profil, "config", "get", klucz, "--json"), env=env, cwd=cwd,
                 opis=f"hermes config get {klucz}")
    if w.returncode:
        if "config key not set" in f"{w.stderr}\n{w.stdout}".lower():
            return False, None
        raise BladHermesa(f"hermes -p {profil} config get {klucz}: kod {w.returncode}:\n"
                          + _koncowka(w.stdout, w.stderr))
    linie = [x for x in w.stdout.splitlines() if x.strip()]
    try:
        return True, json.loads(linie[-1])
    except (IndexError, ValueError):
        raise BladHermesa(f"hermes config get {klucz} --json: nie rozumiem odpowiedzi:\n"
                          + _koncowka(w.stdout)) from None


def konfiguracja_bezpieczna(u: Uklad, checkout: Path, env: dict, log: Callable[[str], None] = print, *,
                            profile: Iterable[str] = ()) -> None:
    """Bezpieczne wartości w config.yaml HERMES_HOME Jarva (lista BEZPIECZNE, źródła w docstringu modułu) przez
    `hermes config set`; potem odczyt kontrolny. `profile`: nazwy profili floty do ustawienia tak samo (I13: we
    wszystkich profilach). Wartość już zgodna = bez zapisu. Brak wymaganego klucza w tej wersji = BladHermesa."""
    checkout = Path(checkout)
    env = _env_hermesa(u, env)
    u.dane.mkdir(parents=True, exist_ok=True)
    profile = list(profile)
    for p in profile:
        if not _PROFIL.fullmatch(p) or p == "default":
            raise BladHermesa(f"Zła nazwa profilu Hermesa: {p!r}.")
    for profil in ["default", *profile]:
        home = u.dane if profil == "default" else u.dane / "profiles" / profil
        gdzie = "" if profil == "default" else f" (profil {profil})"
        for klucz, tekst, oczekiwana, wymagany in BEZPIECZNE:
            jest, obecna = _config_get(checkout, env, u.dane, profil, klucz)
            if not jest:
                if wymagany:
                    raise BladHermesa(f"Ta wersja Hermesa nie zna klucza {klucz}. Zanim ją przypniesz, sprawdź w jej "
                                      "kodzie, czym go zastąpiono (docs/NATYWNIE.md, I13).")
                log(f"Hermes{gdzie}: tej wersji nie dotyczy {klucz} (nie ma takiego klucza), pomijam")
                continue
            if obecna != oczekiwana:
                w = _wywolaj(argv_hermesa(checkout, "-p", profil, "config", "set", klucz, tekst), env=env,
                             cwd=u.dane, opis=f"hermes config set {klucz}")
                if w.returncode:
                    raise BladHermesa(f"hermes -p {profil} config set {klucz} {tekst}: kod {w.returncode}:\n"
                                      + _koncowka(w.stdout, w.stderr))
                jest, obecna = _config_get(checkout, env, u.dane, profil, klucz)
                if obecna != oczekiwana:
                    raise BladHermesa(f"{klucz}{gdzie}: po zapisie Hermes podaje {obecna!r}, a ma być {oczekiwana!r}.")
                log(f"Hermes{gdzie}: {klucz} = {tekst}")
            if klucz == "terminal.home_mode":
                (home / "home").mkdir(parents=True, exist_ok=True)   # bez katalogu Hermes zostawia HOME właściciela


def wersja(checkout: Path, env: dict) -> str:
    """Wersja Hermesa z `hermes --version` (np. "0.21.5"). `env` musi mieć HERMES_HOME Jarva: inaczej Hermes czyta
    i zapisuje (.update_check) w prywatnym katalogu właściciela. Po konfiguracja_bezpieczna() bez pytania GitHuba."""
    if not any(k.upper() == "HERMES_HOME" and v for k, v in dict(env).items()):
        raise BladHermesa("wersja(): środowisko bez HERMES_HOME; użyj srodowisko.srodowisko(u).")
    w = _wywolaj(argv_hermesa(checkout, "--version"), env=_z_utf8(env), cwd=Path(checkout), opis="hermes --version")
    m = _WERSJA.search(w.stdout or "")
    if w.returncode or not m:
        raise BladHermesa(f"hermes --version: kod {w.returncode}, brak wersji w odpowiedzi:\n"
                          + _koncowka(w.stdout, w.stderr))
    return m.group(1)
