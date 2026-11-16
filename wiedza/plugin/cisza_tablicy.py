"""Cisza tablicy na czacie: o kartach mówi Jarvo, nie Hermes.

`kanban_create` z rozmowy (Telegram) subskrybuje czat w trybie `notify+wake` (Hermes, tools/kanban_tools.py:
`_resolve_notify_target`): przy każdym zdarzeniu karty Hermes wysyła na czat własny surowy komunikat
(„⏸ [default] @agent Kanban t_… blocked: …”, numery kart, ścieżki) **i** budzi Jarva, który pisze swoją
wiadomość. Właściciel dostawał dwie wiadomości o jednym zdarzeniu, w tym jedną w żargonie (14.11, InstaBox).

Hak `post_tool_call` po udanym `kanban_create` przełącza subskrypcje tej karty z `notify+wake` na `wake`:
Hermes nic nie wysyła, tylko budzi Jarva. `api_server` (czat HQ) zostaje bez zmian: tam wybudzenie JEST
dostarczeniem, a tryb ustawia sam Hermes.

Skoro o kartach mówi tylko Jarvo, karta, która czeka na właściciela (`kanban_block` z `kind: needs_input`), nie może
skończyć się ciszą: 16.11 i 17.11 Jarvo stał na okienku „jestem człowiekiem”, a właściciel nie dostał ani słowa
(„przez godzinę klikał w kółko i nie dał mi znać”). Hak `pre_llm_call` rozpoznaje budzenie „blocked; needs
attention” (szablon Hermesa, locales/en.yaml `gateway.kanban.wake`) i czyta z kanban.db ostatnią blokadę karty;
przy `needs_input` dokłada do tury przypomnienie, że trzeba napisać do właściciela. Hak `transform_llm_output`
zamienia odpowiedź-ciszę (`[SILENT]`) w tej turze na jedno zdanie dla właściciela z tytułem karty i powodem blokady.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

# platformy, na których surowy komunikat Hermesa trafiłby do właściciela obok wiadomości Jarva
BEZ_SUROWYCH = ("telegram",)
# budzenie Jarva po zmianie karty (hermes locales/en.yaml gateway.kanban.wake.message; statusy łączy „, ”)
BUDZENIE = re.compile(r"^\[kanban\] Task (\S+) (.+?)\.\nTitle: (.*)\nAssignee: @(\S+)\nBoard: (\S+)")
STATUS_BLOKADY = "blocked; needs attention"
MAKS_CZEKA = 64
_CZEKA: dict[str, tuple[str, str, str]] = {}      # sesja → (tura, tytuł karty, powód blokady needs_input)
_ZAMEK = threading.Lock()


def _wynik(result: Any) -> dict:
    if isinstance(result, dict):
        return result
    try:
        dane = json.loads(result) if isinstance(result, str) else {}
    except (TypeError, ValueError):
        return {}
    return dane if isinstance(dane, dict) else {}


def ucisz(conn, task_id: str) -> int:
    """Subskrypcje karty `task_id` na platformach z BEZ_SUROWYCH: `notify+wake` → `wake`. Zwraca liczbę zmian."""
    znaki = ",".join("?" * len(BEZ_SUROWYCH))
    cur = conn.execute(
        f"UPDATE kanban_notify_subs SET delivery_mode = 'wake' WHERE task_id = ? AND delivery_mode = 'notify+wake' "
        f"AND lower(platform) IN ({znaki})", (task_id, *BEZ_SUROWYCH))
    conn.commit()
    return cur.rowcount or 0


def po_narzedziu(function_name: str = "", function_args: Any = None, result: Any = None, **_kw: Any) -> None:
    """Hak `post_tool_call`: po `kanban_create` z subskrypcją czatu Hermes milczy, a mówi Jarvo. Błąd = log, nigdy
    wyjątek (narzędzie już się wykonało)."""
    if function_name != "kanban_create":
        return
    wynik = _wynik(result)
    task_id = wynik.get("task_id")
    if not (wynik.get("ok") and wynik.get("subscribed") and isinstance(task_id, str)):
        return
    board = function_args.get("board") if isinstance(function_args, dict) else None
    try:
        from hermes_cli import kanban_db_connect as kbc
        with kbc.connect_closing(board=board) as conn:
            ucisz(conn, task_id)
    except Exception as exc:  # noqa: BLE001 - powiadomienia nie mogą psuć zakładania kart
        logger.warning("cisza tablicy: nie przełączyłem subskrypcji %s na wake: %r", task_id, exc)


def blokada_z_budzenia(tekst: Any) -> Optional[tuple[str, str, str]]:
    """(karta, tytuł, tablica) z budzenia Hermesa o blokadzie karty; None dla innych wiadomości."""
    m = BUDZENIE.match(str(tekst or ""))
    if not m or STATUS_BLOKADY not in m.group(2).split(", "):
        return None
    return m.group(1), m.group(3).strip(), m.group(5)


def powod_needs_input(conn, task_id: str) -> Optional[str]:
    """Powód ostatniej blokady karty, gdy to `needs_input` (karta czeka na właściciela); inaczej None."""
    wiersz = conn.execute("SELECT payload FROM task_events WHERE task_id = ? AND kind = 'blocked' "
                          "ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
    try:
        dane = json.loads(wiersz[0]) if wiersz and wiersz[0] else {}
    except (TypeError, ValueError):
        return None
    if not isinstance(dane, dict) or dane.get("kind") != "needs_input":
        return None
    return str(dane.get("reason") or "").strip()


def przed_tura(session_id: str = "", turn_id: str = "", user_message: Any = None, **_kw: Any) -> Optional[dict]:
    """Hak `pre_llm_call`: budzenie o karcie z `needs_input` zapamiętuje turę i przypomina, że trzeba napisać do
    właściciela. Błąd = log, tura idzie dalej."""
    blokada = blokada_z_budzenia(user_message)
    if blokada is None or not session_id:
        return None
    karta, tytul, tablica = blokada
    try:
        from hermes_cli import kanban_db_connect as kbc
        with kbc.connect_closing(board=tablica) as conn:
            powod = powod_needs_input(conn, karta)
    except Exception as exc:  # noqa: BLE001 - przypomnienie nie może psuć tury
        logger.warning("cisza tablicy: nie odczytałem blokady %s: %r", karta, exc)
        return None
    if powod is None:
        return None
    with _ZAMEK:
        if len(_CZEKA) >= MAKS_CZEKA:
            _CZEKA.pop(next(iter(_CZEKA)))
        _CZEKA[session_id] = (str(turn_id), tytul, powod)
    return {"context": f"Zadanie „{tytul}” czeka na decyzję właściciela (needs_input): {powod or 'bez powodu'}. "
                       "Ta blokada nigdy nie kończy się [SILENT]: napisz właścicielowi jednym zdaniem, czego "
                       "potrzebujesz i gdzie to zrobić (skill decision-queue)."}


def _cisza(tekst: str) -> bool:
    try:
        from gateway.response_filters import is_autonomous_silence_response
        return bool(is_autonomous_silence_response(tekst))
    except Exception:  # noqa: BLE001 - bez Hermesa (testy): znacznik na początku, w pierwszej albo ostatniej linii
        linie = [x.strip().upper() for x in tekst.strip().splitlines() if x.strip()]
        return bool(linie) and (linie[0].startswith("[SILENT]") or linie[-1] == "[SILENT]")


def po_odpowiedzi(response_text: Any = None, session_id: str = "", turn_id: str = "", **_kw: Any) -> Optional[str]:
    """Hak `transform_llm_output`: w turze budzenia o karcie z `needs_input` odpowiedź-cisza staje się zdaniem dla
    właściciela (tytuł karty i powód blokady). Inna odpowiedź i inna tura: bez zmian (None)."""
    with _ZAMEK:
        czeka = _CZEKA.get(session_id)
        if czeka is None or czeka[0] != str(turn_id):
            return None
        _CZEKA.pop(session_id, None)
    if not isinstance(response_text, str) or not _cisza(response_text):
        return None
    _, tytul, powod = czeka
    return f"Zadanie „{tytul}” czeka na Ciebie: {powod}" if powod else f"Zadanie „{tytul}” czeka na Twoją decyzję."
