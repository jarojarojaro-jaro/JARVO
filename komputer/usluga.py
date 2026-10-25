"""Usługa Komputera Jarva natywnie (docs/NATYWNIE.md J01–J13): jeden proces właściciela, bez kluczy floty.

    python -I -X utf8 <app>/komputer/usluga.py [--korzen <root>] [--okno|--w-tle] [--strona-testowa <katalog>]

Kolejność startu (każdy krok, który się nie uda, kończy usługę: Komputer bez filtra nie wstaje):
  1. blokada `<stan>/komputer/usluga.lock` (jedna usługa na korzeń), token właściciela `wlasciciel.klucz` (nowy przy
     każdym starcie, tylko dla właściciela);
  2. proxy filtrujące na 127.0.0.1 (port od systemu) i samotest: metadane chmury, panel i API Jarva na pętli
     zwrotnej, sieć lokalna i port 25 muszą dostać 403;
  3. przeglądarka Jarva (Chrome for Testing z manifestu, profil `<dane>/jarvo/komputer/profil`, okno widoczne albo
     `--headless=new`) z CDP przez potok, sterownik (sterownik_cdp.py) i samotest przeglądarki: karta z adresem panelu
     Jarva musi pójść przez proxy i zostać odrzucona;
  4. kanały `cua` (MCP dla bramki floty) i `ster` (stan, pauza, wznowienie, dziennik; właściciel: stop, okno,
     wyczyść oraz Ekran w HQ: klatka podglądu, przejmij, wejście właściciela), stan w `<stan>/komputer/usluga.json`.
Pliki, które właściciel wybiera dla strony (pole pliku), HQ kładzie w `<dane>/jarvo/komputer/wysylane`: sterownik
przekazuje stronie tylko pliki z tego katalogu.
Przeglądarka, która padnie, wstaje od nowa z tym samym profilem (przerwa rośnie do 60 s). SIGTERM, SIGINT i Ctrl+Break
(nadzorca Jarva) zatrzymują usługę łagodnie. Na Linuksie bez przestrzeni nazw użytkownika (Ubuntu 24.04 z AppArmor)
przeglądarka startuje drugi raz z `--no-sandbox` i status mówi to wprost (decyzja I41).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_APP = Path(__file__).resolve().parent.parent
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from jarvo import przenosne, sciezki, srodowisko, zmiany_hosta  # noqa: E402
from komputer import cdp, filtr, kanal, przegladarka, sterownik_cdp, wejscie_natywne  # noqa: E402

KOD_BLAD = 1
KOD_FILTR = 3                      # samotest filtra albo przeglądarki nie przeszedł: Komputer nie wstaje
PORT_PANELU = 9119


def log(*a: object) -> None:
    """Wiersz dziennika usługi na stderr (nadzorca i `jarvo komputer on` kierują go do `<logi>/komputer.log`)."""
    if sys.stderr is not None:                     # pythonw.exe bez przekierowania: bez konsoli, bez dziennika
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [komputer]", *a, file=sys.stderr, flush=True)


def katalogi(u: sciezki.Uklad) -> dict[str, Path]:
    """Katalogi Komputera: dane (profil, pobrane, dziennik, pauza; przeżywają aktualizacje i migrację J16) i stan."""
    dane = u.jarvo_dane / "komputer"
    stan = kanal.katalog_stanu(u.root)
    return {"dane": dane, "profil": dane / "profil", "pobrane": dane / "pobrane", "wysylane": dane / "wysylane",
            "stan": stan,
            "ustawienia": stan / "ustawienia.json", "usluga": stan / "usluga.json", "token": stan / "wlasciciel.klucz",
            "blokada": stan / "usluga.lock", "log_przegladarki": u.logi / "komputer-przegladarka.log"}


def ustawienia(u: sciezki.Uklad) -> dict:
    return srodowisko.wczytaj_json(katalogi(u)["ustawienia"])


def zapisz_ustawienia(u: sciezki.Uklad, **zmiany) -> dict:
    k = katalogi(u)
    biezace = ustawienia(u)
    biezace.update({x: y for x, y in zmiany.items()})
    przenosne.zapisz_atomowo(k["ustawienia"], json.dumps(biezace, ensure_ascii=False, indent=2) + "\n")
    return biezace


class Usluga:
    def __init__(self, u: sciezki.Uklad, *, program: str, okno: bool, strona_testowa: Path | None = None,
                 port_panelu: int = PORT_PANELU, port_proxy: int = 0):
        self.u = u
        self.k = katalogi(u)
        self.program = program
        self.okno = okno
        self.strona_testowa = strona_testowa
        self.port_panelu = port_panelu
        self.port_proxy = port_proxy
        self.stop = threading.Event()
        self.zadania: list[tuple[str, dict, threading.Event, dict]] = []
        self._lock = threading.Lock()
        self.proxy: filtr.Proxy | None = None
        self.przegl: cdp.Przegladarka | None = None
        self.sterownik: sterownik_cdp.Sterownik | None = None
        self.wejscie: wejscie_natywne.WejscieNatywne | None = None
        self.serwery: list[kanal.Serwer] = []
        self.bez_piaskownicy = False
        self.samotest: dict = {}
        self.od = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.restarty = 0

    # ------------------------------------------------------------------ przeglądarka

    def _argumenty(self) -> list[str]:
        return przegladarka.flagi(profil=self.k["profil"], port_proxy=self.proxy.port if self.proxy else None,
                                  okno=self.okno, bez_piaskownicy=self.bez_piaskownicy)

    def _env_przegladarki(self) -> dict:
        """Środowisko przeglądarki bez kluczy floty i sekretów właściciela (srodowisko.przechodzi). Linux: katalogi
        XDG w katalogu Komputera: Chrome trzyma raporty awarii w domyślnym katalogu danych mimo --user-data-dir,
        a do tego bazę NSS i cache fontconfig (CI natywnie: ~/.config/google-chrome-for-testing, ~/.local/share/pki,
        ~/.cache/fontconfig zostawały po odinstalowaniu)."""
        env = {k: v for k, v in os.environ.items() if srodowisko.przechodzi(k)
               and not k.upper().startswith(("HERMES_", "JARVO_"))}
        if sciezki.LINUX:
            env["LANGUAGE"] = "pl"                 # Linux: język interfejsu z otoczenia (--lang tam nie działa)
            xdg = self.k["profil"].parent / "xdg"
            env.update({"XDG_CONFIG_HOME": str(xdg / "config"), "XDG_CACHE_HOME": str(xdg / "cache"),
                        "XDG_DATA_HOME": str(xdg / "data")})
        return env

    def _slad_raportow_awarii(self) -> None:
        """macOS i Windows: Chrome for Testing zakłada domyślny katalog danych dla raportów awarii (Crashpad) mimo
        --user-data-dir (chrome_paths.cc, DIR_CRASH_DUMPS). Gdy go jeszcze nie ma, wpis w dzienniku zmian hosta przed
        startem: `jarvo uninstall` usunie go, jeśli w środku są tylko raporty awarii (cudzego nie rusza)."""
        if sciezki.MACOS:
            cel = Path.home() / "Library" / "Application Support" / "Google" / "Chrome for Testing"
            dozwolone = ["Crashpad"]
        elif sciezki.WINDOWS and os.environ.get("LOCALAPPDATA"):
            cel = Path(os.environ["LOCALAPPDATA"]) / "Google" / "Chrome for Testing"
            dozwolone = ["User Data/Crashpad"]
        else:
            return
        try:
            zmiany_hosta.katalog_przed_zmiana(self.u, cel, dozwolone)
        except OSError as e:
            log(f"dziennik zmian hosta: nie zapisałem katalogu raportów przeglądarki ({e})")

    def uruchom_przegladarke(self) -> None:
        przegladarka.przygotuj_profil(self.k["profil"], self.k["pobrane"])
        self._slad_raportow_awarii()
        self.k["log_przegladarki"].parent.mkdir(parents=True, exist_ok=True)
        for proba in range(2):
            b = cdp.Przegladarka(self.program, self._argumenty(), env=self._env_przegladarki(),
                                 log=self.k["log_przegladarki"])
            b.start()
            try:
                b.wyslij("Browser.getVersion", czas=30)
            except cdp.BladCDP as e:
                b.zamknij(5)
                if sciezki.LINUX and not self.bez_piaskownicy and proba == 0 and self._brak_piaskownicy():
                    log("przeglądarka nie wstała z piaskownicą (brak przestrzeni nazw użytkownika): start z "
                        "--no-sandbox; zainstaluj profil AppArmor (docs/NATYWNIE.md I41)")
                    self.bez_piaskownicy = True
                    continue
                raise RuntimeError(f"przeglądarka Jarva nie wstała: {e.tekst}") from None
            break
        self.k["wysylane"].mkdir(parents=True, exist_ok=True)
        st = sterownik_cdp.Sterownik(b, pobrane=self.k["pobrane"], w_tle=not self.okno,
                                     strona_testowa=self.strona_testowa, log=log, wysylane=self.k["wysylane"])
        st.start()
        self.przegl, self.sterownik = b, st
        if self.wejscie is not None:
            self.wejscie.sterownik = st
        log(f"przeglądarka: {st.produkt} (pid {b.pid}), {'okno widoczne' if self.okno else 'w tle'}"
            + (", BEZ piaskownicy" if self.bez_piaskownicy else ""))

    def _brak_piaskownicy(self) -> bool:
        try:
            ogon = self.k["log_przegladarki"].read_text(encoding="utf-8", errors="replace")[-4000:]
        except OSError:
            return False
        return "sandbox" in ogon.lower() and ("namespace" in ogon.lower() or "no usable sandbox" in ogon.lower())

    def zatrzymaj_przegladarke(self) -> None:
        if self.wejscie is not None:
            self.wejscie.sterownik = None
        b, self.przegl, self.sterownik = self.przegl, None, None
        if b is not None:
            b.zamknij(10)

    def samotest_przegladarki(self) -> dict:
        """Karta z adresem panelu Jarva (https, więc CONNECT) ma pójść przez proxy i dostać odmowę filtra."""
        przed = self.proxy.statystyki.zablokowane
        cel = self.przegl.wyslij("Target.createTarget", {"url": f"https://127.0.0.1:{self.port_panelu}/jarvo-samotest"})
        koniec = time.monotonic() + 15
        while time.monotonic() < koniec and self.proxy.statystyki.zablokowane == przed:
            time.sleep(0.1)
        try:
            self.przegl.wyslij("Target.closeTarget", {"targetId": cel["targetId"]}, czas=5)
        except cdp.BladCDP:
            pass
        ok = any(c == f"127.0.0.1:{self.port_panelu}" for _, c, _ in list(self.proxy.statystyki.ostatnie))
        return {"ok": ok, "cel": f"https://127.0.0.1:{self.port_panelu}/"}

    # ------------------------------------------------------------------ polecenia właściciela (kanał ster)

    def polecenie(self, co: str, p: dict) -> dict:
        if co == "stan":
            return self.stan()
        if co == "stop":
            self.stop.set()
            return {"ok": True, "stop": True}
        gotowe, wynik = threading.Event(), {}
        with self._lock:
            self.zadania.append((co, p, gotowe, wynik))
        if not gotowe.wait(90):
            return {"ok": False, "blad": f"{co}: usługa nie skończyła w 90 s"}
        return wynik or {"ok": True}

    def _wykonaj(self, co: str, p: dict) -> dict:
        if co == "okno":
            self.okno = bool(p.get("okno"))
            zapisz_ustawienia(self.u, okno=self.okno)
            self.zatrzymaj_przegladarke()
            self.uruchom_przegladarke()
            return {"ok": True, "okno": self.okno}
        if co == "restart":
            self.zatrzymaj_przegladarke()
            self.uruchom_przegladarke()
            return {"ok": True}
        if co == "wyczysc":
            self.zatrzymaj_przegladarke()
            for nazwa in ("profil", "pobrane", "wysylane"):
                shutil.rmtree(self.k[nazwa], ignore_errors=True)
            self.uruchom_przegladarke()
            return {"ok": True, "wyczyszczone": ["profil", "pobrane", "wysylane"]}
        return {"ok": False, "blad": f"nieznane polecenie {co}"}

    def stan(self) -> dict:
        st = self.sterownik
        return {"pid": os.getpid(), "od": self.od, "okno": self.okno, "program": self.program,
                "przegladarka": getattr(st, "produkt", None), "pid_przegladarki": self.przegl.pid if self.przegl else None,
                "dziala": bool(self.przegl and self.przegl.dziala()), "proxy": self.proxy.port if self.proxy else None,
                "filtr": self.proxy.statystyki.slownik() if self.proxy else {},
                "pobrania": dict(st.statystyki) if st else {}, "okna": len(st.okna()) if st else 0,
                "podglad": st is not None and st.podglad_wlaczony,
                "piaskownica": not self.bez_piaskownicy, "samotest": self.samotest, "restarty": self.restarty,
                "strona_testowa": self.strona_testowa is not None}

    def _zapisz_stan(self) -> None:
        dane = {**self.stan(), "cua": kanal.adres(self.u.root, "cua"), "ster": kanal.adres(self.u.root, "ster"),
                "zapisano": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        przenosne.zapisz_atomowo(self.k["usluga"], json.dumps(dane, ensure_ascii=False, indent=2) + "\n")

    # ------------------------------------------------------------------ cykl życia

    def uruchom(self) -> int:
        self.k["stan"].mkdir(parents=True, exist_ok=True)
        try:
            przenosne.chron(self.k["stan"], katalog=True)
        except OSError as e:
            log(f"ochrona katalogu stanu: {e}")
        zamek = przenosne.Zamek(self.k["blokada"], czekaj=False)
        try:
            zamek.__enter__()
        except BlockingIOError:
            log("usługa Komputera już działa dla tego korzenia")
            return KOD_BLAD
        try:
            return self._uruchom_pod_blokada()
        finally:
            self._sprzatnij()
            zamek.__exit__(None, None, None)

    def _uruchom_pod_blokada(self) -> int:
        token = secrets.token_urlsafe(32)
        przenosne.zapisz_atomowo(self.k["token"], token, tryb=0o600)
        przenosne.chron(self.k["token"], katalog=False)
        self.proxy = filtr.Proxy(log=log, port=self.port_proxy)
        port = self.proxy.start()
        test = filtr.samotest(port, self.port_panelu)
        self.samotest = {"filtr": test}
        if not test["ok"]:
            zle = [c["cel"] for c in test["cele"] if c["kod"] != 403]
            log(f"BŁĄD: filtr ruchu przepuścił albo nie odpowiedział dla {', '.join(zle)}: Komputer nie wstaje")
            return KOD_FILTR
        log(f"filtr ruchu: proxy 127.0.0.1:{port}, samotest {len(test['cele'])} adresów zakazanych: odrzucone")
        try:
            self.uruchom_przegladarke()
        except (RuntimeError, OSError) as e:
            log(f"BŁĄD: {e}")
            return KOD_BLAD
        test_b = self.samotest_przegladarki()
        self.samotest["przegladarka"] = test_b
        if not test_b["ok"]:
            log("BŁĄD: przeglądarka nie poszła przez filtr ruchu do panelu Jarva: Komputer nie wstaje")
            return KOD_FILTR
        log("filtr ruchu: przeglądarka idzie przez proxy (adres panelu Jarva odrzucony)")
        self.wejscie = wejscie_natywne.WejscieNatywne(self.k["dane"], token, self.polecenie)
        self.wejscie.sterownik = self.sterownik
        for nazwa, obsluga in (("ster", self.wejscie.obsluz_ster), ("cua", self.wejscie.obsluz_cua)):
            self.serwery.append(kanal.Serwer(kanal.adres(self.u.root, nazwa), obsluga, nazwa).start())
        self._zapisz_stan()
        log(f"gotowe: kanały {kanal.adres(self.u.root, 'cua')} i {kanal.adres(self.u.root, 'ster')}, pauza "
            f"{'tak' if self.wejscie.ekran.wstrzymane else 'nie'}")
        return self._petla()

    def _petla(self) -> int:
        przerwa, ostatni_zapis = 2.0, time.monotonic()
        while not self.stop.is_set():
            self.stop.wait(0.25)
            with self._lock:
                zadania, self.zadania = self.zadania, []
            for co, p, gotowe, wynik in zadania:
                try:
                    wynik.update(self._wykonaj(co, p))
                except Exception as e:  # noqa: BLE001 - polecenie właściciela nie zatrzymuje usługi
                    wynik.update(ok=False, blad=f"{co}: {type(e).__name__}: {e}")
                gotowe.set()
                self._zapisz_stan()
            if self.sterownik is not None:
                try:
                    self.sterownik.podglad_bezczynny()          # podgląd bez widza staje (procesor)
                except cdp.BladCDP:
                    pass
            if self.przegl is not None and not self.przegl.dziala() and not self.stop.is_set():
                log(f"przeglądarka Jarva skończyła pracę; start od nowa za {przerwa:g} s")
                self.stop.wait(przerwa)
                przerwa = min(przerwa * 2, 60.0)
                self.zatrzymaj_przegladarke()
                try:
                    self.uruchom_przegladarke()
                    self.restarty += 1
                except (RuntimeError, OSError) as e:
                    log(f"przeglądarka nie wstała: {e}")
                self._zapisz_stan()
            if time.monotonic() - ostatni_zapis > 30:
                przerwa = max(2.0, przerwa / 2)
                self._zapisz_stan()
                ostatni_zapis = time.monotonic()
        log("zatrzymanie")
        return 0

    def _sprzatnij(self) -> None:
        for s in self.serwery:
            try:
                s.zamknij()
            except OSError:
                pass
        if self.wejscie is not None:
            for sesja in list(self.wejscie.sesje):
                try:
                    sesja.zamknij()
                except OSError:
                    pass
        self.zatrzymaj_przegladarke()
        if self.proxy is not None:
            self.proxy.zatrzymaj()
        for nazwa in ("usluga", "token"):
            try:
                self.k[nazwa].unlink()
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="komputer-usluga", description="Usługa Komputera Jarva (przeglądarka Jarva).")
    p.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT)")
    tryb = p.add_mutually_exclusive_group()
    tryb.add_argument("--okno", action="store_true", default=None, help="okno przeglądarki widoczne na pulpicie")
    tryb.add_argument("--w-tle", dest="okno", action="store_false", help="przeglądarka w tle (--headless=new)")
    p.add_argument("--strona-testowa", metavar="KATALOG", help="próby: strona z katalogu pod https://*.jarvo.test/")
    p.add_argument("--przegladarka", metavar="PROGRAM", help="program przeglądarki (jarvo komputer on podaje pin z "
                   "manifestu); bez niego zmienna próby albo ustawienia Komputera")
    p.add_argument("--port-proxy", type=int, default=int(os.environ.get("JARVO_KOMPUTER_PORT_PROXY") or 0),
                   help="port proxy filtrującego na 127.0.0.1 (domyślnie dowolny wolny)")
    a = p.parse_args(argv)
    if a.korzen:
        os.environ["JARVO_ROOT"] = os.path.abspath(a.korzen)
    try:
        u = sciezki.uklad()
    except sciezki.BladUkladu as e:
        log(f"BŁĄD: {e}")
        return KOD_BLAD
    ust = ustawienia(u)
    program = a.przegladarka or przegladarka.program(os.environ, srodowisko.narzedzia(u)) or ust.get("chrome")
    if not program or not Path(program).is_file():
        log("BŁĄD: nie ma przeglądarki Jarva (Chrome for Testing): `jarvo komputer on` pobierze ją z sumą")
        return KOD_BLAD
    okno = a.okno if a.okno is not None else bool(ust.get("okno"))
    port = os.environ.get("JARVO_PANEL_PORT") or srodowisko.wczytaj_json(u.stan / "ustawienia.json").get(
        "JARVO_PANEL_PORT") or PORT_PANELU
    usluga = Usluga(u, program=program, okno=okno, port_panelu=int(port), port_proxy=a.port_proxy,
                    strona_testowa=Path(a.strona_testowa).resolve() if a.strona_testowa else None)
    for nazwa in ("SIGTERM", "SIGINT", "SIGBREAK"):
        if hasattr(signal, nazwa):
            signal.signal(getattr(signal, nazwa), lambda *_: usluga.stop.set())
    return usluga.uruchom()


if __name__ == "__main__":
    sys.exit(main())
