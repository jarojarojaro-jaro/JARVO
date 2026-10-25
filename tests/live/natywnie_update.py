#!/usr/bin/env python3
"""Test na żywo `jarvo update`, przycisku aktualizacji w panelu i `jarvo uninstall` na zainstalowanym korzeniu Jarva
(docs/NATYWNIE.md: N09, N11, c4, S09, T08; etapy E4 i E13), z zewnątrz, tak jak pracuje właściciel: polecenie jarvo,
panel przez HTTP na 127.0.0.1 (token sesji z index.html, bez hasła) i pliki stanu. Do pełnej macierzy instalacji
natywnej (po drugim przebiegu instalacji) i do prób na komputerze z instalacją próbną (JARVO_ROOT). Sama biblioteka
standardowa i pakiet jarvo/ tego repo; punkty raportu, uruchamianie i polecenie jarvo bierze z natywnie_e2e.py.

Nowsze wersje to kopie bieżącego kodu instalacji z innym `.jarvo-wersja` (SHA testowy), podane przez JARVO_FAKE_KOD
(jarvo/aktualizacja.py): `jarvo update` widzi je jak nowe wydanie na GitHubie, ale bez sieci i bez pushowania.
Pomocnik aktualizacji pod nadzorcą dostaje JARVO_FAKE_KOD z otoczenia nadzorcy: test zatrzymuje serwis (`jarvo down`)
i uruchamia `jarvo serwis --wznow` w tle z tą zmienną (autostart by jej nie przekazał); katalog kopii jest stały,
a nową wersję test podkłada, zmieniając jego treść. Na końcu serwis wraca bez tej zmiennej (`jarvo down`, `jarvo up`).

  aktualizacja [--korzen R] [--zrodla KATALOG] [--bez-wycofania] [--bez-panelu] [--limit S]
      1. ta sama wersja: `jarvo update --json` → „aktualne”; `<program>` (bez __pycache__), current.json,
         narzedzia.json, srodowisko.json, ustawienia.json i polecenie jarvo bez zmian,
      2. GitHub (tylko odczyt): `jarvo update --sprawdz --json` z refem instalacji; bez sieci albo przy limicie API:
         pominięte,
      3. nowsza wersja: „zaktualizowano”, current.json na `<program>/app/<sha12>`, serwis i panel jak przed
         aktualizacją (`jarvo status --json`), doctor bez regresji, front panelu na dysku,
      4. (bez --bez-wycofania) wersja, której nadzorca nie wstaje: „wycofano”, current.json z kroku 3, serwis działa,
      5. (bez --bez-panelu) pomocnik pod nadzorcą: serwis z JARVO_FAKE_KOD, usługa `aktualizacje` działa (`jarvo
         status`), panel widzi go online (GET /api/plugins/jarvo-hq/update),
      6. przycisk „Aktualizuj” w panelu: POST /update {action: check}, potem {action: update} → update.json
         „done” z nową wersją, current.json na niej, serwis i panel działają,
      7. „Zaktualizuj, gdy skończą”: POST /update {action: update, gdy: wolne} = 202 i `po_pracy`, prośbę zapisuje
         obserwator panelu po 30 s bez pracy, pomocnik ją zabiera → „done”,
      8. sprzątanie: znowu ta sama wersja usuwa stare wersje kodu, z których nic nie korzysta (zostaje bieżąca).
  odinstalowanie [--korzen R] [--migawka-przed PLIK]
      `jarvo uninstall --all --yes --json`, czekanie na proces sprzątający (Windows), potem migawka: korzeń, logi
      i cache usunięte, PATH użytkownika, blok w pliku startowym, polecenie jarvo, autostart i procesy bez śladów
      tej instalacji, w katalogu nad korzeniem bez nowych wpisów z „jarvo” albo „hermes” w nazwie; raport polecenia
      bez śladów (proces, który uruchomił ten test, np. `bash -c "… natywnie_update.py … --korzen R"`, ma korzeń
      w wierszu polecenia, ale śladem Jarva nie jest: pomijamy go z opisem). Z --migawka-przed (migawka natywnie_e2e.py
      sprzed instalacji) także różnica migawek komputera (natywnie_e2e.roznica, pusta poza wyjątkami z powodem; wynik
      w <artefakty>/roznica.json).
  wszystko [...]: aktualizacja, potem odinstalowanie.

Wynik: punkty w <artefakty>/raport.json (ten sam plik co natywnie_e2e.py, więc `podsumowanie` pokazuje je razem),
szczegóły i czas każdego kroku w <artefakty>/raport-update.json (raport-odinstalowanie.json), wyjście poleceń
w <artefakty>/update-*.log, a na końcu podsumowanie JSON na stdout: {"test", "polecenie", "kod", "czas_s", "punkty"}.
Kod 0 = żaden punkt nie padł (pominięty z powodem to nie błąd), 1 = któryś padł albo skończył się limit czasu
(--limit, domyślnie 4200 s: kolejne kroki są wtedy pominięte z powodem), 2 = złe argumenty. Kopie kodu leżą
w katalogu tymczasowym (albo w --zrodla) i znikają na końcu.

    python -X utf8 -B tests/live/natywnie_update.py aktualizacja
    python -X utf8 -B tests/live/natywnie_update.py wszystko --korzen D:\\JarvoTest\\fala4-update\\root \\
        --zrodla D:\\JarvoTest\\fala4-update\\zrodla --artefakty D:\\JarvoTest\\fala4-update\\artefakty \\
        --migawka-przed D:\\JarvoTest\\fala4-update\\artefakty\\migawka-przed.json
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

TU = Path(__file__).resolve().parent
if str(TU) not in sys.path:
    sys.path.insert(0, str(TU))
import natywnie_e2e as e2e  # noqa: E402  (dodaje też katalog repo do sys.path)
from jarvo import aktualizacja, instalator, odinstalowanie, srodowisko  # noqa: E402

WINDOWS = os.name == "nt"
POMIN_KOPII = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache", "node_modules")
ZEPSUTY_NADZORCA = ('\n\ndef main(argv=None):  # wersja testowa natywnie_update.py: nadzorca nie wstaje\n'
                    '    print("natywnie_update: ten nadzorca celowo nie startuje", file=sys.stderr)\n'
                    '    return 1\n')
SLAD = re.compile(r"jarvo|hermes", re.I)
TOKEN = re.compile(r'window\.__HERMES_SESSION_TOKEN__="([^"]+)"')
API_UPDATE = "/api/plugins/jarvo-hq/update"
CZAS_UPDATE = 3600.0                  # s na jedną aktualizację (instalator nowej wersji)
CZAS_SERWISU = 240.0                  # s na start serwisu z panelem i pomocnikiem
CZAS_PO_PRACY = 300.0                 # s na prośbę obserwatora („gdy skończą”: 30 s ciszy) i zabranie przez pomocnika
LIMIT = 4200.0                        # s na całe `aktualizacja` (CI: krok z timeout-minutes 80)


# ---------------------------------------------------------------- pomocnicze

class Budzet:
    """Limit czasu całego przebiegu: każdy krok bierze najwyżej tyle, ile zostało; po limicie kroki są pomijane."""

    def __init__(self, limit: float):
        self.t0, self.limit = time.monotonic(), float(limit)

    def zostalo(self) -> float:
        return self.limit - (time.monotonic() - self.t0)

    def czas(self, domyslny: float) -> float:
        return max(30.0, min(domyslny, self.zostalo()))

    def koniec(self) -> bool:
        return self.zostalo() <= 30


def sha_testowy(nazwa: str) -> str:
    """Pełny SHA, którego nie ma w repo (wersja testowa)."""
    return hashlib.sha1(f"jarvo-natywnie-update-{nazwa}-{time.time_ns()}".encode()).hexdigest()


def kopia_kodu(app: Path, cel: Path, sha: str, *, zepsuj_nadzorce: bool = False) -> Path:
    """Kopia kodu Jarva z innym `.jarvo-wersja`; z `zepsuj_nadzorce` `jarvo serwis` tej wersji od razu kończy się
    kodem 1 (instalator nie doczeka się panelu, więc `jarvo update` ma wrócić do poprzedniej wersji)."""
    if cel.exists():
        odinstalowanie.usun_drzewo(cel)
    shutil.copytree(app, cel, ignore=POMIN_KOPII, symlinks=not WINDOWS)
    (cel / ".jarvo-wersja").write_text(sha + "\n", encoding="utf-8")
    if zepsuj_nadzorce:
        with open(cel / "jarvo" / "nadzorca.py", "a", encoding="utf-8") as f:
            f.write(ZEPSUTY_NADZORCA)
    return cel


def wolanie(inst: e2e.Instalacja) -> list[str]:
    """Jak uruchomić polecenie jarvo tej instalacji. Zwykle jej polecenie (jarvo.cmd, ~/.local/bin/jarvo). Windows,
    kod spoza `<program>/app` (instalacja z kopii repo): aktualizacja przepisze jarvo.cmd na ścieżkę innej długości,
    a cmd.exe czyta plik wsadowy dalej od starego miejsca, więc wtedy wprost Pythonem Jarva."""
    app = inst.app
    if inst.jarvo is not None and (not WINDOWS or odinstalowanie.w_katalogu(str(app), inst.u.program / "app")):
        return [str(inst.jarvo)]
    return [str(instalator.python_jarva(inst.u)), "-I", "-X", "utf8", str(app / "jarvo" / "start.py"),
            *instalator.argumenty_korzenia(inst.u)]


def jarvo(inst: e2e.Instalacja, *argumenty: str, fake: Path | None = None, czas: float = 600) -> e2e.Wynik:
    env = inst.env_terminala()
    env.pop(aktualizacja.FAKE, None)
    if fake is not None:
        env[aktualizacja.FAKE] = str(fake)
    return e2e.uruchom([*wolanie(inst), *argumenty], czas=czas, env=env)


def zapisz_log(art: Path, nazwa: str, w: e2e.Wynik) -> None:
    (art / f"update-{nazwa}.log").write_text(e2e.bez_sekretow(e2e.bez_ansi(w.tekst)), encoding="utf-8")


def migawka_programu(u) -> dict[str, Any]:
    """Pliki `<program>` (rozmiar i czas zmiany, bez __pycache__ i .pyc: Python je dopisuje przy imporcie) i pliki
    stanu instalacji (treść), do sprawdzenia „ta sama wersja = nic”."""
    wpisy: dict[str, Any] = {}
    for korzen, katalogi, pliki in os.walk(u.program):
        katalogi[:] = [k for k in katalogi if k != "__pycache__"]
        for p in pliki:
            if p.endswith(".pyc"):
                continue
            sciezka = os.path.join(korzen, p)
            with contextlib.suppress(OSError):
                st = os.lstat(sciezka)
                wpisy[os.path.relpath(sciezka, u.program)] = (st.st_size, st.st_mtime_ns)
    for p in (u.program / "current.json", u.stan / "narzedzia.json", u.stan / "srodowisko.json",
              u.stan / "ustawienia.json", u.root / "bin" / ("jarvo.cmd" if WINDOWS else "jarvo")):
        wpisy[f"tresc:{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    return wpisy


def status(inst: e2e.Instalacja) -> dict:
    r = inst.jarvo_cmd("status", "--json", czas=180)
    s = e2e.json_z_wyjscia(r.out)
    return s if isinstance(s, dict) else {}


def dziala(s: dict) -> bool:
    return bool((s.get("serwis") or {}).get("dziala")) and (s.get("panel_jarva") or {}).get("stan") == "nasz"


def usluga(s: dict, nazwa: str) -> dict:
    return instalator.usluga_nadzorcy((s.get("serwis") or {}).get("stan"), nazwa)


def front_jest(u) -> bool:
    """Front panelu z current.json (`web_dist`) jest na dysku: sprzątanie nie może go zabrać (panel odpowiada na
    /api/status także bez niego, więc sam status tego nie pokaże)."""
    w = srodowisko.biezace(u).get("web_dist")
    return not w or (Path(str(w)) / "index.html").is_file()


def update_json(inst: e2e.Instalacja, *argumenty: str, fake: Path | None, art: Path, nazwa: str,
                czas: float = CZAS_UPDATE) -> tuple[e2e.Wynik, dict]:
    w = jarvo(inst, "update", "--json", *argumenty, fake=fake, czas=czas)
    zapisz_log(art, nazwa, w)
    raport = e2e.json_z_wyjscia(w.out)
    return w, raport if isinstance(raport, dict) else {}


def czekaj(warunek: Callable[[], Any], czas: float, co_ile: float = 3.0) -> Any:
    """Wynik `warunek()`, gdy prawdziwy, albo ostatni wynik po `czas` sekundach."""
    koniec = time.monotonic() + czas
    while True:
        wynik = warunek()
        if wynik or time.monotonic() >= koniec:
            return wynik
        time.sleep(co_ile)


# ---------------------------------------------------------------- panel i serwis z pomocnikiem

def panel(inst: e2e.Instalacja, metoda: str, sciezka: str, cialo: Any = None, czas: float = 20) -> tuple[int, Any]:
    """Trasa wtyczki HQ panelu tej instalacji jak z przeglądarki: token sesji z index.html (127.0.0.1 bez hasła),
    nagłówek panelu (ochrona zapisu), bez proxy systemu. (0, opis) = panel nie odpowiada (np. restart przy
    aktualizacji). Token nie trafia do wyniku."""
    otwieracz = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f"http://127.0.0.1:{inst.port_panelu()}"
    try:
        with otwieracz.open(urllib.request.Request(base + "/", headers={"User-Agent": "jarvo-e2e"}), timeout=czas) as r:
            m = TOKEN.search(r.read(4 << 20).decode("utf-8", "replace"))
        if not m:
            return 0, "index.html bez tokenu sesji"
        dane = None if cialo is None else json.dumps(cialo).encode("utf-8")
        zadanie = urllib.request.Request(base + sciezka, data=dane, method=metoda, headers={
            "X-Hermes-Session-Token": m.group(1), "X-Jarvo-Request": "1", "Content-Type": "application/json",
            "User-Agent": "jarvo-e2e"})
        try:
            with otwieracz.open(zadanie, timeout=czas) as r:
                status_http, tresc = r.status, r.read(4 << 20)
        except urllib.error.HTTPError as e:
            status_http, tresc = e.code, e.read(1 << 20)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, type(e).__name__
    try:
        return status_http, json.loads(tresc.decode("utf-8", "replace") or "null")
    except ValueError:
        return status_http, tresc[:300].decode("utf-8", "replace")


def serwis_z_otoczeniem(inst: e2e.Instalacja, art: Path, dodatki: dict[str, str], nazwa: str,
                        czas: float = CZAS_SERWISU) -> tuple[bool, dict, str]:
    """Serwis od nowa z dodatkowymi zmiennymi (JARVO_FAKE_KOD dla pomocnika pod nadzorcą): `jarvo down`, potem `jarvo
    serwis --wznow` w tle (jak instalator.uruchom_serwis bez autostartu: otoczenie bez sekretów, wyjście w
    <logi>/serwis-start.log). (gotowe, status, opis): serwis i panel działają, a usługa `aktualizacje` też."""
    u = inst.u
    w = jarvo(inst, "down", czas=300)
    zapisz_log(art, f"{nazwa}-down", w)
    env = instalator.env_floty(inst.env_terminala())
    env.pop(aktualizacja.FAKE, None)
    env.update(dodatki)
    argv = instalator.polecenie_jarva(u, "serwis", "--wznow", okno=False, env=env)
    pid = instalator.uruchom_w_tle(argv, env, u.logi / instalator.LOG_STARTU)
    s = czekaj(lambda: (lambda x: x if dziala(x) and usluga(x, "aktualizacje").get("stan") == "dziala" else None)(
        status(inst)), czas, 5) or status(inst)
    gotowe = dziala(s) and usluga(s, "aktualizacje").get("stan") == "dziala"
    return gotowe, s, f"jarvo down: kod {w.kod}; jarvo serwis --wznow w tle (PID {pid})"


def czekaj_na_koniec(u, od: float, czas: float) -> dict:
    """update.json „done” albo „failed” z finished_at po `od` i bez trwającej aktualizacji (blokada wolna). Czytamy
    plik, nie panel: panel startuje od nowa razem z serwisem w trakcie aktualizacji."""
    def gotowe():
        s = aktualizacja.stan_panelu(u)
        if s.get("state") in ("done", "failed") and float(s.get("finished_at") or 0) >= od \
                and not aktualizacja.trwa(u):
            return s
        return None
    return czekaj(gotowe, czas, 3) or aktualizacja.stan_panelu(u)


def kod_z_aktualizacji(u) -> str:
    return (aktualizacja.wersja_kodu(srodowisko.biezace(u).get("app")) or "")[:12]


def _krok_pomocnika(inst: e2e.Instalacja, rap: e2e.Raport, art: Path, z_panelu: Path, sha: str, nazwa: str,
                    szczegoly: dict, budzet: Budzet) -> bool:
    """Serwis z JARVO_FAKE_KOD i pomocnik online w panelu, potem „Sprawdź” z panelu: update.json z `latest` = sha."""
    t0 = time.monotonic()
    gotowe, s, opis = serwis_z_otoczeniem(inst, art, {aktualizacja.FAKE: str(z_panelu)}, nazwa,
                                          budzet.czas(CZAS_SERWISU))
    us = usluga(s, "aktualizacje")
    stan_panelu = czekaj(lambda: (lambda x: x if isinstance(x[1], dict) and x[1].get("online") else None)(
        panel(inst, "GET", API_UPDATE)), 120, 3) or panel(inst, "GET", API_UPDATE)
    online = isinstance(stan_panelu[1], dict) and bool(stan_panelu[1].get("online"))
    od = time.time()
    kod_post, odp = panel(inst, "POST", API_UPDATE, {"action": "check"})
    sprawdzone = czekaj(lambda: (lambda x: x if x.get("latest") == sha[:7] and float(x.get("checked_at") or 0) >= od
                                 else None)(aktualizacja.stan_panelu(u=inst.u)), 120, 2) or {}
    ok = gotowe and online and kod_post == 202 and sprawdzone.get("behind") == 1
    szczegoly["kroki"][nazwa] = {"czas_s": round(time.monotonic() - t0, 1), "serwis": opis,
                                 "aktualizacje": us, "panel": stan_panelu[1] if isinstance(stan_panelu[1], dict)
                                 else str(stan_panelu[1]), "check": [kod_post, odp], "update.json": sprawdzone}
    rap.punkt(f"update-{nazwa}", "pomocnik pod nadzorcą: usługa „aktualizacje”, panel online, „Sprawdź” z panelu", ok,
              f"{opis}; usługa aktualizacje: {us.get('stan')} (PID {us.get('pid')}); panel GET /update: "
              f"{'online' if online else stan_panelu}; POST check: {kod_post}; update.json: latest "
              f"{sprawdzone.get('latest')} (oczekiwany {sha[:7]}), behind {sprawdzone.get('behind')}",
              czas_s=round(time.monotonic() - t0, 1))
    return ok


def _aktualizacja_z_panelu(inst: e2e.Instalacja, rap: e2e.Raport, art: Path, sha: str, ident: str, opis_punktu: str,
                           cialo: dict, szczegoly: dict, budzet: Budzet) -> None:
    """POST /update z `cialo` (przycisk albo „gdy skończą”) i czekanie na koniec w update.json."""
    u = inst.u
    t0, od = time.monotonic(), time.time()
    kod_post, odp = panel(inst, "POST", API_UPDATE, cialo)
    po_pracy = None
    if cialo.get("gdy") == "wolne":
        st = panel(inst, "GET", API_UPDATE)[1]
        po_pracy = st.get("po_pracy") if isinstance(st, dict) else None
    koniec = czekaj_na_koniec(u, od, budzet.czas(CZAS_UPDATE + (CZAS_PO_PRACY if po_pracy else 0)))
    s = czekaj(lambda: (lambda x: x if dziala(x) else None)(status(inst)), budzet.czas(CZAS_SERWISU), 5) or {}
    biez = kod_z_aktualizacji(u)
    ok = (kod_post == 202 and (cialo.get("gdy") != "wolne" or bool(po_pracy)) and koniec.get("state") == "done"
          and koniec.get("current") == sha[:7] and biez == sha[:12] and dziala(s) and front_jest(u))
    log_panelu = u.logi / aktualizacja.LOG_PANELU
    if log_panelu.is_file():
        (art / f"{ident}-w-tle.log").write_text(e2e.bez_sekretow(e2e.czytaj_tekst(log_panelu)), encoding="utf-8")
    szczegoly["kroki"][ident] = {"czas_s": round(time.monotonic() - t0, 1), "post": [kod_post, odp],
                                 "po_pracy": po_pracy, "update.json": {k: koniec.get(k) for k in (
                                     "state", "current", "latest", "behind", "error", "started_at", "finished_at")},
                                 "current.json": biez, "status": s}
    rap.punkt(ident, opis_punktu, ok,
              f"POST {json.dumps(cialo)}: {kod_post}" + (f", po_pracy {po_pracy}" if cialo.get("gdy") else "")
              + f"; update.json: {koniec.get('state')}, current {koniec.get('current')} (oczekiwany {sha[:7]}), "
              f"{time.monotonic() - t0:.0f} s; current.json: {biez}; serwis i panel "
              f"{'działają' if dziala(s) else 'nie działają'}; front {'jest' if front_jest(u) else 'ZNIKNĄŁ'}"
              + (f"; błąd: {koniec.get('error')}" if koniec.get("error") else ""),
              czas_s=round(time.monotonic() - t0, 1))


def _panel(inst: e2e.Instalacja, rap: e2e.Raport, art: Path, zrodla: Path, szczegoly: dict,
           budzet: Budzet) -> None:
    """Kroki 5–7 (docstring modułu); na końcu serwis bez JARVO_FAKE_KOD, tak jak przed testem."""
    z_panelu = zrodla / "z-panelu"
    try:
        for nazwa, ident, opis_punktu, cialo in (
                ("pomocnik", "update-przycisk", "przycisk „Aktualizuj” w panelu → pomocnik → jarvo update w tle",
                 {"action": "update"}),
                ("pomocnik-2", "update-gdy-skoncza", "„Zaktualizuj, gdy skończą” → prośba po pracy → aktualizacja",
                 {"action": "update", "gdy": "wolne"})):
            if budzet.koniec():
                rap.punkt(ident, opis_punktu, None, "pominięte: skończył się limit czasu (--limit)")
                continue
            sha = sha_testowy(nazwa)
            kopia_kodu(Path(str(srodowisko.biezace(inst.u).get("app"))), z_panelu, sha)
            if _krok_pomocnika(inst, rap, art, z_panelu, sha, nazwa, szczegoly, budzet):
                _aktualizacja_z_panelu(inst, rap, art, sha, ident, opis_punktu, cialo, szczegoly, budzet)
            else:
                rap.punkt(ident, opis_punktu, None, "pominięte: pomocnik pod nadzorcą nie przeszedł (punkt wyżej)")
    finally:
        w = jarvo(inst, "down", czas=300)
        zapisz_log(art, "serwis-bez-fake-down", w)
        w = jarvo(inst, "up", czas=600)
        zapisz_log(art, "serwis-bez-fake-up", w)
        szczegoly["kroki"]["serwis-po-panelu"] = {"kod_up": w.kod, "status": status(inst)}


# ---------------------------------------------------------------- aktualizacja

def polecenie_aktualizacja(a) -> int:
    art = e2e.katalog_artefaktow(a.artefakty)
    rap = e2e.Raport(art)
    inst = e2e.Instalacja(a.korzen, a.jarvo)
    u = inst.u
    budzet = Budzet(a.limit)
    szczegoly: dict[str, Any] = {"root": str(u.root), "limit_s": a.limit, "kroki": {}}
    stare_app = inst.app
    if not inst.biez.get("app"):
        rap.punkt("update-instalacja", "jarvo update: jest instalacja do aktualizacji", False,
                  f"brak {u.program / 'current.json'}")
        return 1
    zrodla = Path(a.zrodla) if a.zrodla else Path(tempfile.mkdtemp(prefix="jarvo-update-"))
    zrodla.mkdir(parents=True, exist_ok=True)
    przed_status = status(inst)
    serwis_przed = dziala(przed_status)

    def krok(nazwa: str) -> bool:
        """Czy krok ma jeszcze czas (inaczej punkt pominięty z powodem)."""
        if budzet.koniec():
            rap.punkt(f"update-{nazwa}", f"jarvo update: {nazwa}", None, "pominięte: skończył się limit czasu (--limit)")
            return False
        return True

    try:
        # 1. ta sama wersja: nic
        if krok("ta-sama"):
            biezaca = aktualizacja.wersja_kodu(stare_app) or sha_testowy("biezaca")
            ta_sama = kopia_kodu(stare_app, zrodla / "ta-sama", biezaca)
            if aktualizacja.wersja_kodu(stare_app) is None:
                (stare_app / ".jarvo-wersja").write_text(biezaca + "\n", encoding="utf-8")
            przed = migawka_programu(u)
            w, r = update_json(inst, fake=ta_sama, art=art, nazwa="ta-sama", czas=budzet.czas(900))
            po = migawka_programu(u)
            zmiany = sorted(k for k in set(przed) | set(po) if przed.get(k) != po.get(k))
            szczegoly["kroki"]["ta-sama"] = {"kod": w.kod, "raport": r, "zmiany": zmiany[:40],
                                             "czas_s": round(w.sekundy, 1)}
            rap.punkt("update-ta-sama", "jarvo update do tej samej wersji: nic się nie zmienia",
                      w.kod == 0 and r.get("wynik") == "aktualne" and not zmiany and front_jest(u),
                      f"kod {w.kod}, wynik {r.get('wynik')}, {w.sekundy:.0f} s"
                      + (f"; zmienione: {', '.join(zmiany[:8])}" if zmiany else "; <program> i pliki stanu bez zmian"),
                      czas_s=round(w.sekundy, 1))

        # 2. GitHub tylko do odczytu
        if krok("github"):
            w, r = update_json(inst, "--sprawdz", fake=None, art=art, nazwa="github", czas=budzet.czas(300))
            siec = "brak połączenia" in w.tekst or "limit zapytań" in w.tekst
            szczegoly["kroki"]["github"] = {"kod": w.kod, "raport": r, "czas_s": round(w.sekundy, 1)}
            rap.punkt("update-github", "jarvo update --sprawdz pyta GitHub o ref instalacji",
                      None if siec else (w.kod == 0 and r.get("wynik") in ("aktualne", "dostepna")),
                      ("pominięte: brak sieci albo limit API GitHuba; " if siec else "")
                      + f"kod {w.kod}, ref {r.get('ref')}, zdalna {r.get('zdalna')}, wynik {r.get('wynik')}",
                      czas_s=round(w.sekundy, 1))

        # 3. nowsza wersja
        if krok("nowa"):
            sha2 = sha_testowy("v2")
            v2 = kopia_kodu(stare_app, zrodla / "v2", sha2)
            w, r = update_json(inst, fake=v2, art=art, nazwa="nowa", czas=budzet.czas(CZAS_UPDATE))
            biez = srodowisko.biezace(u)
            app2 = u.program / "app" / sha2[:12]
            s = status(inst)
            ok = (w.kod == 0 and r.get("wynik") == "zaktualizowano"
                  and odinstalowanie.w_katalogu(str(biez.get("app")), app2)
                  and not r.get("regresje") and dziala(s) == serwis_przed and front_jest(u))
            szczegoly["kroki"]["nowa"] = {"kod": w.kod, "raport": r, "status": s, "czas_s": round(w.sekundy, 1)}
            rap.punkt("update-nowa", "jarvo update do nowszej wersji: obok starej, instalator, doctor", ok,
                      f"kod {w.kod}, wynik {r.get('wynik')}, {r.get('wersja_przed')} → {r.get('wersja_po')}, "
                      f"{w.sekundy:.0f} s; front panelu {'jest' if front_jest(u) else 'ZNIKNĄŁ'}; "
                      f"current.json: {biez.get('app')}; serwis i panel "
                      f"{'działają' if dziala(s) else 'nie działają'} (przed: {'działały' if serwis_przed else 'nie'})"
                      + (f"; regresje: {r.get('regresje')}" if r.get("regresje") else "")
                      + (f"; nowe błędy doctora: {r.get('nowe_bledy')}" if r.get("nowe_bledy") else ""),
                      czas_s=round(w.sekundy, 1))

        # 4. wycofanie: wersja, której nadzorca nie wstaje
        if a.bez_wycofania or not serwis_przed:
            rap.punkt("update-wycofanie", "jarvo update: nieudana wersja wraca do poprzedniej", None,
                      "pominięte (--bez-wycofania albo serwis nie działał przed testem)")
        elif krok("wycofanie"):
            sha3 = sha_testowy("zly")
            przed_app = Path(str(srodowisko.biezace(u).get("app")))         # wersja, do której ma wrócić
            v3 = kopia_kodu(przed_app, zrodla / "zly", sha3, zepsuj_nadzorce=True)
            w, r = update_json(inst, fake=v3, art=art, nazwa="wycofanie", czas=budzet.czas(CZAS_UPDATE))
            biez = srodowisko.biezace(u)
            s = status(inst)
            ok = (w.kod == 1 and r.get("wynik") == "wycofano" and instalator.ten_sam_katalog(str(biez.get("app")),
                                                                                           przed_app)
                  and dziala(s) and front_jest(u))
            szczegoly["kroki"]["wycofanie"] = {"kod": w.kod, "raport": r, "status": s, "czas_s": round(w.sekundy, 1)}
            rap.punkt("update-wycofanie", "jarvo update: nieudana wersja wraca do poprzedniej", ok,
                      f"kod {w.kod}, wynik {r.get('wynik')}, {w.sekundy:.0f} s; current.json: {biez.get('app')}; "
                      f"serwis i panel {'działają' if dziala(s) else 'nie działają'}; "
                      + e2e.skrot(r.get("opis") or "", 300), czas_s=round(w.sekundy, 1))

        # 5–7. pomocnik pod nadzorcą, przycisk w panelu, „Zaktualizuj, gdy skończą”
        if a.bez_panelu or not serwis_przed:
            for ident in ("update-pomocnik", "update-przycisk", "update-gdy-skoncza"):
                rap.punkt(ident, "pomocnik aktualizacji pod nadzorcą i przycisk w panelu", None,
                          "pominięte (--bez-panelu albo serwis nie działał przed testem)")
        else:
            _panel(inst, rap, art, zrodla, szczegoly, budzet)

        # 8. sprzątanie: ta sama wersja usuwa stare wersje kodu, z których nic nie korzysta (najpierw czekamy, aż
        # skończą się procesy starych wersji, np. `jarvo update` z panelu: blokadę zwalnia tuż przed końcem procesu)
        if krok("sprzatanie"):
            biez = srodowisko.biezace(u)
            obecna = Path(str(biez.get("app")))
            czekaj_na_stare_wersje(u, obecna)
            w, r = update_json(inst, fake=_zrodlo_biezacej(u, zrodla), art=art, nazwa="sprzatanie",
                               czas=budzet.czas(900))
            zostaly = sorted(p.name for p in (u.program / "app").iterdir()) if (u.program / "app").is_dir() else []
            oczekiwane = [obecna.name] if odinstalowanie.w_katalogu(str(obecna), u.program / "app") else []
            sp = r.get("sprzatanie") or {}
            szczegoly["kroki"]["sprzatanie"] = {"kod": w.kod, "raport": r, "app": zostaly,
                                                "czas_s": round(w.sekundy, 1)}
            rap.punkt("update-sprzatanie", "jarvo update sprząta stare wersje, z których nic nie korzysta",
                      w.kod == 0 and r.get("wynik") == "aktualne" and zostaly == oczekiwane and front_jest(u),
                      f"kod {w.kod}; front panelu {'jest' if front_jest(u) else 'ZNIKNĄŁ'}; w {u.program / 'app'}: "
                      f"{', '.join(zostaly) or 'pusto'}; usunięte: {len(sp.get('usuniete') or [])}, zwolnione "
                      f"{sp.get('zwolnione_mb')} MB; w użyciu: {sp.get('w_uzyciu')}"
                      + (f"; wstrzymane przez: {sp.get('wstrzymane')}" if sp.get("wstrzymane") else ""),
                      czas_s=round(w.sekundy, 1))
    finally:
        szczegoly["czas_s"] = round(time.monotonic() - budzet.t0, 1)
        e2e.zapisz_json(art / "raport-update.json", szczegoly)
        if not a.zostaw_zrodla:
            odinstalowanie.usun_drzewo(zrodla)
    return 1 if rap.bledy else 0


def czekaj_na_stare_wersje(u, obecna: Path, czas: float = 180) -> None:
    """Czeka, aż żaden proces nie korzysta z wersji kodu innej niż bieżąca (np. kończący się `jarvo update`)."""
    stare = [p for p in (u.program / "app").iterdir() if p.is_dir() and p.name != obecna.name] \
        if (u.program / "app").is_dir() else []
    koniec = time.monotonic() + czas
    while stare and time.monotonic() < koniec:
        lista = odinstalowanie.procesy()
        pomin = {os.getpid(), *odinstalowanie.przodkowie(os.getpid(), lista)}
        if not any(odinstalowanie.uzywaja(p, lista, pomin) for p in stare):
            return
        time.sleep(2)


def _zrodlo_biezacej(u, zrodla: Path) -> Path:
    """Kopia bieżącej wersji (ta sama wersja dla `jarvo update`)."""
    app = Path(str(srodowisko.biezace(u).get("app")))
    return kopia_kodu(app, zrodla / "biezaca", aktualizacja.wersja_kodu(app) or sha_testowy("biezaca"))


# ---------------------------------------------------------------- odinstalowanie

def migawka_sladow(inst: e2e.Instalacja) -> dict[str, Any]:
    """Ślady tej instalacji (tylko odczyt): katalogi Jarva, wpisy katalogu nad korzeniem, PATH użytkownika (Windows),
    bloki w plikach startowych powłoki i ~/.local/bin/jarvo (POSIX), autostart tej instalacji, procesy z korzeniem."""
    u = inst.u
    wynik: dict[str, Any] = {k: os.path.lexists(p) for k, p in (("korzen", u.root), ("logi", u.logi),
                                                                  ("cache", u.cache), ("build", u.build))}
    rodzic = u.root.parent
    wynik["rodzic"] = sorted(e.name for e in os.scandir(rodzic)) if rodzic.is_dir() else []
    if WINDOWS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                path = str(winreg.QueryValueEx(k, "Path")[0])
        except OSError:
            path = ""
        wynik["path"] = [c for c in path.split(";") if c.strip() and odinstalowanie.zawiera_sciezke(c, u.root)]
        wynik["aplikacje"] = odinstalowanie._wpis_aplikacji(odinstalowanie.NAZWA_APLIKACJI) is not None
    else:
        dom = Path.home()
        wynik["rc"] = sorted(n for n in (".profile", ".bash_profile", ".zprofile", ".bashrc", ".zshrc")
                             if (dom / n).is_file() and "# >>> jarvo >>>" in (dom / n).read_text("utf-8", "replace"))
        polecenie = dom / ".local" / "bin" / "jarvo"
        wynik["polecenie_w_domu"] = bool(polecenie.is_file() and instalator.ZNACZNIK in polecenie.read_text(
            "utf-8", "replace") and odinstalowanie._plik_polecenia_posix(u) is not None)
    try:
        from jarvo import autostart
        st = autostart.stan(u)
        wynik["autostart"] = bool(st.get("mechanizm") and st.get("nasz"))
    except Exception as e:                    # noqa: BLE001 - brak narzędzia systemu: zapis do raportu
        wynik["autostart"] = f"nie sprawdzony ({type(e).__name__})"
    wynik["procesy"] = [p.opis() for p in procesy_w_korzeniu(u)]
    return wynik


def uruchomienie_testu(tekst: str) -> bool:
    """Proces (albo jego opis w raporcie), który uruchamia ten test, np. `bash -c "… natywnie_update.py odinstalowanie
    --korzen R"`: ma korzeń w wierszu polecenia, a nie jest śladem Jarva. Łańcuch rodziców tego nie złapie, gdy
    pośredni proces (np. `timeout` w Git Bash) już się skończył."""
    return Path(__file__).name in str(tekst or "")


def procesy_w_korzeniu(u) -> list:
    """Procesy z korzeniem w programie albo w wierszu polecenia, bez tego testu, jego przodków i procesów, które go
    uruchomiły (terminal, w którym go uruchomiono, ma korzeń w argumentach --korzen)."""
    lista = odinstalowanie.procesy()
    pomin = {os.getpid(), *odinstalowanie.przodkowie(os.getpid(), lista)}
    return [p for p in odinstalowanie.uzywaja(u.root, lista, pomin) if not uruchomienie_testu(p.polecenie)]


def polecenie_odinstalowanie(a) -> int:
    art = e2e.katalog_artefaktow(a.artefakty)
    rap = e2e.Raport(art)
    inst = e2e.Instalacja(a.korzen, a.jarvo)
    u = inst.u
    t0 = time.monotonic()
    przed = migawka_sladow(inst)
    uruchamiajace = {p.pid for p in odinstalowanie.procesy() if uruchomienie_testu(p.polecenie)} - {os.getpid()}
    w = jarvo(inst, "uninstall", "--all", "--yes", "--json", czas=900)
    zapisz_log(art, "odinstalowanie", w)
    raport = e2e.json_z_wyjscia(w.out)
    raport = raport if isinstance(raport, dict) else {}
    koniec = time.monotonic() + 180                    # proces sprzątający (Windows) kończy po tym poleceniu
    while time.monotonic() < koniec and (u.root.exists() or procesy_w_korzeniu(u)):
        time.sleep(2)
    po = migawka_sladow(inst)
    szczegoly: dict[str, Any] = {"przed": przed, "po": po, "raport": raport, "kod": w.kod,
                                 "czas_s": round(time.monotonic() - t0, 1)}
    # proces, który uruchomił ten test (np. bash -c z --korzen), polecenie słusznie zgłasza i zostawia: to nie Jarvo
    # (w raporcie wiersz polecenia jest przycięty, więc rozpoznajemy go po PID-zie)
    testu = [s for s in raport.get("slady") or [] if s.get("rodzaj") == "proces"
             and any(f"(PID {pid})" in str(s.get("opis")) for pid in uruchamiajace)]
    slady = [s for s in raport.get("slady") or [] if s not in testu]
    tylko_test = bool(testu) and not slady and w.kod == 1
    rap.punkt("odinst-polecenie", "jarvo uninstall --all --yes: bez śladów w raporcie",
              (w.kod == 0 or tylko_test) and raport.get("wynik") == "odinstalowane" and not slady,
              f"kod {w.kod}, wynik {raport.get('wynik')}, {w.sekundy:.0f} s; ślady: "
              + ("; ".join(s.get("opis", "?") for s in slady) or "brak")
              + (f" (pominięte procesy uruchomienia tego testu: {len(testu)})" if testu else "")
              + "; celowo: " + ("; ".join(c.get("opis", "?") for c in raport.get("celowo") or []) or "nic"),
              czas_s=round(w.sekundy, 1))
    nowe = sorted(set(po["rodzic"]) - set(przed["rodzic"]))
    znikly = sorted(set(przed["rodzic"]) - set(po["rodzic"]))
    obce_nowe = [n for n in nowe if SLAD.search(n)]
    ok = (not po["korzen"] and not po["logi"] and not po["cache"] and not po["build"] and not obce_nowe
          and znikly in ([], [u.root.name]) and not po["procesy"] and po.get("autostart") in (False,)
          and not po.get("path") and not po.get("rc") and not po.get("polecenie_w_domu")
          and not po.get("aplikacje"))
    roznica = {"nowe w katalogu nad korzeniem": nowe, "znikły": znikly,
               **{k: (przed.get(k), po.get(k)) for k in sorted(set(przed) | set(po)) if przed.get(k) != po.get(k)
                  and k != "rodzic"}}
    szczegoly["roznica"] = roznica
    rap.punkt("odinst-migawka", "po odinstalowaniu: korzeń, logi, cache, PATH, autostart i procesy bez śladów", ok,
              "; ".join(f"{k}: {v}" for k, v in roznica.items()) or "bez różnic")
    if a.migawka_przed:
        m_przed = e2e.wczytaj_json(Path(a.migawka_przed))
        if isinstance(m_przed, dict):
            m_po = e2e.migawka(u=u)
            e2e.zapisz_json(art / "migawka-po.json", m_po)
            r = e2e.roznica(m_przed, m_po)
            e2e.zapisz_json(art / "roznica.json", r)
            nie = [z for z in r["zmiany"] if not z["wyjasnienie"]]
            szczegoly["migawka"] = {"zmiany": len(r["zmiany"]), "niewyjasnione": nie[:40]}
            rap.punkt("migawka", "komputer po odinstalowaniu jak przed instalacją", not nie,
                      f"{len(r['zmiany'])} różnic, w tym {len(nie)} bez wyjaśnienia"
                      + (": " + "; ".join(f"{z['rodzaj']} {z['klucz']}" for z in nie[:12]) if nie else ""))
        else:
            rap.punkt("migawka", "komputer po odinstalowaniu jak przed instalacją", False,
                      f"brak migawki {a.migawka_przed}")
    e2e.zapisz_json(art / "raport-odinstalowanie.json", szczegoly)
    return 1 if rap.bledy else 0


def polecenie_wszystko(a) -> int:
    kod = polecenie_aktualizacja(a)
    return polecenie_odinstalowanie(a) or kod


# ---------------------------------------------------------------- wejście

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="natywnie_update.py", description="Test na żywo jarvo update, przycisku "
                                "aktualizacji w panelu i jarvo uninstall na zainstalowanym korzeniu Jarva "
                                "(docs/NATYWNIE.md N09, N11, c4, S09).")
    sub = p.add_subparsers(dest="polecenie", required=True, metavar="polecenie")

    def wspolne(s: argparse.ArgumentParser, *, aktualizacja_: bool, odinstalowanie_: bool) -> None:
        s.add_argument("--artefakty", help="katalog artefaktów (domyślnie jak natywnie_e2e.py)")
        s.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT; domyślnie korzeń systemu)")
        s.add_argument("--jarvo", help="ścieżka polecenia jarvo (domyślnie z instalacji)")
        if aktualizacja_:
            s.add_argument("--zrodla", help="katalog na kopie kodu (domyślnie tymczasowy)")
            s.add_argument("--zostaw-zrodla", action="store_true", help="nie usuwaj kopii kodu na końcu")
            s.add_argument("--bez-wycofania", action="store_true", help="bez próby nieudanej wersji (krótszy test)")
            s.add_argument("--bez-panelu", action="store_true",
                           help="bez pomocnika pod nadzorcą i przycisku w panelu (kroki 5–7)")
            s.add_argument("--limit", type=float, default=LIMIT,
                           help=f"sekundy na całą aktualizację (domyślnie {int(LIMIT)}); po nich kroki są pomijane")
        if odinstalowanie_:
            s.add_argument("--migawka-przed", metavar="PLIK",
                           help="migawka natywnie_e2e.py sprzed instalacji: po odinstalowaniu także różnica migawek")

    s = sub.add_parser("aktualizacja", help="ta sama wersja, GitHub, nowsza, wycofanie, panel, sprzątanie")
    wspolne(s, aktualizacja_=True, odinstalowanie_=False)
    s.set_defaults(funkcja=polecenie_aktualizacja)
    s = sub.add_parser("odinstalowanie", help="jarvo uninstall --all --yes i migawka śladów")
    wspolne(s, aktualizacja_=False, odinstalowanie_=True)
    s.set_defaults(funkcja=polecenie_odinstalowanie)
    s = sub.add_parser("wszystko", help="aktualizacja, potem odinstalowanie")
    wspolne(s, aktualizacja_=True, odinstalowanie_=True)
    s.set_defaults(funkcja=polecenie_wszystko)
    return p


def main(argv: list[str] | None = None) -> int:
    for strumien in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            strumien.reconfigure(errors="replace")
    a = parser().parse_args(argv)
    t0 = time.monotonic()
    try:
        kod = int(a.funkcja(a) or 0)
    except e2e.BladE2E as e:
        print(f"BŁĄD: {e2e.bez_sekretow(str(e))}", file=sys.stderr)
        kod = 1
    rap = e2e.Raport(e2e.katalog_artefaktow(a.artefakty))
    punkty = [p for p in rap.dane["punkty"] if str(p.get("id", "")).startswith(("update-", "odinst-", "migawka"))]
    print(json.dumps({"test": "natywnie_update", "polecenie": a.polecenie, "kod": kod,
                      "czas_s": round(time.monotonic() - t0, 1),
                      "punkty": [{k: p.get(k) for k in ("id", "ok", "czas_s")} for p in punkty]},
                     ensure_ascii=False, indent=1), flush=True)
    return kod


if __name__ == "__main__":
    sys.exit(main())
