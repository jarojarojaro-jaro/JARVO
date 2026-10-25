"""Instalacja przy pierwszym użyciu (jarvo/przy_uzyciu.py) i program `manimgx` z bin-floty (jarvo/manimgx.py):
docs/NATYWNIE.md c3 pkt 9, M04, etap E11.

Narzędzie z manifestu pobiera atrapa serwera na 127.0.0.1 (pobieracz przyjmuje pętlę zwrotną tylko w testach), venv
instaluje atrapa jarvo/venvy.zainstaluj. Bez sieci. Na żywo (prawdziwe venvy cad i manimgx, three, platform-tools,
scrcpy): tests/live/natywnie_telefon_3d.py.
"""
from __future__ import annotations

import dataclasses
import hashlib
import http.server
import io
import json
import os
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from conftest import REPO, load_script

sys.path.insert(0, str(REPO))
from jarvo import instalator, przy_uzyciu, sciezki, srodowisko, venvy  # noqa: E402

MG = load_script("jarvo/manimgx.py", "manimgx_natywnie")
WINDOWS = os.name == "nt"
PLATFORMA = "windows-x64"
# Python bez venvu (jak python-build-standalone w instalacji): launcher distlib bierze koło pip z jego ensurepip
PYTHON = Path(sys.base_prefix) / "python.exe" if WINDOWS else Path(sys.executable)


def _zip(pliki: dict[str, bytes]) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, d in pliki.items():
            z.writestr(n, d)
    return b.getvalue()


@pytest.fixture
def serwer():
    """Serwer plików na 127.0.0.1 (port od systemu) z licznikiem pobrań."""
    pliki: dict[str, bytes] = {}
    pobrania: list[str] = []

    class Obsluga(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - nazwa z http.server
            dane = pliki.get(self.path)
            pobrania.append(self.path)
            if dane is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(dane)))
            self.end_headers()
            self.wfile.write(dane)

        def log_message(self, *_a):
            pass

    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Obsluga)
    watek = threading.Thread(target=s.serve_forever, daemon=True)
    watek.start()
    try:
        yield {"adres": f"http://127.0.0.1:{s.server_address[1]}", "pliki": pliki, "pobrania": pobrania}
    finally:
        s.shutdown()
        s.server_close()


def _instalacja(tmp_path: Path, narzedzia: dict | None = None, venvy_m: dict | None = None) -> tuple:
    """Instalacja natywna w katalogu tymczasowym z własnym kodem Jarva (manifest) i current.json."""
    app = tmp_path / "app"
    (app / "vendor").mkdir(parents=True)
    (app / "vendor" / "natywne.lock.json").write_text(json.dumps({
        "version": 1, "hermes": {}, "narzedzia": narzedzia or {}, "modele": {}, "venvy": venvy_m or {}}),
        encoding="utf-8")
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "Jarvo")})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    u.stan.mkdir(parents=True, exist_ok=True)
    (u.program / "current.json").write_text(json.dumps({"app": str(app)}), encoding="utf-8")
    return u, app


def _wpis_atrapy(serwer: dict, dane: bytes, *, suma: str | None = None) -> dict:
    serwer["pliki"]["/atrapa-1.0.zip"] = dane
    return {"atrapa": {"wersja": "1.0", "kiedy": "przy-uzyciu", "pliki": {
        PLATFORMA: {"url": f"{serwer['adres']}/atrapa-1.0.zip", "sha256": suma or hashlib.sha256(dane).hexdigest(),
                    "rozmiar": len(dane), "format": "zip", "usun_poziom": 1, "bin": ["."], "usun": ["zbedny.txt"],
                    "env": {"ATRAPA_DIR": "{katalog}", "ATRAPA_TRYB": "0"}},
        "linux-arm64": {"brak": "atrapa nie ma wydania na Linux arm64"}}}}


# ------------------------------------------------------------------ narzędzia z manifestu

def test_narzedzie_przy_pierwszym_uzyciu_z_suma_i_wpisem(tmp_path, serwer):
    dane = _zip({"atrapa-1.0/program.txt": b"ok", "atrapa-1.0/zbedny.txt": b"x"})
    u, app = _instalacja(tmp_path, _wpis_atrapy(serwer, dane))
    (u.stan / "narzedzia.json").write_text(json.dumps({"uv": {"wersja": "0.12.13"}}), encoding="utf-8")
    assert przy_uzyciu.gotowe_narzedzie(u, "atrapa", platforma=PLATFORMA) is None
    logi = []
    w = przy_uzyciu.narzedzie(u, "atrapa", platforma=PLATFORMA, log=logi.append, pasek=False)
    katalog = u.program / "narzedzia" / "atrapa" / "1.0"
    assert w == {"wersja": "1.0", "katalog": str(katalog), "bin": [str(katalog / ".")],
                 "env": {"ATRAPA_DIR": str(katalog), "ATRAPA_TRYB": "0"}}
    assert (katalog / "program.txt").read_text() == "ok" and not (katalog / "zbedny.txt").exists()
    assert "pierwsze użycie" in logi[0] and serwer["pobrania"] == ["/atrapa-1.0.zip"]
    spis = (u.stan / "narzedzia.json").read_text(encoding="utf-8")
    assert json.loads(spis) == {"uv": {"wersja": "0.12.13"}, "atrapa": w}           # inne wpisy zostają
    assert spis == instalator._json(json.loads(spis))                               # format instalatora
    assert przy_uzyciu.narzedzie(u, "atrapa", platforma=PLATFORMA, log=logi.append) == w
    assert serwer["pobrania"] == ["/atrapa-1.0.zip"]                                  # drugi raz bez sieci
    assert przy_uzyciu.gotowe_narzedzie(u, "atrapa", platforma=PLATFORMA) == w
    srodowisko_floty = srodowisko.srodowisko(u, {"PATH": ""})
    assert srodowisko_floty["ATRAPA_DIR"] == str(katalog)                              # procesy Jarva po restarcie
    assert str(katalog / ".") in srodowisko_floty["PATH"].split(os.pathsep)


def test_srodowisko_json_jak_z_instalatora(tmp_path, serwer, monkeypatch):
    """Po instalacji przy użyciu `<stan>/srodowisko.json` ma zmienne narzędzia i tę samą treść, którą zapisałby krok
    „Środowisko procesów” instalatora (baza = ustawienia instalacji, bez PATH i zmiennych właściciela), więc drugi
    przebieg instalacji niczego nie zmienia."""
    dane = _zip({"atrapa-1.0/program.txt": b"ok", "atrapa-1.0/zbedny.txt": b"x"})
    u, _app = _instalacja(tmp_path, _wpis_atrapy(serwer, dane))
    (u.stan / "ustawienia.json").write_text(json.dumps({"JARVO_PANEL_PORT": "19260"}), encoding="utf-8")
    (u.stan / "srodowisko.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("SEKRET_WLASCICIELA_TOKEN", "x" * 20)
    przy_uzyciu.narzedzie(u, "atrapa", platforma=PLATFORMA, log=lambda t: None, pasek=False)
    plik = json.loads((u.stan / "srodowisko.json").read_text(encoding="utf-8"))
    assert plik["ATRAPA_DIR"] == str(u.program / "narzedzia" / "atrapa" / "1.0") and plik["JARVO_PANEL_PORT"] == "19260"
    assert "SEKRET_WLASCICIELA_TOKEN" not in plik and os.environ["PATH"] not in plik.get("PATH", "")
    przed = (u.stan / "srodowisko.json").read_bytes()
    narz = srodowisko.narzedzia(u)
    srodowisko.zapisz(u, srodowisko.srodowisko(u, {"JARVO_PANEL_PORT": "19260"}, narz=narz), narz=narz)
    assert (u.stan / "srodowisko.json").read_bytes() == przed                         # jak instalator
    assert not przy_uzyciu.odswiez_srodowisko(u)


def test_uklad_instalacji_cache_z_zapisu_instalatora(tmp_path, serwer):
    """Linux z domyślnym korzeniem: instalator (bez JARVO_ROOT) ma cache w ~/.cache/jarvo, a proces floty ma JARVO_ROOT,
    który w sciezki.uklad przenosi cache pod korzeń. Pierwsze użycie z procesu floty ma pobierać do cache instalacji
    i zapisać srodowisko.json tak jak instalator: jego następny przebieg nie widzi zmiany (bajt w bajt)."""
    dane = _zip({"atrapa-1.0/program.txt": b"ok", "atrapa-1.0/zbedny.txt": b"x"})
    u_floty, _app = _instalacja(tmp_path, _wpis_atrapy(serwer, dane))          # układ spod JARVO_ROOT: cache w korzeniu
    u_inst = dataclasses.replace(u_floty, cache=tmp_path / "xdg-cache" / "jarvo",
                                 logi=tmp_path / "xdg-state" / "jarvo" / "logi")
    ust = {"JARVO_PANEL_PORT": "19260"}
    (u_inst.stan / "ustawienia.json").write_text(json.dumps(ust), encoding="utf-8")
    narz0 = {"uv": {"wersja": "0.12.13"}}
    (u_inst.stan / "narzedzia.json").write_text(instalator._json(narz0), encoding="utf-8")
    srodowisko.zapisz(u_inst, srodowisko.srodowisko(u_inst, dict(ust), narz=narz0), narz=narz0)   # krok instalatora
    assert przy_uzyciu.uklad({"JARVO_ROOT": str(u_floty.root)}).cache == u_inst.cache
    u = przy_uzyciu.uklad({"JARVO_ROOT": str(u_floty.root)})
    assert (u.root, u.program, u.stan, u.dane) == (u_floty.root, u_floty.program, u_floty.stan, u_floty.dane)
    przy_uzyciu.narzedzie(u, "atrapa", platforma=PLATFORMA, log=lambda t: None, pasek=False)
    plik = (u.stan / "srodowisko.json").read_bytes()
    env = json.loads(plik)
    assert env["UV_CACHE_DIR"] == str(u_inst.cache / "uv") and env["HF_HOME"] == str(u_inst.cache / "huggingface")
    assert env["ATRAPA_DIR"] == str(u.program / "narzedzia" / "atrapa" / "1.0")
    narz = srodowisko.narzedzia(u_inst)
    srodowisko.zapisz(u_inst, srodowisko.srodowisko(u_inst, dict(ust), narz=narz), narz=narz)    # drugi przebieg
    assert (u.stan / "srodowisko.json").read_bytes() == plik
    assert list((u_inst.cache / "pobrane").iterdir()) and not (u_floty.cache / "pobrane").exists()
    (u.stan / "srodowisko.json").unlink()                              # bez zapisu instalatora: układ bez zmian
    assert przy_uzyciu.uklad({"JARVO_ROOT": str(u_floty.root)}).cache == u_floty.cache


@pytest.mark.linux_only
def test_uklad_instalacji_linux_domyslny_korzen_z_otoczeniem_floty(tmp_path):
    """Prawdziwe reguły sciezki.uklad na Linuksie: instalator z katalogami XDG, proces floty z otoczeniem
    srodowisko.srodowisko (JARVO_ROOT i XDG_CACHE_HOME=<cache>/xdg) liczy ten sam cache co instalator."""
    xdg = {"XDG_DATA_HOME": str(tmp_path / "d"), "XDG_CACHE_HOME": str(tmp_path / "c"),
           "XDG_STATE_HOME": str(tmp_path / "s"), "HOME": str(tmp_path / "dom")}
    u_inst = sciezki.uklad(xdg)
    assert u_inst.cache == tmp_path / "c" / "jarvo" and u_inst.root == tmp_path / "d" / "jarvo"
    u_inst.stan.mkdir(parents=True)
    srodowisko.zapisz(u_inst, srodowisko.srodowisko(u_inst, {}, narz={}, biez={}, build={}), narz={}, build={})
    env_floty = srodowisko.srodowisko(u_inst, xdg, narz={}, biez={}, build={})
    assert sciezki.uklad(env_floty).cache != u_inst.cache                     # sam JARVO_ROOT: cache pod korzeniem
    assert przy_uzyciu.uklad(env_floty).cache == u_inst.cache


def test_bledy_instalacji_jako_blad_przy_uzyciu(tmp_path, monkeypatch, serwer):
    """Agent dostaje komunikat z radą, nie ślad stosu: uv zablokowany (BladHermesa z hermes._strumien), zapis na
    dysku (OSError) przy venvie i przy narzędziu."""
    from jarvo import hermes
    u, app = _instalacja(tmp_path)
    (app / "vendor" / "natywne.lock.json").write_text(json.dumps({"version": 1, "narzedzia": {},
                                                                  "venvy": _venv_wpis(app)}), encoding="utf-8")
    _uv_i_python(u, tmp_path)
    for wyjatek, tekst in ((hermes.BladHermesa("Nie uruchomię uv.exe: [WinError 1260] zablokowany przez zasady"),
                            "Smart App Control"), (PermissionError(13, "Brak dostępu"), "miejsce na dysku")):
        def zainstaluj(*_a, _w=wyjatek, **_k):
            raise _w
        monkeypatch.setattr(venvy, "zainstaluj", zainstaluj)
        with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match=tekst):
            przy_uzyciu.venv(u, "cad", log=lambda t: None)
    dane = _zip({"atrapa-1.0/program.txt": b"ok", "atrapa-1.0/zbedny.txt": b"x"})
    (app / "vendor" / "natywne.lock.json").write_text(json.dumps({"version": 1, "narzedzia": _wpis_atrapy(serwer, dane),
                                                                  "venvy": {}}), encoding="utf-8")

    def zapis(*_a, **_k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(przy_uzyciu.przenosne, "zapisz_atomowo", zapis)
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="No space left"):
        przy_uzyciu.narzedzie(u, "atrapa", platforma=PLATFORMA, log=lambda t: None, pasek=False)
    (app / "vendor" / "natywne.lock.json").write_text(json.dumps({"version": 1, "narzedzia": {"zle": {"wersja": "1"}},
                                                                  "venvy": {"cad": {"python": "python312"}}}),
                                                      encoding="utf-8")
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu):
        przy_uzyciu.narzedzie(u, "zle", platforma=PLATFORMA, log=lambda t: None)
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="bez locka"):
        przy_uzyciu.venv(u, "cad", log=lambda t: None)
    assert przy_uzyciu.gotowy_venv(u, "cad") is None


def test_narzedzie_zla_suma_brak_platformy_i_bez_instalacji(tmp_path, serwer):
    dane = _zip({"atrapa-1.0/program.txt": b"podmieniony"})
    u, _app = _instalacja(tmp_path, _wpis_atrapy(serwer, dane, suma="0" * 64))
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="suma"):
        przy_uzyciu.narzedzie(u, "atrapa", platforma=PLATFORMA, log=lambda t: None, pasek=False)
    assert not (u.program / "narzedzia" / "atrapa" / "1.0").exists()
    assert "atrapa" not in srodowisko.narzedzia(u)
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="Linux arm64"):
        przy_uzyciu.narzedzie(u, "atrapa", platforma="linux-arm64")
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="nie ma go w manifeście"):
        przy_uzyciu.narzedzie(u, "inne", platforma=PLATFORMA)
    (u.program / "current.json").unlink()
    assert not przy_uzyciu.natywnie(u)
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="instalacji natywnej"):
        przy_uzyciu.narzedzie(u, "atrapa", platforma=PLATFORMA)


def test_rozmiar_i_manifest_jarva_ma_wpisy_przy_uzyciu():
    """Wpisy E11 w manifeście tej wersji: platform-tools i scrcpy (licencja Google), venvy cad i manimgx."""
    narz = json.loads((REPO / "vendor" / "natywne.lock.json").read_text(encoding="utf-8"))
    for nazwa in ("platform-tools", "scrcpy"):
        assert narz["narzedzia"][nazwa]["kiedy"] == "przy-uzyciu"
    for nazwa in ("cad", "manimgx"):
        assert narz["venvy"][nazwa]["kiedy"] == "przy-uzyciu" and nazwa in venvy.ZMIENNE
    assert przy_uzyciu.rozmiar_mb(REPO, "platform-tools", "windows-x64") == 8.0
    assert przy_uzyciu.rozmiar_mb(REPO, "scrcpy", "linux-arm64") is None              # `brak` na tej platformie


# ------------------------------------------------------------------ venvy z locków

def _venv_wpis(app: Path) -> dict:
    lock = app / "lock.txt"
    lock.write_text("x==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
    return {"cad": {"python": "python312", "lock": "lock.txt", "sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
                    "paczek": 1, "kiedy": "przy-uzyciu", "venv_mb": 597,
                    "pobranie_mb": {PLATFORMA: 215, sciezki.platforma(): 215}}}  # komunikat liczy dla tego systemu


def _uv_i_python(u: Path, tmp_path: Path) -> None:
    uv_kat, py_kat = tmp_path / "uv", tmp_path / "py312"
    (uv_kat / ("uv.exe" if WINDOWS else "uv")).parent.mkdir(parents=True)
    (uv_kat / ("uv.exe" if WINDOWS else "uv")).write_bytes(b"")
    py = py_kat / ("python.exe" if WINDOWS else "bin/python3")
    py.parent.mkdir(parents=True)
    py.write_bytes(b"")
    (u.stan / "narzedzia.json").write_text(json.dumps({
        "uv": {"wersja": "0.12.13", "katalog": str(uv_kat), "bin": [str(uv_kat)]},
        "python312": {"wersja": "3.12.15", "katalog": str(py_kat), "bin": []}}), encoding="utf-8")


def test_venv_przy_pierwszym_uzyciu_przez_venvy(tmp_path, monkeypatch):
    u, app = _instalacja(tmp_path)
    (app / "vendor" / "natywne.lock.json").write_text(json.dumps({"version": 1, "narzedzia": {},
                                                                  "venvy": _venv_wpis(app)}), encoding="utf-8")
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="uv i python312"):
        przy_uzyciu.venv(u, "cad", log=lambda t: None)
    _uv_i_python(u, tmp_path)
    assert przy_uzyciu.gotowy_venv(u, "cad") is None
    wywolania = []

    def zainstaluj(u_, app_, nazwa, wpis, *, uv, python, log):
        wywolania.append((nazwa, Path(uv).name, Path(python).parent.name))
        kat = venvy.katalog(u_, nazwa, wpis)
        py = venvy.python_venvu(kat)
        py.parent.mkdir(parents=True)
        py.write_bytes(b"")
        (kat / venvy.ZNACZNIK).write_text(json.dumps({"lock_sha256": wpis["sha256"], "torch_backend": None,
                                                      "python_bazowy": str(python)}), encoding="utf-8")
        log("uv pip install …")
        return venvy.wpis_spisu(nazwa, wpis, kat), True

    monkeypatch.setattr(venvy, "zainstaluj", zainstaluj)
    logi = []
    w = przy_uzyciu.venv(u, "cad", log=logi.append)
    assert w["env"] == {"JARVO_CAD_PYTHON": w["python"]} and Path(w["python"]).is_file()
    assert "pierwsze użycie" in logi[0] and "215 MB" in logi[0] and "597 MB" in logi[0]
    assert srodowisko.narzedzia(u)["venv-cad"] == w and przy_uzyciu.gotowy_venv(u, "cad") == w
    assert wywolania[0][1].startswith("uv") and wywolania[0][2] in ("py312", "bin")
    o = przy_uzyciu.opis_venvu(u, "cad", platforma=PLATFORMA)
    assert o == {"venv": "cad", "python": "python312", "pobranie_mb": 215, "venv_mb": 597, "paczek": 1}

    def blad(*_a, **_k):
        raise venvy.BladVenvu("suma pliku z PyPI nie zgadza się z lockiem")
    monkeypatch.setattr(venvy, "zainstaluj", blad)
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="suma pliku"):
        przy_uzyciu.venv(u, "cad", log=lambda t: None)
    with pytest.raises(przy_uzyciu.BladPrzyUzyciu, match="nie ma go w manifeście"):
        przy_uzyciu.venv(u, "manimgx", log=lambda t: None)


# ------------------------------------------------------------------ manimgx w bin-floty (M04)

def test_manimgx_katalog_wyniku_i_cache(tmp_path, monkeypatch):
    assert MG.katalog_wyniku(["render", "s.py", "S", "-o", "out/szkic/s.mp4"]) == Path("out/szkic")
    assert MG.katalog_wyniku(["render", "s.py", "--output=a/b.mp4"]) == Path("a")
    assert MG.katalog_wyniku(["inspect", "s.py", "-o", "x/y"]) is None
    assert MG.katalog_cache({"MANIMGX_CACHE_DIR": str(tmp_path / "c")}) == tmp_path / "c"
    assert MG.katalog_cache({"JARVO_DATA_DIR": str(tmp_path / "dane" / "jarvo")}) == (
        tmp_path / "dane" / "jarvo" / "cache" / "manimgx")


def test_manimgx_znajduje_venv_albo_mowi_co_zrobic(tmp_path, monkeypatch):
    monkeypatch.setattr(MG, "VENV_KONTENER", tmp_path / "nie-ma")
    monkeypatch.setattr(MG.sys, "argv", [str(tmp_path / "bin-floty" / "manimgx")])
    with pytest.raises(MG.BladManimgx, match="dodatek `manim`"):
        MG.znajdz({})
    program = tmp_path / "venv" / ("Scripts/manimgx.exe" if WINDOWS else "bin/manimgx")
    program.parent.mkdir(parents=True)
    program.write_bytes(b"")
    assert MG.znajdz({"JARVO_MANIMGX_VENV": str(tmp_path / "venv")}) == program
    assert MG.znajdz({"JARVO_MANIMGX_PYTHON": str(program.with_name("python.exe" if WINDOWS else "python"))}) == program
    s = MG.stan({})
    assert s["gotowy"] is False and s["program"] is None


def _atrapa_przy_uzyciu(venv: Path, zlecone: list):
    class Atrapa:
        BladPrzyUzyciu = przy_uzyciu.BladPrzyUzyciu
        terminal = staticmethod(przy_uzyciu.terminal)

        def gotowy_venv(self, _u, nazwa):
            return {"katalog": str(venv)} if (venv / "gotowe").is_file() else None

        def venv(self, _u, nazwa, log):
            zlecone.append(nazwa)
            program = MG.program_venvu(venv)
            program.parent.mkdir(parents=True, exist_ok=True)
            program.write_bytes(b"")
            (venv / "gotowe").write_text("1")
            return {"katalog": str(venv)}

        def opis_venvu(self, _u, nazwa):
            return {"venv": nazwa, "pobranie_mb": 85, "venv_mb": 227}

    return Atrapa()


class Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_manimgx_bez_zgody_nie_pobiera_a_za_zgoda_instaluje(tmp_path, monkeypatch, capsys):
    """c3 pkt 9 („z paskiem i pytaniem”): w instalacji natywnej (JARVO_ROOT z current.json) brak venvu = kod 127
    z tym, ile pobierze i jak zainstalować (także `--version`: bez pobierania); `--jarvo-zainstaluj` (zgoda
    właściciela przez agenta) instaluje przez przy_uzyciu.venv. Potem argumenty bez zmian, MANIMGX_CACHE_DIR
    w <dane>/jarvo/cache/manimgx, katalog pliku z -o założony przed renderem."""
    u, app = _instalacja(tmp_path)
    monkeypatch.setattr(MG, "VENV_KONTENER", tmp_path / "nie-ma")
    monkeypatch.setattr(MG.sys, "stdin", io.StringIO(""))                          # bez terminala
    venv = tmp_path / "venvs" / "manimgx-abc"
    zlecone = []
    monkeypatch.setattr(MG, "przy_uzyciu", lambda env: (_atrapa_przy_uzyciu(venv, zlecone), u))
    with pytest.raises(MG.BladManimgx, match="nie jest jeszcze zainstalowany") as e:
        MG.znajdz({})
    assert e.value.do_instalacji and "85 MB" in e.value.opis and "227 MB" in e.value.opis
    assert MG.stan({"JARVO_DATA_DIR": str(u.jarvo_dane)})["przy_uzyciu"]["pobranie_mb"] == 85
    uruchomione = []
    monkeypatch.setattr(MG, "uruchom", lambda program, args, env: uruchomione.append((program, args, env)) or 7)
    monkeypatch.chdir(tmp_path)
    argv = ["render", "scena.py", "Proba", "-r", "640x360", "-o", "out/szkic/proba.mp4"]
    monkeypatch.setenv("JARVO_DATA_DIR", str(u.jarvo_dane))
    monkeypatch.delenv("MANIMGX_CACHE_DIR", raising=False)
    for przed in (["--version"], argv):
        assert MG.main(przed) == 127 and zlecone == [] and uruchomione == []
        err = capsys.readouterr().err
        assert "manimgx --jarvo-zainstaluj" in err and "Zapytaj właściciela" in err and "85 MB" in err
    assert MG.main(["--jarvo-zainstaluj"]) == 0 and zlecone == ["manimgx"]
    assert "ManimGX gotowy" in capsys.readouterr().out
    assert MG.main(argv) == 7 and zlecone == ["manimgx"]
    program, args, env = uruchomione[0]
    assert program == MG.program_venvu(venv) and args == argv
    assert env["MANIMGX_CACHE_DIR"] == str(u.jarvo_dane / "cache" / "manimgx")
    assert (tmp_path / "out" / "szkic").is_dir() and Path(env["MANIMGX_CACHE_DIR"]).is_dir()
    assert MG.main(["--version"]) == 7 and zlecone == ["manimgx"]                     # drugi raz bez instalacji


def test_terminal_tylko_prawdziwa_konsola():
    """Pytanie właściciela tylko w terminalu: proces w tle ma stdin z NUL, a na Windows NUL też „isatty” (wtedy liczy
    się GetConsoleMode); atrapa bez deskryptora = jej isatty()."""
    assert przy_uzyciu.terminal(Tty("")) and not przy_uzyciu.terminal(io.StringIO(""))
    assert not przy_uzyciu.terminal(None)
    with open(os.devnull, encoding="utf-8") as nul:
        assert not przy_uzyciu.terminal(nul)


@pytest.mark.parametrize("odpowiedz,flota,instaluje", [("t\n", None, True), ("n\n", None, False),
                                                        ("t\n", "HERMES_KANBAN_TASK", False)])
def test_manimgx_pyta_tylko_w_terminalu_wlasciciela(tmp_path, monkeypatch, capsys, odpowiedz, flota, instaluje):
    """Pytanie „Pobrać teraz? [t/N]” tylko w terminalu właściciela; proces floty (agent z terminalem, który może być
    pseudoterminalem) nie dostaje pytania, tylko kod 127 z radą."""
    u, _app = _instalacja(tmp_path)
    monkeypatch.setattr(MG, "VENV_KONTENER", tmp_path / "nie-ma")
    venv = tmp_path / "venvs" / "manimgx-abc"
    zlecone = []
    monkeypatch.setattr(MG, "przy_uzyciu", lambda env: (_atrapa_przy_uzyciu(venv, zlecone), u))
    monkeypatch.setattr(MG, "uruchom", lambda program, args, env: 0)
    monkeypatch.setattr(MG.sys, "stdin", Tty(odpowiedz))
    from jarvo import rece
    for z in (*rece.ZNACZNIKI_FLOTY, "HERMES_HOME"):
        monkeypatch.delenv(z, raising=False)
    if flota:
        monkeypatch.setenv(flota, "karta-1")
    assert MG.main(["--version"]) == (0 if instaluje else 127)
    assert zlecone == (["manimgx"] if instaluje else [])
    assert ("Pobrać teraz?" in capsys.readouterr().err) is (flota is None)


def test_manimgx_natywnie_venv_tej_wersji_a_nie_zmienna(tmp_path, monkeypatch):
    """Po aktualizacji locka zmienne bramy wskazują jeszcze stary venv: w instalacji natywnej liczy się venv dla
    locka tej wersji Jarva, a zmienne tylko poza nią."""
    u, _app = _instalacja(tmp_path)
    stary = tmp_path / "venv-stary"
    MG.program_venvu(stary).parent.mkdir(parents=True)
    MG.program_venvu(stary).write_bytes(b"")
    nowy = tmp_path / "venv-nowy"
    MG.program_venvu(nowy).parent.mkdir(parents=True)
    MG.program_venvu(nowy).write_bytes(b"")

    class Atrapa:
        BladPrzyUzyciu = przy_uzyciu.BladPrzyUzyciu

        def gotowy_venv(self, _u, _nazwa):
            return {"katalog": str(nowy)}

    monkeypatch.setattr(MG, "przy_uzyciu", lambda env: (Atrapa(), u))
    assert MG.znajdz({"JARVO_MANIMGX_VENV": str(stary)}) == MG.program_venvu(nowy)
    monkeypatch.setattr(MG, "przy_uzyciu", lambda env: (None, None))
    assert MG.znajdz({"JARVO_MANIMGX_VENV": str(stary)}) == MG.program_venvu(stary)


def test_manimgx_korzen_z_miejsca_programu(tmp_path, monkeypatch):
    """Uruchomiony pełną ścieżką bez JARVO_ROOT: korzeń z `<root>/program/bin-floty/manimgx`."""
    u, _app = _instalacja(tmp_path)
    monkeypatch.setattr(MG.sys, "argv", [str(u.bin_floty / ("manimgx.exe" if WINDOWS else "manimgx"))])
    assert MG.korzen_instalacji({}) == u.root
    assert MG.przy_uzyciu({}) == (None, None)                 # kod Jarva w current.json bez jarvo/przy_uzyciu.py
    pu, uklad = MG.przy_uzyciu({"JARVO_REPO": str(REPO)})      # procesy floty: JARVO_REPO = kod aktywnej wersji
    assert pu.__name__ == "jarvo.przy_uzyciu" and uklad.root == u.root


def test_manimgx_program_w_bin_floty(tmp_path):
    """`zainstaluj` daje samodzielny program (Windows: launcher distlib + zip, POSIX: sh + zip); drugi przebieg nic
    nie zmienia; program bez instalacji mówi przez --jarvo-stan, czego brakuje (JSON w UTF-8)."""
    bin_floty = tmp_path / "bin-floty"
    try:
        zmiany = MG.zainstaluj(bin_floty, PYTHON)
    except FileNotFoundError as e:                       # Python bez koła pip w ensurepip: brak launchera distlib
        pytest.skip(str(e))
    program = bin_floty / ("manimgx.exe" if WINDOWS else "manimgx")
    assert zmiany == [program] and MG.zainstaluj(bin_floty, PYTHON) == []
    tresc = program.read_bytes()
    assert zipfile.ZipFile(io.BytesIO(tresc)).read("__main__.py") == (REPO / "jarvo" / "manimgx.py").read_bytes()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("JARVO_", "MANIMGX_"))}
    kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}
    p = subprocess.run([str(program), "--jarvo-stan"], env=env, capture_output=True, text=True, encoding="utf-8",
                       timeout=60, **kw)
    assert p.returncode == 0, p.stderr
    s = json.loads(p.stdout)
    assert s["gotowy"] is False and "manim" in s["powod"]
