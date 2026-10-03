"""Jarvo HQ: edytor filmów (logika bez serwera, testowalna).

Projekt montażu to mały JSON (zapisywany obok filmu jako `<nazwa>.edycja.json`):

    {"version": 1, "canvas": {"w": 1080, "h": 1920, "fps": 30},
     "clips": [{"src": "/opt/data/jarvo/.../film.mp4", "in": 0.0, "out": 4.2, "speed": 1.0,
                "volume": 1.0, "muted": false, "fit": "contain",     # pasy; "blur" = rozmyte tło; "cover" + fx, fy, zoom
                "fadeIn": 0.0, "fadeOut": 0.0,                      # narastanie i wyciszanie dźwięku (s, opcjonalne)
                "transition": {"type": "fade", "dur": 0.5}}],      # przejście do następnego klipu (opcjonalne)
     "texts": [{"start": 0.5, "end": 3.0, ...}],          # wygląd rysuje przeglądarka (PNG na klatkę)
     "audio": [{"src": ".../muzyka.mp3", "start": 0.0, "in": 0.0, "out": 30.0, "volume": 0.4, "fadeOut": 2.0}]}

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
               "nowoczesny", "retro", "neon")   # te same klucze co TYPO_MOTYWY w 48-typografia.js
TYPO_UKLADY = ("kolumna", "schodki", "srodek", "skos", "3d", "za", "rozrzut")
TYPO_WEJSCIA = ("ciecie", "pop", "kontur", "maska", "pisanie", "zjazd")
TYPO_WYJSCIA = ("ciecie", "zanik", "smuga")
TYPO_STYLE = ("wypelnij", "kontur", "3d", "blask", "tlo", "obrys")
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
# Przejścia między klipami: klucz = nazwa przejścia xfade w FFmpeg, "blur" = przenikanie z rozmyciem Gaussa (nasze).
# Te same klucze co ED_PRZEJSCIA w hq/web/src/49-przejscia.js (podgląd rysuje je tymi samymi wzorami).
PRZEJSCIA = ("fade", "fadeblack", "fadewhite", "blur", "zoomin", "pixelize", "slideleft", "slideright", "slideup",
             "slidedown", "coverleft", "coverright", "wipeleft", "wiperight", "smoothleft", "circleopen")
PRZEJSCIE_D = 0.5        # domyślna długość przejścia (s)
ROZMYCIE_PRZEJSCIA = 40  # rozmycie przy cięciu: σ = krótszy bok kadru / 40 (27 px przy 1080)
MAX_AUDIO = 32           # muzyka, lektor i efekty (na osi w pasach jeden pod drugim)
ZANIK_MAX = 10.0         # najdłuższe narastanie albo wyciszanie (s), najwyżej połowa elementu (ZANIK_MAX w 43-dzwiek.js)
MAX_WORDS = 40           # słów w jednym napisie karaoke (linia napisu ma ich 2–8)
MAX_DURATION = 3 * 3600.0
MIN_CLIP = 0.04          # jedna klatka przy 25 fps
FPS_ALLOWED = (24, 25, 30, 50, 60)


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
        out["bloki"].append(nb)
    out["bloki"].sort(key=lambda b: b["start"])
    return out


def typo_concat(segments: list[tuple[float, Path | None]], blank: Path, dest: Path) -> Path | None:
    """Warstwa typografii jako lista demuxera concat: (czas trwania, PNG albo None = przezroczysta klatka).
    Klatki rysuje przeglądarka tylko tam, gdzie obraz się zmienia (typoOdcinki), reszta to długie odcinki."""
    if not any(png for _d, png in segments):
        return None
    lines = ["ffconcat version 1.0"]
    for dur, png in segments:
        if dur >= 0.0005:
            lines.extend([f"file '{png or blank}'", f"duration {dur:.4f}"])
    lines.append(f"file '{blank}'")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
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


def remap_times(p0: dict, p1: dict) -> dict:
    """Oś magnetyczna, ta sama reguła co remapTimes w hq/web/src/45-edytor.js: po zmianie klipów (usunięcie, wstawienie,
    przycięcie, tempo, przestawienie) napisy, uwagi i bloki typografii (z każdym słowem) idą za materiałem, z którego
    pochodzą (czas źródła klipu), a muzyka i lektor przesuwają się o wycięty albo wstawiony czas. Przy samym
    przestawieniu napis i blok jadą w całości z klipem."""
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
    audio = p1.get("audio") or []
    if not reorder:
        audio = [{**m, "start": round(mapuj(float(m.get("start", 0))), 3)} for m in audio]
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
            lines.extend([f"file '{path}'", f"duration {dur:.3f}"])
    for a, b, png in events:
        if b <= t:
            continue                       # nakładające się napisy karaoke: wygrywa wcześniejszy
        a = max(a, t)
        add(blank, a - t)
        add(png, b - a)
        t = b
    add(blank, max(0.0, p["duration"] - t))
    lines.append(f"file '{blank}'")        # demuxer concat potrzebuje ostatniego pliku jeszcze raz
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
    """Warstwa sylwetek pod eksport (lista concat jak typo_concat): klatki bloków „za osobą”, które mają sylwetkę;
    reszta przezroczysta. Brak bloków za osobą albo nieaktualna maska = None (napis zostaje w całości widoczny)."""
    tyl = [b for b in (p.get("typo") or {}).get("bloki", []) if b.get("warstwa") == "tyl"]
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
                  maska: Path | None = None) -> list[str]:
    """Argumenty ffmpeg dla znormalizowanego projektu. `has_audio[src] -> bool` z ffprobe.
    `typo` = {"tyl": lista concat, "przod": lista concat}: warstwy typografii (z typo_concat) pod tekstami.
    `maska` = lista concat sylwetek (maska_concat): osoba z filmu wraca nad warstwę „tyl”, więc napis jest za nią."""
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
        graph.append(f"[{vi}:v]setpts=(PTS-STARTPTS)/{_f(sp)},fps={F},{fit},setsar=1,format=yuv420p,"
                     + (f"tpad=start_mode=clone:start_duration={_f(brak)}," if brak > 1e-4 else "")
                     + f"tpad=stop_mode=clone:stop_duration={_f(post + 1)},trim=duration={_f(L)},setpts=PTS-STARTPTS"
                     + (rozmycie_przejscia(i, L, F, smax, glowa, ogon) if glowa or ogon else "")
                     + (f",fps={F}" if jest_tr else "") + f"[v{i}]")    # xfade chce stałej liczby klatek
        if c["kind"] == "video" and not c["muted"] and has_audio.get(str(c["src"])) and c["volume"] > 0:
            chain = ",".join(x for x in ("asetpts=PTS-STARTPTS", _atempo(sp),
                                         f"volume={_f(c['volume'])}" if c["volume"] != 1 else "") if x)
            graph.append(f"[{vi}:a]{chain},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                         + (f"adelay={round(brak * 1000)}:all=1," if brak > 1e-4 else "")
                         + f"apad,atrim=duration={_f(L)},asetpts=PTS-STARTPTS"
                         + (f",{zan}" if (zan := afade(c.get("fade_in", 0), c.get("fade_out", 0), pre, L - pre - post)) else "")
                         + f"[a{i}]")
        else:
            graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={_f(L)},aformat=sample_fmts=fltp[a{i}]")
        seg_labels.append(f"[v{i}][a{i}]")
    if not jest_tr:
        graph.append(f"{''.join(seg_labels)}concat=n={len(p['clips'])}:v=1:a=1[vc][ac]")
    else:
        graph += xfade_graph(tr, dlug, F)

    vlast, osoba = "vc", None
    if maska and (typo or {}).get("tyl"):
        graph.append("[vc]split[vcm][vco]")  # kopia klatki: z niej wycinamy osobę według sylwetki
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
            graph.append(f"[{mi}:v]scale={W}:{H}:flags=bicubic,format=rgba,alphaextract,fps={F}[mka]")
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
            args += ["-ss", _f(m["in"]), "-t", _f(m["out"] - m["in"]), "-i", str(m["src"])]
            mi = n; n += 1
            ms = int(round(m["start"] * 1000))
            zan = afade(m.get("fade_in", 0), m.get("fade_out", 0), 0, m["out"] - m["in"])
            graph.append(f"[{mi}:a]asetpts=PTS-STARTPTS,volume={_f(m['volume'])},aresample=48000,"
                         f"aformat=sample_fmts=fltp:channel_layouts=stereo,{zan + ',' if zan else ''}adelay={ms}|{ms}[m{k}]")
            mix.append(f"[m{k}]")
        graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,"
                     f"alimiter=limit=0.97[amx]")
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


def probe(path: Path, ffprobe: str = "ffprobe") -> dict:
    """Czas, wymiary (tak jak film się wyświetla, po obrocie) i obecność dźwięku (ffprobe). Obraz: wymiary, bez czasu."""
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                            "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate"
                            ":stream_side_data=rotation:stream_tags=rotate",
                            "-of", "json", str(path)], capture_output=True, text=True, timeout=20)
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
    return {"ok": True, "duration": float(dur) if dur not in (None, "N/A") else None, "w": w, "h": h, "fps": fps,
            "audio": bool(a), "acodec": a.get("codec_name"),
            "video": bool(v) and media_kind(path) != "audio", "vcodec": v.get("codec_name")}


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
    return {"ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"), "stt": stt_bin()}


# ----------------------------------------------------------------------------- audio: biblioteka, wyodrębnienie, lektor
# Biblioteka dźwięków CC0 (scripts/dzwieki.py): hq/web/dzwieki w repo, dzwieki/ obok wtyczki, scripts/dzwieki
# u Wideografa. Dodanie kopiuje plik obok filmu, więc projekt nie zależy od biblioteki (jak przy wgranym pliku).
DZWIEKI_DIR = "dzwieki"      # podkatalog katalogu filmu: efekty z biblioteki i dźwięk wyodrębniony z filmów
LEKTOR_DIR = "lektor"        # podkatalog katalogu filmu: lektor (Edge TTS) i nagrania z mikrofonu
GLOSY = ("pl-PL-MarekNeural", "pl-PL-ZofiaNeural", "en-US-AndrewMultilingualNeural", "en-US-AvaMultilingualNeural",
         "de-DE-SeraphinaMultilingualNeural")
LEKTOR_MAX = 3000            # znaków tekstu lektora z edytora


def dzwieki_katalog(root: Path | None) -> dict:
    """katalog.json biblioteki (kategorie i dźwięki); brak katalogu = pusta biblioteka."""
    try:
        kat = json.loads((Path(root) / "katalog.json").read_text(encoding="utf-8")) if root else {}
    except (OSError, ValueError):
        kat = {}
    return {"kategorie": kat.get("kategorie") or [], "dzwieki": kat.get("dzwieki") or []}


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


def proxy_key(src: Path) -> str:
    import hashlib
    st = src.stat()
    return hashlib.sha1(f"{src}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:20]


def proxy_command(src: Path, out: Path, ffmpeg: str = "ffmpeg") -> list[str]:
    """Kopia do podglądu, którą odtworzy każda przeglądarka: WebM VP9 do 540 p, klatka kluczowa co 0,5 s
    (szybkie przewijanie), szybkie kodowanie. Eksport i tak bierze oryginał."""
    return [ffmpeg, "-nostdin", "-hide_banner", "-y", "-loglevel", "error", "-i", str(src),
            "-vf", "scale=-2:'min(540,ih)':flags=bilinear,format=yuv420p", "-c:v", "libvpx-vp9", "-deadline", "realtime",
            "-cpu-used", "8", "-row-mt", "1", "-b:v", "1200k", "-g", "15", "-c:a", "libopus", "-b:a", "96k", "-ac", "2",
            "-f", "webm", str(out)]
