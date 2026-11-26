"""Poprawka jednego ujęcia filmu z kodu bez renderu całości: `projekt.py podmien` i `popraw-ujecie` (nowe źródło
klipu w <film>-sciezki/, oś bez zmian, render projektu działa) oraz `html_wideo.py --od` (odcinek osi strony)."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKRYPTY = ROOT / "profiles" / "jarvo-wideo" / "scripts"
sys.path.insert(0, str(SKRYPTY))
spec = importlib.util.spec_from_file_location("projekt_pu", SKRYPTY / "projekt.py")
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)
import html_wideo as hw  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")


def kolor(path: Path, barwa: str, sek: float, w: int = 320, h: int = 180) -> Path:
    RUN(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={barwa}:s={w}x{h}:r=30:d={sek}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@pytest.fixture
def film(tmp_path):
    obraz = kolor(tmp_path / "obraz-src.mp4", "blue", 4)
    f = tmp_path / "film.mp4"
    assert pr.main(["z-kodu", str(f), "--obraz", str(obraz), "--ciecia", "2", "--render"]) == 0
    return f


def test_podmien_ujecie_os_bez_zmian_i_render(film, tmp_path):
    proj = pr.load(film)
    c1, c2 = proj["clips"]
    nowe = kolor(tmp_path / "nowe.mp4", "red", 2.0)
    assert pr.main(["podmien", str(film), c2["id"], "--plik", str(nowe)]) == 0
    po = pr.load(film)
    assert po["clips"][0] == c1                                    # pierwsze ujęcie nietknięte
    k = po["clips"][1]
    assert Path(k["src"]).parent == pr.sciezki_dir(film) and Path(k["src"]).name.startswith(f"ujecie-{c2['id']}-")
    assert (k["in"], k["out"]) == (0.0, 2.0) and pr.total(po) == pytest.approx(4.0)
    assert Path(c2["src"]).is_file()                               # stary obraz zostaje (cofnięcie w edytorze)
    ramka = subprocess.run(["ffmpeg", "-v", "error", "-ss", "3", "-i", str(film), "-frames:v", "1", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    assert ramka[0] > 150 and ramka[2] < 100                       # w filmie (render projektu) drugie ujęcie jest czerwone
    assert pr.edytowany(film)                                      # z-kodu nie nadpisze poprawki bez --nadpisz


def test_podmien_inna_dlugosc_to_blad(film, tmp_path):
    c2 = pr.load(film)["clips"][1]
    with pytest.raises(SystemExit, match="ta sama|tej samej długości"):
        pr.main(["podmien", str(film), c2["id"], "--plik", str(kolor(tmp_path / "dlugie.mp4", "red", 3.0))])
    assert pr.load(film)["clips"][1]["src"] == c2["src"]


def test_popraw_ujecie_renderuje_tylko_zakres(film, tmp_path, monkeypatch):
    c2 = pr.load(film)["clips"][1]
    wolania = []

    def html_wideo(cmd, *a, **k):
        wolania.append(cmd)
        kolor(Path(cmd[cmd.index("-o") + 1]), "green", float(cmd[cmd.index("--dlugosc") + 1]))
        return subprocess.CompletedProcess(cmd, 0)

    strona = tmp_path / "anim.html"
    strona.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(pr.subprocess, "run", lambda cmd, *a, **k: html_wideo(cmd) if "html_wideo.py" in str(cmd)
                        else RUN(cmd, *a, **k))
    assert pr.main(["popraw-ujecie", str(film), c2["id"], "--strona", str(strona), "--html-opcje", "--rozmiar 320x180"]) == 0
    cmd = wolania[0]
    assert cmd[cmd.index("--od") + 1] == "2" and float(cmd[cmd.index("--dlugosc") + 1]) == pytest.approx(2 + 1 / 30, abs=1e-3)
    assert cmd[-2:] == ["--rozmiar", "320x180"] and cmd[cmd.index("--preset") + 1] == "jarvo"
    po = pr.load(film)
    k = po["clips"][1]
    assert (k["in"], k["out"]) == (0.0, 2.0) and pr.total(po) == pytest.approx(4.0)
    assert po["zKodu"]["ujecia"][k["src"]] == 2.0 and pr.chwila_strony(po, k) == 2.0
    assert not any(p.name.startswith(".render-") for p in pr.sciezki_dir(film).iterdir())


def test_html_wideo_od_przesuwa_os(monkeypatch, tmp_path):
    """`wideo --od 12.4 --dlugosc 1`: 30 klatek strony od 12,4 s (capture dostaje chwile osi strony)."""
    zlapane = {}
    monkeypatch.setattr(hw, "ensure_playwright", lambda: None)
    monkeypatch.setattr(hw, "capture_rownolegle", lambda src, times, *a, **k: zlapane.setdefault("t", times) and [])
    monkeypatch.setattr(hw, "encode", lambda *a, **k: tmp_path / "x.mp4")
    strona = tmp_path / "a.html"
    strona.write_text("<html></html>", encoding="utf-8")
    hw.main(["wideo", str(strona), "--od", "12.4", "--dlugosc", "1", "-o", str(tmp_path / "x.mp4"), "--rownolegle", "1"])
    assert zlapane["t"][0] == 12.4 and len(zlapane["t"]) == 30 and zlapane["t"][-1] == pytest.approx(12.4 + 29 / 30)


RUN = subprocess.run      # prawdziwe uruchamianie (test popraw-ujecie podmienia subprocess.run tylko dla html_wideo)
