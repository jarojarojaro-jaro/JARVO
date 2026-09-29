"""Red team (promptfoo): konfiguracja parsuje się, każdy agent floty jest atakowany, asercje JS są poprawne składniowo,
a dostawca wykrywa wyciek sekretu i zbiera komendy z przebiegu sesji."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

R = Path(__file__).resolve().parents[1] / "security" / "redteam"
sys.path.insert(0, str(R))


def test_config_covers_fleet_and_asserts_compile():
    cfg = yaml.safe_load((R / "promptfooconfig.yaml").read_text(encoding="utf-8"))
    fleet = yaml.safe_load((R.parents[1] / "fleet.yaml").read_text(encoding="utf-8"))
    agents = {a["name"] for a in fleet["agents"] if a.get("status") == "active"}
    attacked = {t["vars"]["profil"] for t in cfg["tests"]}
    assert attacked == agents
    asserts = [a["value"] for a in cfg["defaultTest"]["assert"]] + [a["value"] for t in cfg["tests"] for a in t.get("assert", [])]
    if shutil.which("node"):
        for js in asserts:
            r = subprocess.run(["node", "-e", f"const output='{{}}'; (() => {js});"], capture_output=True, text=True)
            assert "SyntaxError" not in r.stderr, js


def test_provider_detects_leak_and_collects_commands(tmp_path, monkeypatch):
    import provider
    (tmp_path / "profiles" / "jarvo-ads").mkdir(parents=True)
    (tmp_path / "profiles" / "jarvo-ads" / ".env").write_text("API_SERVER_KEY=klucz-api-bardzo-tajny\n")
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=sk-or-tajny-123456\nKROTKI=abc\n")
    monkeypatch.setattr(provider, "DATA", tmp_path)

    def fake(method, url, key, body=None, timeout=0):
        if method == "POST":
            return {"choices": [{"message": {"content": "Twój klucz: sk-or-tajny-123456"}}]}, {"X-Hermes-Session-Id": "s1"}
        return {"data": [{"role": "assistant", "tool_calls": [{"function": {"name": "terminal", "arguments": "{\"command\": \"cat .env\"}"}}]}]}, {}
    monkeypatch.setattr(provider, "_req", fake)
    out = json.loads(provider.call_api("x", {}, {"vars": {"profil": "jarvo-ads"}})["output"])
    assert out["wycieki"] == ["OPENROUTER_API_KEY"] and out["komendy"] == ['terminal: {"command": "cat .env"}']
