"""Twarde zasady Komputera Jarva (infra/komputer/zasady.py, docs/KOMPUTER.md §6): decyzje bez ekranu."""

from __future__ import annotations

import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO / "infra" / "komputer"))
import zasady  # noqa: E402
from zasady import CZLOWIEK, NIEZNANY, ODMOWA, TAK, WSTRZYMANE, ocen  # noqa: E402

PRZYCISK_ZAPLAC = {"rola": "push button", "nazwa": "Zapłać 129 zł"}


def el(rola: str, nazwa: str = "", **kw) -> dict:
    return {"rola": rola, "nazwa": nazwa, "atrybuty": kw.pop("atrybuty", {}), "przodkowie": kw.pop("przodkowie", []),
            **kw}


class Ctx:
    """Udawany Kontekst: cel (element albo funkcja argumentów) i fokus podane z góry."""

    def __init__(self, cel=None, fokus=None, wstrzymane=False, program="", aktywne=None, pid_okna=None):
        self._cel, self._fokus, self.wstrzymane, self._program = cel, fokus, wstrzymane, program
        self._aktywne, self._pid_okna = aktywne, pid_okna
        self.pytania: list[tuple] = []

    def cel(self, nazwa, args):
        self.pytania.append(("cel", nazwa))
        return self._cel(args) if callable(self._cel) else self._cel

    def fokus(self, args):
        self.pytania.append(("fokus",))
        return self._fokus

    def program(self, pid):
        return self._program

    def aktywne_okno(self):
        self.pytania.append(("aktywne",))
        return self._aktywne

    def pid_okna(self, okno):
        return self._pid_okna


def decyzja(nazwa: str, args: dict | None = None, **ctx) -> str:
    return ocen(nazwa, args or {}, Ctx(**ctx)).decyzja


def kod(nazwa: str, args: dict | None = None, **ctx) -> str:
    return ocen(nazwa, args or {}, Ctx(**ctx)).kod


# --- narzędzia


def test_grupy_narzedzi_rozlaczne():
    assert not (zasady.ODCZYT & zasady.SESJA) and not (zasady.ODCZYT & zasady.DZIALANIA)
    assert not (zasady.SESJA & zasady.DZIALANIA)
    assert zasady.SESJA_BEZ_EKRANU <= zasady.SESJA


@pytest.mark.parametrize("nazwa", ["page", "browser_navigate", "clipboard_read", "clipboard_write",
                                   "mouse_button_down", "mouse_button_up", "mouse_drag", "replay_trajectory",
                                   "start_recording", "install_ffmpeg", "check_for_update", "nowe_narzedzie", ""])
def test_narzedzia_spoza_listy_zablokowane(nazwa):
    w = ocen(nazwa, {}, Ctx())
    assert w.decyzja == ODMOWA and w.kod == "narzedzie"


def test_odczyt_wolno_takze_przy_pauzie_ale_bez_zapisu_do_pliku():
    assert decyzja("get_window_state", {"pid": 1}, wstrzymane=True) == TAK
    assert kod("get_window_state", {"screenshot_out_file": "/tmp/x.png"}) == "plik"
    assert kod("zoom", {"screenshot_out_file": "/tmp/x.png"}) == "plik"


def test_pauza_wstrzymuje_dzialania_ale_nie_sesje():
    assert decyzja("click", {"x": 1, "y": 1}, wstrzymane=True) == WSTRZYMANE
    assert decyzja("bring_to_front", {"pid": 1}, wstrzymane=True) == WSTRZYMANE
    assert decyzja("end_session", {"session": "a"}, wstrzymane=True) == TAK
    assert decyzja("set_agent_cursor_enabled", {"enabled": True}, wstrzymane=True) == TAK


# --- delivery_mode foreground: tylko w oknie, które już jest aktywne

POLE_ADRESU = {"rola": "entry", "nazwa": "Pasek adresu i wyszukiwania"}
NA_WIERZCHU = [
    ("type_text", {"text": "allegro.pl"}),
    ("press_key", {"key": "Return"}),
    ("hotkey", {"keys": ["ctrl", "a"]}),
    ("scroll", {"direction": "down", "x": 10, "y": 10}),
    ("double_click", {"x": 10, "y": 10}),
    ("drag", {"from_x": 1, "from_y": 1, "to_x": 5, "to_y": 5}),
    ("click", {"element_token": "s1:4"}),
]


@pytest.mark.parametrize("nazwa,args", NA_WIERZCHU)
def test_na_wierzchu_w_aktywnym_oknie_jak_w_tle(nazwa, args):
    a = {"pid": 7, "window_id": 6291459, "delivery_mode": "foreground", **args}
    assert decyzja(nazwa, a, cel=POLE_ADRESU, fokus=POLE_ADRESU, aktywne=6291459) == TAK


@pytest.mark.parametrize("nazwa,args", NA_WIERZCHU)
def test_na_wierzchu_w_nieaktywnym_oknie_odmowa(nazwa, args):
    a = {"pid": 7, "window_id": 6291459, "delivery_mode": "foreground", **args}
    for aktywne in (6291460, None):
        w = ocen(nazwa, a, Ctx(cel=POLE_ADRESU, fokus=POLE_ADRESU, aktywne=aktywne))
        assert w.decyzja == ODMOWA and w.kod == "okno_nieaktywne", aktywne


def test_na_wierzchu_bez_okna_i_zly_tryb():
    assert kod("type_text", {"pid": 7, "text": "a", "delivery_mode": "foreground"}, fokus=POLE_ADRESU,
               aktywne=1) == "okno_nieaktywne"
    assert kod("click", {"pid": 7, "x": 1, "y": 1, "delivery_mode": "foreground"}, aktywne=1) == "okno_nieaktywne"
    assert kod("click", {"pid": 7, "window_id": 1, "x": 1, "y": 1, "delivery_mode": "global"}, aktywne=1) == "tryb"


def test_przewijanie_calego_okna_na_wierzchu_tylko_w_aktywnym_programie():
    a = {"pid": 7, "direction": "down", "delivery_mode": "foreground"}
    assert decyzja("scroll", a, aktywne=1, pid_okna=7) == TAK
    assert kod("scroll", a, aktywne=1, pid_okna=8) == "okno_nieaktywne"
    assert kod("scroll", a, aktywne=1, pid_okna=None) == "okno_nieaktywne"
    assert kod("scroll", a, aktywne=None, pid_okna=7) == "okno_nieaktywne"
    assert kod("scroll", {"direction": "down", "delivery_mode": "foreground"}, aktywne=1, pid_okna=7) == \
        "okno_nieaktywne"


def test_w_tle_okno_aktywne_bez_znaczenia():
    ctx = Ctx(cel=POLE_ADRESU, fokus=POLE_ADRESU, aktywne=None)
    for tryb in (None, "background"):
        a = {"pid": 7, "window_id": 5, "element_token": "s1:4", **({"delivery_mode": tryb} if tryb else {})}
        assert ocen("click", a, ctx).decyzja == TAK
    assert ("aktywne",) not in ctx.pytania


def test_na_wierzchu_nie_zdejmuje_innych_zasad():
    a = {"pid": 7, "window_id": 3, "delivery_mode": "foreground"}
    assert decyzja("click", {**a, "element_token": "s1:9"}, cel=PRZYCISK_ZAPLAC, aktywne=3) == CZLOWIEK
    haslo = el("password text", "Hasło")
    assert kod("type_text", {**a, "text": "Lato2026!"}, fokus=haslo, aktywne=3) == "pole_wrazliwe"
    assert decyzja("press_key", {**a, "key": "Return"}, wstrzymane=True, aktywne=3) == WSTRZYMANE


def test_set_config_tylko_dozwolone_klucze():
    assert decyzja("set_config", {"key": "capture_scope", "value": "window"}) == TAK
    assert decyzja("set_config", {"max_image_dimension": 1024, "session": "s"}) == TAK
    assert kod("set_config", {"key": "telemetry_enabled", "value": True}) == "konfiguracja"
    assert kod("set_config", {"capture_scope": "desktop", "update_check_enabled": True}) == "konfiguracja"
    assert kod("set_config", {}) == "konfiguracja"


# --- aplikacje


@pytest.mark.parametrize("args,ok", [
    ({"name": "chromium", "urls": ["https://example.com"]}, True),
    ({"name": "Chromium Web Browser"}, True),
    ({"bundle_id": "chromium.desktop", "urls": ["http://127.0.0.1:8765/a"]}, True),
    ({"name": "xterm"}, False),
    ({"name": "chromium", "urls": ["file:///etc/passwd"]}, False),
    ({"name": "chromium", "urls": ["javascript:alert(1)"]}, False),
    ({"name": "chromium", "urls": ["chrome://settings"]}, False),
    ({"name": "chromium", "urls": ["https://"]}, False),
    ({"name": "chromium", "additional_arguments": ["--remote-debugging-port=9222"]}, False),
    ({"name": "chromium", "launch_path": "/usr/bin/xterm"}, False),
])
def test_launch_app(args, ok):
    assert (decyzja("launch_app", args) == TAK) is ok


def test_kill_app_tylko_przegladarka():
    assert decyzja("kill_app", {"pid": 10}, program=zasady.PROGRAM_PRZEGLADARKI) == TAK
    assert kod("kill_app", {"pid": 10}, program="/usr/bin/Xvnc") == "aplikacja"
    assert kod("kill_app", {"pid": "zly"}) == "aplikacja"
    assert kod("kill_app", {}) == "aplikacja"


def test_invoke_menu():
    assert decyzja("invoke_menu", {"path": ["Plik", "Nowa karta"]}) == TAK
    w = ocen("invoke_menu", {"path": ["Konto", "Zaloguj się"]}, Ctx())
    assert w.decyzja == CZLOWIEK and w.kod == "menu_wrazliwe"


# --- klik


def test_klik_wymaga_celu_i_znanej_formy_target():
    assert kod("click", {"pid": 1}) == "cel"
    assert kod("click", {"target": {"selector": "#kup"}}) == "cel"
    assert kod("click", {"x": 1, "y": 2, "from_zoom": True}) == "zoom"


@pytest.mark.parametrize("etykieta", ["Kup teraz", "Zapłać 129 zł", "Zaloguj się", "Sign in", "Place order",
                                      "Przejdź do kasy", "Wyślij", "Opublikuj", "BLIK", "Allow", "Zezwól",
                                      "Utwórz konto", "Usuń konto", "Continue with Google", "Subscribe"])
def test_klik_wrazliwego_przycisku_robi_wlasciciel(etykieta):
    w = ocen("click", {"element_token": "s1:5"}, Ctx(cel=el("push button", etykieta)))
    assert w.decyzja == CZLOWIEK and w.kod == "przycisk_wrazliwy"


@pytest.mark.parametrize("etykieta", ["Dodaj do koszyka", "Szukaj", "Dalej", "Zezwól na wszystkie", "Pokaż koszyk",
                                      "Payment methods we accept", "Kupony", "Rejestracja pojazdów", "Logout"])
def test_zwykle_przyciski_przechodza(etykieta):
    # „Payment…”, „Kupony”, „Rejestracja…”: wzorce z granicami słów, nie przedrostki
    assert decyzja("click", {"element_token": "s1:5"}, cel=el("link", etykieta)) == TAK


PUNKT = {"window_id": 5, "delivery_mode": "foreground"}   # klik w punkt na wierzchu w aktywnym oknie 5


def test_klik_w_tekst_wewnatrz_przycisku_patrzy_na_przodkow():
    cel = el("text", "129 zł", przodkowie=[{"rola": "push button", "nazwa": "Zapłać 129 zł"},
                                          {"rola": "form", "nazwa": ""}])
    assert decyzja("click", {**PUNKT, "x": 10, "y": 10}, cel=cel, aktywne=5) == CZLOWIEK
    # przodek bez roli działania (nagłówek sekcji) nie blokuje
    cel = el("text", "Opis", przodkowie=[{"rola": "section", "nazwa": "Kup teraz"}])
    assert decyzja("click", {**PUNKT, "x": 10, "y": 10}, cel=cel, aktywne=5) == TAK


def test_nieznany_cel_to_odmowa_a_pusty_punkt_przechodzi():
    assert kod("click", {"element_token": "obcy:1"}, cel=NIEZNANY) == "nieznany_cel"
    assert kod("click", {**PUNKT, "x": 5, "y": 5}, cel=NIEZNANY, aktywne=5) == "nieznany_cel"
    assert decyzja("click", {**PUNKT, "x": 5, "y": 5}, cel=None, aktywne=5) == TAK


def test_klik_w_punkt_w_tle_odrzucony():
    """cua-driver 0.21.0 robi zwykły klik w punkt w tle akcją najmniejszego elementu programu w tym miejscu okna
    (dowolne okno, także element niewidoczny), więc wejście nie wie, w co trafi: tylko elementem albo na wierzchu."""
    nic = el("text", "Opis")
    for args in ({"x": 5, "y": 5}, {"x": 5, "y": 5, "delivery_mode": "background"}, {"x": 5, "y": 5, "count": 1},
                 {"x": 5, "y": 5, "button": "left"}, {"target": {"x": 5, "y": 5}}):
        assert kod("click", {"pid": 7, "window_id": 5, **args}, cel=nic) == "punkt_w_tle", args
    # zdarzenie do okna (prawy, podwójny, z modyfikatorem) i klik na wierzchu sprawdzane w punkcie jak dotąd
    assert decyzja("click", {"pid": 7, "window_id": 5, "x": 5, "y": 5, "button": "right"}, cel=nic) == TAK
    for args in ({"count": 2}, {"modifier": ["shift"]}, {"delivery_mode": "foreground"}):
        assert decyzja("click", {"pid": 7, "window_id": 5, "x": 5, "y": 5, **args}, cel=nic, aktywne=5) == TAK, args
        assert kod("click", {"pid": 7, "window_id": 5, "x": 5, "y": 5, **args}, aktywne=5,
                   cel=el("push button", "Kup teraz")) == "przycisk_wrazliwy", args
    # elementem w tle bez zmian
    assert decyzja("click", {"pid": 7, "window_id": 5, "element_token": "s:1"}, cel=nic) == TAK


def test_prawy_klik_i_przewijanie_przechodza():
    assert decyzja("click", {"x": 1, "y": 1, "button": "right"}, cel=el("push button", "Kup teraz")) == TAK
    assert decyzja("right_click", {"x": 1, "y": 1}, cel=el("push button", "Kup teraz")) == TAK
    assert decyzja("scroll", {"direction": "down"}) == TAK


def test_podwojny_klik_jak_klik():
    assert decyzja("double_click", {"element_token": "s:1"}, cel=el("link", "Zaloguj się")) == CZLOWIEK


def test_przeciagniecie_sprawdza_oba_konce():
    kup = el("push button", "Kup teraz")
    na_przycisku = lambda a: kup if a.get("x", 0) >= 300 else el("text", "Opis")  # noqa: E731
    args = {"pid": 1, "from_x": 100, "from_y": 100, "to_x": 104, "to_y": 101}
    assert decyzja("drag", args, cel=na_przycisku) == TAK
    # puszczenie na przycisku (także daleko od startu, w dużym przycisku) to klik
    assert decyzja("drag", {**args, "to_x": 320}, cel=na_przycisku) == CZLOWIEK
    assert decyzja("drag", {**args, "from_x": 310, "to_x": 330}, cel=na_przycisku) == CZLOWIEK
    w = ocen("drag", {"from_element": 3, "to_element": 4}, Ctx(cel=lambda a: kup if a["element_index"] == 4 else None))
    assert w.decyzja == CZLOWIEK
    assert kod("drag", {"from_element": 3, "to_element": 4}, cel=NIEZNANY) == "nieznany_cel"
    assert kod("drag", {"from_x": 1}) == "cel"


# --- pisanie


def test_pisanie_w_zwykle_pole():
    w = ocen("type_text", {"pid": 1, "text": "jan@example.com"}, Ctx(fokus=el("entry", "E-mail")))
    assert w.decyzja == TAK and w.dane == {"znaki": 15}


@pytest.mark.parametrize("pole", [
    el("password text", "Hasło"),
    el("entry", "", atrybuty={"text-input-type": "password"}),
    el("entry", "Numer karty"),
    el("entry", "", atrybuty={"autocomplete": "cc-number"}),
    el("entry", "Kod BLIK"),
    el("entry", "CVV"),
    el("entry", "", atrybuty={"html-input-name": "otp_code"}),
    el("entry", "Kod SMS"),
    el("entry", "PIN"),
    el("entry", "API token"),
])
def test_pisanie_w_pola_wrazliwe_robi_wlasciciel(pole):
    w = ocen("type_text", {"pid": 1, "text": "x"}, Ctx(fokus=pole))
    assert w.decyzja == CZLOWIEK and w.kod == "pole_wrazliwe"


def test_pisanie_gdy_fokusu_nie_da_sie_sprawdzic_to_odmowa():
    # fokus przeniesiony (np. Tab chwilę wcześniej) albo AT-SPI bez odpowiedzi: nowy stan, klik w pole, pisanie
    assert kod("type_text", {"pid": 1, "text": "x"}, fokus=NIEZNANY) == "nieznany_cel"
    assert kod("press_key", {"pid": 1, "key": "Return"}, fokus=NIEZNANY) == "nieznany_cel"
    assert kod("press_key", {"pid": 1, "key": "space"}, fokus=NIEZNANY) == "nieznany_cel"
    assert decyzja("hotkey", {"pid": 1, "keys": ["ctrl", "v"]}, fokus=NIEZNANY) == CZLOWIEK
    assert kod("hotkey", {"pid": 1, "keys": ["ctrl", "v"]}, fokus=None) == "brak_fokusu"


def test_pisanie_bez_znanego_pola_to_odmowa():
    assert kod("type_text", {"pid": 1, "text": "abc"}, fokus=None) == "brak_fokusu"
    assert decyzja("type_text", {"pid": 1, "text": ""}, fokus=None) == TAK


def test_tekst_z_sekretem_karta_i_zlym_adresem():
    pole = el("entry", "Uwagi")
    assert kod("type_text", {"text": "sk-ant-api03-" + "A" * 30}, fokus=pole) == "sekret"
    assert kod("type_text", {"text": "ghp_" + "a" * 36}, fokus=pole) == "sekret"
    assert kod("type_text", {"text": "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nabc"}, fokus=pole) == "sekret"
    assert kod("type_text", {"text": "karta 4111 1111 1111 1111"}, fokus=pole) == "karta"
    assert kod("type_text", {"text": "javascript:alert(1)"}, fokus=pole) == "adres"
    assert kod("type_text", {"text": "zobacz chrome://flags"}, fokus=pole) == "adres"
    # sekret blokujemy także bez znanego pola
    assert kod("type_text", {"text": "AKIA" + "A" * 16}, fokus=None) == "sekret"
    assert kod("type_text", {"text": "bot 123456789:AA" + "h" * 33}, fokus=None) == "sekret"


def test_pisanie_na_przycisku_z_fokusem_to_jego_uruchomienie():
    assert decyzja("type_text", {"pid": 1, "text": " "}, fokus=el("push button", "Zapłać")) == CZLOWIEK
    assert decyzja("type_text", {"pid": 1, "text": "x"}, fokus=el("link", "Zaloguj się")) == CZLOWIEK
    assert decyzja("type_text", {"pid": 1, "text": " "}, fokus=el("push button", "Dalej")) == TAK


def test_napisy_z_ukrytymi_znakami_i_ozdobnymi_literami():
    for etykieta in ("K\u200bup teraz", "Ｋｕｐ teraz", "Zap\u00adłać", "Zaloguj\u2060 się", "Kup\u00a0teraz"):
        assert decyzja("click", {"element_token": "s:1"}, cel=el("push button", etykieta)) == CZLOWIEK, etykieta
    assert kod("type_text", {"pid": 1, "text": "x"}, fokus=el("entry", "Has\u200bło")) == "pole_wrazliwe"


def test_element_i_punkt_naraz_odrzucone():
    assert kod("click", {"element_token": "s:1", "x": 5, "y": 5}, cel=el("link", "Dalej")) == "cel"
    assert kod("type_text", {"element_index": 2, "target": {"x": 1, "y": 1}, "text": "a"}) == "cel"
    # Hermes wysyła element_index razem z element_token: to jeden cel
    assert decyzja("click", {"element_index": 2, "element_token": "s:2"}, cel=el("link", "Dalej")) == TAK


def test_pisanie_w_cel_najpierw_klika():
    w = ocen("type_text", {"element_token": "s:3", "text": "x"}, Ctx(cel=el("push button", "Zapłać")))
    assert w.decyzja == CZLOWIEK and w.kod == "przycisk_wrazliwy"


def test_set_value_bez_entera():
    pole = el("entry", "E-mail", formularz=[PRZYCISK_ZAPLAC])
    assert decyzja("set_value", {"element_token": "s:2", "value": "a\nb"}, cel=pole) == TAK
    assert decyzja("set_value", {"element_token": "s:2", "value": "x"}, cel=el("password text", "Hasło")) == CZLOWIEK


# --- Enter wysyła formularz


def test_enter_w_formularzu_platnosci_robi_wlasciciel():
    pole = el("entry", "E-mail", formularz=[{"rola": "push button", "nazwa": "Szukaj"}, PRZYCISK_ZAPLAC])
    w = ocen("press_key", {"pid": 1, "key": "Return"}, Ctx(fokus=pole))
    assert w.decyzja == CZLOWIEK and w.kod == "formularz_wrazliwy"
    w = ocen("type_text", {"pid": 1, "text": "a@b.pl\n"}, Ctx(fokus=pole))
    assert w.decyzja == CZLOWIEK and w.kod == "formularz_wrazliwy"
    w = ocen("type_text", {"element_token": "s:2", "text": "\n"}, Ctx(cel=pole))
    assert w.kod == "formularz_wrazliwy"


def test_enter_w_formularzu_bez_platnosci_i_w_textarea():
    szukaj = el("entry", "Szukaj w sklepie", formularz=[{"rola": "push button", "nazwa": "Szukaj"}])
    assert decyzja("press_key", {"pid": 1, "key": "Return"}, fokus=szukaj) == TAK
    # textarea w formularzu bez płatności: nowa linia; w formularzu z „Zapłać” zwykły Enter mógłby wysłać
    # (strona przechwytuje Enter), więc nowa linia tylko Shift+Enter
    opinia = el("entry", "Opinia", atrybuty={"tag": "textarea"}, formularz=[{"rola": "push button", "nazwa": "Dalej"}])
    assert decyzja("type_text", {"pid": 1, "text": "linia\nlinia"}, fokus=opinia) == TAK
    uwagi = el("entry", "Uwagi", atrybuty={"tag": "textarea"}, formularz=[PRZYCISK_ZAPLAC])
    w = ocen("type_text", {"pid": 1, "text": "linia\nlinia"}, Ctx(fokus=uwagi))
    assert w.decyzja == CZLOWIEK and w.kod == "formularz_wrazliwy" and "Shift+Enter" in w.powod
    assert decyzja("press_key", {"pid": 1, "key": "Return", "modifiers": ["shift"]}, fokus=uwagi) == TAK
    # link w formularzu nie wysyła go Enterem
    pole = el("entry", "E-mail", formularz=[{"rola": "link", "nazwa": "Zaloguj się"}])
    assert decyzja("press_key", {"pid": 1, "key": "Return"}, fokus=pole) == TAK
    # spacja nie wysyła formularza z pola
    assert decyzja("press_key", {"pid": 1, "key": "space"},
                   fokus=el("entry", "E-mail", formularz=[PRZYCISK_ZAPLAC])) == TAK


def test_enter_gdy_formularza_nie_da_sie_sprawdzic():
    pole = el("entry", "E-mail", formularz=[], formularz_nieznany=True)
    assert kod("press_key", {"pid": 1, "key": "Return"}, fokus=pole) == "formularz_wrazliwy"


def test_tab_i_znaki_sterujace_w_pisaniu_odrzucone():
    """\t w type_text to Tab: fokus przeskoczyłby z „Uwagi” na „Kup teraz”, a reszta tekstu albo Enter by go kliknęła."""
    uwagi = el("entry", "Uwagi", atrybuty={"tag": "textarea"}, formularz=[PRZYCISK_ZAPLAC])
    for tekst in ("\t ", "\t\n", "perfumy\t ", "a\x1bb", "\x08"):
        assert kod("type_text", {"pid": 1, "text": tekst}, fokus=uwagi) == "znak_sterujacy", repr(tekst)
    assert kod("type_text", {"pid": 1, "text": "\t"}, fokus=el("entry", "Szukaj")) == "znak_sterujacy"
    # set_value nie naciska klawiszy
    assert decyzja("set_value", {"element_token": "s:2", "value": "a\tb"}, cel=el("entry", "Uwagi")) == TAK


def test_enter_w_srodku_tekstu_tylko_w_polu_wieloliniowym():
    szukaj = el("entry", "Szukaj", formularz=[{"rola": "push button", "nazwa": "Szukaj"}])
    assert kod("type_text", {"pid": 1, "text": "perfumy\nKup"}, fokus=szukaj) == "enter_w_srodku"
    assert decyzja("type_text", {"pid": 1, "text": "perfumy\n"}, fokus=szukaj) == TAK


@pytest.mark.parametrize("pole", [
    el("section", "Napisz wiadomość", atrybuty={"tag": "div"}, stany=["editable", "multi-line"], w_formularzu=False),
    el("entry", "Komentarz", atrybuty={"tag": "textarea"}, w_formularzu=False),
    el("paragraph", "", atrybuty={"tag": "p"}, stany=["editable"], w_formularzu=False),
])
def test_enter_w_polu_wieloliniowym_bez_formularza_robi_wlasciciel(pole):
    """Czat, komentarz, edytor bez <form>: Enter zwykle wysyła wiadomość; nowa linia Shift+Enter."""
    w = ocen("press_key", {"pid": 1, "key": "Return"}, Ctx(fokus=pole))
    assert w.decyzja == CZLOWIEK and w.kod == "wysylka_bez_formularza"
    assert decyzja("type_text", {"pid": 1, "text": "Dzień dobry\n"}, fokus=pole) == CZLOWIEK
    assert decyzja("press_key", {"pid": 1, "key": "Return", "modifiers": ["shift"]}, fokus=pole) == TAK
    assert decyzja("type_text", {"pid": 1, "text": "Dzień dobry"}, fokus=pole) == TAK


def test_wyszukiwarka_bez_formularza_enter_przechodzi():
    szukaj = el("entry", "Szukaj", atrybuty={"tag": "input"}, stany=["editable", "single-line"], w_formularzu=False)
    assert decyzja("press_key", {"pid": 1, "key": "Return"}, fokus=szukaj) == TAK
    assert decyzja("press_key", {"pid": 1, "key": "Return", "modifiers": ["ctrl"]}, fokus=szukaj) == CZLOWIEK


@pytest.mark.parametrize("klawisze", [["ctrl", "Return"], ["super", "Return"], ["Control_L", "KP_Enter"],
                                      ["ctrl", "shift", "Return"]])
def test_ctrl_enter_wysyla_takze_z_textarea(klawisze):
    uwagi = el("entry", "Wiadomość", atrybuty={"tag": "textarea"},
               formularz=[{"rola": "push button", "nazwa": "Wyślij"}])
    w = ocen("hotkey", {"pid": 1, "keys": klawisze}, Ctx(fokus=uwagi))
    assert w.decyzja == CZLOWIEK and w.kod == "formularz_wrazliwy"
    # formularz bez wysyłki: Ctrl+Enter wolno
    notatka = el("entry", "Notatka", atrybuty={"tag": "textarea"}, formularz=[{"rola": "push button", "nazwa": "Dalej"}])
    assert decyzja("hotkey", {"pid": 1, "keys": klawisze}, fokus=notatka) == TAK


def test_textarea_gdy_formularza_nie_da_sie_sprawdzic():
    uwagi = el("entry", "Uwagi", atrybuty={"tag": "textarea"}, formularz=[], formularz_nieznany=True)
    assert kod("type_text", {"pid": 1, "text": "a\nb"}, fokus=uwagi) == "formularz_wrazliwy"
    assert decyzja("press_key", {"pid": 1, "key": "Return", "modifiers": ["shift"]}, fokus=uwagi) == TAK


# --- klawisze


@pytest.mark.parametrize("args", [
    {"keys": ["option", "shift", "s"]}, {"keys": ["alt", "s"]}, {"keys": ["Alt_L", "p"]}, {"keys": ["alt", "1"]},
    {"keys": ["alt", "comma"]}, {"keys": ["alt", "shift", "period"]}, {"keys": ["alt", "ś"]},
])
def test_alt_z_litera_to_accesskey_odrzucony(args):
    assert kod("hotkey", {"pid": 1, **args}, fokus=el("entry", "x")) == "accesskey"


def test_alt_z_litera_przez_press_key_tez():
    assert kod("press_key", {"pid": 1, "key": "s", "modifiers": ["alt"]}, fokus=el("entry", "x")) == "accesskey"


@pytest.mark.parametrize("keys", [["alt", "Left"], ["alt", "Right"], ["alt", "Home"], ["alt", "Tab"],
                                  ["alt", "F4"], ["ctrl", "alt", "s"], ["alt"], ["alt", "shift"]])
def test_alt_z_nawigacja_przechodzi(keys):
    assert decyzja("hotkey", {"pid": 1, "keys": keys}, fokus=el("entry", "x")) == TAK


def test_alt_enter_sprawdza_fokus_jak_enter():
    assert decyzja("hotkey", {"pid": 1, "keys": ["alt", "Return"]}, fokus=el("push button", "Kup teraz")) == CZLOWIEK


@pytest.mark.parametrize("args", [
    {"key": "i", "modifiers": ["ctrl", "shift"]}, {"key": "F12"}, {"key": "f12", "modifiers": ["shift"]},
    {"key": "j", "modifiers": ["Control", "Shift"]}, {"key": "Delete", "modifiers": ["ctrl", "shift"]},
])
def test_skroty_zakazane_press_key(args):
    assert kod("press_key", args, fokus=el("entry", "x")) == "skrot"


def test_skroty_zakazane_hotkey_w_dowolnej_kolejnosci():
    assert kod("hotkey", {"keys": ["i", "shift", "ctrl"]}) == "skrot"
    assert kod("hotkey", {"keys": ["alt", "F2"]}) == "skrot"
    assert decyzja("hotkey", {"keys": ["ctrl", "t"]}) == TAK
    assert kod("hotkey", {"keys": []}) == "klawisz"


def test_enter_i_spacja_na_przycisku_z_fokusem():
    assert decyzja("press_key", {"pid": 1, "key": "Return"}, fokus=el("push button", "Kup teraz")) == CZLOWIEK
    assert decyzja("press_key", {"pid": 1, "key": "space"}, fokus=el("push button", "Kup teraz")) == CZLOWIEK
    assert decyzja("press_key", {"pid": 1, "key": "KP_Space"}, fokus=el("push button", "Kup teraz")) == CZLOWIEK
    assert decyzja("hotkey", {"pid": 1, "keys": ["Return"]}, fokus=el("link", "Dalej")) == TAK
    assert kod("press_key", {"pid": 1, "key": "Return"}, fokus=None) == "brak_fokusu"
    assert kod("press_key", {"pid": 1, "key": "Return"}, fokus=el("password text", "Hasło")) == "pole_wrazliwe"


def test_klawisz_z_celem_najpierw_klika():
    w = ocen("press_key", {"element_token": "s:1", "key": "a"}, Ctx(cel=el("push button", "Zapłać")))
    assert w.decyzja == CZLOWIEK
    assert decyzja("press_key", {"pid": 1, "key": "Tab"}, fokus=None) == TAK


def test_wklejanie_w_pole_hasla():
    assert decyzja("hotkey", {"pid": 1, "keys": ["ctrl", "v"]}, fokus=el("password text", "Hasło")) == CZLOWIEK
    assert decyzja("hotkey", {"pid": 1, "keys": ["shift", "Insert"]}, fokus=el("entry", "Kod BLIK")) == CZLOWIEK
    assert decyzja("hotkey", {"pid": 1, "keys": ["ctrl", "v"]}, fokus=el("entry", "Uwagi")) == TAK


# --- ukrywanie sekretów


def test_luhn_i_numery_kart():
    assert zasady.luhn("4111111111111111") and not zasady.luhn("4111111111111112")
    assert zasady.numery_kart("karta 4111 1111 1111 1111.") == ["4111 1111 1111 1111"]
    assert zasady.numery_kart("0000 0000 0000 0000") == []          # same zera: nie karta
    assert zasady.numery_kart("tel. 123 456 789, NIP 526-000-12-46") == []
    assert zasady.numery_kart("4111-1111-1111-1111") == ["4111-1111-1111-1111"]


def test_ukryj_sekrety_w_tekscie_i_strukturze():
    t, n = zasady.ukryj_sekrety("klucz sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890 i karta 4111111111111111")
    assert n == 2 and "sk-proj" not in t and "4111" not in t and t.count(zasady.ZNACZNIK) == 2
    sc = {"elements": [{"role": "password text", "label": "Hasło", "value": "tajne"},
                       {"role": "entry", "label": "Uwagi", "value": "ghp_" + "a" * 36},
                       {"role": "entry", "label": "Imię", "value": "Jan"}]}
    wynik, n = zasady.ukryj_w_strukturze(sc)
    assert n == 2
    assert wynik["elements"][0]["value"] == zasady.ZNACZNIK and wynik["elements"][1]["value"] == zasady.ZNACZNIK
    assert wynik["elements"][2]["value"] == "Jan"


def test_wynik_odmowy_mowi_co_dalej():
    w = ocen("click", {"element_token": "s:1"}, Ctx(cel=el("push button", "Kup teraz")))
    r = zasady.wynik_odmowy(w)
    assert r["isError"] is True and r["structuredContent"]["code"] == "wymaga_czlowieka"
    assert r["structuredContent"]["next_step"] == "ask_owner" and "Ekranie HQ" in r["content"][0]["text"]
    r = zasady.wynik_odmowy(ocen("click", {"x": 1, "y": 1}, Ctx(wstrzymane=True)))
    assert r["structuredContent"]["code"] == "wstrzymane" and r["structuredContent"]["next_step"] == "wait_for_owner"
    r = zasady.wynik_odmowy(ocen("page", {}, Ctx()))
    assert r["structuredContent"]["code"] == "zablokowane" and r["structuredContent"]["rule"] == "narzedzie"
    ctx = Ctx(wstrzymane=True)
    ctx.powod_pauzy = "Operator czeka na właściciela: zaloguj się do panelu"
    r = zasady.wynik_odmowy(ocen("type_text", {"pid": 1, "text": "a"}, ctx))
    assert "zaloguj się do panelu" in r["content"][0]["text"]
    r = zasady.wynik_odmowy(zasady.Werdykt(zasady.ODMOWA, "zajete", "ekranem steruje inna sesja"))
    assert r["structuredContent"]["next_step"] == "wait_and_retry"
    assert zasady.ZMIANY_EKRANU >= zasady.DZIALANIA and not zasady.ZMIANY_EKRANU & zasady.SESJA_BEZ_EKRANU


def test_zle_argumenty_nie_przepuszczaja():
    assert decyzja("click", None) == ODMOWA
    assert decyzja("type_text", {"text": None}, fokus=None) == TAK          # pusty tekst nic nie wpisuje
    assert kod("drag", {"from_x": "a", "from_y": 1, "to_x": 1, "to_y": 1}) == "cel"
