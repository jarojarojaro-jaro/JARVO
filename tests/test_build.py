"""Build dystrybucji: tokeny, SOUL z protokołem, roster, rubryki sędziego, trasy Telegrama.

Budowa skilli zewnętrznych i crona wymaga drzewa Hermesa: pełny test uruchamia się tylko przy
JARVO_TEST_HERMES_SRC=/ścieżka/do/hermes-agent (opcjonalnie JARVO_HERMES_PYTHON z zależnościami Hermesa).
"""

from __future__ import annotations

import json
import os
import re

import pytest

import build
import fleetlib as fl

EMPTY_LOCK = {"sources": {}, "agents": {}}
ENV = {"TELEGRAM_OWNER_ID": "111111111", "TELEGRAM_HQ_CHAT_ID": "-1002222222222",
       "TELEGRAM_TOPIC_SHERLOCK": "11", "TELEGRAM_TOPIC_WEB": "12", "TELEGRAM_TOPIC_STUDIO": "13",
       "TELEGRAM_TOPIC_REKA": "14", "TELEGRAM_TOPIC_WIDEO": "15", "TELEGRAM_TOPIC_ADS": "16"}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Build wszystkich aktywnych agentów bez skilli zewnętrznych i bez crona (nie wymaga Hermesa)."""
    out = tmp_path_factory.mktemp("build") / "profiles"
    out.mkdir()
    fleet = fl.load_fleet()
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    resolver = build.SourceResolver(EMPTY_LOCK, None, out / ".cache", {})
    original = build.build_cron
    build.build_cron = lambda *a, **k: 0
    try:
        for agent in fleet.active():
            build.build_agent(fleet, agent, out, EMPTY_LOCK, resolver, protocol, "/opt/jarvo/build", ENV, None, [])
    finally:
        build.build_cron = original
    return fleet, out


def test_no_unrendered_tokens(built):
    _, out = built
    leftovers = []
    for path in out.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".yaml", ".yml"}:
            for tok in re.findall(r"@@[A-Z_]+@@", path.read_text(encoding="utf-8")):
                leftovers.append(f"{path.relative_to(out)}: {tok}")
    assert leftovers == []


def test_no_secrets_or_sources_in_dist(built):
    _, out = built
    bad = [p for p in out.rglob("*") if p.name.endswith(".env") or p.name == "jobs.yaml" or p.name == "__pycache__"]
    assert bad == []


def test_models_and_profile_metadata(built):
    fleet, out = built
    for a in fleet.active():
        cfg = fl.load_yaml(out / a.name / "config.yaml")
        assert cfg["model"]["default"] == fleet.model_for(a.model_tier)
        assert cfg["model"]["provider"] == fleet.provider
        meta = fl.load_yaml(out / a.name / "profile.yaml")
        assert meta["description"] == a.description
        assert meta["display_name"].endswith(a.title)


def test_soul_gets_protocol_with_reviewer(built):
    fleet, out = built
    for a in fleet.active():
        soul = (out / a.name / "SOUL.md").read_text(encoding="utf-8")
        assert fl.PROTOCOL_MARKER not in soul and fl.ROSTER_MARKER not in soul
        assert f'kanban_request_review(reviewer="{fleet.reviewer}"' in soul, a.name


def test_soul_gets_model_calibration(built):
    """Kalibracja pod rodzinę modelu agenta (shared/calibration/): orkiestrator i wykonawcy mają swoje sekcje."""
    fleet, out = built
    for a in fleet.active():
        soul = (out / a.name / "SOUL.md").read_text(encoding="utf-8")
        role = "orkiestrator" if a.name == fleet.orchestrator else "wykonawca"
        assert f"<!-- Jarvo:CALIBRATION {role} -->" in soul, a.name
        assert f"## Jak pracuję na tym modelu ({fleet.model_for(a.model_tier)})" in soul, a.name
        # blok stoi za protokołem, przed sekcjami po znaczniku
        assert soul.index("## Kontrakt zlecenia floty") < soul.index("<!-- Jarvo:CALIBRATION")


def test_orchestrator_roster_and_rubrics(built):
    fleet, out = built
    jarvo = out / fleet.orchestrator
    soul = (jarvo / "SOUL.md").read_text(encoding="utf-8")
    roster = (jarvo / "skills/fleet/roster/SKILL.md").read_text(encoding="utf-8")
    fm, _ = fl.split_frontmatter(roster)
    assert fm["name"] == "roster" and len(fm["description"]) <= fl.SKILL_PROMPT_DESC_LIMIT
    for a in fleet.active():
        assert f"`{a.name}`" in roster
        assert a.name in soul
        if a.name != fleet.orchestrator:
            assert (jarvo / f"skills/fleet/sdlc-review/references/rubric-{a.name}.md").exists()
    assert "metoda-sherlocka" in roster     # pin_skills Sherlocka


def test_generalist_sees_specialist_skills(built):
    _, out = built
    cfg = fl.load_yaml(out / "jarvo-reka" / "config.yaml")
    dirs = cfg["skills"]["external_dirs"]
    assert "/opt/jarvo/build/profiles/jarvo-web/skills" in dirs
    assert (out / "jarvo-reka" / ".no-bundled-skills").exists() is False


def test_category_descriptions(built):
    _, out = built
    desc = out / "jarvo-sherlock/skills/sherlock/DESCRIPTION.md"
    assert desc.exists() and "Metoda śledcza" in desc.read_text(encoding="utf-8")


def test_owner_deliver_token():
    fleet = fl.load_fleet()
    jarvo = fleet.agent(fleet.orchestrator)
    assert build.base_tokens(fleet, jarvo, "/b", ENV)["OWNER_DELIVER"] == "telegram:111111111"
    assert build.base_tokens(fleet, jarvo, "/b", {})["OWNER_DELIVER"] == "local"


def test_host_routes(tmp_path):
    fleet = fl.load_fleet()
    notes = build.build_host(fleet, tmp_path, ENV)
    cfg = fl.load_yaml(tmp_path / "config.yaml")
    routes = {r["name"]: r for r in cfg["gateway"]["profile_routes"]}
    assert notes == []
    assert routes["owner-dm"] == {"name": "owner-dm", "platform": "telegram", "chat_id": "111111111",
                                  "profile": fleet.orchestrator}
    assert routes["hq-jarvo"]["chat_id"] == "-1002222222222" and "thread_id" not in routes["hq-jarvo"]
    assert routes["hq-jarvo-web"]["thread_id"] == "12" and routes["hq-jarvo-web"]["profile"] == "jarvo-web"
    assert len(routes) == 1 + len(fleet.active())
    assert cfg["gateway"]["multiplex_profiles"] is True
    assert (tmp_path / "SOUL.md").exists()


def test_host_routes_missing_ids_are_reported(tmp_path):
    notes = build.build_host(fl.load_fleet(), tmp_path, {"TELEGRAM_HQ_CHAT_ID": "-100"})
    joined = " ".join(notes)
    assert "TELEGRAM_OWNER_ID" in joined and "TELEGRAM_TOPIC_WEB" in joined


def test_read_env_file(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("JARVO_", "TELEGRAM_")):
            monkeypatch.delenv(key)
    f = tmp_path / "jarvo.env"
    f.write_text('# komentarz\nTELEGRAM_OWNER_ID="123"\nTELEGRAM_TOPIC_WEB=\'7\'\nINNE\n', encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_HQ_CHAT_ID", "-100")
    env = build.read_env_file(f)
    assert env == {"TELEGRAM_OWNER_ID": "123", "TELEGRAM_TOPIC_WEB": "7", "TELEGRAM_HQ_CHAT_ID": "-100"}


HERMES_SRC = os.environ.get("JARVO_TEST_HERMES_SRC")


@pytest.mark.skipif(not HERMES_SRC, reason="ustaw JARVO_TEST_HERMES_SRC, aby zbudować crona przez API Hermesa")
def test_full_orchestrator_build_with_cron(tmp_path, monkeypatch):
    env_file = tmp_path / "jarvo.env"
    env_file.write_text("TELEGRAM_OWNER_ID=111111111\n", encoding="utf-8")
    for key in list(os.environ):
        if key.startswith("TELEGRAM_"):
            monkeypatch.delenv(key)
    rc = build.main(["--hermes-src", HERMES_SRC, "--out", str(tmp_path / "out"), "--agent", "jarvo",
                     "--env-file", str(env_file)])
    assert rc == 0
    jobs = json.loads((tmp_path / "out/profiles/jarvo/cron/jobs.json").read_text(encoding="utf-8"))
    jobs = jobs["jobs"] if isinstance(jobs, dict) else jobs
    ids = {j["id"] for j in jobs}
    assert ids == {"jarvo-patrol", "jarvo-daily-brief", "jarvo-weekly-review", "jarvo-knowledge-freshness"}
    assert all(j.get("deliver") == "telegram:111111111" for j in jobs)
    manifest = json.loads((tmp_path / "out/BUILD.json").read_text(encoding="utf-8"))
    assert manifest["agents"][0]["cron_jobs"] == 4
