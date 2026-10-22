"""Klucz jednorazowy do dashboardu: infra/bin/jarvo-klucz i łatka dostawcy logowania (branding/patch_dashboard.py)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import stat
import time

import pytest

from conftest import REPO, load_script

BASIC_FIXTURE = '''\
import hashlib
import hmac
import json
import os
import time


class InvalidCredentialsError(Exception):
    pass


class NonInteractiveMixin:
    pass


class DashboardAuthProvider:
    pass


class BasicAuthProvider(NonInteractiveMixin, DashboardAuthProvider):
    name = "basic"

    def __init__(self, username, password):
        self._username, self._password = username, password

    def complete_password_login(self, *, username: str, password: str) -> Session:
        username_ok = hmac.compare_digest(username.encode(), self._username.encode())
        if not (username_ok and password == self._password):
            raise InvalidCredentialsError("invalid username or password")
        return self._mint_session(self._username)

    def _mint_session(self, user_id: str):
        return {"user": user_id}
'''


def _klucz_mod(katalog, monkeypatch):
    monkeypatch.setenv("JARVO_WEJSCIE_DIR", str(katalog))
    path = REPO / "infra" / "bin" / "jarvo-klucz"
    loader = importlib.machinery.SourceFileLoader("jarvo_klucz_test", str(path))
    spec = importlib.util.spec_from_loader("jarvo_klucz_test", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def dostawca(tmp_path, monkeypatch):
    katalog = tmp_path / "wejscie"
    klucz = _klucz_mod(katalog, monkeypatch)
    pd = load_script("branding/patch_dashboard.py")
    basic = tmp_path / "basic.py"
    basic.write_text(BASIC_FIXTURE, encoding="utf-8")
    pd.patch_klucz(basic)
    pd.patch_klucz(basic)                                   # drugi raz nic nie zmienia
    tekst = basic.read_text(encoding="utf-8")
    assert tekst.count("def _jarvo_klucz(") == 1 and tekst.count("if _jarvo_klucz(password)") == 1
    ns: dict = {"Session": dict}
    exec(compile(tekst, "basic.py", "exec"), ns)
    return klucz, ns["BasicAuthProvider"]("jarvo", "tajne-haslo"), ns["InvalidCredentialsError"], katalog


def _nowy(klucz, capsys, ttl=900):
    assert klucz.main(["nowy", "--ttl", str(ttl)]) == 0
    return capsys.readouterr().out.strip()


def test_nowy_klucz_zapisuje_tylko_skrot(dostawca, capsys):
    klucz, _, _, katalog = dostawca
    kod = _nowy(klucz, capsys)
    assert re.fullmatch(r"JRV(-[0-9A-HJKMNP-TV-Z]{4}){3}", kod)
    pliki = list(katalog.iterdir())
    assert [p.name for p in pliki] == [klucz.skrot(kod)]
    assert kod not in pliki[0].read_text(encoding="utf-8")
    assert stat.S_IMODE(katalog.stat().st_mode) == 0o700 and stat.S_IMODE(pliki[0].stat().st_mode) == 0o600
    assert 890 <= json.loads(pliki[0].read_text())["wygasa"] - time.time() <= 900


def test_klucz_wchodzi_raz_bez_hasla(dostawca, capsys):
    klucz, p, Invalid, katalog = dostawca
    kod = _nowy(klucz, capsys)
    assert p.complete_password_login(username="cokolwiek", password=kod.lower()) == {"user": "jarvo"}
    assert list(katalog.iterdir()) == []                    # zużyty: plik skrótu usunięty
    with pytest.raises(Invalid):
        p.complete_password_login(username="cokolwiek", password=kod)
    assert p.complete_password_login(username="jarvo", password="tajne-haslo") == {"user": "jarvo"}  # hasło dalej działa


def test_wygasly_i_obcy_klucz_nie_wchodzi(dostawca, capsys):
    klucz, p, Invalid, katalog = dostawca
    kod = _nowy(klucz, capsys)
    sciezka = katalog / klucz.skrot(kod)
    sciezka.write_text(json.dumps({"wygasa": int(time.time()) - 1}))
    with pytest.raises(Invalid):
        p.complete_password_login(username="jarvo", password=kod)
    assert not sciezka.exists()                             # nieudana próba też zużywa klucz
    with pytest.raises(Invalid):
        p.complete_password_login(username="jarvo", password="JRV-0000-0000-0000")
    with pytest.raises(Invalid):
        p.complete_password_login(username="jarvo", password="../../etc/passwd")


def test_najwyzej_piec_waznych_kluczy_i_sprzatanie(dostawca, capsys):
    klucz, p, _, katalog = dostawca
    kody = [_nowy(klucz, capsys) for _ in range(7)]
    assert len(list(katalog.iterdir())) == klucz.NAJWIECEJ
    for f in katalog.iterdir():                             # wygasłe znikają przy następnym kluczu
        f.write_text(json.dumps({"wygasa": 1}))
    ostatni = _nowy(klucz, capsys)
    assert [f.name for f in katalog.iterdir()] == [klucz.skrot(ostatni)]
    assert p.complete_password_login(username="x", password=ostatni)["user"] == "jarvo"
    assert kody[0] != kody[1]


def test_ttl_ograniczony(dostawca, capsys):
    klucz, _, _, katalog = dostawca
    kod = _nowy(klucz, capsys, ttl=999999)
    assert json.loads((katalog / klucz.skrot(kod)).read_text())["wygasa"] - time.time() <= 3600


def test_jarvo_open_i_link_nie_wypisuja_klucza_do_logu():
    jarvo = (REPO / "bin" / "jarvo").read_text(encoding="utf-8")
    assert "jarvo-klucz nowy" in jarvo and "link) cmd_link ;;" in jarvo
    otworz = jarvo[jarvo.index("cmd_open() {"):jarvo.index("cmd_link() {")]
    assert 'echo "$URL"' in otworz and "echo \"$u\"" not in otworz
    ps1 = (REPO / "install.ps1").read_text(encoding="utf-8")
    assert "jarvo link" in ps1 and "#klucz=JRV" in ps1
