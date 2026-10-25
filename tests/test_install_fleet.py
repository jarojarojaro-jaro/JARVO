"""Instalacja floty w Pythonie: scripts/install_fleet.py i jarvo/flota.py (docs/NATYWNIE.md S07, K02, H05, H27, E4).

install_fleet.py biegnie jak natywnie (osobny proces, --natywnie, --bez-sekretow) na katalogu tymczasowym z atrapą
Hermesa (tests/atrapy.py: `python -P -m hermes_cli.main …` z HERMES_HOME) i prawdziwym wiedza.py (zasiew, indeks,
lint). Pierwszy przebieg instaluje profile (z kluczami configu zależnymi od instalacji z --ustawienia-profili, jak
z jarvo/flota.py), klucze API, wtyczki z dowiązaniami i skarbiec; drugi niczego nie zmienia
(poza historią skarbca) i nie zleca restartu. Atrapa celowo wypisuje klucze z plików .env: w logu i podsumowaniu mają
być tylko gwiazdki. flota.py: argumenty build.py z kontraktu tokenów (tylko opcje, które build.py zna), środowisko
bez zmiennych obcych, podsumowanie i potwierdzenie restartu panelu.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import atrapy
from conftest import REPO

sys.path.insert(0, str(REPO))
import install_fleet  # noqa: E402  (scripts/ w sys.path z conftest)
from jarvo import flota, sciezki  # noqa: E402

SKRYPT = REPO / "scripts" / "install_fleet.py"
AGENCI = ("jarvo", "jarvo-web")
SEKRET_HOSTA = "sk-or-v1-" + "7f3a9c51" * 6        # klucz dostawcy w .env hosta przed instalacją
KLUCZ_WEB = "a1b2c3d4" * 8                         # API_SERVER_KEY profilu jarvo-web sprzed instalacji
WINDOWS = os.name == "nt"
# historia skarbca i dziennik atrapy: wolno im się zmieniać przy każdym przebiegu
ZMIENNE = ("jarvo/knowledge/.git/", "jarvo/knowledge/LOG.md", "jarvo/knowledge/LINT.md", "jarvo/state/wiedza.db",
           ".atrapa-hermesa.log")

ATRAPA_HERMESA = r'''
import json, os, re, shutil, sqlite3, sys, time
from pathlib import Path

argv = sys.argv[1:]
if argv[:3] != ["-P", "-m", "hermes_cli.main"]:
    print("atrapa: oczekiwano -P -m hermes_cli.main, jest", argv)
    sys.exit(3)
argv = argv[3:]
home = Path(os.environ["HERMES_HOME"])
with open(home / ".atrapa-hermesa.log", "a", encoding="utf-8") as f:
    f.write(json.dumps(argv) + "\n")
profil = "default"
if argv[:1] == ["-p"]:
    profil, argv = argv[1], argv[2:]

# gadatliwe narzędzie: wypisuje klucze z plików .env (install_fleet.py ma je zamaskować)
for env in (home / ".env", *sorted((home / "profiles").glob("*/.env"))):
    if env.is_file():
        for linia in env.read_text(encoding="utf-8").splitlines():
            if "_KEY=" in linia and not linia.startswith("#"):
                print("debug", linia)


def kopiuj(src, dst):
    # jak Hermes: pliki dystrybucji nadpisane, skille scalone, manifest z source i nowym installed_at
    shutil.copytree(src, dst, dirs_exist_ok=True)
    tekst = re.sub(r"^(source|installed_at):.*\n?", "", (src / "distribution.yaml").read_text(encoding="utf-8"),
                   flags=re.M)
    (dst / "distribution.yaml").write_text(tekst.rstrip("\n") + f"\nsource: {src}\ninstalled_at: '{time.time_ns()}'\n",
                                           encoding="utf-8")


if argv[:2] == ["profile", "install"]:
    src = Path(argv[2]).resolve()
    nazwa = re.search(r"^name:\s*(\S+)", (src / "distribution.yaml").read_text(encoding="utf-8"), re.M).group(1)
    dst = home / "profiles" / nazwa
    if dst.exists() and "--force" not in argv:
        print(f"Error: Profile '{nazwa}' already exists")
        sys.exit(1)
    kopiuj(src, dst)
    print(f"Installed '{nazwa}'")
elif argv[:2] == ["profile", "update"]:
    dst = home / "profiles" / argv[2]
    zrodlo = re.search(r"^source:\s*'?([^'\n]+?)'?\s*$", (dst / "distribution.yaml").read_text(encoding="utf-8"),
                       re.M).group(1)
    kopiuj(Path(zrodlo), dst)
    print(f"Updated '{argv[2]}'")
elif argv[:2] == ["plugins", "enable"]:
    cel = home if profil == "default" else home / "profiles" / profil
    if not (cel / "plugins" / argv[2] / "plugin.yaml").is_file():
        print(f"Plugin '{argv[2]}' not found.")
        sys.exit(1)
    # dopisek w tym samym układzie, w jakim YAML piszą ruamel i PyYAML (drugi przebieg nie zmienia pliku)
    plik = cel / "config.yaml"
    tekst = "\n" + (plik.read_text(encoding="utf-8") if plik.is_file() else "")
    if f"\n  - {argv[2]}\n" not in tekst:
        if "\nplugins:\n  enabled:\n" in tekst:
            tekst = tekst.replace("\nplugins:\n  enabled:\n", f"\nplugins:\n  enabled:\n  - {argv[2]}\n", 1)
        else:
            tekst = tekst.rstrip("\n") + f"\nplugins:\n  enabled:\n  - {argv[2]}\n"
        plik.write_text(tekst.lstrip("\n"), encoding="utf-8", newline="\n")
    print(f"Plugin {argv[2]} enabled.")
elif argv[:2] == ["kanban", "init"]:
    con = sqlite3.connect(home / "kanban.db")
    con.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT, assignee TEXT)")
    con.commit()
    con.close()
    print("Kanban DB initialized")
elif argv[:2] == ["cron", "resume"]:
    print(f"Resumed job {argv[2]}")
else:
    print("atrapa: nieznane polecenie", argv)
    sys.exit(2)
'''


def _pisz(p: Path, tekst: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tekst, encoding="utf-8", newline="\n")


def zbuduj(build: Path) -> None:
    """Build w układzie scripts/build.py: dwa profile, host, cztery wtyczki, dane skarbca."""
    _pisz(build / "BUILD.json", json.dumps({"agents": [{"agent": a, "skills": 1, "cron_jobs": 0} for a in AGENCI],
                                            "plugins": list(install_fleet.WTYCZKI)}))
    for a in AGENCI:
        p = build / "profiles" / a
        _pisz(p / "distribution.yaml", f'name: {a}\nversion: 0.1.0\ndescription: "Atrapa {a}"\n')
        zgody = "  - jarvo-zgody\n" if a == "jarvo-web" else ""
        _pisz(p / "config.yaml", f"model:\n  provider: openrouter\n  default: atrapa/{a}\nplugins:\n  enabled:\n"
                                 f"  - jarvo-wiedza\n{zgody}")
        _pisz(p / "SOUL.md", f"# {a}\n")
        _pisz(p / "skills" / "fleet" / f"praca-{a}" / "SKILL.md",
              f"---\nname: praca-{a}\ndescription: atrapa\nmetadata:\n  jarvo:\n    agent: {a}\n---\n# Praca\n")
    szablony = build / "profiles" / "jarvo" / "skills" / "fleet"
    _pisz(szablony / "mission-ledger" / "references" / "INDEX.template.md", "# Misje\n")
    _pisz(szablony / "onboarding-interview" / "references" / "USER.template.md", "# Właściciel\n")
    _pisz(build / "host" / "config.yaml", "model:\n  provider: openrouter\n  default: atrapa/host\ngateway:\n"
                                          "  profile_routes: []\nplugins:\n  enabled:\n  - jarvo-zgody\n")
    _pisz(build / "host" / "SOUL.md", "# Host floty\n")
    w = build / "plugins"
    _pisz(w / "jarvo-hq" / "dashboard" / "manifest.json", '{"name": "jarvo-hq"}\n')
    _pisz(w / "jarvo-hq" / "dashboard" / "plugin_api.py", "# panel\n")
    for nazwa in ("jarvo-wiedza", "jarvo-komputer", "jarvo-zgody"):
        _pisz(w / nazwa / "plugin.yaml", f"name: {nazwa}\nversion: 0.1.0\n")
        _pisz(w / nazwa / "__init__.py", "def register(ctx):\n    pass\n")
    _pisz(build / "wiedza" / "fleet.json", json.dumps(
        {"agents": [{"name": a, "short": a, "title": a, "description": f"Atrapa {a}", "skills": [], "scripts": []}
                    for a in AGENCI]}))
    (build / "wiedza" / "repo").mkdir(parents=True, exist_ok=True)


def przebieg(swiat: dict, *dodatki: str) -> tuple[subprocess.CompletedProcess, dict]:
    """install_fleet.py jako osobny proces, z argumentami jak z jarvo/flota.py (także --ustawienia-profili)."""
    wynik = swiat["root"] / "flota.json"
    wynik.unlink(missing_ok=True)
    ustawienia = swiat["root"] / "flota-ustawienia.json"
    ustawienia.write_text(json.dumps(flota.ustawienia_profili(uklad(swiat["root"]), list(AGENCI))), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "HERMES_HOME")}
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(SKRYPT), "--dane", str(swiat["dane"]), "--build", str(swiat["build"]),
                        "--repo", str(REPO), "--narzedzia", str(swiat["root"] / "narzedzia-floty"),
                        "--hermes-python", str(swiat["hermes"]), "--natywnie", "--bez-sekretow",
                        "--podsumowanie", str(wynik), "--czekaj-na-skarbiec", "5",
                        "--ustawienia-profili", str(ustawienia), *dodatki],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=600)
    return r, (json.loads(wynik.read_text(encoding="utf-8")) if wynik.is_file() else {})


def migawka(dane: Path) -> dict[str, str]:
    """Treść katalogu danych (spis z install_fleet.py) bez historii skarbca; distribution.yaml bez installed_at."""
    s = install_fleet.spis(dane)
    for rel in list(s):
        if rel.startswith(ZMIENNE) or "/__pycache__/" in f"/{rel}":
            del s[rel]
        elif rel.endswith("distribution.yaml"):
            s[rel] = re.sub(r"^installed_at:.*$", "", (dane / rel).read_text(encoding="utf-8"), flags=re.M)
    return s


def uklad(root: Path) -> sciezki.Uklad:
    return sciezki.Uklad(root=root, program=root / "program", dane=root / "dane", stan=root / "stan",
                         logi=root / "logi", cache=root / "cache", build=root / "build")


@pytest.fixture(scope="module")
def dwa_przebiegi(tmp_path_factory):
    root = tmp_path_factory.mktemp("flota") / "Jarvo Michał"         # spacja i polskie znaki w ścieżce danych
    # venv Hermesa leży w <program>, a ta ścieżka jest zawsze ASCII (c1); .cmd atrapy cmd.exe czyta w stronie OEM
    swiat = {"root": root, "dane": root / "dane", "build": root / "build",
             "hermes": atrapy.program(tmp_path_factory.mktemp("program") / "venv", "python", ATRAPA_HERMESA)}
    zbuduj(swiat["build"])
    _pisz(swiat["dane"] / ".env", f"OPENROUTER_API_KEY={SEKRET_HOSTA}\n")
    # profil założony przed flotą (bez distribution.yaml), z własnym kluczem API: instalacja z --force, klucz zostaje
    _pisz(swiat["dane"] / "profiles" / "jarvo-web" / ".env", f"API_SERVER_KEY={KLUCZ_WEB}\n")
    r1, w1 = przebieg(swiat, "--first-run")
    zapisany = flota.potwierdz_restart_panelu(uklad(root), w1.get("odcisk_panelu", ""))   # jak nadzorca po restarcie
    m1 = migawka(swiat["dane"])
    r2, w2 = przebieg(swiat)
    m2 = migawka(swiat["dane"])
    return {**swiat, "r1": r1, "w1": w1, "m1": m1, "r2": r2, "w2": w2, "m2": m2, "zapisany": zapisany}


def _env(plik: Path) -> dict[str, str]:
    return install_fleet.czytaj_env(plik)


def test_pierwszy_przebieg_instaluje_flote(dwa_przebiegi):
    s = dwa_przebiegi
    assert s["r1"].returncode == 0, s["r1"].stdout + s["r1"].stderr
    w, dane = s["w1"], s["dane"]
    assert w["agenci"] == list(AGENCI)
    assert w["wtyczki"] == {n: "nowa" for n in install_fleet.WTYCZKI}
    rodzaj = "junction" if WINDOWS else "symlink"
    assert w["dowiazania"] == {"jarvo": {"jarvo-wiedza": rodzaj},
                               "jarvo-web": {"jarvo-wiedza": rodzaj, "jarvo-zgody": rodzaj}}
    assert w["restart_bramy"] and w["restart_panelu"] and w["restart"]
    assert re.fullmatch(r"[0-9a-f]{16}", w["odcisk_panelu"]) and s["zapisany"]
    assert w["klucze_nowe"] == ["host", "jarvo"]
    assert w["skarbiec"]["zasiany"] and w["lint"]["bledy"] == 0
    # profile z buildu, z dowiązaniami do jednej kopii wtyczki i katalogiem home (terminal.home_mode: profile)
    for a in AGENCI:
        home = dane / "profiles" / a
        assert (home / "skills" / "fleet" / f"praca-{a}" / "SKILL.md").is_file()
        assert (home / "home").is_dir()
        assert (home / "skins" / "jarvo.yaml").is_file()
        link = home / "plugins" / "jarvo-wiedza"
        assert install_fleet._link(link) and (link / "plugin.yaml").is_file()
        assert os.path.samefile(link, dane / "plugins" / "jarvo-wiedza")
    assert (dane / "profiles" / "jarvo-web" / "plugins" / "jarvo-zgody" / "plugin.yaml").is_file()
    assert not (dane / "profiles" / "jarvo" / "plugins" / "jarvo-zgody").exists()
    assert not any((dane / "profiles" / a / "plugins" / "jarvo-komputer").exists() for a in AGENCI)
    assert not (dane / "profiles" / "jarvo" / "plugins" / "jarvo-hq").exists()    # wtyczka samego panelu
    # klucze zależne od instalacji (--ustawienia-profili): bez pytania GitHuba, na Windows plik powłoki profilu (H24)
    import yaml
    for a in AGENCI:
        cfg_profilu = yaml.safe_load((dane / "profiles" / a / "config.yaml").read_text(encoding="utf-8"))
        assert cfg_profilu["updates"] == {"check": False}
        assert ("shell_init_files" in (cfg_profilu.get("terminal") or {})) is WINDOWS
    # host: model floty (--first-run), zakładki panelu i wtyczka z plugins.enabled configu hosta z buildu
    import yaml
    cfg = yaml.safe_load((dane / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "atrapa/host"
    assert {"jarvo-hq", "jarvo-wiedza", "jarvo-zgody"} <= set(cfg["plugins"]["enabled"])
    assert b"\r\n" not in (dane / "config.yaml").read_bytes()                      # LF także na Windows
    assert (dane / "SOUL.md").read_text(encoding="utf-8") == "# Host floty\n"
    # katalogi floty, szablony, skarbiec, tablica, motywy
    jd = dane / "jarvo"
    assert (jd / "missions" / "INDEX.md").read_text(encoding="utf-8") == "# Misje\n"
    assert (jd / "knowledge" / "user" / "USER.md").is_file()
    assert (jd / "knowledge" / "brands" / "_szablon" / "BRAND.md").is_file()
    assert all((jd / "workspaces" / a).is_dir() for a in AGENCI)
    assert (jd / "knowledge" / "INDEX.md").is_file() and (jd / "knowledge" / "LINT.md").is_file()
    assert (dane / "kanban.db").is_file() and any((dane / "dashboard-themes").glob("*.yaml"))
    # polecenia Hermesa: -p default, profile bez --alias (H14), istniejący katalog bez manifestu z --force
    wywolania = [json.loads(x) for x in (dane / ".atrapa-hermesa.log").read_text(encoding="utf-8").splitlines()]
    instalacje = [x for x in wywolania if x[2:4] == ["profile", "install"]]
    assert [x[:2] for x in wywolania] == [["-p", "default"]] * len(wywolania)
    assert len(instalacje) == 2 and not any("--alias" in x for x in instalacje)
    assert ["--force" in x for x in instalacje] == [False, True]


def test_klucze_api_wygenerowane_tylko_brakujace(dwa_przebiegi):
    dane = dwa_przebiegi["dane"]
    for plik in (dane / ".env", dane / "profiles" / "jarvo" / ".env"):
        assert re.fullmatch(r"[0-9a-f]{64}", _env(plik)["API_SERVER_KEY"])
        if not WINDOWS:
            assert stat.S_IMODE(plik.stat().st_mode) == 0o600
    assert _env(dane / "profiles" / "jarvo-web" / ".env")["API_SERVER_KEY"] == KLUCZ_WEB
    assert _env(dane / ".env")["OPENROUTER_API_KEY"] == SEKRET_HOSTA
    # wspólne klucze: klucz dostawcy z .env hosta trafia do agentów (share_keys.py), klucz API nigdy
    assert _env(dane / "profiles" / "jarvo" / ".env")["OPENROUTER_API_KEY"] == SEKRET_HOSTA
    assert _env(dane / ".env")["API_SERVER_KEY"] != _env(dane / "profiles" / "jarvo" / ".env")["API_SERVER_KEY"]


def test_sekrety_nie_trafiaja_do_logu(dwa_przebiegi):
    s = dwa_przebiegi
    dane = s["dane"]
    sekrety = {SEKRET_HOSTA, KLUCZ_WEB}
    for plik in (dane / ".env", *(dane / "profiles").glob("*/.env")):
        sekrety.add(_env(plik)["API_SERVER_KEY"])
    assert len(sekrety) == 2 + len(AGENCI)
    wyjscie = "".join(s[r].stdout + s[r].stderr for r in ("r1", "r2"))
    podsumowania = json.dumps([s["w1"], s["w2"]], ensure_ascii=False)
    assert "debug API_SERVER_KEY=***" in wyjscie and "debug OPENROUTER_API_KEY=***" in wyjscie   # atrapa gada
    for sekret in sekrety:
        assert sekret not in wyjscie and sekret not in podsumowania
    assert "+ API_SERVER_KEY dla host" in s["r1"].stdout


def test_drugi_przebieg_niczego_nie_zmienia(dwa_przebiegi):
    s = dwa_przebiegi
    assert s["r2"].returncode == 0, s["r2"].stdout + s["r2"].stderr
    w = s["w2"]
    assert w["zmiany"] == [] and w["klucze_nowe"] == []
    assert not w["restart_bramy"] and not w["restart_panelu"] and not w["restart"]
    assert w["wtyczki"] == {n: "bez zmian" for n in install_fleet.WTYCZKI}
    assert w["odcisk_panelu"] == s["w1"]["odcisk_panelu"]
    assert "= restart niepotrzebny" in s["r2"].stdout
    roznice = sorted(k for k in set(s["m1"]) | set(s["m2"]) if s["m1"].get(k) != s["m2"].get(k))
    assert roznice == []
    wywolania = [json.loads(x) for x in (s["dane"] / ".atrapa-hermesa.log").read_text(encoding="utf-8").splitlines()]
    assert sum(x[2:4] == ["profile", "update"] for x in wywolania) == len(AGENCI)
    assert sum(x[2:4] == ["plugins", "enable"] for x in wywolania) == 3          # tylko w pierwszym przebiegu


def test_brak_buildu_to_blad_z_rada(tmp_path):
    hermes = atrapy.program(tmp_path / "venv", "python", ATRAPA_HERMESA)
    r = subprocess.run([sys.executable, str(SKRYPT), "--dane", str(tmp_path / "dane"), "--build",
                        str(tmp_path / "pusty"), "--hermes-python", str(hermes), "--natywnie", "--bez-sekretow"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 1
    assert "BUILD.json: najpierw scripts/build.py" in r.stdout


# --- pojedyncze kroki (w tym procesie) ------------------------------------------------------------------------------

def flota_na(dane: Path, build: Path, *dodatki: str) -> install_fleet.Flota:
    a = install_fleet.parser().parse_args(["--dane", str(dane), "--build", str(build), "--natywnie",
                                           "--bez-sekretow", *dodatki])
    return install_fleet.Flota(a, wypisz=lambda _t: None)


def test_dowiazanie_wtyczki_i_jego_usuniecie(tmp_path):
    dane = tmp_path / "dane"
    _pisz(dane / "plugins" / "jarvo-zgody" / "plugin.yaml", "name: jarvo-zgody\n")
    f = flota_na(dane, tmp_path / "build")
    assert f.dowiaz("jarvo-zgody", "jarvo-web") == ("junction" if WINDOWS else "symlink")
    link = dane / "profiles" / "jarvo-web" / "plugins" / "jarvo-zgody"
    assert (link / "plugin.yaml").read_text(encoding="utf-8") == "name: jarvo-zgody\n"
    assert [z["co"] for z in f.zmiany] == ["wtyczka jarvo-zgody w jarvo-web"]
    f.dowiaz("jarvo-zgody", "jarvo-web")                       # już jest: bez zmian
    assert len(f.zmiany) == 1
    f.odwiaz("jarvo-zgody", "jarvo-web")
    assert not link.exists() and not install_fleet._link(link)
    assert (dane / "plugins" / "jarvo-zgody" / "plugin.yaml").is_file()   # usunięte samo dowiązanie, nie cel
    # w miejscu dowiązania stara kopia wtyczki: podmiana na dowiązanie bez resztek .jarvo-old
    _pisz(link / "stary.py", "# stara kopia\n")
    f.dowiaz("jarvo-zgody", "jarvo-web")
    assert install_fleet._link(link) and not (link / "stary.py").exists()
    assert sorted(p.name for p in link.parent.iterdir()) == ["jarvo-zgody"]


def test_resztki_przerwanej_podmiany_znikaja_takze_bez_zmian_we_wtyczce(tmp_path):
    """Katalog .new/.old albo tymczasowe dowiązanie po przerwanym przebiegu ma plugin.yaml: Hermes wziąłby je za
    drugą kopię wtyczki, więc znikają przy każdym przebiegu, także gdy wtyczka się nie zmieniła."""
    build, dane = tmp_path / "build", tmp_path / "dane"
    wspolne, profil = dane / "plugins", dane / "profiles" / "jarvo" / "plugins"
    for kat in (build / "plugins" / "jarvo-zgody", wspolne / "jarvo-zgody", wspolne / "jarvo-zgody.old",
                profil / ".jarvo-zgody.jarvo-old", profil / "jarvo-zgody.new"):
        _pisz(kat / "plugin.yaml", "name: jarvo-zgody\n")
    f = flota_na(dane, build)
    assert f.wtyczka("jarvo-zgody") == "bez zmian"
    f.dowiaz("jarvo-zgody", "jarvo")
    assert sorted(p.name for p in wspolne.iterdir()) == ["jarvo-zgody"]
    assert sorted(p.name for p in profil.iterdir()) == ["jarvo-zgody"]


def test_podmiana_katalogu_wtyczki_atomowo(tmp_path):
    src, cel = tmp_path / "build" / "w", tmp_path / "dane" / "w"
    _pisz(src / "a.py", "nowa\n")
    _pisz(cel / "a.py", "stara\n")
    _pisz(cel / "usuniety.py", "x\n")
    _pisz(cel / "__pycache__" / "a.pyc", "bajty")
    _pisz(cel.with_name("w.new") / "resztka.py", "po przerwanym przebiegu\n")
    install_fleet.podmien_katalog(src, cel)
    assert install_fleet.spis(cel) == install_fleet.spis(src)
    assert sorted(p.name for p in cel.parent.iterdir()) == ["w"]
    assert install_fleet.spis(src.parent / "brak") == {}


def test_odcisk_profilu_bez_znacznika_czasu_hermesa(tmp_path):
    home = tmp_path / "profil"
    _pisz(home / "distribution.yaml", "name: jarvo\nsource: /b\ninstalled_at: '2026-10-25T01:00:00+00:00'\n")
    _pisz(home / "config.yaml", "model: {}\n")
    f = flota_na(tmp_path / "dane", tmp_path / "build")
    przed = f.odcisk_profilu(home)
    _pisz(home / "distribution.yaml", "name: jarvo\nsource: /b\ninstalled_at: '2026-10-25T02:00:00+00:00'\n")
    assert f.odcisk_profilu(home) == przed
    _pisz(home / "distribution.yaml", "name: jarvo\nsource: /inny\ninstalled_at: '2026-10-25T02:00:00+00:00'\n")
    assert f.odcisk_profilu(home) != przed


def test_zrodlo_dystrybucji_idzie_za_buildem(tmp_path):
    f = flota_na(tmp_path / "dane", tmp_path / "build")
    manifest = tmp_path / "distribution.yaml"
    zrodlo = tmp_path / "build" / "profiles" / "jarvo"
    _pisz(manifest, "name: jarvo\nsource: /opt/tars/build/profiles/jarvo\nversion: 0.1.0\n")
    f.ustaw_zrodlo(manifest, zrodlo)
    tekst = manifest.read_text(encoding="utf-8")
    assert f"source: '{zrodlo.as_posix()}'\n" in tekst and tekst.endswith("version: 0.1.0\n")
    _pisz(manifest, f"name: jarvo\nsource: {zrodlo}\n")         # Hermes zapisuje ścieżkę z resolve(): bez zapisu
    przed = manifest.stat().st_mtime_ns
    f.ustaw_zrodlo(manifest, zrodlo)
    assert manifest.stat().st_mtime_ns == przed


def test_zapis_yaml_pomocnikow_z_lf_i_tylko_przy_zmianie(tmp_path):
    plik = tmp_path / "config.yaml"
    zapisz = install_fleet._zapis_yaml_lf(lambda dane, p: Path(p).write_text(f"a: {dane}\n", encoding="utf-8"))
    zapisz(1, plik)
    assert plik.read_bytes() == b"a: 1\n"
    przed = plik.stat().st_mtime_ns
    zapisz(1, plik)
    assert plik.stat().st_mtime_ns == przed and sorted(p.name for p in tmp_path.iterdir()) == ["config.yaml"]


def test_log_maskuje_sekrety_z_env(tmp_path):
    linie: list[str] = []
    log = install_fleet.Log(linie.append)
    _pisz(tmp_path / ".env", f'# komentarz\nOPENROUTER_API_KEY="{SEKRET_HOSTA}"\nTRYB=projekt\n'
                             f"TELEGRAM_BOT_TOKEN=123456:abcdefgh # bot\n")
    log.z_pliku(tmp_path / ".env")
    log(f"klucz {SEKRET_HOSTA}, bot 123456:abcdefgh, tryb projekt")
    assert linie == ["klucz ***, bot ***, tryb projekt"]


# --- jarvo/flota.py ------------------------------------------------------------------------------------------------

ATRAPA_BUILDU = r'''
import json, os, sys
from pathlib import Path
if "--help" in sys.argv:
    print("usage: build.py [-h] [--out OUT]\n\nBuduje dystrybucje (--repo-dir w opisie to nie opcja)\n\noptions:")
    opcje = ["-h, --help", "--out OUT", "--hermes-src HERMES_SRC", "--cache CACHE", "--env-file ENV_FILE",
             "--wybor-modelu WYBOR_MODELU", "--runtime-build-dir RUNTIME_BUILD_DIR"]
    for o in opcje + os.environ.get("ATRAPA_OPCJE", "--uklad {kontener,natywny},--dane DANE,--py PY").split(","):
        print(f"  {o}    opis")
    sys.exit(0)
a = sys.argv[1:]
out = Path(a[a.index("--out") + 1])
out.mkdir(parents=True, exist_ok=True)
(out / "argv.json").write_text(json.dumps({"argv": a, "env": {k: os.environ.get(k) for k in (
    "HERMES_HOME", "JARVO_HERMES_PYTHON", "PYTHONPATH", "HERMES_YOLO_MODE", "PYTHONUTF8")}}), encoding="utf-8")
print("Build gotowy")
kod = int(os.environ.get("ATRAPA_KOD_BUILDU", "0"))
if not kod:
    (out / "BUILD.json").write_text(json.dumps({"agents": [{"agent": "jarvo"}]}), encoding="utf-8")
sys.exit(kod)
'''

ATRAPA_INSTALACJI = r'''
import json, sys
from pathlib import Path
a = sys.argv[1:]
Path(a[a.index("--dane") + 1], "argv-instalacji.json").write_text(json.dumps(a), encoding="utf-8")
print("▶ Katalogi floty")
Path(a[a.index("--podsumowanie") + 1]).write_text(json.dumps({
    "wersja": 1, "agenci": ["jarvo"], "zmiany": ["profil jarvo"], "restart_bramy": True, "restart_panelu": False,
    "restart": True, "odcisk_panelu": "0123456789abcdef"}), encoding="utf-8")
'''


@pytest.fixture
def instalacja(tmp_path, monkeypatch):
    root = tmp_path / "Jarvo Ż"
    u = uklad(root)
    app = tmp_path / "app"
    _pisz(app / "scripts" / "build.py", ATRAPA_BUILDU)
    _pisz(app / "scripts" / "install_fleet.py", ATRAPA_INSTALACJI)
    checkout = tmp_path / "hermes"
    _pisz(u.program / "current.json", json.dumps({"app": str(app), "hermes": str(checkout)}))
    monkeypatch.setattr(flota, "python_hermesa", lambda _u: (checkout, Path(sys.executable)))
    env = {**os.environ, "PYTHONPATH": str(tmp_path / "obcy"), "HERMES_YOLO_MODE": "1", "HERMES_HOME": "zly"}
    return u, app, checkout, env


def test_zainstaluj_flote_build_z_kontraktu_i_instalacja(instalacja):
    u, app, checkout, env = instalacja
    linie: list[str] = []
    wynik = flota.zainstaluj_flote(u, env, log=linie.append)
    zapis = json.loads((u.build / "argv.json").read_text(encoding="utf-8"))
    a = zapis["argv"]

    def wartosc(opcja: str) -> str:
        return a[a.index(opcja) + 1]

    assert wartosc("--hermes-src") == str(checkout) and wartosc("--out") == str(u.build)
    assert wartosc("--runtime-build-dir") == u.build.as_posix() and wartosc("--cache") == str(u.cache / "build")
    assert wartosc("--dane") == u.dane.as_posix() and wartosc("--py") == Path(sys.executable).as_posix()
    assert wartosc("--uklad") == "natywny"                                     # inaczej build zostaje kontenerowy
    assert "--repo-dir" not in a and "--env-file" not in a and "--system" not in a   # nieznane / brak pliku
    assert zapis["env"] == {"HERMES_HOME": str(u.dane), "JARVO_HERMES_PYTHON": sys.executable, "PYTHONPATH": None,
                            "HERMES_YOLO_MODE": None, "PYTHONUTF8": "1"}
    inst = json.loads((u.dane / "argv-instalacji.json").read_text(encoding="utf-8"))
    assert inst[inst.index("--repo") + 1] == str(app) and inst[inst.index("--build") + 1] == str(u.build)
    assert inst[inst.index("--narzedzia") + 1] == str(u.program / "narzedzia-floty")
    assert {"--natywnie", "--bez-sekretow", "--first-run"} <= set(inst) and "--resume-cron" not in inst
    assert wynik["agenci"] == ["jarvo"] and wynik["pierwsza"] is True
    assert wynik["build"]["opcje"] == {"DATA_DIR": "--dane", "PY": "--py"}
    assert wynik["build"]["bez_opcji"] == ["REPO_DIR", "TOOLS_DIR", "BIN_DIR"]
    assert wynik["build"]["tokeny"]["KNOWLEDGE_DIR"] == (u.dane / "jarvo" / "knowledge").as_posix()
    assert any("nie zna opcji dla tokenów REPO_DIR, TOOLS_DIR, BIN_DIR" in x for x in linie)
    assert "    Build gotowy" in linie and "  ▶ Katalogi floty" in linie
    assert flota.uslugi_do_restartu(wynik) == ["brama"]


def test_build_z_wszystkimi_opcjami_kontraktu_i_bez_nich(instalacja):
    u, app, _checkout, env = instalacja
    pelne = "--uklad {kontener,natywny},--system {windows,macos,linux},--dane DANE,--repo-dir REPO_DIR," \
            "--bin-dir BIN_DIR,--tools-dir TOOLS_DIR,--py PY"
    wynik = flota.zainstaluj_flote(u, {**env, "ATRAPA_OPCJE": pelne}, log=lambda _t: None)
    a = json.loads((u.build / "argv.json").read_text(encoding="utf-8"))["argv"]
    assert a[a.index("--system") + 1] == flota.system() and a[a.index("--uklad") + 1] == "natywny"
    assert a[a.index("--repo-dir") + 1] == app.as_posix()
    assert a[a.index("--tools-dir") + 1] == (u.program / "narzedzia-floty").as_posix()
    assert a[a.index("--bin-dir") + 1] == (u.program / "bin-floty").as_posix()
    assert wynik["build"]["bez_opcji"] == [] and set(wynik["build"]["opcje"]) == {t for t, _ in flota.OPCJE_BUILDU}
    # dzisiejszy build.py (bez opcji układu): same opcje kontenera, wszystkie tokeny w bez_opcji
    wynik = flota.zainstaluj_flote(u, {**env, "ATRAPA_OPCJE": "--agent AGENT"}, log=lambda _t: None)
    a = json.loads((u.build / "argv.json").read_text(encoding="utf-8"))["argv"]
    assert not {"--uklad", "--dane", "--py"} & set(a)
    assert wynik["build"]["bez_opcji"] == [t for t, _ in flota.OPCJE_BUILDU] and wynik["pierwsza"] is True


def test_flota_zainstalowana_bez_first_run_z_rutynami(instalacja):
    u, _app, _checkout, env = instalacja
    _pisz(u.dane / "profiles" / "jarvo" / "distribution.yaml", "name: jarvo\n")
    _pisz(u.jarvo_dane / "konfig" / "host.env", "X=1\n")
    _pisz(u.jarvo_dane / "konfig" / "jarvo.env", "TELEGRAM_OWNER_ID=1\n")
    wynik = flota.zainstaluj_flote(u, env, log=lambda _t: None, wznow_rutyny=True)
    inst = json.loads((u.dane / "argv-instalacji.json").read_text(encoding="utf-8"))
    assert "--first-run" not in inst and "--resume-cron" in inst and wynik["pierwsza"] is False
    assert inst[inst.index("--sekrety") + 1] == str(u.jarvo_dane / "konfig") and "--bez-sekretow" not in inst
    a = json.loads((u.build / "argv.json").read_text(encoding="utf-8"))["argv"]
    assert a[a.index("--env-file") + 1] == str(u.jarvo_dane / "konfig" / "jarvo.env")


def test_blad_buildu_zatrzymuje_instalacje(instalacja):
    u, _app, _checkout, env = instalacja
    with pytest.raises(flota.BladFloty, match=r"build floty nie przeszedł \(kod 3\)"):
        flota.zainstaluj_flote(u, {**env, "ATRAPA_KOD_BUILDU": "3"}, log=lambda _t: None)
    assert not (u.dane / "argv-instalacji.json").exists()


def test_bez_hermesa_jasny_blad(tmp_path):
    with pytest.raises(flota.BladFloty, match="jarvo instaluj"):
        flota.zainstaluj_flote(uklad(tmp_path / "Jarvo"), dict(os.environ), log=lambda _t: None)


def test_potwierdzenie_restartu_panelu(tmp_path):
    u = uklad(tmp_path / "Jarvo")
    assert flota.potwierdz_restart_panelu(u, "0123456789abcdef")
    assert (u.dane / "plugins" / ".odcisk-panelu").read_text(encoding="utf-8") == "0123456789abcdef\n"
    assert not flota.potwierdz_restart_panelu(u, "0123456789abcdef")           # ten sam: bez zapisu
    assert not flota.potwierdz_restart_panelu(u, "") and not flota.potwierdz_restart_panelu(u, "../../x")
    assert flota.uslugi_do_restartu({"restart_bramy": True, "restart_panelu": True}) == ["brama", "panel"]
    assert flota.uslugi_do_restartu({}) == []


def test_tokeny_z_ukosnikiem_i_py_w_cudzyslowie(tmp_path):
    u = uklad(tmp_path / "Jarvo Ż")
    t = flota.wartosci_tokenow(u, tmp_path / "app", tmp_path / "Michał Żółć" / "python.exe")
    assert all("\\" not in v for v in t.values())
    assert t["DATA_DIR"] == u.dane.as_posix() and t["JARVO_DIR"] == (u.dane / "jarvo").as_posix()
    assert t["INBOX_DIR"].endswith("/dane/jarvo/inbox") and t["BIN_DIR"].endswith("/program/bin-floty")
    assert t["TOOLS_DIR"].endswith("/program/narzedzia-floty") and t["BUILD_DIR"] == u.build.as_posix()
    assert t["PY"] == f'"{(tmp_path / "Michał Żółć" / "python.exe").as_posix()}"'
    assert flota.wartosci_tokenow(u, tmp_path, Path("/opt/py/python3"))["PY"] == "/opt/py/python3"
    assert flota.wartosci_tokenow(u, tmp_path, Path("/home/michał/py"))["PY"] == '"/home/michał/py"'


def test_opcje_prawdziwego_build_py():
    """flota.py woła build.py opcjami, które ma dzisiejszy build.py (kontrakt z deploy.sh)."""
    env = {**os.environ, "PYTHONUTF8": "1"}
    env.pop("PYTHONPATH", None)
    znane = flota.opcje_buildu(Path(sys.executable), REPO / "scripts" / "build.py", env, REPO)
    assert {"--out", "--hermes-src", "--cache", "--env-file", "--wybor-modelu", "--runtime-build-dir"} <= znane
    assert not any(o.startswith("--opt") for o in znane)


def test_argumenty_namespace_kontenera_jak_install_fleet_sh():
    a = install_fleet.parser().parse_args([])
    assert isinstance(a, argparse.Namespace)
    assert (a.dane, a.build, a.sekrety) == ("/opt/data", "/opt/jarvo/build", "/opt/jarvo/secrets")
    assert not a.natywnie and not a.bez_sekretow                                  # kontener: profile z --alias
