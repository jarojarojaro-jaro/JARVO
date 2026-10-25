"""Zakładka „Wiedza”: logika panelu (wiedza/plugin/dashboard/panel.py) bez FastAPI: przegląd, drzewo, notatka z linkami
w obie strony i historią, szukanie, skrzynka, dziennik, lint z pamięcią podręczną, orzeczenia (lista i dodanie),
uwaga do notatki jako szkic, reindeks, kompilacja jako osobny proces (kompilacja.py Pythonem dashboardu, bez basha)."""
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
    assert ov["skarbiec"] == panel.sk.root.as_posix()                           # ścieżka dla UI zawsze z „/”
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
    assert panel.recall_log() == []
    (panel.sk.stan / "wiedza-przypomnienia.jsonl").write_text('{"agent": "jarvo-web", "notatki": ["pojecia/audyt strony"]}\nzepsuta linia\n{"agent": "jarvo"}\n', encoding="utf-8")
    assert [w["agent"] for w in panel.recall_log()] == ["jarvo", "jarvo-web"]


def _czekaj_na_kompilacje(panel) -> dict:
    for _ in range(300):
        if not panel.compile_status()["trwa"]:
            break
        time.sleep(0.1)
    return panel.compile_status()


def test_historia_notatki_z_polskimi_znakami(panel):
    """Historia notatki z gita dekodowana w UTF-8 (dawniej błąd 500 na „Ł” przy kodowaniu cp1250 na Windows)."""
    if not GIT:
        pytest.skip("brak git")
    w.dodaj_orzeczenie(panel.sk, "marki/Łódź Żółć", "Logo zawsze na białym tle", "test")
    historia = panel.note("orzeczenia/marki/łódź-żółć")["historia"]
    assert historia[0]["opis"] == "orzeczenie: łódź żółć" and len(historia) == 1


# atrapa Hermesa dla procesu kompilacji: agent.auxiliary_client.call_llm sprawdza profil i odrzuca szkic
ATRAPA_HERMESA = """import json, os
def call_llm(task, messages, max_tokens, temperature):
    assert task == "jarvo_wiedza", task
    assert os.path.basename(os.environ["HERMES_HOME"]) == "jarvo", os.environ["HERMES_HOME"]
    return {"choices": [{"message": {"content": json.dumps({"wyniki": [{"decyzja": "odrzuc", "powod": "atrapa"}]})}}]}
"""


def test_compile_process(panel, tmp_path, monkeypatch):
    """Przycisk na każdym systemie (także w kontenerze): kompilacja.py Pythonem dashboardu (venv Hermesa) w trybie
    izolowanym, bez basha (na Windows bash z Pythona to WSL), z HERMES_HOME profilu jarvo, w katalogu Hermesa
    i z wyjściem w UTF-8; wynik to cały JSON z --json. Skrypt kontenera obok niczego nie zmienia."""
    skrypt = tmp_path / "repo" / "scripts" / "wiedza-kompiluj.sh"
    skrypt.parent.mkdir(parents=True)
    skrypt.write_text("exit 99\n", encoding="utf-8")
    (tmp_path / "dane" / "profiles" / "jarvo").mkdir(parents=True)
    p = pm.Panel(panel.sk.root, panel.sk.stan, repo=tmp_path / "repo", dane=tmp_path / "dane")
    cmd = p.compile_command()
    assert cmd[:4] == [sys.executable, "-I", "-X", "utf8"] and Path(cmd[4]).name == "kompilacja.py" and "--json" in cmd
    assert cmd[cmd.index("--profil") + 1] == "jarvo" and cmd[cmd.index("--skarbiec") + 1] == str(p.sk.root)
    assert not [x for x in cmd if "bash" in x.lower() or x.endswith(".sh")]
    hermes = tmp_path / "hermes"
    (hermes / "agent").mkdir(parents=True)
    (hermes / "agent" / "__init__.py").write_text("", encoding="utf-8")
    (hermes / "agent" / "auxiliary_client.py").write_text(ATRAPA_HERMESA, encoding="utf-8")
    monkeypatch.setenv("HERMES_SRC", str(hermes))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "dane"))
    assert p._srodowisko_kompilacji()["HERMES_HOME"] == str(tmp_path / "dane" / "profiles" / "jarvo")
    assert p._katalog_kompilacji() == str(hermes)
    w.zapisz_szkic(p.sk, "fakt", "Fakt z zakładki", "Treść faktu do kompilacji.", "karta t_1", "jarvo-web")
    assert p.compile_start()["trwa"] is True
    st = _czekaj_na_kompilacje(p)
    assert st["blad"] == "" and st["wynik"]["szkice"] == 1 and st["wynik"]["odrzucone"] == 1 and st["wynik"]["bledy"] == 0
    assert st["wynik"]["lint"]["bledy"] == 1 and not list((p.sk.root / "skrzynka").glob("*.md"))   # martwy [[nie/ma]]
    w.zapisz_szkic(p.sk, "fakt", "Drugi fakt", "Treść drugiego faktu.", "karta t_2", "jarvo-web")
    monkeypatch.setenv("HERMES_SRC", str(tmp_path / "nie-ma"))               # bez Hermesa: komunikat z ogonkami w UTF-8
    p.compile_start()
    assert "brak dostępu do modelu Hermesa" in _czekaj_na_kompilacje(p)["blad"]
    blok = w.Blokada(p.sk.stan)                                              # inna kompilacja trwa: raport „zablokowana”
    assert blok.wez()
    try:
        monkeypatch.setenv("HERMES_SRC", str(hermes))
        p.compile_start()
        st = _czekaj_na_kompilacje(p)
        assert st["wynik"]["zablokowana"] is True and st["blad"].startswith("skarbiec zajęty (")
    finally:
        blok.zwolnij()
    monkeypatch.setattr(p, "_kompilacja_py", lambda: None)                    # wtyczka bez kompilacja.py obok wiedza.py
    assert p.compile_command() is None and p.compile_start()["blad"] == "brak kompilacja.py obok wiedza.py"
