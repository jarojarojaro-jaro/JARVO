"""Łowca leadów: KRS, przetargi, strona firmy i lista leadów na danych testowych (bez sieci)."""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-lowca" / "scripts"))
import krs  # noqa: E402
import leady  # noqa: E402
import lowca_lib as ll  # noqa: E402
import przetargi  # noqa: E402
import strona  # noqa: E402

ODPIS = {"odpis": {"naglowekA": {"numerKRS": "0001269879", "dataRejestracjiWKRS": "29.09.2026", "dataOstatniegoWpisu": "29.09.2026"},
                   "dane": {"dzial1": {"danePodmiotu": {"formaPrawna": "SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ",
                                                        "identyfikatory": {"nip": "9522290390", "regon": "54216"},
                                                        "nazwa": "NORAL SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ"},
                                       "siedzibaIAdres": {"siedziba": {"wojewodztwo": "MAZOWIECKIE", "miejscowosc": "WARSZAWA"},
                                                          "adres": {"ulica": "UL. PROSTA", "nrDomu": "1", "kodPocztowy": "00-001", "poczta": "WARSZAWA"},
                                                          "adresPocztyElektronicznej": "BIURO@NORAL.COM.PL"},
                                       "kapital": {"wysokoscKapitaluZakladowego": {"wartosc": "5000,00", "waluta": "PLN"}}},
                            "dzial2": {"reprezentacja": {"sklad": [{"nazwisko": {"nazwiskoICzlon": "K***"}, "funkcjaWOrganie": "PREZES ZARZĄDU"}]}},
                            "dzial3": {"przedmiotDzialalnosci": {"przedmiotPrzewazajacejDzialalnosci": [
                                {"opis": "DZIAŁALNOŚĆ FRYZJERSKA", "kodDzial": "96", "kodKlasa": "21", "kodPodklasa": "Z"}],
                                "przedmiotPozostalejDzialalnosci": [{"kodDzial": "47", "kodKlasa": "91", "kodPodklasa": "Z"}]}}}}}


def test_contacts_helpers():
    assert ll.emaile("Pisz: biuro [at] firma [dot] pl albo jan.kowalski@firma.pl, logo@2x.png") == ["biuro@firma.pl", "jan.kowalski@firma.pl"]
    assert [ll.typ_emaila(e) for e in ("biuro@firma.pl", "sprzedaz@firma.pl", "anna.nowak@firma.pl", "kontakt@gmail.com")] == \
        ["ogolny", "rolowy", "osobowy", "osobowy"]
    assert ll.telefony("tel. 22 123 45 67, +48 601-234-567, NIP 5250000251") == ["+48 221 234 567", "+48 601 234 567"]
    assert ll.nip("525-000-02-51") == "5250000251" and ll.nip("5250000252") is None
    assert ll.domena("https://www.Firma.pl/kontakt") == "firma.pl"
    assert ll.krotka_nazwa("ARAS SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ") == "ARAS sp. z o.o."


def test_krs_normalize_and_signal():
    f = krs.normalizuj(ODPIS["odpis"], "P")
    assert f["nip"] == "9522290390" and f["pkd"] == "96.21.Z" and f["pkd_inne"] == ["47.91.Z"]
    assert f["data_rejestracji"] == "2026-09-29" and f["email"] == "biuro@noral.com.pl" and f["email_typ"] == "ogolny"
    assert f["zarzad_funkcje"] == ["PREZES ZARZĄDU"] and "K***" not in json.dumps(f)       # nazwiska maskowane nie przechodzą
    assert krs.pasuje(f, ["47.9"], ["MAZOWIECKIE"]) and not krs.pasuje(f, ["62"], []) and not krs.pasuje(f, [], ["ŚLĄSKIE"])
    s = krs.sygnal(f, "2026-09-29")
    assert s["typ"] == "krs-nowa-firma" and "działalność fryzjerska" in s["opis"] and s["kontakty"][0]["rodzaj"] == "ogolny"
    assert krs.sygnal(f, "2026-10-05")["typ"] == "krs-wpis"


def test_krs_bulletin_new_companies(monkeypatch):
    def fake_json(url, **kw):
        if "/Biuletyn/" in url:
            return ["100", "101", "102"]
        nr = int(url.split("/OdpisAktualny/")[1][:10])
        if "rejestr=S" in url:
            return None
        o = json.loads(json.dumps(ODPIS))
        o["odpis"]["naglowekA"]["numerKRS"] = f"{nr:010d}"
        if nr == 100:
            o["odpis"]["naglowekA"]["dataRejestracjiWKRS"] = "01.01.2020"       # stara firma z wpisem zmian
        return o
    monkeypatch.setattr(ll, "json_z", fake_json)
    wyniki, staty = krs.biuletyn("2026-09-29", nowe=True, pkd=[], woj=[], limit=50)
    assert staty["w_biuletynie"] == 3 and {w["firma"]["krs"] for w in wyniki} == {"0000000101", "0000000102"}
    wszystkie, _ = krs.biuletyn("2026-09-29", nowe=False, pkd=["96"], woj=["MAZOWIECKIE"], limit=50)
    assert sorted(w["typ"] for w in wszystkie) == ["krs-nowa-firma", "krs-nowa-firma", "krs-wpis"]


def test_tenders(monkeypatch):
    ogl = {"noticeType": "TenderResultNotice", "publicationDate": "2026-09-28T03:33:47Z", "noticeNumber": "2026/BZP 1/01",
           "orderObject": "Dostawa systemu kinowego", "cpvCode": "38652000-0 (Projektory),72000000-5 (Usługi IT)", "orderType": "Delivery",
           "organizationName": "Centrum Kultury ZAMEK", "organizationNationalId": "7781019907", "organizationCity": "Poznań",
           "organizationProvince": "PL30", "objectId": "abc", "htmlBody": "<p>treść</p>",
           "contractors": [{"contractorName": "Cine Project Polska sp. z o.o.", "contractorNationalId": "NIP: 779-21-42-959",
                            "contractorCity": "Przeźmierowo", "contractorProvince": "PL30"}]}
    zapytania = []

    def fake_json(url, **kw):
        zapytania.append(url)
        return [ogl, {**ogl, "publicationDate": "2026-09-29T00:10:00Z"}]      # drugi już z następnego dnia
    monkeypatch.setattr(ll, "json_z", fake_json)
    wyniki, uwagi = przetargi.bzp("2026-09-28", "2026-09-28", ["72"], [], wyniki=True, szukaj=None)
    assert len(wyniki) == 1 and wyniki[0]["typ"] == "przetarg-wygrany" and wyniki[0]["firma"]["nip"] == "7792142959"
    assert wyniki[0]["firma"]["woj"] == "WIELKOPOLSKIE" and wyniki[0]["zrodlo"].endswith("/abc") and uwagi == []
    ogloszenia, _ = przetargi.bzp("2026-09-28", "2026-09-28", ["45"], [], wyniki=False, szukaj=None)
    assert ogloszenia == []                                                      # CPV nie pasuje
    zapytania.clear()
    monkeypatch.setattr(ll, "json_z", lambda url, **kw: zapytania.append(url) or [ogl] * przetargi.MAX_BZP)
    przetargi.bzp("2026-09-28", "2026-09-28", [], [], wyniki=False, szukaj=None)
    assert len(zapytania) == 1 + len(ll.WOJ)                                     # pełny dzień dzielony na województwa


HTML = {
    "https://firma.pl/robots.txt": "User-agent: *\nDisallow: /panel\n",
    "https://firma.pl": """<html><head><title>Firma – strony</title><meta name="description" content="Opis">
        <script src="https://www.googletagmanager.com/gtm.js?id=GTM-1"></script></head><body>
        <a href="/kontakt">Kontakt</a> <a href="/kariera">Praca u nas</a> <a href="/panel/x">Panel</a>
        <a href="https://obca.pl/kontakt">Obca</a> <a href="https://www.linkedin.com/company/firma">in</a>
        <footer>NIP: 525-000-02-51 · rok 2026</footer></body></html>""",
    "https://firma.pl/kontakt": """<html><body><p>Anna Nowak, dyrektor sprzedaży: anna.nowak@firma.pl</p>
        <a href="mailto:biuro@firma.pl">napisz</a> <a href="tel:+48221234567">zadzwoń</a>
        <form><input name="email"><textarea name="wiadomosc"></textarea></form></body></html>""",
    "https://firma.pl/kariera": "<html><body><h2>Specjalista ds. marketingu</h2></body></html>",
}


def test_company_site(monkeypatch):
    odwiedzone = []

    def fake_http(url, **kw):
        odwiedzone.append(url)
        return (200, HTML[url]) if url in HTML else (404, "")
    monkeypatch.setattr(ll, "http", fake_http)
    w = strona.kontakt("firma.pl")
    assert set(w["strony"]) == {"https://firma.pl", "https://firma.pl/kontakt", "https://firma.pl/kariera"}
    assert not any("obca.pl" in u or "/panel" in u for u in odwiedzone)                # tylko domena firmy, robots.txt
    emaile = {e["email"]: e for e in w["emaile"]}
    assert emaile["biuro@firma.pl"]["rodzaj"] == "ogolny" and emaile["anna.nowak@firma.pl"]["rodzaj"] == "osobowy"
    assert "dyrektor sprzedaży" in emaile["anna.nowak@firma.pl"]["kontekst"] and emaile["biuro@firma.pl"]["zrodlo"].endswith("/kontakt")
    assert w["telefony"][0]["numer"] == "+48 221 234 567" and w["formularz"] == "https://firma.pl/kontakt"
    assert w["kariera"] == "https://firma.pl/kariera" and w["nip"] == ["5250000251"]
    assert "Google Tag Manager" in w["technologie"] and w["social"]["linkedin"] == "https://linkedin.com/company/firma"
    assert w["odcisk"] and strona.odcisk("Oferta  2026") == strona.odcisk("Oferta 2031") != strona.odcisk("Nowa oferta")


def test_blocked_source_is_a_stop(monkeypatch):
    class R:
        status = 200
        headers = type("H", (), {"get_content_charset": staticmethod(lambda: "utf-8")})()
        def read(self, n): return b"<html><title>Dost\xc4\x99p zablokowany / Access Blocked</title></html>"
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(ll.urllib.request, "urlopen", lambda req, timeout: R())
    with pytest.raises(ll.Blokada):
        ll.http("https://ezamowienia.gov.pl/x", pamiec_h=0)


def _projekt(tmp_path: Path) -> Path:
    p = tmp_path / "leady"
    p.mkdir()
    (p / "ICP.yaml").write_text("nazwa: Test\ndopasowanie:\n  woj: [MAZOWIECKIE]\n  wyklucz_formy: [FUNDACJA]\n  prog: 1.0\n"
                                "sygnaly:\n  krs-nowa-firma: {waga: 3, okno: 30}\n", encoding="utf-8")
    return p


def test_leads_scoring_dedupe_and_monitoring(tmp_path):
    p = _projekt(tmp_path)
    f = krs.normalizuj(ODPIS["odpis"], "P")
    s1 = krs.sygnal(f, "2026-09-29")
    s2 = {"typ": "rekrutacja", "data": "2026-09-25", "zrodlo": "https://firma.pl/kariera", "opis": "szuka specjalisty ds. marketingu",
          "firma": {"nazwa": f["nazwa"], "nip": "952-229-03-90", "woj": "MAZOWIECKIE"}}
    fund = {**s1, "firma": {**s1["firma"], "nip": "5250000251", "nazwa": "FUNDACJA X"}, "szczegoly": {"forma": "FUNDACJA"}}
    slask = {**s1, "firma": {**s1["firma"], "nip": "7792142959", "woj": "ŚLĄSKIE"}}
    plik = tmp_path / "s.jsonl"
    plik.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in (s1, s2, fund, slask, s1)), encoding="utf-8")
    assert leady.cmd_dodaj(p, [str(plik)]) == 0
    assert len(ll.czytaj_jsonl(str(p / "sygnaly.jsonl"))) == 4                   # duplikat s1 odrzucony
    leady.cmd_ocen(p, top=10, monitoring=True, dzis=dt.date(2026, 9, 30))
    rows = list(csv.DictReader((p / "leady.csv").open(encoding="utf-8")))
    assert [r["klucz"] for r in rows] == ["nip:9522290390"]                      # fundacja wykluczona, śląskie poza ICP
    r = rows[0]
    assert r["email"] == "biuro@noral.com.pl" and "rekrutacja" in r["sygnaly"] and int(r["ocena"]) > 48
    md = (p / "LEADY.md").read_text(encoding="utf-8")
    assert "NORAL sp. z o.o." in md and "to jest baza" in md and "UŚUDE" in md and "[KRS](" in md
    leady.cmd_powod(p, "nip:9522290390", "nowa firma bez strony, szuka marketingowca")
    leady.cmd_ocen(p, top=10, monitoring=True, dzis=dt.date(2026, 10, 1))
    md = (p / "LEADY.md").read_text(encoding="utf-8")
    assert "0 nowych firm" in md and "szuka marketingowca" not in md.split("| # |")[1].split("Pełna")[0]   # tylko nowe
    assert "szuka marketingowca" in (p / "leady.csv").read_text(encoding="utf-8")
    leady.cmd_ocen(p, top=10, monitoring=False, dzis=dt.date(2026, 12, 30))       # wszystko poza oknem świeżości
    assert list(csv.DictReader((p / "leady.csv").open(encoding="utf-8"))) == []
