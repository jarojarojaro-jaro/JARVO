#!/usr/bin/env python3
"""Krytyka reżyserska: narzędzia, którymi film ogląda się jak surowy motion director, nie dumny autor.

    python3 krytyka.py telefon film.mp4 [-o out/wideo/<film>/telefon.jpg]      # 1 kl./s w 360 px szer., siatka 5×N
    python3 krytyka.py pasek film.mp4 --t 4.2 [--klatek 12] [-o pasek.jpg]    # kolejne klatki wokół szybkiej akcji
    python3 krytyka.py martwe film.mp4 [--prog 2.5]                           # odcinki bez zmiany obrazu (martwy takt)
    python3 krytyka.py puls film.mp4 [--prog 3] [--min 1.5]                   # gdzie film ZWALNIA (mało nowego), pod retime.py
    python3 krytyka.py petla film.mp4 [-o petla.mp4]                          # szew pętli: ostatnia vs pierwsza klatka
    python3 krytyka.py ciecia film.mp4 [--projekt film.edycja.json | --czasy 2.4,5.1] [--slowa film.mowa.json]
                              [--okno 1.5] [--tylko 2,5] [-o katalog]          # obraz każdego cięcia: klatki, fala, słowa
    python3 krytyka.py determinizm anim.html --czasy 1.3,4.2 [--preset jarvo]  # ta sama klatka 2× = ten sam obraz
    python3 krytyka.py ocena kontrola.json                                    # czy runda spełnia pętlę (7 osi ≥ 8)

Wszystko działa na gotowym MP4 z dowolnego silnika (poza `determinizm`, który renderuje HTML przez html_wideo.py).
Obrazy oglądasz przez vision_analyze. Kod wyjścia: 0 = ok, 1 = znaleziony problem, 2 = złe wejście. --json dla maszyn.

`ciecia` (za browser-use/video-use, timeline_view, MIT): na jednym obrazie 4 klatki przed cięciem i 4 za nim, fala
dźwięku ±okno s z cieniem ciszy, słowa z czasem i czerwona linia cięcia. Do tego liczby: trzask (skok fali na cięciu),
słowo przecięte albo ucięte za ciasno (z projektem edytora: z analizy mowy źródeł), przeskok (ten sam kadr po obu
stronach). Cięcia bierze z projektu edytora (--projekt albo `<film>.edycja.json` obok filmu, jak przy rolkach
clipmakera: koniec każdego klipu), z --czasy (np. lista `ciecia` z montaz.py) albo sam znajduje zmiany ujęcia w obrazie.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import tempfile
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

OSIE = ["hook", "telefon", "ruch", "roznorodnosc", "kompozycja", "marka", "dzwiek"]


def ff(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([wl.need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)


def telefon(film: Path, out: Path) -> dict:
    dur = wl.duration(film)
    rows = max(1, -(-int(dur) // 5))
    r = ff(["-i", str(film), "-vf", f"fps=1,scale=360:-2,tile=5x{rows}:padding=6:color=0x202020", "-frames:v", "1", str(out)])
    if r.returncode:
        raise SystemExit(f"✗ ffmpeg: {r.stderr.strip()[:300]}")
    return {"arkusz": str(out), "klatek": int(dur), "pytanie": "czy każdy tekst da się przeczytać na tym rozmiarze?"}


def pasek(film: Path, t: float, n: int, out: Path) -> dict:
    fps = float(eval_fps(film))
    start = max(0.0, t - (n / 2) / fps)
    r = ff(["-ss", f"{start:.3f}", "-i", str(film), "-vf", f"scale=320:-2,tile={n}x1:padding=4:color=0x202020",
            "-frames:v", "1", str(out)])
    if r.returncode:
        raise SystemExit(f"✗ ffmpeg: {r.stderr.strip()[:300]}")
    return {"pasek": str(out), "od": round(start, 3), "klatek": n,
            "szukaj": "wyskoki (pop), nachodzący tekst, przejazd bez wyhamowania, zła strona ruchu"}


def eval_fps(film: Path) -> float:
    return float((wl.probe(film).get("video") or {}).get("fps") or 0) or 30.0


def roznice(film: Path, fps: float = 5.0) -> list[float]:
    """Średnia bezwzględna różnica kolejnych klatek (64×64, szarość), co 1/fps s."""
    r = subprocess.run([wl.need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(film), "-vf",
                        f"fps={fps},scale=64:64,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    raw = r.stdout
    k = 64 * 64
    frames = [raw[i:i + k] for i in range(0, len(raw) - k + 1, k)]
    return [sum(abs(a - b) for a, b in zip(frames[i - 1], frames[i])) / k for i in range(1, len(frames))]


def martwe(film: Path, prog: float, fps: float = 5.0) -> dict:
    d = roznice(film, fps)
    odc, start = [], None
    for i, v in enumerate(d + [99.0]):
        if v < 0.6:           # praktycznie ta sama klatka (poniżej szumu kompresji)
            start = i if start is None else start
        elif start is not None:
            dl = (i - start) / fps
            if dl >= prog:
                odc.append({"od": round(start / fps, 2), "do": round(i / fps, 2), "sek": round(dl, 2)})
            start = None
    # koniec filmu: celowy „hold” na logo do 2 s jest ok
    dur = len(d) / fps
    odc = [o for o in odc if not (o["do"] >= dur - 0.3 and o["sek"] <= 2.5)]
    return {"martwe": odc, "prog_s": prog, "ok": not odc}


def puls(film: Path, prog: float = 3.0, min_s: float = 1.5, fps: float = 5.0) -> dict:
    """Tempo informacji: martwe() łapie tylko zamrożony obraz, a tło z ruchem (cząsteczki, ziarno) nie jest „martwe”,
    choć nic nowego się nie dzieje. Tu liczy się średnia zmiana obrazu na sekundę; odcinki poniżej `prog` dłuższe
    niż `min_s` to miejsca do zagęszczenia (retime.py: bliżej kotwice, szybszy lektor)."""
    d = roznice(film, fps)
    n = int(len(d) / fps)
    sek = [sum(d[int(i * fps):int((i + 1) * fps)]) / max(1, len(d[int(i * fps):int((i + 1) * fps)])) for i in range(n)]
    wolne, start = [], None
    for i, v in enumerate(sek + [99.0]):
        if v < prog:
            start = i if start is None else start
        elif start is not None:
            if i - start >= min_s:
                wolne.append({"od": start, "do": i, "sek": i - start, "srednio": round(sum(sek[start:i]) / (i - start), 2)})
            start = None
    suma = sum(w["sek"] for w in wolne)
    return {"dlugosc_s": n, "wolne": wolne, "wolne_s": suma, "udzial_wolnych": round(suma / max(1, n), 2),
            "ok": suma / max(1, n) <= 0.25, "prog": prog, "min_s": min_s}


def petla(film: Path, out: Path | None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a.gray", Path(tmp) / "b.gray"
        ff(["-i", str(film), "-vf", "scale=96:96,format=gray", "-frames:v", "1", "-f", "rawvideo", str(a)])
        ff(["-sseof", "-0.2", "-i", str(film), "-vf", "scale=96:96,format=gray", "-update", "1", "-f", "rawvideo", str(b)])
        pa, pb = a.read_bytes(), b.read_bytes()
    diff = sum(abs(x - y) for x, y in zip(pa, pb)) / max(1, len(pa))
    wynik = {"roznica_szwu": round(diff, 2), "ok": diff < 4.0,
             "uwaga": "ostatnia klatka = pierwsza (także pozycja i prędkość kursora); różnica < 4 = szew niewidoczny"}
    if out:
        ff(["-stream_loop", "1", "-i", str(film), "-c", "copy", str(out)])
        wynik["podglad"] = str(out)
    return wynik


# ---------------------------------------------------------------- cięcia: obraz i liczby każdego cięcia gotowego filmu
SR = 48000
CISZA_DB = -35.0        # jak montaz.py cisza i „Mowa” w edytorze HQ
TRZASK = 3.0            # skok fali na cięciu ≥ 3× zwykłego kroku fali obok (i ≥ 5% skali) = słyszalny klik
ZAPAS_SLOWA = 0.04      # granica bliżej słowa niż 40 ms: może ucinać końcówkę (czasy słów z ASR mają ok. ±40 ms)
PRZESKOK = (2.0, 12.0)  # różnica klatek przed i za cięciem: poniżej = ten sam obraz, w zakresie = ten sam kadr z przeskokiem
KLATKA_W = 160


def pcm(film: Path) -> array:
    """Dźwięk filmu: mono 48 kHz, próbki 16 bit (pusta tablica, gdy filmu nie ma dźwięku)."""
    r = subprocess.run([wl.need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(film), "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "s16le", "-"], capture_output=True)
    a = array("h")
    a.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def db(a: array, t0: float, t1: float) -> float:
    i0, i1 = max(0, int(t0 * SR)), min(len(a), int(t1 * SR))
    if i1 <= i0:
        return -120.0
    return round(20 * math.log10(max(math.sqrt(sum(v * v for v in a[i0:i1]) / (i1 - i0)) / 32768, 1e-6)), 1)


def trzask(a: array, t: float, blisko: float = 0.02, okno: float = 1.0) -> dict:
    """Skok fali na cięciu (±blisko s) względem zwykłego kroku fali obok (99. centyl |Δ| w oknie bez cięcia).
    Klik to nagły skok w gładkiej fali; w ciszy liczy się sam skok (próg 5% skali)."""
    c, b, w = int(round(t * SR)), int(blisko * SR), int(okno * SR)
    lo, hi = max(1, c - w), min(len(a), c + w)
    if hi - lo < 8 * b or not lo <= c <= hi:
        return {"skok": 0.0, "krotnosc": 0.0, "trzask": False}
    skok = max(abs(a[i] - a[i - 1]) for i in range(max(lo, c - b), min(hi, c + b)))
    tlo = sorted(abs(a[i] - a[i - 1]) for i in range(lo, hi, 2) if abs(i - c) > 2 * b)
    p99 = tlo[int(len(tlo) * 0.99)] if tlo else 0
    k = skok / max(p99, 30)
    return {"skok": round(skok / 32768, 3), "krotnosc": round(k, 1), "trzask": k >= TRZASK and skok >= 0.05 * 32768}


def slowa_na_granicy(slowa: list, e: float, strona: str) -> list[dict]:
    """Słowa źródła przy granicy klipu (czas źródła e): granica w środku słowa = „przeciete”, bliżej słowa niż
    ZAPAS_SLOWA = „ciasno” (cięcie bez oddechu, może ucinać końcówkę albo zostawić początek następnego słowa)."""
    out = []
    for w0, w1, txt in slowa:
        w0, w1 = float(w0), float(w1)
        if w0 + ZAPAS_SLOWA < e < w1 - ZAPAS_SLOWA:
            rodzaj = "przeciete"
        elif min(abs(e - w0), abs(e - w1)) < ZAPAS_SLOWA:
            rodzaj = "ciasno"
        else:
            continue
        out.append({"slowo": str(txt), "zrodlo": [round(w0, 3), round(w1, 3)], "granica": round(e, 3),
                    "strona": strona, "rodzaj": rodzaj})
    return out


def ciecia_projektu(proj: dict) -> tuple[list[dict], list[list]]:
    """Cięcia osi projektu edytora (koniec każdego klipu poza ostatnim) ze słowami z analiz mowy źródeł
    (`<źródło>.mowa.json`) i słowa w czasie osi do obrazu. Podział ciągłego materiału (`tnij`) nie jest cięciem."""
    import projekt as pr
    ed = pr.ed
    clips = [{**c, "in": float(c.get("in", 0)), "out": float(c.get("out", 0))} for c in proj.get("clips") or []]
    lay = ed.layout_clips(clips)
    prz = ed.przejscia_osi(clips, int((proj.get("canvas") or {}).get("fps") or 30))
    mowa: dict[str, list] = {}

    def slowa(c: dict) -> list:
        src = str(c.get("src") or "")
        if src not in mowa:
            try:
                mowa[src] = json.loads(ed.speech_path(Path(src)).read_text(encoding="utf-8")).get("words") or []
            except (OSError, ValueError, AttributeError):
                mowa[src] = []
        return mowa[src] if c.get("kind", "video") == "video" and not c.get("muted") else []

    na_osi = []                  # słowa w czasie osi; słowo ucięte przez klip zostaje swoim kawałkiem (widać cięcie)
    for c, s0, _e in lay:
        sp = float(c.get("speed") or 1)
        for w0, w1, txt in slowa(c):
            if float(w1) > c["in"] and float(w0) < c["out"]:
                na_osi.append([round(s0 + (max(float(w0), c["in"]) - c["in"]) / sp, 3),
                               round(s0 + (min(float(w1), c["out"]) - c["in"]) / sp, 3), txt])
    lista = []
    for i in range(len(lay) - 1):
        (a, _, t), b = lay[i], lay[i + 1][0]
        if not prz[i] and ed.ciagly({**a, "kind": a.get("kind", "video"), "speed": a.get("speed") or 1, "volume": a.get("volume", 1)},
                                    {**b, "kind": b.get("kind", "video"), "speed": b.get("speed") or 1, "volume": b.get("volume", 1)}):
            continue
        lista.append({"t": round(t, 3), "przed": a.get("id"), "za": b.get("id"), "przejscie": prz[i],
                      "slowa": slowa_na_granicy(slowa(a), float(a.get("out", 0)), "koniec klipu")
                      + slowa_na_granicy(slowa(b), float(b.get("in", 0)), "początek klipu")})
    return lista, na_osi


def sceny(film: Path, prog: float = 0.3) -> list[float]:
    """Zmiany ujęcia w obrazie (filtr scene ffmpeg): czas pierwszej klatki nowego ujęcia."""
    r = subprocess.run([wl.need("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(film), "-an", "-vf",
                        f"select='gt(scene,{prog})',showinfo", "-f", "null", "-"], capture_output=True, text=True)
    return [round(float(x), 3) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def klatka(film: Path, t: float, szer: int = KLATKA_W):
    """Pierwsza klatka o czasie ≥ t (ffmpeg -ss z dokładnym szukaniem) jako obraz PIL albo None."""
    from PIL import Image
    r = subprocess.run([wl.need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.4f}", "-i", str(film),
                        "-frames:v", "1", "-vf", f"scale={szer}:-2", "-f", "image2pipe", "-vcodec", "ppm", "-"], capture_output=True)
    if r.returncode or not r.stdout:
        return None
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def roznica(a, b) -> float:
    pa, pb = (x.convert("L").resize((64, 64)).tobytes() for x in (a, b))
    return round(sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa), 2)


def _czcionka(rozmiar: int):
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, rozmiar)
    try:
        return ImageFont.load_default(size=rozmiar)
    except TypeError:
        return ImageFont.load_default()


def obraz_ciecia(film: Path, a: array, c: dict, okno: float, fps: float, dl: float, slowa: list, out: Path,
                 naglowek: str) -> dict:
    """Obraz cięcia (klatki, fala, cisza, słowa, linia cięcia) i różnica klatek tuż przed i tuż za cięciem."""
    from PIL import Image, ImageDraw
    t, kl = c["t"], 1.0 / fps
    gran = lambda x: min(max(0.0, x), max(0.0, dl - kl))   # noqa: E731
    czasy = [t - okno, t - 2 * okno / 3, t - okno / 3, t - kl, t, t + okno / 3, t + 2 * okno / 3, t + okno - kl]
    # -ss daje pierwszą klatkę o czasie ≥ ss: pół klatki wcześniej trafia dokładnie w klatkę z danej chwili
    klatki = [klatka(film, gran(x) - kl / 2) for x in czasy]
    przed2 = klatka(film, gran(t - 2 * kl) - kl / 2)
    wym = next((k.size for k in klatki if k), (KLATKA_W, 90))
    pusta = Image.new("RGB", wym, (40, 40, 40))
    klatki = [k or pusta for k in klatki]
    skok = roznica(klatki[3], klatki[4])
    tlo = roznica(przed2, klatki[3]) if przed2 else 0.0

    f_dl, f_m, f_s = _czcionka(18), _czcionka(13), _czcionka(11)
    PAD, GAP, CUT = 12, 6, 22
    W = PAD * 2 + 8 * wym[0] + 6 * GAP + CUT
    H_F, H_FALA, H_SL = wym[1] + 18, 150, 48
    y_f, y_w = 40, 40 + H_F + 10
    y_s = y_w + H_FALA + 6
    uwagi = c.get("problemy", []) + c.get("uwagi", [])
    H = y_s + H_SL + 10 + 18 * max(1, len(uwagi)) + 10
    img = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(img)
    kolor = (235, 80, 70) if c.get("problemy") else (240, 180, 60) if c.get("uwagi") else (90, 200, 120)
    d.text((PAD, 10), naglowek, font=f_dl, fill=(240, 240, 240))
    stan = "PROBLEM" if c.get("problemy") else "UWAGA" if c.get("uwagi") else "OK"
    d.text((W - PAD - d.textlength(stan, font=f_dl), 10), stan, font=f_dl, fill=kolor)
    x = PAD
    for i, k in enumerate(klatki):
        if i == 4:
            d.rectangle([x - GAP + 4, y_f - 4, x - GAP + CUT - 4, y_f + wym[1] + 4], fill=(220, 50, 50))
            x += CUT - GAP
        img.paste(k, (x, y_f))
        rel = czasy[i] - t
        d.text((x, y_f + wym[1] + 3), f"{'+' if rel >= 0 else '−'}{abs(rel):.2f} s", font=f_s, fill=(170, 170, 170))
        x += wym[0] + GAP

    # fala: czas [t − okno, t + okno] na całą szerokość
    t0, t1 = t - okno, t + okno
    X = lambda tt: PAD + (tt - t0) / (t1 - t0) * (W - 2 * PAD)   # noqa: E731
    d.rectangle([PAD, y_w, W - PAD, y_w + H_FALA], fill=(32, 34, 42))
    srodek, pol = y_w + H_FALA / 2, H_FALA / 2 - 4
    if len(a):
        krok = 0.01
        tt = t0
        while tt < t1:                                     # cisza: odcinki 10 ms poniżej progu
            if 0 <= tt and tt + krok <= len(a) / SR and db(a, tt, tt + krok) < CISZA_DB:
                d.rectangle([X(tt), y_w, X(tt + krok), y_w + H_FALA], fill=(48, 48, 66))
            tt += krok
        szer = W - 2 * PAD
        for px in range(szer):
            i0 = int((t0 + px / szer * (t1 - t0)) * SR)
            i1 = int((t0 + (px + 1) / szer * (t1 - t0)) * SR)
            kaw = a[max(0, i0):max(0, min(len(a), i1))]
            if kaw:
                d.line([(PAD + px, srodek - max(kaw) / 32768 * pol), (PAD + px, srodek - min(kaw) / 32768 * pol)],
                       fill=(110, 200, 255))
    if c.get("przejscie"):
        pd = c["przejscie"]["d"]
        d.rectangle([X(t - pd / 2), y_w, X(t + pd / 2), y_w + H_FALA], outline=(120, 140, 255), width=2)
        d.text((X(t + pd / 2) + 4, y_w + 4), f"przejście {c['przejscie']['type']} {pd:.2f} s", font=f_s, fill=(150, 165, 255))
    k = -math.floor(okno / 0.5) * 0.5
    while k <= okno + 1e-6:                                 # podziałka co 0,5 s
        d.line([(X(t + k), y_w + H_FALA - 6), (X(t + k), y_w + H_FALA)], fill=(140, 140, 140))
        d.text((X(t + k) + 2, y_w + H_FALA - 18), f"{k:+.1f}", font=f_s, fill=(140, 140, 140))
        k += 0.5
    d.line([(X(t), y_w - 2), (X(t), y_s + H_SL)], fill=(230, 50, 50), width=2)

    # słowa: pasek od początku do końca słowa i tekst, na zmianę w dwóch rzędach
    zle = {(s["slowo"]) for s in c.get("slowa", []) if s["rodzaj"] == "przeciete"}
    widoczne = [w for w in slowa if float(w[1]) > t0 and float(w[0]) < t1]
    for i, (w0, w1, txt) in enumerate(widoczne):
        y = y_s + (i % 2) * 22
        kol = (235, 80, 70) if str(txt) in zle and float(w0) <= t <= float(w1) + 0.05 else (210, 210, 210)
        d.rectangle([max(PAD, X(float(w0))), y, min(W - PAD, X(float(w1))), y + 3], fill=kol)
        d.text((max(PAD, X(float(w0))), y + 5), str(txt), font=f_m, fill=kol)
    if not widoczne:
        d.text((PAD, y_s + 10), "brak słów (analiza mowy: --projekt z mową źródeł albo --slowa)", font=f_s, fill=(120, 120, 120))
    y = y_s + H_SL + 10
    for u in uwagi or ["bez uwag z pomiarów: sprawdź obraz okiem"]:
        d.text((PAD, y), u, font=f_m, fill=(235, 80, 70) if u in c.get("problemy", []) else (240, 180, 60) if uwagi else (90, 200, 120))
        y += 18
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=85)
    return {"skok_obrazu": skok, "tlo_obrazu": tlo}


def wczytaj_slowa(plik: Path) -> list[list]:
    d = json.loads(plik.read_text(encoding="utf-8"))
    return [list(w[:3]) for w in (d.get("words") if isinstance(d, dict) else d) or [] if len(w) >= 3]


def ciecia(film: Path, katalog: Path, czasy: list[float] | None = None, projekt: Path | None = None,
           slowa_plik: Path | None = None, okno: float = 1.5, tylko: list[int] | None = None, prog_sceny: float = 0.3) -> dict:
    try:
        import PIL  # noqa: F401
    except ImportError:
        raise SystemExit("✗ brak Pillow: uruchom python3 z venv Hermesa (/opt/hermes/.venv/bin/python3)")
    dl, fps = wl.duration(film), eval_fps(film)
    slowa, uwaga_filmu, info = [], None, None
    if not czasy and not projekt and film.with_name(f"{film.stem}.edycja.json").is_file():
        projekt = film                                   # rolka clipmakera: projekt leży obok filmu
    if czasy:
        lista, zrodlo = [{"t": round(t, 3)} for t in sorted(czasy)], "--czasy"
    elif projekt:
        import projekt as pr
        pp = projekt if projekt.name.endswith(".edycja.json") else pr.ed.project_path(projekt)
        if not pp.is_file():
            raise SystemExit(f"✗ nie ma projektu: {pp}")
        proj = json.loads(pp.read_text(encoding="utf-8"))
        lista, slowa = ciecia_projektu(proj)
        zrodlo = "projekt"
        dl_proj = pr.total(proj) if proj.get("clips") else 0.0
        if dl_proj and abs(dl_proj - dl) > 0.15:
            uwaga_filmu = f"film trwa {dl:.2f} s, a projekt {dl_proj:.2f} s: wyrenderuj projekt ponownie albo podaj właściwy film"
    else:
        lista, zrodlo = [{"t": t} for t in sceny(film, prog_sceny)], "zmiany ujęcia w obrazie"
        info = ("filtr scene widzi zmiany ujęcia, nie cięcia w tym samym ujęciu (montaż mowy): takie podaj przez --czasy "
                "(lista „ciecia” z montaz.py) albo --projekt")
    if slowa_plik:
        slowa = wczytaj_slowa(slowa_plik)
    a = pcm(film)
    katalog.mkdir(parents=True, exist_ok=True)
    wyniki = []
    for nr, c in enumerate(lista, 1):
        if tylko and nr not in tylko:
            continue
        t = c["t"]
        c.update({"nr": nr, "problemy": [], "uwagi": []})
        c.setdefault("slowa", [])
        if not c.get("przejscie") and len(a):
            c["dzwiek"] = trzask(a, t)
            c["glosnosc_db"] = db(a, t - 0.03, t + 0.03)
            if c["dzwiek"]["trzask"]:
                c["problemy"].append(f"trzask na cięciu: skok fali {c['dzwiek']['skok']} = {c['dzwiek']['krotnosc']}× zwykłego "
                                     "(krótki zanik dźwięku na cięciu: eksport edytora robi go sam, montaz.py też)")
        for s in c["slowa"]:
            gdzie = f"„{s['slowo']}” ({s['strona']}, źródło {s['zrodlo'][0]:.2f}–{s['zrodlo'][1]:.2f} s, granica {s['granica']:.2f} s)"
            if s["rodzaj"] == "przeciete":
                c["problemy"].append(f"cięcie w pół słowa {gdzie}: przesuń granicę klipu za koniec słowa albo przed jego początek")
            else:
                c["uwagi"].append(f"cięcie tuż przy słowie {gdzie}: posłuchaj, czy nie ucina końcówki; zapas 40–200 ms")
        if slowa_plik:                                   # transkrypcja gotowego filmu: słowo, które trwa przez cięcie
            for w0, w1, txt in slowa:
                if float(w0) + ZAPAS_SLOWA < t < float(w1) - ZAPAS_SLOWA:
                    c["uwagi"].append(f"słowo „{txt}” trwa przez cięcie ({float(w0):.2f}–{float(w1):.2f} s): posłuchaj, czy nie w pół słowa")
        if not slowa and not c.get("przejscie") and c.get("glosnosc_db", -120) > -30 and \
                db(a, t - 0.06, t - 0.01) > -30 and db(a, t + 0.01, t + 0.06) > -30:
            c["uwagi"].append(f"cięcie w głośnym dźwięku ({c['glosnosc_db']} dB po obu stronach), bez analizy mowy: posłuchaj, czy nie w pół słowa")
        obraz = katalog / f"ciecie-{nr:02d}-{t:.2f}s.jpg"
        naglowek = f"Cięcie {nr}/{len(lista)} · {t:.2f} s" + (f" · {c['przed']} → {c['za']}" if c.get("przed") else "")
        # różnicę klatek liczy obraz_ciecia; przeskok dopisujemy przed rysowaniem z drugiego przebiegu tylko gdy trzeba
        m = obraz_ciecia(film, a, c, okno, fps, dl, slowa, obraz, naglowek)
        if not c.get("przejscie") and PRZESKOK[0] <= m["skok_obrazu"] < PRZESKOK[1] and m["skok_obrazu"] >= 2.5 * max(m["tlo_obrazu"], 0.5):
            c["uwagi"].append(f"przeskok: ten sam kadr po obu stronach (różnica {m['skok_obrazu']}): przybliżenie drugiej części "
                              f"(projekt.py kadr <id> --wypelnij --zoom 1.15) albo przebitka")
            m = obraz_ciecia(film, a, c, okno, fps, dl, slowa, obraz, naglowek)
        c.update(m, obraz=str(obraz), rodzaj="przejście" if c.get("przejscie") else
                 "ten sam obraz" if m["skok_obrazu"] < PRZESKOK[0] else "przeskok" if any(u.startswith("przeskok") for u in c["uwagi"])
                 else "zmiana ujęcia")
        wyniki.append(c)
    problemy = sum(len(c["problemy"]) for c in wyniki)
    return {"film": str(film), "zrodlo_ciec": zrodlo, "ciec": len(lista), "katalog": str(katalog), "ciecia": wyniki,
            "problemy": problemy, "uwagi": sum(len(c["uwagi"]) for c in wyniki), **({"uwaga": uwaga_filmu} if uwaga_filmu else {}),
            **({"info": info} if info else {}),
            "ok": problemy == 0 and not uwaga_filmu,
            "obejrzyj": "każdy obraz przez vision_analyze: przeskok w pół gestu, czarna albo pusta klatka, tekst zasłonięty "
                        "albo urwany na cięciu, kolec fali na czerwonej linii (trzask), słowo przecięte linią"}


def determinizm(src: str, czasy: str, preset: str) -> dict:
    hashes = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(Path(__file__).with_name("html_wideo.py")), "klatki", src,
                                "--czasy", czasy, "--preset", preset, "--out", tmp], capture_output=True, text=True)
            if r.returncode:
                raise SystemExit(f"✗ html_wideo: {(r.stderr or r.stdout).strip()[-400:]}")
            hashes.append([hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(Path(tmp).glob("*.png"))])
    rozne = [t for t, a, b in zip(czasy.split(","), *hashes) if a != b]
    return {"czasy": czasy.split(","), "ok": not rozne and bool(hashes[0]), "rozne_klatki": rozne,
            "uwaga": "różnica = Math.random bez ziarna, zegar, stan między klatkami albo animacja CSS"}


def ocena(plik: Path) -> dict:
    k = json.loads(plik.read_text(encoding="utf-8"))
    osie = k.get("osie") or {}
    brak = [o for o in OSIE if o not in osie]
    slabe = {o: v for o, v in osie.items() if isinstance(v, (int, float)) and v < 8}
    problemy = k.get("problemy") or []
    bez_czasu = [p for p in problemy if not isinstance(p, dict) or "t" not in p]
    ok = not brak and not slabe and not bez_czasu
    return {"runda": k.get("runda"), "ok": ok, "brak_osi": brak, "ponizej_8": slabe,
            "problemy_bez_czasu": len(bez_czasu),
            "dalej": "PASS pętli: wszystkie osie ≥ 8" if ok else "popraw 3 najgorsze problemy, render tylko tych sekund, nowa runda"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("telefon"); s.add_argument("film"); s.add_argument("-o")
    s = sub.add_parser("pasek"); s.add_argument("film"); s.add_argument("--t", type=float, required=True)
    s.add_argument("--klatek", type=int, default=12); s.add_argument("-o")
    s = sub.add_parser("martwe"); s.add_argument("film"); s.add_argument("--prog", type=float, default=2.5)
    s = sub.add_parser("puls"); s.add_argument("film"); s.add_argument("--prog", type=float, default=3.0)
    s.add_argument("--min", type=float, default=1.5)
    s = sub.add_parser("petla"); s.add_argument("film"); s.add_argument("-o")
    s = sub.add_parser("ciecia"); s.add_argument("film"); s.add_argument("--projekt", help="<film>.edycja.json (albo oryginał obok niego)")
    s.add_argument("--czasy", help="chwile cięć w s, po przecinku"); s.add_argument("--slowa", help="mowa.json gotowego filmu")
    s.add_argument("--okno", type=float, default=1.5); s.add_argument("--tylko", help="numery cięć, np. 2,5")
    s.add_argument("--prog-sceny", type=float, default=0.3); s.add_argument("-o", help="katalog obrazów")
    s = sub.add_parser("determinizm"); s.add_argument("zrodlo"); s.add_argument("--czasy", required=True)
    s.add_argument("--preset", default="jarvo")
    s = sub.add_parser("ocena"); s.add_argument("plik")
    a = ap.parse_args(argv)
    if a.cmd not in ("determinizm",) and not Path(getattr(a, "film", getattr(a, "plik", ""))).exists():
        print("✗ brak pliku", file=sys.stderr)
        return 2
    if a.cmd == "telefon":
        f = Path(a.film); r = telefon(f, Path(a.o or f.with_name(f.stem + "-telefon.jpg")))
    elif a.cmd == "pasek":
        f = Path(a.film); r = pasek(f, a.t, a.klatek, Path(a.o or f.with_name(f"{f.stem}-pasek-{a.t:g}.jpg")))
    elif a.cmd == "martwe":
        r = martwe(Path(a.film), a.prog)
    elif a.cmd == "puls":
        r = puls(Path(a.film), a.prog, a.min)
    elif a.cmd == "petla":
        r = petla(Path(a.film), Path(a.o) if a.o else None)
    elif a.cmd == "ciecia":
        f = Path(a.film)
        r = ciecia(f, Path(a.o or f.with_name(f.stem + "-ciecia")),
                   czasy=[float(x) for x in a.czasy.split(",") if x.strip()] if a.czasy else None,
                   projekt=Path(a.projekt) if a.projekt else None, slowa_plik=Path(a.slowa) if a.slowa else None,
                   okno=max(0.3, min(5.0, a.okno)), tylko=[int(x) for x in a.tylko.split(",")] if a.tylko else None,
                   prog_sceny=a.prog_sceny)
    elif a.cmd == "determinizm":
        r = determinizm(a.zrodlo, a.czasy, a.preset)
    else:
        r = ocena(Path(a.plik))
    print(json.dumps(r, ensure_ascii=False, indent=None if a.json else 2))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
