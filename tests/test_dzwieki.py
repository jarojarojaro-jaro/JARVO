"""Biblioteka dźwięków CC0 (scripts/dzwieki.py → hq/web/dzwieki) i menu Audio: ten sam katalog i te same pliki
w edytorze HQ (plugin_api: /edit/dzwieki, /edit/dzwiek, /edit/wyodrebnij, /edit/lektor, /edit/nagranie)
i u Wideografa (projekt.py dzwieki, dodaj-dzwiek, wyodrebnij, lektor). Dodanie kopiuje plik obok filmu."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dz = _load("scripts/dzwieki.py", "jarvo_dzwieki_test")
pr = _load("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_dzwieki_test")
ed = pr.ed
LIB = ROOT / "hq" / "web" / "dzwieki"
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def test_biblioteka_zgodna_z_lista():
    # pliki, sumy, katalog i LICENCJE.md zgadzają się z DZWIEKI (bez sieci i ffmpeg)
    assert dz.bledy() == []
    kat = ed.dzwieki_katalog(LIB)
    assert [k["id"] for k in kat["kategorie"]] == [k for k, *_ in dz.KATEGORIE]
    assert len(kat["dzwieki"]) == len(dz.DZWIEKI)
    for k, *_ in dz.KATEGORIE:                       # każda kategoria ma czym wybierać
        assert sum(d["kat"] == k for d in kat["dzwieki"]) >= 5, k
    assert all(d["licencja"] == "CC0-1.0" and d["autor"] and d["zrodlo"].startswith("https://") for d in kat["dzwieki"])
    # rozmiar w ryzach (repo i obraz): efekty krótkie, podkłady najwyżej minuta
    assert sum(p.stat().st_size for p in LIB.glob("*/*.mp3")) < 12 * 2**20
    assert all(d["dl"] <= (60.1 if d["kat"] == "muzyka" else 10.1) for d in kat["dzwieki"])


def test_tylko_cc0_z_freesound():
    strona = f'<a href="http://{dz.CC0}/">CC0</a> data-mp3="https://cdn.freesound.org/previews/60/60013_71257-lq.mp3"'
    assert dz.podglad_fs(strona, 60013) == "https://cdn.freesound.org/previews/60/60013_71257-hq.mp3"
    with pytest.raises(SystemExit, match="CC0"):
        dz.podglad_fs(strona.replace(dz.CC0, "creativecommons.org/licenses/by/4.0"), 60013)


def test_dodanie_kopiuje_plik_obok_filmu(tmp_path):
    film = tmp_path / "film.mp4"
    film.write_bytes(b"x")
    dest = ed.dzwiek_do_filmu(LIB, "whoosh", film)
    assert dest == tmp_path / "dzwieki" / "whoosh.mp3" and dest.read_bytes() == (LIB / "przejscia" / "whoosh.mp3").read_bytes()
    assert ed.dzwiek_do_filmu(LIB, "whoosh", film) == dest        # drugi raz ta sama kopia
    with pytest.raises(ed.ProjectError):
        ed.dzwiek_do_filmu(LIB, "nie-ma-takiego", film)
    assert ed.dzwiek_plik(None, "whoosh") is None


def test_katalog_nie_wychodzi_poza_biblioteke(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "tajne.mp3").write_bytes(b"x")
    (tmp_path / "lib" / "katalog.json").write_text(json.dumps({"dzwieki": [{"id": "zly", "plik": "../tajne.mp3"}]}))
    assert ed.dzwiek_plik(tmp_path / "lib", "zly") is None


def test_sciezki_i_polecenia_audio(tmp_path):
    film = tmp_path / "f" / "film.mp4"
    assert ed.wyodrebnij_cel(film, Path("/x/Mój film (1).mov")) == tmp_path / "f" / "dzwieki" / "Mój-film-1-dzwiek.m4a"
    assert "copy" in ed.wyodrebnij_cmd(Path("a.mp4"), Path("b.m4a"), "aac")
    assert "192k" in ed.wyodrebnij_cmd(Path("a.mp4"), Path("b.m4a"), "opus")
    a = ed.lektor_cel(film, "Cześć, to test!", "pl-PL-MarekNeural", "+0%")
    assert a.parent == tmp_path / "f" / "lektor" and a.name.startswith("lektor-cześć-to-test-")
    assert a == ed.lektor_cel(film, "Cześć, to test!", "pl-PL-MarekNeural", "+0%")      # ten sam tekst = ten sam plik
    assert a != ed.lektor_cel(film, "Cześć, to test!", "pl-PL-ZofiaNeural", "+0%")
    assert [ed.tempo_tts(v) for v in (10, "-5%", "+80", "x", None)] == ["+10%", "-5%", "+50%", "+0%", "+0%"]
    assert ed.nagranie_cel(film, 0).suffix == ".m4a" and "aac" in ed.nagranie_cmd(Path("a.webm"), Path("b.m4a"))


def test_lista_dla_agenta(capsys):
    assert pr.main(["dzwieki", "--kategoria", "pieniadze"]) == 0
    out = capsys.readouterr().out
    assert "liczenie-banknotow" in out and "whoosh" not in out
    assert pr.main(["dzwieki", "--szukaj", "applause"]) == 0 and "oklaski" in capsys.readouterr().out
    assert pr.main(["dzwieki", "--muzyka"]) == 0 and "muzyka-lofi" in capsys.readouterr().out
    assert pr.main(["dzwieki", "--szukaj", "zzzz"]) == 1


@pytest.fixture()
def film(tmp_path):
    f = tmp_path / "film.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=4",
                    "-f", "lavfi", "-i", "sine=d=4", "-shortest", "-pix_fmt", "yuv420p", "-c:a", "aac", str(f)], check=True)
    return f


def proj(f):
    return json.loads(ed.project_path(f).read_text(encoding="utf-8"))


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_agent_dodaje_dzwiek_i_podklad(film, capsys):
    assert pr.main(["dodaj-dzwiek", str(film), "kasa", "--start", "1.5"]) == 0
    assert pr.main(["dodaj-dzwiek", str(film), "muzyka-lofi", "--wyciszanie", "1"]) == 0
    a = proj(film)["audio"]
    assert Path(a[0]["src"]) == film.parent / "dzwieki" / "kasa.mp3" and a[0]["start"] == 1.5 and a[0]["volume"] == 1.0
    assert a[1]["volume"] == 0.3 and a[1]["fadeOut"] == 1.0                     # podkład ciszej, z wyciszeniem
    assert pr.main(["sprawdz", str(film)]) == 0


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_wyodrebnij_dzwiek_klipu_i_innego_filmu(film, tmp_path):
    pr.save(film, {"version": 1, "canvas": {"w": 320, "h": 240, "fps": 25}, "texts": [], "audio": [],
                   "clips": [{"id": "c1", "src": str(film), "kind": "video", "in": 0, "out": 1},
                             {"id": "c2", "src": str(film), "kind": "video", "in": 2, "out": 4, "fadeOut": 0.5}]})
    assert pr.main(["wyodrebnij", str(film), "c2"]) == 0
    p = proj(film)
    m = p["audio"][0]
    # dźwięk klipu zostaje w tym samym miejscu osi jako osobne audio (AAC skopiowane bez straty), klip wyciszony
    assert (m["start"], m["in"], m["out"], m.get("fadeOut")) == (1.0, 2, 4, 0.5)
    assert Path(m["src"]).suffix == ".m4a" and ed.probe(Path(m["src"]))["acodec"] == "aac"
    assert p["clips"][1]["muted"] is True and not p["clips"][0].get("muted")
    with pytest.raises(SystemExit, match="wyciszony"):
        pr.main(["wyodrebnij", str(film), "c2"])
    assert pr.main(["wyodrebnij", str(film), "--plik", str(film), "--start", "0.5"]) == 0
    assert proj(film)["audio"][1]["start"] == 0.5
    cisza = tmp_path / "cisza.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=64x64:r=25:d=1", str(cisza)], check=True)
    with pytest.raises(SystemExit, match="nie ma dźwięku"):
        pr.main(["wyodrebnij", str(film), "--plik", str(cisza)])
    p = proj(film)
    assert ed.normalize(p, pr.resolve)["audio"][0]["src"] == Path(m["src"])     # eksport przyjmuje wyodrębniony plik


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_nagranie_z_przegladarki_na_aac(tmp_path):
    src = tmp_path / "nagranie.webm"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=1", "-c:a", "libopus", str(src)], check=True)
    dest = tmp_path / "out.m4a"
    subprocess.run(ed.nagranie_cmd(src, dest), check=True, capture_output=True)
    info = ed.probe(dest)
    assert info["acodec"] == "aac" and info["duration"] == pytest.approx(1.0, abs=0.1) and ed.media_kind(dest) == "audio"


def test_menu_audio_w_edytorze():
    # edytor woła te same endpointy, a Wideograf dostaje w prośbie z edytora polecenia biblioteki
    js = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "hq" / "web" / "src").glob("*.js")))
    for ep in ("/edit/dzwieki", "/edit/dzwiek-plik", "/edit/dzwiek`", "/edit/muzyka", "/edit/wyodrebnij", "/edit/lektor", "/edit/nagranie"):
        assert ep in js, ep
    api = (ROOT / "hq" / "plugin" / "plugin_api.py").read_text(encoding="utf-8")
    for ep in ("/edit/dzwieki", "/edit/dzwiek-plik", '"/edit/dzwiek"', "/edit/muzyka", "/edit/wyodrebnij", "/edit/lektor", "/edit/nagranie"):
        assert ep in api, ep
    assert "projekt.py dodaj-dzwiek" in js and "wyodrebnij" in js
