"""Przeglądarka Jarva natywnie (docs/NATYWNIE.md J01, J07, J11): program, flagi, preferencje profilu i pobrane pliki.

Polityk maszynowych (HKLM, /etc/opt/chrome/policies) nie używamy, bo wymagają admina i działałyby też na Chrome
właściciela. Zamiast nich:
  - flagi startu: bez synchronizacji, rozszerzeń, aplikacji domyślnych, Cast (MediaRouter szuka urządzeń w sieci
    lokalnej po UDP, poza proxy), QUIC, pingów; proxy filtrujące dla całego ruchu (także pętli zwrotnej),
    WebRTC bez UDP poza proxy, odmowa każdej prośby o uprawnienie (`--deny-permission-prompts`);
  - preferencje profilu (`Default/Preferences`, zapisywane przed każdym startem): bez menedżera haseł,
    autouzupełniania adresów i kart, logowania do przeglądarki, tłumacza; pobrane pliki do osobnego katalogu,
    bez pytania; Bezpieczne przeglądanie włączone (ochrony przed phishingiem nie wyłączamy); WebRTC drugi raz
    w preferencjach (ta sama zasada co flaga: UDP tylko przez proxy, czyli wcale);
  - przez CDP (sterownik_cdp.py): odmowa uprawnień (kamera, mikrofon, schowek, przechwytywanie ekranu, położenie,
    powiadomienia…), pobrania pod nazwą GUID z odrzuceniem typów wykonywalnych, blokada file://, przechwycenie
    wyboru pliku (w trybie w tle), strona testowa przez Fetch.fulfillRequest.
Bez `--disable-popup-blocking` i bez wyłączania ochrony przed phishingiem (Playwright robi jedno i drugie).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")
EKRAN = (1440, 900)
NARZEDZIE = "chrome-komputer"                       # wpis manifestu (vendor/natywne.yaml, kiedy: przy-uzyciu)
ZMIENNA_PROGRAMU = "JARVO_KOMPUTER_CHROME"          # env wpisu manifestu: ścieżka programu w katalogu narzędzia
ZMIENNA_PROBY = "JARVO_KOMPUTER_CHROME_PROBA"       # tylko próby i testy: inna przeglądarka (np. chrome-headless-shell)

# Rozszerzenia plików, których Komputer nie zapisuje (programy, skrypty, instalatory, obrazy dysków, skróty).
WYKONYWALNE = frozenset("""
exe msi msix msixbundle appx appxbundle bat cmd com scr pif cpl vbs vbe js jse wsf wsh wsc ps1 psm1 psd1 ps1xml
hta lnk url reg jar dll sys drv ocx inf application appref-ms gadget chm msc msp mst iso img vhd vhdx
app dmg pkg mpkg command tool scpt applescript workflow terminal kext prefpane dylib
sh bash zsh ksh csh fish run bin deb rpm appimage desktop snap flatpakref so elf
py pyw pyc pyz pl rb php lua
""".split())


def program(env: dict | None = None, narzedzia: dict | None = None) -> str | None:
    """Program przeglądarki: zmienna próby, potem zmienna z wpisu manifestu (narzedzia.json albo ustawienia
    Komputera). None, gdy przeglądarki nie zainstalowano."""
    env = os.environ if env is None else env
    for klucz in (ZMIENNA_PROBY, ZMIENNA_PROGRAMU):
        p = str(env.get(klucz) or "").strip()
        if p:
            return p
    wpis = (narzedzia or {}).get(NARZEDZIE) or {}
    p = str((wpis.get("env") or {}).get(ZMIENNA_PROGRAMU) or "").strip()
    return p or None


def flagi(*, profil: Path, port_proxy: int | None, okno: bool, ekran: tuple[int, int] = EKRAN,
          bez_piaskownicy: bool = False, jezyk: str = "pl") -> list[str]:
    """Argumenty startu przeglądarki Jarva (bez --remote-debugging-pipe, który dokłada cdp.Przegladarka)."""
    f = [f"--user-data-dir={profil}", "--site-per-process", "--no-first-run", "--no-default-browser-check",
         "--disable-sync",
         "--disable-extensions", "--disable-component-extensions-with-background-pages", "--disable-default-apps",
         "--no-service-autorun", "--no-pings", "--disable-quic", "--deny-permission-prompts",
         "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
         "--disable-features=MediaRouter,GlobalMediaControls,DialMediaRouteProvider,CastMediaRouteProvider,"
         "Translate,AutofillServerCommunication,OptimizationHints,InterestFeedContentSuggestions",
         f"--lang={jezyk}", f"--accept-lang={jezyk}-PL,{jezyk},en-US,en" if jezyk == "pl" else f"--accept-lang={jezyk}",
         f"--window-size={ekran[0]},{ekran[1]}"]
    if port_proxy:
        f += [f"--proxy-server=http://127.0.0.1:{int(port_proxy)}", "--proxy-bypass-list=<-loopback>"]
    if not okno:
        f += ["--headless=new", "--mute-audio"]
    if MACOS:
        f.append("--use-mock-keychain")              # bez okna pęku kluczy (hasła i tak są wyłączone)
    if LINUX:
        f.append("--password-store=basic")
    if bez_piaskownicy:
        f.append("--no-sandbox")                     # Linux bez przestrzeni nazw użytkownika (I41): ostrzeżenie w status
    f.append("about:blank")
    return f


def preferencje(pobrane: Path) -> dict:
    """Część `Default/Preferences` profilu, którą ustawiamy przed każdym startem (reszta należy do przeglądarki)."""
    return {
        "credentials_enable_service": False,
        "credentials_enable_autosignin": False,
        "profile": {"password_manager_enabled": False, "exit_type": "Normal", "exited_cleanly": True,
                    "default_content_setting_values": {
                        "notifications": 2, "geolocation": 2, "media_stream_camera": 2, "media_stream_mic": 2,
                        "clipboard": 2, "midi_sysex": 2, "sensors": 2, "idle_detection": 2, "local_fonts": 2,
                        "window_placement": 2, "file_system_write_guard": 2, "serial_guard": 2, "usb_guard": 2,
                        "hid_guard": 2, "bluetooth_guard": 2, "automatic_downloads": 2, "protocol_handlers": 2}},
        "autofill": {"enabled": False, "profile_enabled": False, "credit_card_enabled": False},
        "signin": {"allowed": False, "allowed_on_next_startup": False},
        "browser": {"check_default_browser": False, "has_seen_welcome_page": True},
        "download": {"default_directory": str(pobrane), "prompt_for_download": False, "directory_upgrade": True},
        "savefile": {"default_directory": str(pobrane)},
        "safebrowsing": {"enabled": True},
        "webrtc": {"ip_handling_policy": "disable_non_proxied_udp", "multiple_routes_enabled": False,
                   "nonproxied_udp_enabled": False},
        "translate": {"enabled": False},
        "search": {"suggest_enabled": False},
        "alternate_error_pages": {"enabled": False},
        "session": {"restore_on_startup": 5},        # nowa karta, bez przywracania stron po awarii
    }


def _scal(baza: dict, nowe: dict) -> dict:
    for k, v in nowe.items():
        if isinstance(v, dict) and isinstance(baza.get(k), dict):
            _scal(baza[k], v)
        else:
            baza[k] = v
    return baza


def przygotuj_profil(profil: Path, pobrane: Path) -> None:
    """Katalog profilu i preferencje Jarva (scalone z tym, co zapisała przeglądarka). Po zamknięciu przez system
    (wylogowanie, zabicie usługi) bez dymka „Przywrócić strony?”: exit_type i exited_cleanly jak po zamknięciu."""
    domyslny = profil / "Default"
    domyslny.mkdir(parents=True, exist_ok=True)
    pobrane.mkdir(parents=True, exist_ok=True)
    plik = domyslny / "Preferences"
    try:
        biezace = json.loads(plik.read_text(encoding="utf-8"))
        if not isinstance(biezace, dict):
            biezace = {}
    except (OSError, ValueError):
        biezace = {}
    _scal(biezace, preferencje(pobrane))
    tmp = plik.with_name("Preferences.jarvo-tmp")
    tmp.write_text(json.dumps(biezace, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, plik)
    for blokada in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        try:
            (profil / blokada).unlink()
        except OSError:
            pass


def rozszerzenie(nazwa: str) -> str:
    return nazwa.rsplit(".", 1)[-1].lower() if "." in nazwa else ""


def wykonywalny(nazwa: str) -> bool:
    """Plik, którego Komputer nie zapisuje: rozszerzenie programu albo skryptu (także „faktura.pdf.exe”)."""
    return rozszerzenie(nazwa.strip().rstrip(". ")) in WYKONYWALNE


def czysta_nazwa(nazwa: str) -> str:
    """Nazwa pobranego pliku bez ścieżek, znaków zakazanych na Windows i nazw urządzeń, najwyżej 150 znaków."""
    nazwa = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", os.path.basename(nazwa.replace("\\", "/"))).strip().strip(".")
    if not nazwa or nazwa.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
                                                     *(f"LPT{i}" for i in range(10))}:
        nazwa = "pobrany-plik" + (f".{rozszerzenie(nazwa)}" if rozszerzenie(nazwa) else "")
    if len(nazwa) > 150:
        # skracamy rdzeń, nie rozszerzenie: „a…a.exe.pdf” po ucięciu końca byłoby programem „a…a.exe”
        rdzen, kropka, rozsz = nazwa.rpartition(".") if "." in nazwa else (nazwa, "", "")
        rozsz = rozsz[:20]
        rdzen = rdzen[:150 - len(rozsz) - len(kropka)].rstrip(". ") or "pobrany-plik"
        nazwa = f"{rdzen}{kropka}{rozsz}"
    return nazwa


def bezpieczna_nazwa(nazwa: str, katalog: Path) -> str:
    """czysta_nazwa, unikalna w `katalog` („faktura (2).pdf”)."""
    nazwa = czysta_nazwa(nazwa)
    rdzen, kropka, rozsz = nazwa.rpartition(".") if "." in nazwa else (nazwa, "", "")
    kandydat, i = nazwa, 1
    while (katalog / kandydat).exists():
        i += 1
        kandydat = f"{rdzen} ({i}){kropka}{rozsz}" if kropka else f"{nazwa} ({i})"
    return kandydat
