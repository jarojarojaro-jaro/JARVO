"""Landing (site/) i instalatory jednym poleceniem (install.sh, install.ps1)."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "site"


def test_every_local_asset_exists():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    css = (SITE / "style.css").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"#:]+)"', html) + re.findall(r"url\(([^)\"']+)\)", css)
    assert refs
    for ref in refs:
        assert (SITE / ref).is_file(), ref


def test_sprites_match_art_json():
    import json
    art = json.loads((SITE / "assets" / "art.json").read_text(encoding="utf-8"))
    css = (SITE / "style.css").read_text(encoding="utf-8")
    for name, s in art["sprites"].items():
        assert (SITE / "assets" / f"{name}.png").is_file()
        # pozycje w CSS muszą zgadzać się z wygenerowanymi warstwami, inaczej robot „rozjedzie się”
        assert f'[data-spr="{name}"] {{ left: {s["x"]}px; top: {s["y"]}px; width: {s["w"]}px; height: {s["h"]}px; }}' in css, name


def test_install_commands_point_at_repo_installers():
    js = (SITE / "app.js").read_text(encoding="utf-8")
    base = re.search(r'const BASE = "([^"]+)"', js).group(1)
    assert base.startswith("https://")
    assert "${BASE}/install.sh | bash" in js and "${BASE}/install.ps1 | iex" in js
    assert (REPO / "install.sh").is_file() and (REPO / "install.ps1").is_file()
    # PowerShell pobiera ten sam install.sh w WSL
    assert "install.sh" in (REPO / "install.ps1").read_text(encoding="utf-8")


@pytest.mark.skipif(not shutil.which("bash"), reason="brak basha")
@pytest.mark.parametrize("script", ["install.sh", "scripts/local-up.sh"])
def test_shell_syntax(script):
    subprocess.run(["bash", "-n", str(REPO / script)], check=True)


def test_local_up_is_portable_to_macos():
    code = [l for l in (REPO / "scripts" / "local-up.sh").read_text(encoding="utf-8").splitlines()
            if not l.lstrip().startswith("#") and not l.startswith(("owner()", "sedi()"))]
    s = "\n".join(code)
    assert "stat -c" not in s and "sed -i" not in s and "nohup setsid" not in s


def test_seo_and_security_files_are_deployed():
    site = Path(__file__).resolve().parents[1] / "site"
    deploy = (site.parent / "scripts" / "deploy-site.sh").read_text(encoding="utf-8")
    for f in [".htaccess", "robots.txt", "sitemap.xml", "llms.txt", "site.webmanifest", "favicon.ico"]:
        assert (site / f).exists() and f in deploy, f
    ht = (site / ".htaccess").read_text(encoding="utf-8")
    for h in ["Strict-Transport-Security", "Content-Security-Policy", "frame-ancestors 'none'", "X-Content-Type-Options"]:
        assert h in ht, h
    html = (site / "index.html").read_text(encoding="utf-8")
    assert 'rel="canonical"' in html and "application/ld+json" in html
    assert all(" width=" in tag for tag in __import__("re").findall(r"<img [^>]*>", html))


@pytest.mark.skipif(not shutil.which("bash"), reason="brak basha")
@pytest.mark.parametrize("choice, provider, key_in", [
    ("1", "openrouter", "agents"),                 # OpenRouter: klucz do sekretów każdego agenta
    ("2", "commandcode-anthropic", "host"),        # CommandCode: klucz do host.env (share_keys.py)
    ("4", "", None),                               # OpenAI (logowanie ChatGPT): bez klucza, domyślny dostawca
])
def test_local_up_provider_choice(tmp_path, choice, provider, key_in):
    """Wybór dostawcy w local-up.sh trafia do compose/jarvo.env zgodnie z fleet.yaml (puste = openai-codex)."""
    import os
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(REPO / "scripts" / "local-up.sh", root / "scripts")
    shutil.copytree(REPO / "infra" / "env", root / "infra" / "env")
    (root / "scripts" / "deploy.sh").write_text("exit 0\n", encoding="utf-8")
    (root / "scripts" / "updater.py").write_text("", encoding="utf-8")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in {"docker": "exit 0", "sudo": 'exec "$@"', "chown": "exit 0", "chgrp": "exit 0"}.items():
        (bindir / name).write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
        (bindir / name).chmod(0o755)
    local = tmp_path / "jarvo-local"
    env = {**os.environ, "HOME": str(tmp_path), "JARVO_LOCAL": str(local), "PATH": f"{bindir}:{os.environ['PATH']}"}
    env.pop("JARVO_MODEL_PROVIDER", None)
    res = subprocess.run(["bash", str(root / "scripts" / "local-up.sh")], input=f"{choice}\nklucz-testowy\n",
                         env=env, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    jarvo_env = (local / "compose" / "jarvo.env").read_text(encoding="utf-8")
    assert re.search(rf"^JARVO_MODEL_PROVIDER={provider}$", jarvo_env, re.M)
    agent = (local / "secrets" / "jarvo-web.env").read_text(encoding="utf-8")
    host = (local / "secrets" / "host.env").read_text(encoding="utf-8")
    assert ("OPENROUTER_API_KEY=klucz-testowy" in agent) == (key_in == "agents")
    assert ("klucz-testowy" in host) == (key_in is not None)   # szablon hosta też ma OPENROUTER_API_KEY
