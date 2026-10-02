"""Wygląd edytora HQ (styl CapCut): krój w buildzie, format czasu osi, ikony SVG zamiast emoji."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "hq" / "web" / "src"
EDYTOR = ("45-edytor.js", "46-uwagi.js", "47-animacja.js")


def test_kroj_edytora_w_pluginie_i_demo(tmp_path):
    """Inter (OFL) jedzie z licencją, a każdy url() z @font-face edytora wskazuje plik, który build kopiuje."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import hqbuild

    dist = hqbuild.build_plugin(tmp_path / "jarvo-hq") / "dist"
    demo = hqbuild.build_demo(tmp_path / "demo")
    css = (ROOT / "hq" / "web" / "style.css").read_text(encoding="utf-8")
    urls = re.findall(r'font-family: "Inter Jarvo";[^}]*?src: url\(([^)]+)\)', css)
    assert sorted(urls) == ["fonts/Inter-latin-ext.woff2", "fonts/Inter-latin.woff2"]
    for base in (dist, demo):
        for u in urls:
            assert (base / u).stat().st_size > 40_000, (base, u)
        assert "SIL Open Font License" in (base / "fonts" / "LICENSE-Inter.txt").read_text(encoding="utf-8")
    assert (dist / "fonts" / "fosfor.css").is_file()                       # kroje motywu Fosfor zostają obok
    assert '"Inter Jarvo"' in css.split(".thq-ed {", 1)[1].split("}", 1)[0]   # krój zapasowy w stosie edytora


def test_czas_osi_jak_w_capcut():
    if not shutil.which("node"):
        pytest.skip("brak node")
    js = (SRC / "45-edytor.js").read_text(encoding="utf-8")
    fn = re.search(r"^function edTC\(.*?^}", js, re.S | re.M).group(0)
    prog = fn + "\nconsole.log(JSON.stringify([edTC(0), edTC(5.2), edTC(74.666), edTC(3.9, false), edTC(-1), edTC(600, false)]));"
    out = json.loads(subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True).stdout)
    assert out == ["00:00.00", "00:05.20", "01:14.67", "00:03", "00:00.00", "10:00"]


def test_edytor_bez_emoji_i_symboli_zamiast_ikon():
    """Ikony to SVG z ED_ICON (jeden styl linii); emoji i symbole tekstowe wyglądają różnie na każdym systemie."""
    zakazane = set("✦✂⧉⤓❚♪▣⯇⯈▶🔇🗑📷📌")
    for name in EDYTOR:
        for i, line in enumerate((SRC / name).read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("//"):
                continue
            bad = {c for c in line if c in zakazane or ord(c) >= 0x1F000}
            assert not bad, f"{name}:{i}: {''.join(sorted(bad))}"


def test_edytor_ma_tarcze_przed_motywem_dashboardu():
    """Motyw Fosfor zeruje zaokrąglenia i tło pól (!important), świeci tekstem, wyłącza animacje w .thq-root."""
    css = (ROOT / "hq" / "web" / "style.css").read_text(encoding="utf-8")
    for rule in (".thq-ed :is(button, input, select, textarea) { border-radius: var(--r, 8px) !important;",
                 ".thq-ed { text-shadow: none; }",
                 ".thq-ed :is(header, aside, nav) { border-color: var(--ed-line) !important; box-shadow: none !important; }",
                 ".thq-root .thq-ed .thq-ed-spin { animation: thq-ed-spin .8s linear infinite !important; }"):
        assert rule in css, rule
