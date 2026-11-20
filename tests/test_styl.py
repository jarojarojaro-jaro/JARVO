"""wiedza/plugin/styl.py: odpowiedzi floty bez myślników (właściciel 20.11: „wypierdol pisanie double myślników…
AI slop… w briefie jest tego od groma”)."""
from __future__ import annotations

import pytest
from conftest import load_script

st = load_script("wiedza/plugin/styl.py", "jarvo_test_styl")


@pytest.mark.parametrize("przed, po", [
    ("Działa — sprawdzone przed chwilą.", "Działa: sprawdzone przed chwilą."),
    ("Status: Web — zrobione.", "Status: Web, zrobione."),
    ("Sherlock — po dwóch rundach — oddał raport.", "Sherlock, po dwóch rundach, oddał raport."),
    ("Monid -- ocena przed wydaniem $1.", "Monid: ocena przed wydaniem $1."),
    ("— punkt listy\n– drugi punkt", "- punkt listy\n- drugi punkt"),
    ("| misja | — |\n| x | – |", "| misja | - |\n| x | - |"),
    ("tak—nie", "tak, nie"),
    ("zakres 2–3 min, 13:46–15:01", "zakres 2–3 min, 13:46–15:01"),
    ("Na końcu —", "Na końcu"),
])
def test_bez_myslnikow(przed, po):
    assert st.bez_myslnikow(przed) == po


def test_kod_i_adresy_bez_zmian():
    tekst = ("Polecenie `ls -- -x` — działa.\n```\na — b\n```\nLink https://x.com/a—b — gotowe.")
    assert st.bez_myslnikow(tekst) == ("Polecenie `ls -- -x`: działa.\n```\na — b\n```\n"
                                        "Link https://x.com/a—b: gotowe.")


def test_brief_z_20_11_bez_myslnikow():
    wiersz = ("| Z-261118-monid | Monid: płatne API pod sygnały zakupowe (Reddit, LinkedIn, G2) — ocena przed wydaniem "
              "$1 (wpis @Jasperli0122) | zakończona |")
    wynik = st.bez_myslnikow(wiersz)
    assert "—" not in wynik and "(Reddit, LinkedIn, G2), ocena przed wydaniem $1" in wynik
