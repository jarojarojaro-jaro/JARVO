#!/usr/bin/env python3
"""CEIDG (Hurtownia danych CEIDG i Biznes.gov.pl, API v3, darmowy token): jednoosobowe działalności → sygnały Łowcy.

    ceidg.py szukaj --pkd 43.31.Z,43.34.Z --miasto Gliwice [--woj ŚLĄSKIE] [--powiat …] [--gmina …] [--status AKTYWNY]
                    [--od-daty 2026-09-01] [--do-daty …] [--limit 100] [--bez-szczegolow] [-o sygnaly.jsonl]
    ceidg.py firma --nip 6311234567 | --regon 123456789 | --id <GUID> [--json] [-o sygnaly.jsonl]
    ceidg.py sprawdz                                          # jedno zapytanie: czy token działa (kod 2 = brak albo zły)
    ceidg.py szukaj|firma … --z-pliku odpowiedz.json          # offline: zapisana odpowiedź API zamiast sieci, bez tokenu

KRS to spółki, CEIDG to osoby fizyczne prowadzące działalność gospodarczą (JDG). `szukaj` pyta `/firmy` (filtry API:
pełne kody PKD, miasto, województwo, powiat, gmina, status, data rozpoczęcia; kolejne strony za `links.next`), potem
`/firma?ids=…` partiami po szczegóły: PKD i kontakt, który przedsiębiorca sam podał w rejestrze (telefon, e-mail, www).
Sygnały: `ceidg-nowa-firma` (działalność rozpoczęta najwyżej 30 dni przed stanem albo dopiero zaplanowana) i
`ceidg-firma` (sam wpis: dane i kontakt dla leada, nie powód „dlaczego teraz”). Każdy wiersz ma `zrodlo` (wpis
w wyszukiwarce firm biznes.gov.pl) i `stan_na` (dzień pobrania z rejestru).

Dane osobowe: przedsiębiorca jednoosobowy to osoba fizyczna, więc z odpowiedzi przechodzi tylko biała lista pól: nazwa
firmy, NIP, REGON, status i daty działalności, miejscowość, gmina, powiat, województwo, PKD oraz telefon, e-mail i www
podane w CEIDG. Nie przechodzą: imię i nazwisko właściciela jako osobne pola, ulica i numer (często adres domowy), adres
korespondencyjny i adresy dodatkowe, obywatelstwo, wspólność majątkowa, data zgonu, zakazy, upadłości, kuratorzy,
zarządca sukcesyjny, kwalifikacje, adres do e-Doręczeń, „inna forma kontaktu”. PESEL-u API v3 nie zwraca; gdyby się
pojawił, biała lista go nie przepuści. Odpowiedzi nie są zapisywane na dysku. Skrypt niczego nie wysyła; e-mail
i telefon z CEIDG to dane osoby: informacja handlowa tymi kanałami wymaga jej wcześniejszej zgody (art. 398 PKE).

Token: zmienna CEIDG_TOKEN (Jarvo HQ → profil jarvo-lowca → Klucze → Własne klucze; instrukcja w docs/LEADY.md).
Idzie tylko w nagłówku `Authorization: Bearer` do hosta API (bez przekierowań), nigdy do wyjścia, błędów ani pamięci.
Brak tokenu albo token odrzucony (401, 403): kod 2. Limit API: 1000 zapytań na 60 minut; skrypt robi co najmniej 4 s
przerwy między zapytaniami (≤ 900 na godzinę, mieści też dawny limit 50 na 3 minuty), na 429 czeka (Retry-After,
co najmniej 180 s) i ponawia dwa razy, potem kod 3; 5xx i zerwane połączenie: trzy próby z odczekaniem 10 i 30 s.

Źródła (sprawdzone 2026-10-05):
- https://dane.biznes.gov.pl: Hurtownia danych, rejestracja, wniosek o dostęp, token,
- https://akademia.biznes.gov.pl/hurtownia-danych-instrukcje-i-dokumentacja/: instrukcje i dokumentacja API,
- https://pliki.biznes.gov.pl/akademia/20260422/Dokumentacja_dla_integratorow_API_HD_v3.7z: „HD CEIDG, API v3 HD,
  Dokumentacja dla integratorów” v1.4 (27.11.2025) i OpenAPI `API HD v3.json` (endpointy, parametry, pola, kody, limit),
- https://pliki.biznes.gov.pl/akademia/Hurtownia_danych/HD%20CEIDG%20-%20API%20v2%20Hurtowni%20Danych%20-%20Dokumentacja%20dla%20integrator%C3%B3w%20v3.0.pdf:
  API v2 (limit 50 żądań na 3 minuty z przerwą 180 s od ostatniego żądania, optymalnie 3,6 s między zapytaniami).
Środowisko testowe: https://test-dane.biznes.gov.pl/api/ceidg/v3 (`--srodowisko test`, osobny token).
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lowca_lib as ll  # noqa: E402

API = {"produkcja": "https://dane.biznes.gov.pl/api/ceidg/v3", "test": "https://test-dane.biznes.gov.pl/api/ceidg/v3"}
WPIS = "https://www.biznes.gov.pl/pl/wyszukiwarka-firm/wpis/ceidg/{}"
WYSZUKIWARKA = "https://www.biznes.gov.pl/pl/wyszukiwarka-firm/"
STATUSY = ("AKTYWNY", "WYKRESLONY", "ZAWIESZONY", "OCZEKUJE_NA_ROZPOCZECIE_DZIALANOSCI", "WYLACZNIE_W_FORMIE_SPOLKI")
ODSTEP_S = 4.0                 # 1000 zapytań na 60 min = 3,6 s; z zapasem
PAUZA_429_S = 180              # przerwa liczona od ostatniego żądania (dokumentacja v2)
MAX_PAUZA_429_S = 600          # dłuższe Retry-After = limit godzinowy wyczerpany: stop zamiast czekania
PROBY_429 = 2
PAUZY_5XX = (10, 30)           # odczekanie przed 2. i 3. próbą
STRONA = 50                    # firm na stronę `/firmy` (wartość z przykładu w dokumentacji)
PARTIA_IDS = 25                # identyfikatorów na jedno `/firma?ids=…`; za dużo = NIEPOPRAWNA_ILOSC_IDENTYFIKATOROW, dzielimy
NOWA_DNI = 30
MAX_MB = 20
TEST_NIP = "5250000251"        # `sprawdz`: dowolny poprawny NIP; 200 albo 204 znaczy, że token przeszedł
GUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-(?:[0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}$")
PKD_RE = re.compile(r"^\d{4}[A-Z]$")
GDZIE_TOKEN = ("Jarvo HQ: w lewym górnym rogu wybierz profil jarvo-lowca → Klucze → Własne klucze → Dodaj własny klucz, "
               "nazwa CEIDG_TOKEN (albo /srv/jarvo/secrets/jarvo-lowca.env i wdrożenie). Token jest darmowy: dane.biznes.gov.pl, "
               "kroki w docs/LEADY.md („Token CEIDG”).")
ZGODA = ("e-mail i telefon z CEIDG to dane przedsiębiorcy (osoby fizycznej): informacja handlowa tymi kanałami wymaga jego "
         "wcześniejszej zgody (art. 398 PKE); nic nie zostało wysłane")

_spij = time.sleep             # podmieniane w testach
_zegar = time.monotonic
_dzis = dt.date.today


class BladTokenu(Exception):
    """Brak tokenu albo API go odrzuciło (401, 403): kod 2, właściciel wpisuje albo odnawia token."""


class BladZapytania(Exception):
    """API odrzuciło zapytanie (400 i inne): kod HTTP, kod błędu API, komunikat."""

    def __init__(self, kod: int, kod_api: str | None, komunikat: str):
        super().__init__(f"CEIDG {kod}{' ' + kod_api if kod_api else ''}: {komunikat}")
        self.kod, self.kod_api = kod, kod_api


# ------------------------------------------------------------------ token i HTTP

def token() -> str:
    """CEIDG_TOKEN ze środowiska (bez „Bearer ”, cudzysłowów i spacji); brak = BladTokenu."""
    t = (os.environ.get("CEIDG_TOKEN") or "").strip().strip("\"'").strip()
    if t[:7].lower() == "bearer ":
        t = t[7:].strip()
    if not t:
        raise BladTokenu(f"brak CEIDG_TOKEN. Gdzie go wpisać: {GDZIE_TOKEN}")
    return t


def wygasa(t: str) -> dt.date | None:
    """Data z pola `exp` tokenu JWT (bez sprawdzania podpisu: tylko podpowiedź w komunikacie, sam token nie wychodzi)."""
    try:
        czesc = t.split(".")[1]
        dane = json.loads(base64.urlsafe_b64decode(czesc + "=" * (-len(czesc) % 4)))
        return dt.datetime.fromtimestamp(int(dane["exp"]), dt.timezone.utc).date()
    except (IndexError, ValueError, KeyError, TypeError, OverflowError, OSError):
        return None


def bez_tokenu(tekst: str, t: str | None) -> str:
    """Ostatnia zapora: token nigdy nie trafia do komunikatu, nawet gdyby API go odesłało."""
    return tekst.replace(t, "***") if t and len(t) >= 8 else tekst


class _BezPrzekierowan(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102 (nagłówek z tokenem nie idzie dalej)
        return None


_OTWIERACZ = urllib.request.build_opener(_BezPrzekierowan)


def _http(url: str, tok: str, timeout: int = 60) -> tuple[int, str, dict[str, str]]:
    """(kod, treść, nagłówki) jednego GET; token tylko w nagłówku. W testach podmieniane."""
    req = urllib.request.Request(url, headers={"User-Agent": ll.UA, "Accept": "application/json",
                                               "Authorization": f"Bearer {tok}"})
    try:
        with _OTWIERACZ.open(req, timeout=timeout) as r:  # noqa: S310 (adres budowany z API, host sprawdzony)
            surowe, kod, nagl = r.read(MAX_MB * 1_000_000 + 1), r.status, dict(r.headers.items())
    except urllib.error.HTTPError as e:
        return e.code, e.read(200_000).decode("utf-8", "replace"), {k.lower(): v for k, v in (e.headers or {}).items()}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ConnectionError(f"{urllib.parse.urlsplit(url).netloc}: {getattr(e, 'reason', None) or e}") from None
    if len(surowe) > MAX_MB * 1_000_000:
        raise ConnectionError(f"CEIDG: odpowiedź większa niż {MAX_MB} MB (zawęź zapytanie)")
    return kod, surowe.decode("utf-8", "replace"), {k.lower(): v for k, v in nagl.items()}


def _retry_after(nagl: dict[str, str]) -> float:
    try:
        return float(nagl.get("retry-after", "0"))
    except ValueError:
        return 0.0                                            # data HTTP zamiast sekund: zostaje pauza domyślna


def _blad_api(tresc: str) -> tuple[str | None, str]:
    try:
        d = json.loads(tresc)
        return d.get("code"), str(d.get("message") or d)[:300]
    except (ValueError, AttributeError):
        return None, re.sub(r"\s+", " ", tresc)[:300] or "pusta odpowiedź"


class Klient:
    """Zapytania do API v3: token w nagłówku, przerwa między zapytaniami, ponowienia (429, 5xx, sieć), jeden host."""

    def __init__(self, tok: str, srodowisko: str = "produkcja"):
        self._tok = tok
        self.baza = API[srodowisko]
        self._u = urllib.parse.urlsplit(self.baza)
        self._ostatnie: float | None = None

    def __repr__(self) -> str:
        return f"Klient({self.baza})"

    def url(self, sciezka: str, parametry: list[tuple[str, str]] | None = None) -> str:
        return f"{self.baza}{sciezka}" + (f"?{urllib.parse.urlencode(parametry)}" if parametry else "")

    def z_linku(self, link: str | None) -> str | None:
        """Adres z `links.*` odpowiedzi, przepisany na host i ścieżkę API: token nie wychodzi poza dane.biznes.gov.pl."""
        if not link:
            return None
        u = urllib.parse.urlsplit(re.sub(r"\s+", "", link))
        if not u.path.startswith(self._u.path + "/"):
            return None
        return urllib.parse.urlunsplit(("https", self._u.netloc, u.path, u.query, ""))

    def _odstep(self) -> None:
        if self._ostatnie is not None:
            zostalo = self._ostatnie + ODSTEP_S - _zegar()
            if zostalo > 0:
                _spij(zostalo)
        self._ostatnie = _zegar()

    def get(self, url: str) -> dict | None:
        """JSON odpowiedzi; None przy 204 i 404 (brak danych dla kryteriów)."""
        p429 = p5xx = p401 = 0
        while True:
            self._odstep()
            ll.LICZNIK["zapytania"] += 1
            try:
                kod, tresc, nagl = _http(url, self._tok)
            except ConnectionError as e:
                ll.LICZNIK["bledy"] += 1
                if p5xx < len(PAUZY_5XX):
                    _spij(PAUZY_5XX[p5xx])
                    p5xx += 1
                    continue
                raise ConnectionError(bez_tokenu(f"{e} (po {p5xx + 1} próbach)", self._tok)) from None
            if kod == 200:
                try:
                    return json.loads(tresc) if tresc.strip() else None
                except ValueError as e:
                    raise ConnectionError(f"CEIDG: niepoprawny JSON ({e})") from None
            if kod in (204, 404):
                return None
            ll.LICZNIK["bledy"] += 1
            if kod == 429:
                pauza = max(float(PAUZA_429_S), _retry_after(nagl))
                if p429 < PROBY_429 and pauza <= MAX_PAUZA_429_S:
                    print(f"! CEIDG: limit zapytań (429), czekam {pauza:.0f} s i ponawiam", file=sys.stderr)
                    _spij(pauza)
                    p429 += 1
                    continue
                raise ll.Blokada(f"CEIDG: limit zapytań (429) po {p429} ponowieniach (1000 na godzinę); zawęź filtry "
                                 "i spróbuj za godzinę, nie obchodzimy limitu")
            if kod == 401:
                if p401 < 1:                              # bramka API bywa chwilowo niekonsekwentna: jedna powtórka
                    p401 += 1
                    continue
                wyg = wygasa(self._tok)
                kiedy = f" (wygasł {wyg.isoformat()})" if wyg and wyg < _dzis() else ""
                raise BladTokenu(f"CEIDG odrzucił token (401): zły albo wygasły{kiedy}. Wygeneruj nowy na dane.biznes.gov.pl "
                                 f"i wpisz go ponownie. {GDZIE_TOKEN}")
            if kod == 403:
                raise BladTokenu("CEIDG: brak uprawnień do zasobu (403): token bez dostępu do API v3 albo wniosek o dostęp "
                                 f"jeszcze niezatwierdzony; sprawdź na dane.biznes.gov.pl. {GDZIE_TOKEN}")
            if kod >= 500:
                if p5xx < len(PAUZY_5XX):
                    _spij(PAUZY_5XX[p5xx])
                    p5xx += 1
                    continue
                raise ConnectionError(f"CEIDG {kod}: błąd serwera po {p5xx + 1} próbach; spróbuj później")
            kod_api, komunikat = _blad_api(tresc)
            raise BladZapytania(kod, kod_api, bez_tokenu(komunikat, self._tok))


# ------------------------------------------------------------------ pobieranie

def parametry(filtry: dict, na_strone: int) -> list[tuple[str, str]]:
    p = [("pkd", k) for k in filtry["pkd"]] + [("miasto", m) for m in filtry["miasto"]]
    p += [("wojewodztwo", w.lower()) for w in filtry["woj"]] + [("powiat", x) for x in filtry["powiat"]]
    p += [("gmina", x) for x in filtry["gmina"]] + [("status", s) for s in filtry["status"]]
    if filtry["od"]:
        p.append(("dataod", filtry["od"]))
    if filtry["do"]:
        p.append(("datado", filtry["do"]))
    return p + [("limit", str(na_strone))]


def lista(kl: Klient, filtry: dict, limit: int) -> tuple[list[dict], dict]:
    """Wpisy z `/firmy` (bez szczegółów) do `limit`, strona po stronie za `links.next`. Koniec: pusta strona, brak
    `next` albo `next` wskazuje stronę już pobraną (na ostatniej stronie API podaje `next` = `self`)."""
    url: str | None = kl.url("/firmy", parametry(filtry, min(STRONA, max(1, limit))))
    wpisy: dict[str, dict] = {}
    odwiedzone: set[str] = set()
    staty = {"w_rejestrze": 0, "strony": 0, "wiecej": False}
    while url and url not in odwiedzone:
        if len(wpisy) >= limit:
            staty["wiecej"] = True
            break
        odwiedzone.add(url)
        d = kl.get(url)
        staty["strony"] += 1
        if not d:
            break
        staty["w_rejestrze"] = max(staty["w_rejestrze"], int(d.get("count") or 0))
        partia = d.get("firmy") or []
        for f in partia:
            wpisy.setdefault(str(f.get("id") or len(wpisy)).lower(), f)
        linki = d.get("links") or {}
        odwiedzone.add(kl.z_linku(linki.get("self")) or "")
        url = kl.z_linku(linki.get("next")) if partia else None
    staty["wiecej"] = staty["wiecej"] or len(wpisy) > limit or staty["w_rejestrze"] > min(len(wpisy), limit)
    return list(wpisy.values())[:limit], staty


def szczegoly(kl: Klient, ids: list[str]) -> dict[str, dict]:
    """Pełne wpisy z `/firma?ids=…` partiami; API nie podaje maksimum, więc za dużą partię dzielimy na pół."""
    out: dict[str, dict] = {}
    i, partia = 0, PARTIA_IDS
    while i < len(ids):
        kawalek = ids[i:i + partia]
        try:
            d = kl.get(kl.url("/firma", [("ids", x) for x in kawalek]))
        except BladZapytania as e:
            if e.kod_api == "NIEPOPRAWNA_ILOSC_IDENTYFIKATOROW" and len(kawalek) > 1:
                partia = max(1, len(kawalek) // 2)
                continue
            raise
        for f in (d or {}).get("firma") or []:
            if f.get("id"):
                out[str(f["id"]).lower()] = f
        i += len(kawalek)
    return out


def szukaj(kl: Klient, filtry: dict, limit: int, pelne: bool = True) -> tuple[list[dict], dict]:
    """Surowe wpisy (lista, a gdy `pelne`, podmienione na szczegóły) i statystyki."""
    wpisy, staty = lista(kl, filtry, limit)
    if pelne and wpisy:
        dane = szczegoly(kl, [str(f["id"]) for f in wpisy if f.get("id")])
        wpisy = [dane.get(str(f.get("id")).lower(), f) for f in wpisy]
        staty["szczegoly"] = len(dane)
    return wpisy, staty


def firma(kl: Klient, nip: str | None = None, regon: str | None = None, id_: str | None = None) -> list[dict]:
    if id_:
        d = kl.get(kl.url(f"/firma/{id_}"))
    else:
        d = kl.get(kl.url("/firma", [("nip", nip)] if nip else [("regon", regon or "")]))
    return (d or {}).get("firma") or []


def z_pliku(plik: str) -> tuple[list[dict], str]:
    """Zapisana odpowiedź `/firmy` albo `/firma` (offline, bez tokenu); stan na dzień = data pliku."""
    p = Path(plik)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"--z-pliku {plik}: {e.strerror or e}") from None
    except ValueError as e:
        raise ValueError(f"--z-pliku {plik}: niepoprawny JSON ({e})") from None
    wpisy = d if isinstance(d, list) else (d.get("firma") or d.get("firmy") or [])
    return wpisy, dt.date.fromtimestamp(p.stat().st_mtime).isoformat()


# ------------------------------------------------------------------ minimum danych i sygnały

def _pkd(kod: str | None) -> str | None:
    """„4331Z” → „43.31.Z” (zapis jak w KRS i ICP)."""
    k = re.sub(r"[\s.]", "", str(kod or "")).upper()
    return f"{k[:2]}.{k[2:4]}.{k[4:]}" if PKD_RE.match(k) else (k or None)


def _data(d: object) -> str | None:
    return str(d)[:10] if d else None


def normalizuj(f: dict, stan_na: str) -> dict:
    """Biała lista pól wpisu CEIDG: tylko to, co potrzebne do leada (reszta odpowiedzi nie wychodzi ze skryptu)."""
    adr, wl, gl = f.get("adresDzialalnosci") or {}, f.get("wlasciciel") or {}, f.get("pkdGlowny") or {}
    kody = [k for k in dict.fromkeys(_pkd(p.get("kod")) for p in f.get("pkd") or [] if p.get("kod")) if k]
    glowny = _pkd(gl.get("kod")) or (kody[0] if kody else None)
    m = ll.EMAIL_RE.search(str(f.get("email") or ""))         # adres z rejestru: tylko składnia, bez filtrów stron www
    emaile = [f"{m.group(1)}@{m.group(2)}".lower()] if m else []
    telefony = ll.telefony(str(f.get("telefon") or ""))
    www = str(f.get("www") or "").strip().lower()
    id_ = str(f.get("id") or "") or None
    return {
        "id": id_, "nazwa": " ".join(str(f.get("nazwa") or "").split()) or None,
        "nip": ll.nip(wl.get("nip") or ""), "regon": re.sub(r"\D", "", str(wl.get("regon") or "")) or None,
        "status": f.get("status"), "data_rozpoczecia": _data(f.get("dataRozpoczecia")),
        "data_zawieszenia": _data(f.get("dataZawieszenia")), "data_wznowienia": _data(f.get("dataWznowienia")),
        "miejscowosc": adr.get("miasto"), "gmina": adr.get("gmina"), "powiat": adr.get("powiat"),
        "woj": str(adr.get("wojewodztwo") or "").upper() or None,
        "pkd": glowny, "pkd_opis": gl.get("nazwa"), "pkd_inne": [k for k in kody if k != glowny], "rok_pkd": f.get("rokPkd"),
        "email": emaile[0] if emaile else None, "email_typ": ll.typ_emaila(emaile[0]) if emaile else None,
        "telefon": telefony[0] if telefony else None, "www": www if "." in www and " " not in www else None,
        "pelne": any(k in f for k in ("pkd", "pkdGlowny", "telefon", "email", "www", "rokPkd")),
        "zrodlo": WPIS.format(id_) if id_ and GUID_RE.match(id_) else WYSZUKIWARKA, "stan_na": stan_na,
    }


def pasuje(f: dict, filtry: dict) -> bool:
    """Filtry sprawdzone też lokalnie (offline i na wypadek luźniejszego dopasowania w API); brak pola = nie wiadomo."""
    if filtry["status"] and f.get("status") and f["status"] not in filtry["status"]:
        return False
    if filtry["pkd"] and f.get("pelne"):
        kody = {str(k).replace(".", "") for k in [f.get("pkd")] + list(f.get("pkd_inne") or []) if k}
        if not kody & set(filtry["pkd"]):
            return False
    for pole, klucz in (("miasto", "miejscowosc"), ("powiat", "powiat"), ("gmina", "gmina")):
        if filtry[pole] and f.get(klucz) and f[klucz].casefold() not in {x.casefold() for x in filtry[pole]}:
            return False
    if filtry["woj"] and f.get("woj") and f["woj"] not in filtry["woj"]:
        return False
    d = f.get("data_rozpoczecia")
    return not (d and ((filtry["od"] and d < filtry["od"]) or (filtry["do"] and d > filtry["do"])))


def nowa(f: dict) -> bool:
    """Rozpoczęcie najwyżej NOWA_DNI przed stanem na dzień albo w przyszłości (działalność zaplanowana)."""
    try:
        return (dt.date.fromisoformat(f["stan_na"]) - dt.date.fromisoformat(f["data_rozpoczecia"])).days <= NOWA_DNI
    except (KeyError, TypeError, ValueError):
        return False


def sygnal(f: dict) -> dict:
    """Wiersz `sygnaly.jsonl` w formacie Łowcy (jak `krs.py`): `leady.py dodaj` przyjmuje go bez zmian."""
    jest_nowa = nowa(f)
    branza = (f": {str(f['pkd_opis']).lower()}" if f.get("pkd_opis") else "") + (f" (PKD {f['pkd']})" if f.get("pkd") else "")
    if jest_nowa:
        kiedy = "rozpocznie" if f["data_rozpoczecia"] > f["stan_na"] else "rozpoczęła"
        opis = f"{kiedy} działalność {f['data_rozpoczecia']} (CEIDG, jednoosobowa){branza}"
    else:
        opis = f"w CEIDG od {f.get('data_rozpoczecia') or '?'} ({str(f.get('status') or '?').lower()}){branza}"
    kontakty = []
    if f.get("email"):
        kontakty.append({"typ": "email", "wartosc": f["email"], "rodzaj": f["email_typ"], "zrodlo": f["zrodlo"]})
    if f.get("telefon"):
        kontakty.append({"typ": "telefon", "wartosc": f["telefon"], "zrodlo": f["zrodlo"]})
    forma = ("SPÓŁKA CYWILNA (WSPÓLNIK)" if f.get("status") == "WYLACZNIE_W_FORMIE_SPOLKI"
             else "JEDNOOSOBOWA DZIAŁALNOŚĆ GOSPODARCZA")
    return {"typ": "ceidg-nowa-firma" if jest_nowa else "ceidg-firma", "data": f.get("data_rozpoczecia") or f["stan_na"],
            "zrodlo": f["zrodlo"], "stan_na": f["stan_na"], "opis": opis,
            "firma": {k: f.get(k) for k in ("nazwa", "nip", "regon", "woj", "miejscowosc", "pkd", "pkd_inne", "www")},
            "kontakty": kontakty,
            "szczegoly": {"rejestr": "CEIDG", "id": f.get("id"), "forma": forma, "status": f.get("status"),
                          "data_rozpoczecia": f.get("data_rozpoczecia"), "pkd_opis": f.get("pkd_opis"), "rok_pkd": f.get("rok_pkd"),
                          "powiat": f.get("powiat"), "gmina": f.get("gmina")}}


def linia(f: dict) -> str:
    kontakt = " · ".join(x for x in (f"e-mail {f['email']} ({f['email_typ']})" if f.get("email") else "",
                                     f"tel. {f['telefon']}" if f.get("telefon") else "",
                                     f"www {f['www']}" if f.get("www") else "") if x) or "brak opublikowanego kontaktu"
    return (f"{f['nazwa']} · NIP {f['nip'] or '–'} · {f['status'] or '?'} od {f['data_rozpoczecia'] or '?'} · "
            f"{f['miejscowosc'] or '?'}, {f['woj'] or '?'} · PKD {f['pkd'] or '–'} {f['pkd_opis'] or ''} · {kontakt} · "
            f"stan na {f['stan_na']} · {f['zrodlo']}")


# ------------------------------------------------------------------ wejście

def _lista(arg: str | None) -> list[str]:
    return [x.strip() for x in (arg or "").split(",") if x.strip()]


def filtry_z(a: argparse.Namespace) -> dict:
    """Filtry z argumentów; zły argument = ValueError z komunikatem dla agenta."""
    pkd = []
    for k in _lista(a.pkd):
        n = re.sub(r"[\s.]", "", k).upper()
        if not PKD_RE.match(n):
            raise ValueError(f"--pkd {k}: podaj pełne kody podklas (np. 43.31.Z), jak filtr PKD w dokumentacji API (pkd=4331Z); "
                             "dział albo grupę rozpisz na podklasy (remonty i wykończenia: 43.31.Z,43.32.Z,43.33.Z,43.34.Z,43.39.Z)")
        pkd.append(n)
    status = [s.upper() for s in _lista(a.status)]
    if bad := [s for s in status if s not in STATUSY]:
        raise ValueError(f"--status {','.join(bad)}: dozwolone {', '.join(STATUSY)}")
    woj = [ll.WOJ.get(w.upper(), w.upper()) for w in _lista(a.woj)]
    if bad := [w for w in woj if w not in ll.WOJ_KOD]:
        raise ValueError(f"--woj {','.join(bad)}: podaj nazwę (ŚLĄSKIE) albo kod (PL24)")
    for nazwa, d in (("--od-daty", a.od_daty), ("--do-daty", a.do_daty)):
        try:
            if d:
                dt.date.fromisoformat(d)
        except ValueError:
            raise ValueError(f"{nazwa} {d}: data w formacie RRRR-MM-DD") from None
    f = {"pkd": pkd, "miasto": _lista(a.miasto), "woj": woj, "powiat": _lista(a.powiat), "gmina": _lista(a.gmina),
         "status": status, "od": a.od_daty, "do": a.do_daty}
    if not (pkd or f["miasto"] or woj or f["powiat"] or f["gmina"] or a.od_daty or a.do_daty) and not a.z_pliku:
        raise ValueError("podaj co najmniej jeden filtr (--pkd, --miasto, --woj, --powiat, --gmina, --od-daty): "
                         "sam status to cały rejestr")
    return f


def _zapisz(wiersze: list[dict], plik: str | None) -> None:
    ll.zapisz_jsonl([sygnal(f) for f in wiersze], plik)


def cmd_szukaj(a: argparse.Namespace) -> int:
    if a.limit < 1:
        raise ValueError("--limit musi być dodatni")
    filtry = filtry_z(a)
    if a.z_pliku:
        surowe, stan = z_pliku(a.z_pliku)
        staty = {"w_rejestrze": len(surowe), "wiecej": len(surowe) > a.limit}
        surowe = surowe[:a.limit]
    else:
        kl, stan = Klient(token(), a.srodowisko), _dzis().isoformat()
        surowe, staty = szukaj(kl, filtry, a.limit, pelne=not a.bez_szczegolow)
    firmy = [normalizuj(f, stan) for f in surowe]
    wynik = [f for f in firmy if pasuje(f, filtry)]
    _zapisz(wynik, a.o)
    nowe = sum(1 for f in wynik if nowa(f))
    print(f"✓ CEIDG szukaj (stan na {stan}): w rejestrze {staty['w_rejestrze']}, pobrane {len(firmy)}, po filtrach "
          f"{len(wynik)} → sygnałów {len(wynik)} (nowe firmy {nowe}), z e-mailem {sum(1 for f in wynik if f['email'])}, "
          f"z telefonem {sum(1 for f in wynik if f['telefon'])} ({ll.podsumowanie()})", file=sys.stderr)
    if staty["wiecej"]:
        print(f"! w rejestrze więcej niż --limit {a.limit}: zawęź filtry (PKD, gmina, --od-daty) albo zwiększ --limit "
              f"(50 firm ≈ 3 zapytania po {ODSTEP_S:.0f} s)", file=sys.stderr)
    if a.bez_szczegolow and not a.z_pliku:
        print("! --bez-szczegolow: bez PKD z wpisu i bez kontaktu (tylko lista z /firmy)", file=sys.stderr)
    if any(f["email"] or f["telefon"] for f in wynik):
        print(f"! {ZGODA}", file=sys.stderr)
    return 0


def cmd_firma(a: argparse.Namespace) -> int:
    if a.z_pliku:
        surowe, stan = z_pliku(a.z_pliku)
    else:
        if not (a.nip or a.regon or a.id):
            raise ValueError("podaj --nip, --regon albo --id (albo --z-pliku)")
        nip = ll.nip(a.nip) if a.nip else None
        if a.nip and not nip:
            raise ValueError(f"--nip {a.nip}: niepoprawny NIP (suma kontrolna)")
        regon = re.sub(r"\D", "", a.regon or "")
        if a.regon and len(regon) not in (9, 14):
            raise ValueError(f"--regon {a.regon}: REGON ma 9 albo 14 cyfr")
        if a.id and not GUID_RE.match(a.id):
            raise ValueError(f"--id {a.id}: identyfikator wpisu CEIDG to GUID (np. 9D2531B1-6DED-4538-95EA-22FF2C7D2E20)")
        kl, stan = Klient(token(), a.srodowisko), _dzis().isoformat()
        surowe = firma(kl, nip=nip, regon=regon or None, id_=a.id)
    firmy = [normalizuj(f, stan) for f in surowe]
    if not firmy:
        print("✗ brak wpisu w CEIDG (jeśli to spółka, sprawdź KRS: krs.py)", file=sys.stderr)
        return 1
    for f in firmy:
        print(json.dumps({k: v for k, v in f.items() if k != "pelne"}, ensure_ascii=False) if a.json else linia(f))
    if a.o:
        _zapisz(firmy, a.o)
        print(f"✓ {len(firmy)} wpisów → {a.o}", file=sys.stderr)
    if any(f["email"] or f["telefon"] for f in firmy):
        print(f"! {ZGODA}", file=sys.stderr)
    return 0


def cmd_sprawdz(a: argparse.Namespace) -> int:
    tok = token()
    kl = Klient(tok, a.srodowisko)
    kl.get(kl.url("/firmy", [("nip", TEST_NIP)]))           # 200 albo 204: token przeszedł; 401/403 → BladTokenu
    wyg = wygasa(tok)
    print(f"✓ CEIDG odpowiada, token działa{f' (ważny do {wyg.isoformat()})' if wyg else ''} ({kl.baza})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    wspolne = argparse.ArgumentParser(add_help=False)
    wspolne.add_argument("--srodowisko", choices=tuple(API), default="produkcja", help="test = test-dane.biznes.gov.pl (osobny token)")
    wspolne.add_argument("--z-pliku", metavar="ODPOWIEDZ.json", help="offline: zapisana odpowiedź API zamiast sieci (bez tokenu)")
    wspolne.add_argument("-o", help="dopisz sygnały do pliku JSONL (szukaj: domyślnie wypisz)")
    s = sub.add_parser("szukaj", parents=[wspolne], help="firmy po PKD, miejscu, statusie i dacie rozpoczęcia → sygnały")
    s.add_argument("--pkd", help="pełne kody podklas PKD po przecinku, np. 43.31.Z,4334Z (nie prefiks działu)")
    s.add_argument("--miasto", help="miejscowości po przecinku, jak w rejestrze (np. Gliwice)")
    s.add_argument("--woj", help="województwa (nazwa albo kod PL24) po przecinku")
    s.add_argument("--powiat", help="powiaty po przecinku")
    s.add_argument("--gmina", help="gminy po przecinku")
    s.add_argument("--status", default="AKTYWNY", help=f"statusy po przecinku: {', '.join(STATUSY)} (domyślnie AKTYWNY)")
    s.add_argument("--od-daty", help="data rozpoczęcia działalności od (RRRR-MM-DD)")
    s.add_argument("--do-daty", help="data rozpoczęcia działalności do (RRRR-MM-DD)")
    s.add_argument("--limit", type=int, default=100, help="najwięcej firm (50 na stronę + szczegóły po 25: ok. 3 zapytania na 50)")
    s.add_argument("--bez-szczegolow", action="store_true", help="tylko lista z /firmy: bez PKD z wpisu i bez kontaktu (taniej)")
    s = sub.add_parser("firma", parents=[wspolne], help="wpis po NIP, REGON albo identyfikatorze")
    s.add_argument("--nip")
    s.add_argument("--regon")
    s.add_argument("--id", help="identyfikator wpisu CEIDG (GUID z `szczegoly.id`)")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("sprawdz", help="jedno zapytanie: czy token działa")
    s.add_argument("--srodowisko", choices=tuple(API), default="produkcja")
    a = ap.parse_args(argv)
    try:
        return {"szukaj": cmd_szukaj, "firma": cmd_firma, "sprawdz": cmd_sprawdz}[a.cmd](a)
    except BladTokenu as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except ll.Blokada as e:
        print(f"✗ blokada: {e}", file=sys.stderr)
        return 3
    except (BladZapytania, ConnectionError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
