"""Ręce na ekranie właściciela (docs/KOMPUTER.md K6, docs/NATYWNIE.md J14, J15): zgoda, bramka, sterownik, CLI.

Prawdziwego cua-driver nie uruchamiamy (dotknąłby ekranu): sterownik to atrapa w Pythonie, która zapisuje argumenty
i otoczenie, mówi „daemon listening on” i kończy się przy końcu stdin, a w trybie `mcp` odpowiada jak serwer MCP.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS

sys.path.insert(0, str(REPO / "komputer"))
import rece  # noqa: E402
from rece import aplikacje, bramka, dziennik, procesy, sterownik, zgoda  # noqa: E402

from jarvo import rece as cli_rece  # noqa: E402
from jarvo import sciezki  # noqa: E402

PLATFORMA = "windows-x64" if WINDOWS else "linux-x64"
UZYTKOWNIK = "uid:testy"
PROFIL_OK = """# profil rąk w testach
computer_use:
  permission_mode: bounded
  capability_manifest: "{manifest}"
approvals:
  mode: manual
  cron_mode: deny
command_allowlist: []
"""
ATRAPA = r'''
import json, os, sys
from pathlib import Path
tu = Path(__file__).parent
argv = sys.argv[1:]
if argv[:1] == ["serve"]:
    (tu / "serve.json").write_text(json.dumps({"argv": argv, "env": dict(os.environ)}), encoding="utf-8")
    gniazdo = argv[argv.index("--socket") + 1]
    print("Cua Driver daemon listening on " + gniazdo, file=sys.stderr, flush=True)
    sys.stdin.buffer.read()
    (tu / "serve-koniec.txt").write_text("eof", encoding="utf-8")
    sys.exit(0)
if argv[:1] == ["mcp"]:
    narzedzia = ["click", "type_text", "get_desktop_state", "page", "kill_app", "launch_app", "set_config",
                 "get_window_state", "run_script"]
    for wiersz in sys.stdin.buffer:
        w = json.loads(wiersz)
        with open(tu / "mcp.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(w) + "\n")
        if "id" not in w:
            continue
        if w["method"] == "initialize":
            r = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "atrapa"},
                 "instructions": "atrapa"}
        elif w["method"] == "tools/list":
            r = {"tools": [{"name": n, "inputSchema": {"type": "object"}} for n in narzedzia]}
        elif w["method"] == "tools/call":
            r = {"content": [{"type": "text", "text": "zrobione " + w["params"]["name"] + " sk-ant-api03-" + "A" * 30}],
                 "isError": False, "structuredContent": {"ok": True, "okno": "klucz ghp_" + "b" * 36}}
        else:
            r = {}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": w["id"], "result": r}) + "\n")
        sys.stdout.flush()
    sys.exit(0)
if argv[:1] == ["stop"]:
    sys.exit(0)
print("atrapa: nieznane " + " ".join(argv), file=sys.stderr)
sys.exit(2)
'''


# ---------------------------------------------------------------- pomocnicze

def gniazdo(tmp_path: Path) -> str:
    """Nazwa jak u Hermesa (hermes-cua-<token>, <tmp>/hc-<token>.sock), stała dla jednego testu. Na POSIX w katalogu
    tymczasowym systemu, bo tmp_path na macOS przekracza limit ścieżki gniazda (ok. 100 bajtów)."""
    token = hashlib.sha1(str(tmp_path).encode("utf-8")).hexdigest()[:12]
    return rf"\\.\pipe\hermes-cua-{token}" if WINDOWS else os.path.join(tempfile.gettempdir(), f"hc-{token}.sock")


def notatnik() -> zgoda.Aplikacja:
    return zgoda.Aplikacja("notatnik", {"bundle_id": r"C:\Windows\System32\notepad.exe"})


class Zegar:
    def __init__(self):
        self.przesuniecie = 0.0

    def __call__(self) -> float:
        return time.time() + self.przesuniecie


@pytest.fixture
def instalacja(tmp_path):
    stan, dane, program = tmp_path / "stan", tmp_path / "dane", tmp_path / "program"
    for k in (stan, dane / "profiles" / "jarvo-operator", program):
        k.mkdir(parents=True)
    pliki = zgoda.Pliki(stan)
    (dane / "profiles" / "jarvo-operator" / "config.yaml").write_text(
        PROFIL_OK.format(manifest=str(pliki.manifest).replace("\\", "\\\\")), encoding="utf-8")
    atrapa = tmp_path / "atrapa" / "cua-driver.py"
    atrapa.parent.mkdir()
    atrapa.write_text(ATRAPA, encoding="utf-8")
    zegar = Zegar()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "JARVO_", "CUA_"))}
    env.update({"OPENAI_API_KEY": "sk-proj-tajne", "DISPLAY": ":0", "CUA_DRIVER_RS_MCP_HTTP_PORT": "19210",
                "CUA_DRIVER_DANGEROUSLY_BYPASS_APPROVALS": "1",
                "PATH": os.pathsep.join([str(program / "bin-floty"), env.get("PATH", "")])})
    st = sterownik.Sterownik(program=atrapa, przedrostek=(sys.executable, "-I", str(atrapa)), sha256="atrapa")
    k = bramka.Kontekst(env=env, pliki=pliki, platforma=PLATFORMA, program_dir=program, dane=dane, teraz=zegar,
                        daj_sterownik=lambda: st, podwyzszone=lambda: False, uzytkownik=UZYTKOWNIK, takt=0.05,
                        bledy=io.StringIO(), rodzic=os.getpid(), zasady=bramka.wczytaj_zasady())
    return {"k": k, "pliki": pliki, "zegar": zegar, "atrapa": atrapa, "dane": dane, "tmp": tmp_path}


def daj_zgode(inst, sekundy: int = 1800, aplikacje_=None) -> zgoda.Zgoda:
    return zgoda.utworz(inst["pliki"], aplikacje_ or [notatnik()], sekundy, platforma=PLATFORMA,
                        teraz=inst["zegar"](), uzytkownik=UZYTKOWNIK)


def argv_serve(inst, g: str, **zmiany) -> list[str]:
    argv = ["--embedded", "--socket", g, "--no-permissions-gate", "--permission-mode", "bounded",
            "--capability-manifest", str(inst["pliki"].manifest), "--approve-capability-manifest", "--no-overlay"]
    for stara, nowa in zmiany.items():
        argv = [nowa if a == stara.replace("_", "-") else a for a in argv]
    return argv


def czekaj(warunek, limit: float = 10.0) -> bool:
    koniec = time.monotonic() + limit
    while time.monotonic() < koniec:
        if warunek():
            return True
        time.sleep(0.02)
    return False


def uruchom_serve(inst, g: str):
    wynik: dict = {}
    w = threading.Thread(target=lambda: wynik.setdefault("kod", bramka.serve(argv_serve(inst, g), inst["k"])),
                         daemon=True)
    w.start()
    rejestr = inst["k"].rejestr
    assert czekaj(lambda: (rejestr.dla_gniazda(g) or {}).get("gotowy")), inst["k"].bledy.getvalue()
    return w, wynik


def wpisy_dziennika(inst) -> list[dict]:
    return dziennik.ostatnie(inst["pliki"].dziennik, 200)


# ---------------------------------------------------------------- zgoda i manifest

def test_czas_zgody():
    assert zgoda.czas("30m") == 1800 and zgoda.czas("1h") == 3600 and zgoda.czas("90s") == 90
    assert zgoda.czas("45") == 2700 and zgoda.czas("8h") == 8 * 3600 and zgoda.czas(" 2 godz ") == 7200
    for zly in ("0m", "30s", "9h", "abc", "", "-5m", "1d"):
        with pytest.raises(ValueError):
            zgoda.czas(zly)


def test_zgoda_podpisana_i_wazna(instalacja):
    z = daj_zgode(instalacja)
    w = zgoda.wczytaj(instalacja["pliki"], platforma=PLATFORMA, teraz=instalacja["zegar"](), uzytkownik=UZYTKOWNIK)
    assert w == z and w.nazwy() == ["notatnik"] and 1790 <= w.pozostalo(instalacja["zegar"]()) <= 1800
    dane = json.loads(instalacja["pliki"].zgoda.read_text(encoding="utf-8"))
    assert len(dane["podpis"]) == 64 and dane["sterownik"] == rece.WERSJA and dane["profil"] == "jarvo-operator"
    assert bytes.fromhex(instalacja["pliki"].klucz.read_text(encoding="ascii").strip()).__len__() == 32


@pytest.mark.parametrize("pole, wartosc", [("wygasa", 2_000_000_000), ("profil", "jarvo-web"),
                                           ("aplikacje", [{"nazwa": "cmd", "tozsamosc": {"bundle_id": "C:\\cmd.exe"}}]),
                                           ("narzedzia", ["click", "page"])])
def test_zmieniona_zgoda_to_odmowa(instalacja, pole, wartosc):
    daj_zgode(instalacja)
    p = instalacja["pliki"].zgoda
    dane = json.loads(p.read_text(encoding="utf-8"))
    dane[pole] = wartosc
    p.write_text(json.dumps(dane), encoding="utf-8")
    with pytest.raises(zgoda.BladZgody) as e:
        zgoda.wczytaj(instalacja["pliki"], platforma=PLATFORMA, uzytkownik=UZYTKOWNIK)
    assert e.value.kod == "zgoda_zmieniona"


def test_zgoda_wygasa_inna_platforma_i_konto(instalacja):
    daj_zgode(instalacja, sekundy=60)
    pliki = instalacja["pliki"]
    with pytest.raises(zgoda.BladZgody) as e:
        zgoda.wczytaj(pliki, platforma=PLATFORMA, teraz=time.time() + 61, uzytkownik=UZYTKOWNIK)
    assert e.value.kod == "rece_wygasly"
    with pytest.raises(zgoda.BladZgody) as e:
        zgoda.wczytaj(pliki, platforma="macos-arm64", uzytkownik=UZYTKOWNIK)
    assert e.value.kod == "inna_platforma"
    with pytest.raises(zgoda.BladZgody) as e:
        zgoda.wczytaj(pliki, platforma=PLATFORMA, uzytkownik="uid:ktos-inny")
    assert e.value.kod == "inny_uzytkownik"


def test_zmieniony_manifest_i_klucz_to_odmowa(instalacja):
    daj_zgode(instalacja)
    pliki = instalacja["pliki"]
    pliki.manifest.write_text(pliki.manifest.read_text(encoding="utf-8").replace('"1800s"', '"86400s"'),
                              encoding="utf-8")
    with pytest.raises(zgoda.BladZgody) as e:
        zgoda.wczytaj(pliki, platforma=PLATFORMA, uzytkownik=UZYTKOWNIK)
    assert e.value.kod == "zgoda_zmieniona"
    daj_zgode(instalacja)
    pliki.klucz.write_text(os.urandom(32).hex(), encoding="ascii")          # inny klucz: stary podpis nie pasuje
    with pytest.raises(zgoda.BladZgody) as e:
        zgoda.wczytaj(pliki, platforma=PLATFORMA, uzytkownik=UZYTKOWNIK)
    assert e.value.kod == "zgoda_zmieniona"


def test_odwolanie_i_brak_zgody(instalacja):
    pliki = instalacja["pliki"]
    with pytest.raises(zgoda.BladZgody) as e:
        zgoda.wczytaj(pliki, platforma=PLATFORMA, uzytkownik=UZYTKOWNIK)
    assert e.value.kod == "rece_wylaczone"
    daj_zgode(instalacja)
    assert zgoda.odwolaj(pliki) is True and not pliki.zgoda.exists()
    assert "version: 0" in pliki.manifest.read_text(encoding="utf-8")
    with pytest.raises(zgoda.BladZgody) as e:
        zgoda.wczytaj(pliki, platforma=PLATFORMA, uzytkownik=UZYTKOWNIK)
    assert e.value.kod == "rece_wylaczone"
    assert zgoda.odwolaj(pliki) is False


def test_manifest_sterownika_bounded():
    linux = zgoda.Aplikacja("gedit", {"executable": "/usr/bin/gedit"})
    tekst = zgoda.manifest_sterownika((notatnik(), linux), 1234, 600)
    assert tekst.startswith("#")
    m = json.loads(tekst.split("\n", 1)[1])
    assert m["version"] == 3 and "mode" not in m                       # wersja 3 nie deklaruje trybu
    assert m["expires_after"] == "1234s" and m["idle_timeout"] == "600s"
    assert m["resources"]["desktop"] == {"display": False}             # bez pełnego ekranu właściciela
    assert m["resources"]["apps"] == [
        {"bundle_id": r"C:\Windows\System32\notepad.exe", "launch": True, "windows": "all", "terminate": "deny"},
        {"executable": "/usr/bin/gedit", "launch": True, "windows": "all", "terminate": "deny"}]
    allow, deny = set(m["allow"]["tools"]), set(m["deny"]["tools"])
    assert allow == set(rece.NARZEDZIA) and not allow & deny
    assert {"get_desktop_state", "page", "run_script", "clipboard_read", "kill_app", "browser_navigate"} <= deny
    assert m["resources"]["driver_configuration"]["changes"] == [{"key": "max_image_dimension", "value": 1456}]
    krotki = json.loads(zgoda.manifest_sterownika((notatnik(),), 30, 600).split("\n", 1)[1])
    assert krotki["idle_timeout"] == "30s"                             # bezczynność nie dłuższa niż czas


# ---------------------------------------------------------------- aplikacje

def test_aplikacje_windows():
    istnieje = {r"C:\Windows\System32\notepad.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"}.__contains__
    which = {"notepad": r"C:\Windows\System32\notepad.exe"}.get
    lista = aplikacje.rozpoznaj(["notatnik", "chrome", "notepad"], system="win32", which=which, istnieje=istnieje,
                                app_paths={"chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe"}.get)
    assert [(a.nazwa, a.tozsamosc) for a in lista] == [
        ("notatnik", {"bundle_id": r"C:\Windows\System32\notepad.exe"}),
        ("chrome", {"bundle_id": r"C:\Program Files\Google\Chrome\Application\chrome.exe"})]   # bez powtórki
    for zla, czesc in [("cmd", "nie obejmują"), (r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                                                  "nie obejmują"), ("explorer", "nie obejmują"),
                       ("regedit", "nie obejmują"), ("keepass", "nie obejmują"), ("nieznany", "nie znalazłem"),
                       (r"C:\Users\Ja\AppData\Local\Microsoft\WindowsApps\mspaint.exe", "Sklepu"),
                       (r"\\?\C:\x.exe", "pełna ścieżka")]:
        with pytest.raises(aplikacje.BladAplikacji, match=czesc):
            aplikacje.rozpoznaj([zla], system="win32", which=lambda n: None, app_paths=lambda n: None,
                                istnieje=lambda p: True)


def test_aplikacje_macos(tmp_path):
    app = tmp_path / "TextEdit.app" / "Contents"
    app.mkdir(parents=True)
    (app / "Info.plist").write_bytes(b"plist")
    czytaj = lambda p: {"CFBundleIdentifier": "com.apple.TextEdit"}  # noqa: E731
    lista = aplikacje.rozpoznaj(["TextEdit", "com.apple.Safari"], system="darwin", czytaj_plist=czytaj,
                                katalogi_macos=(str(tmp_path),))
    assert [a.tozsamosc for a in lista] == [{"bundle_id": "com.apple.TextEdit"}, {"bundle_id": "com.apple.Safari"}]
    for zla in ("com.apple.Terminal", "Terminal", "com.googlecode.iterm2", "com.trycua.driver", "Keychain Access"):
        with pytest.raises(aplikacje.BladAplikacji):
            aplikacje.rozpoznaj([zla], system="darwin", czytaj_plist=czytaj, katalogi_macos=(str(tmp_path),))


def test_aplikacje_linux(tmp_path):
    program = tmp_path / "gedit"
    program.write_bytes(b"\x7fELF" + b"\0" * 60)
    skrypt = tmp_path / "firefox"
    skrypt.write_text("#!/bin/sh\nexec /usr/lib/firefox/firefox \"$@\"\n", encoding="utf-8")
    which = {"gedit": str(program), "firefox": str(skrypt), "gnome-terminal": str(program)}.get
    assert aplikacje.rozpoznaj(["gedit"], system="linux", which=which)[0].tozsamosc == {
        "executable": os.path.realpath(program)}
    with pytest.raises(aplikacje.BladAplikacji, match="skrypt startowy"):
        aplikacje.rozpoznaj(["firefox"], system="linux", which=which)
    with pytest.raises(aplikacje.BladAplikacji, match="nie obejmują"):
        aplikacje.rozpoznaj(["gnome-terminal"], system="linux", which=which)


def test_pasuje_do_zgody():
    lista = (notatnik(), zgoda.Aplikacja("TextEdit", {"bundle_id": "com.apple.TextEdit"}))
    assert aplikacje.pasuje(lista, "notepad") and aplikacje.pasuje(lista, "Notatnik")
    assert aplikacje.pasuje(lista, r"C:\WINDOWS\system32\NOTEPAD.EXE") and aplikacje.pasuje(lista, None, "com.apple.textedit")
    assert not aplikacje.pasuje(lista, "calc") and not aplikacje.pasuje(lista, None, None)
    safari = (zgoda.Aplikacja("com.apple.Safari", {"bundle_id": "com.apple.Safari"}),)
    assert aplikacje.pasuje(safari, "Safari") and not aplikacje.pasuje(safari, "Mail")


# ---------------------------------------------------------------- profil

def test_stale_zgody_i_approvals_off():
    assert bramka.stale_zgody("command_allowlist:\n  - \"cua:click:background\"\n  # \"cua:type:foreground\"\n"
                              "  - cua:key:foreground  # komentarz\n") == ["cua:click:background", "cua:key:foreground"]
    assert bramka.stale_zgody("command_allowlist: []\n# cua:click:background\n") == []
    assert bramka.zgody_wylaczone("approvals:\n  mode: off\n") and bramka.zgody_wylaczone("approvals:\n  mode: \"off\"\n")
    assert not bramka.zgody_wylaczone("approvals:\n  mode: manual\ntts:\n  mode: off\n")


# ---------------------------------------------------------------- bramka: serve

def test_dla_rak():
    assert bramka.dla_rak(["serve", "--embedded"]) and bramka.dla_rak(["stop", "--socket", "x"])
    assert bramka.dla_rak(["call", "click", "{}"]) and bramka.dla_rak(["mcp", "--embedded", "--socket", "x"])
    assert bramka.dla_rak(["status", "--socket=x"])
    assert not bramka.dla_rak(["mcp"]) and not bramka.dla_rak(["status"]) and not bramka.dla_rak(["manifest"])
    assert not bramka.dla_rak([])


def test_argv_serve_macos_przez_launchservices(tmp_path):
    """macOS: demon startuje jako CuaDriver.app (open -n -g -a), żeby zgody TCC dotyczyły com.trycua.driver."""
    st = sterownik.Sterownik(program=Path("/Applications/CuaDriver.app/Contents/MacOS/cua-driver"),
                             przedrostek=("/Applications/CuaDriver.app/Contents/MacOS/cua-driver",), sha256="x",
                             aplikacja=Path("/Applications/CuaDriver.app"))
    argv = bramka.argv_serve(st, "/tmp/hc-1.sock", tmp_path / "m.yaml", tmp_path / "p.pid",
                             {"--no-overlay": True}, macos=True)
    assert argv[:6] == ["/usr/bin/open", "-n", "-g", "-a", str(Path("/Applications/CuaDriver.app")), "--args"]
    assert argv[6:9] == ["serve", "--embedded", "--socket"] and argv[-1] == "--no-overlay"
    assert bramka.argv_serve(st, "/tmp/hc-1.sock", tmp_path / "m.yaml", tmp_path / "p.pid", {}, macos=False)[0] == \
        "/Applications/CuaDriver.app/Contents/MacOS/cua-driver"


def test_status_bez_gniazda_i_nieznany_czasownik(instalacja):
    k = instalacja["k"]
    assert bramka.obsluz(["status", "--socket", gniazdo(instalacja["tmp"])], k) == 1
    assert bramka.obsluz(["update", "--apply"], k) == bramka.KOD_ODMOWY
    assert bramka.obsluz(["serve", "--dangerously-bypass-approvals"], k) == bramka.KOD_ODMOWY


def test_call_wylaczone():
    bledy = io.StringIO()
    k = bramka.Kontekst(env={}, pliki=zgoda.Pliki(Path("nie-ma")), platforma=PLATFORMA, program_dir=Path("x"),
                        dane=Path("x"), bledy=bledy)
    assert bramka.obsluz(["call", "click", "{}", "--socket", "x"], k) == bramka.KOD_ODMOWY
    assert "wyłączone" in bledy.getvalue()


def test_serve_bez_zgody_odmawia(instalacja):
    k = instalacja["k"]
    assert bramka.serve(argv_serve(instalacja, gniazdo(instalacja["tmp"])), k) == bramka.KOD_BRAK
    assert "wyłączone" in k.bledy.getvalue()
    assert not (instalacja["atrapa"].parent / "serve.json").exists()
    assert wpisy_dziennika(instalacja)[-1]["kod"] == "rece_wylaczone"


@pytest.mark.parametrize("zmiana, kod", [
    ({"bounded": "unrestricted"}, "tryb"),
    ({"bounded": "standard"}, "tryb"),
    ({"--approve-capability-manifest": "--dangerously-bypass-approvals"}, "flaga"),
    ({"--no-overlay": "--grant"}, "flaga"),
    ({"--no-overlay": "--experimental-history"}, "flaga"),
])
def test_serve_odmawia_trybu_bez_granic(instalacja, zmiana, kod):
    daj_zgode(instalacja)
    argv = argv_serve(instalacja, gniazdo(instalacja["tmp"]))
    argv = [zmiana.get(a, a) for a in argv]
    assert bramka.serve(argv, instalacja["k"]) == bramka.KOD_ODMOWY
    assert wpisy_dziennika(instalacja)[-1]["kod"] == kod
    assert not (instalacja["atrapa"].parent / "serve.json").exists()


def test_serve_odmawia_innego_manifestu_i_gniazda(instalacja, tmp_path):
    daj_zgode(instalacja)
    obcy = tmp_path / "obcy.yaml"
    obcy.write_text(instalacja["pliki"].manifest.read_text(encoding="utf-8"), encoding="utf-8")
    argv = argv_serve(instalacja, gniazdo(instalacja["tmp"]))
    argv[argv.index("--capability-manifest") + 1] = str(obcy)
    assert bramka.serve(argv, instalacja["k"]) == bramka.KOD_ODMOWY
    argv = argv_serve(instalacja, r"C:\Windows\zly" if WINDOWS else "wzgledne.sock")
    assert bramka.serve(argv, instalacja["k"]) == bramka.KOD_ODMOWY
    assert [w["kod"] for w in wpisy_dziennika(instalacja)[-2:]] == ["manifest", "gniazdo"]


def test_serve_odmawia_stalych_zgod_profilu_i_administratora(instalacja):
    daj_zgode(instalacja)
    k = instalacja["k"]
    plik = instalacja["dane"] / "profiles" / "jarvo-operator" / "config.yaml"
    dobry = plik.read_text(encoding="utf-8")
    plik.write_text(dobry.replace("command_allowlist: []", "command_allowlist:\n  - \"cua:click:foreground\""),
                    encoding="utf-8")
    assert bramka.serve(argv_serve(instalacja, gniazdo(instalacja["tmp"])), k) == bramka.KOD_BRAK
    assert "stałe zgody cua:click:foreground" in k.bledy.getvalue()
    plik.write_text(dobry.replace("mode: manual", "mode: off"), encoding="utf-8")
    assert bramka.serve(argv_serve(instalacja, gniazdo(instalacja["tmp"])), k) == bramka.KOD_BRAK
    plik.write_text(dobry, encoding="utf-8")
    k.podwyzszone = lambda: True
    assert bramka.serve(argv_serve(instalacja, gniazdo(instalacja["tmp"])), k) == bramka.KOD_BRAK
    assert "administratora" in k.bledy.getvalue()
    k.podwyzszone = lambda: False
    k.env["HERMES_HOME"] = str(instalacja["dane"] / "profiles" / "jarvo-web")
    (instalacja["dane"] / "profiles" / "jarvo-web").mkdir()
    assert bramka.serve(argv_serve(instalacja, gniazdo(instalacja["tmp"])), k) == bramka.KOD_BRAK
    assert [w["kod"] for w in wpisy_dziennika(instalacja)[-4:]] == ["stala_zgoda", "zgody_wylaczone",
                                                                     "administrator", "inny_profil"]
    assert not (instalacja["atrapa"].parent / "serve.json").exists()


def test_serve_linux_bez_ekranu(instalacja):
    daj_zgode(instalacja)
    k = instalacja["k"]
    k.platforma = "linux-x64"
    zgoda.utworz(instalacja["pliki"], [notatnik()], 600, platforma="linux-x64", uzytkownik=UZYTKOWNIK)
    del k.env["DISPLAY"]
    k.env["WAYLAND_DISPLAY"] = "wayland-0"
    krotkie = os.path.join(tempfile.gettempdir(), "hc-0123456789ab.sock")      # sun_path: do 100 bajtów
    assert bramka.serve(argv_serve(instalacja, krotkie), k) == bramka.KOD_BRAK
    assert "XWayland" in k.bledy.getvalue()


def test_serve_nadzoruje_sterownik_i_wylacza_od_razu(instalacja):
    z = daj_zgode(instalacja)
    g = gniazdo(instalacja["tmp"])
    watek, wynik = uruchom_serve(instalacja, g)
    k, pliki = instalacja["k"], instalacja["pliki"]
    zapis = json.loads((instalacja["atrapa"].parent / "serve.json").read_text(encoding="utf-8"))
    argv, env = zapis["argv"], zapis["env"]
    assert argv[:4] == ["serve", "--embedded", "--socket", g]
    assert argv[argv.index("--permission-mode") + 1] == "bounded" and "--approve-capability-manifest" in argv
    assert "--dangerously-bypass-approvals" not in argv and "--no-overlay" in argv
    kopia = Path(argv[argv.index("--capability-manifest") + 1])
    assert kopia.parent == pliki.sesje and kopia != pliki.manifest
    m = json.loads(kopia.read_text(encoding="utf-8").split("\n", 1)[1])
    assert int(m["expires_after"].rstrip("s")) <= 1800                 # czas, który został zgodzie
    assert Path(argv[argv.index("--pid-file") + 1]).parent == pliki.procesy
    for nazwa, wartosc in {"CUA_DRIVER_RS_TELEMETRY_ENABLED": "0", "CUA_DRIVER_RS_UPDATE_CHECK": "0",
                           "DO_NOT_TRACK": "1", "CUA_DRIVER_EMBEDDED": "1", "CUA_DRIVER_PARENT_LIVENESS_STDIN": "1",
                           "CUA_DRIVER_DISABLE_UNRESTRICTED": "1", "CUA_DRIVER_PERMISSION_MODE": "bounded",
                           "CUA_DRIVER_RS_HOME": str(pliki.dom)}.items():
        assert env.get(nazwa) == wartosc, nazwa
    for zakazana in ("OPENAI_API_KEY", "CUA_DRIVER_RS_MCP_HTTP_PORT", "CUA_DRIVER_DANGEROUSLY_BYPASS_APPROVALS"):
        assert zakazana not in env, zakazana
    assert str(k.program_dir / "bin-floty") not in env["PATH"].split(os.pathsep)
    assert bramka.status(["--socket", g], k) == 0
    assert bramka.status(["--socket", g + "x"], k) == 1
    t0 = time.monotonic()
    zgoda.odwolaj(pliki)                                                # jarvo komputer rece off
    watek.join(10)
    assert not watek.is_alive() and time.monotonic() - t0 < 5
    assert wynik["kod"] == 0
    assert (instalacja["atrapa"].parent / "serve-koniec.txt").read_text(encoding="utf-8") == "eof"
    assert k.rejestr.wpisy() == [] and not kopia.exists()
    zdarzenia = [(w["zdarzenie"], w.get("powod")) for w in wpisy_dziennika(instalacja)]
    assert ("serve", None) in zdarzenia and ("koniec", "rece_wylaczone") in zdarzenia
    assert z.id in json.dumps(wpisy_dziennika(instalacja))
    assert bramka.status(["--socket", g], k) == 1


def test_serve_konczy_sie_po_wygasnieciu_i_nowej_zgodzie(instalacja):
    daj_zgode(instalacja, sekundy=120)
    g = gniazdo(instalacja["tmp"])
    watek, _ = uruchom_serve(instalacja, g)
    instalacja["zegar"].przesuniecie = 121
    watek.join(10)
    assert not watek.is_alive()
    assert wpisy_dziennika(instalacja)[-1]["powod"] == "rece_wygasly"
    instalacja["zegar"].przesuniecie = 0
    (instalacja["atrapa"].parent / "serve.json").unlink()
    daj_zgode(instalacja)
    watek, _ = uruchom_serve(instalacja, g)
    daj_zgode(instalacja)                                               # nowa zgoda kończy sesję starej
    watek.join(10)
    # dwa pliki (manifest i zgoda) zmieniają się po kolei: zależnie od chwili odczytu nowa zgoda albo niezgodny
    # manifest, a sesja starej zgody i tak się kończy
    assert not watek.is_alive() and wpisy_dziennika(instalacja)[-1]["powod"] in ("nowa_zgoda", "zgoda_zmieniona")


def test_serve_stop_i_stala_zgoda_w_trakcie(instalacja):
    daj_zgode(instalacja)
    g = gniazdo(instalacja["tmp"])
    watek, _ = uruchom_serve(instalacja, g)
    assert bramka.stop(["--socket", g], instalacja["k"]) == 0
    watek.join(10)
    assert not watek.is_alive() and wpisy_dziennika(instalacja)[-1]["powod"] == "stop"
    watek, _ = uruchom_serve(instalacja, g)
    plik = instalacja["dane"] / "profiles" / "jarvo-operator" / "config.yaml"
    time.sleep(0.05)
    plik.write_text(plik.read_text(encoding="utf-8").replace("command_allowlist: []",
                                                            "command_allowlist: [\"cua:type:foreground\"]"),
                    encoding="utf-8")                                    # „zawsze” w trakcie sesji
    watek.join(10)
    assert not watek.is_alive() and wpisy_dziennika(instalacja)[-1]["powod"] == "stala_zgoda"


def test_off_z_innego_procesu_zatrzymuje_wszystko(instalacja):
    daj_zgode(instalacja)
    g = gniazdo(instalacja["tmp"])
    watek, _ = uruchom_serve(instalacja, g)
    wypis = io.StringIO()
    assert cli_rece.wylacz(None, instalacja["pliki"], cli_rece.Wyjscie(wypis)) == 0
    watek.join(10)
    assert not watek.is_alive() and "Ręce wyłączone" in wypis.getvalue()
    assert wpisy_dziennika(instalacja)[-1]["zdarzenie"] in ("off", "koniec")


# ---------------------------------------------------------------- bramka: filtr MCP

class Rozmowa:
    """Pompa bez procesów: co poszło do Hermesa i do sterownika."""

    def __init__(self, inst, platforma: str = PLATFORMA):
        self.inst = inst
        self.do_hermesa: list[dict] = []
        self.do_sterownika: list[dict] = []
        k = inst["k"]
        k.platforma = platforma
        self.z = zgoda.utworz(inst["pliki"], [notatnik()], 1800, platforma=platforma, teraz=inst["zegar"](),
                              uzytkownik=UZYTKOWNIK)
        self.pompa = bramka.Pompa(k, self.z, lambda b: self.do_hermesa.append(json.loads(b)),
                                  lambda b: self.do_sterownika.append(json.loads(b)), k.zasady)
        self.n = 0

    def wyslij(self, metoda: str, **params) -> int:
        self.n += 1
        self.pompa.od_hermesa(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": metoda, "params": params}).encode())
        return self.n

    def narzedzie(self, nazwa: str, **args) -> dict | None:
        """None = poszło do sterownika; inaczej odpowiedź bramki dla agenta."""
        przed = len(self.do_hermesa)
        self.wyslij("tools/call", name=nazwa, arguments=args)
        return self.do_hermesa[-1] if len(self.do_hermesa) > przed else None

    def odpowiedz(self, id_, wynik: dict) -> dict:
        self.pompa.od_sterownika(json.dumps({"jsonrpc": "2.0", "id": id_, "result": wynik}).encode())
        return self.do_hermesa[-1]


def test_mcp_lista_narzedzi_i_instrukcje(instalacja):
    r = Rozmowa(instalacja)
    i = r.wyslij("initialize", protocolVersion="2025-06-18")
    odp = r.odpowiedz(i, {"instructions": "sterownik", "serverInfo": {"name": "cua-driver"}})
    assert odp["result"]["instructions"].startswith("sterownik") and "notatnik" in odp["result"]["instructions"]
    i = r.wyslij("tools/list")
    odp = r.odpowiedz(i, {"tools": [{"name": n} for n in ("click", "get_desktop_state", "page", "type_text",
                                                         "kill_app", "clipboard_read", "nowe_narzedzie")]})
    assert [t["name"] for t in odp["result"]["tools"]] == ["click", "type_text"]


@pytest.mark.parametrize("nazwa, args, kod", [
    ("get_desktop_state", {}, "poza_zgoda"),
    ("page", {"action": "execute_javascript"}, "poza_zgoda"),
    ("run_script", {"script": "1"}, "poza_zgoda"),
    ("kill_app", {"pid": 1}, "poza_zgoda"),
    ("clipboard_read", {}, "poza_zgoda"),
    ("launch_app", {"name": "calc"}, "poza_zgoda"),
    ("launch_app", {"name": "notatnik", "additional_arguments": ["C:\\tajne.txt"]}, "zablokowane"),
    ("launch_app", {"name": "notatnik", "urls": ["file:///C:/tajne.txt"]}, "zablokowane"),
    ("launch_app", {"bundle_id": "notatnik", "path": r"C:\Windows\System32\cmd.exe"}, "poza_zgoda"),
    ("set_config", {"key": "capture_scope", "value": "desktop"}, "zablokowane"),
    ("set_config", {"max_image_dimension": 4096}, "zablokowane"),
    ("hotkey", {"keys": ["win", "r"]}, "zablokowane"),
    ("hotkey", {"keys": ["ctrl", "alt", "delete"]}, "zablokowane"),
    ("hotkey", {"keys": ["alt", "tab"]}, "zablokowane"),
    ("press_key", {"key": "lwin"}, "zablokowane"),
    ("type_text", {"text": "klucz sk-ant-api03-" + "x" * 30}, "zablokowane"),
    ("type_text", {"text": "karta 4111 1111 1111 1111"}, "zablokowane"),
    ("get_window_state", {"pid": 1, "screenshot_out_file": "C:\\zrzut.png"}, "zablokowane"),
    ("click", {"pid": 1, "delivery_mode": "teleport"}, "zablokowane"),
])
def test_mcp_odmowy(instalacja, nazwa, args, kod):
    r = Rozmowa(instalacja)
    odp = r.narzedzie(nazwa, **args)
    assert odp is not None, f"{nazwa} przeszło do sterownika"
    assert odp["result"]["isError"] is True and odp["result"]["structuredContent"]["code"] == kod
    assert odp["result"]["structuredContent"]["decision"] == "odmowa" and r.do_sterownika == []


@pytest.mark.parametrize("nazwa, args", [
    ("click", {"pid": 4242, "window_id": 7, "element_index": 3, "delivery_mode": "background"}),
    ("type_text", {"pid": 4242, "text": "Dzień dobry, zażółć gęślą jaźń"}),
    ("hotkey", {"pid": 4242, "keys": ["ctrl", "s"]}),
    ("press_key", {"pid": 4242, "key": "Return"}),
    ("launch_app", {"name": "notatnik"}),
    ("launch_app", {"name": "notepad", "urls": ["https://jarvo.pl"]}),
    ("set_config", {"max_image_dimension": 1456}),
    ("get_window_state", {"pid": 4242, "window_id": 7}),
    ("start_session", {"session": "hermes-1"}),
])
def test_mcp_przepuszcza_dzialania_w_zgodzie(instalacja, nazwa, args):
    r = Rozmowa(instalacja)
    assert r.narzedzie(nazwa, **args) is None
    assert r.do_sterownika[-1]["params"] == {"name": nazwa, "arguments": args}


def test_mcp_skroty_macos(instalacja):
    r = Rozmowa(instalacja, platforma="macos-arm64")
    for zly in (["cmd", "space"], ["cmd", "tab"], ["cmd", "option", "esc"], ["ctrl", "cmd", "q"]):
        assert r.narzedzie("hotkey", keys=zly) is not None, zly
    assert r.narzedzie("hotkey", keys=["cmd", "s"]) is None               # Cmd to zwykły skrót aplikacji na macOS


def test_mcp_ukrywa_sekrety_w_odpowiedziach(instalacja):
    r = Rozmowa(instalacja)
    obraz = "iVBORw0KGgo" + "A" * 70000
    i = r.n + 1
    assert r.narzedzie("get_window_state", pid=1, window_id=2) is None
    zrzut = "iVBORw0KGgo" + "B" * 70001                                  # base64 bez spacji, długość podzielna przez 4
    dlugi = "zwykły tekst dokumentu " * 3000 + "a na końcu klucz xoxb-" + "1" * 20
    odp = r.odpowiedz(i, {"content": [{"type": "text", "text": "Twój klucz: sk-proj-" + "Z" * 30},
                                      {"type": "image", "data": obraz, "mimeType": "image/png"}],
                          "structuredContent": {"elements": [{"role": "password text", "value": "Haslo123!"},
                                                             {"role": "text", "value": "ghp_" + "c" * 36}],
                                                "screenshot": zrzut, "tekst": dlugi}})
    tekst = json.dumps(odp, ensure_ascii=False)
    assert "sk-proj-" not in tekst and "ghp_" not in tekst and "Haslo123" not in tekst and "xoxb-" not in tekst
    assert odp["result"]["content"][1]["data"] == obraz                   # obraz bez zmian
    assert odp["result"]["structuredContent"]["screenshot"] == zrzut
    assert r.pompa.ukryte == 4
    r.pompa.od_sterownika(json.dumps({"jsonrpc": "2.0", "method": "notifications/message",
                                      "params": {"data": "log: sk-ant-api03-" + "k" * 30}}).encode())
    assert "sk-ant" not in json.dumps(r.do_hermesa[-1]) and r.pompa.ukryte == 5


def test_mcp_protokol(instalacja):
    r = Rozmowa(instalacja)
    r.pompa.od_hermesa(b"to nie json\n")
    r.pompa.od_hermesa(b'[{"jsonrpc":"2.0","id":1,"method":"ping"}]\n')
    r.wyslij("resources/list")
    assert [o["error"]["code"] for o in r.do_hermesa] == [-32700, -32600, -32601]
    i = r.wyslij("ping")
    assert r.do_sterownika[-1]["method"] == "ping"
    r.wyslij("tools/call", name="click", arguments={"pid": 1})
    r.pompa.od_hermesa(json.dumps({"jsonrpc": "2.0", "id": r.n, "method": "tools/call",
                                   "params": {"name": "click", "arguments": {"pid": 2}}}).encode())
    assert r.do_hermesa[-1]["error"]["code"] == -32600                    # id w toku nie wraca drugi raz
    assert i


def test_mcp_wygasniecie_i_off_w_trakcie(instalacja):
    r = Rozmowa(instalacja)
    assert r.narzedzie("click", pid=1) is None
    instalacja["zegar"].przesuniecie = 1801
    odp = r.narzedzie("click", pid=1)
    assert odp["result"]["structuredContent"]["code"] == "rece_wygasly"
    instalacja["zegar"].przesuniecie = 0
    zgoda.odwolaj(instalacja["pliki"])
    assert r.narzedzie("click", pid=1)["result"]["structuredContent"]["code"] == "rece_wylaczone"


def test_dziennik_bez_tresci(instalacja):
    r = Rozmowa(instalacja)
    r.narzedzie("type_text", pid=1, text="moje tajne zdanie do wpisania")
    r.narzedzie("hotkey", keys=["ctrl", "v"])
    r.narzedzie("launch_app", name="calc")
    r.narzedzie("type_text", pid=1, text="sk-ant-api03-" + "q" * 30)
    surowy = instalacja["pliki"].dziennik.read_text(encoding="utf-8")
    assert "tajne" not in surowy and "sk-ant" not in surowy and "calc" not in surowy
    wpisy = [w for w in wpisy_dziennika(instalacja) if w["zdarzenie"] == "narzedzie"]
    assert [(w["narzedzie"], w["decyzja"]) for w in wpisy] == [("type_text", "tak"), ("hotkey", "tak"),
                                                               ("launch_app", "odmowa"), ("type_text", "odmowa")]
    assert wpisy[0]["znaki"] == len("moje tajne zdanie do wpisania") and wpisy[1]["klawisze"] == ["ctrl", "v"]
    assert wpisy[2]["aplikacja"] == "?"


def test_mcp_przez_demona_bramki(instalacja):
    """serve + mcp + status + stop na atrapie sterownika, tak jak woła je Hermes w trybie bounded."""
    daj_zgode(instalacja)
    g = gniazdo(instalacja["tmp"])
    watek, _ = uruchom_serve(instalacja, g)
    k = instalacja["k"]
    r_in, w_in = os.pipe()
    r_out, w_out = os.pipe()
    wejscie, do_bramki = os.fdopen(r_in, "rb"), os.fdopen(w_in, "wb")
    wyjscie, z_bramki = os.fdopen(w_out, "wb"), os.fdopen(r_out, "rb")
    wynik: dict = {}
    mcp = threading.Thread(target=lambda: wynik.setdefault("kod", bramka.mcp(
        ["--no-overlay", "--embedded", "--socket", g], k, wejscie=wejscie, wyjscie=wyjscie)), daemon=True)
    mcp.start()
    odpowiedzi: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [odpowiedzi.put(json.loads(w)) for w in iter(z_bramki.readline, b"")],
                     daemon=True).start()

    def zapytaj(n: int, metoda: str, **params) -> dict:
        do_bramki.write((json.dumps({"jsonrpc": "2.0", "id": n, "method": metoda, "params": params}) + "\n").encode())
        do_bramki.flush()
        return odpowiedzi.get(timeout=10)

    assert "notatnik" in zapytaj(1, "initialize", protocolVersion="2025-06-18")["result"]["instructions"]
    assert [t["name"] for t in zapytaj(2, "tools/list")["result"]["tools"]] == [
        "click", "type_text", "launch_app", "set_config", "get_window_state"]
    odp = zapytaj(3, "tools/call", name="click", arguments={"pid": 1, "element_index": 0})
    assert odp["result"]["isError"] is False and "sk-ant" not in json.dumps(odp) and "ghp_" not in json.dumps(odp)
    odp = zapytaj(4, "tools/call", name="get_desktop_state", arguments={})
    assert odp["result"]["structuredContent"]["code"] == "poza_zgoda"
    do_bramki.close()                                                    # Hermes kończy sesję
    mcp.join(10)
    assert not mcp.is_alive() and wynik["kod"] == 0
    wyslane = [json.loads(w) for w in (instalacja["atrapa"].parent / "mcp.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [w.get("method") for w in wyslane] == ["initialize", "tools/list", "tools/call"]
    assert bramka.stop(["--socket", g], k) == 0
    watek.join(10)
    assert not watek.is_alive()


def test_mcp_bez_demona_bramki_odmawia(instalacja):
    daj_zgode(instalacja)
    kod = bramka.mcp(["--embedded", "--socket", gniazdo(instalacja["tmp"])], instalacja["k"],
                     wejscie=io.BytesIO(b""), wyjscie=io.BytesIO())
    assert kod == bramka.KOD_BRAK and "brak gotowego demona" in instalacja["k"].bledy.getvalue()


# ---------------------------------------------------------------- sterownik

def test_sterownik_suma_i_uiaccess(tmp_path, monkeypatch):
    program_dir = tmp_path / "program"
    with pytest.raises(sterownik.BladSterownika) as e:
        sterownik.sprawdz(program_dir, "windows-x64", podpis=False)
    assert e.value.kod == "brak_sterownika"
    katalog = sterownik.katalog(program_dir)
    katalog.mkdir(parents=True)
    exe = katalog / "cua-driver.exe"
    exe.write_bytes(b"MZ atrapa")
    with pytest.raises(sterownik.BladSterownika) as e:
        sterownik.sprawdz(program_dir, "windows-x64", podpis=False)
    assert e.value.kod == "zla_suma"
    monkeypatch.setitem(sterownik.PROGRAMY, "windows-x64", ("cua-driver.exe", sterownik.sha256(exe)))
    assert sterownik.sprawdz(program_dir, "windows-x64", podpis=False).program == exe
    (katalog / "cua-driver-uia.exe").write_bytes(b"MZ")
    with pytest.raises(sterownik.BladSterownika) as e:
        sterownik.sprawdz(program_dir, "windows-x64", podpis=False)
    assert e.value.kod == "uiaccess"


def test_sumy_programow_z_przegladu():
    assert set(rece.PROGRAMY) == set(sciezki.PLATFORMY)
    for plik, suma in rece.PROGRAMY.values():
        assert len(suma) == 64 and int(suma, 16) >= 0 and "cua-driver" in plik
    assert rece.WERSJA == "0.38.0" and len(rece.COMMIT) == 40


def test_podpis_macos_z_codesign(tmp_path):
    app = tmp_path / "CuaDriver.app"

    def codesign(zespol: str, ident: str = "com.trycua.driver", kod: int = 0):
        def uruchom(argv):
            import subprocess
            if "--verify" in argv:
                return subprocess.CompletedProcess(argv, kod, "", "" if kod == 0 else "invalid signature")
            return subprocess.CompletedProcess(argv, 0, "", f"Executable=x\nIdentifier={ident}\n"
                                               f"Authority=Developer ID Application: Cua AI, Inc. ({zespol})\n"
                                               f"TeamIdentifier={zespol}\nIdentifier=inny\n")
        return uruchom

    assert "YCK386LBJ7" in sterownik.podpis_macos(app, codesign("YCK386LBJ7"))
    for zly in (codesign("ABCDE12345"), codesign("YCK386LBJ7", ident="com.trycua.driver.evil"),
                codesign("YCK386LBJ7", kod=1)):
        with pytest.raises(sterownik.BladSterownika):
            sterownik.podpis_macos(app, zly)


@pytest.mark.windows_only
def test_podpis_windows(tmp_path):
    bez = tmp_path / "bez.exe"
    bez.write_bytes(b"MZ" + b"\0" * 500)
    with pytest.raises(sterownik.BladSterownika):
        sterownik.podpis_windows(bez)
    try:
        nazwa = sterownik.podpis_windows(Path(sys.executable))
    except sterownik.BladSterownika:
        pytest.skip("ten python.exe nie ma podpisu Authenticode (np. python-build-standalone)")
    assert nazwa
    zmieniony = tmp_path / "zmieniony.exe"
    dane = bytearray(Path(sys.executable).read_bytes())
    dane[len(dane) // 3] ^= 0xFF
    zmieniony.write_bytes(bytes(dane))
    with pytest.raises(sterownik.BladSterownika, match="zmieniony"):
        sterownik.podpis_windows(zmieniony)


def test_srodowisko_sterownika(tmp_path):
    program = tmp_path / "program"
    baza = {"PATH": os.pathsep.join([str(program / "bin-floty"), str(tmp_path / "systemowy")]),
            "OPENAI_API_KEY": "sk-proj-x", "TELEGRAM_BOT_TOKEN": "1:2", "HOME": str(tmp_path),
            "CUA_DRIVER_POLICY_FILE": "x", "CUA_DRIVER_RS_ENABLE_WAYLAND": "1", "HERMES_HOME": "x", "DISPLAY": ":1"}
    env = sterownik.srodowisko(baza, tmp_path / "dom", demon=True, program_dir=program)
    assert env["PATH"] == str(tmp_path / "systemowy") and env["DISPLAY"] == ":1" and env["HOME"] == str(tmp_path)
    for nazwa in ("OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "CUA_DRIVER_POLICY_FILE", "CUA_DRIVER_RS_ENABLE_WAYLAND",
                  "HERMES_HOME"):
        assert nazwa not in env
    assert env["CUA_DRIVER_PARENT_LIVENESS_STDIN"] == "1"
    assert "CUA_DRIVER_PARENT_LIVENESS_STDIN" not in sterownik.srodowisko(baza, tmp_path, demon=False)


def test_ekran_linux_i_prawa():
    assert sterownik.ekran_linux({"DISPLAY": ":0"}) is None
    assert "XWayland" in sterownik.ekran_linux({"WAYLAND_DISPLAY": "wayland-0"})
    assert "DISPLAY" in sterownik.ekran_linux({})
    assert isinstance(sterownik.podwyzszone(), bool)


@pytest.mark.posix_only
def test_odcisk_procesu_posix():
    assert procesy.odcisk(os.getpid()) is not None and procesy.odcisk(2 ** 22 + 7) is None


@pytest.mark.windows_only
def test_odcisk_procesu_windows():
    assert procesy.odcisk(os.getpid()).isdigit() and procesy.odcisk(4_000_000) is None


# ---------------------------------------------------------------- jarvo komputer rece

@pytest.fixture
def jarvo_root(tmp_path, monkeypatch):
    root = tmp_path / "Jarvo root"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "JARVO_"))}
    env["JARVO_ROOT"] = str(root)
    env["DISPLAY"] = ":0"
    u = sciezki.uklad(env)
    pliki = zgoda.Pliki(u.stan)
    profil = u.dane / "profiles" / "jarvo-operator"
    profil.mkdir(parents=True)
    (profil / "config.yaml").write_text(PROFIL_OK.format(manifest=str(pliki.manifest).replace("\\", "\\\\")),
                                        encoding="utf-8")
    u.stan.mkdir(parents=True, exist_ok=True)
    st = sterownik.Sterownik(program=Path(sys.executable), przedrostek=(sys.executable,), sha256="x",
                             podpis="Cua AI, Inc.")
    wypis = io.StringIO()

    def jarvo(*argv, odpowiedz="TAK", tty=True, env_=None, **kw):
        wypis.truncate(0)
        wypis.seek(0)
        kw.setdefault("sprawdz_sterownik", lambda: st)
        kw.setdefault("rozpoznaj", lambda nazwy: [notatnik()])
        kod = cli_rece.main(list(argv), env=env_ or env, wejscie=lambda _p: odpowiedz, tty=tty,
                            podwyzszone=lambda: False, wyjscie=wypis, platforma=PLATFORMA, **kw)
        return kod, wypis.getvalue()

    return {"jarvo": jarvo, "u": u, "pliki": pliki, "env": env, "profil": profil}


def test_cli_on_status_off(jarvo_root, monkeypatch):
    monkeypatch.setattr(zgoda, "tozsamosc_uzytkownika", lambda: UZYTKOWNIK)
    jarvo, pliki = jarvo_root["jarvo"], jarvo_root["pliki"]
    kod, tekst = jarvo("on", "--aplikacje", "notatnik", "--na", "20m")
    assert kod == 0, tekst
    assert "Ręce włączone do" in tekst and "jarvo komputer rece off" in tekst
    z = zgoda.wczytaj(pliki, platforma=PLATFORMA)
    assert z.nazwy() == ["notatnik"] and 1190 <= z.pozostalo() <= 1200 and z.bezczynnosc == 600
    kod, tekst = jarvo("status", "--json")
    s = json.loads(tekst)
    assert kod == 0 and s["zgoda"]["wlaczone"] and s["sterownik"]["gotowy"] and s["profil"]["brakuje"] == []
    assert "Ręce: włączone" in jarvo("status")[1]
    kod, tekst = jarvo("off")
    assert kod == 0 and "Ręce wyłączone" in tekst and not pliki.zgoda.exists()
    assert "Ręce: wyłączone" in jarvo("status")[1]
    assert [w["zdarzenie"] for w in dziennik.ostatnie(pliki.dziennik)] == ["on", "off"]
    assert jarvo("off")[1].startswith("Ręce były wyłączone")


def test_cli_on_tylko_wlasciciel(jarvo_root):
    jarvo, pliki, u = jarvo_root["jarvo"], jarvo_root["pliki"], jarvo_root["u"]
    kod, tekst = jarvo("on", "--aplikacje", "notatnik", tty=False)
    assert kod == 1 and "terminalu" in tekst
    for zmienna, wartosc in (("HERMES_HOME", str(u.dane / "profiles" / "jarvo")), ("HERMES_KANBAN_TASK", "t1"),
                             ("HERMES_WRITE_SAFE_ROOT", str(u.dane)), ("HERMES_CRON_SESSION", "1")):
        kod, tekst = jarvo("on", "--aplikacje", "notatnik", env_={**jarvo_root["env"], zmienna: wartosc})
        assert kod == 1 and zmienna in tekst
    kod, tekst = jarvo("on", "--aplikacje", "notatnik", odpowiedz="nie")
    assert kod == 1 and "Nie włączyłem" in tekst
    assert not pliki.zgoda.exists()
    prywatny = {**jarvo_root["env"], "HERMES_HOME": str(u.root.parent / "prywatny-hermes")}
    assert cli_rece.proces_floty(prywatny, u.dane) is None                # prywatny Hermes właściciela nie przeszkadza


def test_cli_on_odmawia_profilu_ze_stalymi_zgodami(jarvo_root):
    plik = jarvo_root["profil"] / "config.yaml"
    plik.write_text(plik.read_text(encoding="utf-8").replace("command_allowlist: []",
                                                            "command_allowlist:\n  - cua:click:background"),
                    encoding="utf-8")
    kod, tekst = jarvo_root["jarvo"]("on", "--aplikacje", "notatnik")
    assert kod == 2 and "cua:click:background" in tekst and not jarvo_root["pliki"].zgoda.exists()


def test_cli_on_argumenty(jarvo_root):
    jarvo = jarvo_root["jarvo"]
    assert jarvo("on", "--aplikacje", "notatnik", "--na", "9h")[0] == 2
    assert jarvo("on")[0] == 2                                           # bez --aplikacje
    kod, tekst = jarvo("on", "--aplikacje", "notatnik", "--profil", "../../etc")
    assert kod == 2 and "nazwa profilu" in tekst
    kod, tekst = jarvo("on", "--aplikacje", "cmd", rozpoznaj=lambda n: aplikacje.rozpoznaj(
        n, system="win32", which=lambda x: None, istnieje=lambda p: True))
    assert kod == 2 and "nie obejmują" in tekst


def test_cli_on_bez_sterownika_w_manifescie(jarvo_root, monkeypatch):
    from jarvo import manifest

    def brak():
        raise sterownik.BladSterownika("brak_sterownika", "Nie ma sterownika rąk")

    monkeypatch.setattr(manifest, "wczytaj", lambda app: {})
    kod, tekst = jarvo_root["jarvo"]("on", "--aplikacje", "notatnik", sprawdz_sterownik=brak)
    assert kod == 2 and "manifeście" in tekst and not jarvo_root["pliki"].zgoda.exists()


def test_cli_on_pobiera_sterownik_z_manifestu(jarvo_root, monkeypatch, tmp_path):
    from jarvo import manifest
    monkeypatch.setattr(zgoda, "tozsamosc_uzytkownika", lambda: UZYTKOWNIK)
    wpis = {"url": "https://github.com/trycua/cua/releases/download/x.zip", "sha256": "0" * 64, "rozmiar": 35894668,
            "format": "zip"}
    monkeypatch.setattr(manifest, "wczytaj", lambda app: {"cua-driver": {"wersja": rece.WERSJA,
                                                                         "pliki": {PLATFORMA: wpis}}})
    stan = {"zainstalowany": False}
    st = sterownik.Sterownik(program=Path(sys.executable), przedrostek=(sys.executable,), sha256="x")

    def sprawdz():
        if not stan["zainstalowany"]:
            raise sterownik.BladSterownika("brak_sterownika", "Nie ma sterownika rąk")
        return st

    def zainstaluj():
        stan["zainstalowany"] = True
        return tmp_path / "cua-driver"

    kod, tekst = jarvo_root["jarvo"]("on", "--aplikacje", "notatnik", sprawdz_sterownik=sprawdz, zainstaluj=zainstaluj)
    assert kod == 0 and "Pobieram sterownik rąk cua-driver-rs 0.38.0 (36 MB)" in tekst


def test_changelog_operatora_opisuje_rece():
    tekst = (REPO / "profiles" / "jarvo-operator" / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "jarvo komputer rece on" in tekst
