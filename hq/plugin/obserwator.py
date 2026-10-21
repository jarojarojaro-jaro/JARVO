"""Obserwator plików silnika rozmów (docs/HQ.md „Rozmowy”): pętla co 1 s (co 0,5 s, gdy jakiś przebieg pracuje),
same `os.stat`, SQL tylko dla ścieżek, które się zmieniły. Etap 2:

- **state.db profili członków** (i `-wal`): (1) przedłużenie rodowodu: sesja potomna, której rodzic skończył się
  kompresją z rotacją, dostaje wiersz `sesje` (`kompresja`) i staje się `sesja_tip`; (2) nowe wiersze sesji członka
  (`max(id)` > `odczyt_id`) spoza naszej tury = `watek.os` (podpowiedź do pobrania osi), nieprzeczytane i podgląd
  (budzenie kanbana: „Karta „…” · zakończona”); wiersze naszej tury tego nie robią (pokazuje je żywy dymek);
  (3) kompresja w miejscu (zmiana liczby wierszy skompaktowanych) = `watek.os {pelny: true}` i notka systemu;
  (4) budzik dyspozytora (dzierżawa mogła się zwolnić, nasz wiersz mógł się pojawić).
- **agenci.json** = `agenci.zmiana`; **update.json** = `aktualizacja`.
- Co minutę ponowne przypięcie sesji członków w Hermesie (`sesje.przypieta = 0`), raz na dobę `sprzataj`
  (kosz po 30 dniach; sesje usuniętych wątków odpinane): osobnym zadaniem, najwyżej jednym naraz, żeby wolna brama
  nie zatrzymała patrzenia na pliki; `praca.json` przy każdej zmianie i co minutę.
- **Aktualizacja po pracy** („Zaktualizuj, gdy skończą”, docs/HQ.md „Aktualizacja”): przy meta
  `aktualizacja_po_pracy` w rozmowy.db plik `update-request` powstaje dopiero po 30 s bez pracy (N = 0 w praca.json);
  potem meta znika i idzie zdarzenie `aktualizacja`. Gdy aktualizacja już trwa, prośby nie piszemy.
- Nasz dopisek (`steer`) w state.db to nie „wiadomość spoza aplikacji”: Hermes zapisuje go jako wiersz `steer` owinięty
  znacznikiem, więc porównujemy całe linie tekstu z dopiskami członka w wątku, nie skrót.
Obserwator kanbana (karty wątku, decyzje), indeks sesji listy i spool przekazań przyjdą w etapach 4, 4b i 6.
Asyncio na pętli wątku silnika; testy: tests/test_silnik_rozmow.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Callable

PRZYPINANIE_S = 60.0
SPRZATANIE_S = 86400.0
PRACA_ODSWIEZ_S = 60.0
DZIERZAWY_S = 10.0
PO_PRACY_CISZA_S = 30.0


def _zapisz_prosbe(plik: Path) -> None:
    plik.parent.mkdir(parents=True, exist_ok=True)
    tmp = plik.with_name(plik.name + ".tmp")
    tmp.write_text("update", encoding="utf-8")
    tmp.replace(plik)


def _syg(p: Path) -> tuple:
    out = []
    for q in (p, p.with_name(p.name + "-wal")):
        try:
            st = q.stat()
            out.append((st.st_mtime_ns, st.st_size))
        except OSError:
            out.append(None)
    return tuple(out)


class Obserwator:
    def __init__(self, *, db, czytnik, rejestr, hub, agenci, home: Path | str, jarvo_dir: Path | str, prace=None,
                 budzenia=None, log: Callable[[str], None] | None = None, zegar: Callable[[], float] = time.time,
                 stan_aktualizacji: Callable[[], dict] | None = None):
        self.db, self.czytnik, self.rejestr, self.hub, self.agenci = db, czytnik, rejestr, hub, agenci
        self.prace, self.budzenia = prace, budzenia
        self.home, self.jarvo_dir = Path(home), Path(jarvo_dir)
        self.log = log or (lambda _m: None)
        self.zegar = zegar
        self.stan_aktualizacji = stan_aktualizacji or (lambda: {})
        self.pliki = {"agenci": self.jarvo_dir / "state" / "agenci.json",
                      "aktualizacja": self.jarvo_dir / "state" / "update.json",
                      "kanban": self.home / "kanban.db"}
        self.praca_json = self.jarvo_dir / "state" / "praca.json"
        self._syg_plikow: dict[str, tuple] = {k: _syg(v) for k, v in self.pliki.items()}
        self._syg_profili: dict[str, tuple] = {}
        self._czlonkowie: dict[tuple, dict] = {}
        self._karty: list[dict] = []
        self._karty_syg: tuple | None = None
        self._dzierzawy: list[dict] = []
        self._dzierzawy_at = 0.0
        self._praca: tuple | None = None
        self._praca_at = 0.0
        self._zero_od: float | None = None
        self.ostatnia_praca: dict = {"aktywne": 0, "opis": []}
        self._przypinanie_at = 0.0
        self._porzadki: asyncio.Task | None = None
        self.cykl_ms = 0
        self.bledy = 0

    # ------------------------------------------------------------------------------------------- pętla
    async def petla(self) -> None:
        while True:
            t0 = time.monotonic()
            try:
                await self.cykl()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.bledy += 1
                self.log(f"jarvo-hq: obserwator: {type(exc).__name__}")
            self.cykl_ms = int((time.monotonic() - t0) * 1000)
            await asyncio.sleep(0.5 if self.rejestr.aktywne_liczba() else 1.0)

    async def cykl(self) -> None:
        teraz = self.zegar()
        zmienione_profile = await self._profile()
        for nazwa, typ in (("agenci", "agenci.zmiana"), ("aktualizacja", "aktualizacja")):
            s = _syg(self.pliki[nazwa])
            if s != self._syg_plikow.get(nazwa):
                self._syg_plikow[nazwa] = s
                self.hub.nadaj(typ, self.stan_aktualizacji() if nazwa == "aktualizacja" else {})
        await self._praca_floty(teraz, bool(zmienione_profile))
        if teraz - self._przypinanie_at >= PRZYPINANIE_S and (self._porzadki is None or self._porzadki.done()):
            # osobne zadanie (najwyżej jedno naraz): wolna brama (do 15 s na wywołanie) nie zatrzymuje patrzenia na pliki
            self._przypinanie_at = teraz
            self._porzadki = asyncio.get_running_loop().create_task(self._porzadki_co_minute(teraz))

    async def _porzadki_co_minute(self, teraz: float) -> None:
        try:
            await self._przypnij()
            await self._sprzataj(teraz)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.bledy += 1
            self.log(f"jarvo-hq: obserwator, przypinanie i sprzątanie: {type(exc).__name__}")

    # ------------------------------------------------------------------------------------------- profile
    async def _profile(self) -> set[str]:
        """Profile członków z nową sygnaturą state.db; dla każdego rodowody, nowe wiersze i kompresje."""
        grupy: dict[str, dict[tuple, list[str]]] = {}
        for s in self.db.sesje_czlonkow():
            if s.get("watek_id"):
                grupy.setdefault(s["agent"], {}).setdefault((s["watek_id"], s["rola"]), []).append(s["sesja_id"])
        zmienione = set()
        for agent, czlonkowie in grupy.items():
            try:
                sciezka = self.czytnik.state_db(agent)
            except ValueError:
                continue
            s = _syg(sciezka)
            if s == self._syg_profili.get(agent):
                continue
            self._syg_profili[agent] = s
            zmienione.add(agent)
            for (wid, rola), rodowod in czlonkowie.items():
                try:
                    await self._czlonek(agent, wid, rola, rodowod)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.bledy += 1
                    self.log(f"jarvo-hq: obserwator {agent}/{wid}: {type(exc).__name__}")
            self.rejestr.zmiana_stanu(agent)
        return zmienione

    async def _czlonek(self, agent: str, wid: str, rola: str, rodowod: list[str]) -> None:
        dzieci = await asyncio.to_thread(self.czytnik.dzieci_kompresji, agent, rodowod)
        znane = set(rodowod)
        for dziecko, rodzic in dzieci:
            if dziecko in znane:
                continue
            try:
                self.db.ustaw_sesje(wid, agent, dziecko, rola=rola, powod="kompresja", rodzic=rodzic)
            except ValueError:
                continue
            znane.add(dziecko)
            rodowod = rodowod + [dziecko]
            self.log(f"jarvo-hq: wątek {wid}: rodowód {agent} przedłużony po kompresji")
            self._notka_kompresji(wid, agent)
        st = await asyncio.to_thread(self.czytnik.stan_sesji, agent, rodowod)
        klucz = (wid, agent, rola)
        poprzedni = self._czlonkowie.get(klucz)
        self._czlonkowie[klucz] = st
        czl = self.db.czlonek(wid, agent, rola) or {}
        if st["max_id"] > int(czl.get("odczyt_id") or 0):
            tresc, rodzaj = await asyncio.to_thread(self.czytnik.ostatni_uzytkownika, agent, rodowod)
            if not self._nasza_tura(wid, agent, rola, tresc, rodzaj):
                self._nowe_wiersze(wid, agent, rola, tresc)
            self.db.zmien_czlonka(wid, agent, rola, odczyt_id=st["max_id"])
        if poprzedni is not None and st["skompaktowane"] != poprzedni["skompaktowane"]:
            self.hub.nadaj("watek.os", {"watek_id": wid, "agent": agent, "pelny": True}, watek_id=wid)
            if st["skompaktowane"] > poprzedni["skompaktowane"]:
                self._notka_kompresji(wid, agent)

    def _nasza_tura(self, wid: str, agent: str, rola: str, tresc: str, rodzaj: str = "") -> bool:
        """Najnowszy wiersz użytkownika rodowodu należy do naszego przebiegu (jego wiersze pokazuje żywy dymek,
        a koniec przebiegu sam podbija wątek). Wiersz `steer` jest nasz, gdy niesie (całymi liniami) tekst któregoś
        naszego dopisku tego członka: Hermes owija go znacznikiem, więc skrót `payload_sha` nie pasuje."""
        if not tresc:
            return True
        przebiegi = [p for p in self.db.przebiegi_watku(wid)
                     if p["agent"] == agent and (p.get("rola") or "rozmowa") == rola]
        if rodzaj == "steer" and any(p.get("dopisany_do") and self.czytnik.dopisek_w_steerze(
                tresc, (p.get("payload") or {}).get("prosba") or "") for p in przebiegi):
            return True
        sha = hashlib.sha256(tresc.encode("utf-8", "surrogatepass")).hexdigest()
        return any(p.get("payload_sha") == sha for p in przebiegi)

    def _nowe_wiersze(self, wid: str, agent: str, rola: str, tresc: str) -> None:
        self.hub.nadaj("watek.os", {"watek_id": wid, "agent": agent}, watek_id=wid)
        if rola == "nadzor":
            return
        b = self.budzenia.parsuj(tresc) if self.budzenia else None
        nazwy = self.agenci.nazwy_wyswietlane()
        if b:
            podglad = f"Karta „{b['tytul']}” · {nazwy.get(b['wykonawca'], b['wykonawca'])} · {b['status_pl']}"
        else:
            podglad = f"{nazwy.get(agent, agent)}: wiadomość spoza aplikacji"
        otwarty = wid in self.hub.subskrybowane_watki()
        w = self.db.aktywnosc(wid, at=self.zegar(), podglad=podglad, nieprzeczytane_plus=0 if otwarty else 1)
        if w:
            self.hub.nadaj("watek.zmiana", {"watek": {k: w.get(k) for k in (
                "id", "tytul", "przypiety", "archiwum", "usuniety_at", "rodzaj", "kanal", "czlonkowie", "ostatni_agenci",
                "aktywnosc_at", "nieprzeczytane", "status", "podglad", "koordynator")}})

    def _notka_kompresji(self, wid: str, agent: str) -> None:
        w = self.db.dodaj_wpis(wid, rodzaj="system", tekst="Streszczenie wcześniejszej rozmowy",
                               dane={"typ": "kompresja", "agent": agent})
        self.hub.nadaj("watek.wpis", {"watek_id": wid, "wpis": w}, watek_id=wid)

    # ------------------------------------------------------------------------------------------- praca floty
    async def _praca_floty(self, teraz: float, zmiana_profili: bool) -> None:
        if self.prace is None:
            return
        s = _syg(self.pliki["kanban"])
        if s != self._karty_syg:
            self._karty_syg = s
            self._karty = await asyncio.to_thread(self.prace.karty_w_toku, self.pliki["kanban"])
        if zmiana_profili or teraz - self._dzierzawy_at >= DZIERZAWY_S:
            self._dzierzawy_at = teraz
            nasze = {(s["agent"], s["sesja_id"]) for s in self.db.sesje_czlonkow()}
            obce = []
            for agent in self.agenci.nazwy():
                for d in await asyncio.to_thread(self.czytnik.dzierzawy_profilu, agent, teraz):
                    if (agent, d["sesja_id"]) not in nasze:
                        obce.append({"agent": agent, "platforma": d["platforma"]})
            self._dzierzawy = obce
        aktywne = [p for p in self.db.przebiegi_aktywne()
                   if p["stan"] in ("wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie")]
        dane = self.prace.praca(aktywne, self._karty, self._dzierzawy, nazwy=self.agenci.nazwy_wyswietlane(), teraz=teraz)
        klucz = (dane["aktywne"], tuple(dane["opis"]))
        if klucz != self._praca or teraz - self._praca_at >= PRACA_ODSWIEZ_S:
            self._praca, self._praca_at = klucz, teraz
            try:
                await asyncio.to_thread(self.prace.zapisz, self.praca_json, dane)
            except OSError as exc:
                self.log(f"jarvo-hq: praca.json: {type(exc).__name__}")
        self.ostatnia_praca = dane
        await self._aktualizacja_po_pracy(teraz, int(dane["aktywne"]))

    async def _aktualizacja_po_pracy(self, teraz: float, aktywne: int) -> None:
        if not self.db.meta("aktualizacja_po_pracy"):
            self._zero_od = None
            return
        if aktywne:
            self._zero_od = None
            return
        if self._zero_od is None:
            self._zero_od = teraz
        if teraz - self._zero_od < PO_PRACY_CISZA_S:
            return
        self._zero_od = None
        stan = self.stan_aktualizacji() or {}
        if stan.get("state") != "updating":
            prosba = self.jarvo_dir / "state" / "update-request"
            try:
                await asyncio.to_thread(_zapisz_prosbe, prosba)
            except OSError as exc:
                self.log(f"jarvo-hq: aktualizacja po pracy: {type(exc).__name__}")
                return
            self.log("jarvo-hq: aktualizacja po pracy: prośba zapisana (30 s bez pracy)")
        self.db.usun_meta("aktualizacja_po_pracy")
        self.hub.nadaj("aktualizacja", self.stan_aktualizacji() or {})

    # ------------------------------------------------------------------------------------------- przypinanie, sprzątanie
    async def _przypnij(self) -> None:
        for s in self.db.sesje_czlonkow(nieprzypiete=True):
            await self.rejestr.przypnij(s["agent"], s["sesja_id"])

    async def _sprzataj(self, teraz: float) -> None:
        ostatnie = float(self.db.meta("sprzatanie_at", "0") or 0)
        if teraz - ostatnie < SPRZATANIE_S:
            return
        self.db.ustaw_meta("sprzatanie_at", repr(teraz))
        wynik = self.db.sprzataj()
        for s in wynik.get("do_odpiecia", []):
            try:
                await self.rejestr.brama.zmien_sesje(s["agent"], s["sesja_id"], pinned=False)
                self.db.ustaw_przypieta(s["agent"], s["sesja_id"], False)
            except Exception as exc:
                self.log(f"jarvo-hq: odpięcie sesji {s['agent']}: {type(exc).__name__}")
        if wynik.get("usuniete") or wynik.get("payload_wyzerowane"):
            self.log(f"jarvo-hq: sprzątanie: wątki {len(wynik['usuniete'])}, treści {wynik['payload_wyzerowane']}")

    def zdrowie(self) -> dict:
        return {"cykl_ms": self.cykl_ms, "bledy": self.bledy}
