"""„Edytuj ujęcie” filmu z kodu: `projekt.py z-kodu --strona` zapisuje źródło ujęć (strona, preset, odcinek osi strony
każdego klipu), `popraw-ujecie` bierze je z projektu, trasa /edit/ujecie zapisuje parametry strony i renderuje tylko
odcinek klipu w tle (zadanie z postępem, atrapa html_wideo.py), front liczy ten sam odcinek co edytor.py, a lista
mediów edytora pomija pliki robocze kontroli."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, load_script

ed = load_script("hq/plugin/edytor.py", "jarvo_edytor_ujecie_test")
an = load_script("hq/plugin/animacja.py", "jarvo_animacja_ujecie_test")
pr = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_ujecie_test")
SKRYPTY = REPO / "profiles" / "jarvo-wideo" / "scripts"
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
POLA = [{"klucz": "tytul1", "typ": "tekst", "etykieta": "Tytuł 1", "wartosc": "PIERWSZE", "czas": [0, 2]},
        {"klucz": "tytul2", "typ": "tekst", "etykieta": "Tytuł 2", "wartosc": "DWANAŚCIE RÓL", "czas": [2, 4]},
        {"klucz": "akcent", "typ": "kolor", "etykieta": "Akcent", "wartosc": "#FF5500"}]

# atrapa html_wideo.py: zielony obraz rozmiaru kadru na --dlugosc, „klatka” na stdout jak prawdziwy przy JARVO_HTML_POSTEP
ATRAPA = r'''
import os, subprocess, sys
a = sys.argv
dl, fps, out = float(a[a.index("--dlugosc") + 1]), float(a[a.index("--fps") + 1]), a[a.index("-o") + 1]
open(out + ".argv", "w").write("\n".join(a[1:]))
if os.environ.get("JARVO_HTML_POSTEP") == "1":
    for _ in range(round(dl * fps)):
        print("klatka", flush=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=green:s=320x180:r={fps:g}:d={dl}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", out], check=True)
'''


def kolor(path: Path, barwa: str, sek: float) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={barwa}:s=320x180:r=30:d={sek}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@pytest.fixture
def film(tmp_path):
    if not HAS_FF:
        pytest.skip("brak ffmpeg")
    strona = tmp_path / "workspaces" / "src" / "anim" / "index.html"   # workspaces: katalog floty (ROOTS)
    strona.parent.mkdir(parents=True)
    strona.write_text("<html><script>window.__seek = () => {}</script></html>", encoding="utf-8")
    (strona.parent / "parametry.json").write_text(json.dumps({"pola": POLA}, ensure_ascii=False), encoding="utf-8")
    f = tmp_path / "workspaces" / "film.mp4"
    assert pr.main(["z-kodu", str(f), "--obraz", str(kolor(tmp_path / "obraz.mp4", "blue", 4)), "--ciecia", "2",
                    "--strona", str(strona), "--html-opcje", "--rozmiar 320x180", "--render"]) == 0
    return f


def test_z_kodu_zapisuje_zrodlo_ujec(film, capsys):
    proj = pr.load(film)
    zk = proj["zKodu"]
    obraz = str(pr.sciezki_dir(film) / "obraz.mp4")
    assert zk["strona"] == {"plik": str(film.parent / "src" / "anim" / "index.html"), "preset": "jarvo", "opcje": "--rozmiar 320x180"}
    assert zk["ujecia"] == {obraz: 0.0} and zk["parametry"][obraz]["tytul2"] == "DWANAŚCIE RÓL"
    assert [ed.zakres_strony(proj, c) for c in proj["clips"]] == [(0.0, 2.0), (2.0, 4.0)]
    assert not pr.edytowany(film)                                  # źródło ujęć nie jest edycją
    assert pr.main(["pokaz", str(film)]) == 0
    assert "strona 2.00–4.00" in capsys.readouterr().out


def test_zakres_strony_po_cieciu_i_dla_obcego_klipu():
    proj = {"zKodu": {"strona": {"plik": "/a/index.html"}, "ujecia": {"/s/obraz.mp4": 0.0, "/s/ujecie-c2-1.mp4": 2.0}}}
    assert ed.zakres_strony(proj, {"kind": "video", "src": "/s/ujecie-c2-1.mp4", "in": 0.5, "out": 1.25}) == (2.5, 3.25)
    assert ed.zakres_strony(proj, {"kind": "video", "src": "/inny.mp4", "in": 0, "out": 1}) is None
    assert ed.zakres_strony({"zKodu": {"ujecia": proj["zKodu"]["ujecia"]}},
                            {"kind": "video", "src": "/s/obraz.mp4", "in": 0, "out": 1}) is None   # bez strony: nie wiadomo


def test_popraw_ujecie_bez_strony_z_projektu(film, monkeypatch):
    c2 = pr.load(film)["clips"][1]
    wolania = []
    prawdziwe = subprocess.run

    def run(cmd, *a, **k):
        if "html_wideo.py" in str(cmd):
            wolania.append((cmd, k.get("env")))
            kolor(Path(cmd[cmd.index("-o") + 1]), "green", float(cmd[cmd.index("--dlugosc") + 1]))
            return subprocess.CompletedProcess(cmd, 0)
        return prawdziwe(cmd, *a, **k)
    monkeypatch.setattr(pr.subprocess, "run", run)
    assert pr.main(["popraw-ujecie", str(film), c2["id"], "--bez-renderu", "--postep"]) == 0
    cmd, env = wolania[0]
    assert cmd[cmd.index("wideo") + 1] == str(film.parent / "src" / "anim" / "index.html")
    assert cmd[cmd.index("--preset") + 1] == "jarvo" and cmd[-2:] == ["--rozmiar", "320x180"] and cmd[cmd.index("--od") + 1] == "2"
    assert env["JARVO_HTML_POSTEP"] == "1"
    po = pr.load(film)
    k = po["clips"][1]
    assert ed.zakres_strony(po, k) == (2.0, 4.0) and po["zKodu"]["parametry"][k["src"]]["tytul1"] == "PIERWSZE"
    po["clips"].append({**k, "id": "obcy", "src": str(kolor(film.parent / "obcy.mp4", "red", 1)), "in": 0, "out": 1})
    pr.save(film, po)
    with pytest.raises(SystemExit, match="nie pochodzi ze strony"):
        pr.main(["popraw-ujecie", str(film), "obcy"])


def test_parametr_czas_w_schemacie():
    pola = an.schemat({"pola": POLA})
    assert pola[1]["czas"] == [2.0, 4.0] and "czas" not in pola[2]
    for zly in ([2, 1], [0], "0-2", [0, True], [-1, 2]):
        with pytest.raises(an.ParamError, match="czas"):
            an.schemat({"pola": [{**POLA[0], "czas": zly}]})


def test_pliki_robocze_poza_lista_mediow(tmp_path, monkeypatch):
    for n in ("qa-look.jpg", "qa.jpg", "arkusz.jpg", "film-telefon.jpg", "film-pasek-2.5.jpg", "klatki-wzor.png", "wzor-vox.jpg"):
        assert ed.plik_roboczy(n), n
    for n in ("film.mp4", "qatar.mp4", "muzyka.wav", "logo.png", "zakupy-arkusza.jpg", "telefonia.mp4"):
        assert not ed.plik_roboczy(n), n
    pytest.importorskip("fastapi")
    if not HAS_FF:
        pytest.skip("brak ffmpeg")
    api = _api(tmp_path, monkeypatch)
    (tmp_path / "workspaces").mkdir()
    f = kolor(tmp_path / "workspaces" / "film.mp4", "blue", 1)
    for n in ("qa-look.jpg", "film-telefon.jpg", "logo.png"):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=32x32", "-frames:v", "1",
                        str(f.parent / n)], check=True)
    info = asyncio.run(api.edit_info(str(f)))
    assert {m["name"] for m in info["media"]} == {"film.mp4", "logo.png"}


def _api(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    monkeypatch.setenv("JARVO_PREVIEW_PORT", "0")
    monkeypatch.setenv("JARVO_SHARE_KEYS", "0")
    api = load_script("hq/plugin/plugin_api.py", f"jarvo_test_ujecie_api_{tmp_path.name}")
    monkeypatch.setattr(api.ROOTS, "jarvo_dir", tmp_path)
    return api


class Req:
    def __init__(self, body):
        self.body = body

    async def json(self):
        return self.body


def _skrypty(tmp_path: Path) -> Path:
    """projekt.py i edytor.py jak w dystrybucji (obok siebie) z atrapą html_wideo.py."""
    d = tmp_path / "skrypty"
    d.mkdir()
    shutil.copy(SKRYPTY / "projekt.py", d)
    shutil.copy(REPO / "hq" / "plugin" / "edytor.py", d)
    (d / "html_wideo.py").write_text(ATRAPA, encoding="utf-8")
    return d


def test_trasa_ujecia_renderuje_tylko_klip_z_postepem(film, tmp_path, monkeypatch):
    api = _api(tmp_path, monkeypatch)
    monkeypatch.setenv("JARVO_TOOLS_PYTHON", __import__("sys").executable)   # Python renderu strony (venv narzędzi)
    d = _skrypty(tmp_path)
    monkeypatch.setattr(api, "_wideo_skrypt", lambda n: d / n)
    proj = pr.load(film)
    c1, c2 = proj["clips"]
    parametry = film.parent / "src" / "anim" / "parametry.json"

    async def zastosuj(body):
        job = await api.edit_ujecie(Req(body))
        await api._edit.jobs[job["id"]]["task"]
        return api._edit.jobs[job["id"]]

    job = asyncio.run(zastosuj({"path": str(film), "id": c2["id"], "wartosci": {"tytul2": "TRZYNAŚCIE RÓL"}}))
    assert job["state"] == "done", job.get("error")
    assert job["kind"] == "ujecie" and job["zakres"] == [2.0, 4.0] and job["progress"] == 1.0 and job["klatki"] >= 60
    argv = next(pr.sciezki_dir(film).glob(".render-*.mp4.argv")).read_text().split("\n")
    assert argv[argv.index("--od") + 1] == "2" and argv[-2:] == ["--rozmiar", "320x180"]
    po = pr.load(film)
    assert po["clips"][0] == c1 and po["clips"][1]["src"] != c2["src"] and Path(c2["src"]).is_file()   # stary obraz zostaje
    assert po["zKodu"]["parametry"][po["clips"][1]["src"]]["tytul2"] == "TRZYNAŚCIE RÓL"
    assert json.loads(parametry.read_text(encoding="utf-8"))["pola"][1]["wartosc"] == "TRZYNAŚCIE RÓL"
    # nieudany render: parametry.json wraca do stanu sprzed „Zastosuj”
    (d / "html_wideo.py").write_text("import sys; sys.exit(3)", encoding="utf-8")
    przed = parametry.read_text(encoding="utf-8")
    job = asyncio.run(zastosuj({"path": str(film), "id": po["clips"][1]["id"], "wartosci": {"tytul2": "ZŁE"}}))
    assert job["state"] == "error" and "render ujęcia nie wyszedł" in job["error"]
    assert parametry.read_text(encoding="utf-8") == przed and pr.load(film)["clips"][1]["src"] == po["clips"][1]["src"]
    for body, kod in (({"path": str(film), "id": "nie-ma"}, 404),
                      ({"path": str(film), "id": c1["id"], "wartosci": {"nieznane": 1}}, 400)):
        with pytest.raises(api.HTTPException) as e:
            asyncio.run(api.edit_ujecie(Req(body)))
        assert e.value.status_code == kod


def test_front_liczy_zakres_i_pola_jak_serwer():
    if not shutil.which("node"):
        pytest.skip("brak node")
    js = (REPO / "hq" / "web" / "src" / "47-ujecie.js").read_text(encoding="utf-8")
    proj = {"zKodu": {"strona": {"plik": "/a/index.html"}, "ujecia": {"/s/o.mp4": 0.0, "/s/u.mp4": 2.0}}}
    klipy = [{"kind": "video", "src": "/s/u.mp4", "in": 0.5, "out": 1.25}, {"kind": "video", "src": "/x.mp4", "in": 0, "out": 1},
             {"kind": "image", "src": "/s/o.mp4", "in": 0, "out": 1}]
    prog = (f"const P = {json.dumps(proj)}, K = {json.dumps(klipy)}, pola = {json.dumps(an.schemat({'pola': POLA}))};"
            "const r = (x) => x.map((p) => p.klucz);"
            "const a = ujPola(pola, [2, 4]), b = ujPola(pola.map(({ czas, ...p }) => p), [2, 4]);"
            "console.log(JSON.stringify({z: K.map((c) => ujZakres(P, c)), a: [r(a.wlasne), r(a.wspolne), a.przypisane],"
            " b: [r(b.wlasne), r(b.wspolne), b.przypisane]}));")
    out = json.loads(subprocess.run(["node", "-e", js + "\n" + prog], capture_output=True, text=True, check=True).stdout)
    assert out["z"] == [list(ed.zakres_strony(proj, c)) if ed.zakres_strony(proj, c) else None for c in klipy]
    assert out["a"] == [["tytul2"], ["akcent"], True] and out["b"] == [[], ["tytul1", "tytul2", "akcent"], False]


def test_edytor_ma_przycisk_ujecia_i_trase():
    src = (REPO / "hq" / "web" / "src" / "45-edytor.js").read_text(encoding="utf-8")
    assert src.count("setUjecie(c.id)") == 2                       # pasek klipu na komputerze i na telefonie
    assert "api.editUjecie(path, ujKlip.id, wartosci)" in src and "await saveNow()" in src
    assert "editUjecie" in (REPO / "hq" / "web" / "src" / "10-api.js").read_text(encoding="utf-8")
