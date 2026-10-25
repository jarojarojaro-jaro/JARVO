"""Jarvo HQ: edytor filmów (logika bez serwera, testowalna).

Projekt montażu to mały JSON (zapisywany obok filmu jako `<nazwa>.edycja.json`):

    {"version": 1, "canvas": {"w": 1080, "h": 1920, "fps": 30},
     "clips": [{"src": "/opt/data/jarvo/.../film.mp4", "in": 0.0, "out": 4.2, "speed": 1.0,
                "volume": 1.0, "muted": false, "fit": "contain",     # pasy; "blur" = rozmyte tło; "cover" + fx, fy, zoom
                "fadeIn": 0.0, "fadeOut": 0.0,                      # narastanie i wyciszanie dźwięku (s, opcjonalne)
                "voice": "sredni",                                  # czysty głos: lekki | sredni | mocny (opcjonalny)
                "color": {"look": "cieply", "contrast": 10},          # korekcja koloru (opcjonalna, KOLOR_STYLE)
                "transition": {"type": "fade", "dur": 0.5}}],      # przejście do następnego klipu (opcjonalne)
     "texts": [{"start": 0.5, "end": 3.0, ...}],          # wygląd rysuje przeglądarka (PNG na klatkę)
     "audio": [{"src": ".../muzyka.mp3", "start": 0.0, "in": 0.0, "out": 30.0, "volume": 0.4, "fadeOut": 2.0}]}   # + "voice"

Klipy leżą jeden za drugim (ścieżka główna jak w CapCut), napisy i muzyka mają własny czas.
Przejście leży na środku cięcia i nie skraca filmu: klip A gra dalej za cięciem, klip B zaczyna przed nim
(materiał spoza przycięcia; gdy go brak, stoi skrajna klatka), więc napisy i muzyka zostają na miejscu.
Eksport: jeden przebieg ffmpeg (klipy → concat albo xfade/acrossfade → nakładki PNG → miks audio), plik obok oryginału.
Napisy rasteryzuje przeglądarka tą samą funkcją, którą rysuje podgląd, więc eksport wygląda jak podgląd.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".m4v"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}
MEDIA_EXT = VIDEO_EXT | IMAGE_EXT | AUDIO_EXT

MAX_CLIPS = 200
MAX_TEXTS = 60
MAX_TYPO = 400           # bloków typografii (blok = 1–6 słów naraz, jak w montażu słowo po słowie)
MAX_TYPO_WORDS = 14
TYPO_MOTYWY = ("czysty", "kino", "ulica", "energia", "elegancki", "podcast", "vlog", "komiks", "magazyn", "tech",
               "nowoczesny", "retro", "neon", "show")   # te same klucze co TYPO_MOTYWY w 48-typografia.js
TYPO_UKLADY = ("kolumna", "schodki", "srodek", "skos", "3d", "za", "rozrzut")
TYPO_WEJSCIA = ("ciecie", "pop", "kontur", "maska", "pisanie", "zjazd", "skok")
TYPO_WYJSCIA = ("ciecie", "zanik", "smuga")
TYPO_STYLE = ("wypelnij", "kontur", "3d", "blask", "tlo", "obrys", "show")
TYPO_KROJE = ("bricolage", "bricolageL", "montserrat", "montserratI", "montserratL", "unbounded", "unboundedL",
              "poppins", "poppinsL", "inter", "interL", "archivo", "rubik", "spartan", "kanit", "kanitI", "outfit",
              "syne", "raleway", "anton", "bebas", "barlow", "barlowI", "barlowL", "oswald", "teko", "fjalla",
              "staatliches", "shoulders", "saira", "titan", "baloo", "balooL", "nunito", "paytone", "dynapuff",
              "coiny", "grandstander", "playfair", "playfairI", "instrument", "instrumentI", "abril", "dmserif",
              "dmserifI", "lora", "bodoni", "cormorant", "cormorantI", "fraunces", "alfaslab", "yeseva", "caveat",
              "pacifico", "dancing", "lobster", "kaushan", "greatvibes", "amatic", "brush", "patrick", "graffiti",
              "shrikhand", "bangers", "neon", "grunge", "righteous", "bungee", "monoton", "pixel", "glitch",
              "bubbles", "russo", "blackops", "sigmar", "rammetto", "space", "spaceL", "mono", "audiowide", "chakra",
              "spaceMono", "majorMono")   # te same klucze co TYPO_KROJE w 48-typografia.js
# Wirtualna kamera z głębią (typo.kamera, blok.z, blok.kamera, słowo.z): te same listy i liczby co TYPO_KAMERA
# w 48-typografia.js (test pilnuje zgodności). Osoba (film) stoi na głębokości z = 1, napis przed nią ma z < 1,
# za nią z > 1. Kamera ma przejazd w głąb `z` (0 = spoczynek) i przesunięcie `x`, `y` (część kadru); punkt
# w spoczynku (x, y) na głębokości z widać w (0,5 + ((x − 0,5)·z − kx) / (z − kz), …) w skali z / (z − kz),
# więc bliższy napis rośnie i przesuwa się mocniej niż film (paralaksa), a w spoczynku wszystko stoi jak w planie.
TYPO_KAMERY = ("brak", "spokojna", "dynamiczna")      # styl kamery planu: ruchy dobrane z bloków (kamera_ruchy)
TYPO_RUCHY = ("najazd", "odjazd", "przesuniecie", "brak")
TYPO_KIERUNKI = ("lewo", "prawo", "gora", "dol")
TYPO_KRZYWE = ("plynnie", "uderzenie")
TYPO_OSTROSC = ("napis", "osoba")
KAMERA_Z = {"przod": 0.8, "tyl": 1.3}   # głębia bloku bez pola `z` (warstwa przed osobą / za osobą)
KAMERA_ZMAX = 0.25        # najgłębszy najazd: film ×1,33 (dalej obraz z telefonu robi się miękki)
KAMERA_SILA = {"spokojna": 0.35, "dynamiczna": 0.6}   # siła ruchów dobranych ze stylu
KAMERA_UDERZENIE = 0.4    # s: ruch „uderzenie” (szybki start, miękkie lądowanie) od słowa
KAMERA_MIN_BLOK = 0.6     # s: krótszy blok nie dostaje ruchu ze stylu (oko nie zdąży go zobaczyć)
KAMERA_TRZYMAJ = 2.5      # s: spokojna kamera trzyma najazd co najmniej tyle, zanim odjedzie
KAMERA_SKALA = 1.15       # najazd powiększa napis swojego bloku najwyżej tyle (szeroki blok nie wypada z kadru)
TYPO_LEAD = 0.03          # słowo wchodzi tuż przed dźwiękiem (TYPO_LEAD w 48-typografia.js)
# Efekty bloku (`blok.efekt`): pierścień wokół głowy i przejście przez osobę. Te same listy i liczby co TYPO_EFEKT
# w 48-typografia.js (test pilnuje zgodności). Blok z efektem rysuje się w obu warstwach: część za osobą idzie
# pod jej sylwetkę (maska.py), część przed osobą nad nią.
TYPO_EFEKTY = ("pierscien", "przejscie")
EFEKT_KIERUNKI = ("lewo", "prawo")
EFEKT_KOLEJNOSC = ("za-przod", "przod-za")
EFEKT_PREDKOSC = (5, 40, 180)    # °/s pierścienia: najmniej, domyślnie, najwięcej
EFEKT_NACHYLENIE = (40, 14)      # ° pierścienia: ±najwięcej, domyślnie (przód niżej, jak koło widziane z góry)
EFEKT_SLEDZ = 40                 # najwięcej punktów śledzenia głowy (t, dx, dy) w bloku
# Przejścia między klipami: klucz = nazwa przejścia xfade w FFmpeg, "blur" = przenikanie z rozmyciem Gaussa (nasze).
# Te same klucze co ED_PRZEJSCIA w hq/web/src/49-przejscia.js (podgląd rysuje je tymi samymi wzorami).
PRZEJSCIA = ("fade", "fadeblack", "fadewhite", "blur", "zoomin", "pixelize", "slideleft", "slideright", "slideup",
             "slidedown", "coverleft", "coverright", "wipeleft", "wiperight", "smoothleft", "circleopen")
PRZEJSCIE_D = 0.5        # domyślna długość przejścia (s)
ROZMYCIE_PRZEJSCIA = 40  # rozmycie przy cięciu: σ = krótszy bok kadru / 40 (27 px przy 1080)
# Korekcja koloru klipu („Kolor” w edytorze HQ, projekt.py kolor): styl i cztery suwaki −100…100. Przepis jest jeden:
# krzywa na kanał z pięciu punktów (0, ¼, ½, ¾, 1) i macierz nasycenia. Podgląd rysuje go filtrem SVG
# (feComponentTransfer „table” + feColorMatrix, hq/web/src/49-kolor.js), eksport tymi samymi liczbami w lutrgb
# i colorchannelmixer, więc kolor w podglądzie i w pliku jest ten sam. Style za browser-use/video-use (grade.py:
# neutral_punch, warm_cinematic) i filtrami CapCut; krzywa S (`krzywa`) i uniesiona czerń (`lift`) siedzą w stylu.
KOLOR_STYLE = {
    "naturalny": {"contrast": 8, "saturation": 6, "krzywa": 0.5},
    "cieply": {"contrast": 10, "saturation": -6, "temperature": 30, "krzywa": 0.6},
    "chlodny": {"contrast": 6, "saturation": -4, "temperature": -28},
    "kinowy": {"contrast": 14, "saturation": -16, "temperature": 10, "krzywa": 1.0},
    "zywy": {"contrast": 10, "saturation": 30},
    "czb": {"contrast": 18, "saturation": -100, "krzywa": 0.6},
    "wyblakly": {"contrast": -18, "saturation": -24, "lift": 0.07},
}                        # te same klucze i liczby co ED_KOLOR_STYLE w 49-kolor.js
KOLOR_SUWAKI = ("brightness", "contrast", "saturation", "temperature")
KOLOR_X = (0.0, 0.25, 0.5, 0.75, 1.0)
KOLOR_S = (0.0, -0.04, 0.0, 0.04, 0.0)      # krzywa S: cienie w dół, światła w górę
MAX_AUDIO = 64           # muzyka, lektor, efekty i kawałki dźwięku przypiętego do obrazu (na osi w pasach jeden pod drugim)
ZANIK_MAX = 10.0         # najdłuższe narastanie albo wyciszanie (s), najwyżej połowa elementu (ZANIK_MAX w 43-dzwiek.js)
MAX_WORDS = 40           # słów w jednym napisie karaoke (linia napisu ma ich 2–8)
MAX_DURATION = 3 * 3600.0
MIN_CLIP = 0.04          # jedna klatka przy 25 fps
CICHE_CIECIE = 0.025     # mikro-wyciszenie (s) dźwięku na twardym cięciu: cięcie w środku fali daje słyszalny klik
FPS_ALLOWED = (24, 25, 30, 50, 60)
# limiter miksu w eksporcie: szczyt −2 dBFS bez podnoszenia całości (level=false), liczony na 4× próbkowaniu (szczyty
# między próbkami), więc po AAC szczyt prawdziwy zostaje pod −1 dBTP, jak chcą platformy i qa_wideo.py (ten sam limit co
# montaz.py glosnosc); bez nadpróbkowania transjenty (foley, szarpane struny) wychodziły po AAC na −0,9 dBTP
LIMIT_EKSPORTU = 0.79
LIMITER_EKSPORTU = f"aresample=192000,alimiter=limit={LIMIT_EKSPORTU}:level=false,aresample=48000"


class ProjectError(ValueError):
    """Projekt, którego nie da się bezpiecznie złożyć (komunikat trafia do użytkownika)."""


def media_kind(p: Path | str) -> str | None:
    ext = Path(p).suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    return None


def project_path(video: Path) -> Path:
    return video.with_name(f"{video.stem}.edycja.json")


def _num(v: Any, lo: float, hi: float, default: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(x):
        return default
    return min(hi, max(lo, x))


def _even(n: float) -> int:
    n = int(round(n))
    return max(2, n - (n % 2))       # libx264 + yuv420p wymaga parzystych wymiarów


MAX_KROTSZY = 1080   # krótszy bok kadru: platformy pokazują najwyżej 1080p, a 4K z warstwami typografii i maską nie mieści się w pamięci VPS


def kadr_eksportu(w: int, h: int) -> tuple[int, int]:
    """Kadr o proporcjach źródła z krótszym bokiem najwyżej 1080 px (np. 2160×3840 z iPhone'a → 1080×1920).
    Ta sama reguła co edKadr w hq/web/src/45-edytor.js; napisy i typografia skalują się z krótszym bokiem."""
    k = min(1.0, MAX_KROTSZY / max(1, min(w, h)))
    return _even(math.floor(w * k + 0.5)), _even(math.floor(h * k + 0.5))


def zanik(x: dict, d: float) -> tuple[float, float]:
    """Narastanie i wyciszanie elementu o długości d (s na osi): 0–10 s, najwyżej połowa elementu."""
    lim = max(0.0, min(ZANIK_MAX, d / 2))
    return min(_num(x.get("fadeIn"), 0, ZANIK_MAX, 0), lim), min(_num(x.get("fadeOut"), 0, ZANIK_MAX, 0), lim)


def ciche_ciecie(d: float) -> float:
    """Mikro-wyciszenie elementu długości d: 25 ms, a w bardzo krótkim elemencie najwyżej jego ćwierć."""
    return min(CICHE_CIECIE, max(0.0, d) / 4)


def ciagly(a: dict | None, b: dict | None) -> bool:
    """Klip b gra dalej dźwięk klipu a bez przerwy (klip tylko podzielony, np. pod przybliżenie): to samo źródło,
    ten sam czas źródła, tempo i głośność. Na takim podziale fala nie skacze, więc nie dostaje mikro-wyciszenia."""
    return bool(a and b and a.get("kind") == b.get("kind") == "video" and str(a.get("src")) == str(b.get("src"))
                and abs(float(b.get("in", 0)) - float(a.get("out", 0))) < 1e-3 and a.get("speed") == b.get("speed")
                and not a.get("muted") and not b.get("muted") and a.get("volume") == b.get("volume")
                and a.get("voice") == b.get("voice"))


def ciagle_audio(a: dict, b: dict) -> bool:
    """Audio b to dalszy ciąg audio a na osi (podzielony podkład albo lektor): bez dziury z mikro-wyciszenia."""
    return (str(a.get("src")) == str(b.get("src")) and abs(float(b.get("in", 0)) - float(a.get("out", 0))) < 1e-3
            and abs(float(b.get("start", 0)) - float(a.get("start", 0)) - (float(a.get("out", 0)) - float(a.get("in", 0)))) < 1e-3
            and a.get("volume") == b.get("volume") and a.get("voice") == b.get("voice"))


def afade(fi: float, fo: float, st: float, d: float) -> str:
    """Zanik liniowy (curve=tri, jak zanikGain w podglądzie) dźwięku, który zaczyna się w st i trwa d; "" bez zaniku.
    afade daje ciszę przed narastaniem i po wyciszeniu (także w zapasie przejścia), tak samo jak podgląd."""
    out = []
    if fi > 0:
        out.append(f"afade=t=in:st={_f(st)}:d={_f(fi)}:curve=tri")
    if fo > 0:
        out.append(f"afade=t=out:st={_f(st + d - fo)}:d={_f(fo)}:curve=tri")
    return ",".join(out)


def normalize(project: dict, resolve) -> dict:
    """Sprawdza i porządkuje projekt. `resolve(src) -> Path | None` pilnuje katalogów floty."""
    if not isinstance(project, dict):
        raise ProjectError("Projekt musi być obiektem JSON.")
    cv = project.get("canvas") or {}
    fps = int(_num(cv.get("fps"), 1, 60, 30))
    cw, ch = kadr_eksportu(_even(_num(cv.get("w"), 16, 3840, 1920)), _even(_num(cv.get("h"), 16, 3840, 1080)))
    canvas = {"w": cw, "h": ch, "fps": min(FPS_ALLOWED, key=lambda f: abs(f - fps))}

    clips = []
    for c in (project.get("clips") or [])[:MAX_CLIPS + 1]:
        if len(clips) >= MAX_CLIPS:
            raise ProjectError(f"Najwyżej {MAX_CLIPS} klipów.")
        path = resolve(str((c or {}).get("src") or ""))
        kind = media_kind(path) if path else None
        if kind not in ("video", "image"):
            raise ProjectError(f"Klip spoza katalogów floty albo nie wideo/obraz: {(c or {}).get('src')}")
        a = _num(c.get("in"), 0, MAX_DURATION, 0)
        b = _num(c.get("out"), 0, MAX_DURATION, a + 3)
        if b - a < MIN_CLIP:
            raise ProjectError(f"Klip krótszy niż klatka: {path.name}")
        clips.append({"src": path, "kind": kind, "in": a, "out": b,
                      "speed": 1.0 if kind == "image" else _num(c.get("speed"), 0.25, 4, 1),
                      "volume": _num(c.get("volume"), 0, 2, 1), "muted": bool(c.get("muted")),
                      "fit": c.get("fit") if c.get("fit") in ("cover", "blur") else "contain",
                      # kadr przy „Wypełnij”: punkt skupienia (0–1, 0,5 = środek) i przybliżenie (punch-in)
                      "fx": _num(c.get("fx"), 0, 1, 0.5), "fy": _num(c.get("fy"), 0, 1, 0.5),
                      "zoom": _num(c.get("zoom"), 1, 3, 1)})
        fi, fo = zanik(c, (b - a) / clips[-1]["speed"])
        if fi or fo:
            clips[-1].update(fade_in=fi, fade_out=fo)
        tr = c.get("transition")
        if isinstance(tr, dict) and tr.get("type") in PRZEJSCIA:
            clips[-1]["transition"] = {"type": tr["type"], "dur": _num(tr.get("dur"), 0.1, 3, PRZEJSCIE_D)}
        kol = kolor_norm(c.get("color"))
        if kol:
            clips[-1]["color"] = kol
        if kind == "video" and glos_norm(c.get("voice")):
            clips[-1]["voice"] = c["voice"]
    if not clips:
        raise ProjectError("Oś czasu jest pusta: dodaj co najmniej jeden klip.")
    total = sum((c["out"] - c["in"]) / c["speed"] for c in clips)
    if total > MAX_DURATION:
        raise ProjectError("Film dłuższy niż 3 godziny.")

    texts = []   # "i" = numer napisu w projekcie: po nim dobieramy jego obraz PNG
    for i, t in enumerate((project.get("texts") or [])[:MAX_TEXTS]):
        s = _num((t or {}).get("start"), 0, total, 0)
        e = _num(t.get("end"), 0, total, s)
        if e - s >= MIN_CLIP:
            x = {"start": s, "end": e, "i": i}
            kara = karaoke_windows(t, s, e)
            if kara:
                x["kara"] = kara
            texts.append(x)

    audio = []
    for m in (project.get("audio") or [])[:MAX_AUDIO]:
        path = resolve(str((m or {}).get("src") or ""))
        if not path or media_kind(path) not in ("audio", "video"):
            raise ProjectError(f"Ścieżka dźwięku spoza katalogów floty: {(m or {}).get('src')}")
        a = _num(m.get("in"), 0, MAX_DURATION, 0)
        b = _num(m.get("out"), 0, MAX_DURATION, a)
        start = _num(m.get("start"), 0, total, 0)
        b = min(b, a + (total - start))          # muzyka nie wychodzi poza film
        if b - a >= MIN_CLIP:
            audio.append({"src": path, "in": a, "out": b, "start": start, "volume": _num(m.get("volume"), 0, 2, 1)})
            if glos_norm(m.get("voice")):
                audio[-1]["voice"] = m["voice"]
            fi, fo = zanik(m, b - a)             # wyciszenie liczone od końca w filmie (muzyka dłuższa niż film)
            if fi or fo:
                audio[-1].update(fade_in=fi, fade_out=fo)
    return {"canvas": canvas, "clips": clips, "texts": texts, "audio": audio, "duration": total,
            "przejscia": przejscia_osi(clips, canvas["fps"]), "typo": normalize_typo(project.get("typo"), total)}


_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize_typo(raw: Any, total: float) -> dict:
    """Plan typografii (`projekt.typo`) w bezpiecznej postaci: bloki w czasie filmu, liczby w zakresach, klucze
    z list (rysuje je 48-typografia.js; nieznane wartości wracają do domyślnych motywu)."""
    raw = raw if isinstance(raw, dict) else {}
    out = {"motyw": raw.get("motyw") if raw.get("motyw") in TYPO_MOTYWY else "czysty", "bloki": []}
    if isinstance(raw.get("akcent"), str) and _HEX.match(raw["akcent"]):
        out["akcent"] = raw["akcent"]
    paleta = [x.upper() for x in raw.get("paleta") or [] if isinstance(x, str) and _HEX.match(x)][:4] \
        if isinstance(raw.get("paleta"), list) else []
    if paleta:                                     # kolory z kadru (typografia.py): pierwszy = akcent bez marki
        out["paleta"] = paleta
    if raw.get("odstep") == "tusz":                # linie bez stykania (nowe plany); bez pola: układ jak dawniej
        out["odstep"] = "tusz"
    if isinstance(raw.get("kamera"), dict):        # wirtualna kamera z głębią; bez pola: kadr stoi jak dawniej
        k = raw["kamera"]
        out["kamera"] = {"styl": k.get("styl") if k.get("styl") in TYPO_KAMERY else "brak",
                         "przyslona": round(_num(k.get("przyslona"), 0, 1, 0.5), 3),
                         "ostrosc": k.get("ostrosc") if k.get("ostrosc") in TYPO_OSTROSC else "napis"}
    bloki = raw.get("bloki") if isinstance(raw.get("bloki"), list) else []
    for b in bloki[:MAX_TYPO]:
        if not isinstance(b, dict) or not isinstance(b.get("slowa"), list):
            continue
        s = _num(b.get("start"), 0, total, 0)
        e = _num(b.get("end"), 0, total, s)
        if e - s < MIN_CLIP:
            continue
        slowa = []
        for w in b["slowa"][:MAX_TYPO_WORDS]:
            if not isinstance(w, dict) or not str(w.get("tekst") or "").strip():
                continue
            t = _num(w.get("t"), 0, e - s, 0)
            x = {"t": round(t, 3), "k": round(_num(w.get("k"), t, e - s, t), 3), "tekst": str(w["tekst"]).strip()[:40],
                 "waga": int(_num(w.get("waga"), 0, 3, 1)), "linia": int(_num(w.get("linia"), 0, MAX_TYPO_WORDS, len(slowa)))}
            if w.get("glebia") in (-1, 1):
                x["glebia"] = w["glebia"]
            if isinstance(w.get("kolor"), str) and _HEX.match(w["kolor"]):
                x["kolor"] = w["kolor"]
            if w.get("kroj") in TYPO_KROJE:
                x["kroj"] = w["kroj"]
            if w.get("styl") in TYPO_STYLE:
                x["styl"] = w["styl"]
            if w.get("plyta") is True:             # słaby kontrast z tłem: płytka, chyba że motyw daje obrys
                x["plyta"] = True
            if w.get("wejscie") in TYPO_WEJSCIA:
                x["wejscie"] = w["wejscie"]
            if isinstance(w.get("wielkie"), bool):
                x["wielkie"] = w["wielkie"]
            if w.get("skala") is not None:
                x["skala"] = round(_num(w.get("skala"), 0.3, 3, 1), 3)
            if w.get("z") is not None:             # własna głębia słowa (np. pierścień wokół osoby)
                x["z"] = round(_num(w.get("z"), 0.3, 3, 1), 3)
            slowa.append(x)
        if not slowa:
            continue
        nb = {"id": str(b.get("id") or f"b{len(out['bloki'])}")[:32], "start": round(s, 3), "end": round(e, 3),
              "uklad": b.get("uklad") if b.get("uklad") in TYPO_UKLADY else "kolumna",
              "x": round(_num(b.get("x"), 0, 1, 0.5), 4), "y": round(_num(b.get("y"), 0, 1, 0.3), 4),
              "w": round(_num(b.get("w"), 0.15, 1, 0.62), 4), "rot": round(_num(b.get("rot"), -45, 45, 0), 2),
              "tilt": round(_num(b.get("tilt"), -45, 45, 0), 2), "rozmiar": round(_num(b.get("rozmiar"), 0.3, 3, 1), 3),
              "warstwa": "tyl" if b.get("warstwa") == "tyl" else "przod", "slowa": slowa}
        for k, ok in (("wejscie", TYPO_WEJSCIA), ("wyjscie", TYPO_WYJSCIA)):
            if b.get(k) in ok:
                nb[k] = b[k]
        if b.get("z") is not None:
            nb["z"] = round(_num(b.get("z"), 0.3, 3, 1), 3)
        ruch = kamera_ruch_norm(b.get("kamera"), len(slowa))
        if ruch:
            nb["kamera"] = ruch
        efekt = efekt_norm(b.get("efekt"))
        if efekt:
            nb["efekt"] = efekt
        out["bloki"].append(nb)
    out["bloki"].sort(key=lambda b: b["start"])
    return out


# ---------------------------------------------------------------- efekty bloku i warstwy

def _liczba(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _bez_bool(v: Any) -> Any:
    """Prawda/fałsz to nie liczba (typoLiczba w JS też je odrzuca)."""
    return None if isinstance(v, bool) else v


def efekt_norm(raw: Any) -> dict | None:
    """Efekt bloku (`blok.efekt`) w bezpiecznej postaci (jak typoEfekt w 48-typografia.js); zły albo brak = None.
    Pierścień: `kierunek` (lewo = przód jedzie w lewo), `predkosc` °/s, `nachylenie` °, `powtorz` (false = napis raz);
    przejście: `kierunek` ruchu, `kolejnosc` za-przod / przod-za. `sledz`: [[t, dx, dy]] przesunięcie środka za głową
    (punkty po końcu bloku zostają: po cięciu i złączeniu bloku ślad wraca cały)."""
    if not isinstance(raw, dict) or raw.get("rodzaj") not in TYPO_EFEKTY:
        return None
    pier = raw["rodzaj"] == "pierscien"
    e: dict = {"rodzaj": raw["rodzaj"],
               "kierunek": raw.get("kierunek") if raw.get("kierunek") in EFEKT_KIERUNKI else "lewo" if pier else "prawo"}
    if pier:
        lo, dom, hi = EFEKT_PREDKOSC
        e["predkosc"] = round(_num(_bez_bool(raw.get("predkosc")), lo, hi, dom), 2)
        n, dom = EFEKT_NACHYLENIE
        e["nachylenie"] = round(_num(_bez_bool(raw.get("nachylenie")), -n, n, dom), 2)
        if raw.get("powtorz") is False:
            e["powtorz"] = False
    else:
        e["kolejnosc"] = raw.get("kolejnosc") if raw.get("kolejnosc") in EFEKT_KOLEJNOSC else "za-przod"
    sledz = [[round(_num(q[0], 0, MAX_DURATION, 0), 3), round(_num(q[1], -1, 1, 0), 4), round(_num(q[2], -1, 1, 0), 4)]
             for q in raw.get("sledz") or [] if isinstance(q, (list, tuple)) and len(q) == 3 and all(map(_liczba, q))]
    if sledz:
        e["sledz"] = sorted(sledz, key=lambda q: q[0])[:EFEKT_SLEDZ]
    return e


def typo_warstwy(b: dict) -> tuple[str, ...]:
    """Warstwy, w których blok coś rysuje (typoWarstwyBloku w 48-typografia.js): blok z efektem obie, słowo z własną
    głębią z w warstwie po swojej stronie osoby (z > 1 = za nią), reszta w warstwie bloku."""
    if isinstance(b.get("efekt"), dict) and b["efekt"].get("rodzaj") in TYPO_EFEKTY:
        return ("tyl", "przod")
    blok = "tyl" if b.get("warstwa") == "tyl" else "przod"
    ws = {("tyl" if min(3.0, max(0.3, float(w["z"]))) > 1 else "przod") if _liczba(w.get("z")) else blok
          for w in b.get("slowa") or []}
    return tuple(k for k in ("tyl", "przod") if k in ws)


# ---------------------------------------------------------------- wirtualna kamera z głębią

def kamera_ruch_norm(raw: Any, n_slow: int) -> dict | None:
    """Ruch kamery przypięty do bloku (`blok.kamera`) w bezpiecznej postaci; zły albo brak = None (styl decyduje)."""
    if not isinstance(raw, dict) or raw.get("ruch") not in TYPO_RUCHY:
        return None
    r = {"ruch": raw["ruch"]}
    if r["ruch"] == "brak":
        return r
    r["sila"] = round(_num(raw.get("sila"), 0.05, 1, 0.5), 3)
    r["krzywa"] = raw.get("krzywa") if raw.get("krzywa") in TYPO_KRZYWE else "plynnie"
    if r["ruch"] == "przesuniecie":
        r["kierunek"] = raw.get("kierunek") if raw.get("kierunek") in TYPO_KIERUNKI else "prawo"
    if isinstance(raw.get("slowo"), int) and not isinstance(raw.get("slowo"), bool) and 0 <= raw["slowo"] < n_slow:
        r["slowo"] = raw["slowo"]
    return r


def kamera_z(b: dict) -> float:
    """Głębia bloku: pole `z` albo domyślna dla warstwy (przed osobą 0,8, za osobą 1,3)."""
    z = b.get("z")
    return float(z) if isinstance(z, (int, float)) and not isinstance(z, bool) else KAMERA_Z["tyl" if b.get("warstwa") == "tyl" else "przod"]


def kamera_auto(b: dict, styl: str, stan: dict) -> dict | None:
    """Ruch ze stylu kamery dla bloku bez własnego. Blok za osobą = najazd (osoba rośnie, napis za nią mniej).
    Kamera w głębi: dynamiczna odjeżdża przy następnym bloku, spokojna trzyma najazd KAMERA_TRZYMAJ s i odjeżdża
    płynnie z następnym blokiem. W spoczynku uderzenie (waga 3) = najazd (dynamiczna: szybki, od słowa), a co trzeci
    spokojny blok (dynamiczna: każdy) = przesunięcie w stronę bloku, który przez to idzie do środka kadru.
    `stan` = {wcisnieta, od (początek najazdu), spokoj (licznik spokojnych bloków)}, zmienia go kamera_ruchy."""
    if b["end"] - b["start"] < KAMERA_MIN_BLOK:
        return None
    sila = KAMERA_SILA[styl]
    hit = next((j for j, w in enumerate(b["slowa"]) if w.get("waga") == 3), None)
    if b.get("warstwa") == "tyl":
        return {"ruch": "najazd", "sila": sila, "krzywa": "plynnie"}
    if stan["wcisnieta"]:
        if styl == "dynamiczna" or b["start"] - stan["od"] >= KAMERA_TRZYMAJ:
            return {"ruch": "odjazd", "sila": sila, "krzywa": "plynnie"}
        return None
    if hit is not None:
        return ({"ruch": "najazd", "sila": sila, "krzywa": "uderzenie", "slowo": hit} if styl == "dynamiczna"
                else {"ruch": "najazd", "sila": sila, "krzywa": "plynnie"})
    stan["spokoj"] += 1
    if styl == "dynamiczna" or stan["spokoj"] % 3 == 0:
        return {"ruch": "przesuniecie", "sila": sila, "krzywa": "plynnie",
                "kierunek": "prawo" if float(b.get("x", 0.5)) >= 0.5 else "lewo"}
    return None


def kamera_ruchy(typo: dict) -> list[tuple[dict, dict]]:
    """[(blok, ruch)] po czasie: własny ruch bloku (`blok.kamera`, także „brak”) albo ruch ze stylu planu."""
    styl = (typo.get("kamera") or {}).get("styl")
    out, stan = [], {"wcisnieta": False, "od": 0.0, "spokoj": 0}
    for b in sorted(typo.get("bloki") or [], key=lambda x: x["start"]):
        r = b.get("kamera")
        if r is None and styl in KAMERA_SILA:
            r = kamera_auto(b, styl, stan)
        if not r or r.get("ruch") == "brak":
            continue
        out.append((b, r))
        if r["ruch"] == "najazd" and not stan["wcisnieta"]:
            stan["od"] = b["start"]
        stan["wcisnieta"] = r["ruch"] == "najazd" or (stan["wcisnieta"] and r["ruch"] == "przesuniecie")
    return out


def kamera_krzywa(krzywa: str, p: float) -> float:
    """Postęp ruchu 0–1: płynnie = smoothstep (rusza i staje miękko), uderzenie = szybki start, miękkie lądowanie."""
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3 if krzywa == "uderzenie" else p * p * (3 - 2 * p)


def kamera_stan(odc: list[dict], t: float) -> tuple[float, float, float]:
    """(kz, kx, ky) kamery w chwili t: ostatni rozpoczęty odcinek, ucięty początkiem następnego (`c`)."""
    stan = (0.0, 0.0, 0.0)
    for o in odc:
        if t < o["a"]:
            break
        p = 1.0 if o["b"] <= o["a"] else (min(t, o["c"]) - o["a"]) / (o["b"] - o["a"])
        e = kamera_krzywa(o["krzywa"], p)
        stan = tuple(s0 + (s1 - s0) * e for s0, s1 in zip(o["s0"], o["s1"]))
    return stan


def kamera_odcinki(typo: dict) -> list[dict]:
    """Ruchy kamery → odcinki {a, b, c, s0, s1, krzywa} po czasie (stan = (kz, kx, ky)). Odcinek trwa blok (płynnie)
    albo KAMERA_UDERZENIE od słowa; następny zaczyna się od stanu, w którym kamera akurat jest (c = koniec ucięty
    jego początkiem). Najazd: o 0,04 + 0,12·siła w głąb i trochę w stronę bloku, ale napis bloku rośnie najwyżej
    KAMERA_SKALA razy (najazd po przesunięciu nie wypycha go z kadru); odjazd: do spoczynku (ze spoczynku:
    skok w głąb na początku bloku, potem odjazd); przesunięcie: kamera w bok o 0,015 + 0,05·siła z najazdem, który
    film zawsze wypełnia kadr (|kx|, |ky| ≤ kz / 2). Najdalej KAMERA_ZMAX w głąb."""
    odc: list[dict] = []
    for b, r in kamera_ruchy(typo):
        a = b["start"]
        if r.get("slowo") is not None and r["slowo"] < len(b["slowa"]):
            a += max(0.0, float(b["slowa"][r["slowo"]].get("t") or 0) - TYPO_LEAD)
        if odc:
            a = max(a, odc[-1]["a"])
        koniec = min(a + KAMERA_UDERZENIE, b["end"]) if r["krzywa"] == "uderzenie" else b["end"]
        koniec = max(koniec, a + 0.1)
        if odc:
            odc[-1]["c"] = min(odc[-1]["b"], a)
        z0, x0, y0 = kamera_stan(odc, a)
        sila = float(r.get("sila", 0.5))
        dz, dp = 0.04 + 0.12 * sila, 0.015 + 0.05 * sila
        if r["ruch"] == "najazd":
            z1 = min(KAMERA_ZMAX, z0 + dz, max(z0, kamera_z(b) * (1 - 1 / KAMERA_SKALA)))
            x1 = x0 + (float(b.get("x", 0.5)) - 0.5) * dz * 0.5
            y1 = y0 + (float(b.get("y", 0.5)) - 0.5) * dz * 0.5
        elif r["ruch"] == "odjazd":
            if z0 < dz / 2:                        # ze spoczynku: skok w głąb na początku bloku, potem odjazd
                z0 = min(KAMERA_ZMAX, z0 + dz)
            z1, x1, y1 = 0.0, 0.0, 0.0
        else:
            k = r.get("kierunek", "prawo")
            x1 = (dp if k == "prawo" else -dp) if k in ("lewo", "prawo") else x0
            y1 = (dp if k == "dol" else -dp) if k in ("gora", "dol") else y0
            z1 = min(KAMERA_ZMAX, max(z0, 2 * abs(x1) + 0.01, 2 * abs(y1) + 0.01))
        x1 = max(-z1 / 2, min(z1 / 2, x1))
        y1 = max(-z1 / 2, min(z1 / 2, y1))
        x0, y0 = max(-z0 / 2, min(z0 / 2, x0)), max(-z0 / 2, min(z0 / 2, y0))
        odc.append({"a": round(a, 4), "b": round(koniec, 4), "c": round(koniec, 4), "krzywa": r["krzywa"],
                    "s0": tuple(round(v, 5) for v in (z0, x0, y0)), "s1": tuple(round(v, 5) for v in (z1, x1, y1))})
    return odc


def _kamera_suma(odc: list[dict], wsp: tuple[float, float, float], F: float) -> str:
    """Wyrażenie ffmpeg (numer klatki `in`) dla kombinacji wsp·(kz, kx, ky) stanu kamery: płaska suma skoków
    i przyrostów odcinków (bez zagnieżdżeń, więc długi film nie przepełnia parsera), czas klatki = (in + 0,5) / F
    jak w typoOdcinki."""
    lin = lambda s: sum(w * v for w, v in zip(wsp, s))  # noqa: E731
    czesci, przed = [], 0.0
    for o in odc:
        A = o["a"] * F - 0.5
        skok = lin(o["s0"]) - przed
        if abs(skok) > 1e-6:
            czesci.append(f"{skok:.6f}*gte(in,{A:.3f})")
        d = lin(o["s1"]) - lin(o["s0"])
        if o["b"] > o["a"] and abs(d) > 1e-6:
            p = f"clip((min(in,{o['c'] * F - 0.5:.3f})-{A:.3f})/{(o['b'] - o['a']) * F:.3f},0,1)"
            e = (f"(st(0,1-{p});1-ld(0)*ld(0)*ld(0))" if o["krzywa"] == "uderzenie"
                 else f"(st(0,{p});ld(0)*ld(0)*(3-2*ld(0)))")
            czesci.append(f"{d:.6f}*{e}")
        p = 1.0 if o["b"] <= o["a"] else (o["c"] - o["a"]) / (o["b"] - o["a"])
        przed = lin(o["s0"]) + d * kamera_krzywa(o["krzywa"], p)
    return "+".join(czesci) or "0"


def kamera_filter(typo: dict, F: float) -> str:
    """Kamera na obrazie filmu (eksport): `perspective` liczony co klatkę wycina z kadru prostokąt widziany przez
    kamerę (film na z = 1 rośnie 1 / (1 − kz) razy, przesuwa się o kx, ky), z podpikselową dokładnością (bez drgań
    zoompan). Działa tylko tam, gdzie kamera nie stoi w spoczynku (enable); bez ruchów pusty napis."""
    odc = kamera_odcinki(typo)
    if not odc:
        return ""
    okna, od = [], None
    for i, o in enumerate(odc):
        od = o["a"] if od is None else od
        nast = odc[i + 1]["a"] if i + 1 < len(odc) else None
        if max(map(abs, kamera_stan(odc, o["c"]))) < 1e-5 and (nast is None or nast > o["c"]):
            okna.append((od, o["c"]))
            od = None
    if od is not None:
        okna.append((od, MAX_DURATION))
    pol = lambda wz, wx, wy: _kamera_suma(odc, (wz, wx, wy), F)  # noqa: E731
    xl, xp, yg, yd = pol(0.5, 1, 0), pol(-0.5, 1, 0), pol(0.5, 0, 1), pol(-0.5, 0, 1)
    enable = "+".join(f"between(t,{_f(max(0.0, a - 1 / F))},{_f(b + 1 / F)})" for a, b in okna)
    return (f"perspective=x0='W*({xl})':y0='H*({yg})':x1='W*(1+{xp})':y1='H*({yg})':x2='W*({xl})':y2='H*(1+{yd})'"
            f":x3='W*(1+{xp})':y3='H*(1+{yd})':interpolation=linear:eval=frame:enable='{enable}'")


def plik_listy(p: Path | str) -> str:
    """Wpis `file …` listy demuxera concat: ścieżka w apostrofach (w środku „\\” z Windows i spacje są dosłowne),
    apostrof z nazwy jako `'\\''`: zamknięcie, apostrof ze znakiem ucieczki, otwarcie (docs/NATYWNIE.md M10), więc
    „Ania's film” z katalogu projektu nie urywa ścieżki."""
    return "file '" + str(p).replace("'", "'\\''") + "'"


def typo_concat(segments: list[tuple[float, Path | None]], blank: Path, dest: Path) -> Path | None:
    """Warstwa typografii jako lista demuxera concat: (czas trwania, PNG albo None = przezroczysta klatka).
    Klatki rysuje przeglądarka tylko tam, gdzie obraz się zmienia (typoOdcinki), reszta to długie odcinki."""
    if not any(png for _d, png in segments):
        return None
    lines = ["ffconcat version 1.0"]
    for dur, png in segments:
        if dur >= 0.0005:
            lines.extend([plik_listy(png or blank), f"duration {dur:.4f}"])
    lines.append(plik_listy(blank))
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")   # lista ffconcat: „\n” też na Windows
    return dest


def layout_clips(clips: list[dict]) -> list[tuple[dict, float, float]]:
    """(klip, początek, koniec) na osi: klipy jeden po drugim, długość (out − in) / tempo."""
    out, t = [], 0.0
    for c in clips:
        d = (float(c.get("out", 0)) - float(c.get("in", 0))) / float(c.get("speed") or 1)
        out.append((c, t, t + d))
        t += d
    return out


def przejscia_osi(clips: list[dict], fps: int) -> list[dict | None]:
    """Przejście po każdym klipie (None = zwykłe cięcie) jako {"type", "d"}: parzysta liczba klatek (połowa przed
    cięciem, połowa za nim), najwyżej tyle, ile trwa krótszy z sąsiednich klipów. Przejście nie zmienia osi: film
    trwa tyle samo. Ta sama reguła co przejsciaOsi w hq/web/src/49-przejscia.js (podgląd)."""
    def dl(x: dict) -> float:
        return (float(x.get("out", 0)) - float(x.get("in", 0))) / float(x.get("speed") or 1)
    out: list[dict | None] = []
    for i, c in enumerate(clips):
        tr, n = c.get("transition"), (clips[i + 1] if i + 1 < len(clips) else None)
        if n is None or not isinstance(tr, dict) or tr.get("type") not in PRZEJSCIA:
            out.append(None)
            continue
        cap = 2 * math.floor(min(dl(c), dl(n)) * fps / 2 + 1e-6)
        k = min(2 * math.floor(_num(tr.get("dur"), 0.1, 3, PRZEJSCIE_D) * fps / 2 + 0.5), cap)
        out.append({"type": tr["type"], "d": k / fps} if k >= 2 else None)
    return out


def przypiete(m: dict, l0: list, l1: list, ids0: set, uzyte: set) -> list[dict]:
    """Dźwięk przypięty do obrazu (`linked`, np. głos i efekty filmu z kodu) po zmianie klipów: każdy kawałek materiału,
    który został na osi, gra dalej pod tym samym obrazem (wycięte ujęcie zabiera swój dźwięk, przestawione go przenosi,
    zduplikowane powtarza). Kawałki stykające się na osi i w pliku łączą się z powrotem w jeden element; pierwszy
    zostaje z id elementu, kolejne dostają wolne id `<id>-k`. Tempo klipu nie zmienia tempa dźwięku. Ta sama reguła
    co przypiete w hq/web/src/45-edytor.js."""
    s0, i0 = float(m.get("start", 0)), float(m.get("in", 0))
    e0 = s0 + float(m.get("out", 0)) - i0
    kaw = []
    for c0, a0, b0 in l0:
        x, y = max(a0, s0), min(b0, e0)                      # część elementu pod starym klipem
        if y - x < 1e-6:
            continue
        sp0, in0 = float(c0.get("speed") or 1), float(c0.get("in", 0))
        u0, u1 = in0 + (x - a0) * sp0, in0 + (y - a0) * sp0  # ten kawałek w czasie źródła
        for c1, a1, _b1 in l1:
            if c1.get("src") != c0.get("src") or not (c1.get("id") == c0.get("id") or c1.get("id") not in ids0):
                continue
            v0, v1 = max(u0, float(c1.get("in", 0))), min(u1, float(c1.get("out", 0)))
            if v1 - v0 < 1e-6:
                continue
            kaw.append([a1 + (v0 - float(c1.get("in", 0))) / float(c1.get("speed") or 1),
                        i0 + a0 + (v0 - in0) / sp0 - s0, i0 + a0 + (v1 - in0) / sp0 - s0])
    kaw.sort(key=lambda k: (k[0], k[1]))
    zlaczone: list[list[float]] = []
    for k in kaw:
        p = zlaczone[-1] if zlaczone else None
        if p and abs(k[0] - p[0] - (p[2] - p[1])) < 1e-3 and abs(k[1] - p[2]) < 1e-3:
            p[2] = k[2]
        else:
            zlaczone.append(k)
    out = []
    for j, (st, a, b) in enumerate(zlaczone):
        id_ = m.get("id")
        if j:
            n = 1
            while f"{m.get('id')}-{n}" in uzyte:
                n += 1
            id_ = f"{m.get('id')}-{n}"
            uzyte.add(id_)
        out.append({**m, "id": id_, "start": round(st, 3), "in": round(a, 3), "out": round(b, 3)})
    return out


def remap_times(p0: dict, p1: dict) -> dict:
    """Oś magnetyczna, ta sama reguła co remapTimes w hq/web/src/45-edytor.js: po zmianie klipów (usunięcie, wstawienie,
    przycięcie, tempo, przestawienie) napisy, uwagi i bloki typografii (z każdym słowem) idą za materiałem, z którego
    pochodzą (czas źródła klipu), a muzyka i lektor przesuwają się o wycięty albo wstawiony czas. Przy samym
    przestawieniu napis i blok jadą w całości z klipem. Dźwięk przypięty do obrazu (`linked`) idzie kawałkami
    za materiałem (`przypiete`)."""
    l0, l1 = layout_clips(p0.get("clips") or []), layout_clips(p1.get("clips") or [])
    tot0, tot1 = (l0[-1][2] if l0 else 0.0), (l1[-1][2] if l1 else 0.0)
    ids0 = {c.get("id") for c in p0.get("clips") or []}

    def klucz(c: dict) -> str:
        return f"{c.get('id')}|{float(c.get('in', 0))}|{float(c.get('out', 0))}|{float(c.get('speed') or 1)}"
    reorder = (len(p0.get("clips") or []) == len(p1.get("clips") or [])
               and sorted(map(klucz, p0.get("clips") or [])) == sorted(map(klucz, p1.get("clips") or [])))

    def mapuj(t: float) -> float:
        if t >= tot0 - 1e-9:
            return t + tot1 - tot0
        i = next((k for k, s in enumerate(l0) if t < s[2]), 0)
        c0, a0, _ = l0[i]
        u = float(c0.get("in", 0)) + (t - a0) * float(c0.get("speed") or 1)

        def trafia(s) -> bool:
            c = s[0]
            return c.get("src") == c0.get("src") and float(c.get("in", 0)) - 1e-6 <= u <= float(c.get("out", 0)) + 1e-6
        same = next((s for s in l1 if s[0].get("id") == c0.get("id")), None)
        s1 = same if same and trafia(same) else next((s for s in l1 if s[0].get("id") not in ids0 and trafia(s)), None)
        if s1:
            return s1[1] + (u - float(s1[0].get("in", 0))) / float(s1[0].get("speed") or 1)
        if same:                                             # wycięty fragment klipu: na jego krawędź
            return same[1] if u < float(same[0].get("in", 0)) else same[2]
        for s in l0[i + 1:]:                                 # klip usunięty: tam, gdzie był
            nast = next((x for x in l1 if x[0].get("id") == s[0].get("id")), None)
            if nast:
                return nast[1]
        return tot1

    texts = []
    for x in p1.get("texts") or []:
        a, b = float(x.get("start", 0)), float(x.get("end", 0))
        if reorder:
            d = mapuj((a + b) / 2) - (a + b) / 2
            a, b = a + d, b + d
        else:
            a, b = mapuj(a), mapuj(b)
        if b - a >= 0.05:
            texts.append({**x, "start": round(a, 3), "end": round(b, 3)})
    audio, uzyte = [], {m.get("id") for m in p1.get("audio") or []}
    for m in p1.get("audio") or []:
        if m.get("linked"):
            audio += przypiete(m, l0, l1, ids0, uzyte)
        else:
            audio.append(m if reorder else {**m, "start": round(mapuj(float(m.get("start", 0))), 3)})
    notes = [{**n, "t": round(mapuj(float(n.get("t", 0))), 3)} for n in p1.get("notes") or []]
    out = {**p1, "texts": texts, "audio": audio, "notes": notes}
    typo = p1.get("typo")
    if isinstance(typo, dict) and isinstance(typo.get("bloki"), list):   # typografia: blok i każde słowo za materiałem
        bloki = []
        for b in typo["bloki"]:
            if not isinstance(b, dict):
                continue
            a, e = float(b.get("start", 0)), float(b.get("end", 0))
            d = mapuj((a + e) / 2) - (a + e) / 2 if reorder else 0.0
            f = (lambda x, d=d: x + d) if reorder else mapuj
            s1, e1 = f(a), f(e)
            if e1 - s1 < 0.05:
                continue
            slowa = [{**w, "t": round(max(0.0, f(a + float(w.get("t") or 0)) - s1), 3),
                      "k": round(max(0.0, f(a + float(w.get("k") or 0)) - s1), 3)}
                     for w in b.get("slowa") or [] if isinstance(w, dict)]
            bloki.append({**b, "start": round(s1, 3), "end": round(e1, 3), "slowa": slowa})
        out["typo"] = {**typo, "bloki": bloki}
    return out


def karaoke_words(t: dict) -> list[str] | None:
    """Słowa napisu karaoke albo None (ta sama reguła co karaokeWords w 44-napisy.js): jest kolor `hl`, lista `words`
    i tyle samo słów w tekście (poprawiona literówka zostaje karaoke, inna liczba słów już nie)."""
    words, toks = t.get("words"), str(t.get("text") or "").split()
    if not t.get("hl") or not isinstance(words, list) or not words or len(words) != len(toks) or len(words) > MAX_WORDS:
        return None
    return toks


def karaoke_windows(t: dict, s: float, e: float) -> list[tuple[float, float, int]] | None:
    """Okna czasu osi, w których aktywne jest słowo j (czasy słów liczone od początku napisu).
    Przed pierwszym słowem aktywne jest pierwsze, ostatnie trwa do końca napisu: okna pokrywają cały napis."""
    if karaoke_words(t) is None:
        return None
    starts, top = [], 0.0
    for w in t["words"]:
        rel = _num(w[0] if isinstance(w, (list, tuple)) and w else 0, 0, MAX_DURATION, 0)
        top = max(top, rel)                                    # czasy rosną (jak w karaokeIndex)
        starts.append(min(e, s + top))
    out = []
    for j in range(len(starts)):
        a = s if j == 0 else starts[j]
        b = e if j == len(starts) - 1 else starts[j + 1]
        if b - a >= 0.001:
            out.append((a, b, j))
    return out or None


def blank_png(path: Path, w: int, h: int) -> Path:
    """Przezroczysty PNG w×h (tło warstwy karaoke między napisami), bez zależności."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = (b"\x00" + b"\x00" * (4 * w)) * h
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return path


def karaoke_concat(p: dict, pngs: dict[int, list[Path]], blank: Path, dest: Path) -> Path | None:
    """Wszystkie napisy karaoke jako JEDNA warstwa: lista demuxera concat (PNG aktywnego słowa + czas, przerwy
    = przezroczysty PNG). ffmpeg dekoduje naraz jeden obraz, więc pamięć nie rośnie z liczbą słów."""
    events = sorted((a, b, pngs[x["i"]][j]) for x in p["texts"] if x.get("kara") for a, b, j in x["kara"])
    if not events:
        return None
    lines, t = ["ffconcat version 1.0"], 0.0

    def add(path: Path, dur: float) -> None:
        if dur >= 0.001:
            lines.extend([plik_listy(path), f"duration {dur:.3f}"])
    for a, b, png in events:
        if b <= t:
            continue                       # nakładające się napisy karaoke: wygrywa wcześniejszy
        a = max(a, t)
        add(blank, a - t)
        add(png, b - a)
        t = b
    add(blank, max(0.0, p["duration"] - t))
    lines.append(plik_listy(blank))        # demuxer concat potrzebuje ostatniego pliku jeszcze raz
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")   # lista ffconcat: „\n” też na Windows
    return dest


def _atempo(speed: float) -> str:
    # atempo przyjmuje 0.5–2.0 w jednym filtrze, więc szersze tempo składamy z kilku
    parts, s = [], speed
    while s > 2.0:
        parts.append("atempo=2.0"); s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5"); s /= 0.5
    if abs(s - 1.0) > 1e-6:
        parts.append(f"atempo={s:.6f}")
    return ",".join(parts)


def _f(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def cover_filter(W: int, H: int, c: dict) -> str:
    """„Wypełnij” z kadrem: obraz skalowany tak, by pokrył kadr powiększony o `zoom`, i wycięty z punktem skupienia
    (fx, fy). To ten sam kadr co w podglądzie (CSS object-position fx fy + scale(zoom) wokół tego punktu)."""
    z, fx, fy = c.get("zoom", 1), c.get("fx", 0.5), c.get("fy", 0.5)
    sw, sh = (_even(W * z), _even(H * z)) if z != 1 else (W, H)
    return (f"scale={sw}:{sh}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}:(iw-{W})*{_f(fx)}:(ih-{H})*{_f(fy)}")


def _r4(v: float) -> float:
    return math.floor(v * 10000 + 0.5) / 10000        # jak r4 w 49-kolor.js (Math.round), nie zaokrąglanie bankiera


def kolor_norm(raw: Any) -> dict | None:
    """Korekcja koloru klipu: styl z KOLOR_STYLE i suwaki całkowite −100…100 (zera odpadają); None = bez korekty."""
    if not isinstance(raw, dict):
        return None
    out: dict = {"look": raw["look"]} if raw.get("look") in KOLOR_STYLE else {}
    for k in KOLOR_SUWAKI:
        v = int(math.floor(_num(raw.get(k), -100, 100, 0) + 0.5))
        if v:
            out[k] = v
    return out or None


def kolor_domyslne(look: str) -> dict:
    """Suwaki, które ustawia wybór stylu (potem człowiek albo agent może je przesunąć)."""
    return {k: v for k, v in KOLOR_STYLE.get(look, {}).items() if k in KOLOR_SUWAKI}


def kolor_tabele(raw: Any) -> tuple[dict, float] | None:
    """Przepis koloru: krzywa każdego kanału w pięciu punktach (0…1) i nasycenie (1 = bez zmiany).
    Kolejność: krzywa S i lift stylu → kontrast wokół ½ → jasność → temperatura (zysk R/G/B) → obcięcie do 0…1."""
    k = kolor_norm(raw)
    if not k:
        return None
    st = KOLOR_STYLE.get(k.get("look") or "", {})
    a, lift = st.get("krzywa", 0.0), st.get("lift", 0.0)
    kon = 1 + k.get("contrast", 0) / 100 * 0.35
    jas = k.get("brightness", 0) / 100 * 0.2
    t = k.get("temperature", 0) / 100
    zysk = {"r": 1 + 0.10 * t, "g": 1 + 0.02 * t, "b": 1 - 0.12 * t}
    sn = k.get("saturation", 0) / 100
    tab = {}
    for ch in ("r", "g", "b"):
        ys = []
        for x, sx in zip(KOLOR_X, KOLOR_S):
            y = lift + (1 - lift) * (x + a * sx)
            y = (y - 0.5) * kon + 0.5 + jas
            ys.append(_r4(min(1.0, max(0.0, y * zysk[ch]))))
        tab[ch] = ys
    return tab, _r4(1 + sn if sn < 0 else 1 + 0.8 * sn)


def kolor_macierz(s: float) -> list[list[float]]:
    """Macierz nasycenia z Filter Effects (CSS saturate, feColorMatrix type=saturate): luminancja 0,213/0,715/0,072."""
    return [[0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s],
            [0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s],
            [0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s]]


def _lut_expr(ys: list[float]) -> str:
    """Krzywa z pięciu punktów jak feFuncX type=table: odcinki liniowe co 63,75 wartości (0…255)."""
    seg = [f"{ys[i] * 255:.4f}{(ys[i + 1] - ys[i]) * 4:+.6f}*(val-{i * 63.75:g})" for i in range(4)]
    return f"if(lt(val,63.75),{seg[0]},if(lt(val,127.5),{seg[1]},if(lt(val,191.25),{seg[2]},{seg[3]})))"


def kolor_filter(raw: Any) -> str:
    """Filtry FFmpeg korekcji koloru klipu (RGB, ten sam przepis co filtr SVG podglądu); "" = bez korekty."""
    t = kolor_tabele(raw)
    if not t:
        return ""
    tab, s = t
    out = []
    if any(list(tab[ch]) != list(KOLOR_X) for ch in tab):
        out.append(f"lutrgb=r='{_lut_expr(tab['r'])}':g='{_lut_expr(tab['g'])}':b='{_lut_expr(tab['b'])}'")
    if abs(s - 1) > 1e-6:
        m = kolor_macierz(s)
        out.append("colorchannelmixer=" + ":".join(f"{a}{b}={m[i][j]:.6f}" for i, a in enumerate("rgb")
                                                    for j, b in enumerate("rgb")))
    return ",".join(out)


def kolor_pomiar_cmd(src: Path, a: float, b: float, ffmpeg: str = "ffmpeg", sdr: str = "") -> list[str]:
    """Pomiar klatek klipu pod „Auto” (signalstats na ~12 klatkach, zdjęcie: jedna klatka); wynik w stderr,
    czyta go kolor_z_pomiaru. `sdr` (probe) = film HDR: mierzymy obraz po przeliczeniu, jak w eksporcie."""
    if media_kind(Path(src)) == "image":
        return [ffmpeg, "-nostdin", "-hide_banner", "-nostats", "-loglevel", "info", "-i", str(src),
                "-vf", "scale=320:-2,signalstats,metadata=print", "-frames:v", "1", "-f", "null", "-"]
    d = max(0.1, b - a)
    return [ffmpeg, "-nostdin", "-hide_banner", "-nostats", "-loglevel", "info", "-ss", _f(a), "-t", _f(d), "-i", str(src),
            "-vf", f"fps={min(4.0, max(0.5, 12 / d)):.3f},scale=320:-2,{sdr + ',' if sdr else ''}signalstats,metadata=print",
            "-an", "-f", "null", "-"]


def kolor_z_pomiaru(log: str) -> dict | None:
    """„Auto” za video-use (auto_grade): tylko korekta niedoświetlenia, płaskiego obrazu i wyblakłych barw, bez
    przesunięcia barwy i najwyżej ±30 na suwaku („czysto, nie stylizowane”). Średnie Y i nasycenia z signalstats."""
    v: dict[str, list[float]] = {k: [] for k in ("YAVG", "YLOW", "YHIGH", "SATAVG")}
    for m in re.finditer(r"lavfi\.signalstats\.(YAVG|YLOW|YHIGH|SATAVG)=([\d.]+)", log):
        v[m.group(1)].append(float(m.group(2)))
    if not all(v.values()):
        return None
    sr = {k: sum(x) / len(x) for k, x in v.items()}
    y, zakres, sat = (sr["YAVG"] - 16) / 219, (sr["YHIGH"] - sr["YLOW"]) / 219, sr["SATAVG"]
    jas = min(30, round((0.45 - y) / 0.2 * 100)) if y < 0.40 else max(-15, round((0.58 - y) / 0.2 * 100)) if y > 0.62 else 0
    kon = min(30, round((0.62 / max(zakres, 0.2) - 1) / 0.35 * 100)) if zakres < 0.55 else 0
    nas = 15 if sat < 14 else -10 if sat > 55 else 0
    kol = {"brightness": jas, "contrast": kon, "saturation": nas}
    return {"color": kolor_norm(kol), "pomiar": {"jasnosc": round(y, 3), "rozpietosc": round(zakres, 3), "nasycenie": round(sat, 1)}}


# Czysty głos klipu albo audio („voice”: lekki | sredni | mocny). Za kajisho5/ffmpeg-skill (MIT, audio.py VOICE_LEVELS:
# highpass 80 Hz, de-esser, afftdn, kompresor, w mocnym drugi stopień i limiter), poprawione naszym pomiarem na polskiej
# mowie z szumem wentylatora (tło −47 dB, mowa −19 dB): ich stałe afftdn=nf=-25 ze śledzeniem tła (tn=1) ściszało tło
# o ~3 dB, a kompresory z podbiciem podnosiły je z powrotem (mocny: pauzy GŁOŚNIEJSZE niż w nagraniu). U nas próg
# odszumiania z tła nagrania (nf = tło + 6 dB, mocny + 12 dB: mowa bez szkody, falkowe afwtdn ją psuło) i ekspander
# (agate z ograniczonym zasięgiem, próg tło + 6 dB) przed kompresorem: pauzy ciszej o ~10 dB (średni, mowa +2 dB)
# i ~15 dB (mocny, ta sama głośność, mowa równiejsza), lekki bez zmian tła. afftdn opóźnia dźwięk o 25 ms: eksport
# daje głosowi osobne wejście z zapasem przed klipem (GLOS_ZAPAS) i ścina opóźnienie, więc usta zgadzają się
# z obrazem, a podział klipu (zbliżenie) nie ma dziury.
GLOS = ("lekki", "sredni", "mocny")
GLOS_ZAPAS = 1.0          # s materiału przed klipem: odszumianie i kompresor wchodzą w klip rozpędzone
GLOS_OPOZNIENIE = 0.025   # opóźnienie afftdn (okno 25 ms, niezależnie od próbkowania)
GLOS_TLO = -50.0          # tło (dB RMS), gdy pomiaru brak: telefon w cichym pokoju
SZUM_OKNO = 0.05          # okno pomiaru tła (s); tło = najcichsze 10% okien z dźwiękiem
SZUM_MAX = 600.0          # najwyżej tyle sekund źródła mierzymy (tło to cecha nagrania, nie klipu)


def glos_norm(raw: Any) -> str | None:
    return raw if raw in GLOS else None


def glos_filter(poziom: str | None, tlo: float | None = None) -> str:
    """Łańcuch czystego głosu dla poziomu; `tlo` = zmierzone tło źródła w dB (szum_z_logu), None = GLOS_TLO."""
    if poziom not in GLOS:
        return ""
    if poziom == "lekki":                       # dobry pokój: dudnienie i wyrównanie, szum i syczenie bez zmian
        return "highpass=f=80,acompressor=threshold=-18dB:ratio=2:attack=5:release=80:makeup=1.4"
    t = GLOS_TLO if tlo is None else tlo
    nf = lambda o: max(-80, min(-20, round(t + o)))       # noqa: E731  (zakres afftdn)
    prog = f"{10 ** ((t + 6) / 20):.5f}"                  # ekspander: wszystko ciszej niż tło + 6 dB to pauza
    c1 = "acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=2"
    if poziom == "sredni":
        return (f"highpass=f=80,deesser=i=0.4,afftdn=nr=20:nf={nf(6)},"
                f"agate=threshold={prog}:ratio=2:range=0.35:attack=5:release=250,{c1}")
    return (f"highpass=f=80,deesser=i=0.4,afftdn=nr=25:nf={nf(12)},"      # telefon, laptop: szczyty do −1 dBFS
            f"agate=threshold={prog}:ratio=3:range=0.18:attack=5:release=250,{c1},deesser=i=0.6,"
            "acompressor=threshold=-24dB:ratio=4:attack=5:release=120:makeup=3,alimiter=limit=0.891251:level=disabled")


def glos_opoznienie(poziom: str | None) -> float:
    return GLOS_OPOZNIENIE if poziom in ("sredni", "mocny") else 0.0


def glos_auto(tlo: float | None) -> str:
    """Poziom z samego tła nagrania: cicho → lekki, zwykły pokój → średni, głośne tło → mocny."""
    return "sredni" if tlo is None else "lekki" if tlo <= -60 else "mocny" if tlo > -42 else "sredni"


def szum_cmd(src: Path, ffmpeg: str = "ffmpeg", a: float = 0.0, d: float = SZUM_MAX) -> list[str]:
    """Pomiar tła nagrania: RMS w oknach 50 ms po tym samym highpass co łańcuch głosu (wynik w stderr)."""
    n = round(48000 * SZUM_OKNO)
    return [ffmpeg, "-nostdin", "-hide_banner", "-nostats", "-loglevel", "info", "-ss", _f(max(0.0, a)),
            "-t", _f(min(SZUM_MAX, max(0.5, d))), "-i", str(src), "-vn", "-map", "0:a:0",
            "-af", f"aresample=48000,highpass=f=80,asetnsamples=n={n}:p=0,astats=metadata=1:reset=1:measure_perchannel=none"
            ":measure_overall=RMS_level,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"]


def szum_z_logu(log: str) -> float | None:
    """Tło (dB RMS) z wyniku szum_cmd: 10. percentyl okien z dźwiękiem (cyfrowa cisza odpada); None = za mało okien."""
    v = sorted(float(x) for x in re.findall(r"lavfi\.astats\.Overall\.RMS_level=(-?\d+(?:\.\d+)?)", log) if float(x) > -90)
    return round(v[len(v) // 10], 1) if len(v) >= 10 else None


def szum_zakresy(p: dict) -> dict[str, tuple[float, float]]:
    """Źródła z głosem średnim albo mocnym (znormalizowany projekt) → (od, długość) pomiaru tła: obszar ich klipów
    i audio z zapasem 30 s, najwyżej SZUM_MAX. Jeden pomiar na plik, wynik do build_command(szum=...)."""
    zak: dict[str, list[float]] = {}
    for x in [*p["clips"], *p["audio"]]:
        if glos_opoznienie(x.get("voice")):
            z = zak.setdefault(str(x["src"]), [x["in"], x["out"]])
            z[0], z[1] = min(z[0], x["in"]), max(z[1], x["out"])
    return {s: (max(0.0, a - 30), min(SZUM_MAX, b - max(0.0, a - 30) + 30)) for s, (a, b) in zak.items()}


def glos_wejscie(od: float, dl: float, poziom: str | None, tlo: float | None) -> tuple[list[str], str]:
    """Osobne wejście dźwięku z zapasem przed `od` i łańcuch: głos, ścięcie zapasu i opóźnienia afftdn.
    Zwraca (argumenty wejścia, filtr po asetpts) dla odcinka źródła od `od` długości `dl`."""
    z = min(GLOS_ZAPAS, max(0.0, od))
    lat = glos_opoznienie(poziom)
    return (["-ss", _f(od - z), "-t", _f(dl + z + lat + 0.05)],
            f"{glos_filter(poziom, tlo)},atrim=start={_f(z + lat)},asetpts=PTS-STARTPTS")


def glos_probka_cmd(src: Path, a: float, d: float, poziom: str | None, tlo: float | None, out: Path,
                    ffmpeg: str = "ffmpeg") -> list[str]:
    """Kawałek dźwięku klipu po czyszczeniu głosu (odsłuch w edytorze przed eksportem). MP3, bo gra w każdej
    przeglądarce (Chromium bez kodeków własnościowych nie odtwarza AAC)."""
    wej, ch = glos_wejscie(a, d, poziom, tlo)
    return [ffmpeg, "-nostdin", "-hide_banner", "-y", "-loglevel", "error", *wej, "-i", str(src), "-vn", "-map", "0:a:0",
            "-af", f"asetpts=PTS-STARTPTS,{ch},atrim=duration={_f(d)}", "-c:a", "libmp3lame", "-b:a", "160k", str(out)]


def blur_filter(W: int, H: int, i: int) -> str:
    """„Rozmyte tło”: całe ujęcie na środku, pod nim to samo ujęcie pokrywające kadr, rozmyte i lekko przyciemnione
    (jak `film.py --tryb rozmyte`; podgląd: blurBg w przeglądarce). Etykiety z numerem klipu: jeden graf na eksport.
    Promień rośnie z kadrem (24 px przy 1080), bo boxblur odrzuca promień większy niż ćwierć krótszego boku."""
    r = max(2, round(min(W, H) * 0.022))
    return (f"split[bg{i}][fg{i}];[bg{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur={r}:2,eq=brightness=-0.08[bb{i}];[fg{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[ff{i}];"
            f"[bb{i}][ff{i}]overlay=(W-w)/2:(H-h)/2")


def rozmycie_przejscia(i: int, L: float, F: int, smax: float, glowa: float, ogon: float) -> str:
    """Przejście „rozmycie” na odcinku klipu i (długość L): σ rośnie liniowo do pełnego `smax` na końcu (ogon = długość
    przejścia za klipem) i maleje od pełnego na początku (głowa = przejście przed klipem); przenikanie robi xfade.
    Krok co klatkę przez sendcmd, a poza oknami gblur jest wyłączony (enable). Podgląd: CSS blur w przejscieStyl."""
    cmds, okna = [], []
    if glowa:
        n = max(1, round(glowa * F))
        cmds += [(k / F, smax * (1 - k / n)) for k in range(n + 1)]
        okna.append(f"between(t,0,{_f(glowa)})")
    if ogon:
        n, t0 = max(1, round(ogon * F)), L - ogon
        cmds += [(t0 + k / F, smax * k / n) for k in range(n + 1)]
        okna.append(f"between(t,{_f(t0)},{_f(L + 1)})")
    lista = ";".join(f"{t:.4f} gblur@pb{i} sigma {s:.2f}" for t, s in cmds)
    return f",sendcmd=c='{lista}',gblur@pb{i}=sigma=0:enable='{'+'.join(okna)}'"


def maska_dir(video: Path) -> Path:
    """Sylwetki osoby do typografii „za osobą” (Wideograf: maska.py klatki): `<film>.maska/` obok filmu."""
    return video.with_name(f"{video.stem}.maska")


def _k3(x: Any, d: float) -> str:
    try:
        return f"{float(x if x is not None else d):.3f}"
    except (TypeError, ValueError):
        return f"{d:.3f}"


def maska_klucz(p: dict) -> str:
    """Klucz osi dla sylwetek: klipy (plik, przycięcie, tempo, kadr) i kadr. Inna oś = inne klatki, sylwetki nie
    pasują. Ten sam napis liczy edytor HQ (maskaKlucz w 48-typografia.js), więc podgląd wie, czy maska jest aktualna."""
    parts = []
    for c in p.get("clips") or []:
        fit = c.get("fit") if c.get("fit") in ("cover", "blur") else "contain"
        kadr = f",{_k3(c.get('fx'), 0.5)},{_k3(c.get('fy'), 0.5)},{_k3(c.get('zoom'), 1)}" if fit == "cover" else ""
        parts.append(f"{c.get('src')}|{_k3(c.get('in'), 0)}|{_k3(c.get('out'), 0)}|{_k3(c.get('speed'), 1)}|{fit}{kadr}")
    cv = p.get("canvas") or {}
    return ";".join(parts) + f"#{int(cv.get('w') or 0)}x{int(cv.get('h') or 0)}@{_k3(cv.get('fps'), 30)}"


def maska_indeks(video: Path, raw: dict) -> dict | None:
    """indeks.json sylwetek, gdy pasuje do osi projektu `raw` (klucz i fps), inaczej None."""
    try:
        idx = json.loads((maska_dir(video) / "indeks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    cv = raw.get("canvas") or {}
    if not isinstance(idx, dict) or idx.get("klucz") != maska_klucz(raw) or _k3(idx.get("fps"), 0) != _k3(cv.get("fps"), 30):
        return None
    return idx


def maska_concat(video: Path, raw: dict, p: dict, tmpdir: Path) -> Path | None:
    """Warstwa sylwetek pod eksport (lista concat jak typo_concat): klatki bloków z częścią „za osobą” (warstwa „tyl”,
    efekt, słowo z głębią za osobą), które mają sylwetkę; reszta przezroczysta. Brak takich bloków albo nieaktualna
    maska = None (napis zostaje w całości widoczny)."""
    tyl = [b for b in (p.get("typo") or {}).get("bloki", []) if "tyl" in typo_warstwy(b)]
    idx = maska_indeks(video, raw) if tyl else None
    if not idx:
        return None
    F, d = float(p["canvas"]["fps"]), maska_dir(video)
    jest = {int(k) for k in idx.get("klatki") or [] if isinstance(k, int)}
    n = max(1, round(p["duration"] * F))
    w = [False] * n
    for b in tyl:
        for k in range(max(0, int(b["start"] * F)), min(n, int(round(b["end"] * F)) + 1)):
            w[k] = k in jest and (d / f"k{k:06d}.png").is_file()
    if not any(w):
        return None
    segs: list[tuple[float, Path | None]] = []
    for k, on in enumerate(w):
        png = d / f"k{k:06d}.png" if on else None
        if segs and png is None and segs[-1][1] is None:
            segs[-1] = (segs[-1][0] + 1 / F, None)
        else:
            segs.append((1 / F, png))
    blank = blank_png(tmpdir / "maska-pusta.png", int(idx.get("w") or 32), int(idx.get("h") or 32))
    return typo_concat(segs, blank, tmpdir / "maska.ffconcat")


def xfade_graph(tr: list[dict | None], dlug: list[float], F: int) -> list[str]:
    """Łączenie odcinków [v{i}][a{i}] o długościach `dlug`: klipy bez przejścia między sobą sklejone (concat), grupy
    nałożone przejściem (xfade obrazu, acrossfade dźwięku) o długość przejścia; wynik [vc][ac]."""
    grupy: list[list[int]] = [[0]]
    for i in range(1, len(dlug)):
        if tr[i - 1]:
            grupy.append([i])
        else:
            grupy[-1].append(i)
    graph: list[str] = []
    cur: tuple[str, str] | None = None
    cur_len = 0.0
    for g, idx in enumerate(grupy):
        if len(idx) == 1:
            lv, la = f"v{idx[0]}", f"a{idx[0]}"
        else:
            graph.append(f"{''.join(f'[v{i}][a{i}]' for i in idx)}concat=n={len(idx)}:v=1:a=1[gq{g}][ga{g}]")
            graph.append(f"[gq{g}]fps={F}[gv{g}]")
            lv, la = f"gv{g}", f"ga{g}"
        glen = sum(dlug[i] for i in idx)
        if cur is None:
            cur, cur_len = (lv, la), glen
            continue
        t = tr[idx[0] - 1]
        ov, oa = ("vc", "ac") if g == len(grupy) - 1 else (f"xv{g}", f"xa{g}")
        graph.append(f"[{cur[0]}][{lv}]xfade=transition={'fade' if t['type'] == 'blur' else t['type']}:"
                     f"duration={_f(t['d'])}:offset={_f(cur_len - t['d'])}[{ov}]")
        graph.append(f"[{cur[1]}][{la}]acrossfade=d={_f(t['d'])}:c1=tri:c2=tri[{oa}]")
        cur, cur_len = (ov, oa), cur_len + glen - t["d"]
    return graph


def build_command(p: dict, has_audio: dict, text_pngs: list[Path], out: Path,
                  ffmpeg: str = "ffmpeg", karaoke: Path | None = None, typo: dict | None = None,
                  maska: Path | None = None, sdr: dict | None = None, szum: dict | None = None) -> list[str]:
    """Argumenty ffmpeg dla znormalizowanego projektu. `has_audio[src] -> bool` z ffprobe.
    `sdr[src]` = łańcuch HDR → zwykły obraz z probe() (film HDR z telefonu); stoi za kadrem, przed korekcją koloru.
    `szum[src]` = tło nagrania w dB (szum_z_logu) pod czysty głos („voice”); brak = GLOS_TLO.
    `typo` = {"tyl": lista concat, "przod": lista concat}: warstwy typografii (z typo_concat) pod tekstami.
    `maska` = lista concat sylwetek (maska_concat): osoba z filmu wraca nad warstwę „tyl”, więc napis jest za nią.
    Wirtualna kamera typografii (`p["typo"]["kamera"]`, kamera_filter) przesuwa film i sylwetkę tym samym ruchem."""
    W, H, F = p["canvas"]["w"], p["canvas"]["h"], p["canvas"]["fps"]
    args = [ffmpeg, "-nostdin", "-hide_banner", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]
    graph: list[str] = []
    n = 0
    seg_labels = []
    # przejście na środku cięcia: odcinek klipu jest dłuższy o połowę przejścia przed nim (pre) i za nim (post),
    # a xfade nakłada sąsiednie odcinki o całe przejście, więc film trwa tyle samo co bez przejść
    tr = p.get("przejscia") or [None] * len(p["clips"])
    jest_tr = any(tr)
    smax = max(2, round(min(W, H) / ROZMYCIE_PRZEJSCIA))
    dlug: list[float] = []
    for i, c in enumerate(p["clips"]):
        sp = c["speed"]
        pre = tr[i - 1]["d"] / 2 if i and tr[i - 1] else 0.0
        post = tr[i]["d"] / 2 if tr[i] else 0.0
        L = (c["out"] - c["in"]) / sp + pre + post
        dlug.append(L)
        brak = 0.0                     # materiału przed klipem za mało na połowę przejścia: pierwsza klatka stoi
        if c["kind"] == "image":
            args += ["-loop", "1", "-framerate", str(F), "-t", _f(L), "-i", str(c["src"])]
        else:
            od = c["in"] - pre * sp
            brak, od = max(0.0, -od / sp), max(0.0, od)
            args += ["-ss", _f(od), "-t", _f(c["out"] + post * sp - od), "-i", str(c["src"])]
        vi = n; n += 1
        fit = (cover_filter(W, H, c) if c["fit"] == "cover" else blur_filter(W, H, i) if c["fit"] == "blur"
               else f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black")
        glowa = tr[i - 1]["d"] if i and tr[i - 1] and tr[i - 1]["type"] == "blur" else 0.0
        ogon = tr[i]["d"] if tr[i] and tr[i]["type"] == "blur" else 0.0
        kol = kolor_filter(c.get("color"))      # korekcja koloru po kadrze: obejmuje też rozmyte tło, jak w podglądzie
        hd = (sdr or {}).get(str(c["src"])) if c["kind"] == "video" else ""
        graph.append(f"[{vi}:v]setpts=(PTS-STARTPTS)/{_f(sp)},fps={F},{fit}{',' + hd if hd else ''}"
                     f"{',' + kol if kol else ''},setsar=1,format=yuv420p,"
                     + (f"tpad=start_mode=clone:start_duration={_f(brak)}," if brak > 1e-4 else "")
                     + f"tpad=stop_mode=clone:stop_duration={_f(post + 1)},trim=duration={_f(L)},setpts=PTS-STARTPTS"
                     + (rozmycie_przejscia(i, L, F, smax, glowa, ogon) if glowa or ogon else "")
                     + (f",fps={F}" if jest_tr else "") + f"[v{i}]")    # xfade chce stałej liczby klatek
        if c["kind"] == "video" and not c["muted"] and has_audio.get(str(c["src"])) and c["volume"] > 0:
            ai, glos = vi, ""
            if c.get("voice"):              # czysty głos: osobne wejście dźwięku z zapasem (glos_wejscie)
                wej, glos = glos_wejscie(max(0.0, c["in"] - pre * sp), c["out"] + post * sp - max(0.0, c["in"] - pre * sp),
                                         c["voice"], (szum or {}).get(str(c["src"])))
                args += [*wej, "-i", str(c["src"])]
                ai = n; n += 1
            chain = ",".join(x for x in ("asetpts=PTS-STARTPTS", glos, _atempo(sp),
                                         f"volume={_f(c['volume'])}" if c["volume"] != 1 else "") if x)
            graph.append(f"[{ai}:a]{chain},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                         + (f"adelay={round(brak * 1000)}:all=1," if brak > 1e-4 else "")
                         + f"apad,atrim=duration={_f(L)},asetpts=PTS-STARTPTS"
                         # cięcie bez przejścia i bez zaniku dostaje mikro-wyciszenie (przejście ma acrossfade);
                         # podział ciągłego materiału nie jest cięciem dźwięku, więc zostaje bez wyciszenia
                         + (f",{zan}" if (zan := afade(c.get("fade_in", 0) or (0 if pre or (i and ciagly(p["clips"][i - 1], c))
                                                                                else ciche_ciecie(L - pre - post)),
                                                       c.get("fade_out", 0) or (0 if post or ciagly(c, (p["clips"][i + 1:] or [None])[0])
                                                                                 else ciche_ciecie(L - pre - post)),
                                                       pre, L - pre - post)) else "")
                         + f"[a{i}]")
        else:
            graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={_f(L)},aformat=sample_fmts=fltp[a{i}]")
        seg_labels.append(f"[v{i}][a{i}]")
    if not jest_tr:
        graph.append(f"{''.join(seg_labels)}concat=n={len(p['clips'])}:v=1:a=1[vc][ac]")
    else:
        graph += xfade_graph(tr, dlug, F)

    vlast, osoba = "vc", None
    kam = kamera_filter(p.get("typo") or {}, F)     # wirtualna kamera typografii: film (i osoba) na głębokości z = 1
    if kam:
        graph.append(f"[vc]{kam}[vkam]")
        vlast = "vkam"
    if maska and (typo or {}).get("tyl"):
        graph.append(f"[{vlast}]split[vcm][vco]")  # kopia klatki: z niej wycinamy osobę według sylwetki
        vlast, osoba = "vcm", "vco"
    # Warstwy z listy concat (typografia, maska, karaoke): długi odcinek to jedna klatka, którą `fps` powtarza od razu
    # (np. 3 s × 60 kl.). Konwersja formatu stoi więc PRZED `fps`, a nakładka ma ten sam format (yuv420): powtórzenie
    # to odwołanie do tej samej klatki. Konwersja za `fps` robiła z każdego powtórzenia pełną klatkę w pamięci
    # (4K z iPhone'a: ponad 4,5 GB i zabity ffmpeg; na długim filmie pamięć rosła z czasem pustego odcinka).
    for warstwa in ("tyl", "przod"):       # typografia: najpierw warstwa „za osobą”, potem przednia
        lista = (typo or {}).get(warstwa)
        if not lista:
            continue
        args += ["-reinit_filter", "0", "-f", "concat", "-safe", "0", "-i", str(lista)]
        yi = n; n += 1
        graph.append(f"[{yi}:v]format=yuva420p,fps={F}[ty{warstwa}]")
        graph.append(f"[{vlast}][ty{warstwa}]overlay=0:0:format=yuv420:eof_action=pass[vy{warstwa}]")
        vlast = f"vy{warstwa}"
        if warstwa == "tyl" and osoba:
            args += ["-reinit_filter", "0", "-f", "concat", "-safe", "0", "-i", str(maska)]
            mi = n; n += 1
            # sylwetka idzie za kamerą tak samo jak film, więc osoba z kopii klatki trafia w swoje miejsce
            graph.append(f"[{mi}:v]scale={W}:{H}:flags=bicubic,format=rgba,alphaextract,fps={F}{',' + kam if kam else ''}[mka]")
            graph.append(f"[{osoba}]format=rgba[osb];[osb][mka]alphamerge[osa]")
            graph.append(f"[{vlast}][osa]overlay=0:0:format=yuv420:eof_action=pass[vos]")
            vlast = "vos"
    for k, (t, png) in enumerate(zip(p["texts"], text_pngs)):
        if t.get("kara") and karaoke:
            continue                        # ten napis jest w warstwie karaoke niżej
        args += ["-i", str(png)]
        ti = n; n += 1
        graph.append(f"[{vlast}][{ti}:v]overlay=0:0:format=auto:enable='between(t,{_f(t['start'])},{_f(t['end'])})'[vt{k}]")
        vlast = f"vt{k}"

    if karaoke:
        # -reinit_filter 0: obrazy mogą mieć różny format pikseli (RGB/RGBA); bez tego ffmpeg przebudowuje graf
        # w trakcie i nakładka gubi warstwę (sprawdzone testem na kolorach)
        args += ["-reinit_filter", "0", "-f", "concat", "-safe", "0", "-i", str(karaoke)]
        ki = n; n += 1
        graph.append(f"[{ki}:v]format=yuva420p,fps={F}[kl]")
        graph.append(f"[{vlast}][kl]overlay=0:0:format=yuv420:eof_action=pass[vk]")
        vlast = "vk"

    alast = "ac"
    if p["audio"]:
        mix = ["[ac]"]
        for k, m in enumerate(p["audio"]):
            glos = ""
            if m.get("voice"):
                wej, glos = glos_wejscie(m["in"], m["out"] - m["in"], m["voice"], (szum or {}).get(str(m["src"])))
                glos += f",atrim=duration={_f(m['out'] - m['in'])}"
                args += [*wej, "-i", str(m["src"])]
            else:
                args += ["-ss", _f(m["in"]), "-t", _f(m["out"] - m["in"]), "-i", str(m["src"])]
            mi = n; n += 1
            ms = int(round(m["start"] * 1000))
            # audio przycięte od środka: mikro-wyciszenie na początku (od początku pliku zostaje atak efektu) i na końcu
            mik = ciche_ciecie(m["out"] - m["in"])
            dalej = any(ciagle_audio(m, x) for x in p["audio"])        # podzielone audio gra dalej bez dziury
            dalszy = any(ciagle_audio(x, m) for x in p["audio"])
            zan = afade(m.get("fade_in", 0) or (mik if m["in"] > 0.001 and not dalszy else 0),
                        m.get("fade_out", 0) or (0 if dalej else mik), 0, m["out"] - m["in"])
            graph.append(f"[{mi}:a]asetpts=PTS-STARTPTS,{glos + ',' if glos else ''}volume={_f(m['volume'])},aresample=48000,"
                         f"aformat=sample_fmts=fltp:channel_layouts=stereo,{zan + ',' if zan else ''}adelay={ms}|{ms}[m{k}]")
            mix.append(f"[m{k}]")
        graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,"
                     f"{LIMITER_EKSPORTU}[amx]")
        alast = "amx"

    args += ["-filter_complex", ";".join(graph), "-map", f"[{vlast}]", "-map", f"[{alast}]",
             "-t", _f(p["duration"]), "-r", str(F),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    return args


def obrot(v: dict) -> int:
    """Obrót wyświetlania strumienia wideo w stopniach (0, 90, 180, 270). Telefon zapisuje film pionowy jako poziome
    klatki z macierzą obrotu: ffmpeg 5+ podaje ją w side_data_list („rotation”), starszy w tagu `rotate`."""
    for sd in v.get("side_data_list") or []:
        if sd.get("rotation") is not None:
            try:
                return int(round(float(sd["rotation"]))) % 360
            except (TypeError, ValueError):
                break
    try:
        return int(round(float((v.get("tags") or {}).get("rotate", 0)))) % 360
    except (TypeError, ValueError):
        return 0


# HDR z telefonu → zwykły obraz (SDR, BT.709). Za kajisho5/ffmpeg-skill (MIT, color.py i probe.py): rozpoznanie
# po znacznikach strumienia i Dolby Vision, łańcuch zscale + tonemap. iPhone nagrywa domyślnie HDR (Dolby Vision
# z warstwą HLG): bez przeliczenia sama zamiana na yuv420p daje szary, sprany obraz (pomiar na syntetycznym HLG
# z obrazu testowego: nasycenie 44 zamiast 117, PQ: 25). Krzywa mobius z przejściem 0,5 i bez odbarwiania wraca
# do 110 przy jasności 123/126; hable przyciemnia (100/126), domyślne desat=2 zabiera kolor (61).
HDR_TRC = {"smpte2084": "HDR10 (PQ)", "arib-std-b67": "HLG"}
TONEMAP = "mobius:param=0.5:desat=0"
_ZSCALE_TRC = {"bt709", "bt2020-10", "bt2020-12", "smpte170m", "bt470bg", "bt470m", "smpte240m", "iec61966-2-1"}
_ZSCALE_MAT = {"bt709", "bt2020nc", "bt2020c", "smpte170m", "bt470bg", "smpte240m", "fcc", "ycgco"}
PROBE_KOLOR = "color_transfer,color_primaries,color_space,color_range"
PROBE_SIDE = "rotation,side_data_type,dv_profile,dv_bl_signal_compatibility_id"


def hdr(v: dict) -> dict | None:
    """Strumień wideo z ffprobe (znaczniki koloru i side_data_list) → opis HDR albo None (zwykły obraz).
    `tonemap`: sygnał HDR (PQ, HLG, Dolby Vision) do zmapowania; BT.2020 bez HDR potrzebuje tylko zmiany gamy."""
    trc, prim = v.get("color_transfer") or "", v.get("color_primaries") or ""
    dovi = next((sd for sd in v.get("side_data_list") or []
                 if "dv_profile" in sd or "DOVI" in str(sd.get("side_data_type") or "")), None)
    mat = v.get("color_space") if v.get("color_space") in _ZSCALE_MAT else "bt2020nc"
    rng = "pc" if v.get("color_range") in ("pc", "jpeg", "full") else "tv"
    if trc in HDR_TRC or dovi:
        uwaga = None
        if dovi:
            prof = dovi.get("dv_profile")
            rodzaj = f"Dolby Vision{f' (profil {prof})' if prof is not None else ''}"
            if trc not in HDR_TRC:          # warstwa bazowa bez znaczników: profil 8.1 to HDR10 (PQ)
                trc = "smpte2084"
            if str(prof) == "5":
                uwaga = "profil 5 nie ma warstwy zgodnej z HDR10/HLG: kolory po przeliczeniu mogą być przesunięte"
        else:
            rodzaj = HDR_TRC[trc]
        return {"rodzaj": rodzaj, "tonemap": True, "trc": trc, "prim": "bt2020", "mat": mat, "range": rng, "uwaga": uwaga}
    if prim == "bt2020":
        return {"rodzaj": "BT.2020 (SDR)", "tonemap": False, "trc": trc if trc in _ZSCALE_TRC else "bt709",
                "prim": "bt2020", "mat": mat, "range": rng, "uwaga": None}
    return None


def sdr_filter(h: dict | None) -> str:
    """Łańcuch filtrów HDR → SDR BT.709 yuv420p ("" dla zwykłego obrazu). Liczy w float RGB, więc stawiamy go PO
    skalowaniu do kadru (4K: 8× wolniej przed skalowaniem, po nim ok. 2× czasu samego kadrowania); korekcja koloru
    i napisy idą za nim, bo zakładają zwykły obraz."""
    if not h:
        return ""
    wej = (f"zscale=tin={h['trc']}:pin={h['prim']}:min={h['mat']}:rin={h['range']}:t=linear:npl=100,"
           "format=gbrpf32le,zscale=p=bt709")
    mapa = f",tonemap=tonemap={TONEMAP}" if h["tonemap"] else ""
    return f"{wej}{mapa},zscale=t=bt709:m=bt709:r=tv,format=yuv420p"


def probe(path: Path, ffprobe: str = "ffprobe") -> dict:
    """Czas, wymiary (tak jak film się wyświetla, po obrocie) i obecność dźwięku (ffprobe). Obraz: wymiary, bez czasu.
    `hdr`: rodzaj HDR (np. „HLG”) albo None, `sdr`: łańcuch przeliczenia na zwykły obraz (sdr_filter) albo ""."""
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                            f"format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,{PROBE_KOLOR}"
                            f":stream_side_data={PROBE_SIDE}:stream_tags=rotate",
                            "-of", "json", str(path)], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20)
        data = json.loads(r.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"ok": False}
    streams = data.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    w, h = v.get("width"), v.get("height")
    if obrot(v) in (90, 270):           # ffmpeg obraca klatki przy dekodowaniu, więc kadr liczymy po obrocie
        w, h = h, w
    fps = None
    if v.get("r_frame_rate") and "/" in v["r_frame_rate"]:
        a, b = v["r_frame_rate"].split("/")
        fps = round(float(a) / float(b), 3) if float(b) else None
    dur = (data.get("format") or {}).get("duration")
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    hd = hdr(v) if v and media_kind(path) == "video" else None
    return {"ok": True, "duration": float(dur) if dur not in (None, "N/A") else None, "w": w, "h": h, "fps": fps,
            "audio": bool(a), "acodec": a.get("codec_name"),
            "video": bool(v) and media_kind(path) != "audio", "vcodec": v.get("codec_name"),
            "hdr": hd and hd["rodzaj"], "sdr": sdr_filter(hd)}


def export_name(video: Path) -> Path:
    """Wolna nazwa obok oryginału: film-edycja.mp4, film-edycja-2.mp4… (nigdy nie nadpisujemy)."""
    stem = re.sub(r"-edycja(-\d+)?$", "", video.stem)
    for k in range(1, 1000):
        cand = video.with_name(f"{stem}-edycja{'' if k == 1 else f'-{k}'}.mp4")
        if not cand.exists():
            return cand
    raise ProjectError("Za dużo wersji tego filmu w katalogu.")


def parse_progress(chunk: str) -> float | None:
    """Sekundy wyjścia z bloku `-progress` ffmpeg (out_time_us albo out_time_ms, oba w µs)."""
    val = None
    for line in chunk.splitlines():
        k, _, v = line.partition("=")
        if k in ("out_time_us", "out_time_ms") and v.strip().lstrip("-").isdigit():
            val = max(0.0, int(v) / 1e6)
    return val


_SRT_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})")


def _srt_sec(m: re.Match) -> float:
    h, mi, se, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(se) + int(ms.ljust(3, "0")) / 1000


def parse_srt(text: str, limit: int = 5000) -> list[dict]:
    """Napisy SRT → [{start, end, text}] (bloki bez czasu pomijamy, tagi <i> itp. usuwamy)."""
    out = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "").replace("\ufeff", "").strip()):
        lines = [x for x in block.split("\n") if x.strip()]
        for i, line in enumerate(lines):
            if "-->" in line:
                a, _, b = line.partition("-->")
                ma, mb = _SRT_TIME.search(a), _SRT_TIME.search(b)
                body = re.sub(r"<[^>]+>", "", "\n".join(lines[i + 1:])).strip()
                if ma and mb and body and _srt_sec(mb) > _srt_sec(ma):
                    out.append({"start": _srt_sec(ma), "end": _srt_sec(mb), "text": body})
                break
        if len(out) >= limit:
            break
    return out


def _srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def to_srt(lines: list[dict]) -> str:
    return "".join(f"{i}\n{_srt_ts(x['start'])} --> {_srt_ts(x['end'])}\n{x['text']}\n\n" for i, x in enumerate(lines, 1))


def auto_srt_path(src: Path) -> Path:
    """Napisy z mowy zapisujemy obok źródła: następnym razem wczytują się od razu (i widzi je agent)."""
    return src.with_name(f"{src.stem}.auto.srt")


def stt_bin() -> str | None:
    env = os.environ.get("JARVO_STT_BIN")
    if env:
        return env if Path(env).exists() else None
    return shutil.which("jarvo-stt") or ("/opt/jarvo/bin/jarvo-stt" if Path("/opt/jarvo/bin/jarvo-stt").exists() else None)


def kroje_css(root: Path | None, rodziny: set[str] | None = None) -> str:
    """kroje.css z plikami wstawionymi jako data: URL (przeglądarka bez okna nie sięga do plików ani do sieci).
    `root` = katalog kroje/ (hq/web/fonts/kroje w repo, scripts/kroje w profilu Wideografa); brak = pusty CSS.
    `rodziny` = tylko te kroje (render wstawia te, których projekt używa: wszystkie to kilka MB i sekunda startu)."""
    import base64
    if not root or not (Path(root) / "kroje.css").is_file():
        return ""
    root = Path(root)
    css = (root / "kroje.css").read_text(encoding="utf-8")
    if rodziny is not None:
        css = "\n".join(r for r in css.splitlines() if not r.startswith("@font-face")
                        or (m := re.search(r'font-family: "([^"]+)"', r)) and m.group(1) in rodziny) + "\n"

    def inline(m: re.Match) -> str:
        f = root / m.group(1)
        if f.suffix != ".woff2" or f.parent != root or not f.is_file():
            return m.group(0)
        return f"url(data:font/woff2;base64,{base64.b64encode(f.read_bytes()).decode()})"
    return re.sub(r"url\(([\w.-]+)\)", inline, css)


def tools() -> dict:
    """ffmpeg, ffprobe i jarvo-stt z PATH procesu: w obrazie /usr/bin i /opt/jarvo/bin, natywnie narzędzia
    z manifestu (`<program>/narzedzia/ffmpeg/<wersja>/bin`) i bin-floty, które jarvo/srodowisko.py daje panelowi."""
    return {"ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"), "stt": stt_bin()}


# ----------------------------------------------------------------------------- programy z dziećmi (Windows)
# Dashboard uruchamia programy, które mają własne dzieci: lektor (`python film.py lektor` → jarvo-tts.exe →
# Python), jarvo-stt.exe (trampolina uv → Python → ffmpeg). Na Windows TerminateProcess kończy tylko sam program,
# a launcher venvu Pythona wypuszcza wnuki ze swojego zadania (sprawdzone 2026-10-25 na Windows 11: po zabiciu
# `python.exe` venvu jarvo-tts.exe i jego Python żyły dalej; zabita trampolina uv kończy swoje dzieci sama).
# `przypnij_drzewo(proc)` zaraz po starcie daje programowi własny Job Object z JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
# którego uchwyt trzyma dashboard: dzieci programu dziedziczą zadanie, `zabij_drzewo(proc)` kończy całe drzewo
# (anulowanie eksportu, limit czasu), a uchwyt zamyka się z obiektem procesu albo z samym dashboardem (padnięty
# dashboard = koniec jego programów, bez sierot piszących pliki). Na Linuksie i macOS bez zmian: proc.kill().
# Używa ich lektor aplikacji (glos.py: przy_starcie w przenosne.uruchom); trasy edytora w plugin_api.py (eksport,
# lektor, analiza mowy) podłącza się tak samo: przy_starcie=przypnij_drzewo, anulowanie przez zabij_drzewo.
_JOB_KILL_ON_JOB_CLOSE = 0x2000
_JOB_EXTENDED_LIMIT_INFORMATION = 9


def _k32():
    """kernel32 z typami funkcji Job Object (ctypes, bez pywin32)."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    k.SetInformationJobObject.restype = wintypes.BOOL
    k.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    k.AssignProcessToJobObject.restype = wintypes.BOOL
    k.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k.TerminateJobObject.restype = wintypes.BOOL
    k.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    k.CloseHandle.restype = wintypes.BOOL
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k


def _limity_zadania():
    """JOBOBJECT_EXTENDED_LIMIT_INFORMATION z samym KILL_ON_JOB_CLOSE (bez limitów pamięci i czasu)."""
    import ctypes
    from ctypes import wintypes

    class Podstawowe(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class Io(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                    "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Rozszerzone(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Podstawowe), ("IoInfo", Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    info = Rozszerzone()
    info.BasicLimitInformation.LimitFlags = _JOB_KILL_ON_JOB_CLOSE
    return info


def _zamknij_zadanie(uchwyt: int) -> None:
    try:
        _k32().CloseHandle(uchwyt)
    except OSError:
        pass


def przypnij_drzewo(proc: subprocess.Popen) -> bool:
    """Windows: program `proc` (zaraz po starcie) w nowym Job Object z KILL_ON_JOB_CLOSE; jego dzieci dziedziczą
    zadanie. Uchwyt zostaje przy `proc` (`_jarvo_zadanie`) i zamyka się razem z obiektem procesu (weakref.finalize),
    a zamknięcie kończy procesy drzewa, które jeszcze żyją. False poza Windows albo gdy system odmówi (program
    działa wtedy jak dotąd, bez zadania)."""
    if os.name != "nt" or getattr(proc, "_jarvo_zadanie", None):
        return False
    import ctypes
    import weakref
    try:
        k = _k32()
        uchwyt = k.CreateJobObjectW(None, None)
        if not uchwyt:
            return False
        info = _limity_zadania()
        if not (k.SetInformationJobObject(uchwyt, _JOB_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                                          ctypes.sizeof(info))
                and k.AssignProcessToJobObject(uchwyt, int(proc._handle))):
            k.CloseHandle(uchwyt)
            return False
    except (OSError, AttributeError, ValueError):
        return False
    proc._jarvo_zadanie = uchwyt
    weakref.finalize(proc, _zamknij_zadanie, uchwyt)
    return True


def zabij_drzewo(proc: subprocess.Popen) -> None:
    """Koniec programu i jego dzieci bez czekania: Windows z zadaniem z `przypnij_drzewo` = TerminateJobObject, potem
    zawsze kill() samego programu (SIGKILL na POSIX, TerminateProcess na Windows); zakończony pomija."""
    uchwyt = getattr(proc, "_jarvo_zadanie", None)
    if uchwyt and os.name == "nt":
        try:
            _k32().TerminateJobObject(uchwyt, 1)
        except OSError:
            pass
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:              # skończył się między poll() a kill()
            pass


# ----------------------------------------------------------------------------- audio: biblioteka, wyodrębnienie, lektor
# Biblioteka dźwięków CC0 (scripts/dzwieki.py): hq/web/dzwieki w repo, dzwieki/ obok wtyczki, scripts/dzwieki
# u Wideografa. Dodanie kopiuje plik obok filmu, więc projekt nie zależy od biblioteki (jak przy wgranym pliku).
DZWIEKI_DIR = "dzwieki"      # podkatalog katalogu filmu: efekty z biblioteki i dźwięk wyodrębniony z filmów
LEKTOR_DIR = "lektor"        # podkatalog katalogu filmu: lektor (Matcha, Paradee, Edge TTS) i nagrania z mikrofonu
# pierwszy = domyślny (lokalny polski Matcha, jak wideo_lib.DEFAULT_VOICE); Edge TTS do wyboru
GLOSY = ("pl-PL-Matcha-Meski", "pl-PL-Matcha-Damski", "pl-PL-MarekNeural", "pl-PL-ZofiaNeural",
         "en-US-AndrewMultilingualNeural", "en-US-AvaMultilingualNeural", "de-DE-SeraphinaMultilingualNeural",
         "en-US-Paradee")
# bez sieci (jarvo-tts w obrazie): polski Matcha (głos syntetyczny) i angielski Paradee; czasy słów z Parakeeta
GLOSY_LOKALNE = ("pl-PL-Matcha-Meski", "pl-PL-Matcha-Damski", "en-US-Paradee")
LEKTOR_MAX = 3000            # znaków tekstu lektora z edytora


def dzwieki_katalog(root: Path | None) -> dict:
    """katalog.json biblioteki (kategorie, role efektów w kolejności wyboru i dźwięki); brak = pusta biblioteka."""
    try:
        kat = json.loads((Path(root) / "katalog.json").read_text(encoding="utf-8")) if root else {}
    except (OSError, ValueError):
        kat = {}
    return {"kategorie": kat.get("kategorie") or [], "role": kat.get("role") or {}, "dzwieki": kat.get("dzwieki") or []}


def dzwiek_plik(root: Path | None, id_: str) -> tuple[dict, Path] | None:
    """Wpis i plik dźwięku z biblioteki po id (plik tylko z katalog.json, wewnątrz biblioteki)."""
    w = next((d for d in dzwieki_katalog(root)["dzwieki"] if d.get("id") == id_), None)
    if not w or not root:
        return None
    base = Path(root).resolve()
    p = (base / str(w.get("plik") or "")).resolve()
    if base not in p.parents or not p.is_file():
        return None
    return w, p


def dzwiek_do_filmu(root: Path | None, id_: str, film: Path) -> Path:
    """Kopia dźwięku z biblioteki w <katalog filmu>/dzwieki/<id>.mp3 (ta sama przy kolejnym dodaniu)."""
    hit = dzwiek_plik(root, id_)
    if not hit:
        raise ProjectError(f"Nie ma dźwięku „{id_}” w bibliotece.")
    _w, src = hit
    dest = film.parent / DZWIEKI_DIR / src.name
    if not dest.is_file() or dest.stat().st_size != src.stat().st_size:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.part")
        shutil.copyfile(src, tmp)
        tmp.replace(dest)
    return dest


def _nazwa_pliku(stem: str, limit: int = 40) -> str:
    s = re.sub(r"[^\w-]+", "-", stem, flags=re.UNICODE).strip("-_")[:limit]
    return s or "plik"


def wyodrebnij_cel(film: Path, src: Path) -> Path:
    """<katalog filmu>/dzwieki/<nazwa źródła>-dzwiek.m4a: dźwięk innego filmu jako osobny plik audio."""
    return film.parent / DZWIEKI_DIR / f"{_nazwa_pliku(src.stem)}-dzwiek.m4a"


def wyodrebnij_cmd(src: Path, dest: Path, acodec: str | None, ffmpeg: str = "ffmpeg") -> list[str]:
    """Sam dźwięk z filmu: AAC kopiowany bez straty, inny kodek kodowany do AAC 192 kb/s."""
    enc = ["-c:a", "copy"] if acodec == "aac" else ["-c:a", "aac", "-b:a", "192k"]
    return [ffmpeg, "-nostdin", "-hide_banner", "-y", "-i", str(src), "-map", "0:a:0", "-vn", "-sn", "-dn",
            *enc, "-movflags", "+faststart", str(dest)]


def lektor_cel(film: Path, tekst: str, glos: str, tempo: str) -> Path:
    """<katalog filmu>/lektor/lektor-<początek tekstu>-<skrót>.mp3 (ten sam tekst i głos = ten sam plik)."""
    import hashlib
    h = hashlib.sha256(f"{glos}|{tempo}|{tekst}".encode()).hexdigest()[:8]
    return film.parent / LEKTOR_DIR / f"lektor-{_nazwa_pliku(tekst.lower(), 24)}-{h}.mp3"


def tempo_tts(v: Any) -> str:
    """Tempo lektora jako procent Edge TTS (+10%, -5%), od −50% do +50%."""
    try:
        n = int(round(float(str(v).strip().rstrip("%") or 0)))
    except ValueError:
        n = 0
    n = max(-50, min(50, n))
    return f"{n:+d}%"


def nagranie_cel(film: Path, now: float) -> Path:
    import time
    return film.parent / LEKTOR_DIR / f"nagranie-{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}.m4a"


def nagranie_cmd(src: Path, dest: Path, ffmpeg: str = "ffmpeg") -> list[str]:
    """Nagranie z przeglądarki (webm/opus albo mp4) → AAC mono 48 kHz, które gra w każdej przeglądarce i w eksporcie."""
    return [ffmpeg, "-nostdin", "-hide_banner", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "48000",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dest)]


# ----------------------------------------------------------------------------- mowa: pauzy, wtrącenia, napisy
SILENCE_DB = -35       # próg ciszy (dB); pauza krótsza niż SILENCE_MIN nie jest zaznaczana
SILENCE_MIN = 0.35
_FILLER = re.compile(r"^(y+|e+|ee+m*|m+|h?m+|ym+|em+|uh+m*|um+|eh+m*|ah+|yhm+|mhm+)$")


def is_filler(word: str) -> bool:
    """Wtrącenia typu „yyy”, „eee”, „mmm”, „hmm” (bez interpunkcji i wielkości liter)."""
    w = re.sub(r"[^\w]", "", word.lower())
    return bool(w) and bool(_FILLER.match(w))


def parse_silences(log: str, duration: float | None = None) -> list[list[float]]:
    """Wynik filtra silencedetect → [[start, end], …]; cisza do końca pliku kończy się na `duration`."""
    out, start = [], None
    for line in log.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            out.append([round(start, 3), round(float(m.group(1)), 3)])
            start = None
    if start is not None and duration:
        out.append([round(start, 3), round(duration, 3)])
    return [x for x in out if x[1] - x[0] > 0.05]


def lines_from_words(words: list, max_chars: int = 32, max_gap: float = 0.6, max_dur: float = 3.5) -> list[dict]:
    """Słowa [[start, end, tekst]] → linie napisów zgrane ze słowami (nowa linia po pauzie,
    końcu zdania, za długim tekście albo czasie). Wtrąceń nie pokazujemy w napisach."""
    lines, cur = [], []
    def flush():
        if cur:   # words: czasy słów od początku linii (napisy karaoke, jak groupLines w edytorze)
            lines.append({"start": cur[0][0], "end": cur[-1][1], "text": " ".join(w[2] for w in cur),
                          "words": [[round(w[0] - cur[0][0], 3), round(w[1] - cur[0][0], 3), w[2]] for w in cur]})
            cur.clear()
    for w in words:
        a, b, t = float(w[0]), float(w[1]), str(w[2])
        if is_filler(t):
            continue
        if cur and (a - cur[-1][1] > max_gap or len(" ".join(x[2] for x in cur)) + 1 + len(t) > max_chars
                    or b - cur[0][0] > max_dur):
            flush()
        cur.append((a, b, t))
        if t.endswith((".", "!", "?", "…")):
            flush()
    flush()
    return lines


def speech_path(src: Path) -> Path:
    return src.with_name(f"{src.stem}.mowa.json")


def speech_data(words: list, silences: list, duration: float | None) -> dict:
    return {"v": 1, "duration": duration, "words": words, "silences": silences,
            "fillers": [i for i, w in enumerate(words) if is_filler(str(w[2]))],
            "lines": lines_from_words(words)}


def proxy_key(src: Path, sdr: str = "") -> str:
    import hashlib
    st = src.stat()
    return hashlib.sha1(f"{src}|{st.st_size}|{int(st.st_mtime)}{'|sdr' if sdr else ''}".encode()).hexdigest()[:20]


def proxy_command(src: Path, out: Path, ffmpeg: str = "ffmpeg", sdr: str = "") -> list[str]:
    """Kopia do podglądu, którą odtworzy każda przeglądarka: WebM VP9 do 540 p, klatka kluczowa co 0,5 s
    (szybkie przewijanie), szybkie kodowanie. Eksport i tak bierze oryginał. `sdr` (probe): film HDR dostaje
    podgląd po przeliczeniu kolorów, więc w edytorze widać to samo co w eksporcie."""
    return [ffmpeg, "-nostdin", "-hide_banner", "-y", "-loglevel", "error", "-i", str(src),
            "-vf", f"scale=-2:'min(540,ih)':flags=bilinear,{sdr + ',' if sdr else ''}format=yuv420p",
            "-c:v", "libvpx-vp9", "-deadline", "realtime",
            "-cpu-used", "8", "-row-mt", "1", "-b:v", "1200k", "-g", "15", "-c:a", "libopus", "-b:a", "96k", "-ac", "2",
            "-f", "webm", str(out)]
