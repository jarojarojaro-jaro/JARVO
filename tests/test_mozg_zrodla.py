"""Mózg aplikacji (docs/HQ.md „Mózg”): źródła z konfig/mozg.json i graf z pliku (hq/plugin/mozg_zrodla.py), trasy
GET /mozg/zrodla i /mozg/<klucz>, wspólny graf shared/web/graf.js w node (800+ węzłów płynnie, Barnes-Hut, sterownik
na atrapie canvasa), lista Notatek w 63-mozg.js (filtr bez ogonków) i oba buildy z jednym kodem grafu."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from conftest import REPO, load_script

MZ = load_script("hq/plugin/mozg_zrodla.py", "jarvo_test_mozg_zrodla")
NODE = shutil.which("node")
GRAF_JS = REPO / "shared" / "web" / "graf.js"


def _graf_operatora(tmp_path, n=3):
    p = tmp_path / "dane.json"
    p.write_text(json.dumps({"nodes": [{"id": "_hub", "tytul": "Mózg", "hub": True, "stopien": 2, "opis": "o"},
                                       {"id": "bledy/a", "tytul": "A", "zmieniono": "2026-11-08"},
                                       {"id": "bledy/a"}, {"bez": "id"}, {"id": "b"}][:n + 2],
                             "links": [{"source": "_hub", "target": "bledy/a"}, {"source": {"id": "_hub"}, "target": "b"},
                                       {"source": "_hub", "target": "nie-ma"}, {"source": "b", "target": "b"}]}), encoding="utf-8")
    return p


@pytest.fixture
def klient(tmp_path):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    konfig = tmp_path / "konfig" / "mozg.json"
    konfig.parent.mkdir()
    router = fastapi.APIRouter()
    zrodla = MZ.dolacz(router, konfig=konfig)
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app), konfig, zrodla


def test_bez_konfiguracji_tylko_skarbiec(klient):
    c, _, _ = klient
    r = c.get("/mozg/zrodla")
    assert r.status_code == 200 and r.json() == {"zrodla": [MZ.SKARBIEC]}
    assert c.get("/mozg/cokolwiek").status_code == 404


def test_zrodlo_z_konfiguracji_bez_sciezki_w_odpowiedzi(klient, tmp_path):
    c, konfig, _ = klient
    plik = _graf_operatora(tmp_path)
    konfig.write_text(json.dumps({"nazwa": "Baza operatora", "graf": str(plik), "notatka_url": "http://serwer:8091/{id}.html",
                                  "widok_3d": "javascript:alert(1)"}), encoding="utf-8")
    zr = c.get("/mozg/zrodla").json()["zrodla"]
    assert [z["klucz"] for z in zr] == ["jarvo", "baza-operatora"]
    assert zr[1]["notatka_url"] == "http://serwer:8091/{id}.html" and zr[1]["widok_3d"] == "http://serwer:8091/"
    assert str(plik) not in json.dumps(zr)
    g = c.get("/mozg/baza-operatora").json()
    assert [w["id"] for w in g["wezly"]] == ["_hub", "bledy/a", "b"]
    assert g["wezly"][0]["we"] == 2 and g["wezly"][1]["folder"] == "bledy" and g["wezly"][2]["tytul"] == "b"
    assert g["linki"] == [{"z": "_hub", "do": "bledy/a", "auto": False}, {"z": "_hub", "do": "b", "auto": False}]


def test_lista_kluczy_adresy_i_zle_wpisy(tmp_path):
    k = tmp_path / "mozg.json"
    k.write_text(json.dumps({"zrodla": [{"nazwa": "Łąka", "graf": "x.json", "notatka_url": "https://a/b"},
                                        {"nazwa": "Łąka", "graf": "y.json"}, {"nazwa": "jarvo", "graf": "z.json", "klucz": "jarvo"},
                                        {"graf": "bez-nazwy.json"}, "zle"]}), encoding="utf-8")
    w = MZ.wczytaj_konfig(k)
    assert [x["klucz"] for x in w] == ["laka", "laka-2", "jarvo-2"]
    assert w[0]["notatka_url"] == ""            # bez {id} adres notatki nic nie znaczy
    k.write_text("{zły json", encoding="utf-8")
    assert MZ.wczytaj_konfig(k) == []


def test_zly_brakujacy_i_zmieniony_plik(klient, tmp_path):
    c, konfig, zrodla = klient
    plik = tmp_path / "g.json"
    konfig.write_text(json.dumps([{"nazwa": "G", "graf": str(plik)}]), encoding="utf-8")
    assert c.get("/mozg/g").status_code == 404
    plik.write_text("[1, 2]", encoding="utf-8")
    r = c.get("/mozg/g")
    assert r.status_code == 422 and r.json()["blad"]["kod"] == "zly_graf"
    plik.write_text(json.dumps({"wezly": [{"id": "a"}], "linki": []}), encoding="utf-8")
    assert c.get("/mozg/g").json()["wezly"] == [{"id": "a", "hub": False, "tytul": "a", "folder": ""}]
    plik.write_text(json.dumps({"wezly": [{"id": "a"}, {"id": "b", "hub": True}], "linki": [{"z": "a", "do": "b", "auto": True}]}), encoding="utf-8")
    import os
    os.utime(plik, ns=(1, 10**18))
    assert len(zrodla.graf("g")["wezly"]) == 2 and zrodla.graf("g")["linki"][0]["auto"] is True


def test_odczyt_tylko_z_panelu(klient):
    c, _, _ = klient
    assert c.get("/mozg/zrodla", headers={"Sec-Fetch-Site": "same-site"}).status_code == 403
    assert c.get("/mozg/zrodla", headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200


def test_publiczny_kod_bez_prywatnych_sciezek():
    for p in (REPO / "hq" / "plugin" / "mozg_zrodla.py", REPO / "hq" / "web" / "src" / "63-mozg.js", GRAF_JS):
        t = p.read_text(encoding="utf-8")
        assert "~/mozg" not in t and "/home/" not in t and ":8091" not in t


def test_jeden_kod_grafu_w_obu_wtyczkach():
    hqbuild = load_script("scripts/hqbuild.py", "jarvo_test_hqbuild_mozg")
    wiedza = hqbuild.bundle_js(REPO / "wiedza" / "web" / "src", "x", wspolne=(hqbuild.GRAF_WSPOLNY,))
    hq = hqbuild.bundle_js()
    for pakiet in (wiedza, hq):
        assert pakiet.count("function utworzGraf(") == 1
    assert "function Graph(" in wiedza and "function MozgWidok(" in hq
    assert "function stepLayout" not in wiedza       # stary graf zakładki Wiedza zniknął


ATRAPA = r"""
const zdarzenia = {};
global.window = { devicePixelRatio: 1 };
global.performance = { now: () => Number(process.hrtime.bigint()) / 1e6 };
let klatki = [];
global.requestAnimationFrame = (f) => { klatki.push(f); return klatki.length; };
global.cancelAnimationFrame = () => {};
const ctx = new Proxy({}, { get: (o, k) => (k in o ? o[k] : () => {}), set: (o, k, v) => { o[k] = v; return true; } });
const canvas = { clientWidth: 390, clientHeight: 700, width: 0, height: 0, style: {}, getContext: () => ctx,
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 390, height: 700 }),
  addEventListener: (n, f) => { zdarzenia[n] = f; }, removeEventListener: (n) => { delete zdarzenia[n]; } };
%s
const N = Number(process.argv[2]);
const wezly = [], linki = [];
for (let i = 0; i < N; i++) wezly.push({ id: `f${i %% 7}/n${i}`, folder: `f${i %% 7}`, hub: i < 7, we: i %% 5 });
for (let i = 7; i < N; i++) { linki.push({ z: `f${i %% 7}/n${i %% 7}`, do: `f${i %% 7}/n${i}` }); if (i %% 3 === 0) linki.push({ z: `f${i %% 7}/n${i}`, do: `f${(i - 3) %% 7}/n${i - 3}`, auto: true }); }
const otwarte = [];
const g = utworzGraf(canvas, { kolor: () => "#888", motyw: () => ({}), otworz: (id) => otwarte.push(id) });
const liczby = g.dane({ wezly, linki }, {});
// klatki: każda liczy układ w budżecie 10 ms i rysuje; mierzymy najdłuższą
let maks = 0, n = 0;
while (klatki.length && n < 400) { const f = klatki.shift(); const t0 = performance.now(); f(); maks = Math.max(maks, performance.now() - t0); n++; }
const [v, sim] = g.stan(), s = { ...v, alpha: sim.alpha, wezly: sim.nodes }, czeka = klatki.length;
// klik w węzeł otwiera notatkę (świat → ekran: środek płótna + przesunięcie)
const w = s.wezly[10], x = 195 + s.x + w.x * s.k, y = 350 + s.y + w.y * s.k;
zdarzenia.pointerdown({ pointerId: 1, clientX: x, clientY: y }); zdarzenia.pointerup({ pointerId: 1, clientX: x, clientY: y });
// dwa palce: rozsunięcie przybliża
zdarzenia.pointerdown({ pointerId: 2, clientX: 100, clientY: 300 }); zdarzenia.pointerdown({ pointerId: 3, clientX: 200, clientY: 300 });
zdarzenia.pointermove({ pointerId: 3, clientX: 300, clientY: 300 });
const k2 = g.stan()[0].k;
zdarzenia.pointerup({ pointerId: 2 }); zdarzenia.pointerup({ pointerId: 3 });
g.zniszcz();
console.log(JSON.stringify({ liczby, maks, klatki: n, spokoj: s.alpha <= 0.003, czeka, otwarte, k: s.k, k2,
  skonczone: s.wezly.every((q) => Number.isFinite(q.x) && Number.isFinite(q.y)), zdarzenia: Object.keys(zdarzenia).length }));
"""


@pytest.mark.skipif(not NODE, reason="brak node")
@pytest.mark.parametrize("n", [120, 1200])
def test_graf_plynny_i_zasypia(tmp_path, n):
    skrypt = tmp_path / "g.js"
    skrypt.write_text(ATRAPA % GRAF_JS.read_text(encoding="utf-8"), encoding="utf-8")
    r = subprocess.run([NODE, str(skrypt), str(n)], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    w = json.loads(r.stdout)
    assert w["liczby"]["wezly"] == n and w["liczby"]["linki"] > n
    assert w["skonczone"] and w["spokoj"], w
    # płynnie: klatka mieści się w ~16 ms (budżet układu 10 ms + rysowanie), z zapasem na wolną maszynę CI
    assert w["maks"] < 40, w
    # uspokojony graf nie zamawia kolejnych klatek (bateria telefonu)
    assert w["czeka"] == 0 and w["klatki"] < 400
    assert w["otwarte"] == [f"f3/n10"] and w["k2"] > w["k"] * 1.5
    assert w["zdarzenia"] == 0


FILTR = r"""
global.window = {}; const isPL = () => true; const L = (a) => a; const html = () => null; const zadanie = () => null;
%s
const w = ["Łódź", "Zażółć", "abc"].map((t, i) => ({ id: "x/" + i, hub: i === 2, _t: t, _s: mozgProste(t + " x/" + i) }));
console.log(JSON.stringify([mozgFiltruj(w, "").map((n) => n._t), mozgFiltruj(w, "LODZ").map((n) => n._t), mozgFiltruj(w, "zazo").map((n) => n._t),
  mozgUrl({ notatka_url: "https://h/{id}.html" }, "a b/c")]));
"""


@pytest.mark.skipif(not NODE, reason="brak node")
def test_lista_notatek_filtr_i_adresy(tmp_path):
    src = (REPO / "hq" / "web" / "src" / "63-mozg.js").read_text(encoding="utf-8")
    skrypt = tmp_path / "f.js"
    skrypt.write_text(FILTR % src, encoding="utf-8")
    r = subprocess.run([NODE, str(skrypt)], capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [["abc", "Łódź", "Zażółć"], ["Łódź"], ["Zażółć"], "https://h/a%20b/c.html"]
