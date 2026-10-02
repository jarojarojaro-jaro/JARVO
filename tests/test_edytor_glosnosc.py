"""Linia głośności i fala w dB w edytorze HQ: położenie linii ↔ głośność liniowa projektu (0–2), przyciąganie do 0 dB,
fala w dBFS bez wyrównania do najgłośniejszego miejsca."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from conftest import REPO

JS = (REPO / "hq" / "web" / "src" / "45-edytor.js").read_text(encoding="utf-8")


def test_glosnosc_i_fala_w_db():
    if not shutil.which("node"):
        pytest.skip("brak node")
    kod = "\n".join(re.search(rf"^{w}.*?$", JS, re.M).group(0) for w in
                    (r"const clamp = ", r"const waveH = ", r"const ED_DB = ", r"const volDb = ", r"const volPos = ", r"const fmtDb = "))
    kod += "\n" + re.search(r"^function posVol\(.*?^}", JS, re.S | re.M).group(0)
    prog = kod + """
const r = (x) => Math.round(x * 1000) / 1000;
console.log(JSON.stringify({
  zero: r(volPos(1)), gora: volPos(2), dol: volPos(0), cicho: volPos(0.01),
  wstecz: [0.1, 0.25, 0.5, 1, 1.5, 2].map((v) => r(posVol(volPos(v)))),
  przyciaga: posVol(volPos(1) + 0.015), cisza: posVol(0.01),
  db: [fmtDb(1), fmtDb(0.5), fmtDb(2), fmtDb(0)],
  fala: [waveH(1), r(waveH(10 ** (-24 / 20))), waveH(1e-4), waveH(0)]}));"""
    w = json.loads(subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True).stdout)
    assert w["zero"] == round(30 / (30 + 6.0206), 3) and w["gora"] == 1 and w["dol"] == 0 and w["cicho"] == 0
    assert w["wstecz"] == [0.1, 0.25, 0.5, 1, 1.5, 2]          # linia ↔ głośność bez dryfu
    assert w["przyciaga"] == 1 and w["cisza"] == 0              # blisko 0 dB = 100%, sam dół = wyciszenie
    assert w["db"] == ["0.0 dB", "−6.0 dB", "+6.0 dB", "−∞ dB"]
    assert w["fala"] == [1, 0.5, 0, 0]                          # 0 dBFS = pełna, −24 = połowa, −80 = nic
