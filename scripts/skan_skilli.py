#!/usr/bin/env python3
"""Skan skilli zewnętrznych, zanim trafią do profili floty (wywołuje go scripts/build.py).

Trzy warstwy:
  1. skaner Hermesa `tools/skills_guard.py` z obrazu (gdy jest --hermes-src): wstrzyknięcia, eksfiltracja,
     trwałe zmiany konfiguracji, binaria, symlinki,
  2. kontrole strukturalne za getsentry/skills `skill-scanner` (Apache-2.0): hooki w nagłówku, `!`polecenie``,
     pliki testów, skrypty cyklu życia npm, tekst w metadanych PNG, nagłówek YAML,
  3. wzorce za affaan-m/ECC `build-pi-core.js` (MIT): pobierz-i-uruchom (curl|sh, npx -y, npx pkg@wersja),
     sekrety, ukryte znaki Unicode, a także wzorce wstrzyknięć i niebezpiecznego kodu z getsentry.

Ustalenie `critical`/`high` blokuje build, chyba że jest na liście wyjątków `vendor/skan-wyjatki.yaml`.
Wyjątek jest przypięty do źródła i commitu: po zmianie `rev` w locku ustalenie wraca jako błąd i trzeba
je przejrzeć na nowo. `medium`/`low` to ostrzeżenia w raporcie.

Ręcznie (np. przed dodaniem nowego źródła do locka):
  python3 scripts/skan_skilli.py <katalog skilla albo katalog z wieloma skillami> [--hermes-src /opt/hermes] [--json]
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import re
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

WYJATKI_FILE = fl.REPO_ROOT / "vendor" / "skan-wyjatki.yaml"
WAGI = {"low": 0, "medium": 1, "high": 2, "critical": 3}
BLOKUJE = 2                                     # od `high` w górę
TEKSTOWE = {".md", ".txt", ".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".yaml",
            ".yml", ".toml", ".html", ".htm", ".css", ".svg", ".xml", ".rb", ".pl", ".ps1", ".bat", ".cmd", ""}
KOD = {".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".rb", ".pl", ".ps1"}
MAX_PLIK = 2 * 1024 * 1024


@dataclass
class Ustalenie:
    regula: str
    waga: str
    plik: str
    linia: int
    opis: str
    dowod: str = ""


# ------------------------------------------------------------------ wzorce tekstu (każdy plik tekstowy)

WSTRZYKNIECIA = [   # getsentry skill-scanner (Apache-2.0)
    (r"ignore\s+(all\s+)?previous\s+instructions", "critical", "nadpisanie instrukcji: ignore previous instructions"),
    (r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|guidelines)", "critical", "nadpisanie instrukcji: disregard"),
    (r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions|rules|training)", "critical", "nadpisanie instrukcji: forget"),
    (r"act\s+as\s+(a|an)\s+unrestricted", "critical", "jailbreak: tryb bez ograniczeń"),
    (r"enter\s+(developer|debug|admin|god)\s+mode", "critical", "jailbreak: tryb dewelopera/boga"),
    (r"\bDAN\s+(mode|prompt|jailbreak)", "critical", "jailbreak: DAN"),
    (r"bypass\s+(safety|security|content\s+filter|restrictions?)", "critical", "jailbreak: obejście zabezpieczeń"),
    (r"override\s+(system|safety|security)\s+(prompt|message|instruction)", "critical", "nadpisanie promptu systemowego"),
    (r"new\s+system\s+(prompt|instruction|message)\s*:", "critical", "wstrzyknięcie nowego promptu systemowego"),
    (r"\bsystem\s*:\s*you\s+are\b", "high", "znacznik wstrzykniętego promptu systemowego"),
    (r"from\s+now\s+on,?\s+(you\s+will\s+)?(ignore|forget|disregard)", "high", "nadpisanie instrukcji od teraz"),
    (r"pretend\s+(that\s+)?you\s+(have\s+no|don't\s+have|are\s+not\s+bound)", "high", "jailbreak: udawanie braku zasad"),
    (r"(output|reveal|print)\s+(your|the)\s+(system|initial|original)\s+(prompt|instructions)", "high", "wyciąganie promptu systemowego"),
]
SEKRETY = [         # getsentry + ECC
    (r"AKIA[0-9A-Z]{16}", "klucz AWS"),
    (r"ghp_[0-9A-Za-z]{36}", "token GitHub (PAT)"),
    (r"gh[sor]_[0-9A-Za-z]{36}", "token GitHub"),
    (r"github_pat_[0-9A-Za-z_]{60,}", "token GitHub (fine-grained)"),
    (r"sk-ant-api\d\d-[0-9A-Za-z\-_]{80,}", "klucz Anthropic"),
    (r"sk-(proj-)?[0-9A-Za-z]{20,}T3BlbkFJ[0-9A-Za-z]{20,}", "klucz OpenAI"),
    (r"xox[baprs]-[0-9A-Za-z-]{10,}", "token Slack"),
    (r"AIza[0-9A-Za-z_-]{35}", "klucz Google API"),
    (r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", "klucz prywatny"),
]
POBIERZ_I_URUCHOM = [   # ECC build-pi-core.js (MIT)
    (r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b", "pobierz i uruchom (curl|sh)"),
    (r"\bnpx\s+(?:-y|--yes)\b", "npx -y (pobiera i uruchamia bez pytania)"),
    (r"\bnpx\s+(?:--\S+\s+)*[A-Za-z@][^\s]*@\d", "npx pakiet@wersja (pobiera i uruchamia)"),
    (r"\bpipx\s+run\b", "pipx run (pobiera i uruchamia)"),
]
UKRYTE = [
    (re.compile(r"[​‌‍⁠]"), "high", "znaki zerowej szerokości (ukryty tekst)"),
    (re.compile(r"[‪-‮⁦-⁩]"), "high", "znaki sterujące kierunkiem tekstu (bidi)"),
    (re.compile(r"[\U000e0001-\U000e007f]"), "critical", "znaki-tagi Unicode (niewidzialne instrukcje)"),
]
# ------------------------------------------------------------------ wzorce kodu (skrypty)
KOD_WZORCE = [      # getsentry skill-scanner (Apache-2.0), z poprawką na JS `.exec(` (RegExp)
    (r"(?<![.\w$])eval\s*\(", "eval", "high", "eval() na danych"),
    (r"(?<![.\w$])exec\s*\(", "exec", "high", "exec() na danych"),
    (r"os\.(system|popen)\s*\(", "polecenie-powloki", "medium", "os.system/os.popen (powłoka)"),
    (r"subprocess\.[a-z_]+\([^\n]*shell\s*=\s*True", "polecenie-powloki", "medium", "subprocess z shell=True"),
    (r"socket\.(connect|create_connection)\s*\(", "gniazdo", "high", "surowe połączenie sieciowe"),
    (r"\b(nc|ncat|netcat)\b\s+-[a-z]*e", "gniazdo", "critical", "netcat z -e (reverse shell)"),
    (r"(open|write_text|Path)\s*\([^\n]*(\.ssh/|\.aws/|\.gnupg/|\.netrc|\.pgpass)", "wrazliwe-sciezki", "high", "odczyt danych logowania"),
    (r"(open|write_text|Path)\s*\([^\n]*(\.bashrc|\.zshrc|\.profile|\.git/hooks|\.husky/)", "konfiguracja-agenta", "critical", "zapis w konfiguracji powłoki/gita"),
    (r"(open|write_text|Path)\s*\([^\n]*(settings\.json|CLAUDE\.md|MEMORY\.md|SOUL\.md|\.mcp\.json|\.hermes/)", "konfiguracja-agenta", "critical", "zapis w konfiguracji agenta"),
]
PNG_ZWYKLE = {"software", "creation time", "date:create", "date:modify", "date:timestamp", "xml:com.adobe.xmp",
              "author", "title", "copyright", "exif", "raw profile type exif", "raw profile type xmp", "comment",
              "description"}
PLIKI_TESTOW = ("conftest.py", "test_*.py", "*_test.py", "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts")


def _linie(tekst: str):
    for n, linia in enumerate(tekst.splitlines(), 1):
        yield n, linia


def _naglowek(tekst: str) -> tuple[str | None, str]:
    m = re.match(r"^﻿?---\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", tekst, re.S)
    return (m.group(1), tekst[m.end():]) if m else (None, tekst)


def skanuj_tekst(tekst: str, rel: str) -> list[Ustalenie]:
    out: list[Ustalenie] = []
    ext = Path(rel).suffix.lower()
    for n, linia in _linie(tekst):
        for wz, waga, opis in WSTRZYKNIECIA:
            if re.search(wz, linia, re.I):
                out.append(Ustalenie("wstrzykniecie", waga, rel, n, opis, linia.strip()[:160]))
        for wz, opis in SEKRETY:
            if re.search(wz, linia):
                out.append(Ustalenie("sekret", "critical", rel, n, opis, re.sub(r"[0-9A-Za-z]{8,}", "…", linia.strip())[:120]))
        for wz, opis in POBIERZ_I_URUCHOM:
            if re.search(wz, linia):
                out.append(Ustalenie("pobierz-i-uruchom", "high", rel, n, opis, linia.strip()[:160]))
        for wz, waga, opis in UKRYTE:
            if wz.search(linia.lstrip("﻿")):
                out.append(Ustalenie("ukryte-znaki", waga, rel, n, opis, repr(linia.strip()[:80])))
        if ext in KOD and not linia.lstrip().startswith(("#", "//", "*", "/*")):
            for wz, regula, waga, opis in KOD_WZORCE:
                if re.search(wz, linia):
                    out.append(Ustalenie(regula, waga, rel, n, opis, linia.strip()[:160]))
    return out


def _png_teksty(dane: bytes) -> list[tuple[str, str]]:
    if dane[:8] != b"\x89PNG\r\n\x1a\n":
        return []
    out, off = [], 8
    while off + 8 <= len(dane):
        dl = struct.unpack(">I", dane[off:off + 4])[0]
        typ, chunk = dane[off + 4:off + 8], dane[off + 8:off + 8 + dl]
        if typ == b"tEXt" and b"\0" in chunk:
            k, v = chunk.split(b"\0", 1)
            out.append((k.decode("latin-1", "ignore"), v.decode("latin-1", "ignore")))
        elif typ == b"iTXt":
            czesci = chunk.split(b"\0", 4)
            if len(czesci) == 5:
                out.append((czesci[0].decode("latin-1", "ignore"), czesci[4].decode("utf-8", "ignore")))
        off += 12 + dl
    return out


def skanuj_strukture(katalog: Path) -> list[Ustalenie]:
    """Kontrole strukturalne za getsentry skill-scanner (Apache-2.0)."""
    out: list[Ustalenie] = []
    root = katalog.resolve()
    skill_md = katalog / "SKILL.md"
    tekst = skill_md.read_text(encoding="utf-8", errors="replace") if skill_md.is_file() else ""
    yaml_txt, body = _naglowek(tekst)
    if yaml_txt is None:
        out.append(Ustalenie("naglowek-yaml", "medium", "SKILL.md", 1, "brak nagłówka YAML"))
    else:
        try:
            fm = fl.loads_yaml(yaml_txt) or {}
        except Exception as e:  # noqa: BLE001
            fm = {}
            out.append(Ustalenie("naglowek-yaml", "medium", "SKILL.md", 1,
                                 "nagłówek YAML nie parsuje się ściśle (Hermes czyta go łagodniej)", str(e).splitlines()[0][:120]))
        if isinstance(fm, dict):
            for pole in ("name", "description"):
                if yaml_txt is not None and fm and not fm.get(pole):
                    out.append(Ustalenie("naglowek-yaml", "medium", "SKILL.md", 1, f"brak pola {pole}"))
            if "hooks" in fm:
                out.append(Ustalenie("hooki-w-naglowku", "critical", "SKILL.md", 1,
                                     "hooki w nagłówku uruchamiają polecenia bez udziału modelu", str(fm["hooks"])[:120]))
    for n, linia in _linie(body):
        for m in re.finditer(r"!`([^`]+)`", linia):
            out.append(Ustalenie("polecenie-przy-ladowaniu", "high", "SKILL.md", n,
                                 "składnia !`polecenie` wykonuje się przy ładowaniu skilla", m.group(0)[:120]))
    for p in sorted(katalog.rglob("*")):
        rel = str(p.relative_to(katalog))
        if p.is_symlink():
            cel = p.resolve()
            poza = not cel.is_relative_to(root)
            out.append(Ustalenie("symlink", "critical" if poza else "medium", rel, 0,
                                 "symlink poza katalog skilla" if poza else "symlink wewnątrz skilla", str(cel)[:120]))
            continue
        if not p.is_file():
            continue
        if any(fnmatch.fnmatch(p.name, w) for w in PLIKI_TESTOW):
            out.append(Ustalenie("plik-testow", "medium", rel, 0,
                                 "plik testów uruchamia się przy pytest/npm test; w katalogu skilli ich nie uruchamiamy"))
        if p.name == "package.json":
            try:
                skrypty = (json.loads(p.read_text(encoding="utf-8", errors="replace")).get("scripts") or {})
            except (ValueError, AttributeError):
                skrypty = {}
            for hook in ("preinstall", "install", "postinstall", "prepare"):
                if hook in skrypty:
                    out.append(Ustalenie("npm-cykl-zycia", "critical" if hook != "prepare" else "medium", rel, 0,
                                         f"package.json: skrypt {hook} uruchamia się przy npm install", str(skrypty[hook])[:120]))
        if p.suffix.lower() == ".png" and p.stat().st_size < MAX_PLIK * 4:
            for k, v in _png_teksty(p.read_bytes()):
                if k.lower() not in PNG_ZWYKLE and v.strip():
                    out.append(Ustalenie("png-metadane", "high", rel, 0,
                                         f"PNG ma tekst w metadanych ({k}); model multimodalny może go przeczytać", v.strip()[:120]))
    return out


def skanuj_hermesem(katalog: Path, hermes_src: Path | None) -> list[Ustalenie]:
    """Skaner Hermesa (`tools/skills_guard.py`, tylko biblioteka standardowa): wczytany wprost z pliku."""
    if not hermes_src:
        return []
    plik = Path(hermes_src) / "tools" / "skills_guard.py"
    if not plik.is_file():
        return []
    mod = sys.modules.get("_jarvo_skills_guard")
    if mod is None:
        spec = importlib.util.spec_from_file_location("_jarvo_skills_guard", plik)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_jarvo_skills_guard"] = mod
        spec.loader.exec_module(mod)
    wynik = mod.scan_skill(katalog, source="community")
    return [Ustalenie(f"hermes:{f.pattern_id}", f.severity, f.file, f.line, f.description, (f.match or "")[:160])
            for f in wynik.findings]


def skanuj(katalog: Path, hermes_src: Path | None = None) -> list[Ustalenie]:
    katalog = Path(katalog)
    out = skanuj_strukture(katalog)
    for p in sorted(katalog.rglob("*")):
        if p.is_symlink() or not p.is_file() or p.suffix.lower() not in TEKSTOWE or p.stat().st_size > MAX_PLIK:
            continue
        try:
            tekst = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        out.extend(skanuj_tekst(tekst, str(p.relative_to(katalog))))
    out.extend(skanuj_hermesem(katalog, hermes_src))
    return out


# ------------------------------------------------------------------ wyjątki (znane fałszywe alarmy)

def wczytaj_wyjatki(path: Path = WYJATKI_FILE) -> list[dict]:
    if not Path(path).exists():
        return []
    return (fl.load_yaml(path) or {}).get("wyjatki") or []


def _pasuje(w: dict, zrodlo: str, rev: str, sciezka: str, u: Ustalenie) -> bool:
    if w.get("zrodlo") != zrodlo or w.get("skill") != sciezka:
        return False
    wrev = str(w.get("rev") or "")
    if wrev != "*" and not (wrev and rev.startswith(wrev)):
        return False
    reguly = w.get("regula") or []
    reguly = [reguly] if isinstance(reguly, str) else reguly
    return any(fnmatch.fnmatch(u.regula, r) for r in reguly) and fnmatch.fnmatch(u.plik, str(w.get("plik") or "*"))


def ocen(ustalenia: list[Ustalenie], zrodlo: str, rev: str, sciezka: str, wyjatki: list[dict]):
    """→ (blokujące, ostrzeżenia, indeksy użytych wyjątków)."""
    blok, ostrz, uzyte = [], [], set()
    for u in ustalenia:
        trafienie = next((i for i, w in enumerate(wyjatki) if _pasuje(w, zrodlo, rev, sciezka, u)), None)
        if trafienie is not None:
            uzyte.add(trafienie)
        elif WAGI.get(u.waga, 1) >= BLOKUJE:
            blok.append(u)
        else:
            ostrz.append(u)
    return blok, ostrz, uzyte


SKANER_WERSJA = "jarvo-skan-1"
ZAUFANE_TYPY = {"hermes-tree"}   # skille z obrazu Hermesa: Hermes sam instaluje je jako „builtin” (raport bez blokady)


def _odcisk(katalog: Path, hermes_src: Path | None) -> str:
    h = hashlib.sha256(SKANER_WERSJA.encode())
    guard = Path(hermes_src) / "tools" / "skills_guard.py" if hermes_src else None
    if guard and guard.is_file():
        h.update(guard.read_bytes())
    h.update(Path(__file__).read_bytes())
    for p in sorted(katalog.rglob("*")):
        h.update(str(p.relative_to(katalog)).encode())
        if p.is_symlink():
            h.update(str(p.readlink()).encode())
        elif p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


class Straznik:
    """Skan każdego skilla zewnętrznego w buildzie: pamięć po zawartości, wyjątki, raport."""

    def __init__(self, hermes_src: Path | None, cache_dir: Path | None, wyjatki: list[dict] | None = None):
        self.hermes_src = Path(hermes_src) if hermes_src else None
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.wyjatki = wczytaj_wyjatki() if wyjatki is None else wyjatki
        self.blokujace: list[tuple[str, str, str, str, Ustalenie]] = []
        self.ostrzezenia = 0
        self.uzyte: set[int] = set()
        self.zeskanowane: dict[tuple[str, str], str] = {}     # (źródło, ścieżka) → rev
        self._pamiec: dict[tuple[str, str], list[Ustalenie]] = {}

    def _skanuj(self, katalog: Path) -> list[Ustalenie]:
        if not self.cache_dir:
            return skanuj(katalog, self.hermes_src)
        plik = self.cache_dir / f"{_odcisk(katalog, self.hermes_src)}.json"
        if plik.is_file():
            return [Ustalenie(**d) for d in json.loads(plik.read_text(encoding="utf-8"))]
        wynik = skanuj(katalog, self.hermes_src)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        plik.write_text(json.dumps([asdict(u) for u in wynik], ensure_ascii=False), encoding="utf-8")
        return wynik

    def sprawdz(self, katalog: Path, agent: str, zrodlo: str, typ: str, rev: str, sciezka: str) -> None:
        klucz = (zrodlo, sciezka)
        if klucz in self._pamiec:
            return
        ustalenia = self._skanuj(katalog)
        self._pamiec[klucz] = ustalenia
        self.zeskanowane[klucz] = rev
        blok, ostrz, uzyte = ocen(ustalenia, zrodlo, rev, sciezka, self.wyjatki)
        self.uzyte |= uzyte
        if typ in ZAUFANE_TYPY:
            ostrz, blok = ostrz + blok, []
        self.ostrzezenia += len(ostrz)
        self.blokujace += [(agent, zrodlo, sciezka, rev, u) for u in blok]

    def nieuzyte(self) -> list[str]:
        """Wyjątki dla zeskanowanych skilli, które niczego nie przykryły (stary rev albo ustalenie zniknęło)."""
        out = []
        for i, w in enumerate(self.wyjatki):
            rev = self.zeskanowane.get((w.get("zrodlo"), w.get("skill")))
            if rev is not None and i not in self.uzyte:
                out.append(f"{w.get('zrodlo')}:{w.get('skill')} {w.get('regula')} ({w.get('plik', '*')}, rev {w.get('rev')}, "
                           f"w locku {rev[:7]})")
        return out

    def raport(self) -> dict:
        return {"skaner": SKANER_WERSJA, "hermes_guard": bool(self.hermes_src), "skilli": len(self._pamiec),
                "ustalen": sum(map(len, self._pamiec.values())), "ostrzezen": self.ostrzezenia,
                "wyjatkow_uzytych": len(self.uzyte), "blokujacych": len(self.blokujace)}

    def blad(self) -> str | None:
        if not self.blokujace:
            return None
        linie = [f"Skan skilli: {len(self.blokujace)} ustaleń high/critical bez wyjątku. Przejrzyj każde; znany fałszywy "
                 f"alarm dopisz do vendor/skan-wyjatki.yaml (z powodem), prawdziwy problem = nie bierzemy skilla."]
        for agent, zrodlo, sciezka, rev, u in self.blokujace:
            linie.append(f"  {agent} · {zrodlo}:{sciezka}@{rev[:7]} · {opisz(u)}")
        return "\n".join(linie)


def opisz(u: Ustalenie) -> str:
    gdzie = f"{u.plik}:{u.linia}" if u.linia else u.plik
    return f"[{u.waga}] {u.regula} · {gdzie} · {u.opis}" + (f" · {u.dowod}" if u.dowod else "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog", help="katalog skilla (z SKILL.md) albo katalog z wieloma skillami")
    ap.add_argument("--hermes-src", default=None, help="drzewo Hermesa (skaner skills_guard), np. /opt/hermes")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.katalog)
    skille = [root] if (root / "SKILL.md").is_file() else sorted(p.parent for p in root.rglob("SKILL.md"))
    wyniki = {str(s.relative_to(root)) if s != root else s.name: skanuj(s, Path(a.hermes_src) if a.hermes_src else None)
              for s in skille}
    if a.json:
        print(json.dumps({k: [asdict(u) for u in v] for k, v in wyniki.items()}, ensure_ascii=False, indent=1))
    else:
        for k, v in wyniki.items():
            if v:
                print(f"== {k}")
                for u in sorted(v, key=lambda u: -WAGI.get(u.waga, 1)):
                    print("  " + opisz(u))
        n = sum(1 for v in wyniki.values() for u in v if WAGI.get(u.waga, 1) >= BLOKUJE)
        print(f"Skilli: {len(skille)}, ustaleń: {sum(map(len, wyniki.values()))}, w tym high/critical: {n}")
    return 1 if any(WAGI.get(u.waga, 1) >= BLOKUJE for v in wyniki.values() for u in v) else 0


if __name__ == "__main__":
    raise SystemExit(main())
