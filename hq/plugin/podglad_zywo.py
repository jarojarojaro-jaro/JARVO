"""Podgląd na żywo telefonów floty i przeglądarki Jarva w panelu (docs/HQ.md „Podgląd na żywo”).

Jeden WebSocket `GET /api/plugins/jarvo-hq/podglad/ws?token=<token sesji panelu>` na kartę panelu; tylko podgląd,
bez sterowania. Uwierzytelnienie jak WebSockety dashboardu Hermesa (hermes_cli.web_server_chat: `_ws_auth_ok`, czyli
`?token=` z tokenem sesji wstrzykniętym w stronę, i `_ws_request_is_allowed`: Host, Origin, klient z pętli zwrotnej).
Panel w sieci Tailscale (siec.py) wpuszcza WebSocket tylko z ważną sesją i podaje go dalej jak lokalny, więc to
samo sprawdzenie działa w obu trybach. Bez Hermesa (import się nie uda) albo bez poświadczeń = zamknięcie 4401
przed przyjęciem (przeglądarka widzi odmowę uzgodnienia). Nowego sekretu nie ma.

Protokół. Klient → serwer (tekst JSON): {"typ": "patrz", "u": "<telefon>"|"komputer"|null} (null = telefon, na
którym agent pracuje teraz, inaczej pierwszy), {"typ": "ping", "t": <ms klienta>}. Serwer → klient:
  tekst  {"typ": "witaj", "czas", "telefony": [{"id", "rodzaj"}], "komputer": bool, "agent", "przydzialy"}
         {"typ": "pong", "t", "s"} (synchronizacja zegara: opóźnienie liczy klient z czasu nadania)
         {"typ": "stan", "u", "stan": "laczy"|"dziala"|"poza_siecia"|"niedostepny", "opis"}
         {"typ": "ekran", "u", "wlaczony", "zablokowany", "szer", "wys"} (PhoneUse ping co CO_ILE_EKRAN s, gdy ktoś
         patrzy; szer i wys = ekran w pikselach, do kręgu w miejscu stuknięcia)
         {"typ": "sesja", "u", "w", "h", "kodek"} (nowa sesja kodera: start albo obrót telefonu)
         {"typ": "klatka", "u", "w_css", "h_css", "tytul", "url"} (opis klatki Komputera przed jej obrazem)
         {"typ": "agent", "agent"} (zmiana telefonu, na którym agent pracuje: pliki PhoneUse <stan>/<nazwa>.busy)
  binarnie  RAMKA: typ u8 (1 konfiguracja H.264: SPS i PPS, 2 klatka kluczowa, 3 klatka, 4 JPEG Komputera),
         czas odbioru na serwerze f64 (ms od epoki), pts u64 (µs, JPEG: numer klatki), dane. Serwer niczego nie
         przekodowuje: H.264 w Annex B z kodera telefonu, JPEG z Page.startScreencast.

Telefon: scrcpy-server 5.0.1 (vendor/natywne.yaml `scrcpy-server`, przy pierwszym użyciu przez jarvo/przy_uzyciu.py)
przez adb z platform-tools Jarva: push do /data/local/tmp, `adb forward tcp:0 localabstract:scrcpy_<scid>` z losowym
scid, `app_process` z video=true audio=false control=false tunnel_forward=true video_codec=h264, max_size 1280,
max_fps 60, klatka kluczowa co 2 s (krótki GOP: nowy widz dostaje obraz od razu), power_on=false (podgląd nigdy nie
budzi ekranu). Strumień 5.0.1 (server/src: DesktopConnection, Streamer): bajt próby, nazwa urządzenia 64 B, kodek
u32, potem nagłówki 12 B: sesja (bit 63, flagi u32, szerokość, wysokość) albo pakiet (u64 pts z bitem 62 =
konfiguracja i 61 = klatka kluczowa, rozmiar u32) i dane. Pamięć strumienia: ostatnia sesja, konfiguracja i GOP od
ostatniej klatki kluczowej, więc nowy widz dostaje sesję, konfigurację i klatkę kluczową jako pierwsze.
Nazwy telefonów (first, second, third) i seriale adb daje PhoneUse (`<stan>/telefon.json` z `jarvo telefon on`:
katalog tools/ i Python serwera phone): krótki proces z tools/body.py (`Phone.load`, PHONEUSE_NO_RECONNECT=1),
bez czytania plików telefonów przez panel. Ekran wygaszony = PhoneUse ping `screen_on: false`.
Komputer: polecenie `klatka` kanału `ster` usługi Komputera (komputer/kanal.py, token właściciela) z `po` i
`czekaj` (long-poll po stronie serwera); klatka idzie, gdy przyjdzie, bez odpytywania z przeglądarki.

Strumień urządzenia jest jeden na proces i dzielą go wszyscy widzowie; gaśnie WYGASZENIE s po odejściu ostatniego
widza. Widz, który nie nadąża (kolejka ponad MAKS_KOLEJKI bajtów), traci zaległe klatki i czeka na najbliższą
klatkę kluczową (dostaje ją z konfiguracją). Testy: tests/test_podglad_zywo.py.
"""
from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import random
import re
import struct
import sys
import time
from pathlib import Path
from typing import Any, AsyncIterator, Callable

SCRCPY_WERSJA = "5.0.1"
NARZEDZIE_SERWERA = "scrcpy-server"
PLIK_SERWERA = "scrcpy-server.jar"
NA_TELEFONIE = f"/data/local/tmp/jarvo-scrcpy-server-{SCRCPY_WERSJA}.jar"
BRAK_SERWERA = "jarvo-brak-scrcpy-server"     # odpowiedź `adb shell`, gdy pliku serwera nie ma na telefonie
OPCJE_SCRCPY = ("log_level=warn", "video=true", "audio=false", "control=false", "tunnel_forward=true",
                "video_codec=h264", "max_size=1280", "max_fps=60", "video_bit_rate=4000000",
                "video_codec_options=i-frame-interval:int=2", "send_device_meta=true", "send_stream_meta=true",
                "send_frame_meta=true", "send_dummy_byte=true", "power_on=false", "cleanup=false")
WYGASZENIE = 10.0                # s: strumień gaśnie tyle po odejściu ostatniego widza
MAKS_GOP = 6 << 20               # B: GOP ponad to = czekamy na następną klatkę kluczową (nowy widz chwilę czeka)
MAKS_PAKIET = 16 << 20           # B: większy pakiet = zepsuty strumień
MAKS_KOLEJKI = 6 << 20           # B: widz z większą zaległością traci klatki do najbliższej kluczowej
CO_ILE_EKRAN = 5.0               # s: PhoneUse ping (ekran włączony?) strumienia, na który ktoś patrzy
CO_ILE_AGENT = 1.0               # s: pliki .busy PhoneUse (który telefon agent ma teraz)
OKNO_AGENTA = 20.0               # s: tyle od ostatniego działania agenta telefon uchodzi za „w pracy”
CZAS_MAPY = 60.0                 # s: pamięć nazw i seriali telefonów z PhoneUse
KOMPUTER = "komputer"
NAZWA_TELEFONU = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# typy ramek binarnych do przeglądarki
KONFIG, KLUCZ, DELTA, JPEG = 1, 2, 3, 4
_NAGLOWEK_RAMKI = struct.Struct(">Bdq")

# znaczniki nagłówka pakietu scrcpy 5.0.1 (server/.../device/Streamer.java)
FLAGA_SESJI = 1 << 63
FLAGA_KONFIG = 1 << 62
FLAGA_KLUCZ = 1 << 61
MASKA_PTS = FLAGA_KLUCZ - 1
KODEKI = {0x68323634: "h264", 0x68323635: "h265", 0x00617631: "av1"}


def _log_nic(_linia: str) -> None:
    return None


def ramka(typ: int, czas_ms: float, pts: int, dane: bytes) -> bytes:
    """Ramka binarna dla przeglądarki: typ, czas odbioru na serwerze (ms), pts (µs) i dane bez zmian."""
    return _NAGLOWEK_RAMKI.pack(typ, czas_ms, pts) + dane


def tekst(**pola: Any) -> str:
    return json.dumps(pola, ensure_ascii=False, separators=(",", ":"))


class BladProtokolu(ValueError):
    """Strumień scrcpy nie zgadza się z protokołem 5.0.1."""


class BladZrodla(RuntimeError):
    """Urządzenie nie odpowiada (telefon poza siecią, serwer na telefonie padł): ponowienie z przerwą."""


class Niedostepny(RuntimeError):
    """Podglądu tego urządzenia nie da się uruchomić (brak adb, PhoneUse, Komputera): opis dla właściciela."""


# ---------------------------------------------------------------------------------------------- protokół scrcpy

class ParserScrcpy:
    """Przyrostowy parser strumienia wideo scrcpy-server 5.0.1. `dodaj(bajty)` zwraca zdarzenia:
    ("urzadzenie", nazwa), ("kodek", nazwa), ("sesja", w, h), ("pakiet", konfiguracja, klucz, pts, dane)."""

    def __init__(self, *, bajt_proby: bool = True):
        self.bufor = bytearray()
        self.etap = "proba" if bajt_proby else "urzadzenie"

    def dodaj(self, dane: bytes) -> list[tuple]:
        self.bufor += dane
        out: list[tuple] = []
        b = self.bufor
        poz = 0
        while True:
            zostalo = len(b) - poz
            if self.etap == "proba":
                if zostalo < 1:
                    break
                poz += 1
                self.etap = "urzadzenie"
            elif self.etap == "urzadzenie":
                if zostalo < 64:
                    break
                nazwa = bytes(b[poz:poz + 64]).split(b"\0", 1)[0].decode("utf-8", "replace")
                out.append(("urzadzenie", nazwa))
                poz += 64
                self.etap = "kodek"
            elif self.etap == "kodek":
                if zostalo < 4:
                    break
                (kod,) = struct.unpack_from(">I", b, poz)
                poz += 4
                if kod in (0, 1):
                    raise BladProtokolu("telefon wyłączył obraz" if kod == 0 else "błąd konfiguracji na telefonie")
                if kod not in KODEKI:
                    raise BladProtokolu(f"nieznany kodek {kod:#x}")
                out.append(("kodek", KODEKI[kod]))
                self.etap = "naglowek"
            else:
                if zostalo < 12:
                    break
                (pierwsze,) = struct.unpack_from(">Q", b, poz)
                if pierwsze & FLAGA_SESJI:
                    _flagi, w, h = struct.unpack_from(">III", b, poz)
                    out.append(("sesja", w, h))
                    poz += 12
                    continue
                (rozmiar,) = struct.unpack_from(">I", b, poz + 8)
                if rozmiar > MAKS_PAKIET:
                    raise BladProtokolu(f"pakiet {rozmiar} B")
                if zostalo < 12 + rozmiar:
                    break
                dane_p = bytes(b[poz + 12:poz + 12 + rozmiar])
                out.append(("pakiet", bool(pierwsze & FLAGA_KONFIG), bool(pierwsze & FLAGA_KLUCZ),
                            0 if pierwsze & FLAGA_KONFIG else pierwsze & MASKA_PTS, dane_p))
                poz += 12 + rozmiar
        if poz:
            del b[:poz]
        return out


class Gop:
    """Pamięć strumienia dla nowego widza: sesja (tekst), konfiguracja i klatki od ostatniej kluczowej (ramki)."""

    def __init__(self, maks: int = MAKS_GOP):
        self.maks = maks
        self.sesja: str | None = None
        self.config: bytes | None = None
        self.klatki: list[bytes] = []
        self.rozmiar = 0

    def nowa_sesja(self, opis: str) -> None:
        self.sesja, self.config, self.klatki, self.rozmiar = opis, None, [], 0

    def dodaj(self, typ: int, r: bytes) -> None:
        if typ == KONFIG:
            self.config, self.klatki, self.rozmiar = r, [], 0
        elif typ == KLUCZ:
            self.klatki, self.rozmiar = [r], len(r)
        elif self.klatki:
            self.klatki.append(r)
            self.rozmiar += len(r)
            if self.rozmiar > self.maks:
                self.klatki, self.rozmiar = [], 0

    def na_start(self) -> list[str | bytes]:
        out: list[str | bytes] = [self.sesja] if self.sesja else []
        if self.config is not None:
            out.append(self.config)
            out.extend(self.klatki)
        return out

    def wyczysc(self) -> None:
        self.nowa_sesja("")
        self.sesja = None


# ---------------------------------------------------------------------------------------------- widzowie i strumień

class Widz:
    """Jeden oglądający (połączenie WebSocket): kolejka wiadomości do wysłania z limitem zaległości."""

    def __init__(self, maks: int = MAKS_KOLEJKI):
        self.maks = maks
        self.kolejka: asyncio.Queue = asyncio.Queue()
        self.bajty = 0
        self.czeka_na_klucz = False

    def daj(self, wiad: str | bytes) -> None:
        self.bajty += len(wiad)
        self.kolejka.put_nowait(wiad)

    def wideo(self, typ: int, r: bytes, config: bytes | None) -> None:
        """Ramka wideo z kontrolą zaległości: przepełniony widz czeka na klatkę kluczową (z konfiguracją przed nią)."""
        if self.czeka_na_klucz:
            if typ != KLUCZ:
                return
            self.czeka_na_klucz = False
            if config is not None:
                self.daj(config)
        elif typ != KONFIG and self.bajty + len(r) > self.maks:
            self.porzuc_zaleglosci()
            if typ != KLUCZ:
                self.czeka_na_klucz = True
                return
            if config is not None:
                self.daj(config)
        self.daj(r)

    def porzuc_zaleglosci(self) -> None:
        """Bez zaległych ramek binarnych (teksty stanu zostają)."""
        zostaja = []
        while not self.kolejka.empty():
            w = self.kolejka.get_nowait()
            if isinstance(w, str):
                zostaja.append(w)
        self.bajty = 0
        for w in zostaja:
            self.daj(w)

    async def wez(self) -> str | bytes:
        w = await self.kolejka.get()
        self.bajty -= len(w)
        return w


Zrodlo = Callable[[], AsyncIterator[tuple]]


class Strumien:
    """Jeden strumień urządzenia `uid` dzielony przez widzów. `zrodlo()` daje zdarzenia: ("stan", stan, opis),
    ("sesja", w, h), ("pakiet", konfiguracja, klucz, pts, dane), ("jpeg", dane, opis); koniec albo wyjątek =
    ponowienie z przerwą (Niedostepny: dłuższą). `czujnik(strumien)`: pętla obok źródła (ekran telefonu)."""

    def __init__(self, uid: str, zrodlo: Zrodlo, *, wygaszenie: float = WYGASZENIE,
                 czujnik: Callable[["Strumien"], Any] | None = None, log: Callable[[str], None] = _log_nic,
                 zegar: Callable[[], float] = time.time):
        self.uid, self.zrodlo, self.wygaszenie, self.czujnik, self.log, self.zegar = uid, zrodlo, wygaszenie, czujnik, log, zegar
        self.widzowie: set[Widz] = set()
        self.gop = Gop()
        self.jpeg: list[str | bytes] = []
        self.stan = tekst(typ="stan", u=uid, stan="laczy", opis="")
        self.ekran: str | None = None
        self._zadanie: asyncio.Task | None = None
        self._czujnik: asyncio.Task | None = None
        self._stop: asyncio.TimerHandle | None = None

    @property
    def dziala(self) -> bool:
        return self._zadanie is not None and not self._zadanie.done()

    def dolacz(self, widz: Widz) -> None:
        if self._stop is not None:
            self._stop.cancel()
            self._stop = None
        self.widzowie.add(widz)
        widz.daj(self.stan)
        if self.ekran:
            widz.daj(self.ekran)
        for w in [*self.gop.na_start(), *self.jpeg]:
            widz.daj(w)
        if not self.dziala:
            self._zadanie = asyncio.get_running_loop().create_task(self._petla())
            if self.czujnik is not None:
                self._czujnik = asyncio.get_running_loop().create_task(self.czujnik(self))

    def odlacz(self, widz: Widz) -> None:
        self.widzowie.discard(widz)
        if not self.widzowie and self.dziala and self._stop is None:
            self._stop = asyncio.get_running_loop().call_later(self.wygaszenie, self.zatrzymaj)

    def zatrzymaj(self) -> None:
        self._stop = None
        if self.widzowie:
            return
        for z in (self._zadanie, self._czujnik):
            if z is not None:
                z.cancel()
        self._zadanie = self._czujnik = None
        self.gop.wyczysc()
        self.jpeg = []
        self.ekran = None
        self.stan = tekst(typ="stan", u=self.uid, stan="laczy", opis="")
        self.log(f"podgląd: {self.uid} zatrzymany (nikt nie patrzy)")

    def rozeslij(self, wiad: str | bytes) -> None:
        for w in list(self.widzowie):
            w.daj(wiad)

    def ustaw_stan(self, stan: str, opis: str = "") -> None:
        nowy = tekst(typ="stan", u=self.uid, stan=stan, opis=opis)
        if nowy != self.stan:
            self.stan = nowy
            self.rozeslij(nowy)

    def ustaw_ekran(self, wlaczony: bool | None, zablokowany: bool | None, szer: int | None = None,
                    wys: int | None = None) -> None:
        nowy = tekst(typ="ekran", u=self.uid, wlaczony=wlaczony, zablokowany=zablokowany, szer=szer, wys=wys)
        if nowy != self.ekran:
            self.ekran = nowy
            self.rozeslij(nowy)

    def zdarzenie(self, ev: tuple) -> None:
        rodzaj = ev[0]
        if rodzaj == "stan":
            self.ustaw_stan(ev[1], ev[2] if len(ev) > 2 else "")
        elif rodzaj == "sesja":
            opis = tekst(typ="sesja", u=self.uid, w=ev[1], h=ev[2], kodek="h264")
            self.gop.nowa_sesja(opis)
            self.rozeslij(opis)
        elif rodzaj == "pakiet":
            _, konfig, klucz, pts, dane = ev
            typ = KONFIG if konfig else KLUCZ if klucz else DELTA
            r = ramka(typ, self.zegar() * 1000.0, pts, dane)
            self.gop.dodaj(typ, r)
            for w in list(self.widzowie):
                w.wideo(typ, r, self.gop.config)
            if typ != KONFIG:
                self.ustaw_stan("dziala")
        elif rodzaj == "jpeg":
            _, dane, opis = ev
            r = ramka(JPEG, self.zegar() * 1000.0, int(opis.get("nr") or 0), dane)
            o = tekst(typ="klatka", u=self.uid, **{k: opis.get(k) for k in ("w_css", "h_css", "tytul", "url")})
            self.jpeg = [o, r]
            for w in list(self.widzowie):
                if w.bajty > w.maks:
                    w.porzuc_zaleglosci()
                w.daj(o)
                w.daj(r)
            self.ustaw_stan("dziala")

    async def _petla(self) -> None:
        proba = 0
        while True:
            try:
                async for ev in self.zrodlo():
                    self.zdarzenie(ev)
                    if ev[0] in ("pakiet", "jpeg"):
                        proba = 0
                raise BladZrodla("strumień się skończył")
            except asyncio.CancelledError:
                raise
            except Niedostepny as e:
                self.ustaw_stan("niedostepny", str(e))
                await asyncio.sleep(30.0)
            except Exception as e:  # noqa: BLE001 - każdy błąd urządzenia: stan dla widzów i ponowienie
                proba += 1
                self.log(f"podgląd: {self.uid} przerwany ({type(e).__name__}: {str(e)[:160]}), próba {proba}")
                self.gop.wyczysc()
                self.ustaw_stan("poza_siecia", str(e)[:200])
                await asyncio.sleep(min(15.0, 0.5 * 2 ** min(proba, 5)))


# ---------------------------------------------------------------------------------------------- telefony (PhoneUse)

# krótki proces Pythonem PhoneUse: nazwy, rodzaj i serial adb każdego telefonu, przy `ping` także stan ekranu
KOD_TELEFONOW = r'''
import glob, json, os, sys
sys.path.insert(0, sys.argv[1])
os.environ["PHONEUSE_NO_RECONNECT"] = "1"
import body
ping = sys.argv[2]
pliki = glob.glob(os.path.expanduser("~/.phoneuse/phones/*.env"))
nazwy = ["first"] + sorted({os.path.basename(f)[:-4] for f in pliki} - {"first"})
out = {}
for n in nazwy:
    w = {}
    p = None
    try:
        p = body.Phone.load(n)
        w = {"rodzaj": p.kind, "serial": p.adb_serial}
        if n == ping and p.kind == "android":
            s, raw = p.send("/ping", timeout=4)
            d = json.loads(raw)
            scr = (d.get("caps") or {}).get("screen") or {}
            w.update(ekran=d.get("screen_on"), zablokowany=d.get("locked"), szer=scr.get("w"), wys=scr.get("h"))
    except Exception as e:
        w["blad"] = type(e).__name__
    finally:
        if p is not None:
            try:
                p.drop()
            except Exception:
                pass
    out[n] = w
print(json.dumps(out))
'''


class Telefony:
    """Telefony z PhoneUse: `tools` = katalog tools/ PhoneUse, `python` = jego Python, `dom` = katalog domowy
    właściciela (PhoneUse czyta `~/.phoneuse/`), `stan_phoneuse` = katalog plików .busy."""

    def __init__(self, *, tools: Path, python: str, dom: str | None, stan_phoneuse: Path, przydzialy: dict | None = None,
                 log: Callable[[str], None] = _log_nic):
        self.tools, self.python, self.dom, self.stan_phoneuse = Path(tools), python, dom, Path(stan_phoneuse)
        self.przydzialy = dict(przydzialy or {})
        self.log = log
        self._mapa: tuple[float, dict] | None = None
        self._blokada = asyncio.Lock()

    @classmethod
    def z_konfiguracji(cls, stan: Path, env: dict, log: Callable[[str], None] = _log_nic) -> "Telefony | None":
        """Z `<stan>/telefon.json` (`jarvo telefon on`); None, gdy telefon przez PhoneUse jest wyłączony."""
        try:
            t = json.loads((Path(stan) / "telefon.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(t, dict) or not t.get("wlaczony") or not t.get("serwer"):
            return None
        dom = str(t.get("dom") or "") or None
        stan_pu = env.get("PHONEUSE_STATE_DIR") or str(Path(dom or Path.home()) / ".phoneuse" / "state")
        przydzialy = {p: n for p, n in (t.get("profile") or {}).items()
                      if isinstance(p, str) and isinstance(n, str) and NAZWA_TELEFONU.match(n)}
        return cls(tools=Path(t["serwer"]).parent, python=str(t.get("python") or sys.executable), dom=dom,
                   stan_phoneuse=Path(stan_pu), przydzialy=przydzialy, log=log)

    async def _zapytaj(self, ping: str) -> dict:
        env = {**os.environ, "PHONEUSE_NO_RECONNECT": "1"}
        if self.dom:
            env["USERPROFILE" if os.name == "nt" else "HOME"] = self.dom
        proc = await asyncio.create_subprocess_exec(self.python, "-c", KOD_TELEFONOW, str(self.tools), ping or "-",
                                                    stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE, env=env)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), 20.0)
        except asyncio.TimeoutError:
            proc.kill()
            raise BladZrodla("PhoneUse nie odpowiedział w 20 s") from None
        if proc.returncode != 0:
            raise Niedostepny("PhoneUse nie podał telefonów: " + err.decode("utf-8", "replace").strip()[-200:])
        try:
            d = json.loads(out.decode("utf-8").strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise Niedostepny("PhoneUse odpowiedział nie po JSON-owemu") from None
        return {n: w for n, w in d.items() if NAZWA_TELEFONU.match(str(n)) and isinstance(w, dict)}

    async def mapa(self) -> dict:
        """{nazwa: {"rodzaj", "serial"}} z pamięcią CZAS_MAPY s."""
        async with self._blokada:
            teraz = time.monotonic()
            if self._mapa is None or teraz - self._mapa[0] > CZAS_MAPY:
                self._mapa = (teraz, await self._zapytaj(""))
            return self._mapa[1]

    async def ekran(self, nazwa: str) -> dict:
        """PhoneUse ping jednego telefonu: {"ekran": bool|None, "zablokowany": bool|None} (przy okazji świeża mapa)."""
        d = await self._zapytaj(nazwa)
        self._mapa = (time.monotonic(), d)
        return d.get(nazwa) or {}

    def zajety(self, teraz: float | None = None) -> str | None:
        """Telefon, na którym agent działał najpóźniej (mtime `<stan PhoneUse>/<nazwa>.busy` w OKNO_AGENTA s)."""
        teraz = time.time() if teraz is None else teraz
        najlepszy, czas = None, 0.0
        try:
            pliki = list(self.stan_phoneuse.glob("*.busy"))
        except OSError:
            return None
        for p in pliki:
            try:
                t = p.stat().st_mtime
            except OSError:
                continue
            if teraz - t <= OKNO_AGENTA and t > czas and NAZWA_TELEFONU.match(p.stem):
                najlepszy, czas = p.stem, t
        return najlepszy


# ---------------------------------------------------------------------------------------------- źródła

async def _uruchom(*argv: str, czas: float = 30.0) -> str:
    proc = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), czas)
    except asyncio.TimeoutError:
        proc.kill()
        raise BladZrodla(f"{Path(argv[0]).name} {argv[3] if len(argv) > 3 else ''}: brak odpowiedzi w {czas:g} s") from None
    if proc.returncode != 0:
        raise BladZrodla((err or out).decode("utf-8", "replace").strip()[-200:] or f"kod {proc.returncode}")
    return out.decode("utf-8", "replace")


async def zrodlo_scrcpy(adb: str, serial: str, serwer: Path, *, opcje: tuple[str, ...] = OPCJE_SCRCPY,
                        log: Callable[[str], None] = _log_nic) -> AsyncIterator[tuple]:
    """Obraz telefonu `serial` ze scrcpy-server (docstring modułu); zdarzenia jak ParserScrcpy."""
    yield ("stan", "laczy", "")
    scid = random.randrange(1, 1 << 31)
    port = int((await _uruchom(adb, "-s", serial, "forward", "tcp:0", f"localabstract:scrcpy_{scid:08x}")).strip())
    # plik serwera na telefonie (nazwa z wersją) zostaje między sesjami: jedno `adb shell` sprawdza rozmiar i od razu
    # uruchamia serwer; push (ok. 0,9 s przez Tailscale) tylko, gdy pliku nie ma albo ma inny rozmiar
    rozmiar = Path(serwer).stat().st_size
    polecenie = (f'if [ "$(stat -c %s {NA_TELEFONIE} 2>/dev/null)" = "{rozmiar}" ]; then CLASSPATH={NA_TELEFONIE} '
                 f"exec app_process / com.genymobile.scrcpy.Server {SCRCPY_WERSJA} scid={scid:08x} {' '.join(opcje)}; "
                 f"else echo {BRAK_SERWERA}; fi")
    ogon: list[str] = []
    proc = bledy = pisarz = None

    async def czytaj_wyjscie(p) -> None:
        while p.stdout is not None:
            linia = await p.stdout.readline()
            if not linia:
                return
            ogon.append(linia.decode("utf-8", "replace").strip())
            del ogon[:-10]

    try:
        czytnik = None
        for proba in range(2):
            proc = await asyncio.create_subprocess_exec(adb, "-s", serial, "shell", polecenie,
                                                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT)
            bledy = asyncio.get_running_loop().create_task(czytaj_wyjscie(proc))
            koniec = time.monotonic() + 10.0
            while czytnik is None:                 # serwer wstaje ok. 1 s (JVM): do tego czasu adb zamyka połączenie
                if proc.returncode is not None or BRAK_SERWERA in ogon or time.monotonic() > koniec:
                    break
                try:
                    c, pisarz = await asyncio.open_connection("127.0.0.1", port)
                    await asyncio.wait_for(c.readexactly(1), 3.0)
                    czytnik = c
                except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError):
                    if pisarz is not None:
                        pisarz.close()
                        pisarz = None
                    await asyncio.sleep(0.05)
            if czytnik is not None:
                break
            if proba == 0 and BRAK_SERWERA in ogon:
                await proc.wait()
                ogon.clear()
                await _uruchom(adb, "-s", serial, "push", str(serwer), NA_TELEFONIE, czas=60.0)
                continue
            raise BladZrodla("scrcpy-server nie wstał: " + (" ".join(ogon)[-200:] or "brak odpowiedzi"))
        parser = ParserScrcpy(bajt_proby=False)
        while True:
            dane = await czytnik.read(1 << 18)
            if not dane:
                raise BladZrodla("telefon zamknął obraz: " + (" ".join(ogon)[-200:] or "koniec strumienia"))
            for ev in parser.dodaj(dane):
                if ev[0] in ("sesja", "pakiet"):
                    yield ev
    finally:
        if pisarz is not None:
            pisarz.close()
        if proc is not None and proc.returncode is None:
            proc.kill()
        if bledy is not None:
            bledy.cancel()
        try:
            await _uruchom(adb, "-s", serial, "forward", "--remove", f"tcp:{port}", czas=5.0)
        except (BladZrodla, OSError):
            pass


async def zrodlo_komputera(zapytaj: Callable[[dict], dict], *, maks: int = 1280) -> AsyncIterator[tuple]:
    """Klatki Komputera (kanał `ster`, polecenie `klatka` z `po` i `czekaj`): ("jpeg", dane, opis) przy każdej
    nowej klatce. `zapytaj` jest blokujące (wołane w wątku)."""
    yield ("stan", "laczy", "")
    nr = None
    while True:
        odp = await asyncio.to_thread(zapytaj, {"polecenie": "klatka", "po": nr, "czekaj": 5, "maks": maks})
        if not odp.get("ok"):
            raise BladZrodla(str(odp.get("blad") or "Komputer nie dał klatki"))
        k = odp.get("klatka") or {}
        if k.get("bez_zmian"):
            continue
        if k.get("dane"):
            yield ("jpeg", base64.b64decode(k["dane"]), {"nr": k.get("nr"), "w_css": k.get("szer_css"),
                                                        "h_css": k.get("wys_css"), "tytul": k.get("tytul"),
                                                        "url": k.get("url")})
        nr = k.get("nr") if isinstance(k.get("nr"), int) else nr
        if not k.get("dane"):
            await asyncio.sleep(0.5)                 # okno JavaScript na stronie: bez obrazu, pytamy spokojniej


# ---------------------------------------------------------------------------------------------- całość

def _modul_z_pliku(nazwa: str, plik: Path):
    mod = sys.modules.get(nazwa)
    if mod is None:
        spec = importlib.util.spec_from_file_location(nazwa, plik)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules[nazwa] = mod
    return mod


class Podglad:
    """Strumienie urządzeń procesu panelu. `telefony`: Telefony albo None (PhoneUse wyłączony); `komputer`:
    blokujące zapytanie kanału `ster` albo None; `narzedzia()` → (adb, ścieżka scrcpy-server.jar) albo Niedostepny;
    `zrodlo_telefonu(serial)` i `zrodlo_komputera()` podmieniają testy."""

    def __init__(self, *, telefony: Telefony | None = None, komputer: Callable[[dict], dict] | None = None,
                 narzedzia: Callable[[], tuple[str, Path]] | None = None, wygaszenie: float = WYGASZENIE,
                 log: Callable[[str], None] = _log_nic, zrodlo_telefonu: Callable[[str], AsyncIterator] | None = None,
                 zrodlo_komp: Zrodlo | None = None, czujnik_ekranu: bool = True):
        self.telefony, self.komputer, self.narzedzia, self.wygaszenie, self.log = telefony, komputer, narzedzia, wygaszenie, log
        self._zrodlo_telefonu, self._zrodlo_komp, self.czujnik_ekranu = zrodlo_telefonu, zrodlo_komp, czujnik_ekranu
        self.strumienie: dict[str, Strumien] = {}
        self.polaczenia: set[Widz] = set()
        self.agent: str | None = None
        self._agent_zadanie: asyncio.Task | None = None
        self._narzedzia: tuple[str, Path] | None = None

    # -- z otoczenia procesu panelu
    @classmethod
    def z_otoczenia(cls, env: dict | None = None, log: Callable[[str], None] = _log_nic) -> "Podglad":
        """Instalacja natywna: korzeń z JARVO_ROOT, kod aktywnej wersji z JARVO_REPO (jarvo/przy_uzyciu.py i
        komputer/kanal.py). Bez nich (kontener, testy) podgląd odpowiada „niedostępny”."""
        env = dict(os.environ if env is None else env)
        root, app = env.get("JARVO_ROOT"), env.get("JARVO_REPO")
        if not root or not app or not (Path(app) / "jarvo" / "przy_uzyciu.py").is_file():
            return cls(log=log)
        root_p, app_p = Path(root), Path(app)
        if str(app_p) not in sys.path:
            sys.path.append(str(app_p))           # na końcu: moduły Hermesa wygrywają z katalogami repo Jarva

        def narzedzia() -> tuple[str, Path]:
            from jarvo import przy_uzyciu
            u = przy_uzyciu.uklad(env)
            pt = przy_uzyciu.gotowe_narzedzie(u, "platform-tools", app=app_p)
            if pt is None:
                raise Niedostepny("Brak adb Jarva. Zainstaluje go polecenie jarvo android (z licencją Google).")
            adb = Path(pt["katalog"]) / ("adb.exe" if os.name == "nt" else "adb")
            try:
                srv = przy_uzyciu.narzedzie(u, NARZEDZIE_SERWERA, app=app_p, log=log, pasek=False)
            except przy_uzyciu.BladPrzyUzyciu as e:
                raise Niedostepny(f"Nie pobrałem scrcpy-server: {e}") from None
            return str(adb), Path(srv["katalog"]) / PLIK_SERWERA

        komputer = None
        kanal_py = app_p / "komputer" / "kanal.py"
        if kanal_py.is_file():
            kanal = _modul_z_pliku("jarvo_hq_kanal_komputera", kanal_py)

            def komputer(polecenie: dict) -> dict:
                if kanal.pid_uslugi(root_p) is None:
                    raise Niedostepny("Komputer Jarva jest wyłączony (jarvo komputer on).")
                try:
                    token = (kanal.katalog_stanu(root_p) / "wlasciciel.klucz").read_text(encoding="utf-8").strip()
                except OSError:
                    raise Niedostepny("Brak tokenu właściciela Komputera.") from None
                return kanal.zapytaj(kanal.adres(root_p, "ster"), {**polecenie, "token": token}, 10.0,
                                     kanal.pid_uslugi(root_p), maks=32 << 20)

        return cls(telefony=Telefony.z_konfiguracji(root_p / "stan", env, log), komputer=komputer, narzedzia=narzedzia,
                   log=log)

    # -- urządzenia
    async def urzadzenia(self) -> dict:
        telefony: list[dict] = []
        if self.telefony is not None:
            try:
                mapa = await self.telefony.mapa()
            except (BladZrodla, Niedostepny, OSError) as e:
                self.log(f"podgląd: lista telefonów niedostępna ({e})")
                mapa = {}
            telefony = [{"id": n, "rodzaj": w.get("rodzaj") or "android"} for n, w in mapa.items()]
        return {"telefony": telefony, "komputer": self.komputer is not None or self._zrodlo_komp is not None,
                "agent": self.agent, "przydzialy": self.telefony.przydzialy if self.telefony else {}}

    def _zrodlo(self, uid: str) -> Zrodlo:
        if uid == KOMPUTER:
            if self._zrodlo_komp is not None:
                return self._zrodlo_komp
            komputer = self.komputer

            def zk() -> AsyncIterator[tuple]:
                if komputer is None:
                    raise Niedostepny("Komputer Jarva nie działa w tej instalacji.")
                return zrodlo_komputera(komputer)
            return zk

        async def zt() -> AsyncIterator[tuple]:
            yield ("stan", "laczy", "")
            if self._zrodlo_telefonu is not None:
                async for ev in self._zrodlo_telefonu(uid):
                    yield ev
                return
            if self.telefony is None:
                raise Niedostepny("Telefony przez PhoneUse są wyłączone (jarvo telefon on).")
            if self.narzedzia is None:
                raise Niedostepny("Podgląd telefonu działa w instalacji natywnej Jarva.")
            w = (await self.telefony.mapa()).get(uid)
            if not w or not w.get("serial"):
                raise Niedostepny(f"Telefon {uid} nie ma połączenia adb w PhoneUse.")
            if self._narzedzia is None:
                self._narzedzia = await asyncio.to_thread(self.narzedzia)
            adb, srv = self._narzedzia
            async for ev in zrodlo_scrcpy(adb, w["serial"], srv, log=self.log):
                yield ev
        return zt

    async def _czujnik_ekranu(self, s: Strumien) -> None:
        if self.telefony is None:
            return
        while True:
            try:
                e = await self.telefony.ekran(s.uid)
                if "ekran" in e:
                    s.ustaw_ekran(e.get("ekran"), e.get("zablokowany"), e.get("szer"), e.get("wys"))
            except (BladZrodla, Niedostepny, OSError) as exc:
                self.log(f"podgląd: ekran {s.uid} nieznany ({exc})")
            await asyncio.sleep(CO_ILE_EKRAN)

    def strumien(self, uid: str) -> Strumien:
        s = self.strumienie.get(uid)
        if s is None:
            czujnik = self._czujnik_ekranu if uid != KOMPUTER and self.czujnik_ekranu and self.telefony else None
            s = self.strumienie[uid] = Strumien(uid, self._zrodlo(uid), wygaszenie=self.wygaszenie, czujnik=czujnik,
                                                log=self.log)
        return s

    # -- agent na telefonie (pliki .busy)
    async def _sledz_agenta(self) -> None:
        while self.polaczenia:
            agent = self.telefony.zajety() if self.telefony else None
            if agent != self.agent:
                self.agent = agent
                for w in list(self.polaczenia):
                    w.daj(tekst(typ="agent", agent=agent))
            await asyncio.sleep(CO_ILE_AGENT)
        self._agent_zadanie = None

    # -- połączenie
    async def obsluz(self, ws, autoryzuj: Callable[[Any], bool]) -> None:
        """Jedno połączenie WebSocket (Starlette): odmowa 4401 przed przyjęciem bez poświadczeń panelu."""
        try:
            dobre = bool(autoryzuj(ws))
        except Exception:  # noqa: BLE001 - błąd sprawdzania = odmowa
            dobre = False
        if not dobre:
            await ws.close(code=4401)
            return
        await ws.accept()
        widz = Widz()
        self.polaczenia.add(widz)
        if self.telefony is not None and self._agent_zadanie is None:
            self.agent = self.telefony.zajety()
            self._agent_zadanie = asyncio.get_running_loop().create_task(self._sledz_agenta())
        biezacy: Strumien | None = None

        async def nadawaj() -> None:
            try:
                while True:
                    w = await widz.wez()
                    if isinstance(w, bytes):
                        await ws.send_bytes(w)
                    else:
                        await ws.send_text(w)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - przeglądarka zamknęła połączenie: odbiór skończy pętlę
                return

        nadajnik = asyncio.get_running_loop().create_task(nadawaj())
        try:
            widz.daj(tekst(typ="witaj", czas=time.time() * 1000.0, **await self.urzadzenia()))
            while True:
                wiad = await ws.receive()
                if wiad.get("type") == "websocket.disconnect":
                    break
                try:
                    d = json.loads(wiad.get("text") or "{}")
                except ValueError:
                    continue
                if not isinstance(d, dict):
                    continue
                if d.get("typ") == "ping":
                    widz.daj(tekst(typ="pong", t=d.get("t"), s=time.time() * 1000.0))
                elif d.get("typ") == "patrz":
                    u = d.get("u")
                    if u is None:
                        u = self.agent or next(iter((await self.urzadzenia())["telefony"]), {}).get("id")
                    if not isinstance(u, str) or not (u == KOMPUTER or NAZWA_TELEFONU.match(u)):
                        continue
                    if biezacy is not None:
                        biezacy.odlacz(widz)
                    widz.porzuc_zaleglosci()
                    widz.czeka_na_klucz = False
                    biezacy = self.strumien(u)
                    biezacy.dolacz(widz)
        except Exception as e:  # noqa: BLE001 - rozłączenie w trakcie wysyłki albo odbioru
            if type(e).__name__ not in ("WebSocketDisconnect", "ClientDisconnected"):
                self.log(f"podgląd: połączenie przerwane ({type(e).__name__})")
        finally:
            nadajnik.cancel()
            if biezacy is not None:
                biezacy.odlacz(widz)
            self.polaczenia.discard(widz)


def autoryzacja_hermesa(ws) -> bool:
    """Te same zasady co WebSockety dashboardu Hermesa (docstring modułu); bez Hermesa = odmowa."""
    try:
        from hermes_cli.web_server_chat import _ws_auth_ok, _ws_request_is_allowed
    except Exception:  # noqa: BLE001 - inna wersja Hermesa albo brak: zamknięte, nie otwarte
        return False
    return bool(_ws_auth_ok(ws) and _ws_request_is_allowed(ws))


def dolacz(router, *, podglad: Podglad, autoryzuj: Callable[[Any], bool] = autoryzacja_hermesa) -> list[str]:
    """WebSocket `/podglad/ws` na routerze wtyczki (pod /api/plugins/jarvo-hq/)."""
    from fastapi import WebSocket

    async def podglad_ws(ws):
        await podglad.obsluz(ws, autoryzuj)

    podglad_ws.__annotations__ = {"ws": WebSocket}   # typ wprost: adnotacje modułu są napisami (__future__)
    router.websocket("/podglad/ws")(podglad_ws)

    return ["/podglad/ws"]
