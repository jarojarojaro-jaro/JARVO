#!/usr/bin/env python3
"""Wgrywanie stron właściciela na hosting (SEOHost) przez SSH, tylko za zgodą przypiętą do odcisku (skill `wgrywanie-stron`).

Każda strona to repo `jarojarojaro-jaro/<domena>`, którego korzeń to dokładnie `public_html` serwera; gałąź `main` = strona
na żywo. Metadane repo (`.git/`, `.github/`, `.gitignore`, `.strona.json`) nigdy nie trafiają na serwer. Pliki pasujące
do `chronione` z `.strona.json` (np. `api/config.php`, `cgi-bin/`) narzędzie nigdy nie wysyła i nigdy nie usuwa; śledzony
plik pasujący do `chronione` jest pomijany z ostrzeżeniem. Śledzony plik pasujący do `.gitignore` strony (sekret dodany
na siłę) = odmowa.

Zasady hostingu: jedno połączenie SSH na przebieg (ControlMaster, przez nie każde ssh i rsync), jedna próba logowania
(nieudane logowania banują IP dla wszystkich stron), jedno wgrywanie naraz w całej flocie (blokada w katalogu stanu),
sprawdzanie sumami sha256 przez to samo połączenie, nigdy seriami zapytań HTTP.

    wgraj.py sprawdz <repo> [--wersja REV]           # lokalnie: zbiór plików, odcisk (hash drzewa REV)
    wgraj.py plan <repo> [--wersja REV]              # + jedno połączenie: co dodać, zmienić, usunąć
    wgraj.py wgraj <repo> --odcisk HASH [--wersja REV]
    wgraj.py cofnij <repo> --do TAG --odcisk HASH    # nowy commit na main z drzewem TAG i wgranie go
    wgraj.py kopie <repo>                            # kopie strony na serwerze
    wgraj.py z-buildu <repo> --build DIR             # podmiana wpisów `z_buildu` wynikiem builda
    wgraj.py podglad <repo> [--wersja REV | --robocze]

Kody wyjścia: 0 dobrze, 1 odmowa albo błąd, 3 weryfikacja sum nie zgadza się (strona do cofnięcia).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sciezki  # noqa: E402  (katalogi z HERMES_HOME, nie z /opt)

HOST_DOMYSLNY = "seohost"
METADANE = ("/.git", "/.github/", "/.gitignore", "/.strona.json")
ROZSZERZENIA_TEKSTU = (".html", ".js", ".json", ".txt", ".xml")
KLUCZE = {"domena": str, "katalog_na_serwerze": str, "zrodlo": str, "chronione": list, "kopie_na_serwerze": int,
          "z_buildu": list, "zakazane_sciezki": list, "zakazane_wzorce": list, "wymagane_teksty": dict}
BEZPIECZNA_SCIEZKA = re.compile(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*")
DOMENA = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+")
KOPIA = re.compile(r"\d{8}-\d{6}\.tar\.gz")
POKAZ_MAX = 100
KOD_WERYFIKACJI = 3


class Odmowa(Exception):
    """Narzędzie odmawia albo przerywa: komunikat po polsku dla Jarva i właściciela."""


def _info(tekst: str) -> None:
    print(tekst, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- wzorce (rsync i gitignore)

def _wzorzec_re(wz: str) -> str:
    out, i = [], 0
    while i < len(wz):
        c = wz[i]
        if c == "*":
            if wz[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            start = i + 2 if wz[i + 1:i + 2] in ("!", "^") else i + 1
            j = wz.find("]", start + 1 if wz[start:start + 1] == "]" else start)
            if j < 0:
                out.append(re.escape(c))
            else:
                body = wz[i + 1:j]
                if body[:1] in ("!", "^"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = j + 1
                continue
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


class Wzorzec:
    """Wzorzec ścieżki względem public_html. Styl rsync (`chronione`, reguły `--filter`): `/` na początku kotwiczy w korzeniu,
    `/` w środku albo `**` = dopasowanie do końcówki ścieżki od granicy katalogu, bez `/` = do nazwy na każdym poziomie,
    `/` na końcu = tylko katalog. Styl gitignore różni się jednym: `/` w środku kotwiczy w korzeniu. Wykluczony katalog
    obejmuje całą zawartość (tak samo działa rsync i git)."""

    def __init__(self, tekst: str, gitignore: bool = False):
        self.tekst = tekst
        self.katalog = tekst.endswith("/")
        p = tekst.rstrip("/")
        zakotwiczony = p.startswith("/") or (gitignore and "/" in p)
        p = p.lstrip("/")
        self.pelna = zakotwiczony or "/" in p or "**" in p
        rx = _wzorzec_re(p)
        self.re = re.compile(rx + r"\Z" if zakotwiczony or not self.pelna else r"(?:.*/)?" + rx + r"\Z", re.S)

    def _pasuje(self, sciezka: str, katalog: bool) -> bool:
        if self.katalog and not katalog:
            return False
        return self.re.match(sciezka if self.pelna else sciezka.rsplit("/", 1)[-1]) is not None

    def pasuje(self, sciezka: str) -> bool:
        czesci = sciezka.split("/")
        return any(self._pasuje("/".join(czesci[:k]), True) for k in range(1, len(czesci))) or self._pasuje(sciezka, False)


def _pasuje(wzorce: list[Wzorzec], sciezka: str) -> bool:
    return any(w.pasuje(sciezka) for w in wzorce)


WZ_METADANE = [Wzorzec(w) for w in METADANE]


def wzorce_gitignore(tekst: str) -> list[Wzorzec]:
    """Proste wzorce `.gitignore` (nazwy, `*`, ścieżki z `/`); komentarze, puste linie i negacje pomijane."""
    wynik = []
    for linia in tekst.splitlines():
        linia = linia.strip()
        if linia and not linia.startswith(("#", "!")):
            wynik.append(Wzorzec(linia, gitignore=True))
    return wynik


# ---------------------------------------------------------------- konfiguracja strony

def wczytaj_konfiguracje(tekst: str) -> dict:
    try:
        k = json.loads(tekst)
    except ValueError as exc:
        raise Odmowa(f".strona.json nie jest poprawnym JSON: {exc}") from None
    if not isinstance(k, dict):
        raise Odmowa(".strona.json: oczekiwany obiekt JSON")
    bledy = [f"nieznany klucz {x!r}" for x in k if x not in KLUCZE]
    for klucz, typ in KLUCZE.items():
        if klucz not in k:
            bledy.append(f"brak klucza {klucz!r}")
        elif not isinstance(k[klucz], typ) or isinstance(k[klucz], bool):
            bledy.append(f"{klucz!r} ma zły typ (oczekiwany {typ.__name__})")
    if bledy:
        raise Odmowa(".strona.json: " + "; ".join(bledy))
    if not DOMENA.fullmatch(k["domena"]):
        bledy.append(f"domena {k['domena']!r} niepoprawna")
    kat = k["katalog_na_serwerze"]
    if not BEZPIECZNA_SCIEZKA.fullmatch(kat) or any(c in (".", "..") for c in kat.split("/")):
        bledy.append(f"katalog_na_serwerze {kat!r}: tylko ścieżka względem katalogu domowego, bez „..” i znaków specjalnych")
    if k["kopie_na_serwerze"] < 1:
        bledy.append("kopie_na_serwerze musi być ≥ 1")
    for w in k["chronione"]:
        if not isinstance(w, str) or not w.strip("/") or w != w.strip() or w.startswith("!") or "\n" in w:
            bledy.append(f"chronione: zły wzorzec {w!r}")
    for w in k["z_buildu"]:
        if not isinstance(w, str) or not BEZPIECZNA_SCIEZKA.fullmatch(w) or "/" in w or w in (".", "..") \
                or _pasuje(WZ_METADANE, w):
            bledy.append(f"z_buildu: {w!r} musi być nazwą wpisu w korzeniu strony (nie metadaną)")
    for w in k["zakazane_sciezki"]:
        if not isinstance(w, str) or not w.strip("/"):
            bledy.append(f"zakazane_sciezki: zła ścieżka {w!r}")
    for w in k["zakazane_wzorce"]:
        try:
            re.compile(w)
        except (re.error, TypeError) as exc:
            bledy.append(f"zakazane_wzorce: {w!r} nie jest wyrażeniem regularnym ({exc})")
    for plik, tekst_ in k["wymagane_teksty"].items():
        if not isinstance(tekst_, str) or not tekst_:
            bledy.append(f"wymagane_teksty[{plik!r}]: oczekiwany niepusty tekst")
    if bledy:
        raise Odmowa(".strona.json: " + "; ".join(bledy))
    return k


# ---------------------------------------------------------------- git

def git(repo: Path, *args: str, wejscie: bytes | None = None, tekst: bool = True, sprawdz: bool = True):
    r = subprocess.run(["git", "-C", str(repo), *args], input=wejscie, capture_output=True)
    if sprawdz and r.returncode:
        raise Odmowa(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout.decode("utf-8", "replace") if tekst else r


def _rev(repo: Path, rev: str) -> str:
    r = git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", tekst=False, sprawdz=False)
    if r.returncode:
        raise Odmowa(f"Nie ma wersji {rev!r} w repo {repo}")
    return r.stdout.decode().strip()


def odcisk_wersji(repo: Path, rev: str) -> str:
    return git(repo, "rev-parse", f"{rev}^{{tree}}").strip()


class Bloby:
    """Zawartość obiektów git jednym procesem `git cat-file --batch`."""

    def __init__(self, repo: Path):
        self.p = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE)

    def czytaj(self, sha: str) -> bytes:
        self.p.stdin.write(sha.encode() + b"\n")
        self.p.stdin.flush()
        naglowek = self.p.stdout.readline().split()
        if len(naglowek) != 3:
            raise Odmowa(f"git cat-file: brak obiektu {sha}")
        dane = self.p.stdout.read(int(naglowek[2]))
        self.p.stdout.read(1)
        return dane

    def zamknij(self) -> None:
        self.p.stdin.close()
        self.p.wait()


def pliki_wersji(repo: Path, rev: str) -> dict[str, tuple[str, str, int]]:
    """{ścieżka: (tryb, sha obiektu, rozmiar)} wszystkich plików śledzonych w REV."""
    wynik = {}
    for wpis in git(repo, "ls-tree", "-r", "-z", "--long", "--full-tree", rev).split("\0"):
        if not wpis:
            continue
        meta, sciezka = wpis.split("\t", 1)
        tryb, typ, sha, rozmiar = meta.split()
        wynik[sciezka] = (tryb, sha if typ == "blob" else typ, int(rozmiar) if rozmiar != "-" else 0)
    return wynik


# ---------------------------------------------------------------- sprawdz (lokalnie)

def sprawdz(repo: Path, rev: str = "HEAD", czyste: bool = True) -> dict:
    """Zbiór plików do wgrania z REV i wszystkie odmowy. Zwraca słownik z `pliki` {ścieżka: (sha256, rozmiar, sha git)}."""
    repo = Path(repo).resolve()
    if not (repo / ".git").exists():
        raise Odmowa(f"{repo} nie jest repo git strony")
    if czyste:
        brud = git(repo, "status", "--porcelain").strip()
        if brud:
            raise Odmowa("Repo ma niezatwierdzone zmiany; najpierw commit albo przywrócenie:\n" + brud)
    commit = _rev(repo, rev)
    drzewo = pliki_wersji(repo, commit)
    if ".strona.json" not in drzewo:
        raise Odmowa(f"Brak .strona.json w wersji {rev}")
    bloby = Bloby(repo)
    try:
        konf = wczytaj_konfiguracje(bloby.czytaj(drzewo[".strona.json"][1]).decode("utf-8", "replace"))
        sekrety = wzorce_gitignore(bloby.czytaj(drzewo[".gitignore"][1]).decode("utf-8", "replace")) \
            if ".gitignore" in drzewo else []
        chronione = [Wzorzec(w) for w in konf["chronione"]]
        bledy, pominiete, pliki = [], [], {}
        for sciezka, (tryb, sha, rozmiar) in sorted(drzewo.items()):
            if _pasuje(WZ_METADANE, sciezka):
                continue
            if _pasuje(sekrety, sciezka):
                bledy.append(f"śledzony sekret {sciezka} (pasuje do .gitignore): usuń go z repo "
                             f"(`git rm --cached {shlex.quote(sciezka)}`) i zmień ten sekret")
                continue
            if _pasuje(chronione, sciezka):
                pominiete.append(sciezka)
                continue
            if tryb == "120000":
                bledy.append(f"{sciezka}: dowiązanie symboliczne, nie wgrywamy dowiązań")
                continue
            if tryb == "160000" or sha == "commit":
                bledy.append(f"{sciezka}: submoduł, nie wgrywamy submodułów")
                continue
            for pref in konf["zakazane_sciezki"]:
                if sciezka.startswith(pref.lstrip("/")):
                    bledy.append(f"{sciezka}: zakazana ścieżka ({pref})")
            dane = bloby.czytaj(sha)
            if sciezka.lower().endswith(ROZSZERZENIA_TEKSTU) and konf["zakazane_wzorce"]:
                tekst = dane.decode("utf-8", "replace")
                for wz in konf["zakazane_wzorce"]:
                    m = re.search(wz, tekst)
                    if m:
                        linia = tekst.count("\n", 0, m.start()) + 1
                        bledy.append(f"{sciezka}:{linia}: zakazany wzorzec {wz!r} ({m.group(0)[:80]!r})")
            pliki[sciezka] = (hashlib.sha256(dane).hexdigest(), rozmiar, sha)
            wym = konf["wymagane_teksty"].get(sciezka)
            if wym is not None and wym.encode("utf-8") not in dane:
                bledy.append(f"{sciezka}: brak wymaganego tekstu {wym!r}")
        for plik in konf["wymagane_teksty"]:
            if plik not in pliki:
                bledy.append(f"{plik}: wymagany plik nie jest w zbiorze do wgrania")
    finally:
        bloby.zamknij()
    if bledy:
        raise Odmowa(f"Wersja {rev} nie nadaje się do wgrania ({len(bledy)}):\n- " + "\n- ".join(bledy))
    return {"repo": repo, "konf": konf, "rev": commit, "odcisk": odcisk_wersji(repo, commit), "pliki": pliki,
            "pominiete_chronione": pominiete, "rozmiar": sum(p[1] for p in pliki.values())}


def eksportuj(repo: Path, stan: dict, cel: Path) -> None:
    """Zapis zbioru do wgrania z obiektów git (bez drzewa roboczego i bez atrybutów eksportu) do katalogu `cel`."""
    bloby = Bloby(repo)
    try:
        for sciezka, (_, _, sha) in stan["pliki"].items():
            plik = cel / sciezka
            plik.parent.mkdir(parents=True, exist_ok=True)
            plik.write_bytes(bloby.czytaj(sha))
    finally:
        bloby.zamknij()


# ---------------------------------------------------------------- połączenie z serwerem

class Polaczenie:
    """Strona serwera: `uruchom` wykonuje skrypt sh w katalogu domowym, `rsync_cel`/`rsync_opcje` wskazują cel rsync."""

    potrzebne = ("rsync",)

    def otworz(self) -> None: ...

    def zamknij(self) -> None: ...

    def uruchom(self, skrypt: str) -> subprocess.CompletedProcess:
        raise NotImplementedError

    def rsync_opcje(self) -> list[str]:
        return []

    def rsync_cel(self, katalog: str) -> str:
        raise NotImplementedError

    def opis(self) -> str:
        raise NotImplementedError


class PolaczenieSSH(Polaczenie):
    """Jedno połączenie OpenSSH (ControlMaster) na przebieg; jedna próba logowania, bez ponawiania. Polecenia przez
    gniazdo mają `ProxyCommand=false`, więc gdy połączenie główne padnie, ssh nie spróbuje zalogować się drugi raz."""

    potrzebne = ("ssh", "rsync")

    def __init__(self, host: str = HOST_DOMYSLNY):
        self.host = host
        self.katalog: str | None = None
        self.gniazdo: str | None = None

    def _klient(self) -> list[str]:
        return ["ssh", "-S", self.gniazdo, "-o", "ControlMaster=no", "-o", "ProxyCommand=false", "-o", "BatchMode=yes",
                "-o", "LogLevel=ERROR", "-T"]

    def otworz(self) -> None:
        self.katalog = tempfile.mkdtemp(prefix="jarvo-ssh-", dir="/tmp" if os.path.isdir("/tmp") else None)
        os.chmod(self.katalog, 0o700)
        self.gniazdo = os.path.join(self.katalog, "s")
        r = subprocess.run(["ssh", "-o", "ControlMaster=yes", "-o", f"ControlPath={self.gniazdo}",
                            "-o", "ControlPersist=no", "-o", "ConnectionAttempts=1", "-o", "ConnectTimeout=15",
                            "-o", "BatchMode=yes", "-o", "LogLevel=ERROR", "-fN", self.host],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=90)
        if r.returncode:
            shutil.rmtree(self.katalog, ignore_errors=True)
            self.katalog = self.gniazdo = None
            raise Odmowa(f"Nie udało się połączyć z {self.host} (jedna próba, bez ponawiania: kolejne nieudane logowania "
                         f"blokują IP dla wszystkich stron). Sprawdź klucz i ~/.ssh/config, zanim spróbujesz znowu. "
                         f"ssh: {r.stderr.strip() or f'kod {r.returncode}'}")

    def zamknij(self) -> None:
        if self.gniazdo:
            subprocess.run(["ssh", "-S", self.gniazdo, "-O", "exit", self.host], capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=30)
        if self.katalog:
            shutil.rmtree(self.katalog, ignore_errors=True)
        self.katalog = self.gniazdo = None

    def uruchom(self, skrypt: str) -> subprocess.CompletedProcess:
        if not self.gniazdo:
            raise Odmowa("Połączenie z serwerem nie jest otwarte")
        return subprocess.run([*self._klient(), self.host, "sh -s"], input=skrypt.encode(), capture_output=True)

    def rsync_opcje(self) -> list[str]:
        return ["-e", " ".join(shlex.quote(x) for x in self._klient())]

    def rsync_cel(self, katalog: str) -> str:
        return f"{self.host}:{katalog}/"

    def opis(self) -> str:
        return self.host


class PolaczenieLokalne(Polaczenie):
    """Serwer na tym komputerze: `dom` udaje katalog domowy konta hostingu (testy i próby bez sieci)."""

    def __init__(self, dom: Path):
        self.dom = Path(dom)

    def uruchom(self, skrypt: str) -> subprocess.CompletedProcess:
        return subprocess.run(["sh", "-s"], input=skrypt.encode(), capture_output=True, cwd=self.dom)

    def rsync_cel(self, katalog: str) -> str:
        return f"{self.dom / katalog}/"

    def opis(self) -> str:
        return f"lokalnie:{self.dom}"


def wymagane_programy(pol: Polaczenie) -> None:
    brak = [p for p in ("git", *pol.potrzebne) if not shutil.which(p)]
    if brak:
        raise Odmowa(f"Brak programów: {', '.join(brak)}. Wgrywanie stron potrzebuje git, ssh i rsync "
                     f"(na Windows ich nie ma: wgrywa Jarvo z serwera albo z Linuksa/macOS).")


@contextlib.contextmanager
def polaczenie(pol: Polaczenie):
    pol.otworz()
    try:
        yield pol
    finally:
        pol.zamknij()


SUMA = 'if command -v sha256sum >/dev/null 2>&1; then S="sha256sum --"; else S="shasum -a 256 --"; fi'


def _odescapuj(nazwa: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "\\": "\\", "r": "\r"}.get(m.group(1), m.group(1)), nazwa)


def lista_zdalna(pol: Polaczenie, katalog: str) -> dict[str, str]:
    """{ścieżka: sha256} każdego pliku pod katalogiem strony; dowiązania z sumą `->dowiazanie`."""
    skrypt = (f"set -e\n{SUMA}\ncd -- {shlex.quote(katalog)} 2>/dev/null || exit 7\n"
              "find . -type f -exec $S {} +\necho '@@DOWIAZANIA@@'\nfind . -type l -print\n")
    r = pol.uruchom(skrypt)
    if r.returncode == 7:
        raise Odmowa(f"Katalog {katalog} nie istnieje na serwerze ({pol.opis()}); sprawdź katalog_na_serwerze")
    if r.returncode:
        raise Odmowa(f"Lista plików na serwerze nie powiodła się: {r.stderr.decode('utf-8', 'replace').strip()}")
    wynik, linki = {}, False
    for linia in r.stdout.decode("utf-8", "surrogateescape").split("\n"):
        if not linia:
            continue
        if linia == "@@DOWIAZANIA@@":
            linki = True
            continue
        if linki:
            wynik[linia.removeprefix("./")] = "->dowiazanie"
            continue
        esc = linia.startswith("\\")
        suma, nazwa = (linia[1:] if esc else linia).split("  ", 1) if "  " in linia else (linia, "")
        nazwa = _odescapuj(nazwa) if esc else nazwa
        wynik[nazwa.removeprefix("./")] = suma
    return wynik


def porownaj(stan: dict, zdalne: dict[str, str]) -> dict:
    chronione = [Wzorzec(w) for w in stan["konf"]["chronione"]] + WZ_METADANE
    dodane = sorted(p for p in stan["pliki"] if p not in zdalne)
    zmienione = sorted(p for p, (s, _, _) in stan["pliki"].items() if p in zdalne and zdalne[p] != s)
    usuniete = sorted(p for p in zdalne if p not in stan["pliki"] and not _pasuje(chronione, p))
    return {"dodane": dodane, "zmienione": zmienione, "usuniete": usuniete,
            "bez_zmian": len(stan["pliki"]) - len(dodane) - len(zmienione)}


# ---------------------------------------------------------------- blokada floty

@contextlib.contextmanager
def blokada(czekaj: float):
    import fcntl
    katalog = _sciezki.stan()
    katalog.mkdir(parents=True, exist_ok=True)
    sciezka = katalog / "wgrywanie.lock"
    with open(sciezka, "a+") as f:
        koniec = time.monotonic() + czekaj
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= koniec:
                    raise Odmowa(f"Inne wgrywanie trwa (blokada {sciezka}); po {czekaj:.0f} s odmawiam. "
                                 f"Jedno wgrywanie naraz w całej flocie.") from None
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ---------------------------------------------------------------- polecenia

def _skrot(lista: list[str]) -> list[str]:
    return lista[:POKAZ_MAX] + ([f"… i {len(lista) - POKAZ_MAX} więcej"] if len(lista) > POKAZ_MAX else [])


def _ostrzez_chronione(stan: dict) -> None:
    if stan["pominiete_chronione"]:
        _info(f"Uwaga: {len(stan['pominiete_chronione'])} śledzonych plików pasuje do `chronione`; nie wysyłam ich "
              f"i nie porównuję: " + ", ".join(_skrot(stan["pominiete_chronione"])))


def _podsumowanie(stan: dict) -> dict:
    return {"domena": stan["konf"]["domena"], "katalog": stan["konf"]["katalog_na_serwerze"], "rev": stan["rev"],
            "odcisk": stan["odcisk"], "pliki": len(stan["pliki"]), "rozmiar": stan["rozmiar"],
            "pominiete_chronione": stan["pominiete_chronione"]}


def cmd_sprawdz(a, pol) -> dict:
    stan = sprawdz(Path(a.repo), a.wersja)
    _ostrzez_chronione(stan)
    return _podsumowanie(stan)


def cmd_plan(a, pol) -> dict:
    stan = sprawdz(Path(a.repo), a.wersja)
    _ostrzez_chronione(stan)
    wymagane_programy(pol)
    with polaczenie(pol):
        roznice = porownaj(stan, lista_zdalna(pol, stan["konf"]["katalog_na_serwerze"]))
    wersja = "" if a.wersja == "HEAD" else f" --wersja {shlex.quote(a.wersja)}"
    return {**_podsumowanie(stan), **roznice,
            "polecenie": f"wgraj.py wgraj {shlex.quote(str(stan['repo']))} --odcisk {stan['odcisk']}{wersja}"}


def _ostatni_tag(repo: Path, poza: str = "") -> str | None:
    for t in git(repo, "tag", "--list", "wgranie-*", "zywo-*", "--sort=-creatordate").split():
        if t != poza:
            return t
    return None


def _origin_main(repo: Path) -> str | None:
    git(repo, "fetch", "--quiet", "origin", "+refs/heads/main:refs/remotes/origin/main")
    r = git(repo, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main", tekst=False, sprawdz=False)
    return r.stdout.decode().strip() or None


def _przodek(repo: Path, a: str, b: str) -> bool:
    return git(repo, "merge-base", "--is-ancestor", a, b, tekst=False, sprawdz=False).returncode == 0


def _sprawdz_main(repo: Path, rev: str) -> str | None:
    main = _origin_main(repo)
    if main and not _przodek(repo, rev, main) and not _przodek(repo, main, rev):
        raise Odmowa(f"Wersja {rev[:12]} nie jest ani na main, ani jej przewinięciem (origin/main {main[:12]}). "
                     f"Najpierw dołącz zmiany z main do tej wersji; nie wgrywam wersji, której main nie może przyjąć.")
    return main


def _przewin_main(repo: Path, rev: str) -> str:
    main = _origin_main(repo)
    if main and _przodek(repo, rev, main):
        stan = "już na main"
    else:
        if main and not _przodek(repo, main, rev):
            raise Odmowa(f"origin/main ({main[:12]}) rozjechał się z wgraną wersją {rev[:12]}; nie przewijam main")
        git(repo, "push", "--quiet", "origin", f"{rev}:refs/heads/main")
        stan = "przewinięty"
    lokalny = git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/main", tekst=False, sprawdz=False)
    lokalny = lokalny.stdout.decode().strip()
    if lokalny and lokalny != rev and _przodek(repo, lokalny, rev):
        biezaca = git(repo, "symbolic-ref", "--quiet", "HEAD", tekst=False, sprawdz=False).stdout.decode().strip()
        if biezaca == "refs/heads/main":
            git(repo, "merge", "--quiet", "--ff-only", rev)
        else:
            git(repo, "update-ref", "refs/heads/main", rev, lokalny)
    return stan


def wdroz(repo: Path, rev: str, odcisk: str, pol: Polaczenie, czekaj: float) -> tuple[dict, int]:
    """Wgranie REV: blokada → sprawdz → połączenie → kopia → rsync → weryfikacja sum → tag i main. (raport, kod)."""
    start = time.monotonic()
    repo = Path(repo).resolve()
    commit = _rev(repo, rev)
    if odcisk_wersji(repo, commit) != odcisk:
        raise Odmowa(f"Odcisk {odcisk} nie jest odciskiem wersji {rev} ({odcisk_wersji(repo, commit)}). Zgoda "
                     f"właściciela dotyczy dokładnie planowanych plików: zrób nowy plan i zapytaj jeszcze raz.")
    wymagane_programy(pol)
    with blokada(czekaj):
        stan = sprawdz(repo, commit)
        _ostrzez_chronione(stan)
        konf = stan["konf"]
        _sprawdz_main(repo, commit)
        znacznik = time.strftime("%Y%m%d-%H%M%S")
        while git(repo, "tag", "--list", f"wgranie-{znacznik}").strip():    # dwa wgrania w tej samej sekundzie
            time.sleep(1)
            znacznik = time.strftime("%Y%m%d-%H%M%S")
        kopia = f"{znacznik}.tar.gz"
        kat, kopie_kat = konf["katalog_na_serwerze"], f"kopie-stron/{konf['domena']}"
        raport = {"domena": konf["domena"], "rev": commit, "odcisk": odcisk, "serwer": pol.opis(),
                  "kopia": f"~/{kopie_kat}/{kopia}"}
        with tempfile.TemporaryDirectory(prefix="jarvo-wgraj-") as tmp:
            eksport = Path(tmp) / "public_html"
            eksport.mkdir()
            eksportuj(repo, stan, eksport)
            with polaczenie(pol):
                przed = porownaj(stan, lista_zdalna(pol, kat))
                raport["liczby"] = {"pliki": len(stan["pliki"]), "dodane": len(przed["dodane"]),
                                    "zmienione": len(przed["zmienione"]), "usuniete": len(przed["usuniete"]),
                                    "bez_zmian": przed["bez_zmian"]}
                _info(f"Kopia na serwerze: {raport['kopia']}")
                r = pol.uruchom(_skrypt_kopii(kat, kopie_kat, kopia, konf["kopie_na_serwerze"]))
                if r.returncode:
                    raise Odmowa(f"Kopia strony na serwerze nie powiodła się; nic nie wgrałem. "
                                 f"{r.stderr.decode('utf-8', 'replace').strip()}")
                raport["usuniete_kopie"] = [x for x in r.stdout.decode().split() if KOPIA.fullmatch(x)]
                _info(f"Wgrywanie {len(stan['pliki'])} plików na {pol.opis()}:{kat}")
                filtry = [f"--filter=- {w}" for w in [*METADANE, *konf["chronione"]]]
                r = subprocess.run(["rsync", "-rlt", "--checksum", "--chmod=D755,F644", "--delete", *filtry,
                                    *pol.rsync_opcje(), f"{eksport}/", pol.rsync_cel(kat)],
                                   capture_output=True, text=True, stdin=subprocess.DEVNULL)
                raport["rsync_kod"] = r.returncode
                po = porownaj(stan, lista_zdalna(pol, kat))
        roznice = sorted(set(po["dodane"]) | set(po["zmienione"]))
        raport["czas_s"] = round(time.monotonic() - start, 1)
        if r.returncode or roznice or po["usuniete"]:
            tag = _ostatni_tag(repo)
            raport.update(wynik="blad", rsync_blad=r.stderr.strip()[-2000:], niezgodne=roznice, nadmiarowe=po["usuniete"],
                          cofnij=(f"wgraj.py cofnij {shlex.quote(str(repo))} --do {tag} --odcisk "
                                  f"{odcisk_wersji(repo, tag)}") if tag else None)
            _info(f"Weryfikacja nie przeszła: {len(roznice)} niezgodnych, {len(po['usuniete'])} nadmiarowych "
                  f"plików, rsync kod {r.returncode}. Nie taguję. Kopia sprzed wgrania: {raport['kopia']}.")
            if raport["cofnij"]:
                _info(f"Cofnięcie: {raport['cofnij']}")
            return raport, KOD_WERYFIKACJI
        tag = f"wgranie-{znacznik}"
        raport.update(wynik="ok", tag=tag)
        try:
            git(repo, "tag", tag, commit)
            git(repo, "push", "--quiet", "origin", f"refs/tags/{tag}")
            raport["main"] = _przewin_main(repo, commit)
        except Odmowa as exc:
            raport["blad_git"] = str(exc)
            _info(f"Strona wgrana i sprawdzona, ale git się nie domknął: {exc}")
            return raport, 1
        return raport, 0


def _skrypt_kopii(kat: str, kopie_kat: str, nazwa: str, zostaw: int) -> str:
    k, d, n = shlex.quote(kat), shlex.quote(kopie_kat), shlex.quote(nazwa)
    return (f"set -e\numask 077\n[ -d {k} ] || {{ echo 'brak katalogu {kat}' >&2; exit 7; }}\nmkdir -p {d}\n"
            f"tar -czf {d}/.{n}.tmp -C {k} .\nmv {d}/.{n}.tmp {d}/{n}\n"
            f"ls -1 {d} | grep -E '^[0-9]{{8}}-[0-9]{{6}}\\.tar\\.gz$' | sort -r | tail -n +{zostaw + 1} "
            f"| while read -r f; do rm -f -- {d}/\"$f\"; echo \"$f\"; done\n")


def _zapisz_dziennik(raport: dict) -> None:
    katalog = _sciezki.stan()
    katalog.mkdir(parents=True, exist_ok=True)
    with open(katalog / "wgrywanie.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"czas": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **raport}, ensure_ascii=False) + "\n")


def cmd_wgraj(a, pol) -> tuple[dict, int]:
    raport, kod = wdroz(Path(a.repo), a.wersja, a.odcisk, pol, a.czekaj)
    _zapisz_dziennik(raport)
    return raport, kod


def cmd_cofnij(a, pol) -> tuple[dict, int]:
    repo = Path(a.repo).resolve()
    tag = git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/{a.do}", tekst=False, sprawdz=False)
    if tag.returncode:
        raise Odmowa(f"Nie ma tagu {a.do!r}")
    drzewo = odcisk_wersji(repo, f"refs/tags/{a.do}")
    if drzewo != a.odcisk:
        raise Odmowa(f"Odcisk {a.odcisk} nie jest odciskiem {a.do} ({drzewo}); zgoda dotyczy dokładnie tych plików")
    brud = git(repo, "status", "--porcelain").strip()
    if brud:
        raise Odmowa("Repo ma niezatwierdzone zmiany; najpierw commit albo przywrócenie:\n" + brud)
    main = _origin_main(repo)
    if not main:
        raise Odmowa("Brak origin/main; cofnięcie tworzy commit na main")
    if odcisk_wersji(repo, main) == drzewo:
        rev = main
        _info(f"main ma już drzewo {a.do}; wgrywam main ponownie")
    else:
        rev = git(repo, "commit-tree", drzewo, "-p", main, "-m", f"Cofnięcie do {a.do}").strip()
        _info(f"Commit cofnięcia {rev[:12]} (drzewo {a.do}) na main")
    raport, kod = wdroz(repo, rev, a.odcisk, pol, a.czekaj)
    raport["cofniecie_do"] = a.do
    _zapisz_dziennik(raport)
    return raport, kod


def cmd_kopie(a, pol) -> dict:
    repo = Path(a.repo).resolve()
    konf = wczytaj_konfiguracje(git(repo, "show", "HEAD:.strona.json"))
    wymagane_programy(pol)
    d = shlex.quote(f"kopie-stron/{konf['domena']}")
    skrypt = f'for f in {d}/*.tar.gz; do [ -f "$f" ] && echo "$(wc -c <"$f") ${{f##*/}}"; done; true\n'
    with polaczenie(pol):
        r = pol.uruchom(skrypt)
    if r.returncode:
        raise Odmowa(f"Lista kopii nie powiodła się: {r.stderr.decode('utf-8', 'replace').strip()}")
    kopie = []
    for linia in r.stdout.decode().splitlines():
        rozmiar, nazwa = linia.split(None, 1)
        if KOPIA.fullmatch(nazwa):
            kopie.append({"nazwa": nazwa, "rozmiar": int(rozmiar), "sciezka": f"~/kopie-stron/{konf['domena']}/{nazwa}"})
    return {"domena": konf["domena"], "kopie": sorted(kopie, key=lambda k: k["nazwa"], reverse=True)}


def cmd_z_buildu(a, pol) -> dict:
    repo = Path(a.repo).resolve()
    konf = wczytaj_konfiguracje((repo / ".strona.json").read_text(encoding="utf-8"))
    if not konf["z_buildu"]:
        raise Odmowa("z_buildu jest puste: ta strona jest robiona ręcznie, nie podmieniam niczego")
    build = Path(a.build).resolve()
    if not build.is_dir():
        raise Odmowa(f"Nie ma katalogu builda {build}")
    podmienione, usuniete = [], []
    for wpis in konf["z_buildu"]:
        cel, zrodlo = repo / wpis, build / wpis
        if cel.is_dir() and not cel.is_symlink():
            shutil.rmtree(cel)
        elif cel.exists() or cel.is_symlink():
            cel.unlink()
        if zrodlo.is_dir():
            shutil.copytree(zrodlo, cel)
            podmienione.append(wpis)
        elif zrodlo.is_file():
            shutil.copy2(zrodlo, cel)
            podmienione.append(wpis)
        else:
            usuniete.append(wpis)
    pominiete = sorted(p.name for p in build.iterdir() if p.name not in konf["z_buildu"])
    status = git(repo, "status", "--short").splitlines()
    return {"domena": konf["domena"], "podmienione": podmienione, "usuniete": usuniete,
            "pominiete_z_buildu": pominiete, "status": status}


def cmd_podglad(a, pol) -> dict:
    repo = Path(a.repo).resolve()
    baza = Path(os.environ.get("JARVO_PODGLAD_DIR") or _sciezki.jarvo() / "workspaces" / "podglad")
    url = os.environ.get("JARVO_PODGLAD_URL") or "http://localhost:8090/"
    if a.robocze:
        konf = wczytaj_konfiguracje((repo / ".strona.json").read_text(encoding="utf-8"))
        chronione = [Wzorzec(w) for w in konf["chronione"]]
        sekrety = wzorce_gitignore((repo / ".gitignore").read_text(encoding="utf-8")) \
            if (repo / ".gitignore").is_file() else []
        pliki = [p for p in git(repo, "ls-files", "-z", "-co", "--exclude-standard").split("\0")
                 if p and (repo / p).is_file() and not _pasuje(WZ_METADANE + chronione + sekrety, p)]
        cel = baza / konf["domena"]
        if cel.exists():
            shutil.rmtree(cel)
        for p in pliki:
            (cel / p).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / p, cel / p)
        wynik = {"domena": konf["domena"], "wersja": "robocze", "pliki": len(pliki)}
    else:
        stan = sprawdz(repo, a.wersja, czyste=False)
        cel = baza / stan["konf"]["domena"]
        if cel.exists():
            shutil.rmtree(cel)
        cel.mkdir(parents=True)
        eksportuj(repo, stan, cel)
        wynik = {"domena": stan["konf"]["domena"], "wersja": stan["rev"], "odcisk": stan["odcisk"],
                 "pliki": len(stan["pliki"])}
    cel.mkdir(parents=True, exist_ok=True)
    link, tmp = baza / "aktualny", baza / ".aktualny.tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(cel.name, tmp)
    os.replace(tmp, link)
    return {**wynik, "katalog": str(cel), "url": url}


# ---------------------------------------------------------------- wyjście

def _tekst(polecenie: str, w: dict) -> str:
    if polecenie == "sprawdz":
        return (f"Strona {w['domena']} → {w['katalog']}\nWersja {w['rev']}\nOdcisk: {w['odcisk']}\n"
                f"Pliki do wgrania: {w['pliki']} ({w['rozmiar']} B)")
    if polecenie == "plan":
        linie = [f"Strona {w['domena']} → {w['katalog']}", f"Wersja {w['rev']}", f"Odcisk: {w['odcisk']}",
                 f"Pliki: {w['pliki']} ({w['rozmiar']} B); dodane {len(w['dodane'])}, zmienione {len(w['zmienione'])}, "
                 f"usunięte {len(w['usuniete'])}, bez zmian {w['bez_zmian']}"]
        for nazwa, znak in (("dodane", "+"), ("zmienione", "~"), ("usuniete", "-")):
            linie += [f"  {znak} {p}" for p in _skrot(w[nazwa])]
        linie.append(f"Po zgodzie właściciela na ten odcisk: {w['polecenie']}")
        return "\n".join(linie)
    if polecenie == "kopie":
        return "\n".join([f"Kopie {w['domena']} na serwerze: {len(w['kopie'])}"]
                         + [f"  {k['sciezka']} ({k['rozmiar']} B)" for k in w["kopie"]])
    if polecenie == "z-buildu":
        return "\n".join([f"Podmienione z builda: {', '.join(w['podmienione']) or '–'}",
                          f"Usunięte (brak w buildzie): {', '.join(w['usuniete']) or '–'}",
                          f"Pominięte wpisy builda (spoza z_buildu): {', '.join(w['pominiete_z_buildu']) or '–'}",
                          "git status --short:", *(f"  {s}" for s in w["status"])])
    if polecenie == "podglad":
        return f"Podgląd {w['domena']} ({w['wersja']}): {w['katalog']}\n{w['url']}"
    return json.dumps(w, ensure_ascii=False, indent=2)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wgraj.py", description="Wgrywanie stron na hosting przez SSH, za zgodą właściciela.")
    p.add_argument("--json", action="store_true", help="wynik jako JSON")
    p.add_argument("--host", default=os.environ.get("JARVO_WGRAJ_HOST") or HOST_DOMYSLNY,
                   help="alias hosta z ~/.ssh/config (domyślnie seohost)")
    sub = p.add_subparsers(dest="polecenie", required=True)
    for nazwa in ("sprawdz", "plan", "wgraj", "podglad"):
        s = sub.add_parser(nazwa)
        s.add_argument("repo")
        s.add_argument("--wersja", default="HEAD")
        if nazwa == "wgraj":
            s.add_argument("--odcisk", required=True)
            s.add_argument("--czekaj", type=float, default=600, help="ile sekund czekać na inne wgrywanie")
        if nazwa == "podglad":
            s.add_argument("--robocze", action="store_true", help="drzewo robocze zamiast wersji")
    s = sub.add_parser("cofnij")
    s.add_argument("repo")
    s.add_argument("--do", required=True)
    s.add_argument("--odcisk", required=True)
    s.add_argument("--czekaj", type=float, default=600)
    s = sub.add_parser("kopie")
    s.add_argument("repo")
    s = sub.add_parser("z-buildu")
    s.add_argument("repo")
    s.add_argument("--build", required=True)
    return p


POLECENIA = {"sprawdz": cmd_sprawdz, "plan": cmd_plan, "wgraj": cmd_wgraj, "cofnij": cmd_cofnij, "kopie": cmd_kopie,
             "z-buildu": cmd_z_buildu, "podglad": cmd_podglad}


def main(argv: list[str] | None = None, pol: Polaczenie | None = None) -> int:
    a = parser().parse_args(argv)
    pol = pol or PolaczenieSSH(a.host)
    try:
        wynik = POLECENIA[a.polecenie](a, pol)
    except Odmowa as exc:
        if a.json:
            print(json.dumps({"blad": str(exc)}, ensure_ascii=False))
        _info(f"Odmowa: {exc}")
        return 1
    wynik, kod = wynik if isinstance(wynik, tuple) else (wynik, 0)
    if a.json or a.polecenie in ("wgraj", "cofnij"):
        print(json.dumps(wynik, ensure_ascii=False, indent=None if a.json else 2))
    else:
        print(_tekst(a.polecenie, wynik))
    return kod


if __name__ == "__main__":
    sys.exit(main())
