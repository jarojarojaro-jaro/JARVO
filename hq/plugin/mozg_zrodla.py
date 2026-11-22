"""Źródła Mózgu aplikacji Jarvo (docs/HQ.md „Mózg”, widok `#/mozg`, pakiet `mozg` ładowany na żądanie).

- **`GET /mozg/zrodla`**: lista źródeł grafu. Zawsze pierwsze jest `jarvo`, skarbiec Jarva: graf i notatki dają trasy
  wtyczki `jarvo-wiedza` (`/api/plugins/jarvo-wiedza/graph`, `/note`), więc tu jest tylko wpis. Dalej źródła
  z konfiguracji instalacji `<dane>/jarvo/konfig/mozg.json`: jeden obiekt, lista albo `{"zrodla": [...]}`, wpis
  `{"nazwa", "nazwa_en"?, "graf": "<plik json>", "notatka_url"?: "https://…/{id}.html", "widok_3d"?: "https://…"}`
  (bez `widok_3d` = strona główna serwisu z `notatka_url`).
  Repo nie zna żadnej prywatnej ścieżki: plik pisze właściciel instalacji.
- **Części Mózgu** (główne punkty wejścia widoku): `"kategorie": [{"nazwa", "nazwa_en"?, "opis"?, "opis_en"?,
  "foldery": ["agenci", …], "ikona"?, "drugorzedna"?}]` na górze pliku (`{"kategorie": […], "zrodla": […]}`) zmienia
  części skarbca, w wpisie źródła: części tego grafu. Bez nich widok bierze domyślne części skarbca (63-mozg.js
  MOZG_KATEGORIE), a graf z pliku części z folderów. Wpisy sprawdzone (najwyżej 12, klucz `k` z nazwy).
- **`GET /mozg/{klucz}`**: graf źródła z pliku w kształcie skarbca `{wezly, linki}`. Plik może mieć kształt skarbca
  albo `{nodes, links}` (`source/target`, `stopien`), jak dane mózgu 3D. Ścieżka pliku nie wychodzi do przeglądarki.
  Plik > 16 MB, brak pliku albo zły JSON = 404/422 w kształcie błędów aplikacji. Wynik w pamięci do zmiany mtime.
- **`GET /mozg/{klucz}/notatka?id=<id>`**: pełna treść notatki (Markdown bez frontmattera) ze źródła, które ma
  `"notatki": "<katalog z plikami <id>.md>"` (wtedy wpis dostaje `tresc: true`; katalog nie wychodzi do przeglądarki,
  identyfikator nie wyjdzie poza niego). `"rozmowca": "s:gpu"` = kto prowadzi te notatki: „Edytuj” w Mózgu otwiera
  jego rozmowę ze szkicem prośby o zmianę.
- Adresy (`notatka_url`, `widok_3d`) tylko http(s); `notatka_url` z `{id}` (identyfikator notatki, kodowany w URL).
- Odczyt tylko z karty panelu (`Sec-Fetch-Site` same-origin/none), jak trasy rozmów.
Testy: tests/test_mozg_zrodla.py.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Callable



GRAF_MAKS = 16 * 1024 * 1024
KLUCZ = re.compile(r"^[a-z0-9-]{1,40}$")
NOTATKA_MAKS = 2 * 1024 * 1024
ROZMOWCA = re.compile(r"^s:[a-z0-9_-]{1,40}$")
ODCZYT_ZRODLA = ("same-origin", "none")
SKARBIEC = {"klucz": "jarvo", "nazwa": "Skarbiec Jarva", "nazwa_en": "Jarvo's vault", "rodzaj": "skarbiec"}
_POLA_WEZLA = ("tytul", "krotki", "folder", "typ", "status", "zmieniono", "opis")
IKONA = re.compile(r"^[a-z]{1,16}$")


def _czytaj(plik: Path):
    try:
        return json.loads(Path(plik).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def kategorie(lista) -> list[dict]:
    """Części Mózgu z konfiguracji: tylko poprawne wpisy (nazwa i lista folderów pierwszego poziomu), najwyżej 12,
    klucz `k` z nazwy. Zły kształt = [] (widok bierze swoje domyślne)."""
    wynik, zajete = [], set()
    for d in lista if isinstance(lista, list) else []:
        if not isinstance(d, dict) or not str(d.get("nazwa") or "").strip() or not isinstance(d.get("foldery"), list):
            continue
        nazwa = str(d["nazwa"]).strip()[:40]
        w = {"k": _klucz(nazwa, zajete), "nazwa": nazwa,
             "foldery": [f for f in d["foldery"] if isinstance(f, str) and "/" not in f and len(f) <= 60][:20]}
        zajete.add(w["k"])
        for pole, ile in (("nazwa_en", 40), ("opis", 160), ("opis_en", 160)):
            if isinstance(d.get(pole), str) and d[pole].strip():
                w[pole] = d[pole].strip()[:ile]
        if isinstance(d.get("ikona"), str) and IKONA.match(d["ikona"]):
            w["ikona"] = d["ikona"]
        if d.get("drugorzedna") is True:
            w["drugorzedna"] = True
        wynik.append(w)
        if len(wynik) == 12:
            break
    return wynik


def _blad(status: int, kod: str, pl: str, en: str):
    from fastapi.responses import JSONResponse
    return JSONResponse({"blad": {"kod": kod, "komunikat": pl, "komunikat_en": en}}, status_code=status)


def _adres(u) -> str:
    u = str(u or "").strip()
    return u if re.match(r"^https?://[^\s\"'<>]+$", u) else ""


def _start(u: str) -> str:
    """Strona główna serwisu notatek (domyślny „Widok 3D ↗”): https://host:port/."""
    m = re.match(r"^https?://[^/]+", u)
    return m.group(0) + "/" if m else ""


def _klucz(nazwa: str, zajete: set[str]) -> str:
    baza = re.sub(r"[^a-z0-9]+", "-", nazwa.lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))).strip("-")[:32] or "zrodlo"
    k, i = baza, 2
    while k in zajete or k in ("jarvo", "zrodla"):
        k, i = f"{baza}-{i}", i + 1
    return k


def wczytaj_konfig(plik: Path) -> list[dict]:
    """Wpisy konfiguracji z kluczami (bez ścieżki dla przeglądarki: pole `graf` zostaje po stronie serwera)."""
    dane = _czytaj(plik)
    if isinstance(dane, dict):
        dane = dane.get("zrodla") if isinstance(dane.get("zrodla"), list) else [dane]
    wynik, zajete = [], set()
    for w in dane if isinstance(dane, list) else []:
        if not isinstance(w, dict) or not str(w.get("graf") or "").strip() or not str(w.get("nazwa") or "").strip():
            continue
        nazwa = str(w["nazwa"]).strip()[:60]
        k = str(w.get("klucz") or "")
        k = k if KLUCZ.match(k) and k not in zajete and k not in ("jarvo", "zrodla") else _klucz(nazwa, zajete)
        zajete.add(k)
        notatka = _adres(w.get("notatka_url"))
        rozmowca = str(w.get("rozmowca") or "").strip()
        wpis = {"klucz": k, "nazwa": nazwa, "nazwa_en": str(w.get("nazwa_en") or nazwa).strip()[:60], "rodzaj": "plik",
                "notatka_url": notatka if "{id}" in notatka else "",
                "widok_3d": _adres(w.get("widok_3d")) or _start(notatka), "_graf": Path(str(w["graf"])).expanduser()}
        if str(w.get("notatki") or "").strip():
            wpis["_notatki"], wpis["tresc"] = Path(str(w["notatki"])).expanduser(), True
        if ROZMOWCA.match(rozmowca):
            wpis["rozmowca"] = rozmowca
        ks = kategorie(w.get("kategorie"))
        if ks:
            wpis["kategorie"] = ks
        wynik.append(wpis)
    return wynik


def normalizuj(dane) -> dict:
    """Graf z pliku → kształt skarbca {wezly: [{id, tytul, folder, hub, we, …}], linki: [{z, do, auto}]}."""
    if not isinstance(dane, dict):
        raise ValueError("graf to nie obiekt")
    wezly_we = dane.get("wezly") if isinstance(dane.get("wezly"), list) else dane.get("nodes")
    linki_we = dane.get("linki") if isinstance(dane.get("linki"), list) else dane.get("links")
    if not isinstance(wezly_we, list):
        raise ValueError("brak węzłów")
    wezly, ids = [], set()
    for n in wezly_we:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not n["id"] or n["id"] in ids:
            continue
        ids.add(n["id"])
        w = {"id": n["id"][:300], "hub": bool(n.get("hub"))}
        for p in _POLA_WEZLA:
            if isinstance(n.get(p), str):
                w[p] = n[p][:400]
        w.setdefault("tytul", w["id"].rsplit("/", 1)[-1])
        w.setdefault("folder", w["id"].split("/", 1)[0] if "/" in w["id"] else "")
        st = n.get("we", n.get("stopien"))
        if isinstance(st, (int, float)) and not isinstance(st, bool):
            w["we"] = max(0, int(st))
        wezly.append(w)
    linki = []
    for link in linki_we if isinstance(linki_we, list) else []:
        if not isinstance(link, dict):
            continue
        z, do = link.get("z", link.get("source")), link.get("do", link.get("target"))
        z = z.get("id") if isinstance(z, dict) else z
        do = do.get("id") if isinstance(do, dict) else do
        if z in ids and do in ids and z != do:
            linki.append({"z": z, "do": do, "auto": bool(link.get("auto"))})
    return {"wezly": wezly, "linki": linki}


class Zrodla:
    def __init__(self, konfig: Path):
        self.konfig = Path(konfig)
        self._pamiec: dict[str, tuple[tuple, dict]] = {}

    def lista(self) -> list[dict]:
        dane = _czytaj(self.konfig)
        ks = kategorie(dane.get("kategorie")) if isinstance(dane, dict) else []
        return [{**SKARBIEC, "kategorie": ks} if ks else SKARBIEC] + [{k: v for k, v in w.items() if not k.startswith("_")}
                                                                        for w in wczytaj_konfig(self.konfig)]

    def graf(self, klucz: str) -> dict | None:
        """Graf źródła z pliku; None = nie ma takiego źródła albo pliku. ValueError = zły plik."""
        wpis = next((w for w in wczytaj_konfig(self.konfig) if w["klucz"] == klucz), None)
        if wpis is None:
            return None
        p = wpis["_graf"]
        try:
            st = p.stat()
        except OSError:
            return None
        if not p.is_file():
            return None
        if st.st_size > GRAF_MAKS:
            raise ValueError("za duży plik grafu")
        znak = (str(p), st.st_mtime_ns, st.st_size)
        z = self._pamiec.get(klucz)
        if z and z[0] == znak:
            return z[1]
        graf = normalizuj(json.loads(p.read_text(encoding="utf-8")))
        self._pamiec[klucz] = (znak, graf)
        return graf

    def notatka(self, klucz: str, nid: str) -> dict | None:
        """Pełna treść notatki źródła z katalogiem `notatki` (`<katalog>/<id>.md`, bez frontmattera); None = nie ma
        źródła, katalogu albo pliku. Identyfikator nie wychodzi poza katalog (`..`, ścieżka bezwzględna, dowiązanie)."""
        wpis = next((w for w in wczytaj_konfig(self.konfig) if w["klucz"] == klucz), None)
        if wpis is None or "_notatki" not in wpis or not nid or len(nid) > 300 or nid.startswith("/") or "\\" in nid \
                or any(c in ("", ".", "..") for c in nid.split("/")):
            return None
        try:
            kat = wpis["_notatki"].resolve()
            p = (kat / f"{nid}.md").resolve()
            if not p.is_relative_to(kat) or not p.is_file() or p.stat().st_size > NOTATKA_MAKS:
                return None
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if t.startswith("---\n"):
            koniec = t.find("\n---\n", 4)
            t = t[koniec + 5:] if koniec >= 0 else t
        return {"id": nid, "tresc": t}


def dolacz(router, *, konfig: Path, log: Callable[[str], None] | None = None) -> Zrodla:
    # import tutaj (bez `from __future__ import annotations`): adnotacja trasy to klasa z FastAPI w chwili
    # rejestracji, a funkcje czyste działają i bez FastAPI
    from fastapi import Request

    log = log or (lambda _m: None)
    zrodla = Zrodla(konfig)

    def obca(request) -> bool:
        skad = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if skad and skad not in ODCZYT_ZRODLA:
            log(f"jarvo-hq: odczyt odrzucony GET {request.url.path} (sec-fetch-site={skad[:20]})")
            return True
        return False

    def csrf():
        return _blad(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                     "Read refused: the request did not come from the Jarvo dashboard.")

    @router.get("/mozg/zrodla")
    async def mozg_zrodla(request: Request):
        if obca(request):
            return csrf()
        return {"zrodla": await asyncio.to_thread(zrodla.lista)}

    @router.get("/mozg/{klucz}")
    async def mozg_graf(klucz: str, request: Request):
        if obca(request):
            return csrf()
        if not KLUCZ.match(klucz or ""):
            return _blad(404, "brak", "Nie ma takiego źródła.", "No such source.")
        try:
            graf = await asyncio.to_thread(zrodla.graf, klucz)
        except (OSError, ValueError) as e:
            log(f"jarvo-hq: mózg {klucz}: zły plik grafu ({type(e).__name__})")
            return _blad(422, "zly_graf", "Plik grafu jest uszkodzony albo za duży.", "The graph file is broken or too large.")
        if graf is None:
            return _blad(404, "brak", "Nie ma takiego źródła albo jego pliku.", "No such source or its file is missing.")
        return graf

    @router.get("/mozg/{klucz}/notatka")
    async def mozg_notatka(klucz: str, request: Request, id: str = ""):
        if obca(request):
            return csrf()
        n = await asyncio.to_thread(zrodla.notatka, klucz, id) if KLUCZ.match(klucz or "") else None
        if n is None:
            return _blad(404, "brak", "Nie ma takiej notatki.", "No such note.")
        return n

    return zrodla
