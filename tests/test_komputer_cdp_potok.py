"""CDP przez potok (komputer/cdp.py) bez przeglądarki: atrapa przeglądarki w Pythonie czyta polecenia i pisze
odpowiedzi tak jak Chrome z --remote-debugging-pipe (POSIX: deskryptory 3 i 4 z posix_spawn; Windows: uchwyty
z --remote-debugging-io-pipes). Sprawdza rozmowę, zdarzenia, polecenia bez czekania, koniec przeglądarki i to,
że przeglądarka nie dostaje portu DevTools."""
from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from komputer import cdp  # noqa: E402

ATRAPA = textwrap.dedent('''
    import json, os, sys
    if os.name == "nt":
        import msvcrt
        arg = next(a for a in sys.argv if a.startswith("--remote-debugging-io-pipes="))
        r, w = (int(x) for x in arg.split("=", 1)[1].split(","))
        czyt, pisz = msvcrt.open_osfhandle(r, os.O_RDONLY | os.O_BINARY), msvcrt.open_osfhandle(w, os.O_WRONLY | os.O_BINARY)
    else:
        czyt, pisz = 3, 4
    def wyslij(m):
        os.write(pisz, json.dumps(m).encode() + b"\\0")
    bufor = b""
    while True:
        k = os.read(czyt, 65536)
        if not k:
            break
        bufor += k
        while b"\\0" in bufor:
            linia, bufor = bufor.split(b"\\0", 1)
            m = json.loads(linia)
            if m["method"] == "Browser.close":
                wyslij({"id": m["id"], "result": {}})
                sys.exit(0)
            if m["method"] == "Test.blad":
                wyslij({"id": m["id"], "error": {"code": -32000, "message": "nie ma"}})
                continue
            if m["method"] == "Test.cisza":
                continue
            wyslij({"method": "Test.zdarzenie", "params": {"n": m["id"]}, "sessionId": m.get("sessionId")})
            wyslij({"id": m["id"], "result": {"echo": m["method"], "argv": sys.argv[1:], "params": m.get("params")}})
''')


@pytest.fixture
def program(tmp_path):
    skrypt = tmp_path / "atrapa_przegladarki.py"
    skrypt.write_text(ATRAPA, encoding="utf-8")
    if os.name == "nt":
        p = tmp_path / "przegladarka.cmd"
        p.write_text(f'@"{sys.executable}" -I "{skrypt}" %*\r\n', encoding="utf-8")
    else:
        p = tmp_path / "przegladarka"
        p.write_text(f"#!{sys.executable} -I\n" + ATRAPA, encoding="utf-8")
        p.chmod(0o755)
    return str(p)


def test_rozmowa_zdarzenia_i_zamkniecie(program, tmp_path):
    b = cdp.Przegladarka(program, ["--user-data-dir=x", "about:blank"], log=tmp_path / "log.txt")
    zdarzenia = []
    b.sluchaj(lambda m, p, s: zdarzenia.append((m, p, s)))
    b.start()
    try:
        w = b.wyslij("Browser.getVersion", {"a": 1})
        assert w["echo"] == "Browser.getVersion" and w["params"] == {"a": 1}
        assert "--remote-debugging-pipe" in w["argv"] and not any("remote-debugging-port" in a for a in w["argv"])
        if os.name == "nt":
            assert any(a.startswith("--remote-debugging-io-pipes=") for a in w["argv"])
        assert b.wyslij("Page.enable", sesja="S1")["echo"] == "Page.enable"
        oczekiwania = [b.nadaj("Test.x", {"i": i}) for i in range(5)]       # wszystko naraz, potem odpowiedzi
        assert [o.wynik(10)["params"]["i"] for o in oczekiwania] == list(range(5))
        with pytest.raises(cdp.BladCDP, match="nie ma"):
            b.wyslij("Test.blad")
        with pytest.raises(cdp.BladCDP, match="nie odpowiedziała"):
            b.wyslij("Test.cisza", czas=0.5)
        for _ in range(50):
            if len(zdarzenia) >= 7:
                break
            time.sleep(0.05)
        assert ("Test.zdarzenie", {"n": 2}, "S1") in zdarzenia
        assert b.dziala()
    finally:
        kod = b.zamknij(10)
    assert kod == 0 and not b.dziala()
    with pytest.raises(cdp.KoniecPrzegladarki):
        b.wyslij("Browser.getVersion")


def test_padnieta_przegladarka_konczy_czekajacych(program):
    b = cdp.Przegladarka(program, [])
    b.start()
    o = b.nadaj("Test.cisza")
    b.proces.kill()
    with pytest.raises(cdp.KoniecPrzegladarki):
        o.wynik(15)
    b.zamknij(5)


@pytest.mark.posix_only
def test_posix_tylko_deskryptory_3_i_4(program, tmp_path):
    """Przeglądarka nie dziedziczy innych deskryptorów rodzica (PEP 446) ani jego końców potoków, także tych, które
    proces dostał od swojego rodzica bez CLOEXEC (CI: runner zostawiał 142–145)."""
    import fcntl
    plik = os.open(str(tmp_path / "odziedziczony"), os.O_WRONLY | os.O_CREAT, 0o600)
    obcy = fcntl.fcntl(plik, fcntl.F_DUPFD, 150)        # jak od rodzica: wysoki numer, bez CLOEXEC
    os.close(plik)
    os.set_inheritable(obcy, True)
    b = cdp.Przegladarka(program, [])
    b.start()
    try:
        pid = b.pid
        fds = sorted(int(x) for x in os.listdir(f"/proc/{pid}/fd")) if Path(f"/proc/{pid}/fd").is_dir() else None
        if fds is not None:
            assert {0, 1, 2, 3, 4} <= set(fds) and max(fds) < 10
        assert not os.get_inheritable(obcy)               # macOS bez /proc: ten sam warunek po stronie rodzica
        assert os.getpgid(pid) == pid                     # własna grupa procesów: zatrzymanie całej grupy
    finally:
        b.zamknij(5)
        os.close(obcy)
