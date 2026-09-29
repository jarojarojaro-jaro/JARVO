"""Skrypty jarvo-ads: statystyka testów, planer mocy, eksport CSV, klient Skarbca bez Skarbca."""
import json
import subprocess
import sys
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "profiles" / "jarvo-ads" / "scripts"
sys.path.insert(0, str(S))

import eksperyment  # noqa: E402
import eksport  # noqa: E402
import planer  # noqa: E402


def test_winner_clear():
    r = eksperyment.policz({"metryka": "hook", "dni": 5, "warianty": [
        {"nazwa": "A", "obejrzenia3s": 250, "wyswietlenia": 1500},
        {"nazwa": "B", "obejrzenia3s": 480, "wyswietlenia": 1500}]})
    assert r["stan"] == "zwyciezca" and r["lider"] == "B" and "A" in r["do_wylaczenia"]


def test_tie_and_too_early():
    war = [{"nazwa": "A", "klikniecia": 15, "wyswietlenia": 1500}, {"nazwa": "B", "klikniecia": 16, "wyswietlenia": 1500}]
    assert eksperyment.policz({"metryka": "ctr", "dni": 7, "warianty": war})["stan"] == "remis"
    assert eksperyment.policz({"metryka": "ctr", "dni": 2, "warianty": war})["stan"] == "za_wczesnie"


def test_cpa_burn_rule_and_determinism():
    d = {"metryka": "cpa", "dni": 5, "cel_cpa": 30, "warianty": [
        {"nazwa": "A", "konwersje": 0, "wydatek": 70}, {"nazwa": "B", "konwersje": 4, "wydatek": 70}]}
    r1, r2 = eksperyment.policz(d), eksperyment.policz(d)
    assert "A" in r1["do_wylaczenia"] and r1 == r2


def test_planer_ladder():
    ns = lambda **k: type("N", (), {**dict(cpm=20.0, ctr=None, cpa=None, bazowa=None, roznica=0.2), **k})()
    hook = planer.test(ns(metryka="hook", warianty=5, budzet_dzienny=100, dni=7, bazowa=0.25))
    cpa = planer.test(ns(metryka="cpa", warianty=4, budzet_dzienny=30, dni=5, cpa=40))
    assert hook["wykonalny"] and not cpa["wykonalny"] and cpa["rekomendacje"]


def test_export_meta_pl(tmp_path):
    f = tmp_path / "m.csv"
    f.write_text("Nazwa reklamy,Wydana kwota (PLN),Wyświetlenia,Kliknięcia linku,Wyniki,3-sekundowe odtworzenia filmu\n"
                 "T01_a,\"1 234,50\",10000,120,6,2500\nT01_b,99.5,8000,--,0,1200\n", encoding="utf-8")
    rows, mapa = eksport.czytaj(f.read_text(encoding="utf-8"))
    assert rows[0]["wydatek"] == 1234.5 and rows[1]["klikniecia"] == 0 and rows[0]["obejrzenia3s"] == 2500
    assert {"wydatek", "wyswietlenia", "klikniecia", "konwersje"} <= set(mapa)


def test_export_google_title_rows(tmp_path):
    f = tmp_path / "g.csv"
    f.write_text("Raport reklam\n\"1 wrz 2026 - 29 wrz 2026\"\nAd group,Impr.,Clicks,Cost,Conversions\n"
                 "Grupa A,5000,100,250.00,5.00\nTotal: Account,5000,100,250.00,5.00\n", encoding="utf-8")
    rows, _ = eksport.czytaj(f.read_text(encoding="utf-8"))
    assert len(rows) == 1 and rows[0]["konwersje"] == 5


def test_ads_client_without_skarbiec():
    r = subprocess.run([sys.executable, str(S / "ads.py"), "doctor"], capture_output=True, text=True,
                       env={"SKARBIEC_URL": "http://127.0.0.1:9", "PATH": "/usr/bin:/bin"})
    assert r.returncode == 3 and "niepodłączony" in r.stderr
