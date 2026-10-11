#!/usr/bin/env python3
"""Projekt montażu z edytora HQ: Wideograf pracuje na tym samym projekcie co użytkownik.

Projekt to `<film>.edycja.json` obok filmu (zapisuje go edytor HQ). Zmieniasz go tymi poleceniami
(albo ostrożnie edytując JSON), a `render` składa film tym samym silnikiem co przycisk „Eksportuj”
w edytorze. Użytkownik po otwarciu edytora widzi Twoje zmiany osobno i może je dalej poprawiać.

    projekt.py pokaz <film>                        # co jest na osi (klipy, napisy, audio, długość)
    projekt.py dodaj-audio <film> <plik> [--start S] [--od S] [--do S] [--glosnosc 0.8] [--wycisz-film] [--narastanie 1] [--wyciszanie 2]
    projekt.py dzwiek <film> <id> [--glosnosc 0.3] [--narastanie S] [--wyciszanie S] [--wycisz|--wlacz] [--przypnij|--odlacz]
    projekt.py dzwieki [--kategoria pieniadze] [--rola uderzenie] [--szukaj monety] [--muzyka]   # biblioteka CC0
    projekt.py dodaj-dzwiek <film> <id> [--start S | --na T] [--glosnosc 1] [--narastanie S] [--wyciszanie S]   # --na: szczyt w T
    projekt.py zdanie <film> --na T [--przed ID|brak] [--uderzenie ID] [--po ID|brak] [--rozbieg 1.17] [--odstep 0.83]
                                    # narastanie → uderzenie → błysk: duża chwila filmu (najwyżej 2 na film)
    projekt.py seria <film> --czasy 2.0,2.2,2.4 [--id pop] [--id2 plop] [--glosnosc-od 0.4 --glosnosc-do 0.25]
                                    # seria elementów: dwa efekty na zmianę, coraz ciszej; za gęsto → jeden whoosh
    projekt.py slychac <film> [--json raport.json]          # czy efekty słychać pod głosem i muzyką (po montażu)
    projekt.py slychac [obraz.mp4] --cues cues.json --bed glos.wav [--bed-vol 0.5] [--bed-at 0]   # film z kodu
    projekt.py wyodrebnij <film> (<id klipu> | --plik inny.mp4 [--start S])   # dźwięk z filmu jako osobne audio
    projekt.py lektor <film> "tekst" [--start S] [--glos pl-PL-MarekNeural] [--tempo +5%]   # Edge TTS jak film.py
    projekt.py dodaj-tekst <film> "tekst" --start S --koniec S [--styl shadow|box|outline|plain] [--kroj Poppins]
                                           [--y 0.78] [--rozmiar 72] [--kolor #FFFFFF] [--tlo #000000]
    projekt.py dodaj-klip <film> <plik> [--od S] [--do S] [--tempo 1] [--pozycja N] [--rozmyte|--dopasuj|--wypelnij --fx X --fy Y --zoom Z]
    projekt.py kadr <film> <id> [--rozmyte|--dopasuj|--wypelnij] [--fx 0.4] [--fy 0.35] [--zoom 1.15]   # kadr klipu
    projekt.py kolor <film> <id>|--wszystkie [--styl cieply] [--jasnosc N] [--kontrast N] [--nasycenie N]
                     [--temperatura N] [--auto] [--usun] [--podglad]   # korekcja koloru klipu (suwaki −100…100)
    projekt.py glos <film> <id>|--wszystkie [--poziom auto|lekki|sredni|mocny|brak] [--probka]   # czysty głos klipu albo audio
    projekt.py napisy <film> [--srt plik.srt] [--karaoke [#FFE14D]] [--kroj Kanit]   # napisy ze słów (<źródło>.mowa.json) albo SRT
    projekt.py przejscie <film> <id>|--wszystkie [--typ fade] [--dlugosc 0.5] [--usun]   # przejście na cięciu po klipie
    projekt.py tnij <film> <id> (--w S | --czesci 3)   # podziel klip w chwili osi albo na równe części
    projekt.py wytnij <film> --od S --do S          # wytnij kawałek osi (przez klipy); reszta się dosuwa
    projekt.py usun <film> <id>                    # usuń klip / tekst / audio o danym id (z `pokaz`)
    projekt.py uwaga <film> <id> (--zrobione "co zmieniłem" | --odrzuc "dlaczego")   # zamknij uwagę z osi edytora
    projekt.py z-kodu <film> --obraz czysty.mp4 [--ciecia 5.4,9.6|events.json|os_czasu.json] [--glos lektor.wav[@od]]
                      [--efekty fx.wav] [--muzyka muzyka.wav] [--z-muzyki plan.muzyka.json] [--audio NAZWA=plik[@od]]
                      [--napisy film.srt | --slowa lektor.slowa.json[@od]] [--karaoke] [--kroj Caveat] [--styl box]
                      [--kolor #hex] [--tlo #hex] [--render]
                                    # film z kodu jako projekt: obraz w ujęciach, głos i efekty przypięte do obrazu,
                                    # muzyka osobno, napisy tekstem, suma −14 LUFS; --render: film = render projektu
    projekt.py sprawdz <film>                      # walidacja jak przy eksporcie
    projekt.py render <film> [--out plik.mp4]      # nowa wersja obok oryginału, na końcu linia MEDIA:
    (typografia słowo po słowie, klucz `typo`: plan i poprawki robi typografia.py; render rysuje ją tak jak edytor)

Czas S w sekundach osi (po cięciach i zmianach tempa), chyba że opis mówi „źródła” (--od/--do).
Przejście leży na środku cięcia i nie skraca filmu (napisy i audio zostają na miejscu); długość to parzysta liczba
klatek, najwyżej tyle, ile trwa krótszy z dwóch klipów (`pokaz` pokazuje, co wyszło).
Nic nie nadpisuje oryginału: render zapisuje film-edycja.mp4, film-edycja-2.mp4… (`--out` wskazuje inny plik).

Film z kodu (`z-kodu`): czysty obraz i dźwięki trafiają do `<film>-sciezki/` (obraz bez dźwięku, WAV 48 kHz), projekt
obok filmu, a film powstaje z projektu (`--render` albo `render <film> --out <film>`), więc w edytorze HQ widać
dokładnie to, co oddano. Projektu zmienionego w edytorze `z-kodu` nie nadpisze bez `--nadpisz`. `--z-muzyki` bierze
warstwy z planu `muzyka.py zrob` (muzyka, efekty, głos osobno; jawne --glos/--efekty/--muzyka mają pierwszeństwo).
Słowa (`--slowa`) mają czasy od początku lektora: przesuwa je to samo „od” co głos (`--glos plik@od` albo lektor
w planie muzyki), chyba że podasz własne `--slowa plik@od`.

Uwagi (`notes` w projekcie) zostawia właściciel w edytorze HQ: prośba przypięta do chwili osi, często z kadrem
(obraz w inboxie, oglądasz go przez vision_analyze). Każdą zamykasz `uwaga … --zrobione` albo `--odrzuc` z powodem;
edytor pokazuje je wtedy jako ✓ z Twoim opisem. `render` ostrzega, gdy zostały otwarte.
"""

from __future__ import annotations

import argparse
import array
import base64
import contextlib
import json
import math
import os
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
DZWIEKI = next((p for p in (HERE / "dzwieki", _REPO / "hq" / "web" / "dzwieki") if (p / "katalog.json").exists()), None)
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

KOLOR_ARGI = {"jasnosc": "brightness", "kontrast": "contrast", "nasycenie": "saturation", "temperatura": "temperature"}


def opis_koloru(k: dict | None) -> str:
    k = ed.kolor_norm(k)
    if not k:
        return ""
    nazwy = {v: n for n, v in KOLOR_ARGI.items()}
    suw = ", ".join(f"{nazwy[x]} {k[x]:+d}" for x in ed.KOLOR_SUWAKI if x in k)
    return f" · kolor {k.get('look') or 'własny'}" + (f" ({suw})" if suw else "")


def kolor_auto(c: dict) -> dict:
    """Pomiar klatek klipu jak „Auto” w edytorze HQ (edytor.kolor_pomiar_cmd → kolor_z_pomiaru)."""
    r = subprocess.run(ed.kolor_pomiar_cmd(Path(c["src"]), float(c.get("in", 0)), float(c.get("out", 0)), ed.tools()["ffmpeg"] or "ffmpeg",
                                           sdr=ed.probe(Path(c["src"])).get("sdr", "")), capture_output=True, text=True)
    wynik = ed.kolor_z_pomiaru(r.stderr) if r.returncode == 0 else None
    if not wynik:
        raise SystemExit(f"nie udało się zmierzyć klatek klipu {c.get('id')}: {(r.stderr.strip().splitlines() or [''])[-1][:200]}")
    print(f"  pomiar [{c.get('id')}]: jasność {wynik['pomiar']['jasnosc']}, rozpiętość {wynik['pomiar']['rozpietosc']}, "
          f"nasycenie {wynik['pomiar']['nasycenie']}")
    return wynik["color"] or {}


def tlo_nagrania(src: Path, a: float, b: float) -> float | None:
    """Tło nagrania (dB) wokół odcinka źródła, jak „Auto” czystego głosu w edytorze (edytor.szum_cmd)."""
    od = max(0.0, a - 30)
    r = subprocess.run(ed.szum_cmd(src, ed.tools()["ffmpeg"] or "ffmpeg", od, b - od + 30), capture_output=True, text=True)
    return ed.szum_z_logu(r.stderr) if r.returncode == 0 else None


def cmd_glos(film: Path, a) -> int:
    """Czysty głos klipu albo audio (edytor.glos_filter): poziom wprost albo `auto` z tła nagrania; `--probka` zapisuje
    8 s po czyszczeniu obok filmu (odsłuch dla właściciela)."""
    proj = load(film)
    if a.wszystkie:
        cele = [c for c in proj["clips"] if c.get("kind", "video") == "video" and not c.get("muted")]
    else:
        if not a.id:
            raise SystemExit("podaj id klipu albo audio (z `pokaz`) albo --wszystkie")
        cele = [x for x in [*proj["clips"], *(proj.get("audio") or [])] if x.get("id") == a.id]
        if not cele:
            raise SystemExit(f"nie ma klipu ani audio o id {a.id} (lista: projekt.py pokaz)")
    tla: dict[str, float | None] = {}
    for x in cele:
        src = resolve(str(x["src"]))
        if src is None or not ed.probe(src).get("audio"):
            print(f"[{x.get('id')}] bez dźwięku: pomijam")
            continue
        if a.poziom == "brak":
            x.pop("voice", None)
            print(f"[{x.get('id')}] czysty głos: wyłączony")
            continue
        if str(src) not in tla:
            tla[str(src)] = tlo_nagrania(src, float(x["in"]), float(x["out"]))
        tlo = tla[str(src)]
        x["voice"] = ed.glos_auto(tlo) if a.poziom == "auto" else a.poziom
        print(f"[{x.get('id')}] czysty głos: {x['voice']}" + (f" (tło nagrania {tlo:.0f} dB)" if tlo is not None else " (tła nie udało się zmierzyć)"))
    save(film, proj)
    if a.probka:
        x = next((y for y in cele if y.get("voice")), None)
        if x is None:
            raise SystemExit("--probka: żaden element nie ma czystego głosu")
        src = resolve(str(x["src"]))
        out = film.with_name(f"{film.stem}.glos-{x.get('id')}.mp3")
        d = min(8.0, float(x["out"]) - float(x["in"]))
        r = subprocess.run(ed.glos_probka_cmd(src, float(x["in"]), d, x["voice"], tla.get(str(src)), out,
                                              ed.tools()["ffmpeg"] or "ffmpeg"), capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"próbka się nie udała: {r.stderr.strip()[-300:]}")
        print(f"Próbka {d:.0f} s po czyszczeniu (do odsłuchu dla właściciela): {out}")
        print(f"MEDIA:{out}")
    return 0


def kolor_podglad(film: Path, c: dict) -> Path:
    """Klatka ze środka klipu: lewa połowa przed korektą, prawa po niej (ten sam filtr co eksport; film HDR po
    przeliczeniu na zwykły obraz, jak w eksporcie)."""
    out = film.with_name(f"{film.stem}-kolor-{c.get('id')}.jpg")
    kol = ed.kolor_filter(c.get("color")) or "null"
    sdr = ed.probe(Path(c["src"])).get("sdr", "")
    t = (float(c.get("in", 0)) + float(c.get("out", 0))) / 2
    wej = [] if ed.media_kind(Path(c["src"])) == "image" else ["-ss", f"{t:.3f}"]
    r = subprocess.run([ed.tools()["ffmpeg"] or "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *wej, "-i", str(c["src"]),
                        "-frames:v", "1", "-filter_complex",
                        f"[0:v]scale=-2:540,{sdr + ',' if sdr else ''}format=rgb24,split[a][b];[b]{kol},format=rgb24[k];[a][k]hstack",
                        "-q:v", "3", str(out)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"podgląd koloru: {r.stderr.strip()[-300:]}")
    return out


def cmd_kolor(film: Path, a) -> int:
    proj = load(film)
    clips = proj["clips"]
    if a.wszystkie:
        cele = clips
    else:
        if not a.id:
            raise SystemExit("podaj id klipu (z `pokaz`) albo --wszystkie")
        c = next((x for x in clips if x.get("id") == a.id), None)
        if c is None:
            raise SystemExit(f"nie ma klipu o id {a.id} (lista: projekt.py pokaz)")
        cele = [c]
    zmiany = {v: getattr(a, n) for n, v in KOLOR_ARGI.items() if getattr(a, n) is not None}
    for c in cele:
        if a.usun:
            c.pop("color", None)
            continue
        kol = dict(c.get("color") or {})
        if a.styl:
            kol = {} if a.styl == "brak" else {"look": a.styl, **ed.kolor_domyslne(a.styl)}
        if a.auto:
            kol = {**{k: v for k, v in kol.items() if k not in ed.KOLOR_SUWAKI}, **kolor_auto(c)}
        kol = ed.kolor_norm({**kol, **zmiany})
        if kol:
            c["color"] = kol
        else:
            c.pop("color", None)
    save(film, proj)
    for c in cele:
        print(f"Kolor [{c.get('id')}]: {opis_koloru(c.get('color'))[len(' · kolor '):] or 'bez korekty'}")
    if a.podglad:
        out = kolor_podglad(film, cele[0])
        print(f"Przed | po (klatka ze środka klipu {cele[0].get('id')}): {out}")
        print(f"MEDIA:{out}")
    return 0


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
                         f" · głośność {c.get('volume', 1):.2f}" if c.get("volume", 1) != 1 else "",
                         f" · czysty głos {c['voice']}" if c.get("voice") else ""])
        print(f"  [{c.get('id')}] {s:6.2f}–{e:6.2f}  {Path(c['src']).name} (źródło {c['in']:.2f}–{c['out']:.2f}){extra}{opis_zaniku(c)}{opis_koloru(c.get('color'))}")
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
        print(f"  [{m.get('id')}] od {m['start']:6.2f} przez {m['out'] - m['in']:.2f} s  "
              + (f"{m['label']} ({Path(m['src']).name})" if m.get("label") else Path(m["src"]).name)
              + f" · głośność {m.get('volume', 1):.2f}{opis_zaniku(m)}"
              + (f" · czysty głos {m['voice']}" if m.get("voice") else "") + (" · przypięte do obrazu" if m.get("linked") else ""))
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
    if a.przypnij or a.odlacz:
        if x in proj["clips"]:
            raise SystemExit("--przypnij/--odlacz dotyczy elementu audio (dźwięk klipu i tak idzie z klipem)")
        x["linked"] = bool(a.przypnij)
    for arg, key in (("narastanie", "fadeIn"), ("wyciszanie", "fadeOut")):
        if getattr(a, arg) == 0:                   # 0 = bez zaniku
            x.pop(key, None)
    x.update(zanik_z_arg(a, d, x))
    save(film, proj)
    print(f"[{a.id}] głośność {x.get('volume', 1):.2f}{' · wyciszony' if x.get('muted') else ''}{opis_zaniku(x)}"
          f"{' · przypięte do obrazu' if x.get('linked') else ''}")
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


# ---------------------------------------------------------------- audio: biblioteka, wyodrębnienie, lektor

def cmd_dzwieki(_film, a) -> int:
    """Biblioteka CC0 (ta sama co menu Audio w edytorze HQ): id do `dodaj-dzwiek`, kategoria, długość, nazwa."""
    kat = ed.dzwieki_katalog(DZWIEKI)
    if not kat["dzwieki"]:
        raise SystemExit("brak biblioteki dźwięków (hq/web/dzwieki, scripts/dzwieki w profilu)")
    nazwy = {k["id"]: k["nazwa"] for k in kat["kategorie"]}
    q = (a.szukaj or "").lower()
    rows = [d for d in kat["dzwieki"]
            if (not a.kategoria or d["kat"] == a.kategoria) and (not a.muzyka or d["kat"] == "muzyka")
            and (not a.rola or a.rola in (d.get("rola") or []))
            and (not q or q in f"{d['id']} {d['nazwa']} {d['en']}".lower())]
    if not rows:
        role = sorted({r for d in kat["dzwieki"] for r in d.get("rola") or []})
        print(f"Nic nie pasuje. Kategorie: {', '.join(nazwy)}" + (f"; role: {', '.join(role)}" if role else ""))
        return 1
    for d in rows:
        cechy = ([f"szczyt {d['szczyt']:.2f} s"] if d.get("szczyt") is not None else []) + list(d.get("rola") or []) \
            + (["gra: nie do reklamy"] if d.get("gra") else [])
        print(f"  {d['id']:<26} {nazwy.get(d['kat'], d['kat']):<12} {d['dl']:6.2f} s  {d['nazwa']}"
              + (f"  ({', '.join(cechy)})" if cechy else ""))
    print(f"{len(rows)} z {len(kat['dzwieki'])} (CC0, autorzy w {DZWIEKI}/LICENCJE.md). "
          "Dodaj: projekt.py dodaj-dzwiek <film> <id> --start S (albo --na T: szczyt efektu w T)")
    return 0


def dodaj_plik_audio(film: Path, proj: dict, src: Path, start: float, glosnosc: float, a, od: float = 0.0,
                     do: float | None = None) -> dict:
    dur = ed.probe(src).get("duration") or 0
    do = dur if do is None else do
    if do - od <= 0.05:
        raise SystemExit(f"pusty dźwięk: {src}")
    item = {"id": new_id("a"), "src": str(src), "start": max(0.0, start), "in": od, "out": do,
            "volume": max(0.0, min(2.0, glosnosc)), **zanik_z_arg(a, do - od)}
    proj.setdefault("audio", []).append(item)
    return item


def cmd_dodaj_dzwiek(film: Path, a) -> int:
    proj = load(film)
    hit = ed.dzwiek_plik(DZWIEKI, a.id)
    if not hit:
        raise SystemExit(f"nie ma „{a.id}” w bibliotece (lista: projekt.py dzwieki)")
    dest = ed.dzwiek_do_filmu(DZWIEKI, a.id, film)
    vol = a.glosnosc if a.glosnosc is not None else (0.3 if hit[0]["kat"] == "muzyka" else 1.0)
    szczyt = float(hit[0].get("szczyt") or 0)
    start = a.start if a.na is None else a.na - szczyt          # --na: najgłośniejsza chwila efektu trafia w T
    item = dodaj_plik_audio(film, proj, dest, max(0.0, start), vol, a, od=max(0.0, -start))
    save(film, proj)
    print(f"Dodano dźwięk [{item['id']}] {hit[0]['nazwa']} ({dest.name}) od {item['start']:.2f} s ({item['out'] - item['in']:.2f} s)"
          + (f", szczyt na {a.na:.2f} s" if a.na is not None else ""))
    return 0


# ---------------------------------------------------------------- zdanie dźwiękowe i seria (za video-shotcraft, Apache-2.0)

ZDANIE_ROZBIEG = 1.17       # narastanie słychać 35 klatek (przy 30 kl./s) przed uderzeniem
ZDANIE_ODSTEP = 0.83        # błysk 25 klatek po uderzeniu
ZDANIE_GLOSNOSC = {"narastanie": 0.5, "uderzenie": 0.9, "blysk": 0.45}   # uderzenie to najgłośniejsza chwila filmu
ZDANIE_MAX = 2              # finał i najwyżej jedna kulminacja: częste duże uderzenie traci siłę
SERIA_GLOSNOSC = (0.40, 0.25)   # pierwszy i ostatni element: ciszej z każdym, jak oddalanie się, nie karabin
SERIA_ODSTEP = 0.1          # gęściej niż co 3 klatki (30 kl./s) ucho nie liczy uderzeń: jeden whoosh zamiast serii


def efekt(id_: str) -> dict:
    hit = ed.dzwiek_plik(DZWIEKI, id_)
    if not hit:
        raise SystemExit(f"nie ma „{id_}” w bibliotece (lista: projekt.py dzwieki)")
    if hit[0]["kat"] == "muzyka":
        raise SystemExit(f"„{id_}” to podkład, nie efekt")
    return hit[0]


def rola_ids(rola: str) -> list[str]:
    """Efekty roli w kolejności wyboru (katalog „role”, z ROLE w scripts/dzwieki.py)."""
    return list(ed.dzwieki_katalog(DZWIEKI)["role"].get(rola) or [])


def miejsce_na_audio(proj: dict, ile: int) -> None:
    """Edytor bierze najwyżej MAX_AUDIO elementów audio, a nadmiar pomija bez słowa: odmowa przed dodaniem."""
    jest = len(proj.get("audio") or [])
    if jest + ile > ed.MAX_AUDIO:
        raise SystemExit(f"za dużo audio: projekt ma {jest}, doszłoby {ile}, a edytor bierze najwyżej {ed.MAX_AUDIO} "
                         "(połącz efekty w jeden plik albo usuń zbędne: projekt.py usun)")


def poloz_efekt(film: Path, proj: dict, id_: str, szczyt_na: float, glosnosc: float,
                rozbieg: float | None = None) -> dict:
    """Efekt z biblioteki tak, by jego szczyt trafił w `szczyt_na` (s osi). `rozbieg`: słychać najwyżej tyle s przed
    szczytem (dłuższy początek przycięty i wchodzi z narastaniem); początek osi przycina tak samo."""
    sz = float(efekt(id_).get("szczyt") or 0)
    od = sz - rozbieg if rozbieg is not None and sz > rozbieg else 0.0
    start = szczyt_na - (sz - od)
    if start < 0:
        od, start = od - start, 0.0
    zan = argparse.Namespace(narastanie=min(0.3, sz - od) if od > 0 else None, wyciszanie=None)
    return dodaj_plik_audio(film, proj, ed.dzwiek_do_filmu(DZWIEKI, id_, film), start, glosnosc, zan, od=od)


def zdania_w_projekcie(proj: dict) -> int:
    """Ile głośnych uderzeń (rola „uderzenie”, głośność ≥ 0,8) jest już na osi."""
    ids = set(rola_ids("uderzenie"))
    return sum(1 for m in proj.get("audio") or [] if Path(str(m.get("src") or "")).stem in ids
               and float(m.get("volume") or 0) >= 0.8)


def cmd_zdanie(film: Path, a) -> int:
    """Narastanie → uderzenie → błysk na jedną chwilę T (szczyty: narastania i uderzenia w T, błysku w T + odstęp)."""
    proj = load(film)
    czesci = [(r, x) for r, x in (("narastanie", a.przed), ("uderzenie", a.uderzenie), ("blysk", a.po)) if x != "brak"]
    czesci = [(r, x or rola_ids(r)[0]) for r, x in czesci]
    miejsce_na_audio(proj, len(czesci))
    byly = zdania_w_projekcie(proj)
    print(f"Zdanie dźwiękowe na {a.na:.2f} s:")
    for rola, id_ in czesci:
        na = a.na + (a.odstep if rola == "blysk" else 0.0)
        item = poloz_efekt(film, proj, id_, na, round(ZDANIE_GLOSNOSC[rola] * a.glosnosc, 3),
                           a.rozbieg if rola == "narastanie" else None)
        print(f"  {rola:<10} [{item['id']}] {id_:<20} od {item['start']:6.2f} s, szczyt {na:6.2f} s, głośność {item['volume']:.2f}")
    save(film, proj)
    if byly + (1 if any(r == "uderzenie" for r, _ in czesci) else 0) > ZDANIE_MAX:
        print(f"⚠ to już {byly + 1}. głośne uderzenie w filmie: częste traci siłę (najwyżej {ZDANIE_MAX}: finał i jedna "
              "kulminacja; resztę zrób mniejszym efektem albo ciszą przed akcentem)")
    return 0


def plan_serii(czasy: list[float], ids: list[str], ruchy: dict[str, float], od: float = SERIA_GLOSNOSC[0],
               do: float = SERIA_GLOSNOSC[1], odstep: float = SERIA_ODSTEP) -> list[dict]:
    """Seria elementów: efekty z `ids` na zmianę, głośność liniowo od `od` do `do`. Trafienia bliżej niż `odstep`
    ucho zlewa: dwa = zostaje pierwsze, trzy i więcej = jeden whoosh (z `ruchy`: id → długość) szczytem w środku."""
    czasy = sorted(czasy)
    n = len(czasy)
    vol = [round(od + (do - od) * i / (n - 1), 3) if n > 1 else od for i in range(n)]
    grupy: list[list[int]] = []
    for i, t in enumerate(czasy):
        if grupy and t - czasy[grupy[-1][-1]] < odstep:
            grupy[-1].append(i)
        else:
            grupy.append([i])
    out, k = [], 0
    for g in grupy:
        if len(g) <= 2:
            out.append({"id": ids[k % len(ids)], "t": czasy[g[0]], "glosnosc": vol[g[0]], "pominiete": len(g) - 1})
            k += 1
            continue
        a, b = czasy[g[0]], czasy[g[-1]]
        w = min(ruchy, key=lambda x: abs(ruchy[x] - (b - a + 0.2)))
        out.append({"id": w, "t": round((a + b) / 2, 3), "glosnosc": round(sum(vol[i] for i in g) / len(g), 3),
                    "zamiast": len(g), "od": a, "do": b})
    return out


def cmd_seria(film: Path, a) -> int:
    proj = load(film)
    try:
        czasy = [float(x) for x in a.czasy.replace(";", ",").split(",") if x.strip()]
    except ValueError:
        raise SystemExit("--czasy: liczby sekund po przecinku, np. 2.0,2.2,2.4")
    if len(czasy) < 2:
        raise SystemExit("seria to co najmniej 2 czasy (jeden efekt: dodaj-dzwiek --na T)")
    pierwszy = a.id or rola_ids("pojawienie")[0]
    w = efekt(pierwszy)
    drugi = a.id2
    if not drugi:
        para = [i for i in rola_ids((w.get("rola") or ["?"])[0]) if i != pierwszy
                and efekt(i).get("sha256") != w.get("sha256")]
        drugi = para[0] if para else None
    if drugi:
        efekt(drugi)
    else:
        print(f"⚠ „{pierwszy}” nie ma pary w swojej roli: jeden plik raz za razem brzmi jak karabin (podaj --id2)")
    ruchy = {i: float(efekt(i).get("dl") or 0) for i in rola_ids("ruch")}
    plan = plan_serii(czasy, [pierwszy] + ([drugi] if drugi else []), ruchy, a.glosnosc_od, a.glosnosc_do)
    miejsce_na_audio(proj, len(plan))
    for x in plan:
        item = poloz_efekt(film, proj, x["id"], x["t"], x["glosnosc"])
        if x.get("zamiast"):
            print(f"  {x['od']:6.2f}–{x['do']:.2f} s: {x['zamiast']} trafień gęściej niż co {SERIA_ODSTEP:g} s "
                  f"→ jeden {x['id']} [{item['id']}] (szczyt {x['t']:.2f} s, głośność {item['volume']:.2f})")
        else:
            print(f"  {x['t']:6.2f} s  {x['id']:<12} [{item['id']}] głośność {item['volume']:.2f}"
                  + (f"  (pominięte {x['pominiete']} za blisko)" if x["pominiete"] else ""))
    save(film, proj)
    return 0


# ---------------------------------------------------------------- słyszalność efektów (pomysł i progi za video-talkcraft,
# licencja niekomercyjna: tylko pomysł i liczby, kod i opis własne)

SLUCH_SR = 16000            # pomiar: mono 16 kHz, obwiednia co 10 ms
SLUCH_OBECNY = -45.0        # szczyt efektu poniżej: efektu nie ma (za cicho w ogóle)
SLUCH_MASKA = -6.0          # efekt cichszy od tła o więcej: zagłuszony
SLUCH_CZYSTO = 6.0          # efekt głośniejszy od tła o tyle albo w przerwie w mowie: słychać czysto
SLUCH_PRZERWA = 0.3         # przerwa w mowie (oddech) od tylu sekund
SLUCH_ZAGLUSZONE_MAX = 0.5  # zagłuszonych najwyżej połowa
SLUCH_CZYSTE_NA = 30.0      # czysto słyszalnych co najmniej max(3, długość / 30 s)
SLUCH_PRZESUN = {"ruch", "przejscie", "pojawienie", "klik", "pisanie"}   # te wolno przesunąć do przerwy; zdanie stoi
CUE_ROLA = {"whoosh": "ruch", "whip": "ruch", "riser": "narastanie", "thump": "uderzenie", "crack": "uderzenie",
            "sparkle": "blysk", "chime": "blysk", "pop": "pojawienie", "drip": "pojawienie", "boing": "pojawienie",
            "chirp": "pojawienie", "click": "klik", "tick": "klik", "step": "klik", "scratch": "przejscie",
            "splash": "przejscie", "fall": "ruch", "buzz": "klik", "burner": "ruch"}


def obwiednia_db(x, sr: int) -> list[float]:
    """RMS w oknach 10 ms → dBFS (cisza = −100)."""
    n = sr // 100
    out = []
    for i in range(0, len(x) - n + 1, n):
        e = sum(v * v for v in x[i:i + n]) / n
        out.append(10 * math.log10(e) if e > 1e-10 else -100.0)
    return out


def pcm_mono(path: Path, od: float = 0.0, dl: float | None = None, sr: int = SLUCH_SR) -> array.array:
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, od):.3f}"]
    cmd += ["-t", f"{dl:.3f}"] if dl else []
    r = subprocess.run(cmd + ["-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    a = array.array("f")
    a.frombytes(r.stdout[:len(r.stdout) // 4 * 4])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def _srednia_db(v: list[float]) -> float:
    e = sum(10 ** (x / 10) for x in v) / len(v) if v else 0.0
    return 10 * math.log10(e) if e > 1e-10 else -100.0


def przerwy_w_tle(tlo: list[float]) -> tuple[float, list[tuple[float, float]]]:
    """Ciche miejsca tła (oddech lektora, pauza muzyki): próg = 90. centyl tła − 20 dB, nie niżej niż −45 dBFS;
    przerwy ≥ SLUCH_PRZERWA s jako (od, do) w s."""
    zywe = sorted(v for v in tlo if v > -60)
    prog = max(SLUCH_OBECNY, zywe[int(0.9 * (len(zywe) - 1))] - 20) if zywe else SLUCH_OBECNY
    out, i = [], 0
    while i < len(tlo):
        if tlo[i] < prog:
            j = i
            while j < len(tlo) and tlo[j] < prog:
                j += 1
            if (j - i) / 100 >= SLUCH_PRZERWA:
                out.append((i / 100, j / 100))
            i = j
        else:
            i += 1
    return prog, out


def ocena_slyszalnosci(zdarzenia: list[dict], tlo: list[float], dur: float) -> dict:
    """`zdarzenia`: {"id", "nazwa", "start" (s osi), "env" (dB co 10 ms od startu), "glosnosc", "rola"}; `tlo`: dB co 10 ms
    od 0 (głos, muzyka, dźwięk klipów, bez efektów). Każdy efekt mierzony w swoim „ciele” (do 10 dB pod szczytem,
    od 50 ms przed do 450 ms po szczycie) kontra tło w tych samych chwilach."""
    prog, przerwy = przerwy_w_tle(tlo)
    wiersze = []
    for z in zdarzenia:
        env = z["env"] or [-100.0]
        k = max(range(len(env)), key=env.__getitem__)
        szczyt = env[k]
        cialo = [i for i in range(max(0, k - 5), min(len(env), k + 46)) if env[i] >= szczyt - 10]
        t0 = round(z["start"] * 100)
        fx = [env[i] for i in cialo]
        bg = [tlo[t0 + i] if 0 <= t0 + i < len(tlo) else -100.0 for i in cialo]
        sfx_db, tlo_db = _srednia_db(fx), _srednia_db(bg)
        zapas = sfx_db - tlo_db
        w_przerwie = tlo_db < prog
        t_szczyt = round(z["start"] + k / 100, 2)
        ocena = ("brak" if szczyt < SLUCH_OBECNY else "czysto" if w_przerwie or zapas >= SLUCH_CZYSTO
                 else "slychac" if zapas >= SLUCH_MASKA else "zagluszony")
        porada = None
        przesun = bool(set(z.get("rola") or []) & SLUCH_PRZESUN) or not z.get("rola")
        przejscie = bool(set(z.get("rola") or []) & {"ruch", "przejscie"})
        blisko = [a for a, _b in przerwy if abs(a + 0.05 - t_szczyt) <= 0.6]
        if ocena != "brak" and blisko and przesun and (ocena == "zagluszony" or (ocena == "slychac" and przejscie)):
            porada = f"przesuń szczyt na {min(blisko, key=lambda a: abs(a - t_szczyt)) + 0.05:.2f} s (cisza w tle)"
        elif ocena in ("zagluszony", "brak"):
            g = (z.get("glosnosc") or 1.0) * 10 ** ((max(SLUCH_MASKA - zapas, SLUCH_OBECNY - szczyt) + 1) / 20)
            porada = f"głośniej: {g:.2f}" if g <= 2 else "za cicho nawet przy głośności 2: zmień efekt albo ścisz tło w tej chwili"
        wiersze.append({"id": z.get("id"), "nazwa": z.get("nazwa"), "t": t_szczyt, "szczyt_db": round(szczyt, 1),
                        "efekt_db": round(sfx_db, 1), "tlo_db": round(tlo_db, 1), "zapas_db": round(zapas, 1),
                        "ocena": ocena, "porada": porada, "rola": z.get("rola") or []})
    n = len(wiersze)
    ile = {o: sum(1 for w in wiersze if w["ocena"] == o) for o in ("czysto", "slychac", "zagluszony", "brak")}
    wymagane = min(max(3, math.ceil(dur / SLUCH_CZYSTE_NA)), n)
    bledy = []
    if ile["brak"]:
        bledy.append(f"{ile['brak']} efekt(ów) prawie bez dźwięku (szczyt poniżej {SLUCH_OBECNY:g} dBFS)")
    if n and ile["zagluszony"] > SLUCH_ZAGLUSZONE_MAX * n:
        bledy.append(f"zagłuszonych {ile['zagluszony']} z {n} (najwyżej połowa)")
    if ile["czysto"] < wymagane:
        bledy.append(f"czysto słyszalnych {ile['czysto']}, potrzeba {wymagane} (max(3, długość/30 s)): połóż efekty "
                     f"w cichych miejscach tła (jest ich {len(przerwy)}) albo podnieś głośność")
    return {"efekty": wiersze, "ile": ile, "wymagane_czysto": wymagane, "prog_przerwy_db": round(prog, 1),
            "przerwy": [[round(a, 2), round(b, 2)] for a, b in przerwy], "dlugosc": round(dur, 2),
            "ok": not bledy, "bledy": bledy}


def tlo_projektu(film: Path, proj: dict, efekty_src: set[str]) -> list[float]:
    """Dźwięk projektu bez efektów, złożony tym samym grafem co eksport (głos z czyszczeniem, przejścia, zaniki),
    obraz w małym kadrze; PCM zamiast AAC, żeby nic nie przesunęło czasu."""
    p = ed.normalize({**proj, "texts": []}, resolve)
    p = {**p, "texts": [], "audio": [m for m in p["audio"] if str(m["src"]) not in efekty_src]}
    W, H = p["canvas"]["w"], p["canvas"]["h"]
    p["canvas"] = {**p["canvas"], "w": 64, "h": max(16, round(64 * H / W / 2) * 2)}
    info = {str(c["src"]): ed.probe(c["src"]) for c in p["clips"] if c["kind"] == "video"}
    szum = {}
    for src, (od, dl) in ed.szum_zakresy(p).items():
        r = subprocess.run(ed.szum_cmd(Path(src), ed.tools()["ffmpeg"] or "ffmpeg", od, dl), capture_output=True, text=True)
        szum[src] = ed.szum_z_logu(r.stderr) if r.returncode == 0 else None
    with tempfile.TemporaryDirectory(prefix="slychac-") as tmp:
        out = Path(tmp) / "tlo.mov"
        cmd = ed.build_command(p, {k: v.get("audio", False) for k, v in info.items()}, [], out, szum=szum)
        i = cmd.index("-c:a")
        cmd[i + 1:i + 4] = ["pcm_s16le"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"ffmpeg (tło bez efektów): {(r.stderr.strip().splitlines() or ['błąd'])[-1]}")
        return obwiednia_db(pcm_mono(out), SLUCH_SR)


def zdarzenia_projektu(film: Path, proj: dict) -> list[dict]:
    """Efekty z biblioteki na osi (pliki w <katalog filmu>/dzwieki/ o id efektu, nie podkład)."""
    kat = {d["id"]: d for d in ed.dzwieki_katalog(DZWIEKI)["dzwieki"] if d["kat"] != "muzyka"}
    out = []
    for m in proj.get("audio") or []:
        src = resolve(str(m.get("src") or ""))
        w = kat.get(src.stem) if src and src.parent.name == ed.DZWIEKI_DIR else None
        if not w:
            continue
        od, do, vol = float(m.get("in") or 0), float(m.get("out") or 0), float(m.get("volume", 1) or 0)
        x = pcm_mono(src, od, max(0.05, do - od))
        out.append({"id": m.get("id"), "nazwa": w["id"], "start": float(m.get("start") or 0), "glosnosc": vol,
                    "rola": w.get("rola") or [], "src": str(src),
                    "env": [v + 20 * math.log10(vol) if vol > 0 else -100.0 for v in obwiednia_db(x, SLUCH_SR)]})
    return out


def zdarzenia_cues(cues: Path, sound: Path) -> list[dict]:
    """Każdy cue z `cues.json` osobno przez mix() z sound.mjs (ta sama synteza co w filmie, przed loudnorm)."""
    lista = json.loads(cues.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="cues-") as tmp:
        js = ("import { mix } from " + json.dumps(sound.resolve().as_uri()) + "; import fs from 'node:fs';"
              "const cues = JSON.parse(fs.readFileSync(process.env.CUES, 'utf8'));"
              "cues.forEach((c, i) => { const [L, R] = mix([{ ...c, t: 0 }], (c.dur || 1.5) + 0.6);"
              "const m = new Float32Array(L.length); for (let k = 0; k < L.length; k++) m[k] = (L[k] + R[k]) / 2;"
              "fs.writeFileSync(`${process.env.OUT}/c${i}.f32`, Buffer.from(m.buffer)); });")
        r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True,
                           env={**os.environ, "CUES": str(cues), "OUT": tmp})
        if r.returncode != 0:
            raise SystemExit(f"node sound.mjs: {(r.stderr.strip().splitlines() or ['błąd'])[-1]}")
        out = []
        for i, c in enumerate(lista):
            x = array.array("f")
            x.frombytes((Path(tmp) / f"c{i}.f32").read_bytes())
            if sys.byteorder == "big":
                x.byteswap()
            out.append({"id": f"cue {i + 1}", "nazwa": str(c.get("sfx") or "pop"), "start": float(c.get("t") or 0),
                        "glosnosc": float(c.get("vol", 0.5)), "rola": [CUE_ROLA.get(str(c.get("sfx") or "pop"), "klik")],
                        "env": obwiednia_db(x, 48000)})
    return out


def wypisz_slychac(nazwa: str, r: dict) -> int:
    znak = {"czysto": "✓", "slychac": "·", "zagluszony": "✗", "brak": "✗"}
    opis = {"czysto": "czysto", "slychac": "słychać", "zagluszony": "zagłuszony", "brak": "prawie bez dźwięku"}
    print(f"{nazwa}: {len(r['efekty'])} efektów · ciche miejsca tła (oddech, pauza muzyki) od {SLUCH_PRZERWA:g} s: "
          f"{len(r['przerwy'])} (tło poniżej {r['prog_przerwy_db']:g} dBFS)")
    for w in sorted(r["efekty"], key=lambda w: w["t"]):
        print(f"  {znak[w['ocena']]} {w['t']:6.2f} s  {w['nazwa']:<20} {w['zapas_db']:+5.1f} dB względem tła  "
              f"{opis[w['ocena']]}" + (f"  → {w['porada']}" if w["porada"] else ""))
    i = r["ile"]
    print(f"Czysto {i['czysto']}, słychać {i['slychac']}, zagłuszone {i['zagluszony']}, bez dźwięku {i['brak']} "
          f"(czysto potrzeba {r['wymagane_czysto']}).")
    for b in r["bledy"]:
        print(f"✗ {b}")
    print("Wynik: OK" if r["ok"] else "Wynik: DO POPRAWY")
    return 0 if r["ok"] else 1


def cmd_slychac(_film, a) -> int:
    """Czy efekty słychać: każdy efekt kontra tło (głos, muzyka, dźwięk klipów) w tych samych chwilach."""
    if a.cues:
        if not a.bed and not a.film:
            raise SystemExit("film z kodu: --cues cues.json --bed glos.wav (podkład z głosem, ten sam co dla sound.mjs)")
        import narzedzia
        sound = Path(a.sound) if a.sound else Path(os.environ.get("ANIM") or narzedzia.ANIMACJA_SKILL) / "scripts" / "sound.mjs"
        if not sound.is_file():
            raise SystemExit(f"brak sound.mjs ({sound}): narzedzia.py instaluj animacja")
        zd = zdarzenia_cues(Path(a.cues), sound)
        dur = float(ed.probe(Path(a.film)).get("duration") or 0) if a.film else 0.0
        tlo: list[float] = []
        if a.bed:
            bed = [v + 20 * math.log10(a.bed_vol) for v in obwiednia_db(pcm_mono(Path(a.bed)), SLUCH_SR)]
            tlo = [-100.0] * round(a.bed_at * 100) + bed
        dur = dur or max([len(tlo) / 100] + [z["start"] + len(z["env"]) / 100 for z in zd])
        tlo = (tlo + [-100.0] * round(dur * 100))[:round(dur * 100)]
        nazwa = Path(a.cues).name
    else:
        if not a.film:
            raise SystemExit("podaj film projektu (albo --cues i --bed dla filmu z kodu)")
        film = _film or Path(a.film).resolve()
        proj = load(film)
        zd = zdarzenia_projektu(film, proj)
        if not zd:
            print("Na osi nie ma efektów z biblioteki (projekt.py dzwieki, dodaj-dzwiek).")
            return 0
        tlo = tlo_projektu(film, proj, {z["src"] for z in zd})
        dur, nazwa = len(tlo) / 100, film.name
    r = ocena_slyszalnosci(zd, tlo, dur)
    if a.json:
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return wypisz_slychac(nazwa, r)


def wyodrebnij_plik(film: Path, src: Path) -> Path:
    """Ta sama ścieżka i polecenie co „Wyodrębnij” w edytorze HQ (edytor.wyodrebnij_cel / wyodrebnij_cmd)."""
    info = ed.probe(src)
    if not info.get("audio"):
        raise SystemExit(f"ten film nie ma dźwięku: {src.name}")
    dest = ed.wyodrebnij_cel(film, src)
    if not dest.is_file() or dest.stat().st_mtime < src.stat().st_mtime:
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(ed.wyodrebnij_cmd(src, dest, info.get("acodec")), capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"ffmpeg: {(r.stderr.strip().splitlines() or ['błąd'])[-1]}")
    return dest


def cmd_wyodrebnij(film: Path, a) -> int:
    """Klip z osi: dźwięk staje się osobnym audio w tym samym miejscu, a klip jest wyciszony (jak w CapCut).
    --plik: dźwięk innego filmu jako audio od --start."""
    proj = load(film)
    if a.plik:
        src = resolve(a.plik)
        if not src or ed.media_kind(src) != "video":
            raise SystemExit(f"to nie film: {a.plik}")
        item = dodaj_plik_audio(film, proj, wyodrebnij_plik(film, src), a.start or 0.0, 1.0, a)
        save(film, proj)
        print(f"Dodano dźwięk filmu [{item['id']}] {src.name} od {item['start']:.2f} s ({item['out'] - item['in']:.2f} s)")
        return 0
    if not a.id:
        raise SystemExit("podaj id klipu (z `pokaz`) albo --plik")
    hit = next(((c, s) for c, s, _e in layout(proj["clips"]) if c.get("id") == a.id), None)
    if not hit:
        raise SystemExit(f"nie ma klipu {a.id} (lista: projekt.py pokaz)")
    c, s = hit
    if c.get("kind") == "image" or ed.media_kind(c["src"]) != "video":
        raise SystemExit("zdjęcie nie ma dźwięku")
    if abs(float(c.get("speed") or 1) - 1) > 1e-6:
        raise SystemExit("klip ma zmienione tempo: wyodrębnienie działa przy tempie 1× (dźwięk audio nie zmienia tempa)")
    if c.get("muted"):
        raise SystemExit("klip jest wyciszony: najpierw `dzwiek <film> <id> --wlacz`, jeśli chcesz jego dźwięk")
    item = {"id": new_id("a"), "src": str(wyodrebnij_plik(film, Path(c["src"]))), "start": round(s, 4),
            "in": c["in"], "out": c["out"], "volume": c.get("volume", 1),
            **{k: c[k] for k in ("fadeIn", "fadeOut") if c.get(k)}}
    proj.setdefault("audio", []).append(item)
    c["muted"] = True
    save(film, proj)
    print(f"Dźwięk klipu [{c['id']}] jest teraz osobnym audio [{item['id']}] od {s:.2f} s; klip wyciszony")
    return 0


def cmd_lektor(film: Path, a) -> int:
    """Lektor Edge TTS (wideo_lib: ten sam co film.py, z cache) → <katalog filmu>/lektor/ → audio od --start."""
    import shutil as _sh
    import wideo_lib as wl
    tekst = " ".join(a.tekst.split())
    if not tekst:
        raise SystemExit("pusty tekst lektora")
    glos = a.glos or ed.GLOSY[0]
    tempo = ed.tempo_tts(a.tempo)
    proj = load(film)
    dest = ed.lektor_cel(film, tekst, glos, tempo)
    if not dest.is_file():
        sp = wl.speak_many([{"text": tekst, "voice": glos, "rate": tempo}])[0]
        dest.parent.mkdir(parents=True, exist_ok=True)
        _sh.copy2(sp.audio, dest)
        wl.write_json(dest.with_suffix(".slowa.json"), [w.__dict__ for w in sp.words])
    item = dodaj_plik_audio(film, proj, dest, a.start, 1.0, a)
    save(film, proj)
    print(f"Dodano lektora [{item['id']}] {dest.name} od {item['start']:.2f} s ({item['out'] - item['in']:.2f} s, {glos}, {tempo})")
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
        if not any(warstwa in ed.typo_warstwy(b) for b in plan["bloki"]):   # efekt i słowo z głębią: obie warstwy
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
    sdr = ed.probe(Path(c["src"])).get("sdr", "") if c.get("kind") != "image" else ""
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *src, "-frames:v", "1",
                    "-filter_complex", f"[0:v]{fit}{',' + sdr if sdr else ''}", str(dest)], check=True)
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
        g.clearRect(0, 0, W, H); typoKameraObraz(g, img, Q, W, H, t);     // film przez wirtualną kamerę planu
        typoRysuj(g, Q, W, H, t, "tyl");
        if (maska) {          // osoba nad warstwą „za osobą”: klatka przycięta sylwetką (oba przez tę samą kamerę)
            const m = new Image(); m.src = maska; await m.decode();
            o.globalCompositeOperation = "source-over"; o.clearRect(0, 0, W, H); typoKameraObraz(o, img, Q, W, H, t);
            o.globalCompositeOperation = "destination-in"; typoKameraObraz(o, m, Q, W, H, t);
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
    info_src = {str(c["src"]): ed.probe(c["src"]) for c in p["clips"] if c["kind"] == "video"}
    has_audio = {k: v.get("audio", False) for k, v in info_src.items()}
    sdr = {k: v.get("sdr", "") for k, v in info_src.items()}           # film HDR z telefonu → zwykły obraz
    for k, v in info_src.items():
        if v.get("hdr"):
            print(f"  HDR ({v['hdr']}): {Path(k).name} przeliczam na zwykły obraz (SDR)")
    import wideo_lib as wl
    with wl.miejsce_renderu("projekt.py render"), tempfile.TemporaryDirectory(prefix="projekt-") as tmp:
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
        szum = {}                                              # czysty głos: tło nagrania pod próg odszumiania
        for s, (od, dl) in ed.szum_zakresy(p).items():
            r = subprocess.run(ed.szum_cmd(Path(s), ed.tools()["ffmpeg"] or "ffmpeg", od, dl), capture_output=True, text=True)
            szum[s] = ed.szum_z_logu(r.stderr) if r.returncode == 0 else None
            print(f"  czysty głos: {Path(s).name}, tło {'?' if szum[s] is None else f'{szum[s]:.0f}'} dB")
        cmd = ed.build_command(p, has_audio, pngs, out, karaoke=layer, typo=typo, maska=maska, sdr=sdr, szum=szum)
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
    if len(p["clips"]) > 1:
        print(f"Cięcia sprawdzisz obrazem: krytyka.py ciecia {out} --projekt {film}")
    print(f"MEDIA:{out}")
    return 0


# ---------------------------------------------------------------- film z kodu → projekt edytora (poziom 1)

Z_KODU_LUFS = -14.0          # suma dźwięków projektu: głośność platform (qa_wideo), limiter eksportu trzyma szczyt
NAZWY_SCIEZEK = {"glos": "Głos", "efekty": "Efekty", "muzyka": "Muzyka"}      # kolejność = kolejność na osi
PL_ASCII = str.maketrans("ąćęłńóśźż", "acelnoszz")   # nazwa pliku ścieżki z nazwy („Tło” → tlo.wav)


def sciezki_dir(film: Path) -> Path:
    """Katalog czystego obrazu i dźwięków projektu filmu z kodu: projekt nie zależy od plików roboczych silnika."""
    return film.with_name(f"{film.stem}-sciezki")


def kanon(x):
    """Liczby w jednej postaci: edytor HQ zapisuje 1.0 jako 1, a samo otwarcie projektu to jeszcze nie edycja."""
    if isinstance(x, bool) or not isinstance(x, (int, float, list, dict)):
        return x
    if isinstance(x, (int, float)):
        return round(float(x), 4)
    return [kanon(v) for v in x] if isinstance(x, list) else {k: kanon(v) for k, v in x.items()}


def podpis(proj: dict, kanoniczny: bool = True) -> str:
    """Odcisk treści projektu (kadr, klipy, napisy, audio): po nim poznajemy, czy ktoś edytował film w HQ."""
    import hashlib
    tresc = {k: proj.get(k) for k in ("canvas", "clips", "texts", "audio")}
    return hashlib.sha1(json.dumps(kanon(tresc) if kanoniczny else tresc, sort_keys=True, ensure_ascii=False)
                        .encode()).hexdigest()[:16]


def ciecia_z(spec: str | None, dur: float) -> list[float]:
    """--ciecia: „5.4,9.6”, lista liczb w JSON, events.json lemo (zdarzenia `cut`) albo os_czasu.json z film.py
    narracja (początki ujęć). Cięcia bliżej niż 0,1 s od brzegu filmu odpadają."""
    if not spec:
        return []
    p = Path(spec)
    if p.is_file():
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("ujecia"), list):
            t = [float(u["start"]) for u in d["ujecia"][1:] if isinstance(u, dict) and "start" in u]
        else:
            xs = d.get("ev") if isinstance(d, dict) else d
            t = [float(x) if isinstance(x, (int, float)) else float(x["t"]) for x in xs or []
                 if isinstance(x, (int, float)) or (isinstance(x, dict) and x.get("type") == "cut" and "t" in x)]
    else:
        try:
            t = [float(x) for x in spec.replace(";", ",").split(",") if x.strip()]
        except ValueError:
            raise SystemExit(f"--ciecia: liczby po przecinku albo plik JSON, nie {spec!r}")
    return sorted({round(x, 3) for x in t if MIN_CZESC <= x <= dur - MIN_CZESC})


def slowa_z_pliku(path: Path) -> list[list]:
    """Słowa z czasem [[start, end, tekst, podział]]: film.py narracja / lektor ([{start, end, text, podzial}]),
    analiza mowy edytora ({"words": [[start, end, tekst]]}) albo sama lista [[start, end, tekst]]."""
    d = json.loads(path.read_text(encoding="utf-8"))
    xs = d.get("words") if isinstance(d, dict) else d
    out = []
    for w in xs or []:
        if isinstance(w, dict) and str(w.get("text") or w.get("word") or "").strip():
            out.append([float(w["start"]), float(w["end"]), str(w.get("text") or w.get("word")).strip(), bool(w.get("podzial"))])
        elif isinstance(w, (list, tuple)) and len(w) >= 3 and str(w[2]).strip():
            out.append([float(w[0]), float(w[1]), str(w[2]).strip(), False])
    if not out:
        raise SystemExit(f"{path}: brak słów z czasem")
    return sorted(out, key=lambda w: w[0])


def linie_napisow(srt: Path | None, slowa: list[list] | None, pion_: bool, karaoke: bool) -> list[dict]:
    """Linie napisów: z SRT (podział taki jak w filmie) albo ze słów tym samym podziałem co napisy wypalane
    (wideo_lib.chunk_words: karaoke po 3 słowa, zwykłe do 7, polskie sierotki). Ze słowami każda linia ma czasy słów
    (karaoke w edytorze), o ile liczba słów się zgadza."""
    import wideo_lib as wl
    if srt:
        lines = [{"start": k["start"], "end": k["end"], "text": " ".join(str(k["text"]).split())}
                 for k in ed.parse_srt(srt.read_text(encoding="utf-8", errors="replace"))]
        for ln in lines if slowa else []:
            ws = [w for w in slowa if ln["start"] - 0.05 <= (w[0] + w[1]) / 2 <= ln["end"] + 0.05]
            if ws and len(ws) == len(ln["text"].split()):
                ln["words"] = [[round(max(0.0, w[0] - ln["start"]), 3), round(max(0.0, w[1] - ln["start"]), 3), t]
                               for w, t in zip(ws, ln["text"].split())]
        return lines
    znaki = 18 if pion_ else 30
    grupy = wl.chunk_words([wl.Word(w[0], w[1], w[2], w[3]) for w in slowa or []],
                           3 if karaoke else 7, znaki if karaoke else znaki * 2)
    return [{"start": g[0].start, "end": g[-1].end, "text": " ".join(w.text for w in g),
             "words": [[round(w.start - g[0].start, 3), round(w.end - g[0].start, 3), w.text] for w in g]} for g in grupy]


def _ebur(args: list[str]) -> tuple[float | None, float | None]:
    """(LUFS, szczyt próbki dBFS) z podsumowania ebur128 polecenia ffmpeg."""
    r = subprocess.run(args, capture_output=True, text=True)
    s = r.stderr.split("Summary:")[-1]
    m, pk = re.search(r"I:\s+(-?[\d.]+) LUFS", s), re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", s)
    return (float(m.group(1)) if m and r.returncode == 0 else None,
            float(pk.group(1)) if pk and pk.group(1) != "-inf" else None)


def kopia_dzwieku(src: Path, dest: Path, dl: float | None = None, wzmocnienie: float = 1.0) -> float:
    """Ścieżka dźwięku (najwyżej `dl` s) → WAV 48 kHz stereo 16 bit w katalogu ścieżek, ze wzmocnieniem wpisanym
    w plik (element audio zostaje na 0 dB). Gdy szczyt wyszedłby ponad −0,1 dBFS (miks silnika bywa w float ponad
    0 dBFS przed jego limiterem), plik dostaje tylko tyle, ile się mieści; zwraca głośność elementu na resztę."""
    ff = ed.tools()["ffmpeg"] or "ffmpeg"
    _lufs, szczyt = _ebur([ff, "-nostdin", "-hide_banner", "-nostats", "-i", str(src), "-map", "0:a:0",
                           *(["-t", ed._f(dl)] if dl else []), "-af", "ebur128=peak=sample", "-f", "null", "-"])
    k = min(wzmocnienie, 10 ** ((-0.1 - szczyt) / 20)) if szczyt is not None else wzmocnienie
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:a:0",
                        *(["-t", ed._f(dl)] if dl else []),
                        *(["-af", f"volume={k:.6f}"] if abs(k - 1) > 1e-4 else []), "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
                        str(dest)], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"nie umiem skopiować dźwięku {src}: {r.stderr.strip()[-300:]}")
    return wzmocnienie / k


def glosnosc_sumy(audio: list[dict], dur: float) -> float | None:
    """LUFS sumy elementów audio tak, jak zmiesza je eksport (głośność, miejsce na osi, bez limitera)."""
    ff = ed.tools()["ffmpeg"] or "ffmpeg"
    args, graph, mix = [ff, "-nostdin", "-hide_banner", "-nostats"], [], ""
    for k, m in enumerate(audio):
        args += ["-ss", ed._f(m["in"]), "-t", ed._f(m["out"] - m["in"]), "-i", str(m["src"])]
        ms = int(round(m["start"] * 1000))
        graph.append(f"[{k}:a]volume={ed._f(m['volume'])},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                     f"adelay={ms}|{ms}[m{k}]")
        mix += f"[m{k}]"
    graph.append(f"{mix}amix=inputs={len(audio)}:duration=longest:normalize=0,apad=whole_dur={ed._f(dur)},"
                 f"atrim=end={ed._f(dur)},ebur128=peak=sample[o]")
    return _ebur([*args, "-filter_complex", ";".join(graph), "-map", "[o]", "-f", "null", "-"])[0]


def _plik_od(spec: str) -> tuple[Path, float]:
    """„plik.wav” albo „plik.wav@1.5” (od której sekundy filmu gra)."""
    plik, od = spec, 0.0
    if "@" in spec:
        a, b = spec.rsplit("@", 1)
        try:
            plik, od = a, float(b)
        except ValueError:
            pass
    p = Path(plik).resolve()
    if not p.is_file() or ed.media_kind(p) not in ("audio", "video"):
        raise SystemExit(f"nie ma pliku dźwięku: {p}")
    return p, max(0.0, od)


def edytowany(film: Path) -> bool:
    """Projekt filmu z kodu zmieniony po zbudowaniu (np. w edytorze HQ): z-kodu nie nadpisze go po cichu."""
    pp = ed.project_path(film)
    if not pp.is_file():
        return False
    try:
        proj = json.loads(pp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    zk = proj.get("zKodu") or proj.get("clipmaker")
    return not zk or zk.get("podpis") != podpis(proj)


def _od(spec: str) -> tuple[str, float | None]:
    """„plik” albo „plik@1.5” → (plik, od); bez liczby po @ całość to nazwa pliku."""
    if "@" in spec:
        x, y = spec.rsplit("@", 1)
        try:
            return x, max(0.0, float(y))
        except ValueError:
            pass
    return spec, None


def z_planu_muzyki(path: Path) -> tuple[dict, float | None]:
    """Warstwy z planu `muzyka.py zrob` ("sciezki": {muzyka, efekty, glos}, każda od 0 s) i chwila lektora w filmie."""
    try:
        j = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"--z-muzyki: nie umiem odczytać {path}: {exc}")
    sc = {k: v for k, v in (j.get("sciezki") or {}).items() if k in NAZWY_SCIEZEK and v}
    if not sc:
        raise SystemExit(f"--z-muzyki: {path.name} nie ma ścieżek (zrób muzykę od nowa: muzyka.py zrob zapisuje je sama)")
    baza = path.parent
    sc = {k: str((baza / v) if not Path(v).is_absolute() else Path(v)) for k, v in sc.items()}
    od = (j.get("lektor") or {}).get("od")
    return sc, (float(od) if "glos" in sc and od is not None else None)


def projekt_z_kodu(film: Path, a) -> dict:
    """Projekt edytora z części filmu z kodu: czysty obraz (bez dźwięku, pocięty na ujęcia), głos i efekty przypięte
    do obrazu, muzyka osobno, napisy jako tekst. Kopie w <film>-sciezki/, głośność sumy do --lufs."""
    obraz = Path(a.obraz).resolve()
    info = ed.probe(obraz)
    if not info.get("ok") or not info.get("duration"):
        raise SystemExit(f"nie mogę odczytać obrazu: {obraz}")
    dur = float(info["duration"])
    kat = sciezki_dir(film)
    kat.mkdir(parents=True, exist_ok=True)
    ff = ed.tools()["ffmpeg"] or "ffmpeg"
    cel = kat / f"obraz{obraz.suffix.lower()}"
    if obraz != cel:
        r = subprocess.run([ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(obraz), "-map", "0:v:0",
                            "-c:v", "copy", "-an", *(["-movflags", "+faststart"] if cel.suffix in (".mp4", ".mov", ".m4v") else []),
                            str(cel)], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"nie umiem skopiować obrazu: {r.stderr.strip()[-300:]}")
    w, h = ed.kadr_eksportu(even(info.get("w") or 1920), even(info.get("h") or 1080))
    proj = {"version": 1, "format": "orig",
            "canvas": {"w": w, "h": h, "fps": min(FPS, key=lambda f: abs(f - (info.get("fps") or 30)))},
            "clips": [], "texts": [], "audio": []}
    granice = [0.0, *ciecia_z(a.ciecia, dur), dur]
    for x, y in zip(granice, granice[1:]):
        proj["clips"].append({"id": new_id("c"), "src": str(cel), "kind": "video", "in": round(x, 3), "out": round(y, 3),
                              "speed": 1, "volume": 1, "muted": False, "fit": "contain"})
    zrodla = {"obraz": str(obraz)}
    specs = {rola: getattr(a, rola) for rola in NAZWY_SCIEZEK}
    glos_od = _od(a.glos)[1] if a.glos else None
    if getattr(a, "z_muzyki", None):
        z_muzyki, lektor_od = z_planu_muzyki(Path(a.z_muzyki).resolve())
        for rola, plik in z_muzyki.items():
            if not specs[rola]:
                specs[rola] = plik
                glos_od = lektor_od if rola == "glos" else glos_od
        zrodla["muzyka_plan"] = str(Path(a.z_muzyki).resolve())
    sciezki = [(rola, spec, rola != "muzyka", NAZWY_SCIEZEK[rola]) for rola, spec in specs.items() if spec]
    for spec in a.audio or []:
        nazwa, _, plik = spec.partition("=")
        if not plik:
            raise SystemExit(f"--audio: NAZWA=plik[@od], nie {spec!r}")
        plik_nazwa = re.sub(r"[^a-z0-9-]+", "-", nazwa.strip().lower().translate(PL_ASCII)).strip("-") or "dzwiek"
        sciezki.append((plik_nazwa, plik, True, nazwa.strip()))
    wejscia = []
    for rola, spec, przypiete, nazwa in sciezki:
        src, od = _plik_od(spec)
        if any(w[0] == rola for w in wejscia):
            raise SystemExit(f"dwie ścieżki o nazwie {rola}: daj inne NAZWA w --audio")
        dl = ed.probe(src).get("duration") or 0.0
        out = round(min(dl, dur - od), 3)
        if out < ed.MIN_CLIP:
            raise SystemExit(f"{src.name}: dźwięk zaczyna się za końcem filmu albo jest pusty")
        wejscia.append((rola, src, od, out, przypiete, nazwa))
    # głośność sumy liczona z oryginałów, a wzmocnienie do --lufs trafia w kopie (elementy zostają na 0 dB)
    lufs = (glosnosc_sumy([{"src": str(src), "start": od, "in": 0.0, "out": out, "volume": 1.0}
                           for _r, src, od, out, _p, _n in wejscia], dur) if wejscia and a.lufs is not None else None)
    g = 10 ** ((a.lufs - lufs) / 20) if lufs is not None else 1.0
    for rola, src, od, out, przypiete, nazwa in wejscia:
        dest = kat / f"{rola}.wav"
        vol = kopia_dzwieku(src, dest, out, g)
        if vol > 2.0:
            print(f"  ⚠ {nazwa}: za cichy nawet przy 200% głośności; całość będzie cichsza niż {a.lufs:g} LUFS")
        proj["audio"].append({"id": new_id("a"), "src": str(dest), "start": round(od, 3), "in": 0.0, "out": out,
                              "volume": round(min(2.0, vol), 3), "label": nazwa, **({"linked": True} if przypiete else {})})
        zrodla[rola] = str(src)
    pion_ = h > w
    if a.napisy or a.slowa:
        slowa = None
        if a.slowa:
            plik_slow, od_slow = _od(a.slowa)
            przes = od_slow if od_slow is not None else (glos_od or 0.0)
            slowa = [[w[0] + przes, w[1] + przes, *w[2:]] for w in slowa_z_pliku(Path(plik_slow))]
        look = {**CAP_DEFAULT, **pion(proj)}
        for arg, key in (("styl", "style"), ("kolor", "color"), ("tlo", "bg"), ("rozmiar", "size"), ("y", "y")):
            if getattr(a, arg) is not None:
                look[key] = getattr(a, arg)
        if a.kroj is not None:
            look["font"] = kroj_z_nazwy(a.kroj)
        if a.karaoke is not None:
            look["hl"] = a.karaoke or KARAOKE_HL
        for ln in linie_napisow(Path(a.napisy) if a.napisy else None, slowa, pion_, a.karaoke is not None):
            if ln["start"] >= dur - ed.MIN_CLIP:
                continue
            proj["texts"].append({**look, "id": new_id("t"), "cap": True, "start": round(ln["start"], 3),
                                  "end": round(min(ln["end"], dur), 3), "text": ln["text"],
                                  **({"words": ln["words"]} if look.get("hl") and ln.get("words") else {})})
        zrodla["napisy"] = str(Path(a.napisy or _od(a.slowa)[0]).resolve())
    proj["zKodu"] = {"zrodla": zrodla, "sciezki": str(kat), "ciecia": granice[1:-1],
                     **({"lufs_przed": lufs, "lufs": a.lufs} if lufs is not None else {})}
    try:
        ed.normalize(proj, resolve)                    # ta sama walidacja co eksport z edytora
    except ed.ProjectError as exc:
        raise SystemExit(f"projekt nie przechodzi walidacji: {exc}")
    return proj


def cmd_z_kodu(film: Path, a) -> int:
    if film.suffix.lower() not in ed.VIDEO_EXT:
        raise SystemExit(f"film to plik wideo (np. {film.stem}.mp4), nie {film.name}")
    if edytowany(film) and not a.nadpisz:
        raise SystemExit(f"{film.name}: projekt zmieniono po zbudowaniu (np. w edytorze HQ). Poprawiaj go poleceniami "
                         "projekt.py albo zbuduj z --nadpisz, jeśli te zmiany mają zniknąć")
    proj = projekt_z_kodu(film, a)
    zk = proj["zKodu"]
    zk["podpis"] = podpis(proj)
    save(film, proj)
    caps = sum(1 for t in proj["texts"] if t.get("cap"))
    print(f"Projekt: {ed.project_path(film)}")
    print(f"  obraz {total(proj):.2f} s w {len(proj['clips'])} ujęciach · "
          + (", ".join(f"{m['label']} {m['volume']:.2f}{' (przypięte)' if m.get('linked') else ''}" for m in proj["audio"]) or "bez dźwięku")
          + f" · {caps} napisów" + (f" · suma {zk['lufs_przed']:.1f} → {zk['lufs']:g} LUFS" if zk.get("lufs_przed") is not None else ""))
    print(f"  ścieżki: {zk['sciezki']}/", flush=True)            # przed renderem: przeglądarka nie powtórzy bufora
    if a.render:
        if cmd_render(film, argparse.Namespace(out=str(film))) != 0:
            raise SystemExit("render projektu nie wyszedł")
    else:
        print(f"Film = render projektu: projekt.py render {film} --out {film}")
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
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--przypnij", action="store_true", help="audio przypięte do obrazu: przy cięciu klipów idzie z nimi")
    g.add_argument("--odlacz", action="store_true", help="audio odłączone od obrazu: przy cięciu tylko się przesuwa")
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
    sp = film_cmd("kolor", cmd_kolor, "korekcja koloru klipu (styl, suwaki −100…100, Auto z pomiaru klatek)")
    sp.add_argument("id", nargs="?", help="klip (z `pokaz`)")
    sp.add_argument("--wszystkie", action="store_true", help="każdy klip (jeden kolor na film)")
    sp.add_argument("--styl", choices=[*ed.KOLOR_STYLE, "brak"], help="styl; ustawia jego suwaki (potem można je zmienić)")
    for n in KOLOR_ARGI:
        sp.add_argument(f"--{n}", type=int, help="−100…100 (0 = bez zmiany)")
    sp.add_argument("--auto", action="store_true", help="delikatna korekta z pomiaru klatek (ciemne jaśniej, płaskie z kontrastem)")
    sp.add_argument("--usun", action="store_true", help="bez korekty koloru")
    sp.add_argument("--podglad", action="store_true", help="klatka przed | po obok filmu (do vision_analyze)")
    sp = film_cmd("glos", cmd_glos, "czysty głos klipu albo audio: lekki, sredni, mocny albo auto z tła nagrania")
    sp.add_argument("id", nargs="?", help="klip albo audio (z `pokaz`)")
    sp.add_argument("--wszystkie", action="store_true", help="każdy klip wideo z dźwiękiem")
    sp.add_argument("--poziom", choices=["auto", *ed.GLOS, "brak"], default="auto",
                    help="auto = z tła nagrania (cicho lekki, pokój sredni, głośne tło mocny); brak = wyłącz")
    sp.add_argument("--probka", action="store_true", help="8 s po czyszczeniu obok filmu (.mp3) do odsłuchu")
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
    sp = sub.add_parser("dzwieki", help="biblioteka dźwięków CC0 (efekty i podkłady)")
    sp.add_argument("--kategoria", help="np. przejscia, reakcje, pieniadze, uderzenia, akcja, muzyka")
    sp.add_argument("--szukaj", help="fragment nazwy (po polsku albo angielsku)")
    sp.add_argument("--muzyka", action="store_true", help="tylko podkłady muzyczne")
    sp.add_argument("--rola", help="narastanie, uderzenie, blysk, ruch, przejscie, pojawienie, klik, pisanie")
    sp.set_defaults(fn=cmd_dzwieki, film=None)
    sp = film_cmd("dodaj-dzwiek", cmd_dodaj_dzwiek, "efekt albo podkład z biblioteki")
    sp.add_argument("id", help="id z `dzwieki`")
    gr = sp.add_mutually_exclusive_group()
    gr.add_argument("--start", type=float, default=0.0, help="od której sekundy osi gra")
    gr.add_argument("--na", type=float, help="chwila osi, w którą ma trafić szczyt efektu (start = T − szczyt)")
    sp.add_argument("--glosnosc", type=float, help="0–2 (domyślnie 1, podkład 0.3)")
    sp.add_argument("--narastanie", type=float, help="s")
    sp.add_argument("--wyciszanie", type=float, help="s")
    sp = film_cmd("zdanie", cmd_zdanie, "zdanie dźwiękowe: narastanie → uderzenie → błysk na jedną chwilę")
    sp.add_argument("--na", type=float, required=True, help="chwila uderzenia (s osi): stempel, logo, lądowanie")
    sp.add_argument("--przed", help="narastanie (domyślnie pierwsze z roli; „brak” = bez)")
    sp.add_argument("--uderzenie", help="uderzenie (domyślnie pierwsze z roli)")
    sp.add_argument("--po", help="błysk po uderzeniu (domyślnie pierwszy z roli; „brak” = bez)")
    sp.add_argument("--rozbieg", type=float, default=ZDANIE_ROZBIEG, help="ile s narastania przed uderzeniem")
    sp.add_argument("--odstep", type=float, default=ZDANIE_ODSTEP, help="ile s po uderzeniu błysk")
    sp.add_argument("--glosnosc", type=float, default=1.0, help="mnożnik głośności całego zdania")
    sp = film_cmd("seria", cmd_seria, "seria elementów: dwa efekty na zmianę, coraz ciszej")
    sp.add_argument("--czasy", required=True, help="chwile elementów (s osi) po przecinku")
    sp.add_argument("--id", help="pierwszy efekt (domyślnie pop)")
    sp.add_argument("--id2", help="drugi efekt na zmianę (domyślnie następny z tej samej roli)")
    sp.add_argument("--glosnosc-od", type=float, default=SERIA_GLOSNOSC[0])
    sp.add_argument("--glosnosc-do", type=float, default=SERIA_GLOSNOSC[1])
    sp = sub.add_parser("slychac", help="czy efekty słychać pod głosem i muzyką (projekt albo cues.json filmu z kodu)")
    sp.add_argument("film", nargs="?", help="film projektu (obok <film>.edycja.json); z --cues: obraz (długość)")
    sp.add_argument("--cues", help="film z kodu: cues.json dla sound.mjs")
    sp.add_argument("--bed", help="film z kodu: podkład z głosem i muzyką (ten sam co --bed sound.mjs)")
    sp.add_argument("--bed-vol", type=float, default=0.5)
    sp.add_argument("--bed-at", type=float, default=0.0)
    sp.add_argument("--sound", help="ścieżka sound.mjs (domyślnie z narzedzia.py env animacja)")
    sp.add_argument("--json", help="zapisz raport do pliku JSON")
    sp.set_defaults(fn=cmd_slychac)
    sp = film_cmd("wyodrebnij", cmd_wyodrebnij, "dźwięk klipu albo innego filmu jako osobne audio")
    sp.add_argument("id", nargs="?", help="klip z osi (z `pokaz`): dźwięk zostaje w tym samym miejscu, klip wyciszony")
    sp.add_argument("--plik", help="inny film: jego dźwięk jako audio")
    sp.add_argument("--start", type=float, help="z --plik: od której sekundy osi (domyślnie 0)")
    sp = film_cmd("lektor", cmd_lektor, "lektor Edge TTS jako audio")
    sp.add_argument("tekst")
    sp.add_argument("--start", type=float, default=0.0)
    sp.add_argument("--glos", choices=ed.GLOSY, help="domyślnie pl-PL-MarekNeural")
    sp.add_argument("--tempo", help="np. +5% albo -10% (od −50% do +50%)")
    sp.add_argument("--narastanie", type=float, help="s")
    sp.add_argument("--wyciszanie", type=float, help="s")
    film_cmd("usun", cmd_usun, "usuń element po id").add_argument("id")
    sp = film_cmd("uwaga", cmd_uwaga, "zamknij uwagę z osi edytora")
    sp.add_argument("id")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--zrobione", help="co zmieniłeś (zobaczy to właściciel w edytorze)")
    g.add_argument("--odrzuc", help="dlaczego nie (np. kolizja z inną uwagą, wymaga decyzji)")
    sp = film_cmd("z-kodu", cmd_z_kodu, "film z kodu jako projekt edytora: czysty obraz, osobne dźwięki, napisy")
    sp.add_argument("--obraz", required=True, help="czysty obraz filmu: bez wypalonych napisów (dźwięk pliku pomijany)")
    sp.add_argument("--ciecia", help="cięcia ujęć: „5.4,9.6”, events.json lemo albo os_czasu.json (klipy na osi)")
    sp.add_argument("--glos", help="lektor: plik[@od] (przypięty do obrazu)")
    sp.add_argument("--efekty", help="efekty i foley: plik[@od] (przypięte do obrazu)")
    sp.add_argument("--muzyka", help="muzyka: plik[@od] (osobno: przy cięciu gra dalej)")
    sp.add_argument("--z-muzyki", help="plan muzyka.py zrob (<wynik>.muzyka.json): muzyka, efekty i głos z jego ścieżek")
    sp.add_argument("--audio", action="append", help="inna ścieżka przypięta do obrazu: NAZWA=plik[@od] (np. Tło=room.wav)")
    sp.add_argument("--napisy", help="napisy z SRT (podział linii jak w filmie)")
    sp.add_argument("--slowa", help="słowa z czasem (film.py narracja: lektor.slowa.json[@od]): napisy albo karaoke do SRT; "
                                    "bez @od przesunięte jak głos")
    sp.add_argument("--karaoke", nargs="?", const="", help="podświetlenie słowa (domyślnie #FFE14D)")
    sp.add_argument("--kroj", help="krój napisów z listy edytora (np. Caveat, Kanit)")
    sp.add_argument("--styl", choices=["shadow", "box", "outline", "plain"], help="wygląd napisów")
    sp.add_argument("--kolor", help="kolor tekstu napisów (#RRGGBB)")
    sp.add_argument("--tlo", help="kolor tła albo obrysu napisów (#RRGGBB)")
    sp.add_argument("--rozmiar", type=float, help="wielkość napisów (domyślnie 58; przy 1080 px krótszego boku)")
    sp.add_argument("--y", type=float, help="położenie napisów w pionie (0 góra – 1 dół)")
    sp.add_argument("--lufs", type=float, default=Z_KODU_LUFS, help="głośność sumy dźwięków (domyślnie −14)")
    sp.add_argument("--nadpisz", action="store_true", help="nadpisz projekt zmieniony w edytorze")
    sp.add_argument("--render", action="store_true", help="od razu złóż film z projektu (film = render projektu)")
    film_cmd("sprawdz", cmd_sprawdz, "walidacja projektu")
    film_cmd("render", cmd_render, "złóż film (jak „Eksportuj”)").add_argument("--out")
    a = ap.parse_args(argv)
    if a.film is None:
        return a.fn(None, a)
    film = Path(a.film).resolve()
    if not film.is_file() and not (a.cmd == "z-kodu" and film.parent.is_dir()):   # z-kodu: film powstaje z projektu
        raise SystemExit(f"nie ma filmu: {film}")
    return a.fn(film, a)


if __name__ == "__main__":
    sys.exit(main())
