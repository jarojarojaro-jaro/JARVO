"""Serwer MCP inspo natywnie (docs/NATYWNIE.md P06, etap E5): `node <node_modules>/inspo-mcp/inspo-mcp.mjs --stdio`
z konfiguracji, którą build.py daje Webowi, odpowiada na JSON-RPC jak w Hermesie.

Test na żywo: potrzebuje Node, paczki inspo-mcp w NODE_PATH (narzędzia npm floty, infra/node) i sieci (katalog stron
z CDN autorów), więc tylko na życzenie, z JARVO_E2E=1 (jak pozostałe testy na żywo). Środowisko serwera jest takie jak
w Hermesie: tylko zmienne bezpieczne (tools/mcp_tool_config.py, _build_safe_env) i `env` z config.yaml.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

import build
import fleetlib as fl

# zmienne, które Hermes przekazuje serwerowi stdio (f97608f: _SAFE_ENV_KEYS i _SAFE_ENV_KEYS_CASE_INSENSITIVE)
BEZPIECZNE = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "SHELL", "TMPDIR"}
BEZPIECZNE_WINDOWS = {"ALLUSERSPROFILE", "APPDATA", "COMMONPROGRAMFILES", "COMPUTERNAME", "COMSPEC", "HOMEDRIVE",
                      "HOMEPATH", "LOCALAPPDATA", "NUMBER_OF_PROCESSORS", "OS", "PATHEXT", "PROCESSOR_ARCHITECTURE",
                      "PROGRAMDATA", "PROGRAMFILES", "PUBLIC", "SYSTEMDRIVE", "SYSTEMROOT", "TEMP", "TMP", "USERDOMAIN",
                      "USERNAME", "USERPROFILE", "WINDIR"}


def node_modules_inspo() -> Path | None:
    for katalog in filter(None, os.environ.get("NODE_PATH", "").split(os.pathsep)):
        if (Path(katalog) / "inspo-mcp" / "package.json").is_file():
            return Path(katalog)
    return None


class Klient:
    """Klient JSON-RPC 2.0 po stdio (MCP: jedna wiadomość JSON na wiersz)."""

    def __init__(self, argv: list[str], env: dict):
        self.proces = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       env=env, text=True, encoding="utf-8")
        self.odpowiedzi: queue.Queue = queue.Queue()
        threading.Thread(target=self._czytaj, daemon=True).start()
        self.nr = 0

    def _czytaj(self) -> None:
        for wiersz in self.proces.stdout:
            try:
                self.odpowiedzi.put(json.loads(wiersz))
            except ValueError:
                continue

    def wyslij(self, metoda: str, params: dict | None = None, *, powiadomienie: bool = False) -> None:
        wiadomosc = {"jsonrpc": "2.0", "method": metoda, **({"params": params} if params is not None else {})}
        if not powiadomienie:
            self.nr += 1
            wiadomosc["id"] = self.nr
        self.proces.stdin.write(json.dumps(wiadomosc) + "\n")
        self.proces.stdin.flush()

    def zapytaj(self, metoda: str, params: dict | None = None, czas: float = 90) -> dict:
        self.wyslij(metoda, params)
        while True:
            odp = self.odpowiedzi.get(timeout=czas)
            if odp.get("id") == self.nr:
                return odp

    def zamknij(self) -> None:
        self.proces.kill()
        self.proces.wait(10)


@pytest.mark.skipif(os.environ.get("JARVO_E2E") != "1", reason="na życzenie: JARVO_E2E=1 (Node, inspo-mcp, sieć)")
def test_inspo_mcp_odpowiada_na_json_rpc_z_konfiguracji_natywnej():
    nm = node_modules_inspo()
    node = shutil.which("node")
    if nm is None or node is None:
        pytest.skip("brak node albo inspo-mcp w NODE_PATH (narzędzia npm floty)")
    zrodlo = fl.load_yaml(fl.REPO_ROOT / "profiles" / "jarvo-web" / "config.yaml")
    cfg = {"mcp_servers": {"inspo": dict(zrodlo["mcp_servers"]["inspo"])}}
    build.ustaw_mcp(cfg, build.Uklad(nazwa="natywny", system=build.system_tego_komputera(),
                                     node_modules=nm.as_posix()))
    inspo = cfg["mcp_servers"]["inspo"]
    assert inspo["command"] == "node" and inspo["env"]["NODE_USE_SYSTEM_CA"] == "1"
    env = {k: v for k, v in os.environ.items() if k in BEZPIECZNE or k.upper() in BEZPIECZNE_WINDOWS
           or k.startswith("XDG_")}
    env.update({k: str(v) for k, v in inspo["env"].items()})
    k = Klient([node, *inspo["args"]], env)
    try:
        init = k.zapytaj("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                        "clientInfo": {"name": "jarvo-test", "version": "0"}})
        assert init["result"]["serverInfo"]["name"] and "tools" in init["result"]["capabilities"]
        k.wyslij("notifications/initialized", powiadomienie=True)
        narzedzia = {t["name"] for t in k.zapytaj("tools/list")["result"]["tools"]}
        assert set(inspo["tools"]["include"]) <= narzedzia
        wynik = k.zapytaj("tools/call", {"name": "search_screens", "arguments": {"query": "agency", "limit": 1}})
        assert "sourceUrl" in json.dumps(wynik["result"])
    finally:
        k.zamknij()
