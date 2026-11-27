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
    studio = repo_copy / "profiles/jarvo-studio"                       # profil w dawnym układzie (sam SOUL.md)
    for plik in ("ZASADY.md", "MAPA.md"):
        (studio / plik).unlink(missing_ok=True)
    zasady = repo_copy / "profiles/jarvo-web/ZASADY.md"                 # profil w układzie Jarva (SOUL + ZASADY)
    zasady.write_text(zasady.read_text(encoding="utf-8").replace(fl.PROTOCOL_MARKER, ""), encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"jarvo-studio: SOUL.md bez znacznika")
    assert errors_matching(report, r"jarvo-web: SOUL.md ani ZASADY.md bez znacznika")


def test_mapa_specjalisty(repo_copy):
    """22.11 właściciel: każdy agent jak Jarvo. Profil z ZASADY.md ma MAPA.md, znacznik mapy w ZASADY.md i sekcje z
    wiedza/mapa.py SEKCJE; rdzeń trafia do zbudowanego promptu."""
    fleet = fl.load_fleet(nakladka=None)
    web = fleet.agent("jarvo-web")
    protokol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    zbudowany = validate.zbudowany_prompt(fleet, web, protokol)
    assert fl.MAPA_MARKER not in zbudowany and "### Kim jestem\n- Profil `jarvo-web` Hermesa" in zbudowany
    assert "Jarvo:RDZEN" not in fl.rdzen_mapy(fleet, {}, "jarvo-web") and "### Gdzie co jest" not in fl.rdzen_mapy(fleet, {}, "jarvo-web")
    mapa = repo_copy / "profiles/jarvo-web/MAPA.md"
    tekst = mapa.read_text(encoding="utf-8")
    mapa.write_text(tekst + "\n## Ciekawostki\nNic.\n", encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"jarvo-web: MAPA.md ma sekcję 'Ciekawostki' spoza wiedza/mapa.py SEKCJE")
    mapa.unlink()
    zasady = repo_copy / "profiles/jarvo-sherlock/ZASADY.md"
    zasady.write_text(zasady.read_text(encoding="utf-8").replace(fl.MAPA_MARKER, ""), encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"jarvo-web: brak MAPA.md \(agent w układzie SOUL \+ ZASADY ma mapę")
    assert errors_matching(report, r"jarvo-web: <!-- Jarvo:MAPA --> bez MAPA.md")
    assert errors_matching(report, r"jarvo-sherlock: MAPA.md jest, a SOUL.md ani ZASADY.md nie ma <!-- Jarvo:MAPA -->")


def test_soul_postac_bez_procedur(repo_copy):
    """19.11 właściciel: w SOUL.md sam charakter; procedury, roster i protokół floty w ZASADY.md."""
    soul = repo_copy / "profiles/jarvo/SOUL.md"
    soul.write_text(soul.read_text(encoding="utf-8") + "\n" + fl.PROTOCOL_MARKER + "\n", encoding="utf-8")
    zasady = repo_copy / "profiles/jarvo/ZASADY.md"
    zasady.write_text(zasady.read_text(encoding="utf-8").replace(fl.PROTOCOL_MARKER, ""), encoding="utf-8")
    assert errors_matching(validate.run(), rf"jarvo: SOUL.md to sama postać; {fl.PROTOCOL_MARKER} należy do ZASADY.md")


def test_prompt_bez_przykladow(repo_copy):
    """24.11 właściciel: przykłady w prompcie naprowadzają model, więc SOUL i ZASADY to same ogólne zasady."""
    soul = repo_copy / "profiles/jarvo/SOUL.md"
    soul.write_text(soul.read_text(encoding="utf-8") + "\n<example>Ty: działa?\nJarvo: Działa.</example>\n", encoding="utf-8")
    zasady = repo_copy / "profiles/jarvo-web/ZASADY.md"
    zasady.write_text(zasady.read_text(encoding="utf-8") + "\nPrzykład raportu: Gotowe, sprawdzone.\n", encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"^jarvo: SOUL.md albo ZASADY.md z przykładem")
    assert errors_matching(report, r"^jarvo-web: SOUL.md albo ZASADY.md z przykładem")


def test_profile_yaml_must_parse(repo_copy):
    toolbox = repo_copy / "profiles/jarvo-web/toolbox.yaml"
    toolbox.write_text(toolbox.read_text(encoding="utf-8") + "\n  - name: x\n    source: https://x.dev (REST: /v2)\n",
                       encoding="utf-8")
    assert errors_matching(validate.run(), r"jarvo-web: toolbox.yaml nie jest poprawnym YAML")


def test_hq_chat_platform_must_be_configured(repo_copy):
    import re as _re
    cfg = repo_copy / "profiles/jarvo-web/config.yaml"
    cfg.write_text(_re.sub(r"^  api_server: .*\n", "", cfg.read_text(encoding="utf-8"), flags=_re.M), encoding="utf-8")
    jarvo = repo_copy / "profiles/jarvo/config.yaml"
    jarvo.write_text(jarvo.read_text(encoding="utf-8").replace("api_server: [kanban,", "api_server: ["),
                     encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"jarvo-web: config.yaml bez platform_toolsets.api_server")
    assert errors_matching(report, r"jarvo: orkiestrator bez toolsetu kanban na czacie HQ")
    assert not errors_matching(report, r"jarvo: .*terminal")     # Jarvo ma terminal w czacie (decyzja 2026-11-14)


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


def test_sekrety_wykryte_tez_w_repo_pod_katalogiem_claude(repo_copy, tmp_path, monkeypatch):
    """Repo w worktree pod .claude/worktrees/… : SKIP_DIRS liczone od korzenia repo, nie od korzenia dysku
    (wcześniej każdy plik miał w ścieżce „.claude”, więc kontrola sekretów nic nie sprawdzała)."""
    import fleetlib as fl
    worktree = tmp_path / ".claude" / "worktrees" / "wf-1"
    worktree.parent.mkdir(parents=True)
    repo_copy.rename(worktree)
    monkeypatch.setattr(fl, "REPO_ROOT", worktree)
    fake_key = "sk-or-v1-" + "cd" * 16
    (worktree / "shared" / "notatka.md").write_text(f"klucz: {fake_key}\n", encoding="utf-8")
    report = validate.Report()
    validate.check_secrets(report)
    assert errors_matching(report, r"shared/notatka.md: wygląda na klucz OpenRouter")
    (worktree / ".claude").mkdir()                       # katalog .claude W repo dalej pomijany
    (worktree / ".claude" / "x.md").write_text(f"{fake_key}\n", encoding="utf-8")
    report = validate.Report()
    validate.check_secrets(report)
    assert not errors_matching(report, r"\.claude/x.md")


def test_too_few_evals(repo_copy):
    path = repo_copy / "evals/jarvo-web/scenarios.yaml"
    data = fl.load_yaml(path)
    data["scenarios"] = data["scenarios"][:4]
    path.write_text(fl.dump_yaml(data), encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"jarvo-web: 4 scenariuszy evals < 10")


def test_unpinned_lock_source(repo_copy):
    lock = repo_copy / "vendor/skills.lock.yaml"
    text = lock.read_text(encoding="utf-8")
    text = re.sub(r"rev: \"?[0-9a-f]{40}\"?", "rev: main", text, count=1)
    lock.write_text(text, encoding="utf-8")
    assert errors_matching(validate.run(), r"musi być przypięte do pełnego SHA")


def _lock_z_podmiana(repo_copy, stare: str, nowe: str) -> validate.Report:
    lock = repo_copy / "vendor/skills.lock.yaml"
    text = lock.read_text(encoding="utf-8")
    assert stare in text
    lock.write_text(text.replace(stare, nowe, 1), encoding="utf-8")
    report = validate.Report()
    validate.check_lock(fl.load_fleet(), {}, report)
    return report


def test_lock_nakladka_w_skillu_wlasnym(repo_copy):
    """Wpis kategoria/nazwa/podkatalog w skillu własnym agenta (nakładka) przechodzi, z `pomin: [SKILL.md]`."""
    report = validate.Report()
    validate.check_lock(fl.load_fleet(), {}, report)
    assert not errors_matching(report, r"modern-web-guidance"), report.errors
    nazwy = fl.skille_z_locka(fl.load_lock(), "jarvo-web")
    assert "upstream" not in nazwy and "modern-web-guidance" not in nazwy    # dane nakładki to nie osobny skill


def test_lock_nakladka_bez_skilla_wlasnego(repo_copy):
    report = _lock_z_podmiana(repo_copy, "dest: web/modern-web-guidance/upstream", "dest: web/nie-ma-takiego/upstream")
    assert errors_matching(report, r"lock/jarvo-web: dest 'web/nie-ma-takiego/upstream': podkatalog tylko w skillu własnym")


def test_lock_pomin_skill_md_tylko_w_nakladce(repo_copy):
    report = _lock_z_podmiana(repo_copy, 'dest: design/lemo-wake-layers, pomin: ["scripts"]',
                              'dest: design/lemo-wake-layers, pomin: ["scripts", "SKILL.md"]')
    assert errors_matching(report, r"design/lemo-wake-layers: `pomin` to lista wzorców plików")
    assert not errors_matching(report, r"modern-web-guidance")


def test_cron_script_must_exist(repo_copy):
    (repo_copy / "profiles/jarvo/scripts/brief_daily.py").unlink()
    assert errors_matching(validate.run(), r"jarvo/cron/jarvo-daily-brief: brak skryptu scripts/brief_daily.py")


def test_zrodla_paczka_tylko_tar_albo_zip(repo_copy):
    """Źródło bez repo git (`paczka` w vendor/zrodla.yaml): archiwum tar albo zip (platform-tools), inne nie."""
    p = repo_copy / "vendor" / "zrodla.yaml"
    p.write_text(p.read_text(encoding="utf-8")
                 + f"  paczka-zip:\n    paczka: https://example.com/narzedzie.zip\n    status: czeka\n"
                   f"    przejrzane: {'c' * 64}\n"
                   f"  paczka-rar:\n    paczka: https://example.com/narzedzie.rar\n    status: czeka\n"
                   f"    przejrzane: {'d' * 64}\n", encoding="utf-8")
    report = validate.Report()
    validate.check_zrodla(report)
    assert errors_matching(report, r"zrodla/paczka-rar: paczka musi być adresem https archiwum .* / \.zip")
    assert not errors_matching(report, r"paczka-zip|android-platform-tools")


def test_profile_without_fleet_entry(repo_copy):
    (repo_copy / "profiles/jarvo-nieznany").mkdir()
    (repo_copy / "profiles/jarvo-nieznany/SOUL.md").write_text("# Nieznany\n", encoding="utf-8")
    assert errors_matching(validate.run(), r"profiles/jarvo-nieznany: brak wpisu w fleet.yaml")
    # resztka po profilu usuniętym z repo (sam __pycache__, git go nie kasuje) to nie profil
    (repo_copy / "profiles/jarvo-dawny/scripts/__pycache__").mkdir(parents=True)
    (repo_copy / "profiles/jarvo-dawny/scripts/__pycache__/x.cpython-313.pyc").write_bytes(b"\0")
    assert not errors_matching(validate.run(), r"profiles/jarvo-dawny")


def test_watek_telegrama_tylko_jarvo_biznesowi_i_wlasny_uchwyt(repo_copy):
    """Decyzja 16.11: specjalista pracuje przez Jarva; 25.11 właściciel dał Bigshortowi i Hackerowi własne wątki, więc
    specjalista może mieć wątek tylko pod swoim uchwytem, nigdy cudzy temat."""
    p = repo_copy / "fleet.yaml"
    tekst = p.read_text(encoding="utf-8")
    p.write_text(tekst.replace("  - name: jarvo-web\n", "  - name: jarvo-web\n    telegram_topic: sklep\n", 1), encoding="utf-8")
    assert errors_matching(validate.run(), r"jarvo-web: telegram_topic tylko u Jarva")
    p.write_text(tekst.replace("  - name: jarvo-web\n", "  - name: jarvo-web\n    telegram_topic: web\n", 1), encoding="utf-8")
    assert not errors_matching(validate.run(), r"jarvo-web: telegram_topic")


def test_docs_count_must_match_repo(repo_copy):
    import shutil
    shutil.rmtree(repo_copy / "profiles/jarvo-studio/skills/studio/copy-pl")
    assert errors_matching(validate.run(), r"docs/FLEET.md: jarvo-studio ma 6 \(skille\), a tabela podaje 7")


def test_docs_handle_column_must_match_fleet(repo_copy):
    doc = repo_copy / "docs/JARVO-CALOSC.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace("| `@web` |", "| `@webb` |", 1), encoding="utf-8")
    assert errors_matching(validate.run(), r"docs/JARVO-CALOSC.md: jarvo-web ma uchwyt @web, a tabela podaje")


def test_docs_must_list_whole_fleet(repo_copy):
    readme = repo_copy / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("`jarvo-web`", "jarvo-web"), encoding="utf-8")
    assert errors_matching(validate.run(), r"README.md: brak agenta `jarvo-web`")


def test_docs_broken_link_and_anchor(repo_copy):
    (repo_copy / "docs/NOWY.md").write_text("[a](PLAN.md#nie-ma-takiej) [b](BRAK.md) [c](PLAN.md#6-roadmapa)\n",
                                            encoding="utf-8")
    report = validate.run()
    assert errors_matching(report, r"docs/NOWY.md: kotwica #nie-ma-takiej nie istnieje w PLAN.md")
    assert errors_matching(report, r"docs/NOWY.md: link do nieistniejącego BRAK.md")
    assert not errors_matching(report, r"6-roadmapa")


# ---------------------------------------------------------------- routing: nowy agent nie może być „niewidzialny”

def test_specialist_without_handoff_line(repo_copy):
    fy = repo_copy / "fleet.yaml"
    tekst = fy.read_text(encoding="utf-8")
    linia = next(l for l in tekst.splitlines() if l.strip().startswith("oddaj_gdy: \"szukanie klientów"))
    fy.write_text(tekst.replace(linia + "\n", ""), encoding="utf-8")
    assert errors_matching(validate.run(), r"jarvo-lowca: brak `oddaj_gdy`")


def test_specialist_missing_from_dispatch_patterns(repo_copy):
    p = repo_copy / "profiles/jarvo" / validate.PATTERNS_FILE
    p.write_text(p.read_text(encoding="utf-8").replace("`jarvo-ads`", "Ads"), encoding="utf-8")
    assert errors_matching(validate.run(), r"jarvo-ads: nie występuje w żadnym wzorcu misji")


def test_service_command_needs_requirement(repo_copy):
    sk = repo_copy / "profiles/jarvo-ads/skills/ads/start-kampanii/SKILL.md"
    sk.write_text("\n".join(l for l in sk.read_text(encoding="utf-8").splitlines() if "wymaga:" not in l) + "\n", encoding="utf-8")
    assert errors_matching(validate.run(), r"jarvo-ads/start-kampanii: używa poleceń usługi 'skarbiec'")


def test_unknown_required_service(repo_copy):
    sk = repo_copy / "profiles/jarvo-ads/skills/ads/start-kampanii/SKILL.md"
    sk.write_text(sk.read_text(encoding="utf-8").replace("wymaga: [skarbiec]", "wymaga: [skarbiec, skarbonka]"), encoding="utf-8")
    assert errors_matching(validate.run(), r"wymaga nieznanej usługi 'skarbonka'")
