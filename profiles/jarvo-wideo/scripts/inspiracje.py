#!/usr/bin/env python3
"""Inspiracje do rodzaju filmu: prompty twórców filmów Opus 5.5 (yihui-dev/awesome-opus5-5-videos
i guanmo-ai/awesome-ai-motion, MIT) oraz opisane drogi produkcji (athemeroy/awesome-opus-5-5-videos, CC-BY 4.0).

    python3 inspiracje.py explainer [--ile 3] [--tag threejs] [--szukaj whiteboard]
    python3 inspiracje.py --pelny <slug>          # cały prompt jednego wpisu
    python3 inspiracje.py --rodzaje               # nasze rodzaje → kategorie i słowa listy
    python3 inspiracje.py --drogi [--ile 3]       # jak naprawdę powstały filmy: droga produkcji + przykłady z dowodem
    python3 inspiracje.py ujecia [--kategoria kamera] [--energia wysoka] [--szukaj scroll] [--ile 12]
    python3 inspiracje.py ujecia --karta deck-deal-flyin   # karta ujęcia: plik, demo, czas, energia, skąd ruch, nasz odpowiednik

`ujecia` = katalog 157 kart ujęć video-shotcraft (Apache-2.0) z zainstalowanej kopii (`narzedzia.py instaluj shotcraft`):
nazwa, kategoria, energia, czas, opis (po chińsku: tłumaczysz w głowie, nie kopiujesz), ścieżki karty i dema TSX.
Karta z ruchem odtworzonym z cudzej reklamy albo cudzego filmu ma znak „tylko technika”: bierzesz sam ruch, nigdy
kadrów, układu ani tekstów. „u nas” = gotowy odpowiednik w naszym kodzie (`/_lib/jarvo/…`), od niego zaczynasz.

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
import narzedzia as nz  # noqa: E402
import wideo_lib as wl  # noqa: E402

REPO = "https://github.com/yihui-dev/awesome-opus5-5-videos"
REV = "6cdcea6c01a8bb6af836746017983cff32f465cb"
URL = f"https://raw.githubusercontent.com/yihui-dev/awesome-opus5-5-videos/{REV}/data/videos.json"
CACHE_DAYS = 30
AIM_REPO = "https://github.com/guanmo-ai/awesome-ai-motion"         # MIT
AIM_REV = "dff7a79b9da34dc1553634cabcae22a583ab02fc"
AIM_URL = f"https://raw.githubusercontent.com/guanmo-ai/awesome-ai-motion/{AIM_REV}/data/cases.json"
ATH_REPO = "https://github.com/athemeroy/awesome-opus-5-5-videos"   # CC-BY 4.0: przy użyciu podaj autora i link
ATH_REV = "f0728e6fd1e5ec496815c1c7ba115bc70e3a31f9"
ATH_URL = f"https://raw.githubusercontent.com/athemeroy/awesome-opus-5-5-videos/{ATH_REV}/data/cases.csv"
AIM_KAT = {"叙事短片": "stories", "产品宣传": "product", "知识讲解": "explainer", "短动效": "motion",
           "3D 与交互": "3d", "音乐与歌词": "music", "像素与角色": "characters"}

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
    "promo-produktu": {"kategorie": ["product"], "wzorce": WZORCE["promo-produktu"]},
    "motion-graphics": {"kategorie": ["motion"], "wzorce": [],
                        "bez": [w for k in ("promo-produktu", "typografia", "dane", "logo-intro", "fabula")
                                for w in WZORCE[k]]},
    "typografia": {"kategorie": [], "wzorce": WZORCE["typografia"]},
    "dane": {"kategorie": [], "wzorce": WZORCE["dane"]},
    "scena-3d": {"kategorie": ["3d"], "wzorce": WZORCE["scena-3d"]},
    "interaktywne": {"kategorie": ["interactive"], "wzorce": WZORCE["interaktywne"]},
    "logo-intro": {"kategorie": [], "wzorce": WZORCE["logo-intro"]},
    "fabula": {"kategorie": ["stories", "characters"], "wzorce": WZORCE["fabula"]},
}


# ---------------------------------------------------------------- karty ujęć video-shotcraft
KATEGORIE = {"otwarcie": "opening", "typografia": "typography", "wejscie-ui": "ui-entrance", "kamera": "camera",
             "dane": "data", "interakcja": "interaction", "przejscie": "transition", "rytm": "rhythm",
             "efekty": "effects", "zakonczenie": "outro"}
ENERGIE = {"niska": (0, 2.5), "srednia": (2.5, 3.5), "wysoka": (3.5, 9)}
# karta shotcraft → nasz odpowiednik (moduł pod /_lib/jarvo/ albo zasada w skillu)
NASZE: dict[str, str] = {
    "crash-zoom-punch": "strona.js uderzenie() (crash zoom w cel strony; najwyżej 2 na film)",
    "smear-multiples": "ruch.js smuga(), duchy(), rozciagniecie() (szybki ruch bez motion bluru)",
    "marker-underline-title": "strona.js zakreslacz() (pas pod tekstem w 0,4–0,8 s)",
    "shot-transitions": "rodzaje-filmu/references/ruch-i-kompozycja.md §5 (słownik przejść) + projekt.py przejscie",
    "transition-hidden-cut": "rodzaje-filmu/references/ruch-i-kompozycja.md §5 (ukryte cięcia)",
    "deck-deal-flyin": "ujecia.js rozdanie(), startRozdania(), zapowiedzRozdania() (karty z talii do siatki)",
    "list-stack-press": "ujecia.js stos(), docisk(), podswietlenie(), licznikZdarzen() (stos z dociskiem)",
    "row-embed": "ujecia.js wiersz() (wiersz wpada w swoje miejsce w zrzucie, szew akcentu)",
    "type-and-filter": "ujecia.js pisanie(), filtr(), doSlotu(), klik() (wyszukiwarka i wynik)",
    "paper-title-card": "ujecia.js tytulPapier() (słowa wciskane w papier, jedno słowo-akcent)",
    "odometer-digit-roll": "ujecia.js licznikBebnowy() (cyfry jak w liczniku, najwyżej 6)",
    "beat-cut-moves": "ujecia.js przyspieszenie(), flesz() (cięcia na bit; raz na film)",
    "speed-ramp-freeze": "ujecia.js przemapuj(), sprawdzTempo(), kolko() (zwolnienie i stop-klatka)",
    "depth-layer-moves": "ujecia.js paralaksa(), dollyZoom() (warstwy głębi; dolly raz na film)",
    "outro-group-photo-launch": "ujecia.js grupaElement(), grupaLitera(), grupaKamera() (finał: zdjęcie grupowe)",
    "spotlight-hero-card": "ujecia.js reflektor(), kartaBohatera() (reflektor na bohaterze, wolno)",
}


def energia_poziom(tekst: str) -> float | None:
    """Energia karty („中高（…）”, „A 高”, „由低到高”, „峰值”) → 1 (niska) … 5 (wysoka); „n/a” = None."""
    t = re.sub(r"^[AB]\s+", "", (tekst or "").strip())
    if not t or t.lower().startswith("n/a"):
        return None
    glowa = re.split(r"[（(]", t, maxsplit=1)[0]
    if any(x in glowa for x in ("峰值", "高潮", "极高")):
        return 5.0
    oceny = [{"低": 1, "中": 3, "高": 5}[z] for z in glowa if z in "低中高"]
    return round(sum(oceny) / len(oceny), 2) if oceny else None


def _frontmatter(md: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---", md, re.S)
    out = {}
    for linia in (m.group(1).splitlines() if m else []):
        k, _, v = linia.partition(":")
        if v:
            out[k.strip()] = v.strip()
    return out


def zrodla_obce(root: Path) -> dict[str, str]:
    """Karty z ruchem podpatrzonym w cudzych filmach (ATTRIBUTION.md, tabela „逐卡来源映射”): nazwa → źródło."""
    plik = root / "references" / "shots" / "ATTRIBUTION.md"
    if not plik.exists():
        return {}
    tekst = plik.read_text(encoding="utf-8")
    sekcja = tekst.split("逐卡来源映射", 1)[-1] if "逐卡来源映射" in tekst else ""
    out = {}
    for wiersz in sekcja.splitlines():
        kom = [k.strip() for k in wiersz.strip().strip("|").split("|")]
        if len(kom) >= 2 and "`" in kom[1]:
            for nazwa in re.findall(r"`([a-z0-9-]+)`", kom[1]):
                out[nazwa] = kom[0]
    return out


def katalog_ujec(root: Path | None = None) -> list[dict]:
    """Karty z `gallery/api/library.json` zainstalowanego video-shotcraft + plik karty: demo, „原片出处”, źródło obce."""
    root = root or nz.SHOTCRAFT
    lib = root / "gallery" / "api" / "library.json"
    if not lib.exists():
        raise SystemExit(f"brak katalogu kart ({lib}): python3 $HERMES_HOME/scripts/narzedzia.py instaluj shotcraft")
    dane = json.loads(lib.read_text(encoding="utf-8"))
    obce = zrodla_obce(root)
    karty = []
    for c in dane.get("cards", []):
        plik = root / c.get("source", "")
        md = plik.read_text(encoding="utf-8") if plik.is_file() else ""
        fm = _frontmatter(md)
        demo = re.search(r"##\s*参考实现\s*\n+\s*`?(demos/[^\s`（(]+)", md)
        oryginal = re.search(r"原片出处[:：]\s*(.+)", md)
        kat = c.get("category", "")
        karty.append({
            "nazwa": c["name"], "kategoria": next((pl for pl, en in KATEGORIE.items() if en == kat), kat),
            "energia": c.get("energy") or fm.get("能量", ""), "poziom": energia_poziom(c.get("energy") or fm.get("能量", "")),
            "czas": c.get("duration") or fm.get("时长", ""), "opis": c.get("summary") or fm.get("一句话", ""),
            "kiedy": c.get("use") or fm.get("适用", ""), "zamiar": c.get("intention", ""),
            "karta": plik.as_posix(), "demo": (root / demo.group(1)).as_posix() if demo else None,
            "style": [st.get("key") for st in c.get("styles", [])],
            "tylko_technika": (oryginal.group(1).strip() if oryginal else None) or obce.get(c["name"]),
            "u_nas": NASZE.get(c["name"]),
        })
    return karty


def wybierz_ujecia(karty: list[dict], kategoria: str | None = None, energia: str | None = None,
                   szukaj: str | None = None, ile: int = 12) -> list[dict]:
    if kategoria:
        kat = kategoria if kategoria in KATEGORIE else next((pl for pl, en in KATEGORIE.items() if en == kategoria), None)
        if not kat:
            raise SystemExit(f"nieznana kategoria {kategoria!r} ({' | '.join(KATEGORIE)})")
        karty = [k for k in karty if k["kategoria"] == kat]
    if energia:
        if energia not in ENERGIE:
            raise SystemExit(f"nieznana energia {energia!r} ({' | '.join(ENERGIE)})")
        lo, hi = ENERGIE[energia]
        karty = [k for k in karty if k["poziom"] is not None and lo <= k["poziom"] < hi]
    if szukaj:
        fraza = szukaj.lower()
        karty = [k for k in karty if fraza in " ".join(str(k[p]) for p in ("nazwa", "opis", "kiedy", "zamiar", "style")).lower()]
    # najpierw karty z naszym odpowiednikiem, potem własne (bez „tylko technika”), na końcu alfabetycznie
    karty = sorted(karty, key=lambda k: (k["u_nas"] is None, k["tylko_technika"] is not None, k["nazwa"]))
    return karty[:ile]


def pokaz_ujecie(k: dict, pelna: bool = False) -> str:
    poziom = {None: "?"}.get(k["poziom"]) or next(n for n, (lo, hi) in ENERGIE.items() if lo <= k["poziom"] < hi)
    znaki = "".join([f"  [u nas: {k['u_nas']}]" if k["u_nas"] else "",
                     f"  [tylko technika: {k['tylko_technika']}]" if k["tylko_technika"] else ""])
    linie = [f"## {k['nazwa']} · {k['kategoria']} · energia {poziom} · {k['czas'][:40]}{znaki}", k["opis"]]
    if pelna:
        linie += [f"kiedy: {k['kiedy']}", f"zamiar: {k['zamiar']}", f"energia: {k['energia']}",
                  f"style (podgląd w galerii): {', '.join(filter(None, k['style']))}"]
    linie.append(f"karta: {k['karta']}" + (f"\ndemo: {k['demo']}" if k["demo"] else ""))
    return "\n".join(linie) + "\n"


def ujecia(a) -> int:
    karty = katalog_ujec()
    if a.karta:
        k = next((x for x in karty if x["nazwa"] == a.karta), None)
        if not k:
            podobne = [x["nazwa"] for x in karty if a.karta.split("-")[0] in x["nazwa"]][:8]
            raise SystemExit(f"nie ma karty {a.karta!r}" + (f" (podobne: {', '.join(podobne)})" if podobne else ""))
        print(pokaz_ujecie(k, pelna=True))
        return 0
    found = wybierz_ujecia(karty, a.kategoria, a.energia, a.szukaj, a.ile or 12)
    print(f"# Karty ujęć video-shotcraft (Apache-2.0): {len(found)} z {len(karty)} · kategorie: {' | '.join(KATEGORIE)}\n"
          "Kolejność: karta → demo TSX (parametry sprawdzone) → nasz kod. Opis po chińsku tłumaczysz, nie kopiujesz.\n")
    for k in found:
        print(pokaz_ujecie(k))
    if not found:
        print("brak trafień: zdejmij --energia / --szukaj")
    return 0


def fetch(url: str, name: str, refresh: bool, check=json.loads) -> str | None:
    """Pobiera plik z przypiętego commita do cache (30 dni); bez sieci używa starego cache albo zwraca None."""
    path = wl.cache_dir("inspiracje") / name
    fresh = path.exists() and time.time() - path.stat().st_mtime < CACHE_DAYS * 86400
    if refresh or not fresh:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "jarvo-wideo/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            check(data.decode("utf-8"))
            path.write_bytes(data)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if not path.exists():
                print(f"(pominięte źródło {name}: {exc})", file=sys.stderr)
                return None
    return path.read_text(encoding="utf-8")


def from_aim(raw: str) -> list[dict]:
    """awesome-ai-motion → format listy yihui (slug, author, category, prompt, tech_tags, post_url)."""
    out = []
    for c in json.loads(raw).get("cases", []):
        pr = c.get("prompt") or {}
        out.append({"slug": f"aim-{c['id']}", "author": (c.get("author") or {}).get("handle", "?"),
                    "category": AIM_KAT.get(c.get("category"), "other"), "prompt": pr.get("text") or "",
                    "prompt_partial": pr.get("status") != "original", "post_url": (c.get("source") or {}).get("url", ""),
                    "tech_tags": [], "opis": " ".join(filter(None, [c.get("titleEn"), c.get("summaryEn")])),
                    "zrodlo": AIM_REPO})
    return out


def load(refresh: bool = False) -> list[dict]:
    raw = fetch(URL, f"videos-{REV[:12]}.json", refresh)
    items = [dict(it, zrodlo=REPO) for it in json.loads(raw)] if raw else []
    aim = fetch(AIM_URL, f"aim-{AIM_REV[:12]}.json", refresh)
    items += from_aim(aim) if aim else []
    if not items:
        raise SystemExit("nie pobrałem list inspiracji; pracuj bez nich, to tylko dodatek")
    return items


def drogi(refresh: bool, ile: int) -> str:
    """Opisane przypadki (athemeroy, CC-BY 4.0): jaka droga produkcji naprawdę stoi za filmem."""
    import csv, io
    raw = fetch(ATH_URL, f"athemeroy-{ATH_REV[:12]}.csv", refresh, check=lambda t: t.index("source_url"))
    if not raw:
        return "brak danych o drogach produkcji (sieć); to tylko dodatek"
    rows = list(csv.DictReader(io.StringIO(raw)))
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r.get("primary_path") or "?", []).append(r)
    out = [f"# Drogi produkcji: {len(rows)} opisanych filmów · źródło: {ATH_REPO} (CC-BY 4.0, autor: athemeroy)\n"]
    for path, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        out.append(f"## {path} ({len(rs)})")
        for r in rs[:ile]:
            out.append(f"- {r.get('label')} · {r.get('source_url')}\n  {(r.get('creator_disclosure') or '')[:300]}")
    return "\n".join(out)


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
    text = " ".join([item.get("prompt") or "", item.get("opis") or "", *(item.get("tech_tags") or [])]).lower()
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
            f"post: {it.get('post_url', '')} · lista: {it.get('zrodlo', REPO)}\n\n{body}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rodzaj", nargs="?", help=" | ".join(RODZAJE) + " | ujecia (karty ujęć shotcraft)")
    ap.add_argument("--ile", type=int, default=None, help="ile wyników (prompty: 3, karty ujęć: 12)")
    ap.add_argument("--kategoria", help="ujecia: " + " | ".join(KATEGORIE))
    ap.add_argument("--energia", choices=list(ENERGIE), help="ujecia: niska | srednia | wysoka")
    ap.add_argument("--karta", metavar="NAZWA", help="ujecia: pełna karta jednego ujęcia")
    ap.add_argument("--tag", help="canvas, threejs, svg, shader, gsap, css, audio, particles, playable, pixel…")
    ap.add_argument("--szukaj", help="fraza w prompcie (po angielsku), np. whiteboard, \"one shape\"")
    ap.add_argument("--pelny", metavar="SLUG", help="pokaż cały prompt jednego wpisu")
    ap.add_argument("--rodzaje", action="store_true")
    ap.add_argument("--drogi", action="store_true", help="drogi produkcji z przykładami (co naprawdę zrobił model)")
    ap.add_argument("--odswiez", action="store_true", help="pobierz listę ponownie")
    a = ap.parse_args(argv)
    if a.rodzaj == "ujecia":
        return ujecia(a)
    a.ile = a.ile or 3
    if a.rodzaje:
        print(json.dumps(RODZAJE, ensure_ascii=False, indent=1))
        return 0
    if a.drogi:
        print(drogi(a.odswiez, a.ile))
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
    print(f"# Inspiracje: {a.rodzaj} ({len(found)}); listy: {REPO} @ {REV[:7]}, {AIM_REPO} @ {AIM_REV[:7]}\n"
          "Weź strukturę i chwyty (sekcje, reguły, oś czasu), nie tekst. Użyte → autor i link w RAPORT.\n")
    for it in found:
        print(show(it))
    if not found:
        print("brak trafień: zdejmij --tag / --szukaj albo pracuj z samego pliku rodzaju")
    return 0


if __name__ == "__main__":
    sys.exit(main())
