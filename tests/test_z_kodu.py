"""Film z kodu jako projekt edytora HQ (poziom 1): projekt.py z-kodu składa czysty obraz pocięty na ujęcia, głos
i efekty przypięte do obrazu, muzykę osobno i napisy jako tekst. ffmpeg zastępują tu atrapy (pomiar i kopie plików
sprawdza test w kontenerze), a cięcie sprawdza ta sama oś co w edytorze (edytor.remap_times)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import load_script

pr = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_z_kodu_test")
ed = pr.ed
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

SRT = """1
00:00:00,800 --> 00:00:04,400
Każdy worek mąki zaczyna się od kłosa.

2
00:00:05,950 --> 00:00:08,450
Orkisz to stare zboże.
"""


def test_ciecia_z_listy_lemo_i_osi_czasu(tmp_path):
    assert pr.ciecia_z("5.4, 9.6,0.05,26.95", 27.0) == [5.4, 9.6]          # przy brzegu filmu odpada
    ev = tmp_path / "events.json"
    ev.write_text(json.dumps({"dur": 27, "ev": [{"t": 0.9, "type": "vo"}, {"t": 14.4, "type": "cut", "shot": 4},
                                                  {"t": 5.4, "type": "cut", "shot": 2}]}))
    assert pr.ciecia_z(str(ev), 27.0) == [5.4, 14.4]
    os_ = tmp_path / "os_czasu.json"
    os_.write_text(json.dumps({"ujecia": [{"start": 0.0, "koniec": 3.1}, {"start": 3.1, "koniec": 7.0}, {"start": 7.0}]}))
    assert pr.ciecia_z(str(os_), 9.0) == [3.1, 7.0]
    assert pr.ciecia_z(None, 9.0) == []
    with pytest.raises(SystemExit, match="--ciecia"):
        pr.ciecia_z("nie-ma-pliku.json", 9.0)


def test_slowa_z_pliku_trzy_formaty(tmp_path):
    a = tmp_path / "lektor.slowa.json"
    a.write_text(json.dumps([{"start": 1.0, "end": 1.4, "text": "Druga"}, {"start": 0.2, "end": 0.6, "text": "Pierwsza", "podzial": True}]))
    assert pr.slowa_z_pliku(a) == [[0.2, 0.6, "Pierwsza", True], [1.0, 1.4, "Druga", False]]
    b = tmp_path / "film.mowa.json"
    b.write_text(json.dumps({"words": [[0.1, 0.3, "raz"], [0.4, 0.5, " "]]}))
    assert pr.slowa_z_pliku(b) == [[0.1, 0.3, "raz", False]]
    c = tmp_path / "puste.json"
    c.write_text("[]")
    with pytest.raises(SystemExit, match="brak słów"):
        pr.slowa_z_pliku(c)


def test_napisy_ze_slow_jak_wypalane_karaoke_po_trzy():
    slowa = [[0.0, 0.3, "Każdy", False], [0.3, 0.6, "worek", False], [0.6, 0.9, "naszej", False], [0.9, 1.3, "mąki.", False],
             [2.0, 2.4, "Orkisz", False], [2.4, 2.8, "to", False], [2.8, 3.3, "zboże.", False]]
    linie = pr.linie_napisow(None, slowa, pion_=False, karaoke=True)
    assert [ln["text"] for ln in linie] == ["Każdy worek naszej mąki.", "Orkisz to zboże."]   # samotne słowo zdania dołącza
    assert linie[0]["words"] == [[0.0, 0.3, "Każdy"], [0.3, 0.6, "worek"], [0.6, 0.9, "naszej"], [0.9, 1.3, "mąki."]]
    assert linie[1]["start"] == 2.0 and linie[1]["end"] == 3.3


def test_napisy_z_srt_ze_slowami_do_karaoke(tmp_path):
    srt = tmp_path / "film.srt"
    srt.write_text(SRT, encoding="utf-8")
    slowa = [[5.95 + 0.5 * i, 6.3 + 0.5 * i, w, False] for i, w in enumerate(["Orkisz", "to", "stare", "zboże."])]
    linie = pr.linie_napisow(srt, slowa, pion_=False, karaoke=True)
    assert [ln["text"] for ln in linie] == ["Każdy worek mąki zaczyna się od kłosa.", "Orkisz to stare zboże."]
    assert "words" not in linie[0]                                   # tej linii słowa nie pokrywają
    assert linie[1]["words"][1] == [0.5, 0.85, "to"]


@pytest.fixture()
def czesci(tmp_path, monkeypatch):
    """Części filmu z kodu w katalogu silnika i atrapy ffmpeg: obraz 27 s 1920×1080 @ 24, dźwięki w WAV."""
    src = tmp_path / "lemo" / "out"
    src.mkdir(parents=True)
    for n in ("obraz24.mp4", "voice.wav", "music.wav", "sfx.wav", "room.wav"):
        (src / n).write_bytes(b"x")
    (src / "film.srt").write_text(SRT, encoding="utf-8")
    dl = {"voice": 26.0}                                      # długości źródeł (reszta 27 s)

    def probe(p, *_a):
        p = Path(p)
        if p.suffix == ".mp4":
            return {"ok": True, "duration": 27.0, "w": 1920, "h": 1080, "fps": 24.0}
        return {"ok": True, "duration": dl.get(p.stem, 27.0)}

    def run(args, **_kw):                                     # kopia obrazu: ostatni argument to plik docelowy
        Path(args[-1]).write_bytes(b"v")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    def kopia(src_, dest, dl=None, wzmocnienie=1.0):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"a")
        wzmocnienia[dest.name] = (wzmocnienie, dl)
        return 2.5 if src_.name == "music.wav" else 1.0          # muzyce zabrakło zapasu: reszta w głośności elementu

    wzmocnienia = {}

    monkeypatch.setattr(pr.ed, "probe", probe)
    monkeypatch.setattr(pr.subprocess, "run", run)
    monkeypatch.setattr(pr, "kopia_dzwieku", kopia)
    monkeypatch.setattr(pr, "glosnosc_sumy", lambda audio, dur: -20.0)
    kopia.wzmocnienia = wzmocnienia
    return src


def z_kodu(film, src, *extra):
    return pr.main(["z-kodu", str(film), "--obraz", str(src / "obraz24.mp4"), "--ciecia", "5.4,9.6,14.4,19.8",
                    "--glos", f"{src / 'voice.wav'}@0.5", "--muzyka", str(src / "music.wav"), "--efekty", str(src / "sfx.wav"),
                    "--audio", f"Tło={src / 'room.wav'}", "--napisy", str(src / "film.srt"), "--kroj", "Caveat",
                    "--styl", "box", "--kolor", "#2B1E14", "--tlo", "#F4EDDB", *extra])


def test_z_kodu_obraz_w_ujeciach_dzwieki_osobno_napisy_tekstem(tmp_path, czesci, capsys):
    film = tmp_path / "out" / "mlyn.mp4"
    film.parent.mkdir()
    assert z_kodu(film, czesci) == 0
    p = json.loads(ed.project_path(film).read_text(encoding="utf-8"))
    kat = tmp_path / "out" / "mlyn-sciezki"
    assert [(c["in"], c["out"]) for c in p["clips"]] == [(0, 5.4), (5.4, 9.6), (9.6, 14.4), (14.4, 19.8), (19.8, 27.0)]
    assert {c["src"] for c in p["clips"]} == {str(kat / "obraz.mp4")} and (kat / "obraz.mp4").is_file()
    a = {m["label"]: m for m in p["audio"]}
    assert set(a) == {"Głos", "Efekty", "Muzyka", "Tło"}
    assert a["Głos"]["linked"] and a["Efekty"]["linked"] and a["Tło"]["linked"] and "linked" not in a["Muzyka"]
    assert a["Głos"]["src"] == str(kat / "glos.wav") and a["Tło"]["src"] == str(kat / "tlo.wav")
    assert (a["Głos"]["start"], a["Głos"]["in"], a["Głos"]["out"]) == (0.5, 0.0, 26.0)
    g = 10 ** (6 / 20)                                               # suma −20 LUFS → −14 LUFS: wzmocnienie w kopiach
    assert pr.kopia_dzwieku.wzmocnienia["glos.wav"] == (pytest.approx(g), 26.0)   # kopia tylko do końca filmu (od 0,5 s)
    assert a["Głos"]["volume"] == 1.0 and a["Muzyka"]["volume"] == 2.0   # elementy na 0 dB; muzyka obcięta do 200%
    caps = [t for t in p["texts"] if t.get("cap")]
    assert [t["text"] for t in caps] == ["Każdy worek mąki zaczyna się od kłosa.", "Orkisz to stare zboże."]
    assert caps[0]["style"] == "box" and caps[0]["color"] == "#2B1E14" and caps[0]["bg"] == "#F4EDDB"
    assert "Caveat" in caps[0]["font"] and "hl" not in caps[0]
    zk = p["zKodu"]
    assert zk["ciecia"] == [5.4, 9.6, 14.4, 19.8] and zk["lufs_przed"] == -20.0 and zk["lufs"] == -14.0
    assert zk["zrodla"]["glos"] == str(czesci / "voice.wav") and zk["podpis"] == pr.podpis(p)
    assert not pr.edytowany(film)
    out = capsys.readouterr().out
    assert "5 ujęciach" in out and "Muzyka" in out and "za cichy nawet przy 200%" in out and "projekt.py render" in out


def test_wyciete_ujecie_zabiera_swoj_glos_a_muzyka_gra_dalej(tmp_path, czesci):
    film = tmp_path / "mlyn.mp4"
    assert z_kodu(film, czesci) == 0
    p = json.loads(ed.project_path(film).read_text(encoding="utf-8"))
    bez = ed.remap_times(p, {**p, "clips": [c for i, c in enumerate(p["clips"]) if i != 1]})   # bez ujęcia 5,4–9,6
    a = {}
    for m in bez["audio"]:
        a.setdefault(m["label"], []).append((m["start"], m["in"], m["out"]))
    assert a["Głos"] == [(0.5, 0.0, 4.9), (5.4, 9.1, 26.0)]          # głos od 0,5 s: wycięte 4,9–9,1 s pliku
    assert a["Muzyka"] == [(0.0, 0.0, 27.0)]                          # muzyka nie przypięta: tylko się przesuwa
    assert [t["text"] for t in bez["texts"]] == ["Każdy worek mąki zaczyna się od kłosa."]   # napis z ujęcia znika


def test_z_kodu_nie_nadpisuje_projektu_po_edycji(tmp_path, czesci):
    film = tmp_path / "mlyn.mp4"
    assert z_kodu(film, czesci) == 0
    pp = ed.project_path(film)
    p = json.loads(pp.read_text(encoding="utf-8"))
    p["texts"][0]["text"] = "Poprawiony napis"                      # właściciel poprawił napis w edytorze
    pp.write_text(json.dumps(p), encoding="utf-8")
    assert pr.edytowany(film)
    with pytest.raises(SystemExit, match="--nadpisz"):
        z_kodu(film, czesci)
    assert z_kodu(film, czesci, "--nadpisz") == 0


def test_z_kodu_slowa_karaoke_i_bez_glosnosci(tmp_path, czesci):
    slowa = czesci / "lektor.slowa.json"
    slowa.write_text(json.dumps([{"start": 1.0, "end": 1.4, "text": "Młyn"}, {"start": 1.4, "end": 1.9, "text": "Zawada."}]))
    film = tmp_path / "film.mp4"
    assert pr.main(["z-kodu", str(film), "--obraz", str(czesci / "obraz24.mp4"), "--slowa", str(slowa), "--karaoke"]) == 0
    p = json.loads(ed.project_path(film).read_text(encoding="utf-8"))
    assert len(p["clips"]) == 1 and p["audio"] == [] and "lufs" not in p["zKodu"]
    (cap,) = p["texts"]
    assert cap["text"] == "Młyn Zawada." and cap["hl"] == pr.KARAOKE_HL and cap["words"] == [[0.0, 0.4, "Młyn"], [0.4, 0.9, "Zawada."]]


def test_z_kodu_zle_wejscie(tmp_path, czesci):
    with pytest.raises(SystemExit, match="NAZWA=plik"):
        pr.main(["z-kodu", str(tmp_path / "f.mp4"), "--obraz", str(czesci / "obraz24.mp4"), "--audio", str(czesci / "room.wav")])
    with pytest.raises(SystemExit, match="nie ma pliku dźwięku"):
        pr.main(["z-kodu", str(tmp_path / "f.mp4"), "--obraz", str(czesci / "obraz24.mp4"), "--glos", str(tmp_path / "brak.wav")])
    with pytest.raises(SystemExit, match="plik wideo"):
        pr.main(["z-kodu", str(tmp_path / "f.json"), "--obraz", str(czesci / "obraz24.mp4")])


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_kopia_i_glosnosc_sumy_z_ffmpeg(tmp_path):
    """Miks ponad 0 dBFS (float) ściszony w pliku, różnica w głośności elementu; suma dwóch ścieżek mierzona jak eksport."""
    import numpy as np
    import soundfile as sf
    sr = 48000
    t = np.arange(sr * 2) / sr
    sf.write(tmp_path / "glosny.wav", (1.6 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), sr, subtype="FLOAT")
    k = pr.kopia_dzwieku(tmp_path / "glosny.wav", tmp_path / "s" / "glos.wav", wzmocnienie=2.0)
    assert k == pytest.approx(2.0 * 1.6 * 10 ** (0.1 / 20), rel=0.02)   # do pliku weszło tylko tyle, ile się mieści
    data, _ = sf.read(tmp_path / "s" / "glos.wav")
    assert np.abs(data).max() < 1.0
    sf.write(tmp_path / "cichy.wav", (0.05 * np.sin(2 * np.pi * 440 * t)).astype(np.float32), sr)
    m = {"src": str(tmp_path / "cichy.wav"), "start": 0.0, "in": 0.0, "out": 2.0, "volume": 1.0}
    raz = pr.glosnosc_sumy([m], 2.0)
    dwa = pr.glosnosc_sumy([m, {**m, "volume": 1.0}], 2.0)
    assert dwa - raz == pytest.approx(6.0, abs=0.3)                  # dwa razy to samo = +6 dB
    assert subprocess.run(["ffprobe", "-v", "error", str(tmp_path / "s" / "glos.wav")]).returncode == 0
