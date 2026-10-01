#!/usr/bin/env python3
"""Aplikacja Expo z szablonu JARVO: założenie, konfiguracja, kontrole, eksport webowy, podgląd w HQ i w Expo Go.

    aplikacja.py konfiguracja > out/aplikacja.yaml                 # szablon tożsamości aplikacji i danych firmy
    aplikacja.py nowa <katalog> --aplikacja out/aplikacja.yaml --zgodnosc out/zgodnosc.yaml [--logo logo.png|svg]
                 [--bez-instalacji]
    aplikacja.py ustaw <katalog> --aplikacja … --zgodnosc … [--logo …]   # ponownie: dane, kolory, ikony, uprawnienia
    aplikacja.py sprawdz <katalog> [--bez-sieci] [--json]               # typy, lint, wersje SDK, expo-doctor, zasady JARVO
    aplikacja.py eksport <katalog> [--baza /sciezka]                    # wersja webowa do dist-web/
    aplikacja.py podglad <katalog> [--trasy / /wiecej …] [--bez-eksportu] # link w HQ (:9120) + zrzuty iPhone i Pixel, jasny i ciemny
    aplikacja.py expo-go <katalog> [--kanal podglad] [--wiadomosc …]     # EAS Update + link i kod QR do Expo Go (A1, organizacja właściciela)

Szablon: `$HERMES_HOME/templates/expo-jarvo` (Expo SDK 57, expo-router, elementy zgodności ze sklepami od pierwszego
dnia). Profil zgodności: `zgodnosc.py`. Kolory: z koloru marki powstaje paleta jasna i ciemna z kontrastem WCAG AA
(4,5:1) dla tekstu i przycisków. Ikony i ekran startowy: `ikony.cjs` (sharp) z logo albo z inicjałów.

Kod wyjścia: 0 = OK, 1 = błąd albo nieudana kontrola, 2 = złe wejście.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zgodnosc  # noqa: E402

TU = Path(__file__).resolve().parent
SZABLON = TU.parent / "templates" / "expo-jarvo"
EAS = os.environ.get("JARVO_EAS_CLI", "eas-cli@24.7.0")                 # ≥ 14 dni od wydania (kwarantanna npm)
DOCTOR = os.environ.get("JARVO_EXPO_DOCTOR", "expo-doctor@1.21.1")
BUNDLE_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9_]*){1,}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
WYMAGANE = ["src/app/_layout.tsx", "src/app/(tabs)/wiecej.tsx", "src/app/prywatnosc.tsx", "src/app/kontakt.tsx",
            "src/components/BrakSieci.tsx", "src/components/BladEkranu.tsx", "src/components/Stan.tsx", "app.config.ts",
            "jarvo.app.json", "eas.json", ".gitignore", "locales/pl.json"]
SEKRETY = [(r"sk_live_[0-9A-Za-z]{10,}", "klucz Stripe (live)"), (r"AIza[0-9A-Za-z_-]{35}", "klucz Google API"),
           (r"service_role", "klucz service_role Supabase"), (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "klucz prywatny"),
           (r"xox[baprs]-[0-9A-Za-z-]{10,}", "token Slack"), (r"ghp_[0-9A-Za-z]{30,}", "token GitHub"),
           (r"sk-[A-Za-z0-9]{32,}", "klucz API modelu AI")]
MODUL_DO_KLUCZA = {m["modul"]: m["ios"] for m in zgodnosc.UPRAWNIENIA.values() if m["ios"]}
TRASY_DOMYSLNE = ["/", "/wiecej", "/kontakt", "/prywatnosc"]

KONFIGURACJA = """# Tożsamość aplikacji i dane firmy (aplikacja.py nowa/ustaw). Identyfikatora `bundle` nie da się zmienić
# po pierwszym wgraniu do sklepu: odwrotna domena firmy + nazwa, np. pl.salonola.app.
nazwa: "Salon Ola"                 # pod ikoną widać ~12 znaków, w sklepie ≤ 30
slug: salon-ola
bundle: pl.salonola.app
opis: "Rezerwuj wizyty i zbieraj pieczątki za każdą usługę."
kolor_glowny: "#C2185B"            # z brand kitu (knowledge/brands/<marka>/), paleta i kontrast liczą się same
wlasciciel_expo: ""                # organizacja Expo właściciela (podgląd w Expo Go), np. salon-ola
firma:
  nazwa: "Salon Ola sp. z o.o."
  adres: "ul. Długa 1, 00-001 Warszawa"
  email: "kontakt@salonola.pl"
  telefon: "+48 600 000 000"
  strona: "https://salonola.pl"
  prywatnosc_url: "https://salonola.pl/polityka-prywatnosci"
  usuwanie_konta_url: ""           # wymagane, gdy aplikacja ma konta (Google Play): strona z instrukcją usunięcia konta
"""


class Blad(Exception):
    pass


# ------------------------------------------------------------------ kolory (WCAG 2.2)

def _rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in rgb)


def luminancja(h: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(a: str, b: str) -> float:
    la, lb = sorted((luminancja(a), luminancja(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _miesz(a: str, b: str, t: float) -> str:
    return _hex(tuple(x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))))  # type: ignore[arg-type]


def dostosuj(kolor: str, tlo: str, minimum: float = 4.5) -> str:
    """Najmniejsza zmiana koloru (w stronę czerni albo bieli), przy której ma ≥ `minimum` kontrastu z tłem."""
    if kontrast(kolor, tlo) >= minimum:
        return kolor.upper()
    cel = "#000000" if luminancja(tlo) > 0.5 else "#FFFFFF"
    for i in range(1, 21):
        k = _miesz(kolor, cel, i / 20)
        if kontrast(k, tlo) >= minimum:
            return k
    return cel


def paleta(marka: str) -> dict:
    jasne_tlo, ciemne_tlo = "#FFFFFF", "#0E0F12"
    g_j = dostosuj(marka, jasne_tlo)
    g_c = dostosuj(marka, ciemne_tlo)
    na_j = "#FFFFFF" if kontrast("#FFFFFF", g_j) >= 4.5 else "#111318"
    na_c = "#0E0F12" if kontrast("#0E0F12", g_c) >= 4.5 else "#FFFFFF"
    p = {
        "jasny": {"tlo": jasne_tlo, "powierzchnia": "#F4F5F7", "tekst": "#111318", "tekstDrugi": "#5B616E",
                  "linia": "#E3E5EA", "glowny": g_j, "naGlownym": na_j, "blad": "#B42318", "sukces": "#067647"},
        "ciemny": {"tlo": ciemne_tlo, "powierzchnia": "#1A1C21", "tekst": "#F2F3F5", "tekstDrugi": "#A3A8B3",
                   "linia": "#2A2D33", "glowny": g_c, "naGlownym": na_c, "blad": "#F97066", "sukces": "#47CD89"},
    }
    p["kontrasty"] = {m: {"glowny/tlo": round(kontrast(p[m]["glowny"], p[m]["tlo"]), 2),
                          "naGlownym/glowny": round(kontrast(p[m]["naGlownym"], p[m]["glowny"]), 2),
                          "tekstDrugi/tlo": round(kontrast(p[m]["tekstDrugi"], p[m]["tlo"]), 2)} for m in ("jasny", "ciemny")}
    return p


def kolory_ts(p: dict) -> str:
    def blok(m: str) -> str:
        return "\n".join(f"    {k}: '{v}'," for k, v in p[m].items())
    return ("// Paleta z koloru marki (generuje `aplikacja.py ustaw`; kontrast WCAG AA sprawdzony przy generowaniu:\n"
            f"// {json.dumps(p['kontrasty'], ensure_ascii=False)}).\n"
            f"export const KOLORY = {{\n  jasny: {{\n{blok('jasny')}\n  }},\n  ciemny: {{\n{blok('ciemny')}\n  }},\n}} as const;\n")


# ------------------------------------------------------------------ konfiguracja

def wczytaj_yaml(sciezka: str | Path) -> dict:
    import yaml
    return yaml.safe_load(Path(sciezka).read_text(encoding="utf-8")) or {}


def sprawdz_konfiguracje(a: dict, konta: bool) -> list[str]:
    b = []
    if not a.get("nazwa") or len(str(a["nazwa"])) > 30:
        b.append("nazwa: wymagana, ≤ 30 znaków (limit nazwy w obu sklepach)")
    if not SLUG_RE.match(str(a.get("slug", ""))):
        b.append("slug: małe litery, cyfry i myślniki")
    bundle = str(a.get("bundle", ""))
    if not BUNDLE_RE.match(bundle) or bundle.startswith(("com.example", "pl.example", "com.test")):
        b.append("bundle: odwrotna domena firmy, np. pl.salonola.app (bez com.example, bez myślników i wielkich liter)")
    if not HEX_RE.match(str(a.get("kolor_glowny", ""))):
        b.append("kolor_glowny: #RRGGBB")
    f = a.get("firma") or {}
    for pole in ("nazwa", "email", "prywatnosc_url"):
        if not f.get(pole):
            b.append(f"firma.{pole}: wymagane (sklepy i RODO)")
    for pole in ("strona", "prywatnosc_url", "usuwanie_konta_url"):
        if f.get(pole) and not str(f[pole]).startswith("https://"):
            b.append(f"firma.{pole}: adres https://")
    if konta and not f.get("usuwanie_konta_url"):
        b.append("firma.usuwanie_konta_url: aplikacja ma konta, Google Play wymaga strony z instrukcją usunięcia konta")
    return b


def inicjaly(nazwa: str) -> str:
    slowa = [s for s in re.split(r"[\s\-_.]+", nazwa) if s and s[0].isalnum()]
    return ("".join(s[0] for s in slowa[:2]) or nazwa[:1]).upper()


def jarvo_app(a: dict, kz: dict) -> dict:
    f = a.get("firma") or {}
    return {
        "nazwa": a["nazwa"], "slug": a["slug"], "scheme": re.sub(r"[^a-z0-9]", "", a["slug"]),
        "wersja": str(a.get("wersja", "1.0.0")), "bundle_ios": a["bundle"], "pakiet_android": a["bundle"].replace("-", "_"),
        "wlasciciel_expo": a.get("wlasciciel_expo", ""), "expo_project_id": a.get("expo_project_id", ""),
        "tablet": bool(kz.get("tablet")), "opis": a.get("opis", ""),
        "firma": {k: str(f.get(k, "")) for k in ("nazwa", "adres", "email", "telefon", "strona", "prywatnosc_url", "usuwanie_konta_url")},
        "funkcje": kz["funkcje"],
        "kolory": {"glowny": a["kolor_glowny"].upper(), "tlo_ikony": a["kolor_glowny"].upper()},
        "uprawnienia_ios": kz["uprawnienia_ios"], "wtyczki": kz["wtyczki"],
        "zablokowane_uprawnienia_android": kz["zablokowane_uprawnienia_android"],
    }


def _uruchom(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 1200) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env={**os.environ, "CI": "1", "EXPO_NO_TELEMETRY": "1", **(env or {})},
                          capture_output=True, text=True, timeout=timeout)


def ustaw(kat: Path, a: dict, zg: dict, logo: str | None = None) -> dict:
    """Zapisuje konfigurację do aplikacji: jarvo.app.json, paleta, locales, ekran usuwania konta, ikony."""
    w = zgodnosc.ocen(zg)
    if w["bledy"]:
        raise Blad("profil zgodności ma błędy: " + "; ".join(w["bledy"]))
    kz = w["konfiguracja"]
    bledy = sprawdz_konfiguracje(a, kz["funkcje"]["konta"])
    if bledy:
        raise Blad("konfiguracja aplikacji: " + "; ".join(bledy))
    stara = json.loads((kat / "jarvo.app.json").read_text(encoding="utf-8")) if (kat / "jarvo.app.json").exists() else {}
    app = jarvo_app({**a, "expo_project_id": a.get("expo_project_id") or stara.get("expo_project_id", "")}, kz)
    (kat / "jarvo.app.json").write_text(json.dumps(app, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    p = paleta(a["kolor_glowny"])
    (kat / "src" / "theme" / "kolory.ts").write_text(kolory_ts(p), encoding="utf-8")
    (kat / "locales").mkdir(exist_ok=True)
    (kat / "locales" / "pl.json").write_text(json.dumps({"CFBundleDisplayName": a["nazwa"], **kz["uprawnienia_ios"]},
                                                        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pkg = json.loads((kat / "package.json").read_text(encoding="utf-8"))
    pkg["name"] = a["slug"]
    (kat / "package.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _ekran_usuwania(kat, kz["funkcje"]["konta"])
    ikony(kat, a, logo)
    return {"paleta": p, "zgodnosc": w}


def _ekran_usuwania(kat: Path, konta: bool) -> None:
    """Ekran „Usuń konto” jest w aplikacji wtedy i tylko wtedy, gdy aplikacja ma konta."""
    ekran = kat / "src" / "app" / "usun-konto.tsx"
    uklad = kat / "src" / "app" / "_layout.tsx"
    linia = '        <Stack.Screen name="usun-konto" options={{ title: \'Usuń konto\' }} />\n'
    tekst = uklad.read_text(encoding="utf-8")
    if konta:
        if not ekran.exists():
            shutil.copy2(SZABLON / "src" / "app" / "usun-konto.tsx", ekran)
        if 'name="usun-konto"' not in tekst:
            tekst = tekst.replace("      </Stack>\n", linia + "      </Stack>\n")
    else:
        ekran.unlink(missing_ok=True)
        tekst = "".join(l for l in tekst.splitlines(keepends=True) if 'name="usun-konto"' not in l)
    uklad.write_text(tekst, encoding="utf-8")


def ikony(kat: Path, a: dict, logo: str | None) -> None:
    cmd = ["node", str(TU / "ikony.cjs"), "--out", str(kat / "assets"), "--kolor", a["kolor_glowny"],
           "--litery", inicjaly(a["nazwa"])]
    if logo:
        cmd += ["--logo", str(Path(logo).resolve())]
    r = _uruchom(cmd, kat, timeout=180)
    if r.returncode != 0:
        raise Blad(f"ikony.cjs: {r.stderr.strip()[-600:]}")


def nowa(kat: Path, a: dict, zg: dict, logo: str | None, instaluj: bool) -> dict:
    if kat.exists() and any(kat.iterdir()):
        raise Blad(f"{kat} nie jest pusty (do zmian w istniejącej aplikacji: `ustaw`)")
    shutil.copytree(SZABLON, kat, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules", ".expo", "dist*"))
    wynik = ustaw(kat, a, zg, logo)
    if instaluj:
        r = _uruchom(["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"], kat)
        if r.returncode != 0:
            raise Blad(f"npm install: {r.stderr.strip()[-800:]}")
        paczki = wynik["zgodnosc"]["konfiguracja"]["paczki"]
        if paczki:
            r = _uruchom(["npx", "expo", "install", *paczki], kat)
            if r.returncode != 0:
                raise Blad(f"expo install {' '.join(paczki)}: {r.stderr.strip()[-800:]}")
    if shutil.which("git") and not (kat / ".git").exists():
        _uruchom(["git", "init", "-q"], kat, timeout=30)
    return wynik


# ------------------------------------------------------------------ kontrole

def _zrodla(kat: Path) -> list[Path]:
    return [p for p in (kat / "src").rglob("*") if p.suffix in (".ts", ".tsx", ".js", ".jsx") and p.is_file()]


def zasady_jarvo(kat: Path) -> list[dict]:
    """Kontrole bez sieci i bez node_modules: elementy zgodności, uprawnienia ↔ moduły, sekrety, znaczniki JARVO-TODO."""
    k: list[dict] = []
    app = json.loads((kat / "jarvo.app.json").read_text(encoding="utf-8")) if (kat / "jarvo.app.json").exists() else {}
    for rel in WYMAGANE:
        if not (kat / rel).exists():
            k.append({"id": "J-PLIKI", "ok": False, "opis": f"brak {rel} (element zgodności z szablonu)"})
    konta = (app.get("funkcje") or {}).get("konta")
    if konta and not (kat / "src" / "app" / "usun-konto.tsx").exists():
        k.append({"id": "J-USUWANIE", "ok": False, "opis": "aplikacja ma konta, a nie ma ekranu Usuń konto (Apple 5.1.1(v))"})
    zrodla = _zrodla(kat)
    kod = {p: p.read_text(encoding="utf-8", errors="replace") for p in zrodla}
    importy = {m for t in kod.values() for m in re.findall(r"from ['\"]([@\w./-]+)['\"]", t)}
    plist = app.get("uprawnienia_ios") or {}
    for modul, klucz in MODUL_DO_KLUCZA.items():
        if any(i == modul or i.startswith(modul + "/") for i in importy) and klucz not in plist:
            k.append({"id": "J-UPRAWNIENIA", "ok": False,
                      "opis": f"kod używa {modul}, a w profilu zgodności nie ma uprawnienia z opisem {klucz} (Apple 5.1.1(ii))"})
    pkg = json.loads((kat / "package.json").read_text(encoding="utf-8")) if (kat / "package.json").exists() else {}
    zaleznosci = set(pkg.get("dependencies") or {})
    for modul, klucz in MODUL_DO_KLUCZA.items():
        if klucz in plist and modul not in zaleznosci and modul not in importy:
            k.append({"id": "J-UPRAWNIENIA-ZBEDNE", "ok": False,
                      "opis": f"opis {klucz} bez modułu {modul}: zbędne uprawnienie (Apple 5.1.1(iii), Google Play)"})
    for p, t in kod.items():
        for wz, nazwa in SEKRETY:
            if re.search(wz, t):
                k.append({"id": "J-SEKRET", "ok": False, "opis": f"{p.relative_to(kat)}: {nazwa} w kodzie aplikacji (trafia do paczki)"})
    todo = [f"{p.relative_to(kat)}:{i + 1}" for p, t in kod.items() for i, l in enumerate(t.splitlines()) if "JARVO-TODO" in l]
    k.append({"id": "J-TODO", "ok": True, "ostrz": bool(todo),
              "opis": f"znaczniki JARVO-TODO: {len(todo)} ({', '.join(todo[:5])}); blokują wydanie, nie podgląd" if todo
              else "brak znaczników JARVO-TODO"})
    for p, t in kod.items():
        if re.search(r"EXPO_PUBLIC_[A-Z_]*(SECRET|PRIVATE|SERVICE)", t):
            k.append({"id": "J-PUBLIC", "ok": False, "opis": f"{p.relative_to(kat)}: zmienna EXPO_PUBLIC_ z sekretem (trafia do paczki)"})
    if not any(not x["ok"] for x in k if x["id"] != "J-TODO"):
        k.insert(0, {"id": "J-ZASADY", "ok": True, "opis": "elementy zgodności, uprawnienia i sekrety: bez uwag"})
    return k


def sprawdz(kat: Path, siec: bool = True) -> dict:
    wyniki: list[dict] = []

    def krok(id_, opis, cmd, timeout=600, env=None):
        t0 = time.time()
        try:
            r = _uruchom(cmd, kat, env=env, timeout=timeout)
            ok, wyj = r.returncode == 0, (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            ok, wyj = False, f"przekroczony czas {timeout} s"
        wyniki.append({"id": id_, "ok": ok, "opis": opis, "czas_s": round(time.time() - t0, 1), "wyjscie": wyj[-1500:]})

    if not (kat / "node_modules").exists():
        wyniki.append({"id": "INSTALACJA", "ok": False, "opis": "brak node_modules: `npm install` w katalogu aplikacji"})
    else:
        krok("TYPY", "TypeScript bez błędów (tsc --noEmit)", ["npx", "tsc", "--noEmit"])
        krok("LINT", "ESLint (expo lint)", ["npx", "expo", "lint"])
        krok("WERSJE", "wersje paczek zgodne z SDK (expo install --check)", ["npx", "expo", "install", "--check"])
        if siec:
            krok("DOCTOR", "expo-doctor (konfiguracja, zależności, React Native Directory)", ["npx", "--yes", DOCTOR], timeout=300)
    wyniki += zasady_jarvo(kat)
    zle = [w for w in wyniki if not w["ok"]]
    return {"katalog": str(kat), "ok": not zle, "kontrole": wyniki,
            "podsumowanie": f"{len(wyniki) - len(zle)}/{len(wyniki)} kontroli OK" + (f"; nie przeszły: {', '.join(w['id'] for w in zle)}" if zle else "")}


# ------------------------------------------------------------------ eksport, podgląd, zrzuty

def eksport(kat: Path, baza: str | None = None) -> Path:
    env = {"JARVO_BASE_URL": baza} if baza else {}
    r = _uruchom(["npx", "expo", "export", "-p", "web", "--output-dir", "dist-web", "--clear"], kat, env=env)
    if r.returncode != 0 or not (kat / "dist-web" / "index.html").exists():
        raise Blad(f"expo export: {(r.stdout + r.stderr).strip()[-1500:]}")
    return kat / "dist-web"


def _jarvo_link() -> list[str]:
    for kandydat in (os.environ.get("JARVO_REPO", "/opt/jarvo/repo"), str(TU.parents[2])):
        p = Path(kandydat) / "scripts" / "jarvo_link.py"
        if p.exists():
            return [sys.executable, str(p)]
    raise Blad("nie znaleziono scripts/jarvo_link.py (repo floty)")


def link_hq(sciezka: Path) -> str:
    r = subprocess.run([*_jarvo_link(), str(sciezka)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise Blad(f"jarvo_link: {r.stderr.strip()}")
    return r.stdout.strip().splitlines()[-1]


def link_aplikacji(url: str) -> str:
    """Aplikacja (expo-router) czyta ścieżkę z adresu: …/<token>/index.html to dla niej nieznana trasa „/index.html”,
    więc właściciel dostaje adres katalogu …/<token>/ (serwer HQ podaje wtedy index.html, a router pokazuje Start)."""
    return url[: -len("index.html")] if url.endswith("/index.html") else url


def token_z_linku(url: str) -> str:
    return urllib.parse.urlsplit(url).path.lstrip("/").split("/", 1)[0]


class _Spa(SimpleHTTPRequestHandler):
    """Serwer zrzutów: /<prefiks>/… → dist-web/…, nieznane trasy → index.html (jak router aplikacji)."""
    prefiks = ""
    katalog = ""

    def log_message(self, *a):  # noqa: D401
        pass

    def translate_path(self, path):
        sciezka = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        if self.prefiks and sciezka.startswith(self.prefiks):
            sciezka = sciezka[len(self.prefiks):] or "/"
        plik = Path(self.katalog) / sciezka.lstrip("/")
        if not plik.is_file():
            plik = Path(self.katalog) / "index.html"
        return str(plik)


def serwer_spa(katalog: Path, prefiks: str) -> tuple[ThreadingHTTPServer, int]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    handler = type("Spa", (_Spa,), {"prefiks": prefiks.rstrip("/"), "katalog": str(katalog)})
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def zrzuty(url_bazowy: str, out: Path, trasy: list[str]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    r = _uruchom(["node", str(TU / "zrzuty.cjs"), url_bazowy, str(out), "--trasy", ",".join(trasy)], out, timeout=600)
    if r.returncode not in (0, 1) or not (out / "zrzuty.json").exists():
        raise Blad(f"zrzuty.cjs: {(r.stdout + r.stderr).strip()[-1200:]}")
    return json.loads((out / "zrzuty.json").read_text(encoding="utf-8"))


def podglad(kat: Path, trasy: list[str], z_eksportem: bool = True) -> dict:
    dist = kat / "dist-web"
    dist.mkdir(exist_ok=True)
    if not (dist / "index.html").exists():
        (dist / "index.html").write_text("<!doctype html><meta charset=utf-8><title>…</title>", encoding="utf-8")
    url = link_hq(dist)
    token = token_z_linku(url)
    if z_eksportem:
        eksport(kat, f"/{token}")
    url = link_aplikacji(link_hq(dist))
    srv, port = serwer_spa(dist, f"/{token}")
    try:
        wynik = zrzuty(f"http://127.0.0.1:{port}/{token}", kat / "out" / "zrzuty", trasy)
    finally:
        srv.shutdown()
    return {"link": url, "zrzuty": str(kat / "out" / "zrzuty"), "kontrole": wynik.get("podsumowanie"), "wynik": wynik}


# ------------------------------------------------------------------ Expo Go (EAS Update)

def _eas(args: list[str], kat: Path, env: dict | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    if not os.environ.get("EXPO_TOKEN"):
        raise Blad("brak EXPO_TOKEN (token robota z organizacji Expo właściciela, w .env profilu); właściciel tworzy go raz: "
                   "expo.dev → organizacja → Settings → Robot users (rola Developer)")
    return _uruchom(["npx", "--yes", EAS, *args], kat, env=env, timeout=timeout)


def projekt_expo(kat: Path) -> str:
    """ID projektu EAS: z jarvo.app.json albo zakłada projekt w organizacji właściciela (kopia ze statycznym app.json,
    bo `eas init` nie zapisuje do dynamicznego app.config.ts)."""
    app = json.loads((kat / "jarvo.app.json").read_text(encoding="utf-8"))
    if app.get("expo_project_id"):
        return app["expo_project_id"]
    if not app.get("wlasciciel_expo"):
        raise Blad("brak `wlasciciel_expo` (organizacja Expo właściciela) w konfiguracji aplikacji")
    r = _uruchom(["npx", "expo", "config", "--json", "--type", "public"], kat, timeout=180)
    if r.returncode != 0:
        raise Blad(f"expo config: {r.stderr.strip()[-600:]}")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "app.json").write_text(json.dumps({"expo": json.loads(r.stdout)}), encoding="utf-8")
        (Path(tmp) / "package.json").write_text(json.dumps({"name": app["slug"], "private": True}), encoding="utf-8")
        r = _eas(["init", "--account", app["wlasciciel_expo"], "--force", "--non-interactive", "--json"], Path(tmp))
    if r.returncode != 0:
        raise Blad(f"eas init: {(r.stdout + r.stderr).strip()[-800:]}")
    pid = json.loads(r.stdout)["projectId"]
    app["expo_project_id"] = pid
    (kat / "jarvo.app.json").write_text(json.dumps(app, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pid


def linki_expo_go(projekt: str, grupa: str) -> dict:
    q = urllib.parse.urlencode({"slug": "exp", "projectId": projekt, "groupId": grupa})
    return {"qr_svg": f"https://qr.expo.dev/eas-update?{q}", "url_tekst": f"https://qr.expo.dev/eas-update?{q}&format=url"}


def grupa_z_update(wyjscie: str) -> str:
    """`eas update --json` → identyfikator grupy (wspólny dla iOS i Androida)."""
    dane = json.loads(wyjscie[wyjscie.index("["):]) if "[" in wyjscie else []
    grupy = {u.get("group") for u in dane if isinstance(u, dict)} - {None}
    if len(grupy) != 1:
        raise Blad(f"eas update: oczekiwana jedna grupa aktualizacji, jest {len(grupy)}")
    return grupy.pop()


def strona_expo_go(out: Path, nazwa: str, exp_url: str, qr_svg: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "index.html"
    p.write_text(f"""<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{nazwa}: podgląd w Expo Go</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:520px;margin:32px auto;padding:0 16px;color:#111}}a.b{{display:block;
text-align:center;background:#111;color:#fff;padding:14px;border-radius:12px;text-decoration:none;font-weight:600}}img{{width:240px;
height:240px;display:block;margin:16px auto}}ol{{padding-left:20px}}</style>
<h1>{nazwa}</h1><p>Podgląd aplikacji na telefonie (Expo Go).</p>
<a class="b" href="{exp_url}">Otwórz w Expo Go</a>
<img src="{qr_svg}" alt="Kod QR do Expo Go">
<ol><li>Zainstaluj Expo Go (App Store, Google Play) i zaloguj się kontem Expo swojej firmy.</li>
<li>Na komputerze: zeskanuj kod aparatem telefonu. Na telefonie: kliknij przycisk.</li>
<li>To podgląd: płatności, powiadomienia i logowanie mogą działać dopiero w wersji testowej (TestFlight, Google Play).</li></ol>
</html>""", encoding="utf-8")
    return p


def expo_go(kat: Path, kanal: str, wiadomosc: str) -> dict:
    projekt = projekt_expo(kat)
    r = _eas(["update", "--branch", kanal, "--message", wiadomosc, "--platform", "all", "--non-interactive", "--json"], kat,
             env={"APP_VARIANT": "expo-go"})
    if r.returncode != 0:
        raise Blad(f"eas update: {(r.stdout + r.stderr).strip()[-1200:]}")
    grupa = grupa_z_update(r.stdout)
    linki = linki_expo_go(projekt, grupa)
    import urllib.request
    try:
        with urllib.request.urlopen(linki["url_tekst"], timeout=30) as o:  # noqa: S310 (adres Expo z kodu)
            exp_url = o.read().decode().strip()
    except OSError:
        exp_url = f"exp://u.expo.dev/{projekt}/group/{grupa}"
    app = json.loads((kat / "jarvo.app.json").read_text(encoding="utf-8"))
    strona = strona_expo_go(kat / "out" / "expo-go", app["nazwa"], exp_url, linki["qr_svg"])
    return {"projekt": projekt, "grupa": grupa, "exp_url": exp_url, "qr": linki["qr_svg"], "strona": link_hq(strona)}


# ------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("konfiguracja")
    for nazwa in ("nowa", "ustaw"):
        x = sub.add_parser(nazwa)
        x.add_argument("katalog")
        x.add_argument("--aplikacja", required=True)
        x.add_argument("--zgodnosc", required=True)
        x.add_argument("--logo")
        if nazwa == "nowa":
            x.add_argument("--bez-instalacji", action="store_true")
    s = sub.add_parser("sprawdz")
    s.add_argument("katalog")
    s.add_argument("--bez-sieci", action="store_true")
    s.add_argument("--json", action="store_true")
    e = sub.add_parser("eksport")
    e.add_argument("katalog")
    e.add_argument("--baza")
    pg = sub.add_parser("podglad")
    pg.add_argument("katalog")
    pg.add_argument("--trasy", nargs="*", default=TRASY_DOMYSLNE)
    pg.add_argument("--bez-eksportu", action="store_true")
    g = sub.add_parser("expo-go")
    g.add_argument("katalog")
    g.add_argument("--kanal", default="podglad")
    g.add_argument("--wiadomosc", default="podgląd Twórcy aplikacji")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "konfiguracja":
            print(KONFIGURACJA, end="")
            return 0
        kat = Path(args.katalog).resolve()
        if args.cmd in ("nowa", "ustaw"):
            a, zg = wczytaj_yaml(args.aplikacja), zgodnosc.wczytaj(args.zgodnosc)
            if args.cmd == "nowa":
                w = nowa(kat, a, zg, args.logo, not args.bez_instalacji)
            else:
                w = ustaw(kat, a, zg, args.logo)
            md = zgodnosc.raport_md(w["zgodnosc"])
            (kat / "ZGODNOSC.md").write_text(md, encoding="utf-8")
            print(f"✓ {kat} ({args.cmd}): paleta {json.dumps(w['paleta']['kontrasty'], ensure_ascii=False)}; "
                  f"moduły: {', '.join(w['zgodnosc']['konfiguracja']['paczki']) or 'szablon'}; ZGODNOSC.md")
            return 0
        if args.cmd == "sprawdz":
            w = sprawdz(kat, not args.bez_sieci)
            out = kat / "out" / "jakosc"
            out.mkdir(parents=True, exist_ok=True)
            (out / "sprawdz.json").write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")
            if args.json:
                print(json.dumps(w, ensure_ascii=False, indent=2))
            else:
                for k in w["kontrole"]:
                    znak = "⚠" if k.get("ostrz") else ("✓" if k["ok"] else "✗")
                    print(f"{znak} {k['id']}: {k['opis']}" + ("" if k["ok"] else f"\n    {k.get('wyjscie', '')[-400:]}"))
                print(w["podsumowanie"])
            return 0 if w["ok"] else 1
        if args.cmd == "eksport":
            print(eksport(kat, args.baza))
            return 0
        if args.cmd == "podglad":
            w = podglad(kat, args.trasy, not args.bez_eksportu)
            print(json.dumps({k: v for k, v in w.items() if k != "wynik"}, ensure_ascii=False, indent=2))
            return 0 if (w["wynik"].get("bledy_lacznie", 0) == 0) else 1
        if args.cmd == "expo-go":
            print(json.dumps(expo_go(kat, args.kanal, args.wiadomosc), ensure_ascii=False, indent=2))
            return 0
    except Blad as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
