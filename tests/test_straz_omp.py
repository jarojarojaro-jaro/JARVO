"""Straż sesji omp (jarvo/straz_omp.py): koniec pliku sesji po zapomnianym drugim procesie omp (28.11)."""
from __future__ import annotations

import json

from jarvo import straz_omp as so


def _wpis(i, rodzic, typ="message", wersja="19.2.1", **reszta):
    return {"type": typ, "id": i, "parentId": rodzic, "timestamp": f"2026-11-{10 + len(i) % 9}T10:00:00.000Z",
            "runtime": {"version": wersja}, **reszta}


def _wyjscie(i, rodzic, kind="signal", wersja="19.2.1"):
    return {"type": "custom", "customType": "session_exit", "data": {"reason": "sighup", "kind": kind},
            "id": i, "parentId": rodzic, "timestamp": "2026-11-28T13:58:05.622Z", "runtime": {"version": wersja}}


def _plik(tmp_path, wpisy):
    p = tmp_path / "2026-11-15T13-42-44-107Z_01a1df72-2c8b-76c1-99d5-f4865d11da9b.jsonl"
    linie = [{"type": "title", "title": "x"}, {"type": "session", "version": 3, "id": "01a1df72-2c8b-76c1-99d5-f4865d11da9b"}]
    p.write_text("".join(json.dumps(x, separators=(",", ":")) + "\n" for x in linie + wpisy), encoding="utf-8")
    return p


def _rozmowa():
    return [_wpis("aaaaaaa1", None, message={"role": "user"}), _wpis("aaaaaaa2", "aaaaaaa1"),
            _wpis("aaaaaaa3", "aaaaaaa2"), {"type": "model_usage", "id": "aaaaaaa4", "parentId": "aaaaaaa3"},
            _wyjscie("aaaaaaa5", "aaaaaaa4")]


def test_stary_proces_przestawil_koniec_i_naprawa_wraca_do_najnowszej(tmp_path):
    p = _plik(tmp_path, _rozmowa() + [_wyjscie("bbbbbbb1", "aaaaaaa1", wersja="18.22.0")])
    przed = p.read_bytes()
    k = so.koniec(p)
    assert not k["ok"] and k["lisc"] == "bbbbbbb1" and k["najnowsza"] == "aaaaaaa3" and k["cel"] == "aaaaaaa5"
    r = so.napraw(p)
    assert r["naprawiono"] and p.read_bytes().startswith(przed)
    ostatni = json.loads(p.read_text(encoding="utf-8").splitlines()[-1])
    assert ostatni["parentId"] == "aaaaaaa5" and ostatni["type"] == "custom" and ostatni["customType"] == so.TYP_NAPRAWY
    assert so.koniec(p)["ok"] and not so.napraw(p)["naprawiono"]


def test_zwykle_wyjscie_starszej_wersji_tez_naprawia(tmp_path):
    p = _plik(tmp_path, _rozmowa() + [_wyjscie("bbbbbbb1", "aaaaaaa2", kind="normal", wersja="18.22.0")])
    assert so.koniec(p)["cel"] == "aaaaaaa5"


def test_swiadome_tree_i_zwykle_wyjscie_zostaje(tmp_path):
    """Właściciel cofnął się /tree i wyszedł: tej samej wersji zwykłe wyjście ze starszego punktu to jego wybór."""
    p = _plik(tmp_path, _rozmowa() + [_wyjscie("bbbbbbb1", "aaaaaaa1", kind="normal")])
    przed = p.read_bytes()
    assert so.koniec(p)["ok"] and not so.napraw(p)["naprawiono"] and p.read_bytes() == przed


def test_poprawny_koniec_i_nowa_wiadomosc_na_innej_galezi(tmp_path):
    assert so.koniec(_plik(tmp_path, _rozmowa()))["ok"]
    galaz = _rozmowa() + [_wpis("ccccccc1", "aaaaaaa1"), _wyjscie("ccccccc2", "ccccccc1")]
    (tmp_path / "b").mkdir()
    assert so.koniec(_plik(tmp_path / "b", galaz))["ok"]


def test_powrot_do_punktu_ostatniego_procesu_a_nie_do_ostatniej_wiadomosci(tmp_path):
    """28.11 (próba na kopii): wznowienie na złej gałęzi dopisało tam streszczenie, potem świadomy powrót (/tree)
    na dobrą gałąź i dopiero wyjście starego procesu. Cel = punkt powrotu, nie zła gałąź z nowszą wiadomością."""
    p = _plik(tmp_path, _rozmowa() + [_wpis("ddddddd1", "aaaaaaa1"), _wyjscie("ddddddd2", "aaaaaaa5", kind="normal"),
                                      _wyjscie("ddddddd3", "aaaaaaa1")])
    assert so.koniec(p)["cel"] == "ddddddd2"


def test_przy_restarcie_prawdziwy_proces_wyszedl_po_starym(tmp_path):
    p = _plik(tmp_path, _rozmowa()[:4] + [_wyjscie("bbbbbbb1", "aaaaaaa1", wersja="18.22.0"),
                                           _wyjscie("aaaaaaa5", "aaaaaaa4")])
    assert so.koniec(p)["ok"]


def test_terminal_i_argumenty_procesu():
    assert so.pts(34816) == 0 and so.pts(34817) == 1 and so.pts(1025) is None
    plik = "/x/2026-11-15T13-42-44-107Z_01a1df72-2c8b-76c1-99d5-f4865d11da9b.jsonl"
    assert so.sesja_z_argumentow(["omp", "--session-dir", "/s", "--resume", plik]) == plik
    assert so.id_sesji(plik) == "01a1df72-2c8b-76c1-99d5-f4865d11da9b"
    assert so.id_sesji(so.sesja_z_argumentow(["omp", "--resume=01a1df72"])) == "01a1df72"
    assert so.procesy_sesji("01a1df72", [{"pid": 1, "id": "01a1df72-2c8b-76c1-99d5-f4865d11da9b"},
                                         {"pid": 2, "id": None}, {"pid": 3, "id": "01a2227b"}]) == \
        [{"pid": 1, "id": "01a1df72-2c8b-76c1-99d5-f4865d11da9b"}]
