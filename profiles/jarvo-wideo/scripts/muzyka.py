#!/usr/bin/env python3
"""Muzyka pod obraz pisana kodem: gatunek z karty stylu, kulminacja i koniec z osi filmu, efekty w tych samych chwilach.

    muzyka.py przepisy                          # 15 gatunków: do jakiego stylu i filmu, tempo, tonacja, opcje
    muzyka.py efekty                            # efekty w cues.json: nazwy jak w sound.mjs i własne mgaudio („mg”)
    muzyka.py zrob [obraz.mp4] -o final.mp4|muzyka.wav [--cues cues.json] [--styl kreska | --przepis lofi]
                   [--dlugosc S] [--kulminacja T] [--koniec T] [--tempo 100] [--tonacja A --tryb minor]
                   [--opcje '{"keys": "rhodes"}'] [--bez-efektow] [--lufs -14] [--json plan.json]
                   [--lektor lektor.wav [--lektor-od 0]]
    muzyka.py sprawdz muzyka.wav [--lufs -14]   # głośność, szczyt prawdziwy, pasma, faza, najdłuższa cisza

Silnik: mgaudio z mg-styles-15 (MIT, Vincentwei1021): syntezatory, perkusja, sample VCSL (CC0), mastering
do −14 LUFS i szczytu prawdziwego ≤ −1 dBTP, wszystko z ziarna (ten sam plan = ten sam dźwięk). Przepis układa
formę: wstęp → narastanie → kulminacja (takt 0 zaczyna się dokładnie w chwili `--kulminacja`) → koniec (od
`--koniec` gra końcowy akord do ostatniej klatki). Bez `--kulminacja` i `--koniec` liczy je z cues.json:
kulminacja = najgłośniejsze uderzenie albo koniec narastania w 20–80% filmu (remis: bliżej 62%), koniec =
ostatni błysk (chime, sparkle) od 60% filmu. Bez `--tempo` przepis wybiera tempo ze swojego zakresu, przy którym
siatka ósemek najlepiej trafia w zdarzenia z cues.json.
Efekty: wpisy cues.json jak dla sound.mjs (`{"sfx": "pop", "t": 0.94, "vol": 0.5, "dur", "pan", "pitch"}`, t =
początek dźwięku) dostają odpowiednik z mgaudio w tej samej chwili; `{"mg": "impact", "t": 6.2, "opcje": {"kind":
"cinematic"}}` to dowolny efekt mgaudio, a t to jego chwila synchronizacji (atak uderzenia, przelot whoosha,
koniec narastania). Efekty mgaudio mają poziom z konstrukcji (ok. 2 dB nad muzyką, `vol` 0,5 = 0 dB, 0,25 = −6 dB),
a muzyka przysiada o 3 dB wokół każdego.
Z lektorem (`--lektor`, np. z `film.py narracja`): głos w miksie ok. 10 dB nad muzyką, a muzyka przysiada o 8 dB,
gdy lektor mówi (razem ok. −18 dB pod głosem; schodzi 0,12 s przed pierwszym słowem, wraca przez 0,4 s po ostatnim).
Przerwy krótsze niż 0,5 s (oddech w akapicie) jej nie podnoszą, pauza między akapitami (1 s) już tak. Efekty pod
mową ciszej o 4 dB, a ich słyszalność liczona jest względem głosu i muzyki. Mastering bez podbicia góry i saturacji
(głos zostaje naturalny); długość filmu bez obrazu i `--dlugosc` = koniec lektora.
Z obrazem: dźwięk zastępuje ścieżkę filmu (AAC 192k, obraz bez przekodowania); obok zostają <wynik>.muzyka.wav
(do edytora HQ: `projekt.py dodaj-audio`, do planu film.py: `"muzyka": {"plik": …}`) i <wynik>.muzyka.json
(plan: tempo, takty, sekcje, akordy, efekty, kontrola). Bez obrazu: WAV i plan obok.
Ścieżki do edytora: obok WAV katalog <wav bez .wav>.sciezki/ z warstwami miksu osobno (muzyka.wav, efekty.wav,
glos.wav; float, od 0 s do końca filmu, ta sama skala co master), lista w planie pod "sciezki". Film z kodu oddajesz
jako projekt: `projekt.py z-kodu <film> --obraz <obraz> --z-muzyki <plan.muzyka.json>`.
Instalacja raz: python3 $HERMES_HOME/scripts/narzedzia.py instaluj mgaudio (pakiety ok. 390 MB, sample 56 MB).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import narzedzia as nz  # noqa: E402
import projekt as pj  # noqa: E402

KLATKA = 1 / 30
# przepis mgaudio → (opis, tempo domyślne i zakres, tonacja, do czego); liczby z README mgaudio
PRZEPISY = {
    "synthwave": ("neon lat 80.: bramkowany werbel, pad, bas w ósemkach, arpeggio (opcja lead)",
                  "100 (84–118)", "a-moll", "synthwave, retro, gaming, nocne wydarzenie"),
    "darksynth": ("ciemny syntezator, cyber", "110 (96–124)", "d frygijska", "HUD, technologia, cyberbezpieczeństwo"),
    "vaporwave": ("zwolniony, rozmyty pop z taśmy (opcje slow, tape_stop)", "72 (60–90)", "F-dur",
                  "nostalgia, retro internet"),
    "chiptune": ("8-bit: fale prostokątne, trójkąt, szum", "150 (120–170)", "C-dur", "pixel art, gry, „level up”"),
    "techno": ("minimalne techno z kliknięć, akordy dub", "124 (118–132)", "a-moll",
               "Bauhaus, geometria, architektura, design"),
    "acid": ("bas TB-303 (opcja pattern)", "130 (124–140)", "a-moll", "klub, grafika kwasowa"),
    "pop": ("EDM-pop, supersaw na kulminacji", "122 (110–130)", "C-dur", "płaski wektor, produkt 3D, promo"),
    "future_bass": ("miękkie supersaw, przerwa przed kulminacją (opcja gap)", "150 (130–165)", "D-dur",
                    "płyn, morph, kosmetyki"),
    "trap": ("808 i hi-hat; uderzenia 808 na zdarzeniach (opcja accent_hits)", "140 (130–160)", "e-moll",
             "szybkie napisy, social, ogłoszenie"),
    "glitch_hop": ("zacięcia, bitcrush, stop taśmy", "105 (95–115)", "e-moll", "glitch, technologia, gaming"),
    "lofi": ("pianino albo rhodes, trzaski płyty (opcje keys, flavor chill/boombap, vinyl)", "84 (70–96)", "F-dur",
             "kreska, kolaż, ziarno, kawiarnia, rzemiosło"),
    "ambient": ("spokojne pady (opcja flavor glass/product/piano)", "78/100/72", "E-dur",
                "zorza i szkło, rysunek linią, produkt premium"),
    "guofeng": ("pentatonika chińska: cytra, flet dizi (opcje flavor, dizi)", "92/84 (76–110)", "D gong",
                "tylko gdy temat filmu tego chce"),
    "variety": ("skoczne: pizzicato, ukulele (opcja flavor bouncy/cute)", "128/112", "F-dur",
                "napisy show, humor, naklejki"),
    "explainer": ("marimba i czyste bębny", "112 (100–124)", "D-dur", "explainer, izometria, „jak to działa”"),
}
# styl ze skilla style-motion → (wzór mg-styles-15, przepis, alternatywa) jak recipes.STYLES; opcje przepisu
# bierze z recipes.STYLES wzoru. Karta stylu opisuje ścieżkę samego wzoru: kreska (05) i izometria (03) mają
# własne kompozycje, więc alternatywa bywa bliżej karty (kreska: jazz z kreskówki → variety).
STYLE = {
    "kreska": ("05-cel-boil", "lofi", "variety"), "rysunek-linia": ("02-line-art", "ambient", "explainer"),
    "plaski-wektor": ("01-flat-vector", "pop", "future_bass"), "izometria": ("03-isometric", "explainer", "pop"),
    "3d": ("04-3d-render", "pop", "ambient"), "morph": ("08-morph", "future_bass", "techno"),
    "naklejki": ("19-paperclip", "explainer", "pop"), "kolaz": ("06-collage", "lofi", "vaporwave"),
    "hud": ("22-hud", "darksynth", "techno"), "zorza-szklo": ("12-aurora-glass", "ambient", "future_bass"),
    "plyn": ("07-liquid", "future_bass", "lofi"), "bauhaus": ("09-bauhaus", "techno", "explainer"),
    "synthwave": ("10-synthwave", "synthwave", "darksynth"), "pixel": ("20-pixel", "chiptune", None),
    "napisy-show": ("18-hanazi", "variety", "pop"),
}
# efekty sound.mjs → odpowiednik mgaudio: (funkcja, opcje, domyślna długość, chwila synchronizacji od początku
# dźwięku jako ułamek długości: whoosh przelatuje w połowie, narastanie kończy się uderzeniem, reszta od razu)
SOUND_MJS = {
    "pop": ("pop", {"kind": "bubble"}, 0.14, 0.0), "tick": ("tick", {"kind": "hi"}, 0.03, 0.0),
    "thump": ("impact", {"kind": "thud"}, 0.28, 0.0), "crack": ("impact", {"kind": "punch"}, 0.18, 0.0),
    "whoosh": ("whoosh", {"kind": "swoosh"}, 0.5, 0.5), "whip": ("swish", {}, 0.3, 0.0),
    "riser": ("riser", {"kind": "hybrid"}, 1.2, 1.0), "scratch": ("record_scratch", {"kind": "stop"}, 0.25, 0.0),
    "sparkle": ("sparkle", {}, 0.9, 0.0), "drip": ("drip", {}, 0.2, 0.0), "boing": ("boing", {}, 0.5, 0.0),
    "splash": ("splash", {}, 0.45, 0.0), "click": ("click", {"kind": "soft"}, 0.05, 0.0),
    "step": ("tick", {"kind": "wood"}, 0.04, 0.0), "fall": ("slide_whistle", {"up": False}, 0.45, 0.0),
    "chime": ("chime", {}, 1.2, 0.0), "chirp": ("blip", {"kind": "fm"}, 0.18, 0.0),
    "burner": ("whoosh", {"kind": "fire"}, 1.0, 0.5), "buzz": ("ui", {"kind": "error"}, 0.6, 0.0),
}
Z_DLUGOSCIA = {"whoosh": "dur", "swish": "dur", "riser": "dur", "sparkle": "dur", "slide_whistle": "dur"}
Z_WYSOKOSCIA = {"pop", "drip", "boing"}          # funkcje z parametrem pitch (mnożnik), inne: przestrojenie
# role efektów (jak w bibliotece CC0 i `projekt.py slychac`): sound.mjs z projekt.CUE_ROLA, własne mgaudio tutaj
ROLA = {**pj.CUE_ROLA,
        "impact": "uderzenie", "boom": "uderzenie", "sub_drop": "uderzenie", "text_hit": "uderzenie",
        "transition": "uderzenie", "stamp": "uderzenie", "reverse_cymbal": "narastanie", "swell": "narastanie",
        "charge": "narastanie", "lock_on": "narastanie", "shimmer_hit": "blysk", "magic": "blysk", "ding": "blysk",
        "swish": "ruch", "glitch": "przejscie", "shutter": "klik", "blip": "pojawienie", "bubble": "pojawienie",
        "sticker_slap": "pojawienie", "coin": "pojawienie", "hud_beep": "klik", "hud_ping": "klik", "ui": "klik"}
# rodziny efektów mgaudio (README mgaudio, rozdz. 3): dla `efekty`, bez ładowania biblioteki
MG_RODZINY = {
    "ruch": "whoosh(dur, kind=swoosh|air|swish|heavy|sci|cloth|fire|soft, direction) · swish · transition(dur, "
            "kind=whoosh_hit|riser_hit|reverse_hit|swish_pop)",
    "napięcie i uderzenia": "riser(dur, kind=hybrid|noise|tonal|shepard|sweep) · downlifter · impact(kind=cinematic|"
                            "punch|soft|metal|glitch|thud|trailer, size) · boom · sub_drop · reverse_cymbal · charge",
    "interfejs": "pop(kind=mouth|bubble|soft|cork, pitch) · blip · click(kind=soft|hard|mouse|switch|wood) · "
                 "tick(kind=clock|hi|wood|tock) · toggle · ding · ui(kind=confirm|error|notify|hover|swipe|open|close)",
    "ciecz": "bubble · bubbles · drip · gloop · splash · squelch · morph · stretch",
    "papier i biurko": "paper(kind=rustle|flip|crumple|slide) · tape_rip · sticker_slap · sticker_peel · "
                       "stamp(kind=seal|rubber|wood) · pen · shutter(kind=dslr|film|phone) · typewriter · typing · scissors",
    "glitch": "glitch(dur, kind=digital|data|error|crunch|stutter) · bitcrush_burst · digital_noise · data_chirp",
    "retro media": "vhs_noise · head_switch · vinyl · static · crt_on · crt_off · crt_whine · power_down",
    "sci-fi i HUD": "laser(kind=pew|zap|beam) · hud_beep · hud_scan · lock_on · hud_data · hud_open · hud_alert · hud_ping",
    "magia": "sparkle · shimmer_hit · magic · chime",
    "8-bit": "coin · jump · powerup · oneup · explosion_8bit",
    "kreskówka": "boing · sproing · duang · slide_whistle · squeak · zip_ · cork_pop · rimshot_joke · heartbeat",
    "napisy": "text_hit(kind=slam|flash|pop|glitch)",
    "perkusja": "drums.gong · drums.taiko · drums.woodblock · drums.crash · drums.tom (prefiks drums.)",
}
UWAGI_PL = [
    (r"duration ([\d.]+)s != ([\d.]+)s", "długość {0} s zamiast {1} s"),
    (r"NaN/Inf samples", "w dźwięku są wartości NaN/Inf"),
    (r"true peak (\S+) dBTP > -1", "szczyt prawdziwy {0} dBTP, powyżej −1 (przester na telefonie)"),
    (r"DC offset (.+)", "przesunięcie DC {0}"),
    (r"(\d+) clipped samples", "{0} próbek przesterowanych"),
    (r"too much sub \(<60 Hz = (\S+)% of energy\)", "za dużo subbasu: {0}% energii poniżej 60 Hz"),
    (r"harsh 2-5 kHz \((\S+)% of energy\)", "ostro w 2–5 kHz: {0}% energii"),
    (r"dull \(almost nothing above 5 kHz\)", "głucho: prawie nic powyżej 5 kHz"),
    (r"thin low end \(<250 Hz\)", "chudy dół: mało energii poniżej 250 Hz"),
    (r"phase problem \(L/R correlation (\S+)\)", "faza: korelacja L/P {0}, w mono część dźwięku zniknie"),
    (r"silence gap (\S+)s", "cisza {0} s w środku (zamierzona przerwa? jeśli nie: przepis bez gap/tape_stop)"),
]


def uwaga_pl(w: str) -> str:
    for wzor, tekst in UWAGI_PL:
        m = re.fullmatch(wzor, w)
        if m:
            return tekst.format(*m.groups())
    return w


def wczytaj_cues(path: Path | None) -> list[dict]:
    """cues.json: lista wpisów albo obiekt z listą pod `cues` / `dzwiek`. Wpis bez `sfx` i `mg` to pop (jak sound.mjs)."""
    if path is None:
        return []
    dane = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(dane, dict):
        dane = dane.get("cues") or dane.get("dzwiek") or []
    if not isinstance(dane, list):
        raise SystemExit(f"{path}: oczekuję listy wpisów [{{\"sfx\": \"pop\", \"t\": 0.94}}, …]")
    out = []
    for i, c in enumerate(dane):
        if not isinstance(c, dict) or not isinstance(c.get("t"), (int, float)):
            raise SystemExit(f"{path}: wpis {i} bez liczby `t`")
        out.append(c)
    return out


def glosnosc_db(vol) -> float:
    """`vol` jak w sound.mjs (0,5 domyślnie) → dB względem poziomu efektu mgaudio, od −12 do +4."""
    v = 0.5 if vol is None else float(vol)
    if v <= 0:
        return -12.0
    return round(max(-12.0, min(4.0, 20 * math.log10(v / 0.5))), 2)


def zdarzenie(c: dict) -> dict:
    """Wpis cues.json → {nazwa, funkcja, opcje, dlugosc, chwila, rola, db, pan, pitch, zrodlo}. Chwila = moment,
    w który ma trafić synchronizacja efektu mgaudio (atak, przelot, koniec narastania)."""
    t = float(c["t"])
    if c.get("mg"):
        nazwa = str(c["mg"])
        funkcja = nazwa.split(".")[-1]
        return {"nazwa": nazwa, "funkcja": nazwa, "opcje": dict(c.get("opcje") or {}), "dlugosc": None, "chwila": t,
                "rola": ROLA.get(funkcja, "inne"), "db": glosnosc_db(c.get("vol")), "pan": c.get("pan"),
                "pitch": c.get("pitch"), "zrodlo": "mg"}
    nazwa = str(c.get("sfx") or "pop")
    funkcja, opcje, dl, sync = SOUND_MJS.get(nazwa, SOUND_MJS["pop"])
    dl = float(c.get("dur") or dl)
    return {"nazwa": nazwa if nazwa in SOUND_MJS else "pop", "funkcja": funkcja, "opcje": dict(opcje), "dlugosc": dl,
            "chwila": round(t + sync * dl, 4), "rola": ROLA.get(nazwa, "pojawienie"), "db": glosnosc_db(c.get("vol")),
            "pan": c.get("pan"), "pitch": c.get("pitch"), "zrodlo": "sound.mjs"}


def kulminacja_z_cues(zd: list[dict], dlugosc: float) -> dict | None:
    """Najgłośniejsze uderzenie albo koniec narastania w 20–80% filmu; remis: bliżej 62% (kulminacja w 60–65%)."""
    kand = [z for z in zd if z["rola"] in ("uderzenie", "narastanie") and 0.2 * dlugosc <= z["chwila"] <= 0.8 * dlugosc]
    if not kand:
        return None
    return max(kand, key=lambda z: (z["db"], -abs(z["chwila"] - 0.62 * dlugosc)))


def koniec_z_cues(zd: list[dict], dlugosc: float, kulminacja: float | None) -> dict | None:
    """Ostatni błysk (chime, sparkle, shimmer) od 60% filmu i po kulminacji: logo i hasło."""
    kand = [z for z in zd if z["rola"] == "blysk" and z["chwila"] >= 0.6 * dlugosc
            and (kulminacja is None or z["chwila"] > kulminacja + 0.5) and z["chwila"] < dlugosc - 0.3]
    return max(kand, key=lambda z: z["chwila"]) if kand else None


def chwile_do_tempa(zd: list[dict]) -> list[float]:
    """Chwile zdarzeń do dopasowania tempa: bez duplikatów w obrębie klatki."""
    out: list[float] = []
    for t in sorted(z["chwila"] for z in zd):
        if not out or t - out[-1] > KLATKA:
            out.append(round(t, 4))
    return out


def tlok(zd: list[dict]) -> list[str]:
    """Ponad 3 efekty w jednej klatce to już hałas (README mgaudio: najwyżej ok. 3 na klatkę)."""
    uw, ch = [], sorted(z["chwila"] for z in zd)
    i = 0
    for j, t in enumerate(ch):
        while t - ch[i] > KLATKA:
            i += 1
        if j - i + 1 == 4:
            uw.append(f"{ch[i]:.2f} s: 4 efekty w jednej klatce (najwyżej 3)")
    return uw


def wybierz_przepis(a) -> tuple[str, dict, str | None]:
    """(przepis, opcje, wzór mg) z --styl albo --przepis; --opcje dopisuje swoje."""
    opcje = json.loads(a.opcje) if a.opcje else {}
    if a.styl:
        if a.styl not in STYLE:
            raise SystemExit(f"nieznany styl {a.styl!r}: {', '.join(STYLE)}")
        wzor, przepis, _alt = STYLE[a.styl]
        return przepis, opcje, wzor
    przepis = a.przepis or "explainer"
    if przepis not in PRZEPISY:
        raise SystemExit(f"nieznany przepis {przepis!r}: {', '.join(PRZEPISY)}")
    return przepis, opcje, None


def dlugosc_filmu(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        raise SystemExit(f"nie umiem odczytać długości {path}: {out.stderr.strip()[:200]}")


def ma_dzwiek(path: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True)
    return bool(out.stdout.strip())


def glosnosc_pliku(path: Path) -> dict:
    """LUFS i szczyt prawdziwy ścieżki dźwięku (ffmpeg ebur128, ten sam pomiar co qa_wideo.py)."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0",
                          "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    s = log.split("Summary:")[-1]
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", s)
    p = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", s)
    return {"lufs": float(m.group(1)) if m else None,
            "szczyt_dbtp": float(p.group(1)) if p and p.group(1) != "-inf" else None}


# ---------------------------------------------------------------- lektor w miksie (decyzje bez mgaudio)

GLOS_NAD_MUZYKA = 10.0          # dB: głos (LUFS) nad muzyką bez ściszenia
SCISZENIE_POD_GLOSEM = 8.0      # dB: muzyka przysiada, gdy lektor mówi (razem ok. −18 dB pod głosem)
EFEKTY_POD_GLOSEM = 4.0         # dB: efekty ciszej pod mową (lektor-i-dzwiek: −18…−12 dB względem głosu)
MOWA_SCAL = 0.5                 # s: krótsza przerwa (oddech w akapicie) nie podnosi muzyki; pauza akapitu (1 s) tak
MOWA_PRZED, MOWA_PO = 0.12, 0.4  # s: muzyka schodzi przed pierwszym słowem i wraca po ostatnim
POD_GLOSEM_ZAKRES = (-22.0, -14.0)   # dB muzyki względem głosu, gdy lektor mówi (skill: −22…−16, z zapasem)


def segmenty_mowy(env_db: list[float], krok: float = 0.01, scal: float = MOWA_SCAL,
                  min_dl: float = 0.08) -> list[tuple[float, float]]:
    """Obwiednia głosu (dB co `krok` s) → odcinki mowy [(od, do)]: próg 35 dB pod głośnymi fragmentami (95. centyl,
    nie niżej niż −55 dB), przerwy krótsze niż `scal` sklejone, trzaski krótsze niż `min_dl` pominięte."""
    if not env_db:
        return []
    srt = sorted(env_db)
    prog = max(-55.0, srt[int(0.95 * (len(srt) - 1))] - 35.0)
    seg: list[list[float]] = []
    for i, v in enumerate(env_db):
        if v <= prog:
            continue
        t0, t1 = i * krok, (i + 1) * krok
        if seg and t0 - seg[-1][1] < scal - 1e-9:
            seg[-1][1] = t1
        else:
            seg.append([t0, t1])
    return [(round(a, 3), round(b, 3)) for a, b in seg if b - a >= min_dl - 1e-9]


def krzywa_sciszenia(segmenty: list[tuple[float, float]], dlugosc: float, glebokosc: float,
                     przed: float = MOWA_PRZED, po: float = MOWA_PO, krok: float = 0.01) -> list[float]:
    """dB co `krok` s: 0 poza mową, −glebokosc w mowie; zejście przez `przed` s przed mową, powrót przez `po` po niej."""
    n = int(round(dlugosc / krok)) + 1
    g = [0.0] * n
    for a, b in segmenty:
        for i in range(max(0, int((a - przed) / krok) - 1), min(n, int((b + po) / krok) + 2)):
            t = i * krok
            if t < a:
                d = -glebokosc * max(0.0, t - (a - przed)) / przed
            elif t <= b:
                d = -glebokosc
            else:
                d = -glebokosc * max(0.0, 1 - (t - b) / po)
            g[i] = min(g[i], round(d, 4) + 0.0)
    return g


def _srednia_energii_db(env: list[float], idx: list[int]) -> float | None:
    e = [10 ** (env[i] / 10) for i in idx if 0 <= i < len(env)]
    return round(10 * math.log10(sum(e) / len(e)), 1) if e and sum(e) > 0 else None


def proporcje_lektora(glos: list[float], muzyka: list[float], segmenty: list[tuple[float, float]],
                      krok: float = 0.01) -> dict:
    """Gotowy miks po stemach (dB co `krok` s): muzyka względem głosu, gdy lektor mówi, i głośność muzyki w pauzach
    względem głosu. Poza zakresem POD_GLOSEM_ZAKRES = uwaga (głos ginie albo muzyki nie słychać)."""
    mowa = {i for a, b in segmenty for i in range(round(a / krok), round(b / krok))}
    w_mowie = sorted(mowa)
    pauzy = [i for i in range(len(muzyka)) if i not in mowa]
    g, mm, mp = (_srednia_energii_db(glos, w_mowie), _srednia_energii_db(muzyka, w_mowie),
                 _srednia_energii_db(muzyka, pauzy))
    pod = round(mm - g, 1) if g is not None and mm is not None else None
    w_pauzach = round(mp - g, 1) if g is not None and mp is not None else None
    uwagi = []
    if pod is not None and pod > POD_GLOSEM_ZAKRES[1]:
        uwagi.append(f"muzyka pod głosem {pod:+.1f} dB względem lektora (głośniej niż {POD_GLOSEM_ZAKRES[1]:g}): głos ginie")
    if pod is not None and pod < POD_GLOSEM_ZAKRES[0]:
        uwagi.append(f"muzyka pod głosem {pod:+.1f} dB względem lektora (ciszej niż {POD_GLOSEM_ZAKRES[0]:g}): prawie jej nie słychać")
    return {"mowa_s": round(len(w_mowie) * krok, 2), "odcinki": len(segmenty), "muzyka_pod_glosem_db": pod,
            "muzyka_w_pauzach_db": w_pauzach, "uwagi": uwagi}


# ---------------------------------------------------------------- mgaudio (tylko w venv dodatku)

def mgaudio() -> SimpleNamespace:
    """Import mgaudio z klonu wzorów; spoza venv dodatku skrypt uruchamia się od nowa jego Pythonem."""
    venv_py = nz.MGAUDIO_VENV / "bin" / "python"
    if not venv_py.exists() or not (nz.MGSTYLES / "lib/audio/mgaudio").is_dir():
        raise SystemExit("brak mgaudio: python3 $HERMES_HOME/scripts/narzedzia.py instaluj mgaudio "
                         "(raz, pakiety ok. 390 MB i sample 56 MB)")
    if Path(sys.prefix).resolve() != nz.MGAUDIO_VENV.resolve():
        if os.environ.get("JARVO_MUZYKA_VENV"):
            raise SystemExit(f"Python {venv_py} nie widzi pakietów mgaudio: narzedzia.py instaluj mgaudio")
        os.environ["JARVO_MUZYKA_VENV"] = "1"
        os.execv(str(venv_py), [str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]])
    if not nz.indeks_sampli_zgodny():
        nz.napraw_indeks_sampli()
    sys.path.insert(0, str(nz.MGSTYLES / "lib" / "audio"))
    from mgaudio import drums, qc, recipes, sfx, sync  # noqa: PLC0415
    return SimpleNamespace(recipes=recipes, sfx=sfx, drums=drums, qc=qc, sync=sync)


def dzwiek_efektu(z: dict, sfx, drums, form):
    """Sound mgaudio dla zdarzenia: tonalne efekty w tonacji akordu z tej chwili."""
    nazwa = z["funkcja"]
    modul, fn = (drums, nazwa[6:]) if nazwa.startswith("drums.") else (sfx, nazwa)
    f = getattr(modul, fn, None)
    if fn.startswith("_") or not callable(f):
        raise SystemExit(f"nieznany efekt mgaudio {nazwa!r} (lista: muzyka.py efekty)")
    opcje = dict(z["opcje"])
    if z["zrodlo"] == "sound.mjs":
        if fn in Z_DLUGOSCIA:
            opcje[Z_DLUGOSCIA[fn]] = z["dlugosc"]
        akord = form.chord_at(z["chwila"])
        if fn == "chime":
            opcje["notes"] = tuple(n + 24 for n in akord[:4])
        elif fn == "sparkle":
            opcje.update(key=form.key, mode="minor_pentatonic" if "minor" in form.mode else "major_pentatonic")
        elif fn == "blip":
            opcje["note"] = akord[-1] + 24
        if fn in Z_WYSOKOSCIA and z["pitch"]:
            opcje["pitch"] = float(z["pitch"])
    try:
        s = f(**opcje)
    except TypeError as e:
        raise SystemExit(f"efekt {nazwa}: złe opcje {opcje}: {e}")
    if z["pitch"] and float(z["pitch"]) > 0 and abs(float(z["pitch"]) - 1) > 1e-3 \
            and not (z["zrodlo"] == "sound.mjs" and fn in Z_WYSOKOSCIA):
        s = s.pitch(12 * math.log2(float(z["pitch"])))
    return s


def wczytaj_lektora(sciezka: Path):
    """Lektor (WAV, MP3, M4A…) → stereo float 48 kHz (2, n) przez ffmpeg, bez zapisu na dysk."""
    import numpy as np  # noqa: PLC0415
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(sciezka), "-f", "f32le", "-ac", "2", "-ar", "48000",
                        "-"], capture_output=True)
    if r.returncode or not r.stdout:
        raise SystemExit(f"nie umiem odczytać lektora {sciezka}: {r.stderr.decode(errors='replace')[:200]}")
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).T.astype(np.float64)


def dodaj_lektora(m, dane, od: float, dlugosc: float) -> dict:
    """Głos jako ścieżka `lektor` (grupa `glos`, GLOS_NAD_MUZYKA dB nad poziomem muzyki), muzyka i efekty ściszane
    krzywą z odcinków mowy. Krzywe działają na gotowe grupy (post_fx), po ich własnym przysiadaniu pod efektami."""
    import numpy as np  # noqa: PLC0415
    from mgaudio.core import as_sound  # noqa: PLC0415
    sr = 48000
    if od + dane.shape[1] / sr > dlugosc + 0.05:
        raise SystemExit(f"lektor ({dane.shape[1] / sr:.2f} s od {od:g} s) dłuższy niż film ({dlugosc:.2f} s)")
    poziom_muzyki = m.group("music").level if m.group("music").level is not None else -20.0
    m.track("lektor", group="glos", level=poziom_muzyki + GLOS_NAD_MUZYKA).add(as_sound(dane.astype(np.float32)), at=od)
    env = [-100.0] * int(round(od * 100)) + obwiednia(dane.mean(axis=0), sr)
    segmenty = segmenty_mowy(env)
    t = np.arange(m.N) / sr
    siatka = np.arange(int(round(dlugosc / 0.01)) + 1) * 0.01
    for grupa, gleb in (("music", SCISZENIE_POD_GLOSEM), ("sfx", EFEKTY_POD_GLOSEM)):
        g = 10 ** (np.interp(t, siatka, krzywa_sciszenia(segmenty, dlugosc, gleb)) / 20)
        m.group(grupa).post_fx.append(lambda x, g=g: x * g[None, :])
    # głos zostaje naturalny: bez saturacji taśmy, podbicia góry i pochylenia z masteringu przepisu
    m.master_kw.update(warmth=0.0, air=0.0, tilt=0.0)
    return {"segmenty": segmenty, "mowa_s": round(sum(b - a for a, b in segmenty), 2),
            "poziom_lufs_przed_masterem": poziom_muzyki + GLOS_NAD_MUZYKA}


def plan_muzyki(a, dlugosc: float, zd: list[dict]) -> dict:
    """Decyzje przed renderem (czyste, bez mgaudio): przepis, kulminacja, koniec, tempo, zdarzenia do siatki."""
    przepis, opcje, wzor = wybierz_przepis(a)
    kul = a.kulminacja
    zrodla = {}
    if kul is None:
        z = kulminacja_z_cues(zd, dlugosc)
        if z:
            kul, zrodla["kulminacja"] = z["chwila"], f"{z['nazwa']} w {z['chwila']:.2f} s (cues.json)"
    else:
        zrodla["kulminacja"] = "--kulminacja"
    kon = a.koniec
    if kon is None:
        z = koniec_z_cues(zd, dlugosc, kul)
        if z:
            kon, zrodla["koniec"] = z["chwila"], f"{z['nazwa']} w {z['chwila']:.2f} s (cues.json)"
    else:
        zrodla["koniec"] = "--koniec"
    if kul is not None and not 0 < kul < dlugosc:
        raise SystemExit(f"kulminacja {kul} s poza filmem (0–{dlugosc:.2f} s)")
    if kon is not None and (kon >= dlugosc or (kul is not None and kon <= kul)):
        raise SystemExit(f"koniec {kon} s musi być po kulminacji i przed końcem filmu ({dlugosc:.2f} s)")
    trafienia = chwile_do_tempa(zd) if a.tempo is None else []
    zrodla.setdefault("kulminacja", "przepis (ok. 42% filmu, na początku taktu)")
    zrodla.setdefault("koniec", "przepis (końcowy akord ok. 1–2 s przed końcem)")
    return {"przepis": przepis, "opcje": opcje, "wzor": wzor, "styl": a.styl, "dlugosc": round(dlugosc, 4),
            "kulminacja": kul, "koniec": kon, "tempo": a.tempo, "trafienia": trafienia, "zrodla": zrodla}


def cmd_zrob(a) -> int:
    obraz = Path(a.obraz).resolve() if a.obraz else None
    wynik = Path(a.o).resolve()
    if obraz and wynik.suffix.lower() != ".mp4":
        raise SystemExit("z obrazem wynik to .mp4 (dźwięk zastępuje ścieżkę filmu)")
    if not obraz and wynik.suffix.lower() != ".wav":
        raise SystemExit("bez obrazu wynik to .wav (albo podaj obraz.mp4)")
    lektor = Path(a.lektor).resolve() if getattr(a, "lektor", None) else None
    if lektor and not lektor.is_file():
        raise SystemExit(f"brak pliku lektora: {lektor}")
    dlugosc = a.dlugosc or (dlugosc_filmu(obraz) if obraz else None) \
        or (round(a.lektor_od + dlugosc_filmu(lektor), 3) if lektor else None)
    if not dlugosc:
        raise SystemExit("podaj --dlugosc S, obraz.mp4 albo --lektor")
    zd = [] if a.bez_efektow else [zdarzenie(c) for c in wczytaj_cues(Path(a.cues) if a.cues else None)]
    plan = plan_muzyki(a, dlugosc, zd)
    mga = mgaudio()

    kw = dict(plan["opcje"])
    if plan["wzor"]:
        przepis_wzoru, opcje_wzoru, _alt, _paleta = mga.recipes.STYLES[plan["wzor"]]
        if przepis_wzoru != plan["przepis"]:
            print(f"! wzór {plan['wzor']} ma teraz przepis {przepis_wzoru} (u nas {plan['przepis']}): biorę {przepis_wzoru}")
            plan["przepis"] = przepis_wzoru
        kw = {**opcje_wzoru, **kw}
    kw["duration"] = plan["dlugosc"]
    for klucz, pole in (("drop", "kulminacja"), ("outro", "koniec"), ("bpm", "tempo")):
        if plan[pole] is not None:
            kw[klucz] = plan[pole]
    if a.tonacja:
        kw["key"] = a.tonacja
    if a.tryb:
        kw["mode"] = a.tryb
    if plan["trafienia"] and len(plan["trafienia"]) >= 2:
        kw["hits"] = plan["trafienia"]
    try:
        m = mga.recipes.recipe(plan["przepis"], **kw)
    except TypeError as e:
        raise SystemExit(f"przepis {plan['przepis']}: {e} (opcje: muzyka.py przepisy)")
    f = m.form
    umieszczone, polozone = [], []
    for z in zd:
        s = dzwiek_efektu(z, mga.sfx, mga.drums, f)
        chwila = z["chwila"]
        if chwila - s.sync < 0:          # dźwięk zacząłby się przed filmem: przycinamy początek
            s = s.trim(s.sync - chwila)
        m.sfx(s, at=chwila, gain=z["db"], pan=z["pan"])
        polozone.append((z, s))
        umieszczone.append({"nazwa": z["nazwa"], "zrodlo": z["zrodlo"], "chwila": round(chwila, 3),
                            "start": round(chwila - s.sync, 3), "glosnosc_db": z["db"], "rola": z["rola"]})

    lektor_info = dodaj_lektora(m, wczytaj_lektora(lektor), a.lektor_od, plan["dlugosc"]) if lektor else None
    wav = wynik if not obraz else wynik.with_suffix(".muzyka.wav")
    wav.parent.mkdir(parents=True, exist_ok=True)
    # do MP4 zapas 0,5 dB: AAC dokłada przesterowania między próbkami
    m.export(str(wav), lufs=a.lufs, tp=-1.5 if obraz else -1.0, analyze=False)
    sciezki = zapisz_sciezki(m, wav)
    res = mga.qc.analyze(str(wav), expected=plan["dlugosc"], onsets=False)
    kontrola = ocena(res, a.lufs, slyszalnosc(m, polozone, wav, plan["dlugosc"]) if polozone else None)
    kontrola["uwagi"] += tlok(zd)
    if lektor_info:
        kontrola["lektor"] = lektor_w_miksie(m, wav, lektor_info["segmenty"])
        kontrola["uwagi"] += kontrola["lektor"]["uwagi"]
    if obraz:
        if not lektor and ma_dzwiek(obraz):
            kontrola["uwagi"].append("obraz miał własny dźwięk i został zastąpiony; lektora daj przez --lektor")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(obraz), "-i", str(wav), "-map", "0:v:0", "-map", "1:a:0",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                        str(wynik)], check=True)
        mp4 = glosnosc_pliku(wynik)
        kontrola["mp4"] = mp4
        if mp4["szczyt_dbtp"] is not None and mp4["szczyt_dbtp"] > -1.0:
            kontrola["uwagi"].append(f"MP4: szczyt {mp4['szczyt_dbtp']} dBTP po AAC (montaz.py glosnosc --lufs {a.lufs:g})")
        if mp4["lufs"] is not None and abs(mp4["lufs"] - a.lufs) > 1.0:
            kontrola["uwagi"].append(f"MP4: {mp4['lufs']} LUFS zamiast {a.lufs:g}")

    fs = f.summary()
    takty = [round(t, 3) for t in f.bars(0, plan["dlugosc"]) if t >= -1e-6]
    siatka = [{"t": t, "na_siatce": g, "blad": e} for t, g, e, _ in mga.sync.grid_report(plan["trafienia"], m.grid, 8)]
    na_siatce = sum(1 for r in siatka if abs(r["blad"]) <= KLATKA + 1e-6)
    wynik_json = {
        "przepis": plan["przepis"], "opcje": {k: v for k, v in kw.items() if k not in ("duration", "hits", "drop", "outro", "bpm")},
        "styl": plan["styl"], "wzor": plan["wzor"], "dlugosc": plan["dlugosc"], "tempo": fs["bpm"],
        "takt_s": fs["bar"], "bit_s": fs["beat"], "tonacja": fs["key"],
        "sekcje": {"wstep": 0.0, "narastanie": fs["build"], "kulminacja": fs["drop"], "koniec": fs["outro"]},
        "skad": plan["zrodla"], "akordy": fs["chords"], "akord_koncowy": fs["final"], "takty": takty,
        "siatka": {"zdarzenia": len(siatka), "w_klatce": na_siatce, "najwiekszy_blad_s": fs["hit_fit_err"], "lista": siatka},
        "efekty": umieszczone, "kontrola": kontrola,
        **({"lektor": {"plik": str(lektor), "od": a.lektor_od, "mowa_s": lektor_info["mowa_s"],
                       "odcinki": [list(x) for x in lektor_info["segmenty"]],
                       "glos_nad_muzyka_db": GLOS_NAD_MUZYKA, "sciszenie_db": SCISZENIE_POD_GLOSEM,
                       "efekty_pod_glosem_db": EFEKTY_POD_GLOSEM}} if lektor_info else {}),
        "pliki": {"wav": str(wav), **({"mp4": str(wynik)} if obraz else {})},
        "sciezki": sciezki,
    }
    plan_json = Path(a.json).resolve() if a.json else (wynik.with_suffix(".muzyka.json"))
    plan_json.write_text(json.dumps(wynik_json, ensure_ascii=False, indent=1), encoding="utf-8")
    wypisz(wynik_json, plan_json)
    return 0 if kontrola["ok"] else 1


GRUPY_SCIEZEK = {"group.sfx": "efekty", "group.glos": "glos"}    # każda inna grupa (music…) = muzyka


def sciezki_dir(wav: Path) -> Path:
    return wav.with_name(f"{wav.stem}.sciezki")


def zapisz_sciezki(m, wav: Path) -> dict:
    """Warstwy miksu osobno do edytora (`projekt.py z-kodu --z-muzyki`): grupy po przysiadaniu pod efektami i lektorem,
    przeskalowane jak master (gotowy WAV kontra suma grup, jak w kontroli), float bez obcinania, od 0 s do końca."""
    import numpy as np  # noqa: PLC0415
    import soundfile as sf  # noqa: PLC0415
    grupy = {k: np.asarray(v, dtype=np.float64) for k, v in m.stems.items() if k.startswith("group.")}
    if not grupy:
        return {}
    rms = lambda x: float(np.sqrt(np.mean(np.square(x))) + 1e-12)  # noqa: E731
    gotowy, sr = sf.read(str(wav), always_2d=True)
    master = rms(gotowy.T.mean(axis=0)) / rms(sum(v.mean(axis=0) for v in grupy.values()))
    warstwy: dict[str, object] = {}
    for k, v in grupy.items():
        nazwa = GRUPY_SCIEZEK.get(k, "muzyka")
        warstwy[nazwa] = warstwy[nazwa] + v if nazwa in warstwy else v
    kat = sciezki_dir(wav)
    kat.mkdir(parents=True, exist_ok=True)
    wynik = {}
    for nazwa, v in warstwy.items():
        if not np.any(np.abs(v) > 1e-6):            # pusta grupa (np. efekty bez cues.json) nie idzie do edytora
            continue
        plik = kat / f"{nazwa}.wav"
        sf.write(str(plik), (v * master).T.astype(np.float32), sr, subtype="FLOAT")
        wynik[nazwa] = str(plik)
    return wynik


def obwiednia(x, sr: int = 48000):
    """dB co 10 ms (jak projekt.obwiednia_db, cisza = −100), numpy zamiast pętli."""
    import numpy as np  # noqa: PLC0415
    n = sr // 100
    x = np.asarray(x, dtype=np.float64)
    k = len(x) // n
    e = (x[:k * n].reshape(k, n) ** 2).mean(axis=1)
    return [float(v) for v in np.where(e > 1e-10, 10 * np.log10(np.maximum(e, 1e-30)), -100.0)]


def slyszalnosc(m, polozone: list, wav: Path, dlugosc: float) -> dict:
    """Każdy efekt kontra muzyka w tej samej chwili, oceną z `projekt.py slychac` (czysto / słychać / zagłuszony /
    bez dźwięku). Muzyka = jej grupa po przysiadaniu pod efektami; efekt = jego dźwięk z głośnością i tym samym
    wzmocnieniem co cała grupa efektów; oba przeskalowane jak master (gotowy WAV kontra suma grup przed nim)."""
    import numpy as np  # noqa: PLC0415
    import soundfile as sf  # noqa: PLC0415
    st = m.stems
    mono = lambda x: np.asarray(x, dtype=np.float64).mean(axis=0) if np.ndim(x) == 2 else np.asarray(x, dtype=np.float64)  # noqa: E731
    rms = lambda x: float(np.sqrt(np.mean(np.square(x))) + 1e-12)  # noqa: E731
    przed = sum(mono(v) for k, v in st.items() if k.startswith("group."))
    gotowy, sr = sf.read(str(wav), always_2d=True)
    master = rms(mono(gotowy.T)) / rms(przed)
    surowe, bufory = np.zeros(m.N), []
    for z, s in polozone:
        d = mono(s.data) * 10 ** (z["db"] / 20)
        i0 = max(0, round((z["chwila"] - s.sync) * sr))
        d = d[:max(0, m.N - i0)]
        surowe[i0:i0 + len(d)] += d
        bufory.append((z, i0, d))
    grupa = rms(mono(st["group.sfx"])) / rms(surowe) if "group.sfx" in st else 1.0
    tlo_grupy = [mono(st[k]) for k in ("group.music", "group.glos") if k in st]     # tło = muzyka i lektor
    tlo = obwiednia(sum(tlo_grupy) * master, sr) if tlo_grupy else [-100.0] * int(dlugosc * 100)
    zdarzenia = [{"nazwa": z["nazwa"], "start": i0 / sr, "env": obwiednia(d * grupa * master, sr), "rola": [z["rola"]],
                  "glosnosc": 0.5 * 10 ** (z["db"] / 20)} for z, i0, d in bufory]
    return pj.ocena_slyszalnosci(zdarzenia, tlo, dlugosc)


def lektor_w_miksie(m, wav: Path, segmenty: list[tuple[float, float]]) -> dict:
    """Proporcje w gotowym miksie: stemy głosu i muzyki przeskalowane jak master (gotowy WAV kontra suma grup)."""
    import numpy as np  # noqa: PLC0415
    import soundfile as sf  # noqa: PLC0415
    st = m.stems
    mono = lambda x: np.asarray(x, dtype=np.float64).mean(axis=0)  # noqa: E731
    rms = lambda x: float(np.sqrt(np.mean(np.square(x))) + 1e-12)  # noqa: E731
    gotowy, sr = sf.read(str(wav), always_2d=True)
    master = rms(gotowy.T.mean(axis=0)) / rms(sum(mono(v) for k, v in st.items() if k.startswith("group.")))
    return proporcje_lektora(obwiednia(mono(st["group.glos"]) * master, sr),
                             obwiednia(mono(st["group.music"]) * master, sr), segmenty)


def ocena(res: dict, lufs: float, sluch: dict | None) -> dict:
    """Kontrola po eksporcie: uwagi mgaudio po polsku (głośność względem naszego celu) i słyszalność efektów."""
    uwagi = [uwaga_pl(w) for w in res.get("warnings", []) if not w.startswith("LUFS ")]
    if abs(res["lufs"] - lufs) > 0.6:
        uwagi.append(f"głośność {res['lufs']} LUFS zamiast {lufs:g}")
    bledy = [u for u in uwagi if u.startswith(("długość", "w dźwięku", "szczyt", "głośność"))
             or "próbek przesterowanych" in u]
    if sluch:
        uwagi += [f"efekty: {b}" for b in sluch["bledy"]]
    return {"lufs": res["lufs"], "szczyt_dbtp": res["true_peak"], "pasma_proc": res.get("bands"),
            "korelacja_lp": res.get("stereo_corr"), "najdluzsza_cisza_s": res.get("longest_gap"),
            "slyszalnosc": sluch, "uwagi": uwagi, "ok": not bledy and (sluch is None or sluch["ok"])}


def wypisz(p: dict, plan_json: Path) -> None:
    s = p["sekcje"]
    print(f"Muzyka: {p['przepis']}" + (f" (styl {p['styl']}, wzór {p['wzor']})" if p["styl"] else "")
          + f" · {p['tempo']:g} BPM · {p['tonacja']} · {p['dlugosc']:g} s")
    print(f"  forma: wstęp 0 → narastanie {s['narastanie']:.2f} → kulminacja {s['kulminacja']:.2f} → koniec "
          f"{s['koniec']:.2f} s" + "".join(f"\n  {k}: {v}" for k, v in p["skad"].items()))
    print(f"  akordy: {' '.join(p['akordy'])} → {p['akord_koncowy']}; takty co {p['takt_s']:.3f} s, "
          f"pierwsze: {', '.join(f'{t:.2f}' for t in p['takty'][:6])}")
    sg = p["siatka"]
    if sg["zdarzenia"]:
        print(f"  zdarzenia z cues.json w klatce siatki ósemek: {sg['w_klatce']} z {sg['zdarzenia']}"
              + (f" (największy błąd {sg['najwiekszy_blad_s'] * 1000:.0f} ms)" if sg["najwiekszy_blad_s"] is not None else ""))
    k = p["kontrola"]
    sl = k["slyszalnosc"]
    if sl:
        znak = {"czysto": "✓", "slychac": "·", "zagluszony": "✗", "brak": "✗"}
        opis = {"czysto": "czysto", "slychac": "słychać", "zagluszony": "zagłuszony", "brak": "prawie bez dźwięku"}
        print(f"  efekty: {len(p['efekty'])} · czysto {sl['ile']['czysto']}, słychać {sl['ile']['slychac']}, "
              f"zagłuszone {sl['ile']['zagluszony']}, bez dźwięku {sl['ile']['brak']}")
        for w in sorted(sl["efekty"], key=lambda w: w["t"]):
            print(f"    {znak[w['ocena']]} {w['t']:6.2f} s  {w['nazwa']:<14} {w['zapas_db']:+5.1f} dB nad tłem  "
                  f"{opis[w['ocena']]}" + (f"  → {w['porada'].replace('głośniej: ', 'głośniej: vol ')}" if w["porada"] else ""))
    if k.get("lektor"):
        lk = k["lektor"]
        print(f"  lektor: mowa {lk['mowa_s']:g} s w {lk['odcinki']} odcinkach; muzyka pod głosem "
              f"{lk['muzyka_pod_glosem_db']} dB, w pauzach {lk['muzyka_w_pauzach_db']} dB względem lektora")
    print(f"  kontrola: {k['lufs']} LUFS, szczyt {k['szczyt_dbtp']} dBTP, korelacja L/P {k['korelacja_lp']}"
          + (f"; MP4 {k['mp4']['lufs']} LUFS, {k['mp4']['szczyt_dbtp']} dBTP" if k.get("mp4") else ""))
    for u in k["uwagi"]:
        print(f"  ! {u}")
    if p.get("sciezki"):
        print(f"  ścieżki do edytora: {', '.join(p['sciezki'])} w {Path(next(iter(p['sciezki'].values()))).parent}/ "
              f"(projekt.py z-kodu <film> --obraz <obraz> --z-muzyki {plan_json})")
    print(f"Wynik: {'OK' if k['ok'] else 'DO POPRAWY'} · plan {plan_json}")
    if "mp4" in p["pliki"]:
        print(f"MEDIA:{p['pliki']['mp4']}")


def cmd_sprawdz(a) -> int:
    qc = mgaudio().qc
    wav = Path(a.plik).resolve()
    res = qc.analyze(str(wav), expected=None, onsets=False)
    k = ocena(res, a.lufs, None)
    print(f"{wav.name}: {res['duration']:.2f} s, {k['lufs']} LUFS, szczyt {k['szczyt_dbtp']} dBTP, "
          f"korelacja L/P {k['korelacja_lp']}, najdłuższa cisza {k['najdluzsza_cisza_s']} s")
    print("  pasma (% energii): " + ", ".join(f"{n} {v}" for n, v in (k["pasma_proc"] or {}).items()))
    for u in k["uwagi"]:
        print(f"  ! {u}")
    print(f"Wynik: {'OK' if k['ok'] else 'DO POPRAWY'}")
    return 0 if k["ok"] else 1


def cmd_przepisy(_a) -> int:
    print("Przepisy (mgaudio, MIT): tempo domyślne (zakres) · tonacja · brzmienie → do czego")
    for n, (opis, tempo, ton, do) in PRZEPISY.items():
        print(f"  {n:<12} {tempo:<14} {ton:<12} {opis}\n  {'':<12} → {do}")
    print("\nStyle ze skilla style-motion (--styl): przepis i opcje jak we wzorze mg-styles-15; alternatywa przez --przepis")
    for st, (wzor, prz, alt) in STYLE.items():
        print(f"  {st:<14} {prz:<12} alternatywa {alt or '–':<12} wzór {wzor}")
    print("\nOpcje przepisu: --opcje '{\"flavor\": \"glass\"}'; wspólne: --tempo, --tonacja (A, F#, Bb), "
          "--tryb (major, minor, dorian, phrygian…), --kulminacja, --koniec.")
    return 0


def cmd_efekty(_a) -> int:
    print("Wpisy jak dla sound.mjs ({\"sfx\": …, \"t\": początek}) → odpowiednik mgaudio:")
    for n, (fn, op, dl, sync) in SOUND_MJS.items():
        kiedy = "przelot w połowie" if sync == 0.5 else "koniec = uderzenie" if sync == 1.0 else "atak od razu"
        print(f"  {n:<8} → {fn}({', '.join(f'{k}={v!r}' for k, v in op.items())})  [{dl:g} s, {kiedy}, rola {ROLA[n]}]")
    print("\nWłasne mgaudio ({\"mg\": nazwa, \"t\": chwila synchronizacji, \"opcje\": {…}, \"vol\", \"pan\", \"pitch\"}):")
    for rodzina, lista in MG_RODZINY.items():
        print(f"  {rodzina}: {lista}")
    print("\nTonalne (chime, sparkle, blip) grają w tonacji akordu z tej chwili. Najwyżej 3 efekty na klatkę.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("przepisy", help="15 gatunków i style").set_defaults(fn=cmd_przepisy)
    sub.add_parser("efekty", help="efekty w cues.json").set_defaults(fn=cmd_efekty)
    z = sub.add_parser("zrob", help="muzyka (i efekty) pod obraz")
    z.add_argument("obraz", nargs="?", help="film bez dźwięku albo z dźwiękiem do zastąpienia (.mp4)")
    z.add_argument("-o", required=True, help="final.mp4 (z obrazem) albo muzyka.wav")
    z.add_argument("--cues", help="cues.json filmu (te same czasy co obraz)")
    gatunek = z.add_mutually_exclusive_group()
    gatunek.add_argument("--styl", help="styl ze skilla style-motion (kreska, hud, synthwave…)")
    gatunek.add_argument("--przepis", help="gatunek mgaudio (muzyka.py przepisy), domyślnie explainer")
    z.add_argument("--opcje", help='opcje przepisu jako JSON, np. \'{"keys": "rhodes"}\'')
    z.add_argument("--dlugosc", type=float, help="długość w s (domyślnie długość obrazu)")
    z.add_argument("--kulminacja", type=float, help="chwila kulminacji (drop): takt 0, pełne wejście")
    z.add_argument("--koniec", type=float, help="chwila logo / końcowego kadru: od niej końcowy akord")
    z.add_argument("--tempo", type=float, help="BPM (domyślnie: z zakresu przepisu, najlepiej do zdarzeń)")
    z.add_argument("--tonacja", help="np. A, F#, Bb")
    z.add_argument("--tryb", help="major, minor, dorian, phrygian…")
    z.add_argument("--bez-efektow", action="store_true", help="sama muzyka (efekty osobno albo pod lektora)")
    z.add_argument("--lufs", type=float, default=-14.0)
    z.add_argument("--json", help="plan (domyślnie <wynik>.muzyka.json)")
    z.add_argument("--lektor", help="głos do miksu (lektor.wav z film.py narracja): muzyka ściszana pod mowę")
    z.add_argument("--lektor-od", type=float, default=0.0, help="chwila filmu, od której gra lektor (s)")
    z.set_defaults(fn=cmd_zrob)
    s = sub.add_parser("sprawdz", help="kontrola gotowej muzyki (WAV)")
    s.add_argument("plik")
    s.add_argument("--lufs", type=float, default=-14.0)
    s.set_defaults(fn=cmd_sprawdz)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
