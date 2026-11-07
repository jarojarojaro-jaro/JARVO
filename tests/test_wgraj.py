"""Wgrywanie stron (profiles/jarvo/scripts/wgraj.py): plan, wgranie z kopią i weryfikacją sum, tag i main, cofnięcie,
odmowy, z-buildu, podgląd, blokada floty i jedna próba połączenia SSH. Serwer to katalog tymczasowy
(`PolaczenieLokalne`), origin to lokalne repo bare."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import load_script

pytestmark = pytest.mark.skipif(os.name == "nt" or not shutil.which("rsync") or not shutil.which("git"),
                                reason="potrzebne rsync i git (Linux albo macOS)")

w = load_script("profiles/jarvo/scripts/wgraj.py", "jarvo_wgraj_test")

DOMENA = "przyklad.pl"
KAT = f"domains/{DOMENA}/public_html"
KONF = {"domena": DOMENA, "katalog_na_serwerze": KAT, "zrodlo": "test", "kopie_na_serwerze": 2,
        "chronione": ["api/config.php", "cgi-bin/", ".well-known/", "*.sqlite", ".env*"],
        "z_buildu": [], "zakazane_sciezki": [], "zakazane_wzorce": [], "wymagane_teksty": {}}


def g(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def zapisz(korzen: Path, pliki: dict[str, str]) -> None:
    for sciezka, tresc in pliki.items():
        p = korzen / sciezka
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(tresc, encoding="utf-8")


def commit(repo: Path, pliki: dict[str, str], msg: str = "zmiana", *, sila: bool = False) -> str:
    zapisz(repo, pliki)
    g(repo, "add", *(["-f"] if sila else []), "-A", *pliki)
    g(repo, "commit", "-q", "-m", msg)
    return g(repo, "rev-parse", "HEAD")


def ustaw_konf(repo: Path, **zmiany) -> str:
    return commit(repo, {".strona.json": json.dumps({**KONF, **zmiany})}, "konfiguracja")


@pytest.fixture
def strona(tmp_path, monkeypatch):
    pusty = tmp_path / "gitconfig"
    pusty.write_text("")
    for k, v in {"GIT_CONFIG_GLOBAL": str(pusty), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                 "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                 "JARVO_STATE_DIR": str(tmp_path / "stan"), "JARVO_PODGLAD_DIR": str(tmp_path / "podglad")}.items():
        monkeypatch.setenv(k, v)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    g(repo, "remote", "add", "origin", str(origin))
    commit(repo, {".strona.json": json.dumps(KONF), ".gitignore": "api/config.php\n*.sqlite\n.env*\n",
                  ".github/README.md": "# repo\n", "index.html": "<h1>stara</h1>\n", "js/app.js": "var a=1;\n",
                  "robots.txt": "User-agent: *\n", "cgi-bin/.htaccess": "Deny from all # z repo\n"}, "stan na żywo")
    g(repo, "tag", "zywo-2026-11-07")
    g(repo, "push", "-q", "origin", "main", "--tags")
    dom = tmp_path / "dom"
    zapisz(dom / KAT, {"index.html": "<h1>stara</h1>\n", "js/app.js": "var a=0;\n", "stary.html": "stary\n",
                       "api/config.php": "<?php $haslo='x';\n", "dane.sqlite": "SQL", "cgi-bin/.htaccess": "serwer\n",
                       ".well-known/acme": "token\n"})
    return {"repo": repo, "origin": origin, "dom": dom, "srv": dom / KAT, "pol": w.PolaczenieLokalne(dom),
            "tmp": tmp_path}


def uruchom(s, *argv, capsys=None):
    kod = w.main(["--json", *argv], pol=s["pol"])
    return kod, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def drzewo(katalog: Path) -> dict[str, str]:
    return {p.relative_to(katalog).as_posix(): p.read_text() for p in katalog.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(katalog).parts}


def test_wzorce_rsync_i_gitignore():
    assert w.Wzorzec("cgi-bin/").pasuje("cgi-bin/.htaccess") and w.Wzorzec("cgi-bin/").pasuje("a/cgi-bin/x")
    assert not w.Wzorzec("cgi-bin/").pasuje("cgi-bin")                  # plik, nie katalog
    assert w.Wzorzec("*.sqlite").pasuje("x/dane.sqlite") and not w.Wzorzec("*.sqlite").pasuje("dane.sqlite3")
    assert w.Wzorzec("api/config.php").pasuje("x/api/config.php")       # rsync: końcówka ścieżki
    assert not w.Wzorzec("api/config.php", gitignore=True).pasuje("x/api/config.php")   # gitignore: od korzenia
    assert w.Wzorzec("/.git").pasuje(".git/config") and not w.Wzorzec("/.git").pasuje("a/.git/config")
    assert w.Wzorzec(".env*").pasuje(".env.local") and w.Wzorzec("**/tajne").pasuje("a/b/tajne/c")


def test_plan_dodane_zmienione_usuniete_bez_chronionych(strona, capsys):
    s = strona
    commit(s["repo"], {"nowy.html": "nowy\n"})
    kod, plan = uruchom(s, "plan", str(s["repo"]), capsys=capsys)
    assert kod == 0
    assert plan["dodane"] == ["nowy.html", "robots.txt"] and plan["zmienione"] == ["js/app.js"]
    assert plan["usuniete"] == ["stary.html"] and plan["bez_zmian"] == 1
    assert plan["pominiete_chronione"] == ["cgi-bin/.htaccess"]
    assert plan["odcisk"] == g(s["repo"], "rev-parse", "HEAD^{tree}") and plan["pliki"] == 4
    assert "--odcisk " + plan["odcisk"] in plan["polecenie"]
    assert drzewo(s["srv"])["stary.html"] == "stary\n"                    # plan nic nie zapisuje


def test_wgraj_kopia_weryfikacja_tag_i_main(strona, capsys):
    s = strona
    kopie = s["dom"] / "kopie-stron" / DOMENA
    zapisz(kopie, {"20200101-000000.tar.gz": "a", "20200102-000000.tar.gz": "b", "notatka.txt": "c"})
    g(s["repo"], "checkout", "-q", "-b", "zmiana")
    rev = commit(s["repo"], {"index.html": "<h1>nowa</h1>\n", "nowy.html": "nowy\n"})
    g(s["repo"], "checkout", "-q", "main")
    odcisk = g(s["repo"], "rev-parse", "zmiana^{tree}")
    kod, raport = uruchom(s, "wgraj", str(s["repo"]), "--wersja", "zmiana", "--odcisk", odcisk, capsys=capsys)
    assert kod == 0 and raport["wynik"] == "ok" and raport["rev"] == rev
    assert raport["liczby"] == {"pliki": 4, "dodane": 2, "zmienione": 2, "usuniete": 1, "bez_zmian": 0}
    pliki = drzewo(s["srv"])
    assert pliki["index.html"] == "<h1>nowa</h1>\n" and pliki["robots.txt"] == "User-agent: *\n"
    assert "stary.html" not in pliki
    assert pliki["api/config.php"] == "<?php $haslo='x';\n" and pliki["dane.sqlite"] == "SQL"
    assert pliki["cgi-bin/.htaccess"] == "serwer\n" and pliki[".well-known/acme"] == "token\n"
    assert not {".strona.json", ".gitignore", ".github/README.md"} & set(pliki)
    nazwy = sorted(p.name for p in kopie.iterdir())
    assert len([n for n in nazwy if n.endswith(".tar.gz")]) == 2 and "20200101-000000.tar.gz" not in nazwy
    assert "notatka.txt" in nazwy and raport["usuniete_kopie"] == ["20200101-000000.tar.gz"]
    nowa = kopie / raport["kopia"].rsplit("/", 1)[1]
    lista = subprocess.run(["tar", "-tzf", str(nowa)], capture_output=True, text=True, check=True).stdout
    assert "./stary.html" in lista and "./api/config.php" in lista
    tag = raport["tag"]
    assert tag.startswith("wgranie-") and g(s["origin"], "rev-parse", f"refs/tags/{tag}") == rev
    assert g(s["origin"], "rev-parse", "main") == rev and g(s["repo"], "rev-parse", "main") == rev
    assert raport["main"] == "przewinięty"
    log = (s["tmp"] / "stan" / "wgrywanie.jsonl").read_text().splitlines()
    assert json.loads(log[-1])["odcisk"] == odcisk
    kod, k = uruchom(s, "kopie", str(s["repo"]), capsys=capsys)
    assert kod == 0 and k["kopie"][0]["nazwa"] == nowa.name and len(k["kopie"]) == 2


def test_wgraj_odmawia_bez_zmian_na_serwerze(strona, capsys):
    s = strona
    przed = drzewo(s["srv"])
    kod, wynik = uruchom(s, "wgraj", str(s["repo"]), "--odcisk", "0" * 40, capsys=capsys)
    assert kod == 1 and "Odcisk" in wynik["blad"]
    (s["repo"] / "index.html").write_text("brudne\n")
    odcisk = g(s["repo"], "rev-parse", "HEAD^{tree}")
    kod, wynik = uruchom(s, "wgraj", str(s["repo"]), "--odcisk", odcisk, capsys=capsys)
    assert kod == 1 and "niezatwierdzone" in wynik["blad"]
    assert drzewo(s["srv"]) == przed and not (s["dom"] / "kopie-stron").exists()


def test_wgraj_odmawia_gdy_main_nie_przewija_sie(strona, capsys):
    s = strona
    g(s["repo"], "checkout", "-q", "-b", "boczna", "zywo-2026-11-07")
    commit(s["repo"], {"a.html": "a\n"})
    g(s["repo"], "checkout", "-q", "main")
    commit(s["repo"], {"b.html": "b\n"})
    g(s["repo"], "push", "-q", "origin", "main")
    kod, wynik = uruchom(s, "wgraj", str(s["repo"]), "--wersja", "boczna",
                         "--odcisk", g(s["repo"], "rev-parse", "boczna^{tree}"), capsys=capsys)
    assert kod == 1 and "przewinięciem" in wynik["blad"] and not (s["dom"] / "kopie-stron").exists()


@pytest.mark.parametrize("zmiany, pliki, sila, fragment", [
    ({"zakazane_sciezki": ["kernel/"]}, {"kernel/x.js": "1"}, False, "zakazana ścieżka"),
    ({"zakazane_wzorce": [r"(?<!github\.com/jarojarojaro-jaro/)KERNEL/"]}, {"x.html": "~/KERNEL/deploy"}, False,
     "zakazany wzorzec"),
    ({"wymagane_teksty": {"index.html": "Polityka"}}, {}, False, "brak wymaganego tekstu"),
    ({}, {"api/config.php": "<?php $haslo='x';"}, True, "śledzony sekret api/config.php"),
])
def test_sprawdz_odmowy(strona, capsys, zmiany, pliki, sila, fragment):
    s = strona
    if zmiany:
        ustaw_konf(s["repo"], **zmiany)
    if pliki:
        commit(s["repo"], pliki, sila=sila)
    kod, wynik = uruchom(s, "sprawdz", str(s["repo"]), capsys=capsys)
    assert kod == 1 and fragment in wynik["blad"]


def test_lookbehind_przepuszcza_link_do_repo(strona, capsys):
    s = strona
    ustaw_konf(s["repo"], zakazane_wzorce=[r"(?<!github\.com/jarojarojaro-jaro/)KERNEL/"],
               wymagane_teksty={"index.html": "stara"})
    commit(s["repo"], {"o.html": '<a href="https://github.com/jarojarojaro-jaro/KERNEL/releases">KERNEL</a>'})
    kod, wynik = uruchom(s, "sprawdz", str(s["repo"]), capsys=capsys)
    assert kod == 0 and wynik["pominiete_chronione"] == ["cgi-bin/.htaccess"]


def test_weryfikacja_wykrywa_niezgodnosc(strona, capsys, monkeypatch):
    s = strona
    commit(s["repo"], {"index.html": "<h1>nowa</h1>\n"})
    prawdziwy = subprocess.run

    def run(argv, *a, **k):
        r = prawdziwy(argv, *a, **k)
        if argv[0] == "rsync":
            (s["srv"] / "index.html").write_text("zepsute\n")
        return r

    monkeypatch.setattr(w.subprocess, "run", run)
    kod, raport = uruchom(s, "wgraj", str(s["repo"]), "--odcisk", g(s["repo"], "rev-parse", "HEAD^{tree}"),
                          capsys=capsys)
    assert kod == w.KOD_WERYFIKACJI and raport["wynik"] == "blad" and raport["niezgodne"] == ["index.html"]
    zywo = g(s["repo"], "rev-parse", "zywo-2026-11-07^{tree}")
    assert raport["cofnij"].endswith(f"--do zywo-2026-11-07 --odcisk {zywo}")
    assert not g(s["repo"], "tag", "--list", "wgranie-*") and "tag" not in raport


def test_cofnij_przywraca_stare_drzewo_nowym_commitem(strona, capsys):
    s = strona
    commit(s["repo"], {"index.html": "<h1>nowa</h1>\n"})
    kod, _ = uruchom(s, "wgraj", str(s["repo"]), "--odcisk", g(s["repo"], "rev-parse", "HEAD^{tree}"), capsys=capsys)
    assert kod == 0 and (s["srv"] / "index.html").read_text() == "<h1>nowa</h1>\n"
    nowy_main = g(s["origin"], "rev-parse", "main")
    zywo = g(s["repo"], "rev-parse", "zywo-2026-11-07^{tree}")
    kod, raport = uruchom(s, "cofnij", str(s["repo"]), "--do", "zywo-2026-11-07", "--odcisk", zywo, capsys=capsys)
    assert kod == 0 and raport["cofniecie_do"] == "zywo-2026-11-07", raport
    main = g(s["origin"], "rev-parse", "main")
    assert main != nowy_main and g(s["origin"], "rev-parse", "main^") == nowy_main
    assert g(s["origin"], "rev-parse", "main^{tree}") == zywo
    assert g(s["origin"], "log", "-1", "--format=%s", "main") == "Cofnięcie do zywo-2026-11-07"
    assert (s["srv"] / "index.html").read_text() == "<h1>stara</h1>\n" and g(s["repo"], "rev-parse", "HEAD") == main
    kod, wynik = uruchom(s, "cofnij", str(s["repo"]), "--do", "zywo-2026-11-07", "--odcisk", "1" * 40, capsys=capsys)
    assert kod == 1 and "Odcisk" in wynik["blad"]


def test_z_buildu_podmienia_tylko_wpisy(strona, capsys):
    s = strona
    kod, wynik = uruchom(s, "z-buildu", str(s["repo"]), "--build", str(s["tmp"]), capsys=capsys)
    assert kod == 1 and "z_buildu jest puste" in wynik["blad"]
    ustaw_konf(s["repo"], z_buildu=["_app", "index.html", "pl"])
    commit(s["repo"], {"_app/stary.js": "1", "pl/stara.html": "pl"})
    build = s["tmp"] / "build"
    zapisz(build, {"_app/nowy.js": "2", "index.html": "<h1>z builda</h1>", "robots.txt": "build",
                   "inne.html": "x"})
    kod, wynik = uruchom(s, "z-buildu", str(s["repo"]), "--build", str(build), capsys=capsys)
    assert kod == 0 and wynik["podmienione"] == ["_app", "index.html"] and wynik["usuniete"] == ["pl"]
    assert wynik["pominiete_z_buildu"] == ["inne.html", "robots.txt"]
    pliki = drzewo(s["repo"])
    assert pliki["_app/nowy.js"] == "2" and "_app/stary.js" not in pliki and "pl/stara.html" not in pliki
    assert pliki["index.html"] == "<h1>z builda</h1>" and pliki["robots.txt"] == "User-agent: *\n"
    assert "inne.html" not in pliki and any("index.html" in x for x in wynik["status"])


def test_podglad_bez_metadanych(strona, capsys, monkeypatch):
    s = strona
    monkeypatch.setenv("JARVO_PODGLAD_URL", "http://podglad.test/")
    kod, wynik = uruchom(s, "podglad", str(s["repo"]), capsys=capsys)
    baza = s["tmp"] / "podglad"
    assert kod == 0 and wynik["url"] == "http://podglad.test/"
    assert set(drzewo(baza / DOMENA)) == {"index.html", "js/app.js", "robots.txt"}
    assert os.readlink(baza / "aktualny") == DOMENA
    (s["repo"] / "index.html").write_text("robocze\n")
    zapisz(s["repo"], {"api/config.php": "tajne"})
    kod, wynik = uruchom(s, "podglad", str(s["repo"]), "--robocze", capsys=capsys)
    assert kod == 0 and (baza / "aktualny" / "index.html").read_text() == "robocze\n"
    assert not (baza / DOMENA / "api").exists()


def test_blokada_odmawia_po_czekaniu(strona, capsys):
    s = strona
    stan = s["tmp"] / "stan"
    stan.mkdir()
    with open(stan / "wgrywanie.lock", "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        kod, wynik = uruchom(s, "wgraj", str(s["repo"]), "--czekaj", "0.5",
                             "--odcisk", g(s["repo"], "rev-parse", "HEAD^{tree}"), capsys=capsys)
    assert kod == 1 and "Inne wgrywanie trwa" in wynik["blad"] and not (s["dom"] / "kopie-stron").exists()


def test_ssh_jedna_proba_bez_rsync(strona, capsys, monkeypatch):
    s = strona
    bin_ = s["tmp"] / "bin"
    bin_.mkdir()
    dziennik = s["tmp"] / "wywolania.log"
    for prog, kod in (("ssh", 255), ("rsync", 0)):
        p = bin_ / prog
        p.write_text(f'#!/bin/sh\necho "{prog} $*" >> "{dziennik}"\n'
                     + ('echo "Permission denied (publickey)." >&2\n' if prog == "ssh" else "") + f"exit {kod}\n")
        p.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    odcisk = g(s["repo"], "rev-parse", "HEAD^{tree}")
    for argv in (["plan", str(s["repo"])], ["wgraj", str(s["repo"]), "--odcisk", odcisk]):
        dziennik.unlink(missing_ok=True)
        kod = w.main(["--json", "--host", "seohost", *argv])
        wynik = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        wywolania = dziennik.read_text().splitlines()
        assert kod == 1 and "jedna próba" in wynik["blad"] and "Permission denied" in wynik["blad"]
        assert len(wywolania) == 1 and wywolania[0].startswith("ssh ")
        assert "ControlMaster=yes" in wywolania[0] and "ConnectionAttempts=1" in wywolania[0]
        assert wywolania[0].rstrip().endswith("-fN seohost")
    assert not (s["dom"] / "kopie-stron").exists()
