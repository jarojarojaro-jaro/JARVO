#!/usr/bin/env python3
"""Projekt montażu z edytora HQ: Wideograf pracuje na tym samym projekcie co użytkownik.

Projekt to `<film>.edycja.json` obok filmu (zapisuje go edytor HQ). Zmieniasz go tymi poleceniami
(albo ostrożnie edytując JSON), a `render` składa film tym samym silnikiem co przycisk „Eksportuj”
w edytorze. Użytkownik po otwarciu edytora widzi Twoje zmiany osobno i może je dalej poprawiać.

    projekt.py pokaz <film>                        # co jest na osi (klipy, napisy, audio, długość)
    projekt.py dodaj-audio <film> <plik> [--start S] [--od S] [--do S] [--glosnosc 0.8] [--wycisz-film]
    projekt.py dodaj-tekst <film> "tekst" --start S --koniec S [--styl shadow|box|outline|plain]
                                           [--y 0.78] [--rozmiar 72] [--kolor #FFFFFF] [--tlo #000000]
    projekt.py dodaj-klip <film> <plik> [--od S] [--do S] [--tempo 1] [--pozycja N] [--wypelnij --fx X --fy Y --zoom Z]
    projekt.py kadr <film> <id> [--wypelnij|--dopasuj] [--fx 0.4] [--fy 0.35] [--zoom 1.15]   # kadr klipu
    projekt.py napisy <film> [--srt plik.srt] [--karaoke [#FFE14D]]   # napisy ze słów (<źródło>.mowa.json) albo SRT
    projekt.py usun <film> <id>                    # usuń klip / tekst / audio o danym id (z `pokaz`)
    projekt.py uwaga <film> <id> (--zrobione "co zmieniłem" | --odrzuc "dlaczego")   # zamknij uwagę z osi edytora
    projekt.py sprawdz <film>                      # walidacja jak przy eksporcie
    projekt.py render <film> [--out plik.mp4]      # nowa wersja obok oryginału, na końcu linia MEDIA:

Czas S w sekundach osi (po cięciach i zmianach tempa), chyba że opis mówi „źródła” (--od/--do).
Nic nie nadpisuje oryginału: render zapisuje film-edycja.mp4, film-edycja-2.mp4…

Uwagi (`notes` w projekcie) zostawia właściciel w edytorze HQ: prośba przypięta do chwili osi, często z kadrem
(obraz w inboxie, oglądasz go przez vision_analyze). Każdą zamykasz `uwaga … --zrobione` albo `--odrzuc` z powodem;
edytor pokazuje je wtedy jako ✓ z Twoim opisem. `render` ostrzega, gdy zostały otwarte.
"""

from __future__ import annotations

import argparse
import json
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
TEXT_DEFAULT = {"x": 0.5, "y": 0.78, "size": 72, "color": "#FFFFFF", "bg": "#000000", "style": "shadow",
                "font": "system-ui, 'Segoe UI', Roboto, sans-serif", "bold": True, "align": "center", "maxw": 0.86}
CAP_DEFAULT = {**TEXT_DEFAULT, "y": 0.84, "size": 58, "style": "outline", "maxw": 0.84,
               "font": "'Bricolage Grotesque', system-ui, sans-serif"}
FPS = (24, 25, 30, 50, 60)
KARAOKE_HL = "#FFE14D"   # kolor aktywnego słowa (jak ED_HL w edytorze)


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
    return {"version": 1, "format": "orig",
            "canvas": {"w": even(info.get("w") or 1920), "h": even(info.get("h") or 1080), "fps": min(FPS, key=lambda f: abs(f - fps))},
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
    for c, s, e in layout(proj["clips"]):
        extra = "".join([f" · tempo {c.get('speed', 1)}×" if c.get("speed", 1) != 1 else "", " · wyciszony" if c.get("muted") else "",
                         f" · głośność {c.get('volume', 1):.2f}" if c.get("volume", 1) != 1 else ""])
        print(f"  [{c.get('id')}] {s:6.2f}–{e:6.2f}  {Path(c['src']).name} (źródło {c['in']:.2f}–{c['out']:.2f}){extra}")
    print("Napisy i teksty:" if proj.get("texts") else "Napisy i teksty: brak")
    for x in proj.get("texts") or []:
        print(f"  [{x.get('id')}] {x['start']:6.2f}–{x['end']:6.2f}  {'napis' if x.get('cap') else 'tekst'}: {x.get('text', '')!r}")
    print("Audio:" if proj.get("audio") else "Audio: brak")
    for m in proj.get("audio") or []:
        print(f"  [{m.get('id')}] od {m['start']:6.2f} przez {m['out'] - m['in']:.2f} s  {Path(m['src']).name} · głośność {m.get('volume', 1):.2f}")
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
            "volume": max(0.0, min(2.0, a.glosnosc))}
    proj.setdefault("audio", []).append(item)
    if a.wycisz_film:
        for c in proj["clips"]:
            c["muted"] = True
    save(film, proj)
    print(f"Dodano audio [{item['id']}] {src.name} od {item['start']:.2f} s ({do - od:.2f} s)")
    return 0


def cmd_dodaj_tekst(film: Path, a) -> int:
    proj = load(film)
    t = total(proj)
    if not (0 <= a.start < a.koniec) or a.start >= t:
        raise SystemExit(f"zły czas napisu (film ma {t:.2f} s)")
    base = CAP_DEFAULT if a.napis else TEXT_DEFAULT
    x = {**base, "id": new_id("t"), "text": a.tekst, "start": a.start, "end": min(a.koniec, t)}
    for k, v in (("style", a.styl), ("y", a.y), ("size", a.rozmiar), ("color", a.kolor), ("bg", a.tlo)):
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
    dur = 3.0 if kind == "image" else (ed.probe(src).get("duration") or 3.0)
    od = a.od or 0.0
    do = a.do if a.do is not None else (od + dur if kind == "image" else dur)
    c = {"id": new_id("c"), "src": str(src), "kind": kind, "in": od, "out": do, "speed": 1 if kind == "image" else a.tempo,
         "volume": 1, "muted": False, "fit": "cover" if a.wypelnij else "contain"}
    c.update(kadr_z_arg(a))
    pos = len(proj["clips"]) if a.pozycja is None else max(0, min(len(proj["clips"]), a.pozycja))
    clips = list(proj["clips"])
    clips.insert(pos, c)
    save(film, ed.remap_times(proj, {**proj, "clips": clips}))   # wstawiony w środek: reszta osi odsuwa się
    print(f"Dodano klip [{c['id']}] {src.name} na pozycji {pos} ({(do - od) / c['speed']:.2f} s)")
    return 0


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
    if a.wypelnij or a.dopasuj:
        c["fit"] = "cover" if a.wypelnij else "contain"
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
    proj["texts"] = [x for x in proj.get("texts") or [] if not x.get("cap")] + [
        {**CAP_DEFAULT, **look, "id": new_id("t"), "cap": True, "start": k["start"], "end": min(k["end"], t), "text": k["text"],
         **({"words": k["words"]} if k.get("words") else {})}
        for k in lines if k["start"] < t]
    save(film, proj)
    print(f"Napisy: {sum(1 for x in proj['texts'] if x.get('cap'))} linii")
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


def text_pngs(texts: list[dict], W: int, H: int, out_dir: Path,
              hi: list[int] | None = None) -> list[Path]:
    """Każdy napis → PNG W×H, rysowany TĄ SAMĄ funkcją co w edytorze (44-napisy.js) w przeglądarce bez okna.
    `hi[k]` ≥ 0: napis karaoke z aktywnym słowem o tym numerze (jeden obraz na słowo)."""
    if not texts:
        return []
    hi = hi or [-1] * len(texts)
    if NAPISY_JS is None:
        raise SystemExit("brak edytor_napisy.js obok skryptu (przebuduj profil)")
    ensure_playwright()
    from playwright.sync_api import sync_playwright
    try:
        import narzedzia as nz
        exe = nz.headless_shell()
    except Exception:  # noqa: BLE001 - poza obrazem floty: domyślna przeglądarka playwright
        exe = None
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        page = browser.new_page()
        page.set_content("<!doctype html><meta charset=utf-8><body></body>")
        try:   # te same kroje co w HQ; bez sieci zostają systemowe
            page.add_style_tag(url="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=JetBrains+Mono:wght@400;600&display=swap")
        except Exception:  # noqa: BLE001
            pass
        page.add_script_tag(content=NAPISY_JS.read_text(encoding="utf-8"))
        for i, t in enumerate(texts):
            data = page.evaluate("""async ([t, W, H, hi]) => {
                try { await document.fonts.load(textFont(t, H, W).font); } catch (_) {}
                const c = document.createElement("canvas"); c.width = W; c.height = H;
                drawText(c.getContext("2d"), t, W, H, hi);
                return c.toDataURL("image/png");
            }""", [t, W, H, hi[i]])
            import base64
            dest = out_dir / f"napis-{i}{'' if hi[i] < 0 else f'-slowo-{hi[i]}'}.png"
            dest.write_bytes(base64.b64decode(data.split(",", 1)[1]))
            paths.append(dest)
        browser.close()
    return paths


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
        # jedno uruchomienie przeglądarki: zwykłe obrazy napisów, potem obraz na każde słowo napisów karaoke
        jobs = [(t, -1) for t in kept] + [(texts[x["i"]], j) for x in p["texts"] if x.get("kara")
                                          for j in range(len(texts[x["i"]]["words"]))]
        allp = text_pngs([t for t, _ in jobs], W, H, Path(tmp), [j for _, j in jobs])
        pngs, rest = allp[:len(kept)], iter(allp[len(kept):])
        kara = {x["i"]: [next(rest) for _ in texts[x["i"]]["words"]] for x in p["texts"] if x.get("kara")}
        layer = ed.karaoke_concat(p, kara, ed.blank_png(Path(tmp) / "pusty.png", W, H), Path(tmp) / "karaoke.ffconcat") if kara else None
        cmd = ed.build_command(p, has_audio, pngs, out, karaoke=layer)
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
    sp = film_cmd("dodaj-tekst", cmd_dodaj_tekst, "tekst albo napis na obrazie")
    sp.add_argument("tekst")
    sp.add_argument("--start", type=float, required=True)
    sp.add_argument("--koniec", type=float, required=True)
    sp.add_argument("--styl", choices=["shadow", "box", "outline", "plain"])
    sp.add_argument("--y", type=float, help="położenie w pionie 0–1 (0.84 = dół)")
    sp.add_argument("--rozmiar", type=float)
    sp.add_argument("--kolor")
    sp.add_argument("--tlo", help="kolor tła (styl box) albo obrysu (outline)")
    sp.add_argument("--napis", action="store_true", help="napis (wspólny styl napisów w edytorze)")
    sp = film_cmd("dodaj-klip", cmd_dodaj_klip, "klip albo plansza na ścieżce głównej")
    sp.add_argument("plik")
    sp.add_argument("--od", type=float)
    sp.add_argument("--do", type=float)
    sp.add_argument("--tempo", type=float, default=1.0)
    sp.add_argument("--pozycja", type=int, help="miejsce na ścieżce (0 = na początek; domyślnie na koniec)")

    def kadr_args(sp):
        sp.add_argument("--wypelnij", action="store_true", help="wypełnij kadr (fit=cover), np. pion z poziomego")
        sp.add_argument("--fx", type=float, help="punkt skupienia poziomo 0–1 (0.5 = środek, twarz mówcy z klatek)")
        sp.add_argument("--fy", type=float, help="punkt skupienia pionowo 0–1")
        sp.add_argument("--zoom", type=float, help="przybliżenie 1–3 (punch-in ok. 1.15)")
    kadr_args(sp)
    sp = film_cmd("kadr", cmd_kadr, "kadr klipu: wypełnij/dopasuj, punkt skupienia, przybliżenie")
    sp.add_argument("id")
    kadr_args(sp)
    sp.add_argument("--dopasuj", action="store_true", help="cały obraz z pasami (fit=contain)")
    sp = film_cmd("napisy", cmd_napisy, "napisy ze słów albo z SRT")
    sp.add_argument("--srt")
    sp.add_argument("--karaoke", nargs="?", const="", metavar="KOLOR",
                    help="aktywne słowo w kolorze (domyślnie żółty); tylko napisy ze słów, nie z SRT")
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
