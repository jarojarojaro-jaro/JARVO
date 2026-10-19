"""Twarde zasady Komputera Jarva (etap K2, docs/KOMPUTER.md §6).

Czyste funkcje bez wejścia i wyjścia: wejscie.py woła `ocen` przy każdym wywołaniu narzędzia sterownika ekranu,
zanim sterownik je dostanie, i `ukryj_sekrety` na każdej odpowiedzi, zanim zobaczy ją agent.

Decyzje:
  tak         przepuść,
  odmowa      zakazane zawsze (narzędzie wyłączone, sekret w tekście, zła aplikacja),
  czlowiek    to kliknięcie albo wpis robi właściciel w Ekranie HQ (płatność, zakup, logowanie, wysyłka,
              publikacja, hasło, karta, BLIK, kod 2FA),
  wstrzymane  Komputer zatrzymany (właściciel: jarvo komputer pauza; Operator: czeka na właściciela);
              patrzeć wolno, działać nie, wznawia tylko właściciel.
Przy dwóch sesjach naraz zmieniać ekran może jedna (odmowa `zajete`, wejscie.py: Ekran.zajmij).
Działanie z delivery_mode foreground (klawiatura, przewijanie, przeciąganie i podwójny klik na pulpicie X11 mają tylko
tę drogę) przechodzi tylko w oknie, które już jest aktywne: wejście sprawdza cel i pole z fokusem w tym oknie,
a przełączenie okna przez sterownik posłałoby klawisze tam, gdzie nikt nie patrzył.

Cel działania (pole, przycisk) opisuje słownik z wejscie.py: rola i nazwa z drzewa dostępności, atrybuty HTML
z AT-SPI (tag, html-input-name, text-input-type), przodkowie (rola, nazwa) do kilku poziomów w górę i przy polach
przyciski formularza, w którym pole leży (Enter w polu wysyła formularz).
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
})
SESJA = frozenset({
    "start_session", "end_session", "escalate_session", "set_agent_cursor_enabled", "set_agent_cursor_motion",
    "set_agent_cursor_theme", "set_config", "bring_to_front", "set_window_frame", "move_cursor",
})
DZIALANIA = frozenset({
    "click", "double_click", "right_click", "drag", "scroll", "type_text", "press_key", "hotkey", "set_value",
    "launch_app", "kill_app", "invoke_menu",
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


# Napisy na przyciskach i linkach, których kliknięcie zostawiamy właścicielowi. Szukamy w całej etykiecie
# („Kup teraz za 129 zł”), z granicami słów, po polsku i po angielsku.
WRAZLIWE = _wzorce(
    # płatność i zakup
    r"kup(?:uj[eę])?", r"zam[oó]w(?:ienie)?", r"zamawiam", r"z[lł][oó][zż] zam[oó]wienie", r"zap[lł]a[cć]",
    r"p[lł]ac[eę]", r"zap[lł]ac[eę]", r"op[lł]a[cć]", r"przejd[zź] do (?:p[lł]atno[sś]ci|kasy)",
    r"p[lł]atno[sś][cć]", r"potwierd[zź] (?:zakup|p[lł]atno[sś][cć]|zam[oó]wienie|przelew)", r"blik",
    r"przelew", r"przelej", r"wp[lł]a[cć]", r"do[lł]aduj", r"subskrybuj", r"wykup", r"wesprzyj",
    r"darowizn[aęy]", r"dodaj kart[eęy]", r"buy", r"purchase", r"pay", r"check ?out",
    r"place (?:your )?order", r"(?:complete|confirm|submit) (?:order|payment|purchase)", r"subscribe",
    r"donate", r"add (?:a )?(?:payment|card)", r"proceed to (?:checkout|payment)",
    # logowanie, rejestracja, zgody na dostęp
    r"zaloguj(?: si[eę])?", r"logowanie", r"zarejestruj(?: si[eę])?", r"za[lł][oó][zż] konto",
    r"utw[oó]rz konto", r"log ?in", r"sign ?in", r"sign ?up", r"register", r"create (?:an )?account",
    r"continue with (?:google|apple|facebook|microsoft)",
    r"kontynuuj (?:z|przez) (?:google|apple|facebook|microsoft)", r"autoryzuj", r"authori[sz]e",
    # wysyłka i publikacja
    r"wy[sś]lij", r"prze[sś]lij", r"send", r"submit", r"opublikuj", r"publikuj", r"publish", r"post",
    r"tweet", r"udost[eę]pnij", r"share",
    # nieodwracalne zmiany konta
    r"usu[nń] konto", r"delete (?:my )?account", r"zamknij konto", r"close (?:my )?account",
)
# krótkie zgody, groźne tylko jako cała etykieta (ekran zgody OAuth); „Zezwól na wszystkie” to baner ciasteczek
WRAZLIWE_CALE = re.compile(r"^\s*(?:allow|allow access|zezw[oó]l|zezw[oó]l na dost[eę]p|grant access)\s*$", re.I)

# Pola, do których agent nie pisze: hasła, karty, kody jednorazowe, PIN, tokeny.
POLE_WRAZLIWE = _wzorce(
    r"has[lł]o", r"password", r"passwd", r"pass(?:code|phrase)", r"pin", r"karta", r"karty", r"card",
    r"cc-?(?:number|num|csc|exp)", r"cardnumber", r"cvv2?", r"cvc", r"csc", r"blik", r"otp", r"2fa",
    r"two.?factor", r"one.?time", r"verification code", r"security code", r"token",
    r"kod (?:bezpiecze[nń]stwa|cvv|cvc|blik|sms|weryfikacyjny|jednorazowy|autoryzacyjny|potwierdzaj[aą]cy|"
    r"z aplikacji|dost[eę]pu)",
)

# Sekrety w tekście: wpisanie to odmowa, w odpowiedzi sterownika zastępujemy je znacznikiem.
SEKRETY = re.compile("|".join([
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)",
    r"\bsk-(?:ant-|proj-|or-v1-)?[A-Za-z0-9_-]{20,}",
    r"\bgh[pousr]_[A-Za-z0-9]{30,}", r"\bgithub_pat_[A-Za-z0-9_]{30,}", r"\bglpat-[A-Za-z0-9_-]{20,}",
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
                "meta": "super", "cmd": "super", "command": "super", "super": "super", "win": "super"}


@dataclass
class Werdykt:
    decyzja: str
    kod: str = ""
    powod: str = ""
    cel: str = ""                       # opis celu do dziennika (rola i nazwa), bez wpisywanego tekstu
    dane: dict = field(default_factory=dict)

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


def opis(el: Optional[dict]) -> str:
    if not el:
        return "nieznany cel"
    return f"{el.get('rola') or el.get('role') or '?'} „{_etykieta(el)[:60]}”"


def _wrazliwa_etykieta(tekst: str) -> bool:
    tekst = _napis(tekst)
    return bool(tekst) and (bool(WRAZLIWE.search(tekst)) or bool(WRAZLIWE_CALE.match(tekst)))


def przycisk_wrazliwy(el: Optional[dict]) -> Optional[str]:
    """Etykieta przycisku albo linku, który zostawiamy właścicielowi: cel i jego przodkowie z rolą działania."""
    if not el:
        return None
    if _wrazliwa_etykieta(_etykieta(el)):
        return _etykieta(el)
    for p in (el.get("przodkowie") or [])[:4]:
        rola = str(p.get("rola") or p.get("role") or "").lower()
        if rola in ROLE_DZIALANIA and _wrazliwa_etykieta(_etykieta(p)):
            return _etykieta(p)
    return None


def pole_wrazliwe(el: Optional[dict]) -> Optional[str]:
    """Powód, dla którego do pola nie pisze agent (hasło, karta, kod), albo None."""
    if not el:
        return None
    if el.get("nieznany"):
        return "pole, którego Komputer nie umie sprawdzić"
    rola = str(el.get("rola") or el.get("role") or "").lower()
    atr = el.get("atrybuty") or {}
    if rola in ROLE_HASLA or str(atr.get("text-input-type", "")).lower() == "password":
        return "pole hasła"
    for tekst in (_etykieta(el), str(atr.get("html-input-name", "")), str(atr.get("autocomplete", "")),
                  str(atr.get("placeholder-text", ""))):
        tekst = _napis(tekst)
        if tekst and POLE_WRAZLIWE.search(tekst.replace("_", " ")):
            return f"pole „{tekst[:40]}”"
    return None


def _skrot(klawisze: list) -> tuple:
    norm = []
    for k in klawisze:
        k = str(k).strip().lower()
        norm.append(MODYFIKATORY.get(k, k))
    mod = sorted(k for k in norm if k in {"ctrl", "shift", "alt", "super"})
    reszta = [k for k in norm if k not in {"ctrl", "shift", "alt", "super"}]
    return tuple(mod + reszta)


def _czlowiek(kod: str, powod: str, cel: str = "") -> Werdykt:
    return Werdykt(CZLOWIEK, kod, powod, cel)


def _odmowa(kod: str, powod: str, cel: str = "") -> Werdykt:
    return Werdykt(ODMOWA, kod, powod, cel)


def _sprawdz_tekst(tekst: str, pole: Optional[dict]) -> Optional[Werdykt]:
    if SEKRETY.search(tekst):
        return _odmowa("sekret", "tekst wygląda na klucz, token albo klucz prywatny; sekretów nie wpisujemy", opis(pole))
    if numery_kart(tekst):
        return _czlowiek("karta", "numer karty płatniczej wpisuje właściciel", opis(pole))
    if ADRES_ZAKAZANY.search(tekst):
        return _odmowa("adres", "adresy javascript:, data:, file:, chrome: i devtools: są wyłączone", opis(pole))
    powod = pole_wrazliwe(pole)
    if powod:
        return _czlowiek("pole_wrazliwe", f"{powod}: hasło, kartę i kody wpisuje właściciel", opis(pole))
    return None


def formularz_wrazliwy(el: Optional[dict]) -> Optional[str]:
    """Enter w polu formularza wysyła formularz: etykieta wrażliwego przycisku tego formularza (Zapłać, Zaloguj,
    Wyślij), albo None. W polu wieloliniowym (textarea) Enter to nowa linia."""
    if not el or str((el.get("atrybuty") or {}).get("tag", "")).lower() == "textarea":
        return None
    if el.get("formularz_nieznany"):
        return "formularz, którego Komputer nie umie sprawdzić"
    for p in el.get("formularz") or []:
        rola = str(p.get("rola") or p.get("role") or "").lower()
        if rola in {"push button", "button"} and _wrazliwa_etykieta(_etykieta(p)):
            return _etykieta(p)
    return None


def _sprawdz_enter(el: Optional[dict]) -> Optional[Werdykt]:
    zly = _sprawdz_aktywacje(el, "Enter na")
    if zly:
        return zly
    etykieta = formularz_wrazliwy(el)
    if etykieta:
        return _czlowiek("formularz_wrazliwy", f"Enter w {opis(el)} wysyła formularz z przyciskiem "
                         f"„{etykieta[:60]}” (płatność, logowanie, wysyłka): to robi właściciel", opis(el))
    return None


def _sprawdz_aktywacje(el: Optional[dict], jak: str) -> Optional[Werdykt]:
    """Klik, Enter albo spacja na elemencie: przycisk wrażliwy albo cel, którego nie da się sprawdzić."""
    if el and el.get("nieznany"):
        return _odmowa("nieznany_cel", f"{jak} elementu, którego Komputer nie umie sprawdzić; zrób świeży stan "
                       "okna (get_window_state) i wskaż element z niego")
    etykieta = przycisk_wrazliwy(el)
    if etykieta:
        return _czlowiek("przycisk_wrazliwy", f"{jak} „{etykieta[:60]}” (płatność, zakup, logowanie, wysyłka "
                         "albo publikacja) robi właściciel", opis(el))
    return None


def _wspolrzedne(args: dict) -> bool:
    return args.get("x") is not None and args.get("y") is not None


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
    """Decyzja dla jednego wywołania narzędzia sterownika."""
    args = args if isinstance(args, dict) else {}
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
                return _odmowa("adres", f"launch_app: tylko adresy http i https, nie {str(u)[:40]}")
        return Werdykt(TAK, cel=", ".join(urlsplit(str(u)).netloc for u in args.get("urls") or []))

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
            if _wrazliwa_etykieta(p):
                return _czlowiek("menu_wrazliwe", f"pozycję menu „{p[:60]}” wybiera właściciel", " › ".join(sciezka))
        return Werdykt(TAK, cel=" › ".join(sciezka)[:80])

    if nazwa in {"scroll", "right_click"}:
        return Werdykt(TAK, cel=opis(ctx.cel(nazwa, args)) if nazwa == "right_click" else "")

    if nazwa in {"click", "double_click"}:
        if not _celowane(args):
            return _odmowa("cel", f"{nazwa} wymaga elementu (element_token) albo punktu (x, y)")
        if nazwa == "click" and str(args.get("button") or "left").lower() == "right":
            return Werdykt(TAK, cel=opis(ctx.cel(nazwa, args)))
        el = ctx.cel(nazwa, args)
        return _sprawdz_aktywacje(el, "kliknięcie") or Werdykt(TAK, cel=opis(el))

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
            zly = _sprawdz_aktywacje(el, "przeciągnięcie na")
            if zly:
                return zly
            opisy.append(opis(el))
        return Werdykt(TAK, cel=" → ".join(opisy))

    if nazwa in {"type_text", "set_value"}:
        tekst = args.get("text") if nazwa == "type_text" else args.get("value")
        tekst = "" if tekst is None else str(tekst)
        celowane = nazwa == "set_value" or _celowane(args)
        pole = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
        if nazwa == "type_text" and (celowane or str((pole or {}).get("rola") or "").lower() in ROLE_DZIALANIA):
            # pisanie w cel to najpierw klik; spacja albo Enter na przycisku z fokusem go uruchamia
            zly = _sprawdz_aktywacje(pole, "kliknięcie przed pisaniem w" if celowane else "pisanie na")
            if zly:
                return zly
        if pole is None and tekst.strip():
            # bez znanego pola nie piszemy: tekst mógłby trafić w pole hasła, którego nie widzimy
            zly = _sprawdz_tekst(tekst, None)
            return zly or _odmowa("brak_fokusu", "nie wiem, w które pole trafi tekst; kliknij najpierw pole, "
                                  "potem pisz")
        zly = _sprawdz_tekst(tekst, pole)
        if zly:
            return zly
        if nazwa == "type_text" and ("\n" in tekst or "\r" in tekst):
            zly = _sprawdz_enter(pole)
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
        celowane = _celowane(args)
        if celowane:
            zly = _sprawdz_aktywacje(ctx.cel(nazwa, args), "kliknięcie przed klawiszem na")
            if zly:
                return zly
        if skrot[-1] in KLAWISZE_AKTYWUJACE:
            el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
            if el is None:
                return _odmowa("brak_fokusu", f"nie wiem, gdzie trafi {'+'.join(skrot)}; kliknij najpierw pole "
                               "albo przycisk, potem naciśnij klawisz")
            if skrot[-1] in KLAWISZE_ENTER and pole_wrazliwe(el):
                return _czlowiek("pole_wrazliwe", f"Enter w {pole_wrazliwe(el)} wysyła dane logowania albo "
                                 "płatności: to robi właściciel", opis(el))
            zly = _sprawdz_enter(el) if skrot[-1] in KLAWISZE_ENTER else _sprawdz_aktywacje(el, "spacja na")
            if zly:
                return zly
            return Werdykt(TAK, cel=opis(el), dane={"klawisze": "+".join(skrot)})
        if skrot[-1] in {"v", "insert"} and ("ctrl" in skrot or "shift" in skrot):
            el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
            powod = pole_wrazliwe(el)
            if powod:
                return _czlowiek("pole_wrazliwe", f"wklejanie w {powod} robi właściciel", opis(el))
        return Werdykt(TAK, dane={"klawisze": "+".join(skrot)})

    return _odmowa("narzedzie", f"narzędzie {nazwa} nie ma zasady w Komputerze Jarva")


def wynik_odmowy(w: Werdykt) -> dict:
    """Wynik MCP (tools/call) dla odmowy: agent widzi powód i co dalej, sterownik nie dostaje wywołania."""
    if w.decyzja == CZLOWIEK:
        tekst = (f"To robi właściciel: {w.powod}. Poproś go, żeby zrobił to sam w Ekranie HQ (Komputer Jarva). "
                 "Nie obchodź tej zasady innym kliknięciem, skrótem ani wpisem.")
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
    return {"content": [{"type": "text", "text": tekst}], "isError": True,
            "structuredContent": {"ok": False, "code": kod, "rule": w.kod, "decision": w.decyzja,
                                  "message": tekst, "next_step": dalej}}


INSTRUKCJE = (
    "\n\nKomputer Jarva (twarde zasady, sprawdzane przy każdym wywołaniu): płatności, zakupy, logowanie, rejestrację, "
    "zgody na dostęp, wysyłkę i publikację oraz wpisywanie haseł, numerów kart, kodów BLIK i 2FA robi właściciel. "
    "Takie wywołanie wraca z code=wymaga_czlowieka (decision=czlowiek): powiedz właścicielowi, co ma kliknąć w Ekranie "
    "HQ, i poczekaj. Sekretów nie wpisujesz, a w drzewie i tekście są ukryte. Narzędzia page, browser_*, clipboard_*, "
    "mouse_button_*, nagrywanie i aktualizacje są wyłączone; uruchamiasz tylko Chromium z adresami http i https.\n"
    "Jarvo Computer hard rules: payments, purchases, sign-in, sign-up, access grants, sending, publishing and typing "
    "passwords, card numbers or one-time codes are left to the owner (decision=czlowiek)."
)
