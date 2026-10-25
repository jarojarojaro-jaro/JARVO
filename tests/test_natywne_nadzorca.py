"""Nadzorca procesów Jarva, `jarvo serwis` (docs/NATYWNIE.md: H04, H09, H22, c2, I10, N03), na atrapach usług, bez
Hermesa: restart po kodzie 75 (szybkie wyjścia 75 z rosnącą przerwą i powodem z PID-em programu, który trzyma port),
postój po 78, rosnąca przerwa z sufitem i zerowaniem, kolejność startu z gotowością (plik i serwer HTTP na
127.0.0.1:191xx), gotowość panelu tylko dla własnego HERMES_HOME, jedna instancja na korzeń, kanał sterowania
(status, restart, stop, zły klucz, milczący klient i milczący nadzorca, zamknięcie bez zakleszczenia przy klientach
w trakcie stopu, odpowiedź na stop przed końcem nadzorcy), trwałe zatrzymanie (znacznik, `jarvo serwis` przy znaczniku, --stop, --wznow), logi z rotacją
„kopiuj i przytnij”, zatrzymanie łagodne i twarde z limitem na usługę, sprzątanie po poprzednim nadzorcy, odcisk
procesu niezależny od locale i strefy, `jarvo serwis` jako osobny proces (stop z czekaniem, sygnał), usługi Jarva
(argv, zmienne i limity Hermesa f97608f), pytanie do potoku sterującego bramy, a na Windows launcher z dzieckiem
(zabity launcher i dziecko, wnuk żyje), CREATE_BREAKAWAY_FROM_JOB i DACL potoku kanału."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
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
MACOS = sys.platform == "darwin"
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
if tryb in ("78", "1", "75"):
    sys.exit(int(tryb))
if tryb in ("1-po", "75-po"):
    time.sleep(float(sys.argv[3]))
    sys.exit(int(tryb.split("-")[0]))
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


def nazwa_testu(tekst: str) -> bool:
    """Nazwa procesu tego testu: python (python -m pytest, python.exe, Python z frameworka macOS) albo pytest
    (Linux nazywa proces skryptu z shebangiem nazwą skryptu)."""
    return any(x in tekst.lower() for x in ("python", "pytest"))


def wolny_port() -> int:
    for port in range(19150, 19200):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    pytest.skip("brak wolnego portu 19150–19199")


@contextmanager
def serwer_http(odpowiedz: dict):
    """Serwer HTTP na 127.0.0.1:191xx w tym procesie: GET zwraca 200 i `odpowiedz` jako JSON (jak /api/status)."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            tresc = json.dumps(odpowiedz).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(tresc)))
            self.end_headers()
            self.wfile.write(tresc)

        def log_message(self, *_a):
            pass

    port = wolny_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()


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


def test_kod_75_na_zajetym_porcie_rosnaca_przerwa_i_kto_trzyma_port(u, tmp_path):
    """Hermes kończy dashboard kodem 75, gdy port jest zajęty (np. prywatny Hermes właściciela na 9119): bez
    rosnącej przerwy panel wstawałby co 5 s bez końca. Port trzyma tu ten proces testu."""
    plik = tmp_path / "p.jsonl"
    with serwer_http({"hermes_home": str(tmp_path / "prywatny")}) as port:
        n = nowy(u, [Usluga("panel", atrapa(plik, "75"), port=port)], przerwa_restartu=0.1, przerwa_max=0.4)
        with dziala(n):
            czekaj(lambda: len(starty(plik)) >= 5, limit=30, opis="pięć startów")
            s = czekaj(lambda: (x := usluga(n, "panel")).get("stan") == "ponowienie" and x)
        assert s["ostatni_kod"] == 75 and s["szybkie_75_z_rzedu"] >= 4 and s["port"] == port
        assert f"kod 75: port {port} zajęty przez inny program (" in s["powod"]
        if not (MACOS and not shutil.which("lsof")):
            assert f"(PID {os.getpid()}, " in s["powod"]
            assert nazwa_testu(s["powod"].partition(f"(PID {os.getpid()}, ")[2].partition(")")[0])
        assert "raz z rzędu" in s["powod"]
    assert przerwy_z_dziennika(u, "panel")[:5] == [0.1, 0.2, 0.4, 0.4, 0.4]


def test_kod_75_po_dluzszym_dzialaniu_zawsze_krotka_przerwa(u, tmp_path):
    plik = tmp_path / "a.jsonl"
    n = nowy(u, [Usluga("a", atrapa(plik, "75-po", 0.3))], przerwa_restartu=0.1, przerwa_max=5, szybki_restart=0.2)
    with dziala(n):
        czekaj(lambda: len(starty(plik)) >= 4, limit=20, opis="cztery starty")
        s = czekaj(lambda: (x := usluga(n, "a")).get("stan") == "ponowienie" and x, opis="przerwa po 75")
        assert s["szybkie_75_z_rzedu"] == 0 and "poprosiła o restart" in s["powod"]
    przerwy = przerwy_z_dziennika(u, "a")
    assert len(przerwy) >= 3 and set(przerwy) == {0.1}                           # /restart po pracy: zawsze 5 s


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


def test_panel_gotowy_tylko_dla_wlasnego_hermes_home(tmp_path):
    """Cudzy dashboard na porcie panelu (200 z innym hermes_home) to nie gotowość panelu Jarva."""
    dane = tmp_path / "dane"
    dane.mkdir()
    odpowiedz = {"version": "0.21.5", "hermes_home": str(dane), "auth_required": False}
    with serwer_http(odpowiedz) as port:
        adres = f"http://127.0.0.1:{port}/api/status"
        assert nadzorca.panel_gotowy(adres, dane) is True
        odpowiedz["hermes_home"] = str(dane).upper() if WINDOWS else str(dane / ".." / "dane")
        assert nadzorca.panel_gotowy(adres, dane) is True             # ta sama ścieżka zapisana inaczej
        odpowiedz["hermes_home"] = str(tmp_path / "prywatny-hermes")
        assert nadzorca.panel_gotowy(adres, dane) is False            # prywatny Hermes właściciela na tym porcie
        del odpowiedz["hermes_home"]
        assert nadzorca.panel_gotowy(adres, dane) is False            # bez ścieżki i bez bramki: nie wiadomo, czyj
        odpowiedz["auth_required"] = True
        assert nadzorca.panel_gotowy(adres, dane) is True             # bramka logowania ukrywa ścieżki (tryb LAN)
    assert nadzorca.panel_gotowy(adres, dane, limit=0.5) is False


def test_wlasciciel_portu_pid_i_nazwa():
    port = wolny_port()
    assert nadzorca.wlasciciel_portu(port) is None                    # nikt nie słucha
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
        s.listen(8)
        kto = nadzorca.wlasciciel_portu(port)
    assert kto is not None
    if MACOS and not shutil.which("lsof"):
        pytest.skip("macOS bez lsof: system nie podaje właściciela portu")
    pid, nazwa = kto
    assert pid == os.getpid() and nazwa and nazwa_testu(nazwa)


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
        z_pliku = nadzorca.stan_z_pliku(u)
        assert z_pliku["dziala"] is True and z_pliku["zatrzymanie"] is None
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
        odp = k.stop(powod="próba kanału")
        assert odp["ok"] is True and odp["trwale"] is True
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
    assert nadzorca.zatrzymany(u)                                        # stop z kanału = trwałe zatrzymanie
    assert nadzorca.stan_z_pliku(u)["zatrzymanie"]["powod"] == "próba kanału"


def test_kanal_zamyka_sie_gdy_watek_kanalu_trzyma_innego_klienta(u, monkeypatch):
    """Wyścig z recenzji: accept() wrócił z połączeniem prawdziwego klienta i właśnie wtedy przychodzi stop. Budzik
    z kluczem czekałby wtedy bez końca na wymianę HMAC, której nikt już nie zacznie (nadzorca z blokadą wisi)."""
    n = nowy(u, [], kanal=True)
    przyjal = threading.Event()
    oryginal = nadzorca._Sluchacz.accept

    def accept(self):
        c = oryginal(self)
        if not przyjal.is_set():
            przyjal.set()
            n._kanal._koniec.wait(15)            # wątek kanału „wywłaszczony” tuż po accept()
        return c

    monkeypatch.setattr(nadzorca._Sluchacz, "accept", accept)

    def klient():
        while not przyjal.is_set():
            try:
                nadzorca.Klient(u, limit=3).status()
            except nadzorca.BladNadzorcy:
                time.sleep(0.02)

    t = threading.Thread(target=n.uruchom, daemon=True)
    t.start()
    k = threading.Thread(target=klient, daemon=True)
    k.start()
    assert przyjal.wait(20), "kanał nie przyjął klienta"
    t0 = time.monotonic()
    n.zatrzymaj()
    t.join(20)
    assert not t.is_alive(), "zamknięcie kanału wisi"
    assert time.monotonic() - t0 < 10
    k.join(10)
    assert not k.is_alive(), "klient wisi po zamknięciu kanału"


def test_kanal_stop_nie_wisi_przy_klientach_pytajacych_w_trakcie(tmp_path):
    """Jak pętla `jarvo down` albo instalatora, tylko gęściej: dwóch klientów pyta o status w trakcie zatrzymania.
    Przed poprawką wisiało ok. 40% zatrzymań; teraz każde kończy się w kilka sekund, a żadne pytanie nie trwa
    dłużej niż limit klienta."""
    for i in range(6):
        u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / f"j{i}")})
        n = nadzorca.Nadzorca(u, [], {}, kanal=True, takt=0.01)
        t = threading.Thread(target=n.uruchom, daemon=True)
        t.start()
        czekaj(lambda: _klient(u), opis=f"kanał w przebiegu {i}")
        koniec, najdluzej = threading.Event(), [0.0]

        def pytaj():
            while not koniec.is_set():
                t0 = time.monotonic()
                try:
                    nadzorca.Klient(u, limit=2).status()
                except nadzorca.BladNadzorcy:
                    time.sleep(0.002)
                najdluzej[0] = max(najdluzej[0], time.monotonic() - t0)

        pytajacy = [threading.Thread(target=pytaj, daemon=True) for _ in range(2)]
        for w in pytajacy:
            w.start()
        time.sleep(0.2)
        t0 = time.monotonic()
        n.zatrzymaj()
        t.join(20)
        czas = time.monotonic() - t0
        koniec.set()
        for w in pytajacy:
            w.join(10)
        assert not t.is_alive(), f"przebieg {i}: zatrzymanie wisi"
        assert czas < 10, f"przebieg {i}: zatrzymanie trwało {czas:.1f} s"
        assert not any(w.is_alive() for w in pytajacy) and najdluzej[0] < 6, najdluzej[0]


def test_kanal_przy_zamykaniu_czeka_na_odpowiedz_na_stop(u, monkeypatch):
    """Bez usług pętla kończy się zaraz po „stop”, a w procesie `jarvo serwis` wątki w tle giną razem z nim:
    zamknięcie kanału czeka na trwające odpowiedzi (najdłużej 1 s), więc `jarvo down` dostaje odpowiedź."""
    oryginal = nadzorca.Nadzorca._obsluz
    obsluzone: list[float] = []

    def obsluz(self, zadanie):
        odp = oryginal(self, zadanie)
        if zadanie.get("polecenie") == "stop":
            time.sleep(0.5)                               # odpowiedź jeszcze w drodze, gdy pętla już skończyła
            obsluzone.append(time.monotonic())
        return odp

    monkeypatch.setattr(nadzorca.Nadzorca, "_obsluz", obsluz)
    n = nowy(u, [], kanal=True)
    koniec: list[float] = []
    t = threading.Thread(target=lambda: (n.uruchom(), koniec.append(time.monotonic())), daemon=True)
    t.start()
    k = czekaj(lambda: _klient(u), opis="kanał nadzorcy")
    assert k.stop(powod="test")["trwale"] is True
    t.join(20)
    assert not t.is_alive() and obsluzone and koniec and koniec[0] >= obsluzone[0]


def test_klient_nie_wisi_gdy_kanal_milczy(u):
    """Gniazdo albo potok istnieje, ale nikt nie zaczyna wymiany klucza (nadzorca zawieszony): limit klienta obejmuje
    połączenie i wymianę klucza, nie tylko czekanie na odpowiedź."""
    adres, rodzina = nadzorca.adres_kanalu(u)
    u.stan.mkdir(parents=True)
    (u.stan / "nadzorca.klucz").write_bytes(b"k" * 32)
    if rodzina == "AF_PIPE":
        sluchacz = connection.Listener(adres, "AF_PIPE")               # instancja potoku czeka, nikt jej nie obsłuży
        zamknij = sluchacz.close
    else:
        Path(adres).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        gniazdo = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        gniazdo.bind(adres)
        gniazdo.listen(8)                                               # słucha, ale nikt nie przyjmuje połączeń

        def zamknij():
            gniazdo.close()
            os.unlink(adres)
            if Path(adres).parent != u.stan:
                Path(adres).parent.rmdir()
    try:
        t0 = time.monotonic()
        with pytest.raises(nadzorca.NadzorcaNieDziala, match="nie odpowiedział w 1 s"):
            nadzorca.Klient(u, limit=1.0).status()
        assert time.monotonic() - t0 < 5
    finally:
        zamknij()


def test_znacznik_zatrzymania_api(u):
    assert not nadzorca.zatrzymany(u) and nadzorca.zdejmij_zatrzymanie(u) is False
    nadzorca.oznacz_zatrzymanie(u, "jarvo down, token 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")
    assert nadzorca.zatrzymany(u)
    z = json.loads((u.stan / "zatrzymany.json").read_text(encoding="utf-8"))
    assert z["powod"].startswith("jarvo down") and "AAHdq" not in z["powod"] and z["kiedy"] and z["pid"] == os.getpid()
    assert nadzorca.stan_z_pliku(u) == {}                              # nadzorca nigdy nie działał
    assert nadzorca.zdejmij_zatrzymanie(u) is True and not nadzorca.zatrzymany(u)


def test_main_przy_znaczniku_konczy_od_razu_kodem_0(tmp_path, monkeypatch, capsys):
    """Zapasowy wyzwalacz Harmonogramu (odblokowanie, co 5 minut) po `jarvo down`: `jarvo serwis` nic nie startuje."""
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path / "j"))
    u = sciezki.uklad()
    nadzorca.oznacz_zatrzymanie(u, "jarvo down")
    assert nadzorca.main([]) == 0                        # bez Hermesa: znacznik sprawdzany przed wszystkim innym
    out = capsys.readouterr().out
    assert "zatrzymany (jarvo down, " in out and "jarvo up" in out and "--wznow" in out
    assert nadzorca.main(["--status"]) == 1
    assert "jarvo up" in capsys.readouterr().err
    assert nadzorca.main(["--wznow"]) == 1               # znacznik zdjęty, start trafia na brak Hermesa
    assert "current.json" in capsys.readouterr().err and not nadzorca.zatrzymany(u)
    assert nadzorca.main(["--stop"]) == 0                # nadzorca nie działa: znacznik i tak zostaje zapisany
    assert "nie działał" in capsys.readouterr().out and nadzorca.zatrzymany(u)


def test_nadzorca_szanuje_znacznik_przy_starcie_i_w_trakcie(u, tmp_path):
    plik = tmp_path / "a.jsonl"
    nadzorca.oznacz_zatrzymanie(u, "jarvo down")
    n = nowy(u, [Usluga("a", atrapa(plik, "spi"))], szanuj_zatrzymanie=True)
    with pytest.raises(nadzorca.NadzorcaZatrzymany, match="jarvo up"):
        n.uruchom()
    assert not starty(plik) and not (u.stan / "nadzorca.json").exists()      # stan poprzedniego zostaje
    nadzorca.zdejmij_zatrzymanie(u)
    n = nowy(u, [Usluga("a", atrapa(plik, "spi"))], szanuj_zatrzymanie=True, co_ile_znacznik=0.05)
    t = threading.Thread(target=n.uruchom, daemon=True)
    t.start()
    try:
        czekaj(lambda: usluga(n, "a").get("stan") == "dziala", opis="start bez znacznika")
        nadzorca.oznacz_zatrzymanie(u, "jarvo down bez kanału")        # np. kanał nie odpowiadał
        t.join(30)
        assert not t.is_alive(), "nadzorca nie zauważył znacznika"
    finally:
        n.zatrzymaj()
        t.join(30)
    assert nadzorca.stan_z_pliku(u)["uslugi"]["a"]["stan"] == "zatrzymana"
    assert "pojawił się znacznik zatrzymania" in (u.logi / "nadzorca.log").read_text(encoding="utf-8")


def test_main_bez_nadzorcy(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path / "j"))
    assert nadzorca.main(["--status"]) == 1
    assert "nie działa" in capsys.readouterr().err
    assert nadzorca.main([]) == 1                                       # brak instalacji Hermesa
    assert "current.json" in capsys.readouterr().err


NAPED = r'''
import sys
sys.path.insert(0, sys.argv[1])
from jarvo import nadzorca
py, kod, plik = sys.argv[2], sys.argv[3], sys.argv[4]
nadzorca.uslugi_jarva = lambda u, env: [nadzorca.Usluga("a", [py, "-c", kod, plik, "spi"])]
sys.exit(nadzorca.main(sys.argv[5:]))
'''


def serwis(root: Path, wyjscie: Path, plik: Path, *argumenty: str) -> subprocess.Popen:
    """`jarvo serwis` jako osobny proces (jak z autostartu), z atrapą usługi zamiast bramy i panelu."""
    flagi = {"creationflags": 0x08000000 | 0x00000200} if WINDOWS else {"start_new_session": True}
    with open(wyjscie, "ab") as out:
        return subprocess.Popen([PY, "-c", NAPED, str(REPO), PY, ATRAPA, str(plik), *argumenty],
                                env={**os.environ, "JARVO_ROOT": str(root), "PYTHONUTF8": "1"},
                                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, **flagi)


def test_serwis_jako_proces_stop_z_czekaniem_znacznik_i_sygnal(tmp_path):
    root, wyjscie, plik = tmp_path / "j", tmp_path / "serwis.out", tmp_path / "a.jsonl"
    u = sciezki.uklad({"JARVO_ROOT": str(root)})
    p = serwis(root, wyjscie, plik)
    try:
        czekaj(lambda: _klient(u) and starty(plik), limit=60, opis="serwis w osobnym procesie")
        assert nadzorca.stan_z_pliku(u)["dziala"] is True             # odcisk procesu liczony w innym procesie
        pierwsza = starty(plik)[0]["pid"]
        odp = nadzorca.polacz(u).stop(czekaj=60, powod="jarvo down")
        assert odp["trwale"] is True and p.wait(15) == 0               # stop(czekaj) wraca po końcu procesu
        assert nadzorca._odcisk(pierwsza) is None and nadzorca.zatrzymany(u)
        assert nadzorca.stan_z_pliku(u)["dziala"] is False
        p = serwis(root, wyjscie, plik)                                # zapasowy wyzwalacz autostartu
        assert p.wait(60) == 0 and len(starty(plik)) == 1
        assert "Serwis Jarva jest zatrzymany (jarvo down" in wyjscie.read_text(encoding="utf-8", errors="replace")
        p = serwis(root, wyjscie, plik, "--wznow")                     # jawny start zdejmuje znacznik
        czekaj(lambda: _klient(u) and len(starty(plik)) == 2, limit=60, opis="serwis po --wznow")
        assert not nadzorca.zatrzymany(u)
        if WINDOWS:
            assert nadzorca._lagodnie(p.pid)                           # Ctrl+Break do konsoli serwisu
        else:
            p.send_signal(signal.SIGTERM)
        assert p.wait(60) == 0
        assert nadzorca._odcisk(starty(plik)[1]["pid"]) is None
        assert not nadzorca.zatrzymany(u)                              # sygnał nie zapisuje znacznika
    finally:
        if p.poll() is None:
            p.kill()


def test_odcisk_nie_zalezy_od_locale_ani_strefy():
    """Ten sam proces ma ten sam odcisk z launchd (bez LANG) i z terminala z pl_PL albo inną strefą."""
    kod = ("import sys; sys.path.insert(0, sys.argv[1]); from jarvo import nadzorca; "
           "print(nadzorca._odcisk(int(sys.argv[2])))")
    wyniki = set()
    for zmienne in ({"LANG": "pl_PL.UTF-8", "LC_ALL": "pl_PL.UTF-8", "TZ": "Asia/Tokyo"},
                    {"LANG": "C", "LC_ALL": "C", "TZ": "UTC"}, {"LANG": "de_DE.UTF-8", "TZ": "America/New_York"}):
        wynik = subprocess.run([PY, "-c", kod, str(REPO), str(os.getpid())], env={**os.environ, **zmienne},
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        assert wynik.returncode == 0, wynik.stderr
        wyniki.add(wynik.stdout.strip())
    assert wyniki == {nadzorca._odcisk(os.getpid())}


def test_odcisk_procesu_zakonczonego_i_zombie():
    p = subprocess.Popen([PY, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
    try:
        czekaj(lambda: nadzorca._odcisk(p.pid), opis="odcisk żywego procesu")
        p.stdin.close()
        czekaj(lambda: nadzorca._odcisk(p.pid) is None, opis="koniec procesu")
        assert p.returncode is None                                    # jeszcze niezebrany (POSIX: zombie)
    finally:
        p.wait(10)


@pytest.mark.skipif(not MACOS, reason="tylko macOS")
def test_macos_odcisk_z_libproc_i_zapasowo_z_ps(monkeypatch):
    assert str(nadzorca._odcisk_bsd(os.getpid())).startswith("bsd:")  # libproc działa i ma ten układ struktury
    pierwszy = nadzorca._odcisk_ps(os.getpid())
    assert pierwszy and pierwszy.startswith("ps:")
    for nazwa, wartosc in (("LANG", "pl_PL.UTF-8"), ("LC_ALL", "pl_PL.UTF-8"), ("TZ", "Asia/Tokyo")):
        monkeypatch.setenv(nazwa, wartosc)
    assert nadzorca._odcisk_ps(os.getpid()) == pierwszy
    assert nadzorca._nazwa_procesu(os.getpid())


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


def test_start_mimo_nieudanej_rotacji_dziennika_nadzorcy(u, tmp_path, monkeypatch):
    """Windows: kopię dziennika trzyma podgląd bez FILE_SHARE_DELETE; rotacja przy starcie nie może zatrzymać floty."""
    oryginal = nadzorca._Dziennik.rotuj

    def rotuj(self, wymus=False):
        if self.sciezka.name == "nadzorca.log":
            raise PermissionError(32, "plik używany przez inny proces")
        return oryginal(self, wymus)

    monkeypatch.setattr(nadzorca._Dziennik, "rotuj", rotuj)
    plik = tmp_path / "a.jsonl"
    with dziala(nowy(u, [Usluga("a", atrapa(plik, "spi"))])):
        czekaj(lambda: starty(plik), opis="start mimo rotacji")


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
    assert not nadzorca.zatrzymany(u)                                  # zatrzymaj() bez znacznika


def test_limit_zatrzymania_osobno_dla_uslugi(u, tmp_path):
    """Brama dostaje 70 s (budżet Hermesa), panel 30 s: limit usługi wygrywa z limitem nadzorcy."""
    pa, pb = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    n = nowy(u, [Usluga("a", atrapa(pa, "uparta"), limit_stopu=0.3), Usluga("b", atrapa(pb, "uparta"))],
             limit_stopu=1.5)
    with dziala(n):
        czekaj(lambda: starty(pa) and starty(pb), opis="obie usługi")
        assert (usluga(n, "a")["limit_stopu"], usluga(n, "b")["limit_stopu"]) == (0.3, 1.5)
        t0 = time.monotonic()
    czas = time.monotonic() - t0
    log = (u.logi / "nadzorca.log").read_text(encoding="utf-8")
    assert "a: nie skończył się w 0.3 s, zabity" in log and "b: nie skończył się w 1.5 s, zabity" in log
    assert 1.5 <= czas < 15


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


def test_uslugi_jarva_argv_srodowisko_i_limity_hermesa(tmp_path):
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
    # gotowość panelu: /api/status z hermes_home tej instalacji; limity jak TimeoutStopSec Hermesa (70 s) i 30 s
    assert panel.gotowa.func is nadzorca.panel_gotowy
    assert panel.gotowa.args == ("http://127.0.0.1:19123/api/status", u.dane)
    assert (brama.limit_stopu, panel.limit_stopu) == (nadzorca.LIMIT_STOPU_BRAMY, nadzorca.LIMIT_STOPU_PANELU)
    assert nadzorca.LIMIT_STOPU_BRAMY == 70 and nadzorca.LIMIT_STOPU_PANELU == 30
    assert nadzorca.CZAS_ZATRZYMANIA >= nadzorca.LIMIT_STOPU_BRAMY + 10
    assert (brama.port, panel.port) == (None, 19123)
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


@pytest.mark.windows_only
def test_windows_breakaway_wylaczany_dopiero_po_udanym_starcie_bez_flagi(u, monkeypatch):
    n = nowy(u, [Usluga("a", [PY, "-c", "pass"])])
    s = n._stany["a"]
    flagi: list[int] = []
    zachowanie = {"bez_flagi": "blad"}

    def popen(argv, creationflags=0, **_kw):
        flagi.append(creationflags)
        if creationflags & 0x01000000 or zachowanie["bez_flagi"] == "blad":
            raise PermissionError(5, "Odmowa dostępu")
        return "proces"

    monkeypatch.setattr(nadzorca.subprocess, "Popen", popen)
    with pytest.raises(PermissionError):                 # brak dostępu do programu, nie job: flaga zostaje
        n._popen(s, {}, None)
    assert n._breakaway is True and len(flagi) == 2
    zachowanie["bez_flagi"] = "ok"
    assert n._popen(s, {}, None) == "proces" and n._breakaway is False   # job zabrania BREAKAWAY
    flagi.clear()
    assert n._popen(s, {}, None) == "proces" and flagi == [0x08000000 | 0x00000200]


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
