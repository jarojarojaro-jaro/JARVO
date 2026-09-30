"""Odcisk wersji plików dla zgód A2: stały dla tej samej treści, zmienia się po każdej poprawce."""

from __future__ import annotations

from conftest import load_script

O = load_script("scripts/odcisk.py")


def test_fingerprint_is_stable_and_detects_changes(tmp_path, capsys):
    paczka = tmp_path / "do-publikacji"
    (paczka / "grafiki").mkdir(parents=True)
    (paczka / "post-1.txt").write_text("Nowa kawa z Etiopii.", encoding="utf-8")
    (paczka / "grafiki" / "post-1.png").write_bytes(b"\x89PNG-1")
    (paczka / ".DS_Store").write_bytes(b"x")                      # pliki systemowe nie zmieniają odcisku
    kal = tmp_path / "kalendarz.csv"
    kal.write_text("data,post\n2026-10-03,1\n", encoding="utf-8")
    odc, n = O.odcisk([paczka, kal])
    assert len(odc) == 12 and n == 3
    assert O.odcisk([paczka, kal]) == (odc, 3)
    assert O.main([str(paczka), str(kal), "--sprawdz", odc]) == 0 and "zgodny" in capsys.readouterr().out
    (paczka / "post-1.txt").write_text("Nowa kawa z Etiopii!", encoding="utf-8")   # poprawka po zgodzie
    assert O.odcisk([paczka, kal])[0] != odc
    assert O.main([str(paczka), str(kal), "--sprawdz", odc]) == 1 and "nowa zgoda" in capsys.readouterr().out
    (paczka / "post-1.txt").write_text("Nowa kawa z Etiopii.", encoding="utf-8")
    (paczka / "post-1.txt").rename(paczka / "post-2.txt")                          # ta sama treść, inna nazwa
    assert O.odcisk([paczka, kal])[0] != odc
