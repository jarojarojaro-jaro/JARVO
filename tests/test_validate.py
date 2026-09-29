"""Walidator repo: prawdziwe repo przechodzi bez błędów, a typowe pomyłki są wyłapywane."""

from __future__ import annotations

import re

import fleetlib as fl
import validate


def errors_matching(report, pattern: str) -> list[str]:
    return [e for e in report.errors if re.search(pattern, e)]


def test_repo_is_valid():
    report = validate.run()
    assert report.errors == [], "\n".join(report.errors)


def test_fleet_matches_profiles():
    fleet = fl.load_fleet()
    active = {a.name for a in fleet.active()}
    assert fleet.orchestrator in active and fleet.reviewer in active
    for a in fleet.active():
        assert a.dir.is_dir(), a.name
        assert a.model_tier in fleet.tiers and a.delegation_tier in fleet.tiers


def test_too_long_skill_description(repo_copy):
    skill = repo_copy / "profiles/jarvo-sherlock/skills/sherlock/monitoring/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    text = re.sub(r"^description: .*$", 'description: "' + "x" * 61 + '"', text, count=1, flags=re.M)
    skill.write_text(text, encoding="utf-8")
    assert errors_matching(validate.run(), r"monitoring: description 61 > 60")


def test_soul_without_protocol_marker(repo_copy):
    soul = repo_copy / "profiles/jarvo-web/SOUL.md"
    soul.write_text(soul.read_text(encoding="utf-8").replace(fl.PROTOCOL_MARKER, ""), encoding="utf-8")
    assert errors_matching(validate.run(), r"jarvo-web: SOUL.md bez znacznika")


def test_orchestrator_terminal_on_telegram(repo_copy):
    cfg = repo_copy / "profiles/jarvo/config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("telegram: [kanban,", "telegram: [terminal, kanban,"),
                   encoding="utf-8")
    assert errors_matching(validate.run(), r"nie powinien mieć terminala na Telegramie")



def test_hq_chat_platform_must_be_configured(repo_copy):
    import re as _re
    cfg = repo_copy / "profiles/jarvo-web/config.yaml"
    cfg.write_text(_re.sub(r"^  api_server: .*\n", "", cfg.read_text(encoding="utf-8"), flags=_re.M), encoding="utf-8")
    jarvo = repo_copy / "profiles/jarvo/config.yaml"
    jarvo.write_text(jarvo.read_text(encoding="utf-8").replace("api_server: [kanban,", "api_server: [terminal,"),
                     encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"jarvo-web: config.yaml bez platform_toolsets.api_server")
    assert errors_matching(report, r"jarvo: orkiestrator bez toolsetu kanban na czacie HQ")
    assert errors_matching(report, r"jarvo: orkiestrator nie powinien mieć terminala na czacie HQ")

def test_unattended_approvals_must_deny(repo_copy):
    cfg = repo_copy / "profiles/jarvo-studio/config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("cron_mode: deny", "cron_mode: approve"), encoding="utf-8")
    assert errors_matching(validate.run(), r"jarvo-studio: approvals.cron_mode")


def test_missing_script_reference(repo_copy):
    (repo_copy / "profiles/jarvo-web/scripts/seo_check.py").unlink()
    assert errors_matching(validate.run(), r"jarvo-web: odwołanie do nieistniejącego skryptu scripts/seo_check.py")


def test_env_file_and_secret_detected(repo_copy):
    (repo_copy / "profiles/jarvo/.env").write_text("X=1\n", encoding="utf-8")
    fake_key = "sk-or-v1-" + "ab" * 16          # składany w locie, żeby sam test nie był „sekretem”
    (repo_copy / "shared/notatka.md").write_text(f"klucz: {fake_key}\n", encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"profiles/jarvo/.env: plik .env nie może być w repo")
    assert errors_matching(report, r"shared/notatka.md: wygląda na klucz OpenRouter")


def test_too_few_evals(repo_copy):
    path = repo_copy / "evals/jarvo-reka/scenarios.yaml"
    data = fl.load_yaml(path)
    data["scenarios"] = data["scenarios"][:4]
    path.write_text(fl.dump_yaml(data), encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"jarvo-reka: 4 scenariuszy evals < 10")


def test_unpinned_lock_source(repo_copy):
    lock = repo_copy / "vendor/skills.lock.yaml"
    text = lock.read_text(encoding="utf-8")
    text = re.sub(r"rev: \"?[0-9a-f]{40}\"?", "rev: main", text, count=1)
    lock.write_text(text, encoding="utf-8")
    assert errors_matching(validate.run(), r"musi być przypięte do pełnego SHA")


def test_cron_script_must_exist(repo_copy):
    (repo_copy / "profiles/jarvo/scripts/brief_daily.py").unlink()
    assert errors_matching(validate.run(), r"jarvo/cron/jarvo-daily-brief: brak skryptu scripts/brief_daily.py")


def test_profile_without_fleet_entry(repo_copy):
    (repo_copy / "profiles/jarvo-nieznany").mkdir()
    assert errors_matching(validate.run(), r"profiles/jarvo-nieznany: brak wpisu w fleet.yaml")


def test_docs_count_must_match_repo(repo_copy):
    import shutil
    shutil.rmtree(repo_copy / "profiles/jarvo-studio/skills/studio/copy-pl")
    assert errors_matching(validate.run(), r"docs/FLEET.md: jarvo-studio ma 5 \(skille\), a tabela podaje 6")


def test_docs_must_list_whole_fleet(repo_copy):
    readme = repo_copy / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("`jarvo-reka`", "jarvo-reka"), encoding="utf-8")
    assert errors_matching(validate.run(), r"README.md: brak agenta `jarvo-reka`")


def test_docs_broken_link_and_anchor(repo_copy):
    (repo_copy / "docs/NOWY.md").write_text("[a](PLAN.md#nie-ma-takiej) [b](BRAK.md) [c](PLAN.md#6-roadmapa)\n",
                                            encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"docs/NOWY.md: kotwica #nie-ma-takiej nie istnieje w PLAN.md")
    assert errors_matching(report, r"docs/NOWY.md: link do nieistniejącego BRAK.md")
    assert not errors_matching(report, r"6-roadmapa")


def test_generalist_must_see_every_specialist(repo_copy):
    cfg = repo_copy / "profiles/jarvo-reka/config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace('    - "@@BUILD_DIR@@/profiles/jarvo-ads/skills"\n', ""),
                   encoding="utf-8")
    assert errors_matching(validate.run(), r"jarvo-reka: skills.external_dirs bez skilli jarvo-ads")
