#!/usr/bin/env python3
"""Pomiar animacji HTML z DOM i klatek (dla `html_wideo.py pomiar` i `aktualny`): twarde ustalenia przed renderem.

Pomysł z Remocn Studio (`design_check`, MIT): zamiast oceniać piksele gotowego MP4, w każdej próbce czasu czytamy
z przeglądarki teksty (widoczna część, granice glifów, krycie, kolor, rozmiar) i robimy małą klatkę. Z tego:

    tekst_poza_kadrem     tekst w pełni widoczny wychodzi poza kadr (≥ 0,25 s)                     błąd
    czas_czytania         tekst widoczny krócej, niż trzeba na przeczytanie (pl: 0,4 s + 3 słowa/s)  błąd / ostrzeżenie
    strefa_platformy      tekst pod interfejsem platformy (9:16: dół 24%, góra 14%, prawy pasek 16%) błąd przy --platforma
    kontrast              tekst a tło za nim poniżej WCAG (4,5:1; duży tekst 3:1)                  błąd
    czcionka_zastepcza    krój z CSS niedostępny: render pokaże inny niż projekt                   błąd
    czarna_przerwa        czarna klatka między scenami (nie na początku i końcu)                   błąd
    martwy_odcinek        obraz bez zmiany dłużej niż 3 s (koniec: 4 s)                             ostrzeżenie
    monotonny_rytm        zmiany w równych odstępach bez akcentu                                    ostrzeżenie
    zasob / blad_js       plik nie wczytał się / błąd JavaScript na stronie                         błąd

Raport ma odcisk źródeł (pliki animacji + ustawienia pomiaru): zmiana czegokolwiek = raport nieaktualny. Film z kodu
HTML oddajesz tylko z pełnym (`--tryb pelny`) i aktualnym raportem bez błędów; świadomy wyjątek (`--wyjatek`) ma powód.
Tekst rysowany na kanwie/WebGL animacja podaje sama: `window.__teksty()` → [{tekst, x, y, w, h, kolor, rozmiar, krycie,
widoczny?, id?}] dla bieżącej klatki (kontrakt HTML). Ograniczenia: maski (overflow: hidden) liczone jako widoczne;
tło pod tekstem to mediana pikseli wokół glifów.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import statistics
from pathlib import Path

STATYKA_PROG = 0.06             # największa zmiana piksela (miniatura 96 px) poniżej = obraz stoi
CZERN_PROG = 0.035              # średnia jasność poniżej = czarna klatka
PLATFORMY_PION = {"tiktok", "ig-reel", "reels", "ig-story", "yt-shorts", "shorts", "fb-reel"}
GENERYCZNE = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif",
              "ui-monospace", "ui-rounded", "emoji", "math", "fangsong", "inherit", "initial", "-apple-system",
              "blinkmacsystemfont"}
POMIN_W_ODCISKU = {"out", "node_modules", ".git", "__pycache__", "klatki", "render"}
WYJSCIA_EXT = {".mp4", ".mov", ".webm", ".gif", ".mkv"}

# Sonda w przeglądarce: bloki tekstu (najbliższy przodek blokowy węzłów tekstowych), widoczna część tekstu (węzły
# z kryciem ≥ 0,5), granice glifów (Range.getClientRects), krycie, kolor, cień/obrys, rozmiar i krój.
SONDA_JS = r"""() => {
  const W = innerWidth, H = innerHeight;
  const ids = window.__jarvoPomiar || (window.__jarvoPomiar = { m: new WeakMap(), n: 0 });
  const blocks = new Map();
  const opac = (el) => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
    const s = getComputedStyle(e); if (s.display === "none" || s.visibility === "hidden") return 0; o *= parseFloat(s.opacity || "1"); } return o; };
  const blockOf = (el) => { for (let e = el; e && e !== document.body; e = e.parentElement) {
    const d = getComputedStyle(e).display; if (!/^inline/.test(d) && d !== "contents") return e; } return document.body; };
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    const txt = n.nodeValue.replace(/\s+/g, " ");
    if (!txt.trim() || !n.parentElement || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(n.parentElement.tagName)) continue;
    const b = blockOf(n.parentElement);
    if (!ids.m.has(b)) ids.m.set(b, ++ids.n);
    const id = ids.m.get(b);
    const r = document.createRange(); r.selectNodeContents(n);
    const rects = [...r.getClientRects()].filter((q) => q.width > 0.5 && q.height > 0.5);
    const a = opac(n.parentElement);
    let x = blocks.get(id);
    if (!x) { const s = getComputedStyle(n.parentElement);
      x = { id, full: "", seen: "", a: 0, x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9, color: s.color, size: parseFloat(s.fontSize),
            weight: parseInt(s.fontWeight, 10) || 400, family: s.fontFamily, shadow: s.textShadow !== "none" ? s.textShadow : "",
            stroke: parseFloat(s.webkitTextStrokeWidth || "0") > 0 ? s.webkitTextStrokeColor : "" };
      blocks.set(id, x); }
    x.full += txt;
    if (a >= 0.5 && rects.length) {
      x.seen += txt; x.a = Math.max(x.a, a);
      for (const q of rects) { x.x0 = Math.min(x.x0, q.left); x.y0 = Math.min(x.y0, q.top); x.x1 = Math.max(x.x1, q.right); x.y1 = Math.max(x.y1, q.bottom); }
    }
  }
  const teksty = [...blocks.values()].filter((x) => x.seen.trim()).map((x) => ({ ...x, full: x.full.trim(), seen: x.seen.trim() }));
  // tekst rysowany na kanwie/WebGL: animacja podaje go sama (kontrakt HTML, window.__teksty)
  if (typeof window.__teksty === "function") {
    try {
      for (const q of (window.__teksty() || [])) {
        if (!q || !String(q.tekst || "").trim() || !(q.w > 0) || !(q.h > 0)) continue;
        const full = String(q.tekst).trim();
        teksty.push({ id: "c:" + (q.id || full), full, seen: String(q.widoczny ?? full).trim(), a: q.krycie ?? 1,
          x0: q.x, y0: q.y, x1: q.x + q.w, y1: q.y + q.h, color: q.kolor || "rgb(255, 255, 255)", size: q.rozmiar || 40,
          weight: q.waga || 700, family: q.font || "system-ui", shadow: q.cien || "", stroke: q.obrys || "" });
      }
    } catch (e) { /* błąd w __teksty nie zatrzymuje pomiaru; zobaczy go blad_js w konsoli */ }
  }
  return { W, H, teksty };
}"""

# Krój dostępny? Szerokość próbki w kroju z rezerwą A i B; ta sama co samej rezerwy = przeglądarka go nie ma.
CZCIONKI_JS = r"""(rodziny) => {
  const c = document.createElement("canvas").getContext("2d"), probka = "Zażółć gęślą jaźń 0123 WMwmil";
  const w = (f) => { c.font = `48px ${f}`; return c.measureText(probka).width; };
  const bledne = [...(document.fonts || [])].filter((f) => f.status === "error").map((f) => f.family.replace(/["']/g, ""));
  return { brak: rodziny.filter((r) => w(`"${r}", monospace`) === w("monospace") && w(`"${r}", serif`) === w("serif")), bledne };
}"""


# ---------------------------------------------------------------- czyste funkcje

def czas_czytania(tekst: str, jezyk: str = "pl") -> float:
    """Sekundy potrzebne na przeczytanie tekstu na ekranie: 0,4 s reakcji + słowa / tempo (pl 3, en 3,3 słowa/s)."""
    slowa = len(re.findall(r"[\w\d]+(?:[-'’][\w\d]+)*", tekst))
    if not slowa:
        return 0.0
    tempo = 3.3 if jezyk.startswith("en") else 3.0
    return round(max(0.5 if slowa == 1 else 0.8, 0.4 + slowa / tempo), 2)


def kolor_css(s: str) -> tuple[float, float, float, float] | None:
    """rgb()/rgba() z getComputedStyle albo #rgb / #rrggbb / #rrggbbaa (kolory podane przez __teksty)."""
    h = re.fullmatch(r"\s*#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\s*", s or "")
    if h:
        x = h.group(1)
        x = "".join(c * 2 for c in x) if len(x) == 3 else x
        return (int(x[0:2], 16), int(x[2:4], 16), int(x[4:6], 16), int(x[6:8], 16) / 255 if len(x) == 8 else 1.0)
    m = re.search(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?", s or "")
    if not m:
        return None
    a = m.group(4)
    alfa = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
    return float(m.group(1)), float(m.group(2)), float(m.group(3)), alfa


def luminancja(rgb) -> float:
    def k(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * k(r) + 0.7152 * k(g) + 0.0722 * k(b)


def kontrast(a, b) -> float:
    la, lb = sorted((luminancja(a), luminancja(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def nalozony(fg, bg) -> tuple[float, float, float]:
    """Kolor tekstu z kryciem (rgba) na tle."""
    a = fg[3] if len(fg) > 3 else 1.0
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))


def strefy(W: int, H: int, platforma: str | None) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Strefy interfejsu platformy (jak safe_margins w wideo_lib i arkusz qa_wideo): (nazwa, (x0, y0, x1, y1))."""
    if H > W or (platforma or "") in PLATFORMY_PION:
        return [("dół (opis, przyciski)", (0, H * 0.76, W, H)), ("góra (nazwa konta)", (0, 0, W, H * 0.14)),
                ("prawy pasek przycisków", (W * 0.84, H * 0.40, W, H))]
    return [("margines kadru", (0, 0, W, H * 0.08)), ("margines kadru", (0, H * 0.92, W, H)),
            ("margines kadru", (0, 0, W * 0.06, H)), ("margines kadru", (W * 0.94, 0, W, H))]


def _przeciecie(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def _ustalenie(kod, waga, opis, poprawka, t0, t1, **extra) -> dict:
    return {"kod": kod, "waga": waga, "opis": opis, "poprawka": poprawka, "od": round(t0, 2), "do": round(t1, 2), **extra}


def analiza(probki: list[dict], dlugosc: float, hz: float, platforma: str | None = None, jezyk: str = "pl",
            tla: dict | None = None) -> list[dict]:
    """Próbki [{t, W, H, teksty, luma, zmiana}] → ustalenia. `tla`: id tekstu → (kolor tła RGB, chwila) z klatek."""
    out: list[dict] = []
    if not probki:
        return out
    dt = 1.0 / hz
    W, H = probki[0]["W"], probki[0]["H"]
    zony = strefy(W, H, platforma)
    twarde_strefy = bool(platforma) or H > W
    # teksty: przebieg w czasie
    przebieg: dict[int, list[tuple[float, dict]]] = {}
    for p in probki:
        for x in p.get("teksty") or []:
            przebieg.setdefault(x["id"], []).append((p["t"], x))
    for tid, ciag in przebieg.items():
        pelny = max((x["full"] for _, x in ciag), key=len)
        krotki = pelny if len(pelny) <= 60 else pelny[:57] + "…"
        # czas czytania: chwile, gdy cały tekst jest odsłonięty i dobrze widoczny
        dostepny = sum(dt for _, x in ciag if x["a"] >= 0.6 and len(x["seen"]) >= len(pelny) * 0.98)
        potrzeba = czas_czytania(pelny, jezyk)
        t0, t1 = ciag[0][0], ciag[-1][0] + dt
        if potrzeba and dostepny < potrzeba:
            waga = "blad" if dostepny < potrzeba * 0.7 else "ostrz"
            out.append(_ustalenie("czas_czytania", waga, f"„{krotki}” czytelny {dostepny:.1f} s, potrzeba ok. {potrzeba:.1f} s",
                                  "pokaż tekst dłużej, odsłoń go wcześniej albo skróć", t0, t1, tekst=pelny,
                                  dostepny=round(dostepny, 2), potrzeba=potrzeba))
        # poza kadrem: w pełni widoczny tekst wystający poza kadr
        poza = [(t, x) for t, x in ciag if x["a"] >= 0.9 and (x["x0"] < -2 or x["y0"] < -2 or x["x1"] > W + 2 or x["y1"] > H + 2)]
        if len(poza) * dt >= 0.25:
            out.append(_ustalenie("tekst_poza_kadrem", "blad", f"„{krotki}” wychodzi poza kadr przez {len(poza) * dt:.1f} s",
                                  "zmniejsz tekst, złam linię albo przesuń go do środka", poza[0][0], poza[-1][0] + dt, tekst=pelny))
        # strefy platformy
        for nazwa, z in zony:
            pod = [(t, x) for t, x in ciag if x["a"] >= 0.6 and
                   _przeciecie((x["x0"], x["y0"], x["x1"], x["y1"]), z) > 0.15 * max(1.0, (x["x1"] - x["x0"]) * (x["y1"] - x["y0"]))]
            if len(pod) * dt >= 0.3:
                out.append(_ustalenie("strefa_platformy", "blad" if twarde_strefy else "ostrz",
                                      f"„{krotki}” w strefie: {nazwa} ({len(pod) * dt:.1f} s)",
                                      "przesuń tekst do bezpiecznego środka kadru (formaty-wideo)", pod[0][0], pod[-1][0] + dt,
                                      tekst=pelny, strefa=nazwa))
                break
        # kontrast z tłem zmierzonym na klatce
        if tla and tid in tla:
            bg, tk = tla[tid]
            x = next(x for t, x in ciag if t == tk) if any(t == tk for t, _ in ciag) else ciag[0][1]
            fg = kolor_css(x["color"])
            if fg:
                k = kontrast(nalozony(fg, bg), bg)
                for extra in (x.get("shadow"), x.get("stroke")):       # cień albo obrys daje własny kontrast
                    c = kolor_css(extra or "")
                    if c:
                        k = max(k, kontrast(nalozony(fg, bg), c[:3]))
                duzy = x["size"] >= 0.025 * H or (x["size"] >= 0.019 * H and x["weight"] >= 700)
                prog = 3.0 if duzy else 4.5
                if k < prog:
                    out.append(_ustalenie("kontrast", "blad", f"„{krotki}” kontrast {k}:1 (próg {prog}:1)",
                                          "ciemniejsze/jaśniejsze tło pod tekstem, obrys albo cień; kolory z brand kitu",
                                          tk, tk + dt, tekst=pelny, kontrast=k, prog=prog))
    # obraz: czarne przerwy, martwe odcinki, rytm
    n = len(probki)
    czarne = {i for i, p in enumerate(probki) if p.get("luma") is not None and p["luma"] < CZERN_PROG}
    jasne = [i for i, p in enumerate(probki) if p.get("luma") is not None and p["luma"] >= CZERN_PROG]
    i = jasne[0] + 1 if jasne else n
    while jasne and i < jasne[-1]:
        if i in czarne:
            j = i
            while j + 1 in czarne:
                j += 1
            out.append(_ustalenie("czarna_przerwa", "blad", f"czarny obraz między scenami ({(j - i + 1) * dt:.1f} s)",
                                  "przejście bez wygaszenia do czerni: wspólny obiekt, przenikanie albo cięcie",
                                  probki[i]["t"], probki[j]["t"] + dt))
            i = j + 1
        else:
            i += 1
    zmiany = [p.get("zmiana") for p in probki]
    ruch = [p.get("ruch", p.get("zmiana")) for p in probki]
    i = 1
    while i < n:
        if ruch[i] is not None and ruch[i] < STATYKA_PROG:
            j = i
            while j + 1 < n and ruch[j + 1] is not None and ruch[j + 1] < STATYKA_PROG:
                j += 1
            dl = (j - i + 2) * dt
            koniec = j >= n - 2
            if dl >= (4.0 if koniec else 3.0):
                out.append(_ustalenie("martwy_odcinek", "ostrz", f"obraz stoi {dl:.1f} s" + (" na końcu" if koniec else ""),
                                      "dodaj zmianę (tekst, ruch kamery, akcent) albo skróć", probki[i - 1]["t"], probki[j]["t"] + dt))
            i = j + 1
        else:
            i += 1
    znane = [z for z in zmiany if z is not None]
    if len(znane) > 20:
        prog = max(0.02, statistics.median(znane) * 3)
        szczyty = [probki[k]["t"] for k in range(1, n - 1) if zmiany[k] is not None and zmiany[k] >= prog
                   and zmiany[k] >= (zmiany[k - 1] or 0) and zmiany[k] >= (zmiany[k + 1] or 0)]
        odst = [b - a for a, b in zip(szczyty, szczyty[1:]) if b - a > dt * 1.5]
        if len(odst) >= 6 and statistics.mean(odst) > 0 and statistics.pstdev(odst) / statistics.mean(odst) < 0.12:
            out.append(_ustalenie("monotonny_rytm", "ostrz", f"{len(odst) + 1} zmian co ~{statistics.mean(odst):.1f} s, bez akcentu",
                                  "zróżnicuj długość ujęć: krótsze przy akcji, dłuższe przy puencie; jeden mocny akcent",
                                  szczyty[0], szczyty[-1]))
    return out


def tlo_wokol(jpg: bytes, bbox: tuple[float, float, float, float], skala: float = 1.0) -> tuple[float, float, float] | None:
    """Mediana kolorów w ramce 4 px wokół glifów (2 px odstępu): tło, na którym czyta się tekst."""
    from PIL import Image
    im = Image.open(io.BytesIO(jpg)).convert("RGB")
    x0, y0, x1, y1 = (int(round(v * skala)) for v in bbox)
    W, H = im.size
    px = []
    for (a, b, c, d) in ((x0 - 6, y0 - 6, x1 + 6, y0 - 2), (x0 - 6, y1 + 2, x1 + 6, y1 + 6),
                         (x0 - 6, y0 - 2, x0 - 2, y1 + 2), (x1 + 2, y0 - 2, x1 + 6, y1 + 2)):
        a, b, c, d = max(0, a), max(0, b), min(W, c), min(H, d)
        if c > a and d > b:
            px += list(im.crop((a, b, c, d)).getdata())
    if not px:
        return None
    return tuple(float(statistics.median(p[i] for p in px)) for i in range(3))


def luma_i_zmiana(jpg: bytes, poprzednia):
    """Średnia jasność (0–1) małej klatki, średnia i największa zmiana piksela względem poprzedniej (0–1)."""
    from PIL import Image
    im = Image.open(io.BytesIO(jpg)).convert("L")
    im = im.resize((96, max(1, round(96 * im.size[1] / im.size[0]))))
    data = list(im.getdata())
    luma = sum(data) / (255 * len(data))
    if poprzednia is None or len(poprzednia) != len(data):
        return luma, None, None, data
    roznice = [abs(a - b) for a, b in zip(data, poprzednia)]
    return luma, sum(roznice) / (255 * len(data)), max(roznice) / 255, data


def odcisk(anim: Path, ustawienia: dict) -> str:
    """Pliki animacji (katalog strony, bez wyjść i raportów) + ustawienia pomiaru → sha256."""
    h = hashlib.sha256()
    root = anim.resolve().parent
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or any(part in POMIN_W_ODCISKU for part in rel.parts[:-1]) or p.suffix.lower() in WYJSCIA_EXT \
                or re.match(r"pomiar.*\.(json|md)$", p.name) or p.stat().st_size > 50_000_000:
            continue
        h.update(str(rel).encode())
        h.update(hashlib.sha256(p.read_bytes()).digest())
    h.update(json.dumps(ustawienia, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()


def wyjatki(lista: list[str]) -> list[dict]:
    """`KOD[@fragment tekstu]=powód` → [{kod, tekst, powod}]; powód co najmniej 15 znaków."""
    out = []
    for w in lista or []:
        lewa, _, powod = w.partition("=")
        kod, _, tekst = lewa.partition("@")
        if len(powod.strip()) < 15:
            raise SystemExit(f"wyjątek {w!r}: podaj powód (co najmniej 15 znaków), np. czas_czytania@Logo=znak marki, nie do czytania")
        out.append({"kod": kod.strip(), "tekst": tekst.strip(), "powod": powod.strip()})
    return out


def zastosuj_wyjatki(ustalenia: list[dict], wyj: list[dict]) -> None:
    for u in ustalenia:
        for w in wyj:
            if u["kod"] == w["kod"] and (not w["tekst"] or w["tekst"].lower() in (u.get("tekst") or "").lower()):
                u["wyjatek"] = w["powod"]
                break


def werdykt(ustalenia: list[dict]) -> dict:
    bledy = [u for u in ustalenia if u["waga"] == "blad" and not u.get("wyjatek")]
    return {"bledy": len(bledy), "ostrzezenia": sum(1 for u in ustalenia if u["waga"] == "ostrz" and not u.get("wyjatek")),
            "wyjatki": sum(1 for u in ustalenia if u.get("wyjatek")), "ok": not bledy}


def aktualnosc(anim: Path, raport: dict) -> list[str]:
    """Powody, dla których raportu nie można użyć do oddania filmu (pusta lista = aktualny, pełny, bez błędów)."""
    powody = []
    if raport.get("odcisk") != odcisk(anim, raport.get("ustawienia") or {}):
        powody.append("pliki animacji albo ustawienia zmieniły się po pomiarze: zmierz ponownie")
    pok = raport.get("pokrycie") or {}
    if not pok.get("pelne"):
        powody.append(f"pomiar niepełny (tryb {pok.get('tryb', '?')}, {pok.get('hz', '?')} próbek/s): do oddania --tryb pelny")
    if not (raport.get("werdykt") or {}).get("ok"):
        powody.append(f"błędy bez wyjątku: {(raport.get('werdykt') or {}).get('bledy', '?')} (popraw albo opisz świadomy wyjątek)")
    return powody


def podsumowanie_md(raport: dict) -> str:
    w = raport["werdykt"]
    l = [f"# Pomiar animacji: {raport['plik']}", "",
         f"{'✓' if w['ok'] else '✗'} błędy {w['bledy']}, ostrzeżenia {w['ostrzezenia']}, wyjątki {w['wyjatki']} · "
         f"{raport['pokrycie']['probek']} próbek, {raport['pokrycie']['hz']:g}/s, tryb {raport['pokrycie']['tryb']}", ""]
    for u in sorted(raport["ustalenia"], key=lambda u: (u["waga"] != "blad", u["od"])):
        znak = "◇" if u.get("wyjatek") else ("✗" if u["waga"] == "blad" else "⚠")
        l.append(f"- {znak} {u['od']:.1f}–{u['do']:.1f} s `{u['kod']}`: {u['opis']} → {u['poprawka']}"
                 + (f" (wyjątek: {u['wyjatek']})" if u.get("wyjatek") else ""))
    if raport.get("czcionki_brak"):
        l.append(f"- kroje niedostępne: {', '.join(raport['czcionki_brak'])}")
    return "\n".join(l) + "\n"
