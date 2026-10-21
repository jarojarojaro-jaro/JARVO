"""Klient bramy Hermesa dla silnika rozmów (docs/HQ.md „Rozmowy”): `/v1/runs` i sesje profilu przez jeden gateway
z `multiplex_profiles` (`/p/<profil>/…`; profil domyślny bez prefiksu, `jarvo` pod `/p/jarvo`).

- **Klucze.** `API_SERVER_KEY` z `.env` profilu czyta proces dashboardu (`Klucze`, pamięć 60 s); klucz nie trafia do
  przeglądarki, do dziennika ani do odpowiedzi.
- **Przebieg.** `POST /v1/runs {input, session_id[, author]}` z `Idempotency-Key: jarvo-<id przebiegu>` → 202
  `{run_id, status}`. Brama liczy odcisk z całego ciała JSON, więc ciało jest czystą funkcją tego, co przebieg ma
  zapisane przed pierwszym POST (`cialo`, `cialo_sha`): ponowienie po restarcie daje to samo ciało i ten sam przebieg.
- **Zdarzenia.** `GET /v1/runs/{id}/events`: ramki `data: <json>` bez linii `event:` (nazwa w polu `event`),
  `: keepalive` co 10 s. Strumień ma jednego słuchacza i brama zapomina kolejkę, gdy słuchacz odejdzie, więc po
  zerwaniu nie otwieramy go ponownie: rejestr przechodzi na odpytywanie stanu (`odlaczony`).
- **Błędy** jako `BladBramy(kod)`: `niedostepna` (połączenie, czas, 502/503/504; `dotarlo` = żądanie mogło dojść
  do bramy: czas odpowiedzi minął albo połączenie zerwane po wysłaniu), `limit` (429, `ponow_za` z Retry-After),
  `klucz` (401/403), `odrzucone` (400/404/413/422), `brak` (404 przebiegu albo sesji), `konflikt` (409; `typ` niesie
  kod bramy, np. `idempotency_key_conflict`, `approval_not_pending`), `nieaktywny` (409 `run_not_active` /
  `run_not_accepting_steer`).
- **Ścieżki.** Id sesji (`^[A-Za-z0-9_.:-]{1,128}$`) i przebiegu (`^[A-Za-z0-9_-]{1,128}$`) sprawdzane przed złożeniem
  URL-a z kluczem profilu (wartości przychodzą z state.db, odpowiedzi bramy i importu); httpx bez zmiennych proxy
  środowiska (`trust_env=False`): brama jest zawsze lokalna, klucz nie wyjdzie przez obce proxy.
Czysty Python + httpx (jest w procesie dashboardu); testy z atrapą bramy: tests/test_silnik_rozmow.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from pathlib import Path
from typing import Any, AsyncIterator, Callable

import httpx

PROFIL_RE = re.compile(r"^[a-z0-9-]+$")
SESJA_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")          # jak ochrona.SESJA_RE
PRZEBIEG_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
KLUCZ_TTL = 60.0
CIALO_MAX = 9_500_000              # brama odrzuca > 10 000 000 bajtów (MAX_REQUEST_BYTES); zapas na nagłówki
CZAS = httpx.Timeout(15.0, connect=3.0)
CZAS_ZDARZEN = httpx.Timeout(15.0, connect=3.0, read=30.0)     # keepalive co 10 s: 30 s ciszy = brama zawieszona
AUTOR_NADZOR = {"id": "bot:jarvo-app", "name": "Aplikacja Jarvo · nadzór", "is_bot": True}
AUTOR_JARVO = {"id": "bot:jarvo", "name": "Jarvo", "is_bot": True}


class BladBramy(Exception):
    """Błąd bramy w kształcie, który rejestr umie obsłużyć (kod, status HTTP, ponów za s, kod błędu bramy)."""

    def __init__(self, kod: str, komunikat: str = "", *, status: int | None = None, ponow_za: float | None = None,
                 typ: str | None = None, dotarlo: bool = False):
        super().__init__(komunikat or kod)
        self.kod = kod
        self.komunikat = komunikat
        self.status = status
        self.ponow_za = ponow_za
        self.typ = typ
        self.dotarlo = dotarlo


# połączenie nie powstało albo żądanie nie wyszło z puli: brama na pewno go nie dostała
NIE_DOTARLO = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


def _sesja(sid: str) -> str:
    if not SESJA_RE.fullmatch(str(sid or "")) or sid in (".", ".."):      # „..” httpx skróciłby w ścieżce
        raise BladBramy("odrzucone", "zły identyfikator sesji")
    return sid


def _przebieg(run_id: str) -> str:
    if not PRZEBIEG_RE.fullmatch(str(run_id or "")):
        raise BladBramy("odrzucone", "zły identyfikator przebiegu")
    return run_id


def klient_http(**kw) -> httpx.AsyncClient:
    """httpx do lokalnej bramy: bez proxy ze zmiennych środowiska (klucz profilu nie wyjdzie przez obce proxy)."""
    return httpx.AsyncClient(trust_env=False, **kw)


def _czytaj_env(sciezka: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for linia in sciezka.read_text(encoding="utf-8").splitlines():
            if "=" in linia and not linia.lstrip().startswith("#"):
                k, _, v = linia.partition("=")
                out[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


class Klucze:
    """`API_SERVER_KEY` profilu z jego `.env` (domyślny: `<home>/.env`), w pamięci 60 s. Wywołanie: `klucze(agent)`."""

    def __init__(self, home: Path | str, *, ttl: float = KLUCZ_TTL, zegar: Callable[[], float] = time.monotonic):
        self.home = Path(home)
        self.ttl = ttl
        self.zegar = zegar
        self._pamiec: dict[str, tuple[float, str | None]] = {}

    def sciezka(self, agent: str) -> Path:
        if agent in ("", "default"):
            return self.home / ".env"
        if not PROFIL_RE.fullmatch(agent):
            raise ValueError(f"zła nazwa profilu {agent!r}")
        return self.home / "profiles" / agent / ".env"

    def __call__(self, agent: str) -> str | None:
        teraz = self.zegar()
        hit = self._pamiec.get(agent)
        if hit and teraz - hit[0] < self.ttl:
            return hit[1]
        klucz = _czytaj_env(self.sciezka(agent)).get("API_SERVER_KEY") or None
        self._pamiec[agent] = (teraz, klucz)
        return klucz

    def zapomnij(self, agent: str | None = None) -> None:
        if agent is None:
            self._pamiec.clear()
        else:
            self._pamiec.pop(agent, None)


def cialo(sesja_id: str, wejscie: Any, autor: dict | None = None) -> dict:
    """Ciało `POST /v1/runs` (bez model/provider/instructions: decyduje konfiguracja profilu)."""
    out: dict[str, Any] = {"input": wejscie, "session_id": sesja_id}
    if autor:
        out["author"] = dict(autor)
    return out


def cialo_json(c: dict) -> bytes:
    return json.dumps(c, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def cialo_sha(c: dict) -> str:
    """Odcisk ciała (kanoniczny JSON, klucze posortowane): ponowienie musi dać ten sam."""
    return hashlib.sha256(json.dumps(c, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _blad_z(r: httpx.Response) -> tuple[str, str]:
    """(komunikat, kod) z koperty błędu bramy `{"error": {"message", "type", "code"}}`."""
    try:
        e = r.json().get("error", {})
    except ValueError:
        return r.text[:200], ""
    if isinstance(e, dict):
        return str(e.get("message") or "")[:300], str(e.get("code") or e.get("type") or "")
    return str(e)[:300], ""


def _ponow_za(r: httpx.Response) -> float:
    try:
        return max(0.0, float(r.headers.get("Retry-After") or 1))
    except ValueError:
        return 1.0


def blad_odpowiedzi(r: httpx.Response) -> BladBramy:
    komunikat, typ = _blad_z(r)
    s = r.status_code
    if s == 429:
        return BladBramy("limit", komunikat, status=s, ponow_za=_ponow_za(r), typ=typ or "rate_limit_exceeded")
    if s in (401, 403):
        return BladBramy("klucz", komunikat, status=s, typ=typ)
    if s in (502, 503, 504):
        return BladBramy("niedostepna", komunikat, status=s, typ=typ)
    if s == 409:
        kod = "nieaktywny" if typ in ("run_not_active", "run_not_accepting_steer") else "konflikt"
        return BladBramy(kod, komunikat, status=s, typ=typ)
    if s == 404:
        return BladBramy("brak", komunikat, status=s, typ=typ)
    return BladBramy("odrzucone", komunikat, status=s, typ=typ)


class KlientBramy:
    """Klient bramy dla jednego procesu (wątek silnika). `http`: wspólny httpx.AsyncClient (testy podają własny)."""

    def __init__(self, api_base: str, czytaj_klucz: Callable[[str], str | None], http: httpx.AsyncClient | None = None):
        self.api_base = api_base.rstrip("/")
        self.czytaj_klucz = czytaj_klucz
        self.http = http or klient_http(timeout=CZAS)

    async def zamknij(self) -> None:
        await self.http.aclose()

    def cel(self, agent: str) -> tuple[str, dict]:
        """(bazowy URL profilu, nagłówki z kluczem). BladBramy('klucz'), gdy profil nie ma klucza."""
        if agent in ("", "default"):
            base = self.api_base
        elif PROFIL_RE.fullmatch(agent or ""):
            base = f"{self.api_base}/p/{agent}"
        else:
            raise BladBramy("odrzucone", f"zła nazwa profilu {agent!r}")
        klucz = self.czytaj_klucz(agent)
        if not klucz:
            raise BladBramy("klucz", f"profil {agent} nie ma API_SERVER_KEY w .env")
        return base, {"Authorization": f"Bearer {klucz}"}

    async def _zadanie(self, metoda: str, agent: str, sciezka: str, *, json_: Any = None, tresc: bytes | None = None,
                       naglowki: dict | None = None, ok: tuple[int, ...] = (200, 201, 202)) -> httpx.Response:
        base, h = self.cel(agent)
        h = {**h, **(naglowki or {})}
        if tresc is not None:
            h["Content-Type"] = "application/json"
        try:
            r = await self.http.request(metoda, base + sciezka, json=json_, content=tresc, headers=h, timeout=CZAS)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise BladBramy("niedostepna", type(exc).__name__, dotarlo=not isinstance(exc, NIE_DOTARLO)) from None
        if r.status_code not in ok:
            raise blad_odpowiedzi(r)
        return r

    @staticmethod
    def _json(r: httpx.Response) -> dict:
        try:
            d = r.json()
        except ValueError:
            raise BladBramy("odrzucone", "brama nie zwróciła JSON-a", status=r.status_code) from None
        return d if isinstance(d, dict) else {}

    # ------------------------------------------------------------------------------------------- sesje
    async def utworz_sesje(self, agent: str, sid: str, tytul: str) -> str:
        """Sesja o naszym id (deterministycznym): 201 albo 409 `session_exists` = ok; 400 `invalid_title` (tytuł
        zajęty) → jedna próba z nowym sufiksem ` · <6 hex>`."""
        _sesja(sid)
        for proba in range(2):
            t = tytul if proba == 0 else f"{tytul} · {secrets.token_hex(3)}"
            try:
                await self._zadanie("POST", agent, "/api/sessions", json_={"id": sid, "title": t})
                return sid
            except BladBramy as e:
                if e.status == 409:                      # session_exists: ta sama sesja (ponowienie po awarii)
                    return sid
                if e.status == 400 and e.typ == "invalid_title" and proba == 0:
                    continue
                raise
        return sid

    async def zmien_sesje(self, agent: str, sid: str, **pola) -> dict:
        """PATCH sesji (`title`, `pinned`); przy zajętym tytule jedna próba z nowym sufiksem."""
        for proba in range(2):
            p = dict(pola)
            if proba and "title" in p:
                p["title"] = f"{p['title']} · {secrets.token_hex(3)}"
            try:
                return self._json(await self._zadanie("PATCH", agent, f"/api/sessions/{_sesja(sid)}", json_=p))
            except BladBramy as e:
                if e.status == 400 and e.typ == "invalid_title" and proba == 0 and "title" in pola:
                    continue
                raise
        return {}

    # ------------------------------------------------------------------------------------------- przebiegi
    async def start(self, agent: str, *, cialo_: dict, idem: str) -> dict:
        """`POST /v1/runs` → {run_id, status, replayed}; ciało z `cialo()` (bajtowo stałe)."""
        tresc = cialo_json(cialo_)
        if len(tresc) > CIALO_MAX:
            raise BladBramy("odrzucone", "ciało za duże", status=413, typ="za_duze")
        r = await self._zadanie("POST", agent, "/v1/runs", tresc=tresc, naglowki={"Idempotency-Key": idem})
        return self._json(r)

    async def stan(self, agent: str, run_id: str) -> dict:
        return self._json(await self._zadanie("GET", agent, f"/v1/runs/{_przebieg(run_id)}"))

    async def stop(self, agent: str, run_id: str) -> dict:
        return self._json(await self._zadanie("POST", agent, f"/v1/runs/{_przebieg(run_id)}/stop", json_={}))

    async def zgoda(self, agent: str, run_id: str, wybor: str, request_id: str) -> dict:
        """Odpowiedź na prośbę o zgodę; `request_id` zawsze (bez niego Hermes rozstrzyga NAJSTARSZĄ czekającą)."""
        return self._json(await self._zadanie("POST", agent, f"/v1/runs/{_przebieg(run_id)}/approval",
                                              json_={"choice": wybor, "request_id": request_id}))

    async def dopisz(self, agent: str, run_id: str, tekst: str) -> dict:
        return self._json(await self._zadanie("POST", agent, f"/v1/runs/{_przebieg(run_id)}/steer", json_={"input": tekst}))

    async def zdarzenia(self, agent: str, run_id: str) -> AsyncIterator[dict]:
        """Zdarzenia przebiegu (`data: <json>`; komentarze `:` pomijane). Koniec strumienia = koniec iteracji;
        30 s ciszy albo zerwane połączenie = BladBramy('niedostepna')."""
        base, h = self.cel(agent)
        _przebieg(run_id)
        try:
            async with self.http.stream("GET", f"{base}/v1/runs/{run_id}/events",
                                        headers={**h, "Accept": "text/event-stream"}, timeout=CZAS_ZDARZEN) as r:
                if r.status_code != 200:
                    await r.aread()
                    raise blad_odpowiedzi(r)
                dane: list[str] = []
                async for linia in r.aiter_lines():
                    if linia == "":
                        if dane:
                            surowe = "\n".join(dane)
                            dane = []
                            try:
                                ev = json.loads(surowe)
                            except ValueError:
                                continue
                            if isinstance(ev, dict):
                                yield ev
                        continue
                    if linia.startswith(":"):
                        continue
                    pole, _, wartosc = linia.partition(":")
                    if pole == "data":
                        dane.append(wartosc[1:] if wartosc.startswith(" ") else wartosc)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise BladBramy("niedostepna", type(exc).__name__, dotarlo=not isinstance(exc, NIE_DOTARLO)) from None
