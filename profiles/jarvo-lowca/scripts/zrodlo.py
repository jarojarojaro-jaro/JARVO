#!/usr/bin/env python3
"""Rozpoznanie nowego publicznego źródła danych, zanim powstanie skrypt (skill `rozpoznanie-zrodla`, 0 tokenów).

    zrodlo.py nagraj <url> -o a.har [--czekaj 3] [--przewin]   # ruch strony w przeglądarce (bez obrazków i fontów)
    zrodlo.py har a.har [--json]                               # żądania z danymi: metoda, ścieżka, parametry, kształt
                                                               # odpowiedzi, nagłówki do pobierania przyrostowego
                                                               # (ETag, Last-Modified), zależności, dane ukryte w HTML
    zrodlo.py roznice a.har b.har [--json]                     # nagrania różniące się JEDNĄ rzeczą (strona 2, inna
                                                               # fraza, filtr): co się zmieniło w parametrach, ciele,
                                                               # odpowiedzi; nowe i zniknięte żądania
    zrodlo.py schemat <plik.json|plik.har|katalog>… [--zadanie /v1/szukaj] [--json]
                                                               # schemat jednego żądania z 20–30 różnych odpowiedzi:
                                                               # typy, pola opcjonalne, null, niespójne typy, przykłady

Po co: zrozumieć model zapytań źródła (parametry, paginacja, kolejność wywołań) i pełny kształt danych, zanim
napiszemy skrypt, zamiast klikać stronę w przeglądarce przy każdym przebiegu. Ekstraktor zbudowany na pierwszych
100 rekordach potrafi po cichu gubić pola, które pojawiają się dalej: schemat sumy to pokazuje.

Granice jak w całym Łowcy: tylko strony publiczne bez logowania, `robots.txt` (nagraj sprawdza), uczciwy User-Agent,
odmowa albo ochrona antybotowa = blokada (kod 3). Najpierw oficjalne API i dokumentacja źródła; regulamin i prawo do
bazy danych (pobieranie istotnej części cudzej bazy) ocenia człowiek przed pierwszym przebiegiem.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import signal
import subprocess
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lowca_lib as ll  # noqa: E402
import strona  # noqa: E402

STATYCZNE = re.compile(r"\.(?:js|mjs|css|png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf|otf|mp4|webm|mp3|map)$", re.I)
ANALITYKA = re.compile(r"google-analytics|googletagmanager|doubleclick|facebook\.(?:com|net)/tr|connect\.facebook|hotjar|"
                       r"clarity\.ms|sentry|segment\.(?:io|com)|mixpanel|analytics\.tiktok|px\.ads\.linkedin|bat\.bing|"
                       r"cookiebot|cookieyes|onetrust|pinterest\.com/(?:v3|user)|analytics\.twitter|ads-twitter|snapchat\.com|"
                       r"reddit\.com/rp|hs-analytics|track\.hubspot|plausible\.io|matomo|criteo|taboola", re.I)
# piksele i telemetria spoza listy: ścieżka mówi sama za siebie
SLEDZENIE = re.compile(r"(?:^|[/_.-])(?:pixel|track|tracking|collect|beacon|telemetry)(?:[/_.-]|$)", re.I)
PRZYROST = ("etag", "last-modified", "cache-control", "expires", "x-total-count", "link")
MALO_PROBEK = 20


# ------------------------------------------------------------------ HAR

def wczytaj_har(plik: str | Path) -> list[dict]:
    return json.loads(Path(plik).read_text(encoding="utf-8"))["log"]["entries"]


def tresc(content: dict) -> str:
    t = content.get("text") or ""
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(t).decode("utf-8", "replace")
        except ValueError:
            return ""
    return t


def _json(tekst: str | None):
    try:
        return json.loads(tekst) if tekst else None
    except ValueError:
        return None


def cialo_zadania(req: dict):
    pd = req.get("postData") or {}
    t = pd.get("text") or ""
    if (j := _json(t)) is not None:
        return j
    if pd.get("params"):
        return {p["name"]: p.get("value") for p in pd["params"]}
    if "form" in (pd.get("mimeType") or "") and "=" in t:
        return dict(urllib.parse.parse_qsl(t, keep_blank_values=True))
    return t or None


def szablon(url: str) -> str:
    """Host i ścieżka z identyfikatorami zamienionymi na {id}: klucz do parowania żądań między nagraniami."""
    u = urllib.parse.urlsplit(url)
    czesci = ["{id}" if re.fullmatch(r"\d+|[0-9a-f]{8,}(?:-[0-9a-f]{4,})*", s, re.I) else s for s in u.path.split("/")]
    return u.netloc + "/".join(czesci)


def czy_dane(e: dict) -> bool:
    url = e["request"]["url"]
    typ = (e["response"].get("content") or {}).get("mimeType", "")
    sciezka = urllib.parse.urlsplit(url).path
    if ANALITYKA.search(url) or SLEDZENIE.search(sciezka) or STATYCZNE.search(sciezka) or not url.startswith("http"):
        return False
    if typ.startswith(("image/", "font/", "video/", "audio/")):
        return False
    return e.get("_resourceType") in ("xhr", "fetch") or "json" in typ or "graphql" in url.lower()


def ksztalt(v, gl: int = 0) -> str:
    """Krótki opis struktury: {items: [20× {…}], total: liczba}."""
    if isinstance(v, dict):
        if gl >= 2:
            return "{…}"
        pola = [f"{k}: {ksztalt(x, gl + 1)}" for k, x in list(v.items())[:8]]
        return "{" + ", ".join(pola) + (", …" if len(v) > 8 else "") + "}"
    if isinstance(v, list):
        return f"[{len(v)}× {ksztalt(v[0], gl) if v else '–'}]"
    return nazwa_typu(v)


def nazwa_typu(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "logiczna"
    if isinstance(v, (int, float)):
        return "liczba"
    if isinstance(v, str):
        return "tekst"
    return "lista" if isinstance(v, list) else "obiekt"


def wpis(e: dict) -> dict:
    req, res = e["request"], e["response"]
    content = res.get("content") or {}
    cialo = tresc(content)
    j = _json(cialo)
    h = {x["name"].lower(): x["value"] for x in res.get("headers") or []}
    return {"metoda": req["method"], "url": req["url"], "szablon": szablon(req["url"]),
            "parametry": dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(req["url"]).query, keep_blank_values=True)),
            "cialo": cialo_zadania(req), "status": res.get("status"), "typ": content.get("mimeType", ""),
            "rozmiar": content.get("size") or len(cialo), "przyrostowo": {k: h[k] for k in PRZYROST if k in h},
            "odpowiedz": ksztalt(j) if j is not None else None, "_json": j, "_tekst": cialo}


def _wartosci(v, sciezka: str = "") -> dict[str, str]:
    """Płaskie pary ścieżka → wartość (skalary)."""
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            out.update(_wartosci(x, f"{sciezka}.{k}" if sciezka else str(k)))
        return out
    if isinstance(v, list):
        out = {}
        for i, x in enumerate(v[:50]):
            out.update(_wartosci(x, f"{sciezka}[{i}]"))
        return out
    return {sciezka: v} if sciezka else {}


def zaleznosci(wpisy: list[dict]) -> list[dict]:
    """Parametr albo pole ciała żądania, którego wartość pojawiła się wcześniej w odpowiedzi innego żądania
    (token, identyfikator, kursor strony): kolejność wywołań, której skrypt musi przestrzegać. Wartość, którą
    wcześniej wysłało samo żądanie, a serwer tylko odbił w odpowiedzi (meta.params), zależnością nie jest."""
    out, wyslane = [], set()
    for i, w in enumerate(wpisy):
        wej = {**{f"?{k}": v for k, v in w["parametry"].items()}, **_wartosci(w["cialo"] if isinstance(w["cialo"], dict) else {})}
        for k, v in wej.items():
            s = str(v)
            if len(s) < 6 or s in wyslane:                  # numer strony, „true”, krótka fraza, odbite parametry
                continue
            for wcz in wpisy[:i]:
                if wcz["_tekst"] and re.search(r"(?<![\w-])" + re.escape(s) + r"(?![\w-])", wcz["_tekst"]):
                    out.append({"zadanie": f"{w['metoda']} {w['szablon']}", "pole": k, "z_odpowiedzi": f"{wcz['metoda']} {wcz['szablon']}"})
                    break
        wyslane.update(str(v) for v in wej.values())
    return out


def analiza_har(plik: str | Path) -> dict:
    wpisy_all = wczytaj_har(plik)
    dokumenty = []
    for e in wpisy_all:
        typ = (e["response"].get("content") or {}).get("mimeType", "")
        if (e.get("_resourceType") == "document" or "text/html" in typ) and e["response"].get("status") == 200:
            html = tresc(e["response"].get("content") or {})
            ladunki = [{"skad": s, "kB": round(len(json.dumps(d, ensure_ascii=False) if not isinstance(d, str) else d) / 1024, 1)}
                       for s, d in strona.ladunki(html)]
            dokumenty.append({"url": e["request"]["url"], "ukryte": ladunki})
    dane = [wpis(e) for e in wpisy_all if czy_dane(e)]
    odmowy = [f"{w['metoda']} {w['url']} → {w['status']}" for w in dane if w["status"] in (401, 403, 429, 503)]
    return {"plik": str(plik), "zadan": len(wpisy_all), "dokumenty": dokumenty, "dane": dane, "zaleznosci": zaleznosci(dane),
            "odmowy": odmowy}


# ------------------------------------------------------------------ różnice

def _porownaj(a: dict, b: dict) -> dict:
    zmienione = {k: [a[k], b[k]] for k in a if k in b and a[k] != b[k]}
    return {"zmienione": zmienione, "tylko_a": {k: a[k] for k in a if k not in b}, "tylko_b": {k: b[k] for k in b if k not in a}}


def _grupy(dane: list[dict]) -> dict[tuple, list[dict]]:
    g: dict[tuple, list[dict]] = {}
    for w in dane:
        g.setdefault((w["metoda"], w["szablon"]), []).append(w)
    return g


def roznice(plik_a: str | Path, plik_b: str | Path) -> dict:
    A, B = analiza_har(plik_a)["dane"], analiza_har(plik_b)["dane"]
    ga, gb = _grupy(A), _grupy(B)
    pary = []
    for klucz in [k for k in ga if k in gb]:
        for nr, (wa, wb) in enumerate(_paruj(ga[klucz], gb[klucz]), 1):
            par = _porownaj(wa["parametry"], wb["parametry"])
            ciala = _porownaj(_wartosci(wa["cialo"]) if isinstance(wa["cialo"], (dict, list)) else {},
                              _wartosci(wb["cialo"]) if isinstance(wb["cialo"], (dict, list)) else {})
            ra, rb = _wartosci(wa["_json"]), _wartosci(wb["_json"])
            wspolne = [k for k in ra if k in rb]
            zmiana = sum(ra[k] != rb[k] for k in wspolne)
            if not (par["zmienione"] or par["tylko_a"] or par["tylko_b"] or ciala["zmienione"] or ciala["tylko_a"]
                    or ciala["tylko_b"] or wa["odpowiedz"] != wb["odpowiedz"] or zmiana):
                continue
            wiele = f" ({nr}. wywołanie)" if len(ga[klucz]) > 1 else ""
            pary.append({"zadanie": f"{klucz[0]} {klucz[1]}{wiele}", "parametry": par, "cialo": ciala,
                         "odpowiedz": {"a": wa["odpowiedz"], "b": wb["odpowiedz"],
                                       "zmienione_pola": f"{zmiana} z {len(wspolne)}" if wspolne else "–"}})
    return {"pary": pary, "tylko_a": [f"{m} {s}" for (m, s) in ga if (m, s) not in gb],
            "tylko_b": [f"{m} {s}" for (m, s) in gb if (m, s) not in ga],
            "kolejnosc_a": _kolejnosc(A), "kolejnosc_b": _kolejnosc(B)}


def _paruj(la: list[dict], lb: list[dict]) -> list[tuple[dict, dict]]:
    """To samo żądanie kilka razy w nagraniu (np. liczniki i lista wyników): para z najbliższymi parametrami,
    nie po kolejności, żeby nie porównywać licznika z listą."""
    wolne, out = list(lb), []
    for wa in la:
        if not wolne:
            break
        def odl(wb, wa=wa):
            p = _porownaj(wa["parametry"], wb["parametry"])
            return len(p["zmienione"]) + len(p["tylko_a"]) + len(p["tylko_b"])
        wb = min(wolne, key=odl)
        wolne.remove(wb)
        out.append((wa, wb))
    return out


def _kolejnosc(dane: list[dict]) -> list[str]:
    return list(dict.fromkeys(f"{w['metoda']} {w['szablon']}" for w in dane))


# ------------------------------------------------------------------ schemat

PLIKI_JSON = "pliki JSON"


def dokumenty_json(zrodla: list[str], zadanie: str | None = None) -> dict[str, list]:
    """Odpowiedzi pogrupowane po żądaniu („GET host/ścieżka/{id}”); pliki .json to jedna grupa. Schemat ma sens dla
    jednego żądania: suma tłumaczeń, CMS i listy firm niczego nie mówi."""
    out: dict[str, list] = {}
    for z in zrodla:
        p = Path(z)
        pliki = sorted(p.rglob("*.json")) + sorted(p.rglob("*.har")) if p.is_dir() else [p]
        for f in pliki:
            if f.suffix == ".har":
                for w in analiza_har(f)["dane"]:
                    if w["_json"] is not None:
                        out.setdefault(f"{w['metoda']} {w['szablon']}", []).append(w["_json"])
            elif (j := _json(f.read_text(encoding="utf-8", errors="replace"))) is not None:
                out.setdefault(PLIKI_JSON, []).append(j)
    if zadanie:
        out = {k: v for k, v in out.items() if zadanie.lower() in k.lower()}
    return dict(sorted(out.items(), key=lambda kv: -len(kv[1])))


def schemat_zrodel(zrodla: list[str], zadanie: str | None = None) -> dict:
    """Jedna grupa = pełny schemat; kilka = lista żądań do wyboru (`--zadanie <fragment ścieżki>`)."""
    grupy = dokumenty_json(zrodla, zadanie)
    if len(grupy) == 1:
        (k, docs), = grupy.items()
        return {"zadanie": k, **schemat(docs)}
    return {"zadania": [{"zadanie": k, "odpowiedzi": len(v)} for k, v in grupy.items()],
            "uwaga": "wybierz jedno żądanie: --zadanie <fragment>, np. ścieżka listy wyników" if grupy
            else "brak odpowiedzi JSON" + (f" dla „{zadanie}”" if zadanie else "")}


def _przyklad(v) -> str:
    s = re.sub(ll.EMAIL_RE, "<e-mail>", str(v))
    return re.sub(r"(?<![\d-])(?!\d{4}-\d\d-\d\d)\+?\d[\d\s-]{7,}\d", "<numer>", s)[:40]   # daty zostają


def schemat(dokumenty: list) -> dict:
    obiekty, obecne, typy, przyklady = Counter(), Counter(), {}, {}

    def idz(v, sciezka: str) -> None:
        typy.setdefault(sciezka, Counter())[nazwa_typu(v)] += 1
        if isinstance(v, dict):
            obiekty[sciezka] += 1
            for k, x in v.items():
                obecne[f"{sciezka}.{k}"] += 1
                idz(x, f"{sciezka}.{k}")
        elif isinstance(v, list):
            for x in v:
                idz(x, sciezka + "[]")
        elif v is not None:
            p = przyklady.setdefault(sciezka, [])
            if (s := _przyklad(v)) not in p and len(p) < 3:
                p.append(s)

    for d in dokumenty:
        idz(d, "$")
    pola = []
    for sciezka, t in typy.items():
        if sciezka == "$":
            continue
        klucz = not sciezka.endswith("[]")
        rodzic = sciezka.rsplit(".", 1)[0] if klucz else None
        ile = sum(t.values())
        niepuste = [n for n in t if n != "null"]
        pola.append({"sciezka": sciezka, "typy": dict(t), "obecne": obecne[sciezka] if klucz else ile,
                     "obiektow": obiekty[rodzic] if klucz else ile,
                     "opcjonalne": bool(klucz and obecne[sciezka] < obiekty[rodzic]),
                     "null_proc": round(100 * t.get("null", 0) / ile) if ile else 0,
                     "niespojne": len(niepuste) > 1, "przyklady": przyklady.get(sciezka, [])})
    pola.sort(key=lambda p: p["sciezka"])
    return {"dokumentow": len(dokumenty), "pola": pola,
            "podsumowanie": {"pol": len(pola), "opcjonalnych": sum(p["opcjonalne"] for p in pola),
                             "z_null": sum(p["null_proc"] > 0 for p in pola), "niespojnych": sum(p["niespojne"] for p in pola)},
            "uwaga": (f"mało próbek ({len(dokumenty)}): zbierz {MALO_PROBEK}–30 różnych odpowiedzi (inne frazy, filtry, "
                      "typy rekordów, dalsze strony)") if len(dokumenty) < MALO_PROBEK else None}


# ------------------------------------------------------------------ nagrywanie

def nagraj(url: str, wyjscie: str, czekaj: float = 3.0, przewin: bool = False) -> int:
    if "://" not in url:
        url = "https://" + url
    if not strona.robots(url).can_fetch(ll.UA, url):
        print(f"✗ {url}: robots.txt nie pozwala (User-Agent jarvo-lowca); to granica, nie zagadka", file=sys.stderr)
        return 3
    Path(wyjscie).parent.mkdir(parents=True, exist_ok=True)
    polecenie = ["node", str(Path(__file__).with_name("har.cjs")), url, wyjscie, "--czekaj", str(int(czekaj * 1000))]
    return subprocess.run(polecenie + (["--przewin"] if przewin else []), env={**os.environ, "JARVO_UA": ll.UA}).returncode


# ------------------------------------------------------------------ wydruk

def _bez_prywatnych(x):
    if isinstance(x, dict):
        return {k: _bez_prywatnych(v) for k, v in x.items() if not k.startswith("_")}
    if isinstance(x, list):
        return [_bez_prywatnych(v) for v in x]
    return x


def drukuj_har(a: dict) -> None:
    print(f"{a['plik']}: {a['zadan']} żądań, z danymi: {len(a['dane'])}")
    for d in a["dokumenty"]:
        if d["ukryte"]:
            print(f"  dokument {d['url']}: dane ukryte w HTML: " + ", ".join(f"{u['skad']} {u['kB']} kB" for u in d["ukryte"]))
    for w in a["dane"]:
        par = ", ".join(f"{k}={v}"[:40] for k, v in w["parametry"].items())
        cialo = ", ".join(list(w["cialo"])[:8]) if isinstance(w["cialo"], dict) else ("tekst" if w["cialo"] else "")
        print(f"  {w['metoda']} {w['szablon']}" + (f" ?{par}" if par else "") + (f" · ciało: {cialo}" if cialo else ""))
        print(f"      {w['status']} {w['typ']} {round((w['rozmiar'] or 0) / 1024, 1)} kB · {w['odpowiedz'] or '(nie JSON)'}")
        if w["przyrostowo"]:
            print("      przyrostowo: " + ", ".join(f"{k}: {v}"[:60] for k, v in w["przyrostowo"].items()))
    for z in a["zaleznosci"]:
        print(f"  zależność: {z['zadanie']} bierze {z['pole']} z odpowiedzi {z['z_odpowiedzi']}")
    for o in a["odmowy"]:
        print(f"  ✗ odmowa: {o} (blokada: nie obchodzimy)")


def drukuj_roznice(r: dict) -> None:
    if not (r["pary"] or r["tylko_a"] or r["tylko_b"]):
        print("bez różnic w żądaniach z danymi")
    for p in r["pary"]:
        print(p["zadanie"])
        for co, d in (("parametr", p["parametry"]), ("ciało", p["cialo"])):
            for k, (va, vb) in d["zmienione"].items():
                print(f"  {co} {k}: {va} → {vb}")
            for k, v in d["tylko_a"].items():
                print(f"  {co} {k}: tylko w A ({v})")
            for k, v in d["tylko_b"].items():
                print(f"  {co} {k}: tylko w B ({v})")
        o = p["odpowiedz"]
        print(f"  odpowiedź: {o['a']}" + (f" → {o['b']}" if o["a"] != o["b"] else "") + f"; zmienione wartości: {o['zmienione_pola']}")
    for s in r["tylko_a"]:
        print(f"tylko w A: {s}")
    for s in r["tylko_b"]:
        print(f"tylko w B: {s}")
    if r["kolejnosc_a"] != r["kolejnosc_b"]:
        print("kolejność A: " + " → ".join(r["kolejnosc_a"]))
        print("kolejność B: " + " → ".join(r["kolejnosc_b"]))


def drukuj_schemat(s: dict) -> None:
    if "zadania" in s:
        for z in s["zadania"]:
            print(f"  {z['odpowiedzi']:>3}× {z['zadanie']}")
        print(f"! {s['uwaga']}")
        return
    p = s["podsumowanie"]
    print(f"{s['zadanie']}: dokumentów: {s['dokumentow']}, pól: {p['pol']}, opcjonalnych: {p['opcjonalnych']}, z null: {p['z_null']}, "
          f"niespójnych typów: {p['niespojnych']}")
    if s["uwaga"]:
        print(f"  ! {s['uwaga']}")
    for f in s["pola"]:
        typy = "/".join(f"{t} {n}" for t, n in f["typy"].items())
        znaki = [f"OPCJONALNE ({f['obecne']}/{f['obiektow']})" if f["opcjonalne"] else "",
                 f"NULL {f['null_proc']}%" if f["null_proc"] else "", "NIESPÓJNE TYPY" if f["niespojne"] else ""]
        print(f"  {f['sciezka']}: {typy}" + "".join(f" · {z}" for z in znaki if z)
              + (f" · np. {', '.join(repr(x) for x in f['przyklady'])}" if f["przyklady"] else ""))


def main(argv: list[str] | None = None) -> int:
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)       # `zrodlo.py har … | head` bez BrokenPipeError
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("nagraj")
    s.add_argument("url")
    s.add_argument("-o", "--wyjscie", required=True)
    s.add_argument("--czekaj", type=float, default=3.0, help="sekundy po załadowaniu (doładowania, leniwe listy)")
    s.add_argument("--przewin", action="store_true", help="przewiń stronę (listy doładowywane przy przewijaniu)")
    s = sub.add_parser("har")
    s.add_argument("plik")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("roznice")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("schemat")
    s.add_argument("zrodla", nargs="+")
    s.add_argument("--zadanie", help="fragment żądania z `har`, np. /v1/szukaj (gdy nagranie ma kilka)")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "nagraj":
        return nagraj(a.url, a.wyjscie, a.czekaj, a.przewin)
    wynik = analiza_har(a.plik) if a.cmd == "har" else roznice(a.a, a.b) if a.cmd == "roznice" else schemat_zrodel(a.zrodla, a.zadanie)
    if a.json:
        print(json.dumps(_bez_prywatnych(wynik), ensure_ascii=False, indent=1))
    else:
        {"har": drukuj_har, "roznice": drukuj_roznice, "schemat": drukuj_schemat}[a.cmd](wynik)
    if a.cmd == "har" and wynik["odmowy"]:
        return 3
    return 1 if a.cmd == "schemat" and not wynik.get("zadania", True) else 0


if __name__ == "__main__":
    sys.exit(main())
