#!/usr/bin/env python3
"""Wiadomość do skrzynki sesji zewnętrznej (domyślnie Kernel) ręcznie, gdy brama jej nie oddała, bez modelu.

    python3 wrzuc_do_kernel.py [--sesja <klucz>] <id wiadomości>:<tekst> [<id>:<tekst> ...]

Sesje i ich skrzynki opisuje `<dane>/jarvo/konfig/sesje.json` (sesje/plugin, hq/plugin/omp_sesje.py): klucz to
dopisek („… gpu”), wpis ma `nazwa`, `skrzynka` i opcjonalnie `czat` i `watek` (gdzie sesja odpowiada). Bez `--sesja`
skrypt bierze wpis o nazwie „Kernel”. Plik trafia do `<skrzynka>/nowe/` w tym samym kształcie, jaki zapisuje
wtyczka `jarvo-sesje` dla wiadomości z Telegrama (`<RRRRMMDD-HHMMSS>-<id>.json`, zapis atomowy), więc odpowiedź
idzie tam, gdzie poszłaby po zwykłym dopisku; skrzynkę budzi jej jednostka `.path` (patrzy na `nowe/`).

Ta sama wiadomość (id) drugi raz nie wchodzi: jest już w `nowe/`, `zrobione/` albo `bledy/`. Skąd: 14.11 brama po
aktualizacji nie oddała sześciu wiadomości „… gpu” Kernelowi; 15.11 to też droga poleceń Jarva do wiki Kernela.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sciezki  # noqa: E402  (katalogi z HERMES_HOME, nie z /opt)

DOMYSLNA_NAZWA = "Kernel"
ID_RE = re.compile(r"[0-9A-Za-z_-]{1,64}")


class Blad(Exception):
    pass


def plik_sesji() -> Path:
    return _sciezki.jarvo() / "konfig" / "sesje.json"


def wpis(konfig: Path, klucz: str | None) -> tuple[str, dict]:
    """(klucz, wpis) sesji ze skrzynką: podany klucz albo jedyny wpis o nazwie „Kernel”."""
    try:
        wpisy = json.loads(konfig.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Blad(f"nie czytam {konfig}: {e}") from None
    if not isinstance(wpisy, dict):
        raise Blad(f"{konfig}: to nie jest słownik sesji")
    if klucz:
        trafione = [(k, v) for k, v in wpisy.items() if str(k).lower() == klucz.lower()]
    else:
        trafione = [(k, v) for k, v in wpisy.items()
                    if isinstance(v, dict) and str(v.get("nazwa") or "").lower() == DOMYSLNA_NAZWA.lower()]
    if len(trafione) != 1:
        jakie = ", ".join(sorted(str(k) for k, v in wpisy.items() if isinstance(v, dict) and v.get("skrzynka")))
        kogo = f"sesji „{klucz}”" if klucz else f"jednej sesji o nazwie „{DOMYSLNA_NAZWA}”"
        raise Blad(f"nie ma {kogo} w {konfig} (sesje ze skrzynką: {jakie or 'brak'})")
    k, v = trafione[0]
    if not isinstance(v, dict) or not str(v.get("skrzynka") or "").strip():
        raise Blad(f"sesja „{k}” nie ma skrzynki (wpis z `profil` to agent floty, nie sesja)")
    return str(k), v


def skrzynka(v: dict) -> Path:
    p = Path(os.path.expanduser(str(v["skrzynka"])))
    if not p.is_absolute():
        raise Blad(f"skrzynka musi być ścieżką bezwzględną: {v['skrzynka']}")
    return p


def wiadomosci(argumenty: list[str]) -> list[tuple[str, str]]:
    wynik = []
    for a in argumenty:
        mid, dwukropek, tekst = a.partition(":")
        if not dwukropek or not ID_RE.fullmatch(mid) or not tekst.strip():
            raise Blad(f"zły argument „{a}”: oczekuję <id wiadomości>:<tekst>")
        wynik.append((mid, tekst.strip()))
    return wynik


def juz_jest(kat: Path, mid: str) -> bool:
    return any(next((kat / d).glob(f"*-{mid}.json"), None) for d in ("nowe", "zrobione", "bledy") if (kat / d).is_dir())


def wrzuc(klucz: str, v: dict, lista: list[tuple[str, str]], teraz: float | None = None) -> list[tuple[str, str]]:
    """Zapisuje wiadomości do `<skrzynka>/nowe/`; zwraca [(id, „zapisane …” albo „już jest”)]."""
    kat = skrzynka(v)
    nowe = kat / "nowe"
    nowe.mkdir(parents=True, exist_ok=True)
    baza = time.time() if teraz is None else teraz
    wynik = []
    for i, (mid, tekst) in enumerate(lista):
        if juz_jest(kat, mid):
            wynik.append((mid, "już jest"))
            continue
        czas = time.localtime(baza + i)                  # kolejność w skrzynce = kolejność argumentów
        rdzen = time.strftime("%Y%m%d-%H%M%S", czas) + "-" + mid
        dane = {"dopisek": klucz, "nazwa": str(v.get("nazwa") or klucz), "tekst": tekst, "odpowiedz_na": "",
                "media": [], "czas": time.strftime("%Y-%m-%d %H:%M:%S", czas), "chat_id": str(v.get("czat") or ""),
                "message_id": mid, "watek": str(v.get("watek") or ""), "zrodlo_chat_id": "", "zrodlo_watek": "",
                "zrodlo": "reczne"}
        tmp = nowe / f".{rdzen}.json.tmp"
        tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(nowe / f"{rdzen}.json")
        wynik.append((mid, f"zapisane {rdzen}.json"))
    return wynik


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sesja", help=f"klucz wpisu w sesje.json (domyślnie wpis o nazwie „{DOMYSLNA_NAZWA}”)")
    ap.add_argument("wiadomosci", nargs="+", metavar="ID:TEKST")
    a = ap.parse_args(argv)
    try:
        klucz, v = wpis(plik_sesji(), a.sesja)
        for mid, co in wrzuc(klucz, v, wiadomosci(a.wiadomosci)):
            print(f"{v.get('nazwa') or klucz} · {mid}: {co}")
    except Blad as e:
        print(f"błąd: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
