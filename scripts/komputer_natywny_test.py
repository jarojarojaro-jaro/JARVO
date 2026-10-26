"""Test Komputera Jarva natywnie na żywo (docs/NATYWNIE.md E10, J13): rozmowa MCP przez bramkę floty, jak Hermes.

    JARVO_ROOT=<korzeń próby> [JARVO_KOMPUTER_CHROME_PROBA=<chrome albo chrome-headless-shell>] \\
        python -I -X utf8 scripts/komputer_natywny_test.py [--uruchom]

Natywna wersja scripts/komputer_test.py (kontener). Usługa Komputera musi działać ze stroną testową
(`jarvo komputer on --strona-testowa komputer/strona_testowa`); z `--uruchom` skrypt włącza ją sam w tym korzeniu
i wyłącza na końcu. Strona testowa (sklep z polem hasła, karty, BLIK, przyciskami płatności, kluczem API w treści
i w nazwie przycisku; formularz zamówienia z ramką płatności z innej witryny, oknem potwierdzenia, wyborem pliku,
pobraniami i banerem) przychodzi przez Fetch.fulfillRequest pod https://sklep.jarvo.test/, więc nie ma serwera na
porcie i proxy filtrujące działa jak zawsze. Bramka (komputer/jarvo_cua.py mcp) idzie tą samą drogą co Hermes.

Sprawdzenia zależne od X11 (okienko podręczne przykrywające okno, Xvnc w list_apps) mają tu oczekiwany wynik
przeglądarki: okno = karta, punkt poza stroną to `nieznany_cel`, program spoza przeglądarki to `zablokowane`.
Wznowienie po pauzie robi właściciel: skrypt działa w jego terminalu, więc sam wysyła token właściciela (po tym, jak
sprawdzi, że bez tokenu wznowić się nie da). Kod wyjścia 0 tylko przy komplecie zaliczeń.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from jarvo import sciezki  # noqa: E402
from komputer import kanal  # noqa: E402

BRAMKA = REPO / "komputer" / "jarvo_cua.py"
SKLEP = "https://sklep.jarvo.test/sklep.html"
FORMULARZ = "https://sklep.jarvo.test/formularz.html"
KLUCZ = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890"
KLUCZ_PRZYCISK = "sk-proj-ZYXWVUTSRQPONMLKJIHGFEDCBA0987654321"
UKRYTE = "[ukryte przez Komputer Jarva]"

TEKSTOWE = ("static", "label", "paragraph", "heading", "document web", "document frame", "form", "internal frame")

wyniki: list[tuple[bool, str]] = []


def po_nazwie(elementy: list[dict]) -> dict:
    """Element według napisu; przy kilku z tym samym napisem wygrywa ten do działania (pole, przycisk, link)."""
    wynik: dict = {}
    for e in elementy:
        if e.get("in_web_content") and e.get("label"):
            if e["label"] not in wynik or (wynik[e["label"]]["role"] in TEKSTOWE and e["role"] not in TEKSTOWE):
                wynik[e["label"]] = e
    return wynik


def sprawdz(ok: bool, opis: str, szczegoly: str = "") -> bool:
    wyniki.append((ok, opis))
    print(("  ✓ " if ok else "  ✗ ") + opis + ("" if ok or not szczegoly else f"\n      {szczegoly[:300]}"), flush=True)
    return ok


class Klient:
    def __init__(self) -> None:
        self.p = subprocess.Popen([sys.executable, "-I", "-X", "utf8", str(BRAMKA), "mcp"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.n = 0

    def wyslij(self, msg: dict) -> None:
        self.p.stdin.write((json.dumps(msg) + "\n").encode())
        self.p.stdin.flush()

    def rpc(self, metoda: str, params: dict | None = None, powiadomienie: bool = False) -> dict:
        msg: dict = {"jsonrpc": "2.0", "method": metoda}
        if params is not None:
            msg["params"] = params
        if not powiadomienie:
            self.n += 1
            msg["id"] = self.n
        self.wyslij(msg)
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


def ster(root: str, polecenie: str, wlasciciel: bool = False, **kw) -> dict:
    if wlasciciel:
        kw["token"] = (kanal.katalog_stanu(root) / "wlasciciel.klucz").read_text(encoding="utf-8").strip()
    return kanal.zapytaj(kanal.adres(root, "ster"), {"polecenie": polecenie, **kw}, 15.0, kanal.pid_uslugi(root),
                         maks=16 << 20)


def inicjuj(k: Klient, nazwa: str = "komputer-natywny-test") -> dict:
    init = k.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": nazwa, "version": "1"}})
    k.rpc("notifications/initialized", powiadomienie=True)
    return init


def okno_o_tytule(k: Klient, tytul: str, poza: int | None = None, czas: float = 45.0) -> dict | None:
    """Okno (karta) o tytule; do `czas` sekund: Windows arm64 uruchamia przeglądarkę x64 w emulacji i nowa karta
    z tytułem bywa gotowa po kilkunastu sekundach (CI natywnie, WARM: 10 s nie wystarczało)."""
    koniec = time.monotonic() + czas
    while True:
        for o in (k.narzedzie("list_windows", {"on_screen_only": True}).get("structuredContent") or {}).get(
                "windows", []):
            if tytul in str(o.get("title")) and o.get("window_id") != poza:
                return o
        if time.monotonic() >= koniec:
            return None
        time.sleep(0.25)


def przebieg(root: str) -> int:
    stan = ster(root, "stan")
    if not sprawdz(stan.get("ok") is True and (stan.get("usluga") or {}).get("strona_testowa") is True,
                   "usługa Komputera działa ze stroną testową", json.dumps(stan, ensure_ascii=False)):
        return 1
    k = Klient()
    init = inicjuj(k)
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

    # aplikacje i adresy
    sprawdz(kod(k.narzedzie("launch_app", {"name": "xterm"})) == "zablokowane", "launch_app xterm: zablokowane")
    sprawdz(kod(k.narzedzie("launch_app", {"name": "chromium", "urls": ["file:///etc/passwd"]})) == "zablokowane",
            "launch_app z file://: zablokowane")
    sprawdz(kod(k.narzedzie("launch_app", {"name": "chromium", "urls": [SKLEP],
                                            "additional_arguments": ["--remote-debugging-port=9222"]}))
            == "zablokowane", "launch_app z flagą przeglądarki: zablokowane")
    w = k.narzedzie("launch_app", {"name": "chromium", "urls": [SKLEP]})
    sprawdz(not w.get("isError"), "launch_app chromium ze stroną testową: przechodzi", tekst(w))
    okno = okno_o_tytule(k, "Sklep testowy Jarvo")
    if not sprawdz(okno is not None, "okno (karta) strony testowej widać w list_windows"):
        return 1
    pid, wid = okno["pid"], okno["window_id"]
    k.narzedzie("start_session", {"session": "komputer-test"})
    sprawdz(not k.narzedzie("bring_to_front", {"pid": pid, "window_id": wid}).get("isError"),
            "bring_to_front karty sklepu: przechodzi (karta aktywna)")

    def stan_okna(nr: int = wid) -> tuple[dict, dict]:
        w = k.narzedzie("get_window_state", {"pid": pid, "window_id": nr, "session": "komputer-test"})
        return w, po_nazwie((w.get("structuredContent") or {}).get("elements", []))

    def srodek(e: dict) -> tuple[float, float]:
        """Środek elementu w pikselach zrzutu okna (natywnie ramki są już w układzie okna)."""
        f = e["frame"]
        return f["x"] + f["w"] / 2, f["y"] + f["h"] / 2

    w, el = stan_okna()
    sc = w.get("structuredContent") or {}
    sprawdz(bool(sc.get("screenshot_width")) and any(e.get("role") == "document web" for e in sc.get("elements", [])),
            "migawka ma zrzut i dokument strony")
    calosc = json.dumps(w, ensure_ascii=False)
    for etykieta in ("Szukaj w sklepie", "Szukaj", "E-mail", "Hasło", "Numer karty", "Kod BLIK", "Uwagi", "Kup teraz",
                     "Dodaj do koszyka", "Zaloguj się", "Zapłać 129 zł", "Pokaż szczegóły"):
        if not sprawdz(etykieta in el, f"drzewo dostępności ma „{etykieta}”"):
            return 1
    sprawdz(el["Hasło"]["role"] == "password text", "pole hasła w słowniku zasad: password text (atrybut type z DOM)")
    sprawdz(KLUCZ not in calosc and UKRYTE in calosc, "klucz API z treści strony ukryty w drzewie i tekście odpowiedzi")
    sprawdz(kod(k.narzedzie("get_window_state", {"pid": pid, "window_id": wid, "screenshot_out_file": "x.png"}))
            == "zablokowane", "get_window_state z zapisem do pliku: zablokowane")

    def klik(etykieta: str, slownik: dict | None = None, nr: int = wid) -> dict:
        return k.narzedzie("click", {"pid": pid, "window_id": nr,
                                     "element_token": (slownik or el)[etykieta]["element_token"]})

    sprawdz(kod(klik("Dodaj do koszyka")) == "ok", "klik „Dodaj do koszyka”: przechodzi")
    w, el = stan_okna()
    for etykieta in ("Kup teraz", "Zaloguj się", "Zapłać 129 zł"):
        sprawdz(kod(klik(etykieta)) == "wymaga_czlowieka", f"klik „{etykieta}” elementem: wymaga człowieka")
    z_kluczem = f"Zapłać kluczem {UKRYTE}"
    if sprawdz(z_kluczem in el, f"drzewo dostępności ma „{z_kluczem}”"):
        w = klik(z_kluczem)
        sprawdz(kod(w) == "wymaga_czlowieka" and KLUCZ_PRZYCISK[8:20] not in json.dumps(w, ensure_ascii=False)
                and "[ukryte" in tekst(w), "klik przycisku z kluczem w nazwie: wymaga człowieka, klucz ukryty w odmowie",
                tekst(w))
    x, y = srodek(el["Zapłać 129 zł"])
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "x": x, "y": y})
    sprawdz(zasada(w) == "punkt_w_tle", "klik w punkt w tle: zablokowany (zasada wspólna z kontenerem)", tekst(w))
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "x": x, "y": y, "delivery_mode": "foreground"})
    sprawdz(kod(w) == "wymaga_czlowieka", "klik „Zapłać” w punkt na wierzchu (trafienie silnika strony): wymaga "
            "człowieka", tekst(w))
    x, y = srodek(el["Kup teraz"])
    sprawdz(kod(k.narzedzie("drag", {"pid": pid, "window_id": wid, "from_x": x, "from_y": y, "to_x": x + 2,
                                     "to_y": y})) == "wymaga_czlowieka",
            "przeciągnięcie w miejscu na „Kup teraz”: wymaga człowieka")
    sprawdz(kod(k.narzedzie("mouse_button_down", {"pid": pid, "window_id": wid, "x": x, "y": y})) == "zablokowane",
            "mouse_button_down (klik poza zasadami): zablokowane")
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "x": 5000, "y": 10, "delivery_mode": "foreground"})
    sprawdz(zasada(w) == "nieznany_cel", "klik w punkt poza obszarem strony: zablokowany (nieznany cel)", tekst(w))

    # pisanie
    pisz = {"pid": pid, "window_id": wid, "delivery_mode": "foreground"}
    sprawdz(kod(klik("E-mail")) == "ok", "klik w pole E-mail: przechodzi")
    w = k.narzedzie("type_text", {**pisz, "text": "jan@example.com"})
    sprawdz(kod(w) == "ok", "pisanie e-maila: przechodzi", tekst(w))
    sprawdz((w.get("structuredContent") or {}).get("effect") == "confirmed",
            "pisanie e-maila: effect confirmed (wartość pola sprawdzona)", json.dumps(w.get("structuredContent")))
    w = k.narzedzie("press_key", {**pisz, "key": "Return"})
    sprawdz(zasada(w) == "formularz_wrazliwy", "Enter w polu E-mail wysłałby formularz z „Zapłać”: wymaga człowieka",
            tekst(w))
    w = k.narzedzie("type_text", {**pisz, "element_token": el["E-mail"]["element_token"], "text": "\n"})
    sprawdz(zasada(w) == "formularz_wrazliwy", "nowa linia w polu E-mail (element z migawki): wymaga człowieka",
            tekst(w))
    w = k.narzedzie("hotkey", {**pisz, "keys": ["ctrl", "v"]})
    sprawdz(zasada(w) == "schowek", "Ctrl+V (schowek właściciela): zablokowane", tekst(w))
    w = k.narzedzie("hotkey", {**pisz, "keys": ["ctrl", "l"]})
    sprawdz(zasada(w) == "skrot_przegladarki", "Ctrl+L (pasek adresu): zablokowane", tekst(w))
    sprawdz(kod(klik("Szukaj w sklepie")) == "ok", "klik w wyszukiwarkę: przechodzi")
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "perfumy"})) == "ok", "pisanie w wyszukiwarce: przechodzi")
    w = k.narzedzie("type_text", {**pisz, "window_id": wid + 1000, "text": "perfumy"})
    sprawdz(zasada(w) == "okno_nieaktywne", "pisanie na wierzchu w oknie, które nie jest aktywne: zablokowane",
            tekst(w))
    w = k.narzedzie("press_key", {**pisz, "key": "Return"})
    sprawdz(kod(w) == "ok", "Enter w wyszukiwarce (formularz bez płatności): przechodzi", tekst(w))
    sprawdz(kod(klik("Hasło")) == "ok", "klik w pole hasła: przechodzi (klik niczego nie wysyła)")
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "tajne-haslo"})) == "wymaga_czlowieka",
            "pisanie w polu hasła (fokus na żywo): wymaga człowieka")
    sprawdz(zasada(k.narzedzie("press_key", {**pisz, "key": "t"})) == "pole_wrazliwe",
            "hasło znak po znaku (press_key w polu hasła): wymaga człowieka")
    sprawdz(kod(k.narzedzie("press_key", {**pisz, "key": "Return"})) == "wymaga_czlowieka",
            "Enter w polu hasła: wymaga człowieka")
    klik("Numer karty")
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "1234"})) == "wymaga_czlowieka",
            "pisanie w polu „Numer karty”: wymaga człowieka")
    klik("Kod BLIK")
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "123456"})) == "wymaga_czlowieka",
            "kod BLIK: wymaga człowieka")
    klik("Uwagi")
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
    k.narzedzie("press_key", {**pisz, "key": "Tab"})
    w = k.narzedzie("press_key", {**pisz, "key": "Return"})
    sprawdz(kod(w) == "wymaga_czlowieka", "Tab na „Kup teraz” i Enter (fokus na żywo): wymaga człowieka", tekst(w))
    klik("Uwagi")
    for znaki, opis in (("\t ", "Tab i spacja"), ("\t\n", "Tab i Enter")):
        w = k.narzedzie("type_text", {**pisz, "text": znaki})
        sprawdz(zasada(w) == "znak_sterujacy", f"{opis} w type_text w „Uwagi”: zablokowane", tekst(w))
    w = k.narzedzie("type_text", {**pisz, "text": "linia\nlinia"})
    sprawdz(zasada(w) == "formularz_wrazliwy", "Enter w „Uwagi” (formularz z „Zapłać”): wymaga człowieka", tekst(w))
    w = k.narzedzie("press_key", {**pisz, "key": "Return", "modifiers": ["shift"]})
    sprawdz(kod(w) == "ok", "Shift+Enter w „Uwagi” (nowa linia): przechodzi", tekst(w))
    w = k.narzedzie("hotkey", {**pisz, "keys": ["ctrl", "Return"]})
    sprawdz(zasada(w) == "formularz_wrazliwy", "Ctrl+Enter w „Uwagi”: wymaga człowieka", tekst(w))
    w = k.narzedzie("hotkey", {**pisz, "keys": ["option", "shift", "k"]})
    sprawdz(zasada(w) == "accesskey", "Alt+Shift+K (accesskey przycisku „Kup teraz”): zablokowane", tekst(w))

    # strona zmieniona od migawki: element dodany na początku formularza przesuwa numery
    w, el = stan_okna()
    stary = el["Dodaj do koszyka"]["element_token"]
    sprawdz(kod(klik("Pokaż baner")) == "ok", "klik „Pokaż baner” (token świeżej migawki od wejścia): przechodzi")
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": stary})
    sprawdz(zasada(w) == "element_zmieniony" and "„Dodaj do koszyka”; zrób" in tekst(w),
            "klik „Dodaj do koszyka” numerem sprzed zmiany strony: zablokowany", tekst(w))
    w, el = stan_okna()
    sprawdz(kod(klik("Dodaj do koszyka")) == "ok", "ten sam klik z nowej migawki: przechodzi")

    # okno podręczne (window.open): osobna karta, sprawdzana w swoim punkcie
    sprawdz(kod(klik("Pokaż szczegóły")) == "ok", "klik „Pokaż szczegóły” (otwiera okno podręczne): przechodzi")
    okno2 = okno_o_tytule(k, "Okno testowe Jarvo", poza=wid)
    if sprawdz(okno2 is not None, "okno podręczne widać w list_windows jako osobne okno"):
        zaplac, w2 = None, {}
        for _ in range(20):
            w2 = k.narzedzie("get_window_state", {"pid": okno2["pid"], "window_id": okno2["window_id"]})
            zaplac = next((e for e in (w2.get("structuredContent") or {}).get("elements", [])
                           if e.get("label") == "Zapłać teraz" and e.get("frame")), None)
            if zaplac:
                break
            time.sleep(0.25)
        if sprawdz(zaplac is not None, "drzewo okna podręcznego ma „Zapłać teraz”"):
            x, y = srodek(zaplac)
            w = k.narzedzie("double_click", {"pid": okno2["pid"], "window_id": okno2["window_id"], "x": x, "y": y})
            sprawdz(kod(w) == "wymaga_czlowieka", "podwójny klik w punkt „Zapłać teraz” w oknie podręcznym: wymaga "
                    "człowieka", tekst(w))
        k.narzedzie("bring_to_front", {"pid": pid, "window_id": wid})

    # dwa żądania z tym samym id: drugie odrzucone, odpowiedź pierwszego nadal bez sekretów
    k.n += 1
    for nazwa in ("get_window_state", "list_apps"):
        k.wyslij({"jsonrpc": "2.0", "id": k.n, "method": "tools/call", "params": {
            "name": nazwa, "arguments": {"pid": pid, "window_id": wid}}})
    odp = []
    while len(odp) < 2:
        m = json.loads(k.p.stdout.readline())
        if m.get("id") == k.n:
            odp.append(m)
    sprawdz(any((m.get("error") or {}).get("code") == -32600 for m in odp)
            and KLUCZ not in json.dumps(odp, ensure_ascii=False), "powtórzone id żądania: odrzucone, klucz dalej ukryty")
    aplikacje = (k.narzedzie("list_apps", {}).get("structuredContent") or {}).get("apps", [])
    sprawdz([a.get("name") for a in aplikacje] == ["Chromium"], "list_apps: tylko przeglądarka Jarva", str(aplikacje))
    sprawdz(kod(k.narzedzie("kill_app", {"pid": os.getpid()})) == "zablokowane",
            "kill_app procesu spoza przeglądarki: zablokowane")

    # filtr ruchu: przeglądarka nie dostanie panelu Jarva ani sieci lokalnej
    przed = ((ster(root, "stan").get("usluga") or {}).get("filtr") or {}).get("zablokowane", 0)
    port_panelu = int(os.environ.get("JARVO_PANEL_PORT") or 9119)
    k.narzedzie("launch_app", {"name": "chromium", "urls": [f"https://127.0.0.1:{port_panelu}/",
                                                            "http://192.168.1.1/"]})
    time.sleep(2)
    po = ((ster(root, "stan").get("usluga") or {}).get("filtr") or {}).get("zablokowane", 0)
    sprawdz(po >= przed + 2, "karty z panelem Jarva i bramą sieci lokalnej: odrzucone przez filtr ruchu",
            f"zablokowane przed {przed}, po {po}")
    k.narzedzie("bring_to_front", {"pid": pid, "window_id": wid})

    # druga sesja (druga karta Operatora): patrzy, ale ekranem steruje ta, która działała ostatnio
    k2 = Klient()
    inicjuj(k2, "komputer-natywny-test-2")
    el2 = po_nazwie((k2.narzedzie("get_window_state", {"pid": pid, "window_id": wid}).get(
        "structuredContent") or {}).get("elements") or [])
    w = k2.narzedzie("click", {"pid": pid, "window_id": wid,
                               "element_token": (el2.get("Dodaj do koszyka") or {}).get("element_token")})
    sprawdz(zasada(w) == "zajete" and (w.get("structuredContent") or {}).get("next_step") == "wait_and_retry",
            "druga sesja: patrzy, ale klik dostaje „zajęte” (jedna sesja naraz)", tekst(w))
    k2.zamknij()

    formularz(k, pid)
    pulapka_fokusu(k, pid)
    ekran_hq(k, root, pid, wid)

    # prośba Operatora i pauza
    w, el = stan_okna()
    odp = ster(root, "pauza", powod="Zaloguj się do sklepu testowego")
    sprawdz((odp.get("pauza") or {}).get("kto") == "flota", "kanał ster: prośba Operatora (pauza od floty z powodem)")
    w = klik("Dodaj do koszyka")
    sprawdz(kod(w) == "wstrzymane" and "Zaloguj się do sklepu testowego" in tekst(w),
            "klik przy prośbie: wstrzymane z powodem prośby", tekst(w))
    sprawdz(ster(root, "pauza").get("wstrzymane") is True, "kanał ster: pauza")
    sprawdz(kod(klik("Dodaj do koszyka")) == "wstrzymane", "klik przy pauzie: wstrzymane")
    _, el = stan_okna()
    sprawdz(bool(el), "patrzenie przy pauzie: działa")
    odp = ster(root, "wznow")
    sprawdz(odp.get("ok") is False and odp.get("wstrzymane") is True, "kanał ster: bez tokenu właściciela pauzy nie "
            "zdejmie (agent floty)")
    odp = ster(root, "wznow", token="zly-token")
    sprawdz(odp.get("ok") is False and odp.get("wstrzymane") is True, "kanał ster: zły token nie zdejmie pauzy")
    sprawdz(ster(root, "wznow", wlasciciel=True).get("wstrzymane") is False,
            "wznowienie przez właściciela (jarvo komputer wznow, token)")
    sprawdz(kod(klik("Dodaj do koszyka")) == "ok", "klik po wznowieniu: przechodzi")

    dziennik = json.dumps(ster(root, "dziennik", n=200), ensure_ascii=False)
    sprawdz('"czlowiek"' in dziennik and '"wstrzymane"' in dziennik, "dziennik ma decyzje człowiek i pauzę")
    sprawdz("tajne-haslo" not in dziennik and "4111" not in dziennik and "Proszę o fakturę" not in dziennik
            and "sklepu testowego" not in dziennik and KLUCZ_PRZYCISK[8:20] not in dziennik
            and "Jan Kowalski" not in dziennik, "dziennik bez wpisywanych treści, bez treści prośby i bez klucza")

    k.narzedzie("end_session", {"session": "komputer-test"})
    k.zamknij()
    zle = [o for ok, o in wyniki if not ok]
    print(f"\n{len(wyniki) - len(zle)}/{len(wyniki)} zaliczone" + (f"; niezaliczone: {', '.join(zle)}" if zle else ""))
    return 1 if zle else 0


def formularz(k: Klient, pid: int) -> None:
    """Operator wypełnia formularz zamówienia; wrażliwe pola, przyciski, okno potwierdzenia, ramka płatności i wybór
    pliku kończą się „oddaj” (wymaga_czlowieka), pobranie programu jest odrzucane."""
    w = k.narzedzie("launch_app", {"name": "chromium", "urls": [FORMULARZ]})
    okno = okno_o_tytule(k, "Zamówienie testowe Jarvo")
    if not sprawdz(okno is not None, "formularz zamówienia otwarty w nowej karcie", tekst(w)):
        return
    wid = okno["window_id"]
    pisz = {"pid": pid, "window_id": wid, "delivery_mode": "foreground"}
    k.narzedzie("bring_to_front", {"pid": pid, "window_id": wid})

    def migawka() -> dict:
        sc = k.narzedzie("get_window_state", {"pid": pid, "window_id": wid}).get("structuredContent") or {}
        return po_nazwie(sc.get("elements", []))

    el = migawka()
    for etykieta, wartosc in (("Imię i nazwisko", "Jan Kowalski"), ("E-mail", "jan@example.com"),
                              ("Telefon", "+48 600 100 200"), ("Adres dostawy", "ul. Testowa 1, 00-001 Warszawa")):
        w = k.narzedzie("type_text", {**pisz, "element_token": el[etykieta]["element_token"], "text": wartosc})
        sprawdz(kod(w) == "ok", f"formularz: Operator wpisuje „{etykieta}”", tekst(w))
    w = k.narzedzie("set_value", {"pid": pid, "window_id": wid, "element_token": el["Dostawa"]["element_token"],
                                  "value": "Paczkomat"})
    sprawdz(kod(w) == "ok", "formularz: lista „Dostawa” przez set_value", tekst(w))
    w = k.narzedzie("click", {"pid": pid, "window_id": wid,
                              "element_token": el["Akceptuję regulamin sklepu"]["element_token"]})
    sprawdz(kod(w) == "ok", "formularz: zaznaczenie regulaminu (zwykłe pole wyboru)", tekst(w))
    el = migawka()
    sprawdz(el.get("Imię i nazwisko", {}).get("value") == "Jan Kowalski", "formularz: wartość pola widać w migawce")
    for etykieta in ("Hasło do konta", "Kod BLIK"):
        w = k.narzedzie("type_text", {**pisz, "element_token": el[etykieta]["element_token"], "text": "123456"})
        sprawdz(kod(w) == "wymaga_czlowieka", f"formularz: „{etykieta}” wpisuje właściciel", tekst(w))
    # ramka płatności to inna witryna (osobny proces): na Windows arm64 z przeglądarką x64 w emulacji jej
    # przygotowanie trwa kilkanaście sekund (CI natywnie WARM: Page.enable ramki po 14 s), więc czekamy jak na kartę
    koniec = time.monotonic() + 45
    while True:
        karta = next((e for e in el.values() if e.get("role") == "entry" and e["label"] == "Numer karty"), None)
        if karta is not None or time.monotonic() >= koniec:
            break
        time.sleep(1)
        el = migawka()
    if sprawdz(karta is not None, "formularz: pole karty z ramki płatności (inna witryna) jest w migawce"):
        w = k.narzedzie("type_text", {**pisz, "element_token": karta["element_token"], "text": "4111"})
        sprawdz(kod(w) == "wymaga_czlowieka", "formularz: numer karty w ramce płatności wpisuje właściciel", tekst(w))
    for etykieta in ("Zapłać 129 zł", "Zapłać kartą"):
        if etykieta in el:
            w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el[etykieta]["element_token"]})
            sprawdz(kod(w) == "wymaga_czlowieka", f"formularz: „{etykieta}” klika właściciel", tekst(w))
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el["Faktura (PDF)"]["element_token"]})
    sprawdz(zasada(w) == "wybor_pliku", "formularz: pole wyboru pliku: plik wybiera właściciel", tekst(w))
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el["Dodaj załącznik"]["element_token"]})
    sprawdz(zasada(w) == "wybor_pliku" and kod(w) == "wymaga_czlowieka",
            "formularz: przycisk otwierający wybór pliku skryptem: wybór pliku robi człowiek", tekst(w))
    # okna potwierdzenia
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el["Podsumowanie"]["element_token"]})
    sprawdz(kod(w) == "ok" and (w.get("structuredContent") or {}).get("dialog"),
            "formularz: zwykły przycisk „Podsumowanie” otwiera okno potwierdzenia płatności", tekst(w))
    dialog = migawka()
    sprawdz("OK" in dialog and "Anuluj" in dialog, "okno potwierdzenia w migawce: OK i Anuluj")
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": dialog["OK"]["element_token"]})
    sprawdz(zasada(w) == "okno_wrazliwe", "OK w oknie „Czy na pewno zapłacić…?”: zatwierdza właściciel", tekst(w))
    w = k.narzedzie("press_key", {**pisz, "key": "Return"})
    sprawdz(zasada(w) == "okno_wrazliwe", "Enter w oknie płatności: zatwierdza właściciel", tekst(w))
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": dialog["Anuluj"]["element_token"]})
    sprawdz(kod(w) == "ok", "Anuluj w oknie płatności: przechodzi", tekst(w))
    el = migawka()
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el["Usuń pozycję"]["element_token"]})
    dialog = migawka()
    if sprawdz("OK" in dialog, "„Usuń pozycję” otwiera zwykłe okno potwierdzenia", tekst(w)):
        w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": dialog["OK"]["element_token"]})
        sprawdz(kod(w) == "ok", "OK w oknie bez płatności i logowania: przechodzi", tekst(w))
    # pobrane pliki: dokument tak, program nie
    el = migawka()
    root = os.environ["JARVO_ROOT"]
    przed = ((ster(root, "stan").get("usluga") or {}).get("pobrania") or {})
    for etykieta in ("Pobierz fakturę", "Pobierz instalator"):
        k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el[etykieta]["element_token"]})
    time.sleep(2)
    po = ((ster(root, "stan").get("usluga") or {}).get("pobrania") or {})
    sprawdz(po.get("pobrane", 0) == przed.get("pobrane", 0) + 1, "pobranie faktury PDF: zapisane w katalogu Komputera")
    sprawdz(po.get("odrzucone", 0) == przed.get("odrzucone", 0) + 1, "pobranie instalatora .exe: odrzucone")
    # baner przykrywa przycisk: klik elementem nie trafi w baner
    k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el["Pokaż baner"]["element_token"]})
    el = migawka()
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el["Pobierz fakturę"]["element_token"]})
    sprawdz(kod(w) == "element_przesloniety", "klik w link przykryty banerem strony: nie klika banera", tekst(w))


def pulapka_fokusu(k: Klient, pid: int) -> None:
    """Pasek adresu jak w Chromium z pulpitu (klik w element 0, type z adresem, key return) otwiera stronę, która
    przenosi fokus z „Kod rabatowy” do pola hasła: sterownik sprawdza fokus tuż przed pisaniem."""
    okno = okno_o_tytule(k, "Zamówienie testowe Jarvo")
    if not sprawdz(okno is not None, "karta formularza zamówienia jest"):
        return
    wid = okno["window_id"]
    k.narzedzie("bring_to_front", {"pid": pid, "window_id": wid})
    pasek = ((k.narzedzie("get_window_state", {"pid": pid, "window_id": wid}).get("structuredContent") or {})
             .get("elements") or [{}])[0]
    sprawdz(pasek.get("label") == "Pasek adresu i wyszukiwania" and pasek.get("value", "").endswith("formularz.html"),
            "element 0 migawki: pasek adresu z adresem karty", json.dumps(pasek, ensure_ascii=False)[:200])
    pisz = {"pid": pid, "window_id": wid, "delivery_mode": "foreground"}
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": pasek.get("element_token")})
    sprawdz(kod(w) == "ok", "klik w pasek adresu: przechodzi", tekst(w))
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "javascript:alert(1)"})) == "zablokowane",
            "pasek adresu: adres javascript: zablokowany")
    sprawdz(kod(k.narzedzie("type_text", {**pisz, "text": "sklep.jarvo.test/fokus.html"})) == "ok",
            "pasek adresu: wpisanie adresu przechodzi")
    sprawdz(kod(k.narzedzie("press_key", {**pisz, "key": "Return"})) == "ok", "pasek adresu: Enter przechodzi")
    okno = okno_o_tytule(k, "Pułapka fokusu Jarvo")
    if not sprawdz(okno is not None and okno["window_id"] == wid,
                   "pasek adresu otworzył stronę w tej samej karcie (jak w Chromium z pulpitu)"):
        return
    el = po_nazwie((k.narzedzie("get_window_state", {"pid": pid, "window_id": wid}).get("structuredContent")
                    or {}).get("elements", []))
    w = k.narzedzie("type_text", {"pid": pid, "window_id": wid, "delivery_mode": "foreground",
                                  "element_token": el["Kod rabatowy"]["element_token"], "text": "RABAT10"})
    sprawdz(kod(w) == "fokus_zmieniony", "pisanie w pole, które przy fokusie przenosi go do hasła: tekst nie trafia do "
            "hasła (fokus_zmieniony)", tekst(w))


def ekran_hq(k: Klient, root: str, pid: int, wid: int) -> None:
    """Ekran w HQ (J10): podgląd i „Przejmij” tylko z tokenem właściciela; przy przejęciu agent stoi, a działanie
    właściciela idzie wprost do karty; „Oddaj” (wznow) oddaje ekran agentowi."""
    import base64
    k.narzedzie("bring_to_front", {"pid": pid, "window_id": wid})
    w = k.narzedzie("get_window_state", {"pid": pid, "window_id": wid})
    sc = w.get("structuredContent") or {}
    el = po_nazwie(sc.get("elements", []))
    sprawdz(ster(root, "klatka").get("ok") is False, "podgląd HQ bez tokenu właściciela: odmowa")
    odp = ster(root, "klatka", wlasciciel=True, czekaj=1.0)
    klatka = odp.get("klatka") or {}
    sprawdz(bool(odp.get("ok")) and klatka.get("aktywne") == wid
            and base64.b64decode(klatka.get("dane") or "")[:3] == b"\xff\xd8\xff",
            "podgląd HQ: klatka JPEG aktywnej karty (Page.startScreencast)", json.dumps(odp)[:200])
    klik = {"typ": "klik"}
    if "Pokaż baner" in el and sc.get("screenshot_width"):
        f = el["Pokaż baner"]["frame"]
        klik.update(x=(f["x"] + f["w"] / 2) / sc["screenshot_width"], y=(f["y"] + f["h"] / 2) / sc["screenshot_height"])
    sprawdz(ster(root, "wejscie", wlasciciel=True, zdarzenie=klik).get("ok") is False,
            "wejście właściciela bez przejęcia ekranu: odmowa (agent i właściciel nie działają naraz)")
    sprawdz(ster(root, "przejmij").get("ok") is False, "Przejmij bez tokenu właściciela: odmowa")
    sprawdz(ster(root, "przejmij", wlasciciel=True).get("przejete") is True, "Przejmij: pauza właściciela")
    w = k.narzedzie("click", {"pid": pid, "window_id": wid, "element_token": el["Dodaj do koszyka"]["element_token"]})
    sprawdz(kod(w) == "wstrzymane", "klik agenta przy przejętym ekranie: wstrzymane", tekst(w))
    przed = sum(1 for e in sc.get("elements", []) if e.get("label") == "Baner")
    sprawdz(ster(root, "wejscie", wlasciciel=True, zdarzenie=klik).get("ok") is True,
            "klik właściciela z podglądu („Pokaż baner”): przechodzi bez twardych zasad")
    po = sum(1 for e in (k.narzedzie("get_window_state", {"pid": pid, "window_id": wid}).get("structuredContent")
                         or {}).get("elements", []) if e.get("label") == "Baner")
    sprawdz(po == przed + 1, "klik właściciela zmienił stronę (nowy przycisk „Baner”)", f"przed {przed}, po {po}")
    sprawdz(ster(root, "wznow", wlasciciel=True).get("wstrzymane") is False, "Oddaj (wznow): ekran wraca do agenta")


def main() -> int:
    root = os.environ.get("JARVO_ROOT")
    if not root:
        print("Ustaw JARVO_ROOT na korzeń próby (instalacja natywna albo katalog próbny).", file=sys.stderr)
        return 2
    uruchom = "--uruchom" in sys.argv[1:]
    if uruchom:
        from jarvo import komputer
        kod_on = komputer.main(["on", "--w-tle", "--strona-testowa", str(REPO / "komputer" / "strona_testowa")],
                               u=sciezki.uklad())
        if kod_on:
            return kod_on
    try:
        return przebieg(root)
    finally:
        if uruchom:
            from jarvo import komputer
            komputer.main(["off"], u=sciezki.uklad())


if __name__ == "__main__":
    sys.exit(main())
