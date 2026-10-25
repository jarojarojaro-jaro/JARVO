"""Nakładki agent-browsera: demon bez serwera podglądu (docs/TOOLBOX.md), odmowy i środowisko binarki.

Dwie nakładki z tym samym zachowaniem tam, gdzie się pokrywają: bash z obrazu (infra/bin/agent-browser; testy tam,
gdzie jest prawdziwy bash, także na Windows) i Python dla instalacji natywnej (infra/bin/agent_browser.py, program
w bin-floty; docs/NATYWNIE.md C05), która dodatkowo odrzuca pobieranie bez sumy i profil Chrome właściciela oraz daje
silnikowi chrome Chromium z instalacji.

Atrapa agent-browsera to program z kodu Pythona zbudowany tak samo jak program w bin-floty (agent_browser.program:
na Windows launcher distlib i zip, na POSIX dwa wiersze sh i zip). Każde wywołanie zapisuje jako wiersz JSON
(argumenty, wejście, AGENT_BROWSER_EXECUTABLE_PATH) i odpowiada jak 0.38.1. Te same scenariusze przechodzą obie
nakładki, więc obraz i instalacja natywna zachowują się tak samo.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

import pytest

from conftest import REPO, load_script

NAKLADKA = REPO / "infra" / "bin" / "agent-browser"
MODUL = REPO / "infra" / "bin" / "agent_browser.py"
AB = load_script("infra/bin/agent_browser.py", "agent_browser_nakladka")
WINDOWS = os.name == "nt"
# Python bez venvu (jak python-build-standalone w instalacji): launcher venvu na Windows to osobny proces
PYTHON = Path(sys.base_prefix) / "python.exe" if WINDOWS else Path(sys.executable)

ATRAPA = r'''
import json, os, subprocess, sys, time
args = sys.argv[1:]
wejscie = sys.stdin.read() if "batch" in args else ""
with open(os.environ["LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": args, "stdin": wejscie,
                        "exe": os.environ.get("AGENT_BROWSER_EXECUTABLE_PATH")}, ensure_ascii=False) + "\n")
if "stream" in args and "disable" in args:
    stan = os.environ.get("STAN", "wylaczony")
    if stan == "wlaczony":
        print('{"success":true,"data":{"disabled":true},"error":null}')
    elif stan == "wylaczony":
        print('{"success":false,"data":null,"error":"Streaming is not enabled for this session"}')
    else:
        print('{"success":false,"data":null,"error":"Failed to connect to daemon"}')
        sys.exit(1)
    sys.exit(0)
if "demon" in args:                  # jak prawdziwe polecenie: odpięty demon żyje dłużej niż ono
    flagi = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], creationflags=flagi,
                         start_new_session=os.name != "nt", stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    open(os.environ["PIDY"], "w").write(f"{os.getpid()} {p.pid}")
if "czekaj" in args:
    open(os.environ["PIDY"], "w").write(str(os.getpid()))
    time.sleep(60)
print('{"success":true,"data":{"title":"x"},"error":null}')
sys.exit(int(os.environ.get("KOD", "0")))
'''


def zbuduj(cel: Path, kod: str) -> Path:
    try:
        cel.write_bytes(AB.program(PYTHON, kod.encode("utf-8"), opis="# atrapa agent-browsera (testy)"))
    except FileNotFoundError as e:                    # Python bez koła pip w ensurepip: brak launchera distlib
        pytest.skip(str(e))
    cel.chmod(0o755)
    return cel


@pytest.fixture
def ab(tmp_path: Path):
    binarka = zbuduj(tmp_path / ("agent-browser-bin.exe" if WINDOWS else "agent-browser-bin"), ATRAPA)
    log = tmp_path / "wywolania.jsonl"

    def uruchom(impl: str, *args: str, stan: str = "wylaczony", wejscie: str = "", env: dict | None = None,
                bez_binarki: bool = False) -> tuple[subprocess.CompletedProcess, list[dict]]:
        e = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_BROWSER_") and k != "CHROME_PATH"}
        e.update(LOG=str(log), STAN=stan, PIDY=str(tmp_path / "pidy"))
        if not bez_binarki:
            e["JARVO_AGENT_BROWSER_BIN"] = str(binarka)
        else:
            e.pop("JARVO_AGENT_BROWSER_BIN", None)
        e.update(env or {})
        argv = [str(PYTHON), "-I", "-S", str(MODUL), *args] if impl == "python" else ["bash", str(NAKLADKA), *args]
        p = subprocess.run(argv, input=wejscie, capture_output=True, text=True, encoding="utf-8", env=e, timeout=60)
        wyw = [json.loads(w) for w in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
        log.unlink(missing_ok=True)
        return p, wyw

    uruchom.binarka = binarka
    return uruchom


IMPL = [pytest.param("python", id="python"), pytest.param("bash", id="bash", marks=pytest.mark.wymaga_bash)]


def argv(wywolania: list[dict]) -> list[str]:
    return [" ".join(w["argv"]) for w in wywolania]


# ------------------------------------------------------------------ zachowanie wspólne obu nakładek

@pytest.mark.parametrize("impl", IMPL)
def test_wylacza_podglad_przed_poleceniem_z_tymi_samymi_flagami(ab, impl):
    # dokładnie tak woła Hermes (tools/browser_tool_session.py): flagi sesji, --json, polecenie
    p, wyw = ab(impl, "--session", "s1", "--engine", "lightpanda", "--json", "open", "https://example.com",
                stan="wlaczony")
    assert p.returncode == 0 and json.loads(p.stdout)["success"] is True
    assert argv(wyw) == ["--session s1 --engine lightpanda --json --json stream disable",
                         "--session s1 --engine lightpanda --json open https://example.com"]
    p, wyw = ab(impl, "--session", "s1", "--headed", "--json", "get", "title")        # już wyłączony: polecenie idzie
    assert p.returncode == 0 and argv(wyw)[0] == "--session s1 --headed --json --json stream disable"
    p, wyw = ab(impl, "open", "https://example.com", "--session", "s2", "--idle-timeout", "5000")   # flagi po poleceniu
    assert argv(wyw)[0] == "--session s2 --idle-timeout 5000 --json stream disable"


@pytest.mark.parametrize("impl", IMPL)
def test_wejscie_trafia_do_polecenia(ab, impl):
    p, wyw = ab(impl, "--session", "s1", "--json", "batch", wejscie='[["get","title"]]')
    assert p.returncode == 0 and wyw[-1]["stdin"] == '[["get","title"]]' and wyw[0]["stdin"] == ""


@pytest.mark.parametrize("impl", IMPL)
def test_nie_puszcza_polecenia_gdy_podgladu_nie_da_sie_wylaczyc(ab, impl):
    p, wyw = ab(impl, "--session", "s1", "--json", "open", "https://example.com", stan="blad")
    assert p.returncode == 1 and json.loads(p.stdout)["success"] is False
    assert "nie poszło dalej" in json.loads(p.stdout)["error"]
    assert not any("open" in w["argv"] for w in wyw)


@pytest.mark.parametrize("impl", IMPL)
@pytest.mark.parametrize("polecenie", [["stream", "enable"], ["stream", "enable", "--port", "9223"],
                                       ["dashboard", "start"], ["mcp"]])
def test_serwery_bez_hasla_odrzucone(ab, impl, polecenie):
    p, wyw = ab(impl, "--session", "s1", "--json", *polecenie)
    assert p.returncode == 1 and json.loads(p.stdout)["success"] is False and wyw == []
    p, wyw = ab(impl, *polecenie)                                                  # bez --json: komunikat na stderr
    assert p.returncode == 1 and p.stdout == "" and "agent-browser:" in p.stderr and wyw == []


@pytest.mark.parametrize("impl", IMPL)
@pytest.mark.parametrize("args", [["--version"], ["--help"], ["doctor", "--offline"], ["session", "list"], [],
                                  ["skills", "get", "core"], ["open", "--help"]])
def test_polecenia_bez_demona_bez_wylaczania(ab, impl, args):
    p, wyw = ab(impl, *args)
    assert p.returncode == 0 and argv(wyw) == [" ".join(args)]


@pytest.mark.parametrize("impl", IMPL)
def test_stream_status_i_close_tez_najpierw_wylaczaja(ab, impl):
    # pominięte uruchomiłyby demona z serwerem podglądu
    for args in (["--session", "s1", "stream", "status"], ["--session", "s1", "close"]):
        p, wyw = ab(impl, *args, stan="wlaczony")
        assert argv(wyw) == ["--session s1 --json stream disable", " ".join(args)]


@pytest.mark.wymaga_bash
def test_nakladka_bash_przepuszcza_install(ab):
    """Obraz: przeglądarka jest w obrazie, a `install` nakładka bash przepuszcza (natywnie odmowa, niżej)."""
    p, wyw = ab("bash", "install")
    assert p.returncode == 0 and argv(wyw) == ["install"]


# ------------------------------------------------------------------ nakładka natywna: odmowy i środowisko

@pytest.mark.parametrize("polecenie", [["install"], ["install", "--with-deps"], ["upgrade"],
                                       ["plugin", "add", "agent-browser-plugin-x"], ["plugins", "add", "x"]])
def test_pobieranie_bez_sumy_odrzucone(ab, polecenie):
    p, wyw = ab("python", "--json", *polecenie)
    assert p.returncode == 1 and wyw == [] and "bez" in json.loads(p.stdout)["error"]
    p, wyw = ab("python", "plugin", "list")                                         # bez pobierania: przechodzi
    assert p.returncode == 0 and argv(wyw) == ["plugin list"]


@pytest.mark.parametrize("args, env, odmowa", [
    (["profiles"], {}, True),
    (["--auto-connect", "snapshot"], {}, True),
    (["--auto-connect", "true", "snapshot"], {}, True),
    (["--auto-connect", "false", "snapshot"], {}, False),
    (["snapshot"], {"AGENT_BROWSER_AUTO_CONNECT": "1"}, True),
    (["snapshot"], {"AGENT_BROWSER_AUTO_CONNECT": "0"}, False),
    (["--profile", "Default", "open", "gmail.com"], {}, True),
    (["--profile", "Profile 1", "open", "gmail.com"], {}, True),
    (["open", "x.pl"], {"AGENT_BROWSER_PROFILE": "Default"}, True),
    (["--profile", "./profil-agenta", "open", "x.pl"], {}, False),
    (["--profile", "~/.agent/profil", "open", "x.pl"], {}, False),
    (["--profile", r"D:\dane\profil", "open", "x.pl"], {}, False),
])
def test_profil_chrome_wlasciciela_odrzucony(ab, args, env, odmowa):
    p, wyw = ab("python", "--json", *args, env=env, stan="wylaczony")
    if odmowa:
        assert p.returncode == 1 and wyw == [] and "właściciela" in json.loads(p.stdout)["error"]
    else:
        assert p.returncode == 0 and argv(wyw)[-1].endswith(" ".join(args[-2:]))


def test_silnik_chrome_dostaje_chromium_z_instalacji(ab, tmp_path):
    """Windows (silnik chrome) i zapas Hermesa dla zrzutów: AGENT_BROWSER_EXECUTABLE_PATH = CHROME_PATH dla obu
    wywołań (demon startuje już przy `stream disable`); Lightpanda nigdy; ustawienie właściciela i flaga wygrywają."""
    chrome = tmp_path / "chrome-headless-shell.exe"
    chrome.write_bytes(b"x")
    _, wyw = ab("python", "--session", "s", "--engine", "chrome", "--json", "open", "x.pl", env={"CHROME_PATH": str(chrome)})
    assert [w["exe"] for w in wyw] == [str(chrome), str(chrome)]
    _, wyw = ab("python", "--session", "s", "open", "x.pl", env={"CHROME_PATH": str(chrome)})       # auto = Chrome
    assert {w["exe"] for w in wyw} == {str(chrome)}
    for args, env in ((["--engine", "lightpanda", "open", "x.pl"], {}),
                      (["open", "x.pl"], {"AGENT_BROWSER_ENGINE": "lightpanda"}),
                      (["--executable-path", "C:/inny/chrome.exe", "open", "x.pl"], {}),
                      (["open", "x.pl"], {"CHROME_PATH": str(tmp_path / "nie-ma.exe")})):
        _, wyw = ab("python", *args, env={"CHROME_PATH": str(chrome), **env})
        assert {w["exe"] for w in wyw} == {None}, args
    _, wyw = ab("python", "open", "x.pl", env={"CHROME_PATH": str(chrome), "AGENT_BROWSER_EXECUTABLE_PATH": "C:/moj"})
    assert {w["exe"] for w in wyw} == {"C:/moj"}


def test_kod_wyjscia_i_brak_binarki(ab):
    p, _ = ab("python", "--json", "open", "x.pl", env={"KOD": "5"})
    assert p.returncode == 5
    p, wyw = ab("python", "--json", "open", "x.pl", bez_binarki=True)
    assert p.returncode == 127 and "JARVO_AGENT_BROWSER_BIN" in p.stderr and wyw == []


def _zyje(pid: int) -> bool:
    if not WINDOWS:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000 | 0x00100000, False, pid)       # PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
    if not h:
        return False
    try:
        return k32.WaitForSingleObject(h, 0) == 0x102            # WAIT_TIMEOUT: proces działa
    finally:
        k32.CloseHandle(h)


def _zabij(pid: int) -> None:
    if WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


@pytest.mark.windows_only
def test_zabicie_nakladki_zabija_polecenie_a_demon_zyje(ab, tmp_path):
    """Windows: polecenie siedzi w zadaniu nakładki (KILL_ON_JOB_CLOSE), więc limit czasu Hermesa, który zabija
    nakładkę, zabija też polecenie. Demon, którego polecenie odpina, wychodzi z zadania i żyje dalej."""
    pidy = tmp_path / "pidy"
    p, _ = ab("python", "--session", "s", "--json", "open", "x.pl", "demon")
    assert p.returncode == 0
    polecenie, demon = map(int, pidy.read_text(encoding="utf-8").split())
    try:
        time.sleep(0.5)
        assert not _zyje(polecenie) and _zyje(demon)
    finally:
        _zabij(demon)
    pidy.unlink()
    e = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_BROWSER_")}
    e.update(JARVO_AGENT_BROWSER_BIN=str(ab.binarka), LOG=str(tmp_path / "log"), STAN="wylaczony", PIDY=str(pidy))
    nakladka = subprocess.Popen([str(PYTHON), "-I", "-S", str(MODUL), "--session", "s", "open", "x.pl", "czekaj"],
                                env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(200):
            if pidy.exists() and pidy.read_text(encoding="utf-8").strip():
                break
            time.sleep(0.05)
        polecenie = int(pidy.read_text(encoding="utf-8"))
        assert _zyje(polecenie)
        nakladka.kill()
        nakladka.wait(10)
        for _ in range(100):
            if not _zyje(polecenie):
                break
            time.sleep(0.05)
        assert not _zyje(polecenie)
    finally:
        nakladka.kill()
        _zabij(polecenie)


# ------------------------------------------------------------------ program w bin-floty

def test_program_w_bin_floty_przekazuje_argumenty_bez_zmian(ab, tmp_path):
    """`zainstaluj` daje program, który Hermes znajdzie przez shutil.which (Windows: .exe, nie .cmd: cmd.exe rozbiłby
    adres z „&”, rozwinąłby %…% i uciął skrypt eval na nowym wierszu). Drugi przebieg niczego nie zmienia."""
    bin_floty = tmp_path / "bin-floty"
    zmiany = AB.zainstaluj(bin_floty, PYTHON)
    program = bin_floty / ("agent-browser.exe" if WINDOWS else "agent-browser")
    assert zmiany == [program] and AB.zainstaluj(bin_floty, PYTHON) == []
    sciezka = os.pathsep.join([str(bin_floty), os.environ.get("PATH", "")])
    assert Path(shutil.which("agent-browser", path=sciezka)).resolve() == program.resolve()
    e = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_BROWSER_") and k != "CHROME_PATH"}
    log = tmp_path / "log.jsonl"
    e.update(JARVO_AGENT_BROWSER_BIN=str(ab.binarka), LOG=str(log), STAN="wlaczony", PIDY=str(tmp_path / "p"))
    trudne = ["open", "https://x.pl/?a=1&b=%20%PATH%", 'z "cudzysłowem"', "Zażółć gęślą jaźń", "a\nb", "", "^|<>"]
    kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}
    p = subprocess.run([str(program), "--session", "s", "--json", *trudne], env=e, capture_output=True, text=True,
                       encoding="utf-8", timeout=60, **kw)
    assert p.returncode == 0, p.stderr
    wyw = [json.loads(w) for w in log.read_text(encoding="utf-8").splitlines()]
    assert wyw[0]["argv"] == ["--session", "s", "--json", "--json", "stream", "disable"]
    assert wyw[1]["argv"] == ["--session", "s", "--json", *trudne]
    p = subprocess.run([str(program), "install"], env=e, capture_output=True, text=True, encoding="utf-8", timeout=60,
                       **kw)
    assert p.returncode == 1 and "bez sumy" in p.stderr                    # komunikat w UTF-8 z polskimi znakami


def test_program_windows_i_posix_z_tym_modulem(tmp_path):
    """Windows: launcher distlib z koła pip Pythona, wiersz #! z Pythonem w cudzysłowie i flagami izolacji, zip z tym
    modułem; POSIX: sh z exec Pythona na tym samym pliku. Ścieżka Pythona z polskimi znakami na Windows: błąd (B13)."""
    import io
    import zipfile
    posix = AB.tresc_programu(PurePosixPath("/home/o la/.jarvo/program/narzedzia/python313/3.13.17/bin/python3"),
                              windows=False)
    naglowek, _, _ = posix.partition(b"PK\x03\x04")
    assert naglowek.decode("utf-8").splitlines()[:3] == [
        "#!/bin/sh", AB.NAGLOWEK_SH,
        "exec '/home/o la/.jarvo/program/narzedzia/python313/3.13.17/bin/python3' -I -S -X utf8 \"$0\" \"$@\""]
    assert zipfile.ZipFile(io.BytesIO(posix)).read("__main__.py") == MODUL.read_bytes()
    with pytest.raises(ValueError):
        AB.tresc_programu(Path("C:/Users/Michał/python.exe"), windows=True)
    if WINDOWS:
        exe = AB.tresc_programu(PYTHON, windows=True)
        assert exe[:2] == b"MZ" and f'#!"{PYTHON}" -I -S -X utf8\r\n'.encode() in exe
        assert zipfile.ZipFile(io.BytesIO(exe)).read("__main__.py") == MODUL.read_bytes()


@pytest.mark.posix_only
def test_chromium_w_bin_floty_na_posix(tmp_path):
    """macOS i Linux: `chromium` w bin-floty uruchamia chrome-headless-shell z instalacji (jak /usr/local/bin/chromium
    w obrazie): Hermes widzi Chromium do zapasu Lightpandy (zrzuty), a skrypty mogą wołać `chromium`."""
    chrome = tmp_path / "chs" / "chrome-headless-shell"
    chrome.parent.mkdir()
    chrome.write_text("#!/bin/sh\necho chrome \"$@\"\n", encoding="utf-8")
    chrome.chmod(0o755)
    bin_floty = tmp_path / "bin"
    zmiany = AB.zainstaluj(bin_floty, PYTHON, chrome=str(chrome))
    assert bin_floty / "chromium" in zmiany and os.access(bin_floty / "chromium", os.X_OK)
    p = subprocess.run([str(bin_floty / "chromium"), "--version"], capture_output=True, text=True, timeout=30)
    assert p.stdout.strip() == "chrome --version"
    assert AB.zainstaluj(bin_floty, PYTHON, chrome=str(chrome)) == []


def test_hermes_znajduje_nakladke_pierwsza():
    """Obraz: nakładka bash pierwsza w PATH; natywnie bin-floty jest pierwszy w PATH procesów Jarva."""
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chmod=0755 infra/bin/ /opt/jarvo/bin/" in docker
    assert 'ENV PATH="/opt/jarvo/bin:' in docker                 # przed node_modules/.bin z natywną binarką
    assert "ln -sf /opt/jarvo/bin/agent-browser /usr/local/bin/agent-browser" in docker
    assert wykonywalny(NAKLADKA)
    sys.path.insert(0, str(REPO))
    from jarvo import sciezki, srodowisko
    u = sciezki.uklad({"JARVO_ROOT": str(REPO / "build" / "proba-nie-istnieje")})
    assert srodowisko.srodowisko(u, {"PATH": "/usr/bin"}, biez={}, narz={})["PATH"].split(os.pathsep)[0] == \
        str(u.bin_floty)


def wykonywalny(plik: Path) -> bool:
    """Bit wykonywania: na POSIX z systemu plików; Windows go nie ma, więc tryb pliku zapisany w gicie (100755)."""
    if os.name != "nt":
        return bool(plik.stat().st_mode & 0o111)
    r = subprocess.run(["git", "-C", str(REPO), "ls-files", "-s", "--", plik.relative_to(REPO).as_posix()],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode or not r.stdout:
        pytest.skip("bez repozytorium gita nie ma trybu pliku na Windows")
    return r.stdout.startswith("100755 ")
