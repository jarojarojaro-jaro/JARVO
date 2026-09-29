#!/usr/bin/env python3
"""Jedyne wejście agenta Ads do kont reklamowych: rozmawia ze Skarbcem (osobny kontener z tokenami i polityką).

Agent nie ma tokenów Meta ani Google. Skarbiec wymusza: szkice tylko PAUSED, start i zwiększenie wydatku tylko w kopercie
zatwierdzonej kodem, który użytkownik dostaje od Skarbca (Telegram / inny podłączony komunikator / panel HQ).

  ads.py doctor                              # czy Skarbiec działa, jakie konta i uprawnienia
  ads.py konta                               # konta reklamowe z polityki (Meta, Google), waluta, limit miesięczny
  ads.py kampanie [--konto ID]               # kampanie, zestawy/grupy, reklamy ze stanem i budżetem
  ads.py statystyki --konto ID [--od RRRR-MM-DD --do RRRR-MM-DD] [--poziom reklama|zestaw|kampania] [--json]
  ads.py szkic plan.json                     # buduje kampanię jako PAUSED (0 zł), zwraca ID i linki podglądu
  ads.py koperta zglos koperta.json          # prośba o zgodę: Skarbiec sam wysyła użytkownikowi opis i kod
  ads.py koperta zatwierdz ID --kod 123456   # kod wpisany przez użytkownika (nigdy zgadywany)
  ads.py koperta stan [ID]                   # koperty: czeka / aktywna / zakończona, wydane / zatwierdzone
  ads.py pauza OBIEKT                        # zawsze dozwolone
  ads.py budzet OBIEKT KWOTA                 # w obrębie koperty; ponad kopertę Skarbiec odmawia
  ads.py stop [--powod TEKST]                # pauzuje wszystko, co prowadzi Skarbiec
  ads.py dziennik [--ile 20]                 # kto, co, kiedy, z jaką zgodą

Adres: SKARBIEC_URL (domyślnie http://jarvo-skarbiec:8710). Kod wyjścia: 0 ok, 1 odmowa Skarbca, 2 złe wejście,
3 Skarbiec niepodłączony (pracuj na eksportach: eksport.py; podłączenie: skill podlacz-konto).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

URL = os.environ.get("SKARBIEC_URL", "http://jarvo-skarbiec:8710").rstrip("/")
NIEPODLACZONY = ("Skarbiec niepodłączony ({err}). Konta reklamowe nie są jeszcze podpięte: pracuj na eksporcie CSV "
                 "(`eksport.py`), a użytkownikowi zaproponuj podłączenie (skill `podlacz-konto`).")


class Odmowa(Exception):
    pass


def wolaj(metoda: str, sciezka: str, dane: dict | None = None, **query) -> dict:
    q = {k: v for k, v in query.items() if v is not None}
    url = URL + sciezka + ("?" + urllib.parse.urlencode(q) if q else "")
    body = json.dumps(dane).encode() if dane is not None else None
    req = urllib.request.Request(url, data=body, method=metoda, headers={"Content-Type": "application/json",
                                                                       "X-Jarvo-Kto": "agent"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            info = json.loads(e.read() or b"{}")
        except ValueError:
            info = {}
        raise Odmowa(info.get("blad") or f"HTTP {e.code}") from None


def wypisz(x: dict, jako_json: bool) -> None:
    if jako_json or not isinstance(x, dict) or "tekst" not in x:
        print(json.dumps(x, ensure_ascii=False, indent=2))
    else:
        print(x["tekst"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor")
    d.add_argument("--quiet", action="store_true")
    sub.add_parser("konta")
    k = sub.add_parser("kampanie")
    k.add_argument("--konto")
    s = sub.add_parser("statystyki")
    s.add_argument("--konto", required=True)
    s.add_argument("--od")
    s.add_argument("--do")
    s.add_argument("--poziom", choices=["reklama", "zestaw", "kampania"], default="reklama")
    sz = sub.add_parser("szkic")
    sz.add_argument("plan")
    ko = sub.add_parser("koperta")
    ko.add_argument("akcja", choices=["zglos", "zatwierdz", "stan"])
    ko.add_argument("arg", nargs="?")
    ko.add_argument("--kod")
    p = sub.add_parser("pauza")
    p.add_argument("obiekt")
    b = sub.add_parser("budzet")
    b.add_argument("obiekt")
    b.add_argument("kwota", type=float)
    st = sub.add_parser("stop")
    st.add_argument("--powod", default="STOP na prośbę")
    dz = sub.add_parser("dziennik")
    dz.add_argument("--ile", type=int, default=20)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "doctor":
            r = wolaj("GET", "/doctor")
            if a.quiet:
                return 0 if r.get("ok") else 1
        elif a.cmd == "konta":
            r = wolaj("GET", "/konta")
        elif a.cmd == "kampanie":
            r = wolaj("GET", "/kampanie", konto=a.konto)
        elif a.cmd == "statystyki":
            r = wolaj("GET", "/statystyki", konto=a.konto, od=a.od, do=a.do, poziom=a.poziom)
        elif a.cmd == "szkic":
            r = wolaj("POST", "/szkic", json.load(open(a.plan, encoding="utf-8")))
        elif a.cmd == "koperta":
            if a.akcja == "zglos":
                if not a.arg:
                    raise ValueError("podaj plik koperty")
                r = wolaj("POST", "/koperty", json.load(open(a.arg, encoding="utf-8")))
            elif a.akcja == "zatwierdz":
                if not (a.arg and a.kod):
                    raise ValueError("podaj ID koperty i --kod od użytkownika")
                r = wolaj("POST", f"/koperty/{urllib.parse.quote(a.arg)}/zatwierdz", {"kod": a.kod})
            else:
                r = wolaj("GET", "/koperty" + (f"/{urllib.parse.quote(a.arg)}" if a.arg else ""))
        elif a.cmd == "pauza":
            r = wolaj("POST", "/akcje/pauza", {"obiekt": a.obiekt})
        elif a.cmd == "budzet":
            r = wolaj("POST", "/akcje/budzet", {"obiekt": a.obiekt, "kwota": a.kwota})
        elif a.cmd == "stop":
            r = wolaj("POST", "/stop", {"powod": a.powod})
        else:
            r = wolaj("GET", "/dziennik", ile=a.ile)
    except (urllib.error.URLError, OSError) as exc:
        if isinstance(exc, FileNotFoundError):
            print(f"✗ {exc}", file=sys.stderr)
            return 2
        print("✗ " + NIEPODLACZONY.format(err=getattr(exc, "reason", exc)), file=sys.stderr)
        return 3
    except Odmowa as exc:
        print(f"✗ Skarbiec odmówił: {exc}", file=sys.stderr)
        return 1
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    wypisz(r, a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
