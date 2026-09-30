"""Wspólne narzędzia Łowcy: grzeczne HTTP (uczciwy User-Agent, pauza na host, pamięć odpowiedzi), kontakty, JSONL.

Tylko biblioteka standardowa. Źródła odpowiadające ochroną antybotową albo odmową traktujemy jak blokadę
(kontrakt pkt 16): skrypt zgłasza błąd i nie próbuje innej drogi.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (compatible; jarvo-lowca/1.0; +https://jarvo.pl)"
PAUZA_S = float(os.environ.get("LOWCA_PAUZA", "0.25"))        # minimum między zapytaniami do jednego hosta
PAUZY_HOSTOW = {"ezamowienia.gov.pl": 4.0}                     # ciężkie odpowiedzi (pełny HTML ogłoszeń): wolniej
OZNAKI_BLOKADY = ("_Incapsula_Resource", "cf-chl", "Dostęp zablokowany", "Access Blocked", "Request unsuccessful")
CACHE = Path(os.environ.get("LOWCA_CACHE", str(Path.home() / ".cache" / "jarvo-lowca")))
LICZNIK = {"zapytania": 0, "z_pamieci": 0, "bledy": 0}

WOJ = {"PL02": "DOLNOŚLĄSKIE", "PL04": "KUJAWSKO-POMORSKIE", "PL06": "LUBELSKIE", "PL08": "LUBUSKIE",
       "PL10": "ŁÓDZKIE", "PL12": "MAŁOPOLSKIE", "PL14": "MAZOWIECKIE", "PL16": "OPOLSKIE", "PL18": "PODKARPACKIE",
       "PL20": "PODLASKIE", "PL22": "POMORSKIE", "PL24": "ŚLĄSKIE", "PL26": "ŚWIĘTOKRZYSKIE",
       "PL28": "WARMIŃSKO-MAZURSKIE", "PL30": "WIELKOPOLSKIE", "PL32": "ZACHODNIOPOMORSKIE"}
WOJ_KOD = {v: k for k, v in WOJ.items()}


class Blokada(Exception):
    """Źródło odmówiło (403/429, ochrona antybotowa, robots.txt): koniec, nie zagadka."""


_lock = threading.Lock()
_ostatnie: dict[str, float] = {}


def _czekaj(host: str) -> None:
    with _lock:
        teraz = time.monotonic()
        start = max(teraz, _ostatnie.get(host, 0.0) + PAUZY_HOSTOW.get(host, PAUZA_S))
        _ostatnie[host] = start
    if start > teraz:
        time.sleep(start - teraz)


def _klucz(metoda: str, url: str, dane: bytes | None) -> Path:
    h = hashlib.sha256(f"{metoda} {url}".encode() + (dane or b"")).hexdigest()[:32]
    return CACHE / "http" / h[:2] / f"{h}.json"


def http(url: str, metoda: str = "GET", dane: dict | None = None, pamiec_h: float = 12.0, naglowki: dict | None = None,
         timeout: int = 30, max_mb: int = 6) -> tuple[int, str]:
    """(kod, treść). Pamięć odpowiedzi na dysku przez `pamiec_h` godzin (0 = bez pamięci)."""
    body = json.dumps(dane).encode() if dane is not None else None
    plik = _klucz(metoda, url, body)
    if pamiec_h and plik.is_file() and time.time() - plik.stat().st_mtime < pamiec_h * 3600:
        LICZNIK["z_pamieci"] += 1
        z = json.loads(plik.read_text(encoding="utf-8"))
        return z["kod"], z["tresc"]
    _czekaj(urllib.parse.urlsplit(url).netloc)
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.5", **(naglowki or {})}
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=metoda, headers=h)
    LICZNIK["zapytania"] += 1
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (adresy źródeł z kodu albo od agenta)
            surowe = r.read(max_mb * 1_000_000 + 1)
            if len(surowe) > max_mb * 1_000_000:
                raise ConnectionError(f"{url}: odpowiedź większa niż {max_mb} MB (zawęź zapytanie)")
            kod, tresc = r.status, surowe.decode(r.headers.get_content_charset() or "utf-8", "replace")
    except urllib.error.HTTPError as e:
        kod, tresc = e.code, e.read(200_000).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        LICZNIK["bledy"] += 1
        raise ConnectionError(f"{url}: {e}") from e
    if kod in (403, 429) or (tresc[:1].strip() in ("<", "") and any(o in tresc[:4000] for o in OZNAKI_BLOKADY)):
        LICZNIK["bledy"] += 1
        raise Blokada(f"{urllib.parse.urlsplit(url).netloc} odmówił ({kod}); nie obchodzimy ochrony, zgłoś blokadę")
    if pamiec_h and kod in (200, 404):
        plik.parent.mkdir(parents=True, exist_ok=True)
        plik.write_text(json.dumps({"kod": kod, "tresc": tresc}, ensure_ascii=False), encoding="utf-8")
    return kod, tresc


def json_z(url: str, **kw):
    kod, tresc = http(url, **kw)
    if kod != 200:
        return None
    try:
        return json.loads(tresc)
    except ValueError as e:                                   # ucięta albo zła odpowiedź: nie zostaje w pamięci
        _klucz(kw.get("metoda", "GET"), url, None).unlink(missing_ok=True)
        raise ConnectionError(f"{url}: niepoprawny JSON ({e})") from e


# ------------------------------------------------------------------ kontakty

DARMOWE = {"gmail.com", "wp.pl", "o2.pl", "onet.pl", "onet.eu", "interia.pl", "interia.eu", "op.pl", "icloud.com",
           "yahoo.com", "outlook.com", "hotmail.com", "live.com", "gazeta.pl", "tlen.pl", "vp.pl", "poczta.fm", "proton.me",
           "protonmail.com", "me.com", "aol.com", "yandex.com", "mail.com", "go2.pl", "autograf.pl", "buziaczek.pl"}
OGOLNE = {"biuro", "kontakt", "contact", "info", "office", "hello", "hej", "czesc", "sekretariat", "recepcja", "firma",
          "mail", "poczta", "admin", "sklep", "shop", "zamowienia", "obsluga", "bok", "support", "pomoc", "help"}
ROLOWE = {"sprzedaz", "sales", "handel", "marketing", "hr", "rekrutacja", "kariera", "praca", "jobs", "careers",
          "ksiegowosc", "faktury", "biznes", "b2b", "oferty", "zakupy", "press", "media", "pr", "partner", "partners",
          "wspolpraca", "it", "dev", "ceo", "zarzad", "board", "prezes", "dyrektor", "kadry", "rodo", "iod", "dpo"}
EMAIL_RE = re.compile(r"(?<![\w.+-])([a-z0-9][a-z0-9._%+-]{0,63})@([a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,24})(?![\w-])", re.I)
PHONE_RE = re.compile(r"(?<![\d+])(?:\+?48[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}|\d{3}[\s.-]?\d{3}[\s.-]?\d{3})(?!\d)")
ZASLONY = [(re.compile(r"\s*[\[\(\{<]\s*(?:at|małpa|malpa)\s*[\]\)\}>]\s*", re.I), "@"),
           (re.compile(r"\s*[\[\(\{<]\s*(?:dot|kropka)\s*[\]\)\}>]\s*", re.I), ".")]
BEZ_SENSU = ("example.", "domain.", "email.", "sentry", "wixpress", "@2x", ".png", ".jpg", ".webp", ".svg", ".gif")


def odslon(tekst: str) -> str:
    """„biuro [at] firma [dot] pl” → „biuro@firma.pl” (adres opublikowany, tylko zapisany inaczej)."""
    for wz, zam in ZASLONY:
        tekst = wz.sub(zam, tekst)
    return tekst


def typ_emaila(email: str) -> str:
    """ogolny (biuro@), rolowy (sprzedaz@), osobowy (imie.nazwisko@ albo skrzynka darmowa: dane osobowe)."""
    lokal, _, domena = email.lower().partition("@")
    if domena in DARMOWE:
        return "osobowy"
    baza = re.sub(r"[\d._-]+$", "", lokal)
    if baza in OGOLNE:
        return "ogolny"
    if baza in ROLOWE or any(baza.startswith(r + ".") or baza.startswith(r + "-") for r in ROLOWE):
        return "rolowy"
    return "osobowy"


def emaile(tekst: str) -> list[str]:
    out = []
    for m in EMAIL_RE.finditer(odslon(tekst)):
        e = f"{m.group(1)}@{m.group(2)}".lower().strip(".")
        if not any(b in e for b in BEZ_SENSU) and e not in out:
            out.append(e)
    return out


def telefony(tekst: str) -> list[str]:
    out = []
    for m in PHONE_RE.finditer(tekst):
        cyfry = re.sub(r"\D", "", m.group(0))
        if cyfry.startswith("48") and len(cyfry) == 11:
            cyfry = cyfry[2:]
        if len(cyfry) == 9 and cyfry[0] in "123456789" and len(set(cyfry)) > 2:
            num = f"+48 {cyfry[:3]} {cyfry[3:6]} {cyfry[6:]}"
            if num not in out:
                out.append(num)
    return out


def nip(tekst: str) -> str | None:
    d = re.sub(r"\D", "", str(tekst or ""))
    if len(d) != 10:
        return None
    wagi = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    return d if sum(int(a) * w for a, w in zip(d, wagi)) % 11 == int(d[9]) else None


FORMY = [("SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ", "sp. z o.o."), ("PROSTA SPÓŁKA AKCYJNA", "P.S.A."),
         ("SPÓŁKA KOMANDYTOWO-AKCYJNA", "S.K.A."), ("SPÓŁKA AKCYJNA", "S.A."), ("SPÓŁKA KOMANDYTOWA", "sp.k."),
         ("SPÓŁKA JAWNA", "sp.j."), ("SPÓŁKA PARTNERSKA", "sp.p.")]


def krotka_nazwa(nazwa: str | None) -> str:
    """„ARAS SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ” → „ARAS sp. z o.o.”."""
    n = nazwa or "?"
    for pelna, skrot in FORMY:
        n = re.sub(pelna, skrot, n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip()


def domena(url: str) -> str:
    h = (urllib.parse.urlsplit(url if "://" in url else f"https://{url}").hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


# ------------------------------------------------------------------ JSONL

def zapisz_jsonl(wiersze: list[dict], plik: str | None) -> None:
    tekst = "".join(json.dumps(w, ensure_ascii=False) + "\n" for w in wiersze)
    if plik and plik != "-":
        p = Path(plik)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(tekst)
    else:
        print(tekst, end="")


def czytaj_jsonl(plik: str) -> list[dict]:
    p = Path(plik)
    if not p.is_file():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def podsumowanie() -> str:
    return f"zapytań {LICZNIK['zapytania']}, z pamięci {LICZNIK['z_pamieci']}, błędów {LICZNIK['bledy']}"
