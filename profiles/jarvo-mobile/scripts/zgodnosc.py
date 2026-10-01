#!/usr/bin/env python3
"""Profil zgodności aplikacji: decyzje z planu (logowanie, płatności, treści, AI, uprawnienia…) → wymagania sklepów
z numerami wytycznych i konfiguracja szablonu JARVO (moduły, wtyczki z polskimi opisami uprawnień, blokady uprawnień).

    zgodnosc.py szablon > out/zgodnosc.yaml
    zgodnosc.py sprawdz out/zgodnosc.yaml [--json] [--md out/ZGODNOSC.md]

Po co: większość odrzuceń w App Store i Google Play wynika z decyzji podjętych pierwszego dnia (logowanie przez Google
bez Apple, brak usuwania konta, płatność za treści cyfrowe poza sklepem, ogólnikowy opis uprawnienia). Profil
zgodności wypełniasz w kroku „Plan” i z niego `aplikacja.py nowa/ustaw` buduje aplikację, a `sklep_check.py` wie,
które punkty listy kontrolnej obowiązują.

Kod wyjścia: 0 = profil poprawny, 1 = błędy (np. uprawnienie bez polskiego powodu).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LOGOWANIE = {"email", "telefon", "google", "facebook", "apple", "firmowe"}
PLATNOSCI = {"fizyczne", "uslugi", "cyfrowe", "subskrypcja", "napiwki"}
BRANZE = {"zwykla", "zdrowie", "finanse", "hazard", "leki", "inne-regulowane"}
POWOD_MIN = 40
OGOLNIKI = re.compile(r"potrzebuje dost[eę]pu|requires access|needs access|\$\(PRODUCT_NAME\)|allow .* to access|"
                      r"w celu działania aplikacji|do działania aplikacji|aby aplikacja działała", re.I)

# uprawnienie → (moduł Expo, wtyczka, klucz wtyczki z opisem, klucz Info.plist iOS, dodatkowe propsy wtyczki,
#                uprawnienia Androida do odblokowania)
UPRAWNIENIA: dict[str, dict] = {
    "aparat": {"modul": "expo-camera", "wtyczka": "expo-camera", "prop": "cameraPermission",
               "ios": "NSCameraUsageDescription", "extra": {"recordAudioAndroid": False}},
    "zdjecia": {"modul": "expo-image-picker", "wtyczka": "expo-image-picker", "prop": "photosPermission",
                "ios": "NSPhotoLibraryUsageDescription", "extra": {"microphonePermission": False}},
    "lokalizacja": {"modul": "expo-location", "wtyczka": "expo-location", "prop": "locationWhenInUsePermission",
                    "ios": "NSLocationWhenInUseUsageDescription", "extra": {}},
    "lokalizacja-w-tle": {"modul": "expo-location", "wtyczka": "expo-location",
                          "prop": "locationAlwaysAndWhenInUsePermission",
                          "ios": "NSLocationAlwaysAndWhenInUseUsageDescription",
                          "extra": {"isAndroidBackgroundLocationEnabled": True},
                          "odblokuj": ["android.permission.ACCESS_BACKGROUND_LOCATION"]},
    "powiadomienia": {"modul": "expo-notifications", "wtyczka": "expo-notifications", "prop": None, "ios": None, "extra": {}},
    "kontakty": {"modul": "expo-contacts", "wtyczka": "expo-contacts", "prop": "contactsPermission",
                 "ios": "NSContactsUsageDescription", "extra": {}},
    "kalendarz": {"modul": "expo-calendar", "wtyczka": "expo-calendar", "prop": "calendarPermission",
                  "ios": "NSCalendarsFullAccessUsageDescription", "extra": {}},
    "mikrofon": {"modul": "expo-audio", "wtyczka": "expo-audio", "prop": "microphonePermission",
                 "ios": "NSMicrophoneUsageDescription", "extra": {}, "odblokuj": ["android.permission.RECORD_AUDIO"]},
    "biometria": {"modul": "expo-local-authentication", "wtyczka": "expo-local-authentication", "prop": "faceIDPermission",
                  "ios": "NSFaceIDUsageDescription", "extra": {}},
    "sledzenie": {"modul": "expo-tracking-transparency", "wtyczka": "expo-tracking-transparency",
                  "prop": "userTrackingPermission", "ios": "NSUserTrackingUsageDescription", "extra": {},
                  "odblokuj": ["com.google.android.gms.permission.AD_ID"]},
}
# blokowane zawsze, chyba że uprawnienie z profilu je odblokuje (Google Play: deklaracje i odrzucenia za zbędne uprawnienia)
ZAWSZE_BLOKUJ = ["android.permission.RECORD_AUDIO", "android.permission.SYSTEM_ALERT_WINDOW",
                 "android.permission.READ_EXTERNAL_STORAGE", "android.permission.WRITE_EXTERNAL_STORAGE",
                 "android.permission.ACCESS_BACKGROUND_LOCATION", "android.permission.READ_MEDIA_IMAGES",
                 "android.permission.READ_MEDIA_VIDEO", "android.permission.READ_MEDIA_AUDIO",
                 "android.permission.QUERY_ALL_PACKAGES", "com.google.android.gms.permission.AD_ID"]

SZABLON = """# Profil zgodności aplikacji (zgodnosc.py sprawdz). Wypełnij w kroku „Plan”; z niego powstaje aplikacja i lista
# kontrolna sklepów. Każda decyzja tutaj to mniej odrzuceń później.
logowanie: []              # email | telefon | google | facebook | apple | firmowe; puste = aplikacja bez kont
platnosci: []              # fizyczne (towary) | uslugi (wizyty, dostawy) | cyfrowe (treści, odblokowanie funkcji) | subskrypcja | napiwki
tresci_uzytkownikow: false # klienci publikują coś widocznego dla innych (opinie, zdjęcia, czat)
ai: false                  # dane klienta trafiają do zewnętrznego modelu AI
uprawnienia: []            # aparat | zdjecia | lokalizacja | lokalizacja-w-tle | powiadomienia | kontakty | kalendarz | mikrofon | biometria | sledzenie
powody: {}                 # uprawnienie: "po polsku, z przykładem, ≥ 40 znaków" (trafia do okna systemowego)
#  aparat: "Aparat służy do zeskanowania kodu QR z karty stałego klienta przy kasie."
reklamy: false             # reklamy w aplikacji (SDK reklamowe)
dzieci: false              # aplikacja kierowana także do dzieci
tablet: false              # wersja na iPada (wtedy także zrzuty iPad 13″)
branza: zwykla             # zwykla | zdrowie | finanse | hazard | leki | inne-regulowane
konto_google: organizacja  # organizacja (numer D-U-N-S) | osobiste (test zamknięty: 12 testerów przez 14 dni)
"""


def _lista(p: dict, klucz: str, dozwolone: set[str], bledy: list[str]) -> list[str]:
    v = p.get(klucz) or []
    if isinstance(v, str):
        v = [v]
    zle = [x for x in v if x not in dozwolone]
    if zle:
        bledy.append(f"{klucz}: nieznane {', '.join(map(str, zle))} (dozwolone: {', '.join(sorted(dozwolone))})")
    return [x for x in v if x in dozwolone]


def ocen(p: dict) -> dict:
    """Profil → {bledy, ostrzezenia, wymagania, konfiguracja}. Czysta funkcja (testy, aplikacja.py)."""
    bledy: list[str] = []
    ostrz: list[str] = []
    logowanie = _lista(p, "logowanie", LOGOWANIE, bledy)
    platnosci = _lista(p, "platnosci", PLATNOSCI, bledy)
    uprawnienia = _lista(p, "uprawnienia", set(UPRAWNIENIA), bledy)
    branza = p.get("branza", "zwykla")
    if branza not in BRANZE:
        bledy.append(f"branza: nieznana {branza!r}")
    powody = {k: str(v).strip() for k, v in (p.get("powody") or {}).items()}
    konta = bool(logowanie)
    W: list[dict] = []

    def wym(id_, opis, podstawa, jak, w_szablonie=False):
        W.append({"id": id_, "opis": opis, "podstawa": podstawa, "jak": jak, "w_szablonie": w_szablonie})

    wym("prywatnosc", "polityka prywatności pod stałym adresem, link w aplikacji i w obu sklepach",
        "Apple 5.1.1(i), Google Play Data safety", "ekran Prywatność + `firma.prywatnosc_url`", True)
    wym("kontakt", "kontakt i strona wsparcia z e-mailem albo telefonem", "App Review (Support URL)", "ekran Kontakt", True)
    wym("stany", "żadnego pustego ani białego ekranu: ładowanie, pusto, błąd, brak sieci", "Apple 2.1, Google Play: niedziałająca aplikacja",
        "`Stan.tsx`, `BrakSieci.tsx`, `ErrorBoundary`", True)
    wym("szyfrowanie", "deklaracja eksportu szyfrowania", "App Store Connect: export compliance",
        "`ios.config.usesNonExemptEncryption: false`", True)
    wym("dsa", "status przedsiębiorcy DSA zweryfikowany w App Store Connect (dane kontaktowe widoczne w UE)",
        "Digital Services Act", "właściciel w App Store Connect")
    if konta:
        wym("usuwanie-konta", "usuwanie konta w aplikacji (trwałe, nie dezaktywacja) i link do usuwania w sieci",
            "Apple 5.1.1(v), Google Play: usuwanie konta", "ekran Usuń konto + `lib/konto.ts` (JARVO-TODO do podłączenia) + "
            "`firma.usuwanie_konta_url` (strona robi Web)", True)
        wym("konto-demo", "konto demo dla recenzentów (bez SMS i 2FA), działające w dniu recenzji", "Apple 2.1, Google Play: dane logowania",
            "`store.config.json` i Play Console (pakiet do sklepów)")
        wym("bez-wymuszania", "funkcje niewymagające konta (katalog, informacje) dostępne bez logowania", "Apple 5.1.1(v)",
            "plan ekranów")
    if {"google", "facebook"} & set(logowanie) and "apple" not in logowanie:
        logowanie.append("apple")
        wym("sign-in-with-apple", "logowanie przez Google lub Facebooka wymaga też Zaloguj się przez Apple na iOS",
            "Apple 4.8", "moduł `expo-apple-authentication` (dodany automatycznie)")
    if "cyfrowe" in platnosci or "subskrypcja" in platnosci:
        wym("iap", "treści cyfrowe i subskrypcje tylko przez zakupy w aplikacji (Apple, Google)", "Apple 3.1.1, Google Play: płatności",
            "RevenueCat (`react-native-purchases`), build deweloperski: Expo Go tego nie obsłuży")
        ostrz.append("zakupy w aplikacji wymagają builda deweloperskiego (podgląd przez TestFlight albo APK, nie Expo Go)")
    if {"fizyczne", "uslugi"} & set(platnosci):
        wym("platnosci-zewnetrzne", "towary fizyczne i usługi płatne poza systemem Apple (Stripe, Przelewy24, PayU, BLIK)",
            "Apple 3.1.3(e)", "Stripe PaymentSheet albo płatność na stronie otwarta w przeglądarce")
    if "napiwki" in platnosci:
        ostrz.append("napiwki dla twórców treści cyfrowych podlegają zakupom w aplikacji (Apple 3.1.1); napiwki za usługę fizyczną nie")
    if p.get("tresci_uzytkownikow"):
        wym("ugc", "treści użytkowników: regulamin zaakceptowany przed publikacją, filtr, zgłaszanie, blokowanie, kontakt",
            "Apple 1.2, Google Play: treści użytkowników", "ekran regulaminu + przycisk „Zgłoś” i „Zablokuj” przy każdej treści")
    if p.get("ai"):
        wym("ai", "zgoda przed wysłaniem danych do zewnętrznego AI i zgłaszanie obraźliwych odpowiedzi",
            "Apple 5.1.2(i), Google Play: treści generowane przez AI", "ekran zgody przy pierwszym użyciu + przycisk „Zgłoś odpowiedź”")
    if p.get("reklamy"):
        wym("reklamy", "deklaracja reklam w Play Console; śledzenie tylko po zgodzie ATT", "Apple 5.1.2, Google Play: reklamy",
            "`sledzenie` w uprawnieniach, gdy SDK reklam śledzi")
    if p.get("dzieci"):
        wym("dzieci", "aplikacja dla dzieci: bez zewnętrznej analityki i reklam, zasady Families i kategorii Dzieci",
            "Apple 1.3, 5.1.4; Google Play Families", "przegląd SDK przed dodaniem")
        ostrz.append("aplikacja dla dzieci: każde SDK analityczne i reklamowe sprawdzić pod kątem Families")
    if branza != "zwykla":
        wym("regulowana", "branża regulowana: wysyła podmiot prawny (konto organizacji), dokumenty w notatkach dla recenzenta",
            "Apple 5.6.2, App Review („Submitted by incorrect entity”)", "konto Apple jako organizacja")
    if p.get("konto_google", "organizacja") == "osobiste":
        wym("test-zamkniety", "nowe konto osobiste Google: test zamknięty z ≥ 12 testerami przez 14 dni przed produkcją",
            "Google Play (answer 14151465)", "plan testerów od dnia pierwszego builda")
    if p.get("tablet"):
        wym("ipad", "wersja na iPada: działające układy i zrzuty iPad 13″ (2064×2752)", "Apple 2.4.1, zrzuty App Store",
            "`tablet: true` w aplikacji")

    paczki, wtyczki, info_plist, odblokuj = [], {}, {}, set()
    for u in uprawnienia:
        d = UPRAWNIENIA[u]
        powod = powody.get(u, "")
        if d["ios"]:
            if not powod:
                bledy.append(f"uprawnienie {u}: brak powodu w `powody.{u}` (trafia do okna systemowego, po polsku)")
            elif len(powod) < POWOD_MIN or OGOLNIKI.search(powod):
                bledy.append(f"uprawnienie {u}: powód ogólnikowy albo krótszy niż {POWOD_MIN} znaków (Apple 5.1.1(ii)): {powod!r}")
            info_plist[d["ios"]] = powod
        if d["modul"] not in paczki:
            paczki.append(d["modul"])
        props = wtyczki.setdefault(d["wtyczka"], {})
        if d["prop"]:
            props[d["prop"]] = powod
        props.update(d["extra"])
        odblokuj.update(d.get("odblokuj", []))
        wym(f"uprawnienie-{u}", f"uprawnienie {u}: prośba w momencie użycia, z wyjaśnieniem; odmowa nie blokuje aplikacji",
            "Apple 5.1.1, 5.1.2(i); Google Play: uprawnienia", f"`{d['modul']}` + polski opis w `uprawnienia_ios` i `locales/pl.json`")
    if "lokalizacja-w-tle" in uprawnienia:
        ostrz.append("lokalizacja w tle: deklaracja w Play Console z filmem, mocne uzasadnienie dla Apple; zwykle wystarcza lokalizacja w użyciu")
    if "kontakty" in uprawnienia:
        ostrz.append("kontakty: Google Play od 2026 woli selektor kontaktów zamiast READ_CONTACTS; uzasadnij pełny dostęp")
    if "apple" in logowanie:
        paczki.append("expo-apple-authentication")
        wtyczki.setdefault("expo-apple-authentication", {})
    blokuj = [x for x in ZAWSZE_BLOKUJ if x not in odblokuj]
    return {
        "bledy": bledy, "ostrzezenia": ostrz, "wymagania": W,
        "konfiguracja": {
            "funkcje": {"konta": konta, "tresci_uzytkownikow": bool(p.get("tresci_uzytkownikow")), "ai": bool(p.get("ai"))},
            "tablet": bool(p.get("tablet")),
            "paczki": paczki,
            "wtyczki": [[n, pr] if pr else n for n, pr in wtyczki.items()],
            "uprawnienia_ios": info_plist,
            "zablokowane_uprawnienia_android": blokuj,
            "logowanie": logowanie, "platnosci": platnosci,
        },
    }


def raport_md(w: dict) -> str:
    l = ["# Profil zgodności aplikacji", "", "Wymagania sklepów wynikające z decyzji w planie. ✓ = szablon JARVO ma to od początku;",
         "• = do zrobienia w aplikacji albo w konsoli sklepu.", "", "| | Wymaganie | Podstawa | Jak |", "|---|---|---|---|"]
    for x in w["wymagania"]:
        l.append(f"| {'✓' if x['w_szablonie'] else '•'} | {x['opis']} | {x['podstawa']} | {x['jak']} |")
    if w["ostrzezenia"]:
        l += ["", "## Uwaga"] + [f"- {o}" for o in w["ostrzezenia"]]
    if w["bledy"]:
        l += ["", "## Błędy profilu (do poprawy przed budową)"] + [f"- {b}" for b in w["bledy"]]
    k = w["konfiguracja"]
    l += ["", "## Konfiguracja aplikacji", "", f"- konta: {'tak' if k['funkcje']['konta'] else 'nie'}",
          f"- moduły: {', '.join(k['paczki']) or 'tylko szablon'}",
          f"- zablokowane uprawnienia Androida: {len(k['zablokowane_uprawnienia_android'])}", ""]
    return "\n".join(l)


def wczytaj(sciezka: str | Path) -> dict:
    import yaml
    return yaml.safe_load(Path(sciezka).read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("szablon")
    s = sub.add_parser("sprawdz")
    s.add_argument("profil")
    s.add_argument("--json", action="store_true")
    s.add_argument("--md", help="zapisz raport (np. out/ZGODNOSC.md)")
    args = ap.parse_args(argv)
    if args.cmd == "szablon":
        print(SZABLON, end="")
        return 0
    w = ocen(wczytaj(args.profil))
    md = raport_md(w)
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(md, encoding="utf-8")
    print(json.dumps(w, ensure_ascii=False, indent=2) if args.json else md)
    return 1 if w["bledy"] else 0


if __name__ == "__main__":
    sys.exit(main())
