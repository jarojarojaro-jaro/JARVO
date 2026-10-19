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

    def __init__(self, cel=None, fokus=None, wstrzymane=False, program=""):
        self._cel, self._fokus, self.wstrzymane, self._program = cel, fokus, wstrzymane, program
        self.pytania: list[tuple] = []

    def cel(self, nazwa, args):
        self.pytania.append(("cel", nazwa))
        return self._cel(args) if callable(self._cel) else self._cel

    def fokus(self, args):
        self.pytania.append(("fokus",))
        return self._fokus

    def program(self, pid):
        return self._program


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


def test_klik_w_tekst_wewnatrz_przycisku_patrzy_na_przodkow():
    cel = el("text", "129 zł", przodkowie=[{"rola": "push button", "nazwa": "Zapłać 129 zł"},
                                          {"rola": "form", "nazwa": ""}])
    assert decyzja("click", {"x": 10, "y": 10}, cel=cel) == CZLOWIEK
    # przodek bez roli działania (nagłówek sekcji) nie blokuje
    cel = el("text", "Opis", przodkowie=[{"rola": "section", "nazwa": "Kup teraz"}])
    assert decyzja("click", {"x": 10, "y": 10}, cel=cel) == TAK


def test_nieznany_cel_to_odmowa_a_pusty_punkt_przechodzi():
    assert kod("click", {"element_token": "obcy:1"}, cel=NIEZNANY) == "nieznany_cel"
    assert decyzja("click", {"x": 5, "y": 5}, cel=None) == TAK


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
    NIEZNANY,
])
def test_pisanie_w_pola_wrazliwe_robi_wlasciciel(pole):
    w = ocen("type_text", {"pid": 1, "text": "x"}, Ctx(fokus=pole))
    assert w.decyzja == CZLOWIEK and w.kod == "pole_wrazliwe"


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
    uwagi = el("entry", "Uwagi", atrybuty={"tag": "textarea"}, formularz=[PRZYCISK_ZAPLAC])
    assert decyzja("type_text", {"pid": 1, "text": "linia\nlinia"}, fokus=uwagi) == TAK
    # link w formularzu nie wysyła go Enterem
    pole = el("entry", "E-mail", formularz=[{"rola": "link", "nazwa": "Zaloguj się"}])
    assert decyzja("press_key", {"pid": 1, "key": "Return"}, fokus=pole) == TAK
    # spacja nie wysyła formularza z pola
    assert decyzja("press_key", {"pid": 1, "key": "space"},
                   fokus=el("entry", "E-mail", formularz=[PRZYCISK_ZAPLAC])) == TAK


def test_enter_gdy_formularza_nie_da_sie_sprawdzic():
    pole = el("entry", "E-mail", formularz=[], formularz_nieznany=True)
    assert kod("press_key", {"pid": 1, "key": "Return"}, fokus=pole) == "formularz_wrazliwy"


# --- klawisze


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


def test_zle_argumenty_nie_przepuszczaja():
    assert decyzja("click", None) == ODMOWA
    assert decyzja("type_text", {"text": None}, fokus=None) == TAK          # pusty tekst nic nie wpisuje
    assert kod("drag", {"from_x": "a", "from_y": 1, "to_x": 1, "to_y": 1}) == "cel"
