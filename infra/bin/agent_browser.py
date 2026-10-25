"""agent-browser w Jarvie natywnie: demon bez serwera podglądu, bez pobierania bez sumy i bez profilu Chrome właściciela.

Odpowiednik nakładki bash z obrazu (infra/bin/agent-browser) dla instalacji natywnej na Windows, macOS i Linuksie
(docs/NATYWNIE.md C05, docs/TOOLBOX.md „agent-browser bez serwera podglądu”). Sama biblioteka standardowa: działa
Pythonem z python-build-standalone, bez venvu.

Demon agent-browsera (0.38.1) przy starcie każdej sesji otwiera na 127.0.0.1 serwer WebSocket/HTTP bez hasła: obraz
strony, każde polecenie z wynikiem (także wpisywane wartości), wstrzykiwanie myszy i klawiatury, zakładanie sesji.
Strona otwarta w przeglądarce agenta (np. podgląd serwera deweloperskiego na localhost) mogłaby go znaleźć. Zmienną ani
flagą się go nie wyłączy (AGENT_BROWSER_STREAM_PORT zmienia tylko port), tylko poleceniem `stream disable` do
działającego demona. Nakładka wysyła je przed każdym poleceniem, które łączy się z demonem, z tymi samymi flagami
globalnymi: gdy demona jeszcze nie ma, startuje bez serwera podglądu, zanim otworzy jakąkolwiek stronę. Gdy wyłączyć
się nie da, polecenie nie idzie dalej. Odrzuca (kod 1, przy --json odpowiedź JSON jak agent-browser):
- `stream enable`, `dashboard` i `mcp`: serwery i demony bez hasła z pominięciem nakładki (jak nakładka bash),
- `install`, `upgrade`, `plugin add`: pobierają przeglądarkę, nowe wersje i wtyczki z sieci bez sumy, a Jarvo bierze
  Chromium i agent-browsera z manifestu instalacji (vendor/natywne.yaml, docs/NATYWNIE.md zasada 3),
- `--auto-connect`, `profiles` i `--profile <nazwa>` (także AGENT_BROWSER_AUTO_CONNECT i AGENT_BROWSER_PROFILE): to
  przeglądarka i profile Chrome właściciela z zalogowanymi kontami; własny profil agenta to ścieżka katalogu.
Silnik chrome (Windows: zawsze, bo Lightpanda nie ma tam wydania; macOS i Linux: zapas Hermesa dla zrzutów) dostaje
AGENT_BROWSER_EXECUTABLE_PATH = CHROME_PATH (chrome-headless-shell z manifestu), gdy nikt go nie ustawił; Lightpanda
nigdy (agent-browser użyłby tej ścieżki także dla niej, infra/Dockerfile).

Ostatnie polecenie: na POSIX exec (proces nakładki staje się agent-browserem, jak `exec` w bashu). Na Windows exec
odpina proces od rodzica, więc nakładka uruchamia binarkę, czeka na nią i zwraca jej kod. Binarka dostaje tylko trzy
uchwyty wejścia i wyjścia (STARTF_USESTDHANDLES, close_fds: cudze uchwyty konsoli zabijają demona, tak samo robi
Hermes) i trafia do zadania (job object) z KILL_ON_JOB_CLOSE: zabicie nakładki (Hermes po limicie czasu) zabija też
polecenie, a demon, którego polecenie uruchamia, wychodzi z zadania (SILENT_BREAKAWAY_OK) i żyje dalej.

Program w `<program>/bin-floty` (pierwszy w PATH procesów floty; Hermes szuka go przez shutil.which) zakłada
`zainstaluj(bin_floty, python)`: na Windows `agent-browser.exe` = launcher distlib (t64.exe z koła pip, które ma
Python z python-build-standalone: ten sam plik, który uruchamia każdy skrypt z `pip install` na Windows), wiersz
`#!"<python>" -I -S -X utf8` i zip z tym modułem jako __main__.py; na macOS i Linuksie `agent-browser` = dwa wiersze
sh (exec Pythona na tym samym pliku) i ten sam zip. Bez .cmd, bo cmd.exe przetwarza argumenty po swojemu (& w adresie,
%, cudzysłowy i nowe wiersze w skryptach `eval`). Na macOS i Linuksie obok staje `chromium` (exec chrome-headless-shell),
jak /usr/local/bin/chromium w obrazie: Hermes sprawdza nim, czy jest Chromium do zapasu Lightpandy.
"""
from __future__ import annotations

import glob
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

WINDOWS = os.name == "nt"

# flagi globalne jak w agent-browser 0.38.1 (cli/src/flags.rs, clean_args): z wartością i bez (to samo co w nakładce bash)
Z_WARTOSCIA = frozenset("""
    --session --restore-save --restore-check-url --restore-check-text --restore-check-fn --namespace --headers
    --executable-path --cdp --extension --init-script --enable --profile --state --proxy --proxy-bypass --args
    --user-agent -p --provider --device --session-name --color-scheme --download-path --max-output --allowed-domains
    --action-policy --confirm-actions --config --engine --input-mode --screenshot-dir --screenshot-quality
    --screenshot-format --idle-timeout --ca-cert --model""".split())
BEZ_WARTOSCI = frozenset("""
    --json --headed --webgpu --no-webmcp --debug --ignore-https-errors --allow-file-access --hide-scrollbars
    --auto-connect --pin-tab --no-pin-tab --no-ca-cert --annotate --content-boundaries --confirm-interactive
    --no-auto-dialog -v --verbose -q --quiet --offline --quick --fix""".split())
WPROST = frozenset({"--version", "-V", "--help", "-h"})
# polecenia, które nie łączą się z demonem (agent-browser 0.38.1, cli/src/main.rs): prosto do binarki
BEZ_DEMONA = frozenset({"", "help", "doctor", "skills", "plugin", "plugins", "session", "chat"})
KONTENER = "/opt/jarvo/node/node_modules/agent-browser/bin/agent-browser-linux-*"   # binarka w obrazie (bez manifestu)

PODGLAD = "serwer podglądu agent-browsera jest w Jarvie wyłączony (bez hasła, na 127.0.0.1)"
POBIERANIE = ("agent-browser {0} pobiera z sieci bez sumy; w Jarvie Chromium i agent-browser są z instalacji "
              "(manifest z sumami), a nową wersję daje aktualizacja Jarva")
PROFIL_WLASCICIELA = ("{0}: to przeglądarka i profile Chrome właściciela z zalogowanymi kontami, w Jarvie wyłączone; "
                      "własny profil agenta podajesz jako ścieżkę katalogu (--profile <katalog>)")

# program w bin-floty
ARGUMENTY_PYTHONA = ("-I", "-S", "-X", "utf8")   # bez PYTHONPATH, site-packages i katalogu bieżącego; UTF-8 zawsze
LAUNCHERY = {0x8664: "t64.exe", 0xAA64: "t64-arm.exe"}     # maszyna z nagłówka PE python.exe → launcher distlib
NAGLOWEK_SH = "# Jarvo: nakładka agent-browsera (infra/bin/agent_browser.py); plik pisze instalacja Jarva, zmiany znikną"


# ------------------------------------------------------------------ argumenty

def binarka(env: dict) -> str | None:
    """Prawdziwy agent-browser: JARVO_AGENT_BROWSER_BIN z manifestu instalacji (narzedzia.json), w obrazie jedyna
    binarka platformy w node_modules (jak nakładka bash)."""
    if env.get("JARVO_AGENT_BROWSER_BIN"):
        return env["JARVO_AGENT_BROWSER_BIN"]
    kandydaci = glob.glob(KONTENER)
    return kandydaci[0] if len(kandydaci) == 1 else None


def rozbierz(args: list[str]) -> tuple[list[str], list[str], bool] | None:
    """(flagi globalne, polecenie z argumentami, czy --json); None = --version/--help: prosto do binarki.
    Kolejność i znaczenie flag jak w nakładce bash: wartość flagi nie jest poleceniem, `true`/`false` po fladze bez
    wartości należy do niej, `--restore[=nazwa]` jest flagą."""
    globalne: list[str] = []
    polecenie: list[str] = []
    json_ = False
    i = 0
    while i < len(args):
        a = args[i]
        if a in WPROST:
            return None
        if a in Z_WARTOSCIA:
            globalne += [a, args[i + 1] if i + 1 < len(args) else ""]
            i += 2
        elif a in BEZ_WARTOSCI:
            globalne.append(a)
            json_ = json_ or a == "--json"
            if i + 1 < len(args) and args[i + 1] in ("true", "false"):
                globalne.append(args[i + 1])
                i += 1
            i += 1
        elif a == "--restore" or a.startswith("--restore="):
            globalne.append(a)
            i += 1
        else:
            polecenie.append(a)
            i += 1
    return globalne, polecenie, json_


def wartosc(globalne: list[str], flaga: str) -> str | None:
    """Ostatnia wartość flagi globalnej z wartością (jak u agent-browsera: późniejsza wygrywa)."""
    znaleziona = None
    for i in range(len(globalne) - 1):
        if globalne[i] == flaga:
            znaleziona = globalne[i + 1]
    return znaleziona


def wlaczona(globalne: list[str], flaga: str) -> bool:
    """Flaga bez wartości włączona (`--x` albo `--x true`; `--x false` wyłącza)."""
    stan = False
    for i, a in enumerate(globalne):
        if a == flaga:
            stan = not (i + 1 < len(globalne) and globalne[i + 1] == "false")
    return stan


def _prawda(tekst: str | None) -> bool:
    return bool(tekst) and tekst.strip().lower() not in ("0", "false", "no", "off", "")


def _sciezka(tekst: str) -> bool:
    """`--profile` z katalogiem (własny profil agenta), a nie nazwą profilu Chrome właściciela (Default, Profile 1)."""
    return "/" in tekst or "\\" in tekst or tekst.startswith(("~", "."))


def powod_odmowy(globalne: list[str], polecenie: list[str], env: dict) -> str | None:
    p0, p1 = (polecenie + ["", ""])[:2]
    if p0 == "stream" and p1 == "enable":
        return PODGLAD
    if p0 == "dashboard":
        return "panel agent-browsera jest w Jarvie wyłączony (serwer bez hasła)"
    if p0 == "mcp":
        return "serwer MCP agent-browsera nie jest w Jarvie używany (otwierałby sesje z serwerem podglądu)"
    if p0 in ("install", "upgrade"):
        return POBIERANIE.format(p0)
    if p0 in ("plugin", "plugins") and p1 == "add":
        return ("wtyczki agent-browsera z npm i GitHuba są w Jarvie wyłączone: kod z sieci bez przeglądu i sumy "
                "(docs/SOURCES.md)")
    if p0 == "profiles":
        return PROFIL_WLASCICIELA.format("profiles")
    if wlaczona(globalne, "--auto-connect") or _prawda(env.get("AGENT_BROWSER_AUTO_CONNECT")):
        return PROFIL_WLASCICIELA.format("--auto-connect")
    profil = wartosc(globalne, "--profile") or env.get("AGENT_BROWSER_PROFILE") or ""
    if profil and not _sciezka(profil):
        return PROFIL_WLASCICIELA.format(f"--profile {profil}")
    return None


def silnik(globalne: list[str], env: dict) -> str:
    return (wartosc(globalne, "--engine") or env.get("AGENT_BROWSER_ENGINE") or "chrome").strip().lower()


def srodowisko(globalne: list[str], env: dict) -> dict:
    """Środowisko binarki: silnik inny niż Lightpanda dostaje Chromium z instalacji (CHROME_PATH), gdy nikt nie podał
    własnego (AGENT_BROWSER_EXECUTABLE_PATH, --executable-path). Bez tego agent-browser szukałby Chrome w systemie
    (np. przeglądarki właściciela) albo prosił o `agent-browser install`."""
    env = dict(env)
    chrome = env.get("CHROME_PATH") or ""
    if (silnik(globalne, env) != "lightpanda" and not env.get("AGENT_BROWSER_EXECUTABLE_PATH")
            and wartosc(globalne, "--executable-path") is None and chrome and os.path.isfile(chrome)):
        env["AGENT_BROWSER_EXECUTABLE_PATH"] = chrome
    return env


def odmowa(tekst: str, json_: bool) -> int:
    if json_:
        _pisz(sys.stdout, json.dumps({"success": False, "data": None, "error": tekst}, ensure_ascii=False,
                                     separators=(",", ":")) + "\n")
    else:
        _pisz(sys.stderr, f"agent-browser: {tekst}\n")
    return 1


def _pisz(strumien, tekst: str) -> None:
    """Zawsze UTF-8 (Hermes czyta wyjście jako UTF-8), także gdy Python dostał stronę kodową systemu."""
    bufor = getattr(strumien, "buffer", None)
    if bufor is None:
        strumien.write(tekst)
        strumien.flush()
        return
    strumien.flush()
    bufor.write(tekst.encode("utf-8"))
    bufor.flush()


# ------------------------------------------------------------------ procesy

def _okno_konsoli() -> bool:
    """Czy nakładka ma widoczne okno konsoli (właściciel w terminalu). Bez okna (Hermes uruchamia bez konsoli)
    binarka dostaje CREATE_NO_WINDOW: inaczej proces bez konsoli otworzyłby nowe okno."""
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except (AttributeError, OSError):
        return False


class _Zadanie:
    """Windows: job object z KILL_ON_JOB_CLOSE (procesy w nim giną razem z nakładką) i SILENT_BREAKAWAY_OK (ich dzieci,
    np. demon agent-browsera, są poza nim). Uchwyt zamyka dopiero koniec procesu nakładki. Bez ctypes albo przy odmowie
    systemu (zagnieżdżone zadania z ograniczeniami) po prostu nic nie robi."""

    def __init__(self) -> None:
        self.uchwyt = None
        try:
            import ctypes
            from ctypes import wintypes

            class Licznik(ctypes.Structure):
                _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount",
                                                              "OtherOperationCount", "ReadTransferCount",
                                                              "WriteTransferCount", "OtherTransferCount")]

            class Podstawowe(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class Rozszerzone(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", Podstawowe), ("IoInfo", Licznik),
                            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateJobObjectW.restype = wintypes.HANDLE
            k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            uchwyt = k32.CreateJobObjectW(None, None)
            if not uchwyt:
                return
            info = Rozszerzone()
            # KILL_ON_JOB_CLOSE | SILENT_BREAKAWAY_OK | BREAKAWAY_OK (demon może też sam prosić o wyjście z zadania)
            info.BasicLimitInformation.LimitFlags = 0x2000 | 0x1000 | 0x800
            if k32.SetInformationJobObject(uchwyt, 9, ctypes.byref(info), ctypes.sizeof(info)):   # Extended = 9
                self.uchwyt, self._k32 = uchwyt, k32
            else:
                k32.CloseHandle(uchwyt)
        except (AttributeError, OSError, ImportError):
            self.uchwyt = None

    def dodaj(self, proces: subprocess.Popen) -> None:
        if self.uchwyt is not None:
            self._k32.AssignProcessToJobObject(self.uchwyt, int(proces._handle))


_ZADANIE: _Zadanie | None = None


def _zadanie() -> _Zadanie:
    global _ZADANIE
    if _ZADANIE is None:
        _ZADANIE = _Zadanie()
    return _ZADANIE


def _uchwyt(fd: int):
    """Własny uchwyt wejścia albo wyjścia dla binarki; proces bez niego (pythonw) daje binarce NUL."""
    try:
        os.fstat(fd)
        return fd
    except OSError:
        return subprocess.DEVNULL


def _popen(argv: list[str], env: dict, *, stdin, stdout, stderr) -> subprocess.Popen:
    kw: dict = {"env": env, "stdin": stdin, "stdout": stdout, "stderr": stderr, "close_fds": True}
    if WINDOWS:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESTDHANDLES
        kw.update(startupinfo=si, creationflags=0 if _okno_konsoli() else subprocess.CREATE_NO_WINDOW)
    proces = subprocess.Popen(argv, **kw)
    if WINDOWS:
        _zadanie().dodaj(proces)
    return proces


def _czekaj(proces: subprocess.Popen) -> int:
    try:
        return proces.wait()
    except KeyboardInterrupt:
        proces.kill()
        proces.wait()
        return 130


def uruchom(ab: str, args: list[str], env: dict) -> int:
    """Polecenie dla binarki z tym samym wejściem i wyjściem: na POSIX exec, na Windows proces potomny i jego kod."""
    argv = [ab, *args]
    try:
        if not WINDOWS:
            sys.stdout.flush()
            sys.stderr.flush()
            os.execve(ab, argv, env)
        return _czekaj(_popen(argv, env, stdin=_uchwyt(0), stdout=_uchwyt(1), stderr=_uchwyt(2)))
    except OSError as e:
        _pisz(sys.stderr, f"agent-browser: nie uruchomię {ab}: {e.strerror or e}\n")
        return 126 if isinstance(e, PermissionError) else 127


def wylacz_podglad(ab: str, globalne: list[str], env: dict) -> bool:
    """`stream disable` z tymi samymi flagami globalnymi; liczy się odpowiedź, nie kod wyjścia (jak w nakładce bash:
    „Streaming is not enabled” znaczy, że serwera nie ma). Wyjście do pliku, nie do potoku: demon, którego to polecenie
    uruchamia, dziedziczy uchwyty polecenia, więc potok nie dostałby końca aż do śmierci demona (Windows; tak samo
    czyta wyjście Hermes). Plik tymczasowy znika sam, gdy zamknie go ostatni proces."""
    with tempfile.TemporaryFile() as plik:
        try:
            _czekaj(_popen([ab, *globalne, "--json", "stream", "disable"], env, stdin=subprocess.DEVNULL,
                           stdout=plik, stderr=subprocess.STDOUT))
        except OSError:
            return False
        plik.seek(0)
        wynik = plik.read().decode("utf-8", errors="replace")
    return '"success":true' in wynik or "Streaming is not enabled" in wynik


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ)
    ab = binarka(env)
    if not ab:
        _pisz(sys.stderr, "agent-browser: brak binarki agent-browsera (JARVO_AGENT_BROWSER_BIN z instalacji Jarva; "
                          "w obrazie /opt/jarvo/node/node_modules/agent-browser/bin)\n")
        return 127
    if env.get("AGENT_BROWSER_DAEMON"):
        return uruchom(ab, args, env)
    rozbior = rozbierz(args)
    if rozbior is None:                       # --version, --help: bez demona
        return uruchom(ab, args, env)
    globalne, polecenie, json_ = rozbior
    powod = powod_odmowy(globalne, polecenie, env)
    if powod:
        return odmowa(powod, json_)
    env_binarki = srodowisko(globalne, env)
    if (polecenie[0] if polecenie else "") in BEZ_DEMONA:
        return uruchom(ab, args, env_binarki)
    if not wylacz_podglad(ab, globalne, env_binarki):
        return odmowa("nie udało się wyłączyć serwera podglądu agent-browsera, więc polecenie nie poszło dalej", json_)
    return uruchom(ab, args, env_binarki)


# ------------------------------------------------------------------ program w bin-floty

def _zip_kodu(kod: bytes) -> bytes:
    """Zip z kodem jako __main__.py (stała data: ta sama treść daje te same bajty, drugi przebieg nic nie zmienia)."""
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as z:
        info = zipfile.ZipInfo("__main__.py", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        z.writestr(info, kod)
    return bufor.getvalue()


def _maszyna_pe(exe: Path) -> int:
    """Typ maszyny z nagłówka PE (0x8664 x64, 0xAA64 arm64): Windows arm64 bierze Pythona x64 w emulacji (I27)."""
    with open(exe, "rb") as f:
        dos = f.read(64)
        if dos[:2] != b"MZ":
            raise ValueError(f"{exe}: to nie jest program Windows")
        f.seek(int.from_bytes(dos[60:64], "little"))
        naglowek = f.read(6)
    if naglowek[:4] != b"PE\0\0":
        raise ValueError(f"{exe}: brak nagłówka PE")
    return int.from_bytes(naglowek[4:6], "little")


def launcher_windows(python: Path) -> bytes:
    """Launcher distlib z koła pip, które Python ma w ensurepip (Lib/ensurepip/_bundled/pip-*.whl), dla maszyny tego
    python.exe. Ten sam plik buduje każdy skrypt z `pip install` na Windows; przyszedł w archiwum Pythona z sumą."""
    python = Path(python)
    kola = sorted(glob.glob(str(python.parent / "Lib" / "ensurepip" / "_bundled" / "pip-*.whl")))
    if not kola:
        raise FileNotFoundError(f"{python.parent}: brak koła pip w Lib/ensurepip/_bundled (launcher programu)")
    nazwa = LAUNCHERY.get(_maszyna_pe(python))
    if nazwa is None:
        raise ValueError(f"{python}: nieznany typ maszyny (launchery: x64, arm64)")
    with zipfile.ZipFile(kola[-1]) as z:
        return z.read(f"pip/_vendor/distlib/{nazwa}")


def _sh(tekst: str) -> str:
    return "'" + tekst.replace("'", "'\\''") + "'"


def program(python: Path, kod: bytes, *, windows: bool = WINDOWS, opis: str = NAGLOWEK_SH) -> bytes:
    """Bajty samodzielnego programu z kodu Pythona: nagłówek uruchamiający `python` z ARGUMENTY_PYTHONA na tym samym
    pliku i zip z kodem jako __main__.py (Python uruchamia zip także z dopisanym z przodu nagłówkiem). Windows:
    launcher distlib i wiersz #!; macOS i Linux: dwa wiersze sh."""
    if windows:
        if not str(python).isascii() or '"' in str(python):
            raise ValueError(f"{python}: ścieżka Pythona programu musi być w ASCII (docs/NATYWNIE.md B13)")
        wiersz = f'#!"{python}" {" ".join(ARGUMENTY_PYTHONA)}\r\n'.encode("ascii")
        return launcher_windows(Path(python)) + wiersz + _zip_kodu(kod)
    naglowek = f'#!/bin/sh\n{opis}\nexec {_sh(str(python))} {" ".join(ARGUMENTY_PYTHONA)} "$0" "$@"\n'
    return naglowek.encode("utf-8") + _zip_kodu(kod)


def tresc_programu(python: Path, *, windows: bool = WINDOWS) -> bytes:
    """Bajty programu `agent-browser` dla bin-floty: ten moduł jako program (`program`)."""
    return program(python, Path(__file__).read_bytes(), windows=windows)


def tresc_chromium(chrome: str) -> bytes:
    return (f"#!/bin/sh\n# Jarvo: chrome-headless-shell z instalacji (jak /usr/local/bin/chromium w obrazie); plik pisze "
            f"instalacja Jarva\nexec {_sh(chrome)} \"$@\"\n").encode("utf-8")


def _zapisz(cel: Path, tresc: bytes, tryb: int) -> bool:
    """Zapis tylko przy innej treści, przez plik obok i os.replace. Na Windows działający program (otwarty .exe)
    da się przemianować, ale nie nadpisać: stary odsuwamy na bok i sprzątamy przy następnej instalacji."""
    if cel.is_file() and cel.read_bytes() == tresc:
        return False
    cel.parent.mkdir(parents=True, exist_ok=True)
    tmp = cel.with_name(f".{cel.name}.{os.getpid()}.nowy")
    tmp.write_bytes(tresc)
    if not WINDOWS:
        os.chmod(tmp, tryb)
    try:
        os.replace(tmp, cel)
    except PermissionError:
        if not WINDOWS or not cel.exists():
            tmp.unlink(missing_ok=True)
            raise
        os.replace(cel, cel.with_name(f".{cel.name}.{os.getpid()}.stary"))
        os.replace(tmp, cel)
    return True


def zainstaluj(bin_floty: Path, python: Path, *, chrome: str | None = None) -> list[Path]:
    """Program `agent-browser` (Windows: `agent-browser.exe`) w bin-floty dla Pythona `python` (python-build-standalone
    z instalacji, bez venvu), a na macOS i Linuksie także `chromium`, gdy znamy chrome-headless-shell. Zwraca
    zmienione pliki; drugi przebieg z tą samą treścią nic nie zmienia. Instalacja woła to przy każdym przebiegu, także
    po aktualizacji: program ma w sobie ścieżkę Pythona i kod nakładki tej wersji Jarva."""
    bin_floty = Path(bin_floty)
    for stary in bin_floty.glob(".*.stary"):           # programy odsunięte przez poprzednią instalację na Windows
        try:
            stary.unlink()
        except OSError:
            pass
    zmiany = []
    cel = bin_floty / ("agent-browser.exe" if WINDOWS else "agent-browser")
    if _zapisz(cel, tresc_programu(python), 0o755):
        zmiany.append(cel)
    if not WINDOWS and chrome:
        cel = bin_floty / "chromium"
        if _zapisz(cel, tresc_chromium(chrome), 0o755):
            zmiany.append(cel)
    return zmiany


if __name__ == "__main__":
    sys.exit(main())
