"""Powłoka /jarvo w dashboardzie Hermesa: branding/patch_dashboard.py z branding/powloka.json i skrypt
branding/powloka.js (docs/HQ.md §2c).

Łatka działa na pakiecie testowym (nazwy jak w zminifikowanym dist Hermesa, ale inne identyfikatory): dokładne liczby
trafień, kod 1 przy brakującym elemencie albo innej liczbie, druga łatka bez zmian, CSS i skrypt w index.html raz.
Skrypt powłoki i strzeżone przekierowanie liczy node (cel __JARVO_CEL__, osadzanie, ramka obca, bezpiecznik 8 s,
inert poza korzeniem aplikacji). Do tego restart dashboardu z limitem timeout-kill (install-fleet.sh, infra/Dockerfile).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from conftest import REPO

BRAND = REPO / "branding"
PATCH = BRAND / "patch_dashboard.py"
NODE = shutil.which("node")

# fragmenty dista Hermesa 0.21.5 (index-*.js), z innymi nazwami zmiennych niż w oryginale
DIST_JS = """import{a as Zx}from"./vendor-1a2b3c.js";
function Qn(e,t){let n=Zx(e,t),r=new Set(e.map(e=>e.path));return n.filter(x=>!r.has(x.path))}
function Korzen(){return(0,$q.jsx)(Nv,{to:`/sessions`,replace:!0})}
function Nieznany(){return(0,$q.jsx)(Nv,{to:`/sessions`,replace:!0})}
function Po1(){Kc(`/sessions`)}function Po2(){Kc(`/sessions`)}function Po3(){y$(`/sessions`)}
const Pasek={id:`app-sidebar`,className:`fixed`};
const Nagl=`lg:hidden fixed top-0 left-0 right-0 z-40 min-h-14`,Zasl=`lg:hidden fixed inset-0 z-40 p-0 block`;
const Odst=`h-14 shrink-0 lg:hidden`;const Link={to:`/sessions`};
"""
VENDOR_JS = "export const a=(e,t)=>e;\n"
INDEX = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Hermes Agent - Dashboard</title>
    <script type="module" crossorigin src="/assets/index-9f8e7d.js"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""


def _dist(root, js: str = DIST_JS):
    web = root / "hermes_cli" / "web_dist"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text(INDEX, encoding="utf-8")
    (web / "assets" / "index-9f8e7d.js").write_text(js, encoding="utf-8")
    (web / "assets" / "vendor-1a2b3c.js").write_text(VENDOR_JS, encoding="utf-8")
    return web


def _patch(root):
    env = {**os.environ, "JARVO_HERMES_DIR": str(root)}
    return subprocess.run([sys.executable, str(PATCH), str(BRAND)], env=env, capture_output=True, text=True, timeout=120)


def _glowny(web):
    pliki = [p for p in (web / "assets").glob("index-*.js")]
    assert len(pliki) == 1, pliki
    return pliki[0].read_text(encoding="utf-8")


@pytest.fixture
def lata(tmp_path):
    web = _dist(tmp_path)
    r = _patch(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    return tmp_path, web, r


def test_dokladne_liczby_i_zamiany(lata):
    _, web, r = lata
    js = _glowny(web)
    assert js.count('new Set([...e.map(e=>e.path),"/jarvo"])') == 1          # Jarvo w głównym menu
    assert js.count('{to:(typeof window.__JARVO_CEL__=="function"?window.__JARVO_CEL__:function(){return"/sessions"})(),'
                    'replace:!0}') == 2
    # po restarcie gatewaya i aktualizacji Hermes zostaje przy /sessions (dziennik akcji), zwykły link do Sesji też
    assert "function Po1(){Kc(`/sessions`)}function Po2(){Kc(`/sessions`)}function Po3(){y$(`/sessions`)}" in js
    assert js.count("`/sessions`") == 4 and "Link={to:`/sessions`}" in js
    for nazwa in ("nav_glowna: 1", "przekierowania: 2", "elementy do ukrycia w dist: 4"):
        assert nazwa in r.stdout
    assert "po_restarcie" not in r.stdout
    # zmieniony plik dostał nową nazwę (cache przeglądarki), index.html wskazuje na nią
    nowy = next((web / "assets").glob("index-*.js")).name
    assert re.fullmatch(r"index-9f8e7d-t[0-9a-f]{6}\.js", nowy)
    assert f"/assets/{nowy}" in (web / "index.html").read_text(encoding="utf-8")


def test_index_html_styl_i_skrypt_raz(lata):
    _, web, _ = lata
    html = (web / "index.html").read_text(encoding="utf-8")
    assert html.count('id="jarvo-powloka"') == 1 and html.count('id="jarvo-powloka-js"') == 1
    glowa, cialo = html.split("</head>", 1)
    assert '<style id="jarvo-powloka">' in glowa and "<title>Jarvo</title>" in glowa
    # skrypt powłoki jest pierwszym dzieckiem <body>, przed korzeniem aplikacji
    assert cialo.index('id="jarvo-powloka-js"') < cialo.index('<div id="root">')
    assert (BRAND / "powloka.js").read_text(encoding="utf-8").strip() in cialo
    dane = json.loads((BRAND / "powloka.json").read_text(encoding="utf-8"))
    for c in dane["css"]:
        assert f"html[data-jarvo-app] {c['selektor']}" in glowa and f"html[data-jarvo-embed] {c['selektor']}" in glowa
    for atrybut in ("data-jarvo-wstepnie", "data-jarvo-gotowe", "data-jarvo-zablokuj"):
        assert atrybut in glowa


def test_druga_latka_niczego_nie_zmienia(lata):
    root, web, _ = lata
    przed = {p.name: p.read_bytes() for p in (web / "assets").iterdir()}
    html = (web / "index.html").read_bytes()
    r = _patch(root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count("już jest") == 2
    assert {p.name: p.read_bytes() for p in (web / "assets").iterdir()} == przed
    assert (web / "index.html").read_bytes() == html


@pytest.mark.parametrize("zmiana,powod", [
    (lambda js: js.replace("id:`app-sidebar`,", ""), "pasek"),                        # Hermes zmienił menu boczne
    (lambda js: js.replace("h-14 shrink-0 lg:hidden", "h-16 shrink-0 lg:hidden"), "odstep"),
    (lambda js: js.replace("r=new Set(e.map(e=>e.path))", "r=new Set(e.map(t=>t.path))"), "nav_glowna"),
    (lambda js: js + "function Trzeci(){return(0,$q.jsx)(Nv,{to:`/sessions`,replace:!0})}\n", "przekierowania"),
])
def test_brak_elementu_wywraca_build(tmp_path, zmiana, powod):
    """Dist Hermesa bez jednego selektora albo z inną liczbą trafień: kod 1 i nazwa wpisu (build obrazu staje)."""
    web = _dist(tmp_path, zmiana(DIST_JS))
    r = _patch(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "powłoka Jarvo" in r.stderr and powod in r.stderr
    assert 'id="jarvo-powloka' not in (web / "index.html").read_text(encoding="utf-8")


def test_przejscia_po_restarcie_bez_lat(tmp_path):
    """Przejść Hermesa na /sessions po restarcie i aktualizacji łatka nie dotyka: inna ich liczba nie wywraca buildu."""
    _dist(tmp_path, DIST_JS.replace("function Po3(){y$(`/sessions`)}", ""))
    r = _patch(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_brak_tytulu_wywraca_build(tmp_path):
    web = _dist(tmp_path)
    (web / "index.html").write_text(INDEX.replace("<title>Hermes Agent - Dashboard</title>", ""), encoding="utf-8")
    assert _patch(tmp_path).returncode == 1


# --------------------------------------------------------------- skrypt powłoki w node

HARNESS = r"""
const vm = require("vm"), fs = require("fs");
const [kod, przypadki] = [fs.readFileSync(process.argv[2], "utf8"), JSON.parse(process.argv[3])];
const wyniki = [];
for (const p of przypadki) {
  const atr = new Set(), timery = [], historia = [], zdarzenia = [], zamiany = [];
  const url = new URL(p.adres, "http://localhost:9119");
  const ustaw = (u) => { const n = new URL(u, url); location.pathname = n.pathname; location.search = n.search; };
  const location = {pathname: url.pathname, search: url.search, hash: url.hash, origin: url.origin,
    replace: (u) => zamiany.push(u)};
  const okno = {location, __HERMES_BASE_PATH__: p.baza,
    history: {state: null, replaceState(s, t, u) { historia.push(u); ustaw(u); }},
    document: {documentElement: {setAttribute: (a) => atr.add(a), removeAttribute: (a) => atr.delete(a), hasAttribute: (a) => atr.has(a)}},
    setTimeout: (f, ms) => timery.push([f, ms]),
    PopStateEvent: class { constructor(t, o) { this.type = t; this.state = o && o.state; } },
    dispatchEvent: (e) => { zdarzenia.push(e.type); if (p.uparty) ustaw(p.wraca); }};   // uparty: SPA nie słucha popstate
  okno.window = okno; okno.self = okno;
  okno.frameElement = p.ramka === "jarvo" ? {hasAttribute: (a) => a === "data-jarvo-embed"}
                    : p.ramka === "wlasna" ? {hasAttribute: () => false} : null;
  okno.top = p.ramka === "obca" ? {get location() { throw new Error("SecurityError"); }}
           : p.ramka ? {location: {origin: url.origin}} : okno;
  vm.runInNewContext(kod, okno);
  const start = historia.length, nStart = timery.length, poSkrypcie = [...atr].sort();
  const cel = p.bezCelu ? [] : [okno.__JARVO_CEL__()];
  if (p.potem) { location.pathname = p.potem; cel.push(okno.__JARVO_CEL__()); }
  const korekty = timery.splice(nStart);            // timery z __JARVO_CEL__ (poprawka cofniętego przekierowania)
  const przed = [...atr].sort();
  if (p.gotowe) atr.add("data-jarvo-gotowe");
  if (p.app) atr.add("data-jarvo-app");
  timery.forEach(([f]) => f());
  // po przekierowaniu SPA jest pod p.potem_spa (udane) albo wróciło pod p.wraca (wyścig ?profile= w Hermesie)
  const adres = location.pathname + location.search;
  if (p.potem_spa) ustaw(p.potem_spa);
  if (p.wraca) ustaw(p.wraca);
  const zKorekty = historia.length;
  korekty.forEach(([f]) => f());
  wyniki.push({historia: historia.slice(0, start), cel, poSkrypcie, przed, po: [...atr].sort(), timery: timery.map((t) => t[1]),
    adres, korekty: korekty.map((t) => t[1]),
    poprawka: historia.slice(zKorekty), zdarzenia, zamiany});
}
console.log(JSON.stringify(wyniki));
"""


def _powloka(tmp_path, przypadki):
    if not NODE:
        pytest.skip("brak node")
    h = tmp_path / "harness.js"
    h.write_text(HARNESS, encoding="utf-8")
    r = subprocess.run([NODE, str(h), str(BRAND / "powloka.js"), json.dumps(przypadki)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_cel_przekierowan(tmp_path):
    w = _powloka(tmp_path, [
        {"adres": "/"},                                   # start: adres przepisany przed SPA, zasłona, bezpiecznik
        {"adres": "/base?x=1#k"},                         # stara zakładka: zapytanie i kotwica zostają
        {"adres": "/jarvo", "potem": "/sessions"},        # na /jarvo bez pluginu cel to /sessions (bez pętli)
        {"adres": "/nieznane"},                           # nieznany adres: Hermes przekieruje na cel = /jarvo
        {"adres": "/sessions"},
        {"adres": "/hermes/", "baza": "/hermes/"},        # dashboard pod prefiksem ścieżki
        {"adres": "/hermes/base", "baza": "/hermes"},
    ])
    assert w[0]["historia"] == ["/jarvo"] and w[0]["poSkrypcie"] == ["data-jarvo-wstepnie"]
    # Hermes opuszcza /jarvo (plugin się nie wczytał): cel /sessions i zasłona od razu zdjęta, nie po 8 s
    assert w[0]["cel"] == ["/sessions"] and w[0]["przed"] == []
    assert w[0]["timery"] == [8000]
    assert w[1]["historia"] == ["/jarvo?x=1#k"] and w[1]["adres"] == "/jarvo?x=1"
    assert w[2]["historia"] == [] and w[2]["cel"] == ["/sessions", "/jarvo"]
    assert w[3]["historia"] == [] and w[3]["cel"] == ["/jarvo"] and w[3]["przed"] == [] and w[3]["timery"] == []
    assert w[4]["cel"] == ["/jarvo"] and w[4]["przed"] == []
    assert w[5]["historia"] == ["/hermes/jarvo"] and w[5]["cel"] == ["/sessions"]
    assert w[6]["historia"] == ["/hermes/jarvo"]


def test_osadzanie_i_ramka_obca(tmp_path):
    w = _powloka(tmp_path, [
        {"adres": "/logs?jarvo-embed=1", "ramka": "wlasna"},   # ręczna próba w ramce: bez powłoki, cel zawsze /sessions
        {"adres": "/?jarvo-embed=1", "ramka": "wlasna"},  # w ramce "/" nie prowadzi do /jarvo
        {"adres": "/config", "ramka": "jarvo"},           # po przejściu w ramce: znacznik z atrybutu ramki
        {"adres": "/jarvo", "ramka": "obca"},             # ramka na stronie z innego pochodzenia (np. :9120)
        {"adres": "/logs?jarvo-embed=1"},                 # w zwykłej karcie zapytanie nic nie zmienia (menu zostaje)
        {"adres": "/jarvo?jarvo-embed=1", "bezCelu": True},
    ])
    assert w[0]["przed"] == ["data-jarvo-embed"] and w[0]["cel"] == ["/sessions"] and w[0]["historia"] == []
    assert w[1]["historia"] == [] and w[1]["cel"] == ["/sessions"] and w[1]["timery"] == []
    assert w[2]["przed"] == ["data-jarvo-embed"] and "data-jarvo-zablokuj" not in w[2]["przed"]
    assert "data-jarvo-zablokuj" in w[3]["przed"]
    assert w[4]["przed"] == [] and w[4]["cel"] == ["/jarvo"]
    assert w[5]["poSkrypcie"] == ["data-jarvo-wstepnie"] and w[5]["timery"] == [8000]


def test_cofniete_przekierowanie(tmp_path):
    """Hermes potrafi w tej samej klatce cofnąć przekierowanie (ProfileProvider dopisuje ?profile= do adresu sprzed
    niego): po 150 ms skrypt powtarza je przez history + popstate, po 1 s przez location.replace; udane przekierowanie
    zostaje w spokoju."""
    w = _powloka(tmp_path, [
        {"adres": "/nieznane", "wraca": "/nieznane?profile=default"},
        {"adres": "/nieznane", "potem_spa": "/jarvo?profile=default"},
        {"adres": "/hermes/nieznane", "baza": "/hermes", "wraca": "/hermes/nieznane?profile=x"},
        {"adres": "/logs?jarvo-embed=1", "ramka": "wlasna", "wraca": "/logs?jarvo-embed=1&profile=default"},
        {"adres": "/nieznane", "wraca": "/nieznane?profile=default", "uparty": True},
        {"adres": "/sessions?jarvo-embed=1", "ramka": "wlasna"},   # cel = obecny adres: bez poprawek
    ])
    assert w[0]["cel"] == ["/jarvo"] and w[0]["korekty"] == [150, 1000]
    assert w[0]["poprawka"] == ["/jarvo?profile=default"] and w[0]["zdarzenia"] == ["popstate"]
    assert w[0]["zamiany"] == []                      # po pierwszej poprawce adres już jest na celu
    assert w[1]["poprawka"] == [] and w[1]["zdarzenia"] == [] and w[1]["zamiany"] == []
    assert w[2]["poprawka"] == ["/hermes/jarvo?profile=x"]
    assert w[3]["cel"] == ["/sessions"] and w[3]["poprawka"] == ["/sessions?jarvo-embed=1&profile=default"]
    assert w[4]["zamiany"] == ["/jarvo?profile=default"]     # pełne przejście zamiast pustej strony
    assert w[5]["cel"] == ["/sessions"] and w[5]["korekty"] == [] and w[5]["zamiany"] == []


def test_bezpiecznik_8s(tmp_path):
    """Aplikacja nie zgłosiła gotowości w 8 s: zasłona i chowanie powłoki znikają (widać menu Hermesa)."""
    w = _powloka(tmp_path, [
        {"adres": "/jarvo", "app": True, "bezCelu": True},
        {"adres": "/jarvo", "app": True, "gotowe": True, "bezCelu": True},
    ])
    assert w[0]["timery"] == [8000] and w[0]["po"] == []
    assert w[1]["po"] == ["data-jarvo-app", "data-jarvo-gotowe", "data-jarvo-wstepnie"]


def test_przekierowanie_strzezone_bez_skryptu(lata, tmp_path):
    """Bez skryptu powłoki (np. inny index.html) przekierowania Hermesa idą na /sessions jak dawniej; tak samo, gdy
    nazwę przesłania element strony o id __JARVO_CEL__ (DOM clobbering: window.__JARVO_CEL__ to wtedy obiekt)."""
    if not NODE:
        pytest.skip("brak node")
    js = _glowny(lata[1])
    wyrazenia = set(re.findall(r'\(typeof window\.__JARVO_CEL__=="function"\?window\.__JARVO_CEL__:'
                               r'function\(\)\{return"/sessions"\}\)\(\)', js))
    assert len(wyrazenia) == 1
    w = wyrazenia.pop()
    kod = (f"const window={{}};const a={w};window.__JARVO_CEL__={{id:'__JARVO_CEL__'}};const b={w};"
           f"window.__JARVO_CEL__=()=>'/jarvo';console.log(a+' '+b+' '+{w})")
    r = subprocess.run([NODE, "-e", kod], capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "/sessions /sessions /jarvo", r.stderr


# --------------------------------------------------------------- inert poza korzeniem aplikacji (node, sztuczny DOM)

INERT = r"""
const vm = require("vm"), fs = require("fs");
const kod = fs.readFileSync(process.argv[2], "utf8");
const obserwatory = [];
class MO { constructor(cb) { this.cb = cb; this.cele = []; obserwatory.push(this); }
  observe(t, o) { this.cele.push([t, o]); } disconnect() { this.cele = []; } }
const zglos = (cel, rodzaj) => obserwatory.forEach((o) => {
  if (o.cele.some(([t, op]) => t === cel && op[rodzaj])) o.cb([]); });
class El {
  constructor(tag, id) { this.tagName = tag; this.id = id; this.children = []; this.parentElement = null; this.a = new Map(); }
  add(...dzieci) { for (const c of dzieci) { c.parentElement = this; this.children.push(c); } zglos(this, "childList"); return this; }
  setAttribute(n, v) { this.a.set(n, String(v)); if (this === html && n === "data-jarvo-app") zglos(html, "attributes"); }
  removeAttribute(n) { const by = this.a.delete(n); if (by && this === html && n === "data-jarvo-app") zglos(html, "attributes"); }
  hasAttribute(n) { return this.a.has(n); }
}
const E = (tag, id) => new El(tag, id);
const html = E("HTML", "html"), body = E("BODY", "body");
const korzen = E("DIV", "korzen").add(E("BUTTON", "w-aplikacji"));
korzen.setAttribute("data-jarvo-korzen", "");
const strona = E("DIV", "strona").add(E("DIV", "thq"), korzen);
const kolumna = E("DIV", "kolumna").add(E("HEADER", "naglowek").add(E("BUTTON", "decyzje")), E("MAIN", "main").add(strona));
const root = E("DIV", "root").add(E("DIV", "baner").add(E("BUTTON", "zamknij")), kolumna);
const cudzy = E("DIV", "cudzy"); cudzy.setAttribute("inert", "");
html.add(E("HEAD", "head"), body);
body.add(E("SCRIPT", "powloka"), root, cudzy);
const wszystkie = (e) => [e, ...e.children.flatMap(wszystkie)];
const document = {documentElement: html, body, querySelector: (s) => wszystkie(html).find((e) => e.a.has("data-jarvo-korzen")) || null};
const location = {pathname: "/sessions", search: "", hash: "", origin: "http://localhost:9119"};
const okno = {document, location, history: {state: null, replaceState() {}}, MutationObserver: MO, setTimeout() {}};
okno.window = okno; okno.self = okno; okno.top = okno;
vm.runInNewContext(kod, okno);
const uspione = () => wszystkie(html).filter((e) => e.a.has("inert")).map((e) => e.id).sort();
const wynik = {start: uspione()};
html.setAttribute("data-jarvo-app", "");
wynik.app = uspione();
body.add(E("DIV", "toast"));                      // Hermes dokłada okno obok: też uśpione
wynik.nowe = uspione();
html.removeAttribute("data-jarvo-app");
wynik.koniec = uspione();
korzen.removeAttribute("data-jarvo-korzen");
html.setAttribute("data-jarvo-app", "");          // bez korzenia: nic nie usypiamy (nie zamykamy właściciela w pustce)
wynik.bezKorzenia = uspione();
console.log(JSON.stringify(wynik));
"""


def test_inert_poza_korzeniem_aplikacji(tmp_path):
    """Z data-jarvo-app wszystko poza korzeniem aplikacji (baner, nagłówek, stara Baza, nowe okna) dostaje inert, więc
    Tab i czytnik ekranu zostają w aplikacji; bez data-jarvo-app atrybuty znikają, a cudzego inert skrypt nie rusza."""
    if not NODE:
        pytest.skip("brak node")
    h = tmp_path / "inert.js"
    h.write_text(INERT, encoding="utf-8")
    r = subprocess.run([NODE, str(h), str(BRAND / "powloka.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    w = json.loads(r.stdout)
    assert w["start"] == ["cudzy"]
    assert w["app"] == ["baner", "cudzy", "naglowek", "thq"]          # skrypt i <head> zostają, korzeń i jego przodkowie też
    assert w["nowe"] == ["baner", "cudzy", "naglowek", "thq", "toast"]
    assert w["koniec"] == ["cudzy"]
    assert w["bezKorzenia"] == ["cudzy"]


def test_restart_panelu_z_limitem():
    """s6 stosuje timeout-kill tylko przy zatrzymaniu (-d), nie przy -r: restart po wdrożeniu to -d i -u, a obraz daje
    usłudze dashboard limit 30 s, więc otwarte strumienie przeglądarek nie wstrzymają go bez końca."""
    sh = (REPO / "scripts" / "install-fleet.sh").read_text(encoding="utf-8")
    assert "s6-svc -r /run/service/dashboard" not in sh
    assert "/command/s6-svc -wd -T 40000 -d /run/service/dashboard" in sh
    assert "/command/s6-svc -u /run/service/dashboard" in sh
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert "printf '30000\\n' > /etc/s6-overlay/s6-rc.d/dashboard/timeout-kill" in docker
