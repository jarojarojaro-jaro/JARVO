"""`jarvo stan [temat…]`: stan tej instalacji jednym poleceniem, tylko odczyt i bez modelu (docs/NATYWNIE.md c4).

Po co: agent, który pyta „co tu działa, kiedy i na czym", składał odpowiedź z kilkunastu `ls`, `grep`, `systemctl`
i skryptów pisanych na miejscu, a każde takie wywołanie wysyła modelowi cały kontekst od nowa. Jedno polecenie daje te
same fakty w kilku tysiącach znaków: godzinę, serwis i adresy panelu, rutyny wszystkich profili i zegary systemu,
skarbiec i progi kompilacji, flotę z listą zadań i limitami, sprzęt, porty z procesem i usługą oraz własne polecenia
agenta z `<dane>/jarvo/polecenia`. Każda część czyta swoje źródło osobno: błąd jednej nie zabiera reszty.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from .sciezki import Uklad

TEMATY = ("serwis", "rutyny", "wiedza", "flota", "sprzet", "porty", "polecenia")
DNI = ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela")
STANY_OTWARTE = ("running", "ready", "todo", "blocked", "review", "triage")
NAZWY_STANOW = {"running": "w toku", "ready": "gotowe do startu", "todo": "czeka", "blocked": "zablokowane",
                "review": "do oceny", "triage": "do rozpisania"}
NAJWYZEJ_ZADAN = 12                         # tyle otwartych zadań z tytułem; reszta tylko w liczbach
Wolaj = Callable[[list[str]], str]


def wolaj(argv: list[str], czas: float = 6.0) -> str:
    """Wyjście programu z systemu albo pusty napis (brak programu, błąd, przekroczony czas)."""
    try:
        r = subprocess.run(argv, capture_output=True, timeout=czas, encoding="utf-8", errors="replace", check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout or ""


def kiedy(ts: float, teraz: float) -> str:
    """Pora względem dziś: „dziś 14:00", „jutro 07:50", dalej dzień tygodnia i data."""
    if not ts:
        return "nigdy"
    t, d = time.localtime(ts), time.localtime(teraz)
    godz = time.strftime("%H:%M", t)
    dni = (time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
           - time.mktime((d.tm_year, d.tm_mon, d.tm_mday, 0, 0, 0, 0, 0, -1))) / 86400
    slowo = {-1: "wczoraj", 0: "dziś", 1: "jutro"}.get(round(dni))
    return f"{slowo} {godz}" if slowo else f"{DNI[t.tm_wday]} {time.strftime('%d.%m', t)} {godz}"


def _iso(napis) -> float:
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(napis)).timestamp()
    except ValueError:
        return 0.0


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _z_yaml(p: Path, sekcja: str, klucz: str) -> str:
    """Wartość `klucz` z bloku najwyższego poziomu `sekcja:` w pliku YAML, bez biblioteki (polecenie `jarvo` biegnie
    na Pythonie instalatora, a PyYAML jest tylko w środowisku Hermesa); brak pliku albo klucza to pusty napis."""
    try:
        tekst = p.read_text(encoding="utf-8")
    except OSError:
        return ""
    blok = re.search(rf"^{re.escape(sekcja)}:[ \t]*\n((?:[ \t]+.*\n?|[ \t]*\n)*)", tekst, re.M)
    m = re.search(rf"^[ \t]+{re.escape(klucz)}:[ \t]*([^#\n]*)", blok.group(1), re.M) if blok else None
    return m.group(1).strip().strip("'\"") if m else ""


# ---------------------------------------------------------------- części

def czesc_serwis(u: Uklad, ot, _wolaj: Wolaj, _teraz: float) -> list[str]:
    from . import cli
    pomin = ("Jarvo:", "  Hermes:", "  narzędzia:", "  autostart:", "  porty:", "  nakładka:")
    return [w.strip() for w in cli.opis_statusu(cli.zbierz_status(u, ot)).splitlines() if not w.startswith(pomin)]


def rutyny_profili(u: Uklad, teraz: float) -> list[str]:
    """Zadania cron Hermesa ze wszystkich profili (`<dane>/profiles/*/cron/jobs.json`)."""
    w = []
    for plik in sorted((u.dane / "profiles").glob("*/cron/jobs.json")):
        dane = _json(plik) or {}
        for j in (dane.get("jobs") if isinstance(dane, dict) else dane) or []:
            if not isinstance(j, dict):
                continue
            sched = j.get("schedule")
            harm = j.get("schedule_display") or (sched.get("expr") or sched.get("display")
                                                 if isinstance(sched, dict) else sched) or "?"
            wlaczona = bool(j.get("enabled")) and j.get("state") != "paused"
            czasy = ""
            if wlaczona:
                czasy = (f" · ostatnio {kiedy(_iso(j.get('last_run_at')), teraz)}"
                         + (f" ({j['last_status']})" if j.get("last_status") else "")
                         + f" · następnie {kiedy(_iso(j.get('next_run_at')), teraz)}")
            w.append(f"{plik.parts[-3]}: {j.get('name') or j.get('id')} · {harm} · "
                     f"{'włączona' if wlaczona else 'wstrzymana'}{czasy}")
    return w


def zegary_systemu(wolaj_: Wolaj, teraz: float) -> list[str]:
    """Zegary użytkownika z systemd (`~/.config/systemd/user`): opis jednostki, ostatni i następny bieg."""
    try:
        lista = json.loads(wolaj_(["systemctl", "--user", "list-timers", "--all", "--no-pager", "--output=json"]) or "[]")
    except ValueError:
        return []
    czasy = {x.get("unit"): x for x in lista if isinstance(x, dict) and x.get("unit")}
    if not czasy:
        return []
    opisy = _wlasciwosci(wolaj_, list(czasy), ("Description", "FragmentPath"))
    wlasne = str(Path.home() / ".config" / "systemd" / "user")
    w = []
    for nazwa, x in czasy.items():
        o = opisy.get(nazwa, {})
        if not o.get("FragmentPath", "").startswith(wlasne):
            continue
        w.append(f"{nazwa} · {o.get('Description') or x.get('activates') or ''} · ostatnio "
                 f"{kiedy((x.get('last') or 0) / 1e6, teraz)} · następnie {kiedy((x.get('next') or 0) / 1e6, teraz)}")
    return w


def _wlasciwosci(wolaj_: Wolaj, jednostki: list[str], pola: tuple[str, ...]) -> dict[str, dict]:
    """`systemctl --user show` dla wielu jednostek naraz: {jednostka: {pole: wartość}}."""
    if not jednostki:
        return {}
    arg = ["systemctl", "--user", "show", *jednostki, "-p", "Id"]
    for p in pola:
        arg += ["-p", p]
    out: dict[str, dict] = {}
    for blok in wolaj_(arg).split("\n\n"):
        pary = dict(linia.split("=", 1) for linia in blok.splitlines() if "=" in linia)
        if pary.get("Id"):
            out[pary["Id"]] = pary
    return out


def czesc_rutyny(u: Uklad, _ot, wolaj_: Wolaj, teraz: float) -> list[str]:
    w = ["rutyny agentów (cron Hermesa, działają z serwisem):"] + [f"  {x}" for x in rutyny_profili(u, teraz)]
    zegary = zegary_systemu(wolaj_, teraz)
    if zegary:
        w += ["zegary systemu (systemd --user):"] + [f"  {x}" for x in zegary]
    cron = [x for x in wolaj_(["crontab", "-l"]).splitlines() if x.strip() and not x.lstrip().startswith("#")]
    w.append("crontab użytkownika: " + ("; ".join(cron) if cron else "pusty"))
    return w


def czesc_wiedza(u: Uklad, ot, _wolaj: Wolaj, _teraz: float) -> list[str]:
    from . import wiedza_cli
    bufor = io.StringIO()
    with contextlib.redirect_stdout(bufor), contextlib.redirect_stderr(bufor):
        kod = wiedza_cli.polecenie_wiedza_status(u, SimpleNamespace(json=False), [], ot)
    w = [x.strip() for x in bufor.getvalue().splitlines() if x.strip()]
    if kod:
        return w                            # brak skarbca: zostaje jego komunikat
    lib = wiedza_cli.wiedza_lib(wiedza_cli._app(u))
    noc = "%02d:%02d" % tuple(lib.KOMPILACJA_NOC)
    w.append(f"szkic staje się notatką przy kompilacji: gdy najnowszy szkic ma {lib.SZKIC_SPOKOJ_S // 60} min albo "
             f"najstarszy {lib.SZKIC_NAJSTARSZY_S // 60} min, a pełny przebieg nocny jest o {noc}")
    return w


def czesc_flota(u: Uklad, _ot, _wolaj: Wolaj, _teraz: float) -> list[str]:
    w = []
    modele: dict[str, list[str]] = {}
    for p in sorted((u.dane / "profiles").glob("*/config.yaml")):
        modele.setdefault(_z_yaml(p, "model", "default") or "?", []).append(p.parent.name)
    for model, agenci in modele.items():
        w.append(f"agenci ({len(agenci)}) na {model}: {', '.join(agenci)}")
    sesje = _json(u.jarvo_dane / "konfig" / "sesje.json") or {}
    if isinstance(sesje, dict) and sesje:
        w.append("sesje omp (osobne programy, rozmówcy w panelu): " + ", ".join(
            f"{k} = {v.get('nazwa') or k}" + (f" ({o})" if (o := (v.get("panel") or {}).get("opis")) else "")
            for k, v in sesje.items() if isinstance(v, dict)))
    ile = {k: _z_yaml(u.dane / "config.yaml", "kanban", k) for k in ("max_in_progress", "max_in_progress_per_profile")}
    dzieci = _z_yaml(u.dane / "profiles" / "jarvo" / "config.yaml", "delegation", "max_concurrent_children")
    limity = [f"zadań naraz najwyżej {ile['max_in_progress']}" if ile["max_in_progress"] else "",
              f"na jednego agenta {ile['max_in_progress_per_profile']}" if ile["max_in_progress_per_profile"] else "",
              f"podagentów Jarva naraz {dzieci}" if dzieci else ""]
    if any(limity):
        w.append("limity: " + ", ".join(x for x in limity if x))
    w += _zadania(u.dane / "kanban.db")
    return w


def _zadania(baza: Path) -> list[str]:
    if not baza.is_file():
        return ["lista zadań: brak bazy"]
    try:
        c = sqlite3.connect(f"file:{baza}?mode=ro", uri=True, timeout=2)
        try:
            liczby = dict(c.execute("select status, count(*) from tasks group by status").fetchall())
            znaki = ",".join("?" * len(STANY_OTWARTE))
            otwarte = c.execute(f"select id, status, assignee, title from tasks where status in ({znaki}) "
                                "order by case status when 'running' then 0 else 1 end, created_at desc limit ?",
                                (*STANY_OTWARTE, NAJWYZEJ_ZADAN)).fetchall()
        finally:
            c.close()
    except sqlite3.Error as e:
        return [f"lista zadań: nie udało się odczytać ({e})"]
    w = ["lista zadań: " + (", ".join(f"{NAZWY_STANOW.get(s, s)} {n}" for s, n in liczby.items() if s in STANY_OTWARTE)
                            or "nic otwartego") + f", zakończone {liczby.get('done', 0)}"]
    w += [f"  {i} · {NAZWY_STANOW.get(s, s)} · {a or 'bez agenta'} · {' '.join(str(t or '').split())[:90]}"
          for i, s, a, t in otwarte]
    return w


def czesc_sprzet(u: Uklad, _ot, wolaj_: Wolaj, _teraz: float) -> list[str]:
    def plik(p: str) -> str:
        try:
            return Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    w = []
    model = re.search(r"model name\s*:\s*(.+)", plik("/proc/cpuinfo"))
    nazwa = plik("/sys/class/dmi/id/product_name").strip()
    w.append(" · ".join(x for x in (nazwa, model.group(1).strip() if model else "", f"wątki CPU: {os.cpu_count()}") if x))
    mem = dict(re.findall(r"(\w+):\s+(\d+) kB", plik("/proc/meminfo")))
    if mem.get("MemTotal"):
        w.append(f"RAM {int(mem['MemTotal']) / 1048576:.0f} GB, wolne {int(mem.get('MemAvailable', 0)) / 1048576:.0f} GB")
    with contextlib.suppress(OSError):
        d = shutil.disk_usage(u.dane)
        w.append(f"dysk z danymi: wolne {d.free / 2**30:.0f} GB z {d.total / 2**30:.0f} GB")
    with contextlib.suppress(OSError, AttributeError):
        l1, l5, l15 = os.getloadavg()
        w.append(f"obciążenie (1, 5, 15 min): {l1:.1f}, {l5:.1f}, {l15:.1f} przy {os.cpu_count()} wątkach, "
                 f"czyli teraz ok. {100 * l1 / (os.cpu_count() or 1):.0f}% CPU")
    kwota = _wlasciwosci(wolaj_, ["jarvo.service"], ("CPUQuotaPerSecUSec",)).get("jarvo.service", {})
    m = re.fullmatch(r"([\d.]+)(ms|s)", kwota.get("CPUQuotaPerSecUSec", ""))
    if m:
        proc = float(m.group(1)) * (100 if m.group(2) == "s" else 0.1)
        w.append(f"limit CPU serwisu Jarva (systemd CPUQuota): {proc:.0f}%, czyli {proc / 100:.1f} z {os.cpu_count()} wątków")
    if any(Path("/dev/dri").glob("renderD*")):
        w.append("układ graficzny: jest węzeł /dev/dri (kodowanie wideo sprzętowo)")
    return w


def czesc_porty(_u: Uklad, _ot, wolaj_: Wolaj, _teraz: float) -> list[str]:
    """Kto słucha na TCP: port, zasięg, program, usługa systemd z opisem i katalog roboczy (bez wiersza poleceń:
    bywają w nim sekrety)."""
    porty: dict[int, dict] = {}
    for linia in wolaj_(["ss", "-ltnpH"]).splitlines():
        pola = linia.split()
        if len(pola) < 4 or ":" not in pola[3]:
            continue
        adres, _, port = pola[3].rpartition(":")
        m = re.search(r'\(\("([^"]+)",pid=(\d+)', linia)
        if not port.isdigit():
            continue
        x = porty.setdefault(int(port), {"lokalny": True, "program": "", "pid": 0})
        x["lokalny"] = x["lokalny"] and adres.strip("[]") in ("127.0.0.1", "::1", "127.0.0.53", "127.0.0.54")
        if m:
            x["program"], x["pid"] = m.group(1), int(m.group(2))
    for x in porty.values():
        x["usluga"], x["katalog"] = "", ""
        if x["pid"]:
            with contextlib.suppress(OSError):
                cg = Path(f"/proc/{x['pid']}/cgroup").read_text(encoding="utf-8")
                uslugi = re.findall(r"([^/\n]+\.service)", cg)
                x["usluga"] = uslugi[-1] if uslugi else ""
            with contextlib.suppress(OSError):
                x["katalog"] = os.readlink(f"/proc/{x['pid']}/cwd")
    opisy = _wlasciwosci(wolaj_, sorted({x["usluga"] for x in porty.values() if x["usluga"]}), ("Description",))
    dom = str(Path.home())
    grupy: dict[tuple, list[str]] = {}      # porty tego samego programu, usługi i zasięgu w jednej linii
    for port, x in sorted(porty.items()):
        if not x["pid"]:
            continue                        # proces innego użytkownika (system): nie nasz
        opis = opisy.get(x["usluga"], {}).get("Description", "")
        grupy.setdefault((
            "tylko ten komputer" if x["lokalny"] else "w sieci", x["program"],
            x["usluga"] + (f" ({opis})" if opis else "") if x["usluga"] else "",
            x["katalog"].replace(dom, "~") if x["katalog"] not in ("", "/") else ""), []).append(str(port))
    w = [" · ".join(k for k in (", ".join(numery), *reszta) if k) for reszta, numery in grupy.items()]
    return w or ["nie udało się odczytać portów (brak `ss`)"]


def katalog_polecen(u: Uklad) -> Path:
    return u.jarvo_dane / "polecenia"


def czesc_polecenia(u: Uklad, _ot, _wolaj: Wolaj, _teraz: float) -> list[str]:
    """Własne polecenia agenta: pliki w `<dane>/jarvo/polecenia`, opis to pierwszy komentarz po `#!`."""
    kat = katalog_polecen(u)
    w = []
    for p in sorted(kat.iterdir()) if kat.is_dir() else []:
        if not p.is_file() or p.name.startswith((".", "_")):
            continue
        opis = ""
        with contextlib.suppress(OSError):
            for linia in p.read_text(encoding="utf-8", errors="replace").splitlines()[:8]:
                m = re.match(r"\s*(?:#(?!!)|\"\"\"|//)\s*(.+?)(?:\"\"\")?\s*$", linia)
                if m and m.group(1).strip():
                    opis = m.group(1).strip()
                    break
        w.append(f"{p} · {opis or 'bez opisu (pierwszy komentarz pliku)'}")
    return w or [f"brak; skrypt zapisany w {kat} z opisem w pierwszym komentarzu pojawi się tutaj"]


CZESCI: dict[str, tuple[str, Callable]] = {
    "serwis": ("serwis i panel", czesc_serwis),
    "rutyny": ("co działa samo i kiedy", czesc_rutyny),
    "wiedza": ("skarbiec wiedzy", czesc_wiedza),
    "flota": ("flota i lista zadań", czesc_flota),
    "sprzet": ("sprzęt", czesc_sprzet),
    "porty": ("porty i kto na nich słucha", czesc_porty),
    "polecenia": ("własne polecenia", czesc_polecenia),
}


def raport(u: Uklad, ot, tematy: tuple[str, ...] = (), *, wolaj_: Wolaj = wolaj, teraz: float | None = None) -> str:
    teraz = time.time() if teraz is None else teraz
    t = time.localtime(teraz)
    w = [f"Jarvo stan · {DNI[t.tm_wday]} {time.strftime('%Y-%m-%d %H:%M %Z', t)}"]
    for temat in tematy or TEMATY:
        tytul, funkcja = CZESCI[temat]
        w.append(f"\n## {temat}: {tytul}")
        try:
            w += funkcja(u, ot, wolaj_, teraz) or ["(pusto)"]
        except Exception as e:  # noqa: BLE001  (jedna część nie zabiera reszty)
            w.append(f"(nie udało się odczytać: {type(e).__name__}: {e})")
    return "\n".join(w)


def polecenie_stan(u: Uklad, a, _reszta, ot) -> int:
    zle = [x for x in a.tematy if x not in TEMATY]
    if zle:
        print(f"Nie znam tematu {', '.join(zle)}. Są: {', '.join(TEMATY)}.", file=sys.stderr)
        return 2
    print(raport(u, ot, tuple(a.tematy)))
    return 0


def dodaj_polecenia(sub) -> None:
    s = sub.add_parser("stan", help="stan instalacji jednym poleceniem (tylko odczyt): godzina, serwis i panel, rutyny "
                       "i zegary, wiedza, flota i zadania, sprzęt, porty, własne polecenia",
                       description="Bez tematu cały stan; z tematami tylko wybrane części: " + ", ".join(TEMATY) + ".")
    s.add_argument("tematy", nargs="*", metavar="temat", help="części do pokazania: " + ", ".join(TEMATY))
    s.set_defaults(funkcja=polecenie_stan)
