#!/usr/bin/env python3
"""Rejestr źródeł śledztwa: numery cytowań [n], ocena wiarygodności, cytaty-dowody i sprawdzenie raportu.

Rejestr nadaje numer w chwili pobrania strony i nigdy go nie zmienia, więc [3] w raporcie zawsze wskazuje
tę samą stronę. Agent wpisuje w tekst tylko numery, które dostał od rejestru; listę „Źródła” generuje
`render`, a `verify` sprawdza raport przed oddaniem.

    python3 sources.py reset                                 # czysty rejestr na nowe zlecenie
    python3 sources.py add <url> [<url>…] [--tier A|B|C|D] [--type pierwotne|wtorne|dane|opinia] \
        [--date RRRR-MM-DD] [--title "..."] [--note "..."] [--tekst plik.txt] [--archive] [--json]
    python3 sources.py ingest wyniki.json|-                  # każdy URL z wyniku narzędzia (np. web_search)
    python3 sources.py quote <n> --text "dokładne słowa" [--from plik.txt|-]
    python3 sources.py list [--min-tier B] [--json]
    python3 sources.py render [--cited-in RAPORT.md | --replace-in RAPORT.md] [--only 1,3-5] [--styl lista|dowody]
    python3 sources.py cite …                                # to samo co render
    python3 sources.py verify RAPORT.md [--min-coverage 0.5] [--dowody] [--strict]

Strony czyta `extract.py`: rejestruje źródło i zapisuje cały tekst w `strony/<n>.txt` obok rejestru.
`quote` przyjmuje tylko słowa, które naprawdę są w zapisanym tekście (bez znaczenia: odstępy, wielkość liter,
znaczniki markdown). Tekst przeczytany inaczej (PDF, transkrypcja) dołączasz przez `add <url> --tekst plik.txt`.
Twierdzenie bez źródła oznaczasz `[niezweryfikowane]` zamiast numeru.

Tier (skala w skillu weryfikacja-faktow): A oficjalne/pierwotne, B renomowane media/branża,
C blogi/fora z nazwiskiem, D anonimowe/afiliacyjne/niepewne.
--archive zapisuje lokalną kopię HTML i tekstu w archiwum/ (dowód, gdyby strona się zmieniła).

Rejestr (pierwsze wygrywa): --rejestr PLIK (przed albo po poleceniu), $JARVO_REJESTR_ZRODEL, out/zrodla.json
w katalogu karty. Wspólny rejestr dla subagentów: ta sama pełna ścieżka w --rejestr albo w zmiennej.

Silnik (rejestr z blokadą, dopasowanie cytatów, render i sprawdzanie raportu) przeniesiony z
`grounded-citations` 1.2.0 Hermes Agent (Hermes Agent + Teknium, MIT); zmiany JARVO: polskie nagłówki
i znaczniki, ocena wiarygodności, zapisany tekst stron, odcisk SHA-256, link z podświetleniem cytatu.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

DOMYSLNY = Path("out/zrodla.json")
STARY_DZIENNIK = "zrodla.jsonl"            # format sprzed rejestru (jeden wpis JSON na linię)
TIERS = ["A", "B", "C", "D"]
TYPY = ["pierwotne", "wtorne", "dane", "opinia"]
WERSJA = 1

# Numer cytowania w tekście: [12]. Linki markdown ([tekst](url)) i etykiety odnośników ([1]: …) się nie liczą.
_CITE_RE = re.compile(r"\[(\d{1,4})\](?![(:])")
_NAGLOWEK_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:źródła|zrodla|sources):?(?:\*\*)?\s*$", re.IGNORECASE)
_LINIA_ZRODLA_RE = re.compile(r"^\s*(?:[-*]\s+)?\[(\d{1,4})\]\s*[-–:]?\s*(\S+)")
# Adres z nawiasami w parach (Wikipedia: /wiki/Python_(programming_language)) zostaje cały; nawias zamykający
# bez pary (koniec linku markdown) już nie należy do adresu.
_URL_RE = re.compile(r"https?://(?:[^\s\"'<>()\[\]{}]|\([^\s\"'<>()]*\))+")
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
# Jawna deklaracja: tego twierdzenia nie potwierdza żadne źródło z rejestru.
_NIEZWERYFIKOWANE_RE = re.compile(r"\[(?:niezweryfikowane|unverified)\]", re.IGNORECASE)


def dzis() -> str:
    return dt.date.today().isoformat()


# --------------------------------------------------------------------------------------------- rejestr

def sciezka_rejestru(jawna: str | None = None) -> Path:
    if jawna:
        return Path(jawna).expanduser()
    env = os.environ.get("JARVO_REJESTR_ZRODEL", "").strip()
    return Path(env).expanduser() if env else DOMYSLNY


def normalize_url(url: str) -> str:
    """Jedna strona = jeden numer: bez fragmentu (#…) i końcowego ukośnika; zapytanie (?…) zostaje."""
    u = (url or "").strip()
    if "#" in u:
        u = u.split("#", 1)[0]
    return u.rstrip("/") or u


def _ze_starego(path: Path) -> dict[str, Any] | None:
    """Przenosi dziennik out/zrodla.jsonl (numery n, checked_at) do rejestru, jeśli rejestru jeszcze nie ma."""
    stary = path.with_name(STARY_DZIENNIK)
    if not stary.exists():
        return None
    sources = []
    for line in stary.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        wpis = {"id": int(e.get("n") or len(sources) + 1), "url": normalize_url(e["url"]),
                "title": e.get("title") or "", "accessed": e.get("checked_at") or dzis()}
        for k in ("tier", "type", "date", "note", "archive"):
            if e.get(k):
                wpis[k] = e[k]
        sources.append(wpis)
    return {"version": WERSJA, "sources": sources}


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _ze_starego(path) or {"version": WERSJA, "sources": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"błąd: rejestru {path} nie da się odczytać ({exc}); zacznij od nowa: reset")
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise SystemExit(f"błąd: rejestr {path} ma nieoczekiwany kształt; zacznij od nowa: reset")
    return data


def save_ledger(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class _LedgerLock:
    """Blokada między procesami (plik .lock z O_EXCL, sama biblioteka standardowa).

    Subagenci mogą dzielić jeden rejestr; bez blokady dwa równoczesne `add` dostałyby ten sam numer.
    Po 5 s uznaje blokadę za porzuconą przez przerwany proces i ją zdejmuje, żeby nie zablokować zlecenia.
    """

    def __init__(self, path: Path, timeout: float = 5.0) -> None:
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.timeout = timeout
        self.fd: int | None = None

    def __enter__(self) -> "_LedgerLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    try:
                        self.lock_path.unlink()
                    except OSError:
                        return self
                    continue
                time.sleep(0.05)

    def __exit__(self, *_exc: object) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        try:
            self.lock_path.unlink()
        except OSError:
            pass


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plik_tekstu(path: Path, entry: dict[str, Any]) -> Path | None:
    """Zapisany tekst strony (ścieżka względem katalogu rejestru)."""
    rel = entry.get("tekst")
    return path.parent / rel if rel else None


def _zapisz_tekst(path: Path, entry: dict[str, Any], text: str) -> None:
    rel = f"strony/{entry['id']}.txt"
    (path.parent / "strony").mkdir(parents=True, exist_ok=True)
    (path.parent / rel).write_text(text, encoding="utf-8")
    entry["tekst"] = rel
    entry["sha256"] = _sha(text)


def add_sources(path: Path, urls: Iterable[str], *, title: str | None = None, accessed: str | None = None,
                meta: dict[str, Any] | None = None, text: str | None = None,
                nadpisz_tytul: bool = True) -> list[dict[str, Any]]:
    """Rejestruje adresy i zwraca ich wpisy (istniejące albo nowe). `meta` (tier, type, date, note)
    i `text` (przeczytana treść) dotyczą wywołań z jednym adresem; puste pola nie nadpisują zapisanych.
    Tytuł z wyników wyszukiwania (`nadpisz_tytul=False`) uzupełnia tylko brakujący."""
    urls = [u for u in (str(u).strip() for u in urls) if u]
    if not urls:
        return []
    meta = {k: v for k, v in (meta or {}).items() if v}
    with _LedgerLock(path):
        data = load_ledger(path)
        sources = data["sources"]
        index = {s["url"]: s for s in sources}
        out: list[dict[str, Any]] = []
        for raw in urls:
            key = normalize_url(raw)
            entry = index.get(key)
            if entry is None:
                entry = {"id": max((s["id"] for s in sources), default=0) + 1, "url": key,
                         "title": "", "accessed": accessed or dzis()}
                sources.append(entry)
                index[key] = entry
            if title and (not entry.get("title") or (len(urls) == 1 and nadpisz_tytul)):
                entry["title"] = title.strip()
            if len(urls) == 1:
                entry.update(meta)
                if text:
                    _zapisz_tekst(path, entry, text)
                    entry["accessed"] = accessed or dzis()
            out.append(entry)
        save_ledger(path, data)
    return out


def update_entry(path: Path, source_id: int, **fields: Any) -> dict[str, Any]:
    with _LedgerLock(path):
        data = load_ledger(path)
        entry = next((s for s in data["sources"] if s["id"] == source_id), None)
        if entry is None:
            raise SystemExit(f"błąd: w rejestrze nie ma źródła [{source_id}]")
        entry.update({k: v for k, v in fields.items() if v})
        save_ledger(path, data)
    return entry


def urls_from_json(payload: Any) -> list[tuple[str, str]]:
    """Pary (url, tytuł) z dowolnego JSON-a narzędzia (web_search, web_extract, search_fanout…), po kolei, bez powtórek."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            url = node.get("url") or node.get("link") or node.get("source_url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                key = normalize_url(url)
                if key not in seen:
                    seen.add(key)
                    raw_title = node.get("title") or node.get("name") or ""
                    found.append((url, raw_title if isinstance(raw_title, str) else ""))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


# -------------------------------------------------------------------------------------- archiwum

def html_na_tekst(raw: str) -> str:
    try:
        import trafilatura  # type: ignore
        text = trafilatura.extract(raw, include_comments=False, include_tables=True, favor_precision=True)
        if text:
            return text
    except ImportError:
        pass
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()


def archive(path: Path, url: str) -> tuple[str, str] | None:
    """Kopia HTML i tekstu strony w archiwum/ obok rejestru; zwraca (html, txt) względem katalogu rejestru."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jarvo-sherlock/1.0"})
        with urllib.request.urlopen(req, timeout=40) as resp:  # noqa: S310 (URL od agenta, tylko odczyt)
            raw = resp.read(8_000_000)
            charset = resp.headers.get_content_charset() or "utf-8"
    except Exception as exc:
        print(f"archiwizacja nieudana: {exc}", file=sys.stderr)
        return None
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    katalog = path.parent / "archiwum"
    katalog.mkdir(parents=True, exist_ok=True)
    (katalog / f"{digest}.html").write_bytes(raw)
    (katalog / f"{digest}.txt").write_text(html_na_tekst(raw.decode(charset, errors="replace")), encoding="utf-8")
    return f"archiwum/{digest}.html", f"archiwum/{digest}.txt"


# ------------------------------------------------------------------------------------ cytaty-dowody

def _normalize_ws(text: str) -> str:
    return " ".join((text or "").split())


# Znaczniki, które ekstraktor dokleja do tekstu identycznego z tym, co widzi czytelnik:
# „w tym _[ERAP1](https://…)_” czyta się tak samo jak strona, więc dopasowanie ich nie widzi.
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((?:[^()\s]|\([^()]*\))*\)")
_MD_NOISE_RE = re.compile(r"[*_`~]|\\(?=[^\w\s])")


def _match_key(text: str) -> str:
    collapsed = _MD_LINK_RE.sub(r"\1", text or "")
    return _normalize_ws(_MD_NOISE_RE.sub("", collapsed)).casefold()


def quote_in_evidence(quote: str, evidence: str) -> bool:
    """Czy cytat jest dosłownie w tekście (bez znaczenia: odstępy, wielkość liter, znaczniki markdown)."""
    q = _match_key(quote)
    return bool(q) and q in _match_key(evidence)


def attach_quote(path: Path, source_id: int, quote: str, evidence: str) -> dict[str, Any]:
    """Dołącza cytat-dowód po sprawdzeniu, że strona go zawiera. Cytat, którego strona nie zawiera,
    to dokładnie ta zmyślona podpórka, przed którą chroni rejestr."""
    quote = (quote or "").strip()
    if len(_normalize_ws(quote).split()) < 3:
        raise SystemExit("błąd: cytat za krótki, potrzeba co najmniej 3 słów dosłownego tekstu")
    if not quote_in_evidence(quote, evidence):
        raise SystemExit("błąd: tego cytatu nie ma dosłownie w tekście strony; skopiuj dokładne słowa "
                         "z pobranego tekstu, bez parafrazy")
    with _LedgerLock(path):
        data = load_ledger(path)
        entry = next((s for s in data["sources"] if s["id"] == source_id), None)
        if entry is None:
            raise SystemExit(f"błąd: w rejestrze nie ma źródła [{source_id}]")
        quotes = entry.setdefault("quotes", [])
        norm = _match_key(quote)
        if not any(_match_key(q.get("text", "")) == norm for q in quotes):
            quotes.append({"text": quote, "added": dzis()})
            save_ledger(path, data)
    return entry


def tekst_dowodu(path: Path, entry: dict[str, Any]) -> str | None:
    """Tekst, wobec którego sprawdzamy cytat: zapisana strona albo tekst z archiwum."""
    for rel in (entry.get("tekst"), entry.get("archiwum_tekst")):
        if rel and (path.parent / rel).is_file():
            return (path.parent / rel).read_text(encoding="utf-8")
    return None


def link_podswietlenia(url: str, quote: str) -> str:
    """Link `#:~:text=`: przeglądarka przewija do cytatu i go podświetla."""
    words = _normalize_ws(_MD_LINK_RE.sub(r"\1", quote)).split()

    def enc(ws: list[str]) -> str:
        return urllib.parse.quote(" ".join(ws), safe="").replace("-", "%2D")

    frag = enc(words) if len(words) <= 8 else f"{enc(words[:4])},{enc(words[-4:])}"
    return f"{url}#:~:text={frag}"


# ---------------------------------------------------------------------------------------- render

def linia_zrodla(s: dict[str, Any]) -> str:
    title = s.get("title")
    opis = f" — {title}" if title and normalize_url(title) != s["url"] else ""
    info = []
    if s.get("date"):
        info.append(f"opublikowano {s['date']}")
    if s.get("tier"):
        info.append(f"wiarygodność {s['tier']}" + (f", {s['type']}" if s.get("type") else ""))
    info.append(f"dostęp {s.get('accessed', '?')}")
    return f"- [{s['id']}] {s['url']}{opis} ({'; '.join(info)})"


def render_sources(sources: list[dict[str, Any]], style: str = "lista", only: set[int] | None = None) -> str:
    picked = sorted((s for s in sources if only is None or s["id"] in only), key=lambda s: s["id"])
    if not picked:
        return ""
    lines = ["## Źródła", ""]
    for s in picked:
        lines.append(linia_zrodla(s))
        if style == "dowody":
            for q in s.get("quotes", []):
                lines.append(f"  > „{q.get('text', '')}” ([podświetl]({link_podswietlenia(s['url'], q.get('text', ''))}))")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------- sprawdzanie

def _ostatni_naglowek(lines: list[str]) -> int:
    idx = -1
    for i, line in enumerate(lines):
        if _NAGLOWEK_RE.match(line):
            idx = i
    return idx


def _split_draft(text: str) -> tuple[str, dict[int, str]]:
    """(tekst bez bloku źródeł i bloków kodu, {numer: url} z bloku „Źródła” po ostatnim nagłówku)."""
    lines = text.splitlines()
    header_idx = _ostatni_naglowek(lines)
    listed: dict[int, str] = {}
    if header_idx >= 0:
        for line in lines[header_idx + 1:]:
            m = _LINIA_ZRODLA_RE.match(line)
            if m:
                url_match = _URL_RE.search(line)
                listed[int(m.group(1))] = url_match.group(0) if url_match else m.group(2)
        body_lines = lines[:header_idx]
    else:
        body_lines = lines
    prose: list[str] = []
    in_fence = False
    for line in body_lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            prose.append(line)
    return "\n".join(prose), listed


def _strip_sources_block(text: str) -> str:
    """Raport bez końcowego bloku źródeł; dzięki temu `render --replace-in` można powtarzać bez dublowania."""
    lines = text.splitlines()
    header_idx = _ostatni_naglowek(lines)
    return text if header_idx < 0 else "\n".join(lines[:header_idx])


def _sentences(prose: str) -> list[str]:
    """Zgrubny podział na zdania (≥ 4 słowa) bez nagłówków i wierszy tabel."""
    out: list[str] = []
    for line in prose.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()
        for part in re.split(r"(?<=[.!?])\s+", stripped):
            part = part.strip()
            if len(part.split()) >= 4:
                out.append(part)
    return out


def _numery(ids: Iterable[int]) -> str:
    return ", ".join(f"[{i}]" for i in sorted(ids))


def verify_draft(draft_path: Path, sources: list[dict[str, Any]], strict: bool = False,
                 min_coverage: float | None = None, require_evidence: bool = False) -> tuple[int, list[str], list[str]]:
    """Zwraca (kod wyjścia, błędy, ostrzeżenia)."""
    prose, listed = _split_draft(draft_path.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in sources}
    errors: list[str] = []
    warnings: list[str] = []

    cited_set = {int(m) for m in _CITE_RE.findall(prose)}
    known = {i for i in cited_set if i in by_id}

    unknown = cited_set - known
    if unknown:
        errors.append(f"numery spoza rejestru (zmyślone albo przenumerowane): {_numery(unknown)}")
    if cited_set and not listed:
        errors.append("raport cytuje źródła, ale nie ma bloku „## Źródła”; uruchom render --replace-in")
    missing_from_block = cited_set - set(listed) if listed else set()
    if missing_from_block:
        errors.append(f"cytowane, a brak ich w bloku „Źródła”: {_numery(missing_from_block)}")
    for sid, url in sorted(listed.items()):
        entry = by_id.get(sid)
        if entry is None:
            errors.append(f"blok „Źródła” wymienia [{sid}], którego nie ma w rejestrze")
        elif normalize_url(url) != entry["url"]:
            errors.append(f"adres [{sid}] w bloku „Źródła” różni się od rejestru (blok: {url} / rejestr: "
                          f"{entry['url']}); uruchom render --replace-in")

    bez_oceny = {i for i in known if by_id[i].get("tier") not in TIERS}
    if bez_oceny:
        errors.append(f"cytowane źródła bez oceny wiarygodności (add <url> --tier … --type …): {_numery(bez_oceny)}")
    nieprzeczytane = {i for i in known if not (by_id[i].get("tekst") or by_id[i].get("archiwum_tekst")
                                               or by_id[i].get("quotes"))}
    if nieprzeczytane:
        errors.append("cytowane źródła bez przeczytanego tekstu, tylko z wyniku wyszukiwania (extract.py <url> "
                      f"albo add <url> --tekst plik.txt): {_numery(nieprzeczytane)}")
    if require_evidence:
        bez_cytatu = {i for i in known if not by_id[i].get("quotes")}
        if bez_cytatu:
            errors.append(f"cytowane źródła bez cytatu-dowodu (quote <n> --text …): {_numery(bez_cytatu)}")

    extra_in_block = set(listed) - cited_set
    if extra_in_block:
        warnings.append(f"w bloku „Źródła”, ale nigdzie nie cytowane w tekście: {_numery(extra_in_block)}")
    uncited = set(by_id) - cited_set
    if uncited:
        warnings.append(f"w rejestrze, ale nie cytowane w tym raporcie: {_numery(uncited)}")

    sentences = _sentences(prose)
    cited_sentences = [s for s in sentences if _CITE_RE.search(s)]
    unverified = [s for s in sentences if _NIEZWERYFIKOWANE_RE.search(s)]
    covered = [s for s in sentences if _CITE_RE.search(s) or _NIEZWERYFIKOWANE_RE.search(s)]
    coverage = (len(covered) / len(sentences)) if sentences else 0.0
    if min_coverage is not None and sentences and coverage < min_coverage:
        errors.append(f"pokrycie {coverage:.0%} poniżej wymaganych {min_coverage:.0%} ({len(covered)}/{len(sentences)} "
                      "zdań ma numer źródła albo [niezweryfikowane])")
    over_cited = [s for s in sentences if len(_CITE_RE.findall(s)) > 3]
    if over_cited:
        warnings.append(f"{len(over_cited)} zdań ma więcej niż 3 numery źródeł")

    domeny = {urllib.parse.urlsplit(by_id[i]["url"]).hostname for i in known}
    code = 1 if errors else (1 if (strict and warnings) else 0)
    quoted = sum(1 for s in sources if s.get("quotes"))
    stats = (f"{len(sentences)} zdań, {len(covered)} z podanym pochodzeniem ({coverage:.0%}): {len(cited_sentences)} "
             f"z numerem źródła, {len(unverified)} [niezweryfikowane]; cytowane źródła: {len(known)} z {len(domeny)} "
             f"domen; w rejestrze {len(by_id)} ({quoted} z cytatami-dowodami)")
    warnings.insert(0, f"stats: {stats}")
    return code, errors, warnings


# ------------------------------------------------------------------------------------------- CLI

def _parse_only(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for chunk in spec.replace(" ", "").split(","):
        if not chunk:
            continue
        if "-" in chunk:
            lo, _, hi = chunk.partition("-")
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(chunk))
    return out


def _czytaj(spec: str) -> str:
    return sys.stdin.read() if spec == "-" else Path(spec).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sources.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rejestr", help="plik rejestru (zamiast $JARVO_REJESTR_ZRODEL i out/zrodla.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("reset", help="czysty rejestr na nowe zlecenie")

    a = sub.add_parser("add", help="rejestruje źródło (albo kilka), wypisuje numery")
    a.add_argument("urls", nargs="+")
    a.add_argument("--tier", choices=TIERS)
    a.add_argument("--type", choices=TYPY)
    a.add_argument("--date", help="data publikacji RRRR-MM-DD")
    a.add_argument("--title")
    a.add_argument("--note")
    a.add_argument("--tekst", help="plik z przeczytaną treścią (PDF, transkrypcja…), dowód do cytatów")
    a.add_argument("--archive", action="store_true", help="lokalna kopia HTML i tekstu w archiwum/")
    a.add_argument("--json", action="store_true")

    ing = sub.add_parser("ingest", help="rejestruje każdy URL z wyniku narzędzia (JSON)")
    ing.add_argument("file", help="plik JSON albo - (stdin)")

    q = sub.add_parser("quote", help="dołącza dosłowny cytat-dowód do źródła")
    q.add_argument("id", type=int)
    q.add_argument("--text", required=True, help="dokładne słowa skopiowane z tekstu strony")
    q.add_argument("--from", dest="evidence", help="plik z tekstem strony albo - (domyślnie zapisany tekst źródła)")

    ls = sub.add_parser("list", help="pokazuje rejestr")
    ls.add_argument("--min-tier", choices=TIERS)
    ls.add_argument("--json", action="store_true")

    for name in ("render", "cite"):
        r = sub.add_parser(name, help="blok „## Źródła” z rejestru" + (" (to samo co render)" if name == "cite" else ""))
        r.add_argument("--styl", default="lista", choices=["lista", "dowody"],
                       help="dowody: pod każdym źródłem jego cytaty z linkiem podświetlenia")
        r.add_argument("--only", help="numery, np. 1,3,5-7")
        r.add_argument("--cited-in", help="tylko numery cytowane w tym raporcie")
        r.add_argument("--replace-in", help="podmienia blok „Źródła” w tym raporcie (cytowane w nim numery)")

    v = sub.add_parser("verify", help="sprawdza cytowania raportu z rejestrem")
    v.add_argument("draft")
    v.add_argument("--strict", action="store_true", help="ostrzeżenia też zatrzymują")
    v.add_argument("--min-coverage", type=float, help="wymagany udział zdań z pochodzeniem, np. 0.5")
    v.add_argument("--dowody", action="store_true", help="każde cytowane źródło musi mieć cytat-dowód")

    # --rejestr działa też po poleceniu (`sources.py add <url> --rejestr X`), jak w extract.py
    argv = list(sys.argv[1:] if argv is None else argv)
    for i, arg in enumerate(argv):
        if arg.startswith("--rejestr=") or (arg == "--rejestr" and i + 1 < len(argv)):
            val = arg.split("=", 1)[1] if "=" in arg else argv[i + 1]
            del argv[i:i + (1 if "=" in arg else 2)]
            argv = ["--rejestr", val, *argv]
            break
    args = ap.parse_args(argv)
    path = sciezka_rejestru(args.rejestr)

    if args.cmd == "reset":
        with _LedgerLock(path):
            save_ledger(path, {"version": WERSJA, "sources": []})
        shutil.rmtree(path.parent / "strony", ignore_errors=True)
        print(f"rejestr wyczyszczony: {path}")
        return 0

    if args.cmd == "add":
        text = _czytaj(args.tekst) if args.tekst else None
        meta = {"tier": args.tier, "type": args.type, "date": args.date, "note": args.note}
        entries = add_sources(path, args.urls, title=args.title, meta=meta, text=text)
        if args.archive:
            for e in entries:
                kopia = archive(path, e["url"])
                if kopia:
                    e = update_entry(path, e["id"], archive=kopia[0], archiwum_tekst=kopia[1])
        entries = [next(s for s in load_ledger(path)["sources"] if s["id"] == e["id"]) for e in entries]
        if args.json:
            print(json.dumps(entries, indent=2, ensure_ascii=False))
        else:
            for e in entries:
                print(f"[{e['id']}] {e['url']}")
        return 0

    if args.cmd == "ingest":
        try:
            payload = json.loads(_czytaj(args.file))
        except json.JSONDecodeError as exc:
            print(f"błąd: to nie jest poprawny JSON ({exc})", file=sys.stderr)
            return 2
        pairs = urls_from_json(payload)
        if not pairs:
            print("brak adresów w danych", file=sys.stderr)
            return 1
        for url, title in pairs:
            entry = add_sources(path, [url], title=title or None, nadpisz_tytul=False)[0]
            print(f"[{entry['id']}] {entry['url']}")
        return 0

    data = load_ledger(path)
    sources = sorted(data["sources"], key=lambda s: s["id"])

    if args.cmd == "quote":
        entry = next((s for s in sources if s["id"] == args.id), None)
        if entry is None:
            raise SystemExit(f"błąd: w rejestrze nie ma źródła [{args.id}]")
        evidence = _czytaj(args.evidence) if args.evidence else tekst_dowodu(path, entry)
        if evidence is None:
            raise SystemExit(f"błąd: źródło [{args.id}] nie ma zapisanego tekstu; przeczytaj je: "
                             f"extract.py {entry['url']} (albo add {entry['url']} --tekst plik.txt)")
        entry = attach_quote(path, args.id, args.text, evidence)
        print(f"[{entry['id']}] cytat zapisany (cytatów: {len(entry.get('quotes', []))})")
        return 0

    if args.cmd == "list":
        limit = TIERS.index(args.min_tier) if args.min_tier else None
        picked = [s for s in sources if limit is None or (s.get("tier") in TIERS and TIERS.index(s["tier"]) <= limit)]
        if args.json:
            print(json.dumps(picked, indent=2, ensure_ascii=False))
        elif not sources:
            print(f"rejestr jest pusty: {path}")
        else:
            for s in picked:
                stan = "przeczytane" if (s.get("tekst") or s.get("archiwum_tekst")) else "tylko wynik wyszukiwania"
                nq = len(s.get("quotes", []))
                print(f"[{s['id']}] {s.get('tier') or '?'} {s.get('type') or '?'} {s.get('date') or '?'} "
                      f"{s.get('title') or ''} {s['url']} ({stan}" + (f", cytatów: {nq})" if nq else ")"))
        return 0

    if args.cmd in ("render", "cite"):
        only = _parse_only(args.only)
        draft_for_ids = args.replace_in or args.cited_in
        if draft_for_ids:
            prose, _ = _split_draft(Path(draft_for_ids).read_text(encoding="utf-8"))
            cited = {int(m) for m in _CITE_RE.findall(prose)}
            only = cited if only is None else (only & cited)
        block = render_sources(sources, style=args.styl, only=only)
        if not block:
            print("brak źródeł do wypisania", file=sys.stderr)
            return 1
        if args.replace_in:
            target = Path(args.replace_in)
            body = _strip_sources_block(target.read_text(encoding="utf-8"))
            target.write_text(body.rstrip("\n") + "\n\n" + block + "\n", encoding="utf-8")
            print(f"blok „Źródła” podmieniony w {target}")
            return 0
        print(block)
        return 0

    if args.cmd == "verify":
        draft_path = Path(args.draft)
        if not draft_path.is_file():
            print(f"błąd: nie ma pliku {draft_path}", file=sys.stderr)
            return 2
        code, errors, warnings = verify_draft(draft_path, sources, strict=args.strict,
                                              min_coverage=args.min_coverage, require_evidence=args.dowody)
        for w in warnings:
            print(("info: " if w.startswith("stats: ") else "uwaga: ") + w.removeprefix("stats: "))
        for e in errors:
            print(f"BŁĄD: {e}", file=sys.stderr)
        print("cytowania OK" if code == 0 else "sprawdzenie nieudane")
        return code

    return 2


if __name__ == "__main__":
    sys.exit(main())
