#!/usr/bin/env python3
"""Krótki film z planu (plan.json): lektor PL → ujęcia (stock, pliki, AI, kolor) → napisy z czasu słów → muzyka → MP4.

    python3 film.py sprawdz plan.json                        # walidacja i szacunek długości, bez renderu
    python3 film.py render plan.json [--szkic] [--format 9:16,16:9] [--wariant B | --wszystkie] [--out out/wideo]
    python3 film.py lektor "Tekst lektora." -o lektor.mp3 [--glos pl-PL-ZofiaNeural] [--tempo +5%]
    python3 film.py narracja narracja.txt -o src/lektor.wav [--os src/anim/os_czasu.json] [--cel 60-90] [--sprawdz]
                             [--fakty src/fakty.json] [--wymowa wymowa.json]
    python3 film.py glosy                                    # głosy: lokalne (Matcha PL, Paradee EN) i Edge TTS
    python3 film.py cache [--starsze-niz 14]                 # rozmiar cache i sprzątanie

Format planu: skill krotki-film, plik references/plan.md. Każdy etap ma cache (lektor, pobrane ujęcia, sceny
po normalizacji), więc warianty i poprawki renderują się szybko, a drugi render tego samego planu nie pobiera
niczego z sieci. `--szkic` = połowa rozdzielczości i szybkie kodowanie: do sprawdzenia rytmu przed finałem.
Wynik: <out>/<slug>/<slug>[-wariant]-<format>.mp4, .srt, miniatura, film.json (sceny, źródła, licencje, czasy).

`narracja`: lektor filmu z kodu z pliku narracji (zdanie w linii, pusty wiersz = nowe ujęcie, `# tytuł` = rozdział,
`|` = podział napisu, `{nazwa}` = chwila przed słowem). Zdania syntezowane osobno, wycięte do słyszalnej mowy i ułożone
z pauzami (w akapicie 0,33 s, między akapitami 1 s, przed rozdziałem 1,5 s): jeden plik lektora, `os_czasu.json`
(zdania, ujęcia, rozdziały, napisy, chwile po nazwie dla `bit()` z `/_lib/jarvo/os_czasu.js`), słowa z czasem i SRT.
Nowe nagranie lektora = nowa oś, animacja idzie za nią sama. Z `fakty.json` (brief Sherlocka) liczba lektora
z listy niepewnych zatrzymuje syntezę, a liczba bez źródła daje ostrzeżenie; słowniczek briefu i `--wymowa` mówią
lektorowi, jak czytać termin („Next.js” → „nekst dżej es”), a napisy zostają w pisowni z tekstu.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

WORDS_PER_SEC = 2.5          # tempo lektora po polsku przy +0%, Edge i Matcha (do szacunku bez syntezy)
SCENE_GAP = 0.18             # oddech między scenami
TAIL = 0.6                   # zapas na końcu filmu
MIN_SCENE = 1.2
# ruch kamery na zdjęciu (Ken Burns) → największe powiększenie kadru; zdjęcie mniejsze niż wyjście × powiększenie
# jest rozciągane i miękkie (zrzut strony robimy w 2×)
RUCH_ZOOM = {"zoom": 1.12, "oddal": 1.12, "panorama": 1.10, "brak": 1.0}
XFADE = 0.35                 # przenikanie
PLATFORM_MAX = {"9:16": 90, "1:1": 120, "4:5": 120, "16:9": 600}   # rozsądna górna granica krótkiego formatu
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")          # libass nie rysuje emoji (puste kratki)
KNOWLEDGE = Path(os.environ.get("JARVO_KNOWLEDGE_DIR", "/opt/data/jarvo/knowledge"))
# podkłady CC0 z biblioteki edytora HQ (scripts/dzwieki.py): zapas dla „losowej”, gdy skarbiec nie ma muzyki
_HERE = Path(__file__).resolve().parent
BIBLIOTEKA_MUZYKI = next((d for d in (_HERE / "dzwieki" / "muzyka", _HERE.parents[2] / "hq" / "web" / "dzwieki" / "muzyka")
                          if d.is_dir()), None) if len(_HERE.parents) > 2 else None


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ plan

def deep_merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = deep_merge(base.get(k), v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def variant_plan(plan: dict, name: str | None) -> dict:
    """Wariant = plan bazowy + nadpisania; `sceny` w wariancie: lista (całość) albo {"1": {...}} (numer sceny od 1)."""
    base = {k: v for k, v in plan.items() if k != "warianty"}
    if not name or name == plan.get("nazwa_bazowa", "A"):
        return base
    var = next((v for v in plan.get("warianty", []) if str(v.get("nazwa")) == name), None)
    if var is None:
        raise SystemExit(f"Brak wariantu {name!r} w planie (są: {', '.join(variant_names(plan))})")
    over = {k: v for k, v in var.items() if k not in ("nazwa", "sceny")}
    out = deep_merge(base, over)
    sc = var.get("sceny")
    if isinstance(sc, list):
        out["sceny"] = copy.deepcopy(sc)
    elif isinstance(sc, dict):
        scenes = copy.deepcopy(base["sceny"])
        for k, v in sc.items():
            i = int(k) - 1
            if not 0 <= i < len(scenes):
                raise SystemExit(f"Wariant {name}: scena {k} nie istnieje (jest {len(scenes)})")
            scenes[i] = deep_merge(scenes[i], v)
        out["sceny"] = scenes
    return out


def variant_names(plan: dict) -> list[str]:
    return [plan.get("nazwa_bazowa", "A")] + [str(v.get("nazwa")) for v in plan.get("warianty", [])]


def resolve(path: str, plan_dir: Path) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    for base in (Path.cwd(), plan_dir):
        if (base / p).exists():
            return (base / p).resolve()
    return (Path.cwd() / p).resolve()


def voice_cfg(plan: dict) -> dict | None:
    v = plan.get("lektor", {})
    if v is False or (isinstance(v, dict) and v.get("wylacz")):
        return None
    v = dict(v or {})
    v.setdefault("glos", wl.DEFAULT_VOICE)
    v.setdefault("tempo", "+0%")
    v.setdefault("glosnosc", "+0%")
    v.setdefault("wysokosc", "+0Hz")
    return v


def formats_of(plan: dict, override: str | None) -> list[str]:
    fm = override.split(",") if override else plan.get("formaty") or [plan.get("format", "9:16")]
    fm = [f.strip().replace("x", ":") for f in fm if f.strip()]
    for f in fm:
        wl.parse_format(f)
    return fm


def photo_warnings(i: int, path: Path, ruch: str, fmts: list[str]) -> list[str]:
    """Zdjęcie za małe na kadr z ruchem kamery (powiększenie > 5%) albo nieznany `ruch`."""
    if ruch not in RUCH_ZOOM:
        return [f"scena {i}: `ruch` {ruch!r} nieznany ({' | '.join(RUCH_ZOOM)}); użyję zoom"]
    try:
        v = wl.probe(path).get("video") or {}
        iw, ih = int(v["width"]), int(v["height"])
    except (Exception, SystemExit):            # brak ffprobe albo uszkodzony plik: render powie więcej
        return []
    if iw <= 0 or ih <= 0:                     # uszkodzony plik, który ffprobe 8 opisuje jako 0×0 bez błędu
        return []
    out = []
    for f in fmts:
        w, h = wl.FORMATS[f]
        skala = max(w / iw, h / ih) * RUCH_ZOOM[ruch]
        if skala > 1.05:
            potrzeba = f"{math.ceil(w * RUCH_ZOOM[ruch])}×{math.ceil(h * RUCH_ZOOM[ruch])}"
            out.append(f"scena {i}: zdjęcie {iw}×{ih} przy ruchu „{ruch}” w {f} rozciągnięte {skala:.2f}× (miękki obraz); "
                       f"daj co najmniej {potrzeba} (zrzut strony w 2×) albo `ruch: brak`")
    return out


def check_plan(plan: dict, plan_dir: Path) -> dict:
    """Błędy blokujące render + ostrzeżenia redakcyjne + szacunek długości (bez syntezy mowy)."""
    errors, warns = [], []
    scenes = plan.get("sceny")
    if not isinstance(scenes, list) or not scenes:
        return {"ok": False, "bledy": ["plan bez listy `sceny`"], "ostrzezenia": [], "szacunek_s": 0}
    try:
        fmts = formats_of(plan, None)
    except SystemExit as exc:
        errors.append(str(exc))
        fmts = ["9:16"]
    voice = voice_cfg(plan)
    if voice and not str(voice["glos"]).lower().startswith("pl-") and not voice.get("plik"):
        warns.append(f"lektor {voice['glos']}: to nie jest polski głos (pl-PL-Matcha-Meski / pl-PL-Matcha-Damski, "
                     "Edge: pl-PL-MarekNeural / pl-PL-ZofiaNeural)")
    if voice and voice.get("plik") and not resolve(voice["plik"], plan_dir).exists():
        errors.append(f"lektor.plik nie istnieje: {voice['plik']}")
    need_stock = False
    total = 0.0
    for i, s in enumerate(scenes, 1):
        text = str(s.get("tekst", "")).strip()
        if voice and not voice.get("plik") and not text:
            errors.append(f"scena {i}: brak `tekst` (lektor jest włączony)")
        if not voice and not s.get("czas"):
            warns.append(f"scena {i}: bez lektora, a bez `czas`; przyjmuję 3 s")
        n = len(text.split())
        est = max(MIN_SCENE, n / WORDS_PER_SEC + SCENE_GAP) if voice else float(s.get("czas") or 3)
        total += max(est, float(s.get("czas") or 0))
        if i == 1 and n > 12:
            warns.append(f"hook (scena 1) ma {n} słów: skróć do ≤ 12 (pierwsze 2 s decydują)")
        if n > 22:
            warns.append(f"scena {i}: {n} słów; podziel na dwie (jedna myśl na scenę)")
        if EMOJI.search(text + str(s.get("tekst_ekranowy", ""))):
            warns.append(f"scena {i}: emoji w tekście albo tekście ekranowym (w napisach będą puste kratki); usuń")
        uj = s.get("ujecie") or {}
        kinds = [k for k in ("stock", "stock_id", "plik", "kolor") if uj.get(k)]
        if len(kinds) != 1:
            errors.append(f"scena {i}: `ujecie` musi mieć dokładnie jedno z: stock, stock_id, plik, kolor")
        elif kinds[0] == "plik" and not resolve(uj["plik"], plan_dir).exists():
            errors.append(f"scena {i}: plik nie istnieje: {uj['plik']}")
        elif kinds[0] == "plik" and wl.is_image(resolve(uj["plik"], plan_dir)):
            warns += photo_warnings(i, resolve(uj["plik"], plan_dir), uj.get("ruch", "zoom"), fmts)
        elif kinds[0] == "kolor":
            try:
                wl.hex_to_ass(uj["kolor"])
            except SystemExit as exc:
                errors.append(f"scena {i}: {exc}")
        if uj.get("koniec", "petla") not in ("petla", "stop"):
            errors.append(f"scena {i}: `ujecie.koniec` = petla | stop (stop: animacja z kodu zatrzymuje się na ostatniej klatce)")
        need_stock |= kinds[:1] in (["stock"], ["stock_id"])
    if need_stock and not (os.environ.get("PEXELS_API_KEY") or os.environ.get("PIXABAY_API_KEY")):
        errors.append("sceny ze `stock`, a brak PEXELS_API_KEY / PIXABAY_API_KEY (darmowe; dashboard → Keys). "
                      "Bez klucza: ujęcia z AI (`plik`), własne pliki albo `kolor`.")
    mus = plan.get("muzyka") or {}
    if isinstance(mus, dict) and mus.get("plik") not in (None, "", "brak", "losowa") and not resolve(mus["plik"], plan_dir).exists():
        errors.append(f"muzyka.plik nie istnieje: {mus['plik']}")
    logo = (plan.get("marka") or {}).get("logo")
    if logo and not resolve(logo, plan_dir).exists():
        errors.append(f"marka.logo nie istnieje: {logo}")
    total += TAIL
    for f in fmts:
        if total > PLATFORM_MAX.get(f, 600):
            warns.append(f"szacunek {total:.0f} s > {PLATFORM_MAX[f]} s dla {f}: krótszy scenariusz utrzyma widza")
    try:
        names = variant_names(plan)
        for n in names[1:]:
            variant_plan(plan, n)
    except SystemExit as exc:
        errors.append(str(exc))
        names = []
    return {"ok": not errors, "bledy": errors, "ostrzezenia": warns, "szacunek_s": round(total, 1),
            "sceny": len(scenes), "formaty": fmts, "warianty": names}


# ------------------------------------------------------------------ ujęcia

def pick_music(plan: dict, plan_dir: Path) -> Path | None:
    mus = plan.get("muzyka")
    if not mus or mus == "brak":
        return None
    if isinstance(mus, str):
        mus = {"plik": mus}
    src = mus.get("plik")
    if not src or src == "brak":
        return None
    if src != "losowa":
        return resolve(src, plan_dir)
    dirs = [resolve(mus["katalog"], plan_dir)] if mus.get("katalog") else []
    brand = (plan.get("marka") or {}).get("nazwa")
    if brand:
        dirs.append(KNOWLEDGE / "brands" / brand / "muzyka")
    dirs.append(KNOWLEDGE / "wideo" / "muzyka")
    tracks = sorted(p for d in dirs if d.is_dir() for p in d.rglob("*") if p.suffix.lower() in wl.AUDIO_EXT)
    if not tracks and BIBLIOTEKA_MUZYKI:
        tracks = sorted(p for p in BIBLIOTEKA_MUZYKI.glob("*") if p.suffix.lower() in wl.AUDIO_EXT)
        log(f"muzyka „losowa”: skarbiec bez utworów, biorę podkład CC0 z biblioteki ({BIBLIOTEKA_MUZYKI})")
    if not tracks:
        log(f"! muzyka „losowa”: brak utworów w {', '.join(str(d) for d in dirs)}; film bez muzyki")
        return None
    return random.Random(plan.get("tytul", "")).choice(tracks)


def source_for(scene: dict, fmt: str, dur: float, plan_dir: Path, used: set, warns: list) -> dict:
    """Ujęcie sceny → {'typ': wideo|zdjecie|kolor, 'plik'?, 'kolor'?, metadane źródła}."""
    uj = scene.get("ujecie") or {}
    if uj.get("kolor"):
        return {"typ": "kolor", "kolor": uj["kolor"]}
    if uj.get("plik"):
        p = resolve(uj["plik"], plan_dir)
        return {"typ": "zdjecie" if wl.is_image(p) else "wideo", "plik": p, "zrodlo": "plik", "opis": uj.get("opis")}
    import stock  # noqa: E402  (tylko gdy potrzebny)
    kind = "zdjecie" if uj.get("typ") == "zdjecie" else "wideo"
    try:
        if uj.get("stock_id"):
            path, meta = stock.download(uj["stock_id"], fmt, kind)
        else:
            items = [it for it in stock.search(uj["stock"], kind, fmt, n=8, min_sec=dur) if it["id"] not in used]
            if not items:
                raise stock.StockError(f"brak wyników dla „{uj['stock']}”")
            path, meta = stock.download(items[0], fmt, kind)
        used.add(meta.get("id"))
        return {"typ": "zdjecie" if wl.is_image(path) else "wideo", "plik": path, **meta}
    except stock.StockError as exc:
        warns.append(f"ujęcie „{uj.get('stock') or uj.get('stock_id')}”: {exc}; wstawiam tło w kolorze")
        return {"typ": "kolor", "kolor": uj.get("zapas_kolor", "#15171C"), "blad": str(exc)}


def fit_filter(w: int, h: int, mode: str) -> str:
    if mode == "rozmyte":   # całe ujęcie widoczne, tło z tego samego ujęcia rozmyte
        return (f"split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=24:2,"
                f"eq=brightness=-0.08[bg];[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    return f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"


def render_scene(src: dict, uj: dict, w: int, h: int, dur: float, draft: bool) -> Path:
    """Scena → klip o dokładnej długości, rozdzielczości i fps (bez dźwięku). Cache po treści."""
    enc = ["-c:v", "libx264", "-preset", "ultrafast" if draft else "veryfast", "-crf", "28" if draft else "18",
           "-pix_fmt", "yuv420p", "-g", str(wl.FPS * 2), *wl.ENC_LIMITS, "-an"]
    mode = uj.get("dopasuj", "przytnij")
    key_src = wl.file_key(src["plik"]) if src.get("plik") else [src.get("kolor")]
    end = uj.get("koniec", "petla")
    sdr = wl.sdr(src["plik"]) if src["typ"] == "wideo" else ""     # ujęcie HDR (telefon, stock) → zwykły obraz
    key = wl.digest("scena-v1", key_src, w, h, round(dur, 3), uj.get("od", 0), uj.get("ruch"), mode, draft,
                    *([end] if end != "petla" else []), *(["sdr"] if sdr else []))
    out = wl.cache_dir("sceny") / f"{key}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out
    tmp = out.with_suffix(".part.mp4")
    if src["typ"] == "kolor":
        c = src["kolor"].lstrip("#")
        wl.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x{c}:s={w}x{h}:r={wl.FPS}:d={dur:.3f}", "-vf", wl.TV_RANGE, *enc, str(tmp)])
    elif src["typ"] == "zdjecie":
        frames = max(1, int(round(dur * wl.FPS)))
        big_w, big_h = (w, h) if draft else (wl.even(w * 1.6), wl.even(h * 1.6))
        z = round(RUCH_ZOOM["zoom"] - 1, 2)
        motion = uj.get("ruch", "zoom")
        if motion == "brak":
            zexpr, xexpr, yexpr = "1", "0", "0"
        elif motion == "oddal":
            zexpr, xexpr, yexpr = f"max(1.0,{1 + z}-{z}*on/{frames})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        elif motion == "panorama":
            zexpr, xexpr, yexpr = f"{RUCH_ZOOM['panorama']:.2f}", f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"
        else:
            zexpr, xexpr, yexpr = f"min({1 + z},1+{z}*on/{frames})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        vf = (f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,crop={big_w}:{big_h},"
              f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}':d={frames}:s={w}x{h}:fps={wl.FPS},{wl.TV_RANGE},setsar=1")
        wl.run(["ffmpeg", "-y", "-i", str(src["plik"]), "-vf", vf, "-frames:v", str(frames), *enc, str(tmp)])
    else:
        start = float(uj.get("od", 0) or 0)
        src_dur = wl.duration(src["plik"])
        short = src_dur - start < dur - 0.05
        # krótszy klip: stock zapętlamy; animacja z kodu (koniec: stop) trzyma ostatnią klatkę do końca sceny.
        # Bez pętli zawsze tpad: klip o zmiennym klatkażu (ManimGX: końcowa klatka to jedna długa) po `fps=`
        # kończyłby się na jej początku, ~1 s przed czasem (wl.stala_klatka); `-t` i tak przycina do sceny
        loop = ["-stream_loop", "-1"] if short and end != "stop" else []
        hold = "" if loop else f"tpad=stop_mode=clone:stop_duration={dur:.3f},"
        fit = fit_filter(w, h, mode)
        chain = f"{hold}{wl.z_sdr(fit, sdr)},fps={wl.FPS},{wl.TV_RANGE},setsar=1"
        if mode == "rozmyte":
            args = ["-filter_complex", f"[0:v]{chain}[v]", "-map", "[v]"]
        else:
            args = ["-vf", chain]
        wl.run(["ffmpeg", "-y", *loop, "-ss", f"{start:.3f}", "-i", str(src["plik"]), "-t", f"{dur:.3f}", *args, *enc, str(tmp)])
    tmp.replace(out)
    return out


# ------------------------------------------------------------------ montaż

def voice_track(speeches: list, durs: list[float], build: Path) -> Path:
    out = build / "lektor.wav"
    inputs, parts = [], []
    for i, (sp, d) in enumerate(zip(speeches, durs)):
        inputs += ["-i", str(sp.audio)]
        parts.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono,apad,atrim=0:{d:.3f}[a{i}]")
    fc = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(durs))) + f"concat=n={len(durs)}:v=0:a=1[out]"
    wl.run(["ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[out]", "-c:a", "pcm_s16le", str(out)])
    return out


def mix_audio(voice: Path | None, music: Path | None, music_vol: float, total: float, build: Path) -> Path:
    """Ścieżka dźwięku filmu w osobnym przebiegu (tylko audio, lekki): lektor + muzyka ściszana pod głos, −14 LUFS.
    Osobno, bo loudnorm ma ~3 s opóźnienia: w jednym grafie z obrazem FFmpeg trzymałby ~90 klatek 1080×1920 w RAM."""
    out = build / f"dzwiek-{wl.digest(str(voice), str(music), music_vol, round(total, 3))}.wav"
    if out.exists():
        return out
    norm = "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"
    fade_out = f"afade=t=out:st={max(0.0, total - 1.5):.3f}:d=1.5"
    inputs, fc = [], []
    if voice:
        inputs += ["-i", str(voice)]
        if music:
            inputs += ["-stream_loop", "-1", "-i", str(music)]
            fc.append(f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={music_vol:.3f},atrim=0:{total:.3f},{fade_out}[mv]")
            fc.append("[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[v1][v2]")
            fc.append("[mv][v1]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350[md]")
            fc.append(f"[v2][md]amix=inputs=2:duration=first:normalize=0,{norm}[aout]")
        else:
            fc.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,{norm}[aout]")
    elif music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fc.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},{fade_out},{norm}[aout]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        fc.append("[0:a]anull[aout]")
    tmp = out.with_suffix(".part.wav")
    wl.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[aout]", "-t", f"{total:.3f}",
            "-c:a", "pcm_s16le", "-ar", "48000", str(tmp)])
    tmp.replace(out)
    return out


def assemble(clips: list[Path], durs: list[float], total: float, w: int, h: int, build: Path, out: Path,
             audio: Path, ass: Path | None, logo: Path | None, logo_pos: str, fade: bool, draft: bool) -> None:
    inputs: list[str] = []
    for c in clips:   # dekoder H.264 domyślnie bierze wątki (i bufory klatek) ze wszystkich rdzeni: 1 wątek na scenę
        inputs += ["-threads", "1", "-i", str(c)]
    n = len(clips)
    fc: list[str] = []
    # wspólna podstawa czasu i stały klatkaż (xfade w FFmpeg 7 odrzuca wejścia bez znanego fps)
    fc.extend(f"[{i}:v]setpts=PTS-STARTPTS,fps={wl.FPS}[s{i}]" for i in range(n))
    if fade and n > 1:
        prev, offset = "[s0]", 0.0
        for i in range(1, n):
            offset += durs[i - 1]
            lab = f"[x{i}]"
            fc.append(f"{prev}[s{i}]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}{lab}")
            prev = lab
        vlast = prev
    else:
        fc.append("".join(f"[s{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]")
        vlast = "[vc]"
    if ass:
        fonts = build / "fonts"
        # krój marki obok (cwd = build); bez niego natywnie Inter z instalacji Jarva (ścieżka bezwzględna, na Windows
        # z zabezpieczonym dwukropkiem), w obrazie kroje z fontconfig systemu
        extra = ":fontsdir=fonts" if fonts.is_dir() else wl.opcja_fontsdir()
        fc.append(f"{vlast}ass={ass.name}{extra}[vs]")
        vlast = "[vs]"
    idx = n
    if logo:
        inputs += ["-i", str(logo)]
        lw = wl.even(min(w, h) * 0.16)
        mx, my = wl.even(w * 0.05), wl.even(h * (0.11 if h > w else 0.06))   # 9:16: pod górnym paskiem aplikacji
        pos = {"gora-prawo": f"W-w-{mx}:{my}", "gora-lewo": f"{mx}:{my}", "dol-prawo": f"W-w-{mx}:H-h-{my}",
               "dol-lewo": f"{mx}:H-h-{my}"}.get(logo_pos, f"W-w-{mx}:{my}")
        fc.append(f"[{idx}:v]scale={lw}:-1[lg];{vlast}[lg]overlay={pos}[vl]")
        vlast = "[vl]"
        idx += 1
    fc.append(f"{vlast}{wl.TV_RANGE}[vout]")
    inputs += ["-i", str(audio)]
    enc = ["-c:v", "libx264", "-preset", "ultrafast" if draft else "medium", "-crf", "30" if draft else "20",
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(wl.FPS), *wl.ENC_LIMITS,
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]
    tmp = out.with_suffix(".part.mp4")
    wl.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", f"{idx}:a",
            "-t", f"{total:.3f}", *enc, str(tmp.resolve())], cwd=build)
    tmp.replace(out)


# ------------------------------------------------------------------ render

def render_variant(plan: dict, name: str, suffix: str, fmts: list[str], draft: bool, outdir: Path, plan_dir: Path) -> dict:
    t0 = time.time()
    scenes = plan["sceny"]
    slug = wl.slugify(plan.get("slug") or plan.get("tytul") or "film")
    target = outdir / slug
    target.mkdir(parents=True, exist_ok=True)
    warns: list[str] = []
    voice = voice_cfg(plan)
    style = wl.SubStyle.from_dict(plan.get("napisy"))

    # 1. lektor → długości scen i słowa z czasem
    speeches, words = [], []
    if voice and voice.get("plik"):
        narr = resolve(voice["plik"], plan_dir)
        total_voice = wl.duration(narr)
        fixed = [float(s.get("czas") or 0) for s in scenes]
        if all(fixed):
            durs = fixed
        else:
            lens = [max(1, len(str(s.get("tekst", "")).split())) for s in scenes]
            durs = [total_voice * n / sum(lens) for n in lens]
        durs[-1] += TAIL
        if style.styl != "brak":
            log("▶ transkrypcja lektora (Parakeet) do napisów")
            words = wl.transcribe_words(narr)
    elif voice:
        items = [{"text": str(s["tekst"]).strip(), "voice": s.get("glos", voice["glos"]), "rate": voice["tempo"],
                  "volume": voice["glosnosc"], "pitch": voice["wysokosc"]} for s in scenes]
        log(f"▶ lektor: {len(items)} scen, głos {voice['glos']}")
        speeches = wl.speak_many(items)
        durs = []
        t = 0.0
        for i, (s, sp) in enumerate(zip(scenes, speeches)):
            d = max(MIN_SCENE, sp.duration + (TAIL if i == len(scenes) - 1 else SCENE_GAP), float(s.get("czas") or 0))
            words += [wl.Word(round(t + x.start, 3), round(t + x.end, 3), x.text)
                      for x in wl.align_display(sp.words, str(s["tekst"]))]
            durs.append(d)
            t += d
    else:
        durs = [max(MIN_SCENE, float(s.get("czas") or 3)) for s in scenes]
    total = sum(durs)
    starts = [sum(durs[:i]) for i in range(len(durs))]
    titles = [(starts[i], starts[i] + durs[i] - 0.05, str(s["tekst_ekranowy"])) for i, s in enumerate(scenes)
              if s.get("tekst_ekranowy")]

    build = wl.cache_dir("render", wl.digest(slug, name, plan, draft))
    if speeches:
        voice_path = voice_track(speeches, durs, build)
    elif voice and voice.get("plik"):
        voice_path = resolve(voice["plik"], plan_dir)
    else:
        voice_path = None
    music = pick_music(plan, plan_dir)
    mcfg = plan.get("muzyka") if isinstance(plan.get("muzyka"), dict) else {}
    music_vol = float(mcfg.get("glosnosc", 0.14 if voice else 0.8))
    marka = plan.get("marka") or {}
    logo = resolve(marka["logo"], plan_dir) if marka.get("logo") else None
    font_file = (plan.get("napisy") or {}).get("font_plik")
    if font_file:
        (build / "fonts").mkdir(exist_ok=True)
        shutil.copy2(resolve(font_file, plan_dir), build / "fonts")
    fade = plan.get("przejscie", "ciecie") == "przenikanie"
    audio = mix_audio(voice_path, music, music_vol, total, build)   # wspólna dla wszystkich formatów

    result = {"tytul": plan.get("tytul"), "wariant": name, "szkic": draft, "sek": round(total, 2),
              "lektor": voice and {k: voice[k] for k in ("glos", "tempo") if k in voice} or None,
              "muzyka": music.as_posix() if music else None, "pliki": {}, "sceny": [], "ostrzezenia": warns}
    if words:
        srt = target / f"{slug}{suffix}.srt"
        srt.write_text(wl.build_srt(words), encoding="utf-8")
        result["srt"] = srt.as_posix()

    for fmt in fmts:
        w, h = wl.parse_format(fmt)
        if draft:
            w, h = wl.even(w / 2), wl.even(h / 2)
        used: set = set()
        clip_durs = [d + (XFADE if fade and i < len(durs) - 1 else 0) for i, d in enumerate(durs)]
        log(f"▶ {fmt}: ujęcia dla {len(scenes)} scen")
        sources = [source_for(s, fmt, d, plan_dir, used, warns) for s, d in zip(scenes, clip_durs)]
        with ThreadPoolExecutor(max_workers=wl.PARALLEL) as pool:
            clips = list(pool.map(lambda a: render_scene(a[0], a[1].get("ujecie") or {}, w, h, a[2], draft),
                                  zip(sources, scenes, clip_durs)))
        ass = None
        if words or titles:
            ass = build / f"napisy-{wl.fmt_slug(fmt)}.ass"
            ass.write_text(wl.build_ass(w, h, words, style, titles), encoding="utf-8")
        out = target / f"{slug}{suffix}-{wl.fmt_slug(fmt)}{'-szkic' if draft else ''}.mp4"
        log(f"▶ {fmt}: montaż → {out}")
        assemble(clips, durs, total, w, h, build, out, audio, ass, logo, marka.get("pozycja", "gora-prawo"), fade, draft)
        info = {"plik": out.as_posix(), "rozdzielczosc": f"{w}x{h}", "sek": round(wl.duration(out), 2),
                "mb": round(out.stat().st_size / 1048576, 2)}
        if not draft:
            thumb = target / f"{slug}{suffix}-{wl.fmt_slug(fmt)}-miniatura.jpg"
            wl.run(["ffmpeg", "-y", "-ss", f"{min(durs[0] * 0.5, 1.2):.2f}", "-i", str(out), "-frames:v", "1", "-q:v", "2", str(thumb)])
            info["miniatura"] = thumb.as_posix()
        result["pliki"][fmt] = info
        if not result["sceny"]:
            for i, (s, src, d) in enumerate(zip(scenes, sources, durs), 1):
                result["sceny"].append({"nr": i, "start": round(starts[i - 1], 2), "sek": round(d, 2), "tekst": s.get("tekst"),
                                        "ujecie": {k: (str(v) if isinstance(v, Path) else v) for k, v in src.items()}})
    result["czas_renderu_s"] = round(time.time() - t0, 1)
    wl.write_json(target / f"film{suffix}{'-szkic' if draft else ''}.json", result)
    return result


def cmd_render(args) -> int:
    plan_path = Path(args.plan).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = check_plan(plan, plan_path.parent)
    if not report["ok"]:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 1
    for wmsg in report["ostrzezenia"]:
        log(f"! {wmsg}")
    wl.need("ffmpeg")
    names = variant_names(plan) if args.wszystkie else [args.wariant or plan.get("nazwa_bazowa", "A")]
    fmts = formats_of(plan, args.format)
    outdir = Path(args.out)
    suffix = (lambda n: f"-{wl.slugify(n, 16)}") if plan.get("warianty") else (lambda n: "")
    with wl.miejsce_renderu("film.py render"):
        results = [render_variant(variant_plan(plan, n), n, suffix(n), fmts, args.szkic, outdir, plan_path.parent) for n in names]
    print(json.dumps({"ok": True, "filmy": results}, ensure_ascii=False, indent=1))
    return 0


def cmd_check(args) -> int:
    plan_path = Path(args.plan).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = check_plan(plan, plan_path.parent)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["ok"] else 1


# ------------------------------------------------------------------ narracja: lektor z pauzami i oś czasu

# Pauzy (s) między słyszalną mową: w akapicie krótki oddech, na końcu akapitu (= cięcie ujęcia) pełna sekunda,
# przed rozdziałem dłużej. Obraz zmienia się w pauzie, więc rytm jest spokojny, a nowy kadr wchodzi z nowym zdaniem.
PAUZY = {"wstep": 0.5, "zdanie": 0.33, "akapit": 1.0, "rozdzial": 1.5, "koniec": 1.5}
ZAPAS_PRZED, ZAPAS_PO = 0.02, 0.06       # wycinek mowy: tyle ciszy zostaje przed i po słyszalnym dźwięku
CIECIE_PRZED = 0.25                      # cięcie ujęcia tyle przed pierwszym zdaniem następnego (najwyżej 1/3 pauzy)
SR_LEKTORA = 48000
SLOW_W_ZDANIU, ZNAKOW_W_NAPISIE, ZDAN_W_UJECIU = 20, 42, 4
TEMPO_MAX, UJECIE_MIN, ROZDZIAL_MIN, ROZDZIALY_OD = 2.7, 4.0, 60.0, 180.0
NAZWA_CHWILI = re.compile(r"^[^\W\d][\w-]*$")
AUTO_CHWILA = re.compile(r"^(u\d+|r\d+|start|koniec)([.].*)?$")
SKROTY = {"np", "m.in", "tj", "tzw", "ok", "godz", "ul", "r", "tys", "mln", "mld", "zł", "nr", "dr", "prof", "itd", "itp",
          "wg", "pt", "ww", "al", "św", "tel", "min", "sek", "proc"}


# zasady narracji (skill scenariusz, references/narracja.md): to, co da się złapać ze słów
START_POWITANIE = re.compile(r"^(cześć|dzień dobry|witaj\w*|hej\b|w tym (filmie|odcinku|materiale)|dziś (opowiem|pokażę|powiem)"
                             r"|dzisiaj (opowiem|pokażę|powiem)|chcę (wam|ci) (opowiedzieć|pokazać))", re.I)
START_DEFINICJA = re.compile(r"^[\w-]+(?:,? [\w-]+){0,3},? (to|oznacza|czyli|nazywamy|jest to)\b", re.I)
AKAPIT_LISTA = re.compile(r"^(po (pierwsze|drugie|trzecie|czwarte|piąte)|kolejn\w*|następn\w*|ponadto|dodatkowo|poza tym"
                          r"|oprócz tego|warto (też|również)|(druga|trzecia|czwarta) rzecz)\b", re.I)
OPIS_OBRAZU = re.compile(r"\b(na ekranie|jak widać|jak widzisz|widzisz tu\w*|tutaj widzimy|spójrz na"
                         r"|na (tym )?(wykresie|obrazku|zdjęciu|animacji|schemacie) (widać|widzisz))\b", re.I)
KONIEC_STRESZCZA = re.compile(r"^(podsumowując|podsumowanie|reasumując|w skrócie|krótko mówiąc|tak więc|na koniec podsumujmy)\b", re.I)


def kontrola_tekstu(rozdzialy: list[dict]) -> list[str]:
    """Ostrzeżenia z zasad narracji: start od powitania albo definicji, akapity jak lista, lektor opisujący obraz,
    koniec, który streszcza, rozdział bez pytania na końcu. Linii opowieści i skali liczb skrypt nie oceni."""
    akapity = [a for r in rozdzialy for a in r["akapity"]]
    if not akapity:
        return []
    out = []
    pierwsza = akapity[0][0]
    if START_POWITANIE.match(pierwsza["tekst"]):
        out.append(f"wiersz {pierwsza['wiersz']}: start od powitania; zacznij w sytuacji widza (scenariusz/references/narracja.md, zasada 1)")
    elif START_DEFINICJA.match(pierwsza["tekst"]):
        out.append(f"wiersz {pierwsza['wiersz']}: start od definicji; zacznij w sytuacji widza, nazwę podaj później (zasady 1 i 6)")
    lista = [a[0]["wiersz"] for a in akapity if AKAPIT_LISTA.match(a[0]["tekst"])]
    if len(lista) >= 2:
        out.append(f"wiersze {', '.join(map(str, lista))}: akapity zaczynają się jak lista; połącz je przyczyną "
                   f"(więc, ale, dlatego), żeby była jedna linia opowieści (zasada 2)")
    out += [f"wiersz {ln['wiersz']}: lektor opisuje obraz („{m.group(0)}”); powiedz to, czego obraz nie mówi (zasada 7)"
            for a in akapity for ln in a if (m := OPIS_OBRAZU.search(ln["tekst"]))]
    out += [f"wiersz {ln['wiersz']}: koniec streszcza; wróć do sytuacji z początku i pokaż ją inaczej (zasada 8)"
            for ln in akapity[-1] if KONIEC_STRESZCZA.match(ln["tekst"])]
    if len(rozdzialy) > 1:
        for i, r in enumerate(rozdzialy[:-1], 1):
            ostatnie = r["akapity"][-1][-1]
            if not ostatnie["tekst"].rstrip().endswith("?"):
                nazwa = f"rozdział {i}" + (f" „{r['tytul']}”" if r["tytul"] else "")
                out.append(f"wiersz {ostatnie['wiersz']}: {nazwa} nie kończy się pytaniem, na które odpowiada następny (zasada 9)")
    return out


def _znaki(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def _kilka_zdan(tekst: str) -> bool:
    """Czy w linii kończy się zdanie, a po nim zaczyna następne (kropka/!/? + spacja + wielka litera; nie po skrócie)."""
    for m in re.finditer(r"(\S+)[.!?…]\s+[A-ZĄĆĘŁŃÓŚŹŻ0-9„\"]", tekst):
        poprzednie = m.group(1).lower().rstrip(".")
        if poprzednie not in SKROTY and not re.fullmatch(r"\d+", poprzednie):
            return True
    return False


def parse_narracja(tekst: str) -> dict:
    """Plik narracji → rozdziały, akapity (= ujęcia) i linie (= zdania lektora) z podziałami napisów i chwilami.

    Linia = jedno zdanie lektora. Pusty wiersz kończy akapit, czyli ujęcie. `# tytuł` zaczyna rozdział (tytuł nie
    jest czytany). `|` dzieli napis w miejscu oddechu (nie jest czytany). `{nazwa}` przed słowem = chwila na początku
    tego słowa, na końcu linii = koniec zdania. `//` na początku wiersza = komentarz."""
    bledy, ostrz = [], []
    rozdzialy: list[dict] = []
    akapit: list[dict] | None = None
    nazwy: set[str] = set()

    def rozdzial(tytul: str) -> dict:
        r = {"tytul": tytul, "akapity": []}
        rozdzialy.append(r)
        return r

    for nr, surowa in enumerate(tekst.splitlines(), 1):
        wiersz = surowa.strip()
        if wiersz.startswith("//"):
            continue
        if not wiersz:
            akapit = None
            continue
        if wiersz.startswith("#"):
            rozdzial(wiersz.lstrip("#").strip())
            akapit = None
            continue
        slowa, podzialy, chwile = [], set(), []
        for tok in re.findall(r"\{[^{}]*\}|\||[^\s{}|]+|[{}]", wiersz):
            if tok == "|":
                if slowa:
                    podzialy.add(len(slowa) - 1)
            elif tok.startswith("{") and tok.endswith("}"):
                nazwa = tok[1:-1].strip()
                if not NAZWA_CHWILI.match(nazwa):
                    bledy.append(f"wiersz {nr}: chwila {tok}: nazwa z liter, cyfr, _ i - (np. {{licznik}})")
                elif AUTO_CHWILA.match(nazwa):
                    bledy.append(f"wiersz {nr}: chwila {tok} zajęta (u3, u3.z2, r1, start, koniec nadaje skrypt)")
                elif nazwa in nazwy:
                    bledy.append(f"wiersz {nr}: chwila {tok} już jest; nazwy chwil muszą być różne")
                else:
                    nazwy.add(nazwa)
                    chwile.append((nazwa, len(slowa)))
            elif tok in "{}":
                bledy.append(f"wiersz {nr}: niedomknięta chwila (samo „{tok}”; zapis: {{nazwa}}słowo)")
            else:
                slowa.append(tok)
        if not slowa:
            bledy.append(f"wiersz {nr}: linia bez słów do przeczytania")
            continue
        if not rozdzialy:
            rozdzial("")
        if akapit is None:
            akapit = []
            rozdzialy[-1]["akapity"].append(akapit)
        czysty = " ".join(slowa)
        akapit.append({"wiersz": nr, "tekst": czysty, "slowa": slowa, "podzialy": sorted(podzialy | {len(slowa) - 1}),
                       "chwile": chwile})
        if len(slowa) > SLOW_W_ZDANIU:
            ostrz.append(f"wiersz {nr}: zdanie ma {len(slowa)} słów (> {SLOW_W_ZDANIU}): podziel na dwa")
        if _kilka_zdan(czysty):
            ostrz.append(f"wiersz {nr}: kilka zdań w jednej linii: każde zdanie w osobnej (pauzy i chwile liczone na linię)")
        poczatek = 0
        for k in sorted(podzialy):
            napis = " ".join(slowa[poczatek:k + 1])
            if len(napis) > ZNAKOW_W_NAPISIE:
                ostrz.append(f"wiersz {nr}: napis „{napis[:30]}…” ma {len(napis)} znaków (> {ZNAKOW_W_NAPISIE}): dodaj | w miejscu oddechu")
            poczatek = k + 1
    rozdzialy = [r for r in rozdzialy if r["akapity"]]
    if not rozdzialy:
        bledy.append("narracja bez zdań")
    ostrz += kontrola_tekstu(rozdzialy)
    for r in rozdzialy:
        for a in r["akapity"]:
            if len(a) > ZDAN_W_UJECIU:
                ostrz.append(f"wiersz {a[0]['wiersz']}: akapit ma {len(a)} zdań (> {ZDAN_W_UJECIU}): podziel na dwa ujęcia")
    return {"rozdzialy": rozdzialy, "bledy": bledy, "ostrzezenia": ostrz}


ZNAKI_BRZEGU = "\"'„”«»()[]"


def _rdzen(tok: str) -> str:
    return tok.strip(ZNAKI_BRZEGU).rstrip(",.;:!?…").strip(ZNAKI_BRZEGU).casefold()


def do_czytania(slowa: list[str], wymowa: dict[str, str] | None
                ) -> tuple[list[str], list[tuple[int, int, int, int]], list[str]]:
    """Słowa do napisów → słowa dla lektora: termin ze słowniczka (też kilkuwyrazowy, bez wielkości liter) zastąpiony
    zapisem wymowy („Next.js” → „nekst dżej es”), interpunkcja z końca zostaje. Mapa: dla każdego słowa napisu
    (początek, koniec) słów lektora oraz (część, ile), gdy kilka słów napisu dzieli jeden zapis wymowy. Na końcu
    lista użytych terminów."""
    klucze = sorted((([_rdzen(t) for t in k.split()], v.split(), k) for k, v in (wymowa or {}).items()
                     if k.strip() and v.strip()), key=lambda kv: -len(kv[0]))
    tts, mapa, uzyte, i = [], [], [], 0
    while i < len(slowa):
        for klucz, zamiana, termin in klucze:
            n = len(klucz)
            if [_rdzen(t) for t in slowa[i:i + n]] == klucz:
                ogon = slowa[i + n - 1][len(slowa[i + n - 1].rstrip(",.;:!?…")):]
                a = len(tts)
                tts += zamiana[:-1] + [zamiana[-1] + ogon]
                mapa += [(a, len(tts), k, n) for k in range(n)]
                uzyte.append(termin)
                i += n
                break
        else:
            mapa.append((len(tts), len(tts) + 1, 0, 1))
            tts.append(slowa[i])
            i += 1
    return tts, mapa, uzyte


def linie_narracji(narr: dict, wymowa: dict[str, str] | None = None) -> list[dict]:
    """Płaska lista linii z numerem ujęcia, zdania w ujęciu, rozdziału, rodzajem pauzy przed linią i tekstem dla
    lektora (z wymową terminów ze słowniczka)."""
    out, u = [], 0
    for ri, r in enumerate(narr["rozdzialy"], 1):
        for ai, akapit in enumerate(r["akapity"]):
            u += 1
            for zi, ln in enumerate(akapit, 1):
                pauza = ("wstep" if not out else "zdanie" if zi > 1 else "akapit" if ai > 0 else "rozdzial")
                tts, mapa, uzyte = do_czytania(ln["slowa"], wymowa)
                out.append({**ln, "rozdzial": ri, "ujecie": u, "zdanie": zi, "pauza": pauza, "id": f"u{u}.z{zi}",
                            "tts_slowa": tts, "tts": " ".join(tts), "mapa": mapa, "wymowa": uzyte})
    return out


def czasy_tokenow(tokeny: list[str], slowa: list[wl.Word]) -> list[tuple[float, float, int]]:
    """Każde słowo tekstu → (początek, koniec, indeks słowa lektora). Edge TTS czyta tekst, który dostał, ale bywa,
    że skleja słowa („2024 roku”) albo dzieli je inaczej: dopasowanie po literach i cyfrach, nie po spacjach;
    w sklejonym słowie czas dzielony według liter."""
    if not slowa:
        return [(0.0, 0.0, -1)] * len(tokeny)
    zn_s = [_znaki(w.text) for w in slowa]
    zn_t = [_znaki(t) for t in tokeny]
    skala = (sum(map(len, zn_s)) or 1) / (sum(map(len, zn_t)) or 1)    # inne litery niż w tekście: proporcjonalnie
    granice, poz = [], 0
    for z in zn_s:
        granice.append((poz, poz + len(z)))
        poz += len(z)
    out, poz = [], 0
    for z in zn_t:
        p0, p1 = poz * skala, (poz + len(z)) * skala
        k = next((i for i, (a, b) in enumerate(granice) if a <= (p0 + p1) / 2 < b), len(slowa) - 1)
        a, b = granice[k]
        w = slowa[k]
        def czas(p, a=a, b=b, w=w):
            return w.start + (w.end - w.start) * (min(max(p, a), b) - a) / max(1, b - a)
        out.append((czas(p0), czas(p1), k))
        poz += len(z)
    return out


def cisza_z_logu(log_ffmpeg: str, dlugosc: float) -> tuple[float, float]:
    """Log `silencedetect` → (początek, koniec) słyszalnej mowy: cisza od zera i cisza do końca pliku."""
    starty = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", log_ffmpeg)]
    konce = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log_ffmpeg)]
    od, do = 0.0, dlugosc
    if starty and starty[0] <= 0.01 and konce:
        od = konce[0]
    if starty and (len(konce) < len(starty) or konce[-1] >= dlugosc - 0.03):
        if not (len(starty) == 1 and starty[0] <= 0.01):
            do = starty[-1]
    return od, max(od, do)


def granice_mowy(sp) -> tuple[float, float]:
    r = wl.run(["ffmpeg", "-i", str(sp.audio), "-af", "silencedetect=n=-50dB:d=0.02", "-f", "null", "-"], quiet=False)
    od, do = cisza_z_logu(r.stderr or "", sp.duration)
    if sp.words:
        od = min(od, sp.words[0].end)                           # nigdy nie tniemy w środku pierwszego słowa
        do = min(sp.duration, max(do, sp.words[-1].end))         # ani przed końcem ostatniego
    return od, do


def uloz_os(linie: list[dict], mowy: list[dict], pauzy: dict, rozdzialy: list[dict]) -> dict:
    """Linie + mowa każdej linii ({od, do, slowa} w czasie jej pliku) → oś czasu filmu: gdzie wkleić mowę, słowa,
    zdania, ujęcia, rozdziały i nazwane chwile. Czysta funkcja (bez dźwięku)."""
    t, kawalki, zdania, slowa_osi = 0.0, [], [], []
    chwile: dict[str, float] = {"start": 0.0}
    for ln, m in zip(linie, mowy):
        t += pauzy[ln["pauza"]]
        przes = t - m["od"]
        start, koniec = round(t, 3), round(t + (m["do"] - m["od"]), 3)
        kawalki.append({"od": max(0.0, m["od"] - ZAPAS_PRZED), "do": m["do"] + ZAPAS_PO,
                        "na": max(0.0, t - min(ZAPAS_PRZED, m["od"]))})
        tts_czasy = czasy_tokenow(ln.get("tts_slowa") or ln["slowa"], m["slowa"])
        tok = []                                   # czas każdego słowa napisu (przez mapę wymowy)
        for i, (a, b, czesc, ile) in enumerate(ln.get("mapa") or [(i, i + 1, 0, 1) for i in range(len(ln["slowa"]))]):
            t0, t1 = tts_czasy[a][0], tts_czasy[b - 1][1]
            d = (t1 - t0) / ile
            tok.append((t0 + czesc * d, t0 + (czesc + 1) * d))
        przytnij = lambda x: round(min(max(x + przes, start), koniec), 3)  # noqa: E731
        for nazwa, i in ln["chwile"]:
            chwile[nazwa] = przytnij(tok[i][0]) if i < len(tok) else koniec
        slowa_zd: list[wl.Word] = []
        for i, (slowo, (t0, t1)) in enumerate(zip(ln["slowa"], tok)):
            podzial = i in ln["podzialy"] or i == len(tok) - 1
            if not _znaki(slowo):                  # sama interpunkcja („–”): nie jest słowem napisu
                if podzial and slowa_zd:
                    slowa_zd[-1].podzial = True
                continue
            tekst = slowo.strip(ZNAKI_BRZEGU).rstrip(",.;:…").strip(ZNAKI_BRZEGU) or slowo
            slowa_zd.append(wl.Word(przytnij(t0), przytnij(t1), tekst, podzial))
        slowa_osi += slowa_zd
        zdania.append({"id": ln["id"], "ujecie": f"u{ln['ujecie']}", "rozdzial": f"r{ln['rozdzial']}", "wiersz": ln["wiersz"],
                       "tekst": ln["tekst"], "start": start, "koniec": koniec,
                       "slowa": [{"tekst": w.text, "start": w.start, "koniec": w.end} for w in slowa_zd]})
        chwile[ln["id"]], chwile[ln["id"] + ".koniec"] = start, koniec
        t = koniec
    dlugosc = round(t + pauzy["koniec"], 3)
    ujecia: list[dict] = []
    for z in zdania:
        if not ujecia or ujecia[-1]["id"] != z["ujecie"]:
            ujecia.append({"id": z["ujecie"], "nr": len(ujecia) + 1, "rozdzial": z["rozdzial"], "mowa_start": z["start"],
                           "zdania": []})
        ujecia[-1]["zdania"].append(z["id"])
        ujecia[-1]["mowa_koniec"] = z["koniec"]
    for i, u in enumerate(ujecia):
        u["start"] = ujecia[i - 1]["koniec"] if i else 0.0
        nast = ujecia[i + 1]["mowa_start"] if i + 1 < len(ujecia) else None
        u["koniec"] = round(nast - min(CIECIE_PRZED, (nast - u["mowa_koniec"]) / 3), 3) if nast is not None else dlugosc
        u["sek"] = round(u["koniec"] - u["start"], 3)
        for k, v in (("", u["start"]), (".mowa", u["mowa_start"]), (".mowa_koniec", u["mowa_koniec"]), (".koniec", u["koniec"])):
            chwile[u["id"] + k] = v
    rozdz = []
    for ri, r in enumerate(rozdzialy, 1):
        uj = [u for u in ujecia if u["rozdzial"] == f"r{ri}"]
        if uj:
            rozdz.append({"id": f"r{ri}", "nr": ri, "tytul": r["tytul"], "start": uj[0]["start"], "koniec": uj[-1]["koniec"],
                          "sek": round(uj[-1]["koniec"] - uj[0]["start"], 3), "ujecia": [u["id"] for u in uj]})
            chwile[f"r{ri}"], chwile[f"r{ri}.koniec"] = uj[0]["start"], uj[-1]["koniec"]
    chwile["koniec"] = dlugosc
    napisy = [{"start": g[0].start, "koniec": g[-1].end, "tekst": " ".join(w.text for w in g)}
              for g in wl.chunk_words(slowa_osi, 7, ZNAKOW_W_NAPISIE)]
    return {"dlugosc": dlugosc, "mowa_s": round(sum(z["koniec"] - z["start"] for z in zdania), 3), "pauzy": pauzy,
            "rozdzialy": rozdz, "ujecia": ujecia, "zdania": zdania, "chwile": chwile, "napisy": napisy,
            "_kawalki": kawalki, "_slowa": slowa_osi}


def tempo_narracji(os_: dict) -> float:
    """Słowa na sekundę tak, jak słyszy je widz: od pierwszego do ostatniego zdania, z pauzami między nimi."""
    if not os_["zdania"]:
        return 0.0
    czas = os_["zdania"][-1]["koniec"] - os_["zdania"][0]["start"]
    return sum(len(z["tekst"].split()) for z in os_["zdania"]) / czas if czas > 0 else 0.0


def kontrola_osi(os_: dict, cel: tuple[float, float] | None) -> list[str]:
    """Ostrzeżenia po syntezie: tempo lektora, krótkie ujęcia, rozdziały w krótkim filmie, długość względem celu."""
    out = []
    tempo = tempo_narracji(os_)
    if tempo > TEMPO_MAX:
        out.append(f"lektor mówi {tempo:.2f} słowa/s razem z pauzami (> {TEMPO_MAX}): --tempo -5% albo krótszy tekst")
    for u in os_["ujecia"]:
        if u["sek"] < UJECIE_MIN and len(os_["ujecia"]) > 1:
            out.append(f"{u['id']} trwa {u['sek']:.1f} s (< {UJECIE_MIN:g} s): połącz akapit z sąsiednim")
    rozdz = os_["rozdzialy"]
    if len(rozdz) > 1 and os_["dlugosc"] < ROZDZIALY_OD:
        out.append(f"{len(rozdz)} rozdziały w filmie {os_['dlugosc']:.0f} s: rozdziały i ich plansze dopiero od "
                   f"{ROZDZIALY_OD / 60:.0f} min (krótszy film = jedna opowieść bez podziału)")
    elif len(rozdz) > 1:
        out += [f"rozdział {r['id']} „{r['tytul']}” trwa {r['sek']:.0f} s (< {ROZDZIAL_MIN:g} s): połącz z sąsiednim"
                for r in rozdz if r["sek"] < ROZDZIAL_MIN]
    if cel and not cel[0] <= os_["dlugosc"] <= cel[1]:
        out.append(f"film ma {os_['dlugosc']:.1f} s, a cel to {cel[0]:g}–{cel[1]:g} s: "
                   f"{'skróć' if os_['dlugosc'] > cel[1] else 'rozwiń'} tekst (≈ {WORDS_PER_SEC} słowa/s)")
    return out


def zloz_lektor(mowy_pliki: list[Path], kawalki: list[dict], dlugosc: float, out: Path) -> None:
    """Wycinki mowy wklejone w swoje chwile osi, cisza między nimi: jeden plik, dokładnie co do próbki."""
    import array
    import subprocess
    import wave
    bufor = array.array("h", bytes(2 * int(round(dlugosc * SR_LEKTORA))))
    for plik, k in zip(mowy_pliki, kawalki):
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(plik), "-f", "s16le", "-ac", "1",
                            "-ar", str(SR_LEKTORA), "-"], capture_output=True)
        if r.returncode:
            raise wl.FFError(f"ffmpeg nie odczytał {plik}: {r.stderr.decode(errors='replace')[-300:]}")
        pcm = array.array("h")
        pcm.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
        a, b = int(round(k["od"] * SR_LEKTORA)), min(len(pcm), int(round(k["do"] * SR_LEKTORA)))
        na = int(round(k["na"] * SR_LEKTORA))
        for i, v in enumerate(pcm[a:b], na):
            if i >= len(bufor):
                break
            bufor[i] = max(-32768, min(32767, bufor[i] + v))
    wav = out if out.suffix.lower() == ".wav" else out.with_suffix(".tmp.wav")
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR_LEKTORA)
        f.writeframes(bufor.tobytes())
    if wav != out:
        wl.run(["ffmpeg", "-y", "-i", str(wav), str(out)])
        wav.unlink()


def _pauzy(spec: str | None) -> dict:
    p = dict(PAUZY)
    for part in filter(None, (spec or "").split(",")):
        k, _, v = part.partition("=")
        if k.strip() not in p:
            raise SystemExit(f"--pauzy: nieznany rodzaj {k.strip()!r} ({', '.join(PAUZY)})")
        p[k.strip()] = float(v)
    return p


def _cel(spec: str | None) -> tuple[float, float] | None:
    if not spec:
        return None
    a, _, b = spec.replace("–", "-").partition("-")
    return float(a), float(b or a)


def fakty_i_wymowa(sciezka_fakty: Path | None, sciezka_wymowa: str | None) -> tuple[dict | None, dict[str, str]]:
    """fakty.json (brief Sherlocka) i słownik wymowy: `slowniczek[].wymowa` z faktów, nadpisany plikiem --wymowa."""
    fakty = json.loads(sciezka_fakty.read_text(encoding="utf-8")) if sciezka_fakty else None
    wymowa = {str(t["termin"]): str(t["wymowa"]) for t in (fakty or {}).get("slowniczek") or []
              if isinstance(t, dict) and t.get("termin") and t.get("wymowa")}
    if sciezka_wymowa:
        wymowa.update({str(k): str(v) for k, v in json.loads(Path(sciezka_wymowa).read_text(encoding="utf-8")).items()})
    return fakty, wymowa


def kontrola_liczb(linie: list[dict], fakty: dict) -> tuple[list[str], list[str]]:
    """Liczby lektora zapisane cyframi kontra fakty.json: z listy niepewnych = błąd, bez pokrycia = ostrzeżenie."""
    pewne, niepewne = wl.liczby_faktow(fakty)
    bledy, ostrz = [], []
    for ln in linie:
        for zapis, rodzaj in wl.sprawdz_liczby(ln["tekst"], pewne, niepewne):
            if rodzaj == "niepewna":
                bledy.append(f"wiersz {ln['wiersz']}: liczba „{zapis}” jest na liście niepewnych w fakty.json: "
                             "nie trafia do lektora")
            else:
                ostrz.append(f"wiersz {ln['wiersz']}: liczba „{zapis}” bez źródła w fakty.json: dopisz ją do briefu "
                             "Sherlocka albo usuń (scenariusz/references/narracja.md, zasada 4)")
    return bledy, ostrz


def cmd_narration(args) -> int:
    zrodlo = Path(args.plik)
    narr = parse_narracja(zrodlo.read_text(encoding="utf-8"))
    sciezka_fakty = Path(args.fakty) if args.fakty else wl.znajdz_fakty(zrodlo.resolve().parent)
    fakty, wymowa = fakty_i_wymowa(sciezka_fakty, args.wymowa)
    linie = linie_narracji(narr, wymowa) if not narr["bledy"] else []
    if fakty is not None:
        b, o = kontrola_liczb(linie, fakty)
        narr["bledy"] += b
        narr["ostrzezenia"] += o
    pauzy, cel = _pauzy(args.pauzy), _cel(args.cel)
    slow = sum(len(ln["tts_slowa"]) for ln in linie)
    szac = slow / WORDS_PER_SEC + sum(pauzy[ln["pauza"]] for ln in linie) + pauzy["koniec"]
    raport = {"ok": not narr["bledy"], "bledy": narr["bledy"], "ostrzezenia": list(narr["ostrzezenia"]),
              "zdania": len(linie), "slowa": sum(len(ln["slowa"]) for ln in linie),
              "ujecia": len({ln["ujecie"] for ln in linie}), "rozdzialy": len(narr["rozdzialy"]),
              "fakty": sciezka_fakty.as_posix() if sciezka_fakty else None,
              "wymowa": sorted({t for ln in linie for t in ln["wymowa"]}),
              "szacunek_s": round(szac, 1)}
    if narr["bledy"] or args.sprawdz:
        if cel and linie and not cel[0] <= szac <= cel[1]:
            raport["ostrzezenia"].append(f"szacunek {szac:.0f} s poza celem {cel[0]:g}–{cel[1]:g} s")
        print(json.dumps(raport, ensure_ascii=False, indent=1))
        return 0 if raport["ok"] else 1
    wl.need("ffmpeg")
    log(f"▶ lektor: {len(linie)} zdań, głos {args.glos}, tempo {args.tempo}")
    mowy_tts = wl.speak_many([{"text": ln["tts"], "voice": args.glos, "rate": args.tempo} for ln in linie])
    mowy = []
    for sp in mowy_tts:
        od, do = granice_mowy(sp)
        mowy.append({"od": od, "do": do, "slowa": sp.words})
    os_ = uloz_os(linie, mowy, pauzy, narr["rozdzialy"])
    out = Path(args.o)
    out.parent.mkdir(parents=True, exist_ok=True)
    zloz_lektor([sp.audio for sp in mowy_tts], os_.pop("_kawalki"), os_["dlugosc"], out)
    slowa = os_.pop("_slowa")
    sciezka_os = Path(args.os) if args.os else out.parent / "os_czasu.json"
    sciezka_os.parent.mkdir(parents=True, exist_ok=True)
    slowa_json, srt = out.with_suffix(".slowa.json"), out.with_suffix(".srt")
    wl.write_json(slowa_json, [{"start": w.start, "end": w.end, "text": w.text, **({"podzial": True} if w.podzial else {})}
                               for w in slowa])
    srt.write_text(wl.build_srt(slowa), encoding="utf-8")
    os_ = {"wersja": 1, "zrodlo": zrodlo.as_posix(), "lektor": out.as_posix(), "glos": args.glos, "tempo": args.tempo, **os_}
    wl.write_json(sciezka_os, os_)
    raport["ostrzezenia"] += kontrola_osi(os_, cel)
    raport.update({"dlugosc_s": os_["dlugosc"], "mowa_s": os_["mowa_s"],
                   "tempo_slow_s": round(tempo_narracji(os_), 2),
                   "pliki": {"lektor": out.as_posix(), "os_czasu": sciezka_os.as_posix(), "slowa": slowa_json.as_posix(),
                             "srt": srt.as_posix()},
                   "render": f"html_wideo.py wideo <strona> --preset jarvo --dlugosc {os_['dlugosc']:g}"})
    raport.pop("szacunek_s")
    print(json.dumps(raport, ensure_ascii=False, indent=1))
    return 0


def cmd_voice(args) -> int:
    text = Path(args.plik).read_text(encoding="utf-8") if args.plik else args.tekst
    if not text:
        raise SystemExit("Podaj tekst albo --plik")
    sp = wl.speak_many([{"text": text.strip(), "voice": args.glos, "rate": args.tempo}])[0]
    out = Path(args.o)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sp.audio, out)
    wl.write_json(out.with_suffix(".slowa.json"), [w.__dict__ for w in sp.words])
    print(json.dumps({"plik": out.as_posix(), "sek": round(sp.duration, 2), "slowa": len(sp.words),
                      "slowa_json": out.with_suffix(".slowa.json").as_posix()}, ensure_ascii=False))
    return 0


def cmd_voices(_args) -> int:
    for name, note in wl.LOCAL_VOICES.items():
        print(f"{name:<28} {'':<7} {note}{' (domyślny)' if name == wl.DEFAULT_VOICE else ''}")
    for v in wl.list_voices("pl-PL"):
        note = wl.PL_VOICES.get(v["ShortName"], "")
        print(f"{v['ShortName']:<28} {v.get('Gender', ''):<7} {note}")
    print("Wielojęzyczne (też czytają po polsku, inna barwa): en-US-AndrewMultilingualNeural, en-US-AvaMultilingualNeural, "
          "de-DE-SeraphinaMultilingualNeural")
    return 0


def cmd_cache(args) -> int:
    """Rozmiar cache i sprzątanie plików starszych niż N dni (lektor, stock, sceny, rendery)."""
    root = wl.cache_dir()
    now = time.time()
    total = removed = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        size = p.stat().st_size
        if args.starsze_niz is not None and now - p.stat().st_mtime > args.starsze_niz * 86400:
            p.unlink()
            removed += size
        else:
            total += size
    for d in sorted((d for d in root.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
        if not any(d.iterdir()):
            d.rmdir()
    print(json.dumps({"cache": root.as_posix(), "mb": round(total / 1048576, 1), "usuniete_mb": round(removed / 1048576, 1)},
                     ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("sprawdz", help="walidacja planu i szacunek długości")
    c.add_argument("plan")
    r = sub.add_parser("render", help="render filmu z planu")
    r.add_argument("plan")
    r.add_argument("--szkic", action="store_true", help="połowa rozdzielczości, szybkie kodowanie")
    r.add_argument("--format", help="np. 9:16,16:9 (domyślnie z planu)")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--wariant", help="nazwa wariantu z planu (domyślnie bazowy)")
    g.add_argument("--wszystkie", action="store_true", help="wszystkie warianty")
    r.add_argument("--out", default="out/wideo")
    v = sub.add_parser("lektor", help="sam lektor (MP3 + czasy słów)")
    v.add_argument("tekst", nargs="?")
    v.add_argument("--plik", help="tekst z pliku")
    v.add_argument("-o", required=True)
    v.add_argument("--glos", default=wl.DEFAULT_VOICE)
    v.add_argument("--tempo", default="+0%")
    n = sub.add_parser("narracja", help="lektor z pliku narracji: pauzy z akapitów, oś czasu z chwilami (os_czasu.json)")
    n.add_argument("plik", help="narracja.txt")
    n.add_argument("-o", default="out/wideo/src/lektor.wav", help="plik lektora (.wav, albo .mp3/.m4a)")
    n.add_argument("--os", help="gdzie zapisać os_czasu.json (domyślnie obok lektora; strona animacji czyta go obok siebie)")
    n.add_argument("--glos", default=wl.DEFAULT_VOICE)
    n.add_argument("--tempo", default="+0%")
    n.add_argument("--pauzy", help="np. zdanie=0.4,akapit=1.2 (domyślnie " + ",".join(f"{k}={v:g}" for k, v in PAUZY.items()) + ")")
    n.add_argument("--cel", help="docelowa długość w s, np. 60-90 (ostrzeżenie poza zakresem)")
    n.add_argument("--fakty", help="brief Sherlocka (domyślnie fakty.json obok narracji albo katalog wyżej): liczby "
                   "lektora muszą mieć w nim źródło, słowniczek daje wymowę terminów")
    n.add_argument("--wymowa", help='JSON {"Next.js": "nekst dżej es"}: jak lektor ma czytać termin (napis zostaje w pisowni)')
    n.add_argument("--sprawdz", action="store_true", help="tylko kontrola tekstu i szacunek długości, bez syntezy")
    sub.add_parser("glosy", help="głosy lektora: lokalne i Edge TTS")
    k = sub.add_parser("cache", help="rozmiar cache; --starsze-niz N usuwa pliki starsze niż N dni")
    k.add_argument("--starsze-niz", type=float, default=None)
    args = ap.parse_args(argv)
    try:
        return {"render": cmd_render, "sprawdz": cmd_check, "lektor": cmd_voice, "narracja": cmd_narration, "glosy": cmd_voices,
                "cache": cmd_cache}[args.cmd](args)
    except wl.FFError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
