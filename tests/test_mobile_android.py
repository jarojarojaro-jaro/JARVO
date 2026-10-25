"""Telefon testowy Twórcy aplikacji natywnie (docs/NATYWNIE.md: N12, U04, U05, E13, F08, I24; etap E11):
`jarvo android status|on|off|ekran` (jarvo/android.py), adb floty w urzadzenie.py z instalacji natywnej i telefon
właściciela zostawiony takim, jakim był (dziennik przywróceń urzadzenie.py, tryb demo w pakiet.py).

Bez telefonu, bez sieci i bez prawdziwego adb: instalacja to katalog tymczasowy z `program/current.json`, a adb i scrcpy
to atrapy (tests/atrapy.py), które zapisują wywołania. Telefon właściciela to atrapa adb ze stanem telefonu w pliku
(ATRAPA_TELEFONU z tests/live/natywnie_telefon_3d.py, ta sama co w teście na żywo). Na żywo (prawdziwe platform-tools
i scrcpy z manifestu): tests/live/natywnie_telefon_3d.py.
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
from jarvo import android, przy_uzyciu, rece, sciezki, zmiany_hosta  # noqa: E402

ur = load_script("profiles/jarvo-mobile/scripts/urzadzenie.py", "urzadzenie_natywnie")
zywo = load_script("tests/live/natywnie_telefon_3d.py", "natywnie_telefon_3d_test")

WINDOWS = os.name == "nt"
KATALOG_KLUCZA = android.katalog_klucza                 # prawdziwa funkcja (fixture podmienia ją na katalog atrapy)
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
    f.write(json.dumps({"argv": args, "mdns": os.environ.get("ADB_MDNS"), "home": os.environ.get("HOME"),
                        "log": os.environ.get("ANDROID_ADB_LOG_PATH"),
                        "klucze": os.environ.get("ADB_VENDOR_KEYS")}) + "\n")
if args[:1] == ["-s"]:
    args = args[2:]
# katalog klucza: jak adb (Windows: profil konta, tu ATRAPA_KLUCZE; macOS i Linux: $HOME/.android)
klucze = os.environ.get("ATRAPA_KLUCZE") or (os.path.join(os.environ["HOME"], ".android")
                                             if os.name != "nt" and os.environ.get("HOME") else None)


def wpis_przed(sciezka):
    """Czy dziennik zmian hosta miał wpis dla pliku, zanim atrapa go założyła (D08: wpis przed zmianą)."""
    d = os.environ.get("ATRAPA_DZIENNIK")
    wpisy = [json.loads(x) for x in open(d, encoding="utf-8") if x.strip()] if d and os.path.exists(d) else []
    with open(os.environ["ATRAPA_SLAD"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"plik": sciezka, "wpis_przed": any((w.get("szczegoly") or {}).get("sciezka") == sciezka
                                                               for w in wpisy)}) + "\n")


if args == ["version"]:
    print("Android Debug Bridge version 1.0.41\nVersion 37.0.1-15733141\nInstalled as adb")
elif args == ["start-server"]:
    if klucze and not os.path.exists(os.path.join(klucze, "adbkey")):   # jak adb: klucz przy pierwszym starcie
        for n in ("adbkey", "adbkey.pub"):
            wpis_przed(os.path.join(klucze, n))
        os.makedirs(klucze, exist_ok=True)
        open(os.path.join(klucze, "adbkey"), "w").write("PRYWATNY")
        open(os.path.join(klucze, "adbkey.pub"), "w").write("PUBLICZNY test@jarvo")
    print("* daemon not running; starting now at tcp:5037\n* daemon started successfully")
elif args[:1] == ["devices"]:
    print(os.environ.get("ATRAPA_URZADZENIA", "List of devices attached\n"))
elif args[:1] == ["connect"]:
    print("connected to " + args[1])
elif args[:1] == ["pair"]:
    if args[2] == "123456":
        hosty = os.path.join(klucze, "adb_known_hosts.pb")
        wpis_przed(hosty)
        open(hosty, "ab").write(b"telefon " + args[1].encode())
        print("Successfully paired to " + args[1] + " [guid=adb-XYZ]")
    else:
        print("Failed: Wrong password")
elif args[:2] == ["shell", "getprop"]:
    print("14")
elif args == ["get-state"]:
    print(os.environ.get("ATRAPA_STAN", "device"))
'''


def _wywolania(log: Path) -> list[dict]:
    return [json.loads(w) for w in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []


@pytest.fixture
def inst(tmp_path, monkeypatch):
    """Instalacja natywna w katalogu tymczasowym: current.json z kodem tego repo, atrapa adb jako platform-tools,
    terminal właściciela (bez znaczników procesu floty), klucz adb Jarva poza katalogiem Jarva (jak na Windows)."""
    root = tmp_path / "Jarvo"
    u = sciezki.uklad({"JARVO_ROOT": str(root)})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    u.stan.mkdir(parents=True, exist_ok=True)
    (u.program / "current.json").write_text(json.dumps({"app": str(REPO)}), encoding="utf-8")
    adb = atrapy.program(tmp_path / "pt", "adb", ATRAPA_ADB)
    log = tmp_path / "adb.jsonl"
    klucze = tmp_path / "dom" / ".android"                     # katalog klucza adb na koncie (atrapa)
    for z in (*rece.ZNACZNIKI_FLOTY, "HERMES_HOME", "JARVO_ANDROID_ADB", "JARVO_ADB"):
        monkeypatch.delenv(z, raising=False)
    monkeypatch.setenv("JARVO_ROOT", str(root))
    monkeypatch.setenv("ATRAPA_LOG", str(log))
    monkeypatch.setenv("ATRAPA_KLUCZE", str(klucze))
    monkeypatch.setenv("ATRAPA_SLAD", str(tmp_path / "slad.jsonl"))
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(zmiany_hosta.sciezka(u)))
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\n")
    monkeypatch.setattr(android, "adb", lambda _u: adb)
    monkeypatch.setattr(android, "scrcpy", lambda _u: None)
    monkeypatch.setattr(android, "katalog_adb", lambda: klucze)
    monkeypatch.setattr(android, "katalog_klucza", lambda _u: klucze)
    return argparse.Namespace(u=u, adb=adb, log=log, root=root, klucze=klucze, slad=tmp_path / "slad.jsonl")


def _a(**kw) -> argparse.Namespace:
    baza = dict(akceptuje_licencje=False, wifi=None, paruj=None, kod=None, urzadzenie=None, zostaw_adb=False,
                json=False, bez_dzwieku=False, rozmiar=None, telefon_testowy=False, telefon_prywatny=False)
    return argparse.Namespace(**(baza | kw))


def _slady(inst) -> list[dict]:
    return _wywolania(inst.slad)


def _pliki_w_dzienniku(u) -> dict[str, str]:
    return {w["szczegoly"]["sciezka"]: w["szczegoly"]["sha256"] for w in zmiany_hosta.wpisy(u) if w["rodzaj"] == "plik"}


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


# ------------------------------------------------------------------ licencja Google i właściciel

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
    (inst.u.stan / android.STAN).unlink()
    with open(os.devnull, encoding="utf-8") as nul:                  # proces w tle (Windows: NUL „isatty”)
        wyjscie = io.StringIO()
        assert not android.zgoda_na_licencje(inst.u, _a(), wejscie=nul, wyjscie=wyjscie)
    assert "Bez terminala nie zapytam" in wyjscie.getvalue() and "[t/N]" not in wyjscie.getvalue()


@pytest.mark.parametrize("zmienna", ["HERMES_KANBAN_TASK", "HERMES_WRITE_SAFE_ROOT", "JARVO_DATA_DIR",
                                     "HERMES_CRON_SESSION"])
def test_licencje_on_i_ekran_tylko_wlasciciel(inst, monkeypatch, capsys, zmienna):
    """Proces Jarva (terminal agenta ma JARVO_REPO i Pythona) nie akceptuje licencji Google za właściciela, nie
    włącza telefonu dla floty i nie otwiera okna na jego ekranie: odmowa jak w jarvo/rece.py (proces_floty)."""
    monkeypatch.setenv(zmienna, str(inst.u.dane))
    monkeypatch.setattr(android, "adb", lambda _u: None)
    pobrania = []
    monkeypatch.setattr(przy_uzyciu, "narzedzie", lambda *a, **k: pobrania.append(a) or {})
    wyjscie = io.StringIO()
    assert not android.zgoda_na_licencje(inst.u, _a(akceptuje_licencje=True), wejscie=Tty("t\n"), wyjscie=wyjscie)
    assert zmienna in wyjscie.getvalue() and not android.stan_androida(inst.u).get("licencja_sdk")
    assert android.polecenie_on(inst.u, _a(akceptuje_licencje=True)) == 1
    assert android.polecenie_ekran(inst.u, _a(akceptuje_licencje=True)) == 1
    err = capsys.readouterr().err
    assert err.count("tylko właściciel") == 2 and zmienna in err
    assert pobrania == [] and _wywolania(inst.log) == [] and not (inst.u.stan / android.STAN).exists()
    android.zapisz_stan(inst.u, {"wlaczony": True})
    assert android.polecenie_off(inst.u, _a()) == 0                     # wyłączyć telefon dla floty może każdy
    assert android.polecenie_status(inst.u, _a()) == 0


def test_prywatny_hermes_wlasciciela_nie_jest_flota(inst, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(inst.root.parent / "prywatny-hermes"))
    assert android._odmowa_floty(inst.u, "Telefon testowy włącza") is None


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
    assert st["wlaczony"] is True and st["serial"] == "R58M123ABC" and st["telefon_testowy"] == []
    assert st["log_adb"] == str(inst.u.logi / "adb.log")              # ten sam log serwera dla urzadzenie.py
    w = _wywolania(inst.log)
    assert [x["argv"][0] for x in w[:3]] == ["version", "start-server", "devices"]
    assert all(x["mdns"] == "0" for x in w)                    # bez szukania telefonów w sieci lokalnej
    assert all(x["log"] == str(inst.u.logi / "adb.log") for x in w)   # log serwera w logach Jarva, nie w TEMP
    out = capsys.readouterr().out
    assert "Android 14" in out and "jarvo android ekran" in out and "9122" in out
    assert "przywracają" in out and "--telefon-testowy" in out and "telefon testowy, nie prywatny" in out


def test_nowy_klucz_adb_w_dzienniku_zmian_hosta_przed_zmiana(inst, monkeypatch, capsys):
    """Klucz adb, który założył serwer z `jarvo android on` poza katalogiem Jarva (Windows: profil konta), to ślad:
    wpis „plik” (D08) już PRZED startem serwera (suma „oczekuje”), potem z sumą pliku, żeby `jarvo uninstall` go
    usunął; klucz, który był wcześniej, nie jest nasz i nie trafia do dziennika."""
    assert android.polecenie_on(inst.u, _a()) == 0
    assert [s["wpis_przed"] for s in _slady(inst)] == [True, True]          # adb założył pliki po wpisie
    pliki = _pliki_w_dzienniku(inst.u)
    assert set(pliki) == {str(inst.klucze / "adbkey"), str(inst.klucze / "adbkey.pub")}
    assert pliki[str(inst.klucze / "adbkey")] == zmiany_hosta._sha(b"PRYWATNY")
    assert android.OCZEKUJE not in pliki.values()
    assert android.polecenie_on(inst.u, _a()) == 0                            # drugi raz: bez nowych wpisów
    assert len(_pliki_w_dzienniku(inst.u)) == 2
    raport = zmiany_hosta.cofnij(inst.u, log=None)                            # jarvo uninstall (E13)
    assert {r["wynik"] for r in raport} == {"cofniete"} and not (inst.klucze / "adbkey").exists()
    assert not inst.klucze.exists()                  # katalog .android założył Jarvo: po plikach znika i on (pusty)
    inst.klucze.mkdir(parents=True)
    (inst.klucze / "adbkey").write_text("KLUCZ ANDROID STUDIO")              # cudzy klucz: zostaje poza dziennikiem
    (inst.klucze / "adbkey.pub").write_text("pub")
    assert android.polecenie_on(inst.u, _a()) == 0
    assert _pliki_w_dzienniku(inst.u) == {}
    capsys.readouterr()


def test_przerwany_on_zostawia_wpis_ktory_konczy_nastepny(inst):
    """Przerwanie między startem serwera a sumą: wpis „oczekuje” zostaje (zmiana nigdy bez wpisu), a następne
    `jarvo android on` daje mu sumę pliku, który adb założył po wpisie; wpis bez pliku znika."""
    adbkey = inst.klucze / "adbkey"
    zmiany_hosta.dopisz(inst.u, "plik", sciezka=str(adbkey), sha256=android.OCZEKUJE)
    zmiany_hosta.dopisz(inst.u, "plik", sciezka=str(inst.klucze / "adbkey.pub"), sha256=android.OCZEKUJE)
    zmiany_hosta.dopisz(inst.u, "plik", sciezka=str(inst.klucze / "nie-powstal"), sha256=android.OCZEKUJE)
    inst.klucze.mkdir(parents=True)
    adbkey.write_text("PO WPISIE")
    (inst.klucze / "adbkey.pub").write_text("pub")
    android.dokoncz_slady(inst.u)
    assert _pliki_w_dzienniku(inst.u) == {str(adbkey): zmiany_hosta._sha(b"PO WPISIE"),
                                          str(inst.klucze / "adbkey.pub"): zmiany_hosta._sha(b"pub")}


def test_katalog_klucza_w_dzienniku_gdy_dziennik_zna_katalogi(inst, monkeypatch):
    """Rodzaj „katalog” w zmiany_hosta (bez `dozwolone`: usuwany przy odinstalowaniu tylko pusty): android.py go
    używa, gdy dziennik go zna, a bez niego nie zgaduje."""
    assert not inst.klucze.exists()
    rodzaje = zmiany_hosta.RODZAJE
    monkeypatch.setattr(zmiany_hosta, "RODZAJE", tuple(r for r in rodzaje if r != "katalog"))
    android.slady_przed(inst.u)
    assert [w for w in zmiany_hosta.wpisy(inst.u) if w["rodzaj"] == "katalog"] == []
    monkeypatch.setattr(zmiany_hosta, "RODZAJE", rodzaje)      # bez undo(): to cofnęłoby też ustawienia fixtury
    android.slady_przed(inst.u)
    assert [w["szczegoly"] for w in zmiany_hosta.wpisy(inst.u) if w["rodzaj"] == "katalog"] == [
        {"sciezka": str(inst.klucze)}]
    inst.klucze.mkdir(parents=True)
    (inst.klucze / "adb_usb.ini").write_text("x")   # cudzy plik w katalogu: przy cofaniu zostaje razem z katalogiem
    raport = zmiany_hosta.cofnij(inst.u, rodzaje=["katalog"], log=None)
    assert [r["wynik"] for r in raport] == ["nie-nasze"] and (inst.klucze / "adb_usb.ini").exists()


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
    hosty = inst.klucze / android.ZNANE_HOSTY                                   # sparowane telefony: też ślad (D08)
    assert [s["wpis_przed"] for s in _slady(inst) if s["plik"] == str(hosty)] == [True]
    assert _pliki_w_dzienniku(inst.u)[str(hosty)] == zmiany_hosta._sha(hosty.read_bytes())
    assert android.polecenie_on(inst.u, _a(paruj="192.168.1.21:41234", kod="123456")) == 0      # drugie parowanie
    assert _pliki_w_dzienniku(inst.u)[str(hosty)] == zmiany_hosta._sha(hosty.read_bytes())    # nowa suma naszego
    assert android.polecenie_on(inst.u, _a(wifi="192.168.1.20;calc")) == 2                       # nie adres
    assert android.polecenie_on(inst.u, _a(urzadzenie="nie-ma-go")) == 1
    capsys.readouterr()


def test_on_kilka_urzadzen_bez_wyboru_i_z_wyborem(inst, monkeypatch, capsys):
    monkeypatch.setenv("ATRAPA_URZADZENIA", URZADZENIA)
    assert android.polecenie_on(inst.u, _a()) == 0
    out = capsys.readouterr().out
    assert android.stan_androida(inst.u)["serial"] is None and "--urzadzenie" in out
    assert "Zawsze zezwalaj" in out and "udev" in out                         # rady dla unauthorized i no permissions
    assert android.polecenie_on(inst.u, _a(telefon_testowy=True)) == 2       # oznaczenie bez wybranego urządzenia
    assert android.polecenie_on(inst.u, _a(urzadzenie="emulator-5554")) == 0
    assert android.stan_androida(inst.u)["serial"] == "emulator-5554"


def test_telefon_testowy_oznacza_i_cofa_wlasciciel(inst, monkeypatch, capsys):
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\nR58M123ABC device usb:1-1 model:SM_A515F\n")
    assert android.polecenie_on(inst.u, _a(telefon_testowy=True)) == 0
    assert android.stan_androida(inst.u)["telefon_testowy"] == ["R58M123ABC"]
    assert "wolno czyścić dane" in capsys.readouterr().out
    assert android.polecenie_on(inst.u, _a()) == 0                                 # zostaje przy kolejnym on
    assert android.stan_androida(inst.u)["telefon_testowy"] == ["R58M123ABC"]
    assert android.polecenie_on(inst.u, _a(telefon_prywatny=True)) == 0
    assert android.stan_androida(inst.u)["telefon_testowy"] == []
    assert android.polecenie_on(inst.u, _a(telefon_testowy=True, telefon_prywatny=True)) == 2
    capsys.readouterr()


def test_off_rozlacza_wifi_i_zatrzymuje_serwer(inst):
    android.zapisz_stan(inst.u, {"wlaczony": True, "serial": "192.168.1.20:37123", "wifi": "192.168.1.20:37123"})
    assert android.polecenie_off(inst.u, _a()) == 0
    argv = [x["argv"] for x in _wywolania(inst.log)]
    assert ["disconnect", "192.168.1.20:37123"] in argv and ["kill-server"] in argv
    assert argv.index(["start-server"]) < argv.index(["disconnect", "192.168.1.20:37123"])   # serwer z plikiem, nie potok
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
    assert s["podglad_hq"].startswith("wyłączony") and s["zalegle_przywrocenia"] == {}


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
    a = p.parse_args(["android", "on", "--wifi", "10.0.0.5:5555", "--akceptuje-licencje", "--telefon-testowy"])
    assert a.funkcja is android.polecenie_on and a.wifi == "10.0.0.5:5555" and a.akceptuje_licencje
    assert a.telefon_testowy and not a.telefon_prywatny
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


@pytest.mark.posix_only
def test_posix_klucz_adb_jarva_w_katalogu_jarva(inst, monkeypatch, capsys):
    """macOS i Linux: serwer adb Jarva ma HOME `<stan>/adb-dom`, więc klucz i sparowane telefony powstają w katalogu
    Jarva (znikają z nim), a katalog domowy właściciela i dziennik zmian hosta zostają bez zmian."""
    monkeypatch.setattr(android, "katalog_klucza", KATALOG_KLUCZA)
    monkeypatch.delenv("ATRAPA_KLUCZE")                     # atrapa jak adb: klucz w $HOME/.android
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\nR58M123ABC device usb:1-1 model:SM_A515F\n")
    assert android.polecenie_on(inst.u, _a()) == 0
    dom = inst.u.stan / "adb-dom"
    assert all(x["home"] == str(dom) for x in _wywolania(inst.log))
    assert (dom / ".android" / "adbkey").read_text() == "PRYWATNY" and not inst.klucze.exists()
    assert zmiany_hosta.wpisy(inst.u) == []
    capsys.readouterr()


def test_env_adb_z_kluczem_wlasciciela(inst, monkeypatch):
    klucz = inst.klucze / "adbkey"
    klucz.parent.mkdir(parents=True, exist_ok=True)
    klucz.write_text("x")
    monkeypatch.setattr(android, "klucz_wlasciciela", lambda: klucz)
    env = android.env_adb(inst.u, {"ADB_VENDOR_KEYS": "inny"})
    assert env["ADB_VENDOR_KEYS"].split(os.pathsep) == ["inny", str(klucz)] and env["ADB_MDNS"] == "0"
    assert env["ANDROID_ADB_LOG_PATH"] == str(inst.u.logi / "adb.log")
    assert env.get("HOME") == (None if WINDOWS else str(inst.u.stan / "adb-dom"))


@pytest.mark.windows_only
def test_klucz_wlasciciela_na_windows_z_profilu_konta(monkeypatch, tmp_path):
    """Windows: adb bierze klucz z profilu konta (SHGetFolderPath), nie z USERPROFILE (sprawdzone na Windows 11):
    katalog_adb też, a ADB_VENDOR_KEYS nie jest potrzebne."""
    prawdziwy = android.katalog_adb()
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profil-agenta"))
    assert android.katalog_adb() == prawdziwy and prawdziwy.name == ".android"
    assert android.klucz_wlasciciela() is None
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "Jarvo")})
    assert KATALOG_KLUCZA(u) == prawdziwy and android.dom_adb(u) is None


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
    (floty.u.stan / "android.json").write_text(json.dumps({"wlaczony": True, "serial": None,
                                                           "log_adb": str(floty.u.logi / "adb.log")}),
                                               encoding="utf-8")
    monkeypatch.setenv("ATRAPA_URZADZENIA", "List of devices attached\nR58M123ABC\tdevice\n")
    adb = ur.Adb()
    assert adb.korzen == floty.root and adb.adb == str(floty.adb) and adb.serial is None
    adb.polacz()
    assert adb.serial == "R58M123ABC"
    w = _wywolania(floty.log)
    assert w[0]["argv"] == ["start-server"] and all(x["mdns"] == "0" for x in w)
    assert w[0]["log"] == str(floty.u.logi / "adb.log")                          # ten sam log serwera co jarvo android
    if not WINDOWS:                                                              # HOME adb Jarva (Windows: profil konta)
        assert w[0]["home"] == str(floty.u.stan / "adb-dom") and (floty.u.stan / "adb-dom").is_dir()
    assert ["-s", "R58M123ABC", "get-state"] in [x["argv"] for x in w]
    adb.polacz()                                                                 # drugi raz: bez adb (raz na proces)
    assert len(_wywolania(floty.log)) == len(w)


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
    wyjscie = ("venv cad: pierwsze użycie, instaluję {56 paczek}\n  three 0.186.1: 100%\n"
               '{\n  "silnik": "x",\n  "stan": {\n    "podglad": {"sposob": "python"}\n  }\n}\n')
    assert zywo.json_z(wyjscie) == {"silnik": "x", "stan": {"podglad": {"sposob": "python"}}}
    with pytest.raises(zywo.Niepowodzenie):
        zywo.json_z("bez JSON")
    assert zywo._dopuszczenia("manimgx=render bez GPU; film=") == {"manimgx": "render bez GPU", "film": "dopuszczone"}
    assert zywo._dopuszczenia("") == {} and set(zywo.PUNKTY) == {"adb", "android", "scrcpy", "przywracanie", "cad",
                                                                  "film", "manimgx", "doctor"}
    assert zywo.roznice_telefonu(zywo.TELEFON, {**zywo.TELEFON, "polecenia": ["x"]}) == []
    assert zywo.roznice_telefonu(zywo.TELEFON, {**zywo.TELEFON, "dane": "1"}) == ["dane: '0' → '1'"]


def test_test_na_zywo_bez_instalacji_kod_2_i_zle_argumenty(tmp_path, capsys):
    assert zywo.main(["--wyniki", str(tmp_path / "w"), "--korzen", str(tmp_path / "brak")]) == 2
    assert "brak instalacji natywnej" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        zywo.main(["--wyniki", str(tmp_path / "w"), "--punkty", "adb,nie-ma"])


def test_urzadzenie_w_kontenerze_bez_zmian(monkeypatch, tmp_path):
    monkeypatch.delenv("JARVO_ROOT", raising=False)
    monkeypatch.delenv("JARVO_ANDROID_ADB", raising=False)
    monkeypatch.delenv("JARVO_ADB", raising=False)
    adb = ur.Adb()
    assert adb.korzen is None and adb.serial == "jarvo-android:5555" and adb.adb == "adb" and adb.env is None
    assert ur.urzadzenie_testowe(adb) == {"jednorazowe": True, "przez_siec": False,
                                          "dlaczego": "urządzenie floty w kontenerze"}
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path))                             # bez current.json: nie instalacja
    assert ur.Adb().korzen is None


# ------------------------------------------------------------------ telefon właściciela: każde ustawienie wraca (U04)

@pytest.fixture
def telefon(inst, monkeypatch, tmp_path):
    """Telefon właściciela przez USB jako atrapa adb ze stanem w pliku (ustawienia inne niż domyślne, dane
    komórkowe wyłączone), urządzenie floty z `jarvo android on`."""
    adb = atrapy.program(tmp_path / "tel", "adb", zywo.ATRAPA_TELEFONU)
    plik = tmp_path / "telefon.json"
    plik.write_text(json.dumps(zywo.TELEFON), encoding="utf-8")
    monkeypatch.setenv("ATRAPA_TELEFON", str(plik))
    monkeypatch.setattr(ur, "adb_natywny", lambda _k: str(adb))
    monkeypatch.setattr(ur, "CZEKAJ_S", 0)
    monkeypatch.setattr(ur.time, "sleep", lambda s: None)
    android.zapisz_stan(inst.u, {"wlaczony": True, "serial": zywo.TELEFON["serial"]})

    def czytaj() -> dict:
        return json.loads(plik.read_text(encoding="utf-8"))

    def ustaw(**kw) -> None:
        plik.write_text(json.dumps({**czytaj(), **kw}), encoding="utf-8")

    return argparse.Namespace(u=inst.u, adb=adb, czytaj=czytaj, ustaw=ustaw, dziennik=inst.u.stan / ur.PLIK_PRZYWROCEN)


def test_wrogie_na_telefonie_wlasciciela_zostawia_kazde_ustawienie(telefon, tmp_path, capsys):
    """Blokada z recenzji E11: po testach wrogich telefon właściciela ma te same ustawienia co przed nimi (font_scale
    1.15, nadpisany rozmiar ekranu, tryb nocny „auto”, Wi-Fi, dane komórkowe wyłączone, uprawnienia), a nie wartości
    domyślne; bez pm clear, logcat -c i plików w pamięci telefonu."""
    assert ur.main(["wrogie", "pl.jarvo.proba", str(tmp_path / "wrogie")]) == 0
    po = telefon.czytaj()
    assert zywo.roznice_telefonu(zywo.TELEFON, po) == []
    r = json.loads((tmp_path / "wrogie" / "wrogie.json").read_text(encoding="utf-8"))
    st = {w["id"]: w["status"] for w in r["wyniki"]}
    assert st == {**{s: "ok" for s in ur.SCENARIUSZE}, "swieza-instalacja": "not_run"}
    assert "emulatorze albo telefonie testowym" in r["wyniki"][-1]["dlaczego"]
    assert r["telefon_zmieniony"] == [] and r["urzadzenie"]["telefon"]["jednorazowe"] is False
    p = po["polecenia"]
    assert "settings put system font_scale 1.15" in p and "wm size 1080x2000" in p and "wm density reset" in p
    assert "cmd uimode night auto" in p and "svc data enable" not in p and "svc data disable" not in p
    assert "pm grant pl.jarvo.proba android.permission.CAMERA" in p
    assert not any("INTERNET" in x or "POST_NOTIFICATIONS" in x for x in p if x.startswith("pm "))
    assert not po.get("dane_wyczyszczone") and "logcat -c" not in p and not po.get("pliki")
    assert not any("/sdcard" in x for x in p) and not telefon.dziennik.exists()
    capsys.readouterr()


def test_wrogie_offline_przez_wifi_nie_odcina_adb(telefon, tmp_path):
    android.zapisz_stan(telefon.u, {"wlaczony": True, "serial": "192.168.1.20:37123", "wifi": "192.168.1.20:37123"})
    telefon.ustaw(serial="192.168.1.20:37123")
    r = ur.wrogie(ur.Adb(), "pl.jarvo.proba", tmp_path / "w", ["offline", "ciemny"])
    st = {w["id"]: w for w in r["wyniki"]}
    assert st["offline"]["status"] == "not_run" and "Wi-Fi" in st["offline"]["dlaczego"]
    assert st["ciemny"]["status"] == "ok"
    p = telefon.czytaj()["polecenia"]
    assert not any(x.startswith(("cmd connectivity", "svc ")) for x in p)


def test_zerwane_polaczenie_zostawia_dziennik_i_przywraca_przy_nastepnym_poleceniu(telefon, tmp_path, capsys):
    """Kabel wyjęty po wyłączeniu Wi-Fi w teście offline: kod 4 z listą zmian, wpisy w <stan>/android-przywroc.json;
    po podłączeniu `urzadzenie.py przywroc` przywraca wszystko i czyści dziennik."""
    telefon.ustaw(zerwij_po="svc wifi disable")
    assert ur.main(["wrogie", "pl.jarvo.proba", str(tmp_path / "w"), "--tylko", "offline"]) == 4
    err = capsys.readouterr().err
    assert "UWAGA" in err and "tryb samolotowy (było: 0)" in err and "Wi-Fi (było: 1)" in err
    assert telefon.czytaj()["samolot"] == "1" and telefon.czytaj()["wifi"] == "0"
    zalegle = json.loads(telefon.dziennik.read_text(encoding="utf-8"))[zywo.TELEFON["serial"]]
    assert [w["ustawienie"] for w in zalegle] == ["samolot", "wifi"]
    assert ur.main(["przywroc"]) == 3                                         # telefon dalej odłączony
    assert "zaległe przywrócenia" in capsys.readouterr().err
    telefon.ustaw(podlaczony=True)
    assert ur.main(["przywroc"]) == 0
    out = capsys.readouterr().out
    assert "Przywrócone:" in out and "Wi-Fi (było: 1)" in out and "tryb samolotowy (było: 0)" in out
    assert zywo.roznice_telefonu(zywo.TELEFON, telefon.czytaj()) == [] and not telefon.dziennik.exists()
    assert ur.main(["przywroc"]) == 0 and "Nic do przywrócenia" in capsys.readouterr().out


def test_wrogie_nie_rusza_przy_zaleglych_zmianach(telefon, tmp_path, capsys):
    """Zaległa zmiana, której telefon nie przyjmuje: nowy test by ją odczytał jako ustawienie właściciela, więc kod 4
    bez żadnej nowej zmiany."""
    telefon.ustaw(samolot="1", odmawia=["cmd connectivity airplane-mode disable"])
    telefon.dziennik.write_text(json.dumps({zywo.TELEFON["serial"]: [
        {"id": "a1", "ustawienie": "samolot", "wartosc": "0", "sprawdz": True}]}), encoding="utf-8")
    assert ur.main(["wrogie", "pl.jarvo.proba", str(tmp_path / "w")]) == 4
    assert "urzadzenie.py przywroc" in capsys.readouterr().err
    p = telefon.czytaj()["polecenia"]
    assert "settings put system font_scale 2.0" not in p and not (tmp_path / "w" / "wrogie.json").exists()
    assert json.loads(telefon.dziennik.read_text(encoding="utf-8"))[zywo.TELEFON["serial"]][0]["id"] == "a1"


def test_wartosc_nie_do_odczytania_na_telefonie_nie_zmienia(telefon, tmp_path):
    telefon.ustaw(noc="nieznany-tryb", font_scale="")
    r = ur.wrogie(ur.Adb(), "pl.jarvo.proba", tmp_path / "w", ["ciemny", "duza-czcionka"])
    st = {w["id"]: w for w in r["wyniki"]}
    assert st["ciemny"]["status"] == st["duza-czcionka"]["status"] == "not_run"
    assert "tryb ciemny" in st["ciemny"]["dlaczego"] and "rozmiar czcionki" in st["duza-czcionka"]["dlaczego"]
    p = telefon.czytaj()["polecenia"]
    assert "cmd uimode night yes" not in p and "settings put system font_scale 2.0" not in p


@pytest.mark.parametrize("jak", ["emulator", "telefon-testowy"])
def test_emulator_i_telefon_testowy_wlasciciela_pozwalaja_wyczyscic_dane(telefon, tmp_path, jak):
    if jak == "emulator":
        telefon.ustaw(qemu="1")
    else:
        android.zapisz_stan(telefon.u, {"wlaczony": True, "serial": zywo.TELEFON["serial"],
                                        "telefon_testowy": [zywo.TELEFON["serial"]]})
    r = ur.wrogie(ur.Adb(), "pl.jarvo.proba", tmp_path / "w", ["swieza-instalacja", "start"])
    assert {w["id"]: w["status"] for w in r["wyniki"]} == {"swieza-instalacja": "ok", "start": "ok"}
    assert telefon.czytaj()["dane_wyczyszczone"] is True and "logcat -c" in telefon.czytaj()["polecenia"]


def test_brak_odpowiedzi_adb_to_blad_a_ustawienie_wraca(telefon, tmp_path, monkeypatch):
    """subprocess.TimeoutExpired z adb nie przechodzi jako ślad stosu: test ma status blad, a zmienione wcześniej
    ustawienie wraca do wartości sprzed testu."""
    prawdziwy = ur.subprocess.run

    def run(argv, **kw):
        if argv[-1:] == ["am force-stop pl.jarvo.proba"]:
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        return prawdziwy(argv, **kw)

    monkeypatch.setattr(ur.subprocess, "run", run)
    r = ur.wrogie(ur.Adb(), "pl.jarvo.proba", tmp_path / "w", ["duza-czcionka"])
    w = r["wyniki"][0]
    assert w["status"] == "blad" and "brak odpowiedzi" in w["dlaczego"] and "nieprzywrocone" not in w
    assert telefon.czytaj()["font_scale"] == "1.15" and not telefon.dziennik.exists()


def test_brak_odpowiedzi_adb_przy_laczeniu_to_kod_3(telefon, monkeypatch, capsys):
    prawdziwy = ur.subprocess.run

    def run(argv, **kw):
        if argv[-1:] == ["get-state"]:
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        return prawdziwy(argv, **kw)

    monkeypatch.setattr(ur.subprocess, "run", run)
    assert ur.main(["status"]) == 3
    assert "brak odpowiedzi" in capsys.readouterr().err


def test_dziennik_przywrocen_przyjmuje_tylko_znane_ustawienia(telefon, capsys):
    """Dziennik na dysku daje tylko nazwę i wartość; polecenie składa kod, więc wpis z dopisanym poleceniem powłoki
    jest pomijany i usuwany, a nie wykonywany."""
    for ustawienie, wartosc in (("wm_size", "720x1280; reboot"), ("noc", "yes && rm -rf /sdcard"),
                                ("uprawnienie", "pl.x android.permission.CAMERA;reboot"), ("cos", "1")):
        with pytest.raises(ValueError):
            ur.polecenia_przywrocenia(ustawienie, wartosc)
    assert ur.polecenia_przywrocenia("wm_size", "-") == ["wm size reset"]
    assert ur.polecenia_przywrocenia("font_scale", "null") == ["settings delete system font_scale"]
    telefon.dziennik.write_text(json.dumps({zywo.TELEFON["serial"]: [
        {"id": "z1", "ustawienie": "wm_size", "wartosc": "720x1280; reboot"}]}), encoding="utf-8")
    assert ur.main(["przywroc"]) == 0
    assert not any("reboot" in x for x in telefon.czytaj().get("polecenia", [])) and not telefon.dziennik.exists()
    capsys.readouterr()


def test_awarie_na_telefonie_tylko_testowanej_aplikacji_od_startu_testu():
    class Atrapa:
        def __init__(self, tekst):
            self.tekst = tekst

        def sh(self, polecenie, timeout=60):
            assert "-v epoch" in polecenie
            return self.tekst

    linie = ("1729850000.100  1234  1234 E AndroidRuntime: FATAL EXCEPTION: main\n"
             "1729850000.101  1234  1234 E AndroidRuntime: Process: com.bank.prywatny, PID: 1234\n"
             "1729850010.100  2222  2222 E AndroidRuntime: FATAL EXCEPTION: main\n"
             "1729850010.101  2222  2222 E AndroidRuntime: Process: pl.jarvo.proba, PID: 2222\n"
             "1729849990.000  3333  3333 E ReactNativeJS: TypeError: stary błąd sprzed testu\n"
             "1729850011.000  2222  2222 E ReactNativeJS: TypeError: undefined is not a function\n")
    wynik = ur.awarie(Atrapa(linie), "pl.jarvo.proba", od=1729850005)
    assert len(wynik) == 3 and not any("bank" in x or "stary" in x for x in wynik)
    assert "FATAL EXCEPTION" in wynik[0] and "pl.jarvo.proba" in wynik[1] and "undefined" in wynik[2]


def test_off_przywraca_zalegle_ustawienia_telefonu(telefon, monkeypatch, capsys):
    """`jarvo android off` po przerwanym teście: najpierw ustawienia telefonu (ten sam kod urzadzenie.py z aktywnej
    wersji), potem wyłączenie dla floty; status i doctor mówią o zaległych zmianach."""
    monkeypatch.setattr(android, "adb", lambda _u: telefon.adb)
    telefon.ustaw(font_scale="2.0", noc="yes")
    telefon.dziennik.write_text(json.dumps({zywo.TELEFON["serial"]: [
        {"id": "f1", "ustawienie": "font_scale", "wartosc": "1.15", "sprawdz": True},
        {"id": "n1", "ustawienie": "noc", "wartosc": "auto", "sprawdz": True}]}), encoding="utf-8")
    zalegle = {zywo.TELEFON["serial"]: ["rozmiar czcionki (było: 1.15)", "tryb ciemny (było: auto)"]}
    assert android.zalegle_przywrocenia(telefon.u) == zalegle
    w = {x["nazwa"]: x for x in android.sprawdzenia(telefon.u)}
    assert w["ustawienia telefonu"]["stan"] == "uwaga" and "jarvo android off" in w["ustawienia telefonu"]["rada"]
    assert android.polecenie_status(telefon.u, _a()) == 0 and "UWAGA" in capsys.readouterr().out
    assert android.polecenie_off(telefon.u, _a()) == 0
    assert "Przywróciłem" in capsys.readouterr().out
    po = telefon.czytaj()
    assert po["font_scale"] == "1.15" and po["noc"] == "auto" and not telefon.dziennik.exists()
    assert android.stan_androida(telefon.u)["wlaczony"] is False


def test_off_bez_telefonu_mowi_co_zostalo(telefon, monkeypatch, capsys):
    monkeypatch.setattr(android, "adb", lambda _u: telefon.adb)
    telefon.ustaw(podlaczony=False)
    telefon.dziennik.write_text(json.dumps({zywo.TELEFON["serial"]: [
        {"id": "f1", "ustawienie": "font_scale", "wartosc": "1.15", "sprawdz": True}]}), encoding="utf-8")
    assert android.polecenie_off(telefon.u, _a()) == 1
    assert "rozmiar czcionki (było: 1.15)" in capsys.readouterr().err and telefon.dziennik.exists()


def _pakiet_i_aplikacja(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "profiles" / "jarvo-mobile" / "scripts"))
    import pakiet
    monkeypatch.setitem(sys.modules, "urzadzenie", ur)            # ten sam moduł co atrapa w tym teście
    app = tmp_path / "app"
    app.mkdir()
    (app / "jarvo.app.json").write_text(json.dumps({"pakiet_android": "pl.jarvo.proba", "scheme": "jarvoproba"}),
                                        encoding="utf-8")
    return pakiet, app


def test_pakiet_zrzuty_android_przywraca_tryb_demo(telefon, tmp_path, monkeypatch):
    """pakiet.py zrzuty --zrodlo android: zgoda na tryb demo paska stanu i sam tryb wracają do stanu sprzed zrzutów
    (wcześniej sysui_demo_allowed zostawało na 1)."""
    pakiet, app = _pakiet_i_aplikacja(tmp_path, monkeypatch)
    out = pakiet.ekrany_android(app, ["/", "/oferta"])
    assert set(out) == {"android:/", "android:/oferta"} and all(p.is_file() for p in out.values())
    po = telefon.czytaj()
    assert po["demo_zgoda"] == "null" and po["demo"] is False and not telefon.dziennik.exists()
    p = po["polecenia"]
    assert "settings put global sysui_demo_allowed 1" in p and "settings delete global sysui_demo_allowed" in p
    telefon.ustaw(demo_zgoda="???")                                   # nie do odczytania: bez trybu demo na telefonie
    with pytest.raises(pakiet.Blad, match="sysui_demo_allowed"):
        pakiet.ekrany_android(app, ["/"])
    assert telefon.czytaj()["demo_zgoda"] == "???"


def test_pakiet_tryb_demo_wraca_po_bledzie_w_polowie(telefon, tmp_path, monkeypatch):
    """Telefon odrzuca polecenie trybu demo w połowie: wpis zostaje (trybu demo nie da się odczytać), więc wyjście
    z trybu demo i zgoda wracają mimo błędu, a agent dostaje błąd adb zamiast śladu stosu."""
    pakiet, app = _pakiet_i_aplikacja(tmp_path, monkeypatch)
    telefon.ustaw(odmawia=["am broadcast -a com.android.systemui.demo -e command battery -e level 100 -e plugged false"])
    with pytest.raises(pakiet.Blad, match="adb"):
        pakiet.ekrany_android(app, ["/"])
    po = telefon.czytaj()
    assert po["demo"] is False and po["demo_zgoda"] == "null" and not telefon.dziennik.exists()
    p = po["polecenia"]
    assert p.index("am broadcast -a com.android.systemui.demo -e command exit") < \
        p.index("settings delete global sysui_demo_allowed")                       # przywrócenie od końca


# ------------------------------------------------------------------ jarvo_link.py --android natywnie (I24)

def test_jarvo_link_android_natywnie_bez_martwego_linku(inst, tmp_path):
    env = {**os.environ, "HERMES_HOME": str(tmp_path / "dom"), "JARVO_ROOT": str(inst.root)}
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "jarvo_link.py"), "--android"], env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 3 and r.stdout == ""
    assert "I24" in r.stderr and "jarvo android ekran" in r.stderr
    assert not (tmp_path / "dom" / "jarvo" / "state" / "preview-links.json").exists()   # żadnego tokenu
