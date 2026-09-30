"""Zakładka „Wiedza”: logika panelu (wiedza/plugin/dashboard/panel.py) bez FastAPI: przegląd, drzewo, notatka z linkami
w obie strony i historią, szukanie, skrzynka, dziennik, lint z pamięcią podręczną, orzeczenia (lista i dodanie),
uwaga do notatki jako szkic, reindeks, kompilacja jako osobny proces."""
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "wiedza"))
import wiedza as w  # noqa: E402

spec = importlib.util.spec_from_file_location("jarvo_wiedza_panel", REPO / "wiedza" / "plugin" / "dashboard" / "panel.py")
pm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pm)

GIT = shutil.which("git") is not None
FLEET = {"orchestrator": "jarvo", "agents": [
    {"name": "jarvo-web", "short": "Web", "title": "Web Senior Dev", "emoji": "🌐", "kind": "specialist", "description": "Strony i SEO.",
     "room": "devlab", "label": "Pracownia", "telegram_topic": "web", "autonomy_max": "A1", "skills": [], "scripts": []}]}


@pytest.fixture
def panel(tmp_path, monkeypatch):
    monkeypatch.setenv("WIEDZA_DZIS", "2026-09-30")
    root = tmp_path / "knowledge"
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps(FLEET, ensure_ascii=False), encoding="utf-8")
    assert w.main(["--skarbiec", str(root), "--stan", str(tmp_path / "state"), "zasiej", "--fleet", str(fleet)]) == 0
    sk = w.Skarbiec(root, tmp_path / "state")
    sk.zapisz_plik("pojecia/audyt strony", w.sklej({"typ": "pojecie", "tagi": ["web"], "utworzono": "2026-09-30", "zmieniono": "2026-09-30", "status": "aktualna", "zrodlo": "karta t_1"},
        "# Audyt strony\n\n**Audyt strony to Lighthouse, axe i linkinator.**\n\nSzczegóły w [[agenci/jarvo-web/_hub-web|Web]].\n\n## Powiązane\n- hub: [[pojecia/_hub-pojecia]]\n- [[nie/ma]]\n"))
    w.dodaj_orzeczenie(sk, "jarvo-web", "Nie używaj innerHTML", "test")
    w.main(["--skarbiec", str(root), "--stan", str(tmp_path / "state"), "indeksuj"])
    return pm.Panel(root, tmp_path / "state", repo=tmp_path / "repo")


def test_overview_tree_note_search(panel):
    ov = panel.overview()
    assert ov["notatek"] >= 14 and ov["wg_folderu"]["pojecia"] == 2 and ov["szkice"] == 0 and ov["git"] == GIT
    assert ov["lint"]["bledy"] == 1 and ov["dziennik"][0]["rodzaj"] in ("orzeczenie", "zasiew")
    tree = panel.tree()
    foldery = {f["folder"]: f for f in tree["foldery"]}
    assert foldery["pojecia"]["hub"]["sciezka"] == "pojecia/_hub-pojecia" and [n["sciezka"] for n in foldery["pojecia"]["notatki"]] == ["pojecia/audyt strony"]
    assert "zrodla" not in foldery and foldery["agenci"]["notatki"][0]["sciezka"] == "agenci/jarvo-web/_hub-web"
    n = panel.note("pojecia/audyt strony")
    assert n["tytul"] == "Audyt strony" and n["streszczenie"].startswith("Audyt strony to Lighthouse") and n["frontmatter"]["typ"] == "pojecie"
    wy = {l["cel"]: l for l in n["linki_wy"]}
    assert wy["agenci/jarvo-web/_hub-web"]["istnieje"] and wy["agenci/jarvo-web/_hub-web"]["tytul"].endswith("(jarvo-web)") and not wy["nie/ma"]["istnieje"]
    assert any(l["z"] == "pojecia/_hub-pojecia" and l["auto"] for l in n["linki_we"])
    assert n["zrodla"] == [{"tekst": "karta t_1", "sciezka": None}]
    assert (len(n["historia"]) >= 1) == GIT
    with pytest.raises(ValueError):
        panel.note("../../etc/passwd")
    with pytest.raises(FileNotFoundError):
        panel.note("pojecia/nie ma")
    assert panel.search("lighthouse axe")[0]["sciezka"] == "pojecia/audyt strony"
    assert panel.search("lighthouse", folder="agenci") == []
    g = panel.graph()
    assert any(n["id"] == "pojecia/audyt strony" for n in g["wezly"]) and any(l["z"] == "pojecia/audyt strony" for l in g["linki"])


def test_lint_cache_rulings_remark_inbox_log(panel, monkeypatch):
    r1 = panel.lint()
    assert r1["bledy"] == ["martwy link `[[nie/ma]]` w [[pojecia/audyt strony]]"]
    ts1 = panel._lint_cache[0]
    assert panel.lint() is r1 and panel._lint_cache[0] == ts1                    # 60 s pamięci podręcznej
    assert panel.lint(odswiez=True) is not r1
    pliki = {p["kogo"]: p for p in panel.rulings()}
    assert pliki["web"]["linie"][0].startswith("2026-09-30 · [web] Nie używaj innerHTML") and "wszyscy" in pliki
    r = panel.add_ruling("marki/Acme", "Przyciski zaokrąglone")
    assert r["orzeczenie"].startswith("- 2026-09-30 · [acme] Przyciski zaokrąglone. (źródło: człowiek, zakładka Wiedza)")
    assert "marki/acme" in {p["kogo"] for p in panel.rulings()}
    with pytest.raises(ValueError):
        panel.add_ruling("web", "x" * 500)
    s = panel.add_remark("pojecia/audyt strony", "Brakuje informacji o Lighthouse CI.")
    assert s["szkic"].startswith("skrzynka/2026-09-30-czlowiek-poprawka-audyt-strony-")
    with pytest.raises(ValueError):
        panel.add_remark("pojecia/audyt strony", "za")
    inbox = panel.inbox()
    assert len(inbox["szkice"]) == 1 and inbox["szkice"][0]["tytul"] == "Poprawka: Audyt strony" and "[[pojecia/audyt strony]]" in inbox["szkice"][0]["podglad"]
    assert inbox["szkice"][0]["agent"] == "czlowiek" and inbox["kompilacja"]["trwa"] is False
    log = panel.log(10)
    assert log[0]["rodzaj"] == "orzeczenie" and log[-1]["rodzaj"] == "zasiew" and log[0]["data"] == "2026-09-30"
    r = panel.reindex()
    assert r["pliki"] >= 15 and r["index"] >= 15


def test_compile_process(panel, tmp_path):
    assert panel.compile_command() is None
    assert panel.compile_start()["blad"].startswith("brak scripts/wiedza-kompiluj.sh")
    skrypt = tmp_path / "repo" / "scripts" / "wiedza-kompiluj.sh"
    skrypt.parent.mkdir(parents=True)
    skrypt.write_text('#!/usr/bin/env bash\necho "{\\"szkice\\": 1, \\"nowe\\": 1, \\"profil\\": \\"$JARVO_WIEDZA_PROFIL\\"}"\n', encoding="utf-8")
    os.chmod(skrypt, 0o755)
    r = panel.compile_start()
    assert r["trwa"] is True
    for _ in range(50):
        if not panel.compile_status()["trwa"]:
            break
        time.sleep(0.1)
    st = panel.compile_status()
    assert st["trwa"] is False and st["wynik"] == {"szkice": 1, "nowe": 1, "profil": "jarvo"} and st["blad"] == ""
    skrypt.write_text('#!/usr/bin/env bash\necho "zła odpowiedź" >&2; exit 3\n', encoding="utf-8")
    panel.compile_start()
    for _ in range(50):
        if not panel.compile_status()["trwa"]:
            break
        time.sleep(0.1)
    assert panel.compile_status()["blad"] == "zła odpowiedź"
