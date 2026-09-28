"""Wideograf (jarvo-wideo): biblioteka napisów i lektora, plan filmu, stock, montaż, kontrola i render end-to-end."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

import pytest

from conftest import REPO, load_script

wl = load_script("profiles/jarvo-wideo/scripts/wideo_lib.py", "wideo_lib")
film = load_script("profiles/jarvo-wideo/scripts/film.py")
stock = load_script("profiles/jarvo-wideo/scripts/stock.py", "stock")
montaz = load_script("profiles/jarvo-wideo/scripts/montaz.py")
qa = load_script("profiles/jarvo-wideo/scripts/qa_wideo.py")

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


def test_check_plan_rejects_unknown_clip_end(tmp_path):
    plan = plan_base(tmp_path)
    plan["sceny"][0]["ujecie"] = {"kolor": "#101820", "koniec": "zamroz"}
    rep = film.check_plan(plan, tmp_path)
    assert not rep["ok"] and any("ujecie.koniec" in e for e in rep["bledy"])
    plan["sceny"][0]["ujecie"]["koniec"] = "stop"
    assert film.check_plan(plan, tmp_path)["ok"]


@needs_ffmpeg
def test_short_code_clip_holds_last_frame_or_loops(tmp_path, monkeypatch):
    """Animacja z kodu krótsza od sceny: `koniec: stop` trzyma ostatnią klatkę, domyślnie (stock) pętla; obie mają długość sceny."""
    monkeypatch.setenv("JARVO_WIDEO_CACHE", str(tmp_path / "cache"))
    clip = tmp_path / "anim.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=30:d=1",
                    "-pix_fmt", "yuv420p", str(clip)], check=True)
    src = {"typ": "wideo", "plik": clip}
    stop = film.render_scene(src, {"plik": str(clip), "koniec": "stop"}, 360, 640, 2.0, True)
    loop = film.render_scene(src, {"plik": str(clip)}, 360, 640, 2.0, True)
    assert stop != loop                                                    # różne klucze cache
    for out in (stop, loop):
        assert abs(wl.duration(out) - 2.0) < 0.1

    def frame_at(path, t):
        return subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                               "-vf", "scale=16:16", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                              capture_output=True, check=True).stdout

    def diff(a, b):
        return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

    assert diff(frame_at(stop, 1.5), frame_at(stop, 1.9)) < 2              # stop: ta sama (ostatnia) klatka
    assert diff(frame_at(loop, 1.5), frame_at(loop, 1.9)) > 2              # pętla: animacja trwa dalej


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
    md = (REPO / "profiles/jarvo-wideo/skills/wideo/formaty-wideo/references/specs.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([a-z0-9-]+)` \|[^|]*\| (\d+:\d+) \| (\d+)×(\d+) \| (\d+) s \| (\d+)–(\d+) s", md, flags=re.M)
    documented = {k: (fmt, int(mx), (int(lo), int(hi))) for k, fmt, _w, _h, mx, lo, hi in rows}
    assert documented == qa.PLATFORMS
    for key, fmt, w, h, *_ in rows:
        assert wl.FORMATS[fmt] == (int(w), int(h)), key


# ------------------------------------------------------------------ render end-to-end (bez sieci: bez lektora)

@needs_ffmpeg
def test_render_draft_end_to_end_passes_qa(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVO_WIDEO_CACHE", str(tmp_path / "cache"))
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
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    import yaml
    lock = yaml.safe_load((REPO / "vendor/skills.lock.yaml").read_text(encoding="utf-8"))
    assert lock["sources"]["lemo-opuscar"]["rev"] == nz.LEMO_REV            # biblioteka = ten sam commit co skill
    dests = {e["dest"] for e in lock["agents"]["jarvo-wideo"]}
    assert {"video/motion-broll", "video/lemo-opuscar", "video/anidoodle"} <= dests
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    shell = tmp_path / "chromium_headless_shell-1243" / "chrome-headless-shell-linux64" / "chrome-headless-shell"
    shell.parent.mkdir(parents=True)
    shell.write_text("")
    assert nz.env_for("lemo")["PLAYWRIGHT_CHROME"] == str(shell)
    assert nz.env_for("motion")["NODE_PATH"].endswith("node/node_modules")
    assert lock["sources"]["video-shotcraft"]["rev"] == nz.SHOTCRAFT_REV
    assert lock["sources"]["lottie"]["rev"] == nz.LOTTIE_REV                # player = ten sam commit co skill
    assert {"video/remotion-best-practices", "video/bang-motion", "video/pixel2motion", "video/text-to-lottie",
            "video/kinetic-typography", "screenwriting/sw-scene-craft"} <= dests
    # router Remotion zawiera resztę skilli Remotion: osobne kopie byłyby dublami
    assert not [d for d in dests if d.startswith("video/remotion-") and d != "video/remotion-best-practices"]
    monkeypatch.setattr(nz, "CHROME_WRAPPER", tmp_path / "bin" / "chrome-no-sandbox")   # jeszcze bez nakładki
    rem = nz.env_for("shotcraft")
    assert rem["REMOTION_BROWSER_EXECUTABLE"] == rem["PUPPETEER_EXECUTABLE_PATH"] == str(shell)
    assert rem["SHOTCRAFT"].endswith("video-shotcraft")
    assert nz.env_for("html")["CHROME_BIN"] == str(shell)
    # z nakładką (--no-sandbox dla puppeteer i CHROME_BIN); Remotion i playwright dostają przeglądarkę wprost
    wrapper = nz.ensure_chrome_wrapper()
    assert wrapper.stat().st_mode & 0o111 and "--no-sandbox" in wrapper.read_text(encoding="utf-8")
    html = nz.env_for("html")
    assert html["PUPPETEER_EXECUTABLE_PATH"] == html["CHROME_BIN"] == str(wrapper) and html["JARVO_CHROME_REAL"] == str(shell)
    assert nz.env_for("remotion")["REMOTION_BROWSER_EXECUTABLE"] == str(shell)
    assert nz.env_for("lottie")["LOTTIE_PLAYER"].endswith("lottie-player")
    with pytest.raises(SystemExit):
        nz.env_for("puppeteer-core")
    monkeypatch.setenv("JARVO_EXTRAS", "media lemo")
    assert nz.full_extras()


def test_code_tools_helpers(monkeypatch, tmp_path):
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    # starszy układ przeglądarki (chrome-linux/headless_shell) i wybór najnowszego buildu po numerze, nie alfabetycznie
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    assert nz.headless_shell() is None
    old = tmp_path / "chromium_headless_shell-999" / "chrome-linux" / "headless_shell"
    new = tmp_path / "chromium_headless_shell-1200" / "chrome-headless-shell-linux64" / "chrome-headless-shell"
    for p in (old, new):
        p.parent.mkdir(parents=True)
        p.write_text("")
    assert nz.headless_shell() == str(new)
    new.unlink()
    assert nz.headless_shell() == str(old)
    assert nz.npm_name("@remotion/cli@4.0.484") == "@remotion/cli"
    assert nz.npm_name("remotion@4.0.484") == "remotion" and nz.npm_name("esbuild") == "esbuild"
    assert nz.npm_name("puppeteer@24") == "puppeteer"
    assert nz.py_module("playwright==1.63.0") == "playwright" and nz.py_module("pillow") == "PIL"
    assert nz.py_module("faster-whisper") == "faster_whisper"
    monkeypatch.setattr(nz, "NODE", tmp_path / "node")
    link = nz.link(tmp_path / "projekt")
    assert link.is_symlink() and link.resolve() == (tmp_path / "node" / "node_modules").resolve()
    assert nz.link(tmp_path / "projekt") == link                           # drugi raz bez błędu


# ------------------------------------------------------------------ html_wideo (animacja HTML / Lottie → wideo)

hw = load_script("profiles/jarvo-wideo/scripts/html_wideo.py")


def test_html_presets_and_flags_override():
    o = hw.resolve_opts("pixel2motion")
    assert (o["param"], o["jednostka"], o["selektor"]) == ("t", "ms", "#logo-root")
    o = hw.resolve_opts("iart", jednostka="ms", selektor=None)
    assert o["jednostka"] == "ms" and o["gotowe"] == "window.__ready === true" and o["selektor"] is None
    assert hw.resolve_opts("bang")["seek"].startswith("async (t)")
    assert hw.resolve_opts(None)["param"] == "t"
    with pytest.raises(SystemExit):
        hw.resolve_opts("nie-ma")


def test_html_time_values_and_urls(tmp_path):
    assert hw.time_value(1.5, "s", 30) == "1.5" and hw.time_value(0, "s", 30) == "0"
    assert hw.time_value(1.2345, "ms", 30) == "1234" and hw.time_value(2, "klatka", 25) == "50"
    assert hw.frame_times(1, 4) == [0, .25, .5, .75] and hw.frame_times(0, 30) == [0]
    assert hw.parse_times("0, 1.5;3") == [0, 1.5, 3] and hw.parse_size("1080x1920") == (1080, 1920)
    page = tmp_path / "anim.html"
    page.write_text("<p>x</p>")
    url = hw.page_url(str(page), {"t": "1.5", "clean": 1})
    assert url.startswith("file://") and url.endswith("anim.html?t=1.5&clean=1")
    assert hw.page_url("http://127.0.0.1:3030/p/scene-1?frame=2", {"frame": 5}) == "http://127.0.0.1:3030/p/scene-1?frame=5"
    with pytest.raises(SystemExit):
        hw.page_url(str(tmp_path / "brak.html"), {})


def test_html_encode_commands(tmp_path):
    mp4 = hw.encode_cmd("f%05d.png", 30, tmp_path / "a.mp4", False)
    assert "libx264" in mp4 and "+faststart" in mp4 and any("out_range=tv" in x for x in mp4)
    mov = hw.encode_cmd("f%05d.png", 24, tmp_path / "a.mov", True)
    assert "prores_ks" in mov and "yuva444p10le" in mov and "4444" in mov
    assert "yuva420p" in hw.encode_cmd("f%05d.png", 30, tmp_path / "a.webm", True)
    with pytest.raises(SystemExit):
        hw.encode_cmd("f%05d.png", 30, tmp_path / "a.mp4", True)            # MP4 nie ma alfy
    with pytest.raises(SystemExit):
        hw.encode_cmd("f%05d.png", 30, tmp_path / "a.avi", False)


def test_lottie_contract_check():
    ok = {"v": "5.12.0", "fr": 30, "ip": 0, "op": 90, "w": 512, "h": 512, "layers": [{"ty": 4}]}
    assert hw.lottie_check(ok) == []
    assert "brak pola 'op'" in hw.lottie_check({k: v for k, v in ok.items() if k != "op"})
    assert hw.lottie_check({**ok, "op": 0}) == ["op ≤ ip (animacja bez klatek)"]
    assert hw.lottie_check({**ok, "layers": []}) == ["pusta lista layers"]


@needs_ffmpeg
def test_html_sheet_and_encode_from_frames(tmp_path):
    PIL = pytest.importorskip("PIL.Image")
    frames = []
    for i in range(6):
        p = tmp_path / f"f{i:05d}.png"
        PIL.new("RGBA", (64, 36), (40 * i, 80, 160, 255 if i % 2 else 0)).save(p)
        frames.append(p)
    sheet = hw.sheet(frames, [f"t={i}" for i in range(6)], tmp_path / "arkusz.jpg", width=600)
    assert PIL.open(sheet).size[0] == 600
    out = hw.encode(tmp_path, 6, tmp_path / "film.mp4", False)
    info = wl.probe(out)
    assert info["video"]["codec"] == "h264" and info["video"]["pix_fmt"] == "yuv420p" and abs(info["duration"] - 1) < .2
    mov = hw.encode(tmp_path, 6, tmp_path / "film.mov", True)
    assert wl.probe(mov)["video"]["pix_fmt"].startswith("yuva")


def test_html_jarvo_preset_query_merge_and_subframes():
    o = hw.resolve_opts("jarvo", query={"lang": "pl"})
    assert o["serwer"] and o["query"] == {"render": "1", "lang": "pl"}      # --query dokłada, render=1 zostaje
    assert "instanceof Promise" in o["seek"]                               # oś GSAP (thenable) nie blokuje
    assert hw.resolve_opts("iart")["query"] == {} and not hw.resolve_opts("iart")["serwer"]
    assert hw.subframe_times([0, 1 / 30], 30, 2) == [0, 1 / 60, 1 / 30, 1 / 30 + 1 / 60]


def test_html_server_maps_lib_and_blocks_escape(tmp_path, monkeypatch):
    import urllib.error
    import urllib.request
    nz_mod = sys.modules["narzedzia"]                                     # ten sam moduł, którego używa html_wideo
    monkeypatch.setattr(nz_mod, "NODE", tmp_path / "node")
    lib = tmp_path / "node" / "node_modules" / "three" / "build"
    lib.mkdir(parents=True)
    (lib / "three.module.js").write_text("export const ok = 1;")
    (tmp_path / "sekret.txt").write_text("nie")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<p>ok</p>")
    httpd = hw.serve(site, lib=True)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/index.html") as r:
            assert b"ok" in r.read()
        with urllib.request.urlopen(base + "/_lib/three/build/three.module.js") as r:
            assert r.headers["Content-Type"].startswith("text/javascript") and b"ok" in r.read()
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/_lib/../../sekret.txt")
    finally:
        httpd.shutdown()


# ------------------------------------------------------------------ rodzaje filmu i inspiracje

RODZAJE_DIR = REPO / "profiles/jarvo-wideo/skills/wideo/rodzaje-filmu"
SEKCJE = ["## Wynik", "## Silnik", "## Struktura", "## Rzemiosło", "## Brief", "## Pułapki", "## Kontrola", "## Inspiracje"]
insp = load_script("profiles/jarvo-wideo/scripts/inspiracje.py")


def test_rodzaje_index_matches_files_and_stays_lean():
    """Indeks = pliki; każdy plik rodzaju ma te same sekcje, jest krótki (bez rozrostu) i ma swój klucz inspiracji."""
    index = (RODZAJE_DIR / "SKILL.md").read_text(encoding="utf-8")
    linked = set(re.findall(r"`references/([a-z0-9-]+)\.md`", index))
    files = {p.stem for p in (RODZAJE_DIR / "references").glob("*.md")}
    assert linked == files
    types = files - {"kontrakt-html"}
    assert types == set(insp.RODZAJE)                                     # każdy rodzaj ma inspiracje i odwrotnie
    for name in sorted(types):
        text = (RODZAJE_DIR / "references" / f"{name}.md").read_text(encoding="utf-8")
        heads = [ln.split(" (")[0] for ln in text.splitlines() if ln.startswith("## ")]
        assert heads == SEKCJE, name
        assert len(text.splitlines()) <= 70, f"{name}: plik rodzaju ma być krótki"
        assert f"inspiracje.py {name}" in text, name
    assert len(index.splitlines()) <= 70


def test_inspiracje_pick_filters_dedupes_and_excludes():
    base = {"prompt_partial": False, "tech_tags": ["canvas"], "author": "a", "post_url": "u"}
    long = " — scene one, scene two, rules and timeline." * 12
    items = [
        {**base, "slug": "exp", "category": "explainer", "prompt": "Explain how photons travel." + long},
        {**base, "slug": "exp-kopia", "category": "explainer", "prompt": "Explain how photons travel." + long},
        {**base, "slug": "czesciowy", "category": "explainer", "prompt": "Explain it." + long, "prompt_partial": True},
        {**base, "slug": "promo", "category": "motion", "prompt": "Product launch video for our app." + long},
        {**base, "slug": "czysty-ruch", "category": "motion", "prompt": "Abstract loop of circles." + long},
        {**base, "slug": "gra", "category": "motion", "prompt": "Playable game." + long, "tech_tags": ["threejs"]},
    ]
    assert [x["slug"] for x in insp.pick(items, "explainer", ile=5)] == ["exp"]   # bez kopii i częściowych
    assert [x["slug"] for x in insp.pick(items, "promo-produktu", ile=5)] == ["promo"]
    mg = [x["slug"] for x in insp.pick(items, "motion-graphics", ile=5)]
    assert "czysty-ruch" in mg and "promo" not in mg                       # promo ma swój rodzaj
    assert [x["slug"] for x in insp.pick(items, "interaktywne", tag="threejs")] == ["gra"]
    with pytest.raises(SystemExit):
        insp.pick(items, "reklama")
    shown = insp.show(items[0], limit=40)
    assert "@a" in shown and "--pelny exp" in shown


def test_inspiracje_cache_used_when_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVO_WIDEO_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(insp, "URL", "http://127.0.0.1:9/brak.json")       # sieć niedostępna
    with pytest.raises(SystemExit):
        insp.load()                                                        # bez cache: jasny komunikat, nie traceback
    cached = wl.cache_dir("inspiracje") / f"videos-{insp.REV[:12]}.json"
    cached.write_text(json.dumps([{"slug": "x"}]))
    assert insp.load() == [{"slug": "x"}]


# ------------------------------------------------------------------ rytm muzyki i mrugnięcia klatek
def _wscript(name):
    import importlib.util as iu
    sys.path.insert(0, str(REPO / "profiles" / "jarvo-wideo" / "scripts"))
    spec = iu.spec_from_file_location(name, REPO / "profiles" / "jarvo-wideo" / "scripts" / f"{name}.py")
    mod = iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_rytm_finds_tempo_grid_and_drop(tmp_path):
    rytm = _wscript("rytm")
    p = 0.46875   # 128 BPM, pierwszy bit 0.2 s, głośniej od 7.7 s (drop), mocny bit co takt
    expr = (f"if(gte(t,0.2), sin(2*PI*55*t)*exp(-25*mod(t-0.2,{p}))*if(eq(mod(floor((t-0.2)/{p}),4),0),1,0.55)"
            f"*if(lt(t,7.7),0.25,1), 0)")
    wav = tmp_path / "beat.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d=16", str(wav)], check=True)
    r = rytm.analyze(wav)
    assert r["bpm"] == pytest.approx(128, abs=0.5)
    assert r["pierwszy_bit"] == pytest.approx(0.2, abs=0.03)
    assert r["drop"] == pytest.approx(7.7, abs=0.05)
    assert r["takty"][1] - r["takty"][0] == pytest.approx(4 * p, abs=0.02)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_qa_single_frame_pop_but_not_cut_or_pan(tmp_path):
    qa = _wscript("qa_wideo")
    pop = tmp_path / "pop.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=0x223344:s=320x180:r=30:d=2",
                    "-f", "lavfi", "-i", "color=white:s=320x180:r=30:d=0.0333", "-f", "lavfi", "-i", "color=c=0x223344:s=320x180:r=30:d=1",
                    "-f", "lavfi", "-i", "color=c=orange:s=320x180:r=30:d=1",
                    "-filter_complex", "[0][1][2][3]concat=n=4:v=1:a=0,format=yuv420p", str(pop)], check=True)
    frames, fps = qa.gray_frames(pop)
    assert qa.single_frame_pops(frames, fps) == [pytest.approx(2.0, abs=0.04)]     # błysk tak, cięcie na pomarańcz nie
    pan = tmp_path / "pan.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=2",
                    "-vf", "scroll=h=0.05,format=yuv420p", str(pan)], check=True)
    assert qa.single_frame_pops(*qa.gray_frames(pan)) == []                          # szybka panorama to nie błąd


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_rytm_sfx_peak(tmp_path):
    rytm = _wscript("rytm")
    wav = tmp_path / "klik.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc='if(gte(t,0.15),sin(2*PI*900*t)*exp(-40*(t-0.15)),0)':s=44100:d=0.6", str(wav)], check=True)
    assert rytm.peak(wav)["szczyt"] == pytest.approx(0.15, abs=0.02)


def test_narzedzia_exempts_exact_pins_from_uv_quarantine():
    """Obraz Hermesa ma exclude-newer 14 dni: dokładne piny (playwright==X) muszą być zwolnione, reszta nie."""
    nz = _wscript("narzedzia")
    assert nz.uv_exempt(["numpy", "playwright==1.63.0", "imageio"]) == ["--exclude-newer-package", "playwright=false"]
    assert nz.py_module("playwright==1.63.0") == "playwright" and nz.py_module("pillow") == "PIL"
