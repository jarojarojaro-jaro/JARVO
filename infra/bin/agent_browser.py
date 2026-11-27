"""agent-browser w Jarvie natywnie: demon bez serwera podglądu, bez pobierania bez sumy i bez profilu Chrome właściciela.

Odpowiednik nakładki bash z obrazu (infra/bin/agent-browser) dla instalacji natywnej na Windows, macOS i Linuksie
(docs/NATYWNIE.md C05, docs/TOOLBOX.md „agent-browser bez serwera podglądu”). Sama biblioteka standardowa: działa
Pythonem z python-build-standalone, bez venvu.

Demon agent-browsera (0.38.1 … 0.43.0) przy starcie każdej sesji otwiera na 127.0.0.1 serwer WebSocket/HTTP bez hasła: obraz
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

`snapshot --help` (i `-h`) dostaje po pomocy binarki dopisek POMOC_SNAPSHOT: snapshot jest do klikania, a treść z cenami
daje `read` (docs/TOOLBOX.md „agent-browser: czytanie treści”).

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
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

WINDOWS = os.name == "nt"

# flagi globalne jak w agent-browser 0.43.0 (cli/src/flags.rs, clean_args): z wartością i bez (to samo co w nakładce bash)
Z_WARTOSCIA = frozenset("""
    --session --restore-save --restore-check-url --restore-check-text --restore-check-fn --namespace --headers
    --executable-path --cdp --extension --init-script --enable --profile --state --proxy --proxy-bypass --args
    --user-agent -p --provider --device --session-name --color-scheme --download-path --max-output --allowed-domains
    --action-policy --confirm-actions --config --engine --input-mode --screenshot-dir --screenshot-quality
    --screenshot-format --idle-timeout --ca-cert --model --cdp-headers --capture""".split())
BEZ_WARTOSCI = frozenset("""
    --json --headed --webgpu --no-webmcp --debug --ignore-https-errors --allow-file-access --hide-scrollbars
    --auto-connect --pin-tab --no-pin-tab --no-ca-cert --annotate --content-boundaries --confirm-interactive
    --no-auto-dialog -v --verbose -q --quiet --offline --quick --fix --no-auto-connect --relaunch --use-system-ca""".split())
WPROST = frozenset({"--version", "-V", "--help", "-h"})
# polecenia, które nie łączą się z demonem (agent-browser 0.43.0, cli/src/main.rs): prosto do binarki
BEZ_DEMONA = frozenset({"", "help", "doctor", "skills", "plugin", "plugins", "session", "chat"})
KONTENER = "/opt/jarvo/node/node_modules/@agent-browser/cli-linux-*/bin/agent-browser"   # binarka w obrazie (bez manifestu)

PODGLAD = "serwer podglądu agent-browsera jest w Jarvie wyłączony (bez hasła, na 127.0.0.1)"
POBIERANIE = ("agent-browser {0} pobiera z sieci bez sumy; w Jarvie Chromium i agent-browser są z instalacji "
              "(manifest z sumami), a nową wersję daje aktualizacja Jarva")
PROFIL_WLASCICIELA = ("{0}: to przeglądarka i profile Chrome właściciela z zalogowanymi kontami, w Jarvie wyłączone; "
                      "własny profil agenta podajesz jako ścieżkę katalogu (--profile <katalog>)")
POMOC_SNAPSHOT = """
Jarvo: snapshot jest do klikania, nie do czytania treści.
  -i zostawia same kontrolki: tekst strony (ceny, opisy, tabele) znika.
  -s <selektor> działa tylko wtedy, gdy strona ma taki element. x-kom.pl nie ma <main>: wyjście jest puste,
     a na stderr „Selector 'main' did not match any element” (kod 1).
  Treść z cenami: agent-browser read <url> albo, po open, samo agent-browser read (strona po JavaScripcie).
  Refy do klikania: agent-browser snapshot -i -c.
"""

# przeglądarka agenta (silnik chrome): flagi startu, profil, widok strony
FLAGI_CHROME = ("--disable-blink-features=AutomationControlled", "--lang=pl", "--accept-lang=pl-PL,pl,en-US,en",
                "--disk-cache-size=104857600")
# przeglądarka w tle (bez --headed): ekran z paskiem zadań zamiast 800×600 przy oknie 1280×720, mysz z najeżdżaniem
# zamiast (any-pointer: none), a na Linuksie z kartą graficzną WebGL z karty zamiast SwiftShadera (jak Komputer,
# komputer/przegladarka.py); wszystko to cechy trybu bez okna
FLAGI_W_TLE = ("--screen-info={0,0 1920x1080 workAreaBottom=48}",
               "--blink-settings=primaryPointerType=4,availablePointerTypes=4,primaryHoverType=2,availableHoverTypes=2")
FLAGI_GPU_LINUX = ("--use-gl=angle", "--use-angle=gl-egl")
KATALOG_PRZEGLADARKI = "przegladarka"      # w HERMES_HOME profilu agenta: profil/, sesje/, wlasciciel, zamek
ZAJECIE_S = 60.0                           # s: profil zajęty przez sesję, której przeglądarka jeszcze startuje
WIERSZ_DRZEWA = re.compile(r'^([A-Za-z]+)(?: "((?:[^"\\]|\\.)*)")?(?: \[([^\]]*)\])?(.*)$')
BEZ_TRESCI = frozenset({"ListMarker"})
W_AKAPICIE = frozenset({"link", "emphasis", "strong", "code", "mark", "superscript", "subscript", "Abbr", "time"})
USTALENIE_MS = 200
USTALENIE_JS = ("new Promise(r=>{let t=Date.now();const o=new MutationObserver(()=>{t=Date.now()});"
                "o.observe(document,{subtree:true,childList:true,attributes:true,characterData:true});"
                "const k=Date.now()+2500;(function c(){if((document.readyState==='complete'&&Date.now()-t>="
                f"{USTALENIE_MS})||Date.now()>k){{o.disconnect();r(true)}}else setTimeout(c,50)}})()}})")

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


def pomoc_snapshot(args: list[str]) -> bool:
    """`snapshot --help` albo `snapshot -h`: polecenie liczone jak w `rozbierz` (wartość flagi nie jest poleceniem)."""
    if not any(a in ("--help", "-h") for a in args):
        return False
    _, polecenie, _ = rozbierz([a for a in args if a not in WPROST])
    return polecenie[:1] == ["snapshot"]


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


def zewnetrzna(globalne: list[str], env: dict) -> bool:
    """Sesja na cudzej przeglądarce (CDP, dostawca w chmurze, przeglądarka właściciela): bez naszych flag i profilu."""
    return (wartosc(globalne, "--cdp") is not None or wartosc(globalne, "--provider") is not None
            or wartosc(globalne, "-p") is not None or bool(env.get("AGENT_BROWSER_PROVIDER"))
            or wlaczona(globalne, "--auto-connect"))


def program_chrome(env: dict) -> str:
    """Chromium dla silnika chrome: pełny Chrome for Testing Komputera (JARVO_KOMPUTER_CHROME, gdy jest), bo
    chrome-headless-shell (CHROME_PATH) to stary tryb bez okna, który antyboty rozpoznają po samym odcisku."""
    for zmienna in ("JARVO_KOMPUTER_CHROME", "CHROME_PATH"):
        sciezka = env.get(zmienna) or ""
        if sciezka and os.path.isfile(sciezka):
            return sciezka
    return ""


def user_agent(program: str) -> str | None:
    """User-agent jak Chrome z oknem tej samej wersji (wersja z katalogu manifestu, np. …/157.0.8103.78/…): przeglądarka
    w tle przedstawia się „HeadlessChrome”, a to blokuje wiele stron od pierwszego żądania."""
    wersja = re.search(r"[/\\](\d+)\.\d+\.\d+\.\d+[/\\]", program)
    if not wersja:
        return None
    system = {"win32": "Windows NT 10.0; Win64; x64", "darwin": "Macintosh; Intel Mac OS X 10_15_7"}.get(
        sys.platform, "X11; Linux x86_64")
    return (f"Mozilla/5.0 ({system}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{wersja.group(1)}.0.0.0 "
            "Safari/537.36")


def gpu_linux() -> bool:
    """Linux: karta graficzna dostępna dla tego użytkownika (/dev/dri/renderD*, odczyt i zapis)."""
    if not sys.platform.startswith("linux"):
        return False
    return any(os.access(p, os.R_OK | os.W_OK) for p in glob.glob("/dev/dri/renderD*"))


def srodowisko(globalne: list[str], env: dict) -> dict:
    """Środowisko binarki. Silnik inny niż Lightpanda dostaje Chromium z instalacji (program_chrome), gdy nikt nie
    podał własnego (AGENT_BROWSER_EXECUTABLE_PATH, --executable-path): bez tego agent-browser szukałby Chrome w systemie
    (np. przeglądarki właściciela) albo prosił o `agent-browser install`. Przeglądarka, którą agent-browser uruchamia
    sam, dostaje FLAGI_CHROME (bez navigator.webdriver, polski język, pamięć podręczna do 100 MB), bez okna także
    FLAGI_W_TLE i na Linuksie z kartą graficzną FLAGI_GPU_LINUX, oraz user-agenta bez „HeadlessChrome”, jak Komputer
    Jarva. Od 0.41.2 agent-browser przy starcie przeglądarki pyta
    chromereleases.googleblog.com o poprawki CVE nowszego Chrome: w Jarvie wersję Chromium daje manifest instalacji,
    a nowe wydania śledzi Jarvo, więc tego zapytania nie ma (AGENT_BROWSER_NO_VERSION_CHECK)."""
    env = dict(env)
    env.setdefault("AGENT_BROWSER_NO_VERSION_CHECK", "1")
    if silnik(globalne, env) == "lightpanda":
        return env
    chrome = program_chrome(env)
    if not env.get("AGENT_BROWSER_EXECUTABLE_PATH") and wartosc(globalne, "--executable-path") is None and chrome:
        env["AGENT_BROWSER_EXECUTABLE_PATH"] = chrome
    if zewnetrzna(globalne, env):
        return env
    obecne = env.get("AGENT_BROWSER_ARGS") or env.get("AGENT_BROWSER_CHROME_FLAGS") or ""
    flagi = list(FLAGI_CHROME)
    if not (wlaczona(globalne, "--headed") or _prawda(env.get("AGENT_BROWSER_HEADED"))):
        flagi += FLAGI_W_TLE + (FLAGI_GPU_LINUX if gpu_linux() else ())
    nowe = [f for f in flagi if f.split("=", 1)[0] not in obecne]
    # user-agent flagą Chrome, nie AGENT_BROWSER_USER_AGENT: nadpisanie przez CDP zostawia pustą listę marek
    # (navigator.userAgentData.brands), a to zdradza automat tak samo jak „HeadlessChrome”
    ua = user_agent(env.get("AGENT_BROWSER_EXECUTABLE_PATH") or chrome)
    if (ua and "--user-agent" not in obecne and not env.get("AGENT_BROWSER_USER_AGENT")
            and wartosc(globalne, "--user-agent") is None):
        nowe.append(f"--user-agent={ua}")
    if nowe and wartosc(globalne, "--args") is None:
        env["AGENT_BROWSER_ARGS"] = ("\n" if "\n" in obecne else ",").join([obecne, *nowe] if obecne else nowe)
    return env


# ------------------------------------------------------------------ profil przeglądarki agenta

def _sesja(globalne: list[str], env: dict) -> str:
    nazwa = wartosc(globalne, "--session") or env.get("AGENT_BROWSER_SESSION") or "default"
    return re.sub(r"[^\w-]", "_", nazwa)[:100] or "default"


def _zyje(pid: int) -> bool:
    if pid <= 0:
        return False
    if WINDOWS:
        import ctypes
        uchwyt = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
        if uchwyt:
            ctypes.windll.kernel32.CloseHandle(uchwyt)
        return bool(uchwyt)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def profil_zajety(profil: Path) -> bool:
    """Czy Chrome działa na tym profilu: POSIX dowiązanie SingletonLock („host-pid”) z żywym procesem, Windows plik
    lockfile otwarty przez przeglądarkę."""
    if WINDOWS:
        try:
            fd = os.open(str(profil / "lockfile"), os.O_RDWR)
        except FileNotFoundError:
            return False
        except OSError:
            return True
        os.close(fd)
        return False
    try:
        cel = os.readlink(profil / "SingletonLock")
    except OSError:
        return False
    pid = cel.rpartition("-")[2]
    return pid.isdigit() and _zyje(int(pid))


class _Zamek:
    """Blokada pliku na czas decyzji o profilu (dwie sesje startujące naraz nie dostaną tego samego profilu)."""

    def __init__(self, plik: Path):
        self.plik = plik

    def __enter__(self):
        self.fd = os.open(str(self.plik), os.O_RDWR | os.O_CREAT, 0o600)
        if WINDOWS:
            import msvcrt
            koniec = time.monotonic() + 10
            while True:
                try:
                    msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > koniec:
                        raise
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        if WINDOWS:
            import msvcrt
            try:
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        os.close(self.fd)


def profil_agenta(globalne: list[str], polecenie: list[str], env: dict) -> list[str]:
    """Trwały profil przeglądarki agenta (`<HERMES_HOME>/przegladarka/profil`: logowania i ciasteczka przeżywają
    zadania i restarty) jako flagi `--profile <katalog>` do dopisania, albo [] (Lightpanda, cudza przeglądarka, własny
    profil lub stan podany wprost, brak HERMES_HOME). Profil ma naraz jedna przeglądarka, więc pierwsza sesja agenta
    go zajmuje, a druga, gdy profil jest zajęty, działa na profilu chwilowym jak dotąd. Decyzja jest stała dla sesji
    (plik `sesje/<sesja>`): każde polecenie tej sesji dostaje te same flagi, bo inne flagi agent-browser uznałby za
    nową przeglądarkę. `close` zwalnia profil."""
    dom = env.get("HERMES_HOME") or ""
    if (not dom or silnik(globalne, env) == "lightpanda" or zewnetrzna(globalne, env)
            or wartosc(globalne, "--profile") is not None or wartosc(globalne, "--state") is not None
            or any(a == "--restore" or a.startswith("--restore=") for a in globalne)
            or env.get("AGENT_BROWSER_PROFILE") or env.get("AGENT_BROWSER_STATE") or env.get("AGENT_BROWSER_RESTORE")):
        return []
    katalog = Path(dom) / KATALOG_PRZEGLADARKI
    profil, sesje = katalog / "profil", katalog / "sesje"
    sesja = _sesja(globalne, env)
    plik = sesje / sesja
    try:
        sesje.mkdir(parents=True, exist_ok=True)
        with _Zamek(katalog / "zamek"):
            decyzja = plik.read_text(encoding="utf-8").strip() if plik.is_file() else ""
            if not decyzja:
                decyzja = _decyzja(katalog, sesja)
                plik.write_text(decyzja, encoding="utf-8")
            if (polecenie[:1] == ["close"]):
                plik.unlink(missing_ok=True)
                wlasciciel = katalog / "wlasciciel"
                if decyzja == "profil" and wlasciciel.is_file() and wlasciciel.read_text(
                        encoding="utf-8").split("\n", 1)[0] == sesja:
                    wlasciciel.unlink(missing_ok=True)
    except OSError:
        return []
    return ["--profile", str(profil)] if decyzja == "profil" else []


def _decyzja(katalog: Path, sesja: str) -> str:
    """„profil”, gdy profil agenta jest wolny (żadna przeglądarka go nie trzyma i żadna inna sesja nie zajęła go przed
    chwilą, ZAJECIE_S), inaczej „chwilowy”. Przy okazji usuwa decyzje sesji starszych niż doba."""
    teraz = time.time()
    for stary in (katalog / "sesje").iterdir():
        try:
            if teraz - stary.stat().st_mtime > 86400:
                stary.unlink()
        except OSError:
            pass
    wlasciciel = katalog / "wlasciciel"
    try:
        kto, _, kiedy = wlasciciel.read_text(encoding="utf-8").partition("\n")
        swiezy = (kto != sesja and (katalog / "sesje" / kto).is_file()
                  and teraz - float(kiedy or 0) < ZAJECIE_S)
    except (OSError, ValueError):
        swiezy = False
    if swiezy or profil_zajety(katalog / "profil"):
        return "chwilowy"
    wlasciciel.write_text(f"{sesja}\n{teraz}", encoding="utf-8")
    return "profil"


# ------------------------------------------------------------------ widok strony dla Hermesa (snapshot -c)

def zwiezly_widok(drzewo: str) -> str:
    """Drzewo dostępności agent-browsera (`snapshot -c`) jako zwarta lista: jeden element na wiersz bez wcięć,
    kontrolki z refem na początku (`[e12] button "Szukaj"`), tekst strony w tej samej kolejności, a tekst i linki
    jednego akapitu w jednym wierszu. Węzły bez nazwy, refu i atrybutów (generic, list, listitem, row…) i znaczniki
    list znikają. Na stronach z dużą ilością tekstu wychodzi ok. połowa znaków przy tych samych refach i treści."""
    wiersze: list[str] = []
    akapit: list[str] = []
    poprzedni = ""

    def zamknij() -> None:
        if akapit:
            wiersze.append(" ".join(akapit))
            akapit.clear()

    for linia in drzewo.split("\n"):
        s = linia.strip()
        if not s.startswith("- "):
            if s:
                zamknij()
                wiersze.append(s)
            continue
        m = WIERSZ_DRZEWA.match(s[2:])
        if not m:
            zamknij()
            wiersze.append(s[2:])
            continue
        rola, nazwa, atrybuty, reszta = m.group(1), m.group(2), m.group(3) or "", (m.group(4) or "").strip()
        if rola in BEZ_TRESCI:
            continue
        if rola == "StaticText":
            tekst = (nazwa if nazwa is not None else reszta.lstrip(":").strip())
            if tekst.strip() and tekst.strip() != poprzedni:
                akapit.append(tekst.strip())
            poprzedni = ""
            continue
        czesci = [a.strip() for a in atrybuty.split(",") if a.strip()]
        ref = next((a[4:] for a in czesci if a.startswith("ref=")), None)
        poziom = next((a[6:] for a in czesci if a.startswith("level=")), None)
        inne = [a for a in czesci if not a.startswith(("ref=", "level="))]
        if not ref and not nazwa and not inne and not reszta:
            if rola not in W_AKAPICIE:
                zamknij()                        # akapit, punkt listy, wiersz tabeli: nowy wiersz widoku
            continue
        if rola == "heading" and poziom:
            rola = f"h{poziom}"
        opis = " ".join(x for x in ((f"[{ref}]" if ref else ""), rola, (f'"{nazwa}"' if nazwa else ""), *inne,
                                    reszta) if x)
        if rola in W_AKAPICIE and akapit and len(" ".join(akapit)) < 400:
            akapit.append(opis)
        else:
            zamknij()
            if rola in W_AKAPICIE:
                akapit.append(opis)
            else:
                wiersze.append(opis)
        poprzedni = nazwa or ""
    zamknij()
    return "\n".join(wiersze)


def _wynik_binarki(ab: str, argv: list[str], env: dict) -> tuple[int, str]:
    """Kod i wyjście polecenia binarki (plik tymczasowy, nie potok: demon dziedziczy uchwyty, jak w wylacz_podglad)."""
    with tempfile.TemporaryFile() as plik:
        try:
            kod = _czekaj(_popen([ab, *argv], env, stdin=subprocess.DEVNULL, stdout=plik, stderr=subprocess.DEVNULL))
        except OSError as e:
            return 127, json.dumps({"success": False, "data": None, "error": f"agent-browser: {e}"})
        plik.seek(0)
        return kod, plik.read().decode("utf-8", errors="replace")


def widok_strony(ab: str, globalne: list[str], env: dict) -> int:
    """`snapshot -c` z Hermesa (wynik browser_navigate i browser_snapshot): najpierw ustalenie strony (USTALENIE_JS:
    dokument wczytany i USTALENIE_MS bez zmian DOM, najwyżej 2,5 s), potem drzewo w zwartym widoku (zwiezly_widok)
    z tymi samymi refami i adresem strony w pierwszym wierszu. Błąd binarki idzie dalej bez zmian."""
    _wynik_binarki(ab, [*globalne, "eval", USTALENIE_JS], env)
    kod, wyjscie = _wynik_binarki(ab, [*globalne, "snapshot", "-c"], env)
    try:
        wynik = json.loads(wyjscie)
        drzewo = wynik["data"]["snapshot"]
        if not wynik.get("success") or not isinstance(drzewo, str):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        _pisz(sys.stdout, wyjscie)
        return kod
    adres = wynik["data"].get("origin")
    widok = zwiezly_widok(drzewo)
    wynik["data"]["snapshot"] = f"adres: {adres}\n{widok}" if isinstance(adres, str) and adres else widok
    _pisz(sys.stdout, json.dumps(wynik, ensure_ascii=False, separators=(",", ":")) + "\n")
    return kod


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


def uruchom(ab: str, args: list[str], env: dict, dopisek: str = "") -> int:
    """Polecenie dla binarki z tym samym wejściem i wyjściem: na POSIX exec, na Windows proces potomny i jego kod.
    Z dopiskiem zawsze proces potomny: dopisek idzie na wyjście po binarce."""
    argv = [ab, *args]
    try:
        if not WINDOWS and not dopisek:
            sys.stdout.flush()
            sys.stderr.flush()
            os.execve(ab, argv, env)
        kod = _czekaj(_popen(argv, env, stdin=_uchwyt(0), stdout=_uchwyt(1), stderr=_uchwyt(2)))
    except OSError as e:
        _pisz(sys.stderr, f"agent-browser: nie uruchomię {ab}: {e.strerror or e}\n")
        return 126 if isinstance(e, PermissionError) else 127
    if dopisek:
        _pisz(sys.stdout, dopisek)
    return kod


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
        return uruchom(ab, args, env, POMOC_SNAPSHOT if pomoc_snapshot(args) else "")
    globalne, polecenie, json_ = rozbior
    powod = powod_odmowy(globalne, polecenie, env)
    if powod:
        return odmowa(powod, json_)
    env_binarki = srodowisko(globalne, env)
    if (polecenie[0] if polecenie else "") in BEZ_DEMONA:
        return uruchom(ab, args, env_binarki)
    profil = profil_agenta(globalne, polecenie, env)
    globalne, args = profil + globalne, profil + args
    if not wylacz_podglad(ab, globalne, env_binarki):
        return odmowa("nie udało się wyłączyć serwera podglądu agent-browsera, więc polecenie nie poszło dalej", json_)
    if json_ and polecenie == ["snapshot", "-c"] and silnik(globalne, env) != "lightpanda":
        return widok_strony(ab, globalne, env_binarki)
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
