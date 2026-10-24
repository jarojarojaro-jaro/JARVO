"""Polecenie jarvo, instalator i skrypty jednego polecenia (docs/NATYWNIE.md: N01–N17, c3, c4, L01, L02, etap E3).

Bootstrapy: adresy i sumy uv i Pythona 3.13 w jarvo/bootstrap/install.ps1 i install.sh są te same co
w vendor/natywne.lock.json; install.ps1 ma samo ASCII bez BOM i parsuje się w PowerShellu; install.sh przechodzi
`bash -n` (na Windows Git Bash z conftest.bash()); suchy przebieg wybiera pliki platformy, Mac z Intelem dostaje
odmowę, JARVO_TOKEN nie pojawia się na ekranie, a pobranie, suma i rozpakowanie działają na plikach z serwera
na 127.0.0.1 (porty 19100–19199). CLI i instalator biegną na atrapach (instalator.Otoczenie): nie dotykają PATH,
rejestru, autostartu ani procesów właściciela, a drugi przebieg instalatora niczego nie zmienia.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

import pytest

import atrapy
from conftest import REPO, WINDOWS, uruchom_bash

sys.path.insert(0, str(REPO))
from jarvo import cli, instalator, pobieracz, sciezki, srodowisko  # noqa: E402

PS1 = REPO / "jarvo" / "bootstrap" / "install.ps1"
SH = REPO / "jarvo" / "bootstrap" / "install.sh"
LOCK = json.loads((REPO / "vendor" / "natywne.lock.json").read_text(encoding="utf-8"))
PIN = LOCK["hermes"]["commit"]
SHA_JARVA = "fb7e3ffa0e77b125f7f24457f8316026bbb3a07b"
PLATFORMY_PS1 = ("windows-x64", "windows-arm64")
PLATFORMY_SH = ("macos-arm64", "linux-x64", "linux-arm64")


# ---------------------------------------------------------------- pomocnicze

class _Cichy(SimpleHTTPRequestHandler):
    def log_message(self, *_a):
        pass


class _Serwer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"       # na Windows SO_REUSEADDR pozwala zająć cudzy port
    daemon_threads = True


@pytest.fixture
def serwer(tmp_path):
    """Serwer plików na 127.0.0.1, port z zakresu prób 19100–19199."""
    katalog = tmp_path / "www"
    katalog.mkdir()
    for port in range(19100, 19200):
        try:
            httpd = _Serwer(("127.0.0.1", port), partial(_Cichy, directory=str(katalog)))
            break
        except OSError:
            continue
    else:
        pytest.skip("brak wolnego portu 19100–19199")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield katalog, f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


def wolny_port() -> int:
    for port in range(19100, 19200):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    pytest.skip("brak wolnego portu 19100–19199")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _tar_gz(pliki: dict[str, bytes]) -> bytes:
    bufor = io.BytesIO()
    with tarfile.open(fileobj=bufor, mode="w:gz") as tf:
        for nazwa, dane in pliki.items():
            info = tarfile.TarInfo(nazwa)
            info.size = len(dane)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(dane))
    return bufor.getvalue()


def _msys(p: Path) -> str:
    """Ścieżka dla Git Bash: C:\\x\\y → /c/x/y (GNU tar bierze „C:” za nazwę zdalnego hosta)."""
    p = Path(p)
    if not WINDOWS:
        return str(p)
    return "/" + p.drive[0].lower() + p.as_posix()[2:]


def _powershell() -> str | None:
    return shutil.which("powershell") if WINDOWS else shutil.which("pwsh")


def _ps(polecenie: str, env: dict | None = None) -> subprocess.CompletedProcess:
    ps = _powershell()
    if ps is None:
        pytest.skip("brak PowerShella")
    return subprocess.run([ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-Command", "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + polecenie],
                          env={**os.environ, **(env or {})}, capture_output=True, encoding="utf-8", errors="replace",
                          timeout=180)


def _ps_na_sucho(tmp_path: Path, **env) -> subprocess.CompletedProcess:
    ps = _powershell()
    if ps is None:
        pytest.skip("brak PowerShella")
    czyste = {k: v for k, v in os.environ.items() if not k.startswith("JARVO_")}
    czyste.update({"JARVO_DRY_RUN": "1", "JARVO_ROOT": str(tmp_path / "root"), **env})
    return subprocess.run([ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-File", str(PS1)], env=czyste, capture_output=True, encoding="utf-8", errors="replace",
                          timeout=120)


def _sh(skrypt: str, **env) -> subprocess.CompletedProcess:
    # bez JARVO_* z otoczenia; bez MSYS_NO_PATHCONV, bo curl z Git Bash dostaje wtedy /c/... zamiast C:/...
    czyste = {k: v for k, v in os.environ.items()
              if not k.startswith("JARVO_") and k not in ("MSYS_NO_PATHCONV", "MSYS2_ARG_CONV_EXCL")}
    return uruchom_bash("-c", skrypt, env={**czyste, **env}, timeout=120)


ATRAPA_UNAME = ('uname() { case "${1:-}" in -m) echo "$FAKE_M" ;; *) echo "$FAKE_S" ;; esac; }\n'
                'sysctl() { echo "${FAKE_ARM64:-0}"; }\n')


def _sh_na_sucho(tmp_path: Path, system: str, maszyna: str, **env) -> subprocess.CompletedProcess:
    dom = tmp_path / "dom"
    dom.mkdir(exist_ok=True)
    return _sh(ATRAPA_UNAME + f'source "{_msys(SH)}"\nmain\n', FAKE_S=system, FAKE_M=maszyna, JARVO_DRY_RUN="1",
               JARVO_ROOT=_msys(tmp_path / "root"), HOME=_msys(dom), **env)


def _wpisy_ps1() -> dict[tuple[str, str], dict]:
    tekst = PS1.read_text(encoding="utf-8")
    wynik = {}
    for m in re.finditer(r"@\{ platforma = '([^']+)'; nazwa = '([^']+)'; katalog = '([^']+)'; format = '([^']+)'; "
                         r"poziom = (\d+); rozmiar = (\d+)\s+url = '([^']+)'\s+sha256 = '([0-9a-f]{64})' \}", tekst):
        wynik[(m[1], m[2])] = {"katalog": m[3], "format": m[4], "usun_poziom": int(m[5]), "rozmiar": int(m[6]),
                               "url": m[7], "sha256": m[8]}
    return wynik


def _wpisy_sh() -> dict[tuple[str, str], dict]:
    tekst = SH.read_text(encoding="utf-8")
    wynik = {}
    wzor = r"([a-z0-9-]+):([a-z0-9]+)\) K=([^;]+); P=(\d+); F=([^\s]+)\s+U='([^']+)'\s+S=([0-9a-f]{64}) ;;"
    for m in re.finditer(wzor, tekst):
        wynik[(m[1], m[2])] = {"katalog": m[3], "usun_poziom": int(m[4]), "format": m[5], "url": m[6],
                               "sha256": m[7]}
    return wynik


# ---------------------------------------------------------------- bootstrap: zgodność z manifestem i składnia

@pytest.mark.parametrize("skrypt,platformy,wpisy", [(PS1, PLATFORMY_PS1, _wpisy_ps1), (SH, PLATFORMY_SH, _wpisy_sh)],
                         ids=["install.ps1", "install.sh"])
def test_bootstrap_sumy_i_adresy_jak_manifest(skrypt, platformy, wpisy):
    znalezione = wpisy()
    oczekiwane = set()
    for platforma in platformy:
        for nazwa in ("uv", "python313"):
            oczekiwane.add((platforma, nazwa))
            plik = LOCK["narzedzia"][nazwa]["pliki"][platforma]
            w = znalezione.get((platforma, nazwa))
            assert w, f"{skrypt.name}: brak wpisu {platforma}/{nazwa}"
            assert w["url"] == plik["url"] and w["sha256"] == plik["sha256"], f"{skrypt.name}: {platforma}/{nazwa}"
            assert w["format"] == plik["format"] and w["usun_poziom"] == plik.get("usun_poziom", 0)
            assert w["katalog"] == pobieracz.katalog_wersji(LOCK["narzedzia"][nazwa]["wersja"])
            if "rozmiar" in w:
                assert w["rozmiar"] == plik["rozmiar"]
    assert set(znalezione) == oczekiwane, f"{skrypt.name}: wpisy spoza manifestu {set(znalezione) - oczekiwane}"
    # każdy adres i suma ze skryptu pochodzą z manifestu (nic dopisanego obok tabeli)
    tekst = skrypt.read_text(encoding="utf-8")
    sumy = set(re.findall(r"\b[0-9a-f]{64}\b", tekst))
    assert sumy == {LOCK["narzedzia"][n]["pliki"][p]["sha256"] for p, n in oczekiwane}


def test_bootstrap_ps1_tylko_ascii_bez_bom():
    dane = PS1.read_bytes()
    assert not dane.startswith(b"\xef\xbb\xbf"), "bez BOM: irm | iex w PowerShell 5.1 zostawia go w tekście"
    zle = [i for i, b in enumerate(dane) if b > 127]
    assert not zle, f"znak spoza ASCII w bajcie {zle[0]}: PowerShell 5.1 czyta plik bez BOM jako ANSI"
    tekst = dane.decode("ascii")
    assert "$ErrorActionPreference = 'Stop'" in tekst and "Tls12" in tekst
    assert "Get-FileHash" in tekst and "tar.exe" in tekst and "Expand-Archive" in tekst
    # wartość klucza tylko w nagłówku; nigdy w napisie dla człowieka ani w argv programu (nazwa zmiennej może być)
    for linia in tekst.splitlines():
        if "$env:JARVO_TOKEN" in linia and not linia.lstrip().startswith("#"):
            assert re.search(r"if \(\$env:JARVO_TOKEN\)|'Bearer ' \+ \$env:JARVO_TOKEN", linia), linia


def test_bootstrap_ps1_parsuje_sie():
    r = _ps("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{PS1}', [ref]$null, [ref]$e); $e | ForEach-Object {{ $_.ToString() }}; exit $e.Count")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.wymaga_bash
def test_bootstrap_sh_skladnia_bash():
    r = uruchom_bash("-n", _msys(SH))
    assert r.returncode == 0, r.stderr
    assert SH.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")
    kod = "\n".join(w for w in SH.read_text(encoding="utf-8").splitlines() if not w.lstrip().startswith("#"))
    for zakazane in ("declare -A", "mapfile", ",,}", "^^}", "readarray", "local -n"):     # bash 3.2 na macOS
        assert zakazane not in kod, zakazane


# ---------------------------------------------------------------- bootstrap Windows: suchy przebieg i pobieranie

@pytest.mark.windows_only
def test_bootstrap_ps1_na_sucho_x64_arm64_i_odmowa_x86(tmp_path):
    r = _ps_na_sucho(tmp_path, JARVO_REF=SHA_JARVA, JARVO_FAKE_ARCH="AMD64")
    assert r.returncode == 0, r.stdout + r.stderr
    x64 = {n: LOCK["narzedzia"][n]["pliki"]["windows-x64"] for n in ("uv", "python313")}
    assert x64["uv"]["url"] in r.stdout and x64["python313"]["url"] in r.stdout
    assert "program\\narzedzia\\uv\\0.12.13" in r.stdout and "program\\narzedzia\\python313\\3.13.17" in r.stdout
    assert f"codeload.github.com/jarojarojaro-jaro/JARVO/tar.gz/{SHA_JARVA}" in r.stdout
    assert re.search(r"python\.exe -I -X utf8 \S+app\\fb7e3ffa0e77\\jarvo\\start\.py instaluj", r.stdout)
    assert not (tmp_path / "root").exists(), "na sucho nic nie powstaje"
    r = _ps_na_sucho(tmp_path, JARVO_REF=SHA_JARVA, JARVO_FAKE_ARCH="ARM64", JARVO_NO_AUTOSTART="1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert LOCK["narzedzia"]["uv"]["pliki"]["windows-arm64"]["url"] in r.stdout        # uv natywny ARM64
    assert "x86_64-pc-windows-msvc-install_only" in r.stdout                         # Python x64 (I27)
    assert "instaluj --bez-autostartu" in r.stdout
    r = _ps_na_sucho(tmp_path, JARVO_FAKE_ARCH="x86")
    assert r.returncode != 0 and "64-bitowego Windowsa" in r.stdout + r.stderr


@pytest.mark.windows_only
def test_bootstrap_ps1_przez_iex_nie_zostawia_sladow_w_sesji(tmp_path):
    """`irm … | iex` wykonuje tekst w sesji użytkownika: funkcje i ErrorActionPreference zostają w bloku `& { }`."""
    r = _ps(f"$env:JARVO_DRY_RUN = '1'; $env:JARVO_ROOT = '{tmp_path / 'root'}'; $env:JARVO_FAKE_ARCH = 'AMD64'; "
            f"$env:JARVO_REF = '{SHA_JARVA}'; Get-Content -Raw -LiteralPath '{PS1}' | Invoke-Expression; "
            "'EAP=' + $ErrorActionPreference; 'FUNKCJA=' + [bool](Get-Command JarvoKrok -ErrorAction SilentlyContinue)")
    assert r.returncode == 0, r.stdout + r.stderr
    assert LOCK["narzedzia"]["uv"]["pliki"]["windows-x64"]["url"] in r.stdout
    assert "EAP=Continue" in r.stdout and "FUNKCJA=False" in r.stdout


@pytest.mark.linux_only
def test_bootstrap_sh_pod_dash_odmawia_czytelnie():
    dash = shutil.which("dash")
    if dash is None:
        pytest.skip("brak dash")
    r = subprocess.run([dash, str(SH)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 1 and "przez bash" in r.stderr


@pytest.mark.windows_only
def test_bootstrap_ps1_klucz_nie_wycieka_i_stara_instalacja(tmp_path):
    r = _ps_na_sucho(tmp_path, JARVO_FAKE_ARCH="AMD64", JARVO_TOKEN="tajny-klucz-0123456789")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "tajny-klucz" not in r.stdout + r.stderr and "<ukryty>" in r.stdout
    assert "api.github.com/repos/jarojarojaro-jaro/JARVO/commits/main" in r.stdout
    assert "api.github.com/repos/jarojarojaro-jaro/JARVO/tarball/" in r.stdout      # prywatna kopia: przez API
    (tmp_path / "root" / "wsl").mkdir(parents=True)
    r = _ps_na_sucho(tmp_path, JARVO_FAKE_ARCH="AMD64")
    assert r.returncode != 0 and "stara instalacja Jarvo" in r.stdout + r.stderr
    assert not (tmp_path / "root" / "program").exists()


_PS_FUNKCJE = r"""
$ErrorActionPreference = 'Stop'
$e = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{skrypt}', [ref]$null, [ref]$e)
$typ = [System.Management.Automation.Language.FunctionDefinitionAst]
foreach ($f in $ast.FindAll({{ param($n) $n -is $typ }}, $true)) {{
  . ([scriptblock]::Create($f.Extent.Text))
}}
$JarvoNaSucho = $false
$JarvoRepo = 'jarojarojaro-jaro/JARVO'
"""


@pytest.mark.windows_only
def test_bootstrap_ps1_pobiera_sprawdza_sume_i_rozpakowuje(tmp_path, serwer):
    """Prawdziwe funkcje install.ps1 (wyjęte z AST, bez uruchamiania całości) na plikach z serwera 127.0.0.1."""
    www, adres = serwer
    tgz = _tar_gz({"python/python.exe": b"atrapa", "python/Lib/os.py": b"#"})
    (www / "py.tar.gz").write_bytes(tgz)
    zbufor = io.BytesIO()
    with zipfile.ZipFile(zbufor, "w") as zf:
        zf.writestr("uv.exe", "atrapa-uv")
    (www / "uv.zip").write_bytes(zbufor.getvalue())
    program, pobrane = tmp_path / "program", tmp_path / "cache" / "pobrane"
    wstep = _PS_FUNKCJE.format(skrypt=PS1)
    polecenie = wstep + (
        f"$py = @{{ nazwa = 'python313'; katalog = '3.13.17'; format = 'tar.gz'; poziom = 1; rozmiar = {len(tgz)}; "
        f"url = '{adres}/py.tar.gz'; sha256 = '{_sha(tgz)}' }}\n"
        f"$uv = @{{ nazwa = 'uv'; katalog = '0.12.13'; format = 'zip'; poziom = 0; rozmiar = 9; "
        f"url = '{adres}/uv.zip'; sha256 = '{_sha(zbufor.getvalue())}' }}\n"
        f"foreach ($w in @($py, $uv)) {{ JarvoNarzedzie $w (JarvoKatalogNarzedzia '{program}' $w) '{pobrane}' }}\n"
        f"JarvoNarzedzie $py (JarvoKatalogNarzedzia '{program}' $py) '{pobrane}'\n")
    r = _ps(polecenie)
    assert r.returncode == 0, r.stdout + r.stderr
    kat = program / "narzedzia" / "python313" / "3.13.17"
    assert (kat / "python.exe").read_bytes() == b"atrapa" and (kat / "Lib" / "os.py").is_file()
    assert (kat / ".jarvo-suma").read_text(encoding="utf-8").strip() == _sha(tgz)
    assert (program / "narzedzia" / "uv" / "0.12.13" / "uv.exe").read_text(encoding="utf-8") == "atrapa-uv"
    assert "python313 3.13.17: juz jest" in r.stdout                  # drugi raz: znacznik z sumą, bez pobierania
    # jarvo/pobieracz.py uznaje instalację z bootstrapu za swoją (ten sam katalog i znacznik): nic nie pobiera
    assert pobieracz.zainstaluj("python313", "3.13.17+20261021", {"url": "https://127.0.0.1.invalid/x",
                                                                   "sha256": _sha(tgz)},
                                program / "narzedzia", pobrane) == kat
    # zła suma: plik usunięty, katalog narzędzia nie powstaje
    zly = wstep + (f"$w = @{{ nazwa = 'zly'; katalog = '1.0'; format = 'tar.gz'; poziom = 1; rozmiar = 1; "
                   f"url = '{adres}/py.tar.gz'; sha256 = '{'0' * 64}' }}\n"
                   f"JarvoNarzedzie $w (JarvoKatalogNarzedzia '{program}' $w) '{pobrane}'\n")
    r = _ps(zly)
    assert r.returncode != 0 and "suma sha256" in r.stdout + r.stderr
    assert not (program / "narzedzia" / "zly").exists() and not list(pobrane.glob("*.czesc"))


# ---------------------------------------------------------------- bootstrap macOS i Linux

@pytest.mark.wymaga_bash
@pytest.mark.parametrize("system,maszyna,arm64,platforma", [
    ("Darwin", "arm64", "1", "macos-arm64"),
    ("Darwin", "x86_64", "1", "macos-arm64"),          # Terminal pod Rosettą na Apple Silicon
    ("Linux", "x86_64", "0", "linux-x64"),
    ("Linux", "aarch64", "0", "linux-arm64"),
])
def test_bootstrap_sh_na_sucho_wybiera_pliki_platformy(tmp_path, system, maszyna, arm64, platforma):
    r = _sh_na_sucho(tmp_path, system, maszyna, FAKE_ARM64=arm64, JARVO_REF=SHA_JARVA, JARVO_WEB_LOKALNIE="1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"platforma {platforma}" in r.stdout
    for nazwa in ("uv", "python313"):
        plik = LOCK["narzedzia"][nazwa]["pliki"][platforma]
        assert plik["url"] in r.stdout and plik["sha256"] in r.stdout
    assert "/program/narzedzia/python313/3.13.17" in r.stdout
    assert f"codeload.github.com/jarojarojaro-jaro/JARVO/tar.gz/{SHA_JARVA}" in r.stdout
    assert re.search(r"python313/3\.13\.17/bin/python3 -I -X utf8 \S+/app/fb7e3ffa0e77/jarvo/start\.py instaluj "
                     r"--web-lokalnie", r.stdout)
    assert not (tmp_path / "root").exists(), "na sucho nic nie powstaje"


@pytest.mark.wymaga_bash
def test_bootstrap_sh_odmawia_maca_z_intelem(tmp_path):
    r = _sh_na_sucho(tmp_path, "Darwin", "x86_64", FAKE_ARM64="0")
    assert r.returncode == 1 and "Intel" in r.stderr and "I06" in r.stderr
    assert "pobierz" not in r.stdout


@pytest.mark.wymaga_bash
def test_bootstrap_sh_klucz_nie_wycieka_i_stare_polecenie(tmp_path):
    r = _sh_na_sucho(tmp_path, "Linux", "x86_64", JARVO_TOKEN="tajny-klucz-0123456789")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "tajny-klucz" not in r.stdout + r.stderr and "<ukryty>" in r.stdout
    assert "api.github.com/repos/jarojarojaro-jaro/JARVO/tarball/" in r.stdout
    stare = tmp_path / "dom" / ".local" / "bin" / "jarvo"
    stare.parent.mkdir(parents=True)
    stare.write_text("#!/bin/sh\nexec docker exec -it jarvo-hermes hermes \"$@\"\n", encoding="utf-8")
    r = _sh_na_sucho(tmp_path, "Linux", "x86_64")
    assert r.returncode == 1 and "należy do innej instalacji" in r.stderr
    stare.write_text(instalator.tresc_jarvo_sh(Path("/x/python3"), Path("/x/start.py")), encoding="utf-8")
    assert _sh_na_sucho(tmp_path, "Linux", "x86_64").returncode == 0      # nasze polecenie: aktualizacja


@pytest.mark.wymaga_bash
def test_bootstrap_sh_pobiera_sprawdza_sume_i_rozpakowuje(tmp_path, serwer):
    www, adres = serwer
    tgz = _tar_gz({"uv-x/uv": b"atrapa-uv"})
    (www / "uv.tar.gz").write_bytes(tgz)
    program, pobrane = tmp_path / "program", tmp_path / "pobrane"

    def skrypt(sha: str) -> str:
        return (f'source "{_msys(SH)}"\n'
                f"plik() {{ K=1.0; P=1; F=tar.gz; U='{adres}/uv.tar.gz'; S={sha}; }}\n"
                f'PLATFORMA=linux-x64; PROGRAM="{_msys(program)}"; POBRANE="{_msys(pobrane)}"; DRY=0\n'
                "narzedzie uv\nnarzedzie uv\n")
    r = _sh(skrypt(_sha(tgz)))
    assert r.returncode == 0, r.stdout + r.stderr
    kat = program / "narzedzia" / "uv" / "1.0"
    assert (kat / "uv").read_bytes() == b"atrapa-uv"
    assert (kat / ".jarvo-suma").read_text(encoding="utf-8").strip() == _sha(tgz)
    assert "uv 1.0: już jest" in r.stdout
    shutil.rmtree(kat)
    r = _sh(skrypt("0" * 64))
    assert r.returncode == 1 and "Suma sha256" in r.stderr
    assert not kat.exists() and not list(pobrane.glob("*.czesc"))


def _archiwum_kodu(sha: str, *, start: bool = True) -> bytes:
    """Jak archiwum codeload: katalog JARVO-<sha>/ z kodem."""
    pliki = {f"JARVO-{sha}/README.md": b"readme"}
    if start:
        pliki[f"JARVO-{sha}/jarvo/start.py"] = b"# start"
    return _tar_gz(pliki)


@pytest.mark.windows_only
def test_bootstrap_ps1_kod_jarva_z_archiwum(tmp_path, serwer):
    www, adres = serwer
    (www / "app.tar.gz").write_bytes(_archiwum_kodu(SHA_JARVA))
    (www / "zly.tar.gz").write_bytes(_archiwum_kodu(SHA_JARVA, start=False))
    cel, pobrane = tmp_path / "program" / "app" / SHA_JARVA[:12], tmp_path / "pobrane"
    (cel / "resztka").mkdir(parents=True)                        # przerwana próba: katalog bez jarvo\start.py
    wstep = _PS_FUNKCJE.format(skrypt=PS1)
    r = _ps(wstep + f"function JarvoAdresKodu([string]$Sha) {{ '{adres}/app.tar.gz' }}\n"
                    f"JarvoKod '{SHA_JARVA}' '{cel}' '{pobrane}'\nJarvoKod '{SHA_JARVA}' '{cel}' '{pobrane}'\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (cel / "jarvo" / "start.py").read_bytes() == b"# start" and (cel / "README.md").is_file()
    assert (cel / ".jarvo-wersja").read_text(encoding="utf-8").strip() == SHA_JARVA
    assert not (cel / "resztka").exists(), "niepełny katalog zastąpiony, nie zagnieżdżony"
    assert "juz jest" in r.stdout and not list(pobrane.glob("*.tar.gz"))
    zly = tmp_path / "program" / "app" / "zly"
    r = _ps(wstep + f"function JarvoAdresKodu([string]$Sha) {{ '{adres}/zly.tar.gz' }}\n"
                    f"JarvoKod '{SHA_JARVA}' '{zly}' '{pobrane}'\n")
    assert r.returncode != 0 and "nie ma jarvo" in r.stdout + r.stderr and not zly.exists()


@pytest.mark.wymaga_bash
def test_bootstrap_sh_kod_jarva_z_archiwum(tmp_path, serwer):
    www, adres = serwer
    (www / "app.tar.gz").write_bytes(_archiwum_kodu(SHA_JARVA))
    program, pobrane = tmp_path / "program", tmp_path / "pobrane"
    app = program / "app" / SHA_JARVA[:12]
    (app / "resztka").mkdir(parents=True)
    r = _sh(f'source "{_msys(SH)}"\n'
            f"adres_kodu() {{ printf '%s\\n' '{adres}/app.tar.gz'; }}\n"
            f'SHA={SHA_JARVA}; PROGRAM="{_msys(program)}"; POBRANE="{_msys(pobrane)}"; DRY=0\n'
            "kod\nkod\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (app / "jarvo" / "start.py").read_bytes() == b"# start"
    assert (app / ".jarvo-wersja").read_text(encoding="utf-8").strip() == SHA_JARVA
    assert not (app / "resztka").exists() and "już jest" in r.stdout


# ---------------------------------------------------------------- launcher i parser

def test_start_py_w_trybie_izolowanym_ignoruje_cudzy_pythonpath(tmp_path):
    obcy = tmp_path / "obcy" / "jarvo"
    obcy.mkdir(parents=True)
    (obcy / "__init__.py").write_text("raise SystemExit('cudzy pakiet jarvo')\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(obcy.parent), "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(REPO / "jarvo" / "start.py"), "--help"],
                       cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert "użycie: jarvo" in r.stdout and "pokaż tę pomoc" in r.stdout and "cudzy" not in r.stdout + r.stderr
    r = subprocess.run([sys.executable, "-m", "jarvo", "status", "--help"], cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"}, timeout=60)
    assert r.returncode == 0 and "--json" in r.stdout


def test_pomoc_po_polsku_i_argparse_bez_trwalej_zmiany(capsys):
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    for slowo in ("użycie: jarvo", "opcje:", "--korzen", "instaluj", "serwis", "up", "down", "status", "panel",
                  "chat", "logs", "autostart", "doctor", "update", "uninstall", "migruj"):
        assert slowo in out
    assert cli.main(["autostart", "wlacz"]) == 2
    assert "błąd:" in capsys.readouterr().err
    assert cli.main(["status", "--nieznana"]) == 2
    assert argparse._("usage: ") == "usage: "       # podmiana tylko na czas parsowania


def _ot(tmp_path, **kw) -> instalator.Otoczenie:
    env = {k: v for k, v in os.environ.items() if not k.startswith("JARVO_")}
    env.update({"JARVO_ROOT": str(tmp_path / "j"), "JARVO_PANEL_PORT": str(kw.pop("port", 19199))})
    env.update(kw.pop("env", {}))
    moduly = kw.pop("moduly", {})

    def modul(nazwa):
        if nazwa not in moduly:
            raise ImportError(f"No module named 'jarvo.{nazwa}'")
        return moduly[nazwa]
    kw.setdefault("czekaj", lambda s: None)
    return instalator.Otoczenie(modul=modul, env=env, **kw)


def test_w_budowie_kod_2(tmp_path, capsys):
    for polecenie, etap in (("update", "E4"), ("uninstall", "E13"), ("migruj", "E12")):
        assert cli.main([polecenie, "--all"], otoczenie=_ot(tmp_path)) == 2
        err = capsys.readouterr().err
        assert "w budowie" in err and f"etap {etap}" in err


def test_korzen_z_argv_jak_jarvo_root(tmp_path, capsys):
    """Launcher i autostart instalacji spod JARVO_ROOT podają korzeń w argv (Harmonogram nie przekazuje zmiennych)."""
    ot = _ot(tmp_path, port=wolny_port())
    ot.env.pop("JARVO_ROOT")
    assert cli.main(["--korzen", str(tmp_path / "inny"), "status", "--json"], otoczenie=ot) == 1
    assert json.loads(capsys.readouterr().out)["root"] == str(tmp_path / "inny")
    assert cli.main([f"--korzen={tmp_path / 'trzeci'}", "status", "--json"], otoczenie=ot) == 1
    assert json.loads(capsys.readouterr().out)["root"] == str(tmp_path / "trzeci")
    assert "JARVO_ROOT" not in os.environ or os.environ["JARVO_ROOT"] != str(tmp_path / "trzeci")   # tylko atrapa


def test_status_i_doctor_na_pustym_katalogu_niczego_nie_tworza(tmp_path, capsys):
    ot = _ot(tmp_path, port=wolny_port())
    assert cli.main(["status"], otoczenie=ot) == 1
    out = capsys.readouterr().out
    assert "instalacja: brak" in out and "serwis:     nie działa" in out
    assert cli.main(["status", "--json"], otoczenie=ot) == 1
    raport = json.loads(capsys.readouterr().out)
    assert raport["zainstalowane"] is False and raport["serwis"]["dziala"] is False
    assert cli.main(["doctor", "--json"], otoczenie=ot) == 1
    d = json.loads(capsys.readouterr().out)
    po_nazwie = {w["nazwa"]: w for w in d["wyniki"]}
    assert po_nazwie["korzeń"]["stan"] == "blad" and "jednym poleceniem" in po_nazwie["korzeń"]["rada"]
    assert po_nazwie["uv"]["stan"] == "blad" and po_nazwie["Hermes"]["stan"] == "blad"
    assert all(w["rada"] for w in d["wyniki"] if w["stan"] != "ok"), "każdy błąd i uwaga ma radę"
    assert d["bledy"] >= 3
    assert cli.main(["doctor"], otoczenie=ot) == 1
    assert "rada:" in capsys.readouterr().out
    for polecenie in (["panel"], ["up"], ["chat"], ["autostart", "on"]):
        assert cli.main(polecenie, otoczenie=ot) == 1
        assert "nie jest zainstalowane" in capsys.readouterr().err
    assert cli.main(["down"], otoczenie=ot) == 0
    assert not (tmp_path / "j").exists()


class AtrapaNadzorcy:
    def __init__(self, dziala=False):
        self.dziala, self.zatrzymania, self.argv = dziala, 0, None

    def polacz(self, u):
        if not self.dziala:
            raise ConnectionRefusedError("Nadzorca Jarva nie działa (atrapa)")
        return self

    def status(self):
        return {"nadzorca": {"pid": 100, "stan": "dziala"},
                "uslugi": {"brama": {"stan": "dziala", "pid": 101, "gotowa": True, "restarty": 0},
                           "panel": {"stan": "dziala", "pid": 102, "gotowa": True, "restarty": 2}}}

    def stop(self):
        self.dziala = False
        self.zatrzymania += 1
        return {"ok": True}

    def restart(self, nazwa):
        return {"ok": True}

    def stan_z_pliku(self, u):
        return {"dziala": False, "uslugi": {"brama": {"stan": "postój", "ostatni_kod": 78,
                                                       "powod": "brak klucza modelu"}}}

    def main(self, argv):
        self.argv = list(argv)
        return 0


class AtrapaAutostartu:
    """Jak jarvo/autostart.py: wlacz(start=True) od razu uruchamia nadzorcę mechanizmem systemu."""

    def __init__(self, nadzorca: AtrapaNadzorcy | None = None):
        self.nadzorca, self.wlaczony, self.argv, self.wywolania = nadzorca, False, None, []

    def wlacz(self, u, argv, wykonaj=None, *, start=True, log=print, **_kw):
        zmieniony = not self.wlaczony or self.argv != list(argv)
        self.wlaczony, self.argv = True, list(argv)
        self.wywolania.append(("wlacz", start))
        if start and self.nadzorca is not None:
            self.nadzorca.dziala = True
        return {"zmieniony": zmieniony, "uruchomiony": start, "uwagi": []}

    def wylacz(self, u, wykonaj=None, **_kw):
        self.wlaczony = False
        self.wywolania.append(("wylacz",))
        return {"usuniety": True, "uwagi": []}

    def stan(self, u, wykonaj=None, **_kw):
        return {"wlaczony": self.wlaczony, "nasz": True, "mechanizm": "harmonogram" if self.wlaczony else None,
                "opis": "włączony (zadanie Harmonogramu Jarvo)" if self.wlaczony else "wyłączony"}

    def nazwa_zadania(self, u):
        return "Jarvo"


class RejestrAtrapa:
    """HKCU w pamięci, interfejs jarvo/zmiany_hosta.Rejestr (rejestru właściciela test nie dotyka)."""

    def __init__(self, path: str | None = r"C:\Narzedzia;%USERPROFILE%\bin;", typ: int = 2):
        self.wartosci = {} if path is None else {("Environment", "Path"): (path, typ)}
        self.zapisy, self.ogloszenia = [], 0

    def czytaj(self, klucz, nazwa):
        return self.wartosci.get((klucz, nazwa))

    def zapisz(self, klucz, nazwa, wartosc, typ):
        self.wartosci[(klucz, nazwa)] = (wartosc, typ)
        self.zapisy.append((klucz, nazwa, wartosc))

    def usun(self, klucz, nazwa):
        self.wartosci.pop((klucz, nazwa), None)

    def oglos(self):
        self.ogloszenia += 1


class AtrapaZmian:
    """Dziennik zmian hosta w pamięci z tymi samymi pomocnikami co jarvo/zmiany_hosta.py (plik, blok-rc,
    path-uzytkownika); pliki i bloki zapisuje naprawdę (w katalogu testu)."""

    def __init__(self):
        self.lista = []

    def dopisz(self, u, rodzaj, **szczegoly):
        wpis = {"rodzaj": rodzaj, "szczegoly": {k: str(v) if isinstance(v, Path) else v for k, v in szczegoly.items()}}
        if wpis not in self.lista:
            self.lista.append(wpis)
        return wpis

    def wpisy(self, u):
        return [dict(w) for w in self.lista]

    def zapisz_plik(self, u, sciezka, tresc, tryb=0o644):
        dane = tresc.encode("utf-8") if isinstance(tresc, str) else tresc
        self.dopisz(u, "plik", sciezka=str(sciezka), sha256=hashlib.sha256(dane).hexdigest())
        if Path(sciezka).is_file() and Path(sciezka).read_bytes() == dane:
            return False
        Path(sciezka).parent.mkdir(parents=True, exist_ok=True)
        Path(sciezka).write_bytes(dane)
        if tryb is not None and not WINDOWS:
            os.chmod(sciezka, tryb)
        return True

    def dodaj_blok_rc(self, u, sciezka, tresc, znacznik="jarvo"):
        blok = f"# >>> {znacznik} >>>\n{tresc}\n# <<< {znacznik} <<<\n"
        self.dopisz(u, "blok-rc", sciezka=str(sciezka), znacznik=znacznik,
                    sha256=hashlib.sha256(blok.encode()).hexdigest())
        p = Path(sciezka)
        stary = p.read_text(encoding="utf-8") if p.exists() else ""
        if blok in stary:
            return False
        p.write_text(stary + ("\n" if stary and not stary.endswith("\n") else "") + blok, encoding="utf-8")
        return True

    def dodaj_do_path(self, u, katalog, *, rejestr=None):
        self.dopisz(u, "path-uzytkownika", wartosc=str(katalog))
        tekst, typ = rejestr.czytaj("Environment", "Path") or ("", 2)
        if any(c.strip().rstrip("\\").casefold() == str(katalog).rstrip("\\").casefold() for c in tekst.split(";")):
            return False
        nowa = f"{tekst.rstrip(';')};{katalog}" if tekst.strip(";") else str(katalog)
        rejestr.zapisz("Environment", "Path", nowa, typ)
        rejestr.oglos()
        return True


class AtrapaHermesa:
    def __init__(self):
        self.wywolania = []

    def zainstaluj(self, u, pin, *, git, uv, python, log=print):
        self.wywolania.append(("zainstaluj", pin["commit"], Path(git), Path(uv), Path(python)))
        checkout = u.program / "hermes" / pin["commit"][:12]
        (checkout / ".git").mkdir(parents=True, exist_ok=True)
        (checkout / ".git" / "HEAD").write_text(pin["commit"] + "\n", encoding="utf-8")
        py = srodowisko.hermes_python(checkout)
        py.parent.mkdir(parents=True, exist_ok=True)
        py.write_bytes(b"")
        log("checkout gotowy")
        return checkout

    def web_dist(self, u, checkout, *, npm=None, log=print):
        self.wywolania.append(("web_dist", npm))
        dist = checkout / "hermes_cli" / "web_dist"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")
        return dist

    def konfiguracja_bezpieczna(self, u, checkout, env, log=print):
        self.wywolania.append(("konfiguracja", env["HERMES_HOME"], env["HERMES_DISABLE_LAZY_INSTALLS"]))

    def argv_hermesa(self, checkout, *argumenty):
        return [str(srodowisko.hermes_python(checkout)), "-m", "hermes_cli.main", *argumenty]


def _zainstalowane(tmp_path, *, profile=("jarvo",)) -> sciezki.Uklad:
    """Układ jak po instalacji, bez instalatora: current.json (app = to repo), checkout Hermesa na pinie, uv."""
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    checkout = u.program / "hermes" / PIN[:12]
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".git" / "HEAD").write_text(PIN + "\n", encoding="utf-8")
    srodowisko.hermes_python(checkout).parent.mkdir(parents=True)
    srodowisko.hermes_python(checkout).write_bytes(b"")
    uv_kat = u.program / "narzedzia" / "uv" / "0.12.13"
    atrapy.program(uv_kat, "uv", "print('uv 0.12.13 (atrapa 2026-10-01)')\n")
    (u.stan / "narzedzia.json").write_text(json.dumps({"uv": {"wersja": "0.12.13", "katalog": str(uv_kat),
                                                               "bin": [str(uv_kat)], "env": {}}}), encoding="utf-8")
    (u.program / "current.json").write_text(json.dumps({"app": str(REPO), "hermes": str(checkout),
                                                        "wersja": "abc123def456"}), encoding="utf-8")
    for p in profile:
        (u.dane / "profiles" / p).mkdir(parents=True)
    return u


def test_status_z_nadzorcy_albo_z_pliku(tmp_path, capsys):
    _zainstalowane(tmp_path)
    nadzorca, auto = AtrapaNadzorcy(dziala=True), AtrapaAutostartu()
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca, "autostart": auto}, port=wolny_port())
    assert cli.main(["status"], otoczenie=ot) == 0
    out = capsys.readouterr().out
    assert "serwis:     działa" in out and "brama: dziala, gotowa, PID 101" in out
    assert "panel: dziala, gotowa, PID 102, restarty 2" in out
    assert "wersja:     abc123def456" in out and "uv 0.12.13" in out and "autostart:  wyłączony" in out
    nadzorca.dziala = False
    assert cli.main(["status"], otoczenie=ot) == 1
    out = capsys.readouterr().out
    assert "nie działa (Nadzorca Jarva nie działa (atrapa)); ostatni stan z pliku:" in out
    assert "brama: postój, kod 78, powód brak klucza modelu" in out


def test_serwis_up_down(tmp_path, capsys):
    _zainstalowane(tmp_path)
    nadzorca = AtrapaNadzorcy()
    assert cli.main(["serwis", "--status", "-v"], otoczenie=_ot(tmp_path, moduly={"nadzorca": nadzorca})) == 0
    assert nadzorca.argv == ["--status", "-v"]
    assert cli.main(["serwis"], otoczenie=_ot(tmp_path)) == 1                 # brak modułu: jasny błąd
    assert "brak modułu nadzorcy" in capsys.readouterr().err
    w_tle = []

    def start(argv, env, log):
        w_tle.append(argv)
        nadzorca.dziala = True
        return 1
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca}, uruchom_w_tle=start, odpowiada=lambda a, c: nadzorca.dziala)
    assert cli.main(["up"], otoczenie=ot) == 0 and len(w_tle) == 1
    assert "Jarvo działa. Panel: http://127.0.0.1:19199/" in capsys.readouterr().out
    assert cli.main(["up"], otoczenie=ot) == 0 and len(w_tle) == 1              # działa: bez drugiego startu
    assert cli.main(["down"], otoczenie=ot) == 0 and nadzorca.zatrzymania == 1
    assert "Serwis zatrzymany" in capsys.readouterr().out
    assert cli.main(["down"], otoczenie=ot) == 0 and nadzorca.zatrzymania == 1  # już nie działa


def test_chat_srodowisko_tryb_i_argumenty_dla_hermesa(tmp_path, capsys):
    u = _zainstalowane(tmp_path)
    wywolania = []
    ot = _ot(tmp_path, moduly={"hermes": AtrapaHermesa()}, env={"HERMES_YOLO_MODE": "1", "HERMES_HOME": "/obcy"},
             na_pierwszym_planie=lambda argv, env: wywolania.append((argv, env)) or 7)
    assert cli.main([], otoczenie=ot) == 7                                       # samo `jarvo` = rozmowa
    argv, env = wywolania[-1]
    assert argv[1:] == ["-m", "hermes_cli.main", "-p", "jarvo", "chat"]
    assert env["JARVO_TRYB_ZGOD"] == "projekt" and env["HERMES_HOME"] == str(u.dane)   # domyślny tryb (I08)
    assert "HERMES_YOLO_MODE" not in env and env["HERMES_DISABLE_LAZY_INSTALLS"] == "1"
    assert cli.main(["--tryb", "pelny", "--resume", "abc"], otoczenie=ot) == 7
    argv, env = wywolania[-1]
    assert argv[-3:] == ["chat", "--resume", "abc"] and env["JARVO_TRYB_ZGOD"] == "pelny"
    assert cli.main(["chat", "--tryb", "pytaj", "--profil", "default", "--", "-q", "hej"], otoczenie=ot) == 7
    argv, env = wywolania[-1]
    assert argv[3:] == ["-p", "default", "chat", "-q", "hej"] and env["JARVO_TRYB_ZGOD"] == "pytaj"
    assert cli.main(["chat", "--profil", "web"], otoczenie=ot) == 1             # profil jeszcze nie zainstalowany
    assert "etap E4" in capsys.readouterr().err
    assert cli.main(["chat", "--profil", "../x"], otoczenie=ot) == 2
    assert cli.main(["chat", "--tryb", "yolo"], otoczenie=ot) == 2
    assert len(wywolania) == 3


def test_panel_startuje_serwis_czeka_i_otwiera_przegladarke(tmp_path, capsys):
    u = _zainstalowane(tmp_path)
    nadzorca, uruchomione, otwarte = AtrapaNadzorcy(), [], []
    port = wolny_port()

    def w_tle(argv, env, log):
        uruchomione.append((argv, env, log))
        nadzorca.dziala = True
        return 4242
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca}, port=port, uruchom_w_tle=w_tle,
             odpowiada=lambda adres, czas: nadzorca.dziala, otworz=otwarte.append)
    assert cli.main(["panel"], otoczenie=ot) == 0
    assert otwarte == [f"http://127.0.0.1:{port}/"]
    argv, env, log = uruchomione[0]
    assert argv[-1] == "serwis" and argv[1:4] == ["-I", "-X", "utf8"] and log == u.logi / "serwis-start.log"
    assert argv[-3:-1] == ["--korzen", str(u.root)]                       # korzeń spod JARVO_ROOT idzie w argv
    assert env["JARVO_ROOT"] == str(u.root) and env["JARVO_PANEL_PORT"] == str(port)
    assert "uruchamiam go w tle" in capsys.readouterr().out
    assert cli.main(["panel", "--bez-przegladarki"], otoczenie=ot) == 0          # działa: bez drugiego startu
    assert len(uruchomione) == 1 and len(otwarte) == 1
    nadzorca.dziala = False                                                      # nie wstaje: limit czasu z radą
    zegar = iter(range(0, 10_000, 5))
    ot2 = _ot(tmp_path, moduly={"nadzorca": nadzorca}, port=port, uruchom_w_tle=lambda *a: 1,
              odpowiada=lambda adres, czas: False, otworz=otwarte.append, zegar=lambda: float(next(zegar)))
    assert cli.main(["panel"], otoczenie=ot2) == 1
    assert "jarvo logs panel" in capsys.readouterr().err
    assert cli.main(["panel"], otoczenie=_ot(tmp_path, port=port)) == 1          # bez nadzorcy: od razu błąd
    assert "brak modułu nadzorcy" in capsys.readouterr().err


def test_logs_ogon_wybor_i_sledzenie(tmp_path, capsys):
    u = _zainstalowane(tmp_path)
    (u.logi / "brama.log").write_text("".join(f"brama {i}\n" for i in range(200)), encoding="utf-8")
    (u.logi / "panel.log").write_text("panel start\nżółć gotowe\n", encoding="utf-8")
    (u.dane / "logs").mkdir()
    (u.dane / "logs" / "gateway.log").write_text("hermes brama\n", encoding="utf-8")
    ot = _ot(tmp_path)
    assert cli.main(["logs"], otoczenie=ot) == 0
    out = capsys.readouterr().out
    assert "==> brama" in out and "brama 199" in out and "brama 150" not in out and "żółć gotowe" in out
    assert "jarvo logs hermes" in out and "hermes brama" not in out
    assert cli.main(["logs", "brama", "-n", "2"], otoczenie=ot) == 0
    assert capsys.readouterr().out.splitlines() == ["brama 198", "brama 199"]
    assert cli.main(["logs", "hermes"], otoczenie=ot) == 0 and "hermes brama" in capsys.readouterr().out
    assert cli.main(["logs", "nieznany"], otoczenie=ot) == 2
    assert "Nie znam logu" in capsys.readouterr().err
    # -f: dopisane wiersze, niepełny wiersz czeka, przycięcie przy rotacji czyta od nowa
    p = u.logi / "panel.log"
    kroki = iter([lambda: p.write_text(p.read_text(encoding="utf-8") + "nowy 1\npół", encoding="utf-8"),
                  lambda: p.write_text("po rotacji\n", encoding="utf-8"), lambda: None])
    ot.czekaj = lambda s: next(kroki)()
    assert cli.sledz_logi({"panel": p}, ot, obiegi=3) == 0
    assert capsys.readouterr().out.splitlines() == ["nowy 1", "po rotacji"]


def test_autostart_on_off_status(tmp_path, capsys):
    u = _zainstalowane(tmp_path)
    auto = AtrapaAutostartu()
    ot = _ot(tmp_path, moduly={"autostart": auto})
    assert cli.main(["autostart", "on"], otoczenie=ot) == 0
    assert auto.argv[-1] == "serwis" and auto.argv[1:4] == ["-I", "-X", "utf8"]
    assert auto.argv[4].endswith(os.path.join("jarvo", "start.py")) and auto.argv[5:7] == ["--korzen", str(u.root)]
    assert "Autostart: włączony (zadanie Harmonogramu Jarvo)" in capsys.readouterr().out
    assert cli.main(["autostart", "off"], otoczenie=ot) == 0
    assert [w[0] for w in auto.wywolania] == ["wlacz", "wylacz"]
    assert cli.main(["autostart", "status"], otoczenie=ot) == 0
    assert "Autostart: wyłączony" in capsys.readouterr().out
    pusty = _ot(tmp_path / "inny", moduly={"autostart": auto})
    assert cli.main(["autostart", "on"], otoczenie=pusty) == 1 and len(auto.wywolania) == 2


def test_doctor_na_zainstalowanym(tmp_path, capsys, monkeypatch):
    u = _zainstalowane(tmp_path)
    port = wolny_port()
    auto = AtrapaAutostartu()
    monkeypatch.setenv("HOME", str(tmp_path / "dom"))                # Path.home() w sprawdz_polecenie (POSIX)
    nasze = u.root / "bin" / "jarvo.cmd" if WINDOWS else tmp_path / "dom" / ".local" / "bin" / "jarvo"
    nasze.parent.mkdir(parents=True, exist_ok=True)
    nasze.write_text("@echo off\r\n" if WINDOWS else "#!/bin/sh\n", encoding="utf-8")
    nasze.chmod(0o755)
    ot = _ot(tmp_path, moduly={"autostart": auto, "nadzorca": AtrapaNadzorcy()}, port=port,
             env={"PATH": atrapy.sciezka(nasze.parent)})
    assert cli.main(["doctor", "--json"], otoczenie=ot) in (0, 1)
    d = {w["nazwa"]: w for w in json.loads(capsys.readouterr().out)["wyniki"]}
    assert d["korzeń"]["stan"] == "ok"
    assert d["uv"]["stan"] == "ok" and "0.12.13" in d["uv"]["opis"]
    assert d["Hermes"]["stan"] == "ok" and PIN[:7] in d["Hermes"]["opis"]
    assert d[f"port {port} (panel)"]["stan"] == "ok"
    assert d["autostart"]["stan"] == "uwaga" and "jarvo autostart on" in d["autostart"]["rada"]
    assert d["polecenie jarvo"]["stan"] == "ok"
    auto.wlaczony = True
    assert cli.sprawdz_autostart(u, ot)["stan"] == "ok"
    # checkout na innym commicie niż pin: błąd z radą (bez `hermes update`)
    checkout = Path(srodowisko.biezace(u)["hermes"])
    (checkout / ".git" / "HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
    wynik = cli.sprawdz_hermesa(u, REPO)
    assert wynik["stan"] == "blad" and "hermes update" in wynik["rada"]
    # zajęty port panelu bez serwisu Jarva: błąd z nazwą programu, jeśli system ją poda
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
        s.listen()
        wyniki = {w["nazwa"]: w for w in cli.sprawdz_porty(u, ot, dziala=False)}
    panel = wyniki[f"port {port} (panel)"]
    assert panel["stan"] == "blad" and "JARVO_PANEL_PORT" in panel["rada"]


def test_kto_slucha_i_port_zajety():
    port = wolny_port()
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
        s.listen()
        assert cli.port_zajety(port)
        kto = cli.kto_slucha(port)
        if kto is not None:                     # netstat (Windows) albo lsof (POSIX) jest
            assert f"PID {os.getpid()}" in kto
    assert not cli.port_zajety(port)


# ---------------------------------------------------------------- instalator

HERMES_PIN = {"repo": "https://github.com/NousResearch/hermes-agent", "tag": "v2026.9.24", "commit": PIN,
              "wersja": "0.21.5", "dodatki": ["all"]}


def _aplikacja(tmp_path: Path, adres: str, www: Path, nazwa: str = "app", sha: str = SHA_JARVA) -> Path:
    """Kod Jarva z manifestem atrap: uv, python313 i python312 z serwera 127.0.0.1 (ten sam plik na 5 platform)."""
    archiwa = {
        "uv": _tar_gz({"uv-x/uv.exe": b"uv", "uv-x/uv": b"uv"}),
        "python313": _tar_gz({"python/python.exe": b"py", "python/pythonw.exe": b"pyw", "python/bin/python3": b"py"}),
        "python312": _tar_gz({"python/python.exe": b"py", "python/bin/python3": b"py"}),
    }
    wersje = {"uv": "0.12.13", "python313": "3.13.17+20261021", "python312": "3.12.15+20261021"}
    narz = {}
    for n, dane in archiwa.items():
        (www / f"{nazwa}-{n}.tar.gz").write_bytes(dane)
        wpis = {"url": f"{adres}/{nazwa}-{n}.tar.gz", "sha256": _sha(dane), "rozmiar": len(dane), "format": "tar.gz",
                "usun_poziom": 1, **({"bin": ["."]} if n == "uv" else {})}
        narz[n] = {"wersja": wersje[n], "kiedy": "instalacja", "licencja": "MIT", "zrodlo": n,
                   "pliki": {p: wpis for p in sciezki.PLATFORMY}}
    app = tmp_path / nazwa
    (app / "vendor").mkdir(parents=True)
    (app / "vendor" / "natywne.lock.json").write_text(json.dumps({"version": 1, "hermes": HERMES_PIN,
                                                                  "narzedzia": narz}), encoding="utf-8")
    (app / "jarvo").mkdir()
    (app / "jarvo" / "start.py").write_text("# atrapa\n", encoding="utf-8")
    (app / ".jarvo-wersja").write_text(sha + "\n", encoding="utf-8")
    return app


@pytest.fixture
def stanowisko(tmp_path, serwer, monkeypatch):
    """Instalator na atrapach: moduły Jarva, rejestr, git, procesy w tle i panel; HOME w katalogu testu."""
    www, adres = serwer
    dom = tmp_path / "dom"
    dom.mkdir()
    monkeypatch.setenv("HOME", str(dom))
    git = atrapy.program(tmp_path / "narz", "git", "print('git version 2.54.0 (atrapa)')\n")
    nadzorca = AtrapaNadzorcy()
    s = {"www": www, "adres": adres, "dom": dom, "nadzorca": nadzorca, "hermes": AtrapaHermesa(),
         "autostart": AtrapaAutostartu(nadzorca), "zmiany": AtrapaZmian(), "rejestr": RejestrAtrapa(), "w_tle": [],
         "log": [], "moduly": {}}

    def w_tle(argv, env, log):
        s["w_tle"].append(argv)
        nadzorca.dziala = True
        return 4242

    def otoczenie(**kw):
        opcje = dict(rejestr=s["rejestr"], program=lambda n: str(git) if n == "git" else None, uruchom_w_tle=w_tle,
                     odpowiada=lambda a, c: nadzorca.dziala)
        opcje.update(kw)
        moduly = {"hermes": s["hermes"], "nadzorca": nadzorca, "autostart": s["autostart"],
                  "zmiany_hosta": s["zmiany"], **s["moduly"]}
        return _ot(tmp_path, moduly=moduly, env={"PATH": atrapy.sciezka(tmp_path / "narz", reszta=False),
                                                 "SHELL": "/bin/bash"}, **opcje)
    s["otoczenie"] = otoczenie
    s["u"] = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    return s


def _instaluj(s, app, **kw) -> int:
    s["log"].clear()
    return instalator.instaluj(s["u"], app, log=s["log"].append, otoczenie=s["otoczenie"](), **kw)


def _migawka(katalog: Path) -> dict[str, bytes]:
    return {str(p.relative_to(katalog)): p.read_bytes() for p in sorted(katalog.rglob("*"))
            if p.is_file() and p.name != "instalacja.log"}


def test_instaluj_na_atrapach_i_drugi_przebieg_niczego_nie_zmienia(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    assert _instaluj(s, app) == 0, "\n".join(s["log"])
    log = "\n".join(s["log"])
    for krok in ("Sprawdzenie komputera", "Katalogi", "uv", "Python 3.13", "Python 3.12", "Spis narzędzi",
                 "Wersja Jarva", "Hermes", "Front panelu", "Bezpieczne ustawienia Hermesa", "Środowisko procesów",
                 "Polecenie jarvo", "Autostart", "Serwis", "Panel"):
        assert re.search(rf"\[[#-]+\] +\d+/15  {re.escape(krok)}$", log, re.M), krok
    assert "Panel: http://127.0.0.1:19199/" in log and "serwis działa (uruchomił go autostart)" in log
    narz = srodowisko.narzedzia(u)
    assert set(narz) == {"uv", "python313", "python312"}
    assert Path(narz["python313"]["katalog"]) == u.program / "narzedzia" / "python313" / "3.13.17"
    assert narz["uv"]["bin"] == [str(u.program / "narzedzia" / "uv" / "0.12.13")]
    biez = srodowisko.biezace(u)
    assert biez["app"] == str(app.resolve()) and biez["wersja"] == SHA_JARVA[:12]
    assert biez["hermes"] == str(u.program / "hermes" / PIN[:12]) and biez["web_dist"].endswith("web_dist")
    assert json.loads((u.stan / "srodowisko.json").read_text(encoding="utf-8"))["HERMES_HOME"] == str(u.dane)
    h = s["hermes"].wywolania
    assert h[0][0] == "zainstaluj" and h[0][1] == PIN and h[0][2].name.startswith("git")
    assert h[0][3].parent == u.program / "narzedzia" / "uv" / "0.12.13" and h[0][4].is_file()
    assert ("web_dist", None) in h and ("konfiguracja", str(u.dane), "1") in h
    argv = s["autostart"].argv
    assert argv[-3:] == ["--korzen", str(u.root), "serwis"]
    assert argv[0].endswith("pythonw.exe" if WINDOWS else "python3")
    assert s["autostart"].wywolania == [("wlacz", True)] and not s["w_tle"]       # serwis wystartował autostartem
    rodzaje = [w["rodzaj"] for w in s["zmiany"].lista]
    if WINDOWS:
        cmd = u.root / "bin" / "jarvo.cmd"
        tekst = cmd.read_bytes()
        assert tekst.isascii() and b"\r\n" in tekst and b" -I -X utf8 " in tekst and b"%*" in tekst
        assert str(app.resolve() / "jarvo" / "start.py").encode() in tekst
        assert f'--korzen "{u.root}" %*'.encode() in tekst
        assert s["rejestr"].czytaj("Environment", "Path") == (rf"C:\Narzedzia;%USERPROFILE%\bin;{u.root / 'bin'}", 2)
        assert s["rejestr"].ogloszenia == 1 and rodzaje == ["plik", "path-uzytkownika"]
    else:
        sh = s["dom"] / ".local" / "bin" / "jarvo"
        assert os.access(sh, os.X_OK) and "exec " in sh.read_text(encoding="utf-8")
        profil = instalator.plik_rc(s["dom"], "/bin/bash", sciezki.MACOS).read_text(encoding="utf-8")
        assert profil.count("# >>> jarvo >>>") == 1 and ".local/bin" in profil
        assert rodzaje == ["plik", "blok-rc"]
    # drugi przebieg: nic nowego w plikach, dzienniku, PATH ani procesach
    przed = (_migawka(u.root), _migawka(s["dom"]), len(s["zmiany"].lista), list(s["rejestr"].zapisy))
    assert _instaluj(s, app) == 0, "\n".join(s["log"])
    assert "Gotowe. Zmiany w tym przebiegu: brak." in s["log"]
    assert (_migawka(u.root), _migawka(s["dom"]), len(s["zmiany"].lista), s["rejestr"].zapisy) == przed
    assert not s["w_tle"] and [w for w in s["hermes"].wywolania if w[0] == "web_dist"] == [("web_dist", None)]
    assert (u.logi / "instalacja.log").read_text(encoding="utf-8").count("Jarvo natywnie: instalacja w") == 2


def test_instaluj_nowa_wersja_obok_starej_i_restart_serwisu(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"])) == 0
    nowa = _aplikacja(tmp_path, s["adres"], s["www"], nazwa="app2", sha="a" * 40)
    assert _instaluj(s, nowa) == 0, "\n".join(s["log"])
    assert srodowisko.biezace(u)["app"] == str(nowa.resolve()) and srodowisko.biezace(u)["wersja"] == "a" * 12
    poprzedni = json.loads((u.program / "current.poprzedni.json").read_text(encoding="utf-8"))
    assert poprzedni["app"] == str((tmp_path / "app").resolve())
    assert s["nadzorca"].zatrzymania == 1 and s["nadzorca"].dziala            # stary zatrzymany, nowy z autostartu
    assert "nowa wersja: zatrzymuję serwis poprzedniej" in "\n".join(s["log"])
    polecenie = (u.root / "bin" / "jarvo.cmd") if WINDOWS else (s["dom"] / ".local" / "bin" / "jarvo")
    assert "app2" in polecenie.read_text(encoding="utf-8")


def test_instaluj_bez_autostartu_startuje_serwis_w_tle(tmp_path, stanowisko):
    s = stanowisko
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"]), autostart=False) == 0, "\n".join(s["log"])
    assert s["autostart"].wywolania == [] and len(s["w_tle"]) == 1
    assert s["w_tle"][0][-3:] == ["--korzen", str(s["u"].root), "serwis"]
    assert any("serwis uruchomiony w tle (PID 4242)" in w for w in s["log"])


def test_instaluj_bez_path_nie_rusza_niczego_poza_korzeniem(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    if not WINDOWS:                              # cudze ~/.local/bin/jarvo nie przeszkadza, polecenie idzie do root/bin
        stare = s["dom"] / ".local" / "bin" / "jarvo"
        stare.parent.mkdir(parents=True)
        stare.write_text("#!/bin/sh\nexec docker exec jarvo-hermes hermes\n", encoding="utf-8")
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"]), bez_path=True, start=False, autostart=False) == 0
    assert (u.root / "bin" / ("jarvo.cmd" if WINDOWS else "jarvo")).is_file()
    assert [w["rodzaj"] for w in s["zmiany"].lista] == ["plik"] and not s["rejestr"].zapisy
    assert not list(s["dom"].glob(".*profile")) and any("--bez-path" in w for w in s["log"]) == WINDOWS


def test_polecenie_posix_nie_podmienia_polecenia_innej_instalacji(tmp_path, stanowisko):
    s = stanowisko
    inst = instalator._Instalacja(s["u"], _aplikacja(tmp_path, s["adres"], s["www"]), s["otoczenie"](), s["log"].append,
                                  autostart=False, web_lokalnie=False, start=False, bez_path=False,
                                  platforma="linux-x64")
    dom = tmp_path / "dom4"
    inne = dom / ".local" / "bin" / "jarvo"
    inne.parent.mkdir(parents=True)
    inne.write_text(instalator.tresc_jarvo_sh(PurePosixPath("/x/python3"), PurePosixPath("/x/start.py"),
                                              ["--korzen", "/inny"]), encoding="utf-8")
    inst.polecenie_posix(dom, PurePosixPath("/p"), PurePosixPath("/s"), instalator.argumenty_korzenia(s["u"]))
    assert "--korzen /inny" in inne.read_text(encoding="utf-8")                 # zostało polecenie tamtej
    assert (s["u"].root / "bin" / "jarvo").is_file() and inst.bez_path
    assert any("uruchamia inną instalację Jarva (/inny)" in w for w in inst.uwagi)
    assert [w["rodzaj"] for w in s["zmiany"].lista] == ["plik"]               # bez bloku rc dla tej instalacji


def test_instaluj_odmawia_przy_starej_instalacji(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    if WINDOWS:
        (u.root / "wsl").mkdir(parents=True)
    else:
        stare = s["dom"] / ".local" / "bin" / "jarvo"
        stare.parent.mkdir(parents=True)
        stare.write_text("#!/bin/sh\nexec docker exec jarvo-hermes hermes\n", encoding="utf-8")
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"])) == 1
    log = "\n".join(s["log"])
    assert "BŁĄD w kroku „Sprawdzenie komputera”" in log and "JARVO_ROOT" in log and "E12" in log
    assert not (u.program / "narzedzia").exists() and not s["zmiany"].lista and not s["rejestr"].zapisy


def test_instaluj_bez_gita_i_bez_startu(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    ot = s["otoczenie"](program=lambda n: None)
    log: list[str] = []
    assert instalator.instaluj(u, app, log=log.append, otoczenie=ot) == 1
    assert any("brak działającego programu git" in w for w in log)
    rada = "Git for Windows" if WINDOWS else ("xcode-select --install" if sciezki.MACOS else "menedżerem pakietów")
    assert rada in "\n".join(log)
    assert _instaluj(s, app, start=False) == 0
    assert not s["w_tle"] and s["autostart"].wywolania == [("wlacz", False)] and not s["nadzorca"].dziala
    assert not any("Panel:" in w for w in s["log"])


def test_polecenie_posix_blok_rc_tylko_raz(tmp_path, stanowisko):
    s = stanowisko
    inst = instalator._Instalacja(s["u"], _aplikacja(tmp_path, s["adres"], s["www"]), s["otoczenie"](), s["log"].append,
                                  autostart=False, web_lokalnie=False, start=False, bez_path=False,
                                  platforma="linux-x64")
    dom = tmp_path / "dom2"
    rc = instalator.plik_rc(dom, "/bin/bash", sciezki.MACOS)                  # ~/.profile (macOS: ~/.zprofile)
    rc.parent.mkdir(parents=True)
    rc.write_bytes(b"export EDITOR=vim")                                       # bez końcowego \n
    korzen = instalator.argumenty_korzenia(s["u"])                             # instalacja spod JARVO_ROOT
    for _ in range(2):
        inst.polecenie_posix(dom, PurePosixPath("/opt/py 3/bin/python3"), PurePosixPath("/x/it's/start.py"), korzen)
    tekst = rc.read_text(encoding="utf-8")
    assert tekst.startswith("export EDITOR=vim\n# >>> jarvo >>>") and tekst.count("# <<< jarvo <<<") == 1
    sh = (dom / ".local" / "bin" / "jarvo").read_text(encoding="utf-8")
    assert "exec '/opt/py 3/bin/python3' -I -X utf8 '/x/it'\"'\"'s/start.py' --korzen " in sh
    assert instalator.korzen_polecenia(sh) == str(s["u"].root) and sh.rstrip().endswith('"$@"')
    assert [w["rodzaj"] for w in s["zmiany"].lista] == ["plik", "blok-rc"]
    dom3 = tmp_path / "dom3"
    rc3 = instalator.plik_rc(dom3, "/bin/bash", sciezki.MACOS)
    rc3.parent.mkdir(parents=True)
    rc3.write_text('if [ -d "$HOME/.local/bin" ]; then PATH="$HOME/.local/bin:$PATH"; fi\n', encoding="utf-8")
    inst.polecenie_posix(dom3, PurePosixPath("/p"), PurePosixPath("/s"), korzen)
    assert "# >>> jarvo >>>" not in rc3.read_text(encoding="utf-8")            # plik sam dokłada ~/.local/bin
    assert instalator.plik_rc(dom3, "/bin/zsh", False) == dom3 / ".zprofile"
    assert instalator.plik_rc(dom3, "/bin/bash", True) == dom3 / ".zprofile"
    (dom3 / ".bash_profile").write_text("", encoding="utf-8")
    assert instalator.plik_rc(dom3, "/bin/bash", False) == dom3 / ".bash_profile"


def test_tresc_polecen_jarvo_i_korzen_w_nich():
    cmd = instalator.tresc_jarvo_cmd(Path(r"C:\J\program\python.exe"), Path(r"C:\J\program\app\x\jarvo\start.py"))
    assert cmd.isascii() and cmd.count(b"\r\n") == 4 and b"\n" not in cmd.replace(b"\r\n", b"")
    assert b'"C:\\J\\program\\python.exe" -I -X utf8 "C:\\J\\program\\app\\x\\jarvo\\start.py" %*' in cmd
    assert instalator.ZNACZNIK.encode() in cmd and instalator.korzen_polecenia(cmd.decode()) is None
    z_korzeniem = instalator.tresc_jarvo_cmd(Path(r"C:\p.exe"), Path(r"C:\s.py"), ["--korzen", r"D:\Jarvo Test"])
    assert b'"C:\\s.py" --korzen "D:\\Jarvo Test" %*' in z_korzeniem
    assert instalator.korzen_polecenia(z_korzeniem.decode()) == r"D:\Jarvo Test"
    with pytest.raises(instalator.BladInstalacji, match="ASCII"):
        instalator.tresc_jarvo_cmd(Path(r"C:\Użytkownik\python.exe"), Path(r"C:\s.py"))
    with pytest.raises(instalator.BladInstalacji):
        instalator.tresc_jarvo_cmd(Path(r"C:\p.exe"), Path(r"C:\s.py"), ["--korzen", r"D:\100%\x"])
    sh = instalator.tresc_jarvo_sh(PurePosixPath("/home/a/py"), PurePosixPath("/home/a/start.py"))
    assert sh.startswith("#!/bin/sh\n") and sh.rstrip().endswith('exec /home/a/py -I -X utf8 /home/a/start.py "$@"')
    sh = instalator.tresc_jarvo_sh(PurePosixPath("/p"), PurePosixPath("/s"), ["--korzen", "/x/it's here"])
    assert instalator.korzen_polecenia(sh) == "/x/it's here"


def test_korzen_domyslny_i_argumenty(tmp_path):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    assert not instalator.korzen_domyslny(u) and instalator.argumenty_korzenia(u) == ["--korzen", str(u.root)]
    domyslny = sciezki.uklad({k: v for k, v in os.environ.items() if k != "JARVO_ROOT"})
    assert instalator.korzen_domyslny(domyslny) and instalator.argumenty_korzenia(domyslny) == []


def test_head_gita_bez_gita(tmp_path):
    k = tmp_path / "odlaczony"
    (k / ".git").mkdir(parents=True)
    (k / ".git" / "HEAD").write_text(PIN + "\n", encoding="utf-8")
    assert instalator.head_gita(k) == PIN
    g = tmp_path / "galaz"
    (g / ".git" / "refs" / "heads").mkdir(parents=True)
    (g / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (g / ".git" / "packed-refs").write_text(f"# pack-refs\n{'b' * 40} refs/heads/main\n", encoding="utf-8")
    assert instalator.head_gita(g) == "b" * 40
    (g / ".git" / "refs" / "heads" / "main").write_text("c" * 40 + "\n", encoding="utf-8")
    assert instalator.head_gita(g) == "c" * 40
    w = tmp_path / "worktree"                                  # git worktree: .git to plik, refs we wspólnym katalogu
    wt = g / ".git" / "worktrees" / "w"
    wt.mkdir(parents=True)
    (wt / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (wt / "commondir").write_text("../..\n", encoding="utf-8")
    w.mkdir()
    (w / ".git").write_text(f"gitdir: {wt}\n", encoding="utf-8")
    assert instalator.head_gita(w) == "c" * 40
    assert instalator.head_gita(tmp_path / "nie-ma") is None
    assert instalator.wersja_aplikacji(k) == PIN[:12] and instalator.wersja_aplikacji(g) == "c" * 12
    assert instalator.wersja_aplikacji(tmp_path / "nie-ma") == "dev"
    (k / ".jarvo-wersja").write_text(SHA_JARVA + "\n", encoding="utf-8")       # z bootstrapu: pierwszeństwo
    assert instalator.wersja_aplikacji(k) == SHA_JARVA[:12]


def test_stan_serwisu_i_adres_panelu(tmp_path):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    assert instalator.stan_serwisu(u, _ot(tmp_path))[1].startswith("Jarvo nie jest zainstalowane")
    u.stan.mkdir(parents=True)
    assert instalator.stan_serwisu(u, _ot(tmp_path))[1].startswith("brak modułu nadzorcy")
    assert instalator.adres_panelu({"JARVO_PANEL_PORT": "19150"}) == "http://127.0.0.1:19150/"
    assert instalator.adres_panelu({"JARVO_PANEL_PORT": "zły"}) == "http://127.0.0.1:9119/"
    assert instalator.adres_panelu({}) == "http://127.0.0.1:9119/"


def test_odpowiada_bez_proxy(serwer, monkeypatch):
    www, adres = serwer
    (www / "index.html").write_text("ok", encoding="utf-8")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")    # proxy z ustawień nie może przechwycić 127.0.0.1
    monkeypatch.setenv("NO_PROXY", "")
    assert instalator.odpowiada(adres + "/", 2.0)
    assert not instalator.odpowiada(f"http://127.0.0.1:{wolny_port()}/", 0.5)


# ---------------------------------------------------------------- z prawdziwymi modułami (po scaleniu etapu E3)

def _prawdziwy(nazwa: str):
    try:
        return instalator.modul(nazwa)
    except ImportError:
        pytest.skip(f"jarvo/{nazwa}.py jeszcze nie w tym drzewie (etap E3 składa moduły równolegle)")


def test_instaluj_z_prawdziwym_dziennikiem_zmian_i_nadzorca(tmp_path, stanowisko):
    """Interfejs jarvo/zmiany_hosta.py (pomocnicy plik, blok-rc, path-uzytkownika; cofanie) i klienta nadzorcy:
    instalacja zapisuje dziennik, drugi przebieg go nie zmienia, a cofnięcie zostawia komputer jak przed nią."""
    zmiany, nadzorca = _prawdziwy("zmiany_hosta"), _prawdziwy("nadzorca")
    s, u = stanowisko, stanowisko["u"]
    s["moduly"].update({"zmiany_hosta": zmiany})
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    dom_przed = _migawka(s["dom"])
    assert _instaluj(s, app, start=False) == 0, "\n".join(s["log"])
    wpisy = zmiany.wpisy(u)
    assert {w["rodzaj"] for w in wpisy} == ({"plik", "path-uzytkownika"} if WINDOWS else {"plik", "blok-rc"})
    assert _instaluj(s, app, start=False) == 0 and zmiany.wpisy(u) == wpisy
    raport = zmiany.cofnij(u, lambda argv: (0, ""), rejestr=s["rejestr"], log=None)
    assert {r["wynik"] for r in raport} == {"cofniete"}, raport
    assert _migawka(s["dom"]) == dom_przed
    if WINDOWS:
        assert s["rejestr"].czytaj("Environment", "Path")[0] == r"C:\Narzedzia;%USERPROFILE%\bin;".rstrip(";")
    # prawdziwy klient nadzorcy bez działającego nadzorcy: status mówi „nie działa”, nic nie startuje
    s["moduly"].update({"nadzorca": nadzorca})
    stan, powod = instalator.stan_serwisu(u, s["otoczenie"]())
    assert stan is None and powod
