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
- **Raporty rutyn** (`raporty`, z archiwum Aktualizacji): rutyna z `attach_to_session` trafia do sesji tematu
  lustrem Hermesa (`[Cron delivery: …]`, oś: `rutyna`). Temat bez trasy bramy (nikt w nim jeszcze nie pisał) nie ma
  sesji, więc lustro przepada; wtedy raport rozmówcy floty (bez koordynatora, temat General) idzie do jego wątku jako
  wpis systemu `{typ: rutyna, agent, nazwa}` (oś: ta sama pozycja `rutyna`), raz na raport (klucz `raport:<id>`),
  z aktywnością i nieprzeczytanymi jak odpowiedź agenta.
Testy: tests/test_rozmowcy.py.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

STANY = ("pracuje", "czeka", "wolny", "terminal", "kolejka", "offline")
AKTYWNE = ("wysylanie", "przyjety", "pracuje", "czeka_na_ture", "zatrzymywanie")
POWIADOM_PO_S = 120.0
SYNCHRONIZUJ_S = 60.0
TEMAT_S = 10.0


class Serwis:
    def __init__(self, *, db, agenci, hub, dane: Path | str, tematy, omp=None, czytnik=None, czytnik_omp=None,
                 log: Callable[[str], None] | None = None, zegar: Callable[[], float] = time.time):
        self.db, self.agenci, self.hub = db, agenci, hub
        self.dane = Path(dane)
        self.tematy, self.omp, self.czytnik, self.czytnik_omp = tematy, omp, czytnik, czytnik_omp
        self._pliki: dict[str, tuple] = {}             # klucz → (sygnatura pliku sesji omp, odpowiedzi w nim)
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

    # ------------------------------------------------------------------------------------------- raporty rutyn
    def _lustro_hermesa(self, r: dict) -> bool:
        """Raport z `attach_to_session` jest już na osi wątku: temat ma trasę bramy, a jej sesja należy do tego wątku
        albo jeszcze do żadnego (`sesje_tematow` przejmie ją w ciągu TEMAT_S)."""
        if not (r.get("czat") and r.get("watek_tg")):
            return False
        try:
            s = self.tematy.sesja_tematu(self.dane, r["cel"], r["czat"], r["watek_tg"])
        except ValueError:
            return False
        if not s:
            return False
        gdzie = self.db.watek_sesji(r["cel"], s["session_id"])
        return gdzie is None or gdzie[0] == r["watek_id"]

    def raporty(self, raporty: Iterable[Mapping]) -> int:
        """Raporty rutyn (raporty.Archiwum: {id, profil, nazwa, ts, tekst, blad}) do wątków rozmówców floty, gdy lustro
        Hermesa nie miało dokąd trafić. Zwraca liczbę dodanych wpisów."""
        rozmowcy = {r["profil"]: r for r in self._lista
                    if r.get("zaplecze") == "hermes" and r.get("profil") and r.get("temat") != "general"}
        dodane = 0
        for rap in sorted(raporty, key=lambda x: float(x["ts"])):
            k = rozmowcy.get(rap.get("profil"))
            r = self.db.rozmowca(k["klucz"]) if k else None
            if not r or not r.get("watek_id") or r.get("usuniety_at") or self._lustro_hermesa(r):
                continue
            wid = r["watek_id"]
            ostatni = self.db.wpisy(wid, limit=1)            # czas rośnie z `seq`: oś scala wpisy po czasie
            at = max([float(rap["ts"])] + [float(w["utworzony_at"]) for w in ostatni])
            profil, zadanie, stem = str(rap["id"]).split("/", 2)
            w = self.db.dodaj_wpis(wid, rodzaj="system", tekst=rap["tekst"], klucz=f"raport:{rap['id']}", at=at,
                                   dane={"typ": "rutyna", "agent": r["cel"], "nazwa": rap["nazwa"],
                                         "blad": bool(rap.get("blad")),
                                         "plik": str(self.dane / "profiles" / profil / "cron" / "output" / zadanie
                                                     / f"{stem}.md")})
            if w.get("powtorzony"):
                continue
            dodane += 1
            self.hub.nadaj("watek.os", {"watek_id": wid, "agent": r["cel"]}, watek_id=wid)
            otwarty = wid in self.hub.subskrybowane_watki()
            w_ = self.db.aktywnosc(wid, at=at, nieprzeczytane_plus=0 if otwarty else 1,
                                   podglad=f"{r['nazwa']} · {rap['nazwa']}: {' '.join(rap['tekst'].split())[:120]}")
            if w_:
                self.hub.nadaj("watek.zmiana", {"watek": {k_: w_.get(k_) for k_ in (
                    "id", "aktywnosc_at", "nieprzeczytane", "status", "podglad")}})
        if dodane:
            self.log(f"jarvo-hq: raporty rutyn w wątkach rozmówców: {dodane}")
        return dodane

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
        """Plik sesji omp urósł (tura z Telegrama, terminala albo panelu, także każdy krok narzędzia): oś wątku na żywo
        (`watek.os`). Aktywność i nieprzeczytane tylko o nowe odpowiedzi kończące turę spoza panelu
        (`czytnik_omp.odpowiedzi`; turę z panelu liczy koniec przebiegu), więc tura z dwudziestoma krokami to jedna
        wiadomość. Pierwszy odczyt po starcie i nowy plik sesji (inna ścieżka albo i-węzeł) tylko zapamiętują stan."""
        try:
            plik = self.omp.plik_sesji(w)
            s = plik.stat() if plik else None
        except OSError:
            s = None
        syg = (str(plik), s.st_ino, s.st_mtime_ns, s.st_size) if s else None
        stara = self._pliki.get(r["klucz"])
        if stara is not None and stara[0] == syg:
            return
        n = self.czytnik_omp.odpowiedzi(plik) if syg and self.czytnik_omp is not None else None
        self._pliki[r["klucz"]] = (syg, n)
        if stara is None or syg is None:
            return
        wid = r["watek_id"]
        self.hub.nadaj("watek.os", {"watek_id": wid, "agent": r["klucz"]}, watek_id=wid)
        syg0, n0 = stara
        ten_sam = syg0 is not None and syg0[:2] == syg[:2]
        nowe = n - n0 if ten_sam and n is not None and n0 is not None else 0
        if nowe <= 0:
            return
        otwarty = wid in self.hub.subskrybowane_watki()
        w_ = self.db.aktywnosc(wid, at=s.st_mtime_ns / 1e9, nieprzeczytane_plus=0 if otwarty else nowe)
        if w_:
            self.hub.nadaj("watek.zmiana", {"watek": {k: w_.get(k) for k in ("id", "aktywnosc_at", "nieprzeczytane",
                                                                               "status", "podglad")}})
