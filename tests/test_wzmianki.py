"""Parser wzmianek @uchwyt (hq/plugin/wzmianki.py) i jego bliźniak w przeglądarce (hq/web/src/12-wzmianki.js):
te same wektory z tests/data/wzmianki.json w Pythonie i w node, zgodność listy agentów z fleet.yaml, brak
przyklejonego adresata (sekwencje), składanie polskich znaków i słowa zarezerwowane wspólne z walidatorem."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import load_script

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
WEKTORY = json.loads((REPO / "tests" / "data" / "wzmianki.json").read_text(encoding="utf-8"))
JS = REPO / "hq" / "web" / "src" / "12-wzmianki.js"
wz = load_script("hq/plugin/wzmianki.py", "jarvo_test_wzmianki")
POLA = ("adresaci", "bezposrednio", "tresc", "wiodace", "ostrzezenia")


def _przypadki():
    for v in WEKTORY["wektory"]:
        for i, krok in enumerate(v.get("sekwencja") or [v]):
            yield pytest.param(v, krok, id=f"{v['nr']}.{i}")


@pytest.mark.parametrize("wektor,krok", list(_przypadki()))
def test_wektory_python(wektor, krok):
    agenci = WEKTORY["agenci"] + wektor.get("dodatkowi", [])
    wynik = wz.parsuj(krok["tekst"], wz.mapa_aliasow(agenci), nazwy=wz.nazwy_agentow(agenci),
                      koordynator=wektor.get("koordynator", WEKTORY["koordynator"]))
    assert wynik.jako_slownik() == {k: krok[k] for k in POLA}


def test_sekwencje_bez_przyklejonego_adresata():
    """W2: po `@web …` następna wiadomość bez @ idzie do koordynatora; parser nie ma stanu."""
    sekwencje = [v for v in WEKTORY["wektory"] if v.get("sekwencja")]
    assert {v["nr"] for v in sekwencje} >= {18, 19, 30, 31}
    mapa = wz.mapa_aliasow(WEKTORY["agenci"])
    wz.parsuj("@web popraw", mapa)
    assert wz.parsuj("zrób", mapa).adresaci == ("jarvo",)


@pytest.mark.skipif(not NODE, reason="brak node")
def test_wektory_node_dzialaja_tak_samo(tmp_path):
    skrypt = tmp_path / "t.js"
    skrypt.write_text(JS.read_text(encoding="utf-8") + """
const fs = require("fs");
const d = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = [];
for (const v of d.wektory) {
  const agenci = d.agenci.concat(v.dodatkowi || []);
  const mapa = Wzmianki.mapaAliasow(agenci), nazwy = Wzmianki.nazwyAgentow(agenci);
  for (const k of (v.sekwencja || [v])) {
    out.push(Wzmianki.parsuj(k.tekst, mapa, { koordynator: v.koordynator || d.koordynator, nazwy }));
  }
}
console.log(JSON.stringify({ out, zarezerwowane: [...Wzmianki.ZAREZERWOWANE], zloz: Wzmianki.zloz("ŁÓDŹ Ręka Żółw") }));
""", encoding="utf-8")
    r = subprocess.run([NODE, str(skrypt), str(REPO / "tests" / "data" / "wzmianki.json")],
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    wynik = json.loads(r.stdout)
    oczekiwane = [{k: krok[k] for k in POLA} for v in WEKTORY["wektory"] for krok in (v.get("sekwencja") or [v])]
    assert wynik["out"] == oczekiwane
    assert set(wynik["zarezerwowane"]) == set(wz.ZAREZERWOWANE)
    assert wynik["zloz"] == wz.zloz("ŁÓDŹ Ręka Żółw") == "lodz reka zolw"


def test_agenci_wektorow_to_flota_z_fleet_yaml():
    import fleetlib as fl

    flota = [{"name": a.name, "handle": a.handle, "aliasy": a.aliasy, "nazwa": a.hq_short} for a in fl.load_fleet().active()]
    assert WEKTORY["agenci"] == flota, "tests/data/wzmianki.json: lista agentów nie odpowiada fleet.yaml (uchwyty, aliasy)"


def test_uchwyty_i_aliasy_floty_jak_w_specyfikacji():
    import fleetlib as fl

    a = {x.name: x for x in fl.load_fleet().active()}
    assert a["jarvo-lowca"].handle == "lowca" and "lowca" in a["jarvo-lowca"].aliasy
    assert a["jarvo-reka"].aliasy == ["reka", "jarvo-reka"]
    assert a["jarvo-wideo"].aliasy == ["wideo", "jarvo-wideo", "wideograf"]
    assert a["jarvo-mobile"].aliasy == ["mobile", "jarvo-mobile", "aplikacje"]
    assert all(re.fullmatch(r"[a-z][a-z0-9]{1,15}", x.handle) for x in a.values())


def test_zloz_i_slowa_zarezerwowane_wspolne_z_fleetlib():
    import fleetlib as fl

    for s in ("Łowca", "Ręka", "ŻÓŁW", "Wideograf", "ﬁ", "café"):
        assert fl.zloz(s) == wz.zloz(s)
    assert fl.UCHWYTY_ZAREZERWOWANE == wz.ZAREZERWOWANE
    assert fl.UCHWYT_RE.pattern == wz.UCHWYT_RE.pattern


def test_mapa_aliasow_bez_slow_zarezerwowanych_i_pierwszy_wygrywa():
    mapa = wz.mapa_aliasow([{"name": "a", "aliasy": ["all", "Ala"]}, {"name": "b", "aliasy": ["ala", "bob"]},
                            {"name": "c", "handle": "cecylia"}])
    assert mapa == {"ala": "a", "bob": "b", "cecylia": "c", "c": "c"}


def test_js_ma_jedna_nazwe_na_poziomie_pakietu():
    """Pliki hq/web/src/*.js dzielą jedno IIFE: parser wystawia tylko `Wzmianki`."""
    tekst = JS.read_text(encoding="utf-8")
    nazwy = re.findall(r"^(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)", tekst, re.M)
    assert nazwy == ["Wzmianki"]
    inne = [p for p in (REPO / "hq" / "web" / "src").glob("*.js") if p != JS]
    assert not any(re.search(r"^(?:const|let|var|function|class)\s+Wzmianki\b", p.read_text(encoding="utf-8"), re.M)
                   for p in inne)
