"""Polecenie jarvo, instalator i skrypty jednego polecenia (docs/NATYWNIE.md: N01–N17, c3, c4, L01, L02, etap E3).

Bootstrapy: adresy i sumy uv i Pythona 3.13 w jarvo/bootstrap/install.ps1 i install.sh są te same co
w vendor/natywne.lock.json; install.ps1 ma samo ASCII bez BOM i parsuje się w PowerShellu; install.sh przechodzi
`bash -n` (na Windows Git Bash z conftest.bash()); suchy przebieg wybiera pliki platformy, Mac z Intelem dostaje
odmowę, JARVO_TOKEN nie pojawia się na ekranie ani w otoczeniu instalatora w Pythonie, a pobranie, suma
i rozpakowanie działają na plikach z serwera na 127.0.0.1 (porty 19100–19199). CLI i instalator biegną na atrapach
(instalator.Otoczenie, wirtualny zegar): nie dotykają PATH, rejestru, autostartu ani procesów właściciela, a drugi
przebieg instalatora niczego nie zmienia. Panel liczy się tylko nasz (/api/status z hermes_home = <dane>), current.json
przełącza się dopiero po udanym Hermesie, froncie i konfiguracji, a `jarvo down` zostawia znacznik zatrzymania.
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
import stat
import subprocess
import sys
import tarfile
import threading
import zipfile
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

import pytest

import atrapy
from conftest import REPO, WINDOWS, uruchom_bash

sys.path.insert(0, str(REPO))
from jarvo import cli, instalator, pobieracz, sciezki, srodowisko  # noqa: E402

WYKRYJ_STARA = instalator.wykryj_stara      # prawdziwa: conftest podmienia ją w każdym teście na „nie ma”

PS1 = REPO / "jarvo" / "bootstrap" / "install.ps1"
SH = REPO / "jarvo" / "bootstrap" / "install.sh"
LOCK = json.loads((REPO / "vendor" / "natywne.lock.json").read_text(encoding="utf-8"))
PIN = LOCK["hermes"]["commit"]
SHA_JARVA = "fb7e3ffa0e77b125f7f24457f8316026bbb3a07b"
PLATFORMY_PS1 = ("windows-x64", "windows-arm64")
PLATFORMY_SH = ("macos-arm64", "linux-x64", "linux-arm64")
ZMIENNE_PROCESU = ("NoDefaultCurrentDirectoryInExePath", "JARVO_ROOT", "JARVO_PANEL_PORT")


# ---------------------------------------------------------------- pomocnicze

class _Cichy(SimpleHTTPRequestHandler):
    def log_message(self, *_a):
        pass


class _Serwer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"       # na Windows SO_REUSEADDR pozwala zająć cudzy port
    daemon_threads = True


def _serwer_na_porcie(handler) -> tuple[ThreadingHTTPServer, int]:
    for port in range(19100, 19200):
        try:
            return _Serwer(("127.0.0.1", port), handler), port
        except OSError:
            continue
    pytest.skip("brak wolnego portu 19100–19199")


@pytest.fixture
def serwer(tmp_path):
    """Serwer plików na 127.0.0.1, port z zakresu prób 19100–19199."""
    katalog = tmp_path / "www"
    katalog.mkdir()
    httpd, port = _serwer_na_porcie(partial(_Cichy, directory=str(katalog)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield katalog, f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def bez_zmian_procesu():
    """cli.main bez atrapy Otoczenia ustawia zmienne procesu (Windows: NoDefaultCurrentDirectoryInExePath,
    JARVO_ROOT, JARVO_PANEL_PORT): po teście wracają do stanu sprzed niego."""
    przed = {k: os.environ.get(k) for k in ZMIENNE_PROCESU}
    yield
    for k, v in przed.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


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
    # wartość klucza tylko w nagłówku (i przechowana na czas instalatora, żeby wróciła do sesji); nigdy w napisie dla
    # człowieka ani w argv programu (nazwa zmiennej może być)
    for linia in tekst.splitlines():
        if "$env:JARVO_TOKEN" in linia and not linia.lstrip().startswith("#"):
            assert re.search(r"if \(\$env:JARVO_TOKEN\)|'Bearer ' \+ \$env:JARVO_TOKEN|"
                             r"^\s*\$klucz = \$env:JARVO_TOKEN$|\{ \$env:JARVO_TOKEN = \$klucz \}", linia), linia


@pytest.mark.parametrize("skrypt", [PS1, REPO / "install.ps1"], ids=["bootstrap", "stary-adres"])
def test_bootstrap_ps1_parsuje_sie(skrypt):
    r = _ps("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{skrypt}', [ref]$null, [ref]$e); $e | ForEach-Object {{ $_.ToString() }}; exit $e.Count")
    assert r.returncode == 0, r.stdout + r.stderr


def test_stary_adres_install_ps1_przekierowuje_na_bootstrap():
    """install.ps1 z katalogu głównego (stare linki, jarvo.pl przed wgraniem strony): ten sam bootstrap natywny
    z tego samego refu, bez WSL; ASCII bez BOM jak bootstrap; klucz tylko w nagłówku."""
    dane = (REPO / "install.ps1").read_bytes()
    assert dane.isascii() and not dane.startswith(b"\xef\xbb\xbf")
    tekst = dane.decode("ascii")
    assert "https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/$ref/jarvo/bootstrap/install.ps1" in tekst
    assert "$ref = $env:JARVO_REF" in tekst and "Invoke-Expression $skrypt" in tekst
    assert "wsl.exe" not in tekst and "wsl --" not in tekst and "Tls12" in tekst
    assert "\"Bearer $($env:JARVO_TOKEN)\"" in tekst and "Write-Host $env:JARVO_TOKEN" not in tekst


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
    # stara instalacja z WSL w domyślnym katalogu: wersja natywna obok (Jarvo-natywnie), stary katalog nietknięty
    stary = tmp_path / "lad" / "Jarvo"
    (stary / "wsl").mkdir(parents=True)
    r = _ps_na_sucho(tmp_path, JARVO_FAKE_ARCH="AMD64", JARVO_ROOT="", LOCALAPPDATA=str(tmp_path / "lad"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"katalog {stary}-natywnie" in r.stdout and f"{stary}-natywnie\\program" in r.stdout
    assert [p.name for p in stary.iterdir()] == ["wsl"]
    (stary / "wsl").rmdir()
    (stary / "bin").mkdir()
    (stary / "bin" / "jarvo.cmd").write_text('@wsl.exe -d Jarvo -u jarvo -- jarvo %*\r\n', encoding="utf-8")
    r = _ps_na_sucho(tmp_path, JARVO_FAKE_ARCH="AMD64", JARVO_ROOT="", LOCALAPPDATA=str(tmp_path / "lad"))
    assert f"katalog {stary}-natywnie" in r.stdout, r.stdout + r.stderr
    (stary / "bin" / "jarvo.cmd").write_text("@rem Jarvo natywnie (jarvo instaluj)\r\n", encoding="utf-8")
    r = _ps_na_sucho(tmp_path, JARVO_FAKE_ARCH="AMD64", JARVO_ROOT="", LOCALAPPDATA=str(tmp_path / "lad"))
    assert f"katalog {stary}\r" in r.stdout or f"katalog {stary}\n" in r.stdout, r.stdout + r.stderr


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


@pytest.mark.windows_only
def test_bootstrap_ps1_korzen_wzgledny_i_z_tylda_od_katalogu_powershella(tmp_path):
    """Względny JARVO_ROOT i `~` liczy się od katalogu PowerShella (nie procesu .NET), a pełna ścieżka wraca do
    $env:JARVO_ROOT, którą potem dostaje instalator w Pythonie, jarvo.cmd i autostart."""
    wstep = _PS_FUNKCJE.format(skrypt=PS1)
    r = _ps(wstep + f"Set-Location -LiteralPath '{tmp_path}'\n"
            "$env:JARVO_ROOT = 'wzgledny\\kat'; 'A=' + (JarvoKorzen); 'E=' + $env:JARVO_ROOT\n"
            "$env:JARVO_ROOT = '~\\jarvo-proba'; 'B=' + (JarvoKorzen)\n"
            "$env:JARVO_ROOT = 'C:\\JarvoProba\\'; 'C=' + (JarvoKorzen)\n"
            "$env:JARVO_ROOT = 'HKCU:\\Software'; try { JarvoKorzen } catch { 'D=' + $_.Exception.Message }\n"
            "Remove-Item Env:JARVO_ROOT; $env:LOCALAPPDATA = 'C:\\Lokalne'; 'F=' + (JarvoKorzen); "
            "'G=' + [bool]$env:JARVO_ROOT\n")
    assert r.returncode == 0, r.stdout + r.stderr
    wiersze = dict(w.split("=", 1) for w in r.stdout.splitlines() if re.match(r"^[A-G]=", w))
    assert wiersze["A"] == str(tmp_path / "wzgledny" / "kat") == wiersze["E"]
    assert wiersze["B"] == str(Path.home() / "jarvo-proba")
    assert wiersze["C"] == r"C:\JarvoProba"
    assert "nie sciezka katalogu na dysku" in wiersze["D"]
    assert wiersze["F"] == r"C:\Lokalne\Jarvo" and wiersze["G"] == "False"     # domyślny korzeń nie idzie do zmiennej


@pytest.mark.windows_only
def test_bootstrap_ps1_instalator_bez_jarvo_token(tmp_path):
    """Instalator w Pythonie (tu atrapa .cmd) nie dostaje JARVO_TOKEN, a sesja PowerShella odzyskuje go po
    zakończeniu, także po błędzie instalatora."""
    atrapa = tmp_path / "python.cmd"
    atrapa.write_text("@if defined JARVO_TOKEN (echo TOKEN-JEST) else (echo TOKEN-BRAK)\r\n@echo ARGV=%*\r\n"
                      "@if \"%1\"==\"blad\" exit /b 1\r\n@if \"%1\"==\"bez-zgody\" exit /b 3\r\n", encoding="ascii",
                      newline="")
    wstep = _PS_FUNKCJE.format(skrypt=PS1)
    r = _ps(wstep + "$env:JARVO_TOKEN = 'tajny-klucz-0123456789'\n"
            f"JarvoUruchomInstalator '{atrapa}' @('instaluj', '--bez-path')\n"
            "'PO=' + $env:JARVO_TOKEN\n"
            f"try {{ JarvoUruchomInstalator '{atrapa}' @('blad') }} catch {{ 'BLAD=' + $_.Exception.Message }}\n"
            "'PO2=' + $env:JARVO_TOKEN\n"
            f"JarvoUruchomInstalator '{atrapa}' @('bez-zgody'); 'KOD3=' + $LASTEXITCODE\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "KOD3=3" in r.stdout                  # bez zgody na przeniesienie starej instalacji: nie błąd
    assert r.stdout.count("TOKEN-BRAK") == 3 and "TOKEN-JEST" not in r.stdout and "tajny" not in r.stdout.split("PO=")[0]
    assert "ARGV=instaluj --bez-path" in r.stdout
    assert "PO=tajny-klucz-0123456789" in r.stdout and "PO2=tajny-klucz-0123456789" in r.stdout
    assert "BLAD=JARVO: instalator Jarva zakonczyl sie bledem" in r.stdout


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
    r = _sh_na_sucho(tmp_path, "Linux", "x86_64")                  # stara z Dockerem: decyduje instalator w Pythonie
    assert r.returncode == 0 and "start.py instaluj" in r.stdout, r.stdout + r.stderr   # (przeniesienie za zgodą)
    stare.write_text(instalator.tresc_jarvo_sh(Path("/x/python3"), Path("/x/start.py")), encoding="utf-8")
    assert _sh_na_sucho(tmp_path, "Linux", "x86_64").returncode == 0      # nasze polecenie: aktualizacja


@pytest.mark.wymaga_bash
def test_bootstrap_sh_instalator_bez_jarvo_token(tmp_path):
    """Instalator w Pythonie (tu atrapa python3) nie dostaje JARVO_TOKEN: klucz był potrzebny tylko do pobrania."""
    py_kat = tmp_path / "py"
    (py_kat / "bin").mkdir(parents=True)
    atrapa = py_kat / "bin" / "python3"
    atrapa.write_text('#!/usr/bin/env bash\necho "TOKEN=${JARVO_TOKEN:-BRAK} ARGV=$*"\n', encoding="utf-8",
                      newline="\n")
    atrapa.chmod(0o755)
    r = _sh(f'source "{_msys(SH)}"\nPY_KAT="{_msys(py_kat)}"; APP=/x/app; DRY=0\n'
            "JARVO_TOKEN=tajny-klucz-0123456789; export JARVO_TOKEN\ninstalator --bez-startu\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "TOKEN=BRAK" in r.stdout and "tajny" not in r.stdout + r.stderr
    assert "ARGV=-I -X utf8 /x/app/jarvo/start.py instaluj --bez-startu" in r.stdout
    # kod 3 (bez zgody na przeniesienie starej instalacji) to nie błąd, inny kod tak
    for kod, oczekiwany in ((3, 0), (1, 1)):
        atrapa.write_text(f"#!/usr/bin/env bash\nexit {kod}\n", encoding="utf-8", newline="\n")
        r = _sh(f'source "{_msys(SH)}"\nPY_KAT="{_msys(py_kat)}"; APP=/x/app; DRY=0\n'
                'instalator\necho "KOD=$KOD"\n')
        assert r.returncode == oczekiwany, r.stdout + r.stderr
        assert (f"KOD={kod}" in r.stdout) == (kod == 3) and ("błędem" in r.stderr) == (kod == 1)


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


def test_start_py_wylacza_szukanie_programow_w_katalogu_biezacym(tmp_path):
    """Windows: launcher ustawia NoDefaultCurrentDirectoryInExePath=1 przed importem CLI (shutil.which i cmd.exe
    nie biorą uv.exe ani git.cmd z katalogu, w którym wpisano polecenie); na POSIX niczego nie zmienia."""
    kod = ("import os, runpy, sys\n"
           "os.environ.pop('NoDefaultCurrentDirectoryInExePath', None)\n"
           f"sys.argv = [{str(REPO / 'jarvo' / 'start.py')!r}, '--help']\n"
           "try:\n    runpy.run_path(sys.argv[0], run_name='__main__')\nexcept SystemExit:\n    pass\n"
           "print('ZMIENNA=' + str(os.environ.get('NoDefaultCurrentDirectoryInExePath')))\n")
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", kod], cwd=tmp_path, capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert ("ZMIENNA=1" if WINDOWS else "ZMIENNA=None") in r.stdout


@pytest.mark.windows_only
def test_start_py_zostawia_krotka_nazwe_8_3(tmp_path):
    """Kod Jarva spod ścieżki z polskimi znakami uruchomiony przez krótką nazwę 8.3 zostaje pod nią (c1: `<program>`
    w ASCII): bez Path.resolve(), który rozwinąłby ją do pełnej."""
    dlugi = tmp_path / "Michał Żółć"
    shutil.copytree(REPO / "jarvo", dlugi / "jarvo", ignore=shutil.ignore_patterns("__pycache__"))
    krotki = sciezki.krotka_sciezka(dlugi)
    if krotki == dlugi or not str(krotki).isascii():
        pytest.skip("ten wolumen nie ma krótkich nazw 8.3")
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(krotki / "jarvo" / "start.py"), "--korzen",
                        str(tmp_path / "root"), "--wersja"], capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    assert r.returncode == 0, r.stderr
    assert f"({krotki})" in r.stdout and "Żółć" not in r.stdout


def test_pomoc_po_polsku_i_argparse_bez_trwalej_zmiany(capsys, bez_zmian_procesu):
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    for slowo in ("użycie: jarvo", "opcje:", "--korzen", "instaluj", "serwis", "up", "down", "status", "panel",
                  "chat", "logs", "autostart", "doctor", "version", "help", "update", "uninstall", "migruj",
                  "komputer", "android"):
        assert slowo in out
    assert cli.main(["autostart", "wlacz"]) == 2
    assert "błąd:" in capsys.readouterr().err
    assert cli.main(["status", "--nieznana"]) == 2
    assert argparse._("usage: ") == "usage: "       # podmiana tylko na czas parsowania
    if WINDOWS:                                     # cli.main na starcie procesu (bez atrapy Otoczenia)
        assert os.environ.get("NoDefaultCurrentDirectoryInExePath") == "1"


def _ot(tmp_path, **kw) -> instalator.Otoczenie:
    """Otoczenie na atrapach: moduły z `moduly`, zmienne bez JARVO_* właściciela, wirtualny zegar (czekaj przesuwa
    go od razu, bez spania), nikt nie słucha na portach (sluchacz), dysk ma dużo miejsca, a innych dysków nie ma
    (instalator liczy potrzebę z manifestu, więc wynik nie zależy od dysku, na którym biegną testy)."""
    kw.setdefault("wolne_miejsce", lambda sciezka: 1 << 50)
    kw.setdefault("dyski", lambda: [])
    env = {k: v for k, v in os.environ.items() if not k.startswith("JARVO_")}
    env.update({"JARVO_ROOT": str(tmp_path / "j"), "JARVO_PANEL_PORT": str(kw.pop("port", 19199))})
    env.update(kw.pop("env", {}))
    moduly = kw.pop("moduly", {})

    def modul(nazwa):
        if nazwa not in moduly:
            raise ImportError(f"No module named 'jarvo.{nazwa}'")
        return moduly[nazwa]
    teraz = [0.0]
    kw.setdefault("czekaj", lambda s: teraz.__setitem__(0, teraz[0] + s))
    kw.setdefault("zegar", lambda: teraz[0])
    kw.setdefault("sluchacz", lambda port: None)
    return instalator.Otoczenie(modul=modul, env=env, **kw)


def http_panelu(u: sciezki.Uklad, warunek=lambda: True, **pola):
    """Atrapa zapytaj_http: /api/status dashboardu tej instalacji (hermes_home = <dane>), gdy warunek(), inaczej
    nikt nie odpowiada."""
    def zapytaj(url, czas):
        if not warunek():
            return None
        return 200, {"version": "0.21.5", "hermes_home": str(u.dane), "auth_required": False, **pola}
    return zapytaj


def test_komputer_rece_i_migruj_przekazuja_argumenty(tmp_path, capsys):
    """`jarvo komputer …` idzie do jarvo/komputer.py, `jarvo komputer rece …` do jarvo/rece.py, `jarvo migruj …` do
    jarvo/migracja.py: argumenty bez zmian (także nieznane parserowi jarvo), kod wyjścia modułu; brak modułu = 1."""
    wywolania = []

    class Komputer:
        @staticmethod
        def main(argv, *, u=None, ot=None):
            wywolania.append(("komputer", argv, u is not None, ot is not None))
            return 3

    class Rece:
        @staticmethod
        def main(argv, *, env=None):
            wywolania.append(("rece", argv, env["JARVO_ROOT"]))
            return 0

    class Migracja:
        @staticmethod
        def main(argv, *, uklad=None, otoczenie=None):
            wywolania.append(("migruj", argv, str(uklad.root)))
            return 0
    ot = _ot(tmp_path, moduly={"komputer": Komputer, "rece": Rece, "migracja": Migracja})
    assert cli.main(["komputer", "on", "--w-tle"], otoczenie=ot) == 3
    assert cli.main(["komputer", "rece", "on", "--aplikacje", "notatnik", "--na", "30m"], otoczenie=ot) == 0
    assert cli.main(["migruj", "--tak", "--katalog", str(tmp_path / "k")], otoczenie=ot) == 0
    assert wywolania == [("komputer", ["on", "--w-tle"], True, True),
                         ("rece", ["on", "--aplikacje", "notatnik", "--na", "30m"], str(tmp_path / "j")),
                         ("migruj", ["--tak", "--katalog", str(tmp_path / "k")], str(tmp_path / "j"))]
    assert cli.main(["komputer", "status"], otoczenie=_ot(tmp_path)) == 1
    assert "brak modułu Komputera" in capsys.readouterr().err
    assert cli.main(["migruj"], otoczenie=_ot(tmp_path)) == 1
    assert cli.W_BUDOWIE == {}                       # update, uninstall i migruj działają


def test_version_i_help(tmp_path, capsys):
    """N16: `jarvo version` (i `wersja`, `--wersja`) oraz `jarvo help [polecenie]`."""
    ot = _ot(tmp_path)
    for polecenie in (["version"], ["wersja"], ["--wersja"]):
        assert cli.main(polecenie, otoczenie=ot) == 0
        out = capsys.readouterr().out
        assert out.startswith("Jarvo ") and f"Hermes {LOCK['hermes']['wersja']}" in out and PIN[:7] in out
    assert cli.main(["help"], otoczenie=ot) == 0 and "użycie: jarvo" in capsys.readouterr().out
    assert cli.main(["help", "status"], otoczenie=ot) == 0
    assert "jarvo status" in (out := capsys.readouterr().out) and "--json" in out
    assert cli.main(["help", "serwis"], otoczenie=ot) == 0 and "jarvo serwis --help" in capsys.readouterr().out
    assert cli.main(["help", "nie-ma"], otoczenie=ot) == 2 and "Nie znam polecenia" in capsys.readouterr().err
    assert not (tmp_path / "j").exists()


def test_korzen_z_argv_jak_jarvo_root(tmp_path, capsys, monkeypatch):
    """Launcher i autostart instalacji spod JARVO_ROOT podają korzeń w argv (Harmonogram nie przekazuje zmiennych);
    względny korzeń liczymy od katalogu bieżącego i podajemy dalej jako pełną ścieżkę."""
    ot = _ot(tmp_path, port=wolny_port())
    ot.env.pop("JARVO_ROOT")
    assert cli.main(["--korzen", str(tmp_path / "inny"), "status", "--json"], otoczenie=ot) == 1
    assert json.loads(capsys.readouterr().out)["root"] == str(tmp_path / "inny")
    assert cli.main([f"--korzen={tmp_path / 'trzeci'}", "status", "--json"], otoczenie=ot) == 1
    assert json.loads(capsys.readouterr().out)["root"] == str(tmp_path / "trzeci")
    assert "JARVO_ROOT" not in os.environ or os.environ["JARVO_ROOT"] != str(tmp_path / "trzeci")   # tylko atrapa
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--korzen", "wzgledny", "status", "--json"], otoczenie=ot) == 1
    assert json.loads(capsys.readouterr().out)["root"] == str(tmp_path / "wzgledny")
    assert ot.env["JARVO_ROOT"] == str(tmp_path / "wzgledny")


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
    for polecenie in (["panel"], ["chat"], ["autostart", "on"]):
        assert cli.main(polecenie, otoczenie=ot) == 1
        assert "nie jest zainstalowane" in capsys.readouterr().err
    assert cli.main(["down"], otoczenie=ot) == 0
    assert not (tmp_path / "j").exists()


def test_status_i_doctor_korzen_z_polskimi_znakami_przed_instalacja(tmp_path, capsys):
    """Korzeń z polskimi znakami, którego jeszcze nie ma: status i doctor mówią „brak instalacji” (krótką nazwę 8.3
    system poda dopiero dla istniejącego katalogu), zamiast błędu układu; niczego nie tworzą."""
    ot = _ot(tmp_path, port=wolny_port(), env={"JARVO_ROOT": str(tmp_path / "Michał Żółć")})
    assert cli.main(["status"], otoczenie=ot) == 1
    assert "instalacja: brak" in capsys.readouterr().out
    assert cli.main(["doctor", "--json"], otoczenie=ot) == 1
    assert json.loads(capsys.readouterr().out)["bledy"] >= 1
    assert not (tmp_path / "Michał Żółć").exists()


class AtrapaNadzorcyBezZnacznika:
    """Jak jarvo/nadzorca.py sprzed znacznika trwałego zatrzymania: kanał (polacz, status, stop) i stan z pliku."""
    CZAS_ZATRZYMANIA = 110.0

    def __init__(self, dziala=False, *, panel="dziala", powod_panelu=None):
        self.dziala, self.zatrzymania, self.argv = dziala, 0, None
        self.panel, self.powod_panelu = panel, powod_panelu
        self.stopy: list[dict] = []
        self.restarty: list[str] = []            # restart(nazwa) z kanału: usługa wstaje z nowym PID-em

    def polacz(self, u):
        if not self.dziala:
            raise ConnectionRefusedError("Nadzorca Jarva nie działa (atrapa)")
        return self

    def status(self):
        def pid(nazwa: str, baza: int) -> int:
            return baza + 10 * self.restarty.count(nazwa)
        return {"nadzorca": {"pid": 100, "stan": "dziala"},
                "uslugi": {"brama": {"stan": "dziala", "pid": pid("brama", 101), "pidy": [111], "gotowa": True,
                                     "restarty": self.restarty.count("brama")},
                           "panel": {"stan": self.panel, "pid": pid("panel", 102), "pidy": [112],
                                     "gotowa": self.panel == "dziala", "restarty": 2 + self.restarty.count("panel"),
                                     "ostatni_kod": 78 if self.panel == "postoj" else None,
                                     "powod": self.powod_panelu}}}

    def stop(self, czekaj: float = 0.0):
        self.dziala = False
        self.zatrzymania += 1
        self.stopy.append({"czekaj": czekaj})
        return {"ok": True}

    def restart(self, nazwa):
        self.restarty.append(nazwa)
        return {"ok": True}

    def stan_z_pliku(self, u):
        return {"dziala": False, "uslugi": {"brama": {"stan": "postój", "ostatni_kod": 78,
                                                       "powod": "brak klucza modelu"}}}

    def main(self, argv):
        self.argv = list(argv)
        return 0


class AtrapaNadzorcy(AtrapaNadzorcyBezZnacznika):
    """Jak jarvo/nadzorca.py ze znacznikiem `<stan>/zatrzymany.json` (oznacz, zdejmij, zatrzymany; stop z powodem)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.znaczniki: list[tuple] = []

    def stop(self, czekaj: float = 0.0, powod: str = ""):
        wynik = super().stop(czekaj)
        self.stopy[-1]["powod"] = powod
        return {**wynik, "trwale": True}

    def oznacz_zatrzymanie(self, u, powod=""):
        self.znaczniki.append(("oznacz", powod))
        (u.stan / "zatrzymany.json").write_text(json.dumps({"wersja": 1, "kiedy": "2026-10-25T10:00:00",
                                                            "powod": powod, "pid": 1}), encoding="utf-8")

    def zdejmij_zatrzymanie(self, u):
        self.znaczniki.append(("zdejmij",))
        (u.stan / "zatrzymany.json").unlink(missing_ok=True)
        return True

    def zatrzymany(self, u):
        return (u.stan / "zatrzymany.json").is_file()


class AtrapaAutostartu:
    """Jak jarvo/autostart.py: wlacz(start=True) od razu uruchamia nadzorcę mechanizmem systemu; `blad` = wlacz
    rzuca BladAutostartu (np. brak user busa systemd)."""

    class BladAutostartu(RuntimeError):
        pass

    def __init__(self, nadzorca: AtrapaNadzorcyBezZnacznika | None = None, *, mechanizm="harmonogram", blad=None):
        self.nadzorca, self.mechanizm, self.blad = nadzorca, mechanizm, blad
        self.wlaczony, self.argv, self.env, self.wywolania = False, None, None, []

    def wlacz(self, u, argv, wykonaj=None, *, start=True, log=print, env=None, **_kw):
        self.wywolania.append(("wlacz", start))
        if self.blad:
            raise self.BladAutostartu(self.blad)
        zmieniony = not self.wlaczony or self.argv != list(argv)
        self.wlaczony, self.argv, self.env = True, list(argv), env
        if start and self.nadzorca is not None:
            self.nadzorca.dziala = True
        return {"system": "atrapa", "mechanizm": self.mechanizm, "zmieniony": zmieniony, "uruchomiony": start,
                "uwagi": []}

    def wylacz(self, u, wykonaj=None, *, env=None, log=print, **_kw):
        self.wlaczony, self.argv = False, None
        self.wywolania.append(("wylacz",))
        return {"usuniety": True, "uwagi": []}

    def stan(self, u, wykonaj=None, *, env=None, **_kw):
        return {"wlaczony": self.wlaczony, "nasz": True, "mechanizm": self.mechanizm if self.wlaczony else None,
                "opis": "włączony (zadanie Harmonogramu Jarvo)" if self.wlaczony else "wyłączony"}


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
    path-uzytkownika); pliki i bloki zapisuje naprawdę (w katalogu testu). `blad_pliku`: zapisz_plik rzuca OSError."""

    def __init__(self):
        self.lista = []
        self.blad_pliku: str | None = None

    def dopisz(self, u, rodzaj, **szczegoly):
        wpis = {"rodzaj": rodzaj, "szczegoly": {k: str(v) if isinstance(v, Path) else v for k, v in szczegoly.items()}}
        if wpis not in self.lista:
            self.lista.append(wpis)
        return wpis

    def wpisy(self, u):
        return [dict(w) for w in self.lista]

    def katalog_przed_zmiana(self, u, cel, dozwolone):
        if Path(cel).exists():
            return None
        self.dopisz(u, "katalog", sciezka=str(cel), dozwolone=sorted(dozwolone))
        return Path(cel)

    def zapisz_plik(self, u, sciezka, tresc, tryb=0o644):
        if self.blad_pliku:
            raise OSError(self.blad_pliku)
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
    """Jak jarvo/hermes.py: checkout `<program>/hermes/<commit12>`, front ze znacznikiem commitu w checkoucie
    (gotowy = bez budowy), konfiguracja. `blad_web` i `blad_konfiguracji`: krok rzuca wyjątek."""
    ZNACZNIK_WEB = ".jarvo-web-dist.json"

    def __init__(self):
        self.wywolania = []
        self.blad_web: str | None = None
        self.blad_konfiguracji: str | None = None

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
        dist = checkout / "hermes_cli" / "web_dist"
        if (checkout / self.ZNACZNIK_WEB).is_file() and (dist / "index.html").is_file():
            self.wywolania.append(("web_dist", "gotowy", checkout.name))
            return dist
        if self.blad_web:
            raise RuntimeError(self.blad_web)
        self.wywolania.append(("web_dist", "buduje", checkout.name))
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")
        (checkout / self.ZNACZNIK_WEB).write_text(json.dumps({"commit": checkout.name}), encoding="utf-8")
        return dist

    def konfiguracja_bezpieczna(self, u, checkout, env, log=print):
        if self.blad_konfiguracji:
            raise RuntimeError(self.blad_konfiguracji)
        self.wywolania.append(("konfiguracja", env["HERMES_HOME"], env["HERMES_DISABLE_LAZY_INSTALLS"],
                               env.get("JARVO_REPO")))

    def argv_hermesa(self, checkout, *argumenty):
        return [str(srodowisko.hermes_python(checkout)), "-m", "hermes_cli.main", *argumenty]


class AtrapaFloty:
    """Jak jarvo/flota.py: zainstaluj_flote (build i install_fleet.py; profil jarvo na dysku), pierwszy przebieg
    zmienia flotę i chce restartu bramy i panelu, kolejne nie (`zmiany` na następny przebieg); uslugi_do_restartu
    i potwierdz_restart_panelu jak w module. `blad`: build się nie udał."""

    def __init__(self):
        self.wywolania: list[dict] = []
        self.potwierdzenia: list[str] = []
        self.zmiany = ["profil jarvo", "wtyczka jarvo-hq"]
        self.blad: str | None = None

    def zainstaluj_flote(self, u, env, *, log=print, pierwsza=None, wznow_rutyny=False):
        self.wywolania.append({"env": dict(env), "biez": srodowisko.biezace(u)})
        if self.blad:
            raise RuntimeError(self.blad)
        (u.dane / "profiles" / "jarvo").mkdir(parents=True, exist_ok=True)
        log("▶ Flota (atrapa)")
        zmiany, self.zmiany = self.zmiany, []
        return {"wersja": 1, "agenci": ["jarvo"], "zmiany": zmiany, "restart_bramy": bool(zmiany),
                "restart_panelu": bool(zmiany), "odcisk_panelu": "0123456789abcdef", "ostrzezenia": []}

    def uslugi_do_restartu(self, wynik):
        return [n for n, pole in (("brama", "restart_bramy"), ("panel", "restart_panelu")) if wynik.get(pole)]

    def potwierdz_restart_panelu(self, u, odcisk):
        self.potwierdzenia.append(odcisk)
        return True


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
    assert "nie odpowiada" in out                                               # na porcie panelu nikt nie słucha
    nadzorca.dziala = False
    assert cli.main(["status"], otoczenie=ot) == 1
    out = capsys.readouterr().out
    assert "nie działa (Nadzorca Jarva nie działa (atrapa)); ostatni stan z pliku:" in out
    assert "brama: postój, kod 78, powód brak klucza modelu" in out


def test_serwis_up_down(tmp_path, capsys):
    u = _zainstalowane(tmp_path)
    nadzorca = AtrapaNadzorcy()
    assert cli.main(["serwis", "--status", "-v"], otoczenie=_ot(tmp_path, moduly={"nadzorca": nadzorca})) == 0
    assert nadzorca.argv == ["--status", "-v"]
    assert cli.main(["serwis"], otoczenie=_ot(tmp_path)) == 1                 # brak modułu: jasny błąd
    assert "brak modułu nadzorcy" in capsys.readouterr().err
    w_tle = []

    def start(argv, env, log):
        w_tle.append((argv, env))
        nadzorca.dziala = True
        return 1
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca}, uruchom_w_tle=start,
             zapytaj_http=http_panelu(u, lambda: nadzorca.dziala),
             env={"JARVO_TOKEN": "tajny-klucz", "OPENAI_API_KEY": "sk-tajny", "SSH_AUTH_SOCK": "/tmp/agent"})
    assert cli.main(["up"], otoczenie=ot) == 0 and len(w_tle) == 1
    out = capsys.readouterr().out
    assert "Serwis nie działa: uruchamiam go" in out and "Serwis uruchomiony w tle (PID 1)." in out
    assert "Jarvo działa. Panel: http://127.0.0.1:19199/" in out
    env = w_tle[0][1]                                                            # bez sekretów z powłoki właściciela
    assert not {"JARVO_TOKEN", "OPENAI_API_KEY", "SSH_AUTH_SOCK"} & set(env) and env["JARVO_ROOT"] == str(u.root)
    assert cli.main(["up"], otoczenie=ot) == 0 and len(w_tle) == 1              # działa: bez drugiego startu
    assert cli.main(["down"], otoczenie=ot) == 0 and nadzorca.zatrzymania == 1
    assert "Serwis zatrzymany" in capsys.readouterr().out
    assert cli.main(["down"], otoczenie=ot) == 0 and nadzorca.zatrzymania == 1  # już nie działa


def test_down_znacznik_zatrzymania_i_up_go_zdejmuje(tmp_path, capsys):
    """`jarvo down` zostawia znacznik `<stan>/zatrzymany.json` (nadzorca.oznacz_zatrzymanie, stop z powodem): autostart
    nie podniesie floty sam (Windows: zapasowe wyzwalacze co 5 minut), `status` to pokazuje, a `jarvo up` zdejmuje
    znacznik przed startem."""
    u = _zainstalowane(tmp_path)
    nadzorca = AtrapaNadzorcy(dziala=True)
    w_tle = []
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca}, zapytaj_http=http_panelu(u, lambda: nadzorca.dziala),
             uruchom_w_tle=lambda argv, env, log: w_tle.append(argv) or nadzorca.__setattr__("dziala", True) or 7)
    assert cli.main(["down"], otoczenie=ot) == 0
    out = capsys.readouterr().out
    assert "Serwis zatrzymany" in out and "Nie wstanie sam" in out
    assert nadzorca.znaczniki == [("oznacz", "jarvo down")] and (u.stan / "zatrzymany.json").is_file()
    assert nadzorca.stopy[0]["powod"] == "jarvo down" and nadzorca.stopy[0]["czekaj"] >= instalator.CZAS_STOPU
    assert cli.main(["status"], otoczenie=ot) == 1
    assert "serwis:     zatrzymany (jarvo down, 2026-10-25T10:00:00): autostart go nie uruchomi" in \
        capsys.readouterr().out
    assert cli.main(["status", "--json"], otoczenie=ot) == 1
    assert json.loads(capsys.readouterr().out)["serwis"]["zatrzymanie"]["powod"] == "jarvo down"
    assert cli.main(["up"], otoczenie=ot) == 0 and len(w_tle) == 1
    assert ("zdejmij",) in nadzorca.znaczniki and not (u.stan / "zatrzymany.json").exists()


def test_down_ze_starszym_nadzorca_zostawia_sam_plik(tmp_path, capsys):
    """Nadzorca bez funkcji znacznika (moduł sprzed poprawki): `down` zapisuje sam plik w tym samym formacie i mówi,
    że autostart może podnieść serwis; `up` plik usuwa."""
    u = _zainstalowane(tmp_path)
    nadzorca = AtrapaNadzorcyBezZnacznika(dziala=True)
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca}, zapytaj_http=http_panelu(u, lambda: nadzorca.dziala),
             uruchom_w_tle=lambda argv, env, log: nadzorca.__setattr__("dziala", True) or 7)
    assert cli.main(["down"], otoczenie=ot) == 0
    assert "nie zna znacznika zatrzymania" in capsys.readouterr().out
    znacznik = json.loads((u.stan / "zatrzymany.json").read_text(encoding="utf-8"))
    assert znacznik["powod"] == "jarvo down" and znacznik["kiedy"] and nadzorca.zatrzymania == 1
    assert cli.main(["up"], otoczenie=ot) == 0 and not (u.stan / "zatrzymany.json").exists()


def test_chat_srodowisko_tryb_i_argumenty_dla_hermesa(tmp_path, capsys):
    u = _zainstalowane(tmp_path)
    wywolania = []
    ot = _ot(tmp_path, moduly={"hermes": AtrapaHermesa()}, env={"HERMES_YOLO_MODE": "1", "HERMES_HOME": "/obcy",
                                                                "GITHUB_TOKEN": "ghp_tajny"},
             na_pierwszym_planie=lambda argv, env: wywolania.append((argv, env)) or 7)
    assert cli.main([], otoczenie=ot) == 7                                       # samo `jarvo` = rozmowa
    argv, env = wywolania[-1]
    assert argv[1:] == ["-m", "hermes_cli.main", "-p", "jarvo", "chat"]
    assert env["JARVO_TRYB_ZGOD"] == "projekt" and env["HERMES_HOME"] == str(u.dane)   # domyślny tryb (I08)
    assert "HERMES_YOLO_MODE" not in env and "GITHUB_TOKEN" not in env and env["HERMES_DISABLE_LAZY_INSTALLS"] == "1"
    assert env["JARVO_FOLDER_PROJEKTU"] == os.getcwd()                          # folder startu czatu (tryb projekt)
    # H20: narzędzia plików piszą pod <dane> i w folderze projektu (lista z os.pathsep jak w agent/file_safety.py)
    assert env["HERMES_WRITE_SAFE_ROOT"].split(os.pathsep) == [str(u.dane), os.getcwd()]
    assert cli.main(["--tryb", "pelny", "--resume", "abc"], otoczenie=ot) == 7
    argv, env = wywolania[-1]
    assert argv[-4:] == ["chat", "--yolo", "--resume", "abc"] and env["JARVO_TRYB_ZGOD"] == "pelny"   # tylko flaga
    assert "HERMES_YOLO_MODE" not in env
    assert cli.main(["chat", "--tryb", "pytaj", "--profil", "default", "--", "-q", "hej"], otoczenie=ot) == 7
    argv, env = wywolania[-1]
    assert argv[3:] == ["-p", "default", "chat", "-q", "hej"] and env["JARVO_TRYB_ZGOD"] == "pytaj"
    assert cli.main(["chat", "--profil", "web"], otoczenie=ot) == 1             # profil jeszcze nie zainstalowany
    assert "etap E4" in capsys.readouterr().err
    assert cli.main(["chat", "--profil", "../x"], otoczenie=ot) == 2
    assert cli.main(["chat", "--tryb", "yolo"], otoczenie=ot) == 2
    (u.dane / "profiles" / "jarvo-operator").mkdir(parents=True)
    assert cli.main(["chat", "--tryb", "pelny", "--profil", "jarvo-operator"], otoczenie=ot) == 1   # nigdy pełny
    assert "jarvo-operator" in capsys.readouterr().err
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
             zapytaj_http=http_panelu(u, lambda: nadzorca.dziala), otworz=otwarte.append)
    assert cli.main(["panel"], otoczenie=ot) == 0
    assert otwarte == [f"http://127.0.0.1:{port}/"]
    argv, env, log = uruchomione[0]
    assert argv[-1] == "serwis" and argv[1:4] == ["-I", "-X", "utf8"] and log == u.logi / "serwis-start.log"
    assert argv[-3:-1] == ["--korzen", str(u.root)]                       # korzeń spod JARVO_ROOT idzie w argv
    assert env["JARVO_ROOT"] == str(u.root) and env["JARVO_PANEL_PORT"] == str(port)
    assert "Serwis uruchomiony w tle (PID 4242)" in capsys.readouterr().out
    assert cli.main(["panel", "--bez-przegladarki"], otoczenie=ot) == 0          # działa: bez drugiego startu
    assert len(uruchomione) == 1 and len(otwarte) == 1
    # serwis działa, ale panel nie odpowiada: limit czasu z radą
    ot2 = _ot(tmp_path, moduly={"nadzorca": nadzorca}, port=port, uruchom_w_tle=lambda *a: 1,
              zapytaj_http=lambda url, czas: None, otworz=otwarte.append)
    assert cli.main(["panel"], otoczenie=ot2) == 1
    assert "nie odpowiada po 180 s" in (err := capsys.readouterr().err) and "jarvo logs panel" in err
    # serwis nie wstał (np. błąd startu): bez czekania na limit panelu, z radą o logu startu
    nadzorca.dziala = False
    assert cli.main(["panel"], otoczenie=ot2) == 1
    assert "serwis Jarva nie działa" in (err := capsys.readouterr().err) and "serwis-start" in err
    assert cli.main(["panel"], otoczenie=_ot(tmp_path, port=port)) == 1          # bez nadzorcy: od razu błąd
    assert "brak modułu nadzorcy" in capsys.readouterr().err


def test_up_przy_cudzym_panelu_na_porcie_mowi_kto_go_trzyma(tmp_path, capsys):
    """Port 9119 trzyma stara flota z WSL (wslrelay) albo prywatny Hermes: `jarvo up` i `jarvo panel` nie uznają go
    za panel Jarva, nie czekają 3 minut i mówią, kto trzyma port, z radą JARVO_PANEL_PORT."""
    u = _zainstalowane(tmp_path)
    nadzorca, w_tle, otwarte = AtrapaNadzorcy(), [], []
    obcy = {"version": "0.20.1", "hermes_home": "/opt/data", "auth_required": False}
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca}, zapytaj_http=lambda url, czas: (200, obcy),
             sluchacz=lambda port: (4321, "wslrelay.exe"), uruchom_w_tle=lambda *a: w_tle.append(a) or 1,
             otworz=otwarte.append)
    assert cli.main(["up"], otoczenie=ot) == 1
    err = capsys.readouterr().err
    assert "wslrelay.exe (PID 4321)" in err and "WSL" in err and "JARVO_PANEL_PORT" in err
    assert "HERMES_HOME /opt/data" in err and not w_tle
    ot.zapytaj_http = lambda url, czas: (404, None)                         # coś innego niż Hermes
    assert cli.main(["panel"], otoczenie=ot) == 1 and not otwarte
    assert "nie odpowiada jak panel Hermesa" in capsys.readouterr().err
    nadzorca.dziala = True                                                   # nasz serwis działa, ale port zajęty
    assert cli.main(["panel"], otoczenie=ot) == 1 and not otwarte


def test_stan_panelu_tylko_dashboard_tej_instalacji(tmp_path):
    u = _zainstalowane(tmp_path)

    def stan(odp):
        return instalator.stan_panelu(u, _ot(tmp_path, zapytaj_http=lambda url, czas: odp))
    assert stan(None) == ("brak", "brak odpowiedzi")
    assert stan((503, None)) == ("brak", "HTTP 503")
    assert stan((200, {"version": "0.21.5", "hermes_home": str(u.dane)})) == ("nasz", "")
    if WINDOWS:                                                             # bez wielkości liter na Windows
        assert stan((200, {"version": "0.21.5", "hermes_home": str(u.dane).upper()}))[0] == "nasz"
    assert stan((200, {"version": "0.21.5", "hermes_home": str(tmp_path / "inny")}))[0] == "obcy"
    assert stan((404, None))[0] == "obcy" and "HTTP 404" in stan((404, None))[1]
    assert stan((0, None)) == ("obcy", "program, który nie odpowiada jak panel Hermesa (odpowiedź spoza HTTP)")
    assert stan((200, {"cos": "innego"}))[0] == "obcy"
    # za bramką logowania (tryb LAN) dashboard nie podaje hermes_home: rozpoznaje go install_id z <dane>
    (u.dane / "install_id").write_text("a" * 32 + "\n", encoding="utf-8")
    assert stan((200, {"version": "0.21.5", "install_id": "a" * 32}))[0] == "nasz"
    assert stan((200, {"version": "0.21.5", "install_id": "b" * 32}))[0] == "obcy"
    adresy = []
    instalator.stan_panelu(u, _ot(tmp_path, port=19150, zapytaj_http=lambda url, czas: adresy.append(url)))
    assert adresy == ["http://127.0.0.1:19150/api/status"]


class _Status(BaseHTTPRequestHandler):
    tresc: dict = {}

    def do_GET(self):  # noqa: N802 - nazwa z http.server
        dane = json.dumps(self.tresc).encode("utf-8") if self.path == "/api/status" else b"nie ma"
        self.send_response(200 if self.path == "/api/status" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dane)))
        self.end_headers()
        self.wfile.write(dane)

    def log_message(self, *_a):
        pass


def test_zapytaj_http_prawdziwy_serwer_bez_proxy(tmp_path, monkeypatch):
    """Prawdziwe zapytanie na 127.0.0.1 (port z zakresu prób) mimo proxy w zmiennych: /api/status z hermes_home
    tej instalacji to nasz panel, inny HERMES_HOME to cudzy."""
    u = _zainstalowane(tmp_path)
    handler = type("StatusTestu", (_Status,), {"tresc": {"version": "0.21.5", "hermes_home": str(u.dane)}})
    httpd, port = _serwer_na_porcie(handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")    # proxy z ustawień nie może przechwycić 127.0.0.1
    monkeypatch.setenv("NO_PROXY", "")
    try:
        assert instalator.zapytaj_http(f"http://127.0.0.1:{port}/api/status", 2.0) == (200, handler.tresc)
        assert instalator.zapytaj_http(f"http://127.0.0.1:{port}/inne", 2.0) == (404, None)
        ot = instalator.Otoczenie(modul=lambda n: (_ for _ in ()).throw(ImportError(n)),
                                  env={"JARVO_ROOT": str(u.root), "JARVO_PANEL_PORT": str(port)})
        assert instalator.stan_panelu(u, ot) == ("nasz", "")
        handler.tresc = {"version": "0.21.5", "hermes_home": str(tmp_path / "prywatny-hermes")}
        assert instalator.stan_panelu(u, ot)[0] == "obcy"
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert instalator.zapytaj_http(f"http://127.0.0.1:{wolny_port()}/api/status", 0.5) is None


def test_czekaj_na_panel_postoj_i_martwy_serwis(tmp_path):
    u = _zainstalowane(tmp_path)
    nadzorca = AtrapaNadzorcy(dziala=True, panel="postoj", powod_panelu="port 19199 zajęty")
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca}, zapytaj_http=lambda url, czas: None)
    with pytest.raises(instalator.BladInstalacji, match="kod 78: port 19199 zajęty"):
        instalator.czekaj_na_panel(u, ot, lambda t: None)
    assert ot.zegar() < 5                                    # od razu, bez czekania na limit
    nadzorca.dziala = False
    with pytest.raises(instalator.BladInstalacji, match="serwis Jarva nie działa"):
        instalator.czekaj_na_panel(u, ot, lambda t: None)
    nadzorca.dziala, nadzorca.panel = True, "dziala"
    log: list[str] = []
    with pytest.raises(instalator.BladInstalacji, match="nie odpowiada po 180 s"):
        instalator.czekaj_na_panel(u, ot, log.append)
    assert "    czekam na panel… 15 s" in log


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
    assert auto.env is ot.env                                    # przyrostek nazwy i środowisko usługi z instalacji
    assert "Autostart: włączony (zadanie Harmonogramu Jarvo)" in capsys.readouterr().out
    assert cli.main(["autostart", "off"], otoczenie=ot) == 0
    assert [w[0] for w in auto.wywolania] == ["wlacz", "wylacz"]
    assert cli.main(["autostart", "status"], otoczenie=ot) == 0
    assert "Autostart: wyłączony" in capsys.readouterr().out
    pusty = _ot(tmp_path / "inny", moduly={"autostart": auto})
    assert cli.main(["autostart", "on"], otoczenie=pusty) == 1 and len(auto.wywolania) == 2
    auto.blad = "Brak usług systemd użytkownika: `systemctl --user` nie odpowiada"
    assert cli.main(["autostart", "on"], otoczenie=ot) == 1
    err = capsys.readouterr().err
    assert "BŁĄD: Brak usług systemd użytkownika" in err and "Rada:" in err and "Traceback" not in err


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
    # zajęty port panelu bez serwisu Jarva: błąd z radą JARVO_PANEL_PORT
    ot.zapytaj_http = lambda url, czas: None
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
        s.listen()
        wyniki = {w["nazwa"]: w for w in cli.sprawdz_porty(u, ot, None)}
    panel = wyniki[f"port {port} (panel)"]
    assert panel["stan"] == "blad" and "JARVO_PANEL_PORT" in panel["rada"]


def test_doctor_miejsce_zajete_i_wolne(tmp_path):
    """`jarvo doctor` „wolne miejsce”: ile zajmuje Jarvo (części korzenia) i ile jest wolnego; poniżej 10 GB uwaga
    z tym, ile zajmą narzędzia przy pierwszym użyciu (z manifestu), poniżej 2 GB błąd. Przed instalacją: potrzeba
    z manifestu tego kodu, a za mało miejsca to błąd z radą (JARVO_ROOT na innym dysku), bez zakładania korzenia."""
    gb = instalator.GB
    u = _zainstalowane(tmp_path)
    with open(u.cache / "kolo.bin", "wb") as f:
        f.truncate(20 * 10 ** 6)
    w = instalator.sprawdz_miejsce(u, _ot(tmp_path, wolne_miejsce=lambda p: 50 * gb))
    assert w["nazwa"] == "wolne miejsce" and w["stan"] == "ok", w
    assert re.fullmatch(r"Jarvo zajmuje 0,02 GB \(cache 0,02\); wolne 50,0 GB na dysku .+", w["opis"]), w["opis"]
    w = instalator.sprawdz_miejsce(u, _ot(tmp_path, wolne_miejsce=lambda p: 5 * gb))
    assert w["stan"] == "uwaga" and re.search(r"przy pierwszym użyciu .+ zajmą jeszcze ok\. [\d,]+ GB", w["rada"])
    w = instalator.sprawdz_miejsce(u, _ot(tmp_path, wolne_miejsce=lambda p: gb))
    assert w["stan"] == "blad" and "zwolnij miejsce na dysku" in w["rada"]
    d = cli.sprawdz_miejsce(u)                                              # prawdziwy dysk testów
    assert d["nazwa"] == "wolne miejsce" and "Jarvo zajmuje" in d["opis"] and "GB na dysku" in d["opis"]
    nowy = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "nowy")})
    w = instalator.sprawdz_miejsce(nowy, _ot(tmp_path, wolne_miejsce=lambda p: gb))
    assert w["stan"] == "blad" and re.search(r"instalacja potrzebuje ok\. [\d,]+ GB \(po sprzątaniu", w["opis"])
    assert "JARVO_ROOT" in w["rada"] and "Niczego nie zainstalowałem" not in w["rada"] and not nowy.root.exists()
    assert instalator.sprawdz_miejsce(nowy, _ot(tmp_path, wolne_miejsce=lambda p: 500 * gb))["stan"] == "ok"


def test_doctor_porty_po_pid_uslug_nadzorcy(tmp_path):
    """Przy działającym serwisie zajęty port to Jarvo tylko wtedy, gdy słucha proces którejś usługi nadzorcy (PID
    albo dziecko launchera venvu); panel rozpoznaje /api/status. Cudzy proces to uwaga z nazwą programu."""
    u = _zainstalowane(tmp_path)
    port = wolny_port()
    nadzorca = AtrapaNadzorcy(dziala=True)
    stan = nadzorca.status()
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca}, port=port, zapytaj_http=lambda url, czas: None,
             sluchacz=lambda p: (112, "python.exe"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
        s.listen()
        assert {w["nazwa"]: w for w in cli.sprawdz_porty(u, ot, stan)}[f"port {port} (panel)"]["opis"] == \
            "używa go Jarvo (python.exe, PID 112)"
        ot.sluchacz = lambda p: (999, "obcy.exe")
        wynik = {w["nazwa"]: w for w in cli.sprawdz_porty(u, ot, stan)}[f"port {port} (panel)"]
        assert wynik["stan"] == "uwaga" and "obcy.exe (PID 999), nie przez usługę Jarva" in wynik["opis"]
        ot.zapytaj_http = http_panelu(u)
        assert {w["nazwa"]: w for w in cli.sprawdz_porty(u, ot, stan)}[f"port {port} (panel)"]["opis"] == \
            "panel Jarva"


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


@pytest.mark.windows_only
def test_programy_tylko_z_pelnej_sciezki_nie_z_katalogu_biezacego(tmp_path, monkeypatch):
    """shutil.which na Windows bez NoDefaultCurrentDirectoryInExePath zagląda najpierw do katalogu bieżącego (także
    z podanym path=): doctor sprawdza pliki narzędzi wprost, programy systemu woła z System32, a gita bierze tylko
    z pełną ścieżką."""
    obcy = tmp_path / "cwd"
    obcy.mkdir()
    (obcy / "uv.exe").write_bytes(b"MZ obcy")
    monkeypatch.chdir(obcy)
    monkeypatch.delenv("NoDefaultCurrentDirectoryInExePath", raising=False)
    assert cli._bin({}, "uv", "uv") is None
    assert cli._bin({"uv": {"bin": [str(tmp_path / "nie-ma")]}}, "uv", "uv") is None
    assert cli._bin({"uv": {"bin": ["."], "katalog": "."}}, "uv", "uv") is None      # katalog względny: pomijamy
    prawdziwy = tmp_path / "uv-kat"
    prawdziwy.mkdir()
    (prawdziwy / "uv.exe").write_bytes(b"MZ")
    assert cli._bin({"uv": {"bin": [str(prawdziwy)]}}, "uv", "uv") == prawdziwy / "uv.exe"
    for program in ("netstat", "tasklist"):
        assert instalator.systemowy(program).lower().endswith(f"\\system32\\{program}.exe")
    assert instalator.program_bezwzgledny(instalator.Otoczenie(program=lambda n: "git.exe"), "git") is None
    assert instalator.program_bezwzgledny(instalator.Otoczenie(program=lambda n: r"C:\Git\cmd\git.exe"), "git") \
        == r"C:\Git\cmd\git.exe"


def test_przygotuj_proces_na_starcie(monkeypatch):
    monkeypatch.setenv("NoDefaultCurrentDirectoryInExePath", "0")
    monkeypatch.delenv("NoDefaultCurrentDirectoryInExePath")
    cli._przygotuj_proces()
    assert os.environ.get("NoDefaultCurrentDirectoryInExePath") == ("1" if WINDOWS else None)


def test_bez_konsoli_wyjscie_i_bledy_do_logu_startu(tmp_path):
    """pythonw.exe z Harmonogramu nie ma stdout ani stderr: komunikaty i błędy startu `jarvo` idą do
    <logi>/serwis-start.log (z nagłówkiem: czas, PID, polecenie), a nie giną. Tu proces z sys.stdout = None."""
    root = tmp_path / "root"
    root.mkdir()
    kod = (f"import sys\nsys.path.insert(0, {str(REPO)!r})\nfrom jarvo import cli\n"
           "sys.stdout = sys.stderr = None\n"
           f"raise SystemExit(cli.main(['--korzen', {str(root)!r}, 'nieznane-polecenie']))\n")
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", kod], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 2 and not r.stdout and not r.stderr
    log = (root / "logi" / "serwis-start.log").read_text(encoding="utf-8")
    assert "bez konsoli" in log and "nieznane-polecenie" in log and "błąd:" in log
    zapis = cli._LogBledow(tmp_path / "nowy" / "x.log", ["serwis"])
    assert zapis.write("") == 0 and not (tmp_path / "nowy").exists()          # plik dopiero przy pierwszym zapisie
    zapis.write("Serwis Jarva jest zatrzymany\n")
    zapis.close()
    tekst = (tmp_path / "nowy" / "x.log").read_text(encoding="utf-8")
    assert "jarvo serwis" in tekst and "Serwis Jarva jest zatrzymany" in tekst


def test_wywolaj_pomija_argumenty_ktorych_funkcja_nie_zna():
    def stara(u, argv, *, start=True):
        return ("stara", start)

    def nowa(u, argv, *, start=True, env=None):
        return ("nowa", start, env)

    def dowolna(u, **kw):
        return ("dowolna", kw)
    assert instalator.wywolaj(stara, 1, 2, start=False, env={"A": "1"}) == ("stara", False)
    assert instalator.wywolaj(nowa, 1, 2, start=False, env={"A": "1"}) == ("nowa", False, {"A": "1"})
    assert instalator.wywolaj(dowolna, 1, env={"A": "1"}, powod="x") == ("dowolna", {"env": {"A": "1"}, "powod": "x"})


def test_env_floty_bez_sekretow_i_zmiennych_obcych():
    env = {"PATH": "/bin", "JARVO_ROOT": "/j", "JARVO_TOKEN": "t", "jarvo_token": "t", "OPENAI_API_KEY": "k",
           "SSH_AUTH_SOCK": "/s", "PIP_INDEX_URL": "https://u:haslo@x", "UV_INDEX_URL": "https://y",
           "HERMES_HOME": "/obcy", "PYTHONPATH": "/x", "XAUTHORITY": "/x/.Xauthority", "LANG": "pl_PL.UTF-8"}
    assert instalator.env_floty(env) == {"PATH": "/bin", "JARVO_ROOT": "/j", "XAUTHORITY": "/x/.Xauthority",
                                         "LANG": "pl_PL.UTF-8"}


# ---------------------------------------------------------------- instalator

HERMES_PIN = {"repo": "https://github.com/NousResearch/hermes-agent", "tag": "v2026.9.24", "commit": PIN,
              "wersja": "0.21.5", "dodatki": ["all"]}


def _aplikacja(tmp_path: Path, adres: str, www: Path, nazwa: str = "app", sha: str = SHA_JARVA,
               commit: str = PIN) -> Path:
    """Kod Jarva z manifestem atrap: uv, python313 i python312 z serwera 127.0.0.1 (ten sam plik na 5 platform)
    i pinem Hermesa `commit`."""
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
    (app / "vendor" / "natywne.lock.json").write_text(json.dumps({"version": 1, "hermes": {**HERMES_PIN,
                                                                                         "commit": commit},
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
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    s = {"www": www, "adres": adres, "dom": dom, "nadzorca": nadzorca, "hermes": AtrapaHermesa(),
         "autostart": AtrapaAutostartu(nadzorca), "zmiany": AtrapaZmian(), "rejestr": RejestrAtrapa(), "w_tle": [],
         "env_w_tle": [], "log": [], "moduly": {}, "env": {}, "u": u, "git": git, "flota": AtrapaFloty()}

    def w_tle(argv, env, log):
        s["w_tle"].append(argv)
        s["env_w_tle"].append(env)
        nadzorca.dziala = True
        return 4242

    def otoczenie(**kw):
        opcje = dict(rejestr=s["rejestr"], program=lambda n: str(git) if n == "git" else None, uruchom_w_tle=w_tle,
                     zapytaj_http=http_panelu(u, lambda: s["nadzorca"].dziala))
        opcje.update(kw)
        moduly = {"hermes": s["hermes"], "nadzorca": s["nadzorca"], "autostart": s["autostart"],
                  "zmiany_hosta": s["zmiany"], "flota": s["flota"], **s["moduly"]}
        return _ot(tmp_path, moduly=moduly, env={"PATH": atrapy.sciezka(tmp_path / "narz", reszta=False),
                                                 "SHELL": "/bin/bash", **s["env"]}, **opcje)
    s["otoczenie"] = otoczenie
    return s


def _instaluj(s, app, **kw) -> int:
    s["log"].clear()
    return instalator.instaluj(s["u"], app, log=s["log"].append, otoczenie=s["otoczenie"](), **kw)


def _migawka(katalog: Path) -> dict[str, bytes]:
    return {str(p.relative_to(katalog)): p.read_bytes() for p in sorted(katalog.rglob("*"))
            if p.is_file() and p.name != "instalacja.log"}


KROKI = ("Sprawdzenie komputera", "Katalogi", "uv", "Python 3.13", "Python 3.12", "Spis narzędzi", "Wersja Jarva",
         "Hermes", "Front panelu", "Bezpieczne ustawienia Hermesa", "Klucz API bramy", "Przełączenie wersji",
         "Programy floty", "Flota", "Środowisko procesów", "Polecenie jarvo", "Autostart", "Serwis", "Panel")


def test_instaluj_na_atrapach_i_drugi_przebieg_niczego_nie_zmienia(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    assert _instaluj(s, app) == 0, "\n".join(s["log"])
    log = "\n".join(s["log"])
    for i, krok in enumerate(KROKI, 1):
        assert re.search(rf"\[[#-]+\] +{i}/{len(KROKI)}  {re.escape(krok)}$", log, re.M), krok
    assert "Panel: http://127.0.0.1:19199/" in log and "serwis uruchomiony przez autostart" in log
    assert "panel Jarva odpowiada" in log
    narz = srodowisko.narzedzia(u)
    assert set(narz) == {"uv", "python313", "python312"}
    assert Path(narz["python313"]["katalog"]) == u.program / "narzedzia" / "python313" / "3.13.17"
    assert narz["uv"]["bin"] == [str(u.program / "narzedzia" / "uv" / "0.12.13")]
    biez = srodowisko.biezace(u)
    assert biez["app"] == os.path.abspath(app) and biez["wersja"] == SHA_JARVA[:12]
    assert biez["hermes"] == str(u.program / "hermes" / PIN[:12])
    assert biez["web_dist"] == str(u.program / "hermes" / PIN[:12] / "hermes_cli" / "web_dist")
    assert not (u.program / "current.poprzedni.json").exists()
    assert json.loads((u.stan / "srodowisko.json").read_text(encoding="utf-8"))["HERMES_HOME"] == str(u.dane)
    h = s["hermes"].wywolania
    assert h[0][0] == "zainstaluj" and h[0][1] == PIN and h[0][2].name.startswith("git")
    assert h[0][3].parent == u.program / "narzedzia" / "uv" / "0.12.13" and h[0][4].is_file()
    assert ("web_dist", "buduje", PIN[:12]) in h
    assert ("konfiguracja", str(u.dane), "1", os.path.abspath(app)) in h      # środowisko NOWEJ wersji
    argv = s["autostart"].argv
    assert argv[-3:] == ["--korzen", str(u.root), "serwis"]
    assert argv[0].endswith("pythonw.exe" if WINDOWS else "python3")
    # rejestracja bez startu, potem start tym samym mechanizmem (krok „Serwis”); bez procesu obok zadania
    assert s["autostart"].wywolania == [("wlacz", False), ("wlacz", True)] and not s["w_tle"]
    assert s["autostart"].env["JARVO_ROOT"] == str(u.root)
    rodzaje = [w["rodzaj"] for w in s["zmiany"].lista]
    if WINDOWS:
        cmd = u.root / "bin" / "jarvo.cmd"
        tekst = cmd.read_bytes()
        assert tekst.isascii() and b"\r\n" in tekst and b" -I -X utf8 " in tekst and b"%*" in tekst
        assert os.path.join(os.path.abspath(app), "jarvo", "start.py").encode() in tekst
        assert f'--korzen "{u.root}" %*'.encode() in tekst
        assert s["rejestr"].czytaj("Environment", "Path") == (rf"C:\Narzedzia;%USERPROFILE%\bin;{u.root / 'bin'}", 2)
        assert s["rejestr"].ogloszenia == 1 and rodzaje == ["plik", "path-uzytkownika"]
    else:
        sh = s["dom"] / ".local" / "bin" / "jarvo"
        assert os.access(sh, os.X_OK) and "exec " in sh.read_text(encoding="utf-8")
        profil = instalator.plik_rc(s["dom"], "/bin/bash", sciezki.MACOS).read_text(encoding="utf-8")
        assert profil.count("# >>> jarvo >>>") == 1 and ".local/bin" in profil
        assert rodzaje == ["plik", "blok-rc"]
    assert re.search(r"^Polecenia: jarvo panel, jarvo status, jarvo doctor, jarvo chat \(.+\)\.$", log, re.M)
    # flota po przełączeniu wersji, w środowisku nowej wersji; panel wstał po niej, więc potwierdza odcisk wtyczek
    f = s["flota"].wywolania
    assert len(f) == 1 and f[0]["biez"]["wersja"] == SHA_JARVA[:12] and f[0]["env"]["HERMES_HOME"] == str(u.dane)
    assert s["flota"].potwierdzenia == ["0123456789abcdef"] and "flota" in log
    # klucz API bramy (H05) w <dane>/.env, port domyślny; sam klucz nie trafia do dziennika
    env_hosta = instalator.czytaj_env(u.dane / ".env")
    assert re.fullmatch(r"[0-9a-f]{64}", env_hosta["API_SERVER_KEY"]) and env_hosta["API_SERVER_PORT"] == "8642"
    assert env_hosta["API_SERVER_KEY"] not in log
    assert env_hosta["API_SERVER_KEY"] not in (u.logi / "instalacja.log").read_text(encoding="utf-8")
    # drugi przebieg: nic nowego w plikach, dzienniku, PATH ani procesach; serwis działa dalej, front gotowy
    przed = (_migawka(u.root), _migawka(s["dom"]), len(s["zmiany"].lista), list(s["rejestr"].zapisy))
    assert _instaluj(s, app) == 0, "\n".join(s["log"])
    assert "Gotowe. Zmiany w tym przebiegu: brak." in s["log"]
    assert (_migawka(u.root), _migawka(s["dom"]), len(s["zmiany"].lista), s["rejestr"].zapisy) == przed
    assert not s["w_tle"] and s["nadzorca"].zatrzymania == 0 and "    serwis działa" in s["log"]
    assert s["nadzorca"].restarty == [] and s["flota"].potwierdzenia == ["0123456789abcdef"]
    assert [w for w in s["hermes"].wywolania if w[0] == "web_dist"] == [("web_dist", "buduje", PIN[:12]),
                                                                         ("web_dist", "gotowy", PIN[:12])]
    assert s["autostart"].wywolania[2:] == [("wlacz", False)]
    assert (u.logi / "instalacja.log").read_text(encoding="utf-8").count("Jarvo natywnie: instalacja w") == 2


def test_instaluj_nowa_wersja_obok_starej_i_restart_serwisu(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    stara = _aplikacja(tmp_path, s["adres"], s["www"])
    assert _instaluj(s, stara) == 0
    nowa = _aplikacja(tmp_path, s["adres"], s["www"], nazwa="app2", sha="a" * 40)
    assert _instaluj(s, nowa) == 0, "\n".join(s["log"])
    assert srodowisko.biezace(u)["app"] == os.path.abspath(nowa) and srodowisko.biezace(u)["wersja"] == "a" * 12
    poprzedni = json.loads((u.program / "current.poprzedni.json").read_text(encoding="utf-8"))
    assert poprzedni["app"] == os.path.abspath(stara)
    assert s["nadzorca"].zatrzymania == 1 and s["nadzorca"].dziala            # stary zatrzymany, nowy z autostartu
    assert s["nadzorca"].stopy[0]["powod"] == "aktualizacja Jarva"
    assert "zatrzymuję serwis poprzedniej wersji" in "\n".join(s["log"])
    assert s["autostart"].argv[4] == os.path.join(os.path.abspath(nowa), "jarvo", "start.py")
    assert not (u.stan / "zatrzymany.json").exists() and ("zdejmij",) in s["nadzorca"].znaczniki
    polecenie = (u.root / "bin" / "jarvo.cmd") if WINDOWS else (s["dom"] / ".local" / "bin" / "jarvo")
    assert "app2" in polecenie.read_text(encoding="utf-8")


def test_nieudana_aktualizacja_zostawia_dzialajaca_stara_wersje(tmp_path, stanowisko):
    """current.json przełącza się dopiero po udanym Hermesie, froncie i konfiguracji: błąd w nich nie zatrzymuje
    serwisu, a działająca wersja zostaje w current.json."""
    s, u = stanowisko, stanowisko["u"]
    stara = _aplikacja(tmp_path, s["adres"], s["www"])
    assert _instaluj(s, stara) == 0
    przed = srodowisko.biezace(u)
    nowa = _aplikacja(tmp_path, s["adres"], s["www"], nazwa="app2", sha="a" * 40, commit="b" * 40)
    s["hermes"].blad_konfiguracji = "config set security.tirith_enabled: odmowa"
    assert _instaluj(s, nowa) == 1
    assert "BŁĄD w kroku „Bezpieczne ustawienia Hermesa”" in "\n".join(s["log"])
    s["hermes"].blad_konfiguracji = None
    s["hermes"].blad_web = "npm run build w web nie przeszedł (kod 1)"
    trzecia = _aplikacja(tmp_path, s["adres"], s["www"], nazwa="app3", sha="c" * 40, commit="c" * 40)
    ot_z_npm = s["otoczenie"](program=lambda n: str(s["git"]) if n in ("git", "npm") else None)
    log: list[str] = []
    assert instalator.instaluj(u, trzecia, log=log.append, otoczenie=ot_z_npm) == 1
    assert "BŁĄD w kroku „Front panelu”: npm run build" in "\n".join(log)      # npm jest: zostaje błąd npm
    assert srodowisko.biezace(u) == przed and not (u.program / "current.poprzedni.json").exists()
    assert s["nadzorca"].dziala and s["nadzorca"].zatrzymania == 0 and not (u.stan / "zatrzymany.json").exists()
    assert (u.program / "hermes" / ("b" * 12)).is_dir()                         # nowa wersja obok, gotowa na ponowienie


def test_ponowienie_po_przerwanej_aktualizacji_uruchamia_nowa_wersje(tmp_path, stanowisko):
    """Aktualizacja przerwana po przełączeniu (tu: zapis polecenia jarvo): serwis stoi, znacznik zdjęty, więc
    zapasowy wyzwalacz Harmonogramu może podnieść go ze STARYM poleceniem. Ponowienie przerejestrowuje autostart
    i uruchamia działający serwis od nowa, więc rusza kod z current.json."""
    s, u = stanowisko, stanowisko["u"]
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"])) == 0
    nowa = _aplikacja(tmp_path, s["adres"], s["www"], nazwa="app2", sha="a" * 40)
    s["zmiany"].blad_pliku = "Brak miejsca na dysku"
    assert _instaluj(s, nowa) == 1
    log = "\n".join(s["log"])
    assert "BŁĄD w kroku „Polecenie jarvo”: Brak miejsca na dysku" in log and "Serwis Jarva stoi" in log
    assert srodowisko.biezace(u)["app"] == os.path.abspath(nowa) and not s["nadzorca"].dziala
    assert not (u.stan / "zatrzymany.json").exists()                          # to nie `jarvo down`
    s["nadzorca"].dziala = True                                               # zapasowy wyzwalacz, stare polecenie
    assert s["autostart"].argv[4] != os.path.join(os.path.abspath(nowa), "jarvo", "start.py")
    s["zmiany"].blad_pliku = None
    assert _instaluj(s, nowa) == 0, "\n".join(s["log"])
    assert "uruchamiam go od nowa" in "\n".join(s["log"]) and s["nadzorca"].zatrzymania == 2
    assert s["nadzorca"].dziala and s["autostart"].argv[4] == os.path.join(os.path.abspath(nowa), "jarvo", "start.py")


def test_front_zawsze_z_checkoutu_biezacego_pinu(tmp_path, stanowisko):
    """Po zmianie pinu Hermesa front pochodzi z nowego checkoutu (stary web_dist leży obok, ale nie zostaje w
    current.json); --web-lokalnie buduje go od nowa także wtedy, gdy jest gotowy."""
    s, u = stanowisko, stanowisko["u"]
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"])) == 0
    nowa = _aplikacja(tmp_path, s["adres"], s["www"], nazwa="app2", sha="a" * 40, commit="b" * 40)
    assert _instaluj(s, nowa) == 0, "\n".join(s["log"])
    biez = srodowisko.biezace(u)
    assert biez["hermes"] == str(u.program / "hermes" / ("b" * 12))
    assert biez["web_dist"] == str(u.program / "hermes" / ("b" * 12) / "hermes_cli" / "web_dist")
    assert (u.program / "hermes" / PIN[:12] / "hermes_cli" / "web_dist" / "index.html").is_file()   # stary obok
    assert _instaluj(s, nowa, web_lokalnie=True) == 0
    budowy = [w for w in s["hermes"].wywolania if w[:2] == ("web_dist", "buduje")]
    assert budowy == [("web_dist", "buduje", PIN[:12]), ("web_dist", "buduje", "b" * 12),
                      ("web_dist", "buduje", "b" * 12)]


def test_nowa_definicja_autostartu_restartuje_dzialajacy_serwis(tmp_path, stanowisko):
    """Ten sam kod, ale inne polecenie autostartu (np. nowy Python 3.13): działający serwis ma stare polecenie,
    więc startuje od nowa przez autostart."""
    s = stanowisko
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    assert _instaluj(s, app) == 0
    s["autostart"].argv = ["stare", "polecenie"]
    assert _instaluj(s, app) == 0, "\n".join(s["log"])
    assert "uruchamiam go od nowa" in "\n".join(s["log"]) and s["nadzorca"].zatrzymania == 1
    assert s["nadzorca"].dziala and s["autostart"].wywolania[-2:] == [("wlacz", False), ("wlacz", True)]


def test_macos_nowy_plist_wyladowuje_stara_definicje(tmp_path, stanowisko):
    """macOS: launchd trzyma wczytaną definicję, a kickstart uruchomiłby starą. Nowy plist: działający serwis
    zatrzymany kanałem, agent wyładowany (wylacz), plist zapisany bez wczytania, a krok „Serwis” go wczytuje."""
    s = stanowisko
    s["autostart"] = AtrapaAutostartu(s["nadzorca"], mechanizm="launchagent")
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    assert _instaluj(s, app) == 0, "\n".join(s["log"])
    s["autostart"].argv = ["stary", "plist"]
    s["autostart"].wywolania.clear()
    assert _instaluj(s, app) == 0, "\n".join(s["log"])
    log = "\n".join(s["log"])
    assert "nowa definicja LaunchAgenta: zatrzymuję serwis" in log and s["nadzorca"].zatrzymania == 1
    assert s["autostart"].wywolania == [("wlacz", False), ("wylacz",), ("wlacz", False), ("wlacz", True)]
    assert s["nadzorca"].dziala and not (s["u"].stan / "zatrzymany.json").exists()


def test_blad_autostartu_nie_przerywa_instalacji(tmp_path, stanowisko):
    """Brak user busa systemd (WSL, kontener, su) albo sesji GUI na macOS: uwaga z radą, serwis startuje wprost."""
    s = stanowisko
    s["autostart"] = AtrapaAutostartu(s["nadzorca"], blad="Brak usług systemd użytkownika: `systemctl --user` "
                                                          "nie odpowiada")
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"])) == 0, "\n".join(s["log"])
    log = "\n".join(s["log"])
    assert "autostart nie włączony: Brak usług systemd" in log
    assert "Uwaga: autostart nie działa (Brak usług systemd" in log and "Serwis uruchamiam bezpośrednio" in log
    assert "JARVO_NO_AUTOSTART=1" in log and "--bez-autostartu" in log
    assert len(s["w_tle"]) == 1 and "serwis uruchomiony w tle (PID 4242)" in log and "Panel: http" in log


def test_brak_node_jasna_rada(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    s["hermes"].blad_web = "Nie znalazłem programu npm."
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"])) == 1
    log = "\n".join(s["log"])
    assert "BŁĄD w kroku „Front panelu”" in log and "Node.js 24 LTS" in log and "https://nodejs.org" in log
    assert "jeszcze raz" in log and srodowisko.biezace(u) == {}                # current.json nie powstał


def test_caly_korzen_tylko_dla_wlasciciela(tmp_path, stanowisko):
    """Korzeń (z program, bin, logi i cache) tylko dla właściciela: na innym dysku dziedziczyłby ACL dysku z zapisem
    dla Użytkowników uwierzytelnionych, a autostart uruchamia kod z `<program>` jako właściciel."""
    s = stanowisko
    dysk = tmp_path / "dysk"
    dysk.mkdir()
    icacls = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "icacls.exe")
    if WINDOWS:
        # jak D:\ właściciela: Użytkownicy uwierzytelnieni (S-1-5-11) mogą zmieniać, wpisy dziedziczone zwykłym
        # mechanizmem (katalog testu pytest zakłada przez mkdir(0o700), z DACL bez auto-dziedziczenia, więc jego
        # dzieci dostają kopie wpisów jako jawne i nie nadają się do tej próby)
        kto = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}"
        subprocess.run([icacls, str(dysk), "/inheritance:r", "/grant:r", "*S-1-5-11:(OI)(CI)M", f"{kto}:(OI)(CI)F"],
                       check=True, capture_output=True)
    u = s["u"] = sciezki.uklad({"JARVO_ROOT": str(dysk / "Jarvo")})
    s["env"]["JARVO_ROOT"] = str(u.root)
    sprzed = u.program / "app" / "kod-z-bootstrapu.py"                        # plik sprzed instalatora w Pythonie
    sprzed.parent.mkdir(parents=True)
    sprzed.write_text("# kod\n", encoding="utf-8")
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"]), start=False, autostart=False) == 0, \
        "\n".join(s["log"])
    plik = u.program / "narzedzia" / "uv" / "0.12.13" / ".jarvo-suma"
    if WINDOWS:
        for p, wpis in ((u.root, "(OI)(CI)(F)"), (plik, "(I)(F)"), (sprzed, "(I)(F)"), (u.root / "bin", "(I)")):
            wyj = subprocess.run([icacls, str(p)], capture_output=True, text=True, encoding="utf-8",
                                 errors="replace").stdout
            assert wyj.count(":(") == 1 and wpis in wyj, wyj                  # jeden wpis: właściciel
            assert os.environ["USERNAME"].casefold() in wyj.casefold()
    else:
        assert stat.S_IMODE(u.root.stat().st_mode) == 0o700


def test_korzen_musi_byc_osobnym_katalogiem(tmp_path, stanowisko):
    def uklad(root: Path) -> sciezki.Uklad:
        return sciezki.Uklad(root=root, program=root / "program", dane=root / "dane", stan=root / "stan",
                             logi=root / "logi", cache=root / "cache", build=root / "build")
    assert "katalog główny dysku" in instalator.korzen_nieosobny(uklad(Path(tmp_path.anchor)))
    assert "katalog domowy" in instalator.korzen_nieosobny(uklad(Path.home()))
    zdjecia = tmp_path / "zdjecia"
    (zdjecia / "program").mkdir(parents=True)
    (zdjecia / "wakacje.jpg").write_bytes(b"jpg")
    (zdjecia / "desktop.ini").write_text("", encoding="utf-8")
    assert "pliki spoza Jarva: wakacje.jpg" in instalator.korzen_nieosobny(uklad(zdjecia))
    (zdjecia / "wakacje.jpg").unlink()
    assert instalator.korzen_nieosobny(uklad(zdjecia)) is None
    assert instalator.korzen_nieosobny(uklad(tmp_path / "nie-ma")) is None
    # kopia `jarvo migruj` w korzeniu to katalog Jarva: aktualizacja po migracji nie może jej uznać za obcy plik
    from jarvo import migracja
    (zdjecia / migracja.KATALOG / "kopia-zapasowa").mkdir(parents=True)
    assert instalator.korzen_nieosobny(uklad(zdjecia)) is None
    s, u = stanowisko, stanowisko["u"]
    u.root.mkdir(parents=True)
    (u.root / "dokument.docx").write_bytes(b"x")
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"])) == 1
    log = "\n".join(s["log"])
    assert "BŁĄD w kroku „Sprawdzenie komputera”" in log and "osobnego katalogu" in log and "JARVO_ROOT" in log
    assert not u.program.exists()


def test_srodowisko_json_tylko_czesc_jarva_i_ustawienia_instalacji(tmp_path, stanowisko, capsys):
    """srodowisko.json nie zawiera PATH właściciela ani przełączników bootstrapu (drugi przebieg z innego okna niczego
    nie zmienia), a JARVO_PANEL_PORT pamięta <stan>/ustawienia.json: zadanie Harmonogramu nie zna zmiennych sesji."""
    s, u = stanowisko, stanowisko["u"]
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    s["env"] = {"JARVO_PANEL_PORT": "19157", "JARVO_BEZ_PATH": "1", "JARVO_REF": "main"}
    assert _instaluj(s, app, start=False) == 0
    zapis = json.loads((u.stan / "srodowisko.json").read_text(encoding="utf-8"))
    assert str(tmp_path / "narz") not in zapis["PATH"] and "JARVO_BEZ_PATH" not in zapis and "JARVO_REF" not in zapis
    assert zapis["JARVO_PANEL_PORT"] == "19157" and str(u.bin_floty) in zapis["PATH"]
    assert json.loads((u.stan / "ustawienia.json").read_text(encoding="utf-8")) == {"JARVO_PANEL_PORT": "19157"}
    s["env"] = {"JARVO_PANEL_PORT": "19157", "PATH": os.pathsep.join([str(tmp_path / "inne"), str(tmp_path / "narz")])}
    assert _instaluj(s, app, start=False) == 0 and "Gotowe. Zmiany w tym przebiegu: brak." in s["log"]
    ot = s["otoczenie"]()
    ot.env.pop("JARVO_PANEL_PORT")
    assert cli.main(["status", "--json"], otoczenie=ot) == 1
    assert json.loads(capsys.readouterr().out)["panel"] == "http://127.0.0.1:19157/"
    s["env"] = {"JARVO_PANEL_PORT": "zły"}
    assert _instaluj(s, app, start=False) == 1 and "JARVO_PANEL_PORT='zły'" in "\n".join(s["log"])


def test_instaluj_zdejmuje_znacznik_i_nie_przekazuje_sekretow(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    s["env"] = {"JARVO_TOKEN": "tajny-klucz", "GITHUB_TOKEN": "ghp_x", "ANTHROPIC_API_KEY": "sk-x"}
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    assert _instaluj(s, app, start=False, autostart=False) == 0
    s["nadzorca"].oznacz_zatrzymanie(u, "jarvo down")                         # właściciel zatrzymał flotę
    assert _instaluj(s, app, autostart=False) == 0, "\n".join(s["log"])
    assert not (u.stan / "zatrzymany.json").exists() and ("zdejmij",) in s["nadzorca"].znaczniki
    assert len(s["w_tle"]) == 1 and s["w_tle"][0][-1] == "serwis"
    env = s["env_w_tle"][0]
    assert not {"JARVO_TOKEN", "GITHUB_TOKEN", "ANTHROPIC_API_KEY"} & set(env) and env["JARVO_PANEL_PORT"] == "19199"


def test_up_bez_instalacji_instaluje(tmp_path, stanowisko, monkeypatch, capsys):
    """N02: `jarvo up` bez instalacji robi instalację (jak `jarvo instaluj`), potem serwis i panel."""
    s, u = stanowisko, stanowisko["u"]
    monkeypatch.setattr(instalator, "APP", _aplikacja(tmp_path, s["adres"], s["www"]))
    assert cli.main(["up"], otoczenie=s["otoczenie"]()) == 0
    out = capsys.readouterr().out
    assert f"Jarvo nie jest zainstalowane w {u.root}: instaluję" in out and "Jarvo działa. Panel: http" in out
    assert srodowisko.biezace(u)["app"] == os.path.abspath(instalator.APP) and s["nadzorca"].dziala


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
    cel = u.root / "bin" / ("jarvo.cmd" if WINDOWS else "jarvo")
    assert cel.is_file()
    assert [w["rodzaj"] for w in s["zmiany"].lista] == ["plik"] and not s["rejestr"].zapisy
    assert not list(s["dom"].glob(".*profile")) and any("--bez-path" in w for w in s["log"]) == WINDOWS
    assert f"(pełną ścieżką {cel})." in s["log"][-1]


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
    assert _instaluj(s, _aplikacja(tmp_path, s["adres"], s["www"])) == 1     # stara wykryta przez sciezke, bez
    log = "\n".join(s["log"])                                                  # migracji (JARVO_MIGRACJA=nie)
    assert "BŁĄD w kroku „Sprawdzenie komputera”" in log and "JARVO_MIGRACJA=nie" in log
    assert ("JARVO_ROOT" if WINDOWS else "JARVO_BEZ_PATH=1") in log
    assert not (u.program / "narzedzia").exists() and not s["zmiany"].lista and not s["rejestr"].zapisy


class AtrapaMigracji:
    """jarvo/migracja.py dla instalatora: main(argv, uklad=, otoczenie=) z kodem i zapisem wywołań."""
    def __init__(self, kod: int, po=None):
        self.kod, self.po, self.wywolania = kod, po, []

    def main(self, argv, *, uklad, otoczenie):
        self.wywolania.append(list(argv))
        if self.po:
            self.po(uklad)
        return self.kod


def _stara(s, u) -> None:
    """Ślad starej instalacji jak u ludzi: macOS i Linux polecenie ~/.local/bin/jarvo starej floty. Na Windows stara
    zostaje w %LOCALAPPDATA%\\Jarvo, a bootstrap stawia tę obok (Jarvo-natywnie), więc w korzeniu nie ma nic."""
    if not WINDOWS:
        stare = s["dom"] / ".local" / "bin" / "jarvo"
        stare.parent.mkdir(parents=True, exist_ok=True)
        stare.write_text("#!/bin/sh\nexec docker exec jarvo-hermes hermes\n", encoding="utf-8")


def test_instaluj_ze_stara_instalacja_przenosi_dane_przed_startem(tmp_path, stanowisko, monkeypatch):
    s, u = stanowisko, stanowisko["u"]
    _stara(s, u)
    monkeypatch.setattr(instalator.Path, "home", staticmethod(lambda: s["dom"]))

    def po(uklad):                     # jak migracja: stare polecenie usunięte (U4), stan zakończony
        if not WINDOWS:
            (s["dom"] / ".local" / "bin" / "jarvo").unlink()
        uklad.stan.mkdir(parents=True, exist_ok=True)
        (uklad.stan / "migracja.json").write_text(json.dumps({"zakonczona": "2026-10-25T10:00:00"}), encoding="utf-8")
    s["moduly"]["migracja"] = m = AtrapaMigracji(0, po)
    s["env"]["JARVO_YES"] = "1"
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    s["log"].clear()
    kod = instalator.instaluj(u, app, log=s["log"].append, otoczenie=s["otoczenie"](stara=lambda uu, ot: "stara"))
    log = "\n".join(s["log"])
    assert kod == 0, log
    assert m.wywolania == [["--bez-startu", "--z-instalatora", "--tak"]]
    kroki = [m.group(1) for w in s["log"] if (m := re.match(r"\[[#-]+\] +\d+/\d+  (.+)$", w))]
    assert kroki.index("Przeniesienie ze starej instalacji") == kroki.index("Środowisko procesów") + 1
    assert kroki.index("Polecenie jarvo") > kroki.index("Przeniesienie ze starej instalacji")
    assert s["nadzorca"].dziala and "Panel:" in log
    assert instalator.obca_instalacja(u, s["dom"]) is None and instalator.migracja_zakonczona(u)


def test_instaluj_bez_zgody_na_przeniesienie_kod_3_i_stara_flota_zostaje(tmp_path, stanowisko, monkeypatch):
    s, u = stanowisko, stanowisko["u"]
    _stara(s, u)
    monkeypatch.setattr(instalator.Path, "home", staticmethod(lambda: s["dom"]))
    s["moduly"]["migracja"] = m = AtrapaMigracji(3)
    app = _aplikacja(tmp_path, s["adres"], s["www"])
    s["log"].clear()
    kod = instalator.instaluj(u, app, log=s["log"].append, otoczenie=s["otoczenie"](stara=lambda uu, ot: "stara"))
    log = "\n".join(s["log"])
    assert kod == 3 and m.wywolania == [["--bez-startu", "--z-instalatora"]]
    assert "stara flota pracuje dalej" in log and "uruchom to samo polecenie instalacji" in log
    assert not s["nadzorca"].dziala and not s["w_tle"] and not s["autostart"].wywolania
    assert (u.program / "current.json").is_file()                             # wersja natywna gotowa, stoi
    if not WINDOWS:
        assert "docker exec" in (s["dom"] / ".local" / "bin" / "jarvo").read_text(encoding="utf-8")
    s["moduly"]["migracja"] = AtrapaMigracji(1)
    s["log"].clear()
    assert instalator.instaluj(u, app, log=s["log"].append,
                               otoczenie=s["otoczenie"](stara=lambda uu, ot: "stara")) == 1
    assert "przeniesienie danych przerwane" in "\n".join(s["log"])


def test_wykryj_stara_po_migracji_i_z_jarvo_migracja_nie(tmp_path):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    wykrycie = type("W", (), {"jest": True})()
    migracja = type("M", (), {"SystemMigracji": lambda self=None, env=None: None,
                              "wykryj": staticmethod(lambda s, uu: wykrycie)})
    ot = instalator.Otoczenie(modul=lambda n: migracja, env={})
    prawdziwa = WYKRYJ_STARA
    assert prawdziwa(u, ot) is wykrycie
    assert prawdziwa(u, instalator.Otoczenie(modul=lambda n: migracja, env={"JARVO_MIGRACJA": "nie"})) is None
    wykrycie.jest = False
    assert prawdziwa(u, ot) is None
    wykrycie.jest = True
    u.stan.mkdir(parents=True)
    (u.stan / "migracja.json").write_text(json.dumps({"zakonczona": "2026-10-25", "wycofana": None}), encoding="utf-8")
    assert prawdziwa(u, ot) is None
    (u.stan / "migracja.json").write_text(json.dumps({"zakonczona": "2026-10-25", "wycofana": "2026-10-26"}),
                                          encoding="utf-8")
    assert prawdziwa(u, ot) is wykrycie


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
    assert any(instalator.kiedy_dziala_path() in w for w in s["log"])
    assert instalator.plik_rc(dom3, "/bin/zsh", False) == dom3 / ".zprofile"
    assert instalator.plik_rc(dom3, "/bin/bash", True) == dom3 / ".zprofile"
    (dom3 / ".bash_profile").write_text("", encoding="utf-8")
    assert instalator.plik_rc(dom3, "/bin/bash", False) == dom3 / ".bash_profile"


def test_kiedy_dziala_nowy_path():
    """Linux: terminal w GNOME i KDE nie czyta ~/.profile, więc wpis PATH działa dopiero po ponownym zalogowaniu."""
    tekst = instalator.kiedy_dziala_path()
    if WINDOWS:
        assert tekst == "w nowym oknie terminala"
    elif sciezki.MACOS:
        assert tekst == "w nowym oknie Terminala"
    else:
        assert "po ponownym zalogowaniu" in tekst


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


def test_zatrzymaj_serwis_czeka_na_koniec_procesu(tmp_path):
    """Stop kanałem z powodem i limitem z nadzorcy (CZAS_ZATRZYMANIA); starszy nadzorca bez `powod` też działa,
    a „już się zatrzymuje” (wyjątek ze stop) nie jest błędem, gdy proces kończy się w limicie."""
    u = _zainstalowane(tmp_path)
    nowy = AtrapaNadzorcy(dziala=True)
    assert instalator.zatrzymaj_serwis(u, _ot(tmp_path, moduly={"nadzorca": nowy}), "jarvo down") is True
    assert nowy.stopy == [{"czekaj": 120.0, "powod": "jarvo down"}]           # max(CZAS_STOPU, 110 + 10)
    stary = AtrapaNadzorcyBezZnacznika(dziala=True)
    assert instalator.zatrzymaj_serwis(u, _ot(tmp_path, moduly={"nadzorca": stary}), "x") is True
    assert stary.stopy == [{"czekaj": 120.0}]
    assert instalator.zatrzymaj_serwis(u, _ot(tmp_path, moduly={"nadzorca": stary})) is False   # już nie działa

    class Zatrzymujacy(AtrapaNadzorcy):
        def __init__(self):
            super().__init__(dziala=True)
            self.zostalo = 3

        def stop(self, czekaj=0.0, powod=""):
            raise RuntimeError("Nadzorca właśnie się zatrzymuje.")

        def polacz(self, u):
            self.zostalo -= 1
            if self.zostalo <= 0:
                self.dziala = False
            return super().polacz(u)
    assert instalator.zatrzymaj_serwis(u, _ot(tmp_path, moduly={"nadzorca": Zatrzymujacy()})) is True
    wieczny = AtrapaNadzorcy(dziala=True)
    wieczny.stop = lambda czekaj=0.0, powod="": {"ok": True}                  # nie kończy się: limit z radą
    with pytest.raises(instalator.BladInstalacji, match="nie zatrzymał się w 120 s"):
        instalator.zatrzymaj_serwis(u, _ot(tmp_path, moduly={"nadzorca": wieczny}))


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
        # PATH sprzed instalacji wraca bajt w bajt, także z końcowym średnikiem (CI natywnie, windows-2025)
        assert s["rejestr"].czytaj("Environment", "Path")[0] == r"C:\Narzedzia;%USERPROFILE%\bin;"
    # prawdziwy klient nadzorcy bez działającego nadzorcy: status mówi „nie działa”, nic nie startuje; znacznik
    # zatrzymania przez ten moduł (albo plik, gdy moduł go jeszcze nie zna) w tym samym miejscu
    s["moduly"].update({"nadzorca": nadzorca})
    ot = s["otoczenie"]()
    stan, powod = instalator.stan_serwisu(u, ot)
    assert stan is None and powod
    instalator.oznacz_zatrzymanie(u, ot, "próba")
    assert instalator.zatrzymanie(u)["powod"] == "próba"
    instalator.zdejmij_zatrzymanie(u, ot)
    assert instalator.zatrzymanie(u) is None
