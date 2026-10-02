"""Twórca aplikacji, etap 6: aplikacja ze strony firmy (dane, sygnały, funkcje natywne, szkice konfiguracji) i utrzymanie
(terminy sklepów z .ics, stan, plan Expo SDK, poprawka EAS Update tylko do zgodnego buildu sklepowego, za zgodą)."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-mobile" / "scripts"))

import aplikacja as ap  # noqa: E402
import audyt_mobilny as am  # noqa: E402
import mobile_lib as ml  # noqa: E402
import utrzymanie as ut  # noqa: E402
import wydanie as wy  # noqa: E402
import ze_strony as zs  # noqa: E402
import zgodnosc as zg  # noqa: E402

from test_mobile_sklep import app  # noqa: E402,F401  (fixture aplikacji wzorcowej)

# ------------------------------------------------------------------ strona firmy (atrapa)

GLOWNA = """<!doctype html><html lang="pl"><head><title>Pizzeria Nova | Kraków</title>
<meta name="description" content="Pizzeria Nova ✓ Pizza neapolitańska z pieca opalanego drewnem 🍕 Rezerwuj stolik online i zamów na wynos.">
<meta name="theme-color" content="#337ab7"><link rel="stylesheet" href="/style.css">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Restaurant","name":"Pizzeria Nova",
"telephone":"+48 12 345 67 89","email":"czesc@pizzerianova.pl","logo":"https://pizzerianova.pl/logo.svg",
"address":{"@type":"PostalAddress","streetAddress":"ul. Długa 5","postalCode":"31-147","addressLocality":"Kraków"},
"openingHours":["Mo-Fr 12:00-22:00","Sa-Su 13:00-23:00"]}</script></head>
<body><nav><a href="/menu">Menu</a><a href="/rezerwacje">Rezerwacje</a><a href="/karta">Karta stałego klienta</a>
<a href="/kontakt">Kontakt</a><a href="/blog">Blog</a></nav>
<h1>Pizza neapolitańska</h1><p>Zarezerwuj stolik albo zamów na wynos. Nasze lokale: Kazimierz i Podgórze, dojazd tramwajem.</p>
<a href="/polityka-prywatnosci">Polityka prywatności</a><a href="https://www.facebook.com/pizzerianova">Facebook</a>
<a href="https://evil.example/phish">obcy host</a></body></html>"""
MENU = "<html><body><h1>Menu</h1>" + "".join(
    f"<p>{n} {c} zł</p>" for n, c in (("Margherita", "32"), ("Marinara", "28"), ("Diavola", "38"), ("Capricciosa", "39"),
                                      ("Quattro formaggi", "41"), ("Tiramisu", "19"))) + "</body></html>"
KONTAKT = """<html><body><h1>Kontakt</h1><a href="tel:+48123456789">12 345 67 89</a>
<a href="mailto:rezerwacje@pizzerianova.pl">rezerwacje@pizzerianova.pl</a><form><input name="x"></form></body></html>"""
KARTA = "<html><body><p>Karta stałego klienta: co dziesiąta pizza gratis, zbieraj pieczątki.</p></body></html>"
REZERWACJE = "<html><body><p>Rezerwacja stolika przez Booksy albo telefonicznie.</p></body></html>"
LOGO = '<svg xmlns="http://www.w3.org/2000/svg"><path fill="#B3261E" d="M0 0h10v10z"/><circle fill="#B3261E" r="3"/></svg>'
CSS = "body{background:#ffffff} .btn{background-color:#337ab7} a{color:#0d6efd}"


def strona(monkeypatch, nadpisz: dict | None = None):
    """ml.pobierz → atrapa pizzerianova.pl; zwraca listę odwiedzonych adresów."""
    adresy = {"https://pizzerianova.pl": GLOWNA, "https://pizzerianova.pl/menu": MENU, "https://pizzerianova.pl/kontakt": KONTAKT,
              "https://pizzerianova.pl/karta": KARTA, "https://pizzerianova.pl/rezerwacje": REZERWACJE,
              "https://pizzerianova.pl/logo.svg": LOGO, "https://pizzerianova.pl/style.css": CSS, **(nadpisz or {})}
    odwiedzone = []

    def pobierz(url, **kw):
        odwiedzone.append(url)
        url = url.rstrip("/") if url.count("/") <= 3 else url
        if url not in adresy:
            return ml.Odpowiedz(404, "", url, "text/html")
        tresc = adresy[url]
        if isinstance(tresc, Exception):
            raise tresc
        return ml.Odpowiedz(200, tresc, url + ("/" if url.count("/") == 2 else ""), "text/html")
    monkeypatch.setattr(ml, "pobierz", pobierz)
    return odwiedzone


def test_ze_strony_dane_firmy_i_marka(monkeypatch):
    odwiedzone = strona(monkeypatch)
    r = zs.analizuj("pizzerianova.pl")
    assert r["nazwa"] == "Pizzeria Nova" and r["bundle"] == "pl.pizzerianova.app"
    assert r["opis"].startswith("Pizza neapolitańska") and "✓" not in r["opis"] and "🍕" not in r["opis"]
    assert r["firma"]["telefony"][0] == "+48123456789" and "czesc@pizzerianova.pl" in r["firma"]["emaile"]
    assert r["firma"]["prywatnosc"] == "https://pizzerianova.pl/polityka-prywatnosci"
    assert r["marka"]["kolor"] == "#B3261E"                     # Bootstrap #337AB7 z theme-color to nie marka; kolor z logo SVG
    assert r["spolecznosci"] == ["https://www.facebook.com/pizzerianova"]
    assert not any("evil.example" in u for u in odwiedzone)       # tylko ten sam host
    assert odwiedzone.index("https://pizzerianova.pl/kontakt") < odwiedzone.index("https://pizzerianova.pl/blog")  # kontakt najpierw


def test_ze_strony_sygnaly_funkcje_i_tresci(monkeypatch):
    strona(monkeypatch)
    r = zs.analizuj("https://pizzerianova.pl")
    assert {"rezerwacje", "lojalnosc", "zamowienia", "menu", "lokale"} <= set(r["sygnaly"])
    mocne = {f["funkcja"] for f in r["funkcje"] if f["mocna"]}
    assert {"przypomnienia", "karta-qr", "oferta-offline", "zadzwon-nawiguj"} <= mocne and not r["ryzyko_4_2"]
    assert len(r["pozycje"]) == 6 and r["pozycje"][0] == {"nazwa": "Margherita", "cena": "32 zł", "zrodlo": "https://pizzerianova.pl/menu"}
    assert [e["trasa"] for e in r["ekrany"]][:4] == ["/", "/menu", "/rezerwacje", "/karta-stalego-klienta"]


def test_ze_strony_menu_bez_nav_z_podkategoriami(monkeypatch):
    """Menu w div#menu (bez <nav>): ekrany z pozycji najwyższego poziomu, podkategorie w zawartości, bez „Strona główna”."""
    glowna = """<html><head><title>Cukiernia Sowa</title><meta name="description" content="Cukiernia Sowa ➤ Torty na zamówienie
    ✔️ Sieć cukierni w całej Polsce ⭐ Zobacz!"></head><body><div id="menu"><ul class="menu-main">
    <li><a href="/">Strona główna</a></li><li><a href="/produkty">Produkty</a><ul class="sub"><li><a href="/torty">Torty</a></li>
    <li><a href="/ciasta">Ciasta</a></li></ul></li><li><a href="/cukiernie">Cukiernie</a></li><li><a href="/kontakt">Kontakt</a></li>
    </ul></div><div class="tresc"><a href="/promocja">Promocja</a></div><p>Torty na zamówienie, znajdź cukiernię.</p></body></html>"""
    strona(monkeypatch, {"https://pizzerianova.pl": glowna})
    r = zs.analizuj("https://pizzerianova.pl")
    assert [(e["trasa"], e["zawartosc"].split(";")[0]) for e in r["ekrany"][1:]] == [
        ("/produkty", "kategorie: Torty, Ciasta"), ("/cukiernie", "treść z https://pizzerianova.pl/cukiernie")]
    assert [m["tekst"] for m in r["menu_strony"]] == ["Strona główna", "Produkty", "Torty", "Ciasta", "Cukiernie", "Kontakt"]
    assert r["opis"] == "Torty na zamówienie. Sieć cukierni w całej Polsce."


def test_ze_strony_wizytowka_to_ryzyko_4_2(monkeypatch):
    strona(monkeypatch, {"https://pizzerianova.pl": "<html><head><title>Biuro Rachunkowe Kowalski</title></head>"
                                                     "<body><p>Księgowość dla firm. Zadzwoń: 600 100 200.</p></body></html>"})
    r = zs.analizuj("https://pizzerianova.pl")
    assert r["ryzyko_4_2"] and r["mocnych_funkcji"] == 0
    assert r["firma"]["telefony"] == ["600100200"] and r["marka"]["kolor"] is None
    plan = zs.plan_md(r)
    assert "4.2" in plan and "natywna-czy-pwa" in plan and "brak (praca dla Weba" in plan


def test_ze_strony_siec_lokali_osobno(monkeypatch):
    lokale = "<html><body>" + "".join(f"<p>Lokal {i}: 12 300 {i:02d} {i:02d}</p>" for i in range(10, 30)) + "</body></html>"
    strona(monkeypatch, {"https://pizzerianova.pl/kontakt": lokale})
    r = zs.analizuj("https://pizzerianova.pl")
    assert len(r["lokale_telefony"]) >= 20 and len(r["firma"]["telefony"]) <= 3
    assert r["firma"]["telefony"][0] == "+48123456789"            # z JSON-LD, nie pierwszy z listy lokali


def test_ze_strony_szkice_przechodza_walidacje(monkeypatch, tmp_path):
    strona(monkeypatch)
    assert zs.main(["analizuj", "https://pizzerianova.pl", "--out", str(tmp_path / "nova")]) == 0
    out = tmp_path / "nova"
    assert {p.name for p in out.iterdir()} == {"ze-strony.json", "PLAN-ZE-STRONY.md", "aplikacja.yaml", "zgodnosc.yaml", "tresci.json"}
    a = ap.wczytaj_yaml(out / "aplikacja.yaml")
    assert ap.sprawdz_konfiguracje(a, konta=False) == []
    assert a["firma"]["adres"].startswith("ul. Długa 5") and a["kolor_glowny"] == "#B3261E"
    z = yaml.safe_load((out / "zgodnosc.yaml").read_text(encoding="utf-8"))
    assert "powiadomienia" in z["uprawnienia"] and z["logowanie"] == [] and z["platnosci"] == ["fizyczne", "uslugi"]
    w = zg.ocen(z)
    assert w["bledy"] == [] and "expo-notifications" in w["konfiguracja"]["paczki"]
    tresci = json.loads((out / "tresci.json").read_text(encoding="utf-8"))
    assert len(tresci["pozycje"]) == 6 and tresci["godziny"]


def test_ze_strony_braki_oznaczone_do_uzupelnienia():
    r = {"url": "https://x.pl", "url_koncowy": "https://x.pl/", "data": "2026-10-02", "nazwa": "X", "domena": "x.pl",
         "bundle": "pl.x.app", "opis": "", "marka": {"kolor": None}, "firma": {"telefony": [], "emaile": []}}
    y = zs.aplikacja_yaml(r)
    assert y.count("JARVO-TODO") == 4 and "#2F5BEA" in y            # kolor, adres, e-mail, telefon
    assert ap.sprawdz_konfiguracje(yaml.safe_load(y), konta=False)  # bez e-maila aplikacja nie powstanie


def test_ze_strony_kody(monkeypatch, tmp_path):
    strona(monkeypatch, {"https://pizzerianova.pl": ml.Blokada("robots.txt zabrania")})
    assert zs.main(["analizuj", "https://pizzerianova.pl", "--out", str(tmp_path / "a")]) == 3
    strona(monkeypatch, {"https://pizzerianova.pl": ConnectionError("timeout")})
    assert zs.main(["analizuj", "https://pizzerianova.pl", "--out", str(tmp_path / "b")]) == 1
    assert not (tmp_path / "a").exists() and not (tmp_path / "b").exists()


# ------------------------------------------------------------------ terminy i kalendarz

def test_terminy_od_dzis_z_prognoza():
    t = ut.terminy(dt.date(2026, 10, 2), lata=1)
    assert all(x["data"] >= dt.date(2026, 10, 2) for x in t) and t == sorted(t, key=lambda x: x["data"])
    assert t[0]["data"] == dt.date(2026, 11, 1) and "API 36" in t[0]["co"] and "prognoza" not in t[0]["co"]
    assert any(x["data"] == dt.date(2027, 2, 1) and "16 KB" in x["co"] for x in t)
    api = next(x for x in t if x["data"] == dt.date(2027, 8, 31))
    assert "API 37" in api["co"] and "prognoza" in api["co"]
    assert not any(x["sklep"] == "Expo" for x in t)
    stary = ut.terminy(dt.date(2026, 10, 2), lata=1, sdk_aplikacji=55, sdk_najnowszy=57)
    assert any(x["sklep"] == "Expo" and "SDK 55" in x["co"] for x in stary)


def test_ics_jest_poprawny():
    t = ut.terminy(dt.date(2026, 10, 2), lata=1)
    s = ut.ics(t, "Salon Ola, Kraków")
    linie = s.split("\r\n")
    assert linie[0] == "BEGIN:VCALENDAR" and linie[-2] == "END:VCALENDAR" and s.endswith("\r\n")
    assert s.count("BEGIN:VEVENT") == len(t) == s.count("END:VEVENT") == s.count("TRIGGER:-P30D")
    assert "SUMMARY:Salon Ola\\, Kraków: Google Play" in s and "DTSTART;VALUE=DATE:20261101" in s
    uid = [l for l in linie if l.startswith("UID:")]
    assert len(set(uid)) == len(uid)
    assert all("," not in l.split(":", 1)[1].replace("\\,", "") for l in linie if l.startswith(("SUMMARY:", "DESCRIPTION:")))


def test_kalendarz_zapisuje_pliki(app, monkeypatch):
    monkeypatch.setattr(ml, "DZIS", dt.date(2026, 10, 2))
    r = ut.kalendarz(app, lata=2)
    assert (app / "out" / "utrzymanie" / "terminy.ics").read_text(encoding="utf-8").startswith("BEGIN:VCALENDAR")
    md = (app / "out" / "utrzymanie" / "KALENDARZ.md").read_text(encoding="utf-8")
    assert "Salon Ola" in md and "| 2027-02-01 | Google Play |" in md and len(r["terminy"]) > 6


# ------------------------------------------------------------------ stan i SDK

def _buildy(kat: Path, runtime: str = "fp-1") -> None:
    ml.zapisz(kat / "out" / "wydanie" / "buildy.json", json.dumps({"buildy": [
        {"id": "b-ios", "platforma": "IOS", "status": "FINISHED", "wersja": "1.0.0", "numer": "7", "runtime": runtime},
        {"id": "b-and", "platforma": "ANDROID", "status": "FINISHED", "wersja": "1.0.0", "numer": "7", "runtime": runtime}]}))


def test_stan_bez_sieci(app):
    _buildy(app)
    r = ut.stan(app, siec=False)
    assert r["expo"] == "57.0.26" and "sdk_npm" not in r and "app_store" not in r
    md = (app / "out" / "utrzymanie" / "STAN.md").read_text(encoding="utf-8")
    assert "Expo SDK 57.0.26" in md and "IOS 1.0.0 (7), ANDROID 1.0.0 (7)" in md and "## Najbliższe terminy" in md


def test_stan_ze_sklepem_i_opiniami(app, monkeypatch):
    monkeypatch.setattr(ut, "sdk_z_npm", lambda: {"latest": "58.0.3", "next": None, "sdk": [56, 57, 58]})
    monkeypatch.setattr(am, "ios_lookup", lambda klucz: [{"trackId": 1234567890, "version": "1.0.0", "averageUserRating": 4.2,
                                                          "userRatingCount": 31, "currentVersionReleaseDate": "2026-09-01T07:00:00Z"}]
                        if klucz == "pl.salonola.app" else [])
    monkeypatch.setattr(am, "ios_opinie", lambda app_id, ile=50: {"liczba": 12, "srednia": 4.1, "niskie": 2,
                                                                 "tematy_skarg": {"logowanie": 2}, "cytaty": []})
    r = ut.stan(app)
    assert r["app_store"] == {"wersja": "1.0.0", "wydana": "2026-09-01", "ocena": 4.2, "ocen": 31}
    md = (app / "out" / "utrzymanie" / "STAN.md").read_text(encoding="utf-8")
    assert "najnowszy SDK 58.0.3" in md and "ocena 4.2 (31 ocen)" in md and "logowanie 2" in md and "obce treści" in md


def test_stan_gdy_npm_i_sklep_nie_odpowiadaja(app, monkeypatch):
    monkeypatch.setattr(ut, "sdk_z_npm", lambda: (_ for _ in ()).throw(ConnectionError("npm view expo: ETIMEDOUT")))
    monkeypatch.setattr(am, "ios_lookup", lambda klucz: (_ for _ in ()).throw(ml.Blokada("429")))
    r = ut.stan(app)
    assert "ETIMEDOUT" in r["sdk_npm"]["blad"] and r["app_store"] == {"blad": "429"}


def test_sdk_plan_podniesienia(app, monkeypatch):
    monkeypatch.setattr(ut, "sdk_z_npm", lambda: {"latest": "58.0.3", "next": "59.0.0-preview.1", "sdk": [56, 57, 58]})
    r = ut.sdk(app)
    assert r["do_podniesienia"] and r["teraz"] == "57.0.26"
    md = (app / r["plik"]).read_text(encoding="utf-8")
    assert "SDK 57 → 58" in md and "expo@^58.0.0" in md and "nie EAS Update" in md
    monkeypatch.setattr(ut, "sdk_z_npm", lambda: {"latest": "57.0.26", "next": None, "sdk": [56, 57]})
    assert not ut.sdk(app)["do_podniesienia"]


def test_sdk_z_npm_czyta_tagi(monkeypatch):
    tagi = {"latest": "57.0.26", "next": "58.0.2", "sdk-56": "56.0.9", "sdk-57": "57.0.26", "canary": "x"}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, json.dumps(tagi), ""))
    assert ut.sdk_z_npm() == {"latest": "57.0.26", "next": "58.0.2", "sdk": [56, 57]}


# ------------------------------------------------------------------ EAS Update (A2)

@pytest.fixture
def wywolania() -> list[list[str]]:
    return []


@pytest.fixture
def gotowa(app, monkeypatch, wywolania):
    """Aplikacja z buildami w sklepie (runtime fp-1), projektem EAS, tokenem i atrapą `eas update`."""
    dane = json.loads((app / "jarvo.app.json").read_text(encoding="utf-8"))
    dane["expo_project_id"] = "11111111-2222-3333-4444-555555555555"
    (app / "jarvo.app.json").write_text(json.dumps(dane, ensure_ascii=False), encoding="utf-8")
    _buildy(app)
    monkeypatch.setenv("EXPO_TOKEN", "robot-token")
    monkeypatch.setattr(ap, "sprawdz", lambda kat, siec=True: {"ok": True, "podsumowanie": "6/6 kontroli OK"})
    monkeypatch.setattr(ut, "runtime", lambda kat, platforma: "fp-1")

    def eas(args, kat, timeout=1800):
        wywolania.append(args)
        return subprocess.CompletedProcess(args, 0, "Published!\n" + json.dumps(
            [{"id": "u1", "group": "g-42", "platform": "ios"}, {"id": "u2", "group": "g-42", "platform": "android"}]), "")
    monkeypatch.setattr(wy, "_eas", eas)
    return app


ZGODA = "tak, wypuść poprawkę godzin otwarcia"
OPIS = "Poprawione godziny otwarcia na ekranie Kontakt"


def test_aktualizacja_publikuje_za_zgoda(gotowa, wywolania):
    r = ut.aktualizacja(gotowa, OPIS, ZGODA)
    assert r["grupa"] == "g-42" and r["kanal"] == "production"
    assert wywolania == [["update", "--channel", "production", "--message", OPIS, "--non-interactive", "--json"]]
    zgody = json.loads((gotowa / "out" / "wydanie" / "zgody.json").read_text(encoding="utf-8"))["zgody"]
    assert zgody[-1]["krok"] == "aktualizacja" and zgody[-1]["zgoda"] == ZGODA and zgody[-1]["wiadomosc"] == OPIS


def test_aktualizacja_bramki(gotowa, wywolania, monkeypatch):
    with pytest.raises(wy.Blad, match="opis zmiany"):
        ut.aktualizacja(gotowa, "poprawki", ZGODA)
    with pytest.raises(wy.Blad, match="słowa zgody"):
        ut.aktualizacja(gotowa, OPIS, "ok")
    monkeypatch.setattr(ut, "runtime", lambda kat, platforma: "fp-2" if platforma == "ios" else "fp-1")
    with pytest.raises(wy.Blad, match=r"IOS: odcisk kodu natywnego fp-2 ≠ build w sklepie fp-1") as e:
        ut.aktualizacja(gotowa, OPIS, ZGODA)
    assert "ANDROID" not in str(e.value) and "nowa wersja przez `wydanie`" in str(e.value)
    assert wywolania == [] and not (gotowa / "out" / "wydanie" / "zgody.json").exists()   # bez publikacji i bez wpisu


def test_aktualizacja_bez_buildu_tokenu_i_projektu(app, monkeypatch):
    monkeypatch.delenv("EXPO_TOKEN", raising=False)
    monkeypatch.setattr(ap, "sprawdz", lambda kat, siec=True: {"ok": False, "podsumowanie": "5/6 kontroli OK; nie przeszły: TYPY"})
    (app / "src" / "lib" / "nowe.ts").write_text("// JARVO-TODO: dokończyć\n", encoding="utf-8")
    with pytest.raises(wy.Blad) as e:
        ut.aktualizacja(app, OPIS, ZGODA)
    for brak in ("nie przeszły: TYPY", "JARVO-TODO", "EXPO_TOKEN", "expo_project_id", "brak buildu sklepowego"):
        assert brak in str(e.value)


def test_main_kody(gotowa, monkeypatch, tmp_path):
    assert ut.main(["kalendarz", str(gotowa)]) == 0
    assert ut.main(["stan", str(gotowa), "--bez-sieci"]) == 0
    assert ut.main(["aktualizacja", str(gotowa), "--wiadomosc", "fix", "--zgoda", ZGODA]) == 1
    assert ut.main(["aktualizacja", str(gotowa), "--wiadomosc", OPIS, "--zgoda", ZGODA]) == 0
    assert ut.main(["kalendarz", str(tmp_path / "nic")]) == 2
    monkeypatch.setattr(ut, "sdk_z_npm", lambda: (_ for _ in ()).throw(ConnectionError("npm offline")))
    assert ut.main(["sdk", str(gotowa)]) == 1


# ------------------------------------------------------------------ paczki npm przed instalacją

import paczki as pq  # noqa: E402

REJESTR = {
    "zustand": {"istnieje": True, "pobrania": 9_000_000, "wersja": "5.0.0", "natywna": False, "skrypty": []},
    "react-native-qrcode-svg": {"istnieje": True, "pobrania": 300_000, "wersja": "6.3.26", "natywna": True, "skrypty": []},
    "react-native-webview": {"istnieje": True, "pobrania": 1_500_000, "natywna": True, "skrypty": []},
    "core-js": {"istnieje": True, "pobrania": 80_000_000, "natywna": False, "skrypty": ["postinstall"]},
    "rn-super-utils": {"istnieje": True, "pobrania": 40, "utworzony": "2026-09-20T10:00:00Z", "natywna": False, "skrypty": []},
    "rn-stary-helper": {"istnieje": True, "pobrania": 2_500, "utworzony": "2019-01-01T00:00:00Z", "natywna": False,
                        "skrypty": ["postinstall"]},
    "left-pad": {"istnieje": True, "pobrania": 2_000_000, "natywna": False, "skrypty": [], "przestarzala": "use padStart()"},
    "zmyslona-paczka-ai": {"istnieje": False},
    "rejestr-milczy": {"istnieje": None, "blad": "timeout"},
}


@pytest.fixture
def rejestr(monkeypatch):
    pytane = []
    monkeypatch.setattr(pq, "rejestr", lambda n: pytane.append(n) or REJESTR[n])
    return pytane


@pytest.mark.parametrize("nazwa,wzor", [("expo-notifcations", "expo-notifications"), ("react-native-reanimatd", "react-native-reanimated"),
                                        ("react-native-async-storage", "@react-native-async-storage/async-storage"),
                                        ("@expo/vector-icon", "@expo/vector-icons"), ("raect", "react"), ("stripe", "@stripe/stripe-react-native")])
def test_paczki_literowki_i_podszycia_bez_sieci(nazwa, wzor, rejestr):
    w = pq.ocen(nazwa, siec=True)
    assert w["wynik"] == "blad" and wzor in w["powody"][0] and rejestr == []          # rozstrzygnięte przed rejestrem


def test_paczki_werdykty_z_rejestru(rejestr):
    d = dt.date(2026, 10, 2)
    w = {n: pq.ocen(n, siec=True, dzis=d) for n in REJESTR}
    assert w["zustand"]["wynik"] == "ok" and "biblioteka JS" in w["zustand"]["powody"][0]
    assert w["react-native-qrcode-svg"]["wynik"] == "ostrz" and "React Native Directory" in w["react-native-qrcode-svg"]["powody"][0]
    assert w["core-js"]["wynik"] == "ostrz" and "postinstall" in w["core-js"]["powody"][-1]
    assert w["rn-super-utils"]["wynik"] == "blad" and "nowa (12 dni)" in w["rn-super-utils"]["powody"][0]
    assert w["rn-stary-helper"]["wynik"] == "blad" and "skrypty przy instalacji (postinstall)" in w["rn-stary-helper"]["powody"][0]
    assert w["left-pad"]["wynik"] == "ostrz" and "przestarzała" in w["left-pad"]["powody"][-1]
    assert w["zmyslona-paczka-ai"]["wynik"] == "blad" and "zmyślona" in w["zmyslona-paczka-ai"]["powody"][0]
    assert w["rejestr-milczy"]["wynik"] == "?"                                          # nigdy „czysto” bez odpowiedzi


def test_paczki_zaufane_i_bez_sieci(rejestr, tmp_path):
    assert pq.ocen("expo-camera@~17.0.0")["wynik"] == "ok" and pq.ocen("@expo/vector-icons")["wynik"] == "ok"
    assert pq.ocen("zustand", siec=False)["wynik"] == "ostrz" and pq.ocen("rn-super-utils", siec=False)["wynik"] == "?"
    assert pq.ocen("Zła Nazwa!")["wynik"] == "blad" and rejestr == []
    kat = tmp_path / "app"
    (kat / "node_modules" / "expo").mkdir(parents=True)
    (kat / "node_modules" / "expo" / "bundledNativeModules.json").write_text(json.dumps({"expo-maps": "~0.12.0"}), encoding="utf-8")
    assert pq.ocen("expo-maps", kat)["wynik"] == "ok" and "lista Expo SDK" in pq.ocen("expo-maps", kat)["powody"][0]


def test_paczki_main_i_zasady_jarvo(app, rejestr, capsys):
    assert pq.main(["sprawdz", str(app), "zustand", "expo-camera"]) == 0
    assert pq.main(["sprawdz", str(app), "zustand", "expo-notifcations"]) == 1
    assert "nie instaluj: expo-notifcations" in capsys.readouterr().out
    pkg = json.loads((app / "package.json").read_text(encoding="utf-8"))
    pkg["dependencies"]["expo-notifcations"] = "1.0.0"
    (app / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    zasady = ap.zasady_jarvo(app)
    assert any(k["id"] == "J-PACZKA" and "expo-notifications" in k["opis"] for k in zasady)
    assert pq.main(["zaleznosci", str(app)]) == 1
    assert pq.main(["zaleznosci", str(app / "brak")]) == 2
