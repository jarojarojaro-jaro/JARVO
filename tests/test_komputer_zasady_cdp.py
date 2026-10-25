"""Twarde zasady natywnie (docs/NATYWNIE.md J05): słownik ról CDP → zasady z kontenera (infra/komputer/zasady.py bez
zmian) i zasady natywne (komputer/zasady_natywne.py): schowek, skróty okna przeglądarki, okna potwierdzeń
z wrażliwym tekstem, wybór pliku i CAPTCHA. Czyste funkcje na atrapie kontekstu: biegną na każdym systemie."""
from __future__ import annotations

import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from komputer import sterownik_cdp, zasady_natywne  # noqa: E402

zasady = zasady_natywne.zasady

# role z drzewa dostępności Chromium (CDP), które coś uruchamiają albo przyjmują tekst → ich miejsce w słowniku zasad
INTERAKTYWNE_CDP = {"button": "push button", "link": "link", "textbox": "entry", "searchbox": "entry",
                    "combobox": "combo box", "checkbox": "check box", "radio": "radio button",
                    "menuitem": "menu item", "menuitemcheckbox": "check menu item", "menuitemradio": "radio menu item",
                    "tab": "page tab", "switch": "toggle button", "PopUpButton": "push button",
                    "RootWebArea": "document web", "form": "form", "dialog": "dialog"}


@pytest.mark.parametrize("cdp, oczekiwana", sorted(INTERAKTYWNE_CDP.items()))
def test_slownik_rol_cdp(cdp, oczekiwana):
    assert sterownik_cdp.rola_zasad(cdp) == oczekiwana


def test_pole_hasla_po_atrybucie_type():
    assert sterownik_cdp.rola_zasad("textbox", "password") == "password text"
    assert sterownik_cdp.rola_zasad("textbox", "email") == "entry"
    assert "password text" in zasady.ROLE_HASLA


def test_role_dzialania_zasad_pokrywaja_przyciski_i_linki_cdp():
    """Każda rola CDP, którą da się kliknąć, trafia w ROLE_DZIALANIA zasad (przodek-przycisk z napisem „Zapłać”
    blokuje klik w tekst w środku), a pola tekstowe w role pól."""
    for cdp in ("button", "link", "menuitem", "menuitemcheckbox", "menuitemradio", "tab", "checkbox", "radio",
                "PopUpButton", "switch"):
        assert sterownik_cdp.rola_zasad(cdp) in zasady.ROLE_DZIALANIA, cdp


class Ctx:
    """Atrapa kontekstu zasad: cel i fokus podane przez test (jak KontekstCDP po opisie ze sterownika)."""

    def __init__(self, cel=None, fokus=None, wstrzymane=False, aktywne=1):
        self._cel, self._fokus, self.wstrzymane, self._aktywne = cel, fokus, wstrzymane, aktywne
        self.powod_pauzy = "właściciel zatrzymał Komputer"

    def cel(self, nazwa, args):
        return self._cel

    def fokus(self, args):
        return self._fokus

    def program(self, pid):
        return zasady.PROGRAM_PRZEGLADARKI if pid == 7 else ""

    def aktywne_okno(self):
        return self._aktywne

    def pid_okna(self, okno):
        return 7


def el(rola_cdp: str, nazwa: str, typ: str = "", **kw) -> dict:
    """Opis elementu taki, jaki daje sterownik CDP (opis_wezla)."""
    wynik = {"rola": sterownik_cdp.rola_zasad(rola_cdp, typ), "nazwa": nazwa, "atrybuty": {"tag": kw.pop("tag", "")},
             "przodkowie": [], "w_formularzu": False, "formularz": [], "zrodlo": "cdp"}
    if typ:
        wynik["atrybuty"]["text-input-type"] = typ
    wynik.update(kw)
    return wynik


KLIK = {"pid": 7, "window_id": 1, "element_token": "s1:3"}
PISZ = {"pid": 7, "window_id": 1, "delivery_mode": "foreground"}


@pytest.mark.parametrize("cel, decyzja, kod", [
    (el("button", "Zapłać 129 zł"), zasady.CZLOWIEK, "przycisk_wrazliwy"),
    (el("link", "Zaloguj się"), zasady.CZLOWIEK, "przycisk_wrazliwy"),
    (el("menuitem", "Kup teraz"), zasady.CZLOWIEK, "przycisk_wrazliwy"),
    (el("button", "Dodaj do koszyka"), zasady.TAK, ""),
    (el("checkbox", "Akceptuję regulamin sklepu"), zasady.TAK, ""),
    (el("StaticText", "129 zł", przodkowie=[{"rola": "push button", "nazwa": "Zapłać teraz"}]), zasady.CZLOWIEK,
     "przycisk_wrazliwy"),
])
def test_rdzen_zasad_na_opisie_z_cdp(cel, decyzja, kod):
    w = zasady.ocen("click", KLIK, Ctx(cel=cel))
    assert (w.decyzja, w.kod) == (decyzja, kod)


@pytest.mark.parametrize("pole, powod", [
    (el("textbox", "Hasło", "password"), "pole hasła"),
    (el("textbox", "Numer karty", autocomplete="cc-number"), "pole"),
    (el("textbox", "", atrybuty={"tag": "input", "autocomplete": "cc-number"}), "pole"),
    (el("textbox", "Kod BLIK"), "pole"),
    (el("textbox", "Kod SMS"), "pole"),
])
def test_pisanie_w_polach_wrazliwych_z_cdp(pole, powod):
    w = zasady.ocen("type_text", {**PISZ, "text": "123456"}, Ctx(fokus=pole))
    assert w.decyzja == zasady.CZLOWIEK and w.kod == "pole_wrazliwe" and powod in w.powod


def test_enter_w_formularzu_z_przyciskiem_platnosci_z_cdp():
    pole = el("textbox", "E-mail", "email", w_formularzu=True,
              formularz=[{"rola": "push button", "nazwa": "Zapłać 129 zł"}], stany=["editable", "single-line"])
    w = zasady.ocen("press_key", {**PISZ, "key": "Return"}, Ctx(fokus=pole))
    assert w.kod == "formularz_wrazliwy"
    wyszukiwarka = el("searchbox", "Szukaj", w_formularzu=True, formularz=[{"rola": "push button", "nazwa": "Szukaj"}],
                      stany=["editable", "single-line"])
    assert zasady.ocen("press_key", {**PISZ, "key": "Return"}, Ctx(fokus=wyszukiwarka)).wolno


@pytest.mark.parametrize("klawisze", [["ctrl", "v"], ["cmd", "v"], ["shift", "Insert"], ["ctrl", "shift", "v"],
                                      ["ctrl", "c"], ["command", "x"], ["control", "Insert"]])
def test_schowek_wlasciciela(klawisze):
    w = zasady_natywne.ocen("hotkey", {**PISZ, "keys": klawisze}, Ctx(fokus=el("textbox", "Uwagi")))
    assert w is not None and w.decyzja == zasady.ODMOWA and w.kod == "schowek"


@pytest.mark.parametrize("klawisze", [["ctrl", "l"], ["cmd", "l"], ["alt", "d"], ["f6"], ["ctrl", "t"], ["ctrl", "n"],
                                      ["ctrl", "o"], ["ctrl", "s"], ["ctrl", "p"], ["ctrl", "shift", "n"],
                                      ["ctrl", "tab"], ["ctrl", "1"], ["ctrl", "h"], ["ctrl", "j"], ["ctrl", "u"]])
def test_skroty_okna_przegladarki(klawisze):
    args = {**PISZ, "keys": klawisze} if len(klawisze) > 1 else {**PISZ, "key": klawisze[0]}
    nazwa = "hotkey" if len(klawisze) > 1 else "press_key"
    w = zasady_natywne.ocen(nazwa, args, Ctx(fokus=el("textbox", "Uwagi")))
    assert w is not None and w.kod == "skrot_przegladarki", klawisze


@pytest.mark.parametrize("klawisze", [["ctrl", "a"], ["ctrl", "z"], ["shift", "Tab"], ["ctrl", "Backspace"]])
def test_zwykle_skroty_edycji_przechodza_do_rdzenia(klawisze):
    assert zasady_natywne.ocen("hotkey", {**PISZ, "keys": klawisze}, Ctx(fokus=el("textbox", "Uwagi"))) is None


def _ok(wiadomosc: str, typ: str = "confirm") -> dict:
    return {"rola": "push button", "nazwa": "OK", "atrybuty": {}, "przodkowie": [{"rola": "dialog", "nazwa": wiadomosc}],
            "w_formularzu": False, "formularz": [], "dialog": {"typ": typ, "wiadomosc": wiadomosc, "akceptuje": True}}


@pytest.mark.parametrize("wiadomosc", ["Czy na pewno zapłacić 129 zł kartą?", "Potwierdź płatność BLIK",
                                       "Wysłać wiadomość do 120 osób?", "Usunąć konto na stałe?",
                                       "Confirm purchase of 3 items?", "Opublikować post?"])
def test_okno_potwierdzenia_z_wrazliwym_tekstem(wiadomosc):
    for nazwa, args, ctx in (("click", KLIK, Ctx(cel=_ok(wiadomosc))),
                             ("press_key", {**PISZ, "key": "Return"}, Ctx(fokus=_ok(wiadomosc)))):
        w = zasady_natywne.ocen(nazwa, args, ctx)
        assert w is not None and (w.decyzja, w.kod) == (zasady.CZLOWIEK, "okno_wrazliwe"), (nazwa, wiadomosc)


def test_okno_bez_wrazliwego_tekstu_i_anuluj_przechodza():
    assert zasady_natywne.ocen("click", KLIK, Ctx(cel=_ok("Usunąć pozycję z koszyka?"))) is None
    assert zasady_natywne.ocen("click", KLIK, Ctx(cel=_ok("Opuścić stronę? Zmiany nie zostaną zapisane."))) is None
    anuluj = {**_ok("Czy na pewno zapłacić 129 zł?"), "nazwa": "Anuluj"}
    anuluj["dialog"] = {**anuluj["dialog"], "akceptuje": False}
    assert zasady_natywne.ocen("click", KLIK, Ctx(cel=anuluj)) is None


def test_prompt_z_wrazliwym_tekstem_i_enterem():
    pole = {"rola": "entry", "nazwa": "Podaj kod BLIK", "atrybuty": {}, "przodkowie": [], "stany": ["editable"],
            "w_formularzu": False, "formularz": [],
            "dialog": {"typ": "prompt", "wiadomosc": "Podaj kod BLIK do płatności", "akceptuje": False}}
    w = zasady_natywne.ocen("type_text", {**PISZ, "text": "123456\n"}, Ctx(fokus=pole))
    assert w is not None and w.kod == "okno_wrazliwe"
    assert zasady.ocen("type_text", {**PISZ, "text": "123456"}, Ctx(fokus=pole)).kod == "pole_wrazliwe"


def test_wybor_pliku_robi_czlowiek():
    plik = el("button", "Faktura (PDF)", "file", tag="input", plik=True)
    for nazwa, args, ctx in (("click", KLIK, Ctx(cel=plik)), ("double_click", KLIK, Ctx(cel=plik)),
                             ("press_key", {**PISZ, "key": "space"}, Ctx(fokus=plik)),
                             ("press_key", {**PISZ, "key": "Return"}, Ctx(fokus=plik))):
        w = zasady_natywne.ocen(nazwa, args, ctx)
        assert w is not None and (w.decyzja, w.kod) == (zasady.CZLOWIEK, "wybor_pliku"), nazwa
    assert zasady_natywne.ocen("right_click", KLIK, Ctx(cel=plik)) is None


@pytest.mark.parametrize("cel", [
    el("checkbox", "Nie jestem robotem", sciezka_przodkow=[{"rola": "document web", "nazwa": "reCAPTCHA"}]),
    el("button", "Weryfikuj", sciezka_przodkow=[{"rola": "internal frame", "nazwa": "Widget containing a Cloudflare "
                                                 "security challenge turnstile"}]),
    el("checkbox", "I'm not a robot"),
])
def test_captcha_robi_czlowiek(cel):
    w = zasady_natywne.ocen("click", KLIK, Ctx(cel=cel))
    assert w is not None and w.kod == "captcha"


def test_pauza_i_odczyt_zostaja_dla_rdzenia():
    assert zasady_natywne.ocen("get_window_state", {}, Ctx()) is None
    assert zasady_natywne.ocen("hotkey", {**PISZ, "keys": ["ctrl", "v"]}, Ctx(wstrzymane=True)) is None
    assert zasady.ocen("hotkey", {**PISZ, "keys": ["ctrl", "v"]}, Ctx(wstrzymane=True)).decyzja == zasady.WSTRZYMANE


def test_nieznany_cel_nie_przechodzi_przez_zasady_natywne():
    assert zasady_natywne.ocen("click", KLIK, Ctx(cel=zasady.NIEZNANY)) is None
    assert zasady.ocen("click", KLIK, Ctx(cel=zasady.NIEZNANY)).kod == "nieznany_cel"


@pytest.mark.parametrize("args", [{"key": "a"}, {"key": "7"}, {"key": "A", "modifiers": ["shift"]},
                                  {"keys": ["shift", "x"]}])
def test_znak_po_znaku_w_polu_hasla_robi_wlasciciel(args):
    """Rdzeń sprawdza pole tylko przy type_text: znak przez press_key albo hotkey w polu hasła czy kodu też jest
    pisaniem, więc natywnie robi go właściciel."""
    nazwa = "hotkey" if "keys" in args else "press_key"
    w = zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=el("textbox", "Hasło", "password")))
    assert (w.decyzja, w.kod) == (zasady.CZLOWIEK, "pole_wrazliwe")
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=el("textbox", "Kod BLIK"))).kod == "pole_wrazliwe"
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=el("textbox", "Uwagi"))) is None
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=None)) is None        # skrót strony bez pola
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=zasady.NIEZNANY)).kod == "nieznany_cel"


def test_skrot_z_ctrl_w_polu_hasla_to_nie_pisanie():
    haslo = Ctx(fokus=el("textbox", "Hasło", "password"))
    assert zasady_natywne.ocen("hotkey", {**PISZ, "keys": ["ctrl", "a"]}, haslo) is None
    assert zasady_natywne.ocen("press_key", {**PISZ, "key": "Tab"}, haslo) is None


@pytest.mark.parametrize("tekst, adres", [
    ("https://sklep.jarvo.test/sklep.html", "https://sklep.jarvo.test/sklep.html"),
    ("http://example.com", "http://example.com"),
    ("allegro.pl", "https://allegro.pl"),
    ("example.com:8443/a?b=1", "https://example.com:8443/a?b=1"),
    ("localhost:9119", "https://localhost:9119"),                 # adres przejdzie, a odrzuci go filtr ruchu
    ("perfumy damskie", "https://www.google.com/search?q=perfumy+damskie"),
    ("  https://example.com  ", "https://example.com")])
def test_adres_z_paska(tekst, adres):
    assert sterownik_cdp.adres_z_paska(tekst) == adres


@pytest.mark.parametrize("tekst", ["", "   ", "javascript:alert(1)", "JAVASCRIPT:alert(1)", "file:///C:/Windows",
                                   "chrome://settings", "data:text/html,x", "view-source:https://a.pl",
                                   "devtools://devtools", "https://", "mailto:a@b.pl"])
def test_pasek_adresu_odrzuca_inne_schematy(tekst):
    assert sterownik_cdp.adres_z_paska(tekst) is None


def test_pasek_adresu_dla_zasad_to_zwykle_pole_bez_formularza():
    """Pasek adresu sterownika (element 0 migawki) to dla zasad pole jednowierszowe poza formularzem: tekst sprawdzają
    zasady tekstu (javascript:, klucze), a Enter przechodzi jak w Chromium z pulpitu."""
    pasek = sterownik_cdp.Sterownik._opis_paska()
    assert pasek["rola"] == "entry" and pasek["nazwa"] == sterownik_cdp.PASEK and not pasek["w_formularzu"]
    ctx = Ctx(fokus=pasek)
    assert zasady.ocen("type_text", {**PISZ, "text": "https://allegro.pl"}, ctx).wolno
    assert zasady.ocen("press_key", {**PISZ, "key": "Return"}, ctx).wolno
    assert zasady.ocen("type_text", {**PISZ, "text": "javascript:alert(1)"}, ctx).decyzja == zasady.ODMOWA
    assert not zasady.ocen("type_text", {**PISZ, "text": "sk-ant-api03-" + "A" * 30}, ctx).wolno
    assert zasady.ocen("click", KLIK, Ctx(cel=pasek)).wolno
