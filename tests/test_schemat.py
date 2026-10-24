"""Narzędzie `schemat` (wiedza/plugin/schemat.py): SVG → PNG w rozmowie. Strona do zrzutu bez sieci i skryptów,
rozmiar z width/height albo viewBox, wynik z linią MEDIA:. Prawdziwy Chromium: test w kontenerze (docs/WIEDZA.md),
na Windows prawdziwy Chrome albo Edge, jeśli jest (potok DevTools przez --remote-debugging-io-pipes)."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

import pytest

import atrapy
from conftest import load_script

s = load_script("wiedza/plugin/schemat.py", "jarvo_schemat_test")

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="520"><text x="10" y="40">Jak działa skarbiec</text></svg>'


def test_wymiary():
    assert s.wymiary(SVG) == (1200, 520)
    assert s.wymiary('<svg viewBox="0 0 4000 1000">') == (2400, 600)            # za duży: w dół, proporcje bez zmian
    assert s.wymiary('<svg width="100" height="50">') == (400, 200)             # za mały: w górę
    assert s.wymiary('<svg width="600">') == (1200, 800) and s.wymiary("<svg>") == (1200, 800)
    assert s.wymiary('<svg width="600" viewBox="0 0 300 100">') == (600, 200)


def test_strona_bez_sieci_i_skryptow():
    html = s.strona('<svg width="5000" height="1000" onload="x()"><script>fetch("//zly")</script><rect/></svg>',
                    *s.wymiary('<svg width="5000" height="1000">'))
    assert "default-src 'none'" in html and "<script" not in html
    assert '<svg width="2400" height="480" viewBox="0 0 5000 1000"' in html     # viewBox: skala bez przycinania
    assert 'width="5000"' not in html
    assert s.slug("Jak działa skarbiec wiedzy?") == "jak-dziala-skarbiec-wiedzy" and s.slug("???") == "schemat"


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200 + b"\x00\x00\x00\x00IEND\xaeB`\x82"

# Udawany Chromium mówi protokołem DevTools na potoku (JSON zakończony bajtem 0): na POSIX fd 3 polecenia i fd 4
# odpowiedzi, na Windows uchwyty z --remote-debugging-io-pipes=<odczyt>,<zapis> (bez --no-sandbox)
UDAWANY = r"""import base64, json, os, sys, time
TRYB = os.path.splitext(os.path.basename(sys.argv[0]))[0].rsplit("-", 1)[-1]
assert "--remote-debugging-pipe" in sys.argv and "about:blank" in sys.argv
if os.name == "nt":
    import msvcrt
    assert "--no-sandbox" not in sys.argv
    uchwyty = next(a for a in sys.argv if a.startswith("--remote-debugging-io-pipes=")).split("=", 1)[1].split(",")
    WE, WY = msvcrt.open_osfhandle(int(uchwyty[0]), os.O_RDONLY), msvcrt.open_osfhandle(int(uchwyty[1]), 0)
else:
    WE, WY = 3, 4
if TRYB == "pusty":
    sys.exit(0)
bufor = b""
def odpisz(m):
    os.write(WY, json.dumps(m).encode() + b"\0")
while True:
    kawalek = os.read(WE, 65536)
    if not kawalek:
        break
    bufor += kawalek
    while b"\0" in bufor:
        raw, bufor = bufor.split(b"\0", 1)
        m = json.loads(raw); metoda = m["method"]; wynik = {}
        if metoda == "Target.createTarget": wynik = {"targetId": "t1"}
        elif metoda == "Target.attachToTarget": wynik = {"sessionId": "s1"}
        elif metoda == "Page.navigate":
            assert m["params"]["url"].startswith("file://") and m["sessionId"] == "s1"
            odpisz({"method": "Page.loadEventFired", "sessionId": "s1", "params": {}})
            wynik = {"frameId": "f"}
        elif metoda == "Page.captureScreenshot":
            wynik = {"data": base64.b64encode(open(os.environ["WZOR_PNG"], "rb").read()).decode()}
        elif metoda == "Browser.close":
            if TRYB == "wisi":
                time.sleep(300)
            sys.exit(0)
        odpisz({"id": m["id"], "result": wynik, **({"sessionId": m["sessionId"]} if "sessionId" in m else {})})
"""


def _udawany_chromium(tmp_path: Path, monkeypatch, tryb: str = "dobry") -> Path:
    """Udawany Chromium: dobry (zrzut i wyjście), wisi (zrzut, ale nie wychodzi), pusty (wychodzi od razu).
    Atrapa przenośna (tests/atrapy.py): na Windows nakładka .cmd, za którą Python dziedziczy uchwyty potoków."""
    (tmp_path / "wzor.png").write_bytes(PNG)
    monkeypatch.setenv("WZOR_PNG", str(tmp_path / "wzor.png"))
    return atrapy.program(tmp_path, f"chromium-{tryb}", UDAWANY)


def test_chromium_wiszacy_po_zrzucie(tmp_path, monkeypatch):
    """Przeglądarka, która po zrzucie nie zamyka się sama: bierzemy zrzut i ją zamykamy (na Windows z potomnymi)."""
    t0 = time.monotonic()
    png = s.renderuj(SVG, "test", tmp_path / "out", przegladarka=str(_udawany_chromium(tmp_path, monkeypatch, "wisi")))
    assert png.read_bytes() == PNG and time.monotonic() - t0 < 15


def test_chromium_bez_zrzutu_to_blad(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="nie zrobił zrzutu"):
        s.renderuj(SVG, "test", tmp_path / "out", przegladarka=str(_udawany_chromium(tmp_path, monkeypatch, "pusty")))
    assert not list((tmp_path / "out").glob("*.png"))


def test_obsluz_z_udawanym_chromium(tmp_path, monkeypatch):
    fake = _udawany_chromium(tmp_path, monkeypatch)
    monkeypatch.setenv("JARVO_CHROMIUM", str(fake))
    monkeypatch.setenv("JARVO_SCHEMATY_DIR", str(tmp_path / "schematy"))
    w = json.loads(s.obsluz({"svg": SVG, "tytul": "Jak działa skarbiec"}))
    assert w["ok"] and w["media"] == f"MEDIA:{w['plik']}" and w["plik"].endswith("-jak-dziala-skarbiec.png")
    assert "\\" not in w["media"] and Path(w["plik"]).read_bytes() == PNG       # na Windows C:/…: bez ucieczek w MEDIA:
    assert w["rozmiar"] == "1200×520" and (tmp_path / "schematy").is_dir()
    assert "error" in json.loads(s.obsluz({"svg": "to nie svg", "tytul": "x"}))
    assert "maks." in json.loads(s.obsluz({"svg": "<svg>" + "x" * s.MAX_ZNAKOW, "tytul": "x"}))["error"]
    monkeypatch.setenv("JARVO_CHROMIUM", str(tmp_path / "nie-ma"))
    assert "Nie udało się" in json.loads(s.obsluz({"svg": SVG, "tytul": "x"}))["error"]


def test_katalog_schematow_z_profilu(tmp_path, monkeypatch):
    """PNG w <dane>/jarvo/workspaces/jarvo/schematy, także gdy HERMES_HOME to katalog profilu."""
    monkeypatch.delenv("JARVO_SCHEMATY_DIR", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "dane" / "profiles" / "jarvo"))
    assert s.katalog_schematow() == tmp_path / "dane" / "jarvo" / "workspaces" / "jarvo" / "schematy"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "dane"))
    assert s.katalog_schematow() == tmp_path / "dane" / "jarvo" / "workspaces" / "jarvo" / "schematy"


@pytest.mark.windows_only
def test_chromium_na_windows(tmp_path, monkeypatch):
    """Windows: JARVO_CHROMIUM, potem CHROME_PATH (chrome-headless-shell instalatora), potem PATH i typowe instalacje."""
    monkeypatch.delenv("JARVO_CHROMIUM", raising=False)
    shell = tmp_path / "chrome-headless-shell.exe"
    shell.write_bytes(b"")
    monkeypatch.setenv("CHROME_PATH", str(shell))
    assert s.chromium() == str(shell)
    monkeypatch.setenv("JARVO_CHROMIUM", "C:/inna/chrome.exe")
    assert s.chromium() == "C:/inna/chrome.exe"
    monkeypatch.delenv("JARVO_CHROMIUM")
    monkeypatch.setenv("CHROME_PATH", str(tmp_path / "nie-ma.exe"))                 # nieistniejący CHROME_PATH pomijany
    monkeypatch.setenv("PATH", str(tmp_path))
    for zmienna in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        monkeypatch.setenv(zmienna, str(tmp_path / zmienna.lower()))
    assert s.chromium() is None
    edge = tmp_path / "programfiles(x86)" / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_bytes(b"")
    assert s.chromium() == str(edge)


@pytest.mark.skipif(not shutil.which("chromium"), reason="brak Chromium (test w kontenerze)")
def test_prawdziwy_chromium(tmp_path):
    png = s.renderuj(SVG, "test", tmp_path)
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.windows_only
@pytest.mark.skipif(os.name == "nt" and not s.chromium(), reason="brak Chrome, Edge i chrome-headless-shell")
def test_prawdziwy_chrome_na_windows(tmp_path):
    """Prawdziwa przeglądarka na Windows: potok DevTools przez dziedziczone uchwyty, PNG ×2, wątek odczytu kończy pracę."""
    png = s.renderuj(SVG, "Jak działa skarbiec", tmp_path)
    dane = png.read_bytes()
    assert s._pelny_png(png) and int.from_bytes(dane[16:20], "big") == 2400 and int.from_bytes(dane[20:24], "big") == 1040
    time.sleep(0.2)
    import threading
    assert not [t for t in threading.enumerate() if t.name == "jarvo-schemat-cdp"]
