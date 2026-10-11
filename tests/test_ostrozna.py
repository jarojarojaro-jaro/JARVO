"""Wspólny skill ostrozna-przegladarka: jedna próba Camoufoxem po odmowie strony (przeglądarka podmieniona atrapą)."""

from __future__ import annotations

import contextlib
import fcntl
import json
import socket
import sys
import types

import pytest

from conftest import load_script

O = load_script("shared/skills/ostrozna-przegladarka/scripts/ostrozna.py")
S = load_script("profiles/jarvo-lowca/scripts/strona.py")


# ------------------------------------------------------------------ adres i robots.txt

def test_adres_tylko_publiczny_http(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, p: [(2, 1, 6, "", ("93.184.215.14", 0))])
    assert O.sprawdz_adres("firma.pl/kontakt") == "https://firma.pl/kontakt"
    for zly in ("ftp://firma.pl", "file:///etc/passwd", "http://localhost:9119/", "http://jarvo-hermes.local/",
                "https://user:haslo@firma.pl/", "http://127.0.0.1/", "http://[::1]/", "http://169.254.169.254/"):
        with pytest.raises(O.ZlyAdres):
            O.sprawdz_adres(zly)
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, p: [(2, 1, 6, "", ("10.0.0.5", 0))])
    with pytest.raises(O.ZlyAdres, match="nie jest publiczny"):
        O.sprawdz_adres("https://intranet.firma.pl/")


def test_adres_nieznany_przechodzi_do_przegladarki(monkeypatch):
    def brak(h, p):
        raise socket.gaierror("brak")
    monkeypatch.setattr(socket, "getaddrinfo", brak)
    assert O.sprawdz_adres("https://nie-ma-takiej.pl") == "https://nie-ma-takiej.pl"


def test_robots():
    u = "https://firma.pl/oferta"
    O.ocen_robots(404, "", u)                                            # brak robots.txt = wolno
    O.ocen_robots(200, "User-agent: *\nDisallow: /panel\n", u)
    with pytest.raises(O.Blokada, match="zabrania"):
        O.ocen_robots(200, "User-agent: *\nDisallow: /\n", u)
    with pytest.raises(O.Blokada, match="zabrania"):
        O.ocen_robots(200, "User-agent: jarvo\nDisallow: /oferta\n", u)
    for kod, tresc in ((403, ""), (429, ""), (503, ""), (None, ""), (200, "<!DOCTYPE html><title>Just a moment...</title>")):
        with pytest.raises(O.Blokada, match="niedostępny"):
            O.ocen_robots(kod, tresc, u)


# ------------------------------------------------------------------ rozpoznanie blokady

DLUGI = "Oferta firmy. " * 200


def test_oznaki_blokady():
    assert "logowania" in O.oznaka_blokady(401, "Firma", DLUGI, "<html>")
    assert "403" in O.oznaka_blokady(403, "Firma", DLUGI, "<html>")
    assert O.oznaka_blokady(200, "Just a moment...", "", "<html>")
    assert O.oznaka_blokady(200, "Human Verification", "", "<html>")
    assert O.oznaka_blokady(200, "Firma", "Verify", '<div class="cf-turnstile"></div>')
    # formularz kontaktowy z reCAPTCHA na zwykłej stronie to nie blokada
    assert O.oznaka_blokady(200, "Kontakt | Firma", DLUGI, '<div class="g-recaptcha"></div>') is None
    assert O.oznaka_blokady(200, "Firma", DLUGI, "<html><body>ok</body></html>") is None
    assert O.oznaka_blokady(404, "Nie znaleziono", "Brak strony", "<html>") is None   # błąd, nie blokada


# ------------------------------------------------------------------ limity

def test_odstep_i_limit_dzienny(tmp_path, monkeypatch):
    assert O.rezerwuj("firma.pl", teraz=1000.0, katalog=tmp_path) == 0
    assert O.rezerwuj("firma.pl", teraz=1005.0, katalog=tmp_path) == pytest.approx(O.ODSTEP_S - 5)
    assert O.rezerwuj("inna.pl", teraz=1005.0, katalog=tmp_path) == 0          # odstęp liczy się per domena
    monkeypatch.setattr(O, "DZIENNIE", 3)
    O.rezerwuj("firma.pl", teraz=2000.0, katalog=tmp_path)
    with pytest.raises(O.Limit, match="na dobę"):
        O.rezerwuj("firma.pl", teraz=3000.0, katalog=tmp_path)
    assert O.rezerwuj("firma.pl", teraz=1000.0 + 90000, katalog=tmp_path) == 0  # po dobie stare wizyty wypadają


def test_jedna_przegladarka_naraz(tmp_path):
    with open(tmp_path / "przegladarka.lock", "w", encoding="utf-8") as inny:
        fcntl.flock(inny, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(O.Limit, match="zajęta"), O.jedna_naraz(tmp_path, czekaj_s=0):
            pass
    with O.jedna_naraz(tmp_path, czekaj_s=0):
        pass


# ------------------------------------------------------------------ atrapa przeglądarki

class Resp:
    def __init__(self, status, text="", nawigacja=True, frame="main"):
        self.status, self._text, self.frame = status, text, frame
        self.request = types.SimpleNamespace(is_navigation_request=lambda: nawigacja)

    def text(self):
        return self._text


class Strona:
    """Atrapa strony Playwrighta: `strony` = adres → (kod, tytuł, html); `po_czekaniu` zmienia stan jak strażnik JS."""

    def __init__(self, strony, robots=(200, "User-agent: *\nAllow: /\n"), haslo=False, po_czekaniu=None):
        self.strony, self.robots, self.haslo, self.po_czekaniu = strony, robots, haslo, po_czekaniu
        self.main_frame, self.url, self._stan, self._sluchacze = "main", "", ("", ""), []
        self.odwiedzone, self.zrzut = [], None

    def on(self, zdarzenie, cb):
        self._sluchacze.append(cb)

    def goto(self, url, **kw):
        self.odwiedzone.append(url)
        self.url = url
        if url.endswith("/robots.txt"):
            return Resp(*self.robots)
        kod, tytul, html = self.strony[url]
        self._stan = (tytul, html)
        return Resp(kod)

    def wait_for_load_state(self, *a, **kw):
        pass

    def wait_for_timeout(self, ms):
        if self.po_czekaniu:
            kod, tytul, html = self.po_czekaniu
            self._stan = (tytul, html)
            for cb in self._sluchacze:
                cb(Resp(kod))
            self.po_czekaniu = None

    def title(self):
        return self._stan[0]

    def content(self):
        return self._stan[1]

    def inner_text(self, sel, timeout=0):
        import re
        return re.sub(r"<[^>]+>", " ", self._stan[1])

    def locator(self, sel):
        return types.SimpleNamespace(count=lambda: 1 if self.haslo else 0)

    def screenshot(self, path, full_page):
        self.zrzut = (path, full_page)
        with open(path, "wb") as f:
            f.write(b"\x89PNG")


def podmien(monkeypatch, strona):
    @contextlib.contextmanager
    def otworz(zrzut=False):
        yield types.SimpleNamespace(new_page=lambda: strona)
    monkeypatch.setattr(O, "otworz", otworz)


TRESC = "<html><head><title>Kontakt | Firma</title></head><body><h1>Kontakt</h1><p>" + DLUGI + \
        "Napisz: <a href='mailto:biuro@firma.pl'>biuro@firma.pl</a></p></body></html>"


def test_czytaj_robots_przed_strona(monkeypatch):
    s = Strona({"https://firma.pl/kontakt": (200, "Kontakt | Firma", TRESC)})
    podmien(monkeypatch, s)
    w = O.czytaj("https://firma.pl/kontakt", "html")
    assert s.odwiedzone == ["https://firma.pl/robots.txt", "https://firma.pl/kontakt"]
    assert w["kod"] == 200 and w["tytul"] == "Kontakt | Firma" and "biuro@firma.pl" in w["tresc"]
    md = O.czytaj("https://firma.pl/kontakt", "markdown")["tresc"]
    assert "Oferta firmy" in md and "<p>" not in md


def test_robots_zabrania_strona_nieczytana(monkeypatch):
    s = Strona({"https://firma.pl/kontakt": (200, "x", TRESC)}, robots=(200, "User-agent: *\nDisallow: /kontakt\n"))
    podmien(monkeypatch, s)
    with pytest.raises(O.Blokada, match="robots"):
        O.czytaj("https://firma.pl/kontakt")
    assert s.odwiedzone == ["https://firma.pl/robots.txt"]


def test_straznik_przepuszcza_sam(monkeypatch):
    """„Just a moment…” z kodem 403, po kilku sekundach strona przeładowuje się z 200: czytamy bez klikania."""
    s = Strona({"https://firma.pl/": (403, "Just a moment...", "<div id='cf-chl'></div>")},
               po_czekaniu=(200, "Firma", TRESC))
    podmien(monkeypatch, s)
    w = O.czytaj("https://firma.pl/", "html", czekaj_s=5)
    assert w["kod"] == 200 and "biuro@firma.pl" in w["tresc"]


def test_captcha_zostaje_blokada(monkeypatch):
    s = Strona({"https://firma.pl/": (200, "Human Verification", "<iframe src='https://geo.captcha-delivery.com'>")})
    podmien(monkeypatch, s)
    with pytest.raises(O.Blokada, match="automatów"):
        O.czytaj("https://firma.pl/", czekaj_s=0)
    s2 = Strona({"https://firma.pl/": (429, "Too Many Requests", "")})
    podmien(monkeypatch, s2)
    with pytest.raises(O.Blokada, match="429"):
        O.czytaj("https://firma.pl/", czekaj_s=5)


def test_logowanie_i_404(monkeypatch):
    podmien(monkeypatch, Strona({"https://firma.pl/panel": (200, "Zaloguj się", "<form><input type=password></form>")},
                                haslo=True))
    with pytest.raises(O.Blokada, match="logowania"):
        O.czytaj("https://firma.pl/panel")
    podmien(monkeypatch, Strona({"https://firma.pl/x": (404, "Nie znaleziono", "<p>404</p>")}))
    with pytest.raises(ConnectionError, match="404"):
        O.czytaj("https://firma.pl/x")


# ------------------------------------------------------------------ CLI

@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "STAN", tmp_path / "stan")
    monkeypatch.setattr(O, "ma_camoufox", lambda: True)
    monkeypatch.setattr(O, "sprawdz_adres", lambda u: u)
    monkeypatch.setattr(O.time, "sleep", lambda s: None)
    return tmp_path


def test_cli_kody_i_plik(cli, monkeypatch, capsys):
    podmien(monkeypatch, Strona({"https://firma.pl/": (200, "Firma", TRESC)}))
    out = cli / "strony" / "firma.html"
    assert O.main(["https://firma.pl/", "--html", "-o", str(out), "--json"]) == 0
    w = json.loads(capsys.readouterr().out)
    assert w["plik"] == str(out) and w["tresc"] == "" and "biuro@firma.pl" in out.read_text(encoding="utf-8")
    assert json.loads((cli / "stan" / "domeny.json").read_text(encoding="utf-8"))["firma.pl"]

    podmien(monkeypatch, Strona({"https://firma.pl/": (403, "Attention Required! | Cloudflare", "")}))
    monkeypatch.setattr(O, "CZEKAJ_NA_STRAZNIKA_S", 0)
    assert O.main(["https://firma.pl/"]) == 3
    assert "blokada" in capsys.readouterr().err

    monkeypatch.setattr(O, "sprawdz_adres", lambda u: (_ for _ in ()).throw(O.ZlyAdres("adres wewnętrzny")))
    assert O.main(["http://localhost/"]) == 2


def test_cli_zrzut_i_limit(cli, monkeypatch, capsys):
    s = Strona({"https://firma.pl/": (200, "Firma", TRESC)})
    podmien(monkeypatch, s)
    png = cli / "a.png"
    assert O.main(["https://firma.pl/", "--zrzut", str(png)]) == 0
    assert s.zrzut == (str(png), True) and png.exists()
    monkeypatch.setattr(O, "DZIENNIE", 1)
    assert O.main(["https://firma.pl/"]) == 4
    assert "limit" in capsys.readouterr().err


def test_opcje_bez_proxy_i_dodatkow(tmp_path, monkeypatch):
    (tmp_path / "application.ini").write_text("[App]\nVendor=Camoufox\nVersion=152.0.4-beta.30\n", encoding="utf-8")
    monkeypatch.setattr(O, "EXE", str(tmp_path / "camoufox-bin"))
    fake = types.ModuleType("camoufox")
    fake.DefaultAddons = types.SimpleNamespace(UBO="ubo")
    monkeypatch.setitem(sys.modules, "camoufox", fake)
    o = O.opcje_camoufox(zrzut=False)
    assert o["headless"] is True and o["os"] == "linux" and o["ff_version"] == 152
    assert o["exclude_addons"] == ["ubo"] and o["block_images"] is True and o["humanize"] is False
    assert not {"proxy", "user_data_dir", "persistent_context", "addons", "geoip_db"} & set(o) and o["geoip"] is False
    assert O.opcje_camoufox(zrzut=True)["block_images"] is False


def test_sprawdz(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(O, "ma_camoufox", lambda: True)
    monkeypatch.setattr(O, "EXE", str(tmp_path / "camoufox-bin"))
    assert O.sprawdz() == 1 and "brak" in capsys.readouterr().err
    (tmp_path / "camoufox-bin").write_text("#!/bin/sh\n")
    (tmp_path / "camoufox-bin").chmod(0o755)
    (tmp_path / "fontconfig" / "linux").mkdir(parents=True)
    (tmp_path / "fontconfig" / "linux" / "fonts.conf").write_text("<fontconfig/>")
    (tmp_path / "fonts" / "linux").mkdir(parents=True)
    (tmp_path / "properties.json").write_text("[]")
    assert O.sprawdz() == 0


# ------------------------------------------------------------------ Łowca: strona.py --z-html

def test_strona_z_html_bez_sieci(monkeypatch):
    def siec(*a, **kw):
        raise AssertionError("bez sieci: strona przyszła z ostrozna.py")
    monkeypatch.setattr(S.ll, "http", siec)
    html = ("<html><head><title>Firma Kowalski</title></head><body><a href='/kariera'>Kariera</a>"
            "<p>Biuro: <a href='mailto:biuro@kowalski.pl'>biuro@kowalski.pl</a>, tel. 22 123 45 67, NIP 525-000-00-00</p>"
            "</body></html>")
    w = S.kontakt("https://kowalski.pl/kontakt", z_html=html)
    assert w["odczyt"] == "camoufox" and w["strony"] == ["https://kowalski.pl/kontakt"]
    assert [e["email"] for e in w["emaile"]] == ["biuro@kowalski.pl"]
    assert w["emaile"][0]["zrodlo"] == "https://kowalski.pl/kontakt" and w["telefony"]
    assert w["kariera"] == "https://kowalski.pl/kariera"
