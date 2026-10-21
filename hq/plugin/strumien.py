"""Strumień SSE aplikacji Jarvo (docs/HQ.md „Rozmowy”): jeden `GET /strumien` na przeglądarkę (karta-lider),
pierścień zdarzeń z wznowieniem od kursora i routing po wątkach.

- **Kursor** `<epoka>.<seq>`: epoka = losowy hex na start procesu, seq rośnie z każdym zdarzeniem. Wznowienie z
  `Last-Event-ID` (ponowne połączenie przeglądarki) albo `?od=` (każde połączenie, które klient otwiera sam);
  nagłówek wygrywa. Ta sama epoka i seq w pierścieniu = powtórka zdarzeń po nim; inna epoka albo seq starszy niż
  pierścień = `reset` (klient pobiera listę, otwarte wątki i aktywne przebiegi od nowa).
- **Kursor w ramkach `hello`, `reset` i `kursor`**: `reset` (też przepełnienie) i `hello` nowego połączenia bez
  kursora niosą `id: <epoka>.<seq>` chwili, od której klient ma stan, więc automatyczne wznowienie przeglądarki
  (`Last-Event-ID`) po resecie nie dostaje tego samego resetu co 25 s. `hello` przy powtórce nie ma `id`, za to
  powtórka kończy się ramką `kursor` z `id` chwili połączenia (powtórka i rejestracja pod jedną blokadą: wszystko
  wcześniejsze dla tego klienta już przyszło), więc kursor klienta oglądającego cichy wątek idzie naprzód z każdym
  wznowieniem i nie wypada z pierścienia, gdy inne wątki mówią. Przepełnienie kolejki: `reset` z seq ramki, która
  się nie zmieściła; ramki o seq nie większym niż ten (spóźnione z innego wątku) są pomijane.
- **Pierścień**: 2000 zdarzeń, 5 minut albo 8 MB ramek (co pierwsze).
- **Routing**: zdarzenie z `watek_id` idzie tylko do klientów, którzy subskrybują ten wątek; globalne do wszystkich.
  Hub pamięta per klient bieżący zbiór wątków (z URL-a połączenia albo z ostatniego `POST /subskrypcje`) i URL,
  z którym klient się łączył, przez 2 × czas życia strumienia. Przeglądarka wznawia połączenie z pierwotnym URL-em:
  ten sam URL = zapamiętany zbiór (wątki dodane i zamknięte później zostają takie, jak w ostatnim POST); inny URL =
  klient otworzył strumień sam, wygrywa URL; POST sprzed pierwszego połączenia klienta = suma z URL-em.
  `subskrybowane_watki` liczy je przez ten sam czas.
- **Najwyżej 20 strumieni** naraz: nowy zamyka najstarszy (z dziennikiem).
- **Wątki**: `nadaj` woła wątek silnika; każde połączenie pamięta pętlę serwera i dostaje ramki przez
  `loop.call_soon_threadsafe`. Kolejka połączenia ma 1000 miejsc; przepełnienie = `reset` i zrzucenie zaległości.
- **Czas życia**: każdy strumień kończy się sam po 25 s (po ramce `retry: 1000`), `: ping` co 10 s; przeglądarka
  łączy się ponownie z kursorem. Dzięki temu restart dashboardu (uvicorn czeka na otwarte odpowiedzi bez limitu)
  trwa najwyżej 25 s, a z `zamknij_wszystkie()` (hak `handle_exit`, silnik.py) poniżej sekundy.
Czysty Python (asyncio); testy: tests/test_strumien.py.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import threading
import time
from collections import deque
from typing import Any, AsyncIterator, Callable

POJEMNOSC = 2000
WIEK_S = 300.0
BAJTY_MAKS = 8 * 1024 * 1024
ZYCIE_S = 25.0
PING_S = 10.0
KOLEJKA = 1000
POLACZENIA_MAKS = 20
_KONIEC = object()


def _ramka(kursor: str | None, typ: str, dane: Any) -> bytes:
    tekst = json.dumps(dane, ensure_ascii=False, separators=(",", ":"))
    glowa = f"id: {kursor}\n" if kursor else ""
    return f"{glowa}event: {typ}\ndata: {tekst}\n\n".encode("utf-8")


def parsuj_kursor(kursor: str | None) -> tuple[str, int] | None:
    if not kursor or "." not in kursor:
        return None
    epoka, _, seq = kursor.strip().rpartition(".")
    try:
        return epoka, int(seq)
    except ValueError:
        return None


class Polaczenie:
    """Jedno połączenie SSE klienta. Ramki wstawia wątek silnika (`_wstaw` przez call_soon_threadsafe)."""

    def __init__(self, hub: "Hub", klient: str, watki: set[str], loop: asyncio.AbstractEventLoop, *,
                 poczatek: list[bytes], zycie: float, ping: float):
        self.hub = hub
        self.klient = klient
        self.watki = set(watki)
        self.panele: list[dict] = []
        self.sesje: list[dict] = []
        self.loop = loop
        self.kolejka: deque[Any] = deque(poczatek)
        self.zycie = zycie
        self.ping = ping
        self.otwarte_at = time.monotonic()
        self._sygnal = asyncio.Event()
        self._reset = False
        self._reset_kursor: str | None = None
        self._reset_seq = -1
        self._zamkniete = False
        if self.kolejka:
            self._sygnal.set()

    def _wstaw(self, ramka: Any, seq: int = -1) -> None:
        if self._zamkniete:
            return
        if ramka is _KONIEC:
            self._zamkniete = True
        elif 0 <= seq <= self._reset_seq:
            return                    # spóźniona ramka sprzed resetu (inny wątek nadawał równolegle): stan ją już ma
        elif len(self.kolejka) >= KOLEJKA:
            self.kolejka.clear()
            self._reset = True
            # stan klienta po resecie = od ramki, która się nie zmieściła: każda następna ma większy seq
            self._reset_seq = max(self._reset_seq, seq)
            self._reset_kursor = f"{self.hub.epoka}.{seq}" if seq >= 0 else self.hub.kursor()
        else:
            self.kolejka.append(ramka)
        self._sygnal.set()

    def wstaw(self, ramka: Any, seq: int = -1) -> None:
        """Bezpieczne z każdego wątku."""
        try:
            self.loop.call_soon_threadsafe(self._wstaw, ramka, seq)
        except RuntimeError:          # pętla serwera już zamknięta
            self._zamkniete = True

    def zamknij(self) -> None:
        self.wstaw(_KONIEC)

    async def strumien(self, czy_rozlaczony: Callable[[], Any] | None = None) -> AsyncIterator[bytes]:
        """retry, hello, powtórka, na żywo, ping co 10 s; koniec po 25 s albo przy zamknięciu."""
        koniec_at = time.monotonic() + self.zycie
        ping_at = time.monotonic() + self.ping
        powod = "czas"
        try:
            yield b"retry: 1000\n\n"
            while True:
                if self._reset:              # przed kolejką: ramki po wyczyszczeniu mają seq > kursora resetu
                    self._reset = False
                    yield _ramka(self._reset_kursor, "reset", {"powod": "przepelnienie"})
                    continue
                while self.kolejka and not self._reset:
                    ramka = self.kolejka.popleft()
                    yield ramka
                if self._reset:
                    continue
                if self._zamkniete:
                    powod = "zamkniete"
                    break
                teraz = time.monotonic()
                if teraz >= koniec_at:
                    break
                if teraz >= ping_at:
                    yield b": ping\n\n"
                    ping_at = teraz + self.ping
                    continue
                self._sygnal.clear()
                if self.kolejka or self._reset or self._zamkniete:
                    continue
                try:
                    await asyncio.wait_for(self._sygnal.wait(), timeout=max(0.01, min(koniec_at, ping_at) - teraz))
                except asyncio.TimeoutError:
                    pass
        except (asyncio.CancelledError, GeneratorExit):
            powod = "klient"
            raise
        finally:
            self.hub.rozlacz(self.klient, self, powod=powod)


class Hub:
    """Rozgłośnia zdarzeń aplikacji z pierścieniem do powtórek; jedna na proces dashboardu."""

    def __init__(self, *, pojemnosc: int = POJEMNOSC, wiek: float = WIEK_S, zycie: float = ZYCIE_S, ping: float = PING_S,
                 zegar: Callable[[], float] = time.monotonic, log: Callable[[str], None] | None = None,
                 hello: Callable[[], dict] | None = None):
        self.epoka = secrets.token_hex(3)
        self.seq = 0
        self.pojemnosc = pojemnosc
        self.wiek = wiek
        self.zycie = zycie
        self.ping = ping
        self.zegar = zegar
        self.log = log or (lambda _m: None)
        self.hello = hello or (lambda: {})
        self._bufor: deque[tuple[int, float, str | None, bytes]] = deque()
        self._bajty = 0
        self._lock = threading.Lock()
        self._polaczenia: dict[str, Polaczenie] = {}
        # klient → (bieżące wątki: z URL-a albo z ostatniego POST, kiedy ostatnio, wątki z URL-a połączenia)
        self._subskrypcje: dict[str, tuple[set[str], float, frozenset[str] | None]] = {}
        self._zamkniety = False

    # ------------------------------------------------------------------------------------------- stan
    def kursor(self) -> str:
        with self._lock:
            return f"{self.epoka}.{self.seq}"

    def liczba_polaczen(self) -> int:
        with self._lock:
            return len(self._polaczenia)

    def subskrybowane_watki(self) -> set[str]:
        """Wątki otwarte w którejś karcie (dla licznika nieprzeczytanych), także w przerwie między połączeniami."""
        with self._lock:
            self._zapomnij_stare()
            return {w for p in self._polaczenia.values() for w in p.watki} | {
                w for ws, _at, _u in self._subskrypcje.values() for w in ws}

    def _zapomnij_stare(self) -> None:
        granica = time.monotonic() - 2 * max(self.zycie, 1.0)
        for k in [k for k, (_ws, at, _u) in self._subskrypcje.items() if at < granica and k not in self._polaczenia]:
            del self._subskrypcje[k]

    def _przytnij_subskrypcje(self) -> None:
        """Najwyżej 200 zapamiętanych klientów (pod blokadą): najpierw stare, potem najdawniej widziani."""
        if len(self._subskrypcje) > 200:
            self._zapomnij_stare()
            for k in sorted(self._subskrypcje, key=lambda k: self._subskrypcje[k][1])[:len(self._subskrypcje) - 200]:
                self._subskrypcje.pop(k, None)

    def _przytnij(self) -> None:
        granica = self.zegar() - self.wiek
        while self._bufor and (len(self._bufor) > self.pojemnosc or self._bufor[0][1] < granica
                               or self._bajty > BAJTY_MAKS):
            self._bajty -= len(self._bufor.popleft()[3])

    # ------------------------------------------------------------------------------------------- nadawanie
    def nadaj(self, typ: str, dane: dict, *, watek_id: str | None = None) -> int:
        """Zdarzenie do pierścienia i do subskrybentów; bezpieczne z każdego wątku. Zwraca seq."""
        with self._lock:
            self.seq += 1
            kursor = f"{self.epoka}.{self.seq}"
            ramka = _ramka(kursor, typ, dane)
            self._bufor.append((self.seq, self.zegar(), watek_id, ramka))
            self._bajty += len(ramka)
            self._przytnij()
            odbiorcy = [p for p in self._polaczenia.values() if watek_id is None or watek_id in p.watki]
            seq = self.seq
        for p in odbiorcy:
            p.wstaw(ramka, seq)
        return seq

    # ------------------------------------------------------------------------------------------- połączenia
    def polacz(self, klient: str, watki: set[str] | list[str], od: str | None, *,
               loop: asyncio.AbstractEventLoop | None = None) -> Polaczenie:
        """Nowe połączenie (wołane na pętli serwera). Starsze połączenie z tym samym `klient` jest zamykane.
        Powtórka i rejestracja pod jedną blokadą: żadne zdarzenie nie zginie ani nie przyjdzie dwa razy."""
        loop = loop or asyncio.get_running_loop()
        watki = set(watki or ())
        with self._lock:
            teraz_kursor = f"{self.epoka}.{self.seq}"
            hello = {**self.hello(), "epoka": self.epoka, "klient": klient, "czas": time.time(), "kursor": teraz_kursor}
            if self._zamkniety:
                pol = Polaczenie(self, klient, watki, loop, poczatek=[_ramka(None, "hello", hello)], zycie=0,
                                 ping=self.ping)
                pol._zamkniete = True
                return pol
            self._przytnij()
            self._zapomnij_stare()
            pamiec = self._subskrypcje.get(klient)
            url = frozenset(watki)
            if pamiec is not None and pamiec[2] == url:
                watki = set(pamiec[0])          # wznowienie przeglądarki ze starym URL-em: nowszy stan z POST wygrywa
            elif pamiec is not None and pamiec[2] is None:
                watki |= pamiec[0]              # POST przyszedł przed pierwszym połączeniem tego klienta: suma
            self._subskrypcje[klient] = (set(watki), time.monotonic(), url)
            self._przytnij_subskrypcje()
            k = parsuj_kursor(od)
            reset = None
            powtorka: list[bytes] = []
            if od and k is None:
                reset = "za_stare"
            elif k is not None:
                epoka, seq = k
                najstarszy = self._bufor[0][0] if self._bufor else self.seq + 1
                if epoka != self.epoka:
                    reset = "epoka"
                elif seq > self.seq or seq < najstarszy - 1:
                    reset = "za_stare"
                else:
                    powtorka = [r for s, _t, w, r in self._bufor if s > seq and (w is None or w in watki)]
            # kursor w hello tylko bez wznowienia; reset niesie kursor chwili resetu (wznowienie przeglądarki
            # z Last-Event-ID nie dostanie go znowu)
            poczatek = [_ramka(teraz_kursor if k is None and not od else None, "hello", hello)]
            if reset:
                poczatek.append(_ramka(teraz_kursor, "reset", {"powod": reset}))
            elif k is not None:
                # po powtórce: kursor chwili połączenia (nic wcześniejszego dla tego klienta już nie przyjdzie)
                poczatek += powtorka + [_ramka(teraz_kursor, "kursor", {"kursor": teraz_kursor})]
            stare = self._polaczenia.get(klient)
            pol = Polaczenie(self, klient, watki, loop, poczatek=poczatek, zycie=self.zycie, ping=self.ping)
            self._polaczenia[klient] = pol
            nadmiar = []
            if len(self._polaczenia) > POLACZENIA_MAKS:
                nadmiar = sorted((p for k_, p in self._polaczenia.items() if k_ != klient),
                                 key=lambda p: p.otwarte_at)[:len(self._polaczenia) - POLACZENIA_MAKS]
                for p in nadmiar:
                    self._polaczenia.pop(p.klient, None)
        for p in nadmiar:
            p.zamknij()
            self.log(f"jarvo-hq: strumień {p.klient} zamknięty (limit {POLACZENIA_MAKS} strumieni)")
        if stare is not None:
            stare.zamknij()
        self.log(f"jarvo-hq: strumień {klient} połączony (wątki {len(watki)}, od {'tak' if od else 'nie'})")
        return pol

    def subskrybuj(self, klient: str, *, watki: set[str] | list[str], panele: list[dict] | None = None,
                   sesje: list[dict] | None = None) -> bool:
        """Suma subskrypcji kart przeglądarki (lider), zapamiętana dla wznowień. False, gdy klient nie ma teraz
        otwartego strumienia (zapamiętana i tak: następne połączenie jej użyje)."""
        with self._lock:
            byl = self._subskrypcje.get(klient)
            self._subskrypcje[klient] = (set(watki or ()), time.monotonic(), byl[2] if byl else None)
            self._przytnij_subskrypcje()
            p = self._polaczenia.get(klient)
            if p is None:
                return False
            p.watki = set(watki or ())
            p.panele = list(panele or [])
            p.sesje = list(sesje or [])
        return True

    def rozlacz(self, klient: str, pol: Polaczenie | None = None, *, powod: str = "") -> None:
        with self._lock:
            obecne = self._polaczenia.get(klient)
            if obecne is not None and (pol is None or obecne is pol):
                del self._polaczenia[klient]
                if klient in self._subskrypcje:          # okres łaski od rozłączenia
                    ws, _at, url = self._subskrypcje[klient]
                    self._subskrypcje[klient] = (ws, time.monotonic(), url)
            else:
                return
        trwalo = time.monotonic() - obecne.otwarte_at
        self.log(f"jarvo-hq: strumień {klient} rozłączony po {trwalo:.1f} s ({powod or 'koniec'})")

    def zamknij_wszystkie(self) -> None:
        """Wyłączanie procesu: każdy strumień kończy się od razu, nowe kończą się zaraz po hello."""
        with self._lock:
            self._zamkniety = True
            wszystkie = list(self._polaczenia.values())
        for p in wszystkie:
            p.zamknij()
