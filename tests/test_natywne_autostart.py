"""Autostart nadzorcy i dziennik zmian hosta (docs/NATYWNIE.md: H22, c2 „Autostart”, N08, D08, c4 uninstall).

Polecenia systemu (schtasks, launchctl, systemctl, loginctl) idą do atrapy ze stanem w pamięci, a rejestr Windows do
atrapy winreg: testy wszystkich trzech systemów biegną na każdym systemie i niczego nie zmieniają w komputerze.
Na Windows parser Harmonogramu sprawdza nasz XML w pamięci (bez rejestracji). Prawdziwy Harmonogram zadań i zapis
w rejestrze tylko na runnerze CI (zmienna CI), z unikalną nazwą i sprzątaniem: komputer właściciela zostaje
nietknięty.
"""
from __future__ import annotations

import json
import ntpath
import os
import plistlib
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import autostart, sciezki, zmiany_hosta  # noqa: E402

NS = {"t": autostart.NS}
SID = "S-1-5-21-1111111111-2222222222-3333333333-1001"
ARGV_POSIX = ["/opt/jarvo/program/python/bin/python3", "-I", "-X", "utf8", "/opt/jarvo/program/app/1.0/jarvo/start.py",
              "serwis"]
NA_CI = pytest.mark.skipif(not os.environ.get("CI"), reason="prawdziwy Harmonogram i rejestr tylko na runnerze CI")


def _program(argv0: str) -> str:
    return re.split(r"[\\/]", argv0)[-1].lower().removesuffix(".exe")


class Host:
    """Atrapa `wykonaj(argv) -> (kod, wyjście)` ze stanem: Harmonogram zadań, launchctl, systemctl i loginctl.
    Zadanie wraca z /Query /XML tak jak z Windows: CRLF, bez wartości domyślnych, UserId wyzwalaczy jako nazwa."""

    def __init__(self):
        self.polecenia: list[list[str]] = []
        self.zadania: dict[str, str] = {}
        self.dzialajace: set[str] = set()
        self.odmowa_create = False           # polityka blokuje Harmonogram
        self.odmowa_zapasowych = False       # Harmonogram nie przyjmuje odblokowania i wyzwalacza czasu
        self.odmowa_delete = False
        self.agenci: dict[str, str] = {}
        self.odmowa_bootstrap = False
        self.bus = True
        self.wlaczone: set[str] = set()
        self.aktywne: set[str] = set()
        self.linger = False

    def __call__(self, argv):
        argv = [str(a) for a in argv]
        self.polecenia.append(argv)
        return getattr(self, "_" + _program(argv[0]))(argv[1:])

    def kroki(self) -> list[tuple[str, ...]]:
        """Polecenia bez ścieżek programów: [("schtasks", "/Query"), ("launchctl", "print"), …]."""
        return [(_program(p[0]), *(p[2:3] if _program(p[0]) == "systemctl" else p[1:2])) for p in self.polecenia]

    def _schtasks(self, a):
        nazwa = a[a.index("/TN") + 1] if "/TN" in a else None
        if a[0] == "/Create":
            tekst = Path(a[a.index("/XML") + 1]).read_bytes().decode("utf-16")
            if self.odmowa_create or (self.odmowa_zapasowych and "SessionStateChangeTrigger" in tekst):
                return 1, "ERROR: Odmowa dostępu.\r\n"
            tekst = re.sub(r"\n\s*<(Enabled|MultipleInstancesPolicy)>(true|IgnoreNew)</\1>", "", tekst)
            tekst = re.sub(r"(<(?:Logon|SessionStateChange)Trigger>(?:(?!</).)*?<UserId>)S-1-5-[^<]+", r"\1HOST\\ola",
                           tekst, flags=re.S)
            self.zadania[nazwa] = tekst.replace("\n", "\r\n")
            return 0, f'SUCCESS: The scheduled task "{nazwa}" has successfully been created.\r\n'
        if a[0] == "/Query" and nazwa is None:
            return 0, "".join(f'"\\{n}","N/A","Ready"\r\n' for n in [*self.zadania, "Microsoft\\Windows\\Inne"])
        if nazwa not in self.zadania:
            return 1, "ERROR: Nie można odnaleźć określonego pliku.\r\n"
        if a[0] == "/Query" and "/XML" in a:
            return 0, self.zadania[nazwa]
        if a[0] == "/Query":
            dziala = nazwa in self.dzialajace
            pola = ["HOST", "\\" + nazwa, "N/A", "Running" if dziala else "Ready", "Interactive only", "N/A",
                    "267009" if dziala else "267011", "Jarvo"]
            return 0, ",".join(f'"{p}"' for p in pola) + "\r\n"
        if a[0] == "/Run":
            self.dzialajace.add(nazwa)
            return 0, f'SUCCESS: Attempted to run the scheduled task "{nazwa}".\r\n'
        if a[0] == "/Delete":
            if self.odmowa_delete:
                return 1, "ERROR: Odmowa dostępu.\r\n"
            del self.zadania[nazwa]
            return 0, f'SUCCESS: The scheduled task "{nazwa}" was successfully deleted.\r\n'
        raise AssertionError(f"nieoczekiwane schtasks {a}")

    def _launchctl(self, a):
        et = a[-1].rsplit("/", 1)[-1]
        if a[0] == "bootstrap":
            et = plistlib.loads(Path(a[2]).read_bytes())["Label"]
            if self.odmowa_bootstrap:
                return 5, "Bootstrap failed: 5: Input/output error\n"
            if et in self.agenci:
                return 37, "Bootstrap failed: 37: Operation already in progress\n"
            self.agenci[et] = a[2]
            return 0, ""
        if et not in self.agenci:
            return 113, f'Could not find service "{et}" in domain for user gui: 501\n'
        if a[0] == "print":
            return 0, (f"{a[1]} = {{\n\tactive count = 1\n\tpath = {self.agenci[et]}\n\tstate = running\n\n"
                       "\tpid = 4242\n}\n")
        if a[0] == "bootout":
            del self.agenci[et]
            return 0, ""
        if a[0] == "kickstart":
            return 0, ""
        raise AssertionError(f"nieoczekiwane launchctl {a}")

    def _systemctl(self, a):
        assert a[0] == "--user"
        a = a[1:]
        if not self.bus:
            return 1, "Failed to connect to bus: No medium found\n"
        if a[0] in ("show-environment", "daemon-reload"):
            return 0, "HOME=/home/ola\n" if a[0] == "show-environment" else ""
        nazwa = a[1] if a[0] == "show" else a[-1]
        if a[0] == "enable":
            self.wlaczone.add(nazwa)
            if "--now" in a:
                self.aktywne.add(nazwa)
            return 0, ""
        if a[0] == "disable":
            self.wlaczone.discard(nazwa)
            if "--now" in a:
                self.aktywne.discard(nazwa)
            return 0, ""
        if a[0] == "is-enabled":
            return (0, "enabled\n") if nazwa in self.wlaczone else (1, "disabled\n")
        if a[0] == "is-active":
            return (0, "active\n") if nazwa in self.aktywne else (3, "inactive\n")
        if a[0] == "show":
            return 0, "4343\n" if nazwa in self.aktywne else "0\n"
        raise AssertionError(f"nieoczekiwane systemctl {a}")

    def _loginctl(self, a):
        if a[0] == "show-user":
            return 0, "yes\n" if self.linger else "no\n"
        if a[0] in ("enable-linger", "disable-linger"):
            self.linger = a[0] == "enable-linger"
            return 0, ""
        raise AssertionError(f"nieoczekiwane loginctl {a}")


class Rejestr:
    """Atrapa zmiany_hosta.Rejestr: wartości HKCU w słowniku."""

    def __init__(self, wartosci=None):
        self.wartosci = dict(wartosci or {})
        self.ogloszenia = 0

    def czytaj(self, klucz, nazwa):
        return self.wartosci.get((klucz, nazwa))

    def zapisz(self, klucz, nazwa, wartosc, typ):
        self.wartosci[(klucz, nazwa)] = (wartosc, typ)

    def usun(self, klucz, nazwa):
        self.wartosci.pop((klucz, nazwa), None)

    def oglos(self):
        self.ogloszenia += 1


@pytest.fixture
def u(tmp_path):
    return sciezki.uklad({"JARVO_ROOT": str(tmp_path / "jarvo")})


@pytest.fixture
def host(monkeypatch):
    monkeypatch.setattr(autostart, "_uzytkownik_windows", lambda: SID)
    monkeypatch.setattr(autostart, "_uzytkownik_posix", lambda: "ola")
    monkeypatch.setattr(autostart, "PRZERWA_LAUNCHCTL", 0)
    return Host()


def argv_windows(u) -> list[str]:
    """Polecenie nadzorcy z pythonw.exe; na Linuksie i macOS ścieżka programu udaje Windows, skrypt jest pod
    u.program (po tym poznajemy nasz wpis HKCU Run)."""
    program = str(u.program / "python" / "pythonw.exe") if os.name == "nt" else r"C:\Jarvo\python\pythonw.exe"
    return [program, "-I", "-X", "utf8", str(u.program / "app" / "1.0" / "jarvo" / "start.py"), "serwis"]


def _tagi(e) -> list[str]:
    return [d.tag.rsplit("}", 1)[-1] for d in e]


# ---------------------------------------------------------------- dziennik zmian hosta

def test_dziennik_bez_powtorzen_bez_sekretow_i_odporny_na_urwany_wiersz(u):
    w = zmiany_hosta.dopisz(u, "plik", sciezka=Path("/dom/a"), sha256="ab")
    assert w["rodzaj"] == "plik" and w["szczegoly"] == {"sciezka": str(Path("/dom/a")), "sha256": "ab"} and w["czas"]
    assert zmiany_hosta.dopisz(u, "plik", sciezka=str(Path("/dom/a")), sha256="ab") == w     # bez drugiego wiersza
    zmiany_hosta.dopisz(u, "blok-rc", sciezka="/dom/.zprofile", znacznik="jarvo", sha256="cd")
    linie = zmiany_hosta.sciezka(u).read_text(encoding="utf-8").splitlines()
    assert len(linie) == 2 and [json.loads(x)["rodzaj"] for x in linie] == ["plik", "blok-rc"]
    with pytest.raises(ValueError, match="sekretów"):
        zmiany_hosta.dopisz(u, "plik", sciezka="/dom/b", api_key="sk-tajne")
    with pytest.raises(ValueError, match="sekretów"):
        zmiany_hosta.dopisz(u, "plik", sciezka="/dom/b", dane={"token": "tajne"})
    with pytest.raises(ValueError, match="nieznany rodzaj"):
        zmiany_hosta.dopisz(u, "rejestr", a=1)
    assert "tajne" not in zmiany_hosta.sciezka(u).read_text(encoding="utf-8")
    with open(zmiany_hosta.sciezka(u), "a", encoding="utf-8") as f:
        f.write('{"czas": "2026-10-24T')                         # urwany zapis po awarii zasilania
    assert [x["rodzaj"] for x in zmiany_hosta.wpisy(u)] == ["plik", "blok-rc"]


def test_plik_cofany_od_konca_i_tylko_z_nasza_trescia(u, tmp_path):
    assert zmiany_hosta.cofnij(u, log=None) == [] and not zmiany_hosta.sciezka(u).exists()   # pusty: bez zapisu
    dom = tmp_path / "dom"
    a, b, c = dom / "a.txt", dom / "b.txt", dom / "c.txt"
    assert zmiany_hosta.zapisz_plik(u, a, "nasz\n")
    assert not zmiany_hosta.zapisz_plik(u, a, "nasz\n")                  # drugi raz: bez zmian
    zmiany_hosta.zapisz_plik(u, b, "nasz b\n")
    b.write_text("zmienione przez właściciela\n", encoding="utf-8")
    zmiany_hosta.zapisz_plik(u, c, b"c")
    c.unlink()
    raport = zmiany_hosta.cofnij(u, log=None)
    assert [r["wynik"] for r in raport] == ["brak", "nie-nasze", "cofniete"]    # od końca: c, b, a
    assert not a.exists() and b.read_text(encoding="utf-8") == "zmienione przez właściciela\n"
    assert zmiany_hosta.wpisy(u) == []


def test_blok_rc_w_miejscu_bez_ruszania_reszty_pliku(u, tmp_path):
    rc = tmp_path / ".zprofile"
    rc.write_bytes(b"export A=1\r\nalias ll='ls -l'")                     # CRLF i brak końca wiersza zostają
    assert zmiany_hosta.dodaj_blok_rc(u, rc, 'export PATH="$HOME/.local/bin:$PATH"')
    tekst = rc.read_bytes().decode("utf-8")
    assert tekst == "export A=1\r\nalias ll='ls -l'\n# >>> jarvo >>>\nexport PATH=\"$HOME/.local/bin:$PATH\"\n" \
                    "# <<< jarvo <<<\n"
    assert not zmiany_hosta.dodaj_blok_rc(u, rc, 'export PATH="$HOME/.local/bin:$PATH"')
    assert zmiany_hosta.dodaj_blok_rc(u, rc, "export PATH=/nowa:$PATH")    # podmiana w miejscu, jeden blok
    assert rc.read_text(encoding="utf-8").count(">>> jarvo >>>") == 1
    tylko_blok = tmp_path / ".bash_profile"
    zmiany_hosta.dodaj_blok_rc(u, tylko_blok, "export X=1")
    zmieniony = tmp_path / ".zshrc"
    zmieniony.write_text("x\n", encoding="utf-8")
    zmiany_hosta.dodaj_blok_rc(u, zmieniony, "export Y=1")
    zmieniony.write_text(zmieniony.read_text(encoding="utf-8").replace("Y=1", "Y=2"), encoding="utf-8")
    raport = zmiany_hosta.cofnij(u, log=None)
    assert [r["wynik"] for r in raport] == ["nie-nasze", "cofniete", "cofniete", "brak"]
    assert rc.read_bytes() == b"export A=1\r\nalias ll='ls -l'\n"
    assert not tylko_blok.exists() and "Y=2" in zmieniony.read_text(encoding="utf-8")


def test_path_uzytkownika_tylko_nasz_wpis(u):
    r = Rejestr({("Environment", "Path"): (r"C:\Users\Michał\bin;%USERPROFILE%\.cargo\bin", 2)})
    kat = r"C:\Users\Michał\AppData\Local\Jarvo\bin"
    assert zmiany_hosta.dodaj_do_path(u, kat, rejestr=r)
    assert r.czytaj("Environment", "Path") == (r"C:\Users\Michał\bin;%USERPROFILE%\.cargo\bin;" + kat, 2)
    assert not zmiany_hosta.dodaj_do_path(u, kat, rejestr=r)
    assert len(zmiany_hosta.wpisy(u)) == 1 and r.ogloszenia == 1
    # właściciel dopisał katalog po nas, a nasz zapisał wielkimi literami: znika tylko nasz
    r.zapisz("Environment", "Path",
             r"C:\Users\Michał\bin;%USERPROFILE%\.cargo\bin;" + kat.upper() + "\\;D:\\narzędzia", 2)
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, rejestr=r, log=None)] == ["cofniete"]
    assert r.czytaj("Environment", "Path") == (r"C:\Users\Michał\bin;%USERPROFILE%\.cargo\bin;D:\narzędzia", 2)
    pusty = Rejestr()
    zmiany_hosta.dodaj_do_path(u, kat, rejestr=pusty)
    assert pusty.czytaj("Environment", "Path") == (kat, zmiany_hosta.REG_EXPAND_SZ)
    zmiany_hosta.cofnij(u, rejestr=pusty, log=None)
    assert pusty.czytaj("Environment", "Path") is None
    with pytest.raises(ValueError):
        zmiany_hosta.dodaj_do_path(u, "C:\\a;C:\\b", rejestr=pusty)


def test_cofnij_od_konca_filtr_i_bledy_zostaja(u, host, tmp_path):
    dom = tmp_path / "dom"
    zmiany_hosta.zapisz_plik(u, dom / "a.txt", "a")
    autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    autostart.wlacz_linger(u, host, log=None)
    with open(zmiany_hosta.sciezka(u), "a", encoding="utf-8") as f:     # wpis z przyszłej wersji Jarva
        f.write(json.dumps({"czas": "2027-01-01T00:00:00+01:00", "rodzaj": "nowy-rodzaj", "szczegoly": {}}) + "\n")
    tylko_plik = zmiany_hosta.cofnij(u, host, rodzaje={"plik"}, log=None)
    assert [r["rodzaj"] for r in tylko_plik] == ["plik"] and not (dom / "a.txt").exists()
    raport = zmiany_hosta.cofnij(u, host, log=None)
    assert [(r["rodzaj"], r["wynik"]) for r in raport] == [("nowy-rodzaj", "blad"), ("linger", "cofniete"),
                                                         ("autostart-linux", "cofniete")]
    assert not host.linger and not host.aktywne
    assert [w["rodzaj"] for w in zmiany_hosta.wpisy(u)] == ["nowy-rodzaj"]      # do następnej próby


def test_uruchom_domyslnie_i_strona_kodowa(tmp_path):
    kod, wyj = zmiany_hosta.uruchom_domyslnie([sys.executable, "-c",
                                               "import sys; sys.stdout.buffer.write('zażółć'.encode()); "
                                               "sys.stderr.write('E'); sys.exit(3)"])
    assert kod == 3 and "zażółć" in wyj and "E" in wyj
    assert zmiany_hosta.uruchom_domyslnie([str(tmp_path / "nie-ma-takiego-programu")])[0] == 127
    if os.name == "nt":                                  # schtasks pisze do potoku w stronie OEM (np. cp852)
        import ctypes
        oem = f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        assert zmiany_hosta._dekoduj("café".encode(oem)) == "café"


# ---------------------------------------------------------------- nazwy

def test_nazwy_z_przyrostkiem_dla_jarvo_root(tmp_path):
    proba = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "proba")})
    nazwa = autostart.nazwa_zadania(proba)
    assert re.fullmatch(r"Jarvo-[0-9a-f]{8}", nazwa)
    assert nazwa == autostart.nazwa_zadania(sciezki.uklad({"JARVO_ROOT": str(tmp_path / "proba")}))
    assert nazwa != autostart.nazwa_zadania(sciezki.uklad({"JARVO_ROOT": str(tmp_path / "inna")}))
    skrot = nazwa.split("-", 1)[1]
    assert autostart.etykieta_agenta(proba) == f"pl.jarvo.nadzorca-{skrot}"
    assert autostart.nazwa_jednostki(proba) == f"jarvo-{skrot}.service"
    env = {"LOCALAPPDATA": str(tmp_path / "lad"), "XDG_DATA_HOME": str(tmp_path / "xdg")}
    domyslny = sciezki.uklad(env)
    assert autostart.nazwa_zadania(domyslny, env) == "Jarvo"
    assert autostart.etykieta_agenta(domyslny, env) == "pl.jarvo.nadzorca"
    assert autostart.nazwa_jednostki(domyslny, env) == "jarvo.service"
    assert autostart.nazwa_zadania(domyslny, {**env, "JARVO_ROOT": str(domyslny.root)}) == "Jarvo"


# ---------------------------------------------------------------- Windows: Harmonogram zadań

def test_xml_zadania_utf16_wyzwalacze_i_ustawienia():
    argv = [r"C:\Program Files\Jarvo\python\pythonw.exe", "-I", "-X", "utf8", r"C:\Jarvo\app\1.0\jarvo\start.py",
            "serwis", 'z "cudzysłowem"', "ukośnik\\"]
    dane = autostart.xml_zadania(argv, SID, katalog=Path(r"C:\Jarvo"))
    assert dane[:2] == b"\xff\xfe" and dane.decode("utf-16").startswith('<?xml version="1.0" encoding="UTF-16"?>')
    korzen = ET.fromstring(dane)
    assert korzen.tag == f"{{{autostart.NS}}}Task" and korzen.get("version") == "1.2"

    def pole(sciezka):
        return korzen.find(sciezka, NS).text

    assert _tagi(korzen.find("t:Triggers", NS)) == ["LogonTrigger", "SessionStateChangeTrigger", "TimeTrigger"]
    assert _tagi(korzen.find("t:Triggers/t:LogonTrigger", NS)) == ["Enabled", "UserId", "Delay"]   # jak w schemacie
    assert _tagi(korzen.find("t:Triggers/t:SessionStateChangeTrigger", NS)) == ["Enabled", "UserId", "StateChange"]
    assert pole("t:Triggers/t:LogonTrigger/t:UserId") == SID and pole("t:Triggers/t:LogonTrigger/t:Delay") == "PT15S"
    assert pole("t:Triggers/t:SessionStateChangeTrigger/t:UserId") == SID
    assert pole("t:Triggers/t:SessionStateChangeTrigger/t:StateChange") == "SessionUnlock"
    assert pole("t:Triggers/t:TimeTrigger/t:Repetition/t:Interval") == "PT5M"
    for klucz, wartosc in {"DisallowStartIfOnBatteries": "false", "StopIfGoingOnBatteries": "false",
                           "ExecutionTimeLimit": "PT0S", "MultipleInstancesPolicy": "IgnoreNew", "Priority": "5",
                           "AllowStartOnDemand": "true", "Enabled": "true"}.items():
        assert pole(f"t:Settings/t:{klucz}") == wartosc, klucz
    assert pole("t:Settings/t:RestartOnFailure/t:Interval") == "PT1M"
    assert pole("t:Settings/t:RestartOnFailure/t:Count") == "999"
    assert pole("t:Principals/t:Principal/t:UserId") == SID
    assert pole("t:Principals/t:Principal/t:LogonType") == "InteractiveToken"
    assert pole("t:Principals/t:Principal/t:RunLevel") == "LeastPrivilege"
    assert pole("t:Actions/t:Exec/t:Command") == argv[0]
    assert pole("t:Actions/t:Exec/t:Arguments") == subprocess.list2cmdline(argv[1:])
    assert pole("t:Actions/t:Exec/t:WorkingDirectory") == r"C:\Jarvo"
    opis = pole("t:RegistrationInfo/t:Description")
    assert autostart.ZNACZNIK in opis and "nadzorca procesów" in opis
    odcisk = re.search(r"odcisk=([0-9a-f]{12})", opis).group(1)
    assert autostart.xml_zadania(argv, SID, katalog=Path(r"C:\Jarvo")) == dane            # ten sam XML co raz
    assert f"odcisk={odcisk}" not in autostart.xml_zadania(argv[:-1], SID).decode("utf-16")
    tylko_logowanie = ET.fromstring(autostart.xml_zadania(argv, SID, zapasowe=False))
    assert _tagi(tylko_logowanie.find("t:Triggers", NS)) == ["LogonTrigger"]
    with pytest.raises(ValueError, match="pełną ścieżkę"):
        autostart.xml_zadania(["pythonw.exe", "x"], SID)
    with pytest.raises(ValueError, match="%"):
        autostart.xml_zadania([r"C:\x\pythonw.exe", "%TEMP%"], SID)


POWERSHELL = ntpath.join(os.environ.get("SystemRoot") or "C:\\Windows", "System32", "WindowsPowerShell", "v1.0",
                         "powershell.exe")
PARSER = """$s = New-Object -ComObject Schedule.Service
$s.Connect()
foreach ($p in $args) {
  $d = $s.NewTask(0)
  try { $d.XmlText = [IO.File]::ReadAllText($p); 'ok ' + $d.Triggers.Count + ' ' + $d.Settings.Priority + ' ' +
        $d.Settings.ExecutionTimeLimit + ' ' + $d.Settings.MultipleInstances }
  catch { 'blad ' + $_.Exception.Message.Trim() }
}
"""


@pytest.mark.windows_only
def test_xml_przyjmuje_parser_harmonogramu(tmp_path):
    """Parser Harmonogramu w pamięci (NewTask + XmlText) sprawdza schemat i kolejność; niczego nie rejestruje."""
    argv = [sys.executable.replace("python.exe", "pythonw.exe"), "-I", "-X", "utf8", str(tmp_path / "start.py"),
            "serwis"]
    dobry = tmp_path / "dobry.xml"
    dobry.write_bytes(autostart.xml_zadania(argv, autostart._sid(), katalog=tmp_path))
    zly = tmp_path / "zly.xml"
    zly.write_bytes(dobry.read_bytes().decode("utf-16").replace(
        "<Priority>5</Priority>", "<Priority>5</Priority><Nieznany>1</Nieznany>").encode("utf-16"))
    skrypt = tmp_path / "parser.ps1"
    skrypt.write_text(PARSER, encoding="utf-8")
    kod, wyj = zmiany_hosta.uruchom_domyslnie([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                                               "Bypass", "-File", str(skrypt), str(dobry), str(zly)])
    linie = [x.strip() for x in wyj.splitlines() if x.strip()]
    assert kod == 0 and linie[0] == "ok 3 5 PT0S 2", wyj          # 3 wyzwalacze, priorytet 5, IgnoreNew = 2
    assert linie[1].startswith("blad") and "Nieznany" in linie[1], wyj


@pytest.mark.windows_only
def test_argumenty_zadania_wracaja_jak_sys_argv():
    """Harmonogram składa wiersz polecenia z Command i Arguments; Python rozbiera go z powrotem na to samo argv."""
    reszta = ["z spacją", 'cudzy"słów', "ukośnik\\", "a\\\\b", ""]
    argv = [sys.executable, "-c", "import json, sys; print(json.dumps(sys.argv[1:]))", *reszta]
    argumenty = ET.fromstring(autostart.xml_zadania(argv, SID)).find("t:Actions/t:Exec/t:Arguments", NS).text
    w = subprocess.run(f'"{sys.executable}" {argumenty}', capture_output=True, encoding="utf-8", errors="replace",
                       creationflags=subprocess.CREATE_NO_WINDOW)
    assert json.loads(w.stdout) == reszta, w.stderr


def test_windows_wlacz_stan_drugi_raz_i_wylacz(u, host):
    r = Rejestr()
    argv = argv_windows(u)
    nazwa = autostart.nazwa_zadania(u)
    w = autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert w["mechanizm"] == "harmonogram" and w["zmieniony"] and w["uruchomiony"] and w["nazwa"] == nazwa
    create = next(p for p in host.polecenia if p[1] == "/Create")
    assert ntpath.basename(create[0]).lower() == "schtasks.exe" and ntpath.isabs(create[0])
    assert create[1:] == ["/Create", "/TN", nazwa, "/XML", w["plik"], "/F"]
    assert ("schtasks", "/Delete") not in host.kroki()                       # bez kasowania przed /Create
    assert host.kroki()[-1] == ("schtasks", "/Run") and Path(w["plik"]).read_bytes()[:2] == b"\xff\xfe"
    wpisy = zmiany_hosta.wpisy(u)
    assert [(x["rodzaj"], x["szczegoly"]["tryb"], x["szczegoly"]["nazwa"]) for x in wpisy] == [
        ("autostart-windows", "harmonogram", nazwa)]
    s = autostart.stan(u, host, system="windows", rejestr=r)
    assert s["mechanizm"] == "harmonogram" and s["wlaczony"] and s["nasz"] and s["dziala"]
    assert s["ustawienia"]["MultipleInstancesPolicy"] == "IgnoreNew"        # eksport pomija wartość domyślną
    assert (s["ustawienia"]["ExecutionTimeLimit"], s["ustawienia"]["Priority"]) == ("PT0S", "5")
    assert s["ustawienia"]["DisallowStartIfOnBatteries"] == s["ustawienia"]["StopIfGoingOnBatteries"] == "false"
    assert s["wyzwalacze"] == ["LogonTrigger", "SessionStateChangeTrigger", "TimeTrigger"]
    assert s["opis"].startswith("włączony") and "działa" in s["opis"]
    host.polecenia.clear()
    w2 = autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert not w2["zmieniony"] and ("schtasks", "/Create") not in host.kroki() and zmiany_hosta.wpisy(u) == wpisy
    host.polecenia.clear()
    wy = autostart.wylacz(u, host, system="windows", rejestr=r, log=None)
    assert wy["usuniety"] and nazwa not in host.zadania
    assert host.kroki() == [("schtasks", "/Query"), ("schtasks", "/Delete")]   # bez /End: nadzorca nie ginie
    s = autostart.stan(u, host, system="windows", rejestr=r)
    assert s["mechanizm"] is None and s["opis"] == "wyłączony"
    assert autostart.wylacz(u, host, system="windows", rejestr=r, log=None)["usuniety"] is False


def test_windows_obce_zadanie_zostaje(u, host):
    nazwa = autostart.nazwa_zadania(u)
    obce = '<?xml version="1.0" encoding="UTF-16"?>\r\n<Task version="1.2" xmlns="' + autostart.NS + '">' \
           "<RegistrationInfo><Description>moje</Description></RegistrationInfo></Task>"
    host.zadania[nazwa] = obce
    with pytest.raises(autostart.BladAutostartu, match="nie założył Jarvo"):
        autostart.wlacz(u, argv_windows(u), host, system="windows", rejestr=Rejestr(), log=None)
    wy = autostart.wylacz(u, host, system="windows", rejestr=Rejestr(), log=None)
    assert not wy["usuniety"] and host.zadania[nazwa] == obce and "nie jest Jarva" in wy["uwagi"][0]
    assert zmiany_hosta.wpisy(u) == []
    assert autostart.stan(u, host, system="windows", rejestr=Rejestr())["opis"].startswith("nieaktywny")


def test_windows_bez_zapasowych_wyzwalaczy_a_potem_wpis_run(u, host):
    r = Rejestr()
    argv = argv_windows(u)
    nazwa = autostart.nazwa_zadania(u)
    host.odmowa_zapasowych = True
    w = autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert w["mechanizm"] == "harmonogram" and w["zmieniony"] and "zapasowych" in w["uwagi"][0]
    assert "SessionStateChangeTrigger" not in host.zadania[nazwa] and "LogonTrigger" in host.zadania[nazwa]
    assert not autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)["zmieniony"]   # drugi raz
    autostart.wylacz(u, host, system="windows", rejestr=r, log=None)
    host.odmowa_create = True                                   # polityka blokuje Harmonogram w ogóle
    w = autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert w["mechanizm"] == "run" and w["uruchomiony"] is False and "Odmowa dostępu" in w["komunikat"]
    assert r.czytaj(autostart.KLUCZ_RUN, nazwa) == (subprocess.list2cmdline(argv), zmiany_hosta.REG_SZ)
    s = autostart.stan(u, host, system="windows", rejestr=r)
    assert s["mechanizm"] == "run" and s["nasz"] and "bez podtrzymania" in s["opis"]
    host.odmowa_create = False                                  # Harmonogram znów działa: wpis Run znika
    w = autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert w["mechanizm"] == "harmonogram" and r.czytaj(autostart.KLUCZ_RUN, nazwa) is None
    r.zapisz(autostart.KLUCZ_RUN, nazwa, r'"C:\Inny\program.exe"', zmiany_hosta.REG_SZ)
    host.odmowa_create, host.zadania = True, {}
    with pytest.raises(autostart.BladAutostartu, match="innego"):          # cudzego wpisu Run nie nadpisujemy
        autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)


def test_windows_cofniecie_z_dziennika(u, host):
    r = Rejestr()
    argv = argv_windows(u)
    nazwa = autostart.nazwa_zadania(u)
    autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    host.odmowa_delete = True
    raport = zmiany_hosta.cofnij(u, host, rejestr=r, log=None)
    assert [x["wynik"] for x in raport] == ["blad"] and len(zmiany_hosta.wpisy(u)) == 1   # zostaje do ponowienia
    host.odmowa_delete = False
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, rejestr=r, log=None)] == ["cofniete"]
    assert nazwa not in host.zadania
    # zadanie o tej nazwie, ale z inną definicją (np. właściciel założył je na nowo): zostaje
    autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    host.zadania[nazwa] = host.zadania[nazwa].replace("odcisk=", "odcisk=0")
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, rejestr=r, log=None)] == ["nie-nasze"]
    assert nazwa in host.zadania
    # Harmonogram odmawia: wpisy obu prób zadania i wpis Run; cofamy Run, zadań już nie ma
    host.odmowa_create, host.zadania = True, {}
    autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert [x["szczegoly"]["tryb"] for x in zmiany_hosta.wpisy(u)] == ["harmonogram", "harmonogram", "run"]
    raport = zmiany_hosta.cofnij(u, host, rejestr=r, log=None)
    assert [x["wynik"] for x in raport] == ["cofniete", "brak", "brak"] and r.wartosci == {}
    # wpis Run zmieniony po instalacji zostaje
    autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    r.zapisz(autostart.KLUCZ_RUN, nazwa, subprocess.list2cmdline([*argv, "--inaczej"]), zmiany_hosta.REG_SZ)
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, rejestr=r, log=None)][0] == "nie-nasze"
    assert r.czytaj(autostart.KLUCZ_RUN, nazwa) is not None


# ---------------------------------------------------------------- macOS: LaunchAgent

def test_plist_agenta(u):
    dane = plistlib.loads(autostart.plist_agenta(ARGV_POSIX, u))
    assert dane["Label"] == "pl.jarvo.nadzorca" and dane["ProgramArguments"] == ARGV_POSIX
    assert dane["RunAtLoad"] is True and dane["KeepAlive"] == {"SuccessfulExit": False}
    assert dane["ThrottleInterval"] == 30 and dane["ExitTimeOut"] == 45 and "ProcessType" not in dane
    assert dane["StandardOutPath"] == dane["StandardErrorPath"] == str(u.logi / "autostart.log")
    assert dane["WorkingDirectory"] == str(u.root) and "EnvironmentVariables" not in dane
    proba = plistlib.loads(autostart.plist_agenta(ARGV_POSIX, u, "pl.jarvo.nadzorca-1", jarvo_root=True))
    assert proba["EnvironmentVariables"] == {"JARVO_ROOT": str(u.root)} and proba["Label"] == "pl.jarvo.nadzorca-1"
    with pytest.raises(ValueError, match="pełną ścieżkę"):
        autostart.plist_agenta(["python3", "-m", "jarvo"], u)


@pytest.mark.skipif(sys.platform != "darwin", reason="plutil jest tylko na macOS")
def test_plist_przyjmuje_plutil(u, tmp_path):
    plik = tmp_path / "pl.jarvo.nadzorca.plist"
    plik.write_bytes(autostart.plist_agenta(ARGV_POSIX, u))
    w = subprocess.run(["/usr/bin/plutil", "-lint", str(plik)], capture_output=True, encoding="utf-8",
                       errors="replace")
    assert w.returncode == 0, w.stdout + w.stderr


def test_macos_wlacz_stan_drugi_raz_zmiana_i_wylacz(u, host, tmp_path):
    dom = tmp_path / "dom"
    et = autostart.etykieta_agenta(u)
    plik = dom / "Library" / "LaunchAgents" / f"{et}.plist"
    domena = f"gui/{autostart._uid()}"
    w = autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, log=None)
    assert w["plik"] == str(plik) and w["zmieniony"] and w["uruchomiony"] and plik.is_file()
    assert host.polecenia[-1] == [autostart.LAUNCHCTL, "bootstrap", domena, str(plik)]
    assert plistlib.loads(plik.read_bytes())["EnvironmentVariables"] == {"JARVO_ROOT": str(u.root)}   # próbny korzeń
    assert u.logi.is_dir()
    s = autostart.stan(u, host, system="macos", dom=dom)
    assert (s["mechanizm"], s["wlaczony"], s["nasz"], s["dziala"], s["pid"]) == ("launchagent", True, True, True, 4242)
    host.polecenia.clear()
    assert not autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, log=None)["zmieniony"]
    assert host.kroki() == [("launchctl", "print"), ("launchctl", "kickstart")]     # działającego nie restartuje
    host.polecenia.clear()
    autostart.wlacz(u, [*ARGV_POSIX, "--gadatliwie"], host, system="macos", dom=dom, log=None)
    assert host.kroki() == [("launchctl", "print"), ("launchctl", "bootout"), ("launchctl", "bootstrap")]
    wy = autostart.wylacz(u, host, system="macos", dom=dom, log=None)
    assert wy["usuniety"] and not plik.exists() and et not in host.agenci
    assert autostart.stan(u, host, system="macos", dom=dom)["opis"] == "wyłączony"
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, log=None)] == ["brak", "brak"]


def test_macos_bootstrap_nieudany_i_cofniecie(u, host, tmp_path):
    dom = tmp_path / "dom"
    host.odmowa_bootstrap = True
    with pytest.raises(autostart.BladAutostartu, match="bootstrap"):
        autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, log=None)
    assert host.kroki().count(("launchctl", "bootstrap")) == 3              # trzy próby, plik zostaje
    plik = dom / "Library" / "LaunchAgents" / f"{autostart.etykieta_agenta(u)}.plist"
    assert plik.is_file()
    host.odmowa_bootstrap = False
    assert not autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, start=False, log=None)["zmieniony"]
    autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, log=None)
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, log=None)] == ["cofniete"]
    assert not plik.exists() and not host.agenci and host.kroki()[-1] == ("launchctl", "bootout")


# ---------------------------------------------------------------- Linux: systemd --user

def _rozbierz_systemd(wiersz: str, zmienne: bool = True) -> list[str]:
    """Odwrotność cytowania systemd w podzbiorze, który piszemy (systemd.syntax(7), systemd.service(5)):
    specyfikatory %% → %, słowa w cudzysłowie z ucieczkami \\\\ i \\", potem zmienne $$ → $."""
    wiersz = wiersz.replace("%%", "\0")
    assert "%" not in wiersz, "systemd rozwinąłby specyfikator"
    slowa, i = [], 0
    while i < len(wiersz):
        if wiersz[i] == " ":
            i += 1
            continue
        assert wiersz[i] == '"', wiersz
        i, s = i + 1, ""
        while wiersz[i] != '"':
            if wiersz[i] == "\\":
                assert wiersz[i + 1] in '\\"'
                s, i = s + wiersz[i + 1], i + 2
            else:
                s, i = s + wiersz[i], i + 1
        i += 1
        if zmienne:
            assert "$" not in s.replace("$$", ""), "systemd podstawiłby zmienną"
            s = s.replace("$$", "$")
        slowa.append(s.replace("\0", "%"))
    return slowa


def test_jednostka_systemd_cytowanie_i_ustawienia(u):
    argv = ["/home/ola/.local/share/jarvo/program/python/bin/python3", "-I", "-c", 'print("100% $HOME \\ ok")',
            "z spacją", "it's", "${X}"]
    tekst = autostart.jednostka_systemd(argv, u)
    assert tekst.startswith("# " + autostart.ZNACZNIK) and tekst.endswith("\n")
    linie = dict(x.split("=", 1) for x in tekst.splitlines() if "=" in x and not x.startswith("#"))
    assert _rozbierz_systemd(linie["ExecStart"]) == argv
    assert (linie["Type"], linie["Restart"], linie["KillMode"], linie["TimeoutStopSec"]) == (
        "simple", "on-failure", "mixed", "45")
    assert linie["WantedBy"] == "default.target" and linie["WorkingDirectory"] == str(u.root).replace("%", "%%")
    assert "Environment" not in linie
    z_korzeniem = dict(x.split("=", 1) for x in autostart.jednostka_systemd(argv, u, jarvo_root=True).splitlines()
                       if x.startswith("Environment="))
    assert _rozbierz_systemd(z_korzeniem["Environment"], zmienne=False) == [f"JARVO_ROOT={u.root}"]
    with pytest.raises(ValueError, match="nowego wiersza"):
        autostart.jednostka_systemd([argv[0], "a\nExecStartPre=/bin/zle"], u)


def test_linux_wlacz_stan_drugi_raz_wylacz_i_bez_busa(u, host, tmp_path):
    dom = tmp_path / "dom"
    nazwa = autostart.nazwa_jednostki(u)
    plik = dom / ".config" / "systemd" / "user" / nazwa
    w = autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    assert w["plik"] == str(plik) and w["zmieniony"] and w["uruchomiony"] and plik.is_file()
    assert host.polecenia == [[autostart._systemctl(), "--user", "show-environment"],
                              [autostart._systemctl(), "--user", "daemon-reload"],
                              [autostart._systemctl(), "--user", "enable", "--now", nazwa]]
    assert ("loginctl", "enable-linger") not in host.kroki()               # linger tylko na życzenie
    s = autostart.stan(u, host, system="linux", dom=dom)
    assert (s["mechanizm"], s["wlaczony"], s["nasz"], s["dziala"], s["pid"]) == ("systemd", True, True, True, 4343)
    assert s["bus"] is True and s["linger"] is False and s["opis"].startswith("włączony")
    host.polecenia.clear()
    assert not autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)["zmieniony"]
    assert host.kroki() == [("systemctl", "show-environment"), ("systemctl", "enable")]       # bez daemon-reload
    wy = autostart.wylacz(u, host, system="linux", dom=dom, log=None)
    assert wy["usuniety"] and not plik.exists() and not host.aktywne and not host.wlaczone
    assert ("systemctl", "disable") in host.kroki()
    host.bus = False
    with pytest.raises(autostart.BladAutostartu, match="Brak usług systemd użytkownika"):
        autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    assert not plik.exists()
    obca = plik.parent / nazwa
    obca.write_text("[Service]\nExecStart=/bin/true\n", encoding="utf-8")
    assert not autostart.wylacz(u, host, system="linux", dom=dom, log=None)["usuniety"] and obca.exists()


def test_linger_tylko_na_wyrazne_zyczenie(u, host):
    assert not autostart.wylacz_linger(u, host, log=None)                    # Jarvo go nie włączał
    host.linger = True                                                       # właściciel włączył go sam
    assert not autostart.wlacz_linger(u, host, log=None) and zmiany_hosta.wpisy(u) == []
    assert not autostart.wylacz_linger(u, host, log=None) and host.linger
    host.linger = False
    assert autostart.wlacz_linger(u, host, log=None) and host.linger
    assert [(x["rodzaj"], x["szczegoly"]) for x in zmiany_hosta.wpisy(u)] == [("linger", {"uzytkownik": "ola"})]
    assert ("loginctl", "enable-linger") in host.kroki()
    assert autostart.wylacz_linger(u, host, log=None) and not host.linger
    host.linger = True
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, log=None)] == ["cofniete"] and not host.linger


# ---------------------------------------------------------------- prawdziwy system (tylko CI i odczyt)

@pytest.mark.windows_only
def test_rejestr_czyta_path_bez_zmian():
    wartosc = zmiany_hosta.Rejestr().czytaj("Environment", "Path")           # tylko odczyt
    assert wartosc is None or (isinstance(wartosc[0], str) and wartosc[1] in (1, 2))
    assert zmiany_hosta.Rejestr().czytaj(rf"Software\JarvoNieMa-{uuid.uuid4().hex}", "Path") is None


@pytest.mark.windows_only
@NA_CI
def test_prawdziwy_rejestr_na_runnerze_ci():
    import winreg
    klucz = rf"Software\JarvoTest-{uuid.uuid4().hex[:8]}"
    r = zmiany_hosta.Rejestr()
    try:
        r.zapisz(klucz, "Path", r"C:\a;C:\Zażółć", zmiany_hosta.REG_EXPAND_SZ)
        assert r.czytaj(klucz, "Path") == (r"C:\a;C:\Zażółć", zmiany_hosta.REG_EXPAND_SZ)
        r.usun(klucz, "Path")
        assert r.czytaj(klucz, "Path") is None
        r.oglos()
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, klucz)
        except OSError:
            pass


@pytest.mark.windows_only
@NA_CI
def test_prawdziwy_harmonogram_na_runnerze_ci(tmp_path):
    """Prawdziwe schtasks: unikalna nazwa spod JARVO_ROOT, rejestracja, ustawienia z eksportu, drugi przebieg bez
    zmian, cofnięcie z dziennika; na końcu sprzątanie, nawet gdy coś pękło."""
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "jarvo")})
    nazwa = autostart.nazwa_zadania(u)
    assert nazwa.startswith("Jarvo-")
    argv = [sys.executable, "-c", "pass"]
    try:
        w = autostart.wlacz(u, argv, start=False, log=None)
        assert w["mechanizm"] == "harmonogram" and w["zmieniony"] and not w["uwagi"], w
        s = autostart.stan(u)
        assert s["mechanizm"] == "harmonogram" and s["wlaczony"] and s["nasz"], s
        assert s["ustawienia"]["DisallowStartIfOnBatteries"] == s["ustawienia"]["StopIfGoingOnBatteries"] == "false"
        assert (s["ustawienia"]["ExecutionTimeLimit"], s["ustawienia"]["Priority"]) == ("PT0S", "5")
        assert s["ustawienia"]["MultipleInstancesPolicy"] == "IgnoreNew"
        ponow = (s["ustawienia"]["RestartOnFailureInterval"], s["ustawienia"]["RestartOnFailureCount"])
        assert ponow == ("PT1M", "999")
        assert sorted(s["wyzwalacze"]) == ["LogonTrigger", "SessionStateChangeTrigger", "TimeTrigger"]
        assert s["polecenie"] == sys.executable
        assert autostart.wlacz(u, argv, start=False, log=None)["zmieniony"] is False
        assert [x["wynik"] for x in zmiany_hosta.cofnij(u, log=None)] == ["cofniete"]
        assert autostart.stan(u)["mechanizm"] is None
    finally:
        zmiany_hosta.uruchom_domyslnie([autostart._schtasks(), "/Delete", "/TN", nazwa, "/F"])
        zmiany_hosta.Rejestr().usun(autostart.KLUCZ_RUN, nazwa)
