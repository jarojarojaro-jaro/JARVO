#!/usr/bin/env python3
"""Clipmaker: długie nagranie → krótkie rolki (9:16 domyślnie, 16:9 na życzenie) jako projekty edytora HQ + MP4.

    klipy.py przygotuj <nagranie> [-o out/wideo/klipy] [--od-nowa]
    klipy.py sprawdz <plan.json>
    klipy.py zbuduj <plan.json> [-o out/wideo/klipy] [--bez-renderu] [--tylko SLUG] [--nadpisz]

przygotuj (0 tokenów): mowa (Parakeet: słowa z czasem, pauzy, wtrącenia) do <nagranie>.mowa.json — tego samego
pliku używa zakładka „Mowa” w edytorze HQ; cięcia ujęć; arkusze klatek z czasem (do vision_analyze: gdzie jest
mówca); transkrypcja.txt ze zdaniami i czasami, podzielona na okna ~90 s (to czytasz według master promptu,
każde okno dostaje ocenę) i analiza.json.

sprawdz: plan.json przed budową (czasy w źródle, długości, hook, kadr, oceny, granice w słowach, wspólny materiał
rolek, pokrycie nagrania). Błędy = kod 1, uwagi nie blokują.

zbuduj: każda rolka → <out>/klip-N-<slug>.edycja.json (projekt edytora: segmenty ze źródła z granicą dosuniętą
ze środka słowa do przerwy obok, wycięte pauzy i wtrącenia, kadr na twarzy mówcy, gdy plan nie podaje fx/fy
(twarze.py, YuNet: śledzenie z bezwładnością, nowe ujęcie przy zmianie twarzy albo dużym przesunięciu),
punch-in na cięciach, głośność klipów do −14 LUFS z pomiaru źródła, napisy karaoke ze słów, tytuł-hook)
i render tym samym
silnikiem co „Eksportuj” → <out>/klip-N-<slug>.mp4, na końcu KLIPY.md. Człowiek otwiera rolkę w HQ („✎ Edytuj”)
i poprawia wszystko; eksport z edytora robi nową wersję obok.

plan.json: patrz skill clipmaker (references/plan.md). Czas w sekundach ŹRÓDŁA.
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import projekt as pr  # noqa: E402  (silnik edytora: pr.ed)

ed = pr.ed
FORMATY = {"9:16": (1080, 1920), "16:9": (1920, 1080)}
FPS = 30
ODDECH = 0.12            # tyle ciszy zostaje po wycięciu pauzy (jak w edytorze)
PRZED, PO = 0.08, 0.25   # zapas przed pierwszym i po ostatnim słowie segmentu
LEAD, TAIL = 0.35, 0.45  # granica dosunięta ze słowa: najwyżej tyle ciszy przed / po słowie (połowa przerwy; za openshorts)
OKNO = 90.0              # okno transkrypcji do oceny 0–100: długie nagranie przeczytane i ocenione równo, nie tylko początek
WSPOLNE = 0.2            # dwie rolki dzielą więcej materiału źródła niż tyle krótszej z nich → uwaga
KADR_Y = 0.38            # środek twarzy na tej wysokości kadru (oczy mniej więcej na 1/3)
ZMIANA = 3               # tyle próbek z rzędu (≈ 1,5 s), zanim kadr przejdzie na inną twarz albo w nowe miejsce
BONUS = 3.0              # twarz w kadrze liczy się ×3 przy wyborze (za openshorts: kadr nie skacze między twarzami)
ODEJSCIE = 0.35          # twarz odeszła od ustawienia kadru o tyle szerokości kadru → nowe ustawienie
LUFS, SZCZYT = -14.0, -1.5   # głośność rolki i najwyższy szczyt (jak montaz.py glosnosc i qa_wideo.py)
PUNCH = 1.12             # przybliżenie co drugiego ujęcia po cięciu (ukrywa skok obrazu)
HL = pr.KARAOKE_HL
ZLE_STARTY = ("no i", "i ", "a ", "tak jak mówiłem", "wracając do", "jak mówiłem", "więc", "no więc", "no to",
              "ale ", "bo ", "czyli", "and ", "so ", "but ", "like i said", "anyway")
STYL = {"napisy": "karaoke", "hl": HL, "tytul": True, "tytul_s": 3.0, "tnij_pauzy": 0.6, "bez_wtracen": True,
        "punch": True, "kadr_auto": True, "muzyka": None, "muzyka_glosnosc": 0.12}


def mmss(s: float) -> str:
    s = max(0.0, s)
    return f"{int(s // 60):02d}:{s % 60:04.1f}"


# ---------------------------------------------------------------- przygotuj

def analiza_mowy(src: Path, od_nowa: bool) -> dict:
    """<nagranie>.mowa.json jak w edytorze HQ: pauzy (silencedetect) + słowa (jarvo-stt --json)."""
    sp = ed.speech_path(src)
    if sp.is_file() and not od_nowa:
        d = json.loads(sp.read_text(encoding="utf-8"))
        if d.get("words"):
            return d
    info = ed.probe(src)
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-vn", "-af",
                        f"silencedetect=noise={ed.SILENCE_DB}dB:d={ed.SILENCE_MIN}", "-f", "null", "-"],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffmpeg nie przeanalizował dźwięku: {r.stderr.strip()[-300:]}")
    silences = ed.parse_silences(r.stderr, info.get("duration"))
    stt = ed.stt_bin()
    if not stt:
        raise SystemExit("brak jarvo-stt (rozpoznawanie mowy): bez słów nie wybierzesz fragmentów")
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "slowa.json"
        r = subprocess.run([stt, str(src), "--json", str(out)], capture_output=True, text=True)
        if r.returncode or not out.is_file():
            raise SystemExit(f"jarvo-stt: {r.stderr.strip()[-300:]}")
        words = json.loads(out.read_text(encoding="utf-8")).get("words") or []
    d = ed.speech_data(words, silences, info.get("duration"))
    sp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    if d["lines"]:
        ed.auto_srt_path(src).write_text(ed.to_srt(d["lines"]), encoding="utf-8")
    return d


def sceny(src: Path, prog: float = 0.35) -> list[float]:
    """Cięcia ujęć (zmniejszony obraz: szybko także dla godzinnego nagrania)."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-an", "-vf",
                        f"scale=320:-2,select='gt(scene,{prog})',showinfo", "-f", "null", "-"], capture_output=True, text=True)
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def arkusze(src: Path, dur: float, out: Path, na_arkusz: int = 24, kolumny: int = 6) -> list[dict]:
    """Klatki co `co` s (najwyżej ~72 na całe nagranie) z czasem w rogu: gdzie mówca, ile osób, plansze."""
    co = max(5.0, dur / 72)
    n = max(1, int(dur / co))
    out.mkdir(parents=True, exist_ok=True)
    wynik = []
    for k, first in enumerate(range(0, n, na_arkusz)):
        cnt = min(na_arkusz, n - first)
        dest = out / f"arkusz-{k + 1}.jpg"
        t0 = first * co
        base = f"fps=1/{co:.3f},scale=320:-2"
        label = (f",drawtext=text='%{{pts\\:hms\\:{t0:.3f}}}':x=4:y=4:fontsize=16:fontcolor=white:"
                 "box=1:boxcolor=black@0.7:boxborderw=3")
        tile = f",tile={kolumny}x{(cnt + kolumny - 1) // kolumny}:padding=4:color=0x0B0D12"
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{cnt * co:.3f}", "-i", str(src)]
        r = subprocess.run(cmd + ["-vf", base + label + tile, "-frames:v", "1", "-q:v", "3", str(dest)], capture_output=True)
        if r.returncode:   # bez fontu do drawtext: arkusz bez czasu (kolejność × co od t0)
            subprocess.run(cmd + ["-vf", base + tile, "-frames:v", "1", "-q:v", "3", str(dest)], check=True, capture_output=True)
        wynik.append({"plik": str(dest), "od": round(t0, 1), "do": round(t0 + cnt * co, 1), "co_s": round(co, 1)})
    return wynik


def zdania(words: list, max_gap: float = 1.0, max_dur: float = 25.0) -> list[dict]:
    """Słowa → zdania z czasem źródła (do czytania i wyboru fragmentów). Wtrącenia zostają, oznaczone „(yyy)”."""
    out, cur = [], []

    def flush():
        if cur:
            out.append({"od": cur[0][0], "do": cur[-1][1], "tekst": " ".join(w[2] for w in cur)})
            cur.clear()
    for w in words:
        a, b, t = float(w[0]), float(w[1]), str(w[2])
        if cur and (a - cur[-1][1] > max_gap or b - cur[0][0] > max_dur):
            flush()
        cur.append((a, b, "(yyy)" if ed.is_filler(t) else t))
        if t.endswith((".", "!", "?", "…")):
            flush()
    flush()
    return out


def okna(zd: list[dict], dl: float = OKNO) -> list[dict]:
    """Zdania → okna ~`dl` s (granica zawsze między zdaniami). Każde okno agent ocenia 0–100, zanim wybierze rolki."""
    out: list[dict] = []
    for z in zd:
        if not out or z["od"] - out[-1]["od"] >= dl:
            out.append({"n": len(out) + 1, "od": z["od"], "do": z["do"], "zdan": 0})
        out[-1]["do"] = z["do"]
        out[-1]["zdan"] += 1
    return out


def cmd_przygotuj(a) -> int:
    src = Path(a.nagranie).resolve()
    if not src.is_file():
        raise SystemExit(f"nie ma pliku: {src}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    info = ed.probe(src)
    dur = info.get("duration") or 0.0
    print(f"▶ mowa (Parakeet, ~1–2 min na 10 min nagrania): {src.name}, {mmss(dur)}", flush=True)
    d = analiza_mowy(src, a.od_nowa)
    print("▶ cięcia ujęć i arkusze klatek", flush=True)
    cuts = sceny(src)
    sheets = arkusze(src, dur, out / "klatki") if info.get("video") else []
    zd = zdania(d["words"])
    pauzy = [s for s in d.get("silences") or [] if s[1] - s[0] >= 1.5]
    ok = okna(zd)
    lines = [f"# Transkrypcja: {src.name} · {mmss(dur)} · {len(d['words'])} słów · {len(cuts)} cięć ujęć · {len(ok)} okien",
             "# [od–do w ŹRÓDLE] zdanie; (yyy) = wtrącenie; (pauza N s) = cisza ≥ 1,5 s",
             "# ## Okno N: ~90 s; każde oceniasz 0–100 w KANDYDACI.md (master prompt, krok 1)", ""]
    pi, starty = 0, {o["od"]: o for o in ok}
    for z in zd:
        while pi < len(pauzy) and pauzy[pi][0] < z["od"]:
            lines.append(f"      (pauza {pauzy[pi][1] - pauzy[pi][0]:.1f} s)")
            pi += 1
        if z["od"] in starty:
            o = starty.pop(z["od"])
            lines += ([""] if o["n"] > 1 else []) + [f"## Okno {o['n']} [{mmss(o['od'])}–{mmss(o['do'])}]"]
        lines.append(f"[{mmss(z['od'])}–{mmss(z['do'])}] {z['tekst']}")
    (out / "transkrypcja.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = {"zrodlo": str(src), "sek": round(dur, 2), "w": info.get("w"), "h": info.get("h"), "fps": info.get("fps"),
           "slowa": len(d["words"]), "zdania": len(zd), "okna": ok, "ciecia_ujec": cuts, "arkusze": sheets,
           "mowa": str(ed.speech_path(src)), "transkrypcja": str(out / "transkrypcja.txt")}
    (out / "analiza.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {out / 'transkrypcja.txt'} ({len(zd)} zdań, {len(ok)} okien) · {len(sheets)} arkuszy klatek · {out / 'analiza.json'}")
    print("Dalej: master prompt (skill clipmaker) → plan.json → klipy.py sprawdz → klipy.py zbuduj")
    return 0


# ---------------------------------------------------------------- plan: odczyt i sprawdzenie

def wczytaj_plan_dict(plan: dict) -> dict:
    """Plan z domyślnym stylem rolki (to, czego plan nie podaje, bierzemy z STYL)."""
    return {**plan, "styl": {**STYL, **(plan.get("styl") or {})}}


def wczytaj_plan(path: Path) -> dict:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"plan.json nie czyta się: {exc}")
    return wczytaj_plan_dict(plan)


def slowa_zrodla(src: Path) -> list:
    sp = ed.speech_path(src)
    if not sp.is_file():
        raise SystemExit(f"brak {sp.name}: najpierw klipy.py przygotuj {src}")
    return json.loads(sp.read_text(encoding="utf-8")).get("words") or []


def _tokeny(tekst: str) -> set[str]:
    return {w for w in re.findall(r"\w+", tekst.lower()) if len(w) > 2}


def powtarza_mowe(tytul: str, words: list, od: float, okno: float = 4.0) -> bool:
    """Tytuł-hook, który mówi to samo co pierwsze sekundy mowy, marnuje warstwę tekstu (≥ 60% słów wspólnych)."""
    tt = _tokeny(tytul)
    mowa = _tokeny(" ".join(str(w[2]) for w in words if od - 0.05 <= w[0] < od + okno))
    return len(tt) >= 2 and len(tt & mowa) / len(tt) >= 0.6


def dosun(t: float, words: list, koniec: bool, dur: float | None = None) -> float:
    """Granica w środku słowa → przerwa obok (ASR myli się o dziesiątki ms, model przy liczeniu czasów bardziej).
    Słowo zostaje w segmencie, gdy jest w nim jego środek (jak w `fragmenty`); zapas ciszy to połowa przerwy,
    najwyżej LEAD przed słowem i TAIL po nim. Granica w ciszy (albo dalej niż 1,5 s od przerwy) zostaje."""
    i = next((i for i, w in enumerate(words) if float(w[0]) + 0.01 < t < float(w[1]) - 0.01), None)
    if i is None:
        return t
    mid = (float(words[i][0]) + float(words[i][1])) / 2
    if not koniec:
        j = i if mid >= t else i + 1
        if j >= len(words):
            return t
        s = float(words[j][0])
        przerwa = s - (float(words[j - 1][1]) if j else 0.0)
        nowy = s - min(LEAD, max(0.0, przerwa) / 2)
    else:
        j = i if mid < t else i - 1
        if j < 0:
            return t
        e = float(words[j][1])
        przerwa = (float(words[j + 1][0]) if j + 1 < len(words) else (dur or e + 2 * TAIL)) - e
        nowy = e + min(TAIL, max(0.0, przerwa) / 2)
    if abs(nowy - t) > 1.5:
        return t
    return round(min(max(nowy, 0.0), dur or nowy), 3)


def granice(od: float, do: float, words: list, dur: float | None = None) -> tuple[float, float]:
    """Segment planu → segment z granicami w przerwach; dosunięcie, które zjadłoby segment, nie wchodzi."""
    a, b = dosun(od, words, False, dur), dosun(do, words, True, dur)
    return (a, b) if b - a >= 0.3 else (od, do)


def _wspolne(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(y1, y2) - max(x1, x2)) for x1, y1 in a for x2, y2 in b)


def sprawdz_plan(plan: dict) -> tuple[list[str], list[str], dict]:
    bledy, uwagi = [], []
    src = Path(str(plan.get("zrodlo") or ""))
    if not src.is_file():
        return [f"nie ma źródła: {src}"], [], {}
    info = ed.probe(src)
    dur = info.get("duration") or 0.0
    words = slowa_zrodla(src)
    rolki = plan.get("rolki") or []
    if (plan.get("styl") or {}).get("napisy") not in ("karaoke", "zwykle", None):
        bledy.append("styl.napisy: karaoke, zwykle albo null")
    if not 1 <= len(rolki) <= 12:
        bledy.append(f"rolek: {len(rolki)} (dozwolone 1–12)")
    slugi, czasy = set(), []
    for n, r in enumerate(rolki, 1):
        tag = f"rolka {n} ({r.get('slug')})"
        slug = str(r.get("slug") or "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", slug):
            bledy.append(f"{tag}: slug tylko a-z, 0-9 i „-”, do 40 znaków")
        if slug in slugi:
            bledy.append(f"{tag}: slug się powtarza")
        slugi.add(slug)
        fmt = r.get("format") or plan.get("format") or "9:16"
        if fmt not in FORMATY:
            bledy.append(f"{tag}: format {fmt!r} (dozwolone: {', '.join(FORMATY)})")
        segs = r.get("segmenty") or []
        if not 1 <= len(segs) <= 3:
            bledy.append(f"{tag}: segmentów {len(segs)} (dozwolone 1–3)")
        suma, prev, cz = 0.0, -1.0, []
        for s in segs:
            od, do = float(s.get("od", -1)), float(s.get("do", -1))
            if not 0 <= od < do <= dur + 0.05:
                bledy.append(f"{tag}: segment {od}–{do} poza nagraniem (0–{dur:.1f} s) albo od ≥ do")
                continue
            if od < prev:
                uwagi.append(f"{tag}: segmenty nie idą po kolei w źródle: upewnij się, że sens się nie zmienia")
            prev = do
            suma += do - od
            cz.append((od, do))
            for k in ("fx", "fy"):
                if k in s and not 0 <= float(s[k]) <= 1:
                    bledy.append(f"{tag}: {k}={s[k]} (0–1)")
            if "zoom" in s and not 1 <= float(s["zoom"]) <= 3:
                bledy.append(f"{tag}: zoom={s['zoom']} (1–3)")
            for t, gdzie in ((od, "początek"), (do, "koniec")):
                w = next((w for w in words if w[0] + 0.05 < t < w[1] - 0.05), None)
                if w:
                    nowy = dosun(t, words, gdzie == "koniec", dur)
                    dalej = (f": zbuduj dosunie granicę do przerwy, {nowy:.2f} s" if nowy != t
                             else ": przesuń granicę do przerwy między słowami")
                    uwagi.append(f"{tag}: {gdzie} {t:.2f} s tnie słowo „{w[2]}” ({w[0]:.2f}–{w[1]:.2f}){dalej}")
        czasy.append((n, cz))
        if segs and not bledy:
            if not 8 <= suma <= 90:
                bledy.append(f"{tag}: długość {suma:.1f} s (dozwolone 8–90, najlepiej 20–60)")
            elif not 20 <= suma <= 60:
                uwagi.append(f"{tag}: długość {suma:.1f} s poza 20–60 s")
            s0 = segs[0]
            start = " ".join(str(w[2]) for w in words if float(s0["od"]) - 0.05 <= w[0] < float(s0["do"]))[:40].lower()
            if start.startswith(ZLE_STARTY):
                uwagi.append(f"{tag}: zaczyna się od „{start[:20]}…”: hook powinien być pierwszym zdaniem")
        tytul = str(r.get("tytul") or "")
        if segs and not bledy and tytul and powtarza_mowe(tytul, words, float(segs[0]["od"])):
            uwagi.append(f"{tag}: tytuł powtarza pierwsze zdanie mówione: tekst na ekranie ma dokładać stawkę "
                         "albo wywołać odbiorcę (skill hooki)")
        if len(tytul) > 60:
            bledy.append(f"{tag}: tytuł ma {len(tytul)} znaków (do 60)")
        elif len(tytul.split()) > 7:
            uwagi.append(f"{tag}: tytuł ma {len(tytul.split())} słów (na ekran najlepiej ≤ 6)")
        oc = r.get("oceny") or {}
        if oc:
            sr = sum(float(v) for v in oc.values()) / len(oc)
            if sr < 7 or float(oc.get("hook", 10)) < 7:
                uwagi.append(f"{tag}: oceny poniżej progu (średnia {sr:.1f}, hook {oc.get('hook')}): master prompt mówi ≥ 7")
    # wspólny materiał: dwie rolki z tego samego fragmentu to jedna rolka dwa razy (chyba że świadome wersje A/B)
    for i, (na, a) in enumerate(czasy):
        for nb, b in czasy[i + 1:]:
            krotsza = min(sum(y - x for x, y in a), sum(y - x for x, y in b))
            if a and b and krotsza > 0 and (w := _wspolne(a, b) / krotsza) > WSPOLNE:
                uwagi.append(f"rolki {na} i {nb} dzielą {w:.0%} materiału źródła (master prompt: najwyżej ~20%): "
                             "zostaw mocniejszą albo napisz w KANDYDACI.md, że to wersje A/B")
    # pokrycie: długie nagranie, a wszystkie rolki z jednej połowy → okna drugiej połowy zostały nieocenione
    konce = [y for _, cz in czasy for _, y in cz]
    poczatki = [x for _, cz in czasy for x, _ in cz]
    if dur >= 600 and len(czasy) >= 3 and konce:
        polowa = "pierwszej" if max(konce) <= dur / 2 else "drugiej" if min(poczatki) >= dur / 2 else ""
        if polowa:
            uwagi.append(f"wszystkie rolki z {polowa} połowy nagrania: oceń okna z drugiej części (transkrypcja.txt, "
                         "„## Okno N”) i weź z niej rolkę, jeśli któreś ma ocenę jak wybrane")
    return bledy, uwagi, {"src": src, "dur": dur, "words": words, "info": info}


def cmd_sprawdz(a) -> int:
    bledy, uwagi, _ = sprawdz_plan(wczytaj_plan(Path(a.plan)))
    for u in uwagi:
        print(f"  ⚠ {u}")
    for b in bledy:
        print(f"  ✗ {b}")
    print(f"Plan: {len(bledy)} błędów, {len(uwagi)} uwag")
    return 1 if bledy else 0


# ---------------------------------------------------------------- zbuduj

def fragmenty(od: float, do: float, words: list, prog: float | None, bez_wtracen: bool) -> list[tuple[float, float]]:
    """Segment źródła → kawałki bez pauz dłuższych niż `prog` (zostaje oddech) i bez „yyy”. Czasy źródła."""
    ws = [w for w in words if od <= (w[0] + w[1]) / 2 < do and not (bez_wtracen and ed.is_filler(str(w[2])))]
    if not prog or not ws:
        return [(od, do)]
    out = [[max(od, ws[0][0] - PRZED), ws[0][1]]]
    for w in ws[1:]:
        if w[0] - out[-1][1] > prog:
            out[-1][1] = min(do, out[-1][1] + ODDECH / 2)
            out.append([max(od, w[0] - ODDECH / 2), w[1]])
        else:
            out[-1][1] = w[1]
    out[-1][1] = min(do, out[-1][1] + PO)
    # bardzo krótkie kawałki doklejamy do sąsiada (migotanie obrazu)
    merged: list[list[float]] = []
    for a, b in out:
        if merged and (b - a < 0.35 or a - merged[-1][1] < 0.05):
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in merged]


# ---------------------------------------------------------------- kadr na twarz (twarze.py)

def twarze_zrodla(src: Path, odcinki: list[tuple[float, float]]) -> dict | None:
    """twarze.py Pythonem narzędzi (onnxruntime z obrazu); błąd albo brak modelu = None i kadr z planu albo środek."""
    if not odcinki:
        return None
    py = "/opt/jarvo/venv/bin/python" if Path("/opt/jarvo/venv/bin/python").exists() else sys.executable
    arg = ",".join(f"{a:.3f}-{b:.3f}" for a, b in odcinki)
    try:
        r = subprocess.run([py, str(HERE / "twarze.py"), "wykryj", str(src), "--odcinki", arg], capture_output=True,
                           text=True, timeout=3600)
        if r.returncode == 0:
            return json.loads(r.stdout)
        powod = (r.stderr or r.stdout).strip()[-240:]
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        powod = str(exc)
    print(f"uwaga: wykrywanie twarzy niedostępne ({powod}); kadr z planu albo środek", file=sys.stderr)
    return None


def _srodek(f: list) -> tuple[float, float]:
    return (f[0] + f[2]) / 2, (f[1] + f[3]) / 2


def ta_sama(a: list, b: list) -> bool:
    """Ta sama twarz w dwóch próbkach: środki bliżej niż 0,6 szerokości większej z nich."""
    (ax, ay), (bx, by) = _srodek(a), _srodek(b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 < 0.6 * max(a[2] - a[0], b[2] - b[0])


def sledz(probki: list) -> list[tuple[float, list | None, int]]:
    """Twarz kadru w każdej próbce (za SpeakerTracker z openshorts): największa, a obecna z bonusem ×3; inna twarz
    (albo ta sama po skoku, np. zmiana ujęcia) przejmuje kadr dopiero po ZMIANA próbkach z rzędu, od pierwszej
    z nich. Próbka bez twarzy trzyma poprzednią. Wynik: (chwila, twarz, numer twarzy kadru)."""
    out: list[list] = []
    cur, kand, od, n = None, None, 0, 0
    for t, twarze in probki:
        if not twarze:
            out.append([t, cur, n])
            continue
        best = max(twarze, key=lambda f: (f[2] - f[0]) * (f[3] - f[1]) * (BONUS if cur and ta_sama(f, cur) else 1))
        if cur is None or ta_sama(best, cur):
            cur, kand = best, None
        else:
            if not (kand and ta_sama(best, kand)):
                od = len(out)
            kand = best
            if len(out) + 1 - od >= ZMIANA:
                cur, kand, n = best, None, n + 1
                for k in range(od, len(out)):          # zmiana od pierwszej próbki nowej twarzy
                    out[k][1] = next((f for f in probki[k][1] if ta_sama(f, best)), best)
                    out[k][2] = n
            else:
                cur = next((f for f in twarze if ta_sama(f, cur)), cur)
        out.append([t, cur, n])
    return [(t, f, k) for t, f, k in out]


def ustawienia(slad: list, szer: float) -> list[dict]:
    """Ślad twarzy (sledz) → kolejne ustawienia kadru {od, x, y} (środek twarzy 0–1 źródła). Nowe ustawienie, gdy
    kadr przeszedł na inną twarz albo twarz odeszła o > ODEJSCIE szerokości kadru na ZMIANA próbek (za
    SmoothedCameraman: mały ruch kadr ignoruje, duży musi się potwierdzić)."""
    out: list[dict] = []
    xs: list[float] = []
    ys: list[float] = []
    ost, daleko = None, []
    for t, f, nr in slad:
        if f is None:
            continue
        x, y = _srodek(f)
        if out and nr != ost:
            out.append({"od": t, "x": x, "y": y})
            xs, ys, daleko = [x], [y], []
        elif out and abs(x - sorted(xs)[len(xs) // 2]) > ODEJSCIE * szer:
            daleko.append((t, x, y))
            if len(daleko) >= ZMIANA:
                out.append({"od": daleko[0][0], "x": x, "y": y})
                xs, ys, daleko = [d[1] for d in daleko], [d[2] for d in daleko], []
        else:
            if not out:
                out.append({"od": t, "x": x, "y": y})
            xs.append(x)
            ys.append(y)
            daleko = []
        ost = nr
        out[-1]["x"], out[-1]["y"] = sorted(xs)[len(xs) // 2], sorted(ys)[len(ys) // 2]
    if out:
        out[0]["od"] = slad[0][0]
    return out


def ogniskowa(x: float, y: float, W: int, H: int, zoom: float, sw: float, sh: float) -> tuple[float, float]:
    """Środek twarzy (0–1 źródła) → fx, fy klipu `cover` (edytor.cover_filter): twarz na środku w poziomie
    i na KADR_Y wysokości kadru, o ile kadr nie wyjdzie poza obraz."""
    k = max(W * zoom / sw, H * zoom / sh)
    iw, ih = sw * k, sh * k
    fx = (x * iw - W / 2) / (iw - W) if iw - W > 1 else 0.5
    fy = (y * ih - KADR_Y * H) / (ih - H) if ih - H > 1 else 0.5
    return round(min(1.0, max(0.0, fx)), 3), round(min(1.0, max(0.0, fy)), 3)


def podziel(a: float, b: float, ust: list[dict], words: list) -> list[tuple[float, float, dict | None]]:
    """Kawałek źródła → części według ustawień kadru; podział w przerwie między słowami najbliżej zmiany (±0,75 s),
    części krótsze niż 0,8 s doklejone do sąsiada."""
    if not ust:
        return [(a, b, None)]
    tniemy = [a]
    for u in ust[1:]:
        if a + 0.8 <= u["od"] <= b - 0.8:
            luki = [(float(w1[1]) + float(w2[0])) / 2 for w1, w2 in zip(words, words[1:])
                    if abs((float(w1[1]) + float(w2[0])) / 2 - u["od"]) <= 0.75 and a + 0.8 <= float(w1[1]) <= b - 0.8]
            t = min(luki, key=lambda g: abs(g - u["od"])) if luki else u["od"]
            if t - tniemy[-1] >= 0.8:
                tniemy.append(round(t, 3))
    tniemy.append(b)
    wybierz = lambda t0, t1: max((u for u in ust if u["od"] <= (t0 + t1) / 2), key=lambda u: u["od"], default=ust[0])  # noqa: E731
    return [(t0, t1, wybierz(t0, t1)) for t0, t1 in zip(tniemy, tniemy[1:])]


def projekt_rolki(plan: dict, r: dict, src: Path, words: list, info: dict, twarze: dict | None = None) -> dict:
    st = plan["styl"]
    fmt = r.get("format") or plan.get("format") or "9:16"
    W, H = FORMATY[fmt]
    pion = fmt == "9:16"
    # poziome źródło w pionowym kadrze (i odwrotnie) → wypełnij z punktem skupienia; ten sam kształt → też cover
    sw = float((info or {}).get("w") or (twarze or {}).get("w") or 0)
    sh = float((info or {}).get("h") or (twarze or {}).get("h") or 0)
    clips, k, gr, kadr = [], 0, [], []
    for s in r["segmenty"]:
        od, do = granice(float(s["od"]), float(s["do"]), words, (info or {}).get("duration"))
        gr.append([od, do])
        auto = auto_kadr(st, s) and sw and sh
        ust = ustawienia(sledz([p for p in (twarze or {}).get("probki") or [] if od - 0.01 <= p[0] <= do + 0.01]),
                         min(1.0, (W / H) / (sw / sh))) if auto else []
        kadr.append("plan" if not auto_kadr(st, s) else "twarz" if ust else "srodek")
        for a0, b0 in fragmenty(od, do, words, st.get("tnij_pauzy"), st.get("bez_wtracen", True)):
            for a, b, u in podziel(a0, b0, ust, words):
                zoom = float(s.get("zoom", 1.0))
                if st.get("punch") and k % 2 == 1:
                    zoom = min(3.0, zoom * PUNCH)
                fx, fy = (ogniskowa(u["x"], u["y"], W, H, zoom, sw, sh) if u
                          else (float(s.get("fx", 0.5)), float(s.get("fy", 0.4 if pion else 0.5))))
                clips.append({"id": pr.new_id("c"), "src": str(src), "kind": "video", "in": a, "out": b, "speed": 1,
                              "volume": 1, "muted": False, "fit": "cover", "fx": fx, "fy": fy, "zoom": round(zoom, 3)})
                k += 1
    proj = {"version": 1, "format": fmt, "canvas": {"w": W, "h": H, "fps": FPS}, "clips": clips, "texts": [], "audio": [],
            "clipmaker": {"slug": r["slug"], "segmenty": r["segmenty"], "granice": gr, "kadr": kadr, "zrodlo": str(src)}}
    total = pr.total(proj)
    # napisy karaoke: krótkie linie (2–4 słowa w pionie), nad strefą przycisków platform
    look = {**pr.CAP_DEFAULT, "size": 76 if pion else 60, **(pr.PION if pion else {"y": 0.86, "maxw": 0.8}),
            "style": "outline", "bold": True}
    if st.get("napisy") == "karaoke":
        look["hl"] = st.get("hl") or HL
    if st.get("napisy"):
        lines = ed.lines_from_words(pr.timeline_words(proj), max_chars=18 if pion else 30, max_gap=0.5, max_dur=2.6)
        for ln in lines:
            if ln["start"] >= total:
                continue
            proj["texts"].append({**look, "id": pr.new_id("t"), "cap": True, "start": ln["start"],
                                  "end": min(ln["end"], total), "text": ln["text"],
                                  **({"words": ln["words"]} if look.get("hl") and ln.get("words") else {})})
    if st.get("tytul") and r.get("tytul"):
        proj["texts"].append({**pr.TEXT_DEFAULT, "id": pr.new_id("t"), "start": 0.0, "end": min(float(st.get("tytul_s") or 3), total),
                              "text": str(r["tytul"]), "style": "box", "color": "#111111", "bg": st.get("hl") or HL,
                              "y": 0.14 if pion else 0.12, "size": 78 if pion else 64, "maxw": 0.84,
                              "font": "'Bricolage Grotesque', system-ui, sans-serif"})
    if st.get("muzyka"):
        m = Path(str(st["muzyka"]))
        if m.is_file():
            md = ed.probe(m).get("duration") or total
            proj["audio"].append({"id": pr.new_id("a"), "src": str(m.resolve()), "start": 0.0, "in": 0.0,
                                  "out": min(md, total), "volume": float(st.get("muzyka_glosnosc") or 0.12)})
    return proj


def glosnosc_zrodla(src: Path, odcinki: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Głośność zintegrowana (LUFS) i szczyt prawdziwy (dBFS) kawałków źródła, które trafiają do rolki, razem
    (ebur128 po aselect: wycięte pauzy i wtrącenia nie liczą się do szczytu; cisza odpada bramką pomiaru).
    Bez 30 ms na brzegach kawałka: tam eksport wycisza cięcie (ciche cięcia), więc trzask na styku nie gra.
    Dźwięk idzie przez tę samą zamianę na stereo 48 kHz co eksport edytora (szczyt mono spada tam o 3 dB)."""
    odcinki = [(a + 0.03, b - 0.03) if b - a > 0.2 else (a, b) for a, b in odcinki]
    if not odcinki:
        return None
    t0, t1 = min(a for a, _ in odcinki), max(b for _, b in odcinki)
    wybor = "+".join(f"between(t\\,{a - t0:.3f}\\,{b - t0:.3f})" for a, b in odcinki)
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(src),
           "-vn", "-af", f"aselect={wybor},asetpts=N/SR/TB,aresample=48000,"   # jak eksport: mono → stereo −3 dB
           "aformat=sample_fmts=fltp:channel_layouts=stereo,ebur128=peak=true", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except OSError:
        return None
    summary = r.stderr[r.stderr.rfind("Summary:"):]
    i, pk = re.search(r"I:\s+(-?[\d.]+) LUFS", summary), re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    if r.returncode or not i or float(i.group(1)) < -69:
        return None
    return float(i.group(1)), float(pk.group(1)) if pk else 0.0


def wzmocnienie(lufs: float, szczyt: float) -> float:
    """Głośność klipów (0,25–2, jak w edytorze), która daje LUFS bez wyjścia szczytu ponad SZCZYT; ±1 dB zostaje 1."""
    db = min(LUFS - lufs, SZCZYT - szczyt, 20 * math.log10(2))
    return 1.0 if abs(db) < 1 else round(min(2.0, max(0.25, 10 ** (db / 20))), 3)


def auto_kadr(st: dict, s: dict) -> bool:
    """Kadr z twarzy, gdy plan nie podaje fx ani fy segmentu (i styl go nie wyłącza)."""
    return bool(st.get("kadr_auto", True)) and "fx" not in s and "fy" not in s


def odcinki_twarzy(plan: dict, words: list, info: dict, tylko: str | None = None) -> list[tuple[float, float]]:
    """Odcinki źródła, w których trzeba znaleźć twarze: segmenty bez fx/fy, gdy kadr ma inne proporcje niż źródło."""
    sw, sh = float(info.get("w") or 0), float(info.get("h") or 0)
    out = []
    for r in plan["rolki"]:
        W, H = FORMATY[r.get("format") or plan.get("format") or "9:16"]
        if (tylko and r["slug"] != tylko) or not info.get("video") or not sw or not sh or abs(W / H - sw / sh) < 0.05:
            continue
        out += [granice(float(s["od"]), float(s["do"]), words, info.get("duration"))
                for s in r["segmenty"] if auto_kadr(plan["styl"], s)]
    return out


def podpis(proj: dict) -> str:
    """Odcisk treści projektu (klipy, napisy, audio, kadr): po nim poznajemy, czy ktoś edytował rolkę w HQ."""
    import hashlib
    tresc = {k: proj.get(k) for k in ("canvas", "clips", "texts", "audio")}
    return hashlib.sha1(json.dumps(tresc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def edytowana_recznie(film: Path) -> bool:
    """Projekt rolki zmieniony po zbudowaniu (albo bez podpisu): ponowne zbuduj nie może go po cichu nadpisać."""
    pp = ed.project_path(film)
    if not pp.is_file():
        return False
    try:
        proj = json.loads(pp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return (proj.get("clipmaker") or {}).get("podpis") != podpis(proj)


def ensure_render_env() -> None:
    """Render napisów potrzebuje playwright (jak projekt.py render): w razie potrzeby uruchom się w venv narzędzi."""
    import narzedzia as nz
    nz.wymagaj_playwright(__file__, "JARVO_KLIPY_REEXEC", "render napisów potrzebuje przeglądarki",
                          " (albo zbuduj z --bez-renderu i wyrenderuj w edytorze HQ)")


def cmd_zbuduj(a) -> int:
    plan = wczytaj_plan(Path(a.plan))
    bledy, uwagi, ctx = sprawdz_plan(plan)
    for u in uwagi:
        print(f"  ⚠ {u}")
    if bledy:
        for b in bledy:
            print(f"  ✗ {b}")
        raise SystemExit("plan ma błędy (klipy.py sprawdz): popraw plan.json")
    if not a.bez_renderu:
        ensure_render_env()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    odc = odcinki_twarzy(plan, ctx["words"], ctx["info"], a.tylko)
    if odc:
        print(f"▶ twarze (YuNet): {len(odc)} odcinków, {sum(b - a for a, b in odc):.0f} s źródła", flush=True)
    twarze = twarze_zrodla(ctx["src"], odc)
    wyniki = []
    for n, r in enumerate(plan["rolki"], 1):
        if a.tylko and r["slug"] != a.tylko:
            continue
        film = out / f"klip-{n}-{r['slug']}.mp4"
        if edytowana_recznie(film) and not a.nadpisz:
            raise SystemExit(f"{film.name}: projekt zmieniono po zbudowaniu (np. w edytorze HQ). Poprawiaj go przez "
                             "projekt.py (kadr, usun, napisy…) albo zbuduj z --nadpisz, jeśli te zmiany mają zniknąć")
        proj = projekt_rolki(plan, r, ctx["src"], ctx["words"], ctx["info"], twarze)
        gl = glosnosc_zrodla(ctx["src"], [(c["in"], c["out"]) for c in proj["clips"]]) if ctx["info"].get("audio") else None
        if gl:
            v = wzmocnienie(*gl)
            for c in proj["clips"]:
                c["volume"] = v
            proj["clipmaker"]["glosnosc"] = {"lufs": gl[0], "szczyt": gl[1], "volume": v}
        ed.normalize(proj, pr.resolve)                     # ta sama walidacja co eksport z edytora
        proj["clipmaker"]["podpis"] = podpis(proj)
        pr.save(film, proj)
        dl = pr.total(proj)
        print(f"▶ rolka {n}: {film.name} · {len(proj['clips'])} ujęć · {dl:.1f} s · {sum(1 for t in proj['texts'] if t.get('cap'))} napisów"
              f" · kadr: {', '.join(proj['clipmaker']['kadr'])}"
              + (f" · głośność {gl[0]:.1f} LUFS → ×{proj['clipmaker']['glosnosc']['volume']}" if gl else ""), flush=True)
        if not a.bez_renderu:
            if pr.cmd_render(film, argparse.Namespace(out=str(film))) != 0:
                raise SystemExit(f"render {film.name} nie wyszedł")
        wyniki.append({"n": n, "r": r, "film": film, "dl": dl, "ujecia": len(proj["clips"]),
                       "granice": proj["clipmaker"]["granice"]})
    pisz_klipy_md(plan, wyniki, out, ctx)
    print(f"✓ {out / 'KLIPY.md'}")
    return 0


def pisz_klipy_md(plan: dict, wyniki: list[dict], out: Path, ctx: dict) -> None:
    src = ctx["src"]
    lines = [f"# Rolki z nagrania {src.name}", "",
             f"Źródło: `{src}` ({mmss(ctx['dur'])}). Każdą rolkę otwierasz w HQ („✎ Edytuj”): cięcia, kadr, napisy i tytuł "
             "są edytowalne, eksport robi nową wersję obok.", "",
             "| # | Rolka | Długość | Fragmenty źródła | Ocena | Plik |", "|---|---|---|---|---|---|"]
    for w in wyniki:
        r, oc = w["r"], w["r"].get("oceny") or {}
        sr = f"{sum(float(v) for v in oc.values()) / len(oc):.1f}" if oc else "–"
        segs = ", ".join(f"{mmss(od)}–{mmss(do)}" for od, do in w["granice"])     # po dosunięciu do przerw
        lines.append(f"| {w['n']} | {r.get('tytul') or r['slug']} | {w['dl']:.0f} s | {segs} | {sr} | `{w['film'].name}` |")
    for w in wyniki:
        r = w["r"]
        lines += ["", f"## {w['n']}. {r.get('tytul') or r['slug']}", "",
                  f"- plik: `{w['film'].name}` (projekt: `{ed.project_path(w['film']).name}`), {w['ujecia']} ujęć, {w['dl']:.1f} s",
                  f"- hook: {r.get('taktyka') or '–'} (taktyka), dlaczego: {r.get('dlaczego') or '–'}",
                  f"- opis: {r.get('opis') or '–'}",
                  f"- hashtagi: {' '.join(r.get('hashtagi') or []) or '–'}"]
        if r.get("oceny"):
            lines.append("- oceny: " + ", ".join(f"{k} {v}" for k, v in r["oceny"].items()))
    (out / "KLIPY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("przygotuj", help="mowa, cięcia ujęć, arkusze klatek, transkrypcja.txt")
    p.add_argument("nagranie")
    p.add_argument("-o", "--out", default="out/wideo/klipy")
    p.add_argument("--od-nowa", action="store_true", help="rozpoznaj mowę jeszcze raz (zamiast wziąć .mowa.json)")
    p.set_defaults(fn=cmd_przygotuj)
    p = sub.add_parser("sprawdz", help="walidacja plan.json")
    p.add_argument("plan")
    p.set_defaults(fn=cmd_sprawdz)
    p = sub.add_parser("zbuduj", help="plan.json → projekty edytora + MP4 + KLIPY.md")
    p.add_argument("plan")
    p.add_argument("-o", "--out", default="out/wideo/klipy")
    p.add_argument("--bez-renderu", action="store_true", help="tylko projekty (render później: projekt.py render albo edytor HQ)")
    p.add_argument("--tylko", help="zbuduj tylko rolkę o tym slugu (poprawka jednej rolki)")
    p.add_argument("--nadpisz", action="store_true", help="nadpisz rolkę zmienioną w edytorze HQ (zmiany człowieka znikną)")
    p.set_defaults(fn=cmd_zbuduj)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
