"""Hermes natywnie (jarvo/hermes.py; docs/NATYWNIE.md H01–H03, H13, H16, H23, H24, I13): checkout przypiętego
commitu, zależności z uv.lock i zależności budowy z sumą (bez izolowanej budowy z PyPI), front dashboardu z npm
i bezpieczna konfiguracja przez CLI Hermesa. git, uv i npm to atrapy (tests/atrapy.py); CLI Hermesa to atrapa pakietu
hermes_cli w prawdziwym venvie, więc argv_hermesa() działa bez podmian (na Windows z launcherem venvu). Bez sieci."""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

import atrapy
from conftest import REPO, uruchom_bash

sys.path.insert(0, str(REPO))
from jarvo import hermes, przenosne, sciezki, srodowisko  # noqa: E402

WINDOWS = os.name == "nt"
COMMIT = "f97608f178d1ffeca59860195ab7da295f7c8e5f"
PIN = {"repo": "https://example.invalid/hermes-agent", "tag": "v2026.9.24", "commit": COMMIT, "wersja": "0.21.5",
       "dodatki": ["all", "messaging"]}
BEZ_CWD = "NoDefaultCurrentDirectoryInExePath"
WYMAGANIA_BUDOWY = (
    "setuptools==83.0.0 --hash=sha256:29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3\n"
    "wheel==0.48.0 --hash=sha256:3217dcc807155e45db462d7ef2431f5ddda0d7273b700d05a67b271ceb1287ab\n")

# wspólny początek atrap: każde wywołanie dopisuje argv, katalog i wybrane zmienne do dziennika JSONL
DZIENNIK = r'''
import json, os, sys
from pathlib import Path

def dziennik(program, **dodatki):
    env = {k.lower(): v for k, v in os.environ.items()
           if k.upper().startswith(("UV_", "GIT_", "GCM_", "NPM_CONFIG_", "XDG_CONFIG", "APPDATA", "NODE_ENV",
                                    "NO_COLOR", "NODEFAULTCURRENTDIRECTORYINEXEPATH")) or k.upper() == "PATH"}
    with open(os.environ["ATRAPA_DZIENNIK"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"program": program, "argv": sys.argv[1:], "cwd": os.getcwd(), "env": env, **dodatki})
                + "\n")
'''

GIT = DZIENNIK + r'''
dziennik("git")
argv = sys.argv[1:]
while argv[:1] == ["-c"]:
    argv = argv[2:]
polecenie, reszta = argv[0], argv[1:]
if polecenie == "clone":
    pozycyjne, i = [], 0
    while i < len(reszta):
        if reszta[i] == "-c":
            i += 2
        elif reszta[i].startswith("-"):
            i += 1
        else:
            pozycyjne.append(reszta[i])
            i += 1
    if os.environ.get("ATRAPA_GIT_KLON_BLAD"):
        print(f"fatal: repository '{pozycyjne[0]}' not found", file=sys.stderr)
        sys.exit(128)
    cel = Path(pozycyjne[1])
    (cel / ".git" / "info").mkdir(parents=True)
    (cel / ".git" / "info" / "exclude").write_text("# git ls-files --others --exclude-from=.git/info/exclude\n",
                                                   encoding="utf-8")
    (cel / ".git" / "HEAD_ATRAPY").write_text("1" * 40, encoding="utf-8")
    print("Receiving objects: 100% (10/10), done.", file=sys.stderr)
elif polecenie == "cat-file":
    print("commit")
elif polecenie == "checkout":
    Path(".git", "HEAD_ATRAPY").write_text(os.environ.get("ATRAPA_GIT_HEAD") or reszta[-1], encoding="utf-8")
    budowa = os.environ.get("ATRAPA_BUDOWA") or '["setuptools==83.0.0", "wheel"]'     # jak [build-system] f97608f
    tresc = "[project]\nname = 'hermes-agent'\nversion = '0.21.5'\n"
    if budowa != "brak":
        tresc += f"\n[build-system]\nrequires = {budowa}\nbuild-backend = 'setuptools.build_meta'\n"
    Path("pyproject.toml").write_text(tresc, encoding="utf-8")
    Path("web").mkdir(exist_ok=True)
    Path("web", "package.json").write_text("{}", encoding="utf-8")
elif polecenie == "rev-parse":
    print(Path(".git", "HEAD_ATRAPY").read_text(encoding="utf-8"))
elif polecenie == "fetch":
    pass
else:
    sys.exit("atrapa git: nie znam polecenia " + polecenie)
'''

# atrapa uv: sync bez projektu zakłada venv, pip install kładzie zależności budowy, sync z budową bez nich pada
UV = DZIENNIK + r'''
argv = sys.argv[1:]
venv = Path(".venv")
python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if argv[:1] == ["sync"]:
    dziennik("uv")
    if os.environ.get("ATRAPA_UV_BLAD"):
        print("Resolved 312 packages in 9ms", file=sys.stderr)
        print("error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided. To update the "
              "lockfile, run `uv lock`.", file=sys.stderr)
        sys.exit(2)
    if "--no-install-project" in argv:
        python.parent.mkdir(parents=True, exist_ok=True)
        python.write_bytes(b"")
        print("Installed 2 packages in 5ms", file=sys.stderr)
        print(" + aiohttp==3.14.3", file=sys.stderr)
    elif not (venv / "atrapa-budowa.txt").is_file():
        print("ModuleNotFoundError: No module named 'setuptools'", file=sys.stderr)
        sys.exit(1)
    else:
        print(" + hermes-agent==0.21.5 (from file:///hermes-agent)", file=sys.stderr)
        print(" - setuptools==83.0.0", file=sys.stderr)
elif argv[:2] == ["pip", "install"]:
    wymagania = Path(argv[argv.index("-r") + 1]).read_text(encoding="utf-8")
    dziennik("uv", wymagania=wymagania)
    if os.path.normcase(os.path.abspath(argv[argv.index("--python") + 1])) != os.path.normcase(os.path.abspath(python)):
        sys.exit("atrapa uv: pip install tylko do venvu checkoutu")
    if os.environ.get("ATRAPA_UV_SUMA"):
        print("error: Hash mismatch for `wheel==0.48.0`", file=sys.stderr)
        sys.exit(1)
    (venv / "atrapa-budowa.txt").write_text(wymagania, encoding="utf-8")
    print(" + setuptools==83.0.0", file=sys.stderr)
else:
    sys.exit("atrapa uv: nie znam " + " ".join(argv))
'''

NPM = DZIENNIK + r'''
dziennik("npm")
argv = sys.argv[1:]
if os.environ.get("ATRAPA_NPM_BLAD"):
    print("npm error code EBADENGINE", file=sys.stderr)
    sys.exit(1)
if argv[0] == "ci":
    Path("..", "node_modules").mkdir(exist_ok=True)
elif argv[:2] == ["run", "build"]:
    dist = Path("..", "hermes_cli", "web_dist")
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    print("../hermes_cli/web_dist/assets/index-abc.js  12.30 kB")
    print("\x1b[32mbuilt in 4.03s\x1b[39m\x1b[2K")
else:
    sys.exit("atrapa npm: nie znam " + " ".join(argv))
'''

# atrapa CLI Hermesa (pakiet hermes_cli w venvie): -p <profil>, lepki active_profile, config get/set i --version
# jak w f97608f
CLI = r'''
import json, os, sys
from pathlib import Path

DOMYSLNE = {"security.tirith_enabled": True, "security.allow_lazy_installs": True,
            "auth.adopt_external_logins": True, "updates.check": True, "terminal.home_mode": "auto",
            "terminal.auto_source_bashrc": True, "terminal.shell_init_files": []}
for brak in filter(None, os.environ.get("ATRAPA_BRAK_POL", "").split(",")):
    DOMYSLNE.pop(brak, None)
argv = sys.argv[1:]
profil = None
if "-p" in argv:
    i = argv.index("-p")
    profil = argv[i + 1]
    del argv[i:i + 2]
home = Path(os.environ["HERMES_HOME"])
if profil is None and (home / "active_profile").is_file():         # hermes_cli/main.py:593
    profil = (home / "active_profile").read_text(encoding="utf-8").strip()
if profil and profil != "default":
    home = home / "profiles" / profil
plik = home / "atrapa-config.json"
stan = json.loads(plik.read_text(encoding="utf-8")) if plik.exists() else {}
with open(os.environ["ATRAPA_DZIENNIK"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"program": "hermes", "argv": sys.argv[1:], "home": str(home), "cwd": os.getcwd(),
                        "safe_path": bool(sys.flags.safe_path)}) + "\n")
if argv == ["--version"]:
    print("Hermes Agent v0.21.5 (2026.9.24) · upstream 266a8731")
    print("Install method: git")
    if {**DOMYSLNE, **stan}.get("updates.check", True):
        print("Update available: 3 commits behind — run 'hermes update'")
elif argv[:2] == ["config", "get"]:
    if argv[2] not in DOMYSLNE:
        print(f"Config key not set: {argv[2]}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({**DOMYSLNE, **stan}[argv[2]]))
elif argv[:2] == ["config", "set"]:
    klucz, wartosc = argv[2], argv[3]
    domyslna = DOMYSLNE.get(klucz)
    if isinstance(domyslna, bool):
        stan[klucz] = {"false": False, "true": True}.get(wartosc.lower(), wartosc)
    elif isinstance(domyslna, list) and wartosc.lstrip().startswith("["):
        stan[klucz] = json.loads(wartosc)                     # Hermes: yaml.safe_load listy (config.py:3266)
    else:
        stan[klucz] = wartosc
    home.mkdir(parents=True, exist_ok=True)
    plik.write_text(json.dumps(stan), encoding="utf-8")
    print(f"✓ Set {klucz} = {wartosc} in {home / 'config.yaml'}")
else:
    sys.exit("atrapa hermes: nie znam " + " ".join(argv))
'''

# śpioch: proces z wnukiem, który co chwilę zapisuje puls; po zatrzymaniu drzewa puls staje
SPIOCH = r'''
import os, subprocess, sys, time
from pathlib import Path
puls = Path(os.environ["ATRAPA_PULS"])
if sys.argv[1:] == ["wnuk"]:
    while True:
        puls.write_text(str(time.monotonic()), encoding="utf-8")
        time.sleep(0.05)
subprocess.Popen([sys.executable, os.path.abspath(sys.argv[0]), "wnuk"])
print("start", flush=True)
time.sleep(120)
'''


def _ta_sama(a, b) -> bool:
    return os.path.normcase(os.path.realpath(str(a))) == os.path.normcase(os.path.realpath(str(b)))


def _uklad(tmp_path: Path) -> sciezki.Uklad:
    return sciezki.uklad({"JARVO_ROOT": str(tmp_path / "jarvo")})


def _cicho(_linia: str) -> None:
    pass


class Atrapy:
    def __init__(self, katalog: Path, dziennik: Path):
        self.katalog, self.dziennik = katalog, dziennik
        self.git = atrapy.program(katalog, "git", GIT)
        self.uv = atrapy.program(katalog, "uv", UV)
        self.npm = atrapy.program(katalog, "npm", NPM)

    def wpisy(self, program: str | None = None) -> list[dict]:
        if not self.dziennik.exists():
            return []
        wszystkie = [json.loads(x) for x in self.dziennik.read_text(encoding="utf-8").splitlines() if x.strip()]
        return [w for w in wszystkie if program in (None, w["program"])]

    def wyczysc(self) -> None:
        self.dziennik.unlink(missing_ok=True)

    def instaluj(self, u: sciezki.Uklad, pin: dict = PIN, log=_cicho) -> Path:
        return hermes.zainstaluj(u, pin, git=self.git, uv=self.uv, python=sys.executable, log=log)


@pytest.fixture
def atrapa(tmp_path, monkeypatch):
    dziennik = tmp_path / "dziennik.jsonl"
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(dziennik))
    for zmienna in ("ATRAPA_GIT_HEAD", "ATRAPA_GIT_KLON_BLAD", "ATRAPA_UV_BLAD", "ATRAPA_UV_SUMA", "ATRAPA_BUDOWA",
                    "ATRAPA_NPM_BLAD", "NODE_ENV"):
        monkeypatch.delenv(zmienna, raising=False)
    return Atrapy(tmp_path / "bin", dziennik)


def test_argv_hermesa_to_python_venvu_checkoutu_bez_biezacego_katalogu(tmp_path):
    assert hermes.argv_hermesa(tmp_path / "h", "config", "get", "x") == [
        str(srodowisko.hermes_python(tmp_path / "h")), "-P", "-m", "hermes_cli.main", "config", "get", "x"]
    assert hermes.katalog_checkoutu(_uklad(tmp_path), COMMIT) == _uklad(tmp_path).program / "hermes" / COMMIT[:12]


def test_zainstaluj_checkout_zaleznosci_z_sumami_a_drugi_przebieg_nic_nie_robi(atrapa, tmp_path, monkeypatch):
    # odziedziczone po właścicielu: UV_NO_CONFIG, indeks i UV_NO_SYSTEM_CONFIG=0 nie mogą dojść do uv, GIT_DIR nie
    # może przekierować gita, względne wpisy PATH (bieżący katalog) nie przechodzą; UV_NATIVE_TLS dotyczy sieci
    monkeypatch.setenv("UV_NO_CONFIG", "1")
    monkeypatch.setenv("UV_INDEX_URL", "https://zly.invalid/simple")
    monkeypatch.setenv("UV_NO_SYSTEM_CONFIG", "0")
    monkeypatch.setenv("UV_NATIVE_TLS", "1")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "obce-repo"))
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", "bin", os.environ.get("PATH", "")]))
    monkeypatch.delenv(BEZ_CWD, raising=False)
    u = _uklad(tmp_path)
    logi: list[str] = []
    checkout = atrapa.instaluj(u, log=logi.append)
    assert checkout == u.program / "hermes" / COMMIT[:12] and checkout.is_dir()
    assert not checkout.with_name(checkout.name + ".new").exists()

    git = atrapa.wpisy("git")
    klon = next(w for w in git if "clone" in w["argv"])
    assert {"--filter=blob:none", "--no-checkout", PIN["repo"]} <= set(klon["argv"])
    assert Path(klon["argv"][-1]).name == COMMIT[:12] + ".new"          # klon obok, nazwa dopiero po kontroli HEAD
    co = next(w for w in git if "checkout" in w["argv"])
    i = co["argv"].index("checkout")
    assert co["argv"][i + 1:] == [COMMIT]
    assert {"core.longpaths=true", "core.autocrlf=false", "http.lowSpeedLimit=1000",
            "http.lowSpeedTime=120"} <= set(co["argv"][:i])                # zastygłe dociąganie blobów też zerwie
    assert any(w["argv"][-2:] == ["rev-parse", "HEAD"] for w in git)
    assert all(w["env"].get("git_terminal_prompt") == "0" and "git_dir" not in w["env"] for w in git)

    sync, pip, budowa = atrapa.wpisy("uv")
    extras = ["--extra", "all", "--extra", "messaging"]
    assert sync["argv"] == ["sync", "--locked", "--no-install-project", "--no-build", *extras]   # same koła z locka
    assert pip["argv"][:2] == ["pip", "install"] and pip["argv"][2] == "--python"
    assert _ta_sama(pip["argv"][3], srodowisko.hermes_python(checkout))
    assert pip["argv"][4:-1] == ["--no-config", "--require-hashes", "--no-deps", "--only-binary", ":all:", "-r"]
    assert pip["wymagania"] == WYMAGANIA_BUDOWY and not Path(pip["argv"][-1]).exists()   # plik wymagań sprzątnięty
    assert budowa["argv"] == ["sync", "--locked", "--no-build-isolation", "--offline", *extras]
    for w in (sync, pip, budowa):
        assert _ta_sama(w["cwd"], checkout)
        env = w["env"]
        assert _ta_sama(env["uv_python"], sys.executable) and env["uv_python_downloads"] == "never"
        assert _ta_sama(env["uv_cache_dir"], u.cache / "uv") and env["uv_link_mode"] == "copy"
        assert env["uv_no_system_config"] == "1"                          # bez uv.toml z ProgramData i /etc
        assert "uv_no_config" not in env and "uv_index_url" not in env and env.get("uv_native_tls") == "1"
        pusty = u.stan / "bez-konfiguracji-uv"                            # zamiast uv.toml właściciela
        if WINDOWS:
            assert _ta_sama(env["appdata"], pusty)
        else:
            assert _ta_sama(env["xdg_config_home"], pusty) and _ta_sama(env["xdg_config_dirs"], pusty)
        assert pusty.is_dir() and not any(pusty.iterdir())
    for w in atrapa.wpisy():
        sciezka = w["env"]["path"].split(os.pathsep)
        assert all(Path(k).is_absolute() for k in sciezka if k)  and "" not in sciezka
        if WINDOWS:
            assert w["env"]["nodefaultcurrentdirectoryinexepath"] == "1"   # cmd.exe i which dzieci: bez cwd
    assert not list(u.stan.glob("hermes-budowa-*"))

    znacznik = json.loads((checkout / hermes.ZNACZNIK).read_text(encoding="utf-8"))
    assert znacznik["commit"] == COMMIT and znacznik["dodatki"] == ["all", "messaging"]
    assert znacznik["budowa"] == ["setuptools==83.0.0", "wheel==0.48.0"]
    wyklucz = (checkout / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
    assert f"/{hermes.ZNACZNIK}" in wyklucz and f"/{hermes.ZNACZNIK_WEB}" in wyklucz
    assert not [x for x in logi if "aiohttp==" in x] and "gotowy" in logi[-1]   # lista paczek nie zasypuje logu
    assert BEZ_CWD not in os.environ                                           # przywrócone po szukaniu programów

    # drugi przebieg: żadnego wywołania (gita i uv może już nawet nie być)
    atrapa.wyczysc()
    assert hermes.zainstaluj(u, PIN, git=tmp_path / "nie-ma-gita", uv=tmp_path / "nie-ma-uv", python=sys.executable,
                             log=logi.append) == checkout
    assert atrapa.wpisy() == [] and "już zainstalowany" in logi[-1]

    # inne dodatki w pinie: tylko kroki uv, bez nowego klonu
    atrapa.instaluj(u, dict(PIN, dodatki=["all"]))
    assert [w["argv"][:3] for w in atrapa.wpisy("uv")] == [["sync", "--locked", "--no-install-project"],
                                                          ["pip", "install", "--python"],
                                                          ["sync", "--locked", "--no-build-isolation"]]
    assert atrapa.wpisy("uv")[-1]["argv"][-2:] == ["--extra", "all"]
    assert not [w for w in atrapa.wpisy("git") if "clone" in w["argv"] or "checkout" in w["argv"]]


def test_brak_build_system_to_sam_setuptools(atrapa, tmp_path, monkeypatch):
    monkeypatch.setenv("ATRAPA_BUDOWA", "brak")                  # PEP 517: bez [build-system] buduje setuptools
    atrapa.instaluj(_uklad(tmp_path))
    [pip] = [w for w in atrapa.wpisy("uv") if w["argv"][:2] == ["pip", "install"]]
    assert pip["wymagania"] == WYMAGANIA_BUDOWY.splitlines(keepends=True)[0]


@pytest.mark.parametrize("budowa, fragment", [
    ('["hatchling"]', "'hatchling'"),
    ('["setuptools==99.0.0", "wheel"]', "'setuptools==99.0.0'"),
    ('["setuptools>=61", "wheel"]', "'setuptools>=61'"),
])
def test_zaleznosc_budowy_bez_przypietej_sumy_zatrzymuje_przed_uv(atrapa, tmp_path, monkeypatch, budowa, fragment):
    monkeypatch.setenv("ATRAPA_BUDOWA", budowa)
    with pytest.raises(hermes.BladHermesa, match=re.escape(fragment)) as blad:
        atrapa.instaluj(_uklad(tmp_path))
    assert "bez sumy" in str(blad.value) and "setuptools==83.0.0" in str(blad.value)
    assert atrapa.wpisy("uv") == []


def test_inny_head_niz_pin_zatrzymuje_instalacje(atrapa, tmp_path, monkeypatch):
    u = _uklad(tmp_path)
    monkeypatch.setenv("ATRAPA_GIT_HEAD", "e" * 40)
    with pytest.raises(hermes.BladHermesa, match="nie instaluję kodu innego niż przypięty"):
        atrapa.instaluj(u)
    assert not (u.program / "hermes" / COMMIT[:12]).exists() and atrapa.wpisy("uv") == []
    # istniejący katalog z innym commitem albo bez gita: błąd z poradą, bez poprawiania cudzych zmian
    docelowy = u.program / "hermes" / COMMIT[:12]
    (docelowy / ".git").mkdir(parents=True)
    (docelowy / ".git" / "HEAD_ATRAPY").write_text("e" * 40, encoding="utf-8")
    with pytest.raises(hermes.BladHermesa, match="ma commit eeeeeeeeeeee"):
        atrapa.instaluj(u)
    (docelowy / ".git" / "HEAD_ATRAPY").unlink()
    (docelowy / ".git").rmdir()
    with pytest.raises(hermes.BladHermesa, match="nie jest checkoutem gita"):
        atrapa.instaluj(u)
    assert atrapa.wpisy("uv") == []


def test_przerwany_klon_usuniety_takze_z_plikami_tylko_do_odczytu(atrapa, tmp_path):
    u = _uklad(tmp_path)
    paczka = u.program / "hermes" / f"{COMMIT[:12]}.new" / ".git" / "objects" / "pack" / "pack-1.pack"
    paczka.parent.mkdir(parents=True)
    paczka.write_bytes(b"PACK")
    paczka.chmod(stat.S_IREAD)                 # git zostawia paczki tylko do odczytu; Windows nie skasuje ich wprost
    checkout = atrapa.instaluj(u)
    assert (checkout / hermes.ZNACZNIK).is_file() and not paczka.exists()
    assert not checkout.with_name(checkout.name + ".new").exists()


def test_resztki_klonu_trzymane_przez_inny_program_to_blad_z_porada(atrapa, tmp_path, monkeypatch):
    u = _uklad(tmp_path)
    (u.program / "hermes" / f"{COMMIT[:12]}.new").mkdir(parents=True)

    def zajete(_p):
        raise PermissionError(32, "plik używany przez inny proces")
    monkeypatch.setattr(hermes, "_usun_drzewo", zajete)
    with pytest.raises(hermes.BladHermesa, match="resztki przerwanej instalacji"):
        atrapa.instaluj(u)
    assert atrapa.wpisy() == []


def test_blad_locka_to_wyjatek_bez_obejscia_bez_sum(atrapa, tmp_path, monkeypatch):
    u = _uklad(tmp_path)
    monkeypatch.setenv("ATRAPA_UV_BLAD", "lock")
    with pytest.raises(hermes.BladHermesa) as blad:
        atrapa.instaluj(u)
    tekst = str(blad.value)
    assert "uv.lock nie pasuje" in tekst and "bez sum" in tekst and "needs to be updated" in tekst
    assert [w["argv"][:2] for w in atrapa.wpisy("uv")] == [["sync", "--locked"]]   # jedna próba, nic w zastępstwie
    checkout = u.program / "hermes" / COMMIT[:12]
    assert checkout.is_dir() and not (checkout / hermes.ZNACZNIK).exists()
    # po naprawie: ten sam checkout (bez klonu), kroki uv jeszcze raz
    monkeypatch.delenv("ATRAPA_UV_BLAD")
    atrapa.wyczysc()
    assert atrapa.instaluj(u) == checkout
    assert not [w for w in atrapa.wpisy("git") if "clone" in w["argv"]] and len(atrapa.wpisy("uv")) == 3
    assert (checkout / hermes.ZNACZNIK).is_file()


def test_zla_suma_zaleznosci_budowy_zatrzymuje_przed_budowa(atrapa, tmp_path, monkeypatch):
    u = _uklad(tmp_path)
    monkeypatch.setenv("ATRAPA_UV_SUMA", "1")
    with pytest.raises(hermes.BladHermesa, match="suma pliku z PyPI nie zgadza się") as blad:
        atrapa.instaluj(u)
    assert "uv pip install --require-hashes" in str(blad.value)
    assert [w["argv"][:2] for w in atrapa.wpisy("uv")] == [["sync", "--locked"], ["pip", "install"]]
    assert not (u.program / "hermes" / COMMIT[:12] / hermes.ZNACZNIK).exists()
    assert not list(u.stan.glob("hermes-budowa-*"))


def test_blad_klonu_w_komunikacie_i_token_w_adresie_maskowany(atrapa, tmp_path, monkeypatch):
    monkeypatch.setenv("ATRAPA_GIT_KLON_BLAD", "1")
    logi: list[str] = []
    with pytest.raises(hermes.BladHermesa, match="git clone") as blad:
        atrapa.instaluj(_uklad(tmp_path), log=logi.append)
    assert "not found" in str(blad.value) and atrapa.wpisy("uv") == []
    assert hermes._bez_sekretow("fatal: https://ktos:tajny-token@example.invalid/r") == \
        "fatal: https://***@example.invalid/r"
    assert hermes._bez_sekretow("https://ghp_tajnytoken@github.com/x/y") == "https://***@github.com/x/y"


@pytest.mark.parametrize("zmiana, fragment", [
    ({"commit": "f97608f"}, "pełnym SHA"),
    ({"repo": "http://example.invalid/hermes-agent"}, "https"),
    ({"repo": "https://ktos:tajny-token@example.invalid/hermes-agent"}, "bez loginu i tokenu"),
    ({"repo": "https://tajny-token@example.invalid/hermes-agent"}, "bez loginu i tokenu"),
    ({"dodatki": ["all", "--no-locked"]}, "extras"),
    ({"dodatki": "all"}, "extras"),
])
def test_zly_pin_odrzucony_przed_uruchomieniem(atrapa, tmp_path, zmiana, fragment):
    with pytest.raises(hermes.BladHermesa, match=fragment) as blad:
        atrapa.instaluj(_uklad(tmp_path), dict(PIN, **zmiana))
    assert "tajny-token" not in str(blad.value)        # token z adresu nie trafia do komunikatu ani do .git/config
    assert atrapa.wpisy() == []


def test_programy_tylko_po_pelnej_sciezce_nigdy_z_biezacego_katalogu(atrapa, tmp_path, monkeypatch):
    # podrzucony git (na Windows git.cmd, który shutil.which bierze przez PATHEXT) w katalogu, z którego ruszył
    # instalator (np. Pobrane); runner windows-2025 nie ma NoDefaultCurrentDirectoryInExePath
    pobrane = tmp_path / "Pobrane"
    atrapy.program(pobrane, "git", "import sys; sys.exit('podrzucony git')")
    monkeypatch.chdir(pobrane)
    monkeypatch.delenv(BEZ_CWD, raising=False)
    u = _uklad(tmp_path)
    for path in (str(tmp_path / "pusto"), os.pathsep.join(["", ".", "Pobrane"])):   # względne wpisy = bieżący katalog
        monkeypatch.setenv("PATH", path)
        with pytest.raises(hermes.BladHermesa, match="Nie znalazłem programu git"):
            hermes.zainstaluj(u, PIN, git="git", uv=atrapa.uv, python=sys.executable, log=_cicho)
    # goła nazwa: program z katalogu bezwzględnego w PATH, nie z bieżącego
    monkeypatch.setenv("PATH", os.pathsep.join([".", str(atrapa.katalog)]))
    assert _ta_sama(hermes._program("git", "git"), atrapa.git)
    assert BEZ_CWD not in os.environ                                       # przywrócone po szukaniu
    with pytest.raises(hermes.BladHermesa, match="pełna ścieżka"):
        hermes.zainstaluj(u, PIN, git=os.path.join("Pobrane", "git"), uv=atrapa.uv, python=sys.executable,
                          log=_cicho)
    with pytest.raises(hermes.BladHermesa, match="Nie znalazłem programu uv"):
        hermes.zainstaluj(u, PIN, git=atrapa.git, uv=tmp_path / "brak" / "uv", python=sys.executable, log=_cicho)
    assert atrapa.wpisy() == []


def test_web_dist_npm_ci_build_i_drugi_przebieg(atrapa, tmp_path, monkeypatch):
    u = _uklad(tmp_path)
    checkout = atrapa.instaluj(u)
    monkeypatch.setenv("NODE_ENV", "production")          # pominęłoby tsc i vite z devDependencies
    # npm z Node Jarva (<stan>/narzedzia.json), nie z PATH i nie podrzucony w bieżącym katalogu
    przenosne.zapisz_atomowo(u.stan / "narzedzia.json",
                             json.dumps({"node": {"wersja": "26.12.1", "bin": [str(atrapa.katalog)]}}))
    pobrane = tmp_path / "Pobrane"
    atrapy.program(pobrane, "npm", "import sys; sys.exit('podrzucony npm')")
    monkeypatch.chdir(pobrane)
    monkeypatch.delenv(BEZ_CWD, raising=False)
    atrapa.wyczysc()
    logi: list[str] = []
    dist = hermes.web_dist(u, checkout, log=logi.append)
    assert dist == checkout / "hermes_cli" / "web_dist" and (dist / "index.html").is_file()
    npm = atrapa.wpisy("npm")
    assert [w["argv"] for w in npm] == [["ci", "--ignore-scripts", "--no-audit", "--no-fund", "--include=dev"],
                                        ["run", "build"]]
    assert all(_ta_sama(w["cwd"], checkout / "web") for w in npm)
    assert all(_ta_sama(w["env"]["npm_config_cache"], u.cache / "npm") and "node_env" not in w["env"]
               and w["env"].get("no_color") == "1" for w in npm)
    if WINDOWS:
        assert all(w["env"]["nodefaultcurrentdirectoryinexepath"] == "1" for w in npm)
    assert not [x for x in logi if "index-abc.js" in x]          # lista plików vite nie zasypuje logu
    assert "    built in 4.03s" in logi and not [x for x in logi if "\x1b" in x]   # bez kodów kolorów ANSI
    assert json.loads((checkout / hermes.ZNACZNIK_WEB).read_text(encoding="utf-8"))["commit"] == COMMIT
    # drugi przebieg: bez npm (nawet gdy go nie ma)
    atrapa.wyczysc()
    assert hermes.web_dist(u, checkout, npm=tmp_path / "nie-ma-npm", log=logi.append) == dist
    assert atrapa.wpisy() == []
    # brak index.html (np. przerwana budowa) = budowa od nowa
    (dist / "index.html").unlink()
    hermes.web_dist(u, checkout, npm=atrapa.npm, log=_cicho)
    assert len(atrapa.wpisy("npm")) == 2


def test_web_dist_bledy(atrapa, tmp_path, monkeypatch):
    u = _uklad(tmp_path)
    with pytest.raises(hermes.BladHermesa, match="najpierw zainstaluj"):
        hermes.web_dist(u, tmp_path / "pusty", npm=atrapa.npm)
    checkout = atrapa.instaluj(u)
    monkeypatch.setenv("ATRAPA_NPM_BLAD", "1")
    with pytest.raises(hermes.BladHermesa, match="EBADENGINE"):
        hermes.web_dist(u, checkout, npm=atrapa.npm, log=_cicho)
    assert not (checkout / hermes.ZNACZNIK_WEB).exists()


def test_przerwanie_zatrzymuje_cale_drzewo_procesow(tmp_path, monkeypatch):
    # Ctrl+C w trakcie git, uv albo npm: program i jego dzieci nie piszą dalej po zwolnieniu zamka hermes.lock
    puls = tmp_path / "puls.txt"
    monkeypatch.setenv("ATRAPA_PULS", str(puls))
    spioch = atrapy.program(tmp_path / "bin", "spioch", SPIOCH)

    def przerwij(linia: str) -> None:
        if "start" in linia:
            koniec = time.monotonic() + 30
            while not puls.exists() and time.monotonic() < koniec:
                time.sleep(0.05)
            raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        hermes._strumien([spioch], cwd=tmp_path, env=dict(os.environ), log=przerwij)
    assert puls.exists()
    time.sleep(0.5)
    przed = puls.read_text(encoding="utf-8")
    time.sleep(0.5)
    assert puls.read_text(encoding="utf-8") == przed                      # wnuk też nie żyje

    # limit czasu krótkiego wywołania: to samo
    puls.unlink()
    with pytest.raises(hermes.BladHermesa, match="brak odpowiedzi po 3 s"):
        hermes._wywolaj([spioch], env=dict(os.environ), cwd=tmp_path, opis="śpioch", czas=3)
    time.sleep(0.5)
    przed = puls.read_text(encoding="utf-8") if puls.exists() else ""
    time.sleep(0.5)
    assert (puls.read_text(encoding="utf-8") if puls.exists() else "") == przed


def test_uruchomienie_bez_okna_tylko_bez_konsoli(monkeypatch):
    if WINDOWS:
        monkeypatch.setattr(hermes, "_ma_konsole", lambda: True)       # z konsolą Ctrl+C dociera do programu
        assert hermes._uruchomienie() == {"creationflags": 0}
        monkeypatch.setattr(hermes, "_ma_konsole", lambda: False)      # pythonw, przycisk w panelu: bez mignięcia
        assert hermes._uruchomienie() == {"creationflags": subprocess.CREATE_NO_WINDOW}
    else:
        assert hermes._uruchomienie() == {"start_new_session": True}   # cała grupa do zatrzymania


@pytest.fixture(scope="module")
def checkout_cli(tmp_path_factory):
    """Checkout z prawdziwym venvem i atrapą pakietu hermes_cli dołączoną przez .pth (jak instalacja edytowalna)."""
    checkout = tmp_path_factory.mktemp("hermes-cli")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(checkout / ".venv")], check=True,
                   capture_output=True)
    (checkout / "hermes_cli").mkdir()
    (checkout / "hermes_cli" / "__init__.py").write_text("", encoding="utf-8")
    (checkout / "hermes_cli" / "main.py").write_text(CLI, encoding="utf-8")
    site = subprocess.run([str(srodowisko.hermes_python(checkout)), "-c",
                           "import sysconfig; print(sysconfig.get_paths()['purelib'])"], check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()
    Path(site, "atrapa_hermesa.pth").write_text(f"{checkout}\n", encoding="utf-8")
    return checkout


def _wywolania(dziennik: Path) -> list[dict]:
    if not dziennik.exists():
        return []
    return [json.loads(x) for x in dziennik.read_text(encoding="utf-8").splitlines() if x.strip()]


def _wersja_tekst(checkout: Path, env: dict) -> str:
    return subprocess.run(hermes.argv_hermesa(checkout, "--version"), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def _powloka(u: sciezki.Uklad, profil: str) -> Path:
    return u.stan / "powloka" / f"{profil}.sh"


def test_konfiguracja_bezpieczna_przez_cli_hermesa(checkout_cli, tmp_path, monkeypatch):
    dziennik = tmp_path / "dziennik.jsonl"
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(dziennik))
    monkeypatch.delenv("ATRAPA_BRAK_POL", raising=False)
    u = _uklad(tmp_path)
    env = srodowisko.srodowisko(u, os.environ, biez={}, narz={})
    assert "Update available" in _wersja_tekst(checkout_cli, env)       # domyślnie Hermes podpowiada `hermes update`

    prywatny = tmp_path / "prywatny-hermes"                               # HERMES_HOME właściciela w przekazanym env
    logi: list[str] = []
    hermes.konfiguracja_bezpieczna(u, checkout_cli, dict(os.environ, HERMES_HOME=str(prywatny)), log=logi.append)
    oczekiwane = {"security.tirith_enabled": False, "security.allow_lazy_installs": False,
                  "auth.adopt_external_logins": False, "updates.check": False, "terminal.home_mode": "profile",
                  "terminal.auto_source_bashrc": False}                 # bez ~/.bashrc i ~/.profile właściciela
    if WINDOWS:
        oczekiwane["terminal.shell_init_files"] = [str(_powloka(u, "default"))]
    assert json.loads((u.dane / "atrapa-config.json").read_text(encoding="utf-8")) == oczekiwane
    assert (u.dane / "home").is_dir() and not prywatny.exists()
    konfig = [w for w in _wywolania(dziennik) if "config" in w["argv"]]
    assert konfig and all(w["argv"][:2] == ["-p", "default"] for w in konfig)  # lepki active_profile nie przekieruje
    assert all(w["safe_path"] for w in konfig)                                # -P: bez katalogu roboczego w sys.path
    assert len([w for w in konfig if w["argv"][2:4] == ["config", "set"]]) == len(oczekiwane)
    assert any("updates.check = false" in x for x in logi)
    if WINDOWS:
        tresc = _powloka(u, "default").read_text(encoding="utf-8")
        dom = u.dane / "home"
        assert f"export USERPROFILE='{dom}'\n" in tresc and f"export CODEX_HOME='{dom / '.codex'}'\n" in tresc
        assert f"export APPDATA='{dom / 'AppData' / 'Roaming'}'\n" in tresc and "\r" not in tresc
        assert all((dom / k).is_dir() for k in ("AppData/Roaming", "AppData/Local", ".config", ".codex"))
    else:
        assert not (u.stan / "powloka").exists()

    tekst = _wersja_tekst(checkout_cli, env)
    assert "Update available" not in tekst and "hermes update" not in tekst
    dziennik.unlink()
    assert hermes.wersja(checkout_cli, env) == "0.21.5"
    assert [w["argv"] for w in _wywolania(dziennik)] == [["-p", "default", "--version"]]

    # drugi przebieg: same odczyty, bez zapisu (także pliku powłoki)
    dziennik.unlink()
    znacznik_czasu = _powloka(u, "default").stat().st_mtime_ns if WINDOWS else None
    hermes.konfiguracja_bezpieczna(u, checkout_cli, env, log=logi.append)
    konfig = [w for w in _wywolania(dziennik) if "config" in w["argv"]]
    assert len(konfig) == len(oczekiwane) and not [w for w in konfig if "set" in w["argv"]]
    if WINDOWS:
        assert _powloka(u, "default").stat().st_mtime_ns == znacznik_czasu


def test_wersja_tylko_w_hermes_home_jarva(checkout_cli, tmp_path, monkeypatch):
    # prywatny Hermes właściciela w env (albo env bez HERMES_HOME lub JARVO_ROOT): odmowa bez uruchamiania, bo Hermes
    # czytałby jego config i zapisał tam .update_check; z u= zawsze <dane> Jarva
    dziennik = tmp_path / "dziennik.jsonl"
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(dziennik))
    monkeypatch.delenv("ATRAPA_BRAK_POL", raising=False)
    u = _uklad(tmp_path)
    env = srodowisko.srodowisko(u, os.environ, biez={}, narz={})
    prywatny = tmp_path / "prywatny-hermes"
    for zle in (dict(env, HERMES_HOME=str(prywatny)), {k: v for k, v in env.items() if k != "HERMES_HOME"},
                {k: v for k, v in env.items() if k != "JARVO_ROOT"}):
        with pytest.raises(hermes.BladHermesa, match="HERMES_HOME spoza Jarva"):
            hermes.wersja(checkout_cli, zle)
    assert _wywolania(dziennik) == [] and not prywatny.exists()
    assert hermes.wersja(checkout_cli, dict(os.environ, HERMES_HOME=str(prywatny)), u=u) == "0.21.5"
    [w] = _wywolania(dziennik)
    assert w["argv"] == ["-p", "default", "--version"] and _ta_sama(w["home"], u.dane) and w["safe_path"]


def test_konfiguracja_profili_i_klucze_ktorych_wersja_nie_zna(checkout_cli, tmp_path, monkeypatch):
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(tmp_path / "dziennik.jsonl"))
    monkeypatch.setenv("ATRAPA_BRAK_POL", "terminal.home_mode,security.tirith_enabled")   # np. Hermes 0.22 bez tirith
    u = _uklad(tmp_path)
    (u.dane / "profiles" / "jarvo").mkdir(parents=True)
    env = srodowisko.srodowisko(u, os.environ, biez={}, narz={})
    logi: list[str] = []
    hermes.konfiguracja_bezpieczna(u, checkout_cli, env, log=logi.append, profile=["jarvo"])
    oczekiwane = {"security.allow_lazy_installs": False, "auth.adopt_external_logins": False, "updates.check": False,
                  "terminal.auto_source_bashrc": False}
    for profil, home in (("default", u.dane), ("jarvo", u.dane / "profiles" / "jarvo")):
        jest = json.loads((home / "atrapa-config.json").read_text(encoding="utf-8"))
        if WINDOWS:
            assert jest.pop("terminal.shell_init_files") == [str(_powloka(u, profil))]
            assert f"export USERPROFILE='{home / 'home'}'\n" in _powloka(u, profil).read_text(encoding="utf-8")
        assert jest == oczekiwane
    assert any("nie dotyczy terminal.home_mode" in x for x in logi)
    # bez home_mode HOME zostaje właściciela; na Windows katalog domowy profilu i tak jest dla zmiennych powłoki
    assert (u.dane / "home").is_dir() == WINDOWS
    with pytest.raises(hermes.BladHermesa, match="nie zna klucza updates.check"):
        hermes.konfiguracja_bezpieczna(u, checkout_cli, dict(env, ATRAPA_BRAK_POL="updates.check"), log=_cicho)
    if WINDOWS:          # f97608f nie czyta plików rc na Windows (local.py:729), ale shell_init_files jest konieczne
        hermes.konfiguracja_bezpieczna(u, checkout_cli, dict(env, ATRAPA_BRAK_POL="terminal.auto_source_bashrc"),
                                       log=logi.append)
        assert any("nie dotyczy terminal.auto_source_bashrc" in x for x in logi)
        with pytest.raises(hermes.BladHermesa, match="nie zna klucza terminal.shell_init_files"):
            hermes.konfiguracja_bezpieczna(u, checkout_cli, dict(env, ATRAPA_BRAK_POL="terminal.shell_init_files"),
                                           log=_cicho)
    else:
        with pytest.raises(hermes.BladHermesa, match="nie zna klucza terminal.auto_source_bashrc"):
            hermes.konfiguracja_bezpieczna(u, checkout_cli, dict(env, ATRAPA_BRAK_POL="terminal.auto_source_bashrc"),
                                           log=_cicho)
    with pytest.raises(hermes.BladHermesa, match="Zła nazwa profilu"):
        hermes.konfiguracja_bezpieczna(u, checkout_cli, env, log=_cicho, profile=["../obcy"])
    # profil, którego nie ma: odmowa, zanim cokolwiek powstanie (także katalog domowy i plik powłoki na Windows)
    przed = len(_wywolania(tmp_path / "dziennik.jsonl"))
    with pytest.raises(hermes.BladHermesa, match="Nie ma profilu brak"):
        hermes.konfiguracja_bezpieczna(u, checkout_cli, env, log=_cicho, profile=["brak"])
    assert not (u.dane / "profiles" / "brak").exists() and not _powloka(u, "brak").exists()
    assert len(_wywolania(tmp_path / "dziennik.jsonl")) == przed


def test_cli_hermesa_bez_katalogu_roboczego_w_sys_path(checkout_cli, tmp_path, monkeypatch):
    # json.py podrzucony w HERMES_HOME (piszą tam agenci) i w katalogu, z którego ruszył proces, nie wykonuje się;
    # lepki active_profile nie przekierowuje zapisu konfiguracji ani --version
    dziennik = tmp_path / "dziennik.jsonl"
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(dziennik))
    monkeypatch.delenv("ATRAPA_BRAK_POL", raising=False)
    u = _uklad(tmp_path)
    znacznik = tmp_path / "podrzucony-wykonany.txt"
    podrzucony = f"open({str(znacznik)!r}, 'w').close()\nraise SystemExit('podrzucony json.py')\n"
    pobrane = tmp_path / "Pobrane"
    for katalog in (u.dane, pobrane):
        katalog.mkdir(parents=True, exist_ok=True)
        (katalog / "json.py").write_text(podrzucony, encoding="utf-8")
    (u.dane / "active_profile").write_text("inny\n", encoding="utf-8")
    monkeypatch.chdir(pobrane)
    env = srodowisko.srodowisko(u, os.environ, biez={}, narz={})
    hermes.konfiguracja_bezpieczna(u, checkout_cli, env, log=_cicho)
    assert json.loads((u.dane / "atrapa-config.json").read_text(encoding="utf-8"))["updates.check"] is False
    assert hermes.wersja(checkout_cli, env) == "0.21.5"
    w = subprocess.run(hermes.argv_hermesa(checkout_cli, "-p", "default", "--version"), cwd=u.dane, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")   # jak nadzorca: cwd=dane
    assert w.returncode == 0 and "Hermes Agent v0.21.5" in w.stdout
    assert not znacznik.exists() and not (u.dane / "profiles" / "inny").exists()
    assert all(x["safe_path"] for x in _wywolania(dziennik))


@pytest.mark.windows_only
@pytest.mark.wymaga_bash
def test_powloka_windows_w_git_bash_widza_programy_natywne(tmp_path):
    # plik z terminal.shell_init_files tak, jak go czyta Hermes f97608f (_prepend_shell_init, local.py:741-748):
    # ścieżka Windows w apostrofach; programy natywne (tu python) widzą katalogi profilu, także ze spacją, polskimi
    # literami i apostrofem w ścieżce
    korzen = tmp_path / "Jarvo Żółć'x"            # <dane> i <stan> mogą mieć znaki spoza ASCII (tylko <program> nie)
    u = sciezki.Uklad(root=korzen, program=tmp_path / "program", dane=korzen / "dane", stan=korzen / "stan",
                      logi=korzen / "logi", cache=korzen / "cache", build=korzen / "build")
    dom = u.dane / "home"
    plik = hermes._przygotuj_powloke(u, "default", dom)
    zrzut = tmp_path / "zrzut.py"
    zrzut.write_text("import json, os, sys\nprint(json.dumps({k: os.environ.get(k) for k in sys.argv[1:]}))\n",
                     encoding="utf-8")
    zmienne = list(hermes._dom_windows(dom))
    p = str(plik).replace("'", "'\\''")
    skrypt = (f"set +e\n[ -r '{p}' ] && . '{p}' 2>/dev/null || true\n"
              f"'{Path(sys.executable).as_posix()}' '{zrzut.as_posix()}' {' '.join(zmienne)}\n")
    w = uruchom_bash("-c", skrypt, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    assert w.returncode == 0, w.stderr
    widziane = json.loads(w.stdout.strip().splitlines()[-1])
    assert widziane == {k: str(v) for k, v in hermes._dom_windows(dom).items()}
