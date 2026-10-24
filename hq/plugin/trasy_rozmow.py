"""Trasy rozmów aplikacji Jarvo (docs/HQ.md „Rozmowy”, montowane pod /api/plugins/jarvo-hq/ na routerze wtyczki,
więc każda trasa zapisu dostaje ochronę CSRF z `ochrona.Trasa`).

- Wątki: `GET/POST /rozmowy`, `GET/PATCH/DELETE /rozmowy/{id}`, `POST /rozmowy/{id}/przywroc`, `/przeczytane`.
- Oś czasu: `GET /rozmowy/{id}/os` (scalanie wpisów aplikacji z sesjami członków w state.db, kursor nieprzezroczysty).
- Eksport: `GET /rozmowy/{id}/eksport` (cała oś jako plik Markdown, przez `ochrona.utajnij`); agenci: `GET /agenci`.
- Wysyłka: `POST /rozmowy/{id}/wiadomosci` (wzmianki, załączniki przez `safe_path`, obrazy sprawdzane po magicznych
  bajtach i limit 7 000 000 bajtów zakodowanych data URL → 413 `za_duze` zanim cokolwiek pójdzie do bramy).
- Przebiegi: `GET /przebiegi/{id}`, `POST …/stop` (i `…/zatrzymaj`), `…/anuluj`, `…/wyslij` (i `…/wyslij-teraz`),
  `…/zgoda`, `…/dopisz`, `…/ponow`.
- Strumień: `GET /strumien` (SSE, jeden na przeglądarkę), `POST /strumien/{klient}/subskrypcje`.
Treści JSON parsują modele pydantic (`model_validate_json`), a każdy błąd ma kształt
`{"blad": {"kod", "komunikat", "komunikat_en"}}`. Zapisy idą przez wątek silnika (`Silnik.wykonaj`), odczyty listy
i osi przez `asyncio.to_thread` (krótkie połączenia tylko do odczytu).

- **Odczyty tylko z tej strony**: GET tras rozmów, przebiegów i strumienia z `Sec-Fetch-Site` innym niż
  `same-origin`/`none` = 403 `csrf` (strony agentów na innych portach localhost to dla przeglądarki ta sama witryna
  i niosą ciasteczko; bez tego mogłyby trzymać strumienie i zajmować połączenia przeglądarki).
- **Tempo**: 10 wysyłek (wiadomość albo dopisz) na 10 s na ciasteczko logowania, sprawdzane PRZED czytaniem treści
  (pełne okno = 429 `za_szybko` z `ponow_za_s` bez buforowania 7,6 MB; także dla powtórki, bo klucz jest w treści).
  Sprawdzenie od razu rezerwuje miejsce w oknie (równoległe żądania nie przejdą wszystkie), a trasa oddaje je, gdy
  nie powstał nowy wpis (powtórka z tym samym `klucz`, odrzucona wysyłka, błąd); nowe wątki osobno, 30 na minutę.
- **Ten sam `klucz`**: wiadomość i dopisz z kluczem, który jest w drodze albo już zapisany, dostają tę samą odpowiedź
  bez drugiego steera i drugiej wysyłki (rezerwacja klucza na pętli silnika przed pierwszym `await`, osobno dla
  wiadomości i dopisz; „Dopisz” wiadomości z kolejki zapisuje klucz w przebiegu). Klucz innej wiadomości w dopisz =
  409 `klucz_zajety`. Dopisz do pracy w wątku w koszu = 409 `w_koszu`. `POST /rozmowy` z wiadomością: ten sam
  `wiadomosc.klucz` = ten sam wątek (klucz pierwszego wpisu, `jednorazowo` dla żądań naraz), a nieudana pierwsza
  wysyłka usuwa właśnie założony wątek (bez pustych wątków po ponowieniach).
- **Kosz w trakcie wysyłki**: wątek czytany na nowo na pętli silnika przed zapisem obrazów, przed steerem i przed
  wpisem (DELETE mógł przyjść w trakcie sprawdzania w wątku roboczym): kosz = 409 `w_koszu`, usunięty = 404 `brak`,
  bez wpisu, przebiegu i plików obrazów.
- **Walidacja wysyłki** (obrazy, załączniki, adresaci) w wątku roboczym (`asyncio.to_thread`), nie na pętli serwera.
- **Snapshoty**: `seq` w `GET /rozmowy/{id}` brany PRZED odczytem (zdarzenie w trakcie odczytu przyjdzie jeszcze raz,
  zamiast zginąć).
Testy: tests/test_silnik_rozmow.py, tests/test_trasy_rozmow.py.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import functools
import hashlib
import os
import time
import unicodedata
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Literal

from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

TEKST_MAKS = 32_000
DOPISZ_MAKS = 4_000
OBRAZY_MAKS = 4
ZALACZNIKI_MAKS = 8
OBRAZY_BAJTY = 7_000_000           # suma zakodowanych data URL (≈ 5,2 MB obrazów); brama przyjmuje ≤ 10 000 000 bajtów
CIALO_WYSYLKI_MAKS = 7_600_000     # całe żądanie wysyłki (obrazy + tekst + JSON); więcej = 413 za_duze bez parsowania
CIALO_MAKS = 64_000                # inne trasy JSON
TEMPO = (10, 10.0)                 # 10 wysyłek na 10 s na sesję logowania (ciasteczko)
TEMPO_WATKOW = (30, 60.0)          # nowe wątki: 30 na minutę
ODCZYT_ZRODLA = ("same-origin", "none")
KLUCZ_WZOR = r"^[A-Za-z0-9_-]{1,64}$"


# ----------------------------------------------------------------------------------------------- modele treści

class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Obraz(_Model):
    nazwa: str = Field("", max_length=200)
    dane: str


class WyslijBody(_Model):
    tekst: str = Field("", max_length=TEKST_MAKS)
    klucz: str = Field(..., pattern=KLUCZ_WZOR)
    zalaczniki: list[str] = Field(default_factory=list, max_length=ZALACZNIKI_MAKS)
    obrazy: list[Obraz] = Field(default_factory=list)
    adresaci: list[str] | None = Field(None, max_length=12)
    tryb_kolejki: Literal["czekaj", "dopisz"] = "czekaj"
    odpowiedz_na: str | None = None


class NowyWatekBody(_Model):
    tytul: str = Field("", max_length=120)
    koordynator: str = Field("jarvo", max_length=64)
    wiadomosc: WyslijBody | None = None


class ZmianaWatkuBody(_Model):
    tytul: str | None = Field(None, min_length=1, max_length=120)
    przypiety: bool | None = None
    archiwum: bool | None = None
    praca: Literal["zatrzymaj", "zostaw"] | None = None


class PrzeczytaneBody(_Model):
    do_at: float = Field(..., ge=0, allow_inf_nan=False)


class ZgodaBody(_Model):
    wybor: str = Field(..., min_length=1, max_length=40)
    request_id: str = Field(..., min_length=1, max_length=200)


class DopiszBody(_Model):
    tekst: str = Field(..., min_length=1, max_length=DOPISZ_MAKS)
    klucz: str | None = Field(None, pattern=KLUCZ_WZOR)


class SubskrypcjeBody(_Model):
    watki: list[str] = Field(default_factory=list, max_length=200)
    panele: list[dict] = Field(default_factory=list, max_length=50)
    sesje: list[dict] = Field(default_factory=list, max_length=50)


# ----------------------------------------------------------------------------------------------- błędy

class BladTrasy(Exception):
    def __init__(self, status: int, kod: str, komunikat: str, komunikat_en: str = "", **dane):
        super().__init__(kod)
        self.status, self.kod, self.komunikat, self.komunikat_en, self.dane = status, kod, komunikat, komunikat_en, dane


def blad(status: int, kod: str, komunikat: str, komunikat_en: str = "", **dane) -> JSONResponse:
    return JSONResponse({"blad": {"kod": kod, "komunikat": komunikat, "komunikat_en": komunikat_en, **dane}},
                        status_code=status)


SILNIK = ("Silnik rozmów nie działa — odśwież stronę albo zajrzyj do Ustawienia › Stan.",
          "The conversation engine is not running — reload the page or check Settings › Status.")


async def czytaj_cialo(request: Request, model: type[_Model], *, maks: int = CIALO_MAKS) -> _Model:
    """Treść JSON → model pydantic; za duża = 413 `za_duze`, zła = 422 `zle_dane` (w formacie błędów aplikacji)."""
    typ = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if typ != "application/json":
        raise BladTrasy(415, "zly_typ", "Treść musi być w JSON.", "The body must be JSON.")
    try:
        dlugosc = int(request.headers.get("content-length") or 0)
    except ValueError:
        dlugosc = 0
    za_duze = BladTrasy(413, "za_duze", "Za duża wiadomość — wyślij mniejsze albo mniej obrazów.",
                        "The message is too large — send smaller or fewer images.")
    if dlugosc > maks:
        raise za_duze
    dane = bytearray()
    async for kawalek in request.stream():
        dane += kawalek
        if len(dane) > maks:
            raise za_duze
    try:
        return model.model_validate_json(bytes(dane) or b"{}")
    except ValidationError as e:
        pierwszy = (e.errors() or [{}])[0]
        pole = ".".join(str(x) for x in pierwszy.get("loc") or ())
        raise BladTrasy(422, "zle_dane", f"Niepoprawne dane ({pole or 'treść'}).", f"Invalid data ({pole or 'body'}).",
                        pole=pole) from None


# ----------------------------------------------------------------------------------------------- eksport

EKSPORT_STRON = 100                # najwyżej 100 stron osi po 200 pozycji (20 000 pozycji)
_ETYKIETY_EKSPORTU = {"system": "", "kompresja": "", "luka": "", "dostawa": "Wynik w tle: ", "budzenie": "Powrót z pracą: ",
                      "dopisano": "Dopisane do trwającej pracy: ", "obca": "Wiadomość spoza aplikacji: ",
                      "blad_tury": "Tura się nie udała: ", "przekazanie": "Przekazanie: "}


def nazwa_pliku_eksportu(tytul: str) -> str:
    """„Strona dla piekarni Złoty Kłos” → „rozmowa-strona-dla-piekarni-zloty-klos.md” (ASCII, do 60 znaków)."""
    s = unicodedata.normalize("NFKD", (tytul or "").replace("ł", "l").replace("Ł", "L"))
    s = "".join(c for c in s if not unicodedata.combining(c)).encode("ascii", "ignore").decode().lower()
    s = "-".join("".join(c if c.isalnum() else " " for c in s).split())[:60].strip("-")
    return f"rozmowa-{s}.md" if s else "rozmowa.md"


def eksport_md(tytul: str, pozycje: list[dict], nazwy: dict[str, str], *, teraz: float,
               utajnij: Callable[[str], str] = lambda t: t) -> str:
    """Oś czasu wątku jako Markdown: teksty właściciela i agentów, pliki (ścieżki), kroki w jednej linii, notatki
    systemowe kursywą. Całość przez `utajnij` (sekrety z treści i podglądów nie wychodzą w pliku)."""
    def kiedy(ts: float) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts or 0)))

    linie = [f"# {' '.join((tytul or 'Rozmowa').split())}", "", f"Eksport rozmowy z Jarva · {kiedy(teraz)}", ""]
    for p in pozycje:
        rodzaj, tekst = p.get("rodzaj"), (p.get("tekst") or "").strip()
        if rodzaj in ("wlasciciel", "agent"):
            kto = "Ty" if rodzaj == "wlasciciel" else nazwy.get(p.get("agent") or "", p.get("agent") or "Agent")
            tryb = " · bezpośrednio" if p.get("tryb") == "bezposrednio" else ""
            linie += ["---", "", f"**{kto}** · {kiedy(p.get('ts'))}{tryb}", ""]
            if tekst:
                linie += [tekst, ""]
            if rodzaj == "wlasciciel":
                linie += [f"📎 {f.get('path')}" for f in p.get("pliki") or [] if f.get("path")]
                if p.get("pliki"):
                    linie.append("")
        elif rodzaj == "kroki":
            kroki = [k.get("verb") or k.get("narzedzie") or "" for k in p.get("kroki") or []]
            if kroki:
                reszta = f" i {len(kroki) - 12} więcej" if len(kroki) > 12 else ""
                linie += [f"_Kroki: {' · '.join(x for x in kroki[:12] if x)}{reszta}_", ""]
        elif tekst:
            linie += [f"_{_ETYKIETY_EKSPORTU.get(rodzaj, '')}{' '.join(tekst.split())[:2000]}_", ""]
    return utajnij("\n".join(linie).rstrip() + "\n")


# ----------------------------------------------------------------------------------------------- trasy

def dolacz(router, *, m: SimpleNamespace, silnik: Callable[[], Any], hub, agenci, inbox: Path | str,
           log: Callable[[str], None] | None = None, zegar: Callable[[], float] = time.time) -> list[str]:
    """Rejestruje trasy rozmów na routerze wtyczki. `m`: moduły wtyczki (hq_core, ochrona, rozmowy, przebiegi,
    scalanie, budzenia, kontekst, wzmianki, silnik). Zwraca listę ścieżek (dla testów)."""
    log = log or (lambda _m: None)
    core, ochrona, przebiegi = m.hq_core, m.ochrona, m.przebiegi
    inbox = Path(inbox)
    tempo: dict[str, deque] = {}
    w_drodze: dict[tuple, asyncio.Future] = {}        # (rodzaj, wątek, klucz) w trakcie zapisu; tylko na pętli silnika
    sciezki: list[str] = []

    def trasa(metoda: str, sciezka: str, **kw):
        sciezki.append(f"{metoda} {sciezka}")
        return router.api_route(sciezka, methods=[metoda], **kw)

    def obsluga(fn):
        """Błędy tras, rejestru i silnika → {"blad": …}."""
        @functools.wraps(fn)
        async def owiniete(*a, **kw):
            try:
                return await fn(*a, **kw)
            except BladTrasy as e:
                return blad(e.status, e.kod, e.komunikat, e.komunikat_en, **e.dane)
            except przebiegi.Blad as e:
                return blad(e.status, e.kod, e.komunikat, e.komunikat_en, **e.dane)
            except m.silnik.SilnikNiedostepny:
                return blad(503, "silnik", *SILNIK)
        return owiniete

    def s():
        sil = silnik()
        if sil is None or not sil.dziala():
            raise BladTrasy(503, "silnik", *SILNIK)
        return sil

    def tylko_ta_strona(request: Request) -> None:
        """GET tylko z karty panelu (albo wpisany adres): strona agenta z innego portu localhost niesie ciasteczko."""
        skad = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if skad and skad not in ODCZYT_ZRODLA:
            ochrona.ODMOWY["razem"] += 1
            log(f"jarvo-hq: odczyt odrzucony GET {request.url.path} (sec-fetch-site={skad[:20]})")
            raise BladTrasy(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                            "Read refused: the request did not come from the Jarvo dashboard.")

    async def jednorazowo(klucz: tuple | None, fn: Callable[[], Any]):
        """Na pętli silnika: drugie żądanie z tym samym (wątek, klucz), gdy pierwsze jest w drodze, czeka na jego
        wynik zamiast robić to samo drugi raz (steer, wysyłka). Bez klucza = zwykłe wywołanie."""
        if klucz is None:
            return await fn()
        jest = w_drodze.get(klucz)
        if jest is not None:
            return await asyncio.shield(jest)
        f = asyncio.get_running_loop().create_future()
        w_drodze[klucz] = f
        try:
            wynik = await fn()
        except Exception as e:
            f.set_exception(e)
            f.exception()                            # odebrany: brak ostrzeżenia, gdy nikt nie czekał
            raise
        except BaseException:
            f.cancel()
            raise
        else:
            f.set_result(wynik)
            return wynik
        finally:
            w_drodze.pop(klucz, None)

    def id_watku(wid: str) -> str:
        if not ochrona.WATEK_RE.fullmatch(wid or ""):
            raise BladTrasy(404, "brak", "Nie ma takiej rozmowy.", "No such conversation.")
        return wid

    def id_przebiegu(pid: str) -> str:
        if not ochrona.PRZEBIEG_RE.fullmatch(pid or ""):
            raise BladTrasy(404, "brak", "Nie ma takiej pracy.", "No such run.")
        return pid

    def sprawdz_watek(w: dict | None, *, kosz: bool = True) -> dict:
        """Wątek albo 404 `brak`; `kosz=False`: wątek w koszu = 409 `w_koszu`."""
        if w is None:
            raise BladTrasy(404, "brak", "Nie ma takiej rozmowy.", "No such conversation.")
        if not kosz and w.get("usuniety_at"):
            raise BladTrasy(409, "w_koszu", "Ta rozmowa jest w koszu — przywróć ją, żeby pisać dalej.",
                            "This conversation is in the trash — restore it to keep writing.")
        return w

    async def watek_lub_404(sil, wid: str, *, kosz: bool = True) -> dict:
        return sprawdz_watek(await asyncio.to_thread(sil.db.watek, id_watku(wid)), kosz=kosz)

    def nazwy() -> dict[str, str]:
        try:
            return agenci.nazwy_wyswietlane()
        except Exception:
            return {}

    def plik(raw: str) -> dict | None:
        p = core.safe_path(str(raw or ""), core.Roots())
        if p is None:
            return None
        try:
            return core.file_entry(p)
        except OSError:
            return None

    def watek_pelny(sil, w: dict) -> dict:
        """Watek (pełny) = WatekKrotki + członkowie z sesjami, aktywne przebiegi, nieudane do ponowienia i karty."""
        db, rej = sil.db, sil.rejestr
        d = przebiegi.watek_krotki(w)
        d.update(utworzony_at=w.get("utworzony_at"), tytul_zrodlo=w.get("tytul_zrodlo"),
                 czlonkowie_pelni=[{k: c.get(k) for k in ("agent", "sesja_id", "sesja_tip", "widzial_at")}
                                   for c in db.czlonkowie(w["id"], rola="rozmowa")],
                 przebiegi_aktywne=[rej.widok(p, tekst=False) for p in db.przebiegi_watku(w["id"], aktywne=True)
                                    if p.get("zrodlo") != "nadzor"],
                 przebiegi_do_ponowienia=[rej.widok(p, tekst=False) for p in db.przebiegi_do_ponowienia(w["id"])],
                 karty=db.karty_watku(w["id"]))
        return d

    # ------------------------------------------------------------------------------------------- wysyłka
    def _okno(request: Request, rodzaj: str) -> tuple[deque, tuple[int, float]]:
        granice = TEMPO_WATKOW if rodzaj == "watek" else TEMPO
        klucz = rodzaj + ":" + hashlib.sha256(request.headers.get("cookie", "").encode()).hexdigest()[:16]
        okno = tempo.setdefault(klucz, deque())
        teraz = time.monotonic()
        while okno and teraz - okno[0] > granice[1]:
            okno.popleft()
        if len(tempo) > 1000:
            for k in [k for k, v in tempo.items() if not v or teraz - v[-1] > TEMPO_WATKOW[1]]:
                tempo.pop(k, None)
            okno = tempo.setdefault(klucz, okno)
        return okno, granice

    def sprawdz_tempo(request: Request, rodzaj: str = "wysylka") -> tuple[deque, float]:
        """Pełne okno = 429; inaczej rezerwuje miejsce w oknie od razu (równoległe żądania jednego ciasteczka nie
        przejdą wszystkie przed pierwszym zapisem). Trasa oddaje rezerwację (`oddaj_tempo`), gdy nie powstał nowy wpis
        ani wątek."""
        okno, granice = _okno(request, rodzaj)
        if len(okno) >= granice[0]:
            za = max(1, int(granice[1] - (time.monotonic() - okno[0])) + 1)     # kiedy zwolni się miejsce w oknie
            if rodzaj == "watek":
                raise BladTrasy(429, "za_szybko", "Za dużo nowych rozmów naraz — poczekaj chwilę.",
                                "Too many new conversations at once — wait a moment.", ponow_za_s=za)
            raise BladTrasy(429, "za_szybko", "Za dużo wiadomości naraz — poczekaj chwilę.",
                            "Too many messages at once — wait a moment.", ponow_za_s=za)
        t = time.monotonic()
        okno.append(t)
        return okno, t

    def oddaj_tempo(rezerwacja: tuple[deque, float] | None) -> None:
        """Powtórka, odrzucona wysyłka albo błąd: miejsce w oknie wraca."""
        if rezerwacja is None:
            return
        okno, t = rezerwacja
        try:
            okno.remove(t)
        except ValueError:
            pass

    def obrazy_z(body: WyslijBody) -> list[tuple[str, bytes, str]]:
        """(nazwa, bajty, mime) każdego obrazu; limity sprawdzane przed dekodowaniem i zanim cokolwiek pójdzie dalej."""
        if len(body.obrazy) > OBRAZY_MAKS:
            raise BladTrasy(422, "za_duzo_obrazow", f"Najwyżej {OBRAZY_MAKS} obrazy w jednej wiadomości.",
                            f"At most {OBRAZY_MAKS} images per message.")
        if sum(len(o.dane) for o in body.obrazy) > OBRAZY_BAJTY:
            raise BladTrasy(413, "za_duze", "Obrazy są za duże — wyślij mniejsze albo mniej.",
                            "The images are too large — send smaller or fewer.")
        out = []
        for o in body.obrazy:
            naglowek, _, b64 = o.dane.partition(",")
            if not naglowek.startswith("data:") or not naglowek.endswith(";base64") or not b64:
                raise BladTrasy(422, "zly_obraz", "Obraz musi przyjść jako data URL (base64).",
                                "An image must be a base64 data URL.")
            try:
                dane = base64.b64decode(b64, validate=True)
            except (binascii.Error, ValueError):
                raise BladTrasy(422, "zly_obraz", "Uszkodzony obraz.", "Corrupted image.") from None
            mime = ochrona.sprawdz_obraz(dane)
            if mime is None:
                raise BladTrasy(415, "zly_obraz", "To nie jest obraz PNG, JPEG, WebP ani GIF.",
                                "This is not a PNG, JPEG, WebP or GIF image.")
            out.append((o.nazwa, dane, mime))
        return out

    def usun_obrazy(obrazy: list[dict]) -> None:
        """Pliki obrazów wiadomości, która nie powstała (błąd, wątek usunięty w trakcie, wyścig tego samego klucza)."""
        for o in obrazy:
            try:
                Path(o["path"]).unlink(missing_ok=True)
            except OSError:
                pass

    def zapisz_obrazy(obrazy: list[tuple[str, bytes, str]]) -> list[dict]:
        """Obrazy do inboxa (nazwa z `upload_target`, rozszerzenie z rozpoznanego typu); do wpisu tylko ścieżki.
        Plik rezerwowany atomowo (`O_EXCL`): dwie równoczesne wysyłki obrazu o tej samej nazwie dostają dwa pliki.
        Błąd przy którymś obrazie usuwa zapisane wcześniej pliki tej wiadomości; błąd dysku = 507 `dysk`."""
        out: list[dict] = []
        teraz = zegar()
        try:
            for nazwa, dane, mime in obrazy:
                rdzen = Path(str(nazwa or "obraz")).stem[:80] or "obraz"
                for _proba in range(100):
                    cel = core.upload_target(inbox, rdzen + ochrona.OBRAZY[mime], teraz)
                    cel.parent.mkdir(parents=True, exist_ok=True)
                    if os.path.lexists(cel):      # Windows: O_EXCL przechodzi przez wiszące dowiązanie i tworzy jego cel
                        continue
                    try:
                        fd = os.open(cel, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    except FileExistsError:
                        continue
                    break
                else:
                    raise BladTrasy(409, "zajete", "Nie da się zapisać obrazu — spróbuj jeszcze raz.",
                                    "The image could not be saved — try again.")
                try:
                    with os.fdopen(fd, "wb") as f:
                        f.write(dane)
                except OSError:
                    cel.unlink(missing_ok=True)
                    raise
                out.append({"path": cel.as_posix(), "name": cel.name, "size": len(dane), "mime": mime})
        except OSError:
            usun_obrazy(out)
            raise BladTrasy(507, "dysk", "Nie da się zapisać obrazu na dysku — sprawdź wolne miejsce.",
                            "The image could not be saved to disk — check free space.") from None
        except BaseException:
            usun_obrazy(out)
            raise
        return out

    def znaki_sterujace(tekst: str) -> bool:
        """Znaki sterujące, formatujące i separatory linii (nowa linia, zero-width, odwrócenie kierunku U+202E,
        U+2028/U+2029, które model i `splitlines` biorą za koniec linii) w ścieżce."""
        return any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in str(tekst))

    def zalaczniki_z(body: WyslijBody) -> list[dict]:
        out = []
        for raw in body.zalaczniki:
            # nazwa pliku idzie linią „📎 <ścieżka>” do części właściciela: nowa linia w nazwie dopisałaby mu prośbę.
            # Sprawdzana też ścieżka po rozwiązaniu dowiązań (to ona trafia do wiadomości): agent może podłożyć czyste
            # dowiązanie do pliku o nazwie z nową linią
            e = None if znaki_sterujace(raw) else plik(raw)
            if e is not None and znaki_sterujace(e.get("path") or ""):
                e = None
            if e is None:
                raise BladTrasy(422, "zla_sciezka", "Nie widzę tego pliku na dysku floty.",
                                "That file is not on the fleet disk.", sciezka=str(raw)[:200])
            out.append({k: e.get(k) for k in ("path", "name", "size", "kind")})
        return out

    def adresaci_z(body: WyslijBody, koordynator: str) -> tuple[list[str], str, list[str]]:
        lista = agenci.lista()
        wynik = m.wzmianki.parsuj(body.tekst, m.wzmianki.mapa_aliasow(lista), koordynator=koordynator, nazwy=nazwy())
        ostrzezenia = list(wynik.ostrzezenia)
        adresaci = list(wynik.adresaci)
        if body.adresaci is not None:
            znane = {a["name"] for a in lista}
            nieznani = [a for a in body.adresaci if a not in znane]
            if nieznani or not body.adresaci:
                raise BladTrasy(422, "nieznany_agent", "Nie ma takiego agenta.", "No such agent.",
                                agenci=nieznani[:5])
            adresaci = list(dict.fromkeys(body.adresaci))
        if agenci.agent(koordynator) is None and koordynator in adresaci:
            raise BladTrasy(409, "nieznany_agent", "Agent tej rozmowy nie jest już dostępny.",
                            "This conversation's agent is no longer available.")
        return adresaci, wynik.tresc, ostrzezenia

    def przygotuj_wysylke(body: WyslijBody, koordynator: str) -> dict:
        """Wszystko, co da się sprawdzić bez zapisu: obrazy, załączniki, adresaci, pusta treść (tempo sprawdza
        trasa przed czytaniem treści). Blokujące (dekodowanie do 7 MB obrazów, stat plików): trasa woła przez
        `asyncio.to_thread`."""
        obrazy = obrazy_z(body)
        zalaczniki = zalaczniki_z(body)
        adresaci, tresc, ostrzezenia = adresaci_z(body, koordynator)
        if not tresc and not obrazy and not zalaczniki:
            raise BladTrasy(409, "pusta_tresc", "Nie ma czego wysłać.", "There is nothing to send.")
        ostrzezenia = [o for o in ostrzezenia if o != "pusta_tresc"]
        return {"obrazy": obrazy, "zalaczniki": zalaczniki, "adresaci": adresaci, "tresc": tresc,
                "ostrzezenia": ostrzezenia}

    async def wyslij_na_silniku(sil, wid: str, body: WyslijBody, prz: dict) -> dict:
        """Zapis wpisu i przebiegów (na wątku silnika). Ten sam `klucz` = ta sama odpowiedź, bez drugiej wysyłki
        (także gdy pierwsze żądanie jeszcze trwa). `_nowy` (zdejmuje trasa) = powstał nowy wpis."""
        return await jednorazowo(("wpis", wid, body.klucz), lambda: _wyslij_na_silniku(sil, wid, body, prz))

    def powtorka(sil, wid: str, klucz: str | None) -> dict | None:
        if not klucz:
            return None
        db, rej = sil.db, sil.rejestr
        jest = db.wpis_po_kluczu(wid, klucz)
        if jest is None:
            return None
        return {"wpis": jest, "przebiegi": [rej.widok(p, tekst=False) for p in db.przebiegi_watku(wid)
                                            if p.get("wpis_id") == jest["id"]], "ostrzezenia": []}

    def powtorka_watku(sil, klucz: str) -> dict | None:
        """`POST /rozmowy` z wiadomością, której klucz już założył wątek (pierwszy wpis): ten wątek, wpis i przebiegi."""
        w = sil.db.watek_po_kluczu(klucz)
        if w is None:
            return None
        return {"watek": watek_pelny(sil, w), **(powtorka(sil, w["id"], klucz) or {})}

    async def _wyslij_na_silniku(sil, wid: str, body: WyslijBody, prz: dict) -> dict:
        db, rej = sil.db, sil.rejestr
        # wątek na nowo, na pętli silnika: kosz albo trwałe usunięcie mogły przyjść w trakcie sprawdzania wysyłki
        watek = sprawdz_watek(db.watek(wid), kosz=False)
        jest = powtorka(sil, wid, body.klucz)
        if jest is not None:
            return jest
        koordynator = watek.get("koordynator") or "jarvo"
        adresaci, tresc, ostrzezenia = prz["adresaci"], prz["tresc"], list(prz["ostrzezenia"])
        obrazy = await asyncio.to_thread(zapisz_obrazy, prz["obrazy"]) if prz["obrazy"] else []
        try:
            if obrazy:                      # zapis obrazów oddał pętlę: DELETE wątku mógł przyjść w tym czasie
                sprawdz_watek(db.watek(wid), kosz=False)
            pliki = [z["path"] for z in prz["zalaczniki"]] + [o["path"] for o in obrazy]
            prosba = core.compose_message(tresc, pliki)
            tryb = "jarvo" if koordynator in adresaci else "bezposrednio"
            n = nazwy()
            przed = {c["agent"] for c in db.czlonkowie(wid, rola="rozmowa")}
            dane: dict[str, Any] = {}
            dopisany = None
            if body.tryb_kolejki == "dopisz":
                akt = None
                if len(adresaci) == 1 and not obrazy:
                    akt = next((p for p in db.przebiegi_watku(wid, aktywne=True)
                                if p["agent"] == adresaci[0] and (p.get("rola") or "rozmowa") == "rozmowa"
                                and p["stan"] in ("pracuje", "czeka_na_ture", "przyjety") and p.get("run_id")), None)
                if akt is not None:
                    try:
                        dopisany = await rej.dopisz(akt["id"], prosba)
                        dane["dopisane_do"] = akt["id"]
                    except przebiegi.Blad:
                        ostrzezenia.append(f"dopisz_niemozliwe:{adresaci[0]}")
                    sprawdz_watek(db.watek(wid))    # usunięty na stałe w trakcie steera: 404 (w koszu: wpis zostaje)
                else:
                    ostrzezenia.append(f"dopisz_niemozliwe:{','.join(adresaci)}")
            if body.odpowiedz_na and ochrona.WPIS_RE.fullmatch(body.odpowiedz_na):
                dane["odpowiedz_na"] = body.odpowiedz_na
            w = db.dodaj_wpis(wid, rodzaj="wlasciciel", tekst=body.tekst, tresc=tresc, adresaci=adresaci, tryb=tryb,
                              zalaczniki=prz["zalaczniki"], obrazy=obrazy, dane=dane, klucz=body.klucz)
        except BaseException:
            usun_obrazy(obrazy)                 # wiadomość nie powstała: jej obrazy nie zostają w inboxie
            raise
        if w.get("powtorzony"):              # wyścig dwóch żądań z tym samym kluczem
            usun_obrazy(obrazy)
            return {"wpis": w, "przebiegi": [], "ostrzezenia": []}
        # dalej bez `await`: nic nie wejdzie między wpis a zlecenia (DELETE wątku czeka na swoją kolej na pętli)
        hub.nadaj("watek.wpis", {"watek_id": wid, "wpis": w}, watek_id=wid)
        if przed:
            for a in adresaci:
                if a not in przed:
                    s_ = db.dodaj_wpis(wid, rodzaj="system", tekst=f"Dołącza: {n.get(a, a)}",
                                       dane={"typ": "dolaczyl", "agent": a})
                    hub.nadaj("watek.wpis", {"watek_id": wid, "wpis": s_}, watek_id=wid)
        for a in adresaci:
            db.zapewnij_czlonka(wid, a)
        nowe: list[dict] = []
        if dopisany is not None:
            nowe.append(db.zmien_przebieg(dopisany["id"], wpis_id=w["id"]))
        else:
            for a in adresaci:
                tekst_a = m.kontekst.prosba_wlasciciela(prosba, inni=[x for x in adresaci if x != a], nazwy=n)
                nowe.append(rej.zlec(watek_id=wid, wpis_id=w["id"], agent=a, prosba=tekst_a,
                                     obrazy=[{"path": o["path"], "mime": o["mime"]} for o in obrazy],
                                     lancuch_id=w["id"], nadzorowany=a != koordynator))
        if not watek.get("tytul") and watek.get("tytul_zrodlo", "auto") == "auto":
            tytul = m.rozmowy.tytul_z_tresci(tresc, obrazy=len(obrazy), at=w["utworzony_at"])
            if tytul:
                db.zmien(wid, tytul=tytul, tytul_zrodlo="auto")
        nowy = db.aktywnosc(wid, at=w["utworzony_at"], podglad=f"Ty: {tresc or (obrazy and 'obraz') or 'plik'}")
        db.przeczytane(wid, w["utworzony_at"])
        nowy = db.watek(wid) or nowy
        hub.nadaj("watek.zmiana", {"watek": przebiegi.watek_krotki(nowy)})
        return {"wpis": w, "przebiegi": [rej.widok(p, tekst=False) for p in nowe], "ostrzezenia": ostrzezenia,
                "_nowy": True}

    # ------------------------------------------------------------------------------------------- wątki
    @trasa("GET", "/rozmowy")
    @obsluga
    async def lista_rozmow(request: Request, filtr: str = "rozmowy", q: str = "", limit: int = 50, przed: str = ""):
        tylko_ta_strona(request)
        sil = s()
        if filtr not in ("rozmowy", "przypiete", "archiwum", "kosz"):
            raise BladTrasy(422, "zle_dane", "Nieznany filtr.", "Unknown filter.")
        try:
            watki, dalej = await asyncio.to_thread(sil.db.lista, filtr=filtr, q=q[:200], limit=limit,
                                                   przed=przed or None)
        except ValueError:
            raise BladTrasy(422, "zly_kursor", "Zły kursor listy.", "Bad list cursor.") from None
        return {"watki": [przebiegi.watek_krotki(w) for w in watki], "dalej": m.rozmowy.kursor_tekst(dalej)}

    @trasa("POST", "/rozmowy", status_code=201)
    @obsluga
    async def nowa_rozmowa(request: Request):
        sil = s()
        rez_watek = sprawdz_tempo(request, "watek")
        rez_wpis = None
        nowy_watek = nowy_wpis = False
        try:
            body = await czytaj_cialo(request, NowyWatekBody, maks=CIALO_WYSYLKI_MAKS)
            koord = body.koordynator or "jarvo"
            if not agenci.moze_koordynowac(koord):
                raise BladTrasy(422, "zly_koordynator", "Tej rozmowy nie może prowadzić ten agent.",
                                "This agent cannot lead a conversation.")
            if body.wiadomosc:
                rez_wpis = sprawdz_tempo(request)
                jest = await asyncio.to_thread(powtorka_watku, sil, body.wiadomosc.klucz)
                if jest is not None:                # powtórzone żądanie: ten sam wątek, bez walidacji i tempa
                    return JSONResponse(jest, status_code=201)
            prz = await asyncio.to_thread(przygotuj_wysylke, body.wiadomosc, koord) if body.wiadomosc else None

            async def _r():
                if body.wiadomosc:                  # pierwsze żądanie z tym kluczem skończyło się w międzyczasie
                    jest = powtorka_watku(sil, body.wiadomosc.klucz)
                    if jest is not None:
                        return jest
                w = sil.db.utworz_watek(tytul=" ".join(body.tytul.split()), koordynator=koord,
                                        tytul_zrodlo="wlasciciel" if body.tytul.strip() else None)
                out: dict[str, Any] = {}
                if prz is not None:
                    try:
                        out = await wyslij_na_silniku(sil, w["id"], body.wiadomosc, prz)
                    except BaseException:
                        # utworzenie i pierwsza wysyłka razem: bez pustego wątku na liście (ponowienie założy nowy)
                        sil.db.usun(w["id"], trwale=True)
                        hub.nadaj("watek.usuniety", {"id": w["id"], "trwale": True})
                        raise
                w = sil.db.watek(w["id"])
                hub.nadaj("watek.zmiana", {"watek": przebiegi.watek_krotki(w)})
                return {"watek": watek_pelny(sil, w), **out, "_nowy_watek": True}

            # dwa żądania z tym samym kluczem naraz: drugie czeka na wynik pierwszego (jeden wątek, jedna wysyłka)
            klucz = ("watek", body.wiadomosc.klucz) if body.wiadomosc else None
            wynik = await sil.wykonaj(jednorazowo(klucz, _r))
            nowy_watek = bool(wynik.pop("_nowy_watek", False))
            nowy_wpis = bool(wynik.pop("_nowy", False))
            return JSONResponse(wynik, status_code=201)
        finally:
            if not nowy_watek:
                oddaj_tempo(rez_watek)
            if not nowy_wpis:
                oddaj_tempo(rez_wpis)

    @trasa("GET", "/rozmowy/{wid}")
    @obsluga
    async def rozmowa(wid: str, request: Request):
        tylko_ta_strona(request)
        sil = s()
        seq = hub.kursor()            # przed odczytem: zdarzenie w trakcie odczytu przyjdzie ze strumienia (nie zginie)
        w = await watek_lub_404(sil, wid)
        return {"watek": await asyncio.to_thread(watek_pelny, sil, w), "seq": seq}

    def praca_trwa(sil, wid: str) -> dict | None:
        akt = [p for p in sil.db.przebiegi_watku(wid, aktywne=True)
               if p["stan"] not in ("kolejka", "dopisany") and p.get("zrodlo") != "nadzor"]
        karty = [k for k in sil.db.karty_watku(wid) if (k.get("ostatni_stan") or "") in ("running", "ready", "todo",
                                                                                           "blocked", "review")]
        if not akt and not karty:
            return None
        return {"przebiegi": [{"id": p["id"], "agent": p["agent"], "stan": p["stan"]} for p in akt],
                "karty": [{"task_id": k["task_id"], "stan": k.get("ostatni_stan")} for k in karty]}

    async def porzadek_pracy(sil, wid: str, praca: str | None) -> None:
        """Przed archiwum albo koszem: aktywna praca bez wyboru = 409 (zanim cokolwiek się zmieni); potem kolejka
        anulowana (i dopiski czekające na koniec tury, chyba że praca zostaje), aktywna praca zatrzymana albo
        zostawiona."""
        db, rej = sil.db, sil.rejestr
        trwa = praca_trwa(sil, wid)
        if trwa is not None and praca is None:
            raise BladTrasy(409, "praca_trwa", "W tej rozmowie trwa praca — zatrzymać ją czy zostawić?",
                            "Work is running in this conversation — stop it or leave it?", **trwa)
        for p in db.przebiegi_watku(wid, aktywne=True):
            if p["stan"] == "kolejka" or (p["stan"] == "dopisany" and praca != "zostaw"):
                await rej.anuluj(p["id"], dopisany=True)
        if trwa is None:
            return
        if praca == "zatrzymaj":
            for p in trwa["przebiegi"]:
                try:
                    await rej.stop(p["id"])
                except przebiegi.Blad:
                    pass
        else:
            w = db.dodaj_wpis(wid, rodzaj="system", tekst="Praca zostawiona", dane={"typ": "praca_zostawiona"})
            hub.nadaj("watek.wpis", {"watek_id": wid, "wpis": w}, watek_id=wid)

    async def zmien_tytul_sesji(sil, wid: str, tytul: str) -> None:
        n = nazwy()
        for c in sil.db.czlonkowie(wid):
            sid = c.get("sesja_tip") or c.get("sesja_id")
            if not sid:
                continue
            t = f"Jarvo · {tytul[:60]} · {n.get(c['agent'], c['agent'])}{' · nadzór' if c.get('rola') == 'nadzor' else ''}"
            try:
                await sil.brama.zmien_sesje(c["agent"], sid, title=t)
            except sil.m.brama.BladBramy as e:
                log(f"jarvo-hq: tytuł sesji {c['agent']}/{sid} bez zmiany ({e.kod})")

    @trasa("PATCH", "/rozmowy/{wid}")
    @obsluga
    async def zmien_rozmowe(wid: str, request: Request):
        sil = s()
        await watek_lub_404(sil, wid)
        body = await czytaj_cialo(request, ZmianaWatkuBody)

        async def _r():
            pola: dict[str, Any] = {}
            if body.tytul is not None:
                tytul = " ".join(body.tytul.split())
                if not tytul:
                    raise BladTrasy(422, "zle_dane", "Tytuł nie może być pusty.", "The title cannot be empty.")
                pola.update(tytul=tytul, tytul_zrodlo="wlasciciel")
            if body.przypiety is not None:
                pola["przypiety"] = int(body.przypiety)
            if body.archiwum is not None:
                if body.archiwum:
                    await porzadek_pracy(sil, wid, body.praca)
                pola["archiwum"] = int(body.archiwum)
            w = sil.db.zmien(wid, **pola)
            if "tytul" in pola:
                sil.rejestr.zadanie(zmien_tytul_sesji(sil, wid, pola["tytul"]))
            hub.nadaj("watek.zmiana", {"watek": przebiegi.watek_krotki(w)})
            return {"watek": watek_pelny(sil, w)}

        return await sil.wykonaj(_r())

    @trasa("DELETE", "/rozmowy/{wid}", status_code=204)
    @obsluga
    async def usun_rozmowe(wid: str, trwale: int = 0, praca: str = ""):
        sil = s()
        await watek_lub_404(sil, wid)
        if praca not in ("", "zatrzymaj", "zostaw"):
            raise BladTrasy(422, "zle_dane", "Nieznany wybór pracy.", "Unknown work choice.")

        async def _r():
            await porzadek_pracy(sil, wid, praca or None)
            sesje = sil.db.usun(wid, trwale=bool(trwale))
            if trwale:
                for x in sesje:
                    if x.get("przypieta"):
                        try:
                            await sil.brama.zmien_sesje(x["agent"], x["sesja_id"], pinned=False)
                            sil.db.ustaw_przypieta(x["agent"], x["sesja_id"], False)
                        except sil.m.brama.BladBramy:
                            pass
            hub.nadaj("watek.usuniety", {"id": wid, "trwale": bool(trwale)})

        await sil.wykonaj(_r())
        return Response(status_code=204)

    @trasa("POST", "/rozmowy/{wid}/przywroc")
    @obsluga
    async def przywroc_rozmowe(wid: str):
        sil = s()
        await watek_lub_404(sil, wid)

        async def _r():
            w = sil.db.przywroc(wid)
            hub.nadaj("watek.zmiana", {"watek": przebiegi.watek_krotki(w)})
            return {"watek": watek_pelny(sil, w)}

        return await sil.wykonaj(_r())

    @trasa("POST", "/rozmowy/{wid}/przeczytane", status_code=204)
    @obsluga
    async def przeczytane(wid: str, request: Request):
        sil = s()
        await watek_lub_404(sil, wid)
        body = await czytaj_cialo(request, PrzeczytaneBody)

        async def _r():
            sil.db.przeczytane(wid, min(float(body.do_at), zegar() + 60))
            hub.nadaj("watek.zmiana", {"watek": przebiegi.watek_krotki(sil.db.watek(wid))})

        await sil.wykonaj(_r())
        return Response(status_code=204)

    @trasa("GET", "/rozmowy/{wid}/os")
    @obsluga
    async def os_rozmowy(wid: str, request: Request, przed: str = "", po: str = "", limit: int = 80):
        tylko_ta_strona(request)
        sil = s()
        await watek_lub_404(sil, wid)
        try:
            return await asyncio.to_thread(
                m.scalanie.os_watku, sil.db, sil.czytnik, wid, przed=przed or None, po=po or None, limit=limit,
                budzenia=m.budzenia, etykieta=core.tool_label, utajnij=ochrona.utajnij, plik=plik)
        except ValueError:
            raise BladTrasy(422, "zly_kursor", "Zły kursor osi czasu.", "Bad timeline cursor.") from None

    @trasa("GET", "/rozmowy/{wid}/eksport")
    @obsluga
    async def eksport_rozmowy(wid: str, request: Request):
        """Cała rozmowa jako plik Markdown do pobrania (strony osi od najnowszej wstecz)."""
        tylko_ta_strona(request)
        sil = s()
        w = await watek_lub_404(sil, wid)

        def zbierz() -> str:
            strony, przed = [], None
            for _ in range(EKSPORT_STRON):
                o = m.scalanie.os_watku(sil.db, sil.czytnik, w["id"], przed=przed, limit=m.scalanie.LIMIT_MAKS,
                                        budzenia=m.budzenia, etykieta=core.tool_label, utajnij=ochrona.utajnij,
                                        plik=plik)
                strony.append(o["pozycje"])
                przed = o.get("przed")
                if not przed or o.get("pelny"):
                    break
            pozycje = [p for strona in reversed(strony) for p in strona]
            return eksport_md(w.get("tytul") or "", pozycje, nazwy(), teraz=zegar(), utajnij=ochrona.utajnij)

        tresc = await asyncio.to_thread(zbierz)
        nazwa = nazwa_pliku_eksportu(w.get("tytul") or "")
        return Response(tresc.encode("utf-8"), media_type="text/markdown; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="{nazwa}"',
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @trasa("GET", "/agenci")
    @obsluga
    async def lista_agentow(request: Request):
        """Agenci aplikacji (flota, z `JARVO_E2E=1` także testowi): nazwy, uchwyty i aliasy wzmianek, opisy."""
        tylko_ta_strona(request)
        return {"agenci": await asyncio.to_thread(agenci.lista)}

    @trasa("POST", "/rozmowy/{wid}/wiadomosci", status_code=202)
    @obsluga
    async def wiadomosc(wid: str, request: Request):
        sil = s()
        w = await watek_lub_404(sil, wid, kosz=False)
        rez = sprawdz_tempo(request)                # przed czytaniem treści (do 7,6 MB); miejsce zarezerwowane
        nowy = False
        try:
            body = await czytaj_cialo(request, WyslijBody, maks=CIALO_WYSYLKI_MAKS)
            jest = await asyncio.to_thread(powtorka, sil, wid, body.klucz)
            if jest is not None:                    # powtórzone żądanie: zapisana odpowiedź, bez walidacji i tempa
                return JSONResponse(jest, status_code=202)
            prz = await asyncio.to_thread(przygotuj_wysylke, body, w.get("koordynator") or "jarvo")
            wynik = await sil.wykonaj(wyslij_na_silniku(sil, wid, body, prz))
            nowy = bool(wynik.pop("_nowy", False))
            return JSONResponse(wynik, status_code=202)
        finally:
            if not nowy:
                oddaj_tempo(rez)

    # ------------------------------------------------------------------------------------------- przebiegi
    async def akcja(pid: str, fn, *, status: int = 200):
        sil = s()
        id_przebiegu(pid)

        async def _r():
            p = await fn(sil)
            return {"przebieg": sil.rejestr.widok(p)}

        wynik = await sil.wykonaj(_r())
        return JSONResponse(wynik, status_code=status) if status != 200 else wynik

    @trasa("GET", "/przebiegi/{pid}")
    @obsluga
    async def przebieg(pid: str, request: Request):
        tylko_ta_strona(request)

        async def _wez(sil):
            p = sil.db.przebieg(pid)
            if p is None:
                raise BladTrasy(404, "brak", "Nie ma takiej pracy.", "No such run.")
            return p
        return await akcja(pid, _wez)

    async def _stop(pid: str):
        return await akcja(pid, lambda sil: sil.rejestr.stop(pid), status=202)

    @trasa("POST", "/przebiegi/{pid}/stop", status_code=202)
    @obsluga
    async def stop(pid: str):
        return await _stop(pid)

    @trasa("POST", "/przebiegi/{pid}/zatrzymaj", status_code=202)
    @obsluga
    async def zatrzymaj(pid: str):
        return await _stop(pid)

    @trasa("POST", "/przebiegi/{pid}/anuluj")
    @obsluga
    async def anuluj(pid: str):
        return await akcja(pid, lambda sil: sil.rejestr.anuluj(pid))

    @trasa("POST", "/przebiegi/{pid}/wyslij")
    @obsluga
    async def wyslij_teraz(pid: str):
        return await akcja(pid, lambda sil: sil.rejestr.wyslij_teraz(pid))

    @trasa("POST", "/przebiegi/{pid}/wyslij-teraz")
    @obsluga
    async def wyslij_teraz_alias(pid: str):
        return await akcja(pid, lambda sil: sil.rejestr.wyslij_teraz(pid))

    @trasa("POST", "/przebiegi/{pid}/zgoda")
    @obsluga
    async def zgoda(pid: str, request: Request):
        body = await czytaj_cialo(request, ZgodaBody)
        return await akcja(pid, lambda sil: sil.rejestr.zgoda(pid, body.wybor, body.request_id))

    @trasa("POST", "/przebiegi/{pid}/dopisz")
    @obsluga
    async def dopisz(pid: str, request: Request):
        rez = sprawdz_tempo(request)
        nowy_wpis = []
        try:
            return await _dopisz_trasa(pid, request, nowy_wpis)
        finally:
            if not nowy_wpis:
                oddaj_tempo(rez)

    async def _dopisz_trasa(pid: str, request: Request, nowy_wpis: list) -> dict:
        body = await czytaj_cialo(request, DopiszBody)

        async def _dopisz(sil, p: dict) -> dict:
            db, rej = sil.db, sil.rejestr
            wid = p["watek_id"]
            if body.klucz:                                # powtórzone żądanie (po zerwanym połączeniu): bez steera
                jest = db.wpis_po_kluczu(wid, body.klucz)
                if jest is not None:
                    if (jest.get("dane") or {}).get("dopisane_do") != pid:
                        raise BladTrasy(409, "klucz_zajety", "Ten klucz należy już do innej wiadomości.",
                                        "This key already belongs to another message.")
                    return next((q for q in db.przebiegi_watku(wid) if q.get("wpis_id") == jest["id"]), None) or p
            q = await rej.dopisz(pid, body.tekst)
            koord = (db.watek(wid) or {}).get("koordynator") or "jarvo"
            wpis = dict(rodzaj="wlasciciel", tekst=body.tekst, tresc=body.tekst, adresaci=[p["agent"]],
                        tryb="jarvo" if p["agent"] == koord else "bezposrednio", dane={"dopisane_do": pid})
            w = db.dodaj_wpis(wid, **wpis, klucz=body.klucz)
            if w.get("powtorzony"):     # klucz zajęła w trakcie steera inna wiadomość: steer już poszedł, wpis bez klucza
                w = db.dodaj_wpis(wid, **wpis)
            hub.nadaj("watek.wpis", {"watek_id": wid, "wpis": w}, watek_id=wid)
            q = db.zmien_przebieg(q["id"], wpis_id=w["id"])
            nowy = db.aktywnosc(wid, at=w["utworzony_at"], podglad=f"Ty: {body.tekst}")
            db.przeczytane(wid, w["utworzony_at"])
            hub.nadaj("watek.zmiana", {"watek": przebiegi.watek_krotki(db.watek(wid) or nowy)})
            nowy_wpis.append(w["id"])
            return q

        def _biezacy(sil) -> dict:
            p = sil.db.przebieg(pid)
            if p is None:
                raise BladTrasy(404, "brak", "Nie ma takiej pracy.", "No such run.")
            return p

        async def _dopisz_albo_kolejka(sil) -> dict:
            p = _biezacy(sil)                             # na nowo: mogliśmy czekać na żądanie z tym samym kluczem
            if body.klucz and (p.get("payload") or {}).get("klucz_dopisz") == body.klucz:
                return p                                  # powtórka „Dopisz” wiadomości z kolejki: ten sam przebieg
            if p["stan"] == "kolejka":                    # wiadomość w kolejce: dopisz ją do trwającej pracy
                return await sil.rejestr.dopisz_kolejke(pid, klucz=body.klucz)
            return await _dopisz(sil, p)

        async def _r(sil):
            p = _biezacy(sil)
            sprawdz_watek(sil.db.watek(p["watek_id"]), kosz=False)
            klucz = ("dopisz", p["watek_id"], body.klucz) if body.klucz else None
            return await jednorazowo(klucz, lambda: _dopisz_albo_kolejka(sil))

        return await akcja(pid, _r)

    @trasa("POST", "/przebiegi/{pid}/ponow", status_code=202)
    @obsluga
    async def ponow(pid: str):
        return await akcja(pid, lambda sil: sil.rejestr.ponow(pid), status=202)

    # ------------------------------------------------------------------------------------------- strumień
    @trasa("GET", "/strumien")
    @obsluga
    async def strumien(request: Request, klient: str = "", watki: str = "", od: str = ""):
        tylko_ta_strona(request)
        if not ochrona.KLIENT_RE.fullmatch(klient or ""):
            raise BladTrasy(422, "zly_klient", "Brak identyfikatora karty przeglądarki.", "Missing browser client id.")
        ws = [w for w in (watki or "").split(",") if ochrona.WATEK_RE.fullmatch(w)][:200]
        kursor = request.headers.get("last-event-id") or od or None
        pol = hub.polacz(klient, ws, kursor)
        return StreamingResponse(pol.strumien(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @trasa("POST", "/strumien/{klient}/subskrypcje", status_code=204)
    @obsluga
    async def subskrypcje(klient: str, request: Request):
        if not ochrona.KLIENT_RE.fullmatch(klient or ""):
            raise BladTrasy(422, "zly_klient", "Brak identyfikatora karty przeglądarki.", "Missing browser client id.")
        body = await czytaj_cialo(request, SubskrypcjeBody)
        ws = [w for w in body.watki if ochrona.WATEK_RE.fullmatch(w)]
        sesje = [x for x in body.sesje if ochrona.PROFIL_RE.fullmatch(str(x.get("profil", "")))
                 and ochrona.SESJA_RE.fullmatch(str(x.get("id", "")))]
        hub.subskrybuj(klient, watki=ws, panele=body.panele, sesje=sesje)
        return Response(status_code=204)

    return sciezki
