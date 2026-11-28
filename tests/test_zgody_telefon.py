"""Strażnik zgód: jedno zadanie = jeden telefon floty i blokada prywatnego numeru właściciela (26.11)."""
from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("jarvo_zgody_plugin_telefon", REPO / "zgody" / "plugin" / "__init__.py")
z = importlib.util.module_from_spec(_spec)
sys.modules["jarvo_zgody_plugin_telefon"] = z
_spec.loader.exec_module(z)

IP = {"first": "100.99.0.1", "second": "100.99.0.2", "third": "100.99.0.3"}
NUMER_TESTOWY = "600100200"          # fikcyjny numer tylko dla testu


@pytest.fixture
def straz(tmp_path, monkeypatch):
    home = tmp_path / "dane" / "profiles" / "jarvo"
    home.mkdir(parents=True)
    monkeypatch.setattr(z, "_hermes_home", lambda: home)
    monkeypatch.setattr(z, "_decyzja", lambda tool_name, args, task_id: None)
    monkeypatch.setattr(z, "_mapa_ip", lambda: {ip: n for n, ip in IP.items()})
    monkeypatch.setattr(z, "_TELEFON_ZADANIA", collections.OrderedDict())
    monkeypatch.setattr(z, "_NUMERY_CACHE", {})
    monkeypatch.setattr(z, "_cialo_odpowiada", lambda nazwa: False)       # ciało PhoneUse nie odpowiada
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.delenv("PHONEUSE_ONLY", raising=False)
    return home


def hak(narzedzie, sesja="s1", **args):
    return z.straznik_zgod(tool_name=narzedzie, args=args, task_id="t", session_id=sesja)


def zablokowane(w):
    return bool(w) and w["action"] == "block"


def test_mcp_przeskok_w_zadaniu_blokowany(straz):
    assert hak("mcp__phone__act", cmd="tap") is None              # brak phone = first
    w = hak("mcp__phone__act", phone="third", cmd="tap")
    assert zablokowane(w) and "telefonie first" in w["message"]


def test_przepis_telefonu_wiaze_jak_akcja(straz):
    """`run_recipe` stuka i pisze jak `batch`, więc też wiąże zadanie z telefonem; `find` i `read_list` tylko czytają."""
    assert hak("mcp__phone__run_recipe", phone="second", name="lista") is None
    assert zablokowane(hak("mcp__phone__run_recipe", phone="third", name="lista"))
    assert hak("mcp__phone__read_list", phone="third") is None


def test_inne_zadanie_zaczyna_od_zera(straz, monkeypatch):
    assert hak("mcp__phone__act", phone="first", cmd="tap") is None
    assert hak("mcp__phone__act", sesja="s2", phone="third", cmd="tap") is None
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_nowa")
    assert hak("mcp__phone__act", phone="second", cmd="tap") is None


def test_adb_akcja_na_innym_telefonie_blokowana(straz):
    assert hak("terminal", command=f"adb -s {IP['first']}:5555 shell input tap 1 2") is None
    assert zablokowane(hak("terminal", command=f"adb -s {IP['third']}:5555 shell am start -a android.intent.action.VIEW"))


def test_petla_akcji_po_dwoch_telefonach_blokowana(straz):
    polecenie = f"for N in first:{IP['first']} third:{IP['third']}; do adb -s ${{N#*:}}:5555 shell input keyevent 3; done"
    assert zablokowane(hak("terminal", command=polecenie))


def test_odczyt_nie_wiaze_i_nie_blokuje(straz):
    """27.11: Jarvo sprawdzał, czy na którymś telefonie jest OLX, a strażnik blokował odczyt wszystkich telefonów."""
    assert hak("mcp__phone__act", phone="third", cmd="tap") is None
    assert hak("mcp__phone__list_phones") is None
    assert hak("mcp__phone__ping", phone="second") is None
    assert hak("mcp__phone__screen", phone="first") is None
    polecenie = f"for S in {IP['first']} {IP['third']}; do adb -s $S:5555 shell pm list packages | grep olx; done"
    assert hak("terminal", command=polecenie) is None
    assert hak("terminal", command="ls 100.99.0.1") is None        # bez adb nie dotyczy telefonu


def test_wiazanie_rozmowy_wygasa(straz, monkeypatch):
    zegar = [1000.0]
    monkeypatch.setattr(z.time, "monotonic", lambda: zegar[0])
    assert hak("mcp__phone__act", phone="first", cmd="tap") is None
    zegar[0] += 1801
    assert hak("mcp__phone__act", phone="third", cmd="tap") is None


def test_telefon_zajety_przez_inne_zadanie(straz, monkeypatch):
    """28.11: SMS Jarva w rozmowie i test OLX stukały naraz w first i zgubiły się oba."""
    zegar = [5000.0]
    monkeypatch.setattr(z.time, "time", lambda: zegar[0])
    assert hak("mcp__phone__act", phone="first", cmd="tap") is None
    w = hak("mcp__phone__act", sesja="s2", phone="first", cmd="tap")
    assert zablokowane(w) and "Telefon first prowadzi teraz inne zadanie" in w["message"]
    assert hak("mcp__phone__screen", sesja="s2", phone="first") is None           # odczyt wolny
    assert hak("mcp__phone__act", phone="first", cmd="tap") is None               # właściciel działa dalej
    zegar[0] += 601
    assert hak("mcp__phone__act", sesja="s2", phone="first", cmd="tap") is None   # po 10 min bez kroku przejmuje
    assert zablokowane(hak("mcp__phone__act", phone="first", cmd="tap"))


def test_prywatny_numer_blokowany(straz):
    plik = straz.parent.parent / "jarvo" / "konfig" / "prywatne-numery.json"
    assert hak("mcp__phone__act", cmd="type", text="+48 600 100 200") is None        # brak pliku = nic
    plik.parent.mkdir(parents=True)
    plik.write_text(json.dumps({"sha256_9": [hashlib.sha256(NUMER_TESTOWY.encode()).hexdigest()]}), encoding="utf-8")
    w = hak("mcp__phone__act", cmd="type", text="+48 600 100 200")
    assert zablokowane(w) and "prywatny numer JARO" in w["message"]
    assert zablokowane(hak("browser_type", text="0048-600.100(200)"))
    assert hak("mcp__phone__act", sesja="s9", phone="second", cmd="type", text="+48 600 100 201") is None


@pytest.mark.parametrize("profil,wolno", [("jarvo-hacker", True), ("jarvo-bigshort", True), ("jarvo", False),
                                          ("jarvo-inny", False)])
def test_prywatny_numer_tylko_hacker_i_bigshort(straz, monkeypatch, profil, wolno):
    home = straz.parent / profil
    home.mkdir(exist_ok=True)
    monkeypatch.setattr(z, "_hermes_home", lambda: home)
    plik = straz.parent.parent / "jarvo" / "konfig" / "prywatne-numery.json"
    plik.parent.mkdir(parents=True)
    plik.write_text(json.dumps({"sha256_9": [hashlib.sha256(NUMER_TESTOWY.encode()).hexdigest()]}), encoding="utf-8")
    w = hak("browser_type", text="+48 600 100 200")
    assert (w is None) if wolno else (zablokowane(w) and "fleet/telefony.md" in w["message"])


def test_mapa_z_telefon_json(tmp_path, monkeypatch):
    home = tmp_path / "root" / "dane" / "profiles" / "jarvo"
    home.mkdir(parents=True)
    stan = tmp_path / "root" / "stan"
    stan.mkdir()
    (stan / "telefon.json").write_text(json.dumps({"adresy": {n: f"{ip}:5555" for n, ip in IP.items()}}),
                                       encoding="utf-8")
    monkeypatch.setattr(z, "_hermes_home", lambda: home)
    monkeypatch.setattr(z, "_MAPA", {"t": 0.0, "ip": {}})
    assert z._mapa_ip() == {ip: n for n, ip in IP.items()}


@pytest.mark.parametrize("polecenie", [
    '$A -s $S shell "pm clear com.android.chrome"',
    "adb -s 100.99.0.1:5555 shell cmd package uninstall com.x",
    "adb uninstall com.x",
    "for S in a b; do adb -s $S shell sh -c 'rm -rf /sdcard/Download'; done",
    "adb shell settings delete global x",
    "adb reboot recovery",
    "adb -s $S shell cmd connectivity airplane-mode enable",
    "adb shell settings put global airplane_mode_on 1",
    "adb shell svc wifi disable",
    "adb shell 'cmd wifi set-wifi-enabled disabled'",
])
def test_adb_niszczace_blokowane(straz, polecenie):
    w = hak("terminal", command=polecenie)
    assert zablokowane(w) and "tylko na wyraźne polecenie JARO" in w["message"]


@pytest.mark.parametrize("polecenie", [
    '$A -s $S shell "pm list packages"',
    "adb -s 100.99.0.1:5555 shell am start -n com.android.chrome/.Main",
    "adb -s $S shell cmd connectivity airplane-mode disable",
])
def test_adb_odczyt_i_start_przechodza(straz, polecenie):
    assert hak("terminal", command=polecenie) is None


# ------------------------------------------------------------------- surowe adb ekranu przy działającym ciele PhoneUse

SONDA = z._cialo_odpowiada


class _Cialo:
    """Atrapa ciała PhoneUse: GET /ping bez tokenu jak Replies.ping (PHONEUSE docs/body-api.md, sekcja 5)."""

    def __init__(self):
        import http.server
        import threading
        cialo = self
        self.pingi = 0

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                cialo.pingi += 1
                tresc = json.dumps({"success": True, "service": "PhoneUseBody", "version_name": "1.8.1",
                                    "auth_required": True, "token_set": True, "authenticated": False}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(tresc)))
                self.end_headers()
                self.wfile.write(tresc)

            def log_message(self, *a):
                pass

        self.serwer = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.serwer.server_address[1]
        threading.Thread(target=self.serwer.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def stop(self):
        self.serwer.shutdown()
        self.serwer.server_close()


LOKALNY = {"third": "127.0.0.1", "first": "127.0.0.2"}


@pytest.fixture
def cialo(straz, monkeypatch):
    """Prawdziwa sonda _cialo_odpowiada na atrapie ciała third (127.0.0.1); first (127.0.0.2) bez ciała."""
    c = _Cialo()
    mapa = {ip: n for n, ip in LOKALNY.items()}
    stan = {"t": 0.0, "ip": mapa, "wlaczony": True, "przydzialy": {"jarvo-hacker": "first"}}
    monkeypatch.setattr(z, "_cialo_odpowiada", SONDA)
    monkeypatch.setattr(z, "_CIALA", {})
    monkeypatch.setattr(z, "PORT_CIALA", c.port)
    monkeypatch.setattr(z, "_stan_telefonow", lambda: stan)
    monkeypatch.setattr(z, "_mapa_ip", lambda: mapa)
    yield c, stan
    c.stop()


@pytest.mark.parametrize("polecenie", [
    "adb -s 127.0.0.1:5555 shell input tap 360 1440",
    'ADB=/x/platform-tools/37.0.1/adb S=127.0.0.1:5555 $ADB -s $S shell "uiautomator dump /sdcard/u.xml" && grep text',
    "adb -s 127.0.0.1:5555 exec-out screencap -p > ekran.png",
    "adb -s 127.0.0.1:5555 shell am start -a android.intent.action.VIEW -d https://olx.pl",
    "adb -s 127.0.0.1:5555 shell monkey -p pl.tablica 1",
    "adb -s 127.0.0.1:5555 shell input touchscreen swipe 360 1200 360 400",
    "adb shell input keyevent 4",                        # bez serialu: każdy telefon floty
    "adb -s $S shell input text kot",                    # serial w zmiennej: każdy telefon floty
])
def test_adb_ekranu_przy_zywym_ciele_blokowany(cialo, polecenie):
    w = hak("terminal", command=polecenie)
    assert zablokowane(w) and 'phone="third"' in w["message"] and "mcp__phone__screen" in w["message"]


@pytest.mark.parametrize("polecenie", [
    "adb -s 127.0.0.1:5555 shell pm list packages | grep olx",
    "adb -s 127.0.0.1:5555 shell dumpsys window | grep mCurrentFocus",
    "adb -s 127.0.0.1:5555 shell getprop ro.product.model",
    "adb -s 127.0.0.1:5555 logcat -d -t 50",
    "adb -s 127.0.0.1:5555 install -r capcut.apk",
    "adb -s emulator-5554 shell input tap 1 2",          # jawny serial spoza floty
    "adb -s 127.0.0.2:5555 shell input tap 1 2",         # first: ciało nie odpowiada
])
def test_adb_bez_ekranu_albo_bez_ciala_przechodzi(cialo, polecenie):
    assert hak("terminal", command=polecenie) is None


def test_adb_ekranu_w_execute_code_blokowany(cialo):
    kod = 'import subprocess\nsubprocess.run(["adb", "-s", "127.0.0.1:5555", "shell", "input", "tap", "1", "2"])'
    assert zablokowane(hak("execute_code", code=kod))


def test_cialo_wylaczone_adb_przechodzi_i_pamiec_odpowiedzi(cialo, monkeypatch):
    c, _ = cialo
    polecenie = "adb -s 127.0.0.1:5555 shell input tap 1 2"
    assert zablokowane(hak("terminal", command=polecenie))
    assert zablokowane(hak("terminal", command=polecenie))
    assert c.pingi == 1                                  # druga ocena z pamięci, bez nowego /ping
    c.stop()                                             # ciało wyłączone
    monkeypatch.setattr(z, "_CIALA", {})                 # pamięć wygasła
    assert hak("terminal", command=polecenie) is None


def test_adb_ekranu_tylko_telefony_profilu(cialo, monkeypatch, straz):
    _, stan = cialo
    hacker = straz.parent / "jarvo-hacker"
    hacker.mkdir()
    monkeypatch.setattr(z, "_hermes_home", lambda: hacker)
    assert hak("terminal", command="adb -s 127.0.0.1:5555 shell input tap 1 2") is None    # third: nie jego serwer
    stan["przydzialy"] = {"jarvo-hacker": "third"}
    assert zablokowane(hak("terminal", command="adb -s 127.0.0.1:5555 shell input tap 1 2"))
    monkeypatch.setattr(z, "_hermes_home", lambda: straz)
    stan["wlaczony"] = False                                                              # jarvo telefon off
    assert hak("terminal", command="adb -s 127.0.0.1:5555 shell input tap 1 2") is None


def test_sonda_ciala_bez_serwera_falsz(monkeypatch):
    monkeypatch.setattr(z, "_CIALA", {})
    monkeypatch.setattr(z, "_mapa_ip", lambda: {"127.0.0.1": "third"})
    monkeypatch.setattr(z, "PORT_CIALA", 9)               # discard: nikt nie słucha
    assert SONDA("third") is False
    assert SONDA("nieznany") is False


# ------------------------------------------------------------------- narzędzie pulpitu (wtyczka jarvo-pulpit)

def test_pulpit_pod_yolo_zablokowany(monkeypatch):
    monkeypatch.setattr(z, "_yolo", lambda: True)
    w = z._decyzja("pulpit", {"akcja": "klik", "x": 10, "y": 10}, "t")
    assert zablokowane(w) and "YOLO" in w["message"]


def test_pulpit_prywatny_numer_zablokowany(straz):
    plik = straz.parent.parent / "jarvo" / "konfig" / "prywatne-numery.json"
    plik.parent.mkdir(parents=True)
    plik.write_text(json.dumps({"sha256_9": [hashlib.sha256(NUMER_TESTOWY.encode()).hexdigest()]}), encoding="utf-8")
    assert zablokowane(hak("pulpit", akcja="pisz", tekst="+48 600 100 200"))
    assert zablokowane(hak("pulpit", akcja="kroki", kroki=[{"akcja": "klik", "x": 1, "y": 2},
                                                           {"akcja": "pisz", "tekst": "600-100-200"}]))
    assert hak("pulpit", akcja="pisz", tekst="+48 600 100 201") is None
