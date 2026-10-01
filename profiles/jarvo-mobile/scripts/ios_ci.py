#!/usr/bin/env python3
"""iPhone bez Maca: testy i zrzuty aplikacji w symulatorze iOS na GitHub Actions (runner macos-26), sterowane z kontenera.

    ios_ci.py przygotuj <app>                                   # workflow .github/workflows/jarvo-ios.yml w repo aplikacji
    ios_ci.py wypchnij <app> --repo wlasciciel/nazwa             # kod na gałąź jarvo/ci repozytorium właściciela
    ios_ci.py uruchom <app> --repo wlasciciel/nazwa [--tryb expo-go|build] [--trasy / /wiecej] [--czekaj 45]
    ios_ci.py wynik <app> --repo wlasciciel/nazwa --run <id>     # pobranie artefaktu z zakończonego przebiegu

Wymaga `GITHUB_TOKEN` w .env profilu: token „fine-grained” właściciela tylko do repozytorium aplikacji, uprawnienia
Contents: read and write (gałąź jarvo/ci), Actions: read and write. Token idzie do gita przez zmienne środowiska
(GIT_CONFIG_*), nigdy w argumentach polecenia. Repo publiczne: minuty macOS za darmo; prywatne: płatne ponad limit.

Wynik: `<app>/out/jakosc/ios/` (zrzuty jasny / ciemny / duża czcionka, logi) i `wynik.json` w formacie warstw bramki.
Kod: 0 = OK, 1 = błędy w testach albo przebieg nieudany, 2 = złe wejście, 3 = brak tokenu.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

API = os.environ.get("GITHUB_API", "https://api.github.com")
WORKFLOW = "jarvo-ios.yml"
GALAZ = "jarvo/ci"
SZABLON = Path(__file__).resolve().parent.parent / "templates" / "ci" / WORKFLOW


class BrakTokenu(Exception):
    pass


def token() -> str:
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if not t:
        raise BrakTokenu("brak GITHUB_TOKEN (token fine-grained właściciela do repozytorium aplikacji: Contents i Actions "
                         "read/write) w .env profilu jarvo-mobile")
    return t


def api(metoda: str, sciezka: str, dane: dict | None = None, surowe: bool = False):
    req = urllib.request.Request(f"{API}{sciezka}", method=metoda,
                                 data=json.dumps(dane).encode() if dane is not None else None,
                                 headers={"Authorization": f"Bearer {token()}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "jarvo-mobile"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (API GitHuba z kodu)
            tresc = r.read()
            if surowe:
                return tresc
            return json.loads(tresc) if tresc else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub {metoda} {sciezka}: HTTP {e.code} {e.read(300).decode(errors='replace')}") from e


def przygotuj(app: Path) -> Path:
    cel = app / ".github" / "workflows" / WORKFLOW
    cel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SZABLON, cel)
    return cel


def wypchnij(app: Path, repo: str) -> str:
    """Commit bieżącego stanu i wypchnięcie na gałąź jarvo/ci (nie main właściciela)."""
    basic = base64.b64encode(f"x-access-token:{token()}".encode()).decode()      # jak actions/checkout
    env = {**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
           "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}", "GIT_TERMINAL_PROMPT": "0"}
    git = lambda *a: subprocess.run(["git", *a], cwd=app, env=env, capture_output=True, text=True, timeout=300)  # noqa: E731
    if not (app / ".git").exists():
        git("init", "-q")
    git("add", "-A")
    git("-c", "user.name=Jarvo", "-c", "user.email=jarvo@localhost", "commit", "-q", "-m", "jarvo: stan do testów iOS")
    r = git("push", "--force", f"https://github.com/{repo}.git", f"HEAD:refs/heads/{GALAZ}")
    if r.returncode != 0:
        raise RuntimeError(f"git push: {r.stderr.strip()[-400:]}")
    return git("rev-parse", "HEAD").stdout.strip()


def uruchom(repo: str, tryb: str, trasy: list[str]) -> int:
    od = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 5))
    odp = api("POST", f"/repos/{repo}/actions/workflows/{WORKFLOW}/dispatches",
              {"ref": GALAZ, "inputs": {"tryb": tryb, "trasy": " ".join(trasy)}, "return_run_details": True})
    if isinstance(odp, dict) and odp.get("workflow_run_id"):
        return int(odp["workflow_run_id"])
    for _ in range(30):                          # starsze API: 204 bez treści → szukamy przebiegu po czasie
        time.sleep(4)
        runs = api("GET", f"/repos/{repo}/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&branch={GALAZ}"
                          f"&created=%3E%3D{od}&per_page=5").get("workflow_runs", [])
        if runs:
            return int(runs[0]["id"])
    raise RuntimeError("przebieg nie pojawił się w ciągu 2 minut")


def czekaj(repo: str, run_id: int, minuty: int) -> dict:
    koniec = time.time() + minuty * 60
    while time.time() < koniec:
        run = api("GET", f"/repos/{repo}/actions/runs/{run_id}")
        if run.get("status") == "completed":
            return run
        time.sleep(20)
    raise RuntimeError(f"przebieg {run_id} nie skończył się w {minuty} min (sprawdź kolejkę runnerów macOS)")


def wynik(app: Path, repo: str, run_id: int, run: dict | None = None) -> dict:
    run = run or api("GET", f"/repos/{repo}/actions/runs/{run_id}")
    out = app / "out" / "jakosc" / "ios"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    arts = api("GET", f"/repos/{repo}/actions/runs/{run_id}/artifacts").get("artifacts", [])
    art = next((a for a in arts if a["name"] == "jarvo-ios"), None)
    if art:
        dane = api("GET", f"/repos/{repo}/actions/artifacts/{art['id']}/zip", surowe=True)
        with zipfile.ZipFile(io.BytesIO(dane)) as z:
            z.extractall(out)
    return ocen_artefakt(out, run)


def ocen_artefakt(out: Path, run: dict) -> dict:
    pliki = sorted(p.name for p in out.glob("*.png"))
    bledy = (out / "bledy.txt").read_text(encoding="utf-8", errors="replace").splitlines() if (out / "bledy.txt").exists() else []
    puste = [p for p in pliki if (out / p).stat().st_size < 15_000]      # zrzut prawie jednolity = pusty albo czarny ekran
    wyniki = []
    for wariant, opis in (("jasny", "start i trasy w trybie jasnym"), ("ciemny", "tryb ciemny"),
                          ("duza-czcionka", "największa czcionka systemowa (Dynamic Type)")):
        z = [p for p in pliki if p.startswith(wariant + "-")]
        if not z:
            wyniki.append({"id": wariant, "warstwa": "ios", "status": "not_run", "obserwacje": {}, "dlaczego": f"brak zrzutów: {opis}"})
            continue
        pz = [p for p in z if p in puste]
        wyniki.append({"id": wariant, "warstwa": "ios", "status": "blad" if pz else "ok", "obserwacje": {"zrzuty": z, "puste": pz},
                       "dlaczego": "pusty albo czarny ekran" if pz else ""})
    if bledy:
        wyniki.append({"id": "logi", "warstwa": "ios", "status": "blad", "obserwacje": {"bledy": bledy[:10]},
                       "dlaczego": "awaria albo błąd JS w logach symulatora"})
    if run.get("conclusion") not in ("success", None):
        wyniki.append({"id": "przebieg", "warstwa": "ios", "status": "blad", "obserwacje": {"url": run.get("html_url")},
                       "dlaczego": f"przebieg CI: {run.get('conclusion')}"})
    raport = {"run": run.get("id"), "url": run.get("html_url"), "wyniki": wyniki, "zrzuty": pliki,
              "podsumowanie": f"iOS: {sum(w['status'] == 'ok' for w in wyniki)} ok, "
                              f"{sum(w['status'] == 'blad' for w in wyniki)} błędów, {len(pliki)} zrzutów"}
    (out / "wynik.json").write_text(json.dumps(raport, ensure_ascii=False, indent=2), encoding="utf-8")
    return raport


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("przygotuj").add_argument("app")
    for n in ("wypchnij", "uruchom", "wynik"):
        x = sub.add_parser(n)
        x.add_argument("app")
        x.add_argument("--repo", required=True)
        if n == "uruchom":
            x.add_argument("--tryb", default="expo-go", choices=["expo-go", "build"])
            x.add_argument("--trasy", nargs="*", default=["/", "/wiecej", "/kontakt", "/prywatnosc"])
            x.add_argument("--czekaj", type=int, default=45)
        if n == "wynik":
            x.add_argument("--run", type=int, required=True)
    args = ap.parse_args(argv)
    app = Path(args.app).resolve()
    try:
        if args.cmd == "przygotuj":
            print(przygotuj(app))
            return 0
        if args.cmd == "wypchnij":
            print(f"✓ {args.repo}@{GALAZ}: {wypchnij(app, args.repo)}")
            return 0
        if args.cmd == "uruchom":
            run_id = uruchom(args.repo, args.tryb, args.trasy)
            print(f"… przebieg {run_id} (https://github.com/{args.repo}/actions/runs/{run_id})", file=sys.stderr)
            r = wynik(app, args.repo, run_id, czekaj(args.repo, run_id, args.czekaj))
        else:
            r = wynik(app, args.repo, args.run)
        print(r["podsumowanie"])
        return 1 if any(w["status"] == "blad" for w in r["wyniki"]) else 0
    except BrakTokenu as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    except RuntimeError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
