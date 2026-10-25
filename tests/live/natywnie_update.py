#!/usr/bin/env python3
"""Test na żywo `jarvo update` i `jarvo uninstall` na zainstalowanym korzeniu Jarva (docs/NATYWNIE.md: N09, N11, c4,
S09, T08; etapy E4 i E13). Uruchamia go pełna macierz CI (.github/workflows/natywnie.yml, po drugim przebiegu
instalacji) albo właściciel na próbnej instalacji (JARVO_ROOT). Sama biblioteka standardowa i pakiet jarvo/ tego repo;
pomocnicze rzeczy (punkty raportu, uruchamianie, polecenie jarvo) bierze z tests/live/natywnie_e2e.py.

Druga wersja to kopia bieżącego kodu instalacji z innym `.jarvo-wersja` (SHA testowy), podana przez JARVO_FAKE_KOD
(jarvo/aktualizacja.py): `jarvo update` widzi ją jak nowe wydanie na GitHubie, ale bez sieci i bez pushowania.

  aktualizacja [--korzen R] [--zrodla KATALOG] [--bez-wycofania] [--bez-pomocnika]
      1. ta sama wersja: `jarvo update --json` → „aktualne”; `<program>` (bez __pycache__), current.json,
         narzedzia.json, srodowisko.json, ustawienia.json i polecenie jarvo bez zmian,
      2. GitHub (tylko odczyt): `jarvo update --sprawdz --json` z refem instalacji; bez sieci albo przy limicie API:
         pominięte,
      3. nowsza wersja: „zaktualizowano”, current.json na `<program>/app/<sha12>`, serwis i panel jak przed
         aktualizacją (`jarvo status --json`), doctor bez regresji,
      4. (bez --bez-wycofania) wersja, której nadzorca nie wstaje: „wycofano”, current.json z kroku 3, serwis działa,
      5. (bez --bez-pomocnika) pomocnik panelu: prośba „check” → update.json (behind, latest), prośba „update” →
         `jarvo update` w tle aż do state „done”, current.json na nowej wersji,
      6. sprzątanie: znowu ta sama wersja usuwa stare wersje kodu, z których nic nie korzysta (zostaje bieżąca).
  odinstalowanie [--korzen R]
      `jarvo uninstall --all --yes --json`, czekanie na proces sprzątający (Windows), potem migawka: korzeń, logi
      i cache usunięte, PATH użytkownika, blok w pliku startowym, polecenie jarvo, autostart i procesy bez śladów
      tej instalacji, w katalogu nad korzeniem bez nowych wpisów z „jarvo” albo „hermes” w nazwie; raport polecenia
      bez śladów.
  wszystko [...]: aktualizacja, potem odinstalowanie.

Każde podpolecenie dopisuje punkty do <artefakty>/raport.json (ten sam plik co natywnie_e2e.py, więc `podsumowanie`
pokazuje je w CI), szczegóły do <artefakty>/raport-update.json, wyjście poleceń do <artefakty>/update-*.log; kod 1 =
któryś punkt nie przeszedł. Kopie kodu leżą w katalogu tymczasowym (albo w --zrodla) i znikają na końcu.

    python -X utf8 -B tests/live/natywnie_update.py aktualizacja
    python -X utf8 -B tests/live/natywnie_update.py wszystko --korzen D:\\JarvoTest\\proba-update\\root \\
        --zrodla D:\\JarvoTest\\proba-update\\zrodla
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

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
CZAS_UPDATE = 3600.0


# ---------------------------------------------------------------- pomocnicze

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


# ---------------------------------------------------------------- aktualizacja

def polecenie_aktualizacja(a) -> int:
    art = e2e.katalog_artefaktow(a.artefakty)
    rap = e2e.Raport(art)
    inst = e2e.Instalacja(a.korzen, a.jarvo)
    u = inst.u
    szczegoly: dict[str, Any] = {"root": str(u.root), "kroki": {}}
    stare_app = inst.app
    if not inst.biez.get("app"):
        rap.punkt("update-instalacja", "jarvo update: jest instalacja do aktualizacji", False,
                  f"brak {u.program / 'current.json'}")
        return 1
    zrodla = Path(a.zrodla) if a.zrodla else Path(tempfile.mkdtemp(prefix="jarvo-update-"))
    zrodla.mkdir(parents=True, exist_ok=True)
    przed_status = status(inst)
    serwis_przed = dziala(przed_status)
    try:
        # 1. ta sama wersja: nic
        biezaca = aktualizacja.wersja_kodu(stare_app) or sha_testowy("biezaca")
        ta_sama = kopia_kodu(stare_app, zrodla / "ta-sama", biezaca)
        if aktualizacja.wersja_kodu(stare_app) is None:
            (stare_app / ".jarvo-wersja").write_text(biezaca + "\n", encoding="utf-8")
        przed = migawka_programu(u)
        w, r = update_json(inst, fake=ta_sama, art=art, nazwa="ta-sama", czas=900)
        po = migawka_programu(u)
        zmiany = sorted(k for k in set(przed) | set(po) if przed.get(k) != po.get(k))
        szczegoly["kroki"]["ta-sama"] = {"kod": w.kod, "raport": r, "zmiany": zmiany[:40]}
        rap.punkt("update-ta-sama", "jarvo update do tej samej wersji: nic się nie zmienia",
                  w.kod == 0 and r.get("wynik") == "aktualne" and not zmiany and front_jest(u),
                  f"kod {w.kod}, wynik {r.get('wynik')}, {w.sekundy:.0f} s"
                  + (f"; zmienione: {', '.join(zmiany[:8])}" if zmiany else "; <program> i pliki stanu bez zmian"))

        # 2. GitHub tylko do odczytu
        w, r = update_json(inst, "--sprawdz", fake=None, art=art, nazwa="github", czas=300)
        siec = "brak połączenia" in w.tekst or "limit zapytań" in w.tekst
        szczegoly["kroki"]["github"] = {"kod": w.kod, "raport": r}
        rap.punkt("update-github", "jarvo update --sprawdz pyta GitHub o ref instalacji",
                  None if siec else (w.kod == 0 and r.get("wynik") in ("aktualne", "dostepna")),
                  ("pominięte: brak sieci albo limit API GitHuba; " if siec else "")
                  + f"kod {w.kod}, ref {r.get('ref')}, zdalna {r.get('zdalna')}, wynik {r.get('wynik')}")

        # 3. nowsza wersja
        sha2 = sha_testowy("v2")
        v2 = kopia_kodu(stare_app, zrodla / "v2", sha2)
        w, r = update_json(inst, fake=v2, art=art, nazwa="nowa")
        biez = srodowisko.biezace(u)
        app2 = u.program / "app" / sha2[:12]
        s = status(inst)
        ok = (w.kod == 0 and r.get("wynik") == "zaktualizowano" and odinstalowanie.w_katalogu(str(biez.get("app")),
                                                                                            app2)
              and not r.get("regresje") and dziala(s) == serwis_przed and front_jest(u))
        szczegoly["kroki"]["nowa"] = {"kod": w.kod, "raport": r, "status": s}
        rap.punkt("update-nowa", "jarvo update do nowszej wersji: obok starej, instalator, doctor", ok,
                  f"kod {w.kod}, wynik {r.get('wynik')}, {r.get('wersja_przed')} → {r.get('wersja_po')}, "
                  f"{w.sekundy:.0f} s; front panelu {'jest' if front_jest(u) else 'ZNIKNĄŁ'}; "
                  f"current.json: {biez.get('app')}; serwis i panel "
                  f"{'działają' if dziala(s) else 'nie działają'} (przed: {'działały' if serwis_przed else 'nie'})"
                  + (f"; regresje: {r.get('regresje')}" if r.get("regresje") else "")
                  + (f"; nowe błędy doctora: {r.get('nowe_bledy')}" if r.get("nowe_bledy") else ""))

        # 4. wycofanie: wersja, której nadzorca nie wstaje
        if not a.bez_wycofania and serwis_przed:
            sha3 = sha_testowy("zly")
            przed_app = Path(str(srodowisko.biezace(u).get("app")))         # wersja, do której ma wrócić
            v3 = kopia_kodu(przed_app, zrodla / "zly", sha3, zepsuj_nadzorce=True)
            w, r = update_json(inst, fake=v3, art=art, nazwa="wycofanie")
            biez = srodowisko.biezace(u)
            s = status(inst)
            ok = (w.kod == 1 and r.get("wynik") == "wycofano" and instalator.ten_sam_katalog(str(biez.get("app")),
                                                                                           przed_app)
                  and dziala(s) and front_jest(u))
            szczegoly["kroki"]["wycofanie"] = {"kod": w.kod, "raport": r, "status": s}
            rap.punkt("update-wycofanie", "jarvo update: nieudana wersja wraca do poprzedniej", ok,
                      f"kod {w.kod}, wynik {r.get('wynik')}, {w.sekundy:.0f} s; current.json: {biez.get('app')}; "
                      f"serwis i panel {'działają' if dziala(s) else 'nie działają'}; "
                      + e2e.skrot(r.get("opis") or "", 300))
        else:
            rap.punkt("update-wycofanie", "jarvo update: nieudana wersja wraca do poprzedniej", None,
                      "pominięte (--bez-wycofania albo serwis nie działał przed testem)")

        # 5. pomocnik dla panelu
        if not a.bez_pomocnika:
            _pomocnik(inst, rap, art, zrodla, szczegoly)
        else:
            rap.punkt("update-pomocnik", "pomocnik aktualizacji dla panelu", None, "pominięte (--bez-pomocnika)")

        # 6. sprzątanie: ta sama wersja usuwa stare wersje kodu, z których nic nie korzysta (najpierw czekamy, aż
        # skończy się `jarvo update` uruchomiony przez pomocnika: blokadę zwalnia tuż przed końcem procesu)
        biez = srodowisko.biezace(u)
        obecna = Path(str(biez.get("app")))
        czekaj_na_stare_wersje(u, obecna)
        w, r = update_json(inst, fake=_zrodlo_biezacej(u, zrodla), art=art, nazwa="sprzatanie", czas=900)
        zostaly = sorted(p.name for p in (u.program / "app").iterdir()) if (u.program / "app").is_dir() else []
        oczekiwane = [obecna.name] if odinstalowanie.w_katalogu(str(obecna), u.program / "app") else []
        szczegoly["kroki"]["sprzatanie"] = {"kod": w.kod, "raport": r, "app": zostaly}
        rap.punkt("update-sprzatanie", "jarvo update sprząta stare wersje, z których nic nie korzysta",
                  w.kod == 0 and r.get("wynik") == "aktualne" and zostaly == oczekiwane and front_jest(u),
                  f"kod {w.kod}; front panelu {'jest' if front_jest(u) else 'ZNIKNĄŁ'}; w {u.program / 'app'}: "
                  f"{', '.join(zostaly) or 'pusto'}; usunięte: "
                  f"{len((r.get('sprzatanie') or {}).get('usuniete') or [])}, zwolnione "
                  f"{(r.get('sprzatanie') or {}).get('zwolnione_mb')} MB; w użyciu: "
                  f"{(r.get('sprzatanie') or {}).get('w_uzyciu')}")
    finally:
        e2e.zapisz_json(art / "raport-update.json", szczegoly)
        if not a.zostaw_zrodla:
            odinstalowanie.usun_drzewo(zrodla)
    return 1 if rap.bledy else 0


def czekaj_na_stare_wersje(u, obecna: Path, czas: float = 120) -> None:
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


def _pomocnik(inst: e2e.Instalacja, rap: e2e.Raport, art: Path, zrodla: Path, szczegoly: dict) -> None:
    """Kontrakt z panelem: update-request „check” i „update”, update.json (hq/plugin/plugin_api.py)."""
    u = inst.u
    sha4 = sha_testowy("v4")
    biez = Path(str(srodowisko.biezace(u).get("app")))
    v4 = kopia_kodu(biez, zrodla / "v4", sha4)
    prosba = u.jarvo_dane / aktualizacja.PROSBA_PANELU
    prosba.parent.mkdir(parents=True, exist_ok=True)
    prosba.write_text("check", encoding="utf-8")
    t0 = time.time()
    w = jarvo(inst, "update", "--pomocnik", "--raz", fake=v4, czas=300)
    zapisz_log(art, "pomocnik-check", w)
    panel = aktualizacja.stan_panelu(u)
    ok = (w.kod == 0 and not prosba.exists() and panel.get("latest") == sha4[:7] and panel.get("behind") == 1
          and float(panel.get("checked_at") or 0) >= t0 - 1)
    rap.punkt("update-pomocnik-check", "pomocnik panelu: prośba „check” → update.json", ok,
              f"kod {w.kod}, prośba {'zostala' if prosba.exists() else 'zabrana'}, latest {panel.get('latest')}, "
              f"behind {panel.get('behind')}, state {panel.get('state')}")
    prosba.write_text("update", encoding="utf-8")
    t0 = time.time()
    w = jarvo(inst, "update", "--pomocnik", "--raz", fake=v4, czas=300)
    zapisz_log(art, "pomocnik-update", w)
    koniec = time.monotonic() + CZAS_UPDATE
    panel = aktualizacja.stan_panelu(u)
    while time.monotonic() < koniec:
        panel = aktualizacja.stan_panelu(u)
        if (panel.get("state") in ("done", "failed") and float(panel.get("finished_at") or 0) >= t0
                and not aktualizacja.trwa(u)):
            break
        time.sleep(5)
    biez = srodowisko.biezace(u)
    s = status(inst)
    ok = (w.kod == 0 and panel.get("state") == "done" and panel.get("current") == sha4[:7]
          and odinstalowanie.w_katalogu(str(biez.get("app")), u.program / "app" / sha4[:12]) and dziala(s)
          and front_jest(u))
    szczegoly["kroki"]["pomocnik"] = {"panel": {k: panel.get(k) for k in ("state", "current", "latest", "behind",
                                                                           "error", "started_at", "finished_at")},
                                      "status": s}
    log_panelu = u.logi / aktualizacja.LOG_PANELU
    if log_panelu.is_file():
        (art / "update-pomocnik-w-tle.log").write_text(e2e.bez_sekretow(e2e.czytaj_tekst(log_panelu)), encoding="utf-8")
    rap.punkt("update-pomocnik", "pomocnik panelu: prośba „update” → jarvo update w tle do końca", ok,
              f"state {panel.get('state')}, current {panel.get('current')} (oczekiwany {sha4[:7]}), "
              f"{time.time() - t0:.0f} s; current.json: {biez.get('app')}; serwis i panel "
              f"{'działają' if dziala(s) else 'nie działają'}" + (f"; błąd: {panel.get('error')}"
                                                                    if panel.get("error") else ""))


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


def procesy_w_korzeniu(u) -> list:
    """Procesy z korzeniem w programie albo w wierszu polecenia, bez tego testu i jego przodków (terminal, w którym
    go uruchomiono, ma korzeń w argumentach --korzen)."""
    lista = odinstalowanie.procesy()
    pomin = {os.getpid(), *odinstalowanie.przodkowie(os.getpid(), lista)}
    return odinstalowanie.uzywaja(u.root, lista, pomin)


def polecenie_odinstalowanie(a) -> int:
    art = e2e.katalog_artefaktow(a.artefakty)
    rap = e2e.Raport(art)
    inst = e2e.Instalacja(a.korzen, a.jarvo)
    u = inst.u
    przed = migawka_sladow(inst)
    w = jarvo(inst, "uninstall", "--all", "--yes", "--json", czas=900)
    zapisz_log(art, "odinstalowanie", w)
    raport = e2e.json_z_wyjscia(w.out)
    raport = raport if isinstance(raport, dict) else {}
    koniec = time.monotonic() + 180                    # proces sprzątający (Windows) kończy po tym poleceniu
    while time.monotonic() < koniec and (u.root.exists() or procesy_w_korzeniu(u)):
        time.sleep(2)
    po = migawka_sladow(inst)
    szczegoly = {"przed": przed, "po": po, "raport": raport, "kod": w.kod}
    rap.punkt("odinst-polecenie", "jarvo uninstall --all --yes: bez śladów w raporcie",
              w.kod == 0 and raport.get("wynik") == "odinstalowane" and not raport.get("slady"),
              f"kod {w.kod}, wynik {raport.get('wynik')}, {w.sekundy:.0f} s; ślady: "
              + ("; ".join(s.get("opis", "?") for s in raport.get("slady") or []) or "brak")
              + "; celowo: " + ("; ".join(c.get("opis", "?") for c in raport.get("celowo") or []) or "nic"))
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
    e2e.zapisz_json(art / "raport-odinstalowanie.json", szczegoly)
    rap.punkt("odinst-migawka", "po odinstalowaniu: korzeń, logi, cache, PATH, autostart i procesy bez śladów", ok,
              "; ".join(f"{k}: {v}" for k, v in roznica.items()) or "bez różnic")
    return 1 if rap.bledy else 0


def polecenie_wszystko(a) -> int:
    kod = polecenie_aktualizacja(a)
    return polecenie_odinstalowanie(a) or kod


# ---------------------------------------------------------------- wejście

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="natywnie_update.py", description="Test na żywo jarvo update i jarvo uninstall "
                                "na zainstalowanym korzeniu Jarva (docs/NATYWNIE.md N09, N11, c4, S09).")
    sub = p.add_subparsers(dest="polecenie", required=True, metavar="polecenie")

    def wspolne(s: argparse.ArgumentParser, *, zrodla: bool) -> None:
        s.add_argument("--artefakty", help="katalog artefaktów (domyślnie jak natywnie_e2e.py)")
        s.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT; domyślnie korzeń systemu)")
        s.add_argument("--jarvo", help="ścieżka polecenia jarvo (domyślnie z instalacji)")
        if zrodla:
            s.add_argument("--zrodla", help="katalog na kopie kodu (domyślnie tymczasowy)")
            s.add_argument("--zostaw-zrodla", action="store_true", help="nie usuwaj kopii kodu na końcu")
            s.add_argument("--bez-wycofania", action="store_true", help="bez próby nieudanej wersji (krótszy test)")
            s.add_argument("--bez-pomocnika", action="store_true", help="bez próby pomocnika panelu")

    s = sub.add_parser("aktualizacja", help="ta sama wersja, GitHub, nowsza, wycofanie, pomocnik, sprzątanie")
    wspolne(s, zrodla=True)
    s.set_defaults(funkcja=polecenie_aktualizacja)
    s = sub.add_parser("odinstalowanie", help="jarvo uninstall --all --yes i migawka śladów")
    wspolne(s, zrodla=False)
    s.set_defaults(funkcja=polecenie_odinstalowanie)
    s = sub.add_parser("wszystko", help="aktualizacja, potem odinstalowanie")
    wspolne(s, zrodla=True)
    s.set_defaults(funkcja=polecenie_wszystko)
    return p


def main(argv: list[str] | None = None) -> int:
    for strumien in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            strumien.reconfigure(errors="replace")
    a = parser().parse_args(argv)
    try:
        return int(a.funkcja(a) or 0)
    except e2e.BladE2E as e:
        print(f"BŁĄD: {e2e.bez_sekretow(str(e))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
