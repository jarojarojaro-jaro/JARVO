"""ujecia.js: karty video-shotcraft przeniesione do kontraktu HTML jako czyste funkcje czasu. Liczby z kart
(klatki przy 30 kl./s, przestrzelenia, limity „raz na film”) sprawdzane w node."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from conftest import REPO, load_script

MODUL = REPO / "profiles/jarvo-wideo/scripts/ujecia.js"
KL = 1 / 30


def node(kod: str) -> dict:
    skrypt = f"import * as U from {json.dumps(MODUL.as_uri())};\n{kod}"
    wynik = subprocess.run(["node", "--input-type=module", "-e", skrypt], capture_output=True, text=True, encoding="utf-8")
    assert wynik.returncode == 0, wynik.stderr
    return json.loads(wynik.stdout)


pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="brak node")


def test_rozdanie_stos_wiersz():
    w = node("""
const r = [0, 4, 8, 12, 14].map(f => U.rozdanie(f / 30, 0));
const st = [0, 12, 34].map(f => U.stos(f / 30, 1));
const wi = [0, 12, 14, 30].map(f => U.wiersz(f / 30, 0));
console.log(JSON.stringify({ r, starty: [1, 2, 30].map(U.startRozdania), lot: Math.max(...Array.from({length: 9}, (_, f) => U.rozdanie(f / 30, 0).z)),
  st, docisk: [22, 26, 30].map(f => U.docisk(f / 30, 1)), pods: [U.podswietlenie(25 / 30, 0), U.podswietlenie(40 / 30, 0)],
  wi, zdarzen: [U.licznikZdarzen(0, [0, 1]), U.licznikZdarzen(2, [0, 1])], zap: U.zapowiedzRozdania(0.8, 1) }));
""")
    r = w["r"]
    assert r[0]["p"] == 0 and r[2]["p"] == pytest.approx(0.97) and r[4]["p"] == pytest.approx(1)   # 8 klatek lotu + 4 osiadania
    assert r[3]["skala"] == pytest.approx(0.996) and r[4]["wyladowala"] and not r[3]["wyladowala"]  # docisk 0,996 → 1
    assert w["lot"] == pytest.approx(90, abs=1) and r[1]["skala"] == pytest.approx(1.06, abs=0.001)  # łuk 90 px, skala 1,06 w szczycie
    assert w["starty"][0] == pytest.approx(4 * KL) and w["starty"][1] == pytest.approx((4 + 3.8416) * KL)
    assert w["starty"][2] < 30 * 4 * KL and w["starty"][2] > w["starty"][1]                     # talia przyspiesza, odstęp ≥ 0,2 kl.
    s0, s1, s2 = w["st"]
    assert s0["krycie"] == 0 and s1["krycie"] == 1 and s1["y"] == 600 and s1["obrot"] == -2      # druga karta po 12 kl., −2°
    assert s2["y"] == pytest.approx(0) and s2["obrot"] == pytest.approx(0) and s2["ladowanie"] == pytest.approx(34 * KL)
    assert w["docisk"][0] == 0 and w["docisk"][1] == pytest.approx(6) and w["docisk"][2] == 0   # 6 px w połowie 8 klatek
    assert w["pods"][0]["szer"] == 0 and w["pods"][1]["szer"] == pytest.approx(0.4) and w["pods"][1]["krycie"] == pytest.approx(0.5)
    wi = w["wi"]
    assert wi[0]["y"] == -120 and wi[0]["obrotX"] == 16 and wi[0]["latka"]
    assert wi[1]["skala"] == pytest.approx(0.995) and wi[2]["latka"] is False and wi[3]["skala"] == 1
    assert wi[3]["szew"]["szer"] == 1 and wi[3]["szew"]["krycie"] == pytest.approx(1 - 13 / 8 + 5 / 8, abs=0.01)
    assert w["zdarzen"] == [0, 2] and w["zap"]["wcisniecie"] > 30 and w["zap"]["cofniecie"] > 20


def test_pisanie_filtr_klik_tytul_licznik():
    w = node("""
const p = [0, 15, 33, 41, 45].map(f => U.pisanie(f / 30, 'chleb żytni'));
const k = U.klik(3 / 30, 0);
const t = U.tytulPapier(4 / 30, ['Chleb', 'prosto', 'z', 'pieca'], { akcent: 3 });
const t2 = U.tytulPapier(60 / 30, ['Chleb', 'prosto', 'z', 'pieca'], { akcent: 3 });
const L = (f) => U.licznikBebnowy(f / 30, '98,5%');
console.log(JSON.stringify({ p, filtr: [U.filtr(0.4 / 30, 1), U.filtr(5.4 / 30, 1)], slot: [U.doSlotu(0), U.doSlotu(5 / 30), U.doSlotu(1)],
  k, t: t.slowa, t2: [t2.kreska, t2.krycie, t2.slowa.map(s => s.krycie)], L: [L(20), L(36), L(42), L(80)], dlugi: U.licznikBebnowy(0, 1234567).uwaga }));
""")
    p = w["p"]
    assert p[1]["tekst"] == "chleb" and p[2]["tekst"] == "chleb żytni" and p[2]["koniec"] == pytest.approx(33 * KL)
    assert p[1]["kursor"] and p[3]["kursor"] is False and p[4]["kursor"] is False             # miga co 8 klatek po pisaniu
    assert p[0]["oddech"] == pytest.approx(44 * KL)                                           # 11 klatek oddechu przed filtrem
    assert w["filtr"][0]["krycie"] == 1 and w["filtr"][1] == {"krycie": 0, "y": 8}
    assert w["slot"][0]["p"] == 0 and w["slot"][1]["z"] == pytest.approx(18) and w["slot"][2]["p"] == 1
    assert w["k"][0]["r"] > 14 and w["k"][1]["r"] == pytest.approx(14) and w["k"][1]["krycie"] == 1  # drugi krąg 3 klatki później
    pierwsze = w["t"][0]
    assert pierwsze["skala"] == pytest.approx(1.28) and pierwsze["rozmycie"] == 7 and pierwsze["krycie"] == 0
    assert [s["akcent"] for s in w["t"]] == [False, False, False, True]
    assert w["t2"][0] == 1 and w["t2"][1] == 0 and w["t2"][2] == [1, 1, 1, 1]                  # kreska cała, karta zgasła
    l20, l36, l42, l80 = w["L"]
    assert [c["znak"] for c in l20["cyfry"]] == ["9", "8", ",", "5", "%"] and l20["cyfry"][0]["pos"] == 0
    assert l36["cyfry"][0]["pos"] == pytest.approx(19.5) and l36["cyfry"][0]["duchy"] is False   # przestrzelenie o pół wiersza
    assert l36["cyfry"][1]["duchy"] and not l36["cyfry"][2]["cyfra"]
    assert l42["cyfry"][0]["zablokowana"] and l42["cyfry"][0]["wiersz"] == 9
    assert [c.get("wiersz") for c in l80["cyfry"]] == [9, 8, None, 5, None]
    assert l80["koniec"] == pytest.approx((20 + 14 + 22 + 8) * KL) and l80["spokoj"] - l80["koniec"] == pytest.approx(45 * KL)
    assert l80["uwaga"] == "" and "7 cyfr" in w["dlugi"]


def test_ciecia_tempo_glebia_final_reflektor():
    w = node("""
const A = [48, 49, 50, 95, 130].map(f => U.przyspieszenie(f / 30));
const B = [29, 30, 34, 52, 70].map(f => U.flesz(f / 30));
const gr = [0, 4, 16, 18, 60].map(f => U.grupaElement(f / 30, 0));
const ka = U.kartaBohatera(0);
console.log(JSON.stringify({ A, B,
  mapa: [0, 40, 85, 135, 150].map(f => U.przemapuj(f / 30, U.ZWOLNIENIE) * 30),
  tempo: U.sprawdzTempo(U.ZWOLNIENIE), zle: U.sprawdzTempo([[0, 0], [1, 1], [1.5, 1.5], [2, 1.5]]),
  par: U.paralaksa(100), dolly: [U.dollyZoom(0), U.dollyZoom(3.5)], gr, litera: [U.grupaLitera(42 / 30, 0), U.grupaLitera(50 / 30, 0)],
  kam: [U.grupaKamera(0), U.grupaKamera(5)],
  ref: [U.reflektor(0, { cel: { x: 960, y: 540 }, start: { x: 0, y: 0 } }), U.reflektor(48 / 30, { cel: { x: 960, y: 540 } })],
  karta: [0, 10, 30, 64, 83, 86].map(f => U.kartaBohatera(f / 30)), kolko: [U.kolko(0, 0, 2), U.kolko(8 / 30, 0, 2), U.kolko(2, 0, 2)],
  limity: U.sprawdzUjecia(['flesz', 'flesz', 'przyspieszenie', 'dollyZoom', 'stop', 'stop', 'stop'], { dlugosc: 30 }),
  limityOk: U.sprawdzUjecia(['flesz', 'dollyZoom', 'stop', 'stop', 'stop', 'stop'], { dlugosc: 60 }),
  zaDuzo: (() => { try { U.paralaksa(1, [1, 2, 3, 4, 5].map(() => U.WARSTWY[0])); return ''; } catch (e) { return e.message; } })() }));
""")
    A = w["A"]
    assert A[0]["widok"] == 0 and A[1]["widok"] == 1 and A[1]["blysk"] == 1 and A[2]["blysk"] == 0   # błysk 1 klatkę
    assert A[3]["widok"] == 6 and A[4]["skala"] == pytest.approx(1.06) and A[0]["koniec"] == pytest.approx(130 * KL)
    B = w["B"]
    assert B[0]["widok"] == -1 and B[1]["biel"] == pytest.approx(0.95) and B[1]["skala"] == pytest.approx(1.03)
    assert B[1]["y"] == -16 and abs(B[1]["drgniecie"]) <= 2 and B[2]["biel"] == 0                 # biel znika w 4 klatki
    assert B[3]["przyblizenie"] == 2.3 and B[4]["przyblizenie"] == 4 and B[0]["koniec"] == pytest.approx(130 * KL)
    assert w["mapa"] == pytest.approx([0, 88, 97, 207, 240])
    assert w["tempo"] == [] and any("1,5 s" in u for u in w["zle"]) and any("10×" in u for u in w["zle"])
    assert [p["x"] for p in w["par"]] == pytest.approx([35, 70, 140]) and w["par"][0]["filtr"] == "blur(2px) saturate(0.92)"
    assert w["dolly"][0] == {"skalaTla": 1, "rozmycieTla": 0, "cien": 12} and w["dolly"][1] == {"skalaTla": 2.25, "rozmycieTla": 3.5, "cien": 28}
    g = w["gr"]
    assert g[0]["krycie"] == 0 and 360 <= (g[1]["x"] ** 2 + g[1]["y"] ** 2) ** 0.5 <= 500 and g[1]["skala"] == pytest.approx(1.12)
    assert g[3]["x"] == pytest.approx(0, abs=1e-6) and abs(g[3]["obrot"]) <= 5 and g[3]["poswiata"] == pytest.approx(0.35 * 2 / 3, abs=0.01)
    assert g[4]["krycie"] == pytest.approx(0.88) and g[4]["nasycenie"] == pytest.approx(0.92) and g[4]["poswiata"] == 0
    assert w["litera"][0]["krycie"] == 0 and w["litera"][1]["krycie"] == 1
    assert w["kam"][0]["obrotX"] == 4 and w["kam"][0]["skala"] == pytest.approx(1.06)
    assert w["kam"][1]["skala"] == pytest.approx(1.035) and w["kam"][1]["rozmycieTla"] == 14
    r0, r1 = w["ref"]
    assert r0["swiatlo"]["r"] == 620 and r0["winieta"] == pytest.approx(0.16) and not r0["stoi"]
    assert r1["stoi"] and r1["swiatlo"]["x"] == 960 and r1["swiatlo"]["r"] == pytest.approx(360 * 1.06) and r1["winieta"] == pytest.approx(0.42)
    k = w["karta"]
    assert k[0]["uniesienie"] == 0 and k[1]["uniesienie"] == pytest.approx(1) and k[2]["bob"] == pytest.approx(0, abs=1e-9)
    assert k[3]["bob"] == pytest.approx(0, abs=1e-9)                                           # unoszenie kończy się płynnie
    assert k[4]["uniesienie"] == 0 and 0.997 <= k[4]["skala"] < 1 and k[5]["skala"] == 1 and k[0]["koniec"] == pytest.approx(86 * KL)
    assert k[0]["obwodka"]["nr"] == 1 and k[2]["obwodka"] == {"nr": 2, "postep": 0.5, "krycie": 0.62}
    assert w["kolko"][0]["obrys"] == 1 and w["kolko"][1]["obrys"] == 0 and w["kolko"][2]["krycie"] == 0
    lim = " | ".join(w["limity"])
    assert "flesz 2×" in lim and "wybierz jeden" in lim and "stop-klatek 3, najwyżej 2" in lim and "dollyZoom" not in lim
    assert w["limityOk"] == [] and "najwyżej 4 warstwy" in w["zaDuzo"]


def test_cien_i_modul_pod_lib_jarvo():
    w = node("console.log(JSON.stringify([U.cien(0), U.cien(1), U.cien(2, '20,10,0')]));")
    assert w[0] == "0 2.0px 8.0px rgba(0,0,0,0.140)" and w[1] == "0 32.0px 64.0px rgba(0,0,0,0.240)" and w[2].endswith("rgba(20,10,0,0.240)")
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    assert "ujecia.js" in nz.JARVO_JS_PLIKI and "from './ruch.js'" in MODUL.read_text(encoding="utf-8")
    insp = load_script("profiles/jarvo-wideo/scripts/inspiracje.py")
    eksporty = MODUL.read_text(encoding="utf-8")
    for karta, opis in insp.NASZE.items():                                                     # każda nazwa funkcji istnieje
        if opis.startswith("ujecia.js"):
            for nazwa in opis.split(" (")[0].removeprefix("ujecia.js ").split(", "):
                assert f"export function {nazwa.removesuffix('()')}(" in eksporty, (karta, nazwa)
