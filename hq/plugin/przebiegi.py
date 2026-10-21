"""Rejestr przebiegów aplikacji Jarvo (docs/HQ.md „Rozmowy”): maszyna stanów jednej tury agenta zleconej przez
aplikację (`POST /v1/runs`), dyspozytor kolejki, słuchacz zdarzeń, odpytywanie stanu, strażnik.

Stany (nazwy dokładnie jak w `przebiegi.stan`): `kolejka` (powód `start` | `zajety_agent` | `tura` | `limit` |
`brama` | `wstrzymane` | `misja`), `wysylanie`, `przyjety`, `pracuje`, `czeka_na_ture`, `czeka_na_zgode`,
`zatrzymywanie`, `dopisany`; końcowe `gotowe`, `blad`, `zatrzymane`, `przerwane`, `zgubione`, `anulowane`,
`wlaczony`. `odlaczony` to flaga (strumień zgubiony, odpytujemy stan co 2 s), nie stan.

- **Dyspozytor** (budzony przy zleceniu, końcu przebiegu, zmianie state.db, co 2 s): FIFO; jeden aktywny przebieg
  na sesję członka (`zajety_agent`); sesja zajęta cudzą turą (budzenie, Telegram, inny klient) = przebieg czeka
  lokalnie w `kolejka(tura)` i nie zajmuje miejsca w bramie; limit globalny `JARVO_HQ_MAX_PRZEBIEGOW` (domyślnie
  liczba procesorów + 1, najwyżej 8: tury `/v1/runs`, budzenia z kanbana, zakładanie i przypinanie sesji oraz
  streszczenia kompresji dzielą domyślną pulę wątków bramy `min(32, cpu + 4)`, trzy wątki zostają wolne; tury
  Telegrama i porządki bramy mają własne pule) liczy stany od `wysylanie` do `zatrzymywanie`. `wstrzymane`
  i `misja` zdejmuje tylko „Wyślij teraz” (runda nie nadpisze ich starym wierszem); przebieg wątku w koszu
  dyspozytor anuluje. Przy pierwszej próbie: blok kontekstu z wątku takiego, jaki jest teraz,
  `payload.tekst` i `payload_sha`, `widzial_at` członka; sesja członka (deterministyczne id `jarvo_<wątek>_<agent>`)
  tworzona i przypinana w Hermesie, gdy jej nie ma; `sesja_id` i `cialo_sha` zapisane PRZED wysłaniem.
- **Wysyłka**: 202 → `przyjety` i słuchacz; 429 → `kolejka(limit)` (Retry-After + 0–0,5 s; po 10 min w kolejce
  od pierwszego 429 `blad(limit_bramy)`; próba spóźniona o ponad 60 s względem Retry-After liczy budżet od nowa);
  brak bramy → `kolejka(brama)` z odstępem 1, 2, 4, 8, 16, 30 s (po 120 s `blad`, 300 s przy młodej bramie, bez
  limitu w trakcie aktualizacji); 401/403 → `blad(klucz)`; 400/404/413/422 → `blad(odrzucone)`; 409
  `idempotency_key_conflict` → zostaje `wysylanie` i czeka na nasz wiersz w state.db (najwyżej 60 s), potem tura
  „tylko z osi czasu” bez `run_id` (`pracuje`, po Stopie `zatrzymywanie`; koniec: wolna dzierżawa i odpowiedź). Stop
  w `wysylanie` + błąd wysyłki = `zatrzymane` bez ponowienia (gdy POST mógł dotrzeć: jedno ponowienie tym samym
  kluczem i ciałem, brama zwraca istniejący przebieg, i od razu stop). 202 dla usuniętego albo skończonego
  przebiegu = stop w bramie (praca nie zostaje bez właściciela).
- **Nasza tura** = nasz wiersz użytkownika w rodowodzie członka (skrót `payload_sha`, czas ≥ `wyslany_at − 2 s`):
  `przyjety`/`czeka_na_ture` → `pracuje` i `user_msg_id`. Bez wiersza, bez zdarzeń przez 5 s i z cudzą dzierżawą →
  `czeka_na_ture`.
- **Zgoda**: `approval.request` → `czeka_na_zgode` z `wygasa_at` = czas zdarzenia + `approvals.timeout` profilu; po
  czasie `zgoda.wygasla` i `pracuje` (brama dalej mówi `waiting_for_approval`, więc ten status po wygaśnięciu czytamy
  jak `running`); spóźnione `zgoda()` = 409 `zgoda_wygasla`. Brama ma ten sam czas i zwykle odmawia pierwsza (bez
  `approval.responded`): zdarzenie pracy w `czeka_na_zgode` najwyżej 1 s przed `wygasa_at` to też wygaśnięcie.
- **Stop**: `zatrzymywanie` + `stop_lokalny`; kolejne przebiegi tego członka w wątku → `kolejka(wstrzymane)` (tylko
  „Wyślij teraz” je puści). `run.cancelled` = `zatrzymane` przy naszym stopie, inaczej `przerwane`. Stop w
  `wysylanie` przed pierwszym POST = `zatrzymane` bez wysyłki. Nieudany POST stopu (brama chwilowo nie odpowiada)
  kontrola ponawia w tle co 5 s (5 razy), potem co 30 s, także po trwałym usunięciu wątku (wiersza już nie ma, praca
  w bramie nie zostaje bez właściciela; najwyżej godzinę); drugi Stop właściciela wysyła go od razu; po restarcie
  dashboardu raz od razu. Tura bez `run_id` (tylko z osi czasu): stopu nie ma dokąd wysłać, `zatrzymywanie` kończy
  kontrola z osi czasu (`gotowe` z odpowiedzią), turę bez odpowiedzi strażnik (`zgubione`).
- **Dopisz**: wiersz `dopisany` zapisany PRZED steerem (koniec tamtej tury w trakcie steera go widzi; steer odrzucony
  = wiersz usunięty, a z kolejki: powrót do kolejki, po Stopie celu jako `wstrzymane`); przebieg `dopisany` czeka na
  koniec tamtej. `pending_steer` z końca (Hermes skleja niedostarczone steery `\n`) dzielimy na całe teksty
  dopisków tego celu: jedyny podział → te w nim wróciły (`kolejka(zajety_agent)`, po Stopie właściciela
  `kolejka(wstrzymane)`), reszta `wlaczony`. Brak albo kilka podziałów, koniec bez statusu bramy (`zgubione`,
  konflikt, tura z osi czasu), restart (także dopisek sprzed restartu: steer mógł nie dojść do bramy), a przy `zatrzymane`/`przerwane` każdy niezwrócony (Hermes przy twardym
  przerwaniu gubi niedostarczony steer) = kontrola szuka wiersza `steer` w state.db: jest → `wlaczony`, nie ma →
  `kolejka(wstrzymane)`.
- **Ponów**: nowy przebieg (`ponowienie_z`); gdy nasz wiersz jest w state.db, krótkie „Poprzednia tura nie
  dokończyła się (…). Odpowiedz jeszcze raz na moją ostatnią wiadomość.”, inaczej cała prośba z nowym blokiem.
  Drugie Ponów tego samego przebiegu zwraca ponowienie, które trwa albo się udało (bez drugiej wysyłki); po
  ponowieniu anulowanym albo nieudanym Ponów tworzy następne.
- **Koniec**: każde przejście do stanu końcowego (też `anulowane` i `wlaczony`) wysyła `przebieg.koniec`.
- **Restart dashboardu** (`uruchom`): `kolejka`/`dopisany` zostają (`dopisany` zapamiętane jako niepewne), `wysylanie` wysyła to samo ciało z tym samym
  kluczem (brama zwraca istniejący przebieg), przebiegi z `run_id` dostają `odlaczony` i odpytywanie (strumienia
  `/events` nie da się podpiąć drugi raz).
Asyncio na pętli wątku silnika (silnik.py); zależności wstrzykiwane. Testy z atrapą bramy: tests/test_silnik_rozmow.py.
"""

from __future__ import annotations

import asyncio
import base64
import os
import random
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

STANY_AKTYWNE = ("kolejka", "wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie",
                 "dopisany")
STANY_KONCOWE = ("gotowe", "blad", "zatrzymane", "przerwane", "zgubione", "anulowane", "wlaczony")
STANY_W_LIMICIE = ("wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie")
STANY_Z_PRZEBIEGIEM = ("przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie")
_K = set(STANY_KONCOWE)
PRZEJSCIA: dict[str, set[str]] = {
    "kolejka": {"kolejka", "wysylanie", "dopisany", "anulowane", "blad"},
    "wysylanie": {"wysylanie", "kolejka", "przyjety", "pracuje", "zatrzymywanie"} | _K,
    "przyjety": {"przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie"} | _K,
    "pracuje": {"pracuje", "czeka_na_zgode", "zatrzymywanie"} | _K,
    "czeka_na_ture": {"czeka_na_ture", "pracuje", "czeka_na_zgode", "zatrzymywanie"} | _K,
    "czeka_na_zgode": {"czeka_na_zgode", "pracuje", "zatrzymywanie"} | _K,
    "zatrzymywanie": {"zatrzymywanie"} | _K,
    "dopisany": {"dopisany", "kolejka", "wlaczony", "anulowane"},
}
BRAMA_KONCOWE = {"completed", "failed", "cancelled", "interrupted"}
ZDARZENIA_KONCOWE = {f"run.{s}" for s in BRAMA_KONCOWE}

TRZYMANE = ("wstrzymane", "misja")      # powody kolejki, które zdejmuje tylko właściciel („Wyślij teraz”)


def limit_domyslny(cpu: int | None = None) -> int:
    """Limit przebiegów w bramie: domyślna pula wątków bramy Hermesa to `min(32, cpu + 4)` (tury `/v1/runs`,
    budzenia z kanbana, zakładanie i przypinanie sesji, streszczenia kompresji), trzy wątki zostają wolne;
    najwyżej 8."""
    if cpu is None:
        cpu = (getattr(os, "process_cpu_count", None) or os.cpu_count)() or 1
    return max(1, min(8, min(32, int(cpu) + 4) - 3))


LIMIT = limit_domyslny()
ODSTEPY_BRAMY = (1, 2, 4, 8, 16, 30)
BRAMA_LIMIT_S = 120.0
BRAMA_MLODA_S = 300.0
LIMIT_429_S = 600.0
KONFLIKT_S = 60.0
CZEKA_NA_TURE_S = 5.0
CISZA_S = 90.0
ZGUBIONY_404_S = 60.0
ZGUBIONY_S = 600.0
ODPYTANIE_S = 2.0
DELTA_S = 0.05
TEKST_MAKS = 256 * 1024
MYSL_MAKS = 2048
PODGLAD_MAKS = 500
DZIENNIK_PO_KONCU_S = 300.0
ZGODA_DOMYSLNIE_S = 300.0
ZGODA_TOLERANCJA_S = 1.0         # brama liczy swój czas od chwili po zdarzeniu `approval.request`
WYGASLE_PAMIEC_S = 3600.0        # wygasłe prośby o zgodę pamiętane godzinę (późne zdarzenia tej samej prośby)
STOP_PONOW_S = 5.0
STOP_PROBY = 5
STOP_PONOW_WOLNO_S = 30.0        # po STOP_PROBY szybkich próbach: wolne ponawianie, dopóki przebieg się nie skończy
STOP_SIEROTA_S = 3600.0          # stop przebiegu bez wiersza (wątek usunięty na stałe): ponawiany najwyżej godzinę
PRZERWA_429_S = 60.0             # 429 po dłuższym czekaniu z innego powodu (tura, wstrzymane) zaczyna budżet od nowa
DLUGO_S = float(os.environ.get("JARVO_HQ_DLUGO_S") or 7200)
OKNO_SHA = 2.0
KONTYNUACJA = "Poprzednia tura nie dokończyła się ({powod}). Odpowiedz jeszcze raz na moją ostatnią wiadomość."
PRZYCZYNY = {      # turn_exit_reason → krótka przyczyna po polsku (nieznana: „Praca się nie udała” + szczegóły)
    "max_iterations": "Skończył się limit kroków", "iteration_budget": "Skończył się limit kroków",
    "iteration_budget_exhausted": "Skończył się limit kroków", "budget_exhausted": "Skończył się limit kroków",
    "provider_error": "Model przestał odpowiadać", "model_error": "Model przestał odpowiadać",
    "empty_response": "Model nic nie odpowiedział", "timeout": "Model przestał odpowiadać",
    "context_overflow": "Rozmowa jest za długa dla modelu", "context_length_exceeded": "Rozmowa jest za długa dla modelu",
    "auth_error": "Brak klucza albo zły klucz modelu", "credentials": "Brak klucza albo zły klucz modelu",
    "rate_limited": "Dostawca modelu ogranicza zapytania", "interrupted": "Tura przerwana",
}
RYZYKA = (         # pattern_key / opis polecenia → zdanie o ryzyku (karta zgody); reszta: zdanie ogólne
    (re.compile(r"rm\b|delet|remov|unlink|rmdir|shred", re.I), "Agent chce usunąć pliki"),
    (re.compile(r"sudo|root|chmod|chown|privileg", re.I), "Agent chce uruchomić polecenie z uprawnieniami administratora"),
    (re.compile(r"git.?push|force.?push|publish|deploy", re.I), "Agent chce wysłać zmiany na zewnątrz"),
    (re.compile(r"curl|wget|network|http|ssh|scp", re.I), "Agent chce połączyć się z innym komputerem albo pobrać plik"),
    (re.compile(r"kill|shutdown|reboot|systemctl", re.I), "Agent chce zatrzymać albo zrestartować program"),
)
RYZYKO_DOMYSLNE = "Agent chce uruchomić polecenie, które wymaga Twojej zgody"
CZAS_ZGODY_RE = re.compile(r"^approvals:\s*\n((?:[ \t]+.*\n?)*)", re.M)
_NIEZNANE = object()             # `pending_steer` nieznane (koniec bez statusu bramy): dopiski rozstrzyga oś czasu


def przyczyna(powod: str | None) -> str:
    return PRZYCZYNY.get(str(powod or ""), "Nieznana przyczyna")


def ryzyko(zgoda: Mapping) -> str:
    tekst = " ".join(str(zgoda.get(k) or "") for k in ("pattern_key", "description"))
    tekst += " " + " ".join(str(k) for k in zgoda.get("pattern_keys") or [])
    return next((zdanie for wzor, zdanie in RYZYKA if wzor.search(tekst)), RYZYKO_DOMYSLNE)


def czas_zgody_z_configu(sciezka: Path | str) -> float:
    """`approvals.timeout` z config.yaml profilu (bez parsera YAML: blok `approvals:` i jego `timeout:`)."""
    try:
        tekst = Path(sciezka).read_text(encoding="utf-8")
    except OSError:
        return ZGODA_DOMYSLNIE_S
    m = CZAS_ZGODY_RE.search(tekst)
    if m:
        t = re.search(r"^[ \t]+timeout:\s*([0-9]+(?:\.[0-9]+)?)\s*$", m.group(1), re.M)
        if t:
            return float(t.group(1))
    return ZGODA_DOMYSLNIE_S


def watek_krotki(w: Mapping) -> dict:
    """WatekKrotki (pozycja listy) z wiersza `Rozmowy.watek`."""
    return {k: w.get(k) for k in ("id", "tytul", "przypiety", "archiwum", "usuniety_at", "rodzaj", "kanal", "czlonkowie",
                                  "ostatni_agenci", "aktywnosc_at", "nieprzeczytane", "status", "podglad", "koordynator")}


class Blad(Exception):
    """Błąd operacji rejestru dla trasy: status HTTP, kod (slug) i komunikat PL/EN."""

    def __init__(self, status: int, kod: str, komunikat: str, komunikat_en: str = "", **dane):
        super().__init__(komunikat)
        self.status, self.kod, self.komunikat, self.komunikat_en, self.dane = status, kod, komunikat, komunikat_en, dane


class Dziennik:
    """Stan przebiegu w pamięci: tekst strumienia (≤ 256 KB), ostatnie 50 kroków, ostatnie 500 zdarzeń (bez treści)."""

    def __init__(self):
        self.tekst = ""
        self.oczekuje = ""
        self.po_narzedziu = False
        self.kroki: deque[dict] = deque(maxlen=50)
        self.otwarte: dict[str, deque[dict]] = {}
        self.zdarzenia: deque[dict] = deque(maxlen=500)
        self.ostatnie_at: float | None = None
        self.ostatnie: str | None = None
        self.zapisane_at = 0.0
        self.koniec_at: float | None = None
        self.zaplanowana = False
        self.dopisane: dict[str, str] = {}        # dopiski tego celu po końcu tury: id → wrocil | wlaczony | sprawdz

    def dopisz(self, tekst: str) -> None:
        if not tekst:
            return
        if len(self.tekst) + len(tekst) > TEKST_MAKS:
            miejsce = max(0, TEKST_MAKS - len(self.tekst))
            if miejsce == 0:
                return
            tekst = tekst[:miejsce] + "\n…(ucięte)"
        self.tekst += tekst
        self.oczekuje += tekst


class Rejestr:
    """Rejestr przebiegów: jedna instancja na proces, wszystkie metody na pętli wątku silnika."""

    def __init__(self, db, brama, hub, *, czytnik, agenci, kontekst, scalanie, budzenia=None, cialo: Callable,
                 cialo_sha: Callable, blad_bramy: type, utajnij: Callable[[str], str] = lambda t: t,
                 etykieta: Callable | None = None, limit: int = LIMIT, zegar: Callable[[], float] = time.time,
                 log: Callable[[str], None] | None = None, czas_zgody: Callable[[str], float] = lambda _a: ZGODA_DOMYSLNIE_S,
                 aktualizacja: Callable[[], bool] = lambda: False, brama_mloda: Callable[[], bool] = lambda: False,
                 obrazy_wprost: Callable[[], bool] = lambda: True, plik: Callable | None = None,
                 odstep_odpytania: float = ODPYTANIE_S):
        self.db, self.brama, self.hub = db, brama, hub
        self.czytnik, self.agenci, self.kontekst, self.scalanie, self.budzenia = czytnik, agenci, kontekst, scalanie, budzenia
        self.cialo, self.cialo_sha, self.BladBramy = cialo, cialo_sha, blad_bramy
        self.utajnij, self.etykieta = utajnij, etykieta
        self.limit = max(1, int(limit))
        self.zegar = zegar
        self.log = log or (lambda _m: None)
        self.czas_zgody, self.aktualizacja, self.brama_mloda, self.obrazy_wprost = czas_zgody, aktualizacja, brama_mloda, obrazy_wprost
        self.plik = plik
        self.odstep_odpytania = odstep_odpytania
        self._dzienniki: dict[str, Dziennik] = {}
        self._zadania: set[asyncio.Task] = set()
        self._sluchacze: dict[str, asyncio.Task] = {}
        self._odpytywane: dict[str, asyncio.Task] = {}
        self._wygasle: dict[str, float] = {}          # request_id → kiedy wygasła
        self._odpowiadane: set[str] = set()            # request_id, na które odpowiedź właśnie idzie do bramy
        self._w_locie: set[str] = set()                # przebiegi `dopisany`, których steer właśnie idzie do bramy
        self._sprzed_startu: set[str] = set()          # `dopisany` sprzed restartu: nie wiadomo, czy steer doszedł
        self._konflikty: dict[str, float] = {}
        self._pierwszy_blad: dict[str, float] = {}
        self._pierwszy_429: dict[str, tuple[float, float]] = {}    # (pierwsza odmowa, kiedy miała być następna próba)
        self._stop_ponowiony: set[str] = set()         # stop w `wysylanie`: jedno ponowienie POST (mógł dotrzeć)
        self._stop_proby: dict[str, dict] = {}         # nieudany stop: n, at, od, agent, run_id, sierota
        self._stop_w_locie: set[str] = set()           # ponowienie stopu właśnie idzie do bramy (zadanie tła)
        self._brak_404: dict[str, float] = {}
        self._wiersze: dict[str, tuple[int, float]] = {}
        self._dlugo: set[str] = set()
        self._budzik: asyncio.Event | None = None
        self._dziala = False

    # =========================================================================================== pomocnicze
    def _nazwy(self) -> dict[str, str]:
        try:
            return self.agenci.nazwy_wyswietlane()
        except Exception:
            return {}

    def _zadanie(self, coro) -> asyncio.Task:
        t = asyncio.get_running_loop().create_task(coro)
        self._zadania.add(t)
        t.add_done_callback(self._po_zadaniu)
        return t

    def _po_zadaniu(self, t: asyncio.Task) -> None:
        """Wyjątek zadania tła odebrany tutaj (nie trafi do domyślnej obsługi asyncio z pełnym tekstem)."""
        self._zadania.discard(t)
        if not t.cancelled() and t.exception() is not None:
            self.log(f"jarvo-hq: zadanie tła: {type(t.exception()).__name__}")

    def zadanie(self, coro) -> asyncio.Task:
        """Zadanie tła na pętli silnika (trasy: np. zmiana tytułu sesji członków po zmianie tytułu wątku)."""
        return self._zadanie(coro)

    def _budz(self) -> None:
        if self._budzik is not None:
            self._budzik.set()

    def dziennik(self, pid: str) -> Dziennik:
        dz = self._dzienniki.get(pid)
        if dz is None:
            dz = self._dzienniki[pid] = Dziennik()
        return dz

    def _rodowod(self, p: Mapping) -> list[str]:
        return [s["sesja_id"] for s in self.db.sesje_watku(p["watek_id"], agent=p["agent"], rola=p.get("rola") or "rozmowa")]

    async def _w_tle(self, fn, *arg):
        return await asyncio.to_thread(fn, *arg)

    def widok(self, p: Mapping, *, tekst: bool = True) -> dict:
        """Przebieg w kształcie API (`tekst_dotad`, `kroki_dotad`, `seq` = pozycja w strumieniu)."""
        dz = self._dzienniki.get(p["id"])
        out = {k: p.get(k) for k in ("id", "watek_id", "wpis_id", "agent", "rola", "stan", "powod", "zrodlo",
                                     "lancuch_id", "lancuch_zrodlo", "hop", "przekaz_z", "run_id", "utworzony_at",
                                     "przyjety_at", "zakonczony_at", "zgoda", "blad", "dopisany_do", "ponowienie_z",
                                     "proby", "nastepna_proba_at")}
        out["odlaczony"] = bool(p.get("odlaczony"))
        out["nadzor"] = ({"stan": p["nadzor_stan"], "przez": p.get("nadzor_przez")} if p.get("nadzor_stan") else None)
        out["nadzor_zgoda"] = ({"stan": p["nadzor_zgoda"], "przez": p.get("nadzor_zgoda_przez")}
                               if p.get("nadzor_zgoda") else None)
        out["dlugo"] = p["id"] in self._dlugo
        if tekst:
            # bez tekstu czekającego na wspólną deltę (≤ 50 ms): ten przyjdzie jako `przebieg.delta` z seq > `seq`
            out["tekst_dotad"] = (dz.tekst[:len(dz.tekst) - len(dz.oczekuje)] if dz.oczekuje else dz.tekst) if dz else ""
            out["kroki_dotad"] = list(dz.kroki) if dz else list(p.get("kroki") or [])
            out["seq"] = self.hub.kursor()
        return out

    def _nadaj(self, p: Mapping, typ: str, dane: dict) -> None:
        if p.get("zrodlo") == "nadzor" and typ in ("przebieg.delta", "przebieg.komentarz", "przebieg.mysl"):
            return          # nadzór niczego nie streamuje: „[SILENT]” nigdy nie trafia do przeglądarki
        self.hub.nadaj(typ, {"id": p["id"], "watek_id": p["watek_id"], "agent": p["agent"], **dane},
                       watek_id=p["watek_id"])

    def _nadaj_stan(self, p: Mapping) -> None:
        self.hub.nadaj("przebieg.stan", {"przebieg": self.widok(p, tekst=False)}, watek_id=p["watek_id"])

    def _zapisz_goraca(self, p: Mapping, *, zawsze: bool = False) -> dict:
        """Gorące pola (ostatnie zdarzenie) zapisywane co 2 s i przy zmianie stanu, nie przy każdym zdarzeniu."""
        dz = self._dzienniki.get(p["id"])
        if dz is None or dz.ostatnie_at is None:
            return dict(p)
        teraz = self.zegar()
        if zawsze or teraz - dz.zapisane_at >= 2.0:
            dz.zapisane_at = teraz
            return self.db.zmien_przebieg(p["id"], ostatnie_zdarzenie_at=dz.ostatnie_at, ostatnie_zdarzenie=dz.ostatnie)
        return dict(p)

    # =========================================================================================== przejścia
    def _przejdz(self, p: Mapping, stan: str, *, powod: str | None = None, zwolnij: bool = False, **pola) -> dict:
        """Zmiana stanu według tabeli przejść: zapis, dziennik, `przebieg.stan` (i `przebieg.koniec` przy stanie
        końcowym), status wątku. Zawsze od bieżącego wiersza: `kolejka(wstrzymane|misja)` nie wraca do zwykłej kolejki
        ani do wysyłki bez `zwolnij` („Wyślij teraz”), nawet gdy wołający ma stary odczyt."""
        pid = p["id"]
        biezacy = self.db.przebieg(pid)
        if biezacy is None:
            return dict(p)
        stary = biezacy["stan"]
        if stary in STANY_KONCOWE or stan not in PRZEJSCIA.get(stary, set()):
            self.log(f"jarvo-hq: przebieg {pid}: przejście {stary}→{stan} odrzucone")
            return biezacy
        if (stary == "kolejka" and biezacy.get("powod") in TRZYMANE and not zwolnij
                and (stan == "wysylanie" or (stan == "kolejka" and powod not in TRZYMANE))):
            return biezacy
        zm: dict[str, Any] = dict(pola)
        zm["stan"] = stan
        if powod is not None:
            zm["powod"] = powod
        elif stan != stary:
            zm["powod"] = "start" if stan == "kolejka" else ""
        if stan in STANY_KONCOWE:
            zm.setdefault("zakonczony_at", self.zegar())
        dz = self._dzienniki.get(pid)
        if dz is not None and dz.ostatnie_at is not None:
            zm.setdefault("ostatnie_zdarzenie_at", dz.ostatnie_at)
            zm.setdefault("ostatnie_zdarzenie", dz.ostatnie)
        nowy = self.db.zmien_przebieg(pid, **zm)
        if stan != stary or (powod is not None and powod != biezacy.get("powod")):
            ms = int((self.zegar() - float(biezacy.get("utworzony_at") or self.zegar())) * 1000)
            self.log(f"jarvo-hq: przebieg {pid} {biezacy['agent']} {stary}→{stan}"
                     f"{'(' + nowy['powod'] + ')' if nowy.get('powod') else ''} {ms} ms")
        self._nadaj_stan(nowy)
        if stan in STANY_KONCOWE:
            self.hub.nadaj("przebieg.koniec", {"id": pid, "watek_id": nowy["watek_id"], "agent": nowy["agent"],
                                               "stan": stan, "blad": nowy.get("blad")}, watek_id=nowy["watek_id"])
        if stan != stary:
            self._status_watku(nowy["watek_id"])
        return nowy

    def _zmien(self, p: Mapping, **pola) -> dict:
        """Zmiana pól bez zmiany stanu (np. `odlaczony`, `zgoda`), z `przebieg.stan`."""
        nowy = self.db.zmien_przebieg(p["id"], **pola)
        self._nadaj_stan(nowy)
        return nowy

    def _status_watku(self, wid: str) -> None:
        w = self.db.watek(wid)
        if w is None:
            return
        aktywne = [p for p in self.db.przebiegi_watku(wid, aktywne=True) if p.get("zrodlo") != "nadzor"]
        if any(p["stan"] == "czeka_na_zgode" for p in aktywne):
            status = "czeka"
        elif aktywne:
            status = "pracuje"
        else:
            status = "blad" if w.get("status") == "blad" else "cisza"
        if status != w.get("status"):
            w = self.db.zmien(wid, status=status)
            self.hub.nadaj("watek.zmiana", {"watek": watek_krotki(w)})

    # =========================================================================================== start i pętle
    async def uruchom(self) -> None:
        """Odzyskanie po restarcie (§ Restart), potem dyspozytor, kontrola (1 s) i strażnik (10 s)."""
        self._budzik = asyncio.Event()
        self._dziala = True
        for p in self.db.przebiegi_aktywne():
            if p["stan"] == "dopisany":
                # wiersz powstaje przed steerem: proces mógł paść, zanim steer doszedł do bramy, więc niezwrócony
                # w `pending_steer` tekst nie znaczy, że agent go przeczytał (rozstrzyga wiersz `steer` w state.db)
                self._sprzed_startu.add(p["id"])
                continue
            if p["stan"] == "kolejka":
                continue
            if p["stan"] == "wysylanie" and not p.get("run_id"):
                self.log(f"jarvo-hq: przebieg {p['id']}: wysyłka po restarcie (ten sam klucz)")
                self._zadanie(self._wyslij(p["id"]))
            elif p.get("run_id"):
                p = self._zmien(p, odlaczony=True)
                self._odpytuj_start(p["id"])
                if p["stan"] == "zatrzymywanie" and p.get("stop_lokalny"):
                    self._zadanie(self._stop_bramy(p))      # stop sprzed restartu mógł nie dojść do bramy
        self._zadanie(self._dyspozytor())
        self._zadanie(self._kontrola())
        self._zadanie(self._straznik())

    async def zatrzymaj_petle(self) -> None:
        self._dziala = False
        for t in list(self._zadania):
            t.cancel()
        await asyncio.gather(*list(self._zadania), return_exceptions=True)

    async def _dyspozytor(self) -> None:
        while self._dziala:
            self._budzik.clear()        # przed rundą: budzenie w trakcie rundy (nowa wiadomość, koniec) nie ginie
            try:
                await self._runda()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - dziennik, pętla żyje dalej
                self.log(f"jarvo-hq: dyspozytor: {type(exc).__name__}")
            try:
                await asyncio.wait_for(self._budzik.wait(), timeout=ODPYTANIE_S)
            except asyncio.TimeoutError:
                pass

    def _powod(self, p: Mapping, powod: str, **pola) -> dict:
        """Powód czekania w kolejce z bieżącego wiersza (runda czyta wiersze na początku i czeka na sondy: Stop
        w tym czasie mógł dać `wstrzymane`, a tego runda nie nadpisuje)."""
        biezacy = self.db.przebieg(p["id"])
        if biezacy is None or biezacy["stan"] != "kolejka" or biezacy.get("powod") in TRZYMANE:
            return biezacy or dict(p)
        if biezacy.get("powod") == powod and not pola:
            return biezacy
        return self._przejdz(biezacy, "kolejka", powod=powod, **pola)

    async def _runda(self) -> None:
        """Jedna runda dyspozytora: które przebiegi z kolejki mogą iść teraz."""
        teraz = self.zegar()
        aktywne = self.db.przebiegi_aktywne()
        w_limicie = sum(1 for p in aktywne if p["stan"] in STANY_W_LIMICIE)
        zajete = {(p["watek_id"], p["agent"], p.get("rola") or "rozmowa") for p in aktywne if p["stan"] in STANY_W_LIMICIE}
        widziane: set[tuple] = set()
        w_koszu: dict[str, bool] = {}
        for p in aktywne:
            if p["stan"] != "kolejka":
                continue
            if p["watek_id"] not in w_koszu:
                w_koszu[p["watek_id"]] = bool((self.db.watek(p["watek_id"]) or {"usuniety_at": 1}).get("usuniety_at"))
            if w_koszu[p["watek_id"]]:              # wątek w koszu: kolejka nie rusza (np. dopisany wrócił po końcu,
                self._koniec(p, "anulowane")        # także wstrzymany: porządek przed koszem anulował całą kolejkę)
                continue
            if p.get("powod") in TRZYMANE:
                continue
            k = (p["watek_id"], p["agent"], p.get("rola") or "rozmowa")
            if k in zajete or k in widziane:
                widziane.add(k)
                self._powod(p, "zajety_agent")
                continue
            widziane.add(k)
            if p.get("nastepna_proba_at") and float(p["nastepna_proba_at"]) > teraz:
                continue
            rodowod = self._rodowod(p)
            if rodowod:
                d = await self._w_tle(self.czytnik.dzierzawa, p["agent"], rodowod, self.zegar())
                if d:
                    self._powod(self.db.przebieg(p["id"]) or p, "tura")
                    continue
            if w_limicie >= self.limit:
                self._powod(p, "limit")
                continue
            biezacy = self.db.przebieg(p["id"])
            if not biezacy or biezacy["stan"] != "kolejka" or biezacy.get("powod") in TRZYMANE:
                continue
            biezacy = self._przejdz(biezacy, "wysylanie", proby=int(biezacy.get("proby") or 0) + 1, nastepna_proba_at=None)
            if biezacy["stan"] != "wysylanie":
                continue
            w_limicie += 1
            zajete.add(k)
            self._zadanie(self._wyslij(p["id"]))

    # =========================================================================================== zlecenia
    def zlec(self, *, watek_id: str, wpis_id: str | None, agent: str, prosba: str, obrazy: Iterable[Mapping] = (),
             rola: str = "rozmowa", zrodlo: str = "wlasciciel", autor: dict | None = None, lancuch_id: str | None = None,
             nadzorowany: bool = False, tekst: str | None = None, ponowienie_z: str | None = None, hop: int = 0) -> dict:
        """Nowy przebieg w `kolejka(start)`. `prosba` = treść dla agenta z liniami 📎 (bez bloku kontekstu: ten
        powstaje, gdy przebieg wychodzi z kolejki). `tekst` podany = treść stała, bez bloku (kontynuacja Ponów)."""
        payload: dict[str, Any] = {"prosba": prosba, "obrazy": [{"path": o["path"], "mime": o["mime"]} for o in obrazy]}
        pola: dict[str, Any] = {}
        if tekst is not None:
            payload.update(tekst=tekst, wprost=False, obrazy=[])
            pola["payload_sha"] = self.kontekst.payload_sha(tekst, 0)
        p = self.db.dodaj_przebieg(watek_id=watek_id, wpis_id=wpis_id, agent=agent, rola=rola, zrodlo=zrodlo,
                                   lancuch_id=lancuch_id, autor=autor, payload=payload, nadzorowany=nadzorowany,
                                   ponowienie_z=ponowienie_z, hop=hop, **pola)
        self.log(f"jarvo-hq: przebieg {p['id']} {agent} —→kolejka(start)")
        self._nadaj_stan(p)
        self._status_watku(watek_id)
        self._budz()
        return p

    async def anuluj(self, pid: str, *, dopisany: bool = False) -> dict:
        """Wiadomość z kolejki (i z `dopisany`, gdy `dopisany`: porządek przed archiwum albo koszem) → `anulowane`."""
        p = self._wez(pid)
        if dopisany and p["stan"] == "dopisany":
            if pid in self._w_locie:                # steer w drodze: rozstrzygnie go `_po_steerze` i koniec celu
                return p
            self._koniec(p, "anulowane")
            return self.db.przebieg(pid) or p
        if p["stan"] != "kolejka":
            raise Blad(409, "nieaktywny", "Anulować można tylko wiadomość, która czeka w kolejce.",
                       "Only a queued message can be cancelled.")
        self._koniec(p, "anulowane")
        return self.db.przebieg(pid) or p

    async def wyslij_teraz(self, pid: str) -> dict:
        p = self._wez(pid)
        if p["stan"] != "kolejka" or p.get("powod") not in ("wstrzymane", "misja"):
            raise Blad(409, "nieaktywny", "„Wyślij teraz” działa tylko dla wstrzymanej wiadomości.",
                       "“Send now” works only for a held message.")
        p = self._przejdz(p, "kolejka", powod="start", nastepna_proba_at=None, zwolnij=True)
        self._pierwszy_429.pop(pid, None)           # decyzja właściciela: budżet 429 od nowa
        self._budz()
        return p

    def _wez(self, pid: str) -> dict:
        p = self.db.przebieg(pid)
        if p is None:
            raise Blad(404, "brak", "Nie ma takiej pracy.", "No such run.")
        return p

    # =========================================================================================== wysyłka
    async def _przygotuj(self, p: dict) -> dict:
        """Pierwsza próba: blok kontekstu z wątku teraz, `payload.tekst`, `payload_sha`, `widzial_at`."""
        payload = dict(p.get("payload") or {})
        wid, agent, rola = p["watek_id"], p["agent"], p.get("rola") or "rozmowa"
        watek = self.db.watek(wid) or {}
        czl = self.db.zapewnij_czlonka(wid, agent, rola)
        teraz = self.zegar()
        nazwy = self._nazwy()
        blok = ""
        kod = self.kontekst.kod()
        try:
            pozycje = await self._w_tle(lambda: self.scalanie.pozycje_kontekstu(
                self.db, self.czytnik, wid, budzenia=self.budzenia, etykieta=self.etykieta))
            koord = None
            if agent == watek.get("koordynator") and rola == "rozmowa":
                w_toku = sorted({q["agent"] for q in self.db.przebiegi_watku(wid, aktywne=True)
                                 if q["agent"] != agent and q["stan"] in STANY_W_LIMICIE})
                koord = {"ostatnia": self.scalanie.ostatnia_praca(pozycje, agent), "w_toku": w_toku, "do_sprawdzenia": []}
            # blok w wątku roboczym: wpisy są czyszczone (sekrety, podróbki znaczników) w całości, zanim zostaną
            # przycięte, a długie odpowiedzi agentów nie mogą wstrzymać pętli silnika (strumienie, inne przebiegi)
            blok = await self._w_tle(lambda: self.kontekst.blok(
                pozycje, agent=agent, tytul=watek.get("tytul") or "", kod_bloku=kod, rola=rola,
                widzial_at=float(czl.get("widzial_at") or 0), wpis_id=p.get("wpis_id"), nazwy=nazwy, teraz=teraz,
                utajnij=self.utajnij, koordynator=koord))
        except Exception as exc:  # oś czasu nieczytelna (schemat Hermesa): wysyłamy bez bloku, dziennik mówi czemu
            self.log(f"jarvo-hq: przebieg {p['id']}: blok kontekstu pominięty ({type(exc).__name__})")
        tekst = self.kontekst.tekst_przebiegu(blok_kontekstu=blok, prosba=payload.get("prosba") or "", kod_bloku=kod,
                                              zlecenie=p.get("zrodlo") == "przekaz", utajnij=self.utajnij)
        wprost = bool(payload.get("obrazy")) and bool(self.obrazy_wprost())
        payload.update(tekst=tekst, wprost=wprost)
        p = self.db.zmien_przebieg(p["id"], payload=payload,
                                   payload_sha=self.kontekst.payload_sha(tekst, len(payload.get("obrazy") or []) if wprost else 0))
        self.db.zmien_czlonka(wid, agent, rola, widzial_at=teraz)
        return p

    def _wejscie(self, payload: Mapping) -> Any:
        """`input` przebiegu: tekst albo lista z obrazami (data URL z plików inboxa: te same bajty = to samo ciało)."""
        tekst = payload.get("tekst") or ""
        obrazy = payload.get("obrazy") if payload.get("wprost") else []
        if not obrazy:
            return tekst
        czesci: list[dict] = [{"type": "text", "text": tekst}]
        for o in obrazy:
            dane = Path(o["path"]).read_bytes()
            czesci.append({"type": "image_url",
                           "image_url": {"url": f"data:{o['mime']};base64,{base64.b64encode(dane).decode('ascii')}"}})
        return [{"role": "user", "content": czesci}]

    async def _sesja(self, p: dict) -> str:
        """Sesja Hermesa członka (tworzona i przypinana przy pierwszym przebiegu); wysyłamy do najnowszej z rodowodu."""
        wid, agent, rola = p["watek_id"], p["agent"], p.get("rola") or "rozmowa"
        czl = self.db.czlonek(wid, agent, rola)
        if czl and czl.get("sesja_id"):
            return czl.get("sesja_tip") or czl["sesja_id"]
        sid = f"jarvo_{wid}_{'nadzor' if rola == 'nadzor' else agent}"
        watek = self.db.watek(wid) or {}
        nazwa = self._nazwy().get(agent, agent)
        tytul = " ".join(str(watek.get("tytul") or "Rozmowa").split())[:60]
        await self.brama.utworz_sesje(agent, sid, f"Jarvo · {tytul} · {nazwa}{' · nadzór' if rola == 'nadzor' else ''}")
        self.db.ustaw_sesje(wid, agent, sid, rola=rola, powod="start")
        await self.przypnij(agent, sid)
        return sid

    async def przypnij(self, agent: str, sid: str) -> bool:
        """`pinned` w Hermesie (auto-prune nie usunie historii wątku); porażka nie blokuje, obserwator ponawia."""
        try:
            await self.brama.zmien_sesje(agent, sid, pinned=True)
        except self.BladBramy as e:
            self.log(f"jarvo-hq: przypięcie sesji {agent}/{sid} nieudane ({e.kod}), ponowię")
            return False
        self.db.ustaw_przypieta(agent, sid, True)
        return True

    async def _wyslij(self, pid: str) -> None:
        p = self.db.przebieg(pid)
        if not p or p["stan"] != "wysylanie":
            return
        try:
            if not (p.get("payload") or {}).get("tekst") and not p.get("cialo_sha"):
                p = await self._przygotuj(p)
            payload = p.get("payload") or {}
            if not payload.get("tekst") and payload.get("prosba") is None:
                raise Blad(409, "brak_tresci", "Treść tej wiadomości już nie jest przechowywana.")
            sesja = p.get("sesja_id") or await self._sesja(p)
            wejscie = await self._w_tle(self._wejscie, payload)
            p = self.db.przebieg(pid)               # po sondach: Stop albo usunięcie wątku mogły przyjść w trakcie
            if p is None or p["stan"] != "wysylanie":
                return
            if p.get("stop_lokalny") and not p.get("wyslany_at") and pid not in self._stop_ponowiony:
                self._koniec(p, "zatrzymane")       # nic jeszcze nie poszło do bramy: bez POST
                return
            c = self.cialo(sesja, wejscie, p.get("autor"))
            sha = self.cialo_sha(c)
            if p.get("cialo_sha") and p["cialo_sha"] != sha:
                self.log(f"jarvo-hq: BŁĄD przebieg {pid}: ciało ponowienia różni się od pierwszego, nie wysyłam")
                self._koniec(p, "blad", blad={"kod": "wewnetrzny", "komunikat": "Wewnętrzny błąd aplikacji przy ponownym wysłaniu."})
                return
            if not p.get("cialo_sha") or not p.get("sesja_id") or not p.get("wyslany_at"):
                p = self.db.zmien_przebieg(pid, sesja_id=sesja, cialo_sha=sha, wyslany_at=p.get("wyslany_at") or self.zegar())
            odp = await self.brama.start(p["agent"], cialo_=c, idem=p["idem"])
        except self.BladBramy as e:
            self._blad_wysylki(pid, e)
            return
        except FileNotFoundError:
            self._koniec(self.db.przebieg(pid), "blad", blad={"kod": "odrzucone", "komunikat": "Obraz z tej wiadomości zniknął z dysku."})
            return
        except Blad as e:
            self._koniec(self.db.przebieg(pid), "blad", blad={"kod": e.kod, "komunikat": e.komunikat})
            return
        except Exception as exc:
            self.log(f"jarvo-hq: przebieg {pid}: wysyłka {type(exc).__name__}")
            self._koniec(self.db.przebieg(pid), "blad", blad={"kod": "wewnetrzny", "komunikat": "Wewnętrzny błąd aplikacji."})
            return
        self._pierwszy_blad.pop(pid, None)
        self._pierwszy_429.pop(pid, None)
        await self._przyjety(pid, odp, agent=p["agent"])

    async def _przyjety(self, pid: str, odp: Mapping, *, agent: str | None = None) -> None:
        p = self.db.przebieg(pid)
        run_id, status = str(odp.get("run_id") or ""), str(odp.get("status") or "started")
        if p is None or p["stan"] in STANY_KONCOWE:
            # wątek usunięty na stałe (albo przebieg zamknięty) w trakcie POST: praca w bramie nie zostaje bez
            # właściciela, nikt by jej już nie zatrzymał
            if run_id and status not in BRAMA_KONCOWE and (agent or p):
                self.log(f"jarvo-hq: przebieg {pid}: przyjęty po usunięciu, zatrzymuję w bramie")
                await self._stop_w_bramie(pid, agent or p["agent"], run_id, sierota=True)
            return
        p = self._przejdz(p, "przyjety", run_id=run_id, przyjety_at=self.zegar(), nastepna_proba_at=None)
        if odp.get("replayed"):
            self.log(f"jarvo-hq: przebieg {pid}: brama zwróciła istniejący przebieg ({status})")
        if status in BRAMA_KONCOWE:
            try:
                st = await self.brama.stan(p["agent"], run_id)
            except self.BladBramy:
                st = {"status": status}
            self._koniec_ze_statusu(p, st)
            return
        if p.get("stop_lokalny"):
            await self._stop_bramy(p)
        if odp.get("replayed") and status not in ("started", "queued"):
            self._zmien(p, odlaczony=True)        # strumień tego przebiegu mógł już mieć słuchacza: odpytujemy
            self._odpytuj_start(pid)
            return
        self._sluchacze[pid] = self._zadanie(self._sluchaj(pid))

    def _blad_wysylki(self, pid: str, e) -> None:
        p = self.db.przebieg(pid)
        if p is None or p["stan"] != "wysylanie":
            return
        teraz = self.zegar()
        if p.get("stop_lokalny"):
            # Stop przyszedł, gdy POST był w drodze: bez ponawiania. Gdy POST mógł dotrzeć (czas odpowiedzi minął po
            # wysłaniu), jedno ponowienie tym samym kluczem i ciałem: brama zwraca istniejący przebieg (albo przyjmuje
            # ten), `_przyjety` od razu go zatrzymuje.
            if e.kod == "niedostepna" and getattr(e, "dotarlo", False) and pid not in self._stop_ponowiony:
                self._stop_ponowiony.add(pid)
                self._zadanie(self._wyslij_po_stopie(pid))
                return
            self._stop_ponowiony.discard(pid)
            self._koniec(p, "zatrzymane")
            return
        if e.kod == "limit":
            # budżet liczą tylko odmowy jedna po drugiej: po dłuższym czekaniu z innego powodu (obca tura, wstrzymane)
            # zaczyna się od nowa
            pierwszy, oczekiwana = self._pierwszy_429.get(pid, (teraz, teraz))
            if teraz - oczekiwana > PRZERWA_429_S:
                pierwszy = teraz
            nastepna = teraz + float(e.ponow_za or 1) + random.uniform(0, 0.5)
            self._pierwszy_429[pid] = (pierwszy, nastepna)
            if teraz - pierwszy > LIMIT_429_S:
                self._koniec(p, "blad", blad={"kod": "limit_bramy", "komunikat": "Jarvo ma teraz za dużo pracy naraz — spróbuj za chwilę."})
            else:
                self._przejdz(p, "kolejka", powod="limit", nastepna_proba_at=nastepna)
            return
        if e.kod == "niedostepna":
            pierwszy = self._pierwszy_blad.setdefault(pid, teraz)
            limit = None if self.aktualizacja() else (BRAMA_MLODA_S if self.brama_mloda() else BRAMA_LIMIT_S)
            if limit is not None and teraz - pierwszy > limit:
                self._pierwszy_blad.pop(pid, None)
                self._koniec(p, "blad", blad={"kod": "brama_niedostepna", "komunikat": "Jarvo nie odpowiada — sprawdź stan."})
            else:
                odstep = ODSTEPY_BRAMY[min(max(int(p.get("proby") or 1) - 1, 0), len(ODSTEPY_BRAMY) - 1)]
                self._przejdz(p, "kolejka", powod="brama", nastepna_proba_at=teraz + odstep)
            return
        if e.kod == "klucz":
            self._koniec(p, "blad", blad={"kod": "klucz", "komunikat": "Brakuje klucza profilu tego agenta albo jest zły."})
            return
        if e.kod == "konflikt" and e.typ == "idempotency_key_conflict":
            self.log(f"jarvo-hq: BŁĄD przebieg {pid}: idempotency_key_conflict (ciało różne od pierwszego); czekam na wiersz")
            self._konflikty.setdefault(pid, teraz)
            return
        self._koniec(p, "blad", blad={"kod": "odrzucone",
                                      "komunikat": self.utajnij(e.komunikat or "Brama odrzuciła wiadomość.")[:300]})

    async def _wyslij_po_stopie(self, pid: str) -> None:
        await asyncio.sleep(1.0)
        await self._wyslij(pid)

    # =========================================================================================== zdarzenia
    async def _sluchaj(self, pid: str) -> None:
        p = self.db.przebieg(pid)
        if not p or not p.get("run_id"):
            return
        self.dziennik(pid)
        koniec = False
        try:
            async for ev in self.brama.zdarzenia(p["agent"], p["run_id"]):
                koniec = self._zdarzenie(pid, ev)
                if koniec:
                    break
        except self.BladBramy as e:
            self.log(f"jarvo-hq: przebieg {pid}: strumień zdarzeń zerwany ({e.kod})")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.log(f"jarvo-hq: przebieg {pid}: strumień {type(exc).__name__}")
        finally:
            self._sluchacze.pop(pid, None)
        if not koniec:
            p = self.db.przebieg(pid)
            if p and p["stan"] not in STANY_KONCOWE:
                self._zmien(p, odlaczony=True)
                self._odpytuj_start(pid)

    def _do_pracy(self, p: dict) -> dict:
        if p["stan"] in ("przyjety", "czeka_na_ture"):
            return self._przejdz(p, "pracuje")
        if p["stan"] == "czeka_na_zgode":
            return self._po_zgodzie(p)
        return p

    def _po_zgodzie(self, p: dict) -> dict:
        """Brama pracuje dalej bez `approval.responded`. Po swoim `approvals.timeout` (tym samym co nasz) sama odmawia,
        zwykle zanim zrobi to kontrola co 1 s: wtedy to wygaśnięcie (`zgoda.wygasla`), a nie zwykły powrót do pracy."""
        z = p.get("zgoda") or {}
        if not z.get("wygasla") and z.get("wygasa_at") is not None and z.get("request_id") not in self._odpowiadane \
                and self.zegar() >= float(z["wygasa_at"]) - ZGODA_TOLERANCJA_S:
            return self._wygas(p)
        return self._przejdz(p, "pracuje", zgoda=z if z.get("wygasla") else None)

    def _zdarzenie(self, pid: str, ev: Mapping) -> bool:
        """Jedno zdarzenie `/v1/runs`; True = zdarzenie końcowe (słuchacz kończy)."""
        typ = str(ev.get("event") or "")
        p = self.db.przebieg(pid)
        if p is None or p["stan"] in STANY_KONCOWE:
            return True
        dz = self.dziennik(pid)
        dz.ostatnie_at, dz.ostatnie = float(ev.get("timestamp") or self.zegar()), typ
        dz.zdarzenia.append({"event": typ, "ts": dz.ostatnie_at, **({"tool": ev["tool"]} if ev.get("tool") else {})})
        if typ == "message.delta":
            p = self._do_pracy(p)
            tekst = str(ev.get("delta") or "")
            if dz.po_narzedziu and tekst:            # tekst po narzędziu = nowy akapit (nie przy pierwszym tekście)
                if dz.tekst and not dz.tekst.endswith("\n\n"):
                    tekst = ("\n" if dz.tekst.endswith("\n") else "\n\n") + tekst
                dz.po_narzedziu = False
            dz.dopisz(tekst)
            self._zaplanuj_delte(pid)
        elif typ == "message.interim":
            if not ev.get("already_streamed"):
                p = self._do_pracy(p)
                self._nadaj(p, "przebieg.komentarz", {"tekst": str(ev.get("text") or ""), "typ": "interim"})
        elif typ == "reasoning.available":
            self._nadaj(p, "przebieg.mysl", {"tekst": str(ev.get("text") or "")[:MYSL_MAKS]})
        elif typ == "tool.started":
            p = self._do_pracy(p)
            dz.po_narzedziu = True
            krok = self._krok(ev)
            dz.kroki.append(krok)
            dz.otwarte.setdefault(krok["narzedzie"], deque()).append(krok)
            self._nadaj(p, "przebieg.narzedzie", {"faza": "start", "krok": krok})
        elif typ == "tool.completed":
            p = self._do_pracy(p)
            nazwa = str(ev.get("tool") or "?")
            kolejka = dz.otwarte.get(nazwa)
            krok = kolejka.popleft() if kolejka else None
            if krok is None:
                krok = self._krok(ev)
                dz.kroki.append(krok)
            try:
                krok["czas_ms"] = int(round(float(ev.get("duration") or 0) * 1000))
            except (TypeError, ValueError):
                krok["czas_ms"] = None
            krok["blad"] = bool(ev.get("error"))
            if ev.get("preview"):
                krok["podglad"] = str(ev["preview"])[:PODGLAD_MAKS]
            self._nadaj(p, "przebieg.narzedzie", {"faza": "koniec", "krok": krok})
        elif typ.startswith("subagent."):
            opis = str(ev.get("goal") or ev.get("summary") or ev.get("preview") or ev.get("text") or "")[:300]
            self._nadaj(p, "przebieg.podagent", {"faza": typ.split(".", 1)[1], "opis": opis})
        elif typ == "approval.request":
            self._prosba_o_zgode(p, ev)
        elif typ == "approval.responded":
            rid = str(ev.get("request_id") or "")
            if p["stan"] == "czeka_na_zgode" and (not rid or rid == (p.get("zgoda") or {}).get("request_id")):
                self._przejdz(p, "pracuje", zgoda=None)
        elif typ == "run.steered":
            self._nadaj(p, "przebieg.komentarz", {"tekst": "", "typ": "dopisano", "przyjete": bool(ev.get("accepted", True))})
        elif typ in ZDARZENIA_KONCOWE:
            self._koniec_ze_statusu(p, {**ev, "status": typ.split(".", 1)[1]})
            return True
        self._zapisz_goraca(self.db.przebieg(pid) or p)
        return False

    def _krok(self, ev: Mapping) -> dict:
        nazwa = str(ev.get("tool") or "?")
        podglad = str(ev.get("preview") or "")
        e = self.etykieta(nazwa, {"command": podglad, "path": podglad}) if self.etykieta else {}
        return {"ts": float(ev.get("timestamp") or self.zegar()), "narzedzie": nazwa, "verb": e.get("verb", nazwa),
                "verb_en": e.get("verb_en", nazwa), "detail": e.get("detail", "")[:140], "czas_ms": None, "blad": False,
                "podglad": podglad[:PODGLAD_MAKS]}

    def _zaplanuj_delte(self, pid: str) -> None:
        dz = self._dzienniki.get(pid)
        if dz is None or dz.zaplanowana:
            return
        dz.zaplanowana = True
        asyncio.get_running_loop().call_later(DELTA_S, self._wyslij_delte, pid)

    def _wyslij_delte(self, pid: str) -> None:
        dz = self._dzienniki.get(pid)
        if dz is None:
            return
        dz.zaplanowana = False
        if not dz.oczekuje:
            return
        tekst, dz.oczekuje = dz.oczekuje, ""
        p = self.db.przebieg(pid)
        if p is not None:
            self._nadaj(p, "przebieg.delta", {"tekst": tekst})

    # =========================================================================================== zgoda
    def _prosba_o_zgode(self, p: dict, ev: Mapping) -> dict:
        rid = str(ev.get("request_id") or "")
        if rid and rid in self._wygasle:
            return p
        od = float(ev.get("timestamp") or self.zegar())
        wybory = [str(c) for c in (ev.get("choices") or ["once", "deny"])]
        zgoda = {"request_id": rid, "od": od, "wygasa_at": od + float(self.czas_zgody(p["agent"])), "wygasla": False,
                 "ryzyko": ryzyko(ev), "opis": self.utajnij(str(ev.get("description") or ""))[:500],
                 "polecenie": self.utajnij(str(ev.get("command") or ""))[:2000], "wybory": wybory,
                 "klucz_wzorca": str(ev.get("pattern_key") or "")}
        if p["stan"] in ("przyjety", "czeka_na_ture", "pracuje", "czeka_na_zgode"):
            p = self._przejdz(p, "czeka_na_zgode", zgoda=zgoda)
            self._nadaj(p, "przebieg.zgoda", {"zgoda": zgoda})
        return p

    def _wygas(self, p: dict) -> dict:
        z = dict(p.get("zgoda") or {})
        if z.get("request_id") in self._odpowiadane:     # odpowiedź właściciela właśnie idzie do bramy
            return p
        if z.get("request_id"):
            self._wygasle[z["request_id"]] = self.zegar()
        z["wygasla"] = True
        if p["stan"] == "czeka_na_zgode":
            p = self._przejdz(p, "pracuje", zgoda=z)
        else:
            p = self._zmien(p, zgoda=z)
        self._nadaj(p, "przebieg.zgoda", {"zgoda": z})
        self.log(f"jarvo-hq: przebieg {p['id']}: czas na zgodę minął")
        return p

    async def zgoda(self, pid: str, wybor: str, request_id: str) -> dict:
        p = self._wez(pid)
        z = p.get("zgoda") or {}
        wygasla = Blad(409, "zgoda_wygasla", "Czas minął — polecenie nie zostało wykonane.",
                       "Time is up — the command did not run.")
        if not z or z.get("request_id") != request_id or p["stan"] in STANY_KONCOWE:
            raise wygasla
        if z.get("wygasla") or self.zegar() >= float(z.get("wygasa_at") or 0):
            if not z.get("wygasla"):
                self._wygas(p)
            raise wygasla
        if wybor not in (z.get("wybory") or []):
            raise Blad(422, "zly_wybor", "Taki wybór nie był proponowany.", "That choice was not offered.")
        if request_id in self._odpowiadane:
            raise Blad(409, "zgoda_w_toku", "Odpowiedź na tę prośbę już idzie do agenta.",
                       "An answer to this request is already on its way.")
        self._odpowiadane.add(request_id)
        try:
            await self.brama.zgoda(p["agent"], p["run_id"], wybor, request_id)
        except self.BladBramy as e:
            self._odpowiadane.discard(request_id)
            if e.status == 409 or e.typ in ("approval_not_pending", "approval_not_active"):
                q = self.db.przebieg(pid)
                if q and (q.get("zgoda") or {}).get("request_id") == request_id:
                    self._wygas(q)
                raise wygasla from None
            raise Blad(503, "brama", "Jarvo chwilowo nie odpowiada — spróbuj jeszcze raz.",
                       "Jarvo is not responding right now — try again.") from None
        except BaseException:
            self._odpowiadane.discard(request_id)
            raise
        self._odpowiadane.discard(request_id)
        # w czasie odpowiedzi mogła przyjść następna prośba (inny request_id): tej nie czyścimy
        p = self._wez(pid)                          # wątek mógł zostać usunięty na stałe w trakcie: 404
        if p["stan"] == "czeka_na_zgode" and (p.get("zgoda") or {}).get("request_id") == request_id:
            p = self._przejdz(p, "pracuje", zgoda=None)
        self.log(f"jarvo-hq: przebieg {pid}: zgoda {wybor}")
        return p

    # =========================================================================================== stop, dopisz
    async def stop(self, pid: str) -> dict:
        p = self._wez(pid)
        if p["stan"] == "zatrzymywanie":
            if p.get("stop_lokalny") and pid not in self._stop_proby:
                return p                                # stop doszedł do bramy: czekamy na koniec tury
            # poprzedni stop nie doszedł (albo zatrzymuje brama, nie my): drugi Stop wysyła go od razu
            self._stop_proby.pop(pid, None)
            self._wstrzymaj_kolejke(p)
            if not p.get("stop_lokalny"):
                p = self._zmien(p, stop_lokalny=True)
            await self._stop_bramy(p)
            return self.db.przebieg(pid) or p
        if p["stan"] not in ("wysylanie",) + STANY_Z_PRZEBIEGIEM:
            raise Blad(409, "nieaktywny", "Ta praca już się nie toczy.", "This run is not active.")
        self._wstrzymaj_kolejke(p)
        if p["stan"] == "wysylanie":                    # 202 jeszcze nie przyszło: stop zaraz po przyjęciu
            return self._zmien(p, stop_lokalny=True)
        p = self._przejdz(p, "zatrzymywanie", stop_lokalny=True)
        if not p.get("run_id"):
            # tura tylko z osi czasu (po konflikcie klucza): bramie nie ma czego wysłać, przebieg kończy kontrola
            # z state.db, gdy tura się skończy (kolejka członka już wstrzymana)
            self.log(f"jarvo-hq: przebieg {pid}: stop bez run_id, czekam na koniec tury w state.db")
        await self._stop_bramy(p)
        return self.db.przebieg(pid) or p              # wątek usunięty na stałe w trakcie: ostatni znany wiersz

    def _wstrzymaj_kolejke(self, p: Mapping) -> None:
        for q in self.db.przebiegi_watku(p["watek_id"], aktywne=True):
            if (q["id"] != p["id"] and q["agent"] == p["agent"] and (q.get("rola") or "rozmowa") == (p.get("rola") or "rozmowa")
                    and q["stan"] == "kolejka" and q.get("powod") != "wstrzymane"):
                self._przejdz(q, "kolejka", powod="wstrzymane")

    async def _stop_bramy(self, p: Mapping) -> None:
        if not p.get("run_id"):
            return
        if p["stan"] != "zatrzymywanie":
            p = self._przejdz(p, "zatrzymywanie", stop_lokalny=True)
        await self._stop_w_bramie(p["id"], p["agent"], p["run_id"])

    async def _stop_w_bramie(self, pid: str, agent: str, run_id: str, *, sierota: bool = False) -> None:
        """POST stopu. Chwilowy błąd = wpis w `_stop_proby` (z agentem i run_id): kontrola ponawia go w tle także
        wtedy, gdy wiersza przebiegu już nie ma (`sierota`: wątek usunięty na stałe, praca w bramie trwa dalej)."""
        try:
            await self.brama.stop(agent, run_id)
        except self.BladBramy as e:
            if e.kod in ("nieaktywny", "konflikt", "brak"):    # przebieg w bramie już się nie toczy (albo go nie ma)
                self._stop_proby.pop(pid, None)
                if e.kod == "brak" or self.db.przebieg(pid) is None:
                    return
                try:
                    st = await self.brama.stan(agent, run_id)
                except self.BladBramy:
                    return
                if st.get("status") in BRAMA_KONCOWE:
                    self._koniec_ze_statusu(self.db.przebieg(pid), st)
                return
            teraz = self.zegar()
            byl = self._stop_proby.get(pid) or {"n": 0, "od": teraz, "sierota": sierota}
            self._stop_proby[pid] = {**byl, "n": byl["n"] + 1, "at": teraz, "agent": agent, "run_id": run_id,
                                     "sierota": byl["sierota"] or sierota}
            self.log(f"jarvo-hq: przebieg {pid}: stop nieudany ({e.kod}), próba {byl['n'] + 1}, ponowię")
            return
        self._stop_proby.pop(pid, None)
        if sierota:
            self.log(f"jarvo-hq: przebieg {pid}: zatrzymany w bramie (bez wiersza)")

    def _ponow_stopy(self, teraz: float) -> None:
        """Kontrola: nieudane stopy ponawiane w tle (co 5 s, po 5 próbach co 30 s), dopóki przebieg jest
        w `zatrzymywanie` albo (sierota, bez wiersza) najwyżej godzinę; wolna brama nie wstrzymuje kontroli."""
        for pid, s in list(self._stop_proby.items()):
            if pid in self._stop_w_locie:
                continue
            p = self.db.przebieg(pid)
            sierota = s["sierota"] or p is None
            if not sierota and not (p["stan"] == "zatrzymywanie" and p.get("stop_lokalny")):
                self._stop_proby.pop(pid, None)     # przebieg się skończył albo zatrzymuje go już brama
                continue
            if sierota and teraz - s["od"] > STOP_SIEROTA_S:
                self._stop_proby.pop(pid, None)
                self.log(f"jarvo-hq: przebieg {pid}: stop bez wiersza nieudany od godziny, przestaję ponawiać")
                continue
            if teraz - s["at"] < (STOP_PONOW_S if s["n"] < STOP_PROBY else STOP_PONOW_WOLNO_S):
                continue
            if p is None and not s["sierota"]:
                self._stop_proby[pid] = {**s, "sierota": True}
            self._stop_w_locie.add(pid)
            self._zadanie(self._ponow_stop(pid, s["agent"], s["run_id"], sierota))

    async def _ponow_stop(self, pid: str, agent: str, run_id: str, sierota: bool) -> None:
        try:
            await self._stop_w_bramie(pid, agent, run_id, sierota=sierota)
        finally:
            self._stop_w_locie.discard(pid)

    async def dopisz(self, pid: str, tekst: str, *, wpis_id: str | None = None) -> dict:
        """Steer do trwającej tury `pid` (przebieg `pracuje`). Zwraca nowy przebieg `dopisany`. Wiersz powstaje przed
        steerem (koniec tamtej tury w trakcie steera go widzi i rozstrzyga po `pending_steer`), steer odrzucony =
        wiersz usunięty, bez śladu w strumieniu."""
        p = self._wez(pid)
        if p["stan"] not in ("pracuje", "czeka_na_ture", "przyjety") or not p.get("run_id"):
            raise Blad(409, "nieaktywny", "Agent teraz nie pracuje — wiadomość może poczekać w kolejce.",
                       "The agent is not working right now — the message can wait in the queue.")
        q = self.db.dodaj_przebieg(watek_id=p["watek_id"], wpis_id=wpis_id, agent=p["agent"], rola=p.get("rola") or "rozmowa",
                                   zrodlo="wlasciciel", lancuch_id=p["lancuch_id"], stan="dopisany", powod="",
                                   dopisany_do=pid, payload={"prosba": tekst, "obrazy": []})
        self._w_locie.add(q["id"])
        try:
            await self.brama.dopisz(p["agent"], p["run_id"], tekst)
        except BaseException as e:
            self._w_locie.discard(q["id"])
            self.db.usun_przebieg(q["id"])
            if isinstance(e, self.BladBramy):
                if e.kod in ("nieaktywny", "konflikt", "brak"):
                    raise Blad(409, "nieaktywny", "Agent właśnie kończy — wiadomość może poczekać w kolejce.",
                               "The agent is finishing — the message can wait in the queue.") from None
                raise Blad(503, "brama", "Jarvo chwilowo nie odpowiada — spróbuj jeszcze raz.",
                           "Jarvo is not responding right now — try again.") from None
            raise
        self._w_locie.discard(q["id"])
        self.log(f"jarvo-hq: przebieg {q['id']} {q['agent']} —→dopisany (do {pid})")
        return self._po_steerze(q)

    async def dopisz_kolejke(self, pid: str, *, klucz: str | None = None) -> dict:
        """„Dopisz do trwającej pracy” na wiadomości czekającej w `kolejka(zajety_agent)`. Przebieg idzie do
        `dopisany` przed steerem (dyspozytor nie wyśle go w tym czasie drugi raz) z `payload.klucz_dopisz` (powtórzone
        żądanie dostaje ten sam przebieg); steer odrzucony = wraca do kolejki, a gdy cel w tym czasie zatrzymano,
        jako `wstrzymane` (jak reszta kolejki tego członka po Stopie)."""
        q = self._wez(pid)
        if klucz and (q.get("payload") or {}).get("klucz_dopisz") == klucz:
            return q
        if q["stan"] != "kolejka":
            raise Blad(409, "nieaktywny", "Ta wiadomość już nie czeka w kolejce.", "This message is no longer queued.")
        akt = next((a for a in self.db.przebiegi_watku(q["watek_id"], aktywne=True)
                    if a["agent"] == q["agent"] and (a.get("rola") or "rozmowa") == (q.get("rola") or "rozmowa")
                    and a["stan"] in ("pracuje", "czeka_na_ture", "przyjety") and a.get("run_id")), None)
        if akt is None:
            raise Blad(409, "nieaktywny", "Agent teraz nie pracuje — wiadomość pójdzie normalnie.",
                       "The agent is not working right now — the message will be sent normally.")
        payload = dict(q.get("payload") or {})
        tekst = payload.get("prosba") or ""
        powod = q.get("powod") or "start"
        q = self._przejdz(q, "dopisany", dopisany_do=akt["id"],
                          **({"payload": {**payload, "klucz_dopisz": klucz}} if klucz else {}))
        if q["stan"] != "dopisany":
            raise Blad(409, "nieaktywny", "Ta wiadomość już nie czeka w kolejce.", "This message is no longer queued.")
        self._w_locie.add(pid)
        try:
            await self.brama.dopisz(akt["agent"], akt["run_id"], tekst)
        except BaseException as e:
            self._w_locie.discard(pid)
            cel = self.db.przebieg(akt["id"])
            if cel is not None and (cel.get("stop_lokalny") or cel["stan"] in ("zatrzymywanie", "zatrzymane")):
                powod = "wstrzymane"                 # Stop celu w trakcie steera: ta wiadomość też czeka na właściciela
            self._przejdz(q, "kolejka", powod=powod, dopisany_do=None, **({"payload": payload} if klucz else {}))
            self._budz()
            if isinstance(e, self.BladBramy):
                raise Blad(409, "nieaktywny", "Agent właśnie kończy — wiadomość pójdzie normalnie.",
                           "The agent is finishing — the message will be sent normally.") from None
            raise
        self._w_locie.discard(pid)
        return self._po_steerze(q)

    def _po_steerze(self, q: Mapping) -> dict:
        """Steer przyjęty. Gdy tura celu skończyła się w trakcie (jej koniec pominął przebieg w locie), rozstrzyga od
        razu z podziału `pending_steer` zapisanego przy końcu celu (nierozstrzygnięty czeka na kontrolę)."""
        q = self.db.przebieg(q["id"]) or dict(q)
        cel = self.db.przebieg(q.get("dopisany_do") or "")
        if q["stan"] == "dopisany" and (cel is None or cel["stan"] in STANY_KONCOWE):
            q = self._dopisany_po_koncu(q, cel)
            if q.get("stan") != "dopisany":
                return q
        self._nadaj_stan(q)
        self._status_watku(q["watek_id"])
        return q

    @staticmethod
    def _linie(tekst: Any) -> list[str]:
        """Tekst dopisku tak, jak go trzyma Hermes (`strip`), jako lista linii; pusty = []."""
        t = str(tekst or "").strip()
        return t.split("\n") if t else []

    @staticmethod
    def _podzial(linie: list[str], teksty: list[list[str]]) -> set[int] | None:
        """Jedyny podział `linie` (`pending_steer`) na całe teksty dopisków, po kolei, każdy najwyżej raz: indeksy
        tych, które wróciły. None = takiego podziału nie ma albo jest ich kilka (nie wiadomo, który wrócił)."""
        n, k = len(linie), len(teksty)
        ile = [[0] * (k + 1) for _ in range(n + 1)]     # ile[i][j]: sposoby pokrycia linie[i:] tekstami j.. (do 2)
        for j in range(k + 1):
            ile[n][j] = 1
        for i in range(n - 1, -1, -1):
            for j in range(k - 1, -1, -1):
                t = teksty[j]
                w = ile[i][j + 1]
                if t and linie[i:i + len(t)] == t:
                    w += ile[i + len(t)][j + 1]
                ile[i][j] = min(w, 2)
        if ile[0][0] != 1:
            return None
        wrocily, i = set(), 0
        for j, t in enumerate(teksty):
            if t and linie[i:i + len(t)] == t and ile[i + len(t)][j + 1] == 1:
                wrocily.add(j)
                i += len(t)
        return wrocily

    def _rozdziel(self, kandydaci: list[dict], pending: Any, *, niepewne: bool) -> dict[str, str]:
        """Dopiski celu po końcu jego tury: id → `wrocil` (tekst w `pending_steer`), `wlaczony` albo `sprawdz`
        (kontrola szuka wiersza `steer` w state.db). `niepewne`: tura przerwana twardo, Hermes mógł zgubić
        niedostarczony steer, więc niezwrócony tekst nie znaczy, że agent go przeczytał."""
        if pending is _NIEZNANE:
            return {q["id"]: "sprawdz" for q in kandydaci}
        if isinstance(pending, (list, tuple)):
            pending = "\n".join(str(x) for x in pending)
        linie = str(pending).split("\n") if pending else []
        wrocily = self._podzial(linie, [self._linie((q.get("payload") or {}).get("prosba")) for q in kandydaci])
        if wrocily is None:
            return {q["id"]: "sprawdz" for q in kandydaci}
        zostal = "sprawdz" if niepewne else "wlaczony"
        # dopisek sprzed restartu: steer mógł nie dojść do bramy, więc niezwrócony tekst też idzie do sprawdzenia
        return {q["id"]: ("wrocil" if i in wrocily else "sprawdz" if q["id"] in self._sprzed_startu else zostal)
                for i, q in enumerate(kandydaci)}

    def _dopisany_po_koncu(self, q: Mapping, cel: Mapping | None) -> dict:
        """`dopisany`, gdy tura celu już się skończyła, według rozstrzygnięcia z końca celu: tekst wrócił → kolejka
        (`wstrzymane` po Stopie właściciela, inaczej `zajety_agent`), wszedł do tury → `wlaczony`; nieznane = zostaje
        `dopisany`, kontrola sprawdza state.db (`_dopisany_z_osi`)."""
        dz = self._dzienniki.get(cel["id"]) if cel else None
        decyzja = dz.dopisane.get(q["id"]) if dz is not None else None
        if decyzja == "wrocil":
            return self._przejdz(q, "kolejka", powod="wstrzymane" if (cel or {}).get("stop_lokalny") else "zajety_agent")
        if decyzja == "wlaczony":
            self._koniec(q, "wlaczony")
        return self.db.przebieg(q["id"]) or dict(q)

    async def _dopisany_z_osi(self, q: Mapping) -> None:
        """Kontrola: `dopisany` bez rozstrzygnięcia z `pending_steer` (koniec bez statusu, restart, niejasny podział,
        twarde przerwanie). Wiersz `steer` z tym tekstem w rodowodzie członka (od zapisu dopisku) = agent go dostał
        (`wlaczony`); inaczej `kolejka(wstrzymane)`: właściciel zdecyduje, tekst nie ginie i nie idzie sam drugi raz."""
        tekst = str((q.get("payload") or {}).get("prosba") or "")
        steery = await self._w_tle(self.czytnik.steery_po, q["agent"], self._rodowod(q),
                                   float(q.get("utworzony_at") or 0) - OKNO_SHA)
        q = self.db.przebieg(q["id"])
        if q is None or q["stan"] != "dopisany":
            return
        self._sprzed_startu.discard(q["id"])
        if tekst.strip() and any(self.czytnik.dopisek_w_steerze(t, tekst) for t in steery or []):
            self._koniec(q, "wlaczony")
        else:
            self._przejdz(q, "kolejka", powod="wstrzymane")

    # =========================================================================================== koniec
    def _koniec_ze_statusu(self, p: Mapping | None, st: Mapping) -> None:
        if p is None:
            return
        p = self.db.przebieg(p["id"]) or p
        if p["stan"] in STANY_KONCOWE:
            return
        status = str(st.get("status") or "")
        blad = None
        if status == "completed":
            stan = "gotowe"
        elif status == "failed":
            stan = "blad"
            powod = st.get("turn_exit_reason")
            # właściciel czyta krótkie zdanie po polsku; surowy błąd Hermesa (bez sekretów) idzie do „Szczegóły”
            surowy = self.utajnij(str(st.get("error") or ""))[:300]
            if powod and str(powod) in PRZYCZYNY:
                blad = {"kod": "model", "komunikat": przyczyna(powod), "szczegoly": surowy}
            else:
                blad = {"kod": "model", "komunikat": "Praca się nie udała", "komunikat_en": "The work failed",
                        "szczegoly": " · ".join(x for x in (str(powod or ""), surowy) if x)}
            blad["powod_hermesa"] = powod
        elif status == "cancelled":
            stan = "zatrzymane" if p.get("stop_lokalny") else "przerwane"
        elif status == "interrupted":
            stan = "przerwane"
        else:
            return
        dz = self.dziennik(p["id"])
        wynik = st.get("output")
        if isinstance(wynik, str) and wynik and (p.get("odlaczony") or not dz.tekst):
            dz.tekst = wynik[:TEKST_MAKS]
            dz.oczekuje = ""
        # Hermes dokłada `pending_steer` tylko, gdy coś zostało: brak pola przy statusie bramy = nic nie wróciło
        self._koniec(p, stan, blad=blad, pending=st.get("pending_steer") or "", uzycie=st.get("usage"))

    def _koniec(self, p: Mapping | None, stan: str, *, blad: dict | None = None, pending: Any = _NIEZNANE,
                uzycie: Any = None) -> None:
        """Stan końcowy: kroki z czasami (`przebieg.koniec` wysyła `_przejdz`), dopisane, aktywność wątku, budzik
        dyspozytora, sprzątanie pamięci przebiegu. `pending` (`pending_steer` bramy) domyślnie nieznane: koniec bez
        statusu bramy (`zgubione`, konflikt, tura z osi czasu) nie mówi, które dopiski agent przeczytał."""
        if p is None:
            return
        pid = p["id"]
        self._wyslij_delte(pid)
        dz = self._dzienniki.get(pid)
        pola: dict[str, Any] = {}
        if dz is not None and dz.kroki:
            pola["kroki"] = list(dz.kroki)
        if uzycie:
            pola["uzycie"] = uzycie
        if blad:
            pola["blad"] = blad
        z = (self.db.przebieg(pid) or p).get("zgoda")
        if z and not (z or {}).get("wygasla"):
            pola["zgoda"] = None
        p = self._przejdz(p, stan, **pola)
        if p["stan"] != stan:
            return
        if dz is not None:
            dz.koniec_at = self.zegar()
        for t in (self._odpytywane.pop(pid, None),):
            if t is not None and t is not asyncio.current_task():
                t.cancel()
        for slownik in (self._konflikty, self._brak_404, self._pierwszy_blad, self._pierwszy_429, self._stop_proby):
            slownik.pop(pid, None)
        self._stop_ponowiony.discard(pid)
        self._dopisane_po(p, stan, pending)
        if p.get("zrodlo") != "nadzor" and stan not in ("anulowane", "wlaczony"):
            self._aktywnosc_po(p, stan, dz)
        self._budz()

    def _dopisane_po(self, p: Mapping, stan: str, pending: Any) -> None:
        """Koniec tury `p`: wszystkie jej `dopisany` (także te, których steer jest jeszcze w drodze: podział liczy je
        razem, a rozstrzyga je potem `_po_steerze`) wg `pending_steer`. Rozstrzygnięcie zostaje w dzienniku celu."""
        dz = self.dziennik(p["id"])
        if dz.koniec_at is None:
            dz.koniec_at = self.zegar()
        kandydaci = [q for q in self.db.przebiegi_watku(p["watek_id"], aktywne=True)
                     if q["stan"] == "dopisany" and q.get("dopisany_do") == p["id"]]
        if not kandydaci:
            return
        dz.dopisane = self._rozdziel(kandydaci, pending, niepewne=stan in ("zatrzymane", "przerwane"))
        self._sprzed_startu.difference_update(q["id"] for q in kandydaci)
        for q in kandydaci:
            if q["id"] not in self._w_locie:
                self._dopisany_po_koncu(q, p)

    def _aktywnosc_po(self, p: Mapping, stan: str, dz: Dziennik | None) -> None:
        nazwa = self._nazwy().get(p["agent"], p["agent"])
        if stan == "gotowe":
            tekst = (dz.tekst if dz else "") or "gotowe"
        elif stan == "blad":
            tekst = "błąd — " + str((p.get("blad") or {}).get("komunikat") or "")
        elif stan == "zatrzymane":
            tekst = "zatrzymane"
        else:
            tekst = "praca przerwana"
        otwarty = p["watek_id"] in self.hub.subskrybowane_watki()
        w = self.db.aktywnosc(p["watek_id"], at=self.zegar(), podglad=f"{nazwa}: {tekst}",
                              nieprzeczytane_plus=0 if otwarty else 1, agent=p["agent"],
                              status="blad" if stan == "blad" else None)
        self._status_watku(p["watek_id"])
        w = self.db.watek(p["watek_id"]) or w
        if w:
            self.hub.nadaj("watek.zmiana", {"watek": watek_krotki(w)})

    # =========================================================================================== odpytywanie
    def _odpytuj_start(self, pid: str) -> None:
        if pid in self._odpytywane and not self._odpytywane[pid].done():
            return
        self._odpytywane[pid] = self._zadanie(self._odpytuj(pid))

    async def _odpytuj(self, pid: str) -> None:
        """Status przebiegu co 2 s, gdy strumień zdarzeń zginął (`odlaczony`); nigdy nie otwiera /events ponownie."""
        while self._dziala:
            p = self.db.przebieg(pid)
            if not p or p["stan"] in STANY_KONCOWE or not p.get("run_id"):
                break
            try:
                st = await self.brama.stan(p["agent"], p["run_id"])
            except self.BladBramy as e:
                if e.kod == "brak":
                    self._brak_404.setdefault(pid, self.zegar())
                await asyncio.sleep(self.odstep_odpytania)
                continue
            self._brak_404.pop(pid, None)
            p = self.db.przebieg(pid)
            if not p or p["stan"] in STANY_KONCOWE:
                break
            self._ze_statusu(p, st)
            p = self.db.przebieg(pid)
            if p is None or p["stan"] in STANY_KONCOWE:
                break
            await asyncio.sleep(self.odstep_odpytania)
        self._odpytywane.pop(pid, None)

    def _ze_statusu(self, p: dict, st: Mapping) -> None:
        s = str(st.get("status") or "")
        if s in BRAMA_KONCOWE:
            self._koniec_ze_statusu(p, st)
        elif s == "waiting_for_approval":
            a = st.get("approval") or {}
            rid = str(a.get("request_id") or "")
            if rid and rid not in self._wygasle and (p.get("zgoda") or {}).get("request_id") != rid:
                self._prosba_o_zgode(p, a)
        elif s == "running":
            if p["stan"] == "czeka_na_zgode":
                self._po_zgodzie(p)
        elif s == "stopping" and p["stan"] not in ("zatrzymywanie",):
            self._przejdz(p, "zatrzymywanie")

    # =========================================================================================== kontrola i strażnik
    async def _kontrola(self) -> None:
        """Co 1 s: nasz wiersz w state.db (→ `pracuje`), `czeka_na_ture`, wygaśnięcie zgody, konflikt klucza."""
        while self._dziala:
            try:
                await self.kontrola()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover
                self.log(f"jarvo-hq: kontrola przebiegów: {type(exc).__name__}")
            await asyncio.sleep(1.0)

    async def kontrola(self) -> None:
        teraz = self.zegar()
        self._ponow_stopy(teraz)
        for p in self.db.przebiegi_aktywne():
            pid = p["id"]
            p = self.db.przebieg(pid)               # lista sprzed sond tej pętli: każdy wiersz czytany na nowo
            if p is None or p["stan"] in STANY_KONCOWE or p["stan"] == "kolejka":
                continue
            if p["stan"] == "dopisany":             # cel skończył się: rozstrzygnięcie z jego końca albo z osi czasu
                if pid not in self._w_locie:
                    cel = self.db.przebieg(p.get("dopisany_do") or "")
                    if cel is None or cel["stan"] in STANY_KONCOWE:
                        p = self._dopisany_po_koncu(p, cel)
                        if p.get("stan") == "dopisany" and pid not in self._w_locie:
                            await self._dopisany_z_osi(p)
                continue
            if p["stan"] == "zatrzymywanie" and p.get("stop_lokalny") and pid in self._stop_proby:
                continue                            # stop ponawia `_ponow_stopy` (w tle)
            if p["stan"] == "czeka_na_zgode":
                z = p.get("zgoda") or {}
                if not z.get("wygasla") and z.get("request_id") not in self._odpowiadane \
                        and teraz >= float(z.get("wygasa_at") or teraz + 1):
                    self._wygas(p)
                continue
            if p.get("user_msg_id") and p["stan"] in ("przyjety", "czeka_na_ture"):
                self._przejdz(p, "pracuje")
                continue
            if not p.get("user_msg_id") and p.get("payload_sha") and p.get("wyslany_at"):
                rodowod = self._rodowod(p)
                mid = await self._w_tle(self.czytnik.nasz_wiersz, p["agent"], rodowod, p["payload_sha"],
                                        float(p["wyslany_at"]) - OKNO_SHA)
                p = self.db.przebieg(pid)
                if p is None or p["stan"] in STANY_KONCOWE:
                    continue
                if mid:
                    p = self.db.zmien_przebieg(pid, user_msg_id=mid)
                    if pid in self._konflikty:          # tura bez run_id: tylko z osi czasu
                        self._konflikty.pop(pid)
                        # Stop w czasie czekania na wiersz: tura trwa, ale stopu nie da się wysłać (bez run_id);
                        # `zatrzymywanie` do końca tury, który przyjdzie z osi czasu
                        self._przejdz(p, "zatrzymywanie" if p.get("stop_lokalny") else "pracuje", odlaczony=True)
                    elif p["stan"] in ("przyjety", "czeka_na_ture"):
                        self._przejdz(p, "pracuje")
                    continue
                if pid in self._konflikty and teraz - self._konflikty[pid] > KONFLIKT_S:
                    self._konflikty.pop(pid)
                    self._koniec(p, "blad", blad={"kod": "konflikt", "komunikat": "Wewnętrzny błąd aplikacji przy wysyłce."})
                    continue
                dz = self._dzienniki.get(pid)
                if (p["stan"] == "przyjety" and p.get("przyjety_at") and teraz - float(p["przyjety_at"]) >= CZEKA_NA_TURE_S
                        and (dz is None or dz.ostatnie_at is None)):
                    d = await self._w_tle(self.czytnik.dzierzawa, p["agent"], rodowod, teraz)
                    p = self.db.przebieg(pid)
                    if d and p and p["stan"] == "przyjety":
                        self._przejdz(p, "czeka_na_ture")
            elif p["stan"] in ("pracuje", "zatrzymywanie") and not p.get("run_id") and p.get("user_msg_id"):
                # tura „tylko z osi czasu” (po konflikcie klucza, też po Stopie, którego brama nie dostanie): koniec,
                # gdy dzierżawa wolna i jest odpowiedź; tura bez odpowiedzi kończy strażnik (`zgubione`)
                rodowod = self._rodowod(p)
                d = await self._w_tle(self.czytnik.dzierzawa, p["agent"], rodowod, teraz)
                if not d and await self._w_tle(self.czytnik.odpowiedz_po, p["agent"], rodowod, int(p["user_msg_id"])):
                    self._koniec(self.db.przebieg(pid), "gotowe")
            dz = self._dzienniki.get(pid)
            if dz is not None:
                self._zapisz_goraca(self.db.przebieg(pid) or p)

    async def _straznik(self) -> None:
        while self._dziala:
            await asyncio.sleep(10.0)
            try:
                await self.straznik()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover
                self.log(f"jarvo-hq: strażnik: {type(exc).__name__}")

    async def straznik(self) -> None:
        """Co 10 s: cisza > 90 s → status bramy; `zgubione` tylko gdy brama nie prowadzi przebiegu, nikt nie trzyma
        dzierżawy i od 10 min (po 404: od 60 s) nie przybył żaden wiersz; tura bez `run_id` (tylko z osi czasu) tak
        samo, bez pytania bramy. Nigdy automatyczny stop."""
        teraz = self.zegar()
        for p in self.db.przebiegi_aktywne():
            pid = p["id"]
            # `czeka_na_ture` też: brama mogła zgubić przebieg (restart, aktualizacja), a tura nie przyjdzie nigdy
            if p["stan"] in ("kolejka", "dopisany", "czeka_na_zgode"):
                continue
            # tura tylko z osi czasu (bez run_id, nasz wiersz jest): bramy nie da się zapytać, liczą dzierżawa i wiersze
            z_osi = not p.get("run_id") and bool(p.get("user_msg_id")) and p["stan"] in ("pracuje", "zatrzymywanie")
            if not p.get("run_id") and not z_osi:
                continue
            start = float(p.get("wyslany_at") or p["utworzony_at"])
            if teraz - start > DLUGO_S and pid not in self._dlugo:
                self._dlugo.add(pid)
                self._nadaj_stan(p)
            dz = self._dzienniki.get(pid)
            ostatnie = (dz.ostatnie_at if dz and dz.ostatnie_at else None) or p.get("ostatnie_zdarzenie_at") \
                or p.get("przyjety_at") or start
            if teraz - float(ostatnie) <= CISZA_S:
                continue
            brak, st = False, {}
            try:
                if not z_osi:
                    st = await self.brama.stan(p["agent"], p["run_id"])
            except self.BladBramy as e:
                if e.kod != "brak":
                    continue
                brak, st = True, {}
                self._brak_404.setdefault(pid, teraz)
            s = str(st.get("status") or "")
            if s in BRAMA_KONCOWE:
                self._koniec_ze_statusu(self.db.przebieg(pid), st)
                continue
            if s in ("running", "queued", "stopping", "waiting_for_approval"):
                continue
            rodowod = self._rodowod(p)
            if await self._w_tle(self.czytnik.dzierzawa, p["agent"], rodowod, teraz):
                continue
            stan_s = await self._w_tle(self.czytnik.stan_sesji, p["agent"], rodowod)
            byl = self._wiersze.get(pid)
            if byl is None or byl[0] != stan_s["max_id"]:
                self._wiersze[pid] = (stan_s["max_id"], teraz)
                continue
            prog = ZGUBIONY_404_S if brak else ZGUBIONY_S
            if teraz - byl[1] >= prog:
                self.log(f"jarvo-hq: przebieg {pid}: zgubiony (brama: {'bez run_id' if z_osi else s or '404'})")
                self._koniec(self.db.przebieg(pid), "zgubione")
        for pid, dz in list(self._dzienniki.items()):
            if dz.koniec_at is None and self.db.przebieg(pid) is None:
                dz.koniec_at = teraz - DZIENNIK_PO_KONCU_S - 1     # wątek usunięty na stałe w trakcie pracy
                for slownik in (self._konflikty, self._brak_404, self._pierwszy_blad, self._pierwszy_429):
                    slownik.pop(pid, None)
                self._stop_ponowiony.discard(pid)
            if dz.koniec_at is not None and teraz - dz.koniec_at > DZIENNIK_PO_KONCU_S:
                self._dzienniki.pop(pid, None)
                self._wiersze.pop(pid, None)
                self._dlugo.discard(pid)
        for rid, at in list(self._wygasle.items()):
            if teraz - at > WYGASLE_PAMIEC_S:
                self._wygasle.pop(rid, None)

    # =========================================================================================== ponów
    async def ponow(self, pid: str) -> dict:
        """Nowy przebieg po `blad`/`przerwane`/`zgubione`/`zatrzymane`: krótka kontynuacja, gdy nasz wiersz jest
        w state.db (treść właściciela nie powtarza się), inaczej cała prośba z nowym blokiem kontekstu."""
        p = self._wez(pid)
        if p["stan"] not in ("blad", "przerwane", "zgubione", "zatrzymane"):
            raise Blad(409, "nieaktywny", "Ponowić można pracę, która się nie udała albo została przerwana.",
                       "Only a failed or interrupted run can be retried.")
        juz = self._ponowienie(p)
        if juz is not None:                         # drugi klik, druga karta, ponowione żądanie: to samo ponowienie
            return juz
        payload = p.get("payload") or {}
        if not payload:
            raise Blad(409, "brak_tresci", "Treść tej wiadomości już nie jest przechowywana.",
                       "This message's content is no longer stored.")
        jest = p.get("user_msg_id")
        if not jest and p.get("payload_sha") and p.get("wyslany_at"):
            jest = await self._w_tle(self.czytnik.nasz_wiersz, p["agent"], self._rodowod(p), p["payload_sha"],
                                     float(p["wyslany_at"]) - OKNO_SHA)
            juz = self._ponowienie(p)               # równoległe Ponów w czasie sondy
            if juz is not None:
                return juz
        if jest:
            powod = {"przerwane": "praca przerwana", "zgubione": "połączenie z pracą zerwane",
                     "zatrzymane": "zatrzymana"}.get(p["stan"]) or przyczyna((p.get("blad") or {}).get("powod_hermesa")).lower()
            tekst = KONTYNUACJA.format(powod=powod)
            q = self.zlec(watek_id=p["watek_id"], wpis_id=p.get("wpis_id"), agent=p["agent"], prosba=tekst,
                          rola=p.get("rola") or "rozmowa", zrodlo=p.get("zrodlo") or "wlasciciel", autor=p.get("autor"),
                          lancuch_id=p["lancuch_id"], tekst=tekst, ponowienie_z=pid, hop=int(p.get("hop") or 0))
        else:
            q = self.zlec(watek_id=p["watek_id"], wpis_id=p.get("wpis_id"), agent=p["agent"],
                          prosba=payload.get("prosba") or "", obrazy=payload.get("obrazy") or [],
                          rola=p.get("rola") or "rozmowa", zrodlo=p.get("zrodlo") or "wlasciciel", autor=p.get("autor"),
                          lancuch_id=p["lancuch_id"], ponowienie_z=pid, hop=int(p.get("hop") or 0))
        self.log(f"jarvo-hq: przebieg {q['id']}: ponowienie {pid} ({'kontynuacja' if jest else 'cała treść'})")
        return q

    def _ponowienie(self, p: Mapping) -> dict | None:
        """Ponowienie `p`, które trwa albo się udało (drugi klik dostaje je, bez drugiej wysyłki). Anulowane albo
        nieudane się nie liczy: następne Ponów tworzy nowe."""
        return next((q for q in reversed(self.db.przebiegi_watku(p["watek_id"])) if q.get("ponowienie_z") == p["id"]
                     and (q["stan"] in STANY_AKTYWNE or q["stan"] in ("gotowe", "wlaczony"))), None)

    # =========================================================================================== zewnętrzne
    def zmiana_stanu(self, agent: str | None = None) -> None:
        """Obserwator: state.db profilu się zmienił (dzierżawa mogła się zwolnić, nasz wiersz mógł się pojawić)."""
        self._budz()

    def aktywne_liczba(self) -> int:
        return sum(1 for p in self.db.przebiegi_aktywne() if p["stan"] in STANY_W_LIMICIE)

    def zdrowie(self) -> dict:
        return {"limit": self.limit, "sluchacze": len(self._sluchacze), "odpytywane": len(self._odpytywane),
                "dzienniki": len(self._dzienniki)}
