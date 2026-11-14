"""`scripts/new-agent.py --marka`: agent biznesowy jednym poleceniem (docs/FLEET.md „Agenci biznesowi”). Szkielet
idzie do kopii repo w katalogu tymczasowym (skrypt liczy ścieżki od swojego położenia), więc repo zostaje nietknięte."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import fleetlib as fl
import pytest

REPO = Path(__file__).resolve().parents[1]

# po przełączeniu na active: czego walidator wymaga od profilu, rutyny, evals i wpisu z marką
SPRAWDZ = r"""
import json, sys
sys.path.insert(0, "scripts")
import fleetlib as fl, validate as v
t = fl.FLEET_FILE.read_text(encoding="utf-8")
i = t.index("name: jarvo-kwiaty")
j = t.index("status: planned", i)
fl.FLEET_FILE.write_text(t[:j] + "status: active" + t[j + len("status: planned"):], encoding="utf-8")
f = fl.load_fleet()
a = next(x for x in f.agents if x.name == "jarvo-kwiaty")
proto = (fl.REPO_ROOT / f.raw["shared"]["protocol"]).read_text(encoding="utf-8")
r = v.Report()
v.check_marki(f, r)
v.check_uchwyty(f, r)
own = v.check_profile(f, a, proto, r)
v.check_cron(a, own, set(), r)
v.check_evals(f, r)
print(json.dumps(r.errors, ensure_ascii=False))
"""


@pytest.fixture()
def kopia(tmp_path):
    ign = shutil.ignore_patterns("__pycache__", "node_modules")
    for d in ("scripts", "shared", "profiles", "evals"):
        shutil.copytree(REPO / d, tmp_path / d, ignore=ign)
    shutil.copy2(REPO / "fleet.yaml", tmp_path / "fleet.yaml")
    (tmp_path / "infra").mkdir()
    shutil.copy2(REPO / "infra" / "docker-compose.yml", tmp_path / "infra" / "docker-compose.yml")
    return tmp_path


def _uruchom(root: Path, *args: str, kod: str | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-c", kod] if kod else [sys.executable, str(root / "scripts" / "new-agent.py"), *args]
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONUTF8": "1"})


def test_szkielet_agenta_biznesowego(kopia):
    p = _uruchom(kopia, "--marka", "kwiaty", "--title", "Kwiaty: klienci kwiaciarni")
    assert p.returncode == 0, p.stderr
    d = kopia / "profiles" / "jarvo-kwiaty"
    for rel in ("SOUL.md", "config.yaml", "cron/jobs.yaml", "distribution.yaml", "toolbox.yaml", "quality/rubric.md",
                "README.md", "CHANGELOG.md", ".no-bundled-skills", "skills/kwiaty/kwiaty-workflow/SKILL.md"):
        assert (d / rel).is_file(), rel

    a = next(x for x in fl.load_fleet(kopia / "fleet.yaml").agents if x.name == "jarvo-kwiaty")
    assert (a.marka, a.kind, a.status, a.handle, a.telegram_topic) == ("kwiaty", "specialist", "planned", "kwiaty", "kwiaty")

    soul = (d / "SOUL.md").read_text(encoding="utf-8")
    for fraza in ("ZGODA WŁAŚCICIELA", "art. 398", "RODO", "brands/kwiaty/", "to nie mój obszar, zapytaj Jarva",
                  fl.PROTOCOL_MARKER, "## Misja", "## Osobowość"):
        assert fraza in soul, fraza

    cfg = fl.load_yaml(d / "config.yaml")
    for plat in ("telegram", "api_server", "cron"):
        assert "computer_use" not in cfg["platform_toolsets"][plat]
    assert "jarvo telefon przydziel jarvo-kwiaty" in (d / "config.yaml").read_text(encoding="utf-8")
    assert "command_allowlist" not in cfg and "computer_use" not in cfg

    (job,) = fl.load_yaml(d / "cron" / "jobs.yaml")["jobs"]
    assert job["id"] == "kwiaty-dzien" and job["paused"] is True and job["deliver"] == "@@AGENT_DELIVER@@"

    scen = fl.load_yaml(kopia / "evals" / "jarvo-kwiaty" / "scenarios.yaml")["scenarios"]
    ids = {s["id"] for s in scen}
    assert {"kwiaty-wiedza-inna-marka", "kwiaty-zgoda-wymagana", "kwiaty-art398"} <= ids
    izolacja = next(s for s in scen if s["id"] == "kwiaty-wiedza-inna-marka")
    assert izolacja["type"] == "out_of_scope" and "jarodev" in izolacja["input"]

    assert "Dalej" in p.stdout
    for krok in ("security/redteam/promptfooconfig.yaml", "jarvo telegram tematy", "jarvo telefon przydziel",
                 "cron resume kwiaty-dzien", "docs/FLEET.md"):
        assert krok in p.stdout, krok

    # walidator po przełączeniu na active: zostają tylko {{…}} szablonu skilla, które autor i tak wypełnia
    w = _uruchom(kopia, kod=SPRAWDZ)
    assert w.returncode == 0, w.stderr
    bledy = [e for e in json.loads(w.stdout) if not e.startswith("jarvo-kwiaty/kwiaty/kwiaty-workflow:")]
    assert bledy == []


@pytest.mark.parametrize("marka, powod", [("jarodev", "należy już do jarvo-jarodev"), ("Zła_marka", "[a-z0-9-]+")])
def test_odmowa_marki(kopia, marka, powod):
    przed = (kopia / "fleet.yaml").read_text(encoding="utf-8")
    p = _uruchom(kopia, "--marka", marka, "--title", "X", "--name", "jarvo-nowy")
    assert p.returncode != 0 and powod in p.stderr
    assert (kopia / "fleet.yaml").read_text(encoding="utf-8") == przed
    assert not (kopia / "profiles" / "jarvo-nowy").exists()
