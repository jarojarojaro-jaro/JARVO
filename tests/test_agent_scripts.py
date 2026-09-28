"""Skrypty narzędziowe snajperów: SEO, dziennik źródeł, pakiet misji, kontrola mediów."""

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

def test_sources_add_dedupe_list_cite(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    sources.main(["add", "https://stat.gov.pl/raport", "--tier", "A", "--type", "dane", "--date", "2026-03-01",
                  "--title", "GUS: raport"])
    sources.main(["add", "https://blog.example/wpis", "--tier", "C", "--type", "opinia"])
    sources.main(["add", "https://stat.gov.pl/raport", "--tier", "A", "--type", "pierwotne", "--title", "GUS"])
    entries = [json.loads(line) for line in (tmp_path / "out/zrodla.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["n"] for e in entries] == [1, 2]
    assert entries[0]["type"] == "pierwotne" and entries[0]["title"] == "GUS"
    capsys.readouterr()
    sources.main(["list", "--min-tier", "B"])
    listed = capsys.readouterr().out
    assert "stat.gov.pl" in listed and "blog.example" not in listed
    sources.main(["cite"])
    cited = capsys.readouterr().out.splitlines()
    assert cited[0].startswith("[1] GUS") and "wiarygodność A" in cited[0]
    assert cited[1].startswith("[2] https://blog.example/wpis")


def test_sources_rejects_bad_tier(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        sources.main(["add", "https://x.example", "--tier", "Z", "--type", "dane"])


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
