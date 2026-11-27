"""Ścieżki Komputera Jarva: zapamiętane przepływy na stronach (cache przepływów, docs/KOMPUTER.md §7).

Agent raz przechodzi ścieżkę (logowanie, wyszukanie z filtrem, ulubione, formularz) narzędziem `komputer`, a wtyczka
nagrywa w pamięci rozmowy każdy udany krok (`idz`, krok paczki `kroki` z paragonem ok, `czekaj`). `zapisz_sciezke`
zapisuje odcinek nagrania jako ścieżkę agenta (domena, nazwa celu, parametry), a `odtworz` przechodzi ją od nowa
paczkami run_steps, bez modelu na każdym kroku, tą samą drogą co `kroki`, więc twarde zasady Komputera oceniają
każdy krok tak samo (płatność bez zgody zatrzymuje).

Zapis kroku:
  - cel numerem z `patrz` (`element_index`) zamienia się na cel napisem i rolą z tej migawki (numery nie przeżywają
    strony); krok bez napisu celu nie da się zapisać,
  - wartości parametrów (`{"fraza": "telefon"}`) zastępują znaczniki `{fraza}` w pisanym tekście, wartościach pól,
    napisach celów i adresach (w adresie też postać z `+` i `%20`, a `{fraza|-}`: spacje jako `-`, jak w ścieżkach
    adresów sklepów),
  - tekst wpisany w pole hasła, PIN-u, kodu (SMS, 2FA, BLIK) albo tekst wyglądający na klucz nigdy nie trafia do
    pliku ani do nagrania: zamiast niego znacznik `{haslo}` albo `{kod}` z `tajny: true` (odwołanie: parametr przy
    odtworzeniu albo menedżer haseł przeglądarki, gdzie zostaje hasło); z adresów wypadają parametry typu token,
    sesja, kod i podpis,
  - po kroku, który zmienił adres, wzór adresu (`po`: host i ścieżka, liczby i parametry jako `*`): przy odtworzeniu
    następny krok czeka na ten adres (wait_for), więc „strona po kroku pasuje” sprawdza sterownik,
  - klik w baner zgody albo okno („Akceptuję”, „Odrzuć”, „Zamknij”) jest opcjonalny: przy odtworzeniu krótka próba,
    a brak banera (zgoda zapamiętana) nie psuje ścieżki.

Odtworzenie: kroki opcjonalne osobno (stop_on: refusal), reszta paczkami do MAKS_PACZKA z celem napisem szukanym do
CZAS_CELU ms i weryfikacją adresu po kroku oraz `sprawdz` (tekst na końcu). Krok, który nie pasuje (brak celu, kilka
celów, adres po kroku inny), kończy odtworzenie z widokiem strony: samonaprawa to krok agenta (`kroki`), potem
`odtworz` z `od`, a ścieżka zapisuje się poprawiona (prefiks, kroki agenta, reszta). Odmowa zasad kończy odtworzenie
z radą zasad i bez naprawy. Odmowę `element_zmieniony` (strona dorysowała reklamę między celem a działaniem) odtworzenie
ponawia od tego kroku do PONOWIENIA razy.

Skrót (jak „saved flows” agent-browsera: najpierw sam adres): gdy ścieżka kończy się pod adresem, który niesie
wszystkie parametry (wyniki wyszukania z filtrem), każdy klik zmienia adres, nic nie jest tajne i jest `sprawdz`,
odtworzenie bez `od` idzie od razu pod ten adres i czeka na `sprawdz`; strona pod skrótem inna → cała ścieżka.

Plik: `<HERMES_HOME>/sciezki-komputera.json` (dane profilu agenta), zapis atomowy.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote, quote_plus, unquote_plus, urlencode, urlsplit, urlunsplit

PLIK = "sciezki-komputera.json"
WERSJA = 1
MAKS_NAGRANIE = 60               # kroków nagrania rozmowy w pamięci
MAKS_KROKOW = 60                 # kroków jednej ścieżki
MAKS_SCIEZEK = 200               # ścieżek agenta
MAKS_PACZKA = 20                 # kroków w jednym run_steps (sterownik: MAKS_KROKOW)
CZAS_CELU = 8000                 # ms: krok z celem napisem szuka celu przy odtworzeniu (strona może wolniej wstać)
CZAS_OPCJI = 1500                # ms: krok opcjonalny (baner, którego może już nie być)
CZAS_PO = 15000                  # ms: czekanie na adres po kroku i na tekst `sprawdz`
PONOWIENIA = 5                   # odmów `element_zmieniony` (strona dorysowała reklamę) ponawianych w jednym odtworzeniu
PRZERWA_PONOWIENIA = 0.4         # s × numer ponowienia: przerwa, zanim krok pójdzie jeszcze raz
NAZWA = re.compile(r"^[\w][\w .,:/+()-]{1,59}$")
ZNACZNIK = re.compile(r"\{([a-z_][a-z0-9_]{0,30})(\|-)?\}")
NAZWA_PARAMU = re.compile(r"^[a-z_][a-z0-9_]{0,30}$")
POLE_TAJNE = re.compile(r"hasł|hasl|password|passw|\bpass\b|\bpin\b|\bkod|code|otp|2fa|\bsms|cvv|cvc|blik|token|"
                        r"sekret|secret|weryfikac|verif", re.I)
POLE_HASLA = re.compile(r"hasł|hasl|password|passw|\bpass\b", re.I)
ROLE_TAJNE = frozenset({"password text"})
SEKRET_TEKST = re.compile(
    r"sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY|(?<![\d])(?:\d[ -]?){12,18}\d(?![\d])")
DLUGI_TOKEN = re.compile(r"[A-Za-z0-9]{32,}")
PARAMY_TAJNE = re.compile(r"token|sess|^sid$|auth|key|^code$|kod|sig|password|passwd|hasl|otp|ticket|nonce|csrf|jwt|"
                          r"secret|^state$|access|refresh", re.I)
BANER = re.compile(r"^(?:akceptuj\w*|zaakceptuj\w*|zgadzam\w*|zgoda|accept\w*|agree|allow\w*|zezwól\w*|ok, rozumiem|"
                   r"rozumiem|odrzuć\w*|odrzucam|reject\w*|decline|tylko niezbędne|only necessary|zamknij|close|"
                   r"nie teraz|później|not now|nie, dziękuję|no thanks|x|×|✕)(?!\w)", re.I)
BANER_SLOWA = re.compile(r"cookie|ciasteczk|plików cookie|zgod", re.I)
OBCE = ("pid", "window_id", "session", "snapshot_id", "element_token", "delivery_mode")
NUMERY = ("element_index", "from_element", "to_element")
ALIASY = {"type": "type_text", "key": "press_key", "press": "press_key", "keypress": "press_key", "set": "set_value",
          "goto": "navigate"}

_LOCK = threading.Lock()


class BladSciezki(ValueError):
    pass


# ---------------------------------------------------------------------- plik ścieżek agenta

def plik() -> Path:
    dom = os.environ.get("HERMES_HOME", "").strip()
    return (Path(dom) if dom else Path.home() / ".hermes") / PLIK


def wczytaj(p: Optional[Path] = None) -> Dict[str, Any]:
    p = p or plik()
    try:
        dane = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sc = dane.get("sciezki") if isinstance(dane, dict) else None
    return {k: v for k, v in sc.items() if isinstance(v, dict)} if isinstance(sc, dict) else {}


def zmien(fn: Callable[[Dict[str, Any]], Any], p: Optional[Path] = None) -> Any:
    """Odczyt, zmiana `fn(sciezki)` i zapis atomowy (plik tymczasowy obok i os.replace)."""
    p = p or plik()
    with _LOCK:
        sciezki = wczytaj(p)
        wynik = fn(sciezki)
        sprawdz_bez_sekretow(sciezki)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({"wersja": WERSJA, "sciezki": sciezki}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, p)
        return wynik


def sprawdz_bez_sekretow(obj: Any) -> None:
    """BladSciezki, gdy w czymkolwiek do zapisu jest coś jak klucz, token albo numer karty."""
    for s in _napisy(obj):
        if SEKRET_TEKST.search(s) or any(_wyglada_na_token(t) for t in DLUGI_TOKEN.findall(s)):
            raise BladSciezki("w ścieżce jest coś jak klucz, token albo numer karty; tego nie zapisuję (pole hasła "
                              "i kodu zostaje parametrem tajnym)")


def _napisy(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _napisy(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _napisy(v)


def _wyglada_na_token(t: str) -> bool:
    return any(c.isdigit() for c in t) and any(c.isalpha() for c in t)


# ---------------------------------------------------------------------- adresy

def domena(url: str) -> str:
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def czysty_adres(url: str) -> str:
    """Adres bez parametrów i fragmentu, które wyglądają na token, sesję, kod albo podpis."""
    try:
        cz = urlsplit(str(url or ""))
    except ValueError:
        return ""
    query = [(k, v) for k, v in parse_qsl(cz.query, keep_blank_values=True) if not PARAMY_TAJNE.search(k)]
    frag = "" if "=" in cz.fragment or DLUGI_TOKEN.search(cz.fragment) else cz.fragment
    return urlunsplit((cz.scheme, cz.netloc, cz.path, urlencode(query, safe="[]:,") if query else "", frag))


def _odmiany(wartosc: str) -> List[Tuple[str, str]]:
    """(postać wartości w adresie, filtr znacznika) od najdłuższej: zwykła, +, %20, -."""
    w = [(wartosc, ""), (quote_plus(wartosc), ""), (quote(wartosc, safe=""), "")]
    if " " in wartosc:
        w.append((wartosc.replace(" ", "-"), "|-"))
    wynik, byly = [], set()
    for postac, f in sorted(w, key=lambda x: -len(x[0])):
        if postac and postac.lower() not in byly:
            byly.add(postac.lower())
            wynik.append((postac, f))
    return wynik


def _granica(postac: str) -> str:
    """Wartość jako całość: nie fragment słowa, liczby ani znacznika `{nazwa}`."""
    znaki = "0-9A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ_{}|"
    return rf"(?<![{znaki}]){re.escape(postac)}(?![{znaki}])"


def wzor_po(url: str, wartosci: Dict[str, str]) -> str:
    """Wzór adresu po kroku dla wait_for: `*host/ścieżka*`, liczby i wartości parametrów jako `*`, bez zapytania."""
    try:
        cz = urlsplit(str(url or ""))
    except ValueError:
        return ""
    if not cz.hostname:
        return ""
    sciezka = cz.path or "/"                      # jak w adresie karty: znaki spoza ASCII zakodowane (%C5%BC)
    for wartosc in sorted((v for v in wartosci.values() if v), key=len, reverse=True):
        for postac, _ in _odmiany(wartosc) + [(unquote_plus(wartosc), "")]:
            sciezka = re.sub(_granica(postac), "*", sciezka, flags=re.I)
    sciezka = re.sub(r"\d+", "*", sciezka)
    sciezka = re.sub(r"[\[\]?]", "*", sciezka)
    host = cz.hostname[4:] if cz.hostname.startswith("www.") else cz.hostname
    return re.sub(r"\*+", "*", f"*{host}{sciezka}*")


# ---------------------------------------------------------------------- krok: normalizacja, szablon, wypełnienie

def rozbierz(krok: Any) -> Tuple[Optional[str], Dict[str, Any], Dict[str, Any]]:
    """(narzędzie albo None dla samego wait_for, argumenty, pola kroku wait_for/timeout_ms)."""
    if not isinstance(krok, dict):
        raise BladSciezki("krok to obiekt {<narzędzie>: args}")
    pola = {k: krok[k] for k in ("wait_for", "timeout_ms") if k in krok}
    akcje = [k for k in krok if k not in ("tool", "args", "wait_for", "timeout_ms")]
    if "tool" in krok and not akcje:
        nazwa, a = krok["tool"], krok.get("args", {})
    elif len(akcje) == 1 and "tool" not in krok:
        nazwa, a = akcje[0], krok[akcje[0]]
    elif not akcje and "wait_for" in krok:
        return None, {}, pola
    else:
        raise BladSciezki("jeden krok to jedno działanie {<narzędzie>: args}")
    if not isinstance(nazwa, str) or not isinstance(a, dict):
        raise BladSciezki("krok to obiekt {<narzędzie>: args}")
    nazwa = ALIASY.get(nazwa, nazwa)
    if nazwa == "wait_for":
        return None, {}, {**pola, "wait_for": a}
    return nazwa, dict(a), pola


def zloz(nazwa: Optional[str], a: Dict[str, Any], pola: Dict[str, Any]) -> Dict[str, Any]:
    return {**({nazwa: a} if nazwa else {}), **pola}


def cel_kroku(nazwa: Optional[str], a: Dict[str, Any]) -> str:
    """Napis celu kroku (cel napisem), pusty bez celu."""
    if nazwa == "type_text":
        return str(a.get("name") or "")
    return str(a.get("name") or a.get("text") or "")


def opcjonalny(nazwa: Optional[str], napis: str, w_dialogu: bool = False) -> bool:
    """Klik w baner zgody albo okno: „Akceptuję”, „Odrzuć wszystkie”, „Zamknij”, przyciski z cookie/zgodą."""
    if nazwa != "click" or not napis:
        return False
    napis = " ".join(napis.split())
    return bool(BANER.match(napis) and (len(napis) <= 40 or BANER_SLOWA.search(napis))) or \
        bool(BANER_SLOWA.search(napis) and len(napis) <= 60) or (w_dialogu and len(napis) <= 25 and bool(BANER.match(napis)))


def wpis_kroku(krok: Dict[str, Any], cel: Optional[Dict[str, Any]], adres_przed: str,
               adres_po: str = "") -> Dict[str, Any]:
    """Wpis nagrania z kroku paczki, który się udał: bez pól sesji, cel numerem zamieniony na napis z `cel`
    (rola i napis z migawki albo z paragonu), tekst pola tajnego jako znacznik. `uwaga: numer` = cel bez napisu."""
    nazwa, a, pola = rozbierz(krok)
    for k in OBCE:
        a.pop(k, None)
    uwaga = ""
    if any(a.get(k) is not None for k in NUMERY):
        napis = str((cel or {}).get("label") or "").strip()
        if napis and a.get("element_index") is not None and not any(a.get(k) is not None for k in NUMERY[1:]):
            a.pop("element_index")
            a["name" if nazwa == "type_text" else "text"] = " ".join(napis.split())[:300]
            if (cel or {}).get("role"):
                a["role"] = cel["role"]
        else:
            uwaga = "numer"
    elif a.get("x") is not None or a.get("y") is not None:
        uwaga = "punkt"
    rola = str((cel or {}).get("role") or a.get("role") or "")
    napis_celu = " ".join(str((cel or {}).get("label") or cel_kroku(nazwa, a)).split())
    tajny = ""
    if nazwa in ("type_text", "set_value"):
        pole = "text" if nazwa == "type_text" else "value"
        tekst = str(a.get(pole) or "")
        if rola in ROLE_TAJNE or POLE_HASLA.search(napis_celu):
            tajny = "haslo"
        elif POLE_TAJNE.search(napis_celu) or SEKRET_TEKST.search(tekst) or any(
                _wyglada_na_token(t) for t in DLUGI_TOKEN.findall(tekst)):
            tajny = "kod"
        if tajny and tekst and not ZNACZNIK.fullmatch(tekst.rstrip("\n")):
            a[pole] = "{" + tajny + "}" + ("\n" if tekst.endswith("\n") else "")
    if nazwa == "navigate":
        a["url"] = czysty_adres(str(a.get("url") or ""))
    wpis: Dict[str, Any] = {"krok": zloz(nazwa, a, pola), "adres_przed": adres_przed,
                            "domena": domena(adres_przed)}
    if nazwa == "navigate":
        wpis["domena"] = domena(a["url"]) or wpis["domena"]
    if adres_po:
        wpis["po_adres"] = czysty_adres(adres_po)
    if opcjonalny(nazwa, napis_celu, rola in ("dialog", "alert")):
        wpis["opcjonalny"] = True
    if uwaga:
        wpis["uwaga"] = uwaga
    if tajny:
        wpis["tajne"] = [tajny]
    return wpis


def _zastap(s: str, wartosci: Dict[str, str], adres: bool) -> str:
    """Wartości parametrów → znaczniki. W adresie tylko ścieżka i zapytanie (host zostaje): w ścieżce znacznik
    `{x|-}` (spacje jako `-`, jak w adresach sklepów), w zapytaniu `{x}` (spacje jako `+`)."""
    poczatek, sciezka, reszta = "", "", s
    if adres:
        m = re.match(r"^([a-z][a-z0-9+.-]*://[^/?#]*)?([^?#]*)(.*)$", s, re.I | re.S)
        poczatek, sciezka, reszta = m.group(1) or "", m.group(2), m.group(3)
    for nazwa, wartosc in sorted(wartosci.items(), key=lambda x: -len(x[1] or "")):
        if not wartosc:
            continue
        if adres:
            for postac, f in _odmiany(wartosc):
                f_sciezki = f if " " in wartosc else "|-"
                sciezka = re.sub(_granica(postac), "{" + nazwa + f_sciezki + "}", sciezka, flags=re.I)
                reszta = re.sub(_granica(postac), "{" + nazwa + "}", reszta, flags=re.I)
        elif reszta.rstrip("\n") == wartosc:
            reszta = "{" + nazwa + "}" + reszta[len(wartosc):]
        else:
            reszta = re.sub(_granica(wartosc), "{" + nazwa + "}", reszta)
    return poczatek + sciezka + reszta


def szablon(krok: Dict[str, Any], wartosci: Dict[str, str]) -> Dict[str, Any]:
    """Krok z wartościami parametrów zamienionymi na znaczniki (role, klawisze i kierunki bez zmian)."""
    nazwa, a, pola = rozbierz(krok)
    for k, v in list(a.items()):
        if isinstance(v, str) and k in ("text", "name", "value", "url"):
            a[k] = _zastap(v, wartosci, adres=(k == "url"))
    if isinstance(pola.get("wait_for"), dict):
        w = dict(pola["wait_for"])
        for k in ("text", "url"):
            if isinstance(w.get(k), str):
                w[k] = _zastap(w[k], wartosci, adres=(k == "url"))
        pola["wait_for"] = w
    return zloz(nazwa, a, pola)


class BrakParametru(BladSciezki):
    def __init__(self, nazwa: str, tajny: bool):
        super().__init__(nazwa)
        self.nazwa, self.tajny = nazwa, tajny


def _wypelnij_napis(s: str, wartosci: Dict[str, str], tajne: set, adres: bool, zostaw_tajne: bool) -> str:
    def zamien(m: re.Match) -> str:
        nazwa, myslnik = m.group(1), m.group(2)
        if nazwa in tajne and zostaw_tajne:
            return m.group(0)
        if nazwa not in wartosci:
            raise BrakParametru(nazwa, nazwa in tajne)
        w = str(wartosci[nazwa])
        if myslnik:
            w = w.replace(" ", "-")
        return (quote(w, safe="-") if myslnik else quote_plus(w)) if adres else w
    return ZNACZNIK.sub(zamien, s)


def wypelnij(krok: Dict[str, Any], wartosci: Dict[str, str], tajne: set = frozenset(),
             zostaw_tajne: bool = False) -> Dict[str, Any]:
    """Krok ze znacznikami zastąpionymi wartościami (w adresie zakodowanymi); BrakParametru bez wartości.
    `zostaw_tajne`: znaczniki tajne zostają (do nagrania, które nie trzyma haseł)."""
    nazwa, a, pola = rozbierz(krok)
    for k, v in list(a.items()):
        if isinstance(v, str):
            a[k] = _wypelnij_napis(v, wartosci, tajne, k == "url", zostaw_tajne)
    if isinstance(pola.get("wait_for"), dict):
        w = dict(pola["wait_for"])
        for k in ("text", "url"):
            if isinstance(w.get(k), str):
                w[k] = _wypelnij_napis(w[k], wartosci, tajne, k == "url", zostaw_tajne)
        pola["wait_for"] = w
    return zloz(nazwa, a, pola)


def znaczniki(obj: Any) -> set:
    return {m.group(1) for s in _napisy(obj) for m in ZNACZNIK.finditer(s)}


def opis_kroku(krok: Dict[str, Any]) -> str:
    """Krótki opis kroku dla modelu: `klik „Szukaj” (push button)`, `pisz „{fraza}” w „Czego szukasz?”`."""
    try:
        nazwa, a, pola = rozbierz(krok)
    except BladSciezki:
        return json.dumps(krok, ensure_ascii=False)[:120]
    cel = cel_kroku(nazwa, a)
    rola = f" ({a['role']})" if a.get("role") else ""
    if nazwa == "navigate":
        t = f"idź {a.get('url')}"
    elif nazwa is None:
        w = pola.get("wait_for") or {}
        t = f"czekaj na {'adres ' + str(w.get('url')) if w.get('url') else '„' + str(w.get('text')) + '”'}"
    elif nazwa == "type_text":
        t = f"pisz „{str(a.get('text') or '').rstrip(chr(10))}”{' + Enter' if str(a.get('text') or '').endswith(chr(10)) else ''}" \
            + (f" w „{cel}”{rola}" if cel else "")
    elif nazwa == "set_value":
        t = f"ustaw „{a.get('value')}” w „{cel}”{rola}"
    elif nazwa == "press_key":
        t = f"klawisz {a.get('key')}"
    elif nazwa == "scroll":
        t = f"przewiń {a.get('direction')} {a.get('amount') or ''}".strip()
    else:
        t = f"{ {'click': 'klik', 'double_click': 'dwuklik', 'right_click': 'prawy klik'}.get(nazwa, nazwa)} " \
            + (f"„{cel}”{rola}" if cel else json.dumps({k: v for k, v in a.items() if k != 'role'}, ensure_ascii=False))
    return t[:160]


# ---------------------------------------------------------------------- zapis ścieżki

def odcinek(nagranie: List[Dict[str, Any]], od: Optional[int] = None) -> List[Dict[str, Any]]:
    """Odcinek nagrania do zapisu: od wpisu `od` (1…), a bez niego ciągła praca na domenie ostatniego wpisu."""
    if not nagranie:
        return []
    if od is not None:
        if not 1 <= od <= len(nagranie):
            raise BladSciezki(f"`od`: numer wpisu nagrania 1–{len(nagranie)} (lista w akcja=sciezki)")
        return nagranie[od - 1:]
    d = nagranie[-1].get("domena") or ""
    start = len(nagranie) - 1
    while start > 0 and (nagranie[start - 1].get("domena") or d) == d:
        start -= 1
    return nagranie[start:]


def kroki_sciezki(wpisy: List[Dict[str, Any]], wartosci: Dict[str, str], start: bool = True) -> List[Dict[str, Any]]:
    """Kroki ścieżki z wpisów nagrania: zaczyna od przejścia pod adres (`start`; bez niego środek ścieżki, np. kroki
    samonaprawy), parametry jako znaczniki, wzory adresów po kroku (`po` z odtworzenia zostaje)."""
    if not wpisy and start:
        raise BladSciezki("brak nagranych kroków: najpierw przejdź ścieżkę (idz, kroki), potem zapisz")
    zle = [i + 1 for i, w in enumerate(wpisy) if w.get("uwaga") == "numer"]
    if zle:
        raise BladSciezki(f"kroki {', '.join(map(str, zle))} miały cel numerem bez napisu; zrób je celem napisem "
                          "(albo pomiń przez `od`) i zapisz jeszcze raz")
    kroki: List[Dict[str, Any]] = []
    if start and rozbierz(wpisy[0]["krok"])[0] != "navigate":
        poczatek = czysty_adres(str(wpisy[0].get("adres_przed") or ""))
        if not poczatek.startswith(("http://", "https://")):
            raise BladSciezki("nie wiem, z jakiej strony zaczyna się ścieżka: zacznij od `idz`")
        kroki.append({"krok": szablon({"navigate": {"url": poczatek}}, wartosci)})
    for n, w in enumerate(wpisy):
        if rozbierz(w["krok"])[0] == "navigate" and n + 1 < len(wpisy) and \
                rozbierz(wpisy[n + 1]["krok"])[0] == "navigate":
            continue                              # przejście, po którym od razu jest następne, nic nie wnosi
        k: Dict[str, Any] = {"krok": szablon(w["krok"], wartosci)}
        if w.get("po"):
            k["po"] = w["po"]
        elif w.get("po_adres"):
            po = wzor_po(w["po_adres"], wartosci)
            if po:
                k["po"] = po
        if w.get("opcjonalny"):
            k["opcjonalny"] = True
        if w.get("uwaga") == "punkt":
            k["uwaga"] = "punkt"
        kroki.append(k)
    if len(kroki) > MAKS_KROKOW:
        raise BladSciezki(f"ścieżka ma {len(kroki)} kroków, najwyżej {MAKS_KROKOW}: zapisz krótszy odcinek (`od`)")
    return kroki


def skrot(wpisy: List[Dict[str, Any]], wartosci: Dict[str, str]) -> str:
    """Adres, pod którym kończy się ścieżka (jak „saved flows” agent-browsera: najpierw sam adres), ze znacznikami,
    albo pusty. Tylko gdy wszystkie parametry są w tym adresie, ścieżka nie wpisuje nic tajnego, a każdy klik zmienia
    adres (klik bez zmiany adresu, np. „Dodaj do ulubionych”, zmienia stan strony, którego adres nie powtórzy) i po
    ostatniej zmianie adresu nie ma już działań."""
    ostatni = None
    for n, w in enumerate(wpisy):
        nazwa = rozbierz(w["krok"])[0]
        if w.get("tajne") or w.get("uwaga") or "po" in w and "po_adres" not in w:
            return ""
        if nazwa in ("click", "double_click", "right_click", "drag", "hotkey") and not w.get("opcjonalny") \
                and not w.get("po_adres"):
            return ""
        if w.get("po_adres") and nazwa is not None:
            ostatni = n
    if ostatni is None or any(rozbierz(w["krok"])[0] is not None for w in wpisy[ostatni + 1:]):
        return ""
    adres = _zastap(czysty_adres(wpisy[ostatni]["po_adres"]), wartosci, adres=True)
    if not adres.startswith(("http://", "https://")) or any(v and n not in znaczniki(adres)
                                                            for n, v in wartosci.items()):
        return ""
    return adres

def nowa_sciezka(nazwa: str, kroki: List[Dict[str, Any]], parametry: Dict[str, str], opis: str = "",
                 sprawdz: str = "", tajne: set = frozenset(), stara: Optional[Dict[str, Any]] = None,
                 skrot: str = "") -> Dict[str, Any]:
    if not NAZWA.match(nazwa or ""):
        raise BladSciezki("`nazwa`: 2–60 znaków (litery, cyfry, spacje, - _ . : /), np. „olx szukaj z ceną”")
    uzyte = znaczniki([k["krok"] for k in kroki]) | znaczniki(sprawdz)
    tajne = set(tajne) | {n for n in uzyte if POLE_TAJNE.search(n) or n in ("haslo", "kod", "sekret")}
    tajne |= {n for n, v in (stara or {}).get("parametry", {}).items() if isinstance(v, dict) and v.get("tajny")}
    params: Dict[str, Any] = {}
    for n in sorted(uzyte):
        if n in tajne:
            params[n] = {"tajny": True, "zrodlo": "parametr przy odtworzeniu albo menedżer haseł przeglądarki"}
        elif n in parametry:
            params[n] = {"przyklad": str(parametry[n])[:200]}
        elif isinstance((stara or {}).get("parametry", {}).get(n), dict):
            params[n] = stara["parametry"][n]
        else:
            params[n] = {}
    adres = rozbierz(kroki[0]["krok"])[1].get("url", "") if kroki else ""
    teraz = time.strftime("%Y-%m-%d %H:%M")
    sc = {"nazwa": nazwa, "domena": domena(adres), "opis": " ".join(str(opis or "").split())[:200],
          "parametry": params, "kroki": kroki, "utworzona": (stara or {}).get("utworzona") or teraz,
          "zmieniona": teraz, "uzycia": int((stara or {}).get("uzycia") or 0),
          "naprawy": int((stara or {}).get("naprawy") or 0)}
    if sprawdz:
        sc["sprawdz"] = " ".join(sprawdz.split())[:200]
    elif (stara or {}).get("sprawdz"):
        sc["sprawdz"] = stara["sprawdz"]
    if skrot and sc.get("sprawdz") and znaczniki(skrot) <= set(params) - tajne:
        sc["skrot"] = skrot                           # bez `sprawdz` nie ma czym sprawdzić strony pod skrótem
    sprawdz_bez_sekretow(sc)
    return sc


def zapisz(sc: Dict[str, Any], p: Optional[Path] = None) -> None:
    def fn(sciezki: Dict[str, Any]) -> None:
        if sc["nazwa"] not in sciezki and len(sciezki) >= MAKS_SCIEZEK:
            raise BladSciezki(f"masz już {MAKS_SCIEZEK} ścieżek: nadpisz starą tą samą nazwą")
        sciezki[sc["nazwa"]] = sc
    zmien(fn, p)


def opis_sciezki(sc: Dict[str, Any], z_krokami: bool = False) -> List[str]:
    params = []
    for n, v in (sc.get("parametry") or {}).items():
        v = v if isinstance(v, dict) else {}
        params.append(f"{n} (tajny)" if v.get("tajny") else f"{n}={v['przyklad']}" if v.get("przyklad") else n)
    linie = [f"„{sc.get('nazwa')}” ({sc.get('domena')}): {len(sc.get('kroki') or [])} kroków"
             + (f"; parametry: {', '.join(params)}" if params else "")
             + (f"; {sc['opis']}" if sc.get("opis") else "")
             + f"; użycia {sc.get('uzycia', 0)}, naprawy {sc.get('naprawy', 0)}, zmieniona {sc.get('zmieniona', '')}"]
    if z_krokami:
        for i, k in enumerate(sc.get("kroki") or []):
            linie.append(f"  {i + 1}. {opis_kroku(k.get('krok') or {})}" + (" (opcjonalny)" if k.get("opcjonalny") else "")
                         + (f" → adres {k['po']}" if k.get("po") else ""))
        if sc.get("sprawdz"):
            linie.append(f"  na końcu na stronie: „{sc['sprawdz']}”")
        if sc.get("skrot"):
            linie.append(f"  skrót: {sc['skrot']} (sam adres i sprawdzenie; bez `od`)")
    return linie


# ---------------------------------------------------------------------- odtworzenie

def plan(sc: Dict[str, Any], wartosci: Dict[str, str], od: int = 1) -> List[Dict[str, Any]]:
    """Paczki run_steps: [{"steps", "mapa" [(nr kroku ścieżki od 0, rodzaj: krok|po|sprawdz)], "opcja"}].
    BrakParametru przed pierwszym działaniem, jeśli brakuje wartości kroku (tajny: osobno, przy kroku, patrz niżej)."""
    kroki = sc.get("kroki") or []
    tajne = {n for n, v in (sc.get("parametry") or {}).items() if isinstance(v, dict) and v.get("tajny")}
    paczki: List[Dict[str, Any]] = []
    biezaca: Dict[str, Any] = {"steps": [], "mapa": [], "opcja": False}

    def zamknij() -> None:
        nonlocal biezaca
        if biezaca["steps"]:
            paczki.append(biezaca)
        biezaca = {"steps": [], "mapa": [], "opcja": False}

    czekaj_po = ""
    for i in range(od - 1, len(kroki)):
        wpis = kroki[i]
        krok = wypelnij(wpis["krok"], wartosci, tajne)
        nazwa, a, pola = rozbierz(krok)
        szuka = nazwa not in (None, "navigate") and bool(cel_kroku(nazwa, a))
        if wpis.get("opcjonalny"):
            zamknij()
            if szuka:
                pola["timeout_ms"] = CZAS_OPCJI
            paczki.append({"steps": [zloz(nazwa, a, pola)], "mapa": [(i, "krok")], "opcja": True})
            continue
        if szuka and "timeout_ms" not in pola:
            pola["timeout_ms"] = CZAS_CELU
        if len(biezaca["steps"]) >= MAKS_PACZKA - 1:
            zamknij()
        if czekaj_po:
            warunek = {"url": czekaj_po, "timeout_ms": CZAS_PO}
            if "wait_for" in pola:
                biezaca["steps"].append({"wait_for": warunek})
                biezaca["mapa"].append((i, "po"))
            else:
                pola["wait_for"] = warunek
        biezaca["steps"].append(zloz(nazwa, a, pola))
        biezaca["mapa"].append((i, "krok"))
        czekaj_po = str(wpis.get("po") or "")
    if len(biezaca["steps"]) >= MAKS_PACZKA - 1:
        zamknij()
    if czekaj_po:
        biezaca["steps"].append({"wait_for": {"url": czekaj_po, "timeout_ms": CZAS_PO}})
        biezaca["mapa"].append((len(kroki), "po"))
    if sc.get("sprawdz"):
        tekst = _wypelnij_napis(str(sc["sprawdz"]), wartosci, tajne, False, False)
        biezaca["steps"].append({"wait_for": {"text": tekst, "timeout_ms": CZAS_PO}})
        biezaca["mapa"].append((len(kroki), "sprawdz"))
    zamknij()
    return paczki


def odtworz(sc: Dict[str, Any], wartosci: Dict[str, str], od: int,
            run_steps: Callable[[Dict[str, Any]], Dict[str, Any]], obserwuj: Optional[Dict[str, Any]] = None,
            ze_skrotem: bool = False) -> Dict[str, Any]:
    """Przejście ścieżki paczkami przez `run_steps(args) -> wynik MCP`. Wynik: ok, wykonane (kroki ścieżki od 0,
    które poszły, z pominiętymi opcjonalnymi), stop (nr kroku ścieżki od 0, od którego agent robi sam, albo None),
    rodzaj (cel: krok nie pasuje do strony; po: adres po kroku inny; sprawdz; zasady; parametr), powod, wynik
    (ostatni wynik run_steps: obserwacja, next_step), pominiete (opcjonalne bez celu), sekundy, skrot (adres
    skrótu, gdy ścieżka przeszła nim). `ze_skrotem`: najpierw sam adres skrótu i `sprawdz`; gdy strona pod nim nie
    pasuje, cała ścieżka."""
    start = time.monotonic()
    kroki = sc.get("kroki") or []
    wynik: Dict[str, Any] = {"ok": False, "wykonane": [], "stop": None, "rodzaj": "", "powod": "",
                             "wynik": {}, "pominiete": [], "sekundy": 0.0, "paczki": 0}
    params = sc.get("parametry") or {}
    tajne = {n for n, v in params.items() if isinstance(v, dict) and v.get("tajny")}
    wartosci = {**{n: str(v["przyklad"]) for n, v in params.items() if isinstance(v, dict) and v.get("przyklad")
                   and n not in tajne}, **wartosci}
    brak = sorted(n for n in znaczniki([k["krok"] for k in kroki[od - 1:]]) | znaczniki(sc.get("sprawdz") or "")
                  if n not in wartosci and n not in tajne)
    if brak:                                          # zwykły parametr bez wartości i bez przykładu: nic nie robi
        wynik.update(stop=od - 1, rodzaj="parametr", powod=f"brak wartości parametru {', '.join(brak)}")
        wynik["wartosci"] = {}
        return wynik
    wynik["wartosci"] = {k: v for k, v in wartosci.items() if k not in tajne}
    if ze_skrotem and sc.get("skrot") and sc.get("sprawdz") and not znaczniki(sc["skrot"]) & tajne:
        adres = _wypelnij_napis(str(sc["skrot"]), wartosci, tajne, True, False)
        args: Dict[str, Any] = {"steps": [{"navigate": {"url": adres}}, {"wait_for": {
            "text": _wypelnij_napis(str(sc["sprawdz"]), wartosci, tajne, False, False), "timeout_ms": CZAS_PO}}],
            "stop_on": "error"}
        if obserwuj is not None:
            args["observe"] = obserwuj
        w = run_steps(args)
        wynik.update(paczki=1, wynik=w)
        s = w.get("structuredContent") if isinstance(w.get("structuredContent"), dict) else {}
        raporty = s.get("steps") if isinstance(s.get("steps"), list) else []
        if len(raporty) == 2 and all(r.get("ok") for r in raporty):
            wynik.update(ok=True, skrot=adres, sekundy=round(time.monotonic() - start, 2))
            return wynik
        odmowa = next((r for r in raporty if not r.get("ok") and r.get("decision")), None)
        if odmowa is not None:                        # adres skrótu zatrzymały zasady: tak samo jak krok ścieżki
            wynik.update(stop=0, rodzaj="zasady", next_step=odmowa.get("next_step"), decision=odmowa.get("decision"),
                         powod=f"BŁĄD {odmowa.get('code') or 'blad'}: {odmowa.get('message') or ''}"[:400],
                         sekundy=round(time.monotonic() - start, 2))
            return wynik
        wynik["skrot_nie"] = next((f"{r.get('code') or 'blad'}: {r.get('message') or ''}"[:200]
                                   for r in raporty if not r.get("ok")), "brak odpowiedzi")
    # tajny bez wartości (hasło z menedżera haseł albo od agenta): kroki do niego idą, on i reszta to krok agenta
    tajny_stop = next((i for i in range(od - 1, len(kroki))
                       if any(n in tajne and n not in wartosci for n in znaczniki(kroki[i]["krok"]))), None)
    koniec = len(kroki) if tajny_stop is None else tajny_stop
    sc_czesc = {**sc, "kroki": kroki[:koniec]}
    if tajny_stop is not None:
        sc_czesc.pop("sprawdz", None)
    ponowienia, biezacy_od = PONOWIENIA, od
    while koniec >= biezacy_od:
        ponow = None
        paczki = plan(sc_czesc, wartosci, biezacy_od)
        for n, p in enumerate(paczki):
            args: Dict[str, Any] = {"steps": p["steps"], "stop_on": "refusal" if p["opcja"] else "error"}
            if obserwuj is not None and (not p["opcja"] or n == len(paczki) - 1):
                args["observe"] = obserwuj
            w = run_steps(args)
            wynik["paczki"] += 1
            wynik["wynik"] = w
            s = w.get("structuredContent") if isinstance(w.get("structuredContent"), dict) else {}
            if "steps" not in s:
                wynik.update(stop=min(p["mapa"][0][0], len(kroki)), rodzaj="cel",
                             powod=f"BŁĄD {s.get('code') or 'blad'}: {s.get('message') or ''}"[:400])
                break
            for r in s["steps"]:
                j = r.get("index")
                if not isinstance(j, int) or not 0 <= j < len(p["mapa"]):
                    continue
                i, rodzaj = p["mapa"][j]
                if r.get("ok"):
                    if rodzaj == "krok":
                        wynik["wykonane"].append(i)
                    continue
                if p["opcja"] and not r.get("decision"):
                    wynik["pominiete"].append(i)
                    continue
                zmieniona = "element_zmieniony" in (r.get("rule"), r.get("code"))
                if rodzaj == "krok" and zmieniona and ponowienia > 0:
                    ponowienia -= 1                   # strona dorysowała coś (reklama) między celem a klikiem
                    ponow = i
                    break
                opis = f"BŁĄD {r.get('code') or 'blad'}: {r.get('message') or ''}"[:400]
                if r.get("decision") and not zmieniona:
                    wynik.update(rodzaj="zasady", next_step=r.get("next_step"), decision=r.get("decision"))
                elif rodzaj in ("po", "sprawdz") or r.get("phase") == "wait_for":
                    wynik["rodzaj"] = "sprawdz" if rodzaj == "sprawdz" else "po"
                else:
                    wynik["rodzaj"] = "cel"            # także strona, która nie przestaje się przestawiać
                wynik.update(powod=opis, stop=i)
                break
            if ponow is not None or wynik["stop"] is not None:
                break
        if ponow is None:
            break
        biezacy_od = ponow + 1
        time.sleep(PRZERWA_PONOWIENIA * (PONOWIENIA - ponowienia))   # strona dokończy rysowanie
    if wynik["stop"] is None:
        if tajny_stop is not None:
            brak = sorted(n for n in znaczniki(kroki[tajny_stop]["krok"]) if n in tajne and n not in wartosci)
            wynik.update(stop=tajny_stop, rodzaj="parametr",
                         powod=f"krok wpisuje wartość tajną ({', '.join(brak)}), której nie ma w parametrach")
        else:
            wynik["ok"] = True
    wynik["sekundy"] = round(time.monotonic() - start, 2)
    return wynik
