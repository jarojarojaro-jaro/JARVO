"""silnikjava we flocie: przypięcie w locku i narzedzia.py, strony rysowany.py i pracownia.py, lektor pod oś silnika,
cięcia, kroje stylów, serwowanie /_lib/silnikjava/ i /_lib/malarz/, zgodność zasad rysownika z silnikiem oraz testy
samego silnika (node --test, unittest voxel), gdy klon na przypiętym commicie jest pod ręką (`narzedzia.py instaluj
silnikjava` albo JARVO_SILNIKJAVA_SRC)."""

from __future__ import annotations

import array
import importlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKRYPTY = REPO / "profiles" / "jarvo-wideo" / "scripts"
sys.path.insert(0, str(SKRYPTY))
sys.path.insert(0, str(REPO / "scripts"))

import fleetlib as fl  # noqa: E402
import narzedzia as nz  # noqa: E402
import rysowany as ry  # noqa: E402
import pracownia as pr  # noqa: E402
import voxel as vx  # noqa: E402


def klon() -> Path | None:
    p = Path(os.environ.get("JARVO_SILNIKJAVA_SRC") or nz.SILNIKJAVA)
    if not (p / ".git").exists():
        return None
    head = subprocess.run(["git", "-C", str(p), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return p if head == nz.SILNIKJAVA_REV else None


SJ = klon()
z_klonem = pytest.mark.skipif(SJ is None, reason="brak klonu silnikjava na przypiętym commicie")


def test_przypiecie_w_locku_i_narzedziach():
    lock = fl.load_lock()
    src = lock["sources"]["silnikjava"]
    assert src["rev"] == nz.SILNIKJAVA_REV and src["license"] == "MIT" and src["license_file"] == "LICENSE"
    assert src["repo"].rstrip("/") + ".git" == nz.SILNIKJAVA_REPO
    for agent in ("jarvo", "jarvo-wideo"):
        dest = {e["dest"] for e in lock["agents"][agent]}
        assert {"wideo/film-rysowany", "wideo/pracownia-malarza", "wideo/voxel-ascii"} <= dest
    assert "silnikjava" in nz.TOOLS and "/docs/img/" in nz.SILNIKJAVA_POMIN and "/tools/" in nz.SILNIKJAVA_POMIN
    assert "/examples/voice/*/*.ogg" in nz.SILNIKJAVA_POMIN and "scipy==1.16.3" in nz.VOXEL_PY
    env = nz.env_for("silnikjava")
    assert env["MALARZ"].endswith(os.path.join(".claude", "skills", "malarz")) and env["SILNIKJAVA"] == str(nz.SILNIKJAVA)
    assert env["VOXEL"].endswith("voxel-ascii")


def test_rodziny_i_pliki_krojow():
    themes = "fonts: { hand: '\"Kalam\", \"Caveat\", cursive', title: '\"Caveat Brush\", \"Kalam\", cursive' },\n" \
             "fonts: { hand: '\"VT323\", monospace' },"
    assert nz.rodziny_stylow(themes) == ["Kalam", "Caveat", "Caveat Brush", "VT323"]
    assert nz.pliki_rodziny(["Caveat[wght].ttf", "OFL.txt"]) == [("Caveat[wght].ttf", "100 900")]
    assert nz.pliki_rodziny(["Kalam-Bold.ttf", "Kalam-Light.ttf", "Kalam-Regular.ttf"]) == \
        [("Kalam-Regular.ttf", "400"), ("Kalam-Bold.ttf", "700")]
    assert nz.pliki_rodziny(["VT323-Regular.ttf"]) == [("VT323-Regular.ttf", "400")]
    assert nz.pliki_rodziny(["X-Italic.ttf"]) == []


class _Fonty:
    """Atrapa google/fonts: Kalam (ofl, statyczne), Special Elite (apache), Nima (brak)."""
    def __init__(self, ttf: bytes):
        self.ttf, self.pobrane = ttf, []

    def pliki(self, rodzina, licencja="ofl"):
        return {("kalam", "ofl"): ["Kalam-Regular.ttf", "OFL.txt"],
                ("specialelite", "apache"): ["SpecialElite-Regular.ttf", "LICENSE.txt"]}.get((rodzina, licencja), [])

    def plik(self, rodzina, nazwa, licencja="ofl"):
        self.pobrane.append(nazwa)
        return self.ttf if nazwa.endswith(".ttf") else b"licencja"


def test_kroje_silnikjava_css_licencje_i_bez_sieci(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "themes.js").write_text(
        "fonts: { hand: '\"Kalam\", cursive', title: '\"Special Elite\", \"Nima\", serif' },", encoding="utf-8")
    monkeypatch.setattr(nz, "znaki_kroju", lambda p: {ord(z) for z in nz.POLSKIE})
    zrodlo = _Fonty(b"ttf")
    uwagi = nz.kroje_silnikjava(tmp_path, zrodlo)
    css = (tmp_path / "kroje" / "fonts.css").read_text(encoding="utf-8")
    assert '@font-face{font-family:"Kalam";src:url("Kalam-Regular.ttf");font-weight:400' in css
    assert 'font-family:"Special Elite"' in css and (tmp_path / "kroje" / "LICENSE-specialelite.txt").is_file()
    assert (tmp_path / "kroje" / "OFL-kalam.txt").is_file()
    assert any(u.startswith("Nima:") for u in uwagi)
    zrodlo.pobrane.clear()
    assert nz.kroje_silnikjava(tmp_path, zrodlo) == [] and zrodlo.pobrane == []    # gotowe: bez sieci


def test_strona_i_scena_rysowanego():
    html = ry.strona("import { zbuduj } from './scena.js';", None, "Tytuł <x>")
    assert "const GLOS = null;" in html and "/_lib/silnikjava/kroje/fonts.css" in html and "&lt;x>" in html
    for klucz in ("window.__seek", "window.__ready = true", "__W: W", "s.captions = null", "window.__os", "has('render')"):
        assert klucz in html
    assert 'const GLOS = "glos/voice.json";' in ry.strona("", "glos/voice.json")
    js = ry.scena("chalk", False, "Jak „to” działa?")
    assert "theme: 'chalk' })" in js and "format: 'reel'" not in js and '"Jak „to” działa?"' in js
    assert "format: 'reel'" in ry.scena("neon", True, "x") and "strefa bezpieczna rolki" in ry.scena("neon", True, "x")


def test_voice_json_z_osi_narracji():
    os_ = {"lektor": "lektor.wav", "zdania": [
        {"tekst": "Agent patrzy.", "start": 0.5, "koniec": 1.5, "ujecie": "u1",
         "slowa": [{"tekst": "Agent", "start": 0.5, "koniec": 0.9}, {"tekst": "patrzy", "start": 0.9, "koniec": 1.5}]},
        {"tekst": "Potem działa.", "start": 2.0, "koniec": 3.0, "ujecie": "u2",
         "slowa": [{"tekst": "Potem", "start": 2.0, "koniec": 2.4}, {"tekst": "działa", "start": 2.4, "koniec": 3.0}]}]}
    v = ry.voice_json(ry.zdania_z_osi(os_), "/x/lektor.wav", podzialy={1.5, 2.4})
    assert [b["id"] for b in v["beats"]] == ["b1", "b2"] and v["beats"][1]["ujecie"] == "u2"
    assert v["beats"][0]["words"] == [{"w": "Agent", "s": 0.0, "e": 0.4}, {"w": "patrzy", "s": 0.4, "e": 1.0}]
    assert v["beats"][1]["words"][1] == {"w": "działa", "s": 0.4, "e": 1.0, "p": True}
    assert v["beats"][0]["duration"] == 1.0 and v["beats"][0]["audio"] is None
    assert v["zdania"] == [{"id": "b1", "start": 0.5, "koniec": 1.5}, {"id": "b2", "start": 2.0, "koniec": 3.0}]


def test_zdania_ze_slow_krotkiego_lektora():
    slowa = [{"start": 0.0, "end": 0.3, "text": "Raz"}, {"start": 0.3, "end": 0.6, "text": "dwa."},
             {"start": 0.9, "end": 1.2, "text": "Trzy?"}, {"start": 1.4, "end": 1.6, "text": "Cztery"}]
    z = ry.zdania_ze_slow(slowa)
    assert [x["tekst"] for x in z] == ["Raz dwa.", "Trzy?", "Cztery"]
    assert (z[0]["start"], z[0]["koniec"], z[2]["start"]) == (0.0, 0.6, 1.4)


def test_lektor_pod_os_silnika_i_slowa():
    sr = ry.SR
    pcm = array.array("h", [0] * int(4 * sr))
    for i in range(int(1.0 * sr), int(1.5 * sr)):          # zdanie 1: 1,0–1,5 s
        pcm[i] = 1000
    for i in range(int(2.5 * sr), int(3.0 * sr)):          # zdanie 2: 2,5–3,0 s
        pcm[i] = 2000
    glos = {"zdania": [{"id": "b1", "start": 1.0, "koniec": 1.5}, {"id": "b2", "start": 2.5, "koniec": 3.0}],
            "beats": [{"id": "b1", "words": [{"w": "a", "s": 0.0, "e": 0.5, "p": True}]},
                      {"id": "b2", "words": [{"w": "b", "s": 0.1, "e": 0.5}]}]}
    os_ = {"dlugosc": 6.0, "zdania": [{"id": "b1", "start": 0.3}, {"id": "b2", "start": 4.0}]}
    out, slowa = ry.uloz_lektor(pcm, glos, os_)
    assert len(out) == 6 * sr
    assert out[int(0.5 * sr)] == 1000 and out[int(4.2 * sr)] == 2000      # zdania tam, gdzie silnik je postawił
    assert out[int(1.2 * sr)] == 0 and out[int(2.7 * sr)] == 0            # stare miejsca są ciche
    assert slowa == [{"start": 0.3, "end": 0.8, "text": "a", "podzial": True}, {"start": 4.1, "end": 4.5, "text": "b"}]


def test_ciecia_na_akapitach_i_scieraniu():
    os_ = {"scieranie": [5.0], "zdania": [
        {"id": "b1", "rysunek_od": 0.0, "rysunek_do": 2.0}, {"id": "b2", "rysunek_od": 2.5, "rysunek_do": 4.0},
        {"id": "b3", "rysunek_od": 6.0, "rysunek_do": 8.0}]}
    glos = {"beats": [{"id": "b1", "ujecie": "u1"}, {"id": "b2", "ujecie": "u1"}, {"id": "b3", "ujecie": "u2"}]}
    assert ry.ciecia(os_, glos) == [5.0]                    # akapit 2 zaczyna się ścieraniem tablicy
    assert ry.ciecia({**os_, "scieranie": []}, glos) == [6.0]
    assert ry.ciecia({**os_, "zdania": []}, None) == [5.0]   # film bez lektora: cięcia na ścieraniu


def test_ocena_lintu_i_audytu():
    lint = {"krokow": 3, "dlugosc": 4.0, "problemy": [{"poziom": "uwaga", "t": 1.0, "nazwa": "b1", "problem": "x"}]}
    audyt = {"klatek": 120, "sr_ms": 3.0, "p95_ms": 5.0, "max_ms": 9.0, "reka_proc": 99.0, "vmax": 900.0, "skoki": []}
    assert ry.ocena(lint, audyt, 33)["ok"] is True
    assert ry.ocena(lint, {**audyt, "p95_ms": 40.0}, 33)["ok"] is False
    assert ry.ocena(lint, {**audyt, "skoki": [{"t": 1.0, "px": 90}]}, 33)["ok"] is False
    zly = {**lint, "problemy": [{"poziom": "blad", "t": 0.0, "nazwa": "pen#1", "problem": "element bez ręki"}]}
    assert ry.ocena(zly, None, 33)["ok"] is False


def test_strona_pracowni():
    html = pr.strona(30, 3.5, None, "obraz.json")
    assert '"obraz": "obraz.json"' in html and '"czas": "30"' in html and "uklad" not in html
    assert "/_lib/malarz/pracownia/pracownia.js" in html and "q.set('film', '1')" in html and "window.__seek" in html
    assert '"uklad": "poziom"' in pr.strona(10, 2, "poziom")


def test_szelest_wav(tmp_path):
    import base64
    import wave
    probki = array.array("h", [0, 1000, -1000, 32767])
    plik = pr.zapisz_szelest(base64.b64encode(probki.tobytes()).decode(), tmp_path / "s.wav")
    with wave.open(str(plik)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 44100, 4)


def test_voxel_polecenie_i_kroj(tmp_path, monkeypatch):
    v = tmp_path / "vx"
    cmd = vx.polecenie(v, "lighthouse", ["--preview", "8"], vx.KROJ_SILNIKA)
    assert cmd[-4:] == [str(v / "run.py"), "lighthouse", "--preview", "8"]
    inny = vx.polecenie(v, "lighthouse", ["--sheet"], "/k/DejaVuSansMono-Bold.ttf")
    assert inny[1] == "-c" and inny[3:] == [str(v), "/k/DejaVuSansMono-Bold.ttf", "lighthouse", "--sheet"]
    assert all(vx.JEDEN_WATEK[k] == "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"))
    (v / "scenes").mkdir(parents=True)
    (v / "scenes" / "las.py").write_text('"""Las nocą."""\nVARIANTS = {"mgla": {}, "snieg": {}}\n', encoding="utf-8")
    assert vx.sceny(v) == [{"scena": "las", "warianty": ["mgla", "snieg"], "opis": "Las nocą."}]


def test_serwer_lib_silnikjava_i_malarz(tmp_path, monkeypatch):
    import html_wideo as hw
    sj = tmp_path / "sj"
    (sj / "src").mkdir(parents=True)
    (sj / "src" / "index.js").write_text("export const SILNIK = 1;", encoding="utf-8")
    m = sj / ".claude" / "skills" / "malarz" / "pracownia"
    m.mkdir(parents=True)
    (m / "pracownia.js").write_text("// pracownia", encoding="utf-8")
    (tmp_path / "sekret.txt").write_text("nie", encoding="utf-8")
    monkeypatch.setattr(nz, "SILNIKJAVA", sj)
    monkeypatch.setattr(nz, "MALARZ", sj / ".claude" / "skills" / "malarz")
    monkeypatch.setattr(nz, "JARVO_JS", tmp_path / "jarvo-js")
    strona = tmp_path / "strona"
    strona.mkdir()
    httpd = hw.serve(strona, lib=True)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        with urllib.request.urlopen(base + "/_lib/silnikjava/src/index.js") as r:
            assert b"SILNIK" in r.read()
        with urllib.request.urlopen(base + "/_lib/malarz/pracownia/pracownia.js") as r:
            assert b"pracownia" in r.read()
        for zle in ("/_lib/silnikjava/../sekret.txt", "/_lib/malarz/../../../../sekret.txt"):
            with pytest.raises(urllib.error.HTTPError):
                urllib.request.urlopen(base + zle)
    finally:
        httpd.shutdown()


def test_hq_lib_file_silnikjava(tmp_path):
    sys.path.insert(0, str(REPO / "hq" / "plugin"))
    core = importlib.import_module("hq_core")
    sj = tmp_path / "sj"
    (sj / "src").mkdir(parents=True)
    (sj / "src" / "index.js").write_text("x", encoding="utf-8")
    mal = sj / ".claude" / "skills" / "malarz" / "lib"
    mal.mkdir(parents=True)
    (mal / "pedzel.js").write_text("x", encoding="utf-8")
    nm = tmp_path / "nm"
    nm.mkdir()
    assert core.lib_file("silnikjava/src/index.js", nm, silnikjava_root=sj) == (sj / "src" / "index.js").resolve()
    assert core.lib_file("malarz/lib/pedzel.js", nm, malarz_root=sj / ".claude" / "skills" / "malarz") == \
        (mal / "pedzel.js").resolve()
    assert core.lib_file("silnikjava/.claude/skills/malarz/lib/pedzel.js", nm, silnikjava_root=sj) is None
    assert core.MALARZ_ROOT.parts[-4:] == ("silnikjava", ".claude", "skills", "malarz")


def test_skille_wspolne_bez_pauz_i_z_plikami():
    for nazwa in ("film-rysowany", "pracownia-malarza", "voxel-ascii"):
        d = REPO / "shared" / "skills" / nazwa
        fm, body = fl.read_skill(d / "SKILL.md")
        assert fm["name"] == nazwa and len(fm["description"]) <= fl.SKILL_PROMPT_DESC_LIMIT
        for ref in re.findall(r"`(references/[^`\s]+)`", body):
            assert (d / ref).is_file(), ref
        for md in d.rglob("*.md"):
            tekst = md.read_text(encoding="utf-8")
            assert "—" not in tekst and "–" not in tekst, md
            assert "**Co to jest:**" in body or md.name != "SKILL.md"


@z_klonem
def test_zasady_rysownika_zgodne_z_silnikiem():
    """references/zasady-rysownika.md = rozdziały 1–7 docs/ZASADY.md z przypiętego commitu (zakresy „do”, odnośniki
    jako nazwy plików); po podbiciu rev test pokazuje, że trzeba przenieść zmiany autora."""
    def rozdzialy(t: str) -> str:
        t = t[t.index("## 1. Fizyka ręki"):t.index("## 8. ")]
        return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t).replace("–", " do ").strip()
    nasze = (REPO / "shared/skills/film-rysowany/references/zasady-rysownika.md").read_text(encoding="utf-8")
    assert rozdzialy(nasze) == rozdzialy((SJ / "docs" / "ZASADY.md").read_text(encoding="utf-8"))


@z_klonem
def test_style_z_rejestru_silnika():
    lista = ry.style(SJ)
    assert len(lista) == 21 and {"chalk", "notebook", "iso", "ascii"} <= {s["id"] for s in lista}
    ref = (REPO / "shared/skills/film-rysowany/references/style.md").read_text(encoding="utf-8")
    assert all(f"| `{s['id']}` |" in ref for s in lista)


@z_klonem
@pytest.mark.skipif(not shutil.which("node"), reason="brak node")
@pytest.mark.parametrize("testy", ["tests", ".claude/skills/malarz/tests"])
def test_silnik_node(testy):
    p = subprocess.run(["node", "--test", testy], cwd=SJ, capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-1000:]


@z_klonem
def test_voxel_unittest():
    python = nz.py() if Path(nz.py()).exists() else sys.executable
    if subprocess.run([python, "-c", "import numpy, scipy, PIL"], capture_output=True).returncode:
        pytest.skip("brak numpy, scipy albo Pillow")
    p = subprocess.run([python, "-m", "unittest", "discover", "-s", str(nz.VOXEL / "tests" if SJ == nz.SILNIKJAVA
                        else SJ / ".claude/skills/voxel-ascii/tests")], capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr[-2000:]
