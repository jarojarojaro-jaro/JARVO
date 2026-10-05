"""strona.js: kamera po zrzucie strony (assety.py --film). Przewijanie z postojami, wycieczka do 4 punktów, najazd,
lupa, uderzenie, zakreślacz i kontrola planu ruchów; liczone w node na układzie jak z assety.py."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from conftest import REPO, load_script

MODUL = REPO / "profiles/jarvo-wideo/scripts/strona.js"
UKLAD = {"url": "http://127.0.0.1:8765/", "strony": {"start": {
    "adres": "http://127.0.0.1:8765/",
    "desktop": {"szer": 1920, "dpr": 2, "wys": 2561, "wys_pelna": 2561,
                "kafle": [{"plik": "start-desktop-1.png", "y": 0, "h": 2561}],
                "pusta": [{"plik": "start-desktop-pusta-1.png", "y": 0, "h": 2561}],
                "cele": [{"id": "naglowek-1", "typ": "naglowek", "poziom": 1, "tekst": "Chleb", "x": 390, "y": 240, "w": 568, "h": 276,
                          "wycinek": "start-desktop-naglowek-1.png"},
                         {"id": "przycisk-2", "typ": "przycisk", "tekst": "Zamów", "x": 390, "y": 671, "w": 202, "h": 55},
                         {"id": "cena-2", "typ": "cena", "tekst": "18 zł", "x": 816, "y": 1647, "w": 287, "h": 40},
                         {"id": "karta-4", "typ": "karta", "tekst": "Pszenny", "x": 414, "y": 1368, "w": 345, "h": 419},
                         {"id": "formularz-1", "typ": "formularz", "tekst": "Imię", "x": 988, "y": 1971, "w": 542, "h": 374},
                         {"id": "zly", "typ": "wlasny", "brak": "selektor '.x' nic nie znalazł"}]},
    "telefon": {"brak": "timeout"}}}}


def node(kod: str) -> dict:
    skrypt = f"import * as S from {json.dumps(str(MODUL))};\nconst uklad = {json.dumps(UKLAD)};\n{kod}"
    wynik = subprocess.run(["node", "--input-type=module", "-e", skrypt], capture_output=True, text=True)
    assert wynik.returncode == 0, wynik.stderr
    return json.loads(wynik.stdout)


pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="brak node")


def test_strona_z_ukladu_i_bledy():
    w = node("""
const st = S.stronaZUkladu(uklad, { katalog: 'assets/film/' });
const bledy = [];
for (const f of [() => S.stronaZUkladu(uklad, { strona: 'cennik' }), () => S.stronaZUkladu(uklad, { widok: 'telefon' }),
                 () => st.cel('zly'), () => S.przewijanie({ strona: st }),
                 () => S.wycieczka({ strona: st, punkty: ['cena-2', 'cena-2', 'cena-2', 'cena-2', 'cena-2'] })])
  try { f(); bledy.push(''); } catch (e) { bledy.push(e.message); }
console.log(JSON.stringify({ srodek: st.srodek('cena-2'), fit: S.dopasuj(st, [1080, 1920]), bledy,
  brzeg: S.ogranicz({ x: 100, y: 5000, zoom: 2 }, st, [1920, 1080]), kadr: S.wKadrze({ x: 960, y: 1667, zoom: 2 }, { x: 1060, y: 1667 }, [1920, 1080]) }));
""")
    assert w["srodek"] == {"x": 959.5, "y": 1667} and w["fit"] == pytest.approx(0.5625)
    assert "brak strony „cennik”" in w["bledy"][0] and "nie ma widoku „telefon” (timeout)" in w["bledy"][1]
    assert "nieznany cel „zly”" in w["bledy"][2] and "naglowek-1" in w["bledy"][2]   # cel z „brak” nie istnieje
    assert "przystanki" in w["bledy"][3] and "najwyżej 4 punkty" in w["bledy"][4]
    assert w["brzeg"] == {"x": 480, "y": 2561 - 270, "zoom": 2}                         # kamera nie wyjeżdża poza stronę
    assert w["kadr"] == {"x": 1160, "y": 540}


def test_przewijanie_postoje_hamowanie_i_tempo():
    w = node("""
const st = S.stronaZUkladu(uklad);
const p = S.przewijanie({ strona: st, od: 0.5, przystanki: ['karta-4', 'formularz-1'], kadr: [1920, 1080] });
const y = []; for (let t = 0; t <= p.do + 0.5; t += 0.05) y.push(p(t).y);
const tr = S.trapez(100, 4, 0.6, 1.4);
console.log(JSON.stringify({ od: p.od, do: p.do, chwile: p.chwile, typ: p.typ, y, start: p(0), postoj: p(p.chwile[0].od + 0.7),
  koniec: p(p.do + 1), tr: [tr(0), tr(0.6), tr(2), tr(4), tr(9)], krotki: S.trapez(10, 1, 0.6, 1.4)(1) }));
""")
    assert w["typ"] == "przewijanie" and w["start"]["y"] == 540 and w["start"]["faza"] == "start"
    c0, c1 = w["chwile"]
    assert c0["do"] - c0["od"] == pytest.approx(1.5) and c1["do"] == pytest.approx(w["do"])
    assert w["postoj"]["y"] == pytest.approx(1577.5) and w["postoj"]["faza"] == "postoj"     # środek karty na środku kadru
    assert w["koniec"]["y"] == pytest.approx(2561 - 540) and w["koniec"]["faza"] == "koniec"  # formularz przy dole: do brzegu
    y = w["y"]
    assert all(b >= a - 1e-9 for a, b in zip(y, y[1:]))                                         # tylko w dół
    v = max(b - a for a, b in zip(y, y[1:])) / 0.05
    assert v == pytest.approx(0.10 * 2561, rel=0.02)                                          # ~10% wysokości strony na sekundę
    assert w["tr"][0] == 0 and w["tr"][3] == 100 and w["tr"][4] == 100 and 0 < w["tr"][1] < w["tr"][2] < 100
    assert w["krotki"] == 10


def test_wycieczka_najazd_lupa_uderzenie_zakreslacz():
    w = node("""
const st = S.stronaZUkladu(uklad);
const K = [1920, 1080];
const wy = S.wycieczka({ strona: st, od: 1, punkty: [{ cel: 'przycisk-2', przyblizenie: 1.5 }, { cel: 'cena-2', przyblizenie: 1.8 }],
                         start: 'calosc', nachylenie: true, kadr: K });
const n = S.najazd({ strona: st, od: 0, do: 4, kadr: K });
const l = S.lupa({ strona: st, cel: 'cena-2', od: 2, do: 4, kadr: K });
const kam = { x: 960, y: 1667, zoom: 1 };
const u = S.uderzenie({ strona: st, cel: 'naglowek-1', od: 1, baza: kam, kadr: K });
const z = S.zakreslacz({ strona: st, cel: 'cena-2', od: 1 });
console.log(JSON.stringify({ wy: [wy(0), wy(1.5), wy(3.6), wy(wy.do), wy(2.6)], wyDo: wy.do, wyMax: wy.maxZoom, chwile: wy.chwile,
  n: [n(0).zoom, n(2).zoom, n(4).zoom], l: [l(1.9, kam), l(2.15, kam), l(3, kam), l(4, kam)],
  u: [u(0.9).zoom, u(1 + 6 / 30).zoom, u(1 + 6 / 30)], uDo: u.do, z: [z(0.9).u, z(1.3), z(2).u] }));
""")
    wy = w["wy"]
    assert wy[0]["zoom"] == 1 and wy[1]["zoom"] == 1 and wy[1]["y"] == pytest.approx(698.5)  # cała szerokość, wysokość celu
    assert wy[2]["zoom"] == pytest.approx(1.5) and wy[2]["x"] == pytest.approx(640)            # przy lewym brzegu: do granicy
    assert wy[3]["zoom"] == pytest.approx(1.8) and wy[3]["x"] == pytest.approx(959.5) and wy[3]["y"] == pytest.approx(1667)
    assert wy[0]["rotX"] == 0 and wy[4]["rotX"] > 5 and wy[4]["rotY"] < -5                    # nachylenie tylko w przejeździe
    assert w["wyDo"] == pytest.approx(1 + 2 * 2.15 + 1) and w["wyMax"] == pytest.approx(1.8)
    assert [c["od"] for c in w["chwile"]] == pytest.approx([1, 3.15, 5.3])
    assert w["n"] == pytest.approx([1, 1.025, 1.05])                                          # najazd liniowo do 105%
    przed, pop, pelna, po = w["l"]
    assert not przed["widac"] and przed["tlo"] == 1 and not po["widac"]
    assert pop["skala"] > 0.6 and pelna["skala"] == 1 and pelna["tlo"] == pytest.approx(0.8)
    assert pelna["ramka"]["h"] <= 1080 / 3 and pelna["zoom"] == pytest.approx(1.75)
    assert pelna["ramka"]["y"] + pelna["ramka"]["h"] < 540                                     # nad celem
    assert w["u"][0] == 1 and w["u"][1] == pytest.approx(2.3) and w["uDo"] == pytest.approx(1.2)
    assert w["u"][2]["x"] == pytest.approx(674) and w["u"][2]["y"] == pytest.approx(378)       # środek nagłówka
    assert w["z"][0] == 0 and 0 < w["z"][1]["u"] < 1 and w["z"][2] == 1
    assert w["z"][1]["pas"]["x"] == 810 and w["z"][1]["pas"]["h"] == pytest.approx(40 * 0.82)


def test_plan_ruchow():
    w = node("""
const st = S.stronaZUkladu(uklad);
const p = S.przewijanie({ strona: st, od: 0.5, przystanki: ['karta-4', 'formularz-1'], kadr: [1920, 1080] });
const c = p.chwile[0];
const naPostoju = S.lupa({ strona: st, cel: 'cena-2', od: c.od + 0.1, do: c.do - 0.1 });
const wJezdzie = S.lupa({ strona: st, cel: 'cena-2', od: 1, do: 2 });
const zak = S.zakreslacz({ strona: st, cel: 'cena-2', od: 1 });
const n = S.najazd({ strona: st, od: 2, do: 3, na: 2.4 });
const ud = [0, 1, 2].map(i => S.uderzenie({ strona: st, cel: 'naglowek-1', od: 20 + i }));
const ok = S.sprawdzPlan([p, naPostoju], { strona: st });
const zle = S.sprawdzPlan([p, wJezdzie, zak, n, ...ud], { strona: st });
let rzut = ''; try { S.wymagajPlanu([p, wJezdzie]); } catch (e) { rzut = e.message; }
console.log(JSON.stringify({ ok, zle, rzut }));
""")
    assert w["ok"] == {"bledy": [], "ostrzezenia": []}
    b, o = " | ".join(w["zle"]["bledy"]), " | ".join(w["zle"]["ostrzezenia"])
    assert "dwa ruchy kamery naraz: przewijanie" in b and "najazd" in b
    assert "lupa w czasie ruchu kamery" in b and "uderzenie" not in b                         # uderzenie może przerwać ruch
    assert "zakreślacz w czasie ruchu kamery" in o and "uderzeń 3, najwyżej 2" in o
    assert "przybliżenie 2.40× przekracza rozdzielczość zrzutu (2×)" in o
    assert w["rzut"].startswith("strona.js: lupa w czasie ruchu kamery")


def test_modul_strona_jest_kopiowany_pod_lib_jarvo():
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    assert "strona.js" in nz.JARVO_JS_PLIKI and MODUL.is_file()
    assert "from './ruch.js'" in MODUL.read_text(encoding="utf-8")                           # import względny: /_lib/jarvo/
