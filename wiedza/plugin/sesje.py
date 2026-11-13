"""Skrzynki sesji zewnętrznych: wiadomość właściciela zakończona dopiskiem (np. „gpu”) idzie do innej sesji agenta.

Właściciel ma poza flotą długie sesje agenta kodującego (np. sesja omp o kernelach GPU jego silnika, przeniesiona na
serwer Jarva 13.11). Chce wysyłać do nich tweety i linki z telefonu tym samym botem: wiadomość zakończona słowem
z `<dane>/jarvo/konfig/sesje.json` nie trafia do Jarva, tylko jako plik JSON do skrzynki tej sesji; bot odpowiada
krótkim potwierdzeniem, a odpowiedź sesji wysyła jej własny proces (`jarvo telegram wyslij`).

Hak `pre_gateway_dispatch` (brama, przed autoryzacją i modelem): przechwytuje tylko wiadomości od osoby
z listy dozwolonych; reszta idzie dalej zwykłą drogą. Konfiguracja (bez sekretów):

    {"gpu": {"nazwa": "Kernel", "skrzynka": "/home/<użytkownik>/kernel/skrzynka"}}

Plik w skrzynce: `nowe/<RRRRMMDD-HHMMSS>-<id wiadomości>.json` z polami dopisek, nazwa, tekst (bez dopisku),
odpowiedz_na (cytowana wiadomość), media (kopie zdjęć i plików obok JSON-a), czas, chat_id, message_id.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

PLIK_KONFIGURACJI = "sesje.json"
_OSTATNIE_SLOWO = re.compile(r"(?:^|\s)([^\s]+)\s*$")
_PRZYJETE: dict[tuple[str, str], float] = {}     # (chat, wiadomość) → czas: ten sam event dwa razy (dwie rejestracje
_PAMIEC_S = 600                                  # wtyczki, ponowienie Telegrama) nie robi drugiego pliku ani potwierdzenia


def _dane() -> Optional[Path]:
    h = os.environ.get("HERMES_HOME")
    if not h:
        return None
    p = Path(h)
    return p.parent.parent if p.parent.name == "profiles" else p


def konfiguracja(dane: Optional[Path] = None) -> dict[str, dict]:
    """Dopisek (małe litery) → {nazwa, skrzynka}; brak pliku albo błąd = brak skrzynek."""
    dane = dane or _dane()
    if dane is None:
        return {}
    try:
        surowe = json.loads((dane / "jarvo" / "konfig" / PLIK_KONFIGURACJI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    wynik = {}
    for dopisek, wpis in (surowe or {}).items():
        if isinstance(wpis, dict) and wpis.get("skrzynka"):
            wynik[str(dopisek).strip().lower()] = {"nazwa": str(wpis.get("nazwa") or dopisek), "skrzynka": str(wpis["skrzynka"])}
    return wynik


def rozpoznaj(tekst: str, dopiski: dict[str, dict]) -> Optional[tuple[str, str]]:
    """(dopisek, tekst bez dopisku), gdy ostatnie słowo wiadomości to dopisek („… gpu”, „…, GPU.”); inaczej None."""
    m = _OSTATNIE_SLOWO.search(tekst or "")
    if not m:
        return None
    slowo = m.group(1).strip(".,;:!?…\"'()").lower()
    if slowo not in dopiski:
        return None
    return slowo, tekst[: m.start(1)].rstrip(" \t\n,;:-–—")


def zapisz(skrzynka: Path, dopisek: str, nazwa: str, tekst: str, event: Any) -> Path:
    """Wiadomość jako JSON w `nowe/` (zapis przez plik tymczasowy, więc proces sesji nie przeczyta połowy)."""
    nowe = skrzynka / "nowe"
    nowe.mkdir(parents=True, exist_ok=True)
    zrodlo = getattr(event, "source", None)
    mid = re.sub(r"[^0-9A-Za-z_-]", "", str(getattr(event, "message_id", "") or "")) or "0"
    rdzen = f"{time.strftime('%Y%m%d-%H%M%S')}-{mid}"
    media = []
    for i, sciezka in enumerate(getattr(event, "media_urls", None) or []):
        p = Path(str(sciezka))
        if p.is_file():
            cel = nowe / f"{rdzen}-{i}{p.suffix}"
            shutil.copy2(p, cel)
            media.append(str(cel))
    wpis = {"dopisek": dopisek, "nazwa": nazwa, "tekst": tekst,
            "odpowiedz_na": getattr(event, "reply_to_text", None) or "",
            "media": media, "czas": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chat_id": str(getattr(zrodlo, "chat_id", "") or ""), "message_id": mid}
    tymczasowy = nowe / f".{rdzen}.json.tmp"
    tymczasowy.write_text(json.dumps(wpis, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    plik = nowe / f"{rdzen}.json"
    tymczasowy.replace(plik)
    return plik


async def przechwyc(event: Any = None, gateway: Any = None, **_kw) -> Optional[dict]:
    """Hak `pre_gateway_dispatch`: wiadomość z dopiskiem sesji → skrzynka + potwierdzenie, Jarvo jej nie dostaje."""
    try:
        if event is None or getattr(event, "internal", False) or not isinstance(getattr(event, "text", None), str):
            return None
        dopiski = konfiguracja()
        trafienie = rozpoznaj(event.text, dopiski) if dopiski else None
        if trafienie is None:
            return None
        zrodlo = getattr(event, "source", None)
        autoryzacja = getattr(gateway, "_is_user_authorized_for_source", None)
        if zrodlo is None or not callable(autoryzacja) or not autoryzacja(zrodlo):
            return None                       # obcy nadawca idzie zwykłą drogą (parowanie / odmowa Hermesa)
        dopisek, tekst = trafienie
        klucz = (str(getattr(zrodlo, "chat_id", "") or ""), str(getattr(event, "message_id", "") or ""))
        teraz = time.time()
        for k in [k for k, t in _PRZYJETE.items() if teraz - t > _PAMIEC_S]:
            del _PRZYJETE[k]
        if klucz[1] and klucz in _PRZYJETE:
            return {"action": "skip", "reason": f"skrzynka sesji „{dopisek}” (już przyjęta)"}
        _PRZYJETE[klucz] = teraz
        cel = dopiski[dopisek]
        skrzynka = Path(os.path.expanduser(cel["skrzynka"]))
        zapisz(skrzynka, dopisek, cel["nazwa"], tekst, event)
        w_kolejce = len(list((skrzynka / "nowe").glob("*.json")))
        potwierdzenie = f"📥 {cel['nazwa']}: przyjąłem, analizuję" + (f" (w kolejce: {w_kolejce})" if w_kolejce > 1 else "") + "."
        adapter = getattr(gateway, "_delivery_adapter_for", lambda _s: None)(zrodlo)
        if adapter is not None:
            try:
                await adapter.send(zrodlo.chat_id, potwierdzenie)
            except Exception as e:            # potwierdzenie to grzeczność; wiadomość już leży w skrzynce
                logger.warning("jarvo-wiedza: potwierdzenie skrzynki %s nie wyszło: %s", dopisek, e)
        return {"action": "skip", "reason": f"skrzynka sesji „{dopisek}”"}
    except Exception as e:                    # awaria haka nigdy nie gubi wiadomości: idzie do Jarva
        logger.warning("jarvo-wiedza: skrzynka sesji: %s", e)
        return None
