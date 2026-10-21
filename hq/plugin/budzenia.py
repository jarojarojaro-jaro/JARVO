"""Wiersze budzenia kanbana w sesji członka wątku (docs/HQ.md „Rozmowy”): Hermes po zmianie karty utworzonej
w sesji api_server zaczyna turę w tej sesji wiadomością użytkownika według szablonu (po angielsku w każdym języku,
`/opt/hermes/locales/en.yaml`):

    [kanban] Task {task_id} {status}.
    Title: {title}
    Assignee: @{assignee}
    Board: {board}

    Check the result or decide the next step.

czasem z `Result: {summary}` (przekazanie) albo `Review feedback: {reason}` (ocena). Oś czasu pokazuje taki wiersz
jako kartę systemową „Karta „…” · Web · zakończona · Jarvo sprawdza”; wzmianek w nim nie szukamy. Nieznany status
zostaje po angielsku z tonem `info`. Czysty Python; testy: tests/test_budzenia.py.
"""

from __future__ import annotations

import re

WZOR = re.compile(r"^\[kanban\] Task (\S+) (.+?)\.\nTitle: (.*)\nAssignee: @(\S+)\nBoard: (\S+)", re.S)
WYNIK = re.compile(r"^Result: (.*)$", re.M)
UWAGI = re.compile(r"^Review feedback: (.*)$", re.M)
STATUSY = {
    "completed": ("zakończona", "ok"),
    "gave up (retries exhausted)": ("porzucona po próbach", "blad"),
    "crashed (worker exited); dispatcher will retry": ("pracownik padł, ponowi", "ostrzezenie"),
    "timed out; dispatcher will retry": ("przekroczony czas, ponowi", "ostrzezenie"),
    "blocked; needs attention": ("zablokowana, wymaga uwagi", "ostrzezenie"),
    "handed off for review; the implementation is done": ("oddana do oceny", "info"),
    "review requested changes (BLOCK); implementation is not approved": ("ocena: do poprawy", "ostrzezenie"),
    "routed to triage after repeated blocks; orchestration attention needed": ("do rozpisania po blokadach", "ostrzezenie"),
    "status changed": ("zmiana statusu", "info"),
}
STATUSY_EN = {
    "completed": "completed",
    "gave up (retries exhausted)": "gave up after retries",
    "crashed (worker exited); dispatcher will retry": "worker crashed, will retry",
    "timed out; dispatcher will retry": "timed out, will retry",
    "blocked; needs attention": "blocked, needs attention",
    "handed off for review; the implementation is done": "handed off for review",
    "review requested changes (BLOCK); implementation is not approved": "review: changes requested",
    "routed to triage after repeated blocks; orchestration attention needed": "routed to triage after blocks",
    "status changed": "status changed",
}


def czy_budzenie(tekst: str) -> bool:
    return bool(WZOR.match(str(tekst or "")))


def parsuj(tekst: str) -> dict | None:
    """{task_id, status, status_pl, status_en, ton, tytul, wykonawca, tablica, wynik?, uwagi?} albo None."""
    tekst = str(tekst or "")
    m = WZOR.match(tekst)
    if not m:
        return None
    task_id, status, tytul, wykonawca, tablica = m.groups()
    status_pl, ton = STATUSY.get(status, (status, "info"))
    out = {"task_id": task_id, "status": status, "status_pl": status_pl, "status_en": STATUSY_EN.get(status, status),
           "ton": ton, "tytul": tytul.strip(), "wykonawca": wykonawca, "tablica": tablica}
    w = WYNIK.search(tekst, m.end())
    if w:
        out["wynik"] = w.group(1).strip()
    u = UWAGI.search(tekst, m.end())
    if u:
        out["uwagi"] = u.group(1).strip()
    return out
