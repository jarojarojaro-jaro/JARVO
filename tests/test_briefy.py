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


# 23.11: właściciel odpowiedział na brief B-2026-11-20 w panelu, Jarvo nie wpisał odpowiedzi do tabeli, a briefy 21–23.11
# pytały o te same sprawy innymi słowami (bez „(z …)”). Odpowiedź zapisuje kod, a brief nie pyta o sprawy ustalone.
BRIEF_20 = """☀️ Brief B-2026-11-20 · Dzień dobry. Stan floty:
Czeka na Ciebie (5 decyzji):
1. Monid: poprosić ich o wynik testowy, a ICP.yaml dla jarodev.pl zrobić osobną kartą? Rekomenduję tak. (z B-2026-11-18/4 i /5)
2. Jarodev: przydzielić telefon „second” i włączyć rutynę dnia? Rekomenduję tak, bez tego lejek nie ruszy.
3. Ankiety: wysłać gotową prośbę do OneFormy o zgodę Project Ownera? Rekomenduję tak, to jedyna legalna droga.
4. 🛠 Pomijać zdublowane linki: wczoraj ten sam link context.dev przyszedł dwa razy w minutę, każde powtórzenie to drugi pełny research. Rekomenduję tak, tanie.
5. AssemblyAI: zapisać 3 klucze do `konfig/assemblyai-konta/`? Rekomenduję tak, bo inaczej $150 kredytów leży bezużyteczne.
Odpowiedz np. „1 ok, 2 nie”."""

BRIEF_23 = """☀️ Brief B-2026-11-23 · Dzień dobry. Stan floty:
Czeka na Ciebie (4 decyzji):
1. Monid: nie zakładać konta za $1, poprosić o wynik testowy mailem, ICP.yaml zrobić osobno? Wisi 5 dni. (z B-2026-11-18/4)
2. 🛠 Pomijać zdublowane linki: ten sam link przyszedł dwa razy w minutę, a każde powtórzenie to drugi research. Wisi 4 dni.
3. Szukać zamiennika wyszukiwarki przed 1.01.2027, bo Google zamyka Custom Search API? Rekomenduję tak.
4. AssemblyAI: zapisać 3 klucze w `konfig/assemblyai-konta/`? Rekomenduję tak, bez tego $150 kredytów leży bezużyteczne.
Dziś w planie: patrol co 30 min.
Odpowiedz np. „1 ok, 2 nie”."""


def test_odpowiedz_na_brief_zapisuje_kod_i_brief_nie_pyta_o_ustalone(tmp_path):
    k, out = tmp_path / "knowledge", tmp_path / "output"
    k.mkdir()
    wyjscie(out, "jarvo-daily-brief", dt.datetime(2026, 11, 20, 7, 51), BRIEF_20)
    briefy.synchronizuj(k, out)
    odp = ("> Odpowiadam na raport „Poranny brief” (07:51): ☀️ Brief B-2026-11-20 · Dzień dobry. Stan floty:\n\n"
           "1 - na monid trzeba zalozyc konta i skorzystac z ich free creditow\nJarodev jeszcze nie, ale pamiętać\n"
           "4 pomijac zdublowane linki - dawac znac ze byl juz research\n5 tak assembly ai zapisac oczyiwscie")
    numer, przypisane, puste = briefy.odpowiedz_z_wiadomosci(odp, "", k, dt.datetime(2026, 11, 20, 14, 21))
    assert numer == "B-2026-11-20" and puste == ["B-2026-11-20/3"]
    assert przypisane == {"B-2026-11-20/1": "1 na monid trzeba zalozyc konta i skorzystac z ich free creditow",
                          "B-2026-11-20/4": "4 pomijac zdublowane linki - dawac znac ze byl juz research",
                          "B-2026-11-20/5": "5 tak assembly ai zapisac oczyiwscie",
                          "B-2026-11-20/2": "Jarodev jeszcze nie, ale pamiętać"}
    notatka = (k / "briefy" / "B-2026-11-20.md").read_text(encoding="utf-8")
    assert "| „5 tak assembly ai zapisac oczyiwscie” (20.11 14:21) | 2026-11-20 |" in notatka
    assert "## Odpowiedzi właściciela" in notatka and "- 2026-11-20 14:21: „1 - na monid" in notatka   # surowo, nic nie ginie
    # brief 23.11 pyta o te same sprawy innymi słowami: zostaje tylko nowa, przenumerowana, z poprawną liczbą
    tekst, wyciete = briefy.filtruj_brief(BRIEF_23, k, dt.date(2026, 11, 23))
    assert [w["ustalona"]["numer"] for w in wyciete] == ["B-2026-11-20/1", "B-2026-11-20/4", "B-2026-11-20/5"]
    assert "Czeka na Ciebie (1 decyzja):\n1. Szukać zamiennika wyszukiwarki" in tekst
    assert "AssemblyAI" not in tekst and "zdublowane" not in tekst and "Dziś w planie: patrol" in tekst
    assert [o["numer"] for o in briefy.otwarte(k, dt.date(2026, 11, 23))] == ["B-2026-11-20/3"]


def test_odpowiedz_tylko_na_brief(tmp_path):
    k, out = tmp_path / "knowledge", tmp_path / "output"
    k.mkdir()
    wyjscie(out, "jarvo-daily-brief", dt.datetime(2026, 11, 20, 7, 51), BRIEF_20)
    briefy.synchronizuj(k, out)
    # zwykła wiadomość, raport innej rutyny i prompt rutyny z numerami decyzji: nic nie zapisane
    assert briefy.odpowiedz_z_wiadomosci("1 rzecz: zrób stronę", "", k) is None
    assert briefy.odpowiedz_z_wiadomosci("> Odpowiadam na raport „Patrol floty” (09:00): ok\n\n1 ok", "", k) is None
    assert briefy.odpowiedz_z_wiadomosci("Dane: otwarte B-2026-11-20/3 (3 dni)", "", k) is None
    # Telegram: odpowiedź na wiadomość z briefem; po czasie numerem pozycji; „1.01.2027” to nie pozycja
    tg = f'[Replying to your previous message: "{BRIEF_20}"]\n\n3 nie, przed 1.01.2027 wrócimy'
    assert briefy.odpowiedz_z_wiadomosci(tg, "", k)[1] == {"B-2026-11-20/3": "3 nie, przed 1.01.2027 wrócimy"}
    assert briefy.odpowiedz_z_wiadomosci("B-2026-11-20/2 tak", "", k)[1] == {"B-2026-11-20/2": "2 tak"}
    assert briefy.odpowiedz_z_wiadomosci("1 ok, 5 nie", "☀️ Brief B-2026-11-20 · Dzień dobry", k)[1] == {
        "B-2026-11-20/1": "1 ok", "B-2026-11-20/5": "5 nie"}
