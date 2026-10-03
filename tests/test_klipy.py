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
    proj["texts"][0]["text"] = "Poprawione w HQ"                                        # człowiek edytował rolkę
    pp.write_text(json.dumps(proj), encoding="utf-8")
    with pytest.raises(SystemExit, match="zmieniono po zbudowaniu"):
        K.main(["zbuduj", str(pl), "-o", str(out), "--bez-renderu"])
    assert "Poprawione w HQ" in pp.read_text(encoding="utf-8")
    assert K.main(["zbuduj", str(pl), "-o", str(out), "--bez-renderu", "--nadpisz"]) == 0
