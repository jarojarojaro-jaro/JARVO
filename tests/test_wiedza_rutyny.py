"""Rutyny Jarva natywnie (docs/NATYWNIE.md H06, F01): skrypty rutyn (patrol, brief, przegląd, świeżość i to, co
importują) biorą katalogi z HERMES_HOME i JARVO_*_DIR (profiles/jarvo/scripts/_sciezki.py), a nie z /opt; patrol
zgłasza brak dziennika misji. Cron Hermesa uruchamia skrypt z HERMES_HOME profilu, więc tak też je tu wołamy
(katalog danych ze spacją i polskimi znakami, jak u właściciela)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import atrapy
from conftest import REPO, load_script

sc = load_script("profiles/jarvo/scripts/_sciezki.py", "jarvo_sciezki_e7")
patrol = load_script("profiles/jarvo/scripts/patrol.py", "jarvo_patrol_e7")
lekcje = load_script("profiles/jarvo/scripts/lekcje.py", "jarvo_lekcje_e7")
liczby = load_script("profiles/jarvo/scripts/liczby.py", "jarvo_liczby_e7")
raport = load_script("profiles/jarvo/scripts/raport_strona.py", "jarvo_raport_e7")
SKRYPTY = REPO / "profiles" / "jarvo" / "scripts"
ZMIENNE = ("HERMES_HOME", "JARVO_DATA_DIR", "JARVO_MISSIONS_DIR", "JARVO_STATE_DIR", "JARVO_KNOWLEDGE_DIR",
           "JARVO_BUILD_DIR", "JARVO_HERMES_BIN", "JARVO_PATROL_STATE", "JARVO_RAPORTY_DIR")


@pytest.fixture
def czyste(monkeypatch):
    for z in ZMIENNE:
        monkeypatch.delenv(z, raising=False)


@pytest.fixture
def instalacja(tmp_path):
    """Układ natywny z c1: <root>/dane (HERMES_HOME) z profilem jarvo i <root>/build obok."""
    root = tmp_path / "Michał Żółć" / "Jarvo"
    dane = root / "dane"
    (dane / "profiles" / "jarvo").mkdir(parents=True)
    (root / "build").mkdir()
    return root, dane


def test_katalogi_z_hermes_home_profilu(czyste, monkeypatch, instalacja, tmp_path):
    root, dane = instalacja
    monkeypatch.setenv("HERMES_HOME", str(dane / "profiles" / "jarvo"))
    assert sc.dane() == dane and sc.jarvo() == dane / "jarvo"
    assert (sc.misje(), sc.stan(), sc.skarbiec()) == (dane / "jarvo" / "missions", dane / "jarvo" / "state",
                                                     dane / "jarvo" / "knowledge")
    assert sc.build() == root / "build"
    monkeypatch.setenv("HERMES_HOME", str(dane))                          # brama i panel: HERMES_HOME = <dane>
    assert sc.dane() == dane and sc.misje() == dane / "jarvo" / "missions"
    # JARVO_DATA_DIR to <dane>/jarvo (jarvo/srodowisko.py, HQ), a nie <dane>: dawniej liczby.py i poczekalnia.py
    # szukały wtedy <dane>/jarvo/kanban.db, a lekcje.py <dane>/jarvo/jarvo/knowledge
    monkeypatch.delenv("HERMES_HOME")
    monkeypatch.setenv("JARVO_DATA_DIR", str(dane / "jarvo"))
    assert sc.dane() == dane and sc.jarvo() == dane / "jarvo"
    assert liczby.dane_domyslne() == dane
    assert lekcje.domyslne() == (dane / "jarvo" / "knowledge" / "fleet" / "lekcje.md",
                                 dane / "jarvo" / "evals" / "historia.jsonl")
    assert raport.katalog_raportow() == dane / "jarvo" / "workspaces" / "jarvo" / "raporty"
    for zmienna, funkcja in (("JARVO_MISSIONS_DIR", sc.misje), ("JARVO_STATE_DIR", sc.stan),
                             ("JARVO_KNOWLEDGE_DIR", sc.skarbiec), ("JARVO_BUILD_DIR", sc.build)):
        monkeypatch.setenv(zmienna, str(tmp_path / zmienna))
        assert funkcja() == tmp_path / zmienna                            # jawne zmienne instalacji wygrywają


def test_bez_zmiennych_uklad_kontenera(czyste):
    assert sc.dane() == Path("/opt/data") and sc.misje() == Path("/opt/data/jarvo/missions")
    assert sc.build() == Path("/opt/jarvo/build")


def test_hermes_pelna_sciezka(czyste, monkeypatch, tmp_path):
    """JARVO_HERMES_BIN (natywnie `<checkout>/.venv/Scripts/hermes.exe`) albo `hermes` z PATH pełną ścieżką: na
    Windows nakładka bywa plikiem .cmd, którego CreateProcess nie znajdzie po samej nazwie."""
    prog = atrapy.program(tmp_path / "bin", "hermes", "print('x')")
    monkeypatch.setenv("PATH", atrapy.sciezka(tmp_path / "bin"))
    assert Path(sc.hermes()).resolve() == prog.resolve()
    monkeypatch.setenv("JARVO_HERMES_BIN", str(prog))
    assert Path(sc.hermes()).resolve() == prog.resolve()


ATRAPA_HERMESA = """import json, sys
args = sys.argv[1:]
if args[:2] == ["kanban", "list"]:
    print("[]")
elif args[:2] == ["kanban", "diagnostics"]:
    print("[]")
else:
    print("{}")
"""


def _env(dane: Path, **extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ZMIENNE}
    env.update(HERMES_HOME=str(dane / "profiles" / "jarvo"), PYTHONUTF8="1", **extra)
    return env


def test_patrol_z_hermes_home_i_brak_dziennika_misji(instalacja, tmp_path):
    """Patrol jak z crona (tylko HERMES_HOME profilu): stan w <dane>/jarvo/state/patrol.json (nie /opt), a brak
    <misje>/INDEX.md budzi Jarva raz (dawniej patrol bez dziennika milczał); z dziennikiem cisza."""
    root, dane = instalacja
    hermes = atrapy.program(tmp_path / "bin", "hermes", ATRAPA_HERMESA)
    env = _env(dane, JARVO_HERMES_BIN=str(hermes))
    r = subprocess.run([sys.executable, str(SKRYPTY / "patrol.py")], env=env, capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    ostatnia = json.loads(r.stdout.strip().splitlines()[-1])
    assert ostatnia["wakeAgent"] is True
    assert ostatnia["context"]["anomalies"][0]["kind"] == "mission_index_missing"
    assert "Brak dziennika misji" in r.stdout and (dane / "jarvo" / "missions" / "INDEX.md").as_posix() in r.stdout
    stan = dane / "jarvo" / "state" / "patrol.json"
    assert "mission_index_missing" in json.loads(stan.read_text(encoding="utf-8"))
    r = subprocess.run([sys.executable, str(SKRYPTY / "patrol.py")], env=env, capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert json.loads(r.stdout.strip().splitlines()[-1]) == {"wakeAgent": False}      # ta sama anomalia: raz na 12 h
    (dane / "jarvo" / "missions").mkdir(parents=True)
    (dane / "jarvo" / "missions" / "INDEX.md").write_text("# Misje\n\n## Aktywne\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SKRYPTY / "patrol.py")], env=env, capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert json.loads(r.stdout.strip().splitlines()[-1]) == {"wakeAgent": False}
    assert "mission_index_missing" not in json.loads(stan.read_text(encoding="utf-8"))  # rozwiązane: zapomniane


def test_patrol_fixture_bez_indeksu_bez_alarmu():
    """Dane testowe bez pola index_brak (brak misji to nie brak dziennika): bez nowej anomalii."""
    assert not [a for a in patrol.analyze({"tasks": [], "index": ""}, 0.0) if a["kind"] == "mission_index_missing"]


def test_swiezosc_z_katalogow_instalacji(instalacja):
    """Rutyna bez modelu: build obok <dane> (natywnie <root>/build) i skarbiec <dane>/jarvo/knowledge, bez /opt."""
    root, dane = instalacja
    skill = root / "build" / "profiles" / "jarvo" / "skills" / "stary" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: stary\nmetadata:\n  jarvo:\n    reviewed: 2026-01-01\n---\n# Stary\n", encoding="utf-8")
    notatka = dane / "jarvo" / "knowledge" / "pojecia" / "cena żółtego.md"
    notatka.parent.mkdir(parents=True)
    notatka.write_text("---\ntyp: fakt\nwazne_do: 2026-02-01\n---\n# Cena\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SKRYPTY / "swiezosc.py"), "--dzis", "2026-10-25"], env=_env(dane),
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert "jarvo/stary: 2026-01-01" in r.stdout and "pojecia/cena żółtego (ważna do 2026-02-01)" in r.stdout


def test_brief_i_przeglad_z_hermes_home(instalacja, tmp_path):
    """Brief i przegląd tygodnia (fleet_report.py z lekcje, liczby, poczekalnia, raport_strona) jak z crona: tylko
    HERMES_HOME profilu i atrapa hermesa; kończą się JSON-em dla schedulera, a niczego nie piszą poza <dane>."""
    root, dane = instalacja
    hermes = atrapy.program(tmp_path / "bin", "hermes", ATRAPA_HERMESA)
    for skrypt in ("brief_daily.py", "review_weekly.py"):
        r = subprocess.run([sys.executable, str(SKRYPTY / skrypt)], env=_env(dane, JARVO_HERMES_BIN=str(hermes)),
                           capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=str(tmp_path))
        assert r.returncode == 0, r.stderr
        assert "wakeAgent" in json.loads(r.stdout.strip().splitlines()[-1])
        assert "/opt/" not in r.stdout and "\\opt\\" not in r.stdout
