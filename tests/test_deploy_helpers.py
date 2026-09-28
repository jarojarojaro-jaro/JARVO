"""Skrypty wdrożenia: scalanie sekretów, configu hosta i czyszczenie skilli po zmianie buildu."""

from __future__ import annotations

import stat

import fleetlib as fl
import merge_env
import merge_host_config
import prune_skills


# ------------------------------------------------------------------ merge_env

def test_merge_env_updates_keeps_and_protects(tmp_path, capsys):
    src = tmp_path / "src.env"
    dst = tmp_path / "profile" / ".env"
    dst.parent.mkdir()
    dst.write_text("# komentarz Hermesa\nOPENROUTER_API_KEY=stary\nWLASNY=zostaje\nPUSTY_W_ZRODLE=istniejacy\n",
                   encoding="utf-8")
    src.write_text('OPENROUTER_API_KEY=nowy\nPUSTY_W_ZRODLE=\nNOWY="x y"\nexport EXPORTED=1\n# KOMENTARZ=nie\n',
                   encoding="utf-8")
    merge_env.main([str(src), str(dst)])
    lines = dst.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# komentarz Hermesa"
    assert "OPENROUTER_API_KEY=nowy" in lines
    assert "WLASNY=zostaje" in lines
    assert "PUSTY_W_ZRODLE=istniejacy" in lines           # pusta wartość w szablonie nie zeruje
    assert 'NOWY="x y"' in lines and "EXPORTED=1" in lines
    assert not any(line.startswith("KOMENTARZ") for line in lines)
    assert stat.S_IMODE(dst.stat().st_mode) == 0o600
    out = capsys.readouterr().out
    assert "nowy" not in out and "OPENROUTER_API_KEY" in out   # nazwy kluczy tak, wartości nigdy


def test_merge_env_missing_source_is_noop(tmp_path):
    dst = tmp_path / ".env"
    dst.write_text("A=1\n", encoding="utf-8")
    merge_env.main([str(tmp_path / "brak.env"), str(dst)])
    assert dst.read_text(encoding="utf-8") == "A=1\n"


# ------------------------------------------------------------ merge_host_config

def test_merge_host_config(tmp_path):
    fleet_cfg = tmp_path / "flota.yaml"
    target = tmp_path / "config.yaml"
    fleet_cfg.write_text(fl.dump_yaml({
        "model": {"default": "anthropic/claude-haiku-4.5", "provider": "openrouter"},
        "timezone": "Europe/Warsaw",
        "platform_toolsets": {"telegram": ["kanban"]},
        "gateway": {"multiplex_profiles": True, "profile_routes": [{"name": "owner-dm", "chat_id": "1"}]},
        "kanban": {"dispatch_in_gateway": True},
        "platforms": {"telegram": {"require_mention": True}},
    }), encoding="utf-8")
    target.write_text(fl.dump_yaml({
        "model": {"default": "wybrany/w-setupie"},
        "custom": {"zostaje": True},
        "platform_toolsets": {"telegram": ["terminal"], "discord": ["web"]},
        "gateway": {"profile_routes": [{"name": "stara"}], "port": 8080},
        "platforms": {"telegram": {"token_env": "TELEGRAM_BOT_TOKEN"}},
    }), encoding="utf-8")
    merge_host_config.main([str(fleet_cfg), str(target)])
    out = fl.load_yaml(target)
    assert out["model"]["default"] == "wybrany/w-setupie"          # nie nadpisujemy wyboru z setupu
    assert out["custom"] == {"zostaje": True}
    assert out["platform_toolsets"] == {"telegram": ["kanban"]}     # zastąpione w całości
    assert out["gateway"]["port"] == 8080 and out["gateway"]["multiplex_profiles"] is True
    assert out["gateway"]["profile_routes"] == [{"name": "owner-dm", "chat_id": "1"}]
    assert out["platforms"]["telegram"] == {"token_env": "TELEGRAM_BOT_TOKEN", "require_mention": True}
    assert out["kanban"]["dispatch_in_gateway"] is True
    assert out["timezone"] == "Europe/Warsaw"


def test_merge_host_config_sets_model_when_missing(tmp_path):
    fleet_cfg = tmp_path / "flota.yaml"
    target = tmp_path / "config.yaml"
    fleet_cfg.write_text(fl.dump_yaml({"model": {"default": "anthropic/claude-haiku-4.5"}}), encoding="utf-8")
    merge_host_config.main([str(fleet_cfg), str(target)])
    assert fl.load_yaml(target)["model"]["default"] == "anthropic/claude-haiku-4.5"


def test_merge_host_config_force_model_on_first_run(tmp_path):
    fleet_cfg = tmp_path / "flota.yaml"
    target = tmp_path / "config.yaml"
    fleet_cfg.write_text(fl.dump_yaml({"model": {"default": "anthropic/claude-haiku-4.5", "provider": "openrouter"}}),
                         encoding="utf-8")
    target.write_text(fl.dump_yaml({"model": {"default": "przyklad/z-obrazu", "provider": "auto"}}), encoding="utf-8")
    merge_host_config.main([str(fleet_cfg), str(target), "--force-model"])
    assert fl.load_yaml(target)["model"] == {"default": "anthropic/claude-haiku-4.5", "provider": "openrouter"}


# ---------------------------------------------------------------- prune_skills

def skill(root, rel, frontmatter_extra="", vendored=False):
    d = root / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {d.name}\ndescription: test\n{frontmatter_extra}---\n\nTreść\n",
                                encoding="utf-8")
    if vendored:
        (d / ".vendored.json").write_text("{}", encoding="utf-8")
    return d


def test_prune_removes_only_managed_skills_missing_from_build(tmp_path):
    build, profile = tmp_path / "build", tmp_path / "profile"
    skill(build, "web/audyt-strony", "metadata:\n  jarvo:\n    agent: jarvo-web\n")
    skill(profile, "web/audyt-strony", "metadata:\n  jarvo:\n    agent: jarvo-web\n")
    old_own = skill(profile, "web/stary-workflow", "metadata:\n  jarvo:\n    agent: jarvo-web\n")
    old_vendor = skill(profile, "marketing/competitors", vendored=True)
    agent_made = skill(profile, "moje/wlasny-skill")
    hidden = skill(profile, ".archive/cos", "metadata:\n  jarvo:\n    agent: jarvo-web\n")

    prune_skills.main([str(build), str(profile), "--dry-run"])
    assert old_own.exists() and old_vendor.exists()

    prune_skills.main([str(build), str(profile)])
    assert not old_own.exists() and not old_vendor.exists()
    assert (profile / "web/audyt-strony").exists()
    assert agent_made.exists() and hidden.exists()


# ------------------------------------------------------------------ check-pins

def test_version_range_check():
    from conftest import load_script
    pins = load_script("scripts/check-pins.py")
    ok = pins.node_satisfies
    assert ok(None, "26.5.1") is True
    assert ok(">=22.18.0", "26.5.1") is True
    assert ok("^22.22.0 || >= 24.8.0", "26.5.1") is True
    assert ok("^22.22.0 || >= 24.8.0", "23.1.0") is False
    assert ok(">=18 <20", "26.5.1") is False
    assert ok("<4.0 >=3.11", "3.12.0") is True
    assert ok(">=3.13", "3.12.0") is False
