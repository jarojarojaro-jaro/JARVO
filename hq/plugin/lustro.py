"""Lustro panel → Telegram (centrum §3.1, D10): rozmowa z rozmówcą Hermesa z panelu trafia też do jego tematu w grupie
JARVO HQ, więc historia w Telegramie jest pełna.

- Po końcu przebiegu `gotowe` w wątku rozmówcy z włączonym lustrem (`rozmowcy.lustro`) silnik zapisuje w przebiegu
  `lustro = {"stan": "czeka", "odp": <odpowiedź>}`; pętla wysyła „🖥 <tekst właściciela, do 300 znaków>” i odpowiedź
  (pocięta po 4000 znaków) do tematu, potem `lustro_at` i `stan: ok`. Każda wysyłka jest jedna: przebieg z `lustro_at`
  nie idzie drugi raz (także po restarcie). Błąd: do 3 prób co 30 s, potem `stan: nie_doszlo` i zdarzenie
  `przebieg.lustro` (pod dymkiem znacznik „nie doszło do Telegrama”).
- Wysyła Bot API bramy (token `TELEGRAM_BOT_TOKEN` z `<dane>/.env`, ten sam co `jarvo telegram wyslij`). Token nie
  trafia do dziennika, odpowiedzi ani przeglądarki; dziennik nie ma treści rozmów.
- Rozmówcy omp lustra tu nie mają: odpowiedź do tematu wysyła proces skrzynki (`jarvo sesja`), a wiadomość z panelu
  niesie `lustro` w pliku skrzynki.
Testy: tests/test_lustro.py.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

TELEGRAM_API = "https://api.telegram.org"
PROSBA_MAKS = 300
CZESC_MAKS = 4000
PROBY = 3
ODSTEP_S = 30.0
ODP_MAKS = 64_000


class BladLustra(RuntimeError):
    """Wysyłka do Telegrama nieudana (opis bez tokenu)."""


def token(dane: Path) -> str:
    """TELEGRAM_BOT_TOKEN z `<dane>/.env` bramy (linia KLUCZ=wartość, opcjonalnie w cudzysłowie)."""
    try:
        linie = (Path(dane) / ".env").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for linia in linie:
        k, _, v = linia.strip().partition("=")
        if k.strip().removeprefix("export ").strip() == "TELEGRAM_BOT_TOKEN":
            return v.strip().strip("\"'")
    return ""


def wiadomosci(prosba: str, odpowiedz: str) -> list[str]:
    """Teksty do tematu: „🖥 ” + prośba właściciela (≤ 300 znaków), potem odpowiedź w częściach ≤ 4000 znaków
    (cięcie na końcu linii, gdy się da)."""
    prosba = " ".join(str(prosba or "").split())
    if len(prosba) > PROSBA_MAKS:
        prosba = prosba[:PROSBA_MAKS - 1].rstrip() + "…"
    out = [f"🖥 {prosba}"] if prosba else []
    reszta = str(odpowiedz or "").strip()
    while reszta:
        if len(reszta) <= CZESC_MAKS:
            out.append(reszta)
            break
        ciecie = reszta.rfind("\n", 0, CZESC_MAKS)
        ciecie = ciecie if ciecie > CZESC_MAKS // 2 else CZESC_MAKS
        out.append(reszta[:ciecie].rstrip())
        reszta = reszta[ciecie:].lstrip("\n")
    return out


def wyslij(tok: str, czat: str, watek: str, tekst: str, *, baza: str | None = None, czas: float = 20.0) -> int:
    """sendMessage do tematu; zwraca message_id. BladLustra bez tokenu w opisie."""
    baza = (baza or os.environ.get("JARVO_TELEGRAM_API") or TELEGRAM_API).rstrip("/")
    dane = {"chat_id": czat, "text": tekst, "disable_web_page_preview": True}
    if watek and watek != "1":
        dane["message_thread_id"] = int(watek)
    req = urllib.request.Request(f"{baza}/bot{tok}/sendMessage", data=json.dumps(dane).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "jarvo"})
    host = urllib.parse.urlsplit(baza).hostname or ""
    otw = (urllib.request.build_opener(urllib.request.ProxyHandler({})) if host in ("127.0.0.1", "localhost", "::1")
           else urllib.request.build_opener())
    try:
        with otw.open(req, timeout=czas) as r:
            odp = json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            odp = json.loads(e.read().decode("utf-8", errors="replace"))
        except ValueError:
            odp = {"ok": False, "description": f"HTTP {e.code}"}
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise BladLustra(f"brak połączenia z Telegramem ({type(e).__name__})") from None
    if not isinstance(odp, dict) or not odp.get("ok"):
        opis = str((odp or {}).get("description") or "błąd API") if isinstance(odp, dict) else "błąd API"
        raise BladLustra(opis.replace(tok, "…") if tok else opis)
    return int(((odp.get("result") or {}).get("message_id")) or 0)


class Lustro:
    """Kolejka lustra w rozmowy.db (pole `przebiegi.lustro`); `wyslij_fn` podmieniają testy."""

    def __init__(self, db, dane: Path | str, hub=None, *, log: Callable[[str], None] | None = None,
                 wyslij_fn: Callable[..., int] = wyslij, zegar: Callable[[], float] = time.time):
        self.db, self.dane, self.hub = db, Path(dane), hub
        self.log = log or (lambda _m: None)
        self.wyslij_fn, self.zegar = wyslij_fn, zegar

    def po_koncu(self, p: dict, stan: str, odpowiedz: str) -> bool:
        """Koniec przebiegu: zapamiętaj do wysłania, gdy to rozmówca Hermesa z lustrem i tematem. True = w kolejce."""
        if stan != "gotowe" or p.get("lustro_at") or p.get("lustro") or p.get("zrodlo") not in ("wlasciciel", None):
            return False
        r = self.db.rozmowca_watku(p["watek_id"])
        if not r or r.get("zaplecze") != "hermes" or not r.get("lustro") or not (r.get("czat") and r.get("watek_tg")):
            return False
        self.db.zmien_przebieg(p["id"], lustro=json.dumps({"stan": "czeka", "proby": 0, "odp": str(odpowiedz or "")[:ODP_MAKS]},
                                                          ensure_ascii=False))
        return True

    def do_wyslania(self) -> list[dict]:
        out = []
        for p in self.db._przebiegi("lustro IS NOT NULL AND lustro_at IS NULL"):
            try:
                stan = json.loads(p.get("lustro") or "{}")
            except ValueError:
                continue
            if stan.get("stan") == "czeka" and float(stan.get("nastepna_at") or 0) <= self.zegar():
                out.append({**p, "_lustro": stan})
        return out

    def runda(self) -> int:
        """Jedna runda (wątek tła silnika): wysyła zaległe; zwraca liczbę wysłanych przebiegów."""
        zalegle = self.do_wyslania()
        if not zalegle:
            return 0
        tok = token(self.dane)
        wyslane = 0
        for p in zalegle:
            stan = p["_lustro"]
            r = self.db.rozmowca_watku(p["watek_id"]) or {}
            wpis = self.db.wpis(p["wpis_id"]) if p.get("wpis_id") else None
            prosba = (wpis or {}).get("tekst") or (p.get("payload") or {}).get("prosba") or ""
            try:
                if not tok:
                    raise BladLustra("brak tokenu bota")
                ids = [self.wyslij_fn(tok, r["czat"], r["watek_tg"], t) for t in wiadomosci(prosba, stan.get("odp") or "")]
            except (BladLustra, KeyError, TypeError) as e:
                proby = int(stan.get("proby") or 0) + 1
                nowy = {**stan, "proby": proby, "nastepna_at": self.zegar() + ODSTEP_S}
                if proby >= PROBY:
                    nowy = {"stan": "nie_doszlo", "proby": proby}
                    self.log(f"jarvo-hq: lustro {p['id']}: nie doszło do Telegrama ({str(e)[:80]})")
                self.db.zmien_przebieg(p["id"], lustro=json.dumps(nowy, ensure_ascii=False))
                if nowy["stan"] == "nie_doszlo" and self.hub is not None:
                    self.hub.nadaj("przebieg.lustro", {"przebieg_id": p["id"], "watek_id": p["watek_id"], "stan": "nie_doszlo"},
                                   watek_id=p["watek_id"])
                continue
            self.db.zmien_przebieg(p["id"], lustro_at=self.zegar(),
                                   lustro=json.dumps({"stan": "ok", "message_id": ids[-1] if ids else 0}))
            wyslane += 1
        return wyslane
