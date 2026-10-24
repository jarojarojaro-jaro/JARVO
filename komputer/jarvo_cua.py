#!/usr/bin/python3 -I
"""Bramka sterownika ekranu dla Hermesa: HERMES_CUA_DRIVER_CMD wskazuje ten plik (infra/docker-compose.yml).

Hermes woła „cua-driver” z kilkoma czasownikami. Bramka przepuszcza tylko te, których potrzebuje narzędzie
computer_use, i niczego nie pobiera:
  --help, --version, manifest   odpowiedzi stałe (wersja sterownika z obrazu Komputera Jarva),
  mcp [--no-overlay]            rozmowa MCP ze sterownikiem w Komputerze Jarva: bramka tylko przepuszcza bajty
                                między Hermesem a gniazdem cua.sock; zasady sprawdza wejście w Komputerze
                                (infra/komputer/wejscie.py, docs/KOMPUTER.md §6),
  status                        czy Komputer Jarva odpowiada.
Odmawia wszystkiego innego, m.in. check-update i update (sterownik nie aktualizuje się sam ani nie łączy z GitHubem),
serve (tryb bez ograniczeń: /yolo i approvals.mode off zamykają computer_use zamiast go otwierać) oraz install.
Ustawiona zmienna wyłącza też w Hermesie automatyczną „naprawę” sterownika przez curl|bash.
"""

from __future__ import annotations

import json
import os
import sys

WERSJA_STEROWNIKA = "0.21.0"          # cua-driver-rs w obrazie jarvo-komputer (infra/komputer, vendor/zrodla.yaml)
GNIAZDO = os.environ.get("JARVO_KOMPUTER_GNIAZDO", "/opt/jarvo/komputer/cua.sock")   # wolumen gniazd Komputera
EKRAN = os.path.join(os.path.dirname(GNIAZDO), "rfb.sock")                             # ekran Komputera (Xvnc)
WYLACZONY = ("Komputer Jarva jest wyłączony albo jeszcze startuje. Włącz go na komputerze z Jarvem: "
             "jarvo komputer on (docs/KOMPUTER.md).")
BEZ_KANALU = ("Komputer Jarva działa, ale wejście sterownika (cua.sock) nie odpowiada: "
              "jarvo komputer status, jarvo logs komputer (docs/KOMPUTER.md).")
KOD_ODMOWY = 64                        # EX_USAGE: czasownik zablokowany przez bramkę
KOD_BRAK_KOMPUTERA = 69                # EX_UNAVAILABLE

POMOC = """cua-driver (bramka Jarvo)

Użycie: cua-driver <czasownik>
  mcp [--no-overlay]   serwer MCP na stdin/stdout (sterownik w Komputerze Jarva)
  manifest             opis wywołania MCP (JSON)
  status               czy Komputer Jarva odpowiada
  --version            wersja sterownika

Pozostałe czasowniki (check-update, update, serve, install, skills, extension, ...) są wyłączone.
"""


def manifest() -> dict:
    """Manifest w formacie, który sprawdza Hermes (kontrakt 0.20: wersja, wywołanie MCP, flagi czasowników)."""
    sciezka = os.path.abspath(__file__)
    flagi = {"mcp": ["--socket", "--grant", "--no-overlay"],
             "serve": ["--socket", "--permission-mode", "--capability-manifest", "--approve-capability-manifest",
                       "--embedded"],
             "stop": ["--socket"], "status": ["--socket"]}
    return {"binary_version": WERSJA_STEROWNIKA, "binary_path": sciezka, "gateway": "jarvo",
            "mcp_invocation": {"command": sciezka, "args": ["mcp"]},
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


def powod_braku() -> str:
    """Wyłączony Komputer albo działający pulpit bez odpowiadającego wejścia sterownika: różne rady dla właściciela."""
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
    if czas == "status":
        if komputer_dostepny():
            print("Komputer Jarva odpowiada.")
            return 0
        print(powod_braku(), file=sys.stderr)
        return 1
    if czas == "mcp":
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
