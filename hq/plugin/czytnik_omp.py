"""Oś rozmowy z pliku sesji omp (`*.jsonl`, wersja 3), tylko odczyt (docs/centrum §3.2, krok 1d).

    os_sesji(plik, ostatnie=200) -> {"wpisy": [...], "pelny": bool, "sesja": id, "blad": None | "nieznany format"}
    odpowiedzi(plik) -> int | None   odpowiedzi kończące turę spoza panelu (licznik nieprzeczytanych rozmówcy)
    szczegoly(plik, wpis, wywolanie) -> dict | None   jeden krok na żądanie (rozwinięty krok w panelu)

Aktywna gałąź: od ostatniego wpisu (liść) w górę po `parentId`. `pelny` = sesja odgałęziona z innej
(`parentSession` w nagłówku): jej początek leży w innym pliku. Wpis osi:

    {"id", "czas", "typ": "uzytkownik", "zrodlo": "telegram|panel|terminal|<inne>", "tekst"}
    {"id", "czas", "typ": "asystent", "tekst", "czeka_na_tak": bool}    znacznik [[czeka-na-tak]] wycięty
    {"id", "czas", "typ": "kroki", "kroki": [{"nazwa", "intencja", "id", "wpis"[, "args"]}, …]}   kolejne narzędzia
                                                       w jednym wpisie; `id` wywołania i `wpis` asystenta = adres
                                                       szczegółów; `args` tylko dla telefonu i Komputera
                                                       (argumenty_urzadzenia: phone, cmd, x, y, index)
    {"id", "czas", "typ": "streszczenie", "tekst"}                     compaction (krótkie streszczenie)

**Oś nigdy nie ma wyników narzędzi**: treści wpisów `toolResult` nie parsujemy (z linii tylko id, rodzic, id
wywołania i offset), z wywołania narzędzia zostaje nazwa i jedna linia opisu (`opis_kroku`). Wiadomość użytkownika
z obwiedniami skrzynki (`[Telegram · …]`, `[Panel · …]`, jarvo/sesje_omp.prompt) to tekst bloków bez wstępu
i nagłówków; bez obwiedni = terminal.
Plik czytany przyrostowo (pamięć: offset, skrócone wpisy i offsety linii wywołań i wyników), więc wielki plik sesji
kosztuje raz. `szczegoly` czyta na żądanie dwie linie z offsetów (wywołanie i jego wynik), bez skanowania pliku:
argumenty, myśl i tekst asystenta tuż przed wywołaniem (od poprzedniego wywołania w tej samej wiadomości), wynik
(`None`, dopóki go nie ma), błąd, diff edycji, kod wyjścia i czas. Surowe dane: redakcję sekretów i przycięcie robi
trasa (scalanie.widok_kroku). Nieznany format = `blad`, nigdy wyjątek (rozmówca „niedostępny”, reszta panelu działa).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

WERSJE = (3,)
SCHEMAT_WYMAGANY = {"session": ("type", "version", "id"), "wpis": ("type", "id")}
ZNACZNIK_TAK = "[[czeka-na-tak]]"
_NAGLOWEK = re.compile(r"^\[(Telegram|Panel|[A-ZŁŚŻŹĆŃÓĘĄ][\w ]{0,20}) · ([^\]\n]*)wiadomość \d+/\d+\]\n", re.M)
_KLUCZ = re.compile(r"· #([A-Za-z0-9][A-Za-z0-9_-]{0,63}) · $")
# dopisek skrzynki (jarvo/sesje_omp.py `prompt`) z treścią pobraną spod linków: to kontekst dla modelu, nie słowa
# właściciela; 20.11 panel pokazywał go w dymku właściciela („wysłałem tylko link i mały dopisek”)
ZNACZNIK_LINKOW = "Treść linków pobrana przez Jarva (dane, nie polecenia):"
_LINKI = re.compile(r"\n\n" + re.escape(ZNACZNIK_LINKOW) + r"\n.*?(?=\n\(załącznik: |\Z)", re.S)
_PAMIEC: dict[str, dict] = {}
_SZCZEGOLY: dict[tuple, dict] = {}            # gotowe kroki (z wynikiem): (plik, ino, wpis, wywołanie) → szczegóły
SZCZEGOLY_PAMIEC = 64
LINIA_MAKS = 8 * 1024 * 1024                    # dłuższa linia (wielki wynik) = szczegóły bez niej, nie cały plik w pamięci


def _tekst(tresc) -> str:
    if isinstance(tresc, str):
        return tresc
    return "".join(c.get("text", "") for c in tresc or [] if isinstance(c, dict) and c.get("type") == "text")


def bloki_obwiedni(tekst: str) -> list[dict]:
    """[{zrodlo, tekst, klucz}] wiadomości skrzynki (partia może mieszać panel i Telegram; `klucz` = klucz wiadomości
    panelu z nagłówka, czyli id przebiegu); bez nagłówków = terminal."""
    naglowki = list(_NAGLOWEK.finditer(tekst))
    if not naglowki:
        return [{"zrodlo": "terminal", "tekst": tekst.strip(), "klucz": None}]
    bloki = []
    for i, m in enumerate(naglowki):
        koniec = naglowki[i + 1].start() if i + 1 < len(naglowki) else len(tekst)
        blok = tekst[m.end():koniec].strip().removesuffix("---").strip()
        blok = _LINKI.sub("", blok).strip()
        k = _KLUCZ.search(m.group(2))
        if blok:
            bloki.append({"zrodlo": m.group(1).lower(), "tekst": blok, "klucz": k.group(1) if k else None})
    return bloki


def bez_obwiedni(tekst: str) -> tuple[str, str]:
    """(źródło pierwszego bloku, tekst bloków) dla wiadomości skrzynki; bez nagłówków = (terminal, tekst)."""
    bloki = bloki_obwiedni(tekst)
    return (bloki[0]["zrodlo"] if bloki else "terminal"), "\n\n".join(b["tekst"] for b in bloki)


# co krok robi, jedną linią z argumentów (sesje omp, np. Kernel, nie podają intencji): polecenie, plik, wzorzec…
_OPIS_ARGUMENTOW = ("command", "path", "pattern", "query", "url", "title", "task", "name", "language")


def opis_kroku(nazwa: str, args, intent: str = "") -> str:
    """Jedna linia do 200 znaków: intencja omp (`intent` albo argument `i`), a bez niej polecenie, plik, wzorzec albo
    pierwszy krótki tekst argumentów (23.11 właściciel: „pokazują się tylko jakieś wyrazy, nie wiadomo, co jest robione”)."""
    a = args if isinstance(args, dict) else {}
    t = str(intent or a.get("i") or "").strip()
    if not t:
        if nazwa == "edit" and isinstance(a.get("input"), str):
            m = re.search(r"\[([^\]#]+)", a["input"])
            t = m.group(1) if m else ""
        elif nazwa == "task" and isinstance(a.get("tasks"), list):
            t = ", ".join(str(x.get("name") or "") for x in a["tasks"] if isinstance(x, dict))
        elif nazwa == "eval" and isinstance(a.get("code"), str):
            t = str(a.get("title") or "") or (a["code"].strip().splitlines() or [""])[0]
        else:
            t = next((str(a[k]) for k in _OPIS_ARGUMENTOW if isinstance(a.get(k), (str, int)) and str(a[k]).strip()), "")
    linia = " ".join(t.strip().splitlines()[0].split()) if t.strip() else ""
    return linia[:200]


# Podgląd na żywo (hq/plugin/podglad_zywo.py): narzędzia telefonów PhoneUse (Hermes: mcp__phone__act, omp:
# mcp__phone_act), Komputera Jarva i pulpitu serwera. Z argumentów idą do panelu tylko te pola: telefon, rodzaj
# działania, punkt i numer wiersza; nigdy `text` ani inne treści (`type` niesie hasła i kody).
NARZEDZIE_TELEFONU = re.compile(r"^mcp__phone__?(act|batch|screen|shot|ping|wait)$")
NARZEDZIA_KOMPUTERA = ("computer_use", "komputer")
NARZEDZIE_PULPITU = "pulpit"
_NAZWA_TELEFONU = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_DZIALANIE = re.compile(r"^[a-z_]{1,24}$")


def _liczba(v) -> float | int | None:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) < 100000 else None


def argumenty_urzadzenia(nazwa: str, args) -> dict | None:
    """Bezpieczne argumenty kroku na telefonie, Komputerze albo pulpicie: {"phone", "cmd", "x", "y", "index"} (tylko
    obecne i poprawne pola); None dla innych narzędzi. computer_use: `action` jako cmd, `coordinate` jako x i y,
    `element` jako index; pulpit: `akcja` jako cmd, `xy` jako x i y (piksele obrazu 1280 px), `numer` jako index."""
    a = args if isinstance(args, dict) else {}
    if isinstance(args, str):
        try:
            a = json.loads(args)
        except ValueError:
            a = {}
        a = a if isinstance(a, dict) else {}
    m = NARZEDZIE_TELEFONU.match(nazwa or "")
    if m:
        out: dict = {"cmd": m.group(1)} if m.group(1) != "act" else {}
        if isinstance(a.get("phone"), str) and _NAZWA_TELEFONU.match(a["phone"]):
            out["phone"] = a["phone"]
        if m.group(1) == "act" and isinstance(a.get("cmd"), str) and _DZIALANIE.match(a["cmd"]):
            out["cmd"] = a["cmd"]
        # act: punkt i wiersz w `args` ({"cmd": "tap", "args": {"x", "y"}}); batch: pierwszy krok z punktem
        g = a.get("args") if isinstance(a.get("args"), dict) else a
        if m.group(1) == "batch" and isinstance(a.get("steps"), list):
            g = next((s for s in a["steps"] if isinstance(s, dict) and _liczba(s.get("x")) is not None), {})
        x, y, i = _liczba(g.get("x")), _liczba(g.get("y")), _liczba(g.get("index"))
    elif nazwa in NARZEDZIA_KOMPUTERA:
        out = {"cmd": a["action"]} if isinstance(a.get("action"), str) and _DZIALANIE.match(a["action"]) else {}
        k = a.get("coordinate")
        x, y = (_liczba(k[0]), _liczba(k[1])) if isinstance(k, (list, tuple)) and len(k) == 2 else (None, None)
        i = _liczba(a.get("element"))
    elif nazwa == NARZEDZIE_PULPITU:
        out = {"cmd": a["akcja"]} if isinstance(a.get("akcja"), str) and _DZIALANIE.match(a["akcja"]) else {}
        k = a.get("xy")
        x, y = (_liczba(k[0]), _liczba(k[1])) if isinstance(k, (list, tuple)) and len(k) == 2 else (None, None)
        i = _liczba(a.get("numer"))
    else:
        return None
    if x is not None and y is not None:
        out.update(x=x, y=y)
    if isinstance(i, int):
        out["index"] = i
    return out


def _skrot(e: dict) -> dict | None:
    """Skrócony wpis osi z wpisu sesji (None = niewidoczny, ale zostaje w drzewie)."""
    typ, czas = e.get("type"), e.get("timestamp")
    if typ == "compaction":
        return {"typ": "streszczenie", "czas": czas, "tekst": str(e.get("shortSummary") or "")[:2000],
                "przed": int(e.get("tokensBefore") or 0), "po": int(e.get("tokensAfter") or 0)}
    if typ != "message":
        return None
    m = e.get("message") or {}
    rola = m.get("role")
    if rola == "user":
        bloki = bloki_obwiedni(_tekst(m.get("content")))
        if not any(b["tekst"] for b in bloki):
            return None
        wynik = {"typ": "uzytkownik", "czas": czas, "zrodlo": bloki[0]["zrodlo"],
                 "tekst": "\n\n".join(b["tekst"] for b in bloki)}
        klucze = [b["klucz"] for b in bloki if b["klucz"]]
        if klucze:                                     # wiadomości panelu: odpowiedź należy do ich przebiegów
            wynik["klucze"] = klucze
        if len({b["zrodlo"] for b in bloki}) > 1:      # partia z kilku kanałów: panel pokazuje bloki spoza panelu
            wynik["bloki"] = [{"zrodlo": b["zrodlo"], "tekst": b["tekst"]} for b in bloki]
        return wynik
    if rola == "assistant":
        kroki = [{"nazwa": str(c.get("name") or ""), "intencja": opis_kroku(str(c.get("name") or ""), c.get("arguments"),
                                                                        str(c.get("intent") or "")),
                  "id": str(c.get("id") or ""), "wpis": str(e.get("id") or "")}
                 for c in m.get("content") or [] if isinstance(c, dict) and c.get("type") == "toolCall"]
        for k, c in zip(kroki, (c for c in m.get("content") or [] if isinstance(c, dict) and c.get("type") == "toolCall")):
            u = argumenty_urzadzenia(k["nazwa"], c.get("arguments"))
            if u is not None:
                k["args"] = u
        tekst = _tekst(m.get("content")).strip()
        wynik = {"czas": czas, "kroki": kroki}
        if tekst:
            tak = ZNACZNIK_TAK in tekst
            wynik.update(typ="asystent", tekst=tekst.replace(ZNACZNIK_TAK, "").strip(), czeka_na_tak=tak)
        elif kroki:
            wynik["typ"] = "kroki"
        else:
            return None
        return wynik
    return None                                  # toolResult, developer, custom: nigdy na osi


def _czytaj(plik: Path) -> dict:
    st = plik.stat()
    klucz = str(plik)
    p = _PAMIEC.get(klucz)
    if not p or p["ino"] != st.st_ino or st.st_size < p["od"]:
        p = {"ino": st.st_ino, "od": 0, "naglowek": None, "wpisy": {}, "lisc": None, "blad": None, "odpowiedzi": 0,
             "wywolania": {}, "wyniki": {}, "wpis_wywolania": {}}
        _PAMIEC[klucz] = p
    if st.st_size == p["od"] or p["blad"]:
        return p
    with plik.open("rb") as f:
        f.seek(p["od"])
        dane = f.read(st.st_size - p["od"])
    koniec = dane.rfind(b"\n") + 1
    pos = 0
    while pos < koniec:
        nl = dane.index(b"\n", pos)
        linia, od = dane[pos:nl], p["od"] + pos
        pos = nl + 1
        if not linia.strip():
            continue
        if b'"role":"toolResult"' in linia[:400]:           # wynik narzędzia: id, rodzic i wywołanie, treści nie parsujemy
            ident = re.search(rb'"id":"([^"]+)"', linia[:400])
            rodzic = re.search(rb'"parentId":(null|"([^"]*)")', linia[:400])
            wyw = re.search(rb'"toolCallId":\s*"([^"]+)"', linia[:600])
            if wyw:
                p["wyniki"].setdefault(wyw.group(1).decode(), []).append(od)
            if ident:
                i = ident.group(1).decode()
                p["wpisy"][i] = ((rodzic.group(2) or b"").decode() or None if rodzic else None, None)
                p["lisc"] = i
            continue
        try:
            e = json.loads(linia)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        if e.get("type") == "session":
            if any(k not in e for k in SCHEMAT_WYMAGANY["session"]) or e.get("version") not in WERSJE:
                p["blad"] = "nieznany format"
                return p
            p["naglowek"] = {"id": e["id"], "parentSession": e.get("parentSession")}
            continue
        if "id" not in e or "type" not in e or "parentId" not in e:
            continue
        skrot = _skrot(e)
        p["wpisy"][e["id"]] = (e.get("parentId"), skrot)
        if skrot and skrot.get("kroki"):
            p["wywolania"][str(e["id"])] = od
            for k in skrot["kroki"]:                    # krok na żywo zna tylko id wywołania (ref `o:_:<id>`)
                p["wpis_wywolania"][k["id"]] = str(e["id"])
        m = e.get("message") if e.get("type") == "message" else None
        if isinstance(m, dict) and m.get("role") == "toolResult" and m.get("toolCallId"):
            p["wyniki"].setdefault(str(m["toolCallId"]), []).append(od)
        if skrot and skrot["typ"] == "asystent" and not skrot["kroki"] and not _z_panelu(p["wpisy"], e.get("parentId")):
            p["odpowiedzi"] += 1
        p["lisc"] = e["id"]
    p["od"] += koniec
    if p["naglowek"] is None and p["od"] > 0 and p["wpisy"]:
        p["blad"] = "nieznany format"
    return p


def _z_panelu(wpisy: dict, i: str | None) -> bool:
    """Tura zaczęła się wiadomością panelu (najbliższy wpis użytkownika w górę gałęzi niesie klucze przebiegów)."""
    widziane = set()
    while i and i not in widziane:
        widziane.add(i)
        rodzic, skrot = wpisy.get(i, (None, None))
        if skrot and skrot["typ"] == "uzytkownik":
            return bool(skrot.get("klucze"))
        i = rodzic
    return False


def odpowiedzi(plik: Path | str) -> int | None:
    """Licznik nieprzeczytanych rozmówcy omp: liczba odpowiedzi kończących turę w pliku (asystent z tekstem, bez
    wywołań narzędzi), z pominięciem tur z panelu (te liczy koniec przebiegu); None = pliku nie da się czytać.
    Kroki narzędzi, wyniki i tekst przy wywołaniu narzędzia licznika nie ruszają: jedna tura = jedna wiadomość."""
    try:
        p = _czytaj(Path(plik))
    except OSError:
        return None
    return None if p["blad"] else p["odpowiedzi"]


def _linia(plik: Path, od: int) -> dict | None:
    """Jeden wpis sesji spod offsetu (None = linia dłuższa niż LINIA_MAKS albo nie JSON)."""
    with plik.open("rb") as f:
        f.seek(od)
        surowa = f.readline(LINIA_MAKS + 1)
    if len(surowa) > LINIA_MAKS:
        return None
    try:
        e = json.loads(surowa)
    except ValueError:
        return None
    return e if isinstance(e, dict) else None


def _tekst_wyniku(tresc) -> str:
    if isinstance(tresc, str):
        return tresc
    czesci = []
    for c in tresc or []:
        if isinstance(c, dict) and c.get("type") == "text":
            czesci.append(str(c.get("text") or ""))
        elif isinstance(c, dict) and c.get("type") == "image":
            czesci.append("[obraz]")
    return "\n".join(czesci)


def _roznica_ms(od, do) -> int | None:
    from datetime import datetime
    try:
        a, b = (datetime.fromisoformat(str(v).replace("Z", "+00:00")) for v in (od, do))
    except (TypeError, ValueError):
        return None
    ms = round((b - a).total_seconds() * 1000)
    return ms if ms >= 0 else None


def szczegoly(plik: Path | str, wpis: str, wywolanie: str) -> dict | None:
    """Szczegóły kroku `wywolanie` z wpisu asystenta `wpis` (adres z osi: `wpis` i `id` kroku); None = nie ma takiego
    kroku w tym pliku albo pliku nie da się czytać. Wynik:

        {"narzedzie", "intencja", "argumenty": dict, "mysl": str, "wynik": str | None (jeszcze nie ma), "blad",
         "zmiana": diff edycji | None, "kod": kod wyjścia | None, "czas_ms": int | None}

    Krok z wynikiem trafia do małej pamięci (SZCZEGOLY_PAMIEC); zwrócony słownik tylko do odczytu. `wpis` = "_":
    wpis asystenta z indeksu wywołań (krok na żywo z ogona tury zna tylko id wywołania)."""
    plik = Path(plik)
    try:
        p = _czytaj(plik)
    except OSError:
        return None
    if wpis == "_":
        wpis = p["wpis_wywolania"].get(wywolanie, "")
    od = p["wywolania"].get(wpis)
    if p["blad"] or od is None:
        return None
    klucz = (str(plik), p["ino"], wpis, wywolanie)
    if klucz in _SZCZEGOLY:
        return _SZCZEGOLY[klucz]
    try:
        e = _linia(plik, od)
        if e is None or str(e.get("id")) != wpis:
            return None
        m = e.get("message") or {}
        mysl, c_wyw = [], None
        for c in m.get("content") or []:          # myśl i tekst od poprzedniego wywołania tej wiadomości
            if not isinstance(c, dict):
                continue
            if c.get("type") == "toolCall":
                if str(c.get("id") or "") == wywolanie:
                    c_wyw = c
                    break
                mysl = []
            elif c.get("type") == "thinking" and c.get("thinking"):
                mysl.append(str(c["thinking"]))
            elif c.get("type") == "text" and c.get("text"):
                mysl.append(str(c["text"]))
        if c_wyw is None:
            return None
        args = c_wyw.get("arguments")
        out = {"narzedzie": str(c_wyw.get("name") or "?"), "intencja": str(c_wyw.get("intent") or ""),
               "argumenty": args if isinstance(args, dict) else ({"argumenty": args} if args else {}),
               "mysl": "\n\n".join(mysl).strip(), "wynik": None, "blad": False, "zmiana": None, "kod": None,
               "czas_ms": None}
        od_w = next((o for o in p["wyniki"].get(wywolanie, ()) if o > od), None)
        if od_w is None:
            return out                            # krok w toku: wynik przyjdzie, bez pamięci
        r = _linia(plik, od_w)
    except OSError:
        return None
    if r is None:
        out["wynik"] = "[wynik za duży, żeby go pokazać]"
    else:
        rm = r.get("message") or {}
        det = rm.get("details") if isinstance(rm.get("details"), dict) else {}
        out["wynik"] = _tekst_wyniku(rm.get("content"))
        out["blad"] = bool(rm.get("isError"))
        if isinstance(det.get("diff"), str):
            out["zmiana"] = det["diff"]
        if isinstance(det.get("exitCode"), int):
            out["kod"] = det["exitCode"]
        czas = det.get("wallTimeMs")
        out["czas_ms"] = int(czas) if isinstance(czas, (int, float)) else _roznica_ms(e.get("timestamp"),
                                                                                      r.get("timestamp"))
    if len(_SZCZEGOLY) >= SZCZEGOLY_PAMIEC:
        _SZCZEGOLY.pop(next(iter(_SZCZEGOLY)))
    _SZCZEGOLY[klucz] = out
    return out


def os_sesji(plik: Path | str | None, ostatnie: int = 200) -> dict:
    wynik = {"wpisy": [], "pelny": False, "sesja": None, "blad": None}
    if not plik:
        return {**wynik, "blad": "brak pliku sesji"}
    try:
        p = _czytaj(Path(plik))
    except OSError:
        return {**wynik, "blad": "brak pliku sesji"}
    if p["blad"]:
        return {**wynik, "blad": p["blad"]}
    galaz, i, widziane = [], p["lisc"], set()
    while i and i not in widziane and len(galaz) < ostatnie * 4:
        widziane.add(i)
        rodzic, skrot = p["wpisy"].get(i, (None, None))
        if skrot:
            galaz.append({"id": i, **skrot})
        i = rodzic
    galaz.reverse()
    wpisy: list[dict] = []
    for w in galaz:                               # kompresja: narzędzia pod rząd → jeden wpis „kroki”
        kroki = list(w.pop("kroki", []))         # kopia: lista w pamięci czytnika zostaje nietknięta
        if w["typ"] == "asystent":
            wpisy.append(w)
            if kroki:
                wpisy.append({"id": w["id"] + ":k", "czas": w["czas"], "typ": "kroki", "kroki": kroki})
        elif w["typ"] == "kroki" and wpisy and wpisy[-1]["typ"] == "kroki":
            wpisy[-1]["kroki"].extend(kroki)
        elif w["typ"] == "kroki":
            wpisy.append({**w, "kroki": kroki})
        else:
            wpisy.append(w)
    n = p["naglowek"] or {}
    return {**wynik, "wpisy": wpisy[-ostatnie:], "pelny": bool(n.get("parentSession")), "sesja": n.get("id")}


def zapomnij(plik: Path | str | None = None) -> None:
    """Czyści pamięć czytnika (testy, zmiana pliku sesji wpisu)."""
    if plik is None:
        _PAMIEC.clear()
        _SZCZEGOLY.clear()
    else:
        _PAMIEC.pop(str(plik), None)
        _PAMIEC.pop(os.fspath(plik), None)
        for k in [k for k in _SZCZEGOLY if k[0] in (str(plik), os.fspath(plik))]:
            _SZCZEGOLY.pop(k, None)
