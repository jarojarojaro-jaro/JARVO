"""Kanały usługi Komputera natywnie (komputer/kanal.py, docs/NATYWNIE.md J03, J09): adresy z korzenia (ten sam
przepis co nadzorca i wtyczka Operatora), potok nazwany z DACL właściciela na Windows, gniazdo 0600 na POSIX,
sprawdzenie procesu, który trzyma potok, i odczyt z zapisem naraz (I/O z nakładaniem)."""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import nadzorca  # noqa: E402
from komputer import kanal  # noqa: E402

sys.path.insert(0, str(REPO / "komputer" / "plugin"))


@pytest.fixture
def korzen():
    # krótka ścieżka (gniazdo unix ma limit ok. 100 bajtów)
    k = Path(tempfile.mkdtemp(prefix="jk"))
    yield k
    import shutil
    shutil.rmtree(k, ignore_errors=True)


def test_skrot_jak_nadzorca_i_adresy(korzen):
    assert kanal.skrot(korzen) == nadzorca._skrot(korzen)
    cua, ster = kanal.adres(korzen, "cua"), kanal.adres(korzen, "ster")
    if os.name == "nt":
        assert cua == rf"\\.\pipe\jarvo-komputer-cua-{kanal.skrot(korzen)}"
        assert ster.endswith(f"jarvo-komputer-ster-{kanal.skrot(korzen)}")
    else:
        assert cua == str(korzen / "stan" / "komputer" / "cua.sock")
    with pytest.raises(ValueError):
        kanal.adres(korzen, "inny")


def test_wtyczka_liczy_ten_sam_adres(korzen):
    import importlib.util
    spec = importlib.util.spec_from_file_location("jarvo_test_wtyczka_kanal", REPO / "komputer" / "plugin" /
                                                  "__init__.py")
    wtyczka = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wtyczka)
    assert wtyczka.adres_natywny(str(korzen)) == kanal.adres(korzen, "ster")


@pytest.mark.posix_only
def test_dluga_sciezka_gniazda_w_katalogu_tymczasowym():
    dlugi = Path(tempfile.gettempdir()) / ("k" * 120)
    adres = kanal.adres(dlugi, "cua")
    assert len(os.fsencode(adres)) <= kanal.MAKS_GNIAZDA and f"jarvo-{os.getuid()}-" in adres


def _echo_json(s):
    linia = kanal.czytaj_wiersz(s)
    s.sendall((json.dumps({"ok": True, "echo": json.loads(linia), "pid": kanal.pid_klienta(s)}) + "\n").encode())
    s.close()


def test_pytanie_i_odpowiedz(korzen):
    adres = kanal.adres(korzen, "ster")
    srv = kanal.Serwer(adres, _echo_json, "ster").start()
    try:
        for i in range(3):
            odp = kanal.zapytaj(adres, {"polecenie": "stan", "i": i}, 5.0)
            assert odp["ok"] and odp["echo"] == {"polecenie": "stan", "i": i}
        assert srv.dacl
        if os.name == "nt" or sys.platform.startswith("linux"):
            assert odp["pid"] == os.getpid()           # Windows: GetNamedPipeClientProcessId, Linux: SO_PEERCRED
        if os.name != "nt":
            assert stat.S_IMODE(os.stat(adres).st_mode) == 0o600
            assert stat.S_IMODE(os.stat(Path(adres).parent).st_mode) == 0o700
    finally:
        srv.zamknij()
    with pytest.raises(kanal.BladKanalu):
        kanal.zapytaj(adres, {"polecenie": "stan"}, 1.0)


@pytest.mark.windows_only
def test_potok_obcego_procesu_i_drugi_serwer(korzen):
    adres = kanal.adres(korzen, "ster")
    srv = kanal.Serwer(adres, _echo_json, "ster").start()
    try:
        with pytest.raises(kanal.BladKanalu, match="inny proces"):
            kanal.zapytaj(adres, {"polecenie": "stan"}, 5.0, oczekiwany_pid=os.getpid() + 100000)
        assert kanal.zapytaj(adres, {"polecenie": "stan"}, 5.0, oczekiwany_pid=os.getpid())["ok"]
        with pytest.raises(kanal.BladKanalu, match="już istnieje"):
            kanal.Serwer(adres, _echo_json, "ster2").start()
    finally:
        srv.zamknij()


def test_odczyt_i_zapis_naraz(korzen):
    """Wątek czeka na odczycie, drugi pisze: na Windows bez I/O z nakładaniem zapis czekałby na odczyt."""
    def echo(s):
        while True:
            d = s.recv(65536)
            if not d:
                break
            s.sendall(d)
        s.close()
    adres = kanal.adres(korzen, "cua")
    srv = kanal.Serwer(adres, echo, "cua").start()
    k = kanal.polacz(adres, 5.0)
    try:
        k.settimeout(5)
        wynik = []
        w = threading.Thread(target=lambda: wynik.append(k.recv(64)), daemon=True)
        w.start()
        time.sleep(0.3)
        k.sendall(b"abc\n")
        w.join(5)
        assert wynik == [b"abc\n"]
    finally:
        k.close()
        srv.zamknij()


def test_pid_uslugi(korzen):
    assert kanal.pid_uslugi(korzen) is None
    p = kanal.katalog_stanu(korzen) / "usluga.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"pid": 1234}), encoding="utf-8")
    assert kanal.pid_uslugi(korzen) == 1234
    p.write_text("zepsute", encoding="utf-8")
    assert kanal.pid_uslugi(korzen) is None
