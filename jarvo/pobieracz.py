"""Pobieranie narzędzi z przypiętą sumą sha256 (docs/NATYWNIE.md, c3 i L03).

Każdy plik ma w manifeście adres, sumę i rozmiar. Pobieramy przez HTTPS z weryfikacją certyfikatu, pokazujemy pasek
(procent, MB, prędkość), wznawiamy przerwane pobranie (nagłówek Range) i sprawdzamy sumę PRZED rozpakowaniem.
Rozpakowujemy do `<wersja>.new` i dopiero po sukcesie zmieniamy nazwę, więc przerwana instalacja nie zostawia
połowy narzędzia. Plik z inną sumą zatrzymuje instalację: niczego nie uruchamiamy bez zgodnej sumy.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PORCJA = 1 << 16
AGENT = "jarvo-instalator/1"


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


def rozpakuj(archiwum: Path, katalog: Path, format: str, usun_poziom: int = 0) -> None:
    """Bezpieczne rozpakowanie (bez ścieżek poza `katalog`, bez urządzeń i dowiązań na zewnątrz). `usun_poziom`
    zdejmuje tyle początkowych katalogów z każdej ścieżki (np. 1 dla archiwów z katalogiem `nazwa-wersja/`)."""
    katalog = Path(katalog).resolve()
    katalog.mkdir(parents=True, exist_ok=True)

    def przytnij(nazwa: str) -> str | None:
        czesci = [c for c in nazwa.replace("\\", "/").split("/") if c not in ("", ".")]
        czesci = czesci[usun_poziom:]
        return "/".join(czesci) if czesci else None

    if format == "zip":
        with zipfile.ZipFile(archiwum) as z:
            for info in z.infolist():
                rel = przytnij(info.filename)
                if rel is None:
                    continue
                cel = _w_srodku(katalog, rel)
                if info.is_dir():
                    cel.mkdir(parents=True, exist_ok=True)
                    continue
                cel.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as zr, open(cel, "wb") as zw:
                    shutil.copyfileobj(zr, zw)
                tryb = (info.external_attr >> 16) & 0o777
                if tryb and os.name != "nt":
                    os.chmod(cel, tryb)
        return
    if format in ("tar.gz", "tgz", "tar.xz", "tar.bz2", "tar"):
        with tarfile.open(archiwum, "r:*") as t:
            czlonki = []
            for m in t.getmembers():
                rel = przytnij(m.name)
                if rel is None:
                    continue
                m.name = rel
                if m.issym() or m.islnk():
                    if os.name == "nt":               # zwykły użytkownik Windows nie tworzy symlinków: pomijamy
                        continue
                czlonki.append(m)
            t.extractall(katalog, members=czlonki, filter="data")
        return
    if format == "plik":
        cel = _w_srodku(katalog, Path(archiwum).name)
        shutil.copy2(archiwum, cel)
        if os.name != "nt":
            os.chmod(cel, 0o755)
        return
    raise BladPobierania(f"nieznany format archiwum: {format}")


def katalog_wersji(wersja: str) -> str:
    """Krótka nazwa katalogu wersji: bez dopisku budowy po „+” (3.13.17+20261021 → 3.13.17). Na Windows ścieżki
    pod MAX_PATH (260 znaków) liczą się co do znaku (Z25), a pełną wersję trzyma znacznik i narzedzia.json."""
    return wersja.split("+", 1)[0]


def zainstaluj(nazwa: str, wersja: str, plik: dict, katalog_narzedzi: Path, pobrane: Path, *,
               pasek: bool = True, wyjscie=None) -> Path:
    """Narzędzie z jednego wpisu manifestu (url, sha256, rozmiar, format, usun_poziom, nazwa_pliku) do
    `katalog_narzedzi/nazwa/<wersja bez dopisku budowy>`. Gotowa instalacja z tą samą sumą = bez zmian.
    Zwraca katalog wersji."""
    docelowy = Path(katalog_narzedzi) / nazwa / katalog_wersji(wersja)
    znacznik = docelowy / ".jarvo-suma"
    if znacznik.is_file() and znacznik.read_text(encoding="utf-8").strip() == plik["sha256"]:
        return docelowy
    nazwa_pliku = plik.get("nazwa_pliku") or plik["url"].rsplit("/", 1)[-1].split("?")[0]
    archiwum = pobierz(plik["url"], Path(pobrane) / f"{plik['sha256'][:16]}-{nazwa_pliku}", plik["sha256"],
                       plik.get("rozmiar"), nazwa=f"{nazwa} {wersja}", pasek=pasek, wyjscie=wyjscie)
    nowy = docelowy.with_name(docelowy.name + ".new")
    if nowy.exists():
        shutil.rmtree(nowy)
    rozpakuj(archiwum, nowy, plik.get("format") or "zip", int(plik.get("usun_poziom") or 0))
    (nowy / ".jarvo-suma").write_text(plik["sha256"] + "\n", encoding="utf-8")
    if docelowy.exists():
        stary = docelowy.with_name(docelowy.name + f".stary-{int(time.time())}")
        os.replace(docelowy, stary)
        shutil.rmtree(stary, ignore_errors=True)
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
