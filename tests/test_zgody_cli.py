"""`jarvo doctor`: wtyczka zgód w każdym profilu bramy i restart po jej dodaniu (jarvo/zgody_cli.py, ryzyko Z39).
Prawdziwy skrypt na Pythonie testów (PyYAML jak w Hermesie) na atrapie <dane>: host, profile floty i obcy."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from jarvo import sciezki, zgody_cli as zc  # noqa: E402


def _profil(dom: Path, *, wlaczona=True, jest=True):
    dom.mkdir(parents=True, exist_ok=True)
    (dom / "config.yaml").write_text("plugins:\n  enabled: [jarvo-wiedza" + (", jarvo-zgody" if wlaczona else "")
                                     + "]\nmodel:\n  default: atrapa\n", encoding="utf-8")
    if jest:
        (dom / "plugins" / zc.NAZWA).mkdir(parents=True, exist_ok=True)
        (dom / "plugins" / zc.NAZWA / "plugin.yaml").write_text("name: jarvo-zgody\n", encoding="utf-8")


@pytest.fixture
def u(tmp_path, monkeypatch):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    _profil(u.dane)
    for p in ("jarvo", "jarvo-web"):
        _profil(u.dane / "profiles" / p)
    monkeypatch.setattr(zc, "_python_hermesa", lambda _u: Path(sys.executable))
    return u


def test_wszystkie_profile_z_wtyczka(u):
    w = zc.sprawdzenie(u, flota_agenci=["jarvo", "jarvo-web"], start=None)
    assert w["stan"] == "ok" and "host i 2 profili" in w["opis"]


def test_profil_floty_bez_wtyczki_to_blad(u):
    _profil(u.dane / "profiles" / "jarvo-web", wlaczona=False)
    w = zc.sprawdzenie(u, flota_agenci=["jarvo", "jarvo-web"], start=None)
    assert w["stan"] == "blad" and "jarvo-web" in w["opis"] and "instalację ponownie" in w["rada"]
    _profil(u.dane / "profiles" / "jarvo-web")
    (u.dane / "profiles" / "jarvo-web" / "plugins" / zc.NAZWA / "plugin.yaml").unlink()        # włączona, ale nie ma
    assert zc.sprawdzenie(u, flota_agenci=["jarvo", "jarvo-web"], start=None)["stan"] == "blad"


def test_obcy_profil_bez_wtyczki_to_uwaga_a_katalog_bez_configu_pomijany(u):
    _profil(u.dane / "profiles" / "moj-wlasny", wlaczona=False, jest=False)
    (u.dane / "profiles" / "po-usunieciu" / "logs").mkdir(parents=True)          # resztka bez config.yaml
    w = zc.sprawdzenie(u, flota_agenci=["jarvo", "jarvo-web"], start=None)
    assert w["stan"] == "uwaga" and "moj-wlasny" in w["opis"] and "po-usunieciu" not in w["opis"]


def _lacze(cel: Path, wpis: Path) -> None:
    """Wtyczka profilu jak z instalatora floty: dowiązanie (POSIX) albo junction (Windows, bez administratora)."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(cel), str(wpis))
    else:
        wpis.symlink_to(cel, target_is_directory=True)


def test_wtyczka_dodana_po_starcie_bramy(u):
    """Z39: dowiązanie wtyczki powstałe po starcie bramy = uwaga z radą restartu; po restarcie (późniejszy start) ok.
    Kopia katalogu (host) i import w bramie (__pycache__) nie dają uwagi: data kopii nie mówi, kiedy doszła."""
    import shutil
    web = u.dane / "profiles" / "jarvo-web" / "plugins"
    shutil.rmtree(web / zc.NAZWA)
    _lacze(u.dane / "plugins" / zc.NAZWA, web / zc.NAZWA)
    (u.dane / "plugins" / zc.NAZWA / "__pycache__").mkdir()          # import w bramie po jej starcie
    start = time.time() - 60
    w = zc.sprawdzenie(u, flota_agenci=["jarvo", "jarvo-web"], start=start)
    assert w["stan"] == "uwaga" and "jarvo-web" in w["opis"] and w["rada"] == "jarvo serwis --restart brama"
    assert "host" not in w["opis"] and "jarvo," not in w["opis"]
    assert zc.sprawdzenie(u, flota_agenci=["jarvo", "jarvo-web"], start=time.time() + 5)["stan"] == "ok"



def test_config_nieczytelny_to_brak_wtyczki(u):
    (u.dane / "profiles" / "jarvo" / "config.yaml").write_text("plugins: [\n", encoding="utf-8")
    w = zc.sprawdzenie(u, flota_agenci=["jarvo", "jarvo-web"], start=None)
    assert w["stan"] == "blad" and "jarvo" in w["opis"]


def test_bez_hermesa_i_bez_instalacji(u, tmp_path, monkeypatch):
    monkeypatch.setattr(zc, "_python_hermesa", lambda _u: None)
    assert zc.sprawdzenie(u, flota_agenci=[], start=None)["stan"] == "uwaga"
    pusty = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "nic")})
    assert "nie jest zainstalowane" in zc.sprawdzenie(pusty, flota_agenci=[], start=None)["opis"]


def test_start_bramy_z_nadzorca_json(u):
    assert zc.start_bramy(u) is None                                   # nadzorca nigdy nie działał
    u.stan.mkdir(parents=True, exist_ok=True)
    (u.stan / "nadzorca.json").write_text(json.dumps({"nadzorca": {"pid": 1, "odcisk": "x", "stan": "dziala"},
                                                      "uslugi": {"brama": {"stan": "dziala",
                                                                           "od": "2026-10-25T07:30:18+00:00"}}}),
                                          encoding="utf-8")
    assert zc.start_bramy(u) is None                                   # zapisany pid nie żyje: stan nieaktualny
