"""Branding dashboardu: nowe nazwy zmienionych plików (cache przeglądarki) i skórka terminala; w instalacji natywnej
łatka kopii dista (--web --natywnie: bez „Update Hermes”, checkout Hermesa czysty) i jej katalog w <program>/web-dist
(jarvo/hermes.py, dist_jarva)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest
import yaml

from conftest import REPO, load_script

sys.path.insert(0, str(REPO))
from jarvo import hermes, sciezki  # noqa: E402

PATCH = REPO / "branding" / "patch_dashboard.py"
NODE = shutil.which("node")

# fragmenty dista Hermesa 0.21.5 (index-*.js i SystemPage-*.js) z innymi nazwami zmiennych niż w oryginale: powłoka
# (jak w tests/test_powloka.py) i miejsca aktualizacji Hermesa (H16): 5 × can_update_hermes, 2 × checkHermesUpdate(!1)
DIST_INDEX = """import{a as Zx}from"./vendor-1a2b3c.js";
function Qn(e,t){let n=Zx(e,t),r=new Set(e.map(e=>e.path));return n.filter(x=>!r.has(x.path))}
function Korzen(){return(0,$q.jsx)(Nv,{to:`/sessions`,replace:!0})}
function Nieznany(){return(0,$q.jsx)(Nv,{to:`/sessions`,replace:!0})}
const Pasek={id:`app-sidebar`,className:`fixed`};
const Nagl=`lg:hidden fixed top-0 left-0 right-0 z-40 min-h-14`,Zasl=`lg:hidden fixed inset-0 z-40 p-0 block`;
const Odst=`h-14 shrink-0 lg:hidden`;
export function On(a,X,T){let m=a?.can_update_hermes===!0;return T(!0),X.checkHermesUpdate(!1).then(t=>[m,t])}
export const strona=()=>import("./SystemPage-5d6e7f.js");
"""
DIST_SYSTEM = """export async function Laduj(N,r,t){const on=async(e=!1)=>{if(r?.can_update_hermes!==!1){await N.checkHermesUpdate(e)}};
const deps=[t,r?.can_update_hermes];const ap=()=>{if(r?.can_update_hermes===!1)return `poza`;return `aktualizuj`};
let fn=r?.can_update_hermes!==!1;const [h,u]=await Promise.all([N.getHooks(),N.checkHermesUpdate(!1)]);
return {fn,deps:deps.length,ap:ap(),u,on:typeof on}}
"""
INDEX_HTML = """<!doctype html>
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


def _dist(katalog, index: str = DIST_INDEX, system: str = DIST_SYSTEM):
    (katalog / "assets").mkdir(parents=True)
    (katalog / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (katalog / "assets" / "index-9f8e7d.js").write_text(index, encoding="utf-8")
    (katalog / "assets" / "SystemPage-5d6e7f.js").write_text(system, encoding="utf-8")
    (katalog / "assets" / "vendor-1a2b3c.js").write_text("export const a=(e,t)=>e;\n", encoding="utf-8")
    return katalog


def _latka(*argv, env=None):
    return subprocess.run([sys.executable, str(PATCH), str(REPO / "branding"), *map(str, argv)], capture_output=True,
                          text=True, encoding="utf-8", timeout=120, env={**os.environ, **(env or {})})


def _plik(katalog, przedrostek: str) -> str:
    pliki = list((katalog / "assets").glob(f"{przedrostek}-*.js"))
    assert len(pliki) == 1, pliki
    return pliki[0].read_text(encoding="utf-8")


def test_latka_natywna_kopii_dista_bez_aktualizacji_hermesa(tmp_path):
    """--web --natywnie: powłoka /jarvo jak w obrazie i ściśle 5 + 2 miejsca aktualizacji Hermesa (H16); pliki
    Pythona checkoutu (strona logowania) zostają bez zmian, nawet gdy JARVO_HERMES_DIR wskazuje checkout."""
    hermes_dir = tmp_path / "hermes"
    login = hermes_dir / "hermes_cli" / "dashboard_auth" / "login_page.py"
    login.parent.mkdir(parents=True)
    login.write_text(LOGIN_FIXTURE, encoding="utf-8")
    dist = _dist(tmp_path / "web-dist" / "abc")
    r = _latka("--web", dist, "--natywnie", env={"JARVO_HERMES_DIR": str(hermes_dir)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "bez_aktualizacji_hermesa: 5" in r.stdout and "bez_sprawdzania_aktualizacji: 2" in r.stdout
    index, system = _plik(dist, "index"), _plik(dist, "SystemPage")
    assert "can_update_hermes" not in index + system
    assert "m=!1/*jarvo-bez-aktualizacji*/===!0" in index
    assert "Promise.resolve(null)/*jarvo-bez-sprawdzania*/.then(" in index
    assert system.count("/*jarvo-bez-aktualizacji*/") == 4 and "N.checkHermesUpdate(e)" in system
    assert 'new Set([...e.map(e=>e.path),"/jarvo"])' in index           # powłoka jak w obrazie
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert "<title>Jarvo</title>" in html and 'id="jarvo-powloka-js"' in html
    assert login.read_text(encoding="utf-8") == LOGIN_FIXTURE          # checkout Hermesa czysty (S12)
    assert (dist / "favicon.ico").is_file()
    # druga łatka niczego nie zmienia
    przed = {p.name: p.read_bytes() for p in (dist / "assets").iterdir()}
    r = _latka("--web", dist, "--natywnie")
    assert r.returncode == 0 and r.stdout.count("już jest") == 4
    assert {p.name: p.read_bytes() for p in (dist / "assets").iterdir()} == przed


@pytest.mark.skipif(not NODE, reason="brak node")
def test_latka_natywna_daje_poprawny_js_z_wylaczona_aktualizacja(tmp_path):
    """Kod po łatce się wykonuje: przycisk aktualizacji ukryty (fn i m = false), sprawdzenia nie ma (null bez sieci),
    a „Aktualizuj” w System mówi, że aktualizacje są poza panelem."""
    dist = _dist(tmp_path / "dist")
    assert _latka("--web", dist, "--natywnie").returncode == 0
    system = next((dist / "assets").glob("SystemPage-*.js"))
    index = next((dist / "assets").glob("index-*.js"))
    proba = tmp_path / "proba.mjs"
    proba.write_text(
        f'import{{Laduj}}from"./dist/assets/{system.name}";import{{On}}from"./dist/assets/{index.name}";'
        'const N={getHooks:async()=>1,checkHermesUpdate:async()=>{throw new Error("sieć")}};'
        'const w=await Laduj(N,{can_update_hermes:true},"t");const z=await On({can_update_hermes:true},N,()=>0);'
        'console.log(JSON.stringify([w,z]))', encoding="utf-8")
    out = subprocess.run([NODE, str(proba)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    w, z = json.loads(out.stdout)
    assert w == {"fn": False, "deps": 2, "ap": "poza", "u": None, "on": "function"}
    assert z == [False, None]


def test_bez_flagi_natywnie_obraz_bez_zmian(tmp_path):
    """W obrazie (bez --natywnie) Hermes sam chowa aktualizację (kontener): miejsca can_update_hermes zostają."""
    dist = _dist(tmp_path / "dist")
    r = _latka("--web", dist)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "bez_aktualizacji" not in r.stdout and _plik(dist, "SystemPage").count("can_update_hermes") == 4


def test_latka_natywna_scisla(tmp_path):
    """Inna liczba miejsc aktualizacji (nowy Hermes) = kod 1 i nazwa wpisu; index.html bez powłoki."""
    dist = _dist(tmp_path / "dist", system=DIST_SYSTEM + "export const x=(r)=>r?.can_update_hermes;\n")
    r = _latka("--web", dist, "--natywnie")
    assert r.returncode == 1 and "bez_aktualizacji_hermesa" in r.stderr
    assert 'id="jarvo-powloka' not in (dist / "index.html").read_text(encoding="utf-8")
    pusty = tmp_path / "pusty"
    pusty.mkdir()
    r = _latka("--web", pusty, "--natywnie")
    assert r.returncode == 1 and "index.html" in r.stderr


def _uklad(tmp_path) -> sciezki.Uklad:
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "jarvo")})
    u.stan.mkdir(parents=True, exist_ok=True)
    return u


def test_dist_jarva_w_katalogu_programu(tmp_path):
    """jarvo/hermes.py: kopia dista z łatkami w <program>/web-dist/<skrót> i opis obok (poza distem, bo dashboard
    podaje każdy plik dista); front w checkoucie bez zmian; gotowa kopia = bez łatania; inny branding = nowy katalog."""
    u = _uklad(tmp_path)
    zrodlo = _dist(tmp_path / "checkout" / "hermes_cli" / "web_dist")
    przed = {p.relative_to(zrodlo).as_posix(): p.read_bytes() for p in zrodlo.rglob("*") if p.is_file()}
    logi: list[str] = []
    wynik = hermes.dist_jarva(u, zrodlo, log=logi.append)
    assert wynik.parent == u.program / "web-dist" and len(wynik.name) == 16
    assert 'id="jarvo-powloka"' in (wynik / "index.html").read_text(encoding="utf-8")
    opis = json.loads((u.program / "web-dist" / f"{wynik.name}.json").read_text(encoding="utf-8"))
    assert opis["skrot"].startswith(wynik.name) and opis["zrodlo"] == str(zrodlo)
    assert not list(wynik.glob("*.json")) and not list((u.program / "web-dist").glob("*.new"))
    assert {p.relative_to(zrodlo).as_posix(): p.read_bytes() for p in zrodlo.rglob("*") if p.is_file()} == przed
    assert not any("✓" in x for x in logi)                           # wiersze łatki nie zasypują logu instalacji
    # drugi przebieg: ta sama kopia, bez łatania
    znacznik = (wynik / "index.html").stat().st_mtime_ns
    assert hermes.dist_jarva(u, zrodlo, log=logi.append) == wynik
    assert (wynik / "index.html").stat().st_mtime_ns == znacznik and "już jest" in logi[-1]
    # nowa wersja brandingu = nowy katalog obok (stary zostaje dla działającego panelu)
    brand = tmp_path / "branding"
    shutil.copytree(REPO / "branding", brand)
    (brand / "powloka.js").write_text((brand / "powloka.js").read_text(encoding="utf-8") + "\n// zmiana\n",
                                      encoding="utf-8")
    nowy = hermes.dist_jarva(u, zrodlo, brand=brand, log=logi.append)
    assert nowy != wynik and nowy.parent == wynik.parent and (wynik / "index.html").is_file()


def test_dist_jarva_niepasujaca_latka_zostawia_front_hermesa(tmp_path):
    """Łatka nie pasuje do dista (nowy układ plików Hermesa) albo nie ma brandingu: ostrzeżenie w logu i front
    Hermesa bez zmian (panel działa; CI łapie to testem E2E), bez resztek kopii."""
    u = _uklad(tmp_path)
    zrodlo = _dist(tmp_path / "web_dist", index=DIST_INDEX.replace("id:`app-sidebar`,", ""))
    logi: list[str] = []
    assert hermes.dist_jarva(u, zrodlo, log=logi.append) == zrodlo
    assert any("UWAGA" in x and "Update Hermes" in x for x in logi)
    assert not list((u.program / "web-dist").iterdir())
    logi.clear()
    assert hermes.dist_jarva(u, zrodlo, brand=tmp_path / "brak", log=logi.append) == zrodlo
    assert "UWAGA" in logi[-1]


def test_bust_cache_renames_changed_files_and_importers(tmp_path):
    pd = load_script("branding/patch_dashboard.py")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "i18n-AAAA11.js").write_text("export const brand = `Jarvo`;", encoding="utf-8")
    (assets / "page-BBBB22.js").write_text('import{b}from"./i18n-AAAA11.js";export default 1;', encoding="utf-8")
    (assets / "vendor-CCCC33.js").write_text("export const v = 1;", encoding="utf-8")
    (assets / "index-DDDD44.js").write_text('import"./page-BBBB22.js";const m=["assets/vendor-CCCC33.js"];', encoding="utf-8")
    index = tmp_path / "index.html"
    index.write_text('<script src="/assets/index-DDDD44.js"></script><link href="/assets/vendor-CCCC33.js">', encoding="utf-8")
    pd.CHANGED.clear()
    pd.CHANGED.add(assets / "i18n-AAAA11.js")
    assert pd.bust_cache(assets, index) == 3          # i18n + importujący ją page + importujący page index
    names = sorted(p.name for p in assets.iterdir())
    assert "vendor-CCCC33.js" in names                 # niezmieniony zostaje (cache dalej ważny)
    assert not any(n in names for n in ("i18n-AAAA11.js", "page-BBBB22.js", "index-DDDD44.js"))
    new_index = next(n for n in names if n.startswith("index-"))
    new_page = next(n for n in names if n.startswith("page-"))
    new_i18n = next(n for n in names if n.startswith("i18n-"))
    assert new_index in index.read_text(encoding="utf-8")
    assert new_page in (assets / new_index).read_text(encoding="utf-8")
    assert new_i18n in (assets / new_page).read_text(encoding="utf-8")
    assert "vendor-CCCC33.js" in (assets / new_index).read_text(encoding="utf-8")


def test_patch_pisze_konce_linii_lf_na_kazdym_systemie(tmp_path):
    """Łatki dista i plików Hermesa zapisują „\\n” także na Windows: te same bajty co w obrazie."""
    pd = load_script("branding/patch_dashboard.py")
    index = tmp_path / "index.html"
    index.write_bytes(b"<html>\n<head><title>Hermes Agent</title></head>\n</html>\n")
    pd.CHANGED.clear()
    assert pd.sub_all([index], r"<title>[^<]*</title>", "<title>Jarvo</title>", "tytuł karty") == 1
    assert index.read_bytes() == b"<html>\n<head><title>Jarvo</title></head>\n</html>\n"


def test_skin_and_profiles_use_jarvo_branding():
    skin = yaml.safe_load((REPO / "branding" / "skin-jarvo.yaml").read_text(encoding="utf-8"))
    assert skin["name"] == "jarvo" and skin["branding"]["agent_name"] == "Jarvo"
    for name in ["_host", "jarvo", "jarvo-sherlock", "jarvo-web", "jarvo-studio", "jarvo-reka"]:
        cfg = yaml.safe_load((REPO / "profiles" / name / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["display"]["skin"] == "jarvo", name
    ico = (REPO / "branding" / "favicon.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00"                # prawdziwy plik ICO, nie SVG pod złą nazwą


FAKE_I18N = (
    "var s={af:`Afrikaans`,de:`Deutsch`,en:`English`};"
    "var d={common:{save:`Save`,cancel:`Cancel`},app:{nav:{sessions:`Sessions`}}},h={common:{save:`Speichern`}},"
    "k={en:d,zh:h,de:h},M=`hermes-locale`;"
    "function N(e){return Object.keys(k).includes(e)}"
    "function P(){try{let e=localStorage.getItem(M);if(e&&N(e))return e}catch{}return`en`}"
    "export{k as TR,P as initial};"
)


def test_add_polish_injects_locale_and_defaults(tmp_path):
    import json
    import subprocess

    pd = load_script("branding/patch_dashboard.py")
    chunk = tmp_path / "i18n-XYZ.mjs"
    chunk.write_text(FAKE_I18N, encoding="utf-8")
    index = tmp_path / "index.html"
    index.write_text('<html lang="en"><body></body></html>', encoding="utf-8")
    pl = tmp_path / "pl.json"
    pl.write_text(json.dumps({"common": {"save": "Zapisz"}, "app": {"nav": {"sessions": "Sesje"}}}), encoding="utf-8")
    pd.CHANGED.clear()
    assert pd.add_polish([chunk], index, pl) == 1
    assert pd.add_polish([chunk], index, pl) == 0            # drugi raz nic nie dopisuje
    assert 'lang="pl"' in index.read_text(encoding="utf-8")
    text = chunk.read_text(encoding="utf-8")
    assert "pl:`Polski`" in text
    # tłumaczenie scalone z angielskim: brakujący klucz = tekst angielski; polski domyślny bez wyboru
    probe = tmp_path / "probe.mjs"
    probe.write_text(
        f'import{{TR,initial}}from"./{chunk.name}";globalThis.localStorage={{getItem:()=>null}};'
        "console.log(JSON.stringify([TR.pl.common.save,TR.pl.common.cancel,TR.pl.app.nav.sessions,Object.keys(TR)[1],initial()]))",
        encoding="utf-8")
    out = subprocess.run(["node", str(probe)], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    assert json.loads(out) == ["Zapisz", "Cancel", "Sesje", "pl", "pl"]


def test_polish_translation_covers_dashboard_sections():
    import json

    pl = json.loads((REPO / "branding" / "i18n" / "pl.json").read_text(encoding="utf-8"))
    for section in ("common", "app", "status", "sessions", "cron", "config", "env", "kanban", "achievements"):
        assert section in pl
    assert pl["app"]["nav"]["plugin_jarvo-hq"] == "Jarvo"
    # placeholdery zostają jak w oryginale
    assert "{count}" in pl["sessions"]["selectedCount"] and "{what}" in pl["common"]["loadFailed"]


LOGIN_FIXTURE = """\
_LOGIN_HTML_TEMPLATE = \"\"\"\\
<!doctype html>
<html lang="en">
<head><title>Sign in — Jarvo</title>
<style>
  :root {{ --midground: #ffac02; }}
</style></head>
<body><main>
  <div class="brand">Nous<span class="dot"></span>Research</div>
  <div class="card"><h1>Sign in</h1>
    <p class="subtitle">Choose a sign-in method to continue to Jarvo HQ.</p>
{provider_buttons}
  </div>
  <footer><span class="sep"></span>Public bind &middot; Auth required<span class="sep"></span></footer>
</main>{password_script}</body></html>
\"\"\"

_EMPTY_HTML = \"\"\"\\
<html lang="en"><head><title>Sign-in unavailable — Jarvo</title>
<style>
  :root { --midground: #ffac02; }
</style></head><body><h1>Sign-in unavailable</h1></body></html>
\"\"\"


def _password_form(plabel):
    return (
        f'        <div class="form-title">Sign in with {plabel}</div>\\n'
        f'          <span class="field-label">Username</span>\\n'
        f'          <span class="field-label">Password</span>\\n'
        f'        <button class="provider-btn" type="submit">Sign in</button>\\n'
    )
"""


def test_login_page_gets_jarvo_brand_polish_and_fonts(tmp_path):
    pd = load_script("branding/patch_dashboard.py")
    hermes = tmp_path / "hermes"
    login = hermes / "hermes_cli" / "dashboard_auth" / "login_page.py"
    login.parent.mkdir(parents=True)
    (hermes / "hermes_cli" / "web_dist").mkdir()
    login.write_text(LOGIN_FIXTURE, encoding="utf-8")
    pd.HERMES, pd.WEB = hermes, hermes / "hermes_cli" / "web_dist"
    pd.patch_login(login, REPO / "branding")
    pd.patch_login(login, REPO / "branding")                      # drugi raz nic nie dokleja
    text = login.read_text(encoding="utf-8")
    assert text.count("---- Jarvo: strona tytułowa logowania") == 1   # szablon logowania
    assert text.count("---- Jarvo: biel i czerwień") == 1             # strona „brak metod”
    for word in ("Nous", "Sign in", "Public bind", "Username", ">Password<", 'lang="en"'):
        assert word not in text, word
    for word in ("Zaloguj</button>", "Użytkownik", "Hasło", "Logowanie niedostępne", "from idea to reality.",
                 "Twój zespół agentów już czeka.", "klucz=", "Klucz jednorazowy", "j-robot-oczy"):
        assert word in text, word
    for font in ("VT323-400-latin.woff2", "instrument-serif-latin-400-normal.woff2", "inter-latin-wght-normal.woff2",
                 "jetbrains-mono-latin-wght-normal.woff2", "caveat-latin-wght-normal.woff2"):
        assert (pd.WEB / "fonts" / font).is_file(), font
    assert "url('/fonts/instrument-serif-latin-400-normal.woff2')" in text
    # szablon Hermesa to str.format: po łatce musi się formatować, a strona „brak metod” zostaje zwykłym CSS
    ns: dict = {}
    exec(compile(text, "login_page.py", "exec"), ns)
    html = ns["_LOGIN_HTML_TEMPLATE"].format(provider_buttons=ns["_password_form"]("Jarvo"), password_script="<!--hasło-->")
    assert '<body class="j">' in html and 'class="j-robot"' in html and "{{" not in html and "@@" not in html
    assert html.index('<div class="form-title">') < html.index("<!--hasło-->") < html.index("klucz=([A-Za-z0-9-]")
    assert "--midground: #D4213D;" in ns["_EMPTY_HTML"] and "{{" not in ns["_EMPTY_HTML"]
