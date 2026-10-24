#!/usr/bin/env python3
"""Gramatyki explainera: odcinek animacji do filmu z lektorem z jednego pliku spec (JSON), silnikiem kanwy
huashu-art-motion (MIT) pod polską nakładką, renderem i kontrolą Jarva.

    gramatyka.py lista [--json]                                    # 8 gramatyk z klipem + prowadzący (tylko wzór)
    gramatyka.py szablon wykresy [--format 9:16] [-o out/wideo/src/klip-wykres/spec.json]
    gramatyka.py sprawdz spec.json [--os os_czasu.json] [--fakty fakty.json]   # kod 1 = błędy
    gramatyka.py strona spec.json                                  # spec → <spec>.html obok (kontrakt jarvo)
    gramatyka.py render spec.json --klatki 0.5,2,4 [--arkusz a.jpg]   # stopklatki do oceny
    gramatyka.py render spec.json -o out/wideo/klip.mp4 [--alfa]   # .mp4 albo z --alfa .mov (ProRes 4444) / .webm
    gramatyka.py pomiar spec.json [--platforma tiktok]             # html_wideo.py pomiar strony klipu
    gramatyka.py wzor wykresy [--czasy 1,3,5,7] [--arkusz out/wideo/wzor-wykresy.jpg]   # ich film pokazowy

Spec ma klucze oryginału (`grammar`, `duration`, `fps`, `width`, `height`, `safe`, `alpha`, `data`, `cues` z `at`,
`kind`, `text`, `sub`, `image`, `data`, `dur`), bo czyta go ich `clip.js`; karta każdej gramatyki i kontrakt:
skill `gramatyki-explainera`. Dodatki Jarva (zdejmowane przed stroną):
  `grammar`  nazwa po polsku (`wykresy`) albo id z kodu (`t3_finance_chart`);
  cue `slowo` (+ `nth` od 1, `offset` s) zamiast `at`: chwila słowa lektora z `os_czasu.json` (`film.py narracja`),
             szukana w oknie klipu; fraza = kilka słów, `*` na końcu = początek słowa (odmiana);
  `od`       gdzie klip zaczyna się na osi lektora: sekundy albo nazwa chwili (`u3`, `r2`, `u3.mowa`), domyślnie 0;
  `do`       koniec (sekundy albo chwila) zamiast `duration`;
  `os`       ścieżka os_czasu.json (domyślnie obok spec albo katalog wyżej);
  `postac`   kolory postaci gramatyki historyjki {skora, linia, wlosy, koszulka, spodnie, buty} (marka klienta).
Domyślne Jarva: wykresy `upDown: "us"` (zielony = wzrost), historyjka z lektorem: usta z obwiedni głosu (`VO_ENV`).

Jeden klip = jeden katalog (`out/wideo/src/klip-<nazwa>/spec.json` + obrazy obok): pomiar i jego odcisk są
per katalog strony, a `fakty.json` i `os_czasu.json` znajdują się w nim albo katalog wyżej. Kod wyjścia: 0 ok,
1 błędy w spec albo w renderze, 2 złe wejście.
"""

from __future__ import annotations

import argparse
import array
import copy
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import narzedzia as nz  # noqa: E402
import wideo_lib as wl  # noqa: E402

# nazwa w Jarvie → id w kodzie silnika, rodzaje cue (kind), które gramatyka rysuje, i to, co czyta `dur`
GRAMATYKI: dict[str, dict] = {
    "kurzgesagt": {"id": "y1_kurzgesagt", "kinds": ["title", "point", "highlight", "enter"], "dur": ["enter"],
                   "opis": "płaska popularnonaukowa: skala, „co jest w środku”, mechanizm; kamera przelatuje między skalami"},
    "vox": {"id": "y2_vox", "kinds": ["image", "clip", "title", "point", "highlight"], "dur": [],
            "opis": "kolaż na biurku: argument z prawdziwymi zrzutami, archiwami, cytatami; kamera jak oko reportera"},
    "tablica": {"id": "y3_whiteboard", "kinds": ["title", "point", "draw", "image", "highlight"], "dur": [],
                "opis": "rysowana tablica: zdanie powiedziane = zdanie napisane, łańcuch rozumowania, odjazd na końcu"},
    "historyjka": {"id": "y4_storytime", "kinds": ["point", "title", "highlight", "react", "insert"],
                   "dur": ["react", "insert"],
                   "opis": "prosta postać opowiada: przeżycie, wpadka, puenta na zbliżeniu reakcji"},
    "kinetyczna": {"id": "y5_kinetic_type", "kinds": ["title", "point", "number", "highlight"], "dur": [],
                   "opis": "typografia kinetyczna: lista, etapy, zdanie-puenta, otwarcie liczbą, plansze rozdziałów"},
    "3b1b": {"id": "t1_3b1b", "kinds": ["title", "equation", "point", "line", "highlight"],
             "dur": ["title", "point", "equation", "line"],
             "opis": "3Blue1Brown: czarne tło, przekształcenie pojęcia w następne, wzory, kolor = pojęcie"},
    "prezentacja": {"id": "t2_keynote_ui", "kinds": ["title", "card", "step", "image", "highlight", "number"], "dur": [],
                    "opis": "interfejs z premiery: produkt, funkcje, kroki samouczka na zrzutach w szklanych kartach"},
    "wykresy": {"id": "t3_finance_chart", "kinds": ["title", "bar", "line", "candle", "highlight", "number"],
                "dur": ["bar", "line", "candle"],
                "opis": "wykresy finansowe: najpierw osie, potem dane, jedno oznaczenie; liczby uczciwe i ze źródłem"},
}
PROWADZACY = {"id": "y6_presenter_explainer",
              "opis": "rysunkowy prowadzący łączy kartki, wykresy i słowa-klucze; tylko wzór i metoda, bez klipu",
              "kod": "scripts/engine/reference_films/spacex/spacex_lin"}
ID_NAZWA = {g["id"]: n for n, g in GRAMATYKI.items()}
LIBY = ["fonts", "util", "paint", "kit", "motion", "camera", "diagram", "typo", "chart", "ui", "collage", "toon"]
NUMBER_MIN = {"kinetyczna": 0.7}            # number: liczenie startuje w at − 0,9 s (kinetyczna − 0,7 s)
DODATKI = ("od", "do", "os", "postac")
POLA_CUE_JARVO = ("slowo", "nth", "offset")
# dół nad pasem napisów lektora (wideo_lib.PAS_NAPISOW: 16:9 250 px, 9:16 700 px), w 9:16 góra pod zakładki TikToka
# (131 px); lewo/prawo gramatyki prawie nie czytają
FORMATY = {"16:9": (1920, 1080, {"bottom": wl.margines_napisow(1920, 1080)}),
           "9:16": (1080, 1920, {"top": 140, "bottom": wl.margines_napisow(1080, 1920)})}
CJK = re.compile(r"[⺀-鿿豈-﫿　-〿＀-￯]")
BRZEG = "„”\"'«»()[]{}.,;:!?…–—-‒"
DANE_PRZYKLADOWE = re.compile(r"dane\s+przykładowe", re.I)

# Szablony po polsku (dane zmyślone mają „dane przykładowe”); czasy dla 16:9 i 9:16 te same.
SZABLONY: dict[str, dict] = {
    "kurzgesagt": {"duration": 7, "data": {"center": "Wyszukiwarka", "flow": True}, "cues": [
        {"at": 0, "kind": "title", "text": "Co się dzieje, gdy szukasz"},
        {"at": 1.2, "kind": "point", "text": "Pobieranie"},
        {"at": 2, "kind": "point", "text": "Indeks"},
        {"at": 2.8, "kind": "point", "text": "Ranking"},
        {"at": 4.6, "kind": "highlight", "data": {"index": 2}}]},
    "vox": {"duration": 8, "cues": [
        {"at": 0, "kind": "title", "text": "Trzy ślady podwyżki"},
        {"at": 2.6, "kind": "point", "text": "Najpierw pismo od dostawcy"},
        {"at": 5, "kind": "point", "text": "Po dwóch tygodniach nowy cennik"}]},
    "tablica": {"duration": 8, "cues": [
        {"at": 0, "kind": "title", "text": "Po co pisać testy"},
        {"at": 1.6, "kind": "point", "text": "Pilnują kodu przy zmianach"},
        {"at": 3.8, "kind": "draw", "text": "Kontrola", "data": {"icon": "check"}},
        {"at": 6, "kind": "highlight", "data": {"index": 0}}]},
    "historyjka": {"duration": 7, "cues": [
        {"at": 0.2, "kind": "point", "text": "Poprosiłem AI o literówkę", "sub": "Popraw jedną literkę!"},
        {"at": 2, "kind": "insert", "sub": "Popraw literówkę w tytule", "text": "40 plików",
         "data": {"hit": 3.4, "app": "Asystent AI", "count": 40, "unit": " plików"}},
        {"at": 4.6, "kind": "react"},
        {"at": 5.9, "kind": "highlight", "data": {"mark": "?"}}]},
    "kinetyczna": {"duration": 5, "cues": [
        {"at": 0, "kind": "title", "text": "Wolno znaczy szybko"},
        {"at": 1.6, "kind": "point", "text": "Wolno", "sub": "Jedna zmiana naraz", "data": {"key": "Jedna zmiana"}},
        {"at": 3.3, "kind": "point", "text": "Szybko", "sub": "Działa za pierwszym razem",
         "data": {"key": "za pierwszym razem"}}]},
    "3b1b": {"duration": 6, "cues": [
        {"at": 0, "kind": "title", "text": "Uwaga to średnia ważona"},
        {"at": 1.2, "kind": "equation", "text": "softmax(QK)V"},
        {"at": 3, "kind": "point", "text": "Najpierw licz podobieństwo"},
        {"at": 4.2, "kind": "point", "text": "Potem sumuj według podobieństwa"}]},
    "prezentacja": {"duration": 6, "data": {"title": "Trzy nowe funkcje"}, "cues": [
        {"at": 0, "kind": "title"},
        {"at": 1.8, "kind": "card", "text": "Dyktowanie", "sub": "Mówisz, a tekst się pisze", "data": {"icon": "wave"}},
        {"at": 2.6, "kind": "card", "text": "Pamięć", "sub": "Pamięta, co mówiłeś ostatnio", "data": {"icon": "memory"}},
        {"at": 3.4, "kind": "card", "text": "Automatyzacja", "sub": "Klika za ciebie resztę", "data": {"icon": "agent"}}]},
    "wykresy": {"duration": 6, "data": {
        "title": "Firma A wydaje na badania najwięcej", "unit": "nakłady na badania w 2024 r., mln zł",
        "source": "Źródło: dane przykładowe", "badge": "dane przykładowe", "chart": "bar", "upDown": "us", "decimals": 0,
        "series": [{"label": "A", "value": 120}, {"label": "B", "value": 86}, {"label": "C", "value": 43}]}, "cues": [
        {"at": 0, "kind": "title"},
        {"at": 1, "kind": "bar"},
        {"at": 3.5, "kind": "highlight", "data": {"index": 0}, "text": "najwięcej"}]},
}


# ---------------------------------------------------------------- spec

def gramatyka(spec: dict) -> str | None:
    """Nazwa w Jarvie z `grammar` (nazwa albo id z kodu); None = nieznana."""
    g = str(spec.get("grammar") or "")
    return g if g in GRAMATYKI else ID_NAZWA.get(g)


def norm(slowo: str) -> str:
    return slowo.strip().strip(BRZEG).replace(" ", " ").lower()


def wczytaj(plik: Path) -> dict:
    try:
        spec = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"✗ {plik}: {e}") from e
    if not isinstance(spec, dict):
        raise SystemExit(f"✗ {plik}: spec to obiekt JSON")
    return spec


def znajdz_os(spec: dict, plik: Path, os_cli: str | None) -> Path | None:
    if os_cli:
        return Path(os_cli)
    if spec.get("os"):
        p = Path(spec["os"])
        return p if p.is_absolute() else plik.parent / p
    for d in (plik.parent, plik.parent.parent):
        if (d / "os_czasu.json").is_file():
            return d / "os_czasu.json"
    return None


def slowa_osi(os_: dict) -> list[dict]:
    return [w for z in os_.get("zdania") or [] for w in z.get("slowa") or []]


def chwila(wartosc, os_: dict | None, co: str, bledy: list[str]) -> float | None:
    if isinstance(wartosc, (int, float)) and not isinstance(wartosc, bool):
        return float(wartosc)
    if isinstance(wartosc, str):
        if os_ is None:
            bledy.append(f"`{co}`: „{wartosc}” to chwila lektora, a nie ma os_czasu.json (film.py narracja, `os` albo --os)")
            return None
        if wartosc in (os_.get("chwile") or {}):
            return float(os_["chwile"][wartosc])
        bledy.append(f"`{co}`: nieznana chwila „{wartosc}” w os_czasu.json")
        return None
    bledy.append(f"`{co}` to sekundy albo nazwa chwili z os_czasu.json")
    return None


def znajdz_slowo(slowa: list[dict], fraza: str, nth: int, od: float, do: float | None) -> float | None:
    """Początek nth (od 1) wystąpienia frazy lektora w oknie klipu; `*` na końcu = początek słowa."""
    szukane = [norm(s) for s in fraza.split()]
    prefiks = szukane and szukane[-1].endswith("*")
    if prefiks:
        szukane[-1] = szukane[-1].rstrip("*")
    okno = [w for w in slowa if w["start"] >= od - 0.05 and (do is None or w["start"] < do)]
    ile = 0
    for i in range(len(okno) - len(szukane) + 1):
        kawalek = [norm(w["tekst"]) for w in okno[i:i + len(szukane)]]
        if kawalek[:-1] == szukane[:-1] and (kawalek[-1].startswith(szukane[-1]) if prefiks else kawalek[-1] == szukane[-1]):
            ile += 1
            if ile == nth:
                return float(okno[i]["start"])
    return None


def teksty_cue(q: dict) -> list[str]:
    d = q.get("data") if isinstance(q.get("data"), dict) else {}
    out = [q.get("text"), q.get("sub"), d.get("text"), d.get("label"), d.get("key"), d.get("app")]
    return [str(x) for x in out if isinstance(x, (str, int, float)) and not isinstance(x, bool)]


def teksty_data(d: dict) -> list[str]:
    out = [d.get(k) for k in ("title", "unit", "source", "badge", "eyebrow", "subtitle", "center")]
    h = d.get("highlight")
    if isinstance(h, dict):
        out += [h.get("text"), h.get("sub")]
    out += [s.get("label") for s in d.get("series") or [] if isinstance(s, dict)]
    return [str(x) for x in out if isinstance(x, (str, int, float)) and not isinstance(x, bool)]


def liczby_danych(spec: dict) -> list[str]:
    """Wartości liczbowe, które widz zobaczy jako liczby: słupki i świece, wielkie liczby, licznik wstawki."""
    out = []
    for s in (spec.get("data") or {}).get("series") or []:
        if isinstance(s, dict):
            out += [s[k] for k in ("value", "o", "h", "l", "c") if isinstance(s.get(k), (int, float))]
    for q in spec.get("cues") or []:
        d = q.get("data") if isinstance(q, dict) and isinstance(q.get("data"), dict) else {}
        out += [d[k] for k in ("value", "count") if isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool)]
    return [f"{v:g}".replace(".", ",") for v in out]


def rozwiaz(spec: dict, plik: Path, os_cli: str | None = None, fakty_cli: str | None = None) -> dict:
    """Spec Jarva → spec dla clip.js + raport: błędy, ostrzeżenia, czasy cue (slowo → at), gdzie oś i fakty."""
    bledy, ostrz = [], []
    out = copy.deepcopy(spec)
    nazwa = gramatyka(spec)
    if spec.get("grammar") in ("prowadzacy", PROWADZACY["id"]):
        bledy.append("`prowadzacy` nie ma klipu: własna strona filmu (karta prowadzacy.md, wzór w kodzie silnika)")
    elif nazwa is None:
        bledy.append(f"nieznana gramatyka „{spec.get('grammar')}” ({', '.join(GRAMATYKI)})")
    g = GRAMATYKI.get(nazwa or "", {"kinds": [], "dur": [], "id": spec.get("grammar")})
    out["grammar"] = g["id"]
    os_path = znajdz_os(spec, plik, os_cli)
    os_ = None
    if os_path is not None:
        try:
            os_ = json.loads(Path(os_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            bledy.append(f"os_czasu.json {os_path}: {e}")
    od = chwila(spec.get("od", 0), os_, "od", bledy) or 0.0
    dur = spec.get("duration")
    if dur is None and "do" in spec:
        do = chwila(spec["do"], os_, "do", bledy)
        dur = round(do - od, 3) if do is not None else None
    if not isinstance(dur, (int, float)) or isinstance(dur, bool) or dur <= 0:
        bledy.append("`duration` (s) > 0 albo `do` (koniec na osi lektora)")
        dur = None
    else:
        out["duration"] = dur
    fps = spec.get("fps", 30)
    w, h = spec.get("width", 1920), spec.get("height", 1080)
    for k, v in (("fps", fps), ("width", w), ("height", h)):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            bledy.append(f"`{k}` to liczba > 0")
    cues = spec.get("cues")
    if not isinstance(cues, list) or not cues:
        bledy.append("`cues`: lista co najmniej jednego cue")
        cues = []
    slowa = slowa_osi(os_) if os_ else []
    nowe, czasy = [], []
    for i, q in enumerate(cues):
        if not isinstance(q, dict):
            bledy.append(f"cue {i + 1}: obiekt JSON")
            continue
        q2 = {k: v for k, v in q.items() if k not in POLA_CUE_JARVO}
        kind = q.get("kind")
        etyk = f"cue {i + 1} ({kind})"
        if nazwa and kind not in g["kinds"]:
            bledy.append(f"{etyk}: gramatyka {nazwa} nie zna rodzaju „{kind}” i nic nie narysuje ({', '.join(g['kinds'])})")
        if "slowo" in q:
            if os_ is None:
                bledy.append(f"{etyk}: `slowo` bez os_czasu.json (film.py narracja … --os, `os` w spec albo --os)")
            else:
                nth = q.get("nth", 1)
                t = znajdz_slowo(slowa, str(q["slowo"]), nth if isinstance(nth, int) and nth > 0 else 1, od,
                                 od + dur if dur else None)
                if t is None:
                    blisko = [w["tekst"] for w in slowa if w["start"] >= od - 0.05 and (dur is None or w["start"] < od + dur)]
                    bledy.append(f"{etyk}: słowo „{q['slowo']}” (wystąpienie {nth}) nie pada w lektorze w oknie klipu "
                                 f"{od:g}–{od + (dur or 0):g} s; słowa w oknie: {' '.join(blisko[:24])}")
                else:
                    if "at" in q:
                        ostrz.append(f"{etyk}: ma i `at`, i `slowo`: liczy się `slowo`")
                    q2["at"] = round(t + float(q.get("offset", 0) or 0) - od, 3)
        elif not isinstance(q.get("at"), (int, float)) or isinstance(q.get("at"), bool):
            bledy.append(f"{etyk}: brak `at` (s) albo `slowo`")
        at = q2.get("at")
        if isinstance(at, (int, float)) and not isinstance(at, bool):
            if at < 0:
                bledy.append(f"{etyk}: at = {at:g} s, przed początkiem klipu (słowo przed `od`?)")
            elif dur and at > dur + 1e-9:
                bledy.append(f"{etyk}: at = {at:g} s po końcu klipu ({dur:g} s): clip.js go odrzuci")
            if kind == "number" and at < NUMBER_MIN.get(nazwa or "", 0.9):
                ostrz.append(f"{etyk}: liczba staje w at = {at:g} s, a liczy od at − {NUMBER_MIN.get(nazwa or '', 0.9):g} s: "
                             "w pierwszej klatce będzie już przewinięta")
            czasy.append((at, etyk))
        if "dur" in q and nazwa and kind not in g["dur"]:
            ostrz.append(f"{etyk}: `dur` jest tu ignorowane (czytają je: {', '.join(g['dur']) or 'nic w tej gramatyce'})")
        if q.get("image"):
            img = str(q["image"])
            if re.match(r"https?:", img):
                ostrz.append(f"{etyk}: obraz z sieci ({img}): render offline go nie pobierze, zapisz plik obok spec")
            elif not img.startswith("data:"):
                p = Path(img) if Path(img).is_absolute() else plik.parent / img
                if not p.is_file():
                    bledy.append(f"{etyk}: brak obrazu {img}")
                elif plik.parent.resolve() not in p.resolve().parents:
                    bledy.append(f"{etyk}: obraz {img} spoza katalogu spec: skopiuj go obok spec")
        nowe.append(q2)
    out["cues"] = nowe
    for k in DODATKI:
        out.pop(k, None)
    data = out.setdefault("data", {}) if isinstance(out.get("data", {}), dict) else None
    if data is None:
        bledy.append("`data` to obiekt")
        data = {}
    # zasady gramatyk sprawdzalne bez renderu
    czasy.sort()
    for (a, e1), (b, e2) in zip(czasy, czasy[1:]):
        if b - a < 0.3:
            ostrz.append(f"{e1} i {e2} w odstępie {b - a:.2f} s: jeden punkt uwagi naraz (zasada 5)")
    if nazwa == "wykresy":
        if data.get("upDown") == "cn":
            ostrz.append("wykresy: upDown „cn” (czerwony = wzrost); u nas zielony = wzrost (`us`)")
        data.setdefault("upDown", "us")
        if sum(1 for q in nowe if q.get("kind") == "highlight") > 1:
            ostrz.append("wykresy: liczy się tylko pierwszy `highlight`; dwa wnioski = dwa klipy")
    if nazwa == "historyjka":
        for q in nowe:
            hit = (q.get("data") or {}).get("hit") if isinstance(q.get("data"), dict) else None
            if isinstance(hit, (int, float)) and dur and not 0 <= hit <= dur:
                bledy.append(f"historyjka: data.hit = {hit:g} s poza klipem (sekundy bezwzględne klipu, 0–{dur:g})")
    safe = spec.get("safe") or {}
    if isinstance(h, (int, float)) and isinstance(w, (int, float)) and w > 0 and h > 0 \
            and (safe.get("bottom") or 0) < wl.margines_napisow(w, h):
        pas = wl.pas_napisow(w, h)
        ostrz.append(f"{'pion' if h > w else 'poziom'} bez `safe.bottom` ≥ {wl.margines_napisow(w, h)}: pas napisów "
                     f"lektora (y {pas[1]:.0f}–{pas[3]:.0f} px) wejdzie na treść")
    # tekst: po polsku, bez znaków CJK (kroje nakładki ich nie mają)
    teksty = teksty_data(data) + [t for q in nowe for t in teksty_cue(q)]
    for t in teksty:
        if CJK.search(t):
            bledy.append(f"chiński znak w tekście „{t[:40]}”: wszystko po polsku")
        elif len(t) > 90:
            ostrz.append(f"długi tekst w kadrze ({len(t)} znaków): „{t[:40]}…”; jedno krótkie zdanie, reszta mówi lektor")
    # liczby kontra brief Sherlocka
    przykladowe = any(DANE_PRZYKLADOWE.search(t) for t in teksty)
    fakty_path = Path(fakty_cli) if fakty_cli else wl.znajdz_fakty(plik.parent)
    liczby = teksty + liczby_danych(out)
    if przykladowe:
        pass
    elif fakty_path is None:
        if any(wl.sprawdz_liczby(t, set(), set()) for t in liczby):
            ostrz.append("liczby na ekranie bez fakty.json (brief Sherlocka): dopisz źródło albo oznacz „dane przykładowe”")
    else:
        try:
            pewne, niepewne = wl.liczby_faktow(json.loads(fakty_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as e:
            bledy.append(f"fakty.json {fakty_path}: {e}")
            pewne, niepewne = set(), set()
        for t in liczby:
            for zapis, rodzaj in wl.sprawdz_liczby(t, pewne, niepewne):
                (bledy if rodzaj == "niepewna" else ostrz).append(
                    f"liczba „{zapis}” " + ("jest na liście niepewnych w fakty.json" if rodzaj == "niepewna"
                                            else "bez źródła w fakty.json") + f" („{t[:40]}”)")
    return {"spec": out, "gramatyka": nazwa, "bledy": bledy, "ostrzezenia": ostrz, "od": od,
            "os": Path(os_path).as_posix() if os_path else None, "os_dane": os_,
            "fakty": Path(fakty_path).as_posix() if fakty_path else None,
            "dane_przykladowe": przykladowe,
            "cue": [{"kind": q.get("kind"), "at": q.get("at"), **({"slowo": c["slowo"]} if "slowo" in c else {})}
                    for q, c in zip(nowe, [c for c in cues if isinstance(c, dict)])]}


# ---------------------------------------------------------------- strona

def obwiednia_lektora(os_: dict, os_path: Path, od: float, dur: float, fps: float) -> dict | None:
    """window.VO_ENV = {fps, a}: RMS głosu w oknach klatki (0..1, 95. percentyl = 1), czas klipu od `od`."""
    lektor = os_.get("lektor")
    if not lektor:
        return None
    p = Path(lektor)
    if not p.is_absolute():
        p = next((c for c in (os_path.parent / p.name, os_path.parent / p, Path.cwd() / p) if c.is_file()), p)
    if not p.is_file():
        return None
    sr = 8000
    raw = subprocess.run([wl.need("ffmpeg"), "-nostdin", "-v", "error", "-ss", f"{od:.3f}", "-t", f"{dur:.3f}", "-i", str(p),
                          "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    pcm = array.array("h")
    pcm.frombytes(raw[: len(raw) - len(raw) % 2])
    n, hop = int(round(dur * fps)), sr / fps
    env = []
    for i in range(n):
        kawalek = pcm[int(i * hop):int((i + 1) * hop)]
        env.append(math.sqrt(sum(x * x for x in kawalek) / len(kawalek)) if kawalek else 0.0)
    if not env or max(env) <= 0:
        return None
    top = sorted(env)[int(len(env) * 0.95)] or max(env)
    return {"fps": fps, "a": [round(min(1.0, v / top), 3) for v in env]}


STRONA = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><title>{tytul}</title>
<!-- gramatyka.py strona: zrobiona ze spec {spec}; nie edytuj, popraw spec i zrób stronę od nowa -->
<style>html,body{{margin:0;background:{tlo};overflow:hidden}}canvas{{display:block}}#ui{{display:none}}</style></head>
<body><canvas id="c" width="{w}" height="{h}"></canvas>
<div id="ui"><input id="scrub" type="range"><span id="tt"></span></div>
{skrypty}
<script src="/_lib/jarvo/huashu_pl.js"></script>
<script>
{dodatki}window.CLIP_SPEC = {dane};
</script>
<script src="/_lib/huashu/clip.js"></script>
</body></html>
"""


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def strona(plik: Path, r: dict, alfa: bool = False) -> Path:
    """Strona klipu w kontrakcie jarvo obok spec (<spec>.html): biblioteki z /_lib/huashu/, nakładka, CLIP_SPEC."""
    spec = copy.deepcopy(r["spec"])
    if alfa:
        spec["alpha"] = True
    dodatki = ""
    postac = wczytaj(plik).get("postac")
    if isinstance(postac, dict):
        dodatki += f"window.POSTAC = {_js(postac)};\n"
    if r["gramatyka"] == "historyjka" and r["os_dane"] and r["os"]:
        env = obwiednia_lektora(r["os_dane"], Path(r["os"]), r["od"], spec["duration"], spec.get("fps", 30))
        if env:
            dodatki += f"window.VO_ENV = {_js(env)};\n"
            r["vo_env"] = True
    out = plik.with_suffix(".html")
    out.write_text(STRONA.format(
        tytul=f"{r['gramatyka']} · {plik.parent.name}", spec=plik.name, tlo="transparent" if spec.get("alpha") else "#000",
        w=spec.get("width", 1920), h=spec.get("height", 1080), dodatki=dodatki, dane=_js(spec),
        skrypty="\n".join(f'<script src="/_lib/huashu/lib/{n}.js"></script>' for n in LIBY)), encoding="utf-8")
    return out


# ---------------------------------------------------------------- polecenia

def html_wideo(*args: str) -> int:
    return subprocess.run([sys.executable, str(HERE / "html_wideo.py"), *args]).returncode


def wymagaj_silnika() -> None:
    if not nz.huashu_gotowe():
        raise SystemExit("✗ brak silnika huashu-art-motion: python3 $HERMES_HOME/scripts/narzedzia.py instaluj huashu")


def raport_sprawdzenia(plik: Path, r: dict) -> dict:
    s = r["spec"]
    return {"ok": not r["bledy"], "spec": Path(plik).as_posix(), "gramatyka": r["gramatyka"], "id": s.get("grammar"),
            "dlugosc": s.get("duration"), "fps": s.get("fps", 30), "rozmiar": [s.get("width", 1920), s.get("height", 1080)],
            "od": r["od"], "os": r["os"], "fakty": r["fakty"], "dane_przykladowe": r["dane_przykladowe"], "cue": r["cue"],
            "bledy": r["bledy"], "ostrzezenia": r["ostrzezenia"]}


def przygotuj(a) -> tuple[Path, dict]:
    plik = Path(a.spec).resolve()
    r = rozwiaz(wczytaj(plik), plik, a.os, a.fakty)
    if r["bledy"]:
        print(json.dumps(raport_sprawdzenia(plik, r), ensure_ascii=False, indent=1))
        raise SystemExit(1)
    for o in r["ostrzezenia"]:
        print(f"⚠ {o}", file=sys.stderr)
    return plik, r


def cmd_lista(a) -> int:
    if a.json:
        print(json.dumps({"gramatyki": GRAMATYKI, "prowadzacy": PROWADZACY}, ensure_ascii=False, indent=1))
        return 0
    for n, g in GRAMATYKI.items():
        print(f"{n:<12} {g['id']:<18} {g['opis']}\n{'':<31}cue: {', '.join(g['kinds'])}")
    print(f"{'prowadzacy':<12} {PROWADZACY['id']:<18} {PROWADZACY['opis']}")
    return 0


def cmd_szablon(a) -> int:
    nazwa = a.gramatyka if a.gramatyka in GRAMATYKI else ID_NAZWA.get(a.gramatyka)
    if nazwa is None:
        raise SystemExit(f"✗ nieznana gramatyka {a.gramatyka} ({', '.join(GRAMATYKI)}; prowadzacy nie ma klipu)")
    w, h, safe = FORMATY[a.format]
    s = copy.deepcopy(SZABLONY[nazwa])
    spec = {"grammar": nazwa, "duration": s.pop("duration"), "fps": 30, "width": w, "height": h,
            **({"safe": safe} if safe else {}), **s}
    out = Path(a.o or f"out/wideo/src/klip-{nazwa}/spec.json")
    if out.exists() and not a.nadpisz:
        raise SystemExit(f"✗ {out} już jest (--nadpisz)")
    wl.write_json(out, spec)
    print(json.dumps({"spec": Path(out).as_posix(), "gramatyka": nazwa, "dalej": [
        "teksty po polsku; cue przypnij do słów lektora: \"slowo\" (+ \"nth\", \"offset\") zamiast \"at\"",
        f"gramatyka.py sprawdz {Path(out).as_posix()}", f"gramatyka.py render {Path(out).as_posix()} --klatki 0.5,2,4"]}, ensure_ascii=False, indent=1))
    return 0


def cmd_sprawdz(a) -> int:
    plik = Path(a.spec).resolve()
    r = rozwiaz(wczytaj(plik), plik, a.os, a.fakty)
    print(json.dumps(raport_sprawdzenia(plik, r), ensure_ascii=False, indent=1))
    return 0 if not r["bledy"] else 1


def cmd_strona(a) -> int:
    wymagaj_silnika()
    plik, r = przygotuj(a)
    out = strona(plik, r, a.alfa)
    print(json.dumps({"strona": Path(out).as_posix(), "cue": r["cue"], "vo_env": bool(r.get("vo_env"))}, ensure_ascii=False))
    return 0


def _rozmiar(r: dict) -> str:
    return f"{r['spec'].get('width', 1920)}x{r['spec'].get('height', 1080)}"


def cmd_render(a) -> int:
    wymagaj_silnika()
    plik, r = przygotuj(a)
    if a.alfa and not a.klatki and (not a.o or Path(a.o).suffix.lower() == ".mp4"):
        raise SystemExit("✗ --alfa: MP4 nie ma przezroczystości; -o klip.mov (ProRes 4444) albo .webm")
    page = strona(plik, r, a.alfa)
    s = r["spec"]
    if a.klatki:
        arkusz = Path(a.arkusz) if a.arkusz else plik.parent / "klatki" / f"{plik.stem}-arkusz.jpg"
        return html_wideo("klatki", str(page), "--preset", "jarvo", "--rozmiar", _rozmiar(r), "--czasy", a.klatki,
                          "--out", str(plik.parent / "klatki"), "--arkusz", str(arkusz), *(["--alfa"] if a.alfa else []))
    if not a.o:
        raise SystemExit("✗ -o klip.mp4 (albo --klatki 0.5,2,4 do oceny)")
    return html_wideo("wideo", str(page), "--preset", "jarvo", "--rozmiar", _rozmiar(r), "--dlugosc", f"{s['duration']:g}",
                      "--fps", f"{s.get('fps', 30):g}", "-o", a.o, *(["--alfa"] if a.alfa else []),
                      *(["--arkusz", a.arkusz] if a.arkusz else []))


def cmd_pomiar(a) -> int:
    wymagaj_silnika()
    plik, r = przygotuj(a)
    page = strona(plik, r)
    extra = [x for k, v in (("--platforma", a.platforma), ("--tryb", a.tryb)) if v for x in (k, v)]
    for w in a.wyjatek:
        extra += ["--wyjatek", w]
    if r["fakty"]:
        extra += ["--fakty", r["fakty"]]
    return html_wideo("pomiar", str(page), "--preset", "jarvo", "--rozmiar", _rozmiar(r), "--napisy", "tak",
                      "--dlugosc", f"{r['spec']['duration']:g}", *extra)


def cmd_wzor(a) -> int:
    if a.gramatyka in ("prowadzacy", PROWADZACY["id"]):
        print(f"prowadzacy: filmu-wzoru nie da się wyrenderować (brak klatek postaci i lektora); czytaj kod "
              f"$HUASHU/{PROWADZACY['kod']}/ i kartę prowadzacy.md")
        return 2
    nazwa = a.gramatyka if a.gramatyka in GRAMATYKI else ID_NAZWA.get(a.gramatyka)
    if nazwa is None:
        raise SystemExit(f"✗ nieznana gramatyka {a.gramatyka} ({', '.join(GRAMATYKI)}, prowadzacy)")
    wymagaj_silnika()
    arkusz = a.arkusz or f"out/wideo/wzor-{nazwa}.jpg"
    return html_wideo("klatki", str(nz.HUASHU / "scripts" / "engine" / "index.html"), "--preset", "huashu",
                      "--query", f"film=demos/{GRAMATYKI[nazwa]['id']}", "--czasy", a.czasy,
                      "--out", f"out/wideo/klatki-wzor-{nazwa}", "--arkusz", arkusz)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lista", help="gramatyki, ich id w kodzie i rodzaje cue")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("szablon", help="szkielet spec po polsku")
    s.add_argument("gramatyka")
    s.add_argument("--format", choices=sorted(FORMATY), default="16:9")
    s.add_argument("-o", help="plik spec (domyślnie out/wideo/src/klip-<gramatyka>/spec.json)")
    s.add_argument("--nadpisz", action="store_true")
    for name, pomoc in (("sprawdz", "spec bez renderu: rodzaje cue, słowa lektora, czasy, obrazy, tekst, liczby z faktów"),
                        ("strona", "spec → strona klipu <spec>.html (kontrakt jarvo)"),
                        ("render", "stopklatki (--klatki) albo film klipu przez html_wideo.py"),
                        ("pomiar", "html_wideo.py pomiar strony klipu (czas czytania, kontrast, strefy, liczby)")):
        s = sub.add_parser(name, help=pomoc)
        s.add_argument("spec")
        s.add_argument("--os", help="os_czasu.json lektora (domyślnie `os` w spec, obok spec albo katalog wyżej)")
        s.add_argument("--fakty", help="fakty.json (domyślnie obok spec albo katalog wyżej)")
        if name in ("strona", "render"):
            s.add_argument("--alfa", action="store_true", help="bez tła (.mov ProRes 4444 / .webm / PNG)")
        if name == "render":
            s.add_argument("-o", help="film .mp4 | .mov | .webm")
            s.add_argument("--klatki", help="tylko stopklatki w tych sekundach, np. 0.5,2,4")
            s.add_argument("--arkusz", help="JPG z klatkami (domyślnie przy --klatki: klatki/<spec>-arkusz.jpg)")
        if name == "pomiar":
            s.add_argument("--platforma", help="tiktok | ig-reel | yt-shorts | youtube…")
            s.add_argument("--tryb", choices=["pelny", "szybki"])
            s.add_argument("--wyjatek", action="append", default=[], help="KOD[@fragment tekstu]=powód")
    s = sub.add_parser("wzor", help="stopklatki ich filmu pokazowego gramatyki (preset huashu)")
    s.add_argument("gramatyka")
    s.add_argument("--czasy", default="1,2.5,4,5.5,7", help="sekundy filmu pokazowego (ok. 8 s)")
    s.add_argument("--arkusz", help="JPG (domyślnie out/wideo/wzor-<gramatyka>.jpg)")
    a = ap.parse_args(argv)
    return {"lista": cmd_lista, "szablon": cmd_szablon, "sprawdz": cmd_sprawdz, "strona": cmd_strona,
            "render": cmd_render, "pomiar": cmd_pomiar, "wzor": cmd_wzor}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
