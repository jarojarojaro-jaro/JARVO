"""Dziennik zmian hosta (docs/NATYWNIE.md: D08, N08 i c4 „jarvo uninstall”, krok 4).

Wszystko, co Jarvo zmienia poza swoim katalogiem (autostart, PATH użytkownika, blok w pliku startowym powłoki,
pliki w katalogu domowym), trafia do `<stan>/zmiany-hosta.jsonl`: jeden wiersz JSON na zmianę (UTF-8, wiersze
kończy samo LF), {"czas": ISO 8601, "rodzaj": …, "szczegoly": {…}}. W szczegółach są tylko ścieżki, nazwy i skróty
sha256, nigdy treść plików ani sekrety (pole o nazwie jak TOKEN, KEY czy KLUCZ to błąd programisty). Wpis powstaje
PRZED zmianą: przerwana instalacja zostawia najwyżej wpis bez zmiany (cofnięcie powie „już nie ma”), nigdy zmianę
bez wpisu. Wyjątek to linger: wpis dopiero po udanym `loginctl enable-linger`, bo w nim nie ma czego porównać,
a wpis bez zmiany kazałby cofnięciu wyłączyć linger, który właściciel włączy kiedyś sam. Ten sam wpis drugi raz
nie powstaje, więc ponowna instalacja nie zmienia dziennika (E3: drugi przebieg instalatora niczego nie zmienia).

Rodzaje i to, co przy cofaniu znaczy „dalej nasze”:
    autostart-windows  zadanie Harmonogramu z naszym odciskiem w opisie albo wpis HKCU Run o naszej wartości
    autostart-macos    LaunchAgent: plik plist o naszej sumie (potem launchctl bootout)
    autostart-linux    jednostka systemd --user: plik o naszej sumie (potem disable --now)
    linger             loginctl enable-linger, włączony przez Jarvo na wyraźne życzenie właściciela: ten sam plik
                       lingera (odcisk); wpis znika przy `autostart.wylacz_linger()`, więc linger, który właściciel
                       włączy potem sam, zostaje
    path-uzytkownika   katalog w PATH użytkownika (Windows, HKCU\\Environment\\Path): usuwamy tylko ten wpis
    blok-rc            oznaczony blok w pliku startowym powłoki o naszej sumie; reszta pliku zostaje
    plik               plik poza katalogiem Jarva o naszej sumie
    katalog            katalog, którego przed Jarvem nie było, a zakłada go program Jarva (np. Chrome for Testing
                       Komputera trzyma raporty awarii w domyślnym katalogu danych mimo --user-data-dir): usuwamy cały,
                       gdy w środku są tylko ścieżki z `dozwolone` (względne, z „/”) i ich przodkowie; coś innego
                       (np. właściciel zaczął używać tej przeglądarki) = nie nasze, zostaje

`cofnij()` idzie od końca. Zmienione przez kogoś innego zostawia i mówi o tym; wpis, którego nie dało się cofnąć
(błąd), zostaje w dzienniku do następnej próby. `zapomnij()` usuwa wpis bez cofania (zmianę cofnięto inną drogą).
Polecenia systemu idą przez `wykonaj(argv) -> (kod, wyjście)`:
domyślnie `uruchom_domyslnie` (subprocess), w testach atrapa. Rejestr Windows idzie przez `Rejestr` (winreg),
w testach też atrapa.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .przenosne import Zamek, zapisz_atomowo
from .sciezki import WINDOWS, Uklad
from .srodowisko import SEKRET

PLIK = "zmiany-hosta.jsonl"
RODZAJE = ("autostart-windows", "autostart-macos", "autostart-linux", "linger", "path-uzytkownika", "blok-rc",
           "plik", "katalog")
_AUTOSTART = ("autostart-windows", "autostart-macos", "autostart-linux", "linger")
WYNIKI = {"cofniete": "cofnięte", "brak": "już nie ma", "nie-nasze": "nie nasze", "pominiete": "pominięte",
          "blad": "błąd, wpis zostaje"}
ENV = "Environment"                      # HKCU\Environment: zmienne użytkownika Windows
REG_SZ, REG_EXPAND_SZ = 1, 2             # stałe winreg (moduł jest tylko na Windows)

Wykonaj = Callable[[list], tuple[int, str]]


def _dekoduj(dane: bytes) -> str:
    """Wyjście programu jako tekst. Narzędzia konsoli Windows (schtasks, reg) piszą do potoku w stronie kodowej
    OEM (np. cp852), a nie w UTF-8, także gdy Python działa w trybie UTF-8 (sprawdzone na Windows 11 pl-PL:
    cp852 daje „pamięci”, cp1250 nie). Dlatego najpierw ścisłe UTF-8, potem OEM i ANSI, na końcu UTF-8
    z zamiennikami (wzór: hermes_cli/gateway_windows.py w f97608f)."""
    try:
        return dane.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if WINDOWS:
        import ctypes
        k32 = ctypes.windll.kernel32
        for strona in (k32.GetOEMCP(), k32.GetACP()):
            if strona and strona != 65001:
                try:
                    return dane.decode(f"cp{strona}")
                except (LookupError, UnicodeDecodeError):
                    continue
    return dane.decode("utf-8", errors="replace")


def uruchom_domyslnie(argv: list, czas: float = 60) -> tuple[int, str]:
    """Domyślne `wykonaj`: program z listy argv bez okna konsoli; zwraca (kod, stdout razem ze stderr).
    Bajty dekoduje `_dekoduj`, a nie encoding="utf-8", bo schtasks pisze w stronie OEM (polskie komunikaty)."""
    argv = [str(a) for a in argv]
    try:
        w = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=czas, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        return 127, f"nie ma programu {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"{argv[0]}: brak odpowiedzi po {czas:.0f} s"
    except OSError as e:
        return 126, f"{argv[0]}: {e}"
    return w.returncode, _dekoduj(w.stdout or b"")


# ---------------------------------------------------------------- dziennik

def sciezka(u: Uklad) -> Path:
    """`<stan>/zmiany-hosta.jsonl`."""
    return u.stan / PLIK


def _zamek(u: Uklad) -> Path:
    return u.stan / (PLIK + ".zamek")


def _sha(dane: bytes | str) -> str:
    return hashlib.sha256(dane.encode("utf-8") if isinstance(dane, str) else dane).hexdigest()


def _jawne(wartosc, klucz: str = ""):
    """Szczegóły wpisu jako JSON: Path → str, krotki → listy. Pole o nazwie jak TOKEN czy KLUCZ to błąd."""
    if klucz and SEKRET.search(klucz):
        raise ValueError(f"dziennik zmian hosta nie przyjmuje sekretów (pole {klucz!r})")
    if isinstance(wartosc, Path):
        return str(wartosc)
    if isinstance(wartosc, dict):
        return {str(k): _jawne(v, str(k)) for k, v in wartosc.items()}
    if isinstance(wartosc, (list, tuple)):
        return [_jawne(v) for v in wartosc]
    if wartosc is None or isinstance(wartosc, (str, int, float, bool)):
        return wartosc
    raise TypeError(f"dziennik zmian hosta: wartości {type(wartosc).__name__} nie zapiszę jako JSON")


def wpisy(u: Uklad) -> list[dict]:
    """Wpisy dziennika w kolejności zapisu. Urwany albo uszkodzony wiersz (np. po awarii zasilania) pomijamy.
    Dzielimy tylko po LF: json.dumps zostawia U+2028, U+2029 i U+0085 w wartościach (np. w ścieżce), a
    str.splitlines() przeciąłby po nich wpis i następny zapis by go zgubił. BOM (plik z Notatnika) pomijamy."""
    try:
        tekst = sciezka(u).read_text(encoding="utf-8-sig", errors="replace")
    except FileNotFoundError:
        return []
    wynik = []
    for linia in tekst.split("\n"):
        if not linia.strip():
            continue
        try:
            w = json.loads(linia)
        except ValueError:
            continue
        if isinstance(w, dict) and isinstance(w.get("rodzaj"), str) and isinstance(w.get("szczegoly"), dict):
            wynik.append(w)
    return wynik


def _wiersz(w: dict) -> str:
    tekst = json.dumps(w, ensure_ascii=False)
    try:
        tekst.encode("utf-8")
    except UnicodeEncodeError:
        # samotny surogat (nazwa pliku spoza UTF-8 na Linuksie, surrogateescape): ucieczka \udcxx wraca bez strat
        tekst = json.dumps(w)
    return tekst + "\n"


def _zapisz(u: Uklad, lista: list[dict]) -> None:
    zapisz_atomowo(sciezka(u), "".join(_wiersz(w) for w in lista))


def dopisz(u: Uklad, rodzaj: str, **szczegoly) -> dict:
    """Zapisuje zmianę hosta przed jej wykonaniem (linger: po, opis modułu). Ten sam rodzaj z tymi samymi
    szczegółami drugi raz nie powstaje (zwraca wtedy istniejący wpis). Szczegóły: ścieżki, nazwy, sumy; bez treści
    i bez sekretów."""
    if rodzaj not in RODZAJE:
        raise ValueError(f"nieznany rodzaj zmiany hosta {rodzaj!r} (znane: {', '.join(RODZAJE)})")
    jawne = _jawne(szczegoly)
    with Zamek(_zamek(u)):
        lista = wpisy(u)
        for w in lista:
            if w["rodzaj"] == rodzaj and w["szczegoly"] == jawne:
                return w
        wpis = {"czas": datetime.now().astimezone().isoformat(timespec="seconds"), "rodzaj": rodzaj,
                "szczegoly": jawne}
        _zapisz(u, [*lista, wpis])
    return wpis


def zapomnij(u: Uklad, rodzaj: str, **szczegoly) -> int:
    """Usuwa z dziennika wpisy tego rodzaju o tych szczegółach, bez cofania zmiany: gdy naszą zmianę cofnięto inną
    drogą (np. `autostart.wylacz_linger()`) albo cofnął ją już ktoś inny. Zwraca liczbę usuniętych wpisów."""
    jawne = _jawne(szczegoly)
    if not sciezka(u).exists():
        return 0
    with Zamek(_zamek(u)):
        lista = wpisy(u)
        zostaja = [w for w in lista if not (w["rodzaj"] == rodzaj and w["szczegoly"] == jawne)]
        if len(zostaja) != len(lista):
            _zapisz(u, zostaja)
    return len(lista) - len(zostaja)


def cofnij(u: Uklad, wykonaj: Wykonaj = uruchom_domyslnie, *, rodzaje=None, rejestr=None, log=print) -> list[dict]:
    """Cofa zmiany z dziennika od końca, tylko tam, gdzie dalej jest nasza wartość (c4, krok 4). `rodzaje` zawęża
    cofanie (np. tylko autostart). Zwraca raport [{"rodzaj", "wynik", "opis", "czas"}], wynik: cofniete, brak
    (już nie ma), nie-nasze (zmienione przez kogoś innego, zostaje), pominiete (inny system), blad. W dzienniku
    zostają wpisy z błędem i pominięte, żeby następna próba mogła je dokończyć."""
    raport = []
    with Zamek(_zamek(u)):
        lista, zostaja = wpisy(u), []
        for w in reversed(lista):
            if rodzaje is not None and w["rodzaj"] not in rodzaje:
                zostaja.append(w)
                continue
            try:
                wynik, opis = _cofnij_jeden(u, w, wykonaj, rejestr)
            except Exception as e:  # noqa: BLE001 - jeden zły wpis nie może zatrzymać sprzątania pozostałych
                wynik, opis = "blad", f"{w['rodzaj']}: {type(e).__name__}: {e}"
            if wynik in ("blad", "pominiete"):
                zostaja.append(w)
            raport.append({"rodzaj": w["rodzaj"], "wynik": wynik, "opis": opis, "czas": w.get("czas")})
            if log:
                log(f"  {WYNIKI.get(wynik, wynik)}: {opis}")
        if len(zostaja) != len(lista):
            _zapisz(u, zostaja[::-1])
    return raport


def _cofnij_jeden(u: Uklad, w: dict, wykonaj: Wykonaj, rejestr) -> tuple[str, str]:
    rodzaj, s = w["rodzaj"], w["szczegoly"]
    if rodzaj == "plik":
        return _cofnij_plik(Path(s["sciezka"]), s["sha256"])
    if rodzaj == "blok-rc":
        return _cofnij_blok(Path(s["sciezka"]), s["znacznik"], s["sha256"])
    if rodzaj == "katalog":
        return _cofnij_katalog(Path(s["sciezka"]), list(s.get("dozwolone") or []))
    if rodzaj == "path-uzytkownika":
        return _cofnij_path(s["wartosc"], rejestr, bool(s.get("srednik")))
    if rodzaj in _AUTOSTART:
        from . import autostart              # autostart importuje ten moduł, więc import dopiero tutaj
        return autostart.cofnij_wpis(u, w, wykonaj, rejestr=rejestr)
    return "blad", f"nieznany rodzaj {rodzaj!r} (wpis z nowszej wersji Jarva?)"


# ---------------------------------------------------------------- katalog

def katalog_przed_zmiana(u: Uklad, cel: Path, dozwolone: list[str]) -> Path | None:
    """Przed startem programu, który założy `cel` poza katalogiem Jarva: wpis „katalog” dla najwyższego brakującego
    katalogu na drodze do `cel` (np. ~/Library/Application Support/Google, gdy go nie było). `dozwolone` są względem
    `cel`; w dzienniku zapisujemy je względem tego katalogu. Gdy `cel` już jest (np. właściciela), nic nie zapisuje
    i zwraca None."""
    cel = Path(cel)
    if cel.exists():
        return None
    gora = cel
    while not gora.parent.exists() and gora.parent != gora:
        gora = gora.parent
    przedrostek = cel.relative_to(gora).as_posix()
    wzgledne = [f"{przedrostek}/{d}".strip("/") if przedrostek != "." else d.strip("/") for d in dozwolone]
    dopisz(u, "katalog", sciezka=str(gora), dozwolone=sorted(wzgledne))
    return gora


def _cofnij_katalog(p: Path, dozwolone: list[str]) -> tuple[str, str]:
    if not p.exists():
        return "brak", f"{p}: już nie ma"
    prefiksy = [d.strip("/") for d in dozwolone if d.strip("/")]

    def wolno(rel: str) -> bool:
        return any(rel == d or rel.startswith(d + "/") or d.startswith(rel + "/") for d in prefiksy)
    for korzen, katalogi, pliki in os.walk(p, followlinks=False):
        baza = Path(korzen).relative_to(p).as_posix()
        for nazwa in [*katalogi, *pliki]:
            rel = nazwa if baza == "." else f"{baza}/{nazwa}"
            if not wolno(rel):
                return "nie-nasze", f"{p}: jest w nim {rel} (nie zakładał go Jarvo), zostaje"
    shutil.rmtree(p)
    return "cofniete", f"{p}: usunięty (zakładał go program Jarva)"


# ---------------------------------------------------------------- plik

def zapisz_plik(u: Uklad, sciezka: Path, tresc: str | bytes, tryb: int | None = 0o644) -> bool:
    """Plik poza katalogiem Jarva (np. ~/.local/bin/jarvo): wpis w dzienniku, potem zapis atomowy.
    Zwraca True, gdy zapisał, a False, gdy plik już miał tę treść."""
    p = Path(sciezka)
    dane = tresc.encode("utf-8") if isinstance(tresc, str) else tresc
    dopisz(u, "plik", sciezka=str(p), sha256=_sha(dane))
    if p.is_file() and p.read_bytes() == dane:
        return False
    zapisz_atomowo(p, dane, tryb=tryb)
    return True


def _cofnij_plik(p: Path, sha: str) -> tuple[str, str]:
    if not p.exists():
        return "brak", f"{p}: pliku już nie ma"
    if not p.is_file() or _sha(p.read_bytes()) != sha:
        return "nie-nasze", f"{p}: zmieniony po instalacji, zostaje"
    p.unlink()
    return "cofniete", f"{p}: usunięty"


# ---------------------------------------------------------------- blok w pliku startowym powłoki

def blok_rc(tresc: str, znacznik: str = "jarvo") -> str:
    """Blok w pliku startowym powłoki: wiersz `# >>> jarvo >>>`, treść, wiersz `# <<< jarvo <<<`."""
    return f"# >>> {znacznik} >>>\n{tresc.strip(chr(10))}\n# <<< {znacznik} <<<\n"


def _wzor_bloku(znacznik: str) -> re.Pattern:
    z = re.escape(znacznik)
    return re.compile(rf"^# >>> {z} >>>\r?\n.*?^# <<< {z} <<<[^\n]*(?:\n|\Z)", re.M | re.S)


def _czytaj_rc(p: Path) -> str:
    # bajty bez zmian: końce wierszy właściciela i niepoprawne UTF-8 wracają do pliku takie, jakie były
    return p.read_bytes().decode("utf-8", "surrogateescape") if p.exists() else ""


def dodaj_blok_rc(u: Uklad, sciezka: Path, tresc: str, znacznik: str = "jarvo") -> bool:
    """Oznaczony blok w pliku startowym powłoki (np. PATH z ~/.local/bin w ~/.zprofile na macOS, c1). Blok o tym
    znaczniku podmienia w miejscu, resztę pliku zostawia; dowiązanie (dotfiles) zostaje, zmienia się jego cel.
    Zwraca True, gdy plik się zmienił."""
    p = Path(sciezka)
    if p.is_symlink():
        p = p.resolve()
    blok = blok_rc(tresc, znacznik)
    stary = _czytaj_rc(p)
    m = _wzor_bloku(znacznik).search(stary)
    if m:
        nowy = stary[:m.start()] + blok + stary[m.end():]
    else:
        nowy = stary + ("\n" if stary and not stary.endswith("\n") else "") + blok
    dopisz(u, "blok-rc", sciezka=str(p), znacznik=znacznik, sha256=_sha(blok))
    if nowy == stary:
        return False
    tryb = (p.stat().st_mode & 0o777) if p.exists() else 0o644
    zapisz_atomowo(p, nowy.encode("utf-8", "surrogateescape"), tryb=tryb)
    return True


def _cofnij_blok(p: Path, znacznik: str, sha: str) -> tuple[str, str]:
    if not p.is_file():
        return "brak", f"{p}: pliku już nie ma"
    stary = _czytaj_rc(p)
    m = _wzor_bloku(znacznik).search(stary)
    if not m:
        return "brak", f"{p}: nie ma już bloku {znacznik}"
    if _sha(m.group(0).encode("utf-8", "surrogateescape")) != sha:
        return "nie-nasze", f"{p}: blok {znacznik} zmieniony po instalacji, zostaje"
    nowy = stary[:m.start()] + stary[m.end():]
    if not nowy.strip():
        p.unlink()
        return "cofniete", f"{p}: usunięty (był w nim tylko blok {znacznik})"
    zapisz_atomowo(p, nowy.encode("utf-8", "surrogateescape"), tryb=p.stat().st_mode & 0o777)
    return "cofniete", f"{p}: usunięty blok {znacznik}"


# ---------------------------------------------------------------- PATH użytkownika (Windows)

class Rejestr:
    """Wartości w HKEY_CURRENT_USER przez winreg (tylko Windows). Nie przez reg.exe: ten pisze w stronie kodowej
    konsoli i zamienia znaki spoza niej, a zapis PATH z takim błędem zepsułby PATH właściciela."""

    def czytaj(self, klucz: str, nazwa: str) -> tuple[str, int] | None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, klucz) as k:
                wartosc, typ = winreg.QueryValueEx(k, nazwa)
        except FileNotFoundError:
            return None
        if not isinstance(wartosc, str):
            raise OSError(f"HKCU\\{klucz}\\{nazwa}: wartość typu {typ}, a miał być tekst")
        return wartosc, typ

    def zapisz(self, klucz: str, nazwa: str, wartosc: str, typ: int) -> None:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, klucz, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, nazwa, 0, typ, wartosc)

    def usun(self, klucz: str, nazwa: str) -> None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, klucz, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, nazwa)
        except FileNotFoundError:
            pass

    def oglos(self) -> None:
        """WM_SETTINGCHANGE „Environment”: Eksplorator i nowe okna konsoli biorą nowy PATH bez wylogowania."""
        import ctypes
        from ctypes import wintypes
        f = ctypes.WinDLL("user32").SendMessageTimeoutW
        f.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR, wintypes.UINT,
                      wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        wynik = ctypes.c_size_t()
        f(0xFFFF, 0x001A, 0, ENV, 0x0002, 5000, ctypes.byref(wynik))   # HWND_BROADCAST, SMTO_ABORTIFHUNG


def _klucz_path(wpis: str) -> str:
    return wpis.strip().strip('"').replace("/", "\\").rstrip("\\").casefold()


def dodaj_do_path(u: Uklad, katalog: Path | str, *, rejestr=None) -> bool:
    """Windows: katalog na końcu PATH użytkownika (HKCU\\Environment\\Path; typ wartości zostaje). Wpis w dzienniku
    powstaje także wtedy, gdy katalog już był (np. z dawnej instalacji): po odinstalowaniu i tak ma zniknąć.
    Zwraca True, gdy PATH się zmienił."""
    wartosc = str(katalog)
    if not wartosc.strip() or ";" in wartosc:
        raise ValueError(f"katalog do PATH: {wartosc!r}")
    r = rejestr or Rejestr()
    tekst, typ = r.czytaj(ENV, "Path") or ("", REG_EXPAND_SZ)
    jest = any(_klucz_path(c) == _klucz_path(wartosc) for c in tekst.split(";"))
    if not any(w["rodzaj"] == "path-uzytkownika" and w["szczegoly"].get("wartosc") == wartosc for w in wpisy(u)):
        # PATH właściciela kończący się średnikiem (np. obraz windows-2025) wraca po odinstalowaniu bajt w bajt
        dopisz(u, "path-uzytkownika", wartosc=wartosc, **({"srednik": True} if tekst.endswith(";") and not jest else {}))
    if jest:
        return False
    # oryginał zostaje bez zmian na początku (także końcowy średnik), nasz katalog dochodzi na końcu
    r.zapisz(ENV, "Path", (tekst + wartosc) if (not tekst.strip(";") or tekst.endswith(";")) else f"{tekst};{wartosc}",
             typ)
    r.oglos()
    return True


def _cofnij_path(wartosc: str, rejestr, srednik: bool = False) -> tuple[str, str]:
    if rejestr is None and not WINDOWS:
        return "pominiete", f"PATH użytkownika ({wartosc}): zmieniamy go tylko na Windows"
    r = rejestr or Rejestr()
    obecna = r.czytaj(ENV, "Path")
    czesci = obecna[0].split(";") if obecna else []
    zostaja = [c for c in czesci if _klucz_path(c) != _klucz_path(wartosc)]
    if not obecna or len(zostaja) == len(czesci):
        return "brak", f"PATH użytkownika: nie ma już {wartosc}"
    nowa = ";".join(zostaja)
    if srednik and nowa.strip(";") and not nowa.endswith(";"):
        nowa += ";"                                  # PATH sprzed instalacji kończył się średnikiem
    if nowa.strip(";"):
        r.zapisz(ENV, "Path", nowa, obecna[1])
    else:
        r.usun(ENV, "Path")
    r.oglos()
    return "cofniete", f"PATH użytkownika: usunięty {wartosc}"
