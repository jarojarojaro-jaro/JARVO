"""Nadzorca procesów Jarva, `jarvo serwis` (docs/NATYWNIE.md: H04, H09, H22, c2, I10, N03), na atrapach usług, bez
Hermesa: restart po kodzie 75, postój po 78, rosnąca przerwa z sufitem i zerowaniem, kolejność startu z gotowością
(plik i serwer HTTP na 127.0.0.1:191xx), jedna instancja na korzeń, kanał sterowania (status, restart, stop, zły
klucz), logi z rotacją „kopiuj i przytnij”, zatrzymanie łagodne i twarde, sprzątanie po poprzednim nadzorcy, usługi
Jarva (argv i zmienne Hermesa f97608f), pytanie do potoku sterującego bramy, a na Windows launcher z dzieckiem
(zabity launcher i dziecko, wnuk żyje) i DACL potoku kanału."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from multiprocessing import connection
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import nadzorca, przenosne, sciezki, srodowisko  # noqa: E402

WINDOWS = os.name == "nt"
# Na Windows `Scripts\python.exe` venvu to launcher z procesem potomnym, a atrapa ma być jednym procesem
# (test launchera buduje drzewo sam); bazowy interpreter wystarczy, bo atrapy biorą tylko bibliotekę standardową.
PY = sys.executable
if WINDOWS and Path(getattr(sys, "_base_executable", "") or "").is_file():
    PY = sys._base_executable
Usluga = nadzorca.Usluga

ATRAPA = r'''
import json, os, signal, sys, time
plik, tryb = sys.argv[1], sys.argv[2]
def koniec(*_):
    sys.exit(0)
for nazwa in ("SIGTERM", "SIGBREAK", "SIGINT"):
    if hasattr(signal, nazwa):
        signal.signal(getattr(signal, nazwa), signal.SIG_IGN if tryb == "uparta" else koniec)
with open(plik, "a", encoding="utf-8") as f:
    f.write(json.dumps({"pid": os.getpid(), "t": time.time()}) + "\n")
with open(plik, encoding="utf-8") as f:
    n = len(f.read().splitlines())
if tryb == "75-raz" and n == 1:
    sys.exit(75)
if tryb in ("78", "1"):
    sys.exit(int(tryb))
if tryb == "1-po":
    time.sleep(float(sys.argv[3]))
    sys.exit(1)
if tryb == "gotowa-po":
    time.sleep(float(sys.argv[3]))
    open(sys.argv[4], "w").close()
if tryb == "gada":
    serie, rozmiar, log = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    for k in range(serie):
        sys.stdout.write(f"seria {k} " + "x" * rozmiar + "\n")   # jeden zapis większy niż limit logu
        sys.stdout.flush()
        koniec = time.time() + 30
        while os.path.getsize(log) >= rozmiar and time.time() < koniec:
            time.sleep(0.01)                                     # czeka, aż nadzorca skopiuje i przytnie
    print("KONIEC-GADANIA", flush=True)
if tryb == "http":
    from http.server import BaseHTTPRequestHandler, HTTPServer
    time.sleep(float(sys.argv[4]))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/api/status" else 404)
            self.end_headers()
            self.wfile.write(b"{}")
        def log_message(self, *a):
            pass
    HTTPServer(("127.0.0.1", int(sys.argv[3])), H).serve_forever()
while True:
    time.sleep(0.05)
'''

SZYBKO = dict(przerwa_restartu=0.2, przerwa_min=0.1, przerwa_max=0.4, limit_stopu=5, limit_kolejnosci=10,
              co_ile_gotowosc=0.05, co_ile_rotacja=0.05, takt=0.02, kanal=False)


def atrapa(plik: Path, tryb: str, *reszta) -> list[str]:
    return [PY, "-c", ATRAPA, str(plik), tryb, *map(str, reszta)]


def nowy(u, uslugi, **kw) -> nadzorca.Nadzorca:
    return nadzorca.Nadzorca(u, uslugi, dict(os.environ), **{**SZYBKO, **kw})


@pytest.fixture
def u(tmp_path):
    return sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})


@contextmanager
def dziala(n: nadzorca.Nadzorca):
    """Nadzorca w wątku na czas bloku; na końcu łagodne zatrzymanie i sprawdzenie, że pętla się skończyła."""
    bledy: list[BaseException] = []

    def cel():
        try:
            n.uruchom()
        except BaseException as e:            # noqa: BLE001 - przekazujemy do testu
            bledy.append(e)

    t = threading.Thread(target=cel, daemon=True)
    t.start()
    try:
        yield t
    finally:
        n.zatrzymaj()
        t.join(60)
    assert not t.is_alive(), "nadzorca nie zatrzymał się"
    if bledy:
        raise bledy[0]


def czekaj(warunek, limit: float = 20.0, opis: str = "warunek"):
    koniec = time.monotonic() + limit
    while time.monotonic() < koniec:
        wynik = warunek()
        if wynik:
            return wynik
        time.sleep(0.02)
    raise AssertionError(f"{opis}: nie doczekałem się w {limit} s")


def starty(plik: Path) -> list[dict]:
    try:
        return [json.loads(x) for x in Path(plik).read_text(encoding="utf-8").splitlines() if x.strip()]
    except FileNotFoundError:
        return []


def usluga(n: nadzorca.Nadzorca, nazwa: str) -> dict:
    return (n.stan().get("uslugi") or {}).get(nazwa) or {}


def wolny_port() -> int:
    for port in range(19150, 19200):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    pytest.skip("brak wolnego portu 19150–19199")


def test_restart_po_kodzie_75(u, tmp_path):
    plik = tmp_path / "a.jsonl"
    n = nowy(u, [Usluga("a", atrapa(plik, "75-raz"))])
    with dziala(n):
        czekaj(lambda: len(starty(plik)) >= 2, opis="drugi start po kodzie 75")
        s = czekaj(lambda: (x := usluga(n, "a")).get("restarty") == 1 and x.get("stan") == "dziala" and x)
        assert s["ostatni_kod"] == 75 and s["pid"] == starty(plik)[1]["pid"] and s["od"]
    t = starty(plik)
    assert len(t) == 2 and t[1]["t"] - t[0]["t"] >= 0.2


def test_postoj_po_kodzie_78_z_powodem_bez_sekretow(u, tmp_path):
    plik = tmp_path / "a.jsonl"
    powod = "telegram: token 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw już obsługuje inny profil"
    n = nowy(u, [Usluga("a", atrapa(plik, "78"), powod_postoju=lambda: powod)])
    with dziala(n):
        czekaj(lambda: usluga(n, "a").get("stan") == "postoj", opis="postój po 78")
        time.sleep(0.5)                                   # postój = bez ponowień
        s = usluga(n, "a")
        assert len(starty(plik)) == 1 and s["ostatni_kod"] == 78 and s["pid"] is None
        assert "kod 78" in s["powod"] and "inny profil" in s["powod"] and "AAHdq" not in s["powod"]
        n.restart("a")                                    # właściciel poprawił konfigurację
        czekaj(lambda: len(starty(plik)) == 2 and usluga(n, "a").get("stan") == "postoj", opis="restart z postoju")
        assert usluga(n, "a")["restarty"] == 1
    plik_stanu = json.loads((u.stan / "nadzorca.json").read_text(encoding="utf-8"))
    assert plik_stanu["uslugi"]["a"]["stan"] == "postoj"


def przerwy_z_dziennika(u, nazwa: str) -> list[float]:
    """Przerwy przed ponowieniem z dziennika nadzorcy (dokładne, niezależne od obciążenia komputera)."""
    tekst = (u.logi / "nadzorca.log").read_text(encoding="utf-8")
    return [float(x) for x in re.findall(rf"{nazwa}: kod [^;\n]*; ponowienie za ([\d.]+) s", tekst)]


def test_inne_kody_rosnaca_przerwa_z_sufitem(u, tmp_path):
    plik = tmp_path / "a.jsonl"
    n = nowy(u, [Usluga("a", atrapa(plik, "1"))], przerwa_min=0.1, przerwa_max=0.4)
    with dziala(n):
        czekaj(lambda: len(starty(plik)) >= 5, limit=30, opis="pięć startów")
        s = czekaj(lambda: (x := usluga(n, "a")).get("stan") == "ponowienie" and x)
        assert s["ostatni_kod"] == 1 and s["bledy_z_rzedu"] >= 4 and s["nastepny_start"]
        assert "ponowienie za" in s["powod"]
    assert przerwy_z_dziennika(u, "a")[:5] == [0.1, 0.2, 0.4, 0.4, 0.4]          # 5 s → 5 min w małej skali
    t = [x["t"] for x in starty(plik)]
    przerwy = [b - a for a, b in zip(t, t[1:])]
    assert przerwy[0] >= 0.1 and przerwy[1] >= 0.2 and przerwy[2] >= 0.4 and przerwy[3] >= 0.4


def test_przerwa_zeruje_sie_po_dlugim_dzialaniu(u, tmp_path):
    plik = tmp_path / "a.jsonl"
    n = nowy(u, [Usluga("a", atrapa(plik, "1-po", 0.25))], przerwa_min=0.1, przerwa_max=5, reset_po=0.15)
    with dziala(n):
        czekaj(lambda: len(starty(plik)) >= 4, limit=20, opis="cztery starty")
        assert usluga(n, "a")["bledy_z_rzedu"] == 1
    przerwy = przerwy_z_dziennika(u, "a")
    assert len(przerwy) >= 3 and set(przerwy) == {0.1}                           # zawsze od początku


def test_kolejnosc_startu_czeka_na_gotowosc(u, tmp_path):
    pa, pb, gotowa = tmp_path / "a.jsonl", tmp_path / "b.jsonl", tmp_path / "a.gotowa"
    a = Usluga("a", atrapa(pa, "gotowa-po", 0.5, gotowa), gotowa=gotowa.exists, kolejnosc=0)
    b = Usluga("b", atrapa(pb, "spi"), kolejnosc=1)
    n = nowy(u, [b, a])                                   # kolejność z pola, nie z listy
    with dziala(n):
        czekaj(lambda: starty(pb), opis="start b")
        sa, sb = usluga(n, "a"), usluga(n, "b")
        assert sa["gotowa"] is True and sa["gotowa_od"] and sb["gotowa"] is None
        assert starty(pb)[0]["t"] >= gotowa.stat().st_mtime - 0.05
        assert starty(pb)[0]["t"] - starty(pa)[0]["t"] >= 0.5


def test_kolejnosc_po_limicie_startuje_mimo_braku_gotowosci(u, tmp_path):
    pa, pb = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    n = nowy(u, [Usluga("a", atrapa(pa, "spi"), gotowa=lambda: False), Usluga("b", atrapa(pb, "spi"), kolejnosc=1)],
             limit_kolejnosci=0.4)
    przed = time.time()
    with dziala(n):
        czekaj(lambda: starty(pb), opis="start b po limicie")
        assert usluga(n, "a")["gotowa"] is False
    assert starty(pb)[0]["t"] >= przed + 0.4             # limit liczy się od uruchomienia a
    assert "b: a nie zgłosiła gotowości w 0.4 s, startuję mimo to" in (u.logi / "nadzorca.log").read_text(
        encoding="utf-8")


def test_gotowosc_przez_http_jak_panel(u, tmp_path):
    port = wolny_port()
    adres = f"http://127.0.0.1:{port}/api/status"
    n = nowy(u, [Usluga("panel", atrapa(tmp_path / "p.jsonl", "http", port, 0.3),
                        gotowa=partial(nadzorca.http_gotowa, adres))])
    with dziala(n):
        s = czekaj(lambda: (x := usluga(n, "panel")).get("gotowa") is True and x, opis="panel gotowy")
        assert s["stan"] == "dziala"
        assert nadzorca.http_gotowa(f"http://127.0.0.1:{port}/inne") is False      # 404
    assert nadzorca.http_gotowa(adres, limit=0.5) is False                         # po zatrzymaniu nikt nie słucha


def test_http_gotowa_tylko_200(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/api/status" else 503)
            self.end_headers()

        def log_message(self, *_a):
            pass

    port = wolny_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert nadzorca.http_gotowa(f"http://127.0.0.1:{port}/api/status") is True
        assert nadzorca.http_gotowa(f"http://127.0.0.1:{port}/startuje") is False
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert nadzorca.http_gotowa(f"http://127.0.0.1:{port}/api/status", limit=0.5) is False


def test_jedna_instancja_na_korzen(u, tmp_path, monkeypatch, capsys):
    pa, pb = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    n = nowy(u, [Usluga("a", atrapa(pa, "spi"))])
    with dziala(n):
        czekaj(lambda: usluga(n, "a").get("stan") == "dziala", opis="pierwszy nadzorca")
        drugi = nowy(u, [Usluga("a", atrapa(pb, "spi"))])
        with pytest.raises(nadzorca.NadzorcaJuzDziala, match=f"już działa .*pid {os.getpid()}"):
            drugi.uruchom()
        monkeypatch.setenv("JARVO_ROOT", str(u.root))
        assert nadzorca.main([]) == 1
        assert "już działa" in capsys.readouterr().err
    assert not starty(pb)


def _klient(u):
    try:
        k = nadzorca.polacz(u, limit=5)
        k.status()
        return k
    except nadzorca.NadzorcaNieDziala:
        return None


def test_kanal_status_restart_stop_i_zly_klucz(u, tmp_path):
    plik = tmp_path / "a.jsonl"
    n = nowy(u, [Usluga("a", atrapa(plik, "spi"))], kanal=True)
    t = threading.Thread(target=n.uruchom, daemon=True)
    t.start()
    try:
        k = czekaj(lambda: _klient(u), opis="kanał nadzorcy")
        stan = czekaj(lambda: (x := k.status())["uslugi"]["a"]["stan"] == "dziala" and starty(plik) and x)
        assert stan["nadzorca"]["pid"] == os.getpid() and stan["nadzorca"]["stan"] == "dziala"
        assert stan["uslugi"]["a"]["pid"] == starty(plik)[0]["pid"]
        assert k.restart("a")["ok"] is True
        czekaj(lambda: len(starty(plik)) == 2 and k.status()["uslugi"]["a"]["restarty"] == 1, opis="restart")
        assert k.status()["uslugi"]["a"]["pid"] == starty(plik)[1]["pid"]
        with pytest.raises(nadzorca.BladNadzorcy, match="Nie ma usługi"):
            k.restart("nie-ma")
        adres, rodzina = nadzorca.adres_kanalu(u)
        with pytest.raises(connection.AuthenticationError):
            connection.Client(adres, rodzina, authkey=b"zly-klucz-z-zewnatrz")
        assert k.status()["uslugi"]["a"]["stan"] == "dziala"           # kanał działa dalej
        cichy = connection.Client(adres, rodzina)                        # połączony, ale bez klucza i bez słowa
        try:
            assert k.status()["uslugi"]["a"]["stan"] == "dziala"       # nie blokuje innych klientów
        finally:
            cichy.close()
        if not WINDOWS:
            assert Path(adres).stat().st_mode & 0o777 == 0o600
            assert Path(adres).parent.stat().st_mode & 0o777 == 0o700
        assert ((u.stan / "nadzorca.klucz").stat().st_size == 32)
        assert k.stop()["ok"] is True
        t.join(30)
        assert not t.is_alive()
    finally:
        n.zatrzymaj()
        t.join(30)
    assert not (u.stan / "nadzorca.klucz").exists()
    with pytest.raises(nadzorca.NadzorcaNieDziala):
        nadzorca.polacz(u)
    log = (u.logi / "nadzorca.log").read_text(encoding="utf-8")
    assert "odrzucone połączenie" in log and "zly-klucz" not in log


def test_main_bez_nadzorcy(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path / "j"))
    assert nadzorca.main(["--status"]) == 1
    assert "nie działa" in capsys.readouterr().err
    assert nadzorca.main([]) == 1                                       # brak instalacji Hermesa
    assert "current.json" in capsys.readouterr().err


def test_dziennik_kopiuj_i_przytnij_bez_dziury(tmp_path):
    d = nadzorca._Dziennik(tmp_path / "x.log", maks=100, kopie=2)
    f = d.otworz()                                       # jak uchwyt usługi: otwarty przez całą rotację
    try:
        f.write(b"a" * 150)
        assert d.rotuj() is True
        f.write(b"b" * 10)
        assert (tmp_path / "x.log").read_bytes() == b"b" * 10       # dopisane od zera, bez dziury z zer
        assert (tmp_path / "x.log.1").read_bytes() == b"a" * 150
        assert d.rotuj() is False                                     # za mały
        f.write(b"c" * 95)
        assert d.rotuj() is True and d.rotuj(wymus=True) is True
        f.write(b"d")
    finally:
        f.close()
    assert sorted(p.name for p in tmp_path.glob("x.log*")) == ["x.log", "x.log.1", "x.log.2"]
    assert (tmp_path / "x.log").read_bytes() == b"d" and (tmp_path / "x.log.2").read_bytes() == b"b" * 10 + b"c" * 95


def test_logi_uslugi_rotacja_przy_pracujacym_procesie(u, tmp_path):
    log = u.logi / "a.log"
    n = nowy(u, [Usluga("a", atrapa(tmp_path / "a.jsonl", "gada", 5, 45_000, log))], log_max=40_000, log_kopie=3)

    def tekst(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, PermissionError):     # Windows: plik właśnie zmienia nazwę przy rotacji
            return ""

    with dziala(n):
        czekaj(lambda: "KONIEC-GADANIA" in tekst(log), limit=60, opis="koniec gadania")
    assert sorted(p.name for p in u.logi.glob("a.log*")) == ["a.log", "a.log.1", "a.log.2", "a.log.3"]
    for p in u.logi.glob("a.log*"):
        assert b"\x00" not in p.read_bytes(), f"{p.name}: dziura po przycięciu"
    assert "seria 4 " in tekst(log.with_name("a.log.1")) and "seria 3 " in tekst(log.with_name("a.log.2"))
    assert "seria 2 " in tekst(log.with_name("a.log.3")) and "seria 1 " not in tekst(log.with_name("a.log.3"))
    assert log.stat().st_size < 45_000                                # proces pisał dalej do przyciętego pliku
    dziennik = (u.logi / "nadzorca.log").read_text(encoding="utf-8")
    assert "a: start (pid" in dziennik and "a: zatrzymany" in dziennik


def test_zatrzymanie_lagodne_i_twarde(u, tmp_path):
    pa, pb = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    pidy: list[int] = []
    n = nowy(u, [Usluga("a", atrapa(pa, "spi"), przed_stopem=pidy.extend), Usluga("b", atrapa(pb, "uparta"))],
             limit_stopu=0.8)
    with dziala(n):
        czekaj(lambda: starty(pa) and starty(pb), opis="obie usługi")
        t0 = time.monotonic()
    czas = time.monotonic() - t0
    stan = nadzorca.stan_z_pliku(u)
    assert stan["uslugi"]["a"]["ostatni_kod"] == 0                    # obsłużyła SIGTERM albo Ctrl+Break
    assert stan["uslugi"]["b"]["ostatni_kod"] != 0                    # zabita po limicie
    assert pidy == [starty(pa)[0]["pid"]]                             # przed_stopem dostał właściwy proces
    assert 0.8 <= czas < 15
    assert stan["uslugi"]["a"]["stan"] == stan["uslugi"]["b"]["stan"] == "zatrzymana"
    assert stan["nadzorca"]["stan"] == "zatrzymany" and stan["dziala"] is False
    assert "b: nie skończył się w 0.8 s, zabity" in (u.logi / "nadzorca.log").read_text(encoding="utf-8")


def test_sprzata_proces_po_poprzednim_nadzorcy(u, tmp_path):
    stary_plik, plik = tmp_path / "stary.jsonl", tmp_path / "a.jsonl"
    flagi = {"creationflags": 0x08000000 | 0x00000200} if WINDOWS else {"start_new_session": True}
    stary = subprocess.Popen(atrapa(stary_plik, "spi"), stdin=subprocess.DEVNULL, **flagi)
    try:
        czekaj(lambda: starty(stary_plik), opis="stary proces")
        odcisk = nadzorca._odcisk(stary.pid)
        assert odcisk and nadzorca._odcisk(stary.pid) == odcisk
        przenosne.zapisz_atomowo(u.stan / "nadzorca.json", json.dumps({"uslugi": {
            "a": {"pid": stary.pid, "odcisk": odcisk, "launcher": False},
            "b": {"pid": os.getpid(), "odcisk": "1"},                   # ten sam PID, inny proces: nie ruszamy
        }}))
        n = nowy(u, [Usluga("a", atrapa(plik, "spi"))])
        with dziala(n):
            czekaj(lambda: starty(plik), opis="nowy proces")
            assert stary.wait(10) == 0                                  # łagodnie, przed startem nowego
        log = (u.logi / "nadzorca.log").read_text(encoding="utf-8")
        assert f"a: proces {stary.pid} po poprzednim nadzorcy" in log and "b: proces" not in log
    finally:
        if stary.poll() is None:
            stary.kill()


def test_uslugi_jarva_argv_i_srodowisko_hermesa(tmp_path):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    with pytest.raises(nadzorca.BladNadzorcy, match="current.json"):
        nadzorca.uslugi_jarva(u, {})
    checkout = tmp_path / "program" / "hermes" / "f97608f"
    py = srodowisko.hermes_python(checkout)
    web = tmp_path / "web-dist"
    przenosne.zapisz_atomowo(u.program / "current.json",
                             json.dumps({"hermes": str(checkout), "web_dist": str(web)}))
    with pytest.raises(nadzorca.BladNadzorcy, match="Brak Pythona Hermesa"):
        nadzorca.uslugi_jarva(u, {})
    py.parent.mkdir(parents=True)
    py.write_bytes(b"")
    u.dane.mkdir(parents=True)
    env = srodowisko.srodowisko(u, {"PATH": os.environ.get("PATH", ""), "JARVO_PANEL_PORT": "19123"})
    brama, panel = nadzorca.uslugi_jarva(u, env)
    assert (brama.nazwa, panel.nazwa) == ("brama", "panel") and brama.kolejnosc < panel.kolejnosc
    assert Path(brama.argv[0]) == py and Path(panel.argv[0]) == py
    m = brama.argv.index("-m")
    assert brama.argv[m:] == ["-m", "hermes_cli.main", "gateway", "run", "--external-supervisor"]
    assert panel.argv[m:] == ["-m", "hermes_cli.main", "dashboard", "--host", "127.0.0.1", "--port", "19123",
                              "--no-open", "--skip-build"]
    assert brama.env["HERMES_GATEWAY_DETACHED"] == "1" and brama.env["HERMES_SUPERVISED_CHILD"] == "1"
    assert panel.env["HERMES_SUPERVISED_CHILD"] == "1" and "HERMES_GATEWAY_DETACHED" not in panel.env
    assert brama.env["HERMES_HOME"] == str(u.dane) and Path(brama.cwd) == u.dane == Path(panel.cwd)
    assert "HERMES_WEB_DIST" not in panel.env                         # dist bez index.html nie istnieje
    assert panel.gotowa.args == ("http://127.0.0.1:19123/api/status",)
    assert brama.gotowa() is False and brama.przed_stopem is not None and brama.powod_postoju() is None
    (u.dane / "gateway_state.json").write_text(json.dumps({"gateway_state": "startup_failed",
                                                           "exit_reason": "token collision with profile x"}),
                                               encoding="utf-8")
    assert brama.powod_postoju() == "token collision with profile x"
    web.mkdir()
    (web / "index.html").write_text("<html></html>", encoding="utf-8")
    assert nadzorca.uslugi_jarva(u, env)[1].env["HERMES_WEB_DIST"] == str(web)
    bez_portu = {k: v for k, v in env.items() if k != "JARVO_PANEL_PORT"}
    assert "9119" in nadzorca.uslugi_jarva(u, bez_portu)[1].argv
    with pytest.raises(nadzorca.BladNadzorcy, match="JARVO_PANEL_PORT"):
        nadzorca.uslugi_jarva(u, {**env, "JARVO_PANEL_PORT": "abc"})


@contextmanager
def atrapa_kontroli_bramy(dane: Path, odpowiedz: dict):
    """Serwer jak gateway/control_socket.py Hermesa: jedna linia JSON tam i z powrotem na połączenie."""
    petla = asyncio.new_event_loop()
    gotowe, zamknij, sprzatnij = threading.Event(), [], []
    linia = json.dumps(odpowiedz).encode("utf-8") + b"\n"

    async def start():
        if WINDOWS:
            class Protokol(asyncio.Protocol):
                def connection_made(self, transport):
                    self.t, self.bufor = transport, b""

                def data_received(self, dane_):
                    self.bufor += dane_
                    if b"\n" in self.bufor:
                        self.t.write(linia)
                        self.t.close()

            serwery = await petla.start_serving_pipe(Protokol, nadzorca.potok_bramy(dane))
            zamknij.extend(s.close for s in serwery)
        else:
            async def obsluz(czytnik, pisarz):
                await czytnik.readline()
                pisarz.write(linia)
                await pisarz.drain()
                pisarz.close()

            sciezka = dane / "gateway.sock"
            if len(os.fsencode(str(sciezka))) > 100:                   # jak Hermes: krótkie gniazdo + wskaźnik
                krotki = Path(tempfile.mkdtemp(prefix="gw", dir="/tmp"))
                sprzatnij.append(krotki)
                sciezka = krotki / "g.sock"
                (dane / "gateway.sock.path").write_text(str(sciezka), encoding="utf-8")
            serwer = await asyncio.start_unix_server(obsluz, path=str(sciezka))
            zamknij.append(serwer.close)
        gotowe.set()

    def watek():
        asyncio.set_event_loop(petla)
        petla.run_until_complete(start())
        petla.run_forever()

    t = threading.Thread(target=watek, daemon=True)
    t.start()
    assert gotowe.wait(10)
    try:
        yield
    finally:
        def stop():
            for z in zamknij:
                z()
            petla.call_later(0.2, petla.stop)            # transporty domykają się w pętli

        petla.call_soon_threadsafe(stop)
        t.join(10)
        petla.close()
        for k in sprzatnij:
            shutil.rmtree(k, ignore_errors=True)


def test_zapytaj_brame_przez_potok_sterujacy(tmp_path):
    dane, dane2 = tmp_path / "dane", tmp_path / "dane2"
    dane.mkdir()
    dane2.mkdir()
    assert nadzorca.zapytaj_brame(dane) is None and nadzorca.brama_gotowa(dane) is False
    with atrapa_kontroli_bramy(dane, {"ok": True, "protocol": 1, "result": {"kind": "gateway", "pid": 4242}}):
        assert nadzorca.zapytaj_brame(dane) == {"kind": "gateway", "pid": 4242}
        assert nadzorca.brama_gotowa(dane) is True
        assert nadzorca.brama_gotowa(dane2) is False                  # inny HERMES_HOME = inny potok
    with atrapa_kontroli_bramy(dane2, {"ok": False, "error": "unknown verb"}):
        assert nadzorca.zapytaj_brame(dane2) is None


LAUNCHER = r'''
import ctypes, signal, subprocess, sys
ctypes.windll.kernel32.SetConsoleCtrlHandler(None, 1)
for nazwa in ("SIGINT", "SIGBREAK"):
    signal.signal(getattr(signal, nazwa), signal.SIG_IGN)
dziecko = subprocess.Popen([sys.executable, "-c", sys.argv[1], *sys.argv[2:]])
sys.exit(dziecko.wait())
'''

DZIECKO = r'''
import ctypes, json, os, signal, subprocess, sys, time
ctypes.windll.kernel32.SetConsoleCtrlHandler(None, 1)
for nazwa in ("SIGINT", "SIGBREAK"):
    signal.signal(getattr(signal, nazwa), signal.SIG_IGN)
wnuk = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], creationflags=0x08000000)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({"dziecko": os.getpid(), "wnuk": wnuk.pid}, f)
while True:
    time.sleep(0.05)
'''


@pytest.mark.windows_only
def test_windows_zatrzymanie_launchera_z_dzieckiem_bez_wnukow(u, tmp_path):
    """Jak venvlauncher: dziecko dzieli konsolę i grupę launchera i ignoruje Ctrl+Break (brama z
    HERMES_GATEWAY_DETACHED=1); wnuk ma własną konsolę jak pracownik kanbana i musi przeżyć."""
    plik = tmp_path / "drzewo.json"
    pidy: list[int] = []
    n = nowy(u, [Usluga("brama", [PY, "-c", LAUNCHER, DZIECKO, str(plik)], launcher=True,
                        przed_stopem=pidy.extend)], limit_stopu=0.5)
    wnuk = None
    try:
        with dziala(n):
            drzewo = czekaj(lambda: plik.exists() and plik.stat().st_size and
                            json.loads(plik.read_text(encoding="utf-8")), opis="drzewo procesów")
            wnuk = drzewo["wnuk"]
            s = czekaj(lambda: (x := usluga(n, "brama")).get("pidy") and x, opis="dzieci launchera w stanie")
            assert s["launcher"] is True and s["pidy"] == [drzewo["dziecko"]]
            assert [p for p, _ in nadzorca.dzieci(s["pid"])] == [drzewo["dziecko"]]   # bez conhost i wnuka
            assert [p for p, _ in nadzorca.dzieci(drzewo["dziecko"])] == [wnuk]
        assert nadzorca._odcisk(s["pid"]) is None and nadzorca._odcisk(drzewo["dziecko"]) is None
        assert nadzorca._odcisk(wnuk) is not None                        # pracownik kanbana kończy kartę
        assert pidy == [drzewo["dziecko"]]                               # znacznik bramy dla właściwego procesu
        assert f"i dzieci {drzewo['dziecko']}" in (u.logi / "nadzorca.log").read_text(encoding="utf-8")
    finally:
        if wnuk:
            nadzorca._zabij_pid(wnuk)


def _sddl_potoku(adres: str) -> str:
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.LocalFree.argtypes = [wintypes.HLOCAL]
    adv.GetSecurityInfo.restype = wintypes.DWORD
    adv.GetSecurityInfo.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.DWORD] + \
        [ctypes.POINTER(wintypes.LPVOID)] * 5
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(wintypes.ULONG)]
    h = k32.CreateFileW(adres, 0x80000000, 0, None, 3, 0, None)        # GENERIC_READ, OPEN_EXISTING
    assert h and h != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        sd = wintypes.LPVOID()
        assert adv.GetSecurityInfo(h, 6, 4, None, None, None, None, ctypes.byref(sd)) == 0   # SE_KERNEL_OBJECT, DACL
        tekst = wintypes.LPWSTR()
        assert adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd, 1, 4, ctypes.byref(tekst), None)
        wynik = tekst.value
        k32.LocalFree(sd)
        return wynik
    finally:
        k32.CloseHandle(h)


@pytest.mark.windows_only
def test_windows_potok_kanalu_tylko_dla_wlasciciela(u, tmp_path):
    n = nowy(u, [Usluga("a", atrapa(tmp_path / "a.jsonl", "spi"))], kanal=True)
    with dziala(n):
        czekaj(lambda: _klient(u), opis="kanał nadzorcy")
        adres, rodzina = nadzorca.adres_kanalu(u)
        assert rodzina == "AF_PIPE" and adres.startswith("\\\\.\\pipe\\jarvo-nadzorca-")
        sddl = _sddl_potoku(adres)
        assert _klient(u) is not None                                    # kanał przeżył obce połączenie
    sid = nadzorca._sid_uzytkownika()
    assert sid and sid in sddl and sddl.startswith("D:P")
    assert ";;;WD)" not in sddl and ";;;AN)" not in sddl and ";;;BU)" not in sddl
