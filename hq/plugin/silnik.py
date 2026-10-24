"""Silnik rozmów aplikacji Jarvo w procesie dashboardu (docs/HQ.md „Rozmowy”): jeden wątek tła z własną pętlą
asyncio, startowany przy imporcie wtyczki (aplikacja dashboardu ma lifespan, więc `on_startup` routera wtyczki nigdy
się nie wykona, a czekanie na pierwsze żądanie zostawiłoby kolejkę bez ruchu po restarcie).

Wątek ma: połączenie piszące `rozmowy.db` (wszystkie zapisy idą tędy), klienta httpx bramy, `Rejestr` przebiegów,
`Obserwator` plików i nadawanie do `Hub`. Trasy wołają go przez `wykonaj(coro)` (`run_coroutine_threadsafe` +
`wrap_future` pod `asyncio.shield`: rozłączony klient nie przerywa operacji w połowie, np. po steerze, a przed zapisem),
odczyty listy i osi idą przez `asyncio.to_thread` (krótkie połączenia tylko do odczytu).

- **Jeden na proces**: strażnik w `sys.modules` (drugi import wtyczki w tym samym procesie dostaje ten sam silnik).
- **Awaria widoczna**: wyjątek w wątku = do 3 restartów z odstępem 2, 4, 8 s, potem `stan = "awaria"` (`/health`,
  `hello` strumienia; aplikacja pokazuje baner „Odśwież”).
- **Szybki restart dashboardu**: `zahacz_uvicorn` owija `uvicorn.Server.handle_exit` (jak sse-starlette), żeby
  sygnał zamknięcia od razu kończył otwarte strumienie SSE (`Hub.zamknij_wszystkie`); uvicorn czeka na otwarte
  odpowiedzi bez limitu. Wtyczki ładują się przy imporcie web_server, przed `capture_signals`, więc owinięta metoda
  trafia do `signal.signal`.
- **Dziennik** `jarvo.hq`: stdout dashboardu (docker logs) i `/opt/data/logs/jarvo-hq.log` (5 × 2 MB, tryb 0600);
  linie bez treści rozmów: wyjątki tylko nazwą typu, także nieodebrane wyjątki zadań pętli (własna obsługa
  `loop.set_exception_handler` zamiast domyślnej, która wypisuje pełny tekst i ślad).
Wyłączenie (testy, diagnoza): `JARVO_HQ_SILNIK=0`.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import logging.handlers
import os
import sys
import threading
import time
import types
from pathlib import Path
from typing import Any, Callable

STRAZNIK = "jarvo_hq_silnik_instancja"
RESTARTY = (2.0, 4.0, 8.0)
DZIENNIK_MAKS = 2 * 1024 * 1024
DZIENNIK_KOPIE = 4


class SilnikNiedostepny(RuntimeError):
    """Silnik nie działa (wyłączony, startuje albo padł)."""


class _Stdout(logging.StreamHandler):
    """Strumień = bieżące `sys.stdout` (docker logs dashboardu; testy podmieniają stdout)."""

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _wartosc):
        pass


def _przenosne():
    """przenosne.py wtyczki (załadowany przez plugin_api jako jarvo_hq_przenosne albo z pliku obok)."""
    mod = sys.modules.get("jarvo_hq_przenosne")
    if mod is None:
        spec = importlib.util.spec_from_file_location("jarvo_hq_przenosne", Path(__file__).with_name("przenosne.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["jarvo_hq_przenosne"] = mod
        spec.loader.exec_module(mod)
    return mod


def ustaw_dziennik(plik: Path | str | None) -> logging.Logger:
    """Logger `jarvo.hq`: stdout i plik rotowany (5 × 2 MB, 0600). Bez pliku, gdy katalogu nie da się utworzyć."""
    log = logging.getLogger("jarvo.hq")
    if getattr(log, "_jarvo_gotowy", False):
        return log
    log.setLevel(logging.INFO)
    log.propagate = False
    fmt = logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%dT%H:%M:%S")
    h = _Stdout()
    h.setFormatter(fmt)
    log.addHandler(h)
    if plik:
        try:
            p = Path(plik)
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                os.close(fd)
            _przenosne().tryb_pliku(p, 0o600)            # na Windows ACL tylko dla właściciela
            fh = logging.handlers.RotatingFileHandler(p, maxBytes=DZIENNIK_MAKS, backupCount=DZIENNIK_KOPIE,
                                                      encoding="utf-8")
            fh.setFormatter(fmt)
            log.addHandler(fh)
        except OSError as exc:
            log.info(f"jarvo-hq: dziennik w pliku niedostępny ({exc.__class__.__name__})")
    log._jarvo_gotowy = True
    return log


def zahacz_uvicorn(zamknij: Callable[[], None]) -> bool:
    """`uvicorn.Server.handle_exit` woła najpierw `zamknij` (koniec strumieni SSE). True = hak założony."""
    try:
        import uvicorn  # noqa: PLC0415
    except ImportError:
        return False
    Server = uvicorn.Server
    Server._jarvo_zamknij = staticmethod(zamknij)
    if getattr(Server.handle_exit, "_jarvo", False):
        return True
    oryginal = Server.handle_exit

    def handle_exit(self, sig, frame):
        try:
            Server._jarvo_zamknij()
        except Exception:  # zamykanie nie może zablokować wyjścia
            pass
        return oryginal(self, sig, frame)

    handle_exit._jarvo = True
    Server.handle_exit = handle_exit
    return True


class Silnik:
    """Wątek silnika. `moduly`: przestrzeń z modułami wtyczki (rozmowy, brama, przebiegi, strumien, scalanie,
    budzenia, kontekst, czytnik, agenci, obserwator, prace, ochrona, hq_core); ścieżki i bramę podaje wtyczka."""

    def __init__(self, *, moduly: types.SimpleNamespace, home: Path | str, jarvo_dir: Path | str, api_base: str,
                 agenci, hub, log: Callable[[str], None] | None = None, limit: int | None = None,
                 sciezka_db: Path | str | None = None, stan_aktualizacji: Callable[[], dict] | None = None,
                 obserwator: bool = True, http=None, odstep_odpytania: float | None = None,
                 plik: Callable[[str], dict | None] | None = None):
        self.m = moduly
        self.home = Path(home)
        self.jarvo_dir = Path(jarvo_dir)
        self.api_base = api_base
        self.agenci = agenci
        self.hub = hub
        self.log = log or (lambda _m: None)
        zadany = str(limit or os.environ.get("JARVO_HQ_MAX_PRZEBIEGOW") or "").strip()   # zła wartość = domyślny
        # tylko cyfry ASCII: `isdigit` przepuszcza „²” i inne cyfry Unicode, których `int` nie czyta
        self.limit = max(1, min(32, int(zadany))) if zadany.isascii() and zadany.isdigit() else moduly.przebiegi.LIMIT
        self.sciezka_db = Path(sciezka_db or self.jarvo_dir / "state" / "rozmowy.db")
        self.stan_aktualizacji = stan_aktualizacji or (lambda: {})
        self.z_obserwatorem = obserwator
        self._http = http
        self.odstep_odpytania = odstep_odpytania
        self.plik = plik
        self.stan = "start"
        self.blad: str | None = None
        self.start_at = time.time()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.watek: threading.Thread | None = None
        self.db = self.brama = self.rejestr = self.obserwator = self.czytnik = None
        self._gotowy = threading.Event()
        self._koniec: asyncio.Event | None = None
        self.czytnik = moduly.czytnik.Czytnik(self.home / "profiles", agenci.nazwy, log=self.log)

    # ------------------------------------------------------------------------------------------- start
    def start(self, czekaj: float = 10.0) -> "Silnik":
        self.watek = threading.Thread(target=self._watek, name="jarvo-silnik", daemon=True)
        self.watek.start()
        self._gotowy.wait(czekaj)
        return self

    def _watek(self) -> None:
        for proba in range(len(RESTARTY) + 1):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            try:
                loop.run_until_complete(self._glowna())
                return                                      # zwykłe zamknięcie
            except Exception as exc:
                self.blad = type(exc).__name__          # bez tekstu wyjątku (może nieść treść)
                self.log(f"jarvo-hq: silnik padł ({self.blad})"
                         + (f", restart {proba + 1}/{len(RESTARTY)}" if proba < len(RESTARTY) else ""))
            finally:
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                loop.close()
            if proba < len(RESTARTY):
                self.stan = "start"
                time.sleep(RESTARTY[proba])
        self.stan = "awaria"
        self._gotowy.set()
        self.log("jarvo-hq: silnik rozmów nie działa po 3 restartach")

    async def _glowna(self) -> None:
        import httpx  # noqa: PLC0415

        m = self.m
        self._koniec = asyncio.Event()
        if self.db is None or self.db._watek != threading.get_ident():
            self.db = m.rozmowy.Rozmowy(self.sciezka_db)
        self.db.migruj()
        try:
            wynik = m.rozmowy.migruj_hq_sessions(self.db, self.jarvo_dir / "state" / "hq-sessions.json",
                                                 self.home / "profiles", agenci=self.agenci.nazwy_wyswietlane(),
                                                 log=self.log)
            if wynik.get("zaimportowane"):
                self.log(f"jarvo-hq: zaimportowane stare rozmowy: {len(wynik['zaimportowane'])}")
        except Exception as exc:
            self.log(f"jarvo-hq: import hq-sessions.json: {type(exc).__name__}")
        asyncio.get_running_loop().set_exception_handler(self._wyjatek_petli)
        http = self._http or m.brama.klient_http(timeout=m.brama.CZAS,
                                                 limits=httpx.Limits(max_connections=40, max_keepalive_connections=20))
        self.brama = m.brama.KlientBramy(self.api_base, m.brama.Klucze(self.home), http)
        kw = {}
        if self.odstep_odpytania is not None:
            kw["odstep_odpytania"] = self.odstep_odpytania
        self.rejestr = m.przebiegi.Rejestr(
            self.db, self.brama, self.hub, czytnik=self.czytnik, agenci=self.agenci, kontekst=m.kontekst,
            scalanie=m.scalanie, budzenia=m.budzenia, cialo=m.brama.cialo, cialo_sha=m.brama.cialo_sha,
            blad_bramy=m.brama.BladBramy, utajnij=m.ochrona.utajnij, etykieta=m.hq_core.tool_label, limit=self.limit,
            log=self.log, czas_zgody=self._czas_zgody, aktualizacja=self._aktualizacja, brama_mloda=self._brama_mloda,
            obrazy_wprost=self._obrazy_wprost, plik=self.plik, **kw)
        await self.rejestr.uruchom()
        if self.z_obserwatorem:
            self.obserwator = m.obserwator.Obserwator(
                db=self.db, czytnik=self.czytnik, rejestr=self.rejestr, hub=self.hub, agenci=self.agenci,
                home=self.home, jarvo_dir=self.jarvo_dir, prace=m.prace, budzenia=m.budzenia, log=self.log,
                stan_aktualizacji=self.stan_aktualizacji)
            obs = asyncio.get_running_loop().create_task(self.obserwator.petla())
        else:
            obs = None
        self.stan = "ok"
        self.blad = None
        self._gotowy.set()
        self.log(f"jarvo-hq: silnik rozmów działa (limit {self.limit}, czytnik {self.czytnik.tryb})")
        try:
            await self._koniec.wait()
        finally:
            # obserwator i jego porządki (przypinanie, sprzątanie) kończą się przed pętlami rejestru i klientem HTTP
            zadania = [t for t in (obs, getattr(self.obserwator, "_porzadki", None)) if t is not None]
            for t in zadania:
                t.cancel()
            await asyncio.gather(*zadania, return_exceptions=True)
            await self.rejestr.zatrzymaj_petle()
            if self._http is None:
                await http.aclose()

    def _wyjatek_petli(self, _loop, kontekst: dict) -> None:
        exc = kontekst.get("exception")
        self.log(f"jarvo-hq: pętla silnika: {type(exc).__name__ if exc else 'błąd'}"
                 f"{' (' + str(kontekst.get('message'))[:80] + ')' if not exc and kontekst.get('message') else ''}")

    def zamknij(self, czekaj: float = 5.0) -> None:
        """Koniec wątku (testy); w dashboardzie wątek kończy się z procesem."""
        if self.loop is not None and self._koniec is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._koniec.set)
        if self.watek is not None:
            self.watek.join(czekaj)
        self.stan = "zamkniety"

    # ------------------------------------------------------------------------------------------- most dla tras
    def dziala(self) -> bool:
        return self.stan == "ok" and self.loop is not None and not self.loop.is_closed()

    def wykonaj(self, coro) -> "asyncio.Future":
        """Korutyna na pętli silnika; wynik jako awaitable pętli wołającego. Anulowanie wołającego (klient się
        rozłączył, zamykanie) nie anuluje operacji silnika: ta kończy się, wynik przepada."""
        if not self.dziala():
            coro.close()
            raise SilnikNiedostepny(self.stan)
        fut = asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, self.loop))
        fut.add_done_callback(lambda f: f.cancelled() or f.exception())     # wynik porzucony bez ostrzeżenia
        return asyncio.shield(fut)

    def wykonaj_fn(self, fn: Callable, *arg, **kw):
        """Zwykła funkcja (zapis do rozmowy.db) na wątku silnika."""
        async def _f():
            return fn(*arg, **kw)
        return self.wykonaj(_f())

    # ------------------------------------------------------------------------------------------- ustawienia
    def _czas_zgody(self, agent: str) -> float:
        cfg = (self.home / "config.yaml") if agent in ("", "default") else (self.home / "profiles" / agent / "config.yaml")
        return self.m.przebiegi.czas_zgody_z_configu(cfg)

    def _aktualizacja(self) -> bool:
        st = self.stan_aktualizacji() or {}
        return bool(st.get("online") and st.get("state") == "updating")

    def _brama_mloda(self) -> bool:
        """Silnik albo brama wstała mniej niż 2 min temu (ostatni start w `gateway-starts.log`, aplikacja.py)."""
        if time.time() - self.start_at < 120:
            return True
        apl = getattr(self.m, "aplikacja", None)
        return bool(apl and apl.brama_mloda(self.home))

    def _obrazy_wprost(self) -> bool:
        if os.environ.get("JARVO_HQ_OBRAZY_WPROST") == "0":
            return False
        return (self.db.meta("obrazy_wprost", "1") if self.db else "1") != "0"

    # ------------------------------------------------------------------------------------------- zdrowie
    def zdrowie(self) -> dict:
        out: dict[str, Any] = {"silnik": "ok" if self.dziala() else ("awaria" if self.stan == "awaria" else self.stan),
                               "pid": os.getpid(), "czytnik": self.czytnik.tryb if self.czytnik else None,
                               "strumien": {"polaczenia": self.hub.liczba_polaczen()}}
        if self.blad:
            out["silnik_blad"] = self.blad
        if self.obserwator is not None:
            out["obserwator"] = self.obserwator.zdrowie()
        if self.rejestr is not None:
            out["rejestr"] = self.rejestr.zdrowie()
        return out


def instancja() -> Silnik | None:
    mod = sys.modules.get(STRAZNIK)
    return getattr(mod, "silnik", None) if mod else None


def zarejestruj(s: Silnik) -> Silnik:
    """Jeden silnik na proces: pierwszy zarejestrowany wygrywa."""
    mod = sys.modules.get(STRAZNIK)
    if mod is None:
        mod = types.ModuleType(STRAZNIK)
        mod.silnik = None
        sys.modules[STRAZNIK] = mod
    if mod.silnik is None:
        mod.silnik = s
    return mod.silnik
