"""Twarde zasady natywnie (docs/NATYWNIE.md J05): słownik ról CDP → zasady z kontenera (infra/komputer/zasady.py bez
zmian) i zasady natywne (komputer/zasady_natywne.py): schowek, skróty okna przeglądarki, okna potwierdzeń
z wrażliwym tekstem, wybór pliku i znak po znaku w polu karty. Czyste funkcje na atrapie kontekstu: biegną na każdym
systemie."""
from __future__ import annotations

import json
import re
import socket
import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from komputer import sterownik_cdp, wejscie_natywne, zasady_natywne  # noqa: E402

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
    """Atrapa kontekstu zasad: cel, fokus i zgody z karty podane przez test (jak KontekstCDP po opisie ze sterownika)."""

    def __init__(self, cel=None, fokus=None, wstrzymane=False, aktywne=1, zgody=frozenset()):
        self._cel, self._fokus, self.wstrzymane, self._aktywne = cel, fokus, wstrzymane, aktywne
        self._zgody = frozenset(zgody)
        self.powod_pauzy = "właściciel zatrzymał Komputer"

    def zgody(self):
        return self._zgody

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
    (el("link", "Zaloguj się"), zasady.TAK, ""),
    (el("button", "Continue with GitHub"), zasady.TAK, ""),
    (el("menuitem", "Kup teraz"), zasady.CZLOWIEK, "przycisk_wrazliwy"),
    (el("button", "Dodaj do koszyka"), zasady.TAK, ""),
    (el("checkbox", "Akceptuję regulamin sklepu"), zasady.TAK, ""),
    (el("StaticText", "129 zł", przodkowie=[{"rola": "push button", "nazwa": "Zapłać teraz"}]), zasady.CZLOWIEK,
     "przycisk_wrazliwy"),
])
def test_rdzen_zasad_na_opisie_z_cdp(cel, decyzja, kod):
    w = zasady.ocen("click", KLIK, Ctx(cel=cel))
    assert (w.decyzja, w.kod) == (decyzja, kod)


@pytest.mark.parametrize("pole", [
    el("textbox", "Numer karty", autocomplete="cc-number"),
    el("textbox", "", atrybuty={"tag": "input", "autocomplete": "cc-number"}),
    el("textbox", "Kod BLIK"),
])
def test_pisanie_w_polach_platnosci_z_cdp(pole):
    w = zasady.ocen("type_text", {**PISZ, "text": "123456"}, Ctx(fokus=pole))
    assert w.decyzja == zasady.CZLOWIEK and w.kod == "pole_wrazliwe" and "pole" in w.powod
    assert zasady.ocen("type_text", {**PISZ, "text": "123456"}, Ctx(fokus=pole, zgody={"platnosc"})).wolno


@pytest.mark.parametrize("pole", [el("textbox", "Hasło", "password"), el("textbox", "Kod SMS"),
                                  el("textbox", "", atrybuty={"tag": "input", "autocomplete": "one-time-code"})])
def test_hasla_i_kody_z_cdp_agent_wpisuje_sam(pole):
    assert zasady.ocen("type_text", {**PISZ, "text": "123456"}, Ctx(fokus=pole)).wolno


def test_rejestracja_z_cdp_wysyla_sam():
    """Formularz rejestracji tak, jak go opisuje sterownik CDP (pola_formularza, opis_formularza)."""
    rejestracja = {"w_formularzu": True, "formularz": [{"rola": "push button", "nazwa": "Wyślij"}],
                   "pola_formularza": [{"tag": "input", "typ": "email", "nazwa": "email"},
                                       {"tag": "input", "typ": "password", "nazwa": "haslo"}],
                   "opis_formularza": {"nazwa": "", "id": "", "action": "/konto", "etykieta": ""}}
    assert zasady.ocen("click", KLIK, Ctx(cel=el("button", "Wyślij", **rejestracja))).wolno
    haslo = el("textbox", "Hasło", "password", stany=["editable", "single-line"], **rejestracja)
    assert zasady.ocen("press_key", {**PISZ, "key": "Return"}, Ctx(fokus=haslo)).wolno
    kontakt = {**rejestracja, "pola_formularza": [{"tag": "input", "typ": "email"}, {"tag": "textarea", "typ": ""}]}
    w = zasady.ocen("click", KLIK, Ctx(cel=el("button", "Wyślij", **kontakt)))
    assert (w.decyzja, w.dane) == (zasady.CZLOWIEK, {"kategoria": "wysylka"})


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
    assert zasady.ocen("type_text", {**PISZ, "text": "123456"}, Ctx(fokus=pole, zgody={"platnosc"})).wolno


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
def test_captcha_agent_probuje_sam(cel):
    assert zasady_natywne.ocen("click", KLIK, Ctx(cel=cel)) is None
    assert zasady.ocen("click", KLIK, Ctx(cel=cel)).wolno
    pierwsza = CtxProby(cel=cel)
    assert zasady_natywne.ocen("click", KLIK, pierwsza) is None and pierwsza.proba_weryfikacji == "dataannotation.tech"


class CtxProby(Ctx):
    """Kontekst z pamięcią prób okienka „jestem człowiekiem” (jak KontekstCDP.weryfikacja)."""

    def __init__(self, proby=0, nieudana=False, **kw):
        super().__init__(**kw)
        self.proby, self.nieudana, self.proba_weryfikacji = proby, nieudana, None

    def weryfikacja(self, args):
        return "dataannotation.tech", self.proby, self.nieudana


TURNSTILE = el("checkbox", "Potwierdź, że jesteś człowiekiem")


@pytest.mark.parametrize("cel", [
    TURNSTILE, el("checkbox", "Verify you are human"), el("checkbox", "I’m not a robot"),
    el("checkbox", "hCaptcha checkbox. Select in order to trigger the challenge"),
    el("checkbox", "", adres_ramki="https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/if/ov2"),
    el("button", "Weryfikuj", adres_ramki="https://www.google.com/recaptcha/api2/bframe"),
])
def test_okienko_jestem_czlowiekiem_rozpoznane(cel):
    assert zasady_natywne.weryfikacja_czlowieka(cel)


@pytest.mark.parametrize("cel", [el("checkbox", "Akceptuję regulamin sklepu"), el("button", "Continue with Google"),
                                 el("checkbox", "", adres_ramki="https://app.dataannotation.tech/signup")])
def test_zwykle_pola_to_nie_weryfikacja(cel):
    assert not zasady_natywne.weryfikacja_czlowieka(cel)
    assert zasady_natywne.ocen("click", KLIK, CtxProby(proby=3, cel=cel)) is None


@pytest.mark.parametrize("nazwa, args, kw", [
    ("click", KLIK, {"cel": TURNSTILE}), ("double_click", KLIK, {"cel": TURNSTILE}),
    ("press_key", {**PISZ, "key": "space"}, {"fokus": TURNSTILE}),
    ("press_key", {**PISZ, "key": "Return"}, {"fokus": TURNSTILE})])
def test_druga_proba_weryfikacji_odmowa_z_droga_telefon_potem_wlasciciel(nazwa, args, kw):
    """16.11: cztery kliknięcia tego samego pola Turnstile na DataAnnotation w ~godzinę. Druga próba: odmowa, a jej
    treść prowadzi Komputer → telefon floty (MCP `phone`, to samo konto) → właściciel (kanban_block needs_input)."""
    w = zasady_natywne.ocen(nazwa, args, CtxProby(proby=1, **kw))
    assert (w.decyzja, w.kod, w.dane) == (zasady.ODMOWA, "weryfikacja_czlowieka", {"strona": "dataannotation.tech"})
    tekst = zasady.wynik_odmowy(w)["content"][0]["text"]
    assert "już było" in tekst and "nie klikaj go ponownie" in tekst and "user-agenta" in tekst
    telefon, wlasciciel = tekst.index("telefonie floty: MCP `phone`"), tekst.index("`kanban_block` z `kind: needs_input`")
    assert telefon < wlasciciel and "to samo konto" in tekst
    assert zasady.wynik_odmowy(w)["structuredContent"]["next_step"] == "choose_another_way"


def test_po_nieudanej_weryfikacji_nawet_pierwsza_proba_to_odmowa():
    w = zasady_natywne.ocen("click", KLIK, CtxProby(nieudana=True, cel=TURNSTILE))
    assert w.kod == "weryfikacja_czlowieka" and "nieudaną weryfikację" in w.powod
    assert zasady_natywne.ocen("right_click", KLIK, CtxProby(proby=1, cel=TURNSTILE)) is None


@pytest.mark.parametrize("tekst", ["Weryfikacja negatywna", "We couldn't verify you're human",
                                   "We couldn’t verify you’re human", "Verification failed. Try again",
                                   "Weryfikacja nie powiodła się"])
def test_tekst_nieudanej_weryfikacji(tekst):
    assert zasady_natywne.nieudana_weryfikacja(tekst)


def test_wzorzec_nieudanej_weryfikacji_bez_skladni_tylko_pythona():
    """Ten sam wzorzec idzie do JavaScriptu (Sterownik.jest_wzorzec): bez (?P<…>), (?i), \\A, \\Z i lookbehind."""
    assert not re.search(r"\(\?[P<i]|\\[AZ]", zasady_natywne.WERYFIKACJA_NIEUDANA)


@pytest.mark.parametrize("adres, oczekiwana", [
    ("https://app.dataannotation.tech/signup?x=1", "dataannotation.tech"), ("https://www.outlier.ai/", "outlier.ai"),
    ("https://konto.sklep.co.uk/a", "sklep.co.uk"), ("about:blank", ""), ("", "")])
def test_strona_proby(adres, oczekiwana):
    assert zasady_natywne.strona(adres) == oczekiwana


class _Okno:
    def __init__(self, url):
        self.url = url


class _Sterownik:
    """Atrapa sterownika CDP: karta 1 z adresem i (opcjonalnie) tekstem nieudanej weryfikacji na stronie."""

    def __init__(self, url="https://app.dataannotation.tech/signup", nieudana=False):
        self.okna, self.nieudana = {1: _Okno(url)}, nieudana

    def okno(self, nr):
        return self.okna.get(nr)

    def aktywne_okno(self):
        return 1

    def jest_wzorzec(self, nr, wzorzec):
        return self.nieudana


def _sesja(wej, karta=None):
    a, b = socket.socketpair()
    s = wejscie_natywne.SesjaNatywna(b, wej)
    if karta:
        s._karta({"karta": karta, "tablica": "default"})
    return s, a


def test_proba_liczona_na_karte_dopiero_po_ostatecznym_werdykcie(tmp_path):
    """Próba liczy się po wszystkich zasadach (odmowa `element_zmieniony` jej nie zjada) i na kartę: druga sesja
    tej samej karty (16.11: sesje 9 i 11) nie dostaje drugiego kliknięcia; inna karta i sesja bez karty tak."""
    wej = wejscie_natywne.WejscieNatywne(tmp_path, "token-testowy")
    wej.sterownik = _Sterownik()
    s1, _a1 = _sesja(wej, "t_87d11e3a")
    args = {"window_id": 1}
    assert s1.ctx.weryfikacja(args) == ("dataannotation.tech", 0, False)
    s1.ctx.proba_weryfikacji = "dataannotation.tech"
    s1._zapisz("click", args, zasady.Werdykt(zasady.ODMOWA, "element_zmieniony", "strona zmieniła się"))
    assert s1.ctx.weryfikacja(args)[1] == 0 and s1.ctx.proba_weryfikacji is None
    s1.ctx.proba_weryfikacji = "dataannotation.tech"
    s1._zapisz("click", args, zasady.Werdykt(zasady.TAK, cel="check box „Potwierdź, że jesteś człowiekiem”"))
    s2, _a2 = _sesja(wej, "t_87d11e3a")
    assert s2.ctx.weryfikacja(args)[1] == 1
    assert _sesja(wej, "t_00000001")[0].ctx.weryfikacja(args)[1] == 0
    assert _sesja(wej)[0].ctx.weryfikacja(args)[1] == 0
    wpis = [json.loads(x) for x in (tmp_path / "dziennik.jsonl").read_text(encoding="utf-8").splitlines()][-1]
    assert (wpis["narzedzie"], wpis["decyzja"]) == ("click", "tak")


def test_nieudana_weryfikacja_zostaje_w_pamieci_karty(tmp_path):
    wej = wejscie_natywne.WejscieNatywne(tmp_path, "token-testowy")
    wej.sterownik = _Sterownik(nieudana=True)
    s, _a = _sesja(wej, "t_87d11e3a")
    assert s.ctx.weryfikacja({"window_id": 1}) == ("dataannotation.tech", 1, True)
    wej.sterownik.nieudana = False                                  # napis zniknął, strona dalej odrzuca
    assert s.ctx.weryfikacja({"window_id": 1})[1:] == (1, False)


def test_pauza_i_odczyt_zostaja_dla_rdzenia():
    assert zasady_natywne.ocen("get_window_state", {}, Ctx()) is None
    assert zasady_natywne.ocen("hotkey", {**PISZ, "keys": ["ctrl", "v"]}, Ctx(wstrzymane=True)) is None
    assert zasady.ocen("hotkey", {**PISZ, "keys": ["ctrl", "v"]}, Ctx(wstrzymane=True)).decyzja == zasady.WSTRZYMANE


def test_nieznany_cel_nie_przechodzi_przez_zasady_natywne():
    assert zasady_natywne.ocen("click", KLIK, Ctx(cel=zasady.NIEZNANY)) is None
    assert zasady.ocen("click", KLIK, Ctx(cel=zasady.NIEZNANY)).kod == "nieznany_cel"


@pytest.mark.parametrize("args", [{"key": "a"}, {"key": "7"}, {"key": "A", "modifiers": ["shift"]},
                                  {"keys": ["shift", "x"]}])
def test_znak_po_znaku_w_polu_karty_tylko_ze_zgoda(args):
    """Rdzeń sprawdza pole tylko przy type_text: znak przez press_key albo hotkey w polu karty czy BLIK też jest
    pisaniem, więc natywnie potrzebuje zgody `platnosc`; w polu hasła agent pisze sam."""
    nazwa = "hotkey" if "keys" in args else "press_key"
    w = zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=el("textbox", "Kod BLIK")))
    assert (w.decyzja, w.kod, w.dane) == (zasady.CZLOWIEK, "pole_wrazliwe", {"kategoria": "platnosc"})
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=el("textbox", "Kod BLIK"), zgody={"platnosc"})) \
        is None
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=el("textbox", "Hasło", "password"))) is None
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=el("textbox", "Uwagi"))) is None
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=None)) is None        # skrót strony bez pola
    assert zasady_natywne.ocen(nazwa, {**PISZ, **args}, Ctx(fokus=zasady.NIEZNANY)).kod == "nieznany_cel"


def test_skrot_z_ctrl_w_polu_karty_to_nie_pisanie():
    karta = Ctx(fokus=el("textbox", "Numer karty"))
    assert zasady_natywne.ocen("hotkey", {**PISZ, "keys": ["ctrl", "a"]}, karta) is None
    assert zasady_natywne.ocen("press_key", {**PISZ, "key": "Tab"}, karta) is None


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
