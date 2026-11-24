"""Bloki Hermesa w prompcie Jarva (profiles/jarvo/config.yaml): bez sprzecznych z SOUL, z prawdziwym hintem panelu.

Test konfiguracji działa zawsze. Render promptu prawdziwym kodem Hermesa (offline: atrapa klucza, kopia profilu
w tmp, bez sieci) uruchamia się tylko przy JARVO_TEST_HERMES_SRC=/ścieżka/do/hermes-agent i JARVO_HERMES_PYTHON
(Python z zależnościami Hermesa), jak pełny build w test_build.py.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

import fleetlib as fl

KONFIG = fl.REPO_ROOT / "profiles" / "jarvo" / "config.yaml"


def _cfg() -> dict:
    return fl.load_yaml(KONFIG)


def _katalogi_podgladu() -> tuple[str, ...]:
    """PREVIEW_ROOTS z hq/plugin/hq_core.py bez importu modułu (ciężkie zależności panelu)."""
    drzewo = ast.parse((fl.REPO_ROOT / "hq" / "plugin" / "hq_core.py").read_text(encoding="utf-8"))
    for wezel in drzewo.body:
        if isinstance(wezel, ast.Assign) and any(getattr(t, "id", "") == "PREVIEW_ROOTS" for t in wezel.targets):
            return tuple(ast.literal_eval(wezel.value))
    raise AssertionError("brak PREVIEW_ROOTS w hq_core.py")


def test_bez_angielskich_wskazowek_powtorzonych_w_zasadach():
    """24.11: bloki Hermesa, które ZASADY Jarva mówią jednym zdaniem po polsku, wyłączone jawnie, nie „auto”
    (dla deepseek „auto” = włączony): Execution discipline, Finishing the job, Parallel tool calls, Tool-use enforcement."""
    agent = _cfg()["agent"]
    for klucz in ("execution_guidance", "task_completion_guidance", "parallel_tool_call_guidance", "tool_use_enforcement"):
        assert agent[klucz] is False, klucz


def test_skill_manage_jarva_przez_poczekalnie():
    """Skille Jarva to kod floty: zapis skill_manage czeka na zgodę właściciela, Jarvo sam ich nie tworzy."""
    sk = _cfg()["skills"]
    assert sk["write_approval"] is True
    assert int(sk.get("creation_nudge_interval") or 0) == 0


def test_vision_na_telegramie_i_w_panelu():
    """Protokół 10: obraz od człowieka Jarvo ogląda vision_analyze, więc toolset vision jest na każdej platformie czatu."""
    toolsety = _cfg()["platform_toolsets"]
    for platforma in ("telegram", "api_server", "cli"):
        assert "vision" in toolsety[platforma], platforma


def test_hint_panelu_mowi_prawde_o_markdown_i_plikach():
    """api_server = czat aplikacji Jarvo: Markdown się renderuje, MEDIA: i pełna ścieżka dają kartę pliku, podgląd
    tylko z katalogów PREVIEW_ROOTS (domyślny hint Hermesa mówi „plain text” i „MEDIA: renders as literal text”)."""
    spec = _cfg()["platform_hints"]["api_server"]
    tekst = spec["replace"]
    assert "append" not in spec
    assert "Markdown się renderuje" in tekst
    assert "MEDIA:<pełna ścieżka>" in tekst and "![opis](<pełna ścieżka>)" in tekst
    assert "@@JARVO_DIR@@/" in tekst
    for katalog in _katalogi_podgladu():
        assert re.search(rf"\b{katalog}\b", tekst), katalog
    assert "plain text" not in tekst


HERMES_SRC = os.environ.get("JARVO_TEST_HERMES_SRC")
HERMES_PY = os.environ.get("JARVO_HERMES_PYTHON")

RENDER = r"""
import json, sys
from hermes_cli.prompt_size import _build_inspection_agent
from hermes_cli.config import load_config
from hermes_cli.tools_config import _get_platform_tools
from agent.system_prompt import build_system_prompt_parts
cfg = load_config()
wynik = {}
for platforma in ("telegram", "api_server"):
    czesci = build_system_prompt_parts(_build_inspection_agent(platforma))
    wynik[platforma] = {"prompt": "\n\n".join(p for p in czesci.values() if p),
                        "toolsety": sorted(_get_platform_tools(cfg, platforma))}
print("WYNIK " + json.dumps(wynik, ensure_ascii=False))
"""


@pytest.mark.skipif(not (HERMES_SRC and HERMES_PY),
                    reason="ustaw JARVO_TEST_HERMES_SRC i JARVO_HERMES_PYTHON, aby złożyć prompt kodem Hermesa")
def test_prompt_zlozony_przez_hermesa(tmp_path):
    """Prompt Jarva złożony build_system_prompt_parts z configiem repo (model deepseek, przy którym bramka „auto”
    włącza Execution discipline): bez sprzecznych bloków, z polskim hintem panelu i z toolsetem vision."""
    home = tmp_path / "root" / "profiles" / "jarvo"
    (home / "skills" / "fleet" / "intake").mkdir(parents=True)
    (home / "skills" / "fleet" / "intake" / "SKILL.md").write_text(
        "---\nname: intake\ndescription: Przyjmuję zlecenie.\n---\n# Intake\n", encoding="utf-8")
    (home / "SOUL.md").write_text("# Jarvo\n", encoding="utf-8")
    tokeny = {"MODEL": "deepseek/deepseek-v4.1-flash", "DELEGATION_MODEL": "deepseek/deepseek-v4.1-flash",
              "PROVIDER": "openrouter", "TIMEZONE": "Europe/Warsaw"}
    tekst = re.sub(r"@@([A-Z_]+)@@", lambda m: tokeny.get(m.group(1), str(tmp_path / "dane" / m.group(1).lower())),
                   KONFIG.read_text(encoding="utf-8"))
    (home / "config.yaml").write_text(tekst, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_API_KEY", "_TOKEN"))}
    env.update(HERMES_HOME=str(home), HOME=str(tmp_path), PYTHONUTF8="1")
    wyjscie = subprocess.run([HERMES_PY, "-c", RENDER], cwd=HERMES_SRC, env=env, capture_output=True, text=True,
                             timeout=300, check=True).stdout
    wynik = json.loads(next(l for l in wyjscie.splitlines() if l.startswith("WYNIK "))[len("WYNIK "):])
    for platforma, dane in wynik.items():
        prompt = dane["prompt"]
        assert "# Execution discipline" not in prompt, platforma
        assert "confirm scope before executing" not in prompt, platforma
        assert "Current facts (weather, news, versions)" not in prompt, platforma
        for blok in ("# Finishing the job", "# Parallel tool calls", "# Tool-use enforcement"):
            assert blok not in prompt, (platforma, blok)
        assert "vision" in dane["toolsety"], platforma
    assert "Markdown się renderuje" in wynik["api_server"]["prompt"]
    assert "assume plain text" not in wynik["api_server"]["prompt"]
    assert "Rozmawiam na Telegramie" in wynik["telegram"]["prompt"]
    assert "You are on Telegram" not in wynik["telegram"]["prompt"]
