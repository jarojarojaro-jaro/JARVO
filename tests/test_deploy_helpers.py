"""Skrypty wdrożenia: scalanie sekretów, configu hosta i czyszczenie skilli po zmianie buildu."""

from __future__ import annotations

import stat

import enable_plugin
import fleetlib as fl
import merge_env
import merge_host_config
import prune_skills


# ------------------------------------------------------------------ merge_env

def test_merge_env_updates_keeps_and_protects(tmp_path, capsys):
    src = tmp_path / "src.env"
    dst = tmp_path / "profile" / ".env"
    dst.parent.mkdir()
    dst.write_text("# komentarz Hermesa\nOPENROUTER_API_KEY=stary\nWLASNY=zostaje\nPUSTY_W_ZRODLE=istniejacy\n",
                   encoding="utf-8")
    src.write_text('OPENROUTER_API_KEY=nowy\nPUSTY_W_ZRODLE=\nNOWY="x y"\nexport EXPORTED=1\n# KOMENTARZ=nie\n',
                   encoding="utf-8")
    merge_env.main([str(src), str(dst)])
    lines = dst.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# komentarz Hermesa"
    assert "OPENROUTER_API_KEY=nowy" in lines
    assert "WLASNY=zostaje" in lines
    assert "PUSTY_W_ZRODLE=istniejacy" in lines           # pusta wartość w szablonie nie zeruje
    assert 'NOWY="x y"' in lines and "EXPORTED=1" in lines
    assert not any(line.startswith("KOMENTARZ") for line in lines)
    assert stat.S_IMODE(dst.stat().st_mode) == 0o600
    out = capsys.readouterr().out
    assert "nowy" not in out and "OPENROUTER_API_KEY" in out   # nazwy kluczy tak, wartości nigdy


def test_merge_env_missing_source_is_noop(tmp_path):
    dst = tmp_path / ".env"
    dst.write_text("A=1\n", encoding="utf-8")
    merge_env.main([str(tmp_path / "brak.env"), str(dst)])
    assert dst.read_text(encoding="utf-8") == "A=1\n"


# ------------------------------------------------------------ merge_host_config

def test_merge_host_config(tmp_path):
    fleet_cfg = tmp_path / "flota.yaml"
    target = tmp_path / "config.yaml"
    fleet_cfg.write_text(fl.dump_yaml({
        "model": {"default": "anthropic/claude-haiku-4.5", "provider": "openrouter"},
        "timezone": "Europe/Warsaw",
        "platform_toolsets": {"telegram": ["kanban"]},
        "gateway": {"multiplex_profiles": True, "profile_routes": [{"name": "owner-dm", "chat_id": "1"}]},
        "kanban": {"dispatch_in_gateway": True},
        "platforms": {"telegram": {"require_mention": True}},
        "tts": {"provider": "matcha", "providers": {"matcha": {"type": "command", "voice": "pl-PL-Matcha-Meski"}}},
    }), encoding="utf-8")
    target.write_text(fl.dump_yaml({
        "model": {"default": "wybrany/w-setupie"},
        "custom": {"zostaje": True},
        "platform_toolsets": {"telegram": ["terminal"], "discord": ["web"]},
        "gateway": {"profile_routes": [{"name": "stara"}], "port": 8080},
        "platforms": {"telegram": {"token_env": "TELEGRAM_BOT_TOKEN"}},
        "tts": {"provider": "edge", "edge": {"voice": "en-US-AriaNeural"}},
    }), encoding="utf-8")
    merge_host_config.main([str(fleet_cfg), str(target)])
    out = fl.load_yaml(target)
    assert out["model"]["default"] == "wybrany/w-setupie"          # nie nadpisujemy wyboru z setupu
    assert out["custom"] == {"zostaje": True}
    assert out["platform_toolsets"] == {"telegram": ["kanban"]}     # zastąpione w całości
    assert out["gateway"]["port"] == 8080 and out["gateway"]["multiplex_profiles"] is True
    assert out["gateway"]["profile_routes"] == [{"name": "owner-dm", "chat_id": "1"}]
    assert out["platforms"]["telegram"] == {"token_env": "TELEGRAM_BOT_TOKEN", "require_mention": True}
    assert out["kanban"]["dispatch_in_gateway"] is True
    assert out["timezone"] == "Europe/Warsaw"
    assert out["tts"]["provider"] == "matcha"                       # głos floty wygrywa z domyślnym Edge
    assert out["tts"]["providers"]["matcha"]["voice"] == "pl-PL-Matcha-Meski"


def test_merge_host_config_sets_model_when_missing(tmp_path):
    fleet_cfg = tmp_path / "flota.yaml"
    target = tmp_path / "config.yaml"
    fleet_cfg.write_text(fl.dump_yaml({"model": {"default": "anthropic/claude-haiku-4.5"}}), encoding="utf-8")
    merge_host_config.main([str(fleet_cfg), str(target)])
    assert fl.load_yaml(target)["model"]["default"] == "anthropic/claude-haiku-4.5"


def test_merge_host_config_force_model_on_first_run(tmp_path):
    fleet_cfg = tmp_path / "flota.yaml"
    target = tmp_path / "config.yaml"
    fleet_cfg.write_text(fl.dump_yaml({"model": {"default": "anthropic/claude-haiku-4.5", "provider": "openrouter"}}),
                         encoding="utf-8")
    target.write_text(fl.dump_yaml({"model": {"default": "przyklad/z-obrazu", "provider": "auto"}}), encoding="utf-8")
    merge_host_config.main([str(fleet_cfg), str(target), "--force-model"])
    assert fl.load_yaml(target)["model"] == {"default": "anthropic/claude-haiku-4.5", "provider": "openrouter"}


# ---------------------------------------------------------------- prune_skills

def skill(root, rel, frontmatter_extra="", vendored=False):
    d = root / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {d.name}\ndescription: test\n{frontmatter_extra}---\n\nTreść\n",
                                encoding="utf-8")
    if vendored:
        (d / ".vendored.json").write_text("{}", encoding="utf-8")
    return d


def test_prune_removes_only_managed_skills_missing_from_build(tmp_path):
    build, profile = tmp_path / "build", tmp_path / "profile"
    skill(build, "web/audyt-strony", "metadata:\n  jarvo:\n    agent: jarvo-web\n")
    skill(profile, "web/audyt-strony", "metadata:\n  jarvo:\n    agent: jarvo-web\n")
    old_own = skill(profile, "web/stary-workflow", "metadata:\n  jarvo:\n    agent: jarvo-web\n")
    old_vendor = skill(profile, "marketing/competitors", vendored=True)
    agent_made = skill(profile, "moje/wlasny-skill")
    hidden = skill(profile, ".archive/cos", "metadata:\n  jarvo:\n    agent: jarvo-web\n")

    prune_skills.main([str(build), str(profile), "--dry-run"])
    assert old_own.exists() and old_vendor.exists()

    prune_skills.main([str(build), str(profile)])
    assert not old_own.exists() and not old_vendor.exists()
    assert (profile / "web/audyt-strony").exists()
    assert agent_made.exists() and hidden.exists()


# ------------------------------------------------------------------ check-pins

def test_version_range_check():
    from conftest import load_script
    pins = load_script("scripts/check-pins.py")
    ok = pins.node_satisfies
    assert ok(None, "26.5.1") is True
    assert ok(">=22.18.0", "26.5.1") is True
    assert ok("^22.22.0 || >= 24.8.0", "26.5.1") is True
    assert ok("^22.22.0 || >= 24.8.0", "23.1.0") is False
    assert ok(">=18 <20", "26.5.1") is False
    assert ok("<4.0 >=3.11", "3.12.0") is True
    assert ok(">=3.13", "3.12.0") is False
    assert ok("!=3.0.*,!=3.1.*,>=2.7".replace(",", " "), "3.13.0") is True
    assert ok("!=3.14.1 >=3.12", "3.13.0") is True
    assert ok("!=3.14.1 >=3.12", "3.14.1") is False


# ------------------------------------------------------------------ deploy.sh --no-build, sandbox-up.sh

def _fake_docker(tmp_path, image_exists: bool, ncpu: int = 8):
    """Atrapa `docker`: zapisuje wywołania; `image inspect` zwraca 0 albo 1 (czy obraz jest), `info` liczbę CPU."""
    import os
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True)
    log = tmp_path / "docker.log"
    (bindir / "docker").write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$*" >> "{log}"\n'
        f'if [[ "$1 $2" == "image inspect" ]]; then exit {0 if image_exists else 1}; fi\n'
        f'if [[ "$1" == info ]]; then echo {ncpu}; exit 0; fi\n'
        "exit 0\n", encoding="utf-8")
    (bindir / "docker").chmod(0o755)
    compose = tmp_path / "compose"
    compose.mkdir()
    (compose / ".env").write_text("SEARXNG_SECRET=x\nDASHBOARD_PASSWORD=y\n", encoding="utf-8")
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "JARVO_COMPOSE_DIR": str(compose),
           "JARVO_BUILD": str(tmp_path / "build")}
    return env, log


def _deploy(env, *flags):
    """JARVO_TEST_BASH=/bin/bash na macOS (CI): ten sam test pod bashem 3.2 (puste tablice przy set -u)."""
    import os
    import subprocess
    return subprocess.run([os.environ.get("JARVO_TEST_BASH", "bash"), str(fl.REPO_ROOT / "scripts/deploy.sh"), *flags],
                          env=env, capture_output=True, text=True, timeout=60)


def test_deploy_no_build_never_builds_even_on_first_run(tmp_path):
    env, log = _fake_docker(tmp_path, image_exists=True)
    res = _deploy(env, "--no-pull", "--no-build", "--first-run")
    assert res.returncode == 0, res.stdout + res.stderr
    calls = log.read_text(encoding="utf-8")
    assert " up -d" in calls and " build " not in calls and "Budowa obrazu" not in res.stdout


def test_deploy_caps_cpus_to_docker(tmp_path):
    """Laptop z 2 rdzeniami (CI na GitHubie też): domyślne HERMES_CPUS=4 Docker by odrzucił przy starcie."""
    env, _log = _fake_docker(tmp_path, image_exists=True, ncpu=2)
    dot = tmp_path / "compose" / ".env"
    dot.write_text(dot.read_text(encoding="utf-8") + "HERMES_CPUS=4\n", encoding="utf-8")
    res = _deploy(env, "--no-pull", "--no-build")
    assert res.returncode == 0, res.stdout + res.stderr
    text = dot.read_text(encoding="utf-8")
    assert "HERMES_CPUS=2\n" in text and "HERMES_CPUS=4" not in text
    assert "ANDROID_CPUS" not in text   # 2 mieści się w 2 procesorach
    # 1 procesor: oba sufity w dół, brakująca zmienna dopisana
    env, _log = _fake_docker(tmp_path / "jeden", image_exists=True, ncpu=1)
    assert _deploy(env, "--no-pull", "--no-build").returncode == 0
    text = (tmp_path / "jeden" / "compose" / ".env").read_text(encoding="utf-8")
    assert "HERMES_CPUS=1\n" in text and "ANDROID_CPUS=1\n" in text


def test_deploy_keeps_cpus_that_fit(tmp_path):
    env, _log = _fake_docker(tmp_path, image_exists=True, ncpu=8)
    dot = tmp_path / "compose" / ".env"
    dot.write_text(dot.read_text(encoding="utf-8") + "HERMES_CPUS=6\n", encoding="utf-8")
    assert _deploy(env, "--no-pull", "--no-build").returncode == 0
    assert "HERMES_CPUS=6\n" in dot.read_text(encoding="utf-8")


def test_deploy_clears_old_service_image_pins(tmp_path):
    """Dawne IMAGE_* z compose.env.example i digesty z pin-images.sh nie zasłaniają wersji przypiętych w repo."""
    env, _log = _fake_docker(tmp_path, image_exists=True)
    dot = tmp_path / "compose" / ".env"
    wlasny = "IMAGE_REDROID=redroid/redroid:13.0.0-latest\n"
    dot.write_text(dot.read_text(encoding="utf-8") + "IMAGE_SEARXNG=searxng/searxng:latest\n"
                   f"IMAGE_VALKEY=valkey/valkey@sha256:{'a' * 64}\n" + wlasny
                   + "IMAGE_ANDROID_EMULATOR=halimqarroum/docker-android:api-33\n", encoding="utf-8")
    res = _deploy(env, "--no-pull", "--no-build")
    assert res.returncode == 0, res.stdout + res.stderr
    text = dot.read_text(encoding="utf-8")
    assert "IMAGE_SEARXNG=\n" in text and "IMAGE_VALKEY=\n" in text and "IMAGE_ANDROID_EMULATOR=\n" in text
    assert wlasny in text and "IMAGE_VALKEY: wersja przypięta w repo" in res.stdout


def test_deploy_points_container_at_this_repo(tmp_path):
    """Stara instalacja z JARVO_REPO na dawnym katalogu (~/TARS): lokalnie deploy.sh poprawia ścieżkę na repo,
    z którego wdraża (inaczej build w kontenerze idzie ze starego kodu), a na serwerze zatrzymuje się z komunikatem."""
    env, log = _fake_docker(tmp_path, image_exists=True)
    dot = tmp_path / "compose" / ".env"
    stare = tmp_path / "TARS"
    stare.mkdir()
    dot.write_text(dot.read_text(encoding="utf-8") + f"JARVO_REPO={stare}\n", encoding="utf-8")
    res = _deploy(env, "--no-pull", "--no-build")
    assert res.returncode == 1 and "Popraw JARVO_REPO" in res.stdout
    assert " up -d" not in log.read_text(encoding="utf-8")
    res = _deploy({**env, "JARVO_LOCAL_INSTALL": "1"}, "--no-pull", "--no-build")
    assert res.returncode == 0, res.stdout + res.stderr
    assert f"JARVO_REPO={fl.REPO_ROOT}\n" in dot.read_text(encoding="utf-8")
    assert "kontener czytał stary kod" in res.stdout
    # ścieżka już dobra: bez zmian i bez komunikatu
    res = _deploy(env, "--no-pull", "--no-build")
    assert res.returncode == 0 and "JARVO_REPO" not in res.stdout


def test_deploy_no_build_requires_existing_image(tmp_path):
    env, log = _fake_docker(tmp_path, image_exists=False)
    res = _deploy(env, "--no-pull", "--no-build")
    assert res.returncode == 1
    assert "Brak obrazu jarvo-hermes:local" in res.stdout
    assert " up -d" not in log.read_text(encoding="utf-8")


def test_deploy_komputer_blocks_public_ips_without_hostname_i(tmp_path):
    """Komputer na VPS: publiczne adresy hosta w KOMPUTER_BLOKADA także bez `hostname -I` (Arch, busybox: przez ip),
    a pusty wynik (adresów nie znaleziono) nie zdejmuje poprzedniej blokady."""
    env, _log = _fake_docker(tmp_path, image_exists=True)
    bindir = tmp_path / "bin"
    (bindir / "docker").write_text(
        (bindir / "docker").read_text(encoding="utf-8").replace(
            "exit 0\n", 'case "$*" in *"config --services"*) printf "hermes\\nkomputer\\n";; esac\nexit 0\n', 1),
        encoding="utf-8")
    for name, body in {"hostname": "exit 1\n", "uname": "echo Linux\n",
                       "ip": 'cat "$IP_OUT" 2>/dev/null\n'}.items():
        (bindir / name).write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
        (bindir / name).chmod(0o755)
    ip_out = tmp_path / "ip.txt"
    ip_out.write_text("2: eth0    inet 203.0.113.5/24 brd 203.0.113.255 scope global eth0\n"
                      "3: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\n", encoding="utf-8")
    env = {**env, "IP_OUT": str(ip_out)}
    dot = tmp_path / "compose" / ".env"
    if "microsoft" in open("/proc/version", encoding="utf-8").read().lower():
        return   # WSL: blokada dotyczy tylko zwykłego Linuksa
    assert _deploy(env, "--no-pull", "--no-build").returncode == 0
    assert "KOMPUTER_BLOKADA=203.0.113.5\n" in dot.read_text(encoding="utf-8")
    ip_out.write_text("", encoding="utf-8")
    res = _deploy(env, "--no-pull", "--no-build")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "KOMPUTER_BLOKADA=203.0.113.5\n" in dot.read_text(encoding="utf-8")


def test_sandbox_up_refuses_outside_sandbox(tmp_path):
    import os
    import subprocess
    env = {k: v for k, v in os.environ.items() if k.upper() != "HTTPS_PROXY"}
    env["JARVO_LOCAL"] = str(tmp_path / "local")
    res = subprocess.run(["bash", str(fl.REPO_ROOT / "scripts/sandbox-up.sh")], env=env,
                         capture_output=True, text=True, timeout=30)
    assert res.returncode == 1 and "to nie piaskownica" in res.stdout
    assert not (tmp_path / "local").exists()


# ------------------------------------------------------------------ enable_plugin

def test_enable_plugin_keeps_comments_and_removes_from_disabled(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("# konfiguracja hosta\nplugins:\n  enabled: [inny]\n  disabled: [jarvo-hq, stary]\nmodel: x  # zostaje\n",
                   encoding="utf-8")
    assert enable_plugin.main([str(cfg), "jarvo-hq"]) == 0
    assert enable_plugin.main([str(cfg), "jarvo-hq"]) == 0                     # drugi raz bez duplikatu
    data = fl.load_yaml(cfg)
    assert data["plugins"]["enabled"] == ["inny", "jarvo-hq"] and data["plugins"]["disabled"] == ["stary"]
    load, _dump = fl.rt_yaml()
    assert load(tmp_path / "brak.yaml") is None and data["model"] == "x"


# ------------------------------------------------- deploy.sh: start usług przy porcie zwalnianym z opóźnieniem

def _start_uslug(tmp_path, bledy: int, komunikat: str):
    """Pętla startu z deploy.sh z udawanym compose: pierwsze `bledy` prób kończy się `komunikat`, potem sukces."""
    import subprocess
    body = (fl.REPO_ROOT / "scripts/deploy.sh").read_text(encoding="utf-8")
    a = body.index('up_out="$(mktemp)"')
    b = body.index('rm -f "$up_out"\n', body.index("\ndone\n", a)) + len('rm -f "$up_out"\n')
    licznik = tmp_path / "proby"
    licznik.write_text("0", encoding="utf-8")
    fake = (f'compose() {{ n=$(( $(cat {licznik}) + 1 )); echo $n > {licznik}; '
            f'if (( n <= {bledy} )); then echo "{komunikat}"; return 1; fi; echo "Container jarvo-hermes Started"; }}\n')
    script = ("set -euo pipefail\nsleep() { :; }\nfail() { echo \"FAIL $*\"; exit 1; }\n" + fake
              + "COMPOSE=(compose)\nPROFILES=()\n" + body[a:b] + "echo GOTOWE\n")
    res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    return res, int(licznik.read_text())


def test_deploy_retries_port_released_late(tmp_path):
    port = ("Error response from daemon: ports are not available: exposing port TCP 127.0.0.1:9120 -> 127.0.0.1:0: "
            "/forwards/expose returned unexpected status: 500")
    res, n = _start_uslug(tmp_path, 2, port)
    assert res.returncode == 0 and "GOTOWE" in res.stdout and n == 3, res.stdout + res.stderr
    assert "ponawiam za 5 s (próba 2/4)" in res.stdout and "ponawiam za 10 s (próba 3/4)" in res.stdout
    res, n = _start_uslug(tmp_path, 9, port)   # dalej zajęty po 4 próbach: błąd z radą
    assert res.returncode == 1 and n == 4 and "FAIL Port floty" in res.stdout and "wsl --shutdown" in res.stdout


def test_deploy_other_start_error_fails_at_once(tmp_path):
    res, n = _start_uslug(tmp_path, 1, "Error response from daemon: no such image")
    assert res.returncode == 1 and n == 1 and "FAIL Usługi nie wystartowały" in res.stdout
