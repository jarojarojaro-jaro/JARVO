#!/usr/bin/env python3
"""Media natywnie na żywo: filmy, lektor, rozpoznawanie mowy i edytor HQ (docs/NATYWNIE.md etap E9: M01–M12, V01–V11).

    python -X utf8 -B tests/live/natywnie_media.py --wyniki <katalog> [--korzen <JARVO_ROOT>] [--punkty 1,3] [--zostaw]

Sprawdza instalację z zewnątrz, tak jak pracuje flota: programy w środowisku procesów Jarva (jarvo/srodowisko.py
z `<stan>/narzedzia.json` i `<program>/current.json`, jak brama i panel), skrypty Wideografa z zainstalowanego profilu
(`<dane>/profiles/jarvo-wideo/scripts`) Pythonem floty (`<program>/bin-floty/python3`, jak @@PY@@ w skillach), lektor
i rozpoznawanie mowy przez programy floty z bin-floty, edytor przez API panelu na 127.0.0.1 (token sesji z index.html,
bez hasła). Pliki próby leżą w `<dane>/jarvo/workspaces/test-media-natywnie/` (w środku katalog „Próba Żółć”: polskie
litery i spacja) i znikają po teście (--zostaw: zostają do obejrzenia). Sama biblioteka standardowa, dowolny Python
3.11+; filmy krótkie i w szkicu (CLAUDE.md: filmy renderujemy szybko), cały test trwa kilka minut, a przy pierwszym
użyciu rozpoznawania mowy dochodzi pobranie Parakeeta (ok. 0,67 GB).

Punkty:
  1. lektor: jarvo-tts z bin-floty, trzy głosy jednym wsadem (pl-PL-Matcha-Meski, pl-PL-Matcha-Damski,
     en-US-Paradee) → trzy WAV-y niepuste, częstotliwość 22,05 kHz (Matcha) i 24 kHz (Paradee), długość pliku zgodna
     z JSON-em wsadu
  2. rozpoznawanie mowy: jarvo-stt na nagraniu lektora „Próba Żółć/nagranie_październik.wav” (--json): słowa z czasem,
     wśród nich „dzień” i „dobry”; przy pierwszym użyciu Parakeet i Silero z manifestu z sumą (raport: czy modele były
     już na dysku i ile trwało)
  3. krótki film: film.py render planu z dwiema scenami, lektorem Matcha i napisami karaoke (szkic 540×960): MP4
     z obrazem i dźwiękiem o długości z planu, SRT obok, jasne piksele napisów w pasie napisów; libass z `fontsdir`
     instalacji wybiera dla stylu „Inter” krój Inter-Bold, a nie zastępczy krój systemu
  4. animacja HTML → wideo: html_wideo.py wideo (2 s, 30 kl./s, 2 przeglądarki naraz, zegar strony przez --seek) na
     chrome-headless-shell z instalacji: 60 klatek w MP4
  5. HyperFrames z node_modules/.bin narzędzi npm floty (wpis node-floty w narzedzia.json, lock z infra/node):
     wersja 0.8.78, przeglądarka instalacji, render krótkiej kompozycji CSS (bez sieci); bez wpisu: pominięte z powodem
  6. edytor HQ przez panel: lektor (POST /edit/lektor, film.py lektor w procesie panelu), analiza mowy (/edit/speech:
     ffmpeg + jarvo-stt), eksport filmu z punktu 3 z napisem PNG (/edit/export, postęp z /edit/job) → plik obok
     oryginału; anulowanie dłuższego eksportu kończy ffmpeg i nie zostawia pliku ani pliku częściowego
  7. głos Jarva w aplikacji (hq/plugin/glos.py, POST /app/glos): polski męski i damski oraz angielski → WAV z panelu
  8. głos bramy (V11) kodem Hermesa z instalacji: głosówka „Próba Żółć/brama/głosówka_październik.wav” przez
     HERMES_LOCAL_STT_COMMAND (shlex jak tools/transcription_local.py) → transkrypcja z „dzień”; odpowiedź głosem
     przez tts.providers.matcha z config.yaml (render_command_template i run_command_provider Hermesa) → WAV
Kod 0 = żaden punkt nie padł (pominięty z powodem to nie błąd); raport JSON na stdout i w <wyniki>/raport.json.

CI (.github/workflows/natywnie.yml, po teście na żywo z natywnie_e2e.py, przed drugim przebiegiem instalacji):
    python -X utf8 -B tests/live/natywnie_media.py --wyniki "$RUNNER_TEMP/natywnie-artefakty/media"
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import wave
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from jarvo import sciezki, srodowisko  # noqa: E402

WINDOWS = os.name == "nt"
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0
KATALOG_PROBY = "test-media-natywnie"
POLSKI = "Próba Żółć"
GLOSY = {"pl-PL-Matcha-Meski": ("Dzień dobry, tu Jarvo bez Dockera.", 22050),
         "pl-PL-Matcha-Damski": ("Napisy i lektor działają po polsku.", 22050),
         "en-US-Paradee": ("Jarvo works without Docker.", 24000)}
HYPERFRAMES = "0.8.78"
TOKEN = re.compile(r'window\.__HERMES_SESSION_TOKEN__="([^"]+)"')
API = "/api/plugins/jarvo-hq"
STANY_KONCOWE = {"done", "error", "cancelled"}


class Niepowodzenie(Exception):
    pass


class Pominiete(Exception):
    """Punkt nie dotyczy tej instalacji (powód w raporcie), to nie błąd."""


def musi(warunek, opis: str) -> None:
    if not warunek:
        raise Niepowodzenie(opis)


# ----------------------------------------------------------------------------------------------- instalacja

class Proba:
    """Instalacja pod testem: układ katalogów, środowisko procesów Jarva i katalog plików próby."""

    def __init__(self, a: argparse.Namespace):
        env = dict(os.environ)
        if a.korzen:
            env["JARVO_ROOT"] = a.korzen
        self.u = sciezki.uklad(env)
        musi((self.u.program / "current.json").is_file(), f"brak instalacji Jarva w {self.u.root} (current.json)")
        self.env = srodowisko.srodowisko(self.u, baza=env)
        self.narz = srodowisko.narzedzia(self.u)
        self.kat = self.u.jarvo_dane / "workspaces" / KATALOG_PROBY
        self.skrypty = self.u.dane / "profiles" / "jarvo-wideo" / "scripts"
        self.port = int(str(env.get("JARVO_PANEL_PORT") or srodowisko.wczytaj_json(self.u.stan / "ustawienia.json")
                            .get("JARVO_PANEL_PORT") or "9119").strip())

    def program(self, nazwa: str) -> str:
        """Program floty z bin-floty (na Windows .exe), potem z PATH procesów Jarva."""
        p = self.u.bin_floty / (f"{nazwa}.exe" if WINDOWS else nazwa)
        if p.is_file():
            return str(p)
        znaleziony = shutil.which(nazwa, path=self.env.get("PATH"))
        musi(znaleziony, f"brak programu {nazwa} w bin-floty i w PATH procesów Jarva")
        return str(znaleziony)

    def uruchom(self, argv: list, *, cwd: Path | None = None, timeout: float = 600) -> subprocess.CompletedProcess:
        r = subprocess.run([str(x) for x in argv], cwd=cwd, env=self.env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, creationflags=BEZ_OKNA)
        if r.returncode != 0:
            ogon = "\n".join((r.stderr or r.stdout or "").strip().splitlines()[-8:])
            raise Niepowodzenie(f"{Path(str(argv[0])).name} {' '.join(str(x) for x in argv[1:3])}… kod {r.returncode}: {ogon}")
        return r

    def ffprobe(self, plik: Path) -> dict:
        r = self.uruchom([self.program("ffprobe"), "-v", "error", "-show_entries",
                          "stream=codec_type,width,height,nb_frames:format=duration", "-of", "json", plik], timeout=60)
        dane = json.loads(r.stdout or "{}")
        strumienie = dane.get("streams") or []
        v = next((s for s in strumienie if s.get("codec_type") == "video"), {})
        return {"sek": round(float((dane.get("format") or {}).get("duration") or 0), 3),
                "wideo": [v.get("width"), v.get("height")] if v else None,
                "klatek": int(v["nb_frames"]) if str(v.get("nb_frames") or "").isdigit() else None,
                "dzwiek": any(s.get("codec_type") == "audio" for s in strumienie)}

    def klatka_szara(self, plik: Path, t: float, w: int, h: int) -> bytes:
        """Jedna klatka filmu w skali szarości (bajty w×h), do szukania jasnych pikseli napisów."""
        r = subprocess.run([self.program("ffmpeg"), "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(plik),
                            "-frames:v", "1", "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                           env=self.env, capture_output=True, timeout=60, creationflags=BEZ_OKNA)
        musi(r.returncode == 0 and len(r.stdout) == w * h, f"ffmpeg nie dał klatki z {plik.name} w {t} s")
        return r.stdout


# ----------------------------------------------------------------------------------------------- punkty

def punkt_lektor(p: Proba) -> dict:
    kat = p.kat / "lektor"
    kat.mkdir(parents=True, exist_ok=True)
    zadania = [{"tekst": tekst, "wyjscie": str(kat / f"{glos}.wav"), "glos": glos} for glos, (tekst, _hz) in GLOSY.items()]
    plik = kat / "wsad.json"
    plik.write_text(json.dumps(zadania, ensure_ascii=False), encoding="utf-8")
    start = time.monotonic()
    wynik = json.loads(p.uruchom([p.program("jarvo-tts"), "--wsad", plik], timeout=900).stdout)
    s = round(time.monotonic() - start, 1)
    musi(len(wynik) == 3, f"wsad zwrócił {len(wynik)} wyników zamiast 3")
    glosy = {}
    for (glos, (_tekst, hz)), w in zip(GLOSY.items(), wynik):
        wav = Path(w["wyjscie"])
        musi(wav.is_file() and wav.stat().st_size > 4000, f"{glos}: brak pliku albo pusty {wav}")
        with wave.open(str(wav), "rb") as r:
            rate, sek = r.getframerate(), r.getnframes() / r.getframerate()
        musi(rate == hz, f"{glos}: {rate} Hz zamiast {hz}")
        musi(sek > 0.8 and abs(sek - float(w["sekundy"])) < 0.05, f"{glos}: {sek:.2f} s, a wsad podaje {w['sekundy']}")
        glosy[glos] = {"sek": round(sek, 2), "hz": rate, "kb": wav.stat().st_size // 1024}
    return {"glosy": glosy, "s": s}


def punkt_stt(p: Proba) -> dict:
    zrodlo = p.kat / "lektor" / "pl-PL-Matcha-Meski.wav"
    if not zrodlo.is_file():
        punkt_lektor(p)
    kat = p.kat / POLSKI
    kat.mkdir(parents=True, exist_ok=True)
    nagranie = kat / "nagranie_październik.wav"
    shutil.copy2(zrodlo, nagranie)
    modele = Path(p.env.get("JARVO_MODELS_DIR") or p.u.jarvo_dane / "models")
    byly = all((modele / k / ".jarvo-model.json").is_file() for k in ("parakeet-tdt-0.6b-v3", "silero-vad"))
    wyjscie = kat / "słowa.json"
    start = time.monotonic()
    p.uruchom([p.program("jarvo-stt"), nagranie, "--json", wyjscie], timeout=3600)
    s = round(time.monotonic() - start, 1)
    slowa = json.loads(wyjscie.read_text(encoding="utf-8")).get("words") or []
    tekst = " ".join(str(w[2]) for w in slowa).lower()
    musi(slowa and all(len(w) == 3 and float(w[1]) >= float(w[0]) for w in slowa), f"słowa bez czasu: {slowa[:3]}")
    musi("dzień" in tekst and "dobry" in tekst, f"rozpoznany tekst bez „dzień dobry”: {tekst[:120]!r}")
    musi(all((modele / k / ".jarvo-model.json").is_file() for k in ("parakeet-tdt-0.6b-v3", "silero-vad")),
         "modele nie leżą w katalogu z manifestu (parakeet-tdt-0.6b-v3, silero-vad)")
    return {"tekst": tekst[:200], "slow": len(slowa), "modele_przed": "były" if byly else "pobrane teraz", "s": s}


PLAN = {"tytul": "Próba mediów natywnie", "slug": "proba-mediow", "formaty": ["9:16"],
        "lektor": {"glos": "pl-PL-Matcha-Meski"},
        "napisy": {"styl": "karaoke", "akcent": "#FFD400", "font": "Inter", "pozycja": "dol", "wielkie": True},
        "przejscie": "ciecie",
        "sceny": [{"tekst": "Dzień dobry, tu Jarvo bez Dockera.", "ujecie": {"kolor": "#1B2A41"},
                   "tekst_ekranowy": "Zażółć gęślą jaźń"},
                  {"tekst": "Napisy mają polskie znaki.", "ujecie": {"kolor": "#202020"}}]}


def punkt_film(p: Proba) -> dict:
    kat = p.kat / "film"
    kat.mkdir(parents=True, exist_ok=True)
    (kat / "plan.json").write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")
    start = time.monotonic()
    p.uruchom([p.program("python3"), p.skrypty / "film.py", "render", "plan.json", "--szkic"], cwd=kat, timeout=900)
    s = round(time.monotonic() - start, 1)
    wynik = json.loads((kat / "out" / "wideo" / "proba-mediow" / "film-szkic.json").read_text(encoding="utf-8"))
    mp4 = kat / "out" / "wideo" / "proba-mediow" / "proba-mediow-9x16-szkic.mp4"
    info = p.ffprobe(mp4)
    musi(info["wideo"] == [540, 960] and info["dzwiek"], f"film: {info}")
    musi(abs(info["sek"] - float(wynik["sek"])) < 0.2, f"film {info['sek']} s, plan {wynik['sek']} s")
    srt = Path(wynik.get("srt") or "brak.srt")
    musi((srt if srt.is_absolute() else kat / srt).is_file(), "brak SRT obok filmu")
    # pas napisów lektora (dół kadru 9:16) w chwili pierwszych słów: jasne litery na ciemnym tle sceny
    w, h = 270, 480
    szara = p.klatka_szara(mp4, 0.6, w, h)
    pas = szara[int(h * 0.62) * w:int(h * 0.80) * w]
    jasne = sum(1 for b in pas if b > 180)
    musi(jasne > 50, f"w pasie napisów brak jasnych pikseli ({jasne})")
    kroj = sprawdz_kroj_napisow(p)
    return {"film": mp4.as_posix(), "sek": info["sek"], "jasne_piksele_napisow": jasne, "kroj_napisow": kroj,
            "czas_renderu_s": wynik.get("czas_renderu_s"), "s": s}


def sprawdz_kroj_napisow(p: Proba) -> str:
    """Napisy ASS ostatniego renderu (cache Wideografa) przez ffmpeg z `fontsdir` instalacji: libass ma wybrać Inter,
    a nie krój zastępczy systemu (na Windows DirectWrite dałby Arial)."""
    inter = p.env.get("JARVO_FONTY_INTER")
    musi(inter and Path(inter).is_dir(), "brak JARVO_FONTY_INTER w środowisku procesów Jarva (fonty-inter z manifestu)")
    cache = Path(p.env.get("JARVO_WIDEO_CACHE") or p.u.jarvo_dane / "cache" / "wideo")
    ass = max((cache / "render").glob("*/napisy-9x16.ass"), key=lambda x: x.stat().st_mtime, default=None)
    musi(ass is not None, f"brak napisów ASS renderu w {cache / 'render'}")
    sciezka = Path(inter).as_posix() if WINDOWS else inter
    fontsdir = "'" + sciezka.replace(":", "\\:") + "'"
    r = subprocess.run([p.program("ffmpeg"), "-nostdin", "-loglevel", "debug", "-f", "lavfi", "-i",
                        "color=c=black:s=540x960:d=0.5", "-vf", f"ass={ass.name}:fontsdir={fontsdir}", "-frames:v", "1",
                        "-f", "null", "-"], cwd=ass.parent, env=p.env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120, creationflags=BEZ_OKNA)
    wybory = re.findall(r"fontselect: \(Inter, (\d+), \d+\) -> ([^,\s]+)", r.stderr)
    musi(r.returncode == 0 and wybory, f"libass nie wybrał kroju dla „Inter” (kod {r.returncode})")
    musi(all(k.startswith("Inter") for _w, k in wybory), f"„Inter” → {wybory}: krój zastępczy zamiast Intera")
    return ", ".join(sorted({k for _w, k in wybory}))


ANIMACJA = """<!doctype html><html lang="pl"><head><meta charset="utf-8"><style>
html,body{margin:0;width:640px;height:360px;background:#101418;overflow:hidden;font:700 40px sans-serif;color:#fff}
#k{position:absolute;top:150px;left:0;width:60px;height:60px;background:#ffd400}
#t{position:absolute;top:40px;left:40px}</style></head>
<body><div id="t">Zażółć gęślą jaźń</div><div id="k"></div><script>
window.__t = (t) => { document.getElementById('k').style.transform = `translateX(${Math.round(t * 280)}px)`; };
window.__t(0); window.__ready = true;
</script></body></html>
"""


def punkt_html(p: Proba) -> dict:
    kat = p.kat / "html"
    kat.mkdir(parents=True, exist_ok=True)
    (kat / "anim.html").write_text(ANIMACJA, encoding="utf-8")
    start = time.monotonic()
    r = p.uruchom([p.program("python3"), p.skrypty / "html_wideo.py", "wideo", "anim.html", "--dlugosc", "2", "--fps", "30",
                   "--rozmiar", "640x360", "--rownolegle", "2", "--seek", "t => window.__t(t)", "--gotowe",
                   "window.__ready === true", "-o", "anim.mp4"], cwd=kat, timeout=600)
    s = round(time.monotonic() - start, 1)
    wynik = json.loads(r.stdout.strip().splitlines()[-1])
    musi(wynik.get("klatek") == 60 and wynik.get("przegladarki") == 2, f"html_wideo: {wynik}")
    info = p.ffprobe(kat / "anim.mp4")
    musi(info["wideo"] == [640, 360] and abs(info["sek"] - 2.0) < 0.1, f"anim.mp4: {info}")
    # ruch: żółty kwadrat jest w innym miejscu na początku i na końcu
    a, b = p.klatka_szara(kat / "anim.mp4", 0.0, 64, 36), p.klatka_szara(kat / "anim.mp4", 1.9, 64, 36)
    musi(a != b, "klatki z początku i końca są takie same (zegar strony nie działał)")
    return {"klatek": wynik["klatek"], "przegladarki": wynik["przegladarki"], "sek": info["sek"], "s": s,
            "przegladarka": p.env.get("CHROME_PATH")}


KOMPOZYCJA = """<!doctype html>
<html lang="pl"><head><meta charset="UTF-8" /><meta name="viewport" content="width=320, height=180" />
<style>
body { margin: 0; background: #101418; color: #fff; font-family: "Noto Sans", "DejaVu Sans", sans-serif; }
#root { position: relative; width: 100%; height: 100%; overflow: hidden; }
.clip { position: absolute; inset: 0; display: grid; place-items: center; }
h1 { margin: 0; font-size: 28px; animation: wejscie 600ms ease-out 1 both; }
@keyframes wejscie { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="320" data-height="180" data-duration="1"
     data-no-timeline>
  <section class="clip" data-start="0" data-duration="1"><h1>Zażółć gęślą jaźń</h1></section>
</div>
</body></html>
"""


def punkt_hyperframes(p: Proba) -> dict:
    wpis = p.narz.get("node-floty")
    if not isinstance(wpis, dict) or not wpis.get("bin"):
        raise Pominiete("brak wpisu node-floty w narzedzia.json: instalacja bez kroku „Narzędzia npm floty” "
                        "(npm ci z infra/node/package-lock.json, infra/node/node_floty.py)")
    hf = Path(wpis["bin"][0]) / ("hyperframes.cmd" if WINDOWS else "hyperframes")
    musi(hf.is_file(), f"brak {hf}")
    wersja = p.uruchom([hf, "--version"], timeout=120).stdout.strip()
    musi(wersja == HYPERFRAMES, f"hyperframes {wersja!r} zamiast {HYPERFRAMES}")
    przegladarka = p.uruchom([hf, "browser", "path"], timeout=120).stdout.strip().splitlines()[-1]
    musi(os.path.normcase(os.path.abspath(przegladarka)) == os.path.normcase(os.path.abspath(p.env["CHROME_PATH"])),
         f"HyperFrames bierze inną przeglądarkę: {przegladarka}")
    musi(p.env.get("HYPERFRAMES_NO_TELEMETRY") == "1" and p.env.get("HYPERFRAMES_NO_UPDATE_CHECK") == "1",
         "HyperFrames bez HYPERFRAMES_NO_TELEMETRY i HYPERFRAMES_NO_UPDATE_CHECK w środowisku procesów Jarva")
    kat = p.kat / "hyperframes"
    kat.mkdir(parents=True, exist_ok=True)
    (kat / "index.html").write_text(KOMPOZYCJA, encoding="utf-8")
    start = time.monotonic()
    p.uruchom([hf, "render", ".", "-o", kat / "film.mp4", "--quality", "draft", "--workers", "1", "--quiet"], cwd=kat,
              timeout=900)
    s = round(time.monotonic() - start, 1)
    info = p.ffprobe(kat / "film.mp4")
    musi(info["wideo"] == [320, 180] and abs(info["sek"] - 1.0) < 0.1, f"film HyperFrames: {info}")
    return {"wersja": wersja, "przegladarka": przegladarka, "sek": info["sek"], "s": s}


# ------------------------------------------------------------------- edytor HQ przez panel (token sesji, 127.0.0.1)

def token_sesji(base: str) -> str:
    with urllib.request.urlopen(base + "/", timeout=20) as r:        # noqa: S310 (127.0.0.1)
        html = r.read().decode("utf-8", "replace")
    m = TOKEN.search(html)
    musi(m, "index.html bez tokenu sesji: panel nie działa w trybie bez logowania (127.0.0.1)")
    return m.group(1)


def zadanie(base: str, token: str, metoda: str, sciezka: str, cialo=None, czas: float = 60) -> tuple[int, object]:
    dane = None if cialo is None else json.dumps(cialo).encode("utf-8")
    req = urllib.request.Request(base + sciezka, data=dane, method=metoda, headers={
        "X-Hermes-Session-Token": token, "X-Jarvo-Request": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=czas) as r:          # noqa: S310 (127.0.0.1)
            tresc, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        tresc, status = e.read(), e.code
    try:
        return status, json.loads(tresc or b"null")
    except ValueError:
        return status, tresc[:300].decode("utf-8", "replace")


def png_napisu(w: int, h: int) -> str:
    """PNG w×h z półprzezroczystym czerwonym pasem w środku (jak napis z przeglądarki), jako data URL."""
    def blok(rodzaj: bytes, dane: bytes) -> bytes:
        return struct.pack(">I", len(dane)) + rodzaj + dane + struct.pack(">I", zlib.crc32(rodzaj + dane) & 0xFFFFFFFF)
    wiersze = []
    for y in range(h):
        kolor = b"\xd6\x2d\x20\xc0" if h * 0.45 < y < h * 0.55 else b"\x00\x00\x00\x00"
        wiersze.append(b"\x00" + kolor * w)
    png = (b"\x89PNG\r\n\x1a\n" + blok(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + blok(b"IDAT", zlib.compress(b"".join(wiersze), 9)) + blok(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode()


def czekaj_na_zadanie(base: str, token: str, jid: str, limit: float) -> dict:
    koniec = time.monotonic() + limit
    while time.monotonic() < koniec:
        status, job = zadanie(base, token, "GET", f"{API}/edit/job/{jid}")
        musi(status == 200, f"/edit/job/{jid}: {status} {job}")
        if job.get("state") in STANY_KONCOWE:
            return job
        time.sleep(0.5)
    raise Niepowodzenie(f"zadanie {jid} nie skończyło się w {limit:.0f} s")


def punkt_edytor(p: Proba) -> dict:
    film = p.kat / "film" / "out" / "wideo" / "proba-mediow" / "proba-mediow-9x16-szkic.mp4"
    if not film.is_file():
        punkt_film(p)
    base = f"http://127.0.0.1:{p.port}"
    token = token_sesji(base)
    wynik: dict = {"panel": base}
    sciezka = film.as_posix()
    status, info = zadanie(base, token, "GET", f"{API}/edit/info?path={urllib.parse.quote(sciezka)}")
    musi(status == 200 and info.get("ffmpeg") and info.get("stt"), f"/edit/info: {status} {str(info)[:300]}")

    start = time.monotonic()                                  # lektor z edytora: film.py lektor w procesie panelu
    status, lektor = zadanie(base, token, "POST", f"{API}/edit/lektor", {
        "path": sciezka, "text": "Lektor z edytora działa bez kontenera.", "glos": "pl-PL-Matcha-Damski"}, czas=900)
    musi(status == 200 and lektor.get("kind") == "audio" and float(lektor.get("duration") or 0) > 1,
         f"/edit/lektor: {status} {str(lektor)[:300]}")
    wynik["lektor"] = {"plik": Path(lektor["path"]).name, "sek": round(float(lektor["duration"]), 2),
                       "s": round(time.monotonic() - start, 1)}

    start = time.monotonic()                                  # analiza mowy: silencedetect + jarvo-stt w panelu
    status, job = zadanie(base, token, "POST", f"{API}/edit/speech", {"src": sciezka, "force": True})
    musi(status == 200, f"/edit/speech: {status} {job}")
    job = job if job.get("state") in STANY_KONCOWE else czekaj_na_zadanie(base, token, job["id"], 900)
    slowa = (job.get("speech") or {}).get("words") or []
    musi(job.get("state") == "done" and slowa, f"analiza mowy: {job.get('state')} {job.get('error')}")
    wynik["mowa"] = {"slow": len(slowa), "s": round(time.monotonic() - start, 1)}

    projekt = {"version": 1, "canvas": {"w": 540, "h": 960, "fps": 30},
               "clips": [{"src": sciezka, "in": 0.2, "out": 3.0, "fadeOut": 0.3}],
               "texts": [{"start": 0.3, "end": 1.5, "text": "napis"}],
               "audio": [{"src": lektor["path"], "start": 0.5, "in": 0, "out": 1.5, "volume": 0.8}]}
    start = time.monotonic()
    status, job = zadanie(base, token, "POST", f"{API}/edit/export",
                          {"path": sciezka, "project": projekt, "texts": [png_napisu(540, 960)]})
    musi(status == 200 and job.get("id"), f"/edit/export: {status} {str(job)[:300]}")
    job = czekaj_na_zadanie(base, token, job["id"], 600)
    musi(job.get("state") == "done", f"eksport: {job.get('state')} {job.get('error')}")
    wyjscie = Path(job["out"])
    info = p.ffprobe(wyjscie)
    musi(wyjscie.parent == film.parent and info["wideo"] == [540, 960] and info["dzwiek"]
         and abs(info["sek"] - 2.8) < 0.15, f"eksport {wyjscie.name}: {info}")
    z_napisem, bez_napisu = (max(p.klatka_szara(wyjscie, t, 54, 96)[46 * 54:50 * 54]) for t in (1.0, 2.2))
    musi(z_napisem > bez_napisu + 15, f"w eksporcie nie widać napisu PNG ({z_napisem} wobec {bez_napisu})")
    wynik["eksport"] = {"plik": wyjscie.name, "sek": info["sek"], "s": round(time.monotonic() - start, 1)}

    # anulowanie: długi projekt (ten sam film 30 razy w 1080×1920), stop po starcie ffmpeg
    dlugi = {**projekt, "canvas": {"w": 1080, "h": 1920, "fps": 30}, "texts": [], "audio": [],
             "clips": [{"src": sciezka, "in": 0.0, "out": 3.9}] * 30}
    przed = {x.name for x in film.parent.iterdir()}
    status, job = zadanie(base, token, "POST", f"{API}/edit/export", {"path": sciezka, "project": dlugi, "texts": []})
    musi(status == 200 and job.get("id"), f"/edit/export (długi): {status} {str(job)[:300]}")
    cel = Path(job["target"])
    time.sleep(2.0)
    status, stan = zadanie(base, token, "POST", f"{API}/edit/job/{job['id']}/cancel")
    musi(status == 200 and stan.get("state") == "cancelled", f"anulowanie: {status} {stan}")
    for _ in range(40):
        po = {x.name for x in film.parent.iterdir()} - przed
        if not po:
            break
        time.sleep(0.25)
    musi(not cel.exists() and not po, f"po anulowaniu zostały pliki: {sorted(po)}")
    wynik["anulowanie"] = {"cel": cel.name, "pliki_po": sorted(po)}
    return wynik


def punkt_glos_aplikacji(p: Proba) -> dict:
    """Głos Jarva w aplikacji (hq/plugin/glos.py, pierwsze spotkanie): POST /app/glos → WAV z lokalnego lektora."""
    base = f"http://127.0.0.1:{p.port}"
    token = token_sesji(base)
    wynik = {}
    for glos, jezyk, tekst in (("meski", "pl", "Cześć, tu Jarvo, bez kontenera."), ("damski", "pl", "Mówię z panelu."),
                               ("meski", "en", "Hello from the panel.")):
        dane = json.dumps({"tekst": tekst, "glos": glos, "tempo": "normalnie", "jezyk": jezyk}).encode("utf-8")
        req = urllib.request.Request(base + f"{API}/app/glos", data=dane, method="POST", headers={
            "X-Hermes-Session-Token": token, "X-Jarvo-Request": "1", "Content-Type": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:        # noqa: S310 (127.0.0.1)
                tresc, status, typ = r.read(), r.status, r.headers.get("Content-Type") or ""
        except urllib.error.HTTPError as e:
            tresc, status, typ = e.read(), e.code, ""
        musi(status == 200 and typ.startswith("audio/wav") and tresc[:4] == b"RIFF" and len(tresc) > 8000,
             f"/app/glos {glos}/{jezyk}: {status} {typ} {len(tresc)} B {tresc[:120]!r}")
        wynik[f"{glos}-{jezyk}"] = {"kb": len(tresc) // 1024, "s": round(time.monotonic() - start, 1)}
    return wynik


# STT i TTS bramy kodem Hermesa z instalacji (V11): głosówka z Telegrama idzie przez HERMES_LOCAL_STT_COMMAND
# (shlex, jak tools/transcription_local.py), odpowiedź głosem przez tts.providers.matcha (render_command_template
# i run_command_provider z tools/tts_command_provider.py; na Windows przez cmd.exe)
GLOS_BRAMY = r"""
import json, os, sys, time
from pathlib import Path
import yaml
from tools.transcription_local import _transcribe_local_command
from tools.tts_command_provider import render_command_template, run_command_provider
wav, kat = Path(sys.argv[1]), Path(sys.argv[2])
t0 = time.monotonic()
stt = _transcribe_local_command(str(wav), "base")
t1 = time.monotonic()
cfg = yaml.safe_load(Path(os.environ["HERMES_HOME"], "config.yaml").read_text(encoding="utf-8"))
szablon = cfg["tts"]["providers"]["matcha"]["command"]
tekst, wyjscie = kat / "tekst wejściowy.txt", kat / "odpowiedź głosem.wav"
tekst.write_text("Dzień dobry, odpowiadam głosem.", encoding="utf-8")
polecenie = render_command_template(szablon, {"input_path": str(tekst), "text_path": str(tekst), "output_path": str(wyjscie),
                                              "voice": "pl-PL-Matcha-Damski", "format": "wav", "model": "", "speed": "1.0"})
r = run_command_provider(polecenie, timeout=300)
print(json.dumps({"stt": stt, "stt_s": round(t1 - t0, 1), "tts_kod": r.returncode, "tts_s": round(time.monotonic() - t1, 1),
                  "tts_bajty": wyjscie.stat().st_size if wyjscie.is_file() else 0}, ensure_ascii=False))
"""


def punkt_glos_bramy(p: Proba) -> dict:
    biez = srodowisko.biezace(p.u)
    musi(biez.get("hermes"), "current.json bez checkoutu Hermesa")
    checkout = Path(biez["hermes"])
    musi(p.env.get("HERMES_LOCAL_STT_COMMAND"), "brak HERMES_LOCAL_STT_COMMAND w środowisku bramy (build floty)")
    zrodlo = p.kat / "lektor" / "pl-PL-Matcha-Meski.wav"
    if not zrodlo.is_file():
        punkt_lektor(p)
    kat = p.kat / POLSKI / "brama"
    kat.mkdir(parents=True, exist_ok=True)
    glosowka = kat / "głosówka_październik.wav"
    shutil.copy2(zrodlo, glosowka)
    r = p.uruchom([srodowisko.hermes_python(checkout), "-c", GLOS_BRAMY, glosowka, kat], cwd=checkout, timeout=900)
    wynik = json.loads(r.stdout.strip().splitlines()[-1])
    stt = wynik["stt"]
    musi(stt.get("success") and "dzień" in str(stt.get("transcript", "")).lower(),
         f"STT bramy: {str(stt)[:300]}")
    musi(wynik["tts_kod"] == 0 and wynik["tts_bajty"] > 8000, f"TTS bramy: kod {wynik['tts_kod']}, {wynik['tts_bajty']} B")
    return {"transkrypcja": stt["transcript"][:120], "stt_s": wynik["stt_s"], "tts_kb": wynik["tts_bajty"] // 1024,
            "tts_s": wynik["tts_s"]}


PUNKTY = [("1", "lektor jarvo-tts: trzy głosy (Matcha męski i damski, Paradee) jednym wsadem", punkt_lektor),
          ("2", "jarvo-stt na nagraniu z polską nazwą (modele z manifestu z sumą)", punkt_stt),
          ("3", "krótki film: render z lektorem i napisami ASS z krojem Inter z instalacji", punkt_film),
          ("4", "animacja HTML → wideo w 2 przeglądarkach naraz (chrome-headless-shell z instalacji)", punkt_html),
          ("5", f"HyperFrames {HYPERFRAMES} z node_modules/.bin narzędzi npm floty", punkt_hyperframes),
          ("6", "edytor HQ przez panel: lektor, analiza mowy, eksport i anulowanie eksportu", punkt_edytor),
          ("7", "głos Jarva w aplikacji (POST /app/glos): polski męski i damski, angielski", punkt_glos_aplikacji),
          ("8", "głos bramy kodem Hermesa: głosówka przez HERMES_LOCAL_STT_COMMAND, odpowiedź przez tts.providers.matcha",
           punkt_glos_bramy)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wyniki", required=True, help="katalog raportu i śladów błędów (CI: artefakty)")
    ap.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT)")
    ap.add_argument("--punkty", default="", help="np. 1,3: tylko te punkty")
    ap.add_argument("--zostaw", action="store_true", help="pliki próby zostają do obejrzenia")
    a = ap.parse_args(argv)
    wyniki = Path(a.wyniki).resolve()
    wyniki.mkdir(parents=True, exist_ok=True)
    wybrane = {x.strip() for x in a.punkty.split(",") if x.strip()}
    raport: dict = {"punkty": []}
    p = None
    try:
        p = Proba(a)
        raport.update(korzen=str(p.u.root), system=sys.platform)
        wersja = subprocess.run([p.program("ffmpeg"), "-version"], env=p.env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", creationflags=BEZ_OKNA).stdout.splitlines()
        raport["ffmpeg"] = (wersja or ["?"])[0][:80]
        p.kat.mkdir(parents=True, exist_ok=True)
        for nr, opis, f in PUNKTY:
            if wybrane and nr not in wybrane:
                continue
            start = time.monotonic()
            wpis = {"punkt": nr, "opis": opis}
            try:
                wpis.update(ok=True, wynik=f(p))
            except Pominiete as e:
                wpis.update(ok=True, pominiety=str(e))
            except Exception as e:            # noqa: BLE001 - każdy punkt w raporcie, test idzie dalej
                wpis.update(ok=False, blad=f"{type(e).__name__}: {e}"[:800])
                if not isinstance(e, Niepowodzenie):
                    (wyniki / f"punkt-{nr}-slad.txt").write_text(traceback.format_exc(), encoding="utf-8")
            wpis["s"] = round(time.monotonic() - start, 1)
            raport["punkty"].append(wpis)
            print(f"[{'ok' if wpis['ok'] else 'BŁĄD'}] {nr}. {opis} ({wpis['s']} s)"
                  + (f": {wpis.get('blad') or wpis.get('pominiety')}" if not wpis["ok"] or "pominiety" in wpis else ""),
                  file=sys.stderr, flush=True)
    except Exception as e:                    # noqa: BLE001 - raport zamiast śladu na ekranie
        raport["blad"] = f"{type(e).__name__}: {e}"[:800]
    finally:
        if p is not None and not a.zostaw:
            shutil.rmtree(p.kat, ignore_errors=True)
    raport["ok"] = bool(raport["punkty"]) and all(x["ok"] for x in raport["punkty"]) and "blad" not in raport
    tekst = json.dumps(raport, ensure_ascii=False, indent=1)
    (wyniki / "raport.json").write_text(tekst + "\n", encoding="utf-8")
    print(tekst)
    return 0 if raport["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
