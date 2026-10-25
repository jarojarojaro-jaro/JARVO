"""Filtr ruchu przeglądarki Jarva (docs/NATYWNIE.md J06): lokalne proxy HTTP w aplikacji, asyncio i biblioteka
standardowa.

Natywnie nie ma iptables kontenera, więc cały ruch przeglądarki Jarva idzie przez to proxy (`--proxy-server`,
`--proxy-bypass-list=<-loopback>`: także 127.0.0.1 i localhost; bez QUIC; WebRTC tylko przez proxy). Proxy samo
rozwiązuje nazwę (DNS) i łączy się dokładnie z adresem, który sprawdziło (bez drugiego zapytania, więc podmiana
odpowiedzi DNS po sprawdzeniu nic nie da). Odrzuca:
  - sieć lokalną (RFC 1918, fc00::/7), CGNAT i Tailscale (100.64.0.0/10),
  - link-local z metadanymi chmury (169.254.169.254, fe80::/10),
  - pętlę zwrotną (panel Jarva 127.0.0.1:9119, API bramy :8642, podgląd :9120 i każdy inny serwer na tym komputerze),
  - zakresy specjalne i multicast, adresy samego komputera,
  - port 25 (poczta).
IPv4 w IPv6 (::ffff:a.b.c.d, NAT64 64:ff9b::/96, 6to4 2002::/16) sprawdzamy jak IPv4. Samotest (`samotest`) przed
startem przeglądarki łączy się przez proxy z adresami zakazanymi: każdy ma dostać 403 bez próby połączenia.
To filtr w aplikacji, nie w jądrze: obejmuje cały ruch tej przeglądarki, ale nie inne programy właściciela.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlsplit

PORTY_ZAKAZANE = frozenset({25})
MAKS_NAGLOWEK = 64 << 10
CZAS_NAGLOWKA = 30.0
CZAS_POLACZENIA = 15.0
CZAS_BEZCZYNNOSCI = 300.0
# zakresy zawsze zakazane (z powodem po polsku); kolejność: pierwszy pasujący daje powód
ZAKRESY = [
    ("127.0.0.0/8", "pętla zwrotna: ten komputer (panel i API Jarva)"),
    ("::1/128", "pętla zwrotna: ten komputer (panel i API Jarva)"),
    ("169.254.0.0/16", "link-local: metadane chmury (169.254.169.254) i sieć lokalna"),
    ("fe80::/10", "link-local IPv6"),
    ("10.0.0.0/8", "sieć lokalna"),
    ("172.16.0.0/12", "sieć lokalna"),
    ("192.168.0.0/16", "sieć lokalna"),
    ("fc00::/7", "sieć lokalna IPv6"),
    ("100.64.0.0/10", "CGNAT i Tailscale"),
    ("0.0.0.0/8", "adres specjalny"),
    ("192.0.0.0/24", "adres specjalny"),
    ("192.0.2.0/24", "adres dokumentacyjny"),
    ("198.18.0.0/15", "adres testowy"),
    ("198.51.100.0/24", "adres dokumentacyjny"),
    ("203.0.113.0/24", "adres dokumentacyjny"),
    ("224.0.0.0/4", "multicast"),
    ("240.0.0.0/4", "adres zarezerwowany"),
    ("::/128", "adres nieokreślony"),
    ("ff00::/8", "multicast IPv6"),
    ("2001:db8::/32", "adres dokumentacyjny IPv6"),
    ("100::/64", "adres do odrzucania"),
]
_SIECI = [(ipaddress.ip_network(z), p) for z, p in ZAKRESY]
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def adresy_tego_komputera() -> set[str]:
    """Adresy interfejsów tego komputera (z nazwy hosta i trasy domyślnej): ich też przeglądarka nie dostaje,
    także gdy są publiczne (serwer z publicznym adresem)."""
    wynik: set[str] = set()
    try:
        for rodzina, _, _, _, adres in socket.getaddrinfo(socket.gethostname(), None):
            wynik.add(str(adres[0]).split("%", 1)[0])
    except OSError:
        pass
    for rodzina, cel in ((socket.AF_INET, ("192.0.2.1", 9)), (socket.AF_INET6, ("2001:db8::1", 9))):
        s = socket.socket(rodzina, socket.SOCK_DGRAM)
        try:
            s.connect(cel)                   # UDP bez wysyłania: system wybiera adres źródłowy trasy domyślnej
            wynik.add(str(s.getsockname()[0]).split("%", 1)[0])
        except OSError:
            pass
        finally:
            s.close()
    return wynik


@dataclass
class Filtr:
    """Decyzja o adresie docelowym. `wyjatki` (host, port) tylko dla testów na pętli zwrotnej."""
    porty_zakazane: frozenset = PORTY_ZAKAZANE
    wlasne: set = field(default_factory=set)
    wyjatki: frozenset = frozenset()

    def powod(self, ip: str, port: int) -> str | None:
        """None, gdy wolno; inaczej powód odmowy po polsku."""
        if (ip, port) in self.wyjatki:
            return None
        if port in self.porty_zakazane:
            return f"port {port} (poczta)" if port == 25 else f"port {port}"
        try:
            a = ipaddress.ip_address(ip.split("%", 1)[0])
        except ValueError:
            return "zły adres"
        if a.version == 6:
            wewnatrz = a.ipv4_mapped or a.sixtofour or (ipaddress.IPv4Address(int(a) & 0xFFFFFFFF)
                                                         if a in _NAT64 else None)
            if wewnatrz is not None:
                return self.powod(str(wewnatrz), port)
            if a.teredo:
                return "tunel Teredo"
        for siec, p in _SIECI:
            if a.version == siec.version and a in siec:
                return p
        if str(a) in self.wlasne:
            return "adres tego komputera"
        if not a.is_global or a.is_multicast or a.is_reserved:
            return "adres spoza internetu"
        return None


@dataclass
class Statystyki:
    przepuszczone: int = 0
    zablokowane: int = 0
    ostatnie: deque = field(default_factory=lambda: deque(maxlen=50))     # (czas, host:port, powód) bez ścieżek
    lock: threading.Lock = field(default_factory=threading.Lock)

    def blokada(self, cel: str, powod: str) -> None:
        with self.lock:
            self.zablokowane += 1
            self.ostatnie.append((time.time(), cel, powod))

    def slownik(self) -> dict:
        with self.lock:
            return {"przepuszczone": self.przepuszczone, "zablokowane": self.zablokowane,
                    "ostatnie": [{"t": round(t), "cel": c, "powod": p} for t, c, p in list(self.ostatnie)[-10:]]}


def _host_port(tekst: str, domyslny: int) -> tuple[str, int]:
    tekst = tekst.strip()
    if tekst.startswith("["):
        host, _, reszta = tekst[1:].partition("]")
        port = reszta[1:] if reszta.startswith(":") else ""
    else:
        host, _, port = tekst.rpartition(":") if tekst.count(":") == 1 else (tekst, "", "")
    if not port:
        return host.rstrip("."), domyslny
    if not port.isdigit() or not 0 < int(port) < 65536:
        raise ValueError("zły port")
    return host.rstrip("."), int(port)


class Proxy:
    """Proxy HTTP (CONNECT i zwykłe żądania z pełnym adresem) w osobnym wątku z pętlą asyncio."""

    def __init__(self, filtr: Filtr | None = None, *, host: str = "127.0.0.1", port: int = 0,
                 log: Callable[[str], None] | None = None,
                 rozwiaz: Callable[[str, int], list[str]] | None = None):
        self.filtr = filtr or Filtr(wlasne=adresy_tego_komputera())
        self.host, self.port = host, port
        self.log = log or (lambda _t: None)
        self.statystyki = Statystyki()
        self._rozwiaz = rozwiaz
        self._petla: asyncio.AbstractEventLoop | None = None
        self._serwer = None
        self._watek: threading.Thread | None = None
        self._gotowe = threading.Event()
        self._blad: BaseException | None = None

    # --- cykl życia

    def start(self) -> int:
        self._watek = threading.Thread(target=self._uruchom, daemon=True, name="komputer-proxy")
        self._watek.start()
        if not self._gotowe.wait(10):
            raise RuntimeError("proxy Komputera nie wstało w 10 s")
        if self._blad is not None:
            raise RuntimeError(f"proxy Komputera: {self._blad}")
        return self.port

    def _uruchom(self) -> None:
        petla = asyncio.new_event_loop()
        self._petla = petla
        asyncio.set_event_loop(petla)
        try:
            self._serwer = petla.run_until_complete(asyncio.start_server(self._klient, self.host, self.port,
                                                                         limit=MAKS_NAGLOWEK))
            self.port = self._serwer.sockets[0].getsockname()[1]
        except BaseException as e:  # noqa: BLE001
            self._blad = e
            self._gotowe.set()
            return
        self._gotowe.set()
        try:
            petla.run_forever()
        finally:
            petla.close()

    def zatrzymaj(self) -> None:
        petla = self._petla
        if petla is None or petla.is_closed():
            return

        async def koniec():
            if self._serwer is not None:
                self._serwer.close()
            zadania = [z for z in asyncio.all_tasks() if z is not asyncio.current_task()]
            for z in zadania:
                z.cancel()
            await asyncio.gather(*zadania, return_exceptions=True)
            if self._serwer is not None:
                try:
                    await asyncio.wait_for(self._serwer.wait_closed(), 2)
                except (asyncio.TimeoutError, OSError):
                    pass
            petla.stop()
        try:
            asyncio.run_coroutine_threadsafe(koniec(), petla)
        except RuntimeError:
            return
        if self._watek is not None:
            self._watek.join(5)

    # --- obsługa klienta

    async def _adresy(self, host: str, port: int) -> list[str]:
        if self._rozwiaz is not None:
            return list(self._rozwiaz(host, port))
        try:
            ipaddress.ip_address(host)
            return [host]
        except ValueError:
            pass
        wyniki = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return list(dict.fromkeys(str(w[4][0]) for w in wyniki))

    async def _polacz(self, host: str, port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | str:
        """Połączenie z pierwszym dozwolonym adresem `host` albo powód odmowy (tekst)."""
        try:
            adresy = await asyncio.wait_for(self._adresy(host, port), CZAS_POLACZENIA)
        except (OSError, asyncio.TimeoutError, UnicodeError):
            return "nazwa nie istnieje"
        powod, ostatni_blad = None, None
        for ip in adresy:
            p = self.filtr.powod(ip, port)
            if p:
                powod = powod or p
                continue
            try:
                return await asyncio.wait_for(asyncio.open_connection(ip, port), CZAS_POLACZENIA)
            except (OSError, asyncio.TimeoutError) as e:
                ostatni_blad = e
        if powod and ostatni_blad is None:
            return "!" + powod                        # „!” = odmowa filtra, nie błąd sieci
        return "nie udało się połączyć"

    async def _odpowiedz(self, w: asyncio.StreamWriter, kod: int, tekst: str, opis: str = "") -> None:
        tresc = (f"<!doctype html><meta charset=utf-8><title>Komputer Jarva</title>"
                 f"<p>Komputer Jarva: {opis or tekst}</p>").encode("utf-8")
        w.write(f"HTTP/1.1 {kod} {tekst}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(tresc)}"
                f"\r\nConnection: close\r\nX-Jarvo-Filtr: {kod}\r\n\r\n".encode("latin-1") + tresc)
        try:
            await w.drain()
        except OSError:
            pass

    async def _klient(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        try:
            await self._obsluz(r, w)
        except (OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError,
                ValueError):
            pass
        except asyncio.CancelledError:
            pass
        finally:
            try:
                w.close()
            except OSError:
                pass

    async def _obsluz(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        naglowek = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), CZAS_NAGLOWKA)
        linie = naglowek.decode("latin-1").split("\r\n")
        try:
            metoda, cel, wersja = linie[0].split(" ", 2)
        except ValueError:
            await self._odpowiedz(w, 400, "Bad Request", "złe żądanie")
            return
        if metoda.upper() == "CONNECT":
            try:
                host, port = _host_port(cel, 443)
            except ValueError:
                await self._odpowiedz(w, 400, "Bad Request", "zły adres")
                return
            wynik = await self._polacz(host, port)
            if isinstance(wynik, str):
                await self._odmowa(w, host, port, wynik)
                return
            gr, gw = wynik
            w.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await w.drain()
            self.statystyki.przepuszczone += 1
            await self._przepompuj(r, w, gr, gw)
            return
        czesci = urlsplit(cel)
        if czesci.scheme.lower() != "http" or not czesci.hostname:
            await self._odpowiedz(w, 400, "Bad Request", "proxy przyjmuje tylko http:// i CONNECT")
            return
        host, port = czesci.hostname, czesci.port or 80
        wynik = await self._polacz(host, port)
        if isinstance(wynik, str):
            await self._odmowa(w, host, port, wynik)
            return
        gr, gw = wynik
        sciezka = czesci.path or "/"
        if czesci.query:
            sciezka += "?" + czesci.query
        upgrade = any(l.lower().startswith("upgrade:") for l in linie[1:])
        naglowki = [f"{metoda} {sciezka} {wersja}"]
        for linia in linie[1:]:
            if not linia:
                continue
            nazwa = linia.split(":", 1)[0].strip().lower()
            if nazwa.startswith("proxy-") or (nazwa in ("connection", "keep-alive") and not upgrade):
                continue
            naglowki.append(linia)
        if not upgrade:
            naglowki.append("Connection: close")
        gw.write(("\r\n".join(naglowki) + "\r\n\r\n").encode("latin-1"))
        await gw.drain()
        self.statystyki.przepuszczone += 1
        await self._przepompuj(r, w, gr, gw)

    async def _odmowa(self, w: asyncio.StreamWriter, host: str, port: int, wynik: str) -> None:
        if wynik.startswith("!"):
            powod = wynik[1:]
            self.statystyki.blokada(f"{host}:{port}", powod)
            self.log(f"filtr: odrzucone {host}:{port} ({powod})")
            await self._odpowiedz(w, 403, "Forbidden", f"połączenie z {host}:{port} zablokowane ({powod})")
        else:
            await self._odpowiedz(w, 502, "Bad Gateway", f"{host}:{port}: {wynik}")

    async def _przepompuj(self, r1, w1, r2, w2) -> None:
        async def kierunek(r, w):
            try:
                while True:
                    dane = await asyncio.wait_for(r.read(1 << 16), CZAS_BEZCZYNNOSCI)
                    if not dane:
                        break
                    w.write(dane)
                    await w.drain()
            except (OSError, asyncio.TimeoutError):
                pass
            finally:
                try:
                    if w.can_write_eof():
                        w.write_eof()
                except OSError:
                    pass
        try:
            await asyncio.gather(kierunek(r1, w2), kierunek(r2, w1))
        finally:
            for x in (w2, w1):
                try:
                    x.close()
                except OSError:
                    pass


# --------------------------------------------------------------------------- samotest

def cele_samotestu(port_panelu: int = 9119) -> list[tuple[str, int, str]]:
    """Adresy, które proxy ma odrzucić: metadane chmury, panel i API Jarva na pętli zwrotnej (IPv4, IPv6 i nazwa),
    brama sieci lokalnej i adres tego komputera, port 25 na adresie publicznym."""
    cele = [("169.254.169.254", 80, "metadane chmury"), ("127.0.0.1", port_panelu, "panel Jarva"),
            ("127.0.0.1", 8642, "API bramy Jarva"), ("localhost", port_panelu, "panel Jarva (nazwa)"),
            ("[::1]", port_panelu, "panel Jarva (IPv6)"), ("192.168.1.1", 80, "brama sieci lokalnej"),
            ("10.0.0.1", 80, "sieć lokalna"), ("1.1.1.1", 25, "poczta (port 25)")]
    for ip in sorted(adresy_tego_komputera()):
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.version == 4 and not a.is_loopback:
            cele.append((ip, 80, "adres tego komputera"))
            siec = ipaddress.ip_network(f"{ip}/24", strict=False)
            cele.append((str(next(siec.hosts())), 80, "brama sieci lokalnej (zgadnięta)"))
    wynik, widziane = [], set()
    for host, port, opis in cele:
        if (host, port) not in widziane:
            widziane.add((host, port))
            wynik.append((host, port, opis))
    return wynik


def zapytaj_przez_proxy(port_proxy: int, host: str, port: int, czas: float = 10.0) -> int | None:
    """CONNECT host:port przez proxy na 127.0.0.1; kod odpowiedzi albo None (brak odpowiedzi)."""
    s = socket.create_connection(("127.0.0.1", port_proxy), timeout=czas)
    try:
        s.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode("latin-1"))
        dane = b""
        while b"\r\n" not in dane and len(dane) < 4096:
            k = s.recv(4096)
            if not k:
                break
            dane += k
    except OSError:
        return None
    finally:
        s.close()
    try:
        return int(dane.split(b" ", 2)[1])
    except (IndexError, ValueError):
        return None


def samotest(port_proxy: int, port_panelu: int = 9119) -> dict:
    """Każdy cel z `cele_samotestu` ma dostać od proxy 403. {"ok": bool, "cele": [{cel, opis, kod}]}."""
    wyniki, ok = [], True
    for host, port, opis in cele_samotestu(port_panelu):
        kod = zapytaj_przez_proxy(port_proxy, host, port)
        wyniki.append({"cel": f"{host}:{port}", "opis": opis, "kod": kod})
        ok = ok and kod == 403
    return {"ok": ok, "cele": wyniki}
