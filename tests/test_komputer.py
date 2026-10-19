"""Computer use (docs/KOMPUTER.md): bramka sterownika ekranu i reguły walidatora."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from conftest import REPO

import validate

BRAMKA = REPO / "komputer" / "jarvo_cua.py"
sys.path.insert(0, str(BRAMKA.parent))
import jarvo_cua  # noqa: E402


def uruchom(*args: str, gniazdo: str = "/nie/ma/takiego.sock") -> subprocess.CompletedProcess:
    env = {**os.environ, "JARVO_KOMPUTER_GNIAZDO": gniazdo}
    return subprocess.run([sys.executable, "-I", str(BRAMKA), *args], capture_output=True, text=True, env=env,
                          timeout=20)


def test_bramka_jest_wykonywalna_i_w_compose():
    assert os.access(BRAMKA, os.X_OK)
    compose = (REPO / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "HERMES_CUA_DRIVER_CMD: /opt/jarvo/repo/komputer/jarvo_cua.py" in compose


def test_manifest_spelnia_kontrakt_hermesa():
    """Ten sam test co _manifest_contract_reason w Hermesie: wersja ≥ 0.20, wywołanie MCP, flagi czasowników."""
    m = json.loads(uruchom("manifest").stdout)
    wersja = tuple(int(x) for x in re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", m["binary_version"]).groups())
    assert wersja >= (0, 20, 0)
    assert m["mcp_invocation"]["args"] == ["mcp"] and m["mcp_invocation"]["command"].endswith("jarvo_cua.py")
    flagi = {c["name"]: {a["name"] for a in c["args"]} for c in m["subcommands"]}
    for czas, wymagane in {"mcp": {"--socket", "--grant"}, "serve": {"--socket", "--permission-mode",
                           "--capability-manifest", "--approve-capability-manifest", "--embedded"},
                           "stop": {"--socket"}}.items():
        assert wymagane <= flagi[czas]


def test_pomoc_i_wersja():
    pomoc = uruchom("--help")
    assert pomoc.returncode == 0 and "--no-overlay" in pomoc.stdout      # Hermes dopisuje wtedy --no-overlay do mcp
    assert uruchom("--version").stdout.startswith(f"cua-driver {jarvo_cua.WERSJA_STEROWNIKA}")


def test_odmowa_aktualizacji_instalacji_i_trybu_bez_ograniczen():
    for czas in ("check-update", "update", "serve", "install", "skills", "extension", "call", "autostart"):
        r = uruchom(czas, "--json")
        assert r.returncode == jarvo_cua.KOD_ODMOWY, czas
        assert "wyłączone w bramce Jarvo" in r.stderr


def test_bez_komputera_mcp_i_status_mowia_jak_wlaczyc():
    for czas, kod in (("mcp", jarvo_cua.KOD_BRAK_KOMPUTERA), ("status", 1)):
        r = uruchom(czas)
        assert r.returncode == kod and "jarvo komputer on" in r.stderr


def test_pulpit_bez_kanalu_sterownika_nie_udaje_wylaczonego():
    """Działa ekran Komputera (rfb.sock), ale wejście sterownika (cua.sock) nie odpowiada: rada inna niż „włącz”."""
    import socket
    import tempfile
    katalog = tempfile.mkdtemp(prefix="jk")          # krótka ścieżka: gniazdo unix ma limit ~100 znaków
    ekran = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        ekran.bind(os.path.join(katalog, "rfb.sock"))
        ekran.listen(4)
        for czas, kod in (("mcp", jarvo_cua.KOD_BRAK_KOMPUTERA), ("status", 1)):
            r = uruchom(czas, gniazdo=os.path.join(katalog, "cua.sock"))
            assert r.returncode == kod and "wejście sterownika (cua.sock) nie odpowiada" in r.stderr
            assert "jarvo komputer on" not in r.stderr
    finally:
        ekran.close()
        for nazwa in os.listdir(katalog):
            os.unlink(os.path.join(katalog, nazwa))
        os.rmdir(katalog)


def test_bramka_nie_importuje_sieci():
    """Bramka nie łączy się z internetem: tylko gniazdo unix (socket), bez http, urllib, ssl, requests."""
    tekst = BRAMKA.read_text(encoding="utf-8")
    for modul in ("urllib", "http.client", "requests", "ssl", "httpx"):
        assert not re.search(rf"^\s*(import|from)\s+{re.escape(modul)}\b", tekst, re.M), modul


def _blad(raport, wzor: str) -> list[str]:
    return [e for e in raport.errors if re.search(wzor, e)]


def test_computer_use_tylko_z_komputer_true(repo_copy):
    cfg = repo_copy / "profiles/jarvo-web/config.yaml"
    tekst = cfg.read_text(encoding="utf-8")
    tekst = re.sub(r"^  cli: \[", "  cli: [computer_use, ", tekst, count=1, flags=re.M)
    tekst += "\ncommand_allowlist:\n  - \"cua:click:background\"\n"
    cfg.write_text(tekst, encoding="utf-8")
    raport = validate.run()
    assert _blad(raport, r"jarvo-web: toolset computer_use na cli bez `komputer: true`")
    assert _blad(raport, r"jarvo-web: command_allowlist 'cua:click:background' bez `komputer: true`")


def test_zle_klucze_gwiazdki_i_tryb_off(repo_copy):
    cfg = repo_copy / "profiles/jarvo-studio/config.yaml"
    tekst = cfg.read_text(encoding="utf-8").replace("  mode: smart", "  mode: off\n  allowlist: [x]", 1)
    tekst += "\ncommand_allowlist:\n  - \"cua:*:background\"\n  - \"plugin_rule:komputer-host:excel\"\n"
    cfg.write_text(tekst, encoding="utf-8")
    raport = validate.run()
    assert _blad(raport, r"jarvo-studio: approvals.mode: off")
    assert _blad(raport, r"jarvo-studio: approvals.allowlist nie istnieje")
    assert _blad(raport, r"jarvo-studio: command_allowlist 'cua:\*:background': Hermes porównuje klucze dokładnie")
    assert _blad(raport, r"jarvo-studio: command_allowlist 'plugin_rule:komputer-host:excel'")


def test_agent_z_komputerem_bez_lokalnego_terminala(repo_copy):
    fleet = repo_copy / "fleet.yaml"
    tekst = fleet.read_text(encoding="utf-8")
    tekst = re.sub(r"(\n  - name: jarvo-ads\n)", r"\1    komputer: true\n", tekst, count=1)
    fleet.write_text(tekst, encoding="utf-8")
    cfg = repo_copy / "profiles/jarvo-ads/config.yaml"
    tekst = cfg.read_text(encoding="utf-8") + "\ncommand_allowlist:\n  - \"cua:clik:background\"\n"
    cfg.write_text(tekst, encoding="utf-8")
    raport = validate.run()
    assert _blad(raport, r"jarvo-ads: agent z computer_use nie ma lokalnego terminala")
    assert _blad(raport, r"jarvo-ads: terminal w Komputerze Jarva wymaga terminal.sync_back_max_bytes: 0")
    assert _blad(raport, r"jarvo-ads: command_allowlist 'cua:clik:background': zły klucz")


def test_deny_blokuje_instalacje_sterownika():
    deny = (REPO / "shared/security/deny.yaml").read_text(encoding="utf-8")
    for wzor in ("*computer-use install*", "*trycua/cua*", "*cua-driver*", "*/opt/jarvo/komputer*"):
        assert f'"{wzor}"' in deny
