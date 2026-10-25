#!/usr/bin/python3 -I
"""Bramka sterownika ekranu dla Hermesa: HERMES_CUA_DRIVER_CMD wskazuje ten plik (infra/docker-compose.yml) albo,
natywnie, nakładkę `jarvo-cua` (`jarvo komputer on`: `<program>/bin-floty/jarvo-cua.cmd` na Windows,
`<program>/bin-floty/jarvo-cua` na macOS i Linuksie), która uruchamia ją Pythonem Jarva.

Hermes woła „cua-driver” z kilkoma czasownikami. Bramka przepuszcza tylko te, których potrzebuje narzędzie
computer_use, i niczego nie pobiera:
  --help, --version, manifest   odpowiedzi stałe (wersja kontraktu sterownika Komputera Jarva),
  mcp [--no-overlay]            rozmowa MCP ze sterownikiem w Komputerze Jarva: bramka tylko przepuszcza bajty
                                między Hermesem a kanałem wejścia; zasady sprawdza wejście (kontener:
                                infra/komputer/wejscie.py; natywnie: komputer/wejscie_natywne.py, docs/KOMPUTER.md §6),
  status                        czy Komputer Jarva odpowiada.
Natywnie czasowniki rąk na ekranie właściciela (K6) idą do komputer/rece/bramka.py: `serve`, `stop`, `call`
oraz `mcp` i `status` z `--socket` (tak woła je Hermes w trybie bounded); bez `--socket` `mcp` i `status` to dalej
Komputer Jarva. Bramka rąk przepuszcza je tylko przy podpisanej zgodzie właściciela (`jarvo komputer rece on`).
Odmawia wszystkiego innego, m.in. check-update i update (sterownik nie aktualizuje się sam ani nie łączy z GitHubem),
w kontenerze serve (tryb bez ograniczeń: /yolo i approvals.mode off zamykają computer_use zamiast go otwierać) oraz
install. Ustawiona zmienna wyłącza też w Hermesie automatyczną „naprawę” sterownika przez curl|bash.

Kontener: gniazdo `JARVO_KOMPUTER_GNIAZDO` (domyślnie /opt/jarvo/komputer/cua.sock w wolumenie gniazd). Natywnie
(jest JARVO_ROOT, nie ma JARVO_KOMPUTER_GNIAZDO): kanał `cua` usługi Komputera tego korzenia (komputer/kanal.py:
potok nazwany z DACL właściciela na Windows, gniazdo 0600 na macOS i Linuksie), a potok musi trzymać proces usługi
z `<stan>/komputer/usluga.json`. Manifest podaje wtedy jako polecenie MCP Pythona z tą bramką, bo Windows nie
uruchomi pliku .py wprost.
"""

from __future__ import annotations

import json
import os
import sys
import time

WERSJA_STEROWNIKA = "0.21.0"          # kontrakt cua-driver-rs (obraz jarvo-komputer; natywnie sterownik CDP)
GNIAZDO = os.environ.get("JARVO_KOMPUTER_GNIAZDO", "/opt/jarvo/komputer/cua.sock")   # wolumen gniazd Komputera
EKRAN = os.path.join(os.path.dirname(GNIAZDO), "rfb.sock")                             # ekran Komputera (Xvnc)
WYLACZONY = ("Komputer Jarva jest wyłączony albo jeszcze startuje. Włącz go na komputerze z Jarvem: "
             "jarvo komputer on (docs/KOMPUTER.md).")
BEZ_KANALU = ("Komputer Jarva działa, ale wejście sterownika (cua.sock) nie odpowiada: "
              "jarvo komputer status, jarvo logs komputer (docs/KOMPUTER.md).")
BEZ_KANALU_NATYWNIE = ("Komputer Jarva działa, ale jego kanał sterownika nie odpowiada: jarvo komputer status, "
                       "jarvo logs komputer (docs/KOMPUTER.md).")
KOD_ODMOWY = 64                        # EX_USAGE: czasownik zablokowany przez bramkę
KOD_BRAK_KOMPUTERA = 69                # EX_UNAVAILABLE
PO_KONCU_WEJSCIA = 2.0                 # s: ostatnie odpowiedzi po zamknięciu stdin przez Hermesa (potok bez półzamknięcia)

POMOC = """cua-driver (bramka Jarvo)

Użycie: cua-driver <czasownik>
  mcp [--no-overlay]   serwer MCP na stdin/stdout (sterownik w Komputerze Jarva)
  manifest             opis wywołania MCP (JSON)
  status               czy Komputer Jarva odpowiada
  --version            wersja sterownika

Natywnie, z podpisaną zgodą właściciela (jarvo komputer rece on), także ręce na jego ekranie: serve, stop
oraz mcp i status z --socket (bramka komputer/rece). Pozostałe czasowniki (check-update, update, install, skills,
extension, call, ...) są wyłączone.
"""


def natywnie() -> bool:
    """Instalacja natywna: korzeń Jarva w otoczeniu (srodowisko.py) i bez gniazda kontenera."""
    return not os.environ.get("JARVO_KOMPUTER_GNIAZDO") and bool(os.environ.get("JARVO_ROOT"))


def _kanal():
    """Moduł kanałów usługi (komputer/kanal.py, sama biblioteka standardowa) z kodu tej wersji Jarva."""
    app = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if app not in sys.path:
        sys.path.insert(0, app)
    from komputer import kanal
    return kanal


def _bramka_rak():
    """Bramka rąk (komputer/rece/bramka.py) z kodu tej wersji Jarva; pakiet `rece` jak w jarvo/rece.py."""
    katalog = os.path.dirname(os.path.abspath(__file__))
    if katalog not in sys.path:
        sys.path.insert(0, katalog)
    from rece import bramka
    return bramka


def dla_rak(argv: list[str]) -> bool:
    """Czasownik rąk na ekranie właściciela: tylko natywnie (w kontenerze nie ma ekranu właściciela)."""
    if not natywnie() or not argv:
        return False
    if argv[0] in ("serve", "stop", "call"):
        return True
    return argv[0] in ("mcp", "status") and any(a == "--socket" or a.startswith("--socket=") for a in argv[1:])


def manifest() -> dict:
    """Manifest w formacie, który sprawdza Hermes (kontrakt 0.20: wersja, wywołanie MCP, flagi czasowników)."""
    sciezka = os.path.abspath(__file__)
    flagi = {"mcp": ["--socket", "--grant", "--no-overlay"],
             "serve": ["--socket", "--permission-mode", "--capability-manifest", "--approve-capability-manifest",
                       "--embedded"],
             "stop": ["--socket"], "status": ["--socket"]}
    wywolanie = {"command": sciezka, "args": ["mcp"]}
    if natywnie():                     # Windows nie uruchomi .py wprost: Python Jarva z tą bramką, bez powłoki
        wywolanie = {"command": sys.executable, "args": ["-I", "-X", "utf8", sciezka, "mcp"]}
    return {"binary_version": WERSJA_STEROWNIKA, "binary_path": sciezka, "gateway": "jarvo",
            "backend": "cdp" if natywnie() else "cua-driver", "mcp_invocation": wywolanie,
            "subcommands": [{"name": n, "args": [{"name": f} for f in f_]} for n, f_ in flagi.items()]}


def odpowiada(sciezka: str) -> bool:
    import socket
    if not os.path.exists(sciezka):
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(sciezka)
        return True
    except OSError:
        return False
    finally:
        s.close()


def komputer_dostepny() -> bool:
    if natywnie():
        kanal, root = _kanal(), os.environ["JARVO_ROOT"]
        try:
            return bool(kanal.zapytaj(kanal.adres(root, "ster"), {"polecenie": "stan"}, 3.0,
                                      kanal.pid_uslugi(root)).get("ok"))
        except kanal.BladKanalu:
            return False
    return odpowiada(GNIAZDO)


def pompuj(sciezka: str) -> int:
    """MCP na stdin/stdout ↔ gniazdo wejścia Komputera, bajt w bajt, aż jedna strona zamknie połączenie."""
    import socket
    import threading
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(sciezka)
    except OSError as e:
        print(f"{powod_braku()} ({e.strerror})", file=sys.stderr)
        return KOD_BRAK_KOMPUTERA

    def do_komputera() -> None:
        try:
            while dane := os.read(0, 1 << 16):
                s.sendall(dane)
        except OSError:
            pass
        finally:
            try:
                s.shutdown(socket.SHUT_WR)          # koniec rozmowy: wejście zamyka sterownik i gniazdo
            except OSError:
                pass

    threading.Thread(target=do_komputera, daemon=True).start()
    try:
        while dane := s.recv(1 << 16):
            widok = memoryview(dane)
            while widok:
                widok = widok[os.write(1, widok):]
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        s.close()
    return 0


def pompuj_natywnie(root: str) -> int:
    """MCP na stdin/stdout ↔ kanał `cua` usługi Komputera (potok albo gniazdo), bajt w bajt. Potok Windows nie ma
    półzamknięcia: po końcu stdin bramka czyta jeszcze najwyżej PO_KONCU_WEJSCIA s i kończy."""
    import socket
    import threading
    kanal = _kanal()
    try:
        s = kanal.polacz(kanal.adres(root, "cua"), 5.0, kanal.pid_uslugi(root))
    except kanal.BladKanalu as e:
        print(f"{powod_braku()} ({e})", file=sys.stderr)
        return KOD_BRAK_KOMPUTERA
    koniec_wejscia: list[float] = []

    def do_komputera() -> None:
        try:
            while dane := os.read(0, 1 << 16):
                s.sendall(dane)
        except OSError:
            pass
        finally:
            koniec_wejscia.append(time.monotonic())
            try:
                s.shutdown(socket.SHUT_WR)          # gniazdo: wejście kończy sesję; potok: nic
            except (OSError, AttributeError):
                pass

    threading.Thread(target=do_komputera, daemon=True).start()
    s.settimeout(0.5)
    try:
        while True:
            try:
                dane = s.recv(1 << 16)
            except (TimeoutError, socket.timeout):
                if koniec_wejscia and time.monotonic() - koniec_wejscia[0] > PO_KONCU_WEJSCIA:
                    break
                continue
            if not dane:
                break
            widok = memoryview(dane)
            while widok:
                widok = widok[os.write(1, widok):]
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        s.close()
    return 0


def powod_braku() -> str:
    """Wyłączony Komputer albo działający pulpit bez odpowiadającego wejścia sterownika: różne rady dla właściciela."""
    if natywnie():
        return BEZ_KANALU_NATYWNIE if _kanal().pid_uslugi(os.environ["JARVO_ROOT"]) else WYLACZONY
    return BEZ_KANALU if odpowiada(EKRAN) else WYLACZONY


def main(argv: list[str]) -> int:
    czas = argv[0] if argv else "--help"
    if czas in {"--help", "-h", "help"}:
        print(POMOC, end="")
        return 0
    if czas in {"--version", "-V", "version"}:
        print(f"cua-driver {WERSJA_STEROWNIKA} (bramka Jarvo)")
        return 0
    if czas == "manifest":
        print(json.dumps(manifest(), ensure_ascii=False))
        return 0
    if dla_rak(argv):
        return _bramka_rak().obsluz(argv)
    if czas == "status":
        if komputer_dostepny():
            print("Komputer Jarva odpowiada.")
            return 0
        print(powod_braku(), file=sys.stderr)
        return 1
    if czas == "mcp":
        if natywnie():
            return pompuj_natywnie(os.environ["JARVO_ROOT"])
        if not os.path.exists(GNIAZDO):
            print(powod_braku(), file=sys.stderr)
            return KOD_BRAK_KOMPUTERA
        return pompuj(GNIAZDO)
    print(f"cua-driver {czas}: wyłączone w bramce Jarvo. Sterownik nie aktualizuje się ani nie instaluje sam; "
          "nową wersję wprowadza przegląd źródła (docs/SOURCES.md).", file=sys.stderr)
    return KOD_ODMOWY


def wyjscie_utf8() -> None:
    """Windows: stdout i stderr w UTF-8 (potok dostaje tam stronę kodową ANSI, a Hermes czyta pomoc, manifest
    i odmowy jako UTF-8); na Linuksie i macOS wyjście już jest w UTF-8. Rozmowa MCP idzie bajtami (os.write)."""
    if os.name == "nt":
        for strumien in (sys.stdout, sys.stderr):
            if hasattr(strumien, "reconfigure"):
                strumien.reconfigure(encoding="utf-8", errors=strumien.errors)


if __name__ == "__main__":
    wyjscie_utf8()
    sys.exit(main(sys.argv[1:]))
