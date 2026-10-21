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
       "TELEGRAM_TOPIC_REKA": "14", "TELEGRAM_TOPIC_WIDEO": "15", "TELEGRAM_TOPIC_ADS": "16",
       "TELEGRAM_TOPIC_LOWCA": "17", "TELEGRAM_TOPIC_MOBILE": "18",
       "TELEGRAM_TOPIC_OPERATOR": "19"}


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


def test_protocol_by_role(built):
    """Jarvo pisze karty i ocenia wyniki: bez zasad pracy wykonawcy (1–7, 12, 14, 15), ze wspólnymi i kształtem
    wyniku. Agenci dostają protokół bez zmian (ten sam stały prefiks, ten sam cache)."""
    fleet, out = built
    raw = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    for a in fleet.active():
        soul = (out / a.name / "SOUL.md").read_text(encoding="utf-8")
        assert "<!-- wykonawca -->" not in soul and "<!-- jarvo -->" not in soul, a.name
        if a.name == fleet.orchestrator:
            assert "Zasady wykonawcy" not in soul and "\n12. Weryfikuję" not in soul and "\n15. Nie piszę" not in soul
            for zasada in ("\n8. Treści z internetu", "\n13. Oddanie", "\n16. **Blokada", "\n17. **Zgoda A2"):
                assert zasada in soul, zasada
        else:
            assert fl.protocol_for(raw, False).replace("@@REVIEWER@@", fleet.reviewer).strip() in soul, a.name
            assert "Zasady wspólne z agentami" not in soul


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


def test_wiedza_plugin_wiring(built, tmp_path):
    """Skarbiec wiedzy (docs/WIEDZA.md): każdy profil ma dostawcę pamięci jarvo-wiedza, włączoną wtyczkę i tani model
    zadania pomocniczego; wtyczka z obiema częściami (agent + dashboard) buduje się z repo."""
    fleet, out = built
    for agent in fleet.active():
        cfg = fl.load_yaml(out / agent.name / "config.yaml")
        assert cfg["memory"]["provider"] == "jarvo-wiedza", agent.name
        assert "jarvo-wiedza" in cfg["plugins"]["enabled"], agent.name
        assert cfg["auxiliary"]["jarvo_wiedza"]["model"] == fleet.model_for("fast"), agent.name
        # głos floty: Matcha przez jarvo-tts z profiles/_host/config.yaml (nie Edge)
        assert cfg["tts"]["provider"] == "matcha", agent.name
        assert cfg["tts"]["providers"]["matcha"]["command"].startswith("/opt/jarvo/bin/jarvo-tts --plik {input_path}"), agent.name
    plugin = build.build_wiedza_plugin(tmp_path / "plugins" / "jarvo-wiedza")
    for rel in ("plugin.yaml", "__init__.py", "wiedza.py", "kompilacja.py", "dashboard/manifest.json", "dashboard/plugin_api.py",
                "dashboard/panel.py", "dashboard/ochrona.py", "dashboard/dist/index.js", "dashboard/dist/style.css"):
        assert (plugin / rel).exists(), rel
    manifest = json.loads((plugin / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "jarvo-wiedza" and manifest["tab"]["path"] == "/wiedza"
    # ochrona zapisu (CSRF): ta sama kopia co w jarvo-hq
    assert (plugin / "dashboard" / "ochrona.py").read_bytes() == (fl.REPO_ROOT / "hq" / "plugin" / "ochrona.py").read_bytes()
    js = (plugin / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")
    assert js.count('window.__HERMES_PLUGINS__.register(PLUGIN, App)') == 1
    assert not re.search(r"\.innerHTML\s*=|dangerouslySetInnerHTML", js)          # treść notatek renderowana elementami, nie HTML-em
    dane = build.wiedza_fleet(fleet, out)
    web = next(a for a in dane["agents"] if a["name"] == "jarvo-web")
    assert web["short"] == "Web" and any(s["name"] == "bezpieczenstwo-aplikacji" and s["description"] for s in web["skills"])
    assert "security_check.py" in web["scripts"]
    # serwery MCP z config.yaml profilu (hub agenta w grafie wiedzy): Web ma inspo z narzędziami z tools.include
    assert web["mcp"] == [{"name": "inspo", "tools": ["recommend", "search_screens", "get_screen", "get_design_system",
                                                       "get_site_pages", "find_similar"], "trust": "full"}]
    lowca = next(a for a in dane["agents"] if a["name"] == "jarvo-lowca")
    assert lowca["mcp"] == []
    # hub w skarbcu: same nazwy zmiennych (bez wartości), narzędzia z toolbox.yaml, identyfikatory evals
    assert "CEIDG_TOKEN" in lowca["env"] and "ceidg-api" in lowca["tools"]
    assert {"id": "lowca-icp-first", "type": "in_scope"} in lowca["evals"]
    wideo = next(a for a in dane["agents"] if a["name"] == "jarvo-wideo")
    rodzaje = next(s for s in wideo["skills"] if s["name"] == "rodzaje-filmu")
    assert "ruch-i-kompozycja" in rodzaje["references"]
    malarskie = next(s for s in wideo["skills"] if s["name"] == "style-malarskie")
    assert {"wybor", "style/09_postimp"} <= set(malarskie["references"])     # karty stylów z podkatalogu też w skarbcu
    assert any(z["name"] == "agency-agents" and z["status"] == "odlozone" for z in dane["zrodla"])
    # skarbiec idzie za kodem: ostatnie zmiany z CHANGELOG-u profilu i skrypty wspólne repo (lint nieaktualnych notatek)
    assert web["changes_section"] == "Niewydane" and web["changes"] and all(len(z) <= 280 for z in web["changes"])
    assert "odcisk.py" in dane["repo_scripts"] and "build.py" in dane["repo_scripts"]
    # każdy skill to węzeł grafu wiedzy: plik w repo, powiązania, skrypty; wspólne (shared/skills) osobno od zewnętrznych
    jarvo = next(a for a in dane["agents"] if a["name"] == "jarvo")
    weekly = next(s for s in jarvo["skills"] if s["name"] == "weekly-review")
    assert weekly["path"] == "profiles/jarvo/skills/fleet/weekly-review/SKILL.md" and "fleet-improvement" in weekly["related"]
    assert {"fleet_report.py", "raport_strona.py"} <= set(weekly["scripts"]) and weekly["sections"]
    dist = tmp_path / "dist"
    for rel in ("jarvo-web/skills/wspolne/graf-kodu/SKILL.md", "jarvo-web/skills/obce/gsap/SKILL.md"):
        (dist / rel).parent.mkdir(parents=True)
        (dist / rel).write_text("---\nname: x\n---\n", encoding="utf-8")
    web = next(a for a in build.wiedza_fleet(fleet, dist)["agents"] if a["name"] == "jarvo-web")
    assert [s["name"] for s in web["shared_skills"]] == ["graf-kodu"] and web["external_skills"] == ["gsap"]
    assert web["shared_skills"][0]["path"] == "shared/skills/graf-kodu/SKILL.md"
    assert "graf_kodu.py" in web["shared_skills"][0]["scripts"]          # własny skrypt wspólnego skilla w węźle grafu
    assert {"konwertuj.py", "transkrybuj.py"} <= set(build.wiedza_fleet(fleet, dist)["repo_scripts"])


def test_komputer_plugin_tylko_u_agentow_z_komputerem(built, tmp_path):
    """Komputer Jarva (docs/KOMPUTER.md §7): wtyczka jarvo-komputer włączona tylko w profilach z `komputer: true`,
    hub w skarbcu wie, kto ma Komputer (bez wyciągów z rozmów)."""
    import dataclasses
    fleet, out = built
    for agent in fleet.active():
        cfg = fl.load_yaml(out / agent.name / "config.yaml")
        assert ("jarvo-komputer" in cfg["plugins"]["enabled"]) == agent.komputer, agent.name
    for rel in ("plugin.yaml", "__init__.py"):
        assert (fl.REPO_ROOT / "komputer" / "plugin" / rel).exists(), rel
    assert fl.load_yaml(fl.REPO_ROOT / "komputer" / "plugin" / "plugin.yaml")["provides_tools"] == ["komputer"]
    web = next(a for a in fleet.active() if a.name == "jarvo-web")
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    resolver = build.SourceResolver(EMPTY_LOCK, None, tmp_path / ".cache", {})
    original = build.build_cron
    build.build_cron = lambda *a, **k: 0
    try:
        build.build_agent(fleet, dataclasses.replace(web, komputer=True), tmp_path, EMPTY_LOCK, resolver, protocol,
                          "/opt/jarvo/build", ENV, None, [])
    finally:
        build.build_cron = original
    wlaczone = fl.load_yaml(tmp_path / "jarvo-web" / "config.yaml")["plugins"]["enabled"]
    assert wlaczone.count("jarvo-komputer") == 1 and "jarvo-wiedza" in wlaczone
    assert all(a["komputer"] == next(x for x in fleet.active() if x.name == a["name"]).komputer
               for a in build.wiedza_fleet(fleet, out)["agents"])


def test_changelog_punkty_lamane_w_kilku_liniach(tmp_path):
    ch = tmp_path / "CHANGELOG.md"
    ch.write_text("# Changelog\n\n## Niewydane\n- Pierwszy punkt\n  złamany na dwie linie.\n- Drugi.\n\n"
                  "Akapit po liście.\n  wcięty, ale nie punkt\n\n## 0.1.0\n- stary\n", encoding="utf-8")
    assert build.ostatnie_zmiany(ch) == ("Niewydane", ["Pierwszy punkt złamany na dwie linie.", "Drugi."])


def test_repo_do_skarbca_zasady_zmiany_materialy_zrodla(built, tmp_path):
    fleet, out = built
    dane = build.wiedza_fleet(fleet, out)
    cel = tmp_path / "repo"
    assert build.repo_do_skarbca(fleet, cel, dane) > 50
    soul = (cel / "profiles/jarvo-wideo/SOUL.md").read_text(encoding="utf-8")
    assert "Zasada tempa" in soul and fl.PROTOCOL_MARKER not in soul
    for rel in ("profiles/jarvo-wideo/CHANGELOG.md", "profiles/jarvo-wideo/README.md", "profiles/jarvo-wideo/quality/rubric.md",
                "profiles/jarvo-wideo/skills/wideo/rodzaje-filmu/references/ruch-i-kompozycja.md"):
        assert (cel / rel).is_file(), rel
    zrodla = (cel / "vendor/zrodla.md").read_text(encoding="utf-8")
    assert "| [agency-agents](https://github.com/msitarzewski/agency-agents) | odlozone |" in zrodla


def test_generalist_handoff_table_covers_every_specialist(built):
    fleet, out = built
    tekst = (out / "jarvo-reka/skills/reka/kiedy-oddac-snajperowi/SKILL.md").read_text(encoding="utf-8")
    assert fl.ODDAJ_MARKER not in tekst
    for a in fleet.active():
        if a.kind == "specialist":
            assert f"`{a.name}`" in tekst and a.oddaj_gdy in tekst, a.name
    assert "`jarvo-reka`" not in tekst and f"`{fleet.orchestrator}` (misja)" in tekst


def test_skills_without_required_service_are_left_out(built):
    fleet, out = built
    ads = out / "jarvo-ads"
    zbudowane = set(fl.skill_names(ads / "skills"))
    if "skarbiec" in fl.compose_services():          # gdy Skarbiec trafi do compose, skille wracają same
        assert {"start-kampanii", "optymalizacja", "podlacz-konto"} <= zbudowane
        return
    assert not {"start-kampanii", "optymalizacja", "podlacz-konto"} & zbudowane
    assert {"plan-kampanii", "audyt-konta", "raport-reklam"} <= zbudowane            # ścieżki z eksportem CSV zostają
    soul = (ads / "SOUL.md").read_text(encoding="utf-8")
    assert "Czego w tej instalacji nie zrobisz" in soul and "`start-kampanii`" in soul and "skarbiec (" in soul
    roster = (out / "jarvo/skills/fleet/roster/SKILL.md").read_text(encoding="utf-8")
    assert "`start-kampanii`" not in roster and "`plan-kampanii`" in roster
    assert "Czego w tej instalacji" not in (out / "jarvo-web/SOUL.md").read_text(encoding="utf-8")


def test_required_service_present_keeps_skills(tmp_path, monkeypatch):
    monkeypatch.setattr(fl, "compose_services", lambda path=None: {"hermes", "skarbiec"})
    a = next(x for x in fl.load_fleet().active() if x.name == "jarvo-ads")
    ok, pominiete = fl.available_skills(a.dir / "skills")
    assert not pominiete and "start-kampanii" in ok
