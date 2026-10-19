#!/usr/bin/python3 -I
"""Wejście Komputera Jarva (etap K2, docs/KOMPUTER.md §6): jedyna droga floty do sterownika ekranu.

Działa jako użytkownik pulpit (start.sh). Na gnieździe cua.sock każde połączenie to jedna sesja MCP: wejście
uruchamia `cua-driver mcp` dopiero przy pierwszej wiadomości i przepuszcza rozmowę w obie strony, a po drodze:
  - każde tools/call przechodzi przez zasady.ocen (narzędzia, płatności, logowanie, hasła, karty, kody, pauza);
    odmowa wraca do agenta jako wynik narzędzia, sterownik jej nie dostaje,
  - tools/list pokazuje tylko narzędzia dopuszczone, a initialize dopisuje zasady do instrukcji serwera,
  - odpowiedzi tracą sekrety (klucze, tokeny, numery kart) w tekście i w drzewie dostępności,
  - cel kliknięcia i pole z fokusem bierzemy z migawek sterownika i na żywo z AT-SPI (zdarzenia fokusu,
    element w punkcie), nie z deklaracji agenta.
Na gnieździe ster.sock polecenia JSON: stan, pauza, wznow, dziennik. Pauzę włączy każdy, kto widzi gniazdo
(flota, HQ), wznowić może tylko właściciel: proces pulpitu albo root w tym kontenerze (jarvo komputer wznow),
sprawdzane po SO_PEERCRED, więc agent z terminalem we flocie nie zdejmie sobie pauzy. Dziennik
~/.jarvo/dziennik.jsonl zapisuje każde wywołanie bez treści (narzędzie, decyzja, cel, liczba znaków).
"""

from __future__ import annotations

import json
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zasady  # noqa: E402

GNIAZDA = os.environ.get("KOMPUTER_GNIAZDA", "/run/jarvo-komputer")
CUA = os.path.join(GNIAZDA, "cua.sock")
STER = os.path.join(GNIAZDA, "ster.sock")
STAN = os.path.expanduser("~/.jarvo")
DZIENNIK = os.path.join(STAN, "dziennik.jsonl")
PAUZA = os.path.join(STAN, "pauza")
STEROWNIK = ["cua-driver", "mcp"]
METODY = {"initialize", "notifications/initialized", "notifications/cancelled", "ping", "tools/list",
          "tools/call"}
MAKS_ZADANIE = 1 << 20          # 1 MB na wiadomość od agenta (zrzuty idą w drugą stronę)
MAKS_SESJE = 4
LIMIT_DZIALAN = 120             # działań na minutę, ponad to odmowa (zapętlony agent)
MAKS_DZIENNIK = 2 << 20
ROLE_PRZYCISKOW = {"push button", "button"}
PISANIE = {"type_text", "set_value", "press_key", "hotkey"}   # cel tych narzędzi dostaje też przyciski formularza
MAKS_FORMULARZ = 300            # elementów formularza przeglądanych przy Enterze (przyciski wysyłki)


def wolno_wznowic(uid: int) -> bool:
    """Wznowienie po pauzie: tylko właściciel (docker exec jako pulpit albo root), nie uid floty."""
    return uid in (0, os.getuid())


def log(*a: object) -> None:
    print("[wejście]", *a, file=sys.stderr, flush=True)


class Dziennik:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.ostatnie: deque = deque(maxlen=200)
        os.makedirs(STAN, mode=0o700, exist_ok=True)
        try:                                        # po restarcie wejścia dziennik pamięta ostatnie wpisy
            with open(DZIENNIK, encoding="utf-8") as f:
                for linia in deque(f, maxlen=200):
                    try:
                        self.ostatnie.append(json.loads(linia))
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass

    def zapisz(self, wpis: dict) -> None:
        wpis = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), **wpis}
        with self._lock:
            self.ostatnie.append(wpis)
            try:
                if os.path.exists(DZIENNIK) and os.path.getsize(DZIENNIK) > MAKS_DZIENNIK:
                    os.replace(DZIENNIK, DZIENNIK + ".1")
                with open(DZIENNIK, "a", encoding="utf-8") as f:
                    f.write(json.dumps(wpis, ensure_ascii=False) + "\n")
            except OSError as e:
                log("dziennik:", e)


class Dostepnosc:
    """AT-SPI w osobnym wątku z pętlą GLib: fokus klawiatury ze zdarzeń i element w punkcie na żądanie."""

    def __init__(self) -> None:
        self.dziala = False
        self._fokus: dict[int, tuple] = {}            # pid -> (opis, obiekt AT-SPI) ostatniego fokusu
        self._lock = threading.Lock()
        try:
            import gi
            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi, GLib
        except (ImportError, ValueError) as e:
            log("AT-SPI niedostępne (python3-gi):", e)
            return
        self.Atspi, self.GLib = Atspi, GLib
        gotowe = threading.Event()
        threading.Thread(target=self._petla, args=(gotowe,), daemon=True, name="atspi").start()
        gotowe.wait(10)

    def _petla(self, gotowe: threading.Event) -> None:
        try:
            self.Atspi.init()
            self._sluchacz = self.Atspi.EventListener.new(self._zdarzenie)
            self._sluchacz.register("object:state-changed:focused")
            self.dziala = True
        except Exception as e:  # noqa: BLE001 - brak szyny AT-SPI: wejście działa, zasady fokusu odmawiają
            log("AT-SPI nie wstało:", e)
            return
        finally:
            gotowe.set()
        self.Atspi.event_main()

    def _opis(self, acc, przodkowie: int = 5) -> dict:
        atr = {}
        try:
            atr = {k: v for k, v in (acc.get_attributes() or {}).items()
                   if k in ("tag", "html-input-name", "text-input-type", "autocomplete", "placeholder-text")}
        except Exception:  # noqa: BLE001
            pass
        el = {"rola": acc.get_role_name(), "nazwa": acc.get_name() or "", "atrybuty": atr, "zrodlo": "atspi",
              "przodkowie": []}
        p = acc
        for _ in range(przodkowie):
            try:
                p = p.get_parent()
            except Exception:  # noqa: BLE001
                break
            if p is None:
                break
            el["przodkowie"].append({"rola": p.get_role_name(), "nazwa": p.get_name() or ""})
        return el

    def _formularz(self, acc) -> list[dict]:
        """Przyciski formularza (role form), w którym leży element: Enter w polu wysyła ten formularz."""
        p = acc
        for _ in range(12):
            p = p.get_parent()
            if p is None:
                return []
            if p.get_role_name() == "form":
                break
        else:
            return []
        wynik, kolejka, widziane = [], [p], 0
        while kolejka and widziane < MAKS_FORMULARZ:
            el = kolejka.pop(0)
            widziane += 1
            if el.get_role_name() in ROLE_PRZYCISKOW and el.get_name():
                wynik.append({"rola": el.get_role_name(), "nazwa": el.get_name()})
            for i in range(min(el.get_child_count(), 64)):
                dziecko = el.get_child_at_index(i)
                if dziecko is not None:
                    kolejka.append(dziecko)
        return wynik

    def _zdarzenie(self, ev) -> None:
        if ev.detail1 != 1:
            return
        try:
            pid = ev.source.get_process_id()
            opis = self._opis(ev.source)
        except Exception:  # noqa: BLE001 - element zniknął w trakcie
            return
        with self._lock:
            self._fokus[pid] = (opis, ev.source)

    def _w_glib(self, fn, czas: float = 3.0):
        if not self.dziala:
            return None
        wynik: dict = {}
        koniec = threading.Event()

        def zadanie():
            try:
                wynik["w"] = fn()
            except Exception as e:  # noqa: BLE001
                wynik["e"] = e
            koniec.set()
            return False

        self.GLib.idle_add(zadanie)
        if not koniec.wait(czas):
            return None
        return wynik.get("w")

    def fokus(self, pid: int | None) -> dict | None:
        with self._lock:
            wpis = self._fokus.get(pid) if pid is not None else None
        if wpis is None:
            return None
        opis, acc = wpis
        przyciski = self._w_glib(lambda: self._formularz(acc))
        if przyciski is None:                       # AT-SPI nie odpowiedział: Enter w tym polu sprawdzi człowiek
            return {**opis, "formularz": [], "formularz_nieznany": True}
        return {**opis, "formularz": przyciski}

    def w_punkcie(self, pid: int | None, x: float, y: float, formularz: bool = False) -> dict | None:
        Atspi = self.Atspi if self.dziala else None

        def szukaj():
            pulpit = Atspi.get_desktop(0)
            for i in range(pulpit.get_child_count()):
                app = pulpit.get_child_at_index(i)
                if app is None or (pid is not None and app.get_process_id() != pid):
                    continue
                for j in range(app.get_child_count()):
                    okno = app.get_child_at_index(j)
                    if okno is None or not okno.get_state_set().contains(Atspi.StateType.SHOWING):
                        continue
                    r = okno.get_extents(Atspi.CoordType.SCREEN)
                    if not (r.x <= x < r.x + r.width and r.y <= y < r.y + r.height):
                        continue
                    acc = okno
                    for _ in range(64):
                        nast = acc.get_accessible_at_point(int(x), int(y), Atspi.CoordType.SCREEN)
                        if nast is None or nast == acc:
                            break
                        acc = nast
                    opis = self._opis(acc)
                    if formularz:
                        opis["formularz"] = self._formularz(acc)
                    return opis
            return None

        return self._w_glib(szukaj) if Atspi else None


class Ekran:
    """Wspólny stan dla zasad: pauza, migawki sterownika, AT-SPI, limit działań."""

    def __init__(self, dostepnosc: Dostepnosc) -> None:
        self.dostepnosc = dostepnosc
        self.wstrzymane = os.path.exists(PAUZA)
        self._dzialania: deque = deque()
        self._lock = threading.Lock()

    def ustaw_pauze(self, tak: bool) -> None:
        self.wstrzymane = tak
        if tak:
            with open(PAUZA, "w", encoding="utf-8") as f:
                f.write(datetime.now(timezone.utc).isoformat() + "\n")
        else:
            try:
                os.unlink(PAUZA)
            except FileNotFoundError:
                pass

    def limit(self) -> bool:
        """True, gdy w ostatniej minucie było już LIMIT_DZIALAN działań."""
        teraz = time.monotonic()
        with self._lock:
            while self._dzialania and teraz - self._dzialania[0] > 60:
                self._dzialania.popleft()
            if len(self._dzialania) >= LIMIT_DZIALAN:
                return True
            self._dzialania.append(teraz)
            return False


class KontekstSesji:
    """zasady.Kontekst dla jednej sesji MCP: migawki tej sesji + AT-SPI całego ekranu."""

    def __init__(self, ekran: Ekran) -> None:
        self.ekran = ekran
        self.migawki: dict[str, dict] = {}            # snapshot_id -> {"okno": (pid, wid), "elementy": {...}, ...}
        self.okna: dict[tuple, dict] = {}              # (pid, window_id) -> ostatnia migawka

    @property
    def wstrzymane(self) -> bool:
        return self.ekran.wstrzymane

    def zapamietaj(self, args: dict, sc: dict) -> None:
        sid = sc.get("snapshot_id")
        elementy = sc.get("elements")
        if not isinstance(sid, str) or not isinstance(elementy, list):
            return
        po_indeksie = {e.get("element_index"): e for e in elementy if isinstance(e, dict)}
        korzen = po_indeksie.get(0, {}).get("frame") or {}
        m = {"okno": (sc.get("pid", args.get("pid")), sc.get("window_id", args.get("window_id"))),
             "elementy": po_indeksie, "korzen": korzen, "szer": sc.get("screenshot_width"), "czas": time.monotonic()}
        self.migawki[sid] = m
        self.okna[m["okno"]] = m
        if len(self.migawki) > 8:
            for stary in sorted(self.migawki, key=lambda k: self.migawki[k]["czas"])[:-8]:
                del self.migawki[stary]

    def _z_migawki(self, sid: str | None, indeks) -> dict | None:
        m = self.migawki.get(sid or "")
        if not m:
            return None
        try:
            el = m["elementy"].get(int(indeks))
        except (TypeError, ValueError):
            return None
        if not el:
            return None
        wynik = {"rola": el.get("role"), "nazwa": el.get("label") or "", "atrybuty": {}, "zrodlo": "migawka",
                 "przodkowie": []}
        rodzic, formularz = el.get("parent_index"), None
        for krok in range(12):
            p = m["elementy"].get(rodzic) if rodzic is not None else None
            if not p:
                break
            if krok < 5:
                wynik["przodkowie"].append({"rola": p.get("role"), "nazwa": p.get("label") or ""})
            if p.get("role") == "form":
                formularz = rodzic
                break
            rodzic = p.get("parent_index")
        wynik["formularz"] = self._przyciski_formularza(m, formularz) if formularz is not None else []
        return wynik

    @staticmethod
    def _przyciski_formularza(m: dict, formularz) -> list[dict]:
        wynik = []
        for e in m["elementy"].values():
            if e.get("role") not in ROLE_PRZYCISKOW or not e.get("label"):
                continue
            rodzic = e.get("parent_index")
            for _ in range(12):
                if rodzic is None or rodzic == formularz:
                    break
                rodzic = (m["elementy"].get(rodzic) or {}).get("parent_index")
            if rodzic == formularz:
                wynik.append({"rola": e.get("role"), "nazwa": e.get("label")})
        return wynik

    def _punkt_ekranu(self, args: dict, x: float, y: float) -> tuple[float, float]:
        """Współrzędne zrzutu okna (window-local, ewentualnie przeskalowane) na współrzędne ekranu."""
        if args.get("scope") == "desktop":
            return x, y
        m = self.okna.get((args.get("pid"), args.get("window_id")))
        if not m:
            return x, y
        k = m["korzen"]
        skala = (k.get("w") / m["szer"]) if k.get("w") and m.get("szer") else 1.0
        return k.get("x", 0) + x * skala, k.get("y", 0) + y * skala

    def cel(self, nazwa: str, args: dict) -> dict | None:
        """Element pod działaniem. Token albo indeks spoza migawek tej sesji i punkt bez działającego AT-SPI
        dają zasady.NIEZNANY (odmowa), pusty punkt na ekranie daje None (nic do sprawdzenia)."""
        cel = args.get("target") if isinstance(args.get("target"), dict) else {}
        token = args.get("element_token") or cel.get("element_token")
        if token:
            sid, _, indeks = str(token).rpartition(":")
            return self._z_migawki(sid, indeks) or zasady.NIEZNANY
        indeks = args.get("element_index", cel.get("element_index"))
        if indeks is not None:
            return self._z_migawki(args.get("snapshot_id") or cel.get("snapshot_id"), indeks) or zasady.NIEZNANY
        x, y = args.get("x", cel.get("x")), args.get("y", cel.get("y"))
        if x is not None and y is not None:
            if not self.ekran.dostepnosc.dziala:
                return zasady.NIEZNANY
            try:
                sx, sy = self._punkt_ekranu(args, float(x), float(y))
            except (TypeError, ValueError):
                return zasady.NIEZNANY
            pid = args.get("pid") if isinstance(args.get("pid"), int) else None
            return self.ekran.dostepnosc.w_punkcie(pid, sx, sy, formularz=nazwa in PISANIE)
        return None

    def fokus(self, args: dict) -> dict | None:
        pid = args.get("pid") if isinstance(args.get("pid"), int) else None
        return self.ekran.dostepnosc.fokus(pid)

    def program(self, pid: int) -> str:
        try:
            return os.readlink(f"/proc/{pid}/exe")
        except OSError:
            return ""


class Sesja:
    """Jedno połączenie z cua.sock: agent ↔ wejście ↔ cua-driver mcp."""

    licznik = 0

    def __init__(self, gniazdo: socket.socket, wejscie: "Wejscie") -> None:
        Sesja.licznik += 1
        self.nr = Sesja.licznik
        self.gniazdo, self.wejscie = gniazdo, wejscie
        self.ctx = KontekstSesji(wejscie.ekran)
        self.sterownik: subprocess.Popen | None = None
        self._czytnik: threading.Thread | None = None
        self._pisz = threading.Lock()
        self._wywolania: dict = {}                    # id żądania -> (narzędzie, args)
        self._koniec = threading.Event()

    # --- wysyłanie
    def do_agenta(self, wiadomosc: dict) -> None:
        dane = (json.dumps(wiadomosc, ensure_ascii=False) + "\n").encode()
        with self._pisz:
            try:
                self.gniazdo.sendall(dane)
            except OSError:
                self._koniec.set()

    def do_sterownika(self, wiadomosc: dict) -> None:
        if self.sterownik is None:
            self.sterownik = subprocess.Popen(STEROWNIK, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                              stderr=None, env=self.wejscie.srodowisko, start_new_session=True)
            self._czytnik = threading.Thread(target=self._od_sterownika, daemon=True, name=f"sterownik-{self.nr}")
            self._czytnik.start()
            log(f"sesja {self.nr}: sterownik pid {self.sterownik.pid}")
        try:
            self.sterownik.stdin.write((json.dumps(wiadomosc, ensure_ascii=False) + "\n").encode())
            self.sterownik.stdin.flush()
        except (OSError, ValueError):
            self._koniec.set()

    # --- agent → sterownik
    def obsluz(self) -> None:
        bufor = b""
        try:
            while not self._koniec.is_set():
                kawalek = self.gniazdo.recv(65536)
                if not kawalek:
                    break
                bufor += kawalek
                while b"\n" in bufor:
                    linia, bufor = bufor.split(b"\n", 1)
                    if linia.strip():
                        self._od_agenta(linia)
                if len(bufor) > MAKS_ZADANIE:
                    log(f"sesja {self.nr}: wiadomość ponad {MAKS_ZADANIE} bajtów, koniec sesji")
                    break
        except OSError:
            pass
        finally:
            self.zamknij()

    def _blad_rpc(self, ident, kod: int, tekst: str) -> None:
        if ident is not None:
            self.do_agenta({"jsonrpc": "2.0", "id": ident, "error": {"code": kod, "message": tekst}})

    def _od_agenta(self, linia: bytes) -> None:
        try:
            msg = json.loads(linia)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.do_agenta({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            return
        if not isinstance(msg, dict):
            self.do_agenta({"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32600, "message": "batch wyłączony w Komputerze Jarva"}})
            return
        metoda, ident = msg.get("method"), msg.get("id")
        if metoda is None:                      # odpowiedź agenta na żądanie sterownika
            self.do_sterownika(msg)
            return
        if metoda not in METODY:
            self._blad_rpc(ident, -32601, f"metoda {metoda} wyłączona w Komputerze Jarva")
            return
        if ident is not None and ident in self._wywolania:
            # odpowiedź sterownika musi trafić do właściwego wywołania (ukrywanie sekretów, migawki okien)
            self._blad_rpc(ident, -32600, "id żądania jest już w toku")
            return
        if metoda == "tools/call":
            params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
            nazwa, args = str(params.get("name", "")), params.get("arguments") or {}
            if not isinstance(args, dict):
                self._blad_rpc(ident, -32602, "arguments musi być obiektem")
                return
            w = self._ocen(nazwa, args)
            self._zapisz(nazwa, args, w)
            if not w.wolno:
                if ident is not None:
                    self.do_agenta({"jsonrpc": "2.0", "id": ident, "result": zasady.wynik_odmowy(w)})
                return
            if ident is not None:
                self._wywolania[ident] = (nazwa, args)
        elif ident is not None:
            self._wywolania[ident] = (metoda, {})
        self.do_sterownika(msg)

    def _ocen(self, nazwa: str, args) -> zasady.Werdykt:
        try:
            w = zasady.ocen(nazwa, args, self.ctx)
        except Exception as e:  # noqa: BLE001 - błąd zasady to odmowa, nigdy przepuszczenie
            log(f"sesja {self.nr}: błąd zasady dla {nazwa}: {e!r}")
            return zasady.Werdykt(zasady.ODMOWA, "blad_zasady", "wewnętrzny błąd zasad; działanie wstrzymane")
        if w.wolno and nazwa in zasady.DZIALANIA and self.wejscie.ekran.limit():
            return zasady.Werdykt(zasady.ODMOWA, "limit", f"ponad {LIMIT_DZIALAN} działań na minutę; zwolnij")
        return w

    def _zapisz(self, nazwa: str, args, w: zasady.Werdykt) -> None:
        if nazwa in zasady.ODCZYT and w.wolno:
            return                                  # odczyty nie zapychają dziennika
        wpis = {"sesja": self.nr, "narzedzie": nazwa, "decyzja": w.decyzja}
        if w.kod:
            wpis["zasada"] = w.kod
        if w.cel:
            wpis["cel"] = w.cel[:100]
        wpis.update(w.dane)
        if w.decyzja != zasady.TAK:
            wpis["powod"] = w.powod[:200]
        self.wejscie.dziennik.zapisz(wpis)

    # --- sterownik → agent
    def _od_sterownika(self) -> None:
        wyjscie = self.sterownik.stdout
        try:
            for linia in iter(wyjscie.readline, b""):
                if not linia.strip():
                    continue
                try:
                    msg = json.loads(linia)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(msg, dict) and "id" in msg and ("result" in msg or "error" in msg):
                    msg = self._po_odpowiedzi(msg)
                self.do_agenta(msg)
        except (OSError, ValueError):
            pass
        finally:
            self._koniec.set()
            try:
                self.gniazdo.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def _po_odpowiedzi(self, msg: dict) -> dict:
        nazwa, args = self._wywolania.pop(msg.get("id"), (None, {}))
        wynik, blad = msg.get("result"), msg.get("error")
        if isinstance(blad, dict) and isinstance(blad.get("message"), str):
            blad["message"], _ = zasady.ukryj_sekrety(blad["message"])
        if not isinstance(wynik, dict):
            return msg
        if nazwa == "initialize":
            wynik["instructions"] = str(wynik.get("instructions") or "") + zasady.INSTRUKCJE
        elif nazwa == "tools/list":
            wynik["tools"] = [t for t in wynik.get("tools") or [] if t.get("name") in zasady.DOSTEPNE]
        else:                                       # każda inna odpowiedź traci sekrety, także bez znanego id
            sc = wynik.get("structuredContent")
            if nazwa in zasady.DOSTEPNE and isinstance(sc, dict):
                self.ctx.zapamietaj(args, sc)
            ukryte = 0
            for c in wynik.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str):
                    c["text"], n = zasady.ukryj_sekrety(c["text"])
                    ukryte += n
            if sc is not None:
                wynik["structuredContent"], n = zasady.ukryj_w_strukturze(sc)
                ukryte += n
            if ukryte:
                self.wejscie.dziennik.zapisz({"sesja": self.nr, "narzedzie": nazwa, "decyzja": "ukryte",
                                              "sekrety": ukryte})
        return msg

    def zamknij(self) -> None:
        self._koniec.set()
        s = self.sterownik
        if s is not None and s.poll() is None:
            try:
                s.stdin.close()
            except OSError:
                pass
            try:
                s.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(s.pid, signal.SIGKILL)
                except OSError:
                    pass
        # agent mógł wysłać wszystko i zamknąć swoją stronę: ostatnie odpowiedzi sterownika jeszcze do niego idą
        if self._czytnik is not None and self._czytnik is not threading.current_thread():
            self._czytnik.join(timeout=5)
        try:
            self.gniazdo.close()
        except OSError:
            pass
        self.wejscie.koniec_sesji(self)


class Wejscie:
    def __init__(self) -> None:
        self.dziennik = Dziennik()
        self.ekran = Ekran(Dostepnosc())
        self.sesje: set[Sesja] = set()
        self._lock = threading.Lock()
        self.srodowisko = {k: v for k, v in os.environ.items()
                           if k in ("HOME", "USER", "LOGNAME", "PATH", "LANG", "LC_ALL", "TZ", "DISPLAY", "XAUTHORITY",
                                    "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")}
        self.srodowisko.update(CUA_DRIVER_RS_TELEMETRY_ENABLED="0", CUA_TELEMETRY_ENABLED="0", CUA_TELEMETRY="0",
                               DO_NOT_TRACK="1", CUA_DRIVER_RS_UPDATE_CHECK="false", RUST_LOG="error")

    def koniec_sesji(self, sesja: Sesja) -> None:
        with self._lock:
            if sesja in self.sesje:
                self.sesje.discard(sesja)
                log(f"sesja {sesja.nr}: koniec")

    def _gniazdo(self, sciezka: str) -> socket.socket:
        try:
            os.unlink(sciezka)
        except FileNotFoundError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stara = os.umask(0o117)
        try:
            s.bind(sciezka)
        finally:
            os.umask(stara)
        os.chmod(sciezka, 0o660)
        s.listen(8)
        return s

    def sluchaj_cua(self, s: socket.socket) -> None:
        while True:
            klient, _ = s.accept()
            with self._lock:
                if len(self.sesje) >= MAKS_SESJE:
                    klient.close()
                    continue
                sesja = Sesja(klient, self)
                self.sesje.add(sesja)
            threading.Thread(target=sesja.obsluz, daemon=True, name=f"sesja-{sesja.nr}").start()

    def sluchaj_ster(self, s: socket.socket) -> None:
        while True:
            klient, _ = s.accept()
            threading.Thread(target=self._sterowanie, args=(klient,), daemon=True).start()

    def _sterowanie(self, klient: socket.socket) -> None:
        klient.settimeout(5)
        try:
            dane = b""
            while b"\n" not in dane and len(dane) < 4096:
                k = klient.recv(4096)
                if not k:
                    break
                dane += k
            try:
                polecenie = json.loads(dane.split(b"\n", 1)[0] or b"{}")
            except json.JSONDecodeError:
                polecenie = {}
            co = polecenie.get("polecenie") if isinstance(polecenie, dict) else None
            _, uid, _ = struct.unpack("3i", klient.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                                               struct.calcsize("3i")))
            if co == "wznow" and not wolno_wznowic(uid):
                self.dziennik.zapisz({"narzedzie": "ster", "decyzja": "odmowa", "zasada": "wznow_z_floty",
                                      "uid": uid})
                klient.sendall((json.dumps({"ok": False, "wstrzymane": self.ekran.wstrzymane,
                                            "blad": "wznowić może tylko właściciel: jarvo komputer wznow"},
                                           ensure_ascii=False) + "\n").encode())
                return
            if co == "pauza":
                self.ekran.ustaw_pauze(True)
                self.dziennik.zapisz({"narzedzie": "ster", "decyzja": "pauza"})
            elif co == "wznow":
                self.ekran.ustaw_pauze(False)
                self.dziennik.zapisz({"narzedzie": "ster", "decyzja": "wznow"})
            if co in {"stan", "pauza", "wznow"}:
                odp = {"ok": True, "wstrzymane": self.ekran.wstrzymane, "sesje": len(self.sesje),
                       "atspi": self.ekran.dostepnosc.dziala}
            elif co == "dziennik":
                n = polecenie.get("n", 50)
                n = n if isinstance(n, int) and 0 < n <= 200 else 50
                odp = {"ok": True, "wpisy": list(self.dziennik.ostatnie)[-n:]}
            else:
                odp = {"ok": False, "blad": "polecenia: stan, pauza, wznow, dziennik"}
            klient.sendall((json.dumps(odp, ensure_ascii=False) + "\n").encode())
        except OSError:
            pass
        finally:
            klient.close()

    def start(self) -> None:
        cua, ster = self._gniazdo(CUA), self._gniazdo(STER)
        threading.Thread(target=self.sluchaj_ster, args=(ster,), daemon=True, name="ster").start()
        log(f"gotowe: {CUA} i {STER}, AT-SPI {'tak' if self.ekran.dostepnosc.dziala else 'nie'}, "
            f"pauza {'tak' if self.ekran.wstrzymane else 'nie'}")
        self.sluchaj_cua(cua)


def main() -> int:
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    Wejscie().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
