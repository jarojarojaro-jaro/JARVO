"""Instalator Windows (install.ps1): składnia, PSScriptAnalyzer i próby na sucho na udawanym Windowsie.

PowerShell 7 z `make dev-pwsh` (.tools/pwsh) albo z PATH; bez niego testy są pomijane. JARVO_TEST_PWSH=powershell
(CI na Windowsie) uruchamia je w Windows PowerShell 5.1, tym samym, którego używa większość ludzi. Próba na sucho
(JARVO_DRY_RUN=1) tylko wypisuje kroki; stan Windowsa udają zmienne JARVO_FAKE_* (WSL, dystrybucje,
kompilacja, procesor, RAM, dysk, folder Autostart).
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "install.ps1"
LOCAL = ROOT / ".tools/pwsh/pwsh"
PWSH = os.environ.get("JARVO_TEST_PWSH") or (str(LOCAL) if LOCAL.exists() else shutil.which("pwsh"))
WINPS = Path(PWSH or "").stem.lower() == "powershell"   # Windows PowerShell 5.1
pytestmark = pytest.mark.skipif(not PWSH, reason="brak pwsh (make dev-pwsh)")
UTF8 = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "


def _ps(command: str, **env) -> subprocess.CompletedProcess:
    return subprocess.run([PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", UTF8 + command],
                          env={**os.environ, **env}, capture_output=True, encoding="utf-8", errors="replace",
                          timeout=180)


def _dry(tmp_path: Path, **fake) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("JARVO_")}
    env.update({"HOME": str(tmp_path), "LANG": "C.UTF-8", "JARVO_DRY_RUN": "1",
                "JARVO_FAKE_BUILD": "22631", "JARVO_FAKE_ARCH": "AMD64", "JARVO_FAKE_RAM_GB": "16",
                "JARVO_FAKE_DISK_GB": "100", "JARVO_FAKE_WSL": "jest", "JARVO_FAKE_STARTUP": str(tmp_path / "Autostart")})
    env.update(fake)
    script = PS1
    if WINPS:   # PowerShell 5.1 czyta plik bez BOM jako ANSI; kopia po restarcie (RunOnce) też ma BOM
        script = tmp_path / "install.ps1"
        script.write_bytes(b"\xef\xbb\xbf" + PS1.read_bytes())
    return subprocess.run([PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
                           f"{UTF8}& '{script}'; exit $LASTEXITCODE"],
                          env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=120)


def test_parses_without_errors():
    r = _ps("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{PS1}', [ref]$null, [ref]$e); $e | ForEach-Object {{ $_.ToString() }}; exit $e.Count")
    assert r.returncode == 0, r.stdout + r.stderr


def test_script_analyzer_clean():
    mods = ROOT / ".tools/psmodules"
    r = _ps("Import-Module PSScriptAnalyzer -ErrorAction Stop; "
            f"$f = Invoke-ScriptAnalyzer -Path '{PS1}' -Settings '{ROOT / 'PSScriptAnalyzerSettings.psd1'}'; "
            "$f | ForEach-Object { \"$($_.RuleName):$($_.Line) $($_.Message)\" }; exit @($f).Count",
            PSModulePath=f"{mods}{os.pathsep}{os.environ.get('PSModulePath', '')}")
    if "PSScriptAnalyzer" in r.stderr and "not loaded" in r.stderr.replace("\n", " "):
        pytest.skip("brak PSScriptAnalyzer (make dev-pwsh)")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("ansi", ["cp1250", "cp1252"])
def test_parses_when_read_as_ansi(tmp_path, ansi):
    """Windows PowerShell 5.1 czyta plik bez BOM w kodowaniu ANSI (polski Windows: cp1250). Np. „ń” (C5 84)
    staje się wtedy „Å„”, a „„” PowerShell traktuje jak cudzysłów: plik pobrany i uruchomiony ręcznie musi się
    i tak sparsować (polskie litery w komunikatach będą wtedy krzaczkami, ale instalacja ruszy)."""
    mangled = tmp_path / "ansi.ps1"
    mangled.write_text(PS1.read_bytes().decode(ansi, errors="replace"), encoding="utf-8-sig")
    r = _ps("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{mangled}', [ref]$null, [ref]$e); $e | ForEach-Object {{ $_.ToString() }}; exit $e.Count")
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_typographic_quotes_in_code():
    """PowerShell traktuje „ ” ‘ ’ jak cudzysłowy, a – — jak minus: w kodzie tylko ASCII, polskie znaki w napisach."""
    for i, line in enumerate(PS1.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        assert not re.search("[“”„‘’–—]", line.split(" # ")[0]), f"{i}: {line}"
        # "$zmienna:" w napisie to błąd składni (zasięg zmiennej); piszemy "${zmienna}:"
        assert not re.search(r"\$(?!env:|script:|global:|using:)[A-Za-z_]\w*:", line), f"{i}: {line}"
    assert not PS1.read_bytes().startswith(b"\xef\xbb\xbf"), "bez BOM: irm | iex w PowerShell 5.1 psuje go"


def test_dry_fresh_windows_installs_wsl_and_resumes_after_restart(tmp_path):
    r = _dry(tmp_path, JARVO_FAKE_WSL="brak", JARVO_FAKE_RAM_GB="8")
    out = r.stdout
    assert r.returncode == 0, out + r.stderr
    assert "wsl.exe --install --no-distribution -Verb RunAs" in out
    assert "RunOnce JarvoInstall = powershell.exe -NoExit -ExecutionPolicy Bypass -File" in out
    assert "WSL dostanie 5 GB RAM" in out   # 8 GB komputera: domyślna połowa to za mało
    assert "Restart-Computer" in out
    assert "wsl.exe --import" not in out   # dystrybucja dopiero po restarcie


def test_dry_wsl_ready_imports_own_distro(tmp_path):
    r = _dry(tmp_path)
    out = r.stdout
    assert r.returncode == 0, out + r.stderr
    assert "ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz" in out and "SHA256SUMS" in out
    assert re.search(r"wsl\.exe --import Jarvo \S+ \S+amd64-wsl\.rootfs\.tar\.gz --version 2", out)
    assert "wsl.exe -d Jarvo -u root -e bash" in out and "wsl.exe --terminate Jarvo" in out
    assert "wsl.exe -d Jarvo -u jarvo --cd ~ -e bash" in out
    assert "Jarvo.vbs" in out and "Start-Process http://localhost:9119/jarvo" in out
    assert out.index("--import") < out.index("-u jarvo --cd")
    assert "RunOnce" not in out and "Docker Desktop" not in out
    # polecenie jarvo w PowerShellu: jarvo.cmd w %LOCALAPPDATA%\Jarvo\bin, dopisany do PATH użytkownika
    assert re.search(r'jarvo\.cmd: wsl\.exe -d Jarvo -u jarvo --cd ~ -e bash -c "export PATH=\$\{PATH\}:\$\{HOME\}/\.local/bin:'
                     r'\$\{HOME\}/jarvo/bin; exec jarvo \\"\$@\\"" jarvo %\*', out)
    assert re.search(r"PATH użytkownika = \S*Jarvo[/\\]bin$", out, re.M) and "Polecenie jarvo w PowerShellu" in out
    assert "polecenia: jarvo help" in out


def test_dry_jarvo_command_keeps_user_path(tmp_path):
    r = _dry(tmp_path, JARVO_FAKE_USER_PATH=r"C:\Narzedzia;%USERPROFILE%\bin")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"PATH użytkownika = C:\\Narzedzia;%USERPROFILE%\\bin;\S*Jarvo[/\\]bin$", r.stdout, re.M)


def test_dry_jarvo_command_already_in_path(tmp_path):
    jarvo_bin = str(tmp_path / "Jarvo" / "bin")
    r = _dry(tmp_path, LOCALAPPDATA=str(tmp_path), JARVO_FAKE_USER_PATH=r"C:\Narzedzia;" + jarvo_bin)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PATH użytkownika" not in r.stdout and "jarvo.cmd: wsl.exe" in r.stdout


def test_dry_existing_distro_command_uses_its_user(tmp_path):
    r = _dry(tmp_path, JARVO_FAKE_DISTROS="Ubuntu", JARVO_FAKE_EXISTING="Ubuntu")
    assert r.returncode == 0 and "jarvo.cmd: wsl.exe -d Ubuntu -u uzytkownik --cd ~" in r.stdout


def test_dry_arm64_uses_arm_rootfs(tmp_path):
    r = _dry(tmp_path, JARVO_FAKE_ARCH="ARM64")
    assert r.returncode == 0 and "ubuntu-noble-wsl-arm64-wsl.rootfs.tar.gz" in r.stdout


def test_dry_existing_install_updates_that_distro(tmp_path):
    r = _dry(tmp_path, JARVO_FAKE_DISTROS="Ubuntu", JARVO_FAKE_EXISTING="Ubuntu")
    out = r.stdout
    assert r.returncode == 0, out + r.stderr
    assert "Jarvo jest już w dystrybucji Ubuntu" in out and "--import" not in out
    # tymczasowe sudo bez hasła (hasło Linuksa to nie hasło Windowsa) i sprzątanie po instalacji
    assert "wsl.exe -d Ubuntu -u root -e sh -c" in out and "visudo -cf" in out
    assert "wsl.exe -d Ubuntu -u root -e rm -f /etc/sudoers.d/zz-jarvo-install" in out
    assert "wsl.exe -d Ubuntu -u uzytkownik --cd ~ -e bash" in out


def test_dry_own_distro_present_is_update(tmp_path):
    r = _dry(tmp_path, JARVO_FAKE_DISTROS="Jarvo,Ubuntu")
    assert r.returncode == 0 and "Dystrybucja Jarvo: jest" in r.stdout and "--import" not in r.stdout


@pytest.mark.parametrize("fake,msg", [
    ({"JARVO_FAKE_BUILD": "18363"}, "Potrzebny Windows 10 w wersji 2004"),
    ({"JARVO_FAKE_RAM_GB": "2"}, "Za mało RAM"),
    ({"JARVO_FAKE_DISK_GB": "8"}, "Za mało miejsca"),
    ({"JARVO_FAKE_ARCH": "x86"}, "Nieobsługiwany procesor"),
])
def test_dry_refuses_unsupported(tmp_path, fake, msg):
    r = _dry(tmp_path, **fake)
    assert r.returncode == 1 and msg in r.stdout, r.stdout + r.stderr
    assert "wsl.exe" not in r.stdout


def test_token_never_printed(tmp_path):
    secret = "github_pat_TAJNY0123456789"
    r = _dry(tmp_path, JARVO_TOKEN=secret, JARVO_FAKE_WSL="brak")
    assert r.returncode == 0 and secret not in r.stdout + r.stderr
    r = _dry(tmp_path, JARVO_TOKEN=secret)
    assert r.returncode == 0 and secret not in r.stdout + r.stderr


def test_dry_uninstall(tmp_path):
    r = _dry(tmp_path, JARVO_UNINSTALL="1")
    assert r.returncode == 0 and "wsl.exe --unregister Jarvo" in r.stdout and "--import" not in r.stdout
    jarvo_bin = str(tmp_path / "Jarvo" / "bin")
    r = _dry(tmp_path, JARVO_UNINSTALL="1", LOCALAPPDATA=str(tmp_path), JARVO_FAKE_USER_PATH=r"C:\Narzedzia;" + jarvo_bin)
    assert re.search(r"PATH użytkownika = C:\\Narzedzia$", r.stdout, re.M), r.stdout


def test_irm_iex_keeps_session(tmp_path):
    """Tak jak `irm … | iex`: błąd nie zamyka okna PowerShella, a ustawienia sesji wracają."""
    env = {"HOME": str(tmp_path), "JARVO_DRY_RUN": "1", "JARVO_FAKE_BUILD": "18363"}
    # irm dekoduje odpowiedź jako UTF-8 (nagłówek charset), więc i tu UTF-8
    r = _ps(f"Get-Content -Raw -Encoding UTF8 '{PS1}' | Invoke-Expression; Write-Output \"dalej $ErrorActionPreference\"", **env)
    assert "Potrzebny Windows 10" in r.stdout and "dalej Continue" in r.stdout, r.stdout + r.stderr
