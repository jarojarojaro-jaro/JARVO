"""Panel w sieci Tailscale: `jarvo panel siec on|off|status|wyloguj` i `jarvo panel klucz` (docs/HQ.md „Panel
w sieci”, docs/NATYWNIE.md H10, I11 i N06).

Panel Jarva słucha zawsze na 127.0.0.1:<port> bez hasła. Tryb sieci dokłada w tym samym procesie dashboardu drugi
nasłuch na adresie Tailscale (hq/plugin/siec.py), za bramką z logowaniem kluczem jednorazowym (dostawca `jarvo`
w rejestrze logowania Hermesa). Ten moduł tylko zapisuje ustawienia i sekret, wydaje klucze i pokazuje stan;
nasłuch włącza i wyłącza sam panel w ciągu kilku sekund, bez restartu (bez przerwy w rozmowach i pracy kart).

  jarvo panel siec on [--adres IP] [--nazwa NAZWA]
        adres i nazwa MagicDNS z `tailscale status --json` (zapasowo adres źródłowy trasy do 100.100.100.100, bez
        nazwy), sekret sesji (32 bajty, `<dane>/jarvo/konfig/panel-siec.sekret`, tylko właściciel, nigdy na ekranie
        ani w logach), `<dane>/jarvo/konfig/panel-siec.json` z wlaczony=true; czeka do 15 s, aż panel odpowie w sieci
  jarvo panel siec off        wlaczony=false: panel zamyka nasłuch sieci, 127.0.0.1 bez zmian
  jarvo panel siec status [--json]   ustawienia, stan nasłuchu z panelu, próba GET /api/status w sieci (401 bez sesji
        = bramka działa), ważne klucze, adres Tailscale teraz; samo `jarvo panel siec` to status
  jarvo panel siec wyloguj    nowy sekret: każda sesja (każde urządzenie) traci ważność od razu
  jarvo panel klucz [--waznosc 1h]   klucz JRV-XXXX-XXXX-XXXX (działa raz, domyślnie 1 h, najwyżej 24 h) i link
        `http://<adres>:<port>/login?next=%2Fjarvo#klucz=…` do wysłania właścicielowi; na dysku tylko skrót SHA-256

`on`, `off`, `wyloguj` i `klucz` robi tylko właściciel albo operator w swoim terminalu: wywołane przez proces Jarva
(agent, rutyna, karta kanbana; jarvo/rece.py proces_floty) kończą się odmową. `status` może każdy.
`jarvo status` pokazuje adres w sieci, a `jarvo doctor` ostrzega, gdy tryb jest włączony, a panel w sieci nie
odpowiada (Tailscale wyłączony, panel bez nowej wersji wtyczki), i zgłasza błąd, gdy odpowiada bez logowania.
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import przenosne, przy_uzyciu
from .rece import proces_floty
from .sciezki import MACOS, WINDOWS, Uklad

APP = Path(__file__).resolve().parent.parent
SIEC_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
SIEC_TAILSCALE_6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
RESOLVER_TAILSCALE = "100.100.100.100"
CZAS_TAILSCALE = 15.0
CZEKANIE_NA_PANEL = 15.0
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NAZWA = "panel w sieci"


class BladSieci(RuntimeError):
    """Krok `jarvo panel siec` się nie udał (komunikat po polsku z radą)."""


def siec():
    """hq/plugin/siec.py tej wersji Jarva: jeden wzór plików, klucza i sesji dla panelu i dla CLI."""
    nazwa = "jarvo_hq_siec_cli"
    if nazwa in sys.modules:
        return sys.modules[nazwa]
    spec = importlib.util.spec_from_file_location(nazwa, APP / "hq" / "plugin" / "siec.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[nazwa] = modul
    spec.loader.exec_module(modul)
    return modul


def sciezki(u: Uklad):
    return siec().Sciezki(u.jarvo_dane)


def _port(ot=None) -> int:
    from .instalator import port_panelu
    return port_panelu(ot.env if ot is not None else os.environ)


def _wynik(nazwa: str, stan: str, opis: str, rada: str = "") -> dict:
    return {"nazwa": nazwa, "stan": stan, "opis": opis, "rada": rada}


# ---------------------------------------------------------------- Tailscale

def program_tailscale() -> str | None:
    """CLI Tailscale: z PATH, a gdy go tam nie ma, z miejsca instalacji aplikacji (macOS, Windows)."""
    znaleziony = shutil.which("tailscale")
    if znaleziony:
        return znaleziony
    kandydaci = []
    if MACOS:
        kandydaci.append(Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale"))
    if WINDOWS:
        kandydaci.append(Path(os.environ.get("ProgramFiles") or r"C:\Program Files") / "Tailscale" / "tailscale.exe")
    return next((str(p) for p in kandydaci if p.is_file()), None)


def z_tailscale_status(dane: dict) -> dict:
    """Adres IPv4 i nazwa MagicDNS z `tailscale status --json` (BladSieci, gdy Tailscale nie działa)."""
    stan = dane.get("BackendState")
    if stan != "Running":
        raise BladSieci(f"Tailscale nie jest połączony (stan {stan or '?'}): połącz go (`tailscale up`) i spróbuj "
                        "jeszcze raz.")
    ja = dane.get("Self") if isinstance(dane.get("Self"), dict) else {}
    adresy_ = [str(a) for a in (ja.get("TailscaleIPs") or dane.get("TailscaleIPs") or [])]
    adres = next((a for a in adresy_ if ":" not in a), "")
    if not adres:
        raise BladSieci("Tailscale nie podał adresu IPv4 tego komputera; podaj go sam: --adres 100.x.y.z")
    siec_ = dane.get("CurrentTailnet") if isinstance(dane.get("CurrentTailnet"), dict) else {}
    nazwa = str(ja.get("DNSName") or "").strip().rstrip(".").lower() if siec_.get("MagicDNSEnabled") else ""
    return {"adres": adres, "nazwa": nazwa, "zrodlo": "tailscale status"}


def adres_trasy() -> str:
    """Adres źródłowy trasy do resolvera Tailscale (connect UDP nie wysyła pakietu); "" bez trasy."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((RESOLVER_TAILSCALE, 53))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


def tailscale() -> dict:
    """{"adres", "nazwa", "zrodlo"} tego komputera w sieci Tailscale albo BladSieci z radą."""
    program = program_tailscale()
    if program:
        try:
            r = subprocess.run([program, "status", "--json", "--peers=false"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=CZAS_TAILSCALE, creationflags=NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise BladSieci(f"`tailscale status` nie odpowiedział ({type(e).__name__}); podaj adres sam: "
                            "--adres 100.x.y.z") from e
        if r.returncode == 0:
            try:
                return z_tailscale_status(json.loads(r.stdout))
            except ValueError as e:
                raise BladSieci("`tailscale status --json` dał nie-JSON; podaj adres sam: --adres 100.x.y.z") from e
    adres = adres_trasy()
    try:
        if adres and ipaddress.ip_address(adres) in SIEC_TAILSCALE:
            return {"adres": adres, "nazwa": "", "zrodlo": f"trasa do {RESOLVER_TAILSCALE}"}
    except ValueError:
        pass
    raise BladSieci("Nie widzę Tailscale na tym komputerze: zainstaluj go i połącz (`tailscale up`), albo podaj "
                    "adres sam: --adres 100.x.y.z")


# ---------------------------------------------------------------- adresy i stan

def adresy(ust: dict, port: int, sciezka: str = "/jarvo") -> list[str]:
    hosty = [h for h in (ust.get("adres"), ust.get("nazwa")) if h]
    return [f"http://{'[' + h + ']' if ':' in h else h}:{port}{sciezka}" for h in hosty]


def sprawdz_nasluch(ust: dict, port: int, ot=None) -> tuple[str, str]:
    """Próba GET /api/status na adresie sieci: ("bramka", opis) = 401 od bramki panelu; ("otwarty", opis) =
    odpowiedź bez logowania (błąd); ("brak", opis) = nikt nie odpowiada; ("inny", opis) = coś innego."""
    from .instalator import zapytaj_http
    adres = adresy(ust, port, "/api/status")[0]
    odp = (ot.zapytaj_http if ot is not None else zapytaj_http)(adres, 3.0)
    if odp is None:
        return "brak", f"{adres}: nikt nie odpowiada"
    kod, tresc = odp
    if kod == 401 and isinstance(tresc, dict) and tresc.get("jarvo") == "panel-siec":
        return "bramka", "odpowiada, bez sesji 401 (logowanie kluczem)"
    if kod == 200:
        return "otwarty", f"{adres} odpowiada 200 bez logowania"
    return "inny", f"{adres}: odpowiedź HTTP {kod} nie od bramki panelu Jarva"


def wazne_klucze(sc) -> int:
    teraz = time.time()
    try:
        pliki = [p for p in sc.klucze.iterdir() if not p.name.endswith(".zuzyty")]
    except OSError:
        return 0
    licznik = 0
    for p in pliki:
        try:
            wygasa = json.loads(p.read_text(encoding="utf-8")).get("wygasa", 0)
        except (OSError, ValueError, AttributeError):
            continue
        licznik += isinstance(wygasa, int) and wygasa > teraz
    return licznik


def opis_stanu(u: Uklad, ot=None, *, proba: bool = True) -> dict:
    sc = sciezki(u)
    s = siec()
    ust = s.ustawienia(sc)
    port = _port(ot)
    st = s.stan(sc)
    wynik = {"wlaczony": ust["wlaczony"], "adres": ust["adres"], "nazwa": ust["nazwa"], "port": port,
             "adresy": adresy(ust, port) if ust["adres"] else [], "sekret": sc.sekret.is_file(),
             "nasluch": st.get("nasluch") is True, "blad": st.get("blad"), "od": st.get("od"),
             "klucze": wazne_klucze(sc)}
    if ust["wlaczony"] and proba:
        wynik["proba"], wynik["proba_opis"] = sprawdz_nasluch(ust, port, ot)
    return wynik


# ---------------------------------------------------------------- polecenia

def _odmowa_floty(u: Uklad, co: str) -> int | None:
    znak = proces_floty(dict(os.environ), u.dane)
    if znak is None:
        return None
    print(f"{co} tylko właściciel albo operator, w swoim terminalu. To polecenie wywołał proces Jarva ({znak}): "
          "odmowa.", file=sys.stderr)
    return 1


def _bez_instalacji(u: Uklad) -> int | None:
    if przy_uzyciu.natywnie(u):
        return None
    print(f"Jarvo nie jest zainstalowane natywnie w {u.root}: panel w sieci działa w instalacji natywnej.",
          file=sys.stderr)
    return 1


def _chron(p: Path) -> None:
    przenosne.chron(p, katalog=p.is_dir())


def _czekaj(ust: dict, port: int, ot=None) -> tuple[str, str]:
    termin = time.monotonic() + CZEKANIE_NA_PANEL
    while True:
        stan, opis = sprawdz_nasluch(ust, port, ot)
        if stan in ("bramka", "otwarty") or time.monotonic() >= termin:
            return stan, opis
        time.sleep(1.0)


def polecenie_on(u: Uklad, a, _reszta=(), ot=None) -> int:
    kod = _bez_instalacji(u) or _odmowa_floty(u, "Panel w sieci włącza")
    if kod:
        return kod
    s = siec()
    try:
        if a.adres:
            if not s.adres_poprawny(a.adres):
                raise BladSieci(f"--adres {a.adres!r}: potrzebny konkretny adres IP tego komputera (nie 0.0.0.0, "
                                "nie 127.0.0.1)")
            ts = {"adres": a.adres.strip(), "nazwa": "", "zrodlo": "--adres"}
        else:
            ts = tailscale()
    except BladSieci as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    nazwa = (a.nazwa or ts["nazwa"] or "").strip().rstrip(".").lower()
    if nazwa and not s.nazwa_poprawna(nazwa):
        print(f"BŁĄD: --nazwa {nazwa!r} to nie nazwa hosta (np. serwer.tail1234.ts.net).", file=sys.stderr)
        return 1
    ip = ipaddress.ip_address(ts["adres"])
    if ip not in (SIEC_TAILSCALE if ip.version == 4 else SIEC_TAILSCALE_6):
        print(f"Uwaga: {ts['adres']} nie jest adresem Tailscale; panel będzie widoczny w tej sieci (z logowaniem).")
    sc = sciezki(u)
    sc.ustawienia.parent.mkdir(parents=True, exist_ok=True)
    _chron(sc.ustawienia.parent)
    if not s.Sesje(sc).sekret():
        s.nowy_sekret(sc)
        _chron(sc.sekret)
    s.zapisz_ustawienia(sc, wlaczony=True, adres=ts["adres"], nazwa=nazwa)
    ust = s.ustawienia(sc)
    port = _port(ot)
    print(f"Panel w sieci włączony ({ts['zrodlo']}): " + " i ".join(adresy(ust, port)))
    print("Na 127.0.0.1 panel działa dalej bez hasła. W sieci każde urządzenie loguje się kluczem jednorazowym.")
    stan, opis = _czekaj(ust, port, ot)
    if stan == "bramka":
        print(f"Panel słucha w sieci: {opis}.")
    elif stan == "otwarty":
        print(f"BŁĄD: {opis}. Wyłącz: jarvo panel siec off, i zgłoś to.", file=sys.stderr)
        return 1
    else:
        print(f"Panel jeszcze nie słucha w sieci ({s.stan(sc).get('blad') or opis}). Zacznie sam, gdy panel działa "
              "(jarvo up) i ma wersję wtyczki z trybem sieci (jarvo update); stan: jarvo panel siec status.")
    print("Klucz dla właściciela: jarvo panel klucz")
    return 0


def polecenie_off(u: Uklad, _a, _reszta=(), ot=None) -> int:
    kod = _bez_instalacji(u) or _odmowa_floty(u, "Panel w sieci wyłącza")
    if kod:
        return kod
    s = siec()
    sc = sciezki(u)
    ust = s.ustawienia(sc)
    if not ust["wlaczony"]:
        print("Panel w sieci jest wyłączony.")
        return 0
    s.zapisz_ustawienia(sc, wlaczony=False, adres=ust["adres"], nazwa=ust["nazwa"])
    print("Panel w sieci wyłączony: panel zamknie nasłuch w ciągu kilku sekund; 127.0.0.1 działa jak dotąd. "
          "Zalogowane urządzenia tracą dostęp (po ponownym włączeniu sesje wracają; wylogowanie wszystkich: "
          "jarvo panel siec wyloguj).")
    return 0


def polecenie_wyloguj(u: Uklad, _a, _reszta=(), ot=None) -> int:
    kod = _bez_instalacji(u) or _odmowa_floty(u, "Wszystkich z panelu w sieci wylogowuje")
    if kod:
        return kod
    sc = sciezki(u)
    sc.sekret.parent.mkdir(parents=True, exist_ok=True)
    siec().nowy_sekret(sc)
    _chron(sc.sekret)
    print("Nowy sekret sesji: każde urządzenie w sieci jest wylogowane od razu. Nowe wejście: jarvo panel klucz.")
    return 0


def waznosc(tekst: str) -> int:
    m = re.fullmatch(r"\s*(\d+)\s*([smhd]?)\s*", tekst or "")
    if not m:
        raise ValueError(tekst)
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def polecenie_klucz(u: Uklad, a, _reszta=(), ot=None) -> int:
    kod = _bez_instalacji(u) or _odmowa_floty(u, "Klucz do panelu wydaje")
    if kod:
        return kod
    s = siec()
    sc = sciezki(u)
    ust = s.ustawienia(sc)
    if not ust["wlaczony"] or not s.Sesje(sc).sekret():
        print("BŁĄD: panel w sieci jest wyłączony, klucz nic by nie otworzył. Najpierw: jarvo panel siec on",
              file=sys.stderr)
        return 1
    try:
        sekundy = waznosc(a.waznosc)
    except ValueError:
        print(f"BŁĄD: --waznosc {a.waznosc!r}: np. 30m, 1h, 1d.", file=sys.stderr)
        return 2
    kod_, wygasa = s.wydaj_klucz(sc, sekundy, chron=_chron)
    port = _port(ot)
    print(f"Klucz jednorazowy (działa raz, ważny do {time.strftime('%Y-%m-%d %H:%M', time.localtime(wygasa))}): "
          f"{kod_}")
    print("Link dla właściciela (klucz jest w części po #: nie idzie do serwera z adresem i nie trafia do logów):")
    for adres in adresy(ust, port, "/login?next=%2Fjarvo"):
        print(f"  {adres}#klucz={kod_}")
    print("Bez linku: otwórz adres panelu i wpisz klucz w polu „Klucz jednorazowy”. Po wejściu urządzenie zostaje "
          "zalogowane (sesja odnawia się sama; wygasa po 30 dniach bez wejścia albo po jarvo panel siec wyloguj).")
    return 0


def polecenie_status(u: Uklad, a, _reszta=(), ot=None) -> int:
    r = opis_stanu(u, ot)
    try:
        r["tailscale"] = tailscale()
    except BladSieci as e:
        r["tailscale"] = {"blad": str(e)}
    if getattr(a, "json", False):
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0
    print(f"Panel w sieci: {'włączony' if r['wlaczony'] else 'wyłączony'}")
    if r["adresy"]:
        print(f"  adres:     {' i '.join(r['adresy'])}")
    if r["wlaczony"]:
        if r["nasluch"]:
            print(f"  nasłuch:   słucha od {r.get('od') or '?'}")
        else:
            print(f"  nasłuch:   nie słucha ({r.get('blad') or 'panel nie działa albo nie ma wersji z trybem sieci'})")
        print(f"  próba:     {r.get('proba_opis')}")
        print(f"  klucze:    {r['klucze']} ważnych (nowy: jarvo panel klucz)")
        if not r["sekret"]:
            print("  sekret:    brak (jarvo panel siec on)")
    else:
        print("  włączenie: jarvo panel siec on (adres z Tailscale), potem jarvo panel klucz")
    ts = r["tailscale"]
    if ts.get("adres"):
        inny = r["adres"] and ts["adres"] != r["adres"]
        print(f"  Tailscale: {ts['adres']}" + (f" ({ts['nazwa']})" if ts.get("nazwa") else "")
              + (": inny niż w ustawieniach, popraw: jarvo panel siec on" if inny else ""))
    else:
        print(f"  Tailscale: {ts.get('blad')}")
    return 0


# ---------------------------------------------------------------- jarvo status i jarvo doctor

def do_statusu(u: Uklad, ot=None) -> dict | None:
    """Skrót dla `jarvo status` (bez CLI Tailscale): None, gdy to nie instalacja natywna."""
    if not przy_uzyciu.natywnie(u):
        return None
    try:
        return opis_stanu(u, ot)
    except Exception as e:  # noqa: BLE001 - status nie może paść na trybie opcjonalnym
        return {"wlaczony": None, "blad": f"{type(e).__name__}: {e}"}


def opis_do_statusu(r: dict | None) -> str | None:
    if r is None:
        return None
    if r.get("wlaczony") is None:
        return f"nie sprawdzony ({r.get('blad')})"
    if not r["wlaczony"]:
        return "wyłączony (jarvo panel siec on)"
    adres = " i ".join(r.get("adresy") or [])
    if r.get("proba") == "bramka":
        return f"{adres} (słucha, logowanie kluczem: jarvo panel klucz)"
    if r.get("proba") == "otwarty":
        return f"{adres} (BŁĄD: odpowiada bez logowania)"
    return f"{adres} (nie odpowiada: {r.get('blad') or r.get('proba_opis')})"


def sprawdzenia(u: Uklad, ot=None) -> list[dict]:
    """Wyniki dla `jarvo doctor` (niczego nie zapisują). Tryb sieci jest opcjonalny."""
    if not przy_uzyciu.natywnie(u):
        return []
    r = opis_stanu(u, ot)
    if not r["wlaczony"]:
        return [_wynik(NAZWA, "ok", "wyłączony (opcjonalny): panel tylko na 127.0.0.1; z Maca przez Tailscale: "
                       "jarvo panel siec on")]
    adres = " i ".join(r["adresy"])
    if not r["sekret"]:
        return [_wynik(NAZWA, "blad", f"włączony ({adres}), ale bez sekretu sesji: nikt się nie zaloguje",
                       "jarvo panel siec on (zapisze sekret)")]
    if r["proba"] == "otwarty":
        return [_wynik(NAZWA, "blad", r["proba_opis"], "jarvo panel siec off i zgłoś błąd: panel w sieci ma "
                       "odpowiadać 401 bez sesji")]
    if r["proba"] != "bramka":
        powod = r.get("blad") or r["proba_opis"]
        return [_wynik(NAZWA, "uwaga", f"włączony, ale nie odpowiada w sieci: {powod}",
                       "Sprawdź Tailscale (`tailscale status`; adres zmieniony = jarvo panel siec on), czy panel "
                       "działa (jarvo up) i ma wersję z trybem sieci (jarvo update); stan: jarvo panel siec status")]
    try:
        ts = tailscale()
    except BladSieci:
        ts = {}
    if ts.get("adres") and ts["adres"] != r["adres"]:
        return [_wynik(NAZWA, "uwaga", f"słucha na {r['adres']}, a Tailscale ma teraz {ts['adres']}",
                       "jarvo panel siec on (weźmie nowy adres)")]
    return [_wynik(NAZWA, "ok", f"{adres}: słucha z logowaniem kluczem ({r['klucze']} ważnych kluczy)")]


# ---------------------------------------------------------------- parser

def dodaj_polecenia(panel) -> None:
    """Podpolecenia `jarvo panel` (cli._parser): siec on|off|status|wyloguj i klucz; funkcje biorą (u, a, reszta,
    ot). Samo `jarvo panel` otwiera panel jak dotąd, samo `jarvo panel siec` to status."""
    t = panel.add_subparsers(dest="panel_polecenie", metavar="polecenie", title="panel w sieci Tailscale")
    s = t.add_parser("siec", help="panel w sieci Tailscale: on, off, status, wyloguj",
                     description="Drugi nasłuch panelu na adresie Tailscale z logowaniem kluczem jednorazowym; "
                                 "127.0.0.1 zostaje bez hasła.")
    s.set_defaults(funkcja=polecenie_status, json=False)
    k = s.add_subparsers(dest="siec_polecenie", metavar="polecenie", title="polecenia")
    p = k.add_parser("on", help="włącz: adres z Tailscale, sekret sesji, panel zacznie słuchać sam")
    p.add_argument("--adres", metavar="IP", help="adres tego komputera zamiast wykrytego z Tailscale")
    p.add_argument("--nazwa", metavar="NAZWA", help="nazwa hosta (MagicDNS) zamiast wykrytej z Tailscale")
    p.set_defaults(funkcja=polecenie_on)
    p = k.add_parser("off", help="wyłącz: panel zamyka nasłuch sieci")
    p.set_defaults(funkcja=polecenie_off)
    p = k.add_parser("status", help="ustawienia, nasłuch, próba w sieci, klucze, adres Tailscale")
    p.add_argument("--json", action="store_true")
    p.set_defaults(funkcja=polecenie_status)
    p = k.add_parser("wyloguj", help="nowy sekret: wyloguj od razu wszystkie urządzenia")
    p.set_defaults(funkcja=polecenie_wyloguj)
    s = t.add_parser("klucz", help="klucz jednorazowy i link logowania dla właściciela (panel w sieci)")
    s.add_argument("--waznosc", default="1h", metavar="CZAS", help="jak długo ważny: 30m, 1h (domyślnie), najwyżej 1d")
    s.set_defaults(funkcja=polecenie_klucz)
