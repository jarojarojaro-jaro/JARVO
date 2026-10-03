#!/usr/bin/env python3
"""Projekt montażu z edytora HQ: Wideograf pracuje na tym samym projekcie co użytkownik.

Projekt to `<film>.edycja.json` obok filmu (zapisuje go edytor HQ). Zmieniasz go tymi poleceniami
(albo ostrożnie edytując JSON), a `render` składa film tym samym silnikiem co przycisk „Eksportuj”
w edytorze. Użytkownik po otwarciu edytora widzi Twoje zmiany osobno i może je dalej poprawiać.

    projekt.py pokaz <film>                        # co jest na osi (klipy, napisy, audio, długość)
    projekt.py dodaj-audio <film> <plik> [--start S] [--od S] [--do S] [--glosnosc 0.8] [--wycisz-film] [--narastanie 1] [--wyciszanie 2]
    projekt.py dzwiek <film> <id> [--glosnosc 0.3] [--narastanie S] [--wyciszanie S] [--wycisz|--wlacz]   # klip albo audio
    projekt.py dodaj-tekst <film> "tekst" --start S --koniec S [--styl shadow|box|outline|plain] [--kroj Poppins]
                                           [--y 0.78] [--rozmiar 72] [--kolor #FFFFFF] [--tlo #000000]
    projekt.py dodaj-klip <film> <plik> [--od S] [--do S] [--tempo 1] [--pozycja N] [--rozmyte|--dopasuj|--wypelnij --fx X --fy Y --zoom Z]
    projekt.py kadr <film> <id> [--rozmyte|--dopasuj|--wypelnij] [--fx 0.4] [--fy 0.35] [--zoom 1.15]   # kadr klipu
    projekt.py napisy <film> [--srt plik.srt] [--karaoke [#FFE14D]] [--kroj Kanit]   # napisy ze słów (<źródło>.mowa.json) albo SRT
    projekt.py przejscie <film> <id>|--wszystkie [--typ fade] [--dlugosc 0.5] [--usun]   # przejście na cięciu po klipie
    projekt.py tnij <film> <id> (--w S | --czesci 3)   # podziel klip w chwili osi albo na równe części
    projekt.py wytnij <film> --od S --do S          # wytnij kawałek osi (przez klipy); reszta się dosuwa
    projekt.py usun <film> <id>                    # usuń klip / tekst / audio o danym id (z `pokaz`)
    projekt.py uwaga <film> <id> (--zrobione "co zmieniłem" | --odrzuc "dlaczego")   # zamknij uwagę z osi edytora
    projekt.py sprawdz <film>                      # walidacja jak przy eksporcie
    projekt.py render <film> [--out plik.mp4]      # nowa wersja obok oryginału, na końcu linia MEDIA:
    (typografia słowo po słowie, klucz `typo`: plan i poprawki robi typografia.py; render rysuje ją tak jak edytor)

Czas S w sekundach osi (po cięciach i zmianach tempa), chyba że opis mówi „źródła” (--od/--do).
Przejście leży na środku cięcia i nie skraca filmu (napisy i audio zostają na miejscu); długość to parzysta liczba
klatek, najwyżej tyle, ile trwa krótszy z dwóch klipów (`pokaz` pokazuje, co wyszło).
Nic nie nadpisuje oryginału: render zapisuje film-edycja.mp4, film-edycja-2.mp4…

Uwagi (`notes` w projekcie) zostawia właściciel w edytorze HQ: prośba przypięta do chwili osi, często z kadrem
(obraz w inboxie, oglądasz go przez vision_analyze). Każdą zamykasz `uwaga … --zrobione` albo `--odrzuc` z powodem;
edytor pokazuje je wtedy jako ✓ z Twoim opisem. `render` ostrzega, gdy zostały otwarte.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# silnik edytora: w dystrybucji kopiowany obok (build.py), w repo leży w hq/plugin
_REPO = HERE.parents[2] if len(HERE.parents) > 2 else HERE
for cand in (HERE, _REPO / "hq" / "plugin"):
    if (cand / "edytor.py").exists():
        sys.path.insert(0, str(cand))
        break
import edytor as ed  # noqa: E402

NAPISY_JS = next((p for p in (HERE / "edytor_napisy.js", _REPO / "hq" / "web" / "src" / "44-napisy.js") if p.exists()), None)
TYPO_JS = next((p for p in (HERE / "edytor_typografia.js", _REPO / "hq" / "web" / "src" / "48-typografia.js") if p.exists()), None)
KROJE = next((p for p in (HERE / "kroje", _REPO / "hq" / "web" / "fonts" / "kroje") if (p / "kroje.css").exists()), None)
TEXT_DEFAULT = {"x": 0.5, "y": 0.78, "size": 72, "color": "#FFFFFF", "bg": "#000000", "style": "shadow",
                "font": "system-ui, 'Segoe UI', Roboto, sans-serif", "bold": True, "align": "center", "maxw": 0.86}
CAP_DEFAULT = {**TEXT_DEFAULT, "y": 0.84, "size": 58, "style": "outline", "maxw": 0.84,
               "font": "'Bricolage Grotesque', system-ui, sans-serif"}
# tekst i napisy w kadrze pionowym: nad opisem TikToka i Shorts, węższe niż kolumna przycisków (ED_PION w edytorze HQ)
PION = {"y": 0.68, "maxw": 0.74}
FPS = (24, 25, 30, 50, 60)
KARAOKE_HL = "#FFE14D"   # kolor aktywnego słowa (jak ED_HL w edytorze)


def pion(proj: dict) -> dict:
    """Położenie i szerokość domyślna w kadrze pionowym (poza strefami platform); w poziomym zostaje z TEXT_DEFAULT / CAP_DEFAULT."""
    c = proj.get("canvas") or {}
    return dict(PION) if (c.get("h") or 0) > (c.get("w") or 0) else {}


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def even(n: float) -> int:
    n = int(round(n))
    return max(2, n - n % 2)


# ---------------------------------------------------------------- projekt: odczyt, zapis, oś czasu

def load(film: Path) -> dict:
    """Projekt z pliku albo nowy z samego filmu (jak przy pierwszym otwarciu edytora)."""
    pp = ed.project_path(film)
    if pp.is_file():
        proj = json.loads(pp.read_text(encoding="utf-8"))
        if proj.get("clips"):
            return proj
    info = ed.probe(film)
    if not info.get("ok"):
        raise SystemExit(f"nie mogę odczytać filmu: {film}")
    fps = info.get("fps") or 30
    w, h = ed.kadr_eksportu(even(info.get("w") or 1920), even(info.get("h") or 1080))   # 4K → 1080p, jak w edytorze
    return {"version": 1, "format": "orig",
            "canvas": {"w": w, "h": h, "fps": min(FPS, key=lambda f: abs(f - fps))},
            "clips": [{"id": new_id("c"), "src": str(film), "kind": "video", "in": 0, "out": info.get("duration") or 5,
                       "speed": 1, "volume": 1, "muted": False, "fit": "contain"}],
            "texts": [], "audio": []}


def save(film: Path, proj: dict) -> Path:
    """Zapis atomowy; `rev` i `zmienil` mówią edytorowi, że projekt zmienił agent (wczyta zmiany sam)."""
    proj["rev"] = int(proj.get("rev") or 0) + 1
    proj["zmienil"] = {"kto": "jarvo-wideo", "kiedy": time.time()}
    pp = ed.project_path(film)
    tmp = pp.with_name(f".{pp.name}.part")
    tmp.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pp)
    return pp


def layout(clips: list[dict]) -> list[tuple[dict, float, float]]:
    return ed.layout_clips(clips)                  # ta sama oś co edytor HQ


def total(proj: dict) -> float:
    lay = layout(proj["clips"])
    return lay[-1][2] if lay else 0.0


def resolve(raw: str) -> Path | None:
    p = Path(raw)
    return p.resolve() if p.is_file() else None


# ---------------------------------------------------------------- polecenia

def cmd_pokaz(film: Path, a) -> int:
    proj = load(film)
    exists = ed.project_path(film).is_file()
    print(f"Projekt: {ed.project_path(film) if exists else '(jeszcze nie ma: sam film)'}")
    cv = proj["canvas"]
    print(f"Kadr {cv['w']}×{cv['h']} @ {cv['fps']} fps · długość {total(proj):.2f} s")
    print("Klipy (ścieżka główna, jeden za drugim):")
    trs = ed.przejscia_osi(proj["clips"], cv["fps"])
    for (c, s, e), tr in zip(layout(proj["clips"]), trs):
        extra = "".join([f" · tempo {c.get('speed', 1)}×" if c.get("speed", 1) != 1 else "", " · wyciszony" if c.get("muted") else "",
                         f" · głośność {c.get('volume', 1):.2f}" if c.get("volume", 1) != 1 else ""])
        print(f"  [{c.get('id')}] {s:6.2f}–{e:6.2f}  {Path(c['src']).name} (źródło {c['in']:.2f}–{c['out']:.2f}){extra}{opis_zaniku(c)}")
        if tr:
            print(f"      ↳ przejście {tr['type']} {tr['d']:.2f} s ({e - tr['d'] / 2:.2f}–{e + tr['d'] / 2:.2f})")
        elif c.get("transition") and c is not proj["clips"][-1]:
            print(f"      ↳ przejście {c['transition'].get('type')}: klipy za krótkie, zostaje zwykłe cięcie")
    print("Napisy i teksty:" if proj.get("texts") else "Napisy i teksty: brak")
    for x in proj.get("texts") or []:
        print(f"  [{x.get('id')}] {x['start']:6.2f}–{x['end']:6.2f}  {'napis' if x.get('cap') else 'tekst'}: {x.get('text', '')!r}")
    typo = ed.normalize_typo(proj.get("typo"), total(proj))
    if typo["bloki"]:
        print(f"Typografia: {len(typo['bloki'])} bloków, motyw {typo['motyw']} (szczegóły: typografia.py pokaz)")
    print("Audio:" if proj.get("audio") else "Audio: brak")
    for m in proj.get("audio") or []:
        print(f"  [{m.get('id')}] od {m['start']:6.2f} przez {m['out'] - m['in']:.2f} s  {Path(m['src']).name} · głośność {m.get('volume', 1):.2f}{opis_zaniku(m)}")
    notes = sorted((n for n in proj.get("notes") or [] if isinstance(n, dict)), key=lambda n: float(n.get("t") or 0))
    if notes:
        otwarte = sum(1 for n in notes if not n.get("done"))
        print(f"Uwagi właściciela ({otwarte} otwartych z {len(notes)}; czas osi):")
        for n in notes:
            stan = f"✓ {n.get('odp') or 'zrobione'}" if n.get("done") else "OTWARTA"
            kadr = f" · kadr {n['img']}" if n.get("img") else ""
            print(f"  [{n.get('id')}] {float(n.get('t') or 0):6.2f}  {(n.get('text') or '(kadr)')!r}{kadr} · {stan}")
    if a.json:
        print(json.dumps(proj, ensure_ascii=False, indent=1))
    return 0


def cmd_uwaga(film: Path, a) -> int:
    proj = load(film)
    note = next((n for n in proj.get("notes") or [] if isinstance(n, dict) and n.get("id") == a.id), None)
    if note is None:
        raise SystemExit(f"nie ma uwagi o id {a.id} (lista: projekt.py pokaz)")
    odp = " ".join((a.zrobione or a.odrzuc or "").split())
    if len(odp) < 8:
        raise SystemExit("opisz konkretnie, co zmieniłeś albo dlaczego nie (co najmniej 8 znaków)")
    note.update(done=True, odp=("" if a.zrobione else "odrzucona: ") + odp, kto="jarvo-wideo", kiedy=time.time())
    save(film, proj)
    left = sum(1 for n in proj["notes"] if isinstance(n, dict) and not n.get("done"))
    print(f"Uwaga {a.id} zamknięta. Otwarte: {left}.")
    return 0


def cmd_dodaj_audio(film: Path, a) -> int:
    proj = load(film)
    src = resolve(a.plik)
    if not src or ed.media_kind(src) not in ("audio", "video"):
        raise SystemExit(f"to nie plik audio: {a.plik}")
    dur = ed.probe(src).get("duration") or 0
    od, do = a.od or 0.0, a.do if a.do is not None else dur
    if do - od <= 0.05:
        raise SystemExit("pusty fragment audio (sprawdź --od/--do)")
    item = {"id": new_id("a"), "src": str(src), "start": max(0.0, a.start), "in": od, "out": do,
            "volume": max(0.0, min(2.0, a.glosnosc)), **zanik_z_arg(a, do - od)}
    proj.setdefault("audio", []).append(item)
    if a.wycisz_film:
        for c in proj["clips"]:
            c["muted"] = True
    save(film, proj)
    print(f"Dodano audio [{item['id']}] {src.name} od {item['start']:.2f} s ({do - od:.2f} s)")
    return 0


def zanik_z_arg(a, d: float, old: dict | None = None) -> dict:
    """--narastanie / --wyciszanie (s) → fadeIn / fadeOut, do połowy elementu i najwyżej 10 s (edytor.zanik)."""
    out = {}
    for arg, key in (("narastanie", "fadeIn"), ("wyciszanie", "fadeOut")):
        v = getattr(a, arg, None)
        v = (old or {}).get(key) if v is None else v
        if v:
            out[key] = round(max(0.0, min(float(v), ed.ZANIK_MAX, d / 2)), 2)
    return out


def opis_zaniku(x: dict) -> str:
    return "".join([f" · narastanie {x['fadeIn']:.1f} s" if x.get("fadeIn") else "", f" · wyciszanie {x['fadeOut']:.1f} s" if x.get("fadeOut") else ""])


def cmd_dzwiek(film: Path, a) -> int:
    """Głośność, wyciszenie i zanik klipu (jego dźwięk) albo elementu audio, jak suwaki w edytorze HQ."""
    proj = load(film)
    lay = {c.get("id"): e - s for c, s, e in layout(proj["clips"])}
    x = next((c for c in proj["clips"] if c.get("id") == a.id), None)
    d = lay.get(a.id, 0.0)
    if x is None:
        x = next((m for m in proj.get("audio") or [] if m.get("id") == a.id), None)
        if x is None:
            raise SystemExit(f"nie ma klipu ani audio o id {a.id} (lista: projekt.py pokaz)")
        d = max(0.0, min(x["out"] - x["in"], total(proj) - x.get("start", 0)))   # muzyka ucięta na końcu filmu
    if a.glosnosc is not None:
        x["volume"] = round(max(0.0, min(2.0, a.glosnosc)), 3)
    if a.wycisz or a.wlacz:
        if "muted" not in x and x not in proj["clips"]:
            raise SystemExit("--wycisz/--wlacz dotyczy klipu; audio wyciszasz --glosnosc 0")
        x["muted"] = bool(a.wycisz)
    for arg, key in (("narastanie", "fadeIn"), ("wyciszanie", "fadeOut")):
        if getattr(a, arg) == 0:                   # 0 = bez zaniku
            x.pop(key, None)
    x.update(zanik_z_arg(a, d, x))
    save(film, proj)
    print(f"[{a.id}] głośność {x.get('volume', 1):.2f}{' · wyciszony' if x.get('muted') else ''}{opis_zaniku(x)}")
    return 0


def kroje_napisow() -> list[tuple[str, str, str]]:
    """Kroje zwykłych napisów z listy edytora (ED_FONTS w 44-napisy.js): (rodzina CSS, nazwa, grupa)."""
    js = NAPISY_JS.read_text(encoding="utf-8") if NAPISY_JS else ""
    lista = js[js.find("const ED_FONTS"):js.find("];", js.find("const ED_FONTS"))]
    return re.findall(r'\[\s*"([^"]+)", "([^"]+)", "(\w+)", \d+, \d+\]', lista)


def kroj_z_nazwy(nazwa: str | None) -> str | None:
    """--kroj: nazwa z edytora („Bąbelki”) albo rodzina („Rubik Bubbles”), bez wielkości liter → rodzina CSS z listy
    (ta sama co w edytorze, więc grubość i podgląd się zgadzają)."""
    if nazwa is None:
        return None
    lista = kroje_napisow()
    n = nazwa.strip().strip("'\"").casefold()
    for css, nazwa_ed, _g in lista:
        if n in (nazwa_ed.casefold(), css.split(",")[0].strip("'\" ").casefold()):
            return css
    raise SystemExit(f"nie ma kroju „{nazwa}”; są: {', '.join(n for _c, n, _g in lista)}")


def cmd_dodaj_tekst(film: Path, a) -> int:
    proj = load(film)
    t = total(proj)
    if not (0 <= a.start < a.koniec) or a.start >= t:
        raise SystemExit(f"zły czas napisu (film ma {t:.2f} s)")
    base = CAP_DEFAULT if a.napis else TEXT_DEFAULT
    x = {**base, **pion(proj), "id": new_id("t"), "text": a.tekst, "start": a.start, "end": min(a.koniec, t)}
    for k, v in (("style", a.styl), ("y", a.y), ("size", a.rozmiar), ("color", a.kolor), ("bg", a.tlo), ("font", kroj_z_nazwy(a.kroj))):
        if v is not None:
            x[k] = v
    if a.napis:
        x["cap"] = True
    proj.setdefault("texts", []).append(x)
    save(film, proj)
    print(f"Dodano {'napis' if a.napis else 'tekst'} [{x['id']}] {x['start']:.2f}–{x['end']:.2f} s: {a.tekst!r}")
    return 0


def cmd_dodaj_klip(film: Path, a) -> int:
    proj = load(film)
    src = resolve(a.plik)
    kind = ed.media_kind(src) if src else None
    if kind not in ("video", "image"):
        raise SystemExit(f"to nie film ani obraz: {a.plik}")
    info = ed.probe(src)
    dur = 3.0 if kind == "image" else (info.get("duration") or 3.0)
    od = a.od or 0.0
    do = a.do if a.do is not None else (od + dur if kind == "image" else dur)
    c = {"id": new_id("c"), "src": str(src), "kind": kind, "in": od, "out": do, "speed": 1 if kind == "image" else a.tempo,
         "volume": 1, "muted": False, "fit": fit_z_arg(a, "blur" if inny_kadr(info, proj["canvas"]) else "contain")}
    c.update(kadr_z_arg(a))
    pos = len(proj["clips"]) if a.pozycja is None else max(0, min(len(proj["clips"]), a.pozycja))
    clips = list(proj["clips"])
    clips.insert(pos, c)
    save(film, ed.remap_times(proj, {**proj, "clips": clips}))   # wstawiony w środek: reszta osi odsuwa się
    print(f"Dodano klip [{c['id']}] {src.name} na pozycji {pos} ({(do - od) / c['speed']:.2f} s)")
    return 0


def inny_kadr(info: dict, canvas: dict) -> bool:
    """Proporcje pliku inne niż kadr projektu (jak innyKadr w edytorze); nieznane wymiary = pasuje."""
    w, h = info.get("w"), info.get("h")
    k = canvas["w"] / canvas["h"]
    return bool(w and h) and abs(w / h - k) > 0.02 * k


def fit_z_arg(a, domyslny: str) -> str:
    """--wypelnij / --rozmyte / --dopasuj → fit klipu; bez flagi `domyslny` (inne proporcje: rozmyte tło, jak w edytorze)."""
    return "cover" if a.wypelnij else "blur" if a.rozmyte else "contain" if a.dopasuj else domyslny


def kadr_z_arg(a) -> dict:
    """--fx/--fy/--zoom → pola klipu (kadr działa przy „Wypełnij”, czyli fit=cover; edytor.py pilnuje zakresów)."""
    out = {}
    for k in ("fx", "fy", "zoom"):
        v = getattr(a, k, None)
        if v is not None:
            lo, hi = (1.0, 3.0) if k == "zoom" else (0.0, 1.0)
            out[k] = min(hi, max(lo, v))
    return out


def cmd_kadr(film: Path, a) -> int:
    proj = load(film)
    c = next((x for x in proj["clips"] if x.get("id") == a.id), None)
    if c is None:
        raise SystemExit(f"nie ma klipu o id {a.id} (lista: projekt.py pokaz)")
    c["fit"] = fit_z_arg(a, c.get("fit") or "contain")
    c.update(kadr_z_arg(a))
    if c.get("fit") != "cover" and kadr_z_arg(a):
        print("uwaga: fx/fy/zoom działają przy --wypelnij (fit=cover)")
    save(film, proj)
    print(f"Kadr [{c['id']}]: {c.get('fit')} fx={c.get('fx', 0.5)} fy={c.get('fy', 0.5)} zoom={c.get('zoom', 1)}")
    return 0


def timeline_words(proj: dict) -> list[list]:
    """Słowa z analiz mowy (<źródło>.mowa.json) w czasie osi, jak w edytorze (słowo = klip z jego środkiem)."""
    out, cache = [], {}
    for c, s, _e in layout(proj["clips"]):
        src = Path(c["src"])
        if src not in cache:
            p = ed.speech_path(src)
            cache[src] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        d = cache[src]
        if not d:
            continue
        sp = c.get("speed") or 1
        for w0, w1, w in d.get("words") or []:
            if not (c["in"] <= (w0 + w1) / 2 < c["out"]):
                continue
            out.append([s + (max(w0, c["in"]) - c["in"]) / sp, s + (min(w1, c["out"]) - c["in"]) / sp, w])
    return out


def cmd_napisy(film: Path, a) -> int:
    proj = load(film)
    if a.srt:
        lines = ed.parse_srt(Path(a.srt).read_text(encoding="utf-8", errors="replace"))
    else:
        words = timeline_words(proj)
        if not words:
            raise SystemExit("brak analizy mowy: w edytorze „Mowa → Wykryj mowę”, albo podaj --srt")
        lines = ed.lines_from_words(words)
    t = total(proj)
    old = next((x for x in proj.get("texts") or [] if x.get("cap")), None)
    look = {k: old[k] for k in ("x", "y", "size", "color", "bg", "style", "font", "bold", "maxw", "hl") if old and k in old}
    if a.karaoke is not None:
        look["hl"] = a.karaoke or KARAOKE_HL
    if a.kroj is not None:
        look["font"] = kroj_z_nazwy(a.kroj)
    proj["texts"] = [x for x in proj.get("texts") or [] if not x.get("cap")] + [
        {**CAP_DEFAULT, **pion(proj), **look, "id": new_id("t"), "cap": True, "start": k["start"], "end": min(k["end"], t), "text": k["text"],
         **({"words": k["words"]} if k.get("words") else {})}
        for k in lines if k["start"] < t]
    save(film, proj)
    print(f"Napisy: {sum(1 for x in proj['texts'] if x.get('cap'))} linii")
    return 0


def cmd_przejscie(film: Path, a) -> int:
    proj = load(film)
    clips = proj["clips"]
    if a.wszystkie:
        cele = clips[:-1]
    else:
        if not a.id:
            raise SystemExit("podaj id klipu przed cięciem (z `pokaz`) albo --wszystkie")
        c = next((x for x in clips if x.get("id") == a.id), None)
        if c is None:
            raise SystemExit(f"nie ma klipu o id {a.id} (lista: projekt.py pokaz)")
        if c is clips[-1]:
            raise SystemExit("za ostatnim klipem nie ma cięcia: przejście ustawiasz na klipie przed cięciem")
        cele = [c]
    if not cele:
        raise SystemExit("jeden klip: nie ma cięcia na przejście")
    for c in cele:
        if a.usun:
            c.pop("transition", None)
            continue
        old = c.get("transition") or {}
        c["transition"] = {"type": a.typ or old.get("type") or "fade",
                           "dur": round(min(3.0, max(0.1, a.dlugosc if a.dlugosc is not None else old.get("dur") or ed.PRZEJSCIE_D)), 3)}
    save(film, proj)
    trs = ed.przejscia_osi(clips, proj["canvas"]["fps"])
    for c, (_c, _s, e) in zip(clips, layout(clips)):
        if c not in cele:
            continue
        tr = trs[clips.index(c)]
        stan = (f"{tr['type']} {tr['d']:.2f} s" if tr else "zwykłe cięcie" if a.usun or not c.get("transition")
                else "klipy za krótkie, zostaje zwykłe cięcie")
        print(f"Cięcie po [{c.get('id')}] ({e:.2f} s): {stan}")
    return 0


MIN_CZESC = 0.1      # najkrótszy kawałek po cięciu (ED_MIN w edytorze HQ)


def cmd_tnij(film: Path, a) -> int:
    """Podział klipu jak „Tnij” w edytorze: oś się nie zmienia, przejście zostaje na ostatniej części."""
    proj = load(film)
    lay = layout(proj["clips"])
    k = next((i for i, (c, _s, _e) in enumerate(lay) if c.get("id") == a.id), None)
    if k is None:
        raise SystemExit(f"nie ma klipu o id {a.id} (lista: projekt.py pokaz)")
    c, s, e = lay[k]
    if a.czesci:
        if a.czesci < 2 or (e - s) / a.czesci < MIN_CZESC:
            raise SystemExit(f"klip ma {e - s:.2f} s: części muszą mieć co najmniej {MIN_CZESC} s")
        punkty = [s + (e - s) * j / a.czesci for j in range(1, a.czesci)]
    else:
        if a.w is None or not (s + MIN_CZESC <= a.w <= e - MIN_CZESC):
            raise SystemExit(f"--w musi leżeć w klipie z zapasem {MIN_CZESC} s ({s:.2f}–{e:.2f} s osi)")
        punkty = [a.w]
    sp = float(c.get("speed") or 1)
    granice = [c["in"], *(round(c["in"] + (t - s) * sp, 4) for t in punkty), c["out"]]
    czesci = [{**c, "id": c["id"] if j == 0 else new_id("c"), "in": granice[j], "out": granice[j + 1]} for j in range(len(granice) - 1)]
    for x in czesci[:-1]:
        x.pop("transition", None)
    proj["clips"] = proj["clips"][:k] + czesci + proj["clips"][k + 1:]
    save(film, proj)
    for x, xs, xe in layout(czesci):
        print(f"  [{x['id']}] {s + xs:6.2f}–{s + xe:6.2f}  (źródło {x['in']:.2f}–{x['out']:.2f})")
    return 0


def wytnij_zakres(proj: dict, od: float, do: float) -> dict:
    """Projekt bez odcinka osi od–do (przez wszystkie klipy), jak wycinanie pauz w edytorze HQ (cutTimeline): kawałek
    klipu krótszy niż 0,04 s znika, przejście zostaje na ostatnim kawałku, napisy, typografia, uwagi i audio dosuwają się
    (edytor.remap_times)."""
    clips = []
    for c, s, e in layout(proj["clips"]):
        kaw = [(s, e)] if do <= s or od >= e else [(s, min(od, e)), (max(do, s), e)]
        kaw = [(x, y) for x, y in kaw if y - x >= 0.04]
        sp = float(c.get("speed") or 1)
        for j, (x, y) in enumerate(kaw):
            n = {**c, "id": c.get("id") if j == 0 else new_id("c"),
                 "in": round(c["in"] + (x - s) * sp, 4) if x > s else c["in"], "out": round(c["in"] + (y - s) * sp, 4) if y < e else c["out"]}
            if j < len(kaw) - 1:
                n.pop("transition", None)
            clips.append(n)
    if not clips:
        raise SystemExit("po wycięciu nie zostałby żaden klip")
    return ed.remap_times(proj, {**proj, "clips": clips})


def cmd_wytnij(film: Path, a) -> int:
    proj = load(film)
    t0 = total(proj)
    od, do = max(0.0, a.od), min(t0, a.do)
    if do - od < 0.02:
        raise SystemExit(f"pusty zakres: film ma {t0:.2f} s, --od musi być mniejsze niż --do")
    nowy = wytnij_zakres(proj, od, do)
    save(film, nowy)
    print(f"Wycięto {od:.2f}–{do:.2f} s osi; film ma teraz {total(nowy):.2f} s (było {t0:.2f} s). Napisy i audio dosunięte.")
    return 0


def cmd_usun(film: Path, a) -> int:
    proj = load(film)
    for key in ("clips", "texts", "audio"):
        items = proj.get(key) or []
        if any(x.get("id") == a.id for x in items):
            if key == "clips" and len(items) == 1:
                raise SystemExit("to jedyny klip: projekt musi mieć choć jeden")
            nowy = {**proj, key: [x for x in items if x.get("id") != a.id]}
            if key == "clips":                     # oś magnetyczna: napisy, uwagi i audio za klipem dosuwają się
                nowy = ed.remap_times(proj, nowy)
            save(film, nowy)
            print(f"Usunięto {a.id}")
            return 0
    raise SystemExit(f"nie ma elementu {a.id} (sprawdź `pokaz`)")


def cmd_sprawdz(film: Path, a) -> int:
    proj = load(film)
    try:
        p = ed.normalize(proj, resolve)
    except ed.ProjectError as exc:
        print(f"BŁĄD: {exc}")
        return 1
    print(f"OK: {len(p['clips'])} klipów, {len(p['texts'])} tekstów, {len(p['audio'])} ścieżek audio, {p['duration']:.2f} s, "
          f"{p['canvas']['w']}×{p['canvas']['h']} @ {p['canvas']['fps']} fps")
    return 0


# ---------------------------------------------------------------- render (ten sam silnik co „Eksportuj”)

def ensure_playwright() -> None:
    import narzedzia as nz
    nz.wymagaj_playwright(__file__, "JARVO_PROJEKT_REEXEC", "napisy renderuje przeglądarka")


# rodziny krojów, których użyją napisy i typografia projektów (ta sama funkcja wyboru kroju co przy rysowaniu)
RODZINY_JS = """(plany) => {
    const out = new Set(), rodzina = (f) => (f.match(/px (.*)$/) || [0, f])[1].split(",")[0].trim().replace(/^['"]|['"]$/g, "");
    for (const P of plany) {
        for (const t of P.texts || []) out.add(rodzina(textFont(t, 1920, 1080).font));
        if (P.typo && typeof typoFonty === "function") for (const [f] of typoFonty(P, 1080, 1920)) out.add(rodzina(f));
    }
    return [...out];
}"""


@contextlib.contextmanager
def strona(plany: list[dict] | None = None):
    """Przeglądarka bez okna z krojami edytora (lokalnie) i jego rendererami: napisy (44-napisy.js) i typografia
    (48-typografia.js). Jedno uruchomienie na cały render. `plany` = projekty ({texts, typo}) do narysowania:
    strona dostaje tylko ich kroje (bez listy wszystkie, kilka MB)."""
    if NAPISY_JS is None:
        raise SystemExit("brak edytor_napisy.js obok skryptu (przebuduj profil)")
    ensure_playwright()
    from playwright.sync_api import sync_playwright
    try:
        import narzedzia as nz
        exe = nz.headless_shell()
    except Exception:  # noqa: BLE001 - poza obrazem floty: domyślna przeglądarka playwright
        exe = None
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        page = browser.new_page()
        page.set_content("<!doctype html><meta charset=utf-8><body></body>")
        page.add_script_tag(content=NAPISY_JS.read_text(encoding="utf-8"))
        if TYPO_JS is not None:
            page.add_script_tag(content=TYPO_JS.read_text(encoding="utf-8"))
        rodziny = set(page.evaluate(RODZINY_JS, plany)) if plany is not None else None
        kroje = ed.kroje_css(KROJE, rodziny)   # te same pliki krojów co edytor HQ (lokalnie, bez sieci)
        if kroje:
            page.add_style_tag(content=kroje)
        try:
            yield page
        finally:
            browser.close()


def _png(data_url: str, dest: Path) -> Path:
    dest.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
    return dest


def text_pngs(texts: list[dict], W: int, H: int, out_dir: Path,
              hi: list[int] | None = None, page=None) -> list[Path]:
    """Każdy napis → PNG W×H, rysowany TĄ SAMĄ funkcją co w edytorze (44-napisy.js) w przeglądarce bez okna.
    `hi[k]` ≥ 0: napis karaoke z aktywnym słowem o tym numerze (jeden obraz na słowo)."""
    if not texts:
        return []
    if page is None:
        with strona([{"texts": texts}]) as pg:
            return text_pngs(texts, W, H, out_dir, hi, pg)
    hi = hi or [-1] * len(texts)
    paths = []
    for i, t in enumerate(texts):
        data = page.evaluate("""async ([t, W, H, hi]) => {
            await fontLoad(textFont(t, H, W).font, t.text);
            const c = document.createElement("canvas"); c.width = W; c.height = H;
            drawText(c.getContext("2d"), t, W, H, hi);
            return c.toDataURL("image/png");
        }""", [t, W, H, hi[i]])
        paths.append(_png(data, out_dir / f"napis-{i}{'' if hi[i] < 0 else f'-slowo-{hi[i]}'}.png"))
    return paths


TYPO_KLATKI_JS = """async ([P, W, H, fps, total, warstwa, partia]) => {
    for (const [f, txt] of typoFonty(P, W, H)) await fontLoad(f, txt);
    const segs = typoOdcinki(P, fps, total, warstwa);
    const c = document.createElement("canvas"); c.width = W; c.height = H;
    const g = c.getContext("2d");
    const out = [];
    for (const s of segs) {
        if (!s.podpis) { out.push([s.od, s.do, null]); continue; }
        g.clearRect(0, 0, W, H);
        typoRysuj(g, P, W, H, (s.od + 0.5) / fps, warstwa);
        out.push([s.od, s.do, partia ? c.toDataURL("image/png") : ""]);
    }
    return out;
}"""


def typo_warstwy(plan: dict, W: int, H: int, fps: int, total: float, out_dir: Path, page) -> dict[str, Path]:
    """Warstwy typografii (przód i „za osobą”) jako listy concat: przeglądarka rysuje klatkę tylko tam,
    gdzie obraz się zmienia (wejście słowa, wyjście bloku), resztę ffmpeg trzyma jako długie odcinki."""
    if not plan.get("bloki") or TYPO_JS is None:
        return {}
    blank = ed.blank_png(out_dir / "typo-pusty.png", W, H)
    out = {}
    for warstwa in ("tyl", "przod"):
        if not any((b.get("warstwa") == "tyl") == (warstwa == "tyl") for b in plan["bloki"]):
            continue
        segs = page.evaluate(TYPO_KLATKI_JS, [{"typo": plan}, W, H, fps, total, warstwa, True])
        lista = [((b - a) / fps, _png(png, out_dir / f"typo-{warstwa}-{a:06d}.png") if png else None) for a, b, png in segs]
        dest = ed.typo_concat(lista, blank, out_dir / f"typo-{warstwa}.ffconcat")
        if dest:
            out[warstwa] = dest
    return out


def kadr_osi(proj: dict, t: float, W: int, H: int, dest: Path) -> Path:
    """Klatka osi w chwili t w kadrze W×H (klip, czas źródła, dopasowanie jak przy eksporcie)."""
    lay = layout(proj["clips"])
    c, s, _e = next((x for x in lay if x[1] <= t < x[2]), lay[-1])
    u = float(c["in"]) + (t - s) * float(c.get("speed") or 1)
    fit = (ed.cover_filter(W, H, {"zoom": 1, "fx": 0.5, "fy": 0.5, **c}) if c.get("fit") == "cover"
           else ed.blur_filter(W, H, 0) if c.get("fit") == "blur"
           else f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black")
    src = ["-i", str(c["src"])] if c.get("kind") == "image" else ["-ss", f"{max(0.0, u):.3f}", "-i", str(c["src"])]
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *src, "-frames:v", "1",
                    "-filter_complex", f"[0:v]{fit}", str(dest)], check=True)
    return dest


ARKUSZ_JS = """async ([P, W, H, kadry, cols]) => {
    const plany = kadry.map((k) => (k[3] ? { typo: k[3] } : P));          // kafel może mieć własny plan (arkusz stylów)
    for (const Q of new Set(plany)) for (const [f, txt] of typoFonty(Q, W, H)) await fontLoad(f, txt);
    const cw = Math.min(W, 420), ch = Math.round(cw * H / W), rows = Math.ceil(kadry.length / cols);
    const sheet = document.createElement("canvas"); sheet.width = cw * cols; sheet.height = ch * rows;
    const sg = sheet.getContext("2d"); sg.fillStyle = "#111"; sg.fillRect(0, 0, sheet.width, sheet.height);
    const c = document.createElement("canvas"); c.width = W; c.height = H; const g = c.getContext("2d");
    const oc = document.createElement("canvas"); oc.width = W; oc.height = H; const o = oc.getContext("2d");
    for (let i = 0; i < kadry.length; i++) {
        const [src, t, maska, , podpis] = kadry[i], Q = plany[i];
        const img = new Image(); img.src = src; await img.decode();
        g.clearRect(0, 0, W, H); g.drawImage(img, 0, 0, W, H);
        typoRysuj(g, Q, W, H, t, "tyl");
        if (maska) {          // osoba nad warstwą „za osobą”: klatka przycięta sylwetką
            const m = new Image(); m.src = maska; await m.decode();
            o.globalCompositeOperation = "source-over"; o.clearRect(0, 0, W, H); o.drawImage(img, 0, 0, W, H);
            o.globalCompositeOperation = "destination-in"; o.drawImage(m, 0, 0, W, H);
            g.drawImage(oc, 0, 0);
        }
        typoRysuj(g, Q, W, H, t, "przod");
        const x = (i % cols) * cw, y = Math.floor(i / cols) * ch, napis = podpis || t.toFixed(2) + " s";
        sg.drawImage(c, x, y, cw, ch);
        sg.font = "600 14px system-ui, sans-serif";
        sg.fillStyle = "rgba(0,0,0,.7)"; sg.fillRect(x, y, sg.measureText(napis).width + 12, 22); sg.fillStyle = "#FFE14D";
        sg.fillText(napis, x + 6, y + 16);
    }
    return sheet.toDataURL("image/jpeg", 0.86);
}"""


def arkusz_typografii(proj: dict, plan: dict, chwile: list[float], out: Path, film: Path | None = None,
                      warianty: list[tuple[str, dict]] | None = None) -> Path:
    """Arkusz do oceny okiem: klatki filmu w podanych chwilach z typografią narysowaną tym samym rendererem
    (z sylwetką osoby nad napisem „za osobą”, gdy maska.py ją policzył). warianty = [(podpis, plan)]: jedna chwila
    (chwile[0]) w kilku wersjach planu, np. ten sam blok w każdym motywie (arkusz stylów)."""
    cv = proj["canvas"]
    k = min(1.0, 720 / max(cv["w"], cv["h"]))
    W, H = even(cv["w"] * k), even(cv["h"] * k)
    idx = ed.maska_indeks(film, proj) if film else None
    kafle = [(chwile[0], podpis, q) for podpis, q in warianty] if warianty else [(t, None, None) for t in chwile]
    plany = [{"typo": q} for q in ([plan] + [q for _p, q in warianty or []])]
    with tempfile.TemporaryDirectory(prefix="typo-arkusz-") as tmp, strona(plany) as page:
        kadry, obrazy = [], {}
        for t, podpis, q in kafle:
            if t not in obrazy:                     # ta sama chwila w kilku wariantach: jedna klatka filmu
                f = kadr_osi(proj, t, W, H, Path(tmp) / f"k{len(obrazy)}.png")
                m = ed.maska_dir(film) / f"k{int(t * float(cv['fps']) + 1e-6):06d}.png" if idx else None
                obrazy[t] = ("data:image/png;base64," + base64.b64encode(f.read_bytes()).decode(),
                             "data:image/png;base64," + base64.b64encode(m.read_bytes()).decode() if m and m.is_file() else None)
            kadry.append([obrazy[t][0], t, obrazy[t][1], q, podpis])
        data = page.evaluate(ARKUSZ_JS, [{"typo": plan}, W, H, kadry, 4 if H > W else 3])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(data.split(",", 1)[1]))
    return out


def cmd_render(film: Path, a) -> int:
    proj = load(film)
    texts = [x for x in proj.get("texts") or [] if str(x.get("text") or "").strip()]
    try:
        p = ed.normalize({**proj, "texts": texts}, resolve)
    except ed.ProjectError as exc:
        raise SystemExit(f"projekt nie przechodzi walidacji: {exc}")
    kept = [texts[x["i"]] for x in p["texts"]]   # tylko napisy, które przeszły walidację, w tej samej kolejności
    out = Path(a.out) if a.out else ed.export_name(film)
    has_audio = {str(c["src"]): ed.probe(c["src"]).get("audio", False) for c in p["clips"] if c["kind"] == "video"}
    with tempfile.TemporaryDirectory(prefix="projekt-") as tmp:
        W, H = p["canvas"]["w"], p["canvas"]["h"]
        # jedno uruchomienie przeglądarki: zwykłe obrazy napisów, obraz na każde słowo napisów karaoke, typografia
        jobs = [(t, -1) for t in kept] + [(texts[x["i"]], j) for x in p["texts"] if x.get("kara")
                                          for j in range(len(texts[x["i"]]["words"]))]
        allp, typo = [], {}
        if jobs or p["typo"]["bloki"]:
            with strona([{"texts": [t for t, _ in jobs], "typo": p["typo"]}]) as page:
                allp = text_pngs([t for t, _ in jobs], W, H, Path(tmp), [j for _, j in jobs], page=page)
                typo = typo_warstwy(p["typo"], W, H, p["canvas"]["fps"], p["duration"], Path(tmp), page)
        pngs, rest = allp[:len(kept)], iter(allp[len(kept):])
        kara = {x["i"]: [next(rest) for _ in texts[x["i"]]["words"]] for x in p["texts"] if x.get("kara")}
        layer = ed.karaoke_concat(p, kara, ed.blank_png(Path(tmp) / "pusty.png", W, H), Path(tmp) / "karaoke.ffconcat") if kara else None
        maska = ed.maska_concat(film, proj, p, Path(tmp)) if typo.get("tyl") else None   # osoba nad napisem „za”
        cmd = ed.build_command(p, has_audio, pngs, out, karaoke=layer, typo=typo, maska=maska)
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip()[-1500:], file=sys.stderr)
        return 1
    info = ed.probe(out)
    print(f"Gotowe w {time.time() - t0:.1f} s: {out} · {info.get('w')}×{info.get('h')} · {info.get('duration') or 0:.2f} s")
    otwarte = [n.get("id") for n in proj.get("notes") or [] if isinstance(n, dict) and not n.get("done")]
    if otwarte:
        print(f"⚠ otwarte uwagi właściciela: {', '.join(map(str, otwarte))} (zamknij: projekt.py uwaga <film> <id> --zrobione|--odrzuc)")
    print(f"MEDIA:{out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def film_cmd(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("film", help="oryginalny film (obok niego leży <film>.edycja.json)")
        sp.set_defaults(fn=fn)
        return sp

    film_cmd("pokaz", cmd_pokaz, "co jest na osi czasu").add_argument("--json", action="store_true", help="także cały projekt")
    sp = film_cmd("dodaj-audio", cmd_dodaj_audio, "muzyka, lektor, efekt")
    sp.add_argument("plik")
    sp.add_argument("--start", type=float, default=0.0, help="od której sekundy osi gra")
    sp.add_argument("--od", type=float, help="fragment źródła: początek (s)")
    sp.add_argument("--do", type=float, help="fragment źródła: koniec (s)")
    sp.add_argument("--glosnosc", type=float, default=1.0, help="0–2 (muzyka pod lektorem ok. 0.15–0.3)")
    sp.add_argument("--wycisz-film", action="store_true", help="wycisz oryginalny dźwięk klipów")
    sp.add_argument("--narastanie", type=float, help="narastanie na początku (s, do 10, najwyżej połowa)")
    sp.add_argument("--wyciszanie", type=float, help="wyciszanie na końcu (s; muzyka dłuższa niż film cichnie na końcu filmu)")
    sp = film_cmd("dzwiek", cmd_dzwiek, "głośność i zanik klipu albo audio")
    sp.add_argument("id", help="klip albo audio (z `pokaz`)")
    sp.add_argument("--glosnosc", type=float, help="0–2 (1 = bez zmian)")
    sp.add_argument("--narastanie", type=float, help="s (0 = bez)")
    sp.add_argument("--wyciszanie", type=float, help="s (0 = bez)")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--wycisz", action="store_true", help="wycisz dźwięk klipu")
    g.add_argument("--wlacz", action="store_true", help="włącz dźwięk klipu")
    sp = film_cmd("dodaj-tekst", cmd_dodaj_tekst, "tekst albo napis na obrazie")
    sp.add_argument("tekst")
    sp.add_argument("--start", type=float, required=True)
    sp.add_argument("--koniec", type=float, required=True)
    sp.add_argument("--styl", choices=["shadow", "box", "outline", "plain"])
    sp.add_argument("--y", type=float, help="położenie w pionie 0–1 (0.84 = dół; w kadrze pionowym domyślnie 0.68, nad opisem)")
    sp.add_argument("--rozmiar", type=float)
    sp.add_argument("--kolor")
    sp.add_argument("--tlo", help="kolor tła (styl box) albo obrysu (outline)")
    sp.add_argument("--napis", action="store_true", help="napis (wspólny styl napisów w edytorze)")
    sp.add_argument("--kroj", help="krój z listy edytora: nazwa („Bąbelki”) albo rodzina („Rubik Bubbles”)")
    sp = film_cmd("dodaj-klip", cmd_dodaj_klip, "klip albo plansza na ścieżce głównej")
    sp.add_argument("plik")
    sp.add_argument("--od", type=float)
    sp.add_argument("--do", type=float)
    sp.add_argument("--tempo", type=float, default=1.0)
    sp.add_argument("--pozycja", type=int, help="miejsce na ścieżce (0 = na początek; domyślnie na koniec)")

    def kadr_args(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--wypelnij", action="store_true", help="wypełnij kadr (fit=cover), np. pion z poziomego")
        g.add_argument("--rozmyte", action="store_true", help="całe ujęcie na rozmytym tle z niego samego (fit=blur)")
        g.add_argument("--dopasuj", action="store_true", help="całe ujęcie z czarnymi pasami (fit=contain)")
        sp.add_argument("--fx", type=float, help="punkt skupienia poziomo 0–1 (0.5 = środek, twarz mówcy z klatek)")
        sp.add_argument("--fy", type=float, help="punkt skupienia pionowo 0–1")
        sp.add_argument("--zoom", type=float, help="przybliżenie 1–3 (punch-in ok. 1.15)")
    kadr_args(sp)
    sp = film_cmd("kadr", cmd_kadr, "kadr klipu: wypełnij/dopasuj, punkt skupienia, przybliżenie")
    sp.add_argument("id")
    kadr_args(sp)
    sp = film_cmd("napisy", cmd_napisy, "napisy ze słów albo z SRT")
    sp.add_argument("--srt")
    sp.add_argument("--karaoke", nargs="?", const="", metavar="KOLOR",
                    help="aktywne słowo w kolorze (domyślnie żółty); tylko napisy ze słów, nie z SRT")
    sp.add_argument("--kroj", help="krój napisów z listy edytora: nazwa albo rodzina")
    sp = film_cmd("przejscie", cmd_przejscie, "przejście na cięciu po klipie (nie skraca filmu)")
    sp.add_argument("id", nargs="?", help="klip przed cięciem (z `pokaz`)")
    sp.add_argument("--wszystkie", action="store_true", help="na każdym cięciu")
    sp.add_argument("--typ", choices=ed.PRZEJSCIA, help="rodzaj (domyślnie fade albo obecny)")
    sp.add_argument("--dlugosc", type=float, help="sekundy 0.1–3 (domyślnie 0.5 albo obecna)")
    sp.add_argument("--usun", action="store_true", help="zwykłe cięcie zamiast przejścia")
    sp = film_cmd("tnij", cmd_tnij, "podziel klip (oś się nie zmienia)")
    sp.add_argument("id", help="klip (z `pokaz`)")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--w", type=float, help="chwila osi (s), w której tniesz")
    g.add_argument("--czesci", type=int, help="na tyle równych części (np. 3)")
    sp = film_cmd("wytnij", cmd_wytnij, "wytnij odcinek osi; reszta się dosuwa")
    sp.add_argument("--od", type=float, required=True, help="początek odcinka (s osi)")
    sp.add_argument("--do", type=float, required=True, help="koniec odcinka (s osi)")
    film_cmd("usun", cmd_usun, "usuń element po id").add_argument("id")
    sp = film_cmd("uwaga", cmd_uwaga, "zamknij uwagę z osi edytora")
    sp.add_argument("id")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--zrobione", help="co zmieniłeś (zobaczy to właściciel w edytorze)")
    g.add_argument("--odrzuc", help="dlaczego nie (np. kolizja z inną uwagą, wymaga decyzji)")
    film_cmd("sprawdz", cmd_sprawdz, "walidacja projektu")
    film_cmd("render", cmd_render, "złóż film (jak „Eksportuj”)").add_argument("--out")
    a = ap.parse_args(argv)
    film = Path(a.film).resolve()
    if not film.is_file():
        raise SystemExit(f"nie ma filmu: {film}")
    return a.fn(film, a)


if __name__ == "__main__":
    sys.exit(main())
