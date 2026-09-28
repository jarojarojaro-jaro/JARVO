#!/usr/bin/env python3
"""Inspiracje do rodzaju filmu: prompty twórców filmów Opus 5.5 (yihui-dev/awesome-opus5-5-videos).

    python3 inspiracje.py explainer [--ile 3] [--tag threejs] [--szukaj whiteboard]
    python3 inspiracje.py --pelny <slug>          # cały prompt jednego wpisu
    python3 inspiracje.py --rodzaje               # nasze rodzaje → kategorie i słowa listy

Lista nie ma licencji (prompty należą do autorów), więc NIE trzymamy jej w repo: pobieramy w locie z przypiętego
commita (cache 30 dni) i czytamy jak publiczną stronę. Bierz strukturę i chwyty, nie tekst; zainspirowało → autor
i link w RAPORT. Pokazujemy tylko pełne prompty (bez „partial”), najpierw średnie i długie (najwięcej rzemiosła).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

REPO = "https://github.com/yihui-dev/awesome-opus5-5-videos"
REV = "6cdcea6c01a8bb6af836746017983cff32f465cb"
URL = f"https://raw.githubusercontent.com/yihui-dev/awesome-opus5-5-videos/{REV}/data/videos.json"
CACHE_DAYS = 30

# nasz rodzaj (rodzaje-filmu) → kategorie listy i wzorce w prompcie (regex, całe słowa; trafienia = trafność).
# motion-graphics: kategoria „motion” bez promptów, które pasują do rodzajów węższych (tam są lepiej opisane).
WZORCE: dict[str, list[str]] = {
    "explainer": [r"\bexplain", r"\bhow (it|\w+) works?\b", r"\bwhiteboard", r"\beducational\b", r"\bexplainer\b"],
    "promo-produktu": [r"\bproduct\b", r"\blaunch", r"\bapp\b", r"\bsaas\b", r"\blanding page\b", r"\bkeynote\b",
                       r"\bui states?\b", r"\bpromo\b", r"\bads?\b", r"\bfeatures?\b"],
    "typografia": [r"\btypograph", r"\bkinetic type", r"\blyrics?\b", r"\bquotes?\b", r"\bmanifesto\b",
                   r"\btext reveal", r"\bwords? (appear|fly|reveal)"],
    "dane": [r"\bcharts?\b", r"\binfographic", r"\bstatistic", r"\bdata[- ]driven\b", r"\bdata ?vi[sz]",
             r"\bgraphs?\b", r"\bbar chart", r"\bdashboard\b", r"\bleaderboard\b"],
    "logo-intro": [r"\blogo\b", r"\bintro\b", r"\bwordmark\b", r"\boutro\b", r"\bsting\b", r"\blower[- ]thirds?\b",
                   r"\bbumper\b", r"\bloader\b"],
    "fabula": [r"\bstory\b", r"\bcharacters?\b", r"\bpixar\b", r"\bshort film\b", r"\bnarrative\b",
               r"\bstorybook\b", r"\btale\b", r"\bprotagonist\b"],
    # kategorie listy bywają przypadkowe: 3D i gry potwierdzamy słowami i tagami (tagi są doklejone do tekstu)
    "scena-3d": [r"\bthreejs\b", r"\bthree\.js\b", r"\b3d\b", r"\bwebgl\b", r"\bshaders?\b", r"\bcamera\b"],
    "interaktywne": [r"\bgames?\b", r"\bplayable\b", r"\binteractive\b", r"\bplayers?\b", r"\bgameplay\b"],
}
RODZAJE: dict[str, dict] = {
    "explainer": {"kategorie": ["explainer"], "wzorce": WZORCE["explainer"]},
    "promo-produktu": {"kategorie": [], "wzorce": WZORCE["promo-produktu"]},
    "motion-graphics": {"kategorie": ["motion"], "wzorce": [],
                        "bez": [w for k in ("promo-produktu", "typografia", "dane", "logo-intro", "fabula")
                                for w in WZORCE[k]]},
    "typografia": {"kategorie": [], "wzorce": WZORCE["typografia"]},
    "dane": {"kategorie": [], "wzorce": WZORCE["dane"]},
    "scena-3d": {"kategorie": ["3d"], "wzorce": WZORCE["scena-3d"]},
    "interaktywne": {"kategorie": ["interactive"], "wzorce": WZORCE["interaktywne"]},
    "logo-intro": {"kategorie": [], "wzorce": WZORCE["logo-intro"]},
    "fabula": {"kategorie": [], "wzorce": WZORCE["fabula"]},
}


def load(refresh: bool = False) -> list[dict]:
    path = wl.cache_dir("inspiracje") / f"videos-{REV[:12]}.json"
    fresh = path.exists() and time.time() - path.stat().st_mtime < CACHE_DAYS * 86400
    if refresh or not fresh:
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "jarvo-wideo/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            json.loads(data)
            path.write_bytes(data)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if not path.exists():
                raise SystemExit(f"nie pobrałem listy inspiracji ({exc}); pracuj bez nich, to tylko dodatek")
    return json.loads(path.read_text(encoding="utf-8"))


def score(item: dict) -> float:
    """Najpierw prompty z rzemiosłem: 400–4000 znaków najwyżej, bardzo długie (specyfikacje) i krótkie niżej."""
    prompt = item.get("prompt", "")
    n = len(prompt)
    latin = sum(c.isascii() for c in prompt) / max(1, n) > 0.9      # czytelne od ręki (EN), pozostałe niżej
    if n < 120:
        return 0.1
    base = 1.0 + min(n, 4000) / 4000 if n <= 4000 else 1.0
    return base + (1.0 if latin else 0.0)


def relevance(item: dict, rule: dict) -> int:
    """0 = nie pasuje; kategoria listy = 3 pkt, każdy trafiony wzorzec = 1 pkt; wzorzec z „bez” wyklucza."""
    text = ((item.get("prompt") or "") + " " + " ".join(item.get("tech_tags") or [])).lower()
    if any(re.search(p, text) for p in rule.get("bez", [])):
        return 0
    return 3 * (item.get("category") in rule["kategorie"]) + sum(bool(re.search(p, text)) for p in rule["wzorce"])


def pick(items: list[dict], rodzaj: str, tag: str | None = None, szukaj: str | None = None, ile: int = 3) -> list[dict]:
    if rodzaj not in RODZAJE:
        raise SystemExit(f"nieznany rodzaj {rodzaj!r} ({' | '.join(RODZAJE)})")
    rule = RODZAJE[rodzaj]
    scored, seen = [], set()
    for it in items:
        if it.get("prompt_partial"):
            continue
        text = (it.get("prompt") or "").lower()
        rel = relevance(it, rule)
        if not rel or (tag and tag not in (it.get("tech_tags") or [])) or (szukaj and szukaj.lower() not in text):
            continue
        key = re.sub(r"\W+", " ", text)[:400]          # ten sam prompt u kilku autorów: pokaż raz
        if key in seen:
            continue
        seen.add(key)
        scored.append((min(rel, 4), score(it), it))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2].get("slug", "")))
    return [it for _, _, it in scored[:ile]]


def show(it: dict, limit: int | None = 1500) -> str:
    prompt = it.get("prompt", "").strip()
    cut = limit is not None and len(prompt) > limit
    body = prompt[:limit] + (f"\n[… {len(prompt) - limit} zn. więcej: --pelny {it['slug']}]" if cut else "")
    tags = ", ".join(it.get("tech_tags") or [])
    return (f"## {it['slug']}  ·  @{it.get('author', '?')}  ·  {it.get('category')}  ·  {tags}\n"
            f"post: {it.get('post_url', '')}\n\n{body}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rodzaj", nargs="?", help=" | ".join(RODZAJE))
    ap.add_argument("--ile", type=int, default=3)
    ap.add_argument("--tag", help="canvas, threejs, svg, shader, gsap, css, audio, particles, playable, pixel…")
    ap.add_argument("--szukaj", help="fraza w prompcie (po angielsku), np. whiteboard, \"one shape\"")
    ap.add_argument("--pelny", metavar="SLUG", help="pokaż cały prompt jednego wpisu")
    ap.add_argument("--rodzaje", action="store_true")
    ap.add_argument("--odswiez", action="store_true", help="pobierz listę ponownie")
    a = ap.parse_args(argv)
    if a.rodzaje:
        print(json.dumps(RODZAJE, ensure_ascii=False, indent=1))
        return 0
    items = load(a.odswiez)
    if a.pelny:
        hit = next((it for it in items if it.get("slug") == a.pelny), None)
        if not hit:
            raise SystemExit(f"nie ma wpisu {a.pelny!r}")
        print(show(hit, limit=None))
        return 0
    if not a.rodzaj:
        ap.error("podaj rodzaj albo --pelny <slug>")
    found = pick(items, a.rodzaj, a.tag, a.szukaj, a.ile)
    print(f"# Inspiracje: {a.rodzaj} ({len(found)}); źródło: {REPO} @ {REV[:7]}\n"
          "Weź strukturę i chwyty (sekcje, reguły, oś czasu), nie tekst. Użyte → autor i link w RAPORT.\n")
    for it in found:
        print(show(it))
    if not found:
        print("brak trafień: zdejmij --tag / --szukaj albo pracuj z samego pliku rodzaju")
    return 0


if __name__ == "__main__":
    sys.exit(main())
