#!/usr/bin/env python3
"""Ekstrakcja systemu designu ze strony (dembrandt) do brand kitu.

    python3 brand_extract.py <url> <slug> [--pages 3] [--kit <ścieżka w skarbcu>]

Zapisuje do <skarbiec>/brands/<slug>/ (skarbiec: JARVO_KNOWLEDGE_DIR, w obrazie /opt/data/jarvo/knowledge):
  DESIGN.md (format Google DESIGN.md), tokens.json (W3C DTCG), dembrandt.json (surowe dane),
  wcag.json (kontrast), screenshots/viewport.png
--kit zmienia katalog docelowy (względny w skarbcu), np. strona referencyjna skilla inspiracje-stron:
  --kit inspiracje/strony/nieruchomosci/example.pl  (bez katalogu logo/ i bez szablonu BRAND.md: to nie marka klienta)
Na końcu JSON: {"kit": <katalog z „/”>, "design_md": true|false, "tokens": true|false}.

Ta sama logika co dawny brand_extract.sh (docs/NATYWNIE.md F02). dembrandt uruchamia Node na skrypcie paczki
z NODE_PATH (audit.program_npm, bez .cmd), z --no-sandbox tylko tam, gdzie piaskownica Chromium nie ruszy
(audit.bez_piaskownicy). dembrandt otwiera Chromium przez playwright-core bez ścieżki programu, więc szuka go
w PLAYWRIGHT_BROWSERS_PATH (chromium_headless_shell-<rewizja z browsers.json>). Gdy instalacja go tam nie położyła,
skrypt na czas pracy wskazuje chrome-headless-shell z CHROME_PATH (dowiązanie w katalogu roboczym: junction na
Windows, symlink gdzie indziej), a bez żadnego Chromium kończy się błędem: dembrandt pobrałby wtedy przeglądarkę
z sieci bez sumy.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit import bez_piaskownicy, chrome_path, katalog_paczki, program_npm, utf8  # noqa: E402

UZYCIE = "Użycie: brand_extract.py <url> <slug> [--pages N] [--kit <ścieżka w skarbcu>]"
SKARBIEC_OBRAZU = "/opt/data/jarvo/knowledge"


def blad(tekst: str, kod: int = 2) -> int:
    print(tekst, file=sys.stderr)
    return kod


def rewizja_headless_shell() -> str | None:
    """Rewizja chrome-headless-shell, której szuka playwright-core z NODE_PATH (browsers.json, np. 1243)."""
    katalog = katalog_paczki("playwright-core")
    try:
        dane = json.loads((katalog / "browsers.json").read_text(encoding="utf-8")) if katalog else {}
    except (OSError, ValueError):
        return None
    return next((str(b.get("revision")) for b in dane.get("browsers") or []
                 if b.get("name") == "chromium-headless-shell" and b.get("revision")), None)


def _dowiaz(link: Path, cel: Path) -> None:
    """Katalog-dowiązanie bez uprawnień administratora: junction na Windows, symlink gdzie indziej."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(cel), str(link))
    else:
        os.symlink(cel, link, target_is_directory=True)


def przegladarka_dembrandt(praca: Path, env: dict) -> tuple[dict, Path | None]:
    """Środowisko dembrandt z Chromium, które playwright-core znajdzie bez pobierania. Zwraca też dowiązanie do
    usunięcia przed sprzątaniem katalogu roboczego (żeby rmtree nie zszedł do instalacji Chromium)."""
    rewizja = rewizja_headless_shell()
    if not rewizja:
        return env, None                     # bez playwright-core w NODE_PATH dembrandt i tak się nie uruchomi
    nazwa = f"chromium_headless_shell-{rewizja}"
    pbp = env.get("PLAYWRIGHT_BROWSERS_PATH") or ""
    if pbp and (Path(pbp) / nazwa).is_dir():
        return env, None                     # instalacja (albo obraz Hermesa) ma już ten układ
    chrome = chrome_path()
    prawdziwy = Path(os.path.realpath(chrome)) if chrome else None
    if prawdziwy is None or not prawdziwy.is_file() or not prawdziwy.parent.name.startswith("chrome-headless-shell-"):
        raise RuntimeError("brak Chromium dla dembrandt: ustaw CHROME_PATH na chrome-headless-shell z instalacji "
                           f"(albo PLAYWRIGHT_BROWSERS_PATH z {nazwa}); bez tego dembrandt pobrałby przeglądarkę "
                           "z sieci bez sumy")
    katalog = praca / "przegladarki"
    link = katalog / nazwa
    _dowiaz(link, prawdziwy.parent.parent)
    return {**env, "PLAYWRIGHT_BROWSERS_PATH": str(katalog)}, link


def najnowszy(wzor: str, katalog: Path) -> Path | None:
    pliki = sorted(katalog.glob(wzor), key=lambda p: p.stat().st_mtime, reverse=True)
    return pliki[0] if pliki else None


def main(argv: list[str] | None = None) -> int:
    utf8()
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[0] in ("-h", "--help"):
        return blad(UZYCIE)
    url, slug, reszta = args[0], args[1], args[2:]
    strony, kit_rel = "3", f"brands/{slug}"
    while reszta:
        if reszta[0] in ("--pages", "--kit") and len(reszta) > 1:
            if reszta[0] == "--pages":
                strony = reszta[1]
            else:
                kit_rel = reszta[1]
            reszta = reszta[2:]
        else:
            return blad(UZYCIE)
    if (not kit_rel or kit_rel.startswith("/") or ".." in kit_rel or "\\" in kit_rel
            or re.match(r"[A-Za-z]:", kit_rel)):
        return blad('--kit: ścieżka względna w skarbcu, bez ".."')
    dembrandt = program_npm("dembrandt")
    if not dembrandt:
        return blad("brak dembrandt (paczka npm floty w NODE_PATH, infra/node/package.json)", 1)

    skarbiec = Path(os.environ.get("JARVO_KNOWLEDGE_DIR") or SKARBIEC_OBRAZU)
    kit = skarbiec / kit_rel.rstrip("/")
    marka = kit_rel.startswith("brands/")
    (kit / "screenshots").mkdir(parents=True, exist_ok=True)
    if marka:
        (kit / "logo").mkdir(parents=True, exist_ok=True)

    praca = Path(tempfile.mkdtemp(prefix="brand_extract-"))
    link = None
    try:
        try:
            env, link = przegladarka_dembrandt(praca, dict(os.environ))
        except RuntimeError as e:
            return blad(f"✗ {e}", 1)
        wspolne = [*(["--no-sandbox"] if bez_piaskownicy() else []), "--crawl", strony, "--slow"]
        print("▶ dembrandt: surowe dane", file=sys.stderr, flush=True)
        with open(kit / "dembrandt.json", "wb") as f:
            kod = subprocess.run([*dembrandt, url, *wspolne, "--json-only"], cwd=praca, env=env,
                                 stdin=subprocess.DEVNULL, stdout=f).returncode
        if kod:
            return blad(f"✗ dembrandt zakończył się kodem {kod}", kod)
        print("▶ dembrandt: DESIGN.md + tokeny DTCG + WCAG + zrzut", file=sys.stderr, flush=True)
        subprocess.run([*dembrandt, url, *wspolne, "--design-md", "--dtcg", "--wcag", "--screenshot",
                        str(kit / "screenshots" / "viewport.png")], cwd=praca, env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL)

        # dembrandt zapisuje eksporty do output/<domena>/ w katalogu roboczym
        if design := najnowszy("output/*/DESIGN.md", praca):
            shutil.copyfile(design, kit / "DESIGN.md")
        if tokeny := najnowszy("output/*/*.tokens.json", praca):
            shutil.copyfile(tokeny, kit / "tokens.json")
    finally:
        if link is not None:                 # najpierw samo dowiązanie: rmtree nie może zejść do Chromium instalacji
            try:
                if os.name == "nt":
                    os.rmdir(link)           # junction: usuwa samo dowiązanie, nie katalog docelowy
                else:
                    os.unlink(link)
            except OSError:
                pass
        if link is None or not os.path.lexists(link):
            shutil.rmtree(praca, ignore_errors=True)

    try:
        d = json.loads((kit / "dembrandt.json").read_text(encoding="utf-8"))
        wcag = (d.get("wcag") or d.get("contrast") or {}) if isinstance(d, dict) else {}
        (kit / "wcag.json").write_text(json.dumps(wcag, ensure_ascii=False, indent=1), encoding="utf-8")
    except (OSError, ValueError):
        pass
    szablon = skarbiec / "brands" / "_szablon" / "BRAND.md"
    if marka and not (kit / "BRAND.md").is_file() and szablon.is_file():
        shutil.copyfile(szablon, kit / "BRAND.md")

    print(json.dumps({"kit": kit.as_posix(), "design_md": (kit / "DESIGN.md").is_file(),
                      "tokens": (kit / "tokens.json").is_file()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
