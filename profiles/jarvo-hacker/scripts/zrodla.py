#!/usr/bin/env python3
"""Codzienne źródła radaru Hackera: pobiera agregatory hackathonów i konkursów, łączy powtórki, porównuje z bazą
i wypisuje, co jest do sprawdzenia (online albo hybryda, spoza bazy, pula od progu).

    zrodla.py [--katalog out] [--min-pula 5000]

Źródła (publiczne, bez logowania, jeden odczyt dziennie, kopia w `<katalog>/.zrodla/`): DevGrants Daily (`/all/`,
karty hackathon i bounty), HackList (`/api/opportunities`), Hackathon Hub (`/llms-full.txt`), BuildJams (RSS),
advance.to (RSS, kategoria konkursów), make.fun (`/api/competitions`). Granty, akceleratory i stypendia pomija
(to Bigshort). Wynik: `<katalog>/ZRODLA.md` i `<katalog>/zrodla.json`, a na wyjściu te same liczby i lista.
Pula w USD jest przybliżona (kursy stałe, do progu); termin z agregatora bywa terminem wejścia albo datą wydarzenia,
termin zgłoszenia zawsze ze strony zasad. Skrypt niczego nie dopisuje do bazy.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sqlite3
import sys
import unicodedata
import urllib.request
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hackatony  # noqa: E402

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
KURS = {"$": 1.0, "US$": 1.0, "USD": 1.0, "USDT": 1.0, "USDC": 1.0, "€": 1.08, "EUR": 1.08, "£": 1.27, "GBP": 1.27,
        "PLN": 0.25, "ZŁ": 0.25, "₹": 0.012, "INR": 0.012}
WALUTA = r"US\$|\$|€|£|₹|USDT|USDC|USD|EUR|GBP|PLN|zł|INR"
MNOZNIK = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mln": 1e6, "million": 1e6}
KWOTA = re.compile(rf"(?P<w1>{WALUTA})\s?(?P<l1>\d[\d,.]*)\s?(?P<m1>k|m|mln|million|thousand)?\b"
                   rf"|(?P<l2>\d[\d,.]*)\s?(?P<m2>k|m|mln|million|thousand)?\s?(?P<w2>{WALUTA})(?![A-Za-z])", re.I)
MIESIACE = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
AI = re.compile(r"\b(ai|llms?|agents?|agentic|gpt|gemini|claude|genai|generative|machine learning|ml|rag|"
                r"deep learning|neural|kaggle)\b", re.I)
POMIJANE = {"hackathon", "hackathons", "hack", "the", "a", "an", "of", "and", "for", "on", "in", "with", "to", "by", "x",
            "edition", "global", "ai", "agent", "agents", "build", "builder", "challenge", "competition", "contest", "jam",
            "game", "online", "open", "program", "prize", "prizes", "cash", "usd", "usdt", "usdc", "up", "season", "k", "m",
            "bug", "bounty", "bounties", "reward", "rewards", "security", "contract", "contracts", "immunefi",
            "sherlock", "hackerone", "cantina", "hackenproof", "bugcrowd", "intigriti", "yeswehack", "kaggle", "devpost",
            "dorahacks", "unstop", "lablab"}
OGOLNE_NA_POCZATKU = {"one", "new", "first", "best", "your", "our", "my", "world", "international", "national", "european",
                      "student", "students", "university", "community", "creative", "future", "data", "web", "code",
                      "dev", "developer", "developers", "tech", "health", "healthcare", "climate", "green", "smart",
                      "digital", "cyber", "space", "robot", "robotics", "machine", "deep", "quantum", "crypto",
                      "blockchain", "defi", "summer", "winter", "spring", "autumn", "fall", "hacking", "make",
                      "sum", "promote", "roast", "funniest", "most", "all", "how", "what", "why", "google", "microsoft",
                      "apple", "amazon", "aws", "meta", "openai", "nvidia", "solana", "base", "ethereum", "create",
                      "lovable", "cursor", "start", "big", "claude", "codex", "grok", "day", "physical", "dawn", "build"}


def pobierz(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "ignore")


def tekst(s: str) -> str:
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def liczba(s: str) -> float | None:
    s = s.rstrip(".,")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if len(s.split(",")[-1]) == 3 else s.replace(",", ".")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[-1]) == 3):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def pula_usd(s: str) -> int | None:
    """Największa kwota z walutą w tekście, w USD; linki i daty nie są kwotami."""
    s = re.sub(r"https?://\S+|\b\d{4}-\d{2}-\d{2}\b", " ", s or "")
    best = None
    for m in KWOTA.finditer(s):
        v = liczba(m["l1"] or m["l2"])
        if v is None:
            continue
        v *= MNOZNIK.get((m["m1"] or m["m2"] or "").lower(), 1) * KURS[(m["w1"] or m["w2"]).upper()]
        best = max(best or 0, int(v))
    return best


def data(s: str) -> str | None:
    """Ostatnia data w tekście jako RRRR-MM-DD (ISO, „25 Nov 2026”, „Nov 25, 2026”)."""
    s = s or ""
    iso = re.findall(r"\b(\d{4})-(\d{2})-(\d{2})", s)
    if iso:
        return "-".join(iso[-1])
    for d, m, r in reversed(re.findall(r"\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?,?\s+(\d{4})", s)):
        if m.lower() in MIESIACE:
            return f"{r}-{MIESIACE[m.lower()]:02d}-{int(d):02d}"
    for m, d, r in reversed(re.findall(r"\b([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s)):
        if m.lower() in MIESIACE:
            return f"{r}-{MIESIACE[m.lower()]:02d}-{int(d):02d}"
    return None


def tryb(s: str) -> str:
    s = (s or "").lower()
    if "hybrid" in s:
        return "hybryda"
    if re.search(r"in[- ]person|onsite|on-site|offline", s):
        return "na miejscu"
    if re.search(r"online|remote|virtual", s):
        return "online"
    return "?"


def pozycja(nazwa: str, link: str, zrodlo: str, typ: str, pula: str, termin: str | None, tryb_: str, opis: str) -> dict:
    return {"nazwa": nazwa.strip(), "link": link, "zrodla": [zrodlo], "typ": typ, "pula_tekst": pula.strip(),
            "pula_usd": pula_usd(pula), "termin": termin, "tryb": tryb_, "ai": bool(AI.search(f"{nazwa} {opis}"))}


def dgd(h: str) -> list[dict]:
    out = []
    for href, typ, body in re.findall(r'<a class="card" href="(/items/[^"]+)"[^>]*data-type="([^"]*)"[^>]*>(.*?)</a>', h, re.S):
        if typ not in ("hackathon", "bounty"):
            continue
        fakty = {tekst(k): tekst(v) for k, v in re.findall(r'fact__label">(.*?)</span><span class="fact__value">(.*?)</span>', body, re.S)}
        tytul = re.search(r'card__title">(.*?)</h3>', body, re.S)
        opis = tekst((re.search(r'card__summary">(.*?)</p>', body, re.S) or [None, ""])[1])
        out.append(pozycja(tekst(tytul[1]) if tytul else href, "https://devgrantsdaily.com" + href, "DevGrants Daily", typ,
                           fakty.get("Amount", ""), data(fakty.get("Deadline", "")), tryb(opis), opis))
    return out


def hacklist(x: str) -> list[dict]:
    d = json.loads(x)
    return [pozycja(i.get("title") or "", i.get("apply_url") or i.get("url") or "", "HackList", i["type"],
                    i.get("prize") or "", data(i.get("deadline") or i.get("deadline_text") or ""), tryb(i.get("format") or ""),
                    f"{i.get('category') or ''} {i.get('description') or ''}")
            for i in d.get("items", []) if i.get("type") in ("hackathon", "bounty")]


def hackathonhub(x: str) -> list[dict]:
    out = []
    for blok in re.split(r"\n(?=## )", x):
        if not blok.startswith("## "):
            continue
        pola = {k.lower(): v.strip() for k, v in re.findall(r"- \*\*(.+?):\*\*\s*(.+)", blok)}
        if pola.get("type") not in ("hackathon", "competition", "challenge"):
            continue
        out.append(pozycja(blok.split("\n", 1)[0][3:], pola.get("url", ""), "Hackathon Hub", pola["type"], pola.get("prize", ""),
                           data(pola.get("date", "")), tryb(pola.get("format", "")), f"{pola.get('tags', '')} {blok[:600]}"))
    return out


def rss(x: str, zrodlo: str, kategoria: str | None = None) -> list[dict]:
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        pole = lambda t: tekst((re.search(rf"<{t}[^>]*>(.*?)</{t}>", it, re.S) or [None, ""])[1])  # noqa: E731
        if kategoria and kategoria not in pole("category"):
            continue
        opis = pole("description")
        nagrody = re.search(r"Prizes?:\s*([^.]*(?:\.\d[^.]*)*)", opis)
        zamyka = re.search(r"(?:Closes?|Deadline)[:\s]+(.+)", opis)
        nazwa = re.sub(r"\s*·\s*deadline.*$", "", pole("title"), flags=re.I)
        out.append(pozycja(nazwa, pole("link"), zrodlo, "hackathon" if zrodlo == "BuildJams" else "konkurs",
                           nagrody[1] if nagrody else opis, data(zamyka[1]) if zamyka else None, tryb(opis), opis))
    return out


def makefun(x: str) -> list[dict]:
    return [pozycja(i.get("title") or "", "https://make.fun" + (i.get("url") or ""), "make.fun", "konkurs",
                    f"${i['rewardAmount']}" if i.get("rewardAmount") else "", data(i.get("deadline") or ""), "online",
                    f"{i.get('category') or ''} {i.get('description') or ''}")
            for i in json.loads(x).get("items", [])]


ZRODLA: dict[str, tuple[str, Callable[[str], list[dict]]]] = {
    "DevGrants Daily": ("https://devgrantsdaily.com/all/", dgd),
    "HackList": ("https://hacklist.io/api/opportunities", hacklist),
    "Hackathon Hub": ("https://hackathonhub.eu/llms-full.txt", hackathonhub),
    "BuildJams": ("https://jams.shippedby.app/feed.xml", lambda x: rss(x, "BuildJams")),
    "advance.to": ("https://advance.to/feed.xml", lambda x: rss(x, "advance.to", "Competitions")),
    "make.fun": ("https://make.fun/api/competitions?status=open", makefun),
}


def tokeny(nazwa: str) -> tuple[str, ...]:
    """Znaczące słowa nazwy w kolejności (bez lat, liczb i słów, które ma prawie każdy konkurs)."""
    t = unicodedata.normalize("NFKD", nazwa.lower().replace("ł", "l")).encode("ascii", "ignore").decode()
    return tuple(dict.fromkeys(s for s in re.findall(r"[a-z0-9]+", t) if not s.isdigit() and s not in POMIJANE))


def podobne(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    """Ta sama okazja: krótsza nazwa prawie cała w dłuższej („Pi Next Hackathon (Pi Network)” = „Pi Next Hackathon
    2026: 200,000 USDT for apps on Pi”) albo krótka nazwa to marka z początku dłuższej („QNX Global Hackathon” =
    „QNX Global Hackathon 2026”, „Kiroween 2026” = „Kiroween 2026: Kiro hackathon”)."""
    if not a or not b:
        return False
    wspolne, krotsza = set(a) & set(b), min(len(a), len(b))
    if len(wspolne) >= 2 and len(wspolne) / krotsza >= 0.6:
        return True
    return (krotsza <= 2 and len(wspolne) / krotsza >= 0.5 and a[0] == b[0] and len(a[0]) >= 3
            and a[0] not in OGOLNE_NA_POCZATKU)


def scal(pozycje: list[dict]) -> list[dict]:
    """Ta sama okazja z kilku źródeł = jeden wiersz (źródła razem, największa znana pula, najwcześniejszy termin);
    nazwę porównuje z każdą nazwą, pod którą wiersz już wystąpił."""
    wynik: list[dict] = []
    for p in pozycje:
        t = tokeny(p["nazwa"])
        jest = next((w for w in wynik if any(podobne(t, x) for x in w["_t"])), None)
        if not jest:
            wynik.append({**p, "_t": [t], "_linki": [p["link"].rstrip("/")]})
            continue
        jest["_t"].append(t)
        jest["_linki"].append(p["link"].rstrip("/"))
        jest["zrodla"] += [z for z in p["zrodla"] if z not in jest["zrodla"]]
        if (p["pula_usd"] or 0) > (jest["pula_usd"] or 0):
            jest["pula_usd"], jest["pula_tekst"] = p["pula_usd"], p["pula_tekst"]
        if p["termin"] and (not jest["termin"] or p["termin"] < jest["termin"]):
            jest["termin"] = p["termin"]
        jest["ai"] |= p["ai"]
        jest["tryb"] = jest["tryb"] if jest["tryb"] != "?" else p["tryb"]
    return wynik


def w_bazie(sciezka: Path) -> list[tuple[str, tuple[str, ...], str]]:
    if not sciezka.exists():
        return []
    db = sqlite3.connect(f"file:{sciezka}?mode=ro", uri=True)
    try:
        return [(r[0], tokeny(r[1]), (r[2] or "").rstrip("/")) for r in db.execute("SELECT id, nazwa, url FROM hackatony")]
    finally:
        db.close()


def zbierz(katalog: Path, dzis: dt.date, pobieracz: Callable[[str], str] = pobierz) -> tuple[list[dict], dict[str, str]]:
    kopia = katalog / ".zrodla"
    kopia.mkdir(parents=True, exist_ok=True)
    pozycje, stan = [], {}
    for nazwa, (url, parser) in ZRODLA.items():
        plik = kopia / f"{re.sub(r'[^a-z0-9]+', '-', nazwa.lower())}-{dzis}.txt"
        try:
            if not plik.exists():
                plik.write_text(pobieracz(url), encoding="utf-8")
            z = parser(plik.read_text(encoding="utf-8"))
            stan[nazwa] = str(len(z))
            pozycje += z
        except Exception as e:  # jedno padnięte źródło nie zatrzymuje reszty; błąd widać w raporcie
            plik.unlink(missing_ok=True)
            stan[nazwa] = f"błąd: {type(e).__name__}: {str(e)[:80]}"
    for stary in kopia.glob("*.txt"):
        if not stary.stem.endswith(str(dzis)):
            stary.unlink()
    return pozycje, stan


def raport(pozycje: list[dict], stan: dict[str, str], baza: list[tuple[str, tuple[str, ...], str]], dzis: dt.date,
           min_pula: int) -> tuple[list[str], dict]:
    otwarte = scal([p for p in pozycje if p["nazwa"] and (not p["termin"] or p["termin"] >= str(dzis))])
    for p in otwarte:
        nazwy, linki = p.pop("_t"), p.pop("_linki")
        p["w_bazie"] = next((hid for hid, bt, url in baza if any(podobne(t, bt) for t in nazwy) or (url and url in linki)), None)
    zdalne = [p for p in otwarte if p["tryb"] != "na miejscu"]
    nowe = [p for p in zdalne if not p["w_bazie"]]
    od_progu = sorted((p for p in nowe if (p["pula_usd"] or 0) >= min_pula), key=lambda p: -(p["pula_usd"] or 0))
    konkursy = [p for p in od_progu if p["typ"] != "bounty"]
    bounty = [p for p in od_progu if p["typ"] == "bounty"]
    bez_puli = [p for p in nowe if p["pula_usd"] is None and p["ai"] and p["typ"] != "bounty"]
    kw = lambda n: format(n, ",d").replace(",", " ")  # noqa: E731
    tabela = lambda lista: ["| # | Nazwa | Pula USD | Termin w źródle | Tryb | AI | Źródła |", "|---|---|---|---|---|---|---|"] + [  # noqa: E731
        f"| {i} | [{p['nazwa'][:70]}]({p['link']}) | {kw(p['pula_usd'])} | {p['termin'] or '?'} | {p['tryb']} | "
        f"{'tak' if p['ai'] else ''} | {' + '.join(p['zrodla'])} |" for i, p in enumerate(lista, 1)]
    md = [f"# Źródła radaru, {dzis}", "",
          f"Otwarte dziś: {len(otwarte)} hackathonów, konkursów i bounty (powtórki z kilku źródeł liczone raz); online "
          f"albo hybryda: {len(zdalne)}; z nich w bazie: {len(zdalne) - len(nowe)}.",
          f"Do sprawdzenia (online albo hybryda, spoza bazy, pula od {kw(min_pula)} USD): {len(konkursy)} hackathonów "
          f"i konkursów, z nich o AI {sum(p['ai'] for p in konkursy)}; do tego {len(bounty)} stałych programów bounty.", ""]
    if konkursy:
        md += ["## Hackathony i konkursy do sprawdzenia", ""] + tabela(konkursy)
    if bez_puli:
        md += ["", f"## Online o AI spoza bazy, pula nieznana ({len(bez_puli)})", ""]
        md += [f"- [{p['nazwa'][:80]}]({p['link']}), termin {p['termin'] or '?'}, {' + '.join(p['zrodla'])}" for p in bez_puli]
    if bounty:
        md += ["", "## Bounty spoza bazy (programy stałe)", ""] + tabela(bounty)
    md += ["", "## Źródła", "", "| Źródło | Pozycji |", "|---|---|"] + [f"| {z} | {s} |" for z, s in stan.items()]
    dane = {"dzien": str(dzis), "zrodla": stan, "otwarte": len(otwarte), "online_lub_hybryda": len(zdalne),
            "konkursy": konkursy, "bounty": bounty, "ai_bez_puli": bez_puli, "wszystkie": otwarte}
    return md, dane


def main(argv: list[str] | None = None, dzis: dt.date | None = None, pobieracz: Callable[[str], str] = pobierz) -> int:
    domyslny = Path(hackatony.domyslna_baza())
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baza", default=str(domyslny))
    ap.add_argument("--katalog", default=str(domyslny.resolve().parents[1] / "out"))
    ap.add_argument("--min-pula", type=int, default=5000)
    a = ap.parse_args(argv)
    dzis = dzis or dt.datetime.now(dt.timezone.utc).date()
    katalog = Path(a.katalog)
    pozycje, stan = zbierz(katalog, dzis, pobieracz)
    md, dane = raport(pozycje, stan, w_bazie(Path(a.baza)), dzis, a.min_pula)
    (katalog / "ZRODLA.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (katalog / "zrodla.json").write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(md))
    print(f"\nPełna lista: {katalog / 'ZRODLA.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
