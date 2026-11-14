"""Cisza tablicy na czacie: o kartach mówi Jarvo, nie Hermes.

`kanban_create` z rozmowy (Telegram) subskrybuje czat w trybie `notify+wake` (Hermes, tools/kanban_tools.py:
`_resolve_notify_target`): przy każdym zdarzeniu karty Hermes wysyła na czat własny surowy komunikat
(„⏸ [default] @agent Kanban t_… blocked: …”, numery kart, ścieżki) **i** budzi Jarva, który pisze swoją
wiadomość. Właściciel dostawał dwie wiadomości o jednym zdarzeniu, w tym jedną w żargonie (14.11, InstaBox).

Hak `post_tool_call` po udanym `kanban_create` przełącza subskrypcje tej karty z `notify+wake` na `wake`:
Hermes nic nie wysyła, tylko budzi Jarva. `api_server` (czat HQ) zostaje bez zmian: tam wybudzenie JEST
dostarczeniem, a tryb ustawia sam Hermes.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# platformy, na których surowy komunikat Hermesa trafiłby do właściciela obok wiadomości Jarva
BEZ_SUROWYCH = ("telegram",)


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
