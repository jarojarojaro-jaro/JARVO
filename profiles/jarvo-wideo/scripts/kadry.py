#!/usr/bin/env python3
"""Klatki do oceny okiem (vision_analyze) i cięcia ujęć: arkusz klatek z wielu klipów, lista zmian scen.

    python3 kadry.py arkusz klip1.mp4 [klip2.mp4 …] [--klatek 4] [-o out/wideo/kandydaci.jpg]
    python3 kadry.py sceny nagranie.mp4 [--prog 0.35] [--json]
    python3 kadry.py wzor film-wzor.mp4 [--fps 2] [-o out/wideo/wzor] [--prog 5] [--przerwa 12] [--bez-ruchu]

arkusz: każdy klip = jeden rząd klatek (równo rozłożonych), podpisany numerem klipu i czasem, żeby
w jednym obrazie porównać kandydatów na ujęcie (ostrość, kadr, znak wodny, tekst, pasuje do sceny?).
sceny: momenty cięć montażowych w gotowym nagraniu (do klipów z długiego materiału i wyboru fragmentów).
wzor: film, który ma być wzorem („zrób coś takiego dla naszego produktu”): arkusze klatek co 1/fps s z czasem
w rogu (do vision), cięcia i rytm muzyki (rytm.py) w wzor.json. Do tego rozbiór ruchu (za breakdown.py
z huashu-art-motion, MIT; kod własny): starty przejść z różnicy klatek, siatka, na którą padają (największy krok
przy ≥ 80% startów w 1,5 klatki; tempo, gdy krok to ósemka albo ćwierćnuta), arkusz każdego przejścia co 2 klatki
(`przejscia/P01.jpg`), mapa ruchu odcinków (`ruch-1.jpg`: na czerwono, co się rusza między przejściami, i jaka część
kadru) i klatki kluczowe (ostatnia klatka odcinka: `kluczowe-1.jpg`, pełny kadr `ref/odc01.png` jako referencja
kompozycji dla modelu obrazu). Z tego rozpisujesz mapę bitów: przejścia, ruch kamery, kolory, fonty, co na którym
takcie; przenosisz strukturę, nigdy treści, logo ani assetów.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import narzedzia as nz  # noqa: E402
import wideo_lib as wl  # noqa: E402

PROG_PRZEJSCIA = 5.0    # średnia różnica szarości (kadr 192 px) między klatkami: spokój < 2, przejście 10–40
PRZERWA_KLATEK = 12     # kolejny start przejścia najwcześniej po tylu klatkach (jedno przejście = jeden start)
BEZ_ZMIAN = 0.5         # różnica poniżej = sąsiednie klatki bez zmiany (szum kompresji)
PROG_RUCHU = 25         # piksel rusza się, gdy w odcinku zmieni kolor o więcej (0–255)
NA_ARKUSZ = 16          # odcinków na arkusz mapy ruchu i klatek kluczowych (4 × 4)


def contact_rows(videos: list[Path], per: int, out: Path, cell_w: int = 240) -> Path:
    with tempfile.TemporaryDirectory(prefix="jarvo-kadry-") as tmp:
        tdir = Path(tmp)
        n = 0
        for vi, video in enumerate(videos, 1):
            info = wl.probe(video)
            v = info["video"] or {}
            ratio = (v.get("height") or 9) / (v.get("width") or 16)
            cell_h = wl.even(min(cell_w * ratio, cell_w * 1.8))
            dur = info["duration"] or 1.0
            times = [0.2] if wl.is_image(video) else [dur * (k + 0.5) / per for k in range(per)]
            for k in range(per):
                t = times[min(k, len(times) - 1)]
                label = f"{vi}.{k + 1} {t:.1f}s"
                base = (f"scale={cell_w}:{cell_h}:force_original_aspect_ratio=decrease,{v.get('sdr') + ',' if v.get('sdr') else ''}"
                        f"pad={cell_w}:{wl.even(cell_w * 1.8)}:(ow-iw)/2:(oh-ih)/2:color=0x15171C")
                cell = tdir / f"c{n:03d}.png"
                seek = [] if wl.is_image(video) else ["-ss", f"{t:.2f}"]
                try:
                    wl.run(["ffmpeg", "-y", *seek, "-i", str(video), "-frames:v", "1", "-vf",
                            base + f",drawtext=text='{label}'{wl.drawtext_kroj()}:x=6:y=6:fontsize=16:fontcolor=white:box=1:boxcolor=0xD62D20:boxborderw=4",
                            str(cell)])
                except wl.FFError:
                    wl.run(["ffmpeg", "-y", *seek, "-i", str(video), "-frames:v", "1", "-vf", base, str(cell)])
                n += 1
        out.parent.mkdir(parents=True, exist_ok=True)
        wl.run(["ffmpeg", "-y", "-framerate", "1", "-i", str(tdir / "c%03d.png"), "-vf",
                f"tile={per}x{len(videos)}:padding=4:color=0x0B0D12", "-frames:v", "1", "-q:v", "3", str(out)])
    return out


def scene_changes(video: Path, threshold: float) -> list[float]:
    res = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(video), "-an", "-vf",
                          f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", res.stderr)]


def starty_przejsc(roznice: list[float], prog: float = PROG_PRZEJSCIA, przerwa: int = PRZERWA_KLATEK) -> list[int]:
    """Klatki, w których zaczyna się przejście: różnica do następnej klatki przekracza próg po spokojnej klatce."""
    starty: list[int] = []
    for i in range(1, len(roznice)):
        if roznice[i] > prog and roznice[i - 1] <= prog and (not starty or i - starty[-1] > przerwa):
            starty.append(i)
    return starty


def _szukaj(pkt: list[float], krok_od: float, krok_do: float, tolerancja: float, udzial: float):
    """Największy krok z [krok_od, krok_do] (siatka kroków 4,00 + j·0,01 klatki), przy którym ≥ udzial punktów leży w tolerancji od siatki
    t0 + k·krok, t0 = jeden z trzech pierwszych punktów; przy tym kroku t0 z największą liczbą punktów wewnętrznych.
    Z numpy liczy całe pasma kroków naraz, bez niego punkt po punkcie z wczesnym wyjściem."""
    n, wymagane = len(pkt), udzial * len(pkt)
    if krok_do < krok_od:
        return None
    j_max, j_min = int(round((krok_do - 4.0) / 0.01)), max(0, math.ceil(round((krok_od - 4.0) / 0.01, 6)))
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        p = np.asarray(pkt)
        for gora in range(j_max, j_min - 1, -4000):
            kroki = 4.0 + np.arange(gora, max(j_min, gora - 3999) - 1, -1) * 0.01
            najl = None
            for t0 in pkt[:3]:
                k = np.round((p[None, :] - t0) / kroki[:, None])
                ile = (np.abs(p[None, :] - (t0 + k * kroki[:, None])) <= tolerancja).sum(axis=1)
                dobre = np.nonzero(ile >= wymagane)[0]
                if dobre.size and (najl is None or dobre[0] < najl[0] or (dobre[0] == najl[0] and ile[dobre[0]] > najl[1])):
                    najl = (int(dobre[0]), int(ile[dobre[0]]), t0)
            if najl:
                krok, t0 = float(kroki[najl[0]]), najl[2]
                k = [round((x - t0) / krok) for x in pkt]
                return krok, k, [abs(x - (t0 + kk * krok)) <= tolerancja for x, kk in zip(pkt, k)]
        return None
    wolno_poza = n - wymagane
    for j in range(j_max, j_min - 1, -1):
        krok = 4.0 + j * 0.01
        najl = None
        for t0 in pkt[:3]:
            poza = 0
            for x in pkt:
                if abs(x - (t0 + round((x - t0) / krok) * krok)) > tolerancja:
                    poza += 1
                    if poza > wolno_poza:
                        break
            else:
                if najl is None or poza < najl[0]:
                    najl = (poza, t0)
        if najl:
            t0 = najl[1]
            k = [round((x - t0) / krok) for x in pkt]
            return krok, k, [abs(x - (t0 + kk * krok)) <= tolerancja for x, kk in zip(pkt, k)]
    return None


def _losowe_starty(los, n: int, od: int, do: int, przerwa: int) -> list[float]:
    """n startów rozłożonych losowo w [od, do], co najmniej `przerwa` + 1 klatki od siebie (jak po wykrywaniu)."""
    luz = do - od - (n - 1) * (przerwa + 1)
    if luz < 0:
        przerwa, luz = 0, max(0, do - od - (n - 1))
    return [float(od + x + i * (przerwa + 1)) for i, x in enumerate(sorted(los.randint(0, luz) for _ in range(n)))]


def siatka(starty: list[int], fps: float, bpm_muzyki: float | None = None, tolerancja: float = 1.5,
           udzial: float = 0.8, krok_min: float = 4.0, przerwa: int = PRZERWA_KLATEK, proby: int = 40) -> dict | None:
    """Siatka, na którą padają starty przejść: start ≈ t0 + k·krok. Bierze NAJWIĘKSZY krok, przy którym ≥ 80% startów
    leży w 1,5 klatki od siatki (mały krok dopasuje wszystko na siłę), resztę oznacza jako odstające (duży ruch
    w ujęciu wzięty za przejście); krok i t0 dopasowane potem najmniejszymi kwadratami po punktach wewnętrznych.
    `przypadek`: jaka część losowych układów startów (ta sama liczba, ten sam odcinek filmu, ta sama przerwa) daje
    równie duży krok; przy kilku startach siatka bywa przypadkowa, wtedy `pewna` = false (chyba że krok pasuje do
    tempa muzyki)."""
    if len(starty) < 4:
        return None
    pkt = [float(x) for x in starty]
    maks = max(b - a for a, b in zip(pkt, pkt[1:]))
    znalezione = _szukaj(pkt, krok_min, maks, tolerancja, udzial)
    if not znalezione:
        return None
    krok_szukany, k, wew = znalezione
    xs = [kk for kk, w in zip(k, wew) if w]
    ys = [x for x, w in zip(pkt, wew) if w]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    krok = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else krok_szukany
    t0 = my - krok * mx
    kmin = min(k)
    k = [kk - kmin for kk in k]
    t0 += kmin * krok
    blad = max(abs(y - (t0 + (x - kmin) * krok)) for x, y in zip(xs, ys))
    if (2 * tolerancja + 1) / krok_szukany >= 0.5:          # okno tolerancji to pół kroku: trafi wszystko
        przypadek = 1.0
    else:
        import random
        los = random.Random(len(pkt) * 1_000_003 + int(sum(pkt)))
        trafione = 0
        for _ in range(proby):
            lp = _losowe_starty(los, len(pkt), int(pkt[0]), int(pkt[-1]), przerwa)
            lmaks = max(b - a for a, b in zip(lp, lp[1:]))
            trafione += bool(_szukaj(lp, krok_szukany * 0.98, lmaks, tolerancja, udzial))
        przypadek = trafione / proby
    wynik = {"t0_klatka": round(t0, 2), "t0_s": round(t0 / fps, 3), "krok_klatek": round(krok, 3),
             "krok_s": round(krok / fps, 4), "max_blad_klatek": round(blad, 2), "jednostki": k,
             "odcinki_w_krokach": [b - a for a, b in zip(k, k[1:])],
             "odstajace": [i for i, w in enumerate(wew) if not w],
             "bpm_gdy_osemka": round(60 * fps / krok / 2, 2), "bpm_gdy_cwiercnuta": round(60 * fps / krok, 2),
             "przypadek": round(przypadek, 3), "pewna": przypadek <= 0.05}
    if bpm_muzyki:
        for nazwa, bpm in (("ósemka", wynik["bpm_gdy_osemka"]), ("ćwierćnuta", wynik["bpm_gdy_cwiercnuta"]),
                           ("pół taktu", wynik["bpm_gdy_cwiercnuta"] * 2), ("szesnastka", wynik["bpm_gdy_osemka"] / 2)):
            if abs(bpm - bpm_muzyki) <= 0.02 * bpm_muzyki:
                wynik["krok_w_muzyce"] = f"{nazwa} przy {bpm_muzyki:g} BPM"
                wynik["pewna"] = True
                break
        else:
            wynik["krok_w_muzyce"] = None
    return wynik


def rozmiar_analizy(w: int, h: int, dluzszy: int) -> tuple[int, int]:
    return (dluzszy, wl.even(dluzszy * h / w)) if w >= h else (wl.even(dluzszy * w / h), dluzszy)


def strumien(video: Path, w: int, h: int, sdr: str = "", szary: bool = False):
    """Klatki filmu jako tablice numpy, po jednej (bez trzymania całego filmu w pamięci)."""
    import numpy as np
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-vf", wl.z_sdr(f"scale={w}:{h}", sdr),
                             "-f", "rawvideo", "-pix_fmt", "gray" if szary else "rgb24", "-"], stdout=subprocess.PIPE)
    n = w * h * (1 if szary else 3)
    try:
        while True:
            buf = proc.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape((h, w) if szary else (h, w, 3))
    finally:
        proc.stdout.close()
        proc.wait()


def _arkusze(obrazy: list, out_dir: Path, nazwa: str, kolumny: int = 4) -> list[str]:
    from PIL import Image
    pliki = []
    for nr, od in enumerate(range(0, len(obrazy), NA_ARKUSZ), 1):
        part = obrazy[od:od + NA_ARKUSZ]
        cw, ch = part[0].size
        ark = Image.new("RGB", (min(kolumny, len(part)) * cw, ((len(part) + kolumny - 1) // kolumny) * ch), "#0b0d12")
        for i, im in enumerate(part):
            ark.paste(im, ((i % kolumny) * cw, (i // kolumny) * ch))
        dest = out_dir / f"{nazwa}-{nr}.jpg"
        ark.save(dest, quality=85)
        pliki.append(str(dest))
    return pliki


def _pl(x: float, miejsc: int = 2) -> str:
    return f"{x:.{miejsc}f}".replace(".", ",")


def _podpis(rys, xy: tuple[int, int], tekst: str, font, kolor: str = "#ffffff") -> None:
    x, y = xy
    l, t, r, b = rys.textbbox((x, y), tekst, font=font)
    rys.rectangle((l - 3, t - 2, r + 3, b + 2), fill="#000000")
    rys.text((x, y), tekst, fill=kolor, font=font)


def rozbior(video: Path, out_dir: Path, info: dict, prog: float = PROG_PRZEJSCIA, przerwa: int = PRZERWA_KLATEK,
            bpm_muzyki: float | None = None) -> dict:
    """Ruch filmu-wzoru: starty przejść i ich siatka, arkusz każdego przejścia, mapa ruchu odcinków, klatki kluczowe."""
    import numpy as np
    from PIL import Image, ImageDraw
    v = info["video"] or {}
    w, h, fps, sdr = v.get("width") or 1920, v.get("height") or 1080, v.get("fps") or 30.0, v.get("sdr") or ""
    # 1) różnice sąsiednich klatek w szarości (kadr 192 px) → starty przejść
    roznice, poprz = [], None
    for f in strumien(video, *rozmiar_analizy(w, h, 192), sdr, szary=True):
        f = f.astype(np.int16)
        if poprz is not None:
            roznice.append(float(np.abs(f - poprz).mean()))
        poprz = f
    n = len(roznice) + 1
    starty = starty_przejsc(roznice, prog, przerwa)
    granice = [0, *starty, n]
    odcinki = []
    for i in range(len(granice) - 1):
        a0 = granice[i] + (round(0.35 * fps) if i else 0)        # po przejściu: 0,35 s na uspokojenie
        b0 = granice[i + 1] - 2
        odcinki.append({"nr": i + 1, "od": round(granice[i] / fps, 3), "do": round(granice[i + 1] / fps, 3),
                        "sek": round((granice[i + 1] - granice[i]) / fps, 3), "a0": a0, "b0": b0,
                        "ref_klatka": max(granice[i], granice[i + 1] - 3)})
    # 2) jedno przejście klatek w kolorze (kadr 480 px): mapy ruchu, klatki kluczowe, arkusze przejść
    mw, mh = rozmiar_analizy(w, h, 480)
    pw, ph = rozmiar_analizy(w, h, 384)
    font, font_m = wl.czcionka(16), wl.czcionka(14)
    (out_dir / "przejscia").mkdir(parents=True, exist_ok=True)
    potrzebne: dict[int, list[tuple[int, int]]] = {}
    for t, s0 in enumerate(starty):
        for c, f in enumerate(range(s0 - 2, s0 + 28, 2)):
            if 0 <= f < n:
                potrzebne.setdefault(f, []).append((t, c))
    otwarte: dict = {}
    arkusze_przejsc: dict[int, str] = {}

    def zamknij(t: int) -> None:
        dest = out_dir / "przejscia" / f"P{t + 1:02d}.jpg"
        otwarte.pop(t).save(dest, quality=85)
        arkusze_przejsc[t] = str(dest)

    ref_nr = {o["ref_klatka"]: o for o in odcinki}
    mapy, kluczowe = [], []
    seg, baza, mx, poprz = 0, None, None, None
    for j, f in enumerate(strumien(video, mw, mh, sdr)):
        while seg < len(odcinki) and j >= odcinki[seg]["b0"]:
            seg += 1
            baza = mx = poprz = None
        if seg < len(odcinki) and odcinki[seg]["b0"] - odcinki[seg]["a0"] >= 4 and j >= odcinki[seg]["a0"]:
            o = odcinki[seg]
            fi = f.astype(np.int16)
            if baza is None:
                baza, mx = f.copy(), np.zeros((mh, mw), np.float32)
            else:
                np.maximum(mx, np.abs(fi - poprz).mean(axis=2), out=mx)
            poprz = fi
            if j == o["b0"] - 1:
                o["ruch_proc"] = round(float((mx > PROG_RUCHU).mean()) * 100, 1)
                tlo = Image.fromarray(baza).convert("L").convert("RGB")
                czer = np.zeros((mh, mw, 3), np.uint8)
                czer[..., 0] = np.clip(mx * 4, 0, 255).astype(np.uint8)
                im = Image.blend(tlo, Image.fromarray(czer), 0.6)
                _podpis(ImageDraw.Draw(im), (6, 6), f"odc. {o['nr']} · {_pl(o['a0'] / fps)}–{_pl(o['b0'] / fps)} s · "
                        f"ruch {_pl(o['ruch_proc'], 1)}%", font, "#ffd84d")
                mapy.append(im)
        if j in ref_nr:
            o = ref_nr[j]
            im = Image.fromarray(f.copy())
            _podpis(ImageDraw.Draw(im), (6, 6), f"odc. {o['nr']} · kl. {j} · {_pl(j / fps)} s", font)
            kluczowe.append(im)
        for t, c in potrzebne.get(j, []):
            ark = otwarte.setdefault(t, Image.new("RGB", (5 * pw, 3 * (ph + 20)), "#0b0d12"))
            x, y = (c % 5) * pw, (c // 5) * (ph + 20)
            ark.paste(Image.fromarray(f).resize((pw, ph)), (x, y + 20))
            _podpis(ImageDraw.Draw(ark), (x + 4, y + 2), f"{j - starty[t]:+d} kl. · {_pl(j / fps, 3)} s", font_m,
                    "#ffd84d" if j == starty[t] else "#ffffff")
            if c == 14 or j >= n - 1:
                zamknij(t)
    for t in list(otwarte):
        zamknij(t)
    # 3) klatki kluczowe w pełnym kadrze (referencja kompozycji dla modelu obrazu)
    (out_dir / "ref").mkdir(exist_ok=True)
    for stary in (out_dir / "ref").glob("odc*.png"):
        stary.unlink()
    wybor = "+".join(f"eq(n\\,{o['ref_klatka']})" for o in odcinki)
    try:
        wl.run(["ffmpeg", "-y", "-nostdin", "-i", str(video), "-vf", wl.z_sdr(f"select='{wybor}'", sdr), "-fps_mode", "passthrough",
                str(out_dir / "ref" / "odc%02d.png")])
    except wl.FFError:
        pass
    for o in odcinki:
        ref = out_dir / "ref" / f"odc{o['nr']:02d}.png"
        o["ref"] = str(ref) if ref.exists() else None
        for klucz in ("a0", "b0"):
            o.pop(klucz)
        o.setdefault("ruch_proc", None)
    return {"fps": fps, "klatek": n, "kadr": [w, h],
            "bez_zmian_proc": round(sum(r < BEZ_ZMIAN for r in roznice) / max(1, len(roznice)) * 100, 1),
            "przejscia": [{"nr": t + 1, "klatka": s0, "s": round(s0 / fps, 3), "arkusz": arkusze_przejsc.get(t)}
                          for t, s0 in enumerate(starty)],
            "siatka": siatka(starty, fps, bpm_muzyki), "odcinki": odcinki,
            "sr_odcinek_s": round(sum(o["sek"] for o in odcinki) / len(odcinki), 3),
            "mapy_ruchu": _arkusze(mapy, out_dir, "ruch") if mapy else [],
            "kluczowe": _arkusze(kluczowe, out_dir, "kluczowe") if kluczowe else [],
            "progi": {"przejscie": prog, "przerwa_klatek": przerwa, "ruch_piksela": PROG_RUCHU, "bez_zmian": BEZ_ZMIAN}}


def reference(video: Path, fps: float, out_dir: Path, per_sheet: int = 40, cols: int = 8, ruch: bool = True,
              prog: float = PROG_PRZEJSCIA, przerwa: int = PRZERWA_KLATEK) -> dict:
    """Film-wzór → arkusze klatek (czas w rogu), cięcia, rytm i rozbiór ruchu."""
    info = wl.probe(video)
    dur = info["duration"] or 0.0
    v = info["video"] or {}
    ratio = (v.get("height") or 9) / (v.get("width") or 16)
    cw = 240
    ch = wl.even(cw * ratio)
    n = max(1, int(dur * fps))
    out_dir.mkdir(parents=True, exist_ok=True)
    sheets = []
    for k, first in enumerate(range(0, n, per_sheet)):
        cnt = min(per_sheet, n - first)
        rows = (cnt + cols - 1) // cols
        dest = out_dir / f"wzor-{k + 1}.jpg"
        base = wl.z_sdr(f"fps={fps},scale={cw}:{ch}", v.get("sdr") or "")    # wzór w HDR: klatki po przeliczeniu
        label = (f",drawtext=text='%{{pts\\:hms\\:{first / fps:.3f}}}'{wl.drawtext_kroj()}:x=4:y=4:fontsize=14:"
                 "fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=3")
        tile = f",tile={cols}x{rows}:padding=4:color=0x0B0D12"
        common = ["ffmpeg", "-y", "-ss", f"{first / fps:.3f}", "-t", f"{cnt / fps:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "3"]
        try:
            wl.run(common[:-4] + ["-vf", base + label + tile] + common[-4:] + [str(dest)])
        except wl.FFError:   # bez fontu do drawtext: arkusz bez czasu (czas = kolejność × 1/fps od początku arkusza)
            wl.run(common[:-4] + ["-vf", base + tile] + common[-4:] + [str(dest)])
        sheets.append({"plik": dest.as_posix(), "od": round(first / fps, 2), "do": round((first + cnt) / fps, 2)})
    res = {"film": Path(video).as_posix(), "sek": round(dur, 2), "co_s": round(1 / fps, 3), "arkusze": sheets,
           "ciecia": scene_changes(video, 0.35)}
    if info.get("audio"):
        try:
            import rytm
            r = rytm.analyze(video)
            res["rytm"] = {k: r[k] for k in ("bpm", "pierwszy_bit", "takty", "drop")}
        except SystemExit:
            pass
    if ruch and not wl.is_image(video):
        res.update(rozbior(video, out_dir, info, prog, przerwa, (res.get("rytm") or {}).get("bpm")))
    (out_dir / "wzor.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("arkusz")
    a.add_argument("pliki", nargs="+")
    a.add_argument("--klatek", type=int, default=4)
    a.add_argument("-o", default="out/wideo/kandydaci.jpg")
    s = sub.add_parser("sceny")
    s.add_argument("plik")
    s.add_argument("--prog", type=float, default=0.35, help="czułość cięć 0–1 (niżej = więcej cięć)")
    s.add_argument("--json", action="store_true")
    w = sub.add_parser("wzor")
    w.add_argument("plik")
    w.add_argument("--fps", type=float, default=2.0, help="klatek na sekundę wzoru (2 = co 0,5 s)")
    w.add_argument("-o", default="out/wideo/wzor", help="katalog na arkusze i wzor.json")
    w.add_argument("--prog", type=float, default=PROG_PRZEJSCIA, help="próg różnicy klatek dla startu przejścia "
                   "(spokój < 2, przejście 10–40; niżej = więcej startów)")
    w.add_argument("--przerwa", type=int, default=PRZERWA_KLATEK, help="najmniej klatek między startami przejść")
    w.add_argument("--bez-ruchu", action="store_true", help="bez rozbioru ruchu (same arkusze, cięcia, rytm)")
    args = ap.parse_args(argv)
    wl.need("ffmpeg")
    try:
        if args.cmd == "arkusz":
            vids = [Path(p) for p in args.pliki]
            missing = [str(p) for p in vids if not p.exists()]
            if missing:
                raise SystemExit(f"Brak plików: {', '.join(missing)}")
            out = contact_rows(vids, max(1, min(args.klatek, 8)), Path(args.o))
            print(f"Arkusz: {out}  (rząd N = klip N: " + ", ".join(f"{i}={p.name}" for i, p in enumerate(vids, 1)) + ")")
            return 0
        if args.cmd == "wzor":
            ruch = not args.bez_ruchu and nz.wymagaj_modulow(__file__, "JARVO_KADRY_REEXEC")
            r = reference(Path(args.plik), max(0.25, min(args.fps, 10)), Path(args.o), ruch=ruch, prog=args.prog,
                          przerwa=max(1, args.przerwa))
            print(f"Wzór {r['sek']} s: {len(r['arkusze'])} arkuszy (klatka co {r['co_s']} s), {len(r['ciecia'])} cięć")
            for sh in r["arkusze"]:
                print(f"  {sh['plik']}  ({sh['od']}–{sh['do']} s)")
            if r.get("rytm"):
                print(f"  rytm: {r['rytm']['bpm']} BPM, drop {r['rytm']['drop']} s")
            if "przejscia" in r:
                print(f"  przejścia: {len(r['przejscia'])} (starty: " + ", ".join(f"{p['s']:g}" for p in r["przejscia"][:12])
                      + (" …" if len(r["przejscia"]) > 12 else "") + f" s), średni odcinek {r['sr_odcinek_s']} s, "
                      f"sąsiednie klatki bez zmiany: {r['bez_zmian_proc']}%")
                sg = r.get("siatka")
                if sg:
                    print(f"  siatka: krok {sg['krok_klatek']} kl. = {sg['krok_s']} s (ósemka przy {sg['bpm_gdy_osemka']} BPM "
                          f"albo ćwierćnuta przy {sg['bpm_gdy_cwiercnuta']}), błąd do {sg['max_blad_klatek']} kl., "
                          f"odcinki w krokach {sg['odcinki_w_krokach']}, odstające starty: {sg['odstajace'] or 'brak'}"
                          + (f"; w muzyce: {sg['krok_w_muzyce'] or 'nie pasuje do tempa'}" if "krok_w_muzyce" in sg else "")
                          + ("" if sg["pewna"] else f"; NIEPEWNA: losowe starty dają taki krok w {round(sg['przypadek'] * 100)}% "
                             "prób, tempo bierz z muzyki (rytm.py), nie z tej siatki"))
                elif len(r["przejscia"]) >= 4:
                    print("  siatka: starty nie leżą na wspólnej siatce (montaż nie do bitu albo próg za niski)")
                ruchy = [o["ruch_proc"] for o in r["odcinki"] if o["ruch_proc"] is not None]
                print(f"  mapa ruchu: {', '.join(r['mapy_ruchu']) or 'brak (odcinki za krótkie)'}"
                      + (f" (rusza się {min(ruchy)}–{max(ruchy)}% kadru)" if ruchy else ""))
                print(f"  klatki kluczowe: {', '.join(r['kluczowe'])}; pełny kadr w {Path(args.o) / 'ref'}/")
                if r["przejscia"]:
                    print(f"  przejścia klatka po klatce: {Path(args.o) / 'przejscia'}/P01.jpg …")
            elif not args.bez_ruchu:
                print("  rozbiór ruchu pominięty: brak numpy/Pillow (python3 $HERMES_HOME/scripts/narzedzia.py instaluj html)")
            print(f"  → {Path(args.o) / 'wzor.json'}: rozpisz mapę bitów (przejścia, kamera, kolory, fonty) i przenieś na produkt")
            return 0
        cuts = scene_changes(Path(args.plik), args.prog)
        dur = wl.duration(Path(args.plik))
        bounds = [0.0] + cuts + [round(dur, 2)]
        shots = [{"nr": i + 1, "od": bounds[i], "do": bounds[i + 1], "sek": round(bounds[i + 1] - bounds[i], 2)}
                 for i in range(len(bounds) - 1) if bounds[i + 1] - bounds[i] > 0.05]
        if args.json:
            print(json.dumps({"ciecia": cuts, "ujecia": shots}, ensure_ascii=False, indent=1))
        else:
            for sh in shots:
                print(f"{sh['nr']:>3}. {sh['od']:>7.2f}–{sh['do']:<7.2f} ({sh['sek']} s)")
        return 0
    except wl.FFError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
