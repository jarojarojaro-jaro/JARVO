"""Archiwum briefów w skarbcu (profiles/jarvo/scripts/briefy.py, decyzja właściciela 12.11): numery B-/T-, notatka
z tabelą decyzji z wyjścia rutyny Hermesa, otwarte decyzje do następnego briefu, powtórka zamyka starą pozycję."""

from __future__ import annotations

import datetime as dt

from conftest import load_script

briefy = load_script("profiles/jarvo/scripts/briefy.py", "jarvo_briefy_test")

BRIEF = """☀️ Brief {numer} · Dzień dobry. Stan floty:

**Gotowe od wczoraj:**
- Spacery: research gotowy.

**Czeka na Ciebie (3 decyzji):**
1. Spacery: pilot na 1 mieszkaniu? Rekomenduję tak.
2. Spacery: kupić telefon za 1064,99 zł? Rekomenduję wstrzymać
   do wyniku pilota.
3. Strona: cennik 649 | 849 zł? Rekomenduję tak.

Odpowiedz np. „1 ok, 2 nie”."""


def wyjscie(katalog, zadanie, czas, tresc):
    plik = katalog / zadanie / f"{czas:%Y-%m-%d_%H-%M-%S}.md"
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(f"# Cron Job: x\n\n## Prompt\n\n## Czeka na Ciebie (9 decyzji)\n1. z promptu\n\n## Response\n\n{tresc}\n",
                    encoding="utf-8")


def test_numery_briefu_i_przegladu():
    assert briefy.identyfikator("jarvo-daily-brief", dt.datetime(2026, 11, 12, 7, 51)) == "B-2026-11-12"
    assert briefy.identyfikator("jarvo-weekly-review", dt.datetime(2026, 11, 15, 18, 50)) == "T-2026-W46"
    assert briefy.identyfikator("jarvo-weekly-review", dt.datetime(2027, 1, 3, 18, 50)) == "T-2026-W53"   # tydzień ISO


def test_notatka_z_tabela_decyzji(tmp_path):
    k, out = tmp_path / "knowledge", tmp_path / "output"
    k.mkdir()
    wyjscie(out, "jarvo-daily-brief", dt.datetime(2026, 11, 12, 7, 51, 33), BRIEF.format(numer="B-2026-11-12"))
    wyjscie(out, "jarvo-daily-brief", dt.datetime(2026, 11, 11, 7, 50, 37), "")                    # skrypt nie obudził modelu
    wyjscie(out, "jarvo-weekly-review", dt.datetime(2026, 11, 15, 18, 50, 2), "[SILENT]")
    assert briefy.synchronizuj(k, out) == ["B-2026-11-12"]
    tekst = (k / "briefy" / "B-2026-11-12.md").read_text(encoding="utf-8")
    assert "numer: B-2026-11-12" in tekst and "# Poranny brief B-2026-11-12" in tekst and "3 decyzji czeka" in tekst
    assert "| B-2026-11-12/2 | Spacery: kupić telefon za 1064,99 zł? Rekomenduję wstrzymać do wyniku pilota. |  |  |  |" in tekst
    assert "| B-2026-11-12/3 | Strona: cennik 649 / 849 zł? Rekomenduję tak. |" in tekst        # „|” nie psuje tabeli
    assert "z promptu" not in tekst and (k / "briefy" / "_hub-briefy.md").exists()
    assert briefy.synchronizuj(k, out) == []                                                       # drugi raz nic


def test_otwarte_odpowiedzi_i_powtorka_zamyka_stara(tmp_path):
    k, out = tmp_path / "knowledge", tmp_path / "output"
    k.mkdir()
    wyjscie(out, "jarvo-daily-brief", dt.datetime(2026, 11, 12, 7, 51), BRIEF.format(numer="B-2026-11-12"))
    briefy.synchronizuj(k, out)
    plik = k / "briefy" / "B-2026-11-12.md"
    plik.write_text(plik.read_text(encoding="utf-8").replace(
        "| B-2026-11-12/1 | Spacery: pilot na 1 mieszkaniu? Rekomenduję tak. |  |  |  |",
        "| B-2026-11-12/1 | Spacery: pilot na 1 mieszkaniu? Rekomenduję tak. | ok | 2026-11-12 | karta t_1 |"), encoding="utf-8")
    dzis = dt.date(2026, 11, 13)
    assert [o["numer"] for o in briefy.otwarte(k, dzis)] == ["B-2026-11-12/2", "B-2026-11-12/3"]
    nowy = """☀️ Brief B-2026-11-13

**Czeka na Ciebie (2 decyzji):**
1. Spacery: kupić telefon? Rekomenduję wstrzymać. (z B-2026-11-12/2)
2. Nowa sprawa? Rekomenduję tak."""
    wyjscie(out, "jarvo-daily-brief", dt.datetime(2026, 11, 13, 7, 50), nowy)
    assert briefy.synchronizuj(k, out) == ["B-2026-11-13"]
    assert "| → B-2026-11-13/1 |" in plik.read_text(encoding="utf-8")
    assert [o["numer"] for o in briefy.otwarte(k, dzis)] == ["B-2026-11-12/3", "B-2026-11-13/1", "B-2026-11-13/2"]
    assert "poprzedni: [[briefy/B-2026-11-12]]" in (k / "briefy" / "B-2026-11-13.md").read_text(encoding="utf-8")
    assert briefy.tydzien(dzis, k) == [{"numer": "B-2026-11-12", "decyzje": 3, "z_odpowiedzia": 1, "przeniesione": 1},
                                       {"numer": "B-2026-11-13", "decyzje": 2, "z_odpowiedzia": 0, "przeniesione": 0}]
    assert briefy.otwarte(k, dt.date(2026, 12, 1)) == []                                           # po 14 dniach nie wraca
