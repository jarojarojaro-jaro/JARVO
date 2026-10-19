"""Wtyczka jarvo-komputer: narzędzie `komputer` dla agentów z `komputer: true` we fleet.yaml (Operator, docs/KOMPUTER.md §7).

Rozmawia z wejściem Komputera Jarva przez gniazdo sterowania (`ster.sock`, docs/KOMPUTER.md §6):
  stan       czy Komputer działa, pauza i jej powód, ile sesji, czy działa drzewo dostępności (AT-SPI),
  dziennik   ostatnie decyzje twardych zasad (bez treści: narzędzie, decyzja, zasada, cel),
  oddaj      prośba do właściciela: pauza z powodem („zaloguj się do panelu sklepu”). Komputer stoi, dopóki
             właściciel go nie wznowi (`jarvo komputer wznow`, w K4 przycisk w Ekranie HQ).
Wznowić agent nie może: wejście przepuszcza `wznow` tylko od właściciela (SO_PEERCRED), a narzędzie go nie wysyła.
build.py kopiuje wtyczkę do plugins/jarvo-komputer, install-fleet.sh dowiązuje ją w profilach z `komputer: true`.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Any, Dict

NAZWA = "jarvo-komputer"
STER = os.path.join(os.path.dirname(os.environ.get("JARVO_KOMPUTER_GNIAZDO", "/opt/jarvo/komputer/cua.sock")),
                    "ster.sock")
WYLACZONY = ("Komputer Jarva jest wyłączony albo jeszcze startuje. Właściciel włącza go na komputerze z Jarvem: "
             "jarvo komputer on (docs/KOMPUTER.md).")
MAKS_PROSBA = 300
MAKS_WPISOW = 50

SCHEMAT: Dict[str, Any] = {
    "name": "komputer",
    "description": (
        "Komputer Jarva (Twój pulpit z Chromium, którym sterujesz narzędziem computer_use). "
        "akcja=stan: czy działa, czy jest pauza i dlaczego, czy działa drzewo dostępności. "
        "akcja=dziennik: ostatnie decyzje twardych zasad (co przeszło, co wymaga właściciela, co zablokowane). "
        "akcja=oddaj: oddajesz ekran właścicielowi z prośbą (np. „zaloguj się do panelu sklepu”, „kliknij Zapłać”): "
        "Komputer staje, dopóki właściciel go nie wznowi; potem sprawdź ekran od nowa. Wznowić możesz tylko poprosić."),
    "parameters": {
        "type": "object",
        "properties": {
            "akcja": {"type": "string", "enum": ["stan", "dziennik", "oddaj"]},
            "prosba": {"type": "string", "description": (
                "Dla akcja=oddaj: co właściciel ma zrobić w Ekranie HQ, jednym zdaniem (gdzie i co kliknąć). "
                "Bez haseł, kodów i danych osobowych.")},
            "n": {"type": "integer", "description": f"Dla akcja=dziennik: ile ostatnich wpisów (1–{MAKS_WPISOW}, domyślnie 20)."},
        },
        "required": ["akcja"],
    },
}


def _ster(polecenie: Dict[str, Any], czas: float = 5.0) -> Dict[str, Any]:
    """Jedno polecenie JSON do ster.sock; odpowiedź albo {"ok": False, "blad": ...}."""
    if not os.path.exists(STER):
        return {"ok": False, "dziala": False, "blad": WYLACZONY}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(czas)
    try:
        s.connect(STER)
        s.sendall((json.dumps(polecenie, ensure_ascii=False) + "\n").encode())
        dane = b""
        while not dane.endswith(b"\n") and len(dane) < (1 << 20):
            k = s.recv(65536)
            if not k:
                break
            dane += k
        odp = json.loads(dane or b"{}")
        return odp if isinstance(odp, dict) else {"ok": False, "blad": "wejście odpowiedziało nie po JSON-owemu"}
    except (OSError, ValueError) as e:
        return {"ok": False, "dziala": False, "blad": f"{WYLACZONY} ({type(e).__name__})"}
    finally:
        s.close()


def _stan(odp: Dict[str, Any]) -> Dict[str, Any]:
    if not odp.get("ok"):
        return odp
    wynik = {"ok": True, "dziala": True, "wstrzymane": bool(odp.get("wstrzymane")), "sesje": odp.get("sesje"),
             "drzewo_dostepnosci": bool(odp.get("atspi"))}
    if odp.get("pauza"):
        wynik["pauza"] = odp["pauza"].get("opis") or ""
        wynik["kto_wstrzymal"] = "Operator (czeka na właściciela)" if odp["pauza"].get("kto") == "flota" else "właściciel"
    if not wynik["drzewo_dostepnosci"]:
        wynik["uwaga"] = "drzewo dostępności nie działa: elementy tylko ze zrzutu (capture mode=som), punkty klikasz ostrożnie"
    return wynik


def obsluz(args: Dict[str, Any], **_: Any) -> str:
    akcja = str((args or {}).get("akcja") or "stan")
    if akcja == "stan":
        wynik = _stan(_ster({"polecenie": "stan"}))
    elif akcja == "dziennik":
        n = args.get("n", 20)
        n = n if isinstance(n, int) and not isinstance(n, bool) and 0 < n <= MAKS_WPISOW else 20
        odp = _ster({"polecenie": "dziennik", "n": n})
        wynik = {"ok": True, "wpisy": odp.get("wpisy", [])} if odp.get("ok") else odp
    elif akcja == "oddaj":
        prosba = " ".join(str(args.get("prosba") or "").split())[:MAKS_PROSBA]
        if len(prosba) < 8:
            return json.dumps({"ok": False, "blad": "oddaj: napisz w `prosba`, co właściciel ma zrobić w Ekranie HQ "
                                                   "(np. „zaloguj się do panelu sklepu i daj znać”)"}, ensure_ascii=False)
        wynik = _stan(_ster({"polecenie": "pauza", "powod": prosba}))
        if wynik.get("ok"):
            wynik["dalej"] = ("Komputer stoi i czeka na właściciela. Powiedz mu dokładnie, co ma zrobić (to samo, co w prośbie), "
                              "zakończ swoją część albo zablokuj kartę z tym powodem. Po wznowieniu zacznij od capture.")
            if wynik.get("kto_wstrzymal") == "właściciel":
                wynik["dalej"] = "Właściciel już wstrzymał Komputer; Twoja prośba nie nadpisała jego pauzy. " + wynik["dalej"]
    else:
        wynik = {"ok": False, "blad": "akcja: stan, dziennik albo oddaj"}
    return json.dumps(wynik, ensure_ascii=False)


def register(ctx) -> None:
    ctx.register_tool(name="komputer", toolset="komputer", schema=SCHEMAT, handler=obsluz, emoji="🖥️",
                      description="Komputer Jarva: stan, dziennik twardych zasad, oddanie ekranu właścicielowi")
