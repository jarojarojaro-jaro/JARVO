#!/usr/bin/env python3
"""Audyt strony: Lighthouse (mobile + desktop), axe-core, linkinator, seo_check, security_check, zrzuty.

    python3 audit.py <url> [outdir=out/audyt]

Każde narzędzie działa niezależnie: awaria jednego nie przerywa reszty i trafia do summary.json (na stdout), a status
każdego narzędzia na stderr. Raporty narzędzi leżą obok: lighthouse-{mobile,desktop}.report.{json,html}, axe.json,
links.json, seo.json, security.json, screenshots/ i <narzędzie>.log z wyjściem.

Ta sama logika co dawny audit.sh, ale w Pythonie (bash 3.2 na macOS nie zna tablic asocjacyjnych, a Windows nie ma
basha poza Git Bash; docs/NATYWNIE.md F02). Narzędzia npm (lighthouse, linkinator) uruchamia Node na skrypcie `bin`
z package.json paczki znalezionej w NODE_PATH, a nie przez nakładki z node_modules/.bin: na Windows to pliki .cmd,
a cmd.exe rozbija adres z „&” na dwa polecenia. Chromium: CHROME_PATH (chrome-headless-shell z instalacji; w obrazie
także /etc/hermes/agent-browser-executable-path). `--no-sandbox` tylko tam, gdzie piaskownica Chromium nie ruszy:
root, kontener, Linux z apparmor_restrict_unprivileged_userns=1 (jak Hermes, tools/browser_tool_session.py).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME_OBRAZU = Path("/etc/hermes/agent-browser-executable-path")      # obraz Hermesa zapisuje tu swoje Chromium


# ------------------------------------------------------------------ wspólne z brand_extract.py

def chrome_path() -> str | None:
    """Chromium skryptów: CHROME_PATH, w obrazie Hermesa zapasowo ścieżka z /etc/hermes."""
    if os.environ.get("CHROME_PATH"):
        return os.environ.get("CHROME_PATH")
    try:
        return CHROME_OBRAZU.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def bez_piaskownicy(platforma: str | None = None) -> bool:
    """Czy Chromium potrzebuje --no-sandbox: tylko Linux jako root, w kontenerze albo z zakazem przestrzeni nazw
    użytkownika bez profilu AppArmor (Ubuntu 23.10+). Windows i macOS: piaskownica zawsze działa."""
    if not (platforma or sys.platform).startswith("linux"):
        return False
    if os.geteuid() == 0 or Path("/.dockerenv").exists():
        return True
    try:
        if "docker" in Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="replace"):
            return True
    except OSError:
        pass
    try:
        return Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns").read_text(encoding="utf-8").strip() == "1"
    except OSError:
        return False


def katalog_paczki(pakiet: str) -> Path | None:
    """Katalog paczki npm floty z NODE_PATH (infra/node: w obrazie /opt/jarvo/node/node_modules)."""
    for katalog in filter(None, os.environ.get("NODE_PATH", "").split(os.pathsep)):
        if (Path(katalog) / pakiet / "package.json").is_file():
            return Path(katalog) / pakiet
    return None


def program_npm(pakiet: str, nazwa: str | None = None) -> list[str] | None:
    """Polecenie narzędzia npm: [node, skrypt `bin` z package.json paczki z NODE_PATH]; zapas: program z PATH."""
    nazwa = nazwa or pakiet
    node = shutil.which("node")
    katalog = katalog_paczki(pakiet)
    if node and katalog:
        try:
            bin_ = json.loads((katalog / "package.json").read_text(encoding="utf-8")).get("bin")
        except (OSError, ValueError):
            bin_ = None
        skrypt = bin_ if isinstance(bin_, str) else (bin_ or {}).get(nazwa)
        if skrypt and (katalog / skrypt).is_file():
            return [node, str(katalog / skrypt)]
    sciezka = shutil.which(nazwa)
    return [sciezka] if sciezka else None


# ------------------------------------------------------------------ audyt

class Audyt:
    def __init__(self, url: str, out: Path):
        self.url, self.out = url, out
        self.status: dict[str, str] = {}

    def _start(self, nazwa: str, argv: list[str] | None) -> bool:
        print(f"▶ {nazwa}", file=sys.stderr, flush=True)
        if argv is None:
            self.status[nazwa] = "brak programu (NODE_PATH bez paczki npm albo brak node)"
        return argv is not None

    def run(self, nazwa: str, argv: list[str] | None) -> None:
        """Narzędzie z wyjściem i błędami w <nazwa>.log; kod różny od 0 = błąd."""
        if not self._start(nazwa, argv):
            return
        log = self.out / f"{nazwa}.log"
        try:
            with open(log, "wb") as f:
                kod = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT).returncode
        except OSError as e:
            log.write_text(f"{argv[0]}: {e}\n", encoding="utf-8")
            kod = 127
        self.status[nazwa] = "ok" if kod == 0 else f"błąd (zob. {log.as_posix()})"

    def run_findings(self, nazwa: str, argv: list[str] | None, kopia: str | None = None) -> None:
        """Jak run, ale kod 1 z poprawnym JSON-em na wyjściu = narzędzie działa i coś znalazło (seo, linki, security).
        Wyjście w <nazwa>.log (i w `kopia`), błędy w <nazwa>.err."""
        if not self._start(nazwa, argv):
            return
        log, err = self.out / f"{nazwa}.log", self.out / f"{nazwa}.err"
        try:
            with open(log, "wb") as f_out, open(err, "wb") as f_err:
                kod = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=f_out, stderr=f_err).returncode
        except OSError as e:
            err.write_text(f"{argv[0]}: {e}\n", encoding="utf-8")
            kod = 127
        if kod == 0:
            self.status[nazwa] = "ok"
        elif kod == 1 and _json(log) is not None:
            self.status[nazwa] = "ok (są znaleziska)"
        else:
            self.status[nazwa] = f"błąd (zob. {log.as_posix()}, {err.as_posix()})"
        if kopia and log.is_file():
            shutil.copyfile(log, self.out / kopia)


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def flagi_chrome() -> str:
    return " ".join(["--headless=new", *(["--no-sandbox"] if bez_piaskownicy() else []), "--disable-gpu"])


def podsumowanie(out: Path) -> dict:
    summary = {"lighthouse": {}, "axe": None, "links": None, "seo": None, "security": None, "screenshots": None}
    for ff in ("mobile", "desktop"):
        d = _json(out / f"lighthouse-{ff}.report.json")
        if not isinstance(d, dict):
            continue
        cats = {k: round((v.get("score") or 0) * 100) for k, v in d.get("categories", {}).items()}
        audits = d.get("audits", {})
        vit = {k: audits.get(k, {}).get("displayValue") for k in ("largest-contentful-paint", "cumulative-layout-shift",
                                                                   "total-blocking-time", "first-contentful-paint")}
        # skrypty i zasoby firm trzecich (analityka, czaty, piksele, fonty z CDN): waga i czas pracy na wątku głównym;
        # Lighthouse 13: `third-parties-insight` (mainThreadTime), starsze: `third-party-summary` (blockingTime)
        tpa = audits.get("third-parties-insight") or audits.get("third-party-summary") or {}
        tp = (tpa.get("details") or {}).get("items") or []

        def nazwa(e):
            return e.get("text") if isinstance(e, dict) else e
        firmy = sorted(({"firma": nazwa(i.get("entity")), "kb": round((i.get("transferSize") or 0) / 1024),
                         "watek_ms": round(i.get("mainThreadTime", i.get("blockingTime")) or 0)} for i in tp),
                       key=lambda x: (-x["watek_ms"], -x["kb"]))
        trzecie = {"kb": sum(x["kb"] for x in firmy), "watek_ms": sum(x["watek_ms"] for x in firmy), "firmy": firmy[:5]}
        summary["lighthouse"][ff] = {"scores": cats, "vitals": vit,
                                     "strona_kb": round((audits.get("total-byte-weight", {}).get("numericValue") or 0) / 1024),
                                     "firmy_trzecie": trzecie}
    wyciagi = {
        "axe": ("axe.json", lambda d: d.get("by_impact")),
        "seo": ("seo.json", lambda d: d.get("summary")),
        "security": ("security.json", lambda d: d.get("podsumowanie")),
        "screenshots": ("screenshots/screenshots.json",
                        lambda d: [{"width": r["width"], "horizontal_scroll": r["horizontal_scroll"]}
                                   for r in d.get("results", [])]),
    }
    for klucz, (plik, wyciag) in wyciagi.items():
        f = out / plik
        if f.exists():
            try:
                summary[klucz] = wyciag(json.loads(f.read_text(encoding="utf-8")))
            except Exception as exc:  # noqa: BLE001 (nieczytelny raport jednego narzędzia nie psuje reszty)
                summary[klucz] = f"nieczytelne: {exc}"
    f = out / "links.json"
    if f.exists():
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            broken = [link for link in d.get("links", []) if link.get("state") == "BROKEN"]
            summary["links"] = {"checked": len(d.get("links", [])), "broken": len(broken),
                                "examples": [b.get("url") for b in broken[:10]]}
        except Exception as exc:  # noqa: BLE001
            summary["links"] = f"nieczytelne: {exc}"
    return summary


def utf8() -> None:
    """Wyjście w UTF-8 także bez PYTHONUTF8 (Hermes czyta UTF-8; strona kodowa Windows nie zna „▶”)."""
    for strumien in (sys.stdout, sys.stderr):
        try:
            strumien.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    utf8()
    if not args or args[0] in ("-h", "--help"):
        print("Użycie: audit.py <url> [outdir]", file=sys.stderr)
        return 2
    url = args[0]
    out = Path(args[1] if len(args) > 1 else "out/audyt")
    out.mkdir(parents=True, exist_ok=True)
    chrome = chrome_path()
    if chrome:
        os.environ["CHROME_PATH"] = chrome             # Lighthouse (chrome-launcher) i skrypty .cjs biorą ją z env
    node = shutil.which("node")
    a = Audyt(url, out)
    lh = program_npm("lighthouse")
    wspolne = [url, "--quiet", f"--chrome-flags={flagi_chrome()}"]
    raporty = ["--output=json", "--output=html"]
    a.run("lighthouse-mobile", lh and [*lh, *wspolne, *raporty, f"--output-path={out / 'lighthouse-mobile'}",
                                       "--form-factor=mobile"])
    a.run("lighthouse-desktop", lh and [*lh, *wspolne, "--preset=desktop", *raporty,
                                        f"--output-path={out / 'lighthouse-desktop'}"])
    a.run("axe", node and [node, str(HERE / "a11y.cjs"), url, str(out / "axe.json")])
    linkinator = program_npm("linkinator")
    poczatek = url[:-1] if url.endswith("/") else url                 # tylko linki tej strony (jak ${URL%/})
    a.run_findings("links", linkinator and [*linkinator, url, "--recurse", "--format", "JSON", "--timeout", "15000",
                                            "--concurrency", "10", "--skip", f"^(?!{poczatek})"], kopia="links.json")
    a.run_findings("seo", [sys.executable, str(HERE / "seo_check.py"), url, "--json"], kopia="seo.json")
    a.run_findings("security", [sys.executable, str(HERE / "security_check.py"), "url", url, "--json"],
                   kopia="security.json")
    a.run("screenshots", node and [node, str(HERE / "screenshots.cjs"), url, str(out / "screenshots")])

    summary = podsumowanie(out)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("Status narzędzi:", file=sys.stderr)
    for k, v in a.status.items():
        print(f"  {k}: {v}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
