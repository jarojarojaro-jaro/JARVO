#!/usr/bin/env python3
"""Bramka aplikacji: jeden werdykt z kontroli kodu, zrzutów, testów wrogich (web, Android, iOS) i oceny rubryką.

    bramka.py wrogie <app> [--trasy / /wiecej …]          # warstwa web: eksport już zrobiony przez `aplikacja.py podglad`
    bramka.py ocena-szablon > <app>/out/jakosc/ocena-runda-1.json
    bramka.py werdykt <app> --runda N --ocena <app>/out/jakosc/ocena-runda-N.json [--json]

Źródła (z katalogu aplikacji): `out/jakosc/sprawdz.json` (aplikacja.py sprawdz), `out/zrzuty/zrzuty.json`
(aplikacja.py podglad), `out/jakosc/wrogie/wrogie.json` (warstwa web), opcjonalnie `out/jakosc/wrogie-android/wrogie.json`
(urzadzenie.py wrogie) i `out/jakosc/ios/wynik.json` (ios_ci.py). Ocena rubryką (10 osi, references/rubryka.md) to JSON
od agenta: każda oś zaliczona albo różnica z dowodem i najmniejszą poprawką.

Punkty: start 100; różnica na osiach 1–5 −8, na osiach 6–10 −5; każdy problem blokujący (kontrola kodu, test wrogi
`blad`, poważny błąd axe, błąd konsoli) −15. `BLOCK` zawsze przy: awarii na urządzeniu, sekrecie w kodzie, braku zrzutów,
4. rundzie. `PASS` od 90 bez blokad. `not_run` to brak pomiaru: werdykt go wypisuje, nie liczy jako zaliczenie.
Wynik: `out/jakosc/werdykt-runda-N.json` i `WERDYKT.md`. Kod: 0 = PASS, 1 = REVISE, 2 = BLOCK.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OSIE = {1: "Pierwsze 30 sekund", 2: "Nawigacja wg platformy", 3: "Kciuk i cele dotyku", 4: "Tekst i duża czcionka",
        5: "Stany ekranów", 6: "Formularze i klawiatura", 7: "Tryb ciemny i kontrast", 8: "Ruch i płynność",
        9: "Uprawnienia i zaufanie", 10: "Marka i dopracowanie"}
MAKS_RUND = 3


def _json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ocena_szablon() -> dict:
    return {"runda": 1, "osie": [{"os": n, "nazwa": nazwa, "zaliczona": None, "dowod": "", "roznica": "", "poprawka": ""}
                                 for n, nazwa in OSIE.items()]}


def werdykt(app: Path, runda: int, ocena: dict) -> dict:
    jak = app / "out" / "jakosc"
    blokady: list[str] = []          # BLOCK
    problemy: list[str] = []         # −15
    niezmierzone: list[str] = []
    roznice: list[dict] = []
    punkty = 100

    spr = _json(jak / "sprawdz.json")
    if not spr:
        problemy.append("brak out/jakosc/sprawdz.json (aplikacja.py sprawdz)")
    else:
        for k in spr.get("kontrole", []):
            if not k.get("ok"):
                if k["id"] in ("J-SEKRET", "J-PUBLIC"):
                    blokady.append(f"sekret w kodzie aplikacji: {k['opis']}")
                else:
                    problemy.append(f"kontrola {k['id']}: {k['opis']}")
    zr = _json(app / "out" / "zrzuty" / "zrzuty.json")
    if not zr or not zr.get("wyniki"):
        blokady.append("brak zrzutów (aplikacja.py podglad): ocena bez zrzutów nie istnieje")
    else:
        if zr.get("bledy_lacznie"):
            problemy.append(f"zrzuty: {zr['bledy_lacznie']} błędów konsoli, przewijania albo pustych ekranów")
        if zr.get("axe_powazne"):
            problemy.append(f"zrzuty: {zr['axe_powazne']} poważnych błędów dostępności (axe)")
    warstwy = {"web": jak / "wrogie" / "wrogie.json", "android": jak / "wrogie-android" / "wrogie.json",
               "ios": jak / "ios" / "wynik.json"}
    zmierzone = []
    for warstwa, plik in warstwy.items():
        dane = _json(plik)
        if not dane:
            niezmierzone.append(f"warstwa {warstwa}: brak wyników ({plik.relative_to(app)})")
            continue
        zmierzone.append(warstwa)
        for w in dane.get("wyniki", []):
            if w["status"] == "blad":
                if warstwa != "web" and "awaria" in w.get("dlaczego", ""):
                    blokady.append(f"{warstwa}/{w['id']}: {w['dlaczego']}")
                else:
                    problemy.append(f"{warstwa}/{w['id']}: {w['dlaczego']}")
            elif w["status"] == "not_run":
                niezmierzone.append(f"{warstwa}/{w['id']}: {w.get('dlaczego', '')}")
    if "web" not in zmierzone:
        problemy.append("brak testów wrogich warstwy web (bramka.py wrogie)")
    osie = {o.get("os"): o for o in ocena.get("osie", [])}
    for n, nazwa in OSIE.items():
        o = osie.get(n)
        if not o or o.get("zaliczona") is None:
            problemy.append(f"oś {n} ({nazwa}) bez oceny")
            continue
        if not o.get("dowod"):
            problemy.append(f"oś {n} ({nazwa}) bez dowodu (który zrzut, co widać)")
        if not o["zaliczona"]:
            punkty -= 8 if n <= 5 else 5
            roznice.append({"os": f"{n}. {nazwa}", "roznica": o.get("roznica", ""), "poprawka": o.get("poprawka", ""),
                            "dowod": o.get("dowod", "")})
            if not o.get("poprawka"):
                problemy.append(f"oś {n}: różnica bez najmniejszej poprawki")
    punkty -= 15 * len(problemy)
    punkty = max(0, punkty)
    if runda > MAKS_RUND:
        blokady.append(f"runda {runda} > {MAKS_RUND}: oddaj z ostatnim werdyktem i listą niezamkniętych różnic")
    stan = "BLOCK" if blokady else ("PASS" if punkty >= 90 and not problemy else "REVISE")
    return {"runda": runda, "wynik": punkty, "werdykt": stan, "blokady": blokady, "problemy": problemy,
            "roznice": roznice, "niezmierzone": niezmierzone, "warstwy": zmierzone,
            "zrzuty": str(app / "out" / "zrzuty")}


def werdykt_md(w: dict) -> str:
    l = [f"# Bramka aplikacji: runda {w['runda']}", "", f"**{w['werdykt']}** · wynik {w['wynik']}/100 · warstwy: "
         f"{', '.join(w['warstwy']) or 'brak'}", ""]
    for tytul, klucz in (("Blokady", "blokady"), ("Problemy (−15 każdy)", "problemy")):
        if w[klucz]:
            l += [f"## {tytul}"] + [f"- {x}" for x in w[klucz]] + [""]
    if w["roznice"]:
        l += ["## Różnice z rubryki", "", "| Oś | Różnica | Najmniejsza poprawka | Dowód |", "|---|---|---|---|"]
        l += [f"| {r['os']} | {r['roznica']} | {r['poprawka']} | {r['dowod']} |" for r in w["roznice"]]
        l.append("")
    if w["niezmierzone"]:
        l += ["## Niezmierzone (to nie jest zaliczenie)"] + [f"- {x}" for x in w["niezmierzone"]] + [""]
    return "\n".join(l)


def wrogie_web(app: Path, trasy: list[str]) -> dict:
    """Warstwa web na eksporcie z dist-web (serwer zrzutów z aplikacja.py, bez HQ)."""
    import aplikacja
    dist = app / "dist-web"
    if not (dist / "index.html").exists():
        raise SystemExit("brak dist-web: najpierw `aplikacja.py podglad` (eksport)")
    html = (dist / "index.html").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'src="(/[^"/]+)/_expo/', html)
    prefiks = m.group(1) if m else ""
    srv, port = aplikacja.serwer_spa(dist, prefiks)
    out = app / "out" / "jakosc" / "wrogie"
    try:
        r = subprocess.run(["node", str(Path(__file__).resolve().parent / "wrogie.cjs"), f"http://127.0.0.1:{port}{prefiks}",
                            str(out), "--trasy", ",".join(trasy)], capture_output=True, text=True, timeout=900)
    finally:
        srv.shutdown()
    if r.returncode not in (0, 1) or not (out / "wrogie.json").exists():
        raise SystemExit(f"wrogie.cjs: {(r.stdout + r.stderr)[-1200:]}")
    return json.loads((out / "wrogie.json").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wrogie")
    w.add_argument("app")
    w.add_argument("--trasy", nargs="*", default=["/", "/wiecej", "/kontakt", "/prywatnosc"])
    sub.add_parser("ocena-szablon")
    v = sub.add_parser("werdykt")
    v.add_argument("app")
    v.add_argument("--runda", type=int, required=True)
    v.add_argument("--ocena", required=True)
    v.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "ocena-szablon":
        print(json.dumps(ocena_szablon(), ensure_ascii=False, indent=2))
        return 0
    app = Path(args.app).resolve()
    if args.cmd == "wrogie":
        r = wrogie_web(app, args.trasy)
        print(r["podsumowanie"])
        return 1 if any(x["status"] == "blad" for x in r["wyniki"]) else 0
    ocena = json.loads(Path(args.ocena).read_text(encoding="utf-8"))
    wynik = werdykt(app, args.runda, ocena)
    jak = app / "out" / "jakosc"
    jak.mkdir(parents=True, exist_ok=True)
    (jak / f"werdykt-runda-{args.runda}.json").write_text(json.dumps(wynik, ensure_ascii=False, indent=2), encoding="utf-8")
    (jak / "WERDYKT.md").write_text(werdykt_md(wynik), encoding="utf-8")
    print(json.dumps(wynik, ensure_ascii=False, indent=2) if args.json else werdykt_md(wynik))
    return {"PASS": 0, "REVISE": 1, "BLOCK": 2}[wynik["werdykt"]]


if __name__ == "__main__":
    sys.exit(main())
