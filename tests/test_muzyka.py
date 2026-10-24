"""muzyka.py (muzyka pod obraz z mgaudio, mg-styles-15) i dodatek mgaudio w narzedzia.py: decyzje planu bez
biblioteki (efekty z cues.json, kulminacja, koniec, przepis ze stylu), naprawa indeksu sampli i dokładanie sampli
do klonu wzorów. Sam render mgaudio sprawdzamy w kontenerze (venv dodatku), nie tutaj."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO, load_script

mz = load_script("profiles/jarvo-wideo/scripts/muzyka.py")
nz = mz.nz
WIDEO = REPO / "profiles" / "jarvo-wideo"


def plan_args(**kw):
    base = dict(styl=None, przepis=None, opcje=None, kulminacja=None, koniec=None, tempo=None)
    return argparse.Namespace(**{**base, **kw})


def test_efekty_z_cues_jak_w_sound_mjs_i_wlasne_mgaudio():
    """t z sound.mjs to początek dźwięku: whoosh przelatuje w połowie, narastanie kończy się uderzeniem;
    wpis „mg” podaje chwilę synchronizacji wprost. vol 0,5 = poziom efektu mgaudio, skala w dB od −12 do +4."""
    zs = [mz.zdarzenie(c) for c in [
        {"sfx": "whoosh", "t": 3.6, "dur": 0.5}, {"sfx": "riser", "t": 4.8}, {"sfx": "pop", "t": 1, "vol": 0.25},
        {"t": 2.0}, {"mg": "impact", "t": 6.2, "opcje": {"kind": "cinematic"}, "vol": 2},
        {"sfx": "nieznany", "t": 1, "vol": 0}, {"mg": "drums.gong", "t": 7}]]
    assert (zs[0]["chwila"], zs[0]["rola"], zs[0]["funkcja"]) == (3.85, "ruch", "whoosh")
    assert (zs[1]["chwila"], zs[1]["rola"]) == (6.0, "narastanie")             # riser 1,2 s: koniec = uderzenie
    assert (zs[2]["chwila"], zs[2]["db"], zs[2]["rola"]) == (1.0, -6.02, "pojawienie")
    assert zs[3]["nazwa"] == "pop" and zs[3]["db"] == 0.0                     # bez sfx = pop, jak sound.mjs
    assert zs[4]["zrodlo"] == "mg" and zs[4]["chwila"] == 6.2 and zs[4]["db"] == 4.0
    assert zs[4]["opcje"] == {"kind": "cinematic"} and zs[4]["rola"] == "uderzenie"
    assert zs[5]["nazwa"] == "pop" and zs[5]["db"] == -12.0
    assert zs[6]["funkcja"] == "drums.gong" and zs[6]["rola"] == "inne"


def test_kulminacja_i_koniec_z_osi_filmu():
    """Kulminacja: najgłośniejsze uderzenie albo koniec narastania w 20–80% filmu, remis bliżej 62%;
    koniec: ostatni błysk od 60% filmu, po kulminacji i nie w ostatnich 0,3 s."""
    zd = [mz.zdarzenie(c) for c in [
        {"sfx": "thump", "t": 1.0, "vol": 1.0},                # w pierwszych 20%: nie kulminacja
        {"sfx": "crack", "t": 5.0, "vol": 0.5}, {"sfx": "thump", "t": 6.0, "vol": 0.5},
        {"sfx": "chime", "t": 8.4}, {"sfx": "chime", "t": 9.8}]]
    assert mz.kulminacja_z_cues(zd, 10)["chwila"] == 6.0       # remis: bliżej 6,2 s
    zd.append(mz.zdarzenie({"sfx": "crack", "t": 3.0, "vol": 0.8}))
    assert mz.kulminacja_z_cues(zd, 10)["chwila"] == 3.0       # głośniejsze wygrywa z bliższym
    assert mz.koniec_z_cues(zd, 10, 6.0)["chwila"] == 8.4      # 9,8 s za blisko końca
    assert mz.koniec_z_cues(zd, 10, 8.2) is None               # błysk tuż po kulminacji to jej część
    assert mz.kulminacja_z_cues([mz.zdarzenie({"sfx": "pop", "t": 5})], 10) is None


def test_plan_muzyki_ze_stylu_przepisu_i_flag():
    zd = [mz.zdarzenie(c) for c in [{"sfx": "pop", "t": 1.0}, {"sfx": "pop", "t": 1.02}, {"sfx": "thump", "t": 6.0},
                                    {"sfx": "chime", "t": 8.4}]]
    p = mz.plan_muzyki(plan_args(styl="hud"), 10, zd)
    assert (p["przepis"], p["wzor"], p["kulminacja"], p["koniec"]) == ("darksynth", "22-hud", 6.0, 8.4)
    assert "cues.json" in p["zrodla"]["kulminacja"] and "cues.json" in p["zrodla"]["koniec"]
    assert p["trafienia"] == [1.0, 6.0, 8.4]                     # dwa popy w jednej klatce: raz
    p = mz.plan_muzyki(plan_args(przepis="lofi", kulminacja=4.0, tempo=90, opcje='{"keys": "rhodes"}'), 10, zd)
    assert (p["przepis"], p["opcje"], p["kulminacja"], p["trafienia"]) == ("lofi", {"keys": "rhodes"}, 4.0, [])
    assert p["zrodla"]["kulminacja"] == "--kulminacja"
    p = mz.plan_muzyki(plan_args(), 12, [])
    assert p["przepis"] == "explainer" and p["kulminacja"] is None and p["zrodla"]["kulminacja"].startswith("przepis")
    for zle in (dict(kulminacja=6, koniec=5), dict(kulminacja=12), dict(koniec=10), dict(styl="nie-ma"),
                dict(przepis="polka")):
        with pytest.raises(SystemExit):
            mz.plan_muzyki(plan_args(**zle), 10, [])


def test_tlok_i_uwagi_po_polsku():
    zd = [mz.zdarzenie({"sfx": s, "t": 2.0 + i * 0.005}) for i, s in enumerate(["pop", "click", "tick", "drip"])]
    assert len(mz.tlok(zd)) == 1 and "4 efekty" in mz.tlok(zd)[0]
    assert mz.tlok(zd[:3]) == []
    assert mz.uwaga_pl("silence gap 0.80s").startswith("cisza 0.80 s")
    assert mz.uwaga_pl("true peak -0.5 dBTP > -1").startswith("szczyt prawdziwy -0.5 dBTP")
    assert mz.uwaga_pl("phase problem (L/R correlation -0.2)").startswith("faza: korelacja L/P -0.2")
    assert mz.uwaga_pl("coś nowego") == "coś nowego"


def test_style_i_efekty_zgodne_ze_skillami():
    """Każdy styl skilla style-motion ma przepis (i odwrotnie), a nazwy efektów to te z sound.mjs w lektor-i-dzwiek."""
    karty = {p.stem for p in (WIDEO / "skills/wideo/style-motion/references").glob("*.md")}
    assert set(mz.STYLE) == karty
    assert {p for _w, przepis, alt in mz.STYLE.values() for p in (przepis, alt) if p} <= set(mz.PRZEPISY)
    assert len(mz.PRZEPISY) == 15
    skill = (WIDEO / "skills/wideo/lektor-i-dzwiek/SKILL.md").read_text(encoding="utf-8")
    lista = re.search(r"dźwięki: (pop, whoosh[^(]+?) \(\+", skill).group(1)
    assert set(re.split(r",\s*", lista.strip())) == set(mz.SOUND_MJS)
    assert set(mz.SOUND_MJS) <= set(mz.ROLA)


def test_indeks_sampli_bez_brakujacych_plikow(tmp_path):
    """Indeks mgaudio wymienia pliki, których repo nie ma (598 wpisów, 102 pliki): zostają tylko istniejące."""
    kat = tmp_path / "samples"
    (kat / "piano").mkdir(parents=True)
    (kat / "piano" / "a.flac").write_bytes(b"x")
    indeks = {"piano": [{"file": "piano/a.flac"}, {"file": "piano/b.flac"}], "gong": [{"file": "gong/g.flac"}]}
    (kat / "index.json").write_text(json.dumps(indeks), encoding="utf-8")
    assert not nz.indeks_sampli_zgodny(kat)
    assert nz.napraw_indeks_sampli(kat) == 2
    assert json.loads((kat / "index.json").read_text(encoding="utf-8")) == {"piano": [{"file": "piano/a.flac"}]}
    assert nz.indeks_sampli_zgodny(kat) and nz.napraw_indeks_sampli(kat) == 0
    assert nz.napraw_indeks_sampli(tmp_path / "brak") == 0 and not nz.indeks_sampli_zgodny(tmp_path / "brak")


def test_dodatek_mgaudio_doklada_sample_do_klonu_wzorow(tmp_path, monkeypatch):
    """`instaluj mg` zostawia sample poza klonem; `instaluj mgaudio` dokłada je (wpis sparse-checkout), naprawia
    indeks i stawia venv; kolejne `instaluj mg` na tym samym commicie ich nie zabiera."""
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    up = tmp_path / "up"
    up.mkdir()

    def git(*a, cwd=up):
        return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8",
                              env={**__import__("os").environ, **env}).stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "uploadpack.allowFilter", "true")
    git("config", "uploadpack.allowAnySHA1InWant", "true")
    pliki = {"prompts/a.md": "styl", "lib/audio/mgaudio/__init__.py": "", "videos/a.mp4": "film",
             "lib/audio/samples/piano/a.flac": "x",
             "lib/audio/samples/index.json": json.dumps({"piano": [{"file": "piano/a.flac"}],
                                                         "kalimba": [{"file": "kalimba/k.flac"}]})}
    for rel, tresc in pliki.items():
        (up / rel).parent.mkdir(parents=True, exist_ok=True)
        (up / rel).write_text(tresc, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "c")
    rev = git("rev-parse", "HEAD")
    mg = tmp_path / "mg"
    monkeypatch.setattr(nz, "MGSTYLES_REPO", f"file://{up}")
    monkeypatch.setattr(nz, "MGSTYLES_REV", rev)
    monkeypatch.setattr(nz, "MGSTYLES", mg)
    venv = []
    monkeypatch.setattr(nz, "ensure_venv", lambda pkgs, v=nz.VENV: venv.append((pkgs, v)))
    nz.clone_pinned(nz.MGSTYLES_REPO, rev, mg, nz.MGSTYLES_POMIN, keep=nz.MG_DODANE)       # jak `instaluj mg`
    assert (mg / "lib/audio/mgaudio/__init__.py").exists() and not (mg / "lib/audio/samples").exists()
    assert not (mg / "videos/a.mp4").exists()
    nz.install_mgaudio()
    assert (mg / "lib/audio/samples/piano/a.flac").exists() and nz.indeks_sampli_zgodny()
    assert venv == [(nz.MGAUDIO_PY, nz.MGAUDIO_VENV)]
    nz.clone_pinned(nz.MGSTYLES_REPO, rev, mg, nz.MGSTYLES_POMIN, keep=nz.MG_DODANE)
    assert (mg / "lib/audio/samples/piano/a.flac").exists() and not (mg / "videos/a.mp4").exists()
    mga = nz.env_for("mgaudio")
    assert mga["MGAUDIO"] == str(mg / "lib" / "audio") and mga["MGAUDIO_PY"] == str(nz.venv_python(nz.MGAUDIO_VENV))
    assert Path(mga["MGAUDIO_PY"]).parent.parent.name == "venv-mgaudio"
    assert not nz.mgaudio_gotowe()                              # bez venv dodatku jeszcze niegotowe


def test_pin_paczki_sprawdza_wersje_i_dodatek_z_env(monkeypatch):
    py = Path(sys.executable)
    assert nz.py_ma(py, f"pytest=={pytest.__version__}") and not nz.py_ma(py, "pytest==0.0.1")
    assert nz.py_ma(py, "json") and not nz.py_ma(py, "nie_ma_takiej_paczki")
    monkeypatch.setenv("JARVO_EXTRAS", "lemo,mgaudio")
    assert nz.dodatek("mgaudio") and nz.full_extras() and not nz.dodatek("office")
    assert {"numba==0.66.0", "pedalboard==0.9.25"} <= set(nz.MGAUDIO_PY)    # wersje jak requirements.txt wzorów


def test_lektor_odcinki_mowy_krzywa_sciszenia_i_proporcje():
    # 10 ms: 0,3 s ciszy, mowa 1 s z oddechem 0,3 s w środku, pauza akapitu 1 s, mowa 0,5 s, trzask 30 ms
    env = [-90.0] * 30 + [-20.0] * 40 + [-80.0] * 30 + [-22.0] * 30 + [-90.0] * 100 + [-18.0] * 50 + [-90.0] * 50 \
        + [-30.0] * 3 + [-90.0] * 20
    seg = mz.segmenty_mowy(env)
    assert seg == [(0.3, 1.3), (2.3, 2.8)]                         # oddech sklejony, pauza akapitu nie, trzask pominięty
    assert mz.segmenty_mowy([]) == [] and mz.segmenty_mowy([-100.0] * 50) == []
    g = mz.krzywa_sciszenia(seg, 3.5, 8.0)
    assert len(g) == 351 and g[0] == 0.0 and g[100] == -8.0 and g[200] == 0.0
    assert g[24] == pytest.approx(-8.0 * 0.06 / 0.12)               # zejście 0,12 s przed mową
    assert g[150] == pytest.approx(-8.0 * 0.5)                      # powrót 0,4 s po mowie: w połowie
    assert g[170] == 0.0 and min(g[225:290]) == -8.0
    glos = [-100.0] * 30 + [-20.0] * 100 + [-100.0] * 100 + [-20.0] * 50 + [-100.0] * 70
    muz = [-30.0] * 30 + [-38.0] * 100 + [-30.0] * 100 + [-38.0] * 50 + [-30.0] * 70
    p = mz.proporcje_lektora(glos, muz, seg)
    assert p["muzyka_pod_glosem_db"] == -18.0 and p["muzyka_w_pauzach_db"] == -10.0 and p["uwagi"] == []
    assert p["mowa_s"] == 1.5 and p["odcinki"] == 2
    glosno = mz.proporcje_lektora(glos, [-25.0] * 350, seg)
    assert glosno["muzyka_pod_glosem_db"] == -5.0 and "głos ginie" in glosno["uwagi"][0]
    cicho = mz.proporcje_lektora(glos, [-60.0] * 350, seg)
    assert "prawie jej nie słychać" in cicho["uwagi"][0]


def test_lektor_w_cli_dlugosc_z_lektora(tmp_path, monkeypatch):
    lektor = tmp_path / "lektor.wav"
    lektor.write_bytes(b"RIFF")
    zlapane = {}
    monkeypatch.setattr(mz, "dlugosc_filmu", lambda p: 12.5)

    def stop(a, dlugosc, zd):
        zlapane.update(dlugosc=dlugosc, zd=zd)
        raise SystemExit("stop")
    monkeypatch.setattr(mz, "plan_muzyki", stop)
    with pytest.raises(SystemExit, match="stop"):
        mz.main(["zrob", "-o", str(tmp_path / "m.wav"), "--lektor", str(lektor), "--lektor-od", "0.5", "--bez-efektow"])
    assert zlapane["dlugosc"] == 13.0                               # bez obrazu i --dlugosc: koniec lektora
    with pytest.raises(SystemExit, match="brak pliku lektora"):
        mz.main(["zrob", "-o", str(tmp_path / "m.wav"), "--lektor", str(tmp_path / "nie.wav")])
