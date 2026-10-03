#!/usr/bin/env python3
"""Typografia jak z montażu: nagranie z mową → napisy słowo po słowie z różną wielkością, krojem, kolorem, głębią,
skosem i perspektywą 3D, jako plan bloków w projekcie edytora HQ (`<film>.edycja.json`, klucz `typo`).

    typografia.py plan <film> [--motyw czysty|podcast|vlog|…] [--akcent "#C8102E"] [--paleta A,B]
                              [--tempo spokojne|normalne|ostre] [--zostaw-napisy] [--ziarno N] [--bez-maski] [--nowy]
    typografia.py pokaz <film> [--json]          # plan w skrócie: bloki, układy, wagi słów (do poprawek)
    typografia.py popraw <film> zmiany.json       # Twoje poprawki reżyserskie (format niżej)
    typografia.py sylwetki <film>                 # sylwetki osoby pod bloki „za osobą” (np. ustawione w edytorze)
    typografia.py paleta <film> [--paleta A,B] [--akcent marka] [--bez-akcentu]   # kolory z kadru na gotowym planie
    typografia.py arkusz <film> [-o out/wideo/typografia.jpg] [--ile 12]   # klatki: film + typografia (vision)
    typografia.py style <film> [-o …] [--blok b03] [--motywy podcast,vlog]   # ten sam blok w każdym motywie
    typografia.py usun <film>                     # usuń plan typografii z projektu

plan (0 tokenów, reżyser z reguł): mowa z <źródło>.mowa.json (Parakeet; brak = analiza jak w edytorze), głośność
każdego słowa (krzyk = mocne słowo), pauzy, interpunkcja, cięcia ujęć → frazy (bloki po 1–5 słów), waga słowa 0–3
(0 słowo funkcyjne małe, 3 uderzenie: największe, w kolorze z palety, z efektem motywu), linie bloku, układ bloku
(kolumna, schodki, srodek, skos, 3d, rozrzut), obrót, wejście słów i wyjście bloku. Maska osoby (maska.py, MODNet):
blok staje obok twarzy, nie na niej, a najwyżej co szósty z jednym mocnym słowem idzie „za osobę” (sylwetki klatek
w <film>.maska/, eksport i edytor kładą osobę z powrotem nad napisem). Bez modelu albo z --bez-maski: miejsca domyślne.
Paleta z kadru: dwa akcenty z kontrastu z materiałem (główna barwa sceny → barwa przeciwna, np. niebieskie niebo
i morze → ciemna czerwień; bonus za mocny kolor już w kadrze, kara za barwy skóry przy osobie), wariant ciemny albo
jasny z tła pod blokami, kolory na zmianę po mocnych słowach (uderzenia i co drugi blok bez uderzenia), płytka
pod słowem, które nie odcina się od tła.
Motyw to styl całego filmu (13: czysty, kino, ulica, energia, elegancki, podcast, vlog, komiks, magazyn, tech,
nowoczesny, retro, neon): kroje, styl słów i uderzenia (wypełnienie, obrys, 3D, blask, płytka, kontur), wejście,
wyjście i skos. `style` rysuje ten sam blok filmu w każdym motywie, żeby wybrać styl okiem; zmiana motywu nie rusza
układu, kolorów ani poprawek.
Te same dane rysuje edytor HQ (hq/web/src/48-typografia.js), więc człowiek widzi i poprawia wszystko na osi.
Gotowy plan mógł już poprawić człowiek, więc `plan` go nie nadpisuje: poprawiasz go `popraw`, a od nowa układasz
tylko na wyraźną prośbę (`--nowy`).

pokaz + popraw = Twoja reżyseria (zasady: skill typografia-edit): znaczenie słowa → forma. zmiany.json:
    {"motyw": "kino", "paleta": ["#B3122E", "#F2C94C"],   # nowa paleta: słowa w starych kolorach idą za nią
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
# motyw (styl filmu) → skala skosu w stopniach, wyjście bloku na cięciu ujęcia i po pauzie w mowie, styl słów i styl
# uderzenia; te same wartości co `skos`, `wyjscie`, `styl`, `hit` w TYPO_MOTYWY (48-typografia.js), test pilnuje zgodności
MOTYW_CECHY = {
    "czysty": {"skos": 5, "ciecie": "zanik", "zwykle": "zanik", "styl": "wypelnij", "hit": "wypelnij"},
    "kino": {"skos": 7, "ciecie": "smuga", "zwykle": "zanik", "styl": "wypelnij", "hit": "3d"},
    "ulica": {"skos": 4, "ciecie": "ciecie", "zwykle": "ciecie", "styl": "wypelnij", "hit": "wypelnij"},
    "energia": {"skos": 10, "ciecie": "smuga", "zwykle": "zanik", "styl": "wypelnij", "hit": "blask"},
    "elegancki": {"skos": 3, "ciecie": "zanik", "zwykle": "zanik", "styl": "wypelnij", "hit": "wypelnij"},
    "podcast": {"skos": 3, "ciecie": "ciecie", "zwykle": "ciecie", "styl": "obrys", "hit": "obrys"},
    "vlog": {"skos": 8, "ciecie": "zanik", "zwykle": "zanik", "styl": "obrys", "hit": "3d"},
    "komiks": {"skos": 10, "ciecie": "smuga", "zwykle": "zanik", "styl": "obrys", "hit": "3d"},
    "magazyn": {"skos": 2, "ciecie": "zanik", "zwykle": "zanik", "styl": "wypelnij", "hit": "wypelnij"},
    "tech": {"skos": 0, "ciecie": "ciecie", "zwykle": "ciecie", "styl": "wypelnij", "hit": "tlo"},
    "nowoczesny": {"skos": 4, "ciecie": "smuga", "zwykle": "zanik", "styl": "wypelnij", "hit": "wypelnij"},
    "retro": {"skos": 6, "ciecie": "zanik", "zwykle": "zanik", "styl": "wypelnij", "hit": "3d"},
    "neon": {"skos": 5, "ciecie": "zanik", "zwykle": "zanik", "styl": "wypelnij", "hit": "blask"},
}
SKOS = {k: v["skos"] for k, v in MOTYW_CECHY.items()}
WYJSCIE_CIECIE = {k: v["ciecie"] for k, v in MOTYW_CECHY.items()}
WYJSCIE_ZWYKLE = {k: v["zwykle"] for k, v in MOTYW_CECHY.items()}


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


# ---------------------------------------------------------------- miejsce z maską osoby (maska.py)

def _pole(a: list[float]) -> float:
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


def _wspolne(a: list[float], b: list[float] | None) -> float:
    if not b:
        return 0.0
    return _pole([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def rozmiar_bloku(b: dict, w: float, W: int, H: int) -> tuple[float, float]:
    """Szacunek ramki bloku (część kadru) przed rysowaniem: blok wypełnia ~80% szerokości, linia ma tyle znaków,
    ile jej słowa, a wysokość jak w rendererze ma limit (pion 30%, poziom 50%)."""
    linie_: dict[int, int] = {}
    for x in b["slowa"]:
        linie_[x["linia"]] = linie_.get(x["linia"], 0) + len(x["tekst"]) + 1
    znaki = max(4, max(linie_.values()) - 1)
    bw = 0.8 * w
    px = bw * W / (0.52 * znaki)
    bh = min(len(linie_) * px * 1.05 / H, 0.3 if H > W else 0.5)
    return bw, bh


def miejsce_z_maski(b: dict, o: dict, W: int, H: int, poprzednie: tuple[float, float] | None = None) -> dict:
    """Kotwica i szerokość bloku z osobą w kadrze: nie na twarzy (głowa z zapasem), raczej poza sylwetką, w strefie
    bezpiecznej platformy (pion: nad opisem i obok przycisków), blisko zwykłego miejsca i poprzedniego bloku."""
    pion = H > W
    baza = miejsce(0, W, H, b["uklad"])
    g = o.get("glowa")
    twarz = [g[0] - 0.03, g[1] - 0.02, g[2] + 0.03, g[3] + 0.03] if g else None
    osoba = o.get("osoba")
    best, wynik = None, math.inf
    for w in (baza["w"], baza["w"] * 0.8, baza["w"] * 0.62):
        bw, bh = rozmiar_bloku(b, w, W, H)
        for x in (0.28, 0.36, 0.44, 0.5, 0.56, 0.64, 0.72):
            for y in (0.2, 0.28, 0.36, 0.44, 0.52, 0.6, 0.68, 0.76):
                r = [x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2]
                pole = max(_pole(r), 1e-6)
                c = 9.0 * _wspolne(r, twarz) / pole + 1.2 * _wspolne(r, osoba) / pole
                c += 1.6 * math.hypot(x - baza["x"], y - baza["y"]) + 1.5 * (1 - w / baza["w"])
                gora, dol, prawo = (0.14, 0.8, 0.86) if pion else (0.06, 0.92, 0.96)
                c += 6.0 * (max(0.0, gora - r[1]) + max(0.0, r[3] - dol) + max(0.0, r[2] - prawo) + max(0.0, 0.04 - r[0]))
                if poprzednie:
                    c += 0.35 * math.hypot(x - poprzednie[0], y - poprzednie[1])
                if c < wynik:
                    best, wynik = {"x": x, "y": y, "w": round(w, 3)}, c
    return best


ZA_ZNAKI = 14            # najwięcej znaków napisu za osobą: jedna linia, uderzenie z małymi słowami i jednostką


def _dl(slowa: list[dict]) -> int:
    return sum(len(x["tekst"]) for x in slowa) + max(0, len(slowa) - 1)


def czesc_za(b: dict) -> tuple[int, int] | None:
    """Słowa [i, j) bloku, które pójdą za osobę: uderzenie (waga 3), krótka jednostka po nim („PIĘĆ minut”, do 12
    znaków) i małe słowa przed nim („w PRZYSZŁYM”), razem do ZA_ZNAKI. Napis za osobą zostaje do końca frazy
    (≥ 0,5 s), reszta frazy wchodzi przed osobą obok niego; część przed uderzeniem musi się dać przeczytać
    (≥ 0,3 s), a same małe słowa nie zostają osobno."""
    s = b["slowa"]
    h = next((j for j, x in enumerate(s) if x["waga"] == 3), None)
    if h is None or _dl(s[h:h + 1]) > ZA_ZNAKI:
        return None
    i, j = h, h + 1
    if j < len(s) and s[j]["waga"] >= 2 and _dl(s[i:j + 1]) <= 12:
        j += 1
    while i > 0 and s[i - 1]["waga"] == 0 and _dl(s[i - 1:j]) <= ZA_ZNAKI:
        i -= 1
    if all(x["waga"] == 0 for x in s[:i]):
        i = 0
    if all(x["waga"] == 0 for x in s[j:]):
        j = len(s)
    dlugosc, od = b["end"] - b["start"], (s[i]["t"] if i else 0.0)
    if dlugosc - od < 0.5 or (i and od < 0.3) or (j < len(s) and dlugosc - s[j]["t"] < 0.3):
        return None
    return i, j


def za_osoba(b: dict, o: dict, W: int, H: int) -> bool:
    """Część bloku może stanąć za osobą: jest uderzenie (czesc_za), głowa wyraźna i nie za szeroka (napis za nią
    ma być czytelny: głowa zasłania najwyżej ~40% jego szerokości), nad głową miejsce na górę liter, osoba
    w kadrze, ale nie na cały kadr."""
    g = o.get("glowa")
    if not g or not o.get("osoba") or czesc_za(b) is None:
        return False
    gw, gh = g[2] - g[0], g[3] - g[1]
    return (0.08 <= gh <= 0.45 and gw <= 0.4 * (0.94 if H > W else 0.7) and g[1] >= (0.14 if H > W else 0.1)
            and 0.04 <= o.get("pokrycie", 0) <= 0.7)


def _linie_od_zera(slowa: list[dict]) -> None:
    nr = {v: n for n, v in enumerate(sorted({x["linia"] for x in slowa}))}
    for x in slowa:
        x["linia"] = nr[x["linia"]]


def wydziel_za(b: dict, i: int, j: int, g: list[float], W: int, H: int) -> list[dict]:
    """Blok → [część przed] + część za osobą + [część po]. Za osobą: duży napis w jednej linii, bez skosu, nad
    środkiem głowy tak, że głowa zasłania tylko dół środkowych liter; zostaje do końca frazy. Część przed
    zostaje w miejscu bloku i znika cięciem, gdy wchodzi uderzenie; część po wchodzi przed osobą, pod napisem."""
    s, d0, dl = b["slowa"], b["start"], b["end"] - b["start"]
    baza = {k: v for k, v in b.items() if k != "slowa"}

    def czesc(a: int, z: int, sufiks: str) -> dict:
        od = s[a]["t"] if a else 0.0
        nb = {**baza, "id": b["id"] + sufiks, "start": round(d0 + od, 3), "end": b["end"],
              "slowa": [{**x, "t": round(x["t"] - od, 3), "k": round(x["k"] - od, 3)} for x in s[a:z]]}
        _linie_od_zera(nb["slowa"])
        return nb

    za = czesc(i, j, "b" if i else "")
    x = min(0.7, max(0.3, (g[0] + g[2]) / 2))           # środek głowy, a napis cały w kadrze
    w = min(0.94 if H > W else 0.7, 2 * (min(x, 1 - x) - 0.03))
    for x_ in za["slowa"]:
        x_.pop("glebia", None)
        x_["linia"] = 0
    bh = rozmiar_bloku(za, w, W, H)[1]
    za.update({"uklad": "za", "warstwa": "tyl", "rot": 0, "tilt": 0, "x": round(x, 3), "w": round(w, 3),
               "y": round(min(0.7, max(bh / 2 + 0.02, g[1] + 0.1 * bh)), 3)})
    czesci = [za]
    if i:
        przed = czesc(0, i, "")
        przed.update({"end": round(za["start"] - 0.02, 3), "wyjscie": "ciecie"})
        czesci.insert(0, przed)
    if j < len(s):
        po = czesc(j, len(s), "c" if i else "b")
        ph = rozmiar_bloku(po, po["w"], W, H)[1]
        if abs(po["y"] - za["y"]) < (bh + ph) / 2 + 0.02:      # pod napisem za osobą, nie na nim
            po["y"] = round(min(0.8 - ph / 2, za["y"] + (bh + ph) / 2 + 0.04), 3)
        czesci.append(po)
    return czesci


def uloz_z_maska(plan: dict, opisy: list[dict], W: int, H: int, total: float, udzial: float = 1 / 6) -> dict:
    """Plan po masce osoby: każdy blok z osobą w kadrze dostaje miejsce obok twarzy (miejsce_z_maski), a najwyżej
    co szósty blok (nie dwa z rzędu) z uderzeniem oddaje je „za osobę”: duże, na wysokości czoła, osoba przed nim
    (wydziel_za; reszta frazy zostaje przed osobą)."""
    plan = json.loads(json.dumps(plan))
    bloki = plan["bloki"]
    po_t = {round(x["t"], 3): x for x in opisy}
    poprz = None
    kandydaci = []
    for i, b in enumerate(bloki):
        o = po_t.get(round((b["start"] + b["end"]) / 2, 3))
        if not o or not o.get("osoba"):
            continue
        b.update(miejsce_z_maski(b, o, W, H, poprz))
        poprz = (b["x"], b["y"])
        if za_osoba(b, o, W, H):
            kandydaci.append((i, o))
    limit, wybrane = max(1, round(len(bloki) * udzial)), {}
    for i, o in sorted(kandydaci, key=lambda io: _dl(bloki[io[0]]["slowa"][slice(*czesc_za(bloki[io[0]]))])):
        if len(wybrane) >= limit or {i - 1, i + 1} & set(wybrane):
            continue
        wybrane[i] = wydziel_za(bloki[i], *czesc_za(bloki[i]), o["glowa"], W, H)
    plan["bloki"] = [c for i, b in enumerate(bloki) for c in wybrane.get(i, [b])]
    return ed.normalize_typo(plan, total)


# ---------------------------------------------------------------- paleta z kadru

# Rodziny kolorów napisu: barwa (stopnie), wariant ciemny (na jasne tło), jasny (na ciemne) i smak (kara: oliwkowe
# i pomarańczowe słowo rzadko wygląda dobrze). Paleta filmu to dwie rodziny wybrane z kontrastu z materiałem,
# nie jeden kolor motywu na wszystko. Kolejność = pierwszeństwo przy remisie (szara scena bez wyraźnej barwy).
KOLORY = {
    "czerwony": (355, "#B3122E", "#FF5A5F", 0.0),
    "złoty": (45, "#A87A12", "#F2C94C", 0.0),
    "niebieski": (215, "#1D4ED8", "#7CB7FF", 0.0),
    "turkusowy": (180, "#0E7C86", "#5EEAD4", 0.0),
    "różowy": (325, "#BE185D", "#FF7AC6", 0.0),
    "fioletowy": (265, "#6D28D9", "#B79CFF", 0.05),
    "zielony": (140, "#15803D", "#4ADE80", 0.1),
    "pomarańczowy": (25, "#C2410C", "#FF8A3D", 0.05),
    "limonkowy": (80, "#4D7C0F", "#C6F432", 0.3),
}
PALETA_ROZNICA = 40      # najmniejsza różnica barw dwóch akcentów (stopnie): inaczej to jeden kolor dwa razy
PALETA_BOK = 96          # dłuższy bok klatki do analizy koloru (wystarczy na barwy i jasność tła pod blokiem)
KONTRAST_PLYTA = 1.6     # słabszy kontrast słowa w akcencie z tłem pod blokiem = słowo na płytce (styl „tlo”)


def _barwa_d(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _hex_rgb(h: str) -> tuple[float, float, float]:
    n = int(h.lstrip("#"), 16)
    return ((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255


def luminancja(r: float, g: float, b: float) -> float:
    """Względna luminancja WCAG (0 czerń – 1 biel)."""
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def kontrast(l1: float, l2: float) -> float:
    a, b = max(l1, l2), min(l1, l2)
    return (a + 0.05) / (b + 0.05)


def analiza_kadru(klatki: list[bytes]) -> dict:
    """Barwy materiału z małych klatek RGB: histogram barw ważony nasyceniem (36 przedziałów po 10°; skóra waży
    mniej, bo to osoba, nie scena), „echo” = mały, mocno nasycony przedmiot w kadrze (czerwona czapka), udział
    barw skóry i piasku, jasność i barwność (średnie nasycenie: szare biuro ≈ 0, plaża z morzem ≫ 0)."""
    import colorsys  # noqa: PLC0415
    hist, echo, n, jas, chroma, skory = [0.0] * 36, [0.0] * 36, 0, 0.0, 0.0, 0
    for rgb in klatki:
        for i in range(0, len(rgb) - 2, 3):
            r, g, b = rgb[i] / 255, rgb[i + 1] / 255, rgb[i + 2] / 255
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            n += 1
            jas += luminancja(r, g, b)
            c = s * v
            chroma += c
            if c < 0.12:
                continue
            k = int(h * 36) % 36
            skora = 0.02 <= h <= 0.13 and 0.15 <= s <= 0.7 and v >= 0.3
            skory += skora
            hist[k] += c * (0.3 if skora else 1.0)
            if s >= 0.55 and v >= 0.3 and not skora:
                echo[k] += 1
    suma = sum(hist) or 1.0
    return {"hist": [x / suma for x in hist], "echo": [x / max(1, n) for x in echo],
            "jasnosc": jas / max(1, n), "barwnosc": chroma / max(1, n), "skora": skory / max(1, n)}


def dobierz_palete(an: dict, marka: str | None = None) -> list[str]:
    """Dwa akcenty filmu z kontrastu z materiałem: barwy dopełniające rozszczepione (główna barwa sceny ±150°:
    niebieskie niebo i morze → czerwień i złoto, zieleń → fiolet i róż, ciepłe drewno → turkus i niebieski,
    czerwień → zieleń i niebieski), z bonusem za kolor, który już jest mocnym akcentem
    w kadrze (czapka Mikołaja), z karą za barwy obecne w scenie i za barwy skóry i piasku, gdy jest ich w kadrze dużo
    (pomarańczowe i złote słowo ginie przy ciele i na plaży). Drugi akcent co najmniej PALETA_ROZNICA° dalej.
    Kolor marki (`marka`) jest pierwszy.
    Wariant (ciemny/jasny) wybiera `pokoloruj` z jasności tła pod blokami; tu wraca wariant ciemny."""
    hist, echo = an["hist"], an["echo"]
    gladki = [hist[k - 1] * 0.5 + hist[k] + hist[(k + 1) % 36] * 0.5 for k in range(36)]
    dom = max(range(36), key=gladki.__getitem__) * 10 + 5
    barwna = an["barwnosc"] >= 0.08 and max(gladki) >= 0.12        # scena ma wyraźną barwę (nie szare biuro)
    rozszczep = ((dom + 150) % 360, (dom + 210) % 360)
    skory = an.get("skora", 0.0)

    def ocena(nazwa: str) -> float:
        hue, _c, _j, smak = KOLORY[nazwa]
        konflikt = sum(hist[k] * max(0.0, 1 - _barwa_d(hue, k * 10 + 5) / 45) for k in range(36))
        dop = 1 - min(_barwa_d(hue, x) for x in rozszczep) / 180 if barwna else 0.5
        ech = min(1.0, sum(echo[k] for k in range(36) if _barwa_d(hue, k * 10 + 5) <= 20) / 0.004)
        skora = min(0.35, 3 * skory) if 12 <= hue <= 38 else min(0.15, 1.5 * skory) if 38 < hue <= 50 else 0.0
        return (1 - konflikt) + 0.8 * dop + 0.35 * ech - skora - smak

    ranking = sorted(KOLORY, key=lambda k: (-ocena(k), list(KOLORY).index(k)))
    if marka:
        r, g, b = _hex_rgb(marka)
        import colorsys  # noqa: PLC0415
        hm = colorsys.rgb_to_hsv(r, g, b)[0] * 360
        drugi = next((k for k in ranking if _barwa_d(KOLORY[k][0], hm) >= PALETA_ROZNICA), ranking[0])
        return [marka.upper(), KOLORY[drugi][1]]
    pierwszy = ranking[0]
    drugi = next(k for k in ranking[1:] if _barwa_d(KOLORY[k][0], KOLORY[pierwszy][0]) >= PALETA_ROZNICA)
    return [KOLORY[pierwszy][1], KOLORY[drugi][1]]


def rodzina(kolor: str) -> tuple[str, str] | None:
    """(ciemny, jasny) wariant rodziny, do której należy kolor palety; kolor spoza KOLORY (marka) = None."""
    return next(((d, j) for _, d, j, _s in KOLORY.values() if kolor.upper() in (d.upper(), j.upper())), None)


def jasnosc_pod(rgb: bytes, w: int, h: int, b: dict, W: int, H: int) -> float:
    """Średnia luminancja klatki pod ramką bloku (szacunek rozmiar_bloku), czyli tła, na którym stoi napis."""
    bw, bh = rozmiar_bloku(b, b.get("w", 0.62), W, H)
    x0, x1 = max(0, int((b["x"] - bw / 2) * w)), min(w, int(math.ceil((b["x"] + bw / 2) * w)))
    y0, y1 = max(0, int((b["y"] - bh / 2) * h)), min(h, int(math.ceil((b["y"] + bh / 2) * h)))
    suma, n = 0.0, 0
    for y in range(y0, max(y0 + 1, y1)):
        for x in range(x0, max(x0 + 1, x1)):
            i = (min(y, h - 1) * w + min(x, w - 1)) * 3
            suma += luminancja(rgb[i] / 255, rgb[i + 1] / 255, rgb[i + 2] / 255)
            n += 1
    return suma / max(1, n)


def pokoloruj(plan: dict, paleta: list[str], tla: dict[str, float]) -> dict:
    """Paleta na planie: wariant każdej rodziny (ciemny/jasny) z lepszym kontrastem z tłem pod blokami, a kolory
    rozpisane na zmianę (A, B, A, B…) po mocnych słowach: uderzenie w każdym bloku, który je ma, i najważniejsze słowo
    (waga 2) w co drugim bloku bez uderzenia, żeby film nie był biały z trzema kolorowymi słowami. Słowo, które
    w kolorze nie odcina się od tła pod blokiem, dostaje znacznik `plyta`: renderer kładzie pod nim płytkę w tym
    kolorze, a w motywie z obrysem zostaje obrys (ten sam kontrast; zmiana motywu w HQ nie zostawia płytek).
    Słowa z kolorem (poprawka człowieka) zostają i nie przesuwają kolejki. tla: id bloku → jasność tła pod nim (0–1)."""
    plan = json.loads(json.dumps(plan))
    jasnosci = sorted(tla.values()) or [0.4]
    mediana = lambda c: sorted(kontrast(luminancja(*_hex_rgb(c)), j) for j in jasnosci)[len(jasnosci) // 2]  # noqa: E731
    wybrane = [max(rodzina(k), key=mediana) if rodzina(k) else k.upper() for k in paleta]
    plan["paleta"] = wybrane
    n = bez = 0
    for b in plan["bloki"]:
        cel = [w for w in b["slowa"] if w["waga"] == 3]
        if not cel:
            bez += 1
            cel = [max((w for w in b["slowa"] if w["waga"] == 2), key=lambda w: len(w["tekst"]))] \
                if bez % 2 == 1 and any(w["waga"] == 2 for w in b["slowa"]) else []
        for w in cel:
            if "kolor" in w:
                continue
            kolor = wybrane[n % len(wybrane)]
            n += 1
            w["kolor"] = kolor
            tlo = tla.get(b["id"])
            if tlo is not None and "styl" not in w and b.get("uklad") != "za" \
                    and kontrast(luminancja(*_hex_rgb(kolor)), tlo) < KONTRAST_PLYTA:
                w["plyta"] = True
    return plan


def zmien_palete(plan: dict, nowa: list[str]) -> dict:
    """Nowa paleta i te same miejsca: słowa w kolorze starej pozycji palety dostają kolor nowej (jak w edytorze HQ)."""
    plan = json.loads(json.dumps(plan))
    stara = [str(x).upper() for x in plan.get("paleta") or []]
    mapa = {s: str(n).upper() for s, n in zip(stara, nowa) if s != str(n).upper()}
    for b in plan["bloki"]:
        for w in b["slowa"]:
            if str(w.get("kolor", "")).upper() in mapa:
                w["kolor"] = mapa[str(w["kolor"]).upper()]
    plan["paleta"] = [str(x).upper() for x in nowa]
    return plan


def probki_kadru(proj: dict, plan: dict, ile: int = 24) -> tuple[list[bytes], dict[str, float]]:
    """Małe klatki osi w chwilach bloków (najwyżej `ile`, równo) → (klatki do analizy sceny, jasność tła pod
    każdym blokiem z najbliższej klatki). Błąd ffmpeg = ([], {}): plan bez palety z kadru."""
    import maska as mk  # noqa: PLC0415  (klatki osi jak eksport; bez onnxruntime)
    cv = proj["canvas"]
    W, H = cv["w"], cv["h"]
    k = PALETA_BOK / max(W, H)
    w, h = max(8, round(W * k)), max(8, round(H * k))
    fps = float(cv["fps"])
    srodki = {b["id"]: (b["start"] + b["end"]) / 2 for b in plan["bloki"]}
    chwile = sorted(set(srodki.values()))
    if len(chwile) > ile:
        chwile = [chwile[round(i * (len(chwile) - 1) / (ile - 1))] for i in range(ile)]
    numery = sorted({int(t * fps) for t in chwile})
    try:
        klatki = dict(mk.klatki_osi(proj, numery, fps, w, h))
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"uwaga: nie czytam klatek do palety ({exc}); kolory z motywu", file=sys.stderr)
        return [], {}
    if not klatki:
        return [], {}
    tla = {}
    for b in plan["bloki"]:
        nr = min(klatki, key=lambda x: abs(x / fps - srodki[b["id"]]))
        tla[b["id"]] = round(jasnosc_pod(klatki[nr], w, h, b, W, H), 4)
    return list(klatki.values()), tla


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

def maska(film: Path, *args: str) -> str | None:
    """maska.py Pythonem narzędzi (onnxruntime z obrazu); błąd albo brak modelu = None i plan bez maski."""
    py = "/opt/jarvo/venv/bin/python" if Path("/opt/jarvo/venv/bin/python").exists() else sys.executable
    try:
        r = subprocess.run([py, str(HERE / "maska.py"), args[0], str(film), *args[1:]], capture_output=True, text=True,
                           timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"uwaga: maska osoby niedostępna ({exc}); typografia bez niej", file=sys.stderr)
        return None
    if r.returncode != 0:
        print(f"uwaga: maska osoby niedostępna ({(r.stderr or r.stdout).strip()[-240:]}); typografia bez niej",
              file=sys.stderr)
        return None
    return r.stdout


def sylwetki(film: Path, plan: dict) -> int:
    """Sylwetki osoby (maska.py klatki) pod każdy blok za osobą (warstwa „tyl”); policzone klatki zostają.
    Zwraca liczbę bloków z sylwetkami (bez nich eksport rysuje blok bez osoby przed nim)."""
    return sum(1 for b in plan["bloki"] if b["warstwa"] == "tyl"
               and maska(film, "klatki", "--od", f"{b['start']:.3f}", "--do", f"{b['end']:.3f}") is not None)


def cmd_plan(film: Path, a) -> int:
    proj = pr.load(film)
    cv = proj["canvas"]
    total = pr.total(proj)
    stary = ed.normalize_typo(proj.get("typo"), total)["bloki"]
    if stary and not a.nowy:                    # człowiek mógł go poprawić w edytorze HQ
        raise SystemExit(f"projekt ma już plan typografii ({len(stary)} bloków, może z poprawkami właściciela): "
                         f"popraw go (typografia.py pokaz {film} → popraw), od nowa tylko na wyraźną prośbę: --nowy")
    slowa, ciecia = slowa_osi(proj)
    if not slowa:
        raise SystemExit("brak mowy w nagraniu: typografia potrzebuje słów (sprawdź dźwięk albo transkrypcję)")
    plan = zbuduj_plan(slowa, ciecia, cv["w"], cv["h"], total, a.motyw, a.tempo, a.ziarno, a.akcent)
    za = 0
    if not a.bez_maski:
        opisy = maska(film, "opis", "--chwile", ",".join(f"{(b['start'] + b['end']) / 2:.3f}" for b in plan["bloki"]))
        if opisy is not None:
            plan = uloz_z_maska(plan, json.loads(opisy), cv["w"], cv["h"], total)
            proj["typo"] = plan
            pr.save(film, proj)                 # maska.py klatki liczy klucz osi z zapisanego projektu
            za = sylwetki(film, plan)
    klatki, tla = probki_kadru(proj, plan)
    paleta = [x.strip().upper() for x in a.paleta.split(",")] if a.paleta else \
        dobierz_palete(analiza_kadru(klatki), a.akcent) if klatki else None
    if paleta:
        plan = ed.normalize_typo(pokoloruj(plan, paleta, tla), total)
    proj["typo"] = plan
    if not a.zostaw_napisy:
        proj["texts"] = [x for x in proj.get("texts") or [] if not x.get("cap")]
    pr.save(film, proj)
    n_slow = sum(len(b["slowa"]) for b in plan["bloki"])
    print(f"Typografia: {len(plan['bloki'])} bloków, {n_slow} słów, motyw {plan['motyw']} · cięcia: {len(ciecia)}"
          + ("" if a.bez_maski else f" · za osobą: {za}")
          + (f" · paleta z kadru: {' '.join(plan['paleta'])}" if plan.get("paleta") else " · kolory z motywu"))
    print(f"Dalej: typografia.py pokaz {film} → popraw według znaczenia → typografia.py arkusz {film} → projekt.py render {film}")
    return 0


def opis_slowa(w: dict) -> str:
    extra = "".join(f" {k}={w[k]}" for k in ("kolor", "kroj", "styl", "glebia") if k in w) + (" płytka" if w.get("plyta") else "")
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
          f"{' · paleta ' + ' '.join(plan['paleta']) if plan.get('paleta') else ''}"
          f" · {len(plan['bloki'])} bloków · kadr {cv['w']}×{cv['h']}")
    for b in plan["bloki"]:
        lin: dict[int, list[str]] = {}
        for j, w in enumerate(b["slowa"]):
            lin.setdefault(w["linia"], []).append(f"{j}:{opis_slowa(w)}")
        extra = "".join([f" rot {b['rot']:+.0f}" if b["rot"] else "", f" tilt {b['tilt']:+.0f}" if b["tilt"] else "",
                         " ZA OSOBĄ" if b["warstwa"] == "tyl" else "", f" wyjście {b['wyjscie']}" if b.get("wyjscie") else ""])
        print(f"{b['id']} {b['start']:6.2f}–{b['end']:6.2f} {b['uklad']:8s} x{b['x']:.2f} y{b['y']:.2f} w{b['w']:.2f}{extra}"
              f"  |  {' / '.join(' '.join(v) for _k, v in sorted(lin.items()))}")
    print("\nWaga: [0] małe słowo funkcyjne, [1] zwykłe, [2] ważne (większe), [3] uderzenie (największe, kolor z palety,"
          " jedno na blok, około co trzeci blok).")
    print("Poprawki według znaczenia (skill typografia-edit): zmiany.json → typografia.py popraw <film> zmiany.json")
    return 0


POLA_BLOKU = ("start", "end", "uklad", "x", "y", "w", "rot", "tilt", "warstwa", "wejscie", "wyjscie", "rozmiar")
POLA_SLOWA = ("tekst", "waga", "linia", "glebia", "kolor", "kroj", "styl", "plyta", "wejscie", "wielkie", "skala", "t", "k")


def zastosuj(plan: dict, zmiany: dict, total: float) -> tuple[dict, list[str]]:
    """Poprawki z zmiany.json na planie; zwraca nowy plan (po walidacji) i listę ostrzeżeń."""
    plan = json.loads(json.dumps(plan))
    uwagi = []
    for k in ("motyw", "akcent"):
        if k in zmiany:
            plan[k] = zmiany[k]
    if isinstance(zmiany.get("paleta"), list):           # nowa paleta: słowa w starych kolorach idą za nią
        plan = zmien_palete(plan, zmiany["paleta"])
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
    tyl = sum(1 for b in plan["bloki"] if b["warstwa"] == "tyl")
    za = sylwetki(film, plan) if tyl else 0
    if za < tyl:
        uwagi.append(f"{tyl - za} z {tyl} bloków za osobą bez sylwetki (maska niedostępna): osoba nie zasłoni napisu")
    for u in uwagi:
        print(f"uwaga: {u}")
    print(f"Typografia: {len(plan['bloki'])} bloków po poprawkach" + (f" · za osobą: {za}" if tyl else ""))
    return 0


def cmd_sylwetki(film: Path, a) -> int:
    proj = pr.load(film)
    plan = ed.normalize_typo(proj.get("typo"), pr.total(proj))
    tyl = sum(1 for b in plan["bloki"] if b["warstwa"] == "tyl")
    if not tyl:
        print("Brak bloków za osobą (warstwa „tyl”): nie ma czego liczyć")
        return 0
    za = sylwetki(film, plan)
    print(f"Sylwetki: {za} z {tyl} bloków za osobą" + ("" if za == tyl else " (maska niedostępna: osoba nie zasłoni reszty)"))
    return 0 if za else 1


def cmd_paleta(film: Path, a) -> int:
    """Paleta z kadru na gotowym planie: układ, słowa i poprawki człowieka zostają, zmieniają się kolory uderzeń.
    Plan z paletą: słowa w starych kolorach palety idą za nową (jak w edytorze); bez palety: uderzenia bez własnego
    koloru dostają akcenty na zmianę. Akcent planu to kolor marki: zostaje pierwszy, chyba że --bez-akcentu."""
    proj = pr.load(film)
    total = pr.total(proj)
    plan = ed.normalize_typo(proj.get("typo"), total)
    if not plan["bloki"]:
        raise SystemExit("brak planu typografii: typografia.py plan <film>")
    if a.bez_akcentu:
        plan.pop("akcent", None)
    marka = a.akcent or plan.get("akcent")
    if a.akcent:
        plan["akcent"] = a.akcent
    klatki, tla = probki_kadru(proj, plan)
    if a.paleta:
        paleta = [x.strip().upper() for x in a.paleta.split(",")]
    elif klatki:
        paleta = dobierz_palete(analiza_kadru(klatki), marka)
    else:
        raise SystemExit("nie czytam klatek filmu: podaj paletę sam (--paleta #RRGGBB,#RRGGBB)")
    stara = plan.get("paleta")
    plan = pokoloruj(plan, paleta, tla)         # paleta planu = warianty z tła pod blokami
    if stara:                                    # słowa w kolorach starej palety idą za nową, miejsce po miejscu
        plan = zmien_palete({**plan, "paleta": stara}, plan["paleta"])
    plan = ed.normalize_typo(plan, total)
    proj["typo"] = plan
    pr.save(film, proj)
    kolory = sorted({w["kolor"] for b in plan["bloki"] for w in b["slowa"] if w.get("kolor")})
    plytki = sum(1 for b in plan["bloki"] for w in b["slowa"] if w.get("styl") == "tlo")
    print(f"Paleta: {' '.join(plan['paleta'])}{' (z kadru)' if not a.paleta else ''}"
          + (f" · marka {plan['akcent']}" if plan.get("akcent") else "")
          + f" · kolory słów: {' '.join(kolory) or 'brak'} · płytki: {plytki}")
    print(f"Dalej: typografia.py arkusz {film} → oceń kolory na klatkach → projekt.py render {film}")
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
    wy = lambda b: WYJSCIE_CZAS.get(b.get("wyjscie") or WYJSCIE_CIECIE.get(plan.get("motyw"), "zanik"), 0.16)  # noqa: E731
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
    pr.arkusz_typografii(proj, plan, chwile, out, film)
    print(f"Arkusz: {out} ({len(chwile)} klatek; oceń vision_analyze: czytelność, twarz, strefy UI, sens akcentów)")
    print(f"MEDIA:{out}")
    return 0


def blok_wzorcowy(plan: dict) -> dict:
    """Blok do arkusza stylów: przed osobą, bez ręcznego kroju i stylu słów (te nie zmieniają się z motywem),
    z uderzeniem i z kilkoma słowami (widać krój główny, mały i uderzenie)."""
    def ocena(b: dict) -> tuple:
        wagi = {w["waga"] for w in b["slowa"]}
        reczne = any("kroj" in w or "styl" in w for w in b["slowa"])
        return (b["warstwa"] != "tyl", not reczne, 3 in wagi, len(wagi), min(len(b["slowa"]), 4), b["end"] - b["start"])
    return max(plan["bloki"], key=ocena)


def cmd_style(film: Path, a) -> int:
    import narzedzia as nz
    nz.wymagaj_playwright(__file__, "JARVO_TYPO_REEXEC", "arkusz rysuje przeglądarka")   # re-exec TEGO skryptu
    proj = pr.load(film)
    plan = ed.normalize_typo(proj.get("typo"), pr.total(proj))
    if not plan["bloki"]:
        raise SystemExit("brak planu typografii: typografia.py plan <film>")
    motywy = [x.strip() for x in a.motywy.split(",")] if a.motywy else list(MOTYWY)
    zle = [x for x in motywy if x not in MOTYWY]
    if zle:
        raise SystemExit(f"nie ma motywu: {', '.join(zle)} (są: {', '.join(MOTYWY)})")
    b = next((x for x in plan["bloki"] if x["id"] == a.blok), None) if a.blok else blok_wzorcowy(plan)
    if b is None:
        raise SystemExit(f"nie ma bloku {a.blok} (numery: typografia.py pokaz {film})")
    jeden = {**plan, "bloki": [b]}
    t = chwile_arkusza(jeden, 1)[0]
    warianty = [(f"{k} (teraz)" if k == plan["motyw"] else k, {**jeden, "motyw": k}) for k in motywy]
    out = Path(a.out) if a.out else film.with_name(f"{film.stem}.style.jpg")
    pr.arkusz_typografii(proj, plan, [t], out, film, warianty=warianty)
    print(f"Style: {out} · blok {b['id']} „{' '.join(w['tekst'] for w in b['slowa'])}” w {t:.2f} s · motywy: {', '.join(motywy)}")
    print("Zmiana stylu całego filmu: zmiany.json {\"motyw\": \"<nazwa>\"} → typografia.py popraw (układ, kolory i poprawki"
          " zostają), albo karta stylu w edytorze HQ.")
    print(f"MEDIA:{out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("plan", help="reżyser z reguł: plan typografii w projekcie")
    sp.add_argument("film")
    sp.add_argument("--motyw", choices=MOTYWY, default="czysty")
    sp.add_argument("--akcent", help="kolor marki z brand kitu, #RRGGBB: pierwszy w palecie, drugi z kadru")
    sp.add_argument("--paleta", help="paleta zamiast tej z kadru: #RRGGBB,#RRGGBB (np. na prośbę właściciela)")
    sp.add_argument("--tempo", choices=tuple(TEMPO), default="normalne")
    sp.add_argument("--ziarno", type=int, default=0, help="inny wariant układów (ten sam numer = ten sam plan)")
    sp.add_argument("--zostaw-napisy", action="store_true", help="nie usuwaj zwykłych napisów z projektu")
    sp.add_argument("--bez-maski", action="store_true", help="bez maski osoby (MODNet): miejsca domyślne, bez „za osobą”")
    sp.add_argument("--nowy", action="store_true", help="ułóż od nowa, choć projekt ma już plan (poprawki człowieka giną)")
    sp.set_defaults(fn=cmd_plan)
    sp = sub.add_parser("sylwetki", help="sylwetki osoby pod bloki za osobą")
    sp.add_argument("film")
    sp.set_defaults(fn=cmd_sylwetki)
    sp = sub.add_parser("paleta", help="kolory z kadru na gotowym planie (układ i poprawki zostają)")
    sp.add_argument("film")
    sp.add_argument("--paleta", help="własna paleta zamiast tej z kadru: #RRGGBB,#RRGGBB")
    sp.add_argument("--akcent", help="kolor marki, #RRGGBB: pierwszy w palecie")
    sp.add_argument("--bez-akcentu", action="store_true", help="usuń akcent planu (to nie był kolor marki)")
    sp.set_defaults(fn=cmd_paleta)
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
    sp = sub.add_parser("style", help="ten sam blok filmu w każdym motywie (do wyboru stylu)")
    sp.add_argument("film")
    sp.add_argument("-o", "--out")
    sp.add_argument("--blok", help="id bloku (domyślnie blok z uderzeniem i kilkoma słowami)")
    sp.add_argument("--motywy", help="tylko te motywy, po przecinku")
    sp.set_defaults(fn=cmd_style)
    sp = sub.add_parser("usun", help="usuń plan typografii")
    sp.add_argument("film")
    sp.set_defaults(fn=cmd_usun)
    a = ap.parse_args(argv)
    film = Path(a.film).resolve()
    if not film.is_file():
        raise SystemExit(f"nie ma pliku: {film}")
    if getattr(a, "akcent", None) and not re.match(r"^#[0-9A-Fa-f]{6}$", a.akcent):
        raise SystemExit("--akcent: kolor #RRGGBB")
    if getattr(a, "paleta", None) and not all(re.match(r"^#[0-9A-Fa-f]{6}$", x.strip()) for x in a.paleta.split(",")):
        raise SystemExit("--paleta: kolory #RRGGBB po przecinku")
    return a.fn(film, a)


if __name__ == "__main__":
    sys.exit(main())
