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
Odmowa: 403 `{"blad": {"kod": "csrf", …}}`, w dzienniku metoda, ścieżka i powód (nigdy treść żądania).

Trasy dostają ochronę same: router wtyczki tworzymy z `route_class=Trasa`, a ta dokłada `wymagaj_zapisu`
każdej trasie z metodą zapisu (tests/test_csrf.py sprawdza oba routery i to, że kopie pliku są identyczne).
"""

from __future__ import annotations

import sys
from typing import Mapping
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


def wymagaj_zapisu(request: Request) -> None:
    """Zależność FastAPI każdej trasy zapisu obu wtyczek (dokłada ją Trasa)."""
    powod = powod_odmowy(request.method, request.headers, request.url.scheme)
    if powod:
        print(f"jarvo: odrzucony zapis (csrf) {request.method} {request.url.path}: {powod}", file=sys.stderr)
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
