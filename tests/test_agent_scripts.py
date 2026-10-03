"""Skrypty narzędziowe snajperów: SEO, rejestr źródeł i cytowania, pakiet misji, kontrola mediów."""

from __future__ import annotations

import json
import re
import zipfile

import pytest

from conftest import REPO, load_script

seo = load_script("profiles/jarvo-web/scripts/seo_check.py")
sources = load_script("profiles/jarvo-sherlock/scripts/sources.py")
pack = load_script("profiles/jarvo-reka/scripts/pack.py")
media = load_script("profiles/jarvo-studio/scripts/check_media.py")

GOOD_HTML = """<!doctype html>
<html lang="pl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Serum Nova: lekkie serum z witaminą C</title>
<meta name="description" content="Serum Nova z 15% witaminą C rozjaśnia skórę w 4 tygodnie. Sprawdź skład, opinie i ceny w sklepie Nova Kosmetyki.">
<link rel="canonical" href="https://nova.example/serum">
<link rel="icon" href="/favicon.svg"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest"><meta name="theme-color" content="#112233">
<meta property="og:title" content="Serum Nova"><meta property="og:description" content="Serum z witaminą C">
<meta property="og:image" content="https://nova.example/og.png"><meta property="og:url" content="https://nova.example/serum">
<meta property="og:type" content="product"><meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Product","name":"Nova"},{"@type":"Organization"}]}</script>
</head><body><h1>Serum Nova</h1><h2>Skład</h2><img src="a.webp" alt="Butelka" width="800" height="600"></body></html>
"""


# --------------------------------------------------------------------- seo_check

def test_seo_clean_page_has_no_errors():
    r = seo.check(GOOD_HTML, None)
    assert r["summary"]["errors"] == 0, r
    assert r["summary"]["warnings"] == 0, r
    assert any("Organization" in i and "Product" in i for i in r["jsonld"]["info"])


def test_seo_broken_page():
    html = ('<html><head><meta name="robots" content="noindex,follow">'
            '<script type="application/ld+json">{zly json</script></head>'
            '<body><h2>a</h2><h4>b</h4><img src="x.jpg"></body></html>')
    r = seo.check(html, None)
    joined = json.dumps(r, ensure_ascii=False)
    for expected in ["brak <title>", "brak meta description", "brak atrybutu lang", "brak meta viewport",
                     "noindex", "brak favicon", "brak og:title", "brak og:image", "niepoprawny JSON-LD",
                     "liczba H1: 0", "przeskok nagłówków h2 → h4", "1 obrazów bez alt"]:
        assert expected in joined, expected
    assert r["summary"]["errors"] >= 10


def test_seo_title_length_warning():
    r = seo.check(GOOD_HTML.replace("Serum Nova: lekkie serum z witaminą C", "Nova"), None)
    assert any("title ma 4 znaków" in w for w in r["head"]["warnings"])


# ----------------------------------------------------------------------- sources

extract = load_script("profiles/jarvo-sherlock/scripts/extract.py")
STRONA = "Stopa bezrobocia w marcu 2026 wyniosła **5,1 procent**, podał [GUS](https://stat.gov.pl). Inne zdanie."


def rejestr(tmp_path):
    return json.loads((tmp_path / "out/zrodla.json").read_text(encoding="utf-8"))["sources"]


def test_sources_numery_stale_i_ocena(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    sources.main(["add", "https://stat.gov.pl/raport", "--tier", "A", "--type", "dane", "--date", "2026-03-01",
                  "--title", "GUS: raport"])
    sources.main(["add", "https://blog.example/wpis", "https://inny.example/a"])
    sources.main(["add", "https://stat.gov.pl/raport/#tabela", "--tier", "A", "--type", "pierwotne"])
    e = rejestr(tmp_path)
    assert [x["id"] for x in e] == [1, 2, 3]                       # ten sam adres (z / i #) = ten sam numer
    assert e[0]["type"] == "pierwotne" and e[0]["title"] == "GUS: raport" and e[0]["date"] == "2026-03-01"
    assert capsys.readouterr().out.splitlines()[-1] == "[1] https://stat.gov.pl/raport"
    sources.main(["list", "--min-tier", "B"])
    listed = capsys.readouterr().out
    assert "stat.gov.pl" in listed and "blog.example" not in listed
    sources.main(["cite"])                                          # stare polecenie = render
    cited = capsys.readouterr().out.splitlines()
    assert cited[0] == "## Źródła"
    assert cited[2].startswith("- [1] https://stat.gov.pl/raport — GUS: raport") and "wiarygodność A, pierwotne" in cited[2]
    with pytest.raises(SystemExit):
        sources.main(["add", "https://x.example", "--tier", "Z"])


def test_sources_ingest_i_wspolny_rejestr(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    wspolny = tmp_path / "misja/zrodla.json"
    monkeypatch.setenv("JARVO_REJESTR_ZRODEL", str(wspolny))
    wyniki = {"results": [{"url": "https://a.example/x", "title": "A"}, {"link": "https://b.example", "name": "B"},
                          {"url": "https://a.example/x/"}]}
    (tmp_path / "w.json").write_text(json.dumps(wyniki), encoding="utf-8")
    assert sources.main(["ingest", "w.json"]) == 0
    assert [s["title"] for s in json.loads(wspolny.read_text(encoding="utf-8"))["sources"]] == ["A", "B"]
    sources.main(["add", "https://a.example/x", "--title", "Strona A"])
    assert sources.main(["ingest", "w.json"]) == 0                  # tytuł z wyszukiwarki nie nadpisuje zapisanego
    assert [s["title"] for s in json.loads(wspolny.read_text(encoding="utf-8"))["sources"]] == ["Strona A", "B"]
    assert not (tmp_path / "out").exists()
    inny = tmp_path / "watek/zrodla.json"
    sources.main(["add", "https://c.example", "--rejestr", str(inny)])           # --rejestr także po poleceniu
    sources.main([f"--rejestr={inny}", "add", "https://d.example"])
    assert [x["id"] for x in json.loads(inny.read_text(encoding="utf-8"))["sources"]] == [1, 2]


def test_sources_przenosi_stary_dziennik(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out/zrodla.jsonl").write_text(json.dumps({"n": 1, "url": "https://stat.gov.pl/r", "tier": "A",
                                                          "type": "dane", "checked_at": "2026-09-01"}) + "\n", encoding="utf-8")
    sources.main(["add", "https://nowe.example"])
    e = rejestr(tmp_path)
    assert [(x["id"], x["url"]) for x in e] == [(1, "https://stat.gov.pl/r"), (2, "https://nowe.example")]
    assert e[0]["tier"] == "A" and e[0]["accessed"] == "2026-09-01"


def test_cytat_tylko_doslowny_z_zapisanego_tekstu(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "s.txt").write_text(STRONA, encoding="utf-8")
    sources.main(["add", "https://stat.gov.pl/r", "--tekst", "s.txt"])
    sources.main(["add", "https://blog.example/w"])
    e = rejestr(tmp_path)[0]
    assert (tmp_path / "out" / e["tekst"]).read_text(encoding="utf-8") == STRONA and len(e["sha256"]) == 64
    # odstępy, wielkość liter i znaczniki markdown (pogrubienie, link) nie przeszkadzają
    assert sources.main(["quote", "1", "--text", "wyniosła 5,1 procent, podał GUS"]) == 0
    with pytest.raises(SystemExit, match="dosłownie"):
        sources.main(["quote", "1", "--text", "wyniosła 6 procent, podał GUS"])
    with pytest.raises(SystemExit, match="za krótki"):
        sources.main(["quote", "1", "--text", "5,1 procent"])
    with pytest.raises(SystemExit, match="nie ma zapisanego tekstu"):
        sources.main(["quote", "2", "--text", "cokolwiek tu jest"])
    sources.main(["quote", "1", "--text", "WYNIOSŁA 5,1   procent, podał GUS"])            # bez dubla
    assert len(rejestr(tmp_path)[0]["quotes"]) == 1
    # link z podświetleniem: krótki cytat w całości, długi jako początek,koniec; przecinek i myślnik zakodowane
    assert sources.link_podswietlenia("https://a.pl/r", "jest 5,1 procent - dane") == \
        "https://a.pl/r#:~:text=jest%205%2C1%20procent%20%2D%20dane"
    assert sources.link_podswietlenia("https://a.pl/r", "Stopa bezrobocia w marcu 2026 była równa 5,1 procent według GUS") == \
        "https://a.pl/r#:~:text=Stopa%20bezrobocia%20w%20marcu,5%2C1%20procent%20wed%C5%82ug%20GUS"


def test_verify_raportu(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "s.txt").write_text(STRONA, encoding="utf-8")
    sources.main(["add", "https://stat.gov.pl/r", "--tekst", "s.txt", "--tier", "A", "--type", "dane"])
    sources.main(["add", "https://blog.example/w"])
    raport = tmp_path / "out/RAPORT.md"
    raport.write_text("# Raport\n\nBezrobocie w marcu 2026 wyniosło 5,1 procent [1]. Blog twierdzi zupełnie "
                      "co innego w tej sprawie [2]. To zdanie podaje liczbę [7].\n", encoding="utf-8")
    assert sources.main(["verify", str(raport)]) == 1
    err = capsys.readouterr().err
    assert "spoza rejestru" in err and "[7]" in err and "nie ma bloku" in err
    assert "bez oceny wiarygodności" in err and "tylko z wyniku wyszukiwania" in err

    raport.write_text("# Raport\n\nBezrobocie w marcu 2026 wyniosło 5,1 procent [1]. Blog twierdzi zupełnie "
                      "co innego w tej sprawie [niezweryfikowane]. Prognoza na koniec roku jest niepewna.\n",
                      encoding="utf-8")
    assert sources.main(["render", "--replace-in", str(raport)]) == 0
    assert sources.main(["render", "--replace-in", str(raport), "--styl", "dowody"]) == 0   # bez dublowania bloku
    assert raport.read_text(encoding="utf-8").count("## Źródła") == 1
    assert sources.main(["verify", str(raport), "--min-coverage", "0.9"]) == 1          # 2 z 3 zdań
    assert sources.main(["verify", str(raport), "--min-coverage", "0.6"]) == 0
    assert sources.main(["verify", str(raport), "--dowody"]) == 1                        # brak cytatu-dowodu
    sources.main(["quote", "1", "--text", "Stopa bezrobocia w marcu 2026 wyniosła 5,1 procent"])
    sources.main(["render", "--replace-in", str(raport), "--styl", "dowody"])
    capsys.readouterr()
    assert sources.main(["verify", str(raport), "--dowody"]) == 0
    out = capsys.readouterr().out
    assert "cytowania OK" in out and "1 [niezweryfikowane]" in out
    assert sources.main(["verify", str(raport), "--strict"]) == 1                        # [2] w rejestrze, nie cytowane
    tekst = raport.read_text(encoding="utf-8")
    assert "> „Stopa bezrobocia" in tekst and "#:~:text=" in tekst
    # ręcznie poprawiony adres w bloku źródeł nie przejdzie
    raport.write_text(tekst.replace("- [1] https://stat.gov.pl/r", "- [1] https://stat.gov.pl/inny"), encoding="utf-8")
    assert sources.main(["verify", str(raport)]) == 1
    # adres z nawiasami (Wikipedia) przechodzi cały, a koniec linku markdown nie wchodzi do adresu
    assert sources._URL_RE.search("- [3] https://en.wikipedia.org/wiki/Python_(programming_language) — W").group(0) == \
        "https://en.wikipedia.org/wiki/Python_(programming_language)"
    assert sources._URL_RE.search("[x](https://a.pl/r).").group(0) == "https://a.pl/r"
    # angielskie nagłówek i znacznik też działają (raport po angielsku)
    raport.write_text("Unemployment reached five point one percent [1].\nGrowth may slow down later [unverified].\n\n"
                      "Sources:\n[1] https://stat.gov.pl/r\n", encoding="utf-8")
    assert sources.main(["verify", str(raport), "--min-coverage", "1"]) == 0


def test_extract_rejestruje_i_zapisuje_tekst(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(extract, "extract", lambda url: {
        "url": url, "title": "GUS", "author": None, "date": "2026-03-01", "sitename": "GUS", "text": STRONA,
        "degraded": False})
    assert extract.main(["https://stat.gov.pl/r", "--tier", "A", "--type", "dane", "--max-chars", "10"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("[1] w rejestrze źródeł; pełny tekst: out/strony/1.txt")
    e = rejestr(tmp_path)[0]
    assert (e["tier"], e["type"], e["date"], e["title"]) == ("A", "dane", "2026-03-01", "GUS")
    assert (tmp_path / "out/strony/1.txt").read_text(encoding="utf-8") == STRONA    # cały tekst, nie ucięty
    assert extract.main(["https://inna.example", "--bez-rejestru", "--json", "--max-chars", "10"]) == 0
    assert len(rejestr(tmp_path)) == 1 and json.loads(capsys.readouterr().out)["truncated"] is True


# -------------------------------------------------------------------------- pack

def test_pack_collects_outputs_and_reports_gaps(tmp_path, capsys):
    mission = tmp_path / "M-260926-nova"
    (mission / "rynek/out").mkdir(parents=True)
    (mission / "rynek/out/RAPORT.md").write_text("# Raport\n", encoding="utf-8")
    (mission / "landing/out/strona").mkdir(parents=True)
    (mission / "landing/out/strona/index.html").write_text("<h1>x</h1>", encoding="utf-8")
    (mission / "grafiki").mkdir()                          # karta bez wyników
    (mission / "zlozenie").mkdir()
    out = mission / "zlozenie/out"

    pack.main([str(mission), "--out", str(out)])
    result = json.loads(capsys.readouterr().out)
    assert result["brak_out"] == ["grafiki"]
    assert set(result["role"]) == {"rynek", "landing", "grafiki"}
    manifest = json.loads((out / "pakiet/MANIFEST.json").read_text(encoding="utf-8"))
    files = {f["path"]: f for r in manifest["roles"].values() for f in r["files"]}
    assert set(files) == {"rynek/RAPORT.md", "landing/strona/index.html"}
    assert re.fullmatch(r"[0-9a-f]{64}", files["rynek/RAPORT.md"]["sha256"])
    with zipfile.ZipFile(out / "pakiet.zip") as zf:
        assert "pakiet/rynek/RAPORT.md" in zf.namelist()
        assert "pakiet/MANIFEST.json" in zf.namelist()

    # ponowne złożenie nie dubluje plików
    pack.main([str(mission), "--out", str(out)])
    assert json.loads(capsys.readouterr().out)["plikow"] == 2


# ------------------------------------------------------------------ check_media

def test_media_specs_in_sync_with_skill_reference():
    specs_md = (REPO / "profiles/jarvo-studio/skills/studio/formaty-platform/references/specs.md").read_text(encoding="utf-8")
    documented = dict(re.findall(r"^\| `([a-z0-9-]+)` \|[^|]*\| (\d+×\d+)", specs_md, flags=re.M))
    assert set(documented) == set(media.SPECS)
    for key, (w, h, _) in media.SPECS.items():
        assert documented[key] == f"{w}×{h}", key


def test_media_match_spec():
    assert set(media.match_spec(1080, 1920)) == {"ig-story", "ig-reel", "tiktok", "yt-short"}
    assert media.match_spec(1000, 1000) == []


def fake_probe(info):
    def _probe(path):
        return {"width": None, "height": None, "codec": None, "duration": None, "audio": False,
                "is_video": False, "bytes": path.stat().st_size, **info}
    return _probe


def test_media_check_file_errors(tmp_path, monkeypatch):
    f = tmp_path / "reel.mp4"
    f.write_bytes(b"0" * 10)
    monkeypatch.setattr(media, "probe", fake_probe({"width": 1080, "height": 1350, "codec": "prores",
                                                    "duration": 200.0, "is_video": True}))
    r = media.check_file(f, "ig-reel", auto=False, max_mb=8)
    assert any("wymiary 1080×1350, oczekiwane 1080×1920" in e for e in r["errors"])
    assert any("wideo 200.0 s > limit 180 s" in e for e in r["errors"])
    assert any("kodek wideo prores" in w for w in r["warnings"])
    assert any("brak ścieżki audio" in w for w in r["warnings"])


def test_media_auto_spec(tmp_path, monkeypatch):
    f = tmp_path / "post.png"
    f.write_bytes(b"0")
    monkeypatch.setattr(media, "probe", fake_probe({"width": 1080, "height": 1350}))
    r = media.check_file(f, None, auto=True, max_mb=8)
    assert r["errors"] == [] and set(r["specs"]) == {"ig-post", "fb-post", "li-video"}
    monkeypatch.setattr(media, "probe", fake_probe({"width": 999, "height": 999}))
    r = media.check_file(f, None, auto=True, max_mb=8)
    assert any("nie pasują do żadnej" in w for w in r["warnings"])


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="brak ffmpeg/ffprobe")
def test_media_real_file(tmp_path):
    import subprocess
    f = tmp_path / "og.png"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=1200x630", "-frames:v", "1", str(f)],
                   check=True)
    r = media.check_file(f, "og", auto=False, max_mb=1)
    assert r["errors"] == [] and (r["width"], r["height"]) == (1200, 630)
