"""Rutyna „Świeżość wiedzy” bez modelu (profiles/jarvo/scripts/swiezosc.py) i rutyny Jarva w jobs.yaml."""

from __future__ import annotations

import fleetlib as fl
from conftest import load_script

sw = load_script("profiles/jarvo/scripts/swiezosc.py", "jarvo_swiezosc_test")


def skill(root, agent, name, reviewed, jarvo=True):
    d = root / "profiles" / agent / "skills" / "kat" / name
    d.mkdir(parents=True)
    meta = f"  jarvo:\n    agent: {agent}\n    reviewed: \"{reviewed}\"\n" if jarvo else f"  hermes:\n    reviewed: \"{reviewed}\"\n"
    (d / "SKILL.md").write_text(f"---\nname: {name}\nmetadata:\n{meta}---\n\n# {name}\n", encoding="utf-8")


def test_stare_skille_i_cisza(tmp_path, capsys):
    skill(tmp_path, "jarvo-web", "audyt", "2026-01-10")
    skill(tmp_path, "jarvo-web", "swiezy", "2026-09-01")
    skill(tmp_path, "jarvo-wideo", "obcy", "2025-01-01", jarvo=False)          # skill zewnętrzny: nie nasz
    sk = tmp_path / "knowledge"
    (sk / "pojecia").mkdir(parents=True)
    (sk / "pojecia" / "cennik.md").write_text("---\nstatus: aktualna\nwazne_do: 2026-09-30\n---\n# Cennik\n", encoding="utf-8")
    (sk / "pojecia" / "rynek.md").write_text("---\nstatus: do-sprawdzenia\n---\n# Rynek\n", encoding="utf-8")
    (sk / "pojecia" / "ok.md").write_text("---\nstatus: aktualna\nwazne_do: 2027-01-01\n---\n# Ok\n", encoding="utf-8")
    assert sw.main(["--build", str(tmp_path), "--skarbiec", str(sk), "--dzis", "2026-10-02"]) == 0
    out = capsys.readouterr().out
    assert "2 notatek do przejrzenia" in out and "pojecia/cennik (ważna do 2026-09-30)" in out
    assert "pojecia/rynek (do sprawdzenia)" in out and "pojecia/ok" not in out
    assert "1 skilli do przejrzenia" in out and "jarvo-web/audyt: 2026-01-10 (265 dni)" in out and "obcy" not in out
    assert sw.main(["--build", str(tmp_path), "--skarbiec", str(tmp_path / "brak"), "--dzis", "2026-03-01"]) == 0
    assert capsys.readouterr().out == ""                                       # nic starego = puste wyjście = cisza


def test_jeden_prog_i_rutyny_bez_zbednego_modelu():
    assert sw.SWIEZOSC_DNI == fl.SWIEZOSC_DNI
    jobs = {j["id"]: j for j in fl.load_yaml(fl.PROFILES_DIR / "jarvo" / "cron" / "jobs.yaml")["jobs"]}
    assert jobs["jarvo-knowledge-freshness"]["no_agent"] is True and "prompt" not in jobs["jarvo-knowledge-freshness"]
    assert jobs["jarvo-patrol"]["reasoning_effort"] == jobs["jarvo-daily-brief"]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in jobs["jarvo-weekly-review"] and not any("model" in j for j in jobs.values())
