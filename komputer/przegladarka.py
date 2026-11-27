"""Przeglądarka Jarva natywnie (docs/NATYWNIE.md J01, J07, J11): program, flagi, preferencje profilu i pobrane pliki.

Polityk maszynowych (HKLM, /etc/opt/chrome/policies) nie używamy, bo wymagają admina i działałyby też na Chrome
właściciela. Zamiast nich:
  - flagi startu: bez synchronizacji, rozszerzeń, aplikacji domyślnych, Cast (MediaRouter szuka urządzeń w sieci
    lokalnej po UDP, poza proxy), QUIC, pingów; proxy filtrujące dla całego ruchu (także pętli zwrotnej),
    WebRTC bez UDP poza proxy, odmowa każdej prośby o uprawnienie (`--deny-permission-prompts`), bez
    navigator.webdriver (`--disable-blink-features=AutomationControlled`);
  - preferencje profilu (`Default/Preferences`, zapisywane przed każdym startem): menedżer haseł włączony (logowania
    trwałe), bez autouzupełniania adresów i kart, logowania do przeglądarki, tłumacza; pobrane pliki do osobnego
    katalogu, bez pytania; Bezpieczne przeglądanie włączone (ochrony przed phishingiem nie wyłączamy); WebRTC drugi
    raz w preferencjach (ta sama zasada co flaga: UDP tylko przez proxy, czyli wcale);
  - przez CDP (sterownik_cdp.py): odmowa uprawnień (kamera, mikrofon, schowek, przechwytywanie ekranu, położenie,
    powiadomienia…), pobrania pod nazwą GUID z odrzuceniem typów wykonywalnych, blokada file://, przechwycenie
    wyboru pliku (w trybie w tle), strona testowa przez Fetch.fulfillRequest.
Bez `--disable-popup-blocking` i bez wyłączania ochrony przed phishingiem (Playwright robi jedno i drugie).
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")
EKRAN = (1440, 900)
NARZEDZIE = "chrome-komputer"                       # wpis manifestu (vendor/natywne.yaml, kiedy: przy-uzyciu)
ZMIENNA_PROGRAMU = "JARVO_KOMPUTER_CHROME"          # env wpisu manifestu: ścieżka programu w katalogu narzędzia
ZMIENNA_PROBY = "JARVO_KOMPUTER_CHROME_PROBA"       # tylko próby i testy: inna przeglądarka (np. chrome-headless-shell)
# przeglądarka w tle bez okna nie ma myszy: wskaźnik precyzyjny z najeżdżaniem jak na komputerze (typy Blinka: fine=4,
# hover=2), bo (any-pointer: none) przy desktopowym user-agencie to cecha trybu bez okna
MYSZ_W_TLE = "primaryPointerType=4,availablePointerTypes=4,primaryHoverType=2,availableHoverTypes=2"

# Rozszerzenia plików, których Komputer nie zapisuje (programy, skrypty, instalatory, obrazy dysków, skróty).
WYKONYWALNE = frozenset("""
exe msi msix msixbundle appx appxbundle bat cmd com scr pif cpl vbs vbe js jse wsf wsh wsc ps1 psm1 psd1 ps1xml
hta lnk url reg jar dll sys drv ocx inf application appref-ms gadget chm msc msp mst iso img vhd vhdx
app dmg pkg mpkg command tool scpt applescript workflow terminal kext prefpane dylib
sh bash zsh ksh csh fish run bin deb rpm appimage desktop snap flatpakref so elf
py pyw pyc pyz pl rb php lua
""".split())


def program(env: dict | None = None, narzedzia: dict | None = None, ustawienia: dict | None = None) -> str | None:
    """Program przeglądarki: zmienna próby, przeglądarka próby z ustawień Komputera (`proba`: zapisuje ją `jarvo
    komputer on` wywołane ze zmienną próby, żeby usługa pod nadzorcą wzięła tę samą), zmienna z wpisu manifestu,
    wpis w narzedzia.json i pin z ustawień (`chrome`). None, gdy przeglądarki nie zainstalowano."""
    env = os.environ if env is None else env
    ustawienia = ustawienia or {}
    wpis = (narzedzia or {}).get(NARZEDZIE) or {}
    for p in (env.get(ZMIENNA_PROBY), ustawienia.get("proba"), env.get(ZMIENNA_PROGRAMU),
              (wpis.get("env") or {}).get(ZMIENNA_PROGRAMU), ustawienia.get("chrome")):
        p = str(p or "").strip()
        if p:
            return p
    return None


def x64_w_emulacji(program: str | Path, maszyna: str = "") -> bool:
    """Przeglądarka x64 na Windows ARM64 (nagłówek PE pliku, bez uruchamiania): działa w emulacji Prism."""
    if not WINDOWS and not maszyna:
        return False
    if not maszyna:
        from jarvo import sciezki
        maszyna = sciezki.maszyna_windows()
    if maszyna.upper() != "ARM64":
        return False
    try:
        with open(program, "rb") as f:
            naglowek = f.read(4096)
        pe = int.from_bytes(naglowek[0x3C:0x40], "little")
        return naglowek[:2] == b"MZ" and int.from_bytes(naglowek[pe + 4:pe + 6], "little") == 0x8664
    except (OSError, ValueError):
        return False


def flagi(*, profil: Path, port_proxy: int | None, okno: bool, ekran: tuple[int, int] = EKRAN,
          bez_piaskownicy: bool = False, jezyk: str = "pl", emulacja: bool = False,
          program: str | Path | None = None) -> list[str]:
    """Argumenty startu przeglądarki Jarva (bez --remote-debugging-pipe, który dokłada cdp.Przegladarka).
    `emulacja`: przeglądarka x64 w emulacji (Windows arm64): bez GPU i bez SwiftShadera, którego JIT x64 w emulacji
    potrafi zatrzymać renderer nowej karty na dziesiątki sekund (CI natywnie, WARM: Page.enable bez odpowiedzi).
    `program`: ścieżka przeglądarki z wersją w katalogu manifestu, z niej user-agent w tle (user_agent)."""
    f = [f"--user-data-dir={profil}", "--site-per-process", "--no-first-run", "--no-default-browser-check",
         "--disable-sync",
         "--disable-extensions", "--disable-component-extensions-with-background-pages", "--disable-default-apps",
         "--no-service-autorun", "--no-pings", "--disable-quic", "--deny-permission-prompts",
         "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
         # WebUI* i SpareRenderer: bez ukrytych kart przycisku przeładowania i podpowiedzi paska oraz zapasowego
         # renderera (pomiar 10.11 na CfT 156: 7 procesów zamiast 10, bezczynnie ok. -31% PSS, ze stroną ok. -60 MB;
         # logowanie, ciasteczka, pobieranie, CDP i zrzuty bez zmian). Nazwy eksperymentalne: przy podbiciu pinu
         # sprawdzić, że /json/list po starcie ma tylko about:blank.
         "--disable-features=MediaRouter,GlobalMediaControls,DialMediaRouteProvider,CastMediaRouteProvider,"
         "Translate,AutofillServerCommunication,OptimizationHints,WebUIReloadButton,WebUIOmniboxPopup,"
         "WebUIOmniboxAimPopup,SpareRendererForSitePerProcess",
         # CDP przez potok włącza w Blinku AutomationControlled, czyli navigator.webdriver = true, po którym Turnstile
         # i DataDome odrzucają stronę od razu; Komputer działa na kontach właściciela jak człowiek, więc bez tej flagi
         "--disable-blink-features=AutomationControlled",
         f"--lang={jezyk}", f"--accept-lang={jezyk}-PL,{jezyk},en-US,en" if jezyk == "pl" else f"--accept-lang={jezyk}",
         f"--window-size={ekran[0]},{ekran[1]}"]
    if port_proxy:
        f += [f"--proxy-server=http://127.0.0.1:{int(port_proxy)}", "--proxy-bypass-list=<-loopback>"]
    if not okno:
        # ekran przeglądarki w tle: bez tego 800×600 przy oknie 1440×900 i bez paska zadań (avail = cały ekran), a do
        # tego bez myszy ((any-pointer: none), (hover: none)); po tych cechach CreepJS i antyboty rozpoznają tryb bez okna
        szer, wys = max(1920, ekran[0]), max(1080, ekran[1] + 48)
        f += ["--headless=new", "--mute-audio", f"--screen-info={{0,0 {szer}x{wys} workAreaBottom=48}}",
              "--blink-settings=" + MYSZ_W_TLE]
        if LINUX and not emulacja and gpu_linux():
            # WebGL na karcie graficznej (ANGLE przez EGL bez ekranu) zamiast SwiftShadera, którego nazwę w WebGL
            # antyboty czytają jako tryb bez okna; bez urządzenia renderD* zostaje SwiftShader (VPS, CI)
            f += ["--use-gl=angle", "--use-angle=gl-egl"]
        ua = user_agent(program)
        if ua:
            f.append(f"--user-agent={ua}")
    if emulacja:
        # bez GPU i SwiftShadera, a każda karta we własnym procesie renderera: przy małej pamięci Chrome upycha karty
        # tej samej strony w jednym procesie, a drugi widget w emulacji kończył się błędami mojo (Z42)
        f += ["--disable-gpu", "--disable-software-rasterizer", "--renderer-process-limit=100"]
    if MACOS:
        f.append("--use-mock-keychain")              # bez okna pęku kluczy systemu
    if LINUX:
        f.append("--password-store=basic")
    if bez_piaskownicy:
        f.append("--no-sandbox")                     # Linux bez przestrzeni nazw użytkownika (I41): ostrzeżenie w status
    f.append("about:blank")
    return f


def user_agent(program: str | Path | None) -> str | None:
    """User-agent jak Chrome z oknem tej samej wersji (z katalogu manifestu, np. …/158.0.8127.36/…) dla przeglądarki
    w tle, która przedstawia się „HeadlessChrome”. Flagą, bo nadpisanie przez CDP (sterownik_cdp, karty z markami
    i pełną wersją) nie sięga do service workerów: CreepJS czytał w nich „HeadlessChrome” (pomiar 27.11)."""
    wersja = re.search(r"[/\\](\d+)\.\d+\.\d+\.\d+[/\\]", str(program or ""))
    if not wersja:
        return None
    system = ("Windows NT 10.0; Win64; x64" if WINDOWS else "Macintosh; Intel Mac OS X 10_15_7" if MACOS
              else "X11; Linux x86_64")
    return (f"Mozilla/5.0 ({system}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{wersja.group(1)}.0.0.0 "
            "Safari/537.36")


def gpu_linux() -> bool:
    """Linux: karta graficzna dostępna dla tego użytkownika (/dev/dri/renderD*, odczyt i zapis)."""
    try:
        return any(os.access(p, os.R_OK | os.W_OK) for p in Path("/dev/dri").glob("renderD*"))
    except OSError:
        return False


def brak_piaskownicy(log: Path) -> bool:
    """Linux: przeglądarka nie wstała, bo jądro nie daje przestrzeni nazw użytkownika (AppArmor, I41); poznać to
    po końcu jej dziennika. Wtedy start z `bez_piaskownicy` (usługa i testy sterownika robią to tak samo)."""
    try:
        ogon = log.read_text(encoding="utf-8", errors="replace")[-4000:].lower()
    except OSError:
        return False
    return "sandbox" in ogon and ("namespace" in ogon or "no usable sandbox" in ogon)


def procesy_profilu(profil: Path) -> list[int]:
    """PID-y procesów z `--user-data-dir=<profil>` w argumentach (Linux: /proc, macOS: ps; Windows: brak, tam
    przeglądarka siedzi w zadaniu, które ginie z usługą). Usługa trzyma blokadę profilu, więc przy jej starcie
    każdy taki proces to resztka poprzedniej usługi."""
    znak = f"--user-data-dir={profil}"
    wlasny = os.getpid()
    pidy: list[int] = []
    if LINUX:
        for wpis in os.listdir("/proc"):
            if not wpis.isdigit() or int(wpis) == wlasny:
                continue
            try:
                argv = Path(f"/proc/{wpis}/cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            if znak.encode() in argv:
                pidy.append(int(wpis))
    elif MACOS:
        try:
            wynik = subprocess.run(["ps", "-axww", "-o", "pid=,command="], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return []
        for linia in wynik.stdout.splitlines():
            pid, _, polecenie = linia.strip().partition(" ")
            if pid.isdigit() and int(pid) != wlasny and f" {znak} " in f" {polecenie} ":
                pidy.append(int(pid))
    return pidy


def sprzatnij_osierocone(profil: Path, log=None) -> list[int]:
    """Resztki przeglądarki Jarva na tym profilu (usługa zabita bez sprzątania, proces po fork bez exec, który
    przeżył przeglądarkę): SIGTERM, po 3 s SIGKILL. Zwraca PID-y, które znalazła."""
    pidy = procesy_profilu(profil)
    if not pidy:                                     # także Windows (bez SIGKILL)
        return []
    for sygnal in (signal.SIGTERM, signal.SIGKILL):
        for pid in pidy:
            try:
                os.kill(pid, sygnal)
            except OSError:
                pass
        koniec = time.monotonic() + 3
        while time.monotonic() < koniec and any(_zyje(p) for p in pidy):
            time.sleep(0.1)
        if not any(_zyje(p) for p in pidy):
            break
    if pidy and log is not None:
        log(f"sprzątanie: {len(pidy)} procesów przeglądarki Jarva z poprzedniego startu zakończonych "
            f"(pid {', '.join(map(str, pidy[:8]))})")
    return pidy


def _zyje(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:                                             # zombie własnego dziecka: już nie żyje, tylko czeka na wait
        return Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0] != "Z" if LINUX else True
    except OSError:
        return False


def preferencje(pobrane: Path) -> dict:
    """Część `Default/Preferences` profilu, którą ustawiamy przed każdym startem (reszta należy do przeglądarki)."""
    return {
        # menedżer haseł włączony (decyzja właściciela 13.11: konta robi Jarvo, hasło zostaje w profilu przeglądarki,
        # nie w czacie ani pliku); na Linuksie `--password-store=basic`, więc bez okna pęku kluczy systemu
        "credentials_enable_service": True,
        "credentials_enable_autosignin": True,
        "profile": {"password_manager_enabled": True, "exit_type": "Normal", "exited_cleanly": True,
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
