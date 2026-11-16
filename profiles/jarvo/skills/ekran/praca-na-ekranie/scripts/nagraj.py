#!/usr/bin/env python3
"""Film z pracy na ekranie Komputera Jarva: krótkie segmenty tylko z kroków, które działają, i film z szybkimi cięciami.

    nagraj.py start "<opis kroku>"     # nagrywa jeden krok (najwyżej MAKS_SEGMENT s); poprzedni segment zamyka
    nagraj.py stop                     # koniec kroku: segment udany (chyba że strażnik już zamknął go jako nieudany)
    nagraj.py stop --nieudany          # koniec kroku, który nie wyszedł: segment nie trafi do filmu
    nagraj.py film [--wyjscie P.mp4]   # film.mp4 tylko z udanych segmentów, każdy przyspieszony do MAKS_UJECIE s
    nagraj.py stan                     # segmenty i ich stan (JSON)
    nagraj.py wyczysc [--z-filmem]     # po wysłaniu filmu: usuwa robocze nagrania (i film z --z-filmem)

Wszystkie polecenia przyjmują `--katalog` (domyślnie `out/nagranie` w bieżącym katalogu) i piszą JSON na stdout;
błąd to `{"ok": false, "blad": …}` i kod wyjścia 1.

Nagrywa tylko ekran, na którym jest okno Komputera Jarva (`jarvo komputer okno on`): na Linuksie pulpit X11 z ustawienia
`ekran` Komputera (`<stan>/komputer/ustawienia.json`, DISPLAY i XAUTHORITY z terminala właściciela), inaczej DISPLAY
procesu; na macOS ekran 0 (avfoundation), na Windows pulpit (gdigrab). Komputer w tle (headless) albo wstrzymany:
odmowa, bo nagranie pokazałoby pulpit bez przeglądarki. ffmpeg z PATH floty (pełny ffmpeg z manifestu narzędzi),
z `nice -n 15` i `-threads 2`.

Każdy segment ma twardy limit ffmpeg `-t MAKS_SEGMENT`, więc kończy się sam, nawet gdy nikt nie wywoła `stop`.
Strażnik segmentu (ten skrypt w tle, polecenie `_pilnuj`) czyta dziennik Komputera (`<dane>/jarvo/komputer/
dziennik.jsonl`) i zamyka segment wcześniej:
- jako nieudany przy odmowie, kroku właściciela albo wstrzymaniu (`decyzja` odmowa, czlowiek, wstrzymane; pauza,
  przejęcie) i przy pauzie Komputera (plik `<dane>/jarvo/komputer/pauza`); nagranie nieudanego segmentu kasuje,
- jako nieudany, gdy przez CISZA s od startu w Komputerze nie było żadnego kroku (praca gdzie indziej, np. telefon),
- jako udany, gdy po krokach Komputer milczy CISZA s (krok skończony, a agent jeszcze nie wywołał `stop`); do filmu
  idzie wtedy tylko czas do ostatniego kroku plus ZAPAS_PO_KROKU s.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MAKS_SEGMENT = 75          # s: twardy limit jednego segmentu (ffmpeg -t)
CISZA = 20                 # s bez kroku w dzienniku Komputera: koniec segmentu
MAKS_SEGMENTOW = 40        # na jeden katalog nagrania
MAKS_UJECIE = 5            # s: najdłuższe ujęcie w filmie (dłuższy segment jest przyspieszany)
ZAPAS_PO_KROKU = 3         # s obrazu po ostatnim kroku, gdy segment zamknęła cisza
KLATKI = 10                # klatek na sekundę w nagraniu
CO_ILE = 0.5               # s: krok pętli strażnika
MARTWY = 10                # s bez znaku życia strażnika: segment uznany za przerwany
CZAS_ZAMKNIECIA = 25       # s: tyle `stop` czeka na zamknięcie segmentu
FILM_SZER, FILM_WYS, FILM_KLATKI = 1280, 720, 30

NIEUDANE = {"odmowa", "czlowiek", "wstrzymane"}     # decyzje wejścia Komputera (zasady.py) = krok nie wyszedł
PRZEJECIE = {"pauza", "przejmij"}                    # wpisy kanału `ster`: Komputer stoi albo ma go właściciel
WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"
PLIK_STANU = "stan.json"
PLIK_FILMU = "film.mp4"

_teraz = time.time         # podmieniane w testach
_spij = time.sleep


class Blad(Exception):
    pass


# ------------------------------------------------------------------ ścieżki Jarva i Komputera

def korzen() -> Path:
    """Korzeń instalacji (jarvo/sciezki.py): JARVO_ROOT, a bez niego z JARVO_DATA_DIR (`<root>/dane/jarvo`)
    albo HERMES_HOME (`<root>/dane` lub `<root>/dane/profiles/<agent>`), na końcu domyślny korzeń systemu."""
    if os.environ.get("JARVO_ROOT"):
        return Path(os.environ["JARVO_ROOT"]).expanduser()
    if os.environ.get("JARVO_DATA_DIR"):
        return Path(os.environ["JARVO_DATA_DIR"]).parent.parent
    if os.environ.get("HERMES_HOME"):
        h = Path(os.environ["HERMES_HOME"])
        return (h.parent.parent if h.parent.name == "profiles" else h).parent
    if WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Jarvo"
    if MACOS:
        return Path.home() / ".jarvo"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "jarvo"


def dane_komputera() -> Path:
    """`<dane>/jarvo/komputer`: dziennik decyzji i plik pauzy (komputer/usluga.py katalogi)."""
    jd = os.environ.get("JARVO_DATA_DIR")
    return (Path(jd) if jd else korzen() / "dane" / "jarvo") / "komputer"


def ustawienia_komputera() -> dict:
    """`<stan>/komputer/ustawienia.json`: wlaczony, okno, na Linuksie `ekran` (zmienne pulpitu)."""
    try:
        d = json.loads((korzen() / "stan" / "komputer" / "ustawienia.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _program(nazwa: str) -> str | None:
    return shutil.which(nazwa)


def wejscie_ekranu(ust: dict, env: dict | None = None) -> tuple[list[str], dict]:
    """Argumenty wejścia ffmpeg dla ekranu z oknem Komputera i zmienne środowiska dla ffmpeg."""
    if not ust.get("okno"):
        raise Blad("Komputer Jarva nie ma okna na ekranie (działa w tle albo nie jest włączony): nagranie pokazałoby "
                   "pulpit bez przeglądarki. Okno włącza właściciel: `jarvo komputer okno on`.")
    if WINDOWS:
        return ["-f", "gdigrab", "-framerate", str(KLATKI), "-draw_mouse", "1", "-i", "desktop"], {}
    if MACOS:
        return ["-f", "avfoundation", "-framerate", str(KLATKI), "-capture_cursor", "1",
                "-i", "Capture screen 0:none"], {}
    env = os.environ if env is None else env
    ekran = ust.get("ekran") if isinstance(ust.get("ekran"), dict) else {}
    display = str(ekran.get("DISPLAY") or env.get("DISPLAY") or "")
    if not display:
        raise Blad("brak pulpitu X11 (DISPLAY) dla okna Komputera; sam Wayland bez Xwayland nie da się nagrać. "
                   "Właściciel: `jarvo komputer okno on` w terminalu na pulpicie.")
    dodatkowe = {"DISPLAY": display}
    if ekran.get("XAUTHORITY"):
        dodatkowe["XAUTHORITY"] = str(ekran["XAUTHORITY"])
    return ["-f", "x11grab", "-framerate", str(KLATKI), "-draw_mouse", "1", "-i", display], dodatkowe


def _nice() -> list[str]:
    if WINDOWS:
        return []
    n = _program("nice")
    return [n, "-n", "15"] if n else []


def polecenie_ffmpeg(ffmpeg: str, wejscie: list[str], plik: Path) -> list[str]:
    """Nagranie jednego segmentu: twardy limit `-t MAKS_SEGMENT`, h264 ultrafast (parzyste wymiary dla yuv420p)."""
    return [*_nice(), ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *wejscie, "-t", str(MAKS_SEGMENT),
            "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-pix_fmt", "yuv420p", "-threads", "2", str(plik)]


def _flagi_procesu(w_tle: bool = False) -> int:
    if not WINDOWS:
        return 0
    if w_tle:
        return subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW


# ------------------------------------------------------------------ stan nagrania

def _teraz_iso() -> str:
    return datetime.fromtimestamp(_teraz(), timezone.utc).isoformat(timespec="seconds")


def wczytaj(k: Path) -> dict:
    try:
        d = json.loads((k / PLIK_STANU).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict) or not isinstance(d.get("segmenty"), list):
        d = {"segmenty": []}
    return d


def zapisz(k: Path, stan: dict) -> None:
    k.mkdir(parents=True, exist_ok=True)
    tmp = k / f"{PLIK_STANU}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(stan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for proba in range(20):                    # Windows: plik chwilowo otwarty przez drugi proces (WinError 5/32)
        try:
            os.replace(tmp, k / PLIK_STANU)
            return
        except PermissionError:
            if proba == 19:
                raise
            time.sleep(0.05)


def _segment(stan: dict, nr: int) -> dict:
    for s in stan["segmenty"]:
        if s.get("nr") == nr:
            return s
    raise Blad(f"nie ma segmentu {nr}")


def _nagrywany(stan: dict) -> dict | None:
    return next((s for s in stan["segmenty"] if s.get("status") == "nagrywa"), None)


def _nazwa(nr: int, rozszerzenie: str) -> str:
    return f"seg-{nr:02d}.{rozszerzenie}"


def _krotko(s: dict) -> dict:
    return {k: s.get(k) for k in ("nr", "opis", "status", "powod", "start", "koniec", "dlugosc_s", "kroki_komputera")
            if s.get(k) is not None}


def zakoncz_segment(k: Path, nr: int, status: str, powod: str, *, ostatni_krok: float | None = None,
                    kroki: int = 0) -> dict:
    """Zapis końca segmentu (jedyne miejsce, które ustawia status ok/nieudany); nagranie nieudanego idzie do kosza."""
    stan = wczytaj(k)
    s = _segment(stan, nr)
    koniec = _teraz()
    dlugosc = max(0.0, min(koniec - float(s["start_ts"]), MAKS_SEGMENT))
    uzyteczne = dlugosc
    if ostatni_krok is not None and powod.startswith("cisza"):
        uzyteczne = max(1.0, min(dlugosc, ostatni_krok - float(s["start_ts"]) + ZAPAS_PO_KROKU))
    s.update(status=status, powod=powod, koniec=_teraz_iso(), koniec_ts=koniec, dlugosc_s=round(dlugosc, 1),
             uzyteczne_s=round(uzyteczne, 1), kroki_komputera=kroki)
    zapisz(k, stan)
    if status != "ok":
        (k / s["plik"]).unlink(missing_ok=True)
    for r in ("straz", "stop"):
        (k / _nazwa(nr, r)).unlink(missing_ok=True)
    return s


def _straz(k: Path, nr: int) -> dict:
    try:
        d = json.loads((k / _nazwa(nr, "straz")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _zabij(pid) -> None:
    if isinstance(pid, int) and pid > 0:
        try:
            os.kill(pid, 15)                   # SIGTERM; na Windows TerminateProcess
        except OSError:
            pass


def odswiez(k: Path) -> dict:
    """Segment „nagrywa”, którego strażnik nie daje znaku życia (awaria, restart komputera): nieudany."""
    stan = wczytaj(k)
    s = _nagrywany(stan)
    if s is not None:
        st = _straz(k, s["nr"])
        if _teraz() - float(st.get("t") or s["start_ts"]) > MARTWY:
            _zabij(st.get("ffmpeg"))
            _zabij(st.get("pid"))
            zakoncz_segment(k, s["nr"], "nieudany", "strażnik nagrania nie odpowiada")
            stan = wczytaj(k)
    return stan


def zatrzymaj(k: Path, nieudany: bool) -> dict | None:
    """Prosi strażnika o koniec bieżącego segmentu i czeka na jego zapis; None, gdy nic się nie nagrywa."""
    s = _nagrywany(odswiez(k))
    if s is None:
        return None
    nr = s["nr"]
    (k / _nazwa(nr, "stop")).write_text(json.dumps({"nieudany": nieudany}), encoding="utf-8")
    koniec = _teraz() + CZAS_ZAMKNIECIA
    while _teraz() < koniec:
        s = _segment(odswiez(k), nr)
        if s.get("status") != "nagrywa":
            return s
        _spij(0.2)
    st = _straz(k, nr)
    _zabij(st.get("ffmpeg"))
    _zabij(st.get("pid"))
    return zakoncz_segment(k, nr, "nieudany", f"segment nie zamknął się w {CZAS_ZAMKNIECIA} s")


# ------------------------------------------------------------------ polecenia

def _odpal_straz(k: Path, nr: int) -> None:
    """Strażnik segmentu jako osobny proces w tle (przeżywa to wywołanie; ffmpeg jest jego dzieckiem)."""
    with open(k / "straz.log", "ab") as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_pilnuj", "--katalog", str(k),
                          "--nr", str(nr)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
                         cwd=str(k), close_fds=True, start_new_session=not WINDOWS,
                         creationflags=_flagi_procesu(w_tle=True))


def start(k: Path, opis: str) -> dict:
    opis = " ".join(opis.split())[:120]
    if not opis:
        raise Blad("podaj opis kroku: start \"<krok>\"")
    poprzedni = zatrzymaj(k, False)
    stan = wczytaj(k)
    if len(stan["segmenty"]) >= MAKS_SEGMENTOW:
        raise Blad(f"limit {MAKS_SEGMENTOW} segmentów w jednym nagraniu: zrób film albo wyczyść katalog")
    ffmpeg = _program("ffmpeg")
    if not ffmpeg:
        raise Blad("brak ffmpeg w PATH (pełny ffmpeg floty z manifestu narzędzi)")
    dane = dane_komputera()
    if (dane / "pauza").exists():
        raise Blad("Komputer Jarva jest wstrzymany: nie nagrywam (czekaj na właściciela)")
    wejscie, env = wejscie_ekranu(ustawienia_komputera())
    nr = len(stan["segmenty"]) + 1
    plik = _nazwa(nr, "mkv")
    dziennik = dane / "dziennik.jsonl"
    try:
        od = dziennik.stat().st_size
    except OSError:
        od = 0
    seg = {"nr": nr, "opis": opis, "plik": plik, "status": "nagrywa", "start": _teraz_iso(), "start_ts": _teraz(),
           "dziennik": str(dziennik), "dziennik_od": od, "pauza": str(dane / "pauza"),
           "ffmpeg": polecenie_ffmpeg(ffmpeg, wejscie, k / plik), "env": env}
    stan["segmenty"].append(seg)
    zapisz(k, stan)
    _odpal_straz(k, nr)
    return {"ok": True, "segment": nr, "opis": opis, "maks_s": MAKS_SEGMENT, "cisza_s": CISZA,
            "poprzedni": _krotko(poprzedni) if poprzedni else None}


def stop(k: Path, nieudany: bool) -> dict:
    s = zatrzymaj(k, nieudany)
    if s is not None:
        return {"ok": True, **_krotko(s), "do_filmu": s.get("status") == "ok"}
    stan = wczytaj(k)
    if not stan["segmenty"]:
        raise Blad("nic się nie nagrywa (start \"<krok>\")")
    s = stan["segmenty"][-1]
    return {"ok": True, **_krotko(s), "do_filmu": s.get("status") == "ok", "juz_zakonczony": True}


def czytaj_dziennik(sciezka: Path, od: int) -> tuple[list[dict], int]:
    """Nowe pełne wiersze dziennika od bajtu `od`; po rotacji (plik krótszy) od początku."""
    try:
        rozmiar = sciezka.stat().st_size
    except OSError:
        return [], od
    if rozmiar < od:
        od = 0
    if rozmiar == od:
        return [], od
    with open(sciezka, "rb") as f:
        f.seek(od)
        dane = f.read(rozmiar - od)
    koniec = dane.rfind(b"\n")
    if koniec < 0:
        return [], od
    wpisy = []
    for linia in dane[:koniec].splitlines():
        try:
            w = json.loads(linia)
        except ValueError:
            continue
        if isinstance(w, dict):
            wpisy.append(w)
    return wpisy, od + koniec + 1


def _uruchom_ffmpeg(argv: list[str], env: dict, log) -> subprocess.Popen:
    return subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log, env=env,
                            creationflags=_flagi_procesu())


def _zamknij_ffmpeg(p) -> None:
    """`q` na stdin: ffmpeg domyka plik; po 10 s zabity (Matroska i tak da się odczytać)."""
    if p.poll() is not None:
        return
    try:
        p.stdin.write(b"q")
        p.stdin.flush()
        p.stdin.close()
    except (OSError, ValueError):
        pass
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait(5)


def _ogon(plik: Path) -> str:
    try:
        return " ".join(plik.read_text(encoding="utf-8", errors="replace").split()[-25:])
    except OSError:
        return ""


def _ocena(k: Path, nr: int, s: dict, p, log, plik_logu: Path) -> tuple[str, str, int, float | None]:
    """Pętla strażnika do pierwszego powodu końca: (status, powód, liczba kroków, czas ostatniego kroku)."""
    start_ts = float(s["start_ts"])
    dziennik, pauza, od = Path(s["dziennik"]), Path(s["pauza"]), int(s.get("dziennik_od") or 0)
    plik_stop, plik_straz = k / _nazwa(nr, "stop"), k / _nazwa(nr, "straz")
    kroki, ostatni_krok = 0, None
    while True:
        teraz = _teraz()
        plik_straz.write_text(json.dumps({"pid": os.getpid(), "ffmpeg": p.pid, "t": teraz}), encoding="utf-8")
        if plik_stop.exists():
            try:
                nieudany = bool(json.loads(plik_stop.read_text(encoding="utf-8")).get("nieudany"))
            except (OSError, ValueError, AttributeError):
                nieudany = False
            return ("nieudany", "stop --nieudany", kroki, ostatni_krok) if nieudany else \
                ("ok", "stop", kroki, ostatni_krok)
        kod = p.poll()
        if kod == 0:
            return "ok", f"limit {MAKS_SEGMENT} s", kroki, ostatni_krok
        if kod is not None:
            log.flush()
            return "nieudany", f"ffmpeg zakończył się kodem {kod}: {_ogon(plik_logu)}"[:300], kroki, ostatni_krok
        wpisy, od = czytaj_dziennik(dziennik, od)
        for w in wpisy:
            d = str(w.get("decyzja") or "")
            if d in PRZEJECIE or (d in NIEUDANE and w.get("narzedzie") != "ster"):
                zasada = f" ({w['zasada']})" if w.get("zasada") else ""
                return "nieudany", f"Komputer: {d}{zasada}", kroki, ostatni_krok
            if d == "tak":
                kroki, ostatni_krok = kroki + 1, teraz
        if pauza.exists():
            return "nieudany", "Komputer wstrzymany (pauza)", kroki, ostatni_krok
        if ostatni_krok is None and teraz - start_ts >= CISZA:
            return "nieudany", f"brak kroków w Komputerze przez {CISZA} s od startu", kroki, ostatni_krok
        if ostatni_krok is not None and teraz - ostatni_krok >= CISZA:
            return "ok", f"cisza {CISZA} s po ostatnim kroku", kroki, ostatni_krok
        _spij(CO_ILE)


def pilnuj(k: Path, nr: int) -> dict:
    """Strażnik segmentu: uruchamia ffmpeg i zamyka segment na `stop`, przy odmowie, pauzie, ciszy albo limicie."""
    s = _segment(wczytaj(k), nr)
    plik_logu = k / _nazwa(nr, "log")
    with open(plik_logu, "ab") as log:
        p = _uruchom_ffmpeg(s["ffmpeg"], {**os.environ, **(s.get("env") or {})}, log)
        try:
            status, powod, kroki, ostatni_krok = _ocena(k, nr, s, p, log, plik_logu)
        except Exception as e:                 # awaria strażnika: segment nieudany, ffmpeg nie zostaje bez nadzoru
            status, powod, kroki, ostatni_krok = "nieudany", f"strażnik: {type(e).__name__}: {e}"[:300], 0, None
        finally:
            _zamknij_ffmpeg(p)
    return zakoncz_segment(k, nr, status, powod, ostatni_krok=ostatni_krok, kroki=kroki)


def polecenie_filmu(ffmpeg: str, k: Path, segmenty: list[dict], cel: Path) -> tuple[list[str], float]:
    """Jedno wywołanie ffmpeg: każdy segment przycięty do części z pracą, przyspieszony do najwyżej MAKS_UJECIE s,
    wpasowany w 1280×720 i sklejony (concat) bez przejść; h264 yuv420p, bez dźwięku."""
    wejscia, filtry, etykiety, razem = [], [], [], 0.0
    for i, s in enumerate(segmenty):
        u = max(0.5, float(s.get("uzyteczne_s") or s.get("dlugosc_s") or MAKS_SEGMENT))
        tempo = max(1.0, u / MAKS_UJECIE)
        razem += u / tempo
        wejscia += ["-i", str(k / s["plik"])]
        filtry.append(f"[{i}:v]setpts=PTS-STARTPTS,trim=duration={u:.2f},setpts=(PTS-STARTPTS)/{tempo:.3f},"
                      f"fps={FILM_KLATKI},scale={FILM_SZER}:{FILM_WYS}:force_original_aspect_ratio=decrease,"
                      f"pad={FILM_SZER}:{FILM_WYS}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[v{i}]")
        etykiety.append(f"[v{i}]")
    filtry.append(f"{''.join(etykiety)}concat=n={len(segmenty)}:v=1:a=0[film]")
    argv = [*_nice(), ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *wejscia,
            "-filter_complex", ";".join(filtry), "-map", "[film]", "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-threads", "2", str(cel)]
    return argv, razem


def _uruchom(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=900,
                          creationflags=_flagi_procesu())


def film(k: Path, wyjscie: Path | None = None) -> dict:
    zamkniety = zatrzymaj(k, False)
    stan = wczytaj(k)
    udane = [s for s in stan["segmenty"] if s.get("status") == "ok" and (k / s["plik"]).is_file()
             and (k / s["plik"]).stat().st_size > 0]
    if not udane:
        raise Blad("brak udanych segmentów: film nie powstał (nagrywaj tylko kroki, które działają)")
    ffmpeg = _program("ffmpeg")
    if not ffmpeg:
        raise Blad("brak ffmpeg w PATH (pełny ffmpeg floty z manifestu narzędzi)")
    cel = (wyjscie or k / PLIK_FILMU).resolve()
    cel.parent.mkdir(parents=True, exist_ok=True)
    tmp = cel.with_name(cel.stem + ".tmp.mp4")
    argv, dlugosc = polecenie_filmu(ffmpeg, k, udane, tmp)
    try:
        wynik = _uruchom(argv)
    except subprocess.TimeoutExpired:
        tmp.unlink(missing_ok=True)
        raise Blad("ffmpeg nie skończył filmu w 15 min") from None
    if wynik.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        blad = (wynik.stderr or b"").decode("utf-8", "replace").strip()[-300:]
        raise Blad(f"ffmpeg nie złożył filmu (kod {wynik.returncode}): {blad}")
    os.replace(tmp, cel)
    pominiete = [_krotko(s) for s in stan["segmenty"] if s not in udane]
    return {"ok": True, "film": str(cel), "dlugosc_s": round(dlugosc, 1),
            "ujecia": [{"nr": s["nr"], "opis": s["opis"]} for s in udane], "pominiete": pominiete,
            "zamkniety_segment": _krotko(zamkniety) if zamkniety else None}


def stan_nagrania(k: Path) -> dict:
    stan = odswiez(k)
    s = _nagrywany(stan)
    return {"ok": True, "katalog": str(k), "nagrywa": s["nr"] if s else None,
            "udane": sum(1 for x in stan["segmenty"] if x.get("status") == "ok"),
            "segmenty": [_krotko(x) for x in stan["segmenty"]],
            "film": str(k / PLIK_FILMU) if (k / PLIK_FILMU).is_file() else None,
            "limity": {"maks_segment_s": MAKS_SEGMENT, "cisza_s": CISZA, "maks_segmentow": MAKS_SEGMENTOW,
                       "maks_ujecie_s": MAKS_UJECIE}}


def wyczysc(k: Path, z_filmem: bool) -> dict:
    if _nagrywany(odswiez(k)) is not None:
        raise Blad("trwa nagrywanie: najpierw stop")
    usuniete = 0
    if k.is_dir():
        for p in k.iterdir():
            if p.is_file() and (p.name.startswith(("seg-", PLIK_STANU)) or p.name == "straz.log"
                                or (z_filmem and p.name == PLIK_FILMU)):
                p.unlink()
                usuniete += 1
        if not any(k.iterdir()):
            k.rmdir()
    return {"ok": True, "usuniete": usuniete, "film_zostal": (k / PLIK_FILMU).is_file()}


def main(argv: list[str] | None = None) -> int:
    wspolne = argparse.ArgumentParser(add_help=False)
    wspolne.add_argument("--katalog", type=Path, default=Path("out") / "nagranie",
                         help="katalog roboczy nagrania (domyślnie out/nagranie)")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="polecenie", required=True, metavar="{start,stop,film,stan,wyczysc}")
    p = sub.add_parser("start", parents=[wspolne], help="nagrywa jeden krok")
    p.add_argument("opis")
    p = sub.add_parser("stop", parents=[wspolne], help="koniec kroku")
    p.add_argument("--nieudany", action="store_true", help="krok nie wyszedł: segment nie trafi do filmu")
    p = sub.add_parser("film", parents=[wspolne], help="film z udanych segmentów")
    p.add_argument("--wyjscie", type=Path)
    sub.add_parser("stan", parents=[wspolne], help="stan nagrania (JSON)")
    p = sub.add_parser("wyczysc", parents=[wspolne], help="usuwa robocze nagrania")
    p.add_argument("--z-filmem", action="store_true")
    p = sub.add_parser("_pilnuj", parents=[wspolne])
    p.add_argument("--nr", type=int, required=True)
    a = ap.parse_args(argv)
    k = a.katalog.expanduser().resolve()
    try:
        if a.polecenie == "start":
            wynik = start(k, a.opis)
        elif a.polecenie == "stop":
            wynik = stop(k, a.nieudany)
        elif a.polecenie == "film":
            wynik = film(k, a.wyjscie)
        elif a.polecenie == "stan":
            wynik = stan_nagrania(k)
        elif a.polecenie == "wyczysc":
            wynik = wyczysc(k, a.z_filmem)
        else:
            pilnuj(k, a.nr)
            return 0
    except Blad as e:
        print(json.dumps({"ok": False, "blad": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(wynik, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
