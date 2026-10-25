#!/usr/bin/env python3
"""Instalacja albo aktualizacja floty z buildu: Python zamiast scripts/install-fleet.sh (docs/NATYWNIE.md: S07, S08,
K02, H05, H06, H14, H24, H27, W01, W02, W04).

    python install_fleet.py [--dane DIR] [--build DIR] [--repo DIR] [--sekrety DIR | --bez-sekretow]
                            [--narzedzia DIR] [--hermes-python PY] [--natywnie] [--first-run] [--resume-cron]
                            [--podsumowanie PLIK.json] [--czekaj-na-skarbiec S] [--ustawienia-profili PLIK.json]

Wartości domyślne to kontener (/opt/data, /opt/jarvo/build, /opt/jarvo/secrets, <dane>/jarvo/narzedzia, profile
z aliasem), więc tam skrypt robi te same kroki co install-fleet.sh (scripts/deploy.sh woła na razie install-fleet.sh).
Natywnie woła go jarvo/flota.py Pythonem venvu Hermesa: ścieżki instalacji, `--natywnie` (profile bez --alias, bo
alias zasłoniłby polecenie jarvo, H14; katalog <profil>/home dla terminal.home_mode: profile, H24; w kontenerze go
nie zakładamy, bo zmieniłby HOME agentów) i `--bez-sekretow`, gdy sekrety są od razu w .env w <dane>.

Kroki (numeracja jak w install-fleet.sh):
  1.  migracja TARS → Jarvo (scripts/migrate_jarvo.py container), katalogi floty, szablony wiedzy (INDEX.md misji,
      USER.md, brands/_szablon),
  1b. skarbiec wiedzy (K02): `wiedza.py zasiej` (huby z build/wiedza, docs repo, indeks, punkt zapisu git) pod
      blokadą kompilacji `state/wiedza.lock` (ten sam plik i format co wiedza/kompilacja.py: PID i czas), w niej
      lint informacyjny (`lint --json`; błędy idą do logu i podsumowania, nie zatrzymują instalacji),
  2.  profil hosta: scalenie config.yaml (merge_host_config.py; --first-run wymusza model floty), SOUL.md, host.env,
  3.  profile agentów: `hermes profile install` albo `profile update --force-config` z modelem wybranym w panelu
      (profile_model.py), źródło aktualizacji zawsze = bieżący build, skille spoza buildu (prune_skills.py),
      sekrety <agent>.env; katalog profilu bez distribution.yaml instalujemy z --force (dane profilu zostają);
      klucze configu zależne od instalacji z --ustawienia-profili (JSON {"wszystkie": {klucz: wartość},
      "profile": {agent: {klucz: wartość}}}, klucze z kropkami, np. updates.check, terminal.shell_init_files)
      w tym samym przebiegu co `--force-config`, więc drugi przebieg ich nie zmienia,
  3b. klucze API (H05): API_SERVER_KEY hosta i profili, generowane brakujące (secrets.token_hex(32)), istniejących
      nie ruszamy; klucz hosta podany w otoczeniu procesu wygrywa (jak stage2-hook obrazu Hermesa); .env tylko dla
      właściciela (jarvo.przenosne.chron: POSIX 0600, Windows ACL),
  3b2. impeccable: IMPECCABLE_HOME (<narzędzia>/impeccable) w .env profilu; program pobiera launcher `sh` skilla
      (Windows: przy pierwszym użyciu, w Git Bash agenta, bo instalacja floty nie woła powłoki),
  3c. wtyczki jarvo-hq, jarvo-wiedza, jarvo-komputer, jarvo-zgody (te, które są w buildzie): kopia do <dane>/plugins
      z atomową podmianą (katalog .new, dwie zmiany nazwy), ta sama treść = stara kopia zostaje. W profilach: POSIX
      symlink jak `ln -sfn`, Windows junction (bez admina i trybu dewelopera), a gdy system plików ich nie zna, kopia
      (H27, W02). jarvo-wiedza w każdym profilu (dostawca pamięci), komputer i zgody tam, gdzie config profilu
      z buildu je włącza (plugins.enabled); w pozostałych dowiązanie znika. jarvo-hq i jarvo-wiedza (zakładki
      panelu) oraz wtyczki z plugins.enabled configu hosta z buildu włączone w config hosta: `hermes plugins
      enable`, a gdy Hermes jej nie zna (wtyczka samego panelu), enable_plugin.py,
  3d. skórka terminala, 3e. motywy panelu (install_themes.py), 3f. wspólne klucze (share_keys.py),
  4.  tablica kanban (`hermes kanban init` przy --first-run albo bez kanban.db), 5. rutyny Jarva (--resume-cron),
  6.  restart: bez s6 i bez restartu (opcja --no-restart zostaje dla zgodności). Wynik mówi, czy restart jest
      potrzebny (natywnie robi go nadzorca): brama, gdy zmieniło się coś, co czyta (config, profile, klucze,
      wtyczki bramy, tablica); panel, gdy odcisk wtyczek jarvo-hq i jarvo-wiedza różni się od zapisanego po
      ostatnim restarcie panelu (<dane>/plugins/.odcisk-panelu, ten sam wzór co w install-fleet.sh; zapisuje go
      ten, kto zrestartował panel: jarvo.flota.potwierdz_restart_panelu).

Polecenia Hermesa: `<python venvu Hermesa> -P -m hermes_cli.main -p default …` (albo `-p jarvo`) z HERMES_HOME =
--dane, nigdy z domyślnym katalogiem Hermesa właściciela; `-p default` nie pozwala lepkiemu active_profile przenieść
polecenia do innego profilu, a -P nie wpuszcza do sys.path katalogu bieżącego. Skrypty pomocnicze (S08) działają
w tym procesie, więc skrypt uruchamiamy Pythonem Hermesa (share_keys czyta katalog zmiennych Hermesa); ich zapis
YAML idzie na czas wywołania przez _zapis_yaml_lf (LF na każdym systemie, zapis tylko przy zmianie treści).
wiedza.py i migrate_jarvo.py idą jako osobne procesy. Bez bash, sed, diff, cp i ln: filecmp, shutil, hashlib.
Każda linia logu (także wyjście Hermesa i ślad błędu) przechodzi przez maskowanie znanych sekretów z plików .env.
Drugi przebieg niczego nie zmienia (sprawdzone na Windows 11 z Hermesem f97608f: 10 profili, puste `zmiany`, bez
restartu), poza historią skarbca (LOG.md, git, indeks wiedza.db) i znacznikami czasu, które Hermes stawia przy każdym
`profile update`: `installed_at` w distribution.yaml (odcisk profilu go pomija) i `updated_at` w cron/jobs.json
(wątek rutyn bramy czyta rutyny przy każdym tyknięciu, cron/scheduler_tick.py, więc cron/ nie jest w odcisku i
wznowienie rutyn nie wymaga restartu).
"""
from __future__ import annotations

import argparse
import contextlib
import filecmp
import hashlib
import importlib
import io
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import threading
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Callable, Iterator

SKRYPTY = Path(__file__).resolve().parent
if str(SKRYPTY) not in sys.path:
    sys.path.insert(0, str(SKRYPTY))                # pomocnicy (merge_env, share_keys…) i fleetlib
if str(SKRYPTY.parent) not in sys.path:
    sys.path.append(str(SKRYPTY.parent))            # pakiet jarvo (zapis atomowy, chron) na końcu: niczego nie zasłoni
from jarvo import przenosne  # noqa: E402

WINDOWS = os.name == "nt"
ORKIESTRATOR = "jarvo"
WTYCZKI = ("jarvo-hq", "jarvo-wiedza", "jarvo-komputer", "jarvo-zgody")
W_HOSCIE = ("jarvo-hq", "jarvo-wiedza")             # zakładki panelu: włączone w config hosta (plugins.enabled)
WE_WSZYSTKICH = ("jarvo-wiedza",)                   # dostawca pamięci każdego profilu
TYLKO_PANEL = ("jarvo-hq",)                         # wtyczka samego panelu: bez dowiązań w profilach i restartu bramy
PANEL = ("jarvo-hq", "jarvo-wiedza")                # ich odcisk decyduje o restarcie panelu
RUTYNY = ("jarvo-patrol", "jarvo-daily-brief", "jarvo-weekly-review", "jarvo-knowledge-freshness")
ZNACZNIK_PANELU = ".odcisk-panelu"
PLIKI_PROFILU = ("config.yaml", "SOUL.md", "profile.yaml", "mcp.json", ".env")
KLUCZ_API = re.compile(r"^API_SERVER_KEY=.{16,}", re.M)
LINIA_ENV = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
SEKRET = re.compile(r"TOKEN|KEY|SECRET|PASS|HASLO|KLUCZ|AUTH|COOKIE", re.I)   # jak jarvo/srodowisko.py
BEZ_HERMESA = {"HERMES_HOME", "PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "VIRTUAL_ENV", "HERMES_YOLO_MODE"}
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CZAS_INSTALACJI = re.compile(r"^installed_at:.*$", re.M)   # Hermes stawia go przy każdym install i update
BLOKADA_STARA_S = 2 * 3600                          # jak wiedza/kompilacja.py: starsza blokada to resztka po awarii
CZAS_HERMESA = 900                                  # s na jedno polecenie Hermesa (profile update kopiuje skille)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class BladFloty(RuntimeError):
    """Krok instalacji floty się nie udał (komunikat po polsku, bez sekretów)."""


# ---------------------------------------------------------------- log z maskowaniem sekretów

def _na_ekran(strumien) -> Callable[[str], None]:
    """Domyślne `wypisz`: linia od razu do strumienia złapanego przy starcie (sys.stdout skryptów pomocniczych jest
    w tym czasie przekierowany do logu, więc print() do bieżącego sys.stdout zapętliłby się)."""
    def wypisz(tekst: str) -> None:
        print(tekst, file=strumien, flush=True)
    return wypisz


class Log:
    """Wypisuje linie przez `wypisz`, zamieniając znane sekrety (wartości z plików .env) na ***."""

    def __init__(self, wypisz: Callable[[str], None] | None = None):
        self._wypisz = wypisz or _na_ekran(sys.stdout)
        self.sekrety: set[str] = set()

    def maskuj(self, tekst: str) -> str:
        for s in sorted(self.sekrety, key=len, reverse=True):
            tekst = tekst.replace(s, "***")
        return tekst

    def __call__(self, tekst: str) -> None:
        self._wypisz(self.maskuj(tekst))

    def z_pliku(self, plik: Path) -> None:
        """Wartości zmiennych o nazwach sekretów (KEY, TOKEN, …) z pliku .env idą na listę maskowanych."""
        for nazwa, wartosc in czytaj_env(plik).items():
            if SEKRET.search(nazwa) and len(wartosc) >= 8:
                self.sekrety.add(wartosc)


class _DoLogu(io.TextIOBase):
    """Strumień dla print() skryptów pomocniczych: każda pełna linia trafia do logu z wcięciem."""

    def __init__(self, log: Callable[[str], None], wciecie: str):
        super().__init__()
        self._log, self._wciecie, self._bufor = log, wciecie, ""

    def writable(self) -> bool:
        return True

    def write(self, s: str) -> int:
        self._bufor += s
        while "\n" in self._bufor:
            linia, self._bufor = self._bufor.split("\n", 1)
            if linia.strip():
                self._log(self._wciecie + linia.rstrip())
        return len(s)

    def flush(self) -> None:
        if self._bufor.strip():
            self._log(self._wciecie + self._bufor.rstrip())
        self._bufor = ""


# ---------------------------------------------------------------- pliki: spis treści, kopie, dowiązania

def czytaj_env(plik: Path) -> dict[str, str]:
    """{nazwa: wartość} z .env (bez komentarzy; cudzysłowy zdjęte, komentarz po wartości bez cudzysłowu też);
    brak pliku = {}."""
    try:
        tekst = Path(plik).read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    wynik = {}
    for linia in tekst.splitlines():
        m = LINIA_ENV.match(linia)
        if not m or linia.lstrip().startswith("#"):
            continue
        wartosc = m.group(2).strip()
        if len(wartosc) >= 2 and wartosc[0] == wartosc[-1] and wartosc[0] in "'\"":
            wartosc = wartosc[1:-1]
        elif " #" in wartosc:
            wartosc = wartosc.split(" #", 1)[0].rstrip()
        wynik[m.group(1)] = wartosc
    return wynik


def _skrot(plik: Path) -> str:
    h = hashlib.sha256()
    with open(plik, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()


def _junction(p: Path) -> bool:
    if not WINDOWS:
        return False
    sprawdz = getattr(os.path, "isjunction", None)            # Python 3.12+
    if sprawdz is not None:
        return sprawdz(p)
    try:
        return os.lstat(p).st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
    except (OSError, AttributeError):
        return False


def _link(p: Path) -> bool:
    """Symlink albo junction: na Windows os.walk i is_dir() wchodzą w junction jak w zwykły katalog."""
    return Path(p).is_symlink() or _junction(Path(p))


def _klucz(sciezka: str | os.PathLike) -> str:
    tekst = str(sciezka)
    if tekst.startswith("\\\\?\\"):                         # readlink junction na Windows: przedrostek \\?\
        tekst = tekst[4:]
    return os.path.normcase(os.path.abspath(tekst))


def _cel_linku(p: Path) -> str:
    return _klucz(os.path.join(os.path.dirname(p), os.readlink(p)))


def spis(korzen: Path, pomin: tuple[str, ...] = ("__pycache__",)) -> dict[str, str]:
    """Treść drzewa: {ścieżka względna z "/": "f:<sha256>" albo "l:<cel dowiązania>"}. W dowiązania i junction nie
    wchodzimy, katalogi z `pomin` (np. __pycache__) pomijamy. Pusty słownik = brak."""
    korzen = Path(korzen)
    if _link(korzen):
        return {"": "l:" + _cel_linku(korzen)}
    if korzen.is_file():
        return {"": "f:" + _skrot(korzen)}
    wynik: dict[str, str] = {}

    def idz(katalog: Path, rel: str) -> None:
        try:
            wpisy = sorted(os.scandir(katalog), key=lambda e: e.name)
        except (FileNotFoundError, NotADirectoryError):
            return
        for e in wpisy:
            p = Path(e.path)
            r = rel + e.name
            if e.is_symlink() or _junction(p):
                wynik[r] = "l:" + _cel_linku(p)
            elif e.is_dir(follow_symlinks=False):
                if e.name not in pomin:
                    idz(p, r + "/")
            elif e.is_file(follow_symlinks=False):
                wynik[r] = "f:" + _skrot(p)

    if korzen.is_dir():
        idz(korzen, "")
    return wynik


def _odcisk(dane: object) -> str:
    return hashlib.sha256(json.dumps(dane, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def odcisk_wtyczek_panelu(dane: Path) -> str:
    """Odcisk jarvo-hq i jarvo-wiedza w <dane>/plugins, ten sam wzór co w install-fleet.sh: sha256 z linii
    `sha256sum` (posortowane ścieżki od <dane>/plugins, bez __pycache__), pierwsze 16 znaków. Brak wtyczek = ""."""
    linie = []
    for nazwa in PANEL:
        d = Path(dane) / "plugins" / nazwa
        if d.is_dir() and not _link(d):
            linie += [(f"{nazwa}/{rel}", w[2:]) for rel, w in spis(d).items() if w.startswith("f:")]
    if not linie:
        return ""
    return hashlib.sha256("".join(f"{h}  {p}\n" for p, h in sorted(linie)).encode("utf-8")).hexdigest()[:16]


def usun(p: Path) -> None:
    """Usuwa plik, katalog albo samo dowiązanie (junction: bez wchodzenia do celu); pliki tylko do odczytu też."""
    p = Path(p)
    if _link(p):
        try:
            os.unlink(p)
        except OSError:
            os.rmdir(p)                                       # junction na starszym Pythonie
    elif p.is_dir():
        def odblokuj(funkcja, sciezka, _blad):
            os.chmod(sciezka, stat.S_IWRITE)
            funkcja(sciezka)
        if sys.version_info >= (3, 12):
            shutil.rmtree(p, onexc=odblokuj)
        else:                                                 # pragma: no cover - Python 3.11
            shutil.rmtree(p, onerror=odblokuj)
    elif p.exists():
        p.unlink()


def _zmien_nazwe(z: Path, do: Path, proby: int = 40) -> None:
    """os.replace z ponawianiem: na Windows plik w katalogu chwilowo trzyma antywirus, indeksowanie albo panel."""
    for i in range(proby):
        try:
            os.replace(z, do)
            return
        except PermissionError as e:
            if not WINDOWS or i == proby - 1:
                raise BladFloty(f"Nie mogę zmienić nazwy {z} na {do.name}: {e}. Zatrzymaj panel i bramę (jarvo down) "
                                "i uruchom instalację floty jeszcze raz.") from None
            time.sleep(0.25)


def podmien_katalog(zrodlo: Path, cel: Path) -> None:
    """Kopia `zrodlo` w miejsce `cel` z atomową podmianą: najpierw pełna kopia obok (`.new`), potem dwie zmiany
    nazwy (stary → `.old`, nowy → cel) i sprzątanie. Dowiązania do `cel` (po ścieżce) widzą od razu nową treść."""
    nowy, stary = cel.with_name(cel.name + ".new"), cel.with_name(cel.name + ".old")
    for resztka in (nowy, stary):                             # po przerwanym przebiegu
        if resztka.exists() or _link(resztka):
            usun(resztka)
    shutil.copytree(zrodlo, nowy, ignore=shutil.ignore_patterns("__pycache__"))
    if cel.exists() or _link(cel):
        _zmien_nazwe(cel, stary)
    _zmien_nazwe(nowy, cel)
    with contextlib.suppress(OSError):
        usun(stary)


def _kopiuj_plik(zrodlo: Path, cel: Path) -> bool:
    """Kopia pliku tylko przy innej treści (filecmp bajt po bajcie); True = zapisano."""
    if cel.is_file() and filecmp.cmp(zrodlo, cel, shallow=False):
        return False
    przenosne.zapisz_atomowo(cel, zrodlo.read_bytes())
    return True


def _zapis_yaml_lf(dump: Callable) -> Callable:
    """dump(dane, ścieżka) skryptów pomocniczych (fleetlib.rt_yaml) z LF na każdym systemie i bez zapisu, gdy treść ta
    sama: ruamel i PyYAML piszą tam w trybie tekstowym, więc na Windows dawałyby CRLF, a config.yaml zmieniałby się
    przy każdym przebiegu (Hermes pisze LF)."""
    def zapisz(dane, sciezka) -> None:
        sciezka = Path(sciezka)
        tmp = sciezka.with_name(f".{sciezka.name}.jarvo-yaml")
        try:
            dump(dane, tmp)
            tresc = tmp.read_bytes().replace(b"\r\n", b"\n")
        finally:
            tmp.unlink(missing_ok=True)
        if not (sciezka.is_file() and sciezka.read_bytes() == tresc):
            przenosne.zapisz_atomowo(sciezka, tresc)
    return zapisz


def _zyje(pid: int) -> bool:
    """Czy proces o tym PID-zie jeszcze działa (blokada skarbca bez żywego właściciela to resztka po awarii)."""
    if pid <= 0:
        return False
    if not WINDOWS:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    uchwyt = k32.OpenProcess(0x1000, False, pid)              # PROCESS_QUERY_LIMITED_INFORMATION
    if not uchwyt:
        return ctypes.get_last_error() == 5                   # odmowa dostępu: proces jest, tylko cudzy
    try:
        kod = wintypes.DWORD()
        return bool(k32.GetExitCodeProcess(uchwyt, ctypes.byref(kod))) and kod.value == 259    # STILL_ACTIVE
    finally:
        k32.CloseHandle(uchwyt)


def _bez_sterujacych(x: object, n: int = 120) -> str:
    """Opis z rozmów (praca.json): bez znaków sterujących terminala, najwyżej `n` znaków."""
    return "".join(c for c in str(x) if c.isprintable())[:n]


# ---------------------------------------------------------------- instalacja

class Flota:
    def __init__(self, a: argparse.Namespace, wypisz: Callable[[str], None] | None = None):
        # bezwzględne: dowiązania i junction wtyczek wskazują cel pełną ścieżką
        self.dane = Path(a.dane).absolute()
        self.build = Path(a.build).absolute()
        self.repo = Path(a.repo).absolute()
        self.sekrety = None if a.bez_sekretow else Path(a.sekrety)
        self.narzedzia = Path(a.narzedzia).absolute() if a.narzedzia else self.dane / "jarvo" / "narzedzia"
        self.hermes_python = str(a.hermes_python or sys.executable)
        self.pierwsza, self.wznow, self.natywnie = a.first_run, a.resume_cron, a.natywnie
        self.czekaj_skarbiec = float(a.czekaj_na_skarbiec)
        self.plik_ustawien = Path(a.ustawienia_profili) if getattr(a, "ustawienia_profili", None) else None
        self._ustawienia: dict | None = None
        self.log = Log(wypisz)
        self.jd = self.dane / "jarvo"
        self.agenci: list[str] = []
        self.zmiany: list[dict] = []
        self.ostrzezenia: list[str] = []
        self.wtyczki: dict[str, str] = {}
        self.dowiazania: dict[str, dict[str, str]] = {}
        self.klucze_nowe: list[str] = []
        self.rutyny: dict[str, str] = {}
        self.skarbiec: dict = {}
        self.lint: dict = {}
        self._yaml = None
        self._w_buildzie: dict[str, list[str]] = {}

    # -- pomocnicze
    def krok(self, tekst: str) -> None:
        self.log(f"▶ {tekst}")

    def uwaga(self, tekst: str) -> None:
        self.ostrzezenia.append(self.log.maskuj(tekst))
        self.log(f"  ! {tekst}")

    def zmiana(self, co: str, *, brama: bool = True, panel: bool = False) -> None:
        self.zmiany.append({"co": co, "brama": brama, "panel": panel})

    def profil(self, agent: str) -> Path:
        return self.dane / "profiles" / agent

    @contextlib.contextmanager
    def do_logu(self, wciecie: str = "  ") -> Iterator[None]:
        """print() skryptu pomocniczego idzie linia po linii do logu; sam log pisze wtedy do pierwotnych strumieni
        (także `wypisz` oparte na print), więc nic nie wraca do przekierowania."""
        oryginalne = (sys.stdout, sys.stderr)

        def do_oryginalnych(tekst: str) -> None:
            with contextlib.redirect_stdout(oryginalne[0]), contextlib.redirect_stderr(oryginalne[1]):
                self.log(tekst)

        strumien = _DoLogu(do_oryginalnych, wciecie)
        try:
            with contextlib.redirect_stdout(strumien), contextlib.redirect_stderr(strumien):
                yield
        finally:
            strumien.flush()

    def env_hermesa(self, **dodatki: str) -> dict[str, str]:
        """Środowisko poleceń Hermesa i skryptów: HERMES_HOME = --dane (nigdy katalog prywatnego Hermesa), bez
        PYTHONPATH, PYTHONHOME, cudzego venvu i HERMES_YOLO_MODE, wyjście w UTF-8."""
        env = {k: v for k, v in os.environ.items() if k.upper() not in BEZ_HERMESA}
        env.update({"HERMES_HOME": str(self.dane), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"})
        env.update(dodatki)
        return env

    def uruchom(self, argv: list, *, env: dict | None = None, pokaz: bool = True, czas: float = CZAS_HERMESA,
                wciecie: str = "    ", linie: int | None = 60) -> tuple[int, list[str]]:
        """Program z wyjściem linia po linii do logu (maskowanie sekretów), bez wejścia i bez okna konsoli; po `czas`
        sekundach zabity. Zwraca kod i ostatnie `linie` linii wyjścia (None = całe)."""
        ogon: deque[str] = deque(maxlen=linie)
        try:
            proc = subprocess.Popen([str(x) for x in argv], cwd=str(self.dane), env=env or self.env_hermesa(),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        except OSError as e:
            raise BladFloty(f"Nie uruchomię {Path(str(argv[0])).name}: {e}") from None
        zegar = threading.Timer(czas, proc.kill)
        zegar.start()
        try:
            with proc:
                for surowa in proc.stdout:
                    linia = ANSI.sub("", surowa).rstrip()
                    if not linia.strip():
                        continue
                    ogon.append(linia)
                    if pokaz:
                        self.log(wciecie + linia)
                kod = proc.wait()
        finally:
            zegar.cancel()
        return kod, list(ogon)

    def hermes(self, *argumenty: str, pokaz: bool = True) -> tuple[int, list[str]]:
        """CLI Hermesa Pythonem jego venvu: `python -P -m hermes_cli.main …` (-P: katalog bieżący nie trafia do
        sys.path, więc obcy hermes_cli w <dane> niczego nie podmieni)."""
        return self.uruchom([self.hermes_python, "-P", "-m", "hermes_cli.main", *argumenty], pokaz=pokaz)

    def pomocnik(self, nazwa: str, argv: list[str]) -> int:
        """main(argv) skryptu pomocniczego z scripts/ w tym procesie, z wyjściem w logu. Na czas wywołania jego zapis
        YAML (`dump` z fleetlib.rt_yaml) idzie przez _zapis_yaml_lf; potem moduł wraca do pierwotnego stanu."""
        modul = importlib.import_module(nazwa)
        dump = getattr(modul, "dump", None)
        if dump is not None:
            modul.dump = _zapis_yaml_lf(dump)
        try:
            with self.do_logu():
                return int(modul.main([str(x) for x in argv]) or 0)
        finally:
            if dump is not None:
                modul.dump = dump

    def yaml(self, plik: Path) -> dict:
        try:
            if self._yaml is None:
                import fleetlib
                self._yaml = fleetlib.load_yaml
            dane = self._yaml(plik)
        except FileNotFoundError:
            return {}
        return dane if isinstance(dane, dict) else {}

    def wlaczone(self, config: Path) -> tuple[list[str], list[str]]:
        """(plugins.enabled, plugins.disabled) z config.yaml; plik nieczytelny = puste listy."""
        try:
            wtyczki = self.yaml(config).get("plugins") or {}
        except Exception:                                      # noqa: BLE001 - zepsuty YAML: tak jakby nic nie włączono
            return [], []
        if not isinstance(wtyczki, dict):
            return [], []
        return [str(x) for x in wtyczki.get("enabled") or []], [str(x) for x in wtyczki.get("disabled") or []]

    def w_buildzie(self, agent: str) -> list[str]:
        """plugins.enabled z configu profilu w buildzie (to, co profil dostanie po `profile update --force-config`)."""
        if agent not in self._w_buildzie:
            self._w_buildzie[agent] = self.wlaczone(self.build / "profiles" / agent / "config.yaml")[0]
        return self._w_buildzie[agent]

    def odcisk_profilu(self, home: Path) -> str:
        """Treść, którą czyta brama: pliki dystrybucji, .env, skille (bez zapisków Hermesa .hub, .usage.json),
        wtyczki profilu (dowiązania jako cel) i katalog home. distribution.yaml bez `installed_at`."""
        skille = {k: v for k, v in spis(home / "skills").items() if not k.startswith(".")}
        pliki = {n: spis(home / n) for n in PLIKI_PROFILU}
        try:
            manifest = CZAS_INSTALACJI.sub("", (home / "distribution.yaml").read_text(encoding="utf-8"))
        except OSError:
            manifest = None
        return _odcisk({"pliki": pliki, "manifest": manifest, "skills": skille, "plugins": spis(home / "plugins"),
                        "home": (home / "home").is_dir()})

    def zapisz_env(self, plik: Path, tekst: str) -> None:
        """.env z sekretami: zapis atomowy (plik tymczasowy jest od razu 0600 na POSIX), potem tylko dla właściciela."""
        przenosne.zapisz_atomowo(plik, tekst)
        try:
            przenosne.chron(plik, katalog=False)
        except OSError as e:
            raise BladFloty(f"Nie mogę ograniczyć dostępu do {plik} do właściciela: {e}") from None

    # -- przebieg
    def uruchom_wszystko(self) -> dict:
        self.sprawdz()
        for plik in [self.dane / ".env", *sorted((self.dane / "profiles").glob("*/.env"))]:
            self.log.z_pliku(plik)
        self.migracja()
        self.katalogi()
        self.zasiej_skarbiec()
        self.profil_hosta()
        for agent in self.agenci:
            self.profil_agenta(agent)
        self.klucze_api()
        self.impeccable()
        self.wszystkie_wtyczki()
        self.skorka()
        self.motywy()
        self.wspolne_klucze()
        self.kanban()
        self.wznow_rutyny()
        return self.podsumowanie()

    def sprawdz(self) -> None:
        build_json = self.build / "BUILD.json"
        if not build_json.is_file():
            raise BladFloty(f"Brak {build_json}: najpierw scripts/build.py")
        if self.sekrety is not None and self.sekrety.is_dir():
            try:                                       # os.listdir, nie glob: glob nieczytelny katalog przemilcza
                pliki = [self.sekrety / n for n in sorted(os.listdir(self.sekrety)) if n.endswith(".env")]
            except PermissionError:
                raise BladFloty(f"{self.sekrety} jest nieczytelny dla tego użytkownika. Na hoście: sudo chgrp -R "
                                "10000 /srv/jarvo/secrets && sudo chmod 2750 /srv/jarvo/secrets && sudo chmod 640 "
                                "/srv/jarvo/secrets/*.env") from None
            for f in pliki:
                if not os.access(f, os.R_OK):
                    raise BladFloty(f"{f} nieczytelny (uprawnienia): sudo chgrp 10000 {f} && sudo chmod 640 {f}")
        if os.path.dirname(self.hermes_python) and not Path(self.hermes_python).is_file():
            raise BladFloty(f"Brak Pythona Hermesa {self.hermes_python} (opcja --hermes-python).")
        try:
            dane = json.loads(build_json.read_text(encoding="utf-8"))
            self.agenci = [str(a["agent"]) for a in dane["agents"]]
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise BladFloty(f"{build_json}: nie rozumiem listy agentów ({e}); zbuduj flotę ponownie.") from None
        self.dane.mkdir(parents=True, exist_ok=True)

    def launcher_hermesa(self) -> str:
        """Polecenie `hermes` venvu Hermesa (migrate_jarvo.py przyjmuje jeden program): obok jego Pythona
        (Scripts\\hermes.exe, bin/hermes), a bez niego goła nazwa jak w install-fleet.sh."""
        return shutil.which("hermes", path=str(Path(self.hermes_python).parent)) or "hermes"

    def migracja(self) -> None:
        """Dane i profile sprzed zmiany nazwy (TARS → Jarvo); sesje i pamięć przechodzą z profilem."""
        kod, linie = self.uruchom([sys.executable, SKRYPTY / "migrate_jarvo.py", "container", "--data", self.dane,
                                   "--hermes", self.launcher_hermesa()], wciecie="  ")
        if kod:
            self.uwaga("migracja Jarvo z ostrzeżeniami (patrz wyżej)")
        elif linie:
            self.zmiana("migracja TARS → Jarvo")

    def katalogi(self) -> None:
        self.krok("Katalogi floty")
        for d in ("missions", "state", "knowledge/brands", "knowledge/user", *(f"workspaces/{a}" for a in self.agenci)):
            (self.jd / d).mkdir(parents=True, exist_ok=True)
        szablony = self.build / "profiles" / ORKIESTRATOR / "skills" / "fleet"
        for cel, wzor in ((self.jd / "missions" / "INDEX.md",
                           szablony / "mission-ledger" / "references" / "INDEX.template.md"),
                          (self.jd / "knowledge" / "user" / "USER.md",
                           szablony / "onboarding-interview" / "references" / "USER.template.md")):
            if not cel.exists():
                if not wzor.is_file():
                    raise BladFloty(f"Brak szablonu {wzor} w buildzie.")
                _kopiuj_plik(wzor, cel)
                self.zmiana(f"szablon {cel.name}", brama=False)
        wzor = self.repo / "knowledge" / "brands" / "_szablon"
        cel = self.jd / "knowledge" / "brands" / "_szablon"
        if wzor.is_dir() and spis(wzor) != spis(cel):
            podmien_katalog(wzor, cel)
            self.zmiana("szablon marki", brama=False)

    @contextlib.contextmanager
    def blokada_skarbca(self) -> Iterator[bool]:
        """Blokada kompilacji skarbca (state/wiedza.lock: PID i czas, jak wiedza/kompilacja.py). Czeka do
        --czekaj-na-skarbiec s, aż kompilacja skończy; blokada bez żywego procesu albo starsza niż 2 h to resztka."""
        plik = self.jd / "state" / "wiedza.lock"
        koniec = time.monotonic() + self.czekaj_skarbiec
        ostatni = 0.0
        while True:
            try:
                tresc = plik.read_text(encoding="utf-8").split()
                wiek = time.time() - plik.stat().st_mtime
            except (OSError, ValueError):
                break
            pid = int(tresc[0]) if tresc and tresc[0].isdigit() else 0
            if wiek >= BLOKADA_STARA_S or not _zyje(pid):
                break
            if time.monotonic() >= koniec:
                yield False
                return
            if time.monotonic() - ostatni >= 30:
                self.log("  czekam, aż skończy się kompilacja skarbca (state/wiedza.lock)…")
                ostatni = time.monotonic()
            time.sleep(2)
        moja = f"{os.getpid()} {int(time.time())}\n"
        plik.parent.mkdir(parents=True, exist_ok=True)
        plik.write_text(moja, encoding="utf-8", newline="\n")
        try:
            yield True
        finally:
            with contextlib.suppress(OSError):
                if plik.read_text(encoding="utf-8") == moja:
                    plik.unlink()

    def zasiej_skarbiec(self) -> None:
        """Skarbiec wiedzy (docs/WIEDZA.md): huby agentów z buildu, SCHEMA, INDEX, docs repo jako źródła, indeks i punkt
        zapisu git; 0 tokenów. Po zasiewie lint informacyjny (błędy nie zatrzymują instalacji)."""
        self.krok("Skarbiec wiedzy")
        wiedza = self.repo / "wiedza" / "wiedza.py"
        baza = [sys.executable, wiedza, "--skarbiec", self.jd / "knowledge", "--stan", self.jd / "state"]
        with self.blokada_skarbca() as wzieta:
            if not wzieta:
                self.skarbiec = {"zasiany": False, "powod": "trwa kompilacja skarbca (state/wiedza.lock)"}
                self.uwaga("kompilacja skarbca trwa dłużej niż limit: zasiew pominięty, zrobi go następne wdrożenie")
                return
            kod, ogon = self.uruchom([*baza, "zasiej", "--fleet", self.build / "wiedza" / "fleet.json",
                                      "--docs", self.repo / "docs", "--repo", self.build / "wiedza" / "repo"],
                                     wciecie="  ", czas=1800)
            if kod:
                raise BladFloty(f"zasiew skarbca nie przeszedł (kod {kod}): " + " / ".join(ogon[-3:]))
            self.skarbiec = {"zasiany": True,
                             "wynik": self.log.maskuj(next((x.strip() for x in reversed(ogon) if "zasiew" in x), ""))}
            kod, wyjscie = self.uruchom([*baza, "lint", "--json"], pokaz=False, czas=900, linie=None)
        tekst = "\n".join(wyjscie)
        try:
            raport = json.loads(tekst[tekst.index("{"):]) if not kod and "{" in tekst else {}
        except ValueError:
            raport = {}
        if not raport:
            self.uwaga(f"lint skarbca nie odpowiedział (kod {kod})")
            return
        self.lint = {"notatek": raport.get("notatek", 0), "bledy": len(raport.get("bledy") or []),
                     "ostrzezenia": len(raport.get("ostrzezenia") or []),
                     "informacje": len(raport.get("informacje") or [])}
        self.log(f"  lint skarbca: {self.lint['notatek']} notatek · błędy: {self.lint['bledy']} · ostrzeżenia: "
                 f"{self.lint['ostrzezenia']} · informacje: {self.lint['informacje']} (LINT.md)")
        for b in (raport.get("bledy") or [])[:10]:
            self.log(f"    ✗ {_bez_sterujacych(b, 200)}")

    def profil_hosta(self) -> None:
        self.krok("Profil hosta")
        pliki = [self.dane / n for n in ("config.yaml", "SOUL.md", ".env")]
        przed = {str(p): spis(p) for p in pliki}
        self.pomocnik("merge_host_config", [self.build / "host" / "config.yaml", self.dane / "config.yaml",
                                            *(["--force-model"] if self.pierwsza else [])])
        _kopiuj_plik(self.build / "host" / "SOUL.md", self.dane / "SOUL.md")
        if self.sekrety is not None and (self.sekrety / "host.env").is_file():
            self.log.z_pliku(self.sekrety / "host.env")
            self.pomocnik("merge_env", [self.sekrety / "host.env", self.dane / ".env"])
        if {str(p): spis(p) for p in pliki} != przed:
            self.zmiana("profil hosta")

    def ustaw_zrodlo(self, manifest: Path, zrodlo: Path) -> None:
        """`source:` w distribution.yaml = bieżący build (po migracji TARS → Jarvo zostawała stara ścieżka); YAML
        w pojedynczym cudzysłowie, ścieżka z „/”. Zgodne źródło = bez zapisu (Hermes i tak przepisze manifest)."""
        tekst = manifest.read_text(encoding="utf-8")
        m = re.search(r"^source:[ \t]*(.*?)[ \t]*$", tekst, re.M)
        if m:
            obecne = m.group(1)
            if len(obecne) >= 2 and obecne[0] == obecne[-1] and obecne[0] in "'\"":
                obecne = obecne[1:-1].replace("''", "'") if obecne[0] == "'" else obecne[1:-1]
            if obecne and _klucz(obecne) == _klucz(zrodlo):
                return
        linia = "source: '" + zrodlo.as_posix().replace("'", "''") + "'"
        nowy = tekst[:m.start()] + linia + tekst[m.end():] if m else tekst.rstrip("\n") + "\n" + linia + "\n"
        przenosne.zapisz_atomowo(manifest, nowy)

    def profil_agenta(self, agent: str) -> None:
        src = self.build / "profiles" / agent
        home = self.profil(agent)
        przed = self.odcisk_profilu(home)
        if (home / "distribution.yaml").is_file():
            self.krok(f"Aktualizacja profilu {agent}")
            self.pomocnik("profile_model", ["snapshot", home])
            self.ustaw_zrodlo(home / "distribution.yaml", src)
            kod, _ = self.hermes("-p", "default", "profile", "update", agent, "--force-config", "--yes")
            if kod:
                raise BladFloty(f"hermes profile update {agent}: kod {kod} (wyjście wyżej)")
        else:
            self.krok(f"Instalacja profilu {agent}")
            dodatki = [] if self.natywnie else ["--alias"]
            if home.is_dir():
                # np. katalog założony przez `hermes -p <agent> config set` przed flotą: --force zostawia dane profilu
                self.log(f"  ! {home} nie ma distribution.yaml: instaluję z --force (sesje, pamięć i .env zostają)")
                dodatki.append("--force")
            kod, _ = self.hermes("-p", "default", "profile", "install", str(src), "--yes", *dodatki)
            if kod:
                raise BladFloty(f"hermes profile install {agent}: kod {kod} (wyjście wyżej)")
        self.pomocnik("profile_model", ["restore", home])
        # skille floty i zewnętrzne, których nie ma już w buildzie (utworzone przez agenta zostają)
        self.pomocnik("prune_skills", [src / "skills", home / "skills"])
        if self.sekrety is not None:
            plik = self.sekrety / f"{agent}.env"
            if plik.is_file():
                self.log.z_pliku(plik)
                self.pomocnik("merge_env", [plik, home / ".env"])
            else:
                self.log(f"  ! brak {plik} (agent nie ma klucza OpenRouter)")
        if self.natywnie:
            (home / "home").mkdir(parents=True, exist_ok=True)   # terminal.home_mode: profile (H24)
        self.ustaw_klucze_profilu(agent, home / "config.yaml")
        if self.odcisk_profilu(home) != przed:
            self.zmiana(f"profil {agent}")

    def ustawienia_profili(self) -> dict:
        """--ustawienia-profili: {"wszystkie": {klucz: wartość}, "profile": {agent: {klucz: wartość}}}."""
        if self._ustawienia is None:
            self._ustawienia = {}
            if self.plik_ustawien is not None:
                try:
                    dane = json.loads(self.plik_ustawien.read_text(encoding="utf-8-sig"))
                except (OSError, ValueError) as e:
                    raise BladFloty(f"{self.plik_ustawien}: nie czytam ustawień profili ({e})") from None
                self._ustawienia = dane if isinstance(dane, dict) else {}
        return self._ustawienia

    def ustaw_klucze_profilu(self, agent: str, config: Path) -> None:
        """Klucze z --ustawienia-profili w config.yaml profilu (po `profile update --force-config`); zapis tylko
        przy innej wartości, z LF (ruamel zachowuje resztę pliku)."""
        u = self.ustawienia_profili()
        klucze = {**(u.get("wszystkie") or {}), **((u.get("profile") or {}).get(agent) or {})}
        if not klucze or not config.is_file():
            return
        import fleetlib
        load, dump = fleetlib.rt_yaml()
        cfg = load(config)
        if cfg is None:
            cfg = {}
        zmiana = False
        for klucz, wartosc in sorted(klucze.items()):
            *sciezka, ostatni = str(klucz).split(".")
            wezel = cfg
            for czesc in sciezka:
                if not isinstance(wezel.get(czesc), dict):
                    wezel[czesc] = {}
                wezel = wezel[czesc]
            obecna = wezel.get(ostatni)
            if json.dumps(obecna, sort_keys=True, default=str) != json.dumps(wartosc, sort_keys=True):
                wezel[ostatni] = wartosc
                zmiana = True
        if zmiana:
            _zapis_yaml_lf(dump)(cfg, config)
            self.log(f"  ustawienia instalacji w profilu {agent}: {', '.join(sorted(klucze))}")

    def klucze_api(self) -> None:
        """API_SERVER_KEY: multipleksowana brama obsługuje /p/<profil>/ tylko z własnym kluczem profilu (z niego
        korzysta Jarvo HQ), a serwer API hosta bez klucza nie wstaje. Brakujące generujemy, istniejących nie ruszamy;
        klucz hosta z otoczenia procesu (operator kontenera) ma pierwszeństwo, jak w obrazie Hermesa."""
        self.krok("Klucze API")
        for nazwa, home in [("host", self.dane), *((a, self.profil(a)) for a in self.agenci)]:
            plik = home / ".env"
            try:
                tekst = plik.read_text(encoding="utf-8-sig")
            except FileNotFoundError:
                tekst = ""
            if KLUCZ_API.search(tekst) or (nazwa == "host" and os.environ.get("API_SERVER_KEY")):
                continue
            klucz = secrets.token_hex(32)
            self.log.sekrety.add(klucz)
            if tekst and not tekst.endswith("\n"):
                tekst += "\n"
            home.mkdir(parents=True, exist_ok=True)
            self.zapisz_env(plik, tekst + f"API_SERVER_KEY={klucz}\n")
            self.klucze_nowe.append(nazwa)
            self.log(f"  + API_SERVER_KEY dla {nazwa}")
            self.zmiana(f"klucz API {nazwa}")

    def ustaw_w_env(self, plik: Path, nazwa: str, wartosc: str) -> bool:
        """Zmienna w .env profilu (dopisana albo poprawiona); True = zmieniono plik."""
        try:
            tekst = plik.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            tekst = ""
        linia = f"{nazwa}={wartosc}"
        wzor = re.compile(rf"^{re.escape(nazwa)}=.*$", re.M)
        if wzor.search(tekst):
            nowy = wzor.sub(lambda _m: linia, tekst, count=1)
        else:
            nowy = (tekst + ("\n" if tekst and not tekst.endswith("\n") else "")) + linia + "\n"
        if nowy == tekst:
            return False
        self.zapisz_env(plik, nowy)
        return True

    def impeccable(self) -> None:
        """impeccable (detektor „znaków AI” w projektach): program w wersji z VERSION skilla, raz, do trwałego katalogu
        narzędzi floty. Ścieżka w .env idzie za instalacją (kontener: <dane>/jarvo/narzedzia/impeccable). Pobiera go
        launcher `sh` skilla; na Windows zrobi to agent przy pierwszym użyciu (Git Bash)."""
        dom = self.narzedzia / "impeccable"
        powiedziane = False
        for agent in self.agenci:
            home = self.profil(agent)
            imp = home / "skills" / "design" / "impeccable" / "scripts" / "impeccable"
            if not imp.is_file():
                continue
            if self.ustaw_w_env(home / ".env", "IMPECCABLE_HOME", dom.as_posix()):
                self.zmiana(f"IMPECCABLE_HOME dla {agent}")
            dom.mkdir(parents=True, exist_ok=True)
            sh = None if WINDOWS else shutil.which("sh")
            if sh is None:
                if not powiedziane:
                    self.log("  ! impeccable: program pobierze się przy pierwszym użyciu (na Windows w Git Bash "
                             "agenta)")
                    powiedziane = True
                continue
            kod, _ = self.uruchom([sh, imp, "--version"], env=self.env_hermesa(IMPECCABLE_HOME=str(dom)),
                                  pokaz=False, czas=300)
            self.log(f"  ✓ impeccable ({agent})" if kod == 0 else
                     "  ! impeccable: nie pobrano programu (sieć?); pobierze się przy pierwszym użyciu")

    # -- wtyczki
    def wtyczka(self, nazwa: str) -> str:
        """Kopia wtyczki z buildu do <dane>/plugins; ta sama treść (bez __pycache__) = stara kopia zostaje."""
        src, dst = self.build / "plugins" / nazwa, self.dane / "plugins" / nazwa
        dst.parent.mkdir(parents=True, exist_ok=True)
        for resztka in (dst.with_name(dst.name + ".new"), dst.with_name(dst.name + ".old")):
            if resztka.exists() or _link(resztka):         # po przerwanej podmianie: Hermes wziąłby ją za drugą kopię
                usun(resztka)
        if dst.is_dir() and not _link(dst) and spis(src) == spis(dst):
            self.log(f"  = {nazwa} bez zmian")
            return "bez zmian"
        stan = "podmieniona" if dst.exists() or _link(dst) else "nowa"
        podmien_katalog(src, dst)
        self.log(f"  ✓ {nazwa}: {stan}")
        return stan

    def dowiaz(self, nazwa: str, agent: str) -> str:
        """<profil>/plugins/<nazwa> → <dane>/plugins/<nazwa>: POSIX symlink (jak `ln -sfn`), Windows junction (bez
        admina i trybu dewelopera), a gdy system plików ich nie zna, kopia. Zwraca rodzaj; zmiana idzie do zmian."""
        cel = self.dane / "plugins" / nazwa
        link = self.profil(agent) / "plugins" / nazwa
        link.parent.mkdir(parents=True, exist_ok=True)
        rodzaj = "junction" if WINDOWS else "symlink"
        tmp, stary = link.with_name(f".{nazwa}.jarvo-link"), link.with_name(f".{nazwa}.jarvo-old")
        for resztka in (tmp, stary, link.with_name(nazwa + ".new"), link.with_name(nazwa + ".old")):
            if resztka.exists() or _link(resztka):           # po przerwanym przebiegu (Hermes wziąłby je za wtyczki)
                usun(resztka)
        if _link(link) and _cel_linku(link) == _klucz(cel):
            return rodzaj
        try:
            if WINDOWS:
                import _winapi
                _winapi.CreateJunction(str(cel), str(tmp))
            else:
                os.symlink(cel, tmp, target_is_directory=True)
        except OSError as e:
            if link.is_dir() and not _link(link) and spis(link) == spis(cel):
                return "kopia"
            self.log(f"  ! {agent}: dowiązanie {nazwa} niemożliwe ({e}); kopia")
            podmien_katalog(cel, link)
            self.zmiana(f"wtyczka {nazwa} w {agent} (kopia)")
            return "kopia"
        if link.exists() or _link(link):
            if WINDOWS or (link.is_dir() and not _link(link)):
                _zmien_nazwe(link, stary)
                _zmien_nazwe(tmp, link)
                usun(stary)
            else:
                os.replace(tmp, link)                     # symlink na symlink: jak ln -sfn, bez chwili bez wtyczki
        else:
            _zmien_nazwe(tmp, link)
        self.zmiana(f"wtyczka {nazwa} w {agent}")
        return rodzaj

    def odwiaz(self, nazwa: str, agent: str) -> None:
        link = self.profil(agent) / "plugins" / nazwa
        if link.exists() or _link(link):
            usun(link)
            self.zmiana(f"wtyczka {nazwa} poza {agent}")

    def wlacz_w_hoscie(self, nazwa: str) -> None:
        """Wtyczki użytkownika muszą być jawnie włączone (zabezpieczenie Hermesa): `hermes plugins enable`, a gdy
        Hermes jej nie zna (wtyczka samego panelu), enable_plugin.py. Już włączona = bez wywołań."""
        config = self.dane / "config.yaml"
        wlaczone, wylaczone = self.wlaczone(config)
        if nazwa in wlaczone and nazwa not in wylaczone:
            return
        kod, _ = self.hermes("-p", "default", "plugins", "enable", nazwa, pokaz=False)
        wlaczone, wylaczone = self.wlaczone(config)
        if kod or nazwa not in wlaczone or nazwa in wylaczone:
            self.pomocnik("enable_plugin", [config, nazwa])
        else:
            self.log(f"  plugin {nazwa}: włączony w {config}")
        self.zmiana(f"wtyczka {nazwa} włączona", brama=nazwa not in TYLKO_PANEL, panel=nazwa in PANEL)

    def wszystkie_wtyczki(self) -> None:
        host_build, _ = self.wlaczone(self.build / "host" / "config.yaml")
        for nazwa in WTYCZKI:
            if not (self.build / "plugins" / nazwa).is_dir():
                continue
            self.krok(f"Wtyczka {nazwa}")
            stan = self.wtyczka(nazwa)
            self.wtyczki[nazwa] = stan
            if stan != "bez zmian":
                self.zmiana(f"wtyczka {nazwa}", brama=nazwa not in TYLKO_PANEL)
            if nazwa not in TYLKO_PANEL:
                for agent in self.agenci:
                    if nazwa in WE_WSZYSTKICH or nazwa in self.w_buildzie(agent):
                        self.dowiazania.setdefault(agent, {})[nazwa] = self.dowiaz(nazwa, agent)
                    else:
                        self.odwiaz(nazwa, agent)
            if nazwa in W_HOSCIE or nazwa in host_build:
                self.wlacz_w_hoscie(nazwa)

    # -- reszta
    def skorka(self) -> None:
        """Branding terminala: skórka „jarvo” dla hosta i każdego profilu (display.skin w config.yaml)."""
        wzor = self.repo / "branding" / "skin-jarvo.yaml"
        if not wzor.is_file():
            return
        # tylko prawdziwe profile (z config.yaml): katalog po usuniętym profilu, w którym pracownik kanbana zostawił
        # logi, nie dostaje skórki (inaczej każdy kolejny przebieg zgłaszał zmianę, CI natywnie)
        domy = [self.dane, *sorted(p for p in (self.dane / "profiles").glob("*")
                                   if p.is_dir() and (p / "config.yaml").is_file())]
        if any([_kopiuj_plik(wzor, home / "skins" / "jarvo.yaml") for home in domy]):
            self.zmiana("skórka terminala", brama=False)

    def motywy(self) -> None:
        """Motywy panelu „Fosfor” (jeden kolor → cały wygląd; lista w branding/fosfor/palettes.yaml)."""
        if not (self.repo / "branding" / "fosfor" / "palettes.yaml").is_file():
            return
        przed = (spis(self.dane / "dashboard-themes"), spis(self.dane / "config.yaml"))
        self.pomocnik("install_themes", [self.repo, self.dane])
        if (spis(self.dane / "dashboard-themes"), spis(self.dane / "config.yaml")) != przed:
            self.zmiana("motywy panelu", brama=False)

    def wspolne_klucze(self) -> None:
        """Klucze dostawców i narzędzi z głównego .env do każdego agenta (na żywo pilnuje ich Jarvo HQ)."""
        pliki = sorted((self.dane / "profiles").glob("*/.env"))
        przed = {str(p): spis(p) for p in pliki}
        self.pomocnik("share_keys", [self.dane])
        if {str(p): spis(p) for p in sorted((self.dane / "profiles").glob("*/.env"))} != przed:
            self.zmiana("wspólne klucze")

    def kanban(self) -> None:
        if self.pierwsza or not (self.dane / "kanban.db").exists():
            self.krok("Tablica kanban")
            istniala = (self.dane / "kanban.db").exists()
            kod, _ = self.hermes("-p", "default", "kanban", "init")
            if kod:
                raise BladFloty(f"hermes kanban init: kod {kod} (wyjście wyżej)")
            if not istniala:
                self.zmiana("tablica kanban")

    def wznow_rutyny(self) -> None:
        if not self.wznow:
            return
        self.krok("Wznawiam rutyny Jarva")
        for job in RUTYNY:
            kod, _ = self.hermes("-p", ORKIESTRATOR, "cron", "resume", job)
            self.rutyny[job] = "wznowiona" if kod == 0 else "błąd"
            if kod:
                self.uwaga(f"nie udało się wznowić {job}")

    def praca_w_toku(self) -> list[str]:
        """Praca agentów w toku (praca.json silnika rozmów HQ, docs/HQ.md „Rozmowy”): restart bramy przerwie te tury,
        a aplikacja pokaże je jako „Praca przerwana: możesz ponowić”. Tylko ostrzeżenie."""
        try:
            p = json.loads((self.jd / "state" / "praca.json").read_text(encoding="utf-8"))
            if int(p.get("aktywne") or 0) <= 0 or time.time() - float(p.get("at") or 0) >= 120:
                return []
        except (OSError, ValueError, TypeError, AttributeError):
            return []
        return [self.log.maskuj(_bez_sterujacych(x)) for x in (p["aktywne"], *(p.get("opis") or [])[:12])]

    def podsumowanie(self) -> dict:
        odcisk = odcisk_wtyczek_panelu(self.dane)
        try:
            ostatni = (self.dane / "plugins" / ZNACZNIK_PANELU).read_text(encoding="utf-8").strip()
        except OSError:
            ostatni = ""
        restart_bramy = any(z["brama"] for z in self.zmiany)
        restart_panelu = bool(odcisk and odcisk != ostatni) or any(z["panel"] for z in self.zmiany)
        praca = self.praca_w_toku() if restart_bramy else []
        if praca:
            self.uwaga(f"trwa praca agentów ({praca[0]}); restart bramy ją przerwie (w aplikacji: Ponów)")
            for linia in praca[1:]:
                self.log(f"    - {linia}")
        powody = [z["co"] for z in self.zmiany if z["brama"]]
        if restart_bramy or restart_panelu:
            co = " i ".join(x for x, tak in (("brama", restart_bramy), ("panel", restart_panelu)) if tak)
            dopisek = f"; zmiany: {', '.join(powody[:8])}{'…' if len(powody) > 8 else ''}" if powody else ""
            self.log(f"↻ potrzebny restart: {co} (robi go nadzorca){dopisek}")
        else:
            self.log("= restart niepotrzebny: brama i panel mają aktualną flotę")
        self.log(f"✅ Flota zainstalowana: {' '.join(self.agenci)}")
        return {"wersja": 1, "agenci": self.agenci, "wtyczki": self.wtyczki, "dowiazania": self.dowiazania,
                "zmiany": [z["co"] for z in self.zmiany], "restart_bramy": restart_bramy,
                "restart_panelu": restart_panelu, "restart": restart_bramy or restart_panelu,
                "odcisk_panelu": odcisk, "praca_w_toku": praca, "klucze_nowe": self.klucze_nowe,
                "rutyny": self.rutyny, "skarbiec": self.skarbiec, "lint": self.lint,
                "ostrzezenia": self.ostrzezenia}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Instalacja albo aktualizacja floty Jarva z buildu "
                                             "(docs/NATYWNIE.md S07).")
    ap.add_argument("--dane", default="/opt/data", help="HERMES_HOME instalacji (kontener: /opt/data)")
    ap.add_argument("--build", default="/opt/jarvo/build", help="wynik scripts/build.py (kontener: /opt/jarvo/build)")
    ap.add_argument("--repo", default=str(SKRYPTY.parent), help="kod Jarva (domyślnie repo tego skryptu)")
    ap.add_argument("--sekrety", default="/opt/jarvo/secrets", help="host.env i <agent>.env (kontener)")
    ap.add_argument("--bez-sekretow", action="store_true", help="bez katalogu sekretów (natywnie są w .env w <dane>)")
    ap.add_argument("--narzedzia", default=None,
                    help="narzędzia floty instalowane w locie (kontener <dane>/jarvo/narzedzia, natywnie "
                         "<program>/narzedzia-floty)")
    ap.add_argument("--hermes-python", default=None,
                    help="Python venvu Hermesa (domyślnie ten, który uruchamia skrypt)")
    ap.add_argument("--natywnie", action="store_true",
                    help="układ natywny: profile bez --alias (H14), katalog <profil>/home (H24)")
    ap.add_argument("--first-run", action="store_true",
                    help="pierwsza instalacja: model floty w hoście, tablica kanban")
    ap.add_argument("--resume-cron", action="store_true", help="wznawia rutyny Jarva (po teście Telegrama)")
    ap.add_argument("--no-restart", action="store_true",
                    help="zgodność z install-fleet.sh: ten skrypt nigdy nie restartuje (mówi, czy trzeba)")
    ap.add_argument("--podsumowanie", default=None, help="plik JSON z wynikiem (agenci, wtyczki, czy restart)")
    ap.add_argument("--czekaj-na-skarbiec", type=float, default=300.0,
                    help="ile sekund czekać na koniec kompilacji skarbca przed zasiewem")
    ap.add_argument("--ustawienia-profili", default=None,
                    help="JSON z kluczami configu profili zależnymi od instalacji (natywnie: jarvo/flota.py)")
    return ap


def main(argv: list[str] | None = None, wypisz: Callable[[str], None] | None = None) -> int:
    a = parser().parse_args(argv)
    flota = Flota(a, wypisz)
    try:
        wynik = flota.uruchom_wszystko()
    except BladFloty as e:
        flota.log(f"✗ {e}")
        return 1
    except Exception:                                  # noqa: BLE001 - nieoczekiwany błąd: ślad do logu (maskowany)
        for linia in traceback.format_exc().splitlines():
            flota.log(linia)
        flota.log("✗ instalacja floty przerwana nieoczekiwanym błędem (ślad wyżej)")
        return 1
    if a.podsumowanie:
        przenosne.zapisz_atomowo(Path(a.podsumowanie), json.dumps(wynik, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
