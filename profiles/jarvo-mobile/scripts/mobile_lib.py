"""Wspólne narzędzia Twórcy aplikacji: grzeczne HTTP (uczciwy User-Agent, robots.txt, pauza na host, pamięć
odpowiedzi), daty, wynik kontroli (✓ ✗ ⚠ ? ℹ —) i zapis raportów.

Tylko biblioteka standardowa. Odmowa źródła (403/429, ochrona antybotowa, zakaz w robots.txt) to blokada: skrypt
zgłasza ją i nie próbuje innej drogi (kontrakt zlecenia, pkt 16).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from pathlib import Path

UA = "Mozilla/5.0 (compatible; jarvo-mobile/1.0; +https://jarvo.pl)"
PAUZA_S = float(os.environ.get("MOBILE_PAUZA", "0.3"))         # minimum między zapytaniami do jednego hosta
PAUZY_HOSTOW = {"itunes.apple.com": 4.0, "play.google.com": 1.5, "apps.apple.com": 1.0}   # iTunes API: ~20 zapytań/min
LIMITY_ZWALNIAJ = {"itunes.apple.com"}                         # 403 tu znaczy „za szybko” (~20 zapytań/min), nie zakaz
OZNAKI_BLOKADY = ("_Incapsula_Resource", "cf-chl", "Dostęp zablokowany", "Access Blocked", "Request unsuccessful",
                  "/sorry/index", "unusual traffic")
CACHE = Path(os.environ.get("MOBILE_CACHE", str(Path.home() / ".cache" / "jarvo-mobile")))
# jedna wersja EAS CLI dla aplikacja.py, wydanie.py i reszty; ≥ 14 dni od wydania (kwarantanna npm)
EAS_CLI = os.environ.get("JARVO_EAS_CLI", "eas-cli@24.7.0")
LICZNIK = {"zapytania": 0, "z_pamieci": 0, "bledy": 0}
DZIS = dt.date.fromisoformat(os.environ["MOBILE_DZIS"]) if os.environ.get("MOBILE_DZIS") else dt.date.today()


def czytaj_json(p: Path) -> dict:
    """Plik JSON albo {} (brak pliku, zły JSON)."""
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Blokada(Exception):
    """Źródło odmówiło (403/429, ochrona antybotowa, robots.txt): koniec, nie zagadka."""


@dataclass
class Odpowiedz:
    kod: int
    tresc: str
    url: str                       # adres końcowy (po przekierowaniach)
    typ: str = ""                  # Content-Type
    przekierowania: list[str] = field(default_factory=list)


_lock = threading.Lock()
_ostatnie: dict[str, float] = {}
_roboty: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def _czekaj(host: str) -> None:
    """Pauza między zapytaniami do hosta; dla hostów z limitem (PAUZY_HOSTOW) także między procesami (znacznik w CACHE)."""
    pauza = PAUZY_HOSTOW.get(host, PAUZA_S)
    znacznik = CACHE / "ostatnie" / host if host in PAUZY_HOSTOW else None
    with _lock:
        teraz = time.time()
        poprzednie = _ostatnie.get(host, 0.0)
        if znacznik is not None and znacznik.is_file():
            poprzednie = max(poprzednie, znacznik.stat().st_mtime)
        start = max(teraz, poprzednie + pauza)
        _ostatnie[host] = start
        if znacznik is not None:
            znacznik.parent.mkdir(parents=True, exist_ok=True)
            znacznik.touch()
            os.utime(znacznik, (start, start))
    if start > teraz:
        time.sleep(start - teraz)


class _BezPrzekierowan(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):  # noqa: ANN002, ANN003
        return None


def _jeden(url: str, timeout: int, max_mb: int, naglowki: dict | None) -> tuple[int, bytes, dict, str | None]:
    """Jedno zapytanie bez podążania za przekierowaniem: (kod, treść, nagłówki, Location)."""
    _czekaj(urllib.parse.urlsplit(url).netloc)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.5",
                                               "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.5", **(naglowki or {})})
    opener = urllib.request.build_opener(_BezPrzekierowan)
    LICZNIK["zapytania"] += 1
    try:
        with opener.open(req, timeout=timeout) as r:  # noqa: S310 (adresy z kodu albo od agenta)
            surowe = r.read(max_mb * 1_000_000 + 1)
            return r.status, surowe, dict(r.headers), None
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") if e.code in (301, 302, 303, 307, 308) else None
        return e.code, e.read(200_000), dict(e.headers or {}), loc
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        LICZNIK["bledy"] += 1
        raise ConnectionError(f"{url}: {getattr(e, 'reason', e)}") from e


def _klucz(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:32]
    return CACHE / "http" / h[:2] / f"{h}.json"


def pobierz(url: str, pamiec_h: float = 6.0, timeout: int = 25, max_mb: int = 4, naglowki: dict | None = None,
            max_przekierowan: int = 5, roboty: bool = False) -> Odpowiedz:
    """GET z ręcznym śledzeniem przekierowań (raport je pokazuje: plik AASA nie może przekierowywać).

    `roboty=True` sprawdza robots.txt hosta przed zapytaniem (strony firm, sklepy); pliki protokołów
    (`/.well-known/…`, API) pobieramy bez tego, bo są przeznaczone dla maszyn.
    """
    plik = _klucz(url)
    if pamiec_h and plik.is_file() and time.time() - plik.stat().st_mtime < pamiec_h * 3600:
        LICZNIK["z_pamieci"] += 1
        return Odpowiedz(**json.loads(plik.read_text(encoding="utf-8")))
    if roboty and not wolno(url):
        raise Blokada(f"{urllib.parse.urlsplit(url).netloc}: robots.txt zabrania {urllib.parse.urlsplit(url).path}")
    teraz, droga = url, []
    for _ in range(max_przekierowan + 1):
        kod, surowe, h, loc = _jeden(teraz, timeout, max_mb, naglowki)
        host = urllib.parse.urlsplit(teraz).netloc
        if kod == 429 or (kod == 403 and host in LIMITY_ZWALNIAJ):     # limit zapytań: zwolnić raz, nie obchodzić
            poczekaj = {k.lower(): v for k, v in h.items()}.get("retry-after", "")
            time.sleep(min(int(poczekaj) if poczekaj.isdigit() else 65, 120))
            kod, surowe, h, loc = _jeden(teraz, timeout, max_mb, naglowki)
        if loc:
            droga.append(teraz)
            teraz = urllib.parse.urljoin(teraz, loc)
            continue
        break
    if len(surowe) > max_mb * 1_000_000:
        raise ConnectionError(f"{url}: odpowiedź większa niż {max_mb} MB")
    typ = {k.lower(): v for k, v in h.items()}.get("content-type", "")
    m = re.search(r"charset=([\w-]+)", typ)
    tresc = surowe.decode(m.group(1) if m else "utf-8", "replace")
    if kod in (403, 429) or (tresc[:1].strip() in ("<", "") and any(o in tresc[:6000] for o in OZNAKI_BLOKADY)):
        LICZNIK["bledy"] += 1
        raise Blokada(f"{urllib.parse.urlsplit(teraz).netloc} odmówił ({kod}); nie obchodzimy ochrony, zgłoś blokadę")
    odp = Odpowiedz(kod, tresc, teraz, typ, droga)
    if pamiec_h and kod in (200, 404, 410):
        plik.parent.mkdir(parents=True, exist_ok=True)
        plik.write_text(json.dumps(asdict(odp), ensure_ascii=False), encoding="utf-8")
    return odp


def json_z(url: str, **kw) -> object | None:
    """JSON z adresu albo None (kod ≠ 200 albo treść, która nie jest JSON-em)."""
    odp = pobierz(url, **kw)
    if odp.kod != 200:
        return None
    try:
        return json.loads(odp.tresc)
    except ValueError:
        return None


def wolno(url: str) -> bool:
    """robots.txt hosta pozwala na ten adres (brak pliku albo błąd = wolno, jak u przeglądarek i wyszukiwarek)."""
    p = urllib.parse.urlsplit(url)
    host = f"{p.scheme}://{p.netloc}"
    if host not in _roboty:
        rp = urllib.robotparser.RobotFileParser()
        try:
            odp = pobierz(f"{host}/robots.txt", pamiec_h=24)
            rp.parse(odp.tresc.splitlines() if odp.kod == 200 else [])
            _roboty[host] = rp
        except (ConnectionError, Blokada):
            _roboty[host] = None
    rp = _roboty[host]
    return True if rp is None else rp.can_fetch(UA, url)


# ------------------------------------------------------------------ adresy i daty

def domena(url: str) -> str:
    h = (urllib.parse.urlsplit(url if "://" in url else f"https://{url}").hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def strona_glowna(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = f"https://{url}"
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}/"


MIESIACE_PL = {"sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6, "lip": 7, "sie": 8, "wrz": 9, "paź": 10,
               "paz": 10, "lis": 11, "gru": 12}


def data_pl(tekst: str) -> dt.date | None:
    """„28 wrz 2026” albo „28 września 2026” → data."""
    m = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]{3,})\.?\s+(20\d\d)", tekst or "", re.I)
    if not m:
        return None
    mies = MIESIACE_PL.get(m.group(2).lower()[:3])
    try:
        return dt.date(int(m.group(3)), mies, int(m.group(1))) if mies else None
    except ValueError:
        return None


def data_iso(tekst: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(tekst)[:10]) if tekst else None
    except ValueError:
        return None


def dni_temu(d: dt.date | None) -> int | None:
    return (DZIS - d).days if d else None


# ------------------------------------------------------------------ wynik kontroli

ZNAK = {"ok": "✓", "blad": "✗", "ostrz": "⚠", "brak_danych": "?", "info": "ℹ", "nd": "—"}
WAGA = {"blad": 0, "ostrz": 1, "brak_danych": 2, "info": 3, "ok": 4, "nd": 5}


@dataclass
class Kontrola:
    id: str
    obszar: str            # ios | android | linki | strona | opinie
    tytul: str
    status: str            # klucz ZNAK
    dowod: str = ""
    poprawka: str = ""
    kto: str = ""          # jarvo-web | jarvo-studio | jarvo-mobile | właściciel
    zrodlo: str = ""       # adres, z którego pochodzi dowód
    podstawa: str = ""     # wytyczna albo zasada sklepu

    def __post_init__(self):
        if self.status not in ZNAK:
            raise ValueError(f"nieznany status {self.status!r}")


def zapisz(sciezka: str | Path, tresc: str) -> Path:
    p = Path(sciezka)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tresc, encoding="utf-8")
    return p


def md_komorka(tekst: object) -> str:
    return str(tekst if tekst is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def podsumowanie() -> str:
    return f"zapytań {LICZNIK['zapytania']}, z pamięci {LICZNIK['z_pamieci']}, błędów {LICZNIK['bledy']}"


def obraz(sciezka: str | Path) -> dict:
    """Nagłówek obrazu bez bibliotek: {typ, szer, wys, alfa, bajty}. PNG: typ koloru 4/6 albo blok tRNS = alfa;
    JPEG: wymiary z markera SOF, alfy nie ma. Inny plik: {typ: None}."""
    p = Path(sciezka)
    dane = p.read_bytes()
    info = {"typ": None, "szer": 0, "wys": 0, "alfa": False, "bajty": len(dane)}
    if dane[:8] == b"\x89PNG\r\n\x1a\n":
        info.update(typ="png", szer=int.from_bytes(dane[16:20], "big"), wys=int.from_bytes(dane[20:24], "big"))
        kolor, i = dane[25], 8
        alfa = kolor in (4, 6)
        while i + 8 <= len(dane) and not alfa:
            n, nazwa = int.from_bytes(dane[i:i + 4], "big"), dane[i + 4:i + 8]
            if nazwa == b"tRNS":
                alfa = True
            if nazwa in (b"IDAT", b"IEND"):
                break
            i += 12 + n
        info["alfa"] = alfa
    elif dane[:2] == b"\xff\xd8":
        info["typ"], i = "jpeg", 2
        while i + 9 < len(dane):
            if dane[i] != 0xFF:
                i += 1
                continue
            znacznik, n = dane[i + 1], int.from_bytes(dane[i + 2:i + 4], "big")
            if znacznik in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                info.update(wys=int.from_bytes(dane[i + 5:i + 7], "big"), szer=int.from_bytes(dane[i + 7:i + 9], "big"))
                break
            i += 2 + n
    return info
