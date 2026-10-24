"""Skrypty jarvo-ads: statystyka testów, planer mocy, eksport CSV, klient Skarbca bez Skarbca."""
import json
import os
import subprocess
import sys
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "profiles" / "jarvo-ads" / "scripts"
sys.path.insert(0, str(S))

import eksperyment  # noqa: E402
import eksport  # noqa: E402
import paczka  # noqa: E402
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
    env = {"SKARBIEC_URL": "http://127.0.0.1:9", "PATH": "/usr/bin:/bin"}
    if os.name == "nt":   # bez SYSTEMROOT Windows nie otworzy gniazda (WinError 10106) i test nie sprawdziłby połączenia
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    # -X utf8: w pustym środowisku na Windows stderr miałby stronę kodową ANSI („niepodłączony”)
    r = subprocess.run([sys.executable, "-X", "utf8", str(S / "ads.py"), "doctor"], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert r.returncode == 3 and "niepodłączony" in r.stderr and "10106" not in r.stderr, r.stderr


# ------------------------------------------------------------------ paczka do ręcznej publikacji

def _meta(tmp_path, **kampania):
    (tmp_path / "kreacje").mkdir(exist_ok=True)
    (tmp_path / "kreacje" / "film1.mp4").write_bytes(b"x")
    k = {"nazwa": "JARVO_meta_leady_261015", "cel": "OUTCOME_LEADS", "kategorie_specjalne": [],
         "budzet": {"typ": "dzienny", "kwota": 50}, "od": "2026-10-15", "do": "2026-10-28"}
    k.update(kampania)
    return {"platforma": "meta", "kampania": k,
            "zestawy": [{"nazwa": "szeroko_PL_auto", "odbiorcy": {"lokalizacje": ["Polska"], "wiek": [25, 55]}}],
            "reklamy": [{"nazwa": "T01_hook_9x16_v1", "zestaw": "szeroko_PL_auto", "pliki": ["kreacje/film1.mp4"],
                         "tekst": "Ile klientów ucieka Ci w nocy?", "naglowek": "Zespół AI dla firmy", "cta": "SIGN_UP",
                         "url": "https://jarvo.pl/start", "utm": {"utm_source": "meta", "utm_medium": "paid"}}]}


def test_paczka_budzet_ponad_zgode_i_bez_daty_konca(tmp_path):
    dzis = paczka.dt.date(2026, 10, 11)
    w, b, _ = paczka.sprawdz(_meta(tmp_path), tmp_path, 600, dzis)
    assert b["laczny"] == 700 and any("700.00" in e and "600.00" in e for e in w.bledy)
    w, _, _ = paczka.sprawdz(_meta(tmp_path), tmp_path, 700, dzis)
    assert not w.bledy
    w, _, _ = paczka.sprawdz(_meta(tmp_path, do=None), tmp_path, None, dzis)
    assert any("daty końca" in e for e in w.bledy)


def test_paczka_meta_bledy_tresci(tmp_path):
    spec = _meta(tmp_path)
    r = spec["reklamy"][0]
    r.update(url="http://jarvo.pl", cta="KUP", naglowek="", pliki=["kreacje/brak.mp4"], tekst="x" * 200)
    w, _, _ = paczka.sprawdz(spec, tmp_path, None, paczka.dt.date(2026, 10, 1))
    txt = " | ".join(w.bledy)
    for frag in ("https://", "CTA", "pusty `naglowek`", "brak pliku"):
        assert frag in txt, frag
    assert any("200 znaków" in u for u in w.uwagi)                     # długi tekst Meta: uwaga, nie błąd


def test_paczka_google_limity_twarde(tmp_path):
    spec = {"platforma": "google",
            "kampania": {"nazwa": "JARVO_google_leady_261015", "budzet": {"typ": "dzienny", "kwota": 40},
                         "od": "2026-10-15", "do": "2026-10-24"},
            "zestawy": [{"nazwa": "asystent", "slowa_kluczowe": ["[asystent ai]"],
                         "reklama": {"naglowki": ["Asystent AI dla firmy", "x" * 31], "opisy": ["Opis jeden.", "Opis jeden."],
                                     "url": "https://jarvo.pl"}}]}
    w, b, _ = paczka.sprawdz(spec, tmp_path, None, paczka.dt.date(2026, 10, 11))
    txt = " | ".join(w.bledy)
    assert "`naglowki`: 2" in txt and "31 znaków > 30" in txt and "`opisy` się powtarzają" in txt
    assert b["laczny"] == 400 and any("wykluczających" in u for u in w.uwagi)


def test_paczka_buduje_publikacje(tmp_path):
    (tmp_path / "kampania.json").write_text(json.dumps(_meta(tmp_path)), encoding="utf-8")
    out = tmp_path / "paczka"
    rc = paczka.main([str(tmp_path / "kampania.json"), "-o", str(out), "--limit", "700"])
    assert rc == 0
    md = (out / "PUBLIKACJA.md").read_text(encoding="utf-8")
    assert "**Kontakty** (Leads)" in md and "Budżet dzienny 50 PLN" in md and "2026-10-28" in md
    assert "**Opublikuj** (Publish)" in md and "- [ ] limit wydatków konta" in md
    teksty = (out / "teksty.md").read_text(encoding="utf-8")
    assert "https://jarvo.pl/start?utm_source=meta&utm_medium=paid" in teksty
    assert (out / "kreacje" / "T01_hook_9x16_v1.mp4").is_file()
    assert json.loads((out / "paczka.json").read_text(encoding="utf-8"))["budzet"]["laczny"] == 700
    assert paczka.main([str(tmp_path / "kampania.json"), "-o", str(tmp_path / "p2"), "--limit", "500"]) == 1
    assert not (tmp_path / "p2").exists()
