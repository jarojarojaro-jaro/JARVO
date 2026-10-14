"""security_check.py: próby `atak` na dwóch lokalnych aplikacjach (dziurawej i poprawnej), klucze w JS strony,
zależności z rejestru (podstawiony, bez sieci)."""
import base64
import datetime as dt
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "profiles" / "jarvo-web" / "scripts"))
import security_check as sc  # noqa: E402

KLUCZ = "sk_live_" + "Q7w" * 8                     # sklejony, żeby skanery repo nie widziały klucza w pliku


def jwt(rola: str) -> str:
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b({'alg': 'HS256', 'typ': 'JWT'})}.{b({'iss': 'supabase', 'role': rola, 'ref': 'abcdefghijklmnop'})}.{'s' * 43}"


def aplikacja(dziurawa: bool):
    stan = {"proby": 0, "sesje": {"A", "B"}}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def odp(self, kod, tresc=b"", typ="application/json", **nag):
            self.send_response(kod)
            self.send_header("Content-Type", typ)
            for k, v in nag.items():
                self.send_header(k.replace("_", "-"), v)
            self.end_headers()
            self.wfile.write(tresc)

        def sesja(self):
            c = self.headers.get("Cookie", "")
            s = c.partition("sid=")[2] or None
            return s if s in stan["sesje"] else None

        def do_GET(self):
            p = self.path
            if p == "/":
                cache = ({"Set_Cookie": "sid=gosc; Path=/", "Cache_Control": "public, max-age=300"} if dziurawa
                         else {"Set_Cookie": "sid=gosc; Path=/; Secure; HttpOnly; SameSite=Lax", "Cache_Control": "private, no-store"})
                return self.odp(200, b'<html><script src="/assets/app.js"></script><script src="https://cdn.obca.pl/x.js">'
                                     b'</script></html>', "text/html", **cache)
            if p == "/assets/app.js":
                js = f'const a="{jwt("anon")}";' + (f'const s="{KLUCZ}";const r="{jwt("service_role")}";' if dziurawa else "")
                js += "\n//# sourceMappingURL=app.js.map" if dziurawa else ""
                return self.odp(200, js.encode(), "application/javascript")
            if p == "/assets/app.js.map" and dziurawa:
                mapa = {"version": 3, "sources": ["webpack://app/./src/lib/platnosci.ts", "webpack://app/./node_modules/react/index.js"],
                        "sourcesContent": [f'// TODO usunąć\nconst klucz = "{KLUCZ}";', "module.exports = {}"], "mappings": "AAAA"}
                return self.odp(200, json.dumps(mapa).encode())
            if p == "/api/admin":
                return self.odp(200, b'{"users":[]}') if dziurawa or self.sesja() else self.odp(401)
            if p == "/api/orders/1":
                s = self.sesja()
                if dziurawa or s == "A":
                    return self.odp(200, b'{"id":1,"owner":"A","adres":"ul. Tajna 1"}',
                                    Cache_Control="public, s-maxage=60" if dziurawa else "private, no-store")
                return self.odp(404 if s else 401)
            if p == "/uploads/obrazek.jpg":
                return self.odp(200, b"<html>x</html>", "text/html")
            if p == "/api/search":
                stan["proby"] += 1
                return self.odp(429 if not dziurawa and stan["proby"] > 5 else 200, b"[]")
            return self.odp(200, b"<html>SPA</html>", "text/html")          # SPA: każda nieznana ścieżka to index

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path == "/api/login":
                stan["proby"] += 1
                return self.odp(429 if not dziurawa and stan["proby"] > 5 else 401, b"{}", Retry_After="60")
            if self.path == "/api/upload":
                return self.odp(200, b'{"url":"/uploads/obrazek.jpg"}') if dziurawa else self.odp(415)
            if self.path == "/api/logout":
                if not dziurawa:
                    stan["sesje"].discard(self.sesja())
                return self.odp(204)
            return self.odp(404)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


ARGS = ["--chronione", "/api/admin", "/panel", "--sesja-a", "Cookie: sid=A", "--sesja-b", "Cookie: sid=B",
        "--zasob-a", "/api/orders/1", "--logowanie", "/api/login", "--upload", "/api/upload:plik", "--wyloguj", "/api/logout"]


@pytest.fixture(autouse=True)
def czyste_listy():
    sc.UWAGI.clear()
    sc.SPRAWDZONE.clear()


def test_atak_finds_holes_in_vulnerable_app(capsys):
    srv, base = aplikacja(dziurawa=True)
    try:
        assert sc.main(["atak", base, *ARGS, "--json"]) == 1
    finally:
        srv.shutdown()
    out = json.loads(capsys.readouterr().out)
    co = " | ".join(x["co"] for x in out["ustalenia"])
    assert "/api/admin odpowiada bez logowania" in co
    assert "konto B czyta zasób konta A" in co and "dostępny bez logowania" in co
    assert "logowanie bez limitu prób" in co
    assert "serwuje go jako stronę" in co and any(x["waga"] == "KRYTYCZNE" for x in out["ustalenia"])
    assert "stara sesja działa po wylogowaniu" in co
    assert "odpowiedź dla zalogowanego może trafić do cache CDN i do innej osoby (Cache-Control: public, s-maxage=60)" in co
    assert any("/panel" in x and "SPA" in x for x in out["nie_ocenione"])      # widok SPA to nie dziura


def test_atak_passes_correct_app(capsys):
    srv, base = aplikacja(dziurawa=False)
    try:
        assert sc.main(["atak", base, *ARGS, "--json"]) == 0
    finally:
        srv.shutdown()
    out = json.loads(capsys.readouterr().out)
    assert out["ustalenia"] == []
    ok = " | ".join(out["sprawdzone"])
    assert "/api/admin bez sesji: 401" in ok and "sesją konta B: 404" in ok and "limit prób działa (429" in ok
    assert "odrzucony (415)" in ok and "po wylogowaniu stara sesja nie działa" in ok
    assert "/api/orders/1 sesją konta A: private, no-store (poza wspólnym cache)" in ok


def test_atak_needs_owner_consent_outside_preview():
    assert sc.main(["atak", "https://sklep-klienta.pl", "--chronione", "/admin"]) == 2
    assert sc.lokalny("http://localhost:4321") and sc.lokalny("http://192.168.1.10") and not sc.lokalny("https://jarvo.pl")


def test_url_finds_server_keys_in_page_js(capsys):
    srv, base = aplikacja(dziurawa=True)
    try:
        sc.main(["url", base, "--json"])
    finally:
        srv.shutdown()
    txt = capsys.readouterr().out
    wyn = [x for x in json.loads(txt)["ustalenia"] if "JS wysyłanym do przeglądarki" in x["co"]]
    assert {x["co"].split(" w JS")[0] for x in wyn} == {"klucz Stripe (live)", "klucz Supabase service_role / JWT"}
    assert all(x["gdzie"].endswith("/assets/app.js") for x in wyn)
    assert KLUCZ not in txt                                                    # sekret nigdy w raporcie
    mapy = {x["co"]: x for x in json.loads(txt)["ustalenia"] if "map" in x["co"]}
    assert mapy["publiczna mapa źródeł z kodem źródłowym (1 własnych plików, np. src/lib/platnosci.ts)"]["waga"] == "ŚREDNIE"
    zmapy = mapy["klucz Stripe (live) w kodzie z publicznej mapy źródeł"]
    assert zmapy["waga"] == "KRYTYCZNE" and zmapy["gdzie"].endswith("/assets/app.js.map → src/lib/platnosci.ts")
    srv, base = aplikacja(dziurawa=False)
    try:
        sc.main(["url", base, "--json"])
    finally:
        srv.shutdown()
    czyste = json.loads(capsys.readouterr().out)["ustalenia"]
    assert not [x for x in czyste if "JS" in x["co"] or "map" in x["co"]]     # klucz anon jest publiczny; .map to strona SPA, nie mapa


def test_source_maps_inline_and_without_code(monkeypatch):
    mapa = {"version": 3, "sources": ["../src/main.ts"], "sourcesContent": ["const x = 1"], "mappings": ""}
    wbud = "data:application/json;base64," + base64.b64encode(json.dumps(mapa).encode()).decode()
    wyn = sc.mapa_zrodel("https://a.pl/app.js", f"x()\n//# sourceMappingURL={wbud}", {})
    assert [(x["waga"], x["co"]) for x in wyn] == [("ŚREDNIE", "publiczna mapa źródeł z kodem źródłowym (1 własnych plików, np. src/main.ts)")]
    assert wyn[0]["gdzie"] == "https://a.pl/app.js (mapa wbudowana w skrypt)"
    pytania = []

    def fake(url, **kw):
        pytania.append(url)
        return (200, {}, [], json.dumps({"version": 3, "sources": ["a.ts", "b.ts"], "mappings": ""}).encode())
    monkeypatch.setattr(sc, "pobierz", fake)
    wyn = sc.mapa_zrodel("https://a.pl/_next/static/x.js?v=2", "x()", {"sourcemap": "/maps/x.js.map"})
    assert pytania == ["https://a.pl/maps/x.js.map"] and wyn[0]["waga"] == "NISKIE" and "2 plików" in wyn[0]["co"]
    assert sc.mapa_zrodel("https://a.pl/x.js", "x()\n//# sourceMappingURL=https://cdn.obca.pl/x.js.map", {}) == []   # obca domena
    assert pytania == ["https://a.pl/maps/x.js.map"]
    sc.mapa_zrodel("https://a.pl/y.js?v=1", "y()", {})
    assert pytania[-1] == "https://a.pl/y.js.map"                               # bez komentarza: plik .map obok skryptu


def test_dependencies_missing_young_and_lookalike(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^19", "expres": "^4", "zmyslony-pakiet-ai": "1.0.0",
                                                                         "nowy-pakiet": "0.1.0", "lokalny": "file:../x"}}))
    (tmp_path / "requirements.txt").write_text("# komentarz\nrequests==2.32\nreqeusts>=1\n-r inne.txt\n")
    rejestr = {
        "https://api.npmjs.org/downloads/point/last-week/react": (200, {"downloads": 40_000_000}),
        "https://api.npmjs.org/downloads/point/last-week/expres": (200, {"downloads": 120}),
        "https://registry.npmjs.org/expres": (200, {"time": {"created": "2014-01-01T00:00:00Z"}}),
        "https://api.npmjs.org/downloads/point/last-week/zmyslony-pakiet-ai": (404, None),
        "https://registry.npmjs.org/zmyslony-pakiet-ai": (404, None),
        "https://api.npmjs.org/downloads/point/last-week/nowy-pakiet": (200, {"downloads": 35}),
        "https://registry.npmjs.org/nowy-pakiet": (200, {"time": {"created": "2026-09-10T00:00:00Z"}}),
        "https://pypi.org/pypi/requests/json": (200, {"releases": {"2.0": [{"upload_time_iso_8601": "2011-02-14T00:00:00Z"}]}}),
        "https://pypistats.org/api/packages/requests/recent": (200, {"data": {"last_week": 300_000_000}}),
        "https://pypi.org/pypi/reqeusts/json": (0, None),                  # rejestr milczy: nie oceniono, nie „czysto”
    }
    monkeypatch.setattr(sc, "_json_z", lambda url, timeout=10: rejestr.get(url, (0, None)))
    assert [n for _, n, _ in sc.manifesty(tmp_path)] == ["react", "expres", "zmyslony-pakiet-ai", "nowy-pakiet", "requests", "reqeusts"]
    wyn = sc.zaleznosci(tmp_path, dzis=dt.date(2026, 9, 30))
    co = {x["co"] for x in wyn}
    assert any("zmyslony-pakiet-ai nie istnieje" in c for c in co)
    assert any("expres różni się jedną literą od popularnego express" in c for c in co)
    assert any("nowy-pakiet jest nowa (20 dni)" in c for c in co)
    assert not any("react " in c or "requests " in c for c in co)
    assert sc.UWAGI == ["pypi reqeusts: rejestr nie odpowiedział, nie oceniono"]
    assert sc.odleglosc1("reqeusts", "requests") and not sc.odleglosc1("react", "react")


# ------------------------------------------------------------------ GPS w zdjęciach

def _tiff_gps(e="<", szer=(52, 13, 48.5), dl=(21, 0, 36), ns="N", ew="E"):
    """Minimalny EXIF (TIFF) z GPS IFD: 52°13'48.5"N 21°0'36"E = 52.23014, 21.01."""
    import struct
    asc = lambda c: c.encode() + b"\0\0\0"
    ifd0 = struct.pack(e + "H", 1) + struct.pack(e + "HHII", 0x8825, 4, 1, 26) + struct.pack(e + "I", 0)
    wpisy = [(1, 2, 2, asc(ns)), (2, 5, 3, struct.pack(e + "I", 80)), (3, 2, 2, asc(ew)), (4, 5, 3, struct.pack(e + "I", 104))]
    gps = struct.pack(e + "H", 4) + b"".join(struct.pack(e + "HHI", t, ty, n) + v for t, ty, n, v in wpisy) + struct.pack(e + "I", 0)
    dane = b"".join(struct.pack(e + "II", int(x * 10), 10) for x in (*szer, *dl))
    return (b"II*\0" if e == "<" else b"MM\0*") + struct.pack(e + "I", 8) + ifd0 + gps + dane


def _jpg(tiff=None):
    import struct
    app1 = b"\xff\xe1" + struct.pack(">H", len(tiff) + 8) + b"Exif\0\0" + tiff if tiff else b""
    return b"\xff\xd8" + app1 + b"\xff\xda" + b"\0" * 64 + b"\xff\xd9"


def test_gps_in_image_formats():
    import struct
    import zlib
    t = _tiff_gps()
    assert sc.gps_w_obrazie(_jpg(t)) == (52.23014, 21.01)
    assert sc.gps_w_obrazie(_tiff_gps(">", ns="S", ew="W")) == (-52.23014, -21.01)
    chunk = lambda typ, d: struct.pack(">I", len(d)) + typ + d + struct.pack(">I", zlib.crc32(typ + d))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", b"\0" * 13) + chunk(b"eXIf", t) + chunk(b"IDAT", b"x") + chunk(b"IEND", b"")
    assert sc.gps_w_obrazie(png) == (52.23014, 21.01)
    exif = b"Exif\0\0" + t
    webp = b"RIFF" + struct.pack("<I", 0) + b"WEBP" + b"VP8X" + struct.pack("<I", 10) + b"\0" * 10 \
        + b"EXIF" + struct.pack("<I", len(exif)) + exif
    assert sc.gps_w_obrazie(webp) == (52.23014, 21.01)
    xmp = b'<x:xmpmeta><rdf:Description exif:GPSLatitude="50,3.6N" exif:GPSLongitude="19,56.4E"/></x:xmpmeta>'
    assert sc.gps_w_obrazie(b"\0\0\0\x1cftypheic" + xmp) == (50.06, 19.94)
    assert sc.gps_w_obrazie(_jpg()) is None                                         # bez EXIF
    assert sc.gps_w_obrazie(_jpg(_tiff_gps(szer=(0, 0, 0), dl=(0, 0, 0)))) is None   # aparat bez pozycji
    assert sc.gps_w_obrazie(_jpg(t[:60])) is None                                   # ucięty EXIF: bez wyjątku


def test_gps_in_repo_and_on_page(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "SPRAWDZONE", [])
    monkeypatch.setattr(sc, "UWAGI", [])
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "zespol.JPG").write_bytes(_jpg(_tiff_gps()))
    (tmp_path / "public" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.jpg").write_bytes(_jpg(_tiff_gps()))
    wyn = sc.gps_w_repo(tmp_path)
    assert [(x["waga"], x["gdzie"]) for x in wyn] == [("ŚREDNIE", "public/zespol.JPG")]
    assert "52.23014, 21.01" in wyn[0]["co"] and "openstreetmap.org/?mlat=52.23014&mlon=21.01" in wyn[0]["co"]
    assert "--usun-metadane" in wyn[0]["poprawka"]

    html = ('<img src="/img/a.jpg"><img src="data:image/png;base64,AA"><img src="/logo.svg">'
            '<picture><source srcset="/img/b.webp 480w, /img/c.webp 960w"></picture>'
            '<meta property="og:image" content="https://cdn.example/og.jpg">')
    assert sc.zdjecia_strony("https://a.pl", html) == ["https://a.pl/img/a.jpg", "https://a.pl/img/b.webp",
                                                        "https://a.pl/img/c.webp", "https://cdn.example/og.jpg"]
    pliki = {"https://a.pl/img/a.jpg": _jpg(), "https://a.pl/img/b.webp": _jpg(), "https://cdn.example/og.jpg": _jpg(_tiff_gps())}
    monkeypatch.setattr(sc, "pobierz", lambda url, **kw: (200, {}, [], pliki[url]) if url in pliki else (404, {}, [], b""))
    wyn = sc.gps_na_stronie("https://a.pl", html)
    assert [x["gdzie"] for x in wyn] == ["https://cdn.example/og.jpg"] and "cache CDN" in wyn[0]["poprawka"]
    del pliki["https://cdn.example/og.jpg"]
    assert sc.gps_na_stronie("https://a.pl", html) == [] and sc.SPRAWDZONE == ["zdjęcia bez GPS (2 sprawdzonych)"]
    assert sc.gps_na_stronie("https://a.pl", "<p>bez zdjęć</p>") == [] and "brak <img>" in sc.UWAGI[0]


def test_cache_of_private_responses(monkeypatch, capsys):
    assert sc.cache_wspolny({"cache-control": "private, max-age=60"}) is None
    assert sc.cache_wspolny({"cache-control": "no-store"}) is None
    assert sc.cache_wspolny({"cache-control": "max-age=0, must-revalidate"}) is None
    assert sc.cache_wspolny({}) is None                                   # brak nagłówka: zależy od CDN, nie zgadujemy
    assert sc.cache_wspolny({"cache-control": "public"}) == "Cache-Control: public"
    assert sc.cache_wspolny({"cache-control": "s-maxage=600, stale-while-revalidate"}).startswith("Cache-Control")
    assert sc.cache_wspolny({"cache-control": "max-age=60"}) == "Cache-Control: max-age=60"
    # nagłówek tylko dla CDN wygrywa z private w Cache-Control (Vercel, Cloudflare)
    assert sc.cache_wspolny({"cache-control": "private", "cdn-cache-control": "max-age=3600"}) == "cdn-cache-control: max-age=3600"
    assert sc.z_cache({"cf-cache-status": "HIT"}) and sc.z_cache({"x-vercel-cache": "STALE"}) and sc.z_cache({"age": "12"})
    assert not sc.z_cache({"cf-cache-status": "MISS", "age": "0"}) and not sc.z_cache({"cf-cache-status": "DYNAMIC"})

    def strona(naglowki):
        sc.SPRAWDZONE.clear()
        monkeypatch.setattr(sc, "pobierz", lambda url, **kw: (200, naglowki, ["session=abc; Secure; HttpOnly; SameSite=Lax"],
                                                               b"<html></html>") if url == "https://a.pl" else (404, {}, [], b""))
        return {x["co"]: x["waga"] for x in sc.strona("https://a.pl")}

    co = strona({"cache-control": "public, max-age=300"})
    assert co["odpowiedź z ciasteczkiem sesji session może trafić do cache CDN (Cache-Control: public, max-age=300)"] == "WYSOKIE"
    co = strona({"cache-control": "public, max-age=300", "cf-cache-status": "HIT"})
    assert co["CDN podaje z cache odpowiedź z ciasteczkiem sesji session (każdy dostaje cudzą sesję)"] == "KRYTYCZNE"
    co = strona({"cache-control": "private, no-store"})
    assert not [c for c in co if "cache" in c] and "ciasteczko sesji session: odpowiedź poza wspólnym cache" in sc.SPRAWDZONE
