"""Zgoda właściciela na ręce: klucz HMAC, podpisana zgoda i manifest trybu bounded sterownika.

Pliki w `<stan>` (katalog tylko dla właściciela):
  rece.klucz          32 losowe bajty (hex), zakładany przy pierwszym `jarvo komputer rece on`
  rece/zgoda.json     zgoda: aplikacje, od kiedy, do kiedy, profil, platforma, użytkownik, suma manifestu, podpis
  rece/manifest.yaml  manifest bounded sterownika (wersja 3), na który wskazuje config profilu rąk
                      (`computer_use.capability_manifest`); po `off` zostaje znacznik wyłączenia

Podpis to HMAC-SHA256 kanonicznego JSON-a zgody (klucze posortowane, bez pola `podpis`). Bramka sprawdza przy
każdym `serve` i każdym działaniu: podpis, czas, platformę, użytkownika i sumę manifestu. Zmieniony bajt, inna
lista aplikacji albo dłuższy czas bez nowego podpisu to odmowa. Klucz może przeczytać każdy proces właściciela
(także agent z terminalem w trybie pełnym): to kontrola, nie izolacja (docs/NATYWNIE.md, sekcja d).

Manifest sterownika zapisujemy w JSON-ie (YAML 1.2 to jego nadzbiór, a serde_yaml i PyYAML czytają go bez zmian).
Czas `expires_after` sterownik liczy od swojego startu, więc bramka daje każdemu demonowi własną kopię z czasem,
który został zgodzie (`manifest_sterownika`).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from . import BEZCZYNNOSC, CZAS_MAKS, CZAS_MIN, KONFIGURACJA, NARZEDZIA, PROFIL, WERSJA, ZAKAZANE_NARZEDZIA

WERSJA_ZGODY = 1
CZAS = re.compile(r"^\s*(\d{1,6})\s*(s|sek|m|min|h|godz)?\s*$", re.I)
JEDNOSTKI = {"s": 1, "sek": 1, "m": 60, "min": 60, "h": 3600, "godz": 3600}
WYLACZONE = ("# Ręce na ekranie właściciela są wyłączone (komputer/rece). Włącza je właściciel na swoim komputerze:\n"
             "#   jarvo komputer rece on --aplikacje <lista> --na 30m\n"
             "# Sterownik nie wystartuje z tym plikiem (wersja 0), a bramka odmawia bez podpisanej zgody.\n"
             "version: 0\n")


class BladZgody(RuntimeError):
    """Zgody nie ma albo jest nieważna. `kod` trafia do agenta i do dziennika, komunikat jest dla ludzi."""

    def __init__(self, kod: str, komunikat: str):
        super().__init__(komunikat)
        self.kod = kod


@dataclass(frozen=True)
class Pliki:
    stan: Path

    @property
    def klucz(self) -> Path:
        return self.stan / "rece.klucz"

    @property
    def katalog(self) -> Path:
        return self.stan / "rece"

    @property
    def zgoda(self) -> Path:
        return self.katalog / "zgoda.json"

    @property
    def manifest(self) -> Path:
        return self.katalog / "manifest.yaml"

    @property
    def dziennik(self) -> Path:
        return self.katalog / "dziennik.jsonl"

    @property
    def procesy(self) -> Path:
        return self.katalog / "procesy"

    @property
    def sesje(self) -> Path:
        return self.katalog / "sesje"

    @property
    def dom(self) -> Path:
        """CUA_DRIVER_RS_HOME sterownika: jego stan, konfiguracja i (wyłączona) historia poza profilem właściciela."""
        return self.katalog / "dom"


@dataclass(frozen=True)
class Aplikacja:
    nazwa: str                          # jak podał właściciel (do launch_app i do odczytu)
    tozsamosc: dict                     # {"bundle_id": ...} (macOS, ścieżka programu na Windows) albo {"executable": ...}

    def do_json(self) -> dict:
        return {"nazwa": self.nazwa, "tozsamosc": dict(self.tozsamosc)}


@dataclass(frozen=True)
class Zgoda:
    id: str
    utworzono: int
    wygasa: int
    bezczynnosc: int
    platforma: str
    uzytkownik: str
    profil: str
    aplikacje: tuple[Aplikacja, ...]
    narzedzia: tuple[str, ...]
    manifest_sha256: str
    sterownik: str

    def pozostalo(self, teraz: float | None = None) -> int:
        return int(self.wygasa - (time.time() if teraz is None else teraz))

    def nazwy(self) -> list[str]:
        return [a.nazwa for a in self.aplikacje]


def czas(tekst: str) -> int:
    """`--na`: 30m, 1h, 90s, 45 (minuty) → sekundy; od 1 min do 8 h."""
    m = CZAS.match(str(tekst or ""))
    if not m:
        raise ValueError(f"{tekst!r} to nie czas: podaj np. 30m, 1h albo 90s")
    sekundy = int(m.group(1)) * JEDNOSTKI[(m.group(2) or "m").lower()]
    if not CZAS_MIN <= sekundy <= CZAS_MAKS:
        raise ValueError(f"czas {tekst!r} poza zakresem: od 1 min do {CZAS_MAKS // 3600} h")
    return sekundy


def opis_czasu(sekundy: int) -> str:
    sekundy = max(0, int(sekundy))
    g, reszta = divmod(sekundy, 3600)
    m, s = divmod(reszta, 60)
    if g:
        return f"{g} h {m} min" if m else f"{g} h"
    if m:
        return f"{m} min {s} s" if s and m < 5 else f"{m} min"
    return f"{s} s"


def iso(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def _kanoniczny(dane: dict) -> bytes:
    return json.dumps(dane, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def podpis(klucz: bytes, dane: dict) -> str:
    return hmac.new(klucz, _kanoniczny({k: v for k, v in dane.items() if k != "podpis"}), hashlib.sha256).hexdigest()


def zapisz_plik(plik: Path, tresc: str | bytes) -> None:
    """Zapis atomowy pliku rąk (0600 na POSIX; na Windows ACL dziedziczy katalog `<stan>/rece`)."""
    from jarvo import przenosne
    przenosne.zapisz_atomowo(plik, tresc, tryb=0o600)


def przygotuj_katalog(pliki: Pliki) -> None:
    """`<stan>/rece` tylko dla właściciela (Windows: ACL bez dziedziczenia, POSIX: 0700)."""
    from jarvo import przenosne
    nowy = not pliki.katalog.is_dir()
    for k in (pliki.katalog, pliki.procesy, pliki.sesje, pliki.dom):
        k.mkdir(parents=True, exist_ok=True)
    if nowy or os.name != "nt":
        przenosne.chron(pliki.katalog, katalog=True)


def klucz(pliki: Pliki, *, utworz: bool = False) -> bytes:
    """Klucz HMAC z `<stan>/rece.klucz`; `utworz` zakłada go (tylko `jarvo komputer rece on`)."""
    try:
        tekst = pliki.klucz.read_text(encoding="ascii").strip()
        wartosc = bytes.fromhex(tekst)
        if len(wartosc) >= 32:
            return wartosc
    except (OSError, ValueError):
        pass
    if not utworz:
        raise BladZgody("rece_wylaczone", "Ręce na ekranie właściciela są wyłączone (brak klucza zgody). Włącza je "
                                          "właściciel: jarvo komputer rece on --aplikacje <lista> --na 30m.")
    from jarvo import przenosne
    wartosc = secrets.token_bytes(32)
    pliki.stan.mkdir(parents=True, exist_ok=True)
    zapisz_plik(pliki.klucz, wartosc.hex() + "\n")
    przenosne.chron(pliki.klucz, katalog=False)
    return wartosc


def manifest_sterownika(aplikacje: tuple[Aplikacja, ...] | list[Aplikacja], waznosc: int, bezczynnosc: int,
                        narzedzia: tuple[str, ...] | list[str] = NARZEDZIA) -> str:
    """Manifest bounded (wersja 3) dla cua-driver-rs 0.38.0: tylko te aplikacje (każde okno, uruchomienie tak,
    zamykanie nie), bez pełnego ekranu i plików, set_config tylko z kluczami z KONFIGURACJA, czas i bezczynność."""
    waznosc = max(1, int(waznosc))
    dane = {
        "version": 3,
        "expires_after": f"{waznosc}s",
        "idle_timeout": f"{max(1, min(int(bezczynnosc), waznosc))}s",
        "resources": {
            "apps": [{**a.tozsamosc, "launch": True, "windows": "all", "terminate": "deny"} for a in aplikacje],
            "desktop": {"display": False},
            "driver_configuration": {"changes": [{"key": k, "value": v} for k, v in KONFIGURACJA.items()]},
        },
        "allow": {"tools": [n for n in narzedzia if n in NARZEDZIA]},
        "deny": {"tools": list(ZAKAZANE_NARZEDZIA)},
    }
    return ("# Manifest bounded rąk Jarva (komputer/rece/zgoda.py). Nie edytuj: bramka sprawdza jego sumę w zgodzie.\n"
            + json.dumps(dane, ensure_ascii=True, indent=2) + "\n")


def tozsamosc_uzytkownika() -> str:
    """SID właściciela (Windows) albo uid (POSIX): zgoda skopiowana na inne konto się nie zgadza."""
    if os.name != "nt":
        return f"uid:{os.getuid()}"
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                           ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    k32.LocalFree.argtypes = [ctypes.c_void_p]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(k32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        return f"uzytkownik:{os.environ.get('USERNAME', '')}"
    try:
        n = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(n))          # TokenUser
        bufor = ctypes.create_string_buffer(n.value)
        if not advapi.GetTokenInformation(token, 1, bufor, n, ctypes.byref(n)):
            return f"uzytkownik:{os.environ.get('USERNAME', '')}"
        sid = ctypes.cast(bufor, ctypes.POINTER(ctypes.c_void_p))[0]            # TOKEN_USER.User.Sid
        tekst = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(tekst)):
            return f"uzytkownik:{os.environ.get('USERNAME', '')}"
        try:
            return f"sid:{tekst.value}"
        finally:
            k32.LocalFree(tekst)
    finally:
        k32.CloseHandle(token)


def utworz(pliki: Pliki, aplikacje: list[Aplikacja], sekundy: int, *, platforma: str, profil: str = PROFIL,
           bezczynnosc: int = BEZCZYNNOSC, teraz: float | None = None, uzytkownik: str | None = None) -> Zgoda:
    """Nowa zgoda (stara przestaje działać: inne id) i manifest sterownika. Zwraca zapisaną zgodę."""
    if not aplikacje:
        raise BladZgody("bez_aplikacji", "Podaj aplikacje, w których Operator może działać (--aplikacje).")
    if not CZAS_MIN <= int(sekundy) <= CZAS_MAKS:
        raise BladZgody("zly_czas", f"Czas zgody od 1 min do {CZAS_MAKS // 3600} h.")
    przygotuj_katalog(pliki)
    k = klucz(pliki, utworz=True)
    teraz = int(time.time() if teraz is None else teraz)
    bezczynnosc = max(60, min(int(bezczynnosc), int(sekundy)))
    tekst_manifestu = manifest_sterownika(tuple(aplikacje), int(sekundy), bezczynnosc)
    zapisz_plik(pliki.manifest, tekst_manifestu)
    dane = {
        "wersja": WERSJA_ZGODY, "id": secrets.token_hex(8), "utworzono": teraz, "wygasa": teraz + int(sekundy),
        "utworzono_tekst": iso(teraz), "wygasa_tekst": iso(teraz + int(sekundy)), "bezczynnosc": bezczynnosc,
        "platforma": platforma, "uzytkownik": uzytkownik or tozsamosc_uzytkownika(), "profil": profil,
        "aplikacje": [a.do_json() for a in aplikacje], "narzedzia": list(NARZEDZIA),
        "manifest_sha256": hashlib.sha256(tekst_manifestu.encode("utf-8")).hexdigest(), "sterownik": WERSJA,
    }
    dane["podpis"] = podpis(k, dane)
    zapisz_plik(pliki.zgoda, json.dumps(dane, ensure_ascii=False, indent=2) + "\n")
    return _z_danych(dane)


def _z_danych(dane: dict) -> Zgoda:
    return Zgoda(
        id=str(dane["id"]), utworzono=int(dane["utworzono"]), wygasa=int(dane["wygasa"]),
        bezczynnosc=int(dane["bezczynnosc"]), platforma=str(dane["platforma"]), uzytkownik=str(dane["uzytkownik"]),
        profil=str(dane["profil"]),
        aplikacje=tuple(Aplikacja(str(a["nazwa"]), dict(a["tozsamosc"])) for a in dane["aplikacje"]),
        narzedzia=tuple(str(n) for n in dane["narzedzia"]), manifest_sha256=str(dane["manifest_sha256"]),
        sterownik=str(dane["sterownik"]))


def wczytaj(pliki: Pliki, *, platforma: str, teraz: float | None = None, uzytkownik: str | None = None,
            sprawdz_manifest: bool = True) -> Zgoda:
    """Ważna zgoda albo BladZgody z kodem: rece_wylaczone (brak), zgoda_zmieniona (podpis, format, manifest),
    rece_wygasly (czas), inna_platforma, inny_uzytkownik."""
    try:
        surowe = pliki.zgoda.read_bytes()
    except FileNotFoundError:
        raise BladZgody("rece_wylaczone", "Ręce na ekranie właściciela są wyłączone. Włącza je właściciel na swoim "
                                          "komputerze: jarvo komputer rece on --aplikacje <lista> --na 30m.") from None
    except OSError as e:
        raise BladZgody("zgoda_zmieniona", f"Nie da się przeczytać zgody rąk ({e.strerror}).") from None
    k = klucz(pliki)
    try:
        dane = json.loads(surowe.decode("utf-8"))
        if not isinstance(dane, dict) or dane.get("wersja") != WERSJA_ZGODY:
            raise ValueError("format")
        zapisany = str(dane.get("podpis") or "")
        if not hmac.compare_digest(zapisany, podpis(k, dane)):
            raise BladZgody("zgoda_zmieniona", "Zgoda rąk ma zły podpis (zmieniona poza `jarvo komputer rece on`): "
                                               "ręce wyłączone. Właściciel może włączyć je od nowa.")
        zgoda = _z_danych(dane)
    except BladZgody:
        raise
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        raise BladZgody("zgoda_zmieniona", "Zgoda rąk ma zły format: ręce wyłączone.") from None
    if zgoda.platforma != platforma:
        raise BladZgody("inna_platforma", f"Zgoda rąk jest dla {zgoda.platforma}, a to {platforma}.")
    if zgoda.uzytkownik != (uzytkownik or tozsamosc_uzytkownika()):
        raise BladZgody("inny_uzytkownik", "Zgoda rąk należy do innego konta: ręce wyłączone.")
    if zgoda.sterownik != WERSJA:
        raise BladZgody("zgoda_zmieniona", f"Zgoda rąk jest dla sterownika {zgoda.sterownik}, a bramka zna {WERSJA}.")
    if not (zgoda.aplikacje and zgoda.utworzono < zgoda.wygasa <= zgoda.utworzono + CZAS_MAKS):
        raise BladZgody("zgoda_zmieniona", "Zgoda rąk ma zły zakres: ręce wyłączone.")
    if zgoda.pozostalo(teraz) <= 0:
        raise BladZgody("rece_wygasly", f"Zgoda rąk wygasła ({iso(zgoda.wygasa)}). Właściciel może ją odnowić: "
                                        "jarvo komputer rece on --aplikacje <lista> --na 30m.")
    if sprawdz_manifest:
        try:
            suma = hashlib.sha256(pliki.manifest.read_bytes()).hexdigest()
        except OSError:
            suma = ""
        if not hmac.compare_digest(suma, zgoda.manifest_sha256):
            raise BladZgody("zgoda_zmieniona", "Manifest rąk różni się od podpisanego w zgodzie: ręce wyłączone.")
    return zgoda


def odwolaj(pliki: Pliki) -> bool:
    """Wyłącza ręce od razu: usuwa zgodę, a w miejsce manifestu kładzie znacznik wyłączenia (Hermes w trybie
    bounded wymaga istniejącego pliku manifestu, więc agent dostaje wtedy polski komunikat bramki zamiast
    „capability manifest not found”). True, gdy zgoda była."""
    bylo = pliki.zgoda.exists()
    try:
        pliki.zgoda.unlink()
    except FileNotFoundError:
        pass
    przygotuj_katalog(pliki)
    zapisz_plik(pliki.manifest, WYLACZONE)
    return bylo


def stan_pliku(p: Path) -> tuple[int, int] | None:
    """(mtime_ns, rozmiar) pliku do taniego sprawdzania zmian; None, gdy pliku nie ma."""
    try:
        s = p.stat()
    except OSError:
        return None
    return s.st_mtime_ns, s.st_size
