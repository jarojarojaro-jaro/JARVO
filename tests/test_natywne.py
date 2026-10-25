"""Instalacja natywna (docs/NATYWNIE.md, etapy E2–E3): katalogi, środowisko procesów, manifest narzędzi z sumami,
pobieracz (pasek, wznawianie, suma przed rozpakowaniem, bezpieczne archiwa) i przenośne prymitywy jarvo/przenosne.py."""
from __future__ import annotations

import hashlib
import io
import json
import os
import stat
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
    assert "JARVO_TOKEN" not in env and "OPENROUTER_API_KEY" not in env      # sekrety powłoki właściciela zostają u niego
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


def test_plik_laduje_pod_nazwa_z_manifestu(serwer, tmp_path):
    """Format plik: binarka w katalogu narzędzia ma nazwę z `nazwa_pliku` (albo zdekodowaną końcówkę adresu), a nie
    nazwę z pamięci podręcznej z przedrostkiem sumy (wtedy `jq` ani `lightpanda` nie byłoby w PATH)."""
    www, adres = serwer
    tresc = b"MZ udawane jq"
    (www / "jq-windows-amd64.exe").write_bytes(tresc)
    wpis = {"url": f"{adres}/jq-windows-amd64.exe", "sha256": _sha(tresc), "rozmiar": len(tresc), "format": "plik",
            "nazwa_pliku": "jq.exe"}
    kat = pobieracz.zainstaluj("jq", "1.8.2", wpis, tmp_path / "n", tmp_path / "pob", pasek=False)
    assert sorted(p.name for p in kat.iterdir()) == [".jarvo-suma", "jq.exe"]
    assert (kat / "jq.exe").read_bytes() == tresc
    if os.name != "nt":
        assert (kat / "jq.exe").stat().st_mode & 0o777 == 0o755
    (www / "agent+b").write_bytes(b"ab")                      # bez nazwa_pliku: końcówka adresu po zdekodowaniu
    wpis = {"url": f"{adres}/agent%2Bb", "sha256": _sha(b"ab"), "rozmiar": 2, "format": "plik"}
    kat = pobieracz.zainstaluj("ab", "1", wpis, tmp_path / "n", tmp_path / "pob", pasek=False)
    assert (kat / "agent+b").read_bytes() == b"ab"
    adres_pbs = "https://x/a/cpython-3.13.17%2B20261021-x.tar.gz?y=1"
    assert pobieracz.nazwa_z_adresu(adres_pbs) == "cpython-3.13.17+20261021-x.tar.gz" == \
        natywne.nazwa_pliku({"url": adres_pbs})
    # w prawdziwym manifeście env formatu plik wskazuje dokładnie ten plik (agent-browser, lightpanda, jq)
    for nazwa, w in natywne.wczytaj()["narzedzia"].items():
        for platforma, p in w["pliki"].items():
            if p.get("format") == "plik":
                assert pobieracz.nazwa_z_adresu(p["url"]) == natywne.nazwa_pliku(dict(p, nazwa_pliku=None))
                for v in (p.get("env") or {}).values():
                    assert not v.startswith("{katalog}/") or v == "{katalog}/" + natywne.nazwa_pliku(p), (nazwa, v)


def _zip_unix(sciezka: Path, wpisy: list[tuple[str, bytes, int]]) -> Path:
    """Zip jak z Uniksa: tryb pliku (z typem) w górnych bitach external_attr, dowiązanie = treść z jego celem."""
    with zipfile.ZipFile(sciezka, "w") as zf:
        for nazwa, dane, tryb in wpisy:
            zi = zipfile.ZipInfo(nazwa)
            zi.create_system = 3
            zi.external_attr = tryb << 16
            zf.writestr(zi, dane)
    return sciezka


LINK = stat.S_IFLNK | 0o777


def test_zip_dowiazania_i_uprawnienia(tmp_path):
    """qpdf (lib/libqpdf.so.30 → libqpdf.so.30.4.2) i pandoc dla macOS (bin/pandoc-lua → pandoc) mają w zipie
    dowiązania: na POSIX względne dowiązanie w katalogu, na Windows kopia celu; tryb 0o777 z zipa → 0o755."""
    z = _zip_unix(tmp_path / "qpdf.zip", [
        ("qpdf-12/lib/libqpdf.so.30.4.2", b"biblioteka", stat.S_IFREG | 0o777),
        ("qpdf-12/lib/libqpdf.so.30", b"libqpdf.so.30.4.2", LINK),
        ("qpdf-12/bin/pandoc", b"pandoc", stat.S_IFREG | 0o755),
        ("qpdf-12/bin/pandoc-server", b"pandoc-lua", LINK),               # łańcuch: server → lua → pandoc
        ("qpdf-12/bin/pandoc-lua", b"pandoc", LINK),
        ("qpdf-12/share/doc", b"../lib", LINK),                          # dowiązanie do katalogu w archiwum
        ("qpdf-12/README", b"r", stat.S_IFREG | 0o644)])
    kat = tmp_path / "q"
    pobieracz.rozpakuj(z, kat, "zip", usun_poziom=1)
    so, lua, server = kat / "lib" / "libqpdf.so.30", kat / "bin" / "pandoc-lua", kat / "bin" / "pandoc-server"
    assert so.read_bytes() == b"biblioteka" and lua.read_bytes() == server.read_bytes() == b"pandoc"
    assert (kat / "share" / "doc" / "libqpdf.so.30.4.2").read_bytes() == b"biblioteka"
    if os.name == "nt":
        assert not so.is_symlink() and not lua.is_symlink() and (kat / "share" / "doc").is_dir()
    else:
        assert os.readlink(so) == "libqpdf.so.30.4.2" and os.readlink(server) == "pandoc-lua"
        assert (kat / "lib" / "libqpdf.so.30.4.2").stat().st_mode & 0o777 == 0o755
        assert (kat / "README").stat().st_mode & 0o777 == 0o644
    for zly, cel in (("poza", b"../../poza"), ("abs", b"/etc/passwd"), ("dysk", b"C:/Windows/notepad.exe"),
                     ("pusty", b"")):
        z = _zip_unix(tmp_path / f"{zly}.zip", [("a/plik", b"x", stat.S_IFREG | 0o644), (f"a/{zly}", cel, LINK)])
        with pytest.raises(pobieracz.BladPobierania, match="poza katalog|bez celu"):
            pobieracz.rozpakuj(z, tmp_path / f"r-{zly}", "zip", usun_poziom=1)
    z = _zip_unix(tmp_path / "petla.zip", [("a/k/plik", b"x", stat.S_IFREG | 0o644), ("a/k/petla", b".", LINK)])
    if os.name == "nt":
        with pytest.raises(pobieracz.BladPobierania, match="pętla"):
            pobieracz.rozpakuj(z, tmp_path / "r-petla", "zip", usun_poziom=1)
    else:                                                              # na POSIX zostaje dowiązaniem jak w archiwum
        pobieracz.rozpakuj(z, tmp_path / "r-petla", "zip", usun_poziom=1)
        assert os.readlink(tmp_path / "r-petla" / "k" / "petla") == "."


def _tar(sciezka: Path, wpisy: list[tuple[str, str, bytes | str]]) -> Path:
    """tar.bz2 z plikami (`f`), twardymi (`h`, cel od korzenia archiwum) i symbolicznymi (`s`) dowiązaniami."""
    with tarfile.open(sciezka, "w:bz2") as tf:
        for rodzaj, nazwa, dane in wpisy:
            info = tarfile.TarInfo(nazwa)
            if rodzaj == "f":
                info.size, info.mode = len(dane), 0o755
                tf.addfile(info, io.BytesIO(dane))
                continue
            info.type = tarfile.LNKTYPE if rodzaj == "h" else tarfile.SYMTYPE
            info.linkname = dane
            tf.addfile(info)
    return sciezka


def test_tar_twarde_i_symboliczne_dowiazania(tmp_path):
    """Git for Windows: git-remote-https.exe to twarde dowiązanie (bez niego git nie zna https), cel liczony od
    korzenia archiwum, więc przy usun_poziom też przycięty. Symboliczne do /proc na Windows pomijamy, do pliku
    w archiwum zastępuje kopia; na POSIX tarfile odtwarza dowiązania, a te poza katalog odrzuca."""
    t = _tar(tmp_path / "git.tar.bz2", [
        ("f", "Git/ucrt64/libexec/git-core/git-remote-ftp.exe", b"git-remote"),
        ("h", "Git/ucrt64/libexec/git-core/git-remote-https.exe", "Git/ucrt64/libexec/git-core/git-remote-ftp.exe"),
        ("f", "Git/usr/bin/vim.exe", b"vim"),
        ("s", "Git/usr/bin/vi.exe", "vim.exe")])
    kat = tmp_path / "g"
    pobieracz.rozpakuj(t, kat, "tar.bz2", usun_poziom=1)
    https = kat / "ucrt64" / "libexec" / "git-core" / "git-remote-https.exe"
    assert https.read_bytes() == b"git-remote" and (kat / "usr" / "bin" / "vi.exe").read_bytes() == b"vim"
    assert (kat / "usr" / "bin" / "vi.exe").is_symlink() == (os.name != "nt")
    proc = _tar(tmp_path / "proc.tar.bz2", [("f", "Git/etc/profile", b"p"), ("s", "Git/dev/fd", "/proc/self/fd"),
                                            ("s", "Git/etc/mtab", "/proc/mounts")])
    if os.name == "nt":
        pobieracz.rozpakuj(proc, tmp_path / "p", "tar.bz2", usun_poziom=1)
        assert (tmp_path / "p" / "etc" / "profile").is_file() and not (tmp_path / "p" / "dev" / "fd").exists()
    else:
        with pytest.raises(pobieracz.BladPobierania, match="archiwum"):
            pobieracz.rozpakuj(proc, tmp_path / "p", "tar.bz2", usun_poziom=1)


@pytest.mark.windows_only
def test_tar_na_windows_twarde_dowiazanie_to_ten_sam_plik(tmp_path):
    """NTFS: tarfile robi twarde dowiązanie (os.link, bez admina), więc 92 kopie gita nie zajmują miejsca."""
    t = _tar(tmp_path / "g.tar.bz2", [("f", "a/git.exe", b"git" * 1000), ("h", "a/git-upload-pack.exe", "a/git.exe")])
    pobieracz.rozpakuj(t, tmp_path / "g", "tar.bz2")
    a, b = tmp_path / "g" / "a" / "git.exe", tmp_path / "g" / "a" / "git-upload-pack.exe"
    assert a.read_bytes() == b.read_bytes() and os.stat(a).st_nlink == 2 and os.path.samefile(a, b)


def test_usun_i_zmien_nazwe_po_rozpakowaniu(serwer, tmp_path):
    """platform-tools bez sqlite3 3.50.6 (błąd WAL-reset) i innych zbędnych programów, ExifTool jako exiftool.exe.
    Brak pliku z manifestu albo ścieżka poza katalog = błąd, a połowa narzędzia nie zostaje."""
    www, adres = serwer
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as zf:
        for nazwa in ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "fastboot.exe", "sqlite3.exe", "mke2fs.exe",
                      "mke2fs.conf", "make_f2fs.exe", "make_f2fs_casefold.exe", "etc1tool.exe", "hprof-conv.exe",
                      "libwinpthread-1.dll", "NOTICE.txt", "source.properties", "lib64/libc++.so",
                      "exiftool(-k).exe"):
            zf.writestr(f"platform-tools/{nazwa}", nazwa)
    (www / "pt.zip").write_bytes(bufor.getvalue())
    wpis = {"url": f"{adres}/pt.zip", "sha256": _sha(bufor.getvalue()), "rozmiar": len(bufor.getvalue()),
            "format": "zip", "usun_poziom": 1, "zmien_nazwe": {"exiftool(-k).exe": "exiftool.exe"},
            "usun": ["sqlite3.exe", "mke2fs.exe", "mke2fs.conf", "make_f2fs.exe", "make_f2fs_casefold.exe",
                     "etc1tool.exe", "hprof-conv.exe", "libwinpthread-1.dll", "lib64"]}
    kat = pobieracz.zainstaluj("platform-tools", "37.0.1", wpis, tmp_path / "n", tmp_path / "pob", pasek=False)
    assert sorted(p.name for p in kat.iterdir()) == [".jarvo-suma", "AdbWinApi.dll", "AdbWinUsbApi.dll", "NOTICE.txt",
                                                     "adb.exe", "exiftool.exe", "fastboot.exe", "source.properties"]
    for zle, komunikat in ((dict(wpis, usun=["nie-ma.exe"]), "usun: nie ma nie-ma.exe"),
                           (dict(wpis, usun=["../poza"]), "ścieżką względną"),
                           (dict(wpis, zmien_nazwe={"adb.exe": "fastboot.exe"}), "fastboot.exe już jest"),
                           (dict(wpis, zmien_nazwe={"nie-ma": "x"}), "zmien_nazwe: nie ma nie-ma")):
        with pytest.raises(pobieracz.BladPobierania, match=komunikat):
            pobieracz.zainstaluj("pt-zle", "1", zle, tmp_path / "n", tmp_path / "pob", pasek=False)
        assert not (tmp_path / "n" / "pt-zle").exists() or not list((tmp_path / "n" / "pt-zle").iterdir())


def test_manifest_waliduje_nowe_pola(tmp_path):
    """nazwa_pliku, env, usun, zmien_nazwe (natywne.py) i czekający blok platform-tools (zakomentowany, bo spis
    przyjmuje paczkę tylko jako tar): po odkomentowaniu przejdzie walidację."""
    dobry = {"url": "https://example.com/pt.zip", "sha256": "a" * 64, "rozmiar": 1, "format": "zip"}
    narz = {"pt": {"zrodlo": "uv", "wersja": "1", "licencja": "MIT", "rola": "x",
                   "pliki": {p: dict(dobry) for p in natywne.PLATFORMY}}}
    narz["pt"]["pliki"]["windows-x64"].update(usun=["../poza", "a", "a"], zmien_nazwe={"a": "/abs"},
                                              nazwa_pliku="kat/plik", env={"ZŁA-NAZWA": 1})
    narz["pt"]["pliki"]["linux-x64"].update(format="plik", usun=["x"], env={"JARVO_X": "{katalog}/inna-nazwa"})
    b = "\n".join(natywne.bledy({"version": 1, "hermes": HERMES_OK, "narzedzia": narz}, {"uv": {}}))
    for fragment in ("windows-x64: usun to lista", "windows-x64: zmien_nazwe to słownik", "nazwa_pliku to sama nazwa",
                     "windows-x64: env to słownik", "linux-x64: format plik nie ma czego usuwać",
                     "linux-x64: env JARVO_X wskazuje {katalog}/inna-nazwa, a plik ląduje jako {katalog}/pt.zip"):
        assert fragment in b
    tekst = (REPO / "vendor" / "natywne.yaml").read_text(encoding="utf-8")
    if "  # platform-tools:\n" in tekst:                    # wpis czeka na paczki zip w vendor/zrodla.yaml
        linie = []
        for linia in tekst[tekst.index("  # platform-tools:\n"):].splitlines():
            if not linia.startswith("  #"):
                break
            linie.append(linia.replace("  # ", "  ", 1) if linia.startswith("  # ") else "")
        blok = __import__("yaml").safe_load("narzedzia:\n" + "\n".join(linie))["narzedzia"]
    else:                                                    # po odkomentowaniu: ten sam wpis z manifestu
        blok = {"platform-tools": natywne.wczytaj()["narzedzia"]["platform-tools"]}
    assert set(blok) == {"platform-tools"}
    pt = blok["platform-tools"]
    assert "sqlite3.exe" in pt["pliki"]["windows-x64"]["usun"] and "sqlite3" in pt["pliki"]["macos-arm64"]["usun"]
    assert not {"adb", "adb.exe", "fastboot", "fastboot.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"} & \
        {u for p in pt["pliki"].values() for u in p.get("usun") or []}
    assert natywne.bledy({"version": 1, "hermes": HERMES_OK, "narzedzia": blok}, {"android-platform-tools": {}}) == []


def _lock_venvu(sciezka: Path, tekst: str) -> Path:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_text(tekst, encoding="utf-8", newline="\n")
    return sciezka


def test_venvy_w_manifescie_i_locku(tmp_path):
    """Sekcja venvy: lock z sumami w infra/python/, Python z sekcji narzedzia, pobranie_mb dla 5 platform; do locka
    trafia suma pliku (katalog venvu i kontrola zmiany), liczba paczek i --torch-backend dla instalatora."""
    h = "--hash=sha256:" + "b" * 64
    _lock_venvu(tmp_path / "infra" / "python" / "natywne" / "a.lock",
                f"# komentarz\nnumpy==2.4.6 \\\n    {h}\nen-core-web-sm @ https://example.com/e.whl \\\n    {h}\n")
    py = {"zrodlo": "uv", "wersja": "3.12", "licencja": "PSF", "rola": "x",
          "pliki": {p: {"brak": "test"} for p in natywne.PLATFORMY}}
    mb = {p: 10 for p in natywne.PLATFORMY}
    venv = {"python": "python312", "lock": "infra/python/natywne/a.lock", "rola": "x", "kiedy": "dodatek",
            "bez": ["docopt"], "pobranie_mb": mb, "torch_backend": "cpu"}
    dane = {"version": 1, "hermes": HERMES_OK, "narzedzia": {"python312": py}, "venvy": {"a": venv}}
    assert natywne.bledy(dane, {"uv": {}}, repo=tmp_path) == []
    v = natywne.lock(dane, repo=tmp_path)["venvy"]["a"]
    assert v["paczek"] == 2 and v["torch_backend"] == "cpu" and v["kiedy"] == "dodatek" and v["bez"] == ["docopt"]
    assert v["sha256"] == _sha((tmp_path / "infra" / "python" / "natywne" / "a.lock").read_bytes())
    _lock_venvu(tmp_path / "infra" / "python" / "natywne" / "zly.lock",
                f"--index-url https://example.com/simple\nrequests==2.0\ndocopt==0.6.2 \\\n    {h}\n")
    zle = {"python": "python399", "lock": "infra/python/natywne/zly.lock", "rola": "", "bez": ["docopt"],
           "pobranie_mb": {"windows-x64": 1}, "torch_backend": "cuda", "indeks": "x"}
    b = "\n".join(natywne.bledy(dict(dane, venvy={"zly": zle, "poza": dict(venv, lock="../a.lock"),
                                                  "brak": dict(venv, lock="infra/python/nie-ma.lock")}),
                                {"uv": {}}, repo=tmp_path))
    for fragment in ("nieznane pola ['indeks']", "python to wpis Pythona", "brak pola rola", "pobranie_mb to MB",
                     "torch_backend spoza", "opcja --index-url w locku", "requests: bez --hash=sha256",
                     "docopt jest w `bez`", "poza: lock to plik w infra/python/", "nie ma pliku infra/python/nie-ma"):
        assert fragment in b
    prawdziwe = manifest.venvy(REPO)
    assert set(prawdziwe) == set(natywne.wczytaj()["venvy"]) and prawdziwe["docling"]["torch_backend"] == "cpu"
    for nazwa, w in prawdziwe.items():                     # lock w repo = ten, którego sumę ma natywne.lock.json
        assert _sha((REPO / w["lock"]).read_bytes()) == w["sha256"] and w["paczek"] > 0, nazwa


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


def test_modele_w_manifescie_i_instalacja(serwer, tmp_path):
    www, adres = serwer
    (www / "w.onnx").write_bytes(b"wagi")
    rew = "9" * 40
    m = {"zrodlo": "uv", "rewizja": rew, "licencja": "MIT", "rola": "x", "katalog": "glos",
         "pliki": [{"cel": "meski/w.onnx", "url": f"https://huggingface.co/a/b/resolve/{rew}/w.onnx",
                    "sha256": _sha(b"wagi"), "rozmiar": 4}]}
    assert natywne.bledy({"version": 1, "hermes": HERMES_OK, "narzedzia": {}, "modele": {"glos": m}}, {"uv": {}}) \
        == ["natywne.yaml: brak sekcji narzedzia"]
    zle = dict(m, rewizja="v1.0", katalog="../x", pliki=[{"cel": "../poza", "url": "https://huggingface.co/a/b/resolve/main/w",
                                                          "sha256": "x", "rozmiar": 0}])
    b = "\n".join(natywne.bledy({"version": 1, "hermes": HERMES_OK, "narzedzia": {}, "modele": {"glos": zle}}, {"uv": {}}))
    for fragment in ("pełnym commitem", "katalog to jedna nazwa", "ścieżka względna", "z rewizją modelu", "64 znaki",
                     "rozmiar"):
        assert fragment in b
    lokalny = dict(m, pliki=[dict(m["pliki"][0], url=f"{adres}/w.onnx")])
    kat = pobieracz.zainstaluj_model("glos", lokalny, tmp_path / "models", pasek=False)
    assert (kat / "meski" / "w.onnx").read_bytes() == b"wagi"
    with pytest.raises(pobieracz.BladPobierania, match="poza katalog"):
        pobieracz.zainstaluj_model("glos", dict(lokalny, pliki=[dict(lokalny["pliki"][0], cel="../poza.onnx")]),
                                   tmp_path / "models", pasek=False)
