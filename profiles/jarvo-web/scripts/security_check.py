#!/usr/bin/env python3
"""Automatyczne sprawdzenia bezpieczeństwa strony/aplikacji (część mechaniczna skilla bezpieczenstwo-aplikacji).

    python3 security_check.py repo <katalog projektu> [--offline] [--json]   # kod: sekrety, .env w gicie, zależności, wzorce ryzyka
    python3 security_check.py url https://strona.pl [--json]                 # działająca strona: nagłówki, ciasteczka, CORS,
                                                                             # wycieki, klucze w JS wysyłanym do przeglądarki
    python3 security_check.py atak http://localhost:4321 [próby…] [--json]    # nieniszczące próby na działającej aplikacji

`atak` (tylko nasz podgląd albo aplikacja użytkownika za jego zgodą: `--zgoda-wlasciciela`), próby wybierasz flagami:
    --chronione /api/orders /admin       trasy, które bez sesji muszą odmówić (401/403/przekierowanie na logowanie)
    --sesja-a "Cookie: sid=…" --sesja-b "Authorization: Bearer …" --zasob-a /api/orders/17
                                         konto B nie może czytać zasobu konta A (IDOR); nagłówki kont testowych
    --logowanie /api/login               12 szybkich prób nieistniejącym kontem: oczekiwane 429 (limit prób)
    --limit /api/search                  12 szybkich żądań GET: oczekiwane 429 (endpointu AI z prawdziwym modelem nie testuj)
    --upload /api/upload[:pole]          plik HTML udający obrazek (z sesją A): oczekiwana odmowa 4xx
    --wyloguj /api/logout                na końcu: po wylogowaniu sesja A nie może działać (wymaga --zasob-a)

To nie zastępuje przeglądu kodu (model czyta przepływ danych: skill, references/przeglad-kodu.md), tylko łapie
to, co da się wykryć maszynowo i bez fałszywych alarmów. Każde ustalenie ma wagę: KRYTYCZNE / WYSOKIE / ŚREDNIE / NISKIE.
Kod wyjścia: 0 = brak KRYTYCZNYCH i WYSOKICH, 1 = są, 2 = złe wejście albo brak zgody. Sieć: badana strona, a w `repo`
rejestry npm i PyPI (czy zależności istnieją, wiek, pobrania; `--offline` pomija). Bez zależności poza biblioteką standardową.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import ipaddress
import json
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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

# Popularne pakiety: zależność o nazwie różnej o 1 znak i mało pobierana to kandydat na podszycie (typosquatting)
# albo nazwa zmyślona przez model i zarejestrowana przez kogoś innego (slopsquatting).
POPULARNE_NPM = """react react-dom next vue nuxt svelte astro vite webpack typescript express fastify koa axios lodash
underscore moment dayjs date-fns zod yup joi prisma mongoose sequelize knex pg mysql2 redis ioredis jsonwebtoken bcrypt
bcryptjs argon2 passport helmet cors dotenv uuid nanoid chalk commander yargs inquirer debug winston pino morgan
body-parser cookie-parser multer sharp jimp puppeteer playwright cheerio jsdom marked dompurify tailwindcss postcss
autoprefixer eslint prettier jest vitest mocha chai sinon supertest nodemon rimraf glob minimist semver ws socket.io
graphql apollo-server stripe openai @anthropic-ai/sdk @supabase/supabase-js firebase aws-sdk @aws-sdk/client-s3
nodemailer resend twilio bullmq cron node-fetch got superagent qs formidable busboy rxjs immer zustand redux
@reduxjs/toolkit react-router react-router-dom @tanstack/react-query swr clsx classnames framer-motion three
chart.js d3 leaflet mapbox-gl sass less styled-components @emotion/react""".split()
POPULARNE_PYPI = """requests urllib3 httpx aiohttp flask django fastapi starlette uvicorn gunicorn pydantic sqlalchemy
alembic psycopg2 psycopg2-binary psycopg asyncpg pymysql redis celery boto3 botocore numpy pandas scipy matplotlib
pillow opencv-python scikit-learn torch tensorflow transformers openai anthropic langchain tiktoken beautifulsoup4
lxml selenium playwright pytest black ruff mypy flake8 click typer rich pyyaml python-dotenv jinja2 werkzeug
cryptography pyjwt bcrypt argon2-cffi passlib stripe twilio sentry-sdk python-multipart markdown bleach""".split()
UWAGI: list[str] = []          # czego nie dało się ocenić (brak sieci, limit rejestru): nigdy „czysto”
SPRAWDZONE: list[str] = []     # próby `atak`, które przeszły (dowód do listy kontrolnej)


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


def odleglosc1(a: str, b: str) -> bool:
    """Czy nazwy różnią się dokładnie jedną edycją (wstawienie, usunięcie, zamiana, przestawienie sąsiadów)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        rozne = [i for i in range(len(a)) if a[i] != b[i]]
        return len(rozne) == 1 or (len(rozne) == 2 and rozne[1] == rozne[0] + 1 and a[rozne[0]] == b[rozne[1]] and a[rozne[1]] == b[rozne[0]])
    krotsza, dluzsza = sorted((a, b), key=len)
    return any(dluzsza[:i] + dluzsza[i + 1:] == krotsza for i in range(len(dluzsza)))


def manifesty(root: Path) -> list[tuple[str, str, str]]:
    """(ekosystem, nazwa, plik) dla zależności bezpośrednich: package.json, requirements*.txt, pyproject.toml."""
    out = []
    pj = root / "package.json"
    if pj.is_file():
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
        except ValueError:
            d = {}
        for sekcja in ("dependencies", "devDependencies", "optionalDependencies"):
            for nazwa, spec in (d.get(sekcja) or {}).items():
                if not re.match(r"(file|link|workspace|git\+|github:|https?:|npm:)", str(spec)):
                    out.append(("npm", nazwa, "package.json"))
    for req in sorted(root.glob("requirements*.txt")):
        for linia in req.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", linia)
            if m and not linia.lstrip().startswith(("#", "-")):
                out.append(("pypi", m.group(1), req.name))
    pp = root / "pyproject.toml"
    if pp.is_file():
        try:
            d = tomllib.loads(pp.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            d = {}
        proj = d.get("project") or {}
        for spec in (proj.get("dependencies") or []) + [x for g in (proj.get("optional-dependencies") or {}).values() for x in g]:
            m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
            if m:
                out.append(("pypi", m.group(1), "pyproject.toml"))
    return list(dict.fromkeys(out))


def _json_z(url: str, timeout=10):
    """(kod, dane) z rejestru; kod 0 = brak odpowiedzi (sieć)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "jarvo-web-security/1.0",
                                                                          "Accept": "application/json"}), timeout=timeout) as r:
            return r.status, json.loads(r.read(8_000_000) or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, None


def pakiet(eko: str, nazwa: str) -> dict:
    """Istnieje? Od kiedy? Ile pobrań tygodniowo? (None = nieznane)."""
    if eko == "npm":
        kod, dl = _json_z(f"https://api.npmjs.org/downloads/point/last-week/{urllib.parse.quote(nazwa, safe='@')}")
        pobrania = (dl or {}).get("downloads") if kod == 200 else None
        if pobrania is not None and pobrania >= 10_000:
            return {"istnieje": True, "pobrania": pobrania, "utworzony": None}
        kod, doc = _json_z(f"https://registry.npmjs.org/{urllib.parse.quote(nazwa, safe='@')}")
        if kod == 404:
            return {"istnieje": False}
        if kod != 200:
            return {"istnieje": None}
        return {"istnieje": True, "pobrania": pobrania, "utworzony": ((doc or {}).get("time") or {}).get("created")}
    kod, doc = _json_z(f"https://pypi.org/pypi/{urllib.parse.quote(nazwa)}/json")
    if kod == 404:
        return {"istnieje": False}
    if kod != 200:
        return {"istnieje": None}
    daty = [f.get("upload_time_iso_8601") for pliki_ in ((doc or {}).get("releases") or {}).values() for f in pliki_]
    kod2, st = _json_z(f"https://pypistats.org/api/packages/{nazwa.lower()}/recent")
    return {"istnieje": True, "utworzony": min((d for d in daty if d), default=None),
            "pobrania": ((st or {}).get("data") or {}).get("last_week") if kod2 == 200 else None}


def zaleznosci(root: Path, dzis: dt.date | None = None) -> list[dict]:
    """Czy zależności z manifestów istnieją w rejestrze, nie są świeże i mało używane, nie udają popularnych nazw."""
    lista = manifesty(root)[:200]
    if not lista:
        return []
    dzis = dzis or dt.date.today()
    with ThreadPoolExecutor(6) as ex:
        dane = list(ex.map(lambda x: pakiet(x[0], x[1]), lista))
    wyn = []
    for (eko, nazwa, plik), d in zip(lista, dane):
        if d.get("istnieje") is None:
            UWAGI.append(f"{eko} {nazwa}: rejestr nie odpowiedział, nie oceniono")
            continue
        if d["istnieje"] is False:
            wyn.append(u("WYSOKIE", f"zależność {nazwa} nie istnieje w rejestrze {eko} (nazwa zmyślona?)", plik,
                         "usuń albo znajdź prawdziwy pakiet; nazwę sprawdza człowiek w rejestrze, zanim ktoś ją zarejestruje"))
            continue
        pobrania, wiek = d.get("pobrania"), None
        if d.get("utworzony"):
            try:
                wiek = (dzis - dt.date.fromisoformat(d["utworzony"][:10])).days
            except ValueError:
                pass
        malo = pobrania is not None and pobrania < 1000
        popularne = POPULARNE_NPM if eko == "npm" else POPULARNE_PYPI
        podobny = next((p for p in popularne if odleglosc1(nazwa.lower(), p)), None)
        if podobny and (pobrania is None or pobrania < 10_000):
            wyn.append(u("WYSOKIE", f"zależność {nazwa} różni się jedną literą od popularnego {podobny} "
                         f"({pobrania if pobrania is not None else '?'} pobrań/tydz.)", plik,
                         f"literówka albo podszycie: użyj {podobny}, chyba że {nazwa} to świadomy wybór z opisem"))
        elif wiek is not None and wiek < 90 and (malo or pobrania is None):
            wyn.append(u("ŚREDNIE", f"zależność {nazwa} jest nowa ({wiek} dni) i mało używana "
                         f"({pobrania if pobrania is not None else '?'} pobrań/tydz.)", plik,
                         "sprawdź repozytorium, autora i skrypty instalacyjne; w razie wątpliwości zamień na znany pakiet"))
    return wyn


class BezPrzekierowan(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def pobierz(url: str, method="GET", headers=None, timeout=15, limit=3000, dane: bytes | None = None, przekierowania=True):
    req = urllib.request.Request(url, data=dane, method=method, headers={"User-Agent": "jarvo-web-security/1.0", **(headers or {})})
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                         *([] if przekierowania else [BezPrzekierowan()]))
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.headers.get_all("Set-Cookie") or [], r.read(limit)
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.headers.get_all("Set-Cookie") or [], e.read(limit)


def rola_jwt(token: str) -> str | None:
    """Rola z JWT Supabase (anon jest publiczny z założenia, service_role nigdy)."""
    try:
        cz = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(cz + "=" * (-len(cz) % 4))).get("role")
    except (IndexError, ValueError):
        return None


def sekrety_w_js(tekst: str, gdzie: str) -> list[dict]:
    wyn = []
    for nazwa, wz in SEKRETY[:8]:
        for m in re.finditer(wz, tekst):
            s = m.group(0)
            if re.search(r"(?i)(example|placeholder|your|xxx|dummy)", s):
                continue
            if nazwa.startswith("klucz Supabase") and rola_jwt(s) not in ("service_role", "supabase_admin"):
                continue                                   # klucz anon: publiczny z założenia, chroni go RLS
            if nazwa == "klucz Google API":
                wyn.append(u("ŚREDNIE", "klucz Google API w JS strony", gdzie,
                             "klucze Maps/Firebase bywają publiczne: ogranicz je (referrer, lista API) w konsoli Google"))
            else:
                wyn.append(u("KRYTYCZNE", f"{nazwa} w JS wysyłanym do przeglądarki", gdzie,
                             "klucz tylko na serwerze (trasa API/proxy); UNIEWAŻNIJ klucz u dostawcy"))
            break
    return wyn


def skrypty_strony(base: str, html: str) -> list[str]:
    """Adresy skryptów tej samej domeny z <script src> i <link rel=modulepreload> (maks. 20)."""
    host = urllib.parse.urlsplit(base).netloc
    adresy = re.findall(r"<script[^>]+src=[\"']([^\"']+)", html, re.I)
    adresy += re.findall(r"<link[^>]+rel=[\"']modulepreload[\"'][^>]*href=[\"']([^\"']+)", html, re.I)
    pelne = [urllib.parse.urljoin(base + "/", a) for a in adresy]
    return list(dict.fromkeys(a for a in pelne if urllib.parse.urlsplit(a).netloc == host))[:20]


def strona(url: str) -> list[dict]:
    wyn = []
    base = url.rstrip("/")
    st, h, cookies, body = pobierz(base, limit=3_000_000)
    html = body.decode("utf-8", "replace")
    wyn += sekrety_w_js(html, base)                              # skrypty wbudowane w HTML
    for js in skrypty_strony(base, html):
        s, _, _, b = pobierz(js, limit=8_000_000)
        if s == 200:
            wyn += sekrety_w_js(b.decode("utf-8", "replace"), js)
    body = body[:3000]
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


def lokalny(url: str) -> bool:
    """Nasz podgląd: localhost, *.localhost/.local/.test albo adres prywatny."""
    host = urllib.parse.urlsplit(url).hostname or ""
    if host == "localhost" or host.endswith((".localhost", ".local", ".test", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


def naglowek(linia: str | None) -> dict:
    """„Cookie: sid=…” → {"Cookie": "sid=…"}; puste → {}."""
    if not linia:
        return {}
    k, _, v = linia.partition(":")
    return {k.strip(): v.strip()}


def _odmowa(status: int, h: dict) -> bool:
    return status in (401, 403, 404) or (status in (301, 302, 303, 307, 308) and re.search(r"(?i)log|sign|auth", h.get("location", "")))


def atak(base: str, a) -> list[dict]:
    """Nieniszczące próby na działającej aplikacji. Każda próba to kilka żądań; nic nie jest kasowane ani kupowane."""
    base, wyn = base.rstrip("/"), []
    sa, sb = naglowek(a.sesja_a), naglowek(a.sesja_b)
    url = lambda sciezka: base + "/" + sciezka.lstrip("/")          # tylko ścieżki: zostajemy na badanym hoście
    _, _, _, wzor404 = pobierz(url(f"jarvo-nie-istnieje-{secrets.token_hex(4)}"), limit=20000, przekierowania=False)

    for sciezka in a.chronione or []:                                 # 1. trasy bez sesji
        s, h, _, b = pobierz(url(sciezka), limit=20000, przekierowania=False)
        if _odmowa(s, h):
            SPRAWDZONE.append(f"{sciezka} bez sesji: {s} (odmowa)")
        elif s == 200 and b == wzor404:
            UWAGI.append(f"{sciezka} bez sesji: 200 jak dla nieistniejącej strony (SPA); sprawdź trasę API, nie widok")
        elif s < 300:
            wyn.append(u("WYSOKIE", f"{sciezka} odpowiada bez logowania ({s})", url(sciezka),
                         "sprawdzenie sesji i roli w handlerze/middleware serwera, nie tylko ukrycie w UI"))
        else:
            UWAGI.append(f"{sciezka} bez sesji: {s}, nie oceniono")

    for sciezka in a.zasob_a or []:                                   # 2. cudzy zasób (IDOR)
        s_a, _, _, b_a = pobierz(url(sciezka), headers=sa, limit=200000, przekierowania=False)
        if s_a != 200:
            UWAGI.append(f"{sciezka}: konto A dostało {s_a}, a powinno widzieć własny zasób; próba IDOR pominięta")
            continue
        s_b, h_b, _, b_b = pobierz(url(sciezka), headers=sb, limit=200000, przekierowania=False)
        if s_b == 200 and b_b == b_a:
            wyn.append(u("WYSOKIE", f"konto B czyta zasób konta A ({sciezka})", url(sciezka),
                         "zapytanie z właścicielem z sesji: where id = $1 and user_id = $2; RLS w bazie"))
        elif _odmowa(s_b, h_b) or s_b == 200:
            SPRAWDZONE.append(f"{sciezka} sesją konta B: {s_b}" + (" (inna treść niż u A)" if s_b == 200 else " (odmowa)"))
        s0, h0, _, _ = pobierz(url(sciezka), limit=2000, przekierowania=False)
        if s0 < 300 and not _odmowa(s0, h0):
            wyn.append(u("WYSOKIE", f"zasób konta A dostępny bez logowania ({sciezka})", url(sciezka), "sprawdzenie sesji na serwerze"))

    def seria(sciezka: str, metoda: str, cialo: bytes | None, naglowki: dict) -> list[int]:
        kody = []
        for _ in range(12):
            s, _, _, _ = pobierz(url(sciezka), method=metoda, headers=naglowki, dane=cialo, limit=500, przekierowania=False)
            kody.append(s)
            if s == 429:
                break
        return kody

    if a.logowanie:                                                   # 3. limit prób logowania
        cialo = json.dumps({"email": f"jarvo-test-{secrets.token_hex(3)}@example.invalid",
                            "password": secrets.token_urlsafe(12)}).encode()
        kody = seria(a.logowanie, "POST", cialo, {"Content-Type": "application/json"})
        if set(kody) <= {404, 405}:
            UWAGI.append(f"{a.logowanie}: trasa nie istnieje albo nie przyjmuje POST ({kody[0]}), nie oceniono")
        elif 429 in kody:
            SPRAWDZONE.append(f"{a.logowanie}: limit prób działa (429 po {len(kody)} próbach)")
        else:
            wyn.append(u("WYSOKIE", f"logowanie bez limitu prób: 12 prób, kody {sorted(set(kody))}", url(a.logowanie),
                         "limit na IP i konto (np. 5/min) z 429 i Retry-After; blokada po serii błędów"))
    for sciezka in a.limit or []:                                     # 4. limit żądań na trasie
        kody = seria(sciezka, "GET", None, sa)
        if set(kody) <= {404, 405}:
            UWAGI.append(f"{sciezka}: trasa nie istnieje ({kody[0]}), nie oceniono")
        elif 429 in kody:
            SPRAWDZONE.append(f"{sciezka}: limit żądań działa (429 po {len(kody)})")
        else:
            wyn.append(u("ŚREDNIE", f"{sciezka} bez limitu żądań: 12 żądań, kody {sorted(set(kody))}", url(sciezka),
                         "limit na użytkownika i IP; przy endpointach AI także limit długości wejścia i max_tokens"))

    if a.upload:                                                      # 5. plik HTML udający obrazek
        sciezka, _, pole = a.upload.partition(":")
        granica = "jarvo" + secrets.token_hex(8)
        tresc = b"<html><body><script>alert(document.domain)</script></body></html>"
        cialo = (f"--{granica}\r\nContent-Disposition: form-data; name=\"{pole or 'file'}\"; filename=\"obrazek.jpg\"\r\n"
                 f"Content-Type: image/jpeg\r\n\r\n").encode() + tresc + f"\r\n--{granica}--\r\n".encode()
        s, _, _, b = pobierz(url(sciezka), method="POST", dane=cialo, limit=20000, przekierowania=False,
                             headers={**sa, "Content-Type": f"multipart/form-data; boundary={granica}"})
        if 400 <= s < 500:
            SPRAWDZONE.append(f"{sciezka}: HTML jako obrazek odrzucony ({s})")
        elif 200 <= s < 300:
            gdzie = re.search(rb"[\w./-]+\.jpg", b)
            waga, co = "WYSOKIE", "upload przyjął plik HTML udający obrazek"
            if gdzie:
                s2, h2, _, _ = pobierz(url(gdzie.group(0).decode()), limit=500)
                if s2 == 200 and "html" in h2.get("content-type", ""):
                    waga, co = "KRYTYCZNE", "upload przyjął HTML i serwuje go jako stronę (XSS z pliku)"
            wyn.append(u(waga, co, url(sciezka), "typ po zawartości (magic bytes), lista typów, losowa nazwa, osobna domena/"
                         "bucket z Content-Disposition: attachment i nosniff"))
        else:
            UWAGI.append(f"{sciezka}: upload odpowiedział {s}, nie oceniono")

    if a.wyloguj:                                                     # 6. sesja po wylogowaniu (na końcu)
        if not (a.zasob_a and sa):
            UWAGI.append("--wyloguj wymaga --sesja-a i --zasob-a; pominięte")
        else:
            pobierz(url(a.wyloguj), method="POST", headers=sa, dane=b"", limit=500, przekierowania=False)
            s, h, _, _ = pobierz(url(a.zasob_a[0]), headers=sa, limit=500, przekierowania=False)
            if _odmowa(s, h):
                SPRAWDZONE.append(f"po wylogowaniu stara sesja nie działa ({s})")
            elif s == 200:
                wyn.append(u("ŚREDNIE", "stara sesja działa po wylogowaniu", url(a.wyloguj),
                             "unieważnienie sesji na serwerze (lista odwołanych albo krótki JWT + odświeżanie z rotacją)"))
    return wyn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tryb", choices=["repo", "url", "atak"])
    ap.add_argument("cel")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--offline", action="store_true", help="repo: bez pytania rejestrów npm/PyPI o zależności")
    ap.add_argument("--zgoda-wlasciciela", action="store_true", help="atak na adres spoza podglądu: właściciel się zgodził")
    ap.add_argument("--chronione", nargs="+")
    ap.add_argument("--sesja-a")
    ap.add_argument("--sesja-b")
    ap.add_argument("--zasob-a", nargs="+")
    ap.add_argument("--logowanie")
    ap.add_argument("--limit", nargs="+")
    ap.add_argument("--upload")
    ap.add_argument("--wyloguj")
    a = ap.parse_args(argv)
    if a.tryb == "repo" and not Path(a.cel).is_dir():
        print("✗ brak katalogu", file=sys.stderr)
        return 2
    if a.tryb == "atak" and not (lokalny(a.cel) or a.zgoda_wlasciciela):
        print("✗ atak tylko na naszym podglądzie (localhost, adres prywatny) albo z --zgoda-wlasciciela "
              "po zgodzie właściciela aplikacji", file=sys.stderr)
        return 2
    if a.tryb == "repo":
        wyn = repo(Path(a.cel)) + ([] if a.offline else zaleznosci(Path(a.cel)))
    else:
        wyn = strona(a.cel) if a.tryb == "url" else atak(a.cel, a)
    wyn.sort(key=lambda x: WAGI.index(x["waga"]))
    licz = {w: sum(x["waga"] == w for x in wyn) for w in WAGI}
    if a.json:
        print(json.dumps({"cel": a.cel, "tryb": a.tryb, "podsumowanie": licz, "ustalenia": wyn, "sprawdzone": SPRAWDZONE,
                          "nie_ocenione": UWAGI}, ensure_ascii=False, indent=2))
    else:
        print(f"{a.cel}: " + ", ".join(f"{k} {v}" for k, v in licz.items()))
        for x in wyn:
            print(f"  [{x['waga']}] {x['co']} · {x['gdzie']}\n      → {x['poprawka']}")
        for s in SPRAWDZONE:
            print(f"  ✓ {s}")
        for s in UWAGI:
            print(f"  ? {s}")
    return 1 if licz["KRYTYCZNE"] or licz["WYSOKIE"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
