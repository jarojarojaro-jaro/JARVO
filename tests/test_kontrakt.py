"""Linter kontraktu karty (profiles/jarvo/scripts/kontrakt.py): sekcje zlecenia i kształt przekazania."""

from __future__ import annotations

import json

from conftest import load_script

k = load_script("profiles/jarvo/scripts/kontrakt.py", "jarvo_kontrakt_test")

BODY = """**CEL:** Landing dla kawiarni
**KONTEKST:** właściciel chce zapisów na degustację
**WEJŚCIA:** brand kit w brands/kawa/
**DoD:**
1. Lighthouse mobile >= 90
2. zrzuty 375 i 1440 px
**WYJŚCIA:** out/index.html
**GRANICE:** A1, bez publikacji
"""


def show(tmp_path, dod_check, artifacts=("out/index.html",), body=BODY, extra=None):
    (tmp_path / "out").mkdir(exist_ok=True)
    (tmp_path / "out" / "index.html").write_text("x", encoding="utf-8")
    meta = {"artifacts": list(artifacts), "dod_check": dod_check, "risks": [], "decisions_needed": [], **(extra or {})}
    return {"task": {"id": "t_1", "body": body, "workspace_path": str(tmp_path)},
            "runs": [{"outcome": "review_requested", "metadata": meta}]}


def test_dobre_przekazanie(tmp_path):
    w = k.sprawdz(show(tmp_path, {"1": "spełniony: lighthouse mobile 93 (lighthouse --preset=mobile)",
                                  "2": "spełniony: out/zrzuty/375.png i 1440.png, bez przewijania w poziomie"}))
    assert w == {"id": "t_1", "dod_punktow": 2, "braki": [], "ok": True}


def test_braki_przekazania(tmp_path):
    w = k.sprawdz(show(tmp_path, ["spełniony: OK"], artifacts=("out/index.html", "out/brak.png"),
                       extra={"decisions_needed": None}))
    assert "artefakt nie istnieje: out/brak.png" in w["braki"]
    assert "dod_check ma 1 punktów, DoD karty 2" in w["braki"]
    assert any("punkt 1: bez dowodu" in b for b in w["braki"])
    w = k.sprawdz(show(tmp_path, [{"punkt": 1, "wynik": "działa"}, "niesprawdzony: brak wdrożenia (A2)"]))
    assert any("punkt 1: bez stanu" in b for b in w["braki"]) and any("punkt 1: bez dowodu" in b for b in w["braki"])
    assert not any("punkt 2" in b for b in w["braki"])                     # niesprawdzony z powodem to uczciwy stan


def test_karta_bez_sekcji_i_bez_przekazania(tmp_path):
    s = show(tmp_path, {})
    s["task"]["body"] = "Zrób landing, szybko."
    s["runs"] = []
    w = k.sprawdz(s)
    assert "karta bez sekcji DoD" in w["braki"] and "brak przekazania do recenzji (kanban_request_review)" in w["braki"]


def test_cli_z_pliku(tmp_path, capsys):
    f = tmp_path / "show.json"
    f.write_text(json.dumps(show(tmp_path, {"1": "spełniony: 93", "2": "OK"})), encoding="utf-8")
    assert k.main(["--plik", str(f)]) == 1
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0].startswith("✗ kontrakt karty t_1") and json.loads(out[-1])["ok"] is False
    assert k.main(["--plik", str(tmp_path / "nie-ma.json")]) == 2
