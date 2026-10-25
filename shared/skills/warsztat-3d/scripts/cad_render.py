"""Podgląd modelu GLB w Chromium przez Playwright dla Pythona: PNG albo klatki filmu obrotu. Odpowiednik
cad_render.cjs, gdy Node nie widzi paczek three i playwright-core narzędzi npm floty (np. proces bez NODE_PATH, poza
środowiskiem Jarva); Three.js bierze wtedy cad.py z katalogu narzędzi npm instalacji. Woła go cad.py
(nie Ty):  <python z playwright> -I cad_render.py <zadanie.json>   → wynik JSON w ostatniej linii stdout

    {"tryb": "png", "glb", "out", "w", "h", "kat", "wysokosc", "kolor", "tlo", "siatka", "krawedzie", "skala",
     "three": <katalog paczki three>, "chrome": <chrome-headless-shell z instalacji>}
    {"tryb": "obrot", "glb", "katalog", "klatek", ...}    → katalog/k00000.png … (360° w `klatek` krokach)

Strona (cad_podglad.html), Three.js i model idą z adresu http://cad.jarvo/ przez page.route; każdy inny adres jest
odrzucany, więc podgląd nie wychodzi do sieci. WebGL na procesorze (SwiftShader), jedna przeglądarka (SwiftShader sam
bierze wszystkie rdzenie). Piaskownica Chromium włączona (Playwright domyślnie dodaje --no-sandbox, więc
chromium_sandbox=True), poza Linuksem jako root, w kontenerze albo z zakazem przestrzeni nazw użytkownika bez profilu
AppArmor (Ubuntu 23.10+), jak audit.py Weba.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

TU = Path(__file__).resolve().parent
HOST = "cad.jarvo"
TYPY = {".js": "text/javascript", ".mjs": "text/javascript", ".html": "text/html", ".glb": "model/gltf-binary",
        ".json": "application/json", ".wasm": "application/wasm"}
ARGS = ["--enable-webgl", "--ignore-gpu-blocklist", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
CZAS_STRONY_MS = 120_000


def bez_piaskownicy(platforma: str | None = None) -> bool:
    """Czy Chromium potrzebuje --no-sandbox: tylko Linux jako root, w kontenerze Dockera (/.dockerenv) albo z zakazem
    przestrzeni nazw użytkownika bez profilu AppArmor (Ubuntu 23.10+). Windows i macOS: piaskownica zawsze działa."""
    if not (platforma or sys.platform).startswith("linux"):
        return False
    if os.geteuid() == 0 or Path("/.dockerenv").exists():
        return True
    try:
        return Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns").read_text(encoding="utf-8").strip() == "1"
    except OSError:
        return False


def plik_adresu(adres: str, z: dict) -> Path | None:
    """Plik dla adresu strony podglądu: /, /model.glb, /three/… z katalogu paczki three; poza nim None."""
    u = urlsplit(adres)
    if u.hostname != HOST:
        return None
    sciezka = unquote(u.path)
    if sciezka == "/":
        return TU / "cad_podglad.html"
    if sciezka == "/model.glb":
        return Path(z["glb"])
    if sciezka.startswith("/three/"):
        korzen = Path(z["three"]).resolve()
        p = (korzen / sciezka[len("/three/"):]).resolve()
        if korzen in p.parents:
            return p
    return None


def opcje(z: dict) -> dict:
    return {"w": z["w"], "h": z["h"], "kat": z["kat"], "wysokosc": z["wysokosc"], "kolor": z.get("kolor"),
            "tlo": z.get("tlo"), "siatka": z.get("siatka"), "krawedzie": z.get("krawedzie"), "skala": z.get("skala"),
            "obrot": z["tryb"] == "obrot"}


def renderuj(z: dict) -> dict:
    from playwright.sync_api import Error as BladPlaywrighta
    from playwright.sync_api import sync_playwright

    bledy: list[str] = []
    with sync_playwright() as p:
        przegladarka = p.chromium.launch(executable_path=z.get("chrome") or None, args=ARGS, headless=True,
                                         chromium_sandbox=not bez_piaskownicy())
        try:
            strona = przegladarka.new_page(viewport={"width": z["w"], "height": z["h"]},
                                           device_scale_factor=z.get("skala") or 1)
            strona.on("pageerror", lambda e: bledy.append(str(e)))
            strona.on("console", lambda m: bledy.append(m.text) if m.type == "error" else None)

            def obsluz(route) -> None:
                adres = route.request.url
                if urlsplit(adres).hostname != HOST:
                    route.abort()
                    return
                plik = plik_adresu(adres, z)
                if plik is None or not plik.is_file():
                    route.fulfill(status=404, body="brak")
                    return
                route.fulfill(status=200, body=plik.read_bytes(),
                              content_type=TYPY.get(plik.suffix.lower(), "application/octet-stream"))

            strona.route("**/*", obsluz)
            strona.add_init_script(f"window.__opcje = {json.dumps(opcje(z))};")
            strona.goto(f"http://{HOST}/", wait_until="load")
            try:
                strona.wait_for_function("window.__ready === true", timeout=CZAS_STRONY_MS)
            except BladPlaywrighta as e:
                raise RuntimeError(f"podgląd się nie wczytał: {'; '.join(dict.fromkeys(bledy)) or e}") from None
            info = strona.evaluate("() => window.__info")
            t0 = time.monotonic()
            if z["tryb"] == "png":
                strona.screenshot(path=z["out"], omit_background=not z.get("tlo"))
                wynik = {"plik": z["out"]}
            elif z["tryb"] == "obrot":
                for i in range(int(z["klatek"])):
                    strona.evaluate("k => window.__ustaw(k)", z["kat"] + 360 * i / z["klatek"])
                    strona.screenshot(path=str(Path(z["katalog"]) / f"k{i:05d}.png"))
                wynik = {"katalog": z["katalog"]}
            else:
                raise RuntimeError(f"nieznany tryb {z['tryb']}")
            return {**wynik, "info": info, "render_s": round(time.monotonic() - t0, 3),
                    "bledy": list(dict.fromkeys(bledy))}
        finally:
            przegladarka.close()


def main(argv: list[str]) -> int:
    z = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    try:
        wynik = renderuj(z)
    except ImportError:
        print("brak paczki playwright w tym Pythonie (natywnie: venv narzędzi Jarva)", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - błąd przeglądarki albo strony wraca do cad.py jako komunikat
        print(str(e).strip()[-800:] or type(e).__name__, file=sys.stderr)
        return 1
    print(json.dumps(wynik, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
