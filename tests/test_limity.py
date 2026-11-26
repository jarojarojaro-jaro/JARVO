"""scripts/limity.py: suma limitów pamięci włączonych kontenerów mieści się w pamięci Dockera."""

from __future__ import annotations

import os
import stat
import sys

import fleetlib as fl

sys.path.insert(0, str(fl.REPO_ROOT / "scripts"))
import limity  # noqa: E402

COMPOSE = (fl.REPO_ROOT / "infra/docker-compose.yml").read_text(encoding="utf-8")


def test_domyslne_limity_zgodne_z_compose():
    for klucz, dom, _, _, kontener in limity.USLUGI:
        assert f"${{{klucz}:-{dom // 1024}g}}" in COMPOSE, klucz
        assert f"container_name: {kontener}" in COMPOSE
    for m in (384, 96):
        assert f"limits: {{memory: {m}m}}" in COMPOSE


def test_mib():
    assert limity.mib("5g") == 5120 and limity.mib("2048m") == 2048 and limity.mib("1.5G") == 1536
    assert limity.mib("3221225472") == 3072 and limity.mib("512MB") == 512 and limity.mib("x") is None


def test_duzo_pamieci_bez_zmian():
    assert limity.policz(15000, {"COMPOSE_PROFILES": "komputer"}, {}) == ({}, [])


def test_mac_8gb_z_komputerem():
    """Colima 5 GB (Mac 8 GB): Hermes 5 GB + Komputer 2 GB przekraczają pamięć, dzielimy proporcjonalnie."""
    zmiany, kom = limity.policz(4915, {"COMPOSE_PROFILES": "komputer"}, {})
    assert zmiany == {"HERMES_MEM_LIMIT": "2688m", "KOMPUTER_MEM_LIMIT": "1024m"}
    assert sum(limity.mib(v) for v in zmiany.values()) <= 4915 - limity.SYSTEM_MIB - 384 - 96
    assert "4,8 GB" in kom[0] and len(kom) == 1


def test_wartosci_z_przykladu_env_sa_domyslne():
    """compose.env.example wpisuje HERMES_MEM_LIMIT=5g: to wartość domyślna, nie wybór właściciela."""
    env = {"HERMES_MEM_LIMIT": "5g", "ANDROID_MEM_LIMIT": "2g", "COMPOSE_PROFILES": "komputer"}
    assert limity.policz(4915, env, {})[0] == {"HERMES_MEM_LIMIT": "2688m", "KOMPUTER_MEM_LIMIT": "1024m"}
    assert limity.policz(15000, env, {}) == ({}, [])   # mieści się: plik zostaje jak był


def test_reczny_limit_zostaje_z_ostrzezeniem():
    zmiany, kom = limity.policz(4915, {"HERMES_MEM_LIMIT": "6g"}, {})
    assert zmiany == {} and "ustawiony ręcznie" in kom[0]


def test_za_malo_pamieci_mowi_co_zrobic():
    zmiany, kom = limity.policz(3000, {"COMPOSE_PROFILES": "komputer,android-kvm"}, {})
    assert zmiany["HERMES_MEM_LIMIT"] == "1536m" and zmiany["ANDROID_EMU_MEM_LIMIT"] == "2048m"   # dolne progi
    assert "za mało pamięci" in kom[-1]


def test_main_zapisuje_env_i_wraca_do_domyslnych(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DASHBOARD_PASSWORD=x\nCOMPOSE_PROFILES=komputer\n", encoding="utf-8")
    env.chmod(0o600)
    assert limity.main(["--compose", str(tmp_path), "--pamiec-mib", "4915"]) == 0
    tekst = env.read_text(encoding="utf-8")
    assert "DASHBOARD_PASSWORD=x" in tekst and "HERMES_MEM_LIMIT=2688m" in tekst and "KOMPUTER_MEM_LIMIT=1024m" in tekst
    if os.name != "nt":                   # limity.py to kod kontenerowy (host z Dockerem); tryb pliku tylko na POSIX
        assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert "HERMES_MEM_LIMIT=2688m" in (tmp_path / ".limity-auto").read_text(encoding="utf-8")
    # drugie wdrożenie bez zmian: nic się nie zmienia
    limity.main(["--compose", str(tmp_path), "--pamiec-mib", "4915"])
    assert env.read_text(encoding="utf-8") == tekst
    # Komputer wyłączony: jego limit wraca do domyślnego, Hermes dostaje więcej
    env.write_text(tekst.replace("COMPOSE_PROFILES=komputer\n", ""), encoding="utf-8")
    limity.main(["--compose", str(tmp_path), "--pamiec-mib", "4915"])
    tekst = env.read_text(encoding="utf-8")
    assert "KOMPUTER_MEM_LIMIT" not in tekst and "HERMES_MEM_LIMIT=3776m" in tekst
    # więcej pamięci (colima start --memory 12): wszystko wraca do domyślnych z docker-compose.yml
    limity.main(["--compose", str(tmp_path), "--pamiec-mib", "12000"])
    assert "MEM_LIMIT" not in env.read_text(encoding="utf-8")
    assert "MEM_LIMIT" not in (tmp_path / ".limity-auto").read_text(encoding="utf-8")


def test_reczna_zmiana_po_automacie_jest_wlasciciela(tmp_path):
    env = tmp_path / ".env"
    env.write_text("HERMES_MEM_LIMIT=3g\n", encoding="utf-8")
    (tmp_path / ".limity-auto").write_text("HERMES_MEM_LIMIT=3776m\n", encoding="utf-8")
    limity.main(["--compose", str(tmp_path), "--pamiec-mib", "12000"])
    assert "HERMES_MEM_LIMIT=3g" in env.read_text(encoding="utf-8")
