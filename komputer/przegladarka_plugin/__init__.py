"""Wtyczka jarvo-przegladarka: wyniki narzędzi browser_* Hermesa dla agentów floty (docs/KOMPUTER.md
„Przeglądarka agentów floty”).

Hak `transform_tool_result` (każdy profil, bez narzędzi i bez stanu na dysku):
  - `browser_navigate`: bez `stealth_warning` i `stealth_features` (Hermes dokłada je przy każdej pierwszej nawigacji
    z radą o planie Browserbase, którego flota nie używa); blokadę antybotową rozpoznaje po tytule i po treści
    widoku (Cloudflare, DataDome, CAPTCHA, pusta strona z samą domeną w tytule) i podaje drogę floty zamiast
    angielskich rad Hermesa;
  - `browser_click`, `browser_press`, `browser_back`: po udanym działaniu dokłada `stan_po` = widok strony po
    ustaleniu (browser_snapshot: nakładka agent-browsera czeka na wczytanie i ciszę DOM, potem zwarta lista z refami
    i adresem), więc agent nie woła osobno browser_snapshot i nie klika refów sprzed zmiany strony.
Błąd haka nigdy nie psuje wyniku: wtedy wynik zostaje bez zmian (None).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

NAWIGACJA = "browser_navigate"
PO_DZIALANIU = frozenset({"browser_click", "browser_press", "browser_back"})
ZNAKI_BLOKADY = ("datadome", "captcha", "cloudflare", "just a moment", "checking your browser", "attention required",
                 "verify you are human", "are you a robot", "access denied", "access to this page has been denied",
                 "bot detected", "blocked", "verification required", "please verify", "ddos protection",
                 "cierpliwości", "weryfikacji zabezpieczeń", "zostałeś zablokowany", "jesteś człowiekiem",
                 "potwierdź, że jesteś", "turnstile", "perimeterx", "px-captcha")
KROTKI_WIDOK = 2500          # znaków: tak mała bywa strona blokady; w dłuższej treści te słowa to zwykły tekst
BLOKADA = ("Strona zatrzymała przeglądarkę testem antybotowym ({znak}). Możesz raz kliknąć pole „Jestem człowiekiem”, "
           "jeśli jest w widoku; gdy strona dalej blokuje, nie ponawiaj i nie zmieniaj przeglądarki, tylko zrób ten krok "
           "na telefonie floty, a jeśli i tam nie przejdzie, kanban_block z needs_input.")


def blokada(wynik: dict) -> Optional[str]:
    """Znak blokady antybotowej w wyniku nawigacji albo None: słowo blokady w tytule, w krótkim widoku (strona
    blokady jest mała; w artykule o Cloudflare to zwykły tekst) albo pusta strona z samą domeną w tytule."""
    tytul = str(wynik.get("title") or "")
    widok = re.sub(r"^adres: [^\n]*\n?", "", str(wynik.get("snapshot") or ""))
    tekst = (tytul + ("\n" + widok if len(widok) < KROTKI_WIDOK else "")).lower()
    for znak in ZNAKI_BLOKADY:
        if znak in tekst:
            return znak
    domena = re.sub(r"^www\.", "", re.sub(r"^https?://([^/]+).*$", r"\1", str(wynik.get("url") or "")).lower())
    if domena and re.sub(r"^www\.", "", tytul.strip().lower()) == domena and len(widok.strip()) < 80:
        return "pusta strona z samą domeną w tytule"
    return None


def _widok(task_id: str) -> Optional[dict]:
    try:
        from tools import browser_tool                       # Hermes: ta sama sesja, co działanie
        w = json.loads(browser_tool.browser_snapshot(task_id=task_id or None))
    except Exception as e:                                   # noqa: BLE001 - widok po działaniu jest dodatkiem
        logger.debug("jarvo-przegladarka: widok po działaniu: %s", e)
        return None
    return w if isinstance(w, dict) and w.get("success") else None


def przerob(tool_name: str = "", args: Any = None, result: Any = None, task_id: str = "", **_kw: Any) -> Optional[str]:
    """Hak `transform_tool_result` (docstring modułu): nowy wynik albo None (bez zmian)."""
    if (tool_name != NAWIGACJA and tool_name not in PO_DZIALANIU) or not isinstance(result, str):
        return None
    try:
        wynik = json.loads(result)
    except ValueError:
        return None
    if not isinstance(wynik, dict) or not wynik.get("success"):
        return None
    if tool_name == NAWIGACJA:
        zmiana = wynik.pop("stealth_warning", None) is not None
        zmiana = wynik.pop("stealth_features", None) is not None or zmiana
        wynik.pop("bot_detection_warning", None)
        znak = blokada(wynik)
        if znak:
            wynik["bot_detection_warning"] = BLOKADA.format(znak=znak)
            zmiana = True
        elif "bot_detection_warning" in json.loads(result):
            zmiana = True                                    # angielskie rady Hermesa bez blokady w treści
    else:
        widok = _widok(task_id)
        if widok is None:
            return None
        wynik["stan_po"] = widok.get("snapshot", "")
        wynik["element_count"] = widok.get("element_count", 0)
        zmiana = True
    return json.dumps(wynik, ensure_ascii=False) if zmiana else None


def register(ctx) -> None:
    ctx.register_hook("transform_tool_result", przerob)
