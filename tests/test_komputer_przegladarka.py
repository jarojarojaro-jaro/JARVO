"""Przeglądarka Jarva natywnie (komputer/przegladarka.py, docs/NATYWNIE.md J01, J06, J07, J11): flagi startu,
preferencje profilu, pobrane pliki (bez programów) i wybór programu przeglądarki. Bez przeglądarki: czyste funkcje."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from komputer import przegladarka  # noqa: E402


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


def test_flagi_bez_oslabien_playwrighta_i_portu_cdp(tmp_path):
    """Bez wyłączania blokady wyskakujących okien i ochrony przed phishingiem, bez portu DevTools (CDP tylko po
    potoku) i bez piaskownicy wyłączonej domyślnie."""
    f = " ".join(przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=True))
    for zakazana in ("--disable-popup-blocking", "--disable-client-side-phishing-detection", "--remote-debugging-port",
                     "--no-sandbox", "--disable-web-security", "--enable-automation", "--disable-background-networking"):
        assert zakazana not in f, zakazana
    assert "--no-sandbox" in przegladarka.flagi(profil=tmp_path, port_proxy=1, okno=True, bez_piaskownicy=True)


def test_preferencje_profilu_scalone_z_przegladarka(tmp_path):
    profil, pobrane = tmp_path / "profil", tmp_path / "pobrane"
    (profil / "Default").mkdir(parents=True)
    (profil / "Default" / "Preferences").write_text(json.dumps({
        "profile": {"exit_type": "Crashed", "exited_cleanly": False, "name": "Jarvo"},
        "credentials_enable_service": True, "extensions": {"x": 1}}), encoding="utf-8")
    (profil / "SingletonLock").write_text("x", encoding="utf-8")
    przegladarka.przygotuj_profil(profil, pobrane)
    p = json.loads((profil / "Default" / "Preferences").read_text(encoding="utf-8"))
    assert p["credentials_enable_service"] is False and p["profile"]["password_manager_enabled"] is False
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
