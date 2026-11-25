"""hq/plugin/omp_sesje.py: wpisy z sesje.json, bezpieczne ścieżki, skrzynka (idempotencja), stan, przebieg, ogon."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

import atrapa_omp
from conftest import load_script

pytestmark = pytest.mark.skipif(os.name == "nt", reason="sesje omp z blokadą: Linux i macOS")
om = load_script("hq/plugin/omp_sesje.py", "jarvo_omp_sesje")
fcntl = pytest.importorskip("fcntl")


def konfig(dom, **panel):
    return {"nazwa": "Kernel", "skrzynka": str(dom / "k" / "skrzynka"), "czat": "-1001", "watek": "7",
            "panel": {"zaplecze": "omp", "sesje": str(dom / "k" / "sesje"), "sesja": "01a13b13-14db", "cwd": str(dom),
                      "omp_arg": ["--no-context-files", "--append-system-prompt", "~/k/system.md"], "kolejnosc": 2,
                      **panel}}


@pytest.fixture
def w(tmp_path, monkeypatch):
    monkeypatch.setenv("ATRAPA_OMP", str(tmp_path / "atrapa"))
    monkeypatch.setenv("JARVO_OMP", str(atrapa_omp.zrob(tmp_path / "atrapa")))
    om._dzierzawy.clear()
    wpis = om.wpis_z("gpu", konfig(tmp_path), tmp_path)
    (tmp_path / "k" / "sesje").mkdir(parents=True)
    wpis.katalogi()
    return wpis


def test_wpisy_z_konfiguracji(tmp_path):
    k = tmp_path / "jarvo" / "konfig"
    k.mkdir(parents=True)
    zly = konfig(tmp_path)
    zly["skrzynka"] = "/etc/skrzynka"
    (tmp_path / "zewn").mkdir()
    (tmp_path / "link").symlink_to("/tmp")
    dow = konfig(tmp_path)
    dow["panel"]["sesje"] = str(tmp_path / "link" / "sesje")
    (k / "sesje.json").write_text(json.dumps({
        "GPU": konfig(tmp_path), "op": konfig(tmp_path, kolejnosc=0, potwierdzenia=True), "zly": zly, "dow": dow,
        "dev": {"nazwa": "Jarodev", "profil": "jarvo-jarodev"}, "stary": {"nazwa": "X", "skrzynka": "~/x"}}))
    wp = om.wpisy(tmp_path, tmp_path)
    assert sorted(wp) == ["dow", "gpu", "op", "zly"]
    assert wp["zly"].blad == wp["dow"].blad == "niebezpieczna ścieżka"
    assert wp["gpu"].omp_arg[-1] == os.path.expanduser("~/k/system.md")
    lista = om.rozmowcy(tmp_path, tmp_path)
    assert [r["klucz"] for r in lista] == ["op", "dow", "gpu", "zly"] and lista[0]["potwierdzenia"] is True
    assert om.stan(wp["zly"])["stan"] == "offline"


def test_wyslij_idempotentnie_i_przebieg(w):
    r1 = om.wyslij(w, "zrób test", "k1", media=["/x/a.png"])
    r2 = om.wyslij(w, "zrób test", "k1")
    assert r1["nowy"] and not r2["nowy"] and r1["plik"] == r2["plik"]
    d = json.loads((w.nowe / "panel-k1.json").read_text())
    assert d["zrodlo"] == "panel" and d["klucz"] == "k1" and d["media"] == ["/x/a.png"]
    assert om.przebieg(w, "k1")["stan"] == "kolejka"
    (w.nowe / "panel-k1.json").replace(w.zrobione / "panel-k1.json")
    om.zapisz_atomowo(w.zrobione / "panel-k1.json", {**d, "odpowiedz": "ok", "tura": "20261117-120000-abcdef"})
    assert om.wyslij(w, "zrób test", "k1")["nowy"] is False
    p = om.przebieg(w, "k1")
    assert p["stan"] == "gotowe" and p["odpowiedz"] == "ok"
    r = om.ponow(w, "k1")
    assert r["klucz"] == "k1-p1" and (w.nowe / "panel-k1-p1.json").exists()
    with pytest.raises(ValueError):
        om.wyslij(w, "x", "../zly")


def test_stan(w, tmp_path, monkeypatch):
    assert om.stan(w)["stan"] == "wolny"
    om.wyslij(w, "a", "k1")
    s = om.stan(w)
    assert s["stan"] == "kolejka" and s["czeka"] == 1
    with w.blokada.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        assert om.stan(w)["stan"] == "terminal"           # blokada bez zapisu skrzynki = terminal
        assert om.przebieg(w, "k1")["terminal"] is True
        om.zapisz_stan(w, skrzynka={"pid": os.getpid(), "od": time.time()})
        assert om.stan(w)["stan"] == "pracuje"           # skrzynka bierze wiadomość, procesu RPC jeszcze nie ma
        om.zapisz_stan(w, skrzynka=None)
    (tmp_path / "atrapa" / "held.json").write_text(json.dumps([w.sesja]))
    om._dzierzawy.clear()
    assert om.stan(w)["stan"] == "terminal"
    om.zapisz_stan(w, tura={"id": "20261117-120000-abcdef", "pid": os.getpid(), "start": time.time(), "klucze": ["k1"]})
    assert om.stan(w)["stan"] == "pracuje"
    assert om.przebieg(w, "k1") == {"stan": "pracuje", "terminal": False, "tura": "20261117-120000-abcdef",
                                    "odpowiedz": None, "blad": None}
    monkeypatch.delenv("JARVO_OMP")
    monkeypatch.setenv("PATH", str(tmp_path / "pusto"))
    s = om.stan(w)
    assert s["stan"] == "offline" and s["powod"] == "brak programu omp"


def test_ogon_tylko_pelne_linie(w):
    plik = w.tura / "20261117-120000-abcdef.jsonl"
    plik.write_text('{"typ": "delta", "tekst": "Ala"}\n{"typ": "narzedzie", "nazwa": "bash", "intencja": "x"}\n{"typ": "del')
    z, od = om.ogon(w, "20261117-120000-abcdef")
    assert [e["typ"] for e in z] == ["delta", "narzedzie"]
    with plik.open("a") as f:
        f.write('ta", "tekst": " ma"}\n')
    z, od2 = om.ogon(w, "20261117-120000-abcdef", od)
    assert z == [{"typ": "delta", "tekst": " ma"}] and od2 == plik.stat().st_size
    assert om.ogon(w, "../../etc/passwd") == ([], 0)


def test_python_narzedzi_przezywa_aktualizacje(tmp_path):
    """20.11: `pobierz_linki` w sesje.json wskazywał `venvs/narzedzia-bcc37257827c/bin/python`, który aktualizacja
    usunęła, więc Kernel dostał zamiast treści linku „No such file or directory”."""
    venvs = tmp_path / "venvs"
    stary = f"{venvs}/narzedzia-bcc37257827c/bin/python"
    nowy = venvs / "narzedzia-7a424e7199dd" / "bin" / "python"
    nowy.parent.mkdir(parents=True)
    nowy.write_text("")
    assert om._program_narzedzi(stary) == str(nowy)                      # bez stałej ścieżki: obecny venv
    (venvs / "narzedzia").symlink_to(venvs / "narzedzia-7a424e7199dd")
    assert om._program_narzedzi(stary) == f"{venvs}/narzedzia/bin/python"   # z dowiązaniem instalatora: stała
    assert om._program_narzedzi(str(nowy)) == str(nowy)                  # istniejący plik zostaje
    assert om._program_narzedzi("/inne/skrypt.py") == "/inne/skrypt.py"


def test_zatrzymaj_tylko_omp_wpisu(w, tmp_path):
    obcy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        om.zapisz_stan(w, tura={"id": "t", "pid": obcy.pid})
        assert om.zatrzymaj(w) is False and obcy.poll() is None
    finally:
        obcy.kill()
        obcy.wait()
    nasz = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "omp", "--session-dir", str(w.sesje)])
    try:
        # Popen wraca przed exec dziecka: do tego czasu /proc/<pid>/cmdline to jeszcze pytest (InstaBox -n 4, 20.11)
        koniec = time.time() + 10
        while not om.proces_tury(w, nasz.pid) and time.time() < koniec:
            time.sleep(0.01)
        om.zapisz_stan(w, tura={"id": "t", "pid": nasz.pid})
        assert om.zatrzymaj(w) is True
        assert nasz.wait(timeout=10) != 0
    finally:
        nasz.kill()
