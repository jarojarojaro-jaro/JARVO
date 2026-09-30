#!/usr/bin/env python3
"""Automatyczne sprawdzenia bezpieczeństwa strony/aplikacji (część mechaniczna skilla bezpieczenstwo-aplikacji).

    python3 security_check.py repo <katalog projektu> [--json]     # kod: sekrety, .env w gicie, zależności, wzorce ryzyka
    python3 security_check.py url https://strona.pl [--json]        # działająca strona: nagłówki, ciasteczka, CORS, wycieki

To nie zastępuje przeglądu kodu (model czyta przepływ danych: skill, references/przeglad-kodu.md), tylko łapie
to, co da się wykryć maszynowo i bez fałszywych alarmów. Każde ustalenie ma wagę: KRYTYCZNE / WYSOKIE / ŚREDNIE / NISKIE.
Kod wyjścia: 0 = brak KRYTYCZNYCH i WYSOKICH, 1 = są, 2 = złe wejście. Bez sieci poza badaną stroną; bez zależności.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

WAGI = ["KRYTYCZNE", "WYSOKIE", "ŚREDNIE", "NISKIE"]
POMIN = {"node_modules", ".git", "dist", "build", ".next", ".astro", ".output", "vendor", "__pycache__", ".venv", "coverage"}
KOD = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".astro", ".vue", ".svelte", ".py", ".php", ".rb", ".go", ".html"}

SEKRETY = [
    ("klucz AWS", r"AKIA[0-9A-Z]{16}"),
    ("klucz prywatny", r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    ("token GitHub", r"gh[pousr]_[A-Za-z0-9]{36,}"),
    ("klucz Stripe (live)", r"sk_live_[0-9a-zA-Z]{20,}"),
    ("klucz OpenAI/Anthropic/OpenRouter", r"sk-(ant-|or-v1-|proj-)?[A-Za-z0-9_\-]{32,}"),
    ("klucz Google API", r"AIza[0-9A-Za-z_\-]{35}"),
    ("token Slack", r"xox[baprs]-[0-9A-Za-z\-]{10,}"),
    ("klucz Supabase service_role / JWT", r"eyJhbGciOi[A-Za-z0-9_\-]{20,}\.eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"),
    ("hasło w kodzie", r"(?i)(password|passwd|haslo|secret)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
]
RYZYKA = [  # (waga, opis, wzorzec, poprawka) — tylko wzorce o niskim odsetku fałszywych alarmów
    ("WYSOKIE", "token logowania w localStorage/sessionStorage", r"(local|session)Storage\.setItem\(\s*['\"][^'\"]*(token|jwt|session|auth)",
     "token w ciasteczku httpOnly; Secure; SameSite=Lax (ustawia serwer)"),
    ("WYSOKIE", "SQL sklejany z danych wejściowych", r"(?i)(query|execute|raw)\s*\(\s*[`'\"](select|insert|update|delete)[^`'\"]*(\$\{|['\"]\s*\+)",
     "zapytania z parametrami ($1/?/:nazwa) albo ORM"),
    ("WYSOKIE", "eval na danych", r"\beval\s*\(|new Function\s*\(", "usuń eval; parsuj JSON.parse, mapuj akcje słownikiem"),
    ("ŚREDNIE", "HTML wstrzykiwany bez oczyszczenia", r"dangerouslySetInnerHTML|\.innerHTML\s*=|v-html=|set:html=|\{@html",
     "tekst zamiast HTML; jeśli musi być HTML: DOMPurify po stronie klienta/serwera"),
    ("ŚREDNIE", "klucz serwerowy w zmiennej publicznej frontu", r"(NEXT_PUBLIC|PUBLIC|VITE|NUXT_PUBLIC)_[A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE|STRIPE_SK)",
     "sekret tylko w zmiennych serwera; na froncie wyłącznie klucze publiczne (anon, publishable)"),
    ("ŚREDNIE", "CORS otwarty dla wszystkich z ciasteczkami", r"(?i)(origin:\s*['\"]\*['\"]|Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*)",
     "lista dozwolonych domen; nigdy * razem z credentials"),
    ("ŚREDNIE", "tryb debug na stałe", r"(?i)(DEBUG\s*=\s*True|app\.debug\s*=\s*true|debug:\s*true)", "debug tylko z env i nigdy na produkcji"),
    ("NISKIE", "haszowanie hasła słabym algorytmem", r"(?i)(md5|sha1)\s*\(.*pass", "argon2id albo bcrypt (koszt ≥ 12)"),
]
# Niebezpieczne ustawienia domyślne (metoda za Trail of Bits `insecure-defaults`, reguły własne): liczy się, czy aplikacja
# DZIAŁA z tą wartością, gdy brakuje konfiguracji. `env.get(X, 'dev')` działa ze znanym sekretem, `env[X]` się wywraca.
# Pomijamy pliki testów (fixtures z sekretem testowym to nie ustalenie).
_WRAZLIWE = r"[A-Z0-9_]*(?:SECRET|PASSWORD|PASSWD|PASS|TOKEN|API_KEY|PRIVATE_KEY|SIGNING_KEY|JWT)[A-Z0-9_]*"
DOMYSLNE = [  # (waga, opis, wzorzec, poprawka)
    ("WYSOKIE", "sekret z wartością zapasową w kodzie (aplikacja ruszy ze znanym kluczem)",
     r"(?:environ\.get|getenv|ENV\.fetch)\(\s*['\"]" + _WRAZLIWE + r"['\"]\s*,\s*['\"][^'\"]+['\"]"
     r"|process\.env\." + _WRAZLIWE + r"\s*(?:\|\||\?\?)\s*['\"`][^'\"`]+['\"`]",
     "bez wartości zapasowej: brak zmiennej = błąd przy starcie (os.environ['X'] / throw)"),
    ("WYSOKIE", "zabezpieczenie wyłączone, gdy brak konfiguracji (fail-open)",
     r"(?i)(?:environ\.get|getenv|process\.env)\W+(?:REQUIRE_AUTH|AUTH_ENABLED|ENABLE_AUTH|CSRF\w*|VERIFY_\w+|SSL_VERIFY)"
     r"['\"]?\s*(?:,|\|\||\?\?)\s*['\"](?:false|0|no|off)['\"]",
     "domyślnie włączone; wyłączenie tylko jawną zmienną w środowisku deweloperskim"),
    ("WYSOKIE", "weryfikacja certyfikatu TLS wyłączona",
     r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0",
     "zostaw weryfikację; własny CA przez verify=<ścieżka do CA> / ca: [...]"),
    ("WYSOKIE", "JWT bez weryfikacji podpisu",
     r"(?i)algorithms\s*=\s*\[?\s*['\"]none['\"]|verify_signature['\"]?\s*:\s*False|jwt\.decode\([^)]*verify\s*=\s*False",
     "stały algorytm (HS256/RS256) i weryfikacja podpisu zawsze"),
    ("WYSOKIE", "domyślne hasło w kodzie",
     r"(?i)(?:password|passwd|pass|haslo)\w*['\"]?\s*[:=]\s*['\"](?:admin|password|changeme|root|secret|qwerty|123456)\w{0,4}['\"]",
     "hasło tylko ze zmiennej środowiskowej; żadnego konta z hasłem domyślnym"),
    ("ŚREDNIE", "szczegóły błędu (stos, komunikat bazy) w odpowiedzi do klienta",
     r"(?:jsonify|res\.(?:send|json)|Response)\([^\n]*(?:traceback\.format_exc|\.stack\b)",
     "pełny błąd do logów, klientowi ogólny komunikat"),
    ("ŚREDNIE", "introspekcja GraphQL włączona na stałe", r"introspection\s*:\s*true",
     "introspection: process.env.NODE_ENV !== 'production'"),
    ("ŚREDNIE", "uprawnienia plików dla wszystkich (0o666/0o777, public-read)",
     r"0o?7[67]7\b|0o?666\b|chmod\s+(?:-R\s+)?777|['\"]public-read(?:-write)?['\"]",
     "najmniejsze potrzebne uprawnienia; publiczny odczyt tylko dla zasobów, które mają być publiczne"),
]
PLIK_TESTOW = re.compile(r"(^|/)(tests?|__tests__|spec|fixtures?)/|(^|/)test_[^/]*$|[._](test|spec)\.[a-z]+$")

NAGLOWKI = [  # (nagłówek, waga gdy brak, po co)
    ("strict-transport-security", "ŚREDNIE", "HSTS: wymusza HTTPS (max-age ≥ 15552000; includeSubDomains)"),
    ("content-security-policy", "ŚREDNIE", "CSP: ogranicza skrypty (XSS); minimum default-src 'self', frame-ancestors 'none'"),
    ("x-content-type-options", "NISKIE", "nosniff: przeglądarka nie zgaduje typów plików"),
    ("referrer-policy", "NISKIE", "strict-origin-when-cross-origin: adresy nie wyciekają do obcych stron"),
    ("permissions-policy", "NISKIE", "wyłącza nieużywane API (kamera, mikrofon, geolokalizacja)"),
]
WYCIEKI = [("/.env", "KRYTYCZNE"), ("/.git/HEAD", "KRYTYCZNE"), ("/.git/config", "KRYTYCZNE"), ("/.DS_Store", "NISKIE"),
           ("/server-status", "ŚREDNIE"), ("/phpinfo.php", "WYSOKIE"), ("/.vscode/settings.json", "NISKIE"),
           ("/wp-config.php.bak", "KRYTYCZNE"), ("/config.json", "ŚREDNIE"), ("/backup.zip", "WYSOKIE")]


def u(waga, co, gdzie, poprawka):
    return {"waga": waga, "co": co, "gdzie": gdzie, "poprawka": poprawka}


def pliki(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and not any(part in POMIN for part in p.relative_to(root).parts) and p.stat().st_size < 2_000_000:
            yield p


def git(root: Path, *a) -> str:
    r = subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def repo(root: Path) -> list[dict]:
    wyn = []
    sledzone = set(git(root, "ls-files").splitlines())
    for f in sorted(sledzone):
        name = Path(f).name
        if re.fullmatch(r"\.env(\..+)?", name) and not name.endswith((".example", ".sample", ".template")):
            wyn.append(u("KRYTYCZNE", "plik .env w repozytorium", f, "git rm --cached; dopisz .env* do .gitignore; UNIEWAŻNIJ klucze z pliku"))
    top = Path(git(root, "rev-parse", "--show-toplevel").strip() or root)
    if sledzone and not (top / ".gitignore").exists():
        wyn.append(u("ŚREDNIE", "brak .gitignore", ".", "dodaj .gitignore (.env*, node_modules, dist)"))
    # sekrety: pliki robocze + cała historia gita (usunięty klucz dalej jest w historii)
    for p in pliki(root):
        if p.name.endswith((".example", ".sample", ".lock")) or p.suffix in {".png", ".jpg", ".woff2", ".mp4", ".pdf"}:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(p.relative_to(root))
        for nazwa, wz in SEKRETY:
            for m in re.finditer(wz, txt):
                if re.search(r"(?i)(example|placeholder|twoj|your|xxx|dummy|test)", m.group(0)):
                    continue
                line = txt.count("\n", 0, m.start()) + 1
                wyn.append(u("KRYTYCZNE", f"{nazwa} w kodzie", f"{rel}:{line}", "przenieś do zmiennych serwera; UNIEWAŻNIJ klucz"))
                break
        if p.suffix in KOD:
            reguly = RYZYKA + ([] if PLIK_TESTOW.search(rel) else DOMYSLNE)
            for waga, opis, wz, fix in reguly:
                m = re.search(wz, txt)
                if m:
                    wyn.append(u(waga, opis, f"{rel}:{txt.count(chr(10), 0, m.start()) + 1}", fix))
    historia = git(root, "log", "-p", "--all", "-G", "|".join(w for _, w in SEKRETY[:7]), "--format=@@%h")
    hits = {m.group(0)[:12] for _, wz in SEKRETY[:7] for m in re.finditer(wz, historia)}
    if hits:
        wyn.append(u("KRYTYCZNE", f"sekrety w historii gita ({len(hits)})", "git log",
                     "UNIEWAŻNIJ klucze (usunięcie z historii nie wystarczy: kopie już istnieją); potem git filter-repo"))
    if (root / "package.json").exists() and shutil.which("npm"):
        r = subprocess.run(["npm", "audit", "--json", "--omit=dev"], cwd=root, capture_output=True, text=True)
        try:
            v = (json.loads(r.stdout or "{}").get("metadata") or {}).get("vulnerabilities") or {}
            for waga, klucz in (("KRYTYCZNE", "critical"), ("WYSOKIE", "high")):
                if v.get(klucz):
                    wyn.append(u(waga, f"zależności z podatnościami: {v[klucz]} ({klucz})", "package.json",
                                 "npm audit fix; większe skoki wersji ręcznie z testem"))
        except ValueError:
            pass
    return wyn


def pobierz(url: str, method="GET", headers=None, timeout=15):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "jarvo-web-security/1.0", **(headers or {})})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.headers.get_all("Set-Cookie") or [], r.read(3000)
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.headers.get_all("Set-Cookie") or [], e.read(3000)


def strona(url: str) -> list[dict]:
    wyn = []
    base = url.rstrip("/")
    st, h, cookies, body = pobierz(base)
    if base.startswith("http://"):
        wyn.append(u("WYSOKIE", "strona bez HTTPS", base, "certyfikat (Let's Encrypt) i przekierowanie 301 na https"))
    for nag, waga, po_co in NAGLOWKI:
        if nag not in h and not (nag == "content-security-policy" and "content-security-policy-report-only" in h):
            wyn.append(u(waga, f"brak nagłówka {nag}", base, po_co))
    if "x-frame-options" not in h and "frame-ancestors" not in h.get("content-security-policy", ""):
        wyn.append(u("ŚREDNIE", "strona może być osadzona w cudzej ramce (clickjacking)", base, "CSP frame-ancestors 'none' albo X-Frame-Options: DENY"))
    for nag in ("server", "x-powered-by"):
        if re.search(r"\d", h.get(nag, "")):
            wyn.append(u("NISKIE", f"{nag} ujawnia wersję: {h[nag]}", base, "ukryj wersję serwera/frameworka"))
    for c in cookies:
        nazwa = c.split("=", 1)[0]
        brak = [f for f in ("Secure", "HttpOnly", "SameSite") if f.lower() not in c.lower()]
        if brak and re.search(r"(?i)sess|token|auth|sid|jwt", nazwa):
            wyn.append(u("WYSOKIE", f"ciasteczko sesji {nazwa} bez {', '.join(brak)}", base, "Set-Cookie: …; Secure; HttpOnly; SameSite=Lax"))
    st2, h2, _, _ = pobierz(base, headers={"Origin": "https://atak.example"})
    acao = h2.get("access-control-allow-origin", "")
    if acao == "https://atak.example" or (acao == "*" and h2.get("access-control-allow-credentials") == "true"):
        wyn.append(u("WYSOKIE", f"CORS wpuszcza dowolną domenę ({acao})", base, "lista dozwolonych domen; bez odbijania Origin"))
    if re.search(rb"(?i)(Traceback \(most recent|Whoops!|DEBUG = True|stack trace|at Object\.<anonymous>)", body):
        wyn.append(u("WYSOKIE", "strona pokazuje ślad błędu / tryb debug", base, "wyłącz debug na produkcji; własne strony błędów"))
    for sciezka, waga in WYCIEKI:
        s, hh, _, b = pobierz(base + sciezka)
        typ = hh.get("content-type", "")
        if s == 200 and b and "text/html" not in typ and not b.lstrip().startswith(b"<"):
            wyn.append(u(waga, f"publicznie dostępny {sciezka}", base + sciezka, "zablokuj na serwerze (deny) i usuń z katalogu publicznego"))
    return wyn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tryb", choices=["repo", "url"])
    ap.add_argument("cel")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.tryb == "repo" and not Path(a.cel).is_dir():
        print("✗ brak katalogu", file=sys.stderr)
        return 2
    wyn = repo(Path(a.cel)) if a.tryb == "repo" else strona(a.cel)
    wyn.sort(key=lambda x: WAGI.index(x["waga"]))
    licz = {w: sum(x["waga"] == w for x in wyn) for w in WAGI}
    if a.json:
        print(json.dumps({"cel": a.cel, "tryb": a.tryb, "podsumowanie": licz, "ustalenia": wyn}, ensure_ascii=False, indent=2))
    else:
        print(f"{a.cel}: " + ", ".join(f"{k} {v}" for k, v in licz.items()))
        for x in wyn:
            print(f"  [{x['waga']}] {x['co']} · {x['gdzie']}\n      → {x['poprawka']}")
    return 1 if licz["KRYTYCZNE"] or licz["WYSOKIE"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
