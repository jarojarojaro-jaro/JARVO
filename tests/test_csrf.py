"""Ochrona zapisu (CSRF) wtyczek dashboardu: hq/plugin/ochrona.py w jarvo-hq i jarvo-wiedza (docs/HQ.md §3).

Strony agentów (:9120) i serwery deweloperskie na innych portach localhost są dla przeglądarki tą samą witryną co
dashboard, więc ciasteczko SameSite=Lax jedzie z ich formularzami. Tu: macierz reguł bez FastAPI, każda trasa zapisu
obu routerów ma ochronę (przejście po routerach), odpowiedź 403 {"blad": …}, kopia pliku w wtyczce Wiedzy i trasa
testowa /csrf-proba tylko z JARVO_E2E=1.
"""
from __future__ import annotations

import ast
import re
import importlib.util
import sys

import pytest

from conftest import REPO, load_script

OCHRONA = REPO / "hq" / "plugin" / "ochrona.py"
API_HQ = REPO / "hq" / "plugin" / "plugin_api.py"
API_WIEDZA = REPO / "wiedza" / "plugin" / "dashboard" / "plugin_api.py"
JSON = "application/json"


@pytest.fixture(scope="module")
def ochrona():
    return load_script("hq/plugin/ochrona.py", "jarvo_test_ochrona")


# --------------------------------------------------------------- reguły (bez FastAPI)

@pytest.mark.parametrize("metoda,naglowki,ok", [
    # strona innej witryny: przeglądarka zawsze dokłada Sec-Fetch-Site
    ("POST", {"Sec-Fetch-Site": "cross-site", "Origin": "https://zla.example", "Content-Type": "text/plain"}, False),
    # strona agenta z :9120 (ta sama witryna, inne pochodzenie): formularz text/plain i fetch JSON
    ("POST", {"Sec-Fetch-Site": "same-site", "Origin": "http://localhost:9120", "Host": "localhost:9119",
              "Content-Type": "text/plain"}, False),
    ("POST", {"Sec-Fetch-Site": "same-site", "Origin": "http://localhost:9120", "Host": "localhost:9119",
              "Content-Type": JSON, "X-Jarvo-Request": "1"}, False),
    # ramka z sandbox (nieprzezroczyste pochodzenie)
    ("POST", {"Sec-Fetch-Site": "cross-site", "Origin": "null", "Content-Type": "text/plain"}, False),
    # stara przeglądarka bez Sec-Fetch-Site: Origin musi być tym samym serwerem
    ("POST", {"Origin": "null", "Host": "localhost:9119", "Content-Type": JSON}, False),
    ("POST", {"Origin": "http://localhost:9120", "Host": "localhost:9119", "Content-Type": JSON}, False),
    ("POST", {"Origin": "http://localhost:9119", "Host": "localhost:9119", "Content-Type": "text/plain"}, False),
    ("POST", {"Origin": "http://LOCALHOST:9119", "Host": "localhost:9119", "Content-Type": JSON}, True),
    # za proxy z TLS schemat bywa inny niż w Host; liczy się serwer (host:port)
    ("POST", {"Origin": "https://jarvo.example", "Host": "jarvo.example", "Content-Type": JSON}, True),
    ("POST", {"Origin": "ftp://localhost:9119", "Host": "localhost:9119", "Content-Type": JSON}, False),
    # curl i skrypty: bez Origin i Sec-Fetch-Site tylko z własnym nagłówkiem
    ("POST", {}, False),
    ("POST", {"Content-Type": JSON}, False),
    ("POST", {"X-Jarvo-Request": "1"}, True),
    ("POST", {"X-Jarvo-Request": "0", "Content-Type": JSON}, False),
    # panel: same-origin z JSON albo z nagłówkiem (wysyłka pliku)
    ("POST", {"Sec-Fetch-Site": "same-origin", "Content-Type": "application/json; charset=utf-8"}, True),
    ("POST", {"Sec-Fetch-Site": "same-origin", "Content-Type": "multipart/form-data; boundary=x"}, False),
    ("POST", {"Sec-Fetch-Site": "same-origin", "Content-Type": "application/octet-stream", "X-Jarvo-Request": "1"}, True),
    ("PUT", {"sec-fetch-site": "same-site", "content-type": JSON}, False),
    ("DELETE", {}, False),
    ("PATCH", {"X-Jarvo-Request": "1"}, True),
    # odczyt nie zmienia stanu
    ("GET", {"Sec-Fetch-Site": "cross-site"}, True),
    ("HEAD", {}, True),
    ("OPTIONS", {"Origin": "http://localhost:9120"}, True),
])
def test_macierz_regul(ochrona, metoda, naglowki, ok):
    powod = ochrona.powod_odmowy(metoda, naglowki)
    assert (powod is None) is ok, powod


def test_powod_bez_tresci(ochrona):
    """Powód do dziennika jest krótki i nie zawiera treści żądania (najwyżej 80 znaków Origin)."""
    powod = ochrona.powod_odmowy("POST", {"Origin": "http://x/" + "a" * 500, "Host": "y"})
    assert powod.startswith("origin=") and len(powod) <= 90


# --------------------------------------------------------------- kod wtyczek (bez FastAPI)

def _routery(sciezka):
    drzewo = ast.parse(sciezka.read_text(encoding="utf-8"))
    return [n for n in ast.walk(drzewo) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "APIRouter"]


@pytest.mark.parametrize("sciezka", [API_HQ, API_WIEDZA], ids=["jarvo-hq", "jarvo-wiedza"])
def test_router_z_klasa_trasy(sciezka):
    """Jeden router na wtyczkę i zawsze z route_class=ochrona.Trasa: nowa trasa POST dostaje ochronę sama."""
    wywolania = _routery(sciezka)
    assert len(wywolania) == 1, sciezka
    kw = {k.arg: ast.unparse(k.value) for k in wywolania[0].keywords}
    assert kw.get("route_class") == "ochrona.Trasa"


def test_kopia_w_wiedzy_identyczna(tmp_path):
    """scripts/build.py kopiuje ochrona.py do wtyczki Wiedzy bajt w bajt (jedna logika, dwa miejsca)."""
    build = load_script("scripts/build.py", "jarvo_test_build_csrf")
    out = build.build_wiedza_plugin(tmp_path / "jarvo-wiedza")
    assert (out / "dashboard" / "ochrona.py").read_bytes() == OCHRONA.read_bytes()


# --------------------------------------------------------------- routery na żywo (FastAPI)

def _api_hq(monkeypatch, e2e: bool):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    if e2e:
        monkeypatch.setenv("JARVO_E2E", "1")
    else:
        monkeypatch.delenv("JARVO_E2E", raising=False)
    return load_script("hq/plugin/plugin_api.py", f"jarvo_test_csrf_hq_{int(e2e)}")


def _api_wiedza(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("JARVO_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("JARVO_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    for nazwa in ("jarvo_wiedza_panel", "jarvo_wiedza_ochrona"):
        sys.modules.pop(nazwa, None)
    spec = importlib.util.spec_from_file_location("jarvo_test_csrf_wiedza", API_WIEDZA)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jarvo_test_csrf_wiedza"] = mod
    spec.loader.exec_module(mod)
    return mod


def _trasy(router):
    return [t for t in router.routes if hasattr(t, "dependant")]


def _sprawdz_router(api, nazwa):
    # każda trasa to Trasa: zwykła trasa Starlette (router.add_route, router.mount) ominęłaby route_class, a _trasy
    # (tylko trasy z .dependant) by jej nie zobaczyło
    obce = [f"{type(t).__name__} {getattr(t, 'path', '?')}" for t in api.router.routes if not isinstance(t, api.ochrona.Trasa)]
    assert not obce, f"{nazwa}: trasy spoza ochrona.Trasa: {obce}"
    zapis = [t for t in _trasy(api.router) if set(t.methods) & api.ochrona.METODY_ZAPISU]
    assert zapis, f"{nazwa}: brak tras zapisu"
    bez = [f"{sorted(t.methods)} {t.path}" for t in zapis if not api.ochrona.ma_ochrone(t)]
    assert not bez, f"{nazwa}: trasy zapisu bez ochrony: {bez}"
    # odczyt bez ochrony (GET nie zmienia stanu) i bez metod spoza listy
    for t in _trasy(api.router):
        assert set(t.methods) <= {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}, t.path
        if not set(t.methods) & api.ochrona.METODY_ZAPISU:
            assert not api.ochrona.ma_ochrone(t), t.path
    return zapis


def test_kazda_trasa_zapisu_hq(monkeypatch):
    api = _api_hq(monkeypatch, e2e=False)
    zapis = _sprawdz_router(api, "jarvo-hq")
    sciezki = {t.path for t in zapis}
    assert {"/chat/{name}/send", "/upload", "/konwerter", "/edit/save", "/update"} <= sciezki
    assert "/csrf-proba" not in sciezki            # trasa testowa tylko z JARVO_E2E=1


def test_kazda_trasa_zapisu_wiedza(tmp_path, monkeypatch):
    api = _api_wiedza(tmp_path, monkeypatch)
    zapis = _sprawdz_router(api, "jarvo-wiedza")
    assert {t.path for t in zapis} == {"/rulings", "/remark", "/compile", "/reindex"}


def test_odczyty_hq_bez_skutkow(monkeypatch):
    """Audyt: trasy GET niczego nie zapisują (lista znana; nowa trasa GET = przejrzyj, czy niczego nie zapisuje).
    Najwyżej pamięć podręczna w procesie. Link podglądu animacji wydaje token (zapis w state/preview-links.json, przy
    ponad 500 linkach wypycha najstarsze), więc to POST /anim/info, nie GET."""
    api = _api_hq(monkeypatch, e2e=False)
    get = {t.path for t in _trasy(api.router) if "GET" in t.methods}
    assert get == {
        "/state", "/fleet", "/agent/{name}", "/task/{task_id}", "/file", "/edit/info", "/edit/maska", "/edit/media",
        "/edit/dzwieki", "/edit/dzwiek-plik", "/edit/muzyka", "/edit/stamp", "/edit/srt", "/edit/speech",
        "/edit/proxy-file", "/edit/job/{jid}", "/anim/check", "/host", "/chat/{name}/history",
        "/konwerter/cele", "/konwerter/job/{jid}", "/flota", "/health", "/update", "/zasoby/{nazwa:path}",
        # rozmowy (trasy_rozmow.py): odczyt rozmowy.db i state.db profili tylko do odczytu; strumień trzyma
        # w pamięci procesu połączenie i jego subskrypcje
        "/rozmowy", "/rozmowy/{wid}", "/rozmowy/{wid}/os", "/przebiegi/{pid}", "/strumien"}
    zapis = {t.path for t in _trasy(api.router) if "POST" in t.methods}
    assert "/anim/info" in zapis


def test_odczyty_wiedzy_bez_skutkow(tmp_path, monkeypatch):
    """Audyt Wiedzy: trasy GET czytają skarbiec; najwyżej odświeżają pliki pochodne z jego treści (indeks wyszukiwania,
    raport LINT.md), nic z treści żądania. Zapis (orzeczenia, uwagi, kompilacja, reindeks) to POST."""
    api = _api_wiedza(tmp_path, monkeypatch)
    get = {t.path for t in _trasy(api.router) if "GET" in t.methods}
    assert get == {"/overview", "/tree", "/note", "/graph", "/search", "/inbox", "/log", "/recall", "/lint",
                   "/rulings", "/compile"}


def test_ochrona_przezywa_include_router(monkeypatch):
    """Dashboard montuje router przez app.include_router. Starsze FastAPI (np. 0.133 z obrazu Hermesa) tworzy przy tym
    trasy od nowa, nowsze (0.156+) dołącza router bez kopiowania tras, więc sprawdzamy zachowanie, nie wnętrze
    FastAPI: każda trasa zapisu po dołączeniu odrzuca zwykły formularz 403 csrf, a ochrona jest jedna, nie podwójna."""
    fastapi = pytest.importorskip("fastapi")
    api = _api_hq(monkeypatch, e2e=True)
    prefiks = "/api/plugins/jarvo-hq"
    k = _klient(api, prefiks)
    zapis = [t for t in _trasy(api.router) if set(t.methods) & api.ochrona.METODY_ZAPISU]
    assert zapis
    for t in zapis:
        sciezka = re.sub(r"\{([^}:]+)(:[^}]*)?\}", "x", t.path)
        for metoda in sorted(set(t.methods) & api.ochrona.METODY_ZAPISU):
            r = k.request(metoda, prefiks + sciezka, content="x=1", headers={"Content-Type": "text/plain"})
            assert r.status_code == 403 and r.json()["blad"]["kod"] == "csrf", (metoda, t.path, r.status_code)
    app = fastapi.FastAPI()
    app.include_router(api.router, prefix=prefiks)
    stare = [t for t in app.routes if hasattr(t, "dependant") and set(t.methods) & {"POST"}]
    for t in stare:   # starsze FastAPI: trasa skopiowana przez include_router ma dalej dokładnie jedną ochronę
        assert type(t) is api.ochrona.Trasa, t.path
        assert sum(getattr(d, "call", None) is api.ochrona.wymagaj_zapisu for d in t.dependant.dependencies) == 1, t.path


def _klient(api, prefiks):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    app = fastapi.FastAPI()
    app.include_router(api.router, prefix=prefiks)
    return TestClient(app)


def test_odpowiedz_403_i_trasa_testowa(monkeypatch, capsys):
    api = _api_hq(monkeypatch, e2e=True)
    k = _klient(api, "/api/plugins/jarvo-hq")
    u = "/api/plugins/jarvo-hq/csrf-proba"
    r = k.post(u, content="x=1", headers={"Content-Type": "text/plain"})
    assert r.status_code == 403 and r.json() == api.ochrona.ODPOWIEDZ
    wyjscie = capsys.readouterr()          # dziennik jarvo.hq (stdout dashboardu) albo stderr, gdy go nie ma
    assert "odrzucony zapis (csrf) POST /api/plugins/jarvo-hq/csrf-proba" in wyjscie.out + wyjscie.err
    assert api.ochrona.ODMOWY["razem"] >= 1
    r = k.post(u, content="x", headers={"Sec-Fetch-Site": "same-site", "Origin": "http://localhost:9120",
                                       "Content-Type": "text/plain"})
    assert r.status_code == 403
    assert k.post(u, headers={"X-Jarvo-Request": "1"}).json() == {"ok": True}
    assert k.post(u, json={}, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200
    # odczyt bez nagłówków działa jak dawniej
    assert k.get("/api/plugins/jarvo-hq/zasoby/nie-ma.js").status_code == 404


def test_wiedza_403_bez_zapisu(tmp_path, monkeypatch):
    """Formularz text/plain na /remark: 403 i żaden szkic nie powstaje (trasa nie rusza skarbca)."""
    api = _api_wiedza(tmp_path, monkeypatch)
    wywolane = []
    monkeypatch.setattr(api.PANEL, "add_remark", lambda *a: wywolane.append(a) or {"szkic": "x"})
    k = _klient(api, "/api/plugins/jarvo-wiedza")
    r = k.post("/api/plugins/jarvo-wiedza/remark", content='{"path":"a.md","uwaga":"zla uwaga"}',
               headers={"Content-Type": "text/plain", "Origin": "null", "Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403 and r.json()["blad"]["kod"] == "csrf" and not wywolane
    r = k.post("/api/plugins/jarvo-wiedza/remark", json={"path": "a.md", "uwaga": "dobra uwaga"},
               headers={"X-Jarvo-Request": "1"})
    assert r.status_code == 200 and wywolane == [("a.md", "dobra uwaga")]


def test_front_wysyla_naglowek():
    """Panel HQ (fetch i XHR wysyłki pliku) i zakładka Wiedza wysyłają X-Jarvo-Request: 1."""
    api_js = (REPO / "hq" / "web" / "src" / "10-api.js").read_text(encoding="utf-8")
    assert '"X-Jarvo-Request": "1"' in api_js
    assert api_js.count("SDK.fetchJSON(") == 1           # tylko w jsonFetch: każde zapytanie JSON z nagłówkiem
    assert "authHeaders(" in api_js.split("new XMLHttpRequest", 1)[1].split("xhr.send", 1)[0]   # wysyłka pliku (XHR)
    wiedza_js = (REPO / "wiedza" / "web" / "src" / "00-base.js").read_text(encoding="utf-8")
    assert '"X-Jarvo-Request": "1"' in wiedza_js
