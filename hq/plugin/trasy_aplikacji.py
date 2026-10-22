"""Trasy startu aplikacji Jarvo (docs/HQ.md „Ekran startu”), na routerze wtyczki pod /api/plugins/jarvo-hq/:

- `GET /app`: start aplikacji jednym zapytaniem: wersja paczki, stan silnika, agenci (jak `GET /agenci`), właściciel
  z USER.md, gotowość (model, brama, profil właściciela; same nazwy i wartości logiczne, aplikacja.py), limity
  wysyłki, funkcje instalacji, liczba pytań zespołu (decyzje Starej Bazy) i stan aktualizacji (jak `GET /update`).
- `GET /podpowiedzi?miejsce=start`: „Czeka na Ciebie” (zgody, pytania zespołu jednym wierszem, nieudana praca) i startery „Na początek”
  (nawyki.db, podpowiedzi.py) w budżecie 4 rzeczy.
- `POST /podpowiedzi/{id}/reakcja` `{rodzaj, klucz}`: pokazana / kliknieta / odrzucona / nigdy; 204, idempotentne po
  `klucz`; nieznana podpowiedź = 409 `nieznana`. Ochrona zapisu (CSRF) z routera wtyczki (`ochrona.Trasa`).
- `POST /app/poznanie` `{imie, firma, zajecie, linki: [{rodzaj, wartosc}], cele}`: pierwsze spotkanie bez modelu
  → USER.md (aplikacja.zapisz_poznanie); odpowiedź `{wlasciciel, gotowosc}`. Treści nie logujemy.
- `POST /app/glos` `{tekst, glos, tempo, jezyk}` → `audio/wav` z lokalnego lektora (glos.py); 503 `brak_glosu`, gdy
  w instalacji nie ma `jarvo-tts`, 502 `glos_blad`, gdy lektor nie zrobił pliku.
- `POST /app/glos/przygotuj` `{teksty, glos, tempo, jezyk}` → 202 `{w_kolejce}`: stałe kwestie rozmowy w tle.
GET tylko z karty panelu (`Sec-Fetch-Site` same-origin/none), błędy w kształcie `{"blad": {kod, komunikat, …}}`.
Testy: tests/test_aplikacja.py.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Callable, Literal

from fastapi import Request
from fastapi.responses import FileResponse, Response
from pydantic import Field

PODPOWIEDZ_WZOR = re.compile(r"^pd_[0-9a-f]{21}$")
UPLOAD_MAX = 52_428_800


def dolacz(router, *, m, trasy, silnik: Callable[[], Any], agenci, gotowosc, nawyki, stan_aktualizacji: Callable[[], dict],
           hello: Callable[[], dict], decyzje: Callable[[], list] | None = None, glos=None,
           log: Callable[[str], None] | None = None) -> list[str]:
    """Rejestruje trasy startu. `trasy`: moduł trasy_rozmow (BladTrasy, blad, czytaj_cialo, _Model, ODCZYT_ZRODLA).
    `decyzje`: pytania zespołu ze Starej Bazy (hq_core.build_state → decisions). Języka nie podajemy: wybiera go
    przełącznik dashboardu w przeglądarce (localStorage), serwer go nie zna. `glos`: lektor aplikacji (glos.Glos);
    None = trasy głosu odpowiadają 503 `brak_glosu`."""
    log = log or (lambda _m: None)
    decyzje = decyzje or (lambda: [])
    sciezki: list[str] = []

    class ReakcjaBody(trasy._Model):
        rodzaj: Literal["pokazana", "kliknieta", "odrzucona", "nigdy"]
        klucz: str | None = Field(None, pattern=r"^[A-Za-z0-9_:.-]{1,96}$")

    class LinkBody(trasy._Model):
        rodzaj: Literal["strona", "instagram", "facebook", "tiktok", "youtube", "linkedin", "mapy", "inne"]
        wartosc: str = Field(..., min_length=1, max_length=200)

    class PoznanieBody(trasy._Model):
        imie: str = Field(..., min_length=1, max_length=40)
        firma: str = Field("", max_length=80)
        zajecie: str = Field("", max_length=120)
        linki: list[LinkBody] = Field(default_factory=list, max_length=6)
        cele: list[str] = Field(default_factory=list, max_length=6)

    class GlosBody(trasy._Model):
        tekst: str = Field(..., min_length=1, max_length=400)
        glos: Literal["meski", "damski"] = "meski"
        tempo: Literal["spokojnie", "normalnie", "zwawo"] = "normalnie"
        jezyk: Literal["pl", "en"] = "pl"

    class PrzygotujBody(trasy._Model):
        teksty: list[str] = Field(..., min_length=1, max_length=12)
        glos: Literal["meski", "damski"] = "meski"
        tempo: Literal["spokojnie", "normalnie", "zwawo"] = "normalnie"
        jezyk: Literal["pl", "en"] = "pl"

    def trasa(metoda: str, sciezka: str, **kw):
        sciezki.append(f"{metoda} {sciezka}")
        return router.api_route(sciezka, methods=[metoda], **kw)

    def tylko_ta_strona(request: Request) -> None:
        skad = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if skad and skad not in trasy.ODCZYT_ZRODLA:
            m.ochrona.ODMOWY["razem"] += 1
            log(f"jarvo-hq: odczyt odrzucony GET {request.url.path} (sec-fetch-site={skad[:20]})")
            raise trasy.BladTrasy(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                                  "Read refused: the request did not come from the Jarvo dashboard.")

    def obsluga(fn):
        import functools

        @functools.wraps(fn)
        async def owiniete(*a, **kw):
            try:
                return await fn(*a, **kw)
            except trasy.BladTrasy as e:
                return trasy.blad(e.status, e.kod, e.komunikat, e.komunikat_en, **e.dane)
        return owiniete

    def _sil():
        s = silnik()
        return s if s is not None and s.dziala() else None

    async def _czeka() -> list[dict]:
        s = _sil()
        if s is None or s.db is None:
            return []
        try:
            return await asyncio.to_thread(s.db.czeka_na_wlasciciela, limit=m.podpowiedzi.CZEKA_MAKS)
        except Exception as exc:                       # rozmowy.db zajęta albo stara: ekran startu bez tego bloku
            log(f"jarvo-hq: czeka na Ciebie: {type(exc).__name__}")
            return []

    async def _decyzje() -> list[dict]:
        try:
            return list(await asyncio.to_thread(decyzje) or [])
        except Exception as exc:                       # kanban niedostępny: start bez pytań zespołu
            log(f"jarvo-hq: decyzje: {type(exc).__name__}")
            return []

    @trasa("GET", "/app")
    @obsluga
    async def aplikacja(request: Request):
        tylko_ta_strona(request)
        s = _sil()
        lista, (wlasciciel, got), aktual, pytania = await asyncio.gather(
            asyncio.to_thread(agenci.lista), asyncio.to_thread(gotowosc.calosc), asyncio.to_thread(stan_aktualizacji), _decyzje())
        obrazy_wprost = True
        if s is not None:
            try:
                obrazy_wprost = bool(s._obrazy_wprost())
            except Exception:
                pass
        return {
            "wersja": hello().get("wersja", ""), "silnik": hello().get("silnik", "awaria"),
            "agenci": lista, "wlasciciel": wlasciciel, "gotowosc": got,
            "ustawienia": {"limit_przebiegow": getattr(s, "limit", None), "upload_max": UPLOAD_MAX,
                           "zalaczniki_max": trasy.ZALACZNIKI_MAKS, "obrazy_max": trasy.OBRAZY_MAKS,
                           "obrazy_body_max": trasy.OBRAZY_BAJTY},
            "funkcje": {"obrazy_wprost": obrazy_wprost, "komputer": os.environ.get("JARVO_KOMPUTER") == "1",
                        "telefon": bool(os.environ.get("JARVO_ANDROID_SCREEN_URL")), "agenci_wlasni": False,
                        "e2e": os.environ.get("JARVO_E2E") == "1"},
            "decyzje": len(pytania), "aktualizacja": aktual,
        }

    @trasa("GET", "/podpowiedzi")
    @obsluga
    async def podpowiedzi(request: Request, miejsce: str = "start"):
        tylko_ta_strona(request)
        if miejsce != "start":
            raise trasy.BladTrasy(422, "zle_dane", "Nieznane miejsce podpowiedzi.", "Unknown suggestion place.")
        rows, pytania = await asyncio.gather(_czeka(), _decyzje())
        czeka = m.podpowiedzi.czeka_wiersze(rows, 0, pytania)
        floty = await asyncio.to_thread(lambda: [a["name"] for a in agenci.lista()])
        try:
            wynik = await asyncio.to_thread(nawyki.start, floty, czeka=len(czeka))
        except Exception as exc:                       # nawyki.db zepsuta: same „Czeka”, bez starterów
            log(f"jarvo-hq: podpowiedzi: {type(exc).__name__}")
            wynik = {"tryb": "start", "podpowiedzi": [], "wersja": ""}
        return {**wynik, "czeka": czeka}

    @trasa("POST", "/podpowiedzi/{pid}/reakcja", status_code=204)
    @obsluga
    async def reakcja(pid: str, request: Request):
        body = await trasy.czytaj_cialo(request, ReakcjaBody)
        if not PODPOWIEDZ_WZOR.match(pid):
            raise trasy.BladTrasy(409, "nieznana", "Nie ma takiej podpowiedzi.", "No such suggestion.")
        try:
            await asyncio.to_thread(nawyki.reakcja, pid, body.rodzaj, body.klucz)
        except m.podpowiedzi.Nieznana:
            raise trasy.BladTrasy(409, "nieznana", "Nie ma takiej podpowiedzi.", "No such suggestion.") from None
        return Response(status_code=204)

    @trasa("POST", "/app/poznanie")
    @obsluga
    async def poznanie(request: Request):
        body = await trasy.czytaj_cialo(request, PoznanieBody)
        if not m.aplikacja.wiersz_poznania(body.imie, m.aplikacja.IMIE_MAKS):
            raise trasy.BladTrasy(422, "zle_dane", "Podaj imię.", "Enter your name.")
        try:
            wlasciciel = await asyncio.to_thread(gotowosc.zapisz_poznanie, body.model_dump())
        except OSError as exc:
            log(f"jarvo-hq: poznanie: zapis USER.md ({type(exc).__name__})")
            raise trasy.BladTrasy(500, "zapis", "Nie udało się zapisać profilu.", "Could not save the profile.") from None
        _w, got = await asyncio.to_thread(gotowosc.calosc)
        return {"wlasciciel": wlasciciel, "gotowosc": got}

    def _lektor():
        if glos is None:
            raise trasy.BladTrasy(503, "brak_glosu", "Głos Jarva nie jest zainstalowany.", "Jarvo's voice is not installed.")
        return glos

    @trasa("POST", "/app/glos")
    @obsluga
    async def mowa(request: Request):
        body = await trasy.czytaj_cialo(request, GlosBody)
        lektor = _lektor()
        try:
            sciezka = await lektor.mow(body.tekst, body.glos, body.tempo, body.jezyk)
        except ValueError:
            raise trasy.BladTrasy(422, "zle_dane", "Pusty tekst.", "Empty text.") from None
        except m.glos.BrakGlosu:
            raise trasy.BladTrasy(503, "brak_glosu", "Głos Jarva nie jest zainstalowany.", "Jarvo's voice is not installed.") from None
        except (m.glos.BladGlosu, OSError) as exc:
            log(f"jarvo-hq: głos: {type(exc).__name__}")
            raise trasy.BladTrasy(502, "glos_blad", "Lektor nie odpowiedział.", "The voice did not respond.") from None
        return FileResponse(sciezka, media_type="audio/wav", headers={"Cache-Control": "private, max-age=86400"})

    @trasa("POST", "/app/glos/przygotuj", status_code=202)
    @obsluga
    async def przygotuj(request: Request):
        body = await trasy.czytaj_cialo(request, PrzygotujBody)
        lektor = _lektor()
        try:
            n = lektor.przygotuj(body.teksty, body.glos, body.tempo, body.jezyk)
        except m.glos.BrakGlosu:
            raise trasy.BladTrasy(503, "brak_glosu", "Głos Jarva nie jest zainstalowany.", "Jarvo's voice is not installed.") from None
        return {"w_kolejce": n}

    return sciezki
