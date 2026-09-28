"""Wspólne klocki skryptów Wideografa: formaty, FFmpeg/ffprobe, lektor (Edge TTS), napisy ASS/SRT, cache.

Bez zależności poza biblioteką standardową, FFmpeg i (tylko dla lektora) edge-tts. Edge TTS jest darmowy
i nie wymaga klucza; pakiet leży w katalogu leniwych instalacji Hermesa (HERMES_LAZY_INSTALL_TARGET),
a gdy go brak, doinstalowujemy go tym samym mechanizmem, którego używa narzędzie `text_to_speech`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ------------------------------------------------------------------ formaty

FORMATS = {  # proporcje → rozdzielczość finalna (szkic: połowa)
    "9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350),
}
FPS = 30
# zakres „TV” (limited) + yuv420p: JPEG i część telefonów dają pełny zakres (yuvj420p), którego platformy nie lubią
TV_RANGE = "scale=out_range=tv,format=yuv420p"
# RAM na VPS 8 GB: x264 domyślnie bierze wątki i bufory lookahead ze wszystkich rdzeni (~0,65 GB samego kodera
# przy 1080×1920, a z filtrami ~0,9 GB). 2 wątki + lookahead 10 ≈ 0,3 GB kodera; jakość przy CRF 19–20 bez różnicy.
# Więcej rdzeni i RAM-u: TARS_WIDEO_WATKI=4.
THREADS = os.environ.get("TARS_WIDEO_WATKI", "2")
ENC_LIMITS = ["-threads", THREADS, "-filter_threads", "2", "-x264-params", "rc-lookahead=10"]
PARALLEL = max(1, int(os.environ.get("TARS_WIDEO_ROWNOLEGLE", "1")))   # sceny normalizowane naraz
DEFAULT_VOICE = "pl-PL-MarekNeural"
PL_VOICES = {"pl-PL-MarekNeural": "męski, spokojny", "pl-PL-ZofiaNeural": "żeński, ciepły"}


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
    base = os.environ.get("TARS_WIDEO_CACHE")
    if not base:
        base = "/opt/data/tars/cache/wideo" if Path("/opt/data/tars").is_dir() else str(Path.home() / ".cache" / "tars-wideo")
    p = Path(base, *parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


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


def probe(path: Path) -> dict:
    res = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=index,codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels:format=duration,size,format_name",
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
    return {
        "duration": float(fmt.get("duration") or 0), "size": int(fmt.get("size") or 0),
        "format_name": fmt.get("format_name", ""),
        "video": v and {"codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"),
                        "fps": round(fps, 3), "pix_fmt": v.get("pix_fmt")},
        "audio": a and {"codec": a.get("codec_name"), "sample_rate": int(a.get("sample_rate") or 0),
                        "channels": a.get("channels")},
    }


def duration(path: Path) -> float:
    return probe(path)["duration"]


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


def speak_many(items: list[dict], concurrency: int = 4) -> list[Speech]:
    """Lektor dla wielu tekstów naraz; wynik w cache (ten sam tekst i głos = zero zapytań)."""
    out: list[Speech | None] = [None] * len(items)
    todo = []
    for i, it in enumerate(items):
        key = digest("tts-v1", it["text"], it.get("voice", DEFAULT_VOICE), it.get("rate", "+0%"),
                     it.get("volume", "+0%"), it.get("pitch", "+0Hz"))
        mp3 = cache_dir("lektor") / f"{key}.mp3"
        meta = mp3.with_suffix(".json")
        if mp3.exists() and meta.exists() and mp3.stat().st_size > 0:
            m = json.loads(meta.read_text(encoding="utf-8"))
            out[i] = Speech(mp3, m["duration"], [Word(**w) for w in m["words"]])
        else:
            todo.append((i, it, mp3, meta))
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
        out.append(Word(w.start, w.end, disp or w.text))
    return out


# polska typografia: krótkie słowo nie zostaje na końcu grupy („sierotka”), przechodzi do następnej
ORPHANS = {"a", "i", "o", "u", "w", "z", "do", "na", "od", "po", "za", "ze", "we", "że", "to", "czy", "ale", "bo",
           "jak", "nie", "się", "dla", "pod", "nad", "przy", "bez", "oraz", "lub"}


def chunk_words(words: list[Word], max_words: int, max_chars: int) -> list[list[Word]]:
    """Grupy słów na ekran: limit słów i znaków, przerwa po końcu zdania albo przy pauzie > 0,45 s."""
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur:
            text_len = len(" ".join(x.text for x in cur + [w]))
            pause = w.start - cur[-1].end
            sentence_end = re.search(r"[.!?…]$", cur[-1].text)
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
        if (prev and len(g) == 1 and not re.search(r"[.!?…]$", prev[-1].text) and g[0].start - prev[-1].end <= 0.45
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


def safe_margins(w: int, h: int) -> dict:
    """Marginesy napisów poza strefami interfejsu platform (9:16: dół ~25% i prawy pasek przycisków)."""
    if h > w:   # prawy margines szerszy: pasek przycisków (serce, komentarze, udostępnij)
        return {"dol": even(h * 0.24), "srodek": 0, "gora": even(h * 0.14), "l": even(w * 0.08), "r": even(w * 0.16)}
    return {"dol": even(h * 0.08), "srodek": 0, "gora": even(h * 0.08), "l": even(w * 0.06), "r": even(w * 0.06)}


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
        disp = [Word(x.start, x.end, x.text.upper() if style.wielkie else x.text) for x in words]
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
    """Słowa z czasem z nagrania: Parakeet przez tars-stt (SRT z jednym słowem na linię)."""
    stt = os.environ.get("TARS_STT_BIN", "/opt/tars/bin/tars-stt")
    if not os.path.exists(stt):
        stt = shutil.which("tars-stt") or ""
    if not stt:
        raise SystemExit("Brak tars-stt (obraz TARS: /opt/tars/bin/tars-stt).")
    tmp = cache_dir("transkrypcje") / f"{digest('stt-v1', file_key(media))}.srt"
    if not tmp.exists():
        part = tmp.with_suffix(".part.srt")
        res = subprocess.run([stt, str(media), "--srt", str(part), "--max-chars", "1"], capture_output=True, text=True)
        if res.returncode != 0 or not part.exists():
            tail = "\n".join((res.stderr or res.stdout or "").strip().splitlines()[-6:])
            raise SystemExit(f"Transkrypcja (tars-stt) nie powiodła się:\n{tail}")
        part.replace(tmp)
    return [Word(a, b, w) for a, b, w in parse_srt(tmp.read_text(encoding="utf-8"))]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
