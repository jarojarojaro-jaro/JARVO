"""Pobieranie narzędzi z przypiętą sumą sha256 (docs/NATYWNIE.md, c3 i L03).

Każdy plik ma w manifeście adres, sumę i rozmiar. Pobieramy przez HTTPS z weryfikacją certyfikatu, pokazujemy pasek
(procent, MB, prędkość), wznawiamy przerwane pobranie (nagłówek Range) i sprawdzamy sumę PRZED rozpakowaniem.
Rozpakowujemy do `<wersja>.new` i dopiero po sukcesie zmieniamy nazwę, więc przerwana instalacja nie zostawia
połowy narzędzia. Plik z inną sumą zatrzymuje instalację: niczego nie uruchamiamy bez zgodnej sumy. Po rozpakowaniu
manifest może usunąć zbędne pliki (`usun`) i zmienić nazwy (`zmien_nazwe`), zanim wersja trafi na swoje miejsce.
"""
from __future__ import annotations

import hashlib
import os
import posixpath
import shutil
import stat
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

PORCJA = 1 << 16
AGENT = "jarvo-instalator/1"
DOWIAZANIE_MAX = 4096                # treść wpisu-dowiązania w zipie to ścieżka celu, nie dane


class BladPobierania(RuntimeError):
    """Pobranie albo rozpakowanie się nie udało (komunikat po polsku, bez sekretów)."""


class _Pasek:
    def __init__(self, nazwa: str, razem: int | None, start: int = 0, wyjscie=None):
        self.nazwa, self.razem, self.mam = nazwa, razem, start
        self.wyjscie = wyjscie or sys.stderr
        self.tty = getattr(self.wyjscie, "isatty", lambda: False)()
        self.t0, self.ostatni, self.ostatni_proc = time.monotonic(), 0.0, -10
        self.start = start

    def dodaj(self, n: int) -> None:
        self.mam += n
        teraz = time.monotonic()
        if self.tty and teraz - self.ostatni < 0.2:
            return
        proc = int(self.mam * 100 / self.razem) if self.razem else None
        if not self.tty and (proc is None or proc < self.ostatni_proc + 10):
            return
        self.ostatni = teraz
        if proc is not None:
            self.ostatni_proc = proc
        self._pisz(koniec=False)

    def _pisz(self, koniec: bool) -> None:
        mb = self.mam / 1e6
        szybkosc = (self.mam - self.start) / 1e6 / max(time.monotonic() - self.t0, 1e-6)
        if self.razem:
            tekst = f"  {self.nazwa}: {self.mam * 100 // self.razem:3d}%  {mb:7.1f}/{self.razem / 1e6:.1f} MB  " \
                    f"{szybkosc:5.1f} MB/s"
        else:
            tekst = f"  {self.nazwa}: {mb:7.1f} MB  {szybkosc:5.1f} MB/s"
        if self.tty:
            self.wyjscie.write("\r" + tekst + ("\n" if koniec else ""))
        else:
            self.wyjscie.write(tekst + "\n")
        self.wyjscie.flush()

    def koniec(self) -> None:
        if self.tty or self.ostatni_proc < 100:
            self._pisz(koniec=True)


def sha256_pliku(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()


def pobierz(url: str, cel: Path, sha256: str, rozmiar: int | None = None, *, nazwa: str | None = None,
            naglowki: dict | None = None, proby: int = 4, pasek: bool = True, wyjscie=None) -> Path:
    """Pobiera `url` do `cel` i sprawdza sumę. Plik już obecny z dobrą sumą = bez pobierania. Zwraca `cel`."""
    cel = Path(cel)
    sha256 = sha256.lower().strip()
    if len(sha256) != 64:
        raise BladPobierania(f"{nazwa or cel.name}: w manifeście brak pełnej sumy sha256")
    if not url.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):   # pętla zwrotna: tylko testy
        raise BladPobierania(f"{nazwa or cel.name}: tylko adresy https (dostałem {url[:40]}…)")
    if cel.is_file() and sha256_pliku(cel) == sha256:
        return cel
    cel.parent.mkdir(parents=True, exist_ok=True)
    czesc = cel.with_name(cel.name + ".czesc")
    ostatni_blad = ""
    for proba in range(proby):
        mam = czesc.stat().st_size if czesc.exists() else 0
        if rozmiar and mam > rozmiar:
            czesc.unlink()
            mam = 0
        zadanie = urllib.request.Request(url, headers={"User-Agent": AGENT, **(naglowki or {})})
        if mam:
            zadanie.add_header("Range", f"bytes={mam}-")
        try:
            with urllib.request.urlopen(zadanie, timeout=60) as odp:
                if mam and odp.status != 206:          # serwer nie wznawia: od początku
                    mam = 0
                razem = rozmiar or (int(odp.headers.get("Content-Length") or 0) + mam) or None
                p = _Pasek(nazwa or cel.name, razem, mam, wyjscie) if pasek else None
                with open(czesc, "ab" if mam else "wb") as f:
                    for kawalek in iter(lambda: odp.read(PORCJA), b""):
                        f.write(kawalek)
                        if p:
                            p.dodaj(len(kawalek))
                if p:
                    p.koniec()
            break
        except urllib.error.HTTPError as e:
            if e.code == 416 and czesc.exists():       # całość już jest
                break
            ostatni_blad = f"HTTP {e.code}"
            if e.code in (401, 403, 404):
                raise BladPobierania(f"{nazwa or cel.name}: {ostatni_blad} dla {url}") from None
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            ostatni_blad = str(getattr(e, "reason", e))[:200]
        time.sleep(min(2 ** proba, 15))
    else:
        raise BladPobierania(f"{nazwa or cel.name}: nie udało się pobrać ({ostatni_blad})")
    suma = sha256_pliku(czesc)
    if suma != sha256:
        czesc.unlink(missing_ok=True)
        raise BladPobierania(f"{nazwa or cel.name}: suma sha256 się nie zgadza (jest {suma[:12]}…, ma być "
                             f"{sha256[:12]}…). Plik usunięty, niczego nie uruchomiłem.")
    os.replace(czesc, cel)
    return cel


def _w_srodku(katalog: Path, nazwa: str) -> Path:
    cel = (katalog / nazwa).resolve()
    if cel != katalog and katalog not in cel.parents:
        raise BladPobierania(f"archiwum próbuje pisać poza katalog: {nazwa}")
    return cel


def _wewnatrz(katalog: Path, sciezka: str | os.PathLike) -> bool:
    """Czy ścieżka (już znormalizowana albo rozwiązana) leży w `katalog`, bez względu na wielkość liter na Windows."""
    k = os.path.normcase(os.path.abspath(katalog))
    s = os.path.normcase(os.path.abspath(sciezka))
    return s == k or s.startswith(k.rstrip(os.sep) + os.sep)


def _wzgledna(rel: str) -> bool:
    """Ścieżka z manifestu albo z dowiązania: względna, bez „..” i bez litery dysku."""
    r = str(rel).replace("\\", "/")
    return bool(r) and not r.startswith("/") and ":" not in r and ".." not in r.split("/")


def _usun_drzewo(p: Path) -> None:
    """rmtree, które na Windows zdejmuje atrybut tylko do odczytu (archiwa tar go nadają) i próbuje jeszcze raz."""
    def ponow(funkcja, sciezka, _blad):
        os.chmod(sciezka, stat.S_IWRITE | stat.S_IREAD)
        funkcja(sciezka)
    shutil.rmtree(p, onexc=ponow)


def _kopiuj_cele(dowiazania: list[tuple[Path, str]], katalogi: bool = True) -> None:
    """Windows: dowiązanie z archiwum staje się kopią celu (zwykły użytkownik nie tworzy symlinków). Łańcuchy
    (a → b → plik) rozwiązujemy kolejnymi przejściami; dowiązanie do nieistniejącego celu (albo do katalogu, gdy
    `katalogi=False`) pomijamy: i tak byłoby zepsute. Dowiązanie do katalogu, w którym samo leży, to pętla: błąd."""
    zostale = list(dowiazania)
    while zostale:
        reszta = []
        for cel, docelowy in zostale:
            zrodlo = Path(docelowy)
            if zrodlo.is_file():
                cel.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(zrodlo, cel)
            elif zrodlo.is_dir() and katalogi:
                if _wewnatrz(zrodlo, cel):
                    raise BladPobierania(f"archiwum: dowiązanie {cel.name} wskazuje katalog, w którym leży (pętla)")
                shutil.copytree(zrodlo, cel, dirs_exist_ok=True)
            else:
                reszta.append((cel, docelowy))
        if len(reszta) == len(zostale):
            return
        zostale = reszta


def _rozpakuj_zip(archiwum: Path, katalog: Path, przytnij) -> None:
    dowiazania = []
    with zipfile.ZipFile(archiwum) as z:
        for info in z.infolist():
            rel = przytnij(info.filename)
            if rel is None:
                continue
            cel = _w_srodku(katalog, rel)
            tryb = info.external_attr >> 16
            if stat.S_ISLNK(tryb):                   # dowiązanie z Uniksa: w treści wpisu jest jego cel
                if info.file_size > DOWIAZANIE_MAX:
                    raise BladPobierania(f"archiwum: dowiązanie {rel} ma {info.file_size} B zamiast ścieżki celu")
                dowiazania.append((cel, rel, z.read(info).decode("utf-8", "replace")))
                continue
            if info.is_dir() or stat.S_ISDIR(tryb):
                cel.mkdir(parents=True, exist_ok=True)
                continue
            cel.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as zr, open(cel, "wb") as zw:
                shutil.copyfileobj(zr, zw)
            if tryb & 0o777 and os.name != "nt":
                os.chmod(cel, tryb & 0o755)          # bez zapisu dla grupy i innych (0o777 → 0o755)
    # Dowiązania na końcu: zwykłe pliki nigdy nie są pisane przez dowiązanie z tego samego archiwum.
    kopie = []
    for cel, rel, tekst in dowiazania:
        tekst = tekst.replace("\\", "/")
        docelowy = os.path.normpath(os.path.join(os.path.dirname(cel), tekst))
        if not tekst.strip() or "\0" in tekst:
            raise BladPobierania(f"archiwum: dowiązanie {rel} bez celu")
        if tekst.startswith("/") or ":" in tekst or not _wewnatrz(katalog, docelowy):
            raise BladPobierania(f"archiwum: dowiązanie {rel} → {tekst} wskazuje poza katalog")
        if os.name == "nt":
            kopie.append((cel, docelowy))
            continue
        cel.parent.mkdir(parents=True, exist_ok=True)
        if cel.is_symlink() or cel.exists():
            raise BladPobierania(f"archiwum: dowiązanie {rel} zastępuje inny wpis")
        os.symlink(tekst, cel)                       # względne, jak w archiwum
    for cel, rel, tekst in dowiazania:              # łańcuch dowiązań też nie może wyjść poza katalog
        if os.name != "nt" and not _wewnatrz(katalog, os.path.realpath(cel)):
            raise BladPobierania(f"archiwum: dowiązanie {rel} → {tekst} wskazuje poza katalog")
    _kopiuj_cele(kopie)


def _rozpakuj_tar(archiwum: Path, katalog: Path, przytnij) -> None:
    with tarfile.open(archiwum, "r:*") as t:
        czlonki, kopie = [], []
        for m in t.getmembers():
            rel = przytnij(m.name)
            if rel is None:
                continue
            m.name = rel
            if m.islnk():                            # twarde: cel liczony od korzenia archiwum, więc też przycięty
                cel_linku = przytnij(m.linkname)
                if cel_linku is None:
                    continue
                m.linkname = cel_linku
            elif m.issym() and os.name == "nt":      # symlink na Windows: kopia celu, jeśli to plik z archiwum
                docelowy = posixpath.normpath(posixpath.join(posixpath.dirname(rel), m.linkname.replace("\\", "/")))
                if _wzgledna(docelowy) and _wzgledna(rel):
                    kopie.append((_w_srodku(katalog, rel), str(katalog / docelowy)))
                continue                             # cel spoza archiwum (np. /proc/self/fd w Git for Windows)
            czlonki.append(m)
        # filtr "data": bez ścieżek i dowiązań poza katalog, bez urządzeń, bez bitów setuid i zapisu dla innych;
        # twarde dowiązania tarfile robi przez os.link (NTFS bez admina), a gdy się nie da, kopiuje plik.
        try:
            t.extractall(katalog, members=czlonki, filter="data")
        except tarfile.FilterError as e:
            raise BladPobierania(f"archiwum: {e}") from None
    _kopiuj_cele(kopie, katalogi=False)


def rozpakuj(archiwum: Path, katalog: Path, format: str, usun_poziom: int = 0, nazwa: str | None = None) -> None:
    """Bezpieczne rozpakowanie (bez ścieżek poza `katalog`, bez urządzeń i dowiązań na zewnątrz). `usun_poziom`
    zdejmuje tyle początkowych katalogów z każdej ścieżki (np. 1 dla archiwów z katalogiem `nazwa-wersja/`).
    `nazwa` = nazwa pliku w katalogu dla formatu `plik` (domyślnie nazwa pobranego pliku).

    Dowiązania: tar na POSIX odtwarza je tarfile (filtr "data"); zip ma je w external_attr (S_ISLNK), więc na POSIX
    robimy względne dowiązanie w obrębie katalogu (cel poza nim = błąd). Na Windows twarde dowiązania z tar
    rozpakowujemy, a symboliczne (tar i zip) zastępuje kopia celu z archiwum."""
    katalog = Path(katalog).resolve()
    katalog.mkdir(parents=True, exist_ok=True)

    def przytnij(n: str) -> str | None:
        czesci = [c for c in n.replace("\\", "/").split("/") if c not in ("", ".")]
        czesci = czesci[usun_poziom:]
        return "/".join(czesci) if czesci else None

    if format == "zip":
        _rozpakuj_zip(archiwum, katalog, przytnij)
        return
    if format in ("tar.gz", "tgz", "tar.xz", "tar.bz2", "tar"):
        _rozpakuj_tar(archiwum, katalog, przytnij)
        return
    if format == "plik":
        cel = _w_srodku(katalog, nazwa or Path(archiwum).name)
        shutil.copy2(archiwum, cel)
        if os.name != "nt":
            os.chmod(cel, 0o755)
        return
    raise BladPobierania(f"nieznany format archiwum: {format}")


def _w_katalogu(katalog: Path, rel: str, pole: str) -> Path:
    """Ścieżka z manifestu w katalogu narzędzia, bez rozwiązywania samego wpisu (usuwamy dowiązanie, nie jego cel)."""
    if not _wzgledna(rel):
        raise BladPobierania(f"{pole}: {rel!r} ma być ścieżką względną w katalogu narzędzia")
    p = katalog / rel
    if not _wewnatrz(katalog, p.parent.resolve()):
        raise BladPobierania(f"{pole}: {rel} wychodzi poza katalog narzędzia")
    return p


def po_rozpakowaniu(katalog: Path, usun: list | None = None, zmien_nazwe: dict | None = None) -> None:
    """Kroki z manifestu po rozpakowaniu: najpierw `usun` (zbędne programy, np. sqlite3 z błędem WAL-reset
    w platform-tools), potem `zmien_nazwe` (np. exiftool(-k).exe → exiftool.exe). Brak pliku = błąd manifestu."""
    katalog = Path(katalog).resolve()
    for rel in usun or []:
        p = _w_katalogu(katalog, rel, "usun")
        if p.is_symlink() or p.is_file():
            p.unlink()
        elif p.is_dir():
            _usun_drzewo(p)
        else:
            raise BladPobierania(f"usun: nie ma {rel} w archiwum")
    for stara, nowa in (zmien_nazwe or {}).items():
        z, na = _w_katalogu(katalog, stara, "zmien_nazwe"), _w_katalogu(katalog, nowa, "zmien_nazwe")
        if not (z.is_symlink() or z.exists()):
            raise BladPobierania(f"zmien_nazwe: nie ma {stara} w archiwum")
        if na.is_symlink() or na.exists():
            raise BladPobierania(f"zmien_nazwe: {nowa} już jest w archiwum")
        na.parent.mkdir(parents=True, exist_ok=True)
        os.replace(z, na)


def nazwa_z_adresu(url: str) -> str:
    """Nazwa pliku z końcówki adresu, zdekodowana (cpython-3.13.17%2B… → cpython-3.13.17+…), bez zapytania."""
    return urllib.parse.unquote(url.split("?", 1)[0].rsplit("/", 1)[-1]).replace("\\", "/").rsplit("/", 1)[-1]


def katalog_wersji(wersja: str) -> str:
    """Krótka nazwa katalogu wersji: bez dopisku budowy po „+” (3.13.17+20261021 → 3.13.17). Na Windows ścieżki
    pod MAX_PATH (260 znaków) liczą się co do znaku (Z25), a pełną wersję trzyma znacznik i narzedzia.json."""
    return wersja.split("+", 1)[0]


def zainstaluj(nazwa: str, wersja: str, plik: dict, katalog_narzedzi: Path, pobrane: Path, *,
               pasek: bool = True, wyjscie=None) -> Path:
    """Narzędzie z jednego wpisu manifestu (url, sha256, rozmiar, format, usun_poziom, nazwa_pliku, usun,
    zmien_nazwe) do `katalog_narzedzi/nazwa/<wersja bez dopisku budowy>`. Format `plik` ląduje pod `nazwa_pliku`
    (domyślnie końcówka adresu), a nie pod nazwą z pamięci podręcznej. Gotowa instalacja z tą samą sumą = bez zmian.
    Zwraca katalog wersji."""
    docelowy = Path(katalog_narzedzi) / nazwa / katalog_wersji(wersja)
    znacznik = docelowy / ".jarvo-suma"
    if znacznik.is_file() and znacznik.read_text(encoding="utf-8").strip() == plik["sha256"]:
        return docelowy
    nazwa_pliku = plik.get("nazwa_pliku") or nazwa_z_adresu(plik["url"])
    archiwum = pobierz(plik["url"], Path(pobrane) / f"{plik['sha256'][:16]}-{nazwa_pliku}", plik["sha256"],
                       plik.get("rozmiar"), nazwa=f"{nazwa} {wersja}", pasek=pasek, wyjscie=wyjscie)
    nowy = docelowy.with_name(docelowy.name + ".new")
    if nowy.exists():
        _usun_drzewo(nowy)
    try:
        rozpakuj(archiwum, nowy, plik.get("format") or "zip", int(plik.get("usun_poziom") or 0), nazwa=nazwa_pliku)
        po_rozpakowaniu(nowy, plik.get("usun"), plik.get("zmien_nazwe"))
    except BaseException:
        try:
            _usun_drzewo(nowy)                       # bez połowy narzędzia w <wersja>.new
        except OSError:
            pass
        raise
    (nowy / ".jarvo-suma").write_text(plik["sha256"] + "\n", encoding="utf-8")
    if docelowy.exists():
        stary = docelowy.with_name(docelowy.name + f".stary-{int(time.time())}")
        os.replace(docelowy, stary)
        try:
            _usun_drzewo(stary)
        except OSError:
            pass                                     # zajęty plik (Windows): zostaje do następnego sprzątania
    os.replace(nowy, docelowy)
    return docelowy


def zainstaluj_model(nazwa: str, model: dict, katalog_modeli: Path, *, pasek: bool = True, wyjscie=None) -> Path:
    """Wszystkie pliki modelu z manifestu do `katalog_modeli/<katalog>/<cel>`, każdy ze sprawdzoną sumą. Plik już
    obecny z dobrą sumą zostaje (bez sieci). Zwraca katalog modelu."""
    katalog = Path(katalog_modeli) / model["katalog"]
    katalog.mkdir(parents=True, exist_ok=True)
    baza = katalog.resolve()
    for p in model["pliki"]:
        cel = _w_srodku(baza, p["cel"])          # cel z manifestu nie wyjdzie poza katalog modelu
        pobierz(p["url"], cel, p["sha256"], p.get("rozmiar"), nazwa=f"{nazwa}: {p['cel']}", pasek=pasek,
                wyjscie=wyjscie)
    return katalog
