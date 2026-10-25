"""Sterownik ekranu przeglądarki Jarva przez CDP (docs/NATYWNIE.md J02): ten sam MCP co cua-driver.

Hermes (computer_use) i bramka `komputer/jarvo_cua.py` rozmawiają z nim jak z `cua-driver mcp`: te same nazwy
narzędzi i argumentów, `structuredContent.elements` z `element_index`, `parent_index`, `depth`, `role`, `label`,
`frame` i `element_token` (`<snapshot_id>:<numer>`), obraz zrzutu jako część `image`, a wynik działania z `effect`
(`confirmed` albo `unverifiable`) i `path: cdp`. Okno = karta przeglądarki (window_id to numer karty), pid = proces
przeglądarki, aplikacja nazywa się „Chromium” (zasady.py: uruchamiamy tylko Chromium).

Role z drzewa dostępności Chromium (Accessibility.getFullAXTree) zamieniamy na słownik zasad (role AT-SPI z kontenera:
`push button`, `entry`, `password text`, `form`, `document web`…), a pole hasła rozpoznajemy po atrybucie `type`
z DOMSnapshot (w drzewie dostępności to zwykły `textbox`). Ramki z tej samej domeny i ramki z innych procesów (OOPIF,
np. formularz płatności w ramce) trafiają do jednej migawki z przesunięciem do układu okna.

Dla twardych zasad (wejscie_natywne.KontekstCDP) sterownik opisuje element na żywo: rola, nazwa, atrybuty HTML,
przodkowie, czy pole leży w formularzu i jakie ma on przyciski (Accessibility.queryAXTree), element w punkcie
(DOM.getNodeForLocation, prawdziwe trafienie silnika strony) i pole z fokusem (document.activeElement w odizolowanym
świecie, przez ramki i shadow DOM). Klik elementem trafia w środek jego prostokąta tylko wtedy, gdy w tym punkcie leży
ten element albo jego potomek (inaczej odmowa `element_przesloniety`: baner albo okienko nad przyciskiem).

Okna przeglądarki JavaScript (alert, confirm, prompt, beforeunload) są w migawce oknem `dialog` z przyciskami OK
i Anuluj; wybór pliku w trybie w tle jest przechwycony (Page.setInterceptFileChooserDialog) i robi go człowiek.

Pisanie sprawdza fokus jeszcze raz tuż przed wpisaniem (`fokus_zmieniony`): pole z fokusem musi być tym, które
oceniły twarde zasady, a po kliknięciu w cel fokus musi leżeć w tym celu (skrypt strony, który na kliknięcie
przenosi fokus do pola hasła, nie dostanie tekstu).

Podgląd dla HQ (J10): Page.startScreencast aktywnej karty (JPEG), ostatnia klatka dla `podglad()`; podgląd staje sam
po PODGLAD_BEZCZYNNOSC s bez pytań. „Przejmij” w HQ: `wejscie_wlasciciela()` wysyła mysz, kółko, klawisze, tekst,
adres, odpowiedź w oknie JavaScript i plik z katalogu `wysylane` wprost do aktywnej karty przez CDP Input.*, bez
twardych zasad; wejście natywne przepuszcza je tylko z tokenem właściciela i przy jego pauzie.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import secrets
import struct
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus, urlsplit

from . import cdp, przegladarka

WERSJA = "0.21.0"                  # kontrakt cua-driver, który przyjmuje Hermes (≥ 0.20), bramka podaje tę samą
APLIKACJA = "Chromium"
MAKS_ELEMENTOW = 2000              # jak domyślny limit przejścia drzewa cua-driver
MAKS_RAMEK = 20
MAKS_MIGAWEK = 32
MAKS_NAPIS = 300
CZAS_WEJSCIA = 10.0
CZAS_FOKUSU = 10.0                 # s: tyle ważna jest ocena pola z fokusem przez zasady (sprawdzenie przy pisaniu)
PODGLAD_JAKOSC = 60                # JPEG klatek podglądu
PODGLAD_MAKS = 1280                # px dłuższego boku klatki podglądu
PODGLAD_BEZCZYNNOSC = 20.0         # s bez pytania o klatkę: screencast staje (nie zużywa procesora bez widza)
MAKS_TEKST_WLASCICIELA = 4000
MAKS_PLIKOW = 10
# strona testowa (usługa z --strona-testowa): dwie witryny, żeby ramka płatności była z innego procesu (OOPIF)
DOMENA_TESTOWA = re.compile(r"^https://(?:(?:[a-z0-9-]+\.)*jarvo\.test|jarvo-platnosci\.test)(?::\d+)?/", re.I)
WZORCE_TESTOWE = ("https://*.jarvo.test/*", "https://jarvo-platnosci.test/*")
SCHEMATY_ZAKAZANE = ("file:", "chrome:", "chrome-untrusted:", "devtools:", "view-source:", "chrome-extension:",
                     "chrome-search:", "edge:")
INSTRUKCJE = ("Przeglądarka Jarva (Chromium) sterowana przez CDP: okno to karta przeglądarki, elementy z drzewa "
              "dostępności strony. Klikaj elementem (element_token z get_window_state). Adres strony: klik w element "
              "„Pasek adresu i wyszukiwania” (numer 0), type z adresem, key return.")
# Pasek adresu karty: drzewo dostępności CDP zawiera tylko stronę, więc sterownik dokłada pasek jako element 0 z tą
# samą nazwą co w Chromium z pulpitu (skill praca-na-ekranie: klik w pasek, type z adresem, key return)
PASEK = "Pasek adresu i wyszukiwania"
WYSZUKIWARKA = "https://www.google.com/search?q="          # jak domyślny silnik Chromium dla tekstu bez adresu

# Role drzewa dostępności Chromium (CDP) → słownik zasad (role AT-SPI z kontenera, infra/komputer/zasady.py).
ROLE = {
    "rootwebarea": "document web", "webarea": "document web", "button": "push button",
    "popupbutton": "push button", "togglebutton": "toggle button", "link": "link", "textbox": "entry",
    "searchbox": "entry", "textfield": "entry", "textfieldwithcombobox": "combo box", "combobox": "combo box",
    "combo box select": "combo box", "listbox": "list box", "option": "list item", "listboxoption": "list item",
    "menulistoption": "list item", "menulistpopup": "menu", "checkbox": "check box", "radio": "radio button",
    "radiobutton": "radio button", "switch": "toggle button", "slider": "slider", "spinbutton": "spin button",
    "menuitem": "menu item", "menuitemcheckbox": "check menu item", "menuitemradio": "radio menu item",
    "menu": "menu", "menubar": "menu bar", "tab": "page tab", "tablist": "page tab list", "tabpanel": "panel",
    "form": "form", "dialog": "dialog", "alertdialog": "alert", "alert": "alert", "heading": "heading",
    "paragraph": "paragraph", "img": "image", "image": "image", "figure": "image", "iframe": "internal frame",
    "iframepresentational": "internal frame", "table": "table", "grid": "table", "treegrid": "tree table",
    "row": "table row", "cell": "table cell", "gridcell": "table cell", "columnheader": "table column header",
    "rowheader": "table row header", "list": "list", "listitem": "list item", "tree": "tree",
    "treeitem": "tree item", "navigation": "landmark", "main": "landmark", "banner": "landmark",
    "contentinfo": "landmark", "complementary": "landmark", "region": "landmark", "search": "landmark",
    "article": "article", "blockquote": "block quote", "progressindicator": "progress bar",
    "meter": "level bar", "statictext": "static", "labeltext": "label", "status": "status bar",
    "tooltip": "tool tip", "separator": "separator", "toolbar": "tool bar", "group": "panel",
    "definition": "definition", "term": "description term", "code": "static", "math": "math",
}
POMIJANE = frozenset({"generic", "none", "presentation", "inlinetextbox", "linebreak", "labeltext", "ignored",
                      "genericcontainer", "section", "div", "span", "unknown", "abbr", "time", "mark", "strong",
                      "emphasis", "subscript", "superscript", "insertion", "deletion", "ruby"})
INTERAKTYWNE = frozenset({"push button", "toggle button", "link", "entry", "password text", "combo box", "list box",
                          "list item", "check box", "radio button", "slider", "spin button", "menu item",
                          "check menu item", "radio menu item", "page tab", "tree item"})
TEKSTOWE = frozenset({"paragraph", "heading", "table cell", "table column header", "table row header",
                      "list item", "label", "block quote", "description term", "definition", "status bar",
                      "tool tip", "alert", "article"})

# Klawisze: nazwa (jak w cua-driver i xdotool) → (key, code, windowsVirtualKeyCode, tekst)
KLAWISZE = {
    "return": ("Enter", "Enter", 13, "\r"), "enter": ("Enter", "Enter", 13, "\r"),
    "kp_enter": ("Enter", "NumpadEnter", 13, "\r"), "tab": ("Tab", "Tab", 9, None),
    "escape": ("Escape", "Escape", 27, None), "esc": ("Escape", "Escape", 27, None),
    "backspace": ("Backspace", "Backspace", 8, None), "delete": ("Delete", "Delete", 46, None),
    "space": (" ", "Space", 32, " "), "kp_space": (" ", "Space", 32, " "),
    "up": ("ArrowUp", "ArrowUp", 38, None), "down": ("ArrowDown", "ArrowDown", 40, None),
    "left": ("ArrowLeft", "ArrowLeft", 37, None), "right": ("ArrowRight", "ArrowRight", 39, None),
    "home": ("Home", "Home", 36, None), "end": ("End", "End", 35, None),
    "page_up": ("PageUp", "PageUp", 33, None), "pageup": ("PageUp", "PageUp", 33, None),
    "prior": ("PageUp", "PageUp", 33, None), "page_down": ("PageDown", "PageDown", 34, None),
    "pagedown": ("PageDown", "PageDown", 34, None), "next": ("PageDown", "PageDown", 34, None),
    "insert": ("Insert", "Insert", 45, None),
    **{f"f{i}": (f"F{i}", f"F{i}", 111 + i, None) for i in range(1, 13)},
}
AKTYWUJACE = frozenset({"return", "enter", "kp_enter", "iso_enter", "space", "kp_space", " "})   # jak zasady.py
DZIALANIA_AGENTA = frozenset({"click", "double_click", "right_click", "drag", "scroll", "type_text", "press_key",
                              "hotkey", "set_value"})
MODYFIKATORY = {"alt": (1, "Alt", "AltLeft", 18), "option": (1, "Alt", "AltLeft", 18),
                "ctrl": (2, "Control", "ControlLeft", 17), "control": (2, "Control", "ControlLeft", 17),
                "cmd": (4, "Meta", "MetaLeft", 91), "command": (4, "Meta", "MetaLeft", 91),
                "meta": (4, "Meta", "MetaLeft", 91), "super": (4, "Meta", "MetaLeft", 91),
                "win": (4, "Meta", "MetaLeft", 91), "shift": (8, "Shift", "ShiftLeft", 16)}
UPRAWNIENIA_ODMOWA = ("geolocation", "notifications", "camera", "microphone", "clipboard-read", "clipboard-write",
                      "display-capture", "midi", "idle-detection", "window-management", "local-fonts",
                      "accelerometer", "gyroscope", "magnetometer", "ambient-light-sensor", "background-sync",
                      "payment-handler", "nfc", "screen-wake-lock", "storage-access", "keyboard-lock",
                      "pointer-lock", "captured-surface-control", "speaker-selection")

# JavaScript w odizolowanym świecie (strona go nie widzi ani nie podmieni). Opis elementu dla zasad.
JS_OPIS = """function(){
  const e = this, t = (e.tagName || '').toLowerCase(), a = n => (e.getAttribute && e.getAttribute(n)) || '';
  const f = e.form || (e.closest && e.closest('form'));
  return {tag: t, typ: (a('type') || (t === 'input' ? 'text' : '')).toLowerCase(), nazwa: a('name'),
    autocomplete: a('autocomplete'), placeholder: a('placeholder'), edytowalny: !!e.isContentEditable,
    wieloliniowy: t === 'textarea' || (!!e.isContentEditable && t !== 'input'), plik: t === 'input' && a('type').toLowerCase() === 'file',
    formularz: !!f, wartosc: ('value' in e && t !== 'button') ? String(e.value).slice(0, 200) : null};
}"""
JS_FORMULARZ = "function(){ return this.form || (this.closest && this.closest('form')) || null; }"
JS_FOKUS = """function(){
  let e = document.activeElement;
  for (let i = 0; i < 32 && e && e.shadowRoot && e.shadowRoot.activeElement; i++) e = e.shadowRoot.activeElement;
  if (!e || e === document.body || e === document.documentElement) return null;
  return e;
}"""
JS_ZAWIERA = """function(h){ for (let n = h, i = 0; n && i < 4096; i++) { if (n === this) return true;
  n = n.parentNode || (n.host || null); } return false; }"""
JS_WARTOSC = """function(v){
  const e = this, t = (e.tagName || '').toLowerCase();
  if (t === 'select') {
    const o = [...e.options].find(o => o.value === v || o.text.trim() === String(v).trim());
    if (!o) return {ok: false, powod: 'nie ma takiej opcji'};
    e.value = o.value;
  } else if ('value' in e && t !== 'button') {
    const d = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e), 'value');
    if (d && d.set) d.set.call(e, v); else e.value = v;
  } else return {ok: false, powod: 'element bez wartości'};
  e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true}));
  return {ok: true, wartosc: t === 'select' ? e.options[e.selectedIndex].text : String(e.value).slice(0, 200)};
}"""
JS_WARTOSC_FOKUSU = """function(){ const e = this; return ('value' in e) ? String(e.value).slice(-400)
  : (e.isContentEditable ? String(e.innerText).slice(-400) : null); }"""


class BladSterownika(RuntimeError):
    def __init__(self, kod: str, tekst: str):
        super().__init__(tekst)
        self.kod, self.tekst = kod, tekst


def _wynik(tekst: str, **sc: Any) -> dict:
    return {"content": [{"type": "text", "text": tekst}], "structuredContent": {"ok": True, "message": tekst, **sc},
            "isError": False}


def _blad(kod: str, tekst: str) -> dict:
    return {"content": [{"type": "text", "text": tekst}], "isError": True,
            "structuredContent": {"ok": False, "code": kod, "message": tekst}}


def _rozmiar_png(dane: bytes) -> tuple[int, int]:
    if dane[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", dane[16:24])
    return 0, 0


def _napis(tekst) -> str:
    """Nazwa z drzewa dostępności bez nadmiarowych spacji (etykieta <label> kończy się spacją)."""
    return " ".join(str(tekst or "").split())


def adres_z_paska(tekst: str) -> str | None:
    """Adres, pod który przechodzi pasek adresu: http(s) bez zmian, sam serwer z https://, tekst bez adresu jako
    wyszukiwanie; inne schematy (javascript:, file:, chrome:, data:…) None."""
    t = " ".join(str(tekst or "").split())
    if not t:
        return None
    schemat = re.match(r"^([a-z][a-z0-9+.-]*):(?!\d)", t, re.I)
    if schemat:
        return t if schemat.group(1).lower() in ("http", "https") and urlsplit(t).netloc else None
    if " " not in t and re.match(r"^(?:localhost|\[[0-9a-f:]+\]|[^\s/?#]+\.[^\s/?#]+)(?::\d+)?(?:[/?#].*)?$", t, re.I):
        return "https://" + t
    return WYSZUKIWARKA + quote_plus(t)


def rola_zasad(rola_cdp: str, typ: str = "") -> str:
    """Rola z drzewa dostępności Chromium w słowniku zasad; pole typu password to `password text`."""
    r = (rola_cdp or "").strip().lower()
    if r in ("textbox", "searchbox", "textfield") and typ == "password":
        return "password text"
    return ROLE.get(r, r)


class Okno:
    """Karta przeglądarki (cel CDP typu page)."""

    def __init__(self, nr: int, target_id: str, sesja: str):
        self.nr, self.target_id, self.sesja = nr, target_id, sesja
        self.tytul = self.url = ""
        self.dialog: dict | None = None
        self.wybor_pliku: dict | None = None        # wybór pliku otwarty przez ostatnie działanie agenta
        self.wybor_wlasciciela: dict | None = None  # ostatni wybór pliku (sesja, węzeł): wypełnia go właściciel
        self.fokus_oceniony: tuple | None = None    # (element z fokusem, czas) z ostatniej oceny zasad
        self.pasek: str | None = None               # tekst paska adresu z fokusem (None: fokus na stronie)
        self.ramki: dict[str, str] = {}             # frameId ramki z innego procesu (OOPIF) -> sesja CDP
        self.skala = 1.0                            # piksele zrzutu na piksel CSS (ostatni zrzut tej karty)
        self.rozmiar = przegladarka.EKRAN           # obszar strony w pikselach CSS
        self.zmierzone = False
        self.swiaty: dict[tuple, int] = {}          # (sesja, frameId) -> kontekst odizolowanego świata
        self.utworzone = time.monotonic()
        self.trafienia: dict[tuple, tuple] = {}     # (x, y) -> (czas, sesja, backendNodeId) z oceny zasad


class Sterownik:
    """Narzędzia MCP sterownika na jednej przeglądarce (cdp.Przegladarka)."""

    def __init__(self, przegl: cdp.Przegladarka, *, pobrane: Path, w_tle: bool = True,
                 strona_testowa: Path | None = None, log: Callable[[str], None] | None = None,
                 wysylane: Path | None = None):
        self.b = przegl
        self.pobrane = Path(pobrane)
        self.w_toku = self.pobrane / ".w-toku"
        # pliki, które właściciel wybiera dla strony (HQ zapisuje je tutaj): tylko z tego katalogu, nie z całego dysku
        self.wysylane = Path(wysylane) if wysylane else self.pobrane.parent / "wysylane"
        self.w_tle = w_tle
        self.strona_testowa = Path(strona_testowa) if strona_testowa else None
        self.log = log or (lambda _t: None)
        self._lock = threading.RLock()
        self._okna: dict[int, Okno] = {}
        self._po_celu: dict[str, int] = {}
        self._sesje_ramek: dict[str, tuple[int, str]] = {}   # sesja ramki OOPIF -> (nr okna, frameId)
        self._nr = 0
        self._aktywne: int | None = None
        self._migawki: OrderedDict[str, dict] = OrderedDict()
        self._pobrania: dict[str, dict] = {}
        self.statystyki = {"pobrane": 0, "odrzucone": 0, "nawigacje_zablokowane": 0, "wejscie_wlasciciela": 0}
        self._nowe_okno = threading.Condition(self._lock)
        self.ua: str | None = None
        # podgląd (Page.startScreencast): karta, ostatnia klatka i jej numer, czas ostatniego pytania
        self._podglad: dict[str, Any] = {"okno": None, "klatka": None, "nr": 0, "pytanie": 0.0,
                                         "jakosc": PODGLAD_JAKOSC, "maks": PODGLAD_MAKS}
        self._podglad_zmiana = threading.Condition()

    # ------------------------------------------------------------------ przygotowanie

    def start(self) -> None:
        self.w_toku.mkdir(parents=True, exist_ok=True)
        self.b.sluchaj(self._zdarzenie)
        wersja = self.b.wyslij("Browser.getVersion")
        self.ua = str(wersja.get("userAgent") or "")
        self.produkt = str(wersja.get("product") or "")
        self.b.wyslij("Target.setDiscoverTargets", {"discover": True})
        self.b.wyslij("Browser.setDownloadBehavior", {"behavior": "allowAndName", "downloadPath": str(self.w_toku),
                                                      "eventsEnabled": True})
        for nazwa in UPRAWNIENIA_ODMOWA:
            try:
                self.b.wyslij("Browser.setPermission", {"permission": {"name": nazwa}, "setting": "denied"}, czas=5)
            except cdp.BladCDP:
                pass                                 # nazwy nieznane tej wersji przeglądarki
        self.b.wyslij("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True})
        koniec = time.monotonic() + 10
        with self._lock:
            while not self._okna and time.monotonic() < koniec:
                self._nowe_okno.wait(0.2)

    def _wzorce_fetch(self) -> list[dict]:
        wzorce = [{"urlPattern": "file://*"}]
        if self.strona_testowa is not None:
            wzorce += [{"urlPattern": w} for w in WZORCE_TESTOWE]
        return wzorce

    def _przygotuj_cel(self, sesja: str, info: dict, rodzic: str | None) -> None:
        typ = info.get("type")
        polecenia = [("Fetch.enable", {"patterns": self._wzorce_fetch()}), ("Page.enable", {}),
                     ("Page.setInterceptFileChooserDialog", {"enabled": self.w_tle}),
                     ("Accessibility.enable", {}),
                     ("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True})]
        if typ == "page" and self.ua and "HeadlessChrome" in self.ua:
            polecenia.append(("Emulation.setUserAgentOverride", {"userAgent": self.ua.replace("HeadlessChrome",
                                                                                              "Chrome")}))
        oczekiwania = []
        for metoda, params in polecenia:
            try:
                oczekiwania.append(self.b.nadaj(metoda, params, sesja))
            except cdp.BladCDP:
                return
        try:
            self.b.nadaj("Runtime.runIfWaitingForDebugger", {}, sesja)
        except cdp.BladCDP:
            return
        for o in oczekiwania:
            try:
                o.wynik(15)
            except cdp.BladCDP as e:
                self.log(f"sterownik: {o.metoda} dla {typ}: {e.tekst[:120]}")

    # ------------------------------------------------------------------ zdarzenia CDP

    def _zdarzenie(self, metoda: str, p: dict, sesja: str | None) -> None:
        if metoda == "Target.attachedToTarget":
            self._dolaczony(p, sesja)
        elif metoda == "Target.detachedFromTarget":
            self._odlaczony(p.get("sessionId"))
        elif metoda == "Target.targetInfoChanged":
            info = p.get("targetInfo") or {}
            with self._lock:
                nr = self._po_celu.get(info.get("targetId"))
                if nr in self._okna:
                    self._okna[nr].tytul = str(info.get("title") or "")
                    self._okna[nr].url = str(info.get("url") or "")
        elif metoda == "Page.javascriptDialogOpening":
            okno = self._okno_sesji(sesja)
            if okno is not None:
                okno.dialog = {"typ": str(p.get("type") or "alert"), "wiadomosc": str(p.get("message") or ""),
                               "domyslny": str(p.get("defaultPrompt") or ""), "tekst": None, "sesja": sesja}
        elif metoda == "Page.javascriptDialogClosed":
            okno = self._okno_sesji(sesja)
            if okno is not None:
                okno.dialog = None
        elif metoda == "Page.fileChooserOpened":
            okno = self._okno_sesji(sesja)
            if okno is not None:
                okno.wybor_pliku = {"tryb": p.get("mode"), "czas": time.time()}
                okno.wybor_wlasciciela = {"tryb": p.get("mode"), "czas": time.monotonic(), "sesja": sesja,
                                          "wezel": p.get("backendNodeId")}
                self.log("sterownik: strona otworzyła wybór pliku (robi go właściciel)")
        elif metoda == "Page.screencastFrame":
            self._klatka(p, sesja)
        elif metoda in ("Page.frameStartedNavigating", "Page.frameNavigated"):
            url = str(p.get("url") or (p.get("frame") or {}).get("url") or "")
            if metoda == "Page.frameNavigated":       # nowy dokument: stary odizolowany świat już nie istnieje
                okno = self._okno_sesji(sesja)
                if okno is not None:
                    ramka = (p.get("frame") or {}).get("id")
                    okno.swiaty.pop((sesja, ramka), None)
                    if okno.sesja == sesja and not (p.get("frame") or {}).get("parentId"):
                        okno.pasek = None              # nowa strona w karcie: fokus na stronie, nie w pasku
            if url.lower().startswith(SCHEMATY_ZAKAZANE):
                threading.Thread(target=self._zawroc, args=(sesja, url), daemon=True).start()
        elif metoda == "Runtime.executionContextsCleared":
            okno = self._okno_sesji(sesja)
            if okno is not None:
                for klucz in [k for k in okno.swiaty if k[0] == sesja]:
                    okno.swiaty.pop(klucz, None)
        elif metoda == "Fetch.requestPaused":
            threading.Thread(target=self._zadanie_fetch, args=(p, sesja), daemon=True).start()
        elif metoda == "Browser.downloadWillBegin":
            self._pobranie_start(p)
        elif metoda == "Browser.downloadProgress":
            self._pobranie_postep(p)
        elif metoda in ("Inspector.targetCrashed", "Target.targetCrashed"):
            self.log("sterownik: karta przeglądarki padła")

    def _dolaczony(self, p: dict, rodzic: str | None) -> None:
        info, sesja = p.get("targetInfo") or {}, p.get("sessionId")
        typ = info.get("type")
        if not sesja:
            return
        if typ == "page" and rodzic is None:
            url = str(info.get("url") or "")
            if url.startswith(("devtools:", "chrome-extension:")):
                return
            with self._lock:
                self._nr += 1
                okno = Okno(self._nr, info.get("targetId"), sesja)
                okno.tytul, okno.url = str(info.get("title") or ""), url
                self._okna[okno.nr] = okno
                self._po_celu[okno.target_id] = okno.nr
                self._aktywne = okno.nr
                self._nowe_okno.notify_all()
        elif typ == "iframe":
            with self._lock:
                okno = self._okno_sesji(rodzic)
                if okno is not None:
                    okno.ramki[str(info.get("targetId"))] = sesja
                    self._sesje_ramek[sesja] = (okno.nr, str(info.get("targetId")))
        elif typ not in ("page",):
            threading.Thread(target=self._pusc, args=(sesja,), daemon=True).start()   # workery: tylko wznowić
            return
        threading.Thread(target=self._przygotuj_cel, args=(sesja, info, rodzic), daemon=True).start()

    def _pusc(self, sesja: str) -> None:
        try:
            self.b.wyslij("Runtime.runIfWaitingForDebugger", {}, sesja, czas=5)
        except cdp.BladCDP:
            pass

    def _odlaczony(self, sesja: str | None) -> None:
        with self._lock:
            if sesja in self._sesje_ramek:
                nr, ramka = self._sesje_ramek.pop(sesja)
                if nr in self._okna:
                    self._okna[nr].ramki.pop(ramka, None)
                return
            for nr, okno in list(self._okna.items()):
                if okno.sesja == sesja:
                    del self._okna[nr]
                    self._po_celu.pop(okno.target_id, None)
                    if self._aktywne == nr:
                        self._aktywne = max(self._okna, default=None)

    def _okno_sesji(self, sesja: str | None) -> Okno | None:
        with self._lock:
            for okno in self._okna.values():
                if okno.sesja == sesja:
                    return okno
            if sesja in self._sesje_ramek:
                return self._okna.get(self._sesje_ramek[sesja][0])
        return None

    def _zawroc(self, sesja: str | None, url: str) -> None:
        """Adres spoza http(s) w karcie (file:, chrome:, devtools:, view-source:): z powrotem na pustą stronę."""
        self.statystyki["nawigacje_zablokowane"] += 1
        self.log(f"sterownik: zablokowany adres {url.split(':', 1)[0]}: w karcie")
        try:
            self.b.wyslij("Page.navigate", {"url": "about:blank"}, sesja, czas=10)
        except cdp.BladCDP:
            pass

    def _zadanie_fetch(self, p: dict, sesja: str | None) -> None:
        ident, url = p.get("requestId"), str((p.get("request") or {}).get("url") or "")
        try:
            if url.lower().startswith("file:"):
                self.statystyki["nawigacje_zablokowane"] += 1
                self.b.wyslij("Fetch.failRequest", {"requestId": ident, "errorReason": "BlockedByClient"}, sesja)
                return
            if self.strona_testowa is not None and DOMENA_TESTOWA.match(url):
                kod, naglowki, tresc = self._plik_testowy(url)
                self.b.wyslij("Fetch.fulfillRequest", {
                    "requestId": ident, "responseCode": kod, "body": base64.b64encode(tresc).decode("ascii"),
                    "responseHeaders": [{"name": k, "value": v} for k, v in naglowki.items()]}, sesja)
                return
            self.b.wyslij("Fetch.continueRequest", {"requestId": ident}, sesja)
        except cdp.KoniecPrzegladarki:
            pass
        except cdp.BladCDP as e:                  # wstrzymane żądanie bez odpowiedzi trzyma nawigację karty
            self.log(f"sterownik: żądanie {re.sub(r'[?#].*$', '', url)[:120]}: {e.tekst[:120]}")

    def _plik_testowy(self, url: str) -> tuple[int, dict, bytes]:
        """Plik strony testowej z katalogu; `pobierz/<nazwa>` to załącznik do pobrania o tej nazwie."""
        sciezka = re.sub(r"[?#].*$", "", DOMENA_TESTOWA.sub("", url)) or "index.html"
        bez_pamieci = {"Cache-Control": "no-store"}
        if sciezka.startswith("pobierz/"):
            nazwa = re.sub(r"[^A-Za-z0-9._-]", "_", sciezka.split("/", 1)[1])[:80] or "plik"
            return 200, {"Content-Type": "application/octet-stream", **bez_pamieci,
                         "Content-Disposition": f'attachment; filename="{nazwa}"'}, b"plik testowy Jarvo\n"
        if sciezka.endswith("/"):
            sciezka += "index.html"
        cel = (self.strona_testowa / sciezka).resolve()
        baza = self.strona_testowa.resolve()
        if baza not in cel.parents or not cel.is_file():
            return 404, {"Content-Type": "text/plain; charset=utf-8", **bez_pamieci}, b"nie ma"
        typ = mimetypes.guess_type(cel.name)[0] or "application/octet-stream"
        if typ.startswith("text/") or typ in ("application/javascript", "application/json"):
            typ += "; charset=utf-8"
        return 200, {"Content-Type": typ, **bez_pamieci}, cel.read_bytes()

    # --- pobrane pliki

    def _pobranie_start(self, p: dict) -> None:
        guid, nazwa = str(p.get("guid") or ""), str(p.get("suggestedFilename") or "pobrany-plik")
        if przegladarka.wykonywalny(nazwa):
            self._pobrania[guid] = {"nazwa": nazwa, "odrzucone": True}
            self.statystyki["odrzucone"] += 1
            self.log(f"sterownik: pobranie odrzucone (plik wykonywalny .{przegladarka.rozszerzenie(nazwa)})")
            try:
                self.b.wyslij("Browser.cancelDownload", {"guid": guid}, czas=5)
            except cdp.BladCDP:
                pass
            return
        self._pobrania[guid] = {"nazwa": nazwa, "odrzucone": False}

    def _pobranie_postep(self, p: dict) -> None:
        guid, stan = str(p.get("guid") or ""), p.get("state")
        wpis = self._pobrania.get(guid) or {"nazwa": "pobrany-plik", "odrzucone": False}
        plik = Path(str(p.get("filePath") or (self.w_toku / guid)))
        if stan == "completed":
            cel = self.pobrane / przegladarka.bezpieczna_nazwa(wpis["nazwa"], self.pobrane)
            if wpis["odrzucone"] or przegladarka.wykonywalny(wpis["nazwa"]) or przegladarka.wykonywalny(cel.name):
                try:
                    plik.unlink()
                except OSError:
                    pass
                return
            try:
                os.replace(plik, cel)
                self.statystyki["pobrane"] += 1
                self.log(f"sterownik: pobrany plik zapisany ({cel.name})")
            except OSError as e:
                self.log(f"sterownik: nie przeniosłem pobranego pliku ({e.strerror or e})")
            self._pobrania.pop(guid, None)
        elif stan == "canceled":
            self._pobrania.pop(guid, None)
            try:
                plik.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------ pomoc: okna, światy, węzły

    @property
    def pid(self) -> int | None:
        return self.b.pid

    def okna(self) -> list[Okno]:
        with self._lock:
            return sorted(self._okna.values(), key=lambda o: o.nr)

    def okno(self, nr) -> Okno | None:
        try:
            nr = int(nr)
        except (TypeError, ValueError):
            return None
        with self._lock:
            return self._okna.get(nr)

    def aktywne_okno(self) -> int | None:
        with self._lock:
            return self._aktywne if self._aktywne in self._okna else None

    def _okno_z(self, args: dict, wymagaj: bool = True) -> Okno:
        pid = args.get("pid")
        if pid is not None and pid != self.pid:
            raise BladSterownika("pid", f"proces {pid} to nie przeglądarka Jarva (pid {self.pid})")
        nr = args.get("window_id")
        okno = self.okno(nr) if nr is not None else self.okno(self.aktywne_okno())
        if okno is None and wymagaj:
            raise BladSterownika("okno", "nie ma takiego okna przeglądarki; zrób list_windows")
        return okno

    def _swiat(self, okno: Okno, sesja: str, ramka: str | None = None) -> int:
        """Kontekst odizolowanego świata `jarvo` w ramce (strona go nie widzi i nie podmieni funkcji DOM)."""
        if ramka is None:
            drzewo = self.b.wyslij("Page.getFrameTree", {}, sesja)
            ramka = drzewo["frameTree"]["frame"]["id"]
        klucz = (sesja, ramka)
        ctx = okno.swiaty.get(klucz)
        if ctx is not None:
            return ctx
        ctx = self.b.wyslij("Page.createIsolatedWorld", {"frameId": ramka, "worldName": "jarvo-komputer",
                                                         "grantUniveralAccess": False}, sesja)["executionContextId"]
        okno.swiaty[klucz] = ctx
        return ctx

    def _obiekt(self, okno: Okno, sesja: str, wezel: int, ramka: str | None) -> str:
        """objectId węzła DOM w odizolowanym świecie jego ramki (`ramka`: frameId dokumentu węzła, None = główna
        ramka sesji)."""
        for proba in range(2):
            ctx = self._swiat(okno, sesja, ramka)
            try:
                obiekt = self.b.wyslij("DOM.resolveNode", {"backendNodeId": wezel, "executionContextId": ctx},
                                       sesja).get("object") or {}
                if obiekt.get("objectId"):
                    return obiekt["objectId"]
            except cdp.BladCDP:
                pass
            klucz = (sesja, ramka) if ramka else next((k for k in okno.swiaty if k[0] == sesja), None)
            okno.swiaty.pop(klucz, None)               # świat zniknął z nawigacją: następna próba zakłada nowy
        raise BladSterownika("wezel", "nie da się odczytać elementu (strona się zmieniła)")

    def _js(self, sesja: str, obiekt: str, funkcja: str, *argumenty, wartosc: bool = True) -> Any:
        params = {"objectId": obiekt, "functionDeclaration": funkcja, "returnByValue": wartosc,
                  "arguments": [a if isinstance(a, dict) else {"value": a} for a in argumenty]}
        wynik = self.b.wyslij("Runtime.callFunctionOn", params, sesja)
        if wynik.get("exceptionDetails"):
            raise BladSterownika("js", "błąd odczytu strony")
        return wynik["result"].get("value") if wartosc else wynik["result"]

    # ------------------------------------------------------------------ migawka (get_window_state)

    def _ramki_okna(self, okno: Okno) -> list[dict]:
        """Ramki karty: [{"sesja", "ramka" (frameId albo None dla korzenia sesji), "rodzic", "wlasciciel"}]."""
        drzewo = self.b.wyslij("Page.getFrameTree", {}, okno.sesja)["frameTree"]
        wynik = [{"sesja": okno.sesja, "ramka": drzewo["frame"]["id"], "rodzic": None, "korzen": True}]

        def zejdz(wezel, sesja, glebokosc):
            for dziecko in wezel.get("childFrames") or []:
                if len(wynik) >= MAKS_RAMEK or glebokosc > 6:
                    return
                fid = dziecko["frame"]["id"]
                wynik.append({"sesja": sesja, "ramka": fid, "rodzic": wezel["frame"]["id"], "korzen": False})
                zejdz(dziecko, sesja, glebokosc + 1)
        zejdz(drzewo, okno.sesja, 0)
        for fid, sesja in list(okno.ramki.items()):        # ramki z innych procesów (OOPIF)
            if len(wynik) >= MAKS_RAMEK:
                break
            if not any(r["ramka"] == fid for r in wynik):
                wynik.append({"sesja": sesja, "ramka": fid, "rodzic": None, "korzen": True, "oopif": True})
            else:
                for r in wynik:
                    if r["ramka"] == fid:
                        r.update(sesja=sesja, korzen=True, oopif=True)
        return wynik

    def _snapshot(self, sesja: str) -> dict:
        """DOMSnapshot sesji: backendNodeId -> {"bounds", "doc", "tag", "atr", "dokument"}; dokumenty z przewinięciem."""
        s = self.b.wyslij("DOMSnapshot.captureSnapshot", {
            "computedStyles": ["border-left-width", "border-top-width", "padding-left", "padding-top"],
            "includeDOMRects": True}, sesja)
        napisy = s.get("strings") or []

        def napis(i):
            return napisy[i] if isinstance(i, int) and 0 <= i < len(napisy) else ""
        wezly, dokumenty = {}, []
        for di, d in enumerate(s.get("documents") or []):
            n = d.get("nodes") or {}
            backend = n.get("backendNodeId") or []
            nazwy = n.get("nodeName") or []
            atrybuty = n.get("attributes") or []
            zawartosc = dict(zip((n.get("contentDocumentIndex") or {}).get("index") or [],
                                 (n.get("contentDocumentIndex") or {}).get("value") or []))
            uklad = d.get("layout") or {}
            granice = {}
            style = {}
            for li, ni in enumerate(uklad.get("nodeIndex") or []):
                if ni not in granice:
                    granice[ni] = (uklad.get("bounds") or [])[li]
                    st = (uklad.get("styles") or [])[li] if li < len(uklad.get("styles") or []) else []
                    style[ni] = [napis(x) for x in st]
            dokumenty.append({"ramka": napis(d.get("frameId")), "przewiniecie": (d.get("scrollOffsetX") or 0,
                                                                                 d.get("scrollOffsetY") or 0),
                              "url": napis(d.get("documentURL"))})
            for ni, bid in enumerate(backend):
                atr = {}
                lista = atrybuty[ni] if ni < len(atrybuty) else []
                for k in range(0, len(lista) - 1, 2):
                    atr[napis(lista[k]).lower()] = napis(lista[k + 1])
                wezly[bid] = {"doc": di, "tag": napis(nazwy[ni]).lower() if ni < len(nazwy) else "", "atr": atr,
                              "bounds": granice.get(ni), "style": style.get(ni), "zawartosc": zawartosc.get(ni)}
        return {"wezly": wezly, "dokumenty": dokumenty}

    @staticmethod
    def _px(tekst: str) -> float:
        try:
            return float(str(tekst).removesuffix("px"))
        except ValueError:
            return 0.0

    def _przesuniecia(self, okno: Okno, ramki: list[dict], snapy: dict[str, dict]) -> dict[tuple, tuple]:
        """(sesja, frameId) -> (dx, dy): przesunięcie układu dokumentu ramki do układu okna (piksele CSS)."""
        wynik: dict[tuple, tuple] = {}
        glowny = snapy[okno.sesja]
        for di, d in enumerate(glowny["dokumenty"]):
            if di == 0:
                sx, sy = d["przewiniecie"]
                wynik[(okno.sesja, d["ramka"])] = (-sx, -sy)
        # ramki z tego samego procesu: właściciel (iframe) ma contentDocumentIndex w swoim dokumencie
        for _ in range(4):
            for bid, w in glowny["wezly"].items():
                j = w.get("zawartosc")
                if j is None or j >= len(glowny["dokumenty"]):
                    continue
                rodzic = glowny["dokumenty"][w["doc"]]["ramka"]
                dziecko = glowny["dokumenty"][j]["ramka"]
                if (okno.sesja, rodzic) not in wynik or (okno.sesja, dziecko) in wynik or not w.get("bounds"):
                    continue
                px, py = wynik[(okno.sesja, rodzic)]
                st = [self._px(x) for x in (w.get("style") or [])] + [0, 0, 0, 0]
                sx, sy = glowny["dokumenty"][j]["przewiniecie"]
                wynik[(okno.sesja, dziecko)] = (px + w["bounds"][0] + st[0] + st[2] - sx,
                                                py + w["bounds"][1] + st[1] + st[3] - sy)
        # ramki z innych procesów: właściciel w dokumencie rodzica (DOM.getFrameOwner w sesji rodzica)
        for r in ramki:
            if not r.get("oopif") or r["sesja"] not in snapy:
                continue
            for sesja_rodzica, s in snapy.items():
                if sesja_rodzica == r["sesja"]:
                    continue
                try:
                    wl = self.b.wyslij("DOM.getFrameOwner", {"frameId": r["ramka"]}, sesja_rodzica, czas=5)
                except cdp.BladCDP:
                    continue
                w = s["wezly"].get(wl.get("backendNodeId"))
                if not w or not w.get("bounds"):
                    continue
                rodzic = s["dokumenty"][w["doc"]]["ramka"]
                if (sesja_rodzica, rodzic) not in wynik:
                    continue
                px, py = wynik[(sesja_rodzica, rodzic)]
                st = [self._px(x) for x in (w.get("style") or [])] + [0, 0, 0, 0]
                d0 = snapy[r["sesja"]]["dokumenty"][0] if snapy[r["sesja"]]["dokumenty"] else {"przewiniecie": (0, 0)}
                sx, sy = d0["przewiniecie"]
                wynik[(r["sesja"], d0.get("ramka") or r["ramka"])] = (px + w["bounds"][0] + st[0] + st[2] - sx,
                                                                       py + w["bounds"][1] + st[1] + st[3] - sy)
                break
        return wynik

    def _elementy(self, okno: Okno, maks: int) -> tuple[list[dict], dict]:
        """Elementy migawki (kolejność drzewa) i mapa numer -> (sesja, backendNodeId)."""
        ramki = self._ramki_okna(okno)
        snapy: dict[str, dict] = {}
        for r in ramki:
            if r["sesja"] not in snapy:
                try:
                    snapy[r["sesja"]] = self._snapshot(r["sesja"])
                except cdp.BladCDP:
                    snapy[r["sesja"]] = {"wezly": {}, "dokumenty": []}
        przes = self._przesuniecia(okno, ramki, snapy)
        drzewa: dict[str, list] = {}
        wlasciciele: dict[tuple, str] = {}          # (sesja, backendNodeId iframe) -> frameId zawartości
        for r in ramki:
            try:
                params = {} if r["korzen"] else {"frameId": r["ramka"]}
                drzewa[r["ramka"]] = self.b.wyslij("Accessibility.getFullAXTree", params, r["sesja"]).get("nodes") or []
            except cdp.BladCDP:
                drzewa[r["ramka"]] = []
        sesja_ramki = {r["ramka"]: r["sesja"] for r in ramki}
        for sesja, s in snapy.items():
            for bid, w in s["wezly"].items():
                j = w.get("zawartosc")
                if j is not None and j < len(s["dokumenty"]):
                    wlasciciele[(sesja, bid)] = s["dokumenty"][j]["ramka"]
        for r in ramki:
            if r.get("oopif"):
                for sesja_rodzica in snapy:
                    if sesja_rodzica == r["sesja"]:
                        continue
                    try:
                        wl = self.b.wyslij("DOM.getFrameOwner", {"frameId": r["ramka"]}, sesja_rodzica, czas=5)
                        wlasciciele[(sesja_rodzica, wl.get("backendNodeId"))] = r["ramka"]
                        break
                    except cdp.BladCDP:
                        continue

        elementy: list[dict] = [self._element_paska(okno)]          # pasek adresu: element 0 każdej migawki
        mapa: dict[int, tuple] = {0: ("pasek", None, None)}
        odwiedzone_ramki: set[str] = set()

        def granice(sesja: str, bid: int | None) -> dict | None:
            w = snapy.get(sesja, {}).get("wezly", {}).get(bid) if bid is not None else None
            if not w or not w.get("bounds"):
                return None
            d = snapy[sesja]["dokumenty"][w["doc"]]
            dx, dy = przes.get((sesja, d["ramka"]), (None, None))
            if dx is None:
                return None
            x, y, sz, wy = w["bounds"]
            k = okno.skala
            return {"x": round((x + dx) * k), "y": round((y + dy) * k), "w": round(sz * k), "h": round(wy * k)}

        def tekst_dzieci(wezel: dict, po_id: dict, glebokosc: int = 0) -> str:
            """Tekst akapitu, nagłówka albo komórki bez nazwy; bez etykiet pól (<label>: to już nazwa pola)."""
            czesci = []
            for cid in wezel.get("childIds") or []:
                d = po_id.get(cid)
                if not d:
                    continue
                r = str((d.get("role") or {}).get("value") or "").lower()
                if r == "statictext":
                    czesci.append(str((d.get("name") or {}).get("value") or ""))
                elif glebokosc < 3 and r in POMIJANE and r != "labeltext":
                    czesci.append(tekst_dzieci(d, po_id, glebokosc + 1))
            return " ".join(c for c in czesci if c.strip())

        def przejdz(sesja: str, ramka: str, wezel: dict, po_id: dict, rodzic: int | None, glebokosc: int,
                    rola_rodzica: str, surowy_rodzic: str = "") -> None:
            if len(elementy) >= maks or glebokosc > 60:
                return
            r_cdp = str((wezel.get("role") or {}).get("value") or "")
            r_low = r_cdp.lower()
            bid = wezel.get("backendDOMNodeId")
            w_snap = snapy.get(sesja, {}).get("wezly", {}).get(bid) or {}
            typ = str((w_snap.get("atr") or {}).get("type") or "").lower()
            rola = rola_zasad(r_cdp, typ)
            if rola == "document web" and rodzic is not None:
                rola = "document frame"
            nazwa = _napis((wezel.get("name") or {}).get("value"))
            wlasnosci = {p["name"]: (p.get("value") or {}).get("value") for p in wezel.get("properties") or []}
            pominiety = wezel.get("ignored") or r_low in POMIJANE
            if r_low == "statictext":
                # tekst etykiety pola (<label>) jest już nazwą pola; tekst przycisku, linku i akapitu w ich nazwie
                pominiety = (rola_rodzica in INTERAKTYWNE or rola_rodzica in TEKSTOWE or not nazwa
                             or surowy_rodzic == "labeltext")
            if not pominiety and not nazwa and rola in TEKSTOWE:
                nazwa = _napis(tekst_dzieci(wezel, po_id))
                if not nazwa and not wezel.get("childIds"):
                    pominiety = True                     # pusty akapit albo komórka
            if not pominiety and rola not in INTERAKTYWNE and rola not in TEKSTOWE and rola not in (
                    "document web", "document frame", "form", "dialog", "alert", "internal frame", "image", "table",
                    "table row", "list", "menu", "menu bar", "page tab list", "tree", "landmark", "static", "panel",
                    "tool bar") and not nazwa:
                pominiety = True
            nr = rodzic
            if not pominiety:
                nr = len(elementy)
                el: dict[str, Any] = {"element_index": nr, "depth": glebokosc, "role": rola,
                                      "label": nazwa[:MAKS_NAPIS], "in_web_content": rola != "document web"
                                      or rodzic is not None}
                if rodzic is not None:
                    el["parent_index"] = rodzic
                ramka_el = granice(sesja, bid)
                if ramka_el:
                    el["frame"] = ramka_el
                wartosc = (wezel.get("value") or {}).get("value")
                if wartosc not in (None, "") and rola not in ("password text",) and rola in INTERAKTYWNE:
                    el["value"] = str(wartosc)[:200]
                stany = [k for k in ("focused", "disabled", "required", "readonly", "expanded", "selected",
                                     "modal") if wlasnosci.get(k) is True]
                if wlasnosci.get("checked") in ("true", "mixed", True):
                    stany.append("checked")
                if wlasnosci.get("multiline") is True:
                    stany.append("multi-line")
                if stany:
                    el["states"] = stany
                el["element_token"] = ""                 # uzupełniane po nadaniu numeru migawki
                elementy.append(el)
                mapa[nr] = (sesja, bid, ramka)
                glebokosc += 1
            # zawartość ramki pod jej właścicielem (iframe)
            fid = wlasciciele.get((sesja, bid))
            if fid and fid not in odwiedzone_ramki and fid in drzewa and drzewa[fid]:
                odwiedzone_ramki.add(fid)
                wezly = drzewa[fid]
                po = {n["nodeId"]: n for n in wezly}
                korzen = next((n for n in wezly if not n.get("parentId")), wezly[0])
                przejdz(sesja_ramki.get(fid, sesja), fid, korzen, po, nr, glebokosc, rola)
                return
            for cid in wezel.get("childIds") or []:
                d = po_id.get(cid)
                if d is not None:
                    przejdz(sesja, ramka, d, po_id, nr, glebokosc, rola if not pominiety else rola_rodzica, r_low)

        glowna = ramki[0]["ramka"]
        wezly = drzewa.get(glowna) or []
        if wezly:
            po = {n["nodeId"]: n for n in wezly}
            korzen = next((n for n in wezly if not n.get("parentId")), wezly[0])
            odwiedzone_ramki.add(glowna)
            przejdz(okno.sesja, glowna, korzen, po, None, 0, "")
        return elementy, mapa

    @staticmethod
    def _element_paska(okno: Okno) -> dict:
        el = {"element_index": 0, "depth": 0, "role": "entry", "label": PASEK, "in_web_content": False,
              "value": (okno.pasek if okno.pasek is not None else okno.url)[:200], "element_token": ""}
        if okno.pasek is not None:
            el["states"] = ["focused"]
        return el

    @staticmethod
    def _opis_paska() -> dict:
        """Opis paska adresu dla twardych zasad: zwykłe pole jednowierszowe poza formularzem (tekst sprawdzają zasady
        tekstu: sekrety, adresy javascript:, file:, chrome:…)."""
        przodkowie = [{"rola": "tool bar", "nazwa": ""}]
        return {"rola": "entry", "nazwa": PASEK, "atrybuty": {"tag": "input", "text-input-type": "url"},
                "zrodlo": "pasek", "przodkowie": przodkowie, "sciezka_przodkow": przodkowie, "plik": False,
                "stany": ["editable", "single-line"], "w_formularzu": False, "formularz": []}

    def _pisz_w_pasek(self, okno: Okno, tekst: str, delivery: str) -> dict:
        """Tekst w pasku adresu z fokusem; nowa linia na końcu = Enter (przejście pod adres)."""
        enter = tekst.endswith(("\n", "\r"))
        okno.pasek = (okno.pasek or "") + re.sub(r"[\r\n]+", " ", tekst.rstrip("\r\n"))
        if enter:
            return self._przejdz_z_paska(okno, delivery)
        return _wynik(f"pasek adresu: wpisano {len(tekst)} znaków", effect="confirmed", path="cdp", delivery=delivery)

    def _przejdz_z_paska(self, okno: Okno, delivery: str) -> dict:
        url = adres_z_paska(okno.pasek or "")
        okno.pasek = None
        if url is None:
            return _blad("adres", "pasek adresu przyjmuje adresy http:// i https:// (albo tekst do wyszukania)")
        self.b.wyslij("Page.navigate", {"url": url}, okno.sesja, czas=15)
        return _wynik(f"przejście pod {urlsplit(url).netloc}", effect="unverifiable", path="cdp", delivery=delivery)

    def _klawisz_w_pasku(self, okno: Okno, klawisz: str, mody: list, delivery: str) -> dict:
        k = klawisz.strip().lower()
        skrot = {str(m).strip().lower() for m in mody}
        if k in ("return", "enter", "kp_enter", "iso_enter"):
            return self._przejdz_z_paska(okno, delivery)
        if k in ("escape", "esc", "tab"):
            okno.pasek = None                                     # fokus wraca do strony
            return _wynik("pasek adresu: fokus wrócił do strony", effect="confirmed", path="cdp", delivery=delivery)
        if k == "backspace":
            okno.pasek = (okno.pasek or "")[:-1]
        elif k == "a" and skrot & {"ctrl", "control", "cmd", "command", "meta", "super"}:
            okno.pasek = ""                                       # zaznacz wszystko: następny tekst zastępuje adres
        elif len(klawisz) == 1 and not skrot - {"shift"}:
            okno.pasek = (okno.pasek or "") + klawisz
        else:
            return _blad("klawisz", "w pasku adresu: tekst, Backspace, Ctrl+A, Enter (przejście) albo Escape")
        return _wynik(f"pasek adresu: klawisz {klawisz}", effect="confirmed", path="cdp", delivery=delivery)

    def _aktywuj(self, okno: Okno) -> None:
        """Karta na wierzch: pełny Chrome nie rysuje kart w tle, więc zrzut karty w tle czekałby bez końca."""
        try:
            self.b.wyslij("Target.activateTarget", {"targetId": okno.target_id}, czas=5)
            self.b.wyslij("Page.bringToFront", {}, okno.sesja, czas=5)
        except cdp.BladCDP:
            pass
        with self._lock:
            self._aktywne = okno.nr

    def _zrzut(self, okno: Okno, maks_wymiar: int | None) -> tuple[str, int, int]:
        """Zrzut obszaru strony (PNG w base64) i jego wymiary; skala karty = piksele zrzutu na piksel CSS. Zrzut
        karty w tle przełącza na nią (jak spojrzenie na kartę w przeglądarce)."""
        if okno.nr != self.aktywne_okno():
            self._aktywuj(okno)
        met = self.b.wyslij("Page.getLayoutMetrics", {}, okno.sesja)
        v = met.get("cssVisualViewport") or met.get("cssLayoutViewport") or {}
        sz, wy = float(v.get("clientWidth") or okno.rozmiar[0]), float(v.get("clientHeight") or okno.rozmiar[1])
        okno.rozmiar, okno.zmierzone = (sz, wy), True
        skala = 1.0
        if maks_wymiar and max(sz, wy) > maks_wymiar:
            skala = maks_wymiar / max(sz, wy)
        params: dict[str, Any] = {"format": "png", "captureBeyondViewport": False}
        if skala != 1.0:
            params["clip"] = {"x": float(v.get("pageX") or 0), "y": float(v.get("pageY") or 0), "width": sz,
                              "height": wy, "scale": skala}
        dane = self.b.wyslij("Page.captureScreenshot", params, okno.sesja, czas=15)["data"]
        szer, wys = _rozmiar_png(base64.b64decode(dane[:64] + "=" * (-len(dane[:64]) % 4)))
        if szer and sz:
            okno.skala = szer / sz
        return dane, szer, wys

    def _rejestruj(self, okno: Okno, elementy: list[dict], mapa: dict) -> str:
        sid = "s" + secrets.token_hex(6)
        for el in elementy:
            el["element_token"] = f"{sid}:{el['element_index']}"
        with self._lock:
            self._migawki[sid] = {"okno": okno.nr, "mapa": mapa, "czas": time.monotonic(),
                                  "role": {el["element_index"]: (el["role"], el["label"]) for el in elementy}}
            while len(self._migawki) > MAKS_MIGAWEK:
                self._migawki.popitem(last=False)
        return sid

    def _migawka_dialogu(self, okno: Okno) -> list[dict]:
        d = okno.dialog or {}
        elementy = [{"element_index": 0, "depth": 0, "role": "dialog", "label": d.get("wiadomosc", "")[:MAKS_NAPIS],
                     "in_web_content": True, "states": ["modal"]}]
        przyciski = ["OK"] if d.get("typ") == "alert" else ["OK", "Anuluj"]
        for nazwa in przyciski:
            elementy.append({"element_index": len(elementy), "parent_index": 0, "depth": 1, "role": "push button",
                             "label": nazwa, "in_web_content": True})
        if d.get("typ") == "prompt":
            elementy.append({"element_index": len(elementy), "parent_index": 0, "depth": 1, "role": "entry",
                             "label": d.get("wiadomosc", "")[:MAKS_NAPIS], "in_web_content": True,
                             "value": str(d.get("tekst") if d.get("tekst") is not None else d.get("domyslny"))[:200]})
        return elementy

    def get_window_state(self, args: dict, konfig: dict) -> dict:
        okno = self._okno_z(args)
        maks = args.get("max_elements")
        maks = maks if isinstance(maks, int) and not isinstance(maks, bool) and maks > 0 else MAKS_ELEMENTOW
        zrzut = args.get("include_screenshot") is not False
        tresc: list[dict] = []
        sc: dict[str, Any] = {"pid": self.pid, "window_id": okno.nr, "title": okno.tytul, "url": okno.url}
        if okno.dialog:
            elementy = self._migawka_dialogu(okno)
            mapa = {el["element_index"]: ("dialog", el["element_index"], None) for el in elementy}
            sc["dialog"] = {"type": okno.dialog["typ"]}
            zrzut = False                             # strona stoi do zamknięcia okna
        else:
            if zrzut:
                try:
                    dane, szer, wys = self._zrzut(okno, konfig.get("max_image_dimension"))
                    sc.update(screenshot_width=szer, screenshot_height=wys, screenshot_scale=round(okno.skala, 4))
                except cdp.BladCDP as e:               # drzewo i bez zrzutu: agent patrzy trybem ax
                    zrzut = False
                    sc["screenshot_error"] = f"zrzut się nie udał ({e.tekst[:80]})"
            elementy, mapa = self._elementy(okno, maks)
        wybor = okno.wybor_wlasciciela
        if wybor and time.monotonic() - wybor["czas"] < 300:
            sc["file_chooser"] = {"mode": wybor.get("tryb"),
                                  "message": "strona czeka na wybór pliku: robi go właściciel"}
        sid = self._rejestruj(okno, elementy, mapa)
        sc.update(snapshot_id=sid, elements=elementy, element_count=len(elementy))
        linie = [f"{len(elementy)} elements", f'- AXWindow "{okno.tytul}"']
        linie += [f"{'  ' * (el['depth'] + 1)}- [{el['element_index']}] {el['role']} \"{el['label'][:80]}\""
                  for el in elementy[:400]]
        tresc.append({"type": "text", "text": "\n".join(linie)})
        if zrzut and not okno.dialog:
            tresc.append({"type": "image", "data": dane, "mimeType": "image/png"})
        return {"content": tresc, "structuredContent": sc, "isError": False}

    # ------------------------------------------------------------------ opis elementu dla zasad

    def _ax_wezla(self, sesja: str, bid: int) -> tuple[dict | None, list[dict]]:
        """Węzeł dostępności elementu (pierwszy nieignorowany od niego w górę) i jego przodkowie."""
        wezly = self.b.wyslij("Accessibility.getPartialAXTree", {"backendNodeId": bid, "fetchRelatives": True},
                              sesja).get("nodes") or []
        po_id = {n["nodeId"]: n for n in wezly}
        wezel = next((n for n in wezly if n.get("backendDOMNodeId") == bid), None)
        while wezel is not None and (wezel.get("ignored") or str((wezel.get("role") or {}).get("value") or "").lower()
                                     in POMIJANE):
            wezel = po_id.get(wezel.get("parentId"))
        przodkowie, p = [], po_id.get(wezel.get("parentId")) if wezel else None
        while p is not None and len(przodkowie) < 8:
            r = str((p.get("role") or {}).get("value") or "")
            if not p.get("ignored") and r.lower() not in POMIJANE:
                przodkowie.append({"rola": rola_zasad(r), "nazwa": _napis((p.get("name") or {}).get("value"))})
            p = po_id.get(p.get("parentId"))
        return wezel, przodkowie

    def opis_wezla(self, okno: Okno, sesja: str, bid: int, ramka: str | None = None) -> dict | None:
        """Opis elementu na żywo w słowniku zasad (jak AT-SPI w kontenerze); None przy błędzie (cel nieznany)."""
        try:
            wezel, przodkowie = self._ax_wezla(sesja, bid)
            obiekt = self._obiekt(okno, sesja, bid, ramka)
            dom = self._js(sesja, obiekt, JS_OPIS) or {}
            rola_cdp = str(((wezel or {}).get("role") or {}).get("value") or dom.get("tag") or "")
            el: dict[str, Any] = {
                "rola": rola_zasad(rola_cdp, str(dom.get("typ") or "")),
                "nazwa": _napis(((wezel or {}).get("name") or {}).get("value")),
                "atrybuty": {k: v for k, v in (("tag", dom.get("tag")), ("html-input-name", dom.get("nazwa")),
                                               ("text-input-type", dom.get("typ")),
                                               ("autocomplete", dom.get("autocomplete")),
                                               ("placeholder-text", dom.get("placeholder"))) if v},
                "zrodlo": "cdp", "przodkowie": przodkowie[:5], "plik": bool(dom.get("plik")),
                "sciezka_przodkow": przodkowie}
            stany = []
            if dom.get("edytowalny") or el["rola"] in ("entry", "password text"):
                stany.append("editable")
            if dom.get("wieloliniowy"):
                stany.append("multi-line")
            elif el["rola"] in ("entry", "password text"):
                stany.append("single-line")
            el["stany"] = stany
            if dom.get("formularz"):
                forma = self._js(sesja, obiekt, JS_FORMULARZ, wartosc=False)
                fid = forma.get("objectId")
                fbid = self.b.wyslij("DOM.describeNode", {"objectId": fid}, sesja)["node"]["backendNodeId"] if fid \
                    else None
                przyciski = []
                if fbid:
                    for n in self.b.wyslij("Accessibility.queryAXTree", {"backendNodeId": fbid, "role": "button"},
                                           sesja).get("nodes") or []:
                        nazwa = _napis((n.get("name") or {}).get("value"))
                        if nazwa and not n.get("ignored"):
                            przyciski.append({"rola": "push button", "nazwa": nazwa})
                el.update(w_formularzu=True, formularz=przyciski)
            else:
                el.update(w_formularzu=False, formularz=[])
            return el
        except (cdp.BladCDP, BladSterownika, KeyError, TypeError):
            return None

    def opis_elementu(self, sid: str, indeks) -> dict | None:
        """Element migawki `sid` pod numerem `indeks`, opisany na żywo (None: nie ma go albo nie da się sprawdzić)."""
        with self._lock:
            m = self._migawki.get(sid)
        try:
            indeks = int(indeks)
        except (TypeError, ValueError):
            return None
        if not m or indeks not in m["mapa"]:
            return None
        okno = self.okno(m["okno"])
        if okno is None:
            return None
        sesja, bid, ramka = m["mapa"][indeks]
        if sesja == "dialog":
            return self._opis_dialogu(okno, bid)
        if sesja == "pasek":
            return self._opis_paska()
        if bid is None:
            return None
        return self.opis_wezla(okno, sesja, bid, ramka)

    def _opis_dialogu(self, okno: Okno, indeks: int) -> dict | None:
        d = okno.dialog
        if not d:
            return None
        przodek = [{"rola": "dialog", "nazwa": d["wiadomosc"]}]
        elementy = self._migawka_dialogu(okno)
        if indeks >= len(elementy):
            return None
        el = elementy[indeks]
        opis = {"rola": el["role"], "nazwa": el["label"], "atrybuty": {}, "zrodlo": "dialog",
                "przodkowie": przodek if indeks else [], "w_formularzu": False, "formularz": [],
                "dialog": {"typ": d["typ"], "wiadomosc": d["wiadomosc"], "akceptuje": el["label"] == "OK"}}
        if el["role"] == "entry":
            opis["stany"] = ["editable", "single-line"]
        return opis

    def opis_dialogu_okna(self, nr) -> dict | None:
        """Otwarte okno JavaScript w karcie `nr`: {"typ", "wiadomosc"} albo None."""
        okno = self.okno(nr)
        return dict(okno.dialog) if okno is not None and okno.dialog else None

    def _zmierz(self, okno: Okno) -> tuple[float, float]:
        """Obszar strony karty w pikselach CSS (Page.getLayoutMetrics); zapamiętany do następnego zrzutu."""
        try:
            met = self.b.wyslij("Page.getLayoutMetrics", {}, okno.sesja, czas=5)
            v = met.get("cssVisualViewport") or met.get("cssLayoutViewport") or {}
            if v.get("clientWidth") and v.get("clientHeight"):
                okno.rozmiar = (float(v["clientWidth"]), float(v["clientHeight"]))
                okno.zmierzone = True
        except cdp.BladCDP:
            pass
        return okno.rozmiar

    def _trafienie(self, okno: Okno, x: float, y: float) -> tuple[str, int, str | None] | None:
        """(sesja, backendNodeId, frameId) elementu, który dostanie kliknięcie w punkcie okna (piksele CSS), także
        w ramce z innego procesu; None poza obszarem strony albo bez odpowiedzi."""
        sz, wy = okno.rozmiar if okno.zmierzone else self._zmierz(okno)
        if not (0 <= x < sz and 0 <= y < wy):
            return None
        sesja, lx, ly = okno.sesja, x, y
        for _ in range(4):
            try:
                t = self.b.wyslij("DOM.getNodeForLocation", {"x": int(lx), "y": int(ly),
                                                             "includeUserAgentShadowDOM": False,
                                                             "ignorePointerEventsNone": True}, sesja, czas=5)
            except cdp.BladCDP:
                return None
            bid = t.get("backendNodeId")
            if not bid:
                return None
            try:
                opis = self.b.wyslij("DOM.describeNode", {"backendNodeId": bid}, sesja, czas=5)["node"]
            except cdp.BladCDP:
                return None
            fid = opis.get("frameId") if opis.get("nodeName") in ("IFRAME", "FRAME") else None
            if fid and fid in okno.ramki:              # zawartość ramki z innego procesu
                try:
                    pud = self.b.wyslij("DOM.getBoxModel", {"backendNodeId": bid}, sesja, czas=5)["model"]["content"]
                except cdp.BladCDP:
                    return None
                sesja, lx, ly = okno.ramki[fid], lx - pud[0], ly - pud[1]
                continue
            return sesja, bid, t.get("frameId")
        return None

    def opis_w_punkcie(self, nr, x, y) -> dict | None:
        """Element w punkcie (x, y) okna `nr` w pikselach zrzutu, opisany na żywo; zapamiętany do sprawdzenia przy
        samym kliknięciu."""
        okno = self.okno(nr)
        if okno is None:
            return None
        try:
            cx, cy = float(x) / okno.skala, float(y) / okno.skala
        except (TypeError, ValueError):
            return None
        if okno.dialog:
            return None                               # strona stoi pod oknem JavaScript: punkt nie ma sensu
        cel = self._trafienie(okno, cx, cy)
        if cel is None:
            return None
        teraz = time.monotonic()
        for klucz in [k for k, v in okno.trafienia.items() if teraz - v[0] > 10]:
            okno.trafienia.pop(klucz, None)              # sprawdzenia bez kliknięcia nie zostają na zawsze
        okno.trafienia[(round(cx), round(cy))] = (teraz, *cel)
        return self.opis_wezla(okno, *cel)

    def fokus(self, nr) -> dict | None | bool:
        """Pole z fokusem klawiatury w oknie `nr` (przez ramki i shadow DOM): opis, None bez fokusu albo False,
        gdy nie da się tego ustalić (zasady: cel nieznany)."""
        okno = self.okno(nr) if nr is not None else self.okno(self.aktywne_okno())
        if okno is None:
            return False
        if okno.dialog:
            d = okno.dialog
            if d["typ"] == "prompt":
                return self._opis_dialogu(okno, len(self._migawka_dialogu(okno)) - 1)
            return self._opis_dialogu(okno, 1)        # Enter w oknie JavaScript = OK
        el = self._fokus_teraz(okno)
        # ocena zasad dotyczy tego pola (albo braku pola z fokusem): pisanie, znak i Enter sprawdzą tuż przed
        # działaniem, że fokus jest tam, gdzie był przy ocenie
        okno.fokus_oceniony = (el or None, time.monotonic()) if el is not False else None
        if not el:
            return el
        if el[0] == "pasek":
            return self._opis_paska()
        return self.opis_wezla(okno, *el) or False

    def _fokus_teraz(self, okno: Okno) -> tuple | None | bool:
        """Element z fokusem klawiatury: pasek adresu sterownika albo pole strony (_element_fokusu)."""
        return ("pasek", None, None) if okno.pasek is not None else self._element_fokusu(okno)

    def _sprawdz_fokus(self, okno: Okno) -> None:
        """Pisanie albo Enter bez celu: pole z fokusem ma być tym, które przed chwilą oceniły twarde zasady (skrypt
        strony mógł je przestawić między oceną a działaniem)."""
        ocena, okno.fokus_oceniony = okno.fokus_oceniony, None
        if ocena is None or time.monotonic() - ocena[1] > CZAS_FOKUSU:
            return
        if self._fokus_teraz(okno) != ocena[0]:
            raise BladSterownika("fokus_zmieniony", "fokus przeszedł na inne pole niż to, które sprawdziły twarde "
                                                    "zasady; zrób get_window_state, kliknij pole i spróbuj jeszcze raz")

    def _sprawdz_fokus_w(self, okno: Okno, cel: tuple | None) -> None:
        """Po kliknięciu w cel przed pisaniem: fokus ma leżeć w tym celu (albo cel w polu z fokusem, np. akapit
        w edytorze). Skrypt strony, który na kliknięcie przenosi fokus gdzie indziej (np. do pola hasła), nie dostanie
        tekstu. `cel` = (sesja, backendNodeId, frameId) elementu albo trafienia w punkcie."""
        if cel is None or okno.dialog:
            return
        teraz = self._element_fokusu(okno)
        if not teraz or not (self._zawiera(okno, cel, teraz) or self._zawiera(okno, teraz, cel)):
            raise BladSterownika("fokus_zmieniony", "po kliknięciu fokus nie trafił do wskazanego pola (strona "
                                                    "przeniosła go gdzie indziej); zrób get_window_state i spróbuj "
                                                    "jeszcze raz")

    def _element_fokusu(self, okno: Okno) -> tuple | None | bool:
        """(sesja, backendNodeId, frameId) elementu z fokusem, None bez fokusu, False gdy nie wiadomo."""
        try:
            sesja, ramka = okno.sesja, None
            for _ in range(8):                         # dokument po dokumencie: ramki tej samej i innej domeny
                ctx = self._swiat(okno, sesja, ramka)
                try:
                    w = self.b.wyslij("Runtime.callFunctionOn", {"functionDeclaration": JS_FOKUS,
                                                                 "executionContextId": ctx, "returnByValue": False},
                                      sesja)
                except cdp.BladCDP:                    # świat zniknął z nawigacją: jeden nowy i druga próba
                    for klucz in [k for k, v in okno.swiaty.items() if v == ctx]:
                        okno.swiaty.pop(klucz, None)
                    ctx = self._swiat(okno, sesja, ramka)
                    w = self.b.wyslij("Runtime.callFunctionOn", {"functionDeclaration": JS_FOKUS,
                                                                 "executionContextId": ctx, "returnByValue": False},
                                      sesja)
                obiekt = (w.get("result") or {}).get("objectId")
                if not obiekt:
                    return None
                opis = self.b.wyslij("DOM.describeNode", {"objectId": obiekt}, sesja)["node"]
                if opis.get("nodeName") in ("IFRAME", "FRAME"):
                    fid = opis.get("frameId")
                    if not fid:
                        return False                     # ramka bez dokumentu: nie wiadomo, gdzie trafi tekst
                    if fid in okno.ramki:
                        sesja = okno.ramki[fid]
                    ramka = fid
                    continue
                return sesja, opis["backendNodeId"], ramka
        except (cdp.BladCDP, BladSterownika, KeyError):
            return False
        return False

    # ------------------------------------------------------------------ wejście: mysz i klawiatura

    def _wejscie(self, okno: Okno, metoda: str, params: dict) -> None:
        """Zdarzenie wejścia; nie czeka bez końca, gdy kliknięcie otworzyło okno JavaScript albo wybór pliku."""
        o = self.b.nadaj(metoda, params, okno.sesja)
        koniec = time.monotonic() + CZAS_WEJSCIA
        while time.monotonic() < koniec:
            if o.gotowe(0.05):
                try:
                    o.wynik(1)
                except cdp.BladCDP as e:
                    raise BladSterownika("wejscie", f"przeglądarka odrzuciła zdarzenie: {e.tekst[:100]}") from None
                return
            if okno.dialog or okno.wybor_pliku:
                return
        raise BladSterownika("wejscie", "przeglądarka nie potwierdziła zdarzenia wejścia")

    @staticmethod
    def _mody(lista) -> int:
        maska = 0
        for m in lista or []:
            maska |= MODYFIKATORY.get(str(m).strip().lower(), (0,))[0]
        return maska

    def _mysz(self, okno: Okno, x: float, y: float, przycisk: str = "left", klikniecia: int = 1, mody: int = 0) -> None:
        przyciski = {"left": 1, "right": 2, "middle": 4}
        self._wejscie(okno, "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "modifiers": mody})
        for n in range(1, klikniecia + 1):
            for typ in ("mousePressed", "mouseReleased"):
                self._wejscie(okno, "Input.dispatchMouseEvent", {
                    "type": typ, "x": x, "y": y, "button": przycisk, "clickCount": n, "modifiers": mody,
                    "buttons": przyciski.get(przycisk, 1) if typ == "mousePressed" else 0})
                if okno.dialog:
                    return

    def _punkt_celu(self, okno: Okno, args: dict, nazwa: str) -> tuple[float, float, tuple | None]:
        """Punkt kliknięcia w pikselach CSS okna i element (sesja, backendNodeId), gdy działanie wskazuje element."""
        token = args.get("element_token")
        sid, indeks = (str(token).rpartition(":")[0], str(token).rpartition(":")[2]) if token else (
            args.get("snapshot_id"), args.get("element_index"))
        if token or indeks is not None:
            with self._lock:
                m = self._migawki.get(str(sid or ""))
            if not m:
                raise BladSterownika("stale", "elementu nie ma w żadnej migawce; zrób get_window_state")
            try:
                indeks = int(indeks)
            except (TypeError, ValueError):
                raise BladSterownika("stale", "zły numer elementu") from None
            if m["okno"] != okno.nr or indeks not in m["mapa"]:
                raise BladSterownika("stale", "element z innego okna albo spoza migawki; zrób get_window_state")
            sesja, bid, ramka = m["mapa"][indeks]
            if sesja == "dialog":
                if not okno.dialog:
                    raise BladSterownika("stale", "okna JavaScript już nie ma; zrób get_window_state")
                return -1.0, float(indeks), ("dialog", indeks, None)
            if sesja == "pasek":
                return -1.0, -1.0, ("pasek", None, None)
            if bid is None:
                raise BladSterownika("cel", "ten element nie ma węzła strony")
            if nazwa == "set_value":                     # wartość bez kliknięcia: punkt niepotrzebny
                return -1.0, -1.0, (sesja, bid, ramka)
            return (*self._srodek(okno, sesja, bid, ramka), (sesja, bid, ramka))
        x, y = args.get("x"), args.get("y")
        if x is None or y is None:
            raise BladSterownika("cel", f"{nazwa} wymaga elementu (element_token) albo punktu (x, y)")
        cx, cy = float(x) / okno.skala, float(y) / okno.skala
        trafienie = okno.trafienia.pop((round(cx), round(cy)), None)
        if trafienie and time.monotonic() - trafienie[0] < 10:
            teraz = self._trafienie(okno, cx, cy)
            if teraz is None or teraz != trafienie[1:]:
                raise BladSterownika("cel_zmieniony", "w tym punkcie leży już inny element niż przy sprawdzeniu; "
                                                      "zrób get_window_state")
        return cx, cy, None

    def _srodek(self, okno: Okno, sesja: str, bid: int, ramka: str | None) -> tuple[float, float]:
        """Środek widocznej części elementu w układzie okna; sprawdza, że to on dostanie kliknięcie."""
        try:
            self.b.wyslij("DOM.scrollIntoViewIfNeeded", {"backendNodeId": bid}, sesja, czas=5)
        except cdp.BladCDP:
            pass
        try:
            quady = self.b.wyslij("DOM.getContentQuads", {"backendNodeId": bid}, sesja).get("quads") or []
        except cdp.BladCDP:
            raise BladSterownika("stale", "element zniknął ze strony; zrób get_window_state") from None
        dx = dy = 0.0
        if sesja != okno.sesja:                        # ramka z innego procesu: przesunięcie jej właściciela
            fid = next((f for f, s in okno.ramki.items() if s == sesja), None)
            try:
                wl = self.b.wyslij("DOM.getFrameOwner", {"frameId": fid}, okno.sesja, czas=5)
                pud = self.b.wyslij("DOM.getBoxModel", {"backendNodeId": wl["backendNodeId"]}, okno.sesja,
                                    czas=5)["model"]["content"]
                dx, dy = pud[0], pud[1]
            except (cdp.BladCDP, KeyError):
                raise BladSterownika("cel", "nie da się ustalić położenia ramki elementu") from None
        sz, wy = okno.rozmiar
        for q in quady:
            xs, ys = [q[i] + dx for i in (0, 2, 4, 6)], [q[i] + dy for i in (1, 3, 5, 7)]
            x0, x1 = max(min(xs), 0), min(max(xs), sz - 1)
            y0, y1 = max(min(ys), 0), min(max(ys), wy - 1)
            if x1 - x0 >= 1 and y1 - y0 >= 1:
                x, y = (x0 + x1) / 2, (y0 + y1) / 2
                trafienie = self._trafienie(okno, x, y)
                if trafienie is None or not self._zawiera(okno, (sesja, bid, ramka), trafienie):
                    raise BladSterownika("element_przesloniety", "w miejscu tego elementu leży inny (baner, okienko "
                                                                 "albo nakładka strony); zrób get_window_state")
                return x, y
        raise BladSterownika("niewidoczny", "element jest poza widokiem albo nie ma wymiarów; przewiń stronę")

    def _zawiera(self, okno: Okno, cel: tuple, trafienie: tuple) -> bool:
        """Czy trafiony węzeł to cel albo jego potomek (także w shadow DOM)."""
        sesja, bid, ramka = cel
        ts, tbid, tramka = trafienie
        if ts != sesja:
            return False
        if tbid == bid:
            return True
        if tramka and ramka and tramka != ramka:
            return False                                 # inny dokument: nie potomek
        try:
            a, b = self._obiekt(okno, sesja, bid, ramka), self._obiekt(okno, sesja, tbid, tramka or ramka)
            return bool(self._js(sesja, a, JS_ZAWIERA, {"objectId": b}))
        except (cdp.BladCDP, BladSterownika):
            return False

    def _klawisz(self, okno: Okno, nazwa: str, mody: list) -> None:
        maska, wcisniete = 0, []
        for m in mody:
            info = MODYFIKATORY.get(str(m).strip().lower())
            if info and info[0] not in [w[0] for w in wcisniete]:
                maska |= info[0]
                self._wejscie(okno, "Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": info[1], "code": info[2],
                                                               "windowsVirtualKeyCode": info[3], "modifiers": maska})
                wcisniete.append(info)
        k = str(nazwa).strip()
        info = KLAWISZE.get(k.lower())
        if info is None and len(k) == 1:
            znak = k
            if maska & 8 and znak.isalpha():
                znak = znak.upper()
            kod = f"Key{znak.upper()}" if znak.isalpha() else (f"Digit{znak}" if znak.isdigit() else "")
            info = (znak, kod, ord(znak.upper()) if znak.isalnum() else 0, znak)
        if info is None:
            raise BladSterownika("klawisz", f"nieznany klawisz {k!r}")
        key, code, vk, tekst = info
        drukuje = tekst is not None and not (maska & (1 | 2 | 4))
        zdarzenie = {"type": "keyDown" if drukuje else "rawKeyDown", "key": key, "code": code,
                     "windowsVirtualKeyCode": vk, "modifiers": maska}
        if drukuje:
            zdarzenie.update(text=tekst, unmodifiedText=tekst)
        self._wejscie(okno, "Input.dispatchKeyEvent", zdarzenie)
        if not okno.dialog:
            self._wejscie(okno, "Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": code,
                                                           "windowsVirtualKeyCode": vk, "modifiers": maska})
        for info in reversed(wcisniete):
            maska &= ~info[0]
            if not okno.dialog:
                self._wejscie(okno, "Input.dispatchKeyEvent", {"type": "keyUp", "key": info[1], "code": info[2],
                                                               "windowsVirtualKeyCode": info[3], "modifiers": maska})

    def _obsluz_dialog(self, okno: Okno, przyjmij: bool) -> dict:
        d = okno.dialog or {}
        params: dict[str, Any] = {"accept": przyjmij}
        if przyjmij and d.get("typ") == "prompt":
            params["promptText"] = str(d.get("tekst") if d.get("tekst") is not None else d.get("domyslny") or "")
        self.b.wyslij("Page.handleJavaScriptDialog", params, d.get("sesja") or okno.sesja)
        okno.dialog = None
        return _wynik(f"okno JavaScript zamknięte ({'OK' if przyjmij else 'Anuluj'})", effect="confirmed", path="cdp")

    def _po_dzialaniu(self, okno: Okno, tekst: str, delivery: str, **sc) -> dict:
        if not okno.dialog and not okno.wybor_pliku:
            # okno JavaScript i wybór pliku przychodzą zdarzeniem chwilę po kliknięciu: krótka runda przez kartę
            try:
                self.b.wyslij("Runtime.evaluate", {"expression": "0", "returnByValue": True}, okno.sesja, czas=2)
            except cdp.BladCDP:
                pass
            koniec = time.monotonic() + 0.15
            while time.monotonic() < koniec and not okno.dialog and not okno.wybor_pliku:
                time.sleep(0.02)
        if okno.wybor_pliku and not okno.dialog:
            okno.wybor_pliku = None
            komunikat = "Strona otworzyła wybór pliku: plik wybiera właściciel (Komputer Jarva)."
            return {"content": [{"type": "text", "text": komunikat}], "isError": True,
                    "structuredContent": {"ok": False, "code": "wymaga_czlowieka", "rule": "wybor_pliku",
                                          "decision": "czlowiek", "next_step": "ask_owner", "message": komunikat}}
        if okno.dialog:
            sc["dialog"] = {"type": okno.dialog["typ"]}
            tekst += "; strona otworzyła okno JavaScript (zrób get_window_state)"
        return _wynik(tekst, path="cdp", delivery=delivery, **{"effect": "unverifiable", **sc})

    # ------------------------------------------------------------------ narzędzia

    def click(self, args: dict, nazwa: str = "click") -> dict:
        okno = self._okno_z(args)
        x, y, el = self._punkt_celu(okno, args, nazwa)
        if el and el[0] == "dialog":
            opis = self._opis_dialogu(okno, el[1]) or {}
            if opis.get("rola") != "push button":
                return _blad("cel", "w oknie JavaScript klikasz OK albo Anuluj")
            return self._obsluz_dialog(okno, opis["nazwa"] == "OK")
        delivery = str(args.get("delivery_mode") or "background")
        if el and el[0] == "pasek":
            okno.pasek = ""                            # klik zaznacza cały adres: tekst go zastąpi
            return _wynik("pasek adresu: fokus (wpisz adres i naciśnij Enter)", effect="confirmed", path="cdp",
                          delivery=delivery)
        przycisk = "right" if nazwa == "right_click" else str(args.get("button") or "left").lower()
        if przycisk not in ("left", "right", "middle"):
            return _blad("button", "button: left, right albo middle")
        try:
            ile = 2 if nazwa == "double_click" else max(1, min(3, int(args.get("count") or 1)))
        except (TypeError, ValueError):
            ile = 1
        okno.pasek = None                              # klik w stronę: fokus wraca do strony
        self._mysz(okno, x, y, przycisk, ile, self._mody(args.get("modifier") or args.get("modifiers")))
        return self._po_dzialaniu(okno, f"{nazwa} ({przycisk}) w {round(x)},{round(y)}", delivery)

    def drag(self, args: dict) -> dict:
        okno = self._okno_z(args)
        if args.get("from_element") is not None:
            a = self._punkt_celu(okno, {"snapshot_id": args.get("snapshot_id"), "element_index": args["from_element"]},
                                 "drag")
            b = self._punkt_celu(okno, {"snapshot_id": args.get("snapshot_id"), "element_index": args.get("to_element")},
                                 "drag")
        else:
            a = self._punkt_celu(okno, {"x": args.get("from_x"), "y": args.get("from_y")}, "drag")
            b = self._punkt_celu(okno, {"x": args.get("to_x"), "y": args.get("to_y")}, "drag")
        mody = self._mody(args.get("modifier"))
        okno.pasek = None
        self._wejscie(okno, "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": a[0], "y": a[1], "modifiers": mody})
        self._wejscie(okno, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": a[0], "y": a[1], "button": "left",
                                                         "buttons": 1, "clickCount": 1, "modifiers": mody})
        for i in range(1, 6):
            self._wejscie(okno, "Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": a[0] + (b[0] - a[0]) * i / 5, "y": a[1] + (b[1] - a[1]) * i / 5,
                "button": "left", "buttons": 1, "modifiers": mody})
        self._wejscie(okno, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": b[0], "y": b[1],
                                                         "button": "left", "buttons": 0, "clickCount": 1,
                                                         "modifiers": mody})
        return self._po_dzialaniu(okno, "przeciągnięcie", str(args.get("delivery_mode") or "background"))

    def scroll(self, args: dict) -> dict:
        okno = self._okno_z(args)
        if args.get("element_token") or args.get("element_index") is not None or (
                args.get("x") is not None and args.get("y") is not None):
            x, y, _ = self._punkt_celu(okno, args, "scroll")
        else:
            x, y = okno.rozmiar[0] / 2, okno.rozmiar[1] / 2
        try:
            ile = max(1, min(50, int(args.get("amount") or 3)))
        except (TypeError, ValueError):
            ile = 3
        kierunek = str(args.get("direction") or "down").lower()
        dx, dy = {"down": (0, 1), "up": (0, -1), "right": (1, 0), "left": (-1, 0)}.get(kierunek, (0, 1))
        self._wejscie(okno, "Input.dispatchMouseEvent", {"type": "mouseWheel", "x": x, "y": y,
                                                         "deltaX": dx * ile * 100, "deltaY": dy * ile * 100,
                                                         "modifiers": self._mody(args.get("modifier"))})
        return self._po_dzialaniu(okno, f"przewinięcie {kierunek} ×{ile}", str(args.get("delivery_mode")
                                                                              or "background"))

    def _wartosc_fokusu(self, okno: Okno) -> str | None:
        el = self._element_fokusu(okno)
        if not el:
            return None
        try:
            return self._js(el[0], self._obiekt(okno, *el), JS_WARTOSC_FOKUSU)
        except (cdp.BladCDP, BladSterownika):
            return None

    def type_text(self, args: dict) -> dict:
        okno = self._okno_z(args)
        tekst = str(args.get("text") or "")
        if okno.dialog:
            if okno.dialog.get("typ") != "prompt":
                return _blad("cel", "okno JavaScript nie ma pola tekstu: kliknij OK albo Anuluj")
            okno.dialog["tekst"] = (okno.dialog.get("tekst") or "") + tekst.rstrip("\r\n")
            if tekst.endswith(("\n", "\r")):
                return self._obsluz_dialog(okno, True)
            return _wynik("tekst wpisany w okno JavaScript", effect="confirmed", path="cdp")
        delivery = str(args.get("delivery_mode") or "background")
        if args.get("element_token") or args.get("element_index") is not None or (
                args.get("x") is not None and args.get("y") is not None):
            x, y, el = self._punkt_celu(okno, args, "type_text")
            if el is not None and el[0] == "pasek":
                okno.pasek = ""                        # klik w pasek zaznacza adres, tekst go zastępuje
                return self._pisz_w_pasek(okno, tekst, delivery)
            okno.pasek = None
            self._mysz(okno, x, y)
            if tekst:
                self._sprawdz_fokus_w(okno, el if el is not None else self._trafienie(okno, x, y))
        elif tekst:
            self._sprawdz_fokus(okno)
            if okno.pasek is not None:
                return self._pisz_w_pasek(okno, tekst, delivery)
        linie = re.split(r"(\r\n|\n|\r)", tekst)
        for czesc in linie:
            if czesc in ("\r\n", "\n", "\r"):
                self._klawisz(okno, "Return", [])
                if okno.dialog:
                    break
            elif czesc:
                self._wejscie(okno, "Input.insertText", {"text": czesc})
        ostatni = next((c for c in reversed(linie) if c not in ("\r\n", "\n", "\r") and c), "")
        wartosc = self._wartosc_fokusu(okno) if ostatni and not okno.dialog else None
        efekt = "confirmed" if wartosc is not None and ostatni and ostatni in wartosc else "unverifiable"
        wynik = self._po_dzialaniu(okno, f"wpisano {len(tekst)} znaków", str(args.get("delivery_mode")
                                                                                or "background"))
        if not wynik.get("isError"):
            wynik["structuredContent"]["effect"] = efekt
        return wynik

    def press_key(self, args: dict, hotkey: bool = False) -> dict:
        okno = self._okno_z(args)
        if hotkey:
            klawisze = [str(k) for k in args.get("keys") or []]
            mody = [k for k in klawisze if k.strip().lower() in MODYFIKATORY]
            reszta = [k for k in klawisze if k.strip().lower() not in MODYFIKATORY]
            if not reszta:
                return _blad("klawisz", "hotkey: brak klawisza poza modyfikatorami")
            klawisz = reszta[-1]
        else:
            klawisz, mody = str(args.get("key") or ""), list(args.get("modifiers") or [])
        if okno.dialog:
            k = klawisz.strip().lower()
            if k in ("return", "enter", "kp_enter"):
                return self._obsluz_dialog(okno, True)
            if k in ("escape", "esc"):
                return self._obsluz_dialog(okno, False)
            return _blad("cel", "okno JavaScript: Enter (OK) albo Escape (Anuluj)")
        # Enter, spacja i pojedynczy znak (bez Ctrl, Alt i Cmd): zasady oceniły pole z fokusem, więc tuż przed
        # klawiszem sterownik sprawdza, że fokus nadal tam jest
        drukowany = len(klawisz.strip()) == 1 and not {str(m).strip().lower() for m in mody} & {
            "ctrl", "control", "alt", "option", "cmd", "command", "meta", "super", "win"}
        aktywujacy = klawisz.strip().lower() in AKTYWUJACE or drukowany
        delivery = str(args.get("delivery_mode") or "background")
        if args.get("element_token") or args.get("element_index") is not None:
            x, y, el = self._punkt_celu(okno, args, "press_key")
            if el is not None and el[0] == "pasek":
                okno.pasek = okno.pasek if okno.pasek is not None else ""
                return self._klawisz_w_pasku(okno, klawisz, mody, delivery)
            okno.pasek = None
            self._mysz(okno, x, y)
            if aktywujacy:
                self._sprawdz_fokus_w(okno, el)
        else:
            if aktywujacy:
                self._sprawdz_fokus(okno)
            if okno.pasek is not None:
                return self._klawisz_w_pasku(okno, klawisz, mody, delivery)
        self._klawisz(okno, klawisz, mody)
        return self._po_dzialaniu(okno, f"klawisz {'+'.join([*mody, klawisz])}", str(args.get("delivery_mode")
                                                                                      or "background"))

    def set_value(self, args: dict) -> dict:
        okno = self._okno_z(args)
        _, _, el = self._punkt_celu(okno, args, "set_value")
        if el is not None and el[0] == "pasek":
            okno.pasek = re.sub(r"[\r\n]+", " ", str(args.get("value") or ""))
            return _wynik("pasek adresu: adres wpisany (Enter przechodzi)", effect="confirmed", path="cdp")
        if el is None or el[0] == "dialog":
            return _blad("cel", "set_value wymaga elementu strony (element_token)")
        sesja, bid, ramka = el
        try:
            wynik = self._js(sesja, self._obiekt(okno, sesja, bid, ramka), JS_WARTOSC,
                             str(args.get("value") or "")) or {}
        except BladSterownika as e:
            return _blad(e.kod, e.tekst)
        if not wynik.get("ok"):
            return _blad("set_value", f"set_value: {wynik.get('powod') or 'nie udało się'}")
        return _wynik(f"wartość ustawiona: {wynik.get('wartosc')}", effect="confirmed", path="cdp")

    def launch_app(self, args: dict) -> dict:
        okna = []
        for url in [str(u) for u in args.get("urls") or []][:8]:
            przed = {o.nr for o in self.okna()}
            cel = self.b.wyslij("Target.createTarget", {"url": url})
            # podpięcie nowej karty (Fetch, Network, zasady) na Windows arm64 z przeglądarką x64 w emulacji trwa
            # dłużej niż 10 s (CI natywnie, WARM): bez niej wynik nie miał nowej karty
            koniec = time.monotonic() + 30
            with self._lock:
                while cel.get("targetId") not in self._po_celu and time.monotonic() < koniec:
                    self._nowe_okno.wait(0.2)
                nr = self._po_celu.get(cel.get("targetId"))
            if nr is not None and nr not in przed:
                self._aktywne = nr
                okna.append({"window_id": nr, "title": "", "url": url})
        if not okna:
            okna = [{"window_id": o.nr, "title": o.tytul, "url": o.url} for o in self.okna()]
        return _wynik(f"{APLIKACJA}: {len(okna)} okien", pid=self.pid, name=APLIKACJA, bundle_id="chromium",
                      windows=okna)

    def kill_app(self, args: dict) -> dict:
        if args.get("pid") != self.pid:
            return _blad("aplikacja", "kill_app tylko dla przeglądarki Jarva")
        stare = self.okna()
        self.b.wyslij("Target.createTarget", {"url": "about:blank"})
        for o in stare:
            try:
                self.b.wyslij("Target.closeTarget", {"targetId": o.target_id}, czas=5)
            except cdp.BladCDP:
                pass
        return _wynik("przeglądarka wyczyszczona: zamknięte karty, nowa pusta karta", effect="confirmed", path="cdp")

    def bring_to_front(self, args: dict) -> dict:
        okno = self._okno_z(args)
        self.b.wyslij("Target.activateTarget", {"targetId": okno.target_id})
        try:
            self.b.wyslij("Page.bringToFront", {}, okno.sesja, czas=5)
        except cdp.BladCDP:
            pass
        with self._lock:
            self._aktywne = okno.nr
        return _wynik(f"okno {okno.nr} na wierzchu", effect="confirmed", path="cdp")

    def _odswiez_tytul(self, okno: Okno) -> None:
        """Tytuł i adres karty na żywo (zdarzenie targetInfoChanged nie zawsze niesie tytuł dokumentu)."""
        if okno.dialog:
            return
        try:
            ctx = self._swiat(okno, okno.sesja)
            w = self.b.wyslij("Runtime.evaluate", {"expression": "[document.title, location.href]", "contextId": ctx,
                                                   "returnByValue": True}, okno.sesja, czas=3)
            tytul, url = (w.get("result") or {}).get("value") or ("", "")
            okno.tytul, okno.url = str(tytul or okno.tytul), str(url or okno.url)
        except (cdp.BladCDP, BladSterownika, ValueError, TypeError):
            okno.swiaty.clear()

    def list_windows(self, args: dict) -> dict:
        aktywne = self.aktywne_okno()
        okna = []
        for o in self.okna():
            self._odswiez_tytul(o)
            okna.append({"window_id": o.nr, "pid": self.pid, "app_name": APLIKACJA, "title": o.tytul, "url": o.url,
                         "bounds": {"x": 0, "y": 0, "w": round(o.rozmiar[0]), "h": round(o.rozmiar[1])},
                         "is_on_screen": True, "z_index": 1000 if o.nr == aktywne else o.nr, "layer": 0,
                         "active": o.nr == aktywne})
        okna.sort(key=lambda w: -w["z_index"])
        return _wynik(f"{len(okna)} okien", windows=okna)

    def list_apps(self, args: dict) -> dict:
        return _wynik(APLIKACJA, apps=[{"name": APLIKACJA, "pid": self.pid, "bundle_id": "chromium", "running": True,
                                        "windows": len(self.okna())}])

    def get_desktop_state(self, args: dict, konfig: dict) -> dict:
        okno = self._okno_z(args)
        dane, szer, wys = self._zrzut(okno, konfig.get("max_image_dimension"))
        return {"content": [{"type": "text", "text": f"zrzut okna {okno.nr}"},
                            {"type": "image", "data": dane, "mimeType": "image/png"}],
                "structuredContent": {"ok": True, "screenshot_width": szer, "screenshot_height": wys,
                                      "window_id": okno.nr}, "isError": False}

    # ------------------------------------------------------------------ podgląd dla HQ (J10)

    def _klatka(self, p: dict, sesja: str | None) -> None:
        """Klatka Page.startScreencast: potwierdzenie od razu (bez niego przeglądarka nie wyśle następnej)
        i zapamiętanie ostatniej klatki karty, którą pokazuje podgląd."""
        try:
            self.b.nadaj("Page.screencastFrameAck", {"sessionId": p.get("sessionId")}, sesja)
        except cdp.BladCDP:
            pass
        okno = self._okno_sesji(sesja)
        if okno is None or okno.sesja != sesja or not p.get("data"):
            return
        meta = p.get("metadata") or {}
        with self._podglad_zmiana:
            if self._podglad["okno"] != okno.nr:
                return
            self._podglad["nr"] += 1
            self._podglad["klatka"] = {"nr": self._podglad["nr"], "okno": okno.nr, "typ": "image/jpeg",
                                       "dane": p["data"], "szer_css": meta.get("deviceWidth"),
                                       "wys_css": meta.get("deviceHeight"), "czas": round(time.time(), 3)}
            self._podglad_zmiana.notify_all()

    def _wlacz_podglad(self, okno: Okno) -> None:
        with self._podglad_zmiana:
            stare = self._podglad["okno"]
            self._podglad.update(okno=okno.nr, klatka=None)
            jakosc, maks = self._podglad["jakosc"], self._podglad["maks"]
        poprzednie = self.okno(stare) if stare is not None else None
        if poprzednie is not None and poprzednie.nr != okno.nr:
            try:
                self.b.wyslij("Page.stopScreencast", {}, poprzednie.sesja, czas=5)
            except cdp.BladCDP:
                pass
        self.b.wyslij("Page.startScreencast", {"format": "jpeg", "quality": jakosc, "maxWidth": maks,
                                               "maxHeight": maks, "everyNthFrame": 1}, okno.sesja, czas=5)

    def zatrzymaj_podglad(self) -> None:
        with self._podglad_zmiana:
            nr, self._podglad["okno"], self._podglad["klatka"] = self._podglad["okno"], None, None
        okno = self.okno(nr) if nr is not None else None
        if okno is not None:
            try:
                self.b.wyslij("Page.stopScreencast", {}, okno.sesja, czas=5)
            except cdp.BladCDP:
                pass

    @property
    def podglad_wlaczony(self) -> bool:
        return self._podglad.get("okno") is not None

    def podglad_bezczynny(self) -> None:
        """Wołane co chwilę przez usługę: podgląd bez pytań przez PODGLAD_BEZCZYNNOSC s staje."""
        with self._podglad_zmiana:
            wlaczony = self._podglad["okno"] is not None
            cisza = time.monotonic() - self._podglad["pytanie"]
        if wlaczony and cisza > PODGLAD_BEZCZYNNOSC:
            self.zatrzymaj_podglad()

    def _opis_klatki(self, k: dict, okno: Okno) -> dict:
        wynik = dict(k, aktywne=okno.nr, tytul=okno.tytul, url=okno.url,
                     okna=[{"window_id": o.nr, "title": o.tytul, "url": o.url} for o in self.okna()])
        if okno.dialog:
            wynik["dialog"] = {k_: okno.dialog.get(k_) for k_ in ("typ", "wiadomosc", "domyslny")}
        w = okno.wybor_wlasciciela
        if w and time.monotonic() - w["czas"] < 300:
            wynik["wybor_pliku"] = {"tryb": w.get("tryb")}
        return wynik

    def podglad(self, po: int | None = None, czekaj: float = 1.0, jakosc: int | None = None,
                maks: int | None = None) -> dict | None:
        """Ostatnia klatka podglądu aktywnej karty: {"nr", "okno", "typ": "image/jpeg", "dane" (base64), "szer_css",
        "wys_css", "czas", "aktywne", "tytul", "url", "okna", opcjonalnie "dialog" i "wybor_pliku"}. Pierwsze pytanie
        włącza screencast tej karty (zmiana aktywnej karty przenosi go na nową). `po` = numer klatki, którą pytający
        już ma: czeka do `czekaj` s na nowszą, a bez zmian zwraca {"nr": po, "bez_zmian": True}. Bez klatki
        (karta jeszcze nic nie narysowała) zrzut JPEG. None, gdy nie ma karty."""
        okno = self.okno(self.aktywne_okno())
        if okno is None:
            return None
        with self._podglad_zmiana:
            self._podglad["pytanie"] = time.monotonic()
            zmiana = False
            if isinstance(jakosc, int) and not isinstance(jakosc, bool) and 10 <= jakosc <= 95:
                zmiana, self._podglad["jakosc"] = zmiana or jakosc != self._podglad["jakosc"], jakosc
            if isinstance(maks, int) and not isinstance(maks, bool) and 200 <= maks <= 4096:
                zmiana, self._podglad["maks"] = zmiana or maks != self._podglad["maks"], maks
            biezace = self._podglad["okno"]
        if biezace != okno.nr or zmiana:
            try:
                self._wlacz_podglad(okno)
            except cdp.BladCDP as e:
                self.log(f"sterownik: podgląd się nie włączył ({e.tekst[:100]}); zrzut zamiast klatki")
        try:
            czekaj = max(0.0, min(float(czekaj or 0), 10.0))
        except (TypeError, ValueError):
            czekaj = 1.0
        koniec = time.monotonic() + czekaj
        with self._podglad_zmiana:                     # opis klatki dopiero po zwolnieniu blokady (lista kart)
            while True:
                k = self._podglad["klatka"]
                nowa = k is not None and k["okno"] == okno.nr and (po is None or k["nr"] > po)
                zostalo = koniec - time.monotonic()
                if nowa or zostalo <= 0:
                    break
                self._podglad_zmiana.wait(zostalo)
        if nowa:
            return self._opis_klatki(k, okno)
        if k is not None and k["okno"] == okno.nr:
            return {"nr": k["nr"], "okno": okno.nr, "bez_zmian": True, "aktywne": okno.nr,
                    **({"dialog": {"typ": okno.dialog.get("typ"), "wiadomosc": okno.dialog.get("wiadomosc")}}
                       if okno.dialog else {})}
        if okno.dialog:                                 # strona stoi pod oknem JavaScript: bez zrzutu
            return self._opis_klatki({"nr": 0, "okno": okno.nr, "typ": None, "dane": None}, okno)
        try:
            dane = self.b.wyslij("Page.captureScreenshot", {"format": "jpeg", "quality": PODGLAD_JAKOSC},
                                 okno.sesja, czas=10)["data"]
        except (cdp.BladCDP, KeyError):
            return None
        sz, wy = self._zmierz(okno)
        return self._opis_klatki({"nr": 0, "okno": okno.nr, "typ": "image/jpeg", "dane": dane, "szer_css": sz,
                                  "wys_css": wy, "czas": round(time.time(), 3)}, okno)

    # ------------------------------------------------------------------ „Przejmij”: wejście właściciela (J10)

    def _punkt_wlasciciela(self, okno: Okno, z: dict) -> tuple[float, float]:
        """x i y z podglądu (ułamki klatki 0–1) w pikselach CSS karty."""
        try:
            fx, fy = float(z.get("x")), float(z.get("y"))
        except (TypeError, ValueError):
            raise BladSterownika("wejscie", "x i y to ułamki klatki podglądu (0–1)") from None
        if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
            raise BladSterownika("wejscie", "x i y to ułamki klatki podglądu (0–1)")
        k = self._podglad.get("klatka") or {}
        if k.get("okno") == okno.nr and k.get("szer_css") and k.get("wys_css"):
            sz, wy = float(k["szer_css"]), float(k["wys_css"])
        else:
            sz, wy = self._zmierz(okno)
        return min(fx * sz, sz - 1), min(fy * wy, wy - 1)

    def _plik_wlasciciela(self, okno: Okno, z: dict) -> dict:
        wybor = okno.wybor_wlasciciela
        if not wybor or time.monotonic() - wybor["czas"] > 300 or not wybor.get("wezel"):
            raise BladSterownika("plik", "strona nie czeka na wybór pliku (kliknij najpierw pole pliku)")
        nazwy = z.get("pliki")
        if not isinstance(nazwy, list) or not nazwy or len(nazwy) > MAKS_PLIKOW:
            raise BladSterownika("plik", f"pliki: lista od 1 do {MAKS_PLIKOW} nazw z katalogu {self.wysylane}")
        if wybor.get("tryb") != "selectMultiple" and len(nazwy) > 1:
            raise BladSterownika("plik", "to pole przyjmuje jeden plik")
        baza, sciezki = self.wysylane.resolve(), []
        for n in nazwy:
            p = (baza / str(n)).resolve()
            if baza not in p.parents or not p.is_file():
                raise BladSterownika("plik", f"pliku {Path(str(n)).name!r} nie ma w katalogu {self.wysylane}")
            sciezki.append(str(p))
        self.b.wyslij("DOM.setFileInputFiles", {"files": sciezki, "backendNodeId": wybor["wezel"]},
                      wybor.get("sesja") or okno.sesja)
        okno.wybor_wlasciciela = None
        return {"ok": True, "pliki": len(sciezki)}

    def wejscie_wlasciciela(self, z: dict) -> dict:
        """Działanie właściciela z podglądu w HQ: wprost do aktywnej karty, bez twardych zasad (robi je człowiek).
        Typy: klik i mysz (x, y: ułamki klatki; przycisk, klikniecia, zdarzenie, modyfikatory), kolko (x, y, dx, dy),
        klawisz (klawisz, modyfikatory), tekst (tekst), adres (url http/https), wstecz, dalej, odswiez, okno (nr
        karty na wierzch), dialog (ok: true/false, tekst dla prompt), plik (pliki: nazwy z katalogu `wysylane`)."""
        z = z if isinstance(z, dict) else {}
        typ = str(z.get("typ") or "")
        try:
            if typ == "okno":
                okno = self.okno(z.get("okno"))
                if okno is None:
                    return {"ok": False, "blad": "nie ma takiej karty"}
                self._aktywuj(okno)
                return {"ok": True, "aktywne": okno.nr}
            okno = self.okno(self.aktywne_okno())
            if okno is None:
                return {"ok": False, "blad": "przeglądarka nie ma otwartej karty"}
            self.statystyki["wejscie_wlasciciela"] += 1
            if typ == "dialog":
                if not okno.dialog:
                    return {"ok": False, "blad": "nie ma otwartego okna JavaScript"}
                if okno.dialog.get("typ") == "prompt" and z.get("tekst") is not None:
                    okno.dialog["tekst"] = str(z["tekst"])[:MAKS_TEKST_WLASCICIELA]
                self._obsluz_dialog(okno, bool(z.get("ok")))
                return {"ok": True}
            if typ == "plik":
                return self._plik_wlasciciela(okno, z)
            if okno.dialog:
                return {"ok": False, "blad": "strona czeka na odpowiedź w oknie JavaScript (typ: dialog)",
                        "dialog": {"typ": okno.dialog.get("typ"), "wiadomosc": okno.dialog.get("wiadomosc")}}
            okno.pasek = None                          # właściciel działa na stronie: pasek adresu agenta bez fokusu
            if typ == "adres":
                url = str(z.get("url") or "").strip()
                if urlsplit(url).scheme.lower() not in ("http", "https") or not urlsplit(url).netloc:
                    return {"ok": False, "blad": "adres tylko http:// albo https://"}
                self.b.wyslij("Page.navigate", {"url": url}, okno.sesja, czas=15)
                return {"ok": True}
            if typ in ("wstecz", "dalej"):
                h = self.b.wyslij("Page.getNavigationHistory", {}, okno.sesja)
                i = int(h.get("currentIndex", 0)) + (-1 if typ == "wstecz" else 1)
                wpisy = h.get("entries") or []
                if not 0 <= i < len(wpisy):
                    return {"ok": False, "blad": "nie ma dokąd przejść"}
                self.b.wyslij("Page.navigateToHistoryEntry", {"entryId": wpisy[i]["id"]}, okno.sesja)
                return {"ok": True}
            if typ == "odswiez":
                self.b.wyslij("Page.reload", {}, okno.sesja)
                return {"ok": True}
            if typ in ("klik", "mysz"):
                x, y = self._punkt_wlasciciela(okno, z)
                przycisk = str(z.get("przycisk") or "left")
                if przycisk not in ("left", "right", "middle"):
                    return {"ok": False, "blad": "przycisk: left, right albo middle"}
                mody = self._mody(z.get("modyfikatory"))
                if typ == "klik":
                    try:
                        ile = max(1, min(3, int(z.get("klikniecia") or 1)))
                    except (TypeError, ValueError):
                        ile = 1
                    self._mysz(okno, x, y, przycisk, ile, mody)
                else:
                    zdarzenie = str(z.get("zdarzenie") or "mouseMoved")
                    if zdarzenie not in ("mouseMoved", "mousePressed", "mouseReleased"):
                        return {"ok": False, "blad": "zdarzenie: mouseMoved, mousePressed albo mouseReleased"}
                    maska = {"left": 1, "right": 2, "middle": 4}[przycisk]
                    params = {"type": zdarzenie, "x": x, "y": y, "modifiers": mody,
                              "buttons": maska if z.get("wcisniety") or zdarzenie == "mousePressed" else 0}
                    if zdarzenie != "mouseMoved":
                        params.update(button=przycisk, clickCount=1)
                    self._wejscie(okno, "Input.dispatchMouseEvent", params)
                return {"ok": True}
            if typ == "kolko":
                x, y = self._punkt_wlasciciela(okno, z)
                try:
                    dx, dy = float(z.get("dx") or 0), float(z.get("dy") or 0)
                except (TypeError, ValueError):
                    return {"ok": False, "blad": "dx i dy w pikselach"}
                self._wejscie(okno, "Input.dispatchMouseEvent", {"type": "mouseWheel", "x": x, "y": y,
                                                                 "deltaX": max(-5000.0, min(5000.0, dx)),
                                                                 "deltaY": max(-5000.0, min(5000.0, dy))})
                return {"ok": True}
            if typ == "klawisz":
                self._klawisz(okno, str(z.get("klawisz") or ""), list(z.get("modyfikatory") or []))
                return {"ok": True}
            if typ == "tekst":
                tekst = str(z.get("tekst") or "")[:MAKS_TEKST_WLASCICIELA]
                if tekst:
                    self._wejscie(okno, "Input.insertText", {"text": tekst})
                return {"ok": True, "znaki": len(tekst)}
            return {"ok": False, "blad": "typ: klik, mysz, kolko, klawisz, tekst, adres, wstecz, dalej, odswiez, "
                                         "okno, dialog albo plik"}
        except BladSterownika as e:
            return {"ok": False, "blad": e.tekst}
        except cdp.BladCDP as e:
            return {"ok": False, "blad": f"przeglądarka: {e.tekst[:200]}"}

    # ------------------------------------------------------------------ MCP

    def wywolaj(self, nazwa: str, args: dict, konfig: dict) -> dict:
        """Jedno narzędzie MCP; wynik w formacie tools/call (content, structuredContent, isError)."""
        args = args if isinstance(args, dict) else {}
        if nazwa in DZIALANIA_AGENTA:
            # wybór pliku z wcześniejszego działania (albo kliknięcia właściciela) nie należy do tego wywołania;
            # stronę, która czeka na plik, pokazuje dalej get_window_state (file_chooser)
            for o in self.okna():
                o.wybor_pliku = None
        try:
            if nazwa == "get_window_state":
                return self.get_window_state(args, konfig)
            if nazwa in ("click", "double_click", "right_click"):
                return self.click(args, nazwa)
            if nazwa == "drag":
                return self.drag(args)
            if nazwa == "scroll":
                return self.scroll(args)
            if nazwa == "type_text":
                return self.type_text(args)
            if nazwa == "press_key":
                return self.press_key(args)
            if nazwa == "hotkey":
                return self.press_key(args, hotkey=True)
            if nazwa == "set_value":
                return self.set_value(args)
            if nazwa == "launch_app":
                return self.launch_app(args)
            if nazwa == "kill_app":
                return self.kill_app(args)
            if nazwa == "bring_to_front":
                return self.bring_to_front(args)
            if nazwa == "list_windows":
                return self.list_windows(args)
            if nazwa == "list_apps":
                return self.list_apps(args)
            if nazwa == "get_desktop_state":
                return self.get_desktop_state(args, konfig)
            if nazwa == "get_screen_size":
                okno = self._okno_z(args, wymagaj=False)
                sz, wy = okno.rozmiar if okno else przegladarka.EKRAN
                return _wynik(f"{round(sz)}x{round(wy)}", width=round(sz), height=round(wy))
            if nazwa == "set_config":
                for k in ("capture_scope", "capture_mode", "max_image_dimension"):
                    if args.get("key") == k:
                        konfig[k] = args.get("value")
                    elif k in args:
                        konfig[k] = args[k]
                return _wynik("ustawione", config=dict(konfig))
            if nazwa == "get_config":
                return _wynik("konfiguracja", **dict(konfig))
            if nazwa in ("start_session", "end_session", "set_agent_cursor_enabled", "set_agent_cursor_motion",
                         "set_agent_cursor_theme"):
                return _wynik("ok", session=args.get("session"))
            return _blad("narzedzie", f"narzędzia {nazwa} sterownik CDP nie ma")
        except BladSterownika as e:
            return _blad(e.kod, e.tekst)
        except cdp.KoniecPrzegladarki:
            return _blad("przegladarka", "przeglądarka Jarva nie działa (usługa uruchomi ją ponownie)")
        except cdp.BladCDP as e:
            return _blad("cdp", f"przeglądarka: {e.tekst[:200]}")

    def obsluz_mcp(self, msg: dict, konfig: dict) -> dict | None:
        """Wiadomość JSON-RPC MCP od wejścia; odpowiedź (None dla powiadomień)."""
        ident, metoda = msg.get("id"), msg.get("method")
        if ident is None or metoda is None:
            return None
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        if metoda == "initialize":
            wynik = {"protocolVersion": str(params.get("protocolVersion") or "2025-06-18"),
                     "capabilities": {"tools": {"listChanged": False}},
                     "serverInfo": {"name": "jarvo-komputer-cdp", "version": WERSJA}, "instructions": INSTRUKCJE}
        elif metoda == "ping":
            wynik = {}
        elif metoda == "tools/list":
            wynik = {"tools": NARZEDZIA}
        elif metoda == "tools/call":
            wynik = self.wywolaj(str(params.get("name") or ""), params.get("arguments") or {}, konfig)
        else:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"metoda {metoda}"}}
        return {"jsonrpc": "2.0", "id": ident, "result": wynik}


# ---------------------------------------------------------------------- opis narzędzi (tools/list)

def _schemat(**wlasnosci) -> dict:
    return {"type": "object", "properties": wlasnosci, "additionalProperties": True}


_INT, _NUM, _STR = {"type": "integer"}, {"type": "number"}, {"type": "string"}
_TRYB = {"type": "string", "enum": ["background", "foreground"]}
_CEL = dict(pid=_INT, window_id=_INT, element_index=_INT, element_token=_STR, snapshot_id=_STR, x=_NUM, y=_NUM,
            session=_STR, delivery_mode=_TRYB)
_MOD = {"type": "array", "items": _STR}
NARZEDZIA = [
    {"name": "list_apps", "description": "Uruchomione aplikacje (przeglądarka Jarva).", "inputSchema": _schemat(
        session=_STR)},
    {"name": "list_windows", "description": "Okna (karty) przeglądarki Jarva.", "inputSchema": _schemat(
        on_screen_only={"type": "boolean"}, pid=_INT, session=_STR)},
    {"name": "get_window_state", "description": "Drzewo elementów okna i zrzut.", "inputSchema": _schemat(
        pid=_INT, window_id=_INT, session=_STR, max_elements=_INT, include_screenshot={"type": "boolean"},
        query=_STR), "capabilities": ["accessibility.element_tokens"]},
    {"name": "get_desktop_state", "description": "Zrzut aktywnego okna.", "inputSchema": _schemat(session=_STR)},
    {"name": "get_screen_size", "description": "Rozmiar obszaru strony.", "inputSchema": _schemat(session=_STR)},
    {"name": "get_config", "description": "Ustawienia sesji.", "inputSchema": _schemat(session=_STR)},
    {"name": "set_config", "description": "capture_scope, capture_mode, max_image_dimension.",
     "inputSchema": _schemat(key=_STR, value={}, session=_STR, capture_scope=_STR, capture_mode=_STR,
                             max_image_dimension=_INT)},
    {"name": "start_session", "description": "Początek sesji.", "inputSchema": _schemat(session=_STR)},
    {"name": "end_session", "description": "Koniec sesji.", "inputSchema": _schemat(session=_STR)},
    {"name": "set_agent_cursor_enabled", "description": "Kursor agenta (bez znaczenia w przeglądarce).",
     "inputSchema": _schemat(enabled={"type": "boolean"}, cursor_id=_STR, session=_STR)},
    {"name": "bring_to_front", "description": "Okno na wierzch.", "inputSchema": _schemat(pid=_INT, window_id=_INT)},
    {"name": "click", "description": "Klik elementem albo w punkt.", "inputSchema": _schemat(
        **_CEL, button={"type": "string", "enum": ["left", "right", "middle"]}, count=_INT, modifier=_MOD),
     "capabilities": ["accessibility.element_tokens", "input.delivery_mode"]},
    {"name": "double_click", "description": "Podwójny klik.", "inputSchema": _schemat(**_CEL, modifier=_MOD),
     "capabilities": ["accessibility.element_tokens", "input.delivery_mode"]},
    {"name": "right_click", "description": "Prawy klik.", "inputSchema": _schemat(**_CEL, modifier=_MOD),
     "capabilities": ["accessibility.element_tokens", "input.delivery_mode"]},
    {"name": "drag", "description": "Przeciągnięcie.", "inputSchema": _schemat(
        pid=_INT, window_id=_INT, from_x=_NUM, from_y=_NUM, to_x=_NUM, to_y=_NUM, from_element=_INT,
        to_element=_INT, snapshot_id=_STR, button=_STR, modifier=_MOD, session=_STR, delivery_mode=_TRYB),
     "capabilities": ["input.delivery_mode"]},
    {"name": "scroll", "description": "Przewijanie.", "inputSchema": _schemat(
        **_CEL, direction={"type": "string", "enum": ["up", "down", "left", "right"]}, amount=_INT, modifier=_MOD),
     "capabilities": ["input.scroll.coordinates", "input.delivery_mode"]},
    {"name": "type_text", "description": "Pisanie w pole z fokusem albo we wskazany element.", "inputSchema": _schemat(
        **_CEL, text=_STR), "capabilities": ["input.delivery_mode"]},
    {"name": "press_key", "description": "Klawisz z modyfikatorami.", "inputSchema": _schemat(
        **_CEL, key=_STR, modifiers=_MOD), "capabilities": ["input.delivery_mode"]},
    {"name": "hotkey", "description": "Skrót klawiszowy.", "inputSchema": _schemat(
        pid=_INT, window_id=_INT, keys=_MOD, session=_STR, delivery_mode=_TRYB),
     "capabilities": ["input.delivery_mode"]},
    {"name": "set_value", "description": "Wartość pola albo listy wyboru.", "inputSchema": _schemat(
        pid=_INT, window_id=_INT, element_index=_INT, element_token=_STR, snapshot_id=_STR, value=_STR,
        session=_STR), "capabilities": ["accessibility.element_tokens"]},
    {"name": "launch_app", "description": "Chromium z adresami http(s) w nowych kartach.", "inputSchema": _schemat(
        name=_STR, bundle_id=_STR, urls=_MOD, session=_STR, launch_path=_STR, additional_arguments=_MOD,
        creates_new_application_instance={"type": "boolean"})},
    {"name": "kill_app", "description": "Zamyka karty przeglądarki Jarva.", "inputSchema": _schemat(pid=_INT)},
]
