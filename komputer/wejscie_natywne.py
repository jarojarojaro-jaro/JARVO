"""Wejście Komputera natywnie (docs/NATYWNIE.md J04, J09): jedyna droga floty do przeglądarki Jarva.

Rdzeń jest ten sam co w kontenerze (`infra/komputer/wejscie.py`: sesja MCP, kontrola protokołu, migawki tej sesji,
świeża migawka przed działaniem na element, ukrywanie sekretów, dziennik bez treści, limit działań, jedna sesja przy
ekranie naraz) i te same twarde zasady (`infra/komputer/zasady.py`) z zasadami natywnymi przed nimi
(`zasady_natywne.py`). Inne są trzy rzeczy:
  - kontekst zasad to KontekstCDP: element, punkt i fokus opisuje na żywo sterownik CDP (zamiast AT-SPI i X11);
  - sterownik działa w tym samym procesie (sterownik_cdp.Sterownik), więc wiadomość MCP po ocenie idzie do niego
    przez kolejkę sesji, a odpowiedź wraca tą samą drogą co w kontenerze (ukrywanie sekretów, migawki);
  - kanały to potok nazwany z DACL właściciela albo gniazdo 0600 (komputer/kanal.py), a wznowienie po pauzie
    i polecenia usługi (stop, okno, wyczyść) wymagają tokenu właściciela z `<stan>/komputer/wlasciciel.klucz`
    (`jarvo komputer wznow`, HQ po zalogowaniu). Token przeczyta każdy proces właściciela, także agent z pełnym
    terminalem: to granica wobec Operatora (bez terminala) i wobec stron, nie wobec właściciela.
Działanie agenta zasady oceniają dopiero, gdy sterownik skończył poprzednie wywołanie tej sesji (wiadomości wysłane
jedna za drugą bez czekania na wynik nie ocenią fokusu sprzed kliknięcia, które jeszcze czeka w kolejce).

Ekran w HQ (J10), polecenia kanału `ster` z tokenem właściciela:
  klatka    ostatnia klatka podglądu aktywnej karty (Page.startScreencast, JPEG w base64); `po` = numer klatki,
            którą HQ już ma (czeka do `czekaj` s na nowszą), `jakosc`, `maks` (px dłuższego boku)
  przejmij  pauza właściciela „przejął ekran w HQ”: agent patrzy, ale nie działa
  wejscie   działanie właściciela w aktywnej karcie przez CDP Input.* (sterownik_cdp.wejscie_wlasciciela), bez
            twardych zasad; tylko przy pauzie właściciela (po `przejmij` albo `jarvo komputer pauza`)
  wznow     „Oddaj” w HQ: zdejmuje pauzę, agent zaczyna od nowego stanu okna
W dzienniku zostaje przejęcie, oddanie i rodzaj każdego działania właściciela (bez tekstu, adres tylko z nazwą
serwera); ruchy myszy i kółko bez wpisów.
"""
from __future__ import annotations

import hmac
import json
import os
import queue
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

_INFRA = Path(__file__).resolve().parent.parent / "infra" / "komputer"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))
import wejscie  # noqa: E402  (infra/komputer/wejscie.py: rdzeń sesji bez zmian)
import zasady  # noqa: E402

from . import kanal, zasady_natywne  # noqa: E402

MAKS_DZIENNIK = 2 << 20
MAKS_SESJE = wejscie.MAKS_SESJE
CZAS_KOLEJKI = 60.0               # s czekania na koniec poprzedniego wywołania sesji, zanim zasady ocenią następne
TYLKO_WLASCICIEL = ("wznow", "stop", "okno", "wyczysc", "restart", "klatka", "przejmij", "wejscie")
POWOD_PRZEJECIA = "przejął ekran w HQ"
BEZ_WPISU = ("mysz", "kolko")     # działania właściciela bez wpisu w dzienniku (ruch myszy, przewijanie)


def log(*a: object) -> None:
    if sys.stderr is not None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [wejście]", *a, file=sys.stderr, flush=True)


wejscie.log = log                                 # komunikaty rdzenia w tym samym dzienniku usługi


class DziennikNatywny:
    """Dziennik decyzji (`<dane>/jarvo/komputer/dziennik.jsonl`, 2 MB i jedna kopia), ten sam format co w kontenerze."""

    def __init__(self, sciezka: Path) -> None:
        self.sciezka = Path(sciezka)
        self._lock = threading.Lock()
        self.ostatnie: deque = deque(maxlen=200)
        self.sciezka.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.sciezka, encoding="utf-8") as f:
                for linia in deque(f, maxlen=200):
                    try:
                        self.ostatnie.append(json.loads(linia))
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass

    def zapisz(self, wpis: dict) -> None:
        wpis = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), **wpis}
        with self._lock:
            self.ostatnie.append(wpis)
            try:
                if self.sciezka.exists() and self.sciezka.stat().st_size > MAKS_DZIENNIK:
                    os.replace(self.sciezka, self.sciezka.with_name(self.sciezka.name + ".1"))
                with open(self.sciezka, "a", encoding="utf-8") as f:
                    f.write(json.dumps(wpis, ensure_ascii=False) + "\n")
            except OSError as e:
                log("dziennik:", e)


class _Dostepnosc:
    """Zastępstwo AT-SPI z kontenera: drzewo dostępności daje przeglądarka (CDP), więc „działa”, gdy ona działa."""

    def __init__(self, wej: "WejscieNatywne") -> None:
        self._wej = wej

    @property
    def dziala(self) -> bool:
        s = self._wej.sterownik
        return bool(s is not None and s.b.dziala())


class EkranNatywny(wejscie.Ekran):
    """Pauza (z autorem i powodem), sesja przy ekranie i limit działań; pauza w `<dane>/jarvo/komputer/pauza`."""

    def __init__(self, wej: "WejscieNatywne", plik_pauzy: Path) -> None:
        self.dostepnosc = _Dostepnosc(wej)
        self.x11 = None
        self.plik_pauzy = Path(plik_pauzy)
        self.pauza = self._wczytaj()
        self._dzialania: deque = deque()
        self._zajete = None
        self._lock = threading.Lock()

    def _wczytaj(self) -> dict | None:
        try:
            tresc = self.plik_pauzy.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            return {"kto": "wlasciciel", "powod": ""}     # nieczytelny plik pauzy: dalej pauza
        try:
            stan = json.loads(tresc)
        except json.JSONDecodeError:
            stan = None
        if not isinstance(stan, dict):
            return {"kto": "wlasciciel", "od": tresc.strip()[:40], "powod": ""}
        return {"kto": str(stan.get("kto") or "wlasciciel"), "od": str(stan.get("od") or ""),
                "powod": wejscie.czysty_powod(stan.get("powod"))}

    def ustaw_pauze(self, tak: bool, powod: str = "", kto: str = "wlasciciel") -> None:
        if tak:
            stan = {"kto": kto, "od": datetime.now(timezone.utc).isoformat(), "powod": wejscie.czysty_powod(powod)}
            self.plik_pauzy.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.plik_pauzy.with_name(self.plik_pauzy.name + ".tmp")
            tmp.write_text(json.dumps(stan, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, self.plik_pauzy)
            self.pauza = stan
        else:
            try:
                self.plik_pauzy.unlink()
            except FileNotFoundError:
                pass
            self.pauza = None


class KontekstCDP(wejscie.KontekstSesji):
    """zasady.Kontekst jednej sesji MCP: migawki tej sesji (rdzeń) + opis celu, punktu i fokusu na żywo z CDP."""

    def __init__(self, ekran: EkranNatywny, wej: "WejscieNatywne") -> None:
        super().__init__(ekran)
        self._wej = wej

    @property
    def sterownik(self):
        return self._wej.sterownik

    def _skala(self, args: dict, sc: dict) -> None:
        """Skalę zrzutu zna sterownik (ta sama dla zasad i kliknięcia), więc kontekst jej nie liczy."""

    def _nr_okna(self, args: dict):
        nr = args.get("window_id")
        return nr if nr is not None else (self.sterownik.aktywne_okno() if self.sterownik else None)

    def cel(self, nazwa: str, args: dict) -> dict | None:
        s = self.sterownik
        if s is None:
            return zasady.NIEZNANY
        cel = args.get("target") if isinstance(args.get("target"), dict) else {}
        token = args.get("element_token") or cel.get("element_token")
        if token:
            sid, _, indeks = str(token).rpartition(":")
            return s.opis_elementu(sid, indeks) or zasady.NIEZNANY
        indeks = args.get("element_index", cel.get("element_index"))
        if indeks is not None:
            return s.opis_elementu(str(args.get("snapshot_id") or cel.get("snapshot_id") or ""), indeks) \
                or zasady.NIEZNANY
        x, y = args.get("x", cel.get("x")), args.get("y", cel.get("y"))
        if x is not None and y is not None:
            if args.get("scope") == "desktop":
                return zasady.NIEZNANY
            pid = args.get("pid")
            if pid is not None and pid != s.pid:
                return zasady.NIEZNANY
            return s.opis_w_punkcie(self._nr_okna(args), x, y) or zasady.NIEZNANY
        return None

    def fokus(self, args: dict) -> dict | None:
        s = self.sterownik
        if s is None:
            return zasady.NIEZNANY
        wynik = s.fokus(self._nr_okna(args))
        return zasady.NIEZNANY if wynik is False else wynik

    def program(self, pid: int) -> str:
        return zasady.PROGRAM_PRZEGLADARKI if self.sterownik is not None and pid == self.sterownik.pid else ""

    def aktywne_okno(self) -> int | None:
        return self.sterownik.aktywne_okno() if self.sterownik is not None else None

    def pid_okna(self, okno: int) -> int | None:
        s = self.sterownik
        return s.pid if s is not None and s.okno(okno) is not None else None


class SesjaNatywna(wejscie.Sesja):
    """Jedno połączenie z kanałem `cua`: agent ↔ zasady (rdzeń z kontenera) ↔ sterownik CDP w tym procesie."""

    def __init__(self, strumien, wej: "WejscieNatywne") -> None:
        super().__init__(strumien, wej)
        self.ctx = KontekstCDP(wej.ekran, wej)
        self._kolejka: queue.Queue = queue.Queue()
        self._pracownik: threading.Thread | None = None
        self._konfig: dict = {"capture_scope": "window", "capture_mode": "som", "max_image_dimension": None}
        self._w_toku = 0                              # wiadomości w kolejce sterownika i ta w obsłudze
        self._bezczynny = threading.Condition()

    def do_sterownika(self, wiadomosc: dict) -> None:
        if self._pracownik is None:
            self._pracownik = threading.Thread(target=self._pracuj, daemon=True, name=f"sterownik-{self.nr}")
            self._pracownik.start()
        with self._bezczynny:
            self._w_toku += 1
        self._kolejka.put(wiadomosc)

    def _pracuj(self) -> None:
        while True:
            msg = self._kolejka.get()
            if msg is None:
                return
            sterownik = self.wejscie.sterownik
            try:
                if sterownik is None:
                    raise RuntimeError("przeglądarka Jarva właśnie startuje")
                odp = sterownik.obsluz_mcp(msg, self._konfig)
            except Exception as e:  # noqa: BLE001 - błąd sterownika to błąd wywołania, nie koniec sesji
                odp = None if msg.get("id") is None else {
                    "jsonrpc": "2.0", "id": msg.get("id"),
                    "error": {"code": -32603, "message": f"sterownik Komputera: {type(e).__name__}: {str(e)[:200]}"}}
            try:
                if odp is not None:
                    self._z_sterownika(odp)
            finally:
                with self._bezczynny:
                    self._w_toku -= 1
                    self._bezczynny.notify_all()

    def _czekaj_na_sterownik(self) -> bool:
        """Czeka, aż sterownik skończy wszystko, co ta sesja już mu wysłała (False po CZAS_KOLEJKI s)."""
        with self._bezczynny:
            return self._bezczynny.wait_for(lambda: self._w_toku <= 0, CZAS_KOLEJKI)

    def _z_sterownika(self, msg: dict) -> None:
        """Odpowiedź sterownika: zapytanie wejścia (świeża migawka) do niego, reszta przez ukrywanie do agenta."""
        if isinstance(msg.get("id"), str) and msg["id"].startswith(wejscie.WEWNETRZNE) and (
                "result" in msg or "error" in msg):
            with self._wewn_lock:
                czeka = self._wewn.get(msg["id"])
                if czeka is not None:
                    czeka[1] = msg
                    czeka[0].set()
            return
        if "id" in msg and ("result" in msg or "error" in msg):
            msg = self._po_odpowiedzi(msg)
        self.do_agenta(msg)

    def _ocen(self, nazwa: str, args) -> zasady.Werdykt:
        # zasady patrzą na stronę po poprzednim działaniu, a nie przed nim (np. klik w pole hasła jeszcze w kolejce)
        if nazwa in zasady.DZIALANIA and not self._czekaj_na_sterownik():
            return zasady.Werdykt(zasady.ODMOWA, "zajete", "poprzednie działanie jeszcze trwa; poczekaj na jego "
                                  "wynik i spróbuj znowu")
        try:
            w = zasady_natywne.ocen(nazwa, args, self.ctx)
        except Exception as e:  # noqa: BLE001 - błąd zasady to odmowa, nigdy przepuszczenie
            log(f"sesja {self.nr}: błąd zasady natywnej dla {nazwa}: {e!r}")
            return zasady.Werdykt(zasady.ODMOWA, "blad_zasady", "wewnętrzny błąd zasad; działanie wstrzymane")
        if w is not None:
            return w
        return super()._ocen(nazwa, args)

    def zamknij(self) -> None:
        # agent mógł wysłać wszystko i zamknąć swoją stronę: odpowiedzi na wiadomości w kolejce jeszcze do niego idą
        self._kolejka.put(None)
        if self._pracownik is not None and self._pracownik is not threading.current_thread():
            self._pracownik.join(timeout=30)
        super().zamknij()


class WejscieNatywne:
    """Kanały `cua` (sesje MCP) i `ster` (stan, pauza, wznowienie, dziennik, polecenia usługi)."""

    def __init__(self, katalog_danych: Path, token: str,
                 polecenie_uslugi: Callable[[str, dict], dict] | None = None) -> None:
        self.sterownik = None                      # ustawia usługa po starcie (i po restarcie) przeglądarki
        self.dziennik = DziennikNatywny(Path(katalog_danych) / "dziennik.jsonl")
        self.ekran = EkranNatywny(self, Path(katalog_danych) / "pauza")
        self.sesje: set = set()
        self._lock = threading.Lock()
        self.srodowisko: dict = {}
        self._token = token
        self.polecenie_uslugi = polecenie_uslugi or (lambda _co, _p: {"ok": False, "blad": "brak usługi"})

    def koniec_sesji(self, sesja) -> None:
        self.ekran.zwolnij(sesja.nr)
        with self._lock:
            if sesja in self.sesje:
                self.sesje.discard(sesja)
                log(f"sesja {sesja.nr}: koniec")

    def obsluz_cua(self, strumien) -> None:
        with self._lock:
            if len(self.sesje) >= MAKS_SESJE:
                strumien.close()
                return
            sesja = SesjaNatywna(strumien, self)
            self.sesje.add(sesja)
        log(f"sesja {sesja.nr}: start (PID klienta {kanal.pid_klienta(strumien)})")
        sesja.obsluz()

    def wlasciciel(self, polecenie: dict) -> bool:
        token = polecenie.get("token")
        return isinstance(token, str) and bool(self._token) and hmac.compare_digest(token, self._token)

    def stan(self) -> dict:
        odp = {"ok": True, "wstrzymane": self.ekran.wstrzymane, "sesje": len(self.sesje),
               "atspi": self.ekran.dostepnosc.dziala, "cdp": self.ekran.dostepnosc.dziala}
        if self.ekran.pauza:
            odp["pauza"] = dict(self.ekran.pauza, opis=self.ekran.powod_pauzy)
            odp["przejete"] = self.ekran.pauza.get("kto") == "wlasciciel" and \
                self.ekran.pauza.get("powod") == POWOD_PRZEJECIA
        return odp

    def obsluz_ster(self, strumien) -> None:
        try:
            strumien.settimeout(5)
            try:
                polecenie = json.loads(kanal.czytaj_wiersz(strumien, 1 << 16) or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                polecenie = {}
            polecenie = polecenie if isinstance(polecenie, dict) else {}
            odp = self.polecenie(polecenie, kanal.pid_klienta(strumien))
            strumien.sendall((json.dumps(odp, ensure_ascii=False) + "\n").encode("utf-8"))
        except OSError:
            pass
        finally:
            strumien.close()

    def polecenie(self, polecenie: dict, pid: int | None = None) -> dict:
        co = polecenie.get("polecenie")
        wlasciciel = self.wlasciciel(polecenie)
        if co in TYLKO_WLASCICIEL and not wlasciciel:
            if co != "klatka":                        # podgląd pyta co chwilę: bez zapychania dziennika
                self.dziennik.zapisz({"narzedzie": "ster", "decyzja": "odmowa", "zasada": f"{co}_bez_tokenu",
                                      "pid": pid})
            return {"ok": False, "wstrzymane": self.ekran.wstrzymane,
                    "blad": "to polecenie wydaje tylko właściciel: jarvo komputer " + str(co)
                    if co not in ("klatka", "przejmij", "wejscie") else
                    f"{co}: tylko właściciel (Ekran w HQ po zalogowaniu)"}
        if co == "pauza":
            # pauza od floty to prośba Operatora do właściciela; pauzy właściciela flota nie nadpisze swoją
            kto = "wlasciciel" if wlasciciel else "flota"
            if not (kto == "flota" and self.ekran.pauza and self.ekran.pauza["kto"] == "wlasciciel"):
                self.ekran.ustaw_pauze(True, polecenie.get("powod", ""), kto)
            self.dziennik.zapisz({"narzedzie": "ster", "decyzja": "pauza", "kto": kto})
            return self.stan()
        if co == "wznow":
            self.ekran.ustaw_pauze(False)
            self.dziennik.zapisz({"narzedzie": "ster", "decyzja": "wznow"})
            return self.stan()
        if co == "przejmij":
            # prośbę Operatora (pauza floty) przejęcie zastępuje: teraz ekran ma właściciel, a wraca „Oddaj” (wznow)
            self.ekran.ustaw_pauze(True, POWOD_PRZEJECIA, "wlasciciel")
            self.dziennik.zapisz({"narzedzie": "ster", "decyzja": "przejmij", "kto": "wlasciciel"})
            return self.stan()
        if co == "klatka":
            return self._klatka(polecenie)
        if co == "wejscie":
            return self._wejscie_wlasciciela(polecenie)
        if co == "stan":
            odp = self.stan()
            try:
                odp["usluga"] = self.polecenie_uslugi("stan", polecenie)
            except Exception:  # noqa: BLE001 - stan usługi to dodatek; stan wejścia odpowiada zawsze
                pass
            return odp
        if co == "dziennik":
            n = polecenie.get("n", 50)
            n = n if isinstance(n, int) and not isinstance(n, bool) and 0 < n <= 200 else 50
            return {"ok": True, "wpisy": list(self.dziennik.ostatnie)[-n:]}
        if co in ("stop", "okno", "wyczysc", "restart"):
            self.dziennik.zapisz({"narzedzie": "ster", "decyzja": co})
            return self.polecenie_uslugi(co, polecenie)
        return {"ok": False, "blad": "polecenia: stan, pauza, wznow, dziennik (właściciel: stop, okno, wyczysc, "
                                     "klatka, przejmij, wejscie)"}

    @staticmethod
    def _liczba(wartosc, domyslna=None):
        return wartosc if isinstance(wartosc, (int, float)) and not isinstance(wartosc, bool) else domyslna

    def _klatka(self, p: dict) -> dict:
        s = self.sterownik
        if s is None:
            return {"ok": False, "blad": "przeglądarka Jarva właśnie startuje"}
        po = p.get("po") if isinstance(p.get("po"), int) and not isinstance(p.get("po"), bool) else None
        jakosc, maks = p.get("jakosc"), p.get("maks")
        k = s.podglad(po=po, czekaj=self._liczba(p.get("czekaj"), 1.0),
                      jakosc=jakosc if isinstance(jakosc, int) and not isinstance(jakosc, bool) else None,
                      maks=maks if isinstance(maks, int) and not isinstance(maks, bool) else None)
        if k is None:
            return {"ok": False, "blad": "przeglądarka nie ma otwartej karty albo nie dała obrazu"}
        return {"ok": True, "klatka": k, "wstrzymane": self.ekran.wstrzymane,
                "przejete": bool(self.ekran.pauza and self.ekran.pauza.get("kto") == "wlasciciel")}

    def _wejscie_wlasciciela(self, p: dict) -> dict:
        """Działanie właściciela w aktywnej karcie (HQ, „Przejmij”): tylko przy jego pauzie, żeby agent i właściciel
        nie klikali naraz. W dzienniku rodzaj działania bez treści (adres tylko z nazwą serwera)."""
        if not (self.ekran.pauza and self.ekran.pauza.get("kto") == "wlasciciel"):
            return {"ok": False, "wstrzymane": self.ekran.wstrzymane,
                    "blad": "najpierw przejmij ekran (polecenie przejmij albo jarvo komputer pauza): agent i "
                            "właściciel nie działają naraz"}
        s = self.sterownik
        if s is None:
            return {"ok": False, "blad": "przeglądarka Jarva właśnie startuje"}
        z = p.get("zdarzenie") if isinstance(p.get("zdarzenie"), dict) else {}
        wynik = s.wejscie_wlasciciela(z)
        typ = str(z.get("typ") or "")
        if typ not in BEZ_WPISU:
            wpis = {"narzedzie": "wlasciciel", "decyzja": "wejscie" if wynik.get("ok") else "blad", "typ": typ[:20]}
            if typ == "adres":
                wpis["cel"] = (urlsplit(str(z.get("url") or "")).hostname or "")[:100]
            elif typ == "tekst":
                wpis["znaki"] = len(str(z.get("tekst") or ""))
            elif typ == "klawisz":
                # pojedynczy znak bez Ctrl, Alt i Cmd to pisanie (np. hasło znak po znaku): w dzienniku tylko „znak”
                mody = [str(m).strip().lower()[:10] for m in (z.get("modyfikatory") or [])][:4]
                klawisz = str(z.get("klawisz") or "")
                skrot = set(mody) & {"ctrl", "control", "alt", "option", "cmd", "command", "meta", "super", "win"}
                wpis["klawisze"] = "znak" if len(klawisz) == 1 and not skrot else "+".join([*mody, klawisz[:20]])
            self.dziennik.zapisz(wpis)
        return wynik
