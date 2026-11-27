#!/usr/bin/python3
"""Silnik pulpitu (wtyczka jarvo-pulpit, docs/PULPIT.md): ekran X11 serwera (`:0`) dla narzędzia `pulpit` agentów.

Działa Pythonem systemu (`/usr/bin/python3`, bo tylko on ma PyGObject z AT-SPI, Wnck i Gdk z pakietów pulpitu),
jako proces potomny procesu Hermesa: jedno polecenie JSON w wierszu na wejściu, jedna odpowiedź JSON w wierszu na
wyjściu. Pamięta numery elementów z ostatniego `zobacz`, więc trwa tyle co rozmowa wtyczki.

  zrzut       Gdk (okno główne X11) → Pillow: pomniejszenie do SZER_OBRAZU, ramki i numery elementów, JPEG,
  elementy    AT-SPI aktywnego okna (i otwartych menu tego programu): przycięta lista elementów z numerami,
  wejście     XTEST przez ctypes (libX11, libXtst): ruch, klik, przewijanie, przeciąganie, klawisze, pisanie
              (dowolny znak Unicode przez chwilowo przypisany wolny klawisz, więc polskie litery bez względu na układ),
  okna        Wnck: lista, aktywacja, zamknięcie, nowe okno uruchomionego programu,
  paragon     po każdym działaniu: zmiana ekranu (miniatura przed i po), aktywne okno, nowe i zamknięte okna, fokus.

Współrzędne: jedna przestrzeń, obraz całego ekranu pomniejszony do SZER_OBRAZU (1920×1080 → 1280×720); agent czyta
x,y z obrazu albo z listy elementów i tak samo je podaje, silnik przelicza na piksele ekranu.

Twarde zasady (infra/komputer/zasady.py, te same co Komputer Jarva): kliknięcie przycisku płatności i pisanie w pole
karty albo numeru karty tylko z linią ZGODA WŁAŚCICIELA (platnosc) w zadaniu agenta (komputer/zgoda_karty.py),
sekret w tekście zawsze odmowa; bez terminali, okna uruchamiania poleceń, menedżera zadań i okna Komputera Jarva
(tam działa narzędzie `komputer`), bez skrótów, które wylogowują, blokują ekran albo otwierają terminal.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.util
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TU = Path(__file__).resolve().parent
SZER_OBRAZU = 1280
JAKOSC = 72
DOMYSLNIE_ELEMENTOW = 60
MAKS_ELEMENTOW = 200
MAKS_WEZLOW = 4000            # węzłów AT-SPI na jedno przejście (LibreOffice i GIMP mają ich tysiące)
CZAS_DRZEWA = 2.5             # s na jedno przejście drzewa
MAKS_DZIECI = 300             # dzieci jednego węzła (listy plików, tabele)
MINIATURA = (320, 180)        # miniatura ekranu do paragonu (zmiana przed i po działaniu)
PROG_ZMIANY = 0.0003          # ułamek pikseli miniatury: mniej to „bez widocznej zmiany” (kilka wpisanych liter to więcej)

ROLE = {
    "push button": "przycisk", "button": "przycisk", "toggle button": "przełącznik", "check box": "pole wyboru",
    "radio button": "opcja", "menu item": "pozycja menu", "check menu item": "pozycja menu",
    "radio menu item": "pozycja menu", "menu": "menu", "combo box": "lista rozwijana", "text": "pole tekstu",
    "entry": "pole", "password text": "pole hasła", "spin button": "pole liczby", "slider": "suwak", "link": "link",
    "list item": "element listy", "page tab": "zakładka", "tree item": "element drzewa", "table cell": "komórka",
    "icon": "ikona", "push button menu": "przycisk", "split button": "przycisk", "toggle": "przełącznik",
    "label": "napis", "heading": "nagłówek", "status bar": "pasek stanu", "alert": "komunikat",
    "dialog": "okno dialogowe", "document text": "dokument", "document frame": "dokument", "canvas": "płótno",
}
DZIALANIE = frozenset({"push button", "button", "toggle button", "check box", "radio button", "menu item", "check menu item",
                       "radio menu item", "menu", "combo box", "text", "entry", "password text", "spin button",
                       "slider", "link", "list item", "page tab", "tree item", "icon", "push button menu",
                       "split button", "table cell", "canvas", "document text"})
OPIS = frozenset({"label", "heading", "status bar", "alert"})
POLA = frozenset({"text", "entry", "password text", "spin button", "combo box", "document text"})
ROLE_PRZYCISKOW = frozenset({"push button", "button", "link", "menu item", "check menu item", "radio menu item",
                             "toggle button", "push button menu", "split button"})

# okna, w których pulpit nie działa: terminale i uruchamianie poleceń (ominęłyby zgody terminala), menedżer zadań
TERMINALE = re.compile(r"(?i)(terminal|xterm|konsole|kitty|alacritty|tilix|terminator|wezterm|foot|urxvt|"
                       r"xfrun|appfinder|taskmanager|gnome-system-monitor)")
OKNA_AWARII = re.compile(r"(?i)apport")   # okno zgłoszenia awarii Ubuntu („Ubuntu”), zabiera fokus
SKROTY_ZAKAZANE = frozenset({
    ("alt", "f2"), ("alt", "f3"), ("super", "r"), ("ctrl", "alt", "t"), ("super", "t"),
    ("ctrl", "alt", "delete"), ("ctrl", "alt", "backspace"), ("ctrl", "alt", "escape"), ("ctrl", "alt", "l"),
    ("super", "l"), ("ctrl", "shift", "escape"), ("super", "p"), ("alt", "super", "s"),
})
MODY = {"ctrl": "Control_L", "control": "Control_L", "ctl": "Control_L", "alt": "Alt_L", "shift": "Shift_L",
        "super": "Super_L", "win": "Super_L", "meta": "Super_L"}
KLAWISZE = {"enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape", "tab": "Tab",
            "spacja": "space", "space": "space", "bs": "BackSpace", "backspace": "BackSpace", "del": "Delete",
            "delete": "Delete", "ins": "Insert", "insert": "Insert", "gora": "Up", "góra": "Up", "up": "Up",
            "dol": "Down", "dół": "Down", "down": "Down", "lewo": "Left", "left": "Left", "prawo": "Right",
            "right": "Right", "home": "Home", "end": "End", "pgup": "Prior", "pageup": "Prior", "page_up": "Prior",
            "pgdn": "Next", "pagedown": "Next", "page_down": "Next", "plus": "plus", "minus": "minus",
            "menu": "Menu", "print": "Print"}
PROGRAMY = {          # nazwa dla agenta → polecenie (kdenlive i inkscape: plik z manifestu, ścieżkę podaje wtyczka)
    "gimp": ["gimp"], "libreoffice": ["libreoffice"], "calc": ["libreoffice", "--calc"],
    "writer": ["libreoffice", "--writer"], "impress": ["libreoffice", "--impress"], "draw": ["libreoffice", "--draw"],
    "mousepad": ["mousepad"], "thunar": ["thunar"], "ristretto": ["ristretto"], "parole": ["parole"],
    "firefox": ["firefox", "--new-window"], "przegladarka": ["firefox", "--new-window"],
}
ZEWNETRZNE = ("kdenlive", "inkscape")
OTOCZENIE_A11Y = {"QT_LINUX_ACCESSIBILITY_ALWAYS_ON": "1", "QT_ACCESSIBILITY": "1", "GNOME_ACCESSIBILITY": "1",
                  "ACCESSIBILITY_ENABLED": "1", "SAL_USE_VCLPLUGIN": "gtk3"}


class Odmowa(Exception):
    """Twarda zasada albo zły argument: nic nie zrobione."""


# ------------------------------------------------------------------------------------------- zasady (czyste)

def _modul(nazwa: str, *sciezki: Path):
    import importlib.util
    for p in sciezki:
        if p.is_file():
            spec = importlib.util.spec_from_file_location(nazwa, p)
            m = importlib.util.module_from_spec(spec)
            sys.modules[nazwa] = m
            spec.loader.exec_module(m)
            return m
    raise RuntimeError(f"brak {nazwa}: wtyczka pulpitu bez twardych zasad nie działa")


ZASADY = _modul("jarvo_pulpit_zasady", TU / "zasady.py", TU.parent.parent / "infra" / "komputer" / "zasady.py")
ZGODA = _modul("jarvo_pulpit_zgoda", TU / "zgoda_karty.py", TU.parent.parent / "komputer" / "zgoda_karty.py")


def zgoda_platnosci() -> bool:
    """Linia ZGODA WŁAŚCICIELA z kategorią platnosc w zadaniu agenta (HERMES_KANBAN_TASK procesu Hermesa)."""
    karta = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    try:
        return bool(karta) and "platnosc" in ZGODA.zgoda_z_tresci(ZGODA.tresc_karty(karta))
    except Exception:  # noqa: BLE001 - nieczytelna zgoda to brak zgody
        return False


def sprawdz_klik(el: Optional[dict], zgoda=zgoda_platnosci) -> None:
    """Przycisk albo link płatności (cel i przodkowie z rolą działania) tylko ze zgodą `platnosc`."""
    w = ZASADY.przycisk_wrazliwy(el)
    if w and not zgoda():
        raise Odmowa(f"płatność („{w[0][:60]}”): tylko z linią ZGODA WŁAŚCICIELA: platnosc w zadaniu agenta; "
                     "przygotuj wszystko do tego kroku i poproś JARO o zgodę albo o kliknięcie (VNC)")


def sprawdz_pisanie(tekst: str, pole: Optional[dict], zgoda=zgoda_platnosci) -> None:
    if ZASADY.SEKRETY.search(tekst):
        raise Odmowa("w tekście jest klucz albo token: sekretów nie wpisujesz na ekranie")
    powod = ZASADY.pole_platnosci(pole) if pole else None
    if (powod or ZASADY.numery_kart(tekst)) and not zgoda():
        raise Odmowa(f"dane karty ({powod or 'numer karty w tekście'}): tylko z linią ZGODA WŁAŚCICIELA: platnosc "
                     "w zadaniu agenta")


def skrot(kombinacja: str) -> Tuple[List[str], List[str]]:
    """'ctrl+shift+s' → (modyfikatory X, klawisz X); Odmowa przy nieznanym albo zakazanym skrócie."""
    czesci = [c.strip() for c in re.split(r"\+(?!$)", kombinacja.strip()) if c.strip()]
    if not czesci:
        raise Odmowa("klawisz: podaj np. Return, ctrl+s, alt+F4")
    mody, reszta = [], []
    for c in czesci:
        (mody if c.lower() in MODY else reszta).append(c)
    if len(reszta) > 1:
        raise Odmowa(f"klawisz „{kombinacja}”: jeden klawisz z modyfikatorami (np. ctrl+shift+s)")
    norm = tuple(sorted({"control": "ctrl", "ctl": "ctrl", "win": "super", "meta": "super"}.get(m.lower(), m.lower())
                        for m in mody) + [r.lower() for r in reszta])
    for zakaz in SKROTY_ZAKAZANE:
        if tuple(sorted(zakaz[:-1])) + (zakaz[-1],) == norm:
            raise Odmowa(f"skrót {kombinacja} wylogowuje, blokuje ekran albo otwiera terminal: nie na pulpicie")
    klawisz = reszta[0] if reszta else ""
    if klawisz:
        k = klawisz.lower()
        if k in KLAWISZE:
            klawisz = KLAWISZE[k]
        elif re.fullmatch(r"f([1-9]|1[0-2])", k):
            klawisz = k.upper()
    return [MODY[m.lower()] for m in mody], ([klawisz] if klawisz else [])


def rola_pl(rola: str) -> str:
    return ROLE.get(rola, rola)


def linia_elementu(e: dict) -> str:
    """`[12] przycisk „Zapisz” = „wartość” (fokus) @640,360`"""
    s = f"[{e['n']}] {rola_pl(e['rola'])}"
    if e.get("nazwa"):
        s += f" „{e['nazwa']}”"
    if e.get("wartosc") not in (None, ""):
        s += f" = „{e['wartosc']}”"
    if e.get("stany"):
        s += f" ({', '.join(e['stany'])})"
    return s + f" @{e['x']},{e['y']}"


def zmiana(a: Optional[bytes], b: Optional[bytes]) -> float:
    """Ułamek pikseli miniatury, które się zmieniły (0..1)."""
    if not a or not b or len(a) != len(b):
        return 1.0 if (a or b) else 0.0
    return sum(1 for x, y in zip(a, b) if abs(x - y) > 16) / len(a)


def _napis(t: str, n: int = 60) -> str:
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


# ------------------------------------------------------------------------------------------- X11: XTEST przez ctypes

class X:
    def __init__(self, ekran: str) -> None:
        self.x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        self.xt = ctypes.CDLL(ctypes.util.find_library("Xtst") or "libXtst.so.6")
        v = ctypes.c_void_p
        self.x11.XOpenDisplay.restype = v
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XStringToKeysym.restype = ctypes.c_ulong
        self.x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x11.XKeysymToKeycode.restype = ctypes.c_ubyte
        self.x11.XKeysymToKeycode.argtypes = [v, ctypes.c_ulong]
        self.x11.XGetKeyboardMapping.restype = ctypes.POINTER(ctypes.c_ulong)
        self.x11.XGetKeyboardMapping.argtypes = [v, ctypes.c_ubyte, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.x11.XChangeKeyboardMapping.argtypes = [v, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_ulong),
                                                    ctypes.c_int]
        self.x11.XDisplayKeycodes.argtypes = [v, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        self.x11.XSync.argtypes = [v, ctypes.c_int]
        self.x11.XFree.argtypes = [v]
        for f in ("XTestFakeMotionEvent", "XTestFakeButtonEvent", "XTestFakeKeyEvent"):
            getattr(self.xt, f).argtypes = ([v, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
                                            if f == "XTestFakeMotionEvent" else
                                            [v, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong])
        self.xt.XTestQueryExtension.argtypes = [v] + [ctypes.POINTER(ctypes.c_int)] * 4
        self.d = self.x11.XOpenDisplay(ekran.encode())
        if not self.d:
            raise RuntimeError(f"nie ma dostępu do ekranu {ekran} (X11)")
        a = [ctypes.c_int() for _ in range(4)]
        if not self.xt.XTestQueryExtension(self.d, *[ctypes.byref(x) for x in a]):
            raise RuntimeError(f"ekran {ekran} nie ma rozszerzenia XTEST")
        lo, hi = ctypes.c_int(), ctypes.c_int()
        self.x11.XDisplayKeycodes(self.d, ctypes.byref(lo), ctypes.byref(hi))
        self.kmin, self.kmax = lo.value, hi.value
        self.zapas = self._wolny_klawisz()

    def sync(self) -> None:
        self.x11.XSync(self.d, 0)

    def _mapa(self, kod: int) -> List[int]:
        n = ctypes.c_int()
        p = self.x11.XGetKeyboardMapping(self.d, kod, 1, ctypes.byref(n))
        try:
            return [p[i] for i in range(n.value)]
        finally:
            self.x11.XFree(p)

    def _wolny_klawisz(self) -> int:
        for kod in range(self.kmax, self.kmin, -1):
            if not any(self._mapa(kod)):
                return kod
        return self.kmax

    def ruch(self, x: int, y: int) -> None:
        self.xt.XTestFakeMotionEvent(self.d, -1, int(x), int(y), 0)
        self.sync()

    def przycisk(self, nr: int, wcisniety: bool) -> None:
        self.xt.XTestFakeButtonEvent(self.d, nr, 1 if wcisniety else 0, 0)
        self.sync()

    def klik(self, x: int, y: int, nr: int = 1, razy: int = 1) -> None:
        self.ruch(x, y)
        time.sleep(0.03)
        for _ in range(razy):
            self.przycisk(nr, True)
            self.przycisk(nr, False)
            time.sleep(0.07)

    def przewin(self, kierunek: str, ile: int) -> None:
        nr = {"gora": 4, "dol": 5, "lewo": 6, "prawo": 7}[kierunek]
        for _ in range(ile):
            self.przycisk(nr, True)
            self.przycisk(nr, False)
            time.sleep(0.02)

    def przeciagnij(self, a: Tuple[int, int], b: Tuple[int, int], nr: int = 1) -> None:
        self.ruch(*a)
        time.sleep(0.05)
        self.przycisk(nr, True)
        kroki = 12
        for i in range(1, kroki + 1):
            self.ruch(a[0] + (b[0] - a[0]) * i // kroki, a[1] + (b[1] - a[1]) * i // kroki)
            time.sleep(0.025)
        time.sleep(0.05)
        self.przycisk(nr, False)

    def _kod(self, nazwa: str) -> Tuple[int, bool]:
        """(keycode, czy z shiftem) dla nazwy klawisza X albo jednego znaku; (0, False) gdy brak w układzie."""
        ks = self.x11.XStringToKeysym(nazwa.encode()) if len(nazwa) > 1 else _keysym(nazwa)
        if not ks and len(nazwa) == 1:
            ks = _keysym(nazwa)
        kod = self.x11.XKeysymToKeycode(self.d, ks) if ks else 0
        if not kod:
            return 0, False
        mapa = self._mapa(kod)
        if mapa and mapa[0] == ks:
            return kod, False
        if len(mapa) > 1 and mapa[1] == ks:
            return kod, True
        if len(nazwa) > 1:
            return kod, False
        low = _keysym(nazwa.lower())
        return (kod, nazwa != nazwa.lower()) if mapa and mapa[0] == low else (0, False)

    def klawisz(self, mody: List[str], klawisz: List[str], razy: int = 1) -> None:
        kody = []
        for m in mody:
            kody.append(self._kod(m)[0])
        if klawisz:
            k, shift = self._kod(klawisz[0])
            if not k:
                raise Odmowa(f"nieznany klawisz: {klawisz[0]}")
            if shift and "Shift_L" not in mody:
                kody.append(self._kod("Shift_L")[0])
            kody.append(k)
        if not all(kody):
            raise Odmowa("nieznany modyfikator")
        for _ in range(razy):
            for k in kody:
                self.xt.XTestFakeKeyEvent(self.d, k, 1, 0)
            for k in reversed(kody):
                self.xt.XTestFakeKeyEvent(self.d, k, 0, 0)
            self.sync()
            time.sleep(0.03)

    def pisz(self, tekst: str) -> None:
        shift = self._kod("Shift_L")[0]
        przypisany = False
        try:
            for z in tekst:
                if z in "\n\r":
                    self.klawisz([], ["Return"])
                    continue
                if z == "\t":
                    self.klawisz([], ["Tab"])
                    continue
                kod, sh = self._kod(z) if z.isascii() else (0, False)
                if kod:
                    if sh:
                        self.xt.XTestFakeKeyEvent(self.d, shift, 1, 0)
                    self.xt.XTestFakeKeyEvent(self.d, kod, 1, 0)
                    self.xt.XTestFakeKeyEvent(self.d, kod, 0, 0)
                    if sh:
                        self.xt.XTestFakeKeyEvent(self.d, shift, 0, 0)
                else:                        # znak spoza układu: chwilowo na wolnym klawiszu
                    ks = _keysym(z)
                    tab = (ctypes.c_ulong * 2)(ks, ks)
                    self.x11.XChangeKeyboardMapping(self.d, self.zapas, 2, tab, 1)
                    self.sync()
                    przypisany = True
                    time.sleep(0.03)
                    self.xt.XTestFakeKeyEvent(self.d, self.zapas, 1, 0)
                    self.xt.XTestFakeKeyEvent(self.d, self.zapas, 0, 0)
                self.sync()
                time.sleep(0.012)
        finally:
            if przypisany:
                time.sleep(0.03)
                tab = (ctypes.c_ulong * 2)(0, 0)
                self.x11.XChangeKeyboardMapping(self.d, self.zapas, 2, tab, 1)
                self.sync()


def _keysym(z: str) -> int:
    o = ord(z)
    return o if 0x20 <= o <= 0x7E or 0xA0 <= o <= 0xFF else 0x01000000 + o


def appimage(sciezka: str) -> bool:
    """AppImage typu 2 (znacznik `AI\\x02` po nagłówku ELF), także bez rozszerzenia w nazwie."""
    try:
        with open(sciezka, "rb") as f:
            return f.read(11)[8:11] == b"AI\x02"
    except OSError:
        return False


# ------------------------------------------------------------------------------------------- ekran: Gdk, Wnck, AT-SPI

class Pulpit:
    def __init__(self, ekran: str) -> None:
        os.environ["DISPLAY"] = ekran
        import gi
        gi.require_version("Gdk", "3.0")
        gi.require_version("GdkX11", "3.0")
        gi.require_version("Wnck", "3.0")
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi, Gdk, GdkX11, Wnck  # noqa: F401
        self.Atspi, self.Gdk, self.GdkX11, self.Wnck = Atspi, Gdk, GdkX11, Wnck
        if Gdk.Display.get_default() is None:
            raise RuntimeError(f"nie ma dostępu do ekranu {ekran} (Gdk)")
        self.ekran = ekran
        self.x = X(ekran)
        self.root = Gdk.get_default_root_window()
        self.w, self.h = self.root.get_width(), self.root.get_height()
        self.skala = max(1.0, self.w / SZER_OBRAZU)
        self.wnck = Wnck.Screen.get_default()
        self.elementy: Dict[int, dict] = {}
        self._wlacz_dostepnosc()

    # ---- współrzędne
    def na_ekran(self, x: float, y: float) -> Tuple[int, int]:
        sx, sy = int(round(x * self.skala)), int(round(y * self.skala))
        if not (0 <= sx < self.w and 0 <= sy < self.h):
            raise Odmowa(f"punkt {x},{y} poza ekranem (obraz {self.szer_obr()}×{self.wys_obr()})")
        return sx, sy

    def na_obraz(self, x: float, y: float) -> Tuple[int, int]:
        return int(round(x / self.skala)), int(round(y / self.skala))

    def szer_obr(self) -> int:
        return int(round(self.w / self.skala))

    def wys_obr(self) -> int:
        return int(round(self.h / self.skala))

    def _wlacz_dostepnosc(self) -> None:
        """org.a11y.Status IsEnabled = true: Qt, Firefox i Chromium budują drzewo AT-SPI dopiero po tym sygnale
        (jak przy włączonym czytniku ekranu)."""
        try:
            from gi.repository import Gio, GLib
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync("org.a11y.Bus", "/org/a11y/bus", "org.freedesktop.DBus.Properties", "Set",
                          GLib.Variant("(ssv)", ("org.a11y.Status", "IsEnabled", GLib.Variant("b", True))),
                          None, Gio.DBusCallFlags.NONE, 2000, None)
        except Exception:  # noqa: BLE001 - bez tego GTK i tak daje drzewo; Qt i Firefox mogą nie dać
            pass

    # ---- okna
    def _odswiez(self) -> None:
        """Zdarzenia X czekające w GLib (Wnck zna nowe okna, tytuły i fokus tylko z nich), potem pełny odczyt."""
        from gi.repository import GLib
        ctx = GLib.MainContext.default()
        for _ in range(500):
            if not ctx.iteration(False):
                break
        self.wnck.force_update()

    def _okna(self) -> list:
        self._odswiez()
        return [w for w in self.wnck.get_windows_stacked()
                if w.get_window_type() in (self.Wnck.WindowType.NORMAL, self.Wnck.WindowType.DIALOG,
                                           self.Wnck.WindowType.UTILITY)]

    def okno_opis(self, w) -> dict:
        x, y, ww, hh = w.get_geometry()
        ox, oy = self.na_obraz(x, y)
        return {"id": f"{w.get_xid():#x}", "tytul": w.get_name() or "", "program": w.get_class_group_name() or "",
                "pid": w.get_pid(), "x": ox, "y": oy, "szer": int(ww / self.skala), "wys": int(hh / self.skala),
                "aktywne": bool(w.is_active()), "zminimalizowane": bool(w.is_minimized())}

    def aktywne(self):
        self._odswiez()
        return self.wnck.get_active_window()

    def zakazane(self, w) -> Optional[str]:
        if w is None:
            return None
        klasa = f"{w.get_class_group_name() or ''} {w.get_class_instance_name() or ''}"
        if TERMINALE.search(klasa):
            return f"okno „{_napis(w.get_name(), 40)}” to terminal albo uruchamianie poleceń: polecenia dajesz narzędziem terminal"
        try:
            cmd = Path(f"/proc/{w.get_pid()}/cmdline").read_bytes()
        except OSError:
            cmd = b""
        if b"chrome-komputer" in cmd or b"komputer/profil" in cmd:
            return "to okno Komputera Jarva: strony w nim obsługujesz narzędziem komputer"
        return None

    def okno_w_punkcie(self, sx: int, sy: int):
        for w in reversed(self._okna()):
            if w.is_minimized():
                continue
            x, y, ww, hh = w.get_geometry()
            if x <= sx < x + ww and y <= sy < y + hh:
                return w
        return None

    def znajdz_okno(self, wzor: str):
        wzor = str(wzor or "").strip()
        if not wzor:
            raise Odmowa("podaj `okno`: fragment tytułu albo id z akcji okna")
        okna = self._okna()
        for w in okna:
            if f"{w.get_xid():#x}" == wzor.lower():
                return w
        pasuje = [w for w in okna if wzor.lower() in (w.get_name() or "").lower()]
        if not pasuje:
            raise Odmowa(f"nie ma okna z „{wzor}” w tytule; akcja okna pokaże listę")
        return pasuje[-1]                   # najwyżej położone

    def czas_x(self) -> int:
        return self.GdkX11.x11_get_server_time(self.root)

    def aktywuj(self, w) -> None:
        if w.is_minimized():
            w.unminimize(self.czas_x())
        w.activate(self.czas_x())
        for _ in range(15):
            time.sleep(0.05)
            if self.aktywne() and self.aktywne().get_xid() == w.get_xid():
                return

    # ---- obraz
    def _pixbuf(self, x=0, y=0, w=None, h=None):
        return self.Gdk.pixbuf_get_from_window(self.root, x, y, w or self.w, h or self.h)

    def _obraz(self, x=0, y=0, w=None, h=None):
        from PIL import Image
        pb = self._pixbuf(x, y, w, h)
        tryb = "RGBA" if pb.get_has_alpha() else "RGB"
        im = Image.frombytes(tryb, (pb.get_width(), pb.get_height()), pb.get_pixels(), "raw", tryb,
                             pb.get_rowstride())
        return im.convert("RGB")

    def miniatura(self) -> bytes:
        from PIL import Image
        return self._obraz().resize(MINIATURA, Image.BILINEAR).convert("L").tobytes()

    def zrzut(self, elementy: List[dict], obszar: Optional[List[int]] = None, numery: bool = True) -> Tuple[str, int, int]:
        """JPEG base64 całego ekranu (albo obszaru w przestrzeni obrazu, w pełnej rozdzielczości) z numerami."""
        from PIL import Image, ImageDraw, ImageFont
        if obszar:
            ox, oy = self.na_ekran(obszar[0], obszar[1])
            ex = min(self.w, int((obszar[0] + obszar[2]) * self.skala))
            ey = min(self.h, int((obszar[1] + obszar[3]) * self.skala))
            if ex - ox < 8 or ey - oy < 8:
                raise Odmowa("obszar: za mały (x, y, szerokość, wysokość w pikselach obrazu)")
            im = self._obraz(ox, oy, ex - ox, ey - oy)
            skala = 1.0 if im.width <= SZER_OBRAZU else im.width / SZER_OBRAZU
            if skala > 1:
                im = im.resize((SZER_OBRAZU, int(im.height / skala)), Image.LANCZOS)
            przesun = (ox, oy)
        else:
            im = self._obraz().resize((self.szer_obr(), self.wys_obr()), Image.LANCZOS)
            skala, przesun = self.skala, (0, 0)
        if numery and elementy:
            rys = ImageDraw.Draw(im)
            try:
                font = ImageFont.load_default(size=12)
            except TypeError:
                font = ImageFont.load_default()
            for e in elementy:
                b = e["_ekran"]
                x0, y0 = (b[0] - przesun[0]) / skala, (b[1] - przesun[1]) / skala
                x1, y1 = (b[0] + b[2] - przesun[0]) / skala, (b[1] + b[3] - przesun[1]) / skala
                if x1 < 0 or y1 < 0 or x0 > im.width or y0 > im.height:
                    continue
                rys.rectangle([x0, y0, x1, y1], outline=(230, 30, 60), width=1)
                t = str(e["n"])
                tw = int(rys.textlength(t, font=font)) + 4
                lx, ly = max(0, x0), max(0, y0 - 13 if y0 >= 13 else y0)
                rys.rectangle([lx, ly, lx + tw, ly + 13], fill=(230, 30, 60))
                rys.text((lx + 2, ly), t, fill=(255, 255, 255), font=font)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=JAKOSC, optimize=True)
        return base64.b64encode(buf.getvalue()).decode(), im.width, im.height

    # ---- AT-SPI
    def _aplikacja(self, pid: int):
        d = self.Atspi.get_desktop(0)
        for i in range(d.get_child_count()):
            a = d.get_child_at_index(i)
            try:
                if a is not None and a.get_process_id() == pid:
                    return a
            except Exception:  # noqa: BLE001
                continue
        return None

    def _stany(self, acc) -> set:
        S = self.Atspi.StateType
        ss = acc.get_state_set()
        return {n for n, s in (("showing", S.SHOWING), ("visible", S.VISIBLE), ("focused", S.FOCUSED),
                               ("checked", S.CHECKED), ("selected", S.SELECTED), ("enabled", S.ENABLED),
                               ("sensitive", S.SENSITIVE), ("expanded", S.EXPANDED), ("active", S.ACTIVE),
                               ("editable", S.EDITABLE), ("manages", S.MANAGES_DESCENDANTS),
                               ("defunct", S.DEFUNCT), ("expandable", S.EXPANDABLE)) if ss.contains(s)}

    def _ramka(self, acc) -> Optional[Tuple[int, int, int, int]]:
        try:
            r = acc.get_extents(self.Atspi.CoordType.SCREEN)
        except Exception:  # noqa: BLE001
            return None
        if r.width <= 1 or r.height <= 1 or r.x + r.width <= 0 or r.y + r.height <= 0 or r.x >= self.w or r.y >= self.h:
            return None
        return r.x, r.y, r.width, r.height

    def okna_aplikacji(self, w) -> list:
        """Okna AT-SPI programu aktywnego okna: to aktywne (albo o tym tytule) i otwarte menu."""
        app = self._aplikacja(w.get_pid()) if w is not None else None
        if app is None:
            return []
        tytul = (w.get_name() or "").strip()
        glowne, menu, inne = [], [], []
        for i in range(min(app.get_child_count(), 50)):
            c = app.get_child_at_index(i)
            if c is None:
                continue
            try:
                st = self._stany(c)
                rola = c.get_role_name()
            except Exception:  # noqa: BLE001
                continue
            if "active" in st or (tytul and (c.get_name() or "").strip() == tytul):
                glowne.append(c)
            elif rola in ("menu", "popup menu", "window", "tool tip") and "showing" in st:
                menu.append(c)
            elif "showing" in st:
                inne.append(c)
        return menu + (glowne or inne)

    def drzewo(self, w, maks: int) -> List[dict]:
        start, wezly = time.monotonic(), 0
        wynik: List[dict] = []
        opisy: List[dict] = []
        stos = list(reversed(self.okna_aplikacji(w)))
        while stos and wezly < MAKS_WEZLOW and time.monotonic() - start < CZAS_DRZEWA:
            acc = stos.pop()
            wezly += 1
            try:
                st = self._stany(acc)
                rola = acc.get_role_name()
            except Exception:  # noqa: BLE001
                continue
            if "showing" not in st or "defunct" in st:
                continue
            ramka = self._ramka(acc)
            if ramka and (rola in DZIALANIE or rola in OPIS):
                e = self._element(acc, rola, st, ramka)
                if e and (rola in DZIALANIE or e.get("nazwa")):
                    (wynik if rola in DZIALANIE else opisy).append(e)
            try:
                n = acc.get_child_count()
            except Exception:  # noqa: BLE001
                n = 0
            if rola == "combo box" and "expanded" not in st:
                n = 0                          # zamknięta lista rozwijana: pozycje są ukryte
            dzieci = []
            for i in range(min(n, MAKS_DZIECI)):
                try:
                    c = acc.get_child_at_index(i)
                except Exception:  # noqa: BLE001
                    c = None
                if c is not None:
                    dzieci.append(c)
            stos.extend(reversed(dzieci))
        # najpierw działania, potem napisy, ale w kolejności czytania (góra → dół, lewo → prawo)
        wybrane = wynik[:maks]
        wybrane += opisy[: max(0, min(len(opisy), maks - len(wybrane), maks // 3))]
        wybrane.sort(key=lambda e: (e["_ekran"][1] // 12, e["_ekran"][0]))
        for i, e in enumerate(wybrane, 1):
            e["n"] = i
        self._ucieto = len(wynik) + len(opisy) - len(wybrane)
        self._wezly = wezly
        return wybrane

    def _element(self, acc, rola: str, st: set, ramka) -> Optional[dict]:
        try:
            nazwa = acc.get_name() or ""
        except Exception:  # noqa: BLE001
            nazwa = ""
        if not nazwa and rola in ("label", "heading", "status bar", "alert", "table cell"):
            nazwa = self._tekst(acc, 80)
        cx, cy = self.na_obraz(ramka[0] + ramka[2] / 2, ramka[1] + ramka[3] / 2)
        e = {"rola": rola, "nazwa": _napis(nazwa, 60), "x": cx, "y": cy, "_ekran": ramka, "_acc": acc}
        if rola in POLA and rola != "password text":
            e["wartosc"] = _napis(self._tekst(acc, 200), 50)
        elif rola == "slider":
            try:
                e["wartosc"] = str(round(self.Atspi.Value.get_current_value(acc.get_value_iface()), 2))
            except Exception:  # noqa: BLE001
                pass
        stany = []
        if "focused" in st:
            stany.append("fokus")
        if "checked" in st:
            stany.append("zaznaczone")
        if "selected" in st and rola not in ("page tab",):
            stany.append("wybrane")
        if "expanded" in st:
            stany.append("rozwinięte")
        if "enabled" not in st and "sensitive" not in st and rola in DZIALANIE:
            stany.append("nieaktywne")
        if "page tab" == rola and "selected" in st:
            stany.append("otwarta")
        e["stany"] = stany
        return e

    def _tekst(self, acc, n: int) -> str:
        try:
            t = acc.get_text_iface()
            if t is None:
                return ""
            ile = self.Atspi.Text.get_character_count(t)
            return self.Atspi.Text.get_text(t, 0, min(ile, n)) if ile else ""
        except Exception:  # noqa: BLE001
            return ""

    def opis_dla_zasad(self, acc) -> dict:
        """Słownik celu w kształcie zasad Komputera: rola, nazwa, atrybuty, przodkowie (do 4 w górę)."""
        def jeden(a) -> dict:
            try:
                atr = a.get_attributes() or {}
            except Exception:  # noqa: BLE001
                atr = {}
            try:
                return {"rola": a.get_role_name(), "nazwa": a.get_name() or "", "atrybuty": dict(atr)}
            except Exception:  # noqa: BLE001
                return {"rola": "", "nazwa": ""}
        el = jeden(acc)
        przodkowie, p = [], acc
        for _ in range(4):
            try:
                p = p.get_parent()
            except Exception:  # noqa: BLE001
                p = None
            if p is None:
                break
            przodkowie.append(jeden(p))
        el["przodkowie"] = przodkowie
        return el

    def element_w_punkcie(self, sx: int, sy: int) -> Optional[Any]:
        w = self.okno_w_punkcie(sx, sy)
        for top in self.okna_aplikacji(w):
            acc, glebokosc = top, 0
            ramka = self._ramka(top)
            if not ramka or not (ramka[0] <= sx < ramka[0] + ramka[2] and ramka[1] <= sy < ramka[1] + ramka[3]):
                continue
            while glebokosc < 40:
                try:
                    nast = self.Atspi.Component.get_accessible_at_point(acc.get_component_iface(), sx, sy,
                                                                        self.Atspi.CoordType.SCREEN)
                except Exception:  # noqa: BLE001
                    nast = None
                if nast is None or nast == acc:
                    break
                acc, glebokosc = nast, glebokosc + 1
            return acc
        return None

    def fokus(self) -> Optional[Any]:
        """Element z fokusem klawiatury w aktywnym oknie (AT-SPI), None gdy nieznany."""
        w = self.aktywne()
        start = time.monotonic()
        stos = list(self.okna_aplikacji(w))
        wezly = 0
        while stos and wezly < 3000 and time.monotonic() - start < 1.0:
            acc = stos.pop()
            wezly += 1
            try:
                st = self._stany(acc)
            except Exception:  # noqa: BLE001
                continue
            if "showing" not in st:
                continue
            if "focused" in st:
                return acc
            try:
                n = min(acc.get_child_count(), MAKS_DZIECI)
                stos.extend(c for c in (acc.get_child_at_index(i) for i in range(n)) if c is not None)
            except Exception:  # noqa: BLE001
                continue
        return None

    def opis_fokusu(self) -> str:
        acc = self.fokus()
        if acc is None:
            return ""
        try:
            rola = acc.get_role_name()
            s = f"{rola_pl(rola)} „{_napis(acc.get_name(), 40)}”"
            if rola in POLA and rola != "password text":
                s += f" = „{_napis(self._tekst(acc, 300), 80)}”"
            return s
        except Exception:  # noqa: BLE001
            return ""

    def teksty(self, w) -> str:
        """Napisy widocznych elementów okna (do czekania na tekst)."""
        start, wezly, out = time.monotonic(), 0, []
        stos = list(self.okna_aplikacji(w))
        while stos and wezly < MAKS_WEZLOW and time.monotonic() - start < CZAS_DRZEWA:
            acc = stos.pop()
            wezly += 1
            try:
                if "showing" not in self._stany(acc):
                    continue
                out.append(acc.get_name() or "")
                if acc.get_role_name() in OPIS | POLA:
                    out.append(self._tekst(acc, 300))
                n = min(acc.get_child_count(), MAKS_DZIECI)
                stos.extend(c for c in (acc.get_child_at_index(i) for i in range(n)) if c is not None)
            except Exception:  # noqa: BLE001
                continue
        return "\n".join(out)


# ------------------------------------------------------------------------------------------- akcje

class Silnik:
    def __init__(self, ekran: str) -> None:
        self.p = Pulpit(ekran)
        self.sprzataj()

    def sprzataj(self) -> List[str]:
        """Zamyka okna zgłoszeń awarii (apport „Ubuntu”), które zabierają fokus programom agenta; zgłoszenia
        zostają w /var/crash, a na stałe wyłącza je właściciel (docs/PULPIT.md „Porządek na :0”)."""
        zamkniete = []
        for w in self.p._okna():
            if OKNA_AWARII.search(f"{w.get_class_group_name() or ''} {w.get_class_instance_name() or ''}"):
                w.close(self.p.czas_x())
                zamkniete.append(w.get_name() or "")
        return zamkniete

    # ---- pomocnicze
    def _cel(self, a: dict, klucz_numeru: str = "numer", klucz_xy: str = "xy") -> Tuple[int, int, Optional[dict], Any]:
        """(x, y) na ekranie, opis elementu z ostatniego zobacz (albo None) i obiekt AT-SPI celu."""
        nr = a.get(klucz_numeru)
        if isinstance(nr, int) and not isinstance(nr, bool):
            e = self.p.elementy.get(nr)
            if e is None:
                raise Odmowa(f"nie ma elementu [{nr}] w ostatnim zobacz: zrób zobacz i weź numer z nowej listy")
            acc = e["_acc"]
            try:
                st = self.p._stany(acc)
            except Exception:  # noqa: BLE001
                st = {"defunct"}
            ramka = self.p._ramka(acc) if "defunct" not in st else None
            if ramka is None or "showing" not in st:
                raise Odmowa(f"element [{nr}] {rola_pl(e['rola'])} „{e['nazwa']}” zniknął z ekranu: zrób zobacz")
            return ramka[0] + ramka[2] // 2, ramka[1] + ramka[3] // 2, e, acc
        xy = a.get(klucz_xy)
        if isinstance(xy, (list, tuple)) and len(xy) == 2 and all(isinstance(v, (int, float)) for v in xy):
            sx, sy = self.p.na_ekran(xy[0], xy[1])
            pod = [e for e in self.p.elementy.values()
                   if e["_ekran"][0] <= sx < e["_ekran"][0] + e["_ekran"][2]
                   and e["_ekran"][1] <= sy < e["_ekran"][1] + e["_ekran"][3]]
            if pod:                            # najmniejszy element z ostatniego zobacz pod punktem
                e = min(pod, key=lambda e: e["_ekran"][2] * e["_ekran"][3])
                return sx, sy, e, e["_acc"]
            return sx, sy, None, self.p.element_w_punkcie(sx, sy)
        raise Odmowa(f"podaj cel: `{klucz_numeru}` (numer z zobacz) albo `{klucz_xy}` [x, y] z obrazu")

    def _pilnuj_okna(self, sx: Optional[int] = None, sy: Optional[int] = None) -> None:
        w = self.p.okno_w_punkcie(sx, sy) if sx is not None else self.p.aktywne()
        powod = self.p.zakazane(w)
        if powod:
            raise Odmowa(powod)

    def _przed(self) -> dict:
        return {"mini": self.p.miniatura(), "okna": {w.get_xid(): w.get_name() for w in self.p._okna()},
                "aktywne": (self.p.aktywne().get_xid() if self.p.aktywne() else None)}

    def _paragon(self, przed: dict, co: str, czekaj: float = 1.5) -> str:
        time.sleep(0.3)                       # program dostał zdarzenia; rysuje zwykle w tym czasie
        koniec = time.monotonic() + czekaj
        poprz = self.p.miniatura()
        while time.monotonic() < koniec:      # aż ekran stanie (2 takie same miniatury) albo minie czas
            time.sleep(0.15)
            teraz = self.p.miniatura()
            if zmiana(poprz, teraz) < PROG_ZMIANY:
                break
            poprz = teraz
        po_okna = {w.get_xid(): w.get_name() for w in self.p._okna()}
        z = zmiana(przed["mini"], poprz)
        czesci = [f"ok {co}", "ekran: " + ("bez widocznej zmiany" if z < PROG_ZMIANY else f"zmiana {100 * z:.1f}%".replace(".", ","))]
        nowe = [t for x, t in po_okna.items() if x not in przed["okna"]]
        znikly = [t for x, t in przed["okna"].items() if x not in po_okna]
        if nowe:
            czesci.append("nowe okno: " + ", ".join(f"„{_napis(t, 50)}”" for t in nowe))
        if znikly:
            czesci.append("zamknięte: " + ", ".join(f"„{_napis(t, 50)}”" for t in znikly))
        a = self.p.aktywne()
        czesci.append(f"aktywne: „{_napis(a.get_name(), 60)}”" if a else "aktywne: brak")
        f = self.p.opis_fokusu()
        if f:
            czesci.append(f"fokus: {f}")
        if zmiana(przed["mini"], poprz) < PROG_ZMIANY and not nowe and not znikly:
            czesci.append("sprawdź zobacz, zanim powtórzysz")
        return " | ".join(czesci)

    # ---- akcje
    def zobacz(self, a: dict) -> dict:
        t0 = time.monotonic()
        maks = a.get("maks")
        maks = maks if isinstance(maks, int) and not isinstance(maks, bool) and 0 < maks <= MAKS_ELEMENTOW else DOMYSLNIE_ELEMENTOW
        w = self.p.aktywne()
        elementy = [] if a.get("elementy") is False else self.p.drzewo(w, maks)
        self.p.elementy = {e["n"]: e for e in elementy}
        t1 = time.monotonic()
        obszar = a.get("obszar")
        if obszar is not None and not (isinstance(obszar, list) and len(obszar) == 4
                                       and all(isinstance(v, (int, float)) for v in obszar)):
            raise Odmowa("obszar: [x, y, szerokość, wysokość] w pikselach obrazu")
        obraz, sz, wy = (None, 0, 0) if a.get("obraz") is False else self.p.zrzut(elementy, obszar, a.get("numery") is not False)
        okna = self.p._okna()
        linie = [f"pulpit {self.p.ekran}: obraz {self.p.szer_obr()}×{self.p.wys_obr()} (x,y jak na obrazie)"
                 + (f", powiększony obszar {obszar}" if obszar else ""),
                 "aktywne: " + (f"„{_napis(w.get_name(), 70)}” ({w.get_class_group_name()})" if w else "brak")]
        inne = [f"„{_napis(o.get_name(), 40)}”" for o in reversed(okna) if not o.is_active()][:8]
        if inne:
            linie.append("inne okna: " + ", ".join(inne))
        powod = self.p.zakazane(w)
        if powod:
            linie.append(f"UWAGA: {powod}")
        if elementy:
            linie.append(f"elementy aktywnego okna ({len(elementy)}" + (f", pominięto {self.p._ucieto}" if self.p._ucieto else "") + "):")
            linie += [linia_elementu(e) for e in elementy]
        elif a.get("elementy") is not False:
            linie.append("elementy: brak drzewa dostępności w tym oknie (płótno albo program bez AT-SPI): klikasz x,y z obrazu, "
                         "obszar powiększa fragment")
        return {"ok": True, "tekst": "\n".join(linie), "obraz": obraz, "szer": sz, "wys": wy,
                "czas_drzewa": round(t1 - t0, 3), "czas": round(time.monotonic() - t0, 3), "wezly": getattr(self.p, "_wezly", 0)}

    def klik(self, a: dict) -> dict:
        sx, sy, e, acc = self._cel(a)
        self._pilnuj_okna(sx, sy)
        sprawdz_klik(self.p.opis_dla_zasad(acc) if acc is not None else None)
        przycisk = {"lewy": 1, "prawy": 3, "srodkowy": 2, "środkowy": 2}.get(str(a.get("przycisk") or "lewy"), 1)
        razy = 2 if a.get("podwojny") is True else 1
        przed = self._przed()
        self.p.x.klik(sx, sy, przycisk, razy)
        cel = f"[{e['n']}] {rola_pl(e['rola'])} „{e['nazwa']}”" if e else f"{self.p.na_obraz(sx, sy)}"
        rodzaj = ("prawy " if przycisk == 3 else "") + ("podwójny " if razy == 2 else "")
        return {"ok": True, "tekst": self._paragon(przed, f"{rodzaj}klik {cel}")}

    def pisz(self, a: dict) -> dict:
        tekst = a.get("tekst")
        if not isinstance(tekst, str) or not tekst:
            raise Odmowa("pisz: podaj `tekst`")
        if len(tekst) > 5000:
            raise Odmowa("pisz: najwyżej 5000 znaków naraz; dłuższy tekst wklej z pliku programem albo w częściach")
        przed = self._przed()
        if a.get("numer") is not None or a.get("xy") is not None:
            sx, sy, e, acc = self._cel(a)
            self._pilnuj_okna(sx, sy)
            sprawdz_pisanie(tekst, self.p.opis_dla_zasad(acc) if acc is not None else None)
            self.p.x.klik(sx, sy)
            time.sleep(0.15)
        else:
            self._pilnuj_okna()
            acc = self.p.fokus()
            sprawdz_pisanie(tekst, self.p.opis_dla_zasad(acc) if acc is not None else None)
        if a.get("zamien") is True:
            self.p.x.klawisz(["Control_L"], ["a"])
            time.sleep(0.05)
        self.p.x.pisz(tekst)
        return {"ok": True, "tekst": self._paragon(przed, f"wpisane {len(tekst)} znaków")}

    def klawisz(self, a: dict) -> dict:
        mody, k = skrot(str(a.get("klawisz") or ""))
        razy = a.get("razy", 1)
        razy = razy if isinstance(razy, int) and not isinstance(razy, bool) and 1 <= razy <= 50 else 1
        self._pilnuj_okna()
        if k and k[0] in ("Return", "KP_Enter") and not mody:
            acc = self.p.fokus()
            if acc is not None:
                sprawdz_klik(self.p.opis_dla_zasad(acc))
        przed = self._przed()
        self.p.x.klawisz(mody, k, razy)
        return {"ok": True, "tekst": self._paragon(przed, f"klawisz {a.get('klawisz')}" + (f" ×{razy}" if razy > 1 else ""))}

    def przewin(self, a: dict) -> dict:
        kier = {"góra": "gora", "dół": "dol", "up": "gora", "down": "dol", "left": "lewo", "right": "prawo"}.get(
            str(a.get("kierunek") or "dol"), str(a.get("kierunek") or "dol"))
        if kier not in ("gora", "dol", "lewo", "prawo"):
            raise Odmowa("przewin: kierunek gora, dol, lewo albo prawo")
        ile = a.get("ile", 3)
        ile = ile if isinstance(ile, int) and not isinstance(ile, bool) and 1 <= ile <= 30 else 3
        if a.get("numer") is not None or a.get("xy") is not None:
            sx, sy, _, _ = self._cel(a)
        else:
            w = self.p.aktywne()
            if w is None:
                raise Odmowa("przewin: brak aktywnego okna; podaj numer albo xy")
            x, y, ww, hh = w.get_geometry()
            sx, sy = x + ww // 2, y + hh // 2
        self._pilnuj_okna(sx, sy)
        przed = self._przed()
        self.p.x.ruch(sx, sy)
        self.p.x.przewin(kier, ile)
        return {"ok": True, "tekst": self._paragon(przed, f"przewinięte {kier} ×{ile}")}

    def przeciagnij(self, a: dict) -> dict:
        sx, sy, e1, _ = self._cel(a, "numer", "xy")
        tx, ty, e2, _ = self._cel(a, "do_numer", "do_xy")
        self._pilnuj_okna(sx, sy)
        self._pilnuj_okna(tx, ty)
        przed = self._przed()
        self.p.x.przeciagnij((sx, sy), (tx, ty))
        return {"ok": True, "tekst": self._paragon(przed, f"przeciągnięte {self.p.na_obraz(sx, sy)} → {self.p.na_obraz(tx, ty)}")}

    def okna(self, a: dict) -> dict:
        linie = []
        for w in reversed(self.p._okna()):
            o = self.p.okno_opis(w)
            linie.append(f"{o['id']} „{_napis(o['tytul'], 70)}” {o['program']} @{o['x']},{o['y']} {o['szer']}×{o['wys']}"
                         + (" (aktywne)" if o["aktywne"] else "") + (" (zminimalizowane)" if o["zminimalizowane"] else ""))
        return {"ok": True, "tekst": "\n".join(linie) or "brak okien"}

    def aktywuj(self, a: dict) -> dict:
        w = self.p.znajdz_okno(a.get("okno"))
        powod = self.p.zakazane(w)
        if powod:
            raise Odmowa(powod)
        przed = self._przed()
        self.p.aktywuj(w)
        return {"ok": True, "tekst": self._paragon(przed, f"aktywuję „{_napis(w.get_name(), 60)}”", 0.6)}

    def zamknij(self, a: dict) -> dict:
        w = self.p.znajdz_okno(a.get("okno"))
        powod = self.p.zakazane(w)
        if powod:
            raise Odmowa(powod)
        przed = self._przed()
        w.close(self.p.czas_x())
        return {"ok": True, "tekst": self._paragon(przed, f"zamykam „{_napis(w.get_name(), 60)}” (pytanie o zapis "
                                                         "zostaje oknem, odpowiedz w nim)", 1.5)}

    def uruchom(self, a: dict) -> dict:
        nazwa = str(a.get("program") or "").strip().lower()
        polecenie = a.get("polecenie")             # kdenlive, inkscape: pełna ścieżka od wtyczki
        if nazwa in ZEWNETRZNE:
            if not (isinstance(polecenie, list) and polecenie and all(isinstance(x, str) for x in polecenie)):
                raise Odmowa(f"{nazwa}: brak programu z manifestu")
            cmd = list(polecenie)
        elif nazwa in PROGRAMY:
            cmd = list(PROGRAMY[nazwa])
        else:
            raise Odmowa(f"nie znam programu „{nazwa}”; są: {', '.join(sorted([*PROGRAMY, *ZEWNETRZNE]))}")
        argumenty = a.get("argumenty") or []
        if not isinstance(argumenty, list) or not all(isinstance(x, str) for x in argumenty):
            raise Odmowa("argumenty: lista napisów (pliki do otwarcia albo adres)")
        for x in argumenty:
            if x.startswith("-"):
                raise Odmowa(f"argument „{x}”: tylko pliki i adresy, bez opcji programu")
        env = {**os.environ, **OTOCZENIE_A11Y, "DISPLAY": self.p.ekran}
        if appimage(cmd[0]) and not any(Path(p).exists() for p in (
                "/usr/lib/x86_64-linux-gnu/libfuse.so.2", "/lib/x86_64-linux-gnu/libfuse.so.2", "/usr/lib64/libfuse.so.2")):
            env["APPIMAGE_EXTRACT_AND_RUN"] = "1"      # bez FUSE 2: AppImage rozpakowuje się do /tmp przy starcie
        self.sprzataj()
        przed = self._przed()
        dziennik = Path(os.environ.get("JARVO_PULPIT_LOGI") or "/tmp") / f"pulpit-{nazwa}.log"
        try:
            with open(dziennik, "ab") as log:
                proc = subprocess.Popen(cmd + argumenty, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env,
                                        start_new_session=True, cwd=str(Path.home()))
        except OSError as e:
            raise Odmowa(f"{nazwa} się nie uruchomił: {e}")
        sekundy = a.get("sekundy", 60)
        sekundy = sekundy if isinstance(sekundy, (int, float)) and not isinstance(sekundy, bool) and 1 <= sekundy <= 180 else 60
        koniec, nowe = time.monotonic() + sekundy, None
        while time.monotonic() < koniec:
            time.sleep(0.4)
            okna = [w for w in self.p._okna() if w.get_xid() not in przed["okna"]]
            if okna:
                nowe = next((w for w in okna if w.get_pid() == proc.pid), okna[-1])
                time.sleep(0.8)              # program jeszcze rysuje okno (GIMP najpierw pokazuje ekran startowy)
                okna = [w for w in self.p._okna() if w.get_xid() not in przed["okna"]]
                nowe = next((w for w in reversed(okna) if w.get_window_type() == self.p.Wnck.WindowType.NORMAL), okna[-1] if okna else nowe)
                break
            if proc.poll() not in (None, 0):
                raise Odmowa(f"{nazwa} zakończył się kodem {proc.returncode} bez okna (dziennik: {dziennik})")
        if nowe is None:
            return {"ok": True, "tekst": f"{nazwa} uruchomiony (pid {proc.pid}), ale okno nie pojawiło się w {sekundy:g} s: "
                                          "czekaj okno albo zobacz"}
        self.p.aktywuj(nowe)
        return {"ok": True, "tekst": self._paragon(przed, f"uruchomiony {nazwa}", 2.0)}

    def czekaj(self, a: dict) -> dict:
        sekundy = a.get("sekundy", 10)
        sekundy = sekundy if isinstance(sekundy, (int, float)) and not isinstance(sekundy, bool) and 0 < sekundy <= 60 else 10
        tekst, okno, zniknie = a.get("tekst"), a.get("okno"), a.get("zniknie") is True
        start = time.monotonic()
        poprz = self.p.miniatura() if not (tekst or okno) else None
        while True:
            if okno:
                tytuly = [w.get_name() or "" for w in self.p._okna()]
                jest = any(str(okno).lower() in t.lower() for t in tytuly)
            elif tekst:
                w = self.p.aktywne()
                jest = str(tekst).lower() in (self.p.teksty(w) + "\n" + (w.get_name() if w else "")).lower()
            else:                              # ekran stabilny: dwie miniatury co 0,5 s bez zmiany
                time.sleep(0.5)
                teraz = self.p.miniatura()
                jest, poprz = zmiana(poprz, teraz) < PROG_ZMIANY, teraz
                zniknie = False
            if jest != zniknie:
                a_ = self.p.aktywne()
                co = f"okno „{okno}”" if okno else (f"tekst „{tekst}”" if tekst else "ekran stoi")
                return {"ok": True, "tekst": f"spełnione po {time.monotonic() - start:.1f} s: {co}"
                                             + (" zniknął" if zniknie else "")
                                             + f" | aktywne: „{_napis(a_.get_name(), 60) if a_ else ''}”"}
            if time.monotonic() - start >= sekundy:
                return {"ok": False, "blad": f"czas minął ({sekundy:g} s), warunek niespełniony: zrób zobacz"}
            time.sleep(0.35)

    AKCJE = ("zobacz", "klik", "pisz", "klawisz", "przewin", "przeciagnij", "okna", "aktywuj", "zamknij", "uruchom", "czekaj")

    def kroki(self, a: dict) -> dict:
        kroki = a.get("kroki")
        if not isinstance(kroki, list) or not kroki or len(kroki) > 20:
            raise Odmowa("kroki: lista 1–20 działań, np. [{\"akcja\": \"klik\", \"numer\": 4}, {\"akcja\": \"pisz\", \"tekst\": \"…\"}]")
        linie = []
        for i, k in enumerate(kroki, 1):
            akcja = k.get("akcja") if isinstance(k, dict) else None
            if akcja not in self.AKCJE or akcja in ("zobacz", "kroki"):
                linie.append(f"{i}. ODMOWA: krok bez dozwolonej akcji (klik, pisz, klawisz, przewin, przeciagnij, "
                             "okna, aktywuj, zamknij, uruchom, czekaj); paczka stoi")
                break
            try:
                w = getattr(self, akcja)(k)
            except Odmowa as e:
                linie.append(f"{i}. ODMOWA {akcja}: {e}; paczka stoi")
                break
            linie.append(f"{i}. " + (w["tekst"] if w.get("ok") else f"BŁĄD {akcja}: {w.get('blad')}; paczka stoi"))
            if not w.get("ok"):
                break
        wynik = {"ok": True, "tekst": "\n".join(linie)}
        if a.get("zobacz_po") is True:
            z = self.zobacz({"maks": a.get("maks")})
            wynik.update(obraz=z["obraz"], szer=z["szer"], wys=z["wys"], tekst=wynik["tekst"] + "\n\n" + z["tekst"])
        return wynik

    def stan(self, a: dict) -> dict:
        return {"ok": True, "tekst": f"pulpit {self.p.ekran} {self.p.w}×{self.p.h}, obraz {self.p.szer_obr()}×{self.p.wys_obr()}, "
                                     f"okien: {len(self.p._okna())}"}

    def obsluz(self, a: dict) -> dict:
        akcja = a.get("akcja")
        if akcja not in (*self.AKCJE, "kroki", "stan"):
            return {"ok": False, "blad": "akcja: " + ", ".join([*self.AKCJE, "kroki"])}
        try:
            return getattr(self, akcja)(a)
        except Odmowa as e:
            return {"ok": False, "odmowa": True, "blad": str(e)}


def main() -> int:
    ekran = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DISPLAY", ":0")
    try:
        s = Silnik(ekran)
        gotowy = {"ok": True, "gotowy": True, "szer": s.p.w, "wys": s.p.h}
    except Exception as e:  # noqa: BLE001
        s, gotowy = None, {"ok": False, "gotowy": False, "blad": f"pulpit niedostępny: {e}"}
    sys.stdout.write(json.dumps(gotowy, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    if s is None:
        return 1
    for linia in sys.stdin:
        try:
            pol = json.loads(linia)
        except ValueError:
            continue
        try:
            odp = s.obsluz(pol.get("argumenty") or {})
        except Exception as e:  # noqa: BLE001 - błąd jednego polecenia nie kończy silnika
            odp = {"ok": False, "blad": f"{type(e).__name__}: {e}"}
        odp["id"] = pol.get("id")
        sys.stdout.write(json.dumps(odp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
