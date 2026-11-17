"""Rozmówcy panelu w silniku (centrum §1, §3): lista z konfiguracji, stałe wątki, sesja tematu i stan co 2 s.

- **Lista**: `agenci.rozmowcy` (flota z `telegram_topic`, wpisy sesje.json z `panel.zaplecze = omp` przez
  `omp_sesje.rozmowcy`); temat Telegrama rozmówcy floty z `tematy.temat`. `synchronizuj` zapisuje ją w rozmowy.db
  (`zsynchronizuj_rozmowcow`: wątek na rozmówcę, zniknięty = Archiwum) przy starcie i co minutę.
- **Sesja tematu** (Hermes): bieżąca sesja bramy tematu zostaje sesją członka wątku (`przejecie`); nowa sesja tej
  samej trasy (`/new`, automatyczny reset) = `rotacja` i linia „Nowa sesja” na osi. Temat bez sesji: panel zaczyna
  `jarvo_r_<profil>` (przebiegi._sesja), a pierwsza sesja tematu dochodzi do rodowodu (D5).
- **Stan** (wspólny słownik): `pracuje | czeka | wolny | terminal | kolejka | offline`. Hermes z przebiegów wątku
  (zgoda albo pytanie `[[czeka-na-tak]]` = czeka); omp z `omp_sesje.stan` (blokada, dzierżawa, skrzynka). Zmiana
  idzie zdarzeniem `rozmowca.stan` w strumieniu (bez odpytywania przeglądarki); `czeka`/`kolejka` dłużej niż 2 min
  (D2: „nigdy ciche czekanie”) dostaje w zdarzeniu `powiadom: true` raz.
Testy: tests/test_rozmowcy.py.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

STANY = ("pracuje", "czeka", "wolny", "terminal", "kolejka", "offline")
AKTYWNE = ("wysylanie", "przyjety", "pracuje", "czeka_na_ture", "zatrzymywanie")
POWIADOM_PO_S = 120.0
SYNCHRONIZUJ_S = 60.0
TEMAT_S = 10.0


class Serwis:
    def __init__(self, *, db, agenci, hub, dane: Path | str, tematy, omp=None, czytnik=None,
                 log: Callable[[str], None] | None = None, zegar: Callable[[], float] = time.time):
        self.db, self.agenci, self.hub = db, agenci, hub
        self.dane = Path(dane)
        self.tematy, self.omp, self.czytnik = tematy, omp, czytnik
        self._pliki: dict[str, tuple | None | str] = {}
        self.log = log or (lambda _m: None)
        self.zegar = zegar
        self._lista: list[dict] = []
        self._stany: dict[str, dict] = {}
        self._powiadomione: set[str] = set()
        self._sync_at = 0.0
        self._temat_at = 0.0

    # ------------------------------------------------------------------------------------------- lista
    def konfiguracja(self) -> list[dict]:
        wpisy = []
        if self.omp is not None:
            try:
                wpisy = self.omp.rozmowcy(self.dane)
            except Exception as exc:                 # zły sesje.json nie psuje floty
                self.log(f"jarvo-hq: rozmówcy omp: {type(exc).__name__}")
        lista = self.agenci.rozmowcy(wpisy)
        for r in lista:
            if r["zaplecze"] == "hermes":
                t = self.tematy.temat(self.dane, r.get("temat") or "", r["nazwa"])
                r["czat"], r["watek_tg"] = t if t else ("", "")
        return lista

    def synchronizuj(self) -> dict:
        self._lista = self.konfiguracja()
        wynik = self.db.zsynchronizuj_rozmowcow(self._lista)
        self._sync_at = self.zegar()
        if wynik["nowe"] or wynik["usuniete"]:
            self.log(f"jarvo-hq: rozmówcy: nowi {len(wynik['nowe'])}, usunięci {len(wynik['usuniete'])}")
            self.hub.nadaj("rozmowcy.lista", {"rozmowcy": self.lista()})
        return wynik

    def lista(self) -> list[dict]:
        """Rozmówcy dla aplikacji (GET /rozmowcy, GET /app): konfiguracja + zapis w bazie + stan."""
        konfig = {r["klucz"]: r for r in self._lista}
        out = []
        for r in self.db.rozmowcy():
            k = konfig.get(r["klucz"], {})
            w = self.db.watek(r["watek_id"]) if r.get("watek_id") else None
            st = self._stany.get(r["klucz"], {})
            out.append({"klucz": r["klucz"], "nazwa": r["nazwa"], "nazwa_en": r["nazwa_en"] or r["nazwa"],
                        "opis": k.get("opis", ""), "opis_en": k.get("opis_en", ""), "zaplecze": r["zaplecze"],
                        "cel": r["cel"], "pokoj": k.get("pokoj", ""), "temat": bool(r.get("czat") and r.get("watek_tg")),
                        "lustro": bool(r["lustro"]), "kolejnosc": r["kolejnosc_wlasna"] if r["kolejnosc_wlasna"] is not None
                        else r["kolejnosc"], "potwierdzenia": bool(k.get("potwierdzenia")), "watek_id": r.get("watek_id"),
                        "stan": r["stan"], "stan_od": r.get("stan_od"), "czeka": st.get("czeka", 0),
                        "powod": st.get("powod") or k.get("blad") or "", "terminal_od": st.get("terminal_od"),
                        "nieprzeczytane": (w or {}).get("nieprzeczytane", 0), "podglad": (w or {}).get("podglad", ""),
                        "aktywnosc_at": (w or {}).get("aktywnosc_at")})
        return out

    # ------------------------------------------------------------------------------------------- sesja tematu
    def sesje_tematow(self) -> int:
        """Bieżąca sesja bramy każdego tematu → rodowód wątku rozmówcy; zwraca liczbę zmian."""
        zmiany = 0
        for r in self.db.rozmowcy():
            if r["zaplecze"] != "hermes" or not (r.get("czat") and r.get("watek_tg") and r.get("watek_id")):
                continue
            try:
                s = self.tematy.sesja_tematu(self.dane, r["cel"], r["czat"], r["watek_tg"])
            except ValueError:
                continue
            if not s:
                continue
            wid, agent, sid = r["watek_id"], r["cel"], s["session_id"]
            czl = self.db.zapewnij_czlonka(wid, agent)
            tip = czl.get("sesja_tip") or czl.get("sesja_id")
            if tip == sid or self.db.watek_sesji(agent, sid):
                continue
            rotacja = bool(tip and s.get("prev_session_id") == tip)
            try:
                self.db.ustaw_sesje(wid, agent, sid, powod="rotacja" if rotacja else "przejecie", rodzic=tip)
            except ValueError:
                continue
            if rotacja:
                self.db.dodaj_wpis(wid, rodzaj="system", tekst="Nowa sesja", dane={"typ": "nowa_sesja"},
                                   klucz=f"sesja:{sid}")
            zmiany += 1
        self._temat_at = self.zegar()
        return zmiany

    # ------------------------------------------------------------------------------------------- stan
    def _stan_hermes(self, r: dict) -> dict:
        przebiegi = self.db.przebiegi_watku(r["watek_id"], aktywne=True) if r.get("watek_id") else []
        if any(p["stan"] == "czeka_na_zgode" for p in przebiegi):
            return {"stan": "czeka"}
        if any(p["stan"] in AKTYWNE for p in przebiegi):
            return {"stan": "pracuje"}
        if przebiegi:
            return {"stan": "kolejka", "czeka": len(przebiegi)}
        # tura z tematu Telegrama (nie z panelu): ta sama sesja jest trzymana przez bramę = pracuje (stan niezależny
        # od kanału, z którego przyszło zlecenie)
        if self.czytnik is not None and r.get("watek_id"):
            rodowod = [s["sesja_id"] for s in self.db.sesje_watku(r["watek_id"], agent=r["cel"])]
            try:
                if rodowod and self.czytnik.dzierzawa(r["cel"], rodowod, self.zegar()):
                    return {"stan": "pracuje"}
            except (ValueError, RuntimeError):
                pass
        w = self.db.watek(r["watek_id"]) if r.get("watek_id") else None
        return {"stan": "czeka" if (w or {}).get("status") == "czeka" else "wolny"}

    def _stan_omp(self, r: dict, wpisy: dict) -> dict:
        w = wpisy.get(r["cel"])
        if w is None:
            return {"stan": "offline", "powod": "brak wpisu"}
        try:
            st = self.omp.stan(w)
        except Exception as exc:
            return {"stan": "offline", "powod": type(exc).__name__}
        return {"stan": st.get("stan") if st.get("stan") in STANY else "offline", "czeka": int(st.get("czeka") or 0),
                "powod": st.get("powod") or "", "terminal_od": st.get("terminal_od")}

    def stany(self) -> list[dict]:
        """Jedna runda stanów (wątek tła silnika co 2 s); zmiany idą zdarzeniem `rozmowca.stan`."""
        teraz = self.zegar()
        if teraz - self._sync_at >= SYNCHRONIZUJ_S:
            self.synchronizuj()
        if teraz - self._temat_at >= TEMAT_S:
            self.sesje_tematow()
        wpisy: dict[str, Any] = {}
        if self.omp is not None:
            try:
                wpisy = self.omp.wpisy(self.dane)
            except Exception:
                wpisy = {}
        zmienione = []
        for r in self.db.rozmowcy():
            st = self._stan_omp(r, wpisy) if r["zaplecze"] == "omp" else self._stan_hermes(r)
            if r["zaplecze"] == "omp" and r.get("watek_id") and r["cel"] in wpisy:
                self._os_omp(r, wpisy[r["cel"]])
            stary = self._stany.get(r["klucz"])
            self._stany[r["klucz"]] = st
            if r["stan"] != st["stan"]:
                r = self.db.zmien_rozmowce(r["klucz"], stan=st["stan"])
                self._powiadomione.discard(r["klucz"])
            powiadom = False
            if st["stan"] in ("czeka", "kolejka") and r["klucz"] not in self._powiadomione \
                    and teraz - float(r.get("stan_od") or teraz) >= POWIADOM_PO_S:
                self._powiadomione.add(r["klucz"])
                powiadom = True
            if stary != st or powiadom:
                zdarzenie = {"klucz": r["klucz"], "stan": st["stan"], "stan_od": r.get("stan_od"),
                             "czeka": st.get("czeka", 0), "powod": st.get("powod") or "",
                             "terminal_od": st.get("terminal_od"), "powiadom": powiadom}
                self.hub.nadaj("rozmowca.stan", zdarzenie)
                zmienione.append(zdarzenie)
        return zmienione

    def _os_omp(self, r: dict, w) -> None:
        """Plik sesji omp urósł (tura z Telegrama, terminala albo panelu): oś wątku na żywo (`watek.os`) i aktywność
        wątku (nieprzeczytane, gdy nikt go nie ogląda). Pierwszy odczyt po starcie tylko zapamiętuje rozmiar."""
        try:
            plik = self.omp.plik_sesji(w)
            s = plik.stat() if plik else None
        except OSError:
            s = None
        syg = (s.st_mtime_ns, s.st_size) if s else None
        stara = self._pliki.get(r["klucz"], "start")
        self._pliki[r["klucz"]] = syg
        if stara == "start" or syg is None or syg == stara:
            return
        wid = r["watek_id"]
        otwarty = wid in self.hub.subskrybowane_watki()
        w_ = self.db.aktywnosc(wid, at=s.st_mtime_ns / 1e9, nieprzeczytane_plus=0 if otwarty else 1)
        self.hub.nadaj("watek.os", {"watek_id": wid, "agent": r["klucz"]}, watek_id=wid)
        if w_:
            self.hub.nadaj("watek.zmiana", {"watek": {k: w_.get(k) for k in ("id", "aktywnosc_at", "nieprzeczytane",
                                                                               "status", "podglad")}})
