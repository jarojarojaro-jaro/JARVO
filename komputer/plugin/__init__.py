"""Wtyczka jarvo-komputer: narzędzie `komputer` dla agentów z `komputer: true` we fleet.yaml (Jarvo, docs/KOMPUTER.md §7).

Rozmawia z wejściem Komputera przez gniazdo sterowania (`ster.sock`, docs/KOMPUTER.md §6):
  stan       czy Komputer działa, pauza i jej powód, ile sesji, czy działa drzewo dostępności (AT-SPI),
  dziennik   ostatnie decyzje twardych zasad (bez treści: narzędzie, decyzja, zasada, cel),
  oddaj      prośba do właściciela: pauza z powodem („kliknij Zapłać w oknie Komputera”). Komputer stoi, dopóki
             właściciel go nie wznowi (`jarvo komputer wznow`); krok robi w oknie Komputera na pulpicie serwera
             (VNC do pulpitu serwera, Tailscale).
Wznowić agent nie może: wejście przepuszcza `wznow` tylko od właściciela (kontener: SO_PEERCRED; natywnie: token
właściciela, którego narzędzie nie zna i nie wysyła).

Strony jak telefon (natywnie, sterownik CDP; docs/KOMPUTER.md §7): wtyczka rozmawia MCP z tym samym wejściem co
computer_use, przez tę samą bramkę (`$HERMES_CUA_DRIVER_CMD mcp`), więc każde wywołanie oceniają te same twarde
zasady:
  idz        navigate: karta pod adres http(s) (zasady jak adres w pasku, potem proxy filtrujące),
  patrz      get_window_state bez zrzutu: drzewo z numerami (najpierw okna i banery), wartości pól,
  kroki      run_steps: do 20 działań w jednym wywołaniu (cel numerem z ostatniego `patrz` albo napisem);
             zasady oceniają każdy krok przed nim, paczka staje na pierwszej odmowie albo kroku właściciela;
             `obserwuj` dokłada migawkę po ostatnim kroku (z `*` przy nowych elementach),
  czekaj     wait_for: tekst, jego zniknięcie albo adres, do 30 s, liczone w sterowniku.
Ścieżki (cache przepływów, `sciezki.py` obok): każdy udany krok rozmowy (`idz`, krok `kroki`, `czekaj`) wtyczka
nagrywa w pamięci tej rozmowy, a
  sciezki          lista ścieżek agenta (domena, parametry, użycia) i nagranie tej rozmowy,
  zapisz_sciezke   zapisuje odcinek nagrania jako ścieżkę (nazwa, parametry jako znaczniki, bez haseł i kodów)
                   w `<HERMES_HOME>/sciezki-komputera.json`,
  odtworz          przechodzi ścieżkę z parametrami paczkami run_steps tą samą drogą co `kroki` (twarde zasady na
                   każdym kroku), sprawdzając cel i adres po każdym kroku; krok, który nie pasuje, oddaje agentowi
                   z widokiem strony, a po jego kroku `odtworz` z `od` kończy i zapisuje poprawioną ścieżkę.
Rozmowa trwa na sesję Hermesa (snapshot_id ostatniego `patrz` dokłada się do `kroki`) i kończy się po BEZCZYNNOSC s
bez wywołań. Ekran: każde zadanie agenta (rozmowa Hermesa, karta kanbana) ma natywnie własne okno przeglądarki,
a w kontenerze dostaje ekran jedno naraz (inne: `zajete` z tym, kto ma ekran, czasem do zwolnienia i miejscem
w kolejce). Zadanie rozpoznaje wejście po kluczu: grupa ekranu procesu (JARVO_KOMPUTER_GRUPA, klucz z PID procesu:
pracownik karty kanbana dostaje otoczenie bramy Hermesa z jej kluczem, więc tu bierze własny; 16.11 dwie karty
z kluczem bramy sterowały ekranem naraz), karta kanbana (JARVO_KOMPUTER_KARTA) i rozmowa (JARVO_KOMPUTER_ROZMOWA:
skrót id sesji Hermesa). Bramki tej wtyczki dostają rozmowę wprost, a bramki computer_use przez `zwiaz_computer_use`:
Hermes uruchamia bramkę computer_use raz na sesję w `_get_backend(session_id)`, z otoczeniem z
`cua_driver_child_env()` w wątku swojej pętli, więc wtyczka owija oba i dokłada rozmowę tej sesji (27.11 dwie
rozmowy panelu w jednym procesie bramy działały na jednej karcie: `ctrl+z` w edytorze HQ dał paragon ze strony OLX).
Bez rozmowy (Hermes bez tych funkcji) klucz jest jak dotąd: grupa i karta.

build.py kopiuje wtyczkę do plugins/jarvo-komputer, install-fleet.sh dowiązuje ją w profilach z `komputer: true`.

Natywnie (jest JARVO_ROOT, nie ma JARVO_KOMPUTER_GNIAZDO) kanał `ster` usługi Komputera liczy się z korzenia tym
samym przepisem co komputer/kanal.py: potok `\\\\.\\pipe\\jarvo-komputer-ster-<skrót>` na Windows, gniazdo
`<root>/stan/komputer/ster.sock` na macOS i Linuksie (wtyczka leży w kopii w `<dane>/plugins`, więc go nie importuje).
"""
from __future__ import annotations

import atexit
import hashlib
import importlib.util
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

NAZWA = "jarvo-komputer"
STER = os.path.join(os.path.dirname(os.environ.get("JARVO_KOMPUTER_GNIAZDO", "/opt/jarvo/komputer/cua.sock")),
                    "ster.sock")
GRUPA_ENV = "JARVO_KOMPUTER_GRUPA"        # grupa ekranu procesu (komputer/jarvo_cua.py, infra/komputer/wejscie.py)
KARTA_EKRANU_ENV = "JARVO_KOMPUTER_KARTA" # karta kanbana procesu dla klucza ekranu (przeżywa scrub Hermesa)
ROZMOWA_ENV = "JARVO_KOMPUTER_ROZMOWA"    # rozmowa Hermesa (skrót id sesji) dla klucza ekranu bramki
ZNACZNIK = "_jarvo_rozmowa"               # owinięta funkcja Hermesa (zwiaz_computer_use raz na proces)
BEZCZYNNOSC = 300.0                       # s bez wywołania: rozmowa z wejściem się kończy (sesja i ekran wolne)
CZASY = {"patrz": 60.0, "idz": 60.0, "czekaj": 45.0, "kroki": 150.0, "odtworz": 150.0}   # s na odpowiedź wejścia
MAKS_POKAZ_NAGRANIA = 20                  # wpisów nagrania rozmowy w akcja=sciezki
DOMYSLNIE_ELEMENTOW = 150
MAKS_ELEMENTOW = 400
STANY = ("offscreen", "checked", "expanded", "selected", "disabled", "focused", "required")


def natywnie() -> bool:
    return not os.environ.get("JARVO_KOMPUTER_GNIAZDO") and bool(os.environ.get("JARVO_ROOT"))


def adres_natywny(root: str) -> str:
    """Kanał `ster` usługi Komputera dla korzenia `root` (ten sam przepis co komputer/kanal.py `adres`)."""
    norm = os.path.normcase(str(Path(root).expanduser().resolve(strict=False)))
    skrot = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    if os.name == "nt":
        return rf"\\.\pipe\jarvo-komputer-ster-{skrot}"
    p = Path(root) / "stan" / "komputer" / "ster.sock"
    if len(os.fsencode(str(p))) <= 100:
        return str(p)
    for baza in (tempfile.gettempdir(), "/tmp"):
        p = Path(baza) / f"jarvo-{os.getuid()}-{skrot}-k" / "ster.sock"
        if len(os.fsencode(str(p))) <= 100:
            break
    return str(p)


def _zapytaj_potok(adres: str, dane: bytes, czas: float) -> bytes:
    """Windows: jedno pytanie przez potok nazwany (open na \\\\.\\pipe\\… to CreateFile); odpowiedź do końca wiersza."""
    wynik: list = []

    def rozmowa():
        try:
            with open(adres, "r+b", buffering=0) as p:
                p.write(dane)
                odp = b""
                while not odp.endswith(b"\n") and len(odp) < (1 << 20):
                    k = p.read(65536)
                    if not k:
                        break
                    odp += k
                wynik.append(odp)
        except OSError as e:
            wynik.append(e)

    w = threading.Thread(target=rozmowa, daemon=True)
    w.start()
    w.join(czas)
    if not wynik:
        raise TimeoutError("Komputer nie odpowiedział")
    if isinstance(wynik[0], OSError):
        raise wynik[0]
    return wynik[0]


WYLACZONY = ("Komputer Jarva jest wyłączony albo jeszcze startuje. Właściciel włącza go na komputerze z Jarvem: "
             "jarvo komputer on (docs/KOMPUTER.md).")
MAKS_PROSBA = 300
MAKS_WPISOW = 50
DALEJ = {"ask_owner": "Dalej: to krok właściciela. `komputer` akcja=oddaj z dokładną prośbą (gdzie i co kliknąć), "
                      "potem kanban_block z tym samym zdaniem (skill oddaj-ekran). Nie obchodź tego innym krokiem.",
         "wait_for_owner": "Dalej: Komputer jest wstrzymany; nic nie klikaj, czekaj na właściciela.",
         "wait_and_retry": "Dalej: odczekaj (przy zajętym ekranie podany czas, wait albo sleep) i spróbuj raz jeszcze; "
                           "ekran dalej zajęty → stan w karcie i kanban_block z tym powodem, bez pracy obok.",
         "fresh_state": "Dalej: najpierw akcja=patrz (albo idz), potem kroki z numerami z nowego patrz.",
         "choose_another_way": "Dalej: zasady tego nie przepuszczą; inna droga bez tego działania."}

SCHEMAT: Dict[str, Any] = {
    "name": "komputer",
    "description": (
        "Komputer Jarva (przeglądarka Jarva z twardymi zasadami). Strony robisz tym narzędziem: akcja=idz (adres) → "
        "akcja=patrz (drzewo z numerami: najpierw okna i banery, potem to, co widać) → akcja=kroki (do 20 działań "
        "w jednym wywołaniu: klik, pisanie, klawisz, przewijanie, przejście, czekanie; cel numerem z ostatniego "
        "patrz albo napisem; zasady sprawdzają każdy krok, paczka staje na pierwszym, który robi właściciel) → "
        "odczyt z `obserwuj: true` albo patrz. akcja=czekaj: tekst, jego zniknięcie albo adres (do 30 s). "
        "computer_use tylko do zrzutu (canvas, wygląd, dowód kroku). "
        "akcja=stan: czy działa, czy jest pauza i dlaczego. "
        "akcja=dziennik: ostatnie decyzje twardych zasad. "
        "akcja=oddaj: oddajesz ekran właścicielowi z prośbą (np. „zaloguj się do panelu sklepu”, „kliknij Zapłać”): "
        "Komputer staje, dopóki właściciel go nie wznowi; potem patrz od nowa. Wznowić możesz tylko poprosić. "
        "Ścieżki (powtarzalne przejścia, np. logowanie, wyszukanie z filtrem): akcja=sciezki (lista z parametrami i "
        "nagranie tej rozmowy) → akcja=odtworz (nazwa, parametry: cała ścieżka jednym wywołaniem, zasady na każdym "
        "kroku; krok, który nie pasuje, wraca z widokiem strony: zrób go sam przez kroki, potem odtworz z `od`, a "
        "poprawiona ścieżka zapisze się sama). Po udanej nowej ścieżce akcja=zapisz_sciezke (nazwa, parametry "
        "z wartościami, których użyłeś); hasła i kody nie trafiają do pliku."),
    "parameters": {
        "type": "object",
        "properties": {
            "akcja": {"type": "string", "enum": ["stan", "dziennik", "oddaj", "idz", "patrz", "kroki", "czekaj",
                                                 "sciezki", "zapisz_sciezke", "odtworz"]},
            "prosba": {"type": "string", "description": (
                "Dla akcja=oddaj: co właściciel ma zrobić w oknie Komputera (VNC do pulpitu serwera, Tailscale), "
                "jednym zdaniem (gdzie i co kliknąć). "
                "Bez haseł, kodów i danych osobowych.")},
            "n": {"type": "integer", "description": f"Dla akcja=dziennik: ile ostatnich wpisów (1–{MAKS_WPISOW}, domyślnie 20)."},
            "adres": {"type": "string", "description": (
                "Dla akcja=idz: pełny adres http(s). Dla akcja=czekaj: fragment adresu karty albo wzór z *, na "
                "który czekasz.")},
            "okno": {"type": "integer", "description": "Numer karty (window_id) z Twoich okien; bez niego Twoja "
                                                       "aktywna karta (każda rozmowa i karta kanbana ma własne okno)."},
            "maks": {"type": "integer", "description": (
                f"Dla patrz i obserwuj: ile elementów (domyślnie {DOMYSLNIE_ELEMENTOW}, najwyżej {MAKS_ELEMENTOW}).")},
            "kroki": {"type": "array", "maxItems": 20, "items": {"type": "object"}, "description": (
                "Dla akcja=kroki, po kolei: {\"click\": {\"element_index\": 12}}, {\"click\": {\"text\": \"Odrzuć "
                "wszystkie\"}} (cel napisem: napis elementu z patrz; dokładny wygrywa z fragmentem, kilka pasujących "
                "albo żaden = odmowa z numerami, nic nie kliknięte; opcjonalnie \"role\": button, link, textfield), "
                "{\"type_text\": {\"name\": \"Szukaj\", \"text\": \"ekspres\\n\"}} (tu cel to name, a text to "
                "wpisywany tekst), {\"press_key\": {\"key\": \"Return\"}}, {\"scroll\": {\"direction\": \"down\", "
                "\"amount\": 5}}, {\"set_value\": {\"element_index\": 7, \"value\": \"PL\"}}, {\"navigate\": "
                "{\"url\": \"https://…\"}}, {\"wait_for\": {\"text\": \"Wyniki\", \"timeout_ms\": 10000}} "
                "(także \"gone\": true albo \"url\"). Numery: z ostatniego patrz albo obserwacji.")},
            "obserwuj": {"type": "boolean", "description": (
                "Dla akcja=kroki: po ostatnim kroku migawka strony (jak patrz, z * przy nowych elementach). Ustaw, "
                "gdy po krokach chcesz czytać stronę albo działać dalej numerami.")},
            "stop_on": {"type": "string", "enum": ["error", "refusal"], "description": (
                "Dla akcja=kroki: error (domyślnie) – każdy nieudany krok kończy paczkę; refusal – tylko odmowa "
                "zasad (np. krok „zamknij baner, jeśli jest”). Krok właściciela kończy paczkę zawsze.")},
            "tekst": {"type": "string", "description": "Dla akcja=czekaj: tekst, na który czekasz na stronie."},
            "zniknie": {"type": "boolean", "description": "Dla akcja=czekaj z tekstem: czekaj, aż tekst zniknie."},
            "sekundy": {"type": "number", "description": "Dla akcja=czekaj: najdłużej ile sekund (domyślnie 10, najwyżej 30)."},
            "nazwa": {"type": "string", "description": (
                "Dla zapisz_sciezke i odtworz: nazwa ścieżki, cel jak dla człowieka, np. „olx szukaj z ceną”, "
                "„vinted logowanie”. Dla sciezki: pokaż kroki tej ścieżki.")},
            "parametry": {"type": "object", "additionalProperties": {"type": "string"}, "description": (
                "Dla zapisz_sciezke: wartości, których użyłeś i które zmieniają się między razami, np. {\"fraza\": "
                "\"telefon\", \"cena_od\": \"60\", \"cena_do\": \"80\"} (w ścieżce stają się znacznikami {fraza}). "
                "Dla odtworz: nowe wartości (bez podanej: przykład z zapisu); hasło tylko, gdy ścieżka go chce "
                "(parametr tajny), i nigdy nie trafia do pliku.")},
            "opis": {"type": "string", "description": "Dla zapisz_sciezke: co ścieżka robi, jednym zdaniem."},
            "sprawdz": {"type": "string", "description": (
                "Dla zapisz_sciezke: tekst, który jest na stronie na końcu udanej ścieżki (np. „Wyniki”, „Moje "
                "konto”); odtworz na niego czeka, a gdy wyniki mają własny adres z parametrami, odtworz idzie tam "
                "od razu (skrót). Może mieć znaczniki parametrów.")},
            "od": {"type": "integer", "description": (
                "Dla odtworz: od którego kroku ścieżki (1…), po samonaprawie albo kroku właściciela; z `od` cała "
                "ścieżka krok po kroku, bez skrótu. Dla zapisz_sciezke: od którego wpisu nagrania (numery "
                "w akcja=sciezki); bez niego ciągła praca na domenie ostatniego kroku.")},
            "domena": {"type": "string", "description": "Dla sciezki: tylko ścieżki tej domeny (np. olx.pl)."},
        },
        "required": ["akcja"],
    },
}


def _ster(polecenie: Dict[str, Any], czas: float = 5.0) -> Dict[str, Any]:
    """Jedno polecenie JSON do kanału sterowania Komputera; odpowiedź albo {"ok": False, "blad": ...}."""
    dane = (json.dumps(polecenie, ensure_ascii=False) + "\n").encode()
    adres = adres_natywny(os.environ["JARVO_ROOT"]) if natywnie() else STER
    if os.name == "nt" and natywnie():
        try:
            odp = json.loads(_zapytaj_potok(adres, dane, czas) or b"{}")
        except (OSError, ValueError, TimeoutError) as e:
            return {"ok": False, "dziala": False, "blad": f"{WYLACZONY} ({type(e).__name__})"}
        return odp if isinstance(odp, dict) else {"ok": False, "blad": "wejście odpowiedziało nie po JSON-owemu"}
    if not os.path.exists(adres):
        return {"ok": False, "dziala": False, "blad": WYLACZONY}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(czas)
    try:
        s.connect(adres)
        s.sendall(dane)
        odp = b""
        while not odp.endswith(b"\n") and len(odp) < (1 << 20):
            k = s.recv(65536)
            if not k:
                break
            odp += k
        odp = json.loads(odp or b"{}")
        return odp if isinstance(odp, dict) else {"ok": False, "blad": "wejście odpowiedziało nie po JSON-owemu"}
    except (OSError, ValueError) as e:
        return {"ok": False, "dziala": False, "blad": f"{WYLACZONY} ({type(e).__name__})"}
    finally:
        s.close()


def _stan(odp: Dict[str, Any]) -> Dict[str, Any]:
    if not odp.get("ok"):
        return odp
    wynik = {"ok": True, "dziala": True, "wstrzymane": bool(odp.get("wstrzymane")), "sesje": odp.get("sesje"),
             "drzewo_dostepnosci": bool(odp.get("atspi"))}
    if odp.get("pauza"):
        wynik["pauza"] = odp["pauza"].get("opis") or ""
        wynik["kto_wstrzymal"] = "Jarvo (czeka na właściciela)" if odp["pauza"].get("kto") == "flota" else "właściciel"
    if not wynik["drzewo_dostepnosci"]:
        wynik["uwaga"] = "drzewo dostępności nie działa: elementy tylko ze zrzutu (capture mode=som), punkty klikasz ostrożnie"
    return wynik


# ---------------------------------------------------------------------- strony: rozmowa MCP przez bramkę

def grupa_ekranu() -> str:
    """Klucz grupy ekranu tego procesu Hermesa, ustawiany raz w jego otoczeniu: dziedziczą go bramki, które Hermes
    uruchamia dla computer_use, więc ich sesje i sesje tej wtyczki dzielą ekran (wejście: GRUPA). Klucz z PID tego
    procesu: klucz odziedziczony po rodzicu (pracownik karty kanbana dostaje otoczenie bramy Hermesa, w której ta
    wtyczka też działa) zastępuje nowy, inaczej wszystkie karty i rozmowy bramy byłyby dla wejścia jedną sesją.
    Obok klucza karta tego procesu (KARTA_EKRANU_ENV z HERMES_KANBAN_TASK): Hermes zdejmuje HERMES_KANBAN_* z otoczenia
    bramki computer_use (scrub_kanban_env, 17.11), a bramka podaje kartę wejściu razem z kluczem, więc computer_use
    i `komputer` jednej karty mają ten sam klucz ekranu."""
    przedrostek = f"p{os.getpid()}-"
    klucz = os.environ.get(GRUPA_ENV, "")
    if not klucz.startswith(przedrostek):
        klucz = os.environ[GRUPA_ENV] = przedrostek + secrets.token_hex(16)
        karta = os.environ.get("HERMES_KANBAN_TASK", "").strip()
        if karta:
            os.environ[KARTA_EKRANU_ENV] = karta
        else:
            os.environ.pop(KARTA_EKRANU_ENV, None)         # karta rodzica nie jest kartą tego procesu
    return klucz


def rozmowa_sesji(session_id: Any) -> str:
    """Rozmowa Hermesa w kluczu ekranu: skrót id sesji (16 znaków szesnastkowych, id nie wychodzi z procesu);
    pusty bez sesji (wtedy klucz jak dotąd: grupa procesu i karta)."""
    sid = str(session_id or "")
    return hashlib.sha256(sid.encode("utf-8")).hexdigest()[:16] if sid else ""


_START: Dict[str, Any] = {}               # rozmowa i wątek wywołania `_get_backend` w toku (start bramki computer_use)
_START_LOCK = threading.Lock()
_ROZMOWA_WATKU: Dict[int, str] = {}       # wątek pętli bramki computer_use -> jej rozmowa (restart transportu)


def zwiaz_computer_use() -> bool:
    """Rozmowa Hermesa w otoczeniu bramek computer_use (JARVO_KOMPUTER_ROZMOWA). Hermes uruchamia bramkę raz na
    sesję w `tool._get_backend(session_id)` (pod swoją blokadą, czekając, aż bramka odpowie), a otoczenie bierze
    z `cua_backend.cua_driver_child_env()` w wątku pętli tej bramki (także przy restarcie transportu). Owijamy
    oba: `_get_backend` podaje rozmowę sesji na czas startu, a otoczenie zapamiętuje ją dla wątku pętli bramki.
    True, gdy owinięte (także wcześniej); False bez computer_use w Hermesie."""
    try:
        from tools.computer_use import cua_backend, tool
    except Exception:  # noqa: BLE001 - Hermes bez computer_use albo w innej wersji: klucz bez rozmowy
        return False
    if getattr(tool._get_backend, ZNACZNIK, False):
        return True
    get_backend, child_env = tool._get_backend, cua_backend.cua_driver_child_env

    def _get_backend(session_id: str = ""):
        with _START_LOCK:
            _START.update(rozmowa=rozmowa_sesji(session_id), watek=threading.get_ident())
            try:
                return get_backend(session_id=session_id)
            finally:
                _START.clear()

    def cua_driver_child_env(base_env=None):
        env = child_env(base_env)
        watek = threading.get_ident()
        rozmowa = _START.get("rozmowa")
        if rozmowa is not None and _START.get("watek") != watek:     # pętla bramki startowanej teraz
            if len(_ROZMOWA_WATKU) > 256:
                _ROZMOWA_WATKU.clear()
            _ROZMOWA_WATKU[watek] = rozmowa
        else:
            rozmowa = _ROZMOWA_WATKU.get(watek, "")
        if rozmowa:
            env[ROZMOWA_ENV] = rozmowa
        else:
            env.pop(ROZMOWA_ENV, None)
        return env

    setattr(_get_backend, ZNACZNIK, True)
    setattr(cua_driver_child_env, ZNACZNIK, True)
    tool._get_backend, cua_backend.cua_driver_child_env = _get_backend, cua_driver_child_env
    return True


def ponawiaj_po_zamknieciu() -> bool:
    """Po restarcie Komputera (`jarvo komputer off/on`) bramka computer_use sesji jest martwa, a nowszy pakiet `mcp`
    zgłasza to jako `MCPError(CONNECTION_CLOSED)`, którego Hermes nie uznaje za zamkniętą sesję, więc każdy `capture`
    kończył się „Connection closed” (27.11, W3). Dokładamy ten błąd do zamkniętych: Hermes łączy się raz od nowa.
    True, gdy owinięte (także wcześniej); False bez computer_use albo `mcp` w Hermesie."""
    try:
        from mcp.shared.exceptions import MCPError
        from mcp.types import CONNECTION_CLOSED
        from tools.computer_use.cua_backend_session import _CuaDriverSession
    except Exception:  # noqa: BLE001 - inna wersja Hermesa albo mcp: zostaje zachowanie Hermesa
        return False
    stara = _CuaDriverSession._is_closed_session_error
    if getattr(stara, ZNACZNIK, False):
        return True

    def _is_closed_session_error(exc: Exception) -> bool:
        return (isinstance(exc, MCPError) and getattr(getattr(exc, "error", None), "code", None) == CONNECTION_CLOSED
                or stara(exc))

    setattr(_is_closed_session_error, ZNACZNIK, True)
    _CuaDriverSession._is_closed_session_error = staticmethod(_is_closed_session_error)
    return True


class BrakBramki(RuntimeError):
    pass


def _wywolanie_bramki() -> List[str]:
    """Polecenie MCP bramki z jej manifestu (`mcp_invocation`, jak w Hermesie: natywnie Python Jarva z bramką, więc
    bez powłoki i bez .cmd); bez manifestu `<bramka> mcp`."""
    cmd = os.environ.get("HERMES_CUA_DRIVER_CMD", "").strip()
    if not cmd:
        raise BrakBramki("brak bramki Komputera (HERMES_CUA_DRIVER_CMD): właściciel uruchamia `jarvo komputer on`")
    try:
        m = json.loads(subprocess.run([cmd, "manifest"], capture_output=True, timeout=15, check=False).stdout or b"{}")
        w = m.get("mcp_invocation") if isinstance(m, dict) else None
        if isinstance(w, dict) and isinstance(w.get("command"), str) and isinstance(w.get("args"), list) \
                and all(isinstance(a, str) for a in w["args"]):
            return [w["command"], *w["args"]]
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return [cmd, "mcp"]


class _Klient:
    """Jedna rozmowa MCP z wejściem Komputera przez bramkę (proces `bramka mcp` na sesję Hermesa)."""

    def __init__(self, polecenie: List[str], rozmowa: str = "") -> None:
        env = dict(os.environ)
        env.pop(ROZMOWA_ENV, None)
        if rozmowa:
            env[ROZMOWA_ENV] = rozmowa                # ta sama rozmowa co bramki computer_use tej sesji Hermesa
        self.p = subprocess.Popen(polecenie, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=env)
        self.lock = threading.Lock()                  # jedno wywołanie naraz (kroki oceniają stronę po poprzednich)
        self.ostatnio = time.monotonic()
        self.migawka: Optional[str] = None            # snapshot_id ostatniego `patrz` albo obserwacji `kroki`
        self.elementy: Dict[int, Dict[str, Any]] = {} # rola i napis elementów tej migawki (cel numerem → napisem)
        self.adres = ""                               # adres karty po ostatnim kroku (migawka albo paragon)
        self.nagranie: List[Dict[str, Any]] = []      # udane kroki rozmowy do zapisu ścieżki (sciezki.py)
        self.naprawa: Optional[Dict[str, Any]] = None # odtworzenie, które oddało krok agentowi (samonaprawa)
        self._odp: Dict[Any, dict] = {}
        self._warunek = threading.Condition()
        self._koniec = False
        self._n = 0
        threading.Thread(target=self._czytaj, daemon=True, name="jarvo-komputer-mcp").start()

    def _czytaj(self) -> None:
        try:
            for linia in iter(self.p.stdout.readline, b""):
                try:
                    msg = json.loads(linia)
                except ValueError:
                    continue
                if isinstance(msg, dict) and "id" in msg:
                    with self._warunek:
                        self._odp[msg["id"]] = msg
                        self._warunek.notify_all()
        except (OSError, ValueError):
            pass
        finally:
            with self._warunek:
                self._koniec = True
                self._warunek.notify_all()

    def zyje(self) -> bool:
        return not self._koniec and self.p.poll() is None

    def powod_konca(self) -> str:
        try:
            self.p.wait(2)
            return (self.p.stderr.read() or b"").decode("utf-8", "replace").strip()[:300]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return ""

    def narzedzie(self, nazwa: str, args: Dict[str, Any], czas: float) -> Dict[str, Any]:
        """Wynik tools/call (content, structuredContent, isError); ConnectionError, gdy rozmowa się skończyła,
        TimeoutError bez odpowiedzi w `czas` s."""
        self._n += 1
        ident = self._n
        dane = {"jsonrpc": "2.0", "id": ident, "method": "tools/call", "params": {"name": nazwa, "arguments": args}}
        try:
            self.p.stdin.write((json.dumps(dane, ensure_ascii=False) + "\n").encode("utf-8"))
            self.p.stdin.flush()
        except (OSError, ValueError) as e:
            raise ConnectionError(str(e)) from None
        with self._warunek:
            self._warunek.wait_for(lambda: ident in self._odp or self._koniec, czas)
            msg = self._odp.pop(ident, None)
        self.ostatnio = time.monotonic()
        if msg is None:
            raise ConnectionError("rozmowa z Komputerem się skończyła") if self._koniec else TimeoutError(
                f"Komputer nie odpowiedział w {czas:.0f} s")
        if isinstance(msg.get("error"), dict):
            tekst = str(msg["error"].get("message") or "błąd wejścia")
            return {"isError": True, "content": [{"type": "text", "text": tekst}],
                    "structuredContent": {"ok": False, "code": "rpc", "message": tekst}}
        return msg.get("result") if isinstance(msg.get("result"), dict) else {}

    def zamknij(self) -> None:
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            self.p.wait(5)
        except subprocess.TimeoutExpired:
            self.p.kill()


_KLIENCI: Dict[str, _Klient] = {}
_KLIENCI_LOCK = threading.Lock()
_SPRZATACZ: List[threading.Thread] = []


def _sprzataj() -> None:
    """Rozmowy bez wywołań od BEZCZYNNOSC s albo zakończone: koniec (wejście zwalnia sesję i ekran)."""
    teraz = time.monotonic()
    with _KLIENCI_LOCK:
        stare = [(k, c) for k, c in _KLIENCI.items()
                 if not c.lock.locked() and (teraz - c.ostatnio > BEZCZYNNOSC or not c.zyje())]
        for k, _ in stare:
            del _KLIENCI[k]
    for _, c in stare:
        c.zamknij()


def _petla_sprzatania() -> None:
    while True:
        time.sleep(60)
        _sprzataj()


def _zamknij_wszystkie() -> None:
    with _KLIENCI_LOCK:
        klienci = list(_KLIENCI.values())
        _KLIENCI.clear()
    for c in klienci:
        c.zamknij()


atexit.register(_zamknij_wszystkie)


def _klient(klucz: str, rozmowa: str = "") -> _Klient:
    grupa_ekranu()
    if not _SPRZATACZ:
        _SPRZATACZ.append(threading.Thread(target=_petla_sprzatania, daemon=True, name="jarvo-komputer-sprzatanie"))
        _SPRZATACZ[0].start()
    _sprzataj()
    with _KLIENCI_LOCK:
        c = _KLIENCI.get(klucz)
        if c is None or not c.zyje():
            c = _KLIENCI[klucz] = _Klient(_wywolanie_bramki(), rozmowa)
        return c


def _porzuc(klucz: str, c: _Klient) -> None:
    with _KLIENCI_LOCK:
        if _KLIENCI.get(klucz) is c:
            del _KLIENCI[klucz]
    c.zamknij()


def _tekst(wynik: Dict[str, Any]) -> str:
    return "\n".join(c.get("text", "") for c in wynik.get("content") or []
                     if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str))


def _blad(wynik: Dict[str, Any]) -> str:
    sc = wynik.get("structuredContent") if isinstance(wynik.get("structuredContent"), dict) else {}
    linie = [f"BŁĄD {sc.get('code') or 'blad'}: {sc.get('message') or _tekst(wynik)}"]
    if DALEJ.get(sc.get("next_step")):
        linie.append(DALEJ[sc["next_step"]])
    return "\n".join(linie)


def _drzewo(elementy: list) -> List[str]:
    """Elementy migawki wierszami `[numer] rola „napis” = „wartość” (stany)`, wcięcie po głębokości, `*` przy nowych."""
    linie = []
    for e in elementy:
        if not isinstance(e, dict):
            continue
        napis = " ".join(str(e.get("label") or "").split())[:160]
        w = f"{' ' * min(int(e.get('depth') or 0), 12)}{'*' if e.get('new') else ''}[{e.get('element_index')}] " \
            f"{e.get('role')}"
        if napis:
            w += f" „{napis}”"
        wartosc = " ".join(str(e.get("value") or "").split())
        if wartosc and wartosc != napis:
            w += f" = „{wartosc[:80]}”"
        stany = [s for s in e.get("states") or [] if s in STANY]
        if stany:
            w += f" ({', '.join(stany)})"
        linie.append(w)
    return linie


def _opis_migawki(sc: Dict[str, Any]) -> List[str]:
    elementy = sc.get("elements") if isinstance(sc.get("elements"), list) else []
    naglowek = [f"okno {sc.get('window_id')} „{sc.get('title') or ''}” {sc.get('url') or ''}",
                f"migawka {sc.get('snapshot_id')}: {len(elementy)} elementów"
                + (f", {sc['offscreen_count']} poza ekranem (offscreen)" if sc.get("offscreen_count") else "")
                + (f", {sc['covered_count']} przykrytych (niewidoczne)" if sc.get("covered_count") else "")
                + (f", nowe od stanu sprzed kroków (*): {sc['new_count']}" if sc.get("new_count") is not None else "")]
    if sc.get("dialog"):
        naglowek.append("strona czeka na okno JavaScript (dialog): OK albo Anuluj")
    if sc.get("file_chooser"):
        naglowek.append("strona czeka na wybór pliku: robi go właściciel")
    return naglowek + _drzewo(elementy)


def _maks(args: Dict[str, Any]) -> int:
    m = args.get("maks")
    return m if isinstance(m, int) and not isinstance(m, bool) and 0 < m <= MAKS_ELEMENTOW else DOMYSLNIE_ELEMENTOW


# ---------------------------------------------------------------------- ścieżki: nagranie, zapis, odtworzenie

_TU = Path(__file__).resolve().parent
MODUL_SCIEZEK = "jarvo_komputer_sciezki"
ADRES_PARAGONU = re.compile(r"(?:^|; )adres: ([^;\s]+)")


def _sciezki():
    """Moduł ścieżek obok wtyczki (build kopiuje cały katalog); jedna nazwa modułu w procesie."""
    mod = sys.modules.get(MODUL_SCIEZEK)
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(MODUL_SCIEZEK, _TU / "sciezki.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[MODUL_SCIEZEK] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(MODUL_SCIEZEK, None)        # nieudany import nie zostaje w pamięci jako pusty moduł
        raise
    return mod


def _adres_z_paragonu(tekst: Any) -> str:
    """Adres karty po kroku z paragonu (`adres: host/ścieżka`, bez schematu) albo pusty, gdy się nie zmienił."""
    m = ADRES_PARAGONU.search(str(tekst or ""))
    return "https://" + m.group(1) if m else ""


def _zapamietaj_migawke(c: _Klient, sc: Dict[str, Any]) -> None:
    c.migawka = sc["snapshot_id"]
    c.elementy = {e["element_index"]: {"role": e.get("role"), "label": e.get("label")}
                  for e in sc.get("elements") or [] if isinstance(e, dict) and isinstance(e.get("element_index"), int)}
    if sc.get("url"):
        c.adres = str(sc["url"])
        _dopisz_adres(c, c.adres)


def _dopisz_adres(c: _Klient, url: str) -> None:
    """Adres karty, który strona ustawiła już po paragonie ostatniego działania (OLX zmienia adres po filtrze
    z opóźnieniem, a paragon skraca długi adres): do tego działania, bo z niego bierze się `po` i skrót ścieżki."""
    try:
        S = _sciezki()
        akcje = [w for w in c.nagranie if S.rozbierz(w["krok"])[0] is not None]
    except Exception:  # noqa: BLE001 - nagranie nigdy nie psuje wyniku narzędzia
        return
    if not akcje or not url:
        return
    ostatni = akcje[-1]
    teraz = S.czysty_adres(url)
    bez, po = teraz.split("://", 1)[-1], str(ostatni.get("po_adres") or "").split("://", 1)[-1]
    if (po and bez != po and bez.startswith(po)) or (
            not po and bez != S.czysty_adres(str(ostatni.get("adres_przed") or "")).split("://", 1)[-1]):
        ostatni["po_adres"] = teraz


def _nagraj(c: _Klient, wpis: Dict[str, Any]) -> None:
    c.nagranie.append(wpis)
    nadmiar = len(c.nagranie) - _sciezki().MAKS_NAGRANIE
    if nadmiar > 0:
        del c.nagranie[:nadmiar]
        if c.naprawa:
            c.naprawa["start"] = max(0, c.naprawa["start"] - nadmiar)


def _nagraj_krok(c: _Klient, krok: Dict[str, Any], cel: Optional[Dict[str, Any]],
                 adres_po: str = "") -> Optional[Dict[str, Any]]:
    """Udany krok do nagrania rozmowy (wpis albo None); nagranie nigdy nie psuje wyniku narzędzia."""
    try:
        wpis = _sciezki().wpis_kroku(krok, cel, c.adres, adres_po)
    except Exception:  # noqa: BLE001 - krok, którego nie da się zapisać, po prostu nie trafia do nagrania
        return None
    _nagraj(c, wpis)
    return wpis


def _nagraj_paczke(c: _Klient, kroki: list, sc: Dict[str, Any], przed: Dict[int, Dict[str, Any]]) -> None:
    """Udane kroki paczki do nagrania (adres po kroku z paragonu; spóźniony adres dopisuje obserwacja albo patrz)."""
    S = _sciezki()
    for r in sc.get("steps") or []:
        i = r.get("index") if isinstance(r, dict) else None
        if not r.get("ok") or not isinstance(i, int) or not 0 <= i < len(kroki):
            continue
        cel = r.get("target") if isinstance(r.get("target"), dict) else None
        if cel is None:
            try:
                nr = S.rozbierz(kroki[i])[1].get("element_index")
            except S.BladSciezki:
                nr = None
            cel = przed.get(nr) if isinstance(nr, int) else None
        po = _adres_z_paragonu(r.get("message"))
        _nagraj_krok(c, kroki[i], cel, po)
        if po:
            c.adres = po


def _wartosci(args: Dict[str, Any]) -> Dict[str, str]:
    p = args.get("parametry")
    if p is None:
        return {}
    S = _sciezki()
    if not isinstance(p, dict) or not all(isinstance(k, str) and S.NAZWA_PARAMU.match(k) for k in p) or not all(
            isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in p.values()):
        raise S.BladSciezki("`parametry`: obiekt {nazwa: wartość}, nazwy małymi literami (fraza, cena_od, cena_do)")
    return {k: str(v) for k, v in p.items()}


def _lista(args: Dict[str, Any], c: Optional[_Klient]) -> str:
    S = _sciezki()
    sciezki = S.wczytaj()
    nazwa = " ".join(str(args.get("nazwa") or "").split())
    if nazwa:
        if nazwa not in sciezki:
            return f"BŁĄD sciezka: nie ma ścieżki „{nazwa}” (zapisane: {', '.join(sorted(sciezki)) or 'brak'})"
        return "\n".join(S.opis_sciezki(sciezki[nazwa], z_krokami=True))
    d = S.domena("https://" + str(args.get("domena") or "").strip().split("://")[-1]) if args.get("domena") else ""
    wybrane = sorted((s for s in sciezki.values() if not d or s.get("domena") == d),
                     key=lambda s: (str(s.get("domena")), str(s.get("nazwa"))))
    linie = [f"ścieżki{' ' + d if d else ''}: {len(wybrane)}" + ("" if wybrane else
             " (nowa ścieżka: przejdź ją idz/kroki, potem zapisz_sciezke)")]
    for s in wybrane:
        linie += S.opis_sciezki(s)
    if wybrane:
        linie.append("odtworz: {\"akcja\": \"odtworz\", \"nazwa\": …, \"parametry\": {…}}")
    if c is not None and c.nagranie:
        pokaz = c.nagranie[-MAKS_POKAZ_NAGRANIA:]
        pierwszy = len(c.nagranie) - len(pokaz) + 1
        linie.append(f"nagranie tej rozmowy ({len(c.nagranie)} udanych kroków; zapisz_sciezke bierze ciągłą pracę "
                     "na domenie ostatniego kroku, `od` wybiera wpis):")
        linie += [f"  {pierwszy + i}. {S.opis_kroku(w['krok'])} [{w.get('domena') or '?'}]"
                  + (" (opcjonalny)" if w.get("opcjonalny") else "") for i, w in enumerate(pokaz)]
    return "\n".join(linie)


def _zapisz_sciezke(args: Dict[str, Any], c: Optional[_Klient]) -> str:
    S = _sciezki()
    nazwa = " ".join(str(args.get("nazwa") or "").split())
    wartosci = _wartosci(args)
    od = args.get("od") if isinstance(args.get("od"), int) and not isinstance(args.get("od"), bool) else None
    nagranie = c.nagranie if c is not None else []
    if c is not None and nagranie and c.zyje():       # adres karty teraz: strona mogła go zmienić po ostatnim kroku
        try:
            w = c.narzedzie("get_window_state", {"include_screenshot": False, "max_elements": 1}, CZASY["patrz"])
            stan = w.get("structuredContent") if isinstance(w.get("structuredContent"), dict) else {}
            if not w.get("isError") and stan.get("url"):
                _dopisz_adres(c, str(stan["url"]))
        except (ConnectionError, TimeoutError, OSError):
            pass
    stara = S.wczytaj().get(nazwa)
    naprawa = c.naprawa if c is not None and c.naprawa and c.naprawa["nazwa"] == nazwa and od is None else None
    if naprawa:                                   # agent dokończył sam po kroku, który nie pasował
        wartosci = {**naprawa["wartosci"], **wartosci}
        wpisy = nagranie[naprawa["start"]:]
        kroki = naprawa["prefiks"] + S.kroki_sciezki(wpisy, wartosci, start=False)
    else:
        wpisy = S.odcinek(nagranie, od)
        kroki = S.kroki_sciezki(wpisy, wartosci)
    tajne = {t for w in wpisy for t in w.get("tajne") or []}
    sc = S.nowa_sciezka(nazwa, kroki, wartosci, str(args.get("opis") or ""), str(args.get("sprawdz") or ""),
                        tajne, stara, "" if naprawa else S.skrot(wpisy, wartosci))
    if naprawa:
        sc["naprawy"] = int(sc.get("naprawy") or 0) + 1
    S.zapisz(sc)
    if c is not None:
        c.nagranie.clear()
        c.naprawa = None
    punkty = [i + 1 for i, k in enumerate(kroki) if k.get("uwaga") == "punkt"]
    return "\n".join([f"ok: ścieżka {'poprawiona i ' if naprawa else ''}zapisana" + (" (nadpisana)" if stara else ""),
                      *S.opis_sciezki(sc, z_krokami=True)]
                     + ([f"uwaga: kroki {', '.join(map(str, punkty))} klikają w punkt; po zmianie układu strony "
                         "odtworz je odda"] if punkty else []))


def _odtworz(args: Dict[str, Any], c: _Klient, cel: Dict[str, Any]) -> str:
    """Ścieżka paczkami run_steps przez wejście (zasady na każdym kroku); wynik, widok strony i samonaprawa."""
    S = _sciezki()
    nazwa = " ".join(str(args.get("nazwa") or "").split())
    sciezki = S.wczytaj()
    sc = sciezki.get(nazwa)
    if sc is None:
        return f"BŁĄD sciezka: nie ma ścieżki „{nazwa}” (zapisane: {', '.join(sorted(sciezki)) or 'brak'})"
    kroki = sc.get("kroki") or []
    od = args.get("od", 1)
    if not isinstance(od, int) or isinstance(od, bool) or not 1 <= od <= len(kroki):
        return f"BŁĄD od: numer kroku ścieżki 1–{len(kroki)}"
    wartosci = _wartosci(args)
    tajne = {n for n, v in (sc.get("parametry") or {}).items() if isinstance(v, dict) and v.get("tajny")}
    obserwuj = None if args.get("obserwuj") is False else {"max_elements": _maks(args)}
    adres_przed = c.adres
    w = S.odtworz(sc, wartosci, od, lambda a: c.narzedzie("run_steps", {**cel, **a}, CZASY["kroki"]), obserwuj,
                  ze_skrotem="od" not in args)
    koniec_agenta = len(c.nagranie)
    for i in w["wykonane"]:                       # przebieg w nagraniu rozmowy, hasła dalej jako znaczniki
        k = kroki[i]
        try:
            wpis = {"krok": S.wypelnij(k["krok"], w["wartosci"], tajne, zostaw_tajne=True),
                    "adres_przed": adres_przed if i == w["wykonane"][0] else "", "domena": sc.get("domena") or ""}
        except S.BladSciezki:
            continue
        for pole in ("po", "opcjonalny", "uwaga"):
            if k.get(pole):
                wpis[pole] = k[pole]
        _nagraj(c, wpis)
    if w.get("skrot"):
        _nagraj_krok(c, {"navigate": {"url": w["skrot"]}}, None, w["skrot"])
    ost = w["wynik"].get("structuredContent") if isinstance(w["wynik"].get("structuredContent"), dict) else {}
    obs = ost.get("observation") if isinstance(ost.get("observation"), dict) else None
    widok: List[str] = []
    if obs and obs.get("ok") and obs.get("snapshot_id"):
        _zapamietaj_migawke(c, obs)
        widok = _opis_migawki(obs)
    elif obs:
        widok = [f"widok strony: BŁĄD {obs.get('message') or ''}"]
    wykonane = len(w["wykonane"])
    wart = ", ".join(f"{k}={v}" for k, v in sorted(w["wartosci"].items()))
    pomin = f", pominięte opcjonalne (nie było celu): {', '.join(str(i + 1) for i in w['pominiete'])}" \
        if w["pominiete"] else ""
    naglowek = (f"ścieżka „{nazwa}” skrótem {w['skrot']} (adres i „{sc.get('sprawdz')}” na stronie) w "
                f"{w['sekundy']:.1f} s" if w.get("skrot") else
                f"ścieżka „{nazwa}” kroki {od}–{len(kroki)}: {wykonane} zrobione w {w['sekundy']:.1f} s "
                f"(run_steps × {w['paczki']}{pomin})") + (f"; parametry: {wart}" if wart else "") + (
        f"; skrót nie pasował ({w['skrot_nie']}), więc cała ścieżka" if w.get("skrot_nie") else "")
    if w["ok"]:
        linie = [f"ok: {naglowek}"]
        n = c.naprawa
        try:
            if n and n["nazwa"] == nazwa and od > 1:
                wartosci_n = {**n["wartosci"], **w["wartosci"]}
                nowe = n["prefiks"] + S.kroki_sciezki(c.nagranie[n["start"]:koniec_agenta], wartosci_n, start=False) \
                    + kroki[od - 1:]
                sc = S.nowa_sciezka(nazwa, nowe, wartosci_n, sc.get("opis") or "", "", set(), sc)
                sc["naprawy"] = int(sc.get("naprawy") or 0) + 1
                linie.append(f"samonaprawa: ścieżka poprawiona i zapisana ({len(nowe)} kroków, naprawy: "
                             f"{sc['naprawy']})")
            c.naprawa = None
            sc["uzycia"] = int(sc.get("uzycia") or 0) + 1
            S.zapisz(sc)
        except (S.BladSciezki, OSError) as e:
            linie.append(f"uwaga: ścieżki nie zapisałem: {e}")
        return "\n".join(linie + (["widok strony po ścieżce:", *widok] if widok else []))
    k = w["stop"] if isinstance(w["stop"], int) else od - 1
    rodzaj, powod = w["rodzaj"], w["powod"]
    opis = S.opis_kroku(kroki[k]["krok"]) if k < len(kroki) else ""
    dalej = f"potem `odtworz` z \"od\": {k + 2}, żeby dokończyć" if k + 1 < len(kroki) else \
        "potem `zapisz_sciezke` z tą samą nazwą"
    linie = [naglowek]
    if rodzaj == "zasady":
        c.naprawa = None
        linie.append(f"krok {k + 1} ({opis}) zatrzymały twarde zasady: {powod}")
        if DALEJ.get(w.get("next_step")):
            linie.append(DALEJ[w["next_step"]])
        if k + 1 < len(kroki) and w.get("next_step") == "ask_owner":
            linie.append(f"Po kroku właściciela resztę przejdziesz `odtworz` z \"od\": {k + 2}.")
    elif rodzaj == "parametr" and k >= len(kroki) or rodzaj == "parametr" and not any(
            n in tajne for n in S.znaczniki(kroki[k]["krok"])):
        c.naprawa = None
        linie.append(f"BŁĄD parametr: {powod}; podaj go w `parametry` (akcja=sciezki z nazwą pokazuje kroki)")
    elif rodzaj == "parametr":
        c.naprawa = None
        linie.append(f"krok {k + 1} ({opis}) wpisuje wartość tajną, której nie podałeś: zrób ten krok sam (pole może "
                     f"już wypełnić menedżer haseł przeglądarki), {dalej}.")
    else:
        prefiks = [dict(x) for x in kroki[:k]]
        if rodzaj == "po" and prefiks:
            po = S.wzor_po(c.adres, w["wartosci"])
            if po:
                prefiks[-1]["po"] = po
            else:
                prefiks[-1].pop("po", None)
        c.naprawa = {"nazwa": nazwa, "prefiks": prefiks, "start": len(c.nagranie), "wartosci": w["wartosci"]}
        if rodzaj == "po":
            linie.append(f"po kroku {k} strona nie jest tą z zapisu (adres {kroki[k - 1].get('po') if k else ''}, "
                         f"jest {c.adres}): {powod}")
        elif rodzaj == "sprawdz":
            linie.append(f"po ostatnim kroku nie ma na stronie „{sc.get('sprawdz')}”: {powod}")
        else:
            linie.append(f"krok {k + 1} z {len(kroki)} ({opis}) nie pasuje do strony: {powod}")
        if k < len(kroki):
            linie.append(f"Samonaprawa: zrób sam na widoku poniżej to, co miał zrobić krok {k + 1} (`kroki`, cel "
                         f"napisem z widoku), {dalej}; ścieżka zapisze się poprawiona. Gdy dalej też nie pasuje, "
                         "dokończ sam i `zapisz_sciezke` z tą samą nazwą.")
        else:
            linie.append("Samonaprawa: dokończ sam na widoku poniżej i `zapisz_sciezke` z tą samą nazwą (z nowym "
                         "`sprawdz`, jeśli strona pisze to inaczej); ścieżka zapisze się poprawiona.")
    return "\n".join(linie + (["widok strony:", *widok] if widok else []))


def _strona(akcja: str, args: Dict[str, Any], c: _Klient) -> str:
    """idz, patrz, kroki, czekaj, odtworz: wywołania wejścia i tekst dla modelu; udane kroki do nagrania rozmowy."""
    okno = args.get("okno") if isinstance(args.get("okno"), int) and not isinstance(args.get("okno"), bool) else None
    cel = {"window_id": okno} if okno is not None else {}
    if akcja == "patrz":
        w = c.narzedzie("get_window_state", {**cel, "include_screenshot": False, "max_elements": _maks(args)},
                        CZASY[akcja])
        sc = w.get("structuredContent") if isinstance(w.get("structuredContent"), dict) else {}
        if w.get("isError") or not sc.get("snapshot_id"):
            return _blad(w)
        _zapamietaj_migawke(c, sc)
        return "\n".join(_opis_migawki(sc))
    if akcja == "idz":
        adres = str(args.get("adres") or "").strip()
        if not adres:
            return "BŁĄD adres: podaj `adres` (pełny adres http:// albo https://)"
        w = c.narzedzie("navigate", {**cel, "url": adres}, CZASY[akcja])
        if w.get("isError"):
            return _blad(w)
        sc = w.get("structuredContent") or {}
        _nagraj_krok(c, {"navigate": {"url": adres}}, None, str(sc.get("url") or ""))
        c.adres = str(sc.get("url") or adres)
        return (f"ok: okno {sc.get('window_id', okno or '')} „{sc.get('title') or ''}” {sc.get('url') or ''}\n"
                f"{sc.get('message') or _tekst(w)}")
    if akcja == "czekaj":
        a: Dict[str, Any] = dict(cel)
        if args.get("tekst"):
            a["text"] = str(args["tekst"])
            if args.get("zniknie") is True:
                a["gone"] = True
        elif args.get("adres"):
            a["url"] = str(args["adres"])
        sekundy = args.get("sekundy")
        if isinstance(sekundy, (int, float)) and not isinstance(sekundy, bool) and sekundy >= 0:
            a["timeout_ms"] = int(min(sekundy, 30) * 1000)
        w = c.narzedzie("wait_for", a, CZASY[akcja])
        if w.get("isError"):
            return _blad(w)
        _nagraj_krok(c, {"wait_for": {k: v for k, v in a.items() if k != "window_id"}}, None)
        return f"ok: {_tekst(w)}"
    if akcja == "odtworz":
        try:
            return _odtworz(args, c, cel)
        except _sciezki().BladSciezki as e:
            return f"BŁĄD sciezka: {e}"
    # kroki
    kroki = args.get("kroki")
    if not isinstance(kroki, list) or not kroki:
        return "BŁĄD kroki: podaj `kroki` (lista działań, najwyżej 20)"
    a = {**cel, "steps": kroki}
    if c.migawka:
        a["snapshot_id"] = c.migawka                  # numery z ostatniego patrz albo obserwacji
    if args.get("obserwuj") is True:
        a["observe"] = {"max_elements": _maks(args)}
    if args.get("stop_on") in ("error", "refusal"):
        a["stop_on"] = args["stop_on"]
    przed = c.elementy                                # rola i napis celów numerem (do nagrania)
    w = c.narzedzie("run_steps", a, CZASY[akcja])
    sc = w.get("structuredContent") if isinstance(w.get("structuredContent"), dict) else {}
    if "steps" not in sc:                             # paczka odrzucona przed pierwszym krokiem
        return _blad(w)
    try:
        _nagraj_paczke(c, kroki, sc, przed)
    except Exception:  # noqa: BLE001 - nagranie ścieżki nigdy nie psuje wyniku kroków
        pass
    linie = []
    for linia in _tekst(w).splitlines():
        if linia.startswith("obserwacja:"):
            break
        linie.append(linia)
    obs = sc.get("observation") if isinstance(sc.get("observation"), dict) else None
    if obs and obs.get("ok") and obs.get("snapshot_id"):
        _zapamietaj_migawke(c, obs)
        linie += ["obserwacja po krokach:", *_opis_migawki(obs)]
    elif obs:
        linie.append(f"obserwacja: BŁĄD {obs.get('message') or ''}")
    if DALEJ.get(sc.get("next_step")):
        linie.append(DALEJ[sc["next_step"]])
    return "\n".join(linie)


def obsluz(args: Dict[str, Any], **kontekst: Any) -> str:
    args = args or {}
    akcja = str(args.get("akcja") or "stan")
    if akcja in ("sciezki", "zapisz_sciezke"):        # bez wejścia: plik ścieżek i nagranie tej rozmowy
        klucz = str(kontekst.get("session_id") or kontekst.get("task_id") or "")
        with _KLIENCI_LOCK:
            c = _KLIENCI.get(klucz)
        try:
            S = _sciezki()
        except Exception as e:  # noqa: BLE001 - wtyczka bez modułu ścieżek
            return f"BŁĄD sciezka: brak modułu ścieżek ({type(e).__name__})"
        try:
            if c is None:
                return _lista(args, None) if akcja == "sciezki" else _zapisz_sciezke(args, None)
            with c.lock:
                return _lista(args, c) if akcja == "sciezki" else _zapisz_sciezke(args, c)
        except (S.BladSciezki, OSError) as e:
            return f"BŁĄD sciezka: {e}"
    if akcja in CZASY:
        klucz = str(kontekst.get("session_id") or kontekst.get("task_id") or "")
        try:
            c = _klient(klucz, rozmowa_sesji(kontekst.get("session_id")))
        except (BrakBramki, OSError) as e:
            return f"BŁĄD komputer: {e}"
        with c.lock:
            try:
                return _strona(akcja, args, c)
            except (ConnectionError, TimeoutError, OSError) as e:
                powod = c.powod_konca() if not c.zyje() else ""
                _porzuc(klucz, c)
                return f"BŁĄD komputer: {e}. {powod or WYLACZONY}"
    if akcja == "stan":
        wynik = _stan(_ster({"polecenie": "stan"}))
    elif akcja == "dziennik":
        n = args.get("n", 20)
        n = n if isinstance(n, int) and not isinstance(n, bool) and 0 < n <= MAKS_WPISOW else 20
        odp = _ster({"polecenie": "dziennik", "n": n})
        wynik = {"ok": True, "wpisy": odp.get("wpisy", [])} if odp.get("ok") else odp
    elif akcja == "oddaj":
        prosba = " ".join(str(args.get("prosba") or "").split())[:MAKS_PROSBA]
        if len(prosba) < 8:
            return json.dumps({"ok": False, "blad": "oddaj: napisz w `prosba`, co właściciel ma zrobić w oknie "
                                                   "Komputera (np. „kliknij Zapłać 129 zł i daj znać”)"},
                              ensure_ascii=False)
        wynik = _stan(_ster({"polecenie": "pauza", "powod": prosba}))
        if wynik.get("ok"):
            wynik["dalej"] = ("Komputer stoi i czeka na właściciela. Powiedz mu dokładnie, co ma zrobić (to samo, co w prośbie), "
                              "zakończ swoją część albo zablokuj kartę z tym powodem. Po wznowieniu zacznij od nowego "
                              "odczytu strony (patrz albo capture).")
            if wynik.get("kto_wstrzymal") == "właściciel":
                wynik["dalej"] = "Właściciel już wstrzymał Komputer; Twoja prośba nie nadpisała jego pauzy. " + wynik["dalej"]
    else:
        wynik = {"ok": False, "blad": "akcja: stan, dziennik, oddaj, idz, patrz, kroki, czekaj, sciezki, "
                                      "zapisz_sciezke albo odtworz"}
    return json.dumps(wynik, ensure_ascii=False)


def register(ctx) -> None:
    grupa_ekranu()                    # przed pierwszym computer_use: jego bramki dziedziczą klucz z otoczenia
    zwiaz_computer_use()              # i rozmowę swojej sesji Hermesa (okno Komputera na rozmowę)
    ponawiaj_po_zamknieciu()          # po restarcie Komputera computer_use łączy się od nowa zamiast „Connection closed”
    ctx.register_tool(name="komputer", toolset="komputer", schema=SCHEMAT, handler=obsluz, emoji="🖥️",
                      description="Komputer Jarva: strony (idz, patrz, kroki, czekaj), ścieżki (sciezki, "
                                  "zapisz_sciezke, odtworz), stan, dziennik twardych zasad, oddanie ekranu właścicielowi")


if __name__ == "__main__":       # healthcheck toolboxa Jarva: python3 komputer/plugin/__init__.py stan
    import sys
    akcja = sys.argv[1] if len(sys.argv) > 1 else "stan"
    if akcja not in {"stan", "dziennik"}:       # z wiersza poleceń tylko odczyt, bez prośby do właściciela
        sys.exit("użycie: __init__.py stan|dziennik")
    wynik = json.loads(obsluz({"akcja": akcja}))
    print(json.dumps(wynik, ensure_ascii=False, indent=1))
    sys.exit(0 if wynik.get("ok") else 1)
