"""Wspólne klocki skryptów Wideografa: formaty, FFmpeg/ffprobe, lektor (Edge TTS), napisy ASS/SRT, cache.

Bez zależności poza biblioteką standardową, FFmpeg i (tylko dla lektora) edge-tts. Edge TTS jest darmowy
i nie wymaga klucza; pakiet leży w katalogu leniwych instalacji Hermesa (HERMES_LAZY_INSTALL_TARGET),
a gdy go brak, doinstalowujemy go tym samym mechanizmem, którego używa narzędzie `text_to_speech`.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# silnik edytora HQ (wspólne reguły z eksportem, np. HDR → zwykły obraz): w dystrybucji kopiowany obok (build.py),
# w repo leży w hq/plugin (jak w projekt.py)
_HERE = Path(__file__).resolve().parent
for _cand in (_HERE, (_HERE.parents[2] if len(_HERE.parents) > 2 else _HERE) / "hq" / "plugin"):
    if (_cand / "edytor.py").exists():
        sys.path.insert(0, str(_cand))
        break
import edytor as ed  # noqa: E402

# ------------------------------------------------------------------ formaty

FORMATS = {  # proporcje → rozdzielczość finalna (szkic: połowa)
    "9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350),
}
FPS = 30
# zakres „TV” (limited) + yuv420p: JPEG i część telefonów dają pełny zakres (yuvj420p), którego platformy nie lubią
TV_RANGE = "scale=out_range=tv,format=yuv420p"
# RAM na VPS 8 GB: x264 domyślnie bierze wątki i bufory lookahead ze wszystkich rdzeni (~0,65 GB samego kodera
# przy 1080×1920, a z filtrami ~0,9 GB). 2 wątki + lookahead 10 ≈ 0,3 GB kodera; jakość przy CRF 19–20 bez różnicy.
# Więcej rdzeni i RAM-u: JARVO_WIDEO_WATKI=4.
THREADS = os.environ.get("JARVO_WIDEO_WATKI", "2")
ENC_LIMITS = ["-threads", THREADS, "-filter_threads", "2", "-x264-params", "rc-lookahead=10"]
PARALLEL = max(1, int(os.environ.get("JARVO_WIDEO_ROWNOLEGLE", "1")))   # sceny normalizowane naraz
DEFAULT_VOICE = "pl-PL-MarekNeural"
PL_VOICES = {"pl-PL-MarekNeural": "męski, spokojny", "pl-PL-ZofiaNeural": "żeński, ciepły"}
# lektor angielski bez sieci i bez limitu: Paradee-8M w obrazie (/opt/jarvo/bin/jarvo-tts); czasy słów z Parakeeta
LOCAL_VOICES = {"en-US-Paradee": "angielski, lokalny (Paradee, bez sieci)"}


def parse_format(fmt: str) -> tuple[int, int]:
    fmt = str(fmt).strip().replace("x", ":").replace("/", ":")
    if fmt not in FORMATS:
        raise SystemExit(f"Nieznany format {fmt!r}. Dostępne: {', '.join(FORMATS)}")
    return FORMATS[fmt]


def fmt_slug(fmt: str) -> str:
    return fmt.replace(":", "x")


def orientation(fmt: str) -> str:
    w, h = parse_format(fmt)
    return "portrait" if h > w else "landscape" if w > h else "square"


def even(n: float) -> int:
    return int(round(n / 2)) * 2


# ------------------------------------------------------------------ cache i ścieżki

def cache_dir(*parts: str) -> Path:
    """Wspólny cache Wideografa (pobrane ujęcia, lektor, znormalizowane sceny): między kartami i wariantami."""
    base = os.environ.get("JARVO_WIDEO_CACHE")
    if not base:
        base = "/opt/data/jarvo/cache/wideo" if Path("/opt/data/jarvo").is_dir() else str(Path.home() / ".cache" / "jarvo-wideo")
    p = Path(base, *parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------------ miejsca renderu

RENDER_MIEJSCA = 2          # pełnych renderów naraz na maszynie (JARVO_RENDER_MIEJSCA)
RENDER_WOLNA = 30.0         # % wolnej pamięci, przy którym kolejny render rusza obok trwającego (JARVO_RENDER_WOLNA)


def wolna_pamiec() -> tuple[float, float]:
    """(procent, GB) dostępnej pamięci: limit kontenera (cgroup v2), gdy jest, a inaczej /proc/meminfo; bez nich (100, 8)."""
    try:
        cg = Path("/sys/fs/cgroup")
        limit = (cg / "memory.max").read_text().strip()
        if limit.isdigit():
            wolne = int(limit) - int((cg / "memory.current").read_text().strip())
            return 100.0 * wolne / int(limit), wolne / 2 ** 30
    except (OSError, ValueError):
        pass
    try:
        info = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines() if ":" in line)
        avail, total = (int(info[k].split()[0]) for k in ("MemAvailable", "MemTotal"))
        return 100.0 * avail / total, avail / 2 ** 20
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        return 100.0, 8.0


@contextlib.contextmanager
def miejsce_renderu(co: str = "render", czekaj_s: float = 2.0):
    """Najwyżej JARVO_RENDER_MIEJSCA (domyślnie 2) pełnych renderów naraz na tej maszynie, a kolejny obok trwającego
    rusza tylko przy wolnej pamięci ≥ JARVO_RENDER_WOLNA % (domyślnie 30); pierwszy rusza zawsze. Pomysł i liczby
    z lemo-opuscar (`core/render/slot.mjs`, MIT), u nas blokada `flock` na pliku miejsca, więc padnięty proces
    zwalnia miejsce sam. Render uruchomiony z renderu (JARVO_RENDER_ZAJETE=1) nie zajmuje drugiego miejsca."""
    if os.environ.get("JARVO_RENDER_ZAJETE") == "1":
        yield
        return
    import fcntl
    miejsca = max(1, int(os.environ.get("JARVO_RENDER_MIEJSCA") or RENDER_MIEJSCA))
    prog = float(os.environ.get("JARVO_RENDER_WOLNA") or RENDER_WOLNA)
    katalog = Path(os.environ.get("JARVO_RENDER_KATALOG") or Path(tempfile.gettempdir()) / f"jarvo-render-{os.getuid()}")
    katalog.mkdir(parents=True, exist_ok=True)
    start, nastepny_komunikat = time.monotonic(), 0.0
    while True:
        moje, zajete = None, 0
        for i in range(miejsca):
            f = open(katalog / f"miejsce{i}", "a+")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                zajete += 1
                f.close()
                continue
            if moje is None:
                moje = f
            else:
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
        if moje is not None and (zajete == 0 or wolna_pamiec()[0] >= prog):
            break
        if moje is not None:
            fcntl.flock(moje, fcntl.LOCK_UN)
            moje.close()
        czekam = time.monotonic() - start
        if czekam >= nastepny_komunikat:
            powod = "wszystkie miejsca zajęte" if moje is None else f"wolna pamięć < {prog:g}% przy trwającym renderze"
            print(f"⏳ {co}: czekam na miejsce renderu ({powod}; najwyżej {miejsca} naraz)", file=sys.stderr, flush=True)
            nastepny_komunikat = czekam + 60
        time.sleep(czekaj_s)
    stare = os.environ.get("JARVO_RENDER_ZAJETE")
    os.environ["JARVO_RENDER_ZAJETE"] = "1"          # podprocesy renderu (ffmpeg, html_wideo z innego skryptu) już w środku
    try:
        moje.seek(0)
        moje.truncate()
        moje.write(f"{os.getpid()} {co}\n")
        moje.flush()
        yield
    finally:
        if stare is None:
            os.environ.pop("JARVO_RENDER_ZAJETE", None)
        else:
            os.environ["JARVO_RENDER_ZAJETE"] = stare
        fcntl.flock(moje, fcntl.LOCK_UN)
        moje.close()


def digest(*items) -> str:
    h = hashlib.sha256()
    for it in items:
        h.update(json.dumps(it, sort_keys=True, ensure_ascii=False, default=str).encode())
        h.update(b"\0")
    return h.hexdigest()[:20]


def file_key(path: Path) -> list:
    st = path.stat()
    return [str(path.resolve()), st.st_size, int(st.st_mtime)]


def slugify(text: str, limit: int = 48) -> str:
    t = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return (t[:limit].rstrip("-")) or "film"


# ------------------------------------------------------------------ FFmpeg

class FFError(RuntimeError):
    pass


def need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise SystemExit(f"Brak {tool} w PATH (obraz Hermesa ma FFmpeg w /usr/bin).")
    return path


def run(cmd: list[str], cwd: Path | None = None, quiet: bool = True) -> subprocess.CompletedProcess:
    """Uruchom FFmpeg/ffprobe; przy błędzie pokaż ogon stderr (sam komunikat, bez całego logu)."""
    if cmd and cmd[0] == "ffmpeg":
        cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error" if quiet else "info", *cmd[1:]]
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        lines = (res.stderr or res.stdout or "").strip().splitlines()
        # pierwsza przyczyna bywa na początku (filtr), a na końcu tylko skutki (koder bez danych)
        tail = "\n".join(dict.fromkeys(lines[:6] + lines[-6:]))
        raise FFError(f"{cmd[0]} zakończył się błędem ({res.returncode}):\n{tail}")
    return res


def obrot(v: dict) -> int:
    """Obrót wyświetlania w stopniach: macierz obrotu (ffmpeg 5+, side_data_list) albo stary tag `rotate`.
    Ta sama reguła co `obrot` w hq/plugin/edytor.py."""
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


def probe(path: Path) -> dict:
    """Parametry pliku. Wymiary wideo tak, jak film się wyświetla: pion z telefonu (poziome klatki + obrót 90°)
    ma width < height, bo ffmpeg obraca klatki przy dekodowaniu. `video.hdr` = rodzaj HDR (np. „HLG” z iPhone'a)
    albo None, `video.sdr` = łańcuch przeliczenia na zwykły obraz (edytor.sdr_filter; "" dla zwykłego filmu)."""
    res = run(["ffprobe", "-v", "error", "-show_entries",
               f"stream=index,codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels,{ed.PROBE_KOLOR}"
               f":stream_side_data={ed.PROBE_SIDE}:stream_tags=rotate:format=duration,size,format_name",
               "-of", "json", str(path)])
    data = json.loads(res.stdout or "{}")
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fps = 0.0
    if v and v.get("r_frame_rate") and "/" in v["r_frame_rate"]:
        n, d = v["r_frame_rate"].split("/")
        fps = float(n) / float(d) if float(d) else 0.0
    fmt = data.get("format", {})
    hd = ed.hdr(v) if v and not is_image(Path(path)) else None
    return {
        "duration": float(fmt.get("duration") or 0), "size": int(fmt.get("size") or 0),
        "format_name": fmt.get("format_name", ""),
        "video": v and {"codec": v.get("codec_name"),
                        **dict(zip(("width", "height"), (v.get("height"), v.get("width")) if obrot(v) in (90, 270)
                                   else (v.get("width"), v.get("height")))),
                        "fps": round(fps, 3), "pix_fmt": v.get("pix_fmt"),
                        "hdr": hd and hd["rodzaj"], "hdr_uwaga": hd and hd["uwaga"], "sdr": ed.sdr_filter(hd)},
        "audio": a and {"codec": a.get("codec_name"), "sample_rate": int(a.get("sample_rate") or 0),
                        "channels": a.get("channels")},
    }


def duration(path: Path) -> float:
    return probe(path)["duration"]


def sdr(path: Path) -> str:
    """Łańcuch HDR → zwykły obraz dla filmu (edytor.sdr_filter) albo "" (zwykły film, zdjęcie, brak obrazu).
    Wstawiasz go po skalowaniu do kadru, przed napisami i korekcją koloru; HDR zgłaszamy na stderr."""
    v = probe(path).get("video") or {}
    if v.get("hdr"):
        print(f"HDR ({v['hdr']}): {Path(path).name} przeliczam na zwykły obraz (SDR)"
              + (f"; uwaga: {v['hdr_uwaga']}" if v.get("hdr_uwaga") else ""), file=sys.stderr)
    return v.get("sdr") or ""


def czcionka(rozmiar: int):
    """Krój z polskimi znakami do podpisów na arkuszach (Pillow)."""
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, rozmiar)
    try:
        return ImageFont.load_default(size=rozmiar)
    except TypeError:
        return ImageFont.load_default()


def z_sdr(chain: str, sdr_vf: str) -> str:
    """`chain` + przeliczenie HDR (gdy jest), przecinkiem; pusty łańcuch zostaje pusty."""
    return ",".join(x for x in (chain, sdr_vf) if x)


IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".gif"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXT


# ------------------------------------------------------------------ lektor: Edge TTS z czasem słów

@dataclass
class Word:
    start: float
    end: float
    text: str
    podzial: bool = False      # po tym słowie kończy się grupa napisów (`|` i koniec linii w `film.py narracja`)


@dataclass
class Speech:
    audio: Path
    duration: float
    words: list[Word] = field(default_factory=list)


def _import_edge_tts():
    try:
        import edge_tts  # type: ignore
        return edge_tts
    except ImportError:
        pass
    target = os.environ.get("HERMES_LAZY_INSTALL_TARGET", "/opt/data/lazy-packages")
    if Path(target, "edge_tts").is_dir() and target not in sys.path:
        sys.path.insert(0, target)
        try:
            import edge_tts  # type: ignore
            return edge_tts
        except ImportError:
            pass
    hermes_py = Path("/opt/hermes/.venv/bin/python")
    if hermes_py.exists():  # ten sam instalator, którego używa narzędzie text_to_speech Hermesa
        subprocess.run([str(hermes_py), "-c", "from tools.lazy_deps import ensure; ensure('tts.edge', prompt=False)"],
                       cwd="/opt/hermes", capture_output=True, text=True, timeout=300)
        if target not in sys.path:
            sys.path.insert(0, target)
        try:
            import edge_tts  # type: ignore
            return edge_tts
        except ImportError:
            pass
    raise SystemExit("Brak pakietu edge-tts. Użyj raz narzędzia text_to_speech (Hermes go doinstaluje) "
                     "albo: pip install edge-tts==7.2.7")


def _ssl_bundle():
    """Proxy firmowe z własnym CA: edge-tts bierze certyfikaty z certifi, więc honorujemy SSL_CERT_FILE."""
    bundle = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if bundle and Path(bundle).is_file():
        try:
            import certifi  # type: ignore
            certifi.where = lambda: bundle  # noqa: E731
        except ImportError:
            pass


def list_voices(locale: str = "pl-PL") -> list[dict]:
    edge_tts = _import_edge_tts()
    _ssl_bundle()
    voices = asyncio.run(edge_tts.list_voices())
    return [v for v in voices if v.get("Locale", "").lower().startswith(locale.lower())]


async def _synth(edge_tts, text: str, voice: str, rate: str, volume: str, pitch: str, out: Path) -> list[Word]:
    comm = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch, boundary="WordBoundary")
    words: list[Word] = []
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                s = chunk["offset"] / 1e7
                words.append(Word(round(s, 3), round(s + chunk["duration"] / 1e7, 3), chunk["text"]))
    return words


def _speed(rate: str) -> float:
    """Tempo Edge („+10%”) → szybkość lokalnego lektora (1.1), w granicach 0.5–2.0."""
    m = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*%\s*", rate or "+0%")
    return max(0.5, min(2.0, 1 + float(m.group(1)) / 100)) if m else 1.0


def _volume(volume: str) -> float:
    m = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*%\s*", volume or "+0%")
    return max(0.0, 1 + float(m.group(1)) / 100) if m else 1.0


def time_script_words(text: str, heard: list[Word], sentences: list[tuple[float, float, str]]) -> list[Word]:
    """Słowa tekstu lektora z czasem: dopasowanie do słów usłyszanych przez Parakeeta (difflib), luki rozłożone
    proporcjonalnie między dopasowanymi sąsiadami, a bez Parakeeta proporcjonalnie w obrębie zdań."""
    import difflib

    toks = text.split()
    base = words_from_lines([(a, b, z) for a, b, z in sentences])
    if len(base) != len(toks):            # zdania rozbite inaczej niż spacje tekstu: jedna linia na całość
        end = sentences[-1][1] if sentences else 0.0
        base = words_from_lines([(0.0, end, text)]) if toks else []
    if not heard:
        return [Word(w.start, w.end, t) for w, t in zip(base, toks)]
    times: list[tuple[float, float] | None] = [None] * len(toks)
    sm = difflib.SequenceMatcher(None, [_norm(t) for t in toks], [_norm(w.text) for w in heard], autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            h = heard[blk.b + k]
            times[blk.a + k] = (h.start, h.end)
    i = 0
    while i < len(toks):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(toks) and times[j] is None:
            j += 1
        a = times[i - 1][1] if i > 0 else (base[i].start if base else 0.0)
        b = times[j][0] if j < len(toks) else (base[j - 1].end if base else a)
        if b - a < 0.08 * (j - i):        # brak miejsca między sąsiadami: czasy z podziału na zdania
            for k in range(i, j):
                times[k] = (base[k].start, base[k].end) if base else (a, a)
        else:
            run = words_from_lines([(a, b, " ".join(toks[i:j]))])
            for k, w in zip(range(i, j), run):
                times[k] = (w.start, w.end)
        i = j
    return [Word(round(a, 3), round(b, 3), t) for (a, b), t in zip(times, toks)]


def _heard_per_item(wavs: list[Path], tmp: Path) -> list[list[Word]]:
    """Słowa usłyszane przez Parakeeta w każdym nagraniu. Wszystkie WAV-y sklejone w jeden plik z 0,6 s ciszy
    między nimi: model ładuje się raz (narracja to kilkadziesiąt zdań), a słowa wracają do nagrań po czasie.
    Brak jarvo-stt albo błąd → puste listy (czasy z podziału na zdania)."""
    import wave

    gap, spans, frames, params = 0.6, [], [], None
    t = 0.0
    for w in wavs:
        with wave.open(str(w), "rb") as r:
            params = params or r.getparams()
            data = r.readframes(r.getnframes())
            dur = r.getnframes() / r.getframerate()
        if frames:
            frames.append(b"\0" * (int(gap * params.framerate) * params.sampwidth * params.nchannels))
            t += gap
        frames.append(data)
        spans.append((t, t + dur))
        t += dur
    if not frames:
        return [[] for _ in wavs]
    joined = tmp / "razem.wav"
    with wave.open(str(joined), "wb") as out:
        out.setparams(params)
        out.writeframes(b"".join(frames))
    try:
        heard = transcribe_words(joined)
    except SystemExit:
        return [[] for _ in wavs]
    per: list[list[Word]] = [[] for _ in wavs]
    for h in heard:
        mid = (h.start + h.end) / 2
        for k, (a, b) in enumerate(spans):
            if a - gap / 2 <= mid < b + gap / 2:
                per[k].append(Word(round(max(0.0, h.start - a), 3), round(min(b - a, max(0.0, h.end - a)), 3), h.text))
                break
    return per


def _speak_local(todo: list[tuple]) -> None:
    """Lektor lokalny: jedno wywołanie jarvo-tts na wszystkie teksty (model ładuje się raz), WAV → MP3,
    czasy słów z jednego przebiegu Parakeeta (bez niego, np. bez sieci przy pierwszym użyciu: z podziału na zdania)."""
    tts = os.environ.get("JARVO_TTS_BIN", "/opt/jarvo/bin/jarvo-tts")
    if not os.path.exists(tts):
        tts = shutil.which("jarvo-tts") or ""
    if not tts:
        raise SystemExit("Brak jarvo-tts (obraz Jarvo: /opt/jarvo/bin/jarvo-tts); głos en-US-Paradee działa tylko w obrazie.")
    with tempfile.TemporaryDirectory(prefix="jarvo-tts-") as tmpd:
        tmp = Path(tmpd)
        jobs = [{"tekst": it["text"], "wyjscie": str(tmp / f"{n}.wav"), "szybkosc": _speed(it.get("rate", "+0%"))}
                for n, (_, it, _, _, _) in enumerate(todo)]
        plan = tmp / "zadania.json"
        plan.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        res = subprocess.run([tts, "--wsad", str(plan)], capture_output=True, text=True)
        if res.returncode != 0:
            tail = "\n".join((res.stderr or res.stdout or "").strip().splitlines()[-6:])
            raise SystemExit(f"Lektor lokalny (jarvo-tts) nie powiódł się:\n{tail}")
        done = json.loads(res.stdout)
        heard = _heard_per_item([Path(j["wyjscie"]) for j in jobs], tmp)
        for (_, it, mp3, meta, out_set), job, r, h in zip(todo, jobs, done, heard):
            tmp_mp3 = mp3.with_suffix(".part.mp3")
            run(["ffmpeg", "-y", "-i", job["wyjscie"], "-af", f"volume={_volume(it.get('volume', '+0%')):.3f}",
                 "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", str(tmp_mp3)])
            tmp_mp3.replace(mp3)
            words = time_script_words(it["text"], h, [tuple(z) for z in r["zdania"]])
            dur = duration(mp3)
            meta.write_text(json.dumps({"duration": dur, "words": [w.__dict__ for w in words], "text": it["text"],
                                        "voice": it.get("voice"), "czasy": "parakeet" if h else "zdania"},
                                       ensure_ascii=False), encoding="utf-8")
            out_set(Speech(mp3, dur, words))


def speak_many(items: list[dict], concurrency: int = 4) -> list[Speech]:
    """Lektor dla wielu tekstów naraz; wynik w cache (ten sam tekst i głos = zero zapytań).
    Głosy Edge TTS (sieć, czasy słów z usługi) albo lokalny `en-US-Paradee` (LOCAL_VOICES)."""
    out: list[Speech | None] = [None] * len(items)
    todo, local = [], []
    for i, it in enumerate(items):
        key = digest("tts-v1", it["text"], it.get("voice", DEFAULT_VOICE), it.get("rate", "+0%"),
                     it.get("volume", "+0%"), it.get("pitch", "+0Hz"))
        mp3 = cache_dir("lektor") / f"{key}.mp3"
        meta = mp3.with_suffix(".json")
        if mp3.exists() and meta.exists() and mp3.stat().st_size > 0:
            m = json.loads(meta.read_text(encoding="utf-8"))
            out[i] = Speech(mp3, m["duration"], [Word(**w) for w in m["words"]])
        elif it.get("voice") in LOCAL_VOICES:
            local.append((i, it, mp3, meta, lambda s, i=i: out.__setitem__(i, s)))
        else:
            todo.append((i, it, mp3, meta))
    if local:
        _speak_local(local)
    if todo:
        edge_tts = _import_edge_tts()
        _ssl_bundle()

        async def worker(sem, i, it, mp3, meta):
            async with sem:
                tmp = mp3.with_suffix(".part")
                for attempt in range(3):
                    try:
                        words = await _synth(edge_tts, it["text"], it.get("voice", DEFAULT_VOICE), it.get("rate", "+0%"),
                                             it.get("volume", "+0%"), it.get("pitch", "+0Hz"), tmp)
                        break
                    except Exception as exc:  # noqa: BLE001  (sieć: krótka ponowna próba)
                        if attempt == 2:
                            raise SystemExit(f"Lektor (Edge TTS) nie odpowiedział: {exc}")
                        await asyncio.sleep(1.5 * (attempt + 1))
                tmp.replace(mp3)
                dur = duration(mp3)
                meta.write_text(json.dumps({"duration": dur, "words": [w.__dict__ for w in words], "text": it["text"],
                                            "voice": it.get("voice", DEFAULT_VOICE)}, ensure_ascii=False), encoding="utf-8")
                out[i] = Speech(mp3, dur, words)

        async def main():
            sem = asyncio.Semaphore(concurrency)
            await asyncio.gather(*(worker(sem, *t) for t in todo))

        asyncio.run(main())
    return [s for s in out if s is not None]


# ------------------------------------------------------------------ napisy

def _norm(tok: str) -> str:
    return re.sub(r"[^\w]", "", tok.lower())


def align_display(words: list[Word], text: str) -> list[Word]:
    """Słowa z lektora → słowa do napisów w pisowni oryginału (z ? i !, bez przecinków i kropek)."""
    toks = text.split()
    j, out = 0, []
    for w in words:
        n, disp = _norm(w.text), w.text
        for k in range(j, min(j + 4, len(toks))):
            if _norm(toks[k]) == n and n:
                disp, j = toks[k], k + 1
                break
        disp = disp.strip("\"'„”«»()[]").rstrip(",.;:…")
        out.append(Word(w.start, w.end, disp or w.text, w.podzial))
    return out


# polska typografia: krótkie słowo nie zostaje na końcu grupy („sierotka”), przechodzi do następnej
ORPHANS = {"a", "i", "o", "u", "w", "z", "do", "na", "od", "po", "za", "ze", "we", "że", "to", "czy", "ale", "bo",
           "jak", "nie", "się", "dla", "pod", "nad", "przy", "bez", "oraz", "lub"}


def chunk_words(words: list[Word], max_words: int, max_chars: int) -> list[list[Word]]:
    """Grupy słów na ekran: limit słów i znaków, przerwa po końcu zdania, przy pauzie > 0,45 s albo po słowie
    z `podzial` (podział zaznaczony w tekście lektora)."""
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur:
            text_len = len(" ".join(x.text for x in cur + [w]))
            pause = w.start - cur[-1].end
            sentence_end = re.search(r"[.!?…]$", cur[-1].text) or cur[-1].podzial
            if len(cur) >= max_words or text_len > max_chars or pause > 0.45 or sentence_end:
                carry = []
                if (not sentence_end and pause <= 0.45 and len(cur) > 1
                        and re.sub(r"[^\w]", "", cur[-1].text.lower()) in ORPHANS):
                    carry = [cur.pop()]
                groups.append(cur)
                cur = carry
        cur.append(w)
    if cur:
        groups.append(cur)
    # samotne słowo na końcu zdania dołącza do poprzedniej grupy (bez „wiszących” napisów)
    merged: list[list[Word]] = []
    for g in groups:
        prev = merged[-1] if merged else None
        if (prev and len(g) == 1 and not re.search(r"[.!?…]$", prev[-1].text) and not prev[-1].podzial
                and g[0].start - prev[-1].end <= 0.45
                and len(" ".join(x.text for x in prev + g)) <= max_chars + 8):
            prev.extend(g)
        else:
            merged.append(g)
    return merged


def hex_to_ass(color: str, alpha: int = 0) -> str:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        raise SystemExit(f"Kolor {color!r}: podaj #RRGGBB")
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t: float) -> str:
    cs = max(0, int(round(t * 100)))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def srt_time(t: float) -> str:
    ms = max(0, int(round(t * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", "\\N")


@dataclass
class SubStyle:
    styl: str = "karaoke"          # karaoke | zwykle | brak
    font: str = "Inter"
    kolor: str = "#FFFFFF"
    akcent: str = "#FFD400"
    obrys: str = "#000000"
    pozycja: str = "dol"           # dol | srodek | gora
    wielkie: bool = True
    rozmiar: float = 1.0           # mnożnik wielkości

    @classmethod
    def from_dict(cls, d: dict | None) -> "SubStyle":
        d = dict(d or {})
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)


# Strefy interfejsu w kadrze 9:16: (góra, dół, lewo, prawo) jako ułamki kadru, przegląd 2026: TikTok 130/484/44/140 px,
# Shorts 180/390/60/120 px na 1080×1920, Reels wg zalecenia Meta 14% / 35% / 6%. Te same liczby: ED_STREFY w edytorze HQ.
STREFY_UI = {"tiktok": (0.068, 0.252, 0.041, 0.13), "reels": (0.14, 0.35, 0.06, 0.06), "shorts": (0.094, 0.203, 0.056, 0.111)}
# nazwy platform skryptów (qa_wideo --platforma, pomiar) → zestaw stref; bez platformy albo inna: TikTok (jak w edytorze)
STREFY_PLATFORMY = {"ig-reel": "reels", "fb-reel": "reels", "ig-story": "reels", "yt-short": "shorts", "yt-shorts": "shorts"}


def strefy_ui(w: int, h: int, platforma: str | None = None) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Prostokąty (nazwa, (x0, y0, x1, y1)) zasłaniane przez interfejs platformy; tylko kadr pionowy jak 9:16 (nie 4:5)."""
    if w / h > 0.65:
        return []
    p = STREFY_PLATFORMY.get(platforma or "", platforma or "")
    t, b, l, r = STREFY_UI.get(p, STREFY_UI["tiktok"])
    y0, y1 = h * t, h * (1 - b)
    return [("góra (zakładki, nazwa konta)", (0, 0, w, y0)), ("dół (opis, konto, dźwięk)", (0, y1, w, h)),
            ("lewy margines", (0, y0, w * l, y1)), ("prawy pasek przycisków", (w * (1 - r), y0, w, y1))]


def safe_margins(w: int, h: int) -> dict:
    """Marginesy napisów poza strefami interfejsu platform (9:16: nad opisem TikToka, szerszy margines przycisków)."""
    if h > w:   # prawy margines szerszy: pasek przycisków (serce, komentarze, udostępnij)
        return {"dol": even(h * 0.26), "srodek": 0, "gora": even(h * 0.14), "l": even(w * 0.08), "r": even(w * 0.16)}
    return {"dol": even(h * 0.08), "srodek": 0, "gora": even(h * 0.08), "l": even(w * 0.06), "r": even(w * 0.06)}


# Pas napisów lektora: część kadru, którą zakryją napisy. Edytor HQ i projekt.py: środek napisu y 0,84 (w pionie
# 0,68), krój 58 px na 1080, wiersz 1,18, do dwóch wierszy; napisy ASS (build_ass): dół z safe_margins, krój 0,058
# (pion 0,074) krótszego boku, do dwóch wierszy. Ułamki kadru (x0, y0, x1, y1) z zapasem na obrys;
# tests/test_pomiar.py pilnuje zgodności z obiema drogami napisów.
PAS_NAPISOW = {"pion": (0.075, 1220 / 1920, 0.875, 1440 / 1920), "poziom": (0.055, 830 / 1080, 0.945, 1005 / 1080)}


def pas_napisow(w: int, h: int) -> tuple[float, float, float, float]:
    """Prostokąt pasa napisów lektora w px kadru w×h."""
    x0, y0, x1, y1 = PAS_NAPISOW["pion" if h > w else "poziom"]
    return (w * x0, h * y0, w * x1, h * y1)


def margines_napisow(w: int, h: int) -> int:
    """Dolny margines treści (`safe.bottom` gramatyk), przy którym nic nie wchodzi w pas napisów."""
    return int(-(-(h - pas_napisow(w, h)[1] - 1e-6) // 1))


def build_ass(w: int, h: int, words: list[Word], style: SubStyle, titles: list[tuple[float, float, str]] | None = None) -> str:
    """Plik ASS: napisy z czasu słów (karaoke = aktywne słowo w kolorze akcentu) + teksty ekranowe scen."""
    portrait = h > w
    size = even(min(w, h) * (0.074 if portrait else 0.058) * style.rozmiar)
    outline = max(2, round(size * 0.075))
    m = safe_margins(w, h)
    align = {"dol": 2, "srodek": 5, "gora": 8}.get(style.pozycja, 2)
    margin_v = m.get(style.pozycja, m["dol"])
    prim, acc, out = hex_to_ass(style.kolor), hex_to_ass(style.akcent), hex_to_ass(style.obrys)
    tsize = even(size * 1.25)
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Napisy,{style.font},{size},{prim},{acc},{out},&H64000000,-1,0,0,0,100,100,0,0,1,{outline},{max(1, outline // 2)},"
        f"{align},{m['l']},{m['r']},{margin_v},1",
        f"Style: Tytul,{style.font},{tsize},{prim},{acc},&H00000000,&H78000000,-1,0,0,0,100,100,0,0,3,{even(tsize * 0.22)},0,"
        f"8,{m['l']},{m['r']},{m['gora']},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    ev: list[str] = []
    for a, b, text in titles or []:
        t = ass_escape(text.upper() if style.wielkie else text)
        fade = "{\\fad(0,120)}" if a <= 0.01 else "{\\fad(120,120)}"   # od pierwszej klatki (miniatura, hook)
        ev.append(f"Dialogue: 1,{ass_time(a)},{ass_time(b)},Tytul,,0,0,0,,{fade}{t}")
    if style.styl != "brak" and words:
        disp = [Word(x.start, x.end, x.text.upper() if style.wielkie else x.text, x.podzial) for x in words]
        max_chars = 18 if portrait else 30
        groups = chunk_words(disp, 3 if style.styl == "karaoke" else 7, max_chars if style.styl == "karaoke" else max_chars * 2)
        for gi, g in enumerate(groups):
            nxt = groups[gi + 1][0].start if gi + 1 < len(groups) else g[-1].end + 0.6
            g_end = min(nxt, g[-1].end + 0.35)
            if style.styl == "karaoke":
                for wi, cur in enumerate(g):
                    a = cur.start if wi else min(cur.start, g[0].start)
                    b = g[wi + 1].start if wi + 1 < len(g) else g_end
                    if b <= a:
                        continue
                    parts = []
                    for k, x in enumerate(g):
                        t = ass_escape(x.text)
                        parts.append(f"{{\\c{acc}\\fscx108\\fscy108}}{t}{{\\c{prim}\\fscx100\\fscy100}}" if k == wi else t)
                    ev.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Napisy,,0,0,0,,{' '.join(parts)}")
            else:
                ev.append(f"Dialogue: 0,{ass_time(g[0].start)},{ass_time(g_end)},Napisy,,0,0,0,,{ass_escape(' '.join(x.text for x in g))}")
    return "\n".join(head + ev) + "\n"


def build_srt(words: list[Word], max_chars: int = 42) -> str:
    """SRT do wgrania na platformę (napisy „miękkie”) i do korekty przez człowieka."""
    groups = chunk_words(words, 12, max_chars)
    lines = []
    for i, g in enumerate(groups, 1):
        end = g[-1].end if i == len(groups) else min(groups[i][0].start, g[-1].end + 0.35)
        lines.append(f"{i}\n{srt_time(g[0].start)} --> {srt_time(end)}\n{' '.join(x.text for x in g)}\n")
    return "\n".join(lines)


def parse_srt(text: str) -> list[tuple[float, float, str]]:
    def t(s: str) -> float:
        hh, mm, rest = s.strip().replace(".", ",").split(":")
        ss, ms = rest.split(",")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000

    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        rows = [r for r in block.strip().splitlines() if r.strip()]
        if len(rows) >= 2 and "-->" in rows[1]:
            a, b = rows[1].split("-->")
            out.append((t(a), t(b), " ".join(rows[2:]).strip()))
        elif rows and "-->" in rows[0]:
            a, b = rows[0].split("-->")
            out.append((t(a), t(b), " ".join(rows[1:]).strip()))
    return out


def words_from_lines(lines: list[tuple[float, float, str]]) -> list[Word]:
    """Linie SRT → słowa z czasem rozłożonym proporcjonalnie do długości (gdy brak czasów słów)."""
    out: list[Word] = []
    for a, b, text in lines:
        toks = text.split()
        if not toks:
            continue
        total = sum(len(t) + 1 for t in toks)
        t0 = a
        for tok in toks:
            dt = (b - a) * (len(tok) + 1) / total
            out.append(Word(round(t0, 3), round(t0 + dt, 3), tok))
            t0 += dt
    return out


def transcribe_words(media: Path) -> list[Word]:
    """Słowa z czasem z nagrania: Parakeet przez jarvo-stt (SRT z jednym słowem na linię)."""
    stt = os.environ.get("JARVO_STT_BIN", "/opt/jarvo/bin/jarvo-stt")
    if not os.path.exists(stt):
        stt = shutil.which("jarvo-stt") or ""
    if not stt:
        raise SystemExit("Brak jarvo-stt (obraz Jarvo: /opt/jarvo/bin/jarvo-stt).")
    tmp = cache_dir("transkrypcje") / f"{digest('stt-v1', file_key(media))}.srt"
    if not tmp.exists():
        part = tmp.with_suffix(".part.srt")
        res = subprocess.run([stt, str(media), "--srt", str(part), "--max-chars", "1"], capture_output=True, text=True)
        if res.returncode != 0 or not part.exists():
            tail = "\n".join((res.stderr or res.stdout or "").strip().splitlines()[-6:])
            raise SystemExit(f"Transkrypcja (jarvo-stt) nie powiodła się:\n{tail}")
        part.replace(tmp)
    return [Word(a, b, w) for a, b, w in parse_srt(tmp.read_text(encoding="utf-8"))]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


# ------------------------------------------------------------------ fakty do filmu (brief Sherlocka: fakty.json)

# 3,5 · 12 480 · 12.480 · 2024 · 0.75 · 3,5 mln; spacja albo kropka co trzy cyfry = tysiące, przecinek = ułamek
_LICZBA = re.compile(r"(?<![\w,.])(\d{1,3}(?:[   ]\d{3})+|\d{1,3}(?:\.\d{3})+(?![.,]?\d)|\d+)((?:[,.]\d+)?)(?![\d])"
                     r"(?:\s*(tys\.?|tysięcy|tysiące|mln|milion\w*|mld|miliard\w*|thousand|million|billion|k|M|B)\b)?")
_MNOZNIKI = {"tys": 1e3, "tysięcy": 1e3, "tysiące": 1e3, "thousand": 1e3, "k": 1e3, "mln": 1e6, "million": 1e6, "M": 1e6,
             "mld": 1e9, "billion": 1e9, "B": 1e9}
LICZBY_STRUKTURALNE = {0.0, 1.0, 2.0, 3.0}      # „trzy kroki”, „dwa razy”: wyliczenie, nie fakt do źródła


def _mnoznik(slowo: str | None) -> float:
    s = (slowo or "").rstrip(".")
    return _MNOZNIKI.get(s) or (1e6 if s.startswith("milion") else 1e9 if s.startswith("miliard") else 1.0)


def liczby_w_tekscie(tekst: str) -> list[tuple[str, set[float]]]:
    """Liczby zapisane cyframi: [(zapis, możliwe wartości)]. „3,5 mln” → {3.5, 3 500 000}, więc fakt „3,5 mln”
    pokrywa i „3,5 mln”, i „3 500 000” na ekranie; „1,234” dostaje też 1234 (zapis angielski). Ten sam zapis
    rozumie `fakty.py` Sherlocka."""
    out = []
    for m in _LICZBA.finditer(tekst or ""):
        calosc = re.sub(r"[   .]", "", m.group(1))
        ulamek = m.group(2) or ""
        wartosci = {float(calosc + ulamek.replace(",", "."))}
        if re.fullmatch(r"[,.]\d{3}", ulamek):
            wartosci.add(float(calosc + ulamek[1:]))
        k = _mnoznik(m.group(3))
        if k != 1.0:
            wartosci |= {v * k for v in wartosci}
        out.append((m.group(0).strip(), wartosci))
    return out


POLA_BEZ_FAKTOW = {"zrodla", "id", "tier", "wiarygodnosc"}     # numery źródeł i ocena to nie liczby faktów


def _napisy_w(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for k, v in obj.items() if k not in POLA_BEZ_FAKTOW for s in _napisy_w(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _napisy_w(v)]
    return [str(obj)] if isinstance(obj, (int, float)) and not isinstance(obj, bool) else []


def liczby_faktow(fakty: dict) -> tuple[set[float], set[float]]:
    """fakty.json → (liczby ze źródłem, liczby tylko z listy niepewnych). Ze źródłem = każda liczba w faktach,
    ich przeliczeniach na odczuwalną skalę, przypadkach i datach; `niepewne` nie trafia ani do lektora, ani na ekran.
    Numery źródeł ([3]) to nie liczby faktów: pola `zrodla`, `id` i ocena wiarygodności są pomijane."""
    def zbierz(obj) -> set[float]:
        return {v for s in _napisy_w(obj) for _, vs in liczby_w_tekscie(s) for v in vs}
    pewne = zbierz({k: v for k, v in fakty.items() if k != "niepewne"})
    return pewne, zbierz(fakty.get("niepewne") or []) - pewne


def sprawdz_liczby(tekst: str, pewne: set[float], niepewne: set[float]) -> list[tuple[str, str]]:
    """Liczby z tekstu bez pokrycia w faktach: [(zapis, 'brak' | 'niepewna')]; liczby 0–3 pomijamy (wyliczenia)."""
    out = []
    for zapis, vs in liczby_w_tekscie(tekst):
        if vs & LICZBY_STRUKTURALNE or any(abs(v - p) <= 1e-9 * max(1.0, abs(p)) for v in vs for p in pewne):
            continue
        out.append((zapis, "niepewna" if vs & niepewne else "brak"))
    return out


def znajdz_fakty(*katalogi: Path) -> Path | None:
    """fakty.json obok strony albo pliku narracji, albo katalog wyżej (out/wideo/src/)."""
    for k in katalogi:
        for d in (k, k.parent):
            if (d / "fakty.json").is_file():
                return d / "fakty.json"
    return None
