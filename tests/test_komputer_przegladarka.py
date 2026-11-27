"""Przeglądarka Jarva natywnie (komputer/przegladarka.py, docs/NATYWNIE.md J01, J06, J07, J11): flagi startu,
preferencje profilu, pobrane pliki (bez programów) i wybór programu przeglądarki. Bez przeglądarki: czyste funkcje."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from komputer import przegladarka, sterownik_cdp  # noqa: E402


def test_flagi_proxy_quic_webrtc_i_tryb(tmp_path):
    f = przegladarka.flagi(profil=tmp_path / "profil", port_proxy=19201, okno=False)
    assert f"--user-data-dir={tmp_path / 'profil'}" in f
    assert "--proxy-server=http://127.0.0.1:19201" in f and "--proxy-bypass-list=<-loopback>" in f
    assert "--disable-quic" in f and "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in f
    assert "--headless=new" in f and "--deny-permission-prompts" in f and "--site-per-process" in f
    assert "--disable-extensions" in f and "--disable-sync" in f and f[-1] == "about:blank"
    assert any(x.startswith("--disable-features=") and "MediaRouter" in x for x in f)   # Cast szuka w sieci po UDP
    okno = przegladarka.flagi(profil=tmp_path, port_proxy=19201, okno=True)
    assert "--headless=new" not in okno
    # GPU tylko bez emulacji: x64 na Windows arm64 bez GPU i bez SwiftShadera (renderer nowej karty nie czeka na JIT)
    assert "--disable-gpu" not in f
    emu = przegladarka.flagi(profil=tmp_path, port_proxy=19201, okno=False, emulacja=True)
    assert "--disable-gpu" in emu and "--disable-software-rasterizer" in emu and emu[-1] == "about:blank"
    assert "--renderer-process-limit=100" in emu and not any(x.startswith("--renderer-process-limit") for x in f)


def test_flagi_bez_oslabien_playwrighta_i_portu_cdp(tmp_path):
    """Bez wyłączania blokady wyskakujących okien i ochrony przed phishingiem, bez portu DevTools (CDP tylko po
    potoku) i bez piaskownicy wyłączonej domyślnie."""
    f = " ".join(przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=True))
    for zakazana in ("--disable-popup-blocking", "--disable-client-side-phishing-detection", "--remote-debugging-port",
                     "--no-sandbox", "--disable-web-security", "--enable-automation", "--disable-background-networking"):
        assert zakazana not in f, zakazana
    assert "--no-sandbox" in przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=True, bez_piaskownicy=True)


def test_flagi_w_tle_bez_cech_trybu_bez_okna(tmp_path, monkeypatch):
    """Antybot: przeglądarka w tle ma ekran większy od okna z paskiem zadań (nie 800×600 przy oknie 1440×900),
    mysz, user-agenta bez HeadlessChrome z wersji w katalogu (także dla service workerów), a na Linuksie z kartą
    graficzną WebGL z karty zamiast SwiftShadera; okno i emulacja bez tych flag."""
    monkeypatch.setattr(przegladarka, "LINUX", True)
    monkeypatch.setattr(przegladarka, "gpu_linux", lambda: True)
    f = przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=False)
    assert "--screen-info={0,0 1920x1080 workAreaBottom=48}" in f and f"--blink-settings={przegladarka.MYSZ_W_TLE}" in f
    assert "--use-gl=angle" in f and "--use-angle=gl-egl" in f and f[-1] == "about:blank"
    duzy = przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=False, ekran=(2560, 1440))
    assert "--screen-info={0,0 2560x1488 workAreaBottom=48}" in duzy
    okno = " ".join(przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=True))
    assert "--screen-info" not in okno and "--use-angle" not in okno and "--blink-settings" not in okno
    assert "--use-angle=gl-egl" not in przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=False, emulacja=True)
    monkeypatch.setattr(przegladarka, "gpu_linux", lambda: False)                  # VPS, CI: zostaje SwiftShader
    assert "--use-angle=gl-egl" not in przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=False)
    program = tmp_path / "chrome-komputer" / "158.0.8127.36" / "chrome-linux64" / "chrome"
    ua = przegladarka.user_agent(program)
    assert ua.endswith("AppleWebKit/537.36 (KHTML, like Gecko) Chrome/158.0.0.0 Safari/537.36") and "Headless" not in ua
    assert f"--user-agent={ua}" in przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=False, program=program)
    assert not any(x.startswith("--user-agent") for x in przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=True,
                                                                             program=program))
    assert przegladarka.user_agent("/opt/chrome/chrome") is None                   # bez wersji: tylko nadpisanie CDP


@pytest.mark.parametrize("pelna, marki", [
    ("157.0.8103.78", [("Chromium", "157", "157.0.8103.78"), ("Not-A.Brand", "99", "99.0.0.0")]),
    ("158.0.8127.36", [("Not.A/Brand", "24", "24.0.0.0"), ("Chromium", "158", "158.0.8127.36")]),
])
def test_marki_jak_chrome_for_testing_tej_wersji(pelna, marki):
    """navigator.userAgentData odczytane z CfT 157 i 158 w tle bez nadpisania: nadpisanie user-agenta daje te same."""
    krotkie, pelne = sterownik_cdp.marki_chromium(pelna)
    assert krotkie == [{"brand": m, "version": w} for m, w, _ in marki]
    assert pelne == [{"brand": m, "version": p} for m, _, p in marki]


def test_droga_myszy_lukiem_do_celu():
    """Klik dojeżdża kursorem: kilka do kilkunastu ruchów, różne punkty, koniec dokładnie w celu, razem 0,1 do 0,45 s."""
    los = sterownik_cdp.random.Random(7)
    for a, b in (((100, 100), (900, 500)), ((700, 450), (712, 449)), ((0, 0), (1439, 899))):
        droga = sterownik_cdp.droga_myszy(a, b, los)
        assert 6 <= len(droga) <= 18 and droga[-1][:2] == b
        assert len({(x, y) for x, y, _ in droga}) == len(droga)
        assert 0.1 <= sum(p for _, _, p in droga) <= 0.45
        odl = [abs(x - b[0]) + abs(y - b[1]) for x, y, _ in droga]
        assert odl[-1] == 0 and odl[0] > odl[len(odl) // 2] > 0
    assert sterownik_cdp.droga_myszy((5, 5), (5.5, 5), los) == [(5.5, 5, 0.0)]          # już na miejscu


class _Potwierdzenie:
    def __init__(self, jest: bool):
        self.jest = jest

    def gotowe(self, czas: float) -> bool:
        if not self.jest:
            time.sleep(czas)
        return self.jest

    def wynik(self, _czas: float) -> dict:
        return {}


class _PrzegladarkaBezRuchow:
    """Okno przykryte innym oknem na pulpicie: mouseMoved bez potwierdzenia (Chrome potwierdza po ok. 5 s)."""

    def __init__(self):
        self.zdarzenia: list[tuple] = []

    def nadaj(self, metoda, params, sesja=None):
        self.zdarzenia.append((params["type"], params["x"], params["y"]))
        return _Potwierdzenie(params["type"] != "mouseMoved")


@pytest.mark.parametrize("dojechany", [False, True])
def test_klik_w_przykrytym_oknie_bez_czekania_na_kazdy_ruch(tmp_path, dojechany):
    """Pomiar 27.11 na :0 z drugim oknem na wierzchu: każdy ruch drogi czekał ok. 5 s, klik 31 do 86 s (bez drogi
    5,6 s). Ruch bez potwierdzenia w CZAS_RUCHU kończy drogę: kursor wprost na cel i klik w nim, poniżej 1 s."""
    b = _PrzegladarkaBezRuchow()
    st = sterownik_cdp.Sterownik(b, pobrane=tmp_path)
    okno = sterownik_cdp.Okno(1, "cel", "sesja")
    if dojechany:
        okno.mysz = (300.0, 200.0)                                                  # już nad celem: jeden ruch
    poczatek = time.monotonic()
    st._mysz(okno, 300.0, 200.0)
    assert time.monotonic() - poczatek < sterownik_cdp.CZAS_RUCHU + 0.6
    assert b.zdarzenia[-3:] == [("mouseMoved", 300.0, 200.0), ("mousePressed", 300.0, 200.0),
                                ("mouseReleased", 300.0, 200.0)]
    assert len(b.zdarzenia) <= 4 and okno.mysz == (300.0, 200.0)


def test_preferencje_profilu_scalone_z_przegladarka(tmp_path):
    profil, pobrane = tmp_path / "profil", tmp_path / "pobrane"
    (profil / "Default").mkdir(parents=True)
    (profil / "Default" / "Preferences").write_text(json.dumps({
        "profile": {"exit_type": "Crashed", "exited_cleanly": False, "name": "Jarvo"},
        "credentials_enable_service": False, "extensions": {"x": 1}}), encoding="utf-8")
    (profil / "SingletonLock").write_text("x", encoding="utf-8")
    przegladarka.przygotuj_profil(profil, pobrane)
    p = json.loads((profil / "Default" / "Preferences").read_text(encoding="utf-8"))
    assert p["credentials_enable_service"] is True and p["profile"]["password_manager_enabled"] is True
    assert p["profile"]["exit_type"] == "Normal" and p["profile"]["exited_cleanly"] is True
    assert p["profile"]["name"] == "Jarvo" and p["extensions"] == {"x": 1}          # reszta przeglądarki zostaje
    assert p["autofill"]["credit_card_enabled"] is False and p["signin"]["allowed"] is False
    assert p["download"]["default_directory"] == str(pobrane) and p["download"]["prompt_for_download"] is False
    assert p["safebrowsing"]["enabled"] is True
    # WebRTC drugi raz w preferencjach: pełny Chrome je czyta (chrome-headless-shell tylko flagę)
    assert p["webrtc"] == {"ip_handling_policy": "disable_non_proxied_udp", "multiple_routes_enabled": False,
                           "nonproxied_udp_enabled": False}
    assert p["profile"]["default_content_setting_values"]["clipboard"] == 2
    assert not (profil / "SingletonLock").exists() and pobrane.is_dir()


@pytest.mark.parametrize("nazwa", ["instalator.exe", "SETUP.MSI", "faktura.pdf.exe", "skrypt.ps1", "a.bat", "x.cmd",
                                   "obraz.iso", "app.dmg", "paczka.pkg", "run.sh", "x.AppImage", "skrot.lnk",
                                   "makro.vbs", "lib.dll", "plik.jar", "a.scr", "instaluj.exe.", "x.command"])
def test_pliki_wykonywalne_odrzucane(nazwa):
    assert przegladarka.wykonywalny(nazwa)


@pytest.mark.parametrize("nazwa", ["faktura.pdf", "zdjecie.JPG", "dane.csv", "umowa.docx", "archiwum.zip", "README"])
def test_dokumenty_przechodza(nazwa):
    assert not przegladarka.wykonywalny(nazwa)


def test_bezpieczna_nazwa_pobranego_pliku(tmp_path):
    assert przegladarka.bezpieczna_nazwa("../../etc/passwd", tmp_path) == "passwd"
    assert przegladarka.bezpieczna_nazwa("C:\\Windows\\win.ini", tmp_path) == "win.ini"
    assert przegladarka.bezpieczna_nazwa('fa"k:t*u?r|a.pdf', tmp_path) == "fa_k_t_u_r_a.pdf"
    assert przegladarka.bezpieczna_nazwa("CON.txt", tmp_path) == "pobrany-plik.txt"
    (tmp_path / "faktura.pdf").write_text("x", encoding="utf-8")
    assert przegladarka.bezpieczna_nazwa("faktura.pdf", tmp_path) == "faktura (2).pdf"
    dluga = przegladarka.bezpieczna_nazwa("a" * 400 + ".pdf", tmp_path)
    assert len(dluga) <= 150 and dluga.endswith(".pdf")
    # ucięcie długiej nazwy nie zostawia rozszerzenia programu ze środka („….exe.pdf” → „….exe”)
    for nazwa in ("a" * 146 + ".exe.pdf", "b" * 147 + ".exe" + "c" * 20 + ".pdf"):
        wynik = przegladarka.bezpieczna_nazwa(nazwa, tmp_path)
        assert len(wynik) <= 150 and wynik.endswith(".pdf") and not przegladarka.wykonywalny(wynik), wynik


def test_program_przegladarki(tmp_path):
    assert przegladarka.program({}, {}) is None
    assert przegladarka.program({"JARVO_KOMPUTER_CHROME_PROBA": "x"}, {}) == "x"
    narz = {"chrome-komputer": {"env": {"JARVO_KOMPUTER_CHROME": str(tmp_path / "chrome")}}}
    assert przegladarka.program({}, narz) == str(tmp_path / "chrome")
    assert przegladarka.program({"JARVO_KOMPUTER_CHROME": "y"}, narz) == "y"


def test_x64_w_emulacji_po_naglowku_pe(tmp_path):
    """Windows ARM64: wyłączone GPU tylko dla przeglądarki x64 (emulacja); natywny Chromium ARM64 i inne systemy nie."""
    def pe(maszyna: int):
        dane = bytearray(4096)
        dane[:2] = b"MZ"
        dane[0x3C:0x40] = (0x80).to_bytes(4, "little")
        dane[0x80:0x84] = b"PE\0\0"
        dane[0x84:0x86] = maszyna.to_bytes(2, "little")
        p = tmp_path / f"chrome-{maszyna:x}.exe"
        p.write_bytes(bytes(dane))
        return p
    x64, arm = pe(0x8664), pe(0xAA64)
    assert przegladarka.x64_w_emulacji(x64, "ARM64") and not przegladarka.x64_w_emulacji(arm, "ARM64")
    assert not przegladarka.x64_w_emulacji(x64, "AMD64") and not przegladarka.x64_w_emulacji(tmp_path / "brak", "ARM64")
