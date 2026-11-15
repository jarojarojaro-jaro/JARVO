"""`scripts/new-agent.py --marka`: agent biznesowy jednym poleceniem (docs/FLEET.md „Agenci biznesowi”), domyślnie
w nakładce prywatnej. Szkielet idzie do kopii repo i do nakładki w katalogu tymczasowym (skrypt liczy ścieżki od
swojego położenia), więc repo zostaje nietknięte."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import fleetlib as fl
import pytest

REPO = Path(__file__).resolve().parents[1]

# po przełączeniu na active: czego walidator wymaga od profilu, rutyny, evals i wpisu z marką (flota z nakładką)
SPRAWDZ = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import fleetlib as fl, validate as v
n = Path(sys.argv[1])
plik = n / "fleet.yaml"
t = plik.read_text(encoding="utf-8")
i = t.index("name: jarvo-kwiaty")
j = t.index("status: planned", i)
plik.write_text(t[:j] + "status: active" + t[j + len("status: planned"):], encoding="utf-8")
f = fl.load_fleet(nakladka=n)
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


def _uruchom(root: Path, *args: str, kod: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-c", kod, *args] if kod else [sys.executable, str(root / "scripts" / "new-agent.py"), *args]
    srodowisko = {k: v for k, v in os.environ.items() if k != fl.NAKLADKA_ENV}
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8",
                          env={**srodowisko, "PYTHONUTF8": "1", **(env or {})})


def test_szkielet_agenta_biznesowego_w_nakladce(kopia, tmp_path):
    n = tmp_path / "nakladka"
    przed = (kopia / "fleet.yaml").read_text(encoding="utf-8")
    p = _uruchom(kopia, "--marka", "kwiaty", "--title", "Kwiaty: klienci kwiaciarni", "--nakladka", str(n))
    assert p.returncode == 0, p.stderr
    assert (kopia / "fleet.yaml").read_text(encoding="utf-8") == przed          # publiczne repo bez zmian
    assert not (kopia / "profiles" / "jarvo-kwiaty").exists() and not (kopia / "evals" / "jarvo-kwiaty").exists()
    for rel in ("fleet.yaml", "wzorce.md", "security/redteam/testy.yaml", "README.md", ".gitignore"):
        assert (n / rel).is_file(), rel                                           # szkielet nakładki
    d = n / "profiles" / "jarvo-kwiaty"
    for rel in ("SOUL.md", "config.yaml", "cron/jobs.yaml", "distribution.yaml", "toolbox.yaml", "quality/rubric.md",
                "README.md", "CHANGELOG.md", ".no-bundled-skills", "skills/kwiaty/kwiaty-workflow/SKILL.md"):
        assert (d / rel).is_file(), rel

    a = next(x for x in fl.load_fleet(kopia / "fleet.yaml", nakladka=n).agents if x.name == "jarvo-kwiaty")
    assert (a.marka, a.kind, a.status, a.handle, a.telegram_topic) == ("kwiaty", "specialist", "planned", "kwiaty", "kwiaty")
    assert a.root == n.resolve() and a.dir == n.resolve() / "profiles" / "jarvo-kwiaty"

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

    scen = fl.load_yaml(n / "evals" / "jarvo-kwiaty" / "scenarios.yaml")["scenarios"]
    ids = {s["id"] for s in scen}
    assert {"kwiaty-wiedza-inna-marka", "kwiaty-zgoda-wymagana", "kwiaty-art398"} <= ids

    assert "Dalej" in p.stdout
    for krok in (f"{n.resolve()}/security/redteam/testy.yaml", f"{n.resolve()}/wzorce.md", "--nakladka",
                 "jarvo telegram tematy", "jarvo telefon przydziel", "cron resume kwiaty-dzien", "docs/FLEET.md"):
        assert krok in p.stdout, krok

    # walidator po przełączeniu na active: zostają tylko {{…}} szablonu skilla, które autor i tak wypełnia
    w = _uruchom(kopia, str(n), kod=SPRAWDZ)
    assert w.returncode == 0, w.stderr
    bledy = [e for e in json.loads(w.stdout) if not e.startswith("jarvo-kwiaty/kwiaty/kwiaty-workflow:")]
    assert bledy == []

    # drugi agent w tej samej nakładce: dopisany do jej fleet.yaml, pytanie o cudzą markę bierze pierwszą
    p = _uruchom(kopia, "--marka", "sklep", "--title", "Sklep", env={fl.NAKLADKA_ENV: str(n)})
    assert p.returncode == 0, p.stderr
    nazwy = [x.name for x in fl.load_fleet(kopia / "fleet.yaml", nakladka=n).agents if x.root]
    assert nazwy == ["jarvo-kwiaty", "jarvo-sklep"]
    izolacja = next(s for s in fl.load_yaml(n / "evals" / "jarvo-sklep" / "scenarios.yaml")["scenarios"]
                    if s["id"] == "sklep-wiedza-inna-marka")
    assert izolacja["type"] == "out_of_scope" and "kwiaty" in izolacja["input"]


@pytest.mark.parametrize("marka, powod", [("kwiaty", "należy już do jarvo-kwiaty"), ("Zła_marka", "[a-z0-9-]+")])
def test_odmowa_marki(kopia, tmp_path, marka, powod):
    n = tmp_path / "nakladka"
    assert _uruchom(kopia, "--marka", "kwiaty", "--title", "K", "--nakladka", str(n)).returncode == 0
    przed = (n / "fleet.yaml").read_text(encoding="utf-8")
    p = _uruchom(kopia, "--marka", marka, "--title", "X", "--name", "jarvo-nowy", "--nakladka", str(n))
    assert p.returncode != 0 and powod in p.stderr
    assert (n / "fleet.yaml").read_text(encoding="utf-8") == przed
    assert not (n / "profiles" / "jarvo-nowy").exists()


def test_bez_katalogu_nakladki_odmawia_zamiast_pisac_do_repo(kopia):
    """Kopia bez jarvo/ (nie zna <root>/nakladka) i bez JARVO_NAKLADKA: odmowa, publiczne repo nietknięte."""
    przed = (kopia / "fleet.yaml").read_text(encoding="utf-8")
    p = _uruchom(kopia, "--marka", "kwiaty", "--title", "X")
    assert p.returncode != 0 and "--nakladka" in p.stderr
    assert (kopia / "fleet.yaml").read_text(encoding="utf-8") == przed
    assert not (kopia / "profiles" / "jarvo-kwiaty").exists()


def test_publiczny_tylko_na_zyczenie(kopia):
    p = _uruchom(kopia, "--marka", "kwiaty", "--title", "X", "--publiczny")
    assert p.returncode == 0, p.stderr
    assert (kopia / "profiles" / "jarvo-kwiaty" / "SOUL.md").is_file()
    assert next(a for a in fl.load_fleet(kopia / "fleet.yaml", nakladka=None).agents if a.name == "jarvo-kwiaty").marka == "kwiaty"
    assert "security/redteam/promptfooconfig.yaml" in p.stdout
