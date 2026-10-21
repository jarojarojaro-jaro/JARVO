"""Oś czasu wątku (docs/HQ.md „Rozmowy”): wpisy aplikacji (wiadomości właściciela, notatki systemu) scalone z
wierszami sesji Hermesa każdego członka (czytnik.py: projekcja Hermesa albo zapasowa, cały rodowód sesji).

- **Nasze wiersze** użytkownika są ukryte (wpis właściciela już je pokazuje): id = `user_msg_id` przebiegu, a zanim
  go znamy, skrót trwałej projekcji = `payload_sha` i czas ≥ `wyslany_at − 2 s`. Tak znika też blok kontekstu, który
  agent dostał przed prośbą, i obrazy zapisane jako `[screenshot]`.
- **Reguły** (najpierw `display_kind`): `hidden` pominięty; `steer` naszego „Dopisz” pominięty (pokazuje go wpis;
  dopasowanie całymi liniami po zdjęciu znacznika Hermesa, `czytnik.dopisek_w_steerze`), obcy = `dopisano` (tekst bez
  znacznika); `async_delegation_complete`/`process_complete` = `dostawa`; `failed_turn` = `blad_tury`; inne
  rodzaje = `system`; użytkownik: nasz = ukryty, `[kanban] Task …` = `budzenie`, streszczenie kompresji = `kompresja`,
  reszta = `obca` (w wątku `import` dymek właściciela); asystent z `tool_calls` = grupa `kroki` przed następnym
  tekstem (czas kroku z zapisanych `kroki` przebiegu), `kanban_create` dodatkowo `przekazanie`; asystent z tekstem =
  `agent`; `tool` uzupełnia błąd kroku; sesja rodowodu, której już nie ma = `luka`.
- **Tura w toku**: wiersze członka od `user_msg_id` aktywnego przebiegu mają `w_toku: true` i `przebieg_id`
  (klient składa je w żywy dymek); kursor `po` cofa się do nich, więc po końcu przebiegu przyjdą jeszcze raz już bez
  `w_toku` (klient podmienia pozycje po `id`). Tak samo otwarta grupa kroków.
- **Kolejność**: w obrębie członka kolejność Hermesa (id / display_order, nigdy czas), między źródłami scalanie
  k-drożne po czasie następnej pozycji każdego źródła.
- **Kursor** (nieprzezroczysty base64 JSON): pokolenie kompresji `g` (liczba wierszy skompaktowanych) i dla każdego
  źródła (`w` = wpisy, `<agent>:<rola>` = rodowód członka) indeksy `[pierwszy, za ostatnim]` wczytanych wierszy
  w kolejności źródła. Inne `g` = odpowiedź z najnowszą stroną i `pelny: true`.
- `pozycje_kontekstu` daje te same pozycje w kształcie wejścia kontekst.blok.
Czyste funkcje nad (Rozmowy, Czytnik); testy: tests/test_scalanie.py.
"""

from __future__ import annotations

import base64
import hashlib
import heapq
import json
import re
import sqlite3
from typing import Any, Callable, Iterable, Mapping

LIMIT = 80
LIMIT_MAKS = 200
PODGLAD_KROKU = 300
OKNO_SHA = 2.0
BLAD_NARZEDZIA = re.compile(r'^\s*(?:\{\s*"(?:error|blad)"|Error\b|ERROR\b|Traceback\b)')
SYSTEMOWE = {"auto_continue": "Automatyczna kontynuacja", "model_switch": "Zmiana modelu",
             "personality_switch": "Zmiana osobowości", "skill_invocation": "Użyto umiejętności",
             "internal_notification": "Komunikat systemowy"}
DOSTAWY = ("async_delegation_complete", "process_complete")


def _sha(tekst: str) -> str:
    return hashlib.sha256(str(tekst or "").encode("utf-8", "surrogatepass")).hexdigest()


def _etykieta_domyslna(nazwa: str | None, args: Any = None) -> dict:
    nazwa = nazwa or "?"
    return {"tool": nazwa, "verb": nazwa.replace("_", " "), "verb_en": nazwa.replace("_", " "), "detail": ""}


def _args(tc: Mapping) -> dict:
    f = tc.get("function") if isinstance(tc.get("function"), dict) else {}
    raw = f.get("arguments") if f else tc.get("arguments")
    if isinstance(raw, dict):
        return raw
    try:
        d = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _nazwa_narzedzia(tc: Mapping) -> str:
    f = tc.get("function") if isinstance(tc.get("function"), dict) else {}
    return str((f or {}).get("name") or tc.get("name") or "?")


# ----------------------------------------------------------------------------------------------- kursor

def koduj_kursor(g: int, z: Mapping[str, list[int]]) -> str:
    surowe = json.dumps({"g": g, "z": {k: [int(v[0]), int(v[1])] for k, v in z.items()}}, separators=(",", ":"))
    return base64.urlsafe_b64encode(surowe.encode()).decode().rstrip("=")


def dekoduj_kursor(tekst: str | None) -> dict | None:
    """Kursor osi albo None; zły = ValueError (trasa: 400)."""
    if not tekst:
        return None
    try:
        surowe = base64.urlsafe_b64decode(tekst + "=" * (-len(tekst) % 4))
        d = json.loads(surowe)
        z = {str(k): [int(v[0]), int(v[1])] for k, v in (d.get("z") or {}).items()}
        return {"g": int(d.get("g") or 0), "z": z}
    except (ValueError, TypeError, AttributeError, IndexError, KeyError) as exc:
        raise ValueError("zły kursor osi") from exc


# ----------------------------------------------------------------------------------------------- źródła

def _pozycja(**pola) -> dict:
    p = {"id": "", "rodzaj": "", "kanal": None, "ts": 0.0, "agent": None, "tryb": None, "tekst": "", "kroki": [],
         "pliki": [], "przebieg_id": None, "w_toku": False}
    p.update(pola)
    return p


def _wpisy(wpisy: list[dict], plik: Callable[[str], dict | None] | None) -> list[dict]:
    out = []
    for i, w in enumerate(wpisy):
        pliki = []
        for z in w.get("zalaczniki") or []:
            e = plik(z.get("path", "")) if plik else None
            pliki.append(e or dict(z))
        out.append(_pozycja(id=w["id"], rodzaj=w["rodzaj"], ts=float(w["utworzony_at"]), tekst=w.get("tekst") or "",
                            tryb=w.get("tryb"), pliki=pliki, wpis=w, _i=i))
    return out


def _czlonek(agent: str, rola: str, linia: list[dict], przebiegi: list[dict], wpisy_id: Mapping[str, dict], *,
             import_: bool, budzenia, etykieta: Callable, utajnij: Callable[[str], str] | None,
             plik: Callable[[str], dict | None] | None, czytnik) -> tuple[list[dict], dict]:
    """Pozycje jednego członka (cały rodowód) i informacje do kursora: `koniec` (liczba wierszy), `od_ponownie`
    (indeks pierwszego wiersza, który trzeba wysłać jeszcze raz: tura w toku albo otwarta grupa kroków),
    `skompaktowane` (pokolenie kompresji)."""
    nasze = [p for p in przebiegi if p["agent"] == agent and (p.get("rola") or "rozmowa") == rola
             and (p.get("wyslany_at") is not None or p.get("user_msg_id") is not None)]
    po_id = {int(p["user_msg_id"]): p for p in nasze if p.get("user_msg_id") is not None}
    po_sha = [p for p in nasze if p.get("payload_sha")]
    dopisane = {str((p.get("payload") or {}).get("prosba") or "").strip() for p in przebiegi
                if p["agent"] == agent and p.get("dopisany_do")}
    dopisane.discard("")
    out: list[dict] = []
    i = 0
    biezacy: dict | None = None
    grupa: dict | None = None
    kroki_wywolan: dict[str, dict] = {}
    licznik_krokow: dict[str, int] = {}
    od_ponownie: int | None = None
    skompaktowane = 0
    ostatni_ts = 0.0
    przekazania: dict[str, dict] = {}

    def tryb_biezacego() -> str | None:
        if not biezacy:
            return None
        if biezacy.get("zrodlo") == "przekaz":
            return "przekaz"
        w = wpisy_id.get(biezacy.get("wpis_id") or "")
        return (w or {}).get("tryb")

    def wspolne(m: dict, idx: int) -> dict:
        nonlocal od_ponownie
        w_toku = bool(biezacy and biezacy.get("aktywny"))
        if w_toku and od_ponownie is None:
            od_ponownie = idx
        return {"ts": float(m["ts"]), "agent": agent, "rola": rola, "przebieg_id": biezacy["id"] if biezacy else None,
                "w_toku": w_toku, "_i": idx}

    for s in linia:
        if s.get("stan") == "brak_sesji":
            out.append(_pozycja(id=f"l:{agent}:{s['sesja_id']}", rodzaj="luka", ts=ostatni_ts, agent=agent, _i=i,
                                tekst="Starsza część rozmowy została usunięta przez Hermesa"))
            i += 1
            continue
        for m in s.get("wiersze") or []:
            idx = i
            i += 1
            ostatni_ts = float(m.get("ts") or ostatni_ts)
            if m.get("skompaktowany"):
                skompaktowane += 1
            rodzaj, rola_m, tresc = m.get("rodzaj"), m.get("rola"), m.get("tresc") or ""
            klucz = f"m:{agent}:{m['klucz']}" if rola == "rozmowa" else f"m:{agent}.{rola}:{m['klucz']}"
            if rodzaj == "hidden":
                continue
            if rola_m == "tool":
                k = kroki_wywolan.get(m.get("tool_call_id") or "")
                if k is not None:
                    k["blad"] = bool(BLAD_NARZEDZIA.match(tresc))
                    k["podglad"] = (utajnij(tresc) if utajnij else tresc)[:PODGLAD_KROKU]
                    p = przekazania.get(m.get("tool_call_id") or "")
                    if p is not None:
                        try:
                            wynik = json.loads(tresc)
                        except ValueError:
                            wynik = {}
                        if isinstance(wynik, dict) and wynik.get("task_id"):
                            p["karta"] = {**(p.get("karta") or {}), "task_id": str(wynik["task_id"])}
                continue
            if rola_m == "user":
                grupa = None
                if rodzaj == "steer":
                    if any(czytnik.dopisek_w_steerze(tresc, d) for d in dopisane):
                        continue
                    out.append(_pozycja(id=klucz, rodzaj="dopisano", **wspolne(m, idx),
                                        tekst=czytnik.tekst_steera(tresc)))
                    continue
                if rodzaj in DOSTAWY:
                    out.append(_pozycja(id=klucz, rodzaj="dostawa", **wspolne(m, idx), tekst=tresc,
                                        dostawa={"rodzaj": rodzaj, "opis": tresc[:300]}))
                    continue
                if rodzaj:
                    out.append(_pozycja(id=klucz, rodzaj="system", **wspolne(m, idx),
                                        tekst=SYSTEMOWE.get(rodzaj, "Komunikat systemowy")))
                    continue
                nasz = po_id.get(int(m.get("id") or 0))
                if nasz is None and po_sha:
                    sha = _sha(tresc)
                    nasz = next((p for p in po_sha if p["payload_sha"] == sha and p.get("user_msg_id") is None
                                 and float(m["ts"]) >= float(p.get("wyslany_at") or 0) - OKNO_SHA), None)
                if nasz is not None:
                    biezacy = nasz
                    if nasz.get("aktywny") and od_ponownie is None:
                        od_ponownie = idx
                    continue
                biezacy = None
                b = budzenia.parsuj(tresc) if budzenia else None
                if b:
                    out.append(_pozycja(id=f"b:{agent}:{m['klucz']}", rodzaj="budzenie", **wspolne(m, idx),
                                        tekst=tresc, budzenie=b))
                elif m.get("podsumowanie"):
                    out.append(_pozycja(id=klucz, rodzaj="kompresja", **wspolne(m, idx),
                                        tekst="Streszczenie wcześniejszej rozmowy"))
                elif import_:
                    out.append(_pozycja(id=klucz, rodzaj="wlasciciel", **wspolne(m, idx), tekst=tresc, wpis=None))
                else:
                    out.append(_pozycja(id=klucz, rodzaj="obca", **wspolne(m, idx), tekst=tresc))
                continue
            if rola_m != "assistant":
                continue
            if rodzaj == "failed_turn":
                grupa = None
                out.append(_pozycja(id=klucz, rodzaj="blad_tury", **wspolne(m, idx), tekst=tresc))
                continue
            if rodzaj:
                out.append(_pozycja(id=klucz, rodzaj="system", **wspolne(m, idx),
                                    tekst=SYSTEMOWE.get(rodzaj, "Komunikat systemowy")))
                continue
            if m.get("tool_calls"):
                if grupa is None:
                    grupa = _pozycja(id=klucz, rodzaj="kroki", **wspolne(m, idx))
                    grupa["_otwarta"] = True
                    out.append(grupa)
                zapisane = (biezacy or {}).get("kroki") or []
                for tc in m["tool_calls"]:
                    if not isinstance(tc, dict):
                        continue
                    nazwa, args = _nazwa_narzedzia(tc), _args(tc)
                    e = etykieta(nazwa, args)
                    n = licznik_krokow.get((biezacy or {}).get("id") or "", 0)
                    licznik_krokow[(biezacy or {}).get("id") or ""] = n + 1
                    czas = None
                    if n < len(zapisane) and isinstance(zapisane[n], dict) and zapisane[n].get("narzedzie") == nazwa:
                        czas = zapisane[n].get("czas_ms")
                    krok = {"ts": float(m["ts"]), "narzedzie": nazwa, "verb": e.get("verb", nazwa),
                            "verb_en": e.get("verb_en", nazwa), "detail": e.get("detail", ""), "czas_ms": czas,
                            "blad": False, "podglad": ""}
                    grupa["kroki"].append(krok)
                    if tc.get("id"):
                        kroki_wywolan[str(tc["id"])] = krok
                    if nazwa == "kanban_create":
                        p = _pozycja(id=f"{klucz}:p{len(grupa['kroki'])}", rodzaj="przekazanie", **wspolne(m, idx),
                                     tekst=str(args.get("title") or ""),
                                     karta={"task_id": None, "tytul": str(args.get("title") or ""),
                                            "agent": str(args.get("assignee") or "")})
                        out.append(p)
                        if tc.get("id"):
                            przekazania[str(tc["id"])] = p
                if tresc.strip():
                    grupa["_otwarta"] = False
                    grupa = None
                    out.append(_pozycja(id=f"{klucz}:t", rodzaj="agent", **wspolne(m, idx), tekst=tresc,
                                        tryb=tryb_biezacego(), pliki=_pliki(tresc, plik)))
                continue
            if tresc.strip():
                if grupa is not None:
                    grupa["_otwarta"] = False
                    grupa = None
                out.append(_pozycja(id=klucz, rodzaj="agent", **wspolne(m, idx), tekst=tresc, tryb=tryb_biezacego(),
                                    pliki=_pliki(tresc, plik)))
    if grupa is not None and grupa.get("_otwarta"):
        od_ponownie = grupa["_i"] if od_ponownie is None else min(od_ponownie, grupa["_i"])
    for p in out:
        p.pop("_otwarta", None)
    return out, {"koniec": i, "od_ponownie": od_ponownie, "skompaktowane": skompaktowane}


SCIEZKA_RE = re.compile(r"/opt/data/[^\s,;\"'<>()\[\]{}`]+")


def _pliki(tekst: str, plik: Callable[[str], dict | None] | None) -> list[dict]:
    if plik is None:
        return []
    out, byly = [], set()
    for s in SCIEZKA_RE.findall(tekst or ""):
        s = s.rstrip(".,:;!?…*_)")
        if s in byly:
            continue
        byly.add(s)
        e = plik(s)
        if e:
            out.append(e)
        if len(out) >= 8:
            break
    return out


def zrodla(db, czytnik, wid: str, *, budzenia=None, etykieta: Callable | None = None,
           utajnij: Callable[[str], str] | None = None, plik: Callable[[str], dict | None] | None = None) -> dict:
    """{"zrodla": {klucz: [pozycje]}, "info": {klucz: {...}}, "g": pokolenie}. Klucze: `w` i `<agent>:<rola>`."""
    watek = db.watek(wid) or {}
    wpisy = db.wpisy(wid, limit=10_000)
    przebiegi = db.przebiegi_watku(wid)
    aktywne = {"kolejka", "wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie",
               "dopisany"}
    for p in przebiegi:
        p["aktywny"] = p["stan"] in aktywne
    wpisy_id = {w["id"]: w for w in wpisy}
    out = {"w": _wpisy(wpisy, plik)}
    info = {"w": {"koniec": len(wpisy), "od_ponownie": None, "skompaktowane": 0}}
    g = 0
    bledy: list[dict] = []
    for c in db.czlonkowie(wid):
        sesje = [s["sesja_id"] for s in db.sesje_watku(wid, agent=c["agent"], rola=c["rola"])]
        if not sesje:
            continue
        try:
            linia = czytnik.linia(c["agent"], sesje)
        except ValueError:            # agent spoza listy (usunięty agent testowy): jego wierszy nie czytamy
            continue
        except (RuntimeError, sqlite3.Error) as exc:   # schemat Hermesa zmieniony, baza nieczytelna: reszta osi zostaje
            bledy.append({"agent": c["agent"], "blad": type(exc).__name__})
            continue
        klucz = f"{c['agent']}:{c['rola']}"
        pozycje, inf = _czlonek(c["agent"], c["rola"], linia, przebiegi, wpisy_id,
                                import_=watek.get("rodzaj") == "import", budzenia=budzenia,
                                etykieta=etykieta or _etykieta_domyslna, utajnij=utajnij, plik=plik, czytnik=czytnik)
        out[klucz] = pozycje
        info[klucz] = inf
        g += inf["skompaktowane"]
    return {"zrodla": out, "info": info, "g": g, "bledy": bledy}


def _scal(zr: Mapping[str, list[dict]]) -> list[tuple[str, dict]]:
    return list(heapq.merge(*[[(k, p) for p in v] for k, v in zr.items()], key=lambda x: x[1]["ts"]))


def _czyste(p: dict) -> dict:
    return {k: v for k, v in p.items() if not k.startswith("_")}


def os_watku(db, czytnik, wid: str, *, przed: str | None = None, po: str | None = None, limit: int = LIMIT,
             **kw) -> dict:
    """Strona osi czasu: najnowsza (domyślnie), starsza (`przed`) albo nowsza (`po`)."""
    limit = max(1, min(int(limit or LIMIT), LIMIT_MAKS))
    k = dekoduj_kursor(przed or po)
    dane = zrodla(db, czytnik, wid, **kw)
    zr, info, g = dane["zrodla"], dane["info"], dane["g"]
    scalone = _scal(zr)
    pelny = bool(k and k["g"] != g)
    if k and not pelny and przed:
        z = k["z"]
        strona = [x for x in scalone if x[0] in z and x[1]["_i"] < z[x[0]][0]][-limit:]
        nowe = {s: list(v) for s, v in z.items()}
    elif k and not pelny and po:
        z = k["z"]
        strona = [x for x in scalone if x[1]["_i"] >= (z[x[0]][1] if x[0] in z else 0)][:limit]
        nowe = {s: list(v) for s, v in z.items()}
    else:
        strona = scalone[-limit:]
        nowe = {s: [inf["koniec"], inf["koniec"]] for s, inf in info.items()}
    for s, p in strona:
        a, b = nowe.get(s, [p["_i"], p["_i"] + 1])
        nowe[s] = [min(a, p["_i"]), max(b, p["_i"] + 1)]
    for s, inf in info.items():                  # tura w toku i otwarta grupa kroków przyjdą jeszcze raz
        if inf.get("od_ponownie") is not None and s in nowe:
            nowe[s][1] = max(nowe[s][0], min(nowe[s][1], inf["od_ponownie"]))
    ma_starsze = any(p["_i"] < nowe.get(s, [0, 0])[0] for s, p in scalone)
    kursor = koduj_kursor(g, nowe)
    wynik = {"pozycje": [_czyste(p) for _s, p in strona], "przed": kursor if ma_starsze else None, "po": kursor}
    if pelny:
        wynik["pelny"] = True
    if dane["bledy"]:                            # członek nieczytelny (schemat Hermesa): UI pokazuje żółtą linię
        wynik["niedostepni"] = sorted({b["agent"] for b in dane["bledy"]})
    return wynik


def pozycje_kontekstu(db, czytnik, wid: str, **kw) -> list[dict]:
    """Pozycje osi w kształcie wejścia kontekst.blok (wpisy właściciela i systemu, odpowiedzi agentów, budzenia)."""
    out = []
    for _s, p in _scal(zrodla(db, czytnik, wid, **kw)["zrodla"]):
        r = p["rodzaj"]
        if r == "wlasciciel" and p.get("wpis"):
            w = p["wpis"]
            if (w.get("dane") or {}).get("dopisane_do"):
                continue
            out.append({"ts": p["ts"], "rodzaj": "wlasciciel", "adresaci": w.get("adresaci") or [],
                        "tekst": w.get("tresc") or w.get("tekst") or "",
                        "pliki": [z.get("path") for z in w.get("zalaczniki") or [] if z.get("path")],
                        "obrazy": [o.get("path") for o in w.get("obrazy") or [] if o.get("path")], "wpis_id": w["id"]})
        elif r == "system" and p.get("wpis"):
            if (p["wpis"].get("dane") or {}).get("typ") in ("dolaczyl", "kompresja"):
                continue
            out.append({"ts": p["ts"], "rodzaj": "system", "tekst": p.get("tekst") or ""})
        elif r == "agent":
            out.append({"ts": p["ts"], "rodzaj": "agent", "agent": p["agent"], "rola": p.get("rola") or "rozmowa",
                        "tekst": p.get("tekst") or ""})
        elif r == "budzenie":
            b = p.get("budzenie") or {}
            out.append({"ts": p["ts"], "rodzaj": "budzenie",
                        "karta": {"task_id": b.get("task_id"), "tytul": b.get("tytul"), "agent": b.get("wykonawca"),
                                  "status_pl": b.get("status_pl")}})
    return out


def ostatnia_praca(pozycje: Iterable[Mapping], koordynator: str) -> dict | None:
    """Ostatnia odpowiedź agenta innego niż koordynator (nagłówek bloku koordynatora): {agent, tryb, ts}."""
    for p in reversed(list(pozycje)):
        if p.get("rodzaj") == "agent" and p.get("agent") and p.get("agent") != koordynator:
            return {"agent": p["agent"], "tryb": p.get("tryb") or "bezposrednio", "ts": p["ts"]}
    return None
