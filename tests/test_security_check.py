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
                return self.odp(200, b'<html><script src="/assets/app.js"></script><script src="https://cdn.obca.pl/x.js">'
                                     b'</script></html>', "text/html")
            if p == "/assets/app.js":
                js = f'const a="{jwt("anon")}";' + (f'const s="{KLUCZ}";const r="{jwt("service_role")}";' if dziurawa else "")
                return self.odp(200, js.encode(), "application/javascript")
            if p == "/api/admin":
                return self.odp(200, b'{"users":[]}') if dziurawa or self.sesja() else self.odp(401)
            if p == "/api/orders/1":
                s = self.sesja()
                if dziurawa or s == "A":
                    return self.odp(200, b'{"id":1,"owner":"A","adres":"ul. Tajna 1"}')
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
    srv, base = aplikacja(dziurawa=False)
    try:
        sc.main(["url", base, "--json"])
    finally:
        srv.shutdown()
    assert not [x for x in json.loads(capsys.readouterr().out)["ustalenia"] if "JS" in x["co"]]   # klucz anon jest publiczny


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
