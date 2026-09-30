#!/usr/bin/env python3
"""Branding Jarvo w statycznych zasobach dashboardu Hermesa (uruchamiane przy budowie obrazu).

    python3 patch_dashboard.py <katalog-z-favicon>

Zmienia wyłącznie teksty i ikony widoczne dla użytkownika (tytuł karty, logo w menu, nazwę marki,
etykiety motywów, stronę logowania). Kod Hermesa zostaje bez zmian; licencja MIT i autorzy:
docs/SOURCES.md. Każda podmiana jest opcjonalna: nowa wersja Hermesa z innym układem plików
nie wywraca budowy, tylko wypisuje, czego nie znalazła (wyjątek: tytuł karty, bo to podstawa).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERMES = Path("/opt/hermes")
WEB = HERMES / "hermes_cli" / "web_dist"


CHANGED: set[Path] = set()


def sub_all(files, pattern: str, repl: str, label: str, flags=0) -> int:
    n = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        new, k = re.subn(pattern, repl, text, flags=flags)
        if k:
            f.write_text(new, encoding="utf-8")
            CHANGED.add(f)
            n += k
    print(f"  {'✓' if n else '·'} {label}: {n}")
    return n


def bust_cache(assets_dir: Path, index: Path) -> int:
    """Nowe nazwy dla zmienionych plików JS (i wszystkich, które je importują).

    Dashboard serwuje /assets/* z `Cache-Control: immutable` na rok, a nazwa pliku to hash treści
    z builda Hermesa. Po podmianie treści przeglądarka trzymałaby starą wersję, więc zmieniony plik
    dostaje przyrostek zależny od treści, a zmiana nazwy przechodzi w górę po importach aż do
    index.html (który nie jest cache'owany na stałe).
    """
    files = sorted(assets_dir.glob("*.js"))
    changed = {f for f in CHANGED if f.parent == assets_dir}
    if not changed:
        return 0
    digest = hashlib.sha1(b"".join(f.read_bytes() for f in sorted(changed))).hexdigest()[:6]
    texts = {f: f.read_text(encoding="utf-8") for f in files}
    names = {f.name for f in changed}
    grew = True
    while grew:  # domknięcie: kto importuje zmieniony plik, sam się zmienia
        grew = False
        for f in files:
            if f.name not in names and any(n in texts[f] for n in names):
                names.add(f.name); grew = True
    rename = {n: n[:-3] + f"-t{digest}.js" for n in names}
    pattern = re.compile("|".join(re.escape(n) for n in sorted(rename, key=len, reverse=True)))
    for f in files:
        new = pattern.sub(lambda m: rename[m.group(0)], texts[f])
        target = assets_dir / rename.get(f.name, f.name)
        target.write_text(new, encoding="utf-8")
        if target != f:
            f.unlink()
    html = index.read_text(encoding="utf-8")
    index.write_text(pattern.sub(lambda m: rename[m.group(0)], html), encoding="utf-8")
    print(f"  ✓ nowe nazwy plików (bez starej wersji w cache przeglądarki): {len(rename)}")
    return len(rename)


# Scalanie tłumaczenia z angielskim (jak defineLocale w dashboardzie): brakujący klucz = tekst angielski.
MERGE_JS = ("((a,b)=>{const m=(x,y)=>{if(!x||typeof x!='object'||Array.isArray(x)||!y||typeof y!='object'"
            "||Array.isArray(y))return y??x;const r={...x};for(const[k,v]of Object.entries(y)){if(v!==void 0)"
            "r[k]=m(r[k],v)}return r};return m(a,b)})")


def add_polish(assets: list[Path], index: Path, pl_json: Path) -> int:
    """Język polski w dashboardzie: tłumaczenie z branding/i18n/pl.json dopisane do mapy języków,
    „Polski” w przełączniku i polski jako język domyślny (dopóki ktoś nie wybierze innego)."""
    if not pl_json.is_file():
        print("  · polski: brak pl.json")
        return 0
    data = json.dumps(json.loads(pl_json.read_text(encoding="utf-8")), ensure_ascii=False, separators=(",", ":"))
    done = 0
    for f in assets:
        text = f.read_text(encoding="utf-8")
        if "hermes-locale" not in text or "Afrikaans" not in text:
            continue
        if ",pl:" in text and "Polski" in text:
            print("  · polski: już jest")
            return 0
        new, k1 = re.subn(r"([\w$]+)=\{en:([\w$]+),zh:",
                          lambda m: f"{m.group(1)}={{en:{m.group(2)},pl:{MERGE_JS}({m.group(2)},{data}),zh:", text, count=1)
        new, k2 = re.subn(r"=\{af:`Afrikaans`,", "={af:`Afrikaans`,pl:`Polski`,", new, count=1)
        new, k3 = re.subn(r"(localStorage\.getItem\([\w$]+\);if\([\w$]+&&[\w$]+\([\w$]+\)\)return [\w$]+\}catch\{\}return)`en`",
                          r"\1`pl`", new, count=1)
        if not (k1 and k2):
            print(f"  · polski: nie rozpoznano układu pliku języków (mapa {k1}, nazwy {k2})")
            return 0
        f.write_text(new, encoding="utf-8")
        CHANGED.add(f)
        done = 1
        print(f"  ✓ polski: tłumaczenie, przełącznik, domyślny ({'tak' if k3 else 'nie znaleziono'})")
        break
    if done:
        sub_all([index], r'<html lang="en"', '<html lang="pl"', "język strony")
        # pozycje menu bez klucza tłumaczenia (Files, MCP, Channels…) i zakładki pluginów dostają klucz
        # app.nav.<klucz>; bez tłumaczenia zostaje oryginalna etykieta
        sub_all(assets, r"path:`/(files|mcp|channels|webhooks|pairing|system)`,label:",
                r"path:`/\1`,labelKey:`\1`,label:", "menu: klucze tłumaczeń")
        sub_all(assets, r"\{path:([\w$]+)\.tab\.path,label:\1\.label,",
                r"{path:\1.tab.path,labelKey:`plugin_`+\1.name,label:\1.label,", "menu: zakładki pluginów")
    return done


SESSION_CARD = ("flex min-w-0 max-w-full flex-col gap-2 border border-border p-3 sm:flex-row sm:items-center "
                "sm:justify-between")
SESSION_LABELS = {"Total": "statTotal", "Active in store": "statActive", "Archived": "statArchived",
                  "Messages": "statMessages", "Sources": "statSources", "Import sessions": "importSessions"}


def patch_sessions(assets: list[Path]) -> int:
    """Strona Sesje: otwiera się na Historii (tam: otwórz, wznów w czacie, zmień nazwę, usuń, zaznacz wiele),
    karty „Ostatnie sesje” w Przeglądzie są klikalne (otwierają rozmowę w czacie), a etykiety wpisane
    w kod po angielsku biorą tłumaczenie (klucze sessions.* w pl.json; brak klucza = angielski)."""
    files = [f for f in assets if "Active in store" in f.read_text(encoding="utf-8")]
    if not files:
        print("  · sesje: nie znaleziono strony sesji")
        return 0
    n = sub_all(files, r"useState\)\(`overview`\)(,\[[\w$]+,[\w$]+\]=\(0,[\w$]+\.useState\)\(`chats`\))",
                r"useState)(`list`)\1", "sesje: domyślnie Historia")
    n += sub_all(files,
                 r"children:([\w$]+)\.status\.recentSessions(.{0,400}?)children:([\w$]+)\.map\(([\w$]+)=>"
                 r"\(0,([\w$]+)\.jsxs\)\(`div`,\{className:`" + re.escape(SESSION_CARD) + "`",
                 lambda m: (f"children:{m.group(1)}.status.recentSessions{m.group(2)}children:{m.group(3)}.map("
                            f"{m.group(4)}=>(0,{m.group(5)}.jsxs)(`div`,{{role:`button`,tabIndex:0,"
                            f"title:{m.group(1)}.sessions.resumeInChat,"
                            f"onClick:()=>location.assign(`/chat?resume=${{encodeURIComponent({m.group(4)}.id)}}`),"
                            f"onKeyDown:k=>{{k.key===`Enter`&&location.assign(`/chat?resume=${{encodeURIComponent({m.group(4)}.id)}}`)}},"
                            f"className:`cursor-pointer transition-colors hover:bg-muted/40 {SESSION_CARD}`"),
                 "sesje: klikalne karty ostatnich sesji", flags=re.S)
    for f in files:
        text = f.read_text(encoding="utf-8")
        m = re.search(r"label:([\w$]+)\.sessions\.overview", text)
        if not m:
            continue
        t = m.group(1)
        for en, key in SESSION_LABELS.items():
            n += sub_all([f], rf"children:`{re.escape(en)}`", f"children:{t}.sessions.{key}??`{en}`", f"sesje: „{en}”")
        n += sub_all([f], r"\?`Any chat source`:", f"?({t}.sessions.anyChatSource??`Any chat source`):",
                     "sesje: „Any chat source”")
    return n


# Strona logowania: marka Jarvo (logo, biel i czerwień, fonty VT323 / IBM Plex Mono jak w motywie Fosfor, linie CRT)
# i polskie napisy. Hermes buduje ją z szablonu str.format (w CSS podwójne klamry), więc CSS doklejamy osobno
# do szablonu logowania (klamry podwojone) i do strony „brak metod logowania” (klamry pojedyncze).
LOGIN_TEXTS = [
    (r'<html lang="en">', '<html lang="pl">', "język"),
    (r"<title>Sign in — Jarvo</title>", "<title>Logowanie — Jarvo</title>", "tytuł karty"),
    (r"<h1>Sign in</h1>", "<h1>Zaloguj się</h1>", "nagłówek"),
    (r"Choose a sign-in method to continue to Jarvo HQ\.", "Wejście do Jarvo HQ: Twojej floty agentów.", "opis"),
    (r"Public bind &middot; Auth required", "Dostęp tylko po zalogowaniu", "stopka"),
    (r"f'Sign in with \{", "f'Zaloguj przez {", "przycisk dostawcy"),
    (r"Sign in with \{plabel\}", "Nazwa użytkownika i hasło", "tytuł formularza"),
    (r'<span class="field-label">Username</span>', '<span class="field-label">Użytkownik</span>', "pole użytkownika"),
    (r'<span class="field-label">Password</span>', '<span class="field-label">Hasło</span>', "pole hasła"),
    (r'type="submit">Sign in</button>', 'type="submit">Zaloguj</button>', "przycisk"),
    (r"'Invalid username or password\.'", "'Zły użytkownik albo hasło.'", "błąd hasła"),
    (r"'Network error\. Please try again\.'", "'Błąd sieci. Spróbuj ponownie.'", "błąd sieci"),
    (r"<title>Sign-in unavailable — Jarvo</title>", "<title>Logowanie niedostępne — Jarvo</title>", "tytuł (brak metod)"),
    (r"<h1>Sign-in unavailable</h1>", "<h1>Logowanie niedostępne</h1>", "nagłówek (brak metod)"),
]
LOGIN_CSS = """
  /* ---- Jarvo: biel i czerwień, fonty i linie CRT motywu Fosfor (branding/patch_dashboard.py) ---- */
@@FONTS@@
  :root {
    --background-base: #10131C;
    --background: #10131C;
    --midground: #D4213D;
    --foreground: #F2F1E8;
    --jarvo-red-hi: #FF4D63;
    --hairline: color-mix(in srgb, #D4213D 30%, transparent);
    --hairline-strong: color-mix(in srgb, #D4213D 55%, transparent);
  }
  html, body { font-family: 'IBM Plex Mono', ui-monospace, monospace; }
  body {
    background-image:
      radial-gradient(ellipse at top, color-mix(in srgb, #D4213D 14%, transparent) 0%, transparent 60%),
      repeating-linear-gradient(to bottom, transparent 0 2px, rgba(0, 0, 0, .18) 2px 3px);
    background-size: auto, auto;
  }
  .brand {
    display: flex; flex-direction: column; align-items: center; gap: .55rem;
    font-family: VT323, 'IBM Plex Mono', monospace; font-weight: 400; font-size: 2.9rem; line-height: 1;
    letter-spacing: .38em; text-indent: .38em; color: var(--foreground); text-transform: uppercase;
    text-shadow: 0 0 12px rgba(212, 33, 61, .55);
  }
  .brand .logo { width: 76px; height: 76px; margin-bottom: .35rem; filter: drop-shadow(0 0 16px rgba(212, 33, 61, .5)); }
  .brand .tagline { font-size: 1.05rem; letter-spacing: .28em; text-indent: .28em; text-transform: none; color: var(--jarvo-red-hi); }
  .card {
    background: #151A26; border: 2px solid var(--midground);
    box-shadow: 0 0 24px -6px rgba(212, 33, 61, .6), inset 0 0 0 1px rgba(242, 241, 232, .04), 0 24px 60px -20px rgba(0, 0, 0, .7);
  }
  h1 { font-family: VT323, 'IBM Plex Mono', monospace; font-weight: 400; font-size: 2.5rem; letter-spacing: .06em; text-transform: none; line-height: 1.1; }
  h1::after { content: "▌"; color: var(--midground); margin-left: .12em; animation: jarvo-blink 1.06s steps(1) infinite; }
  @keyframes jarvo-blink { 0%, 49% { opacity: 1 } 50%, 100% { opacity: 0 } }
  .subtitle { font-size: .9rem; }
  .form-title, .field-label { font-family: 'IBM Plex Mono', monospace; letter-spacing: .14em; }
  .field-input { font-family: 'IBM Plex Mono', monospace; background: #0B0E15; }
  .field-input:focus-visible { border-color: var(--midground); box-shadow: 0 0 0 1px var(--midground), 0 0 12px rgba(212, 33, 61, .45); }
  .provider-btn {
    background: var(--midground); color: var(--foreground); font-family: VT323, 'IBM Plex Mono', monospace; font-weight: 400;
    font-size: 1.55rem; letter-spacing: .22em; line-height: 1; padding: .8rem 1rem;
    box-shadow: 0 0 16px -2px rgba(212, 33, 61, .7), inset 1px 1px 0 rgba(255, 255, 255, .25), inset -1px -1px 0 rgba(0, 0, 0, .4);
  }
  .provider-btn:hover { filter: none; background: var(--jarvo-red-hi); }
  .provider-btn:active { filter: none; background: var(--foreground); color: var(--background-base); }
  .provider-btn:focus-visible { outline-color: var(--foreground); }
  .form-error { color: var(--jarvo-red-hi); }
  footer { font-family: 'IBM Plex Mono', monospace; color: color-mix(in srgb, var(--foreground) 50%, transparent); }
  ::selection { background: var(--midground); color: var(--foreground); }
  @media (prefers-reduced-motion: reduce) { h1::after { animation: none; } }
"""


def login_fonts_css(brand: Path) -> str:
    """@font-face z fosfor.css, z adresami /fonts/… (publiczne; pliki pluginu HQ są za logowaniem)."""
    css = (brand / "fonts" / "fosfor.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"url\(([\w.-]+\.woff2)\)", r"url('/fonts/\1')", css).strip()


def patch_login(login: Path, brand: Path) -> None:
    for d in (WEB / "fonts", HERMES / "web" / "public" / "fonts"):
        if d.parent.is_dir():
            d.mkdir(exist_ok=True)
            for f in (brand / "fonts").glob("*.woff2"):
                shutil.copy(f, d / f.name)
    for pat, repl, label in LOGIN_TEXTS:
        sub_all([login], pat, repl, f"logowanie: {label}")
    svg = (brand / "favicon.svg").read_text(encoding="utf-8")
    svg = svg[svg.index("<svg"):].replace("<svg ", '<svg class="logo" aria-hidden="true" ', 1)
    svg = re.sub(r"<title.*?</desc>", "", svg, flags=re.S)
    assert "{" not in svg and "}" not in svg, "logo SVG nie może mieć klamer (szablon str.format)"
    sub_all([login], r'<div class="brand">Nous<span class="dot"></span>Research</div>',
            lambda m: f'<div class="brand">{svg}<span>Jarvo</span><span class="tagline">from idea to reality.</span></div>',
            "logowanie: marka i logo")
    css = LOGIN_CSS.replace("@@FONTS@@", login_fonts_css(brand))
    text = login.read_text(encoding="utf-8")
    if "---- Jarvo: biel i czerwień" in text:
        print("  · logowanie: kolory i fonty (już są)")
        return
    head, sep, tail = text.partition("_EMPTY_HTML = ")
    doubled = css.replace("{", "{{").replace("}", "}}")
    head = head.replace("</style>", doubled + "</style>", 1)
    tail = tail.replace("</style>", css + "</style>", 1)
    login.write_text(head + sep + tail, encoding="utf-8")
    print("  ✓ logowanie: kolory i fonty: 2")


def main(argv: list[str]) -> int:
    brand = Path(argv[0])
    for d in (WEB, HERMES / "web" / "public"):
        if d.is_dir():
            for name in ("favicon.ico", "favicon.svg"):
                shutil.copy(brand / name, d / name)
    assets = sorted((WEB / "assets").glob("*.js"))
    index = [WEB / "index.html"]
    print("Branding Jarvo w dashboardzie:")
    if not sub_all(index, r"<title>[^<]*</title>", "<title>Jarvo</title>", "tytuł karty"):
        print("Nie znaleziono <title> w index.html", file=sys.stderr)
        return 1
    sub_all(index, r'<link rel="icon"[^>]*>', '<link rel="icon" href="/favicon.ico" />', "favicon")
    # logo w menu: dwie linie "Hermes" / "Agent" → jedno słowo "Jarvo"
    sub_all(assets, r"children:\[`Hermes`,(\(0,[\w$]+\.jsx\)\(`br`,\{\}\)),`Agent`\]",
            r"children:[`Jarvo`]", "logo w menu")
    # zakładka BASE (plugin Jarvo HQ) w głównym menu nad CHAT, nie w sekcji „Plugins” na dole
    sub_all(assets, r"(function [\w$]+\(e,t\)\{let n=[\w$]+\(e,t\),r=new Set\()e\.map\(e=>e\.path\)(\))",
            r'\1[...e.map(e=>e.path),"/base"]\2', "BASE w głównym menu")
    sub_all(assets, r"brand:`Hermes Agent`,brandShort:`HA`", "brand:`Jarvo`,brandShort:`J`", "nazwa marki (i18n)")
    sub_all(assets, r"label:`Hermes Teal", "label:`Jarvo Teal", "etykiety motywów")
    # stopka menu: marka Jarvo i silnik (Hermes Agent, MIT) zamiast nazwy firmy Nous Research (wszystkie języki)
    sub_all(assets, r"footer:\{org:`Nous Research`\}", "footer:{org:`Jarvo · Hermes Agent`}", "stopka menu")
    add_polish(assets, index[0], brand / "i18n" / "pl.json")
    patch_sessions(assets)
    themes = HERMES / "hermes_cli" / "web_server_dashboard.py"
    if themes.is_file():
        sub_all([themes], r'"label": "Hermes Teal', '"label": "Jarvo Teal', "etykiety motywów (serwer)")
        # motywy użytkownika przekazują kolory terminala czatu (dashboard je obsługuje, serwer je gubił)
        if '"terminalBackground": data.get' not in themes.read_text(encoding="utf-8"):
            sub_all([themes], r'(\n(\s+)"layoutVariant": layout_variant,\n)',
                    r'\1\2"terminalBackground": data.get("terminalBackground") if _nonempty_str(data.get("terminalBackground")) else None,\n'
                    r'\2"terminalForeground": data.get("terminalForeground") if _nonempty_str(data.get("terminalForeground")) else None,\n',
                    "kolory terminala w motywach")
    login = HERMES / "hermes_cli" / "dashboard_auth" / "login_page.py"
    if login.is_file():
        sub_all([login], r"the Hermes Agent dashboard", "Jarvo HQ", "strona logowania (opis)")
        sub_all([login], r" — Hermes Agent<", " — Jarvo<", "strona logowania (tytuł)")
        patch_login(login, brand)
    bust_cache(WEB / "assets", WEB / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
