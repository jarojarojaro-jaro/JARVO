#!/usr/bin/env python3
"""Lista kontrolna przed wysłaniem do App Store i Google Play: 44 punkty z docs/MOBILE.md §8, każdy z dowodem,
najmniejszą poprawką i podstawą (numer wytycznej albo zasada sklepu).

    sklep_check.py <app> [--aab plik.aab] [--ipa plik.ipa] [--apk plik.apk] [--zgodnosc zgodnosc.yaml]
                   [--bez-sieci] [--json]
    sklep_check.py potwierdz <app> <nr> --kto właściciel --uwaga "…"     # punkt pół / ręczny sprawdzony przez człowieka

Czyta to, co sklepy faktycznie dostaną:
- konfigurację po wtyczkach (`npx expo config --type introspect`: Info.plist i uprawnienia Androida bez prebuilda;
  `--type public`: tylko to, co ustawiła aplikacja);
- zbudowane pliki, jeśli są (`--aab` / `--ipa` / `--apk` albo najnowsze w `out/build/`): manifest AAB (protobuf aapt2),
  wyrównanie bibliotek `.so` do 16 KB (nagłówki ELF), Info.plist i PrivacyInfo.xcprivacy z IPA, paczka JS;
- metadane: `store.config.json` (EAS Metadata, App Store) i karta Google w układzie fastlane supply
  (`out/sklep/google/pl-PL/{title,short_description,full_description}.txt`, `images/`);
- obrazy (nagłówek PNG: typ koloru 4/6 albo tRNS = kanał alfa) i adresy (2xx po przekierowaniach).

Tryby punktów: auto = skrypt rozstrzyga, błąd blokuje wysłanie; pół = skrypt zbiera dowody, człowiek potwierdza;
ręcznie = punkt dla właściciela w konsoli sklepu. Potwierdzenia: `out/sklep/potwierdzenia.json`.
Wynik: `out/sklep/check.json` i `out/sklep/CHECK.md`. Kod: 0 = brak błędów auto, 1 = są błędy auto, 2 = złe wejście.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import plistlib
import re
import subprocess
import sys
import time
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

TU = Path(__file__).resolve().parent
sys.path.insert(0, str(TU))

import mobile_lib as ml  # noqa: E402
import zgodnosc  # noqa: E402

# ------------------------------------------------------------------ 44 punkty (MOBILE.md §8)

PUNKTY: list[tuple[int, str, str, str, str]] = [
    (1, "A", "ręcznie", "wysyła właściciel ze swoich kont Apple i Google; agent jako członek zespołu", "Apple 4.2.6, 5.6.2"),
    (2, "A", "ręcznie", "status przedsiębiorcy DSA zweryfikowany w App Store Connect", "Apple: wymagania DSA"),
    (3, "A", "pół", "branża regulowana → wysyła podmiot prawny, dokumenty w notatkach", "Apple 5.6.2"),
    (4, "B", "auto", "identyfikatory iOS i Android w odwrotnej notacji domeny, nie przykładowe", "App Store Connect, Google Play"),
    (5, "B", "auto", "wersja wyższa niż w sklepie, numery buildów rosną same", "EAS, App Store Connect"),
    (6, "B", "auto", "Xcode ≥ 26, iOS od minimum SDK, targetSdkVersion ≥ 36", "Apple, Google (docelowe API)"),
    (7, "B", "auto", "biblioteki .so (64-bit) wyrównane do 16 KB", "Google (strony pamięci 16 KB)"),
    (8, "B", "auto", "bez debug, bez ruchu bez TLS, bez localhost i serwerów testowych w paczce", "Apple 2.1, 2.5.1"),
    (9, "B", "auto", "ustawione ios.config.usesNonExemptEncryption", "Apple: eksport szyfrowania"),
    (10, "B", "auto", "expo-doctor i expo install --check bez błędów", "Expo"),
    (11, "C", "auto", "każdy moduł z uprawnieniem ma opis w Info.plist", "Apple 5.1.1(ii)"),
    (12, "C", "auto", "opisy uprawnień po polsku, ≥ 40 znaków, bez ogólników", "Apple 5.1.1(ii)"),
    (13, "C", "auto", "brak zbędnych uprawnień (Info.plist i manifest wobec kodu)", "Apple 5.1.1(iii), Google: uprawnienia"),
    (14, "C", "pół", "uprawnienia wymagające deklaracji w Play Console oznaczone", "Google: uprawnienia wrażliwe"),
    (15, "C", "auto", "UIBackgroundModes tylko używane w kodzie", "Apple 2.5.4"),
    (16, "C", "auto", "manifest prywatności z powodami dla API z listy Apple", "Apple: manifest prywatności"),
    (17, "C", "pół", "szkic etykiety prywatności i Data safety z inwentarza bibliotek; ATT przy śledzeniu",
     "Apple 5.1.2, Google: Data safety"),
    (18, "C", "pół", "zewnętrzne AI → informacja i zgoda, zgłaszanie odpowiedzi", "Apple 5.1.2(i), Google: treści z AI"),
    (19, "C", "pół", "prośba o uprawnienie nie blokuje pierwszego ekranu", "Apple 5.1.2(i)"),
    (20, "D", "auto", "polityka prywatności: 200, nazwa firmy, po polsku, podlinkowana w aplikacji", "Apple 5.1.1(i), Google"),
    (21, "D", "auto", "strona wsparcia: 200, e-mail albo telefon", "App Review: wsparcie"),
    (22, "D", "auto", "konta → „Usuń konto” w aplikacji i działający adres w sieci", "Apple 5.1.1(v), Google: usuwanie konta"),
    (23, "D", "auto", "logowanie Google/Facebook → Zaloguj się przez Apple", "Apple 4.8"),
    (24, "D", "pół", "katalog i informacje dostępne bez logowania", "Apple 5.1.1(v)"),
    (25, "D", "auto", "konto demo dla recenzji, bez SMS i 2FA", "Apple 2.1, Google: dane logowania"),
    (26, "E", "auto", "brak tekstów zastępczych, TODO, „Wkrótce”, example.com, danych z szablonu", "Apple 2.1"),
    (27, "E", "auto", "linki w aplikacji i metadanych działają; pliki linków pasują do aplikacji", "Apple 2.1"),
    (28, "E", "pół", "to nie okno na stronę: mało WebView, funkcje natywne", "Apple 4.2, 4.2.2, Google: spam"),
    (29, "E", "pół", "podobieństwo do innych aplikacji floty poniżej progu", "Apple 4.3, Google: spam"),
    (30, "E", "auto", "treści cyfrowe tylko przez zakupy w aplikacji; Stripe/P24/PayU/BLIK za towary i usługi",
     "Apple 3.1.1, 3.1.3(e)"),
    (31, "E", "auto", "treści użytkowników → zgłaszanie, blokowanie, regulamin, kontakt", "Apple 1.2, Google: UGC"),
    (32, "E", "pół", "aktualizacje bez recenzji: polityka fingerprint, tylko poprawki", "Apple 2.5.2, Google: nadużycia"),
    (33, "E", "ręcznie", "przejście na prawdziwym iPhonie i Androidzie, IPv6, raport przedpremierowy, TestFlight",
     "Apple 2.1, 2.5.5"),
    (34, "F", "auto", "ikona iOS 1024 bez alfy, ikona adaptacyjna Androida, ekran startowy", "Expo: ikony"),
    (35, "F", "auto", "ikona Google 512×512 ≤ 1 MB, grafika promocyjna 1024×500 bez alfy", "Google: grafiki"),
    (36, "F", "auto", "zrzuty w wymiarach i liczbie sklepów, bez alfy", "Apple: zrzuty, Google: grafiki"),
    (37, "F", "pół", "zrzuty pokazują aplikację w użyciu; na iOS bez „Android”", "Apple 2.3.3, 2.3.10"),
    (38, "F", "ręcznie", "grafiki zrobione z pomocą AI oznaczone w Play Console", "Google: treści z AI"),
    (39, "G", "auto", "limity znaków metadanych", "Apple, Google: metadane"),
    (40, "G", "auto", "słowa kluczowe ≤ 100 bajtów, bez nazwy aplikacji, firmy i konkurencji", "Apple 2.3.7"),
    (41, "G", "auto", "bez zakazanych słów: obce platformy, „#1”, „najlepsza”, „darmowa”, rabaty, emoji, WIELKIE LITERY",
     "Apple 2.3.10, Google: metadane"),
    (42, "G", "auto", "karta i nazwa w wersji pl-PL", "App Store Connect, Play Console"),
    (43, "G", "ręcznie", "kwestionariusz wieku Apple; IARC, grupa docelowa, reklamy, Data safety w Google",
     "Apple, Google: kontrole przed recenzją"),
    (44, "G", "pół", "notatki dla recenzenta po angielsku: funkcje, ścieżka testu, konto demo", "Apple 2.3.1(a)"),
]
assert len(PUNKTY) == 44 and [p[0] for p in PUNKTY] == list(range(1, 45))

GRUPY = {"A": "Konto i tożsamość", "B": "Build i konfiguracja", "C": "Uprawnienia i prywatność", "D": "Konta i logowanie",
         "E": "Treść i funkcje", "F": "Grafiki", "G": "Metadane", "N": "Wyuczone z odrzuceń"}
ZNAKI = {"ok": "✓", "blad": "✗", "?": "?", "recznie": "☐"}
EAS = "eas-cli@24.7.0"

# wartości z szablonu expo-jarvo, które nie mogą trafić do sklepu
SZABLON = {"pl.mojafirma.app", "Moja Firma", "Moja Firma sp. z o.o.", "ul. Przykładowa 1, 00-001 Warszawa",
           "kontakt@mojafirma.pl", "https://mojafirma.pl", "Krótki opis, co klient załatwi w aplikacji."}
PRZYKLADOWE_ID = re.compile(r"^(com|org|pl)\.(example|mojafirma|test|demo|myapp|yourcompany)\b|^host\.exp\.", re.I)
LOKALNE = re.compile(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"
                     r"|[\w-]+\.ngrok(-free)?\.(io|app|dev)|[\w-]+\.loca\.lt|[\w.-]+\.local\b|staging\.|\.test\b|:8081\b)")
ZASTEPCZE = re.compile(r"lorem ipsum|\bTODO\b|\bFIXME\b|JARVO-TODO|\bwkrótce\b|coming soon|example\.(com|org)|"
                       r"\bplaceholder\b|\bXXX\b|tekst zastępczy|tu pojawi(ą)? się", re.I)
POLSKIE = re.compile(r"[ąćęłńóśźż]|\b(się|jest|nie|aby|oraz|dla|przy|twoje|twój|w|z|na|do)\b", re.I)
ANGIELSKIE = re.compile(r"\b(the|and|to|of|with|tap|open|login|log in|account|screen|test|you)\b", re.I)
POLSKIE_SLOWA = re.compile(r"\b(się|jest|nie|aby|oraz|dla|przy|że|jak|lub|który|która|można|będzie|twoje)\b", re.I)
# wzmianka o SMS / 2FA bez zaprzeczenia przed nią („no SMS code” jest w porządku)
DWA_ETAPY = re.compile(r"(?<!no )(?<!without )(?<!bez )(?<!not )\b(sms|2fa|one[- ]time code|otp|verification code)\b", re.I)
KONKURENCJA = ["booksy", "wolt", "pyszne", "glovo", "uber", "bolt", "allegro", "olx", "vinted", "zalando", "żabka", "zabka",
               "instagram", "facebook", "tiktok", "google", "apple", "android", "iphone", "fresha", "znanylekarz", "docplanner"]
OBCE_PLATFORMY = re.compile(r"\bandroid\w*|google play|play store|sklep\w* play|\bwindows\b|\bhuawei\w*|appgallery", re.I)
ZAKAZANE = re.compile(r"#\s?1\b|\bnr\s?1\b|\bnumer jeden\b|najlepsz\w*|\bnajtańsz\w*|\bbest\b|\btop\b|darmow\w*|za darmo|"
                      r"\bfree\b|\bgratis\b|rabat\w*|promocj\w*|zniżk\w*|-\s?\d{1,2}\s?%|\bsale\b|\bdiscount\b|\bbeta\b|"
                      r"\bnowość\b|\bnew\b|\bhit\b", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF]")
SKROTY = {"SMS", "QR", "PDF", "BLIK", "VAT", "NIP", "PIN", "GPS", "USB", "FAQ", "RODO", "SPA", "AI", "IT", "PLN", "EUR",
          "CEO", "HR", "SEO", "UX", "UI", "API", "B2B", "DIY", "LED", "TV", "DJ", "PZU", "ZUS", "NFZ", "PKO", "IKE"}
# moduł → tryb tła iOS, który usprawiedliwia (Apple 2.5.4)
TRYBY_TLA = {"location": ["expo-location", "expo-task-manager"], "remote-notification": ["expo-notifications"],
             "audio": ["expo-audio", "expo-av", "react-native-track-player"],
             "fetch": ["expo-background-fetch", "expo-background-task"], "processing": ["expo-background-task"],
             "voip": ["react-native-callkeep", "react-native-voip-push-notification"],
             "bluetooth-central": ["react-native-ble-plx"]}
# uprawnienia Androida → moduły, które je usprawiedliwiają
ANDROID_MODULY = {"CAMERA": ["expo-camera", "expo-image-picker", "react-native-vision-camera"],
                  "RECORD_AUDIO": ["expo-audio", "expo-av", "expo-camera"],
                  "ACCESS_FINE_LOCATION": ["expo-location"], "ACCESS_COARSE_LOCATION": ["expo-location"],
                  "ACCESS_BACKGROUND_LOCATION": ["expo-location"], "READ_CONTACTS": ["expo-contacts"],
                  "WRITE_CONTACTS": ["expo-contacts"], "READ_CALENDAR": ["expo-calendar"], "WRITE_CALENDAR": ["expo-calendar"],
                  "USE_BIOMETRIC": ["expo-local-authentication"], "USE_FINGERPRINT": ["expo-local-authentication"],
                  "POST_NOTIFICATIONS": ["expo-notifications"], "READ_MEDIA_IMAGES": ["expo-image-picker", "expo-media-library"],
                  "READ_MEDIA_VIDEO": ["expo-image-picker", "expo-media-library"],
                  "READ_MEDIA_VISUAL_USER_SELECTED": ["expo-image-picker", "expo-media-library"],
                  "VIBRATE": [], "INTERNET": [], "ACCESS_NETWORK_STATE": [], "WAKE_LOCK": [], "RECEIVE_BOOT_COMPLETED": [],
                  "FOREGROUND_SERVICE": ["expo-location", "expo-audio", "expo-task-manager", "expo-notifications"]}
DEKLAROWANE = {"ACCESS_BACKGROUND_LOCATION": "lokalizacja w tle (formularz z filmem)",
               "READ_MEDIA_IMAGES": "zdjęcia i filmy (selektor zdjęć zwykle wystarcza)",
               "READ_MEDIA_VIDEO": "zdjęcia i filmy", "READ_CONTACTS": "kontakty (od 2026 selektor kontaktów)",
               "QUERY_ALL_PACKAGES": "widoczność wszystkich aplikacji", "MANAGE_EXTERNAL_STORAGE": "dostęp do wszystkich plików",
               "SCHEDULE_EXACT_ALARM": "dokładne alarmy", "USE_EXACT_ALARM": "dokładne alarmy",
               "READ_SMS": "SMS", "SEND_SMS": "SMS", "RECEIVE_SMS": "SMS", "READ_CALL_LOG": "rejestr połączeń",
               "AD_ID": "identyfikator reklamowy (formularz reklam)", "SYSTEM_ALERT_WINDOW": "okno nad innymi aplikacjami",
               "USE_FULL_SCREEN_INTENT": "powiadomienia pełnoekranowe"}
FOREGROUND_TYPY = "FOREGROUND_SERVICE_"
AI_WZORCE = re.compile(r"api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com|api\.mistral\.ai|"
                       r"openrouter\.ai|api\.groq\.com|api\.deepseek\.com|bedrock|vertexai", re.I)
AI_PACZKI = {"openai", "@anthropic-ai/sdk", "@google/generative-ai", "@google/genai", "@mistralai/mistralai", "ai",
             "@ai-sdk/openai", "@ai-sdk/anthropic", "groq-sdk"}
IAP_PACZKI = {"react-native-iap", "expo-iap", "react-native-purchases", "expo-in-app-purchases"}
PLATNOSCI_ZEWN = {"@stripe/stripe-react-native", "react-native-payu", "react-native-przelewy24", "@adyen/react-native"}
SLEDZENIE_PACZKI = {"react-native-google-mobile-ads", "react-native-fbsdk-next", "@react-native-firebase/analytics",
                    "react-native-appsflyer", "react-native-adjust", "@amplitude/analytics-react-native",
                    "expo-ads-admob", "react-native-branch"}
LOGOWANIE_ZEWN = {"@react-native-google-signin/google-signin": "Google", "react-native-fbsdk-next": "Facebook",
                  "expo-auth-session": "OAuth (Google/Facebook?)", "@invertase/react-native-apple-authentication": "Apple"}
# biblioteki → typy danych do etykiety prywatności / Data safety (szkic; potwierdza człowiek)
INWENTARZ = {"expo-location": ["lokalizacja dokładna"], "expo-camera": ["zdjęcia lub filmy (tylko na urządzeniu?)"],
             "expo-image-picker": ["zdjęcia lub filmy"], "expo-contacts": ["kontakty"], "expo-calendar": ["kalendarz"],
             "expo-notifications": ["identyfikator urządzenia (token powiadomień)"],
             "@sentry/react-native": ["dane diagnostyczne (awarie)"], "sentry-expo": ["dane diagnostyczne (awarie)"],
             "@react-native-firebase/analytics": ["identyfikatory", "interakcje z aplikacją"],
             "@react-native-firebase/crashlytics": ["dane diagnostyczne (awarie)"],
             "react-native-google-mobile-ads": ["identyfikator reklamowy", "interakcje z aplikacją"],
             "react-native-fbsdk-next": ["identyfikatory", "interakcje z aplikacją"],
             "@react-native-google-signin/google-signin": ["e-mail", "imię i nazwisko"],
             "expo-apple-authentication": ["e-mail", "imię i nazwisko"],
             "@stripe/stripe-react-native": ["dane płatności (u operatora)"], "posthog-react-native": ["interakcje z aplikacją"],
             "@amplitude/analytics-react-native": ["interakcje z aplikacją", "identyfikatory"]}
LIMITY_APPLE = {"title": 30, "subtitle": 30, "promoText": 170, "description": 4000, "releaseNotes": 4000}
LIMITY_GOOGLE = {"title.txt": 30, "short_description.txt": 80, "full_description.txt": 4000}
ZRZUTY_APPLE = {"ios-6.9": [(1320, 2868), (1290, 2796)], "ios-6.5": [(1284, 2778), (1242, 2688)],
                "ipad-13": [(2064, 2752), (2048, 2732)]}
MIN_IOS_DOMYSLNE = "16.4"           # Expo SDK 57 (Expo.podspec), sprawdzane w node_modules, gdy są
TARGET_SDK_MIN = 36


# ------------------------------------------------------------------ odczyt buildów

def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        s += 7
        if not x & 0x80:
            return r, i


def _pola(b: bytes):
    """Pola wiadomości protobuf: (numer, typ, wartość) bez schematu."""
    i = 0
    while i < len(b):
        k, i = _varint(b, i)
        nr, typ = k >> 3, k & 7
        if typ == 0:
            v, i = _varint(b, i)
        elif typ == 2:
            n, i = _varint(b, i)
            v, i = b[i:i + n], i + n
        elif typ == 5:
            v, i = int.from_bytes(b[i:i + 4], "little"), i + 4
        elif typ == 1:
            v, i = int.from_bytes(b[i:i + 8], "little"), i + 8
        else:
            raise ValueError(f"protobuf: nieobsługiwany typ {typ}")
        yield nr, typ, v


def manifest_aab(dane: bytes) -> dict:
    """AndroidManifest.xml z AAB (XmlNode aapt2, Resources.proto) → {nazwa, atrybuty, dzieci}. Wartość atrybutu: tekst
    z pola `value`, a gdy pusty, liczba albo prawda/fałsz z `compiled_item.prim`."""
    def element(b: bytes) -> dict:
        el = {"nazwa": "", "atrybuty": {}, "dzieci": []}
        for nr, _, v in _pola(b):
            if nr == 3:
                el["nazwa"] = v.decode()
            elif nr == 4:
                nazwa, wartosc, prim = "", "", None
                for anr, _, av in _pola(v):
                    if anr == 2:
                        nazwa = av.decode()
                    elif anr == 3:
                        wartosc = av.decode()
                    elif anr == 6:
                        for inr, _, iv in _pola(av):
                            if inr == 7:
                                for pnr, _, pv in _pola(iv):
                                    prim = bool(pv) if pnr == 8 else pv
                el["atrybuty"][nazwa] = wartosc if wartosc != "" else ("" if prim is None else str(prim).lower())
            elif nr == 5:
                for cnr, _, cv in _pola(v):
                    if cnr == 1:
                        el["dzieci"].append(element(cv))
        return el
    for nr, _, v in _pola(dane):
        if nr == 1:
            return element(v)
    raise ValueError("manifest AAB bez elementu głównego")


def _znajdz(el: dict, nazwa: str) -> list[dict]:
    out = [el] if el["nazwa"] == nazwa else []
    for d in el["dzieci"]:
        out += _znajdz(d, nazwa)
    return out


def elf_wyrownanie(dane: bytes) -> tuple[int, int] | None:
    """(bity, najmniejsze p_align segmentów PT_LOAD) z nagłówka ELF; None, gdy to nie ELF."""
    if dane[:4] != b"\x7fELF":
        return None
    bity = 64 if dane[4] == 2 else 32
    kol = "little" if dane[5] == 1 else "big"
    u = lambda o, n: int.from_bytes(dane[o:o + n], kol)  # noqa: E731
    if bity == 64:
        phoff, phentsize, phnum = u(32, 8), u(54, 2), u(56, 2)
    else:
        phoff, phentsize, phnum = u(28, 4), u(42, 2), u(44, 2)
    najm = None
    for k in range(phnum):
        o = phoff + k * phentsize
        if u(o, 4) != 1:                                  # PT_LOAD
            continue
        align = u(o + 48, 8) if bity == 64 else u(o + 28, 4)
        najm = align if najm is None else min(najm, align)
    return bity, najm or 0


@dataclass
class Build:
    rodzaj: str                      # aab | apk | ipa
    sciezka: Path
    manifest: dict | None = None     # Android
    plist: dict = field(default_factory=dict)        # iOS Info.plist
    prywatnosc: dict | None = None   # iOS PrivacyInfo.xcprivacy aplikacji
    sdk_prywatnosc: list[str] = field(default_factory=list)
    biblioteki: list[dict] = field(default_factory=list)   # {plik, abi, bity, align, zip_ok}
    js: bytes = b""


def czytaj_build(p: Path) -> Build:
    rodzaj = p.suffix.lower().lstrip(".")
    b = Build(rodzaj, p)
    with zipfile.ZipFile(p) as z:
        nazwy = z.namelist()
        if rodzaj == "aab":
            b.manifest = manifest_aab(z.read("base/manifest/AndroidManifest.xml"))
        if rodzaj in ("aab", "apk"):
            for info in z.infolist():
                if info.filename.endswith(".so") and "/lib/" in "/" + info.filename:
                    czesci = info.filename.split("/")
                    abi = czesci[czesci.index("lib") + 1] if "lib" in czesci else "?"
                    with z.open(info) as f:
                        naglowek = f.read(4096)
                    wyr = elf_wyrownanie(naglowek)
                    if wyr is None:
                        continue
                    zip_ok = True
                    if rodzaj == "apk" and info.compress_type == zipfile.ZIP_STORED:   # APK: dane .so od granicy 16 KB
                        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
                        zip_ok = start % 16384 == 0
                    b.biblioteki.append({"plik": info.filename, "abi": abi, "bity": wyr[0], "align": wyr[1], "zip_ok": zip_ok})
            bundle = next((n for n in nazwy if n.endswith("index.android.bundle")), None)
            if bundle:
                b.js = z.read(bundle)
        if rodzaj == "ipa":
            app = next((n.rsplit("/", 1)[0] for n in nazwy if re.match(r"Payload/[^/]+\.app/Info\.plist$", n)), None)
            if not app:
                raise ValueError(f"{p.name}: brak Payload/*.app/Info.plist")
            b.plist = plistlib.loads(z.read(f"{app}/Info.plist"))
            if f"{app}/PrivacyInfo.xcprivacy" in nazwy:
                b.prywatnosc = plistlib.loads(z.read(f"{app}/PrivacyInfo.xcprivacy"))
            b.sdk_prywatnosc = sorted({n.split("/")[-2] for n in nazwy if n.endswith("PrivacyInfo.xcprivacy") and n.count("/") > 2})
            if f"{app}/main.jsbundle" in nazwy:
                b.js = z.read(f"{app}/main.jsbundle")
    return b


# ------------------------------------------------------------------ kontekst aplikacji

def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def konfiguracja(kat: Path) -> dict:
    """{public, introspect, zrodlo}: konfiguracja Expo po wtyczkach; bez node_modules odtworzona z jarvo.app.json."""
    if (kat / "node_modules" / "expo").exists():
        out = {}
        for typ in ("public", "introspect"):
            r = subprocess.run(["npx", "expo", "config", "--type", typ, "--json"], cwd=kat, capture_output=True, text=True,
                               timeout=180, env={**os.environ, "CI": "1", "EXPO_NO_TELEMETRY": "1"})
            if r.returncode != 0:
                raise RuntimeError(f"expo config --type {typ}: {(r.stdout + r.stderr).strip()[-600:]}")
            out[typ] = json.loads(r.stdout[r.stdout.find("{"):])
        return {**out, "zrodlo": "expo config"}
    app = _json(kat / "jarvo.app.json")
    cfg = {"name": app.get("nazwa"), "version": app.get("wersja"), "runtimeVersion": {"policy": "fingerprint"},
           "ios": {"bundleIdentifier": app.get("bundle_ios"), "supportsTablet": app.get("tablet"),
                   "config": {"usesNonExemptEncryption": False},
                   "infoPlist": {"CFBundleDevelopmentRegion": "pl", **(app.get("uprawnienia_ios") or {})}},
           "android": {"package": app.get("pakiet_android"), "blockedPermissions": app.get("zablokowane_uprawnienia_android") or []},
           "locales": {"pl": "./locales/pl.json"}, "plugins": app.get("wtyczki") or []}
    return {"public": cfg, "introspect": json.loads(json.dumps(cfg)), "zrodlo": "jarvo.app.json (bez node_modules)"}


@dataclass
class Kontekst:
    kat: Path
    siec: bool = True
    builds: dict[str, Build] = field(default_factory=dict)
    profil: dict = field(default_factory=dict)
    cfg: dict = field(default_factory=dict)

    def __post_init__(self):
        k = self.kat
        self.app = _json(k / "jarvo.app.json")
        self.pkg = _json(k / "package.json")
        self.deps = set(self.pkg.get("dependencies") or {}) | set(self.pkg.get("devDependencies") or {})
        self.src = {p.relative_to(k).as_posix(): p.read_text(encoding="utf-8", errors="replace")
                    for p in sorted((k / "src").rglob("*")) if p.suffix in (".ts", ".tsx", ".js", ".jsx") and p.is_file()} \
            if (k / "src").exists() else {}
        self.importy = {m for t in self.src.values() for m in re.findall(r"""(?:from|import|require\()\s*['"]([@\w./-]+)['"]""", t)}
        self.store = _json(k / "store.config.json")
        apple = self.store.get("apple") or {}
        self.apple_info = (apple.get("info") or {})
        self.apple_pl = self.apple_info.get("pl-PL") or {}
        self.review = apple.get("review") or {}
        self.sklep = k / "out" / "sklep"
        g = self.sklep / "google" / "pl-PL"
        self.google = {n: (g / n).read_text(encoding="utf-8").strip() for n in LIMITY_GOOGLE if (g / n).exists()}
        self.google_dir = g
        self.potw = _json(self.sklep / "potwierdzenia.json")
        self.funkcje = self.app.get("funkcje") or {}
        self.firma = self.app.get("firma") or {}

    @property
    def public(self) -> dict:
        return self.cfg.get("public") or {}

    @property
    def plist(self) -> dict:
        ipa = self.builds.get("ipa")
        return ipa.plist if ipa else ((self.cfg.get("introspect") or {}).get("ios") or {}).get("infoPlist") or {}

    def uzywa(self, modul: str) -> bool:
        return modul in self.deps or any(i == modul or i.startswith(modul + "/") for i in self.importy)

    def wtyczki(self) -> dict[str, dict]:
        out = {}
        for w in self.public.get("plugins") or []:
            n, pr = (w[0], w[1] if len(w) > 1 else {}) if isinstance(w, list) else (w, {})
            out[n] = pr or {}
        return out

    def uprawnienia_android(self) -> set[str]:
        aab = self.builds.get("aab")
        if aab and aab.manifest:
            return {e["atrybuty"].get("name", "") for e in _znajdz(aab.manifest, "uses-permission")}
        a = (self.cfg.get("introspect") or {}).get("android") or {}
        return set(a.get("permissions") or []) - set(a.get("blockedPermissions") or [])

    def metadane_teksty(self) -> dict[str, str]:
        out = {f"apple.{k}": str(v) for k, v in self.apple_pl.items() if isinstance(v, str)}
        if isinstance(self.apple_pl.get("keywords"), list):
            out["apple.keywords"] = ", ".join(self.apple_pl["keywords"])
        out.update({f"google.{k}": v for k, v in self.google.items()})
        return out


# ------------------------------------------------------------------ wynik punktu

@dataclass
class Wynik:
    nr: int
    stan: str                       # ok | blad | ? | recznie
    dowod: str = ""
    poprawka: str = ""


def _u(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def _http(url: str, ctx: Kontekst) -> tuple[int | None, str, str]:
    """(kod, treść, końcowy adres); bez sieci (None, '', ''). Strony właściciela, pojedyncze sprawdzenie."""
    if not ctx.siec:
        return None, "", ""
    try:
        o = ml.pobierz(url, pamiec_h=0, timeout=20, roboty=False)
        return o.kod, o.tresc, o.url
    except (ConnectionError, ml.Blokada) as e:
        return 0, str(e), url


def _tekst_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _publiczny(url: str) -> str:
    """Powód, dla którego recenzent nie otworzy adresu, albo pusty napis."""
    if not url.startswith("https://"):
        return f"{url}: nie HTTPS"
    if LOKALNE.search(url):
        return f"{url}: adres lokalny albo testowy"
    return ""


def _semver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


# ------------------------------------------------------------------ punkty

def p3(ctx):
    branza = (ctx.profil.get("branza") or "zwykla")
    if branza == "zwykla":
        return Wynik(3, "ok", "branża zwykła (profil zgodności)" if ctx.profil else "brak profilu zgodności: przyjęta branża zwykła")
    return Wynik(3, "?", f"branża {branza}: konto Apple organizacji i dokumenty w notatkach dla recenzenta",
                 "potwierdź, że wysyła podmiot prawny z licencją; dokumenty w załączniku App Review")


def p4(ctx):
    ios = (ctx.public.get("ios") or {}).get("bundleIdentifier") or ""
    android = (ctx.public.get("android") or {}).get("package") or ""
    if ctx.builds.get("aab") and ctx.builds["aab"].manifest:
        android = ctx.builds["aab"].manifest["atrybuty"].get("package") or android
    if ctx.builds.get("ipa"):
        ios = ctx.builds["ipa"].plist.get("CFBundleIdentifier") or ios
    zle = []
    for nazwa, v in (("iOS", ios), ("Android", android)):
        if not v:
            zle.append(f"{nazwa}: brak identyfikatora")
        elif not re.fullmatch(r"[a-z][a-z0-9]*(\.[a-z][a-z0-9_]*){2,}", v, re.I):
            zle.append(f"{nazwa}: {v!r} nie jest odwrotną domeną (np. pl.firma.app)")
        elif PRZYKLADOWE_ID.search(v) or v in SZABLON:
            zle.append(f"{nazwa}: {v!r} to identyfikator przykładowy albo z szablonu")
        elif nazwa == "Android" and "-" in v:
            zle.append(f"Android: {v!r} ma myślnik (niedozwolony w pakiecie)")
    if zle:
        return Wynik(4, "blad", "; ".join(zle), "ustaw bundle w out/aplikacja.yaml (odwrotna domena firmy) i `aplikacja.py ustaw`; "
                                                "po pierwszym wgraniu zmiana jest niemożliwa")
    return Wynik(4, "ok", f"iOS {ios}, Android {android}")


def p5(ctx):
    wersja = ctx.public.get("version") or ctx.app.get("wersja") or ""
    eas = _json(ctx.kat / "eas.json")
    zrodlo = (eas.get("cli") or {}).get("appVersionSource")
    auto = ((eas.get("build") or {}).get("production") or {}).get("autoIncrement")
    dowody, zle = [f"wersja {wersja}"], []
    if zrodlo != "remote" or not auto:
        zle.append("eas.json: numery buildów nie rosną same (cli.appVersionSource=remote i build.production.autoIncrement)")
    else:
        dowody.append("buildy numeruje EAS (remote, autoIncrement)")
    bundle = (ctx.public.get("ios") or {}).get("bundleIdentifier")
    if ctx.siec and bundle:
        try:
            d = ml.json_z(f"https://itunes.apple.com/lookup?bundleId={bundle}&country=pl", pamiec_h=1)
            wyniki = (d or {}).get("results") or []
        except (ConnectionError, ml.Blokada):
            wyniki = None
        if wyniki:
            w_sklepie = wyniki[0].get("version", "")
            dowody.append(f"App Store: {w_sklepie}")
            if _semver(wersja) <= _semver(w_sklepie):
                zle.append(f"wersja {wersja} nie jest wyższa niż w App Store ({w_sklepie})")
        elif wyniki == []:
            dowody.append("App Store: aplikacji jeszcze nie ma (pierwsze wydanie)")
    if not re.fullmatch(r"\d+\.\d+\.\d+", wersja or ""):
        zle.append(f"wersja {wersja!r} nie ma postaci X.Y.Z")
    if zle:
        return Wynik(5, "blad", "; ".join(zle + dowody), "podnieś `wersja` w aplikacja.yaml; numery buildów zostaw EAS")
    return Wynik(5, "ok", "; ".join(dowody))


def _min_ios(ctx) -> str:
    pod = ctx.kat / "node_modules" / "expo" / "Expo.podspec"
    if pod.exists():
        m = re.search(r":ios\s*=>\s*'([\d.]+)'", pod.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m.group(1)
    return MIN_IOS_DOMYSLNE


def _target_sdk_szablon(ctx) -> int | None:
    toml = ctx.kat / "node_modules" / "react-native" / "gradle" / "libs.versions.toml"
    if toml.exists():
        m = re.search(r'^targetSdk\s*=\s*"(\d+)"', toml.read_text(encoding="utf-8"), re.M)
        if m:
            return int(m.group(1))
    return None


def p6(ctx):
    dowody, zle, nie_wiem = [], [], []
    bp = ctx.wtyczki().get("expo-build-properties") or {}
    target = None
    aab = ctx.builds.get("aab")
    if aab and aab.manifest:
        sdk = _znajdz(aab.manifest, "uses-sdk")
        target = int(sdk[0]["atrybuty"].get("targetSdkVersion") or 0) if sdk else 0
        dowody.append(f"AAB targetSdkVersion {target}")
    else:
        target = (bp.get("android") or {}).get("targetSdkVersion") or _target_sdk_szablon(ctx)
        if target:
            dowody.append(f"targetSdkVersion {target} (konfiguracja / React Native)")
        else:
            nie_wiem.append("targetSdkVersion nieznany (brak AAB i node_modules)")
    if target is not None and target and int(target) < TARGET_SDK_MIN:
        zle.append(f"targetSdkVersion {target} < {TARGET_SDK_MIN} (Google: nowe aplikacje i aktualizacje od 31.08.2026)")
    min_ios = (bp.get("ios") or {}).get("deploymentTarget") or _min_ios(ctx)
    ipa = ctx.builds.get("ipa")
    if ipa:
        xcode = str(ipa.plist.get("DTXcode") or "")
        dowody.append(f"IPA: Xcode {xcode or '?'}, iOS od {ipa.plist.get('MinimumOSVersion', '?')}")
        if not xcode or int(xcode[:2] or 0) < 26:
            zle.append(f"IPA zbudowane Xcode {xcode or '?'} (< 26, wymóg Apple od 28.04.2026)")
        min_ios = ipa.plist.get("MinimumOSVersion") or min_ios
    else:
        nie_wiem.append("wersja Xcode: dopiero z IPA (EAS buduje na aktualnym obrazie)")
    if _semver(str(min_ios)) < _semver(_min_ios(ctx)):
        zle.append(f"iOS od {min_ios}, a Expo SDK wymaga {_min_ios(ctx)}")
    else:
        dowody.append(f"iOS od {min_ios}")
    if zle:
        return Wynik(6, "blad", "; ".join(zle + dowody), "aktualny Expo SDK i obraz EAS; targetSdk z expo-build-properties tylko w górę")
    return Wynik(6, "?" if nie_wiem else "ok", "; ".join(dowody + nie_wiem))


def p7(ctx):
    libs = [l for b in ("aab", "apk") if b in ctx.builds for l in ctx.builds[b].biblioteki]
    if not libs:
        return Wynik(7, "?", "brak AAB/APK: wyrównanie bibliotek sprawdzimy na buildzie (out/build/*.aab)")
    zle = [f"{l['plik']} (p_align {l['align']})" for l in libs if l["bity"] == 64 and l["align"] < 16384]
    zle += [f"{l['plik']} (APK: dane nie od granicy 16 KB)" for l in libs if not l["zip_ok"]]
    if zle:
        return Wynik(7, "blad", f"{len(zle)} z {len(libs)} bibliotek: " + ", ".join(zle[:6]),
                     "zaktualizuj biblioteki natywne (NDK r28+ wyrównuje do 16 KB); od 1.02.2027 bez tego nie wyjdzie aktualizacja")
    return Wynik(7, "ok", f"{len(libs)} bibliotek .so, 64-bitowe wyrównane do 16 KB")


def p8(ctx):
    zle, dowody = [], []
    aab = ctx.builds.get("aab")
    if aab and aab.manifest:
        app_el = _znajdz(aab.manifest, "application")
        at = app_el[0]["atrybuty"] if app_el else {}
        if at.get("debuggable") == "true":
            zle.append("AAB: android:debuggable=true")
        if at.get("usesCleartextTraffic") == "true":
            zle.append("AAB: usesCleartextTraffic=true (ruch bez TLS)")
        dowody.append("manifest AAB sprawdzony")
    ats = ((ctx.builds["ipa"].plist if "ipa" in ctx.builds else (ctx.public.get("ios") or {}).get("infoPlist") or {})
           .get("NSAppTransportSecurity") or {})
    if ats.get("NSAllowsArbitraryLoads"):
        zle.append("NSAllowsArbitraryLoads=true (ruch bez TLS)" + ("" if "ipa" in ctx.builds else " w konfiguracji aplikacji"))
    if (ctx.public.get("android") or {}).get("usesCleartextTraffic"):
        zle.append("android.usesCleartextTraffic w konfiguracji")
    trafienia = []
    for rel, t in ctx.src.items():
        for m in LOKALNE.finditer(t):
            linia = t.count("\n", 0, m.start()) + 1
            trafienia.append(f"{rel}:{linia} {m.group(0)}")
    for b in ctx.builds.values():
        if b.js:
            for m in LOKALNE.finditer(b.js.decode("latin-1")):
                trafienia.append(f"{b.sciezka.name} (paczka JS): {m.group(0)}")
    if trafienia:
        zle.append("adresy lokalne / testowe: " + ", ".join(sorted(set(trafienia))[:6]))
    dowody.append(f"kod: {len(ctx.src)} plików" + (", paczka JS z buildu" if any(b.js for b in ctx.builds.values()) else ""))
    if zle:
        return Wynik(8, "blad", "; ".join(zle), "adres backendu z produkcji (HTTPS), bez wyjątków ATS; build profilem production")
    return Wynik(8, "ok", "; ".join(dowody))


def p9(ctx):
    # `expo config --type public` usuwa ios.config (bywają tam klucze API), więc czytamy konfigurację po wtyczkach
    ios = (ctx.cfg.get("introspect") or {}).get("ios") or {}
    v = (ios.get("config") or {}).get("usesNonExemptEncryption")
    if v is None:
        v = ctx.plist.get("ITSAppUsesNonExemptEncryption")
    if "ipa" in ctx.builds and "ITSAppUsesNonExemptEncryption" in ctx.builds["ipa"].plist:
        v = ctx.builds["ipa"].plist["ITSAppUsesNonExemptEncryption"]
    if v is None:
        return Wynik(9, "blad", "brak ios.config.usesNonExemptEncryption: każde wgranie utknie na pytaniu o szyfrowanie",
                     "ios.config.usesNonExemptEncryption: false (HTTPS i szyfrowanie systemowe są zwolnione)")
    return Wynik(9, "ok", f"usesNonExemptEncryption = {str(v).lower()}")


def p10(ctx, sprawdz: dict | None = None):
    spr = sprawdz if sprawdz is not None else _json(ctx.kat / "out" / "jakosc" / "sprawdz.json")
    kontrole = {k["id"]: k for k in spr.get("kontrole", [])}
    if not kontrole:
        return Wynik(10, "?", "brak wyników `aplikacja.py sprawdz` (out/jakosc/sprawdz.json)", "uruchom `aplikacja.py sprawdz <app>`")
    zle = [f"{i}: {kontrole[i]['opis']}" for i in ("WERSJE", "DOCTOR", "INSTALACJA") if i in kontrole and not kontrole[i]["ok"]]
    if zle:
        return Wynik(10, "blad", "; ".join(zle), "`npx expo install --fix`, potem poprawki z expo-doctor")
    braki = [i for i in ("WERSJE", "DOCTOR") if i not in kontrole]
    if braki:
        return Wynik(10, "?", f"kontrole {', '.join(braki)} nie uruchomione (bez sieci?)", "`aplikacja.py sprawdz` z siecią")
    return Wynik(10, "ok", "expo install --check i expo-doctor bez błędów")


def _klucze_modulow(ctx) -> dict[str, list[str]]:
    """moduł używany przez aplikację → klucze Info.plist, których potrzebuje."""
    out: dict[str, list[str]] = {}
    for u, d in zgodnosc.UPRAWNIENIA.items():
        if d["ios"] and ctx.uzywa(d["modul"]) and (u != "lokalizacja-w-tle" or "UIBackgroundModes" in ctx.plist):
            out.setdefault(d["modul"], []).append(d["ios"])
    return out


def p11(ctx):
    plist = ctx.plist
    braki = [f"{m}: {k}" for m, ks in _klucze_modulow(ctx).items() for k in ks if not plist.get(k)]
    if braki:
        return Wynik(11, "blad", "brak opisu: " + ", ".join(braki), "uprawnienie w profilu zgodności z polskim powodem, `aplikacja.py ustaw`")
    klucze = sorted(k for k in plist if k.endswith("UsageDescription"))
    return Wynik(11, "ok", f"opisy: {', '.join(klucze) or 'aplikacja nie prosi o uprawnienia'} (źródło: {ctx.cfg.get('zrodlo', 'IPA')})")


def p12(ctx):
    lokalne = _json(ctx.kat / "locales" / "pl.json")
    zle = []
    for k, v in sorted(ctx.plist.items()):
        if not k.endswith("UsageDescription"):
            continue
        tekst = str(lokalne.get(k) or v or "")
        if len(tekst) < zgodnosc.POWOD_MIN:
            zle.append(f"{k}: za krótki ({len(tekst)} znaków)")
        elif zgodnosc.OGOLNIKI.search(tekst):
            zle.append(f"{k}: ogólnik {tekst[:60]!r}")
        elif not POLSKIE.search(tekst):
            zle.append(f"{k}: nie po polsku {tekst[:60]!r}")
    if zle:
        return Wynik(12, "blad", "; ".join(zle), "konkretny polski powód z nazwą funkcji (np. „Aparat służy do zeskanowania kodu QR…”) "
                                                 "albo `false` dla klucza wtyczki, którego aplikacja nie używa")
    return Wynik(12, "ok", "opisy po polsku, konkretne")


def p13(ctx):
    potrzebne = {k for ks in _klucze_modulow(ctx).values() for k in ks}
    znane = {d["ios"] for d in zgodnosc.UPRAWNIENIA.values() if d["ios"]} | {
        "NSMicrophoneUsageDescription", "NSLocationAlwaysUsageDescription", "NSMotionUsageDescription",
        "NSRemindersUsageDescription", "NSRemindersFullAccessUsageDescription", "NSCalendarsUsageDescription",
        "NSLocationWhenInUseUsageDescription", "NSPhotoLibraryAddUsageDescription", "NSBluetoothAlwaysUsageDescription"}
    zle = []
    for k in sorted(ctx.plist):
        if k.endswith("UsageDescription") and k in znane and k not in potrzebne:
            if k == "NSMicrophoneUsageDescription" and (ctx.uzywa("expo-audio") or ctx.uzywa("expo-av")):
                continue
            if k in ("NSLocationAlwaysUsageDescription",) and "NSLocationAlwaysAndWhenInUseUsageDescription" in potrzebne:
                continue
            if k == "NSCalendarsUsageDescription" and ctx.uzywa("expo-calendar"):
                continue
            zle.append(f"iOS {k} bez modułu, który go używa")
    android = ctx.uprawnienia_android()
    for perm in sorted(android):
        krotka = perm.rsplit(".", 1)[-1]
        if krotka.startswith(FOREGROUND_TYPY):
            krotka = "FOREGROUND_SERVICE"
        if krotka in ANDROID_MODULY:
            if ANDROID_MODULY[krotka] and not any(ctx.uzywa(m) for m in ANDROID_MODULY[krotka]):
                zle.append(f"Android {krotka} bez modułu ({' / '.join(ANDROID_MODULY[krotka])})")
        elif perm in zgodnosc.ZAWSZE_BLOKUJ:
            zle.append(f"Android {perm}: na liście blokowanych, a jest w {'AAB' if 'aab' in ctx.builds else 'konfiguracji'}")
    if zle:
        return Wynik(13, "blad", "; ".join(zle), "`false` w propsie wtyczki albo android.blockedPermissions; uprawnienie tylko dla użytej funkcji")
    return Wynik(13, "ok", f"iOS {len([k for k in ctx.plist if k.endswith('UsageDescription')])} opisów, Android {len(android)} uprawnień "
                           f"({'AAB' if 'aab' in ctx.builds else 'konfiguracja; biblioteki dopiszą swoje w buildzie'})")


def p14(ctx):
    wrazliwe = []
    for perm in ctx.uprawnienia_android():
        krotka = perm.rsplit(".", 1)[-1]
        if krotka in DEKLAROWANE:
            wrazliwe.append(f"{krotka}: {DEKLAROWANE[krotka]}")
        elif krotka.startswith(FOREGROUND_TYPY):
            wrazliwe.append(f"{krotka}: usługa pierwszoplanowa (deklaracja typu i film)")
    if wrazliwe:
        return Wynik(14, "?", "do deklaracji w Play Console: " + "; ".join(sorted(wrazliwe)),
                     "właściciel wypełnia deklaracje w Play Console (Treść aplikacji) albo usuwamy uprawnienie")
    return Wynik(14, "ok", "brak uprawnień wymagających deklaracji" + ("" if "aab" in ctx.builds else " (konfiguracja; potwierdzi AAB)"))


def p15(ctx):
    tryby = ctx.plist.get("UIBackgroundModes") or []
    zle = [t for t in tryby if t in TRYBY_TLA and not any(ctx.uzywa(m) for m in TRYBY_TLA[t])]
    zle += [t for t in tryby if t not in TRYBY_TLA]
    if zle:
        return Wynik(15, "blad", f"tryby tła bez użycia w kodzie: {', '.join(zle)}", "usuń tryb z konfiguracji (isIosBackgroundLocationEnabled itd.)")
    return Wynik(15, "ok", f"tryby tła: {', '.join(tryby) or 'brak'}")


def p16(ctx):
    ipa = ctx.builds.get("ipa")
    if not ipa:
        dodatkowe = (ctx.public.get("ios") or {}).get("privacyManifests")
        return Wynik(16, "?", "manifest prywatności dołącza Expo przy buildzie (moduły SDK mają własne); "
                              f"ios.privacyManifests w konfiguracji: {'tak' if dodatkowe else 'nie'}; potwierdzi IPA",
                     "sprawdź na IPA (out/build/*.ipa): `sklep_check.py --ipa`")
    if not ipa.prywatnosc:
        return Wynik(16, "blad", "IPA bez PrivacyInfo.xcprivacy aplikacji", "ios.privacyManifests w app.config (Expo dołącza go przy prebuildzie)")
    zle = [t.get("NSPrivacyAccessedAPIType", "?") for t in ipa.prywatnosc.get("NSPrivacyAccessedAPITypes") or []
           if not t.get("NSPrivacyAccessedAPITypeReasons")]
    if zle:
        return Wynik(16, "blad", f"API bez powodu: {', '.join(zle)}", "powód z listy Apple w ios.privacyManifests")
    return Wynik(16, "ok", f"manifest aplikacji: {len(ipa.prywatnosc.get('NSPrivacyAccessedAPITypes') or [])} API z powodami; "
                           f"manifesty bibliotek: {len(ipa.sdk_prywatnosc)}")


def szkic_prywatnosci(ctx) -> dict:
    dane: dict[str, list[str]] = {}
    for paczka, typy in INWENTARZ.items():
        if ctx.uzywa(paczka):
            for t in typy:
                dane.setdefault(t, []).append(paczka)
    if ctx.funkcje.get("konta"):
        dane.setdefault("e-mail", []).append("konto w aplikacji")
    sledzenie = sorted(p for p in SLEDZENIE_PACZKI if ctx.uzywa(p))
    return {"dane": dane, "sledzenie": sledzenie, "att": ctx.uzywa("expo-tracking-transparency"),
            "uwaga": "szkic z inwentarza bibliotek i funkcji; cel, powiązanie z osobą i udostępnianie potwierdza człowiek"}


def p17(ctx):
    s = szkic_prywatnosci(ctx)
    ml.zapisz(ctx.sklep / "prywatnosc-szkic.json", json.dumps(s, ensure_ascii=False, indent=2))
    if s["sledzenie"] and not s["att"]:
        return Wynik(17, "blad", f"biblioteki śledzące ({', '.join(s['sledzenie'])}) bez expo-tracking-transparency (ATT)",
                     "uprawnienie `sledzenie` w profilu zgodności albo usunięcie SDK")
    opis = ", ".join(f"{k} ({', '.join(v)})" for k, v in s["dane"].items()) or "aplikacja nie zbiera danych przez biblioteki"
    return Wynik(17, "?", f"szkic: out/sklep/prywatnosc-szkic.json: {opis}",
                 "właściciel przenosi szkic do etykiety App Store i formularza Data safety (cel, powiązanie z osobą)")


def p18(ctx):
    ai = ctx.funkcje.get("ai") or any(ctx.uzywa(p) for p in AI_PACZKI) or any(AI_WZORCE.search(t) for t in ctx.src.values())
    if not ai:
        return Wynik(18, "ok", "brak wywołań zewnętrznego AI")
    tekst = "\n".join(ctx.src.values())
    zgoda = re.search(r"zgod\w*[^\n]{0,80}\b(AI|sztuczn)|ZgodaAI|zgoda-ai", tekst, re.I)
    zglos = re.search(r"Zgłoś (odpowiedź|treść)|zglosOdpowiedz|zgłoś", tekst, re.I)
    brak = [n for n, ok in (("ekran zgody przed pierwszym użyciem AI", zgoda), ("„Zgłoś odpowiedź”", zglos)) if not ok]
    if brak:
        return Wynik(18, "blad", f"AI bez: {', '.join(brak)}", "ekran zgody (jaka firma, jakie dane) i przycisk zgłaszania przy odpowiedzi")
    return Wynik(18, "?", "AI: jest ekran zgody i zgłaszanie; treść zgody do potwierdzenia", "przeczytaj zgodę: nazwa dostawcy AI i zakres danych")


def _pierwsze_ekrany(ctx) -> dict[str, str]:
    return {r: t for r, t in ctx.src.items() if r in ("src/app/_layout.tsx", "src/app/(tabs)/_layout.tsx", "src/app/(tabs)/index.tsx",
                                                     "src/app/index.tsx")}


def p19(ctx):
    prosby = []
    for rel, t in _pierwsze_ekrany(ctx).items():
        for m in re.finditer(r"request\w*Permissions?Async|requestPermission\b|requestTrackingPermissionsAsync", t):
            prosby.append(f"{rel}:{t.count(chr(10), 0, m.start()) + 1} {m.group(0)}")
    if prosby:
        return Wynik(19, "blad", "prośba o uprawnienie na pierwszych ekranach: " + ", ".join(prosby),
                     "proś w chwili użycia funkcji, z ekranem wyjaśnienia; odmowa nie blokuje reszty")
    return Wynik(19, "?", "pierwsze ekrany bez prośby o uprawnienia (kod); ATT i powiadomienia sprawdź w przejściu na urządzeniu")


def p20(ctx):
    url = ctx.firma.get("prywatnosc_url") or ""
    sklep = ctx.apple_pl.get("privacyPolicyUrl")
    zle, dowody = [], []
    if not url:
        return Wynik(20, "blad", "brak firma.prywatnosc_url", "strona polityki prywatności na witrynie (jarvo-web), adres w aplikacja.yaml")
    if url in SZABLON or "mojafirma" in url:
        zle.append(f"adres z szablonu: {url}")
    if _publiczny(url):
        return Wynik(20, "blad", _publiczny(url), "publiczny adres HTTPS polityki na witrynie firmy (jarvo-web)")
    if sklep and sklep.rstrip("/") != url.rstrip("/"):
        zle.append(f"store.config.json privacyPolicyUrl {sklep} ≠ adres w aplikacji {url}")
    w_aplikacji = any(("prywatnosc_url" in t or url in t) for t in ctx.src.values())
    if not w_aplikacji:
        zle.append("aplikacja nie linkuje polityki (ekran Prywatność)")
    kod, tresc, _ = _http(url, ctx)
    if kod is None:
        dowody.append("bez sieci: adresu nie sprawdzono")
    elif not 200 <= kod < 300:
        zle.append(f"{url}: HTTP {kod or 'brak odpowiedzi'}")
    else:
        tekst = _tekst_html(tresc)
        firma = ctx.firma.get("nazwa") or ""
        rdzen = re.sub(r"\b(sp\. z o\.o\.|s\.a\.|sp\.k\.|s\.c\.|spółka.*)$", "", firma, flags=re.I).strip(" .,")
        if rdzen and _u(rdzen) not in _u(tekst):
            zle.append(f"polityka nie wymienia firmy „{rdzen}”")
        if len(POLSKIE.findall(tekst)) < 20:
            zle.append("polityka nie jest po polsku")
        dowody.append(f"{url}: HTTP {kod}, {len(tekst)} znaków")
    if zle:
        return Wynik(20, "blad", "; ".join(zle + dowody), "polityka po polsku z nazwą firmy (jarvo-web), ten sam adres w aplikacji i w sklepie")
    return Wynik(20, "?" if kod is None else "ok", "; ".join(dowody + ["link w aplikacji"]))


def p21(ctx):
    url = ctx.apple_pl.get("supportUrl") or ctx.firma.get("strona") or ""
    if not url:
        return Wynik(21, "blad", "brak adresu wsparcia (store.config.json supportUrl albo firma.strona)", "strona kontaktu na witrynie")
    if "mojafirma" in url:
        return Wynik(21, "blad", f"adres z szablonu: {url}", "adres strony kontaktu firmy")
    if _publiczny(url):
        return Wynik(21, "blad", _publiczny(url), "publiczny adres HTTPS strony kontaktu")
    kod, tresc, _ = _http(url, ctx)
    if kod is None:
        return Wynik(21, "?", f"{url}: bez sieci nie sprawdzono")
    if not 200 <= kod < 300:
        return Wynik(21, "blad", f"{url}: HTTP {kod or 'brak odpowiedzi'}", "działająca strona kontaktu")
    tekst = _tekst_html(tresc) + " " + " ".join(re.findall(r'href="(?:mailto|tel):([^"]+)"', tresc))
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d \-]{7,}\d", tekst):
        return Wynik(21, "blad", f"{url}: brak e-maila i telefonu na stronie", "e-mail albo telefon widoczny na stronie wsparcia")
    return Wynik(21, "ok", f"{url}: HTTP {kod}, kontakt na stronie")


def p22(ctx):
    if not ctx.funkcje.get("konta"):
        return Wynik(22, "ok", "aplikacja bez kont")
    zle, dowody = [], []
    if "src/app/usun-konto.tsx" not in ctx.src:
        zle.append("brak ekranu Usuń konto w aplikacji")
    url = ctx.firma.get("usuwanie_konta_url") or ""
    if not url:
        zle.append("brak firma.usuwanie_konta_url (Google wymaga adresu w sieci)")
    elif _publiczny(url):
        zle.append(_publiczny(url))
    else:
        kod, tresc, _ = _http(url, ctx)
        if kod is None:
            dowody.append("bez sieci: adresu nie sprawdzono")
        elif not 200 <= kod < 300:
            zle.append(f"{url}: HTTP {kod or 'brak odpowiedzi'}")
        elif not re.search(r"usu\w* (konto|kont|danych)|delete (your )?account", _tekst_html(tresc), re.I):
            zle.append(f"{url}: strona nie opisuje usuwania konta")
        else:
            dowody.append(f"{url}: HTTP {kod}")
    if zle:
        return Wynik(22, "blad", "; ".join(zle), "ekran Usuń konto (szablon) + strona usuwania konta na witrynie (jarvo-web)")
    return Wynik(22, "?" if any("bez sieci" in d for d in dowody) else "ok", "ekran Usuń konto; " + "; ".join(dowody))


def p23(ctx):
    zewn = [n for p, n in LOGOWANIE_ZEWN.items() if ctx.uzywa(p) and n != "Apple"]
    if not zewn:
        return Wynik(23, "ok", "brak logowania Google/Facebook")
    apple = ctx.uzywa("expo-apple-authentication") or ctx.uzywa("@invertase/react-native-apple-authentication")
    przycisk = any(re.search(r"AppleAuthenticationButton|signInAsync|appleAuth", t) for t in ctx.src.values())
    if not (apple and przycisk):
        return Wynik(23, "blad", f"logowanie {', '.join(zewn)} bez Zaloguj się przez Apple" + ("" if apple else " (brak modułu)"),
                     "expo-apple-authentication + przycisk na ekranie logowania iOS (profil zgodności dodaje sam)")
    return Wynik(23, "ok", f"logowanie {', '.join(zewn)} + Apple")


def p24(ctx):
    if not ctx.funkcje.get("konta"):
        return Wynik(24, "ok", "aplikacja bez kont")
    przekierowania = [f"{r}: {m.group(0)}" for r, t in _pierwsze_ekrany(ctx).items()
                      for m in re.finditer(r"<Redirect[^>]*href=['\"{][^>]*(logowanie|login|zaloguj)[^>]*>", t, re.I)]
    if przekierowania:
        return Wynik(24, "blad", "pierwszy ekran przekierowuje do logowania: " + "; ".join(przekierowania),
                     "katalog i informacje bez konta; logowanie dopiero przy rezerwacji / zakupie")
    return Wynik(24, "?", "brak przekierowania do logowania na pierwszych ekranach (kod); potwierdź przejściem bez konta")


def p25(ctx):
    if not ctx.funkcje.get("konta"):
        return Wynik(25, "ok", "aplikacja bez kont: konto demo niepotrzebne")
    r = ctx.review
    zle = []
    if not r.get("demoUsername"):
        zle.append("brak apple.review.demoUsername w store.config.json")
    if r.get("demoPassword"):
        zle.append("hasło demo w store.config.json: plik jest w repo aplikacji (bywa publiczne dla darmowego CI iOS); "
                   "hasło tylko w JARVO_DEMO_HASLO (.env profilu), wstawia je `wydanie.py karta` na czas wysyłki")
    elif not os.environ.get("JARVO_DEMO_HASLO"):
        zle.append("brak hasła demo: JARVO_DEMO_HASLO w .env profilu (wpisuje właściciel, nie w czacie)")
    if r.get("demoRequired") is False:
        zle.append("demoRequired=false przy aplikacji z kontami")
    notatki = str(r.get("notes") or "")
    if DWA_ETAPY.search(notatki + " " + str(r.get("demoUsername") or "")):
        zle.append("konto demo wymaga kodu SMS / 2FA (recenzent go nie dostanie)")
    if zle:
        return Wynik(25, "blad", "; ".join(zle), "konto demo bez 2FA z przykładowymi danymi; to samo w Play Console (Dostęp do aplikacji)")
    logowanie = (ctx.app.get("backend") or {}).get("demo_login")
    if logowanie and ctx.siec:
        try:
            dane = json.dumps({"login": r["demoUsername"], "haslo": os.environ.get("JARVO_DEMO_HASLO")}).encode()
            import urllib.request
            req = urllib.request.Request(logowanie, data=dane, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=20) as o:  # noqa: S310 (backend aplikacji właściciela)
                kod = o.status
        except Exception as e:  # noqa: BLE001
            return Wynik(25, "blad", f"logowanie kontem demo nie działa: {e}", "sprawdź konto demo na produkcyjnym backendzie")
        return Wynik(25, "ok", f"konto demo {r['demoUsername']}: logowanie HTTP {kod}")
    return Wynik(25, "ok", f"konto demo {r['demoUsername']} (logowania nie sprawdzono: brak backend.demo_login)")


def p26(ctx):
    trafienia = []
    for rel, t in ctx.src.items():
        for m in ZASTEPCZE.finditer(t):
            trafienia.append(f"{rel}:{t.count(chr(10), 0, m.start()) + 1} {m.group(0)}")
    for k, t in ctx.metadane_teksty().items():
        for m in ZASTEPCZE.finditer(t):
            trafienia.append(f"{k}: {m.group(0)}")
    for k, v in [("nazwa", ctx.app.get("nazwa")), ("opis", ctx.app.get("opis"))] + [(f"firma.{a}", b) for a, b in ctx.firma.items()]:
        if v in SZABLON or (isinstance(v, str) and "mojafirma" in v):
            trafienia.append(f"jarvo.app.json {k}: dane z szablonu ({v})")
    if trafienia:
        return Wynik(26, "blad", f"{len(trafienia)}: " + "; ".join(trafienia[:8]),
                     "prawdziwe treści i dane firmy; JARVO-TODO zamknięte (Apple 2.1: aplikacja kompletna)")
    return Wynik(26, "ok", f"kod ({len(ctx.src)} plików) i metadane bez tekstów zastępczych")


def p27(ctx):
    adresy = set()
    for t in list(ctx.src.values()) + list(ctx.metadane_teksty().values()):
        adresy.update(u.rstrip(".,);'\"") for u in re.findall(r"https?://[^\s'\"`<>)]+", t))
    adresy.update(v for v in ctx.firma.values() if isinstance(v, str) and v.startswith("http"))
    adresy.update(v for k, v in ctx.apple_pl.items() if k.endswith("Url") and v)
    adresy = {a for a in adresy if "${" not in a and not LOKALNE.search(a) and "u.expo.dev" not in a}
    if not ctx.siec:
        return Wynik(27, "?", f"bez sieci: {len(adresy)} adresów nie sprawdzono")
    zle = []
    for a in sorted(adresy)[:40]:
        kod, _, _ = _http(a, ctx)
        if not kod or not 200 <= kod < 400:
            zle.append(f"{a}: HTTP {kod or 'brak odpowiedzi'}")
    dowody = [f"{len(adresy)} adresów"]
    ios = ctx.public.get("ios") or {}
    domeny = [d.split(":", 1)[1] for d in (ios.get("associatedDomains") or []) if d.startswith("applinks:")]
    if domeny:
        import audyt_mobilny as am
        for host in domeny:
            a = am.aasa(host)
            if not any(i.endswith("." + (ios.get("bundleIdentifier") or "")) for i in a.get("app_ids", [])):
                zle.append(f"{host}: apple-app-site-association bez {ios.get('bundleIdentifier')}")
        dowody.append(f"Universal Links: {', '.join(domeny)}")
    filtry = [f for f in ((ctx.public.get("android") or {}).get("intentFilters") or []) if f.get("autoVerify")]
    if filtry:
        import audyt_mobilny as am
        pakiet = (ctx.public.get("android") or {}).get("package")
        for host in sorted({d.get("host") for f in filtry for d in f.get("data", []) if d.get("host")}):
            a = am.assetlinks(host)
            if not a.get("pakiety", {}).get(pakiet):
                zle.append(f"{host}: assetlinks.json bez {pakiet} z odciskiem certyfikatu")
        dowody.append("App Links sprawdzone")
    if zle:
        return Wynik(27, "blad", "; ".join(zle[:8]), "napraw albo usuń martwe linki; pliki .well-known z jarvo-web")
    return Wynik(27, "ok", "; ".join(dowody) + ": działają")


def p28(ctx):
    ekrany = [r for r in ctx.src if r.startswith("src/app/") and not Path(r).name.startswith("_")]
    webview = [r for r in ekrany if "react-native-webview" in ctx.src[r]]
    natywne = sorted(m for m in ("expo-notifications", "expo-camera", "expo-location", "expo-calendar", "expo-local-authentication",
                                 "expo-image-picker", "expo-apple-authentication", "react-native-maps", "expo-store-review",
                                 "expo-contacts", "expo-sharing") if ctx.uzywa(m))
    udzial = len(webview) / max(1, len(ekrany))
    dowod = f"ekrany {len(ekrany)}, z WebView {len(webview)} ({udzial:.0%}); funkcje natywne: {', '.join(natywne) or 'brak'}"
    if udzial >= 0.4 or (webview and not natywne):
        return Wynik(28, "blad", dowod, "funkcje natywne z planu (powiadomienia, rezerwacja, offline) zamiast okna na stronę; "
                                        "albo PWA zamiast aplikacji (natywna-czy-pwa)")
    return Wynik(28, "?", dowod, "oceń, czy aplikacja daje więcej niż strona (Apple 4.2)")


def _odcisk(kat: Path) -> set[str]:
    teksty = set()
    for p in (kat / "src").rglob("*.tsx") if (kat / "src").exists() else []:
        for m in re.findall(r">\s*([^<>{}\n]{12,})\s*<|['\"]([^'\"\n]{16,})['\"]", p.read_text(encoding="utf-8", errors="replace")):
            s = (m[0] or m[1]).strip()
            if s and not s.startswith(("@", "./", "../", "http")):
                teksty.add(_u(s))
    app = _json(kat / "jarvo.app.json")
    teksty.add(_u(str(app.get("opis") or "")))
    teksty.update(f"ekran:{p.stem}" for p in (kat / "src" / "app").rglob("*.tsx")) if (kat / "src" / "app").exists() else None
    return teksty


def p29(ctx):
    szablon = _odcisk(TU.parent / "templates" / "expo-jarvo")
    nasz = _odcisk(ctx.kat) - szablon
    korzen = Path(os.environ.get("JARVO_MOBILE_PRACE", "/opt/data/jarvo/workspaces/jarvo-mobile"))
    inne = [p.parent for p in korzen.glob("*/**/jarvo.app.json") if "node_modules" not in p.parts and p.parent.resolve() != ctx.kat.resolve()] \
        if korzen.exists() else []
    najblizsze = []
    for kat in inne[:50]:
        ich = _odcisk(kat) - szablon
        if nasz and ich:
            najblizsze.append((len(nasz & ich) / len(nasz | ich), kat))
    najblizsze.sort(reverse=True)
    if not najblizsze:
        return Wynik(29, "?", f"brak innych aplikacji floty do porównania; własnych treści: {len(nasz)}")
    wsp, kat = najblizsze[0]
    dowod = f"najbliższa: {kat} (wspólne treści poza szablonem {wsp:.0%}); porównano {len(najblizsze)}"
    if wsp >= 0.5:
        return Wynik(29, "blad", dowod, "własne ekrany, treści i wygląd (oś 10 rubryki); jedna aplikacja zamiast kopii (Apple 4.3)")
    return Wynik(29, "?", dowod)


def p30(ctx):
    plat = set(ctx.profil.get("platnosci") or [])
    iap = sorted(p for p in IAP_PACZKI if ctx.uzywa(p))
    zewn = sorted(p for p in PLATNOSCI_ZEWN if ctx.uzywa(p))
    if "cyfrowe" in plat and not iap:
        return Wynik(30, "blad", f"treści cyfrowe w profilu, brak zakupów w aplikacji (biblioteki: {', '.join(zewn) or 'brak'})",
                     "expo-iap / RevenueCat dla treści cyfrowych (Apple 3.1.1)")
    if zewn and plat and not plat & {"fizyczne", "uslugi"}:
        return Wynik(30, "blad", f"{', '.join(zewn)} przy płatnościach tylko cyfrowych", "treści cyfrowe tylko przez zakupy w aplikacji")
    if iap and plat and not plat & {"cyfrowe", "subskrypcja"}:
        return Wynik(30, "blad", f"zakupy w aplikacji ({', '.join(iap)}) przy towarach fizycznych / usługach (Apple 3.1.3(e))",
                     "Stripe, P24, PayU, BLIK dla towarów i usług")
    if (zewn or iap) and not ctx.profil:
        return Wynik(30, "?", f"płatności ({', '.join(zewn + iap)}) bez profilu zgodności: nie wiem, co jest sprzedawane",
                     "podaj --zgodnosc out/zgodnosc.yaml")
    return Wynik(30, "ok", f"płatności: {', '.join(sorted(plat)) or 'brak'}; biblioteki: {', '.join(zewn + iap) or 'brak'}")


def p31(ctx):
    if not (ctx.funkcje.get("tresci_uzytkownikow") or ctx.profil.get("tresci_uzytkownikow")):
        return Wynik(31, "ok", "brak treści użytkowników")
    tekst = "\n".join(ctx.src.values())
    brak = [n for n, wz in (("zgłaszanie", r"Zgłoś|zglos"), ("blokowanie", r"Zablokuj|zablokuj|blokuj"),
                            ("regulamin", r"[Rr]egulamin"), ("kontakt", r"kontakt")) if not re.search(wz, tekst)]
    if brak:
        return Wynik(31, "blad", f"treści użytkowników bez: {', '.join(brak)}", "regulamin przed publikacją, „Zgłoś” i „Zablokuj” przy treści, kontakt")
    return Wynik(31, "ok", "zgłaszanie, blokowanie, regulamin i kontakt w kodzie")


def p32(ctx):
    rv = ctx.public.get("runtimeVersion") or {}
    polityka = rv.get("policy") if isinstance(rv, dict) else f"stała {rv}"
    eas = _json(ctx.kat / "eas.json")
    kanal = ((eas.get("build") or {}).get("production") or {}).get("channel")
    if polityka != "fingerprint":
        return Wynik(32, "blad", f"runtimeVersion: {polityka} (aktualizacja JS może trafić do builda z innym kodem natywnym)",
                     "runtimeVersion { policy: 'fingerprint' } dla buildów sklepowych (szablon)")
    return Wynik(32, "?", f"runtimeVersion fingerprint, kanał {kanal or 'brak'}; przez EAS Update tylko poprawki",
                 "nowe funkcje w nowej wersji z opisem w notatkach dla recenzenta")


def p34(ctx):
    zle, dowody = [], []
    a = ctx.kat / "assets"
    ikona = a / "icon.png"
    if not ikona.exists():
        zle.append("brak assets/icon.png")
    else:
        i = ml.obraz(ikona)
        if (i["szer"], i["wys"]) != (1024, 1024) or i["alfa"]:
            zle.append(f"icon.png {i['szer']}×{i['wys']}{', z kanałem alfa' if i['alfa'] else ''} (iOS: 1024×1024 bez alfy)")
        else:
            dowody.append("ikona 1024 bez alfy")
    for n in ("android-icon-foreground.png", "android-icon-background.png", "android-icon-monochrome.png", "splash-icon.png"):
        if not (a / n).exists():
            zle.append(f"brak assets/{n}")
    if zle:
        return Wynik(34, "blad", "; ".join(zle), "`aplikacja.py ustaw` (ikony.cjs: z logo albo inicjałów, bez alfy)")
    return Wynik(34, "ok", ", ".join(dowody + ["ikona adaptacyjna (3 warstwy)", "ekran startowy"]))


def p35(ctx):
    obr = ctx.google_dir / "images"
    zle, dowody = [], []
    ikona, promo = obr / "icon.png", obr / "featureGraphic.png"
    if not ikona.exists():
        zle.append("brak out/sklep/google/pl-PL/images/icon.png")
    else:
        i = ml.obraz(ikona)
        if (i["szer"], i["wys"]) != (512, 512) or i["typ"] != "png" or i["bajty"] > 1_048_576:
            zle.append(f"icon.png {i['szer']}×{i['wys']} {i['typ']} {i['bajty'] // 1024} KB (512×512 PNG ≤ 1 MB)")
        else:
            dowody.append("ikona 512")
    kand = [p for p in (promo, obr / "featureGraphic.jpg") if p.exists()]
    if not kand:
        zle.append("brak grafiki promocyjnej images/featureGraphic.(png|jpg)")
    else:
        i = ml.obraz(kand[0])
        if (i["szer"], i["wys"]) != (1024, 500) or i["alfa"]:
            zle.append(f"{kand[0].name} {i['szer']}×{i['wys']}{', z alfą' if i['alfa'] else ''} (1024×500 bez alfy)")
        else:
            dowody.append("grafika 1024×500")
    if zle:
        return Wynik(35, "blad", "; ".join(zle), "`pakiet.py grafiki <app>`")
    return Wynik(35, "ok", ", ".join(dowody))


def _obrazy(kat: Path) -> list[Path]:
    return sorted(p for p in kat.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg")) if kat.exists() else []


def p36(ctx):
    zle, dowody = [], []
    apple = ctx.sklep / "apple" / "pl-PL"
    zestawy = {n: _obrazy(apple / n) for n in ZRZUTY_APPLE}
    if not (zestawy["ios-6.9"] or zestawy["ios-6.5"]):
        zle.append("brak zrzutów iPhone 6,9″ (1320×2868) ani 6,5″ w out/sklep/apple/pl-PL/")
    tablet = (ctx.public.get("ios") or {}).get("supportsTablet")
    if tablet and not zestawy["ipad-13"]:
        zle.append("aplikacja na iPada (supportsTablet), a brak zrzutów iPad 13″ (2064×2752)")
    for n, pliki in zestawy.items():
        if not pliki:
            continue
        if len(pliki) > 10:
            zle.append(f"{n}: {len(pliki)} zrzutów (najwyżej 10)")
        for p in pliki:
            i = ml.obraz(p)
            if (i["szer"], i["wys"]) not in ZRZUTY_APPLE[n] or i["alfa"]:
                zle.append(f"{n}/{p.name}: {i['szer']}×{i['wys']}{', alfa' if i['alfa'] else ''}")
        dowody.append(f"{n}: {len(pliki)}")
    telefon = _obrazy(ctx.google_dir / "images" / "phoneScreenshots")
    if not 2 <= len(telefon) <= 8:
        zle.append(f"Google: {len(telefon)} zrzutów telefonu (2–8)")
    for p in telefon:
        i = ml.obraz(p)
        dl, kr = max(i["szer"], i["wys"]), min(i["szer"], i["wys"])
        if not (320 <= kr and dl <= 3840 and dl <= 2 * kr) or i["alfa"]:
            zle.append(f"google/{p.name}: {i['szer']}×{i['wys']}{', alfa' if i['alfa'] else ''} (320–3840 px, proporcje ≤ 2:1)")
    if telefon:
        dowody.append(f"google telefon: {len(telefon)}")
    if zle:
        return Wynik(36, "blad", "; ".join(zle[:8]), "`pakiet.py zrzuty <app>` (kompozycja w dokładnych wymiarach, bez alfy)")
    return Wynik(36, "ok", ", ".join(dowody))


def _ocr(p: Path) -> str:
    try:
        r = subprocess.run(["tesseract", str(p), "-", "-l", "pol+eng"], capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def p37(ctx):
    meta = _json(ctx.sklep / "zrzuty.json")
    zle, dowody = [], []
    ios = [p for n in ZRZUTY_APPLE for p in _obrazy(ctx.sklep / "apple" / "pl-PL" / n)]
    for p in ios:
        tekst = _ocr(p)
        if OBCE_PLATFORMY.search(tekst):
            zle.append(f"{p.parent.name}/{p.name}: na zrzucie iOS widać „{OBCE_PLATFORMY.search(tekst).group(0)}”")
    kadry = meta.get("kadry") or []
    logowanie = [k.get("trasa") for k in kadry if re.search(r"logowan|login|zaloguj|rejestr|start-?screen|splash", str(k.get("trasa")), re.I)]
    if kadry and len(logowanie) * 2 >= len(kadry):
        zle.append(f"połowa kadrów to logowanie / ekran startowy: {', '.join(map(str, logowanie))}")
    if meta.get("zrodlo") == "web":
        dowody.append("źródło: wersja web (przybliżenie): przed wysłaniem przechwyć z buildu (android / ios)")
    dowody.append(f"kadry: {', '.join(str(k.get('trasa')) for k in kadry) or 'brak opisu (out/sklep/zrzuty.json)'}")
    if ios:
        dowody.append(f"OCR {len(ios)} zrzutów iOS")
    if zle:
        return Wynik(37, "blad", "; ".join(zle), "kadry z aplikacją w użyciu (korzyść na kadr); bez nazw innych platform na iOS")
    return Wynik(37, "?", "; ".join(dowody), "obejrzyj zrzuty: każdy pokazuje funkcję w użyciu")


def p39(ctx):
    zle = []
    for k, lim in LIMITY_APPLE.items():
        v = ctx.apple_pl.get(k)
        if isinstance(v, str) and len(v) > lim:
            zle.append(f"App Store {k}: {len(v)} > {lim}")
    for k, lim in LIMITY_GOOGLE.items():
        v = ctx.google.get(k)
        if v is not None and len(v) > lim:
            zle.append(f"Google {k}: {len(v)} > {lim}")
    nazwa = ctx.app.get("nazwa") or ""
    if len(nazwa) > 30:
        zle.append(f"nazwa aplikacji: {len(nazwa)} > 30")
    if not ctx.apple_pl and not ctx.google:
        return Wynik(39, "blad", "brak metadanych (store.config.json, out/sklep/google/pl-PL/)", "`pakiet.py szkic <app>`, teksty od Studia")
    if zle:
        return Wynik(39, "blad", "; ".join(zle), "skróć teksty (znaki, nie słowa)")
    return Wynik(39, "ok", f"App Store: {', '.join(f'{k} {len(v)}' for k, v in ctx.apple_pl.items() if isinstance(v, str) and k in LIMITY_APPLE)}; "
                           f"Google: {', '.join(f'{k[:-4]} {len(v)}' for k, v in ctx.google.items())}")


def p40(ctx):
    slowa = ctx.apple_pl.get("keywords")
    if not slowa:
        return Wynik(40, "blad", "brak słów kluczowych App Store (apple.info.pl-PL.keywords)", "`pakiet.py szkic`, słowa od Studia")
    lista = slowa if isinstance(slowa, list) else [s.strip() for s in str(slowa).split(",")]
    bajty = len(",".join(lista).encode("utf-8"))
    zle = []
    if bajty > 100:
        zle.append(f"{bajty} bajtów > 100 (polska litera z ogonkiem to 2 bajty)")
    krotkie = [s for s in lista if len(s) <= 2]
    if krotkie:
        zle.append(f"za krótkie: {', '.join(krotkie)}")
    zakazane = {_u(w) for w in re.findall(r"\w{3,}", (ctx.app.get("nazwa") or "") + " " + re.sub(
        r"\b(sp|z|o|s\.a)\b", "", ctx.firma.get("nazwa") or "", flags=re.I))}
    powt = [s for s in lista if _u(s) in zakazane]
    if powt:
        zle.append(f"nazwa aplikacji lub firmy w słowach (już się liczy): {', '.join(powt)}")
    obce = [s for s in lista if any(k == _u(s) or k in _u(s).split() for k in KONKURENCJA)]
    if obce:
        zle.append(f"nazwy innych firm lub platform: {', '.join(obce)}")
    if zle:
        return Wynik(40, "blad", "; ".join(zle), "słowa po przecinku bez spacji, bez nazwy i konkurencji, ≤ 100 bajtów")
    return Wynik(40, "ok", f"{len(lista)} słów, {bajty} bajtów")


def p41(ctx):
    zle = []
    for k, t in ctx.metadane_teksty().items():
        if k.endswith(("Url", "keywords")):
            continue
        tytul = k in ("apple.title", "apple.subtitle", "google.title.txt", "google.short_description.txt")
        if k.startswith("apple.") and OBCE_PLATFORMY.search(t):
            zle.append(f"{k}: „{OBCE_PLATFORMY.search(t).group(0)}” na karcie iOS")
        mocne = [m.group(0) for m in ZAKAZANE.finditer(t)
                 if tytul or re.search(r"#\s?1|nr\s?1|najlepsz|darmow|za darmo|rabat|-\s?\d+\s?%", m.group(0), re.I)]
        if mocne:
            zle.append(f"{k}: " + ", ".join(f"„{x}”" for x in dict.fromkeys(mocne)))
        if EMOJI.search(t) and (tytul or len(EMOJI.findall(t)) > 3):
            zle.append(f"{k}: emoji")
        duze = [w for w in re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ]{4,}\b", t) if w not in SKROTY]
        if duze and (tytul or len(duze) > 2):
            zle.append(f"{k}: WIELKIE LITERY ({', '.join(duze[:3])})")
    if zle:
        return Wynik(41, "blad", "; ".join(zle[:8]), "opis korzyści bez superlatyw, cen, emoji i nazw innych platform")
    return Wynik(41, "ok", f"{len(ctx.metadane_teksty())} pól metadanych bez zakazanych słów")


def p42(ctx):
    zle = []
    if not ctx.apple_pl:
        zle.append("brak apple.info.pl-PL w store.config.json")
    elif not ctx.apple_pl.get("title"):
        zle.append("brak nazwy App Store pl-PL")
    if not ctx.google.get("title.txt"):
        zle.append("brak karty Google pl-PL (out/sklep/google/pl-PL/title.txt)")
    region = (ctx.public.get("ios") or {}).get("infoPlist", {}).get("CFBundleDevelopmentRegion")
    if region != "pl" and "pl" not in (ctx.public.get("locales") or {}):
        zle.append("aplikacja bez polskiej lokalizacji (CFBundleDevelopmentRegion / locales.pl)")
    if zle:
        return Wynik(42, "blad", "; ".join(zle), "`pakiet.py szkic <app>`")
    return Wynik(42, "ok", f"pl-PL: „{ctx.apple_pl.get('title')}” / „{ctx.google.get('title.txt')}”")


def p44(ctx):
    notatki = str(ctx.review.get("notes") or "")
    if not notatki:
        return Wynik(44, "blad", "brak apple.review.notes w store.config.json", "notatki po angielsku: funkcje, ścieżka testu, konto demo")
    zle = []
    if len(notatki.encode()) > 4000:
        zle.append(f"{len(notatki.encode())} bajtów > 4000")
    ang, pol = len(ANGIELSKIE.findall(notatki)), len(POLSKIE_SLOWA.findall(notatki))
    if ang < 8 or pol * 3 > ang:          # polskie nazwy przycisków w nawiasach są w porządku, polskie zdania nie
        zle.append(f"nie po angielsku (słowa angielskie {ang}, polskie {pol})")
    if not re.search(r"(^|\n)\s*(\d+[.)]|-|\*)\s", notatki):
        zle.append("bez kroków ścieżki testu (lista)")
    if len(notatki) < 120:
        zle.append("za ogólne (Apple 2.3.1(a): ogólne opisy są odrzucane)")
    if zle:
        return Wynik(44, "blad", "; ".join(zle), "`pakiet.py szkic` daje szablon notatek; uzupełnij ścieżkę testu konkretnej wersji")
    return Wynik(44, "?", f"notatki: {len(notatki)} znaków, po angielsku, z krokami", "przeczytaj: ścieżka pasuje do tej wersji")


SPRAWDZENIA = {3: p3, 4: p4, 5: p5, 6: p6, 7: p7, 8: p8, 9: p9, 10: p10, 11: p11, 12: p12, 13: p13, 14: p14, 15: p15,
               16: p16, 17: p17, 18: p18, 19: p19, 20: p20, 21: p21, 22: p22, 23: p23, 24: p24, 25: p25, 26: p26, 27: p27,
               28: p28, 29: p29, 30: p30, 31: p31, 32: p32, 34: p34, 35: p35, 36: p36, 37: p37, 39: p39, 40: p40, 41: p41,
               42: p42, 44: p44}
RECZNE_PODPOWIEDZI = {
    1: "App Store Connect → Użytkownicy: agent jako członek zespołu; Play Console → Użytkownicy i uprawnienia",
    2: "App Store Connect → Business → status przedsiębiorcy (DSA): adres, telefon, e-mail widoczne na karcie",
    33: "TestFlight na iPhonie (i iPadzie przy tablecie), raport przedpremierowy Google, sieć tylko IPv6 (Apple 2.5.5)",
    38: "Play Console → Karta sklepu: oznaczenie grafik wygenerowanych z pomocą AI",
    43: "Apple: kwestionariusz kategorii wiekowej; Google: IARC, grupa docelowa, reklamy, funkcje finansowe, Data safety",
}


# ------------------------------------------------------------------ uruchomienie

def znajdz_buildy(kat: Path, aab=None, ipa=None, apk=None) -> dict[str, Build]:
    out = {}
    katalog = kat / "out" / "build"
    for rodzaj, jawny in (("aab", aab), ("ipa", ipa), ("apk", apk)):
        p = Path(jawny) if jawny else max(katalog.glob(f"*.{rodzaj}"), key=lambda x: x.stat().st_mtime, default=None) \
            if katalog.exists() else None
        if p:
            out[rodzaj] = czytaj_build(p)
    return out


def wczytaj_profil(kat: Path, sciezka: str | None) -> dict:
    for p in [Path(sciezka)] if sciezka else [kat / "out" / "zgodnosc.yaml", kat.parent / "zgodnosc.yaml"]:
        if p.exists():
            return zgodnosc.wczytaj(p)
    return {}


def bez_komentarzy(kod: str) -> str:
    """Kod TS/JS bez komentarzy blokowych i liniowych (adresy `https://` zostają)."""
    kod = re.sub(r"/\*.*?\*/", " ", kod, flags=re.S)
    return re.sub(r"(?m)(^|[^:\\'\"])//.*$", r"\1", kod)


def punkty_wyuczone(ctx: Kontekst) -> list[dict]:
    """Kontrole dopisane przez `odrzucenie.py naucz` (wzorzec w kodzie i / albo metadanych): błąd blokuje wysłanie."""
    try:
        import odrzucenie
        kontrole = odrzucenie.wyuczone()
    except Exception as e:  # noqa: BLE001
        return [{"nr": "N?", "grupa": "N", "tryb": "auto", "tytul": "kontrole wyuczone", "podstawa": "", "stan": "?", "znak": "?",
                 "dowod": f"nie wczytano _nauka/odrzucenia.yaml: {e}", "poprawka": "popraw plik nauki"}]
    out = []
    for k in kontrole:
        if not k.get("wzorzec"):
            continue
        wz = re.compile(k["wzorzec"], re.I)
        zrodla = {}
        if k.get("gdzie", "oba") in ("src", "oba"):
            zrodla.update({n: bez_komentarzy(t) for n, t in ctx.src.items()})     # komentarze nie trafiają do aplikacji
        if k.get("gdzie", "oba") in ("metadane", "oba"):
            zrodla.update(ctx.metadane_teksty())
        trafienia = [f"{n}: {m.group(0)}" for n, t in zrodla.items() for m in [wz.search(t)] if m]
        out.append({"nr": k["id"], "grupa": "N", "tryb": "auto", "tytul": k["opis"], "podstawa": f"{k['wytyczna']} (odrzucenie {k['data']})",
                    "stan": "blad" if trafienia else "ok", "znak": "✗" if trafienia else "✓",
                    "dowod": "; ".join(trafienia[:5]) if trafienia else f"brak /{k['wzorzec']}/", "poprawka": k["poprawka"]})
    return out


def sprawdz(ctx: Kontekst) -> dict:
    wyniki = []
    for nr, grupa, tryb, tytul, podstawa in PUNKTY:
        if nr in SPRAWDZENIA:
            try:
                w = SPRAWDZENIA[nr](ctx)
            except Exception as e:  # noqa: BLE001 (jeden punkt nie wywraca listy)
                w = Wynik(nr, "?", f"sprawdzenie nie powiodło się: {e.__class__.__name__}: {e}", "sprawdź ręcznie i zgłoś błąd skryptu")
        else:
            w = Wynik(nr, "recznie", RECZNE_PODPOWIEDZI.get(nr, ""))
        potw = ctx.potw.get(str(nr))
        if potw and w.stan in ("?", "recznie"):
            w = Wynik(nr, "ok", f"potwierdził {potw.get('kto')} {potw.get('kiedy', '')}: {potw.get('uwaga', '')} (dowód: {w.dowod})")
        wyniki.append({"nr": nr, "grupa": grupa, "tryb": tryb, "tytul": tytul, "podstawa": podstawa, "stan": w.stan,
                       "znak": ZNAKI[w.stan], "dowod": w.dowod, "poprawka": w.poprawka})
    wyniki += punkty_wyuczone(ctx)
    licz = {s: sum(1 for w in wyniki if w["stan"] == s) for s in ZNAKI}
    blokujace = [w for w in wyniki if w["stan"] == "blad" and w["tryb"] == "auto"]
    return {"aplikacja": str(ctx.kat), "data": ml.DZIS.isoformat(), "konfiguracja": ctx.cfg.get("zrodlo"),
            "buildy": {k: b.sciezka.name for k, b in ctx.builds.items()}, "wyniki": wyniki, "liczby": licz,
            "blokujace": [w["nr"] for w in blokujace],
            "gotowe_do_wyslania": licz["ok"] == len(wyniki),
            "podsumowanie": f"{licz['ok']} ✓, {licz['blad']} ✗ ({len(blokujace)} blokuje), {licz['?']} ? do oceny, "
                            f"{licz['recznie']} ☐ dla właściciela"}


def raport_md(r: dict) -> str:
    l = [f"# Lista kontrolna sklepów: {Path(r['aplikacja']).name}", "",
         f"{r['data']} · {r['podsumowanie']} · konfiguracja: {r['konfiguracja']} · buildy: "
         f"{', '.join(f'{k} {v}' for k, v in r['buildy'].items()) or 'brak (punkty buildów sprawdzi --aab/--ipa)'}", ""]
    if r["blokujace"]:
        l += [f"**Blokuje wysłanie:** punkty {', '.join(map(str, r['blokujace']))}.", ""]
    for g, nazwa in GRUPY.items():
        if not any(w["grupa"] == g for w in r["wyniki"]):
            continue
        l += [f"## {g}. {nazwa}", "", "| # | | Sprawdzenie | Tryb | Dowód | Poprawka | Podstawa |", "|---|---|---|---|---|---|---|"]
        l += [f"| {w['nr']} | {w['znak']} | {ml.md_komorka(w['tytul'])} | {w['tryb']} | {ml.md_komorka(w['dowod'])} | "
              f"{ml.md_komorka(w['poprawka'])} | {ml.md_komorka(w['podstawa'])} |" for w in r["wyniki"] if w["grupa"] == g]
        l.append("")
    l.append("✓ zaliczone · ✗ błąd · ? do oceny człowieka · ☐ punkt dla właściciela w konsoli sklepu. "
             "Potwierdzenie: `sklep_check.py potwierdz <app> <nr> --kto … --uwaga …`.")
    return "\n".join(l) + "\n"


def potwierdz(kat: Path, nr: int, kto: str, uwaga: str) -> dict:
    tryb = next(p[2] for p in PUNKTY if p[0] == nr)
    if tryb == "auto":
        raise SystemExit(f"punkt {nr} jest automatyczny: poprawia się go w aplikacji, nie potwierdza")
    if len(uwaga.strip()) < 10:
        raise SystemExit("uwaga: co sprawdzono i gdzie (co najmniej 10 znaków)")
    p = kat / "out" / "sklep" / "potwierdzenia.json"
    dane = _json(p)
    dane[str(nr)] = {"kto": kto, "kiedy": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "uwaga": uwaga.strip()}
    ml.zapisz(p, json.dumps(dane, ensure_ascii=False, indent=2))
    return dane[str(nr)]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["potwierdz"]:
        ap = argparse.ArgumentParser(prog="sklep_check.py potwierdz")
        ap.add_argument("app")
        ap.add_argument("nr", type=int, choices=range(1, 45), metavar="NR")
        ap.add_argument("--kto", required=True)
        ap.add_argument("--uwaga", required=True)
        a = ap.parse_args(argv[1:])
        print(json.dumps(potwierdz(Path(a.app).resolve(), a.nr, a.kto, a.uwaga), ensure_ascii=False))
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("app")
    ap.add_argument("--aab")
    ap.add_argument("--ipa")
    ap.add_argument("--apk")
    ap.add_argument("--zgodnosc")
    ap.add_argument("--bez-sieci", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    kat = Path(a.app).resolve()
    if not (kat / "jarvo.app.json").exists():
        print(f"✗ {kat}: brak jarvo.app.json (to nie aplikacja z szablonu JARVO)", file=sys.stderr)
        return 2
    t0 = time.time()
    try:
        ctx = Kontekst(kat, siec=not a.bez_sieci, builds=znajdz_buildy(kat, a.aab, a.ipa, a.apk),
                       profil=wczytaj_profil(kat, a.zgodnosc), cfg=konfiguracja(kat))
    except (RuntimeError, ValueError, zipfile.BadZipFile, OSError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    r = sprawdz(ctx)
    r["czas_s"] = round(time.time() - t0, 1)
    ml.zapisz(kat / "out" / "sklep" / "check.json", json.dumps(r, ensure_ascii=False, indent=2))
    ml.zapisz(kat / "out" / "sklep" / "CHECK.md", raport_md(r))
    try:
        import pakiet
        pakiet.galeria(kat)                                    # podsumowanie także w galerii pakietu (podgląd HQ)
    except Exception as e:  # noqa: BLE001 (galeria to dodatek, lista kontrolna ma wynik)
        print(f"(galeria: {e})", file=sys.stderr)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else raport_md(r))
    print(f"{r['podsumowanie']} · {r['czas_s']} s · out/sklep/CHECK.md", file=sys.stderr)
    return 1 if r["blokujace"] else 0


if __name__ == "__main__":
    sys.exit(main())
