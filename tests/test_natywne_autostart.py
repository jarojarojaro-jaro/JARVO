"""Autostart nadzorcy i dziennik zmian hosta (docs/NATYWNIE.md: H22, c2 „Autostart”, N08, D08, c4 uninstall).

Polecenia systemu (schtasks, launchctl, systemctl, loginctl) idą do atrapy ze stanem w pamięci, a rejestr Windows do
atrapy winreg: testy wszystkich trzech systemów biegną na każdym systemie i niczego nie zmieniają w komputerze.
Na Windows parser Harmonogramu sprawdza nasz XML w pamięci (bez rejestracji), a stan() pyta prawdziwy Harmonogram
tylko o zadanie, którego nie ma (odczyt). Prawdziwa rejestracja, /Run i zapis w rejestrze tylko na runnerze CI
(zmienna CI), z unikalną nazwą i sprzątaniem: komputer właściciela zostaje nietknięty.
"""
from __future__ import annotations

import json
import ntpath
import os
import plistlib
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import autostart, sciezki, zmiany_hosta  # noqa: E402

NS = {"t": autostart.NS}
SID = "S-1-5-21-1111111111-2222222222-3333333333-1001"
SID_DRUGI = "S-1-5-21-1111111111-2222222222-3333333333-1002"
ARGV_POSIX = ["/opt/jarvo/program/python/bin/python3", "-I", "-X", "utf8", "/opt/jarvo/program/app/1.0/jarvo/start.py",
              "serwis"]
NA_CI = pytest.mark.skipif(not os.environ.get("CI"), reason="prawdziwy Harmonogram i rejestr tylko na runnerze CI")
WYLACZONE = "<Settings>\r\n    <Enabled>false</Enabled>"      # Settings/Enabled=false w eksporcie zadania
XDG = [nazwa for nazwa, _ in autostart.XDG]


def _program(argv0: str) -> str:
    return re.split(r"[\\/]", argv0)[-1].lower().removesuffix(".exe")


class Host:
    """Atrapa `wykonaj(argv) -> (kod, wyjście)` ze stanem: Harmonogram zadań, launchctl, systemctl i loginctl.
    Zadanie wraca z /Query /XML tak jak z Windows: CRLF, bez wartości domyślnych, UserId wyzwalaczy jako nazwa.
    Menedżer usług użytkownika szuka jednostek w `katalog_jednostek()` (UnitPath) i `enable` innej nie znajdzie."""

    def __init__(self, dom: Path):
        self.dom = dom
        self.polecenia: list[list[str]] = []
        self.zadania: dict[str, str] = {}
        self.dzialajace: set[str] = set()
        self.odmowa_create = False           # polityka blokuje Harmonogram
        self.odmowa_zapasowych = False       # Harmonogram nie przyjmuje odblokowania i wyzwalacza czasu
        self.odmowa_delete = False
        self.odmowa_change = False
        self.nieczytelne: set[str] = set()   # na liście, ale /XML odmawia (np. zadanie innego konta)
        self.harmonogram_padl = False        # /Query nie podaje nawet listy
        self.agenci: dict[str, str] = {}
        self.wylaczone_agenci: set[str] = set()     # launchctl disable
        self.odmowa_bootstrap = False
        self.bus = True
        self.konfig: Path | None = None      # katalog jednostek menedżera (domyślnie <dom>/.config/systemd/user)
        self.env_menedzera: dict[str, str] = {}
        self.obce_fragmenty: dict[str, str] = {}    # jednostka -> jej plik w innym katalogu menedżera albo maska
        self.wlaczone: set[str] = set()
        self.aktywne: set[str] = set()
        self.linger = False
        self.odmowa_linger = False
        self.katalog_lingera = dom.parent / "linger"     # /var/lib/systemd/linger
        self._czas_lingera = 1_700_000_000 * 10**9

    def __call__(self, argv):
        argv = [str(a) for a in argv]
        self.polecenia.append(argv)
        return getattr(self, "_" + _program(argv[0]))(argv[1:])

    def kroki(self) -> list[tuple[str, ...]]:
        """Polecenia bez ścieżek programów: [("schtasks", "/Query"), ("launchctl", "print"), …]."""
        return [(_program(p[0]), *(p[2:3] if _program(p[0]) == "systemctl" else p[1:2])) for p in self.polecenia]

    def wylacz_zadanie(self, nazwa: str) -> None:
        """Jak „Wyłącz” w taskschd.msc: Settings/Enabled=false."""
        self.zadania[nazwa] = self.zadania[nazwa].replace("<Settings>", WYLACZONE, 1)

    def katalog_jednostek(self) -> Path:
        return self.konfig or self.dom / ".config" / "systemd" / "user"

    def ustaw_linger(self, wlaczony: bool) -> None:
        """Jak logind: enable-linger zakłada (albo dotyka) plik <użytkownik> z nowym czasem, disable-linger go usuwa.
        Tak włącza i wyłącza linger także sam właściciel (loginctl poza Jarvem)."""
        self.linger = wlaczony
        plik = self.katalog_lingera / "ola"
        if not wlaczony:
            plik.unlink(missing_ok=True)
            return
        plik.parent.mkdir(parents=True, exist_ok=True)
        plik.touch()
        self._czas_lingera += 10**9
        os.utime(plik, ns=(self._czas_lingera, self._czas_lingera))

    def _schtasks(self, a):
        nazwa = a[a.index("/TN") + 1] if "/TN" in a else None
        if a[0] == "/Query" and self.harmonogram_padl:
            return 1, "ERROR: Usługa Harmonogram zadań nie jest dostępna.\r\n"
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
            if nazwa in self.nieczytelne:
                return 1, "ERROR: Odmowa dostępu.\r\n"
            return 0, self.zadania[nazwa]
        if a[0] == "/Query":
            dziala = nazwa in self.dzialajace
            status = "Running" if dziala else "Disabled" if WYLACZONE in self.zadania[nazwa] else "Ready"
            pola = ["HOST", "\\" + nazwa, "N/A", status, "Interactive only", "N/A",
                    "267009" if dziala else "267011", "Jarvo"]
            return 0, ",".join(f'"{p}"' for p in pola) + "\r\n"
        if a[0] == "/Change":
            if self.odmowa_change:
                return 1, "ERROR: Odmowa dostępu.\r\n"
            tekst = self.zadania[nazwa].replace(WYLACZONE, "<Settings>")
            self.zadania[nazwa] = tekst.replace("<Settings>", WYLACZONE, 1) if "/DISABLE" in a else tekst
            return 0, f'SUCCESS: The parameters of scheduled task "{nazwa}" have been changed.\r\n'
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
        if a[0] == "print-disabled":
            wiersze = "".join(f'\t"{et}" => {"disabled" if et in self.wylaczone_agenci else "enabled"}\n'
                              for et in sorted({"com.openssh.ssh-agent", *self.wylaczone_agenci}))
            return 0, f"disabled services = {{\n{wiersze}}}\n\nlogin item associations = {{\n}}\n"
        et = a[-1].rsplit("/", 1)[-1]
        if a[0] == "enable":
            self.wylaczone_agenci.discard(et)
            return 0, ""
        if a[0] == "bootstrap":
            et = plistlib.loads(Path(a[2]).read_bytes())["Label"]
            if self.odmowa_bootstrap:
                return 5, "Bootstrap failed: 5: Input/output error\n"
            if et in self.wylaczone_agenci:
                return 119, "Bootstrap failed: 119: Service is disabled\n"
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
        if a[0] == "show-environment":
            zmienne = {"HOME": str(self.dom), "LANG": "pl_PL.UTF-8", **self.env_menedzera}
            return 0, "".join(f"{k}={v}\n" for k, v in zmienne.items())
        if a[0] == "daemon-reload":
            return 0, ""
        if a[0] == "show":
            wlasciwosc = next(x for x in a if x.startswith("--property=")).split("=", 1)[1]
            if wlasciwosc == "UnitPath":
                k = self.katalog_jednostek()
                sciezki_ = [f"{k}.control", "/run/user/1000/systemd/user.control", "/run/user/1000/systemd/transient",
                            "/run/user/1000/systemd/generator.early", str(k), "/etc/systemd/user",
                            "/run/user/1000/systemd/user", "/run/systemd/user",
                            str(self.dom / ".local" / "share" / "systemd" / "user"), "/usr/lib/systemd/user"]
                return 0, "UnitPath=" + " ".join(sciezki_) + "\n"
            nazwa = a[1]
            if wlasciwosc == "FragmentPath":
                wlasny = self.katalog_jednostek() / nazwa
                return 0, f"FragmentPath={self.obce_fragmenty.get(nazwa) or (wlasny if wlasny.is_file() else '')}\n"
            assert wlasciwosc == "MainPID", a
            return 0, "4343\n" if nazwa in self.aktywne else "0\n"
        nazwa = a[-1]
        if a[0] == "enable":
            if not (self.katalog_jednostek() / nazwa).is_file():
                return 1, f"Failed to enable unit: Unit file {nazwa} does not exist.\n"
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
        raise AssertionError(f"nieoczekiwane systemctl {a}")

    def _loginctl(self, a):
        if a[0] == "show-user":
            return 0, "yes\n" if self.linger else "no\n"
        if a[0] in ("enable-linger", "disable-linger"):
            if self.odmowa_linger:
                return 1, "Could not enable linger: Access denied\n"
            self.ustaw_linger(a[0] == "enable-linger")
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
def host(monkeypatch, tmp_path):
    monkeypatch.setattr(autostart, "_uzytkownik_windows", lambda: SID)
    monkeypatch.setattr(autostart, "_uzytkownik_posix", lambda: "ola")
    monkeypatch.setattr(autostart, "PRZERWA_LAUNCHCTL", 0)
    for nazwa in XDG:                                   # środowisko usługi nie zależy od powłoki, w której biegną testy
        monkeypatch.delenv(nazwa, raising=False)
    h = Host(tmp_path / "dom")
    monkeypatch.setattr(autostart, "KATALOG_LINGER", str(h.katalog_lingera))
    return h


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


def test_dziennik_znaki_konca_wiersza_w_wartosciach_bom_i_zapomnij(u):
    """json.dumps zostawia U+2028, U+2029 i U+0085 bez ucieczki; str.splitlines() przecinał po nich wpis, a następny
    zapis gubił go na stałe. Dziennik zapisany w Notatniku (z BOM) też się czyta."""
    assert zmiany_hosta.zapomnij(u, "linger", uzytkownik="ola") == 0 and not zmiany_hosta.sciezka(u).exists()
    dziwne = ["/dom/a\u2028b", "/dom/c\u2029d", "/dom/e\u0085f"]
    for i, s in enumerate(dziwne):
        zmiany_hosta.dopisz(u, "plik", sciezka=s, sha256=str(i))
    zmiany_hosta.dopisz(u, "plik", sciezka="/dom/x", sha256="x")              # przepisanie pliku niczego nie gubi
    assert [w["szczegoly"]["sciezka"] for w in zmiany_hosta.wpisy(u)] == [*dziwne, "/dom/x"]
    p = zmiany_hosta.sciezka(u)
    p.write_bytes(b"\xef\xbb\xbf" + p.read_bytes().replace(b"\n", b"\r\n"))   # Notatnik: BOM i CRLF
    assert len(zmiany_hosta.wpisy(u)) == 4
    assert zmiany_hosta.zapomnij(u, "plik", sciezka="/dom/x", sha256="x") == 1
    assert zmiany_hosta.zapomnij(u, "plik", sciezka="/dom/x", sha256="x") == 0
    assert [w["szczegoly"]["sciezka"] for w in zmiany_hosta.wpisy(u)] == dziwne
    with pytest.raises(ValueError, match="sekretów"):
        zmiany_hosta.zapomnij(u, "plik", token="x")
    # nazwa pliku spoza UTF-8 (Linux, surrogateescape): wpis wraca bez strat, a reszta dziennika zostaje czytelna
    obca = "/dom/\udcff-pląk"                    # os.fsdecode(b"/dom/\xff-pl\xc4\x85k") na Linuksie i macOS
    w = zmiany_hosta.dopisz(u, "plik", sciezka=obca, sha256="s")
    assert zmiany_hosta.dopisz(u, "plik", sciezka=obca, sha256="s") == w           # bez drugiego wiersza
    assert [x["szczegoly"]["sciezka"] for x in zmiany_hosta.wpisy(u)] == [*dziwne, obca]
    tekst = p.read_text(encoding="utf-8")                                          # cały plik to poprawne UTF-8
    assert "\\udcff" in tekst and "a\u2028b" in tekst


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


def test_cofnij_od_konca_filtr_i_bledy_zostaja(u, host):
    dom = host.dom
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


# ---------------------------------------------------------------- nazwy i środowisko usługi

def test_nazwy_z_przyrostkiem_dla_jarvo_root_i_konta(tmp_path):
    proba = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "proba")})
    nazwa = autostart.nazwa_zadania(proba, kto=SID)
    assert re.fullmatch(rf"Jarvo-{re.escape(SID)}-[0-9a-f]{{8}}", nazwa)
    assert nazwa == autostart.nazwa_zadania(sciezki.uklad({"JARVO_ROOT": str(tmp_path / "proba")}), kto=SID)
    assert nazwa != autostart.nazwa_zadania(sciezki.uklad({"JARVO_ROOT": str(tmp_path / "inna")}), kto=SID)
    # folder Harmonogramu jest wspólny dla wszystkich kont komputera: drugie konto ma inne zadanie
    assert autostart.nazwa_zadania(proba, kto=SID_DRUGI) != nazwa
    skrot = nazwa.rsplit("-", 1)[1]
    assert autostart.etykieta_agenta(proba) == f"pl.jarvo.nadzorca-{skrot}"
    assert autostart.nazwa_jednostki(proba) == f"jarvo-{skrot}.service"
    env = {"LOCALAPPDATA": str(tmp_path / "lad"), "XDG_DATA_HOME": str(tmp_path / "xdg")}
    domyslny = sciezki.uklad(env)
    assert autostart.nazwa_zadania(domyslny, env, kto=SID) == f"Jarvo-{SID}"
    assert autostart.etykieta_agenta(domyslny, env) == "pl.jarvo.nadzorca"
    assert autostart.nazwa_jednostki(domyslny, env) == "jarvo.service"
    assert autostart.nazwa_zadania(domyslny, {**env, "JARVO_ROOT": str(domyslny.root)}, kto=SID) == f"Jarvo-{SID}"
    # zapas bez SID-u: tylko bezpieczne znaki (ukośnik to folder Harmonogramu) i suma pełnej nazwy konta
    michal = autostart.nazwa_zadania(domyslny, env, kto="DOM\\Michał Żółć")
    assert re.fullmatch(r"Jarvo-DOM-Micha-[0-9a-f]{8}", michal), michal
    assert michal != autostart.nazwa_zadania(domyslny, env, kto="DOM\\Michaś Żółć")


@pytest.mark.windows_only
def test_nazwa_zadania_z_sid_biezacego_konta(u):
    sid = autostart._sid()
    assert re.fullmatch(r"S-1-5-\d+(-\d+)+", sid)
    assert autostart.nazwa_zadania(u) == f"Jarvo-{sid}{autostart._przyrostek(u)}"


def test_zmienne_uslugi_korzen_i_katalogi_xdg(tmp_path):
    """launchd i systemd --user nie czytają plików startowych powłoki: korzeń i katalogi XDG idą do definicji."""
    dom = tmp_path / "dom"
    env = {"LOCALAPPDATA": str(tmp_path / "lad"), "XDG_DATA_HOME": str(tmp_path / "dane"),
           "XDG_CACHE_HOME": str(tmp_path / "cache")}
    domyslny = sciezki.uklad(env)
    # Linux, domyślny korzeń: wszystkie cztery katalogi XDG (bez zmiennej domyślne), bez JARVO_ROOT
    assert autostart.zmienne_uslugi(domyslny, "linux", env, dom) == {
        "XDG_DATA_HOME": str(tmp_path / "dane"), "XDG_STATE_HOME": str(dom / ".local" / "state"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"), "XDG_CONFIG_HOME": str(dom / ".config")}
    # macOS: JARVO_ROOT zawsze i tylko te zmienne XDG, które miała powłoka
    assert autostart.zmienne_uslugi(domyslny, "macos", env, dom) == {
        "JARVO_ROOT": str(domyslny.root), "XDG_DATA_HOME": str(tmp_path / "dane"),
        "XDG_CACHE_HOME": str(tmp_path / "cache")}
    env_proby = {**env, "JARVO_ROOT": str(tmp_path / "proba")}
    proba = sciezki.uklad(env_proby)
    z = autostart.zmienne_uslugi(proba, "linux", env_proby, dom)
    assert z["JARVO_ROOT"] == str(proba.root) and z["XDG_DATA_HOME"] == str(tmp_path / "dane")
    # JARVO_ROOT równy domyślnemu korzeniowi: w układzie instalatora logi i cache są w korzeniu, więc zmienna zostaje
    env_jawny = {**env, "JARVO_ROOT": str(domyslny.root)}
    z = autostart.zmienne_uslugi(sciezki.uklad(env_jawny), "linux", env_jawny, dom)
    assert z["JARVO_ROOT"] == str(domyslny.root)
    assert autostart.nazwa_jednostki(sciezki.uklad(env_jawny), env_jawny) == "jarvo.service"


@pytest.mark.linux_only
def test_zmienne_uslugi_odtwarzaja_uklad_instalatora(tmp_path):
    """Nadzorca pod systemd --user liczy z Environment= ten sam korzeń, logi i cache co instalator w powłoce."""
    env = {"HOME": str(tmp_path / "dom"), "XDG_DATA_HOME": str(tmp_path / "dane"),
           "XDG_STATE_HOME": str(tmp_path / "stan"), "XDG_CACHE_HOME": str(tmp_path / "cache")}
    for e in (env, {**env, "JARVO_ROOT": str(tmp_path / "proba")},
              {**env, "JARVO_ROOT": str(tmp_path / "dane" / "jarvo")}):      # jawnie domyślny korzeń
        u = sciezki.uklad(e)
        assert sciezki.uklad(autostart.zmienne_uslugi(u, "linux", e, tmp_path / "dom")) == u, e


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


def test_czytaj_xml_wylaczone_zadanie_i_wyzwalacze():
    """Eksport pomija wartości domyślne; Enabled=false w Settings to wyłączone zadanie, w wyzwalaczu: wyzwalacz."""
    tekst = ('\ufeff<?xml version="1.0" encoding="UTF-16"?>\r\n<Task version="1.2" xmlns="' + autostart.NS + '">'
             "<RegistrationInfo><Description>opis</Description></RegistrationInfo><Triggers>"
             "<LogonTrigger><Enabled>false</Enabled><UserId>HOST\\ola</UserId></LogonTrigger>"
             "<TimeTrigger><StartBoundary>2026-01-01T00:00:00</StartBoundary></TimeTrigger></Triggers>"
             "<Settings><Enabled>false</Enabled><Priority>5</Priority></Settings></Task>")
    z = autostart._czytaj_xml(tekst)
    assert z["wlaczone"] is False and z["wyzwalacze"] == ["LogonTrigger", "TimeTrigger"]
    assert z["wylaczone_wyzwalacze"] == ["LogonTrigger"] and z["ustawienia"]["Priority"] == "5"
    assert z["ustawienia"]["MultipleInstancesPolicy"] == "IgnoreNew"
    bez = autostart._czytaj_xml(tekst.replace("<Enabled>false</Enabled>", ""))
    assert bez["wlaczone"] is True and bez["wylaczone_wyzwalacze"] == []
    pusty = autostart._czytaj_xml('<Task xmlns="' + autostart.NS + '"><Triggers/></Task>')
    assert pusty["wyzwalacze"] == [] and pusty["wlaczone"] is True
    assert autostart._czytaj_xml("to nie XML")["opis"] == ""


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


@pytest.mark.windows_only
def test_stan_na_prawdziwym_harmonogramie_tylko_odczyt(tmp_path):
    """stan() pyta prawdziwy Harmonogram o zadanie, którego nie ma (/Query, sam odczyt): wyłączony, bez błędu."""
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / f"jarvo-{uuid.uuid4().hex[:8]}")})
    s = autostart.stan(u, rejestr=Rejestr())
    assert (s["mechanizm"], s["opis"]) == (None, "wyłączony"), s


def test_windows_wlacz_stan_drugi_raz_i_wylacz(u, host):
    r = Rejestr()
    argv = argv_windows(u)
    nazwa = autostart.nazwa_zadania(u)
    assert nazwa.startswith(f"Jarvo-{SID}-")
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
    assert s["wylaczone_wyzwalacze"] == []
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


def test_windows_wylaczone_zadanie_on_wlacza_z_powrotem(u, host):
    """Zadanie wyłączone w taskschd.msc (albo przez program „przyspieszający start”): stan to pokazuje, a `on`
    włącza je z powrotem przez /Change /ENABLE; gdy /Change odmówi albo wyłączono sam wyzwalacz, rejestracja od nowa."""
    r = Rejestr()
    argv = argv_windows(u)
    nazwa = autostart.nazwa_zadania(u)
    autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    zadanie, wpisy = host.zadania[nazwa], zmiany_hosta.wpisy(u)
    host.wylacz_zadanie(nazwa)
    s = autostart.stan(u, host, system="windows", rejestr=r)
    assert s["mechanizm"] == "harmonogram" and s["nasz"] and s["wlaczony"] is False
    assert s["opis"].startswith("nieaktywny") and "wyłączone w systemie (włączy je jarvo autostart on)" in s["opis"]
    host.polecenia.clear()
    w = autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert w["zmieniony"] and w["uruchomiony"] and "było wyłączone" in w["uwagi"][0]
    assert host.kroki() == [("schtasks", "/Query"), ("schtasks", "/Change"), ("schtasks", "/Run")]
    assert host.polecenia[1][1:] == ["/Change", "/TN", nazwa, "/ENABLE"]
    assert host.zadania[nazwa] == zadanie and zmiany_hosta.wpisy(u) == wpisy     # ta sama definicja, bez wpisu
    assert autostart.stan(u, host, system="windows", rejestr=r)["wlaczony"] is True
    host.wylacz_zadanie(nazwa)
    host.odmowa_change = True
    host.polecenia.clear()
    w = autostart.wlacz(u, argv, host, system="windows", start=False, rejestr=r, log=None)
    assert w["zmieniony"] and host.kroki() == [("schtasks", "/Query"), ("schtasks", "/Change"), ("schtasks", "/Create")]
    assert autostart.stan(u, host, system="windows", rejestr=r)["wlaczony"] is True
    host.zadania[nazwa] = host.zadania[nazwa].replace("<LogonTrigger>", "<LogonTrigger>\r\n      "
                                                      "<Enabled>false</Enabled>", 1)
    s = autostart.stan(u, host, system="windows", rejestr=r)
    assert s["wylaczone_wyzwalacze"] == ["LogonTrigger"] and s["wlaczony"]       # zapasowe dalej go uruchomią
    assert "wyłączone wyzwalacze: logowanie (włączy je jarvo autostart on)" in s["opis"]
    assert "wyłączone w systemie" not in s["opis"]
    host.polecenia.clear()
    w = autostart.wlacz(u, argv, host, system="windows", start=False, rejestr=r, log=None)
    assert w["zmieniony"] and host.kroki() == [("schtasks", "/Query"), ("schtasks", "/Create")]
    assert autostart.stan(u, host, system="windows", rejestr=r)["wylaczone_wyzwalacze"] == []
    assert zmiany_hosta.wpisy(u) == wpisy
    # wszystkie wyzwalacze wyłączone: zadanie samo już nie ruszy, więc stan mówi „nieaktywny” (doctor: uwaga)
    for wyzwalacz in ("LogonTrigger", "SessionStateChangeTrigger", "TimeTrigger"):
        host.zadania[nazwa] = host.zadania[nazwa].replace(f"<{wyzwalacz}>", f"<{wyzwalacz}>\r\n      "
                                                          "<Enabled>false</Enabled>", 1)
    s = autostart.stan(u, host, system="windows", rejestr=r)
    assert s["wlaczony"] is False and s["wylaczone_w_systemie"] is False and s["opis"].startswith("nieaktywny")
    assert ("wyłączone wyzwalacze: logowanie, odblokowanie sesji, co 5 minut (włączy je jarvo autostart on)"
            in s["opis"])
    assert autostart.wlacz(u, argv, host, system="windows", start=False, rejestr=r, log=None)["zmieniony"]
    assert autostart.stan(u, host, system="windows", rejestr=r)["wlaczony"] is True


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


def test_windows_nieczytelne_zadanie_i_harmonogram_bez_listy(u, host):
    """Zadanie jest na liście, ale jego definicji nie da się odczytać: nie nadpisujemy go i nie kasujemy. Gdy
    Harmonogram nie podaje nawet listy (polityka, wyłączona usługa), zostaje wpis HKCU Run, a `off` go zdejmuje."""
    r = Rejestr()
    argv = argv_windows(u)
    nazwa = autostart.nazwa_zadania(u)
    host.zadania[nazwa] = "<Task>nieczytelne</Task>"
    host.nieczytelne.add(nazwa)
    with pytest.raises(autostart.BladAutostartu, match="nie da się odczytać"):
        autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert ("schtasks", "/Create") not in host.kroki() and zmiany_hosta.wpisy(u) == []
    with pytest.raises(autostart.BladAutostartu, match="Nie mogę sprawdzić"):
        autostart.wylacz(u, host, system="windows", rejestr=r, log=None)
    assert ("schtasks", "/Delete") not in host.kroki() and nazwa in host.zadania
    s = autostart.stan(u, host, system="windows", rejestr=r)
    assert s["mechanizm"] == "harmonogram" and s["nasz"] is None and "nie wiadomo" in s["opis"]
    host.zadania.clear()
    host.nieczytelne.clear()
    host.harmonogram_padl = host.odmowa_create = True
    w = autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert w["mechanizm"] == "run" and r.czytaj(autostart.KLUCZ_RUN, nazwa) is not None
    s = autostart.stan(u, host, system="windows", rejestr=r)
    assert s["mechanizm"] == "run" and s["nasz"] and "Harmonogram nie odpowiada" in s["opis"]
    wy = autostart.wylacz(u, host, system="windows", rejestr=r, log=None)
    assert wy["usuniety"] and r.czytaj(autostart.KLUCZ_RUN, nazwa) is None and "nie mogę sprawdzić" in wy["uwagi"][0]
    with pytest.raises(autostart.BladAutostartu, match="Nie mogę sprawdzić"):
        autostart.wylacz(u, host, system="windows", rejestr=r, log=None)


def test_windows_bez_zapasowych_wyzwalaczy_a_potem_wpis_run(u, host):
    r = Rejestr()
    argv = argv_windows(u)
    nazwa = autostart.nazwa_zadania(u)
    host.odmowa_zapasowych = True
    w = autostart.wlacz(u, argv, host, system="windows", rejestr=r, log=None)
    assert w["mechanizm"] == "harmonogram" and w["zmieniony"] and "zapasowych" in w["uwagi"][0]
    assert "jarvo up" in w["uwagi"][0] and "ponowienie po awarii" not in w["uwagi"][0]   # bez obietnicy bez dowodu
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
    zmienne = {"JARVO_ROOT": str(u.root), "XDG_CONFIG_HOME": "/Users/ola/.config"}
    proba = plistlib.loads(autostart.plist_agenta(ARGV_POSIX, u, "pl.jarvo.nadzorca-1", zmienne=zmienne))
    assert proba["EnvironmentVariables"] == zmienne and proba["Label"] == "pl.jarvo.nadzorca-1"
    with pytest.raises(ValueError, match="pełną ścieżkę"):
        autostart.plist_agenta(["python3", "-m", "jarvo"], u)
    with pytest.raises(ValueError, match="zmienna"):
        autostart.plist_agenta(ARGV_POSIX, u, zmienne={"ZŁA NAZWA": "x"})


@pytest.mark.skipif(sys.platform != "darwin", reason="plutil jest tylko na macOS")
def test_plist_przyjmuje_plutil(u, tmp_path):
    plik = tmp_path / "pl.jarvo.nadzorca.plist"
    plik.write_bytes(autostart.plist_agenta(ARGV_POSIX, u, zmienne=autostart.zmienne_uslugi(u, "macos")))
    w = subprocess.run(["/usr/bin/plutil", "-lint", str(plik)], capture_output=True, encoding="utf-8",
                       errors="replace")
    assert w.returncode == 0, w.stdout + w.stderr


def test_macos_wlacz_stan_drugi_raz_zmiana_i_wylacz(u, host):
    dom = host.dom
    et = autostart.etykieta_agenta(u)
    plik = dom / "Library" / "LaunchAgents" / f"{et}.plist"
    domena = f"gui/{autostart._uid()}"
    w = autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, log=None)
    assert w["plik"] == str(plik) and w["zmieniony"] and w["uruchomiony"] and plik.is_file()
    assert host.kroki() == [("launchctl", "print"), ("launchctl", "print-disabled"), ("launchctl", "bootstrap")]
    assert host.polecenia[-1] == [autostart.LAUNCHCTL, "bootstrap", domena, str(plik)]
    assert plistlib.loads(plik.read_bytes())["EnvironmentVariables"] == {"JARVO_ROOT": str(u.root)}
    assert u.logi.is_dir()
    s = autostart.stan(u, host, system="macos", dom=dom)
    assert (s["mechanizm"], s["wlaczony"], s["nasz"], s["dziala"], s["pid"]) == ("launchagent", True, True, True, 4242)
    host.polecenia.clear()
    assert not autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, log=None)["zmieniony"]
    assert host.kroki() == [("launchctl", "print"), ("launchctl", "print-disabled"),
                            ("launchctl", "kickstart")]                                 # działającego nie restartuje
    host.polecenia.clear()
    autostart.wlacz(u, [*ARGV_POSIX, "--gadatliwie"], host, system="macos", dom=dom, log=None)
    assert host.kroki() == [("launchctl", "print"), ("launchctl", "print-disabled"), ("launchctl", "bootout"),
                            ("launchctl", "bootstrap")]
    wy = autostart.wylacz(u, host, system="macos", dom=dom, log=None)
    assert wy["usuniety"] and not plik.exists() and et not in host.agenci
    assert autostart.stan(u, host, system="macos", dom=dom)["opis"] == "wyłączony"
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, log=None)] == ["brak", "brak"]


def test_macos_wylaczony_w_launchd_on_wlacza_z_powrotem(u, host):
    """Po `launchctl disable gui/<uid>/<etykieta>` usługa nie wczyta się (stan przetrwa restart), a bootstrap pada:
    stan to pokazuje, a `on` woła `launchctl enable`."""
    dom = host.dom
    et = autostart.etykieta_agenta(u)
    autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, log=None)
    host.agenci.clear()
    host.wylaczone_agenci.add(et)                       # wyłączony, a po restarcie już się nie wczytał
    s = autostart.stan(u, host, system="macos", dom=dom)
    assert s["mechanizm"] == "launchagent" and s["wlaczony"] is False and "wyłączone w systemie" in s["opis"]
    host.polecenia.clear()
    w = autostart.wlacz(u, ARGV_POSIX, host, system="macos", dom=dom, log=None)
    assert w["zmieniony"] and w["uruchomiony"] and "włączony z powrotem" in w["uwagi"][0]
    assert host.kroki() == [("launchctl", "print"), ("launchctl", "print-disabled"), ("launchctl", "enable"),
                            ("launchctl", "bootstrap")]
    assert host.polecenia[2][1:] == ["enable", f"gui/{autostart._uid()}/{et}"]
    assert et not in host.wylaczone_agenci and et in host.agenci
    assert autostart.stan(u, host, system="macos", dom=dom)["wlaczony"] is True
    # starszy macOS pisze „=> true” zamiast „=> disabled”; sama etykieta z przyrostkiem to inna usługa
    stary = '{\n\t"pl.jarvo.nadzorca" => true\n\t"com.inny" => false\n}\n'
    assert autostart._wylaczony_w_launchd(lambda a: (0, stary), "gui/501", "pl.jarvo.nadzorca") is True
    assert autostart._wylaczony_w_launchd(lambda a: (0, stary), "gui/501", "com.inny") is False
    assert autostart._wylaczony_w_launchd(lambda a: (0, stary), "gui/501", "pl.jarvo") is False
    assert autostart._wylaczony_w_launchd(lambda a: (1, ""), "gui/501", "pl.jarvo.nadzorca") is None


def test_macos_bootstrap_nieudany_i_cofniecie(u, host):
    dom = host.dom
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

def _rozbierz_systemd(wiersz: str, dolar: bool = True) -> list[str]:
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
        if dolar:
            assert "$" not in s.replace("$$", ""), "systemd podstawiłby zmienną"
            s = s.replace("$$", "$")
        slowa.append(s.replace("\0", "%"))
    return slowa


def _srodowisko_jednostki(tekst: str) -> dict[str, str]:
    """Zmienne z wierszy Environment= jednostki (każdy wiersz: jedno przypisanie w cudzysłowie)."""
    wynik = {}
    for x in tekst.splitlines():
        if x.startswith("Environment="):
            (przypisanie,) = _rozbierz_systemd(x.split("=", 1)[1], dolar=False)
            nazwa, wartosc = przypisanie.split("=", 1)
            wynik[nazwa] = wartosc
    return wynik


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
    zmienne = {"JARVO_ROOT": str(u.root), "XDG_DATA_HOME": '/home/ola/dane 100% $HOME "x" \\'}
    assert _srodowisko_jednostki(autostart.jednostka_systemd(argv, u, zmienne=zmienne)) == zmienne
    with pytest.raises(ValueError, match="nowego wiersza"):
        autostart.jednostka_systemd([argv[0], "a\nExecStartPre=/bin/zle"], u)
    with pytest.raises(ValueError, match="zmienna"):
        autostart.jednostka_systemd(argv, u, zmienne={"X": "a\nExecStartPre=/bin/zle"})
    with pytest.raises(ValueError, match="zmienna"):
        autostart.jednostka_systemd(argv, u, zmienne={"X Y": "a"})


def test_linux_wlacz_stan_drugi_raz_wylacz_i_bez_busa(u, host):
    dom = host.dom
    nazwa = autostart.nazwa_jednostki(u)
    plik = dom / ".config" / "systemd" / "user" / nazwa
    w = autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    assert w["plik"] == str(plik) and w["zmieniony"] and w["uruchomiony"] and plik.is_file()
    assert host.kroki() == [("systemctl", "show-environment"), ("systemctl", "show"), ("systemctl", "show"),
                            ("systemctl", "daemon-reload"), ("systemctl", "enable")]
    assert host.polecenia[1][2:] == ["show", "--property=UnitPath"]
    assert host.polecenia[2][2:] == ["show", nazwa, "--property=FragmentPath"]
    assert host.polecenia[-1] == [autostart._systemctl(), "--user", "enable", "--now", nazwa]
    assert ("loginctl", "enable-linger") not in host.kroki()               # linger tylko na życzenie
    # jawne środowisko: korzeń próby i katalogi XDG z chwili instalacji (systemd --user nie czyta ~/.profile)
    assert _srodowisko_jednostki(plik.read_text(encoding="utf-8")) == {
        "JARVO_ROOT": str(u.root), "XDG_DATA_HOME": str(dom / ".local" / "share"),
        "XDG_STATE_HOME": str(dom / ".local" / "state"), "XDG_CACHE_HOME": str(dom / ".cache"),
        "XDG_CONFIG_HOME": str(dom / ".config")}
    s = autostart.stan(u, host, system="linux", dom=dom)
    assert (s["mechanizm"], s["wlaczony"], s["nasz"], s["dziala"], s["pid"]) == ("systemd", True, True, True, 4343)
    assert s["bus"] is True and s["linger"] is False and s["opis"].startswith("włączony")
    host.polecenia.clear()
    assert not autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)["zmieniony"]
    assert host.kroki() == [("systemctl", "show-environment"), ("systemctl", "show"), ("systemctl", "show"),
                            ("systemctl", "enable")]                       # bez daemon-reload
    host.wlaczone.discard(nazwa)                                            # systemctl --user disable właściciela
    s = autostart.stan(u, host, system="linux", dom=dom)
    assert s["wlaczony"] is False and "wyłączone w systemie" in s["opis"]
    autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    assert nazwa in host.wlaczone                                           # `on` włącza z powrotem
    wy = autostart.wylacz(u, host, system="linux", dom=dom, log=None)
    assert wy["usuniety"] and not plik.exists() and not host.aktywne and not host.wlaczone
    assert ("systemctl", "disable") in host.kroki()
    host.bus = False
    with pytest.raises(autostart.BladAutostartu, match="Brak usług systemd użytkownika"):
        autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    assert not plik.exists()


def test_linux_cudza_jednostka_maska_i_przeslanianie_zostaja(u, host, tmp_path):
    """Plik jarvo.service bez naszego znacznika, jednostka o tej nazwie w innym katalogu menedżera albo maska:
    `on` odmawia, niczego nie pisze i nie zostawia wpisu w dzienniku, a `off` cudzego nie kasuje."""
    dom = host.dom
    nazwa = autostart.nazwa_jednostki(u)
    plik = host.katalog_jednostek() / nazwa
    plik.parent.mkdir(parents=True)
    obca = "[Service]\nExecStart=/usr/bin/moja-usluga\n"
    plik.write_text(obca, encoding="utf-8")
    with pytest.raises(autostart.BladAutostartu, match="nie założył Jarvo"):
        autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    assert plik.read_text(encoding="utf-8") == obca and zmiany_hosta.wpisy(u) == [] and not host.wlaczone
    wy = autostart.wylacz(u, host, system="linux", dom=dom, log=None)
    assert not wy["usuniety"] and plik.read_text(encoding="utf-8") == obca and "nie jest Jarva" in wy["uwagi"][0]
    s = autostart.stan(u, host, system="linux", dom=dom)
    assert s["nasz"] is False and s["opis"].startswith("nieaktywny")
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, log=None)] == [] and plik.exists()
    plik.unlink()
    inna = tmp_path / "etc" / nazwa
    inna.parent.mkdir()
    inna.write_text(obca, encoding="utf-8")
    host.obce_fragmenty[nazwa] = str(inna)                 # np. /etc/systemd/user: nasza by ją przesłoniła
    with pytest.raises(autostart.BladAutostartu, match="przesłoniła"):
        autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    host.obce_fragmenty[nazwa] = "/dev/null"               # systemctl --user mask
    with pytest.raises(autostart.BladAutostartu, match="unmask"):
        autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    assert not plik.exists() and zmiany_hosta.wpisy(u) == []
    host.obce_fragmenty[nazwa] = str(tmp_path / "usuniety" / nazwa)    # pamięć menedżera o pliku, którego nie ma
    assert autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, start=False, log=None)["zmieniony"]
    autostart.wylacz(u, host, system="linux", dom=dom, log=None)
    zmiany_hosta.cofnij(u, host, log=None)
    assert not plik.exists() and zmiany_hosta.wpisy(u) == []
    inna.write_text(f"# {autostart.ZNACZNIK} stara kopia Jarva\n[Service]\n", encoding="utf-8")
    host.obce_fragmenty[nazwa] = str(inna)                 # nasza jednostka z innego katalogu nie blokuje
    assert autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)["zmieniony"] and plik.is_file()


def test_linux_katalog_jednostek_wedlug_menedzera(u, host, monkeypatch, tmp_path):
    """XDG_CONFIG_HOME ustawione tylko w powłoce: systemd --user go nie zna, więc jednostka idzie tam, gdzie szuka
    menedżer (UnitPath), a do Environment= trafia wartość z powłoki. Bez busa `off` i stan znajdą ją i tak."""
    dom = host.dom
    nazwa = autostart.nazwa_jednostki(u)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "konfig-powloki"))
    w = autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    plik = dom / ".config" / "systemd" / "user" / nazwa
    assert w["plik"] == str(plik) and nazwa in host.wlaczone               # enable znalazł plik
    srodowisko = _srodowisko_jednostki(plik.read_text(encoding="utf-8"))
    assert srodowisko["XDG_CONFIG_HOME"] == str(tmp_path / "konfig-powloki")
    host.bus = False
    s = autostart.stan(u, host, system="linux", dom=dom)
    assert s["plik"] == str(plik) and s["mechanizm"] == "systemd" and "user bus" in s["opis"]
    assert autostart.wylacz(u, host, system="linux", dom=dom, log=None)["usuniety"] and not plik.exists()
    # menedżer ma własny XDG_CONFIG_HOME (np. z PAM): jednostka idzie do jego katalogu
    host.bus = True
    host.konfig = tmp_path / "konfig-menedzera" / "systemd" / "user"
    host.env_menedzera = {"XDG_CONFIG_HOME": str(tmp_path / "konfig-menedzera")}
    w = autostart.wlacz(u, ARGV_POSIX, host, system="linux", dom=dom, log=None)
    assert w["plik"] == str(host.konfig / nazwa) and nazwa in host.wlaczone


def test_linger_tylko_na_wyrazne_zyczenie(u, host):
    """Wpis w dzienniku dopiero po udanym enable-linger, z odciskiem pliku lingera, a wylacz_linger go usuwa:
    odinstalowanie nie wyłączy lingera, który właściciel włączył sam (przed Jarvem, po nim albo od nowa po tym,
    jak wyłączył nasz poza Jarvem)."""
    assert not autostart.wylacz_linger(u, host, log=None)                    # Jarvo go nie włączał
    host.ustaw_linger(True)                                                  # właściciel włączył go sam
    assert not autostart.wlacz_linger(u, host, log=None) and zmiany_hosta.wpisy(u) == []
    assert not autostart.wylacz_linger(u, host, log=None) and host.linger
    host.ustaw_linger(False)
    host.odmowa_linger = True                                                # polkit odmawia: bez wpisu
    with pytest.raises(autostart.BladAutostartu, match="sudo loginctl enable-linger ola"):
        autostart.wlacz_linger(u, host, log=None)
    assert zmiany_hosta.wpisy(u) == [] and not host.linger
    host.odmowa_linger = False
    assert autostart.wlacz_linger(u, host, log=None) and host.linger
    odcisk = autostart._odcisk_lingera("ola")
    assert odcisk and [(x["rodzaj"], x["szczegoly"]) for x in zmiany_hosta.wpisy(u)] == [
        ("linger", {"uzytkownik": "ola", "odcisk": odcisk})]
    assert ("loginctl", "enable-linger") in host.kroki()
    assert autostart.wylacz_linger(u, host, log=None) and not host.linger
    assert zmiany_hosta.wpisy(u) == []                                       # wpis znika razem z naszą zmianą
    host.ustaw_linger(True)                                                  # potem właściciel włącza go sam
    assert zmiany_hosta.cofnij(u, host, log=None) == [] and host.linger      # odinstalowanie go nie rusza
    host.ustaw_linger(False)
    assert autostart.wlacz_linger(u, host, log=None)
    host.ustaw_linger(False)                                                 # ktoś wyłączył nasz linger sam
    assert autostart.wylacz_linger(u, host, log=None) is False and zmiany_hosta.wpisy(u) == []
    # nasz linger wyłączony poza Jarvem (loginctl), a potem włączony od nowa przez właściciela: inny plik, nie nasz
    assert autostart.wlacz_linger(u, host, log=None)
    host.ustaw_linger(False)
    host.ustaw_linger(True)
    assert [(x["rodzaj"], x["wynik"]) for x in zmiany_hosta.cofnij(u, host, log=None)] == [("linger", "nie-nasze")]
    assert host.linger and zmiany_hosta.wpisy(u) == []
    host.ustaw_linger(False)
    assert autostart.wlacz_linger(u, host, log=None)
    host.ustaw_linger(False)
    host.ustaw_linger(True)
    host.polecenia.clear()
    assert autostart.wylacz_linger(u, host, log=None) is False and host.linger and zmiany_hosta.wpisy(u) == []
    assert ("loginctl", "disable-linger") not in host.kroki()
    # nasz linger dalej włączony: cofnięcie go wyłącza
    host.ustaw_linger(False)
    assert autostart.wlacz_linger(u, host, log=None)
    assert [x["wynik"] for x in zmiany_hosta.cofnij(u, host, log=None)] == ["cofniete"] and not host.linger
    # pliku lingera nie było przy włączaniu (wpis bez odcisku): cofnięcie wyłącza włączony linger jak dotąd
    assert autostart._odcisk_lingera("nikt") is None
    host.ustaw_linger(True)
    zmiany_hosta.dopisz(u, "linger", uzytkownik="ola", odcisk=None)
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


def _sprzataj_zadanie(nazwa: str) -> None:
    zmiany_hosta.uruchom_domyslnie([autostart._schtasks(), "/End", "/TN", nazwa])
    zmiany_hosta.uruchom_domyslnie([autostart._schtasks(), "/Delete", "/TN", nazwa, "/F"])
    zmiany_hosta.Rejestr().usun(autostart.KLUCZ_RUN, nazwa)


@pytest.mark.windows_only
@NA_CI
def test_prawdziwy_harmonogram_na_runnerze_ci(tmp_path):
    """Prawdziwe schtasks: unikalna nazwa spod JARVO_ROOT z SID-em konta, rejestracja, ustawienia z eksportu, drugi
    przebieg bez zmian, zadanie wyłączone w Harmonogramie `on` włącza z powrotem (/Change /ENABLE), cofnięcie
    z dziennika; na końcu sprzątanie, nawet gdy coś pękło."""
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "jarvo")})
    nazwa = autostart.nazwa_zadania(u)
    assert nazwa.startswith(f"Jarvo-{autostart._sid()}-")
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
        assert s["polecenie"] == sys.executable and s["wylaczone_wyzwalacze"] == []
        assert autostart.wlacz(u, argv, start=False, log=None)["zmieniony"] is False
        kod, wyj = zmiany_hosta.uruchom_domyslnie([autostart._schtasks(), "/Change", "/TN", nazwa, "/DISABLE"])
        assert kod == 0, wyj
        s = autostart.stan(u)
        assert s["wlaczony"] is False and "wyłączone w systemie" in s["opis"], s
        w = autostart.wlacz(u, argv, start=False, log=None)
        assert w["zmieniony"] and any("było wyłączone" in x for x in w["uwagi"]), w
        assert autostart.stan(u)["wlaczony"] is True
        assert [x["wynik"] for x in zmiany_hosta.cofnij(u, log=None)] == ["cofniete"]
        assert autostart.stan(u)["mechanizm"] is None
    finally:
        _sprzataj_zadanie(nazwa)


@pytest.mark.windows_only
@NA_CI
def test_prawdziwy_harmonogram_run_i_dziala_na_runnerze_ci(tmp_path):
    """/Run uruchamia zarejestrowane zadanie, a stan() widzi „działa” (Last Result 267009 = SCHED_S_TASK_RUNNING).
    Zadanie „tylko po zalogowaniu” rusza tylko w sesji interaktywnej konta: runner bez niej daje pominięcie
    z powodem, a każdy inny wynik to błąd."""
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "jarvo")})
    nazwa = autostart.nazwa_zadania(u)
    python = Path(sys.executable)
    bez_okna = python.with_name("pythonw.exe")
    argv = [str(bez_okna if bez_okna.is_file() else python), "-c", "import time; time.sleep(90)"]
    try:
        w = autostart.wlacz(u, argv, log=None)
        assert w["mechanizm"] == "harmonogram" and w["uruchomiony"], w
        koniec = time.monotonic() + 30
        s = autostart.stan(u)
        while not s["dziala"] and time.monotonic() < koniec:
            time.sleep(1)
            s = autostart.stan(u)
        if not s["dziala"]:
            _, wiersz = zmiany_hosta.uruchom_domyslnie([autostart._schtasks(), "/Query", "/TN", nazwa, "/FO", "CSV",
                                                        "/V", "/NH"])
            # 267011 = SCHED_S_TASK_HAS_NOT_RUN, -2147020576 = 0x800710E0 (operator odmówił: brak sesji konta)
            if '"267011"' in wiersz or '"-2147020576"' in wiersz:
                pytest.skip(f"Harmonogram nie uruchomił zadania „tylko po zalogowaniu” (runner bez sesji "
                            f"interaktywnej): {wiersz.strip()[:300]}")
            pytest.fail(f"zadanie nie działa po /Run: {wiersz.strip()[:500]}")
        assert "działa" in s["opis"] and s["opis"].startswith("włączony"), s
    finally:
        _sprzataj_zadanie(nazwa)
