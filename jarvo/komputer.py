"""Polecenie `jarvo komputer` natywnie (docs/NATYWNIE.md N13, J01, J09, J11, J12): przeglądarka Jarva dla Operatora.

  on [--okno|--w-tle]   przeglądarka Jarva (Chrome for Testing z manifestu, wpis `chrome-komputer`, pobierana przy
                        pierwszym włączeniu z paskiem i sumą sha256), nakładka bramki `jarvo-cua` dla Hermesa
                        (HERMES_CUA_DRIVER_CMD), start usługi (komputer/usluga.py: proxy filtrujące z samotestem,
                        przeglądarka, wejście z twardymi zasadami) i czekanie, aż odpowie
  off                   zatrzymanie usługi (profil, pobrane pliki, dziennik i pauza zostają)
  status [--json]       działa czy nie, okno albo w tle, pauza (kto, dlaczego), sesje Operatora, filtr ruchu
                        (zablokowane połączenia), pobrane i odrzucone pliki, piaskownica, wersja przeglądarki
  okno on|off           okno przeglądarki na pulpicie (właściciel sam się w nim loguje) albo w tle (--headless=new)
  pauza [powód]         zatrzymuje Operatora od razu: patrzeć może, działać nie; trwa także po restarcie
  wznow                 zdejmuje pauzę (token właściciela z `<stan>/komputer/wlasciciel.klucz`)
  dziennik [N]          ostatnie N decyzji twardych zasad (bez wpisywanych treści)
  wyczysc [--tak]       po potwierdzeniu kasuje profil przeglądarki (zalogowania, ciasteczka, historia), pobrane
                        pliki i pliki do wysłania
  odswiez               przeglądarka z pinu manifestu tej wersji Jarva (po `jarvo update` z nowym pinem CfT: pobranie
                        z sumą i start usługi od nowa); `on` sprawdza pin tak samo
Ekran w HQ (J10) rozmawia z usługą przez ten sam kanał `ster` z tokenem właściciela (klatka podglądu, przejmij,
wejście właściciela, wznow), opis w komputer/wejscie_natywne.py.

Podpięte w jarvo/cli.py (polecenie_komputer): `jarvo komputer …` woła main(reszta, u=u, ot=ot) bez własnej pomocy
argparse jarvo, a `jarvo komputer rece …` idzie do jarvo/rece.py (ekran właściciela, K6).
Autostart przez nadzorcę (usługa `komputer` po bramie i panelu, gdy `<stan>/komputer/ustawienia.json` ma
`wlaczony: true`) dopisuje jarvo/nadzorca.py; do tego czasu `on` uruchamia usługę sam, w tle.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from . import instalator, manifest, pobieracz, przenosne, sciezki, srodowisko
from .sciezki import WINDOWS, Uklad

APP = Path(__file__).resolve().parent.parent
CZAS_STARTU = 120.0                 # pierwszy start: profil, samotest proxy i przeglądarki
CZAS_STOPU = 40.0
LOG = "komputer.log"


def _kanal():
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    from komputer import kanal
    return kanal


def _przegladarka():
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    from komputer import przegladarka
    return przegladarka


def katalogi(u: Uklad) -> dict[str, Path]:
    stan = u.stan / "komputer"
    dane = u.jarvo_dane / "komputer"
    return {"stan": stan, "dane": dane, "ustawienia": stan / "ustawienia.json", "usluga": stan / "usluga.json",
            "token": stan / "wlasciciel.klucz", "profil": dane / "profil", "pobrane": dane / "pobrane",
            "wysylane": dane / "wysylane", "dziennik": dane / "dziennik.jsonl", "pauza": dane / "pauza",
            "log": u.logi / LOG}


def ustawienia(u: Uklad) -> dict:
    return srodowisko.wczytaj_json(katalogi(u)["ustawienia"])


def zapisz_ustawienia(u: Uklad, **zmiany) -> dict:
    biezace = {**ustawienia(u), **zmiany}
    przenosne.zapisz_atomowo(katalogi(u)["ustawienia"], json.dumps(biezace, ensure_ascii=False, indent=2) + "\n")
    return biezace


def _token(u: Uklad) -> str:
    try:
        return katalogi(u)["token"].read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def zapytaj(u: Uklad, polecenie: dict, czas: float = 10.0, wlasciciel: bool = False) -> dict:
    """Polecenie na kanale `ster` usługi (z tokenem właściciela, gdy `wlasciciel`)."""
    kanal = _kanal()
    if wlasciciel:
        polecenie = {**polecenie, "token": _token(u)}
    return kanal.zapytaj(kanal.adres(u.root, "ster"), polecenie, czas, kanal.pid_uslugi(u.root))


def dziala(u: Uklad) -> dict | None:
    """Stan usługi z kanału (None, gdy nie działa)."""
    kanal = _kanal()
    if kanal.pid_uslugi(u.root) is None:
        return None
    try:
        odp = zapytaj(u, {"polecenie": "stan"}, 5.0)
    except kanal.BladKanalu:
        return None
    return odp if odp.get("ok") else None


# ---------------------------------------------------------------- przeglądarka z manifestu

def wpis_przegladarki(app: Path) -> tuple[str, dict]:
    """(wersja, plik dla tej platformy) wpisu `chrome-komputer`; manifest.BrakNarzedzia, gdy go nie ma."""
    narz = manifest.wczytaj(app)
    nazwa = _przegladarka().NARZEDZIE
    return manifest.wersja(narz, nazwa), manifest.plik(narz, nazwa, sciezki.platforma())


def program_przegladarki(u: Uklad, env: dict) -> str | None:
    """Zainstalowana przeglądarka Jarva (zmienna próby, narzedzia.json albo ustawienia Komputera) albo None."""
    p = _przegladarka().program(env, srodowisko.narzedzia(u)) or ustawienia(u).get("chrome")
    return p if p and Path(p).is_file() else None


def _katalog_pinu(u: Uklad, wersja: str) -> Path:
    return u.program / "narzedzia" / _przegladarka().NARZEDZIE / pobieracz.katalog_wersji(wersja)


def przegladarka_aktualna(u: Uklad, wersja: str, plik: dict) -> bool:
    """Czy pin z manifestu jest już zainstalowany (znacznik `.jarvo-suma` z tą samą sumą) i zapisany w ustawieniach."""
    try:
        suma = (_katalog_pinu(u, wersja) / ".jarvo-suma").read_text(encoding="utf-8").strip()
    except OSError:
        return False
    chrome = ustawienia(u).get("chrome")
    return suma == plik.get("sha256") and bool(chrome) and Path(chrome).is_file() and \
        ustawienia(u).get("wersja") == wersja


def zainstaluj_przegladarke(u: Uklad, app: Path, log=print) -> str:
    """Pobiera przeglądarkę Jarva z manifestu (suma przed rozpakowaniem) do `<program>/narzedzia`. Ścieżka programu.
    Pin już zainstalowany z tą samą sumą: bez pobierania."""
    wersja, plik = wpis_przegladarki(app)
    if not przegladarka_aktualna(u, wersja, plik):
        log(f"Pobieram przeglądarkę Jarva (Chrome for Testing {wersja}, {plik.get('rozmiar', 0) / 1e6:.0f} MB, "
            "suma sha256 sprawdzana przed rozpakowaniem)…")
    katalog = pobieracz.zainstaluj(_przegladarka().NARZEDZIE, wersja, plik, u.program / "narzedzia",
                                   u.cache / "pobrane")
    # jak każde narzędzie przy pierwszym użyciu: prawo odczytu dla piaskownicy Chromium (Windows) i wpis
    # w narzedzia.json, bez którego sprzątanie `jarvo update` uznawało przeglądarkę za starą wersję i ją usuwało
    przenosne.dla_piaskownicy_chromium(katalog)
    from . import przy_uzyciu
    przy_uzyciu.zapisz_wpis(u, _przegladarka().NARZEDZIE, przy_uzyciu.spis_narzedzia(wersja, plik, katalog))
    zmienna = _przegladarka().ZMIENNA_PROGRAMU
    sciezka = str((plik.get("env") or {}).get(zmienna) or "").replace("{katalog}", str(katalog))
    sciezka = os.path.normpath(sciezka) if sciezka else ""
    if not sciezka or not Path(sciezka).is_file():
        raise pobieracz.BladPobierania(f"w paczce przeglądarki nie ma programu {sciezka or '(brak env)'}")
    zapisz_ustawienia(u, chrome=sciezka, wersja=wersja, sha256=plik.get("sha256"))
    return sciezka


def przegladarka_do_startu(u: Uklad, app: Path, env: dict, log=print) -> str:
    """Program przeglądarki dla usługi (J01, J12). Zmienna próby JARVO_KOMPUTER_CHROME_PROBA wygrywa (próby i testy);
    inaczej pin z manifestu tej wersji Jarva: brak albo inna suma niż zainstalowana = pobranie z sumą, więc po
    `jarvo update` z nowym pinem CfT następne `on` (i `odswiez`) bierze nową przeglądarkę. Manifest bez wpisu:
    przeglądarka zainstalowana wcześniej, a bez niej manifest.BrakNarzedzia."""
    przegl = _przegladarka()
    proba = str(env.get(przegl.ZMIENNA_PROBY) or "").strip()
    if proba:
        if not Path(proba).is_file():
            raise pobieracz.BladPobierania(f"{przegl.ZMIENNA_PROBY}: nie ma pliku {proba}")
        return proba
    try:
        wpis_przegladarki(app)
    except manifest.BrakNarzedzia:
        obecna = ustawienia(u).get("chrome")
        if obecna and Path(obecna).is_file():
            return obecna
        raise
    return zainstaluj_przegladarke(u, app, log)


def nakladka_bramki(u: Uklad, app: Path, python: Path) -> Path:
    """`<program>/bin-floty/jarvo-cua(.cmd)`: bramka komputer/jarvo_cua.py Pythonem Jarva. Na nią wskazuje
    HERMES_CUA_DRIVER_CMD procesów floty (jarvo/srodowisko.py)."""
    bramka = app / "komputer" / "jarvo_cua.py"
    if WINDOWS:
        # cmd.exe czyta plik w stronie kodowej OEM: same znaki ASCII (ścieżki <program> są ASCII, c1)
        cel = u.bin_floty / "jarvo-cua.cmd"
        tresc = ("@echo off\r\nrem Bramka Komputera Jarva dla Hermesa (HERMES_CUA_DRIVER_CMD), zapis: jarvo komputer on"
                 f"\r\n\"{python}\" -I -X utf8 \"{bramka}\" %*\r\n")
        przenosne.zapisz_atomowo(cel, tresc)
    else:
        cel = u.bin_floty / "jarvo-cua"
        tresc = ("#!/bin/sh\n# Bramka Komputera Jarva dla Hermesa (HERMES_CUA_DRIVER_CMD); tworzy ją "
                 f"`jarvo komputer on`.\nexec '{python}' -I -X utf8 '{bramka}' \"$@\"\n")
        przenosne.zapisz_atomowo(cel, tresc, tryb=0o755)
    return cel


# ---------------------------------------------------------------- polecenia

def _czekaj_na_start(u: Uklad, ot: instalator.Otoczenie, pid: int, czas: float) -> dict | None:
    koniec = ot.zegar() + czas
    while ot.zegar() < koniec:
        stan = dziala(u)
        if stan:
            return stan
        if not _zyje(pid):
            return None
        ot.czekaj(0.5)
    return None


def _zyje(pid: int | None) -> bool:
    """Czy proces `pid` jeszcze działa (Windows: kod wyjścia STILL_ACTIVE; POSIX: sygnał 0)."""
    if not pid:
        return False
    if WINDOWS:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype, k32.OpenProcess.argtypes = wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL,
                                                                              wintypes.DWORD]
        k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        h = k32.OpenProcess(0x1000, False, int(pid))              # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            kod = wintypes.DWORD()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(kod))) and kod.value == 259
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _ogon_logu(u: Uklad, n: int = 12) -> str:
    try:
        linie = katalogi(u)["log"].read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(linie[-n:])


def polecenie_on(u: Uklad, a, ot: instalator.Otoczenie) -> int:
    app = instalator.katalog_aplikacji(u)
    stan = dziala(u)
    okno = a.okno if a.okno is not None else bool(ustawienia(u).get("okno"))
    if stan:
        uslugi = stan.get("usluga") or {}
        if bool(uslugi.get("okno")) != okno:
            zapytaj(u, {"polecenie": "okno", "okno": okno}, 120.0, wlasciciel=True)
        zapisz_ustawienia(u, wlaczony=True, okno=okno)
        print(f"Komputer Jarva już działa ({'okno widoczne' if okno else 'w tle'}).")
        return 0
    try:
        program = przegladarka_do_startu(u, app, ot.env)
    except manifest.BrakNarzedzia as e:
        print(f"BŁĄD: manifest tej wersji Jarva nie ma przeglądarki Komputera ({e}). Komputer natywnie "
              "przychodzi z etapem E10 (docs/NATYWNIE.md).", file=sys.stderr)
        return 1
    except (pobieracz.BladPobierania, OSError) as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    python = instalator.python_jarva(u)
    nakladka = nakladka_bramki(u, app, python)
    for nazwa in ("dane", "profil", "pobrane", "wysylane"):
        katalogi(u)[nazwa].mkdir(parents=True, exist_ok=True)
    zapisz_ustawienia(u, wlaczony=True, okno=okno)
    argv = [str(python), "-I", "-X", "utf8", str(app / "komputer" / "usluga.py"), "--korzen", str(u.root),
            "--okno" if okno else "--w-tle", "--przegladarka", str(program)]
    if a.strona_testowa:
        argv += ["--strona-testowa", str(Path(a.strona_testowa).resolve())]
    env = srodowisko.srodowisko(u, instalator.env_floty(ot.env))
    pid = ot.uruchom_w_tle(argv, env, katalogi(u)["log"])
    print(f"Startuję Komputer Jarva (przeglądarka {'w oknie' if okno else 'w tle'}, filtr ruchu z samotestem)…")
    stan = _czekaj_na_start(u, ot, pid, CZAS_STARTU)
    if not stan:
        print("BŁĄD: Komputer nie wstał. Ostatnie wiersze logu:\n" + _ogon_logu(u), file=sys.stderr)
        return 1
    print(opis_stanu(u, stan))
    print(f"Bramka dla Hermesa: {nakladka} (HERMES_CUA_DRIVER_CMD).")
    return 0


def polecenie_off(u: Uklad, a, ot: instalator.Otoczenie) -> int:
    kanal = _kanal()
    zapisz_ustawienia(u, wlaczony=False)
    pid = kanal.pid_uslugi(u.root)
    if not dziala(u):
        print("Komputer Jarva nie działa.")
        return 0
    zapytaj(u, {"polecenie": "stop"}, 10.0, wlasciciel=True)
    koniec = ot.zegar() + CZAS_STOPU
    while ot.zegar() < koniec and _zyje(pid) and katalogi(u)["usluga"].exists():
        ot.czekaj(0.3)
    print("Komputer Jarva zatrzymany (profil, pobrane pliki, dziennik i pauza zostają).")
    return 0


def polecenie_odswiez(u: Uklad, a, ot: instalator.Otoczenie) -> int:
    """Pin przeglądarki z manifestu tej wersji Jarva (J12): inny niż zainstalowany = pobranie z sumą; działająca
    usługa startuje od nowa z nową przeglądarką (profil, pobrane, dziennik i pauza zostają)."""
    app = instalator.katalog_aplikacji(u)
    try:
        wersja, plik = wpis_przegladarki(app)
    except manifest.BrakNarzedzia as e:
        print(f"BŁĄD: manifest tej wersji Jarva nie ma przeglądarki Komputera ({e}).", file=sys.stderr)
        return 1
    if przegladarka_aktualna(u, wersja, plik):
        print(f"Przeglądarka Jarva jest aktualna (Chrome for Testing {wersja}).")
        return 0
    try:
        zainstaluj_przegladarke(u, app)
    except (pobieracz.BladPobierania, OSError) as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    print(f"Przeglądarka Jarva: Chrome for Testing {wersja}.")
    if not dziala(u):
        return 0
    polecenie_off(u, a, ot)
    a.okno, a.strona_testowa = None, None
    return polecenie_on(u, a, ot)


def zbierz_stan(u: Uklad) -> dict:
    k = katalogi(u)
    ust = ustawienia(u)
    stan = dziala(u)
    wynik = {"wlaczony": bool(ust.get("wlaczony")), "dziala": bool(stan), "okno": bool(ust.get("okno")),
             "przegladarka": ust.get("chrome"), "wersja": ust.get("wersja"), "profil": str(k["profil"]),
             "pobrane": sorted(p.name for p in k["pobrane"].iterdir() if p.is_file())[:50]
             if k["pobrane"].is_dir() else []}
    if stan:
        wynik.update(wstrzymane=stan.get("wstrzymane"), sesje=stan.get("sesje"), pauza=stan.get("pauza"),
                     usluga=stan.get("usluga"))
    else:
        try:
            wynik["pauza"] = json.loads(k["pauza"].read_text(encoding="utf-8"))
            wynik["wstrzymane"] = True
        except (OSError, ValueError):
            wynik["wstrzymane"] = False
    return wynik


def opis_stanu(u: Uklad, stan: dict | None = None) -> str:
    s = zbierz_stan(u)
    if not s["dziala"]:
        linie = ["Komputer Jarva: nie działa" + (" (włączony, ale usługa stoi: jarvo komputer on)"
                                                if s["wlaczony"] else " (jarvo komputer on)")]
    else:
        us = s.get("usluga") or {}
        filtr = us.get("filtr") or {}
        linie = [f"Komputer Jarva: działa, {'okno widoczne' if us.get('okno') else 'w tle'}; "
                 f"{us.get('przegladarka') or 'przeglądarka'} (pid {us.get('pid_przegladarki')}), "
                 f"kart: {us.get('okna')}, sesje Operatora: {s.get('sesje')}",
                 f"  filtr ruchu: proxy 127.0.0.1:{us.get('proxy')}, zablokowane połączenia: "
                 f"{filtr.get('zablokowane', 0)}" + ("" if (us.get("samotest") or {}).get("filtr", {}).get("ok")
                                                     else " (samotest NIE przeszedł)"),
                 f"  pobrane: {(us.get('pobrania') or {}).get('pobrane', 0)}, odrzucone programy: "
                 f"{(us.get('pobrania') or {}).get('odrzucone', 0)}"]
        if not us.get("piaskownica", True):
            linie.append("  UWAGA: przeglądarka bez piaskownicy (--no-sandbox): brak przestrzeni nazw użytkownika "
                         "(docs/NATYWNIE.md I41)")
    if s.get("wstrzymane"):
        p = s.get("pauza") or {}
        linie.append(f"  PAUZA: {p.get('opis') or p.get('powod') or 'właściciel zatrzymał Komputer'} "
                     "(wznawia właściciel: jarvo komputer wznow)")
    linie.append(f"  profil: {s['profil']}")
    return "\n".join(linie)


def polecenie_status(u: Uklad, a, _ot) -> int:
    s = zbierz_stan(u)
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        print(opis_stanu(u))
    return 0 if s["dziala"] else 1


def polecenie_okno(u: Uklad, a, _ot) -> int:
    okno = a.stan == "on"
    zapisz_ustawienia(u, okno=okno)
    if dziala(u):
        odp = zapytaj(u, {"polecenie": "okno", "okno": okno}, 120.0, wlasciciel=True)
        if not odp.get("ok"):
            print(f"BŁĄD: {odp.get('blad')}", file=sys.stderr)
            return 1
    print("Przeglądarka Jarva " + ("w oknie na pulpicie: zaloguj się w niej sam, Operator korzysta z tej sesji."
                                   if okno else "w tle (podgląd w HQ, K4)."))
    return 0


def polecenie_pauza(u: Uklad, a, _ot) -> int:
    if not dziala(u):
        print("Komputer Jarva nie działa.", file=sys.stderr)
        return 1
    odp = zapytaj(u, {"polecenie": "pauza", "powod": " ".join(a.powod or [])}, wlasciciel=True)
    print("Komputer Jarva wstrzymany: Operator patrzy, ale nie działa. Wznowienie: jarvo komputer wznow"
          if odp.get("wstrzymane") else f"BŁĄD: {odp.get('blad')}")
    return 0 if odp.get("wstrzymane") else 1


def polecenie_wznow(u: Uklad, a, _ot) -> int:
    if not dziala(u):
        print("Komputer Jarva nie działa.", file=sys.stderr)
        return 1
    odp = zapytaj(u, {"polecenie": "wznow"}, wlasciciel=True)
    if odp.get("ok") and not odp.get("wstrzymane"):
        print("Komputer Jarva wznowiony.")
        return 0
    print(f"BŁĄD: {odp.get('blad') or 'pauza została'}", file=sys.stderr)
    return 1


def _wpisy_z_pliku(u: Uklad, n: int) -> list[dict]:
    wpisy = []
    try:
        for linia in katalogi(u)["dziennik"].read_text(encoding="utf-8").splitlines()[-n:]:
            try:
                wpisy.append(json.loads(linia))
            except ValueError:
                pass
    except OSError:
        pass
    return wpisy


def polecenie_dziennik(u: Uklad, a, _ot) -> int:
    n = max(1, min(200, a.n))
    wpisy = zapytaj(u, {"polecenie": "dziennik", "n": n}).get("wpisy", []) if dziala(u) else _wpisy_z_pliku(u, n)
    if a.json:
        print(json.dumps(wpisy, ensure_ascii=False, indent=1))
        return 0
    for w in wpisy:
        cel = f" {w['cel']}" if w.get("cel") else ""
        zasada = f" [{w['zasada']}]" if w.get("zasada") else ""
        print(f"{w.get('t', '')} {w.get('narzedzie', '')}: {w.get('decyzja', '')}{zasada}{cel}")
    if not wpisy:
        print("Dziennik jest pusty.")
    return 0


def polecenie_wyczysc(u: Uklad, a, _ot) -> int:
    k = katalogi(u)
    if not a.tak:
        try:
            odp = input("Skasować profil przeglądarki Jarva (zalogowania, ciasteczka, historia), pobrane pliki i pliki "
                        "do wysłania? "
                        "Wpisz „tak”: ")
        except EOFError:
            odp = ""
        if odp.strip().lower() not in ("tak", "t", "yes", "y"):
            print("Nic nie skasowane.")
            return 1
    if dziala(u):
        odp = zapytaj(u, {"polecenie": "wyczysc"}, 120.0, wlasciciel=True)
        if not odp.get("ok"):
            print(f"BŁĄD: {odp.get('blad')}", file=sys.stderr)
            return 1
    else:
        for nazwa in ("profil", "pobrane", "wysylane"):
            shutil.rmtree(k[nazwa], ignore_errors=True)
    print("Profil przeglądarki Jarva, pobrane pliki i pliki do wysłania skasowane (dziennik i pauza zostają).")
    return 0


def przenies_z_kontenera(u: Uklad, dom_pulpitu: Path) -> dict:
    """Migracja Komputera z kontenera (J16, wołana przez `jarvo migruj`, etap E12): z kopii katalogu domowego
    pulpitu (wolumen `jarvo-komputer-dom`, /home/pulpit) bierze pobrane pliki (`Pobrane/`, bez programów), dziennik
    decyzji (`.jarvo/dziennik.jsonl` i `.1`) i stan pauzy (`.jarvo/pauza`). Profilu przeglądarki nie przenosi:
    właściciel loguje się od nowa (inny Chromium, inne szyfrowanie haseł i ciasteczek). Drugi przebieg niczego nie
    dubluje. Wynik: {"pobrane": n, "odrzucone": n, "dziennik": wiersze, "pauza": bool}."""
    k, przegl = katalogi(u), _przegladarka()
    dom = Path(dom_pulpitu)
    wynik = {"pobrane": 0, "odrzucone": 0, "dziennik": 0, "pauza": False}
    zrodlo = dom / "Pobrane"
    if zrodlo.is_dir():
        k["pobrane"].mkdir(parents=True, exist_ok=True)
        for p in sorted(zrodlo.iterdir()):
            if not p.is_file() or p.is_symlink():
                continue
            if przegl.wykonywalny(p.name):
                wynik["odrzucone"] += 1
                continue
            cel = k["pobrane"] / przegl.czysta_nazwa(p.name)
            if cel.exists() and cel.stat().st_size == p.stat().st_size:
                continue                                  # już przeniesiony
            shutil.copy2(p, k["pobrane"] / przegl.bezpieczna_nazwa(p.name, k["pobrane"]))
            wynik["pobrane"] += 1
    stare = [dom / ".jarvo" / "dziennik.jsonl.1", dom / ".jarvo" / "dziennik.jsonl"]
    wiersze = []
    for p in stare:
        try:
            wiersze += [w for w in p.read_text(encoding="utf-8", errors="replace").splitlines() if w.strip()]
        except OSError:
            pass
    if wiersze:
        k["dziennik"].parent.mkdir(parents=True, exist_ok=True)
        obecne = set(k["dziennik"].read_text(encoding="utf-8").splitlines()) if k["dziennik"].is_file() else set()
        nowe = [w for w in wiersze if w not in obecne]
        if nowe:
            with open(k["dziennik"], "a", encoding="utf-8") as f:
                f.write("".join(w + "\n" for w in nowe))
        wynik["dziennik"] = len(nowe)
    pauza = dom / ".jarvo" / "pauza"
    if pauza.is_file() and not k["pauza"].exists():
        k["pauza"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pauza, k["pauza"])
        wynik["pauza"] = True
    return wynik


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jarvo komputer", description="Komputer Jarva: przeglądarka Jarva dla "
                                "Operatora (osobny profil, filtr ruchu, twarde zasady).")
    sub = p.add_subparsers(dest="akcja", metavar="akcja", title="akcje")
    s = sub.add_parser("on", help="włącz (przy pierwszym razie pobiera przeglądarkę z sumą)")
    tryb = s.add_mutually_exclusive_group()
    tryb.add_argument("--okno", dest="okno", action="store_true", default=None, help="okno na pulpicie")
    tryb.add_argument("--w-tle", dest="okno", action="store_false", help="w tle (--headless=new)")
    s.add_argument("--strona-testowa", metavar="KATALOG", help=argparse.SUPPRESS)
    s.set_defaults(funkcja=polecenie_on)
    s = sub.add_parser("off", help="zatrzymaj (profil i pobrane zostają)")
    s.set_defaults(funkcja=polecenie_off)
    s = sub.add_parser("status", help="stan Komputera")
    s.add_argument("--json", action="store_true")
    s.set_defaults(funkcja=polecenie_status)
    s = sub.add_parser("okno", help="okno przeglądarki na pulpicie (on) albo w tle (off)")
    s.add_argument("stan", choices=("on", "off"), metavar="on|off")
    s.set_defaults(funkcja=polecenie_okno)
    s = sub.add_parser("pauza", help="wstrzymaj Operatora od razu")
    s.add_argument("powod", nargs="*", metavar="powód")
    s.set_defaults(funkcja=polecenie_pauza)
    s = sub.add_parser("wznow", help="zdejmij pauzę (tylko właściciel)")
    s.set_defaults(funkcja=polecenie_wznow)
    s = sub.add_parser("dziennik", help="ostatnie decyzje twardych zasad")
    s.add_argument("n", nargs="?", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.set_defaults(funkcja=polecenie_dziennik)
    s = sub.add_parser("wyczysc", help="skasuj profil przeglądarki, pobrane pliki i pliki do wysłania")
    s.add_argument("--tak", action="store_true", help="bez pytania")
    s.set_defaults(funkcja=polecenie_wyczysc)
    s = sub.add_parser("odswiez", help="przeglądarka z pinu manifestu tej wersji Jarva (pobranie z sumą)")
    s.set_defaults(funkcja=polecenie_odswiez)
    return p


def main(argv: list[str] | None = None, *, u: Uklad | None = None, ot: instalator.Otoczenie | None = None) -> int:
    """`jarvo komputer <akcja>`; kod 0 dobrze, 1 błąd albo Komputer nie działa (status), 2 złe argumenty."""
    ot = ot or instalator.Otoczenie()
    try:
        u = u or sciezki.uklad(ot.env)
    except sciezki.BladUkladu as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    try:
        a = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    if not getattr(a, "funkcja", None):
        _parser().print_help()
        return 2
    try:
        return a.funkcja(u, a, ot)
    except _kanal().BladKanalu as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
