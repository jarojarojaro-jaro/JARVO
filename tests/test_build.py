"""Build dystrybucji: tokeny, SOUL z protokołem, roster, rubryki sędziego, trasy Telegrama, układ kontenera i natywny.

Budowa skilli zewnętrznych i crona wymaga drzewa Hermesa: pełny test uruchamia się tylko przy
JARVO_TEST_HERMES_SRC=/ścieżka/do/hermes-agent (opcjonalnie JARVO_HERMES_PYTHON z zależnościami Hermesa).
Układ natywny (docs/NATYWNIE.md S06) budujemy dla Windows na każdym systemie (ścieżki jako PureWindowsPath).
"""

from __future__ import annotations

import dataclasses
import fnmatch
import json
import os
import re
import shlex
import shutil
from pathlib import PureWindowsPath

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


def test_dist_text_files_have_lf(built):
    """Dystrybucja z LF na każdym systemie: build na Windows nie zamienia końców linii, więc Hermes i skarbiec
    dostają te same bajty co z Linuksa."""
    _, out = built
    crlf = [p.relative_to(out).as_posix() for p in out.rglob("*")
            if p.is_file() and p.suffix in {".md", ".yaml", ".yml"} and b"\r\n" in p.read_bytes()]
    assert crlf == []


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
    """Skarbiec wiedzy (docs/WIEDZA.md): każdy profil ma dostawcę pamięci jarvo-wiedza, włączoną wtyczkę i główny model
    (frontier) zadania pomocniczego; wtyczka z obiema częściami (agent + dashboard) buduje się z repo."""
    fleet, out = built
    for agent in fleet.active():
        cfg = fl.load_yaml(out / agent.name / "config.yaml")
        assert cfg["memory"]["provider"] == "jarvo-wiedza", agent.name
        assert "jarvo-wiedza" in cfg["plugins"]["enabled"], agent.name
        assert cfg["auxiliary"]["jarvo_wiedza"]["model"] == fleet.model_for("frontier"), agent.name
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


# ---------------------------------------------------------------- układ kontenera i natywny (docs/NATYWNIE.md S06)

WIN_DANE = "D:/JarvoTest/proba-build/Michał Żółć/dane"
WIN_PROGRAM = "D:/JarvoTest/proba-build/Michał Żółć/program"
WIN_OPCJE = ["--uklad", "natywny", "--system", "windows", "--dane", WIN_DANE,
             "--runtime-build-dir", "D:/JarvoTest/proba-build/Michał Żółć/build",
             "--repo-dir", f"{WIN_PROGRAM}/app/0123abcd",
             "--py", f"{WIN_PROGRAM}/venvs/narzedzia/Scripts/python.exe"]
# dzisiejsze napisy kontenera: tokeny, polecenia bramy i zakazy w układzie kontenera muszą zostać bajt w bajt
KONTENER_TOKENY = {"DATA_DIR": "/opt/data", "JARVO_DIR": "/opt/data/jarvo", "KNOWLEDGE_DIR": "/opt/data/jarvo/knowledge",
                   "MISSIONS_DIR": "/opt/data/jarvo/missions", "WORKSPACES_DIR": "/opt/data/jarvo/workspaces",
                   "INBOX_DIR": "/opt/data/jarvo/inbox", "REPO_DIR": "/opt/jarvo/repo", "BUILD_DIR": "/opt/jarvo/build",
                   "TOOLS_DIR": "/opt/data/jarvo/narzedzia", "BIN_DIR": "/opt/jarvo/bin", "PY": "python3"}


def _main_bez_zrodel(out, *opcje):
    """build.main bez sieci i bez Hermesa: bez skilli z locka i bez crona (jak fixture `built`), bez TELEGRAM_*."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(build, "vendor_skills", lambda *a, **k: None)
        mp.setattr(build, "build_cron", lambda *a, **k: 0)
        for key in list(os.environ):
            if key.startswith(("JARVO_", "TELEGRAM_")):
                mp.delenv(key)
        assert build.main(["--out", str(out), *opcje]) == 0
    return out


@pytest.fixture(scope="module")
def natywny_win(tmp_path_factory):
    return _main_bez_zrodel(tmp_path_factory.mktemp("natywny") / "build", *WIN_OPCJE)


@pytest.fixture(scope="module")
def kontener_main(tmp_path_factory):
    return _main_bez_zrodel(tmp_path_factory.mktemp("kontener") / "build")


def _zakazany(polecenie: str, deny: list[str]) -> bool:
    """Dopasowanie jak w Hermesie (tools/approval_floors.py:23): fnmatch bez wielkości liter, surowe polecenie."""
    return any(fnmatch.fnmatchcase(polecenie.lower(), w.lower()) for w in deny)


def test_tokeny_kontenera_jak_przed_ukladem_natywnym():
    """Kontener działa bez zmian do etapu E13: ścieżki z fleet.yaml (względne do <dane>) dają w kontenerze te same
    napisy co dawne /opt/data/…, a STT bramy ten sam szablon co ENV obrazu."""
    fleet = fl.load_fleet()
    jarvo = fleet.agent(fleet.orchestrator)
    assert build.sciezki_floty(fleet, build.KONTENER) == KONTENER_TOKENY
    tokeny = build.base_tokens(fleet, jarvo, "/opt/jarvo/build", ENV)
    assert {k: tokeny[k] for k in KONTENER_TOKENY} == KONTENER_TOKENY
    docker = (fl.REPO_ROOT / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert f'HERMES_LOCAL_STT_COMMAND="{build.polecenie_stt(build.KONTENER)}"' in docker
    deny = ["*rm -*r* /opt/data", "*/opt/jarvo/komputer*"]
    assert build.zakazy(deny, fleet, build.KONTENER) is deny
    tts = fl.load_yaml(fl.REPO_ROOT / "profiles/_host/config.yaml")["tts"]["providers"]["matcha"]["command"]
    assert build.polecenie_programu(tts, build.KONTENER) == tts
    for klucz in ("missions_dir", "workspaces_dir", "knowledge_dir", "jarvo_dir", "inbox_dir"):
        assert not str(fleet.raw["shared"][klucz]).startswith("/"), klucz        # F11: względne do <dane>


def test_kontener_main_to_dawny_build_bez_wartosci_natywnych(built, kontener_main):
    """Domyślny build (deploy.sh, kuznia.sh) daje te same profile co dawne wywołanie build_agent i nic z układu
    natywnego: bez wtyczki zgód, bez host/srodowisko.json, wyszukiwarka i silnik przeglądarki jak w repo."""
    _, legacy = built
    nowe = kontener_main / "profiles"
    pliki = sorted(p.relative_to(legacy).as_posix() for p in legacy.rglob("*") if p.is_file())
    assert pliki == sorted(p.relative_to(nowe).as_posix() for p in nowe.rglob("*") if p.is_file())
    assert all((legacy / r).read_bytes() == (nowe / r).read_bytes() for r in pliki)
    assert not (kontener_main / "plugins" / build.ZGODY_PLUGIN).exists()
    assert not (kontener_main / "host" / "srodowisko.json").exists()
    manifest = json.loads((kontener_main / "BUILD.json").read_text(encoding="utf-8"))
    assert manifest["plugins"] == ["jarvo-hq", "jarvo-wiedza", "jarvo-komputer"] and "uklad" not in manifest
    host, szablon = (fl.load_yaml(kontener_main / "host" / "config.yaml"),
                     fl.load_yaml(fl.REPO_ROOT / "profiles" / "_host" / "config.yaml"))
    for klucz in ("plugins", "security", "auth", "terminal", "tts"):
        assert host.get(klucz) == szablon.get(klucz), klucz
    for a in fl.load_fleet().active():
        zrodlo, cfg = fl.load_yaml(a.dir / "config.yaml"), fl.load_yaml(nowe / a.name / "config.yaml")
        for klucz in ("web", "browser", "security", "auth"):
            assert cfg.get(klucz) == zrodlo.get(klucz), (a.name, klucz)
        assert set(cfg["terminal"]) == set(zrodlo["terminal"]), a.name
        assert cfg["approvals"]["mode"] == zrodlo["approvals"]["mode"] and build.ZGODY_PLUGIN not in cfg["plugins"]["enabled"]


def test_natywny_windows_parsuje_sie_bez_sciezek_obrazu(natywny_win):
    """Build natywny dla katalogu danych ze spacją i polskimi znakami: każdy YAML i JSON się parsuje, a konfiguracja
    z buildu (profile, host, BUILD.json, srodowisko.json) nie ma ścieżek obrazu /opt. Wyjątek: serwer MCP inspo
    Weba (node_modules obrazu; natywnie etap E5, docs/NATYWNIE.md P06)."""
    for p in natywny_win.rglob("*"):
        if p.is_file() and p.suffix in (".yaml", ".yml", ".json") and ".cache" not in p.parts:
            tekst = p.read_text(encoding="utf-8")
            json.loads(tekst) if p.suffix == ".json" else fl.loads_yaml(tekst)
    konfig = [*natywny_win.glob("profiles/*/config.yaml"), *natywny_win.glob("profiles/*/profile.yaml"),
              *natywny_win.glob("profiles/*/distribution.yaml"), natywny_win / "host" / "config.yaml",
              natywny_win / "host" / "srodowisko.json", natywny_win / "BUILD.json"]
    assert len(konfig) == 3 * len(fl.load_fleet().active()) + 3
    for p in konfig:
        dane = json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else fl.load_yaml(p)
        if p.name == "config.yaml" and p.parent.name == "jarvo-web":
            assert set(dane.pop("mcp_servers")) == {"inspo"}
        assert "/opt" not in json.dumps(dane, ensure_ascii=False), p.relative_to(natywny_win).as_posix()
    # tokeny w tekstach dla agenta (SOUL, skille) idą za katalogiem danych
    assert f"{WIN_DANE}/jarvo/missions/INDEX.md" in (natywny_win / "profiles/jarvo/SOUL.md").read_text(encoding="utf-8")


def test_natywny_windows_sciezki_i_wartosci_per_system(natywny_win):
    fleet = fl.load_fleet()
    profile = natywny_win / "profiles"
    for a in fleet.active():
        cfg, zrodlo = fl.load_yaml(profile / a.name / "config.yaml"), fl.load_yaml(a.dir / "config.yaml")
        assert cfg["terminal"]["cwd"] == f"{WIN_DANE}/jarvo/workspaces/{a.name}", a.name
        # C06: Lightpanda nie ma wydania na Windows; U01/I14: bez wymuszonej wyszukiwarki (autodetekcja Hermesa)
        if (zrodlo.get("browser") or {}).get("engine"):
            assert cfg["browser"]["engine"] == "chrome", a.name
        assert "search_backend" not in (cfg.get("web") or {}), a.name
        # W04: wtyczka zgód w każdym profilu; I08: profil czatu (orkiestrator) z approvals.mode manual
        assert build.ZGODY_PLUGIN in cfg["plugins"]["enabled"] and "jarvo-wiedza" in cfg["plugins"]["enabled"], a.name
        assert cfg["approvals"]["mode"] == ("manual" if a.name == fleet.orchestrator else zrodlo["approvals"]["mode"])
        assert {k: cfg["approvals"][k] for k in ("cron_mode", "single_query_mode", "unattended_mode")} == \
            {"cron_mode": "deny", "single_query_mode": "deny", "unattended_mode": "deny"}, a.name
        assert cfg["security"]["tirith_enabled"] is False and cfg["security"]["allow_lazy_installs"] is False
        assert cfg["auth"]["adopt_external_logins"] is False
        assert (cfg["terminal"]["home_mode"], cfg["terminal"]["auto_source_bashrc"]) == ("profile", False)
        # V11: lektor z programu floty, pełna ścieżka .exe z „/” w cudzysłowie, argumenty bez zmian
        assert cfg["tts"]["providers"]["matcha"]["command"] == (
            f'"{WIN_PROGRAM}/bin-floty/jarvo-tts.exe" --plik {{input_path}} -o {{output_path}} --glos {{voice}}'), a.name
        assert "Układ natywny (windows)" in (profile / a.name / "config.yaml").read_text(encoding="utf-8").splitlines()[1]
    reka = fl.load_yaml(profile / "jarvo-reka" / "config.yaml")
    assert "D:/JarvoTest/proba-build/Michał Żółć/build/profiles/jarvo-web/skills" in reka["skills"]["external_dirs"]
    assert "Michał Żółć/dane/jarvo/missions." in reka["approvals"]["smart_policy"].replace("\n", " ")
    host = fl.load_yaml(natywny_win / "host" / "config.yaml")
    assert host["plugins"]["enabled"] == [build.ZGODY_PLUGIN] and host["security"]["tirith_enabled"] is False
    assert host["tts"]["providers"]["matcha"]["command"].startswith(f'"{WIN_PROGRAM}/bin-floty/jarvo-tts.exe" --plik ')
    stt = json.loads((natywny_win / "host" / "srodowisko.json").read_text(encoding="utf-8"))
    assert stt == {"HERMES_LOCAL_STT_COMMAND": f'"{WIN_PROGRAM}/bin-floty/jarvo-stt.exe" {build.STT_ARGUMENTY}'}
    manifest = json.loads((natywny_win / "BUILD.json").read_text(encoding="utf-8"))
    assert manifest["plugins"][-1] == build.ZGODY_PLUGIN and manifest["uklad"]["system"] == "windows"
    assert manifest["uklad"]["sciezki"]["PY"] == f'"{WIN_PROGRAM}/venvs/narzedzia/Scripts/python.exe"'
    for rel in ("plugin.yaml", "__init__.py"):
        assert (natywny_win / "plugins" / build.ZGODY_PLUGIN / rel).read_bytes() == \
            (fl.REPO_ROOT / "zgody" / "plugin" / rel).read_bytes()


def test_natywne_polecenia_stt_i_tts_jak_dzieli_je_hermes(natywny_win):
    """HERMES_LOCAL_STT_COMMAND Hermes wypełnia str.format (argumenty przez shlex.quote) i dzieli shlex.split w trybie
    POSIX: program ze spacją i polskimi znakami zostaje jednym słowem, ścieżki Windows z „\\” przechodzą w apostrofach."""
    stt = json.loads((natywny_win / "host" / "srodowisko.json").read_text(encoding="utf-8"))["HERMES_LOCAL_STT_COMMAND"]
    argv = shlex.split(stt.format(input_path=shlex.quote(r"C:\Users\Michał Żółć\głosówka.ogg"),
                                  output_dir=shlex.quote(r"C:\Temp\stt x"), language="pl", model="base"))
    assert argv == [f"{WIN_PROGRAM}/bin-floty/jarvo-stt.exe", r"C:\Users\Michał Żółć\głosówka.ogg", "--output-dir",
                    r"C:\Temp\stt x", "--language", "pl"]
    tts = fl.load_yaml(natywny_win / "host" / "config.yaml")["tts"]["providers"]["matcha"]["command"]
    assert shlex.split(tts)[0] == f"{WIN_PROGRAM}/bin-floty/jarvo-tts.exe"
    # klamry w ścieżce programu nie psują szablonu Hermesa
    u = build.Uklad(nazwa="natywny", system="windows", bin="D:/Jarvo {x}/bin-floty")
    assert build.polecenie_stt(u).format(input_path="a", output_dir="b", language="pl").startswith(
        '"D:/Jarvo {x}/bin-floty/jarvo-stt.exe" a ')


def test_natywne_zakazy_w_kazdej_pisowni_sciezki_danych(natywny_win):
    """F15: zakaz usunięcia danych floty działa dla C:/…, C:\\…, /c/… (Git Bash), $HERMES_HOME i w cudzysłowie, także
    poleceniami Windows; sprzątanie katalogów roboczych zostaje dozwolone."""
    deny = fl.load_yaml(natywny_win / "profiles" / "jarvo-web" / "config.yaml")["approvals"]["deny"]
    d = WIN_DANE.replace("/", "\\")
    gb = "/d/" + WIN_DANE[3:]
    for polecenie in (f'rm -rf "{WIN_DANE}"', f"rm -rf '{d}\\'", f'rm -rf "{gb}/jarvo"', f"rm -rf {WIN_DANE}/jarvo/",
                      f'rm -rf "{WIN_DANE}/jarvo/knowledge/marki"', f'rm -r "{d}\\profiles\\jarvo-web"',
                      'rm -rf "$HERMES_HOME"', "rm -rf ${HERMES_HOME}/jarvo/missions/m1",
                      f'Remove-Item -Recurse -Force "{d}\\jarvo"', f'cmd //c "rmdir /s /q {d}\\jarvo\\state"',
                      f'rm -rf "{WIN_DANE}/jarvo/komputer/profil"', f'del /s /q "{gb}/profiles"'):
        assert _zakazany(polecenie, deny), polecenie
    # (`rm -rf /d/…/workspaces/…` łapie już własny wzorzec profili `rm -rf /*`, jak w kontenerze każdą ścieżkę od „/”)
    for polecenie in (f'rm -rf "{WIN_DANE}/jarvo/workspaces/jarvo-web/out"', f"rm -rf '{d}\\jarvo\\workspaces\\x'",
                      f'ls -la "{WIN_DANE}/jarvo"', "rm -rf out/stare", f'rm -rf "{WIN_DANE}x"'):
        assert not _zakazany(polecenie, deny), polecenie
    assert not any("/opt" in w for w in deny)
    assert {"*hermes config set*", "*webhook.site*", "* | sh"} <= set(deny)      # reszta zakazów bez zmian
    # katalog danych pod katalogiem domowym: także pisownia „~” (Hermes zwija tak HOME, approval_detection.py:550)
    u = build.Uklad(nazwa="natywny", system="windows", dane="C:/Users/Michał Żółć/AppData/Local/Jarvo/dane",
                    dom="C:/Users/Michał Żółć")
    zakazy = build.zakazy(fl.load_yaml(fl.REPO_ROOT / "shared/security/deny.yaml")["deny"], fl.load_fleet(), u)
    assert _zakazany('rm -rf "~/AppData/Local/Jarvo/dane/jarvo"', zakazy)
    assert _zakazany("rm -rf ~/appdata/local/jarvo/dane/profiles/jarvo", zakazy)      # bez wielkości liter


def test_natywny_macos_i_linux_bez_exe_z_lightpanda(tmp_path):
    """macOS i Linux natywnie: Lightpanda zostaje, programy bez .exe, zakazy bez pisowni Windows, ale z „~”."""
    fleet = fl.load_fleet()
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    resolver = build.SourceResolver(EMPTY_LOCK, None, tmp_path / ".cache", {})
    for system, dane, dom in (("macos", "/Users/michał/.jarvo/dane", "/Users/michał"),
                              ("linux", "/home/ola/.local/share/jarvo/dane", "/home/ola")):
        program = dane.rsplit("/", 1)[0] + "/program"
        u = build.Uklad(nazwa="natywny", system=system, dane=dane, repo=program + "/app/1", build="/tmp/b",
                        narzedzia=program + "/narzedzia-floty", bin=program + "/bin-floty",
                        py=f"{program}/venvs/n/bin/python", dom=dom)
        out = tmp_path / system
        out.mkdir()
        original = build.build_cron
        build.build_cron = lambda *a, **k: 0
        try:
            for name in (fleet.orchestrator, "jarvo-web"):
                build.build_agent(fleet, fleet.agent(name), out, EMPTY_LOCK, resolver, protocol, u.build, ENV, None,
                                  [], uklad=u)
        finally:
            build.build_cron = original
        cfg = fl.load_yaml(out / "jarvo-web" / "config.yaml")
        assert cfg["browser"]["engine"] == "lightpanda" and "search_backend" not in (cfg.get("web") or {})
        assert cfg["tts"]["providers"]["matcha"]["command"].startswith(f'"{program}/bin-floty/jarvo-tts" --plik ')
        deny = cfg["approvals"]["deny"]
        assert _zakazany(f'rm -rf "{dane}/jarvo"', deny) and _zakazany("rm -rf ~/" + dane[len(dom) + 1:], deny)
        assert not any(dane.replace("/", "\\") in w or "Remove-Item" in w for w in deny)
        assert fl.load_yaml(out / fleet.orchestrator / "config.yaml")["approvals"]["mode"] == "manual"


def test_sciezka_z_ukosnikiem_w_cudzyslowie_lamie_yaml_a_build_daje_ukosnik_w_przod():
    """S06: ścieżka z „\\” w podwójnym cudzysłowie YAML to sekwencje ucieczki (\\U, \\x…) i ScannerError, więc build
    zapisuje ścieżki przez as_posix(); źródłowy config z tokenem w cudzysłowie parsuje się z polskimi znakami."""
    z_ukosnikiem = str(PureWindowsPath(WIN_DANE))
    with pytest.raises(Exception):
        fl.loads_yaml(f'cwd: "{z_ukosnikiem}"')
    sciezka = build.sciezka_ukladu(z_ukosnikiem, "windows", "dane")
    assert sciezka == WIN_DANE and fl.loads_yaml(f'cwd: "{sciezka}"') == {"cwd": WIN_DANE}
    fleet = fl.load_fleet()
    u = build.Uklad(nazwa="natywny", system="windows", dane=sciezka)
    tokeny = build.base_tokens(fleet, fleet.agent("jarvo-reka"), "D:/b", ENV, u)
    cfg = fl.loads_yaml(build.render_tokens((fleet.agent("jarvo-reka").dir / "config.yaml").read_text(encoding="utf-8"),
                                            tokeny))
    assert cfg["terminal"]["cwd"] == f"{WIN_DANE}/jarvo/workspaces/jarvo-reka"
    inny = "linux" if build.system_tego_komputera() == "macos" else "macos"     # ścieżka względna dla obcego systemu
    for zla, system in (('D:/a"b', "windows"), ("/home/x/$HOME", "linux"), ("/home/a\\b", "linux"), ("dane", inny)):
        with pytest.raises(SystemExit):
            build.sciezka_ukladu(zla, system, "dane")
    assert build.slowo_polecenia("python3") == "python3"
    assert build.slowo_polecenia("C:/Users/Michał Żółć/py.exe") == '"C:/Users/Michał Żółć/py.exe"'


def test_token_psujacy_yaml_zatrzymuje_build(tmp_path, monkeypatch):
    """@@PY@@ ze spacją ma własny cudzysłów: w podwójnym cudzysłowie YAML zepsułby config, więc build staje z opisem."""
    fleet = fl.load_fleet()
    profile = tmp_path / "profiles"
    shutil.copytree(fleet.agent("jarvo-ads").dir, profile / "jarvo-ads")
    cfg = profile / "jarvo-ads" / "config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + 'proba: "@@PY@@ x.py"\n', encoding="utf-8")
    monkeypatch.setattr(fl, "PROFILES_DIR", profile)
    u = build.Uklad(nazwa="natywny", system="windows", dane=WIN_DANE, py='"C:/Py thon/python.exe"')
    resolver = build.SourceResolver(EMPTY_LOCK, None, tmp_path / ".cache", {})
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    (tmp_path / "out").mkdir()
    with pytest.raises(SystemExit, match="config.yaml po podstawieniu tokenów"):
        build.build_agent(fleet, fleet.agent("jarvo-ads"), tmp_path / "out", EMPTY_LOCK, resolver, protocol, "D:/b",
                          ENV, None, [], uklad=u)


def test_katalogi_danych_floty_musza_byc_wzgledne():
    fleet = fl.load_fleet()
    for zle in ("/opt/data/jarvo/missions", "C:/dane/misje", "../misje", "jarvo//misje"):
        inna = dataclasses.replace(fleet, raw={**fleet.raw, "shared": {**fleet.raw["shared"], "missions_dir": zle}})
        with pytest.raises(SystemExit):
            build.sciezki_floty(inna, build.KONTENER)


def test_wspolne_skille_jarva_dostaja_tokeny(tmp_path, monkeypatch):
    """Wspólne skille floty (źródło repo-tree, shared/skills) dostają tokeny jak skille własne; plik bez tokenów
    zostaje bajt w bajt."""
    repo = tmp_path / "repo"
    skill = repo / "shared" / "skills" / "proba"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text('---\nname: proba\n---\nUruchom: @@PY@@ "@@REPO_DIR@@/scripts/x.py"\n', encoding="utf-8")
    (skill / "references" / "bez.md").write_bytes(b"bez tokenow\r\n")
    monkeypatch.setattr(fl, "REPO_ROOT", repo)
    lock = {"sources": {"jarvo": {"type": "repo-tree", "license": "MIT", "notice": "Jarvo"}},
            "agents": {"a": [{"source": "jarvo", "path": "shared/skills/proba", "dest": "wspolne/proba"}]}}
    out = tmp_path / "skills"
    out.mkdir()
    u = build.Uklad(nazwa="natywny", system="windows", repo="D:/app/1", py='"D:/Py thon/python.exe"')
    tokeny = build.sciezki_floty(fl.load_fleet(), u)
    build.vendor_skills("a", out, lock, build.SourceResolver(lock, None, tmp_path / "c", {}), [], None, tokeny)
    assert 'Uruchom: "D:/Py thon/python.exe" "D:/app/1/scripts/x.py"' in (out / "wspolne/proba/SKILL.md").read_text(
        encoding="utf-8")
    assert (out / "wspolne/proba/references/bez.md").read_bytes() == b"bez tokenow\r\n"
