"""Procesy rąk: odcisk (PID + czas startu), rejestr działających sterowników i zatrzymanie.

Rejestr to pliki `<stan>/rece/procesy/<pid bramki>.json`: {bramka: {pid, odcisk}, sterownik: {pid, odcisk},
gniazdo, zgoda, profil, start, gotowy}. Zapisuje go nadzór `serve` w bramce, czyta `mcp` i `status` (czy demon dla
tego gniazda działa i jest gotowy) oraz `jarvo komputer rece off` (zatrzymuje wszystko od razu). Odcisk odróżnia
proces od innego, który dostał ten sam PID, więc zatrzymanie nigdy nie trafi w cudzy program.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

WINDOWS = os.name == "nt"
STOP = ".stop"


def _k32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    return k32


def _czas_startu_windows(k32, h) -> int | None:
    import ctypes
    from ctypes import wintypes
    start, koniec, jadro, uzytk = (wintypes.FILETIME() for _ in range(4))
    if not k32.GetProcessTimes(h, ctypes.byref(start), ctypes.byref(koniec), ctypes.byref(jadro), ctypes.byref(uzytk)):
        return None
    return (start.dwHighDateTime << 32) | start.dwLowDateTime


def odcisk(pid: int | None) -> str | None:
    """Czas startu działającego procesu jako tekst; None, gdy procesu nie ma (także zombie)."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    if WINDOWS:
        import ctypes
        from ctypes import wintypes
        k32 = _k32()
        h = k32.OpenProcess(0x1000, False, pid)              # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            kod = wintypes.DWORD()
            if not k32.GetExitCodeProcess(h, ctypes.byref(kod)) or kod.value != 259:       # STILL_ACTIVE
                return None
            czas = _czas_startu_windows(k32, h)
            return None if czas is None else str(czas)
        finally:
            k32.CloseHandle(h)
    if Path("/proc/self/stat").exists():                       # Linux: pole 22 (starttime) z /proc
        try:
            pola = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace").rpartition(")")[2].split()
        except OSError:
            return None
        return pola[19] if len(pola) > 19 and pola[0] not in ("Z", "X") else None
    ps = "/bin/ps" if os.path.exists("/bin/ps") else "ps"
    try:
        r = subprocess.run([ps, "-o", "stat=", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10,
                           env={**os.environ, "LC_ALL": "C", "TZ": "UTC0"})
    except (OSError, subprocess.SubprocessError):
        return None
    stan, _, start = r.stdout.strip().partition(" ")
    start = " ".join(start.split())
    return None if not stan or stan.startswith("Z") or not start else f"ps:{start}"


def zyje(pid: int | None, odc: str | None) -> bool:
    return odc is not None and odcisk(pid) == odc


def zabij(pid: int, odc: str | None, *, lagodnie: bool = True, czekaj: float = 3.0) -> bool:
    """Zatrzymuje JEDEN proces (bez drzewa), tylko gdy to dalej ten sam proces. POSIX: SIGTERM, po `czekaj` SIGKILL;
    Windows: TerminateProcess (sterownik i tak kończy się sam po zamknięciu potoku stdin)."""
    if odc is None or odcisk(pid) != odc:
        return False
    if WINDOWS:
        k32 = _k32()
        h = k32.OpenProcess(0x0001 | 0x1000 | 0x00100000, False, pid)   # TERMINATE | QUERY_LIMITED | SYNCHRONIZE
        if not h:
            return False
        try:
            if str(_czas_startu_windows(k32, h)) != odc:
                return False
            ok = bool(k32.TerminateProcess(h, 1))
            k32.WaitForSingleObject(h, int(czekaj * 1000))
            return ok
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, signal.SIGTERM if lagodnie else signal.SIGKILL)
    except OSError:
        return False
    koniec = time.monotonic() + czekaj
    while time.monotonic() < koniec:
        if odcisk(pid) != odc:
            return True
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return True


class Rejestr:
    def __init__(self, katalog: Path):
        self.katalog = Path(katalog)

    def plik(self, pid_bramki: int) -> Path:
        return self.katalog / f"{int(pid_bramki)}.json"

    def zapisz(self, wpis: dict) -> None:
        from jarvo import przenosne
        przenosne.zapisz_atomowo(self.plik(wpis["bramka"]["pid"]), json.dumps(wpis, ensure_ascii=False) + "\n",
                                 tryb=0o600)

    def usun(self, pid_bramki: int) -> None:
        for p in (self.plik(pid_bramki), self.znacznik_stopu(pid_bramki)):
            try:
                p.unlink()
            except OSError:
                pass

    def znacznik_stopu(self, pid_bramki: int) -> Path:
        return self.katalog / f"{int(pid_bramki)}{STOP}"

    def wpisy(self, *, sprzataj: bool = True) -> list[dict]:
        """Działające wpisy (bramka żyje); martwe wpisy usuwa, gdy `sprzataj`."""
        wynik = []
        try:
            pliki = sorted(self.katalog.glob("*.json"))
        except OSError:
            return []
        for p in pliki:
            try:
                wpis = json.loads(p.read_text(encoding="utf-8"))
                bramka = wpis["bramka"]
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if zyje(bramka.get("pid"), bramka.get("odcisk")):
                wynik.append(wpis)
            elif sprzataj:
                try:
                    p.unlink()
                except OSError:
                    pass
        return wynik

    def dla_gniazda(self, gniazdo: str) -> dict | None:
        klucz = _klucz_gniazda(gniazdo)
        return next((w for w in self.wpisy() if _klucz_gniazda(str(w.get("gniazdo") or "")) == klucz), None)

    def zatrzymaj_wszystko(self, czekaj: float = 3.0) -> int:
        """Znacznik stopu dla każdego nadzoru, a po `czekaj` s twarde zatrzymanie sterownika i bramki, która jeszcze
        działa. Zwraca liczbę zatrzymanych sterowników."""
        wpisy = self.wpisy()
        for w in wpisy:
            try:
                self.znacznik_stopu(w["bramka"]["pid"]).write_text("off\n", encoding="utf-8")
            except OSError:
                pass
        koniec = time.monotonic() + czekaj
        while time.monotonic() < koniec and any(self.plik(w["bramka"]["pid"]).exists() for w in wpisy):
            time.sleep(0.1)
        for w in wpisy:
            s, b = w.get("sterownik") or {}, w["bramka"]
            if not self.plik(b["pid"]).exists():           # nadzór skończył sam i posprzątał po sobie
                continue
            if s.get("pid"):
                zabij(int(s["pid"]), s.get("odcisk"), lagodnie=False)
            if int(b["pid"]) != os.getpid() and zyje(b.get("pid"), b.get("odcisk")):
                zabij(int(b["pid"]), b.get("odcisk"), lagodnie=False)
            self.usun(b["pid"])
        return len(wpisy)


def _klucz_gniazda(g: str) -> str:
    return os.path.normcase(g.strip()) if WINDOWS else g.strip()
