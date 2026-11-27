"""Mapa Jarva („Jarvo od A do Z”): jedno źródło, dwie postacie (docs/WIEDZA.md §2b). Biblioteka standardowa.

Źródło: `profiles/jarvo/MAPA.md` z repo (mechanizmy, publiczne) i ten sam plik z nakładki prywatnej (dane właściciela),
oba po podstawieniu tokenów @@…@@ (scripts/build.py), plus bloki GENEROWANE z danych floty, żeby nie starzały się:
`agenci`, `skille`, `arsenal`, `sciezki`, `harmonogram`. Sekcje `## ` w stałej kolejności SEKCJE; ta sama sekcja
w nakładce dokleja się pod tekstem z repo. W sekcji:
  - `<!-- Jarvo:RDZEN -->…<!-- /Jarvo:RDZEN -->`: gęste linie, które idą do RDZENIA w prompcie Jarva;
  - `<!-- Jarvo:GEN <nazwa> -->` (para znaczników, pusta): miejsce bloku generowanego.
Postacie:
  - rdzen(): zwarta mapa w stałej części promptu (ZASADY.md, znacznik `<!-- Jarvo:MAPA -->`, podstawia build): bloki
    RDZEN i zwarte GEN `sciezki` i `harmonogram`, bez dat i liczników (stabilny prefiks, cache dostawcy). Zespół rdzenia
    to roster z SOUL (fleetlib.render_roster_summary), więc rdzeń go nie powtarza;
  - notatka(): notatka `jarvo/jak działa jarvo` w skarbcu (zasiew): wszystko, z pełnymi blokami GEN i datą źródła.
Funkcje rdzen(), notatka() i render_*() są czyste (bez wejścia-wyjścia); zadania_cron_profili(), timery_systemd()
i watki_telegrama() czytają stan maszyny dla zasiewu.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

SEKCJE = ("Kim jestem", "Dla kogo pracuję i po co", "Biznesy", "Co robię na co dzień", "Co mogę", "Czego nie robię bez zgody",
          "Zespół", "Gdzie co jest", "Kiedy", "Jak działa mój mózg", "Jak się poprawiam", "Słownik")
TYTUL = "Jarvo od A do Z"
# blok GEN bez znacznika w pliku idzie na koniec swojej sekcji
SEKCJA_GEN = {"agenci": "Zespół", "skille": "Zespół", "arsenal": "Co mogę", "sciezki": "Gdzie co jest", "harmonogram": "Kiedy"}
GEN_W_RDZENIU = ("sciezki", "harmonogram")          # agenci = roster SOUL; skille i arsenał i tak są w prompcie
ZNAKOW_NA_TOKEN = 3.5
RDZEN_RE = re.compile(r"<!-- Jarvo:RDZEN -->\n?(.*?)\n?<!-- /Jarvo:RDZEN -->", re.S)
GEN_PUSTY_RE = re.compile(r"<!-- Jarvo:GEN (\w+) -->.*?<!-- /Jarvo:GEN \1 -->", re.S)
DNI = ("niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela")


def tokeny(tekst: str) -> int:
    return int(len(tekst) / ZNAKOW_NA_TOKEN)


def sekcje(tekst: str | None) -> dict[str, str]:
    """Sekcje `## ` pliku MAPA.md w kolejności pliku: nazwa → treść (bez nagłówka). Tekst przed pierwszą sekcją odpada."""
    out: dict[str, str] = {}
    for m in re.finditer(r"^## (.+?)[ \t]*\n(.*?)(?=^## |\Z)", tekst or "", re.M | re.S):
        nazwa = m.group(1).strip()
        out[nazwa] = (out[nazwa] + "\n\n" if nazwa in out else "") + m.group(2).strip("\n")
    return out


def zloz(mapa_repo: str, mapa_nakladka: str | None) -> list[tuple[str, str]]:
    """[(sekcja, treść)]: SEKCJE w stałej kolejności (repo, pod nim nakładka), potem sekcje spoza listy w kolejności plików."""
    repo, nakl = sekcje(mapa_repo), sekcje(mapa_nakladka)
    kolejnosc = [*SEKCJE, *(n for n in [*repo, *nakl] if n not in SEKCJE)]
    out = []
    for nazwa in dict.fromkeys(kolejnosc):
        czesci = [t.strip() for t in (repo.get(nazwa, ""), nakl.get(nazwa, "")) if t.strip()]
        if czesci:
            out.append((nazwa, "\n\n".join(czesci)))
    return out


# ------------------------------------------------------------------------------------------------ czas po polsku

def _godzina(minuta: str, godzina: str) -> str:
    return f"{int(godzina):02d}:{int(minuta):02d}"


def _dni_tygodnia(pole: str) -> str:
    """Pole dnia tygodnia crona po polsku: `0` niedziela, `1-5` od poniedziałku do piątku, `1,3` poniedziałek i środa."""
    if re.fullmatch(r"\d", pole):
        return DNI[int(pole)]
    if (m := re.fullmatch(r"(\d)-(\d)", pole)):
        return f"od {_dopelniacz(DNI[int(m.group(1))])} do {_dopelniacz(DNI[int(m.group(2))])}"
    if re.fullmatch(r"\d(,\d)+", pole):
        dni = [DNI[int(x)] for x in pole.split(",")]
        return ", ".join(dni[:-1]) + " i " + dni[-1]
    return ""


def _dopelniacz(dzien: str) -> str:
    return {"poniedziałek": "poniedziałku", "wtorek": "wtorku", "środa": "środy", "czwartek": "czwartku", "piątek": "piątku",
            "sobota": "soboty", "niedziela": "niedzieli"}.get(dzien, dzien)


def czas_po_polsku(kiedy: str) -> str:
    """Harmonogram zadania Hermesa po polsku: „every 30m” → „co 30 min”, „50 7 * * *” → „codziennie 07:50”,
    „50 18 * * 0” → „niedziela 18:50”, „40 8 * * 1-6” → „od poniedziałku do soboty 08:40”, „20 9 1 * *” → „1. dnia
    miesiąca 09:20”. Inny zapis zostaje dosłownie (w `…`)."""
    k = " ".join(str(kiedy or "").split())
    if (m := re.fullmatch(r"(?:every )?(\d+)\s*(m|min|minutes?|h|hours?|d|days?)", k, re.I)):
        n, j = int(m.group(1)), m.group(2)[0].lower()
        if j == "d":
            return "codziennie" if n == 1 else f"co {n} dni"
        return f"co {n} " + ("min" if j == "m" else "h")
    pola = k.split(" ")
    if len(pola) == 5 and pola[0].isdigit() and pola[1].isdigit():
        godz, (dzien_m, miesiac, dzien_t) = _godzina(pola[0], pola[1]), pola[2:]
        if dzien_m == "*" and miesiac == "*":
            if dzien_t == "*":
                return f"codziennie {godz}"
            if (dni := _dni_tygodnia(dzien_t)):
                return f"{dni} {godz}"
        if dzien_m.isdigit() and miesiac == "*" and dzien_t == "*":
            return f"{int(dzien_m)}. dnia miesiąca {godz}"
    return f"`{k}`"


def _klucz_czasu(kiedy: str) -> tuple:
    """Kolejność w harmonogramie: zadania co N minut najpierw, potem po godzinie dnia."""
    pola = str(kiedy or "").split()
    if len(pola) == 5 and pola[0].isdigit() and pola[1].isdigit():
        return (1, int(pola[1]) * 60 + int(pola[0]))
    return (0, 0)


# ------------------------------------------------------------------------------------------------ bloki GEN

def render_harmonogram(cron: list[dict], timery: list[dict] | None = None, watki: dict | None = None, zwarty: bool = False) -> str:
    """Zadania cron (nazwa, kiedy, agent, wlaczona, dostarczanie) i timery systemd usera (opis, kiedy, usługa).
    Zwarty (rdzeń): tylko włączone zadania, linia „czas: nazwa (agent)”. Pełny: także wstrzymane, dostarczanie po
    nazwie wątku Telegrama (`watki`: numer wątku → nazwa) i timery."""
    linie = []
    for z in sorted(cron, key=lambda z: (_klucz_czasu(z.get("kiedy", "")), str(z.get("nazwa") or ""))):
        if zwarty and not z.get("wlaczona", True):
            continue
        linia = f"- {czas_po_polsku(z.get('kiedy', ''))}: {z.get('nazwa') or z.get('id') or '?'}"
        agent = str(z.get("agent") or "")
        if zwarty:
            linie.append(linia + (f" ({agent})" if agent and agent != "jarvo" else ""))
            continue
        dodatki = [f"`{agent}`"] if agent else []
        if not z.get("wlaczona", True):
            dodatki.append("wstrzymana")
        if (gdzie := _dostarczanie(str(z.get("dostarczanie") or ""), watki or {})):
            dodatki.append(gdzie)
        linie.append(linia + (f" ({', '.join(dodatki)})" if dodatki else ""))
    if timery and not zwarty:
        linie.append("- timery systemd usera (poza Hermesem):")
        for t in timery:
            opis = " · ".join(x for x in (t.get("opis"), t.get("usluga_opis")) if x)
            linie.append(f"  - `{t.get('nazwa')}` {t.get('kiedy') or ''}" + (f": {opis}" if opis else ""))
    return "\n".join(linie)


def _dostarczanie(deliver: str, watki: dict) -> str:
    """`telegram:<chat>:<wątek>,…` → „Telegram: <nazwa wątku>, …” (state/telegram-grupy.json); `local` → „panel”."""
    cele = []
    for c in (x.strip() for x in deliver.split(",") if x.strip()):
        czesci = c.split(":")
        if czesci[0] == "telegram":
            watek = czesci[2] if len(czesci) > 2 else ""
            nazwa = watki.get(watek) if watek else "rozmowa z właścicielem"
            if nazwa and nazwa not in cele:
                cele.append(nazwa)
        elif c == "local":
            cele.append("panel")
        else:
            cele.append(czesci[0])
    telegram = any(c.strip().startswith("telegram") for c in deliver.split(","))
    if not cele:
        return "Telegram" if telegram else ""                  # nieznany wątek: bez numeru, który nic nie mówi
    return ("Telegram: " if telegram else "") + ", ".join(cele)


def render_sciezki(sciezki: dict[str, str], zwarty: bool = False) -> str:
    """Ścieżki jako lista. Zwarte (rdzeń): baza raz, ścieżki pod nią względnie: „- dane Jarva `/…/jarvo`: skarbiec
    `knowledge/`, misje `missions/`”. Pełne: linia na ścieżkę."""
    if not zwarty:
        return "\n".join(f"- {etykieta}: `{p}`" for etykieta, p in sciezki.items())
    grupy: list[tuple[str, str, list[str]]] = []
    for etykieta, p in sciezki.items():
        p = p.rstrip("/")
        baza = next((g for g in grupy if p.startswith(g[1] + "/")), None)
        if baza:
            baza[2].append(f"{etykieta} `{p[len(baza[1]) + 1:]}/`")
        else:
            grupy.append((etykieta, p, []))
    return "\n".join(f"- {e} `{p}`" + (": " + ", ".join(pod) if pod else "") for e, p, pod in grupy)


def render_agenci(agenci: list[dict]) -> str:
    """Agenci z fleet.json (emoji, krótka nazwa, profil, uchwyt, rola): linia na agenta, link do huba w skarbcu."""
    linie = []
    for a in agenci:
        nazwa = a.get("short") or a.get("title") or a["name"]
        uchwyt = f", `@{a['handle']}`" if a.get("handle") else ""
        hub = a.get("hub")
        etykieta = f"[[{hub}|{nazwa}]]" if hub else nazwa
        opis = " ".join(str(a.get("description") or "").split())
        linie.append(f"- {a.get('emoji', '')} {etykieta} (`{a['name']}`{uchwyt}): {opis}".replace("-  ", "- "))
    return "\n".join(linie)


def render_skille(agenci: list[dict]) -> str:
    """Liczby i nazwy skilli agenta: własne, wspólne floty, zewnętrzne."""
    linie = []
    for a in agenci:
        wlasne = [s["name"] for s in a.get("skills") or []]
        wsp = [s["name"] for s in a.get("shared_skills") or []]
        zewn = list(a.get("external_skills") or [])
        razem = len(wlasne) + len(wsp) + len(zewn)
        czesci = [f"własne: {', '.join(f'`{n}`' for n in wlasne)}" if wlasne else "",
                  f"wspólne: {', '.join(f'`{n}`' for n in wsp)}" if wsp else "",
                  f"zewnętrzne: {', '.join(f'`{n}`' for n in zewn)}" if zewn else ""]
        linie.append(f"- {a.get('short') or a['name']} ({razem}): " + "; ".join(c for c in czesci if c))
    return "\n".join(linie)


def render_arsenal(arsenal: str) -> str:
    """Zasoby z `fleet/arsenal.md` (sekcja „## Zasoby”), dosłownie: jeden wpis na zasób."""
    m = re.search(r"^## Zasoby\s*\n(.*?)(?=^## |\Z)", arsenal or "", re.M | re.S)
    return "\n".join(l.rstrip() for l in (m.group(1) if m else "").splitlines() if l.startswith("- "))


# ------------------------------------------------------------------------------------------------ postacie mapy

def _wstaw_gen(nazwa_sekcji: str, tekst: str, gen: dict[str, str], zrodla: dict[str, str] | None) -> str:
    """Bloki GEN w treści sekcji: pusty znacznik wypełniony, a blok tej sekcji bez znacznika doklejony na końcu."""
    uzyte = set()

    def wypelnij(m: re.Match) -> str:
        nazwa = m.group(1)
        uzyte.add(nazwa)
        return _blok_gen(nazwa, gen.get(nazwa, ""), (zrodla or {}).get(nazwa, ""))

    tekst = GEN_PUSTY_RE.sub(wypelnij, tekst)
    for nazwa, sekcja in SEKCJA_GEN.items():
        if sekcja == nazwa_sekcji and nazwa not in uzyte and gen.get(nazwa):
            tekst = tekst.rstrip("\n") + "\n\n" + _blok_gen(nazwa, gen[nazwa], (zrodla or {}).get(nazwa, ""))
    return tekst


def _blok_gen(nazwa: str, tresc: str, zrodlo: str) -> str:
    naglowek = f"_Stan z {zrodlo}._\n" if zrodlo else ""
    return f"<!-- Jarvo:GEN {nazwa} -->\n{naglowek}{tresc.strip() or '_brak danych_'}\n<!-- /Jarvo:GEN {nazwa} -->"


def notatka(mapa_repo: str, mapa_nakladka: str | None, gen: dict[str, str], zrodla: dict[str, str] | None = None,
            tytul: str = TYTUL) -> str:
    """Treść notatki „od A do Z” agenta (bez frontmatteru; Jarvo: `jarvo/jak działa jarvo`): tytuł, streszczenie, sekcje
    `## ` w stałej kolejności (bloki RDZEN bez znaczników, bloki GEN wypełnione: `gen` nazwa → treść, `zrodla` nazwa →
    „źródło, data”)."""
    czesci = [f"# {tytul}\n",
              "**Jedno źródło prawdy o mnie: kim jestem, dla kogo i po co pracuję, co robię, co mogę, czego nie robię bez zgody, "
              "zespół, gdzie co jest, kiedy, jak działa mój mózg i jak się poprawiam. Skrót (rdzeń) mam w prompcie; tu "
              "szczegóły, sekcja po sekcji.**\n"]
    for nazwa, tekst in zloz(mapa_repo, mapa_nakladka):
        tekst = RDZEN_RE.sub(lambda m: m.group(1).strip("\n"), tekst)
        czesci.append(f"## {nazwa}\n{_wstaw_gen(nazwa, tekst, gen, zrodla).strip()}\n")
    return "\n".join(czesci)


def rdzen(mapa_repo: str, mapa_nakladka: str | None, cron: list[dict], sciezki: dict[str, str]) -> str:
    """Rdzeń mapy do promptu Jarva: dla każdej sekcji (kolejność SEKCJE), która ma bloki RDZEN albo zwarty GEN
    (`sciezki` w „Gdzie co jest”, `harmonogram` w „Kiedy”): `### <Sekcja>`, bloki RDZEN (repo, potem nakładka) i zwarty
    GEN. Bez dat i liczników (stały prefiks promptu). `cron`: [{"nazwa", "kiedy", "agent", "wlaczona", "dostarczanie"}],
    `sciezki`: {"etykieta": "ścieżka"} w kolejności. Pusty tekst, gdy nie ma czego wstawić."""
    gen = {"sciezki": render_sciezki(sciezki, zwarty=True) if sciezki else "",
           "harmonogram": render_harmonogram(cron, zwarty=True) if cron else ""}
    out = []
    for nazwa, tekst in zloz(mapa_repo, mapa_nakladka):
        linie = [m.group(1).strip() for m in RDZEN_RE.finditer(tekst) if m.group(1).strip()]
        linie += [gen[n] for n in GEN_W_RDZENIU if SEKCJA_GEN[n] == nazwa and gen.get(n)]
        if linie:
            out.append(f"### {nazwa}\n" + "\n".join(linie))
    return "\n\n".join(out)


# ------------------------------------------------------------------------------------------------ stan maszyny (zasiew)

def zadania_cron_profili(profile: Path) -> list[dict]:
    """Zadania cron Hermesa wszystkich profili (`<profile>/<agent>/cron/jobs.json`), także wstrzymane."""
    out = []
    for plik in sorted(Path(profile).glob("*/cron/jobs.json")):
        try:
            dane = json.loads(plik.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for z in (dane.get("jobs") if isinstance(dane, dict) else dane) or []:
            if not isinstance(z, dict):
                continue
            h = z.get("schedule")
            kiedy = (h.get("expr") or h.get("display") or "") if isinstance(h, dict) else str(h or "")
            if isinstance(h, dict) and h.get("kind") == "interval" and h.get("minutes"):
                kiedy = f"every {h['minutes']}m"
            out.append({"nazwa": str(z.get("name") or z.get("id") or ""), "kiedy": kiedy, "agent": plik.parent.parent.name,
                        "wlaczona": bool(z.get("enabled", True)) and z.get("state") != "paused",
                        "dostarczanie": str(z.get("deliver") or "")})
    return out


WATEK_OGOLNY = ("1", "JARVO")      # temat General grupy Jarvo HQ (jarvo/wiedza_cli.py NAZWA_OGOLNEGO, WATEK_OGOLNY)


def watki_telegrama(plik: Path, srodowisko: dict | None = None) -> dict[str, str]:
    """Numer wątku → nazwa tematu jak w `jarvo telegram status`: 1 = JARVO (General), zmienne TELEGRAM_TOPIC_<KLUCZ>
    środowiska (bramy, instalatora) = KLUCZ, a poza nimi tematy z state/telegram-grupy.json (nazwa wielkimi). Plików
    .env nie czytamy; nieznany wątek nie dostaje nazwy (render pisze wtedy samo „Telegram”)."""
    out: dict[str, str] = {}
    try:
        dane = json.loads(Path(plik).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dane = {}
    for g in (dane.get("grupy") or {}).values() if isinstance(dane, dict) else []:
        for numer, w in (g.get("watki") or {}).items() if isinstance(g, dict) else []:
            if isinstance(w, dict) and w.get("nazwa"):
                out[str(numer)] = str(w["nazwa"]).upper()
    env = os.environ if srodowisko is None else srodowisko
    for klucz, wartosc in env.items():
        if klucz.startswith("TELEGRAM_TOPIC_") and str(wartosc).strip().isdigit():
            out[str(wartosc).strip()] = klucz.removeprefix("TELEGRAM_TOPIC_")
    out[WATEK_OGOLNY[0]] = WATEK_OGOLNY[1]
    return out


def timery_systemd(katalog_user: Path | None = None) -> list[dict]:
    """Timery usera z plikiem w ~/.config/systemd/user (bez systemowych z /usr/lib): nazwa, kiedy (OnCalendar albo
    OnUnitActiveSec po polsku), opis timera i usługi. Bez systemctl (macOS, Windows, kontener) pusta lista."""
    systemctl = shutil.which("systemctl")
    katalog = Path(katalog_user or Path.home() / ".config" / "systemd" / "user")
    if not systemctl or not katalog.is_dir():
        return []
    out = []
    for plik in sorted(katalog.glob("*.timer")):
        try:
            r = subprocess.run([systemctl, "--user", "show", plik.name, "-p", "Description", "-p", "FragmentPath",
                                "-p", "TimersCalendar", "-p", "TimersMonotonic", "-p", "Unit"],
                               capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        pola: dict[str, str] = {}
        for linia in r.stdout.splitlines():                     # TimersMonotonic bywa w kilku liniach (OnBoot, OnUnitActive)
            k, _, v = linia.partition("=")
            pola[k] = (pola[k] + " ; " + v) if k in pola else v
        if not str(pola.get("FragmentPath") or "").startswith(str(katalog)):
            continue
        kiedy = ""
        if (m := re.search(r"OnCalendar=([^;]+)", pola.get("TimersCalendar", ""))):
            kiedy = _kalendarz_po_polsku(m.group(1).strip())
        elif (m := re.search(r"OnUnitActiveUSec=([^;]+)", pola.get("TimersMonotonic", ""))):
            kiedy = "co " + re.sub(r"(\d+)\s*(min|h|s|d)\b", r"\1 \2", m.group(1).strip())
        usluga_opis = ""
        if pola.get("Unit"):
            try:
                u = subprocess.run([systemctl, "--user", "show", pola["Unit"], "-p", "Description"], capture_output=True,
                                   text=True, timeout=5)
                usluga_opis = u.stdout.strip().partition("=")[2]
            except (OSError, subprocess.SubprocessError):
                pass
        opis = pola.get("Description", "")
        out.append({"nazwa": plik.stem, "kiedy": kiedy, "opis": opis,
                    "usluga_opis": usluga_opis if usluga_opis and usluga_opis != opis else ""})
    return out


def _kalendarz_po_polsku(spec: str) -> str:
    """OnCalendar systemd (znormalizowany przez systemctl, np. `*-*-* 06:30:00`) po polsku."""
    if (m := re.fullmatch(r"\*-\*-\* (\d\d):(\d\d):00", spec)):
        return f"codziennie {m.group(1)}:{m.group(2)}"
    if (m := re.fullmatch(r"\*-\*-\* \*:(\d\d):00", spec)):
        return f"co godzinę o :{m.group(1)}"
    if (m := re.fullmatch(r"\*-\*-\* \*:00/(\d+):00", spec)) or (m := re.fullmatch(r"\*-\*-\* \*:0/(\d+):00", spec)):
        return f"co {int(m.group(1))} min"
    return f"`{spec}`"
