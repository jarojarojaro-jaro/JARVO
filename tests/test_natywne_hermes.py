"""Hermes natywnie (jarvo/hermes.py; docs/NATYWNIE.md H01–H03, H13, H16, H23, H24, I13): checkout przypiętego
commitu, `uv sync --locked` bez obejść i bez cudzej konfiguracji uv, front dashboardu z npm i bezpieczna konfiguracja
przez CLI Hermesa. git, uv i npm to atrapy (tests/atrapy.py); CLI Hermesa to atrapa pakietu hermes_cli w prawdziwym
venvie, więc argv_hermesa() działa bez podmian (na Windows z launcherem venvu). Bez sieci."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import atrapy
from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import hermes, przenosne, sciezki, srodowisko  # noqa: E402

COMMIT = "f97608f178d1ffeca59860195ab7da295f7c8e5f"
PIN = {"repo": "https://example.invalid/hermes-agent", "tag": "v2026.9.24", "commit": COMMIT, "wersja": "0.21.5",
       "dodatki": ["all", "messaging"]}

# wspólny początek atrap: każde wywołanie dopisuje argv, katalog i wybrane zmienne do dziennika JSONL
DZIENNIK = r'''
import json, os, sys
from pathlib import Path

def dziennik(program):
    env = {k.lower(): v for k, v in os.environ.items()
           if k.upper().startswith(("UV_", "GIT_", "GCM_", "NPM_CONFIG_", "XDG_CONFIG", "APPDATA", "NODE_ENV",
                                    "NO_COLOR"))}
    with open(os.environ["ATRAPA_DZIENNIK"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"program": program, "argv": sys.argv[1:], "cwd": os.getcwd(), "env": env}) + "\n")
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
    Path("pyproject.toml").write_text("[project]\nname = 'hermes-agent'\n", encoding="utf-8")
    Path("web").mkdir(exist_ok=True)
    Path("web", "package.json").write_text("{}", encoding="utf-8")
elif polecenie == "rev-parse":
    print(Path(".git", "HEAD_ATRAPY").read_text(encoding="utf-8"))
elif polecenie == "fetch":
    pass
else:
    sys.exit("atrapa git: nie znam polecenia " + polecenie)
'''

UV = DZIENNIK + r'''
dziennik("uv")
if sys.argv[1:2] != ["sync"]:
    sys.exit("atrapa uv: tylko sync")
if os.environ.get("ATRAPA_UV_BLAD"):
    print("Resolved 312 packages in 9ms", file=sys.stderr)
    print("error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided. To update the "
          "lockfile, run `uv lock`.", file=sys.stderr)
    sys.exit(2)
python = Path(".venv") / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
python.parent.mkdir(parents=True, exist_ok=True)
python.write_bytes(b"")
print("Installed 2 packages in 5ms", file=sys.stderr)
print(" + aiohttp==3.14.3", file=sys.stderr)
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

# atrapa CLI Hermesa (pakiet hermes_cli w venvie): -p <profil>, config get/set i --version jak w f97608f
CLI = r'''
import json, os, sys
from pathlib import Path

DOMYSLNE = {"security.tirith_enabled": True, "security.allow_lazy_installs": True,
            "auth.adopt_external_logins": True, "updates.check": True, "terminal.home_mode": "auto"}
for brak in filter(None, os.environ.get("ATRAPA_BEZ_KLUCZY", "").split(",")):
    DOMYSLNE.pop(brak, None)
argv = sys.argv[1:]
profil = None
if "-p" in argv:
    i = argv.index("-p")
    profil = argv[i + 1]
    del argv[i:i + 2]
home = Path(os.environ["HERMES_HOME"])
if profil and profil != "default":
    home = home / "profiles" / profil
plik = home / "atrapa-config.json"
stan = json.loads(plik.read_text(encoding="utf-8")) if plik.exists() else {}
with open(os.environ["ATRAPA_DZIENNIK"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"program": "hermes", "argv": sys.argv[1:], "home": str(home)}) + "\n")
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
    logiczna = isinstance(DOMYSLNE.get(klucz), bool)
    stan[klucz] = {"false": False, "true": True}.get(wartosc.lower(), wartosc) if logiczna else wartosc
    home.mkdir(parents=True, exist_ok=True)
    plik.write_text(json.dumps(stan), encoding="utf-8")
    print(f"✓ Set {klucz} = {wartosc} in {home / 'config.yaml'}")
else:
    sys.exit("atrapa hermes: nie znam " + " ".join(argv))
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
    for zmienna in ("ATRAPA_GIT_HEAD", "ATRAPA_GIT_KLON_BLAD", "ATRAPA_UV_BLAD", "ATRAPA_NPM_BLAD", "NODE_ENV"):
        monkeypatch.delenv(zmienna, raising=False)
    return Atrapy(tmp_path / "bin", dziennik)


def test_argv_hermesa_to_python_venvu_checkoutu(tmp_path):
    assert hermes.argv_hermesa(tmp_path / "h", "config", "get", "x") == [
        str(srodowisko.hermes_python(tmp_path / "h")), "-m", "hermes_cli.main", "config", "get", "x"]
    assert hermes.katalog_checkoutu(_uklad(tmp_path), COMMIT) == _uklad(tmp_path).program / "hermes" / COMMIT[:12]


def test_zainstaluj_checkout_i_uv_sync_locked_a_drugi_przebieg_nic_nie_robi(atrapa, tmp_path, monkeypatch):
    # odziedziczone po właścicielu: UV_NO_CONFIG i indeks z uv nie mogą dojść do sync, GIT_DIR nie może przekierować
    # gita; UV_NATIVE_TLS dotyczy sieci (certyfikaty) i zostaje
    monkeypatch.setenv("UV_NO_CONFIG", "1")
    monkeypatch.setenv("UV_INDEX_URL", "https://zly.invalid/simple")
    monkeypatch.setenv("UV_NATIVE_TLS", "1")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "obce-repo"))
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
    assert {"core.longpaths=true", "core.autocrlf=false"} <= set(co["argv"][:i])
    assert any(w["argv"][:2] == ["rev-parse", "HEAD"] for w in git)
    assert all(w["env"].get("git_terminal_prompt") == "0" and "git_dir" not in w["env"] for w in git)

    [sync] = atrapa.wpisy("uv")
    assert sync["argv"] == ["sync", "--locked", "--extra", "all", "--extra", "messaging"]
    assert _ta_sama(sync["cwd"], checkout)
    env = sync["env"]
    assert _ta_sama(env["uv_python"], sys.executable) and env["uv_python_downloads"] == "never"
    assert _ta_sama(env["uv_cache_dir"], u.cache / "uv") and env["uv_link_mode"] == "copy"
    assert "uv_no_config" not in env and "uv_index_url" not in env and env.get("uv_native_tls") == "1"
    pusty = u.stan / "bez-konfiguracji-uv"                              # zamiast uv.toml właściciela
    if os.name == "nt":
        assert _ta_sama(env["appdata"], pusty)
    else:
        assert _ta_sama(env["xdg_config_home"], pusty) and _ta_sama(env["xdg_config_dirs"], pusty)
    assert pusty.is_dir() and not any(pusty.iterdir())

    znacznik = json.loads((checkout / hermes.ZNACZNIK).read_text(encoding="utf-8"))
    assert znacznik["commit"] == COMMIT and znacznik["dodatki"] == ["all", "messaging"]
    wyklucz = (checkout / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
    assert f"/{hermes.ZNACZNIK}" in wyklucz and f"/{hermes.ZNACZNIK_WEB}" in wyklucz
    assert not [x for x in logi if "aiohttp==" in x] and "gotowy" in logi[-1]   # lista paczek nie zasypuje logu

    # drugi przebieg: żadnego wywołania (gita i uv może już nawet nie być)
    atrapa.wyczysc()
    assert hermes.zainstaluj(u, PIN, git=tmp_path / "nie-ma-gita", uv=tmp_path / "nie-ma-uv", python=sys.executable,
                             log=logi.append) == checkout
    assert atrapa.wpisy() == [] and "już zainstalowany" in logi[-1]

    # inne dodatki w pinie: tylko sync, bez nowego klonu
    atrapa.instaluj(u, dict(PIN, dodatki=["all"]))
    assert [w["argv"] for w in atrapa.wpisy("uv")] == [["sync", "--locked", "--extra", "all"]]
    assert not [w for w in atrapa.wpisy("git") if "clone" in w["argv"] or "checkout" in w["argv"]]


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


def test_blad_locka_to_wyjatek_bez_obejscia_bez_sum(atrapa, tmp_path, monkeypatch):
    u = _uklad(tmp_path)
    monkeypatch.setenv("ATRAPA_UV_BLAD", "lock")
    with pytest.raises(hermes.BladHermesa) as blad:
        atrapa.instaluj(u)
    tekst = str(blad.value)
    assert "uv.lock nie pasuje" in tekst and "bez sum" in tekst and "needs to be updated" in tekst
    assert [w["argv"][:2] for w in atrapa.wpisy("uv")] == [["sync", "--locked"]]   # jedna próba, bez pip install
    checkout = u.program / "hermes" / COMMIT[:12]
    assert checkout.is_dir() and not (checkout / hermes.ZNACZNIK).exists()
    # po naprawie: ten sam checkout (bez klonu), sync jeszcze raz
    monkeypatch.delenv("ATRAPA_UV_BLAD")
    atrapa.wyczysc()
    assert atrapa.instaluj(u) == checkout
    assert not [w for w in atrapa.wpisy("git") if "clone" in w["argv"]] and len(atrapa.wpisy("uv")) == 1
    assert (checkout / hermes.ZNACZNIK).is_file()


def test_blad_klonu_bez_sekretow_w_komunikacie(atrapa, tmp_path, monkeypatch):
    monkeypatch.setenv("ATRAPA_GIT_KLON_BLAD", "1")
    logi: list[str] = []
    pin = dict(PIN, repo="https://ktos:tajny-token@example.invalid/hermes-agent")
    with pytest.raises(hermes.BladHermesa, match="git clone") as blad:
        atrapa.instaluj(_uklad(tmp_path), pin, log=logi.append)
    assert "tajny-token" not in str(blad.value) and not [x for x in logi if "tajny-token" in x]
    assert "***@example.invalid" in str(blad.value)


@pytest.mark.parametrize("zmiana, fragment", [
    ({"commit": "f97608f"}, "pełnym SHA"),
    ({"repo": "http://example.invalid/hermes-agent"}, "https"),
    ({"dodatki": ["all", "--no-locked"]}, "extras"),
    ({"dodatki": "all"}, "extras"),
])
def test_zly_pin_odrzucony_przed_uruchomieniem(atrapa, tmp_path, zmiana, fragment):
    with pytest.raises(hermes.BladHermesa, match=fragment):
        atrapa.instaluj(_uklad(tmp_path), dict(PIN, **zmiana))
    assert atrapa.wpisy() == []


def test_gola_nazwa_programu_tylko_z_path(atrapa, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "git").write_text("podrzucony plik w bieżącym katalogu", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "pusto"))
    with pytest.raises(hermes.BladHermesa, match="Nie znalazłem programu git"):
        hermes.zainstaluj(_uklad(tmp_path), PIN, git="git", uv=atrapa.uv, python=sys.executable, log=_cicho)
    with pytest.raises(hermes.BladHermesa, match="Nie znalazłem programu uv"):
        hermes.zainstaluj(_uklad(tmp_path), PIN, git=atrapa.git, uv=tmp_path / "brak" / "uv", python=sys.executable,
                          log=_cicho)
    assert atrapa.wpisy() == []


def test_web_dist_npm_ci_build_i_drugi_przebieg(atrapa, tmp_path, monkeypatch):
    u = _uklad(tmp_path)
    checkout = atrapa.instaluj(u)
    monkeypatch.setenv("NODE_ENV", "production")          # pominęłoby tsc i vite z devDependencies
    # npm z Node Jarva (<stan>/narzedzia.json), nie z PATH
    przenosne.zapisz_atomowo(u.stan / "narzedzia.json",
                             json.dumps({"node": {"wersja": "26.12.1", "bin": [str(atrapa.katalog)]}}))
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


def test_konfiguracja_bezpieczna_przez_cli_hermesa(checkout_cli, tmp_path, monkeypatch):
    dziennik = tmp_path / "dziennik.jsonl"
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(dziennik))
    monkeypatch.delenv("ATRAPA_BEZ_KLUCZY", raising=False)
    u = _uklad(tmp_path)
    env = srodowisko.srodowisko(u, os.environ, biez={}, narz={})
    assert "Update available" in _wersja_tekst(checkout_cli, env)       # domyślnie Hermes podpowiada `hermes update`

    prywatny = tmp_path / "prywatny-hermes"                               # HERMES_HOME właściciela w przekazanym env
    logi: list[str] = []
    hermes.konfiguracja_bezpieczna(u, checkout_cli, dict(os.environ, HERMES_HOME=str(prywatny)), log=logi.append)
    assert json.loads((u.dane / "atrapa-config.json").read_text(encoding="utf-8")) == {
        "security.tirith_enabled": False, "security.allow_lazy_installs": False,
        "auth.adopt_external_logins": False, "updates.check": False, "terminal.home_mode": "profile"}
    assert (u.dane / "home").is_dir() and not prywatny.exists()
    konfig = [w for w in _wywolania(dziennik) if "config" in w["argv"]]
    assert konfig and all(w["argv"][:2] == ["-p", "default"] for w in konfig)  # lepki active_profile nie przekieruje
    assert len([w for w in konfig if w["argv"][2:4] == ["config", "set"]]) == 5
    assert any("updates.check = false" in x for x in logi)

    tekst = _wersja_tekst(checkout_cli, env)
    assert "Update available" not in tekst and "hermes update" not in tekst
    assert hermes.wersja(checkout_cli, env) == "0.21.5"

    # drugi przebieg: same odczyty, bez zapisu
    dziennik.unlink()
    hermes.konfiguracja_bezpieczna(u, checkout_cli, env, log=logi.append)
    konfig = [w for w in _wywolania(dziennik) if "config" in w["argv"]]
    assert len(konfig) == len(hermes.BEZPIECZNE) and not [w for w in konfig if "set" in w["argv"]]


def test_konfiguracja_profili_i_klucze_ktorych_wersja_nie_zna(checkout_cli, tmp_path, monkeypatch):
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(tmp_path / "dziennik.jsonl"))
    monkeypatch.setenv("ATRAPA_BEZ_KLUCZY", "terminal.home_mode,security.tirith_enabled")   # np. Hermes 0.22 bez tirith
    u = _uklad(tmp_path)
    (u.dane / "profiles" / "jarvo").mkdir(parents=True)
    env = srodowisko.srodowisko(u, os.environ, biez={}, narz={})
    logi: list[str] = []
    hermes.konfiguracja_bezpieczna(u, checkout_cli, env, log=logi.append, profile=["jarvo"])
    oczekiwane = {"security.allow_lazy_installs": False, "auth.adopt_external_logins": False, "updates.check": False}
    assert json.loads((u.dane / "atrapa-config.json").read_text(encoding="utf-8")) == oczekiwane
    assert json.loads((u.dane / "profiles" / "jarvo" / "atrapa-config.json").read_text(encoding="utf-8")) == oczekiwane
    assert any("nie dotyczy terminal.home_mode" in x for x in logi) and not (u.dane / "home").exists()
    with pytest.raises(hermes.BladHermesa, match="nie zna klucza updates.check"):
        hermes.konfiguracja_bezpieczna(u, checkout_cli, dict(env, ATRAPA_BEZ_KLUCZY="updates.check"), log=_cicho)
    with pytest.raises(hermes.BladHermesa, match="Zła nazwa profilu"):
        hermes.konfiguracja_bezpieczna(u, checkout_cli, env, log=_cicho, profile=["../obcy"])


def test_wersja_bez_hermes_home_nie_rusza_prywatnego_hermesa(tmp_path):
    with pytest.raises(hermes.BladHermesa, match="HERMES_HOME"):
        hermes.wersja(tmp_path, {"PATH": os.environ.get("PATH", "")})
