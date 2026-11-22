"""Mózg aplikacji (docs/HQ.md „Mózg”): źródła z konfig/mozg.json, graf i pełna treść notatek z pliku
(hq/plugin/mozg_zrodla.py), trasy GET /mozg/zrodla, /mozg/<klucz> i /mozg/<klucz>/notatka, wspólny graf zakładki Wiedza
shared/web/graf.js w node albo bun (800+ węzłów płynnie, Barnes-Hut, sterownik na atrapie canvasa), części, szukanie
i układ mapy-neuronu w 63-mozg.js / 63-mozg-neuron.js."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from conftest import REPO, load_script

MZ = load_script("hq/plugin/mozg_zrodla.py", "jarvo_test_mozg_zrodla")
NODE = shutil.which("node") or shutil.which("bun")
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


def test_czesci_mozgu_z_konfiguracji(klient, tmp_path):
    c, konfig, _ = klient
    plik = _graf_operatora(tmp_path)
    czesci = [{"nazwa": "Ludzie", "foldery": ["podmioty", "a/b", 3], "ikona": "users", "opis": "o", "drugorzedna": "tak"},
              {"nazwa": "Ludzie", "foldery": [], "ikona": "<svg>", "drugorzedna": True}, {"nazwa": "bez folderów"}, "zle"]
    konfig.write_text(json.dumps({"kategorie": czesci, "zrodla": [{"nazwa": "G", "graf": str(plik), "kategorie": czesci[:1]}]}),
                      encoding="utf-8")
    sk, g = c.get("/mozg/zrodla").json()["zrodla"]
    assert sk["klucz"] == "jarvo" and sk["kategorie"] == [
        {"k": "ludzie", "nazwa": "Ludzie", "foldery": ["podmioty"], "opis": "o", "ikona": "users"},
        {"k": "ludzie-2", "nazwa": "Ludzie", "foldery": [], "drugorzedna": True}]
    assert g["kategorie"] == sk["kategorie"][:1] and "graf" not in g
    assert MZ.kategorie({"nazwa": "x"}) == [] and len(MZ.kategorie([{"nazwa": f"n{i}", "foldery": []} for i in range(20)])) == 12
    konfig.write_text(json.dumps({"kategorie": "zle"}), encoding="utf-8")
    assert c.get("/mozg/zrodla").json() == {"zrodla": [MZ.SKARBIEC]}


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


def test_pelna_tresc_notatki_tylko_z_katalogu_zrodla(klient, tmp_path):
    c, konfig, _ = klient
    wiki = tmp_path / "wiki"
    (wiki / "modele").mkdir(parents=True)
    (wiki / "modele" / "gemma 4.md").write_text("---\ntyp: model\n---\n# Gemma 4\nTreść z [[KOLEJKA]].\n", encoding="utf-8")
    (tmp_path / "sekret.md").write_text("nie wolno", encoding="utf-8")
    konfig.write_text(json.dumps([{"nazwa": "K", "klucz": "k", "graf": str(_graf_operatora(tmp_path)), "notatki": str(wiki), "rozmowca": "s:gpu"},
                                  {"nazwa": "Z", "klucz": "z", "graf": "x.json", "rozmowca": "jarvo; rm"}]), encoding="utf-8")
    k, z = c.get("/mozg/zrodla").json()["zrodla"][1:]
    assert k["tresc"] is True and k["rozmowca"] == "s:gpu" and "notatki" not in k and "_notatki" not in k
    assert "tresc" not in z and "rozmowca" not in z            # bez katalogu nie ma treści, zły rozmówca odpada
    assert c.get("/mozg/k/notatka", params={"id": "modele/gemma 4"}).json() == {"id": "modele/gemma 4", "tresc": "# Gemma 4\nTreść z [[KOLEJKA]].\n"}
    for zly in ("../sekret", "modele/../../sekret", "/etc/passwd", "", "modele/", "nie-ma"):
        assert c.get("/mozg/k/notatka", params={"id": zly}).status_code == 404, zly
    (wiki / "wyjscie.md").symlink_to(tmp_path / "sekret.md")
    assert c.get("/mozg/k/notatka", params={"id": "wyjscie"}).status_code == 404
    assert c.get("/mozg/z/notatka", params={"id": "a"}).status_code == 404
    assert c.get("/mozg/k/notatka", params={"id": "modele/gemma 4"}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_publiczny_kod_bez_prywatnych_sciezek():
    for p in (REPO / "hq" / "plugin" / "mozg_zrodla.py", REPO / "hq" / "web" / "src" / "63-mozg.js", REPO / "hq" / "web" / "src" / "63-mozg-neuron.js", GRAF_JS):
        t = p.read_text(encoding="utf-8")
        assert "~/mozg" not in t and "/home/" not in t and ":8091" not in t


def test_graf_wiedzy_raz_w_zakladce_wiedza():
    hqbuild = load_script("scripts/hqbuild.py", "jarvo_test_hqbuild_mozg")
    wiedza = hqbuild.bundle_js(REPO / "wiedza" / "web" / "src", "x", wspolne=(hqbuild.GRAF_WSPOLNY,))
    assert wiedza.count("function utworzGraf(") == 1 and "function Graph(" in wiedza
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
// skupiska (Mózg): grupa = folder i przybita etykieta każdej grupy
const SKUPISKA = process.argv[3] === "skupiska";
if (SKUPISKA) { for (const q of wezly) q.grupa = q.folder; for (let i = 0; i < 7; i++) wezly.push({ id: `@f${i}`, grupa: `f${i}`, stale: true, r: 15 }); }
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
// skupiska: zasięg węzłów każdej grupy od jej kotwicy; dwa skupiska nie nachodzą na siebie
const zasieg = sim.grupy.map((gr) => Math.max(0, ...gr.nodes.filter((q) => !q.stale).map((q) => Math.hypot(q.x - gr.x, q.y - gr.y))));
let nachodza = 0;
sim.grupy.forEach((a, i) => sim.grupy.forEach((b, j) => { if (i < j && Math.hypot(a.x - b.x, a.y - b.y) < zasieg[i] + zasieg[j]) nachodza++; }));
console.log(JSON.stringify({ liczby, maks, klatki: n, spokoj: s.alpha <= 0.003, czeka, otwarte, k: s.k, k2,
  skonczone: s.wezly.every((q) => Number.isFinite(q.x) && Number.isFinite(q.y)), zdarzenia: Object.keys(zdarzenia).length,
  grupy: sim.grupy.length, nachodza, mosty: sim.mosty.length, przybite: s.wezly.filter((q) => q.stale).every((q) => q.x === q.g.x && q.y === q.g.y) }));
"""


@pytest.mark.skipif(not NODE, reason="brak node")
@pytest.mark.parametrize("n,tryb", [(120, ""), (1200, ""), (1200, "skupiska")])
def test_graf_plynny_i_zasypia(tmp_path, n, tryb):
    skrypt = tmp_path / "g.js"
    skrypt.write_text(ATRAPA % GRAF_JS.read_text(encoding="utf-8"), encoding="utf-8")
    r = subprocess.run([NODE, str(skrypt), str(n), tryb], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    w = json.loads(r.stdout)
    assert w["liczby"]["wezly"] == n + (7 if tryb else 0) and w["liczby"]["linki"] > n
    assert w["skonczone"] and w["spokoj"], w
    # płynnie: klatka mieści się w ~16 ms (budżet układu 10 ms + rysowanie), z zapasem na wolną maszynę CI
    assert w["maks"] < 40, w
    # uspokojony graf nie zamawia kolejnych klatek (bateria telefonu)
    assert w["czeka"] == 0 and w["klatki"] < 400
    assert w["otwarte"] == [f"f3/n10"] and w["k2"] > w["k"] * 1.5
    assert w["zdarzenia"] == 0
    if tryb:
        # 7 skupisk rozłącznych, etykiety w kotwicach, linki między folderami jako mosty (każda para sąsiadów)
        assert w["grupy"] == 7 and w["nachodza"] == 0 and w["przybite"] and w["mosty"] == 7, w
    else:
        assert w["grupy"] == 1 and w["mosty"] == 0


WIDOK = r"""
global.window = {}; const isPL = () => true; const L = (a) => a; const html = () => null; const zadanie = () => null;
%s
const n = (id, o = {}) => { const t = mozgTytul({ id, tytul: o.tytul || id.split("/").pop() }); return { id, hub: false, typ: "", zmieniono: "", ...o, _t: t, _p: mozgProste(t), _s: mozgProste(`${t} ${o.tytul || ""} ${id}`) }; };
const wezly = [n("_hub-skarbiec", { hub: true }), n("user/_hub-ty", { hub: true, tytul: "Ty" }), n("user/kim jestem", { typ: "fakt" }),
  n("agenci/_hub-agenci", { hub: true, tytul: "Agenci" }), n("agenci/jarvo-web/_hub-web", { hub: true, tytul: "🌐 Web Senior Dev (jarvo-web)" }),
  n("agenci/jarvo-web/lekcja a", { typ: "lekcja", zmieniono: "2026-11-10" }), n("agenci/jarvo-web/fakt b", { typ: "fakt" }),
  n("agenci/jarvo-x/samotna", { typ: "lekcja" }), n("fleet/skille/s1", { typ: "skill" }), n("fleet/skille/s2", { typ: "skill" }),
  n("fleet/skille/s3", { typ: "skill" }), n("zrodla/jarvo-repo/HQ"), n("inne/x"), n("Łódź/zażółć", { tytul: "Zażółć gęślą" }),
  n("agenci/jarvo/_hub-jarvo", { hub: true, tytul: "🛰️ Main Judge (jarvo)" }), n("agenci/jarvo/lekcja j", { typ: "lekcja" })];
const m = mozgMapa(wezly, MOZG_KATEGORIE), zespol = m.kat.find((d) => d.k === "zespol"), web = zespol.grupy[0];
const hash = mozgHash({ z: "jarvo", k: "zespol", g: "agenci/jarvo-web", o: "a (b)" });
const cel = (t) => (t === "agenci/jarvo-web/lekcja a" ? ["#h", "Lekcja A"] : null);
const u = neuronUklad(m, [{ z: "agenci/jarvo-web/lekcja a", do: "fleet/skille/s1" }, { z: "fleet/skille/s1", do: "agenci/jarvo-web/lekcja a" },
  { z: "user/kim jestem", do: "nie/ma" }, { z: "user/kim jestem", do: "user/kim jestem" }], mozgKolejnosc);
const ids = u.kropki.map((k) => k.id), nachodza = [];
for (const c of u.czesci) c.grupy.forEach((a, i) => c.grupy.forEach((b, j) => { if (i < j && Math.hypot(a.x - b.x, a.y - b.y) < a.r + b.r) nachodza.push([c.k, a.k, b.k]); }));
for (let i = 0; i < u.czesci.length; i++) for (let j = i + 1; j < u.czesci.length; j++) {
  const [a, b] = [u.czesci[i].bb, u.czesci[j].bb];
  if (a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]) nachodza.push([u.czesci[i].k, u.czesci[j].k]);
}
const trasa = neuronTrasa(u, u.byId.get("agenci/jarvo-web/lekcja a"), u.byId.get("fleet/skille/s1"));
console.log(JSON.stringify({
  glowne: m.glowne.map((d) => [d.k, d.ile]), boczne: m.kat.filter((d) => d.drugorzedna).map((d) => [d.k, d.hub && d.hub.id]),
  zespol: [zespol.hub.id, zespol.grupy.map((x) => [x.k, x.nazwa, x.ile])], ty: m.kat[0].hub.id, samotna: m.gdzie.get("agenci/jarvo-x/samotna"),
  sekcje: mozgSekcje(web.wezly).map((x) => [x.nazwa, x.wezly.map((q) => q._t)]),
  szukaj: [mozgSzukaj(wezly, "ZAZOL")[0].map((q) => q._t), mozgSzukaj(wezly, "web")[0].map((q) => q.id), mozgSzukaj(wezly, "web", 1)[1], mozgSzukaj(wezly, " ")[1],
    mozgSzukaj(wezly, "main judge")[0].map((q) => [q.id, q._t])],
  uklad: { ile: ids.length, unikalne: new Set(ids).size, czesci: u.czesci.map((c) => c.k), linki: u.linki.length, nachodza,
    skonczone: u.kropki.every((k) => Number.isFinite(k.x) && Number.isFinite(k.y)) && trasa.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y)),
    trasa: [trasa[0], trasa[trasa.length - 1]], konce: [[u.byId.get("agenci/jarvo-web/lekcja a").x, u.byId.get("agenci/jarvo-web/lekcja a").y], [u.byId.get("fleet/skille/s1").x, u.byId.get("fleet/skille/s1").y]] },
  hash, stan: mozgStan(hash), pusty: mozgHash({ z: "", k: "", g: "", o: "" }),
  wiki: mozgWiki("x [[agenci/jarvo-web/lekcja a]] i [[nie ma|N]] <!-- c -->\n## Powiązane\n- [[y]]\n## Dalej\nz", cel),
  url: mozgUrl({ notatka_url: "https://h/{id}.html" }, "a b/c") }));
"""


@pytest.mark.skipif(not NODE, reason="brak node")
def test_czesci_grupy_szukanie_i_adresy(tmp_path):
    src = "\n".join((REPO / "hq" / "web" / "src" / p).read_text(encoding="utf-8") for p in ("63-mozg-neuron.js", "63-mozg.js"))
    skrypt = tmp_path / "w.js"
    skrypt.write_text(WIDOK % src, encoding="utf-8")
    r = subprocess.run([NODE, str(skrypt)], capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert r.returncode == 0, r.stderr
    w = json.loads(r.stdout)
    # wejście: części z notatkami (puste znikają), foldery spoza listy jako własne części, źródła na boku
    assert w["glowne"] == [["ty", 1], ["zespol", 7], ["f-inne", 1], ["f-Łódź", 1]]
    assert w["boczne"] == [["zrodla", "_hub-skarbiec"]]
    # grupy: podkatalog z hubem zostaje (nazwa z huba bez „(jarvo-web)”), mały bez huba wraca do folderu;
    # agent `jarvo` to dla właściciela „Jarvo”, nie tytuł roli z huba („Main Judge”); `fleet` w całości jedną grupą
    # „Umiejętności”, ostatnią w Zespole
    assert w["zespol"] == ["agenci/_hub-agenci", [["agenci/jarvo-web", "🌐 Web Senior Dev", 2], ["agenci", "Agenci", 1],
                                                  ["agenci/jarvo", "Jarvo", 1], ["fleet", "Umiejętności", 3]]]
    assert w["ty"] == "user/_hub-ty" and w["samotna"] == {"kat": "zespol", "grupa": "agenci"}
    assert w["sekcje"] == [["Lekcje", ["lekcja a"]], ["Fakty", ["fakt b"]]]
    assert w["szukaj"] == [["Zażółć gęślą"], ["agenci/jarvo-web/_hub-web", "agenci/jarvo-web/fakt b", "agenci/jarvo-web/lekcja a"], 3, 0,
                           [["agenci/jarvo/_hub-jarvo", "Jarvo"]]]
    # mapa-neuron: każda notatka części z notatkami raz (także huby i hub korzenia w „Dokumentacji”), skupiska grup
    # w części i części między sobą bez nachodzenia, link bez kierunku raz, do nieistniejącej notatki i do siebie wcale,
    # włókno zaczyna się i kończy w kropkach
    uk = w["uklad"]
    assert uk["ile"] == uk["unikalne"] == 16 and uk["czesci"] == ["ty", "zespol", "zrodla", "f-inne", "f-Łódź"]
    assert uk["linki"] == 1 and uk["nachodza"] == [] and uk["skonczone"]
    assert uk["trasa"] == uk["konce"]
    assert w["hash"] == "#/mozg?k=zespol&g=agenci%2Fjarvo-web&o=a%20%28b%29" and w["pusty"] == "#/mozg"
    assert w["stan"] == {"z": "", "k": "zespol", "g": "agenci/jarvo-web", "o": "a (b)"}
    assert w["wiki"] == "x [Lekcja A](#h) i N \n## Dalej\nz"
    assert w["url"] == "https://h/a%20b/c.html"


def test_czesci_mozgu_zgodne_z_folderami_skarbca():
    """Jedna definicja folderów (wiedza.py FOLDERY_SKARBCA): każdy folder skarbca ma dokładnie jedną część w Mózgu
    (MOZG_KATEGORIE w 63-mozg.js), Mózg nie zna folderów spoza niej; tożsamość to pierwsza część, archiwum drugorzędna."""
    wiedza = load_script("wiedza/wiedza.py", "jarvo_test_wiedza_foldery_mozgu")
    src = (REPO / "hq" / "web" / "src" / "63-mozg.js").read_text(encoding="utf-8")
    blok = re.search(r"^const MOZG_KATEGORIE = \[\n(.*?)^\];", src, re.M | re.S).group(1)
    czesci = re.findall(r'\{ k: "([a-z]+)".*?foldery: \[([^\]]*)\](.*?)\},?\n', blok, re.S)
    foldery = [f for _k, lista, _r in czesci for f in re.findall(r'"([^"]*)"', lista)]
    assert len(foldery) == len(set(foldery)), foldery
    assert set(foldery) == set(wiedza.FOLDERY_SKARBCA)
    gdzie = {f: (k, "drugorzedna: true" in reszta) for k, lista, reszta in czesci for f in re.findall(r'"([^"]*)"', lista)}
    assert czesci[0][0] == "jarvo" and gdzie[wiedza.TOZSAMOSC] == ("jarvo", False)
    assert gdzie[wiedza.ARCHIWUM] == ("archiwum", True) and gdzie["zrodla"][1] and gdzie["skrzynka"][1]
    # tożsamość w tej samej kolejności co w INDEX-ie i hubach (wiedza.KOLEJNOSC_TOZSAMOSCI; Mózg porównuje nazwy plików)
    kolejnosc = re.search(r"^const MOZG_TOZSAMOSC = \[([^\]]*)\];", src, re.M).group(1)
    assert re.findall(r'"([^"]*)"', kolejnosc) == [p.split("/")[-1] for p in wiedza.KOLEJNOSC_TOZSAMOSCI]
