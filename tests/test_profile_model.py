"""Model agenta wybrany w panelu przetrwa aktualizację; nietknięty idzie za flotą."""

import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "profile_model.py"


def cfg(p, provider, model):
    (p / "config.yaml").write_text(yaml.safe_dump({"model": {"provider": provider, "default": model}, "x": 1}), encoding="utf-8")


def step(p, action):
    subprocess.run([sys.executable, str(SCRIPT), action, str(p)], check=True, capture_output=True)


def model(p):
    return yaml.safe_load((p / "config.yaml").read_text(encoding="utf-8"))["model"]


def update(p, fleet_provider, fleet_model):
    step(p, "snapshot"); cfg(p, fleet_provider, fleet_model); step(p, "restore")


def test_fleet_change_applies_when_untouched(tmp_path):
    cfg(tmp_path, "openrouter", "a"); step(tmp_path, "restore")          # pierwsza instalacja
    update(tmp_path, "commandcode", "deepseek/deepseek-v4-pro")
    assert model(tmp_path) == {"provider": "commandcode", "default": "deepseek/deepseek-v4-pro"}


def test_panel_choice_survives_update(tmp_path):
    cfg(tmp_path, "commandcode", "deepseek/deepseek-v4-pro"); step(tmp_path, "restore")
    cfg(tmp_path, "commandcode", "zai-org/GLM-5.1")                     # zmiana w panelu
    update(tmp_path, "commandcode", "deepseek/deepseek-v4-pro")
    assert model(tmp_path) == {"provider": "commandcode", "default": "zai-org/GLM-5.1"}
    update(tmp_path, "commandcode", "deepseek/deepseek-v4-pro")         # kolejne aktualizacje też
    assert model(tmp_path)["default"] == "zai-org/GLM-5.1"
