"""Wspólne klucze floty: klucze dostawców z głównego .env trafiają do agentów, bez tokenów komunikatorów."""

import importlib.util
import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("share_keys", REPO / "scripts" / "share_keys.py")
sk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sk)


def home(tmp_path, root_env: str, agents=("jarvo", "jarvo-web")):
    (tmp_path / ".env").write_text(root_env, encoding="utf-8")
    for a in agents:
        d = tmp_path / "profiles" / a
        d.mkdir(parents=True)
        (d / "config.yaml").write_text("model: x\n", encoding="utf-8")
        (d / ".env").write_text("API_SERVER_KEY=secret-a\nOPENROUTER_API_KEY=\n", encoding="utf-8")
    return tmp_path


def env(h, agent):
    return sk.assignments((h / "profiles" / agent / ".env").read_text(encoding="utf-8").splitlines())


def test_provider_keys_shared_messaging_not(tmp_path):
    h = home(tmp_path, "COMMANDCODE_API_KEY=cc-1\nOPENROUTER_API_KEY=or-1\nTELEGRAM_BOT_TOKEN=123:x\nAPI_SERVER_KEY=root\n")
    sk.sync(h)
    e = env(h, "jarvo")
    assert e["COMMANDCODE_API_KEY"][1] == "cc-1"
    assert e["OPENROUTER_API_KEY"][1] == "or-1"          # pusta wartość agenta = brak klucza
    assert "TELEGRAM_BOT_TOKEN" not in e
    assert e["API_SERVER_KEY"][1] == "secret-a"          # klucz API agenta nietknięty


def test_agent_value_wins_and_edit_in_block_is_kept(tmp_path):
    h = home(tmp_path, "COMMANDCODE_API_KEY=cc-1\n")
    p = h / "profiles" / "jarvo-web" / ".env"
    p.write_text(p.read_text(encoding="utf-8") + "FIREWORKS_API_KEY=own\n", encoding="utf-8")
    (h / ".env").write_text("COMMANDCODE_API_KEY=cc-1\nFIREWORKS_API_KEY=root\n", encoding="utf-8")
    sk.sync(h)
    assert env(h, "jarvo-web")["FIREWORKS_API_KEY"][1] == "own"
    # zmiana w bloku (np. dashboard przy wybranym agencie) → zostaje ustawieniem agenta
    p.write_text(p.read_text(encoding="utf-8").replace("COMMANDCODE_API_KEY=cc-1", "COMMANDCODE_API_KEY=cc-web"),
                 encoding="utf-8")
    (h / ".env").write_text("COMMANDCODE_API_KEY=cc-2\nFIREWORKS_API_KEY=root\n", encoding="utf-8")
    sk.sync(h)
    assert env(h, "jarvo-web")["COMMANDCODE_API_KEY"][1] == "cc-web"
    assert env(h, "jarvo")["COMMANDCODE_API_KEY"][1] == "cc-2"


def test_env_and_state_only_for_owner(tmp_path):
    """.env agenta i plik stanu z LF i tylko dla właściciela: POSIX tryb 600, Windows ACL z jednym wpisem."""
    h = home(tmp_path, "COMMANDCODE_API_KEY=cc-1\n")
    sk.sync(h)
    for plik in (h / "profiles" / "jarvo" / ".env", h / sk.STATE):
        assert b"\r\n" not in plik.read_bytes(), plik
        if os.name == "nt":
            icacls = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "icacls.exe"
            out = subprocess.run([str(icacls), str(plik)], capture_output=True, encoding="oem", errors="replace").stdout
            wpisy = [w.strip() for w in out.strip().split("\n\n")[0].replace(str(plik), "", 1).splitlines()]
            assert len(wpisy) == 1 and wpisy[0].lower().endswith(f"\\{os.environ['USERNAME'].lower()}:(f)"), out
        else:
            assert stat.S_IMODE(plik.stat().st_mode) == 0o600, plik


def test_replace_retries_only_on_windows(tmp_path, monkeypatch):
    """Cel trzymany chwilę przez inny proces: na Windows os.replace ponawiamy, na POSIX błąd od razu (jak dotąd)."""
    tmp, cel = tmp_path / "a.tmp", tmp_path / "a"
    tmp.write_text("x", encoding="utf-8")
    proby = []
    prawdziwe = Path.replace

    def replace(self, target):
        proby.append(target)
        if len(proby) < 3:
            raise PermissionError("plik zajęty")
        return prawdziwe(self, target)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(sk.time, "sleep", lambda s: None)
    if os.name == "nt":
        sk.zamien(tmp, cel)
        assert cel.read_text(encoding="utf-8") == "x" and len(proby) == 3
    else:
        with pytest.raises(PermissionError):
            sk.zamien(tmp, cel)
        assert len(proby) == 1


def test_removed_key_disappears_and_sync_is_idempotent(tmp_path):
    h = home(tmp_path, "COMMANDCODE_API_KEY=cc-1\n")
    sk.sync(h)
    (h / ".env").write_text("", encoding="utf-8")
    sk.sync(h)
    text = (h / "profiles" / "jarvo" / ".env").read_text(encoding="utf-8")
    assert "COMMANDCODE_API_KEY" not in text and sk.BEGIN not in text
    sk.sync(h)
    assert (h / "profiles" / "jarvo" / ".env").read_text(encoding="utf-8") == text
