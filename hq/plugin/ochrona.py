"""Ochrona zapisu (CSRF) we wtyczkach dashboardu Jarvo: jarvo-hq i jarvo-wiedza (jeden plik, ta sama kopia w obu).

Strony agentów (podgląd na :9120, serwery deweloperskie na innych portach localhost) są dla przeglądarki tą samą
witryną co dashboard na :9119, więc ciasteczko logowania (SameSite=Lax) jedzie z ich żądaniami. Bez tej ochrony
zwykły formularz `text/plain` z takiej strony mógłby np. napisać orzeczenie do skarbca, które czyta każdy agent.

Reguły dla każdej trasy zapisu (POST, PUT, PATCH, DELETE; GET nie zmienia stanu):
  1. `Sec-Fetch-Site`, gdy jest, musi być `same-origin`;
  2. bez niego `Origin`, gdy jest, musi wskazywać ten sam serwer co nagłówek `Host`;
  3. bez obu (curl, skrypty) wymagany jest nagłówek `X-Jarvo-Request: 1`;
  4. treść: `Content-Type: application/json` albo nagłówek `X-Jarvo-Request: 1` (surowe wysyłki plików).
     Własny nagłówek wymusza zapytanie wstępne CORS, a CORS dashboardu nie wpuszcza ciasteczek z innych pochodzeń.
Odmowa: 403 `{"blad": {"kod": "csrf", …}}`, w dzienniku `jarvo.hq` metoda, ścieżka i powód (nigdy treść żądania);
licznik odmów (`ODMOWY`) pokazuje `/health`.

Trasy dostają ochronę same: router wtyczki tworzymy z `route_class=Trasa`, a ta dokłada `wymagaj_zapisu`
każdej trasie z metodą zapisu (tests/test_csrf.py sprawdza oba routery i to, że kopie pliku są identyczne).

`utajnij(tekst)` ukrywa klucze i tokeny w tekście, który aplikacja przekazuje agentom albo zapisuje (blok kontekstu
rozmowy, raport nadzoru, błędy): `agent.redact.redact_sensitive_text(force=True)` Hermesa, gdy da się go
zaimportować, a zawsze także wzorce zapasowe (kopia `SEKRETY` z infra/komputer/zasady.py, bo moduł Komputera nie
leży na ścieżce wtyczki) i numery kart z sumą Luhna.

Dane od klienta, zanim powstanie z nich ścieżka albo plik (docs/HQ.md „Rozmowy”): `profil(nazwa, znane)` (nazwa
profilu `^[a-z0-9-]+$` z listy agentów, inaczej ValueError), `sprawdz_obraz(dane)` (typ obrazu po magicznych
bajtach: PNG, JPEG, WebP, GIF; nigdy SVG) i wzorce identyfikatorów wątków, przebiegów, kart przeglądarki i sesji.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Iterable, Mapping
from urllib.parse import urlsplit

METODY_ZAPISU = frozenset({"POST", "PUT", "PATCH", "DELETE"})
NAGLOWEK = "X-Jarvo-Request"
ODPOWIEDZ = {"blad": {"kod": "csrf",
                      "komunikat": "Odmowa zapisu: żądanie nie przyszło z panelu Jarvo.",
                      "komunikat_en": "Write refused: the request did not come from the Jarvo dashboard."}}


def powod_odmowy(metoda: str, naglowki: Mapping[str, str], schemat: str = "http") -> str | None:
    """None = zapis dozwolony; inaczej krótki powód do dziennika. Bez FastAPI, żeby dało się to testować wprost."""
    if (metoda or "").upper() not in METODY_ZAPISU:
        return None
    h = {str(k).lower(): str(v) for k, v in naglowki.items()}
    wlasny = h.get(NAGLOWEK.lower(), "").strip() == "1"
    skad = h.get("sec-fetch-site")
    origin = h.get("origin")
    if skad is not None:
        if skad.strip().lower() != "same-origin":
            return f"sec-fetch-site={skad}"
    elif origin is not None:
        # ten sam serwer = ten sam host:port co w nagłówku Host (schemat bywa inny za proxy z TLS)
        o = urlsplit(origin.strip())
        if o.scheme not in ("http", "https") or not o.netloc or o.netloc.lower() != h.get("host", "").strip().lower():
            return f"origin={origin[:80]}"
    elif not wlasny:
        return "brak Origin i Sec-Fetch-Site"
    if not wlasny:
        typ = h.get("content-type", "").split(";")[0].strip().lower()
        if typ != "application/json":
            return f"content-type={typ or 'brak'}"
    return None


class Odmowa(Exception):
    """Zapis odrzucony; Trasa zamienia to na 403 {"blad": …}."""


ODMOWY = {"razem": 0}


def wymagaj_zapisu(request: Request) -> None:
    """Zależność FastAPI każdej trasy zapisu obu wtyczek (dokłada ją Trasa)."""
    powod = powod_odmowy(request.method, request.headers, request.url.scheme)
    if powod:
        ODMOWY["razem"] += 1
        linia = (f"jarvo: odrzucony zapis (csrf) {request.method} {request.url.path}: {powod} "
                 f"(sec-fetch-site={request.headers.get('sec-fetch-site', '-')})")
        log = logging.getLogger("jarvo.hq")
        if log.handlers:
            log.info(linia)
        else:
            print(linia, file=sys.stderr)
        raise Odmowa(powod)


try:  # wtyczki działają w procesie dashboardu (FastAPI jest zawsze); bez FastAPI zostaje sama logika do testów
    from fastapi import Depends, Request
    from fastapi.responses import JSONResponse
    from fastapi.routing import APIRoute
except ImportError:  # pragma: no cover
    APIRoute = None

if APIRoute is not None:
    ZAPIS = Depends(wymagaj_zapisu)

    class Trasa(APIRoute):
        """Trasa wtyczki Jarvo: metoda zapisu dostaje `wymagaj_zapisu`, a odmowa wraca jako 403 {"blad": …}
        (HTTPException FastAPI owija treść w {"detail": …}, a format błędów aplikacji to {"blad": …})."""

        def __init__(self, path, endpoint, **kw):
            if {m.upper() for m in (kw.get("methods") or ())} & METODY_ZAPISU:
                zal = list(kw.get("dependencies") or [])
                if not any(getattr(d, "dependency", None) is wymagaj_zapisu for d in zal):   # include_router tworzy trasę ponownie
                    zal.insert(0, ZAPIS)
                kw["dependencies"] = zal
            super().__init__(path, endpoint, **kw)

        def get_route_handler(self):
            obsluz = super().get_route_handler()

            async def handler(request):
                try:
                    return await obsluz(request)
                except Odmowa:
                    return JSONResponse(ODPOWIEDZ, status_code=403)

            return handler


def ma_ochrone(route) -> bool:
    """Czy trasa FastAPI ma zależność wymagaj_zapisu (dla testów i diagnozy)."""
    return any(getattr(d, "call", None) is wymagaj_zapisu
               for d in getattr(getattr(route, "dependant", None), "dependencies", []))


# ------------------------------------------------------------------------------------------- utajnij

SEKRETY = re.compile("|".join([          # kopia infra/komputer/zasady.py: SEKRETY (tests/test_kontekst.py pilnuje)
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)",
    r"\bsk-(?:ant-|proj-|or-v1-)?[A-Za-z0-9_-]{20,}",
    r"\bgh[pousr]_[A-Za-z0-9]{30,}", r"\bgithub_pat_[A-Za-z0-9_]{30,}", r"\bglpat-[A-Za-z0-9_-]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b", r"\bASIA[0-9A-Z]{16}\b", r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    r"\bAIza[0-9A-Za-z_-]{35}\b", r"\bhf_[A-Za-z0-9]{30,}", r"\bnpm_[A-Za-z0-9]{36}\b",
    r"\b(?:rk|sk|pk)_live_[A-Za-z0-9]{20,}", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    r"\b\d{6,12}:AA[A-Za-z0-9_-]{30,}",
]))
KARTA = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
UKRYTE = "[ukryte]"


def _luhn(cyfry: str) -> bool:
    suma = 0
    for i, c in enumerate(reversed(cyfry)):
        d = int(c) * (2 if i % 2 else 1)
        suma += d - 9 if d > 9 else d
    return suma % 10 == 0


def _redakcja_hermesa():
    try:
        from agent.redact import redact_sensitive_text  # noqa: PLC0415  (proces dashboardu Hermesa)
    except Exception:
        return None
    return redact_sensitive_text


_HERMES_REDAKCJA = _redakcja_hermesa()


def utajnij(tekst: str) -> str:
    """Tekst bez kluczy, tokenów, kluczy prywatnych i numerów kart (redakcja Hermesa, gdy jest, i wzorce zapasowe)."""
    tekst = str(tekst or "")
    if _HERMES_REDAKCJA is not None:
        try:
            tekst = _HERMES_REDAKCJA(tekst, force=True)
        except Exception:  # redakcja Hermesa zawiodła: zostają wzorce zapasowe
            pass
    tekst = SEKRETY.sub(UKRYTE, tekst)
    for m in list(KARTA.finditer(tekst)):
        cyfry = re.sub(r"\D", "", m.group())
        if 13 <= len(cyfry) <= 19 and len(set(cyfry)) > 1 and _luhn(cyfry):
            tekst = tekst.replace(m.group(), UKRYTE)
    return tekst


# ------------------------------------------------------------------------------------------- dane od klienta

PROFIL_RE = re.compile(r"^[a-z0-9-]+$")
WATEK_RE = re.compile(r"^w_[0-9a-f]{21}$")
PRZEBIEG_RE = re.compile(r"^p_[0-9a-f]{21}$")
WPIS_RE = re.compile(r"^e_[0-9a-f]{21}$")
KLIENT_RE = re.compile(r"^k_[0-9A-Za-z_-]{6,64}$")
SESJA_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
ZAKAZANE_PROFILE = frozenset({"szablon-wlasny"})

OBRAZY = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


def profil(nazwa: str, znane: Iterable[str]) -> str:
    """Nazwa profilu sprawdzona, zanim powstanie z niej ścieżka: `^[a-z0-9-]+$`, na liście agentów, nie szablon."""
    nazwa = str(nazwa or "")
    if not PROFIL_RE.fullmatch(nazwa) or nazwa in ZAKAZANE_PROFILE or nazwa not in set(znane):
        raise ValueError(f"nieznany profil {nazwa[:40]!r}")
    return nazwa


def sprawdz_obraz(dane: bytes) -> str | None:
    """Typ obrazu po magicznych bajtach (PNG, JPEG, WebP, GIF); None dla wszystkiego innego (SVG, HTML, PDF…)."""
    dane = bytes(dane[:16])
    if dane.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if dane.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if dane[:4] == b"RIFF" and dane[8:12] == b"WEBP":
        return "image/webp"
    if dane[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None
