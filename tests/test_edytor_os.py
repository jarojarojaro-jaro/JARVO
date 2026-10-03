"""Oś magnetyczna edytora: po zmianie klipów napisy, uwagi, audio i bloki typografii (z każdym słowem) idą za materiałem.
Ta sama reguła w przeglądarce (remapTimes w 45-edytor.js) i u agenta (edytor.remap_times w projekt.py); testy sprawdzają
obie na tych samych przypadkach."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from conftest import REPO, load_script

ed = load_script("hq/plugin/edytor.py", "jarvo_edytor_os_test")
JS = (REPO / "hq" / "web" / "src" / "45-edytor.js").read_text(encoding="utf-8")


def klip(id_, a, b, src="f.mp4", speed=1):
    return {"id": id_, "src": src, "in": a, "out": b, "speed": speed}


# trzy klipy po 10 s; napis i uwaga w drugim klipie (12–14 s), muzyka od 25 s (w trzecim), napis w trzecim (22–24 s)
P0 = {"clips": [klip("a", 0, 10), klip("b", 10, 20), klip("c", 20, 30)],
      "texts": [{"id": "t1", "start": 12, "end": 14}, {"id": "t2", "start": 22, "end": 24}, {"id": "t0", "start": 2, "end": 4}],
      "audio": [{"id": "m", "start": 25, "in": 0, "out": 5}, {"id": "tlo", "start": 0, "in": 0, "out": 30}],
      "notes": [{"id": "n", "t": 13}],
      # typografia: blok w drugim klipie (słowa 12 s i 13,2 s) i w trzecim; czas słowa liczony od początku bloku
      "typo": {"motyw": "kino", "bloki": [
          {"id": "y1", "start": 12, "end": 14, "slowa": [{"t": 0, "k": 0.5, "tekst": "raz"}, {"t": 1.2, "k": 1.6, "tekst": "dwa"}]},
          {"id": "y2", "start": 22, "end": 24, "slowa": [{"t": 0.5, "k": 1, "tekst": "trzy"}]}]}}


def zmien(clips):
    return {**P0, "clips": clips}


PRZYPADKI = {
    # usunięcie środkowego klipu: napis z niego znika, reszta dosuwa się o 10 s, muzyka tła stoi
    "usun_srodek": (zmien([klip("a", 0, 10), klip("c", 20, 30)]),
                    {"t0": (2, 4), "t2": (12, 14)}, {"m": 15, "tlo": 0}, {"n": 10},
                    {"y2": (12, 14, [0.5], [1])}),
    # przycięcie końca pierwszego klipu o 4 s: wszystko za nim wcześniej o 4 s
    "przytnij_koniec": (zmien([klip("a", 0, 6), klip("b", 10, 20), klip("c", 20, 30)]),
                        {"t0": (2, 4), "t1": (8, 10), "t2": (18, 20)}, {"m": 21, "tlo": 0}, {"n": 9},
                    {"y1": (8, 10, [0, 1.2], [0.5, 1.6]), "y2": (18, 20, [0.5], [1])}),
    # przycięcie początku drugiego klipu o 3 s: napis z 12–14 s (źródło 12–14) ląduje na 10–11 (13 s źródła wycięte do 12)
    "przytnij_poczatek": (zmien([klip("a", 0, 10), klip("b", 13, 20), klip("c", 20, 30)]),
                          {"t0": (2, 4), "t1": (10, 11), "t2": (19, 21)}, {"m": 22, "tlo": 0}, {"n": 10},
                    {"y1": (10, 11, [0, 0.2], [0, 0.6]), "y2": (19, 21, [0.5], [1])}),
    # wstawienie 5-sekundowego klipu między a i b: reszta później o 5 s
    "wstaw": (zmien([klip("a", 0, 10), klip("x", 0, 5, src="inny.mp4"), klip("b", 10, 20), klip("c", 20, 30)]),
              {"t0": (2, 4), "t1": (17, 19), "t2": (27, 29)}, {"m": 30, "tlo": 0}, {"n": 18},
                    {"y1": (17, 19, [0, 1.2], [0.5, 1.6]), "y2": (27, 29, [0.5], [1])}),
    # tempo 2× na drugim klipie: napis w nim dwa razy bliżej, reszta wcześniej o 5 s
    "tempo": (zmien([klip("a", 0, 10), klip("b", 10, 20, speed=2), klip("c", 20, 30)]),
              {"t0": (2, 4), "t1": (11, 12), "t2": (17, 19)}, {"m": 20, "tlo": 0}, {"n": 11.5},
                    {"y1": (11, 12, [0, 0.6], [0.25, 0.8]), "y2": (17, 19, [0.5], [1])}),
    # przestawienie: c na początek; napisy jadą z klipami, audio stoi
    "przestaw": (zmien([klip("c", 20, 30), klip("a", 0, 10), klip("b", 10, 20)]),
                 {"t0": (12, 14), "t1": (22, 24), "t2": (2, 4)}, {"m": 25, "tlo": 0}, {"n": 23},
                    {"y1": (22, 24, [0, 1.2], [0.5, 1.6]), "y2": (2, 4, [0.5], [1])}),
    # podział b na dwa: nic się nie przesuwa
    "podziel": (zmien([klip("a", 0, 10), klip("b", 10, 15), klip("b2", 15, 20), klip("c", 20, 30)]),
                {"t0": (2, 4), "t1": (12, 14), "t2": (22, 24)}, {"m": 25, "tlo": 0}, {"n": 13},
                    {"y1": (12, 14, [0, 1.2], [0.5, 1.6]), "y2": (22, 24, [0.5], [1])}),
}


def sprawdz(wynik, teksty, audio, uwagi, typo):
    assert {x["id"]: (x["start"], x["end"]) for x in wynik["texts"]} == teksty
    assert {m["id"]: m["start"] for m in wynik["audio"]} == audio
    assert {n["id"]: n["t"] for n in wynik["notes"]} == uwagi
    assert {b["id"]: (b["start"], b["end"], [w["t"] for w in b["slowa"]], [w["k"] for w in b["slowa"]])
            for b in wynik["typo"]["bloki"]} == typo
    assert wynik["typo"]["motyw"] == "kino"


@pytest.mark.parametrize("nazwa", sorted(PRZYPADKI))
def test_os_magnetyczna_python(nazwa):
    p1, teksty, audio, uwagi, typo = PRZYPADKI[nazwa]
    sprawdz(ed.remap_times(P0, p1), teksty, audio, uwagi, typo)


def test_os_magnetyczna_przegladarka_tak_samo():
    if not shutil.which("node"):
        pytest.skip("brak node")
    fn = lambda name: re.search(rf"^function {name}\(.*?^}}", JS, re.S | re.M).group(0)
    prog = (re.search(r"^const clipDur = .*$", JS, re.M).group(0) + "\n" + fn("layoutClips") + "\n" + fn("remapTimes") + "\n"
            + fn("typoNaOsi") + "\n" + fn("typoPrzesun") + "\n"
            + f"const P0 = {json.dumps(P0)};\nconst C = {json.dumps({k: v[0] for k, v in PRZYPADKI.items()})};\n"
            + "const out = {}; for (const k in C) out[k] = remapTimes(P0, C[k]);\nconsole.log(JSON.stringify(out));")
    wyniki = json.loads(subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True).stdout)
    for nazwa, (_p1, teksty, audio, uwagi, typo) in PRZYPADKI.items():
        sprawdz(wyniki[nazwa], teksty, audio, uwagi, typo)


def test_projekt_usun_i_wstaw_dosuwaja_os(tmp_path, monkeypatch):
    """Agent (projekt.py usun / dodaj-klip --pozycja) przesuwa napisy tak samo jak edytor."""
    pr = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_os_test")
    film = tmp_path / "film.mp4"
    film.write_bytes(b"x")
    zapis = {}
    monkeypatch.setattr(pr, "load", lambda f: json.loads(json.dumps(P0)))
    monkeypatch.setattr(pr, "save", lambda f, p: zapis.update(p=p))
    pr.cmd_usun(film, type("A", (), {"id": "b"})())
    sprawdz(zapis["p"], *PRZYPADKI["usun_srodek"][1:])
