"""Instalator jednym poleceniem (install.sh, bin/jarvo, scripts/local-up.sh): składnia, shellcheck, próby na sucho
na udawanych dystrybucjach, sprawdzenie sprzętu, polecenie jarvo i przygotowanie katalogu floty bez pytań.

Pełny test od zera (świeży Ubuntu w kontenerze, Docker Engine z get.docker.com, flota) robi
scripts/install-test.sh w piaskownicy Claude Code; tu tylko to, co działa wszędzie i w sekundy.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import fleetlib as fl

ROOT = fl.REPO_ROOT
INSTALL = ROOT / "install.sh"
JARVO = ROOT / "bin/jarvo"
LOCAL_UP = ROOT / "scripts/local-up.sh"
SCRIPTS = [INSTALL, JARVO, LOCAL_UP]
# próby na sucho udają Linuksa i macOS podmienionymi programami (uname, sw_vers, sysctl) na Linuksie; na prawdziwym
# macOS wygrywa systemowy uname i Homebrew, więc tam CI (installer.yml) sprawdza install.sh i jarvo na żywo
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="testy instalatora udają systemy na Linuksie")
# programy, których instalator ma doinstalować, gdy ich brak (poza PATH testu)
TOOLS = ("git", "curl", "python3", "openssl", "docker")


def _shim(bin_dir: Path, name: str, body: str) -> None:
    p = bin_dir / name
    p.unlink(missing_ok=True)   # zamiast dowiązania do systemowego programu (/bin to /usr/bin na wielu systemach)
    p.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


def _bare_path(tmp_path: Path, hide=TOOLS, root=False) -> Path:
    """PATH ze wszystkim z systemu poza `hide`; udawany zwykły użytkownik (id) z sudo, które nic nie robi."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    for d in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
        for exe in Path(d).glob("*"):
            if exe.name in hide or (bin_dir / exe.name).exists():
                continue
            try:
                (bin_dir / exe.name).symlink_to(exe)
            except OSError:
                pass
    if not root:
        _shim(bin_dir, "id", 'case "$1" in -u) echo 1000;; -un) echo tester;; -nG) echo "tester users";; *) echo 1000;; esac\n')
        _shim(bin_dir, "sudo", 'exec "$@"\n')
    return bin_dir


def _os_release(tmp_path: Path, id_: str, like: str = "") -> Path:
    p = tmp_path / "os-release"
    p.write_text(f'NAME="X"\nID={id_}\n' + (f'ID_LIKE="{like}"\n' if like else ""), encoding="utf-8")
    return p


def _dry(tmp_path: Path, os_release: Path, hide=TOOLS, **extra) -> subprocess.CompletedProcess:
    env = {"PATH": str(_bare_path(tmp_path, hide)), "HOME": str(tmp_path / "home"), "LANG": "C.UTF-8",
           "JARVO_DRY_RUN": "1", "JARVO_DISK_GB": "100", "JARVO_DIR": str(tmp_path / "home/jarvo"), "JARVO_OS_RELEASE": str(os_release)}
    env.update(extra)
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    return subprocess.run(["bash", str(INSTALL)], env=env, capture_output=True, text=True, timeout=60)


# ---------------------------------------------------------------- składnia i lint

def test_scripts_parse():
    for s in SCRIPTS:
        assert subprocess.run(["bash", "-n", str(s)], capture_output=True).returncode == 0, s
    text = INSTALL.read_text(encoding="utf-8").rstrip().splitlines()
    assert text[-1].startswith('main "$@"; exit'), "install.sh: całość w main, exit zaraz po nim (stdin przepięte na terminal)"
    assert (ROOT / "infra/autostart/jarvo-updater.service").exists()


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="brak shellcheck (make dev-deps)")
def test_shellcheck_clean():
    res = subprocess.run(["shellcheck", "-S", "warning", *map(str, SCRIPTS)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout


# ---------------------------------------------------------------- próby na sucho

def test_dry_run_fresh_ubuntu_installs_tools_and_docker(tmp_path):
    res = _dry(tmp_path, _os_release(tmp_path, "ubuntu", "debian"))
    assert res.returncode == 0, res.stdout + res.stderr
    out = res.stdout
    assert "System: linux" in out and "pakiety: apt" in out
    assert "apt-get -o DPkg::Lock::Timeout=600 install -y -q git curl python3 openssl ca-certificates" in out
    assert "get.docker.com" in out and "$ sudo env" in out and " sh /" in out
    assert "$ sudo -v" in out and out.index("$ sudo -v") < out.index("apt-get")   # hasło raz, przed pierwszym sudo
    assert "git clone -q --depth 50 -b main https://github.com/jarojarojaro-jaro/JARVO.git" in out
    assert "bin/jarvo up" in out
    assert "Koniec próby na sucho" in out
    assert not (tmp_path / "home/jarvo").exists() and not (tmp_path / "home/jarvo-local").exists()


def _wsl_shims(bin_dir: Path, log: Path, app: str = r"C:\Users\tester\AppData\Local") -> None:
    """Udawany Windows z WSL: cmd.exe podaje LOCALAPPDATA, wslpath tłumaczy ścieżkę, powershell.exe zapisuje polecenie."""
    (bin_dir / "localappdata.txt").write_text(app + "\r\n", encoding="utf-8")
    _shim(bin_dir, "cmd.exe", f'cat "{bin_dir}/localappdata.txt"\n')
    _shim(bin_dir, "wslpath", f'echo "{log.parent}/win"\n')
    _shim(bin_dir, "powershell.exe", f'printf "%s\\n" "$@" > "{log}"\n')


def test_dry_run_wsl_makes_windows_jarvo_command(tmp_path):
    """jarvo update w Linuksie WSL zakłada też jarvo w PowerShellu (ten sam jarvo.cmd co install.ps1)."""
    proc = tmp_path / "version"
    proc.write_text("Linux version 6.6.87.2-microsoft-standard-WSL2\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    res0 = _dry(tmp_path, _os_release(tmp_path, "ubuntu", "debian"))   # tworzy bin z PATH testu
    assert res0.returncode == 0, res0.stdout + res0.stderr
    assert "jarvo.cmd" not in res0.stdout   # zwykły Linux: nic dla Windowsa
    _wsl_shims(bin_dir, tmp_path / "ps.log")
    env = {"PATH": str(bin_dir), "HOME": str(tmp_path / "home"), "LANG": "C.UTF-8", "JARVO_DRY_RUN": "1",
           "JARVO_DISK_GB": "100", "JARVO_DIR": str(tmp_path / "home/jarvo"),
           "JARVO_OS_RELEASE": str(_os_release(tmp_path, "ubuntu", "debian")), "JARVO_PROC_VERSION": str(proc),
           "WSL_DISTRO_NAME": "Ubuntu"}
    res = subprocess.run(["bash", str(INSTALL)], env=env, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    out = res.stdout
    assert "System: wsl" in out
    assert r"jarvo.cmd (C:\Users\tester\AppData\Local\Jarvo\bin): wsl.exe -d Ubuntu -u tester --cd ~" in out
    assert out.index("jarvo.cmd") < out.index("bin/jarvo up")   # przed flotą: jest nawet, gdy flota padnie
    assert not (tmp_path / "win").exists() and not (tmp_path / "ps.log").exists()   # na sucho nic nie zapisuje


def _windows_cli(tmp_path: Path, **env) -> subprocess.CompletedProcess:
    """Sama funkcja windows_cli z install.sh (bez main), naprawdę zapisuje plik, z udawanym Windowsem."""
    body = INSTALL.read_text(encoding="utf-8")
    fn = body[body.index("windows_cli() {"):body.index("\n}\n", body.index("windows_cli() {")) + 3]
    script = ("say() { echo \"SAY $*\"; }\nwarn() { echo \"WARN $*\"; }\nOS=wsl\nDRY=0\n" + fn + "windows_cli\n")
    full = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "HOME": str(tmp_path), "WSL_DISTRO_NAME": "Ubuntu"}
    full.update(env)
    return subprocess.run(["bash", "-c", script], env=full, capture_output=True, text=True, timeout=30)


def test_wsl_windows_cli_writes_cmd_and_path(tmp_path):
    (tmp_path / "bin").mkdir()
    _wsl_shims(tmp_path / "bin", tmp_path / "ps.log", app=r"C:\Users\O'Neil\AppData\Local")
    res = _windows_cli(tmp_path)
    assert res.returncode == 0 and "WARN" not in res.stdout, res.stdout + res.stderr
    cmd = (tmp_path / "win/Jarvo/bin/jarvo.cmd").read_bytes().decode()
    assert cmd.startswith("@echo off\r\n") and cmd.endswith("jarvo %*\r\n")
    # ta sama linia co WindowsCommand w install.ps1: ${PATH} i ${HOME} dla basha w Linuksie, %* dla cmd
    assert ('wsl.exe -d Ubuntu -u ' in cmd and ' --cd ~ -e bash -c "export PATH=${PATH}:${HOME}/.local/bin:'
            '${HOME}/jarvo/bin; exec jarvo \\"$@\\"" jarvo %*' in cmd)
    ps = (tmp_path / "ps.log").read_text()
    assert "-NoProfile" in ps and "HKCU:\\Environment" in ps and "DoNotExpandEnvironmentNames" in ps
    assert r"$d='C:\Users\O''Neil\AppData\Local\Jarvo\bin'" in ps   # apostrof w nazwie użytkownika
    assert "SAY Polecenie jarvo w PowerShellu" in res.stdout


def test_wsl_windows_cli_without_interop_only_warns(tmp_path):
    (tmp_path / "bin").mkdir()
    res = _windows_cli(tmp_path, PATH=str(tmp_path / "bin") + ":/usr/bin:/bin")   # brak cmd.exe (interop wyłączony)
    assert res.returncode == 0 and "WARN Polecenie jarvo w PowerShellu" in res.stdout and "wsl -d Ubuntu -- jarvo" in res.stdout
    _wsl_shims(tmp_path / "bin", tmp_path / "ps.log")
    (tmp_path / "bin/powershell.exe").write_text("#!/bin/sh\nexit 1\n")   # PATH się nie zapisał
    res = _windows_cli(tmp_path)
    assert res.returncode == 0 and (tmp_path / "win/Jarvo/bin/jarvo.cmd").exists()
    assert "WARN jarvo.cmd jest w" in res.stdout


def test_dry_run_fedora_and_arch(tmp_path):
    fedora = _dry(tmp_path / "f", _os_release(tmp_path, "fedora"), JARVO_BRANCH="wydanie-1")
    assert fedora.returncode == 0, fedora.stdout + fedora.stderr
    assert "git clone -q --depth 50 -b wydanie-1 " in fedora.stdout
    # dnf, a gdy go nie ma na maszynie testowej: yum (ten sam wiersz poleceń)
    assert ("dnf install -y git curl python3 openssl" in fedora.stdout
            or "yum install -y git curl python3 openssl" in fedora.stdout) and "get.docker.com" in fedora.stdout
    arch = _dry(tmp_path / "a", _os_release(tmp_path, "manjaro", "arch"))
    assert arch.returncode == 0, arch.stdout + arch.stderr
    assert "pacman -Sy --noconfirm --needed git curl python openssl" in arch.stdout
    assert "pacman -Sy --noconfirm --needed docker docker-compose docker-buildx" in arch.stdout


def test_dry_run_rhel_likes_outside_get_docker_com(tmp_path):
    """get.docker.com zna tylko centos, rhel, rocky i fedorę: AlmaLinux i Oracle Linux biorą repo Dockera dla CentOS."""
    for d in ("a", "z", "u"):
        (tmp_path / d).mkdir()
    alma = _dry(tmp_path / "a", _os_release(tmp_path / "a", "almalinux", "rhel centos fedora"))
    assert alma.returncode == 0, alma.stdout + alma.stderr
    assert "download.docker.com/linux/centos/docker-ce.repo" in alma.stdout and "get.docker.com" not in alma.stdout
    assert "docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin" in alma.stdout
    amzn = _dry(tmp_path / "z", _os_release(tmp_path / "z", "amzn", "fedora"))
    assert amzn.returncode == 1 and "Amazon Linux" in amzn.stderr
    # apt-get w get.docker.com czeka na blokadę dpkg (aktualizacje w tle świeżego Ubuntu)
    ubuntu = _dry(tmp_path / "u", _os_release(tmp_path / "u", "ubuntu", "debian"))
    assert "APT_CONFIG=" in ubuntu.stdout


def test_rootless_docker_refused_early(tmp_path):
    bin_dir = tmp_path / "shims"
    bin_dir.mkdir()
    _shim(bin_dir, "docker", 'case "$1 $2" in "info -f") echo "[name=seccomp,profile=builtin name=rootless name=cgroupns]";; '
                             '"compose version"|"info ") exit 0;; version*) echo 29.0;; esac\n')
    hide = ("git", "curl", "python3", "openssl")
    res = _dry(tmp_path, _os_release(tmp_path, "debian"), hide=hide,
               PATH=str(bin_dir) + ":" + str(_bare_path(tmp_path / "p", hide=hide)))
    assert res.returncode == 1 and "rootless" in res.stderr


def test_dry_run_unknown_distro_stops_with_instructions(tmp_path):
    res = _dry(tmp_path, _os_release(tmp_path, "gentoo"))
    assert res.returncode == 1
    assert "Nieznana dystrybucja" in res.stderr and "docs.docker.com" in res.stderr


def test_dry_run_with_docker_present_skips_install(tmp_path):
    bin_dir = tmp_path / "shims"
    bin_dir.mkdir()
    _shim(bin_dir, "docker", 'case "$1 $2" in "compose version"|"info ") exit 0;; version*) echo 29.0;; ps*) echo "";; esac\n')
    os_release = _os_release(tmp_path, "debian")
    res = _dry(tmp_path, os_release, hide=("git", "curl", "python3", "openssl"),
               PATH=str(bin_dir) + ":" + str(_bare_path(tmp_path / "p", hide=("git", "curl", "python3", "openssl"))))
    assert res.returncode == 0, res.stdout + res.stderr
    assert "get.docker.com" not in res.stdout and "Docker: 29.0" in res.stdout
    assert "usermod" not in res.stdout and "groupadd" not in res.stdout   # Docker działa jako użytkownik: bez grupy i sudo do Dockera


def test_dry_run_docker_without_buildx_gets_plugin(tmp_path):
    """Docker z pakietów dystrybucji (docker.io) bywa bez buildx: doinstalowujemy, bo compose build go wymaga."""
    bin_dir = tmp_path / "shims"
    bin_dir.mkdir()
    _shim(bin_dir, "docker", 'case "$1 $2" in "compose version"|"info ") exit 0;; "buildx version") exit 1;; version*) echo 29.0;; esac\n')
    hide = ("git", "curl", "python3", "openssl")
    res = _dry(tmp_path, _os_release(tmp_path, "ubuntu", "debian"), hide=hide,
               PATH=str(bin_dir) + ":" + str(_bare_path(tmp_path / "p", hide=hide)))
    assert res.returncode == 0, res.stdout + res.stderr
    assert "apt-get -o DPkg::Lock::Timeout=600 install -y -q docker-buildx-plugin" in res.stdout and "get.docker.com" not in res.stdout


def _mac_shims(tmp_path: Path, ram_gb: int = 16, ver: str = "14.5", arch: str = "arm64") -> Path:
    """Udawany macOS na Linuksie: uname, sw_vers, sysctl (procesor Apple albo Intel, RAM)."""
    d = tmp_path / "mac"
    d.mkdir(parents=True)
    _shim(d, "uname", f'case "$1" in -s) echo Darwin;; -m) echo {arch};; *) echo Darwin;; esac\n')
    _shim(d, "sw_vers", f'echo {ver}\n')
    _shim(d, "sysctl", f'case "$2" in hw.memsize) echo {ram_gb * 1024 ** 3};; hw.ncpu) echo 8;; esac\n')
    _shim(d, "id", 'case "$1" in -u) echo 501;; -un) echo tester;; *) echo 501;; esac\n')
    return d


def _dry_mac(tmp_path: Path, extra_shims: Path | None = None, **extra) -> subprocess.CompletedProcess:
    hide = TOOLS + ("brew", "colima")
    path = [str(_mac_shims(tmp_path, **{k: extra.pop(k) for k in ("ram_gb", "ver", "arch") if k in extra}))]
    if extra_shims:
        path.insert(0, str(extra_shims))
    path.append(str(_bare_path(tmp_path / "p", hide)))
    return _dry(tmp_path, _os_release(tmp_path, "nieistotne"), PATH=":".join(path), **extra)


def test_dry_run_macos_installs_brew_and_colima(tmp_path):
    res = _dry_mac(tmp_path)
    assert res.returncode == 0, res.stdout + res.stderr
    out = res.stdout
    assert "System: macOS 14.5 (arm64)" in out
    # hasło raz, przed instalatorem Homebrew (tryb bez pytań wymaga zapamiętanego sudo)
    assert "$ sudo -v" in out and out.index("$ sudo -v") < out.index("Homebrew/install")
    assert "brew install -q bash git python openssl@3" in out
    assert "brew install -q colima docker docker-compose docker-buildx" in out   # buildx: jarvo komputer on
    # połowa procesorów, 8 GB przy 16 GB RAM, Virtualization.framework
    assert "colima start --cpu 4 --memory 8 --disk 60 --vm-type vz --mount-type virtiofs" in out
    assert "git clone -q --depth 50 -b main" in out and "bin/jarvo up" in out
    assert "/opt/homebrew/bin/jarvo" in out   # polecenie w katalogu Homebrew: bez sudo
    assert "apt-get" not in out and "get.docker.com" not in out


def test_dry_run_macos_homebrew_tier3_warning(tmp_path):
    """Homebrew ma gotowe paczki tylko dla Apple Silicon z macOS 15+; Intel i macOS 12–14 kompilują na miejscu."""
    assert "macOS 14: Homebrew ma gotowe paczki dla macOS 15" in _dry_mac(tmp_path / "a").stdout
    assert "Homebrew" not in _dry_mac(tmp_path / "b", ver="15.4").stdout.split("Instaluję Homebrew")[0]
    intel = _dry_mac(tmp_path / "c", ver="15.4", arch="x86_64")
    assert intel.returncode == 0 and "Mac z Intelem" in intel.stdout and "System: macOS 15.4 (x86_64)" in intel.stdout


def test_disk_thresholds(tmp_path):
    """Obraz floty po rozpakowaniu ma ok. 7 GB (z warstwami spakowanymi 9,8 GB): minimum 20 GB, polecane 30."""
    low = _dry(tmp_path / "a", _os_release(tmp_path, "ubuntu"), JARVO_DISK_GB="15")
    assert low.returncode == 1 and "Za mało miejsca (15 GB)" in low.stderr
    mid = _dry(tmp_path / "b", _os_release(tmp_path, "ubuntu"), JARVO_DISK_GB="25")
    assert mid.returncode == 0 and "Polecamy 30 GB wolnego miejsca" in mid.stdout


def test_dry_run_macos_small_and_old(tmp_path):
    res = _dry_mac(tmp_path, ram_gb=8, ver="12.7")
    assert res.returncode == 0, res.stdout + res.stderr
    # macOS 12: bez vz, QEMU z Homebrew; 8 GB RAM: maszyna wirtualna 5 GB
    assert "colima docker docker-compose docker-buildx qemu" in res.stdout
    assert "--memory 5 --disk 60 --vm-type qemu" in res.stdout
    res = _dry_mac(tmp_path / "s", ver="11.7")
    assert res.returncode == 1 and "macOS 12" in res.stderr


def test_dry_run_macos_docker_running_keeps_it(tmp_path):
    shims = tmp_path / "dk"
    shims.mkdir()
    _shim(shims, "docker", 'case "$1 $2" in "compose version"|"info ") exit 0;; version*) echo 28.1;; context*) echo desktop-linux;; esac\n')
    _shim(shims, "brew", 'case "$1" in shellenv) echo "export HOMEBREW_PREFIX=/opt/homebrew";; --prefix) echo /opt/homebrew;; list) exit 0;; esac\n')
    res = _dry_mac(tmp_path, extra_shims=shims)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Docker: 28.1 (już działa: desktop-linux)" in res.stdout
    assert "colima" not in res.stdout and "Homebrew/install" not in res.stdout
    assert "install -q docker-buildx" not in res.stdout
    # Colima z wcześniejszej instalacji bez buildx: doinstalowana wtyczka i katalog wtyczek w ~/.docker/config.json
    _shim(shims, "docker", 'case "$1 $2" in "compose version"|"info ") exit 0;; "buildx version") exit 1;; version*) echo 28.1;; context*) echo colima;; esac\n')
    res = _dry_mac(tmp_path / "bez-buildx", extra_shims=shims)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "brew install -q docker-buildx" in res.stdout and "colima start" not in res.stdout


def test_token_never_printed_and_used_for_git(tmp_path):
    res = _dry(tmp_path, _os_release(tmp_path, "ubuntu"), JARVO_TOKEN="ghp_tajnytoken123")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "ghp_tajnytoken123" not in res.stdout + res.stderr
    assert "git clone -q --depth 50 -b main" in res.stdout


def test_low_ram_refuses_unless_forced(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:        2000000 kB\n", encoding="utf-8")
    res = _dry(tmp_path / "1", _os_release(tmp_path, "ubuntu"), JARVO_MEMINFO=str(meminfo))
    assert res.returncode == 1 and "Za mało RAM" in res.stderr
    res = _dry(tmp_path / "2", _os_release(tmp_path, "ubuntu"), JARVO_MEMINFO=str(meminfo), JARVO_FORCE="1")
    assert res.returncode == 0, res.stdout + res.stderr


def test_four_gb_machine_counts_as_four_and_update_only_warns(tmp_path):
    """MemTotal „4 GB” maszyny to ok. 3,8 GB (jądro rezerwuje część); aktualizacja istniejącej floty nie przerywa."""
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:        3900000 kB\n", encoding="utf-8")
    res = _dry(tmp_path / "1", _os_release(tmp_path, "ubuntu"), JARVO_MEMINFO=str(meminfo))
    assert res.returncode == 0 and "RAM: 4 GB" in res.stdout and "Polecamy 8 GB RAM" in res.stdout
    # jarvo update na maszynie, której zabrakło miejsca i RAM: tylko ostrzeżenia, aktualizacja idzie dalej
    lokal = tmp_path / "lokal"
    lokal.mkdir()
    (lokal / ".installed").write_text("", encoding="utf-8")
    meminfo.write_text("MemTotal:        2000000 kB\n", encoding="utf-8")
    res = _dry(tmp_path / "2", _os_release(tmp_path, "ubuntu"), JARVO_MEMINFO=str(meminfo), JARVO_DISK_GB="7",
               JARVO_LOCAL=str(lokal))
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Za mało RAM (2 GB)" in res.stdout and "Za mało miejsca (7 GB)" in res.stdout and "JARVO_FORCE" not in res.stdout


def test_setup_only_and_no_secrets_in_output(tmp_path):
    res = _dry(tmp_path, _os_release(tmp_path, "ubuntu"), JARVO_SETUP_ONLY="1", JARVO_KEY="sk-tajny-klucz-123")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "JARVO_SETUP_ONLY=1" in res.stdout and "bin/jarvo up" not in res.stdout
    assert "sk-tajny-klucz-123" not in res.stdout + res.stderr


# ---------------------------------------------------------------- bin/jarvo

def _jarvo(*args, **env_extra) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_extra}
    return subprocess.run(["bash", str(JARVO), *args], env=env, capture_output=True, text=True, timeout=30)


def test_jarvo_update_without_network_says_so(tmp_path):
    """Brak sieci (WSL po uśpieniu, VPN): komunikat mówi o sieci, a nie o „lokalnych zmianach” w repo."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "git").write_text("#!/usr/bin/env bash\n"
                                'case " $* " in *" rev-parse "*) echo main ;; *) exit 128 ;; esac\n', encoding="utf-8")
    (bindir / "git").chmod(0o755)
    res = _jarvo("update", PATH=f"{bindir}:{os.environ['PATH']}")
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "lokalne zmiany" not in out and ("internetu" in out or "połączenia z GitHubem" in out)


def test_jarvo_help_version_and_unknown():
    assert _jarvo("help").returncode == 0
    assert "jarvo uninstall" in _jarvo("help").stdout
    assert _jarvo("bogus").returncode == 2
    assert _jarvo("version").returncode == 0


def test_jarvo_uninstall_without_registry_image(tmp_path):
    """uninstall --yes przy obrazie zbudowanym na miejscu (brak tagów src-* z rejestru) kończy się sukcesem."""
    bin_ = tmp_path / "bin"; bin_.mkdir()
    _shim(bin_, "docker", 'echo "docker $*" >> "$LOG"\n'
          'case "$1" in images) echo jarvo-hermes:local;; esac\nexit 0\n')
    flota = tmp_path / "flota"; (flota / "compose").mkdir(parents=True)
    (flota / "compose/.env").write_text("DASHBOARD_PASSWORD=x\n")
    res = _jarvo("uninstall", "--yes", JARVO_LOCAL=str(flota), LOG=str(tmp_path / "log"),
                 PATH=f"{bin_}:{os.environ['PATH']}", HOME=str(tmp_path))
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Flota usunięta" in res.stdout and "Dane zostają" in res.stdout
    assert "docker image rm -f jarvo-hermes:local" in (tmp_path / "log").read_text()
    assert (flota / "compose/.env").exists()


def _mac_repo(tmp_path: Path) -> Path:
    """Kopia bin/ i szablonów autostartu bez .git: uninstall --all nie ma czego (prawdziwego repo) usunąć."""
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "bin", repo / "bin")
    shutil.copytree(ROOT / "infra/autostart", repo / "infra/autostart")
    return repo


def _uninstall_mac(tmp_path: Path, inne_kontenery: str = "") -> tuple[subprocess.CompletedProcess, str, Path]:
    repo = _mac_repo(tmp_path)
    mac = _mac_shims(tmp_path)
    _shim(mac, "sudo", 'exec "$@"\n')
    _shim(mac, "docker", 'echo "docker $*" >> "$LOG"\n'
          f'case "$1 $2" in "ps -aq") echo "{inne_kontenery}";; "volume ls") echo jarvo-hermes-data;; esac\nexit 0\n')
    _shim(mac, "colima", 'echo "colima $*" >> "$LOG"\n')
    brew = tmp_path / "brew"
    (brew / "bin").mkdir(parents=True)
    _shim(mac, "brew", f'case "$1" in --prefix) echo {brew};; esac\n')
    (brew / "bin/jarvo").symlink_to(repo / "bin/jarvo")   # link_cli na Apple Silicon: /opt/homebrew/bin/jarvo
    flota = tmp_path / "flota"
    (flota / "compose").mkdir(parents=True)
    (flota / "compose/.env").write_text("DASHBOARD_PASSWORD=x\nJARVO_VOL_HERMES=jarvo-hermes-data\n", encoding="utf-8")
    (flota / ".colima").write_text("", encoding="utf-8")   # Colimę postawił instalator
    log = tmp_path / "log"
    res = subprocess.run(["bash", str(repo / "bin/jarvo"), "uninstall", "--yes", "--all"], capture_output=True, text=True,
                         timeout=30, env={**os.environ, "PATH": f"{mac}:{os.environ['PATH']}", "HOME": str(tmp_path),
                                          "JARVO_LOCAL": str(flota), "LOG": str(log)})
    return res, log.read_text(encoding="utf-8") if log.exists() else "", brew / "bin/jarvo"


def test_jarvo_uninstall_macos_removes_homebrew_link_and_colima(tmp_path):
    """Apple Silicon: polecenie jarvo leży w /opt/homebrew/bin; --all zwalnia maszynę wirtualną Colimy instalatora."""
    res, log, link = _uninstall_mac(tmp_path)
    assert res.returncode == 0, res.stdout + res.stderr
    assert not link.is_symlink() and "colima delete -f" in log
    assert "Usunięto maszynę wirtualną Colimy" in res.stdout and not (tmp_path / "flota").exists()
    # w Colimie są cudze kontenery: zostaje, tylko podpowiedź
    res, log, _link = _uninstall_mac(tmp_path / "inne", inne_kontenery="abc123")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "colima delete" not in log and "Colima zostaje" in res.stdout


def test_jarvo_android_on_arm_skips_x86_emulator(tmp_path):
    """Obraz emulatora jest tylko dla x86_64: na ARM (Ampere, Graviton, Raspberry Pi) od razu jasna odmowa."""
    bin_ = tmp_path / "bin"; bin_.mkdir()
    _shim(bin_, "uname", 'case "$1" in -m) echo aarch64;; *) echo Linux;; esac\n')
    flota = tmp_path / "flota"; (flota / "compose").mkdir(parents=True)
    (flota / "compose/.env").write_text("DASHBOARD_PASSWORD=x\n", encoding="utf-8")
    res = _jarvo("android", "on", "--emulator", JARVO_LOCAL=str(flota), PATH=f"{bin_}:{os.environ['PATH']}")
    assert res.returncode == 1 and "nie działa na procesorze ARM" in res.stderr


def _install_fn(name: str) -> str:
    """Jedna funkcja z install.sh (bez uruchamiania całego instalatora)."""
    text = INSTALL.read_text(encoding="utf-8")
    start = text.index(f"\n{name}() {{") + 1
    return text[start:text.index("\n}\n", start) + 3]


def test_brew_shellenv_keeps_existing_profile(tmp_path):
    """bash przy logowaniu czyta tylko pierwszy z .bash_profile/.bash_login/.profile: nowy .bash_profile ukryłby .profile."""
    brew = tmp_path / "brew"
    brew.write_text("#!/bin/sh\necho 'export HOMEBREW_PREFIX=/opt/homebrew'\n", encoding="utf-8")
    brew.chmod(0o755)

    def shellenv(home: Path) -> None:
        script = _install_fn("brew_shellenv") + f'DRY=0; BREW={brew}; HOME={home}; brew_shellenv\n'
        res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
        assert res.returncode == 0, res.stderr

    a = tmp_path / "a"; a.mkdir()
    (a / ".profile").write_text("export X=1\n", encoding="utf-8")
    shellenv(a)
    shellenv(a)   # drugi raz bez powtórki
    assert not (a / ".bash_profile").exists() and (a / ".profile").read_text().count("eval ") == 1
    assert "shellenv" in (a / ".zprofile").read_text()
    b = tmp_path / "b"; b.mkdir()
    (b / ".bash_profile").write_text("# moje\n", encoding="utf-8")
    shellenv(b)
    assert "shellenv" in (b / ".bash_profile").read_text() and not (b / ".profile").exists()



def test_pobierz_retries_transient_network_error(tmp_path):
    """curl: (7) Failed to connect (sieć runnera, chwilowa awaria) nie kończy instalacji: pobierz() ponawia do 3 razy."""
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    licznik = tmp_path / "proby"
    _shim(bin_dir, "sleep", "exit 0\n")
    _shim(bin_dir, "curl", f'echo x >> {licznik}\n[ "$(wc -l < {licznik})" -ge "${{UDANA:-9}}" ] || exit 7\n'
                           'while [ $# -gt 1 ]; do shift; done; echo skrypt > "$1"\n')

    def pobierz(udana: str) -> subprocess.CompletedProcess:
        licznik.unlink(missing_ok=True)
        script = 'warn() { echo "W: $*"; }\n' + _install_fn("pobierz") + f'pobierz https://get.docker.com {tmp_path}/out\n'
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "UDANA": udana}
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30, env=env)

    res = pobierz("3")
    assert res.returncode == 0, res.stdout + res.stderr
    assert (tmp_path / "out").read_text() == "skrypt\n" and res.stdout.count("ponawiam") == 2
    res = pobierz("9")
    assert res.returncode == 1 and licznik.read_text().count("x") == 4 and "ponawiam (3/3)" in res.stdout

def test_mac_compose_plugin_drops_stale_docker_desktop_creds(tmp_path):
    """Po odinstalowanym Docker Desktop zostaje credsStore "desktop": docker pull w Colimie by się wywracał."""
    import json
    (tmp_path / ".docker").mkdir()
    cfg = tmp_path / ".docker/config.json"
    shims = tmp_path / "shims"; shims.mkdir()
    _shim(shims, "brew", f'echo {tmp_path}/brew\n')

    def run(extra_path: str = "") -> dict:
        cfg.write_text(json.dumps({"credsStore": "desktop", "auths": {}}), encoding="utf-8")
        script = _install_fn("mac_compose_plugin") + f'DRY=0; BREW={shims}/brew; HOME={tmp_path}; mac_compose_plugin\n'
        res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30,
                             env={**os.environ, "PATH": f"{extra_path}{shims}:{os.environ['PATH']}"})
        assert res.returncode == 0, res.stderr
        return json.loads(cfg.read_text(encoding="utf-8"))

    c = run()
    assert "credsStore" not in c and c["cliPluginsExtraDirs"] == [f"{tmp_path}/brew/lib/docker/cli-plugins"]
    helper = tmp_path / "helper"; helper.mkdir()
    _shim(helper, "docker-credential-desktop", "exit 0\n")
    assert run(f"{helper}:")["credsStore"] == "desktop"   # Docker Desktop dalej jest: zostaje


def test_jarvo_old_bash_does_not_loop(tmp_path):
    """Stary bash pod /usr/local/bin (nie z Homebrew) nie może zapętlić exec w bin/jarvo: jeden skok i dalej."""
    text = JARVO.read_text(encoding="utf-8")
    assert "JARVO_BASH_REEXEC=1 exec" in text and "[[ -z ${JARVO_BASH_REEXEC:-} ]]" in text
    # skrypty wołane przez jarvo dostają bash 4+ także wtedy, gdy pierwszy w PATH jest /bin/bash 3.2
    assert "BASH_VERSINFO[0] >= 4" in text and 'export PATH="${BASH%/*}:$PATH"' in text


def test_launchagent_runs_in_background(tmp_path):
    import plistlib
    res = subprocess.run(["bash", str(_mac_repo(tmp_path) / "bin/jarvo"), "autostart", "print"], capture_output=True,
                         text=True, timeout=30, env={**os.environ, "JARVO_LOCAL": str(tmp_path / "flota"),
                                                     "PATH": f"{_mac_shims(tmp_path)}:{os.environ['PATH']}"})
    assert res.returncode == 0, res.stderr
    plist = plistlib.loads(res.stdout.encode())
    assert plist["ProcessType"] == "Background" and plist["LowPriorityIO"] is True
    assert ".orbstack/bin" in plist["EnvironmentVariables"]["PATH"]


def test_jarvo_unit_rendering(tmp_path):
    res = _jarvo("autostart", "print", JARVO_LOCAL=str(tmp_path / "flota"), JARVO_AUTO_UPDATE="1")
    assert res.returncode == 0, res.stderr
    unit = res.stdout
    assert f"ExecStart={JARVO} updater" in unit
    assert f"Environment=JARVO_LOCAL={tmp_path / 'flota'}" in unit and "JARVO_AUTO_UPDATE=1" in unit
    assert "WantedBy=default.target" in unit and "#" not in unit


def test_jarvo_reads_local_dir_from_marker(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "bin", repo / "bin")
    shutil.copytree(ROOT / "infra/autostart", repo / "infra/autostart")
    (repo / ".jarvo-local").write_text(str(tmp_path / "moja-flota") + "\n", encoding="utf-8")
    res = subprocess.run(["bash", str(repo / "bin/jarvo"), "autostart", "print"],
                         env={k: v for k, v in os.environ.items() if k != "JARVO_LOCAL"},
                         capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    assert f"JARVO_LOCAL={tmp_path / 'moja-flota'}" in res.stdout


def test_jarvo_needs_installed_fleet(tmp_path):
    res = _jarvo("status", JARVO_LOCAL=str(tmp_path / "nic"))
    assert res.returncode == 1 and "nie jest zainstalowana" in res.stderr


# ---------------------------------------------------------------- local-up.sh --prepare

@pytest.mark.skipif(os.geteuid() != 0, reason="chgrp/chown na uid 10000 wymaga roota (w piaskownce jesteśmy rootem)")
def test_local_up_prepare_without_questions(tmp_path):
    bin_dir = tmp_path / "shims"
    bin_dir.mkdir()
    _shim(bin_dir, "docker", '[ "$1" = info ] && exit 0; exit 1\n')
    local = tmp_path / "flota"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "JARVO_LOCAL": str(local),
           "JARVO_PROVIDER": "commandcode-anthropic", "JARVO_KEY": "cc-tajny-klucz", "JARVO_YES": "1"}
    res = subprocess.run(["bash", str(LOCAL_UP), "--prepare"], env=env, capture_output=True, text=True,
                         timeout=60, stdin=subprocess.DEVNULL)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "cc-tajny-klucz" not in res.stdout + res.stderr
    dot_env = (local / "compose/.env").read_text(encoding="utf-8")
    assert "DASHBOARD_PASSWORD=" in dot_env and f"JARVO_DATA={local}/data" in dot_env
    assert stat.S_IMODE((local / "compose/.env").stat().st_mode) == 0o600
    assert "JARVO_MODEL_PROVIDER=commandcode-anthropic" in (local / "compose/jarvo.env").read_text(encoding="utf-8")
    host_env = local / "secrets/host.env"
    assert "COMMANDCODE_API_KEY=cc-tajny-klucz" in host_env.read_text(encoding="utf-8")
    assert host_env.stat().st_gid == 10000 and stat.S_IMODE(host_env.stat().st_mode) == 0o640
    assert (local / "data").stat().st_uid == 10000 and not (local / ".installed").exists()

    bad = subprocess.run(["bash", str(LOCAL_UP), "--prepare"], env={**env, "JARVO_LOCAL": str(tmp_path / "x"),
                         "JARVO_PROVIDER": "nieznany"}, capture_output=True, text=True, timeout=60)
    assert bad.returncode == 2 and "Nieznany JARVO_PROVIDER" in bad.stdout


def test_local_up_prepare_volumes_mode(tmp_path):
    """macOS (tu JARVO_VOLUMES=1): dane i build w wolumenach Dockera, bez chown katalogów hosta."""
    bin_dir = tmp_path / "shims"
    bin_dir.mkdir()
    _shim(bin_dir, "docker", '[ "$1" = info ] && exit 0; exit 1\n')
    local = tmp_path / "flota"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "JARVO_LOCAL": str(local),
           "JARVO_YES": "1", "JARVO_VOLUMES": "1"}
    res = subprocess.run(["bash", str(LOCAL_UP), "--prepare"], env=env, capture_output=True, text=True,
                         timeout=60, stdin=subprocess.DEVNULL)
    assert res.returncode == 0, res.stdout + res.stderr
    dot_env = (local / "compose/.env").read_text(encoding="utf-8")
    assert "JARVO_BUILD=jarvo-build" in dot_env
    assert "JARVO_VOL_HERMES=jarvo-hermes-data" in dot_env and "JARVO_VOL_VALKEY=jarvo-valkey-data" in dot_env
    assert (local / "data").stat().st_uid != 10000   # wolumeny: katalogów hosta nie przejmujemy


def test_compose_volumes_interpolation(tmp_path):
    """Ten sam docker-compose.yml: katalogi hosta (Linux) albo wolumeny o stałych nazwach (macOS)."""
    if shutil.which("docker") is None or subprocess.run(["docker", "compose", "version"], capture_output=True).returncode:
        pytest.skip("brak docker compose")
    compose = ROOT / "infra/docker-compose.yml"
    base = {"DASHBOARD_PASSWORD": "x", "SEARXNG_SECRET": "y", "JARVO_DATA": "/d", "JARVO_BUILD": "/b",
            "JARVO_REPO": "/r", "JARVO_SECRETS": "/s"}

    def cfg(**extra):
        r = subprocess.run(["docker", "compose", "-f", str(compose), "config", "--format", "json"],
                           env={**os.environ, **base, **extra}, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        import json
        return {v["target"]: v for v in json.loads(r.stdout)["services"]["hermes"]["volumes"]}

    linux = cfg()
    assert linux["/opt/data"]["type"] == "bind" and linux["/opt/data"]["source"] == "/d/hermes"
    mac = cfg(JARVO_VOL_HERMES="jarvo-hermes-data", JARVO_BUILD="jarvo-build")
    assert mac["/opt/data"] == {**mac["/opt/data"], "type": "volume", "source": "jarvo-hermes-data"}
    assert mac["/opt/jarvo/build"]["type"] == "volume" and mac["/opt/jarvo/build"]["source"] == "jarvo-build"


def test_hermes_pinned_everywhere():
    """Jedna wersja Hermesa: ARG w Dockerfile = domyślna w compose = fleet.yaml (klucz obrazu w GHCR jej dotyczy)."""
    import re
    pin = re.search(r"^ARG HERMES_IMAGE=(\S+)$", (ROOT / "infra/Dockerfile").read_text(), re.M).group(1)
    assert re.fullmatch(r"nousresearch/hermes-agent:[\w.-]+@sha256:[0-9a-f]{64}", pin), pin
    assert "HERMES_IMAGE: ${HERMES_IMAGE:-" + pin + "}" in (ROOT / "infra/docker-compose.yml").read_text()
    assert f"hermes_image: {pin} " in (ROOT / "fleet.yaml").read_text()
    assert re.search(r"^HERMES_IMAGE=$", (ROOT / "infra/env/compose.env.example").read_text(), re.M)


def test_obraz_own_hermes_builds_locally(tmp_path):
    """Własny HERMES_IMAGE w compose/.env: obraz z rejestru nie pasuje, więc budowa na miejscu (kod 1, bez docker pull)."""
    (tmp_path / ".env").write_text("HERMES_IMAGE=hermes-ca:test\n")
    bin_ = tmp_path / "bin"; bin_.mkdir()
    _shim(bin_, "docker", 'echo "docker $*" >> "$LOG"; exit 0')
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "LOG": str(tmp_path / "log")}
    r = subprocess.run(["bash", str(ROOT / "scripts/obraz.sh"), "pobierz", str(tmp_path)], env=env,
                       capture_output=True, text=True)
    assert r.returncode == 1 and "Własny HERMES_IMAGE" in r.stdout
    assert not (tmp_path / "log").exists()



def test_obraz_image_extras_build_locally(tmp_path):
    """Dodatki obrazu w JARVO_EXTRAS: CI buduje obraz bez nich, więc pobranie dałoby obraz bez dodatków (kod 1, bez
    docker pull); lemo i mgaudio instalują się w działającym kontenerze, więc z nimi obraz dalej się pobiera."""
    bin_ = tmp_path / "bin"; bin_.mkdir()
    _shim(bin_, "docker", 'echo "docker $*" >> "$LOG"; exit 0')
    log = tmp_path / "log"
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "LOG": str(log)}
    env.pop("JARVO_EXTRAS", None); env.pop("JARVO_TOKEN", None)
    for wpis, zmienna, dodatek in [('JARVO_EXTRAS="lemo,manim"\n', None, "manim"), ("JARVO_EXTRAS=office\n", None, "office"),
                                   ("JARVO_EXTRAS=\n", "lemo docling", "docling")]:
        (tmp_path / ".env").write_text(wpis)
        r = subprocess.run(["bash", str(ROOT / "scripts/obraz.sh"), "pobierz", str(tmp_path)], capture_output=True,
                           text=True, env=env if zmienna is None else {**env, "JARVO_EXTRAS": zmienna})
        assert r.returncode == 1 and f"Dodatek obrazu {dodatek}" in r.stdout, r.stdout + r.stderr
    assert not log.exists()
    (tmp_path / ".env").write_text("JARVO_EXTRAS=lemo mgaudio\n")
    r = subprocess.run(["bash", str(ROOT / "scripts/obraz.sh"), "pobierz", str(tmp_path)], capture_output=True,
                       text=True, env=env)
    assert r.returncode == 0 and "docker pull" in log.read_text(), r.stdout + r.stderr


def test_obraz_extras_match_dockerfile():
    """Lista dodatków, przy których obraz.sh buduje na miejscu = dodatki, które infra/Dockerfile instaluje przy budowie."""
    import re
    df = (ROOT / "infra/Dockerfile").read_text(encoding="utf-8")
    w_obrazie = set(re.findall(r'\*" (\w+) "\*', df)) | set(re.search(r"for x in ([\w ]+); do", df).group(1).split())
    sh = (ROOT / "scripts/obraz.sh").read_text(encoding="utf-8")
    assert set(re.search(r"for x in ([\w ]+); do   # te, które infra/Dockerfile", sh).group(1).split()) == w_obrazie

def _obraz(tmp_path: Path, docker: str, **env_extra) -> tuple[subprocess.CompletedProcess, str]:
    """obraz.sh pobierz w małym repo z świeżą zmianą infra/ (klucz i wiek zmiany jak w prawdziwym repo)."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "infra").mkdir()
    shutil.copy(ROOT / "scripts/obraz.sh", repo / "scripts/obraz.sh")
    (repo / "infra/Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "x"], check=True)
    bin_ = tmp_path / "bin"; bin_.mkdir()
    _shim(bin_, "docker", 'echo "docker $*" >> "$LOG"\n' + docker)
    (tmp_path / "compose").mkdir()
    log = tmp_path / "log"
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "LOG": str(log), "JARVO_IMAGE_POLL": "0",
           "STAN": str(tmp_path / "stan"), **env_extra}
    env.pop("JARVO_TOKEN", None)
    r = subprocess.run(["bash", str(repo / "scripts/obraz.sh"), "pobierz", str(tmp_path / "compose")], env=env,
                       capture_output=True, text=True, timeout=60)
    return r, log.read_text(encoding="utf-8") if log.exists() else ""


# drugi `docker pull` (po manifeście albo ponownej próbie) się udaje; pierwszy zwraca błąd z $BLAD
_PULL_DRUGI = ('case "$1" in\n'
               '  pull) if [ -f "$STAN" ]; then echo "a: Pulling fs layer"; echo "a: Pull complete"; exit 0; fi\n'
               '        touch "$STAN"; echo "$BLAD" >&2; exit 1;;\n'
               '  manifest) exit 0;;\n'
               'esac\nexit 0\n')


def test_obraz_waits_for_ci_build_of_fresh_change(tmp_path):
    """Świeża zmiana infra/: obrazu jeszcze nie ma (CI buduje) → czekamy na manifest zamiast budować na miejscu."""
    r, log = _obraz(tmp_path, _PULL_DRUGI, BLAD="manifest unknown: not found")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "GitHub Actions jeszcze buduje" in r.stdout and "pobrane warstwy: 1/1" in r.stdout
    assert "docker manifest inspect" in log and "docker tag" in log
    assert (tmp_path / "compose/.image-key").exists()
    # JARVO_IMAGE_WAIT=0: bez czekania, od razu budowa na miejscu
    r, log = _obraz(tmp_path / "bez", _PULL_DRUGI, BLAD="not found", JARVO_IMAGE_WAIT="0")
    assert r.returncode == 1 and "Brak gotowego obrazu" in r.stdout and "manifest inspect" not in log


def test_obraz_retries_broken_download_but_not_denied(tmp_path):
    r, log = _obraz(tmp_path, _PULL_DRUGI, BLAD="read: connection reset by peer")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "próbuję jeszcze raz" in r.stdout and log.count("docker pull") == 2
    # pakiet prywatny bez klucza: jedna próba, jasny komunikat, budowa na miejscu
    r, log = _obraz(tmp_path / "prywatny", _PULL_DRUGI, BLAD="denied: denied")
    assert r.returncode == 1 and "Rejestr odmówił" in r.stdout and log.count("docker pull") == 1


@pytest.mark.skipif(shutil.which("script") is None, reason="brak script (util-linux) do udawania terminala")
def test_dashboard_password_on_screen_not_in_install_log(tmp_path):
    """Koniec local-up.sh: hasło do HQ idzie na terminal, a install.log (tee) dostaje tylko `jarvo haslo`."""
    text = LOCAL_UP.read_text(encoding="utf-8")
    blok = text[text.index("JARVO=jarvo; command -v jarvo"):]
    (tmp_path / "L/compose").mkdir(parents=True)
    (tmp_path / "L/compose/.env").write_text("DASHBOARD_USER=jarvo\nDASHBOARD_PASSWORD=sekret123xyz\n", encoding="utf-8")
    (tmp_path / "blok.sh").write_text(blok, encoding="utf-8")
    log = tmp_path / "install.log"
    (tmp_path / "run.sh").write_text(
        f'L={tmp_path}/L ROOT={ROOT}\nexec > >(tee -a {log}) 2>&1\nsource {tmp_path}/blok.sh\nsleep 0.2\n', encoding="utf-8")
    ekran = tmp_path / "ekran.txt"
    subprocess.run(["script", "-qc", f"bash {tmp_path}/run.sh", str(ekran)], capture_output=True, timeout=30)
    assert "jarvo haslo" in log.read_text(encoding="utf-8")
    assert "sekret123xyz" not in log.read_text(encoding="utf-8")
    assert "sekret123xyz" in ekran.read_text(encoding="utf-8", errors="replace")


def test_local_up_prepare_without_terminal(tmp_path):
    """ssh 'curl | bash', cloud-init, Ansible: bez terminala read zwraca EOF; wybór domyślny zamiast cichego wyjścia."""
    res = subprocess.run(["bash", str(LOCAL_UP), "--prepare"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                         timeout=60, env={**os.environ, "JARVO_LOCAL": str(tmp_path / "L")})
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Bez terminala" in res.stdout and (tmp_path / "L/compose/.env").exists()


def _repo_sync(tmp_path: Path, bledy: list[str]) -> tuple[subprocess.CompletedProcess, str]:
    """repo_sync z install.sh na udawanym gicie: kolejne wywołania kończą się błędami z listy, potem sukcesem."""
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    log = tmp_path / "git.log"
    for i, b in enumerate(bledy):
        (tmp_path / f"blad{i}").write_text(b, encoding="utf-8")
    (bin_dir / "git").write_text(
        "#!/bin/bash\n"
        f'echo "git $*" >> {log}\n'
        'case "$*" in *" fetch "*) ;; *" clone "*) ;; *) exit 0 ;; esac\n'
        f'n=$(grep -cE " (fetch|clone) " {log}); f={tmp_path}/blad$((n-1))\n'
        'if [[ -f $f ]]; then cat "$f" >&2; exit 128; fi\n'
        'exit 0\n', encoding="utf-8")
    (bin_dir / "git").chmod(0o755)
    text = INSTALL.read_text(encoding="utf-8").rstrip().splitlines()
    (tmp_path / "fn.sh").write_text("\n".join(text[:-1]) + "\n", encoding="utf-8")   # bez main
    repo = tmp_path / "jarvo"; (repo / ".git").mkdir(parents=True)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "JARVO_GIT_PAUSE": "0", "JARVO_DIR": str(repo)}
    r = subprocess.run(["bash", "-c", f'source {tmp_path}/fn.sh; DIR={repo}; BRANCH=main; repo_sync; echo KONIEC'],
                       env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    return r, log.read_text(encoding="utf-8")


def test_repo_sync_retries_transient_git_error_without_token_prompt(tmp_path):
    """Równoległy git fetch pomocnika aktualizacji (updater.py) starej instalacji: chwilowy błąd refów, nie brak dostępu."""
    r, log = _repo_sync(tmp_path, ["error: fetching ref refs/remotes/origin/main failed: incorrect old value provided\n"])
    assert "KONIEC" in r.stdout, r.stdout + r.stderr
    assert log.count(" fetch ") == 2 and "klucz dostępu" not in r.stdout + r.stderr
    assert "próbuję jeszcze raz" in r.stdout + r.stderr


def test_repo_sync_access_denied_no_retry_and_clear_error(tmp_path):
    """Odmowa dostępu: bez ponawiania; bez terminala nie pytamy o klucz, tylko kończymy z treścią błędu gita."""
    blad = "fatal: could not read Username for 'https://github.com': terminal prompts disabled\n"
    r, log = _repo_sync(tmp_path, [blad, blad, blad])
    assert r.returncode == 1 and "KONIEC" not in r.stdout
    assert log.count(" fetch ") == 1
    assert "terminal prompts disabled" in r.stderr


def test_jarvo_update_ignores_broken_branch_config(tmp_path):
    """jarvo update pobiera swoją gałąź wprost (fetch + FETCH_HEAD): git pull padał u właściciela na
    „Cannot fast-forward to multiple branches” (dwa wpisy branch.main.merge) mimo czystego repo."""
    def git(*a, cwd=tmp_path):
        subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@t"})
    up, cl = tmp_path / "up", tmp_path / "cl"
    git("init", "-q", "-b", "main", str(up))
    (up / "bin").mkdir()
    shutil.copy2(JARVO, up / "bin/jarvo")
    (up / "install.sh").write_text('echo "INSTALL $JARVO_BRANCH"\n', encoding="utf-8")
    git("add", "-A", cwd=up); git("commit", "-q", "-m", "a", cwd=up)
    git("branch", "-q", "inna", cwd=up)
    git("clone", "-q", f"file://{up}", str(cl))
    git("commit", "-q", "--allow-empty", "-m", "nowa wersja", cwd=up)
    git("config", "--add", "branch.main.merge", "refs/heads/inna", cwd=cl)
    git("config", "--add", "remote.origin.fetch", "+refs/heads/inna:refs/remotes/origin/inna", cwd=cl)
    res = subprocess.run(["bash", str(cl / "bin/jarvo"), "update"], capture_output=True, text=True, timeout=60,
                         env={"PATH": os.environ["PATH"], "HOME": str(tmp_path), "JARVO_LOCAL": str(tmp_path / "local")})
    assert res.returncode == 0 and "INSTALL main" in res.stdout, res.stdout + res.stderr
    log = subprocess.run(["git", "-C", str(cl), "log", "--oneline", "-1"], capture_output=True, text=True).stdout
    assert "nowa wersja" in log
