"""Lekki stos pod VPS 8 GB: jarvo-stt (napisy), to_pdf (bez Gotenberga), budżet RAM compose, higiena obrazu."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
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
    # dodatki muszą być widoczne także w działającym kontenerze (narzedzia.py sprawdza „lemo” w czasie pracy)
    assert services["hermes"]["environment"].get("JARVO_EXTRAS") == "${JARVO_EXTRAS:-}"
    assert services["hermes"]["build"]["args"].get("JARVO_EXTRAS") == "${JARVO_EXTRAS:-}"


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
    # Playwright pobiera przeglądarki bez sprawdzania sumy: obraz bierze tylko tę z obrazu Hermesa (sprawdza rewizję)
    assert not re.search(r"cli\.js install|playwright install", code)
    assert "chromium_headless_shell-$rev" in code and "INSTALLATION_COMPLETE" in code
    assert "AGENT_BROWSER_EXECUTABLE_PATH" not in code   # przejąłby też silnik lightpanda
    assert re.search(r"LIGHTPANDA_IMAGE=lightpanda/browser:[\d.]+@sha256:[0-9a-f]{64}", code)
    assert "LIGHTPANDA_DISABLE_TELEMETRY=1" in code       # Lightpanda bez telemetrii i raportów awarii


def test_lightpanda_version_in_docs_matches_image_pin():
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    pin = re.search(r"^ARG LIGHTPANDA_IMAGE=lightpanda/browser:([\d.]+)@", docker, re.M).group(1)
    sources = (REPO / "docs" / "SOURCES.md").read_text(encoding="utf-8")
    assert f"(https://github.com/lightpanda-io/browser) {pin} |" in sources
    toolbox = yaml.safe_load((REPO / "profiles" / "jarvo-sherlock" / "toolbox.yaml").read_text(encoding="utf-8"))
    lp = next(t for t in toolbox["tools"] if t["name"] == "lightpanda")
    assert str(lp["version"]) == pin


def test_browser_versions_in_docs_match_pins_and_source_registry():
    """Wersja w SOURCES.md = pin w obrazie, a commit przy niej = przejrzane w vendor/zrodla.yaml (spis nie opisuje
    innej wersji niż ta, którą flota naprawdę ma)."""
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    pkg = json.loads((REPO / "infra" / "node" / "package.json").read_text(encoding="utf-8"))
    sources = (REPO / "docs" / "SOURCES.md").read_text(encoding="utf-8")
    zrodla = yaml.safe_load((REPO / "vendor" / "zrodla.yaml").read_text(encoding="utf-8"))["zrodla"]
    piny = {"browser": ("https://github.com/lightpanda-io/browser",
                        re.search(r"^ARG LIGHTPANDA_IMAGE=lightpanda/browser:([\d.]+)@", docker, re.M).group(1)),
            "agent-browser": ("https://github.com/vercel-labs/agent-browser", pkg["dependencies"]["agent-browser"])}
    for nazwa, (repo, pin) in piny.items():
        wiersz = re.search(rf"^\| \[[^]]+\]\({re.escape(repo)}\) ([\d.]+) \|.*?commit `([0-9a-f]{{7,40}})`", sources, re.M)
        assert wiersz, nazwa
        assert wiersz.group(1) == pin, nazwa
        assert zrodla[nazwa]["repo"] == repo and zrodla[nazwa]["przejrzane"].startswith(wiersz.group(2)), nazwa


def test_monitoring_and_phone_open_no_host_ports_or_phone_home():
    """Agent Beszela na gnieździe unix wspólnym z hubem (nie port 45876 na każdym interfejsie hosta), bez cogodzinnego
    pytania rejestrów o obrazy; emulator bez statystyk użycia i tylko w sieci floty (adb bez klucza)."""
    services = yaml.safe_load((REPO / "infra" / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    agent, hub = services["beszel-agent"], services["beszel"]
    gniazdo = agent["environment"]["LISTEN"]
    assert gniazdo == "/beszel_socket/beszel.sock" and agent["environment"]["DOCKER_IMAGE_CHECK"] == "false"
    assert "beszel-gniazdo:/beszel_socket" in agent["volumes"] and "beszel-gniazdo:/beszel_socket" in hub["volumes"]
    assert agent["network_mode"] == "host" and "ports" not in agent
    emu = services["android-emulator"]
    assert "-no-metrics" in emu["environment"]["EXTRA_FLAGS"] and "ports" not in emu
    assert emu["networks"] == ["jarvo-net"] and services["komputer"]["networks"] == ["jarvo-komputer-net"]


def test_compose_service_images_pinned_and_reviewed():
    """Obrazy usług w compose: wersja i digest (bez ruchomych tagów), wersja w SOURCES.md, digest w notatce spisu
    źródeł (nowy digest bez przeglądu nie przejdzie); compose.env.example ich nie zasłania."""
    compose = (REPO / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    sources = (REPO / "docs" / "SOURCES.md").read_text(encoding="utf-8")
    spis = (REPO / "vendor" / "zrodla.yaml").read_text(encoding="utf-8")
    obrazy = [o for o in re.findall(r"^ +image: (\S+)$", compose, re.M) if not o.endswith(":local")]
    assert len(obrazy) == 7, obrazy
    for o in obrazy:
        m = re.fullmatch(r"\$\{IMAGE_[A-Z_]+:-([a-z0-9/._-]+):([\w.-]+)@sha256:([0-9a-f]{64})\}", o)
        assert m and m.group(2) != "latest", o
        assert f"`{m.group(1)}" in sources and m.group(2).removesuffix("-alpine") in sources, o
        assert f"{m.group(3)[:8]}…" in spis, o
    example = (REPO / "infra" / "env" / "compose.env.example").read_text(encoding="utf-8")
    assert not re.search(r"^IMAGE_", example, re.M)
    assert not (REPO / "scripts" / "pin-images.sh").exists()


def test_camoufox_pinned_and_lean():
    """Zapasowa przeglądarka: wersja + SHA-256 dla obu architektur, bez fontów Apple/Microsoft, bez systemd."""
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    code = "\n".join(line for line in docker.splitlines() if not line.lstrip().startswith("#"))
    wersja = re.search(r"CAMOUFOX_VERSION=([\w.-]+)", code).group(1)
    assert re.search(r"CAMOUFOX_SHA256_AMD64=[0-9a-f]{64}", code) and re.search(r"CAMOUFOX_SHA256_ARM64=[0-9a-f]{64}", code)
    assert "sha256sum -c" in code and "fonts/macos/" in code and "fonts/windows/" in code
    assert "libgtk-3-0t64" in code and "dbus-x11" in code and "dbus-user-session" not in code
    tools = (REPO / "infra" / "python" / "requirements-tools.txt").read_text(encoding="utf-8")
    assert re.search(r"^camoufox==[\d.]+$", tools, re.M) and re.search(r"^playwright==1\.(\d+)\.\d+$", tools, re.M)
    assert int(re.search(r"^playwright==1\.(\d+)", tools, re.M).group(1)) < 63   # camoufox 0.5.6: playwright < 1.63
    for agent in ("jarvo-lowca", "jarvo-sherlock"):
        tb = yaml.safe_load((REPO / "profiles" / agent / "toolbox.yaml").read_text(encoding="utf-8"))
        cf = next(t for t in tb["tools"] if t["name"] == "camoufox")
        assert wersja in cf["version"] and "ostrozna.py --sprawdz" in cf["healthcheck"]


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


def test_manim_extra_is_manimgx_pinned_by_hash():
    """Dodatek `manim` = ManimGX w osobnym venv na Pythonie 3.13: każda paczka z wersją i sha256, instalacja
    --require-hashes z samych kół, bez apt (cairo, pango, texlive) i bez Manim CE; na końcu próbny render."""
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    code = "\n".join(line for line in docker.splitlines() if not line.lstrip().startswith("#"))
    for pkg in ("texlive", "libcairo2-dev", "libpango1.0-dev"):
        assert pkg not in code, pkg
    assert not re.search(r"for x in [a-z ]*\bmanim\b", code)
    run = next(r for r in code.split("\nRUN ") if "/opt/jarvo/venvs/manimgx" in r)
    assert "*\" manim \"*" in run and "--python 3.13" in run
    assert "--require-hashes" in run and "--only-binary :all:" in run and "requirements-manimgx.txt" in run
    assert re.search(r"manimgx render .*-r 640x360 --fps 30", run) and "MANIMGX_CACHE_DIR" in run
    lock = (REPO / "infra" / "python" / "requirements-manimgx.txt").read_text(encoding="utf-8")
    pins = re.findall(r"^([a-z0-9-]+)==(\S+)(?: ;[^\\]*)? \\\n((?:    --hash=sha256:[0-9a-f]{64}(?: \\)?\n)+)", lock, re.M)
    names = {n for n, _v, _h in pins}
    assert len(pins) == len(re.findall(r"^[a-z0-9-]+==", lock, re.M))       # każda paczka ma sumy
    assert {"manimgx", "manimgx-fonts", "manimgx-fonts-cjk", "numpy", "pillow"} <= names
    assert ("manimgx", "0.1.1") in {(n, v) for n, v, _h in pins}
    assert "1afbccb6f5f27fa8e2ce27eb2c46d364afbbd559f35ae93d10b06f4f2db747a7" in lock   # manylinux_2_28 x86_64
    assert "26ecbdbaf99d35aa62e4a363fc64689c8b40383cc98b6e31bbfac05bdb74957c" in lock   # manylinux_2_28 aarch64
    optional = (REPO / "infra" / "python" / "requirements-optional.txt").read_text(encoding="utf-8")
    assert not re.search(r"^manim==", optional, re.M)
    wrapper = REPO / "infra" / "bin" / "manimgx"
    assert os.access(wrapper, os.X_OK) and "/opt/jarvo/venvs/manimgx" in wrapper.read_text(encoding="utf-8")
    tb = yaml.safe_load((REPO / "profiles" / "jarvo-wideo" / "toolbox.yaml").read_text(encoding="utf-8"))
    mg = next(t for t in tb["tools"] if t["name"] == "manimgx")
    assert mg["optional"] is True and mg["version"] == "0.1.1" and mg["healthcheck"] == "manimgx --version"


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
