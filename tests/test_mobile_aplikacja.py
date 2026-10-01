"""Twórca aplikacji, etap 2: profil zgodności, konfiguracja aplikacji z szablonu JARVO, paleta WCAG, zasady JARVO,
podgląd (serwer zrzutów, link HQ) i Expo Go (parsowanie `eas update --json`). Bez sieci i bez node_modules."""

from __future__ import annotations

import json
import shutil
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-mobile" / "scripts"))

import aplikacja as ap  # noqa: E402
import zgodnosc as zg  # noqa: E402

SZABLON = ROOT / "profiles" / "jarvo-mobile" / "templates" / "expo-jarvo"
POWOD = "Aparat służy do zeskanowania kodu QR z karty stałego klienta przy kasie."
APLIKACJA = {"nazwa": "Salon Ola", "slug": "salon-ola", "bundle": "pl.salonola.app", "opis": "Rezerwacje.",
             "kolor_glowny": "#C2185B",
             "firma": {"nazwa": "Salon Ola sp. z o.o.", "email": "kontakt@salonola.pl", "strona": "https://salonola.pl",
                       "prywatnosc_url": "https://salonola.pl/prywatnosc", "usuwanie_konta_url": "https://salonola.pl/usun"}}


# ------------------------------------------------------------------ profil zgodności

def test_logowanie_google_dodaje_apple_i_usuwanie_konta():
    w = zg.ocen({"logowanie": ["google"], "uprawnienia": []})
    ids = {x["id"] for x in w["wymagania"]}
    assert {"sign-in-with-apple", "usuwanie-konta", "konto-demo"} <= ids
    assert "expo-apple-authentication" in w["konfiguracja"]["paczki"] and w["konfiguracja"]["funkcje"]["konta"]


def test_uprawnienie_bez_powodu_albo_ogolnikowe_to_blad():
    assert any("brak powodu" in b for b in zg.ocen({"uprawnienia": ["aparat"]})["bledy"])
    w = zg.ocen({"uprawnienia": ["aparat"], "powody": {"aparat": "Aplikacja potrzebuje dostępu do aparatu."}})
    assert any("ogólnikowy" in b for b in w["bledy"])
    w = zg.ocen({"uprawnienia": ["aparat", "powiadomienia"], "powody": {"aparat": POWOD}})
    assert not w["bledy"]
    kz = w["konfiguracja"]
    assert kz["uprawnienia_ios"] == {"NSCameraUsageDescription": POWOD}
    assert ["expo-camera", {"cameraPermission": POWOD, "recordAudioAndroid": False, "microphonePermission": False}] in kz["wtyczki"]
    assert "expo-notifications" in kz["wtyczki"]


def test_wtyczki_bez_angielskich_ogolnikow():
    """Wtyczki Expo dopisują „Allow $(PRODUCT_NAME) to access your microphone” dla kluczy, których nie ustawimy;
    profil ustawia każdy klucz obsługiwanej wtyczki: powód albo false (klucz znika z Info.plist)."""
    def wt(w):
        return {n: pr for n, pr in (x if isinstance(x, list) else [x, {}] for x in w["konfiguracja"]["wtyczki"])}
    w = wt(zg.ocen({"uprawnienia": ["aparat"], "powody": {"aparat": POWOD}}))
    assert w["expo-camera"] == {"cameraPermission": POWOD, "recordAudioAndroid": False, "microphonePermission": False}
    w = wt(zg.ocen({"uprawnienia": ["zdjecia"], "powody": {"zdjecia": POWOD}}))
    assert w["expo-image-picker"] == {"photosPermission": POWOD, "cameraPermission": False, "microphonePermission": False}
    w = wt(zg.ocen({"uprawnienia": ["zdjecia", "aparat", "mikrofon"],
                    "powody": {"zdjecia": POWOD, "aparat": POWOD + " A", "mikrofon": POWOD + " M"}}))
    assert w["expo-image-picker"]["cameraPermission"] == POWOD + " A" and w["expo-camera"]["microphonePermission"] == POWOD + " M"
    w = wt(zg.ocen({"uprawnienia": ["lokalizacja"], "powody": {"lokalizacja": POWOD}}))
    assert w["expo-location"] == {"locationWhenInUsePermission": POWOD, "locationAlwaysAndWhenInUsePermission": False,
                                  "locationAlwaysPermission": False, "motionUsagePermission": False}
    for kolejnosc in (["lokalizacja", "lokalizacja-w-tle"], ["lokalizacja-w-tle", "lokalizacja"]):
        o = zg.ocen({"uprawnienia": kolejnosc, "powody": {"lokalizacja": POWOD, "lokalizacja-w-tle": POWOD + " T"}})
        loc = wt(o)["expo-location"]
        assert loc["locationWhenInUsePermission"] == POWOD and loc["locationAlwaysAndWhenInUsePermission"] == POWOD + " T"
        assert loc["isIosBackgroundLocationEnabled"] is True
    o = zg.ocen({"uprawnienia": ["lokalizacja-w-tle"], "powody": {"lokalizacja-w-tle": POWOD}})
    assert wt(o)["expo-location"]["locationWhenInUsePermission"] == POWOD          # Apple wymaga obu kluczy
    assert o["konfiguracja"]["uprawnienia_ios"]["NSLocationWhenInUseUsageDescription"] == POWOD
    assert wt(zg.ocen({"uprawnienia": ["kalendarz"], "powody": {"kalendarz": POWOD}}))["expo-calendar"]["remindersPermission"] is False


def test_blokady_androida_odblokowane_tylko_przez_profil():
    zwykly = zg.ocen({})["konfiguracja"]["zablokowane_uprawnienia_android"]
    assert "android.permission.ACCESS_BACKGROUND_LOCATION" in zwykly and "com.google.android.gms.permission.AD_ID" in zwykly
    tlo = zg.ocen({"uprawnienia": ["lokalizacja-w-tle"],
                   "powody": {"lokalizacja-w-tle": "Lokalizacja w tle przypomina o wizycie, gdy jesteś blisko salonu."}})
    assert "android.permission.ACCESS_BACKGROUND_LOCATION" not in tlo["konfiguracja"]["zablokowane_uprawnienia_android"]
    assert any("lokalizacja w tle" in o for o in tlo["ostrzezenia"])


def test_platnosci_i_tresci():
    w = zg.ocen({"platnosci": ["cyfrowe", "uslugi"], "tresci_uzytkownikow": True, "ai": True, "konto_google": "osobiste"})
    ids = {x["id"] for x in w["wymagania"]}
    assert {"iap", "platnosci-zewnetrzne", "ugc", "ai", "test-zamkniety"} <= ids
    assert any("build" in o for o in w["ostrzezenia"])


def test_nieznane_wartosci():
    w = zg.ocen({"logowanie": ["myspace"], "uprawnienia": ["telepatia"], "branza": "kosmos"})
    assert len(w["bledy"]) == 3


def test_szablon_profilu_jest_poprawny():
    import yaml
    assert zg.ocen(yaml.safe_load(zg.SZABLON))["bledy"] == []


# ------------------------------------------------------------------ paleta i konfiguracja

@pytest.mark.parametrize("marka", ["#C2185B", "#FFD400", "#00A3E0", "#111111", "#FFFFFF", "#3DDC84"])
def test_paleta_spelnia_wcag_aa(marka):
    p = ap.paleta(marka)
    for m in ("jasny", "ciemny"):
        assert ap.kontrast(p[m]["glowny"], p[m]["tlo"]) >= 4.5
        assert ap.kontrast(p[m]["naGlownym"], p[m]["glowny"]) >= 4.5
        assert ap.kontrast(p[m]["tekst"], p[m]["tlo"]) >= 4.5 and ap.kontrast(p[m]["tekstDrugi"], p[m]["tlo"]) >= 4.5


def test_kontrast_wzorcowy():
    assert round(ap.kontrast("#000000", "#FFFFFF"), 1) == 21.0 and ap.kontrast("#777777", "#FFFFFF") < 4.5


def test_konfiguracja_walidacja():
    assert ap.sprawdz_konfiguracje(APLIKACJA, konta=True) == []
    zle = {**APLIKACJA, "bundle": "com.example.app", "slug": "Salon Ola", "kolor_glowny": "red",
           "firma": {**APLIKACJA["firma"], "usuwanie_konta_url": "", "strona": "http://salonola.pl"}}
    bledy = ap.sprawdz_konfiguracje(zle, konta=True)
    assert len(bledy) == 5 and any("usuwanie_konta_url" in b for b in bledy)


def test_inicjaly():
    assert ap.inicjaly("Salon Ola") == "SO" and ap.inicjaly("żabka") == "Ż" and ap.inicjaly("Moja Firma Krawiecka") == "MF"


@pytest.fixture
def aplikacja_tmp(tmp_path, monkeypatch):
    kat = tmp_path / "app"
    shutil.copytree(SZABLON, kat)
    monkeypatch.setattr(ap, "ikony", lambda *a, **k: None)          # ikony.cjs wymaga sharp (obraz floty)
    return kat


def test_ustaw_bez_kont_usuwa_ekran_i_trase(aplikacja_tmp):
    w = ap.ustaw(aplikacja_tmp, {**APLIKACJA, "firma": {**APLIKACJA["firma"], "usuwanie_konta_url": ""}}, {})
    assert not (aplikacja_tmp / "src/app/usun-konto.tsx").exists()
    assert 'name="usun-konto"' not in (aplikacja_tmp / "src/app/_layout.tsx").read_text(encoding="utf-8")
    app = json.loads((aplikacja_tmp / "jarvo.app.json").read_text(encoding="utf-8"))
    assert app["bundle_ios"] == "pl.salonola.app" and app["scheme"] == "salonola" and app["funkcje"]["konta"] is False
    assert w["paleta"]["kontrasty"]["jasny"]["glowny/tlo"] >= 4.5
    kolory = (aplikacja_tmp / "src/theme/kolory.ts").read_text(encoding="utf-8")
    assert "export const KOLORY" in kolory and w["paleta"]["jasny"]["glowny"] in kolory
    assert json.loads((aplikacja_tmp / "package.json").read_text(encoding="utf-8"))["name"] == "salon-ola"


def test_ustaw_z_kontami_przywraca_ekran(aplikacja_tmp):
    ap.ustaw(aplikacja_tmp, {**APLIKACJA, "firma": {**APLIKACJA["firma"], "usuwanie_konta_url": ""}}, {})
    ap.ustaw(aplikacja_tmp, APLIKACJA, {"logowanie": ["email"], "uprawnienia": ["aparat"], "powody": {"aparat": POWOD}})
    assert (aplikacja_tmp / "src/app/usun-konto.tsx").exists()
    assert (aplikacja_tmp / "src/app/_layout.tsx").read_text(encoding="utf-8").count('name="usun-konto"') == 1
    pl = json.loads((aplikacja_tmp / "locales/pl.json").read_text(encoding="utf-8"))
    assert pl == {"CFBundleDisplayName": "Salon Ola", "NSCameraUsageDescription": POWOD}


def test_ustaw_odrzuca_bledny_profil(aplikacja_tmp):
    with pytest.raises(ap.Blad, match="profil zgodności"):
        ap.ustaw(aplikacja_tmp, APLIKACJA, {"uprawnienia": ["aparat"]})


# ------------------------------------------------------------------ zasady JARVO (bez node_modules)

def test_zasady_jarvo_szablon_czysty(aplikacja_tmp):
    ap.ustaw(aplikacja_tmp, APLIKACJA, {"logowanie": ["email"]})
    k = ap.zasady_jarvo(aplikacja_tmp)
    assert all(x["ok"] for x in k)
    todo = next(x for x in k if x["id"] == "J-TODO")
    assert todo["ostrz"] and "konto.ts" in todo["opis"]               # usuwanie konta do podłączenia


def test_zasady_jarvo_lapia_problemy(aplikacja_tmp):
    ap.ustaw(aplikacja_tmp, APLIKACJA, {"logowanie": ["email"]})
    (aplikacja_tmp / "src/app/prywatnosc.tsx").unlink()
    (aplikacja_tmp / "src/app/usun-konto.tsx").unlink()
    (aplikacja_tmp / "src/lib/skaner.ts").write_text(
        "import { CameraView } from 'expo-camera';\nconst k = 'sk_live_abcdefghijklmnop1234';\n"
        "const s = process.env.EXPO_PUBLIC_SUPABASE_SERVICE_ROLE;\n", encoding="utf-8")
    ids = {x["id"] for x in ap.zasady_jarvo(aplikacja_tmp) if not x["ok"]}
    assert {"J-PLIKI", "J-USUWANIE", "J-UPRAWNIENIA", "J-SEKRET", "J-PUBLIC"} <= ids


def test_sprawdz_bez_node_modules(aplikacja_tmp):
    ap.ustaw(aplikacja_tmp, APLIKACJA, {})
    w = ap.sprawdz(aplikacja_tmp, siec=False)
    assert not w["ok"] and w["kontrole"][0]["id"] == "INSTALACJA"


# ------------------------------------------------------------------ podgląd i Expo Go

def test_token_z_linku():
    assert ap.token_z_linku("http://100.64.0.7:9120/Ab_Cd-12/index.html") == "Ab_Cd-12"
    # router aplikacji potraktowałby „/index.html” jak nieznaną trasę: właściciel dostaje adres katalogu
    assert ap.link_aplikacji("http://100.64.0.7:9120/Ab_Cd-12/index.html") == "http://100.64.0.7:9120/Ab_Cd-12/"


def test_serwer_spa_z_prefiksem(tmp_path):
    (tmp_path / "index.html").write_text("APLIKACJA", encoding="utf-8")
    (tmp_path / "_expo").mkdir()
    (tmp_path / "_expo" / "a.js").write_text("JS", encoding="utf-8")
    srv, port = ap.serwer_spa(tmp_path, "/tok123")
    try:
        czytaj = lambda p: urllib.request.urlopen(f"http://127.0.0.1:{port}{p}", timeout=5).read().decode()  # noqa: E731
        assert czytaj("/tok123/") == "APLIKACJA"
        assert czytaj("/tok123/wiecej") == "APLIKACJA"                 # trasa aplikacji → index.html
        assert czytaj("/tok123/_expo/a.js") == "JS"
    finally:
        srv.shutdown()


def test_grupa_z_eas_update():
    wyj = ('Uploading…\n[{"id":"u1","group":"g-123","platform":"ios","runtimeVersion":"exposdk:57.0.0"},'
           '{"id":"u2","group":"g-123","platform":"android","runtimeVersion":"exposdk:57.0.0"}]')
    assert ap.grupa_z_update(wyj) == "g-123"
    with pytest.raises(ap.Blad):
        ap.grupa_z_update('[{"group":"a"},{"group":"b"}]')


def test_linki_expo_go_i_strona(tmp_path):
    l = ap.linki_expo_go("proj-1", "g-1")
    assert l["qr_svg"].startswith("https://qr.expo.dev/eas-update?") and "slug=exp" in l["qr_svg"] and "groupId=g-1" in l["qr_svg"]
    assert l["url_tekst"].endswith("&format=url")
    p = ap.strona_expo_go(tmp_path, "Salon Ola", "exp://u.expo.dev/proj-1/group/g-1", l["qr_svg"])
    html = p.read_text(encoding="utf-8")
    assert 'href="exp://u.expo.dev/proj-1/group/g-1"' in html and "Expo Go" in html


def test_expo_go_bez_tokenu(monkeypatch, aplikacja_tmp):
    monkeypatch.delenv("EXPO_TOKEN", raising=False)
    with pytest.raises(ap.Blad, match="EXPO_TOKEN"):
        ap._eas(["whoami"], aplikacja_tmp)


# ------------------------------------------------------------------ szablon

def test_szablon_ma_elementy_zgodnosci():
    for rel in ap.WYMAGANE:
        assert (SZABLON / rel).exists(), rel
    cfg = (SZABLON / "app.config.ts").read_text(encoding="utf-8")
    assert "usesNonExemptEncryption: false" in cfg and "blockedPermissions" in cfg and "fingerprint" in cfg
    assert "JARVO-TODO" in (SZABLON / "src/lib/konto.ts").read_text(encoding="utf-8")
    pkg = json.loads((SZABLON / "package.json").read_text(encoding="utf-8"))
    assert pkg["dependencies"]["expo"].startswith("~57.") and "expo-font" in pkg["dependencies"]   # peer @expo/vector-icons
    gi = (SZABLON / ".gitignore").read_text(encoding="utf-8")
    assert ".env*" in gi and "*.p8" in gi and "/ios" in gi
