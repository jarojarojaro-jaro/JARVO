#!/usr/bin/env python3
"""Dwa ekrany w jednym kadrze (split screen): dwa nagrania albo zdjęcia obok siebie, jedno nad drugim,
przed/po z przesuwaną kreską albo na dwóch telefonach narysowanych kodem.

    python3 dwa_ekrany.py A.mp4 B.mp4 -o wynik.mp4 [--uklad obok|gora-dol|przed-po|telefony] [--format 9:16]
        [--podpisy "Przed" "Po"] [--dzwiek a|b|oba|brak] [--sek 12] [--kadr-a 0.5,0.4] [--kadr-b 0.5,0.4]
        [--kreska "0=0,2=0.5,4=0.5,6=1"] [--tlo "#0e0f13"] [--kolor "#ffffff"]

Układ domyślny z formatu: pion (9:16, 4:5) → gora-dol, poziom i kwadrat → obok. Każde okno wypełnia treść
przycięta do okna (bez rozciągania); --kadr-a / --kadr-b = środek przycięcia (x, y: 0–1; 0,4 = twarz w górnej
części). Zdjęcie stoi przez cały film; krótsze nagranie trzyma ostatnią klatkę. Długość: --sek albo dłuższe
nagranie (same zdjęcia: 6 s). Dźwięk domyślnie z A (gdy A nie ma, z B).
przed-po: A (przed) z lewej, B (po) z prawej, kreska jedzie po kadrze; --kreska = punkty „sekunda=udział B”
(0 = całe A, 1 = całe B), między punktami płynnie; domyślnie A → pół na pół → B.
telefony: dwa telefony narysowane kodem (ramka, wycięcie na aparat, zaokrąglone rogi) na tle --tlo.
Na końcu test pauzy: w każdej chwili coś ma się ruszać w co najmniej
jednym oknie; dłuższy bezruch obu okien jest w `uwagi`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", *wl.ENC_LIMITS, "-c:a", "aac",
       "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]
UKLADY = ("obok", "gora-dol", "przed-po", "telefony")
SEK_ZDJECIA = 6.0                       # dwa zdjęcia, bez --sek
KRESKA = 0.006                          # grubość kreski podziału (część krótszego boku)
EKRAN_PROPORCJA = 19.5 / 9              # ekran telefonu: wysokość / szerokość
BEZRUCH = {"split": 1.5, "przed-po": 2.5}   # s bezruchu obu okien, od których jest uwaga (przed/po: chwila na obejrzenie)


def kolor(hexa: str, alfa: int = 255) -> tuple[int, int, int, int]:
    h = hexa.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise SystemExit(f"Kolor {hexa!r}: podaj #rrggbb")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alfa


def kadr_xy(spec: str) -> tuple[float, float]:
    try:
        x, y = (float(v) for v in spec.split(","))
    except ValueError:
        raise SystemExit(f"--kadr {spec!r}: podaj x,y (np. 0.5,0.4)") from None
    return min(1.0, max(0.0, x)), min(1.0, max(0.0, y))


def okna(uklad: str, w: int, h: int) -> list[tuple[int, int, int, int]]:
    """Okna A i B (x, y, szer, wys) w px; kreska podziału wchodzi w szczelinę między oknami."""
    k = wl.even(max(2, min(w, h) * KRESKA))
    if uklad == "obok":
        lw = wl.even((w - k) / 2)
        return [(0, 0, lw, h), (lw + k, 0, w - lw - k, h)]
    if uklad == "gora-dol":
        gh = wl.even((h - k) / 2)
        return [(0, 0, w, gh), (0, gh + k, w, h - gh - k)]
    if uklad == "przed-po":
        return [(0, 0, w, h), (0, 0, w, h)]
    # telefony: ekrany obok siebie, tak duże, jak pozwala kadr (zapas na ramkę, podpisy i odstęp)
    sw = min(w * 0.40, h * 0.70 / EKRAN_PROPORCJA)
    sw = wl.even(sw)
    sh = wl.even(sw * EKRAN_PROPORCJA)
    odstep = w * 0.06
    x0 = (w - 2 * sw - odstep) / 2
    y0 = wl.even((h - sh) / 2 - h * 0.03)
    return [(wl.even(x0), y0, sw, sh), (wl.even(x0 + sw + odstep), y0, sw, sh)]


def _font(rozmiar: int):
    return wl.czcionka(rozmiar, gruby=True)  # DejaVu Bold z obrazu, poza Linuksem pogrubiony krój systemu


def _podpis(d, tekst: str, x: float, y: float, rozmiar: int, kotwica: str = "lt") -> None:
    """Podpis na ciemnej pigułce; (x, y) = lewy górny róg pigułki ("lt") albo środek góry ("mt")."""
    f = _font(rozmiar)
    l, t, r, b = d.textbbox((0, 0), tekst, font=f)
    px, py = rozmiar * 0.55, rozmiar * 0.32
    pw, ph = r - l + 2 * px, b - t + 2 * py
    if kotwica == "mt":
        x -= pw / 2
    d.rounded_rectangle((x, y, x + pw, y + ph), radius=ph / 2, fill=(0, 0, 0, 150))
    d.text((x + px - l, y + py - t), tekst, font=f, fill=(255, 255, 255, 255))


def nakladka(uklad: str, w: int, h: int, sloty, podpisy: list[str], tlo: str, kreska_kolor: str) -> "Image":
    """Wszystko, co stoi nad treścią okien: kreska podziału, podpisy, ramki telefonów (z tłem wokół nich)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = min(w, h) / 1080
    rozm = round(46 * s)
    m = wl.safe_margins(w, h)
    if uklad in ("obok", "gora-dol"):
        (ax, ay, aw, ah), (bx, by, bw, bh) = sloty
        if uklad == "obok":
            d.rectangle((ax + aw, 0, bx - 1, h), fill=kolor(kreska_kolor))
        else:
            d.rectangle((0, ay + ah, w, by - 1), fill=kolor(kreska_kolor))
        for i, tekst in enumerate(podpisy[:2]):
            x, y = sloty[i][:2]
            # w rogu okna; przy krawędzi kadru w strefie bezpiecznej (pod zakładkami platformy, z dala od brzegu)
            _podpis(d, tekst, max(x + 24 * s, m["l"]) if x == 0 else x + 24 * s,
                    max(y + 24 * s, m["gora"]) if y == 0 else y + 24 * s, rozm)
    elif uklad == "przed-po":
        if podpisy:
            _podpis(d, podpisy[0], m["l"], m["gora"], rozm)
        if len(podpisy) > 1:
            f = _font(rozm)
            l, t, r, b = d.textbbox((0, 0), podpisy[1], font=f)
            _podpis(d, podpisy[1], w - m["r"] - (r - l) - 1.1 * rozm, m["gora"], rozm)
    else:
        tlo_rgba = kolor(tlo)
        d.rectangle((0, 0, w, h), fill=tlo_rgba)
        for i, (x, y, sw, sh) in enumerate(sloty):
            ramka = sw * 0.045
            rr = sw * 0.13
            d.rounded_rectangle((x - ramka, y - ramka, x + sw + ramka, y + sh + ramka), radius=rr + ramka,
                                fill=(24, 25, 29, 255), outline=(70, 72, 80, 255), width=max(2, round(3 * s)))
            d.rounded_rectangle((x, y, x + sw, y + sh), radius=rr, fill=(0, 0, 0, 0))     # ekran: przezroczysty
            wy, ww_ = sw * 0.30, sw * 0.085                                                  # wycięcie na aparat
            d.rounded_rectangle((x + (sw - wy) / 2, y + sw * 0.035, x + (sw + wy) / 2, y + sw * 0.035 + ww_),
                                radius=ww_ / 2, fill=(0, 0, 0, 255))
            if i < len(podpisy) and podpisy[i]:
                _podpis(d, podpisy[i], x + sw / 2, y + sh + ramka + 28 * s, rozm, "mt")
    return img


def punkty_kreski(spec: str | None, sek: float) -> list[tuple[float, float]]:
    """Punkty (sekunda, udział B) przesuwu kreski przed/po, rosnąco po czasie."""
    if not spec:
        return [(0.0, 0.0), (0.15 * sek, 0.0), (0.4 * sek, 0.5), (0.6 * sek, 0.5), (0.85 * sek, 1.0), (sek, 1.0)]
    pts = []
    for part in spec.split(","):
        t, _, u = part.partition("=")
        try:
            pts.append((max(0.0, float(t)), min(1.0, max(0.0, float(u)))))
        except ValueError:
            raise SystemExit(f"--kreska {part!r}: podaj sekunda=udział (np. 2=0.5)") from None
    pts.sort()
    if not pts:
        raise SystemExit("--kreska: brak punktów")
    return pts


def wyrazenie_kreski(pts: list[tuple[float, float]]) -> str:
    """Udział B w chwili t (wyrażenie FFmpeg): płynnie (smoothstep) między punktami, stały przed i po nich."""
    expr = f"{pts[-1][1]:.4f}"
    for (t0, u0), (t1, u1) in reversed(list(zip(pts, pts[1:]))):
        if t1 <= t0:
            continue
        k = f"((t-{t0:.3f})/{t1 - t0:.3f})"
        expr = f"if(lt(t,{t1:.3f}),{u0:.4f}+({u1 - u0:.4f})*{k}*{k}*(3-2*{k}),{expr})"
    return f"if(lt(t,{pts[0][0]:.3f}),{pts[0][1]:.4f},{expr})"


def dlugosc(pliki: list[Path], sek: float | None) -> float:
    if sek:
        return sek
    filmy = [wl.duration(p) for p in pliki if not wl.is_image(p)]
    return round(max(filmy), 3) if filmy else SEK_ZDJECIA


def wejscie(p: Path, sek: float) -> list[str]:
    if wl.is_image(p):
        return ["-loop", "1", "-framerate", str(wl.FPS), "-t", f"{sek:.3f}", "-i", str(p)]
    return ["-i", str(p)]


def okno_filtr(i: int, p: Path, sw: int, sh: int, xy: tuple[float, float], sek: float) -> str:
    """Treść okna: przycięta do okna (bez rozciągania), HDR → zwykły obraz, krótsze nagranie trzyma ostatnią klatkę."""
    x, y = xy
    chain = (f"[{i}:v]scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,"
             f"crop={sw}:{sh}:x=(iw-{sw})*{x:.3f}:y=(ih-{sh})*{y:.3f},setsar=1")
    chain = wl.z_sdr(chain, "" if wl.is_image(p) else wl.sdr(p))
    return (f"{chain},fps={wl.FPS},tpad=stop_mode=clone:stop_duration={sek:.3f},trim=duration={sek:.3f},"
            f"setpts=PTS-STARTPTS,format=yuv420p[o{i}]")


def zrodlo_dzwieku(wybor: str, pliki: list[Path]) -> list[int]:
    ma = [not wl.is_image(p) and bool(wl.probe(p)["audio"]) for p in pliki]
    if wybor == "brak":
        return []
    if wybor == "a":
        return [0] if ma[0] else []
    if wybor == "b":
        return [1] if ma[1] else []
    if wybor == "oba":
        return [i for i in (0, 1) if ma[i]]
    return [0] if ma[0] else [1] if ma[1] else []          # auto


def bezruchy(plik: Path, sloty, sek: float, prog: float) -> list[tuple[float, float]]:
    """Chwile (od, do), w których żadne okno się nie rusza dłużej niż `prog` s (freezedetect na każdym oknie)."""
    okresy = []
    for (x, y, sw, sh) in sloty:
        r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(plik), "-vf",
                            f"crop={sw}:{sh}:{x}:{y},scale=320:-2,freezedetect=n=0.002:d={prog:.2f}", "-an", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        st = [float(v) for v in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
        en = [float(v) for v in re.findall(r"freeze_end: ([\d.]+)", r.stderr)]
        okresy.append([(a, en[i] if i < len(en) else sek) for i, a in enumerate(st)])
    if len(okresy) == 1:
        return okresy[0]
    wspolne = []
    for a0, a1 in okresy[0]:
        for b0, b1 in okresy[1]:
            o0, o1 = max(a0, b0), min(a1, b1)
            if o1 - o0 >= prog:
                wspolne.append((round(o0, 2), round(o1, 2)))
    return wspolne


def zloz(a: Path, b: Path, out: Path, uklad: str | None = None, fmt: str = "9:16", podpisy: list[str] | None = None,
         dzwiek: str = "auto", sek: float | None = None, kadr_a: str = "0.5,0.4", kadr_b: str = "0.5,0.4",
         kreska: str | None = None, tlo: str = "#0e0f13", kreska_kolor: str = "#ffffff",
         test_pauzy: bool = True) -> tuple[Path, dict]:
    w, h = wl.parse_format(fmt)
    uklad = uklad or ("gora-dol" if h > w else "obok")
    if uklad not in UKLADY:
        raise SystemExit(f"Nieznany układ {uklad!r}. Dostępne: {', '.join(UKLADY)}")
    podpisy = [p.strip() for p in (podpisy or []) if p.strip()]
    pliki = [a, b]
    for p in pliki:
        if not p.exists():
            raise SystemExit(f"Brak pliku: {p}")
        if not wl.is_image(p) and not wl.probe(p).get("video"):
            raise SystemExit(f"{p.name}: plik bez obrazu")
    sek = dlugosc(pliki, sek)
    sloty = okna(uklad, w, h)
    xy = [kadr_xy(kadr_a), kadr_xy(kadr_b)]
    audio = zrodlo_dzwieku(dzwiek, pliki)
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nakladka(uklad, w, h, sloty, podpisy, tlo, kreska_kolor).save(tmp / "nakladka.png")
        args = [*wejscie(a, sek), *wejscie(b, sek), "-loop", "1", "-framerate", str(wl.FPS), "-t", f"{sek:.3f}",
                "-i", str(tmp / "nakladka.png")]
        fc = [okno_filtr(i, p, sloty[i][2], sloty[i][3], xy[i], sek) for i, p in enumerate(pliki)]
        if uklad == "przed-po":
            from PIL import Image, ImageDraw
            maska = Image.new("L", (2 * w, h), 0)
            ImageDraw.Draw(maska).rectangle((w, 0, 2 * w, h), fill=255)
            maska.save(tmp / "maska.png")
            k = wl.even(max(2, min(w, h) * KRESKA))
            pasek = Image.new("RGBA", (k + 8, h), (0, 0, 0, 60))                 # kreska z cieniem po bokach
            ImageDraw.Draw(pasek).rectangle((4, 0, 4 + k - 1, h), fill=kolor(kreska_kolor))
            pasek.save(tmp / "kreska.png")
            args += ["-loop", "1", "-framerate", str(wl.FPS), "-t", f"{sek:.3f}", "-i", str(tmp / "maska.png"),
                     "-loop", "1", "-framerate", str(wl.FPS), "-t", f"{sek:.3f}", "-i", str(tmp / "kreska.png")]
            u = wyrazenie_kreski(punkty_kreski(kreska, sek))
            fc += [f"[3:v]format=gray,crop={w}:{h}:x='{w}*({u})':y=0[m]",           # biel z prawej od kreski = B
                   "[o1][m]alphamerge[ob]", "[o0][ob]overlay=0:0[p1]",
                   f"[p1][4:v]overlay=x='{w}*(1-({u}))-{(k + 8) / 2:.1f}':y=0[p2]",
                   f"[p2][2:v]overlay=0:0,{wl.TV_RANGE}[v]"]
        else:
            tlo_ff = "0x" + tlo.strip().lstrip("#")
            fc += [f"color=c={tlo_ff}:s={w}x{h}:r={wl.FPS}:d={sek:.3f}[bg]",
                   f"[bg][o0]overlay={sloty[0][0]}:{sloty[0][1]}[p0]",
                   f"[p0][o1]overlay={sloty[1][0]}:{sloty[1][1]}[p1]",
                   f"[p1][2:v]overlay=0:0,{wl.TV_RANGE}[v]"]
        maps = ["-map", "[v]"]
        if len(audio) == 2:
            fc.append("[0:a][1:a]amix=inputs=2:duration=longest:normalize=1,apad[a]")
            maps += ["-map", "[a]"]
        elif audio:
            fc.append(f"[{audio[0]}:a]apad[a]")
            maps += ["-map", "[a]"]
        wl.run(["ffmpeg", "-y", *args, "-filter_complex", ";".join(fc), *maps, "-t", f"{sek:.3f}", *ENC, str(out)])
    stats = {"uklad": uklad, "format": fmt, "rozmiar": f"{w}x{h}", "sek": round(wl.duration(out), 2),
             "okna": [list(s) for s in sloty[:1 if uklad == "przed-po" else 2]],
             "dzwiek": "brak" if not audio else "oba" if len(audio) == 2 else "ab"[audio[0]], "uwagi": []}
    if test_pauzy:
        prog = BEZRUCH["przed-po" if uklad == "przed-po" else "split"]
        stoi = bezruchy(out, sloty[:1] if uklad == "przed-po" else sloty, sek, prog)
        if stoi:
            stats["uwagi"].append("test pauzy: w " + ", ".join(f"{a:.1f}–{b:.1f} s" for a, b in stoi)
                                  + " nic się nie rusza w żadnym oknie; dodaj ruch (nagranie, przewijanie, kreska) "
                                    "albo skróć film")
    return out, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", help="lewe / górne okno albo „przed” (nagranie lub zdjęcie)")
    ap.add_argument("b", help="prawe / dolne okno albo „po”")
    ap.add_argument("-o", required=True)
    ap.add_argument("--uklad", choices=UKLADY, default=None, help="domyślnie: pion → gora-dol, poziom/kwadrat → obok")
    ap.add_argument("--format", default="9:16")
    ap.add_argument("--podpisy", nargs="+", default=[], metavar="TEKST", help="podpis okna A, potem B (krótko: 1–3 słowa)")
    ap.add_argument("--dzwiek", choices=["auto", "a", "b", "oba", "brak"], default="auto")
    ap.add_argument("--sek", type=float, default=None, help="długość filmu (domyślnie dłuższe nagranie)")
    ap.add_argument("--kadr-a", default="0.5,0.4", help="środek przycięcia A: x,y (0–1)")
    ap.add_argument("--kadr-b", default="0.5,0.4", help="środek przycięcia B: x,y (0–1)")
    ap.add_argument("--kreska", default=None, help="przed-po: punkty sekunda=udział B, np. 0=0,2=0.5,4=0.5,6=1")
    ap.add_argument("--tlo", default="#0e0f13", help="tło telefonów (#rrggbb)")
    ap.add_argument("--kolor", default="#ffffff", help="kolor kreski podziału (#rrggbb)")
    ap.add_argument("--bez-testu", action="store_true", help="bez testu pauzy (szybciej)")
    args = ap.parse_args(argv)
    wl.need("ffmpeg")
    try:
        out, stats = zloz(Path(args.a), Path(args.b), Path(args.o), args.uklad, args.format, args.podpisy, args.dzwiek,
                          args.sek, args.kadr_a, args.kadr_b, args.kreska, args.tlo, args.kolor, not args.bez_testu)
    except wl.FFError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"plik": out.as_posix(), **stats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
