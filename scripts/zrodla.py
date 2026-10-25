#!/usr/bin/env python3
"""Spis źródeł Jarva (vendor/zrodla.yaml): co nowego w repo, z których bierzemy kod, skille albo wzorce.

    python3 scripts/zrodla.py lista
    python3 scripts/zrodla.py sprawdz [nazwa…] [--json] [--pelny]
    python3 scripts/zrodla.py przejrzane <nazwa> [commit]
    python3 scripts/zrodla.py status <nazwa> <uzywane|do-wdrozenia|czeka|odlozone>

`sprawdz` pyta każde repo o obecny commit (git ls-remote, równolegle) i dla tych, które zmieniły się od
`przejrzane`, pobiera tylko historię od tamtej chwili (bez plików, same drzewa): liczba i tytuły commitów,
pliki dodane / zmienione / usunięte, nowe katalogi (do 2 poziomów), nowe i zmienione SKILL.md, zmiana pliku
licencji (⚠). Źródło z `galaz` (gałąź wydań, np. valkey 8.1) śledzimy na tej gałęzi zamiast domyślnej. Źródło
bez repo git (`paczka`: adres archiwum tar albo zip, np. iso-glow, platform-tools) ma w `przejrzane` SHA-256
paczki: inna suma = nowa wersja, a pliki paczki porównujemy z naszą kopią w repo (`kopia`, `nazwy`). Raport jest
po polsku w Markdownie (albo JSON); z niego rutyna pon/śr/pt robi propozycje dla właściciela. Skrypt niczego nie
wdraża: `przejrzane` i `status` zmieniają tylko spis, a wersja kopiowana do floty (`rev` w skills.lock.yaml, stałe
w narzędziach) zmienia się osobno, po zgodzie właściciela.
Kod wyjścia 0 także przy nowościach; 1 przy błędzie spisu, nieznanej nazwie albo niedostępnym repo.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

SPIS = fl.REPO_ROOT / "vendor" / "zrodla.yaml"
STATUSY = ("uzywane", "do-wdrozenia", "czeka", "odlozone")
SHA = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
PACZKA_MAX = 50 * 1024 * 1024
LICENCJA = re.compile(r"(LICEN[CS]E|COPYING|NOTICE)(\.[A-Za-z]+)?$", re.I)
# GCM_INTERACTIVE: Git dla Windows pyta o hasło okienkiem Git Credential Managera (repo prywatne albo usunięte)
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true", "GCM_INTERACTIVE": "never", "LC_ALL": "C"}
POKAZ_COMMITOW = 12
POKAZ_POZYCJI = 15


class BladSpisu(Exception):
    pass


def wczytaj(path: Path = SPIS) -> dict[str, dict]:
    data = fl.load_yaml(path) or {}
    zrodla = data.get("zrodla")
    if not isinstance(zrodla, dict) or not zrodla:
        raise BladSpisu(f"{path}: brak sekcji `zrodla`")
    for spec in zrodla.values():
        if isinstance(spec, dict) and spec.get("przejrzane") is not None:
            spec["przejrzane"] = str(spec["przejrzane"])
    return zrodla


def git(*args: str, cwd: Path | None = None, timeout: int = 300) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip()
                           else f"git {args[0]}: kod {p.returncode}")
    return p.stdout


def glowa(url: str, galaz: str = "") -> tuple[str, str]:
    """(gałąź, commit): gałąź ze spisu (`galaz`, np. gałąź wydań 8.1) albo domyślna z `git ls-remote --symref`."""
    if galaz:
        sha = git("ls-remote", url, f"refs/heads/{galaz}", timeout=60).split("\t", 1)[0]
        if not SHA.fullmatch(sha):
            raise RuntimeError(f"repo bez gałęzi {galaz}")
        return galaz, sha
    out = git("ls-remote", "--symref", url, "HEAD", timeout=60)
    galaz = sha = ""
    for line in out.splitlines():
        if line.startswith("ref: ") and line.endswith("\tHEAD"):
            galaz = line[5:-5].removeprefix("refs/heads/")
        elif line.endswith("\tHEAD"):
            sha = line.split("\t")[0]
    if not galaz or not SHA.fullmatch(sha):
        raise RuntimeError("repo bez gałęzi domyślnej")
    return galaz, sha


def _drzewo(repo: Path, sha: str) -> tuple[set[str], set[str], dict[str, str]]:
    """(katalogi do 2 poziomów, pliki SKILL.md, pliki licencji w korzeniu → id blobu) w commicie."""
    katalogi = {p for p in git("ls-tree", "-r", "-d", "--name-only", sha, cwd=repo).splitlines() if p.count("/") <= 1}
    skille = {p for p in git("ls-tree", "-r", "--name-only", sha, cwd=repo).splitlines()
              if p.rsplit("/", 1)[-1] == "SKILL.md"}
    licencje = {}
    for line in git("ls-tree", sha, cwd=repo).splitlines():
        meta, name = line.split("\t", 1)
        if LICENCJA.match(name):
            licencje[name] = meta.split()[2]
    return katalogi, skille, licencje


def nowosci(url: str, galaz: str, od: str, do: str, robocze: Path) -> dict:
    """Zmiany od commitu `od` do `do`: płytka kopia bez plików (same commity i drzewa) w katalogu roboczym."""
    repo = robocze
    git("init", "-q", "--bare", str(repo))
    git("remote", "add", "origin", url, cwd=repo)
    git("config", "remote.origin.promisor", "true", cwd=repo)
    git("config", "remote.origin.partialclonefilter", "blob:none", cwd=repo)
    wynik: dict = {"przepisana": False}
    try:
        git("fetch", "-q", "--no-tags", "--depth=1", "origin", od, cwd=repo)
    except RuntimeError:
        od = ""
    ref = f"refs/heads/{galaz}"
    if od:
        kiedy = dt.datetime.fromtimestamp(int(git("log", "-1", "--format=%ct", od, cwd=repo)), dt.timezone.utc)
        od_daty = (kiedy - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            git("fetch", "-q", "--no-tags", f"--shallow-since={od_daty}", "origin", f"+{ref}:{ref}", cwd=repo)
        except RuntimeError:
            git("fetch", "-q", "--no-tags", "--depth=200", "origin", f"+{ref}:{ref}", cwd=repo)
        if subprocess.run(["git", "merge-base", "--is-ancestor", od, ref], cwd=repo, env=GIT_ENV,
                          capture_output=True).returncode:
            wynik["przepisana"] = True
    else:
        git("fetch", "-q", "--no-tags", "--depth=50", "origin", f"+{ref}:{ref}", cwd=repo)
        wynik["przepisana"] = True
    zakres = [ref, "--not", od] if od and not wynik["przepisana"] else [ref, "-n", "50"]
    log = git("log", "--no-merges", "--format=%h%x09%cs%x09%s", *zakres, cwd=repo).splitlines()
    wynik["commity"] = [dict(zip(("sha", "data", "tytul"), line.split("\t", 2))) for line in log if line]
    if not od:
        return wynik
    zmiany: dict[str, list[str]] = {"A": [], "M": [], "D": []}
    for line in git("diff", "--no-renames", "--name-status", od, ref, cwd=repo).splitlines():
        kod, sciezka = line.split("\t", 1)
        zmiany.setdefault(kod[0], []).append(sciezka)
    k0, s0, l0 = _drzewo(repo, od)
    k1, s1, l1 = _drzewo(repo, ref)
    nowe = k1 - k0
    wynik.update(
        dodane=zmiany["A"], zmienione=zmiany["M"] + zmiany.get("T", []), usuniete=zmiany["D"],
        # nowy katalog w nowym katalogu nie jest osobną nowością
        nowe_katalogi=sorted(k for k in nowe if "/" not in k or k.rsplit("/", 1)[0] not in nowe),
        nowe_skille=sorted(s1 - s0),
        zmienione_skille=sorted(s for s in zmiany["M"] if s in s1 and s.rsplit("/", 1)[-1] == "SKILL.md"),
        licencja=sorted(n for n in set(l0) | set(l1) if l0.get(n) != l1.get(n)),
    )
    return wynik


def pobierz(url: str) -> bytes:
    import urllib.request
    with urllib.request.urlopen(url, timeout=60) as r:          # noqa: S310 (adres ze spisu, https)
        dane = r.read(PACZKA_MAX + 1)
    if len(dane) > PACZKA_MAX:
        raise RuntimeError(f"paczka większa niż {PACZKA_MAX // 2**20} MB")
    return dane


def _sha_strumienia(f) -> str:
    import hashlib
    h = hashlib.sha256()
    for kawalek in iter(lambda: f.read(1 << 20), b""):
        h.update(kawalek)
    return h.hexdigest()


def pliki_paczki(dane: bytes) -> dict[str, str]:
    """ścieżka (bez katalogu głównego archiwum) → SHA-256 pliku z archiwum tar (.tar.gz, .tgz, .tar.xz, .tar.bz2,
    .tar) albo zip (np. platform-tools od Google); same pliki, bez katalogów i dowiązań; nic nie rozpakowujemy na
    dysk."""
    import io
    import stat
    import tarfile
    import zipfile
    out = {}

    def dodaj(nazwa: str, otworz) -> None:
        czesci = nazwa.replace("\\", "/").lstrip("./").split("/", 1)
        if len(czesci) == 2 and czesci[1]:
            with otworz() as f:
                out[czesci[1]] = _sha_strumienia(f)

    bufor = io.BytesIO(dane)
    if zipfile.is_zipfile(bufor):
        with zipfile.ZipFile(bufor) as zf:
            for info in zf.infolist():
                if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                    continue
                dodaj(info.filename, lambda i=info: zf.open(i))
        return out
    bufor.seek(0)
    with tarfile.open(fileobj=bufor, mode="r:*") as tar:
        for m in tar.getmembers():
            if m.isfile():
                dodaj(m.name, lambda m=m: tar.extractfile(m))
    return out


def pliki_kopii(kopia: Path, nazwy: dict[str, str]) -> dict[str, str]:
    """Nasza kopia w repo w układzie paczki (przemianowane pliki pod nazwą z paczki) → SHA-256."""
    import hashlib
    wstecz = {v: k for k, v in nazwy.items()}
    return {wstecz.get(p.relative_to(kopia).as_posix(), p.relative_to(kopia).as_posix()):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(kopia.rglob("*")) if p.is_file()}


def sprawdz_paczke(nazwa: str, spec: dict, pobieranie=pobierz) -> dict:
    import hashlib
    url = str(spec.get("paczka", ""))
    w = {"nazwa": nazwa, "repo": url, "paczka": True, "status": spec.get("status"), "przejrzane": spec.get("przejrzane"),
         "pin": None}
    try:
        dane = pobieranie(url)
    except Exception as e:  # noqa: BLE001 (sieć, HTTP, za duża paczka: raport, nie wyjątek)
        w["blad"] = f"niedostępne: {e}"
        return w
    w["glowa"] = hashlib.sha256(dane).hexdigest()
    w["zmiany"] = w["glowa"] != w["przejrzane"]
    if not w["zmiany"]:
        return w
    try:
        nowe = pliki_paczki(dane)
    except Exception as e:  # noqa: BLE001
        w["blad"] = f"nie da się otworzyć paczki: {e}"
        return w
    w["commity"] = []
    if spec.get("kopia"):
        stare = pliki_kopii(fl.REPO_ROOT / str(spec["kopia"]), dict(spec.get("nazwy") or {}))
        w.update(dodane=sorted(set(nowe) - set(stare)), usuniete=sorted(set(stare) - set(nowe)),
                 zmienione=sorted(p for p in set(nowe) & set(stare) if nowe[p] != stare[p]))
        w["licencja"] = sorted(p for p in w["dodane"] + w["zmienione"] + w["usuniete"] if LICENCJA.match(p.rsplit("/", 1)[-1]))
        w["zmienione_skille"] = [p for p in w["zmienione"] if p.rsplit("/", 1)[-1] == "SKILL.md"]
    return w


def sprawdz_jedno(nazwa: str, spec: dict, piny: dict[str, str], robocze: Path) -> dict:
    if spec.get("paczka"):
        return sprawdz_paczke(nazwa, spec)
    url = str(spec.get("repo", ""))
    w = {"nazwa": nazwa, "repo": url, "status": spec.get("status"), "przejrzane": spec.get("przejrzane"),
         "pin": piny.get(url.lower().removesuffix(".git"))}
    try:
        w["galaz"], w["glowa"] = glowa(url, str(spec.get("galaz") or ""))
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        w["blad"] = f"niedostępne: {e}"
        return w
    w["zmiany"] = w["glowa"] != w["przejrzane"]
    if w["zmiany"]:
        try:
            w.update(nowosci(url, w["galaz"], str(w["przejrzane"]), w["glowa"], robocze / f"{nazwa}.git"))
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            w["blad"] = f"nie udało się pobrać historii: {e}"
    return w


def piny_z_locka() -> dict[str, str]:
    """repo → rev z skills.lock.yaml (wersja kopiowana do floty)."""
    out = {}
    for spec in (fl.load_lock().get("sources") or {}).values():
        if spec.get("type") == "git" and spec.get("repo"):
            out[str(spec["repo"]).lower().removesuffix(".git")] = str(spec.get("rev", ""))
    return out


def sprawdz(zrodla: dict[str, dict], nazwy: list[str] | None = None, watki: int = 8) -> list[dict]:
    wybrane = {n: zrodla[n] for n in (nazwy or zrodla)}
    piny = piny_z_locka()
    with tempfile.TemporaryDirectory(prefix="jarvo-zrodla-") as tmp, cf.ThreadPoolExecutor(watki) as pool:
        prace = {n: pool.submit(sprawdz_jedno, n, s, piny, Path(tmp)) for n, s in wybrane.items()}
        return [prace[n].result() for n in wybrane]


def _krotko(sha: str | None) -> str:
    return (sha or "")[:7]


def _commity(n: int) -> str:
    if n == 1:
        return "1 commit"
    return f"{n} commity" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else f"{n} commitów"


def _lista(tytul: str, pozycje: list[str], pelny: bool) -> list[str]:
    if not pozycje:
        return []
    widac = pozycje if pelny else pozycje[:POKAZ_POZYCJI]
    reszta = len(pozycje) - len(widac)
    return [f"- {tytul}: " + ", ".join(f"`{p}`" for p in widac) + (f" i {reszta} więcej" if reszta else "")]


def raport(wyniki: list[dict], pelny: bool = False) -> str:
    zmienione = [w for w in wyniki if w.get("zmiany") and not w.get("blad")]
    bledy = [w for w in wyniki if w.get("blad")]
    pelne = [w for w in zmienione if w["status"] != "odlozone"]
    skrot = [w for w in zmienione if w["status"] == "odlozone"]
    dzis = dt.date.today().isoformat()
    out = [f"# Źródła Jarva: nowości ({dzis})", "",
           f"Sprawdzone: {len(wyniki)} · bez zmian: {len(wyniki) - len(zmienione) - len(bledy)} · "
           f"ze zmianami: {len(zmienione)} · niedostępne: {len(bledy)}", ""]
    if not zmienione and not bledy:
        out.append("Nic nowego od ostatniego przeglądu.")
    for w in pelne:
        ile = "ostatnie commity" if w.get("przepisana") else _commity(len(w.get("commity", [])))
        if w.get("paczka"):
            ile = "nowa wersja paczki"
        out.append(f"## {w['nazwa']} ({w['status']}): {ile} od `{_krotko(w['przejrzane'])}`")
        out.append("")
        if w["repo"].startswith("https://github.com/"):
            out.append(f"{w['repo']}/compare/{_krotko(w['przejrzane'])}...{_krotko(w['glowa'])}")
            out.append("")
        if w.get("przepisana"):
            out.append("- ⚠ przejrzanego commitu nie ma już w historii gałęzi (historia przepisana): przejrzyj od nowa")
        if w.get("pin"):
            out.append(f"- we flocie: `{_krotko(w['pin'])}` (skills.lock.yaml)"
                       + (", to samo co przejrzane" if w["pin"] == w["przejrzane"] else ""))
        if w.get("licencja"):
            out.append("- ⚠ zmiana licencji: " + ", ".join(f"`{p}`" for p in w["licencja"])
                       + " (sprawdź, czy nadal wolno nam z tego korzystać)")
        out += _lista("nowe katalogi", w.get("nowe_katalogi", []), pelny)
        out += _lista("nowe skille", w.get("nowe_skille", []), pelny)
        out += _lista("zmienione skille", w.get("zmienione_skille", []), pelny)
        if w.get("paczka"):
            out.append(f"- paczka {w['repo']}: SHA-256 `{_krotko(w['glowa'])}…` (przejrzana `{_krotko(w['przejrzane'])}…`)")
            out += _lista("nowe pliki względem naszej kopii", w.get("dodane", []), pelny)
            out += _lista("zmienione pliki", w.get("zmienione", []), pelny)
            out += _lista("pliki, których już nie ma", w.get("usuniete", []), pelny)
        elif "dodane" in w:
            out.append(f"- pliki: {len(w['dodane'])} nowych, {len(w['zmienione'])} zmienionych, "
                       f"{len(w['usuniete'])} usuniętych")
        commity = w.get("commity", [])
        widac = commity if pelny else commity[:POKAZ_COMMITOW]
        if widac:
            out.append("- commity:")
            out += [f"  - `{c['sha']}` {c['data']} {c['tytul']}" for c in widac]
            if len(commity) > len(widac):
                out.append(f"  - … i {len(commity) - len(widac)} starszych")
        out.append("")
    if skrot:
        out += ["## Odłożone (tylko skrót)", ""]
        out += [f"- {w['nazwa']}: {_commity(len(w.get('commity', [])))} ({w['repo']})" for w in skrot]
        out.append("")
    if bledy:
        out += ["## Niedostępne", ""]
        out += [f"- {w['nazwa']} ({w['repo']}): {w['blad']}" for w in bledy]
        out.append("")
    if zmienione:
        out += ["Po przeglądzie: `python3 scripts/zrodla.py przejrzane <nazwa>` (zapisuje obecny commit jako "
                "przejrzany). Wdrożenie czegokolwiek tylko po zgodzie właściciela."]
    return "\n".join(out).rstrip() + "\n"


def ustaw(path: Path, nazwa: str, klucz: str, wartosc: str) -> None:
    """Zmienia jedno pole wpisu w spisie w miejscu (komentarze i kolejność zostają)."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next((i for i, l in enumerate(lines) if l.rstrip("\n") == f"  {nazwa}:"), None)
    if start is None:
        raise BladSpisu(f"nie ma źródła {nazwa!r} w {path.name}")
    for i in range(start + 1, len(lines)):
        if not lines[i].startswith("    "):
            break
        if lines[i].startswith(f"    {klucz}:"):
            reszta = re.sub(r"^\s*[^#\s]+", "", lines[i].split(":", 1)[1], count=1)
            lines[i] = f"    {klucz}: {wartosc}{reszta if reszta.strip() else chr(10)}"
            path.write_text("".join(lines), encoding="utf-8", newline="\n")   # spis w repo zostaje z LF
            return
    raise BladSpisu(f"{nazwa}: brak pola {klucz}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spis", type=Path, default=SPIS, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lista", help="wszystkie źródła ze statusem")
    p = sub.add_parser("sprawdz", help="nowości względem przejrzanych commitów")
    p.add_argument("nazwy", nargs="*")
    p.add_argument("--json", action="store_true")
    p.add_argument("--pelny", action="store_true", help="wszystkie commity i ścieżki, bez skracania")
    p = sub.add_parser("przejrzane", help="zapisz przejrzany commit albo SHA-256 paczki (domyślnie obecny)")
    p.add_argument("nazwa")
    p.add_argument("commit", nargs="?")
    p = sub.add_parser("status", help="zmień status źródła")
    p.add_argument("nazwa")
    p.add_argument("status", choices=STATUSY)
    a = ap.parse_args(argv)
    try:
        zrodla = wczytaj(a.spis)
        if a.cmd == "lista":
            for n, s in zrodla.items():
                print(f"{n:32} {s.get('status', ''):13} {_krotko(s.get('przejrzane'))}  {s.get('repo') or s.get('paczka')}")
            return 0
        if a.cmd == "sprawdz":
            nieznane = [n for n in a.nazwy if n not in zrodla]
            if nieznane:
                raise BladSpisu("nieznane źródła: " + ", ".join(nieznane))
            wyniki = sprawdz(zrodla, a.nazwy or None)
            print(json.dumps(wyniki, ensure_ascii=False, indent=2) if a.json else raport(wyniki, a.pelny), end="")
            if a.json:
                print()
            return 1 if any(w.get("blad") for w in wyniki) else 0
        if a.nazwa not in zrodla:
            raise BladSpisu(f"nie ma źródła {a.nazwa!r} w {a.spis.name}")
        if a.cmd == "status":
            ustaw(a.spis, a.nazwa, "status", a.status)
            print(f"{a.nazwa}: status {a.status}")
            return 0
        if zrodla[a.nazwa].get("paczka"):
            import hashlib
            sha = a.commit or hashlib.sha256(pobierz(str(zrodla[a.nazwa]["paczka"]))).hexdigest()
            if not SHA256.fullmatch(sha):
                raise BladSpisu("podaj SHA-256 paczki (64 znaki)")
        else:
            sha = a.commit or glowa(str(zrodla[a.nazwa]["repo"]), str(zrodla[a.nazwa].get("galaz") or ""))[1]
            if not SHA.fullmatch(sha):
                raise BladSpisu("podaj pełny SHA commitu (40 znaków)")
        ustaw(a.spis, a.nazwa, "przejrzane", sha)
        print(f"{a.nazwa}: przejrzane do {_krotko(sha)}")
        return 0
    except (BladSpisu, RuntimeError) as e:
        print(f"zrodla: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
