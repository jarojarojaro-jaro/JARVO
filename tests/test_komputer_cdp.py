"""Sterownik CDP na prawdziwej przeglądarce (docs/NATYWNIE.md J02, J05, J06, J07): chrome-headless-shell albo Chrome
for Testing z manifestu, wskazany w JARVO_KOMPUTER_CHROME_PROBA (pobrany pobieraczem z sumą). Bez niej testy są
pomijane. Na Linuksie bez przestrzeni nazw użytkownika (AppArmor) przeglądarka wstaje z --no-sandbox, tak samo jak
w usłudze (przegladarka.brak_piaskownicy). Strona testowa (komputer/strona_testowa) przychodzi przez
Fetch.fulfillRequest pod https://*.jarvo.test/, ramka płatności z drugiej witryny (OOPIF). Zasady oceniają opisy ze
sterownika tak samo jak w usłudze."""
from __future__ import annotations

import base64
import json
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
from komputer import cdp, filtr, kanal, przegladarka, sterownik_cdp, wejscie_natywne, zasady_natywne  # noqa: E402

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
    log = katalog / "przegladarka.log"
    for bez_piaskownicy in (False, True):            # jak usługa: Linux bez przestrzeni nazw użytkownika (I41)
        b = cdp.Przegladarka(PROGRAM, przegladarka.flagi(profil=profil, port_proxy=proxy.port, okno=False,
                                                         bez_piaskownicy=bez_piaskownicy), log=log)
        b.start()
        try:
            b.wyslij("Browser.getVersion", czas=30)
            break
        except cdp.BladCDP:
            b.zamknij(5)
            if bez_piaskownicy or not (przegladarka.LINUX and przegladarka.brak_piaskownicy(log)):
                raise
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
        w = st.wywolaj("click", {**cel, "element_token": el[etykieta]["element_token"]}, {})
        assert w["structuredContent"]["effect"] == "confirmed" and "pobieranie pliku" in w["content"][0]["text"], w
    for _ in range(40):
        if st.statystyki["pobrane"] > przed["pobrane"] and st.statystyki["odrzucone"] > przed["odrzucone"]:
            break
        time.sleep(0.25)
    assert st.statystyki["pobrane"] == przed["pobrane"] + 1 and st.statystyki["odrzucone"] == przed["odrzucone"] + 1
    assert any(p.name.startswith("faktura") for p in pobrane.iterdir())
    assert not any(p.suffix == ".exe" for p in pobrane.rglob("*"))
    st.wywolaj("click", {**cel, "element_token": el["Pokaż baner"]["element_token"]}, {})
    _, po = migawka(st, nr)
    assert "Pobierz fakturę" not in po and "Ten baner przykrywa dół strony" in po    # środek pod banerem: pominięty
    w = st.wywolaj("click", {**cel, "element_token": el["Pobierz fakturę"]["element_token"]}, {})  # numer sprzed banera
    assert w["structuredContent"]["code"] == "element_przesloniety"
    assert w["structuredContent"]["zasloniety_przez"]["napis"] == "Ten baner przykrywa dół strony"


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


def test_klik_elementem_na_przewinietej_stronie_i_pod_warstwa_bez_zdarzen(przegl):
    """Długa strona: przycisk 1500 px niżej (sterownik przewija stronę) i przycisk pod warstwą na cały ekran
    z pointer-events: none. Dotąd sprawdzenie punktu pytało o układ okna zamiast dokumentu i trafiało w warstwę,
    więc oba kliknięcia kończyły się fałszywym `element_przesloniety`. Paragon: zmiana strony = `confirmed`,
    przycisk bez działania = `suspected_noop`."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/dluga.html")
    cel = {"pid": st.pid, "window_id": nr}
    sc, el = migawka(st, nr)
    assert "offscreen" in el["Przycisk na dole"]["states"] and "offscreen" not in el["Przycisk na górze"].get(
        "states", [])
    pozycja = {e["label"]: i for i, e in enumerate(sc["elements"])}
    assert pozycja["Przycisk na górze"] < pozycja["Przycisk na dole"] < pozycja["Koniec strony"]
    w = st.wywolaj("click", {**cel, "element_token": el["Przycisk na dole"]["element_token"]}, {})
    assert not w["isError"] and w["structuredContent"]["effect"] == "confirmed", w
    assert "nowe: paragraph „Kliknięto dół”" in w["structuredContent"]["message"]
    assert js(st, nr, "document.getElementById('wynik').textContent") == "Kliknięto dół" and js(st, nr, "scrollY") > 0
    w = st.wywolaj("click", {**cel, "element_token": el["Przycisk na górze"]["element_token"]}, {})
    assert w["structuredContent"]["effect"] == "confirmed", w
    assert js(st, nr, "document.getElementById('wynik').textContent") == "Kliknięto górę"
    w = st.wywolaj("click", {**cel, "element_token": el["Nic nie robi"]["element_token"]}, {})
    assert w["structuredContent"]["effect"] == "suspected_noop", w
    assert "nie powtarzaj" in w["structuredContent"]["message"]


def test_okno_zgody_na_gorze_migawki_a_przykryty_element_z_zasloniety_przez(przegl):
    """Okno zgody leży na końcu DOM i przykrywa całą stronę: w migawce jest zaraz po pasku adresu (numery poniżej
    10), elementy pod nim znikają, a klik elementem numerem sprzed okna kończy się odmową z tym, co zasłania."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/dluga.html")
    cel = {"pid": st.pid, "window_id": nr}
    _, el = migawka(st, nr)
    w = st.wywolaj("click", {**cel, "element_token": el["Pokaż zgodę"]["element_token"]}, {})
    assert w["structuredContent"]["effect"] == "confirmed" and "dialog „Zgoda na ciasteczka”" in w["content"][0][
        "text"], w
    sc, po = migawka(st, nr)
    assert [e["label"] for e in sc["elements"][1:5]] == ["Zgoda na ciasteczka", "Ta strona używa ciasteczek.",
                                                         "Akceptuję", "Odrzucam"]
    assert po["Akceptuję"]["element_index"] < 10 and po["Zgoda na ciasteczka"]["role"] == "dialog"
    assert "Przycisk na górze" not in po and sc["covered_count"] > 0
    w = st.wywolaj("click", {**cel, "element_token": el["Przycisk na górze"]["element_token"]}, {})
    assert w["isError"] and w["structuredContent"]["code"] == "element_przesloniety", w
    assert w["structuredContent"]["zasloniety_przez"] == {"rola": "dialog", "napis": "Zgoda na ciasteczka",
                                                          "element_index": po["Zgoda na ciasteczka"]["element_index"]}
    assert js(st, nr, "document.getElementById('wynik').textContent") == "Nic nie kliknięto"
    w = st.wywolaj("click", {**cel, "element_token": po["Akceptuję"]["element_token"]}, {})
    assert w["structuredContent"]["effect"] == "confirmed" and "zniknęło: dialog „Zgoda na ciasteczka”" in w[
        "structuredContent"]["message"], w
    _, po = migawka(st, nr)
    assert "Przycisk na górze" in po and "Akceptuję" not in po


def test_klik_w_punkt_w_zaplac_po_przewinieciu_wymaga_czlowieka(przegl):
    """Zasady oceniają klik w punkt po elemencie, który Chrome naprawdę kliknie: na przewiniętej stronie pod
    przezroczystą warstwą bez zdarzeń wskaźnika w punkcie leży „Zapłać 129 zł”, więc klik robi człowiek. Dotąd
    sterownik opisywał zasadom element o przewinięcie wyżej albo warstwę i klik w płatność mógł przejść."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/dluga.html")
    ctx = Ctx(st)
    js(st, nr, "document.querySelector('button[type=submit]').scrollIntoView({block: 'center'})")
    assert js(st, nr, "scrollY") > 1000
    _, el = migawka(st, nr)
    f = el["Zapłać 129 zł"]["frame"]
    assert "offscreen" not in el["Zapłać 129 zł"].get("states", [])
    punkt = {"pid": st.pid, "window_id": nr, "x": f["x"] + f["w"] / 2, "y": f["y"] + f["h"] / 2,
             "delivery_mode": "foreground"}
    opis = st.opis_w_punkcie(nr, punkt["x"], punkt["y"])
    assert (opis["rola"], opis["nazwa"]) == ("push button", "Zapłać 129 zł"), opis
    w = ocen(ctx, "click", punkt)
    assert (w.decyzja, w.kod) == (zasady.CZLOWIEK, "przycisk_wrazliwy"), (w.kod, w.powod)


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
    otwiera stronę bez zmian w poleceniach Operatora, a type z nową linią na końcu robi to w jednym wywołaniu
    (paragon `adres: …`); adresy spoza http(s) nie przechodzą."""
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
    w = st.wywolaj("press_key", enter, {})
    assert w["structuredContent"]["effect"] == "confirmed" and "adres: sklep.jarvo.test/formularz.html" in w[
        "structuredContent"]["message"], w
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
    # adres w dwóch krokach: klik w pasek i `type` z nową linią na końcu (Enter w tym samym wywołaniu)
    st.wywolaj("click", klik | {"element_token": migawka(st, nr)[0]["elements"][0]["element_token"]}, {})
    jednym = {**pisz, "text": "sklep.jarvo.test/dluga.html\n"}
    assert ocen(ctx, "type_text", jednym).wolno
    w = st.wywolaj("type_text", jednym, {})
    assert w["structuredContent"]["effect"] == "confirmed" and "adres: sklep.jarvo.test/dluga.html" in w[
        "structuredContent"]["message"], w


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


def test_adres_zakazany_cofniety_bez_zdarzen_strony(przegl):
    """Chrome for Testing 156 nie wstrzymuje pierwszej nawigacji karty z Target.createTarget do
    Runtime.runIfWaitingForDebugger (chrome-headless-shell 153 tak): gdy podpięcie karty się spóźniło, file:///
    wczytywał się przed Fetch.enable i Page.enable, bez Fetch.requestPaused i zdarzeń Page.*, i zostawał w karcie.
    Cofnięcie idzie też po zmianie celu (Target.targetInfoChanged, zdarzenie przeglądarki): karta bez Fetch i Page
    przechodzi na file:/// i wraca na pustą stronę."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/sklep.html")
    okno = st.okno(nr)

    def adres():
        try:
            return js(st, nr, "location.href")
        except cdp.BladCDP:
            return None                                  # strona w trakcie nawigacji
    przed = st.statystyki["nawigacje_zablokowane"]
    st.b.wyslij("Fetch.disable", {}, okno.sesja)
    st.b.wyslij("Page.disable", {}, okno.sesja)
    try:
        st.b.wyslij("Page.navigate", {"url": "file:///"}, okno.sesja)
        for _ in range(40):
            if adres() == "about:blank":
                break
            time.sleep(0.25)
        assert adres() == "about:blank" and okno.url == "about:blank"
        assert st.statystyki["nawigacje_zablokowane"] > przed
    finally:
        st.b.wyslij("Page.enable", {}, okno.sesja)
        st.b.wyslij("Fetch.enable", {"patterns": st._wzorce_fetch()}, okno.sesja)


def test_karta_zamknieta_w_trakcie_przygotowania_bez_czekania(przegl, monkeypatch):
    """Samotest proxy usługi otwiera kartę i zamyka ją zaraz po odmowie filtra. Chrome nie odpowiada na polecenia
    odłączonej sesji, więc przygotowanie tej karty (Page.enable…) czekało 4 × 15 s i zostawiało w komputer.log
    cztery wpisy „nie odpowiedziała w czasie”. Odłączenie kończy je od razu (cdp.KoniecCelu), bez wpisu."""
    st, proxy, _ = przegl
    logi: list = []
    monkeypatch.setattr(st, "log", logi.append)
    monkeypatch.setattr(sterownik_cdp, "CZAS_PRZYGOTOWANIA", 2.0)
    przed = proxy.statystyki.zablokowane
    cel = st.b.wyslij("Target.createTarget", {"url": f"https://127.0.0.1:{wolny_port()}/jarvo-samotest"})["targetId"]
    koniec = time.monotonic() + 15
    while time.monotonic() < koniec and proxy.statystyki.zablokowane == przed:
        time.sleep(0.01)
    st.b.wyslij("Target.closeTarget", {"targetId": cel}, czas=5)
    time.sleep(3)
    assert proxy.statystyki.zablokowane > przed and cel not in st._po_celu
    assert not [x for x in logi if "nie odpowiedziała" in x], logi


def test_postoj_przenosi_strony_na_pusta_karte(przegl):
    """Postój: karta ze stroną (także z pytaniem strony przed wyjściem) przechodzi na about:blank, a strona zostaje
    w historii karty; pusta karta nie jest ruszana drugi raz."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/sklep.html")
    js(st, nr, "window.onbeforeunload = (e) => { e.preventDefault(); e.returnValue = 'x'; return 'x'; }")
    assert st.zaparkuj() >= 1
    assert all(o.url == "about:blank" for o in st.okna()) and js(st, nr, "location.href") == "about:blank"
    historia = st.b.wyslij("Page.getNavigationHistory", {}, st.okno(nr).sesja)
    assert "sklep.html" in historia["entries"][historia["currentIndex"] - 1]["url"]
    assert st.zaparkuj() == 0 and st.wlasciciel_przy_oknie() is False


# ---------------------------------------------------------------------- jak telefon: paczka, czekanie, nawigacja

@pytest.fixture
def wejscie(przegl, tmp_path):
    """Wejście natywne z twardymi zasadami na prawdziwym sterowniku (jak w usłudze, bez kanałów)."""
    st, _, _ = przegl
    w = wejscie_natywne.WejscieNatywne(tmp_path / "komputer", "token-wlasciciela-testowy")
    w.sterownik = st
    yield w


class Mcp:
    """Agent na kanale `cua` (para gniazd): wiadomości MCP przez SesjaNatywna (zasady, dziennik) do sterownika."""

    def __init__(self, wej):
        self.a, b = socket.socketpair()
        self.a.settimeout(150)
        sesja = wejscie_natywne.SesjaNatywna(b, wej)
        wej.sesje.add(sesja)
        threading.Thread(target=sesja.obsluz, daemon=True).start()
        self.n, self.bufor = 0, b""

    def narzedzie(self, nazwa: str, args: dict) -> dict:
        self.n += 1
        self.a.sendall((json.dumps({"jsonrpc": "2.0", "id": self.n, "method": "tools/call",
                                    "params": {"name": nazwa, "arguments": args}}) + "\n").encode())
        while True:
            while b"\n" not in self.bufor:
                k = self.a.recv(1 << 16)
                assert k, "wejście zamknęło sesję"
                self.bufor += k
            linia, self.bufor = self.bufor.split(b"\n", 1)
            odp = json.loads(linia)
            if odp.get("id") == self.n:
                return odp["result"]

    def zamknij(self):
        self.a.close()


def test_paczka_staje_na_kroku_platnosci_a_dalszych_nie_wykonuje(przegl, wejscie):
    """run_steps przez wejście: zasady oceniają każdy krok na stronie po poprzednim. Okno zgody otwarte i zamknięte
    po napisie, a krok „Zapłać 129 zł” (poza ekranem) robi właściciel: paczka kończy się na nim z `czlowiek`,
    a następny krok nie idzie. W dzienniku sama paczka i każdy krok."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/dluga.html")
    k = Mcp(wejscie)
    try:
        w = k.narzedzie("run_steps", {"window_id": nr, "steps": [
            {"click": {"text": "Pokaż zgodę"}},
            {"click": {"text": "Odrzucam", "role": "button"}},
            {"tool": "click", "args": {"name": "Zapłać 129 zł"}},
            {"click": {"text": "Przycisk na górze"}}]})
    finally:
        k.zamknij()
    sc = w["structuredContent"]
    assert w["isError"] and (sc["total"], sc["executed"], sc["failed_step"]) == (4, 3, 2), sc
    assert (sc["decision"], sc["code"], sc["rule"], sc["next_step"]) == ("czlowiek", "wymaga_czlowieka",
                                                                         "przycisk_wrazliwy", "ask_owner")
    assert [r["ok"] for r in sc["steps"]] == [True, True, False]
    assert sc["steps"][1]["target"]["role"] == "push button"
    assert "zniknęło: dialog „Zgoda na ciasteczka”" in sc["steps"][1]["message"], sc["steps"][1]
    assert "niewykonane: 1" in w["content"][0]["text"]
    assert js(st, nr, "getComputedStyle(document.getElementById('zgoda')).display") == "none"
    assert js(st, nr, "document.getElementById('wynik').textContent") == "Nic nie kliknięto"    # krok 4 nie poszedł
    wpisy = list(wejscie.dziennik.ostatnie)
    assert any(x["narzedzie"] == "run_steps" and x["decyzja"] == "tak" for x in wpisy)
    assert [x["decyzja"] for x in wpisy if x["narzedzie"] == "click"] == ["tak", "tak", "czlowiek"]


def test_cel_napisem_niejednoznaczny_albo_bez_dopasowania_to_odmowa_bez_dzialania(przegl, wejscie):
    """Napis pasujący do kilku elementów (dwa przyciski z „Zapłać”) albo do żadnego: odmowa kroku z kandydatami
    i numerami z migawki, nic nie kliknięte, kolejne kroki nie idą; numer z odmowy działa w następnej paczce."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/sklep.html")
    przyciski = js(st, nr, "document.querySelectorAll('button').length")
    k = Mcp(wejscie)
    try:
        w = k.narzedzie("run_steps", {"window_id": nr, "steps": [{"click": {"text": "zapłać"}},
                                                                 {"click": {"text": "Pokaż baner"}}]})
        sc = w["structuredContent"]
        assert w["isError"] and (sc["executed"], sc["failed_step"]) == (1, 0) and "decision" not in sc, sc
        krok = sc["steps"][0]
        assert (krok["code"], krok["phase"]) == ("cel_niejednoznaczny", "find")
        assert sorted(e["label"][:12] for e in krok["kandydaci"]) == ["Zapłać 129 z", "Zapłać klucz"]
        assert "[ukryte przez Komputer Jarva]" in json.dumps(krok, ensure_ascii=False)    # klucz z napisu ukryty
        w = k.narzedzie("run_steps", {"window_id": nr, "steps": [
            {"click": {"text": "Nie ma takiego przycisku"}, "timeout_ms": 300}]})
        assert w["structuredContent"]["steps"][0]["code"] == "brak_celu"
        assert js(st, nr, "document.querySelectorAll('button').length") == przyciski       # „Pokaż baner” nie poszedł
        # dokładny napis wygrywa z fragmentem: „Szukaj” to przycisk, nie pole „Szukaj w sklepie”
        w = k.narzedzie("run_steps", {"window_id": nr, "steps": [{"click": {"text": "Szukaj"}}]})
        assert not w["isError"] and w["structuredContent"]["steps"][0]["target"]["role"] == "push button", w
        # klucz z numerem kandydata: przycisk z kluczem nie jest wrażliwy, ale „Zapłać 129 zł” jest
        zaplac = next(e for e in krok["kandydaci"] if e["label"].startswith("Zapłać 129"))
        w = k.narzedzie("run_steps", {"window_id": nr, "snapshot_id": krok["snapshot_id"],
                                      "steps": [{"click": {"element_index": zaplac["element_index"]}}]})
        assert w["structuredContent"]["decision"] == "czlowiek", w
    finally:
        k.zamknij()


def test_wait_for_tekst_po_chwili_zniknienie_adres_i_czysty_limit(przegl, wejscie):
    """wait_for liczy w sterowniku: tekst, który strona dopisze po 1,5 s, jest; tekstu, którego nie będzie, nie ma
    po limicie (błąd `czas_minal`, bez wyjątku); zniknięcie i adres. W paczce wait_for przed klikiem czeka na
    przycisk, który pojawi się później."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/dluga.html")
    js(st, nr, "setTimeout(() => document.body.insertAdjacentHTML('afterbegin', '<p>Gotowe po chwili</p>'), 1500); 1")
    k = Mcp(wejscie)
    try:
        w = k.narzedzie("wait_for", {"window_id": nr, "text": "gotowe  PO chwili", "timeout_ms": 8000})
        sc = w["structuredContent"]
        assert not w["isError"] and sc["met"] is True and 1000 <= sc["waited_ms"] < 8000, sc
        start = time.monotonic()
        w = k.narzedzie("wait_for", {"window_id": nr, "text": "Tego tekstu nie będzie", "timeout_ms": 700})
        sc = w["structuredContent"]
        assert w["isError"] and sc["code"] == "czas_minal" and sc["met"] is False and sc["waited_ms"] >= 700, sc
        assert time.monotonic() - start < 5
        w = k.narzedzie("wait_for", {"window_id": nr, "text": "Gotowe po chwili", "gone": True, "timeout_ms": 300})
        assert w["structuredContent"]["code"] == "czas_minal" and "nadal jest" in w["structuredContent"]["message"]
        w = k.narzedzie("wait_for", {"window_id": nr, "url": "https://sklep.jarvo.test/*.html"})
        assert not w["isError"], w
        assert k.narzedzie("wait_for", {"window_id": nr})["structuredContent"]["code"] == "warunek"
        js(st, nr, "setTimeout(() => { const b = document.createElement('button'); b.textContent = 'Późny przycisk';"
                   " b.onclick = () => wynik('Kliknięto późny'); document.body.prepend(b); }, 1000); 1")
        w = k.narzedzie("run_steps", {"window_id": nr, "steps": [
            {"click": {"text": "Późny przycisk"}, "wait_for": {"text": "Późny przycisk", "timeout_ms": 8000}}]})
        assert not w["isError"] and w["structuredContent"]["steps"][0]["wait_for"]["met"], w
        assert js(st, nr, "document.getElementById('wynik').textContent") == "Kliknięto późny"
    finally:
        k.zamknij()


def test_navigate_adres_zablokowany_przez_zasady_a_dozwolony_z_paragonem(przegl, wejscie):
    """navigate oceniają te same zasady co adres wpisany w pasek: file:, javascript:, chrome: i klucz w adresie
    nie przechodzą (sterownik ich nie dostaje), także jako krok paczki, która wtedy staje. Adres http(s): przejście
    z paragonem `adres: …` i wpisem w dzienniku z samą nazwą serwera."""
    st, _, _ = przegl
    nr = otworz(st, "https://sklep.jarvo.test/sklep.html")
    przyciski = js(st, nr, "document.querySelectorAll('button').length")
    k = Mcp(wejscie)
    try:
        for url, zasada in (("file:///etc/passwd", "adres"), ("javascript:alert(1)", "adres"),
                            ("chrome://settings", "adres"),
                            ("https://sklep.jarvo.test/?k=sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890", "sekret")):
            w = k.narzedzie("navigate", {"window_id": nr, "url": url})
            sc = w["structuredContent"]
            assert w["isError"] and (sc["decision"], sc["rule"]) == ("odmowa", zasada), (url, sc)
        assert st.okno(nr).url == "https://sklep.jarvo.test/sklep.html"
        w = k.narzedzie("run_steps", {"window_id": nr, "steps": [{"navigate": {"url": "file:///etc/passwd"}},
                                                                 {"click": {"text": "Pokaż baner"}}]})
        sc = w["structuredContent"]
        assert (sc["failed_step"], sc["executed"], sc["rule"]) == (0, 1, "adres"), sc
        assert js(st, nr, "document.querySelectorAll('button').length") == przyciski
        w = k.narzedzie("navigate", {"window_id": nr, "url": "https://sklep.jarvo.test/formularz.html"})
        sc = w["structuredContent"]
        assert not w["isError"] and sc["effect"] == "confirmed" and "adres: sklep.jarvo.test/formularz.html" in sc[
            "message"] and sc["title"] == "Zamówienie testowe Jarvo", sc
        w = k.narzedzie("navigate", {"window_id": nr, "url": "https://sklep.jarvo.test/formularz.html"})
        assert w["structuredContent"]["effect"] == "confirmed" and "wczytana od nowa" in w["structuredContent"][
            "message"], w                                  # ten sam adres jeszcze raz: przejście, nie `suspected_noop`
    finally:
        k.zamknij()
    wpisy = [x for x in wejscie.dziennik.ostatnie if x["narzedzie"] == "navigate"]
    assert [x["decyzja"] for x in wpisy] == ["odmowa"] * 5 + ["tak"] * 2 and wpisy[-1]["cel"] == "sklep.jarvo.test"
    assert "sk-proj" not in json.dumps(wpisy)


def _wtyczka():
    import importlib.util
    spec = importlib.util.spec_from_file_location("jarvo_test_wtyczka_cdp", REPO / "komputer" / "plugin" /
                                                  "__init__.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_wtyczka_operatora_idz_patrz_kroki_przez_bramke(przegl, monkeypatch):
    """Droga Operatora do stron: narzędzie `komputer` (wtyczka) przez bramkę floty i kanał `cua` do wejścia
    z zasadami: idz, patrz (okno zgody na górze), kroki z celem napisem i obserwacją (nowy tekst z `*`), czekaj;
    krok płatności kończy paczkę z radą `oddaj`. Cztery wywołania od adresu do odczytu."""
    from jarvo import komputer as jk
    from jarvo import sciezki
    st, _, _ = przegl
    root = Path(tempfile.mkdtemp(prefix="jkw"))          # krótka ścieżka: gniazdo unix ma limit ok. 100 bajtów
    kanal.katalog_stanu(root).mkdir(parents=True)
    (kanal.katalog_stanu(root) / "usluga.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    wej = wejscie_natywne.WejscieNatywne(root / "dane", "token-wlasciciela-testowy")
    wej.sterownik = st
    serwer = kanal.Serwer(kanal.adres(root, "cua"), wej.obsluz_cua, "cua").start()
    u = sciezki.Uklad(root=root, program=root / "program", dane=root / "dane", stan=root / "stan",
                      logi=root / "logi", cache=root / "cache", build=root / "build")
    u.bin_floty.mkdir(parents=True)
    monkeypatch.setenv("HERMES_CUA_DRIVER_CMD", str(jk.nakladka_bramki(u, REPO, Path(sys.executable))))
    monkeypatch.setenv("JARVO_ROOT", str(root))
    monkeypatch.delenv("JARVO_KOMPUTER_GNIAZDO", raising=False)
    monkeypatch.setenv("JARVO_KOMPUTER_GRUPA", "grupa-testowa-wtyczki-0123456789")
    wt = _wtyczka()
    try:
        odp = wt.obsluz({"akcja": "idz", "adres": "https://sklep.jarvo.test/dluga.html?z=wtyczka"}, session_id="s1")
        assert odp.startswith("ok: okno") and "Długa strona Jarvo" in odp and \
            "adres: sklep.jarvo.test/dluga.html?z=wtyczka" in odp, odp
        js(st, st.aktywne_okno(), "document.getElementById('zgoda').style.display = 'block'")
        odp = wt.obsluz({"akcja": "patrz"}, session_id="s1")
        assert "[1] dialog „Zgoda na ciasteczka”" in odp and "„Przycisk na górze”" not in odp, odp
        odp = wt.obsluz({"akcja": "kroki", "obserwuj": True, "kroki": [
            {"click": {"text": "Odrzucam"}}, {"click": {"text": "Przycisk na górze"}},
            {"wait_for": {"text": "Kliknięto górę"}}]}, session_id="s1")
        assert "run_steps: 3/3 kroków ok" in odp and "obserwacja po krokach:" in odp, odp
        nowe = [linia for linia in odp.splitlines() if linia.lstrip().startswith("*[")]
        assert len(nowe) == 1 and "paragraph „Kliknięto górę”" in nowe[0], odp      # tylko to, czego nie było
        assert "dialog „Zgoda na ciasteczka”" not in odp.split("obserwacja po krokach:")[1]
        odp = wt.obsluz({"akcja": "czekaj", "tekst": "Kliknięto górę", "sekundy": 2}, session_id="s1")
        assert odp.startswith("ok: wait_for"), odp
        odp = wt.obsluz({"akcja": "kroki", "kroki": [{"click": {"text": "Zapłać 129 zł"}},
                                                     {"click": {"text": "Nic nie robi"}}]}, session_id="s1")
        assert "BŁĄD wymaga_czlowieka" in odp and "akcja=oddaj" in odp and "niewykonane: 1" in odp, odp
        odp = wt.obsluz({"akcja": "idz", "adres": "file:///etc/passwd"}, session_id="s1")
        assert odp.startswith("BŁĄD zablokowane") and "Dalej:" in odp, odp
    finally:
        wt._zamknij_wszystkie()
        serwer.zamknij()
        shutil.rmtree(root, ignore_errors=True)
