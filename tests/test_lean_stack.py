"""Lekki stos pod VPS 8 GB: jarvo-stt (napisy), to_pdf (bez Gotenberga), budżet RAM compose, higiena obrazu."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import fleetlib as fl
import merge_host_config
from conftest import REPO, load_script


def load_stt():
    loader = importlib.machinery.SourceFileLoader("jarvo_stt", str(REPO / "infra" / "bin" / "jarvo-stt"))
    spec = importlib.util.spec_from_loader("jarvo_stt", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["jarvo_stt"] = module
    loader.exec_module(module)
    return module


# ------------------------------------------------------------------ jarvo-stt

def seg(start, end, tokens, stamps):
    return SimpleNamespace(start=start, end=end, text="".join(tokens).strip(), tokens=tokens, timestamps=stamps)


def test_stt_words_use_absolute_time_and_join_subword_tokens():
    stt = load_stt()
    s = seg(10.0, 12.0, [" Dzie", "ń", " dob", "ry", "."], [0.0, 0.2, 0.5, 0.7, 0.9])
    assert stt.words(s) == [(10.0, 10.5, "Dzień"), (10.5, 12.0, "dobry.")]


def test_stt_srt_lines_respect_max_chars_and_segments():
    stt = load_stt()
    a = seg(0.0, 3.0, [" Proszę", " przygotować", " raport", " o", " konkurencji"], [0.0, 0.5, 1.2, 1.8, 2.0])
    b = seg(5.0, 6.0, [" Dzięki"], [0.1])
    lines = stt.srt_lines([a, b], max_chars=20)
    assert [t for _, _, t in lines] == ["Proszę przygotować", "raport o konkurencji", "Dzięki"]
    assert all(len(t) <= 20 for _, _, t in lines)
    assert lines[1][0] == pytest.approx(1.2) and lines[2][0] == pytest.approx(5.1)   # linie nie przeskakują segmentów


def test_stt_spoken_words_keep_pauses_inside_segment():
    stt = load_stt()
    # "Dzień" o 10.0, potem 1,5 s ciszy i "dobry" o 11.5: koniec "Dzień" nie może sięgać 11.5
    s = seg(10.0, 12.5, [" Dzie", "ń", " dob", "ry"], [0.0, 0.2, 1.5, 1.7])
    (a0, b0, w0), (a1, b1, w1) = stt.spoken(s)
    assert (w0, w1) == ("Dzień", "dobry") and a0 == 10.0 and a1 == 11.5
    assert b0 < 10.8 and b1 <= 12.5


def test_stt_segment_without_tokens_and_time_format():
    stt = load_stt()
    s = SimpleNamespace(start=1.0, end=2.5, text=" Tak. ", tokens=None, timestamps=None)
    assert stt.words(s) == [(1.0, 2.5, "Tak.")]
    assert stt.srt_time(3723.4567) == "01:02:03,457"


def test_stt_command_template_matches_image_env(tmp_path, monkeypatch):
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    m = re.search(r'HERMES_LOCAL_STT_COMMAND="([^"]+)"', docker)
    assert m, "obraz musi ustawiać HERMES_LOCAL_STT_COMMAND"
    tpl = m.group(1)
    assert tpl.startswith("/opt/jarvo/bin/jarvo-stt ") and "{input_path}" in tpl and "{output_dir}" in tpl
    # szablon po podstawieniu przez Hermesa musi przejść przez argparse jarvo-stt (brak pliku → kod 2, bez modelu)
    stt = load_stt()
    monkeypatch.setattr(stt, "load", lambda: pytest.fail("model nie powinien się ładować"))
    argv = tpl.format(input_path=str(tmp_path / "brak.ogg"), output_dir=str(tmp_path), language="pl",
                      model="base").split()[1:]
    assert stt.main(argv) == 2


# ------------------------------------------------------------------ to_pdf

@pytest.fixture
def to_pdf(monkeypatch):
    mod = load_script("profiles/jarvo-reka/scripts/to_pdf.py")
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append([str(c) for c in cmd])
        if cmd[0] == "pandoc":
            Path(cmd[cmd.index("-o") + 1]).write_text("<html><head></head><body>x</body></html>", encoding="utf-8")
        for c in cmd:
            if str(c).startswith("--print-to-pdf="):
                Path(str(c).split("=", 1)[1]).write_bytes(b"%PDF-1.7")
        if "--convert-to" in cmd:
            src = Path(cmd[-1])
            (Path(cmd[cmd.index("--outdir") + 1]) / (src.stem + ".pdf")).write_bytes(b"%PDF-1.7")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "chromium", lambda: "/usr/local/bin/chromium")
    return mod, calls


def test_to_pdf_markdown_goes_pandoc_then_chromium(to_pdf, tmp_path, monkeypatch):
    mod, calls = to_pdf
    monkeypatch.setattr(mod, "soffice", lambda: None)
    src = tmp_path / "raport.md"
    src.write_text("# Raport", encoding="utf-8")
    assert mod.main([str(src), str(tmp_path / "out" / "raport.pdf")]) == 0
    assert calls[0][0] == "pandoc" and "--embed-resources" in calls[0]
    assert calls[1][0] == "/usr/local/bin/chromium" and "--no-pdf-header-footer" in calls[1]
    assert (tmp_path / "out" / "raport.pdf").read_bytes().startswith(b"%PDF")


def test_to_pdf_docx_prefers_libreoffice_and_falls_back_to_pandoc(to_pdf, tmp_path, monkeypatch):
    mod, calls = to_pdf
    src = tmp_path / "umowa.docx"
    src.write_bytes(b"PK")
    monkeypatch.setattr(mod, "soffice", lambda: "/usr/bin/soffice")
    mod.main([str(src), str(tmp_path / "a.pdf")])
    assert calls[-1][0] == "/usr/bin/soffice"
    calls.clear()
    monkeypatch.setattr(mod, "soffice", lambda: None)
    mod.main([str(src), str(tmp_path / "b.pdf")])
    assert [c[0] for c in calls] == ["pandoc", "/usr/local/bin/chromium"]


def test_to_pdf_spreadsheet_without_libreoffice_explains_extra(to_pdf, tmp_path, monkeypatch):
    mod, _ = to_pdf
    monkeypatch.setattr(mod, "soffice", lambda: None)
    src = tmp_path / "budzet.xlsx"
    src.write_bytes(b"PK")
    with pytest.raises(SystemExit, match="JARVO_EXTRAS=\"office\""):
        mod.main([str(src), str(tmp_path / "b.pdf")])


# ------------------------------------------------------------------ compose: budżet 8 GB

def mem_bytes(v: str) -> int:
    m = re.fullmatch(r"(?:\$\{[A-Z_]+:-)?(\d+)([kmgKMG])[bB]?\}?", str(v).strip())
    assert m, v
    return int(m.group(1)) * {"k": 1024, "m": 1024**2, "g": 1024**3}[m.group(2).lower()]


def test_compose_fits_8gb_vps_and_has_no_heavy_sidecars():
    compose = yaml.safe_load((REPO / "infra" / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "crawl4ai" not in services and "gotenberg" not in services
    default = {n: s for n, s in services.items() if not s.get("profiles")}
    total = 0
    for name, svc in default.items():
        limit = ((svc.get("deploy") or {}).get("resources") or {}).get("limits", {}).get("memory")
        assert limit, f"{name}: brak limitu pamięci"
        total += mem_bytes(limit)
    assert total <= 6 * 1024**3, f"domyślne usługi mogą zająć {total / 1024**3:.1f} GB (budżet 6 GB na VPS 8 GB)"
    env = " ".join(str(v) for v in services["hermes"]["environment"].values())
    assert "CRAWL4AI" not in env and "GOTENBERG" not in env


def test_env_example_matches_compose_defaults():
    example = (REPO / "infra" / "env" / "compose.env.example").read_text(encoding="utf-8")
    assert "HERMES_MEM_LIMIT=5g" in example and "JARVO_EXTRAS=" in example
    assert "CRAWL4AI" not in example and "GOTENBERG" not in example and "INSTALL_DOCLING" not in example


def test_every_agent_has_secrets_template():
    """bootstrap-vps.sh i local-up.sh zakładają secrets/<agent>.env tylko z szablonów: bez szablonu agent zostaje bez pliku."""
    import fleetlib as fl
    templates = {p.name.removesuffix(".env.example") for p in (REPO / "infra/env/secrets").glob("*.env.example")}
    missing = {a.name for a in fl.load_fleet().active()} - templates
    assert not missing, f"brak infra/env/secrets/<agent>.env.example dla: {sorted(missing)}"


# ------------------------------------------------------------------ obraz

def test_dockerfile_hygiene():
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    code = "\n".join(line for line in docker.splitlines() if not line.lstrip().startswith("#"))
    assert "UV_NO_CACHE=1" in code                       # cache uv (~1,9 GB) nie trafia do warstw
    assert not re.search(r"chmod\s+-R\b", code)          # chmod -R kopiuje cały katalog do nowej warstwy
    assert "install-browser" not in code                 # bez drugiej Chromium dla dembrandta
    assert "AGENT_BROWSER_EXECUTABLE_PATH" not in code   # przejąłby też silnik lightpanda
    assert re.search(r"LIGHTPANDA_IMAGE=lightpanda/browser:[\d.]+@sha256:[0-9a-f]{64}", code)


def test_every_extra_has_a_pin():
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    optional = (REPO / "infra" / "python" / "requirements-optional.txt").read_text(encoding="utf-8")
    loop = re.search(r"for x in ([a-z ]+); do", docker)
    assert loop
    for extra in loop.group(1).split():
        pkg = "auto-editor" if extra == "media" else extra
        assert re.search(rf"^{re.escape(pkg)}(\[[^\]]*\])?==", optional, re.M), extra
    tools = (REPO / "infra" / "python" / "requirements-tools.txt").read_text(encoding="utf-8")
    assert "faster-whisper" not in tools and "onnx-asr" in tools


def test_node_tools_drop_heavy_packages_and_share_chromium():
    import json
    pkg = json.loads((REPO / "infra" / "node" / "package.json").read_text(encoding="utf-8"))
    deps = pkg["dependencies"]
    assert "@unlighthouse/cli" not in deps and "critical" not in deps
    assert "agent-browser" in deps
    assert pkg["overrides"]["dembrandt"]["playwright-core"] == "$playwright-core"


# ------------------------------------------------------------------ konfiguracja

def test_profiles_use_lightpanda_and_local_stt():
    for agent in ["jarvo", "jarvo-sherlock", "jarvo-web", "jarvo-studio", "jarvo-wideo", "jarvo-reka"]:
        cfg = yaml.safe_load((REPO / "profiles" / agent / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["browser"]["engine"] == "lightpanda", agent
        assert cfg["browser"]["backend"] == "off", agent      # string, nie bool (YAML 1.1: off → False)
        assert cfg["stt"]["provider"] == "local_command", agent
        assert cfg["delegation"]["max_concurrent_children"] <= 3, agent
    host = yaml.safe_load((REPO / "profiles" / "_host" / "config.yaml").read_text(encoding="utf-8"))
    assert 1 <= host["kanban"]["max_in_progress"] <= 3
    assert host["kanban"]["max_in_progress_per_profile"] <= host["kanban"]["max_in_progress"]
    assert host["stt"]["provider"] == "local_command"


def test_merge_host_config_carries_stt_and_kanban_caps(tmp_path):
    fleet_cfg = tmp_path / "flota.yaml"
    target = tmp_path / "config.yaml"
    fleet_cfg.write_text(fl.dump_yaml({
        "kanban": {"max_in_progress": 3, "max_in_progress_per_profile": 2},
        "stt": {"provider": "local_command", "language": "pl"},
    }), encoding="utf-8")
    target.write_text(fl.dump_yaml({
        "kanban": {"dispatch_in_gateway": True},
        "stt": {"enabled": True, "provider": "local", "local": {"model": "base"}},
    }), encoding="utf-8")
    merge_host_config.main([str(fleet_cfg), str(target)])
    out = fl.load_yaml(target)
    assert out["kanban"] == {"dispatch_in_gateway": True, "max_in_progress": 3, "max_in_progress_per_profile": 2}
    assert out["stt"]["provider"] == "local_command" and out["stt"]["enabled"] is True
