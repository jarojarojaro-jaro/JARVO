"""Instalator Jarva natywnie: `jarvo instaluj` po bootstrapie (docs/NATYWNIE.md, c3, c1, N01, L01–L03, etap E3).

Bootstrap (jarvo/bootstrap/install.ps1 albo install.sh) pobiera uv i Pythona 3.13 z sumami wpisanymi w skrypt, kod
Jarva z GitHuba do `<program>/app/<sha12>` i woła `python -I -X utf8 <app>/jarvo/start.py instaluj`. Dalej krok po
kroku, z paskiem i nazwą kroku:

   1. sprawdzenie: platforma (bez Maca z Intelem, I06), wolne miejsce, stara instalacja z WSL/Dockerem w tym miejscu,
   2. katalogi z c1 (`<dane>` i `<stan>` tylko dla właściciela),
   3–5. uv, Python 3.13 i 3.12 z manifestu (vendor/natywne.lock.json) przez pobieracz: suma przed rozpakowaniem,
   6. `<stan>/narzedzia.json`, 7. `<program>/current.json` (app = katalog kodu tej wersji; poprzedni obok),
   8. Hermes: checkout przypiętego commitu i `uv sync --locked` (jarvo/hermes.py, I02),
   9. front panelu (web_dist), gdy go brak albo na życzenie (`--web-lokalnie`),
  10. bezpieczne ustawienia Hermesa (I13), 11. `<stan>/srodowisko.json`,
  12. polecenie `jarvo` dla właściciela: Windows `<root>\\bin\\jarvo.cmd` i wpis w PATH użytkownika (HKCU\\Environment,
      rozgłoszenie WM_SETTINGCHANGE), macOS i Linux `~/.local/bin/jarvo` i oznaczony blok PATH w ~/.zprofile albo
      ~/.profile, gdy trzeba; `--bez-path`: tylko `<root>/bin/jarvo`, bez zmian poza katalogiem Jarva (próby),
  13. autostart nadzorcy (jarvo/autostart.py; uruchamia go od razu przez mechanizm systemu),
  14. serwis: gdy nie działa, start `jarvo serwis` w tle, 15. czekanie na panel i jego adres.

Każda zmiana poza katalogami Jarva idzie przez jarvo/zmiany_hosta.py (wpis w dzienniku przed zmianą, D08), żeby
`jarvo uninstall` cofnął ją od końca. Przebieg jest idempotentny: drugi niczego nie zmienia (narzędzia ze zgodną
sumą zostają, pliki zapisujemy tylko przy innej treści, PATH i blok rc tylko, gdy ich brak). Instalacja spod
JARVO_ROOT innego niż domyślny dostaje korzeń w argv (`jarvo --korzen <root> …`) w poleceniu jarvo i w autostarcie:
zadanie Harmonogramu nie przekazuje zmiennych środowiska. Wszystko, co dotyka komputera (rejestr, procesy w tle,
sieć lokalna, moduły ładowane przy użyciu), idzie przez `Otoczenie`, które testy podmieniają atrapami.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import manifest, pobieracz, przenosne, sciezki, srodowisko
from .sciezki import MACOS, WINDOWS, Uklad

APP = Path(__file__).resolve().parent.parent         # katalog kodu tej wersji Jarva (zawiera jarvo/ i vendor/)
PORT_PANELU = 9119                                   # jak nadzorca.PORT_PANELU; inny: JARVO_PANEL_PORT
SCIEZKA_PANELU = "/"            # panel Hermesa; adres HQ (/jarvo) dojdzie z wtyczką floty w etapie E4
ZNACZNIK = "Jarvo natywnie (jarvo instaluj)"         # w poleceniu jarvo: plik jest nasz i wolno go nadpisać
NARZEDZIA = (("uv", "uv"), ("python313", "Python 3.13"), ("python312", "Python 3.12"))
MIN_MIEJSCA_GB = 2              # instalacja podstawowa: ok. 1,5–2 GB (c3, pkt 11)
CZAS_PANELU = 180.0             # pierwszy start panelu (import Hermesa, bazy) trwa kilkanaście–kilkadziesiąt sekund
CZAS_NADZORCY = 30.0            # tyle czekamy, aż nadzorca uruchomiony przez autostart otworzy kanał
PATH_RC = ('case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac  '
           "# polecenie jarvo (usunie je jarvo uninstall)")


class BladInstalacji(RuntimeError):
    """Krok instalacji się nie udał: komunikat po polsku z radą, bez sekretów."""


# ---------------------------------------------------------------- otoczenie (atrapy w testach)

def modul(nazwa: str) -> Any:
    """Moduł pakietu jarvo ładowany dopiero przy użyciu: `jarvo --help`, status i doctor działają też przy
    niepełnej instalacji (np. bez nadzorcy), a polecenie mówi wtedy, czego brakuje."""
    return importlib.import_module(f"{__package__}.{nazwa}")


def uruchom_w_tle(argv: list[str], env: dict, log: Path) -> int:
    """Proces odłączony od tego terminala (zamknięcie okna go nie kończy), wyjście dopisywane do `log`. Na Windows
    bez okna, we własnej grupie i poza zadaniem (Job) rodzica, jeśli zadanie na to pozwala."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as wyj:
        kw: dict[str, Any] = dict(stdin=subprocess.DEVNULL, stdout=wyj, stderr=subprocess.STDOUT, env=env,
                                  cwd=str(Path(argv[0]).parent), close_fds=True)
        if not WINDOWS:
            return subprocess.Popen(argv, start_new_session=True, **kw).pid
        flagi = przenosne.flagi_tla()
        try:
            return subprocess.Popen(argv, creationflags=flagi | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw).pid
        except OSError:                      # zadanie rodzica nie pozwala na wyjście (np. część runnerów CI)
            return subprocess.Popen(argv, creationflags=flagi, **kw).pid


def odpowiada(url: str, czas: float = 2.0) -> bool:
    """Czy adres na tym komputerze odpowiada (HTTP poniżej 500). Bez proxy: 127.0.0.1 nigdy nie idzie przez
    serwer pośredniczący z ustawień systemu."""
    otwieracz = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with otwieracz.open(urllib.request.Request(url, headers={"User-Agent": "jarvo"}), timeout=czas) as odp:
            return odp.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except (urllib.error.URLError, OSError, ValueError):
        return False


@dataclass
class Otoczenie:
    """Wszystko, czego instalator i polecenia używają poza własnymi plikami: moduły Jarva ładowane przy użyciu,
    zmienne procesu, rejestr Windows (atrapa z interfejsem zmiany_hosta.Rejestr), programy z PATH, procesy w tle,
    sieć lokalna, przeglądarka i zegar. Testy podstawiają atrapy, więc nie dotykają komputera."""
    modul: Callable[[str], Any] = modul
    env: dict = field(default_factory=lambda: dict(os.environ))
    rejestr: Any = None                                  # None = winreg (zmiany_hosta.Rejestr)
    program: Callable[[str], str | None] = przenosne.program
    uruchom_w_tle: Callable[[list[str], dict, Path], int] = uruchom_w_tle
    odpowiada: Callable[[str, float], bool] = odpowiada
    otworz: Callable[[str], bool] | None = None          # przeglądarka; None = webbrowser.open
    na_pierwszym_planie: Callable[[list[str], dict], int] | None = None   # None = cli.uruchom_na_pierwszym_planie
    czekaj: Callable[[float], None] = time.sleep
    zegar: Callable[[], float] = time.monotonic


# ---------------------------------------------------------------- układ wersji: Python, polecenie, panel, serwis

def _klucz(p: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def korzen_domyslny(u: Uklad, env: dict | None = None) -> bool:
    """Czy `u` to domyślny korzeń tego użytkownika (a nie JARVO_ROOT próby, CI albo drugiej instalacji)."""
    env = {k: v for k, v in (os.environ if env is None else env).items() if k != "JARVO_ROOT"}
    try:
        return _klucz(sciezki.uklad(env).root) == _klucz(u.root)
    except sciezki.BladUkladu:
        return False


def python_jarva(u: Uklad, *, okno: bool = True) -> Path:
    """Python polecenia jarvo i nadzorcy: python313 z `<stan>/narzedzia.json` (PBS, SQLite 3.53). `okno=False` na
    Windows = pythonw.exe (autostart i serwis w tle bez konsoli). Bez wpisu: bieżący interpreter."""
    katalog = (srodowisko.narzedzia(u).get("python313") or {}).get("katalog")
    if katalog:
        k = Path(katalog)
        p = k / ("python.exe" if okno else "pythonw.exe") if WINDOWS else k / "bin" / "python3"
        if p.is_file():
            return p
    exe = Path(sys.executable)
    if WINDOWS and not okno and exe.with_name("pythonw.exe").is_file():
        return exe.with_name("pythonw.exe")
    return exe


def katalog_aplikacji(u: Uklad) -> Path:
    """Kod aktywnej wersji Jarva: `app` z current.json, a bez instalacji katalog, z którego działa ten kod."""
    app = srodowisko.biezace(u).get("app")
    return Path(app) if app and (Path(app) / "jarvo" / "start.py").is_file() else APP


def argumenty_korzenia(u: Uklad, env: dict | None = None) -> list[str]:
    """`--korzen <root>` dla instalacji spod JARVO_ROOT (pusta lista dla domyślnego korzenia)."""
    return [] if korzen_domyslny(u, env) else ["--korzen", str(u.root)]


def polecenie_jarva(u: Uklad, *argumenty: str, okno: bool = True, env: dict | None = None) -> list[str]:
    """argv polecenia jarvo aktywnej wersji, np. `polecenie_jarva(u, "serwis", okno=False)` dla autostartu."""
    start = katalog_aplikacji(u) / "jarvo" / "start.py"
    return [str(python_jarva(u, okno=okno)), "-I", "-X", "utf8", str(start), *argumenty_korzenia(u, env),
            *argumenty]


def port_panelu(env: dict | None = None) -> int:
    """Port panelu: JARVO_PANEL_PORT (próby i druga instalacja obok, ten sam co w nadzorcy) albo 9119."""
    wartosc = str((os.environ if env is None else env).get("JARVO_PANEL_PORT") or PORT_PANELU).strip()
    return int(wartosc) if wartosc.isdigit() and 0 < int(wartosc) < 65536 else PORT_PANELU


def adres_panelu(env: dict | None = None) -> str:
    """Zawsze 127.0.0.1, nie localhost (c4): localhost bywa najpierw ::1, a panel słucha tylko na IPv4."""
    return f"http://127.0.0.1:{port_panelu(env)}{SCIEZKA_PANELU}"


def stan_serwisu(u: Uklad, ot: Otoczenie | None = None) -> tuple[dict | None, str]:
    """(stan nadzorcy na żywo z jego kanału albo None, powód braku). Nic nie tworzy na dysku."""
    ot = ot or Otoczenie()
    if not u.stan.is_dir():
        return None, "Jarvo nie jest zainstalowane w tym katalogu"
    try:
        nadzorca = ot.modul("nadzorca")
    except ImportError as e:
        return None, f"brak modułu nadzorcy ({e})"
    try:
        stan = nadzorca.polacz(u).status()
    except Exception as e:    # noqa: BLE001 - kanał zamknięty, brak potoku albo gniazda, limit czasu: serwis nie działa
        opis = str(e).strip()[:160]
        return None, opis or type(e).__name__
    return (stan if isinstance(stan, dict) else {"stan": stan}), ""


def uruchom_serwis(u: Uklad, ot: Otoczenie) -> int:
    """`jarvo serwis` w tle (nadzorca bramy i panelu), z jego wyjściem startowym w `<logi>/serwis-start.log`."""
    return ot.uruchom_w_tle(polecenie_jarva(u, "serwis", okno=False, env=ot.env), dict(ot.env),
                            u.logi / "serwis-start.log")


def czekaj_na_panel(u: Uklad, ot: Otoczenie, log: Callable[[str], None], limit: float = CZAS_PANELU) -> str:
    """Czeka, aż panel odpowie; zwraca adres. BladInstalacji po `limit` sekundach (z radą, gdzie szukać przyczyny)."""
    adres = adres_panelu(ot.env)
    start = ot.zegar()
    ostatni = 0
    while not ot.odpowiada(adres, 2.0):
        minelo = ot.zegar() - start
        if minelo >= limit:
            raise BladInstalacji(f"panel {adres} nie odpowiada po {int(limit)} s. Sprawdź `jarvo status` "
                                 "i `jarvo logs panel`, potem uruchom `jarvo panel` jeszcze raz.")
        if int(minelo) // 15 > ostatni:
            ostatni = int(minelo) // 15
            log(f"    czekam na panel… {int(minelo)} s")
        ot.czekaj(1.0)
    return adres


def head_gita(katalog: Path) -> str | None:
    """SHA commitu HEAD w checkoucie bez uruchamiania gita: odłączony HEAD, gałąź w refs albo packed-refs,
    także w git worktree (plik .git z `gitdir:` i katalog wspólny z `commondir`)."""
    git = Path(katalog) / ".git"
    try:
        if git.is_file():
            wskazanie = git.read_text(encoding="utf-8").strip()
            if not wskazanie.startswith("gitdir:"):
                return None
            git = (Path(katalog) / wskazanie.split(":", 1)[1].strip()).resolve()
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head if re.fullmatch(r"[0-9a-f]{40}", head) else None
        ref = head.split(":", 1)[1].strip()
        bazy = [git]
        if (git / "commondir").is_file():
            bazy.append((git / (git / "commondir").read_text(encoding="utf-8").strip()).resolve())
        for baza in bazy:
            plik = baza / ref
            if plik.is_file():
                return plik.read_text(encoding="utf-8").strip() or None
            spakowane = baza / "packed-refs"
            if spakowane.is_file():
                for linia in spakowane.read_text(encoding="utf-8").splitlines():
                    czesci = linia.split()
                    if len(czesci) == 2 and czesci[1] == ref:
                        return czesci[0]
    except OSError:
        return None
    return None


def wersja_aplikacji(app: Path) -> str:
    """Wersja kodu Jarva: `.jarvo-wersja` z bootstrapu (pełny SHA), w kopii repo HEAD gita, inaczej „dev”."""
    try:
        sha = (Path(app) / ".jarvo-wersja").read_text(encoding="utf-8").split()[0]
    except (OSError, IndexError):
        sha = head_gita(app) or ""
    return sha[:12] if re.fullmatch(r"[0-9a-f]{7,40}", sha) else "dev"


# ---------------------------------------------------------------- polecenie jarvo dla właściciela

def tresc_jarvo_cmd(python: Path, start: Path, korzen: list[str] = ()) -> bytes:
    """`<root>\\bin\\jarvo.cmd`: cmd.exe czyta plik w stronie kodowej OEM, więc tylko ASCII (ścieżki w `<program>`
    są ASCII, c1); CRLF, bo etykiety i goto w cmd psują się na LF. .cmd, bo polityka Restricted blokuje .ps1 (N01)."""
    dodatki = "".join(f' "{a}"' if a != "--korzen" else " --korzen" for a in korzen)
    tekst = (f"@echo off\r\nrem {ZNACZNIK}: polecenie jarvo. Instalator nadpisuje ten plik przy kazdej wersji.\r\n"
             f'"{python}" -I -X utf8 "{start}"{dodatki} %*\r\nexit /b %ERRORLEVEL%\r\n')
    if not tekst.isascii() or "%" in "".join(korzen):
        raise BladInstalacji(f"ścieżka {python}, {start} albo {' '.join(korzen)} ma znaki spoza ASCII albo %, "
                             "a cmd.exe ich nie odczyta. Ustaw JARVO_ROOT na katalog z samymi literami ASCII "
                             "(np. C:\\Jarvo) i zainstaluj ponownie.")
    return tekst.encode("ascii")


def tresc_jarvo_sh(python: Path, start: Path, korzen: list[str] = ()) -> str:
    """`~/.local/bin/jarvo`: /bin/sh, exec bez pośredniego procesu (sygnały i kod wyjścia idą wprost)."""
    argv = " ".join(shlex.quote(str(a)) for a in [python, "-I", "-X", "utf8", start, *korzen])
    return (f"#!/bin/sh\n# {ZNACZNIK}: polecenie jarvo. Instalator nadpisuje ten plik przy każdej wersji.\n"
            f'exec {argv} "$@"\n')


def korzen_polecenia(tekst: str) -> str | None:
    """Korzeń, któremu służy nasze polecenie jarvo (`--korzen <root>` w treści), None = korzeń domyślny."""
    m = re.search(r"""--korzen ("[^"]*"|'(?:[^']|'"'"')*'|\S+)""", tekst)
    if not m:
        return None
    wartosc = m.group(1)
    if wartosc.startswith('"'):
        return wartosc[1:-1]
    return shlex.split(wartosc)[0] if wartosc.startswith("'") else wartosc


def plik_rc(dom: Path, powloka: str, macos: bool) -> Path:
    """Plik startowy powłoki logowania: zsh (domyślna na macOS) czyta ~/.zprofile; bash czyta pierwszy istniejący
    z ~/.bash_profile i ~/.profile, więc nowy ~/.bash_profile przesłoniłby czyjś ~/.profile."""
    if macos or Path(powloka or "").name == "zsh":
        return dom / ".zprofile"
    return dom / ".bash_profile" if (dom / ".bash_profile").is_file() else dom / ".profile"


def obca_instalacja(u: Uklad, dom: Path | None = None, *, polecenie_w_domu: bool = True) -> str | None:
    """Powód odmowy, gdy w miejscu instalacji jest stara instalacja (WSL i Docker) albo cudze polecenie jarvo
    (`polecenie_w_domu=False`: ~/.local/bin nas nie obchodzi, bo polecenie idzie do `<root>/bin`). Migracja
    przyjdzie w etapie E12 (`jarvo migruj`); do tego czasu niczego z niej nie nadpisujemy."""
    if WINDOWS:
        if (u.root / "wsl").is_dir():
            return f"w {u.root} jest stara instalacja Jarvo z WSL (katalog wsl)"
        cmd = u.root / "bin" / "jarvo.cmd"
        if cmd.is_file() and ZNACZNIK not in cmd.read_text(encoding="utf-8", errors="replace"):
            return f"{cmd} należy do starej instalacji Jarvo (WSL)"
        return None
    if not polecenie_w_domu:
        return None
    cel = (dom or Path.home()) / ".local" / "bin" / "jarvo"
    if cel.is_symlink() or cel.exists():
        try:
            nasz = cel.is_file() and not cel.is_symlink() and ZNACZNIK in cel.read_text(encoding="utf-8",
                                                                                         errors="replace")
        except OSError:
            nasz = False
        if not nasz:
            cel_linku = f" (dowiązanie do {os.readlink(cel)})" if cel.is_symlink() else ""
            return f"{cel}{cel_linku} należy do innej instalacji Jarvo (np. starej z Dockerem)"
    return None


# ---------------------------------------------------------------- przebieg instalacji

def _pasek(i: int, n: int, szerokosc: int = 24) -> str:
    pelne = round(szerokosc * i / n)
    return "[" + "#" * pelne + "-" * (szerokosc - pelne) + f"] {i:>2}/{n}"


def _zapisz_jesli_inne(cel: Path, tresc: str | bytes) -> bool:
    dane = tresc.encode("utf-8") if isinstance(tresc, str) else tresc
    try:
        if cel.is_file() and cel.read_bytes() == dane:
            return False
    except OSError:
        pass
    przenosne.zapisz_atomowo(cel, dane)
    return True


def _json(dane: dict) -> str:
    return json.dumps(dane, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _wolne_gb(sciezka: Path) -> float:
    p = Path(sciezka)
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(p).free / 1e9


class _Instalacja:
    def __init__(self, u: Uklad, app: Path, ot: Otoczenie, log: Callable[[str], None], *, autostart: bool,
                 web_lokalnie: bool, start: bool, bez_path: bool, platforma: str | None):
        self.u, self.app, self.ot, self._log = u, Path(app).resolve(), ot, log
        self.autostart, self.web_lokalnie, self.start, self.bez_path = autostart, web_lokalnie, start, bez_path
        self.platforma = platforma
        self.narz: dict = {}
        self.checkout: Path | None = None
        self.app_zmieniona = False
        self.start_autostartem = False
        self.zmiany: list[str] = []          # co zmienił ten przebieg (drugi przebieg: nic)
        self.uwagi: list[str] = []
        self._bufor: list[str] = []

    # dziennik instalacji: ekran + <logi>/instalacja.log (bez sekretów: komunikaty ich nie zawierają)
    def log(self, tekst: str) -> None:
        self._log(tekst)
        self._bufor.append(tekst)
        if self.u.logi.is_dir():
            try:
                with open(self.u.logi / "instalacja.log", "a", encoding="utf-8") as f:
                    f.write("".join(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {t}\n" for t in self._bufor))
                self._bufor.clear()
            except OSError:
                pass

    def podlog(self, tekst: str) -> None:
        self.log(f"    {tekst}")

    def kroki(self) -> list[tuple[str, Callable[[], None]]]:
        k: list[tuple[str, Callable[[], None]]] = [("Sprawdzenie komputera", self.sprawdzenie),
                                                    ("Katalogi", self.katalogi)]
        k += [(opis, lambda n=nazwa: self.narzedzie(n)) for nazwa, opis in NARZEDZIA]
        k += [("Spis narzędzi", self.spis_narzedzi), ("Wersja Jarva", self.wersja_jarva), ("Hermes", self.hermes),
              ("Front panelu", self.front), ("Bezpieczne ustawienia Hermesa", self.konfiguracja),
              ("Środowisko procesów", self.zapis_srodowiska), ("Polecenie jarvo", self.polecenie)]
        if self.autostart:
            k.append(("Autostart", self.wlacz_autostart))
        if self.start:
            k += [("Serwis", self.serwis), ("Panel", self.panel)]
        return k

    def uruchom(self) -> int:
        kroki = self.kroki()
        self.log(f"Jarvo natywnie: instalacja w {self.u.root}")
        for i, (nazwa, krok) in enumerate(kroki, 1):
            self.log(f"{_pasek(i, len(kroki))}  {nazwa}")
            try:
                krok()
            except Exception as e:    # noqa: BLE001 - każdy błąd kroku kończy instalację czytelnym komunikatem
                self.log(f"BŁĄD w kroku „{nazwa}”: {e}")
                self._slad()
                self.log("Instalację można uruchomić ponownie: gotowe kroki zostaną pominięte.")
                return 1
        for uwaga in self.uwagi:
            self.log(f"Uwaga: {uwaga}")
        zmiany = ", ".join(dict.fromkeys(self.zmiany)) or "brak"
        self.log(f"Gotowe. Zmiany w tym przebiegu: {zmiany}.")
        if self.start:
            self.log(f"Panel: {adres_panelu(self.ot.env)}")
        self.log("Polecenia: jarvo chat, jarvo status, jarvo panel, jarvo doctor (w nowym oknie terminala).")
        return 0

    def _slad(self) -> None:
        """Pełny ślad błędu tylko do pliku dziennika (na ekranie wystarczy komunikat)."""
        if self.u.logi.is_dir():
            try:
                with open(self.u.logi / "instalacja.log", "a", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
            except OSError:
                pass

    # -- kroki
    def sprawdzenie(self) -> None:
        self.platforma = self.platforma or sciezki.platforma()
        self.podlog(f"platforma {self.platforma}, Python {sys.version.split()[0]}")
        powod = obca_instalacja(self.u, polecenie_w_domu=not self.bez_path)
        if powod:
            raise BladInstalacji(f"{powod}. Migracja (jarvo migruj) przyjdzie w etapie E12; do tego czasu zainstaluj "
                                 "Jarvo natywnie w osobnym katalogu: ustaw JARVO_ROOT (np. D:\\Jarvo albo ~/jarvo-"
                                 "natywnie) i uruchom polecenie instalacji ponownie.")
        wolne = _wolne_gb(self.u.root)
        if wolne < MIN_MIEJSCA_GB:
            raise BladInstalacji(f"na dysku z {self.u.root} jest {wolne:.1f} GB wolnego miejsca, a instalacja "
                                 f"potrzebuje co najmniej {MIN_MIEJSCA_GB} GB. Zwolnij miejsce albo ustaw JARVO_ROOT "
                                 "na inny dysk.")

    def katalogi(self) -> None:
        nowe = [k for k in [*self.u.katalogi(), self.u.stan / "gateway-locks"] if not k.is_dir()]
        for k in nowe:
            k.mkdir(parents=True, exist_ok=True)
        for k in (self.u.dane, self.u.stan):                 # sekrety, klucze API i kanał nadzorcy (D02, c2)
            przenosne.chron(k, katalog=True)
        if nowe:
            self.zmiany.append("katalogi")

    def narzedzie(self, nazwa: str) -> None:
        n = manifest.wczytaj(self.app)
        wpis = manifest.plik(n, nazwa, self.platforma)
        wersja = manifest.wersja(n, nazwa)
        docelowy = self.u.program / "narzedzia" / nazwa / pobieracz.katalog_wersji(wersja)
        try:
            bylo = (docelowy / ".jarvo-suma").read_text(encoding="utf-8").strip() == wpis["sha256"]
        except OSError:
            bylo = False
        katalog = pobieracz.zainstaluj(nazwa, wersja, wpis, self.u.program / "narzedzia", self.u.cache / "pobrane")
        self.narz[nazwa] = {
            "wersja": wersja, "katalog": str(katalog),
            "bin": [str(katalog / b) for b in wpis.get("bin") or []],
            "env": {str(k): str(v).replace("{katalog}", str(katalog)) for k, v in (wpis.get("env") or {}).items()},
        }
        self.podlog(f"{nazwa} {wersja}: {'już jest' if bylo else 'zainstalowany'} ({katalog})")
        if not bylo:
            self.zmiany.append(nazwa)

    def spis_narzedzi(self) -> None:
        spis = {**srodowisko.narzedzia(self.u), **self.narz}
        if _zapisz_jesli_inne(self.u.stan / "narzedzia.json", _json(spis)):
            self.zmiany.append("narzedzia.json")

    def _zapisz_biezace(self, **pola) -> None:
        biez = srodowisko.biezace(self.u)
        nowe = {**biez, **{k: v for k, v in pola.items() if v is not None}}
        if nowe != biez:
            przenosne.zapisz_atomowo(self.u.program / "current.json", _json(nowe))
            self.zmiany.append("current.json")

    def wersja_jarva(self) -> None:
        if not (self.app / "jarvo" / "start.py").is_file():
            raise BladInstalacji(f"{self.app} nie wygląda na kod Jarva (brak jarvo/start.py)")
        biez = srodowisko.biezace(self.u)
        if biez.get("app") and biez["app"] != str(self.app):
            # poprzednia wersja obok: `jarvo update` wraca do niej, gdy nowa nie wstanie (c4, pkt 5)
            przenosne.zapisz_atomowo(self.u.program / "current.poprzedni.json", _json(biez))
            self.app_zmieniona = True
        wersja = wersja_aplikacji(self.app)
        self._zapisz_biezace(app=str(self.app), wersja=wersja)
        self.podlog(f"wersja {wersja}: {self.app}")

    def _bin_narzedzia(self, nazwa: str) -> Path:
        k = Path(self.narz[nazwa]["katalog"])
        if nazwa == "uv":
            return k / ("uv.exe" if WINDOWS else "uv")
        return k / "python.exe" if WINDOWS else k / "bin" / "python3"

    def _git(self) -> Path:
        git = self.ot.program("git")
        ok = False
        if git:
            try:
                ok = subprocess.run([git, "--version"], capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=60, env=self.ot.env,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
        if ok:
            return Path(git)
        if WINDOWS:
            rada = ("Na razie potrzebny jest Git for Windows w PATH (https://git-scm.com/download/win); własny "
                    "PortableGit z sumą przyjdzie z manifestem w etapie E2 (decyzja I05).")
        elif MACOS:
            rada = "Zainstaluj narzędzia wiersza poleceń Xcode: xcode-select --install."
        else:
            rada = "Zainstaluj git menedżerem pakietów systemu (np. sudo apt install git)."
        raise BladInstalacji(f"brak działającego programu git (potrzebny do pobrania Hermesa). {rada} Potem "
                             "uruchom polecenie instalacji ponownie.")

    def hermes(self) -> None:
        h = self.ot.modul("hermes")
        pin = manifest.hermes(self.app)
        checkout = h.zainstaluj(self.u, pin, git=self._git(), uv=self._bin_narzedzia("uv"),
                                python=self._bin_narzedzia("python313"), log=self.podlog)
        self.checkout = Path(checkout)
        self._zapisz_biezace(hermes=str(self.checkout))

    def _checkout(self) -> Path:
        if self.checkout is None:
            raise BladInstalacji("brak checkoutu Hermesa (krok „Hermes” się nie wykonał)")
        return self.checkout

    def front(self) -> None:
        checkout = self._checkout()
        zapisany = srodowisko.biezace(self.u).get("web_dist")
        kandydaci = [Path(zapisany)] if zapisany else []
        kandydaci.append(checkout / "hermes_cli" / "web_dist")
        gotowy = next((k for k in kandydaci if (k / "index.html").is_file()), None)
        if gotowy and not self.web_lokalnie:
            self.podlog(f"front już jest: {gotowy}")
            self._zapisz_biezace(web_dist=str(gotowy))
            return
        # npm wybiera hermes.web_dist: Node Jarva z narzedzia.json, a bez niego z PATH (Node z manifestem: E2)
        dist = self.ot.modul("hermes").web_dist(self.u, checkout, npm=None, log=self.podlog)
        self._zapisz_biezace(web_dist=str(dist))

    def _env(self) -> dict[str, str]:
        return srodowisko.srodowisko(self.u, self.ot.env)

    def konfiguracja(self) -> None:
        self.ot.modul("hermes").konfiguracja_bezpieczna(self.u, self._checkout(), self._env(), log=self.podlog)

    def zapis_srodowiska(self) -> None:
        cel = self.u.stan / "srodowisko.json"
        przed = cel.read_bytes() if cel.is_file() else b""
        srodowisko.zapisz(self.u, self._env())
        if cel.read_bytes() != przed:
            self.zmiany.append("srodowisko.json")

    def polecenie(self) -> None:
        python = python_jarva(self.u)
        start = self.app / "jarvo" / "start.py"
        korzen = argumenty_korzenia(self.u, self.ot.env)
        if WINDOWS:
            self.polecenie_windows(self.u.root / "bin", sciezki.krotka_sciezka(python),
                                   sciezki.krotka_sciezka(start), korzen)
        else:
            self.polecenie_posix(Path.home(), python, start, korzen)

    def polecenie_windows(self, katalog: Path, python: Path, start: Path, korzen: list[str]) -> None:
        zm = self.ot.modul("zmiany_hosta")
        cel = katalog / "jarvo.cmd"
        if zm.zapisz_plik(self.u, cel, tresc_jarvo_cmd(python, start, korzen), None):
            self.zmiany.append(str(cel))
        self.podlog(f"polecenie: {cel}")
        if self.bez_path:
            self.podlog("PATH użytkownika bez zmian (--bez-path): polecenie uruchomisz pełną ścieżką")
            return
        if zm.dodaj_do_path(self.u, katalog, rejestr=self.ot.rejestr):
            self.zmiany.append("PATH użytkownika")
            self.podlog(f"PATH użytkownika: dopisany {katalog} (nowe okna terminala go widzą)")
        inne = shutil.which("jarvo", path=self.ot.env.get("PATH", ""))
        if inne and Path(inne).resolve().parent != Path(katalog).resolve():
            self.uwagi.append(f"w PATH wcześniej jest inne polecenie jarvo ({inne}); to uruchomisz pełną ścieżką "
                              f"{cel}")

    def polecenie_posix(self, dom: Path, python: Path, start: Path, korzen: list[str]) -> None:
        zm = self.ot.modul("zmiany_hosta")
        tresc = tresc_jarvo_sh(python, start, korzen)
        cel = dom / ".local" / "bin" / "jarvo"
        if not self.bez_path and cel.is_file():
            # nasze polecenie innej instalacji Jarva (np. domyślnej, a ta jest spod JARVO_ROOT): zostaje jej
            stary = korzen_polecenia(cel.read_text(encoding="utf-8", errors="replace"))
            if stary is None:
                stary = str(sciezki.uklad({k: v for k, v in self.ot.env.items() if k != "JARVO_ROOT"}).root)
            if _klucz(stary) != _klucz(self.u.root):
                self.uwagi.append(f"{cel} uruchamia inną instalację Jarva ({stary}); polecenie tej: "
                                  f"{self.u.root / 'bin' / 'jarvo'}")
                self.bez_path = True
        if self.bez_path:
            cel = self.u.root / "bin" / "jarvo"
        if zm.zapisz_plik(self.u, cel, tresc, 0o755):
            self.zmiany.append(str(cel))
        self.podlog(f"polecenie: {cel}")
        if self.bez_path or str(cel.parent) in self.ot.env.get("PATH", "").split(os.pathsep):
            return
        rc = plik_rc(dom, self.ot.env.get("SHELL", ""), MACOS)
        tekst = rc.read_text(encoding="utf-8", errors="replace") if rc.is_file() else ""
        sam_doklada = re.search(r"(\$HOME|\$\{HOME\}|~)/\.local/bin|" + re.escape(str(cel.parent)), tekst)
        if "# >>> jarvo >>>" not in tekst and sam_doklada:
            return                                           # plik sam dokłada ~/.local/bin do PATH
        if zm.dodaj_blok_rc(self.u, rc, PATH_RC):
            self.zmiany.append(str(rc))
            self.podlog(f"PATH: blok jarvo w {rc} (działa w nowym terminalu)")

    def _zatrzymaj_stara_wersje(self) -> None:
        """Nowa wersja: serwis starej trzeba zatrzymać, zanim wystartuje nowy (autostart z IgnoreNew zostawiłby
        starego nadzorcę przy życiu)."""
        stan, _ = stan_serwisu(self.u, self.ot)
        if stan is None:
            return
        self.podlog("nowa wersja: zatrzymuję serwis poprzedniej")
        self.ot.modul("nadzorca").polacz(self.u).stop()
        koniec = self.ot.zegar() + 120
        while stan is not None and self.ot.zegar() < koniec:
            self.ot.czekaj(1.0)
            stan, _ = stan_serwisu(self.u, self.ot)
        if stan is not None:
            raise BladInstalacji("serwis poprzedniej wersji nie zatrzymał się w 120 s; uruchom instalację ponownie")
        self.app_zmieniona = False

    def wlacz_autostart(self) -> None:
        if self.start and self.app_zmieniona:
            self._zatrzymaj_stara_wersje()
        wynik = self.ot.modul("autostart").wlacz(self.u, polecenie_jarva(self.u, "serwis", okno=False, env=self.ot.env),
                                                 start=self.start, log=self.podlog)
        self.start_autostartem = isinstance(wynik, dict) and bool(wynik.get("uruchomiony"))
        if isinstance(wynik, dict) and wynik.get("zmieniony"):
            self.zmiany.append("autostart")

    def serwis(self) -> None:
        if self.app_zmieniona:
            self._zatrzymaj_stara_wersje()
        stan, _ = stan_serwisu(self.u, self.ot)
        if stan is None and self.start_autostartem:
            # autostart uruchomił nadzorcę przez mechanizm systemu (np. schtasks /Run): czekamy na jego kanał,
            # zamiast stawiać drugiego (zapasowe wyzwalacze z IgnoreNew i tak trzymają jedną kopię)
            koniec = self.ot.zegar() + CZAS_NADZORCY
            while stan is None and self.ot.zegar() < koniec:
                self.ot.czekaj(1.0)
                stan, _ = stan_serwisu(self.u, self.ot)
        if stan is not None:
            self.podlog("serwis działa" + (" (uruchomił go autostart)" if self.start_autostartem else ""))
            return
        pid = uruchom_serwis(self.u, self.ot)
        self.podlog(f"serwis uruchomiony w tle (PID {pid})")

    def panel(self) -> None:
        self.podlog(f"panel odpowiada: {czekaj_na_panel(self.u, self.ot, self.log)}")


def wypisz(tekst: str) -> None:
    """Domyślny `log`: wiersz od razu na ekran (pasek pobierania idzie na stderr, więc bez flush kolejność w logu
    CI się miesza)."""
    print(tekst, flush=True)


def instaluj(u: Uklad, app: Path, *, autostart: bool = True, web_lokalnie: bool = False, start: bool = True,
             bez_path: bool = False, log: Callable[[str], None] = wypisz, otoczenie: Otoczenie | None = None,
             platforma: str | None = None) -> int:
    """Instalacja albo naprawa Jarva w układzie `u` z kodu w `app`; 0 = gotowe, 1 = błąd (komunikat wypisany).
    `start=False` kończy po poleceniu jarvo i autostarcie (bez startu serwisu); `bez_path=True`: polecenie tylko
    w `<root>/bin`, bez PATH i plików startowych powłoki (próby na komputerze właściciela)."""
    return _Instalacja(u, app, otoczenie or Otoczenie(), log, autostart=autostart, web_lokalnie=web_lokalnie,
                       start=start, bez_path=bez_path, platforma=platforma).uruchom()
