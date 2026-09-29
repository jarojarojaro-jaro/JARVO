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
