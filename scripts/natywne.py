#!/usr/bin/env python3
"""Manifest narzędzi instalacji natywnej (docs/NATYWNIE.md, L03): vendor/natywne.yaml → vendor/natywne.lock.json.

    python scripts/natywne.py sprawdz      # kompletność wpisów (url https, sha256, rozmiar, format, źródło w spisie)
    python scripts/natywne.py generuj      # zapis vendor/natywne.lock.json (czyta go instalator bez YAML)

Lock trzyma też sumę każdego locka venvu (sekcja `venvy`), więc zmiana manifestu albo locka venvu bez nowego
natywne.lock.json nie przejdzie `sprawdz` ani testu tests/test_natywne.py.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

MANIFEST = fl.REPO_ROOT / "vendor" / "natywne.yaml"
LOCK = fl.REPO_ROOT / "vendor" / "natywne.lock.json"
ZRODLA = fl.REPO_ROOT / "vendor" / "zrodla.yaml"
DOCKERFILE = fl.REPO_ROOT / "infra" / "Dockerfile"
PLATFORMY = ("windows-x64", "windows-arm64", "macos-arm64", "linux-x64", "linux-arm64")
FORMATY = {"zip", "tar.gz", "tar.xz", "tar.bz2", "plik"}
KIEDY = {"instalacja", "przy-uzyciu", "dodatek"}
POLA_PLIKU = {"url", "sha256", "rozmiar", "format", "usun_poziom", "bin", "env", "nazwa_pliku", "usun",
              "zmien_nazwe", "brak", "zamiast"}
POLA_MODELU = {"zrodlo", "rewizja", "licencja", "rola", "kiedy", "katalog", "pliki"}
POLA_VENVU = {"python", "lock", "kiedy", "rola", "bez", "pobranie_mb", "venv_mb", "torch_backend"}
TORCH_BACKEND = {"cpu"}          # `uv pip install --torch-backend <wartość>`: torch z indeksu PyTorch (sumy w locku)
NAZWA = re.compile(r"^[a-z][a-z0-9-]*$")
SHA = re.compile(r"^[0-9a-f]{64}$")
ZMIENNA = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NAZWA_PLIKU = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


def wczytaj(path: Path | None = None) -> dict:
    return fl.load_yaml(path or MANIFEST) or {}


def _wzgledna(sciezka) -> bool:
    """Ścieżka w katalogu narzędzia: względna, bez „..”, bez litery dysku."""
    s = str(sciezka or "").replace("\\", "/")
    return bool(s.strip()) and not s.startswith("/") and ":" not in s and ".." not in s.split("/")


def nazwa_pliku(p: dict) -> str:
    """Pod tą nazwą plik ląduje w katalogu narzędzia (format plik) i w pamięci podręcznej: `nazwa_pliku` albo
    zdekodowana końcówka adresu, jak w jarvo/pobieracz.py (nazwa_z_adresu)."""
    if p.get("nazwa_pliku"):
        return str(p["nazwa_pliku"])
    return urllib.parse.unquote(str(p.get("url") or "").split("?", 1)[0].rsplit("/", 1)[-1])


def wymagania_locka(tekst: str) -> tuple[list[str], list[str]]:
    """Lock uv (`uv pip compile --generate-hashes`): (nazwy wymagań, problemy). Każde wymaganie musi mieć sumę
    sha256, a opcje (-e, --index-url, -r…) są zakazane: lock nie może zmieniać indeksu ani dociągać innych plików."""
    nazwy, problemy = [], []
    for linia in re.sub(r"\\\r?\n", " ", tekst).splitlines():
        s = linia.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("-"):
            problemy.append(f"opcja {s.split()[0]} w locku (dozwolone tylko wymagania z --hash)")
            continue
        nazwa = re.split(r"[\s=<>!~;@\[]", s, maxsplit=1)[0].lower().replace("_", "-")
        nazwy.append(nazwa)
        if "--hash=sha256:" not in s:
            problemy.append(f"{nazwa}: bez --hash=sha256 (uv pip install --require-hashes odmówi)")
    return nazwy, problemy


def bledy(dane: dict, zrodla: dict | None = None, repo: Path | None = None) -> list[str]:
    """Lista problemów manifestu (pusta = dobrze). `zrodla` = słownik `zrodla` z vendor/zrodla.yaml, `repo` = korzeń
    repo z lockami venvów (domyślnie to repo)."""
    wynik: list[str] = []
    if dane.get("version") != 1:
        wynik.append("natywne.yaml: version musi być 1")
    h = dane.get("hermes") or {}
    if not re.match(r"^https://github\.com/[\w.-]+/[\w.-]+$", str(h.get("repo") or "")):
        wynik.append("natywne.yaml/hermes: repo musi być adresem https://github.com/<właściciel>/<repo>")
    if not re.match(r"^[0-9a-f]{40}$", str(h.get("commit") or "")):
        wynik.append("natywne.yaml/hermes: commit musi być pełnym SHA (40 znaków)")
    if not str(h.get("tag") or "").strip() or not str(h.get("wersja") or "").strip():
        wynik.append("natywne.yaml/hermes: brak tagu albo wersji")
    if not isinstance(h.get("dodatki"), list) or not all(isinstance(x, str) for x in h["dodatki"]):
        wynik.append("natywne.yaml/hermes: dodatki to lista nazw extras z pyproject.toml Hermesa")
    obraz = DOCKERFILE.read_text(encoding="utf-8") if DOCKERFILE.is_file() else ""
    m = re.search(r"^ARG HERMES_IMAGE=[^:\s]+:([^@\s]+)", obraz, re.M)
    if m and h.get("tag") and m.group(1) != h["tag"]:
        wynik.append(f"natywne.yaml/hermes: tag {h['tag']} różni się od obrazu VPS ({m.group(1)} w infra/Dockerfile)")
    narzedzia = dane.get("narzedzia") or {}
    if not isinstance(narzedzia, dict) or not narzedzia:
        wynik.append("natywne.yaml: brak sekcji narzedzia")
        narzedzia = {}
    for nazwa, wpis in narzedzia.items():
        gdzie = f"natywne.yaml/{nazwa}"
        if not NAZWA.match(str(nazwa)):
            wynik.append(f"{gdzie}: nazwa tylko z małych liter, cyfr i myślników")
        if not isinstance(wpis, dict):
            wynik.append(f"{gdzie}: wpis musi być słownikiem")
            continue
        for pole in ("zrodlo", "wersja", "licencja", "rola"):
            if not str(wpis.get(pole) or "").strip():
                wynik.append(f"{gdzie}: brak pola {pole}")
        if zrodla is not None and wpis.get("zrodlo") and wpis["zrodlo"] not in zrodla:
            wynik.append(f"{gdzie}: źródła {wpis['zrodlo']!r} nie ma w vendor/zrodla.yaml (przegląd z docs/SOURCES.md)")
        if (wpis.get("kiedy") or "instalacja") not in KIEDY:
            wynik.append(f"{gdzie}: kiedy spoza {sorted(KIEDY)}")
        pliki = wpis.get("pliki") or {}
        for platforma in PLATFORMY:
            p = pliki.get(platforma)
            gp = f"{gdzie}/{platforma}"
            if not isinstance(p, dict):
                wynik.append(f"{gp}: brak pliku (podaj plik albo `brak: <powód>`)")
                continue
            obce = set(p) - POLA_PLIKU
            if obce:
                wynik.append(f"{gp}: nieznane pola {sorted(obce)}")
            if "brak" in p:
                if not str(p.get("brak") or "").strip():
                    wynik.append(f"{gp}: `brak` wymaga powodu")
                continue
            url = str(p.get("url") or "")
            if not url.startswith("https://") or "latest" in url.split("?")[0].split("/"):
                wynik.append(f"{gp}: url musi być dokładnym adresem https (bez latest)")
            if not SHA.match(str(p.get("sha256") or "")):
                wynik.append(f"{gp}: sha256 musi mieć 64 znaki hex")
            if not isinstance(p.get("rozmiar"), int) or p["rozmiar"] <= 0:
                wynik.append(f"{gp}: rozmiar w bajtach (liczba)")
            if p.get("format") not in FORMATY:
                wynik.append(f"{gp}: format spoza {sorted(FORMATY)}")
            if not isinstance(p.get("usun_poziom", 0), int) or p.get("usun_poziom", 0) < 0:
                wynik.append(f"{gp}: usun_poziom to liczba >= 0")
            for k in p.get("bin") or []:
                if str(k).startswith(("/", "\\")) or ".." in str(k).replace("\\", "/").split("/"):
                    wynik.append(f"{gp}: bin {k!r} ma być ścieżką względną w katalogu narzędzia")
            if "nazwa_pliku" in p and not NAZWA_PLIKU.match(str(p["nazwa_pliku"] or "")):
                wynik.append(f"{gp}: nazwa_pliku to sama nazwa pliku (litery, cyfry, . _ + -), bez katalogów")
            env = p.get("env") or {}
            if not isinstance(env, dict) or not all(ZMIENNA.match(str(k)) and isinstance(v, str) for k, v in env.items()):
                wynik.append(f"{gp}: env to słownik NAZWA: \"tekst\" (wartości w cudzysłowie)")
            usun = p.get("usun", [])
            if not isinstance(usun, list) or not all(isinstance(x, str) and _wzgledna(x) for x in usun) \
                    or len(set(usun)) != len(usun):
                wynik.append(f"{gp}: usun to lista różnych ścieżek względnych w katalogu narzędzia")
            zmien = p.get("zmien_nazwe", {})
            if not isinstance(zmien, dict) or not all(isinstance(k, str) and isinstance(v, str) and _wzgledna(k)
                                                     and _wzgledna(v) for k, v in zmien.items()) \
                    or len(set(zmien.values())) != len(zmien):
                wynik.append(f"{gp}: zmien_nazwe to słownik {{stara: nowa}} ścieżek względnych (bez powtórzeń)")
            if p.get("format") == "plik" and (usun or zmien):
                wynik.append(f"{gp}: format plik nie ma czego usuwać ani przemianowywać (użyj nazwa_pliku)")
            if p.get("format") == "plik" and isinstance(env, dict):
                plik = nazwa_pliku(p)
                for k, v in env.items():
                    if str(v).startswith("{katalog}/") and str(v) != "{katalog}/" + plik:
                        wynik.append(f"{gp}: env {k} wskazuje {v}, a plik ląduje jako {{katalog}}/{plik}")
        for platforma in set(pliki) - set(PLATFORMY):
            wynik.append(f"{gdzie}: nieznana platforma {platforma}")
    for nazwa, m in (dane.get("modele") or {}).items():
        gdzie = f"natywne.yaml/modele/{nazwa}"
        if not NAZWA.match(str(nazwa)) or not isinstance(m, dict):
            wynik.append(f"{gdzie}: nazwa z małych liter i myślników, wpis jako słownik")
            continue
        if set(m) - POLA_MODELU:
            wynik.append(f"{gdzie}: nieznane pola {sorted(set(m) - POLA_MODELU)}")
        for pole in ("zrodlo", "licencja", "rola", "katalog"):
            if not str(m.get(pole) or "").strip():
                wynik.append(f"{gdzie}: brak pola {pole}")
        if zrodla is not None and m.get("zrodlo") and m["zrodlo"] not in zrodla:
            wynik.append(f"{gdzie}: źródła {m['zrodlo']!r} nie ma w vendor/zrodla.yaml")
        if not re.match(r"^[0-9a-f]{40}$", str(m.get("rewizja") or "")):
            wynik.append(f"{gdzie}: rewizja musi być pełnym commitem repo modelu (40 znaków), nie tagiem")
        if (m.get("kiedy") or "instalacja") not in KIEDY:
            wynik.append(f"{gdzie}: kiedy spoza {sorted(KIEDY)}")
        if not re.match(r"^[a-z0-9][a-z0-9._-]*$", str(m.get("katalog") or "")):
            wynik.append(f"{gdzie}: katalog to jedna nazwa (małe litery, cyfry, . _ -)")
        cele = set()
        for i, p in enumerate(m.get("pliki") or []):
            gp = f"{gdzie}/pliki[{i}]"
            cel = str((p or {}).get("cel") or "")
            if not cel or cel.startswith(("/", "\\")) or ".." in cel.replace("\\", "/").split("/"):
                wynik.append(f"{gp}: cel to ścieżka względna w katalogu modelu")
            if cel in cele:
                wynik.append(f"{gp}: cel {cel} powtórzony")
            cele.add(cel)
            url = str((p or {}).get("url") or "")
            if not url.startswith("https://") or (m.get("rewizja") and str(m["rewizja"]) not in url
                                                  and "huggingface.co" in url):
                wynik.append(f"{gp}: url https z rewizją modelu w adresie")
            if not SHA.match(str((p or {}).get("sha256") or "")):
                wynik.append(f"{gp}: sha256 musi mieć 64 znaki hex")
            if not isinstance((p or {}).get("rozmiar"), int) or p["rozmiar"] <= 0:
                wynik.append(f"{gp}: rozmiar w bajtach (liczba)")
        if not m.get("pliki"):
            wynik.append(f"{gdzie}: brak plików")
    wynik += _bledy_venvow(dane.get("venvy") or {}, narzedzia, Path(repo) if repo else fl.REPO_ROOT)
    return wynik


def _bledy_venvow(venvy: dict, narzedzia: dict, repo: Path) -> list[str]:
    """Sekcja venvy: Python z sekcji narzedzia, lock z sumami w infra/python/ (jak w obrazie), liczby z pomiaru."""
    wynik: list[str] = []
    if not isinstance(venvy, dict):
        return ["natywne.yaml: venvy to słownik {nazwa: wpis}"]
    for nazwa, v in venvy.items():
        gdzie = f"natywne.yaml/venvy/{nazwa}"
        if not NAZWA.match(str(nazwa)) or not isinstance(v, dict):
            wynik.append(f"{gdzie}: nazwa z małych liter i myślników, wpis jako słownik")
            continue
        if set(v) - POLA_VENVU:
            wynik.append(f"{gdzie}: nieznane pola {sorted(set(v) - POLA_VENVU)}")
        if not str(v.get("python") or "").startswith("python") or v.get("python") not in narzedzia:
            wynik.append(f"{gdzie}: python to wpis Pythona z sekcji narzedzia (np. python312)")
        if not str(v.get("rola") or "").strip():
            wynik.append(f"{gdzie}: brak pola rola")
        if (v.get("kiedy") or "instalacja") not in KIEDY:
            wynik.append(f"{gdzie}: kiedy spoza {sorted(KIEDY)}")
        bez = v.get("bez", [])
        if not isinstance(bez, list) or not all(isinstance(b, str) and b for b in bez):
            wynik.append(f"{gdzie}: bez to lista nazw paczek celowo pominiętych (uv pip check je zgłosi)")
            bez = []
        mb = v.get("pobranie_mb")
        if not isinstance(mb, dict) or set(mb) != set(PLATFORMY) or not all(isinstance(x, int) and x > 0
                                                                             for x in mb.values()):
            wynik.append(f"{gdzie}: pobranie_mb to MB kół dla każdej z {len(PLATFORMY)} platform")
        if "venv_mb" in v and (not isinstance(v["venv_mb"], int) or v["venv_mb"] <= 0):
            wynik.append(f"{gdzie}: venv_mb to rozmiar venvu w MB (liczba)")
        if "torch_backend" in v and v["torch_backend"] not in TORCH_BACKEND:
            wynik.append(f"{gdzie}: torch_backend spoza {sorted(TORCH_BACKEND)}")
        sciezka = str(v.get("lock") or "")
        if not (sciezka.startswith("infra/python/") and _wzgledna(sciezka)):
            wynik.append(f"{gdzie}: lock to plik w infra/python/ (ścieżka od korzenia repo)")
            continue
        if not (repo / sciezka).is_file():
            wynik.append(f"{gdzie}: nie ma pliku {sciezka}")
            continue
        nazwy, problemy = wymagania_locka((repo / sciezka).read_text(encoding="utf-8"))
        wynik += [f"{gdzie}: {sciezka}: {p}" for p in problemy[:5]]
        if not nazwy:
            wynik.append(f"{gdzie}: {sciezka} nie ma żadnej paczki")
        for b in bez:
            if b.lower().replace("_", "-") in nazwy:
                wynik.append(f"{gdzie}: {b} jest w `bez`, a lock go instaluje")
    return wynik


def _venv_do_locka(v: dict, repo: Path) -> dict:
    dane = (repo / v["lock"]).read_bytes()
    nazwy, _ = wymagania_locka(dane.decode("utf-8"))
    out = {"python": str(v["python"]), "lock": str(v["lock"]), "sha256": hashlib.sha256(dane).hexdigest(),
           "paczek": len(set(nazwy)), "kiedy": v.get("kiedy") or "instalacja", "bez": list(v.get("bez") or []),
           "pobranie_mb": {p: v["pobranie_mb"][p] for p in PLATFORMY}}
    for pole in ("venv_mb", "torch_backend"):
        if pole in v:
            out[pole] = v[pole]
    return out


def lock(dane: dict, repo: Path | None = None) -> dict:
    """Postać dla instalatora: tylko to, czego potrzebuje pobieracz, posortowane (stabilny diff). Przy venvach także
    sha256 locka (nazwa katalogu venvu i kontrola, że lock nie zmienił się bez nowego natywne.lock.json) i liczba
    paczek policzona z pliku."""
    repo = Path(repo) if repo else fl.REPO_ROOT
    out = {}
    for nazwa in sorted(dane.get("narzedzia") or {}):
        w = dane["narzedzia"][nazwa]
        pliki = {}
        for platforma in PLATFORMY:
            p = dict((w.get("pliki") or {}).get(platforma) or {})
            pliki[platforma] = {k: p[k] for k in sorted(p)}
        out[nazwa] = {"wersja": str(w["wersja"]), "kiedy": w.get("kiedy") or "instalacja",
                      "licencja": str(w["licencja"]), "zrodlo": str(w["zrodlo"]), "pliki": pliki}
    h = dane.get("hermes") or {}
    hermes = {k: h[k] for k in ("repo", "tag", "commit", "wersja", "dodatki") if k in h}
    modele = {}
    for nazwa in sorted(dane.get("modele") or {}):
        m = dane["modele"][nazwa]
        modele[nazwa] = {"rewizja": str(m["rewizja"]), "kiedy": m.get("kiedy") or "instalacja",
                         "licencja": str(m["licencja"]), "zrodlo": str(m["zrodlo"]), "katalog": str(m["katalog"]),
                         "pliki": [{k: p[k] for k in ("cel", "url", "sha256", "rozmiar")} for p in m.get("pliki") or []]}
    venvy = {nazwa: _venv_do_locka(dane["venvy"][nazwa], repo) for nazwa in sorted(dane.get("venvy") or {})}
    return {"version": 1, "hermes": hermes, "narzedzia": out, "modele": modele, "venvy": venvy}


def tekst_locka(dane: dict, repo: Path | None = None) -> str:
    return json.dumps(lock(dane, repo), ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main(argv: list[str]) -> int:
    polecenie = argv[1] if len(argv) > 1 else "sprawdz"
    dane = wczytaj()
    zrodla = (fl.load_yaml(ZRODLA) or {}).get("zrodla") or {}
    problemy = bledy(dane, zrodla)
    for p in problemy:
        print(f"✗ {p}")
    if problemy:
        return 1
    if polecenie == "generuj":
        LOCK.write_text(tekst_locka(dane), encoding="utf-8", newline="\n")
        print(f"✓ {LOCK.relative_to(fl.REPO_ROOT).as_posix()}: {len(dane['narzedzia'])} narzędzi, "
              f"{len(dane.get('modele') or {})} modeli, {len(dane.get('venvy') or {})} venvów")
        return 0
    if polecenie == "sprawdz":
        aktualny = LOCK.is_file() and LOCK.read_text(encoding="utf-8") == tekst_locka(dane)
        print("✓ manifest kompletny" + ("" if aktualny else "; lock nieaktualny: python scripts/natywne.py generuj"))
        return 0 if aktualny else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
