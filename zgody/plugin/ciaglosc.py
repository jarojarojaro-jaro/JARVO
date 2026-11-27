"""Zadanie nie kończy się w połowie na samym rozumowaniu modelu (wtyczka jarvo-zgody).

27.11 20:07 Command Code dał dwa błędy serwera, a ponowione wywołanie DeepSeek V4.1 Flash wróciło z samym
rozumowaniem (pusta treść, `finish_reason=stop`) w środku pracy: T1 (OLX na telefonie) po 56 wywołaniach i C1
(edytor HQ) po 42. Hermes (`agent/turn_final_response.py`, „Reasoning-only clean stop”) awansuje wtedy rozumowanie
na odpowiedź i kończy turę, więc właściciel nie dostaje ani wyniku, ani odpowiedzi (treść wiersza zostaje pusta).
Gdy ostatnie wiadomości to wyniki narzędzi, czyli agent jest w trakcie pracy, nie awansujemy rozumowania: tura
idzie drabiną pustej odpowiedzi Hermesa (`turn_empty_response.py`: jedno szturchnięcie „kontynuuj”, potem dwa
dopełnienia rozumowania), a dopiero gdy to nie pomoże, Hermes kończy jak dotąd. Odpowiedź bez narzędzi w tle
(zwykła rozmowa) działa bez zmian.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ZNACZNIK = "_jarvo_ciaglosc"
OSTATNIE = 5              # jak `_prior_was_tool` w turn_empty_response.py


def w_trakcie_pracy(messages: Any) -> bool:
    """Czy wśród ostatnich OSTATNIE wiadomości jest wynik narzędzia (agent pracuje, a nie odpowiada na pytanie)."""
    try:
        return any(isinstance(m, dict) and m.get("role") == "tool" for m in list(messages)[-OSTATNIE:])
    except TypeError:
        return False


def samo_rozumowanie(assistant_message: Any, finish_reason: Any) -> bool:
    tresc = getattr(assistant_message, "content", None)
    return (finish_reason == "stop" and not getattr(assistant_message, "tool_calls", None)
            and (tresc is None or (isinstance(tresc, str) and not tresc.strip())))


def owin(oryginal):
    """`finish_text_response` z Hermesa bez awansu rozumowania w trakcie pracy (na czas tego jednego wywołania)."""
    if getattr(oryginal, ZNACZNIK, False):
        return oryginal

    def finish_text_response(agent: Any, **kw: Any):
        if not (samo_rozumowanie(kw.get("assistant_message"), kw.get("finish_reason"))
                and w_trakcie_pracy(kw.get("messages"))):
            return oryginal(agent, **kw)
        logger.warning("jarvo-zgody: samo rozumowanie w trakcie pracy (%s wywołań): tura idzie dalej zamiast kończyć",
                       kw.get("api_call_count"))
        wyciag = agent.__dict__.get("_extract_reasoning")
        agent._extract_reasoning = lambda _m: None
        try:
            return oryginal(agent, **kw)
        finally:
            if wyciag is None:
                agent.__dict__.pop("_extract_reasoning", None)
            else:
                agent._extract_reasoning = wyciag

    setattr(finish_text_response, ZNACZNIK, True)
    return finish_text_response


def zarejestruj(_ctx: Any = None) -> bool:
    """Owija `agent.conversation_loop.finish_text_response` (pętla woła je po nazwie z modułu). False bez Hermesa."""
    try:
        from agent import conversation_loop
    except Exception:  # noqa: BLE001 - inna wersja Hermesa: zostaje jego zachowanie
        return False
    conversation_loop.finish_text_response = owin(conversation_loop.finish_text_response)
    return True
