"""Twórca aplikacji, etap 4: lista kontrolna sklepów (44 punkty) na celowo zepsutych aplikacjach, odczyt buildów
(manifest AAB w protobuf aapt2, wyrównanie ELF do 16 KB, Info.plist i manifest prywatności z IPA), obrazy bez alfy
i szkic pakietu. Bez sieci (adresy podmienione), bez node_modules (konfiguracja z jarvo.app.json)."""

from __future__ import annotations

import io
import json
import plistlib
import shutil
import struct
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROFIL = ROOT / "profiles" / "jarvo-mobile"
sys.path.insert(0, str(PROFIL / "scripts"))

import mobile_lib as ml  # noqa: E402
import pakiet  # noqa: E402
import sklep_check as sk  # noqa: E402

POWOD = "Aparat służy do zeskanowania kodu QR z karty stałego klienta przy kasie w salonie."
POLITYKA = ("<html><body><h1>Polityka prywatności Salon Ola</h1><p>Administratorem danych jest Salon Ola sp. z o.o. "
            "Dane przetwarzamy w celu rezerwacji wizyt. " + "Masz prawo do dostępu do danych i ich usunięcia. " * 12
            + "</p></body></html>")


# ------------------------------------------------------------------ pliki testowe

def png(p: Path, w: int, h: int, alfa: bool = False) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    kanaly = 4 if alfa else 3
    surowe = b"".join(b"\x00" + b"\x80" * (w * kanaly) for _ in range(h))
    def blok(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + blok(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6 if alfa else 2, 0, 0, 0))
                  + blok(b"IDAT", zlib.compress(surowe, 9)) + blok(b"IEND", b""))
    return p


def _pb_varint(n: int) -> bytes:
    out = b""
    while True:
        b, n = n & 0x7F, n >> 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _pb(nr: int, v) -> bytes:
    if isinstance(v, int):
        return _pb_varint(nr << 3) + _pb_varint(v)
    v = v.encode() if isinstance(v, str) else v
    return _pb_varint(nr << 3 | 2) + _pb_varint(len(v)) + v


ANDROID_NS = "http://schemas.android.com/apk/res/android"


def _atr(nazwa: str, wartosc: str, liczba: int | None = None, prawda: bool | None = None) -> bytes:
    """XmlAttribute jak w aapt2: namespace_uri=1, name=2, value=3, resource_id=5, compiled_item=6 (Item.prim=7)."""
    b = _pb(1, ANDROID_NS) + _pb(2, nazwa) + _pb(3, wartosc) + _pb(5, 0x0101020C)
    if liczba is not None:
        b += _pb(6, _pb(7, _pb(6, liczba)))           # Primitive.int_decimal_value = 6
    if prawda is not None:
        b += _pb(6, _pb(7, _pb(8, int(prawda))))      # Primitive.boolean_value = 8
    return b


def _el(nazwa: str, atrybuty: list[bytes], dzieci: list[bytes] = ()) -> bytes:
    e = _pb(3, nazwa) + b"".join(_pb(4, a) for a in atrybuty) + b"".join(_pb(5, _pb(1, d)) for d in dzieci)
    return e


def manifest(target: int = 36, uprawnienia=("android.permission.INTERNET",), debug: bool = False) -> bytes:
    app = _el("application", [_atr("debuggable", "", prawda=True)] if debug else [])
    dzieci = [_el("uses-sdk", [_atr("minSdkVersion", "24", 24), _atr("targetSdkVersion", str(target), target)])]
    dzieci += [_el("uses-permission", [_atr("name", u)]) for u in uprawnienia] + [app]
    root = _pb(1, _pb(1, "android") + _pb(2, ANDROID_NS)) + _el("manifest", [
        _pb(2, "package") + _pb(3, "pl.salonola.app"), _atr("versionCode", "7", 7)], dzieci)
    return _pb(1, root)


def elf(align: int, bity: int = 64) -> bytes:
    if bity == 64:
        nagl = b"\x7fELF\x02\x01\x01" + b"\x00" * 9 + struct.pack("<HHIQQQIHHHHHH", 3, 183, 1, 0, 64, 0, 0, 64, 56, 1, 64, 0, 0)
        ph = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, 0x1000, 0x1000, align)
    else:
        nagl = b"\x7fELF\x01\x01\x01" + b"\x00" * 9 + struct.pack("<HHIIIIIHHHHHH", 3, 40, 1, 0, 52, 0, 0, 52, 32, 1, 40, 0, 0)
        ph = struct.pack("<IIIIIIII", 1, 0, 0, 0, 0x1000, 0x1000, 5, align)
    return nagl + ph


def aab(p: Path, **kw) -> Path:
    align = kw.pop("align", 0x4000)
    js = kw.pop("js", b"var a=1;")
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("base/manifest/AndroidManifest.xml", manifest(**kw))
        z.writestr("base/lib/arm64-v8a/libapp.so", elf(align))
        z.writestr("base/lib/armeabi-v7a/libapp.so", elf(0x1000, 32))     # 32-bit: 16 KB nie obowiązuje
        z.writestr("base/assets/index.android.bundle", js)
    return p


def ipa(p: Path, xcode: str = "2600", ats: bool = False, prywatnosc: bool = True) -> Path:
    plist = {"CFBundleIdentifier": "pl.salonola.app", "DTXcode": xcode, "MinimumOSVersion": "16.4",
             "ITSAppUsesNonExemptEncryption": False, "NSCameraUsageDescription": POWOD}
    if ats:
        plist["NSAppTransportSecurity"] = {"NSAllowsArbitraryLoads": True}
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("Payload/SalonOla.app/Info.plist", plistlib.dumps(plist, fmt=plistlib.FMT_BINARY))
        if prywatnosc:
            z.writestr("Payload/SalonOla.app/PrivacyInfo.xcprivacy", plistlib.dumps({"NSPrivacyAccessedAPITypes": [
                {"NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryUserDefaults",
                 "NSPrivacyAccessedAPITypeReasons": ["CA92.1"]}]}))
        z.writestr("Payload/SalonOla.app/Frameworks/ExpoModulesCore.framework/PrivacyInfo.xcprivacy", plistlib.dumps({}))
        z.writestr("Payload/SalonOla.app/main.jsbundle", b"var api='https://api.salonola.pl';")
    return p


# ------------------------------------------------------------------ aplikacja wzorcowa

APP = {
    "nazwa": "Salon Ola", "slug": "salon-ola", "scheme": "salonola", "wersja": "1.0.0",
    "bundle_ios": "pl.salonola.app", "pakiet_android": "pl.salonola.app", "wlasciciel_expo": "", "expo_project_id": "",
    "tablet": False, "opis": "Rezerwuj wizyty i zbieraj pieczątki za każdą usługę.",
    "firma": {"nazwa": "Salon Ola sp. z o.o.", "adres": "ul. Długa 1, 00-001 Warszawa", "email": "kontakt@salonola.pl",
              "telefon": "+48 600 000 000", "strona": "https://salonola.pl",
              "prywatnosc_url": "https://salonola.pl/polityka-prywatnosci", "usuwanie_konta_url": "https://salonola.pl/usun-konto"},
    "funkcje": {"konta": True, "tresci_uzytkownikow": False, "ai": False},
    "kolory": {"glowny": "#C2185B", "tlo_ikony": "#C2185B"},
    "uprawnienia_ios": {"NSCameraUsageDescription": POWOD},
    "wtyczki": [["expo-camera", {"cameraPermission": POWOD, "recordAudioAndroid": False, "microphonePermission": False}]],
    "zablokowane_uprawnienia_android": ["android.permission.RECORD_AUDIO"],
}
NOTATKI = """This app is published by Salon Ola sp. z o.o. for its own customers in Poland. The interface is in Polish.

Main features:
- Booking a visit: choose a service, a stylist and a time slot on the Home tab.
- Loyalty card: the customer shows a QR code at the till and collects stamps.

How to test:
1. Open the app. The home screen shows the services and opening hours without an account.
2. Tap a service, pick any stylist and a free time slot, then confirm the booking.
3. Sign in with the demo account from the App Review Information fields (no SMS code, no 2FA).
4. Account deletion: More (Więcej) → Delete account (Usuń konto).
"""
ADRESY = {"https://salonola.pl": (200, "<p>Kontakt: kontakt@salonola.pl, tel. +48 600 000 000</p>"),
          "https://salonola.pl/polityka-prywatnosci": (200, POLITYKA),
          "https://salonola.pl/usun-konto": (200, "<h1>Jak usunąć konto</h1><p>Usuń konto w aplikacji: Więcej → Usuń konto.</p>")}


@pytest.fixture
def app(tmp_path, monkeypatch):
    kat = tmp_path / "salon" / "app"
    shutil.copytree(PROFIL / "templates" / "expo-jarvo", kat)
    (kat / "jarvo.app.json").write_text(json.dumps(APP, ensure_ascii=False), encoding="utf-8")
    (kat / "package.json").write_text(json.dumps({"dependencies": {"expo": "~57.0.26", "expo-camera": "~57.0.0",
                                                                   "react-native-webview": "13.0.0"}}), encoding="utf-8")
    for rel in ("src/lib/konto.ts", "src/app/(tabs)/index.tsx"):           # aplikacja „gotowa”: bez znaczników z szablonu
        p = kat / rel
        p.write_text("\n".join(l for l in p.read_text(encoding="utf-8").splitlines() if "JARVO-TODO" not in l
                               and "Tu pojawią się" not in l), encoding="utf-8")
    (kat / "src" / "lib" / "skaner.ts").write_text("import { CameraView } from 'expo-camera';\nexport const S = CameraView;\n",
                                                  encoding="utf-8")
    png(kat / "assets" / "icon.png", 1024, 1024)
    for n in ("android-icon-foreground.png", "android-icon-background.png", "android-icon-monochrome.png", "splash-icon.png"):
        png(kat / "assets" / n, 64, 64, alfa=True)
    (kat / "store.config.json").write_text(json.dumps({"configVersion": 0, "apple": {
        "info": {"pl-PL": {"title": "Salon Ola", "subtitle": "Wizyty i pieczątki w salonie",
                           "description": "Umów wizytę w salonie bez dzwonienia i zbieraj pieczątki za każdą usługę.",
                           "keywords": ["fryzjer", "kosmetyczka", "wizyta", "rezerwacja", "manicure"],
                           "releaseNotes": "Pierwsza wersja aplikacji.", "supportUrl": "https://salonola.pl",
                           "privacyPolicyUrl": "https://salonola.pl/polityka-prywatnosci"}},
        "review": {"demoUsername": "review@salonola.pl", "demoPassword": "Demo-2026", "demoRequired": True, "notes": NOTATKI}}},
        ensure_ascii=False), encoding="utf-8")
    g = kat / "out" / "sklep" / "google" / "pl-PL"
    for n, v in (("title.txt", "Salon Ola"), ("short_description.txt", "Umów wizytę i zbieraj pieczątki za usługi."),
                 ("full_description.txt", "Umów wizytę w salonie bez dzwonienia i zbieraj pieczątki.")):
        ml.zapisz(g / n, v)
    png(g / "images" / "icon.png", 512, 512)
    png(g / "images" / "featureGraphic.png", 1024, 500)
    for i in (1, 2, 3):
        png(kat / "out" / "sklep" / "apple" / "pl-PL" / "ios-6.9" / f"0{i}.png", 1320, 2868)
        png(g / "images" / "phoneScreenshots" / f"0{i}.png", 1080, 1920)
    ml.zapisz(kat / "out" / "sklep" / "zrzuty.json", json.dumps({"zrodlo": "android", "kadry": [
        {"trasa": "/"}, {"trasa": "/rezerwacja"}, {"trasa": "/karta"}]}))
    ml.zapisz(kat / "out" / "jakosc" / "sprawdz.json", json.dumps({"kontrole": [
        {"id": "WERSJE", "ok": True, "opis": ""}, {"id": "DOCTOR", "ok": True, "opis": ""}]}))
    monkeypatch.setattr(sk, "_http", lambda url, ctx: ADRESY.get(url, (404, "", url)) + (url,) if url in ADRESY
                        else (404, "", url))
    monkeypatch.setattr(sk, "_ocr", lambda p: "Salon Ola Umów wizytę")
    monkeypatch.setattr(ml, "json_z", lambda url, **kw: {"results": []})
    monkeypatch.setenv("JARVO_MOBILE_PRACE", str(tmp_path / "brak"))
    return kat


def _http_ok(monkeypatch, adresy=None):
    adresy = adresy or ADRESY
    monkeypatch.setattr(sk, "_http", lambda url, ctx: (*adresy[url], url) if url in adresy else (404, "", url))


def kontekst(kat: Path, **kw) -> sk.Kontekst:
    return sk.Kontekst(kat, builds=kw.pop("builds", {}), profil=kw.pop("profil", {"platnosci": ["uslugi"]}),
                       cfg=kw.pop("cfg", None) or sk.konfiguracja(kat), **kw)


def wyniki(kat: Path, **kw) -> dict[int, dict]:
    return {w["nr"]: w for w in sk.sprawdz(kontekst(kat, **kw))["wyniki"]}


# ------------------------------------------------------------------ testy

def test_lista_ma_44_punkty_i_tryby():
    assert len(sk.PUNKTY) == 44
    tryby = {t for _, _, t, _, _ in sk.PUNKTY}
    assert tryby == {"auto", "pół", "ręcznie"}
    assert set(sk.SPRAWDZENIA) | set(sk.RECZNE_PODPOWIEDZI) == set(range(1, 45))


def test_wzorcowa_aplikacja_bez_bledow_auto(app, monkeypatch):
    _http_ok(monkeypatch)
    w = wyniki(app)
    bledy = {n: x["dowod"] for n, x in w.items() if x["stan"] == "blad"}
    assert not bledy, bledy
    assert w[1]["stan"] == "recznie" and w[33]["stan"] == "recznie"
    assert w[7]["stan"] == "?" and w[16]["stan"] == "?"                       # bez buildów: niezmierzone, nie zaliczone


@pytest.mark.parametrize("zepsuj, nr, fragment", [
    (lambda a: a.update(bundle_ios="com.example.app"), 4, "przykładowy"),
    (lambda a: a.update(pakiet_android="pl.salon-ola.app"), 4, "odwrotną domeną"),
    (lambda a: a.update(wersja="1.0"), 5, "X.Y.Z"),
    (lambda a: a["uprawnienia_ios"].update(NSCameraUsageDescription="Aplikacja potrzebuje dostępu do aparatu."), 12, "ogólnik"),
    (lambda a: a["uprawnienia_ios"].update(NSCameraUsageDescription="The camera is used to scan the loyalty QR code at the till."),
     12, "nie po polsku"),
    (lambda a: a["uprawnienia_ios"].update(NSContactsUsageDescription="Kontakty służą do zaproszenia znajomej do salonu w aplikacji."),
     13, "NSContactsUsageDescription bez modułu"),
    (lambda a: a["uprawnienia_ios"].pop("NSCameraUsageDescription"), 11, "NSCameraUsageDescription"),
    (lambda a: a.update(nazwa="Moja Firma"), 26, "szablonu"),
    (lambda a: a["firma"].update(usuwanie_konta_url=""), 22, "usuwanie_konta_url"),
    (lambda a: a["funkcje"].update(tresci_uzytkownikow=True), 31, "zgłaszanie"),
])
def test_zepsuta_konfiguracja(app, monkeypatch, zepsuj, nr, fragment):
    _http_ok(monkeypatch)
    dane = json.loads((app / "jarvo.app.json").read_text(encoding="utf-8"))
    zepsuj(dane)
    (app / "jarvo.app.json").write_text(json.dumps(dane, ensure_ascii=False), encoding="utf-8")
    w = wyniki(app)[nr]
    assert w["stan"] == "blad" and fragment in w["dowod"], w


def test_ogolnik_wtyczki_z_introspekcji(app, monkeypatch):
    """Ten błąd znalazła introspekcja prawdziwej aplikacji: wtyczka aparatu dopisuje angielski opis mikrofonu."""
    _http_ok(monkeypatch)
    cfg = sk.konfiguracja(app)
    cfg["introspect"]["ios"]["infoPlist"]["NSMicrophoneUsageDescription"] = "Allow $(PRODUCT_NAME) to access your microphone"
    w = wyniki(app, cfg=cfg)
    assert w[12]["stan"] == "blad" and "NSMicrophoneUsageDescription" in w[12]["dowod"]
    assert w[13]["stan"] == "blad" and "NSMicrophoneUsageDescription" in w[13]["dowod"]


def test_kod_z_adresem_lokalnym_i_tekstem_zastepczym(app, monkeypatch):
    _http_ok(monkeypatch)
    (app / "src" / "lib" / "api.ts").write_text("export const API = 'http://192.168.1.20:3000';\n// TODO: lorem ipsum\n",
                                                encoding="utf-8")
    w = wyniki(app)
    assert w[8]["stan"] == "blad" and "192.168.1.20" in w[8]["dowod"]
    assert w[26]["stan"] == "blad" and "lorem ipsum" in w[26]["dowod"]


def test_szablon_ma_znaczniki_blokujace(tmp_path, monkeypatch):
    """Świeży szablon nie przejdzie: ekran startowy i usuwanie konta mają JARVO-TODO, dane firmy są przykładowe."""
    kat = tmp_path / "app"
    shutil.copytree(PROFIL / "templates" / "expo-jarvo", kat)
    monkeypatch.setattr(sk, "_http", lambda url, ctx: (None, "", ""))
    w = wyniki(kat)
    assert w[26]["stan"] == "blad" and "JARVO-TODO" in w[26]["dowod"] and "szablonu" in w[26]["dowod"]
    assert w[4]["stan"] == "blad" and "pl.mojafirma.app" in w[4]["dowod"]


def test_metadane_limity_slowa_kluczowe_zakazane(app, monkeypatch):
    _http_ok(monkeypatch)
    s = json.loads((app / "store.config.json").read_text(encoding="utf-8"))
    pl = s["apple"]["info"]["pl-PL"]
    pl["subtitle"] = "Najlepszy salon w Warszawie – rabat 20%"           # 39 znaków, superlatyw, rabat
    pl["keywords"] = ["źdźbło", "żółć", "łąka", "gęślą", "jaźń", "Booksy", "Salon", "fryzjerka", "manicure hybrydowy",
                      "pedicure", "koloryzacja", "SO"]
    pl["description"] = "Działa też na Androidzie. NOWOŚĆ! 💅💅💅💅"
    (app / "store.config.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    w = wyniki(app)
    assert w[39]["stan"] == "blad" and "subtitle" in w[39]["dowod"]
    d40 = w[40]["dowod"]
    assert w[40]["stan"] == "blad" and "bajtów > 100" in d40 and "Booksy" in d40 and "Salon" in d40 and "SO" in d40
    d41 = w[41]["dowod"]
    assert w[41]["stan"] == "blad" and "Najlepszy" in d41 and "rabat" in d41 and "Androidzie" in d41 and "emoji" in d41


def test_klucze_w_bajtach_nie_znakach():
    assert len(",".join(["żółć"] * 20).encode()) > 100 >= len(",".join(["żółć"] * 20))


def test_grafiki_i_zrzuty_z_alfa_i_zle_wymiary(app, monkeypatch):
    _http_ok(monkeypatch)
    png(app / "assets" / "icon.png", 1024, 1024, alfa=True)
    sklep = app / "out" / "sklep"
    png(sklep / "google" / "pl-PL" / "images" / "featureGraphic.png", 1024, 512)
    png(sklep / "apple" / "pl-PL" / "ios-6.9" / "02.png", 1284, 2778)          # 6,5″ w zestawie 6,9″
    png(sklep / "apple" / "pl-PL" / "ios-6.9" / "03.png", 1320, 2868, alfa=True)
    for p in (sklep / "google" / "pl-PL" / "images" / "phoneScreenshots").glob("0[23].png"):
        p.unlink()
    w = wyniki(app)
    assert w[34]["stan"] == "blad" and "alfy" in w[34]["dowod"]
    assert w[35]["stan"] == "blad" and "1024×512" in w[35]["dowod"]
    d = w[36]["dowod"]
    assert w[36]["stan"] == "blad" and "02.png: 1284×2778" in d and "03.png: 1320×2868, alfa" in d and "1 zrzutów telefonu" in d


def test_zrzuty_ios_z_obca_platforma_i_logowaniem(app, monkeypatch):
    _http_ok(monkeypatch)
    monkeypatch.setattr(sk, "_ocr", lambda p: "Pobierz z Google Play")
    ml.zapisz(app / "out" / "sklep" / "zrzuty.json", json.dumps({"zrodlo": "web", "kadry": [{"trasa": "/logowanie"}, {"trasa": "/"}]}))
    w = wyniki(app)[37]
    assert w["stan"] == "blad" and "Google Play" in w["dowod"] and "logowanie" in w["dowod"]


def test_strony_firmy(app, monkeypatch):
    zle = {"https://salonola.pl": (200, "<p>Zapraszamy!</p>"),
           "https://salonola.pl/polityka-prywatnosci": (200, "<h1>Privacy policy</h1><p>We respect your privacy.</p>"),
           "https://salonola.pl/usun-konto": (404, "")}
    _http_ok(monkeypatch, zle)
    w = wyniki(app)
    assert w[20]["stan"] == "blad" and "nie wymienia firmy" in w[20]["dowod"] and "nie jest po polsku" in w[20]["dowod"]
    assert w[21]["stan"] == "blad" and "brak e-maila i telefonu" in w[21]["dowod"]
    assert w[22]["stan"] == "blad" and "HTTP 404" in w[22]["dowod"]
    assert w[27]["stan"] == "blad" and "usun-konto: HTTP 404" in w[27]["dowod"]


def test_adresy_lokalne_i_bez_https(app, monkeypatch):
    _http_ok(monkeypatch)
    dane = json.loads((app / "jarvo.app.json").read_text(encoding="utf-8"))
    dane["firma"].update(prywatnosc_url="http://127.0.0.1:9120/abc/polityka.html", strona="http://salonola.pl",
                         usuwanie_konta_url="https://salon.ngrok-free.app/usun")
    (app / "jarvo.app.json").write_text(json.dumps(dane, ensure_ascii=False), encoding="utf-8")
    s = json.loads((app / "store.config.json").read_text(encoding="utf-8"))
    s["apple"]["info"]["pl-PL"].pop("supportUrl")
    s["apple"]["info"]["pl-PL"].pop("privacyPolicyUrl")
    (app / "store.config.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    w = wyniki(app)
    assert w[20]["stan"] == "blad" and "nie HTTPS" in w[20]["dowod"]
    assert w[21]["stan"] == "blad" and "nie HTTPS" in w[21]["dowod"]
    assert w[22]["stan"] == "blad" and "lokalny albo testowy" in w[22]["dowod"]


def test_konto_demo_i_notatki(app, monkeypatch):
    _http_ok(monkeypatch)
    s = json.loads((app / "store.config.json").read_text(encoding="utf-8"))
    s["apple"]["review"].update(demoPassword="", notes="Zaloguj się kontem demo, potem wpisz kod SMS.")
    (app / "store.config.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    monkeypatch.delenv("JARVO_DEMO_HASLO", raising=False)
    w = wyniki(app)
    assert w[25]["stan"] == "blad" and "hasła demo" in w[25]["dowod"] and "SMS" in w[25]["dowod"]
    assert w[44]["stan"] == "blad" and "nie po angielsku" in w[44]["dowod"]


def test_platnosci_wedlug_profilu(app, monkeypatch):
    _http_ok(monkeypatch)
    pkg = json.loads((app / "package.json").read_text(encoding="utf-8"))
    pkg["dependencies"]["@stripe/stripe-react-native"] = "0.50.0"
    (app / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    assert wyniki(app, profil={"platnosci": ["cyfrowe"]})[30]["stan"] == "blad"
    assert wyniki(app, profil={"platnosci": ["fizyczne"]})[30]["stan"] == "ok"
    pkg["dependencies"]["expo-iap"] = "3.0.0"
    (app / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    assert "3.1.3(e)" in wyniki(app, profil={"platnosci": ["uslugi"]})[30]["dowod"]


def test_ai_bez_zgody_i_sledzenie_bez_att(app, monkeypatch):
    _http_ok(monkeypatch)
    (app / "src" / "lib" / "czat.ts").write_text("fetch('https://api.openai.com/v1/responses')\n", encoding="utf-8")
    pkg = json.loads((app / "package.json").read_text(encoding="utf-8"))
    pkg["dependencies"]["react-native-google-mobile-ads"] = "15.0.0"
    (app / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    w = wyniki(app)
    assert w[18]["stan"] == "blad" and "ekran zgody" in w[18]["dowod"]
    assert w[17]["stan"] == "blad" and "ATT" in w[17]["dowod"]
    szkic = json.loads((app / "out" / "sklep" / "prywatnosc-szkic.json").read_text(encoding="utf-8"))
    assert "identyfikator reklamowy" in szkic["dane"] and szkic["sledzenie"] == ["react-native-google-mobile-ads"]


def test_prosba_o_uprawnienie_na_starcie_i_logowanie_na_start(app, monkeypatch):
    _http_ok(monkeypatch)
    p = app / "src" / "app" / "(tabs)" / "index.tsx"
    p.write_text(p.read_text(encoding="utf-8") + "\nCamera.requestCameraPermissionsAsync();\n"
                 "const X = () => <Redirect href=\"/logowanie\" />;\n", encoding="utf-8")
    w = wyniki(app)
    assert w[19]["stan"] == "blad" and "requestCameraPermissionsAsync" in w[19]["dowod"]
    assert w[24]["stan"] == "blad" and "logowanie" in w[24]["dowod"]


def test_okno_na_strone(app, monkeypatch):
    _http_ok(monkeypatch)
    for n in ("a", "b", "c", "d"):
        (app / "src" / "app" / f"{n}.tsx").write_text("import { WebView } from 'react-native-webview';\n", encoding="utf-8")
    w = wyniki(app)[28]
    assert w["stan"] == "blad" and "z WebView 4" in w["dowod"]


def test_podobna_aplikacja_floty(app, monkeypatch, tmp_path):
    _http_ok(monkeypatch)
    prace = tmp_path / "prace"
    kopia = prace / "inna" / "app"
    shutil.copytree(app, kopia)
    monkeypatch.setenv("JARVO_MOBILE_PRACE", str(prace))
    w = wyniki(app)[29]
    assert w["stan"] == "blad" and "inna" in w["dowod"]


def test_aab_dobry_i_zly(app, monkeypatch, tmp_path):
    _http_ok(monkeypatch)
    dobry = sk.czytaj_build(aab(tmp_path / "ok.aab"))
    assert dobry.manifest["atrybuty"]["package"] == "pl.salonola.app"
    assert sk._znajdz(dobry.manifest, "uses-sdk")[0]["atrybuty"]["targetSdkVersion"] == "36"
    w = wyniki(app, builds={"aab": dobry})
    assert w[6]["stan"] in ("ok", "?") and w[7]["stan"] == "ok" and w[8]["stan"] == "ok"
    zly = sk.czytaj_build(aab(tmp_path / "zly.aab", target=34, align=0x1000, debug=True,
                              uprawnienia=("android.permission.INTERNET", "android.permission.READ_CONTACTS",
                                           "android.permission.QUERY_ALL_PACKAGES"),
                              js=b"fetch('https://abc123.ngrok-free.app/api')"))
    w = wyniki(app, builds={"aab": zly})
    assert w[6]["stan"] == "blad" and "34" in w[6]["dowod"]
    assert w[7]["stan"] == "blad" and "arm64-v8a/libapp.so (p_align 4096)" in w[7]["dowod"] and "armeabi" not in w[7]["dowod"]
    assert w[8]["stan"] == "blad" and "debuggable" in w[8]["dowod"] and "ngrok" in w[8]["dowod"]
    assert w[13]["stan"] == "blad" and "READ_CONTACTS" in w[13]["dowod"] and "QUERY_ALL_PACKAGES" in w[13]["dowod"]
    assert w[14]["stan"] == "?" and "kontakty" in w[14]["dowod"]


def test_elf_32_i_64_bity():
    assert sk.elf_wyrownanie(elf(0x4000)) == (64, 0x4000)
    assert sk.elf_wyrownanie(elf(0x1000, 32)) == (32, 0x1000)
    assert sk.elf_wyrownanie(b"nie elf") is None


def test_ipa(app, monkeypatch, tmp_path):
    _http_ok(monkeypatch)
    w = wyniki(app, builds={"ipa": sk.czytaj_build(ipa(tmp_path / "ok.ipa"))})
    assert w[6]["stan"] == "?" and "Xcode 2600" in w[6]["dowod"]               # sam IPA nie mówi nic o API Androida
    assert w[16]["stan"] == "ok" and "manifesty bibliotek: 1" in w[16]["dowod"] and w[9]["stan"] == "ok"
    w = wyniki(app, builds={"ipa": sk.czytaj_build(ipa(tmp_path / "ok.ipa")), "aab": sk.czytaj_build(aab(tmp_path / "ok.aab"))})
    assert w[6]["stan"] == "ok" and "AAB targetSdkVersion 36" in w[6]["dowod"]
    w = wyniki(app, builds={"ipa": sk.czytaj_build(ipa(tmp_path / "zle.ipa", xcode="1640", ats=True, prywatnosc=False))})
    assert w[6]["stan"] == "blad" and w[8]["stan"] == "blad" and "NSAllowsArbitraryLoads" in w[8]["dowod"]
    assert w[16]["stan"] == "blad"


def test_potwierdzenia_i_raport(app, monkeypatch):
    _http_ok(monkeypatch)
    with pytest.raises(SystemExit):
        sk.potwierdz(app, 4, "właściciel", "punkt automatyczny")
    sk.potwierdz(app, 1, "właściciel", "konto organizacji Salon Ola, agent w zespole jako Developer")
    w = wyniki(app)
    assert w[1]["stan"] == "ok" and "potwierdził właściciel" in w[1]["dowod"]
    r = sk.sprawdz(kontekst(app))
    md = sk.raport_md(r)
    assert md.count("| 1 |") == 1 and "## G. Metadane" in md and r["liczby"]["blad"] == 0 and r["gotowe_do_wyslania"] is False


def test_main_kody_wyjscia(app, monkeypatch, tmp_path):
    _http_ok(monkeypatch)
    assert sk.main([str(app), "--json"]) == 0
    assert (app / "out" / "sklep" / "check.json").exists() and (app / "out" / "sklep" / "CHECK.md").exists()
    assert sk.main([str(tmp_path / "nic")]) == 2
    dane = json.loads((app / "jarvo.app.json").read_text(encoding="utf-8"))
    dane["bundle_ios"] = "com.example.app"
    (app / "jarvo.app.json").write_text(json.dumps(dane), encoding="utf-8")
    assert sk.main([str(app)]) == 1


# ------------------------------------------------------------------ pakiet

def test_obraz_png_jpeg(tmp_path):
    assert ml.obraz(png(tmp_path / "a.png", 10, 20)) | {"bajty": 0} == {"typ": "png", "szer": 10, "wys": 20, "alfa": False, "bajty": 0}
    assert ml.obraz(png(tmp_path / "b.png", 3, 3, alfa=True))["alfa"]
    jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xc0\x00\x11\x08\x01\xf4\x04\x00\x03"
    (tmp_path / "c.jpg").write_bytes(jpg + b"\x00" * 20)
    assert ml.obraz(tmp_path / "c.jpg") | {"bajty": 0} == {"typ": "jpeg", "szer": 1024, "wys": 500, "alfa": False, "bajty": 0}


def test_szkic_pakietu_i_blokada_todo(app, monkeypatch):
    _http_ok(monkeypatch)
    (app / "store.config.json").unlink()
    shutil.rmtree(app / "out" / "sklep" / "google" / "pl-PL", ignore_errors=True)
    r = pakiet.szkic(app)
    assert "store.config.json" in r["pliki"] and r["do_uzupelnienia"] >= 5
    s = json.loads((app / "store.config.json").read_text(encoding="utf-8"))
    assert s["apple"]["info"]["pl-PL"]["privacyPolicyUrl"] == APP["firma"]["prywatnosc_url"]
    assert s["apple"]["review"]["demoRequired"] is True and "Delete account" in s["apple"]["review"]["notes"]
    w = wyniki(app)
    assert w[26]["stan"] == "blad" and "apple.subtitle: JARVO-TODO" in w[26]["dowod"]
    s["apple"]["info"]["pl-PL"]["subtitle"] = "Moje słowa"
    (app / "store.config.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    pakiet.szkic(app)                                                         # bez --nadpisz: własne teksty zostają
    assert json.loads((app / "store.config.json").read_text(encoding="utf-8"))["apple"]["info"]["pl-PL"]["subtitle"] == "Moje słowa"
    sc = (app / "out" / "sklep" / "zrzuty.yaml").read_text(encoding="utf-8")
    assert "trasa: /\n" in sc and "/prywatnosc" not in sc and "/usun-konto" not in sc


def test_trasy_i_typografia(app):
    assert pakiet.trasy_aplikacji(app)[0] == "/" and "/wiecej" in pakiet.trasy_aplikacji(app)
    assert pakiet.bez_sierotek("Wszystko o salonie w jednym miejscu") == "Wszystko o salonie w jednym miejscu"
    h = pakiet.html_kadru("ios-6.9", png(app / "x.png", 1320, 2868), "Wizyta w 30 sekund", "", {"glowny": "#C2185B",
                          "naGlownym": "#FFFFFF"}, pasek=True)
    assert "width:1320px;height:2868px" in h and "Wizyta w 30 sekund" in h and "9:41" in h


def test_galeria_pakietu(app, monkeypatch):
    _http_ok(monkeypatch)
    sk.main([str(app)])                                                       # odświeża też galerię
    h = (app / "out" / "sklep" / "index.html").read_text(encoding="utf-8")
    assert 'src="apple/pl-PL/ios-6.9/01.png"' in h and 'src="google/pl-PL/images/featureGraphic.png"' in h
    assert "Lista kontrolna" in h and 'href="CHECK.md"' in h and "<script" not in h
