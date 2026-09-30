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
from pathlib import Path

import pytest

import fleetlib as fl

ROOT = fl.REPO_ROOT
INSTALL = ROOT / "install.sh"
JARVO = ROOT / "bin/jarvo"
LOCAL_UP = ROOT / "scripts/local-up.sh"
SCRIPTS = [INSTALL, JARVO, LOCAL_UP]
# programy, których instalator ma doinstalować, gdy ich brak (poza PATH testu)
TOOLS = ("git", "curl", "python3", "openssl", "docker")


def _shim(bin_dir: Path, name: str, body: str) -> None:
    p = bin_dir / name
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
           "JARVO_DRY_RUN": "1", "JARVO_DIR": str(tmp_path / "home/jarvo"), "JARVO_OS_RELEASE": str(os_release)}
    env.update(extra)
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    return subprocess.run(["bash", str(INSTALL)], env=env, capture_output=True, text=True, timeout=60)


# ---------------------------------------------------------------- składnia i lint

def test_scripts_parse():
    for s in SCRIPTS:
        assert subprocess.run(["bash", "-n", str(s)], capture_output=True).returncode == 0, s
    text = INSTALL.read_text(encoding="utf-8").rstrip().splitlines()
    assert text[-1] == 'main "$@"', "install.sh: całość w main (curl | bash wykonuje dopiero po pobraniu)"
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
    assert "apt-get install -y -q git curl python3 openssl ca-certificates" in out
    assert "get.docker.com" in out and "$ sudo env" in out and " sh /" in out
    assert "git clone" in out and "bin/jarvo up" in out
    assert "Koniec próby na sucho" in out
    assert not (tmp_path / "home/jarvo").exists() and not (tmp_path / "home/jarvo-local").exists()


def test_dry_run_fedora_and_arch(tmp_path):
    fedora = _dry(tmp_path / "f", _os_release(tmp_path, "fedora"))
    assert fedora.returncode == 0, fedora.stdout + fedora.stderr
    # dnf, a gdy go nie ma na maszynie testowej: yum (ten sam wiersz poleceń)
    assert ("dnf install -y git curl python3 openssl" in fedora.stdout
            or "yum install -y git curl python3 openssl" in fedora.stdout) and "get.docker.com" in fedora.stdout
    arch = _dry(tmp_path / "a", _os_release(tmp_path, "manjaro", "arch"))
    assert arch.returncode == 0, arch.stdout + arch.stderr
    assert "pacman -Sy --noconfirm --needed git curl python openssl" in arch.stdout
    assert "pacman -Sy --noconfirm --needed docker docker-compose" in arch.stdout


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
    assert "usermod -aG docker tester" in res.stdout     # udawany użytkownik nie jest w grupie docker


def test_low_ram_refuses_unless_forced(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:        2000000 kB\n", encoding="utf-8")
    res = _dry(tmp_path / "1", _os_release(tmp_path, "ubuntu"), JARVO_MEMINFO=str(meminfo))
    assert res.returncode == 1 and "Za mało RAM" in res.stderr
    res = _dry(tmp_path / "2", _os_release(tmp_path, "ubuntu"), JARVO_MEMINFO=str(meminfo), JARVO_FORCE="1")
    assert res.returncode == 0, res.stdout + res.stderr


def test_setup_only_and_no_secrets_in_output(tmp_path):
    res = _dry(tmp_path, _os_release(tmp_path, "ubuntu"), JARVO_SETUP_ONLY="1", JARVO_KEY="sk-tajny-klucz-123")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "JARVO_SETUP_ONLY=1" in res.stdout and "bin/jarvo up" not in res.stdout
    assert "sk-tajny-klucz-123" not in res.stdout + res.stderr


# ---------------------------------------------------------------- bin/jarvo

def _jarvo(*args, **env_extra) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_extra}
    return subprocess.run(["bash", str(JARVO), *args], env=env, capture_output=True, text=True, timeout=30)


def test_jarvo_help_version_and_unknown():
    assert _jarvo("help").returncode == 0
    assert "jarvo uninstall" in _jarvo("help").stdout
    assert _jarvo("bogus").returncode == 2
    assert _jarvo("version").returncode == 0


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
