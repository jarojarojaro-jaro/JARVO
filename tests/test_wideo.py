"""Wideograf (tars-wideo): biblioteka napisów i lektora, plan filmu, stock, montaż, kontrola i render end-to-end."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from conftest import REPO, load_script

wl = load_script("profiles/tars-wideo/scripts/wideo_lib.py", "wideo_lib")
film = load_script("profiles/tars-wideo/scripts/film.py")
stock = load_script("profiles/tars-wideo/scripts/stock.py", "stock")
montaz = load_script("profiles/tars-wideo/scripts/montaz.py")
qa = load_script("profiles/tars-wideo/scripts/qa_wideo.py")

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak FFmpeg")
W = wl.Word


# ------------------------------------------------------------------ napisy

def test_hex_to_ass_is_bgr_with_alpha():
    assert wl.hex_to_ass("#FFD400") == "&H0000D4FF"
    assert wl.hex_to_ass("#abc", alpha=0x78) == "&H78CCBBAA"
    with pytest.raises(SystemExit):
        wl.hex_to_ass("żółty")


def test_align_display_keeps_question_marks_and_drops_commas():
    words = [W(0, .3, "Myślisz"), W(.3, .5, "że"), W(.5, 1, "espresso"), W(1, 1.4, "kofeiny")]
    out = wl.align_display(words, "Myślisz, że espresso… kofeiny?")
    assert [w.text for w in out] == ["Myślisz", "że", "espresso", "kofeiny?"]


def test_chunks_respect_limits_sentence_end_and_merge_orphans():
    words = [W(i * .4, i * .4 + .3, t) for i, t in enumerate("Zapisz ten film i sprawdź resztę mitów".split())]
    groups = wl.chunk_words(words, 3, 18)
    assert all(len(g) <= 4 for g in groups)
    assert len(groups[-1]) > 1                       # bez samotnego „mitów” na końcu
    polish = [W(i * .3, i * .3 + .25, t) for i, t in enumerate("Kawa gratis do dziewiątej rano".split())]
    assert [" ".join(x.text for x in g) for g in wl.chunk_words(polish, 3, 18)] == ["Kawa gratis", "do dziewiątej rano"]
    sent = [W(0, .3, "Nie!"), W(.35, .6, "Kubek"), W(.6, .9, "przelewu")]
    assert [len(g) for g in wl.chunk_words(sent, 3, 18)] == [1, 2]   # koniec zdania zamyka grupę


def test_build_ass_karaoke_highlights_each_word_and_keeps_safe_zone():
    words = [W(0.1, 0.5, "Trzy"), W(0.5, 0.9, "mity"), W(0.9, 1.4, "kawy")]
    ass = wl.build_ass(1080, 1920, words, wl.SubStyle(), titles=[(0.0, 2.0, "3 mity")])
    events = [l for l in ass.splitlines() if l.startswith("Dialogue: 0,")]
    assert len(events) == 3                          # jedno zdarzenie na aktywne słowo
    assert all(r"\c&H0000D4FF" in e for e in events)
    assert "PlayResY: 1920" in ass and "3 MITY" in ass and r"{\fad(0,120)}" in ass   # tytuł od klatki 0
    style = next(l for l in ass.splitlines() if l.startswith("Style: Napisy"))
    margin_l, margin_r, margin_v = map(int, style.split(",")[19:22])
    assert margin_r > margin_l and margin_v >= 1920 * 0.2   # prawy pasek przycisków i dolny opis


def test_srt_roundtrip_and_proportional_words():
    words = [W(0, .4, "Dzień"), W(.4, .9, "dobry."), W(1.5, 2.0, "Test")]
    srt = wl.build_srt(words)
    lines = wl.parse_srt(srt)
    assert lines[0][2].startswith("Dzień dobry.") and lines[0][0] == 0
    spread = wl.words_from_lines([(0.0, 2.0, "aa bbbb")])
    assert spread[0].end < spread[1].end == pytest.approx(2.0, abs=.01)


def test_slugify_polish():
    assert wl.slugify("Kawa: 3 mity o łódzkiej żółtej kawie!") == "kawa-3-mity-o-lodzkiej-zoltej-kawie"


# ------------------------------------------------------------------ plan

def plan_base(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"x")
    return {"tytul": "Test", "formaty": ["9:16"], "lektor": {"glos": "pl-PL-ZofiaNeural"},
            "sceny": [{"tekst": "Krótki hook.", "ujecie": {"plik": str(img)}},
                      {"tekst": "Druga scena.", "ujecie": {"kolor": "#112233"}}],
            "warianty": [{"nazwa": "B", "lektor": {"glos": "pl-PL-MarekNeural"}, "sceny": {"1": {"tekst": "Inny hook."}}}]}


def test_check_plan_ok_and_variants(tmp_path):
    plan = plan_base(tmp_path)
    rep = film.check_plan(plan, tmp_path)
    assert rep["ok"] and rep["warianty"] == ["A", "B"] and rep["szacunek_s"] > 1
    b = film.variant_plan(plan, "B")
    assert b["sceny"][0]["tekst"] == "Inny hook." and b["sceny"][1]["tekst"] == "Druga scena."
    assert b["lektor"]["glos"] == "pl-PL-MarekNeural" and "warianty" not in b
    assert film.variant_plan(plan, "A")["sceny"][0]["tekst"] == "Krótki hook."


def test_check_plan_errors_and_warnings(tmp_path, monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    plan = plan_base(tmp_path)
    plan["sceny"][0]["tekst"] = " ".join(["słowo"] * 14)
    plan["sceny"][1]["ujecie"] = {"stock": "coffee", "kolor": "#000000"}
    plan["sceny"].append({"tekst": "Stock.", "ujecie": {"stock": "coffee beans"}, "tekst_ekranowy": "Zapisz 🔖"})
    rep = film.check_plan(plan, tmp_path)
    assert not rep["ok"]
    assert any("dokładnie jedno" in e for e in rep["bledy"])
    assert any("PEXELS_API_KEY" in e for e in rep["bledy"])
    assert any("hook" in w for w in rep["ostrzezenia"])
    assert any("emoji" in w for w in rep["ostrzezenia"])


# ------------------------------------------------------------------ stock i montaż

def test_stock_ranking_and_file_choice():
    portrait = {"typ": "wideo", "szer": 1080, "wys": 1920, "sek": 12}
    landscape = {"typ": "wideo", "szer": 3840, "wys": 2160, "sek": 12}
    short = {"typ": "wideo", "szer": 1080, "wys": 1920, "sek": 2}
    assert stock.score(portrait, "9:16", 5) > stock.score(landscape, "9:16", 5) > stock.score(short, "9:16", 5) - 10
    item = {"id": "pexels:1", "pliki": [{"url": "a", "szer": 2160, "wys": 3840}, {"url": "b", "szer": 1080, "wys": 1920},
                                         {"url": "c", "szer": 540, "wys": 960}]}
    assert stock.pick_file(item, "9:16")["url"] == "b"     # najlżejszy, który pokrywa 1080


def test_stock_without_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    with pytest.raises(stock.StockError, match="PEXELS_API_KEY"):
        stock.search("kawa")


def test_montaz_time_parsing():
    assert montaz.parse_time("1:10.5") == pytest.approx(70.5)
    assert montaz.parse_time("0:01:02") == 62
    assert montaz.parse_ranges("0:03-0:41.5, 47-80") == [(3.0, 41.5), (47.0, 80.0)]
    with pytest.raises(SystemExit):
        montaz.parse_ranges("10-5")


def test_platform_specs_in_sync_with_skill_reference():
    md = (REPO / "profiles/tars-wideo/skills/wideo/formaty-wideo/references/specs.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([a-z0-9-]+)` \|[^|]*\| (\d+:\d+) \| (\d+)×(\d+) \| (\d+) s \| (\d+)–(\d+) s", md, flags=re.M)
    documented = {k: (fmt, int(mx), (int(lo), int(hi))) for k, fmt, _w, _h, mx, lo, hi in rows}
    assert documented == qa.PLATFORMS
    for key, fmt, w, h, *_ in rows:
        assert wl.FORMATS[fmt] == (int(w), int(h)), key


# ------------------------------------------------------------------ render end-to-end (bez sieci: bez lektora)

@needs_ffmpeg
def test_render_draft_end_to_end_passes_qa(tmp_path, monkeypatch):
    monkeypatch.setenv("TARS_WIDEO_CACHE", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x480", "-frames:v", "1",
                    str(tmp_path / "zdjecie.jpg")], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=25:d=2", "-pix_fmt", "yuv420p",
                    str(tmp_path / "klip.mp4")], check=True)
    plan = {"tytul": "Test renderu", "formaty": ["9:16"], "lektor": False, "napisy": {"styl": "brak"}, "przejscie": "przenikanie",
            "sceny": [{"czas": 1.5, "ujecie": {"plik": "klip.mp4"}, "tekst_ekranowy": "Hook"},
                      {"czas": 1.5, "ujecie": {"plik": "zdjecie.jpg", "ruch": "oddal"}},
                      {"czas": 1.5, "ujecie": {"kolor": "#1B2A41"}, "tekst_ekranowy": "Koniec"}]}
    (tmp_path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    assert film.main(["render", "plan.json", "--szkic", "--out", "out"]) == 0
    mp4 = tmp_path / "out/test-renderu/test-renderu-9x16-szkic.mp4"
    info = wl.probe(mp4)
    assert (info["video"]["width"], info["video"]["height"]) == (540, 960)
    assert info["video"]["pix_fmt"] == "yuv420p"          # zakres TV także ze scen z JPEG
    assert info["duration"] == pytest.approx(4.5, abs=0.15) and info["audio"]
    manifest = json.loads((tmp_path / "out/test-renderu/film-szkic.json").read_text(encoding="utf-8"))
    assert [s["ujecie"]["typ"] for s in manifest["sceny"]] == ["wideo", "zdjecie", "kolor"]
    res = qa.check(mp4, None, "9:16", False, None)
    assert not any("pix_fmt" in e or "kodek" in e for e in res["bledy"]), res
    assert qa.moov_first(mp4)
    # drugi render tego samego planu: sceny z cache
    cached = sorted((tmp_path / "cache" / "sceny").glob("*.mp4"))
    assert len(cached) == 3
    assert film.main(["render", "plan.json", "--szkic", "--out", "out"]) == 0
    assert sorted((tmp_path / "cache" / "sceny").glob("*.mp4")) == cached


def test_stock_parses_pexels_and_pixabay(monkeypatch):
    pexels = {"videos": [{"id": 7, "width": 1080, "height": 1920, "duration": 9, "url": "https://www.pexels.com/video/7/",
                          "image": "https://img/7.jpg", "user": {"name": "Ala", "url": "https://www.pexels.com/@ala"},
                          "video_files": [{"link": "https://v/7-hd.mp4", "width": 1080, "height": 1920, "fps": 25},
                                          {"link": "https://v/7-sd.mp4", "width": 540, "height": 960}]}]}
    pixabay = {"hits": [{"id": 9, "pageURL": "https://pixabay.com/videos/9/", "duration": 4, "user": "ola", "user_id": 1,
                         "videos": {"large": {"url": "https://p/9-l.mp4", "width": 1920, "height": 1080, "thumbnail": "https://p/9.jpg"},
                                    "small": {"url": "https://p/9-s.mp4", "width": 960, "height": 540}}}]}
    monkeypatch.setattr(stock, "_json", lambda url, headers=None: pexels if "pexels" in url else pixabay)
    monkeypatch.setenv("PEXELS_API_KEY", "k1")
    monkeypatch.setenv("PIXABAY_API_KEY", "k2")
    items = stock.search("kawa", "wideo", "9:16", n=5, min_sec=5)
    assert [it["id"] for it in items] == ["pexels:7", "pixabay:9"]        # pion i długość ≥ sceny wygrywają
    assert items[0]["autor"] == "Ala" and items[1]["podglad"] == "https://p/9.jpg"
    assert stock.pick_file(items[0], "9:16")["url"] == "https://v/7-hd.mp4"
    assert "Pexels" in stock.LICENSES["pexels"] and "Pixabay" in stock.LICENSES["pixabay"]


def test_code_tools_pinned_and_env(monkeypatch, tmp_path):
    nz = load_script("profiles/tars-wideo/scripts/narzedzia.py")
    import yaml
    lock = yaml.safe_load((REPO / "vendor/skills.lock.yaml").read_text(encoding="utf-8"))
    assert lock["sources"]["lemo-opuscar"]["rev"] == nz.LEMO_REV            # biblioteka = ten sam commit co skill
    dests = {e["dest"] for e in lock["agents"]["tars-wideo"]}
    assert {"video/motion-broll", "video/lemo-opuscar", "video/anidoodle"} <= dests
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    shell = tmp_path / "chromium_headless_shell-1243" / "chrome-headless-shell-linux64" / "chrome-headless-shell"
    shell.parent.mkdir(parents=True)
    shell.write_text("")
    assert nz.env_for("lemo")["PLAYWRIGHT_CHROME"] == str(shell)
    assert nz.env_for("motion")["NODE_PATH"].endswith("node/node_modules")
    monkeypatch.setenv("TARS_EXTRAS", "media lemo")
    assert nz.full_extras()
