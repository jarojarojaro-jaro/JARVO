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


@pytest.mark.parametrize("przed, po", [
    ("Karta wróciła do oceny. Sprawdzam dowody.", "Zadanie wróciło do oceny. Sprawdzam dowody."),   # panel 26.11
    ("Zakładam kartę dla Wideografa, karta `t_e2666e55`.", "Zakładam zadanie dla Wideografa, zadanie `t_e2666e55`."),
    ("Nowa karta stoi.", "Nowe zadanie stoi."),
    ("Rozdane: 3 karty w toku, w kartach są dowody.", "Rozdane: 3 zadania w toku, w zadaniach są dowody."),
    ("Jak w karcie Hackera.", "Jak w zadaniu Hackera."),
    ("Karta graficzna Intela koduje, płacę kartą kredytową.", "Karta graficzna Intela koduje, płacę kartą kredytową."),
    ("Plik `karta.md` i https://x.pl/karta zostają.", "Plik `karta.md` i https://x.pl/karta zostają."),
])
def test_bez_karty(przed, po):
    assert st.bez_karty(przed) == po
