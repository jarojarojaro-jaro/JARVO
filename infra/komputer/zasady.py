"""Twarde zasady Komputera Jarva (etap K2, docs/KOMPUTER.md §6).

Czyste funkcje bez wejścia i wyjścia: wejscie.py woła `ocen` przy każdym wywołaniu narzędzia sterownika ekranu,
zanim sterownik je dostanie, i `ukryj_sekrety` na każdej odpowiedzi, zanim zobaczy ją agent.

Decyzje:
  tak         przepuść (także logowanie, rejestracja, „Continue with Google”, zgoda OAuth, hasło, kod 2FA i SMS,
              CAPTCHA),
  odmowa      zakazane zawsze (narzędzie wyłączone, sekret w tekście, zła aplikacja),
  czlowiek    krok nieodwracalny bez zgody właściciela w karcie (Zgody, ctx.zgody, komputer/zgoda_karty.py):
              płatność, zakup, subskrypcja, karta i BLIK (`platnosc`), wysyłka (`wysylka`; formularz logowania
              i rejestracji bez zgody),
              publikacja (`publikacja`), usunięcie konta (`usuniecie_konta`); ze zgodą przechodzi,
  wstrzymane  Komputer zatrzymany (właściciel: jarvo komputer pauza; Operator: czeka na właściciela);
              patrzeć wolno, działać nie, wznawia tylko właściciel.
Przy dwóch sesjach naraz zmieniać ekran może jedna (odmowa `zajete`, wejscie.py: Ekran.zajmij).
Działanie z delivery_mode foreground (klawiatura, przewijanie, przeciąganie i podwójny klik na pulpicie X11 mają tylko
tę drogę) przechodzi tylko w oknie, które już jest aktywne: wejście sprawdza cel i pole z fokusem w tym oknie,
a przełączenie okna przez sterownik posłałoby klawisze tam, gdzie nikt nie patrzył.

Cel działania (pole, przycisk) opisuje słownik z wejscie.py: rola i nazwa z drzewa dostępności, atrybuty HTML
z AT-SPI (tag, html-input-name, text-input-type), przodkowie (rola, nazwa) do kilku poziomów w górę i przy polach
przyciski formularza, w którym pole leży (Enter w polu wysyła formularz); natywnie też pola formularza i jego nazwa
(`pola_formularza`, `opis_formularza`: formularz logowania).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol
from urllib.parse import urlsplit

TAK, ODMOWA, CZLOWIEK, WSTRZYMANE = "tak", "odmowa", "czlowiek", "wstrzymane"

# Narzędzia sterownika (cua-driver 0.21.0, tools/list) w trzech grupach. Czego tu nie ma, tego agent nie dostanie:
# page i browser_* (JavaScript i DevTools), schowek (hasło skopiowane przez właściciela), mouse_button_down/up
# i mouse_drag (klik poza zasadami), nagrywanie i odtwarzanie (działania poza wejściem), install_ffmpeg,
# check_for_update (sieć) oraz każde nowe narzędzie z kolejnych wersji, dopóki go nie przejrzymy.
ODCZYT = frozenset({
    "list_apps", "list_windows", "get_window_state", "verify_state", "get_screen_size", "get_desktop_state",
    "get_cursor_position", "get_agent_cursor_state", "check_permissions", "health_report", "get_config",
    "get_accessibility_tree", "zoom", "get_session", "list_sessions", "get_session_state",
    "wait_for",                     # sterownik CDP: czekanie na tekst albo adres, bez działania na stronie
})
SESJA = frozenset({
    "start_session", "end_session", "escalate_session", "set_agent_cursor_enabled", "set_agent_cursor_motion",
    "set_agent_cursor_theme", "set_config", "bring_to_front", "set_window_frame", "move_cursor",
})
DZIALANIA = frozenset({
    "click", "double_click", "right_click", "drag", "scroll", "type_text", "press_key", "hotkey", "set_value",
    "launch_app", "kill_app", "invoke_menu",
    "navigate",                     # sterownik CDP: karta pod adres (zasady jak tekst w pasku adresu)
})
DOSTEPNE = ODCZYT | SESJA | DZIALANIA
# zmieniają tylko stan sesji sterownika, nie ekran: wolno je też przy pauzie
SESJA_BEZ_EKRANU = frozenset({"start_session", "end_session", "escalate_session", "set_config",
                              "set_agent_cursor_enabled", "set_agent_cursor_motion", "set_agent_cursor_theme"})

# zmieniają ekran: przy dwóch sesjach naraz działa tylko jedna (wejscie.py, Ekran.zajmij)
ZMIANY_EKRANU = DZIALANIA | (SESJA - SESJA_BEZ_EKRANU)
# odmowy, po których agent czeka i próbuje znowu (nie szuka innej drogi)
CZEKAJ = frozenset({"zajete", "limit"})

KLUCZE_KONFIGURACJI = frozenset({"capture_scope", "capture_mode", "max_image_dimension"})
PRZEGLADARKA = re.compile(r"^(chromium|chromium[- ]browser|chromium web browser|chromium\.desktop)$", re.I)
PROGRAM_PRZEGLADARKI = "/usr/lib/chromium/chromium"

ROLE_DZIALANIA = frozenset({"push button", "button", "link", "menu item", "check menu item", "radio menu item",
                            "toggle button", "image map", "page tab", "check box", "radio button"})
ROLE_HASLA = frozenset({"password text"})


def _wzorce(*w: str) -> re.Pattern:
    return re.compile(r"(?<!\w)(?:" + "|".join(w) + r")(?!\w)", re.I)


# Napisy na przyciskach i linkach w czterech kategoriach zgody właściciela (linia ZGODA WŁAŚCICIELA w karcie,
# komputer/zgoda_karty.py). Szukamy w całej etykiecie („Kup teraz za 129 zł”), z granicami słów, po polsku
# i po angielsku.
_PLATNOSC = (
    r"kup(?:uj[eę])?", r"zam[oó]w(?:ienie)?", r"zamawiam", r"z[lł][oó][zż] zam[oó]wienie", r"zap[lł]a[cć]",
    r"p[lł]ac[eę]", r"zap[lł]ac[eę]", r"op[lł]a[cć]", r"przejd[zź] do (?:p[lł]atno[sś]ci|kasy)",
    r"p[lł]atno[sś][cć]", r"potwierd[zź] (?:zakup|p[lł]atno[sś][cć]|zam[oó]wienie|przelew)", r"blik",
    r"przelew", r"przelej", r"wp[lł]a[cć]", r"do[lł]aduj", r"subskrybuj", r"wykup", r"wesprzyj",
    r"darowizn[aęy]", r"dodaj kart[eęy]", r"buy", r"purchase", r"pay", r"check ?out",
    r"place (?:your )?order", r"(?:complete|confirm|submit) (?:order|payment|purchase)", r"subscribe",
    r"donate", r"add (?:a )?(?:payment|card)", r"proceed to (?:checkout|payment)", r"top ?up",
)
_USUNIECIE_KONTA = (r"usu[nń] konto", r"delete (?:my )?account", r"zamknij konto", r"close (?:my )?account")
_PUBLIKACJA = (r"opublikuj", r"publikuj", r"publish", r"post", r"tweet", r"udost[eę]pnij", r"share")
_WYSYLKA = (r"wy[sś]lij", r"prze[sś]lij", r"send", r"submit")
# logowanie, rejestracja i zgody na dostęp (OAuth): Komputer robi je sam; wzorce zostają w WRAZLIWE dla Rąk Jarva
# (komputer/rece/bramka.py), a LOGOWANIE (z weryfikacją) rozpoznaje formularz logowania (wysyłka bez zgody)
_LOGOWANIE = (
    r"zaloguj(?: si[eę])?", r"logowanie", r"zarejestruj(?: si[eę])?", r"za[lł][oó][zż] konto",
    r"utw[oó]rz konto", r"log ?in", r"sign ?in", r"sign ?up", r"register", r"create (?:an )?account",
    r"continue with (?:google|apple|facebook|microsoft)",
    r"kontynuuj (?:z|przez) (?:google|apple|facebook|microsoft)", r"autoryzuj", r"authori[sz]e",
)

# kategorie zgody w kolejności ważności: etykieta z kilku kategorii („Zapłać i wyślij”) należy do pierwszej
KATEGORIE = ("platnosc", "usuniecie_konta", "publikacja", "wysylka")
OPIS_KATEGORII = {"platnosc": "płatność, zakup, subskrypcja, darowizna, karta", "usuniecie_konta": "usunięcie konta",
                  "publikacja": "publikacja", "wysylka": "wysyłka"}
WZORCE_KATEGORII = {"platnosc": _wzorce(*_PLATNOSC), "usuniecie_konta": _wzorce(*_USUNIECIE_KONTA),
                    "publikacja": _wzorce(*_PUBLIKACJA), "wysylka": _wzorce(*_WYSYLKA)}
LOGOWANIE = _wzorce(*_LOGOWANIE, r"rejestracja", r"registration", r"continue with github",
                    r"kontynuuj (?:z|przez) github", r"weryfikacja", r"verification", r"verify", r"zweryfikuj")

# Ręce Jarva (ekran właściciela) i okna JavaScript: wszystko powyżej, także logowanie, zostawia właścicielowi.
WRAZLIWE = _wzorce(*_PLATNOSC, *_LOGOWANIE, *_WYSYLKA, *_PUBLIKACJA, *_USUNIECIE_KONTA)
# krótkie zgody, groźne tylko jako cała etykieta (ekran zgody OAuth); „Zezwól na wszystkie” to baner ciasteczek
WRAZLIWE_CALE = re.compile(r"^\s*(?:allow|allow access|zezw[oó]l|zezw[oó]l na dost[eę]p|grant access)\s*$", re.I)

# Ręce Jarva: pola, do których agent nie pisze (hasła, karty, kody jednorazowe, PIN, tokeny).
POLE_WRAZLIWE = _wzorce(
    r"has[lł]o", r"password", r"passwd", r"pass(?:code|phrase)", r"pin", r"karta", r"karty", r"card",
    r"cc-?(?:number|num|csc|exp)", r"cardnumber", r"cvv2?", r"cvc", r"csc", r"blik", r"otp", r"2fa",
    r"two.?factor", r"one.?time", r"verification code", r"security code", r"token",
    r"kod (?:bezpiecze[nń]stwa|cvv|cvc|blik|sms|weryfikacyjny|jednorazowy|autoryzacyjny|potwierdzaj[aą]cy|"
    r"z aplikacji|dost[eę]pu)",
)
# Komputer Jarva: pola płatności (karta, CVV, BLIK) tylko ze zgodą `platnosc`; hasła i kody agent wpisuje sam.
POLE_PLATNOSCI = _wzorce(
    r"karta", r"karty", r"card", r"cc-?(?:number|num|csc|exp|name)", r"cardnumber", r"cvv2?", r"cvc", r"csc",
    r"blik", r"security code", r"expiry", r"expiration", r"data wa[zż]no[sś]ci", r"numer karty",
    r"kod (?:bezpiecze[nń]stwa|cvv|cvc|blik)",
)
# Pole hasła albo kodu (formularz logowania, rejestracji, weryfikacji): wysyłka bez zgody.
POLE_LOGOWANIA = _wzorce(
    r"has[lł]o", r"password", r"passwd", r"pass(?:code|phrase)", r"otp", r"2fa", r"mfa", r"totp",
    r"two.?factor", r"one.?time(?:.code)?", r"verification code", r"kod (?:sms|weryfikacyjny|jednorazowy|"
    r"autoryzacyjny|potwierdzaj[aą]cy|z aplikacji|dost[eę]pu)", r"current.password", r"new.password",
)
# Nazwa, id albo adres (action) formularza logowania i rejestracji, np. „login_form”, „/session”, „/signup”.
FORMULARZ_LOGOWANIA = re.compile(r"log[ _-]?in|sign[ _-]?(?:in|up)|regist|rejestr|logowan|zaloguj|zarejestr|"
                                 r"create[ _-]?account|utw[oó]rz konto|za[lł][oó][zż] konto|(?<![a-z])auth(?![a-z])|"
                                 r"oauth|authenticat|authori[sz]|verif|weryfik|session|otp|2fa|mfa|two[ _-]?factor|"
                                 r"password|has[lł]o", re.I)

# Sekrety w tekście: wpisanie to odmowa, w odpowiedzi sterownika zastępujemy je znacznikiem.
SEKRETY = re.compile("|".join([
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)",
    # wyraźne przedrostki także doklejone do litery (np. „KEYsk-ant-…”); ogólne sk- tylko na granicy słowa (desk-…)
    r"sk-(?:ant-|proj-|or-v1-)[A-Za-z0-9_-]{20,}", r"\bsk-[A-Za-z0-9_-]{20,}",
    r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}", r"glpat-[A-Za-z0-9_-]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b", r"\bASIA[0-9A-Z]{16}\b", r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    r"\bAIza[0-9A-Za-z_-]{35}\b", r"\bhf_[A-Za-z0-9]{30,}", r"\bnpm_[A-Za-z0-9]{36}\b",
    r"\b(?:rk|sk|pk)_live_[A-Za-z0-9]{20,}", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    r"\b\d{6,12}:AA[A-Za-z0-9_-]{30,}",                     # token bota Telegrama (klucz floty)
]))
KARTA = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
ZNACZNIK = "[ukryte przez Komputer Jarva]"
# cel, którego wejście nie umie sprawdzić (token spoza migawek sesji, punkt bez AT-SPI): działanie nie przechodzi
NIEZNANY = {"rola": "", "nazwa": "", "nieznany": True}
ADRES_ZAKAZANY = re.compile(r"\b(?:javascript|vbscript|data|file|chrome|devtools|view-source)\s*:", re.I)

KLAWISZE_ENTER = frozenset({"return", "enter", "kp_enter", "iso_enter", "\n", "\r"})
KLAWISZE_AKTYWUJACE = KLAWISZE_ENTER | {"space", "kp_space", " "}
SKROTY_ZAKAZANE = frozenset({
    ("ctrl", "shift", "i"), ("ctrl", "shift", "j"), ("ctrl", "shift", "c"), ("f12",), ("ctrl", "shift", "delete"),
    ("ctrl", "shift", "o"), ("alt", "f2"),
})
MODYFIKATORY = {"control": "ctrl", "ctl": "ctrl", "ctrl": "ctrl", "shift": "shift", "alt": "alt", "option": "alt",
                "meta": "super", "cmd": "super", "command": "super", "super": "super", "win": "super",
                "control_l": "ctrl", "control_r": "ctrl", "shift_l": "shift", "shift_r": "shift", "alt_l": "alt",
                "alt_r": "alt", "super_l": "super", "super_r": "super", "meta_l": "super", "meta_r": "super"}
MODY = frozenset({"ctrl", "shift", "alt", "super"})
# Alt (bez Ctrl i Super) z literą, cyfrą albo znakiem to w Chromium accesskey strony: klik przycisku (np. Wyślij,
# Opublikuj) bez sprawdzenia jego napisu, a Blink pomija przy tym Shift. Z Altem wolno więc tylko klawisze nawigacji.
ALT_DOZWOLONE = frozenset({"left", "right", "up", "down", "home", "end", "page_up", "page_down", "pageup", "pagedown",
                           "prior", "next", "tab", "escape", "esc", "backspace", "delete", "insert"}
                          | {f"f{i}" for i in range(1, 12)})


@dataclass
class Werdykt:
    decyzja: str
    kod: str = ""
    powod: str = ""
    cel: str = ""                       # opis celu do dziennika (rola i nazwa), bez wpisywanego tekstu
    dane: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # powód trafia do agenta, cel i powód do dziennika: napisy z ekranu (nazwy, adresy) bez sekretów
        self.powod = ukryj_sekrety(self.powod)[0]
        self.cel = ukryj_sekrety(self.cel)[0]

    @property
    def wolno(self) -> bool:
        return self.decyzja == TAK


class Kontekst(Protocol):
    """To, co wejscie.py wie o ekranie w chwili wywołania."""
    wstrzymane: bool
    powod_pauzy: str                  # kto i dlaczego wstrzymał (np. Operator czeka na właściciela)

    def cel(self, nazwa: str, args: dict) -> Optional[dict]:
        """Element, w który trafi działanie (z migawki sterownika albo z AT-SPI w punkcie), None gdy nieznany."""

    def fokus(self, args: dict) -> Optional[dict]:
        """Element z fokusem klawiatury w oknie celu (zdarzenia AT-SPI), None gdy nieznany."""

    def program(self, pid: int) -> str:
        """Ścieżka programu procesu (do kill_app)."""

    def aktywne_okno(self) -> Optional[int]:
        """Okno z fokusem systemu (X11 _NET_ACTIVE_WINDOW, ten sam numer co window_id sterownika), None gdy nieznane."""

    def pid_okna(self, okno: int) -> Optional[int]:
        """Proces, do którego należy okno (X11 _NET_WM_PID), None gdy nieznany."""

    def zgody(self) -> frozenset:
        """Kategorie zgody właściciela z karty, nad którą pracuje agent (komputer/zgoda_karty.py). Czyta je zaufany
        kod wejścia z treści karty w kanban.db, nigdy strona ani argumenty modelu. Kontekst bez tej metody: brak zgód.
        Kategorie spoza KATEGORIE (np. `konto`) zasady Komputera pomijają: logowanie i rejestracja przechodzą bez
        nich."""


class Zgody:
    """Zgody właściciela dla jednej oceny: ctx.zgody() czytane raz i tylko wtedy, gdy działanie ich potrzebuje;
    `uzyte` trafiają do dziennika przy werdykcie tak."""

    def __init__(self, ctx) -> None:
        self._ctx = ctx
        self._z: Optional[frozenset] = None
        self.uzyte: list[str] = []

    def ma(self, kategoria: str) -> bool:
        if self._z is None:
            czytaj = getattr(self._ctx, "zgody", None)
            try:
                z = czytaj() if callable(czytaj) else frozenset()
            except Exception:  # noqa: BLE001 - nieczytelna zgoda to brak zgody, nigdy przepuszczenie
                z = frozenset()
            self._z = frozenset(k for k in (z or ()) if k in KATEGORIE)
        if kategoria in self._z:
            if kategoria not in self.uzyte:
                self.uzyte.append(kategoria)
            return True
        return False

    def brak(self, kategorie) -> Optional[str]:
        """Pierwsza kategoria bez zgody właściciela albo None (wszystkie mają zgodę)."""
        return next((k for k in kategorie if not self.ma(k)), None)



def luhn(cyfry: str) -> bool:
    suma, podwoj = 0, False
    for c in reversed(cyfry):
        d = int(c)
        if podwoj:
            d = d * 2 - 9 if d > 4 else d * 2
        suma += d
        podwoj = not podwoj
    return suma % 10 == 0


def numery_kart(tekst: str) -> list[str]:
    wynik = []
    for m in KARTA.finditer(tekst):
        cyfry = re.sub(r"\D", "", m.group())
        if 13 <= len(cyfry) <= 19 and luhn(cyfry) and len(set(cyfry)) > 1:
            wynik.append(m.group())
    return wynik


def ukryj_sekrety(tekst: str) -> tuple[str, int]:
    """Zastępuje klucze, tokeny, klucze prywatne i numery kart znacznikiem; zwraca (tekst, liczba zamian)."""
    tekst, n = SEKRETY.subn(ZNACZNIK, tekst)
    for numer in numery_kart(tekst):
        tekst = tekst.replace(numer, ZNACZNIK)
        n += 1
    return tekst, n


def ukryj_w_strukturze(obj: Any) -> tuple[Any, int]:
    """ukryj_sekrety w każdym napisie słownika lub listy (structuredContent sterownika); pola value w polach
    haseł znikają zawsze."""
    if isinstance(obj, str):
        return ukryj_sekrety(obj)
    if isinstance(obj, list):
        n, wynik = 0, []
        for x in obj:
            y, k = ukryj_w_strukturze(x)
            wynik.append(y)
            n += k
        return wynik, n
    if isinstance(obj, dict):
        n, wynik = 0, {}
        haslo = str(obj.get("role", "")).lower() in ROLE_HASLA
        for k, v in obj.items():
            if haslo and k == "value" and v:
                wynik[k], n = ZNACZNIK, n + 1
                continue
            y, m = ukryj_w_strukturze(v)
            wynik[k] = y
            n += m
        return wynik, n
    return obj, 0


def _napis(tekst: str) -> str:
    """Napis do porównań: NFKC (pełnoszerokie i ozdobne litery jak zwykłe), bez znaków niewidocznych (Cf),
    obiektów zastępczych i nadmiarowych spacji."""
    tekst = unicodedata.normalize("NFKC", tekst)
    tekst = "".join(z for z in tekst if unicodedata.category(z) != "Cf")
    return re.sub(r"[￼\s]+", " ", tekst).strip()


def _etykieta(el: Optional[dict]) -> str:
    if not el:
        return ""
    return _napis(str(el.get("nazwa") or el.get("label") or ""))


def _pokaz(tekst: str, n: int) -> str:
    """Napis z ekranu do powodu albo dziennika: sekrety ukryte przed przycięciem (ucięty klucz nie pasuje do wzorca)."""
    return ukryj_sekrety(tekst)[0][:n]


def opis(el: Optional[dict]) -> str:
    if not el:
        return "nieznany cel"
    return f"{el.get('rola') or el.get('role') or '?'} „{_pokaz(_etykieta(el), 60)}”"


def _wrazliwa_etykieta(tekst: str) -> bool:
    """Etykieta z dowolnej grupy wrażliwej, także logowania i zgody OAuth (Ręce Jarva, okna JavaScript)."""
    tekst = _napis(tekst)
    return bool(tekst) and (bool(WRAZLIWE.search(tekst)) or bool(WRAZLIWE_CALE.match(tekst)))


def kategoria(tekst: str) -> Optional[str]:
    """Kategoria zgody (KATEGORIE) napisu przycisku, linku albo pozycji menu; None: agent klika sam."""
    tekst = _napis(tekst)
    if not tekst:
        return None
    return next((k for k in KATEGORIE if WZORCE_KATEGORII[k].search(tekst)), None)


def _rola(el: dict) -> str:
    return str(el.get("rola") or el.get("role") or "").lower()


def formularz_logowania(el: Optional[dict]) -> bool:
    """Element leży w formularzu logowania, rejestracji albo weryfikacji (jego wysyłka nie potrzebuje zgody):
    formularz bez pola wieloliniowego (wiadomości), w którym jest pole hasła albo kodu jednorazowego, przycisk
    logowania albo rejestracji, albo którego nazwa, id lub adres (action), nazwa w drzewie dostępności albo tytuł
    strony mówią o logowaniu lub rejestracji."""
    if not el or not w_formularzu(el):
        return False
    pola = [p for p in el.get("pola_formularza") or [] if isinstance(p, dict)]
    if wieloliniowe(el) or any(str(p.get("tag") or "").lower() == "textarea" or p.get("wieloliniowy") for p in pola):
        return False
    atr = el.get("atrybuty") or {}
    if _rola(el) in ROLE_HASLA or str(atr.get("text-input-type", "")).lower() == "password":
        return True
    for p in pola:
        if str(p.get("typ") or "").lower() == "password":
            return True
        if any(a in str(p.get("autocomplete") or "").lower() for a in ("current-password", "new-password",
                                                                       "one-time-code")):
            return True
        for k in ("nazwa", "etykieta", "placeholder"):
            tekst = _napis(str(p.get(k) or "")).replace("_", " ")
            if tekst and POLE_LOGOWANIA.search(tekst):
                return True
    forma = el.get("opis_formularza") if isinstance(el.get("opis_formularza"), dict) else {}
    if any(FORMULARZ_LOGOWANIA.search(_napis(str(forma.get(k) or ""))) for k in ("nazwa", "id", "action", "etykieta")):
        return True
    for p in el.get("formularz") or []:
        if LOGOWANIE.search(_etykieta(p)):
            return True
    return any(_rola(p) in ("form", "document web") and LOGOWANIE.search(_etykieta(p))
               for p in el.get("sciezka_przodkow") or el.get("przodkowie") or [])


def przycisk_wrazliwy(el: Optional[dict]) -> Optional[tuple[str, str]]:
    """(etykieta, kategoria) przycisku albo linku, którego kliknięcie potrzebuje zgody właściciela: cel i jego
    przodkowie z rolą działania. Wysyłka formularza logowania, rejestracji i weryfikacji zgody nie potrzebuje."""
    if not el:
        return None
    kandydaci = [el] + [p for p in (el.get("przodkowie") or [])[:4] if _rola(p) in ROLE_DZIALANIA]
    for p in kandydaci:
        kat = kategoria(_etykieta(p))
        if kat and not (kat == "wysylka" and formularz_logowania(el)):
            return _etykieta(p), kat
    return None


def pole_platnosci(el: Optional[dict]) -> Optional[str]:
    """Powód, dla którego do pola pisze agent tylko ze zgodą `platnosc` (karta, CVV, BLIK), albo None. Hasła
    i kody (2FA, SMS, weryfikacja) agent wpisuje sam."""
    if not el:
        return None
    if el.get("nieznany"):
        return "pole, którego Komputer nie umie sprawdzić"
    atr = el.get("atrybuty") or {}
    for tekst in (_etykieta(el), str(atr.get("html-input-name", "")), str(atr.get("autocomplete", "")),
                  str(atr.get("placeholder-text", ""))):
        tekst = _napis(tekst)
        if tekst and POLE_PLATNOSCI.search(tekst.replace("_", " ")):
            return f"pole „{_pokaz(tekst, 40)}”"
    return None


def _skrot(klawisze: list) -> tuple:
    norm = []
    for k in klawisze:
        k = str(k).strip().lower()
        norm.append(MODYFIKATORY.get(k, k))
    mod = sorted(k for k in norm if k in {"ctrl", "shift", "alt", "super"})
    reszta = [k for k in norm if k not in {"ctrl", "shift", "alt", "super"}]
    return tuple(mod + reszta)


def _czlowiek(kod: str, powod: str, cel: str = "", kategoria: str = "") -> Werdykt:
    return Werdykt(CZLOWIEK, kod, powod, cel, {"kategoria": kategoria} if kategoria else {})


def _bez_zgody(kategoria: str) -> str:
    return f"{OPIS_KATEGORII[kategoria]}: tylko ze zgodą właściciela `{kategoria}` w karcie"


def _odmowa(kod: str, powod: str, cel: str = "") -> Werdykt:
    return Werdykt(ODMOWA, kod, powod, cel)


def _sprawdz_tekst(tekst: str, pole: Optional[dict], z: Zgody) -> Optional[Werdykt]:
    if SEKRETY.search(tekst):
        return _odmowa("sekret", "tekst wygląda na klucz, token albo klucz prywatny; sekretów nie wpisujemy", opis(pole))
    if numery_kart(tekst) and not z.ma("platnosc"):
        return _czlowiek("karta", f"numer karty płatniczej ({_bez_zgody('platnosc')})", opis(pole), "platnosc")
    if ADRES_ZAKAZANY.search(tekst):
        return _odmowa("adres", "adresy javascript:, data:, file:, chrome: i devtools: są wyłączone", opis(pole))
    powod = pole_platnosci(pole)
    if powod and not z.ma("platnosc"):
        return _czlowiek("pole_wrazliwe", f"{powod}: kartę, CVV i BLIK ({_bez_zgody('platnosc')})", opis(pole),
                         "platnosc")
    return None


def wieloliniowe(el: Optional[dict]) -> bool:
    """Pole, w którym zwykły Enter ma być nową linią: textarea, pole multi-line albo edytowalny element strony
    (contenteditable: czaty, komentarze, edytory). Takie pola często wysyłają wiadomość Enterem albo Ctrl+Enter."""
    if not el:
        return False
    tag = str((el.get("atrybuty") or {}).get("tag", "")).lower()
    stany = {str(s).lower() for s in el.get("stany") or []}
    return tag == "textarea" or "multi-line" in stany or ("editable" in stany and tag not in ("", "input"))


def w_formularzu(el: Optional[dict]) -> Optional[bool]:
    """Czy pole leży w formularzu (role form): True, False albo None, gdy Komputer nie umie tego sprawdzić."""
    if not el or el.get("formularz_nieznany"):
        return None
    if "w_formularzu" in el:
        return bool(el["w_formularzu"])
    return bool(el.get("formularz"))


def formularz_wrazliwy(el: Optional[dict], z: Zgody) -> Optional[tuple[str, str]]:
    """Enter w polu formularza wysyła formularz: (etykieta przycisku tego formularza, kategoria bez zgody), np.
    Zapłać bez `platnosc`, Wyślij bez `wysylka` (w formularzu logowania i rejestracji Wyślij przechodzi); formularz,
    którego nie da się sprawdzić, potrzebuje zgód `platnosc` i `wysylka`; None: Enter wolno."""
    if not el:
        return None
    if w_formularzu(el) is None:
        kat = z.brak(("platnosc", "wysylka"))
        return ("formularz, którego Komputer nie umie sprawdzić", kat) if kat else None
    for p in el.get("formularz") or []:
        if _rola(p) not in {"push button", "button"}:
            continue
        kat = kategoria(_etykieta(p))
        if kat and not (kat == "wysylka" and formularz_logowania(el)) and not z.ma(kat):
            return _etykieta(p), kat
    return None


def _sprawdz_enter(el: Optional[dict], z: Zgody, mody: frozenset = frozenset()) -> Optional[Werdykt]:
    """Enter (także z modyfikatorami i jako nowa linia w type_text) w elemencie z fokusem albo w celu.
    W polu wieloliniowym Shift+Enter to zawsze nowa linia; zwykły Enter i Ctrl/Super+Enter traktujemy jak wysyłkę:
    w formularzu z przyciskiem płatności, wysyłki albo publikacji i w polu poza formularzem (czat, komentarz)
    potrzebuje zgody właściciela. W polu jednowierszowym poza formularzem (wyszukiwarka) i w formularzu logowania
    Enter przechodzi."""
    zly = _sprawdz_aktywacje(el, "Enter na", z)
    if zly:
        return zly
    wiele = wieloliniowe(el)
    wysylka = bool(mody & {"ctrl", "super"})
    if wiele and "shift" in mody and not wysylka:
        return None
    klawisz = "+".join(sorted(mody) + ["Enter"])
    nowa_linia = " (nową linię zrób Shift+Enter)" if wiele else ""
    forma = formularz_wrazliwy(el, z)
    if forma:
        etykieta, kat = forma
        return _czlowiek("formularz_wrazliwy", f"{klawisz} w {opis(el)} wysyła formularz z przyciskiem "
                         f"„{_pokaz(etykieta, 60)}” ({_bez_zgody(kat)}){nowa_linia}", opis(el), kat)
    if w_formularzu(el) is False and (wiele or wysylka) and not z.ma("wysylka"):
        return _czlowiek("wysylka_bez_formularza", f"{klawisz} w {opis(el)} poza formularzem (czat, komentarz, "
                         f"edytor) zwykle wysyła wiadomość ({_bez_zgody('wysylka')}){nowa_linia}", opis(el), "wysylka")
    return None


def _sprawdz_aktywacje(el: Optional[dict], jak: str, z: Zgody) -> Optional[Werdykt]:
    """Klik, Enter albo spacja na elemencie: przycisk bez zgody właściciela albo cel, którego nie da się sprawdzić."""
    if el and el.get("nieznany"):
        return _odmowa("nieznany_cel", f"{jak} elementu, którego Komputer nie umie sprawdzić; zrób świeży stan "
                       "okna (get_window_state) i wskaż element z niego")
    przycisk = przycisk_wrazliwy(el)
    if przycisk and not z.ma(przycisk[1]):
        etykieta, kat = przycisk
        return _czlowiek("przycisk_wrazliwy", f"{jak} „{_pokaz(etykieta, 60)}” ({_bez_zgody(kat)})", opis(el), kat)
    return None


def _wspolrzedne(args: dict) -> bool:
    return args.get("x") is not None and args.get("y") is not None


def _punkt(args: dict) -> bool:
    cel = args.get("target") if isinstance(args.get("target"), dict) else {}
    return _wspolrzedne(args) or (cel.get("x") is not None and cel.get("y") is not None)


def _klik_w_punkt_w_tle(nazwa: str, args: dict) -> bool:
    """Zwykły klik lewym w punkt w tle. cua-driver 0.21.0 (X11) nie klika wtedy w okno: szuka w całym drzewie
    programu (wszystkie okna, także elementy niewidoczne, przewinięte i przycięte) najmniejszego elementu z akcją,
    którego prostokąt we współrzędnych swojego okna zawiera punkt, i wywołuje jego akcję. To może być inny element
    niż ten, który widać w tym punkcie. Klik z modyfikatorem, prawym i podwójny idzie zdarzeniem do okna."""
    if nazwa != "click" or not _punkt(args) or args.get("delivery_mode") == "foreground":
        return False
    try:
        raz = int(args.get("count") or 1) == 1
    except (TypeError, ValueError):
        raz = False
    return raz and str(args.get("button") or "left").lower() == "left" and not args.get("modifier") \
        and args.get("scope") != "desktop"


def _celowane(args: dict) -> bool:
    """Działanie wskazuje element albo punkt (wtedy sterownik najpierw tam klika)."""
    return bool(args.get("element_token")) or args.get("element_index") is not None or _wspolrzedne(args) \
        or args.get("target") is not None


def _adresowanie(nazwa: str, args: dict) -> Optional[Werdykt]:
    if args.get("from_zoom"):
        return _odmowa("zoom", "kliknięcia po powiększeniu są wyłączone; klikaj elementem albo w pełnym zrzucie")
    element = bool(args.get("element_token")) or args.get("element_index") is not None
    if element and (args.get("x") is not None or args.get("y") is not None or args.get("target") is not None):
        return _odmowa("cel", f"{nazwa}: wskaż element albo punkt, nie oba naraz")
    cel = args.get("target")
    if cel is not None and not (isinstance(cel, dict) and set(cel) <= {"element_token", "element_index",
                                                                       "snapshot_id", "x", "y"}):
        return _odmowa("cel", f"{nazwa}: nieznana forma pola target")
    return None


def _na_wierzchu(nazwa: str, args: dict, ctx: Kontekst) -> Optional[Werdykt]:
    """delivery_mode foreground: sterownik wysyła działanie przez globalne wejście (XTest) do okna z fokusem
    systemu, a nieaktywne okno najpierw aktywuje. Wolno tylko w oknie, które już jest aktywne."""
    tryb = args.get("delivery_mode")
    if tryb in (None, "", "background"):
        return None
    if tryb != "foreground":
        return _odmowa("tryb", f"{nazwa}: delivery_mode tylko background albo foreground")
    aktywne = ctx.aktywne_okno()
    if aktywne is None:
        return _odmowa("okno_nieaktywne", "nie wiem, które okno jest aktywne; działaj w tle albo zrób nowy capture")
    if args.get("window_id") is None and nazwa == "scroll":
        # przewijanie całego okna (Hermes wysyła wtedy samo pid): nic nie uruchamia, wystarczy, że aktywne okno
        # należy do tego programu
        if not isinstance(args.get("pid"), int) or ctx.pid_okna(aktywne) != args["pid"]:
            return _odmowa("okno_nieaktywne", "scroll z delivery_mode foreground tylko w programie, którego okno "
                           "jest aktywne")
        return None
    try:
        okno = int(args.get("window_id"))
    except (TypeError, ValueError):
        return _odmowa("okno_nieaktywne", f"{nazwa} z delivery_mode foreground wymaga window_id okna, w którym "
                       "działasz (zrób capture tego okna)")
    if okno != aktywne:
        return _odmowa("okno_nieaktywne", f"{nazwa} z delivery_mode foreground tylko w oknie, które już jest "
                       "aktywne (to okno nie jest); działaj w tle albo poproś właściciela o okno na wierzchu")
    return None


def ocen(nazwa: str, args: Optional[dict], ctx: Kontekst) -> Werdykt:
    """Decyzja dla jednego wywołania narzędzia sterownika. Zgody właściciela (ctx.zgody) czyta tylko krok, który ich
    potrzebuje; werdykt tak, który z nich skorzystał, ma w dzienniku `zgoda` (kategorie)."""
    z = Zgody(ctx)
    w = _ocen(nazwa, args if isinstance(args, dict) else {}, ctx, z)
    if w.wolno and z.uzyte:
        w.dane = {**w.dane, "zgoda": ",".join(z.uzyte)}
    return w


def _ocen(nazwa: str, args: dict, ctx: Kontekst, z: Zgody) -> Werdykt:
    if nazwa not in DOSTEPNE:
        return _odmowa("narzedzie", f"narzędzie {nazwa} jest wyłączone w Komputerze Jarva")
    if nazwa in ODCZYT:
        if args.get("screenshot_out_file"):
            return _odmowa("plik", "zapis zrzutu do pliku jest wyłączony; zrzut wraca w odpowiedzi")
        return Werdykt(TAK)
    if ctx.wstrzymane and nazwa not in SESJA_BEZ_EKRANU:
        powod = getattr(ctx, "powod_pauzy", "") or "właściciel zatrzymał Komputer"
        return Werdykt(WSTRZYMANE, "wstrzymane", f"{powod}; patrzeć wolno, działać nie")
    if nazwa == "set_config":
        klucze = {args.get("key")} if "key" in args else set(args) - {"session"}
        if not klucze or not klucze <= KLUCZE_KONFIGURACJI:
            return _odmowa("konfiguracja", f"set_config: wolno tylko {', '.join(sorted(KLUCZE_KONFIGURACJI))}")
        return Werdykt(TAK)
    if nazwa in SESJA:
        return Werdykt(TAK)

    zle = _na_wierzchu(nazwa, args, ctx) or _adresowanie(nazwa, args)
    if zle:
        return zle

    if nazwa == "launch_app":
        if args.get("launch_path") or args.get("additional_arguments"):
            return _odmowa("aplikacja", "launch_app bez launch_path i additional_arguments (flagi przeglądarki)")
        if not PRZEGLADARKA.match(str(args.get("name") or args.get("bundle_id") or "")):
            return _odmowa("aplikacja", "w Komputerze Jarva uruchamiamy tylko Chromium")
        for u in args.get("urls") or []:
            czesci = urlsplit(str(u))
            if czesci.scheme not in {"http", "https"} or not czesci.netloc:
                return _odmowa("adres", f"launch_app: tylko adresy http i https, nie {_pokaz(str(u), 40)}")
        return Werdykt(TAK, cel=", ".join(urlsplit(str(u)).netloc for u in args.get("urls") or []))

    if nazwa == "navigate":
        # te same zasady co adres wpisany w pasek (tekst: sekrety, karty, javascript:, file:…) i tylko http(s);
        # sieć lokalną i ten komputer odcina potem proxy przeglądarki
        url = str(args.get("url") or "").strip()
        czesci = urlsplit(url)
        if czesci.scheme.lower() not in {"http", "https"} or not czesci.netloc:
            return _odmowa("adres", f"navigate: tylko adresy http i https, nie {_pokaz(url, 40)}")
        return _sprawdz_tekst(url, None, z) or Werdykt(TAK, cel=czesci.hostname or "")

    if nazwa == "kill_app":
        try:
            program = ctx.program(int(args.get("pid")))
        except (TypeError, ValueError):
            program = ""
        if program != PROGRAM_PRZEGLADARKI:
            return _odmowa("aplikacja", "kill_app tylko dla Chromium (pulpit, wejście i sterownik zostają)")
        return Werdykt(TAK, cel="chromium")

    if nazwa == "invoke_menu":
        sciezka = [str(p) for p in args.get("path") or []]
        for p in sciezka:
            kat = kategoria(p)
            if kat and not z.ma(kat):
                return _czlowiek("menu_wrazliwe", f"pozycja menu „{_pokaz(p, 60)}” ({_bez_zgody(kat)})",
                                 " › ".join(sciezka), kat)
        return Werdykt(TAK, cel=_pokaz(" › ".join(sciezka), 80))

    if nazwa in {"scroll", "right_click"}:
        return Werdykt(TAK, cel=opis(ctx.cel(nazwa, args)) if nazwa == "right_click" else "")

    if nazwa in {"click", "double_click"}:
        if not _celowane(args):
            return _odmowa("cel", f"{nazwa} wymaga elementu (element_token) albo punktu (x, y)")
        if nazwa == "click" and str(args.get("button") or "left").lower() == "right":
            return Werdykt(TAK, cel=opis(ctx.cel(nazwa, args)))
        if _klik_w_punkt_w_tle(nazwa, args):
            return _odmowa("punkt_w_tle", "klik w punkt w tle sterownik oddaje najmniejszemu elementowi programu "
                           "w tym miejscu okna, także w innym oknie albo niewidocznemu, a nie temu, co widać; "
                           "kliknij elementem (element_token z get_window_state) albo w punkt z delivery_mode "
                           "foreground w aktywnym oknie")
        el = ctx.cel(nazwa, args)
        return _sprawdz_aktywacje(el, "kliknięcie", z) or Werdykt(TAK, cel=opis(el))

    if nazwa == "drag":
        # przeciągnięcie, które zaczyna się albo kończy na przycisku, jest kliknięciem (puszczenie myszy na tym samym
        # elemencie wywołuje click), więc sprawdzamy oba końce, w punktach albo w elementach migawki
        if args.get("from_element") is not None or args.get("to_element") is not None:
            konce = [{"element_index": args.get(k), "snapshot_id": args.get("snapshot_id")}
                     for k in ("from_element", "to_element")]
        else:
            try:
                konce = [{"x": float(args[f"{k}_x"]), "y": float(args[f"{k}_y"])} for k in ("from", "to")]
            except (KeyError, TypeError, ValueError):
                return _odmowa("cel", "drag wymaga from_x, from_y, to_x, to_y albo from_element i to_element")
        opisy = []
        for koniec in konce:
            el = ctx.cel("click", {**{k: v for k, v in args.items() if k in ("pid", "window_id", "scope")}, **koniec})
            zly = _sprawdz_aktywacje(el, "przeciągnięcie na", z)
            if zly:
                return zly
            opisy.append(opis(el))
        return Werdykt(TAK, cel=" → ".join(opisy))

    if nazwa in {"type_text", "set_value"}:
        tekst = args.get("text") if nazwa == "type_text" else args.get("value")
        tekst = "" if tekst is None else str(tekst)
        if nazwa == "type_text" and any(unicodedata.category(z) == "Cc" and z not in "\n\r" for z in tekst):
            # sterownik pisze \t jako Tab: fokus przeszedłby na następny element (np. „Kup teraz”), a reszta tekstu
            # i Enter trafiłyby tam bez sprawdzenia
            return _odmowa("znak_sterujacy", "Tab i inne znaki sterujące naciśnij osobno (press_key), potem zrób "
                           "nowy stan okna: Tab przenosi fokus na inne pole albo przycisk")
        celowane = nazwa == "set_value" or _celowane(args)
        pole = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
        if pole is not None and pole.get("nieznany") and tekst:
            return _odmowa("nieznany_cel", "nie wiem, w które pole trafi tekst (fokus się zmienił albo drzewo "
                           "dostępności nie odpowiedziało); zrób get_window_state, kliknij pole i pisz")
        if nazwa == "type_text" and (celowane or str((pole or {}).get("rola") or "").lower() in ROLE_DZIALANIA):
            # pisanie w cel to najpierw klik; spacja albo Enter na przycisku z fokusem go uruchamia
            zly = _sprawdz_aktywacje(pole, "kliknięcie przed pisaniem w" if celowane else "pisanie na", z)
            if zly:
                return zly
        if pole is None and tekst.strip():
            # bez znanego pola nie piszemy: tekst mógłby trafić w pole karty, którego nie widzimy
            zly = _sprawdz_tekst(tekst, None, z)
            return zly or _odmowa("brak_fokusu", "nie wiem, w które pole trafi tekst; kliknij najpierw pole, "
                                  "potem pisz")
        zly = _sprawdz_tekst(tekst, pole, z)
        if zly:
            return zly
        if nazwa == "type_text" and ("\n" in tekst or "\r" in tekst):
            srodek = tekst.rstrip("\r\n")
            if ("\n" in srodek or "\r" in srodek) and not wieloliniowe(pole):
                return _odmowa("enter_w_srodku", "w polu jednowierszowym Enter tylko na końcu tekstu: po Enterze "
                               "strona i fokus mogą się zmienić; resztę napisz po nowym stanie okna")
            zly = _sprawdz_enter(pole, z)
            if zly:
                return zly
        return Werdykt(TAK, cel=opis(pole), dane={"znaki": len(tekst)})

    if nazwa in {"press_key", "hotkey"}:
        klawisze = [args.get("key")] + list(args.get("modifiers") or []) if nazwa == "press_key" \
            else list(args.get("keys") or [])
        skrot = _skrot([k for k in klawisze if k])
        if not skrot:
            return _odmowa("klawisz", f"{nazwa}: brak klawisza")
        if skrot in SKROTY_ZAKAZANE or skrot[-1:] == ("f12",):
            return _odmowa("skrot", f"skrót {'+'.join(skrot)} jest wyłączony (narzędzia deweloperskie, systemowe)")
        mody = frozenset(k for k in skrot if k in MODY)
        if "alt" in mody and not mody & {"ctrl", "super"} and any(
                k not in MODY and k not in ALT_DOZWOLONE and k not in KLAWISZE_AKTYWUJACE for k in skrot):
            return _odmowa("accesskey", f"{'+'.join(skrot)}: Alt z literą, cyfrą albo znakiem uruchamia skrót strony "
                           "(accesskey), np. Wyślij albo Opublikuj, bez sprawdzenia przycisku; kliknij element z "
                           "migawki albo użyj klawiszy nawigacji")
        celowane = _celowane(args)
        if celowane:
            zly = _sprawdz_aktywacje(ctx.cel(nazwa, args), "kliknięcie przed klawiszem na", z)
            if zly:
                return zly
        if skrot[-1] in KLAWISZE_AKTYWUJACE:
            el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
            if el is None:
                return _odmowa("brak_fokusu", f"nie wiem, gdzie trafi {'+'.join(skrot)}; kliknij najpierw pole "
                               "albo przycisk, potem naciśnij klawisz")
            if skrot[-1] in KLAWISZE_ENTER and not el.get("nieznany") and pole_platnosci(el) and not z.ma("platnosc"):
                return _czlowiek("pole_wrazliwe", f"Enter w {pole_platnosci(el)} wysyła dane płatności "
                                 f"({_bez_zgody('platnosc')})", opis(el), "platnosc")
            zly = _sprawdz_enter(el, z, mody) if skrot[-1] in KLAWISZE_ENTER else _sprawdz_aktywacje(el, "spacja na", z)
            if zly:
                return zly
            return Werdykt(TAK, cel=opis(el), dane={"klawisze": "+".join(skrot)})
        if skrot[-1] in {"v", "insert"} and ("ctrl" in skrot or "shift" in skrot):
            el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
            if el is None:
                return _odmowa("brak_fokusu", "nie wiem, gdzie trafi wklejenie; kliknij najpierw pole")
            powod = pole_platnosci(el)
            if powod and not z.ma("platnosc"):
                return _czlowiek("pole_wrazliwe", f"wklejanie w {powod} ({_bez_zgody('platnosc')})", opis(el),
                                 "platnosc")
        return Werdykt(TAK, dane={"klawisze": "+".join(skrot)})

    return _odmowa("narzedzie", f"narzędzie {nazwa} nie ma zasady w Komputerze Jarva")


# Ekran HQ jeszcze nie działa: krok właściciela robi on sam w oknie Komputera na pulpicie serwera.
GDZIE_WLASCICIEL = ("Okno Komputera Jarva (przeglądarka) jest na pulpicie serwera: właściciel łączy się przez VNC do "
                    "pulpitu serwera (Tailscale), robi ten krok sam w tym oknie i oddaje ekran")


def wynik_odmowy(w: Werdykt) -> dict:
    """Wynik MCP (tools/call) dla odmowy: agent widzi powód i co dalej, sterownik nie dostaje wywołania."""
    kat = w.dane.get("kategoria") if w.decyzja == CZLOWIEK else None
    if w.decyzja == CZLOWIEK:
        tekst = f"To robi właściciel: {w.powod}. {GDZIE_WLASCICIEL}."
        if kat:
            tekst += (f" Albo właściciel zleca ten krok Jarvowi, a Jarvo wpisuje do karty linię „ZGODA WŁAŚCICIELA: "
                      f"{kat} — „<polecenie właściciela>” (RRRR-MM-DD)” i karta rusza od nowa.")
        tekst += " Nie obchodź tej zasady innym kliknięciem, skrótem ani wpisem."
        dalej = "ask_owner"
    elif w.decyzja == WSTRZYMANE:
        tekst = f"Komputer Jarva jest wstrzymany: {w.powod}. Poczekaj, aż właściciel go wznowi."
        dalej = "wait_for_owner"
    elif w.kod in CZEKAJ:
        tekst = f"Komputer Jarva: {w.powod}."
        dalej = "wait_and_retry"
    else:
        tekst = f"Zablokowane przez Komputer Jarva: {w.powod}."
        dalej = "choose_another_way"
    kod = {CZLOWIEK: "wymaga_czlowieka", WSTRZYMANE: "wstrzymane"}.get(w.decyzja, "zablokowane")
    sc = {"ok": False, "code": kod, "rule": w.kod, "decision": w.decyzja, "message": tekst, "next_step": dalej}
    if kat:
        sc["consent_category"] = kat
    return {"content": [{"type": "text", "text": tekst}], "isError": True, "structuredContent": sc}


INSTRUKCJE = (
    "\n\nKomputer Jarva (twarde zasady, sprawdzane przy każdym wywołaniu): logujesz się, zakładasz konta, klikasz "
    "„Continue with Google/GitHub” i zgody OAuth, wpisujesz hasła i kody (2FA, SMS, weryfikacja), próbujesz CAPTCHA "
    "i wysyłasz formularze logowania i rejestracji sam. Kroki nieodwracalne idą tylko ze zgodą właściciela wpisaną "
    "przez Jarva w kartę (ZGODA WŁAŚCICIELA): płatność, zakup, subskrypcja, karta i BLIK (platnosc), wysyłka "
    "wiadomości i formularzy (wysylka), publikacja (publikacja), usunięcie konta (usuniecie_konta). Bez zgody "
    "wywołanie wraca z code=wymaga_czlowieka (decision=czlowiek, consent_category): powiedz, czego brakuje; właściciel "
    "robi krok przez VNC do pulpitu serwera (Tailscale) albo daje zgodę w karcie. Sekretów (kluczy API, tokenów) nie "
    "wpisujesz, a w drzewie i tekście są ukryte. Narzędzia page, browser_*, clipboard_*, mouse_button_*, nagrywanie "
    "i aktualizacje są wyłączone; uruchamiasz tylko Chromium z adresami http i https. "
    "Tab naciskasz osobno (nie w type_text), nową linię w polu wieloliniowym robisz Shift+Enter, skrótów Alt+litera "
    "(accesskey) nie ma. Klikasz elementem; klik w punkt tylko z delivery_mode foreground w aktywnym oknie, gdy to "
    "okno, a nie okienko podręczne, leży w tym punkcie na wierzchu.\n"
    "Jarvo Computer hard rules: sign-in, sign-up, OAuth, passwords and one-time codes are allowed; payments, sending, "
    "publishing and account deletion need the owner's consent line in the kanban card (decision=czlowiek without it)."
)
