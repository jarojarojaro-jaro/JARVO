#!/usr/bin/env python3
"""Typografia jak z montażu: nagranie z mową → napisy słowo po słowie z różną wielkością, krojem, kolorem, głębią,
skosem i perspektywą 3D, jako plan bloków w projekcie edytora HQ (`<film>.edycja.json`, klucz `typo`).

    typografia.py plan <film> [--motyw czysty|kino|ulica|energia|elegancki] [--akcent "#FFD400"]
                              [--tempo spokojne|normalne|ostre] [--zostaw-napisy] [--ziarno N]
    typografia.py pokaz <film> [--json]          # plan w skrócie: bloki, układy, wagi słów (do poprawek)
    typografia.py popraw <film> zmiany.json       # Twoje poprawki reżyserskie (format niżej)
    typografia.py arkusz <film> [-o out/wideo/typografia.jpg] [--ile 12]   # klatki: film + typografia (vision)
    typografia.py usun <film>                     # usuń plan typografii z projektu

plan (0 tokenów, reżyser z reguł): mowa z <źródło>.mowa.json (Parakeet; brak = analiza jak w edytorze), głośność
każdego słowa (krzyk = mocne słowo), pauzy, interpunkcja, cięcia ujęć → frazy (bloki po 1–5 słów), waga słowa 0–3
(0 słowo funkcyjne małe, 3 uderzenie: największe, w akcencie, z efektem motywu), linie bloku, układ bloku
(kolumna, schodki, srodek, skos, 3d, rozrzut; „za” = za osobą, gdy jest maska), obrót, wejście słów i wyjście bloku.
Te same dane rysuje edytor HQ (hq/web/src/48-typografia.js), więc człowiek widzi i poprawia wszystko na osi.

pokaz + popraw = Twoja reżyseria (zasady: skill typografia-edit): znaczenie słowa → forma. zmiany.json:
    {"motyw": "kino", "akcent": "#E5383B",
     "bloki": [{"blok": "b03", "uklad": "skos", "rot": -8, "warstwa": "tyl", "x": 0.3, "y": 0.4,
                "slowa": {"4": {"tekst": "A$$", "kolor": "#2ECC40", "waga": 3, "kroj": "playfairI", "styl": "3d"}}},
               {"polacz": ["b05", "b06"]},          # jedna fraza z dwóch bloków
               {"blok": "b08", "podziel": 2},        # nowy blok od słowa 2 (id b08b)
               {"blok": "b07", "usun": true}]}
Zmiany idą po kolei. Numer słowa liczy się od 0 w bloku (jak w `pokaz`). Pola bloku i słowa: patrz `pokaz --json`.
"""

from __future__ import annotations

import argparse
import array
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import projekt as pr  # noqa: E402  (silnik edytora: pr.ed)

ed = pr.ed
TYPO_JS = next((p for p in (HERE / "edytor_typografia.js", pr._REPO / "hq" / "web" / "src" / "48-typografia.js")
                if p.exists()), None)

# słowa funkcyjne: małe, chyba że wykrzyczane (PL + EN, bez polskich znaków też: transkrypcja bywa bez nich)
STOP = set("""
a aby ale albo ani az aż bo by być byc byl był byla była bylo było by co czy dla do gdy gdzie go i ich im ja jak
jaki jako je jego jej jest jestem jestes jesteś jeszcze juz już ku ma mam mi mnie mu na nad nam nas nawet niech
nim o od on ona one oni ono oraz po pod przez przy sa są się sie sobie tak tam te tego tej ten to tu ty tylko tym
u w we wiec więc z za ze że ze żeby zeby
the a an and or but of to in on at for from with by is are was were be been am it its this that these those
you your i me my we our he she they them his her their do does did so if as just than then there here
""".split())                 # „nie” / „no” / „not” zostają treścią: przeczenie zmienia sens zdania
JEDNOSTKI = {"zł", "zl", "pln", "eur", "euro", "usd", "%", "proc", "procent", "tys", "mln", "mld", "km", "kg", "h", "min",
             "złotych", "złote", "złoty", "procentów"}
LICZEBNIKI = set("""
pół półtora jeden jedna jedno dwa dwie dwóch trzy trzech cztery czterech pięć sześć siedem osiem dziewięć dziesięć
jedenaście dwanaście piętnaście dwadzieścia trzydzieści czterdzieści pięćdziesiąt sto dwieście trzysta pięćset
tysiąc tysiące tysięcy milion miliony milionów miliard miliardy miliardów
one two three four five ten twenty fifty hundred thousand million billion
""".split())
INTERP_KONIEC = (".", "!", "?", "…")
INTERP_PRZERWA = (",", ";", ":", "—", "–")
TEMPO = {"spokojne": {"slow": 5, "dlugosc": 2.8, "idealnie": 3.5}, "normalne": {"slow": 4, "dlugosc": 2.4, "idealnie": 3},
         "ostre": {"slow": 3, "dlugosc": 1.8, "idealnie": 2}}
PAUZA_TWARDA = 0.9       # tak długa cisza zawsze kończy blok (krótsza pauza to tylko dobre miejsce na podział)
KONIEC_ZLY = (STOP | {"nie", "no", "not"}) - {"się", "sie", "mi", "mnie", "go", "jest", "tak", "tu", "tam"}
START_ZLY = {"się", "sie"}
PRZYMIOTNIK = re.compile(r"\w{2,}(ego|emu|ymi|ich|ych|ym|im|ej|ą|ny|na|ne|wy|wa|we|ki|ka|kie|owy|owa|owe|ój|oja|oje)$")  # „bierze | się” — zaimek zwrotny zostaje przy czasowniku
# blok nie kończy się słowem z KONIEC_ZLY („zostaw łapkę w | górę”, „pleców nie | bierze”), chyba że koniec zdania
TRZYMAJ = 0.35           # blok zostaje po ostatnim słowie (czytanie), chyba że wcześniej jest następny albo cięcie
UDERZENIA = 0.34         # część bloków z uderzeniem (waga 3 w kolorze akcentu)
MOTYWY = ed.TYPO_MOTYWY
SKOS = {"czysty": 5, "kino": 7, "ulica": 4, "energia": 10, "elegancki": 3}   # jak `skos` w TYPO_MOTYWY (48-typografia.js)
WYJSCIE_CIECIE = {"czysty": "zanik", "kino": "smuga", "ulica": "ciecie", "energia": "smuga", "elegancki": "zanik"}
WYJSCIE_ZWYKLE = {"czysty": "zanik", "kino": "zanik", "ulica": "ciecie", "energia": "zanik", "elegancki": "zanik"}


def _rng(*klucz) -> float:
    """Powtarzalny „los” 0–1 z klucza (ten sam plan dla tego samego nagrania i ziarna)."""
    h = 2166136261
    for ch in "|".join(map(str, klucz)):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h / 4294967296


def czyste(slowo: str) -> str:
    return re.sub(r"[^\w%$€]", "", slowo.lower())


def liczba(slowo: str) -> bool:
    """Liczba cyframi albo słownie („100”, „dwa”, „tysiące”)."""
    return bool(re.search(r"\d", slowo)) or czyste(slowo) in LICZEBNIKI


# ---------------------------------------------------------------- dane wejściowe: słowa, głośność, cięcia

def glosnosc(src: Path, slowa: list[list]) -> list[float]:
    """Głośność każdego słowa (dB RMS) z dźwięku źródła: ffmpeg → 8 kHz mono, liczone w czystym Pythonie."""
    if not slowa:
        return []
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1",
                        "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    pcm = array.array("h")
    pcm.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    out = []
    for a, b, _w in slowa:
        i, j = int(max(0.0, float(a)) * 8000), int(max(float(a), float(b)) * 8000)
        chunk = pcm[i:max(j, i + 1)]
        if not chunk:
            out.append(-90.0)
            continue
        rms = math.sqrt(sum(x * x for x in chunk) / len(chunk))
        out.append(20 * math.log10(rms / 32768 + 1e-9))
    return out


def z_glosnosci(db: list[float]) -> list[float]:
    """Odchylenie od typowej głośności mówcy (mediana, MAD): +2 = wyraźnie głośniej niż zwykle."""
    if not db:
        return []
    s = sorted(db)
    med = s[len(s) // 2]
    mad = sorted(abs(x - med) for x in db)[len(db) // 2] or 1.0
    return [round((x - med) / (1.4826 * mad), 2) for x in db]


def slowa_osi(proj: dict, analizuj: bool = True) -> tuple[list[dict], list[float]]:
    """Słowa w czasie osi (z klipów projektu) z głośnością i cięcia osi (granice klipów + cięcia ujęć w klipie)."""
    import klipy  # noqa: PLC0415  (analiza mowy i cięcia ujęć jak w clipmakerze)
    out, ciecia, cache = [], [], {}
    for n, (c, s, e) in enumerate(pr.layout(proj["clips"])):
        if n:
            ciecia.append(round(s, 3))
        if c.get("kind") == "image":
            continue
        src = Path(c["src"])
        if src not in cache:
            mowa = klipy.analiza_mowy(src, False) if analizuj else (
                json.loads(ed.speech_path(src).read_text(encoding="utf-8")) if ed.speech_path(src).is_file() else {})
            words = [w for w in mowa.get("words") or [] if not ed.is_filler(str(w[2]))]
            db = glosnosc(src, words) if analizuj else [0.0] * len(words)
            sceny = klipy.sceny(src) if analizuj else []
            cache[src] = (words, z_glosnosci(db), sceny)
        words, z, sceny = cache[src]
        sp = float(c.get("speed") or 1)
        for (a, b, w), zz in zip(words, z):
            if not (c["in"] <= (a + b) / 2 < c["out"]):
                continue
            out.append({"a": round(s + (max(a, c["in"]) - c["in"]) / sp, 3),
                        "b": round(s + (min(b, c["out"]) - c["in"]) / sp, 3), "tekst": str(w), "z": zz})
        ciecia += [round(s + (t - c["in"]) / sp, 3) for t in sceny if c["in"] < t < c["out"]]
    return sorted(out, key=lambda x: x["a"]), sorted(set(ciecia))


# ---------------------------------------------------------------- reżyser: wagi, frazy, linie, układ

def wynik_slowa(w: dict, ostatnie_w_zdaniu: bool) -> float:
    """Waga przed zaokrągleniem: słowo funkcyjne 0, treść 1, plus głośność, długość, liczby, koniec zdania."""
    c = czyste(w["tekst"])
    z = float(w.get("z") or 0)
    if c in STOP:
        return 1.0 if z >= 1.6 else 0.0
    s = 1.0
    if z >= 1.0:
        s += 1.0
    if z >= 2.0:
        s += 1.0
    if len(c) >= 7:
        s += 0.5
    if re.search(r"\d|%|zł|\$|€", w["tekst"].lower()):
        s += 1.5             # liczba to prawie zawsze puenta („100 slajdów”, „2000 zł”)
    elif c in LICZEBNIKI:
        s += 0.8
    if w["tekst"].rstrip().endswith("!"):
        s += 1.0
    if w["tekst"].rstrip().endswith("?"):
        s += 0.8
    if ostatnie_w_zdaniu:
        s += 0.6
    return s


def waga(s: float) -> int:
    return 0 if s < 0.5 else 1 if s < 1.5 else 2 if s < 2.5 else 3


def frazy(slowa: list[dict], ciecia: list[float], tempo: str = "normalne") -> list[list[dict]]:
    """Słowa → bloki (frazy): najtańszy podział całego nagrania, nie zachłanny. Koniec zdania, cięcie ujęcia
    i długa cisza dzielą zawsze; pauza i przecinek to dobre miejsce; blok nie kończy się na słowie funkcyjnym ani
    „nie” („zostaw łapkę w | górę”), nie rozdziela liczby i rzeczy („100 | slajdów”); długość blisko 3 słów (tempo),
    po uderzeniu (waga 3) zostaje najwyżej jedno słowo (mocne słowo na końcu frazy, jak w montażu)."""
    lim = TEMPO.get(tempo, TEMPO["normalne"])
    n = len(slowa)
    if not n:
        return []

    def musi(i: int) -> bool:          # podział między słowem i a i+1 obowiązkowy
        a, b = slowa[i], slowa[i + 1]
        return (a["tekst"].rstrip().endswith(INTERP_KONIEC) or b["a"] - a["b"] > PAUZA_TWARDA
                or any(a["b"] - 0.05 <= t <= b["a"] + 0.05 for t in ciecia))

    tw = [musi(i) for i in range(n - 1)]

    def koszt(a: int, b: int) -> float:
        blok = slowa[a:b + 1]
        k, dl = len(blok), blok[-1]["b"] - blok[0]["a"]
        if k > lim["slow"] + 1 or (k > 1 and dl > lim["dlugosc"] + 1.0) or any(tw[a:b]):
            return math.inf
        ile = sum(0.5 if w["waga"] == 0 else 1.0 for w in blok)     # małe słowa zajmują mniej miejsca i uwagi
        c = 0.8 + 0.6 * (ile - lim["idealnie"]) ** 2 + 3.0 * max(0.0, dl - lim["dlugosc"]) + 2.5 * (ile > lim["slow"])
        hit = max((j for j, w in enumerate(blok) if w["waga"] == 3), default=None)
        if hit is not None and k - 1 - hit >= 2:
            c += 1.5
        if b < n - 1 and not tw[b]:
            ost, nast = slowa[b], slowa[b + 1]
            c += 2.0 - 6.0 * min(nast["a"] - ost["b"], 0.8)     # dzielić w pauzie tanio, w ciągłej mowie drogo
            if ost["tekst"].rstrip().endswith(INTERP_PRZERWA):
                c -= 2.5
            if czyste(ost["tekst"]) in KONIEC_ZLY:
                c += 5.0
            if czyste(nast["tekst"]) in START_ZLY:
                c += 5.0
            if liczba(ost["tekst"]) and czyste(nast["tekst"]) not in STOP:
                c += 6.0
            if PRZYMIOTNIK.search(czyste(ost["tekst"])) and czyste(ost["tekst"]) not in STOP | LICZEBNIKI \
                    and czyste(nast["tekst"]) not in STOP:
                c += 2.0     # „kolejnego | kursu”, „jedną | branżę”: przymiotnik zwykle idzie z rzeczownikiem
        return c

    best, skad = [0.0] + [math.inf] * n, [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(max(0, j - lim["slow"] - 1), j):
            if best[i] < math.inf:
                c = best[i] + koszt(i, j - 1)
                if c < best[j]:
                    best[j], skad[j] = c, i
        if best[j] == math.inf:      # nic nie pasuje (np. bardzo długie słowo): samo słowo jest blokiem
            best[j], skad[j] = best[j - 1] + 1.0, j - 1
    out, j = [], n
    while j > 0:
        out.append(slowa[skad[j]:j])
        j = skad[j]
    return out[::-1]


def ustaw_wagi(slowa: list[dict]) -> None:
    for i, w in enumerate(slowa):
        nast = slowa[i + 1] if i + 1 < len(slowa) else None
        ost = w["tekst"].rstrip().endswith(INTERP_KONIEC) or nast is None or nast["a"] - w["b"] > 0.6
        w["wynik"] = wynik_slowa(w, ost)
        w["waga"] = waga(w["wynik"])


def jednostka(blok: list[dict], j: int) -> bool:
    """Jednostka zaraz po liczbie („1500 zł”, „30 %”): idzie razem z liczbą, w tej samej linii i wadze."""
    return j > 0 and czyste(blok[j]["tekst"]) in JEDNOSTKI and liczba(blok[j - 1]["tekst"])


def po_liczbie(blok: list[dict], j: int) -> bool:
    """Słowo treści zaraz po liczbie („100 slajdów”): ta sama linia co liczba."""
    return j > 0 and liczba(blok[j - 1]["tekst"]) and czyste(blok[j]["tekst"]) not in STOP


def popraw_wagi_bloku(blok: list[dict]) -> None:
    """Jedno uderzenie na blok (najmocniejsze zostaje 3, reszta 2) i zawsze punkt skupienia (co najmniej waga 2)."""
    mocne = sorted((w for w in blok if w["waga"] == 3), key=lambda w: -w["wynik"])
    for w in mocne[1:]:
        w["waga"] = 2
    if not any(w["waga"] >= 2 for w in blok):
        kand = [w for w in blok if czyste(w["tekst"]) not in STOP] or blok
        max(kand, key=lambda w: (w["wynik"], len(w["tekst"])))["waga"] = 2
    jednostki(blok)


def jednostki(blok: list[dict]) -> None:
    """Jednostka po liczbie („100 zł”): uderzenie zawsze na liczbie, jednostka obok niej najwyżej ważna (2)."""
    for j in range(1, len(blok)):
        if jednostka(blok, j):
            if blok[j]["waga"] == 3:
                blok[j - 1]["waga"] = 3
            blok[j]["waga"] = min(blok[j - 1]["waga"], 2)


def rytm_uderzen(grupy: list[list[dict]], udzial: float = UDERZENIA) -> None:
    """Uderzenie (waga 3, kolor akcentu) w około co trzecim bloku: gdy mowa nie dała ich dość, najmocniejsze
    słowa z najmocniejszych bloków dostają 3 (nie dwa bloki z rzędu, jeśli się da); gdy za dużo, słabsze wracają do 2.
    Kolor przestaje znaczyć, gdy jest wszędzie, a film bez akcentów jest płaski."""
    if not grupy:
        return
    cel = max(1, round(len(grupy) * udzial))
    maja = lambda g: any(w["waga"] == 3 for w in g)  # noqa: E731
    sila = lambda g: max((w["wynik"] for w in g if czyste(w["tekst"]) not in STOP), default=0.0)  # noqa: E731
    obecne = [i for i, g in enumerate(grupy) if maja(g)]
    if len(obecne) > round(cel * 1.4):
        for i in sorted(obecne, key=lambda i: sila(grupy[i]))[: len(obecne) - round(cel * 1.4)]:
            for w in grupy[i]:
                if w["waga"] == 3:
                    w["waga"] = 2
        return
    kandydaci = sorted((i for i, g in enumerate(grupy) if not maja(g) and sila(g) > 0), key=lambda i: -sila(grupy[i]))
    for sasiad in (False, True):                 # najpierw bez sąsiadów z uderzeniem, potem jak trzeba
        for i in kandydaci:
            if sum(maja(g) for g in grupy) >= cel:
                return
            if maja(grupy[i]) or (not sasiad and any(0 <= j < len(grupy) and maja(grupy[j]) for j in (i - 1, i + 1))):
                continue
            kand = [w for w in grupy[i] if czyste(w["tekst"]) not in STOP]
            max(kand, key=lambda w: (w["waga"], w["wynik"], len(w["tekst"])))["waga"] = 3
            jednostki(grupy[i])


def linie(blok: list[dict]) -> list[int]:
    """Numer linii każdego słowa: 1–2 słowa w linii, uderzenie samo, małe słowa przy sąsiedzie."""
    out, li, cur = [], 0, []
    for j, w in enumerate(blok):
        nowa = cur and not jednostka(blok, j) and not (po_liczbie(blok, j) and len(cur) == 1) and (
            len(cur) >= 2 or w["waga"] == 3 or any(x["waga"] == 3 for x in cur)
            or (w["waga"] >= 2 and any(x["waga"] >= 1 for x in cur)))
        if nowa:
            li += 1
            cur = []
        cur.append(w)
        out.append(li)
    return out


def energia(blok: list[dict]) -> float:
    return sum(max(0.0, w.get("z") or 0) for w in blok) / len(blok) + max(w["waga"] for w in blok) * 0.4


def wybierz_uklad(blok: list[dict], i: int, poprzednie: list[str], ziarno: int, maska: bool = False) -> str:
    """Układ z sensem: spokojna fraza = kolumna/schodki, mocna = skos/3d; „za” tylko dla jednego uderzenia z maską;
    bez powtarzania tego samego układu trzy razy z rzędu."""
    en = energia(blok)
    if maska and len(blok) == 1 and blok[0]["waga"] == 3:
        return "za"
    if en < 0.9:
        wagi = {"kolumna": 3, "schodki": 2, "srodek": 1.5, "rozrzut": 0.6}
    elif en < 1.6:
        wagi = {"schodki": 3, "kolumna": 2, "skos": 1.5, "3d": 1.0, "rozrzut": 1.0}
    else:
        wagi = {"skos": 3, "3d": 2, "schodki": 1.5, "srodek": 1.0}
    if len(blok) == 1:
        wagi.pop("schodki", None); wagi.pop("rozrzut", None)
        wagi["srodek"] = wagi.get("srodek", 1) + 1
    for k, kara in zip(poprzednie[-2:][::-1], (0.15, 0.5)):
        if k in wagi:
            wagi[k] *= kara
    los = _rng(ziarno, i, "uklad") * sum(wagi.values())
    for k, v in wagi.items():
        los -= v
        if los <= 0:
            return k
    return next(iter(wagi))


def wyjscie(motyw: str, ciecie: bool, ostatnie: float, przerwa: float) -> str:
    """Wyjście bloku: na cięciu ujęcia efekt motywu (smuga), w ciągłej mowie twarde cięcie (następna fraza wchodzi
    od razu, a zanikanie zjadałoby ostatnie słowo), po pauzie zanik. Efekt tylko, gdy ostatnie słowo było widać."""
    if ciecie:
        return WYJSCIE_CIECIE[motyw] if ostatnie >= 0.3 else "ciecie"
    return WYJSCIE_ZWYKLE[motyw] if przerwa >= 0.12 and ostatnie >= 0.3 else "ciecie"


def miejsce(i: int, W: int, H: int, uklad: str) -> dict:
    """Kotwica i szerokość bloku bez wiedzy o osobie w kadrze: pion = nad opisem TikToka i obok przycisków
    (jak PION w edytorze), poziom = dolna część kadru. Z maską osoby miejsce wybiera `miejsce_z_maski`."""
    if H > W:
        return {"x": 0.46 + (0.03 if i % 2 else -0.03), "y": 0.64 if uklad != "za" else 0.34, "w": 0.7}
    return {"x": 0.5 + (0.12 if i % 2 else -0.12) * (uklad in ("kolumna", "3d")), "y": 0.7 if uklad != "za" else 0.4,
            "w": 0.5}


def zbuduj_plan(slowa: list[dict], ciecia: list[float], W: int, H: int, total: float, motyw: str = "czysty",
                tempo: str = "normalne", ziarno: int = 0, akcent: str | None = None) -> dict:
    """Cały plan typografii (czyste funkcje: testy bez ffmpeg i przeglądarki)."""
    slowa = [dict(w) for w in slowa if str(w.get("tekst") or "").strip()]
    ustaw_wagi(slowa)
    bloki, uklady = [], []
    grupy = frazy(slowa, ciecia, tempo)
    for blok in grupy:
        popraw_wagi_bloku(blok)
    rytm_uderzen(grupy)
    for i, blok in enumerate(grupy):
        uklad = wybierz_uklad(blok, i, uklady, ziarno)
        uklady.append(uklad)
        start = blok[0]["a"]
        nast = grupy[i + 1][0]["a"] if i + 1 < len(grupy) else total
        ciecie_po = next((t for t in ciecia if blok[-1]["b"] - 0.05 <= t <= nast + 0.05), None)
        koniec = min(nast - 0.02, blok[-1]["b"] + TRZYMAJ, total)
        if ciecie_po is not None:
            koniec = min(koniec, ciecie_po)
        koniec = min(total, max(koniec, min(blok[-1]["a"] + 0.3, nast - 0.02)))   # ostatnie słowo chwilę widać, bez nakładania
        m = miejsce(i, W, H, uklad)
        strona = -1 if i % 2 else 1
        rot = 0.0
        if uklad == "skos":
            rot = -strona * (4 + _rng(ziarno, i, "rot") * SKOS.get(motyw, 5))
        elif uklad in ("kolumna", "schodki") and SKOS.get(motyw, 0) >= 7:
            rot = round((_rng(ziarno, i, "rot") - 0.5) * 4, 1)
        tilt = (strona * (18 + _rng(ziarno, i, "tilt") * 10)) if uklad == "3d" else 0.0
        li = linie(blok)
        nb = {"id": f"b{i + 1:02d}", "start": round(start, 3), "end": round(min(total, koniec), 3), "uklad": uklad,
              **{k: round(v, 3) for k, v in m.items()}, "rot": round(rot, 1), "tilt": round(tilt, 1),
              "warstwa": "tyl" if uklad == "za" else "przod",
              "wyjscie": wyjscie(motyw, ciecie_po is not None, koniec - blok[-1]["a"], nast - koniec),
              "slowa": []}
        for j, w in enumerate(blok):
            x = {"t": round(w["a"] - start, 3), "k": round(w["b"] - start, 3), "tekst": w["tekst"].strip(" ,;:"),
                 "waga": w["waga"], "linia": li[j]}
            if x["tekst"].endswith((".", "…")) and not x["tekst"].endswith(".."):
                x["tekst"] = x["tekst"].rstrip(".…")
            if uklad == "rozrzut":
                x["glebia"] = (-1, 0, 1)[j % 3] if w["waga"] < 3 else 1
            elif len(blok) >= 4 and w["waga"] == 1 and _rng(ziarno, i, j, "glebia") < 0.25:
                x["glebia"] = -1     # słowo „z tyłu”: mniejsze, drugi krój, lekko rozmyte (głębia bez maski)
            nb["slowa"].append(x)
        bloki.append(nb)
    plan = {"motyw": motyw if motyw in MOTYWY else "czysty", "bloki": bloki}
    if akcent:
        plan["akcent"] = akcent
    return ed.normalize_typo(plan, total)


# ---------------------------------------------------------------- polecenia

def cmd_plan(film: Path, a) -> int:
    proj = pr.load(film)
    cv = proj["canvas"]
    total = pr.total(proj)
    slowa, ciecia = slowa_osi(proj)
    if not slowa:
        raise SystemExit("brak mowy w nagraniu: typografia potrzebuje słów (sprawdź dźwięk albo transkrypcję)")
    plan = zbuduj_plan(slowa, ciecia, cv["w"], cv["h"], total, a.motyw, a.tempo, a.ziarno, a.akcent)
    proj["typo"] = plan
    if not a.zostaw_napisy:
        proj["texts"] = [x for x in proj.get("texts") or [] if not x.get("cap")]
    pr.save(film, proj)
    n_slow = sum(len(b["slowa"]) for b in plan["bloki"])
    print(f"Typografia: {len(plan['bloki'])} bloków, {n_slow} słów, motyw {plan['motyw']} · cięcia: {len(ciecia)}")
    print(f"Dalej: typografia.py pokaz {film} → popraw według znaczenia → typografia.py arkusz {film} → projekt.py render {film}")
    return 0


def opis_slowa(w: dict) -> str:
    extra = "".join(f" {k}={w[k]}" for k in ("kolor", "kroj", "styl", "glebia") if k in w)
    return f"[{w['waga']}]{w['tekst']}{('{' + extra.strip() + '}') if extra else ''}"


def cmd_pokaz(film: Path, a) -> int:
    proj = pr.load(film)
    plan = ed.normalize_typo(proj.get("typo"), pr.total(proj))
    if a.json:
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        return 0
    if not plan["bloki"]:
        print("Brak planu typografii: typografia.py plan <film>")
        return 0
    cv = proj["canvas"]
    print(f"Typografia: {film.name} · motyw {plan['motyw']}{' · akcent ' + plan['akcent'] if plan.get('akcent') else ''}"
          f" · {len(plan['bloki'])} bloków · kadr {cv['w']}×{cv['h']}")
    for b in plan["bloki"]:
        lin: dict[int, list[str]] = {}
        for j, w in enumerate(b["slowa"]):
            lin.setdefault(w["linia"], []).append(f"{j}:{opis_slowa(w)}")
        extra = "".join([f" rot {b['rot']:+.0f}" if b["rot"] else "", f" tilt {b['tilt']:+.0f}" if b["tilt"] else "",
                         " ZA OSOBĄ" if b["warstwa"] == "tyl" else "", f" wyjście {b['wyjscie']}" if b.get("wyjscie") else ""])
        print(f"{b['id']} {b['start']:6.2f}–{b['end']:6.2f} {b['uklad']:8s} x{b['x']:.2f} y{b['y']:.2f} w{b['w']:.2f}{extra}"
              f"  |  {' / '.join(' '.join(v) for _k, v in sorted(lin.items()))}")
    print("\nWaga: [0] małe słowo funkcyjne, [1] zwykłe, [2] ważne (większe), [3] uderzenie (największe, kolor akcentu,"
          " jedno na blok, około co trzeci blok).")
    print("Poprawki według znaczenia (skill typografia-edit): zmiany.json → typografia.py popraw <film> zmiany.json")
    return 0


POLA_BLOKU = ("start", "end", "uklad", "x", "y", "w", "rot", "tilt", "warstwa", "wejscie", "wyjscie", "rozmiar")
POLA_SLOWA = ("tekst", "waga", "linia", "glebia", "kolor", "kroj", "styl", "wejscie", "wielkie", "skala", "t", "k")


def zastosuj(plan: dict, zmiany: dict, total: float) -> tuple[dict, list[str]]:
    """Poprawki z zmiany.json na planie; zwraca nowy plan (po walidacji) i listę ostrzeżeń."""
    plan = json.loads(json.dumps(plan))
    uwagi = []
    for k in ("motyw", "akcent"):
        if k in zmiany:
            plan[k] = zmiany[k]
    po_id = {b["id"]: b for b in plan["bloki"]}
    for z in zmiany.get("bloki") or []:
        if "polacz" in z:
            ids = [str(x) for x in z.get("polacz") or []]
            if len(ids) != 2 or not all(x in po_id for x in ids):
                uwagi.append(f"polacz: podaj dwa istniejące bloki, jest {ids!r}")
                continue
            a, b = sorted((po_id[x] for x in ids), key=lambda x: x["start"])
            d, li = b["start"] - a["start"], max(w["linia"] for w in a["slowa"]) + 1
            a["slowa"] += [{**w, "t": round(w["t"] + d, 3), "k": round(w["k"] + d, 3), "linia": w["linia"] + li}
                           for w in b["slowa"]]
            a["end"] = max(a["end"], b["end"])
            plan["bloki"].remove(b)
            po_id.pop(b["id"])
            continue
        b = po_id.get(str(z.get("blok")))
        if b is None:
            uwagi.append(f"nie ma bloku {z.get('blok')!r} (sprawdź `pokaz`)")
            continue
        if z.get("usun"):
            plan["bloki"].remove(b)
            continue
        if z.get("podziel") is not None:
            j = int(z["podziel"]) if str(z["podziel"]).lstrip("-").isdigit() else -1
            if not 0 < j < len(b["slowa"]):
                uwagi.append(f"{b['id']}: podziel przed słowem 1–{len(b['slowa']) - 1}, jest {z['podziel']!r}")
                continue
            d = b["slowa"][j]["t"]
            nid = next(f"{b['id']}{c}" for c in "bcdefghijklmnopqrstuvwxyz" if f"{b['id']}{c}" not in po_id)
            li = b["slowa"][j]["linia"]
            nowy = {**{k: v for k, v in b.items() if k != "slowa"}, "id": nid, "start": round(b["start"] + d, 3),
                    "slowa": [{**w, "t": round(w["t"] - d, 3), "k": round(w["k"] - d, 3), "linia": max(0, w["linia"] - li)}
                              for w in b["slowa"][j:]]}
            b["slowa"], b["end"] = b["slowa"][:j], round(nowy["start"] - 0.02, 3)
            plan["bloki"].append(nowy)
            po_id[nid] = nowy
            continue
        for k in POLA_BLOKU:
            if k in z:
                b[k] = z[k]
        for j, zw in (z.get("slowa") or {}).items():
            try:
                w = b["slowa"][int(j)]
            except (ValueError, IndexError):
                uwagi.append(f"{b['id']}: nie ma słowa {j}")
                continue
            if zw is None:
                w["tekst"] = ""
                continue
            for k in POLA_SLOWA:
                if k in zw:
                    if zw[k] is None:
                        w.pop(k, None)
                    else:
                        w[k] = zw[k]
    nowy = ed.normalize_typo(plan, total)
    for b in nowy["bloki"]:
        if sum(1 for w in b["slowa"] if w["waga"] == 3) > 1:
            uwagi.append(f"{b['id']}: więcej niż jedno uderzenie (waga 3) w bloku; oko nie wie, gdzie patrzeć")
    return nowy, uwagi


def cmd_popraw(film: Path, a) -> int:
    proj = pr.load(film)
    total = pr.total(proj)
    try:
        zmiany = json.loads(Path(a.zmiany).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"nie mogę odczytać {a.zmiany}: {exc}")
    plan, uwagi = zastosuj(ed.normalize_typo(proj.get("typo"), total), zmiany, total)
    proj["typo"] = plan
    pr.save(film, proj)
    for u in uwagi:
        print(f"uwaga: {u}")
    print(f"Typografia: {len(plan['bloki'])} bloków po poprawkach")
    return 0


def cmd_usun(film: Path, a) -> int:
    proj = pr.load(film)
    proj.pop("typo", None)
    pr.save(film, proj)
    print("Plan typografii usunięty")
    return 0


WYJSCIE_CZAS = {"ciecie": 0.0, "zanik": 0.16, "smuga": 0.14}   # jak TYPO_WYJSCIA w 48-typografia.js


def chwile_arkusza(plan: dict, ile: int) -> list[float]:
    """Chwile, w których blok jest pełny (ostatnie słowo weszło), a wyjście jeszcze się nie zaczęło."""
    wy = lambda b: WYJSCIE_CZAS.get(b.get("wyjscie") or WYJSCIE_ZWYKLE.get(plan.get("motyw"), "zanik"), 0.16)  # noqa: E731
    t = [round(max(b["start"] + b["slowa"][-1]["t"], min(b["end"] - wy(b) - 0.03, b["start"] + b["slowa"][-1]["t"] + 0.3)), 3)
         for b in plan["bloki"]]
    if len(t) <= ile:
        return t
    return [t[round(i * (len(t) - 1) / (ile - 1))] for i in range(ile)] if ile > 1 else t[:1]


def cmd_arkusz(film: Path, a) -> int:
    import narzedzia as nz
    nz.wymagaj_playwright(__file__, "JARVO_TYPO_REEXEC", "arkusz rysuje przeglądarka")   # re-exec TEGO skryptu
    proj = pr.load(film)
    total = pr.total(proj)
    plan = ed.normalize_typo(proj.get("typo"), total)
    if not plan["bloki"]:
        raise SystemExit("brak planu typografii: typografia.py plan <film>")
    out = Path(a.out) if a.out else film.with_name(f"{film.stem}.typografia.jpg")
    chwile = chwile_arkusza(plan, a.ile)
    pr.arkusz_typografii(proj, plan, chwile, out)
    print(f"Arkusz: {out} ({len(chwile)} klatek; oceń vision_analyze: czytelność, twarz, strefy UI, sens akcentów)")
    print(f"MEDIA:{out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("plan", help="reżyser z reguł: plan typografii w projekcie")
    sp.add_argument("film")
    sp.add_argument("--motyw", choices=MOTYWY, default="czysty")
    sp.add_argument("--akcent", help="kolor akcentu (np. kolor marki z brand kitu), #RRGGBB")
    sp.add_argument("--tempo", choices=tuple(TEMPO), default="normalne")
    sp.add_argument("--ziarno", type=int, default=0, help="inny wariant układów (ten sam numer = ten sam plan)")
    sp.add_argument("--zostaw-napisy", action="store_true", help="nie usuwaj zwykłych napisów z projektu")
    sp.set_defaults(fn=cmd_plan)
    sp = sub.add_parser("pokaz", help="plan w skrócie")
    sp.add_argument("film")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_pokaz)
    sp = sub.add_parser("popraw", help="poprawki reżyserskie z pliku JSON")
    sp.add_argument("film")
    sp.add_argument("zmiany")
    sp.set_defaults(fn=cmd_popraw)
    sp = sub.add_parser("arkusz", help="klatki film + typografia do oceny")
    sp.add_argument("film")
    sp.add_argument("-o", "--out")
    sp.add_argument("--ile", type=int, default=12)
    sp.set_defaults(fn=cmd_arkusz)
    sp = sub.add_parser("usun", help="usuń plan typografii")
    sp.add_argument("film")
    sp.set_defaults(fn=cmd_usun)
    a = ap.parse_args(argv)
    film = Path(a.film).resolve()
    if not film.is_file():
        raise SystemExit(f"nie ma pliku: {film}")
    if getattr(a, "akcent", None) and not re.match(r"^#[0-9A-Fa-f]{6}$", a.akcent):
        raise SystemExit("--akcent: kolor #RRGGBB")
    return a.fn(film, a)


if __name__ == "__main__":
    sys.exit(main())
