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
    assert "apt-get install -y -q git curl python3 openssl ca-certificates" in out
    assert "get.docker.com" in out and "$ sudo env" in out and " sh /" in out
    assert "$ sudo -v" in out and out.index("$ sudo -v") < out.index("apt-get")   # hasło raz, przed pierwszym sudo
    assert "git clone -q --depth 50 -b main https://github.com/jarojarojaro-jaro/JARVO.git" in out
    assert "bin/jarvo up" in out
    assert "Koniec próby na sucho" in out
    assert not (tmp_path / "home/jarvo").exists() and not (tmp_path / "home/jarvo-local").exists()


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
    assert "apt-get install -y -q docker-buildx-plugin" in res.stdout and "get.docker.com" not in res.stdout


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
