"""Wybór dostawcy modeli floty: zestawy z fleet.yaml, nadpisania z tars.env, model hosta."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import fleetlib as fl  # noqa: E402


def test_default_is_openrouter():
    f = fl.load_fleet()
    f.apply_model_overrides({})
    assert f.provider == "openrouter" and f.model_for("frontier").startswith("anthropic/")


def test_preset_and_single_model_override():
    f = fl.load_fleet()
    f.apply_model_overrides({"TARS_MODEL_PROVIDER": "commandcode", "TARS_MODEL_FAST": "zai-org/GLM-5.3"})
    assert f.provider == "commandcode"
    assert f.model_for("frontier") == "deepseek/deepseek-v4-pro"
    assert f.model_for("fast") == "zai-org/GLM-5.3"


def test_unknown_provider_is_an_error():
    f = fl.load_fleet()
    with pytest.raises(ValueError, match="models.presets"):
        f.apply_model_overrides({"TARS_MODEL_PROVIDER": "nie-ma-takiego"})


def run_merge(tmp_path, fleet_model, target_model, force=False):
    src, dst = tmp_path / "fleet.yaml", tmp_path / "config.yaml"
    src.write_text(yaml.safe_dump({"model": fleet_model}), encoding="utf-8")
    if target_model is not None and not dst.exists():
        dst.write_text(yaml.safe_dump({"model": target_model}), encoding="utf-8")
    args = [sys.executable, str(REPO / "scripts" / "merge_host_config.py"), str(src), str(dst)]
    subprocess.run(args + (["--force-model"] if force else []), check=True, capture_output=True)
    return yaml.safe_load(dst.read_text(encoding="utf-8"))["model"]


def test_host_model_follows_fleet_but_keeps_manual_choice(tmp_path):
    orr = {"provider": "openrouter", "default": "anthropic/claude-haiku-4.5"}
    cc = {"provider": "commandcode", "default": "deepseek/deepseek-v4-flash"}
    assert run_merge(tmp_path, orr, None) == orr                 # brak modelu → z floty
    assert run_merge(tmp_path, cc, None) == cc                   # nietknięty → zmiana dostawcy floty
    manual = {"provider": "commandcode", "default": "claude-opus-5-5"}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"model": manual}), encoding="utf-8")
    assert run_merge(tmp_path, orr, None) == manual              # wybór z /model zostaje
