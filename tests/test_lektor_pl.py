"""Polski lektor lokalny (jarvo-tts, głosy pl-PL-Matcha-*): normalizator tekstu, tablica symboli, podział na zdania.

Fonemizer (espeak-ng) i model ONNX są tylko w obrazie; tu sprawdzamy część w czystym Pythonie. Próba mowy obu głosów
idzie przy budowie obrazu (`jarvo-tts --sprawdz` w infra/Dockerfile).
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "infra" / "bin"
sys.path.insert(0, str(BIN))

import jarvo_tts_matcha as fon  # noqa: E402
import jarvo_tts_pl as pl  # noqa: E402
from jarvo_tts_pl import normalizuj as n  # noqa: E402


def _jarvo_tts():
    loader = importlib.machinery.SourceFileLoader("jarvo_tts", str(BIN / "jarvo-tts"))
    spec = importlib.util.spec_from_loader("jarvo_tts", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ liczebniki

@pytest.mark.parametrize("liczba, slowa", [
    (0, "zero"), (7, "siedem"), (11, "jedenaście"), (21, "dwadzieścia jeden"), (100, "sto"), (215, "dwieście piętnaście"),
    (1000, "tysiąc"), (2026, "dwa tysiące dwadzieścia sześć"), (5000, "pięć tysięcy"), (12500, "dwanaście tysięcy pięćset"),
    (22000, "dwadzieścia dwa tysiące"), (1_000_000, "milion"), (3_400_000, "trzy miliony czterysta tysięcy"),
    (2_000_000_000, "dwa miliardy"),
])
def test_liczebnik_glowny(liczba, slowa):
    assert pl.liczebnik(liczba) == slowa


def test_liczebnik_dopelniacz_i_rodzaj():
    assert pl.liczebnik(5, dop=True) == "pięciu"
    assert pl.liczebnik(22, dop=True) == "dwudziestu dwóch"
    assert pl.liczebnik(2000, dop=True) == "dwóch tysięcy"
    assert pl.liczebnik(1000, dop=True) == "tysiąca"
    assert pl.liczebnik(1, rodzaj="z") == "jedna" and pl.liczebnik(1, rodzaj="n") == "jedno"
    assert pl.liczebnik(2, rodzaj="z") == "dwie" and pl.liczebnik(22, rodzaj="z") == "dwadzieścia dwie"
    assert pl.liczebnik(21, rodzaj="z") == "dwadzieścia jeden"               # „jeden” w złożonej liczbie bez odmiany


@pytest.mark.parametrize("liczba, forma, slowa", [
    (1, "m", "pierwszy"), (2, "d", "drugiego"), (3, "zm", "trzecia"), (3, "d", "trzeciego"), (11, "d", "jedenastego"),
    (15, "zd", "piętnastej"), (15, "zn", "piętnastą"), (21, "ms", "dwudziestym pierwszym"),
    (2026, "d", "dwa tysiące dwudziestego szóstego"), (2026, "ms", "dwa tysiące dwudziestym szóstym"),
    (1990, "d", "tysiąc dziewięćset dziewięćdziesiątego"), (1900, "d", "tysiąc dziewięćsetnego"),
    (2000, "d", "dwutysięcznego"), (2001, "m", "dwa tysiące pierwszy"),
])
def test_liczebnik_porzadkowy(liczba, forma, slowa):
    assert pl.porzadkowy(liczba, forma) == slowa


def test_odmiana_rzeczownika_po_liczbie():
    f = ("złoty", "złote", "złotych")
    assert [pl.odmiana(k, f) for k in (1, 2, 4, 5, 12, 14, 22, 25, 102)] == [
        "złoty", "złote", "złote", "złotych", "złotych", "złotych", "złote", "złotych", "złote"]


# ------------------------------------------------------------------ normalizator

@pytest.mark.parametrize("tekst, oczekiwany", [
    # daty i lata
    ("Dziś jest 11.10.2026.", "Dziś jest jedenastego października dwa tysiące dwudziestego szóstego roku."),
    ("Termin: 11.10.2026 r. Potem przerwa.",
     "Termin: jedenastego października dwa tysiące dwudziestego szóstego roku. Potem przerwa."),
    ("Raport z 2024-03-01.", "Raport z pierwszego marca dwa tysiące dwudziestego czwartego roku."),
    ("Od 1 stycznia 2027 r.", "Od pierwszego stycznia dwa tysiące dwudziestego siódmego roku."),
    ("W 2026 roku AI zmieni wszystko.", "W dwa tysiące dwudziestym szóstym roku ej aj zmieni wszystko."),
    ("Mieszkam tu od 2019 r.", "Mieszkam tu od dwa tysiące dziewiętnastego roku."),
    ("To był 1990 rok.", "To był tysiąc dziewięćset dziewięćdziesiąty rok."),
    ("W XXI w. wszystko przyspieszyło.", "W dwudziestym pierwszym wieku wszystko przyspieszyło."),
    # godziny
    ("Start o godz. 15:30.", "Start o godzinie piętnastej trzydzieści."),
    ("Spotkajmy się o 9:05 albo do 17:00.", "Spotkajmy się o dziewiątej zero pięć albo do siedemnastej."),
    ("Jest 12:45.", "Jest dwunasta czterdzieści pięć."),
    # kwoty, procenty, mnożniki, ułamki
    ("Koszt: 1 zł, 2 zł, 5 zł, 22 zł.", "Koszt: jeden złoty, dwa złote, pięć złotych, dwadzieścia dwa złote."),
    ("Budżet to 2,5 mln zł.", "Budżet to dwa i pół miliona złotych."),
    ("Zebraliśmy 1,5 tys. zł.", "Zebraliśmy półtora tysiąca złotych."),
    ("Przychód 12 500 zł i 3 tys. klientów.", "Przychód dwanaście tysięcy pięćset złotych i trzy tysiące klientów."),
    ("Wzrost o 42% w rok.", "Wzrost o czterdzieści dwa procent w rok."),
    ("Spadek o 0,75%.", "Spadek o zero przecinek siedemdziesiąt pięć procent."),
    ("Liczba pi to 3,14.", "Liczba pi to trzy przecinek czternaście."),
    ("Od 5 do 10 zł, ok. 20 osób.", "Od pięciu do dziesięciu złotych, około dwudziestu osób."),
    ("Trwa 10–15 minut.", "Trwa od dziesięciu do piętnastu minut."),
    ("Kosztuje $20 albo 15 €.", "Kosztuje dwadzieścia dolarów albo piętnaście euro."),
    ("Mamy 3.5 GB i -5°C.", "Mamy trzy i pół gigabajta i minus pięć stopni Celsjusza."),
    ("Jest 2x szybszy.", "Jest dwa razy szybszy."),
    ("Mamy 2 minuty, 2 godz. i 1 h.", "Mamy dwie minuty, dwie godziny i jedna godzina."),
    ("Było 1 000 000 widzów.", "Było milion widzów."),
    # telefony i kody
    ("Zadzwoń: +48 600 700 800.", "Zadzwoń: plus czterdzieści osiem sześćset siedemset osiemset."),
    ("Numer 600-700-800 albo 12 345 67 89.",
     "Numer sześćset siedemset osiemset albo dwanaście trzysta czterdzieści pięć sześćdziesiąt siedem osiemdziesiąt "
     "dziewięć."),
    ("Kod 007, tel. 600700800.", "Kod zero zero siedem, telefon sześćset siedemset osiemset."),
    # skróty
    ("Np. w poniedziałek, itd.", "Na przykład w poniedziałek, i tak dalej."),
    ("Zrobimy to itd. Potem reszta.", "Zrobimy to i tak dalej. Potem reszta."),
    ("Biuro przy ul. Długiej, pokój nr 12.", "Biuro przy ulicy Długiej, pokój numer dwanaście."),
    ("Ok. godz. 9 dzwoni dr Nowak.", "Około godziny dziewiątej dzwoni doktor Nowak."),
    ("Wg planu m.in. testy, tzn. sprawdzenie.", "Według planu między innymi testy, to znaczy sprawdzenie."),
    # skrótowce
    ("Raport w PDF wyślemy do HQ.", "Raport w pe de ef wyślemy do ha ku."),
    ("TTS i SEO to podstawa.", "te te es i es e o to podstawa."),
    ("Wyślij PDF-a.", "Wyślij pe de efa."),
    ("AI pomaga, OK?", "ej aj pomaga, okej?"),
    ("UWAGA NA STOPIEŃ PRZY WEJŚCIU", "uwaga na stopień przy wejściu"),
    ("Pisz na kontakt@jarvo.pl.", "Pisz na kontakt małpa jarvo kropka pe el."),
])
def test_normalizator(tekst, oczekiwany):
    assert n(tekst) == oczekiwany


def test_normalizator_zostawia_angielskie_wstawki_i_zwykly_tekst():
    assert n("Dzięki za {feedback}, wrzucę to na {Slack}a.") == "Dzięki za {feedback}, wrzucę to na {Slack}a."
    assert n("Po {PDF}ie 5 zł.") == "Po {PDF}ie pięć złotych."                # w klamrach bez zmian, poza nimi jak zwykle
    zwykly = "Zanim zaczniemy gotować, umyjmy ręce. Czy mam włączyć światło w kuchni?"
    assert n(zwykly) == zwykly
    assert not any(c.isdigit() for c in n("Mamy 7 dni, 24 h, 365 dni w roku i 1000 pomysłów."))


# ------------------------------------------------------------------ fonemizer: symbole i numery (bez espeak-ng)

def test_tablica_symboli_matcha_pl():
    assert len(fon.SYMBOLE) == 179 and fon.SYMBOLE[0] == "_" and fon.SYMBOLE[-1] == "̃"
    assert fon.SYMBOL_ID[" "] == 16 and fon.SYMBOL_ID["'"] == 176               # podwójny apostrof: ostatni, jak w Matcha
    assert fon.na_id("ab") == [0, fon.SYMBOL_ID["a"], 0, fon.SYMBOL_ID["b"], 0]
    assert fon.na_id("a☃b") == fon.na_id("ab")                                    # nieznany znak pominięty


def test_fonemy_z_espeak_jak_w_treningu():
    """Wzorce z symbols.js Space machinekind/matcha-tts-pl-v2 (port przeglądarkowy, „znak w znak” z treningiem)."""
    pytest.importorskip("phonemizer")
    pytest.importorskip("espeakng_loader")
    wzorce = {
        "Cześć, jestem robotem. Czy mogę ci w czymś pomóc?": "tʃˈɛɕtɕ, jˌɛstɛm rɔbˈɔtɛm. tʃɨ mˈɔɡɛ tɕi f tʃˈɨmɕ pˈɔmuts?",
        "Dr Nowak mówi: „to jest test” — naprawdę!": "dˈɔktɔr nˈɔvak mˈuvi: tɔ jɛst tˈɛst, naprˈavdɛ!",
        "Serio? To niesamowite!": "sˈɛrjɔ? tɔ ɲʲˌɛsamɔvˈitɛ!",
    }
    for tekst, ipa in wzorce.items():
        assert fon.fonemy(tekst) == ipa


# ------------------------------------------------------------------ jarvo-tts: głosy, zdania, akapity

def test_jarvo_tts_glosy_i_domyslny():
    t = _jarvo_tts()
    assert t.DOMYSLNY_GLOS == "pl-PL-Matcha-Meski"
    assert set(t.GLOSY) == {"pl-PL-Matcha-Meski", "pl-PL-Matcha-Damski", "en-US-Paradee"}
    assert {g["katalog"] for g in t.MATCHA_GLOSY.values()} == {"meski", "damski"}
    assert t.PAUZY_PL["zdanie"] == 0.33 and t.PAUZY_PL["akapit"] == 1.0             # jak PAUZY w film.py


def test_pauzy_lektora_jak_w_narracji_filmu():
    src = (REPO / "profiles" / "jarvo-wideo" / "scripts" / "film.py").read_text(encoding="utf-8")
    assert '"zdanie": 0.33' in src and '"akapit": 1.0' in src


def test_jarvo_tts_akapity_i_zdania_po_polsku():
    t = _jarvo_tts()
    tekst = "Spotkanie 11.10.2026 r. o godz. 15:30, np. w HQ. Potem przerwa.\n\nNowy akapit: dr Nowak mówi. Koniec!"
    assert t.podziel_akapity(tekst) == [
        ["Spotkanie 11.10.2026 r. o godz. 15:30, np. w HQ.", "Potem przerwa."],
        ["Nowy akapit: dr Nowak mówi.", "Koniec!"]]
    assert t.podziel_akapity(" \n\n ") == []


def test_jarvo_tts_dlugie_zdanie_w_kawalkach():
    t = _jarvo_tts()
    zdanie = ", ".join(["to jest dość długi fragment zdania"] * 30) + "."
    kawalki = t._kawalki_tekstu(zdanie, limit=120)
    assert all(len(k) <= 120 for k in kawalki) and len(kawalki) > 5
    assert " ".join(kawalki).replace(" ,", ",") == zdanie


def test_jarvo_tts_nieznany_glos_w_zadaniu(tmp_path):
    t = _jarvo_tts()
    plik = tmp_path / "z.json"
    plik.write_text(json.dumps([{"tekst": "Test.", "wyjscie": str(tmp_path / "a.wav"), "glos": "pl-PL-Nikt"}]))
    with pytest.raises(SystemExit):
        t.main(["--wsad", str(plik)])
    with pytest.raises(SystemExit):
        t.main(["Test.", "-o", str(tmp_path / "a.wav"), "--glos", "pl-PL-Nikt"])
