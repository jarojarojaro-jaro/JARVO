"""Clipmaker Wideografa (klipy.py): plan.json → projekty edytora HQ z kadrem, cięciem pauz i napisami karaoke."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import load_script

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-wideo" / "scripts"))
K = load_script("profiles/jarvo-wideo/scripts/klipy.py")
ed = K.ed

# „nagranie”: dwa zdania, w środku pierwszego pauza 1,2 s i „yyy”
WORDS = [[1.0, 1.3, "Trzy"], [1.35, 1.7, "błędy"], [1.75, 2.0, "yyy"], [3.2, 3.5, "w"], [3.55, 4.0, "cenach."],
         [10.0, 10.3, "No"], [10.35, 10.5, "i"], [10.55, 11.0, "dalej."], [20.0, 20.5, "Koniec."]]


@pytest.fixture()
def nagranie(tmp_path, monkeypatch):
    src = tmp_path / "podcast.mp4"
    src.write_bytes(b"\0")
    ed.speech_path(src).write_text(json.dumps(ed.speech_data(WORDS, [[2.0, 3.2]], 60.0)), encoding="utf-8")
    monkeypatch.setattr(ed, "probe", lambda p: {"ok": True, "duration": 60.0, "w": 1920, "h": 1080, "fps": 30,
                                                 "audio": True, "video": True})
    return src


def plan(src, **rolka):
    r = {"slug": "trzy-bledy", "tytul": "3 błędy w cenach", "segmenty": [{"od": 0.9, "do": 12.0, "fx": 0.3}],
         "oceny": {"hook": 8, "samodzielnosc": 9}, "dlaczego": "konkret", **rolka}
    return {"zrodlo": str(src), "rolki": [r]}


def test_fragments_cut_long_pauses_and_fillers():
    frag = K.fragmenty(0.9, 12.0, WORDS, 0.6, True)
    # pauza 2.0→3.2 (z „yyy” wyciętym) dzieli segment; oddech zostaje; koniec = ostatnie słowo + zapas
    assert frag[0] == (0.92, 1.76) and frag[1][0] == pytest.approx(3.14) and frag[-1][1] == pytest.approx(11.25)
    assert K.fragmenty(0.9, 12.0, WORDS, None, True) == [(0.9, 12.0)]     # bez cięcia pauz: cały segment


def test_plan_check_errors_and_warnings(nagranie):
    bledy, uwagi, _ = K.sprawdz_plan(K.wczytaj_plan_dict(plan(nagranie)))
    assert bledy == [] and not any("tnie" in u for u in uwagi)
    zly = plan(nagranie, slug="Zły Slug", segmenty=[{"od": 50, "do": 80, "zoom": 9}], format="4:3")
    bledy, _, _ = K.sprawdz_plan(K.wczytaj_plan_dict(zly))
    assert any("slug" in b for b in bledy) and any("format" in b for b in bledy) and any("poza nagraniem" in b for b in bledy)
    hook = plan(nagranie, segmenty=[{"od": 9.9, "do": 21.0}], oceny={"hook": 5, "wartosc": 6})
    _, uwagi, _ = K.sprawdz_plan(K.wczytaj_plan_dict(hook))
    assert any("zaczyna się od „no i" in u for u in uwagi) and any("oceny poniżej progu" in u for u in uwagi)
    tnie = plan(nagranie, segmenty=[{"od": 1.5, "do": 12.0}])
    _, uwagi, _ = K.sprawdz_plan(K.wczytaj_plan_dict(tnie))
    assert any("tnie słowo „błędy”" in u and "dosunie granicę do przerwy, 1.32 s" in u for u in uwagi)
    echo = plan(nagranie, tytul="Trzy błędy w cenach")                  # tytuł = pierwsze zdanie mówione
    _, uwagi, _ = K.sprawdz_plan(K.wczytaj_plan_dict(echo))
    assert any("tytuł powtarza pierwsze zdanie" in u for u in uwagi)
    _, uwagi, _ = K.sprawdz_plan(K.wczytaj_plan_dict(plan(nagranie, tytul="Tracisz marżę?")))
    assert not any("tytuł powtarza" in u for u in uwagi)


def test_boundary_inside_word_moves_to_gap():
    # środek słowa po stronie segmentu → słowo zostaje; zapas = połowa przerwy, najwyżej LEAD / TAIL
    assert K.dosun(1.5, WORDS, False, 60) == 1.325          # „błędy” 1.35–1.70: większość w segmencie → od jego startu
    assert K.dosun(1.6, WORDS, False, 60) == 1.725          # większość przed granicą → słowo odpada, start przy „yyy”
    assert K.dosun(3.8, WORDS, True, 60) == 4.45            # „cenach.” zostaje, po nim 6 s ciszy → TAIL 0,45
    assert K.dosun(3.6, WORDS, True, 60) == 3.525           # „cenach.” odpada → koniec po „w”, w połowie przerwy
    assert K.dosun(5.0, WORDS, True, 60) == 5.0             # granica w ciszy zostaje
    assert K.granice(1.5, 1.6, WORDS) == (1.325, 1.725)      # całe słowo zamiast jego środka
    assert K.granice(1.6, 1.65, WORDS) == (1.6, 1.65)        # dosunięcie zjadłoby segment → bez zmian


def test_reels_sharing_material_and_one_half_only(nagranie, monkeypatch):
    dwa = plan(nagranie)
    dwa["rolki"].append({**dwa["rolki"][0], "slug": "znowu", "segmenty": [{"od": 1.0, "do": 11.0}]})
    dwa["rolki"].append({**dwa["rolki"][0], "slug": "inna", "segmenty": [{"od": 12.0, "do": 21.0}]})
    _, uwagi, _ = K.sprawdz_plan(K.wczytaj_plan_dict(dwa))
    assert [u for u in uwagi if "dzielą" in u] == [u for u in uwagi if u.startswith("rolki 1 i 2 dzielą 100%")]
    assert len([u for u in uwagi if "dzielą" in u]) == 1 and not any("połowy" in u for u in uwagi)   # 60 s: za krótkie
    monkeypatch.setattr(ed, "probe", lambda p: {"ok": True, "duration": 1200.0, "video": True, "audio": True})
    _, uwagi, _ = K.sprawdz_plan(K.wczytaj_plan_dict(dwa))
    assert any("wszystkie rolki z pierwszej połowy" in u for u in uwagi)


def test_windows_cover_recording_at_sentence_boundaries():
    zd = [{"od": float(t), "do": t + 8.0, "tekst": "x"} for t in range(0, 300, 10)]
    ok = K.okna(zd)
    assert [o["od"] for o in ok] == [0.0, 90.0, 180.0, 270.0] and ok[-1]["do"] == 298.0
    assert all(a["do"] < b["od"] for a, b in zip(ok, ok[1:])) and sum(o["zdan"] for o in ok) == len(zd)


def test_project_is_editable_reel(nagranie):
    p = K.wczytaj_plan_dict(plan(nagranie))
    proj = K.projekt_rolki(p, p["rolki"][0], nagranie, WORDS, {})
    assert proj["format"] == "9:16" and proj["canvas"] == {"w": 1080, "h": 1920, "fps": 30}
    clips = proj["clips"]
    assert all(c["fit"] == "cover" and c["fx"] == 0.3 for c in clips)
    assert clips[0]["zoom"] == 1.0 and clips[1]["zoom"] == pytest.approx(K.PUNCH)       # punch-in na cięciu
    caps = [t for t in proj["texts"] if t.get("cap")]
    assert caps and all(t["hl"] == K.HL and t["words"] for t in caps)                   # karaoke
    assert "yyy" not in " ".join(t["text"] for t in caps)                              # wtrącenie wycięte
    tytul = [t for t in proj["texts"] if not t.get("cap")]
    assert tytul[0]["text"] == "3 błędy w cenach" and tytul[0]["end"] == 3.0
    ed.normalize(proj, lambda s: Path(s) if Path(s).exists() else None)                # przejdzie eksport z edytora
    assert proj["clipmaker"]["granice"] == [[0.9, 12.0]]                                # granice w ciszy: bez zmian
    tnie = K.wczytaj_plan_dict(plan(nagranie, segmenty=[{"od": 1.5, "do": 10.4}]))     # w „błędy” i w „i”
    pt = K.projekt_rolki(tnie, tnie["rolki"][0], nagranie, WORDS, {"duration": 60.0})
    assert pt["clipmaker"]["granice"] == [[1.325, 10.325]] and pt["clipmaker"]["segmenty"][0]["od"] == 1.5
    assert pt["clips"][0]["in"] == 1.325 and pt["clips"][-1]["out"] <= 10.325
    p16 = K.wczytaj_plan_dict({**plan(nagranie), "format": "16:9", "styl": {"napisy": None, "tytul": False, "punch": False}})
    proj16 = K.projekt_rolki(p16, p16["rolki"][0], nagranie, WORDS, {})
    assert proj16["canvas"]["w"] == 1920 and proj16["texts"] == [] and {c["zoom"] for c in proj16["clips"]} == {1.0}


def test_build_writes_projects_and_klipy_md(nagranie, tmp_path, capsys):
    pl = tmp_path / "plan.json"
    pl.write_text(json.dumps(plan(nagranie, opis="Opis", hashtagi=["#ceny"], taktyka="liczba na start")), encoding="utf-8")
    out = tmp_path / "klipy"
    assert K.main(["zbuduj", str(pl), "-o", str(out), "--bez-renderu"]) == 0
    proj = json.loads((out / "klip-1-trzy-bledy.edycja.json").read_text(encoding="utf-8"))
    assert proj["zmienil"]["kto"] == "jarvo-wideo" and proj["clipmaker"]["slug"] == "trzy-bledy"
    md = (out / "KLIPY.md").read_text(encoding="utf-8")
    assert "3 błędy w cenach" in md and "00:00.9–00:12.0" in md and "#ceny" in md and "liczba na start" in md
    bad = tmp_path / "zly.json"
    bad.write_text(json.dumps(plan(nagranie, segmenty=[{"od": 5, "do": 4}])), encoding="utf-8")
    with pytest.raises(SystemExit, match="plan ma błędy"):
        K.main(["zbuduj", str(bad), "-o", str(out), "--bez-renderu"])


def test_sentences_for_reading():
    zd = K.zdania(WORDS)          # pauza 1,2 s (> 1 s) dzieli zdanie: przy czytaniu widać, gdzie mówca się zawahał
    assert zd[0] == {"od": 1.0, "do": 2.0, "tekst": "Trzy błędy (yyy)"}
    assert [z["tekst"] for z in zd[1:]] == ["w cenach.", "No i dalej.", "Koniec."]
    assert [z["tekst"] for z in K.zdania(WORDS, max_gap=2.0)][0] == "Trzy błędy (yyy) w cenach."


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_real_prepare_without_speech_model(tmp_path, monkeypatch):
    """przygotuj na prawdziwym pliku: cięcia ujęć i arkusz klatek (mowa z atrapy jarvo-stt)."""
    src = tmp_path / "rozmowa.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=12",
                    "-f", "lavfi", "-i", "sine=d=12", "-shortest", "-pix_fmt", "yuv420p", str(src)], check=True)
    stt = tmp_path / "stt"
    stt.write_text('#!/usr/bin/env bash\necho \'{"words": [[0.5, 1.0, "Cześć."], [2.0, 2.4, "Test."]]}\' > "$3"\n')
    stt.chmod(0o755)
    monkeypatch.setenv("JARVO_STT_BIN", str(stt))
    out = tmp_path / "klipy"
    assert K.main(["przygotuj", str(src), "-o", str(out)]) == 0
    a = json.loads((out / "analiza.json").read_text(encoding="utf-8"))
    assert a["slowa"] == 2 and a["arkusze"] and Path(a["arkusze"][0]["plik"]).is_file()
    tr = (out / "transkrypcja.txt").read_text(encoding="utf-8")
    assert "[00:00.5–00:01.0] Cześć." in tr and "## Okno 1 [00:00.5–00:02.4]" in tr and a["okna"][0]["zdan"] == 2


def test_rebuild_does_not_overwrite_user_edit(nagranie, tmp_path):
    pl = tmp_path / "plan.json"
    pl.write_text(json.dumps(plan(nagranie)), encoding="utf-8")
    out = tmp_path / "klipy"
    assert K.main(["zbuduj", str(pl), "-o", str(out), "--bez-renderu"]) == 0
    assert K.main(["zbuduj", str(pl), "-o", str(out), "--bez-renderu"]) == 0       # bez zmian człowieka: wolno
    pp = out / "klip-1-trzy-bledy.edycja.json"
    proj = json.loads(pp.read_text(encoding="utf-8"))
    for c in proj["clips"]:                                  # samo otwarcie w HQ: edytor zapisuje 1.0 jako 1
        c["zoom"] = int(c["zoom"]) if c["zoom"] == int(c["zoom"]) else c["zoom"]
    proj["notes"] = []
    pp.write_text(json.dumps(proj), encoding="utf-8")
    assert not K.edytowana_recznie(out / "klip-1-trzy-bledy.mp4")
    stary = {**proj, "clipmaker": {**proj["clipmaker"], "podpis": K.podpis(proj, kanon=False)}}
    pp.write_text(json.dumps(stary), encoding="utf-8")                                 # podpis sprzed sprowadzenia liczb
    assert not K.edytowana_recznie(out / "klip-1-trzy-bledy.mp4")
    proj["texts"][0]["text"] = "Poprawione w HQ"                                        # człowiek edytował rolkę
    pp.write_text(json.dumps(proj), encoding="utf-8")
    with pytest.raises(SystemExit, match="zmieniono po zbudowaniu"):
        K.main(["zbuduj", str(pl), "-o", str(out), "--bez-renderu"])
    assert "Poprawione w HQ" in pp.read_text(encoding="utf-8")
    assert K.main(["zbuduj", str(pl), "-o", str(out), "--bez-renderu", "--nadpisz"]) == 0


def twarz(x, y=0.4, s=0.1):
    """Twarz jak z twarze.py: ramka 0–1 wokół środka (x, y), bok s, pewność, 10 liczb punktów twarzy."""
    return [x - s / 2, y - s / 2, x + s / 2, y + s / 2, 0.9] + [x, y] * 5


def test_tracker_holds_face_and_switches_after_three_samples():
    a, b = twarz(0.3, s=0.12), twarz(0.7, s=0.1)
    probki = [[0.0, [a, b]], [0.5, [a]], [1.0, []],                         # bez twarzy: trzyma poprzednią
              [1.5, [twarz(0.3, s=0.1), twarz(0.7, s=0.14)]],              # większa obca twarz tylko raz: bonus ×3 trzyma
              [2.0, [b]], [2.5, [b]], [3.0, [b]], [3.5, [b]]]              # trzy próbki z rzędu → zmiana od pierwszej
    slad = K.sledz(probki)
    xs = [None if f is None else round((f[0] + f[2]) / 2, 2) for _, f, _ in slad]
    assert xs == [0.3, 0.3, 0.3, 0.3, 0.7, 0.7, 0.7, 0.7] and [n for *_, n in slad] == [0, 0, 0, 0, 1, 1, 1, 1]
    skok = K.sledz([[t / 2, [twarz(0.3 if t < 3 else 0.5)]] for t in range(6)])      # ta sama osoba po skoku kadru
    assert [n for *_, n in skok] == [0, 0, 0, 1, 1, 1]


def test_frame_settings_ignore_small_moves_and_confirm_big_ones():
    szer = 0.316                                      # kadr 9:16 z 16:9: 0,316 szerokości źródła; próg 0,11
    slad = [(t / 2, twarz(x, s=0.3), 0) for t, x in enumerate([0.30, 0.33, 0.28, 0.45, 0.46, 0.31,  # 2 daleko: nic
                                                             0.31, 0.50, 0.52, 0.51, 0.50])]      # 3+: nowe od 3.5
    ust = K.ustawienia(slad, szer)
    assert [u["od"] for u in ust] == [0.0, 3.5]
    assert ust[0]["x"] == pytest.approx(0.31, abs=0.011) and ust[1]["x"] == pytest.approx(0.51, abs=0.011)
    assert K.ustawienia([(0.0, None, 0), (0.5, None, 0)], szer) == []
    inna = K.ustawienia([(0.0, twarz(0.3), 0), (0.5, twarz(0.31), 0), (1.0, twarz(0.7), 1)], szer)
    assert [u["od"] for u in inna] == [0.0, 1.0]                                            # inna twarz: od razu


def test_focus_from_face_and_split_in_word_gap():
    assert K.ogniskowa(0.691, 0.3, 1080, 1920, 1.0, 1920, 1080) == (0.779, 0.5)   # 16:9 → 9:16: wysokość cała
    assert K.ogniskowa(0.5, 0.5, 1080, 1920, 1.0, 1920, 1080)[0] == 0.5
    fx, fy = K.ogniskowa(0.691, 0.36, 1080, 1920, 1.12, 1920, 1080)                # punch-in: fy już działa
    assert 0.76 < fx < 0.78 and 0.1 < fy < 0.3
    assert K.ogniskowa(0.9, 0.9, 1080, 1920, 1.0, 1080, 1920) == (0.5, 0.5)         # te same proporcje: bez przesunięcia
    ust = [{"od": 0.0, "x": 0.3, "y": 0.4}, {"od": 5.4, "x": 0.7, "y": 0.4}]
    words = [[4.0, 4.9, "a"], [5.3, 6.0, "b"]]
    czesci = K.podziel(0.0, 10.0, ust, words)
    assert [(a, b) for a, b, _ in czesci] == [(0.0, 5.1), (5.1, 10.0)] and czesci[1][2]["x"] == 0.7
    assert K.podziel(0.0, 5.9, ust, words) == [(0.0, 5.9, ust[0])]                   # część < 0,8 s: bez podziału
    assert K.podziel(1.0, 2.0, [], words) == [(1.0, 2.0, None)]


def test_reel_frames_speaker_face_when_plan_has_no_focus(nagranie):
    p = K.wczytaj_plan_dict(plan(nagranie, segmenty=[{"od": 0.9, "do": 12.0}]))
    tw = {"w": 1920, "h": 1080, "co": 0.5,
          "probki": [[t / 2, [twarz(0.3 if t < 12 else 0.7)]] for t in range(2, 25)]}   # od 6 s inna osoba
    proj = K.projekt_rolki(p, p["rolki"][0], nagranie, WORDS, {"w": 1920, "h": 1080, "duration": 60.0}, tw)
    assert proj["clipmaker"]["kadr"] == ["twarz"]
    fx = [c["fx"] for c in proj["clips"]]
    assert fx[0] == K.ogniskowa(0.3, 0.4, 1080, 1920, 1.0, 1920, 1080)[0] and fx[-1] > 0.75 and fx[0] < 0.25
    bez = K.projekt_rolki(p, p["rolki"][0], nagranie, WORDS, {"w": 1920, "h": 1080}, None)
    assert bez["clipmaker"]["kadr"] == ["srodek"] and {c["fx"] for c in bez["clips"]} == {0.5}
    info = {"w": 1920, "h": 1080, "video": True, "duration": 60.0}
    assert K.odcinki_twarzy(p, WORDS, info) == [(0.9, 12.0)]
    assert K.odcinki_twarzy(K.wczytaj_plan_dict(plan(nagranie)), WORDS, info) == []          # fx w planie
    assert K.odcinki_twarzy(p, WORDS, {**info, "w": 1080, "h": 1920}) == []                  # pion z pionu


def test_gain_to_target_loudness_with_peak_headroom():
    assert K.wzmocnienie(-14.5, -6.0) == 1.0                     # w granicach ±1 dB: bez zmian
    assert K.wzmocnienie(-20.0, -10.0) == pytest.approx(10 ** (6 / 20), abs=0.002)
    assert K.wzmocnienie(-26.0, -12.0) == 2.0                    # najwyżej ×2 (jak suwak w edytorze)
    assert K.wzmocnienie(-20.0, -4.0) == pytest.approx(10 ** (2.5 / 20), abs=0.002)   # szczyt najwyżej −1,5 dBFS
    assert K.wzmocnienie(-8.0, -0.5) == pytest.approx(10 ** (-6 / 20), abs=0.002)     # za głośno: ciszej


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_source_loudness_of_reel_segments(tmp_path):
    src = tmp_path / "glos.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:d=12", "-f", "lavfi",
                    "-i", "anoisesrc=c=pink:d=12,volume='if(lt(t,6),0.05,0.2)':eval=frame", "-shortest",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    cicha, glosna = K.glosnosc_zrodla(src, [(0.5, 5.5)]), K.glosnosc_zrodla(src, [(6.5, 11.5)])
    assert glosna[0] - cicha[0] == pytest.approx(12.0, abs=1.0)              # 0,05 → 0,2 = +12 dB
    oba = K.glosnosc_zrodla(src, [(0.5, 5.5), (6.5, 11.5)])
    assert cicha[0] < oba[0] < glosna[0] and oba[1] >= glosna[1] - 0.5
