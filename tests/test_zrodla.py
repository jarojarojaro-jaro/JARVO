"""Spis źródeł (scripts/zrodla.py): nowości liczone na lokalnych repo git, bez sieci; zapis przeglądu w miejscu."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import validate
import zrodla


def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**zrodla.GIT_ENV, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}, encoding="utf-8").stdout.strip()


def commit(repo: Path, pliki: dict[str, str | None], tytul: str) -> str:
    for rel, tresc in pliki.items():
        p = repo / rel
        if tresc is None:
            p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(tresc, encoding="utf-8")
    sh(repo, "add", "-A")
    sh(repo, "commit", "-q", "-m", tytul)
    return sh(repo, "rev-parse", "HEAD")


@pytest.fixture
def upstream(tmp_path):
    repo = tmp_path / "upstream"
    repo.mkdir()
    sh(repo, "init", "-q", "-b", "main")
    # jak GitHub: pobieranie po SHA i bez plików (partial clone)
    sh(repo, "config", "uploadpack.allowFilter", "true")
    sh(repo, "config", "uploadpack.allowAnySHA1InWant", "true")
    a = commit(repo, {"LICENSE": "MIT\n", "styles/stary/STYLE.md": "x", "skills/a/SKILL.md": "a"}, "start")
    return repo, a


def spis(tmp_path: Path, url: str, przejrzane: str, status: str = "uzywane") -> Path:
    p = tmp_path / "zrodla.yaml"
    p.write_text("# komentarz zostaje\nversion: 1\n\nzrodla:\n"
                 f"  lemo:\n    repo: {url}\n    status: {status}   # notatka po wartości\n"
                 f"    przejrzane: {przejrzane}\n"
                 f"  inne:\n    repo: {url}\n    status: czeka\n    przejrzane: {przejrzane}\n", encoding="utf-8")
    return p


def test_nowosci_od_przejrzanego(upstream, tmp_path):
    repo, a = upstream
    commit(repo, {"styles/nowy/STYLE.md": "n", "styles/nowy/demo/x.html": "d", "skills/b/SKILL.md": "b",
                  "skills/a/SKILL.md": "a2"}, "Dodaj styl nowy")
    b = commit(repo, {"LICENSE": "MIT + CC BY\n", "styles/stary/STYLE.md": None}, "Licencja")
    p = spis(tmp_path, f"file://{repo}", a)
    w = zrodla.sprawdz(zrodla.wczytaj(p), ["lemo"])[0]
    assert w["zmiany"] and w["glowa"] == b and w["galaz"] == "main" and not w.get("blad")
    assert [c["tytul"] for c in w["commity"]] == ["Licencja", "Dodaj styl nowy"]
    assert w["nowe_katalogi"] == ["skills/b", "styles/nowy"]          # bez styles/nowy/demo (głębiej niż 2)
    assert w["nowe_skille"] == ["skills/b/SKILL.md"] and w["zmienione_skille"] == ["skills/a/SKILL.md"]
    assert w["licencja"] == ["LICENSE"] and w["usuniete"] == ["styles/stary/STYLE.md"]
    assert not w["przepisana"]
    tekst = zrodla.raport([w])
    assert "## lemo (uzywane): 2 commity od" in tekst and "⚠ zmiana licencji: `LICENSE`" in tekst
    assert "nowe katalogi: `skills/b`, `styles/nowy`" in tekst and "przejrzane <nazwa>" in tekst


def test_bez_zmian_i_odlozone_w_skrocie(upstream, tmp_path):
    repo, a = upstream
    p = spis(tmp_path, f"file://{repo}", a, status="odlozone")
    wyniki = zrodla.sprawdz(zrodla.wczytaj(p))
    assert [w["zmiany"] for w in wyniki] == [False, False]
    assert "Nic nowego od ostatniego przeglądu." in zrodla.raport(wyniki)
    commit(repo, {"x.md": "x"}, "x")
    tekst = zrodla.raport(zrodla.sprawdz(zrodla.wczytaj(p), ["lemo"]))
    assert "## Odłożone (tylko skrót)" in tekst and "- lemo: 1 commit" in tekst and "## lemo" not in tekst


def test_przepisana_historia_i_niedostepne(upstream, tmp_path):
    repo, a = upstream
    commit(repo, {"y.md": "y"}, "y")
    p = spis(tmp_path, f"file://{repo}", "f" * 40)                   # takiego commitu nie ma w repo
    w = zrodla.sprawdz(zrodla.wczytaj(p), ["lemo"])[0]
    assert w["przepisana"] and [c["tytul"] for c in w["commity"]] == ["y", "start"] and "dodane" not in w
    assert "ostatnie commity od `fffffff`" in zrodla.raport([w])
    p = spis(tmp_path, f"file://{tmp_path}/nie-ma", a)
    w = zrodla.sprawdz(zrodla.wczytaj(p), ["lemo"])[0]
    assert w["blad"].startswith("niedostępne") and "## Niedostępne" in zrodla.raport([w])
    assert zrodla.main(["--spis", str(p), "sprawdz", "lemo"]) == 1


def test_przejrzane_i_status_zmieniaja_tylko_jedno_pole(upstream, tmp_path, capsys):
    repo, a = upstream
    b = commit(repo, {"z.md": "z"}, "z")
    p = spis(tmp_path, f"file://{repo}", a)
    przed = p.read_text(encoding="utf-8")
    assert zrodla.main(["--spis", str(p), "przejrzane", "lemo"]) == 0      # bez SHA: obecny commit repo
    assert zrodla.main(["--spis", str(p), "status", "lemo", "do-wdrozenia"]) == 0
    po = p.read_text(encoding="utf-8")
    assert po == przed.replace(f"przejrzane: {a}\n  inne", f"przejrzane: {b}\n  inne", 1).replace(
        "status: uzywane   # notatka", "status: do-wdrozenia   # notatka")
    assert b"\r\n" not in p.read_bytes()                                 # spis w repo z LF także po zapisie na Windows
    assert zrodla.main(["--spis", str(p), "przejrzane", "lemo", "abc1234"]) == 1
    assert zrodla.main(["--spis", str(p), "przejrzane", "brak"]) == 1
    assert "pełny SHA" in capsys.readouterr().err


def _zip(pliki: dict[str, bytes], dowiazanie: bool = False) -> bytes:
    import io
    import stat
    import zipfile
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as zf:
        zf.writestr("platform-tools/", "")                               # wpis katalogu
        for rel, dane in pliki.items():
            zf.writestr(f"platform-tools/{rel}", dane)
        if dowiazanie:                                                    # dowiązanie z zipa macOS/Linuksa
            info = zipfile.ZipInfo("platform-tools/lib64/libc++.so.1")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, "libc++.so")
    return bufor.getvalue()


def test_paczka_zip_bez_gita(tmp_path):
    """Źródło bez repo git jako zip (platform-tools od Google): pliki bez katalogu głównego archiwum, bez wpisów
    katalogów i dowiązań; nowa wersja paczki pokazuje zmiany względem kopii, także pliku NOTICE (licencja)."""
    import hashlib
    sha = lambda b: hashlib.sha256(b).hexdigest()                        # noqa: E731
    stara = _zip({"adb": b"adb", "NOTICE.txt": b"n"}, dowiazanie=True)
    assert zrodla.pliki_paczki(stara) == {"adb": sha(b"adb"), "NOTICE.txt": sha(b"n")}
    kopia = tmp_path / "kopia"
    kopia.mkdir()
    (kopia / "adb").write_bytes(b"adb")
    (kopia / "NOTICE.txt").write_bytes(b"n")
    spec = {"paczka": "https://x/platform-tools-latest-windows.zip", "kopia": str(kopia), "status": "do-wdrozenia",
            "przejrzane": sha(stara)}
    assert zrodla.sprawdz_paczke("pt", spec, pobieranie=lambda url: stara)["zmiany"] is False
    nowa = _zip({"adb": b"adb 2", "NOTICE.txt": b"n 2", "fastboot": b"f"})
    w = zrodla.sprawdz_paczke("pt", spec, pobieranie=lambda url: nowa)
    assert w["zmiany"] and w["glowa"] == sha(nowa) and not w.get("blad")
    assert w["dodane"] == ["fastboot"] and w["zmienione"] == ["NOTICE.txt", "adb"] and w["licencja"] == ["NOTICE.txt"]
    assert "## pt (do-wdrozenia): nowa wersja paczki" in zrodla.raport([w])
    w = zrodla.sprawdz_paczke("pt", spec, pobieranie=lambda url: b"ani tar, ani zip")
    assert w["blad"].startswith("nie da się otworzyć paczki")


def test_spis_repo_jest_kompletny():
    report = validate.Report()
    validate.check_zrodla(report)
    assert report.errors == []
    spis = zrodla.wczytaj()
    assert spis["android-platform-tools"]["paczka"].endswith(".zip")       # platform-tools: paczka zip od Google


def test_walidacja_spisu(repo_copy):
    p = repo_copy / "vendor" / "zrodla.yaml"
    tekst = p.read_text(encoding="utf-8")
    tekst = tekst.replace("  anidoodle:\n    repo: https://github.com/alexgreensh/anidoodle\n    status: uzywane\n",
                          "  anidoodle:\n    repo: https://github.com/alexgreensh/anidoodle\n    status: nowe\n")
    tekst = tekst.replace("  htm:\n    repo: https://github.com/developit/htm", "  htm:\n    repo: https://example.com/htm")
    tekst += ("  model-bez-atrybucji:\n    repo: https://huggingface.co/ktos/model\n    status: uzywane\n"
              f"    przejrzane: {'a' * 40}\n"                           # model z Hugging Face: dozwolony, ale z atrybucją
              "  zla-galaz:\n    repo: https://github.com/ktos/zla\n    galaz: \"refs heads\"\n    status: czeka\n"
              f"    przejrzane: {'b' * 40}\n")
    p.write_text(tekst, encoding="utf-8")
    report = validate.Report()
    validate.check_zrodla(report)
    bledy = "\n".join(report.errors)
    assert "anidoodle: status 'nowe'" in bledy
    assert "htm: repo musi być adresem https://github.com/" in bledy
    assert "github.com/developit/htm (docs/SOURCES.md) nie ma w vendor/zrodla.yaml" in bledy
    assert "model-bez-atrybucji: status uzywane, a repo nie ma w docs/SOURCES.md" in bledy
    assert "zla-galaz: galaz to nazwa gałęzi wydań" in bledy
    assert "matcha-tts-pl-v2" not in bledy                                       # model z atrybucją w SOURCES.md


def test_galaz_wydan_zamiast_domyslnej(upstream, tmp_path):
    """Źródło przypięte do wydania z gałęzi wydań (np. valkey 8.1): nowości z tej gałęzi, nie z domyślnej."""
    repo, a = upstream
    sh(repo, "branch", "8.1")
    commit(repo, {"nowa-wersja.md": "9"}, "main: następna wersja")
    sh(repo, "checkout", "-q", "8.1")
    b = commit(repo, {"poprawka.md": "p"}, "8.1: poprawka bezpieczeństwa")
    sh(repo, "checkout", "-q", "main")
    p = spis(tmp_path, f"file://{repo}", a)
    p.write_text(p.read_text(encoding="utf-8").replace("    status: uzywane", "    galaz: \"8.1\"\n    status: uzywane", 1),
                 encoding="utf-8")
    w = zrodla.sprawdz(zrodla.wczytaj(p), ["lemo"])[0]
    assert w["galaz"] == "8.1" and w["glowa"] == b and not w["przepisana"]
    assert [c["tytul"] for c in w["commity"]] == ["8.1: poprawka bezpieczeństwa"]
    assert zrodla.main(["--spis", str(p), "przejrzane", "lemo"]) == 0
    assert f"przejrzane: {b}\n  inne" in p.read_text(encoding="utf-8")
    p.write_text(p.read_text(encoding="utf-8").replace('galaz: "8.1"', 'galaz: "9.9"'), encoding="utf-8")
    assert zrodla.sprawdz(zrodla.wczytaj(p), ["lemo"])[0]["blad"].startswith("niedostępne: repo bez gałęzi 9.9")
