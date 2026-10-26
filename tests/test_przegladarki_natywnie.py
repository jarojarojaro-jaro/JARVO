"""Przeglądarki i wyszukiwarka natywnie (docs/NATYWNIE.md E5: F02, F03, F04): audit.py i brand_extract.py Weba
zamiast skryptów bash, search_fanout.py Sherlocka z wyszukiwarką „najlepszą dostępną” (I14) i pamięć HTTP oraz
nagranie HAR Łowcy. Narzędzia npm, Node i dembrandt to atrapy (tests/atrapy.py), bez sieci i bez przeglądarki.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

import atrapy
from conftest import load_script

AUDIT = load_script("profiles/jarvo-web/scripts/audit.py", "audit")       # brand_extract.py importuje go jako `audit`
BRAND = load_script("profiles/jarvo-web/scripts/brand_extract.py")
FANOUT = load_script("profiles/jarvo-sherlock/scripts/search_fanout.py")
AB = load_script("infra/bin/agent_browser.py", "agent_browser_przegladarki")
WINDOWS = os.name == "nt"
PYTHON_BAZOWY = Path(sys.base_prefix) / "python.exe" if WINDOWS else Path(sys.executable)


def program(katalog: Path, nazwa: str, kod: str) -> Path:
    """Atrapa jak prawdziwy program: na Windows .exe (launcher z agent_browser.program), bo .cmd przepuszcza argumenty
    przez cmd.exe (adres z „&” to tam dwa polecenia); na POSIX atrapy.program."""
    if not WINDOWS:
        return atrapy.program(katalog, nazwa, kod)
    katalog.mkdir(parents=True, exist_ok=True)
    try:
        dane = AB.program(PYTHON_BAZOWY, kod.encode("utf-8"), opis="# atrapa")
    except FileNotFoundError as e:
        pytest.skip(str(e))
    (katalog / f"{nazwa}.exe").write_bytes(dane)
    return katalog / f"{nazwa}.exe"

# atrapa node: rozpoznaje skrypt po nazwie (a11y.cjs, screenshots.cjs, bin paczek npm) i pisze to, co prawdziwy
NODE = r'''
import json, os, sys
from pathlib import Path
skrypt, args = Path(sys.argv[1]).name, sys.argv[2:]
with open(os.environ["LOG_NODE"], "a", encoding="utf-8") as f:
    f.write(json.dumps([skrypt, *args], ensure_ascii=False) + "\n")
if skrypt == "a11y.cjs":
    Path(args[1]).write_text(json.dumps({"by_impact": {"serious": 1}}), encoding="utf-8")
elif skrypt == "screenshots.cjs":
    Path(args[1]).mkdir(parents=True, exist_ok=True)
    (Path(args[1]) / "screenshots.json").write_text(json.dumps({"results": [{"width": 375, "horizontal_scroll": True}]}),
                                                     encoding="utf-8")
elif skrypt == "lighthouse.js":
    wyjscie = next(a.split("=", 1)[1] for a in args if a.startswith("--output-path="))
    raport = {"categories": {"performance": {"score": 0.91}}, "audits": {
        "largest-contentful-paint": {"displayValue": "1.2 s"}, "total-byte-weight": {"numericValue": 204800},
        "third-parties-insight": {"details": {"items": [{"entity": {"text": "Google"}, "transferSize": 51200,
                                                          "mainThreadTime": 120}]}}}}
    Path(wyjscie + ".report.json").write_text(json.dumps(raport), encoding="utf-8")
    Path(wyjscie + ".report.html").write_text("<html></html>", encoding="utf-8")
elif skrypt == "linkinator.js":
    print(json.dumps({"links": [{"url": "http://x/", "state": "OK", "status": 200},
                                {"url": "http://x/brak", "state": "BROKEN", "status": 404}]}))
    sys.exit(1)
elif skrypt == "dembrandt.js":
    if "--json-only" in args:
        print(json.dumps({"wcag": {"ok": 3}, "colors": ["#123"]}))
    else:
        d = Path("output") / "x.pl"
        d.mkdir(parents=True, exist_ok=True)
        (d / "DESIGN.md").write_text("# Design", encoding="utf-8")
        (d / "x.tokens.json").write_text("{}", encoding="utf-8")
        with open(os.environ["LOG_NODE"], "a", encoding="utf-8") as f:
            f.write(json.dumps(["env", os.environ.get("PLAYWRIGHT_BROWSERS_PATH")]) + "\n")
'''


def paczka(node_modules: Path, nazwa: str, bin_: dict | str, plik: str) -> None:
    katalog = node_modules / nazwa
    (katalog / Path(plik).parent).mkdir(parents=True, exist_ok=True)
    (katalog / plik).write_text("// atrapa", encoding="utf-8")
    (katalog / "package.json").write_text(json.dumps({"name": nazwa, "bin": bin_}), encoding="utf-8")


@pytest.fixture
def npm(tmp_path, monkeypatch):
    """NODE_PATH z paczkami floty (bin z package.json jak w prawdziwych) i atrapa node w PATH."""
    nm = tmp_path / "node_modules"
    paczka(nm, "lighthouse", {"lighthouse": "cli/lighthouse.js", "chrome-debug": "x.js"}, "cli/lighthouse.js")
    paczka(nm, "linkinator", {"linkinator": "./build/src/linkinator.js"}, "build/src/linkinator.js")
    paczka(nm, "dembrandt", {"dembrandt": "dist/dembrandt.js"}, "dist/dembrandt.js")
    (nm / "playwright-core").mkdir()
    (nm / "playwright-core" / "package.json").write_text("{}", encoding="utf-8")
    (nm / "playwright-core" / "browsers.json").write_text(json.dumps({"browsers": [
        {"name": "chromium", "revision": "1243"}, {"name": "chromium-headless-shell", "revision": "1243"}]}),
        encoding="utf-8")
    bin_dir = tmp_path / "bin"
    program(bin_dir, "node", NODE)
    monkeypatch.setenv("NODE_PATH", os.pathsep.join([str(nm), str(tmp_path / "inne")]))
    monkeypatch.setenv("PATH", atrapy.sciezka(bin_dir))
    monkeypatch.setenv("LOG_NODE", str(tmp_path / "node.jsonl"))
    for zmienna in ("CHROME_PATH", "PLAYWRIGHT_BROWSERS_PATH"):
        monkeypatch.delenv(zmienna, raising=False)
    return types.SimpleNamespace(nm=nm, log=tmp_path / "node.jsonl")


def wywolania(log: Path) -> list[list[str]]:
    return [json.loads(w) for w in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


# ------------------------------------------------------------------ Web: audit.py

def test_program_npm_ze_skryptem_paczki_zamiast_nakladki_bin(npm, tmp_path):
    """Node na skrypcie `bin` paczki z NODE_PATH: na Windows nakładka .cmd rozbiłaby adres z „&”."""
    nm = npm.nm
    lh = AUDIT.program_npm("lighthouse")
    assert Path(lh[0]).stem == "node" and lh[1] == str(nm / "lighthouse" / "cli/lighthouse.js")
    assert AUDIT.program_npm("linkinator")[1] == str(nm / "linkinator" / "./build/src/linkinator.js")
    paczka(nm, "napis", "bin/n.js", "bin/n.js")                                     # "bin" jako napis
    assert AUDIT.program_npm("napis")[1] == str(nm / "napis" / "bin/n.js")
    assert AUDIT.program_npm("nie-ma-takiej") is None
    program(tmp_path / "bin", "nie-ma-takiej", "pass\n")                           # zapas: program z PATH
    assert Path(AUDIT.program_npm("nie-ma-takiej")[0]).stem == "nie-ma-takiej"


def test_piaskownica_chromium_wylaczana_tylko_na_linuksie_gdy_trzeba(monkeypatch):
    """--no-sandbox tylko na Linuksie jako root, w kontenerze albo z zakazem przestrzeni nazw użytkownika; Windows
    i macOS zawsze z piaskownicą (jak Hermes)."""
    for platforma in ("win32", "darwin"):
        assert AUDIT.bez_piaskownicy(platforma) is False
    monkeypatch.setattr(AUDIT.os, "geteuid", lambda: 0, raising=False)
    assert AUDIT.bez_piaskownicy("linux") is True
    monkeypatch.setattr(AUDIT, "bez_piaskownicy", lambda: True)
    assert AUDIT.flagi_chrome() == "--headless=new --no-sandbox --disable-gpu"
    monkeypatch.setattr(AUDIT, "bez_piaskownicy", lambda: False)
    assert AUDIT.flagi_chrome() == "--headless=new --disable-gpu"


def test_audit_wszystkie_narzedzia_i_podsumowanie(npm, tmp_path, monkeypatch, capsys):
    """Każde narzędzie osobno, status na stderr, summary.json jak w dawnym audit.sh plus bezpieczeństwo strony;
    kod 1 z poprawnym JSON-em = narzędzie działa i coś znalazło."""
    tu = tmp_path / "skrypty"
    tu.mkdir()
    for nazwa, kod, wynik in (("seo_check.py", 1, {"summary": {"errors": 2, "warnings": 1}}),
                              ("security_check.py", 1, {"podsumowanie": {"KRYTYCZNE": 0, "WYSOKIE": 1}})):
        (tu / nazwa).write_text(f"import json, sys\nprint(json.dumps({wynik!r}))\nsys.exit({kod})\n", encoding="utf-8")
    for nazwa in ("a11y.cjs", "screenshots.cjs"):
        (tu / nazwa).write_text("// atrapa", encoding="utf-8")
    monkeypatch.setattr(AUDIT, "HERE", tu)
    monkeypatch.setattr(AUDIT, "bez_piaskownicy", lambda: False)
    chrome = tmp_path / "chs" / "chrome-headless-shell"
    monkeypatch.setenv("CHROME_PATH", str(chrome))
    out = tmp_path / "out" / "audyt"
    assert AUDIT.main(["https://x.pl/?a=1&b=2", str(out)]) == 0
    io = capsys.readouterr()
    summary = json.loads(io.out)
    assert json.loads((out / "summary.json").read_text(encoding="utf-8")) == summary
    assert summary["lighthouse"]["mobile"]["scores"] == {"performance": 91}
    assert summary["lighthouse"]["desktop"]["strona_kb"] == 200
    assert summary["lighthouse"]["mobile"]["firmy_trzecie"] == {"kb": 50, "watek_ms": 120,
                                                                "firmy": [{"firma": "Google", "kb": 50, "watek_ms": 120}]}
    assert summary["axe"] == {"serious": 1} and summary["links"]["broken"] == 1
    assert summary["seo"] == {"errors": 2, "warnings": 1} and summary["security"] == {"KRYTYCZNE": 0, "WYSOKIE": 1}
    assert summary["screenshots"] == [{"width": 375, "horizontal_scroll": True}]
    for narzedzie, status in (("lighthouse-mobile", "ok"), ("axe", "ok"), ("links", "ok (są znaleziska)"),
                              ("seo", "ok (są znaleziska)"), ("security", "ok (są znaleziska)"), ("screenshots", "ok")):
        assert f"  {narzedzie}: {status}\n" in io.err, narzedzie
    lh = [w for w in wywolania(npm.log) if w[0] == "lighthouse.js"]
    assert len(lh) == 2 and all("--chrome-flags=--headless=new --disable-gpu" in w for w in lh)
    assert "--form-factor=mobile" in lh[0] and "--preset=desktop" in lh[1]
    assert lh[0][1] == "https://x.pl/?a=1&b=2"                                     # adres z „&” w całości
    link = next(w for w in wywolania(npm.log) if w[0] == "linkinator.js")
    assert link[link.index("--skip") + 1] == "^(?!https://x.pl/?a=1&b=2)"
    assert (out / "links.json").is_file() and (out / "seo.json").is_file() and (out / "security.json").is_file()


def test_audit_linki_z_kodem_chwilowym_sprawdza_drugi_raz():
    """Pierwsza sesja 26.10: linkinator wpisał 27 linków z 429 (limit żądań serwera) jako martwe, a w przeglądarce
    działały. Druga próba idzie po kolei, z przerwą: odpowiada = OK, trwały błąd = BROKEN, dalej 429 = NIESPRAWDZONY."""
    odpowiedzi = {"https://x.pl/a": [(429, 2.0), (200, 0)], "https://x.pl/b": [(429, 0)] * 3,
                  "https://x.pl/c": [(0, 0), (404, 0)]}
    pytania, przerwy = [], []

    def kod(url):
        pytania.append(url)
        return odpowiedzi[url].pop(0)

    linki = [{"url": "https://x.pl/a", "state": "BROKEN", "status": 429},
             {"url": "https://x.pl/b", "state": "BROKEN", "status": 429},
             {"url": "https://x.pl/c", "state": "BROKEN", "status": 0},
             {"url": "https://x.pl/d", "state": "BROKEN", "status": 404},              # trwały: bez drugiej próby
             {"url": "https://x.pl/", "state": "OK", "status": 200}]
    assert AUDIT.sprawdz_ponownie(linki, kod_http=kod, czekaj=przerwy.append, zegar=lambda: 0.0) == 3
    assert [(x["state"], x["status"]) for x in linki] == [("OK", 200), ("NIESPRAWDZONY", 429), ("BROKEN", 404),
                                                         ("BROKEN", 404), ("OK", 200)]
    assert "https://x.pl/d" not in pytania and linki[0]["pierwszy_status"] == 429
    assert przerwy[0] == 3.0 and max(przerwy) <= 10.0                             # Retry-After, ale nie dłużej niż 10 s


def test_audit_podsumowanie_linkow_oddziela_niesprawdzone(tmp_path):
    (tmp_path / "links.json").write_text(json.dumps({"links": [
        {"url": "https://x.pl/", "state": "OK", "status": 200}, {"url": "https://x.pl/brak", "state": "BROKEN", "status": 404},
        {"url": "https://x.pl/limit", "state": "NIESPRAWDZONY", "status": 429}]}), encoding="utf-8")
    linki = AUDIT.podsumowanie(tmp_path)["links"]
    assert linki["checked"] == 3 and linki["broken"] == 1 and linki["examples"] == ["https://x.pl/brak (404)"]
    assert linki["niesprawdzone"] == 1 and linki["niesprawdzone_przyklady"] == ["https://x.pl/limit"]
    assert "nie są martwe linki" in linki["uwaga"]


def test_audit_brak_narzedzia_nie_zatrzymuje_reszty(npm, tmp_path, monkeypatch, capsys):
    import shutil
    shutil.rmtree(npm.nm / "lighthouse")
    tu = tmp_path / "skrypty"
    tu.mkdir()
    for nazwa in ("seo_check.py", "security_check.py"):
        (tu / nazwa).write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
    monkeypatch.setattr(AUDIT, "HERE", tu)
    assert AUDIT.main(["https://x.pl", str(tmp_path / "a")]) == 0
    err = capsys.readouterr().err
    assert "lighthouse-mobile: brak programu" in err and "seo: błąd" in err and "links: ok (są znaleziska)" in err


# ------------------------------------------------------------------ Web: brand_extract.py

@pytest.fixture
def skarbiec(tmp_path, monkeypatch):
    k = tmp_path / "Michał Żółć" / "knowledge"
    (k / "brands" / "_szablon").mkdir(parents=True)
    (k / "brands" / "_szablon" / "BRAND.md").write_text("# Marka", encoding="utf-8")
    monkeypatch.setenv("JARVO_KNOWLEDGE_DIR", str(k))
    monkeypatch.setattr(BRAND, "bez_piaskownicy", lambda: False)
    return k


def chrome_z_instalacji(tmp_path) -> Path:
    """Układ jak w manifeście: <wersja>/chrome-headless-shell-<platforma>/chrome-headless-shell[.exe]."""
    chrome = tmp_path / "narzedzia" / "chrome-headless-shell" / "153.0.8010.12" / "chrome-headless-shell-win64" / \
        "chrome-headless-shell.exe"
    chrome.parent.mkdir(parents=True)
    chrome.write_bytes(b"x")
    return chrome


def test_brand_extract_kit_marki_i_chromium_z_instalacji(npm, skarbiec, tmp_path, monkeypatch, capsys):
    """dembrandt dostaje PLAYWRIGHT_BROWSERS_PATH z chromium_headless_shell-<rewizja> wskazującym chrome-headless-shell
    z instalacji (inaczej pobrałby przeglądarkę bez sumy); dowiązanie znika, a instalacja Chromium zostaje."""
    chrome = chrome_z_instalacji(tmp_path)
    monkeypatch.setenv("CHROME_PATH", str(chrome))
    assert BRAND.main(["https://x.pl", "marka-x", "--pages", "2"]) == 0
    wynik = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    kit = skarbiec / "brands" / "marka-x"
    assert wynik == {"kit": kit.as_posix(), "design_md": True, "tokens": True}
    assert json.loads((kit / "wcag.json").read_text(encoding="utf-8")) == {"ok": 3}
    assert (kit / "BRAND.md").read_text(encoding="utf-8") == "# Marka" and (kit / "logo").is_dir()
    w = wywolania(npm.log)
    assert w[0][0] == "dembrandt.js" and w[0][1:] == ["https://x.pl", "--crawl", "2", "--slow", "--json-only"]
    pbp = next(x[1] for x in w if x[0] == "env")
    assert Path(pbp).name == "przegladarki" and not Path(pbp).exists()            # katalog roboczy posprzątany
    assert chrome.is_file()


def test_brand_extract_strona_referencyjna_bez_logo_i_szablonu(npm, skarbiec, tmp_path, monkeypatch, capsys):
    pbp = tmp_path / "pw"
    (pbp / "chromium_headless_shell-1243").mkdir(parents=True)                   # układ instalacji: bez dowiązania
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(pbp))
    assert BRAND.main(["https://x.pl", "x.pl", "--kit", "inspiracje/strony/domy/x.pl"]) == 0
    kit = skarbiec / "inspiracje" / "strony" / "domy" / "x.pl"
    assert (kit / "DESIGN.md").is_file() and not (kit / "logo").exists() and not (kit / "BRAND.md").exists()
    assert next(x[1] for x in wywolania(npm.log) if x[0] == "env") == str(pbp)


@pytest.mark.parametrize("kit", ["/abs/sciezka", "../poza", "brands/../../x", r"brands\x", "C:/x", ""])
def test_brand_extract_kit_tylko_wzgledny_w_skarbcu(npm, skarbiec, kit, capsys):
    assert BRAND.main(["https://x.pl", "s", "--kit", kit]) == 2
    assert "--kit" in capsys.readouterr().err and wywolania(npm.log) == []


def test_brand_extract_bez_chromium_nie_pozwala_pobierac(npm, skarbiec, capsys):
    assert BRAND.main(["https://x.pl", "marka"]) == 1
    assert "bez sumy" in capsys.readouterr().err and wywolania(npm.log) == []


# ------------------------------------------------------------------ Sherlock: search_fanout.py

class DDGS:
    zapytania: list = []

    def __init__(self, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def text(self, query, region=None, timelimit=None, max_results=None):
        DDGS.zapytania.append(("text", query, region, timelimit))
        return [{"title": "A", "href": "https://www.a.pl/x/?utm_source=q", "body": "opis"},
                {"title": "B", "href": f"https://b.pl/{region}", "body": "b"}]

    def news(self, query, region=None, timelimit=None, max_results=None):
        DDGS.zapytania.append(("news", query, region, timelimit))
        return [{"title": "N", "url": "https://a.pl/x", "body": "news", "date": "2026-10-01", "source": "Rzeczpospolita"}]


def test_fanout_bez_searxng_z_ddgs(monkeypatch, capsys):
    """Natywnie bez SEARXNG_URL: DuckDuckGo przez ddgs (region z języka, news dla kategorii news), ten sam wynik."""
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=DDGS))
    DDGS.zapytania.clear()
    assert FANOUT.main(["fraza", "--lang", "pl", "--lang", "en", "--category", "general", "--category", "news",
                        "--time", "month"]) == 0
    w = json.loads(capsys.readouterr().out)
    assert w["wyszukiwarka"] == "ddgs" and w["errors"] == []
    assert ("text", "fraza", "pl-pl", "m") in DDGS.zapytania and ("news", "fraza", "us-en", "m") in DDGS.zapytania
    pierwszy = w["results"][0]
    assert pierwszy["hits"] == 4 and "Rzeczpospolita" in pierwszy["engines"]      # a.pl/x z 4 zapytań (utm, www)


def test_fanout_bez_wyszukiwarki_radzi_web_search(monkeypatch, capsys):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setitem(sys.modules, "ddgs", None)                                 # import ddgs → ImportError
    assert FANOUT.main(["fraza"]) == 2
    assert "web_search" in json.loads(capsys.readouterr().out)["error"]


def test_fanout_searxng_ma_pierwszenstwo(monkeypatch, capsys):
    monkeypatch.setenv("SEARXNG_URL", "http://searxng:8080")
    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=DDGS))
    monkeypatch.setattr(FANOUT, "search", lambda base, q, lang, cat, t: [
        {"url": "https://s.pl", "title": "S", "snippet": "", "engines": ["bing"], "published": None, "category": cat,
         "lang": lang}])
    assert FANOUT.main(["fraza", "--lang", "pl"]) == 0
    w = json.loads(capsys.readouterr().out)
    assert w["wyszukiwarka"] == "searxng" and w["results"][0]["url"] == "https://s.pl"


# ------------------------------------------------------------------ Łowca: pamięć HTTP i nagranie HAR

def test_lowca_pamiec_w_danych_jarva(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "profiles" / "jarvo-lowca" / "scripts"))
    import lowca_lib as ll
    monkeypatch.delenv("LOWCA_CACHE", raising=False)
    monkeypatch.setenv("JARVO_DATA_DIR", str(tmp_path / "dane" / "jarvo"))
    assert ll._pamiec() == tmp_path / "dane" / "jarvo" / "cache" / "lowca"
    monkeypatch.setenv("LOWCA_CACHE", str(tmp_path / "c"))
    assert ll._pamiec() == tmp_path / "c"
    monkeypatch.delenv("LOWCA_CACHE")
    monkeypatch.delenv("JARVO_DATA_DIR")
    assert ll._pamiec().parts[-2:] == (".cache", "jarvo-lowca")


def test_lowca_nagranie_har_przez_node_z_pelna_sciezka(tmp_path, monkeypatch, capsys):
    zrodlo = load_script("profiles/jarvo-lowca/scripts/zrodlo.py", "zrodlo_lowcy")
    monkeypatch.setattr(zrodlo.strona, "robots", lambda url: types.SimpleNamespace(can_fetch=lambda ua, u: True))
    monkeypatch.setenv("PATH", str(tmp_path / "pusto"))
    assert zrodlo.nagraj("https://x.pl", str(tmp_path / "a.har")) == 1
    assert "brak programu node" in capsys.readouterr().err
    log = tmp_path / "node.jsonl"
    program(tmp_path / "bin", "node", "import json, os, sys\n"
            f"open({str(log)!r}, 'w').write(json.dumps(sys.argv[1:] + [os.environ['JARVO_UA']]))\n")
    monkeypatch.setenv("PATH", atrapy.sciezka(tmp_path / "bin"))
    assert zrodlo.nagraj("https://x.pl", str(tmp_path / "a.har"), czekaj=1.5, przewin=True) == 0
    args = json.loads(log.read_text())
    assert Path(args[0]).name == "har.cjs" and args[1:6] == ["https://x.pl", str(tmp_path / "a.har"), "--czekaj",
                                                              "1500", "--przewin"]
    assert "jarvo-lowca" in args[-1]
