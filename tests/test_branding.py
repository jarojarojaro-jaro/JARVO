"""Branding dashboardu: nowe nazwy zmienionych plików (cache przeglądarki) i skórka terminala."""

from __future__ import annotations

import yaml

from conftest import REPO, load_script


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
