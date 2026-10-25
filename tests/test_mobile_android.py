"""Telefon testowy Twórcy aplikacji natywnie (docs/NATYWNIE.md: N12, U04, U05, E13, F08, I24; etap E11):
`jarvo android status|on|off|ekran` (jarvo/android.py) i adb floty w urzadzenie.py z instalacji natywnej.

Bez telefonu, bez sieci i bez prawdziwego adb: instalacja to katalog tymczasowy z `program/current.json`, a adb i scrcpy
to atrapy (tests/atrapy.py), które zapisują wywołania. Na żywo (prawdziwe platform-tools i scrcpy z manifestu):
tests/live/natywnie_telefon_3d.py.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import atrapy
import pytest

from conftest import REPO, load_script

sys.path.insert(0, str(REPO))
from jarvo import android, przy_uzyciu, sciezki  # noqa: E402

ur = load_script("profiles/jarvo-mobile/scripts/urzadzenie.py", "urzadzenie_natywnie")

WINDOWS = os.name == "nt"
URZADZENIA = ("List of devices attached\n"
              "R58M123ABC             device usb:1-1 product:a51 model:SM_A515F device:a51 transport_id:3\n"
              "emulator-5554          device product:sdk_gphone64 model:sdk_gphone64_x86_64 transport_id:1\n"
              "192.168.1.20:37123     unauthorized transport_id:4\n"
              "0123456789ABCDEF       no permissions (missing udev rules? user is in the plugdev group); see "
              "[http://developer.android.com/tools/device.html] usb:1-2 transport_id:5\n")

ATRAPA_ADB = r'''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["ATRAPA_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": args, "mdns": os.environ.get("ADB_MDNS"),
                        "klucze": os.environ.get("ADB_VENDOR_KEYS")}) + "\n")
if args[:1] == ["-s"]:
    args = args[2:]
if args == ["version"]:
    print("Android Debug Bridge version 1.0.41\nVersion 37.0.1-15733141\nInstalled as adb")
elif args == ["start-server"]:
    klucze = os.environ.get("ATRAPA_KLUCZE")
    if klucze and not os.path.exists(os.path.join(klucze, "adbkey")):   # jak adb: klucz przy pierwszym starcie
        os.makedirs(klucze, exist_ok=True)
        open(os.path.join(klucze, "adbkey"), "w").write("PRYWATNY")
        open(os.path.join(klucze, "adbkey.pub"), "w").write("PUBLICZNY test@jarvo")
    print("* daemon not running; starting now at tcp:5037\n* daemon started successfully")
elif args[:1] == ["devices"]:
    print(os.environ.get("ATRAPA_URZADZENIA", "List of devices attached\n"))
elif args[:1] == ["connect"]:
    print("connected to " + args[1])
elif args[:1] == ["pair"]:
    print("Successfully paired to " + args[1] + " [guid=adb-XYZ]" if args[2] == "123456" else "Failed: Wrong password")
elif args[:2] == ["shell", "getprop"]:
    print("14")
elif args == ["get-state"]:
    print(os.environ.get("ATRAPA_STAN", "device"))
'''


def _wywolania(log: Path) -> list[dict]:
    return [json.loads(w) for w in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []


@pytest.fixture
def inst(tmp_path, monkeypatch):
    """Instalacja natywna w katalogu tymczasowym: current.json z kodem tego repo, atrapa adb jako platform-tools."""
    root = tmp_path / "Jarvo"
    u = sciezki.uklad({"JARVO_ROOT": str(root)})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    u.stan.mkdir(parents=True, exist_ok=True)
    (u.program / "current.json").write_text(json.dumps({"app": str(REPO)}), encoding="utf-8")
    adb = atrapy.program(tmp_path / "pt", "adb", ATRAPA_ADB)
    log = tmp_path / "adb.jsonl"
    klucze = tmp_path / "dom" / ".android"                     # katalog klucza adb na koncie (atrapa)
    monkeypatch.setenv("JARVO_ROOT", str(root))
    monkeypatch.setenv("ATRAPA_LOG", str(log))
    monkeypatch.setenv("ATRAPA_KLUCZE", str(klucze))
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\n")
    monkeypatch.delenv("JARVO_ANDROID_ADB", raising=False)
    monkeypatch.delenv("JARVO_ADB", raising=False)
    monkeypatch.setattr(android, "adb", lambda _u: adb)
    monkeypatch.setattr(android, "scrcpy", lambda _u: None)
    monkeypatch.setattr(android, "katalog_adb", lambda: klucze)
    return argparse.Namespace(u=u, adb=adb, log=log, root=root, klucze=klucze)


def _a(**kw) -> argparse.Namespace:
    baza = dict(akceptuje_licencje=False, wifi=None, paruj=None, kod=None, urzadzenie=None, zostaw_adb=False,
                json=False, bez_dzwieku=False, rozmiar=None)
    return argparse.Namespace(**(baza | kw))


# ------------------------------------------------------------------ adb devices, wybór urządzenia

def test_lista_urzadzen_z_adb_devices():
    d = {x["serial"]: x for x in android.urzadzenia(URZADZENIA)}
    assert d["R58M123ABC"] == {"serial": "R58M123ABC", "stan": "device", "model": "SM A515F", "usb": True,
                               "transport": "3"}
    assert d["emulator-5554"]["stan"] == "device" and not d["emulator-5554"]["usb"]
    assert d["192.168.1.20:37123"]["stan"] == "unauthorized"
    assert d["0123456789ABCDEF"]["stan"] == "no permissions" and d["0123456789ABCDEF"]["usb"]
    assert android.urzadzenia("* daemon not running; starting now at tcp:5037\nList of devices attached\n\n") == []
    opis = android._opis_urzadzenia(d["192.168.1.20:37123"])
    assert "Wi-Fi" in opis and "zgodę" in opis


def test_wybor_urzadzenia_floty():
    lista = android.urzadzenia(URZADZENIA)
    assert android.wybierz(lista, "192.168.1.20:37123")[0] == "192.168.1.20:37123"       # wskazany, choć bez zgody
    assert android.wybierz(lista, "nie-ma")[0] is None
    serial, powod = android.wybierz(lista)                     # dwa gotowe: bez zgadywania
    assert serial is None and "--urzadzenie" in powod
    assert android.wybierz(lista, None, "emulator-5554") == ("emulator-5554", "wybrane wcześniej")
    jeden = [x for x in lista if x["serial"] != "emulator-5554"]
    assert android.wybierz(jeden) == ("R58M123ABC", "jedyne gotowe")
    assert android.wybierz([])[0] is None


# ------------------------------------------------------------------ licencja Google przed pierwszym pobraniem

class Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_licencja_pytanie_flaga_i_zapamietanie(inst):
    wyjscie = io.StringIO()
    assert not android.zgoda_na_licencje(inst.u, _a(), wejscie=io.StringIO("t\n"), wyjscie=wyjscie)   # bez terminala
    assert "--akceptuje-licencje" in wyjscie.getvalue() and android.LICENCJA_URL in wyjscie.getvalue()
    assert not android.zgoda_na_licencje(inst.u, _a(), wejscie=Tty("nie\n"), wyjscie=io.StringIO())
    assert not android.stan_androida(inst.u).get("licencja_sdk")
    assert android.zgoda_na_licencje(inst.u, _a(), wejscie=Tty("t\n"), wyjscie=io.StringIO())
    zgoda = android.stan_androida(inst.u)["licencja_sdk"]
    assert zgoda["adres"] == android.LICENCJA_URL and zgoda["zaakceptowano"]
    assert android.zgoda_na_licencje(inst.u, _a(), wejscie=io.StringIO(""), wyjscie=io.StringIO())   # zapamiętana
    (inst.u.stan / android.STAN).unlink()
    assert android.zgoda_na_licencje(inst.u, _a(akceptuje_licencje=True), wejscie=io.StringIO(""),
                                     wyjscie=io.StringIO())


def test_on_bez_platform_tools_i_bez_zgody_niczego_nie_pobiera(inst, monkeypatch, capsys):
    monkeypatch.setattr(android, "adb", lambda _u: None)
    monkeypatch.setattr(android.sciezki, "platforma", lambda: "windows-x64")
    pobrania = []
    monkeypatch.setattr(przy_uzyciu, "narzedzie", lambda *a, **k: pobrania.append(a) or {})
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert android.polecenie_on(inst.u, _a()) == 1
    assert pobrania == [] and "licencji" in capsys.readouterr().out


def test_on_linux_arm64_bez_platform_tools_radzi_adb_z_systemu(inst, monkeypatch, capsys):
    monkeypatch.setattr(android, "adb", lambda _u: None)
    monkeypatch.setattr(android.sciezki, "platforma", lambda: "linux-arm64")
    assert android.polecenie_on(inst.u, _a(akceptuje_licencje=True)) == 1
    assert "apt install adb" in capsys.readouterr().err


# ------------------------------------------------------------------ on, off, status, ekran z atrapą adb

def test_on_wlacza_i_wybiera_jedyne_urzadzenie(inst, monkeypatch, capsys):
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\nR58M123ABC  device usb:1-1 model:SM_A515F\n")
    assert android.polecenie_on(inst.u, _a()) == 0
    st = android.stan_androida(inst.u)
    assert st["wlaczony"] is True and st["serial"] == "R58M123ABC"
    w = _wywolania(inst.log)
    assert [x["argv"][0] for x in w[:3]] == ["version", "start-server", "devices"]
    assert all(x["mdns"] == "0" for x in w)                    # bez szukania telefonów w sieci lokalnej
    out = capsys.readouterr().out
    assert "Android 14" in out and "jarvo android ekran" in out and "9122" in out


def test_nowy_klucz_adb_w_dzienniku_zmian_hosta(inst, monkeypatch, capsys):
    """Klucz adb, który założył serwer z `jarvo android on`, to ślad poza katalogiem Jarva: wpis „plik” (D08), żeby
    `jarvo uninstall` go usunął; klucz, który był wcześniej, nie jest nasz i nie trafia do dziennika."""
    from jarvo import zmiany_hosta
    assert android.polecenie_on(inst.u, _a()) == 0
    pliki = {w["szczegoly"]["sciezka"]: w["szczegoly"]["sha256"] for w in zmiany_hosta.wpisy(inst.u)
             if w["rodzaj"] == "plik"}
    assert set(pliki) == {str(inst.klucze / "adbkey"), str(inst.klucze / "adbkey.pub")}
    assert pliki[str(inst.klucze / "adbkey")] == zmiany_hosta._sha(b"PRYWATNY")
    assert android.polecenie_on(inst.u, _a()) == 0                            # drugi raz: bez nowych wpisów
    assert len([w for w in zmiany_hosta.wpisy(inst.u) if w["rodzaj"] == "plik"]) == 2
    raport = zmiany_hosta.cofnij(inst.u, log=None)                            # jarvo uninstall (E13)
    assert {r["wynik"] for r in raport} == {"cofniete"} and not (inst.klucze / "adbkey").exists()
    (inst.klucze / "adbkey").write_text("KLUCZ ANDROID STUDIO")              # cudzy klucz: zostaje poza dziennikiem
    (inst.klucze / "adbkey.pub").write_text("pub")
    assert android.polecenie_on(inst.u, _a()) == 0
    assert [w for w in zmiany_hosta.wpisy(inst.u) if w["rodzaj"] == "plik"] == []
    capsys.readouterr()


def test_on_wifi_parowanie_kodem_i_polaczenie(inst, monkeypatch, capsys):
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\n192.168.1.20:37123 device model:Pixel_8\n"
                                            "emulator-5554 device model:sdk\n")
    assert android.polecenie_on(inst.u, _a(paruj="192.168.1.20:41234", kod="111111")) == 1      # zły kod
    assert android.polecenie_on(inst.u, _a(paruj="192.168.1.20:41234", kod="12")) == 2           # nie 6 cyfr
    assert android.polecenie_on(inst.u, _a(wifi="192.168.1.20:37123", paruj="192.168.1.20:41234",
                                           kod="123456")) == 0
    st = android.stan_androida(inst.u)
    assert st["wifi"] == st["serial"] == "192.168.1.20:37123"
    argv = [x["argv"] for x in _wywolania(inst.log)]
    assert ["pair", "192.168.1.20:41234", "123456"] in argv and ["connect", "192.168.1.20:37123"] in argv
    assert android.polecenie_on(inst.u, _a(wifi="192.168.1.20;calc")) == 2                       # nie adres
    assert android.polecenie_on(inst.u, _a(urzadzenie="nie-ma-go")) == 1
    capsys.readouterr()


def test_on_kilka_urzadzen_bez_wyboru_i_z_wyborem(inst, monkeypatch, capsys):
    monkeypatch.setenv("ATRAPA_URZADZENIA", URZADZENIA)
    assert android.polecenie_on(inst.u, _a()) == 0
    out = capsys.readouterr().out
    assert android.stan_androida(inst.u)["serial"] is None and "--urzadzenie" in out
    assert "Zawsze zezwalaj" in out and "udev" in out                         # rady dla unauthorized i no permissions
    assert android.polecenie_on(inst.u, _a(urzadzenie="emulator-5554")) == 0
    assert android.stan_androida(inst.u)["serial"] == "emulator-5554"


def test_off_rozlacza_wifi_i_zatrzymuje_serwer(inst):
    android.zapisz_stan(inst.u, {"wlaczony": True, "serial": "192.168.1.20:37123", "wifi": "192.168.1.20:37123"})
    assert android.polecenie_off(inst.u, _a()) == 0
    argv = [x["argv"] for x in _wywolania(inst.log)]
    assert ["disconnect", "192.168.1.20:37123"] in argv and ["kill-server"] in argv
    assert android.stan_androida(inst.u)["wlaczony"] is False
    inst.log.unlink()
    assert android.polecenie_off(inst.u, _a(zostaw_adb=True)) == 0
    assert ["kill-server"] not in [x["argv"] for x in _wywolania(inst.log)]


def test_status_nie_uruchamia_serwera_gdy_telefon_wylaczony(inst, capsys):
    assert android.polecenie_status(inst.u, _a()) == 0
    assert "jeszcze nie włączony" in capsys.readouterr().out
    assert [x["argv"] for x in _wywolania(inst.log)] == [["version"]]           # bez devices (serwer adb nie startuje)
    android.zapisz_stan(inst.u, {"wlaczony": True, "serial": "R58M123ABC"})
    assert android.polecenie_status(inst.u, _a(json=True)) == 0
    s = json.loads(capsys.readouterr().out)
    assert s["wlaczony"] and s["urzadzenia"] == [] and s["adb_wersja"] == "37.0.1"
    assert s["podglad_hq"].startswith("wyłączony")


def test_ekran_uruchamia_scrcpy_w_osobnym_oknie_z_adb_floty(inst, monkeypatch, capsys):
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\nR58M123ABC device usb:1-1 model:SM_A515F\n")
    assert android.polecenie_ekran(inst.u, _a()) == 1                            # telefon wyłączony
    android.zapisz_stan(inst.u, {"wlaczony": True, "serial": "R58M123ABC", "licencja_sdk": {"zaakceptowano": "x"}})
    scrcpy = inst.root / "scrcpy" / ("scrcpy.exe" if WINDOWS else "scrcpy")
    scrcpy.parent.mkdir(parents=True)
    scrcpy.write_bytes(b"")
    monkeypatch.setattr(android, "scrcpy", lambda _u: scrcpy)
    uruchomione = []

    class Proces:
        def __init__(self, argv, **kw):
            uruchomione.append((argv, kw))

        def wait(self, czas=None):
            raise subprocess.TimeoutExpired("scrcpy", czas)

    monkeypatch.setattr(android, "uruchom_okno", Proces)
    assert android.polecenie_ekran(inst.u, _a(bez_dzwieku=True, rozmiar=1024)) == 0
    argv, kw = uruchomione[0]
    assert argv[:3] == [str(scrcpy), "-s", "R58M123ABC"] and "--no-audio" in argv and argv[-2:] == ["--max-size", "1024"]
    assert kw["env"]["ADB"] == str(inst.adb) and kw["env"]["ADB_MDNS"] == "0"
    assert kw["stdin"] is subprocess.DEVNULL and (inst.u.logi / "scrcpy.log").is_file()
    if WINDOWS:
        assert kw["creationflags"] & subprocess.CREATE_NO_WINDOW
    else:
        assert kw["start_new_session"]
    assert "SM A515F" in capsys.readouterr().out


def test_ekran_bez_urzadzenia_nie_otwiera_okna(inst, monkeypatch, capsys):
    android.zapisz_stan(inst.u, {"wlaczony": True, "serial": None})
    monkeypatch.setattr(android, "scrcpy", lambda _u: Path(sys.executable))
    monkeypatch.setattr(android, "uruchom_okno", lambda *a, **k: pytest.fail("bez urządzenia nie ma okna"))
    assert android.polecenie_ekran(inst.u, _a()) == 1
    assert "brak gotowego urządzenia" in capsys.readouterr().err


def test_bez_instalacji_natywnej(tmp_path, capsys):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "nic")})
    for f in (android.polecenie_status, android.polecenie_on, android.polecenie_off, android.polecenie_ekran):
        assert f(u, _a()) == 1
        assert "nie jest zainstalowane natywnie" in capsys.readouterr().err
    assert android.sprawdzenia(u) == []


def test_doctor_telefon_opcjonalny(inst, monkeypatch):
    monkeypatch.setattr(android, "adb", lambda _u: None)
    monkeypatch.setattr(android.sciezki, "platforma", lambda: "windows-x64")
    w = {x["nazwa"]: x for x in android.sprawdzenia(inst.u)}
    assert w["telefon (adb)"]["stan"] == "ok" and "jarvo android on" in w["telefon (adb)"]["opis"]
    assert w["ekran telefonu"]["stan"] == "ok" and "9122" in w["ekran telefonu"]["opis"]
    android.zapisz_stan(inst.u, {"wlaczony": True})
    assert {x["nazwa"]: x for x in android.sprawdzenia(inst.u)}["telefon (adb)"]["stan"] == "uwaga"
    monkeypatch.setattr(android, "adb", lambda _u: inst.adb)
    w = {x["nazwa"]: x for x in android.sprawdzenia(inst.u)}["telefon (adb)"]
    assert w["stan"] == "ok" and "37.0.1" in w["opis"]
    assert [x["argv"] for x in _wywolania(inst.log)] == [["version"]]           # doctor nie startuje serwera adb


def test_parser_jarvo_android():
    p = argparse.ArgumentParser(prog="jarvo")
    sub = p.add_subparsers(dest="polecenie")
    android.dodaj_polecenia(sub)
    a = p.parse_args(["android"])
    assert a.funkcja is android.polecenie_status
    a = p.parse_args(["android", "on", "--wifi", "10.0.0.5:5555", "--akceptuje-licencje"])
    assert a.funkcja is android.polecenie_on and a.wifi == "10.0.0.5:5555" and a.akceptuje_licencje
    assert p.parse_args(["android", "off", "--zostaw-adb"]).zostaw_adb
    a = p.parse_args(["android", "ekran", "--rozmiar", "800"])
    assert a.funkcja is android.polecenie_ekran and a.rozmiar == 800


@pytest.mark.posix_only
def test_klucz_wlasciciela_z_konta_a_nie_z_home(monkeypatch, tmp_path):
    """Terminal agenta ma HOME profilu (H24): klucz adb właściciela idzie z bazy kont przez ADB_VENDOR_KEYS."""
    import pwd
    dom = Path(pwd.getpwuid(os.getuid()).pw_dir)
    monkeypatch.setenv("HOME", str(tmp_path / "profil-agenta"))
    assert android.katalog_adb() == dom / ".android"
    assert android.klucz_wlasciciela() == dom / ".android" / "adbkey"


def test_env_adb_z_kluczem_wlasciciela(inst, monkeypatch):
    klucz = inst.klucze / "adbkey"
    klucz.parent.mkdir(parents=True, exist_ok=True)
    klucz.write_text("x")
    monkeypatch.setattr(android, "klucz_wlasciciela", lambda: klucz)
    env = android.env_adb(inst.u, {"ADB_VENDOR_KEYS": "inny"})
    assert env["ADB_VENDOR_KEYS"].split(os.pathsep) == ["inny", str(klucz)] and env["ADB_MDNS"] == "0"


@pytest.mark.windows_only
def test_klucz_wlasciciela_na_windows_z_profilu_konta(monkeypatch, tmp_path):
    """Windows: adb bierze klucz z profilu konta (SHGetFolderPath), nie z USERPROFILE (sprawdzone na Windows 11):
    katalog_adb też, a ADB_VENDOR_KEYS nie jest potrzebne."""
    prawdziwy = android.katalog_adb()
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profil-agenta"))
    assert android.katalog_adb() == prawdziwy and prawdziwy.name == ".android"
    assert android.klucz_wlasciciela() is None


# ------------------------------------------------------------------ urzadzenie.py w instalacji natywnej

@pytest.fixture
def floty(inst, monkeypatch):
    """Środowisko procesu floty: JARVO_ROOT, wpis platform-tools z atrapą adb w narzedzia.json."""
    (inst.u.stan / "narzedzia.json").write_text(json.dumps({"platform-tools": {
        "wersja": "37.0.1", "katalog": str(inst.root / "pt"), "bin": [], "env": {"ADB_MDNS": "0"}}}), encoding="utf-8")
    monkeypatch.setattr(ur, "adb_natywny", lambda _k: str(inst.adb))
    return inst


def test_urzadzenie_natywnie_telefon_wylaczony_albo_niewlaczany(floty):
    with pytest.raises(ur.BrakUrzadzenia, match="nie jest włączony"):
        ur.Adb().polacz()
    (floty.u.stan / "android.json").write_text(json.dumps({"wlaczony": False}), encoding="utf-8")
    with pytest.raises(ur.BrakUrzadzenia, match="jarvo android off"):
        ur.Adb().polacz()
    assert _wywolania(floty.log) == []                                          # wyłączony: adb nie startuje


def test_urzadzenie_natywnie_bierze_jedyne_gotowe(floty, monkeypatch):
    (floty.u.stan / "android.json").write_text(json.dumps({"wlaczony": True, "serial": None}), encoding="utf-8")
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\nR58M123ABC\tdevice\n")
    adb = ur.Adb()
    assert adb.korzen == floty.root and adb.adb == str(floty.adb) and adb.serial is None
    adb.polacz()
    assert adb.serial == "R58M123ABC"
    w = _wywolania(floty.log)
    assert w[0]["argv"] == ["start-server"] and all(x["mdns"] == "0" for x in w)
    assert ["-s", "R58M123ABC", "get-state"] in [x["argv"] for x in w]


def test_urzadzenie_natywnie_wifi_kilka_i_brak(floty, monkeypatch):
    (floty.u.stan / "android.json").write_text(json.dumps({"wlaczony": True, "serial": "10.0.0.5:5555",
                                                           "wifi": "10.0.0.5:5555"}), encoding="utf-8")
    adb = ur.Adb()
    adb.polacz()
    assert ["connect", "10.0.0.5:5555"] in [x["argv"] for x in _wywolania(floty.log)]
    (floty.u.stan / "android.json").write_text(json.dumps({"wlaczony": True}), encoding="utf-8")
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\nA\tdevice\nB\tdevice\n")
    with pytest.raises(ur.BrakUrzadzenia, match="--urzadzenie"):
        ur.Adb().polacz()
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\nA\tunauthorized\n")
    with pytest.raises(ur.BrakUrzadzenia, match="zaakceptuj"):
        ur.Adb().polacz()


def test_urzadzenie_zmienne_z_otoczenia_wygrywaja(floty, monkeypatch):
    monkeypatch.setenv("JARVO_ANDROID_ADB", "emulator-5554")
    monkeypatch.setenv("JARVO_ADB", str(floty.adb))
    adb = ur.Adb()
    assert adb.serial == "emulator-5554" and adb.adb == str(floty.adb)
    adb.polacz()                                                                # bez android.json: zmienna = zgoda
    assert adb.serial == "emulator-5554"


def test_pomocnicze_testu_na_zywo():
    """tests/live/natywnie_telefon_3d.py: JSON z `--json` po postępie pobierania na stderr i `--dopusc` z macierzy CI."""
    zywo = load_script("tests/live/natywnie_telefon_3d.py", "natywnie_telefon_3d_test")
    wyjscie = ("venv cad: pierwsze użycie, instaluję {56 paczek}\n  three 0.186.1: 100%\n"
               '{\n  "silnik": "x",\n  "stan": {\n    "podglad": {"sposob": "python"}\n  }\n}\n')
    assert zywo.json_z(wyjscie) == {"silnik": "x", "stan": {"podglad": {"sposob": "python"}}}
    with pytest.raises(zywo.Niepowodzenie):
        zywo.json_z("bez JSON")
    assert zywo._dopuszczenia("manimgx=render bez GPU; film=") == {"manimgx": "render bez GPU", "film": "dopuszczone"}
    assert zywo._dopuszczenia("") == {} and set(zywo.PUNKTY) == {"adb", "android", "scrcpy", "cad", "film", "manimgx",
                                                                  "doctor"}


def test_urzadzenie_w_kontenerze_bez_zmian(monkeypatch, tmp_path):
    monkeypatch.delenv("JARVO_ROOT", raising=False)
    monkeypatch.delenv("JARVO_ANDROID_ADB", raising=False)
    monkeypatch.delenv("JARVO_ADB", raising=False)
    adb = ur.Adb()
    assert adb.korzen is None and adb.serial == "jarvo-android:5555" and adb.adb == "adb" and adb.env is None
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path))                             # bez current.json: nie instalacja
    assert ur.Adb().korzen is None
