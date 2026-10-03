"""Szybkie cięcie: podział klipu na równe części, usuń do / od wskaźnika i wycięcie odcinka osi. Te same reguły
w edytorze HQ (47-ciecie.js, testy w node) i u Wideografa (projekt.py tnij / wytnij); oś dosuwa napisy i audio."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from conftest import REPO, load_script

JS = (REPO / "hq" / "web" / "src" / "47-ciecie.js").read_text(encoding="utf-8")
HAS_NODE = bool(shutil.which("node"))


def node(prog: str):
    r = subprocess.run(["node", "-e", JS + "\n" + prog], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def projekt():
    return {"canvas": {"w": 1080, "h": 1920, "fps": 30}, "audio": [{"id": "m", "src": "m.mp3", "start": 9.0, "in": 0, "out": 3, "volume": 1}],
            "texts": [{"id": "t1", "text": "a", "start": 0.5, "end": 1.5}, {"id": "t2", "text": "b", "start": 5.5, "end": 6.5},
                      {"id": "t3", "text": "c", "start": 8.0, "end": 9.0}],
            "clips": [{"id": "a", "src": "a.mp4", "kind": "video", "in": 1.0, "out": 8.5, "speed": 1, "transition": {"type": "fade", "dur": 0.5}},
                      {"id": "b", "src": "b.mp4", "kind": "video", "in": 0, "out": 4, "speed": 2}]}


@pytest.fixture
def pr(tmp_path, monkeypatch):
    mod = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_ciecie_test")
    stan = {"p": projekt()}
    film = tmp_path / "film.mp4"
    film.write_bytes(b"x")
    monkeypatch.setattr(mod, "load", lambda f: json.loads(json.dumps(stan["p"])))
    monkeypatch.setattr(mod, "save", lambda f, p: stan.update(p=json.loads(json.dumps(p))))
    ids = iter(f"n{k}" for k in range(100))
    monkeypatch.setattr(mod, "new_id", lambda prefix: next(ids))
    mod.stan, mod.film = stan, str(film)
    return mod


def test_trzy_czesci_i_usun_srodek(pr):
    """Przykład właściciela: klip 7,5 s na 3 × 2,5 s, środkowa część usunięta, reszta osi się dosuwa."""
    assert pr.main(["tnij", pr.film, "a", "--czesci", "3"]) == 0
    cs = pr.stan["p"]["clips"]
    assert [(c["id"], c["in"], c["out"]) for c in cs] == [("a", 1.0, 3.5), ("n0", 3.5, 6.0), ("n1", 6.0, 8.5), ("b", 0, 4)]
    assert [c.get("transition") for c in cs] == [None, None, {"type": "fade", "dur": 0.5}, None]   # cięcie a→b zostaje
    assert pr.main(["usun", pr.film, "n0"]) == 0
    p = pr.stan["p"]
    assert [c["id"] for c in p["clips"]] == ["a", "n1", "b"]
    assert {x["id"]: (x["start"], x["end"]) for x in p["texts"]} == {"t1": (0.5, 1.5), "t2": (3.0, 4.0), "t3": (5.5, 6.5)}
    assert p["audio"][0]["start"] == 6.5


def test_tnij_w_chwili_osi_z_tempem(pr):
    assert pr.main(["tnij", pr.film, "b", "--w", "8.5"]) == 0          # klip b: oś 7,5–9,5 przy tempie 2×
    cs = pr.stan["p"]["clips"]
    assert [(c["id"], c["in"], c["out"]) for c in cs[1:]] == [("b", 0, 2.0), ("n0", 2.0, 4)]
    with pytest.raises(SystemExit, match="zapasem"):
        pr.main(["tnij", pr.film, "b", "--w", "9.45"])


def test_wytnij_odcinek_przez_dwa_klipy(pr):
    assert pr.main(["wytnij", pr.film, "--od", "6.0", "--do", "8.0"]) == 0
    p = pr.stan["p"]
    assert [(c["id"], c["in"], c["out"]) for c in p["clips"]] == [("a", 1.0, 7.0), ("b", 1.0, 4)]
    assert p["clips"][0]["transition"] == {"type": "fade", "dur": 0.5}
    assert {x["id"]: (x["start"], x["end"]) for x in p["texts"]} == {"t1": (0.5, 1.5), "t2": (5.5, 6.0), "t3": (6.0, 7.0)}
    assert p["audio"][0]["start"] == 7.0
    # środek jednego klipu: dwa kawałki, przejście na drugim
    pr.stan["p"] = projekt()
    assert pr.main(["wytnij", pr.film, "--od", "2.0", "--do", "4.0"]) == 0
    cs = pr.stan["p"]["clips"]
    assert [(c["id"], c["in"], c["out"], "transition" in c) for c in cs] == [("a", 1.0, 3.0, False), ("n0", 5.0, 8.5, True), ("b", 0, 4, False)]
    with pytest.raises(SystemExit, match="pusty"):
        pr.main(["wytnij", pr.film, "--od", "3", "--do", "3"])


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_js_te_same_reguly_co_projekt(pr):
    """Edytor (podzielKlip, przytnijKlip) daje te same klipy co projekt.py tnij."""
    c = projekt()["clips"][0]
    js = node(f"""let k = 0; const c = {json.dumps(c)};
      const s = {{ c: {json.dumps(projekt()["clips"][1])}, start: 7.5, end: 9.5 }};
      console.log(JSON.stringify({{ trzy: podzielKlip(c, 3, () => 'n' + (k++)),
        lewo: przytnijKlip(s, 8.5, 'l'), prawo: przytnijKlip(s, 8.5, 'r'), poza: przytnijKlip(s, 9.47, 'r') }}));""")
    assert pr.main(["tnij", pr.film, "a", "--czesci", "3"]) == 0
    py = pr.stan["p"]["clips"][:3]
    assert [(x["id"], x["in"], x["out"], x.get("transition")) for x in js["trzy"]] == [(x["id"], x["in"], x["out"], x.get("transition")) for x in py]
    assert (js["lewo"]["in"], js["lewo"]["out"], js["prawo"]["in"], js["prawo"]["out"], js["poza"]) == (2.0, 4, 0, 2.0, None)
