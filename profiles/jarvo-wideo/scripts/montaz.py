#!/usr/bin/env python3
"""Montaż nagrań: cięcie fragmentów, kadr pod format (9:16 z poziomego), usuwanie ciszy, głośność, czysty głos,
stabilizacja nagrań z ręki, transkrypcja.

    python3 montaz.py wytnij nagranie.mp4 -o klip.mp4 --zakresy "0:12.5-0:41,1:10-1:32.4"
    python3 montaz.py kadr nagranie.mp4 -o pion.mp4 --format 9:16 [--x 0.5] [--tryb przytnij|rozmyte]
    python3 montaz.py cisza nagranie.mp4 -o bez-ciszy.mp4 [--prog -35] [--min 0.5] [--zapas 0.12]
    python3 montaz.py glosnosc film.mp4 -o film-14lufs.mp4 [--lufs -14]
    python3 montaz.py glos nagranie.mp4 -o czysty.mp4 [--poziom auto|lekki|sredni|mocny]
    python3 montaz.py stabilizuj nagranie.mp4 -o stabilne.mp4 [--sila lekka|srednia|mocna] [--statyw] [--zoom 0]
    python3 montaz.py stabilizuj nagranie.mp4 --tylko-pomiar   # samo drżenie kamery (czy stabilizować)
    python3 montaz.py transkrypcja nagranie.mp4 [-o out/wideo/transkrypcja] [--co 20]
    python3 montaz.py napraw film.mp4 -o film-ok.mp4       # yuv420p/zakres TV/faststart po silnikach zewnętrznych

Czas: sekundy (75.5) albo m:ss(.x) / h:mm:ss. Każde cięcie jest przekodowane (dokładne co do klatki).
kadr --x: środek kadru w poziomie (0 = lewa krawędź, 0.5 = środek, 1 = prawa); rozmyte = całe ujęcie
na rozmytym tle (dobre do slajdów i nagrań ekranu). glosnosc: dwa przejścia loudnorm (pomiar → korekta), potem
limiter szczytów (true peak ≤ −1).
glos: czysty głos jak w edytorze HQ (edytor.glos_filter: dudnienie, syczenie, szum, ciszej w pauzach, wyrównanie);
auto = poziom z tła nagrania; obraz kopiowany bez zmian. Potem glosnosc (kompresor zmienia głośność).
stabilizuj: dwa przejścia vidstab (ruch kamery → wygładzona droga, kadr lekko powiększony bez czarnych brzegów),
4K zmniejszone do 1080p; drżenie przed i po (% szerokości kadru) z tego samego pomiaru. Na całym nagraniu przed
cięciem (cięcie w środku psuje wygładzanie). --statyw: kamera ma stać w miejscu (bez panoram). Bez vidstab: deshake.
wytnij i cisza wypisują `ciecia`: chwile cięć w gotowym pliku (do `krytyka.py ciecia --czasy`).
transkrypcja: Parakeet (jarvo-stt) → słowa z czasem (JSON) + tekst z czasami co --co sekund (do wyboru fragmentów).
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", *wl.ENC_LIMITS, "-c:a", "aac",
       "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]


def parse_time(s: str) -> float:
    s = s.strip()
    if not s:
        raise ValueError("pusty czas")
    parts = s.split(":")
    val = 0.0
    for p in parts:
        val = val * 60 + float(p.replace(",", "."))
    return val


def parse_ranges(spec: str) -> list[tuple[float, float]]:
    out = []
    for part in spec.split(","):
        if not part.strip():
            continue
        a, _, b = part.partition("-")
        start, end = parse_time(a), parse_time(b)
        if end <= start:
            raise SystemExit(f"Zakres {part!r}: koniec przed początkiem")
        out.append((start, end))
    return out


def has_audio(path: Path) -> bool:
    return bool(wl.probe(path)["audio"])


def pozycje_ciec(ranges: list[tuple[float, float]]) -> list[float]:
    """Chwile cięć w gotowym pliku (s): koniec każdego fragmentu poza ostatnim, do `krytyka.py ciecia --czasy`."""
    out, t = [], 0.0
    for a, b in ranges[:-1]:
        t += b - a
        out.append(round(t, 3))
    return out


def cut(src: Path, ranges: list[tuple[float, float]], out: Path) -> Path:
    audio = has_audio(src)
    sdr = wl.sdr(src)                  # film HDR z telefonu → zwykły obraz (bez tego wychodzi szary i sprany)
    fc, labels = [], []
    for i, (a, b) in enumerate(ranges):
        fc.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
        if audio:
            fc.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,"
                      f"afade=t=out:st={max(0.0, b - a - 0.03):.3f}:d=0.03[a{i}]")
            labels.append(f"[a{i}]")
    n = len(ranges)
    fc.append("".join(labels) + f"concat=n={n}:v=1:a={1 if audio else 0}[vc]" + ("[a]" if audio else ""))
    fc.append(f"[vc]{wl.z_sdr(sdr, wl.TV_RANGE)}[v]")
    maps = ["-map", "[v]"] + (["-map", "[a]"] if audio else [])
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", ";".join(fc), *maps, *ENC, str(out)])
    return out


def reframe(src: Path, out: Path, fmt: str, x: float, mode: str) -> Path:
    w, h = wl.parse_format(fmt)
    x = min(1.0, max(0.0, x))
    sdr = wl.sdr(src)                  # HDR → zwykły obraz po kadrze (w kadrze 1080 p, nie w 4K źródła)
    if mode == "rozmyte":
        fc = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=24:2,"
              f"eq=brightness=-0.08[bg];[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2,{wl.z_sdr('setsar=1', sdr)},{wl.TV_RANGE}[v]")
    else:
        fc = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={w}:{h}:x=(iw-{w})*{x:.3f}:y=(ih-{h})/2,{wl.z_sdr('setsar=1', sdr)},{wl.TV_RANGE}[v]")
    maps = ["-map", "[v]"] + (["-map", "0:a"] if has_audio(src) else [])
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", fc, *maps, *ENC, str(out)])
    return out


def silences(src: Path, thresh_db: float, min_len: float) -> list[tuple[float, float]]:
    res = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-vn", "-af",
                          f"silencedetect=noise={thresh_db}dB:d={min_len}", "-f", "null", "-"], capture_output=True, text=True)
    ss = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", res.stderr)]
    dur = wl.duration(src)
    return [(max(0.0, s), se[i] if i < len(se) else dur) for i, s in enumerate(ss)]


def remove_silence(src: Path, out: Path, thresh_db: float, min_len: float, pad: float) -> tuple[Path, dict]:
    if not has_audio(src):
        raise SystemExit("Nagranie bez dźwięku: nie ma czego wycinać.")
    dur = wl.duration(src)
    sil = silences(src, thresh_db, min_len)
    keep, t = [], 0.0
    for s, e in sil:
        a, b = t, s + pad
        if b - a > 0.15:
            keep.append((a, min(b, dur)))
        t = max(t, e - pad)
    if dur - t > 0.15:
        keep.append((t, dur))
    if not keep:
        raise SystemExit("Całe nagranie to cisza (sprawdź --prog).")
    cut(src, keep, out)
    kept = sum(b - a for a, b in keep)
    return out, {"przed_s": round(dur, 2), "po_s": round(kept, 2), "wyciete_s": round(dur - kept, 2), "fragmenty": len(keep),
                 "ciecia": pozycje_ciec(keep)}


def loudness(src: Path, out: Path, target: float) -> tuple[Path, dict]:
    first = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-vn", "-af",
                            f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", first.stderr, re.S)
    if not m:
        raise SystemExit("Pomiar głośności nie powiódł się (brak dźwięku?).")
    meas = json.loads(m.group(0))
    # loudnorm daje 192 kHz: limiter tutaj łapie też szczyty między próbkami (true peak), bo AAC i podniesienie
    # głośności potrafią wypchnąć szczyt ponad 0 dBFS (qa_wideo: true peak ≤ −1); −2 dBFS zostawia zapas na koder
    af = (f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
          f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:"
          "linear=true,alimiter=limit=0.79:level=false:attack=1:release=50,aresample=48000")
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags",
            "+faststart", str(out)])
    return out, {"przed_lufs": float(meas["input_i"]), "cel_lufs": target}


def voice(src: Path, out: Path, poziom: str) -> tuple[Path, dict]:
    """Czysty głos na całym nagraniu (ten sam łańcuch co eksport edytora HQ), obraz kopiowany bez zmian."""
    ed = wl.ed
    if not has_audio(src):
        raise SystemExit("Nagranie nie ma dźwięku.")
    dur = wl.duration(src)
    r = subprocess.run(ed.szum_cmd(src), capture_output=True, text=True)
    tlo = ed.szum_z_logu(r.stderr) if r.returncode == 0 else None
    poziom = ed.glos_auto(tlo) if poziom == "auto" else poziom
    wej, chain = ed.glos_wejscie(0.0, dur, poziom, tlo)      # bez opóźnienia afftdn: usta zgodne z obrazem
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), *wej, "-i", str(src), "-map", "0:v?", "-map", "1:a:0",
            "-af", f"asetpts=PTS-STARTPTS,{chain},aresample=48000,apad=whole_dur={dur:.3f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)])
    return out, {"poziom": poziom, "tlo_db": tlo}


def fix(src: Path, out: Path) -> Path:
    """Film z zewnętrznego silnika → standard platform: yuv420p w zakresie TV, H.264, AAC, faststart (dźwięk bez zmian)."""
    audio = ["-c:a", "aac", "-b:a", "192k"] if has_audio(src) else []
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), "-vf", wl.z_sdr(wl.sdr(src), wl.TV_RANGE), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            *wl.ENC_LIMITS, *audio, "-movflags", "+faststart", str(out)])
    return out


# Stabilizacja nagrań z ręki: za kajisho5/ffmpeg-skill (MIT, stabilize.py: dwa przejścia vidstab), z naszym pomiarem
STAB = {"lekka": (4, 10), "srednia": (6, 15), "mocna": (9, 30)}   # siła → (shakiness detekcji, wygładzanie ± klatek)
DESHAKE = {"lekka": 16, "srednia": 32, "mocna": 64}              # bez vidstab: zasięg ruchu deshake (px)
STAB_MAX = 1920                     # dłuższy bok: 4K z telefonu → 1080p (kilka razy szybciej, platformy i tak 1080p)
POMIAR_SZER = 640                   # pomiar drżenia na kopii tej szerokości (przed i po tak samo)
ODSTRZ = "unsharp=5:5:0.8:3:3:0.4"  # powiększenie kadru zmiękcza obraz (dwuliniowo + to: 2× szybciej niż bicubic)


def ma_vidstab() -> bool:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    return "vidstabdetect" in r.stdout and "vidstabtransform" in r.stdout


def ruch_z_trf(tekst: str) -> list[tuple[float, float]]:
    """Ruch obrazu klatka do klatki (px) z pliku vidstabdetect (ASCII): mediana ruchów lokalnych `LM vx vy`
    (mediana pomija ruch osób i rzeczy w kadrze); klatka bez pól pomiaru = bez ruchu."""
    out = []
    for line in tekst.splitlines():
        if not line.startswith("Frame "):
            continue
        lm = re.findall(r"\(LM (-?\d+) (-?\d+) ", line)
        out.append((statistics.median(int(x) for x, _ in lm), statistics.median(int(y) for _, y in lm))
                   if lm else (0.0, 0.0))
    return out


def drzenie_z_ruchu(ruch: list[tuple[float, float]], szer: int, okno: int = 15) -> float:
    """Drżenie kamery w % szerokości kadru: średnia odległość drogi kamery (suma ruchów) od jej wygładzenia
    (średnia z ±`okno` klatek, przy brzegach okno symetrycznie mniejsze). Płynna panorama i najazd zostają
    w wygładzeniu, drżenie ręki nie."""
    if len(ruch) < 3 or szer <= 0:
        return 0.0
    xs = list(itertools.accumulate(dx for dx, _ in ruch))
    ys = list(itertools.accumulate(dy for _, dy in ruch))
    n, odl = len(xs), []
    for i in range(n):
        k = min(okno, i, n - 1 - i)
        sx, sy = sum(xs[i - k:i + k + 1]) / (2 * k + 1), sum(ys[i - k:i + k + 1]) / (2 * k + 1)
        odl.append(math.hypot(xs[i] - sx, ys[i] - sy))
    return round(100 * sum(odl) / n / szer, 3)


def drzenie(path: Path) -> float:
    """Drżenie nagrania (`drzenie_z_ruchu`) z vidstabdetect na kopii szerokości POMIAR_SZER."""
    with tempfile.TemporaryDirectory() as tmp:     # plik ruchu w katalogu roboczym: ścieżka bez cytowania w filtrze
        wl.run(["ffmpeg", "-i", str(Path(path).resolve()), "-vf",
                f"scale={POMIAR_SZER}:-2,vidstabdetect=shakiness=8:result=ruch.trf", "-an", "-f", "null", "-"],
               cwd=Path(tmp))
        return drzenie_z_ruchu(ruch_z_trf((Path(tmp) / "ruch.trf").read_text()), POMIAR_SZER)


def rada_drzenia(proc: float) -> str:
    """Siła z drżenia (% szerokości; progi z nagrań testowych: statyw 0, lekko 0,3, z ręki 0,8, mocno 2,3)."""
    if proc < 0.15:
        return "stabilne: nie stabilizuj"
    if proc < 0.5:
        return "lekkie drżenie: --sila lekka"
    return "z ręki: --sila srednia" if proc < 1.5 else "mocno trzęsie: --sila mocna"


def stabilize(src: Path, out: Path, sila: str, statyw: bool = False, zoom: float = 0.0,
              pomiar: bool = True) -> tuple[Path, dict]:
    v = wl.probe(src).get("video")
    if not v:
        raise SystemExit("Plik bez obrazu.")
    w, h = int(v["width"]), int(v["height"])
    skala = ""
    if max(w, h) > STAB_MAX:
        k = STAB_MAX / max(w, h)
        w, h = round(w * k / 2) * 2, round(h * k / 2) * 2
        skala = f"scale={w}:{h}:flags=lanczos"
    vidstab = ma_vidstab()
    przed = drzenie(src) if pomiar and vidstab else None
    sdr = wl.sdr(src)                  # HDR → zwykły obraz przed vidstab (inaczej ffmpeg tnie 10 bitów na ślepo)
    statyw_opt = ":tripod=1" if statyw else ""
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if vidstab:
            shak, wygl = STAB[sila]
            wl.run(["ffmpeg", "-i", str(src.resolve()), "-vf",
                    ",".join(x for x in (skala, f"vidstabdetect=shakiness={shak}:accuracy=15:result=ruch.trf{statyw_opt}")
                             if x), "-an", "-f", "null", "-"], cwd=Path(tmp))
            ruch = (f"vidstabtransform=input=ruch.trf:smoothing={wygl}:optzoom=1:zoom={zoom:g}:interpol=bilinear"
                    f"{statyw_opt}")
        else:
            r = DESHAKE[sila]
            ruch = f"deshake=rx={r}:ry={r}"
        vf = ",".join(x for x in (skala, sdr, ruch, ODSTRZ, wl.TV_RANGE) if x)
        wl.run(["ffmpeg", "-y", "-i", str(src.resolve()), "-vf", vf, "-map", "0:v:0", "-map", "0:a:0?", *ENC, str(out)],
               cwd=Path(tmp))
    stats = {"sila": sila, "metoda": "vidstab" if vidstab else "deshake", "statyw": statyw, "rozmiar": f"{w}x{h}",
             "sek": round(wl.duration(out), 2)}
    if przed is not None:
        po = drzenie(out)
        stats.update(drzenie_przed_proc=przed, drzenie_po_proc=po)
        if przed < 0.15:
            stats["uwaga"] = "nagranie było prawie stabilne: zostaw oryginał, powiększenie kadru nic nie daje"
        elif po > 0.7 * przed:
            stats["uwaga"] = ("drżenie spadło mało: obejrzyj (to może być ruch osoby, nie kamery); "
                              "spróbuj --sila mocna albo --statyw")
    return out, stats


def transcript(src: Path, outbase: Path, every: float) -> dict:
    words = wl.transcribe_words(src)
    outbase.parent.mkdir(parents=True, exist_ok=True)
    wl.write_json(outbase.with_suffix(".slowa.json"), [w.__dict__ for w in words])
    lines, cur, t0 = [], [], None
    for w in words:
        if t0 is None:
            t0 = w.start
        cur.append(w.text)
        if w.end - t0 >= every or re.search(r"[.!?]$", w.text) and w.end - t0 >= every / 2:
            lines.append(f"[{int(t0 // 60)}:{t0 % 60:05.2f}] {' '.join(cur)}")
            cur, t0 = [], None
    if cur and t0 is not None:
        lines.append(f"[{int(t0 // 60)}:{t0 % 60:05.2f}] {' '.join(cur)}")
    outbase.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"slowa": len(words), "slowa_json": str(outbase.with_suffix(".slowa.json")), "tekst": str(outbase.with_suffix(".txt"))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("wytnij")
    c.add_argument("plik")
    c.add_argument("-o", required=True)
    c.add_argument("--zakresy", required=True)
    k = sub.add_parser("kadr")
    k.add_argument("plik")
    k.add_argument("-o", required=True)
    k.add_argument("--format", default="9:16")
    k.add_argument("--x", type=float, default=0.5)
    k.add_argument("--tryb", choices=["przytnij", "rozmyte"], default="przytnij")
    s = sub.add_parser("cisza")
    s.add_argument("plik")
    s.add_argument("-o", required=True)
    s.add_argument("--prog", type=float, default=-35.0, help="próg ciszy w dB (np. -35; głośne tło: -30)")
    s.add_argument("--min", type=float, default=0.5, help="minimalna cisza do wycięcia (s)")
    s.add_argument("--zapas", type=float, default=0.12, help="zostaw tyle ciszy przy słowach (s)")
    g = sub.add_parser("glosnosc")
    g.add_argument("plik")
    g.add_argument("-o", required=True)
    g.add_argument("--lufs", type=float, default=-14.0)
    v = sub.add_parser("glos", help="czysty głos: dudnienie, syczenie, szum, ciszej w pauzach, wyrównanie (obraz bez zmian)")
    v.add_argument("plik")
    v.add_argument("-o", required=True)
    v.add_argument("--poziom", choices=["auto", *wl.ed.GLOS], default="auto",
                   help="auto = z tła nagrania; lekki = dobry pokój, sredni = zwykły, mocny = telefon, laptop, hałas")
    n = sub.add_parser("napraw", help="yuv420p (zakres TV), H.264, AAC, faststart: dla filmów z lemo/anidoodle/HyperFrames")
    n.add_argument("plik")
    n.add_argument("-o", required=True)
    st = sub.add_parser("stabilizuj", help="nagranie z ręki: dwa przejścia vidstab, drżenie przed i po")
    st.add_argument("plik")
    st.add_argument("-o", default=None)
    st.add_argument("--sila", choices=list(STAB), default="srednia",
                    help="lekka = lekko drży, srednia = z ręki, mocna = w marszu, z auta")
    st.add_argument("--statyw", action="store_true", help="kamera ma stać w miejscu (bez panoram i najazdów)")
    st.add_argument("--zoom", type=float, default=0.0, help="dodatkowe powiększenie w %% (ponad samo ukrycie brzegów)")
    st.add_argument("--tylko-pomiar", action="store_true", help="tylko drżenie kamery, bez stabilizacji")
    st.add_argument("--bez-pomiaru", action="store_true", help="bez pomiaru drżenia przed i po (szybciej)")
    t = sub.add_parser("transkrypcja")
    t.add_argument("plik")
    t.add_argument("-o", default=None, help="baza nazwy wyników (domyślnie obok nagrania)")
    t.add_argument("--co", type=float, default=20.0, help="linia tekstu co ~N sekund")
    args = ap.parse_args(argv)
    wl.need("ffmpeg")
    src = Path(args.plik)
    if not src.exists():
        raise SystemExit(f"Brak pliku: {src}")
    try:
        if args.cmd == "wytnij":
            zakresy = parse_ranges(args.zakresy)
            out = cut(src, zakresy, Path(args.o))
            print(json.dumps({"plik": str(out), "sek": round(wl.duration(out), 2), "ciecia": pozycje_ciec(zakresy)},
                             ensure_ascii=False))
        elif args.cmd == "kadr":
            out = reframe(src, Path(args.o), args.format, args.x, args.tryb)
            print(json.dumps({"plik": str(out), "format": args.format}, ensure_ascii=False))
        elif args.cmd == "cisza":
            out, stats = remove_silence(src, Path(args.o), args.prog, args.min, args.zapas)
            print(json.dumps({"plik": str(out), **stats}, ensure_ascii=False))
        elif args.cmd == "glosnosc":
            out, stats = loudness(src, Path(args.o), args.lufs)
            print(json.dumps({"plik": str(out), **stats}, ensure_ascii=False))
        elif args.cmd == "glos":
            out, stats = voice(src, Path(args.o), args.poziom)
            print(json.dumps({"plik": str(out), **stats}, ensure_ascii=False))
        elif args.cmd == "stabilizuj":
            if args.tylko_pomiar:
                if not ma_vidstab():
                    raise SystemExit("FFmpeg bez vidstab: pomiar drżenia niedostępny.")
                proc = drzenie(src)
                print(json.dumps({"plik": str(src), "drzenie_proc": proc, "rada": rada_drzenia(proc)}, ensure_ascii=False))
                return 0
            if not args.o:
                raise SystemExit("Podaj -o <wynik> (albo --tylko-pomiar).")
            out, stats = stabilize(src, Path(args.o), args.sila, args.statyw, max(0.0, args.zoom), not args.bez_pomiaru)
            print(json.dumps({"plik": str(out), **stats}, ensure_ascii=False))
        elif args.cmd == "napraw":
            out = fix(src, Path(args.o))
            print(json.dumps({"plik": str(out)}, ensure_ascii=False))
        else:
            base = Path(args.o) if args.o else src.with_suffix("")
            print(json.dumps(transcript(src, base, args.co), ensure_ascii=False))
        return 0
    except wl.FFError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
