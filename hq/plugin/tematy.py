"""Sesja tematu Telegrama rozmówcy floty (centrum §3.1): panel i temat w grupie JARVO HQ piszą do jednej sesji Hermesa.

- **Temat** rozmówcy: grupa i wątek z `<dane>/jarvo/state/telegram-grupy.json` (pisze go wtyczka jarvo-sesje przy
  każdej wiadomości właściciela w grupie). Temat `general` = wątek General („1”), inny = wątek, którego nazwa to nazwa
  rozmówcy albo jego temat wielkimi literami (tak nazywa tematy `jarvo telegram tematy`).
- **Bieżąca sesja** tematu: trasa bramy pod kluczem `agent:<profil>:telegram:group:<czat>:<wątek>` (temat General
  także bez wątku) w tabeli `gateway_routing` state.db hosta albo profilu (tylko odczyt, `mode=ro`), zapasowo lustro
  `sessions/sessions.json`. Wynik: {session_id, prev_session_id, was_auto_reset}; brak trasy = None (nikt jeszcze
  nie pisał w temacie: panel zaczyna własną sesję `jarvo_r_<profil>`, D5).
Czysty Python bez Hermesa; testy: tests/test_tematy.py.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

PLIK_GRUP = "telegram-grupy.json"
WATEK_OGOLNY = "1"
PROFIL_RE = re.compile(r"^[a-z0-9-]+$")
CZAT_RE = re.compile(r"^-\d{3,20}$")
WATEK_RE = re.compile(r"^\d{1,12}$")


def _json(p: Path) -> object:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def temat(dane: Path, temat_tg: str, nazwa: str) -> tuple[str, str] | None:
    """(czat, wątek) tematu rozmówcy z telegram-grupy.json; grupa forum z najnowszym wpisem wygrywa."""
    stan = _json(Path(dane) / "jarvo" / "state" / PLIK_GRUP)
    grupy = stan.get("grupy") if isinstance(stan, dict) and isinstance(stan.get("grupy"), dict) else {}
    szukane = {str(nazwa or "").strip().upper(), str(temat_tg or "").strip().upper()} - {""}
    kandydaci = sorted(((str(g.get("od") or ""), czat, g) for czat, g in grupy.items()
                        if isinstance(g, dict) and CZAT_RE.match(str(czat))), reverse=True)
    for _od, czat, g in kandydaci:
        if temat_tg == "general":
            return czat, WATEK_OGOLNY
        for wid, w in (g.get("watki") or {}).items():
            if isinstance(w, dict) and str(w.get("nazwa") or "").strip().upper() in szukane and WATEK_RE.match(str(wid)):
                return czat, str(wid)
    return None


def klucze_trasy(profil: str, czat: str, watek: str) -> list[str]:
    if not (PROFIL_RE.match(profil) and CZAT_RE.match(czat) and WATEK_RE.match(watek)):
        raise ValueError("zły temat")
    baza = f"agent:{profil}:telegram:group:{czat}"
    return [f"{baza}:{watek}", baza] if watek == WATEK_OGOLNY else [f"{baza}:{watek}"]


def _wpis(surowy: object) -> dict | None:
    if isinstance(surowy, str):
        try:
            surowy = json.loads(surowy)
        except ValueError:
            return None
    if not isinstance(surowy, dict) or not isinstance(surowy.get("session_id"), str) or not surowy["session_id"]:
        return None
    return {"session_id": surowy["session_id"], "prev_session_id": surowy.get("prev_session_id") or None,
            "was_auto_reset": bool(surowy.get("was_auto_reset"))}


def sesja_tematu(dane: Path, profil: str, czat: str, watek: str) -> dict | None:
    """Bieżąca sesja bramy dla tematu (state.db `gateway_routing`, potem sessions.json); None = brak trasy."""
    dane = Path(dane)
    klucze = klucze_trasy(profil, czat, watek)
    for baza in (dane / "profiles" / profil, dane):
        db = baza / "state.db"
        if not db.is_file():
            continue
        try:
            conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
            try:
                for k in klucze:
                    row = conn.execute("SELECT entry_json FROM gateway_routing WHERE session_key = ?", (k,)).fetchone()
                    wpis = _wpis(row[0]) if row else None
                    if wpis:
                        return wpis
            finally:
                conn.close()
        except sqlite3.Error:
            continue
    for baza in (dane / "profiles" / profil, dane):
        lustro = _json(baza / "sessions" / "sessions.json")
        if isinstance(lustro, dict):
            for k in klucze:
                wpis = _wpis(lustro.get(k))
                if wpis:
                    return wpis
    return None


def sesja_panelu(profil: str) -> str:
    """Stała sesja panelu, gdy temat nie ma jeszcze sesji bramy (D5)."""
    if not PROFIL_RE.match(profil):
        raise ValueError("zły profil")
    return f"jarvo_r_{profil}"
