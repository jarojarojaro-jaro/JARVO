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
- `POST /app/klucz` `{klucz}`: mózg z karty „Mózg” pierwszego spotkania (mozg.py): rozpoznanie dostawcy po
  przedrostku, sprawdzenie u dostawcy, zapis do głównego `.env`, rozdanie agentom, przełączenie floty na zestaw
  dostawcy; odpowiedź `{dostawca, nazwa, gotowosc}`. Błędy: 422 `nieznany_klucz` / `klucz_odrzucony`, 503
  `brak_polaczenia`, 409 `brak_zestawu`, 500 `zapis`. Klucz nie wraca w odpowiedzi ani w dzienniku.
- `POST /app/mozg/chatgpt`: po zalogowaniu ChatGPT w karcie (Hermes: `/api/providers/oauth/openai-codex/start` i
  `/poll`, kod urządzenia) flota przechodzi na `openai-codex`; bez zalogowania 409 `brak_logowania`.
- `POST /app/pierwsza-sesja` `{jezyk}`: raz na instalację wątek „Pierwsza sesja” z wpisem systemowym i przebiegiem
  Jarva (skill `pierwsza-sesja`, treść `aplikacja.PIERWSZA_PROSBA`, bez wiadomości właściciela); odpowiedź
  `{watek_id, nowa}`. Druga próba zwraca ten sam wątek (`nowa: false`; pusty `watek_id`, gdy wątek usunięto).
  Bez podłączonego modelu 409 `brak_modelu`, bez imienia w USER.md 409 `brak_profilu`.
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
           mozg: dict | None = None, log: Callable[[str], None] | None = None) -> list[str]:
    """Rejestruje trasy startu. `trasy`: moduł trasy_rozmow (BladTrasy, blad, czytaj_cialo, _Model, ODCZYT_ZRODLA).
    `decyzje`: pytania zespołu ze Starej Bazy (hq_core.build_state → decisions). Języka nie podajemy: wybiera go
    przełącznik dashboardu w przeglądarce (localStorage), serwer go nie zna. `glos`: lektor aplikacji (glos.Glos);
    None = trasy głosu odpowiadają 503 `brak_glosu`. `mozg`: {home, flota (wywołanie → fleet.json), stan, build_json,
    rozdaj, status} dla tras mózgu; None = 503 `brak_mozgu`."""
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

    class KluczBody(trasy._Model):
        klucz: str = Field(..., min_length=1, max_length=400)

    class PierwszaBody(trasy._Model):
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

    # ------------------------------------------------------------------------------------------- mózg
    BLEDY_MOZGU = {
        "nieznany_klucz": (422, "Nie rozpoznaję tego klucza. Wklej klucz OpenRouter (sk-or-…), Anthropic (sk-ant-…) "
                                "albo OpenAI (sk-…).",
                           "I don't recognise this key. Paste an OpenRouter (sk-or-…), Anthropic (sk-ant-…) or OpenAI "
                           "(sk-…) key."),
        "klucz_odrzucony": (422, "{nazwa} nie przyjął tego klucza. Sprawdź, czy wkleiłeś go w całości i czy jest aktywny.",
                            "{nazwa} did not accept this key. Check that you pasted all of it and that it is active."),
        "brak_polaczenia": (503, "Nie mogę teraz sprawdzić klucza u {nazwa}. Sprawdź internet i spróbuj za chwilę.",
                            "I can't check the key with {nazwa} right now. Check the internet and try again."),
        "brak_zestawu": (409, "Ta wersja Jarva nie zna jeszcze tego dostawcy. Zaktualizuj Jarva (jarvo update).",
                         "This Jarvo version doesn't know this provider yet. Update Jarvo (jarvo update)."),
        "zapis": (500, "Nie udało się zapisać klucza. Spróbuj jeszcze raz.", "Could not save the key. Try again."),
    }
    zamek_mozgu = asyncio.Lock()

    def _mozg() -> dict:
        if mozg is None:
            raise trasy.BladTrasy(503, "brak_mozgu", "Podłączanie mózgu w aplikacji jest niedostępne.",
                                  "Connecting the brain in the app is unavailable.")
        return mozg

    def _blad_mozgu(kod: str, nazwa: str = "") -> trasy.BladTrasy:
        status, pl, en = BLEDY_MOZGU.get(kod, BLEDY_MOZGU["zapis"])
        return trasy.BladTrasy(status, kod, pl.format(nazwa=nazwa or "dostawca"), en.format(nazwa=nazwa or "the provider"))

    def _wywolaj_mozg(fn, **kw):
        k = _mozg()
        return fn(home=k["home"], flota=k["flota"](), stan=k["stan"], build_json=k.get("build_json"), **kw)

    @trasa("POST", "/app/klucz")
    @obsluga
    async def klucz(request: Request):
        body = await trasy.czytaj_cialo(request, KluczBody, maks=2048)
        k = _mozg()
        dostawca = m.mozg.rozpoznaj(body.klucz)
        nazwa = m.mozg.DOSTAWCY[dostawca]["nazwa"] if dostawca else ""
        async with zamek_mozgu:
            try:
                wynik = await asyncio.to_thread(_wywolaj_mozg, m.mozg.podlacz_klucz, klucz=body.klucz,
                                                rozdaj=k.get("rozdaj"))
            except m.mozg.BladMozgu as e:
                log(f"jarvo-hq: mózg: klucz {dostawca or 'nieznany'}: {e.kod}")
                raise _blad_mozgu(e.kod, nazwa) from None
        log(f"jarvo-hq: mózg: {wynik['dostawca']} podłączony ({len(wynik['profile'])} profili)")
        gotowosc.odswiez()
        _w, got = await asyncio.to_thread(gotowosc.calosc)
        return {"dostawca": wynik["dostawca"], "nazwa": wynik["nazwa"], "gotowosc": got}

    @trasa("POST", "/app/mozg/chatgpt")
    @obsluga
    async def chatgpt(request: Request):
        await trasy.czytaj_cialo(request, trasy._Model, maks=256)
        k = _mozg()
        stan = await asyncio.to_thread(k["status"], k["home"], m.mozg.CHATGPT)
        if not (stan and stan.get("polaczony")):
            raise trasy.BladTrasy(409, "brak_logowania", "Najpierw zaloguj się kontem ChatGPT.",
                                  "Sign in with your ChatGPT account first.")
        async with zamek_mozgu:
            try:
                wynik = await asyncio.to_thread(_wywolaj_mozg, m.mozg.podlacz_chatgpt)
            except m.mozg.BladMozgu as e:
                log(f"jarvo-hq: mózg: chatgpt: {e.kod}")
                raise _blad_mozgu(e.kod, "ChatGPT") from None
        log(f"jarvo-hq: mózg: chatgpt podłączony ({len(wynik['profile'])} profili)")
        gotowosc.odswiez()
        _w, got = await asyncio.to_thread(gotowosc.calosc)
        return {"dostawca": wynik["dostawca"], "nazwa": wynik["nazwa"], "gotowosc": got}

    # ------------------------------------------------------------------------------------------- pierwsza sesja
    def _istniejacy(sil, wid: str) -> str:
        w = sil.db.watek(wid)
        return wid if w and not w.get("usuniety_at") else ""

    @trasa("POST", "/app/pierwsza-sesja")
    @obsluga
    async def pierwsza(request: Request):
        body = await trasy.czytaj_cialo(request, PierwszaBody, maks=256)
        sil = _sil()
        if sil is None or sil.db is None or sil.rejestr is None:
            raise trasy.BladTrasy(503, "silnik", "Rozmowy jeszcze startują. Spróbuj za chwilę.",
                                  "Conversations are still starting. Try again in a moment.")
        jest = m.aplikacja.pierwsza_sesja(gotowosc.pierwsza)
        if jest:
            return {"watek_id": await asyncio.to_thread(_istniejacy, sil, jest["watek_id"]), "nowa": False}
        gotowosc.odswiez()
        model = await asyncio.to_thread(gotowosc.model)
        if not model.get("polaczony"):
            raise trasy.BladTrasy(409, "brak_modelu", "Najpierw podłącz mózg.", "Connect the brain first.")
        if not (await asyncio.to_thread(gotowosc.wlasciciel)).get("imie"):
            raise trasy.BladTrasy(409, "brak_profilu", "Najpierw się poznajmy.", "Let's get to know each other first.")
        jezyk = body.jezyk

        async def _r():
            jest = m.aplikacja.pierwsza_sesja(gotowosc.pierwsza)    # dwa żądania naraz: drugie widzi zapis pierwszego
            if jest:
                return {"watek_id": _istniejacy(sil, jest["watek_id"]), "nowa": False}
            db, rej, hub = sil.db, sil.rejestr, sil.hub
            tekst = m.aplikacja.PIERWSZA_SYSTEM[jezyk]
            w = db.utworz_watek(tytul=m.aplikacja.PIERWSZA_TYTUL[jezyk], koordynator="jarvo", tytul_zrodlo="wlasciciel")
            wpis = db.dodaj_wpis(w["id"], rodzaj="system", tekst=tekst, dane={"typ": "pierwsza_sesja"})
            m.aplikacja.zapisz_pierwsza_sesja(gotowosc.pierwsza, w["id"], wpis["utworzony_at"])
            hub.nadaj("watek.wpis", {"watek_id": w["id"], "wpis": wpis}, watek_id=w["id"])
            db.zapewnij_czlonka(w["id"], "jarvo")
            p = rej.zlec(watek_id=w["id"], wpis_id=wpis["id"], agent="jarvo", prosba=m.aplikacja.PIERWSZA_PROSBA,
                         zrodlo="system", lancuch_id=wpis["id"])
            db.aktywnosc(w["id"], at=wpis["utworzony_at"], podglad=tekst)
            hub.nadaj("watek.zmiana", {"watek": m.przebiegi.watek_krotki(db.watek(w["id"]) or w)})
            log(f"jarvo-hq: pierwsza sesja: wątek {w['id']}, przebieg {p['id']}")
            return {"watek_id": w["id"], "nowa": True}

        try:
            return await sil.wykonaj(_r())
        except OSError as exc:
            log(f"jarvo-hq: pierwsza sesja: {type(exc).__name__}")
            raise trasy.BladTrasy(500, "zapis", "Nie udało się zacząć sesji.", "Could not start the session.") from None

    return sciezki
