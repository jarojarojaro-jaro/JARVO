#!/usr/bin/env python3
"""Buduje gotowe dystrybucje profili Hermesa z tego repo.

    python scripts/build.py --hermes-src /opt/hermes [--env-file /srv/jarvo/compose/jarvo.env]
    python scripts/build.py --uklad natywny --dane <HERMES_HOME> --hermes-src <checkout Hermesa> --out <root>/build
        [--repo-dir <kod Jarva>] [--bin-dir <program>/bin-floty] [--tools-dir <program>/narzedzia-floty] [--py <python>]
        [--system windows|macos|linux] [--node-modules <narzędzia npm>] [--chrome <chrome-headless-shell>]

Wynik: build/
  profiles/<agent>/   dystrybucja gotowa do `hermes profile install` / `update`
  host/config.yaml    config profilu hosta (default): gateway, trasy Telegrama, kanban
  host/srodowisko.json  (tylko natywnie) zmienne bramy z buildu: HERMES_LOCAL_STT_COMMAND, na Windows także
                      AGENT_BROWSER_EXECUTABLE_PATH (Chromium silnika chrome)
  plugins/            jarvo-hq, jarvo-wiedza, jarvo-komputer; natywnie także jarvo-zgody (tryby zgód, zgody/)
  BUILD.json          manifest (commit repo, źródła skilli, agenci; natywnie także układ i ścieżki)

Układ (`--uklad`, docs/NATYWNIE.md S06): `kontener` (domyślny) daje dzisiejsze ścieżki obrazu (/opt/data, /opt/jarvo/…),
bajt w bajt jak przed układem natywnym; `natywny` bierze ścieżki instalacji (`--dane` i katalogi programu, zawsze z „/”)
i wartości zależne od systemu: silnik przeglądarki, wyszukiwarka (autodetekcja Hermesa, decyzja I14), polecenia STT i TTS
bramy, serwery MCP z Node (P06), zakazy dla katalogu danych w każdej pisowni, wtyczka zgód i tryb zgód profilu czatu.

Kroki dla każdego aktywnego agenta z fleet.yaml:
  1. kopia profiles/<agent>/ (bez plików roboczych),
  2. SOUL.md: wstawienie wspólnego protokołu (i skrótu floty dla Jarva),
  3. profile.yaml z opisem z fleet.yaml (routing kanbana, roster),
  4. config.yaml: podstawienie tokenów @@...@@ (modele, katalogi, strefa czasowa) i wartości układu,
  5. skille zewnętrzne z vendor/skills.lock.yaml (+ licencje, + DESCRIPTION.md kategorii); każdy przechodzi
     skan bezpieczeństwa (scripts/skan_skilli.py): high/critical bez wyjątku z vendor/skan-wyjatki.yaml
     zatrzymuje build; wspólne skille Jarva (shared/skills) dostają tokeny jak skille własne,
  6. dla Jarva: skill `roster` i rubryki sędziego generowane z fleet.yaml i quality/rubric.md,
  7. cron/jobs.yaml → cron/jobs.json (przez API crona Hermesa, stałe ID zadań).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402
import skan_skilli  # noqa: E402

ISO_KROJ = fl.ISO_KROJE
COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".DS_Store", "node_modules", ".git", ".github", ".env", "*.env", "jobs.yaml"
)

CATEGORY_DESCRIPTIONS = {
    # kategorie własne
    "fleet": "Dowodzenie flotą Jarvo: przyjmowanie zleceń, misje, karty, ocena, decyzje, patrol, raporty.",
    "sherlock": "Metoda śledcza: wieloźródłowy research, weryfikacja faktów, raporty z cytatami.",
    "web": "Workflowy Web Senior Deva: brand z URL, audyty, nowe strony, landingi, favicony, obrazy, wdrożenia.",
    "studio": "Workflowy Studio: pakiety kampanii, grafiki social, filmy z kodu, generacja AI, formaty, copy PL, publikacja.",
    "bezpieczenstwo": "Bezpieczeństwo aplikacji (CC BY-SA, bez zmian): przegląd kodu wg OWASP (getsentry), ryzyko zależności (Trail of Bits).",
    "kod": "Praca na kodzie: mapa repo (graf wywołań), wpływ zmian przed refaktorem, debugowanie od przyczyny.",
    "reka": "Workflowy prawej ręki: składanie pakietów misji, dokumenty i konwersje, szybkie prototypy, granice.",
    # kategorie skilli zewnętrznych
    "research": "Narzędzia researchu z Hermesa (MIT): wyszukiwarki, cytowanie, arXiv, YouTube, Reddit, RSS, OSINT firm.",
    "market": "Research rynku (marketingskills, MIT): profile konkurencji, research klientów.",
    "web-quality": "Jakość stron (web-quality-skills, MIT): audyt, Core Web Vitals, wydajność, dostępność, dobre praktyki.",
    "seo": "SEO techniczne i on-page (claude-seo, MIT): audyt, schema, obrazy, sitemap, hreflang, GEO, local, programmatic.",
    "marketing": "Marketing (marketingskills, MIT): copy, social, content, launch, reklamy, psychologia, e-maile, CRO.",
    "design": "Design (Anthropic skills Apache-2.0 + Hermes MIT + izometria Jarva): frontend, systemy designu, grafika, figury izometryczne, motywy, testy UI.",
    "deploy": "Publikacja stron (Hermes, MIT): wersjonowane wdrożenia i tymczasowe podglądy. Produkcja tylko za zgodą.",
    "video": "Wideo z kodu: HyperFrames, Remotion (+ iart: typografia, wykresy, belki), motion-broll, lemo-opuscar, anidoodle, bang-motion, pixel2motion (logo), Lottie.",
    "gsap": "GSAP (oficjalne skille GreenSock, MIT): osie czasu, ScrollTrigger, pluginy, React, wydajność.",
    "threejs": "Three.js (threejs-skills, MIT): scena, geometria, materiały, światło, shadery, animacja, loadery.",
    "motion": "Ruch w UI (skille Emila Kowalskiego, MIT): krzywe i czasy, przegląd i poprawa animacji, słownik ruchu.",
    "screenwriting": "Warsztat scenarzysty (screenwriting-skills, MIT): premisa, scena, dialog, konflikt; do skilla scenariusz.",
    "creative": "Kreacja (Hermes, MIT): Manim (u nas silnik ManimGX), infografiki, humanizer, kalendarz social, ideacja, memy, diagramy.",
    "meta": "Meta-skille: tworzenie i ulepszanie skilli (Anthropic skill-creator, Apache-2.0; mattpocock writing-for-agents, MIT).",
}


# ----------------------------------------------------------------------------- env

def zapisz(path: Path, tekst: str) -> None:
    """Plik dystrybucji z LF na każdym systemie: Hermes, skarbiec i sumy plików widzą te same bajty co z Linuksa."""
    path.write_text(tekst, encoding="utf-8", newline="\n")


def read_env_file(path: Path | None) -> dict[str, str]:
    env: dict[str, str] = {}
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    # zmienne środowiska procesu mają pierwszeństwo
    for key, value in os.environ.items():
        if key.startswith(("JARVO_", "TELEGRAM_")):
            env[key] = value
    return env


# --------------------------------------------------------------------------- układ

UKLADY = ("kontener", "natywny")
SYSTEMY = ("windows", "macos", "linux")


@dataclass(frozen=True)
class Uklad:
    """Instalacja, dla której budujemy (docs/NATYWNIE.md S06). `kontener`: ścieżki obrazu, te same napisy co przed
    układem natywnym (kontener działa bez zmian do etapu E13). `natywny`: ścieżki instalacji natywnej i wartości
    zależne od systemu. Ścieżki zawsze z „/” (as_posix): w YAML w podwójnym cudzysłowie „\\” zaczyna sekwencję
    ucieczki („C:\\Users” to ScannerError), a w poleceniach powłoki „\\” poza cudzysłowem znika."""
    nazwa: str = "kontener"
    system: str = "linux"
    dane: str = "/opt/data"                        # HERMES_HOME (@@DATA_DIR@@)
    repo: str = "/opt/jarvo/repo"                  # kod Jarva (@@REPO_DIR@@)
    build: str = "/opt/jarvo/build"                # ten build w działającej instalacji (@@BUILD_DIR@@)
    narzedzia: str = "/opt/data/jarvo/narzedzia"   # instalacje narzędzi floty w locie (@@TOOLS_DIR@@)
    bin: str = "/opt/jarvo/bin"                    # programy floty (@@BIN_DIR@@)
    py: str = "python3"                            # Python skryptów floty jako słowo polecenia (@@PY@@)
    dom: str = ""                                  # katalog domowy właściciela: zakazy w pisowni „~” (natywnie)
    node_modules: str = "/opt/jarvo/node/node_modules"   # narzędzia npm floty (infra/node): serwery MCP z Node
    chrome: str = ""                               # natywnie: Chromium dla silnika chrome (AGENT_BROWSER_EXECUTABLE_PATH)

    @property
    def natywny(self) -> bool:
        return self.nazwa == "natywny"

    @property
    def windows(self) -> bool:
        return self.natywny and self.system == "windows"


KONTENER = Uklad()
# katalogi danych floty względem <dane>: klucz w fleet.yaml `shared` i wartość, gdy go brak
KATALOGI_DANYCH = (("JARVO_DIR", "jarvo_dir", "jarvo"), ("KNOWLEDGE_DIR", "knowledge_dir", "jarvo/knowledge"),
                   ("MISSIONS_DIR", "missions_dir", "jarvo/missions"),
                   ("WORKSPACES_DIR", "workspaces_dir", "jarvo/workspaces"), ("INBOX_DIR", "inbox_dir", "jarvo/inbox"))
KOMPUTER_KONTENERA = "/opt/jarvo/komputer"         # gniazda Komputera w kontenerze; natywnie <dane>/jarvo/komputer (c1)


def system_tego_komputera() -> str:
    return "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"


def sciezka_ukladu(wartosc: str | os.PathLike, system: str, opcja: str) -> str:
    """Ścieżka bezwzględna z „/” dla systemu docelowego. Bez resolve(): na Windows rozwinąłby krótką nazwę 8.3,
    a <program> ma zostać w ścieżce ASCII, którą podał instalator (docs/NATYWNIE.md B13)."""
    tekst = str(wartosc).strip()
    na_tym = system == system_tego_komputera()
    if na_tym:
        tekst = os.path.abspath(os.path.expanduser(tekst))
    p = PureWindowsPath(tekst) if system == "windows" else PurePosixPath(tekst)
    if not p.is_absolute():
        raise SystemExit(f"--{opcja}: {wartosc!r} nie jest ścieżką bezwzględną dla systemu {system}")
    tekst = p.as_posix()
    # znaki, których nie da się bezpiecznie wstawić do YAML w cudzysłowie i do poleceń w cudzysłowie
    zle = sorted({c for c in tekst if c in '"`$\n\r' or (c == "\\" and system != "windows")})
    if zle:
        raise SystemExit(f"--{opcja}: ścieżka {tekst!r} ma znaki {''.join(zle)!r}, których build nie wstawi do YAML i "
                         "poleceń; wybierz katalog bez nich")
    return tekst


def slowo_polecenia(sciezka: str) -> str:
    """Program jako słowo polecenia powłoki: bez zmian, gdy ma same bezpieczne znaki (kontener: `python3`),
    inaczej w podwójnym cudzysłowie (spacja albo polskie litery w nazwie użytkownika)."""
    return sciezka if re.fullmatch(r"[A-Za-z0-9_./:@%+=,-]+", sciezka) else f'"{sciezka}"'


def uklad_z_argumentow(args: argparse.Namespace) -> Uklad:
    """Układ z opcji build.py. Kontener: dzisiejsze ścieżki obrazu (każdą można nadpisać opcją). Natywnie domyślne
    wartości idą za układem katalogów z docs/NATYWNIE.md (c1): <root>/dane, <root>/program/{bin-floty,
    narzedzia-floty}; instalator podaje je jawnie (<program> w ścieżce ASCII)."""
    if args.uklad != "natywny":
        if args.system not in (None, "linux"):
            raise SystemExit("--system dotyczy układu natywnego (kontener to zawsze Linux)")
        if args.node_modules or args.chrome:
            raise SystemExit("--node-modules i --chrome dotyczą układu natywnego (kontener ma ścieżki obrazu)")

        def k(wartosc, domyslna: str, opcja: str) -> str:
            return sciezka_ukladu(wartosc, "linux", opcja) if wartosc else domyslna
        return Uklad(dane=k(args.dane, KONTENER.dane, "dane"), repo=k(args.repo_dir, KONTENER.repo, "repo-dir"),
                     build=k(args.runtime_build_dir, KONTENER.build, "runtime-build-dir"),
                     narzedzia=k(args.tools_dir, KONTENER.narzedzia, "tools-dir"),
                     bin=k(args.bin_dir, KONTENER.bin, "bin-dir"),
                     py=slowo_polecenia(args.py) if args.py else KONTENER.py)
    system = args.system or system_tego_komputera()
    if args.dane:
        dane = sciezka_ukladu(args.dane, system, "dane")
    elif system == system_tego_komputera():
        sys.path.insert(0, str(fl.REPO_ROOT))
        from jarvo import sciezki            # katalogi tej instalacji (JARVO_ROOT, %LOCALAPPDATA%\Jarvo, ~/.jarvo…)
        try:
            dane = sciezka_ukladu(sciezki.uklad().dane, system, "dane")
        except sciezki.BladUkladu as e:
            raise SystemExit(f"--dane: {e}") from e
    else:
        raise SystemExit("--dane jest wymagane przy budowie dla innego systemu niż ten komputer")
    program = dane.rsplit("/", 1)[0] + "/program"
    py = str(args.py or sys.executable)
    py = slowo_polecenia(sciezka_ukladu(py, system, "py") if re.search(r"[/\\]", py) else py)
    dom = ""
    if system == system_tego_komputera() and os.path.expanduser("~") != "~":
        try:                                 # katalog domowy z dziwnym znakiem: bez pisowni „~” w zakazach
            dom = sciezka_ukladu(os.path.expanduser("~"), system, "dom")
        except SystemExit:
            dom = ""
    # Narzędzia npm i Chromium tej instalacji: jawnie z opcji, a przy budowie na tym komputerze ze środowiska procesów
    # Jarva (jarvo/flota.py woła build w nim: NODE_PATH i CHROME_PATH z narzedzia.json; cudze NODE_PATH właściciela
    # srodowisko.py odcina). Bez nich node_modules ma domyślne miejsce w <program>, a Chromium nie ma (wtedy build
    # nie ustawia AGENT_BROWSER_EXECUTABLE_PATH; nakładka agent-browsera i tak bierze CHROME_PATH dla silnika chrome).
    na_tym = system == system_tego_komputera()
    node_modules = (args.node_modules or (os.environ.get("NODE_PATH", "").split(os.pathsep)[0] if na_tym else "")
                    or program + "/node-floty/node_modules")
    chrome = args.chrome or (os.environ.get("CHROME_PATH", "") if na_tym else "")
    return Uklad(nazwa="natywny", system=system, dane=dane,
                 repo=sciezka_ukladu(args.repo_dir or fl.REPO_ROOT, system, "repo-dir"),
                 build=sciezka_ukladu(args.runtime_build_dir or args.out, system, "runtime-build-dir"),
                 narzedzia=sciezka_ukladu(args.tools_dir or program + "/narzedzia-floty", system, "tools-dir"),
                 bin=sciezka_ukladu(args.bin_dir or program + "/bin-floty", system, "bin-dir"), py=py, dom=dom,
                 node_modules=sciezka_ukladu(node_modules, system, "node-modules"),
                 chrome=sciezka_ukladu(chrome, system, "chrome") if chrome.strip() else "")


def sciezki_floty(fleet: fl.Fleet, u: Uklad) -> dict[str, str]:
    """Tokeny ścieżek (wspólny kontrakt etapu E4, docs/NATYWNIE.md (e) p. 2): katalogi danych floty z fleet.yaml
    `shared` (względem <dane>) i katalogi programu z układu. W kontenerze te same napisy co przed układem natywnym."""
    shared = fleet.raw.get("shared") or {}
    out = {"DATA_DIR": u.dane}
    for token, klucz, domyslnie in KATALOGI_DANYCH:
        rel = str(shared.get(klucz) or domyslnie).strip()
        czesci = rel.split("/")
        if rel.startswith(("/", "~")) or re.match(r"[A-Za-z]:", rel) or "\\" in rel or {"", ".", ".."} & set(czesci):
            raise SystemExit(f"fleet.yaml shared.{klucz}: {rel!r} ma być ścieżką względną do katalogu danych "
                             f"(np. {domyslnie})")
        out[token] = f"{u.dane.rstrip('/')}/{rel}"
    out.update({"REPO_DIR": u.repo, "BUILD_DIR": u.build, "TOOLS_DIR": u.narzedzia, "BIN_DIR": u.bin, "PY": u.py})
    return out


def program(u: Uklad, nazwa: str) -> str:
    """Program floty z @@BIN_DIR@@ jako pierwsze słowo polecenia bramy. Kontener: goła ścieżka jak w obrazie.
    Natywnie pełna ścieżka (na Windows z .exe), z „/” i w cudzysłowie: HERMES_LOCAL_STT_COMMAND Hermes dzieli przez
    shlex.split w trybie POSIX (tools/transcription_local.py:261-288), więc „\\” poza cudzysłowem znika, a spacja
    rozcina ścieżkę; komendę TTS uruchamia powłoka (tools/tts_command_provider.py:153, na Windows cmd.exe). Klamry
    podwajamy, bo obie komendy przechodzą przez str.format albo szablon {nazwa} Hermesa."""
    if not u.natywny:
        return f"{u.bin}/{nazwa}"
    sciezka = f"{u.bin}/{nazwa}{'.exe' if u.system == 'windows' else ''}"
    return '"' + sciezka.replace("{", "{{").replace("}", "}}") + '"'


# wiadomości głosowe (stt.provider: local_command): w kontenerze tę wartość ustawia ENV w infra/Dockerfile
STT_ARGUMENTY = "{input_path} --output-dir {output_dir} --language {language}"


def polecenie_stt(u: Uklad) -> str:
    """HERMES_LOCAL_STT_COMMAND bramy. W kontenerze to ENV obrazu (tests/test_build.py pilnuje, że build zna tę samą
    wartość), natywnie build zapisuje go w host/srodowisko.json dla środowiska bramy."""
    return f"{program(u, 'jarvo-stt')} {STT_ARGUMENTY}"


def polecenie_programu(polecenie: str, u: Uklad) -> str:
    """Komenda z programem obrazu (`/opt/jarvo/bin/<nazwa> …`, np. tts.providers.matcha.command z profilu hosta)
    → ten sam program floty w układzie natywnym; argumenty bez zmian."""
    pierwsze, _, reszta = str(polecenie).strip().partition(" ")
    if not u.natywny or not pierwsze.startswith(KONTENER.bin + "/"):
        return polecenie
    return f"{program(u, pierwsze[len(KONTENER.bin) + 1:])} {reszta}".rstrip()


def mapa_kontenera(fleet: fl.Fleet, u: Uklad) -> dict[str, str]:
    """Ścieżki obrazu → ścieżki układu, dla tekstów z repo, które podają ścieżkę kontenera (approvals.smart_policy,
    zakazy z shared/security/deny.yaml)."""
    k, n = sciezki_floty(fleet, KONTENER), sciezki_floty(fleet, u)
    mapa = {k[t]: n[t] for t in ("TOOLS_DIR", "KNOWLEDGE_DIR", "MISSIONS_DIR", "WORKSPACES_DIR", "INBOX_DIR",
                                 "JARVO_DIR", "DATA_DIR", "REPO_DIR", "BUILD_DIR", "BIN_DIR")}
    mapa[KOMPUTER_KONTENERA] = n["JARVO_DIR"] + "/komputer"
    return mapa


def _wzor_kontenera(mapa: dict[str, str]) -> re.Pattern:
    """Najdłuższa ścieżka obrazu najpierw, cała nazwa katalogu: `/opt/data` nie trafia w `/opt/database` ani
    w `/opt/data.bak`, a kropka na końcu zdania („… /opt/data/jarvo/missions.”) nie przeszkadza."""
    return re.compile("(" + "|".join(re.escape(k) for k in sorted(mapa, key=len, reverse=True))
                      + r")(?![\w-]|\.[\w-])")


def przenies_sciezki(tekst: str, mapa: dict[str, str]) -> str:
    return _wzor_kontenera(mapa).sub(lambda m: mapa[m.group(1)], tekst)


# Zakazy natywnie (docs/NATYWNIE.md F15). Hermes porównuje approvals.deny (fnmatch bez wielkości liter) z kilkoma
# wariantami polecenia: surowym, z katalogiem domowym i HERMES_HOME zwiniętymi do ~ i ~/.hermes oraz z „\” zamienionym
# na „/” (tools/approval_floors.py:23-43, tools/approval_detection.py:489-509, 1398-1421). Ścieżka katalogu danych
# może więc przyjść jako C:/…, C:\…, /c/… (Git Bash), ~/… albo $HERMES_HOME/…, często w cudzysłowie (spacja w nazwie
# użytkownika). Zakaz to podpowiedź dla modelu, nie granica.
USUWANIE_WINDOWS = ("Remove-Item", "rmdir /s", "rd /s", "del /s", "erase /s", "rmdir -*r", "rd -*r", "del -*r")


def _glob(tekst: str) -> str:
    """Tekst jako dosłowny fragment wzorca fnmatch."""
    return re.sub(r"([\[*?])", r"[\1]", tekst)


def _pod(sciezka: str, baza: str, system: str) -> bool:
    s, b = (sciezka.lower(), baza.lower()) if system in ("windows", "macos") else (sciezka, baza)
    return s == b or s.startswith(b.rstrip("/") + "/")


def pisownie(sciezka: str, u: Uklad) -> list[str]:
    """Ścieżka układu (z „/”) we wszystkich pisowniach, w których agent poda ją w terminalu."""
    out = [sciezka]
    if u.system == "windows":
        out.append(sciezka.replace("/", "\\"))
        if m := re.match(r"([A-Za-z]):/(.*)", sciezka):
            out.append(f"/{m.group(1).lower()}/{m.group(2)}")
    for baza, zamiennik in ((u.dom, "~"), (u.dane, "$HERMES_HOME"), (u.dane, "${HERMES_HOME}")):
        if baza and _pod(sciezka, baza, u.system):
            out.append(zamiennik + sciezka[len(baza.rstrip("/")):])
    return list(dict.fromkeys(out))


def zakazy(deny: list[str], fleet: fl.Fleet, u: Uklad) -> list[str]:
    """approvals.deny w układzie: w kontenerze bez zmian; natywnie wzorce ze ścieżką obrazu dostają ścieżkę instalacji
    w każdej pisowni (dokładny katalog także z „/”, „\\” i cudzysłowem na końcu), a na Windows dochodzą polecenia
    usuwania Windows dla wszystkiego pod katalogiem danych (sprzątanie katalogów roboczych zostaje dla `rm`)."""
    if not u.natywny:
        return deny
    mapa = mapa_kontenera(fleet, u)
    wzor = _wzor_kontenera(mapa)
    out: list[str] = []
    for d in deny:
        m = wzor.search(d)
        if not m:
            out.append(d)
            continue
        przed, po = d[:m.start()], przenies_sciezki(d[m.end():], mapa)
        if przed.endswith(" "):
            przed += "*"                     # ścieżka natywnie bywa w cudzysłowie
        for s in pisownie(mapa[m.group(1)], u):
            g = przed + _glob(s)
            if po in ("", "/"):
                out += [g, g + "[/\\\"']", g + "[/\\][\"']"]
            else:
                out.append(g + (po.replace("/", "\\") if "\\" in s else po))
    if u.windows:
        for s in pisownie(u.dane, u):
            out += [f"*{polecenie}*{_glob(s)}*" for polecenie in USUWANIE_WINDOWS]
    return list(dict.fromkeys(out))


# Profil, z którym rozmawia `jarvo chat` (jarvo/cli.py, --profil domyślnie jarvo), czyli orkiestrator: natywnie
# approvals.mode manual (decyzja I08; jedno pytanie, bez wstępnej oceny modelu); tryby zgód daje wtyczka jarvo-zgody,
# a tryb pełny tylko --yolo albo /yolo na sesję (nigdy HERMES_YOLO_MODE w środowisku ani `mode: off`).
TRYB_ZGOD_CZATU = "manual"


def _sekcja(cfg: dict, klucz: str) -> dict:
    if not isinstance(cfg.get(klucz), dict):
        cfg[klucz] = {}
    return cfg[klucz]


def ustaw_bezpieczenstwo(cfg: dict) -> None:
    """Natywnie bez kontenera (docs/NATYWNIE.md (d), H03, H15, H23, H24, I13): bez skanera tirith pobieranego bez pinu,
    bez leniwych instalacji Hermesa, bez cudzych logowań (~/.codex, ~/.claude), HOME agenta w <profil>/home (katalog
    zakłada instalacja; bez niego Hermes zostawia prawdziwy HOME) i bez wczytywania ~/.bashrc właściciela."""
    sec = _sekcja(cfg, "security")
    sec["tirith_enabled"] = False
    sec["allow_lazy_installs"] = False
    _sekcja(cfg, "auth")["adopt_external_logins"] = False
    term = _sekcja(cfg, "terminal")
    term["home_mode"] = "profile"
    term["auto_source_bashrc"] = False


def ustaw_glos(cfg: dict, u: Uklad) -> None:
    """Komendy lektora (tts.providers.<nazwa>.command) z programem floty w układzie (V11)."""
    for dostawca in ((cfg.get("tts") or {}).get("providers") or {}).values():
        if isinstance(dostawca, dict) and dostawca.get("command"):
            dostawca["command"] = polecenie_programu(dostawca["command"], u)


# Serwery MCP z node_modules obrazu (`/opt/jarvo/node/node_modules/.bin/<program>`) natywnie (docs/NATYWNIE.md P06):
# `node <node_modules>/<skrypt paczki>`, bez nakładki z .bin. Na Windows to .cmd: Hermes uruchomiłby cmd.exe, a przy
# zatrzymaniu bezczynnego serwera zabiłby tylko jego, zostawiając proces node bez rodzica. `node` bez ścieżki: Hermes
# szuka go w PATH procesu (tools/mcp_tool_config.py, _resolve_stdio_command), gdzie Node z instalacji jest przed
# programami właściciela. Program bez wpisu tutaj zatrzymuje build natywny (nie zostawiamy w konfiguracji ścieżek /opt).
MCP_BIN_KONTENERA = "/opt/jarvo/node/node_modules/.bin/"
MCP_SKRYPTY_NODE = {"inspo-mcp": "inspo-mcp/inspo-mcp.mjs"}     # program z .bin → skrypt `bin` z package.json paczki


def ustaw_mcp(cfg: dict, u: Uklad) -> None:
    """Serwery MCP z Node w układzie natywnym. Certyfikaty: NODE_EXTRA_CA_CERTS z pakietu Debiana w obrazie
    (/etc/ssl/certs/…) zastępuje NODE_USE_SYSTEM_CA=1: Node 26 bierze wtedy magazyn certyfikatów systemu (proxy
    z własnym certyfikatem działa jak w przeglądarce właściciela)."""
    for nazwa, serwer in (cfg.get("mcp_servers") or {}).items():
        polecenie = str((serwer or {}).get("command") or "") if isinstance(serwer, dict) else ""
        if not polecenie.startswith(MCP_BIN_KONTENERA):
            continue
        program = polecenie[len(MCP_BIN_KONTENERA):]
        if program not in MCP_SKRYPTY_NODE:
            raise SystemExit(f"mcp_servers.{nazwa}: {program} z node_modules obrazu nie ma odpowiednika natywnego "
                             "(MCP_SKRYPTY_NODE w scripts/build.py)")
        serwer["command"] = "node"
        serwer["args"] = [f"{u.node_modules.rstrip('/')}/{MCP_SKRYPTY_NODE[program]}", *(serwer.get("args") or [])]
        env = serwer.get("env") if isinstance(serwer.get("env"), dict) else {}
        if str(env.get("NODE_EXTRA_CA_CERTS", "")).startswith("/etc/"):
            del env["NODE_EXTRA_CA_CERTS"]
            env["NODE_USE_SYSTEM_CA"] = "1"
        if env:
            serwer["env"] = env


def ustaw_natywnie(cfg: dict, fleet: fl.Fleet, u: Uklad, czat: bool) -> None:
    """Wartości profilu zależne od systemu w układzie natywnym (docs/NATYWNIE.md C06, U01, V11, F15, P06, (d))."""
    browser = cfg.get("browser")
    if u.windows and isinstance(browser, dict) and browser.get("engine") == "lightpanda":
        # Lightpanda nie ma wydania na Windows (Z01): Chromium z instalacji (chrome-headless-shell, CHROME_PATH), który
        # agent-browser dostaje przez AGENT_BROWSER_EXECUTABLE_PATH (host/srodowisko.json i nakładka agent_browser.py);
        # macOS i Linux bez zmian (Lightpanda z manifestu, zapas Hermesa dla zrzutów: chromium w bin-floty)
        browser["engine"] = "chrome"
    ustaw_mcp(cfg, u)
    web = cfg.get("web")
    if isinstance(web, dict) and str(web.get("search_backend", "")).lower() == "searxng":
        # I14: bez wymuszonej wyszukiwarki; autodetekcja Hermesa (tools/web_tools.py:99-135): klucz API, potem
        # SEARXNG_URL (VPS), potem ddgs, na końcu darmowy pierścień. SearXNG natywnie nie ruszy (Z06)
        del web["search_backend"]
        if not web:
            del cfg["web"]
    ustaw_glos(cfg, u)
    appr = _sekcja(cfg, "approvals")
    if czat:
        appr["mode"] = TRYB_ZGOD_CZATU
    if isinstance(appr.get("smart_policy"), str):
        appr["smart_policy"] = przenies_sciezki(appr["smart_policy"], mapa_kontenera(fleet, u))
    ustaw_bezpieczenstwo(cfg)


# -------------------------------------------------------------------------- tokens

def render_tokens(text: str, tokens: dict[str, str]) -> str:
    for key, value in tokens.items():
        text = text.replace(f"@@{key}@@", value)
    return text


def base_tokens(fleet: fl.Fleet, agent: fl.Agent, runtime_build_dir: str, env: dict[str, str],
                uklad: Uklad | None = None) -> dict[str, str]:
    """Tokeny @@…@@ profilu. Bez `uklad`: kontener z buildem pod `runtime_build_dir` (dawne wywołanie)."""
    shared = fleet.raw.get("shared", {})
    owner = env.get("TELEGRAM_OWNER_ID", "").strip()
    u = uklad or Uklad(build=runtime_build_dir)
    return {
        "PROVIDER": fleet.provider,
        "MODEL": fleet.model_for(agent.model_tier),
        "DELEGATION_MODEL": fleet.model_for(agent.delegation_tier),
        "MODEL_FRONTIER": fleet.model_for("frontier"),
        "MODEL_STRONG": fleet.model_for("strong"),
        "MODEL_FAST": fleet.model_for("fast"),
        "TIMEZONE": shared.get("timezone", "Europe/Warsaw"),
        # ścieżki (wspólny kontrakt E4): DATA_DIR, JARVO_DIR, KNOWLEDGE_DIR, MISSIONS_DIR, WORKSPACES_DIR, INBOX_DIR,
        # REPO_DIR, BUILD_DIR, TOOLS_DIR, BIN_DIR i PY
        **sciezki_floty(fleet, u),
        "AGENT": agent.name,
        "REVIEWER": fleet.reviewer,
        "ORCHESTRATOR": fleet.orchestrator,
        # cel dostarczania rutyn: DM właściciela (trasa DM → jarvo), albo lokalnie gdy brak
        "OWNER_DELIVER": f"telegram:{owner}" if owner else "local",
    }


# ------------------------------------------------------------------------ vendoring

class SourceResolver:
    """Zwraca katalog z drzewem źródła skilli (hermes-tree albo repo git na commicie)."""

    def __init__(self, lock: dict, hermes_src: Path | None, cache: Path, local_src: dict[str, Path]):
        self.sources = lock.get("sources", {})
        self.hermes_src = hermes_src
        self.cache = cache
        self.local_src = local_src
        self._resolved: dict[str, Path] = {}

    def resolve(self, name: str) -> Path:
        if name in self._resolved:
            return self._resolved[name]
        spec = self.sources[name]
        if spec["type"] == "repo-tree":            # skille własne Jarvo wspólne dla kilku agentów (shared/skills)
            path = fl.REPO_ROOT
        elif spec["type"] == "hermes-tree":
            if not self.hermes_src:
                raise SystemExit("Źródło 'hermes' wymaga --hermes-src (np. /opt/hermes w kontenerze).")
            path = self.hermes_src
        elif name in self.local_src:
            path = self.local_src[name]
            head = _git(["rev-parse", "HEAD"], cwd=path).strip()
            if head != spec["rev"]:
                raise SystemExit(f"Lokalne źródło {name} jest na {head}, lock wymaga {spec['rev']}.")
        else:
            path = self.cache / f"{name}@{spec['rev'][:12]}"
            if not (path / ".git").exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                _git(["init", "-q", str(path)])
                _git(["remote", "add", "origin", spec["repo"]], cwd=path)
                _git(["fetch", "-q", "--depth", "1", "origin", spec["rev"]], cwd=path)
                _git(["checkout", "-q", "FETCH_HEAD"], cwd=path)
        self._resolved[name] = path
        return path


def _git(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


def vendor_skills(agent: str, out_skills: Path, lock: dict, resolver: SourceResolver, report: list,
                  straznik: skan_skilli.Straznik | None = None, tokens: dict[str, str] | None = None) -> None:
    """Skille z locka. Wspólne skille Jarva (źródło repo-tree, shared/skills) dostają tokeny @@…@@ w plikach .md jak
    skille własne (wspólny kontrakt ścieżek E4); cudzych plików nie zmieniamy."""
    for entry in lock.get("agents", {}).get(agent, []) or []:
        source = entry["source"]
        spec = lock["sources"][source]
        src_root = resolver.resolve(source)
        src = src_root / entry["path"]
        if not (src / "SKILL.md").exists():
            raise SystemExit(f"[{agent}] brak SKILL.md w {source}:{entry['path']}")
        dest = out_skills / entry["dest"]
        if dest.exists():
            raise SystemExit(f"[{agent}] kolizja: {entry['dest']} już istnieje (skill własny o tej nazwie?)")
        shutil.copytree(src, dest, ignore=_ignore(entry.get("pomin")))
        rev = spec.get("rev") or _hermes_rev(src_root)
        if straznik is not None:        # skan przed dopisaniem naszych plików (licencja, .vendored.json)
            straznik.sprawdz(dest, agent, source, spec["type"], rev, entry["path"])
        if source == "jarvo" and (dest / "scripts" / "iso.py").exists():
            fl.kopiuj_kroje_izometrii(dest / "scripts")     # izometria: krój OFL obok iso.py, bez Google Fonts
        if tokens and spec["type"] == "repo-tree":
            for md in dest.rglob("*.md"):
                tekst = md.read_text(encoding="utf-8")
                if (nowy := render_tokens(tekst, tokens)) != tekst:      # pliki bez tokenów zostają bajt w bajt
                    zapisz(md, nowy)
        # licencja
        if spec.get("license_file") == "per-skill":
            lic = next((p for p in dest.iterdir() if p.name.lower().startswith("license")), None)
            if lic is None or "Apache License" not in lic.read_text(encoding="utf-8", errors="ignore"):
                raise SystemExit(f"[{agent}] {entry['path']}: brak licencji Apache-2.0, nie kopiujemy")
        elif spec.get("license_file"):
            shutil.copy2(src_root / spec["license_file"], dest / "LICENSE-UPSTREAM")
        elif spec.get("notice") and spec["type"] in ("git", "repo-tree"):
            zapisz(dest / "LICENSE-UPSTREAM", spec["notice"] + "\n")
        elif spec["type"] == "hermes-tree":
            hermes_license = src_root / "LICENSE"
            if hermes_license.exists():
                shutil.copy2(hermes_license, dest / "LICENSE-UPSTREAM")
        # Apache-2.0 §4d: plik NOTICE źródła (jeśli jest) jedzie razem ze skillem
        for notice in (src_root / "NOTICE", src_root / "NOTICE.md", src_root / "NOTICE.txt"):
            if notice.is_file():
                shutil.copy2(notice, dest / "NOTICE-UPSTREAM")
                break
        fl.write_json(dest / ".vendored.json", {
            "source": source,
            "repo": spec.get("repo") or ("jarvo (to repo)" if spec["type"] == "repo-tree" else "hermes-agent (image tree)"),
            "rev": rev, "path": entry["path"], "license": spec["license"],
        })
        report.append({"agent": agent, "dest": entry["dest"], "source": source, "rev": rev})


def _ignore(pomin: list[str] | None):
    """COPY_IGNORE + `pomin` wpisu w locku (np. filmy i zrzuty z przykładów upstreamu: zbędne MB w obrazie)."""
    if not pomin:
        return COPY_IGNORE
    extra = shutil.ignore_patterns(*pomin)
    return lambda d, names: set(COPY_IGNORE(d, names)) | set(extra(d, names))


def _hermes_rev(root: Path) -> str:
    stamp = root / "install-stamp.json"
    if stamp.exists():
        try:
            return json.loads(stamp.read_text(encoding="utf-8"))["commit"]
        except Exception:
            pass
    try:
        return _git(["rev-parse", "HEAD"], cwd=root).strip()
    except Exception:
        return "unknown"


def write_category_descriptions(skills_root: Path) -> None:
    for cat_dir in sorted(p for p in skills_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        desc_file = cat_dir / "DESCRIPTION.md"
        if desc_file.exists():
            continue
        desc = CATEGORY_DESCRIPTIONS.get(cat_dir.name)
        if desc:
            zapisz(desc_file, f"---\ndescription: {json.dumps(desc, ensure_ascii=False)}\n---\n")


# ---------------------------------------------------------------- generated (Jarvo)

def render_roster_skill(fleet: fl.Fleet) -> str:
    lines = [
        "---",
        "name: roster",
        'description: "Kto jest we flocie: agenci, zakresy, skille do kart."',
        "version: 1.0.0",
        "author: Jarvo (generowane z fleet.yaml)",
        "license: MIT",
        "metadata:",
        "  jarvo:",
        f"    agent: {fleet.orchestrator}",
        "    generated: true",
        "---",
        "",
        "# Roster floty (generowane, nie edytuj ręcznie)",
        "",
        "Źródło: `fleet.yaml`. Karty przypisuj **wyłącznie** do agentów z tej listy. Dispatcher",
        "nie wykona karty przypisanej do nieistniejącego profilu.",
        "",
        "| Agent | Rola | Zakres | Model | Maks. autonomia |",
        "|---|---|---|---|---|",
    ]
    for a in fleet.active():
        lines.append(f"| `{a.name}` | {a.emoji} {a.title} | {a.description} | {a.model_tier} | {a.autonomy_max} |")
    lines += [
        "",
        f"Recenzent kart: `{fleet.reviewer}` (snajperzy wołają `kanban_request_review(reviewer=\"{fleet.reviewer}\")`).",
        "",
        "## Skille, które warto przypinać do kart (`kanban_create(skills=[...])`)",
        "",
        "Nazwy muszą istnieć w profilu wykonawcy. Poniższe listy są generowane z repo.",
        "",
    ]
    lock = fl.load_lock()
    for a in fleet.active():
        if a.name == fleet.orchestrator:
            continue
        own = sorted(fl.available_skills(a.dir / "skills")[0].keys())
        vendored = sorted(Path(e["dest"]).name for e in lock.get("agents", {}).get(a.name, []) or [])
        lines.append(f"### `{a.name}`")
        lines.append(f"- workflowy własne: {', '.join(f'`{n}`' for n in own) or '—'}")
        if vendored:
            lines.append(f"- skille zewnętrzne: {', '.join(f'`{n}`' for n in vendored)}")
        if a.pin_skills:
            lines.append(f"- przypinaj domyślnie: {', '.join(f'`{n}`' for n in a.pin_skills)}")
        lines.append("")
    return "\n".join(lines) + "\n"


WIEDZA_PLUGIN = "jarvo-wiedza"
KOMPUTER_PLUGIN = "jarvo-komputer"     # narzędzie `komputer` (komputer/plugin) dla agentów z `komputer: true`
ZGODY_PLUGIN = "jarvo-zgody"           # tryby zgód pytaj/projekt/pełny (zgody/plugin), tylko w układzie natywnym


def glos_floty() -> dict | None:
    """Blok `tts` z profiles/_host/config.yaml: głos floty (Matcha przez jarvo-tts) dla profili bez własnego."""
    return fl.load_yaml(fl.REPO_ROOT / "profiles" / "_host" / "config.yaml").get("tts")


def build_wiedza_plugin(out: Path, recenzent: str | None = None) -> Path:
    """Wtyczka skarbca (wiedza/plugin + wiedza.py obok): install-fleet.sh kopiuje ją do <dane>/plugins/ i dowiązuje
    w każdym profilu (dostawcy pamięci są szukani w <HERMES_HOME profilu>/plugins/). `recenzent` (fleet.yaml) trafia
    do flota.json obok: strażnik dopisuje go do oddania karty, gdy agent go pominie."""
    if out.exists():
        remove_tree(out)
    shutil.copytree(fl.REPO_ROOT / "wiedza" / "plugin", out, ignore=COPY_IGNORE)
    shutil.copy2(fl.REPO_ROOT / "wiedza" / "wiedza.py", out / "wiedza.py")
    shutil.copy2(fl.REPO_ROOT / "wiedza" / "kompilacja.py", out / "kompilacja.py")
    if recenzent:
        fl.write_json(out / "flota.json", {"recenzent": recenzent})
    # zakładka „Wiedza” w dashboardzie: manifest + trasy + logika już skopiowane z wiedza/plugin/dashboard; tu pakiet JS i style
    import hqbuild
    dash = out / "dashboard"
    (dash / "dist").mkdir(parents=True, exist_ok=True)
    zapisz(dash / "dist" / "index.js", hqbuild.bundle_js(fl.REPO_ROOT / "wiedza" / "web" / "src",
                                                          "Jarvo Wiedza: zakładka dashboardu Hermesa. Plik generowany przez scripts/build.py z wiedza/web/src/."))
    shutil.copy2(fl.REPO_ROOT / "wiedza" / "web" / "style.css", dash / "dist" / "style.css")
    shutil.copy2(fl.REPO_ROOT / "hq" / "web" / "vendor" / "LICENSE-htm", dash / "dist" / "LICENSE-htm")
    # ochrona zapisu (CSRF): ten sam plik co w jarvo-hq, żeby obie wtyczki miały jedne reguły (tests/test_csrf.py)
    shutil.copy2(fl.REPO_ROOT / "hq" / "plugin" / "ochrona.py", dash / "ochrona.py")
    return out


def punkty_listy(tresc: str) -> list[str]:
    """Punkty listy markdown („- …”) w jednej linii każdy: wiersze wcięte pod punktem (punkt złamany na kilka linii,
    podpunkty) doklejamy do niego, zamiast je gubić."""
    punkty: list[str] = []
    otwarty = False                                     # zwykły akapit zamyka punkt: wcięcie pod nim nie jest dalszym ciągiem
    for ln in tresc.splitlines():
        if ln.startswith("- "):
            punkty.append(ln[2:])
            otwarty = True
        elif otwarty and ln[:1] in (" ", "\t") and ln.strip():
            punkty[-1] += " " + ln.strip()
        elif ln.strip():
            otwarty = False
    return [" ".join(p.split()) for p in punkty if p.strip()]


def ostatnie_zmiany(changelog: Path, n: int = 6, dlugosc: int = 280) -> tuple[str, list[str]]:
    """(nagłówek, punkty) pierwszej niepustej sekcji CHANGELOG-u profilu („Niewydane” albo ostatnia wersja).
    Cały CHANGELOG trafia do skarbca jako kopia (`repo_do_skarbca`); tu tylko kilka najnowszych na hub agenta."""
    if not changelog.is_file():
        return "", []
    for sekcja in changelog.read_text(encoding="utf-8").split("\n## ")[1:]:
        tytul, _, tresc = sekcja.partition("\n")
        punkty = punkty_listy(tresc)
        if punkty:
            return tytul.strip(), [p if len(p) <= dlugosc else p[:dlugosc - 1].rstrip() + "…" for p in punkty[:n]]
    return "", []


SKRYPT_EXT = {".py", ".sh", ".js", ".mjs", ".cjs"}


def skrypty_skilla(katalog: Path) -> list[str]:
    """Własne skrypty skilla (`<skill>/scripts/`, np. wspólnego `konwertuj.py`), bez modułów pomocniczych `_…`."""
    d = katalog / "scripts"
    return sorted(p.name for p in d.glob("*") if p.is_file() and p.suffix in SKRYPT_EXT and not p.name.startswith("_")) \
        if d.is_dir() else []


def opis_skilla(path: Path, skrypty: set[str]) -> dict:
    """Skill jako węzeł grafu wiedzy: opis, wersja, data przeglądu, powiązane skille (frontmatter i nazwy w `…`),
    skrypty floty wymienione w treści i własne skrypty skilla, sekcje i plik w repo."""
    fm, body = fl.read_skill(path)
    meta = fm.get("metadata") or {}
    try:
        plik = path.resolve().relative_to(fl.REPO_ROOT).as_posix()
    except ValueError:
        plik = path.as_posix()
    return {"name": path.parent.name, "description": " ".join(str(fm.get("description", "")).split()), "path": plik,
            "version": str(fm.get("version") or ""), "reviewed": str((meta.get("jarvo") or {}).get("reviewed") or ""),
            "related": [str(s) for s in (meta.get("hermes") or {}).get("related_skills") or []],
            "mentions": sorted(set(re.findall(r"`([a-z][a-z0-9-]{2,40})`", body)) - {path.parent.name}),
            "scripts": sorted({*(s for s in skrypty if re.search(rf"(?<![\w.-]){re.escape(s)}\b", body)),
                               *skrypty_skilla(path.parent)}),
            "sections": [h.strip() for h in re.findall(r"^## (.+)$", body, re.M)][:10],
            "references": sorted(r.relative_to(path.parent / "references").with_suffix("").as_posix()
                                 for r in (path.parent / "references").rglob("*.md"))}


def serwery_mcp(config: Path) -> list[dict]:
    """Serwery MCP profilu z `mcp_servers` w config.yaml: nazwa i narzędzia widoczne dla modelu (`tools.include`; puste = wszystkie)."""
    cfg = fl.load_yaml(config) if config.is_file() else {}
    serwery = (cfg or {}).get("mcp_servers") or {}
    return [{"name": str(n), "tools": [str(t) for t in ((s or {}).get("tools") or {}).get("include") or []],
             **({"trust": str(s["trust"])} if isinstance(s, dict) and s.get("trust") else {})}
            for n, s in sorted(serwery.items())]


def zmienne_srodowiska(agent_dir: Path) -> list[str]:
    """Same NAZWY zmiennych, które profil dostaje z .env (distribution.yaml `env_requires`, config.yaml
    `terminal.env_passthrough`); wartości nigdy nie trafiają do skarbca."""
    dist = fl.load_yaml(agent_dir / "distribution.yaml") if (agent_dir / "distribution.yaml").is_file() else {}
    cfg = fl.load_yaml(agent_dir / "config.yaml") if (agent_dir / "config.yaml").is_file() else {}
    nazwy = [str(e.get("name")) for e in (dist or {}).get("env_requires") or [] if isinstance(e, dict) and e.get("name")]
    nazwy += [str(n) for n in ((cfg or {}).get("terminal") or {}).get("env_passthrough") or []]
    return list(dict.fromkeys(nazwy))


def evale_agenta(name: str) -> list[dict]:
    plik = fl.REPO_ROOT / "evals" / name / "scenarios.yaml"
    dane = fl.load_yaml(plik) if plik.is_file() else {}
    return [{"id": str(s["id"]), "type": str(s.get("type", ""))} for s in (dane or {}).get("scenarios") or [] if s.get("id")]


def narzedzia_agenta(agent_dir: Path) -> list[str]:
    dane = fl.load_yaml(agent_dir / "toolbox.yaml") if (agent_dir / "toolbox.yaml").is_file() else {}
    return [str(x["name"]) for x in (dane or {}).get("tools") or [] if isinstance(x, dict) and x.get("name")]


def zrodla_zewnetrzne() -> list[dict]:
    """vendor/zrodla.yaml dla skarbca: każde repo, z którego bierzemy, i jego status (używane, odłożone…)."""
    dane = fl.load_yaml(fl.REPO_ROOT / "vendor" / "zrodla.yaml") or {}
    return [{"name": str(n), "repo": str(z.get("repo", "")), "status": str(z.get("status", "")),
             "przejrzane": str(z.get("przejrzane", ""))[:7], "notatka": " ".join(str(z.get("notatka", "")).split())}
            for n, z in sorted((dane.get("zrodla") or {}).items())]


def repo_do_skarbca(fleet: fl.Fleet, out: Path, dane: dict) -> int:
    """Kopia plików repo, które opisują flotę, a nie są w docs/: dla każdego agenta SOUL (bez znacznika protokołu),
    README, CHANGELOG, rubryka i materiały (references) jego skilli, w układzie repo (`profiles/<agent>/…`,
    `shared/skills/…`), plus spis źródeł `vendor/zrodla.md`. `wiedza.py zasiej --repo` kładzie ją w
    `zrodla/jarvo-repo/`, a huby i węzły skilli linkują do tych plików."""
    if out.exists():
        shutil.rmtree(out)
    pliki = 0

    def kopiuj(src: Path, rel: str, tekst: str | None = None) -> None:
        nonlocal pliki
        if tekst is None and not src.is_file():
            return
        cel = out / rel
        cel.parent.mkdir(parents=True, exist_ok=True)
        zapisz(cel, tekst if tekst is not None else src.read_text(encoding="utf-8"))
        pliki += 1

    for a in fleet.active():
        baza = f"profiles/{a.name}"
        soul = a.dir / "SOUL.md"
        if soul.is_file():
            kopiuj(soul, f"{baza}/SOUL.md", soul.read_text(encoding="utf-8").replace(fl.PROTOCOL_MARKER + "\n\n", "")
                   .replace(fl.PROTOCOL_MARKER, ""))
        for rel in ("README.md", "CHANGELOG.md", "quality/rubric.md"):
            kopiuj(a.dir / rel, f"{baza}/{rel}")
    for a in dane["agents"]:
        for s in [*a["skills"], *a["shared_skills"]]:
            katalog = (fl.REPO_ROOT / s["path"]).parent
            for r in s.get("references") or []:
                kopiuj(katalog / "references" / f"{r}.md", f"{Path(s['path']).parent.as_posix()}/references/{r}.md")
    wiersze = ["# Źródła zewnętrzne (vendor/zrodla.yaml)", "",
               "Każde repo, z którego Jarvo bierze kod, skille albo wzorce, i te, które obserwujemy. Licencje i co dokładnie",
               "wzięte: `SOURCES.md`. Status: uzywane, do-wdrozenia, czeka (na decyzję właściciela), odlozone.", "",
               "| Źródło | Status | Przejrzane | Notatka |", "|---|---|---|---|"]
    for z in dane["zrodla"]:
        wiersze.append(f"| [{z['name']}]({z['repo']}) | {z['status']} | `{z['przejrzane']}` | {z['notatka'].replace('|', '/')} |")
    kopiuj(Path(), "vendor/zrodla.md", "\n".join(wiersze) + "\n")
    return pliki


def wiedza_fleet(fleet: fl.Fleet, profiles_out: Path) -> dict:
    """fleet.json dla skarbca wiedzy: hub każdego agenta (wiedza/wiedza.py zasiej) dostaje rolę, skille własne i wspólne
    (shared/skills) z opisami, powiązaniami i skryptami (każdy skill to węzeł grafu), nazwy skilli zewnętrznych
    (z dystrybucji po buildzie), skrypty, serwery MCP i ostatnie zmiany z CHANGELOG-u; `skrypty_repo` to skrypty wspólne (scripts/
    i skryptów wspólnych skilli, shared/skills/*/scripts/), żeby lint skarbca odróżnił odwołanie do istniejącego skryptu od nieaktualnego."""
    skrypty_repo = sorted({p.name for p in (fl.REPO_ROOT / "scripts").glob("*") if p.suffix in SKRYPT_EXT}
                          | {n for d in (fl.SHARED_DIR / "skills").glob("*") for n in skrypty_skilla(d)})
    agents = []
    for a in fleet.active():
        wlasne = fl.available_skills(a.dir / "skills")[0]
        skrypty = sorted(p.name for p in (a.dir / "scripts").glob("*")
                         if p.is_file() and not p.name.startswith("_") and not p.name.endswith("_lib.py")) if (a.dir / "scripts").is_dir() else []
        znane = set(skrypty) | set(skrypty_repo)
        skills = [opis_skilla(path, znane) for _name, path in sorted(wlasne.items())]
        # skille zewnętrzne po nazwach katalogów (ich frontmatter bywa niestandardowy: nie parsujemy YAML-a cudzych skilli);
        # wspólne skille floty (shared/skills) to nasze skille: idą jako węzły grafu jak własne
        katalog = profiles_out / a.name / "skills"
        wszystkie = {p.parent.name for p in fl.iter_skill_files(katalog)} if katalog.is_dir() else set()
        obce = sorted(wszystkie - {p.parent.name for p in wlasne.values()})
        wspolne = [n for n in obce if (fl.SHARED_DIR / "skills" / n / "SKILL.md").is_file()]
        sekcja, zmiany = ostatnie_zmiany(a.dir / "CHANGELOG.md")
        agents.append({"name": a.name, "short": a.hq_short or a.title, "handle": a.handle, "title": a.title, "emoji": a.emoji, "kind": a.kind,
                       "description": a.description, "room": a.hq_room, "label": a.hq_label or a.title,
                       "telegram_topic": a.telegram_topic, "autonomy_max": a.autonomy_max, "komputer": a.komputer,
                       "skills": skills,
                       "shared_skills": [opis_skilla(fl.SHARED_DIR / "skills" / n / "SKILL.md", znane) for n in wspolne],
                       "external_skills": [n for n in obce if n not in wspolne], "scripts": skrypty,
                       "mcp": serwery_mcp(a.dir / "config.yaml"), "env": zmienne_srodowiska(a.dir),
                       "tools": narzedzia_agenta(a.dir), "evals": evale_agenta(a.name),
                       "changes_section": sekcja, "changes": zmiany})
    return {"orchestrator": fleet.orchestrator, "agents": agents, "repo_scripts": skrypty_repo, "zrodla": zrodla_zewnetrzne()}


def render_handoff_table(fleet: fl.Fleet, agent: fl.Agent) -> str:
    """Tabela „komu oddać” z fleet.yaml (pole `oddaj_gdy`): każdy aktywny specjalista poza samym agentem.
    Nowy agent we fleet.yaml trafia tu sam; walidator pilnuje, żeby każdy specjalista miał `oddaj_gdy`."""
    rows = ["| Sygnał | Właściwy agent |", "|---|---|"]
    for a in fleet.active():
        if a.name in (agent.name, fleet.orchestrator) or a.kind != "specialist":
            continue
        rows.append(f"| {a.oddaj_gdy or a.description} | `{a.name}` ({a.emoji} {a.title}) |")
    rows.append(f"| kilka etapów, kilku agentów, decyzje po drodze | `{fleet.orchestrator}` (misja) |")
    return "\n".join(rows)


def render_roster_summary(fleet: fl.Fleet) -> str:
    rows = ["| Agent | Rola |", "|---|---|"]
    for a in fleet.active():
        if a.name == fleet.orchestrator:
            continue
        rows.append(f"| `{a.name}` | {a.emoji} {a.title} |")
    return "\n".join(rows)


def copy_rubrics(fleet: fl.Fleet, review_skill_refs: Path) -> None:
    review_skill_refs.mkdir(parents=True, exist_ok=True)
    for a in fleet.active():
        rubric = a.dir / "quality" / "rubric.md"
        if rubric.exists():
            shutil.copy2(rubric, review_skill_refs / f"rubric-{a.name}.md")


def remove_tree(path: Path) -> None:
    """Usuwa stary wynik budowy. Resztki innego użytkownika (np. __pycache__ roota po ręcznym uruchomieniu
    skryptu agenta) nie mogą wywrócić wdrożenia przed instalacją floty: katalog odkładamy na bok
    (wystarczy prawo zapisu w rodzicu), a przy następnej budowie próbujemy go dosprzątać."""
    try:
        shutil.rmtree(path)
        return
    except PermissionError:
        pass
    trash = path.parent / f".{path.name}.old-{dt.datetime.now():%Y%m%d%H%M%S}"
    path.rename(trash)
    print(f"  ! {path} miał pliki innego użytkownika: odłożony do {trash.name} (usuń ręcznie: sudo rm -rf)")
    for old in path.parent.glob(f".{path.name}.old-*"):
        shutil.rmtree(old, ignore_errors=True)


# ---------------------------------------------------------------------------- cron

def build_cron(agent_dir: Path, out_dir: Path, tokens: dict[str, str], hermes_src: Path | None) -> int:
    src = agent_dir / "cron" / "jobs.yaml"
    if not src.exists():
        return 0
    spec = fl.loads_yaml(render_tokens(src.read_text(encoding="utf-8"), tokens)) or {}
    jobs = spec.get("jobs", []) or []
    if not jobs:
        return 0
    if hermes_src is None:
        raise SystemExit("Budowa crona wymaga --hermes-src (API crona Hermesa waliduje harmonogramy).")
    code = _CRON_SNIPPET
    payload = json.dumps(jobs, ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix="jarvo_cron_") as tmp:
        env = dict(os.environ, HERMES_HOME=tmp, JARVO_CRON_JOBS=payload, JARVO_CRON_OUT=str(out_dir / "cron" / "jobs.json"))
        env["PYTHONPATH"] = os.pathsep.join([str(hermes_src), env.get("PYTHONPATH", "")])
        python = os.environ.get("JARVO_HERMES_PYTHON") or sys.executable
        res = subprocess.run([python, "-c", code], env=env, capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
        if res.returncode != 0:
            raise SystemExit(f"Budowa crona dla {agent_dir.name} nie powiodła się:\n{res.stdout}\n{res.stderr}")
    return len(jobs)


_CRON_SNIPPET = r"""
import json, os, shutil
from pathlib import Path
from cron import jobs as cj

specs = json.loads(os.environ["JARVO_CRON_JOBS"])
home = Path(os.environ["HERMES_HOME"])
with cj.use_cron_store(home):
    for s in specs:
        job = cj.create_job(
            prompt=s.get("prompt"), schedule=s["schedule"], name=s.get("name"),
            deliver=s.get("deliver"), skills=s.get("skills"), script=s.get("script"),
            enabled_toolsets=s.get("enabled_toolsets"), no_agent=bool(s.get("no_agent", False)),
            reasoning_effort=s.get("reasoning_effort"), paused=bool(s.get("paused", False)),
            paused_reason=s.get("paused_reason"), model=s.get("model"), provider=s.get("provider"),
        )
        stable = s["id"]
        records = cj.load_jobs()
        for rec in records:
            if rec.get("id") == job["id"]:
                rec["id"] = stable
        cj.save_jobs(records, replace=True)
store = home / "cron" / "jobs.json"
out = Path(os.environ["JARVO_CRON_OUT"])
out.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(store, out)
"""


# ---------------------------------------------------------------------------- host

def build_host(fleet: fl.Fleet, out: Path, env: dict[str, str], uklad: Uklad | None = None) -> list[str]:
    """Config profilu hosta: gateway + multipleks + trasy Telegrama + dispatcher. Natywnie także program lektora
    z instalacji, wtyczka zgód, ustawienia bezpieczeństwa i host/srodowisko.json (HERMES_LOCAL_STT_COMMAND bramy, na
    Windows AGENT_BROWSER_EXECUTABLE_PATH)."""
    u = uklad or KONTENER
    notes: list[str] = []
    template = fl.REPO_ROOT / "profiles" / "_host" / "config.yaml"
    config = fl.load_yaml(template)
    routes = []
    owner = env.get("TELEGRAM_OWNER_ID", "").strip()
    hq = env.get("TELEGRAM_HQ_CHAT_ID", "").strip()
    if owner:
        routes.append({"name": "owner-dm", "platform": "telegram", "chat_id": owner, "profile": fleet.orchestrator})
    else:
        notes.append("Brak TELEGRAM_OWNER_ID: DM z botem nie zostanie skierowany do Jarva.")
    if hq:
        for a in fleet.active():
            topic = a.telegram_topic
            if not topic:
                continue
            if topic == "general":
                routes.append({"name": f"hq-{a.name}", "platform": "telegram", "chat_id": hq, "profile": a.name})
                continue
            thread = env.get(f"TELEGRAM_TOPIC_{topic.upper()}", "").strip()
            if thread:
                routes.append({"name": f"hq-{a.name}", "platform": "telegram", "chat_id": hq,
                               "thread_id": thread, "profile": a.name})
            else:
                notes.append(f"Brak TELEGRAM_TOPIC_{topic.upper()}: wątek {a.name} w Jarvo HQ nie ma trasy.")
    else:
        notes.append("Brak TELEGRAM_HQ_CHAT_ID: grupa „Jarvo HQ” nie ma tras (działa tylko DM).")
    config.setdefault("gateway", {})["profile_routes"] = routes
    config["timezone"] = fleet.raw.get("shared", {}).get("timezone", "Europe/Warsaw")
    # host (gateway, zadania pomocnicze kanbana) używa dostawcy floty i jej najszybszego modelu
    config["model"] = {"provider": fleet.provider, "default": fleet.model_for("fast")}
    if u.natywny:
        ustaw_glos(config, u)
        wtyczki = _sekcja(config, "plugins")
        wtyczki["enabled"] = list(dict.fromkeys([*(wtyczki.get("enabled") or []), ZGODY_PLUGIN]))
        ustaw_bezpieczenstwo(config)
    out.mkdir(parents=True, exist_ok=True)
    header = "# Wygenerowane przez scripts/build.py z profiles/_host/config.yaml + fleet.yaml. Nie edytuj na serwerze.\n"
    if u.natywny:
        header += f"# Układ natywny ({u.system}): katalog danych {u.dane}.\n"
    zapisz(out / "config.yaml", header + fl.dump_yaml(config))
    shutil.copy2(fl.REPO_ROOT / "profiles" / "_host" / "SOUL.md", out / "SOUL.md")
    # zmienne bramy, które w kontenerze daje obraz (ENV w infra/Dockerfile): natywnie stosuje je środowisko procesów
    # Jarva (jarvo/srodowisko.py, docs/NATYWNIE.md S11); bez sekretów
    srodowisko = out / "srodowisko.json"
    if u.natywny:
        zmienne = {"HERMES_LOCAL_STT_COMMAND": polecenie_stt(u)}
        if u.windows and u.chrome:
            # silnik chrome w każdym profilu (Windows): Hermes pokazuje narzędzia browser_* tylko, gdy widzi Chromium
            # (tools/browser_tool_install.py, _chromium_installed), a agent-browser bierze tę ścieżkę zamiast szukać
            # Chrome w systemie. Na macOS i Linuksie nigdy: agent-browser użyłby jej także dla Lightpandy.
            zmienne["AGENT_BROWSER_EXECUTABLE_PATH"] = str(PureWindowsPath(u.chrome))
        fl.write_json(srodowisko, zmienne)
    elif srodowisko.exists():
        srodowisko.unlink()                  # resztka buildu natywnego w tym samym katalogu
    return notes


# ---------------------------------------------------------------------------- main

def build_agent(fleet, agent, out_root, lock, resolver, protocol, runtime_build_dir, env, hermes_src, report,
                straznik=None, uklad: Uklad | None = None):
    """Dystrybucja jednego agenta. Bez `uklad`: kontener z buildem pod `runtime_build_dir` (dawne wywołanie)."""
    u = uklad or Uklad(build=runtime_build_dir)
    src = agent.dir
    dest = out_root / agent.name
    shutil.copytree(src, dest, ignore=COPY_IGNORE)
    tokens = base_tokens(fleet, agent, u.build, env, u)
    # workflowy, którym brakuje usługi (`metadata.jarvo.wymaga`), nie trafiają do profilu: agent nie ma martwych ścieżek
    _, pominiete = fl.available_skills(src / "skills")
    for name in pominiete:
        sciezka = fl.skill_names(dest / "skills").get(name)
        if sciezka:
            remove_tree(sciezka.parent)
    # Wideograf: silnik edytora HQ obok projekt.py (render agenta = ten sam co „Eksportuj” w edytorze)
    if (dest / "scripts" / "projekt.py").exists():
        shutil.copy2(fl.REPO_ROOT / "hq" / "plugin" / "edytor.py", dest / "scripts" / "edytor.py")
        shutil.copy2(fl.REPO_ROOT / "hq" / "web" / "src" / "44-napisy.js", dest / "scripts" / "edytor_napisy.js")
        shutil.copy2(fl.REPO_ROOT / "hq" / "web" / "src" / "48-typografia.js", dest / "scripts" / "edytor_typografia.js")
        shutil.copytree(fl.REPO_ROOT / "hq" / "web" / "fonts" / "kroje", dest / "scripts" / "kroje", dirs_exist_ok=True)
        # biblioteka dźwięków CC0 (ta sama co w menu Audio edytora): projekt.py dzwieki / dodaj-dzwiek, podkłady film.py
        shutil.copytree(fl.REPO_ROOT / "hq" / "web" / "dzwieki", dest / "scripts" / "dzwieki", dirs_exist_ok=True)

    # SOUL.md
    soul_path = dest / "SOUL.md"
    soul = soul_path.read_text(encoding="utf-8")
    if fl.PROTOCOL_MARKER not in soul:
        raise SystemExit(f"[{agent.name}] SOUL.md nie ma znacznika {fl.PROTOCOL_MARKER}")
    # kalibracja pod rodzinę modelu agenta (shared/calibration/, za oh-my-hermes): tuż po protokole floty
    calibration = fl.calibration_section(fleet.model_for(agent.model_tier), agent.name == fleet.orchestrator)
    soul = soul.replace(fl.PROTOCOL_MARKER, f"{fl.protocol_for(protocol, agent.name == fleet.orchestrator).strip()}\n\n{calibration}")
    if agent.name == fleet.orchestrator:
        soul = soul.replace(fl.ROSTER_MARKER, render_roster_summary(fleet))
    if pominiete:
        soul = soul.rstrip() + "\n\n" + fl.missing_section(pominiete, fleet)
    zapisz(soul_path, render_tokens(soul, tokens))

    # profile.yaml
    zapisz(dest / "profile.yaml", fl.dump_yaml({
        "description": agent.description,
        "description_auto": False,
        "display_name": f"{agent.emoji} {agent.title}".strip(),
    }))

    # config.yaml, toolbox.yaml (healthchecki ze ścieżkami) i distribution.yaml: tokeny; plik musi zostać poprawnym
    # YAML (np. @@PY@@ ma własny cudzysłów, gdy ścieżka ma spację, więc nie stoi w podwójnym cudzysłowie YAML)
    for rel in ["config.yaml", "toolbox.yaml", "distribution.yaml"]:
        p = dest / rel
        if p.exists():
            tekst = render_tokens(p.read_text(encoding="utf-8"), tokens)
            try:
                fl.loads_yaml(tekst)
            except Exception as e:  # noqa: BLE001 - każdy błąd parsera YAML
                raise SystemExit(f"[{agent.name}] {rel} po podstawieniu tokenów nie jest poprawnym YAML: {e}") from e
            zapisz(p, tekst)
    # wspólne zakazy floty (shared/security/deny.yaml) → approvals.deny każdego profilu;
    # skarbiec wiedzy (docs/WIEDZA.md): dostawca pamięci jarvo-wiedza u każdego agenta, wtyczka włączona,
    # zadanie pomocnicze jarvo_wiedza (wyciągi z rozmów, kompilacja) na głównym modelu (poziom frontier, jak Jarvo):
    # do skarbca trafia najważniejsza wiedza floty, więc nie oszczędzamy na niej na tanim modelu (decyzja właściciela)
    # układ natywny (docs/NATYWNIE.md S06): zakazy dla katalogu danych w każdej pisowni, wartości per system,
    # wtyczka zgód jarvo-zgody w każdym profilu i approvals.mode manual w profilu czatu (I08)
    deny_src = fl.REPO_ROOT / "shared" / "security" / "deny.yaml"
    if (dest / "config.yaml").exists():
        cfg = fl.load_yaml(dest / "config.yaml")
        if deny_src.exists():
            appr = cfg.setdefault("approvals", {})
            wlasne = list(appr.get("deny") or [])
            appr["deny"] = zakazy(wlasne + [d for d in fl.load_yaml(deny_src).get("deny", []) if d not in wlasne],
                                  fleet, u)
        cfg.setdefault("memory", {})["provider"] = WIEDZA_PLUGIN
        if "tts" not in cfg and (glos := glos_floty()):
            cfg["tts"] = glos
        wtyczki = cfg.setdefault("plugins", {})
        wlaczone = list(wtyczki.get("enabled") or [])
        wtyczki["enabled"] = wlaczone + [w for w in [WIEDZA_PLUGIN] + ([KOMPUTER_PLUGIN] if agent.komputer else [])
                                         + ([ZGODY_PLUGIN] if u.natywny else []) if w not in wlaczone]
        cfg.setdefault("auxiliary", {})["jarvo_wiedza"] = {"model": fleet.model_for("frontier")}
        naglowek = "# Wygenerowane przez scripts/build.py (tokeny, wspólne zakazy floty, skarbiec wiedzy, głos floty)."
        if u.natywny:
            ustaw_natywnie(cfg, fleet, u, czat=agent.name == fleet.orchestrator)
            naglowek += f"\n# Układ natywny ({u.system}): katalog danych {u.dane}."
        zapisz(dest / "config.yaml", naglowek + "\n" + fl.dump_yaml(cfg))
    # model zapasowy zestawu: agent nie milknie, gdy główny model odmówi (np. poza planem)
    if fleet.fallback and (dest / "config.yaml").exists():
        fb = fleet.fallback
        with (dest / "config.yaml").open("a", encoding="utf-8", newline="\n") as f:
            f.write(f'\nfallback_providers:\n  - provider: "{fb["provider"]}"\n    model: "{fb["model"]}"\n')

    # skille własne → tokeny w SKILL.md i references; tabela „komu oddać” z fleet.yaml
    for md in (dest / "skills").rglob("*.md"):
        tekst = md.read_text(encoding="utf-8")
        if fl.ODDAJ_MARKER in tekst:
            tekst = tekst.replace(fl.ODDAJ_MARKER, render_handoff_table(fleet, agent))
        zapisz(md, render_tokens(tekst, tokens))

    # Jarvo: roster + rubryki
    if agent.name == fleet.orchestrator:
        roster = dest / "skills" / "fleet" / "roster" / "SKILL.md"
        roster.parent.mkdir(parents=True, exist_ok=True)
        zapisz(roster, render_roster_skill(fleet))
        copy_rubrics(fleet, dest / "skills" / "fleet" / "sdlc-review" / "references")

    # skille zewnętrzne (wspólne skille Jarva z tokenami jak własne)
    vendor_skills(agent.name, dest / "skills", lock, resolver, report, straznik, tokens)
    if (dest / "skills").exists():
        write_category_descriptions(dest / "skills")

    # cron
    n_jobs = build_cron(src, dest, tokens, hermes_src)

    # sprzątanie plików źródłowych, których nie chcemy w dystrybucji
    for leftover in ["cron/jobs.yaml"]:
        p = dest / leftover
        if p.exists():
            p.unlink()
    return n_jobs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(fl.REPO_ROOT / "build"))
    ap.add_argument("--hermes-src", default=os.environ.get("JARVO_HERMES_SRC"),
                    help="drzewo Hermesa (skille 'hermes' + API crona), w kontenerze: /opt/hermes")
    ap.add_argument("--cache", default=None, help="cache klonów źródeł skilli (domyślnie <out>/.cache)")
    ap.add_argument("--local-src", action="append", default=[],
                    help="nazwa=ścieżka: użyj lokalnego klonu źródła (musi być na commicie z locka)")
    ap.add_argument("--env-file", default=None, help="plik z TELEGRAM_OWNER_ID, TELEGRAM_HQ_CHAT_ID, TELEGRAM_TOPIC_*")
    ap.add_argument("--wybor-modelu", default=None,
                    help="dostawca wybrany w aplikacji (<dane>/jarvo/state/dostawca-modeli.json, hq/plugin/mozg.py)")
    ap.add_argument("--uklad", choices=UKLADY, default="kontener",
                    help="kontener (domyślnie): ścieżki obrazu /opt, bez zmian do etapu E13; natywny: ścieżki instalacji "
                         "natywnej i wartości per system (docs/NATYWNIE.md S06)")
    ap.add_argument("--system", choices=SYSTEMY, default=None,
                    help="system docelowy układu natywnego (domyślnie ten komputer)")
    ap.add_argument("--dane", default=None,
                    help="HERMES_HOME instalacji, @@DATA_DIR@@ (kontener /opt/data; natywnie domyślnie <root>/dane "
                         "z jarvo/sciezki.py)")
    ap.add_argument("--repo-dir", default=None,
                    help="kod Jarva widziany przez flotę, @@REPO_DIR@@ (kontener /opt/jarvo/repo; natywnie to repo)")
    ap.add_argument("--runtime-build-dir", default=None,
                    help="ścieżka, pod którą build będzie widoczny w działającej instalacji, @@BUILD_DIR@@ "
                         "(external_dirs prawej ręki; kontener /opt/jarvo/build, natywnie --out)")
    ap.add_argument("--bin-dir", default=None,
                    help="programy floty, @@BIN_DIR@@ (kontener /opt/jarvo/bin; natywnie <root>/program/bin-floty)")
    ap.add_argument("--tools-dir", default=None,
                    help="instalacje narzędzi floty w locie, @@TOOLS_DIR@@ (kontener /opt/data/jarvo/narzedzia; "
                         "natywnie <root>/program/narzedzia-floty)")
    ap.add_argument("--py", default=None,
                    help="Python skryptów floty w poleceniach skilli, @@PY@@ (kontener python3; natywnie pełna ścieżka, "
                         "domyślnie Python tego buildu)")
    ap.add_argument("--node-modules", default=None,
                    help="natywnie: narzędzia npm floty (infra/node) dla serwerów MCP z Node (domyślnie pierwszy katalog "
                         "NODE_PATH przy budowie na tym komputerze, inaczej <root>/program/node-floty/node_modules)")
    ap.add_argument("--chrome", default=None,
                    help="natywnie: Chromium dla silnika chrome, AGENT_BROWSER_EXECUTABLE_PATH bramy na Windows "
                         "(domyślnie CHROME_PATH przy budowie na tym komputerze)")
    ap.add_argument("--agent", action="append", default=[], help="buduj tylko wskazanych agentów")
    args = ap.parse_args(argv)
    uklad = uklad_z_argumentow(args)

    fleet = fl.load_fleet()
    lock = fl.load_lock()
    out = Path(args.out).resolve()
    cache = Path(args.cache).resolve() if args.cache else out / ".cache"
    hermes_src = Path(args.hermes_src).resolve() if args.hermes_src else None
    local_src = {}
    for item in args.local_src:
        name, _, path = item.partition("=")
        local_src[name] = Path(path).resolve()
    env = read_env_file(Path(args.env_file) if args.env_file else None)
    provider_env = (env.get("JARVO_MODEL_PROVIDER") or "").strip()
    wybor = None
    if args.wybor_modelu and Path(args.wybor_modelu).is_file():
        try:
            wybor = json.loads(Path(args.wybor_modelu).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print(f"! wybór modelu z aplikacji nieczytelny ({args.wybor_modelu}): pomijam")
    z_aplikacji = fleet.apply_app_choice(env, wybor)
    if z_aplikacji:
        print(f"Dostawca z aplikacji: {env['JARVO_MODEL_PROVIDER']}")
    fleet.apply_model_overrides(env)
    print(f"Modele: {fleet.provider} · " + ", ".join(f"{t}={m}" for t, m in fleet.tiers.items()))
    if uklad.natywny:
        print(f"Układ natywny ({uklad.system}): dane {uklad.dane}, program {uklad.bin.rsplit('/', 1)[0]}, "
              f"Python skryptów {uklad.py}")
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")

    profiles_out = out / "profiles"
    if profiles_out.exists():
        remove_tree(profiles_out)
    profiles_out.mkdir(parents=True)
    resolver = SourceResolver(lock, hermes_src, cache, local_src)

    report: list[dict] = []
    summary = []
    straznik = skan_skilli.Straznik(hermes_src, cache / "skan")
    for agent in fleet.active():
        if args.agent and agent.name not in args.agent:
            continue
        n_jobs = build_agent(fleet, agent, profiles_out, lock, resolver, protocol,
                             uklad.build, env, hermes_src, report, straznik, uklad)
        n_skills = len(list(fl.iter_skill_files(profiles_out / agent.name / "skills")))
        summary.append({"agent": agent.name, "skills": n_skills, "cron_jobs": n_jobs})
        print(f"✓ {agent.name}: {n_skills} skilli, {n_jobs} rutyn cron")

    blad = straznik.blad()
    if blad:
        raise SystemExit(blad)
    skan = straznik.raport()
    print(f"✓ skan skilli: {skan['skilli']} skilli, {skan['ustalen']} ustaleń ({skan['wyjatkow_uzytych']} znanych "
          f"wyjątków, {skan['ostrzezen']} ostrzeżeń)" + ("" if skan["hermes_guard"] else ", bez skanera Hermesa"))
    for w in straznik.nieuzyte():
        print(f"! wyjątek skanu niczego nie przykrył (usuń albo popraw rev): {w}")

    import hqbuild  # Jarvo HQ: plugin dashboardu (pokoje agentów, czat, decyzje)
    hq_dir = hqbuild.build_plugin(out / "plugins" / "jarvo-hq", fleet)
    print(f"✓ Jarvo HQ: {hq_dir.relative_to(out).as_posix()}")

    # skarbiec wiedzy (docs/WIEDZA.md): huby agentów zasiewa install-fleet.sh z tego pliku (wiedza/wiedza.py zasiej)
    dane_wiedzy = wiedza_fleet(fleet, profiles_out)
    fl.write_json(out / "wiedza" / "fleet.json", dane_wiedzy)
    n_repo = repo_do_skarbca(fleet, out / "wiedza" / "repo", dane_wiedzy)
    build_wiedza_plugin(out / "plugins" / WIEDZA_PLUGIN, fleet.reviewer)
    print(f"✓ skarbiec wiedzy: wiedza/fleet.json, wiedza/repo ({n_repo} plików), plugins/{WIEDZA_PLUGIN}")
    # Komputer Jarva (docs/KOMPUTER.md §7): wtyczka z narzędziem `komputer`; install-fleet.sh dowiązuje ją tam, gdzie włączona
    kp = out / "plugins" / KOMPUTER_PLUGIN
    if kp.exists():
        remove_tree(kp)
    shutil.copytree(fl.REPO_ROOT / "komputer" / "plugin", kp, ignore=COPY_IGNORE)
    print(f"✓ plugins/{KOMPUTER_PLUGIN}: agenci z Komputerem: {', '.join(a.name for a in fleet.active() if a.komputer) or 'brak'}")
    # tryby zgód (zgody/README.md, docs/NATYWNIE.md (d)): tylko natywnie; w kontenerze zgody jak dziś (approvals.mode)
    zp = out / "plugins" / ZGODY_PLUGIN
    if zp.exists():
        remove_tree(zp)
    wtyczki = ["jarvo-hq", WIEDZA_PLUGIN, KOMPUTER_PLUGIN]
    if uklad.natywny:
        shutil.copytree(fl.REPO_ROOT / "zgody" / "plugin", zp, ignore=COPY_IGNORE)
        wtyczki.append(ZGODY_PLUGIN)
        print(f"✓ plugins/{ZGODY_PLUGIN}: tryby zgód w każdym profilu i w hoście, profil czatu {fleet.orchestrator} "
              f"z approvals.mode {TRYB_ZGOD_CZATU}")

    notes = build_host(fleet, out / "host", env, uklad)
    for note in notes:
        print(f"! {note}")

    try:
        repo_rev = _git(["rev-parse", "HEAD"], cwd=fl.REPO_ROOT).strip()
    except Exception:
        repo_rev = "unknown"
    manifest = {
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repo_rev": repo_rev,
        "agents": summary,
        # JARVO_MODEL_PROVIDER z jarvo.env przy tym buildzie: aplikacja zapisuje go jako `nad` przy wyborze dostawcy
        "modele": {"env": provider_env, "dostawca": fleet.provider, "z_aplikacji": z_aplikacji},
        "plugins": wtyczki,
        "vendored": report,
        "skan_skilli": skan,
        "notes": notes,
    }
    if uklad.natywny:
        # dla instalacji i doctor: dla jakiego katalogu danych i systemu powstał ten build (ścieżki tokenów)
        manifest["uklad"] = {"nazwa": uklad.nazwa, "system": uklad.system, "sciezki": sciezki_floty(fleet, uklad),
                             "node_modules": uklad.node_modules, "chrome": uklad.chrome}
    fl.write_json(out / "BUILD.json", manifest)
    print(f"Build gotowy: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
