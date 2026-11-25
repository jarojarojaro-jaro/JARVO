"""Hacker: baza hackathonów (hackatony.py) na danych testowych, bez sieci."""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-hacker" / "scripts"))
import hackatony  # noqa: E402

TERAZ = dt.datetime(2026, 11, 25, 12, 0)


def jsonl(tmp_path: Path, *wpisy: dict, nazwa: str = "w.jsonl") -> str:
    p = tmp_path / nazwa
    p.write_text("\n".join(json.dumps(w, ensure_ascii=False) for w in wpisy) + "\n", encoding="utf-8")
    return str(p)


def wpis(**kw) -> dict:
    return {"nazwa": "Gemini Agents Challenge", "platforma": "Devpost", "url": "https://gemini.devpost.com",
            "zrodlo": "https://gemini.devpost.com/rules", "zgloszenie_do": "2026-11-27T17:00Z", "tryb": "online",
            "pula": 100000, "waluta": "USD", "tracki": ["agents", "multimodal"], "ai_kod": "tak", "solo": "tak",
            "sprawdzone": "2026-11-25", **kw}


def uruchom(tmp_path: Path, *argv: str) -> int:
    return hackatony.main(["--baza", str(tmp_path / "baza" / "h.db"), *argv], teraz=TERAZ)


def test_dodaj_bez_dubli_czas_utc_i_status_tylko_przez_status(tmp_path, capsys):
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis()))
    uruchom(tmp_path, "status", "gemini-agents-challenge", "budujemy", "plan gotowy")
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(pula=120000, status="nowy"), nazwa="b.jsonl"))
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {"nowe": 0, "zmienione": 1, "razem": 1}
    uruchom(tmp_path, "lista", "--json")
    (w,) = json.loads(capsys.readouterr().out)
    assert (w["pula"], w["status"], w["zgloszenie_do"], w["tracki"]) == (120000, "budujemy", "2026-11-27T17:00", "agents; multimodal")


@pytest.mark.parametrize("zly, blad", [
    ({"zrodlo": None}, "brak pól zrodlo"),
    ({"ai_kod": "chyba"}, "ai_kod „chyba”"),
    ({"zgloszenie_do": "piątek"}, "zgloszenie_do: „piątek”"),
    ({"url": "devpost.com"}, "url to nie link"),
])
def test_wpis_bez_zasad_albo_z_blednym_polem_odrzucony(tmp_path, zly, blad):
    with pytest.raises(SystemExit, match=blad):
        uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(**zly)))


def test_terminy_w_godzinach_utc_tylko_otwarte(tmp_path, capsys):
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(), wpis(nazwa="Kaggle Gemma", zgloszenie_do="2026-12-10"),
                                     wpis(nazwa="Minęło", zgloszenie_do="2026-11-25T08:00"), wpis(nazwa="Odpuszczony", zgloszenie_do="2026-11-30"),
                                     wpis(nazwa="Daleko", zgloszenie_do="2027-02-01")))
    uruchom(tmp_path, "status", "odpuszczony", "odpuszczony", "KYC")
    capsys.readouterr()
    uruchom(tmp_path, "terminy", "--dni", "20")
    linie = capsys.readouterr().out.splitlines()
    assert linie[0].startswith("2026-11-27T17:00 UTC (53 h)  Gemini Agents Challenge")
    assert linie[1].startswith("2026-12-10 UTC (15 dni)  Kaggle Gemma") and linie[-1] == "w oknie 20 dni: 2"


def test_ocena_z_powodem_i_eksport(tmp_path, capsys):
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(), wpis(nazwa="ETHGlobal Online", platforma="ETHGlobal", ai_kod="niejasne")))
    uruchom(tmp_path, "ocen", "gemini-agents-challenge", "8", "agenci to nasz rdzeń, solo, online")
    with pytest.raises(SystemExit, match="powód"):
        uruchom(tmp_path, "ocen", "ethglobal-online", "5", "")
    uruchom(tmp_path, "status", "ethglobal-online", "zgloszony")
    capsys.readouterr()
    uruchom(tmp_path, "eksport", str(tmp_path / "out"))
    md = (tmp_path / "out" / "HACKATONY.md").read_text(encoding="utf-8")
    assert "**2026-11-27T17:00 UTC** (53 h): [Gemini Agents Challenge]" in md
    assert "| [Gemini Agents Challenge](https://gemini.devpost.com) | Devpost | 100 000 USD |" in md
    assert "- ETHGlobal Online: **zgloszony**" in md
    assert len(list(csv.DictReader((tmp_path / "out" / "hackatony.csv").open(encoding="utf-8")))) == 2


def test_kalendarz_etapy_kamienie_i_ics(tmp_path, capsys):
    """25.11 właściciel: kalendarz trzyma wszystkie terminy: etapy otwartych hackathonów w miesiącach i tygodniach,
    nasze kamienie przy budowie i plik .ics do subskrypcji (linie najwyżej 75 bajtów)."""
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(rejestracja_do="2026-11-26T10:00", wyniki="2026-12-15"),
                                     wpis(nazwa="Odpuszczony", zgloszenie_do="2026-11-28"),
                                     wpis(nazwa="Daleki ze średnikiem; i przecinkiem, " + "x" * 80, zgloszenie_do="2027-01-20")))
    uruchom(tmp_path, "status", "gemini-agents-challenge", "budujemy")
    uruchom(tmp_path, "status", "odpuszczony", "odpuszczony")
    capsys.readouterr()
    uruchom(tmp_path, "kalendarz", str(tmp_path / "out"))
    md = (tmp_path / "out" / "KALENDARZ.md").read_text(encoding="utf-8")
    listopad = md.split("## Listopad 2026")[1].split("\n## ")[0]
    # 26.11 10:00 UTC = 11:00 w Warszawie; zamrożenie 8 h i gotowe 6 h przed zgłoszeniem 27.11 17:00 UTC
    assert [l.split(" · ")[1] for l in listopad.splitlines() if l.startswith("- ")] == \
        ["Rejestracja do", "Zamrożenie projektu", "Gotowe do wysłania", "Zgłoszenie do"]
    assert "**cz 26.11 11:00** (22 h)" in listopad and "Odpuszczony" not in md and "## Grudzień 2026" in md and "Wyniki" in md
    ics = (tmp_path / "out" / "hackatony.ics").read_bytes().decode()
    assert ics.count("BEGIN:VEVENT") == 6 and all(len(l.encode()) <= 75 for l in ics.split("\r\n"))
    assert "Daleki ze średnikiem\\; i przecinkiem\\," in ics.replace("\r\n ", "")
    assert "DTSTART:20261127T170000Z" in ics and "DTSTART;VALUE=DATE:20261215" in ics


def test_raport_do_wziecia_i_nasze_starty_migruje_stara_baze(tmp_path, capsys):
    """25.11 właściciel: raport mówi, który hackathon jest do wzięcia (najlepsza ocena, termin wejścia przed nami),
    a potem śledzi nasze starty; nie okna terminów."""
    import sqlite3
    baza = tmp_path / "baza" / "h.db"
    baza.parent.mkdir()
    stara = [p for p in hackatony.POLA if p != "wyniki"]       # baza sprzed pola `wyniki`
    c = sqlite3.connect(baza)
    c.execute(f"CREATE TABLE hackatony ({', '.join(stara)}, ocena INTEGER, dlaczego TEXT, dodane TEXT NOT NULL, "
              "zmienione TEXT NOT NULL, PRIMARY KEY (id))")
    c.commit()
    c.close()
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(nazwa="Daleki", zgloszenie_do="2027-02-01"),
                                     wpis(nazwa="Słaby", zgloszenie_do="2026-12-05"), wpis(nazwa="Minął", zgloszenie_do="2026-11-20"),
                                     wpis(nazwa="Nasz", zgloszenie_do="2026-12-10")))
    uruchom(tmp_path, "ocen", "daleki", "8", "agenci to nasz rdzeń")
    uruchom(tmp_path, "ocen", "slaby", "3", "web3 i KYC")
    uruchom(tmp_path, "ocen", "minal", "9", "za późno")
    uruchom(tmp_path, "status", "nasz", "budujemy")
    uruchom(tmp_path, "ustaw", "nasz", "krok=demo", "krok_do=2026-12-08")
    capsys.readouterr()
    uruchom(tmp_path, "raport")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Hackathony do wzięcia teraz (najlepsze z 2 otwartych):"
    assert out[1].startswith("1. [Daleki](https://gemini.devpost.com) · 100 000 USD · zgłoszenie do 2027-02-01 UTC (")
    assert out[1].endswith("ocena 8: agenci to nasz rdzeń · nowy") and out[2].startswith("2. [Słaby]")
    assert out[3] == "Nasze starty:" and "**budujemy**" in out[4] and "następny krok: demo do 2026-12-08 UTC" in out[4]
    assert "Minął" not in "\n".join(out)


def test_udzial_historia_i_notatka_w_mozgu(tmp_path, capsys, monkeypatch):
    """25.11 właściciel: wszystko śledzone (nasz udział, następny krok, historia każdej zmiany) i zapisywane w Mózgu,
    w notatce „kalendarz hackathonów” sekcji Hacker; notatka odświeża się po każdej zmianie bazy."""
    (tmp_path / "dane" / "knowledge" / "agenci").mkdir(parents=True)
    monkeypatch.setenv("JARVO_DATA_DIR", str(tmp_path / "dane"))
    monkeypatch.delenv("JARVO_KNOWLEDGE_DIR", raising=False)
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(), wpis(nazwa="Kaggle Gemma", zgloszenie_do="2026-12-10")))
    uruchom(tmp_path, "ocen", "kaggle-gemma", "7", "nasz kernel")
    uruchom(tmp_path, "status", "gemini-agents-challenge", "zapisani", "konto Devpost gotowe")
    uruchom(tmp_path, "ustaw", "gemini-agents-challenge", "konto=Devpost jaro", "krok=nagrać demo", "krok_do=2026-11-26T20:00")
    uruchom(tmp_path, "notuj", "gemini-agents-challenge", "mentor potwierdził track agents")
    with pytest.raises(SystemExit, match="pole z konto"):
        uruchom(tmp_path, "ustaw", "gemini-agents-challenge", "status=wygrany")
    capsys.readouterr()
    uruchom(tmp_path, "historia", "gemini-agents-challenge")
    hist = capsys.readouterr().out.splitlines()
    assert [l.split("  ")[2].split(":")[0] for l in hist[:-1]] == ["notatka", "udział", "status", "dodany"]
    assert "nowy → zapisani: konto Devpost gotowe" in hist[2] and hist[-1] == "wpisów w 30 dni: 4"
    uruchom(tmp_path, "lista", "--szukaj", "mentor", "--json")
    assert [w["id"] for w in json.loads(capsys.readouterr().out)] == ["gemini-agents-challenge"]
    md = (tmp_path / "dane" / "knowledge" / "agenci" / "jarvo-hacker" / "kalendarz hackathonów.md").read_text(encoding="utf-8")
    assert "status: generowane" in md and "sekcje: true" in md and "utworzono: 2026-11-25" in md
    sekcja = lambda n: md.split(f"## {n}\n")[1].split("\n## ")[0]            # noqa: E731
    assert "Nasz krok: nagrać demo" in sekcja("Terminy na 120 dni")
    assert "**zapisani** · zgłoszenie 2026-11-27T17:00 UTC · następny krok: nagrać demo do 2026-11-26T20:00 UTC · konto: Devpost jaro" in sekcja("Nasze starty")
    assert "Kaggle Gemma" in sekcja("Do wzięcia teraz") and "mentor potwierdził" in sekcja("Historia z 30 dni")
    assert "### Grudzień 2026" in sekcja("Terminy na 120 dni") and "[[agenci/jarvo-hacker/_hub-hacker|Hacker]]" in md
