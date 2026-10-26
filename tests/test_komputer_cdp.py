"""Sterownik CDP na prawdziwej przeglądarce (docs/NATYWNIE.md J02, J05, J06, J07): chrome-headless-shell albo Chrome
for Testing z manifestu, wskazany w JARVO_KOMPUTER_CHROME_PROBA (pobrany pobieraczem z sumą). Bez niej testy są
pomijane. Strona testowa (komputer/strona_testowa) przychodzi przez Fetch.fulfillRequest pod https://*.jarvo.test/,
ramka płatności z drugiej witryny (OOPIF). Zasady oceniają opisy ze sterownika tak samo jak w usłudze."""
from __future__ import annotations

import base64
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from komputer import cdp, filtr, przegladarka, sterownik_cdp, zasady_natywne  # noqa: E402

zasady = zasady_natywne.zasady
PROGRAM = os.environ.get("JARVO_KOMPUTER_CHROME_PROBA") or ""
pytestmark = pytest.mark.skipif(not (PROGRAM and Path(PROGRAM).is_file()),
                                reason="potrzebna przeglądarka z manifestu: JARVO_KOMPUTER_CHROME_PROBA")
STRONA = REPO / "komputer" / "strona_testowa"


def wolny_port() -> int:
    for port in range(19202, 19210):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            s.close()
    return 0


class Ctx:
    """Kontekst zasad jak KontekstCDP: cel, punkt i fokus opisuje na żywo sterownik."""

    def __init__(self, st: sterownik_cdp.Sterownik):
        self.st, self.wstrzymane, self.powod_pauzy = st, False, ""

    def cel(self, nazwa, args):
        token = args.get("element_token")
        if token:
            sid, _, i = token.rpartition(":")
            return self.st.opis_elementu(sid, i) or zasady.NIEZNANY
        if args.get("x") is not None:
            return self.st.opis_w_punkcie(args.get("window_id"), args["x"], args["y"]) or zasady.NIEZNANY
        return None

    def fokus(self, args):
        w = self.st.fokus(args.get("window_id"))
        return zasady.NIEZNANY if w is False else w

    def program(self, pid):
        return zasady.PROGRAM_PRZEGLADARKI if pid == self.st.pid else ""

    def aktywne_okno(self):
        return self.st.aktywne_okno()

    def pid_okna(self, okno):
        return self.st.pid


def ocen(ctx, nazwa, args):
    return zasady_natywne.ocen(nazwa, args, ctx) or zasady.ocen(nazwa, args, ctx)


@pytest.fixture(scope="module")
def przegl():
    katalog = Path(tempfile.mkdtemp(prefix="jkc"))
    proxy = filtr.Proxy(port=wolny_port())
    proxy.start()
    profil, pobrane = katalog / "profil", katalog / "pobrane"
    przegladarka.przygotuj_profil(profil, pobrane)
    b = cdp.Przegladarka(PROGRAM, przegladarka.flagi(profil=profil, port_proxy=proxy.port, okno=False),
                         log=katalog / "przegladarka.log")
    b.start()
    st = sterownik_cdp.Sterownik(b, pobrane=pobrane, strona_testowa=STRONA)
    st.start()
    yield st, proxy, pobrane
    b.zamknij()
    proxy.zatrzymaj()
    assert b.proces.poll() is not None
    shutil.rmtree(katalog, ignore_errors=True)


def otworz(st, url: str) -> int:
    w = st.wywolaj("launch_app", {"name": "Chromium", "urls": [url]}, {})
    nr = w["structuredContent"]["windows"][0]["window_id"]
    for _ in range(40):
        st.wywolaj("list_windows", {}, {})
        if st.okno(nr) and st.okno(nr).url.startswith(url.split("#")[0]) and st.okno(nr).tytul and \
                "jarvo.test" not in st.okno(nr).tytul:
            break
        time.sleep(0.25)
    return nr


def migawka(st, nr) -> tuple[dict, dict]:
    sc = st.wywolaj("get_window_state", {"pid": st.pid, "window_id": nr}, {"max_image_dimension": 1456})[
        "structuredContent"]
    po = {}
    for e in sc["elements"]:
        if e.get("label") and (e["label"] not in po or po[e["label"]]["role"] in ("static", "paragraph", "label")):
            po[e["label"]] = e
    return sc, po


def test_cdp_przez_potok_bez_portu(przegl):
    st, _, _ = przegl
    assert st.b.wyslij("Browser.getVersion")["product"]
    assert "--remote-debugging-port" not in " ".join(st.b.argumenty)


def test_migawka_formularza_z_rolami_zasad_i_ramka_platnosci(przegl):
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/formularz.html")
    sc, el = migawka(st, nr)
    assert sc["screenshot_width"] and sc["snapshot_id"] and el["Zamówienie testowe Jarvo"]["role"] == "document web"
    assert el["Hasło do konta"]["role"] == "password text" and el["Zapłać 129 zł"]["role"] == "push button"
    assert el["Imię i nazwisko"]["role"] == "entry" and el["Dostawa"]["role"] == "combo box"
    karta = el["Numer karty"]
    assert karta["role"] == "entry" and karta["frame"]["x"] > el["Płatność kartą"]["frame"]["x"]
    assert st.okno(nr).ramki, "ramka płatności z innej witryny to osobny proces (OOPIF)"
    assert all(e["element_token"].startswith(sc["snapshot_id"] + ":") for e in sc["elements"])


def test_operator_wypelnia_formularz_a_wrazliwe_konczy_oddaj(przegl):
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/formularz.html")
    ctx = Ctx(st)
    _, el = migawka(st, nr)
    cel = {"pid": st.pid, "window_id": nr}
    for etykieta, tekst in (("Imię i nazwisko", "Jan Kowalski"), ("E-mail", "jan@example.com")):
        args = {**cel, "element_token": el[etykieta]["element_token"], "text": tekst}
        assert ocen(ctx, "type_text", args).wolno, etykieta
        w = st.wywolaj("type_text", args, {})
        assert w["structuredContent"]["effect"] == "confirmed", w
    _, el = migawka(st, nr)
    assert el["Imię i nazwisko"]["value"] == "Jan Kowalski"
    for etykieta, nazwa, args in (
            ("Hasło do konta", "type_text", {"text": "tajne"}), ("Kod BLIK", "type_text", {"text": "123456"}),
            ("Numer karty", "type_text", {"text": "4111"}), ("Zapłać 129 zł", "click", {}),
            ("Zapłać kartą", "click", {}), ("Faktura (PDF)", "click", {})):
        w = ocen(ctx, nazwa, {**cel, "element_token": el[etykieta]["element_token"], **args})
        assert w.decyzja == zasady.CZLOWIEK, (etykieta, w.kod, w.powod)
    # pole z fokusem na żywo: po kliknięciu w pole hasła pisanie bez celu też robi właściciel
    st.wywolaj("click", {**cel, "element_token": el["Hasło do konta"]["element_token"]}, {})
    w = ocen(ctx, "type_text", {**cel, "delivery_mode": "foreground", "text": "tajne"})
    assert (w.decyzja, w.kod) == (zasady.CZLOWIEK, "pole_wrazliwe")
    # Enter w polu e-mail wysłałby formularz z przyciskiem płatności
    st.wywolaj("click", {**cel, "element_token": el["E-mail"]["element_token"]}, {})
    w = ocen(ctx, "press_key", {**cel, "delivery_mode": "foreground", "key": "Return"})
    assert w.kod == "formularz_wrazliwy"


def test_okno_potwierdzenia_wybor_pliku_baner_i_pobrania(przegl):
    st, _, pobrane = przegl
    nr = otworz(st, "https://sklep.jarvo.test/formularz.html")
    ctx = Ctx(st)
    cel = {"pid": st.pid, "window_id": nr}
    _, el = migawka(st, nr)
    w = st.wywolaj("click", {**cel, "element_token": el["Podsumowanie"]["element_token"]}, {})
    assert w["structuredContent"].get("dialog") == {"type": "confirm"}
    _, okno = migawka(st, nr)
    assert ocen(ctx, "click", {**cel, "element_token": okno["OK"]["element_token"]}).kod == "okno_wrazliwe"
    assert ocen(ctx, "click", {**cel, "element_token": okno["Anuluj"]["element_token"]}).wolno
    assert st.wywolaj("click", {**cel, "element_token": okno["Anuluj"]["element_token"]}, {})["structuredContent"][
        "effect"] == "confirmed"
    _, el = migawka(st, nr)
    w = st.wywolaj("click", {**cel, "element_token": el["Dodaj załącznik"]["element_token"]}, {})
    assert w["isError"] and w["structuredContent"]["rule"] == "wybor_pliku"
    przed = dict(st.statystyki)
    for etykieta in ("Pobierz fakturę", "Pobierz instalator"):
        st.wywolaj("click", {**cel, "element_token": el[etykieta]["element_token"]}, {})
    for _ in range(40):
        if st.statystyki["pobrane"] > przed["pobrane"] and st.statystyki["odrzucone"] > przed["odrzucone"]:
            break
        time.sleep(0.25)
    assert st.statystyki["pobrane"] == przed["pobrane"] + 1 and st.statystyki["odrzucone"] == przed["odrzucone"] + 1
    assert any(p.name.startswith("faktura") for p in pobrane.iterdir())
    assert not any(p.suffix == ".exe" for p in pobrane.rglob("*"))
    st.wywolaj("click", {**cel, "element_token": el["Pokaż baner"]["element_token"]}, {})
    _, el = migawka(st, nr)
    w = st.wywolaj("click", {**cel, "element_token": el["Pobierz fakturę"]["element_token"]}, {})
    assert w["structuredContent"]["code"] == "element_przesloniety"


def test_padnieta_karta_wraca_po_ponownym_wczytaniu(przegl):
    """CI natywnie WARM (Chrome x64 w emulacji na Windows arm64): proces karty pada przy starcie strony, a martwa
    karta nie miała tytułu i polecenia do niej czekały do limitu. Sterownik wczytuje ją ponownie (najwyżej 3 razy
    na minutę). Tu padnięcie wywołuje Page.crash."""
    st, _, _ = przegl
    logi = []
    st.log = logi.append
    nr = otworz(st, "https://sklep.jarvo.test/formularz.html")
    okno = st.okno(nr)
    tytul = okno.tytul
    assert tytul and "jarvo.test" not in tytul
    try:
        st.b.wyslij("Page.crash", {}, okno.sesja, czas=3)
    except cdp.BladCDP:
        pass                                          # odpowiedzi nie ma: proces karty już nie żyje
    for _ in range(80):
        if any("wczytuję ją ponownie" in x for x in logi) and okno.tytul == tytul:
            try:
                if st.b.wyslij("Runtime.evaluate", {"expression": "document.title", "returnByValue": True},
                               okno.sesja, czas=3)["result"]["value"] == tytul:
                    break
            except cdp.BladCDP:
                pass
        time.sleep(0.25)
    else:
        raise AssertionError(f"karta nie wróciła: {logi}")
    assert sum("wczytuję ją ponownie" in x for x in logi) == 1, logi    # kilka zdarzeń jednego padnięcia = raz
    assert st.wywolaj("get_window_state", {"pid": st.pid, "window_id": nr}, {"max_image_dimension": 800})[
        "structuredContent"]["elements"]


def test_klik_w_punkt_trafia_w_element_strony(przegl):
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/sklep.html")
    ctx = Ctx(st)
    _, el = migawka(st, nr)
    f = el["Zapłać 129 zł"]["frame"]
    w = ocen(ctx, "click", {"pid": st.pid, "window_id": nr, "x": f["x"] + f["w"] / 2, "y": f["y"] + f["h"] / 2,
                            "delivery_mode": "foreground"})
    assert w.kod == "przycisk_wrazliwy"
    w = ocen(ctx, "click", {"pid": st.pid, "window_id": nr, "x": 99999, "y": 5, "delivery_mode": "foreground"})
    assert w.kod == "nieznany_cel"


def test_natywny_test_komputera_na_zywo(tmp_path):
    """Cała droga jak u Hermesa: `jarvo komputer on` (usługa: proxy z samotestem, przeglądarka, wejście z zasadami),
    bramka floty, 134 sprawdzenia scripts/komputer_natywny_test.py, `jarvo komputer off`."""
    import subprocess
    root = Path(tempfile.mkdtemp(prefix="jkz"))
    env = {**os.environ, "JARVO_ROOT": str(root), "JARVO_PANEL_PORT": "19200",
           "JARVO_KOMPUTER_PORT_PROXY": str(wolny_port()), "PYTHONUTF8": "1"}
    env.pop("JARVO_KOMPUTER_GNIAZDO", None)
    try:
        wynik = subprocess.run([sys.executable, "-I", "-X", "utf8", str(REPO / "scripts" / "komputer_natywny_test.py"),
                                "--uruchom"], capture_output=True, text=True, encoding="utf-8", env=env, timeout=600)
        assert wynik.returncode == 0, (wynik.stdout[-3000:], wynik.stderr[-2000:])
        assert " zaliczone" in wynik.stdout and "niezaliczone" not in wynik.stdout
        assert not (root / "stan" / "komputer" / "usluga.json").exists()         # usługa zatrzymana i posprzątana
    finally:
        shutil.rmtree(root, ignore_errors=True)


def js(st, nr, wyrazenie: str, czekaj: bool = False):
    """Wyrażenie w głównym świecie strony karty `nr` (tylko w testach: sprawdzenie stanu strony)."""
    w = st.b.wyslij("Runtime.evaluate", {"expression": wyrazenie, "returnByValue": True, "awaitPromise": czekaj},
                    st.okno(nr).sesja, czas=30)
    return (w.get("result") or {}).get("value")


def udp(port: int) -> socket.socket:
    """Słuchacz UDP na 127.0.0.1 (port z zakresu próby, a zajęty: dowolny wolny)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        s.bind(("127.0.0.1", 0))
    s.settimeout(0.3)
    return s


def test_webrtc_i_webtransport_bez_udp_poza_proxy(przegl):
    """WebRTC (STUN) i WebTransport (QUIC) idą po UDP, czyli poza proxy: przeglądarka Jarva nie wysyła ani jednego
    datagramu (flaga --force-webrtc-ip-handling-policy=disable_non_proxied_udp; bez niej STUN dochodzi do
    127.0.0.1, sprawdzone na chrome-headless-shell 153 i Chrome for Testing 156)."""
    st, _, _ = przegl
    stun, quic = udp(19208), udp(19209)
    odebrane: list = []

    def sluchaj(s):
        koniec = time.time() + 15
        while time.time() < koniec:
            try:
                odebrane.append(s.recvfrom(4096)[1])
            except (TimeoutError, socket.timeout):
                pass
            except OSError:
                return
    watki = [threading.Thread(target=sluchaj, args=(s,), daemon=True) for s in (stun, quic)]
    for w in watki:
        w.start()
    try:
        nr = otworz(st, "https://sklep.jarvo.test/sklep.html")
        wynik = js(st, nr, """(async () => {
          const w = {kandydaci: []};
          const pc = new RTCPeerConnection({iceServers: [{urls: 'stun:127.0.0.1:%d'}]});
          pc.createDataChannel('x');
          pc.onicecandidate = e => { if (e.candidate) w.kandydaci.push(e.candidate.candidate); };
          await pc.setLocalDescription(await pc.createOffer());
          await new Promise(r => setTimeout(r, 3000));
          pc.close();
          if (typeof WebTransport !== 'undefined') {
            try { const t = new WebTransport('https://127.0.0.1:%d/');
                  w.wt = await Promise.race([t.ready.then(() => 'gotowe'),
                                             new Promise(r => setTimeout(() => r('czas'), 3000))]);
            } catch (e) { w.wt = 'blad'; }
          }
          return w; })()""" % (stun.getsockname()[1], quic.getsockname()[1]), czekaj=True)
        time.sleep(1)
    finally:
        for s in (stun, quic):
            s.close()
    assert wynik["kandydaci"] == [], wynik
    assert wynik.get("wt") in (None, "blad"), wynik
    assert odebrane == [], odebrane


def test_podglad_i_wejscie_wlasciciela(przegl):
    """Ekran w HQ (J10): klatki Page.startScreencast aktywnej karty, a „Przejmij”: klik, tekst, okno JavaScript
    i plik od właściciela wprost do karty (bez twardych zasad: robi je człowiek)."""
    st, _, pobrane = przegl
    nr = otworz(st, "https://sklep.jarvo.test/formularz.html")
    st.wywolaj("bring_to_front", {"window_id": nr}, {})
    k = st.podglad()
    assert k["typ"] == "image/jpeg" and base64.b64decode(k["dane"])[:3] == b"\xff\xd8\xff" and k["aktywne"] == nr
    assert k["szer_css"] and k["wys_css"] and any(o["window_id"] == nr for o in k["okna"])
    for _ in range(20):                         # strona dorysowuje jeszcze ramkę płatności: do pierwszej ciszy
        nastepna = st.podglad(po=k["nr"], czekaj=0.3)
        if nastepna.get("bez_zmian"):
            break
        k = nastepna
    assert nastepna["bez_zmian"] is True and nastepna["nr"] == k["nr"]
    sc, el = migawka(st, nr)
    sz, wy = st.okno(nr).rozmiar

    def ulamek(e):
        f = e["frame"]
        skala = st.okno(nr).skala
        return (f["x"] + f["w"] / 2) / skala / sz, (f["y"] + f["h"] / 2) / skala / wy
    x, y = ulamek(el["Sprawdź dane"])
    assert st.wejscie_wlasciciela({"typ": "klik", "x": x, "y": y}) == {"ok": True}
    assert js(st, nr, "document.getElementById('wynik').textContent") == "Dane sprawdzone"
    assert st.podglad(po=k["nr"], czekaj=3)["nr"] > k["nr"]                 # zmiana strony: nowa klatka
    x, y = ulamek(el["Hasło do konta"])
    st.wejscie_wlasciciela({"typ": "klik", "x": x, "y": y})
    assert st.wejscie_wlasciciela({"typ": "tekst", "tekst": "haslo-wlasciciela"})["ok"]
    assert js(st, nr, "document.querySelector('[name=haslo]').value") == "haslo-wlasciciela"
    # okno potwierdzenia płatności zatwierdza właściciel
    x, y = ulamek(el["Podsumowanie"])
    st.wejscie_wlasciciela({"typ": "klik", "x": x, "y": y})
    klatka = st.podglad(czekaj=0.5)
    assert klatka["dialog"]["typ"] == "confirm" and "zapłacić" in klatka["dialog"]["wiadomosc"]
    assert st.wejscie_wlasciciela({"typ": "klik", "x": 0.5, "y": 0.5})["ok"] is False      # strona stoi pod oknem
    assert st.wejscie_wlasciciela({"typ": "dialog", "ok": True}) == {"ok": True}
    assert js(st, nr, "window.potwierdzone") is True
    # wybór pliku: właściciel klika „Dodaj załącznik”, a plik bierze tylko z katalogu wysylane
    (st.wysylane).mkdir(parents=True, exist_ok=True)
    (st.wysylane / "faktura-wlasciciela.pdf").write_bytes(b"%PDF-1.4 test")
    x, y = ulamek(el["Dodaj załącznik"])
    st.wejscie_wlasciciela({"typ": "klik", "x": x, "y": y})
    for _ in range(20):
        if st.okno(nr).wybor_wlasciciela:
            break
        time.sleep(0.1)
    assert st.podglad(czekaj=0.3).get("wybor_pliku") or st.okno(nr).wybor_wlasciciela
    assert st.wejscie_wlasciciela({"typ": "plik", "pliki": ["../pobrane"]})["ok"] is False
    assert st.wejscie_wlasciciela({"typ": "plik", "pliki": ["faktura-wlasciciela.pdf"]}) == {"ok": True, "pliki": 1}
    assert js(st, nr, "document.querySelector('[name=faktura]').files[0].name") == "faktura-wlasciciela.pdf"
    assert st.wejscie_wlasciciela({"typ": "adres", "url": "file:///C:/"})["ok"] is False
    assert st.wejscie_wlasciciela({"typ": "adres", "url": "https://sklep.jarvo.test/sklep.html"})["ok"]
    st.zatrzymaj_podglad()
    assert not st.podglad_wlaczony


def test_pasek_adresu_jak_w_chromium_z_pulpitu(przegl):
    """Element 0 migawki to pasek adresu (ta sama nazwa co w Chromium z pulpitu): klik, type z adresem, key return
    otwiera stronę bez zmian w poleceniach Operatora; adresy spoza http(s) nie przechodzą."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/sklep.html")
    ctx = Ctx(st)
    cel = {"pid": st.pid, "window_id": nr}
    sc, _ = migawka(st, nr)
    pasek = sc["elements"][0]
    assert (pasek["role"], pasek["label"], pasek["value"]) == ("entry", sterownik_cdp.PASEK,
                                                               "https://sklep.jarvo.test/sklep.html")
    klik = {**cel, "element_token": pasek["element_token"]}
    assert ocen(ctx, "click", klik).wolno
    assert st.wywolaj("click", klik, {})["structuredContent"]["effect"] == "confirmed"
    pisz = {**cel, "delivery_mode": "foreground", "text": "sklep.jarvo.test/formularz.html"}
    assert ocen(ctx, "type_text", pisz).wolno
    assert st.wywolaj("type_text", pisz, {})["structuredContent"]["effect"] == "confirmed"
    enter = {**cel, "delivery_mode": "foreground", "key": "Return"}
    assert ocen(ctx, "press_key", enter).wolno
    assert not st.wywolaj("press_key", enter, {}).get("isError")
    for _ in range(40):
        st.wywolaj("list_windows", {}, {})
        if st.okno(nr).tytul == "Zamówienie testowe Jarvo":
            break
        time.sleep(0.25)
    assert st.okno(nr).url == "https://sklep.jarvo.test/formularz.html" and st.okno(nr).pasek is None
    # javascript: odrzucają zasady tekstu, file: sam pasek (gdyby zasady przepuściły)
    st.wywolaj("click", klik | {"element_token": migawka(st, nr)[0]["elements"][0]["element_token"]}, {})
    assert not ocen(ctx, "type_text", {**pisz, "text": "javascript:alert(1)"}).wolno
    w = st.wywolaj("type_text", {**pisz, "text": "file:///C:/Windows/win.ini\n"}, {})
    assert w["isError"] and w["structuredContent"]["code"] == "adres" and st.okno(nr).url.startswith("https://")


def test_skrypt_strony_przenosi_fokus_do_hasla(przegl):
    """Pole „Kod rabatowy” przy fokusie przenosi go do pola hasła: tekst, który zasady przepuściły dla zwykłego
    pola, nie trafi do hasła (fokus sprawdzony tuż przed pisaniem)."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/fokus.html")
    ctx = Ctx(st)
    _, el = migawka(st, nr)
    cel = {"pid": st.pid, "window_id": nr}
    args = {**cel, "element_token": el["Kod rabatowy"]["element_token"], "text": "RABAT10"}
    assert ocen(ctx, "type_text", args).wolno                     # zwykłe pole: zasady przepuszczają
    w = st.wywolaj("type_text", args, {})
    assert w["isError"] and w["structuredContent"]["code"] == "fokus_zmieniony", w
    assert js(st, nr, "document.querySelector('[name=haslo]').value") == ""
    # pisanie bez celu: zasady oceniły pole „Uwagi”, a strona przeniosła fokus do hasła przed pisaniem
    st.wywolaj("click", {**cel, "element_token": el["Uwagi"]["element_token"]}, {})
    assert ocen(ctx, "type_text", {**cel, "text": "abc"}).wolno
    js(st, nr, "document.querySelector('[name=haslo]').focus()")
    w = st.wywolaj("type_text", {**cel, "text": "abc"}, {})
    assert w["structuredContent"]["code"] == "fokus_zmieniony" and js(st, nr, "document.querySelector("
                                                                         "'[name=haslo]').value") == ""
    st.wywolaj("click", {**cel, "element_token": el["Uwagi"]["element_token"]}, {})
    assert ocen(ctx, "type_text", {**cel, "text": "abc"}).wolno
    assert st.wywolaj("type_text", {**cel, "text": "abc"}, {})["structuredContent"]["effect"] == "confirmed"
    # znak po znaku: w polu hasła robi właściciel, a fokus przeniesiony po ocenie zatrzymuje klawisz
    assert ocen(ctx, "press_key", {**cel, "key": "x"}).wolno
    js(st, nr, "document.querySelector('[name=haslo]').focus()")
    w = st.wywolaj("press_key", {**cel, "key": "x"}, {})
    assert w["structuredContent"]["code"] == "fokus_zmieniony" and js(st, nr, "document.querySelector("
                                                                         "'[name=haslo]').value") == ""
    w = ocen(ctx, "press_key", {**cel, "key": "x"})
    assert (w.decyzja, w.kod) == (zasady.CZLOWIEK, "pole_wrazliwe")


def test_file_i_siec_lokalna_zablokowane(przegl):
    st, proxy, _ = przegl
    nr = otworz(st, "file:///")
    time.sleep(1)
    st.wywolaj("list_windows", {}, {})
    assert not st.okno(nr).url.startswith("file:")
    przed = proxy.statystyki.zablokowane
    port = wolny_port()
    serwer = socket.socket()
    serwer.bind(("127.0.0.1", port))
    serwer.listen(4)
    serwer.settimeout(0.5)
    try:
        otworz(st, f"http://127.0.0.1:{port}/panel")
        time.sleep(1.5)
        with pytest.raises((TimeoutError, socket.timeout)):
            serwer.accept()                         # przeglądarka nie dotarła do serwera na pętli zwrotnej
    finally:
        serwer.close()
    assert proxy.statystyki.zablokowane > przed
