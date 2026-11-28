"""Straż sesji omp: jeden proces na sesję i koniec pliku sesji tam, gdzie skończył ostatni prawdziwy proces.

omp wznawia sesję od ostatniej linii pliku (omp://session.md: „loading rebuilds the leaf from the last physical
entry”). Zapomniany drugi proces omp na tej samej sesji przy zamknięciu (SIGHUP przy reboocie) dopisuje na końcu
swój `session_exit` z rodzicem ze swojego starego punktu, więc następne wznowienie pokazuje rozmowę sprzed dni.
28.11: omp 18.22 wisiał 9 dni na sesji operatora, reboot, wznowienie wróciło do 18.11 i streściło tamten stan.

  procesy()              procesy omp tego użytkownika: {pid, start, stary, sesja}; sesja = id albo plik z `--resume`,
                         a dla omp w terminalu plik z ~/.omp/agent/terminal-sessions/pts-N (aktualny po /resume);
                         stary = program podmieniony po starcie procesu (aktualizacja omp), czyli wersja sprzed niej
  procesy_sesji(id)      procesy z tą sesją
  koniec(plik)           {ok, powod, lisc, najnowsza, cel, czas}: ostatnia linia to „wyjście z przeszłości”, gdy jest
                         `session_exit`, którego gałąź nie ma ostatniej wiadomości zapisanej przed nim, a do tego jest
                         po sygnale albo ze starszej wersji omp (zwykłe wyjście tej samej wersji = świadome /tree, ok);
                         `cel` = ostatni wpis przed ciągiem takich wyjść (punkt ostatniego prawdziwego procesu)
  napraw(plik)           dopisuje wpis `custom` `jarvo-straz-konca` z rodzicem `cel`; reszta pliku nietknięta
  zamknij(pidy)          SIGTERM, do 20 s, potem SIGKILL; zwraca pidy, które się skończyły
  apt_pracuje()          polecenia apt, dpkg i unattended-upgrade w toku (restart w trakcie psuje pakiety)
"""
from __future__ import annotations

import datetime
import json
import os
import re
import secrets
import signal
import time
from pathlib import Path

TERMINALE = Path.home() / ".omp" / "agent" / "terminal-sessions"
TYP_NAPRAWY = "jarvo-straz-konca"
ZAMKNIJ_S = 20.0
_CZAS = re.compile(rb'"timestamp":"([0-9T:.Z-]+)"')
_WERSJA = re.compile(rb'"runtime":\{"version":"([0-9.]+)"')
_WPIS = re.compile(rb'"id":"([0-9a-f]{8})","parentId":(?:null|"([0-9a-f]{8})")')
_TYP = re.compile(rb'^\{"type":"([a-z_]+)"')
_ID_SESJI = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
_APT = ("apt", "apt-get", "aptitude", "dpkg", "unattended-upgr")


# ---------------------------------------------------------------- procesy

def _czytaj(sciezka: str) -> str:
    try:
        with open(sciezka, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _argumenty(pid: int) -> list[str]:
    return [a for a in _czytaj(f"/proc/{pid}/cmdline").split("\0") if a]


def _start_systemu() -> float:
    m = re.search(r"^btime (\d+)", _czytaj("/proc/stat"), re.M)
    return float(m.group(1)) if m else 0.0


def _stat(pid: int) -> list[str]:
    """Pola /proc/<pid>/stat po nazwie procesu (nazwa może mieć spacje i nawiasy): [0] = stan, [4] = tty_nr."""
    s = _czytaj(f"/proc/{pid}/stat")
    return s[s.rfind(")") + 2:].split() if ")" in s else []


def pts(tty_nr: int) -> int | None:
    """Numer /dev/pts/N z tty_nr jądra (główne 136–143 = pts)."""
    glowny, poboczny = (tty_nr >> 8) & 0xFFF, (tty_nr & 0xFF) | ((tty_nr >> 12) & 0xFFF00)
    return (glowny - 136) * 256 + poboczny if 136 <= glowny <= 143 else None


def sesja_z_argumentow(argv: list[str]) -> str | None:
    for i, a in enumerate(argv):
        for flaga in ("--resume", "--restore", "-r"):
            if a == flaga and i + 1 < len(argv):
                return argv[i + 1]
            if a.startswith(flaga + "="):
                return a.split("=", 1)[1]
    return None


def id_sesji(sesja: str | None) -> str | None:
    """Id sesji z id (także przedrostka) albo ze ścieżki pliku `<czas>_<id>.jsonl`."""
    if not sesja:
        return None
    m = _ID_SESJI.search(Path(sesja).name)
    return m.group(1) if m else (Path(sesja).name if "/" not in sesja else None)


def _sesja_terminala(pid: int, start: float, pola: list[str]) -> str | None:
    try:
        n = pts(int(pola[4]))
    except (IndexError, ValueError):
        return None
    plik = TERMINALE / f"pts-{n}" if n is not None else None
    try:
        if plik is None or plik.stat().st_mtime < start - 1:   # plik po innym omp, który był wcześniej na tym pts
            return None
    except OSError:
        return None
    linie = _czytaj(str(plik)).splitlines()
    return linie[1].strip() if len(linie) > 1 and linie[1].strip().endswith(".jsonl") else None


def procesy() -> list[dict]:
    """Procesy omp tego użytkownika (bez procesów pomocniczych `__omp_worker…`). Poza Linuksem: []."""
    if not os.path.isdir("/proc"):
        return []
    btime, tik = _start_systemu(), os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    wynik = []
    for wpis in os.scandir("/proc"):
        if not wpis.name.isdigit():
            continue
        pid = int(wpis.name)
        try:
            exe = os.readlink(f"/proc/{pid}/exe")
        except OSError:
            continue
        stary = exe.endswith(" (deleted)")
        argv = _argumenty(pid)
        if os.path.basename(exe.removesuffix(" (deleted)")) != "omp" and \
                not (argv and os.path.basename(argv[0]) == "omp"):
            continue
        if any(a.startswith("__omp_") for a in argv[1:2]):
            continue
        pola = _stat(pid)
        try:
            start = btime + int(pola[19]) / tik
        except (IndexError, ValueError):
            start = 0.0
        sesja = _sesja_terminala(pid, start, pola) or sesja_z_argumentow(argv)
        wynik.append({"pid": pid, "start": round(start), "stary": stary, "sesja": sesja, "id": id_sesji(sesja)})
    return sorted(wynik, key=lambda p: p["start"])


def procesy_sesji(sesja: str, wszystkie: list[dict] | None = None) -> list[dict]:
    """Procesy omp z sesją `sesja` (id albo jego przedrostek)."""
    return [p for p in (procesy() if wszystkie is None else wszystkie)
            if p["id"] and (p["id"].startswith(sesja) or sesja.startswith(p["id"]))]


def zyje(pid: int) -> bool:
    pola = _stat(pid)
    return bool(pola) and pola[0] != "Z"


def zamknij(pidy: list[int], czas: float = ZAMKNIJ_S) -> list[int]:
    """SIGTERM (omp zapisuje wyjście), po `czas` s SIGKILL. Zwraca pidy, które już nie żyją."""
    for pid in pidy:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    koniec = time.monotonic() + czas
    while time.monotonic() < koniec and any(zyje(p) for p in pidy):
        time.sleep(0.25)
    for pid in pidy:
        if zyje(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    time.sleep(0.2)
    return [p for p in pidy if not zyje(p)]


def apt_pracuje() -> list[str]:
    """Polecenia apt/dpkg w toku (bez stałego strażnika `unattended-upgrade-shutdown`, który czeka na sygnał)."""
    if not os.path.isdir("/proc"):
        return []
    wynik = []
    for wpis in os.scandir("/proc"):
        if wpis.name.isdigit() and _czytaj(f"/proc/{wpis.name}/comm").strip() in _APT:
            argv = " ".join(_argumenty(int(wpis.name)))
            if "unattended-upgrade-shutdown" not in argv:
                wynik.append(argv[:120])
    return wynik


# ---------------------------------------------------------------- koniec pliku sesji

def _wersja(tekst) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(tekst or ""))[:3])


def _sciezka(rodzic: dict[str, str | None], od: str) -> set[str]:
    widziane, i = set(), od
    while i and i not in widziane:
        widziane.add(i)
        i = rodzic.get(i)
    return widziane


def koniec(plik: Path | str) -> dict:
    """Czy ostatnia linia pliku sesji to wyjście z przeszłości (patrz opis modułu); wtedy `cel` do naprawy."""
    wynik = {"ok": True, "powod": "", "lisc": None, "najnowsza": None, "cel": None, "czas": None}
    rodzic: dict[str, str | None] = {}
    czas: dict[str, str] = {}
    kolejnosc: list[str] = []
    # wyjście → (dane, wersja omp, ostatnia wiadomość przed nim, jej wersja omp)
    wyjscia: dict[str, tuple[dict, tuple, str | None, tuple]] = {}
    wiadomosc, wersja_wiadomosci = None, ()
    try:
        with open(plik, "rb") as f:
            for linia in f:
                m = _WPIS.search(linia)
                if not m:
                    continue
                i = m.group(1).decode()
                rodzic[i] = m.group(2).decode() if m.group(2) else None
                kolejnosc.append(i)
                if (c := _CZAS.search(linia)) is not None:
                    czas[i] = c.group(1).decode()
                t = _TYP.match(linia)
                if t and t.group(1) == b"message":
                    w = _WERSJA.search(linia)
                    wiadomosc, wersja_wiadomosci = i, _wersja(w.group(1).decode() if w else "")
                elif b'"customType":"session_exit"' in linia[:300]:
                    try:
                        d = json.loads(linia)
                    except ValueError:
                        continue
                    dane = d.get("data") if isinstance(d.get("data"), dict) else {}
                    wyjscia[i] = (dane, _wersja((d.get("runtime") or {}).get("version")), wiadomosc,
                                  wersja_wiadomosci)
    except OSError as e:
        return {**wynik, "ok": False, "powod": f"brak pliku sesji: {e.strerror}"}
    if not kolejnosc:
        return wynik

    def z_przeszlosci(i: str) -> bool:
        if i not in wyjscia:
            return False
        dane, wersja, przed, wersja_przed = wyjscia[i]
        if przed is None or przed in _sciezka(rodzic, i):
            return False
        return dane.get("kind") != "normal" or wersja < wersja_przed

    lisc = kolejnosc[-1]
    wynik.update(lisc=lisc, najnowsza=wyjscia[lisc][2] if lisc in wyjscia else wiadomosc)
    if not z_przeszlosci(lisc):
        return wynik
    cel = next((i for i in reversed(kolejnosc[:-1]) if not z_przeszlosci(i)), None)
    dane, wersja = wyjscia[lisc][0], wyjscia[lisc][1]
    powod = (f"ostatnia linia to wyjście ({dane.get('reason') or dane.get('kind') or '?'}, omp "
             f"{'.'.join(map(str, wersja)) or '?'}) innego procesu ze starszego punktu rozmowy")
    return {**wynik, "ok": False, "powod": powod, "cel": cel, "czas": czas.get(cel or "")}


def napraw(plik: Path | str) -> dict:
    """Koniec nie prowadzi do najnowszej wiadomości: dopisuje wpis z rodzicem `cel` (omp wznowi od niego)."""
    k = koniec(plik)
    if k["ok"] or not k["cel"]:
        return {**k, "naprawiono": False}
    tresc = Path(plik).read_bytes()
    zajete = {m.group(1).decode() for m in _WPIS.finditer(tresc)}
    nowe = secrets.token_hex(4)
    while nowe in zajete:
        nowe = secrets.token_hex(4)
    teraz = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    wpis = {"type": "custom", "customType": TYP_NAPRAWY,
            "data": {"z": k["lisc"], "na": k["cel"], "powod": k["powod"]},
            "id": nowe, "parentId": k["cel"], "timestamp": teraz}
    linia = ("" if tresc.endswith(b"\n") else "\n") + json.dumps(wpis, ensure_ascii=False, separators=(",", ":")) + "\n"
    fd = os.open(plik, os.O_WRONLY | os.O_APPEND)
    try:
        os.write(fd, linia.encode("utf-8"))
    finally:
        os.close(fd)
    return {**k, "naprawiono": True, "wpis": nowe}
