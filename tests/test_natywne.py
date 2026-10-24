"""Instalacja natywna (docs/NATYWNIE.md, etapy E2–E3): katalogi, środowisko procesów, manifest narzędzi z sumami,
pobieracz (pasek, wznawianie, suma przed rozpakowaniem, bezpieczne archiwa) i przenośne prymitywy jarvo/przenosne.py."""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import threading
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import manifest, pobieracz, przenosne, sciezki, srodowisko  # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
import natywne  # noqa: E402


def test_manifest_kompletny_i_lock_aktualny():
    dane = natywne.wczytaj()
    import fleetlib as fl
    zrodla = (fl.load_yaml(REPO / "vendor" / "zrodla.yaml") or {}).get("zrodla") or {}
    assert natywne.bledy(dane, zrodla) == []
    assert (REPO / "vendor" / "natywne.lock.json").read_text(encoding="utf-8") == natywne.tekst_locka(dane)
    n = manifest.wczytaj(REPO)
    for nazwa in ("uv", "python313", "python312"):
        for platforma in sciezki.PLATFORMY:
            p = manifest.plik(n, nazwa, platforma)
            assert p["url"].startswith("https://") and len(p["sha256"]) == 64


HERMES_OK = {"repo": "https://github.com/NousResearch/hermes-agent", "tag": "v2026.9.24", "wersja": "0.21.5",
             "commit": "f97608f178d1ffeca59860195ab7da295f7c8e5f", "dodatki": ["all"]}


def test_manifest_hermes_przypiety_w_jednym_miejscu():
    dane = natywne.wczytaj()
    assert dane["hermes"]["commit"] == "f97608f178d1ffeca59860195ab7da295f7c8e5f"
    assert manifest.hermes(REPO)["tag"] == dane["hermes"]["tag"]
    b = "\n".join(natywne.bledy({"version": 1, "hermes": {"repo": "http://x", "commit": "f97608f", "dodatki": "all"},
                                 "narzedzia": {}}))
    assert "repo musi" in b and "pełnym SHA" in b and "brak tagu" in b and "dodatki to lista" in b
    b = "\n".join(natywne.bledy({"version": 1, "hermes": dict(HERMES_OK, tag="v2099.1.1"), "narzedzia": {}}))
    assert "różni się od obrazu VPS" in b


def test_manifest_lapie_braki():
    zly = {"version": 1, "hermes": HERMES_OK,
           "narzedzia": {"Zle_Nazwa": {"zrodlo": "nie-ma", "wersja": "1", "licencja": "MIT", "rola": "x",
                                                     "pliki": {"windows-x64": {"url": "http://x/latest/a.zip",
                                                                               "sha256": "abc", "format": "rar"}}}}}
    b = "\n".join(natywne.bledy(zly, {"uv": {}}))
    for fragment in ("nazwa tylko z małych", "nie ma w vendor/zrodla.yaml", "dokładnym adresem https", "64 znaki",
                     "rozmiar", "format spoza", "macos-arm64: brak pliku"):
        assert fragment in b
    dobry_brak = {"brak": "Lightpanda nie wydaje wersji na Windows", "zamiast": "chrome"}
    assert not [x for x in natywne.bledy({"version": 1, "hermes": HERMES_OK, "narzedzia": {"a": {
        "zrodlo": "uv", "wersja": "1", "licencja": "MIT", "rola": "x",
        "pliki": {p: dobry_brak for p in natywne.PLATFORMY}}}}, {"uv": {}}) if "brak" in x]


def test_platforma_bez_intela_na_macu():
    assert sciezki.platforma("win32", "AMD64") == "windows-x64"
    assert sciezki.platforma("win32", "ARM64") == "windows-arm64"
    assert sciezki.platforma("darwin", "arm64") == "macos-arm64"
    assert sciezki.platforma("linux", "x86_64") == "linux-x64"
    assert sciezki.platforma("linux", "aarch64") == "linux-arm64"
    with pytest.raises(sciezki.BladUkladu, match="Intel"):
        sciezki.platforma("darwin", "x86_64")


def test_uklad_z_jarvo_root(tmp_path):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j"), "PATH": ""})
    assert u.root == tmp_path / "j" and u.dane == u.root / "dane" and u.program == u.root / "program"
    assert u.logi == u.root / "logi" and u.cache == u.root / "cache" and u.stan == u.root / "stan"
    assert u.jarvo_dane == u.dane / "jarvo" and u.bin_floty == u.program / "bin-floty"


@pytest.mark.windows_only
def test_uklad_domyslny_windows():
    u = sciezki.uklad({"LOCALAPPDATA": r"C:\Users\x\AppData\Local"})
    assert str(u.root) == r"C:\Users\x\AppData\Local\Jarvo"


@pytest.mark.posix_only
def test_uklad_domyslny_posix(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    u = sciezki.uklad({"XDG_DATA_HOME": str(tmp_path / "xd"), "XDG_STATE_HOME": str(tmp_path / "xs"),
                       "XDG_CACHE_HOME": str(tmp_path / "xc")})
    if sys.platform == "darwin":
        assert u.root == tmp_path / ".jarvo" and u.logi == u.root / "logi"
    else:
        assert u.root == tmp_path / "xd" / "jarvo" and u.logi == tmp_path / "xs" / "jarvo" / "logi"
        assert u.cache == tmp_path / "xc" / "jarvo"


def test_srodowisko_procesow_i_plik_bez_sekretow(tmp_path):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    narz = {"node": {"wersja": "26", "bin": [str(tmp_path / "node")], "env": {"NODE_PATH": str(tmp_path / "nm")}}}
    biez = {"app": str(tmp_path / "app"), "hermes": str(tmp_path / "hermes")}
    baza = {"PATH": "/usr/bin", "HERMES_HOME": "/prywatny", "PYTHONPATH": "/x", "JARVO_TOKEN": "tajne",
            "OPENROUTER_API_KEY": "sk-or-tajne"}
    env = srodowisko.srodowisko(u, baza, biez=biez, narz=narz)
    assert env["HERMES_HOME"] == str(u.dane) and "PYTHONPATH" not in env
    assert env["HERMES_GATEWAY_LOCK_DIR"] == str(u.stan / "gateway-locks")
    assert env["PATH"].split(os.pathsep)[:2] == [str(u.bin_floty), str(tmp_path / "node")]
    assert env["PATH"].endswith("/usr/bin") and env["NODE_PATH"] == str(tmp_path / "nm")
    assert env["JARVO_REPO"] == str(tmp_path / "app") and env["HERMES_SRC"] == str(tmp_path / "hermes")
    plik = srodowisko.zapisz(u, env)
    tekst = plik.read_text(encoding="utf-8")
    assert "tajne" not in tekst and "JARVO_TOKEN" not in tekst and json.loads(tekst)["HERMES_HOME"] == str(u.dane)


class _Cichy(SimpleHTTPRequestHandler):
    def log_message(self, *_a):
        pass


@pytest.fixture
def serwer(tmp_path):
    katalog = tmp_path / "www"
    katalog.mkdir()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Cichy, directory=str(katalog)))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield katalog, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_pobierz_suma_wznowienie_i_odrzucenie(serwer, tmp_path):
    www, adres = serwer
    tresc = os.urandom(300_000)
    (www / "plik.bin").write_bytes(tresc)
    cel = tmp_path / "pobrane" / "plik.bin"
    wyj = io.StringIO()
    pobieracz.pobierz(f"{adres}/plik.bin", cel, _sha(tresc), len(tresc), nazwa="próba", wyjscie=wyj)
    assert cel.read_bytes() == tresc and "100%" in wyj.getvalue()
    # wznowienie: połowa już jest w .czesc
    cel2 = tmp_path / "p2" / "plik.bin"
    cel2.parent.mkdir()
    (cel2.parent / "plik.bin.czesc").write_bytes(tresc[:100_000])
    pobieracz.pobierz(f"{adres}/plik.bin", cel2, _sha(tresc), len(tresc), pasek=False)
    assert cel2.read_bytes() == tresc
    with pytest.raises(pobieracz.BladPobierania, match="suma sha256 się nie zgadza"):
        pobieracz.pobierz(f"{adres}/plik.bin", tmp_path / "p3" / "x.bin", "0" * 64, pasek=False)
    assert not (tmp_path / "p3" / "x.bin").exists() and not (tmp_path / "p3" / "x.bin.czesc").exists()
    with pytest.raises(pobieracz.BladPobierania, match="tylko adresy https"):
        pobieracz.pobierz("http://example.com/a.zip", tmp_path / "a.zip", "0" * 64)
    with pytest.raises(pobieracz.BladPobierania, match="HTTP 404"):
        pobieracz.pobierz(f"{adres}/nie-ma.bin", tmp_path / "n.bin", "1" * 64, pasek=False)


def test_rozpakuj_zip_tar_i_odrzuca_wyjscie_poza_katalog(tmp_path):
    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("narzedzie-1.0/bin/prog.txt", "ok")
        zf.writestr("narzedzie-1.0/README", "r")
    pobieracz.rozpakuj(z, tmp_path / "z", "zip", usun_poziom=1)
    assert (tmp_path / "z" / "bin" / "prog.txt").read_text(encoding="utf-8") == "ok"
    t = tmp_path / "a.tar.gz"
    with tarfile.open(t, "w:gz") as tf:
        dane = b"tar-ok"
        info = tarfile.TarInfo("python/bin/x.txt")
        info.size = len(dane)
        tf.addfile(info, io.BytesIO(dane))
    pobieracz.rozpakuj(t, tmp_path / "t", "tar.gz", usun_poziom=1)
    assert (tmp_path / "t" / "bin" / "x.txt").read_bytes() == b"tar-ok"
    zly = tmp_path / "zly.zip"
    with zipfile.ZipFile(zly, "w") as zf:
        zf.writestr("../../poza.txt", "x")
    with pytest.raises(pobieracz.BladPobierania, match="poza katalog"):
        pobieracz.rozpakuj(zly, tmp_path / "zz", "zip")
    assert not (tmp_path / "poza.txt").exists()


def test_zainstaluj_atomowo_i_bez_ponownego_pobrania(serwer, tmp_path):
    www, adres = serwer
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as zf:
        zf.writestr("uv.exe", "udawany")
    (www / "uv.zip").write_bytes(bufor.getvalue())
    wpis = {"url": f"{adres}/uv.zip", "sha256": _sha(bufor.getvalue()), "rozmiar": len(bufor.getvalue()),
            "format": "zip"}
    kat = pobieracz.zainstaluj("uv", "0.12.13+x", wpis, tmp_path / "n", tmp_path / "pob", pasek=False)
    assert kat == tmp_path / "n" / "uv" / "0.12.13" and (kat / "uv.exe").is_file()
    (www / "uv.zip").unlink()                       # drugi raz: bez sieci, bo suma w znaczniku się zgadza
    assert pobieracz.zainstaluj("uv", "0.12.13+x", wpis, tmp_path / "n", tmp_path / "pob", pasek=False) == kat
    assert not list((tmp_path / "n" / "uv").glob("*.new"))


def test_zapisz_atomowo_i_zamek(tmp_path):
    p = tmp_path / "a" / "stan.json"
    przenosne.zapisz_atomowo(p, '{"a": 1}\n')
    assert p.read_bytes() == b'{"a": 1}\n'
    przenosne.zapisz_atomowo(p, b"\x00\x01")
    assert p.read_bytes() == b"\x00\x01" and len(list(p.parent.iterdir())) == 1
    zamek = tmp_path / "zamek"
    kod = ("import sys; sys.path.insert(0, sys.argv[2]); from jarvo.przenosne import Zamek\n"
           "try:\n    Zamek(sys.argv[1], czekaj=False).__enter__()\n    print('wolny')\n"
           "except BlockingIOError:\n    print('zajety')\n")
    with przenosne.Zamek(zamek):
        wynik = subprocess.run([sys.executable, "-c", kod, str(zamek), str(REPO)], capture_output=True, text=True)
    assert wynik.stdout.strip() == "zajety"
    wynik = subprocess.run([sys.executable, "-c", kod, str(zamek), str(REPO)], capture_output=True, text=True)
    assert wynik.stdout.strip() == "wolny"


def test_chron_tylko_wlasciciel(tmp_path):
    p = tmp_path / ".env"
    p.write_text("A=1\n", encoding="utf-8")
    przenosne.chron(p)
    if os.name == "nt":
        acl = subprocess.run(["icacls", str(p)], capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout
        assert os.environ["USERNAME"].lower() in acl.lower() and "Everyone" not in acl and "(I)" not in acl
    else:
        assert p.stat().st_mode & 0o777 == 0o600
    assert p.read_text(encoding="utf-8") == "A=1\n"
