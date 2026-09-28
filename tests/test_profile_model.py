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


def test_panel_choice_recalibrates_soul(tmp_path):
    """Model zmieniony w panelu dostaje w SOUL kalibrację swojej rodziny (ta sama rola)."""
    sys.path.insert(0, str(SCRIPT.parent))
    import fleetlib as fl

    soul = f"# Web\n\nprotokół\n\n{fl.calibration_section('gpt-6-luna', False)}\n\n## Język\n"
    cfg(tmp_path, "openai-codex", "gpt-6-luna"); step(tmp_path, "restore")
    cfg(tmp_path, "openrouter", "anthropic/claude-sonnet-5")               # zmiana w panelu
    step(tmp_path, "snapshot")
    cfg(tmp_path, "openai-codex", "gpt-6-luna")                            # aktualizacja floty
    (tmp_path / "SOUL.md").write_text(soul, encoding="utf-8")              # SOUL z buildu (pod GPT)
    step(tmp_path, "restore")
    new = (tmp_path / "SOUL.md").read_text(encoding="utf-8")
    assert "(anthropic/claude-sonnet-5)" in new and "gpt-6-luna" not in new
    assert "<!-- Jarvo:CALIBRATION wykonawca -->" in new and new.endswith("## Język\n")
