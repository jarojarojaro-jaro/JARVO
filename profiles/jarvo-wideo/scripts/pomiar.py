#!/usr/bin/env python3
"""Pomiar animacji HTML z DOM i klatek (dla `html_wideo.py pomiar` i `aktualny`): twarde ustalenia przed renderem.

Pomysł z Remocn Studio (`design_check`, MIT): zamiast oceniać piksele gotowego MP4, w każdej próbce czasu czytamy
z przeglądarki teksty (widoczna część, granice glifów, krycie, kolor, rozmiar) i robimy małą klatkę. Z tego:

    tekst_poza_kadrem     tekst w pełni widoczny wychodzi poza kadr (≥ 0,25 s)                     błąd
    czas_czytania         tekst widoczny krócej, niż trzeba na przeczytanie: poniżej 70% minimum     błąd
                          (pl: 0,4 s + 3 słowa/s), poniżej spokojnego czytania (znaki / 15 + 1,5 s)  ostrzeżenie
    strefa_platformy      tekst pod interfejsem platformy (9:16: wideo_lib.STREFY_UI, bez platformy TikTok)  błąd przy --platforma
    pas_napisow           tekst w pasie napisów lektora (wideo_lib.PAS_NAPISOW) ≥ 0,3 s: napisy go zakryją  błąd przy napisach
    napisy_na_sobie       dwa różne teksty nachodzą na siebie (≥ 30% mniejszego) ≥ 0,3 s            błąd
    kontrast              tekst a tło za nim poniżej WCAG (4,5:1; duży tekst 3:1)                  błąd
    czcionka_zastepcza    krój z CSS niedostępny: render pokaże inny niż projekt                   błąd
    czarna_przerwa        czarna klatka między scenami (nie na początku i końcu)                   błąd
    martwy_odcinek        obraz bez zmiany dłużej niż 3 s (koniec: 4 s)                             ostrzeżenie
    monotonny_rytm        zmiany w równych odstępach bez akcentu                                    ostrzeżenie
    pusta_scena           największy obiekt < 15% krótszego boku kadru dłużej niż 1,5 s             ostrzeżenie
    bez_oddechu           < 0,8 s spokoju przed przejściem do nowego ujęcia (ujęcie ≥ 2 s; wyjście   ostrzeżenie
                          i wejście do 1,2 s się nie liczą) albo koniec filmu stoi < 0,8 s (logo, puenta:
                          ≥ 1 s); film w pętli bez kontroli końca
    uderzenia_kadru       więcej niż 3 uderzenia całego kadru (błysk, wstrząs, pompa skali)         ostrzeżenie
    liczba_niepewna       liczba na ekranie (≥ 0,5 s) z listy niepewnych w fakty.json               błąd
    liczba_bez_zrodla     liczba na ekranie (≥ 0,5 s) bez pokrycia w fakty.json (oś, numer kroku:   ostrzeżenie
                          wyjątek z powodem); liczby 0–3 i klatki licznika w ruchu pomijane
    zasob / blad_js       plik nie wczytał się / błąd JavaScript na stronie                         błąd

Pas napisów sprawdzamy, gdy film dostanie napisy lektora (`html_wideo.py pomiar --napisy tak`; `auto`: obok strony
leży os_czasu.json, *.slowa.json, *.srt albo lektor*.wav; `gramatyka.py pomiar` zawsze). Nachodzące napisy (za qa.py
huashu-art-motion, MIT): ten sam tekst narysowany dwa razy (obrys, cień) to jeden napis, tekst w oknie z overflow
(licznik) się nie liczy; obrócone napisy mają prostokąt otaczający większy niż litery, więc fałszywy alarm sprawdzasz
na klatce i opisujesz wyjątkiem.
Liczby sprawdzamy, gdy obok strony albo katalog wyżej leży fakty.json (brief Sherlocka) albo podano `--fakty`.
Raport ma odcisk źródeł (pliki animacji, ustawienia pomiaru i fakty.json): zmiana czegokolwiek = raport nieaktualny. Film z kodu
HTML oddajesz tylko z pełnym (`--tryb pelny`) i aktualnym raportem bez błędów; świadomy wyjątek (`--wyjatek`) ma powód.
Tekst rysowany na kanwie/WebGL animacja podaje sama: `window.__teksty()` → [{tekst, x, y, w, h, kolor, rozmiar, krycie,
widoczny?, id?}] dla bieżącej klatki (kontrakt HTML). Okno z overflow (np. licznik bębnowy) przycina tekst: liczy się
tylko jego widoczna część (ucięty o ponad połowę = niewidoczny), a tekst, który przez okno przejeżdżał, czytamy
tylko w końcowym postoju; okno na cały kadr nie przycina (tekst poza kadrem zostaje błędem). Ograniczenia: clip-path
i mask-image liczone jako widoczne; tło pod tekstem to mediana pikseli wokół glifów. Kontrole kompozycji (pusta scena, oddech, uderzenia) to przybliżenia
z małych klatek (zasady: rodzaje-filmu/references/ruch-i-kompozycja.md, za shotcraft i anything2explainer): ostrzegają,
nie blokują.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

STATYKA_PROG = 0.06             # największa zmiana piksela (miniatura 96 px) poniżej = obraz stoi
CZERN_PROG = 0.035              # średnia jasność poniżej = czarna klatka
OBIEKT_PUSTY = 0.15             # największy obiekt < 15% krótszego boku kadru dłużej niż 1,5 s = pusta scena
SPOKOJ = 0.006                  # średnia zmiana miniatury poniżej = kadr osiadł (drobny ruch w tle wolno)
NOWE_UJECIE = 0.25              # część pikseli miniatury zmieniona naraz (bez powrotu) = nowe ujęcie albo duża zmiana
UDERZENIE = 0.4                 # część zmieniona naraz, a po ≤ 0,3 s kadr wraca = uderzenie całego kadru
ODDECH = 0.8                    # s spokoju przed nowym ujęciem i na końcu (zasada: 1 s; próbki co 0,1 s)
PRZEJSCIE = 1.2                 # s na wyjście starego ujęcia i wejście nowego: spokój liczy się sprzed nich
NA_SOBIE = 0.3                  # część mniejszego napisu przykryta drugim = napisy na sobie
TRWALE = 0.3                    # s: krócej to klatki ruchu (napis wjeżdża, drugi odjeżdża), nie usterka
LEKTOR_OBOK = ("os_czasu.json", "*.slowa.json", "*.srt", "lektor*.wav")
GENERYCZNE = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif",
              "ui-monospace", "ui-rounded", "emoji", "math", "fangsong", "inherit", "initial", "-apple-system",
              "blinkmacsystemfont"}
POMIN_W_ODCISKU = {"out", "node_modules", ".git", "__pycache__", "klatki", "render"}
WYJSCIA_EXT = {".mp4", ".mov", ".webm", ".gif", ".mkv"}

# Sonda w przeglądarce: bloki tekstu (najbliższy przodek blokowy węzłów tekstowych), widoczna część tekstu (węzły
# z kryciem ≥ 0,5, glify przycięte do okien z overflow mniejszych niż kadr), granice glifów (Range.getClientRects),
# krycie, kolor, cień/obrys, rozmiar i krój.
SONDA_JS = r"""() => {
  const W = innerWidth, H = innerHeight;
  const ids = window.__jarvoPomiar || (window.__jarvoPomiar = { m: new WeakMap(), n: 0 });
  const blocks = new Map();
  const opac = (el) => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
    const s = getComputedStyle(e); if (s.display === "none" || s.visibility === "hidden") return 0; o *= parseFloat(s.opacity || "1"); } return o; };
  const blockOf = (el) => { for (let e = el; e && e !== document.body; e = e.parentElement) {
    const d = getComputedStyle(e).display; if (!/^inline/.test(d) && d !== "contents") return e; } return document.body; };
  // okno przycinające: część wspólna przodków z overflow ≠ visible, mniejszych niż kadr (kadr przycina sam: poza kadrem)
  const clips = new Map();
  const clipOf = (el) => { if (clips.has(el)) return clips.get(el);
    let c = null;
    for (let e = el; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      const s = getComputedStyle(e), ox = s.overflowX !== "visible", oy = s.overflowY !== "visible";
      if (!ox && !oy) continue;
      const r = e.getBoundingClientRect();
      if (r.left <= 0 && r.top <= 0 && r.right >= W && r.bottom >= H) continue;
      const q = { l: ox ? r.left : -1e9, t: oy ? r.top : -1e9, r: ox ? r.right : 1e9, b: oy ? r.bottom : 1e9 };
      c = c ? { l: Math.max(c.l, q.l), t: Math.max(c.t, q.t), r: Math.min(c.r, q.r), b: Math.min(c.b, q.b) } : q;
    }
    clips.set(el, c); return c; };
  const przytnij = (q, c) => { if (!c) return q;
    const l = Math.max(q.left, c.l), t = Math.max(q.top, c.t), r = Math.min(q.right, c.r), b = Math.min(q.bottom, c.b);
    return { left: l, top: t, right: r, bottom: b, width: r - l, height: b - t }; };
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    const txt = n.nodeValue.replace(/\s+/g, " ");
    if (!n.parentElement || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(n.parentElement.tagName)) continue;
    if (!txt.trim()) {                     // spacja między słowami w osobnych spanach (typografia słowo po słowie)
      const x = blocks.get(ids.m.get(blockOf(n.parentElement)));
      if (x && txt) { if (!x.full.endsWith(" ")) x.full += " "; if (x.seen && !x.seen.endsWith(" ")) x.seen += " "; }
      continue;
    }
    const b = blockOf(n.parentElement);
    if (!ids.m.has(b)) ids.m.set(b, ++ids.n);
    const id = ids.m.get(b);
    const r = document.createRange(); r.selectNodeContents(n);
    const okno = clipOf(n.parentElement);
    let ciety = false;
    const rects = [];
    for (const q0 of r.getClientRects()) {
      if (q0.width <= 0.5 || q0.height <= 0.5) continue;
      const q = przytnij(q0, okno);
      if (q.width < q0.width - 0.5 || q.height < q0.height - 0.5) ciety = true;
      if (q.width >= q0.width * 0.5 && q.height >= q0.height * 0.5) rects.push(q);   // ucięty o ponad połowę: nieczytelny
    }
    const a = opac(n.parentElement);
    let x = blocks.get(id);
    if (!x) { const s = getComputedStyle(n.parentElement);
      x = { id, full: "", seen: "", a: 0, x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9, color: s.color, size: parseFloat(s.fontSize),
            weight: parseInt(s.fontWeight, 10) || 400, family: s.fontFamily, shadow: s.textShadow !== "none" ? s.textShadow : "",
            stroke: parseFloat(s.webkitTextStrokeWidth || "0") > 0 ? s.webkitTextStrokeColor : "" };
      blocks.set(id, x); }
    x.full += txt;
    if (ciety) x.okno = true;
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


def czas_wygodny(tekst: str) -> float:
    """Sekundy na spokojne przeczytanie tekstu w ruchomym kadrze: znaki bez spacji / 15 + 1,5 s (oko najpierw musi
    tekst znaleźć). Liczby z lemo-opuscar (DIRECTOR.md §7, `readcheck.mjs`, MIT); u nas próg ostrzeżenia."""
    znaki = len(re.sub(r"\s+", "", tekst))
    return round(znaki / 15 + 1.5, 2) if znaki else 0.0


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
    """Strefy interfejsu platformy w kadrze 9:16 (wideo_lib.strefy_ui: te same co arkusz qa_wideo i edytor HQ),
    w innym kadrze marginesy: (nazwa, (x0, y0, x1, y1))."""
    pion = wl.strefy_ui(W, H, platforma)
    if pion:
        return pion
    return [("margines kadru", (0, 0, W, H * 0.08)), ("margines kadru", (0, H * 0.92, W, H)),
            ("margines kadru", (0, 0, W * 0.06, H)), ("margines kadru", (W * 0.94, 0, W, H))]


def _przeciecie(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def _ustalenie(kod, waga, opis, poprawka, t0, t1, **extra) -> dict:
    return {"kod": kod, "waga": waga, "opis": opis, "poprawka": poprawka, "od": round(t0, 2), "do": round(t1, 2), **extra}


def napisy_auto(katalog: Path) -> bool:
    """Film dostanie napisy lektora: obok strony leży oś czasu, słowa, SRT albo nagranie lektora."""
    return any(next(katalog.glob(w), None) for w in LEKTOR_OBOK)


def _serie(chwile: list[float], dt: float) -> list[tuple[float, float]]:
    """Chwile próbek → ciągłe odcinki (od, do) bez przerw dłuższych niż próbka."""
    out: list[list[float]] = []
    for t in sorted(chwile):
        if out and t - out[-1][1] <= dt * 1.5:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [(a, b + dt) for a, b in out]


def nakladanie(probki: list[dict], dt: float) -> list[dict]:
    """Dwa różne teksty na sobie (≥ 30% mniejszego) przez ≥ 0,3 s. Ten sam tekst dwa razy (obrys, cień, warstwa
    pod spodem) to jeden napis; tekst przycięty oknem (licznik bębnowy) i słabo widoczny (krycie < 0,6) pomijany."""
    pary: dict[tuple, list[float]] = {}
    nazwy: dict = {}
    for p in probki:
        W, H = p["W"], p["H"]
        vis = [x for x in p.get("teksty") or [] if x["a"] >= 0.6 and not x.get("okno") and x["x1"] > x["x0"] and x["y1"] > x["y0"]
               and _przeciecie((x["x0"], x["y0"], x["x1"], x["y1"]), (0, 0, W, H)) > 0]
        for i, a in enumerate(vis):
            for b in vis[i + 1:]:
                if a["full"] == b["full"] or a["id"] == b["id"]:
                    continue
                ra, rb = (a["x0"], a["y0"], a["x1"], a["y1"]), (b["x0"], b["y0"], b["x1"], b["y1"])
                mniejszy = min((ra[2] - ra[0]) * (ra[3] - ra[1]), (rb[2] - rb[0]) * (rb[3] - rb[1]))
                if mniejszy > 0 and _przeciecie(ra, rb) / mniejszy > NA_SOBIE:
                    klucz = tuple(sorted((str(a["id"]), str(b["id"]))))
                    pary.setdefault(klucz, []).append(p["t"])
                    nazwy[klucz] = (a["full"], b["full"])
    out = []
    for klucz, chwile in pary.items():
        for t0, t1 in _serie(chwile, dt):
            if t1 - t0 >= TRWALE - 1e-9:
                a, b = (s if len(s) <= 40 else s[:37] + "…" for s in nazwy[klucz])
                out.append(_ustalenie("napisy_na_sobie", "blad", f"„{a}” i „{b}” nachodzą na siebie ({t1 - t0:.1f} s)",
                                      "rozsuń napisy albo pokaż je po kolei (drugi po zejściu pierwszego)", t0, t1,
                                      tekst=nazwy[klucz][0], drugi=nazwy[klucz][1]))
    return sorted(out, key=lambda u: u["od"])


def analiza(probki: list[dict], dlugosc: float, hz: float, platforma: str | None = None, jezyk: str = "pl",
            tla: dict | None = None, napisy: bool = False) -> list[dict]:
    """Próbki [{t, W, H, teksty, luma, zmiana}] → ustalenia. `tla`: id tekstu → (kolor tła RGB, chwila) z klatek.
    `napisy`: film dostanie napisy lektora, więc tekst w ich pasie to błąd."""
    out: list[dict] = []
    if not probki:
        return out
    dt = 1.0 / hz
    W, H = probki[0]["W"], probki[0]["H"]
    zony = strefy(W, H, platforma)
    twarde_strefy = bool(platforma) or H > W
    pas = wl.pas_napisow(W, H) if napisy else None
    # teksty: przebieg w czasie
    przebieg: dict[int, list[tuple[float, dict]]] = {}
    for p in probki:
        for x in p.get("teksty") or []:
            przebieg.setdefault(x["id"], []).append((p["t"], x))
    for tid, ciag in przebieg.items():
        pelny = max((x["full"] for _, x in ciag), key=len)
        krotki = pelny if len(pelny) <= 60 else pelny[:57] + "…"
        # czas czytania: chwile, gdy cały tekst jest odsłonięty i dobrze widoczny. Tekst, który przejeżdżał przez
        # okno (licznik bębnowy, pasek cyfr), czytamy tylko w końcowym postoju: cyfra w drodze to klatka licznika
        czytany = ciag
        if any(x.get("okno") for _, x in ciag):
            czytany = []
            for i in range(len(ciag) - 1, 0, -1):
                (ta, a), (tb, b) = ciag[i - 1], ciag[i]
                if b.get("okno") or abs(tb - ta - dt) > dt / 2 or abs(b["y0"] - a["y0"]) > 0.5 or abs(b["x0"] - a["x0"]) > 0.5:
                    break
                czytany.insert(0, ciag[i])
        dostepny = sum(dt for _, x in czytany if x["a"] >= 0.6 and len(x["seen"]) >= len(pelny) * 0.98)
        minimum = czas_czytania(pelny, jezyk)
        potrzeba = max(minimum, czas_wygodny(pelny))
        t0, t1 = ciag[0][0], ciag[-1][0] + dt
        if potrzeba and czytany and dostepny < potrzeba:
            waga = "blad" if dostepny < minimum * 0.7 else "ostrz"
            out.append(_ustalenie("czas_czytania", waga, f"„{krotki}” czytelny {dostepny:.1f} s, potrzeba ok. {potrzeba:.1f} s"
                                  + (f" (szybki czytelnik: {minimum:.1f} s)" if waga == "blad" else " na spokojne przeczytanie"),
                                  "pokaż tekst dłużej, odsłoń go wcześniej albo skróć", t0, t1, tekst=pelny,
                                  dostepny=round(dostepny, 2), potrzeba=potrzeba, minimum=minimum))
        # poza kadrem: w pełni widoczny tekst wystający poza kadr
        poza = [(t, x) for t, x in ciag if x["a"] >= 0.9 and (x["x0"] < -2 or x["y0"] < -2 or x["x1"] > W + 2 or x["y1"] > H + 2)]
        if len(poza) * dt >= 0.25:
            out.append(_ustalenie("tekst_poza_kadrem", "blad", f"„{krotki}” wychodzi poza kadr przez {len(poza) * dt:.1f} s",
                                  "zmniejsz tekst, złam linię albo przesuń go do środka", poza[0][0], poza[-1][0] + dt, tekst=pelny))
        # strefy platformy
        for nazwa, z in zony:                  # ≥ 15% widocznej (w kadrze) części tekstu pod strefą
            pod = [(t, x) for t, x in ciag if x["a"] >= 0.6 and _przeciecie((x["x0"], x["y0"], x["x1"], x["y1"]), z)
                   > 0.15 * max(1.0, _przeciecie((x["x0"], x["y0"], x["x1"], x["y1"]), (0, 0, W, H)))]
            if len(pod) * dt >= 0.3:
                out.append(_ustalenie("strefa_platformy", "blad" if twarde_strefy else "ostrz",
                                      f"„{krotki}” w strefie: {nazwa} ({len(pod) * dt:.1f} s)",
                                      "przesuń tekst do bezpiecznego środka kadru (formaty-wideo)", pod[0][0], pod[-1][0] + dt,
                                      tekst=pelny, strefa=nazwa))
                break
        # pas napisów lektora: dół tekstu wchodzi w pas (z tolerancją 0,4% kadru), tekst choć w 10% w kadrze
        if pas:
            w_pasie = [t for t, x in ciag if x["a"] >= 0.6 and x["y1"] > pas[1] + 0.004 * H and x["y0"] < pas[3]
                       and x["x1"] > pas[0] and x["x0"] < pas[2]
                       and _przeciecie((x["x0"], x["y0"], x["x1"], x["y1"]), (0, 0, W, H))
                       > 0.1 * max(1.0, (x["x1"] - x["x0"]) * (x["y1"] - x["y0"]))]
            for s0, s1 in _serie(w_pasie, dt):
                if s1 - s0 >= TRWALE - 1e-9:
                    out.append(_ustalenie("pas_napisow", "blad", f"„{krotki}” w pasie napisów lektora "
                                          f"(y {pas[1]:.0f}–{pas[3]:.0f} px) przez {s1 - s0:.1f} s",
                                          "podnieś tekst nad pas napisów (gramatyki: safe.bottom) albo pokaż go, gdy lektor milczy",
                                          s0, s1, tekst=pelny))
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
    out += nakladanie(probki, dt)
    out += kompozycja(probki, dt)
    return out


def _spokoj_przed(zm: list, k: int, okno: int) -> int:
    """Najdłuższy ciąg spokojnych próbek (zmiana < SPOKOJ), który kończy się w `okno` próbkach przed k."""
    naj, j = 0, k - 1
    while j >= 1 and j >= k - okno:
        ciag = 0
        while j - ciag >= 1 and zm[j - ciag] is not None and zm[j - ciag] < SPOKOJ:
            ciag += 1
        naj = max(naj, ciag)
        j -= ciag + 1
    return naj


LICZBA_WIDOCZNA = 0.5            # s: tyle musi stać tekst z liczbą, żeby ją sprawdzić (licznik w ruchu się nie liczy)


def liczby_ekranu(probki: list[dict], hz: float, fakty: dict) -> list[dict]:
    """Liczby w tekstach na ekranie kontra fakty.json: każda wersja tekstu widoczna w całości co najmniej 0,5 s.
    Z listy niepewnych = błąd (nie trafia na ekran), bez pokrycia = ostrzeżenie (fakt bez źródła albo oś wykresu)."""
    pewne, niepewne = wl.liczby_faktow(fakty)
    dt = 1.0 / hz
    wersje: dict[tuple, list[float]] = {}
    for p in probki:
        for x in p.get("teksty") or []:
            if x["a"] >= 0.6 and len(x["seen"]) >= len(x["full"]) * 0.98:
                wersje.setdefault((x["id"], x["full"]), []).append(p["t"])
    out, byly = [], set()
    for (_, full), ts in wersje.items():
        if len(ts) * dt < LICZBA_WIDOCZNA - 1e-9:
            continue
        krotki = full if len(full) <= 60 else full[:57] + "…"
        for zapis, rodzaj in wl.sprawdz_liczby(full, pewne, niepewne):
            if (zapis, full) in byly:
                continue
            byly.add((zapis, full))
            if rodzaj == "niepewna":
                out.append(_ustalenie("liczba_niepewna", "blad", f"„{zapis}” w „{krotki}” jest na liście niepewnych w fakty.json",
                                      "usuń liczbę z ekranu albo poproś Sherlocka o drugie źródło", ts[0], ts[-1] + dt,
                                      tekst=full, liczba=zapis))
            else:
                out.append(_ustalenie("liczba_bez_zrodla", "ostrz", f"„{zapis}” w „{krotki}” bez źródła w fakty.json",
                                      "dopisz liczbę do briefu Sherlocka albo usuń; oś wykresu i numer kroku: wyjątek z powodem",
                                      ts[0], ts[-1] + dt, tekst=full, liczba=zapis))
    return out


def fakty_info(sciezka: Path | None) -> dict | None:
    """Ścieżka i skrót fakty.json do ustawień pomiaru (zmiana briefu = raport nieaktualny)."""
    if not sciezka:
        return None
    return {"plik": str(sciezka), "sha": hashlib.sha256(sciezka.read_bytes()).hexdigest()[:16]}


def kompozycja(probki: list[dict], dt: float) -> list[dict]:
    """Pusta scena, oddech przed nowym ujęciem i na końcu, uderzenia całego kadru. Pola próbek z pomiaru przeglądarki:
    `obiekt` (obiekt_glowny), `czesc` i `powrot` (ruch_kadru), `do_poczatku` w ostatniej; bez nich kontrola milczy."""
    out: list[dict] = []
    n = len(probki)
    jasna = [p.get("luma") is None or p["luma"] >= CZERN_PROG for p in probki]
    # pusta scena: odcinki, w których największy obiekt jest mały (czarne klatki się nie liczą)
    i = 0
    while i < n:
        o = probki[i].get("obiekt")
        if o is not None and o < OBIEKT_PUSTY and jasna[i]:
            j = i
            while j + 1 < n and probki[j + 1].get("obiekt") is not None and probki[j + 1]["obiekt"] < OBIEKT_PUSTY and jasna[j + 1]:
                j += 1
            if (j - i + 1) * dt >= 1.5:
                naj = max(probki[k]["obiekt"] for k in range(i, j + 1))
                out.append(_ustalenie("pusta_scena", "ostrz", f"największy obiekt w kadrze ma najwyżej {naj:.0%} krótszego boku "
                                      f"przez {(j - i + 1) * dt:.1f} s", "jeden bohater ujęcia ≥ 1/4 krótszego boku (duża liczba, "
                                      "powiększony element, zdjęcie); małe rzeczy zbierz w jeden duży układ",
                                      probki[i]["t"], probki[j]["t"] + dt, obiekt=naj))
            i = j + 1
        else:
            i += 1
    zm = [p.get("zmiana") for p in probki]
    cz = [p.get("czesc") for p in probki]
    pw = [p.get("powrot") for p in probki]
    wraca = [cz[k] is not None and pw[k] is not None and zm[k] and pw[k] <= 0.35 * zm[k] for k in range(n)]
    # uderzenia całego kadru: duża część kadru zmienia się i wraca (błysk, wstrząs, pompa skali)
    uderzenia, k = [], 1
    while k < n:
        if cz[k] is not None and cz[k] >= UDERZENIE and wraca[k]:
            uderzenia.append(probki[k]["t"])
            while k + 1 < n and cz[k + 1] is not None and cz[k + 1] >= UDERZENIE:
                k += 1
        k += 1
    if len(uderzenia) > 3:
        out.append(_ustalenie("uderzenia_kadru", "ostrz", f"{len(uderzenia)} uderzeń całego kadru (w {', '.join(f'{t:.1f}' for t in uderzenia[:8])} s); "
                              "najwyżej 3 na film", "zostaw 3 na najmocniejszych bitach, resztę bitów tylko na elementach",
                              uderzenia[0], uderzenia[-1] + dt, chwile=uderzenia))
    # oddech przed nowym ujęciem: duża zmiana bez powrotu po ujęciu ≥ 2 s, a w PRZEJSCIE s przed nią (wyjście starego
    # ujęcia, pusta chwila, początek wejścia) nie kończy się żaden spokój ≥ ODDECH s
    bez, poprzednie, k = [], 0.0, 1
    while k < n:
        if cz[k] is not None and cz[k] >= NOWE_UJECIE and not wraca[k]:
            spokoj = _spokoj_przed(zm, k, round(PRZEJSCIE / dt))
            if probki[k]["t"] - poprzednie >= 2.0 - 1e-6 and spokoj * dt < ODDECH:
                bez.append((probki[k]["t"], spokoj * dt))
            while k + 1 < n and cz[k + 1] is not None and cz[k + 1] >= NOWE_UJECIE * 0.5:   # przejście w kilku próbkach
                k += 1
            poprzednie = probki[k]["t"]
        k += 1
    if bez:
        out.append(_ustalenie("bez_oddechu", "ostrz", f"{len(bez)} × nowe ujęcie zaraz po zatrzymaniu ruchu ("
                              + ", ".join(f"{t:.1f} s po {s:.1f} s spokoju" for t, s in bez[:6]) + ")",
                              "po wylądowaniu ostatniego elementu daj 1–1,5 s spokoju, zanim ujęcie zniknie; ruch kamery kończ "
                              "co najmniej 1 s przed wyjściem", bez[0][0], bez[-1][0] + dt, chwile=[t for t, _ in bez]))
    # koniec: ostatni kadr (logo, puenta) stoi ≥ 1 s; wygaszenie do czerni na końcu nie liczy się jako ruch
    ost = probki[-1].get("do_poczatku")
    if ost is not None and ost >= 0.02 and n > 1:
        koniec = n
        while koniec > 1 and not jasna[koniec - 1]:
            koniec -= 1
        while koniec > 1 and probki[koniec - 1].get("luma") is not None and probki[koniec - 2].get("luma") is not None \
                and probki[koniec - 1]["luma"] < probki[koniec - 2]["luma"] - 0.004 and koniec < n:
            koniec -= 1                                                    # trwające wygaszenie
        spokoj = 0
        while koniec - 1 - spokoj >= 1 and zm[koniec - 1 - spokoj] is not None and zm[koniec - 1 - spokoj] < SPOKOJ:
            spokoj += 1
        if spokoj * dt < ODDECH:
            out.append(_ustalenie("bez_oddechu", "ostrz", f"koniec: ostatni kadr stoi {spokoj * dt:.1f} s",
                                  "logo albo puenta na końcu stoi co najmniej 1 s bez ruchu (film w pętli: ostatnia klatka = pierwsza)",
                                  probki[max(0, koniec - 1 - spokoj)]["t"], probki[-1]["t"] + dt))
    return out


def obiekt_glowny(jpg: bytes) -> float:
    """Wielkość największego obiektu w kadrze jako część krótszego boku (0–1). Tło = mediana ramki kadru; obiekt =
    spójne piksele wyraźnie inne niż tło; litery i słowa jednej linii łączą się w jeden obiekt; szeroki obiekt liczy się
    jak wyższy (min(szer., 4 × wys.) / 2,5). Kadr prawie cały inny niż ramka albo niejednolita ramka (zdjęcie, gradient,
    wzór w tle) = 1: tła nie da się ustalić, nie oceniamy."""
    from PIL import Image
    im = Image.open(io.BytesIO(jpg)).convert("RGB")
    skala = 96 / min(im.size)
    w, h = max(1, round(im.size[0] * skala)), max(1, round(im.size[1] * skala))
    px = list(im.resize((w, h)).getdata())
    ramka = px[:w] + px[-w:] + px[::w] + px[w - 1::w]
    tlo = [statistics.median(p[c] for p in ramka) for c in range(3)]
    def inny(p: tuple) -> bool:
        return max(abs(p[0] - tlo[0]), abs(p[1] - tlo[1]), abs(p[2] - tlo[2])) > 40
    maska = [inny(p) for p in px]
    if sum(maska) > 0.85 * len(maska) or sum(map(inny, ramka)) > 0.5 * len(ramka):
        return 1.0
    rodzic: dict[int, int] = {}

    def szukaj(a: int) -> int:
        while rodzic[a] != a:
            rodzic[a] = rodzic[rodzic[a]]
            a = rodzic[a]
        return a
    odcinki, poprzednie, nid = [], [], 0
    for y in range(h):                              # składowe spójne przez odcinki w wierszach (sąsiedztwo 8)
        biezace, x, wiersz = [], 0, maska[y * w:(y + 1) * w]
        while x < w:
            if not wiersz[x]:
                x += 1
                continue
            x0 = x
            while x < w and wiersz[x]:
                x += 1
            nid += 1
            rodzic[nid] = nid
            for a0, a1, pid in poprzednie:
                if a0 <= x and x0 <= a1:
                    ra, rb = szukaj(nid), szukaj(pid)
                    if ra != rb:
                        rodzic[ra] = rb
            biezace.append((x0, x, nid))
            odcinki.append((y, x0, x, nid))
        poprzednie = biezace
    ramki: dict[int, list[int]] = {}
    for y, x0, x1, i in odcinki:
        r = ramki.setdefault(szukaj(i), [x0, y, x1, y + 1, 0])
        r[0], r[1], r[2], r[3], r[4] = min(r[0], x0), min(r[1], y), max(r[2], x1), max(r[3], y + 1), r[4] + x1 - x0
    pudla = sorted((r[:4] for r in ramki.values() if r[4] >= 3), key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))[:150]
    zmiana = True
    while zmiana:                                    # litery i słowa jednej linii → jeden obiekt
        zmiana = False
        for a in range(len(pudla)):
            for b in range(a + 1, len(pudla)):
                p, q = pudla[a], pudla[b]
                hp, hq = p[3] - p[1], q[3] - q[1]
                wspolne = min(p[3], q[3]) - max(p[1], q[1])
                przerwa = max(p[0], q[0]) - min(p[2], q[2])
                if wspolne >= 0.5 * min(hp, hq) and przerwa <= 0.6 * max(hp, hq):
                    pudla[a] = [min(p[0], q[0]), min(p[1], q[1]), max(p[2], q[2]), max(p[3], q[3])]
                    del pudla[b]
                    zmiana = True
                    break
            if zmiana:
                break
    if not pudla:
        return 0.0
    naj = max(max(r[3] - r[1], min(r[2] - r[0], 4 * (r[3] - r[1])) / 2.5) for r in pudla)
    return round(min(1.0, naj / min(w, h)), 3)


def ruch_kadru(miniatury: list[bytes]) -> list[dict]:
    """Dla każdej próbki z miniatur (luma_i_zmiana, ten sam rozmiar): `czesc` = część pikseli zmieniona o > 10%
    względem poprzedniej, `powrot` = najmniejsza średnia różnica między poprzednią a jedną z 3 następnych (kadr
    wraca = uderzenie, nie nowe ujęcie); w ostatniej `do_poczatku` = średnia różnica z pierwszą (pętla ≈ 0)."""
    out: list[dict] = []
    roz = lambda a, b: sum(abs(x - y) for x, y in zip(a, b)) / (255 * max(1, len(a)))   # noqa: E731
    for i, m in enumerate(miniatury):
        d: dict = {}
        if i and len(miniatury[i - 1]) == len(m):
            d["czesc"] = round(sum(1 for x, y in zip(m, miniatury[i - 1]) if abs(x - y) > 26) / max(1, len(m)), 4)
            dalej = [miniatury[k] for k in range(i + 1, min(len(miniatury), i + 4)) if len(miniatury[k]) == len(m)]
            if dalej:
                d["powrot"] = round(min(roz(miniatury[i - 1], x) for x in dalej), 5)
        out.append(d)
    if len(miniatury) > 1 and len(miniatury[0]) == len(miniatury[-1]):
        out[-1]["do_poczatku"] = round(roz(miniatury[0], miniatury[-1]), 5)
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
    f = (raport.get("ustawienia") or {}).get("fakty")
    if f and (not Path(f["plik"]).is_file() or fakty_info(Path(f["plik"]))["sha"] != f["sha"]):
        powody.append("fakty.json zmienił się po pomiarze (liczby na ekranie): zmierz ponownie")
    elif not f and wl.znajdz_fakty(anim.resolve().parent):
        powody.append("obok animacji jest fakty.json, a pomiar był bez niego (liczby na ekranie): zmierz ponownie")
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
