"""Wideograf (jarvo-wideo): biblioteka napisów i lektora, plan filmu, stock, montaż, kontrola i render end-to-end."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys

import pytest

from conftest import REPO, load_script

wl = load_script("profiles/jarvo-wideo/scripts/wideo_lib.py", "wideo_lib")
film = load_script("profiles/jarvo-wideo/scripts/film.py")
stock = load_script("profiles/jarvo-wideo/scripts/stock.py", "stock")
montaz = load_script("profiles/jarvo-wideo/scripts/montaz.py")
qa = load_script("profiles/jarvo-wideo/scripts/qa_wideo.py")
dwa = load_script("profiles/jarvo-wideo/scripts/dwa_ekrany.py")

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


def test_obrot_jak_w_edytorze():
    ed = load_script("hq/plugin/edytor.py", "edytor_obrot")
    for v in ({"side_data_list": [{"rotation": -90}]}, {"tags": {"rotate": "90"}}, {"tags": {"rotate": "180"}}, {}):
        assert wl.obrot(v) == ed.obrot(v)
    assert wl.obrot({"side_data_list": [{"rotation": -90}]}) == 270


@needs_ffmpeg
def test_probe_pion_z_telefonu(tmp_path):
    """Poziome klatki + obrót 90° (tak zapisuje telefon): qa_wideo, napisy i kadry widzą pion 360×640."""
    poz, tel = tmp_path / "poz.mp4", tmp_path / "tel.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=1",
                    "-pix_fmt", "yuv420p", str(poz)], check=True)
    if subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-display_rotation", "90", "-i", str(poz), "-c", "copy",
                       str(tel)]).returncode:
        pytest.skip("ffmpeg bez -display_rotation (starszy niż 6.1)")
    v = wl.probe(tel)["video"]
    assert (v["width"], v["height"]) == (360, 640)
    assert (wl.probe(poz)["video"]["width"], wl.probe(poz)["video"]["height"]) == (640, 360)


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


def test_check_plan_warns_small_photo_for_camera_move(tmp_path, monkeypatch):
    """Zdjęcie 1080×1920 w 9:16: z ruchem kamery (1,12×) rozciągnięte, bez ruchu w porządku; 2× zrzut w porządku."""
    plan = plan_base(tmp_path)
    wymiary = {"w": 1080, "h": 1920}
    monkeypatch.setattr(film.wl, "probe", lambda p: {"video": {"width": wymiary["w"], "height": wymiary["h"]}})
    rep = film.check_plan(plan, tmp_path)
    assert rep["ok"] and any("1080×1920" in w and "1210×2151" in w for w in rep["ostrzezenia"])
    plan["sceny"][0]["ujecie"]["ruch"] = "brak"
    assert not any("zdjęcie" in w for w in film.check_plan(plan, tmp_path)["ostrzezenia"])
    plan["sceny"][0]["ujecie"]["ruch"] = "panorama"
    wymiary.update(w=2160, h=3840)
    assert not any("zdjęcie" in w for w in film.check_plan(plan, tmp_path)["ostrzezenia"])
    plan["sceny"][0]["ujecie"]["ruch"] = "obrot"
    assert any("`ruch` 'obrot' nieznany" in w for w in film.check_plan(plan, tmp_path)["ostrzezenia"])


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


def test_montaz_chwile_ciec():
    # do krytyka.py ciecia --czasy: koniec każdego fragmentu w gotowym pliku
    assert montaz.pozycje_ciec([(3.0, 41.5), (47.0, 80.0), (90.0, 95.0)]) == [38.5, 71.5]
    assert montaz.pozycje_ciec([(0.0, 5.0)]) == []


def test_montaz_time_parsing():
    assert montaz.parse_time("1:10.5") == pytest.approx(70.5)
    assert montaz.parse_time("0:01:02") == 62
    assert montaz.parse_ranges("0:03-0:41.5, 47-80") == [(3.0, 41.5), (47.0, 80.0)]
    with pytest.raises(SystemExit):
        montaz.parse_ranges("10-5")


TRF = """VID.STAB 1
#      accuracy = 15
Frame 1 (List 0 [])
Frame 2 (List 3 [(LM 4 -2 293 81 48 0.68 1.29),(LM 5 -1 558 147 48 0.26 0.74),(LM 40 30 346 81 48 0.55 1.27)])
Frame 3 (List 2 [(LM -3 2 293 81 48 0.68 1.29),(LM -1 0 558 147 48 0.26 0.74)])
"""


def test_montaz_ruch_z_trf_mediana_pomija_obiekty():
    # mediana ruchów lokalnych: jedno pole z ruchem osoby (40, 30) nie zmienia ruchu kamery
    assert montaz.ruch_z_trf(TRF) == [(0.0, 0.0), (5, -1), (-2.0, 1.0)]


def test_montaz_drzenie_panorama_zero_reka_wiecej():
    panorama = [(3.0, 0.0)] * 120                                     # płynna panorama: nie drżenie
    assert montaz.drzenie_z_ruchu(panorama, 640) == pytest.approx(0.0, abs=1e-9)
    reka = [(6.0 * (-1) ** i, 4.0 * (-1) ** (i // 2)) for i in range(120)]
    pan_reka = [(3.0 + dx, dy) for dx, dy in reka]
    assert montaz.drzenie_z_ruchu(reka, 640) > 0.3
    assert montaz.drzenie_z_ruchu(pan_reka, 640) == pytest.approx(montaz.drzenie_z_ruchu(reka, 640), rel=0.05)
    assert montaz.drzenie_z_ruchu(reka, 1280) == pytest.approx(montaz.drzenie_z_ruchu(reka, 640) / 2, rel=0.01)
    assert montaz.drzenie_z_ruchu([(9.0, 9.0)], 640) == 0.0
    assert [montaz.rada_drzenia(x).split(":")[0] for x in (0.05, 0.3, 0.8, 2.3)] == \
        ["stabilne", "lekkie drżenie", "z ręki", "mocno trzęsie"]


def _stab_atrapa(monkeypatch, vidstab, w=3840, h=2160, przed=0.9, po=0.05):
    wywolane = []
    monkeypatch.setattr(montaz, "ma_vidstab", lambda: vidstab)
    monkeypatch.setattr(montaz.wl, "probe", lambda p: {"video": {"width": w, "height": h}, "audio": None})
    monkeypatch.setattr(montaz.wl, "sdr", lambda p: "zscale=t=bt709")
    monkeypatch.setattr(montaz.wl, "duration", lambda p: 4.0)
    monkeypatch.setattr(montaz.wl, "run", lambda cmd, *a, **k: wywolane.append((cmd, k.get("cwd"))))
    pomiary = iter([przed, po])
    monkeypatch.setattr(montaz, "drzenie", lambda p: next(pomiary))
    return wywolane


def test_montaz_stabilizuj_dwa_przejscia_vidstab(tmp_path, monkeypatch):
    wywolane = _stab_atrapa(monkeypatch, vidstab=True)
    out, info = montaz.stabilize(tmp_path / "a.mp4", tmp_path / "w" / "b.mp4", "mocna", statyw=True, zoom=2)
    (det, cwd1), (enc, cwd2) = wywolane
    vf1, vf2 = det[det.index("-vf") + 1], enc[enc.index("-vf") + 1]
    # plik ruchu we wspólnym katalogu roboczym obu przejść (ścieżka bez cytowania w filtrze)
    assert cwd1 == cwd2 and "result=ruch.trf" in vf1 and "input=ruch.trf" in vf2
    assert vf1 == "scale=1920:1080:flags=lanczos,vidstabdetect=shakiness=9:accuracy=15:result=ruch.trf:tripod=1"
    assert [f.split("=")[0] for f in vf2.split(",")] == \
        ["scale", "zscale", "vidstabtransform", "unsharp", "scale", "format"]     # 4K → 1080p, HDR przed vidstab
    assert "smoothing=30:optzoom=1:zoom=2" in vf2 and vf2.endswith(montaz.wl.TV_RANGE) and ":tripod=1" in vf2
    assert enc[enc.index("-map") + 1] == "0:v:0" and "0:a:0?" in enc and (tmp_path / "w").is_dir()
    assert info == {"sila": "mocna", "metoda": "vidstab", "statyw": True, "rozmiar": "1920x1080", "sek": 4.0,
                    "drzenie_przed_proc": 0.9, "drzenie_po_proc": 0.05}


def test_montaz_stabilizuj_uwagi_i_deshake(tmp_path, monkeypatch):
    _stab_atrapa(monkeypatch, vidstab=True, w=1080, h=1920, przed=0.1, po=0.1)
    _, info = montaz.stabilize(tmp_path / "a.mp4", tmp_path / "b.mp4", "lekka")
    assert info["rozmiar"] == "1080x1920" and "prawie stabilne" in info["uwaga"]
    _stab_atrapa(monkeypatch, vidstab=True, w=1080, h=1920, przed=1.0, po=0.8)
    assert "spadło mało" in montaz.stabilize(tmp_path / "a.mp4", tmp_path / "b.mp4", "srednia")[1]["uwaga"]
    wywolane = _stab_atrapa(monkeypatch, vidstab=False, w=1280, h=720)
    _, info = montaz.stabilize(tmp_path / "a.mp4", tmp_path / "b.mp4", "srednia")
    (enc, _), = wywolane                                                   # jedno przejście, bez pomiaru
    assert enc[enc.index("-vf") + 1].split(",")[:2] == ["zscale=t=bt709", "deshake=rx=32:ry=32"]
    assert info["metoda"] == "deshake" and "drzenie_przed_proc" not in info


@needs_ffmpeg
def test_montaz_stabilizuj_nagranie_z_reki(tmp_path):
    """Prawdziwy ffmpeg: drżący kadr ze zdjęcia → tyle samo sekund, dźwięk zostaje; na Linuksie drżenie
    wyraźnie spada (libvidstab na innych systemach liczy inaczej: tam tylko, że narzędzie zadziałało)."""
    if not montaz.ma_vidstab():
        pytest.skip("ffmpeg bez vidstab")
    zdj, src, out = tmp_path / "z.png", tmp_path / "reka.mp4", tmp_path / "stab.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=960x540", "-frames:v", "1",
                    str(zdj)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", str(zdj), "-f", "lavfi",
                    "-i", "sine=f=440:sample_rate=48000", "-vf",
                    "crop=840:472:60+14*sin(n*1.1)+9*sin(n*2.3):34+11*cos(n*1.5),scale=640:360,format=yuv420p",
                    "-t", "3", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(src)], check=True)
    assert montaz.main(["stabilizuj", str(src), "-o", str(out), "--sila", "srednia"]) == 0
    info = montaz.wl.probe(out)
    assert abs(info["duration"] - 3.0) < 0.2 and info["audio"] and info["video"]["pix_fmt"] == "yuv420p"
    if sys.platform.startswith("linux"):
        przed, po = montaz.drzenie(src), montaz.drzenie(out)
        assert przed > 0.3 and po < przed / 2


def test_montaz_napraw_fps_keeps_held_last_frame(tmp_path, monkeypatch):
    """ManimGX zapisuje MP4 o zmiennym klatkażu, końcowa klatka to jedna długa (2,53 s klipu = 31 klatek); sam `fps=30`
    dawał 1,03 s. napraw --fps: fps + tpad (kopie ostatniej klatki), potem -t z długości kontenera w pełnych klatkach."""
    wywolane = []
    monkeypatch.setattr(montaz.wl, "run", lambda cmd, *a, **k: wywolane.append(cmd))
    monkeypatch.setattr(montaz.wl, "duration", lambda p: 2.533)
    monkeypatch.setattr(montaz.wl, "sdr", lambda p: "")
    monkeypatch.setattr(montaz, "has_audio", lambda p: False)
    montaz.fix(tmp_path / "scena.mp4", tmp_path / "ok.mp4", fps=30)
    cmd = wywolane[0]
    assert cmd[cmd.index("-vf") + 1] == f"fps=30,tpad=stop_mode=clone:stop_duration=2.533,{montaz.wl.TV_RANGE}"
    assert cmd[cmd.index("-t") + 1] == "2.533333"                            # 76 pełnych klatek
    wywolane.clear()
    montaz.fix(tmp_path / "scena.mp4", tmp_path / "ok.mp4")                 # bez --fps: jak dotąd
    assert "-t" not in wywolane[0] and wywolane[0][wywolane[0].index("-vf") + 1] == montaz.wl.TV_RANGE
    assert montaz.wl.stala_klatka(60, 0.2) == "fps=60,tpad=stop_mode=clone:stop_duration=1.000"


@needs_ffmpeg
def test_montaz_napraw_fps_pads_video_to_container(tmp_path):
    """Prawdziwy ffmpeg: obraz krótszy od kontenera (1 s obrazu, 2,5 s dźwięku) → po napraw --fps 30 obraz trwa
    tyle co klip (75 klatek, stały klatkaż), bo ostatnia klatka jest trzymana, a nie ucięta."""
    src, out = tmp_path / "scena.mp4", tmp_path / "ok.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=30:d=1", "-f", "lavfi",
                    "-i", "sine=f=440:sample_rate=48000:d=2.5", "-pix_fmt", "yuv420p", "-c:v", "libx264",
                    "-c:a", "aac", str(src)], check=True)
    assert montaz.main(["napraw", str(src), "-o", str(out), "--fps", "30"]) == 0
    res = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                          "stream=nb_read_frames,r_frame_rate,avg_frame_rate", "-of", "json", str(out)],
                         capture_output=True, text=True, check=True)
    v = json.loads(res.stdout)["streams"][0]
    assert abs(int(v["nb_read_frames"]) - 75) <= 1 and v["r_frame_rate"] == v["avg_frame_rate"] == "30/1"
    assert abs(montaz.wl.duration(out) - 2.5) < 0.1


def test_montaz_glosnosc_limiter_true_peak(tmp_path, monkeypatch):
    """glosnosc: po loudnorm (192 kHz) limiter −2 dBFS, dopiero potem 48 kHz i AAC: szczyty między próbkami też
    zostają pod progiem qa_wideo (true peak ≤ −1). Bez niego film z kodu podniesiony z −16 do −14 LUFS miał +0,2 dBFS."""
    pomiar = ('{"input_i": "-16.04", "input_tp": "-1.40", "input_lra": "3.2", "input_thresh": "-26.3", '
              '"target_offset": "0.1"}')
    monkeypatch.setattr(montaz.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", pomiar))
    wywolane = []
    monkeypatch.setattr(montaz.wl, "run", lambda cmd, *a, **k: wywolane.append(cmd))
    out, info = montaz.loudness(tmp_path / "a.mp4", tmp_path / "b.mp4", -14.0)
    af = wywolane[0][wywolane[0].index("-af") + 1]
    lancuch = [f.split("=")[0] for f in af.split(",")]
    assert lancuch == ["loudnorm", "alimiter", "aresample"] and "linear=true" in af
    limit = float(re.search(r"alimiter=limit=([\d.]+)", af).group(1))
    assert limit <= 0.8 and "level=false" in af                                # −2 dBFS, bez podbijania po limiterze
    assert wywolane[0][wywolane[0].index("-c:v") + 1] == "copy" and info == {"przed_lufs": -16.04, "cel_lufs": -14.0}


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
    assert lock["sources"]["mg-styles-15"]["rev"] == nz.MGSTYLES_REV        # wzory stylów motion design
    assert "/videos/*.mp4" in nz.MGSTYLES_POMIN and "/demos/18-hanazi/assets/" in nz.MGSTYLES_POMIN
    assert "/demos/19-paperclip/assets/stickers/" in nz.MGSTYLES_POMIN       # zdjęcia bez podanego źródła
    assert lock["sources"]["huashu-art-motion"]["rev"] == nz.HUASHU_REV     # style malarskie i gramatyki explainera
    assert "/assets/" in nz.HUASHU_POMIN                                    # filmy pokazowe i postać autora
    assert any(e.endswith("spacex_wb/assets/strokes.js") for e in nz.HUASHU_POMIN)   # kreski kroju AR PL (Arphic)
    assert "huashu_pl.js" in nz.JARVO_JS_PLIKI and "huashu" in nz.TOOLS
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
    mg = nz.env_for("mg")
    assert mg["MGSTYLES"].endswith("mg-styles-15") and mg["CHROME_BIN"] == str(wrapper)
    hs = nz.env_for("huashu")
    assert hs["HUASHU"].endswith("huashu-art-motion") and hs["CHROME_BIN"] == str(wrapper) and "MGSTYLES" not in hs
    with pytest.raises(SystemExit):
        nz.env_for("puppeteer-core")
    monkeypatch.setenv("JARVO_EXTRAS", "media lemo")
    assert nz.full_extras()


def test_pinned_clone_upgrades_and_keeps_demos(tmp_path):
    """Nowy rev w repo Jarva przenosi istniejący klon na nowy commit; demo dodane przez `setup.sh demo` zostaje."""
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    up = tmp_path / "up"

    def git(*a, cwd=up):
        return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True,
                              env={**__import__("os").environ, **env}).stdout.strip()

    def commit(files: dict[str, str]) -> str:
        for rel, body in files.items():
            (up / rel).parent.mkdir(parents=True, exist_ok=True)
            (up / rel).write_text(body)
        git("add", "-A")
        git("commit", "-q", "-m", "c")
        return git("rev-parse", "HEAD")

    up.mkdir()
    git("init", "-q", "-b", "main")
    git("config", "uploadpack.allowFilter", "true")
    git("config", "uploadpack.allowAnySHA1InWant", "true")
    a = commit({"AGENTS.md": "v1", "styles/ink/STYLE.md": "s", "styles/ink/demo/d.js": "d", "styles/ink/poster.jpg": "p",
                "styleboard/x.html": "x"})
    b = commit({"AGENTS.md": "v2", "styles/engraving/STYLE.md": "e", "styles/engraving/demo/d.js": "d"})
    dest = tmp_path / "lib"
    nz.clone_pinned(f"file://{up}", a, dest, nz.LEMO_POMIN, keep=nz.LEMO_DODANE)
    assert nz.git_head(dest) == a and (dest / "styles/ink/STYLE.md").exists()
    assert not (dest / "styles/ink/demo").exists() and not (dest / "styleboard").exists()
    assert not (dest / "styles/ink/poster.jpg").exists()
    git("sparse-checkout", "add", "/styles/ink/demo/", cwd=dest)                    # jak `setup.sh demo ink`
    nz.clone_pinned(f"file://{up}", b, dest, nz.LEMO_POMIN, keep=nz.LEMO_DODANE)
    assert nz.git_head(dest) == b and (dest / "AGENTS.md").read_text() == "v2"
    assert (dest / "styles/ink/demo/d.js").exists() and not (dest / "styles/engraving/demo").exists()
    (dest / "AGENTS.md").write_text("lokalnie")
    nz.clone_pinned(f"file://{up}", b, dest, nz.LEMO_POMIN, keep=nz.LEMO_DODANE)  # ten sam commit i lista: nic
    assert (dest / "AGENTS.md").read_text() == "lokalnie"
    # ten sam commit, krótsza lista wykluczeń (jak SHOTCRAFT_POMIN zamiast całej galerii): plik wraca, demo zostaje
    nz.clone_pinned(f"file://{up}", b, dest, [e for e in nz.LEMO_POMIN if e != "/styleboard/"], keep=nz.LEMO_DODANE)
    assert (dest / "styleboard/x.html").exists() and (dest / "styles/ink/demo/d.js").exists()
    assert (dest / "AGENTS.md").read_text() == "v2" and not (dest / "styles/engraving/demo").exists()


def test_shotcraft_keeps_card_index_but_not_media_or_editor():
    """Shotcraft: indeks kart galerii zostaje (skill sprawdza w nim nazwę karty), filmy galerii i edytor nie."""
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    assert not any(e.startswith("/gallery/") and e.rstrip("/") in ("/gallery", "/gallery/api") for e in nz.SHOTCRAFT_POMIN)
    assert {"/gallery/media/", "/workbench/", "/jianying-export/"} <= set(nz.SHOTCRAFT_POMIN)


def test_lemo_markers_match_skill_setup(monkeypatch, tmp_path):
    """Znaczniki pakietów mają treść, którą liczy setup.sh skilla (cksum plików + wersja Pythona venv)."""
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    monkeypatch.setattr(nz, "LEMO", tmp_path)
    (tmp_path / "package.json").write_text("{}\n")
    (tmp_path / "package-lock.json").write_text("{\"lockfileVersion\": 3}\n")
    (tmp_path / "requirements.txt").write_text("numpy\nscipy\n")
    (tmp_path / "node_modules").mkdir()
    py = tmp_path / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\necho 'Python 3.12.7'\n")
    py.chmod(0o755)
    sig = 'sig() { cat "$@" 2>/dev/null | cksum | cut -d" " -f1; }; '
    node = subprocess.run(["sh", "-c", sig + "sig package.json package-lock.json"], cwd=tmp_path,
                          capture_output=True, text=True).stdout.strip()
    core = subprocess.run(["sh", "-c", sig + 'echo "$(sig requirements.txt)-$(.venv/bin/python -V 2>&1 | cut -d. -f1,2)"'],
                          cwd=tmp_path, capture_output=True, text=True).stdout.strip()
    assert nz.lemo_znacznik(None) == (tmp_path / "node_modules" / ".lemo-ok", node)
    assert nz.lemo_znacznik("core") == (tmp_path / ".venv" / ".lemo-core", core) and core.endswith("-Python 3.12")
    assert not nz.lemo_gotowe("core")
    (tmp_path / ".venv" / ".lemo-core").write_text(core + "\n")
    assert nz.lemo_gotowe("core")
    (tmp_path / "requirements.txt").write_text("numpy\n")                        # zmiana wymagań = instalacja od nowa
    assert not nz.lemo_gotowe("core")
    assert nz.lemo_poziomy() == ["core", "music"]
    monkeypatch.setenv("JARVO_EXTRAS", "lemo")
    assert nz.lemo_poziomy() == ["core", "music", "voice"]


def _zapisz(p, dane: bytes):
    p.write_bytes(dane)
    return p


def _ttf(*znaki: str) -> bytes:
    """Najmniejszy plik TTF z samą tabelą cmap (format 4): każdy znak wskazuje glif 1."""
    kody = sorted(ord(z) for z in znaki) + [0xFFFF]
    n = len(kody)
    pole = lambda wartosci: b"".join(struct.pack(">H", w & 0xFFFF) for w in wartosci)   # noqa: E731
    sub = (struct.pack(">HHHHHHH", 4, 16 + 8 * n, 0, 2 * n, 0, 0, 0) + pole(kody) + b"\0\0" + pole(kody)
           + pole([1 - k for k in kody]) + pole([0] * n))
    cmap = struct.pack(">HHHHI", 0, 1, 3, 1, 12) + sub
    return struct.pack(">IHHHH", 0x10000, 1, 16, 0, 0) + b"cmap" + struct.pack(">III", 0, 28, len(cmap)) + cmap


def test_kroje_from_google_fonts_and_polish_letters(tmp_path, capsys):
    """`narzedzia.py kroje`: brakujące kroje z fonts.css dochodzą z google/fonts z licencją, a krój bez polskich
    liter (albo spoza google/fonts) trafia do uwag; innej grubości nie podstawia."""
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    pl, ascii_ = _ttf(*"abcąćęłńóśźżĄĆĘŁŃÓŚŹŻ"), _ttf(*"abcó")
    assert set(map(chr, nz.znaki_kroju(_zapisz(tmp_path / "pl.ttf", pl)))) == set("abcąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
    assert nz.dopasuj_kroj("BodoniModa-Italic-VF.ttf", ["BodoniModa[opsz,wght].ttf",
                                                        "BodoniModa-Italic[opsz,wght].ttf"]) == "BodoniModa-Italic[opsz,wght].ttf"
    assert nz.dopasuj_kroj("Lobster.ttf", ["Lobster-Regular.ttf", "OFL.txt"]) == "Lobster-Regular.ttf"
    assert nz.dopasuj_kroj("Rajdhani-SemiBold.otf", ["Rajdhani-Bold.ttf", "Rajdhani-SemiBold.ttf"]) == "Rajdhani-SemiBold.ttf"
    assert nz.dopasuj_kroj("Rajdhani-Black.ttf", ["Rajdhani-Regular.ttf"]) is None

    class Zrodlo:
        katalog = {"lato": {"Lato-Regular.ttf": pl, "OFL.txt": b"OFL"},
                   "jost": {"Jost[wght].ttf": pl, "Jost-Italic[wght].ttf": ascii_, "OFL.txt": b"OFL"},
                   "oleoscript": {"OleoScript-Regular.ttf": ascii_, "OFL.txt": b"OFL"}}
        pytania: list[str] = []

        def pliki(self, rodzina):
            self.pytania.append(rodzina)
            return list(self.katalog.get(rodzina, {}))

        def plik(self, rodzina, nazwa):
            return self.katalog[rodzina][nazwa]

    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "fonts.css").write_text(
        "@font-face{src:url('Lato-Regular.ttf')}@font-face{src:url(Jost.ttf)}@font-face{src:url(\"Jost.ttf\")}"
        "@font-face{src:url(OleoScript-Regular.ttf)}@font-face{src:url(Mono.ttf)}@font-face{src:url(Nieznany-Regular.ttf)}"
        "@font-face{src:url(../wspolne/Inne.ttf)}", encoding="utf-8")
    _zapisz(fonts / "Mono.ttf", pl)                                      # już jest obok: nie pobiera
    _zapisz(fonts / "OFL-Jost.txt", b"OFL")                              # licencja z biblioteki (inna wielkość liter)
    zrodlo = Zrodlo()
    uwagi = nz.kroje(fonts, zrodlo)
    assert (fonts / "Lato-Regular.ttf").read_bytes() == pl and (fonts / "Jost.ttf").read_bytes() == pl
    assert (fonts / "OFL-lato.txt").exists() and not (fonts / "OFL-jost.txt").exists()
    assert sorted(zrodlo.pytania) == ["jost", "lato", "nieznany", "oleoscript"]   # każda rodzina raz, bez ../
    assert len(uwagi) == 2 and "OleoScript-Regular.ttf: brak polskich znaków ąćęłńśźż" in uwagi[0]
    assert "Nieznany-Regular.ttf: nie ma go w google/fonts" in uwagi[1]
    assert "↓ Jost.ttf ← google/fonts ofl/jost/Jost[wght].ttf" in capsys.readouterr().out
    zrodlo.pytania.clear()
    assert nz.kroje(fonts, zrodlo) == uwagi and zrodlo.pytania == ["nieznany"]   # drugi raz pyta tylko o brakujący


def test_kroje_mg_from_google_fonts_and_cjk_substitute(tmp_path, capsys):
    """`instaluj mg`: kroje z fonts.css wzorów i z ich kodu (`/demos/…ttf`) dochodzą z google/fonts (OFL, potem
    Apache) z licencją obok; chiński spoza google/fonts i Noto Serif SC (25 MB) to dowiązanie do Noto Sans SC."""
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")

    class Zrodlo:
        katalog = {("ofl", "inter"): {"Inter[opsz,wght].ttf": b"inter", "OFL.txt": b"OFL"},
                   ("ofl", "notosanssc"): {"NotoSansSC[wght].ttf": b"noto", "OFL.txt": b"OFL"},
                   ("ofl", "notoserifsc"): {"NotoSerifSC[wght].ttf": b"serif", "OFL.txt": b"OFL"},
                   ("apache", "luckiestguy"): {"LuckiestGuy-Regular.ttf": b"lucky", "LICENSE.txt": b"Apache"},
                   ("ofl", "mrdafoe"): {"MrDafoe-Regular.ttf": b"dafoe", "OFL.txt": b"OFL"}}
        pytania: list[tuple[str, str]] = []

        def pliki(self, rodzina, licencja="ofl"):
            self.pytania.append((licencja, rodzina))
            return list(self.katalog.get((licencja, rodzina), {}))

        def plik(self, rodzina, nazwa, licencja="ofl"):
            return self.katalog[(licencja, rodzina)][nazwa]

    mg = tmp_path / "mg"
    (mg / "assets/fonts").mkdir(parents=True)
    (mg / "assets/fonts/fonts.css").write_text("".join(
        f"@font-face{{src:url('/assets/fonts/{p}') format('truetype')}}" for p in (
            "cjk/alibabapuhuiti3/AlibabaPuHuiTi-3-85-Bold.ttf", "latin/inter/Inter-VF.ttf", "cjk/notosanssc/NotoSansSC-VF.ttf",
            "cjk/notoserifsc/NotoSerifSC-VF.ttf", "latin/luckiestguy/LuckiestGuy-Regular.ttf", "latin/brak/Brak-Bold.ttf")),
        encoding="utf-8")
    (mg / "demos/10-synthwave").mkdir(parents=True)
    (mg / "demos/10-synthwave/index.html").write_text(
        "<script>fetch('/demos/10-synthwave/assets/fonts/MrDafoe-Regular.ttf')</script>", encoding="utf-8")
    zrodlo = Zrodlo()
    uwagi = nz.kroje_mg(mg, zrodlo)
    f = mg / "assets/fonts"
    assert (f / "latin/inter/Inter-VF.ttf").read_bytes() == b"inter" and (f / "latin/inter/OFL.txt").exists()
    assert (f / "latin/luckiestguy/LuckiestGuy-Regular.ttf").read_bytes() == b"lucky"
    assert (f / "latin/luckiestguy/LICENSE.txt").read_bytes() == b"Apache"
    dafoe = mg / "demos/10-synthwave/assets/fonts"
    assert (dafoe / "MrDafoe-Regular.ttf").read_bytes() == b"dafoe" and (dafoe / "OFL-mrdafoe.txt").exists()
    for zastepczy in ("cjk/alibabapuhuiti3/AlibabaPuHuiTi-3-85-Bold.ttf", "cjk/notoserifsc/NotoSerifSC-VF.ttf"):
        p = f / zastepczy
        assert p.is_symlink() and p.read_bytes() == b"noto" and not os.path.isabs(os.readlink(p))
    assert ("ofl", "notoserifsc") not in zrodlo.pytania                       # 25 MB: nie pyta, od razu zastępczy
    assert uwagi == ["/assets/fonts/latin/brak/Brak-Bold.ttf: nie ma go w google/fonts; "
                     "wzór narysuje go krojem zastępczym albo nie wystartuje"]
    assert "↪ Noto Sans SC zamiast: AlibabaPuHuiTi-3-85-Bold.ttf, NotoSerifSC-VF.ttf" in capsys.readouterr().out
    zrodlo.pytania.clear()
    assert nz.kroje_mg(mg, zrodlo) == uwagi and zrodlo.pytania == [("ofl", "brak"), ("apache", "brak")]


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
    # płótno 2D na CPU: na GPU wyczyszczona nakładka (smuga) dawała w zrzucie treść sprzed dwóch klatek
    assert "--disable-accelerated-2d-canvas" in hw.BROWSER_ARGS


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


def test_html_huashu_preset(monkeypatch):
    """Strony silnika huashu-art-motion: prepare + renderFrame, rozmiar z __size, błąd startu przerywa czekanie."""
    o = hw.resolve_opts("huashu", query={"film": "gallery"})
    assert o["serwer"] and o["query"] == {"render": "1", "film": "gallery"}
    assert "window.prepare" in o["seek"] and "window.renderFrame(t)" in o["seek"]
    assert o["blad_startu"] == "window.__bootFailed" and "__size" in o["rozmiar_js"]
    assert hw.resolve_opts("jarvo")["blad_startu"] is None

    import types
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.TimeoutError = type("TimeoutError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    class Strona:
        def wait_for_function(self, warunek, timeout):
            raise sync_api.TimeoutError("czekam")

        def evaluate(self, kod):
            return "没有这个语法：clips/x.js（HTTP 404）" if "__bootFailed" in kod else None

    with pytest.raises(SystemExit, match="strona nie wstała: .*clips/x.js"):
        hw.czekaj_gotowe(Strona(), "window.__ready === true", [], "window.__bootFailed")


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
    monkeypatch.setattr(nz_mod, "JARVO_JS", tmp_path / "jarvo-js")
    monkeypatch.setattr(nz_mod, "HUASHU", tmp_path / "huashu")
    (tmp_path / "huashu" / "scripts" / "engine" / "clips").mkdir(parents=True)
    (tmp_path / "huashu" / "scripts" / "engine" / "clips" / "y2_vox.js").write_text("CLIPS.y2_vox = {};")
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
        with urllib.request.urlopen(base + "/_lib/jarvo/ruch.js") as r:            # nasz moduł, kopia ze scripts/
            assert b"export const CHARAKTERY" in r.read()
        assert (tmp_path / "jarvo-js" / "ruch.js").read_bytes() == (REPO / "profiles/jarvo-wideo/scripts/ruch.js").read_bytes()
        with urllib.request.urlopen(base + "/_lib/kroje/kroje.css") as r:          # kroje z polskimi znakami (edytor HQ)
            assert b'font-family: "Anton"' in r.read()
        with urllib.request.urlopen(base + "/_lib/huashu/clips/y2_vox.js") as r:   # silnik huashu-art-motion
            assert b"CLIPS.y2_vox" in r.read()
        with urllib.request.urlopen(base + "/_lib/jarvo/huashu_pl.js") as r:       # polska nakładka na silnik
            assert b"HUASHU_PL" in r.read()
        for zle in ("/_lib/../../sekret.txt", "/_lib/jarvo/../../sekret.txt", "/_lib/kroje/../../../sekret.txt",
                    "/_lib/huashu/../../../../sekret.txt"):
            with pytest.raises(urllib.error.HTTPError):
                urllib.request.urlopen(base + zle)
    finally:
        httpd.shutdown()
    # preset mg: /assets/, /demos/ z instalacji wzorów, /node_modules/ = wspólne biblioteki; bez wyjścia poza nie
    monkeypatch.setattr(nz_mod, "MGSTYLES", tmp_path / "mg")
    (tmp_path / "mg" / "assets" / "textures").mkdir(parents=True)
    (tmp_path / "mg" / "assets" / "textures" / "grain.png").write_bytes(b"png")
    (tmp_path / "mg" / "demos" / "01").mkdir(parents=True)
    (tmp_path / "mg" / "demos" / "01" / "film.js").write_text("export const f = 1;")
    o = hw.resolve_opts("mg")
    assert o["serwer"] and "renderAt" in o["seek"] and "getAnimations" in o["seek"] and "DEMO" in o["rozmiar_js"]
    assert hw.aliasy(hw.resolve_opts("jarvo")) == {}
    httpd = hw.serve(site, lib=True, alias=hw.aliasy(o))
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        for url, tresc in (("/assets/textures/grain.png", b"png"), ("/demos/01/film.js", b"export"),
                           ("/node_modules/three/build/three.module.js", b"ok"), ("/index.html", b"ok")):
            with urllib.request.urlopen(base + url) as r:
                assert tresc in r.read(), url
        for zle in ("/assets/../../sekret.txt", "/demos/../../sekret.txt", "/node_modules/../../sekret.txt"):
            with pytest.raises(urllib.error.HTTPError):
                urllib.request.urlopen(base + zle)
    finally:
        httpd.shutdown()
    # stara kopia + kilka przeglądarek renderu naraz: na końcu cały plik, bez resztek plików tymczasowych
    import threading
    (tmp_path / "jarvo-js" / "ruch.js").write_text("stare")
    watki = [threading.Thread(target=nz_mod.sync_jarvo_js) for _ in range(8)]
    [w.start() for w in watki]
    [w.join() for w in watki]
    assert (tmp_path / "jarvo-js" / "ruch.js").read_bytes() == (REPO / "profiles/jarvo-wideo/scripts/ruch.js").read_bytes()
    assert sorted(x.name for x in (tmp_path / "jarvo-js").iterdir()) == sorted(nz_mod.JARVO_JS_PLIKI)
    for nazwa in nz_mod.JARVO_JS_PLIKI:                                         # każdy moduł Jarva = kopia ze scripts/
        assert (tmp_path / "jarvo-js" / nazwa).read_bytes() == (REPO / "profiles/jarvo-wideo/scripts" / nazwa).read_bytes()


def test_html_parallel_browsers_split_the_timeline(monkeypatch, tmp_path):
    """--rownolegle: kolejne odcinki osi po równo, każdy w swoim wątku; klatki wracają w kolejności osi."""
    assert hw.ile_przegladarek(300, None, rdzenie=8, wolne_gb=16) == 4          # samo: do 4
    assert hw.ile_przegladarek(300, None, rdzenie=4, wolne_gb=16) == 2          # połowa rdzeni
    assert hw.ile_przegladarek(300, None, rdzenie=16, wolne_gb=1.5) == 1        # ~1 GB na przeglądarkę
    assert hw.ile_przegladarek(60, 6) == 2 and hw.ile_przegladarek(10, 3) == 1  # co najmniej 24 klatki na przeglądarkę
    times = hw.frame_times(4, 25)                                               # 100 klatek
    names = [f"f{i:05d}.png" for i in range(len(times))]
    kawalki = hw.odcinki(times, names, 3)
    assert [len(t) for t, _ in kawalki] == [34, 34, 32] and [n for _, ns in kawalki for n in ns] == names
    import threading
    razem, odcinki = threading.Barrier(3, timeout=10), []

    def fake_capture(src, t, n, out_dir, *rest):
        odcinki.append(t[0])
        razem.wait()                                                        # trzy przeglądarki naraz, nie po kolei
        return [out_dir / x for x in n]

    monkeypatch.setattr(hw, "capture", fake_capture)
    frames = hw.capture_rownolegle("a.html", times, names, tmp_path, {}, 25, (1920, 1080), False, 1.0, False, 0, 3)
    assert frames == [tmp_path / x for x in names] and sorted(odcinki) == [0, times[34], times[68]]
    razem = threading.Barrier(1)
    assert hw.capture_rownolegle("a.html", times[:5], names[:5], tmp_path, {}, 25, (1920, 1080), False, 1.0, False, 0, 1) \
        == [tmp_path / x for x in names[:5]]


def test_html_fast_frame_capture_via_cdp(tmp_path):
    """Zrzut klatki prosto z Chromium (CDP, optimizeForSpeed); bez sesji CDP → None (wtedy zwykły page.screenshot)."""
    import base64
    wyslane = []

    class Cdp:
        def send(self, metoda, parametry):
            wyslane.append((metoda, parametry))
            return {"data": base64.b64encode(b"\x89PNG-klatka").decode()}

    class Kontekst:
        def __init__(self, ok): self.ok = ok
        def new_cdp_session(self, page):
            if not self.ok:
                raise RuntimeError("to nie Chromium")
            return Cdp()

    class Strona:
        def __init__(self, ok): self.context = Kontekst(ok)

    zrzut = hw.zrzut_cdp(Strona(True))
    zrzut(tmp_path / "f00000.png")
    assert (tmp_path / "f00000.png").read_bytes() == b"\x89PNG-klatka"
    assert wyslane == [("Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True})]
    assert hw.zrzut_cdp(Strona(False)) is None
    hd = (1920, 1080)                                                       # 600 klatek 1080p ≈ 1,2 GB pikseli
    assert hw.zrzut_na_dysk(600, hd, 1.0, 10 * 10**9) is True                # miejsce na szybki zrzut (~2 B/px)
    assert hw.zrzut_na_dysk(600, hd, 1.0, 2 * 10**9) is False                # tylko na zwykły (~1 B/px)
    with pytest.raises(SystemExit, match="za mało miejsca"):
        hw.zrzut_na_dysk(600, hd, 1.0, 10**9)
    assert hw.zrzut_na_dysk(600, hd, 2.0, 6 * 10**9) is False                # --skala 2 = 4× więcej pikseli


def test_render_slots_limit_and_memory_gate(monkeypatch, tmp_path):
    """Najwyżej JARVO_RENDER_MIEJSCA renderów naraz; drugi obok trwającego tylko przy wolnej pamięci ≥ progu;
    miejsce trzymane przez padnięty proces wraca samo (flock)."""
    monkeypatch.setenv("JARVO_RENDER_KATALOG", str(tmp_path))
    monkeypatch.setenv("JARVO_RENDER_MIEJSCA", "2")
    monkeypatch.delenv("JARVO_RENDER_ZAJETE", raising=False)
    trzymaj = ("import fcntl, sys, time; f = open(sys.argv[1], 'a+'); fcntl.flock(f, fcntl.LOCK_EX); "
               "print('ok', flush=True); time.sleep(30)")
    inny = subprocess.Popen([sys.executable, "-c", trzymaj, str(tmp_path / "miejsce0")], stdout=subprocess.PIPE, text=True)
    try:
        assert inny.stdout.readline().strip() == "ok"                           # ktoś renderuje w miejscu 0
        monkeypatch.setattr(wl, "wolna_pamiec", lambda: (55.0, 4.0))
        with wl.miejsce_renderu("test"):
            assert os.environ["JARVO_RENDER_ZAJETE"] == "1" and (tmp_path / "miejsce1").read_text().startswith(str(os.getpid()))
            with wl.miejsce_renderu("w środku"):                                # render z renderu nie zajmuje drugiego
                pass
        assert "JARVO_RENDER_ZAJETE" not in os.environ
        # mało pamięci przy trwającym renderze: czeka; gdy tamten padnie, rusza od razu
        monkeypatch.setattr(wl, "wolna_pamiec", lambda: (12.0, 1.0))
        monkeypatch.setattr(wl.time, "sleep", lambda s: inny.kill() or inny.wait())
        with wl.miejsce_renderu("test"):
            pass
        assert inny.returncode is not None
    finally:
        inny.kill()
        inny.wait()


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
    types = files - {"kontrakt-html", "ruch-i-kompozycja"}               # wspólne dla wielu rodzajów
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
    monkeypatch.setattr(insp, "AIM_URL", "http://127.0.0.1:9/brak2.json")
    with pytest.raises(SystemExit):
        insp.load()                                                        # bez cache: jasny komunikat, nie traceback
    cached = wl.cache_dir("inspiracje") / f"videos-{insp.REV[:12]}.json"
    cached.write_text(json.dumps([{"slug": "x"}]))
    assert [it["slug"] for it in insp.load()] == ["x"]                     # drugie źródło bez cache: pominięte
    aim = wl.cache_dir("inspiracje") / f"aim-{insp.AIM_REV[:12]}.json"
    aim.write_text(json.dumps({"cases": [{"id": "1", "category": "产品宣传", "author": {"handle": "a"},
                                          "prompt": {"status": "original", "text": "launch film"}, "source": {"url": "u"}}]}))
    got = insp.load()
    assert [it["slug"] for it in got] == ["x", "aim-1"] and got[1]["category"] == "product" and not got[1]["prompt_partial"]


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
def test_qa_rozpietosc_glosnosci(tmp_path):
    """LRA (za skillem fframes): równy dźwięk przechodzi, połowa filmu o 16 dB ciszej to ostrzeżenie (cel 4–10 LU)."""
    qa = _wscript("qa_wideo")
    pliki = {}
    for nazwa, af in (("rowny", "volume=0.5"), ("skoki", "volume='if(lt(t,6),0.08,0.5)':eval=frame")):
        f = pliki[nazwa] = tmp_path / f"{nazwa}.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=12",
                        "-f", "lavfi", "-i", "anoisesrc=c=pink:d=12:a=0.3", "-af", af, "-shortest",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", str(f)], check=True)
    rowny, skoki = qa.check(pliki["rowny"], None, None, False, None), qa.check(pliki["skoki"], None, None, False, None)
    assert rowny["metryki"]["lra"] < 4 and not any("rozpiętość" in w for w in rowny["ostrzezenia"])
    assert skoki["metryki"]["lra"] > 10 and any("rozpiętość głośności" in w for w in skoki["ostrzezenia"])


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_rytm_sfx_peak(tmp_path):
    rytm = _wscript("rytm")
    wav = tmp_path / "klik.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc='if(gte(t,0.15),sin(2*PI*900*t)*exp(-40*(t-0.15)),0)':s=44100:d=0.6", str(wav)], check=True)
    assert rytm.peak(wav)["szczyt"] == pytest.approx(0.15, abs=0.02)


def _perkusja_wav(path, bpm=120.0, dur=20.0, first=0.25, glosna=None, przesun=0.0):
    """Pętla perkusji: stopa na 1 i 3 (55 Hz ze spadkiem wysokości), werbel na 2 i 4 (szum), talerz na ósemkach
    (9 kHz); `glosna` = chwila jednej mocniejszej stopy. Bez ffmpeg (moduł wave)."""
    import random
    import wave
    sr, p = 44100, 60 / bpm
    rnd = random.Random(7)
    x = [0.0] * int(sr * dur)

    def dodaj(t0, dl, f):
        i0 = int((t0 + przesun) * sr)
        for i in range(max(0, i0), min(len(x), i0 + int(dl * sr))):
            x[i] += f((i - i0) / sr)
    k = 0
    while first + k * p / 2 < dur:
        t = first + k * p / 2
        dodaj(t, 0.05, lambda u: 0.12 * math.sin(2 * math.pi * 9000 * u) * math.exp(-60 * u))
        if k % 2 == 0:
            if (k // 2) % 2 == 0:
                g = 1.0 if glosna is not None and abs(t - glosna) < 0.01 else 0.55
                dodaj(t, 0.4, lambda u, g=g: g * math.sin(2 * math.pi * (55 * u + 2 * (1 - math.exp(-30 * u)))) * math.exp(-8 * u))
            else:
                dodaj(t, 0.2, lambda u: 0.35 * rnd.uniform(-1, 1) * math.exp(-18 * u))
        k += 1
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(int(max(-1.0, min(1.0, v)) * 32000).to_bytes(2, "little", signed=True) for v in x))
    return path


def test_rytm_siatka_pol_i_podwojna():
    """Za wolna siatka gubi werbel na 2 i 4, za szybka ma puste bity: wygrywa prawdziwe tempo (bez ffmpeg)."""
    rytm = _wscript("rytm")
    p = 0.5
    uderzenia = sorted([{"t": round(0.25 + k * p, 3), "s": 0.8, "k": "stopa" if k % 2 == 0 else "werbel"}
                        for k in range(32)], key=lambda u: u["t"])
    for okres in (1.0, 0.25):                                              # 60 i 240 BPM zamiast 120
        first, per, siatka = rytm.wybierz_siatke(0.25, okres, 16.5, uderzenia)
        assert per == pytest.approx(0.5) and first == pytest.approx(0.25) and siatka["mnoznik"] != 1
    first, per, siatka = rytm.wybierz_siatke(0.25, 0.5, 16.5, uderzenia)
    assert per == 0.5 and siatka["mnoznik"] == 1 and siatka["ocena"] == "pewna"
    assert siatka["trafienia"] == 1 and siatka["sredni_blad_ms"] == 0
    nai = rytm.najmocniejsze([{"t": 0.25 + k * p, "s": 0.5 + (0.4 if k in (4, 6, 20) else 0), "k": "stopa"}
                              for k in range(0, 32, 2)], [0.25 + k * p for k in range(32)], p)
    assert [o["t"] for o in nai] == [2.25, 10.25] and all(o["na_bicie"] for o in nai)   # 6 za blisko 4 (< 16 bitów)
    nai = rytm.najmocniejsze([{"t": 0.75, "s": 1.0, "k": "stopa"}, {"t": 4.5, "s": 1.0, "k": "stopa"},
                              {"t": 4.25, "s": 0.6, "k": "stopa"}, {"t": 12.25, "s": 0.5, "k": "stopa"}],
                             [0.25 + k * p for k in range(32)], p)
    assert [o["t"] for o in nai] == [4.25, 12.25]          # w 1. sekundzie i w pół bitu: nie, choć głośniejsze
    assert rytm.opis_talerzy([{"t": 0.0, "do": 2.0, "talerze": 8}, {"t": 2.0, "do": 4.0, "talerze": 1},
                              {"t": 4.0, "do": 5.1, "talerze": 0}]) == [
        "takt 1 (0.0–2.0 s): talerze gęsto", "takty 2–3 (2.0–5.1 s): talerze rzadko"]
    assert rytm.czasy_planu([{"sfx": "pop", "t": 1.2}, {"t": 0.4, "na_bit": False}, 2.0]) == [1.2, 2.0]
    assert rytm.czasy_planu({"ciecia": {"co_takt": [0.25, 2.25]}}) == [0.25, 2.25]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_rytm_pasma_perkusji(tmp_path):
    """Stopa, werbel i talerze z osobnych pasm; najmocniejsza stopa wskazana jako miejsce na uderzenie kadru."""
    rytm = _wscript("rytm")
    r = rytm.analyze(_perkusja_wav(tmp_path / "petla.wav", glosna=10.25))
    assert r["bpm"] == pytest.approx(120, abs=0.5) and r["siatka"]["ocena"] in ("pewna", "dobra")
    po = {k: [u["t"] for u in r["uderzenia"] if u["k"] == k] for k in ("stopa", "werbel", "talerz")}
    assert len(po["stopa"]) == pytest.approx(20, abs=1) and len(po["werbel"]) == pytest.approx(20, abs=1)
    assert all(abs((t - 0.25) % 1.0) < 0.03 or abs((t - 0.25) % 1.0 - 1) < 0.03 for t in po["stopa"])
    assert all(abs((t - 0.75) % 1.0) < 0.03 or abs((t - 0.75) % 1.0 - 1) < 0.03 for t in po["werbel"])
    assert len(po["talerz"]) >= 70                                          # ósemki: 4 na sekundę
    assert 10.25 in [round(o["t"], 2) for o in r["najmocniejsze"]] or \
        any(abs(o["t"] - 10.25) < 0.02 for o in r["najmocniejsze"])
    assert all(i["talerze"] >= 7 for i in r["takty_info"][:-1])


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_rytm_sprawdz_ciecia_po_renderze(tmp_path):
    """Cięcia z obrazu kontra bity z dźwięku gotowego filmu; wspólne przesunięcie wszystkich cięć rozpoznane."""
    rytm = _wscript("rytm")
    wav = _perkusja_wav(tmp_path / "petla.wav", dur=10.0)
    film = tmp_path / "film.mp4"
    kolory = [("red", 2.25), ("blue", 2.5), ("green", 1.65), ("yellow", 3.6)]   # cięcia 2,25 · 4,75 · 6,40 (źle)
    wejscia = []
    for c, d in kolory:
        wejscia += ["-f", "lavfi", "-i", f"color=c={c}:s=320x180:r=30:d={d}"]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *wejscia, "-i", str(wav), "-filter_complex",
                    f"concat=n={len(kolory)}:v=1:a=0,format=yuv420p[v]", "-map", "[v]", "-map", f"{len(kolory)}:a",
                    "-c:a", "aac", "-shortest", str(film)], check=True)
    assert rytm.ciecia_obrazu(film) == pytest.approx([2.233, 4.733, 6.4], abs=0.04)
    r = rytm.sprawdz(film, rytm.ciecia_obrazu(film), 30.0)
    assert [w["ocena"] for w in r["ciecia"]][:2] != ["popraw", "popraw"] and r["ciecia"][2]["ocena"] == "popraw"
    assert r["popraw"] == 1
    assert rytm.main(["sprawdz", str(film), "--ciecia", "2.25,4.75", "--json", str(tmp_path / "r.json")]) == 0
    assert rytm.main(["sprawdz", str(film)]) == 1
    late = rytm.sprawdz(wav, [0.25 + k * 0.5 + 0.08 for k in range(16)], 30.0)    # 80 ms za późno, wszystkie
    assert late["wspolne_przesuniecie_ms"] == pytest.approx(80, abs=12) and late["popraw"] == 0


def test_narzedzia_exempts_exact_pins_from_uv_quarantine():
    """Obraz Hermesa ma exclude-newer 14 dni: dokładne piny (playwright==X) muszą być zwolnione, reszta nie."""
    nz = _wscript("narzedzia")
    assert nz.uv_exempt(["numpy", "playwright==1.63.0", "imageio"]) == ["--exclude-newer-package", "playwright=false"]
    assert nz.py_module("playwright==1.63.0") == "playwright" and nz.py_module("pillow") == "PIL"


@pytest.mark.skipif(not shutil.which("node"), reason="brak node")
def test_ruch_js_characters_landing_and_smear(tmp_path):
    """ruch.js: 6 charakterów, lądowanie kończy się dokładnie w celu (skala 1, bez ściśnięcia), przestrzelenie skali
    = `przestrzal`, wyjście szybsze od wejścia, smuga rysuje kapsułę tylko przy ruchu."""
    skrypt = tmp_path / "t.mjs"
    skrypt.write_text("""
import * as R from %s;
const out = {};
for (const [n, c] of Object.entries(R.CHARAKTERY)) {
  let maxS = 0, minSy = 9;
  for (let i = 0; i <= 200; i++) { const l = R.ladowanie(i / 200 * c.czas, 0, n); maxS = Math.max(maxS, l.skala); minSy = Math.min(minSy, l.sy); }
  const kon = R.ladowanie(c.czas + 1, 0, n), pocz = R.ladowanie(-1, 0, n);
  out[n] = {maxS, minSy, kon: [kon.p, kon.skala, kon.sy, kon.u], pocz: [pocz.p, pocz.skala], wyj: R.wyjscie(c.czas * 0.5, 0, n).p};
}
const ops = [];
const g = {save() {}, restore() {}, beginPath() {}, moveTo(...a) { ops.push(['m', ...a]); }, lineTo(...a) { ops.push(['l', ...a]); },
           stroke() { ops.push(['s']); }, createLinearGradient() { return {addColorStop(o, c) { ops.push(['c', o, c]); }}; }};
const ruch = R.smuga(g, (t) => [1000 * t, 50], 1, 10, '#ff3300');
const stoi = R.smuga(g, () => [5, 5], 1, 10, '#ff3300');
let blad = '';
try { R.ladowanie(0, 0, 'nerwowy'); } catch (e) { blad = String(e.message); }
console.log(JSON.stringify({out, ops, ruch, stoi, blad, rozc: R.rozciagniecie(0)}));
""" % json.dumps(str(REPO / "profiles/jarvo-wideo/scripts/ruch.js")))
    wynik = json.loads(subprocess.run(["node", str(skrypt)], capture_output=True, text=True, check=True).stdout)
    out = wynik["out"]
    assert list(out) == ["zaufanie", "luksus", "odwazny", "zabawny", "spokojny", "przyjazny"]
    for n, w in out.items():
        assert w["kon"] == [1, 1, 1, 1] and w["pocz"] == [0, 0.92], n             # koniec w celu, start od 0,92
        assert w["wyj"] == 0, n                                                    # wyjście = połowa czasu wejścia
    assert out["zaufanie"]["maxS"] == pytest.approx(1.0) and out["zaufanie"]["minSy"] == 1   # nie skacze, nie ściska
    assert out["odwazny"]["maxS"] == pytest.approx(1.12, abs=0.002) and out["odwazny"]["minSy"] < 0.9
    assert out["luksus"]["maxS"] == pytest.approx(1.02, abs=0.002)
    assert wynik["ruch"] is True and wynik["stoi"] is False
    assert ["c", 0, "#ff330000"] in wynik["ops"] and ["c", 1, "#ff3300"] in wynik["ops"]   # ogon przezroczysty
    assert "nieznany charakter" in wynik["blad"] and wynik["rozc"] == {"sx": 1, "sy": 1}


@pytest.mark.skipif(not shutil.which("node"), reason="brak node")
def test_style_motion_js_modules(tmp_path):
    """Moduły technik stylów (kreska, morph, crt, plotno, piksel): ta sama klatka = ten sam rysunek, nowe ziarno =
    wrzenie linii o ~2 px, arkusz ekspozycji liczy rysunki, morph trzyma pole i przechodzi przez koło, ściśnięcie
    nie zmienia pola, kafle papieru i ziarna bez szwu i bez przesunięcia jasności, paleta przechodzi stopniami."""
    d = REPO / "profiles/jarvo-wideo/scripts"
    skrypt = tmp_path / "t.mjs"
    skrypt.write_text("""
import * as K from %s; import * as M from %s; import * as C from %s; import * as P from %s; import * as X from %s;
const g = {beginPath() {}, moveTo() {}, lineTo() {}, closePath() {}, fill() {}, save() {}, restore() {}, clip() {}};
const linia = (z) => K.kreska(g, [[100, 100], [300, 140], [500, 100]], {ziarno: z});
const a = linia(3), b = linia(3), c = linia(4);
const plan = [[0, 2], [8, 1], [24, 2]];
const pr = M.para([[0, 0], [100, 0], [100, 100], [0, 100]], [[300, 0], [400, 100], [200, 100]], {n: 120});
const pol = M.przemiana(pr, 0.5), [sx, sy] = M.srodek(pol), Q = M.macierzScisku(0.7, 1.3);
const papier = P.kafelPapieru(256), ziarno = P.kafelZiarna(64);
let szew = 0, sr = 0;
for (let y = 0; y < 256; y++) szew = Math.max(szew, Math.abs(papier[y * 256 * 4] - papier[(y * 256 + 255) * 4]));
for (let i = 0; i < ziarno.length; i += 4) sr += ziarno[i];
const bf = X.bufor(8, 4); X.linia(bf, 0, 0, 7, 3, 2);
const pal = X.paleta(['#000000', '#ffffff', '#808080', '#404040', '#c0c0c0'], {dzien: [1, 0], noc: [0, 1]});
console.log(JSON.stringify({
  ten_sam: JSON.stringify(a) === JSON.stringify(b),
  wrzenie: Math.max(...a.map((p, i) => Math.hypot(p[0] - c[i][0], p[1] - c[i][1]))),
  eksp: [0, 7, 8, 23, 24, 26].map((f) => { const e = K.ekspozycja(f, plan); return [e.f, e.id, e.krok]; }),
  rys: K.rysunek(1.0, 24),
  pola: [M.pole(M.przemiana(pr, 0)), M.pole(pol), M.pole(M.przemiana(pr, 1))],
  promienie: pol.map((p) => Math.hypot(p[0] - sx, p[1] - sy)),
  det: Q[0] * Q[3] - Q[1] * Q[2], uderzenie: [M.uderzenie(1 - 2 / 30, 1), M.uderzenie(1, 1), M.uderzenie(3, 1)],
  kolor: [M.mieszajKolor('#ff0000', '#0000ff', 0), M.mieszajKolor('#ff0000', '#0000ff', 1), M.zOklab(M.oklab('#ffb627'))],
  szew, srednia: sr / (ziarno.length / 4), kropka: [P.promienKropki(1, 6.5), P.promienKropki(0, 6.5)],
  bres: Array.from(bf.px).join(''), stopnie: [0, 0.2, 0.5, 1].map((u) => Array.from(pal.tablica('dzien', 'noc', u))),
  bayer: [0, 1, 2, 3].flatMap((y) => [0, 1, 2, 3].map((x) => X.bayer(x, y))).filter((v) => v < 0.5).length,
  tryby: Object.keys(C.TRYBY), wl: [C.wlaczanie(0, 0), C.wlaczanie(1, 0), C.wylaczanie(0.1, 0)],
}));
""" % tuple(json.dumps(str(d / n)) for n in ("kreska.js", "morph.js", "crt.js", "plotno.js", "piksel.js")))
    w = json.loads(subprocess.run(["node", str(skrypt)], capture_output=True, text=True, check=True).stdout)
    assert w["ten_sam"] and 1.0 < w["wrzenie"] < 3.0                     # amp 2,2 px: widać, ale linia ta sama
    assert w["eksp"] == [[0, 0, 2], [6, 3, 2], [8, 4, 1], [23, 19, 1], [24, 20, 2], [26, 21, 2]]
    assert w["rys"]["t"] == 1 and w["rys"]["krok"] == 2 and w["rys"]["id"] == 12
    assert w["pola"][0] == pytest.approx(10000) and w["pola"][1] == pytest.approx(10000, rel=0.01)
    assert w["pola"][2] == pytest.approx(5000 * 2, rel=0.01)              # trójkąt 200×100 → pole 10 000
    assert max(w["promienie"]) - min(w["promienie"]) < 0.5                # w połowie drogi: koło
    assert w["det"] == pytest.approx(1) and w["uderzenie"][0] == 0 and w["uderzenie"][2] == 0 and w["uderzenie"][1] > 0
    assert w["kolor"] == ["#ff0000", "#0000ff", "#ffb627"]
    assert w["szew"] <= 3 and w["srednia"] == pytest.approx(128, abs=2)
    assert w["kropka"][0] == 0 and w["kropka"][1] == pytest.approx(6.5 / 2 * 2 ** 0.5)
    assert w["bres"] == "22000000002200000000220000000022"
    assert w["stopnie"] == [[1, 0], [4, 3], [3, 4], [0, 1]]               # biel → jasnoszary → ciemnoszary → czerń
    assert w["bayer"] == 8 and w["tryby"] == ["crt", "vhs", "hud"] and w["wl"] == [0, 1, 0.5]


def test_czekaj_gotowe_mowi_dlaczego(monkeypatch):
    """Strona bez gotowości: zamiast samego timeoutu powód (błędy JS i brakujące pliki, każdy raz)."""
    import types

    class Timeout(Exception):
        pass
    api = types.ModuleType("playwright.sync_api")
    api.TimeoutError = Timeout
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)

    class Strona:
        proby = 0

        def wait_for_function(self, warunek, timeout):
            assert timeout == 500
            self.proby += 1
            raise Timeout(warunek)
    bledy = ["brak pliku /assets/fonts/x.ttf (HTTP 404)", "init failed", "init failed"]
    s = Strona()
    with pytest.raises(SystemExit, match=r"nie jest gotowa po 3.5 s \(window.__ready === true\): "
                                         r"brak pliku /assets/fonts/x.ttf \(HTTP 404\); init failed$"):
        hw.czekaj_gotowe(s, "window.__ready === true", bledy)      # błąd JS: 3 s po nim koniec, nie minuta
    assert s.proby == 7
    with pytest.raises(SystemExit, match=r"po 60 s .*: brak pliku /a.png \(HTTP 404\)$"):
        hw.czekaj_gotowe(Strona(), "window.__ready === true", ["brak pliku /a.png (HTTP 404)"])   # sam brak pliku: czeka
    with pytest.raises(SystemExit, match="bez błędów JS i brakujących plików"):
        hw.czekaj_gotowe(Strona(), "window.__ready === true", [])

    class Gotowa(Strona):
        def wait_for_function(self, warunek, timeout):
            self.proby += 1
            if self.proby < 3:
                raise Timeout(warunek)
    g = Gotowa()
    hw.czekaj_gotowe(g, "window.__ready === true", ["blad przejsciowy"])
    assert g.proby == 3


def _shotcraft(root):
    """Mała kopia video-shotcraft: library.json, dwie karty, ATTRIBUTION z tabelą kart z cudzych filmów."""
    (root / "gallery" / "api").mkdir(parents=True)
    (root / "references" / "shots" / "camera").mkdir(parents=True)
    (root / "references" / "shots" / "typography").mkdir(parents=True)
    karty = [
        {"name": "crash-zoom-punch", "category": "camera", "energy": "高（瞬时）", "duration": "约 0.5s", "summary": "急推",
         "use": "强调", "intention": "", "source": "references/shots/camera/crash-zoom-punch.md", "styles": [{"key": "crash-zoom-punch"}]},
        {"name": "paper-title-card", "category": "typography", "energy": "低（呼吸）", "duration": "1.7s", "summary": "纸上标题",
         "use": "title", "intention": "", "source": "references/shots/typography/paper-title-card.md", "styles": [{"key": "paper"}]},
        {"name": "blur-slide", "category": "typography", "energy": "A 中低", "duration": "1s", "summary": "模糊滑入",
         "use": "", "intention": "", "source": "references/shots/typography/blur-slide.md", "styles": []},
        {"name": "shot-transitions", "category": "transition", "energy": "n/a（技法卡）", "duration": "", "summary": "转场",
         "use": "", "intention": "", "source": "references/shots/transition/shot-transitions.md", "styles": []},
    ]
    (root / "gallery" / "api" / "library.json").write_text(json.dumps({"cards": karty}, ensure_ascii=False), encoding="utf-8")
    (root / "references" / "shots" / "camera" / "crash-zoom-punch.md").write_text(
        "---\nname: crash-zoom-punch\n能量: 高\n---\n## 参考实现\n`demos/camera/crash-zoom-punch/CrashZoom.tsx`\n", encoding="utf-8")
    (root / "references" / "shots" / "typography" / "paper-title-card.md").write_text(
        "---\nname: paper-title-card\n---\n## 参考实现\ndemos/typography/paper-title-card/PaperTitleCard.tsx（原 template）\n"
        "原片出处：notion-ai.mp4 0:03\n", encoding="utf-8")
    (root / "references" / "shots" / "ATTRIBUTION.md").write_text(
        "# x\n## 逐卡来源映射\n| 来源 | 卡片 |\n|---|---|\n| remotion-bits.dev | `blur-slide`、`card-stack` |\n", encoding="utf-8")


def test_inspiracje_ujecia_katalog_kart(tmp_path, monkeypatch, capsys):
    """Katalog kart shotcraft: kategorie po polsku, energia z chińskiego opisu, demo z karty, „tylko technika” z pola
    原片出处 i z tabeli ATTRIBUTION, nasz odpowiednik na górze; bez instalacji jasny komunikat."""
    assert [insp.energia_poziom(x) for x in ("高（瞬时）", "中高", "A 中低", "由低到高", "峰值（全）", "n/a（技法卡）", "")] == \
        [5, 4, 2, 3, 5, None, None]
    monkeypatch.setattr(insp.nz, "SHOTCRAFT", tmp_path / "brak")
    with pytest.raises(SystemExit, match="instaluj shotcraft"):
        insp.katalog_ujec()
    _shotcraft(tmp_path / "sc")
    karty = {k["nazwa"]: k for k in insp.katalog_ujec(tmp_path / "sc")}
    assert karty["crash-zoom-punch"]["kategoria"] == "kamera" and karty["crash-zoom-punch"]["u_nas"].startswith("strona.js")
    assert karty["crash-zoom-punch"]["demo"].endswith("demos/camera/crash-zoom-punch/CrashZoom.tsx")
    assert karty["paper-title-card"]["tylko_technika"] == "notion-ai.mp4 0:03"
    assert karty["paper-title-card"]["demo"].endswith("PaperTitleCard.tsx")
    assert karty["blur-slide"]["tylko_technika"] == "remotion-bits.dev" and karty["blur-slide"]["poziom"] == 2
    assert karty["crash-zoom-punch"]["tylko_technika"] is None and karty["shot-transitions"]["demo"] is None
    lista = list(karty.values())
    assert karty["paper-title-card"]["u_nas"].startswith("ujecia.js tytulPapier()")
    assert [k["nazwa"] for k in insp.wybierz_ujecia(lista, "typografia")] == ["paper-title-card", "blur-slide"]  # nasz port pierwszy
    assert [k["nazwa"] for k in insp.wybierz_ujecia(lista, energia="niska")] == ["paper-title-card", "blur-slide"]
    assert [k["nazwa"] for k in insp.wybierz_ujecia(lista, szukaj="paper")] == ["paper-title-card"]
    assert insp.wybierz_ujecia(lista)[0]["nazwa"] == "crash-zoom-punch"                      # nasz odpowiednik pierwszy
    with pytest.raises(SystemExit, match="nieznana kategoria"):
        insp.wybierz_ujecia(lista, "reklama")
    monkeypatch.setattr(insp.nz, "SHOTCRAFT", tmp_path / "sc")
    assert insp.main(["ujecia", "--kategoria", "camera"]) == 0                                # nazwa angielska też
    out = capsys.readouterr().out
    assert "## crash-zoom-punch · kamera · energia wysoka" in out and "[u nas: strona.js uderzenie()" in out
    assert insp.main(["ujecia", "--karta", "paper-title-card"]) == 0
    out = capsys.readouterr().out
    assert "[tylko technika: notion-ai.mp4 0:03]" in out and "style (podgląd w galerii): paper" in out
    with pytest.raises(SystemExit, match="nie ma karty 'paper'"):
        insp.main(["ujecia", "--karta", "paper"])


SONDA_STRONA = """<html><body style="margin:0;width:400px;height:300px;overflow:hidden">
<div style="position:absolute;inset:0;overflow:hidden">
 <div style="position:absolute;left:20px;top:20px;width:60px;height:50px;overflow:hidden;font:40px/50px sans-serif">
  <div style="transform:translateY(-150px)">""" + "".join(f"<div>{i}</div>" for i in range(10)) + """</div></div>
 <div style="position:absolute;left:330px;top:200px;font:30px sans-serif;white-space:nowrap">poza kadrem</div>
 <div style="position:absolute;left:20px;top:120px;font:30px sans-serif"><span>Chleb</span> <span>co</span> <span>rano</span></div>
 <div style="position:absolute;left:200px;top:20px;width:80px;height:60px;overflow:hidden;font:40px/40px sans-serif">
  <div style="transform:translateY(-45px)"><div>8</div><div>9</div></div></div>
</div></body></html>"""


def test_sonda_przycina_tekst_do_okna():
    """Licznik bębnowy: pasek cyfr w oknie z overflow widać tylko w oknie (jedna cyfra). Kontener na cały kadr nie
    przycina, więc tekst wychodzący poza kadr dalej się liczy."""
    sync_api = pytest.importorskip("playwright.sync_api")
    pm = load_script("profiles/jarvo-wideo/scripts/pomiar.py")
    with sync_api.sync_playwright() as p:
        przegladarka = hw.launch(p)
        strona = przegladarka.new_page(viewport={"width": 400, "height": 300})
        strona.set_content(SONDA_STRONA)
        w = strona.evaluate(pm.SONDA_JS)
        przegladarka.close()
    widac = {t["seen"]: t for t in w["teksty"]}
    assert sorted(t for t in widac if t.isdigit()) == ["3", "9"] and widac["3"]["y0"] >= 20 and widac["3"]["y1"] <= 70
    assert widac["9"]["okno"] and not widac["3"].get("okno")              # „9” przycięte trochę, „8” całkiem: niewidoczne
    assert widac["poza kadrem"]["x1"] > 400 and "Chleb co rano" in widac  # spacje między spanami zostają


# ------------------------------------------------------------------ dwa ekrany (split screen)

def test_dwa_ekrany_okna_bez_nakladania_i_w_kadrze():
    for uklad, (w, h) in (("gora-dol", (1080, 1920)), ("obok", (1920, 1080)), ("telefony", (1080, 1920)),
                          ("telefony", (1920, 1080)), ("obok", (1080, 1080))):
        (ax, ay, aw, ah), (bx, by, bw, bh) = dwa.okna(uklad, w, h)
        for x, y, sw, sh in ((ax, ay, aw, ah), (bx, by, bw, bh)):
            assert x >= 0 and y >= 0 and x + sw <= w and y + sh <= h and sw % 2 == 0 and sh % 2 == 0
        assert ax + aw < bx or ay + ah < by                    # szczelina na kreskę, okna się nie nakładają
    (ax, ay, aw, ah), (bx, by, bw, bh) = dwa.okna("gora-dol", 1080, 1920)
    assert ay + ah + 6 == by and by + bh == 1920 and aw == bw == 1080
    (ax, ay, aw, ah), _ = dwa.okna("telefony", 1080, 1920)
    assert ah / aw == pytest.approx(19.5 / 9, rel=0.01)       # ekran telefonu ma proporcje telefonu
    assert dwa.okna("przed-po", 1080, 1920) == [(0, 0, 1080, 1920)] * 2


def test_dwa_ekrany_kreska_przed_po_plynnie_miedzy_punktami():
    def wartosc(expr, t):
        py = expr.replace("if(", "IF(").replace("lt(", "LT(")
        return eval(py, {"IF": lambda c, a, b: a if c else b, "LT": lambda a, b: a < b, "t": t})  # noqa: S307
    pts = dwa.punkty_kreski(None, 10.0)                       # domyślnie: A → pół na pół → B
    assert pts[0] == (0.0, 0.0) and pts[-1] == (10.0, 1.0)
    e = dwa.wyrazenie_kreski(pts)
    assert wartosc(e, 0.5) == pytest.approx(0.0) and wartosc(e, 5.0) == pytest.approx(0.5)
    assert wartosc(e, 9.9) == pytest.approx(1.0) and wartosc(e, 50) == pytest.approx(1.0)
    vals = [wartosc(e, i / 10) for i in range(101)]
    assert all(b >= a - 1e-9 for a, b in zip(vals, vals[1:]))   # tylko w jedną stronę, bez skoków
    assert max(b - a for a, b in zip(vals, vals[1:])) < 0.07
    wlasne = dwa.punkty_kreski("4=1, 1=0.25", 6.0)             # kolejność dowolna, udział przycięty do 0–1
    assert wlasne == [(1.0, 0.25), (4.0, 1.0)]
    e = dwa.wyrazenie_kreski(wlasne)
    assert wartosc(e, 0) == pytest.approx(0.25) and wartosc(e, 2.5) == pytest.approx(0.625)
    with pytest.raises(SystemExit):
        dwa.punkty_kreski("dwa=pół", 6.0)


def test_dwa_ekrany_dzwiek_i_parametry(monkeypatch, tmp_path):
    a, b, zdj = tmp_path / "a.mp4", tmp_path / "b.mp4", tmp_path / "z.png"
    ma = {a.name: True, b.name: False}
    monkeypatch.setattr(dwa.wl, "probe", lambda p: {"audio": ma.get(p.name) and {"codec": "aac"}})
    assert dwa.zrodlo_dzwieku("auto", [a, b]) == [0] and dwa.zrodlo_dzwieku("auto", [b, a]) == [1]
    assert dwa.zrodlo_dzwieku("oba", [a, b]) == [0] and dwa.zrodlo_dzwieku("b", [a, b]) == []
    assert dwa.zrodlo_dzwieku("auto", [zdj, zdj]) == [] and dwa.zrodlo_dzwieku("brak", [a, a]) == []
    assert dwa.kadr_xy("0.2,1.7") == (0.2, 1.0) and dwa.kolor("#0e0f13", 9) == (14, 15, 19, 9)
    with pytest.raises(SystemExit):
        dwa.kolor("czerwony")
    with pytest.raises(SystemExit):
        dwa.kadr_xy("0.5")


@needs_ffmpeg
def test_dwa_ekrany_render_i_test_pauzy(tmp_path):
    pytest.importorskip("PIL")
    a, zdj = tmp_path / "a.mp4", tmp_path / "z.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=30:d=2",
                    "-f", "lavfi", "-i", "sine=d=2", "-shortest", "-pix_fmt", "yuv420p", str(a)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=200x300", "-frames:v",
                    "1", str(zdj)], check=True)
    out, st = dwa.zloz(a, zdj, tmp_path / "gd.mp4", podpisy=["A", "B"])
    p = wl.probe(out)
    assert (p["video"]["width"], p["video"]["height"]) == (1080, 1920) and p["audio"]
    assert st["uklad"] == "gora-dol" and st["dzwiek"] == "a" and st["uwagi"] == []    # A się rusza
    _, st = dwa.zloz(zdj, zdj, tmp_path / "stoi.mp4", uklad="obok", fmt="16:9", sek=2.0)
    assert st["dzwiek"] == "brak" and "test pauzy" in st["uwagi"][0]               # dwa zdjęcia: nic się nie rusza
    _, st = dwa.zloz(zdj, a, tmp_path / "pp.mp4", uklad="przed-po", sek=3.0)
    assert st["uwagi"] == []                                                         # kreska jedzie



# ------------------------------------------------------------------ lektor lokalny (Matcha PL, Paradee EN, jarvo-tts)

def _jarvo_tts():
    import importlib.machinery
    import importlib.util
    path = str(REPO / "infra" / "bin" / "jarvo-tts")
    loader = importlib.machinery.SourceFileLoader("jarvo_tts", path)
    spec = importlib.util.spec_from_loader("jarvo_tts", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_jarvo_tts_zdania_bez_ciecia_na_skrotach():
    t = _jarvo_tts()
    assert t.podziel_zdania("Shipped on Oct. 5th, Dr. Smith said it is 42% faster! Next one.\nNew line. J. R. Tolkien.") == [
        "Shipped on Oct. 5th, Dr. Smith said it is 42% faster!", "Next one.", "New line.", "J. R. Tolkien."]
    assert t.podziel_zdania("  \n\n") == []


def test_jarvo_tts_szybkosc_poza_zakresem():
    with pytest.raises(SystemExit):
        _jarvo_tts().main(["Hi.", "-o", "x.wav", "--szybkosc", "3"])


def test_lektor_lokalny_tempo_i_glosnosc():
    assert wl._speed("+10%") == pytest.approx(1.1)
    assert wl._speed("-20%") == pytest.approx(0.8)
    assert wl._speed("+300%") == 2.0 and wl._speed("bzdura") == 1.0
    assert wl._volume("-50%") == pytest.approx(0.5) and wl._volume("+0%") == 1.0
    assert "en-US-Paradee" in wl.LOCAL_VOICES
    assert wl.DEFAULT_VOICE == "pl-PL-Matcha-Meski" and {"pl-PL-Matcha-Meski", "pl-PL-Matcha-Damski"} <= set(wl.LOCAL_VOICES)
    assert set(wl.EDGE_FALLBACK.values()) == set(wl.PL_VOICES)              # zapas: Marek i Zofia z Edge
    assert wl.bez_klamer("Po {meeting}u") == "Po meetingu"


def test_czasy_slow_z_parakeeta_i_luki():
    W = wl.Word
    text = "Jarvo answers every message by 8 AM."
    heard = [W(0.3, 0.7, "Jarvo"), W(0.8, 1.2, "answers"), W(1.2, 1.5, "every"), W(1.5, 1.9, "massage"),
             W(1.9, 2.0, "by"), W(2.0, 2.2, "8"), W(2.3, 2.7, "a.m.")]
    out = wl.time_script_words(text, heard, [(0.0, 3.0, text)])
    assert [w.text for w in out] == text.split()                       # pisownia z tekstu, nie z rozpoznania
    assert (out[0].start, out[0].end) == (0.3, 0.7)
    assert (out[-1].start, out[-1].end) == (2.3, 2.7)                   # „AM.” = „a.m.” po normalizacji
    assert 1.5 <= out[3].start < out[3].end <= 1.9                      # „message” źle usłyszane: luka między sąsiadami
    assert all(a.end <= b.start + 1e-6 for a, b in zip(out, out[1:]))


def test_czasy_slow_bez_parakeeta_z_podzialu_na_zdania():
    out = wl.time_script_words("One two. Three four five.", [], [(0.0, 1.0, "One two."), (1.2, 2.4, "Three four five.")])
    assert [w.text for w in out] == ["One", "two.", "Three", "four", "five."]
    assert out[0].start == 0.0 and out[1].end == pytest.approx(1.0, abs=0.01)
    assert out[2].start == pytest.approx(1.2) and out[-1].end == pytest.approx(2.4, abs=0.01)


@needs_ffmpeg
def test_speak_many_glos_lokalny_przez_jarvo_tts(tmp_path, monkeypatch):
    """Głos en-US-Paradee idzie przez jarvo-tts (atrapa: ton zamiast mowy), bez Parakeeta czasy z podziału na zdania,
    drugi raz z cache."""
    fake = tmp_path / "jarvo-tts"
    fake_src = f"""#!{sys.executable}
import json, math, struct, sys, wave
jobs = json.load(open(sys.argv[2]))
out = []
for j in jobs:
    n = int(24000 * 1.5 / j["szybkosc"])
    with wave.open(j["wyjscie"], "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 9))) for i in range(n)))
    out.append({{"wyjscie": j["wyjscie"], "sekundy": n / 24000, "zdania": [[0.0, n / 24000, j["tekst"]]]}})
open(sys.argv[2] + ".log", "a").write("x")
open({str(tmp_path / "glosy.txt")!r}, "a").write(" ".join(j["glos"] for j in jobs) + "\\n")
print(json.dumps(out))
"""
    fake.write_text(fake_src)
    fake.chmod(0o755)
    monkeypatch.setenv("JARVO_TTS_BIN", str(fake))
    monkeypatch.setenv("JARVO_STT_BIN", str(tmp_path / "brak-stt"))
    monkeypatch.setattr(wl.shutil, "which", lambda *_a, **_k: None)
    monkeypatch.setenv("JARVO_WIDEO_CACHE", str(tmp_path / "cache"))
    items = [{"text": "Hello there friend.", "voice": "en-US-Paradee", "rate": "+50%"},
             {"text": "Second line.", "voice": "en-US-Paradee"}]
    sp = wl.speak_many(items)
    assert len(sp) == 2 and sp[0].audio.suffix == ".mp3"
    assert sp[0].duration == pytest.approx(1.0, abs=0.1) and sp[1].duration == pytest.approx(1.5, abs=0.1)
    assert [w.text for w in sp[0].words] == ["Hello", "there", "friend."]
    assert json.loads(sp[0].audio.with_suffix(".json").read_text(encoding="utf-8"))["czasy"] == "zdania"
    assert (tmp_path / "glosy.txt").read_text() == "en-US-Paradee en-US-Paradee\n"      # głos idzie do jarvo-tts
    fake.unlink()                                                       # drugi raz: cache, bez jarvo-tts
    assert [s.audio for s in wl.speak_many(items)] == [s.audio for s in sp]
    # domyślny głos (bez „voice”) to polski Matcha, też przez jarvo-tts; {klamry} nie trafiają do słów napisów
    fake.write_text(fake_src)
    fake.chmod(0o755)
    sp = wl.speak_many([{"text": "Dzięki za {feedback} dziś."}])
    assert (tmp_path / "glosy.txt").read_text().splitlines()[-1] == "pl-PL-Matcha-Meski"
    assert [w.text for w in sp[0].words] == ["Dzięki", "za", "feedback", "dziś."]


def test_lektor_matcha_bez_jarvo_tts_zapas_edge(tmp_path, monkeypatch):
    """Polski lektor lokalny bez jarvo-tts (poza obrazem) → zapas Edge TTS (Marek/Zofia) z ostrzeżeniem, w cache
    pod głosem Edge; tekst do Edge bez {klamer}. Angielski Paradee nie ma zapasu: błąd zostaje."""
    monkeypatch.setenv("JARVO_TTS_BIN", str(tmp_path / "brak-tts"))
    monkeypatch.setattr(wl.shutil, "which", lambda *_a, **_k: None)
    monkeypatch.setenv("JARVO_WIDEO_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(wl, "_import_edge_tts", lambda: object())
    monkeypatch.setattr(wl, "_ssl_bundle", lambda: None)
    wolane = []

    async def synth(_edge, text, voice, rate, volume, pitch, out):
        wolane.append((text, voice))
        out.write_bytes(b"mp3")
        return [wl.Word(0.0, 0.5, w) for w in text.split()]
    monkeypatch.setattr(wl, "_synth", synth)
    monkeypatch.setattr(wl, "duration", lambda _p: 1.0)
    sp = wl.speak_many([{"text": "Raport {PDF} dziś.", "voice": "pl-PL-Matcha-Damski"}, {"text": "Cześć."}])
    assert sorted(wolane) == [("Cześć.", "pl-PL-MarekNeural"), ("Raport PDF dziś.", "pl-PL-ZofiaNeural")]
    assert len(sp) == 2 and json.loads(sp[0].audio.with_suffix(".json").read_text())["voice"] == "pl-PL-ZofiaNeural"
    with pytest.raises(SystemExit):
        wl.speak_many([{"text": "Hello.", "voice": "en-US-Paradee"}])


def test_glos_lokalny_w_edytorze_hq():
    import importlib
    sys.path.insert(0, str(REPO / "hq" / "plugin"))
    ed = importlib.import_module("edytor")
    assert "en-US-Paradee" in ed.GLOSY and set(ed.GLOSY_LOKALNE) <= set(ed.GLOSY)
    assert ed.GLOSY[0] == wl.DEFAULT_VOICE == "pl-PL-Matcha-Meski"              # domyślny lektor HQ = Wideografa
    assert {"pl-PL-Matcha-Meski", "pl-PL-Matcha-Damski"} <= set(ed.GLOSY_LOKALNE)
    js = (REPO / "hq" / "web" / "src" / "44-audio.js").read_text(encoding="utf-8")
    lista = re.search(r"const AUDIO_GLOSY = \[(.*?)\];", js, re.S).group(1)
    assert sorted(re.findall(r'\["([\w-]+)",', lista)) == sorted(ed.GLOSY)
