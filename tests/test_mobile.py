"""Twórca aplikacji (jarvo-mobile): audyt mobilny i decyzja „natywna czy PWA” bez sieci (podstawione odpowiedzi HTTP)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-mobile" / "scripts"))

import audyt_mobilny as am  # noqa: E402
import decyzja  # noqa: E402
import mobile_lib as ml  # noqa: E402

PLAY_HTML = """<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"SoftwareApplication",
"name":"Pizzeria Nova","author":{"@type":"Person","name":"Nova sp. z o.o.","url":"https://nova.pl/"},
"applicationCategory":"FOOD_AND_DRINK","aggregateRating":{"@type":"AggregateRating","ratingValue":"3.6","ratingCount":"412"}}
</script></head><body><div>Pizzeria Nova</div><div>Nova sp. z o.o.</div><div>10 tys.+</div><div>Pobrania</div>
<div>Ostatnia aktualizacja</div><div>12 mar 2024</div><div>Bezpieczeństwo danych</div><div>Dane są zaszyfrowane podczas przesyłania</div>
</body></html>"""

STRONA_HTML = """<html><head><title>Pizzeria Nova</title><link rel="manifest" href="/manifest.json">
<meta name="apple-itunes-app" content="app-id=9999999999"></head><body>
<a href="https://apps.apple.com/pl/app/pizzeria-nova/id1234567890">App Store</a>
<a href="https://play.google.com/store/apps/details?id=pl.nova.app&amp;hl=pl">Google Play</a>
<a href="https://apps.apple.com/pl/app/pyszne-pl/id1039818673">Zamów przez Pyszne</a>
<a href="/polityka-prywatnosci">Polityka prywatności</a></body></html>"""

IOS_NOVA = {"wrapperType": "software", "trackId": 1234567890, "trackName": "Pizzeria Nova", "bundleId": "pl.nova.app",
            "sellerName": "Nova sp. z o.o.", "sellerUrl": "https://nova.pl", "version": "2.1.0",
            "currentVersionReleaseDate": "2026-08-20T10:00:00Z", "averageUserRating": 4.7, "userRatingCount": 120,
            "languageCodesISO2A": ["PL"], "description": "Zamów pizzę dla siebie i znajomych. Możesz płacić BLIK-iem oraz kartą.",
            "screenshotUrls": ["a"] * 6, "releaseNotes": "Poprawki błędów i usprawnienia.",
            "trackViewUrl": "https://apps.apple.com/pl/app/pizzeria-nova/id1234567890?uo=4"}
IOS_PYSZNE = {"wrapperType": "software", "trackId": 1039818673, "trackName": "Pyszne.pl", "bundleId": "com.yourdelivery.pyszne",
              "sellerName": "Takeaway.com Central Core B.V.", "sellerUrl": "https://pyszne.pl",
              "trackViewUrl": "https://apps.apple.com/pl/app/pyszne-pl/id1039818673"}


def fake_http(mapa: dict[str, ml.Odpowiedz]):
    def pobierz(url, **kw):
        for wzorzec, odp in mapa.items():
            if wzorzec in url:
                return odp
        return ml.Odpowiedz(404, "not found", url, "text/html")
    return pobierz


@pytest.fixture
def siec(monkeypatch):
    mapa = {
        "https://nova.pl/.well-known/apple-app-site-association": ml.Odpowiedz(200, "<html>404</html>", "https://nova.pl/", "text/html"),
        "https://nova.pl/.well-known/assetlinks.json": ml.Odpowiedz(
            200, json.dumps([{"relation": ["delegate_permission/common.handle_all_urls"],
                              "target": {"namespace": "android_app", "package_name": "pl.nova.app",
                                         "sha256_cert_fingerprints": ["AA:BB"]}}]),
            "https://nova.pl/.well-known/assetlinks.json", "application/json"),
        "digitalassetlinks.googleapis.com": ml.Odpowiedz(200, json.dumps({"statements": [
            {"target": {"androidApp": {"packageName": "pl.nova.app"}}}]}), "x", "application/json"),
        "app-site-association.cdn-apple.com": ml.Odpowiedz(404, "", "x"),
        "lookup?id=1234567890": ml.Odpowiedz(200, json.dumps({"results": [IOS_NOVA]}), "x", "application/json"),
        "lookup?id=1039818673": ml.Odpowiedz(200, json.dumps({"results": [IOS_PYSZNE]}), "x", "application/json"),
        "lookup?id=9999999999": ml.Odpowiedz(200, json.dumps({"results": []}), "x", "application/json"),
        "lookup?bundleId": ml.Odpowiedz(200, json.dumps({"results": []}), "x", "application/json"),
        "apps.apple.com/pl/app/pizzeria-nova/id1234567890": ml.Odpowiedz(
            200, 'Nova sp. z o.o. has identified itself as a trader for this app. Data Linked to You '
                 '<a aria-label="Developer’s Privacy Policy" href="https://nova.pl/polityka-prywatnosci">x</a>', "x"),
        "play.google.com/store/apps/details?id=pl.nova.app": ml.Odpowiedz(200, PLAY_HTML, "x", "text/html"),
        "https://nova.pl/manifest.json": ml.Odpowiedz(200, json.dumps({"name": "Nova", "icons": [{"src": "i.png", "sizes": "192x192"}],
                                                                      "start_url": "/", "display": "standalone"}), "x"),
        "https://nova.pl/polityka-prywatnosci": ml.Odpowiedz(200, "Polityka", "x"),
        "https://nova.pl/": ml.Odpowiedz(200, STRONA_HTML, "https://nova.pl/", "text/html"),
    }
    monkeypatch.setattr(ml, "pobierz", fake_http(mapa))
    monkeypatch.setattr(am.ml, "DZIS", ml.dt.date(2026, 10, 1))
    monkeypatch.setattr(ml, "DZIS", ml.dt.date(2026, 10, 1))
    return mapa


def statusy(wynik: dict) -> dict[str, str]:
    return {k["id"]: k["status"] for k in wynik["kontrole"]}


def test_audyt_oddziela_partnera_i_wykrywa_bledy(siec):
    w = am.audyt("nova.pl", "Pizzeria Nova")
    assert [a["id"] for a in w["aplikacje"]["ios"]] == [1234567890]
    assert [p["nazwa"] for p in w["aplikacje"]["partnerzy"]] == ["Pyszne.pl"]           # Pyszne nie jest aplikacją pizzerii
    assert [a["pakiet"] for a in w["aplikacje"]["android"]] == ["pl.nova.app"]
    st = statusy(w)
    assert st["LINK-IOS"] == "blad"            # pod adresem AASA jest HTML
    assert st["LINK-ANDROID"] == "ok"
    assert st["WWW-BANER"] == "blad"           # baner wskazuje inną aplikację (9999999999)
    assert st["AND-SWIEZOSC"] == "blad"        # aktualizacja sprzed Androida 15 → ukryta przed nowymi użytkownikami
    assert st["AND-OCENA"] == "blad"           # 3,6★
    assert st["IOS-SWIEZOSC"] == "ok" and st["IOS-DSA"] == "ok" and st["IOS-PRYWATNOSC"] == "ok"
    assert st["IOS-NOWOSCI"] == "ostrz"        # ogólnik w „Co nowego”
    assert st["WWW-PWA"] == "ostrz"            # manifest bez ikony 512
    assert st["WWW-PRYWATNOSC"] == "ok"
    assert w["kontrole"][0]["status"] == "blad"     # błędy na górze
    md = am.raport_md(w)
    assert "partnerzy, nie audytujemy" in md and "Karty poprawek" in md and "Czego audyt nie widzi" in md


def test_audyt_strona_odmawia_reszta_dziala(siec, monkeypatch):
    mapa = dict(siec)
    stary = fake_http(mapa)

    def pobierz(url, **kw):
        if url == "https://nova.pl/":
            raise ConnectionError("Remote end closed connection")
        return stary(url, **kw)
    monkeypatch.setattr(ml, "pobierz", pobierz)
    w = am.audyt("nova.pl", "Pizzeria Nova", pakiety=["pl.nova.app"])
    st = statusy(w)
    assert st["WWW"] == "brak_danych"
    assert st["LINK-ANDROID"] == "ok" and "AND-OCENA" in st


def test_play_parsowanie(siec):
    d = am.android_strona("pl.nova.app")
    assert d["ocena"] == 3.6 and d["liczba_ocen"] == 412 and d["aktualizacja"] == "2024-03-12"
    assert d["pobrania"] == "10 tys.+" and d["data_safety"]["szyfrowanie"] and not d["data_safety"]["usuwanie_danych"]


def test_aasa_oba_formaty():
    stary = {"applinks": {"apps": [], "details": [{"appID": "ABC.pl.a", "paths": ["*"]}]}}
    nowy = {"applinks": {"details": [{"appIDs": ["ABC.pl.b", "ABC.pl.c"], "components": [{"/": "/*"}]}]}}
    assert am._aasa_ids(stary) == {"ABC.pl.a"} and am._aasa_ids(nowy) == {"ABC.pl.b", "ABC.pl.c"}


def test_aasa_przekierowanie_to_blad():
    a = {"url": "https://x.pl/.well-known/apple-app-site-association", "kod": 200, "json": True, "app_ids": ["T.pl.x"],
         "przekierowania": ["https://x.pl/.well-known/apple-app-site-association"], "url_koncowy": "https://www.x.pl/aasa",
         "typ": "application/json"}
    k = am.kontrole_linkow("x.pl", [{"bundleId": "pl.x"}], [], a, {"url": "u"})
    assert next(x for x in k if x.id == "LINK-IOS").status == "blad"


@pytest.mark.parametrize("app,sprzedawca,strona,firma,dom,wynik", [
    ("żappka: zakupy, promocje Żabka", "Żabka Polska sp. z o.o.", None, "Żabka", "zabka.pl", True),
    ("Pyszne.pl", "Takeaway.com Central Core B.V.", "https://pyszne.pl", "McDonald's", "mcdonalds.pl", False),
    ("McDonald's", "McDonald's", "https://www.mcdonaldsapps.com", "McDonald's", "mcdonalds.pl", True),
    ("Allegro Lokalnie", "Allegro Sp. z o.o.", "https://zobacz.allegrolokalnie.pl", "Allegro", "allegro.pl", True),
    ("Sweet Olivia", "TUTOTOONS LTD", None, "Cukiernia Sowa", "cukierniasowa.pl", False),
])
def test_nasza_aplikacja(app, sprzedawca, strona, firma, dom, wynik):
    assert am.nasza(app, sprzedawca, strona, firma, dom) is wynik


def test_ogolnik_w_nowosciach():
    ogolnik = lambda t: len(t) < 300 and bool(am.OGOLNIKI.search(t)) and not am.KONKRETY.search(t)
    assert ogolnik("Stale rozwijamy Żappkę – poprawiamy działanie, usuwamy błędy i dodajemy usprawnienia.")
    assert not ogolnik("Dodaliśmy płatność BLIK i nowy ekran historii zamówień. Poprawki błędów.")


def test_data_pl():
    assert ml.data_pl("Ostatnia aktualizacja 28 wrz 2026") == ml.dt.date(2026, 9, 28)
    assert ml.data_pl("3 października 2025") == ml.dt.date(2025, 10, 3)
    assert ml.data_pl("brak") is None


# ------------------------------------------------------------------ decyzja „natywna czy PWA”

def ocena(**p):
    return decyzja.ocen({"klienci": {"powracajacy": True, "czestotliwosc": "miesiac"}, "juz_ma": ["strona"],
                         "budzet_roczny_usd": 500, **p})


def test_salon_rzadko_pwa_z_wallet():
    w = ocena(funkcje={"musi": ["rezerwacje", "powiadomienia"], "fajnie": ["karta-lojalnosciowa"]})
    assert w["rekomendacja"] == "pwa" and w["uzupelnienie"] == "wallet"
    assert w["wyniki"]["strona"]["odpada"]                         # strona nie wyśle push
    assert any("raz w miesiącu" in r for r in w["wyniki"]["natywna"]["ryzyka"])


def test_ekipa_w_terenie_natywna():
    w = ocena(odbiorcy="pracownicy", klienci={"czestotliwosc": "dzien"},
              funkcje={"musi": ["praca-w-terenie", "aparat", "offline", "podpis"]})
    assert w["rekomendacja"] == "natywna"
    assert any("przeglądarka nie zrobi" in p for p in w["wyniki"]["natywna"]["powody"])


def test_aplikacja_jak_konkurencja_ryzyko_4_2():
    w = ocena(klienci={"czestotliwosc": "rzadziej"}, funkcje={"musi": ["obecnosc-w-sklepie"]})
    assert w["rekomendacja"] == "pwa"
    assert any("4.2" in r for r in w["wyniki"]["natywna"]["ryzyka"])


def test_nieznana_funkcja():
    with pytest.raises(SystemExit):
        ocena(funkcje={"musi": ["teleportacja"]})


def test_raport_decyzji_ma_porownanie():
    w = ocena(funkcje={"musi": ["rezerwacje"]})
    md = decyzja.raport_md(w)
    assert "## Porównanie" in md and "Następny krok" in md and "2026-10-01" in md


def test_szablon_potrzeb_parsuje_sie():
    import yaml
    p = yaml.safe_load(decyzja.SZABLON)
    w = decyzja.ocen(p)
    assert w["rekomendacja"] in decyzja.ROZWIAZANIA


def test_strona_503_to_brak_danych_a_nie_bledy(siec, monkeypatch):
    mapa = dict(siec)
    mapa["https://nova.pl/"] = ml.Odpowiedz(503, "Service Unavailable", "https://nova.pl/", "text/html")
    monkeypatch.setattr(ml, "pobierz", fake_http(mapa))
    st = statusy(am.audyt("nova.pl", "Pizzeria Nova", ios_klucze=["1234567890"]))
    assert st["WWW"] == "brak_danych" and "WWW-PRYWATNOSC" not in st


def test_strona_skryptowa_i_polityka_spod_typowego_adresu(siec, monkeypatch):
    mapa = dict(siec)
    mapa["https://nova.pl/"] = ml.Odpowiedz(200, '<html><div id="root"></div><script src="/app.js"></script></html>',
                                            "https://nova.pl/", "text/html")
    monkeypatch.setattr(ml, "pobierz", fake_http(mapa))
    w = am.audyt("nova.pl", "Pizzeria Nova", ios_klucze=["1234567890"], pakiety=["pl.nova.app"])
    st = statusy(w)
    assert st["WWW-SKLEPY"] == "brak_danych" and st["WWW-USUWANIE"] == "brak_danych"
    assert st["WWW-PRYWATNOSC"] == "ok"               # z karty App Store (ta sama domena), strona skryptowa
    assert w["strona_firmy"]["prywatnosc"] == "https://nova.pl/polityka-prywatnosci"


def test_mala_liczba_ocen_to_prosba_o_ocene():
    assert "prosić o ocenę" in am._popr_oceny("ostrz", 5.0, 2) and "skarg" not in am._popr_oceny("ostrz", 5.0, 2)
    assert "skarg" in am._popr_oceny("blad", 3.2, 900)



def test_host_z_kart_sklepow_gdy_strona_milczy(siec, monkeypatch):
    mapa = dict(siec)
    mapa["https://www.nova.pl/.well-known/assetlinks.json"] = mapa.pop("https://nova.pl/.well-known/assetlinks.json")
    mapa["https://nova.pl/"] = ml.Odpowiedz(503, "", "https://nova.pl/")
    mapa["play.google.com/store/apps/details?id=pl.nova.app"] = ml.Odpowiedz(
        200, PLAY_HTML.replace("https://nova.pl/", "https://www.nova.pl/"), "x", "text/html")
    monkeypatch.setattr(ml, "pobierz", fake_http(mapa))
    w = am.audyt("nova.pl", "Pizzeria Nova", pakiety=["pl.nova.app"])
    assert statusy(w)["LINK-ANDROID"] == "ok"       # Google Play wskazuje www.nova.pl, plik jest na www: bez ostrzeżenia
