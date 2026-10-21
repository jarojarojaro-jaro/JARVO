"""Zasoby aplikacji Jarvo: pakiet z nazwą ze skrótu treści, bliźniak .gz, loader ≤ 4 KB i trasa /zasoby
(scripts/hqbuild.py, hq/plugin/plugin_api.py; docs/HQ.md §2c).

Loader działa na każdej stronie dashboardu, więc jest mały, a pakiet aplikacji pobiera dopiero /jarvo. Tu: nazwy
i gzip (powtarzalny build), nagłówki i biała lista trasy, a w node zachowanie loadera z atrapą Reacta (wczytanie,
zasłona, ekran błędu, osłona błędów, osadzenie, wiszący arkusz, 7 s bez pakietu, ponowna próba, dashboard bez
logowania).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess

import pytest

from conftest import REPO, load_script

NODE = shutil.which("node")


@pytest.fixture(scope="module")
def hqbuild():
    return load_script("scripts/hqbuild.py", "jarvo_test_hqbuild_zasoby")


def test_nazwa_ze_skrotu_i_gzip(hqbuild, tmp_path):
    dane = hqbuild.bundle_js().encode("utf-8")
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    nazwa = hqbuild.zasob(tmp_path / "a", "app", dane, "js")
    assert nazwa == f"app-{hashlib.sha256(dane).hexdigest()[:12]}.js"
    assert (tmp_path / "a" / nazwa).read_bytes() == dane
    gz = (tmp_path / "a" / (nazwa + ".gz")).read_bytes()
    assert gzip.decompress(gz) == dane and len(gz) < len(dane) / 2
    # powtarzalny build: te same bajty dają tę samą nazwę i ten sam plik .gz (mtime 0)
    assert hqbuild.zasob(tmp_path / "b", "app", hqbuild.bundle_js().encode("utf-8"), "js") == nazwa
    assert (tmp_path / "b" / (nazwa + ".gz")).read_bytes() == gz
    # inna treść = inna nazwa (przeglądarka nie trzyma starej wersji)
    assert hqbuild.zasob(tmp_path / "b", "app", dane + b"\n", "js") != nazwa


def test_loader_maly(hqbuild):
    js, css = "app-0123456789ab.js", "app-ba9876543210.css"
    loader = hqbuild.loader_js(js, css)
    assert len(loader.encode("utf-8")) <= hqbuild.LOADER_MAX
    assert f'Z + "{js}"' in loader and f'Z + "{css}"' in loader and "@@" not in loader
    assert '"/api/plugins/jarvo-hq/zasoby/"' in loader
    with pytest.raises(SystemExit):
        hqbuild.loader_js("app-" + "0" * 5000 + ".js", css)


def test_styl_bez_adresow_do_dist_poza_krojami(hqbuild):
    css = hqbuild.style_aplikacji("a{src:url(fonts/Inter-latin.woff2)} b{src:url('fonts/kroje/x.woff2')}")
    assert "url(kroje/Inter-latin.woff2)" in css
    assert "url('../../../../dashboard-plugins/jarvo-hq/dist/fonts/kroje/x.woff2')" in css


# --------------------------------------------------------------- trasa /zasoby (FastAPI)

@pytest.fixture
def trasa(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import fastapi
    from fastapi.testclient import TestClient
    api = load_script("hq/plugin/plugin_api.py", "jarvo_test_hq_zasoby_api")
    zasoby = tmp_path / "dist" / "zasoby"
    (zasoby / "kroje").mkdir(parents=True)
    dane = b"window.__JARVO_APP__ = {};\n" * 50
    nazwa = load_script("scripts/hqbuild.py", "jarvo_test_hqbuild_trasa").zasob(zasoby, "app", dane, "js")
    (zasoby / "kroje" / "Inter-latin.woff2").write_bytes(b"wOF2" + b"\0" * 40)
    (tmp_path / "tajne.woff2").write_bytes(b"sekret")
    os.symlink(tmp_path / "tajne.woff2", zasoby / "kroje" / "obcy.woff2")
    monkeypatch.setattr(api, "ZASOBY", zasoby)
    app = fastapi.FastAPI()
    app.include_router(api.router, prefix="/api/plugins/jarvo-hq")
    return api, TestClient(app), nazwa, dane


def test_trasa_gzip_i_cache(trasa):
    _, k, nazwa, dane = trasa
    u = f"/api/plugins/jarvo-hq/zasoby/{nazwa}"
    r = k.get(u, headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.content == dane          # httpx rozpakowuje
    assert r.headers["content-encoding"] == "gzip"
    assert r.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert r.headers["vary"] == "Accept-Encoding" and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-type"].startswith("text/javascript")
    r = k.get(u, headers={"Accept-Encoding": "identity"})
    assert r.status_code == 200 and "content-encoding" not in r.headers and r.content == dane
    r = k.get("/api/plugins/jarvo-hq/zasoby/kroje/Inter-latin.woff2")
    assert r.status_code == 200 and r.headers["content-type"] == "font/woff2"


@pytest.mark.parametrize("nazwa", [
    "index.js", "app-XYZ.js", "app-0123456789ab.js", "app-{h}.js.gz", "app-{h}.map", "style.css",
    "kroje/obcy.woff2",                      # dowiązanie poza katalog zasobów
])
def test_trasa_biala_lista(trasa, nazwa):
    api, k, h, _ = trasa
    nazwa = nazwa.replace("{h}", h[4:-3])
    assert api._zasob(nazwa, True) is None
    assert k.get(f"/api/plugins/jarvo-hq/zasoby/{nazwa}").status_code == 404


def test_trasa_bez_wyjscia_z_katalogu(trasa):
    api, *_ = trasa
    for nazwa in ("../plugin_api.py", "kroje/../../tajne.woff2", "/etc/passwd", "kroje\\..\\x.woff2", ""):
        assert api._zasob(nazwa, True) is None, nazwa


# --------------------------------------------------------------- loader w node (atrapa Reacta)

HARNESS = r"""
const vm = require("vm"), fs = require("fs");
const kod = fs.readFileSync(process.argv[2], "utf8");
const czekaj = () => new Promise((ok) => setImmediate(ok));
async function scenariusz(tryb) {
  const atr = new Set(["data-jarvo-wstepnie"]), dodane = [], timery = [];
  if (tryb === "embed") atr.add("data-jarvo-embed");
  let rej = null, hooki = [], idx = 0, efekty = [];
  const sklepy = new Map();                         // stan hooków osobno dla każdego komponentu
  function Component(p) { this.props = p; }
  const R = {Component, createElement: (t, p, ...c) => ({t, p: p || {}, c}),
    useState(i) { const k = idx++, h = hooki; if (!(k in h)) h[k] = i; return [h[k], (v) => { h[k] = typeof v === "function" ? v(h[k]) : v; }]; },
    useEffect(f, deps) { const k = idx++, s = hooki[k];
      if (!s || deps.some((d, i) => d !== s[i])) efekty.push(f); hooki[k] = deps; }};
  const el = (tag) => ({tag, remove() { this.usuniety = true; }});
  const okno = {console: {error() {}}, Promise, Object, Error,
    __HERMES_PLUGIN_SDK__: {React: R},
    __HERMES_PLUGINS__: {register: (n, c) => { rej = [n, c]; }},
    localStorage: {getItem: () => (tryb === "en" ? "en" : null)},
    location: {href: "http://localhost:9119/jarvo", reload() {}},
    setTimeout: (f, ms) => { timery.push([f, ms]); return timery.length; }, clearTimeout: (n) => { timery[n - 1][2] = "zdjety"; },
    document: {documentElement: {setAttribute: (a) => atr.add(a), removeAttribute: (a) => atr.delete(a), hasAttribute: (a) => atr.has(a)},
      createElement: el, head: {appendChild: (e) => dodane.push(e)}, body: {appendChild: (e) => dodane.push(e)}}};
  if (tryb === "bez_logowania") okno.__HERMES_AUTH_REQUIRED__ = false;
  okno.window = okno;
  vm.runInNewContext(kod, okno);
  const [nazwa, Jarvo] = rej;
  const sprzatanie = [];
  const rysuj = (C, p) => { hooki = sklepy.get(C) || []; sklepy.set(C, hooki); idx = 0; efekty = []; const w = C(p || {}); efekty.forEach((f) => { const s = f(); if (s) sprzatanie.push(s); }); return w; };
  const tekst = (w) => w == null ? "" : typeof w !== "object" ? String(w) : [w.p && w.p.href ? "[" + w.p.href + "]" : "", ...(w.c || []).map(tekst)].join("");
  const timer = (ms) => timery.filter((t) => t[1] === ms && t[2] !== "zdjety").forEach((t) => { t[2] = "zdjety"; t[0](); });
  const opisz = (w) => { if (w.t.name === "Blad") { const b = rysuj(w.t); return {po: "Blad", blad: tekst(b), rola: b.p.role}; }
    return {po: w.t.name || w.p.className || w.t}; };
  const wynik = {nazwa, tryb};
  let w = rysuj(Jarvo);
  wynik.pierwszy = w.p.className || tekst(w);
  wynik.zadania = dodane.map((e) => e.src || e.href);
  const skrypt = dodane.find((e) => e.tag === "script"), styl = dodane.find((e) => e.tag === "link");
  const aplikacja = () => { okno.__JARVO_APP__ = {App: function App() { return "APP"; }, wersja: 1}; };
  if (tryb === "styl_wisi") {                       // arkusz nie odpowiada: aplikacja rusza po 3 s bez niego
    aplikacja(); skrypt.onload(); await czekaj();
    wynik.przed3s = opisz(rysuj(Jarvo)).po;
    timer(3000); await czekaj();
    Object.assign(wynik, opisz(rysuj(Jarvo)));
  } else if (tryb === "wisi") {                     // pakiet nie odpowiada: po 7 s ekran błędu, potem i tak aplikacja
    if (styl) styl.onload();
    timer(7000); await czekaj();
    Object.assign(wynik, opisz(rysuj(Jarvo)));
    aplikacja(); skrypt.onload(); await czekaj();
    wynik.pozniej = opisz(rysuj(Jarvo)).po;
  } else if (tryb === "ponow") {                    // pierwszy raz błąd sieci; po wyjściu i powrocie nowa próba
    styl.onload(); skrypt.onerror(); await czekaj();
    wynik.raz = opisz(rysuj(Jarvo)).po;
    wynik.usuniete = [skrypt.usuniety, styl.usuniety];
    sprzatanie.splice(0).forEach((f) => f());
    sklepy.delete(Jarvo);                           // nowe zamontowanie zakładki (SPA: /sessions → /jarvo)
    rysuj(Jarvo);
    wynik.zadania2 = dodane.length;
    const s2 = dodane.filter((e) => e.tag === "script")[1], l2 = dodane.filter((e) => e.tag === "link")[1];
    l2.onload(); aplikacja(); s2.onload(); await czekaj();
    Object.assign(wynik, opisz(rysuj(Jarvo)));
  } else {
    if (styl) styl.onload();
    if (tryb === "ok" || tryb === "bez_logowania") { aplikacja(); skrypt.onload(); }
    else if (skrypt) skrypt.onerror();
    await czekaj();
    if (skrypt) {
      w = rysuj(Jarvo);
      Object.assign(wynik, opisz(w));
      if (w.t.name === "Oslona") {
        wynik.dziecko = w.c[0].t.name;
        const O = w.t, inst = new O({children: "x"});
        wynik.stanBledu = O.getDerivedStateFromError(new Error("x"));
        atr.add("data-jarvo-app"); inst.componentDidCatch(new Error("x"));
        wynik.appPoBledzie = atr.has("data-jarvo-app");
        inst.state = {blad: true}; wynik.poBledzie = inst.render().t.name;
      }
    }
  }
  wynik.timery = timery.map((t) => t[1]);
  timery.forEach((t) => { if (t[2] !== "zdjety") t[0](); });
  if (skrypt && tryb === "ok") wynik.po7s = opisz(rysuj(Jarvo)).po;   // timer 7 s nie psuje gotowej aplikacji
  wynik.atr = [...atr].sort();
  sprzatanie.forEach((f) => f());
  wynik.poWyjsciu = [...atr].sort();
  wynik.timerZdjety = timery.filter((t) => t[1] === 7000).every((t) => t[2] === "zdjety");
  return wynik;
}
(async () => {
  const out = {};
  for (const t of ["ok", "blad", "en", "embed", "styl_wisi", "wisi", "ponow", "bez_logowania"]) out[t] = await scenariusz(t);
  console.log(JSON.stringify(out));
})();
"""


def test_loader_w_node(hqbuild, tmp_path):
    if not NODE:
        pytest.skip("brak node")
    js, css = "app-0123456789ab.js", "app-ba9876543210.css"
    (tmp_path / "index.js").write_text(hqbuild.loader_js(js, css), encoding="utf-8")
    (tmp_path / "h.js").write_text(HARNESS, encoding="utf-8")
    r = subprocess.run([NODE, str(tmp_path / "h.js"), str(tmp_path / "index.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    w = json.loads(r.stdout)
    ok, blad, en, embed = w["ok"], w["blad"], w["en"], w["embed"]
    zas = "/api/plugins/jarvo-hq/zasoby/"
    # wczytanie: zasłona startowa, potem styl i pakiet z /zasoby, stara Baza w osłonie błędów
    assert ok["nazwa"] == "jarvo-hq" and ok["pierwszy"] == "jarvo-splash"
    assert sorted(ok["zadania"]) == sorted([zas + css, zas + js])
    assert ok["po"] == "Oslona" and ok["dziecko"] == "App"
    # timery: 7 s na pakiet, 3 s na arkusz, 0,2 s zejścia zasłony; wersja 1: gotowe, powłoka Hermesa zostaje
    assert ok["timery"] == [7000, 3000, 200] and ok["atr"] == ["data-jarvo-gotowe"] and ok["po7s"] == "Oslona"
    assert ok["poWyjsciu"] == [] and ok["timerZdjety"] is True
    # osłona: błąd renderu = ekran błędu, chowanie powłoki zdjęte
    assert ok["stanBledu"] == {"blad": True} and ok["appPoBledzie"] is False and ok["poBledzie"] == "Blad"
    # pakiet się nie wczytał: ekran błędu z odświeżeniem i klasycznym panelem, zasłona zdjęta
    assert blad["po"] == "Blad" and blad["rola"] == "alert"
    assert "Coś poszło nie tak przy otwieraniu Jarva." in blad["blad"]
    assert "Odśwież" in blad["blad"] and "[/sessions]Otwórz klasyczny panel" in blad["blad"]
    assert "data-jarvo-gotowe" in blad["atr"] and "data-jarvo-wstepnie" not in blad["atr"]
    assert "Something went wrong while opening Jarvo." in en["blad"] and "Open the classic dashboard" in en["blad"]
    # w ramce szuflady Jarvo się nie wczytuje
    assert embed["zadania"] == [] and "otwarty w głównym oknie" in embed["pierwszy"]


def test_loader_bez_pustego_pola(hqbuild, tmp_path):
    """Wiszący arkusz czeka najwyżej 3 s; pakiet, którego po 7 s nie ma, daje ekran błędu (a gdy dojdzie, aplikację);
    po błędzie następne wejście próbuje od nowa; dashboard bez logowania bierze pakiet ze statycznej kopii."""
    if not NODE:
        pytest.skip("brak node")
    js, css = "app-0123456789ab.js", "app-ba9876543210.css"
    (tmp_path / "index.js").write_text(hqbuild.loader_js(js, css), encoding="utf-8")
    (tmp_path / "h.js").write_text(HARNESS, encoding="utf-8")
    r = subprocess.run([NODE, str(tmp_path / "h.js"), str(tmp_path / "index.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    w = json.loads(r.stdout)
    assert w["styl_wisi"]["przed3s"] == "jarvo-splash" and w["styl_wisi"]["po"] == "Oslona"
    assert w["wisi"]["po"] == "Blad" and "Odśwież" in w["wisi"]["blad"] and w["wisi"]["pozniej"] == "Oslona"
    assert "data-jarvo-wstepnie" not in w["wisi"]["atr"]
    p = w["ponow"]
    assert p["raz"] == "Blad" and p["usuniete"] == [True, True] and p["zadania2"] == 4 and p["po"] == "Oslona"
    statyczne = "/dashboard-plugins/jarvo-hq/dist/zasoby/"
    assert sorted(w["bez_logowania"]["zadania"]) == sorted([statyczne + css, statyczne + js])
    assert w["bez_logowania"]["po"] == "Oslona"


def test_pakiet_rejestruje_aplikacje_nie_zakladke(hqbuild):
    js = hqbuild.bundle_js()
    assert "window.__JARVO_APP__ = { App: AppJarvo, StaraBaza, wersja: 2 };" in js
    assert not re.search(r"__HERMES_PLUGINS__\.register\(", js)
    manifest = json.loads((REPO / "hq" / "plugin" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["entry"] == "dist/index.js" and "css" not in manifest
