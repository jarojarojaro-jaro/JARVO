"""Bigshort: baza okazji finansowania (okazje.py) na danych testowych, bez sieci."""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-bigshort" / "scripts"))
import okazje  # noqa: E402

DZIS = dt.date(2026, 11, 25)


def jsonl(tmp_path: Path, *wpisy: dict, nazwa: str = "w.jsonl") -> str:
    p = tmp_path / nazwa
    p.write_text("\n".join(json.dumps(w, ensure_ascii=False) for w in wpisy) + "\n", encoding="utf-8")
    return str(p)


def wpis(**kw) -> dict:
    return {"nazwa": "Vercel X", "typ": "akcelerator", "url": "https://vercel.com/x", "zrodlo": "https://vercel.com/x",
            "kwota_max": 30000, "waluta": "USD", "equity": "0%", "termin": "2026-11-29", "sprawdzone": "2026-11-25", **kw}


def uruchom(tmp_path: Path, *argv: str) -> int:
    return okazje.main(["--baza", str(tmp_path / "baza" / "okazje.db"), *argv], dzis=DZIS)


def test_dodaj_bez_dubli_uzupelnia_i_nie_rusza_statusu(tmp_path, capsys):
    assert uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(), wpis(nazwa="Łódzki Grant", typ="grant", termin="rolling"))) == 0
    assert json.loads(capsys.readouterr().out) == {"nowe": 2, "zmienione": 0, "razem": 2}
    uruchom(tmp_path, "status", "vercel-x", "aplikujemy", "JARO chce")
    # to samo źródło drugi raz z nową kwotą i innym statusem: kwota się zmienia, status zostaje (zmienia go tylko `status`)
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(kwota_max=40000, status="nowa"), nazwa="b.jsonl"))
    assert json.loads(capsys.readouterr().out) == {"nowe": 0, "zmienione": 1, "razem": 2}
    uruchom(tmp_path, "lista", "--json")
    w = {x["id"]: x for x in json.loads(capsys.readouterr().out)}
    assert set(w) == {"vercel-x", "lodzki-grant"}
    assert (w["vercel-x"]["kwota_max"], w["vercel-x"]["status"]) == (40000, "aplikujemy")
    assert "2026-11-25 aplikujemy: JARO chce" in w["vercel-x"]["notatki"]


@pytest.mark.parametrize("zly, blad", [
    ({"zrodlo": None}, "brak pól zrodlo"),
    ({"typ": "darmowe"}, "typ „darmowe”"),
    ({"url": "vercel.com/x"}, "url to nie link"),
    ({"termin": "do końca roku"}, "termin: „do końca roku” to nie data"),
])
def test_wpis_bez_zrodla_albo_z_bledem_odrzucony(tmp_path, zly, blad):
    with pytest.raises(SystemExit, match=blad):
        uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(**zly)))


def test_terminy_tylko_otwarte_w_oknie_najblizsze_pierwsze(tmp_path, capsys):
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(), wpis(nazwa="INSEAD AI Founder Sprint", termin="2026-12-01"),
                                     wpis(nazwa="Po terminie", termin="2026-11-20"), wpis(nazwa="Daleko", termin="2027-03-01"),
                                     wpis(nazwa="Ciągły nabór", termin="rolling"), wpis(nazwa="Odrzucony", termin="2026-11-30")))
    uruchom(tmp_path, "status", "odrzucony", "nie-pasuje")
    capsys.readouterr()
    uruchom(tmp_path, "terminy", "--dni", "30")
    linie = capsys.readouterr().out.splitlines()
    assert [x.split("  ")[1] for x in linie[:-1]] == ["Vercel X", "INSEAD AI Founder Sprint"]
    assert linie[0].startswith("2026-11-29 (4 dni)") and linie[-1] == "w oknie 30 dni: 2"


def test_ocena_projektu_filtr_i_eksport_z_rankingiem(tmp_path, capsys):
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(), wpis(nazwa="NVIDIA Inception", typ="kredyty", termin="rolling", equity="0%")))
    uruchom(tmp_path, "ocen", "vercel-x", "Enigma Labz", "4", "front, nie inferencja")
    uruchom(tmp_path, "ocen", "nvidia-inception", "Enigma Labz", "9", "silnik inferencji na GPU NVIDIA")
    with pytest.raises(SystemExit, match="powód"):
        uruchom(tmp_path, "ocen", "vercel-x", "jarvo", "5", " ")
    capsys.readouterr()
    uruchom(tmp_path, "lista", "--projekt", "Enigma Labz", "--min-ocena", "7")
    assert capsys.readouterr().out.splitlines()[-1] == "razem: 1"
    uruchom(tmp_path, "eksport", str(tmp_path / "out"))
    md = (tmp_path / "out" / "OKAZJE.md").read_text(encoding="utf-8")
    assert "## Najlepiej pasuje: enigma-labz" in md
    ranking = [l for l in md.splitlines() if l.startswith("| [")]
    assert ranking[0].startswith("| [NVIDIA Inception]") and "| 9 |" in ranking[0]
    assert "**2026-11-29** (4 dni): [Vercel X]" in md
    wiersze = list(csv.DictReader((tmp_path / "out" / "okazje.csv").open(encoding="utf-8")))
    assert {w["id"]: w["ocena_enigma-labz"] for w in wiersze} == {"vercel-x": "4", "nvidia-inception": "9"}


def test_stare_wpisy_do_ponownego_sprawdzenia(tmp_path, capsys):
    uruchom(tmp_path, "dodaj", jsonl(tmp_path, wpis(sprawdzone="2026-08-01"), wpis(nazwa="Świeży"), wpis(nazwa="Zamknięty", sprawdzone="2026-01-01")))
    uruchom(tmp_path, "status", "zamkniety", "zamkniete")
    capsys.readouterr()
    uruchom(tmp_path, "stare", "--dni", "60")
    out = capsys.readouterr().out
    assert "vercel-x" in out and "swiezy" not in out and "zamkniety" not in out
