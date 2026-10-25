"""Filtr ruchu przeglądarki Jarva natywnie (komputer/filtr.py, docs/NATYWNIE.md J06): decyzje o adresach, proxy
na prawdziwych gniazdach (CONNECT i zwykłe żądania), własne rozwiązywanie nazw i samotest. Wszystko na 127.0.0.1,
porty z zakresu próby (19202–19209) albo wolne od systemu, gdy zajęte."""
from __future__ import annotations

import socket
import sys
import threading

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from komputer import filtr  # noqa: E402


def wolny_port() -> int:
    """Wolny port z zakresu prób Komputera (19202–19209), a gdy wszystkie zajęte: 0 (wolny od systemu)."""
    for port in range(19202, 19210):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            s.close()
    return 0


@pytest.mark.parametrize("ip, port", [
    ("169.254.169.254", 80), ("127.0.0.1", 9119), ("127.0.0.1", 8642), ("127.1.2.3", 443), ("::1", 9119),
    ("10.0.0.1", 80), ("172.16.5.4", 443), ("192.168.1.1", 80), ("100.64.0.1", 443), ("100.100.100.100", 443),
    ("0.0.0.0", 80), ("224.0.0.251", 5353), ("255.255.255.255", 80), ("fe80::1", 80), ("fd00::1", 443),
    ("::ffff:127.0.0.1", 9119), ("::ffff:169.254.169.254", 80), ("64:ff9b::a9fe:a9fe", 80), ("2002:c0a8:101::", 80),
    ("ff02::1", 80), ("192.0.2.10", 443), ("198.18.0.1", 443), ("::", 80), ("2001:db8::1", 443),
])
def test_adresy_zakazane(ip, port):
    assert filtr.Filtr().powod(ip, port), (ip, port)


@pytest.mark.parametrize("ip, port", [("8.8.8.8", 443), ("1.1.1.1", 443), ("142.250.74.110", 80),
                                      ("2606:4700:4700::1111", 443), ("2a00:1450:4001:82a::200e", 443)])
def test_adresy_internetu_przechodza(ip, port):
    assert filtr.Filtr().powod(ip, port) is None


def test_port_25_i_adresy_tego_komputera():
    f = filtr.Filtr(wlasne={"203.0.114.7"})
    assert "poczta" in f.powod("8.8.8.8", 25)
    assert f.powod("203.0.114.7", 443) == "adres tego komputera"
    assert filtr.Filtr(wyjatki=frozenset({("127.0.0.1", 1234)})).powod("127.0.0.1", 1234) is None


def test_adres_z_portem():
    assert filtr._host_port("example.com:443", 80) == ("example.com", 443)
    assert filtr._host_port("[::1]:9119", 443) == ("::1", 9119)
    assert filtr._host_port("example.com.", 80) == ("example.com", 80)
    assert filtr._host_port("::1", 443) == ("::1", 443)
    with pytest.raises(ValueError):
        filtr._host_port("example.com:99999", 80)


class _Serwer:
    """Serwer TCP na 127.0.0.1: zapamiętuje, co dostał, odsyła echo albo odpowiedź HTTP."""

    def __init__(self, http: bool = False):
        self.s = socket.socket()
        self.s.bind(("127.0.0.1", wolny_port()))
        self.s.listen(8)
        self.port = self.s.getsockname()[1]
        self.dane: list[bytes] = []
        self.http = http
        threading.Thread(target=self._petla, daemon=True).start()

    def _petla(self):
        while True:
            try:
                k, _ = self.s.accept()
            except OSError:
                return
            k.settimeout(5)
            try:
                d = k.recv(65536)
                self.dane.append(d)
                k.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok" if self.http else d)
            except OSError:
                pass
            finally:
                k.close()

    def zamknij(self):
        self.s.close()


@pytest.fixture
def proxy():
    serwer = _Serwer()
    serwer_http = _Serwer(http=True)
    nazwy = {"metadane.test": ["169.254.169.254"], "lokalny.test": ["127.0.0.1"],
             "mieszany.test": ["192.168.1.10", "127.0.0.1"], "dozwolony.test": ["127.0.0.1"]}
    p = filtr.Proxy(filtr.Filtr(wyjatki=frozenset({("127.0.0.1", serwer.port), ("127.0.0.1", serwer_http.port)})),
                    port=wolny_port(), rozwiaz=lambda h, port: nazwy.get(h, [h]))
    p.start()
    yield p, serwer, serwer_http
    p.zatrzymaj()
    serwer.zamknij()
    serwer_http.zamknij()


def _zapytanie(port: int, dane: bytes) -> bytes:
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    try:
        s.sendall(dane)
        wynik = b""
        while True:
            k = s.recv(65536)
            if not k:
                break
            wynik += k
            if b"\r\n\r\n" in wynik and not wynik.startswith(b"HTTP/1.1 200 Connection"):
                break
        return wynik
    finally:
        s.close()


def test_connect_do_zakazanych_dostaje_403_bez_polaczenia(proxy):
    p, serwer, _ = proxy
    for cel in ("169.254.169.254:80", "metadane.test:80", "127.0.0.1:9119", "localhost:9119", "lokalny.test:9119",
                "[::1]:9119", "192.168.1.1:80", "8.8.8.8:25"):
        odp = _zapytanie(p.port, f"CONNECT {cel} HTTP/1.1\r\nHost: {cel}\r\n\r\n".encode())
        assert odp.startswith(b"HTTP/1.1 403"), (cel, odp[:80])
    assert p.statystyki.zablokowane == 8 and serwer.dane == []


def test_connect_dozwolony_przepompowuje_bajty(proxy):
    p, serwer, _ = proxy
    s = socket.create_connection(("127.0.0.1", p.port), timeout=10)
    try:
        s.sendall(f"CONNECT dozwolony.test:{serwer.port} HTTP/1.1\r\n\r\n".encode())
        odp = s.recv(4096)
        assert odp.startswith(b"HTTP/1.1 200")
        s.sendall(b"tunel dziala")
        assert s.recv(4096) == b"tunel dziala"
    finally:
        s.close()


def test_zwykle_zadanie_http_przepisane_bez_naglowkow_proxy(proxy):
    p, _, serwer_http = proxy
    odp = _zapytanie(p.port, (f"GET http://127.0.0.1:{serwer_http.port}/sciezka?a=1 HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                              "Proxy-Connection: keep-alive\r\nProxy-Authorization: Basic eDp5\r\n\r\n").encode())
    assert odp.startswith(b"HTTP/1.1 200")
    zadanie = serwer_http.dane[0].decode("latin-1")
    assert zadanie.startswith("GET /sciezka?a=1 HTTP/1.1")
    assert "Proxy-" not in zadanie and "Connection: close" in zadanie
    odp = _zapytanie(p.port, b"GET http://192.168.1.1/ HTTP/1.1\r\nHost: 192.168.1.1\r\n\r\n")
    assert odp.startswith(b"HTTP/1.1 403") and "sieć lokalna".encode() in odp


def test_https_bez_connect_i_zle_zadanie(proxy):
    p, _, _ = proxy
    assert _zapytanie(p.port, b"GET https://example.com/ HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 400")
    assert _zapytanie(p.port, b"COKOLWIEK\r\n\r\n").startswith(b"HTTP/1.1 400")


def test_nazwa_z_adresem_lokalnym_i_publicznym_laczy_tylko_z_dozwolonym(proxy):
    """Własne rozwiązywanie nazw: proxy łączy się dokładnie z adresem, który sprawdziło (bez drugiego DNS)."""
    p, _, _ = proxy
    odp = _zapytanie(p.port, b"CONNECT mieszany.test:443 HTTP/1.1\r\n\r\n")
    assert odp.startswith(b"HTTP/1.1 403")


def test_samotest_na_prawdziwym_proxy():
    p = filtr.Proxy(port=wolny_port())
    port = p.start()
    try:
        wynik = filtr.samotest(port, 19200)
    finally:
        p.zatrzymaj()
    assert wynik["ok"] and all(c["kod"] == 403 for c in wynik["cele"])
    cele = {c["cel"] for c in wynik["cele"]}
    assert {"169.254.169.254:80", "127.0.0.1:19200", "127.0.0.1:8642", "192.168.1.1:80", "1.1.1.1:25"} <= cele


def test_samotest_wykrywa_dziurawy_filtr(monkeypatch):
    """Cel, który nie dostał 403 (proxy go przepuściło albo milczy), oblewa samotest: usługa Komputera nie wstaje.
    Bez prawdziwych połączeń z siecią lokalną: odpowiedzi proxy podstawione."""
    monkeypatch.setattr(filtr, "zapytaj_przez_proxy",
                        lambda port, host, p, czas=10.0: 200 if host == "169.254.169.254" else 403)
    wynik = filtr.samotest(1, 19200)
    assert not wynik["ok"] and [c["cel"] for c in wynik["cele"] if c["kod"] != 403] == ["169.254.169.254:80"]
    monkeypatch.setattr(filtr, "zapytaj_przez_proxy", lambda port, host, p, czas=10.0: None)
    assert not filtr.samotest(1, 19200)["ok"]
