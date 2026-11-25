"""Hacker: codzienne agregatory radaru (agregatory.py) na danych testowych, bez sieci."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "profiles" / "jarvo-hacker" / "scripts"))
import hackatony  # noqa: E402
import agregatory  # noqa: E402

DZIS = dt.date(2026, 11, 25)


@pytest.mark.parametrize("tekst, usd", [
    ("€25,000.00", 27000),
    ("$400k", 400000),
    ("US$4,500 cash (1st $2,500 + M6 Mac Mini; 2nd $1,250)", 4500),
    ("200,000 USDT for apps on Pi", 200000),
    ("$1.5M in prizes", 1500000),
    ("See official page https://lu.ma/293mlhh9", None),
    ("Prizes: See official page", None),
])
def test_pula_w_usd_z_tekstu_agregatora(tekst, usd):
    assert agregatory.pula_usd(tekst) == usd


@pytest.mark.parametrize("tekst, dzien", [
    ("25 Nov 2026", "2026-11-25"),
    ("In person Prizes: $5,000. Closes Dec 7, 2026.", "2026-12-07"),
    ("2026-11-24 — 2026-11-29", "2026-11-29"),
    ("Varies", None),
])
def test_termin_z_tekstu_agregatora(tekst, dzien):
    assert agregatory.data(tekst) == dzien


def karta(href: str, typ: str, tytul: str, kwota: str, termin: str, opis: str) -> str:
    return (f'<a class="card" href="{href}" data-type="{typ}" data-industries="ai"><div class="card__body">'
            f'<h3 class="card__title">{tytul}</h3><p class="card__summary">{opis}</p><div class="card__facts">'
            f'<div class="fact"><span class="fact__label">Amount</span><span class="fact__value">{kwota}</span></div>'
            f'<div class="fact"><span class="fact__label">Deadline</span><span class="fact__value">{termin}</span></div>'
            f'</div></div></a>')


DGD = "".join([
    karta("/items/a/", "hackathon", "Pi Next Hackathon 2026: 200,000 USDT for apps on Pi", "200,000 USDT", "5 Jan 2027",
          "Online hackathon for AI agent apps."),
    karta("/items/b/", "hackathon", "Smart Buildings Competition 2026 on Kaggle", "$40,000", "15 Jan 2027", "Online, AI for HVAC."),
    karta("/items/c/", "hackathon", "Old Jam 2026", "$9,000", "1 Nov 2026", "Online."),
    karta("/items/d/", "grant", "Some Grant", "$50k", "1 Dec 2026", "Online."),
    karta("/items/e/", "bounty", "Acme bug bounty on Immunefi", "$100k", "31 Dec 2026", "Online program."),
])
HACKLIST = json.dumps({"generated_at": "2026-11-25T08:00:00Z", "items": [
    {"type": "hackathon", "title": "Pi Next Hackathon", "prize": "$200,000", "deadline": "2027-01-05", "format": "Online",
     "apply_url": "https://minepi.com/pi-next", "category": "AI", "description": "Build apps with agents"},
    {"type": "hackathon", "title": "Berlin AI Night", "prize": "€10,000", "deadline": "2026-12-01", "format": "In-person (Berlin)",
     "apply_url": "https://example.com/berlin", "category": "AI", "description": ""},
    {"type": "job", "title": "Engineer", "prize": "", "deadline": "2026-12-01", "format": "Online", "apply_url": "x"},
]})
RSS = ("<rss><channel><item><title><![CDATA[Agents League]]></title><link>https://jams.example/agents/</link>"
       "<description>Online Prizes: $12,000. Closes Dec 10, 2026.</description></item></channel></rss>")


def uruchom(tmp_path: Path, odpowiedzi: dict[str, str], wolania: list[str] | None = None) -> dict:
    baza = tmp_path / "baza" / "h.db"
    (tmp_path / "w.jsonl").write_text(json.dumps({
        "nazwa": "Smart Buildings Competition (NeurIPS 2026)", "platforma": "Kaggle",
        "url": "https://www.kaggle.com/competitions/neurips-2026-smart-buildings", "zrodlo": "https://kaggle.com/rules",
        "zgloszenie_do": "2027-01-15"}) + "\n", encoding="utf-8")
    hackatony.main(["--baza", str(baza), "dodaj", str(tmp_path / "w.jsonl")], teraz=dt.datetime(2026, 11, 25, 8))

    def pobieracz(url: str) -> str:
        (wolania if wolania is not None else []).append(url)
        for klucz, tresc in odpowiedzi.items():
            if klucz in url:
                if isinstance(tresc, Exception):
                    raise tresc
                return tresc
        raise OSError("brak odpowiedzi")

    assert agregatory.main(["--baza", str(baza), "--katalog", str(tmp_path / "out")], dzis=DZIS, pobieracz=pobieracz) == 0
    return json.loads((tmp_path / "out" / "zrodla.json").read_text(encoding="utf-8"))


def test_jedna_okazja_z_kilku_zrodel_bez_bazy_stacjonarnych_i_przeszlych(tmp_path):
    d = uruchom(tmp_path, {"devgrantsdaily": DGD, "hacklist": HACKLIST, "shippedby": RSS})
    nazwy = [p["nazwa"] for p in d["konkursy"]]
    assert nazwy == ["Pi Next Hackathon 2026: 200,000 USDT for apps on Pi", "Agents League"]   # od największej puli
    pi = d["konkursy"][0]
    assert pi["zrodla"] == ["DevGrants Daily", "HackList"] and pi["termin"] == "2027-01-05" and pi["ai"]
    smart = next(p for p in d["wszystkie"] if p["nazwa"].startswith("Smart Buildings"))
    assert smart["w_bazie"] == "smart-buildings-competition-neurips-2026"                      # już w bazie: nie do sprawdzenia
    assert not any("Old Jam" in p["nazwa"] or "Grant" in p["nazwa"] for p in d["wszystkie"])  # po terminie, granty to Bigshort
    assert [p["nazwa"] for p in d["bounty"]] == ["Acme bug bounty on Immunefi"]               # bounty osobno
    md = (tmp_path / "out" / "ZRODLA.md").read_text(encoding="utf-8")
    assert "2 hackathonów i konkursów, z nich o AI 2; do tego 1 stałych programów bounty" in md
    assert "Berlin AI Night" not in md.split("## Źródła")[0]                                    # na miejscu: poza listą


def test_padniete_zrodlo_widac_w_raporcie_a_odczyt_raz_dziennie(tmp_path):
    wolania: list[str] = []
    d = uruchom(tmp_path, {"devgrantsdaily": DGD, "hacklist": OSError("HTTP 503")}, wolania)
    assert d["zrodla"]["HackList"].startswith("błąd: OSError") and d["zrodla"]["DevGrants Daily"] == "4"
    przed = len(wolania)
    uruchom(tmp_path, {"devgrantsdaily": DGD, "hacklist": HACKLIST}, wolania)
    assert not any("devgrantsdaily" in u for u in wolania[przed:])                             # kopia z dziś, bez drugiego odczytu
    assert any("hacklist" in u for u in wolania[przed:])                                      # padnięte źródło próbuje znowu
