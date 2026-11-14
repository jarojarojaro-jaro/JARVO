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
Rozmowa trwa na sesję Hermesa (snapshot_id ostatniego `patrz` dokłada się do `kroki`) i kończy się po BEZCZYNNOSC s
bez wywołań. Ekran: wejście daje go jednej sesji naraz (`zajete` przez 120 s), ale wtyczka ustawia w procesie
Hermesa klucz grupy ekranu (JARVO_KOMPUTER_GRUPA), który dziedziczą bramki computer_use, i bramka podaje go
wejściu: computer_use (zrzut, canvas) i `komputer` jednego procesu agenta liczą się jak jedna sesja.

build.py kopiuje wtyczkę do plugins/jarvo-komputer, install-fleet.sh dowiązuje ją w profilach z `komputer: true`.

Natywnie (jest JARVO_ROOT, nie ma JARVO_KOMPUTER_GNIAZDO) kanał `ster` usługi Komputera liczy się z korzenia tym
samym przepisem co komputer/kanal.py: potok `\\\\.\\pipe\\jarvo-komputer-ster-<skrót>` na Windows, gniazdo
`<root>/stan/komputer/ster.sock` na macOS i Linuksie (wtyczka leży w kopii w `<dane>/plugins`, więc go nie importuje).
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

NAZWA = "jarvo-komputer"
STER = os.path.join(os.path.dirname(os.environ.get("JARVO_KOMPUTER_GNIAZDO", "/opt/jarvo/komputer/cua.sock")),
                    "ster.sock")
GRUPA_ENV = "JARVO_KOMPUTER_GRUPA"        # grupa ekranu procesu (komputer/jarvo_cua.py, infra/komputer/wejscie.py)
BEZCZYNNOSC = 300.0                       # s bez wywołania: rozmowa z wejściem się kończy (sesja i ekran wolne)
CZASY = {"patrz": 60.0, "idz": 60.0, "czekaj": 45.0, "kroki": 150.0}   # s na odpowiedź wejścia
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
         "wait_and_retry": "Dalej: poczekaj chwilę i spróbuj raz jeszcze.",
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
        "Komputer staje, dopóki właściciel go nie wznowi; potem patrz od nowa. Wznowić możesz tylko poprosić."),
    "parameters": {
        "type": "object",
        "properties": {
            "akcja": {"type": "string", "enum": ["stan", "dziennik", "oddaj", "idz", "patrz", "kroki", "czekaj"]},
            "prosba": {"type": "string", "description": (
                "Dla akcja=oddaj: co właściciel ma zrobić w oknie Komputera (VNC do pulpitu serwera, Tailscale), "
                "jednym zdaniem (gdzie i co kliknąć). "
                "Bez haseł, kodów i danych osobowych.")},
            "n": {"type": "integer", "description": f"Dla akcja=dziennik: ile ostatnich wpisów (1–{MAKS_WPISOW}, domyślnie 20)."},
            "adres": {"type": "string", "description": (
                "Dla akcja=idz: pełny adres http(s). Dla akcja=czekaj: fragment adresu karty albo wzór z *, na "
                "który czekasz.")},
            "okno": {"type": "integer", "description": "Numer karty (window_id); bez niego aktywna karta."},
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
    uruchamia dla computer_use, więc ich sesje i sesje tej wtyczki dzielą ekran (wejście: GRUPA)."""
    return os.environ.setdefault(GRUPA_ENV, secrets.token_hex(16))


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

    def __init__(self, polecenie: List[str]) -> None:
        self.p = subprocess.Popen(polecenie, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=dict(os.environ))
        self.lock = threading.Lock()                  # jedno wywołanie naraz (kroki oceniają stronę po poprzednich)
        self.ostatnio = time.monotonic()
        self.migawka: Optional[str] = None            # snapshot_id ostatniego `patrz` albo obserwacji `kroki`
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


def _klient(klucz: str) -> _Klient:
    grupa_ekranu()
    if not _SPRZATACZ:
        _SPRZATACZ.append(threading.Thread(target=_petla_sprzatania, daemon=True, name="jarvo-komputer-sprzatanie"))
        _SPRZATACZ[0].start()
    _sprzataj()
    with _KLIENCI_LOCK:
        c = _KLIENCI.get(klucz)
        if c is None or not c.zyje():
            c = _KLIENCI[klucz] = _Klient(_wywolanie_bramki())
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


def _strona(akcja: str, args: Dict[str, Any], c: _Klient) -> str:
    """idz, patrz, kroki, czekaj: jedno wywołanie wejścia i tekst dla modelu."""
    okno = args.get("okno") if isinstance(args.get("okno"), int) and not isinstance(args.get("okno"), bool) else None
    cel = {"window_id": okno} if okno is not None else {}
    if akcja == "patrz":
        w = c.narzedzie("get_window_state", {**cel, "include_screenshot": False, "max_elements": _maks(args)},
                        CZASY[akcja])
        sc = w.get("structuredContent") if isinstance(w.get("structuredContent"), dict) else {}
        if w.get("isError") or not sc.get("snapshot_id"):
            return _blad(w)
        c.migawka = sc["snapshot_id"]
        return "\n".join(_opis_migawki(sc))
    if akcja == "idz":
        adres = str(args.get("adres") or "").strip()
        if not adres:
            return "BŁĄD adres: podaj `adres` (pełny adres http:// albo https://)"
        w = c.narzedzie("navigate", {**cel, "url": adres}, CZASY[akcja])
        if w.get("isError"):
            return _blad(w)
        sc = w.get("structuredContent") or {}
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
        return _blad(w) if w.get("isError") else f"ok: {_tekst(w)}"
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
    w = c.narzedzie("run_steps", a, CZASY[akcja])
    sc = w.get("structuredContent") if isinstance(w.get("structuredContent"), dict) else {}
    if "steps" not in sc:                             # paczka odrzucona przed pierwszym krokiem
        return _blad(w)
    linie = []
    for linia in _tekst(w).splitlines():
        if linia.startswith("obserwacja:"):
            break
        linie.append(linia)
    obs = sc.get("observation") if isinstance(sc.get("observation"), dict) else None
    if obs and obs.get("ok") and obs.get("snapshot_id"):
        c.migawka = obs["snapshot_id"]
        linie += ["obserwacja po krokach:", *_opis_migawki(obs)]
    elif obs:
        linie.append(f"obserwacja: BŁĄD {obs.get('message') or ''}")
    if DALEJ.get(sc.get("next_step")):
        linie.append(DALEJ[sc["next_step"]])
    return "\n".join(linie)


def obsluz(args: Dict[str, Any], **kontekst: Any) -> str:
    args = args or {}
    akcja = str(args.get("akcja") or "stan")
    if akcja in CZASY:
        klucz = str(kontekst.get("session_id") or kontekst.get("task_id") or "")
        try:
            c = _klient(klucz)
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
        wynik = {"ok": False, "blad": "akcja: stan, dziennik, oddaj, idz, patrz, kroki albo czekaj"}
    return json.dumps(wynik, ensure_ascii=False)


def register(ctx) -> None:
    grupa_ekranu()                    # przed pierwszym computer_use: jego bramki dziedziczą klucz z otoczenia
    ctx.register_tool(name="komputer", toolset="komputer", schema=SCHEMAT, handler=obsluz, emoji="🖥️",
                      description="Komputer Jarva: strony (idz, patrz, kroki, czekaj), stan, dziennik twardych zasad, "
                                  "oddanie ekranu właścicielowi")


if __name__ == "__main__":       # healthcheck toolboxa Jarva: python3 komputer/plugin/__init__.py stan
    import sys
    akcja = sys.argv[1] if len(sys.argv) > 1 else "stan"
    if akcja not in {"stan", "dziennik"}:       # z wiersza poleceń tylko odczyt, bez prośby do właściciela
        sys.exit("użycie: __init__.py stan|dziennik")
    wynik = json.loads(obsluz({"akcja": akcja}))
    print(json.dumps(wynik, ensure_ascii=False, indent=1))
    sys.exit(0 if wynik.get("ok") else 1)
