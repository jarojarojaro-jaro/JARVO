"""Okna X11 pulpitu Komputera Jarva (docs/KOMPUTER.md §6): gdzie naprawdę trafi kliknięcie w punkt.

wejscie.py pyta tu o położenie okna na ekranie (to samo XTranslateCoordinates, którego używa sterownik przy kliknięciu
w punkt okna) i o to, które okno leży na wierzchu w punkcie ekranu. Bez nowych zależności: libX11 z obrazu przez
ctypes. Każde połączenie z serwerem X jest osobne i krótkie (pod blokadą), a błędy X (okno zniknęło) dają None,
nigdy wyjście procesu: obsługa błędów Xlib domyślnie kończy program.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import threading

Okno = ctypes.c_ulong
MAPA_WIDOCZNE = 2                     # IsViewable


class _Atrybuty(ctypes.Structure):    # XWindowAttributes (Xlib.h)
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("width", ctypes.c_int), ("height", ctypes.c_int),
                ("border_width", ctypes.c_int), ("depth", ctypes.c_int), ("visual", ctypes.c_void_p),
                ("root", Okno), ("class_", ctypes.c_int), ("bit_gravity", ctypes.c_int),
                ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong), ("save_under", ctypes.c_int),
                ("colormap", ctypes.c_ulong), ("map_installed", ctypes.c_int), ("map_state", ctypes.c_int),
                ("all_event_masks", ctypes.c_long), ("your_event_mask", ctypes.c_long),
                ("do_not_propagate_mask", ctypes.c_long), ("override_redirect", ctypes.c_int),
                ("screen", ctypes.c_void_p)]


_OBSLUGA_BLEDU = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)


class X11:
    """Zapytania o okna pulpitu (DISPLAY i XAUTHORITY ze środowiska pulpitu). Bez libX11 albo serwera X: None."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._x = None
        try:
            x = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "libX11.so.6")
        except OSError:
            return
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x.XDefaultRootWindow.restype = Okno
        x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x.XQueryTree.argtypes = [ctypes.c_void_p, Okno, ctypes.POINTER(Okno), ctypes.POINTER(Okno),
                                 ctypes.POINTER(ctypes.POINTER(Okno)), ctypes.POINTER(ctypes.c_uint)]
        x.XGetWindowAttributes.argtypes = [ctypes.c_void_p, Okno, ctypes.POINTER(_Atrybuty)]
        x.XTranslateCoordinates.argtypes = [ctypes.c_void_p, Okno, Okno, ctypes.c_int, ctypes.c_int,
                                            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
                                            ctypes.POINTER(Okno)]
        x.XFree.argtypes = [ctypes.c_void_p]
        self._blad = False
        self._obsluga = _OBSLUGA_BLEDU(self._na_blad)   # referencja żyje z obiektem (inaczej ctypes ją zwolni)
        x.XSetErrorHandler(self._obsluga)
        self._x = x

    def _na_blad(self, _display, _zdarzenie) -> int:
        self._blad = True
        return 0

    def _zapytaj(self, fn):
        if self._x is None:
            return None
        with self._lock:
            d = self._x.XOpenDisplay(None)
            if not d:
                return None
            self._blad = False
            try:
                wynik = fn(self._x, d, self._x.XDefaultRootWindow(d))
                return None if self._blad else wynik
            finally:
                self._x.XCloseDisplay(d)

    @staticmethod
    def _drzewo(x, d, okno: int) -> tuple[int, list[int]] | None:
        """(rodzic, dzieci od spodu do wierzchu) albo None."""
        korzen, rodzic, dzieci, n = Okno(), Okno(), ctypes.POINTER(Okno)(), ctypes.c_uint()
        if not x.XQueryTree(d, okno, ctypes.byref(korzen), ctypes.byref(rodzic), ctypes.byref(dzieci),
                            ctypes.byref(n)):
            return None
        lista = [dzieci[i] for i in range(n.value)]
        if dzieci:
            x.XFree(dzieci)
        return rodzic.value, lista

    def geometria(self, okno: int) -> tuple[int, int, int, int] | None:
        """(x, y, szerokość, wysokość) okna na ekranie: początek okna tak, jak liczy go sterownik."""
        def fn(x, d, root):
            a = _Atrybuty()
            if not x.XGetWindowAttributes(d, okno, ctypes.byref(a)):
                return None
            gx, gy, dziecko = ctypes.c_int(), ctypes.c_int(), Okno()
            if not x.XTranslateCoordinates(d, okno, root, 0, 0, ctypes.byref(gx), ctypes.byref(gy),
                                           ctypes.byref(dziecko)):
                return None
            return gx.value, gy.value, a.width, a.height
        return self._zapytaj(fn)

    def ekran(self) -> tuple[int, int] | None:
        """Rozmiar ekranu (okno główne)."""
        def fn(x, d, root):
            a = _Atrybuty()
            return (a.width, a.height) if x.XGetWindowAttributes(d, root, ctypes.byref(a)) else None
        return self._zapytaj(fn)

    def na_wierzchu(self, px: float, py: float, okno: int) -> bool | None:
        """Czy kliknięcie w punkcie ekranu dostanie okno najwyższego poziomu zawierające `okno` (ramka menedżera
        okien z klientem). Okno w punkcie wskazuje serwer X (XTranslateCoordinates z okna głównego): najwyższe
        widoczne, które przyjmuje wskaźnik, więc nakładka sterownika z kursorem agenta, przezroczysta dla
        kliknięć, nie przesłania celu. False, gdy kliknięcie dostałoby inne okno albo okienko podręczne (lista,
        menu, podpowiedź przeglądarki: override-redirect); None, gdy nie da się tego sprawdzić."""
        def fn(x, d, root):
            szczyt, nast = okno, okno
            for _ in range(64):              # przodek okna, którego rodzicem jest okno główne
                drzewo = self._drzewo(x, d, nast)
                if drzewo is None:
                    return None
                if drzewo[0] == root:
                    szczyt = nast
                    break
                nast = drzewo[0]
            else:
                return None
            gx, gy, w_punkcie = ctypes.c_int(), ctypes.c_int(), Okno()
            if not x.XTranslateCoordinates(d, root, root, int(px), int(py), ctypes.byref(gx), ctypes.byref(gy),
                                           ctypes.byref(w_punkcie)):
                return None
            if w_punkcie.value != szczyt:
                return False
            a = _Atrybuty()
            if not x.XGetWindowAttributes(d, szczyt, ctypes.byref(a)):
                return None
            return a.map_state == MAPA_WIDOCZNE and not a.override_redirect
        return self._zapytaj(fn)
