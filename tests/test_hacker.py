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
