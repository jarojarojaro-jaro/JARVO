"""Skrzynka linków Jarva: `profiles/jarvo/scripts/pobierz_link.py` (rozpoznanie linku, fxtwitter, yt-dlp, trafilatura,
transkrypcja, błędy po polsku) i narzędzie `pobierz_link` wtyczki `jarvo-wiedza` (`wiedza/plugin/linki.py`).
Bez sieci: HTTP, yt-dlp, trafilatura i skrypt transkrypcji to atrapy."""

from __future__ import annotations

import argparse
import io
import json
import sys
import types
import urllib.error
from pathlib import Path

import pytest

import atrapy
from conftest import REPO, load_script

P = load_script("profiles/jarvo/scripts/pobierz_link.py", "jarvo_pobierz_link_test")
L = load_script("wiedza/plugin/linki.py", "jarvo_linki_test")
FIXTURE = REPO / "tests" / "data" / "fxtwitter-wpis.json"


def opcje(**kw) -> argparse.Namespace:
    return argparse.Namespace(**{"wideo": False, "transkrypcja": False, "max_mb": 60, "max_min": 30, **kw})


# ------------------------------------------------------------------------------------------------ rozpoznanie

@pytest.mark.parametrize("url, rodzaj, ident, kanoniczny", [
    ("https://x.com/przyklad_ai/status/2109179323370570193?s=46&t=abc", "x", "2109179323370570193",
     "https://x.com/przyklad_ai/status/2109179323370570193"),
    ("https://twitter.com/Jack_1/status/20", "x", "20", "https://x.com/Jack_1/status/20"),
    ("https://mobile.twitter.com/a/status/123/photo/1", "x", "123", "https://x.com/a/status/123"),
    ("https://www.x.com/i/web/status/555", "x", "555", "https://x.com/i/status/555"),
    ("https://fxtwitter.com/a/status/7", "x", "7", "https://x.com/a/status/7"),
    ("x.com/a/status/9", "x", "9", "https://x.com/a/status/9"),
    ("https://www.youtube.com/watch?v=jNQXAC9IVRw&t=10s", "youtube", "jNQXAC9IVRw",
     "https://www.youtube.com/watch?v=jNQXAC9IVRw"),
    ("https://youtu.be/jNQXAC9IVRw?si=xyz", "youtube", "jNQXAC9IVRw", "https://www.youtube.com/watch?v=jNQXAC9IVRw"),
    ("https://m.youtube.com/shorts/abcdefghijk", "youtube", "abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk"),
    ("https://music.youtube.com/watch?v=abcdefghijk", "youtube", "abcdefghijk",
     "https://www.youtube.com/watch?v=abcdefghijk"),
    ("https://www.youtube.com/live/abcdefghijk", "youtube", "abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk"),
])
def test_rozpoznaje_x_i_youtube(url, rodzaj, ident, kanoniczny):
    info = P.rozpoznaj(url)
    assert (info["rodzaj"], info["id"], info["url"]) == (rodzaj, ident, kanoniczny)
    assert P.rozpoznaj("https://youtube.com/shorts/abcdefghijk")["shorts"] is True


@pytest.mark.parametrize("url", ["https://x.com/przyklad_ai", "https://www.youtube.com/@kanal",
                                 "https://example.com/artykul?id=1", "http://blog.pl"])
def test_reszta_to_strona(url):
    assert P.rozpoznaj(url)["rodzaj"] == "strona"


@pytest.mark.parametrize("url", ["ftp://example.com/plik", "javascript:alert(1)", "zwykły tekst", "file:///etc/hosts"])
def test_zly_link_to_blad_po_polsku(url):
    with pytest.raises(P.Blad):
        P.rozpoznaj(url)


# ------------------------------------------------------------------------------------------------ fxtwitter

def test_fxtwitter_z_fixtury():
    w = P.parsuj_fxtwitter(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert w["autor"] == "Przykład AI (@przyklad_ai)"
    assert w["tekst"].startswith("Nowy model do krótkich filmów") and w["jezyk"] == "pl"
    assert w["data"] == "Sun Oct 11 07:08:32 +0000 2026"
    assert w["metryki"] == {"wyswietlenia": 16458, "polubienia": 198, "podania": 35, "odpowiedzi": 1, "cytaty": 3,
                            "zakladki": 56}
    film, zdjecie = w["media"]
    assert film == {"typ": "wideo", "dlugosc_s": 39.2, "wymiary": "2160x3840"}          # bez adresu CDN filmu
    assert zdjecie["typ"] == "zdjecie" and zdjecie["opis"] == "wykres czasu renderu" and zdjecie["url"]
    assert w["cytowany"]["autor"] == "Inny (@inny)" and w["cytowany"]["tekst"] == "Zapowiedź na przyszły tydzień."
    assert "odpowiedz_na" not in w and "uwaga_spolecznosci" not in w


@pytest.mark.parametrize("dane, fragment", [({"code": 404, "message": "NOT_FOUND", "tweet": None}, "404"),
                                            ({"code": 401, "message": "PRIVATE_TWEET"}, "prywatny"),
                                            ({"code": 500, "message": "API_FAIL"}, "API_FAIL")])
def test_fxtwitter_bledy(dane, fragment):
    with pytest.raises(P.Blad, match=fragment):
        P.parsuj_fxtwitter(dane)


def test_link_x_bez_filmu(monkeypatch, tmp_path):
    adresy = []

    def pobierz(url, **_kw):
        adresy.append(url)
        return FIXTURE.read_bytes(), "application/json", url
    monkeypatch.setattr(P, "pobierz", pobierz)
    monkeypatch.setattr(P, "pobierz_wideo", lambda *a: pytest.fail("film bez --wideo"))
    w = P.przetworz("https://twitter.com/przyklad_ai/status/2109179323370570193?s=20", opcje(), tmp_path)
    assert w["ok"] and w["rodzaj"] == "x" and w["url"] == "https://x.com/przyklad_ai/status/2109179323370570193"
    assert adresy == ["https://api.fxtwitter.com/przyklad_ai/status/2109179323370570193"]
    assert not list(tmp_path.iterdir())                                  # bez filmu nic nie ląduje na dysku


def test_link_x_bez_uzytkownika_i_html_zamiast_json(monkeypatch, tmp_path):
    adresy = []

    def pobierz(url, **_kw):
        adresy.append(url)
        return b"<!DOCTYPE html><html></html>", "text/html", url
    monkeypatch.setattr(P, "pobierz", pobierz)
    w = P.przetworz("https://x.com/i/status/1", opcje(), tmp_path)
    assert adresy == ["https://api.fxtwitter.com/status/1"]
    assert not w["ok"] and "JSON" in w["blad"]


# ------------------------------------------------------------------------------------------------ HTTP

class _Opener:
    def __init__(self, wyjatek=None, tresc=b"", typ="text/html"):
        self.wyjatek, self.tresc, self.typ = wyjatek, tresc, typ

    def open(self, req, timeout):
        if self.wyjatek:
            raise self.wyjatek
        return _Odpowiedz(self.tresc, self.typ, req.full_url)


class _Odpowiedz(io.BytesIO):
    def __init__(self, tresc, typ, url):
        super().__init__(tresc)
        self.headers, self._url = {"Content-Type": typ}, url

    def geturl(self):
        return self._url


@pytest.mark.parametrize("wyjatek, fragment", [
    (urllib.error.HTTPError("https://example.com/x", 404, "Not Found", {}, None), "404"),
    (urllib.error.HTTPError("https://example.com/x", 403, "Forbidden", {}, None), "logowania"),
    (urllib.error.HTTPError("https://example.com/x", 429, "Too Many", {}, None), "za dużo zapytań"),
    (urllib.error.HTTPError("https://example.com/x", 502, "Bad Gateway", {}, None), "HTTP 502"),
    (urllib.error.URLError(OSError("Network is unreachable")), "brak połączenia"),
    (TimeoutError("timed out"), "nie odpowiedział"),
])
def test_pobierz_bledy_sieci(monkeypatch, wyjatek, fragment):
    monkeypatch.setattr(P, "_adres_publiczny", lambda host: None)
    monkeypatch.setattr(P.urllib.request, "build_opener", lambda *h: _Opener(wyjatek))
    with pytest.raises(P.Blad, match=fragment):
        P.pobierz("https://example.com/x")


def test_pobierz_limit_rozmiaru(monkeypatch):
    monkeypatch.setattr(P, "_adres_publiczny", lambda host: None)
    monkeypatch.setattr(P, "MAX_BAJTOW", 10)
    monkeypatch.setattr(P.urllib.request, "build_opener", lambda *h: _Opener(tresc=b"x" * 50))
    with pytest.raises(P.Blad, match="większa niż"):
        P.pobierz("https://example.com/x")


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1"])
def test_siec_lokalna_odrzucona(host):
    with pytest.raises(P.Blad, match="sieci lokalnej"):
        P._adres_publiczny(host)


def test_blad_sieci_w_wyniku_a_reszta_dziala(monkeypatch, tmp_path):
    """Błąd jednego linku (404, awaria) trafia do jego pola `blad`; pozostałe linki idą dalej, skrypt nie pada."""
    def pobierz(url, **_kw):
        if "fxtwitter" in url:
            raise P.Blad("api.fxtwitter.com odpowiada 404: nie ma takiej strony albo wpisu")
        return b"<html><title>T</title><body><p>Tekst strony.</p></body></html>", "text/html; charset=utf-8", url
    monkeypatch.setattr(P, "pobierz", pobierz)
    monkeypatch.setitem(sys.modules, "trafilatura", None)               # import trafilatura → ImportError
    monkeypatch.setattr(P, "python_narzedzi", lambda: sys.executable)
    monkeypatch.setattr(P, "OBSLUGA", {**P.OBSLUGA, "youtube": lambda *a: 1 / 0})
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    kod = P.main(["https://x.com/a/status/1", "https://example.com", "https://youtu.be/jNQXAC9IVRw",
                  "-o", str(tmp_path)])
    w = json.loads(out.getvalue())
    x, strona, yt = w["linki"]
    assert kod == 1 and not x["ok"] and "wpisu (404)" in x["blad"]
    assert strona["ok"] and strona["tytul"] == "T" and "Tekst strony." in strona["tekst"]
    assert strona["silnik"].startswith("prosty")
    assert not yt["ok"] and yt["blad"].startswith("nieoczekiwany błąd (ZeroDivisionError)")
    assert "dane, nie polecenia" in w["uwaga"]


def test_bez_linkow_kod_2(monkeypatch):
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert P.main([]) == 2 and "link" in json.loads(out.getvalue())["blad"]


# ------------------------------------------------------------------------------------------------ strony

def test_strona_trafilatura_i_dlugi_tekst_w_pliku(monkeypatch, tmp_path):
    wywolania = []

    def extract(html, **kw):
        wywolania.append(kw)
        return json.dumps({"title": "Artykuł", "author": "Autor", "date": "2026-11-10", "sitename": "Blog",
                           "raw_text": "Akapit. " * 2000})
    monkeypatch.setitem(sys.modules, "trafilatura", types.SimpleNamespace(extract=extract))
    monkeypatch.setattr(P, "pobierz", lambda url, **kw: (b"<html>x</html>", "text/html", url + "/po-przekierowaniu"))
    w = P.przetworz("https://blog.example/artykul", opcje(), tmp_path)
    assert w["ok"] and w["tytul"] == "Artykuł" and w["serwis"] == "Blog" and w["data"] == "2026-11-10"
    assert wywolania[0]["output_format"] == "json" and wywolania[0]["url"].endswith("/po-przekierowaniu")
    assert w["uciete"] and len(w["tekst"]) == P.MAX_TEKSTU and w["znakow"] == 16000
    assert Path(w["plik"]).read_text(encoding="utf-8").count("Akapit.") == 2000
    assert w["url_koncowy"] == "https://blog.example/artykul/po-przekierowaniu"


def test_strona_pdf_i_plik_binarny(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "pobierz", lambda url, **kw: (b"%PDF-1.7 ...", "application/pdf", url))
    assert "PDF" in P.przetworz("https://example.com/a.pdf", opcje(), tmp_path)["blad"]
    monkeypatch.setattr(P, "pobierz", lambda url, **kw: (b"\0\1", "application/zip", url))
    assert "application/zip" in P.przetworz("https://example.com/a.zip", opcje(), tmp_path)["blad"]


def test_prosty_wyciag_bez_skryptow():
    w = P.prosty_wyciag("<title>A &amp; B</title><script>zle()</script><p>Jeden</p><p>Dwa</p>")
    assert w["tytul"] == "A & B" and w["tekst"] == "Jeden\nDwa"


# ------------------------------------------------------------------------------------------------ yt-dlp (atrapa)

YT_JSON = {"title": "Me at the zoo", "channel": "jawed", "duration": 19, "upload_date": "20050424",
           "description": "Opis " * 500, "view_count": 448, "like_count": 20, "tags": ["zoo"],
           "chapters": [{"start_time": 0, "title": "Intro"}], "subtitles": {"en": [], "de": []}}
ATRAPA_YTDLP = """import json, os, sys
a = sys.argv[1:]
open(os.environ["YTDLP_LOG"], "a", encoding="utf-8").write(json.dumps(a) + "\\n")
tryb = os.environ.get("YTDLP_TRYB", "")
if tryb == "bot":
    sys.stderr.write("ERROR: [youtube] x: Sign in to confirm you're not a bot\\n"); sys.exit(1)
if "-J" in a:
    print(open(os.environ["YTDLP_JSON"], encoding="utf-8").read()); sys.exit(0)
if tryb == "duzy":
    sys.exit(0)                                        # --max-filesize: yt-dlp pomija pobranie bez błędu
wzor = a[a.index("-o") + 1]
plik = wzor.replace("%(ext)s", "mp4")
open(plik, "wb").write(b"0" * 2_000_000)
print(plik)
"""


@pytest.fixture
def ytdlp(tmp_path, monkeypatch):
    b = tmp_path / "bin"
    atrapy.program(b, "yt-dlp", ATRAPA_YTDLP)
    log = tmp_path / "ytdlp.log"
    (tmp_path / "yt.json").write_text(json.dumps(YT_JSON), encoding="utf-8")
    monkeypatch.setenv("PATH", atrapy.sciezka(b))
    monkeypatch.setenv("YTDLP_LOG", str(log))
    monkeypatch.setenv("YTDLP_JSON", str(tmp_path / "yt.json"))
    monkeypatch.delenv("YTDLP_TRYB", raising=False)
    return lambda: [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]


def test_youtube_metadane(ytdlp, tmp_path):
    w = P.przetworz("https://youtu.be/jNQXAC9IVRw", opcje(), tmp_path / "linki")
    assert w["ok"] and w["tytul"] == "Me at the zoo" and w["kanal"] == "jawed" and w["dlugosc_s"] == 19
    assert w["data"] == "2005-04-24" and w["opis_uciety"] and len(w["opis"]) == P.MAX_OPISU
    assert w["rozdzialy"] == [{"od_s": 0, "tytul": "Intro"}] and w["napisy_autora"] == ["de", "en"]
    (argv,) = ytdlp()
    assert "-J" in argv and "--skip-download" in argv and argv[-1] == "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def test_youtube_wideo_360p(ytdlp, tmp_path):
    w = P.przetworz("https://www.youtube.com/watch?v=jNQXAC9IVRw", opcje(wideo=True, max_mb=25), tmp_path)
    assert w["wideo"] == {"plik": (tmp_path / "youtube-jNQXAC9IVRw" / "wideo.mp4").as_posix(), "mb": 2.0}
    pobranie = ytdlp()[1]
    assert pobranie[pobranie.index("-S") + 1] == P.SORT and "res:360" in P.SORT
    assert pobranie[pobranie.index("--max-filesize") + 1] == "25M"


def test_youtube_za_duzy_film_i_blokada(ytdlp, tmp_path, monkeypatch):
    monkeypatch.setenv("YTDLP_TRYB", "duzy")
    w = P.przetworz("https://youtu.be/jNQXAC9IVRw", opcje(wideo=True), tmp_path)
    assert w["ok"] and "większy niż 60 MB" in w["wideo_blad"] and "wideo" not in w     # opis filmu zostaje
    monkeypatch.setenv("YTDLP_TRYB", "bot")
    w = P.przetworz("https://youtu.be/jNQXAC9IVRw", opcje(), tmp_path)
    assert not w["ok"] and "nie jesteś botem" in w["blad"] and "nie loguję" in w["blad"]


def test_brak_ytdlp(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "narzedzie", lambda nazwa: None)
    w = P.przetworz("https://youtu.be/jNQXAC9IVRw", opcje(), tmp_path)
    assert not w["ok"] and "brak programu yt-dlp" in w["blad"]


def test_ytdlp_za_dlugo(monkeypatch, tmp_path):
    def za_dlugo(*a, **kw):
        raise P.subprocess.TimeoutExpired(a[0], 1)
    monkeypatch.setattr(P, "narzedzie", lambda nazwa: "/bin/yt-dlp")
    monkeypatch.setattr(P.subprocess, "run", za_dlugo)
    w = P.przetworz("https://youtu.be/jNQXAC9IVRw", opcje(), tmp_path)
    assert not w["ok"] and "nie skończył" in w["blad"]


def test_x_wideo_i_transkrypcja(ytdlp, tmp_path, monkeypatch):
    """Wpis z filmem: --wideo pobiera film yt-dlp z adresu wpisu, a transkrypcja idzie z pobranego pliku."""
    monkeypatch.setattr(P, "pobierz", lambda url, **kw: (FIXTURE.read_bytes(), "application/json", url))
    atrapa = tmp_path / "transkrybuj.py"
    atrapa.write_text("""import json, sys
from pathlib import Path
out = Path(sys.argv[sys.argv.index("-o") + 1]); out.mkdir(parents=True, exist_ok=True)
(out / "zrodlo.txt").write_text(sys.argv[1], encoding="utf-8")
(out / "transkrypcja.json").write_text(json.dumps({"mowa": [{"od": 0, "tekst": "Cześć"}, {"od": 2, "tekst": "x" * 5000}],
    "mowa_zrodlo": "rozpoznanie mowy"}), encoding="utf-8")
(out / "transkrypcja.md").write_text("# T", encoding="utf-8")
""", encoding="utf-8")
    monkeypatch.setattr(P, "skrypt_transkrypcji", lambda: atrapa)
    monkeypatch.setattr(P, "python_narzedzi", lambda: sys.executable)
    w = P.przetworz("https://x.com/przyklad_ai/status/2109179323370570193", opcje(wideo=True, transkrypcja=True),
                    tmp_path)
    kat = tmp_path / "x-2109179323370570193"
    assert w["wideo"]["plik"] == (kat / "wideo.mp4").as_posix()
    assert ytdlp()[0][-1] == "https://x.com/przyklad_ai/status/2109179323370570193"
    assert (kat / "transkrypcja" / "zrodlo.txt").read_text(encoding="utf-8") == (kat / "wideo.mp4").as_posix()
    t = w["transkrypcja"]
    assert t["tekst"].startswith("Cześć") and len(t["tekst"]) == P.MAX_TRANSKRYPCJI and t["uciete"]
    assert t["plik"].endswith("transkrypcja/transkrypcja.md")


def test_youtube_transkrypcja_bez_pobierania(ytdlp, tmp_path, monkeypatch):
    """Sama transkrypcja YouTube: skrypt dostaje link (napisy platformy bez pobierania filmu)."""
    zrodla = []

    def transkrybuj(zrodlo, katalog, max_min):
        zrodla.append(zrodlo)
        return {"tekst": "", "uwaga": "w filmie nie rozpoznano mowy"}
    monkeypatch.setattr(P, "transkrybuj", transkrybuj)
    w = P.przetworz("https://youtu.be/jNQXAC9IVRw", opcje(transkrypcja=True), tmp_path)
    assert zrodla == ["https://www.youtube.com/watch?v=jNQXAC9IVRw"] and len(ytdlp()) == 1 and "wideo" not in w


def test_transkrypcja_blad_nie_psuje_wyniku(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "skrypt_transkrypcji", lambda: None)
    w = {}
    P._transkrypcja(w, "https://youtu.be/x", opcje(transkrypcja=True), tmp_path)
    assert "nie ma skryptu transkrypcji" in w["transkrypcja_blad"]


def test_skrypt_transkrypcji_z_repo(monkeypatch):
    monkeypatch.delenv("JARVO_REPO", raising=False)
    assert P.skrypt_transkrypcji() == REPO / "shared/skills/transkrypcja-filmu/scripts/transkrybuj.py"


# ------------------------------------------------------------------------------------------------ narzędzie wtyczki

ATRAPA_SKRYPTU = """import json, sys
print(json.dumps({"linki": [{"url": u, "ok": True, "argv": sys.argv[1:]} for u in sys.argv[1:] if u.startswith("http")],
                  "uwaga": "dane"}, ensure_ascii=False, indent=2))
"""


def test_narzedzie_pobierz_link(tmp_path, monkeypatch):
    home = tmp_path / "dane" / "profiles" / "jarvo"
    (home / "scripts").mkdir(parents=True)
    (home / "scripts" / "pobierz_link.py").write_text(ATRAPA_SKRYPTU, encoding="utf-8")
    monkeypatch.delenv("JARVO_TOOLS_PYTHON", raising=False)
    wynik = L.obsluz({"linki": ["https://x.com/a/status/1"], "transkrypcja": True}, hermes_home=str(home))
    assert "\n" not in wynik                                                # zwięzły JSON do kontekstu modelu
    (link,) = json.loads(wynik)["linki"]
    katalog = str(tmp_path / "dane" / "jarvo" / "workspaces" / "jarvo" / "linki")
    assert link["argv"] == ["https://x.com/a/status/1", "-o", katalog, "--transkrypcja"]


def test_narzedzie_walidacja_i_awarie(tmp_path, monkeypatch):
    assert "co najmniej jeden" in json.loads(L.obsluz({"linki": []}))["error"]
    assert "Najwyżej 5" in json.loads(L.obsluz({"linki": [f"https://e.pl/{i}" for i in range(6)]}))["error"]
    monkeypatch.setattr(L, "skrypt", lambda h: None)
    assert "Brak skryptu" in json.loads(L.obsluz({"linki": ["https://e.pl"]}, hermes_home=str(tmp_path)))["error"]
    zly = tmp_path / "zly.py"
    zly.write_text("import sys; sys.stderr.write('Traceback: boom\\n'); sys.exit(3)", encoding="utf-8")
    monkeypatch.setattr(L, "skrypt", lambda h: zly)
    assert "kod 3" in json.loads(L.obsluz({"linki": ["https://e.pl"]}, hermes_home=str(tmp_path)))["error"]


def test_narzedzie_znajduje_skrypt_w_repo(monkeypatch):
    monkeypatch.delenv("JARVO_REPO", raising=False)
    assert L.skrypt(None) == REPO / "profiles" / "jarvo" / "scripts" / "pobierz_link.py"
