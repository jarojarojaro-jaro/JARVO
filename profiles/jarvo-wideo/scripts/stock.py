#!/usr/bin/env python3
"""Darmowe ujęcia i zdjęcia z Pexels i Pixabay: szukanie, arkusz podglądów do oceny okiem, pobieranie z licencją.

    python3 stock.py szukaj "ziarna kawy makro" [--format 9:16] [--typ wideo|zdjecie] [--ile 8] [--min-sek 4]
                            [--arkusz out/wideo/arkusz.jpg] [--json]
    python3 stock.py pobierz pexels:123456 [--format 9:16] [--typ wideo|zdjecie] [--do out/wideo/src]

Klucze (darmowe): PEXELS_API_KEY (pexels.com/api), PIXABAY_API_KEY (pixabay.com/api/docs). Wystarczy jeden;
dodaj w dashboardzie Keys (profil główny), Jarvo rozda go agentom. Zapytanie może być po polsku (locale pl-PL),
ale angielskie zwykle daje więcej trafień. Pobrane pliki lądują we wspólnym cache (drugi raz: bez pobierania),
a obok pliku `.json` z autorem, adresem strony i licencją (do RAPORT.md i opisu posta).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

UA = "Jarvo-Wideograf/1.0 (+https://github.com/)"
LICENSES = {
    "pexels": "Licencja Pexels: darmowe użycie komercyjne, bez wymogu podpisu (mile widziany); nie sprzedawać bez zmian, "
              "nie sugerować poparcia osób z kadru. https://www.pexels.com/license/",
    "pixabay": "Licencja Pixabay: darmowe użycie komercyjne, bez wymogu podpisu; nie sprzedawać bez zmian, "
               "uważać na znaki towarowe i rozpoznawalne osoby. https://pixabay.com/service/license-summary/",
}


class StockError(RuntimeError):
    pass


def keys() -> dict[str, str]:
    return {p: os.environ.get(v, "").strip() for p, v in (("pexels", "PEXELS_API_KEY"), ("pixabay", "PIXABAY_API_KEY"))
            if os.environ.get(v, "").strip()}


def _get(url: str, headers: dict | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise StockError(f"{urllib.parse.urlparse(url).netloc}: klucz API odrzucony ({exc.code})") from exc
        if exc.code == 429:
            raise StockError(f"{urllib.parse.urlparse(url).netloc}: limit zapytań (429), spróbuj za chwilę") from exc
        raise StockError(f"{url.split('?')[0]}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise StockError(f"{urllib.parse.urlparse(url).netloc}: brak połączenia ({exc.reason})") from exc


def _json(url: str, headers: dict | None = None) -> dict:
    cache = wl.cache_dir("stock", "zapytania") / f"{wl.digest(url)}.json"
    if cache.exists() and (cache.stat().st_mtime > __import__("time").time() - 24 * 3600):  # Pixabay: cache 24 h
        return json.loads(cache.read_text(encoding="utf-8"))
    data = json.loads(_get(url, headers))
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


# ------------------------------------------------------------------ dostawcy

def _pexels_orient(fmt: str) -> str:
    return wl.orientation(fmt)


def _pixabay_orient(fmt: str) -> str:
    return {"portrait": "vertical", "landscape": "horizontal"}.get(wl.orientation(fmt), "all")


def search_pexels(key: str, query: str, kind: str, fmt: str, n: int) -> list[dict]:
    q = urllib.parse.quote(query)
    if kind == "wideo":
        data = _json(f"https://api.pexels.com/videos/search?query={q}&orientation={_pexels_orient(fmt)}&per_page={min(n * 2, 40)}"
                     f"&locale=pl-PL", {"Authorization": key})
        out = []
        for v in data.get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("link") and f.get("width") and f.get("height")]
            out.append({"id": f"pexels:{v['id']}", "zrodlo": "pexels", "typ": "wideo", "szer": v.get("width"),
                        "wys": v.get("height"), "sek": v.get("duration"), "podglad": v.get("image"),
                        "strona": v.get("url"), "autor": (v.get("user") or {}).get("name"),
                        "autor_url": (v.get("user") or {}).get("url"),
                        "pliki": [{"url": f["link"], "szer": f["width"], "wys": f["height"], "fps": f.get("fps")} for f in files]})
        return out
    data = _json(f"https://api.pexels.com/v1/search?query={q}&orientation={_pexels_orient(fmt)}&per_page={min(n * 2, 40)}"
                 f"&locale=pl-PL", {"Authorization": key})
    return [{"id": f"pexels:{p['id']}", "zrodlo": "pexels", "typ": "zdjecie", "szer": p.get("width"), "wys": p.get("height"),
             "podglad": (p.get("src") or {}).get("medium"), "strona": p.get("url"), "autor": p.get("photographer"),
             "autor_url": p.get("photographer_url"), "alt": p.get("alt"),
             "pliki": [{"url": (p.get("src") or {}).get("original"), "szer": p.get("width"), "wys": p.get("height")}]}
            for p in data.get("photos", [])]


def search_pixabay(key: str, query: str, kind: str, fmt: str, n: int) -> list[dict]:
    q = urllib.parse.quote(query)
    per = max(3, min(n * 2, 50))
    if kind == "wideo":
        data = _json(f"https://pixabay.com/api/videos/?key={key}&q={q}&per_page={per}&lang=pl&safesearch=true")
        out = []
        for h in data.get("hits", []):
            vids = h.get("videos") or {}
            files = [{"url": f["url"], "szer": f.get("width"), "wys": f.get("height")}
                     for f in vids.values() if f.get("url") and f.get("width")]
            thumb = next((f.get("thumbnail") for f in (vids.get("medium"), vids.get("small"), vids.get("large")) if f and f.get("thumbnail")), None)
            big = max(files, key=lambda f: f["szer"] * f["wys"], default={})
            out.append({"id": f"pixabay:{h['id']}", "zrodlo": "pixabay", "typ": "wideo", "szer": big.get("szer"),
                        "wys": big.get("wys"), "sek": h.get("duration"), "podglad": thumb, "strona": h.get("pageURL"),
                        "autor": h.get("user"), "autor_url": f"https://pixabay.com/users/{h.get('user')}-{h.get('user_id')}/",
                        "tagi": h.get("tags"), "pliki": files})
        return out
    data = _json(f"https://pixabay.com/api/?key={key}&q={q}&image_type=photo&orientation={_pixabay_orient(fmt)}"
                 f"&per_page={per}&lang=pl&safesearch=true")
    return [{"id": f"pixabay:{h['id']}", "zrodlo": "pixabay", "typ": "zdjecie", "szer": h.get("imageWidth"),
             "wys": h.get("imageHeight"), "podglad": h.get("webformatURL"), "strona": h.get("pageURL"), "autor": h.get("user"),
             "tagi": h.get("tags"), "pliki": [{"url": h.get("largeImageURL"), "szer": h.get("imageWidth"), "wys": h.get("imageHeight")}]}
            for h in data.get("hits", [])]


PROVIDERS = {"pexels": search_pexels, "pixabay": search_pixabay}


def score(item: dict, fmt: str, min_sec: float) -> float:
    """Ranking: zgodna orientacja, rozdzielczość co najmniej docelowa, długość ≥ sceny."""
    w, h = wl.parse_format(fmt)
    sw, sh = item.get("szer") or 0, item.get("wys") or 0
    s = 0.0
    if sw and sh:
        same = (sh > sw) == (h > w) or (sw == sh and w == h)
        s += 3 if same else -2
        s += 2 if min(sw, sh) >= min(w, h) else (0 if min(sw, sh) >= 720 else -4)
    if item["typ"] == "wideo":
        sec = item.get("sek") or 0
        s += 2 if sec >= min_sec else -3
        s -= 0.5 if sec > 60 else 0
    return s


def search(query: str, kind: str = "wideo", fmt: str = "9:16", n: int = 8, min_sec: float = 4.0) -> list[dict]:
    ks = keys()
    if not ks:
        raise StockError("Brak klucza: ustaw PEXELS_API_KEY albo PIXABAY_API_KEY (darmowe; dashboard → Keys).")
    items, errors = [], []
    for prov, key in ks.items():
        try:
            items += PROVIDERS[prov](key, query, kind, fmt, n)
        except StockError as exc:
            errors.append(str(exc))
    if not items and errors:
        raise StockError("; ".join(errors))
    items.sort(key=lambda it: -score(it, fmt, min_sec))
    return items[:n]


def pick_file(item: dict, fmt: str) -> dict:
    """Najlżejszy plik, który pokrywa rozdzielczość docelową (bez 4K, gdy wystarczy 1080p)."""
    w, h = wl.parse_format(fmt)
    need = min(w, h)
    files = [f for f in item.get("pliki", []) if f.get("url")]
    if not files:
        raise StockError(f"{item['id']}: brak plików do pobrania")
    ok = [f for f in files if min(f.get("szer") or 0, f.get("wys") or 0) >= need]
    return min(ok, key=lambda f: (f["szer"] or 0) * (f["wys"] or 0)) if ok else max(files, key=lambda f: (f["szer"] or 0) * (f["wys"] or 0))


def lookup(item_id: str, kind: str) -> dict:
    prov, _, raw = item_id.partition(":")
    ks = keys()
    if prov not in ks:
        raise StockError(f"{item_id}: brak klucza {prov.upper()}_API_KEY")
    if prov == "pexels":
        url = f"https://api.pexels.com/videos/videos/{raw}" if kind == "wideo" else f"https://api.pexels.com/v1/photos/{raw}"
        v = _json(url, {"Authorization": ks[prov]})
        if kind == "wideo":
            files = [f for f in v.get("video_files", []) if f.get("link") and f.get("width")]
            return {"id": item_id, "zrodlo": "pexels", "typ": "wideo", "szer": v.get("width"), "wys": v.get("height"),
                    "sek": v.get("duration"), "strona": v.get("url"), "autor": (v.get("user") or {}).get("name"),
                    "autor_url": (v.get("user") or {}).get("url"),
                    "pliki": [{"url": f["link"], "szer": f["width"], "wys": f["height"]} for f in files]}
        return {"id": item_id, "zrodlo": "pexels", "typ": "zdjecie", "szer": v.get("width"), "wys": v.get("height"),
                "strona": v.get("url"), "autor": v.get("photographer"), "autor_url": v.get("photographer_url"),
                "pliki": [{"url": (v.get("src") or {}).get("original"), "szer": v.get("width"), "wys": v.get("height")}]}
    base = "https://pixabay.com/api/videos/" if kind == "wideo" else "https://pixabay.com/api/"
    data = _json(f"{base}?key={ks[prov]}&id={raw}")
    hits = data.get("hits") or []
    if not hits:
        raise StockError(f"{item_id}: nie znaleziono")
    h = hits[0]
    if kind == "wideo":
        files = [{"url": f["url"], "szer": f.get("width"), "wys": f.get("height")} for f in (h.get("videos") or {}).values() if f.get("url")]
        return {"id": item_id, "zrodlo": "pixabay", "typ": "wideo", "sek": h.get("duration"), "strona": h.get("pageURL"),
                "autor": h.get("user"), "pliki": files}
    return {"id": item_id, "zrodlo": "pixabay", "typ": "zdjecie", "strona": h.get("pageURL"), "autor": h.get("user"),
            "pliki": [{"url": h.get("largeImageURL"), "szer": h.get("imageWidth"), "wys": h.get("imageHeight")}]}


def download(item: dict | str, fmt: str = "9:16", kind: str = "wideo", dest: Path | None = None) -> tuple[Path, dict]:
    """Pobierz (albo weź z cache) plik ujęcia; zwraca ścieżkę i metadane z licencją."""
    if isinstance(item, str):
        hit = next((p for p in sorted(wl.cache_dir("stock", "pliki").glob(item.replace(":", "-") + "-*"))
                    if p.suffix != ".json" and p.stat().st_size > 0), None)
        if hit:
            meta_p = hit.with_suffix(".json")
            meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {"id": item}
            return _deliver(hit, meta, dest)
        item = lookup(item, kind)
    f = pick_file(item, fmt)
    ext = Path(urllib.parse.urlparse(f["url"]).path).suffix.lower() or (".mp4" if item["typ"] == "wideo" else ".jpg")
    if ext not in wl.VIDEO_EXT | wl.IMAGE_EXT:
        ext = ".mp4" if item["typ"] == "wideo" else ".jpg"
    path = wl.cache_dir("stock", "pliki") / f"{item['id'].replace(':', '-')}-{f.get('szer')}x{f.get('wys')}{ext}"
    meta = {k: item.get(k) for k in ("id", "zrodlo", "typ", "strona", "autor", "autor_url", "sek")}
    meta.update({"plik": path.name, "szer": f.get("szer"), "wys": f.get("wys"), "fmt": fmt, "licencja": LICENSES[item["zrodlo"]]})
    if not path.exists() or path.stat().st_size == 0:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, suffix=ext) as tmp:
            tmp.write(_get(f["url"], timeout=180))
        Path(tmp.name).replace(path)
    wl.write_json(path.with_suffix(".json"), meta)
    return _deliver(path, meta, dest)


def _deliver(path: Path, meta: dict, dest: Path | None) -> tuple[Path, dict]:
    if dest:
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / path.name
        if not target.exists():
            try:
                os.link(path, target)   # bez kopiowania bajtów, gdy ten sam dysk
            except OSError:
                import shutil
                shutil.copy2(path, target)
        wl.write_json(target.with_suffix(".json"), meta)
        return target, meta
    return path, meta


# ------------------------------------------------------------------ arkusz podglądów

def contact_sheet(items: list[dict], out: Path, cols: int = 4) -> Path | None:
    """Siatka ponumerowanych podglądów (1…n) do oceny narzędziem vision_analyze."""
    cells = []
    with tempfile.TemporaryDirectory(prefix="jarvo-arkusz-") as tmp:
        tdir = Path(tmp)
        for i, it in enumerate(items, 1):
            if not it.get("podglad"):
                continue
            src = tdir / f"src{i}.jpg"
            try:
                src.write_bytes(_get(it["podglad"], timeout=30))
            except StockError:
                continue
            cell = tdir / f"cell{len(cells):02d}.png"
            label = f"{i}"
            base = ("scale=360:360:force_original_aspect_ratio=decrease,pad=380:400:(ow-iw)/2:(oh-ih)/2+14:color=0x15171C")
            try:
                wl.run(["ffmpeg", "-y", "-i", str(src), "-vf",
                        base + f",drawtext=text='{label}':x=10:y=4:fontsize=26:fontcolor=white:box=1:boxcolor=0xD62D20:boxborderw=6",
                        "-frames:v", "1", str(cell)])
            except wl.FFError:   # FFmpeg bez fontconfig: numeracja wg kolejności (od lewej, rzędami)
                wl.run(["ffmpeg", "-y", "-i", str(src), "-vf", base, "-frames:v", "1", str(cell)])
            cells.append(cell)
        if not cells:
            return None
        rows = (len(cells) + cols - 1) // cols
        out.parent.mkdir(parents=True, exist_ok=True)
        wl.run(["ffmpeg", "-y", "-framerate", "1", "-i", str(tdir / "cell%02d.png"),
                "-vf", f"tile={min(cols, len(cells))}x{rows}:padding=4:color=0x0B0D12", "-frames:v", "1", "-q:v", "3", str(out)])
    return out


# ------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("szukaj", help="szukaj ujęć/zdjęć")
    s.add_argument("zapytanie")
    s.add_argument("--format", default="9:16")
    s.add_argument("--typ", choices=["wideo", "zdjecie"], default="wideo")
    s.add_argument("--ile", type=int, default=8)
    s.add_argument("--min-sek", type=float, default=4.0)
    s.add_argument("--arkusz", help="zapisz siatkę ponumerowanych podglądów (JPG) do oceny okiem")
    s.add_argument("--json", action="store_true")
    p = sub.add_parser("pobierz", help="pobierz ujęcie po id (pexels:123 / pixabay:456)")
    p.add_argument("id", nargs="+")
    p.add_argument("--format", default="9:16")
    p.add_argument("--typ", choices=["wideo", "zdjecie"], default="wideo")
    p.add_argument("--do", help="katalog docelowy (np. out/wideo/src); domyślnie tylko cache")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "szukaj":
            items = search(args.zapytanie, args.typ, args.format, args.ile, args.min_sek)
            sheet = contact_sheet(items, Path(args.arkusz)) if args.arkusz else None
            if args.json:
                print(json.dumps({"wyniki": [{k: v for k, v in it.items() if k != "pliki"} for it in items],
                                  "arkusz": str(sheet) if sheet else None}, ensure_ascii=False, indent=1))
            else:
                for i, it in enumerate(items, 1):
                    dur = f" {it['sek']}s" if it.get("sek") else ""
                    print(f"{i:>2}. {it['id']:<18} {it.get('szer')}×{it.get('wys')}{dur}  {it.get('autor') or ''}  {it.get('strona') or ''}")
                if sheet:
                    print(f"Arkusz: {sheet}  (numery = kolejność powyżej)")
                if not items:
                    print("Brak wyników: spróbuj prostszego zapytania po angielsku (np. 'coffee beans').")
            return 0
        for item_id in args.id:
            path, meta = download(item_id, args.format, args.typ, Path(args.do) if args.do else None)
            print(f"{path}  ({meta.get('autor') or '?'}, {meta.get('zrodlo')})")
        return 0
    except StockError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
