"""Klient testu Komputera Jarva (scripts/komputer-test.sh): rozmowa MCP przez bramkę floty, jak Hermes.

Uruchamiany w jarvo-hermes jako hermes (`python3 -I -`). Strona testowa (wyszukiwarka i koszyk z polem hasła,
karty, BLIK, przyciskami Kup teraz, Zapłać, Zaloguj się, kluczem API w treści i w nazwie przycisku) działa w Komputerze na
127.0.0.1:8765.
Wznowienie po pauzie robi właściciel: klient wypisuje `@@wznow`, a komputer-test.sh wznawia jako pulpit.
Każdy krok sprawdza decyzję wejścia: co przechodzi do sterownika, co wraca z wymaga_czlowieka, co jest
zablokowane, co znika z odpowiedzi. Kod wyjścia 0 tylko przy komplecie zaliczeń.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

BRAMKA = os.environ.get("JARVO_BRAMKA", "/opt/jarvo/repo/komputer/jarvo_cua.py")
STER = os.environ.get("JARVO_KOMPUTER_STER", "/opt/jarvo/komputer/ster.sock")
STRONA = "http://127.0.0.1:8765/sklep.html"
KLUCZ = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890"
KLUCZ_PRZYCISK = "sk-proj-ZYXWVUTSRQPONMLKJIHGFEDCBA0987654321"

wyniki: list[tuple[bool, str]] = []


def sprawdz(ok: bool, opis: str, szczegoly: str = "") -> bool:
    wyniki.append((ok, opis))
    print(("  ✓ " if ok else "  ✗ ") + opis + ("" if ok or not szczegoly else f"\n      {szczegoly[:300]}"), flush=True)
    return ok


class Klient:
    def __init__(self) -> None:
        self.p = subprocess.Popen([BRAMKA, "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        self.n = 0

    def rpc(self, metoda: str, params: dict | None = None, powiadomienie: bool = False) -> dict:
        msg: dict = {"jsonrpc": "2.0", "method": metoda}
        if params is not None:
            msg["params"] = params
        if not powiadomienie:
            self.n += 1
            msg["id"] = self.n
        self.p.stdin.write((json.dumps(msg) + "\n").encode())
        self.p.stdin.flush()
        if powiadomienie:
            return {}
        while True:
            linia = self.p.stdout.readline()
            if not linia:
                raise SystemExit("bramka zamknęła połączenie: " + self.p.stderr.read().decode()[:400])
            odp = json.loads(linia)
            if odp.get("id") == self.n:
                return odp

    def narzedzie(self, nazwa: str, args: dict) -> dict:
        return self.rpc("tools/call", {"name": nazwa, "arguments": args}).get("result") or {}

    def zamknij(self) -> None:
        self.p.stdin.close()
        self.p.wait(timeout=15)


def zasada(wynik: dict) -> str:
    return str((wynik.get("structuredContent") or {}).get("rule") or "")


def kod(wynik: dict) -> str:
    sc = wynik.get("structuredContent") or {}
    return str(sc.get("code") or ("blad" if wynik.get("isError") else "ok"))


def tekst(wynik: dict) -> str:
    return " ".join(c.get("text", "") for c in wynik.get("content") or [] if c.get("type") == "text")


def ster(polecenie: str, **kw) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(STER)
    s.sendall((json.dumps({"polecenie": polecenie, **kw}) + "\n").encode())
    dane = b""
    while not dane.endswith(b"\n"):
        k = s.recv(65536)
        if not k:
            break
        dane += k
    s.close()
    return json.loads(dane)


def main() -> int:
    k = Klient()
    init = k.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "komputer-test", "version": "1"}})
    k.rpc("notifications/initialized", powiadomienie=True)
    sprawdz("Komputer Jarva" in str(init.get("result", {}).get("instructions", "")),
            "initialize: instrukcje serwera mówią o twardych zasadach")

    narzedzia = {t["name"] for t in k.rpc("tools/list").get("result", {}).get("tools", [])}
    sprawdz({"click", "type_text", "get_window_state", "launch_app"} <= narzedzia, "tools/list: narzędzia pracy są")
    ukryte = {"page", "clipboard_read", "clipboard_write", "browser_navigate", "mouse_button_down", "replay_trajectory",
              "check_for_update", "install_ffmpeg"} & narzedzia
    sprawdz(not ukryte, "tools/list: page, schowek, browser_*, mouse_button_*, nagrania i aktualizacje ukryte",
            str(ukryte))
    sprawdz(kod(k.narzedzie("page", {"action": "execute_javascript", "javascript": "1"})) == "zablokowane",
            "page (JavaScript w przeglądarce): zablokowane")
    sprawdz(kod(k.narzedzie("clipboard_read", {})) == "zablokowane", "clipboard_read: zablokowane")

    # aplikacje
    sprawdz(kod(k.narzedzie("launch_app", {"name": "xterm"})) == "zablokowane", "launch_app xterm: zablokowane")
    sprawdz(kod(k.narzedzie("launch_app", {"name": "chromium", "urls": ["file:///etc/passwd"]})) == "zablokowane",
            "launch_app z file://: zablokowane")
    sprawdz(kod(k.narzedzie("launch_app", {"name": "chromium", "urls": [STRONA],
                                            "additional_arguments": ["--remote-debugging-port=9222"]}))
            == "zablokowane", "launch_app z flagą przeglądarki: zablokowane")
    w = k.narzedzie("launch_app", {"name": "chromium", "urls": [STRONA]})
    sprawdz(not w.get("isError"), "launch_app chromium ze stroną testową: przechodzi", tekst(w))

    okno = None
    for _ in range(30):
        for o in (k.narzedzie("list_windows", {"on_screen_only": True}).get("structuredContent") or {}).get(
                "windows", []):
            if "Sklep testowy Jarvo" in str(o.get("title")):
                okno = o
        if okno:
            break
        time.sleep(0.5)
    if not sprawdz(okno is not None, "okno strony testowej widać w list_windows"):
        return 1
    pid, wid = okno["pid"], okno["window_id"]
    k.narzedzie("start_session", {"session": "komputer-test"})
    k.narzedzie("bring_to_front", {"pid": pid, "window_id": wid})

    def stan() -> tuple[dict, dict]:
        w = k.narzedzie("get_window_state", {"pid": pid, "window_id": wid, "session": "komputer-test"})
        sc = w.get("structuredContent") or {}
        po_nazwie = {}
        for e in sc.get("elements", []):
            if e.get("in_web_content") and e.get("label"):
                po_nazwie.setdefault(e["label"], e)
        return w, po_nazwie

    def ramka(w: dict, tytul: str) -> dict:
        """Ramka okna `tytul` z tej samej migawki. cua-driver 0.21.0 daje w migawce drzewo całego programu, a ramki
        przesuwa o położenie okna z zapytania (okno poza rogiem ekranu ma je przesunięte drugi raz), więc punkt
        w oknie to różnica ramek elementu i okna."""
        for e in (w.get("structuredContent") or {}).get("elements", []):
            if e.get("role") == "frame" and str(e.get("label") or "").startswith(tytul) and e.get("frame"):
                return e["frame"]
        return {}

    def srodek(e: dict, r: dict) -> tuple[float, float]:
        """Środek elementu we współrzędnych zrzutu okna o ramce `r`."""
        f = e["frame"]
        return f["x"] + f["w"] / 2 - r.get("x", 0), f["y"] + f["h"] / 2 - r.get("y", 0)

    w, el = stan()
    sklep = ramka(w, "Sklep testowy Jarvo")
    sprawdz(bool(sklep), "migawka ma ramkę okna sklepu")
    calosc = json.dumps(w, ensure_ascii=False)
    for etykieta in ("Szukaj w sklepie", "Szukaj", "E-mail", "Hasło", "Numer karty", "Kod BLIK", "Uwagi", "Kup teraz", "Dodaj do koszyka",
                     "Zaloguj się", "Zapłać 129 zł", "Pokaż szczegóły"):
        if not sprawdz(etykieta in el, f"drzewo dostępności ma „{etykieta}”"):
            return 1
    sprawdz(KLUCZ not in calosc and "[ukryte przez Komputer Jarva]" in calosc,
            "klucz API z treści strony ukryty w drzewie i tekście odpowiedzi")
    sprawdz(kod(k.narzedzie("get_window_state", {"pid": pid, "window_id": wid, "screenshot_out_file": "/tmp/x.png"}))
            == "zablokowane", "get_window_state z zapisem do pliku: zablokowane")

    def klik(etykieta: str) -> dict:
        return k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el[etykieta]["element_token"]})

    sprawdz(kod(klik("Dodaj do koszyka")) == "ok", "klik „Dodaj do koszyka”: przechodzi")
    w, el = stan()
    for etykieta in ("Kup teraz", "Zaloguj się", "Zapłać 129 zł"):
        sprawdz(kod(klik(etykieta)) == "wymaga_czlowieka", f"klik „{etykieta}” elementem: wymaga człowieka")
    z_kluczem = "Zapłać kluczem [ukryte przez Komputer Jarva]"     # nazwa przycisku w drzewie, już bez klucza
    if sprawdz(z_kluczem in el, f"drzewo dostępności ma „{z_kluczem}”"):
        w = klik(z_kluczem)
        sprawdz(kod(w) == "wymaga_czlowieka" and KLUCZ_PRZYCISK[8:20] not in json.dumps(w, ensure_ascii=False)
                and "[ukryte" in tekst(w), "klik przycisku z kluczem w nazwie: wymaga człowieka, klucz ukryty w odmowie",
                tekst(w))
    x, y = srodek(el["Zapłać 129 zł"], sklep)
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "x": x, "y": y})
    sprawdz(zasada(w) == "punkt_w_tle", "klik w punkt w tle (sterownik klika najmniejszy element programu w tym "
            "miejscu, nie to, co widać): zablokowany", tekst(w))
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "x": x, "y": y, "delivery_mode": "foreground"})
    sprawdz(kod(w) == "wymaga_czlowieka", "klik „Zapłać” w punkt na wierzchu (AT-SPI na żywo): wymaga człowieka",
            tekst(w))
    x, y = srodek(el["Kup teraz"], sklep)
    sprawdz(kod(k.narzedzie("drag", {"pid": pid, "window_id": wid, "from_x": x, "from_y": y, "to_x": x + 2,
                                     "to_y": y})) == "wymaga_czlowieka",
            "przeciągnięcie w miejscu na „Kup teraz”: wymaga człowieka")
    sprawdz(kod(k.narzedzie("mouse_button_down", {"pid": pid, "window_id": wid, "x": x, "y": y})) == "zablokowane",
            "mouse_button_down (klik poza zasadami): zablokowane")

    # pisanie
    pisz = {"pid": pid, "window_id": wid, "delivery_mode": "foreground"}
    sprawdz(kod(klik("E-mail")) == "ok", "klik w pole E-mail: przechodzi")
    time.sleep(0.5)
    w = k.narzedzie("type_text", {**pisz, "text": "jan@example.com"})
    sprawdz(kod(w) == "ok", "pisanie e-maila: przechodzi", tekst(w))
    w = k.narzedzie("press_key", {**pisz, "key": "Return"})
    sprawdz(zasada(w) == "formularz_wrazliwy",
            "Enter w polu E-mail wysłałby formularz z „Zapłać” (AT-SPI): wymaga człowieka", tekst(w))
    w = k.narzedzie("type_text", {**pisz, "element_token": el["E-mail"]["element_token"], "text": "\n"})
    sprawdz(zasada(w) == "formularz_wrazliwy", "nowa linia w polu E-mail (migawka): wymaga człowieka", tekst(w))
    sprawdz(kod(klik("Szukaj w sklepie")) == "ok", "klik w wyszukiwarkę: przechodzi")
    time.sleep(0.5)
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "perfumy"})) == "ok", "pisanie w wyszukiwarce: przechodzi")
    w = k.narzedzie("type_text", {**pisz, "window_id": wid + 1, "text": "perfumy"})
    sprawdz(zasada(w) == "okno_nieaktywne", "pisanie na wierzchu w oknie, które nie jest aktywne: zablokowane",
            tekst(w))
    w = k.narzedzie("press_key", {**pisz, "key": "Return"})
    sprawdz(kod(w) == "ok", "Enter w wyszukiwarce (formularz bez płatności): przechodzi", tekst(w))
    sprawdz(kod(klik("Hasło")) == "ok", "klik w pole hasła: przechodzi (klik niczego nie wysyła)")
    time.sleep(0.5)
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "tajne-haslo"})) == "wymaga_czlowieka",
            "pisanie w polu hasła (fokus z AT-SPI): wymaga człowieka")
    sprawdz(kod(k.narzedzie("press_key", {**pisz, "key": "Return"})) == "wymaga_czlowieka",
            "Enter w polu hasła: wymaga człowieka")
    klik("Numer karty")
    time.sleep(0.5)
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "1234"})) == "wymaga_czlowieka",
            "pisanie w polu „Numer karty”: wymaga człowieka")
    klik("Kod BLIK")
    time.sleep(0.5)
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "123456"})) == "wymaga_czlowieka",
            "kod BLIK: wymaga człowieka")
    klik("Uwagi")
    time.sleep(0.5)
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "karta 4111 1111 1111 1111"})) == "wymaga_czlowieka",
            "numer karty w zwykłym polu: wymaga człowieka")
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "sk-ant-api03-" + "A" * 30})) == "zablokowane",
            "klucz API w tekście: zablokowane")
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "javascript:alert(1)"})) == "zablokowane",
            "adres javascript: zablokowany")
    w = k.narzedzie("type_text", {**pisz, "text": "Proszę o fakturę"})
    sprawdz(kod(w) == "ok", "zwykły tekst w polu Uwagi: przechodzi", tekst(w))
    sprawdz(kod(k.narzedzie("hotkey", {**pisz, "keys": ["ctrl", "shift", "i"]})) == "zablokowane",
            "skrót narzędzi deweloperskich: zablokowany")
    w = k.narzedzie("press_key", {**pisz, "key": "Tab"})
    time.sleep(0.5)
    w = k.narzedzie("press_key", {**pisz, "key": "Return"})
    sprawdz(kod(w) == "wymaga_czlowieka", "Tab na „Kup teraz” i Enter (fokus z AT-SPI): wymaga człowieka", tekst(w))
    klik("Uwagi")
    time.sleep(0.5)
    for znaki, opis in (("\t ", "Tab i spacja"), ("\t\n", "Tab i Enter")):
        w = k.narzedzie("type_text", {**pisz, "text": znaki})
        sprawdz(zasada(w) == "znak_sterujacy", f"{opis} w type_text w „Uwagi” (fokus przeskoczyłby na „Kup teraz”): "
                "zablokowane", tekst(w))
    w = k.narzedzie("type_text", {**pisz, "text": "linia\nlinia"})
    sprawdz(zasada(w) == "formularz_wrazliwy", "Enter w „Uwagi” (formularz z „Zapłać”): wymaga człowieka", tekst(w))
    w = k.narzedzie("press_key", {**pisz, "key": "Return", "modifiers": ["shift"]})
    sprawdz(kod(w) == "ok", "Shift+Enter w „Uwagi” (nowa linia): przechodzi", tekst(w))
    w = k.narzedzie("hotkey", {**pisz, "keys": ["ctrl", "Return"]})
    sprawdz(zasada(w) == "formularz_wrazliwy", "Ctrl+Enter w „Uwagi”: wymaga człowieka", tekst(w))
    w = k.narzedzie("hotkey", {**pisz, "keys": ["option", "shift", "k"]})
    sprawdz(zasada(w) == "accesskey", "Alt+Shift+K (accesskey przycisku „Kup teraz”): zablokowane", tekst(w))

    # strona zmieniona od migawki: przycisk dodany na początku koszyka przesuwa numery elementów, a sterownik szuka
    # elementu po numerze w drzewie z chwili kliknięcia; wejście porównuje go w świeżej migawce
    w, el = stan()
    stary = el["Dodaj do koszyka"]["element_token"]
    sprawdz(kod(klik("Pokaż baner")) == "ok", "klik „Pokaż baner” (token świeżej migawki od wejścia): przechodzi")
    time.sleep(0.5)
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": stary})
    sprawdz(zasada(w) == "element_zmieniony" and "„Dodaj do koszyka”; zrób" in tekst(w),
            "klik „Dodaj do koszyka” numerem sprzed zmiany strony (pod nim jest już inny element): zablokowany",
            tekst(w))
    w, el = stan()
    sprawdz(kod(klik("Dodaj do koszyka")) == "ok", "ten sam klik z nowej migawki: przechodzi")

    # okno podręczne w innym miejscu ekranu (window.open): klik w punkt sprawdzany w tym oknie, nie w oknie pod nim
    sprawdz(kod(klik("Pokaż szczegóły")) == "ok", "klik „Pokaż szczegóły” (otwiera okno podręczne): przechodzi")
    okno2 = None
    for _ in range(30):
        for o in (k.narzedzie("list_windows", {"on_screen_only": True}).get("structuredContent") or {}).get(
                "windows", []):
            if "Okno testowe Jarvo" in str(o.get("title")):
                okno2 = o
        if okno2:
            break
        time.sleep(0.5)
    if sprawdz(okno2 is not None and (okno2.get("bounds") or {}).get("x", 0) > 0,
               "okno podręczne z przesunięciem widać w list_windows", json.dumps(okno2)):
        zaplac, w2 = None, {}
        for _ in range(20):
            w2 = k.narzedzie("get_window_state", {"pid": okno2["pid"], "window_id": okno2["window_id"]})
            for e in (w2.get("structuredContent") or {}).get("elements", []):
                if e.get("label") == "Zapłać teraz" and e.get("frame"):
                    zaplac = e
            if zaplac:
                break
            time.sleep(0.5)
        r2 = ramka(w2, "Okno testowe Jarvo")
        if sprawdz(zaplac is not None and bool(r2), "drzewo okna podręcznego ma „Zapłać teraz” i ramkę okna"):
            # podwójny klik idzie zdarzeniem do okna (w tle, bez akcji AT-SPI): sprawdzany w punkcie tego okna
            x, y = srodek(zaplac, r2)
            w = k.narzedzie("double_click", {"pid": okno2["pid"], "window_id": okno2["window_id"], "x": x, "y": y})
            sprawdz(kod(w) == "wymaga_czlowieka", "podwójny klik w punkt „Zapłać teraz” w przesuniętym oknie "
                    "podręcznym: wymaga człowieka", tekst(w))
            # ten sam punkt ekranu w oknie sklepu pod okienkiem: kliknięcie dostałoby okienko, nie sklep
            b1, b2 = okno.get("bounds") or {}, okno2["bounds"]
            w = k.narzedzie("double_click", {"pid": pid, "window_id": wid, "x": b2["x"] + x - b1.get("x", 0),
                                             "y": b2["y"] + y - b1.get("y", 0)})
            sprawdz(zasada(w) == "nieznany_cel", "klik w punkt okna sklepu przykrytego oknem podręcznym: zablokowany",
                    tekst(w))

    # dwa żądania z tym samym id: drugie odrzucone, odpowiedź pierwszego nadal bez sekretów
    k.n += 1
    for nazwa in ("get_window_state", "list_apps"):
        k.p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": k.n, "method": "tools/call", "params": {
            "name": nazwa, "arguments": {"pid": pid, "window_id": wid}}}) + "\n").encode())
    k.p.stdin.flush()
    odp = []
    while len(odp) < 2:
        m = json.loads(k.p.stdout.readline())
        if m.get("id") == k.n:
            odp.append(m)
    sprawdz(any((m.get("error") or {}).get("code") == -32600 for m in odp)
            and KLUCZ not in json.dumps(odp, ensure_ascii=False),
            "powtórzone id żądania: odrzucone, klucz dalej ukryty")

    # aplikacje spoza przeglądarki
    xvnc = [a for a in (k.narzedzie("list_apps", {}).get("structuredContent") or {}).get("apps", [])
            if a.get("name") == "Xvnc"]
    if xvnc:
        sprawdz(kod(k.narzedzie("kill_app", {"pid": xvnc[0]["pid"]})) == "zablokowane", "kill_app Xvnc: zablokowane")

    # druga sesja (np. druga karta Operatora): patrzy, ale ekranem steruje ta, która działała ostatnio
    k2 = Klient()
    k2.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "komputer-test-2", "version": "1"}})
    k2.rpc("notifications/initialized", powiadomienie=True)
    el2 = {}
    for e in (k2.narzedzie("get_window_state", {"pid": pid, "window_id": wid}).get("structuredContent") or {}).get(
            "elements") or []:
        if e.get("in_web_content") and e.get("label"):
            el2.setdefault(e["label"], e)
    w = k2.narzedzie("click", {"pid": pid, "window_id": wid,
                               "element_token": (el2.get("Dodaj do koszyka") or {}).get("element_token")})
    sprawdz(zasada(w) == "zajete" and (w.get("structuredContent") or {}).get("next_step") == "wait_and_retry",
            "druga sesja: patrzy, ale klik dostaje „zajęte” (jedna sesja naraz)", tekst(w))
    k2.zamknij()

    # prośba Operatora do właściciela: pauza od floty z powodem
    odp = ster("pauza", powod="Zaloguj się do sklepu testowego")
    sprawdz((odp.get("pauza") or {}).get("kto") == "flota", "ster.sock: prośba Operatora (pauza od floty z powodem)")
    w = klik("Dodaj do koszyka")
    sprawdz(kod(w) == "wstrzymane" and "Zaloguj się do sklepu testowego" in tekst(w),
            "klik przy prośbie: wstrzymane z powodem prośby", tekst(w))

    # pauza z HQ (ster.sock)
    sprawdz(ster("pauza").get("wstrzymane") is True, "ster.sock: pauza")
    sprawdz(kod(klik("Dodaj do koszyka")) == "wstrzymane", "klik przy pauzie: wstrzymane")
    _, el = stan()
    sprawdz(bool(el), "patrzenie przy pauzie: działa")
    odp = ster("wznow")
    sprawdz(odp.get("ok") is False and odp.get("wstrzymane") is True, "ster.sock: agent floty nie zdejmie pauzy")
    print("@@wznow", flush=True)                 # komputer-test.sh wznawia jako właściciel (pulpit)
    for _ in range(100):
        if ster("stan").get("wstrzymane") is False:
            break
        time.sleep(0.2)
    sprawdz(ster("stan").get("wstrzymane") is False, "wznowienie przez właściciela (jarvo komputer wznow)")
    sprawdz(kod(klik("Dodaj do koszyka")) == "ok", "klik po wznowieniu: przechodzi")

    dziennik = json.dumps(ster("dziennik", n=200), ensure_ascii=False)
    sprawdz('"czlowiek"' in dziennik and '"wstrzymane"' in dziennik, "dziennik ma decyzje człowiek i pauzę")
    sprawdz("tajne-haslo" not in dziennik and "4111" not in dziennik and "Proszę o fakturę" not in dziennik
            and "sklepu testowego" not in dziennik and KLUCZ_PRZYCISK[8:20] not in dziennik,
            "dziennik bez wpisywanych treści, bez treści prośby i bez klucza z nazwy przycisku")

    k.narzedzie("end_session", {"session": "komputer-test"})
    k.zamknij()
    zle = [o for ok, o in wyniki if not ok]
    print(f"\n{len(wyniki) - len(zle)}/{len(wyniki)} zaliczone" + (f"; niezaliczone: {', '.join(zle)}" if zle else ""))
    return 1 if zle else 0


if __name__ == "__main__":
    sys.exit(main())
