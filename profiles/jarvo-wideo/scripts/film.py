#!/usr/bin/env python3
"""Krótki film z planu (plan.json): lektor PL → ujęcia (stock, pliki, AI, kolor) → napisy z czasu słów → muzyka → MP4.

    python3 film.py sprawdz plan.json                        # walidacja i szacunek długości, bez renderu
    python3 film.py render plan.json [--szkic] [--format 9:16,16:9] [--wariant B | --wszystkie] [--out out/wideo]
    python3 film.py lektor "Tekst lektora." -o lektor.mp3 [--glos pl-PL-ZofiaNeural] [--tempo +5%]
    python3 film.py glosy                                    # polskie głosy Edge TTS
    python3 film.py cache [--starsze-niz 14]                 # rozmiar cache i sprzątanie

Format planu: skill krotki-film, plik references/plan.md. Każdy etap ma cache (lektor, pobrane ujęcia, sceny
po normalizacji), więc warianty i poprawki renderują się szybko, a drugi render tego samego planu nie pobiera
niczego z sieci. `--szkic` = połowa rozdzielczości i szybkie kodowanie: do sprawdzenia rytmu przed finałem.
Wynik: <out>/<slug>/<slug>[-wariant]-<format>.mp4, .srt, miniatura, film.json (sceny, źródła, licencje, czasy).
"""

from __future__ import annotations

import argparse
import copy
import json
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

WORDS_PER_SEC = 2.5          # tempo Edge TTS po polsku przy +0% (do szacunku bez syntezy)
SCENE_GAP = 0.18             # oddech między scenami
TAIL = 0.6                   # zapas na końcu filmu
MIN_SCENE = 1.2
XFADE = 0.35                 # przenikanie
PLATFORM_MAX = {"9:16": 90, "1:1": 120, "4:5": 120, "16:9": 600}   # rozsądna górna granica krótkiego formatu
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")          # libass nie rysuje emoji (puste kratki)
KNOWLEDGE = Path(os.environ.get("JARVO_KNOWLEDGE_DIR", "/opt/data/jarvo/knowledge"))


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
        warns.append(f"lektor {voice['glos']}: to nie jest polski głos (pl-PL-MarekNeural / pl-PL-ZofiaNeural)")
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
    key = wl.digest("scena-v1", key_src, w, h, round(dur, 3), uj.get("od", 0), uj.get("ruch"), mode, draft,
                    *([end] if end != "petla" else []))
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
        z = 0.12
        motion = uj.get("ruch", "zoom")
        if motion == "brak":
            zexpr, xexpr, yexpr = "1", "0", "0"
        elif motion == "oddal":
            zexpr, xexpr, yexpr = f"max(1.0,{1 + z}-{z}*on/{frames})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        elif motion == "panorama":
            zexpr, xexpr, yexpr = "1.10", f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"
        else:
            zexpr, xexpr, yexpr = f"min({1 + z},1+{z}*on/{frames})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        vf = (f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,crop={big_w}:{big_h},"
              f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}':d={frames}:s={w}x{h}:fps={wl.FPS},{wl.TV_RANGE},setsar=1")
        wl.run(["ffmpeg", "-y", "-i", str(src["plik"]), "-vf", vf, "-frames:v", str(frames), *enc, str(tmp)])
    else:
        start = float(uj.get("od", 0) or 0)
        src_dur = wl.duration(src["plik"])
        short = src_dur - start < dur - 0.05
        # krótszy klip: stock zapętlamy; animacja z kodu (koniec: stop) trzyma ostatnią klatkę do końca sceny
        loop = ["-stream_loop", "-1"] if short and end != "stop" else []
        hold = f"tpad=stop_mode=clone:stop_duration={dur:.3f}," if short and end == "stop" else ""
        fit = fit_filter(w, h, mode)
        chain = f"{hold}{fit},fps={wl.FPS},{wl.TV_RANGE},setsar=1"
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
        extra = ":fontsdir=fonts" if fonts.is_dir() else ""
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
              "muzyka": str(music) if music else None, "pliki": {}, "sceny": [], "ostrzezenia": warns}
    if words:
        srt = target / f"{slug}{suffix}.srt"
        srt.write_text(wl.build_srt(words), encoding="utf-8")
        result["srt"] = str(srt)

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
        info = {"plik": str(out), "rozdzielczosc": f"{w}x{h}", "sek": round(wl.duration(out), 2),
                "mb": round(out.stat().st_size / 1048576, 2)}
        if not draft:
            thumb = target / f"{slug}{suffix}-{wl.fmt_slug(fmt)}-miniatura.jpg"
            wl.run(["ffmpeg", "-y", "-ss", f"{min(durs[0] * 0.5, 1.2):.2f}", "-i", str(out), "-frames:v", "1", "-q:v", "2", str(thumb)])
            info["miniatura"] = str(thumb)
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
    results = [render_variant(variant_plan(plan, n), n, suffix(n), fmts, args.szkic, outdir, plan_path.parent) for n in names]
    print(json.dumps({"ok": True, "filmy": results}, ensure_ascii=False, indent=1))
    return 0


def cmd_check(args) -> int:
    plan_path = Path(args.plan).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = check_plan(plan, plan_path.parent)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["ok"] else 1


def cmd_voice(args) -> int:
    text = Path(args.plik).read_text(encoding="utf-8") if args.plik else args.tekst
    if not text:
        raise SystemExit("Podaj tekst albo --plik")
    sp = wl.speak_many([{"text": text.strip(), "voice": args.glos, "rate": args.tempo}])[0]
    out = Path(args.o)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sp.audio, out)
    wl.write_json(out.with_suffix(".slowa.json"), [w.__dict__ for w in sp.words])
    print(json.dumps({"plik": str(out), "sek": round(sp.duration, 2), "slowa": len(sp.words),
                      "slowa_json": str(out.with_suffix(".slowa.json"))}, ensure_ascii=False))
    return 0


def cmd_voices(_args) -> int:
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
    print(json.dumps({"cache": str(root), "mb": round(total / 1048576, 1), "usuniete_mb": round(removed / 1048576, 1)},
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
    sub.add_parser("glosy", help="polskie głosy Edge TTS")
    k = sub.add_parser("cache", help="rozmiar cache; --starsze-niz N usuwa pliki starsze niż N dni")
    k.add_argument("--starsze-niz", type=float, default=None)
    args = ap.parse_args(argv)
    try:
        return {"render": cmd_render, "sprawdz": cmd_check, "lektor": cmd_voice, "glosy": cmd_voices,
                "cache": cmd_cache}[args.cmd](args)
    except wl.FFError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
