"""Telefon testowy Twórcy aplikacji: proxy ekranu ws-scrcpy w Jarvo HQ (:9122, token → ciasteczko, WebSocket),
link agenta (jarvo_link.py --android) i polecenie `jarvo android`. Bez Redroida: atrapa ws-scrcpy na gnieździe."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from conftest import load_script

ROOT = Path(__file__).resolve().parent.parent


def _wolny_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class AtrapaEkranu:
    """Udaje ws-scrcpy: na zwykłe żądanie odsyła swój nagłówek (widać, co przepuściło proxy), na WebSocket
    odpowiada 101 i odbija bajty."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._petla, daemon=True).start()

    def _petla(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._obsluz, args=(c,), daemon=True).start()

    def _obsluz(self, c):
        with c:
            buf = b""
            while b"\r\n\r\n" not in buf:
                d = c.recv(4096)
                if not d:
                    return
                buf += d
            head = buf.partition(b"\r\n\r\n")[0]
            if b"Upgrade: websocket" in head:
                c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
                while True:
                    d = c.recv(4096)
                    if not d:
                        return
                    c.sendall(d)
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"
                      % len(head) + head)

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)     # budzi accept() w wątku; samo close() zostawia gniazdo w nasłuchu
        except OSError:
            pass
        self.sock.close()


@pytest.fixture
def hq(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    atrapa = AtrapaEkranu()
    port = _wolny_port()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("JARVO_PREVIEW_PORT", "0")
    monkeypatch.setenv("JARVO_ANDROID_SCREEN_PORT", str(port))
    monkeypatch.setenv("JARVO_ANDROID_SCREEN_UPSTREAM", f"127.0.0.1:{atrapa.port}")
    monkeypatch.setenv("JARVO_SHARE_KEYS", "0")
    monkeypatch.delitem(sys.modules, "jarvo_hq_screen_state", raising=False)
    api = load_script("hq/plugin/plugin_api.py", "jarvo_hq_plugin_api_ekran")
    yield api, port, atrapa
    if getattr(api._screen, "server", None):
        api._screen.server.shutdown()
        api._screen.server.server_close()
    atrapa.close()


def _token(api, ttl=None) -> str:
    return api.core.link_for(api.core.LINKS_FILE, api.core.SCREEN_ROOT, time.time(), ttl or api.core.SCREEN_TTL)


def _zapytaj(port: int, req: bytes, czytaj_do_konca: bool = True) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(req)
        out = b""
        while True:
            d = s.recv(65536)
            if not d:
                break
            out += d
            if not czytaj_do_konca:
                break
        return out


def test_token_daje_ciasteczko_i_przekierowanie(hq):
    api, _, _ = hq
    tok = _token(api)
    kind, odp = api.screen_request(f"GET /{tok}/ HTTP/1.1\r\nHost: x".encode(), time.time())
    head = odp.decode("latin-1")
    assert kind == "odpowiedz" and head.startswith("HTTP/1.1 302")
    assert "Location: /\r\n" in head
    assert f"Set-Cookie: {api.SCREEN_COOKIE}={tok}; Path=/;" in head and "HttpOnly" in head and "SameSite=Lax" in head
    assert api.core.SCREEN_TTL - 60 < int(head.split("Max-Age=")[1].split(";")[0]) <= api.core.SCREEN_TTL


def test_bez_ciasteczka_albo_z_cudzym_tokenem_403(hq, tmp_path):
    api, _, _ = hq
    now = time.time()
    kind, odp = api.screen_request(b"GET / HTTP/1.1\r\nHost: x", now)
    assert kind == "odpowiedz" and odp.startswith(b"HTTP/1.1 403")
    strona = tmp_path / "jarvo" / "workspaces" / "jarvo-web" / "site"
    strona.mkdir(parents=True)
    obcy = api.core.link_for(api.core.LINKS_FILE, strona, now)           # link podglądu strony, nie ekranu
    for tok in (obcy, "zmyslony"):
        kind, odp = api.screen_request(f"GET / HTTP/1.1\r\nCookie: {api.SCREEN_COOKIE}={tok}".encode(), now)
        assert odp.startswith(b"HTTP/1.1 403")
        kind, odp = api.screen_request(f"GET /{tok}/ HTTP/1.1\r\nHost: x".encode(), now)
        assert odp.startswith(b"HTTP/1.1 403")
    stary = _token(api)
    kind, odp = api.screen_request(f"GET / HTTP/1.1\r\nCookie: {api.SCREEN_COOKIE}={stary}".encode(),
                                   now + api.core.SCREEN_TTL + 1)
    assert odp.startswith(b"HTTP/1.1 403")                               # po 12 h link i ciasteczko wygasają
    assert api.screen_request(b"bzdura", now)[1].startswith(b"HTTP/1.1 400")


def test_przekazanie_bez_ciasteczek_i_z_zamknieciem(hq):
    api, _, atrapa = hq
    tok = _token(api)
    kind, head = api.screen_request((f"GET /bundle.js?x=1 HTTP/1.1\r\nHost: 1.2.3.4:9122\r\nConnection: keep-alive\r\n"
                                     f"Cookie: sesja_dashboardu=tajne; {api.SCREEN_COOKIE}={tok}\r\nAccept: */*").encode(),
                                    time.time())
    tekst = head.decode("latin-1")
    assert kind == "przekaz" and tekst.startswith("GET /bundle.js?x=1 HTTP/1.1\r\n")
    assert f"Host: 127.0.0.1:{atrapa.port}" in tekst and "Accept: */*" in tekst
    assert "Cookie" not in tekst and "tajne" not in tekst and tok not in tekst
    assert "Connection: close" in tekst and "keep-alive" not in tekst
    kind, head = api.screen_request((f"GET /?action=proxy-adb HTTP/1.1\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n"
                                     f"Cookie: {api.SCREEN_COOKIE}={tok}").encode(), time.time())
    tekst = head.decode("latin-1")
    assert "Connection: Upgrade" in tekst and "Connection: close" not in tekst


def test_proxy_na_gniazdach_http_i_websocket(hq):
    api, port, _ = hq
    tok = _token(api)
    odp = _zapytaj(port, f"GET /{tok}/ HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    assert odp.startswith(b"HTTP/1.1 302") and f"{api.SCREEN_COOKIE}={tok}".encode() in odp
    odp = _zapytaj(port, b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
    assert odp.startswith(b"HTTP/1.1 403")
    odp = _zapytaj(port, f"GET /index.html HTTP/1.1\r\nHost: localhost\r\nCookie: a=b; {api.SCREEN_COOKIE}={tok}\r\n\r\n".encode())
    assert odp.startswith(b"HTTP/1.1 200")
    cialo = odp.partition(b"\r\n\r\n")[2]
    assert cialo.startswith(b"GET /index.html HTTP/1.1") and b"Cookie" not in cialo and b"Connection: close" in cialo
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(f"GET /?action=stream HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n"
                  f"Cookie: {api.SCREEN_COOKIE}={tok}\r\n\r\n".encode())
        assert s.recv(4096).startswith(b"HTTP/1.1 101")
        for ramka in (b"\x81\x04ping", b"\x82\x03abc"):
            s.sendall(ramka)
            assert s.recv(4096) == ramka                                # strumień WebSocket idzie w obie strony


def test_proxy_gdy_telefon_wylaczony(hq):
    api, port, atrapa = hq
    tok = _token(api)
    atrapa.close()
    odp = _zapytaj(port, f"GET / HTTP/1.1\r\nHost: localhost\r\nCookie: {api.SCREEN_COOKIE}={tok}\r\n\r\n".encode())
    assert odp.startswith(b"HTTP/1.1 503") and "jarvo android on".encode() in odp


def test_podglad_stron_nie_przyjmuje_tokenu_ekranu(hq):
    """Token ekranu w tym samym pliku linków nie otwiera niczego na serwerze podglądu stron (:9120)."""
    api, _, _ = hq
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api._preview_handler())
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        tok = _token(api)
        odp = _zapytaj(srv.server_address[1], f"GET /{tok}/ HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n".encode())
        assert odp.startswith(b"HTTP/1.0 404") or odp.startswith(b"HTTP/1.1 404")
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------- link dla agenta

def test_jarvo_link_android(tmp_path):
    env = {**os.environ, "HERMES_HOME": str(tmp_path), "JARVO_ANDROID_SCREEN_URL": "http://100.64.0.7:9122"}
    r = subprocess.run([sys.executable, str(ROOT / "scripts/jarvo_link.py"), "--android"], env=env,
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    url = r.stdout.strip()
    assert url.startswith("http://100.64.0.7:9122/") and url.endswith("/")
    tok = url.rstrip("/").rsplit("/", 1)[1]
    linki = json.loads((tmp_path / "jarvo/state/preview-links.json").read_text(encoding="utf-8"))
    assert linki[tok]["root"] == "@android-ekran" and linki[tok]["exp"] - time.time() <= 12 * 3600
    r2 = subprocess.run([sys.executable, str(ROOT / "scripts/jarvo_link.py"), "--android"], env=env,
                        capture_output=True, text=True, timeout=30)
    assert r2.stdout.strip() == url                                      # ten sam link, póki ważny


# ---------------------------------------------------------------- jarvo android

def _shim(d: Path, name: str, body: str) -> None:
    p = d / name
    p.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    p.chmod(0o755)


def _jarvo_android(tmp_path, *args, profile_line: str | None = None) -> tuple[subprocess.CompletedProcess, Path]:
    local = tmp_path / "flota"
    (local / "compose").mkdir(parents=True, exist_ok=True)
    env_file = local / "compose/.env"
    if not env_file.exists():
        env_file.write_text("DASHBOARD_PASSWORD=x\n" + (profile_line + "\n" if profile_line else ""), encoding="utf-8")
    shims = tmp_path / "shims"
    shims.mkdir(exist_ok=True)
    _shim(shims, "docker", 'echo "docker $*" >> "$JARVO_TEST_LOG"; [ "$1" = ps ] && exit 0; exit 0\n')
    env = {**os.environ, "PATH": f"{shims}:{os.environ['PATH']}", "JARVO_LOCAL": str(local),
           "JARVO_TEST_LOG": str(tmp_path / "docker.log")}
    r = subprocess.run(["bash", str(ROOT / "bin/jarvo"), "android", *args], env=env, capture_output=True, text=True,
                       timeout=30, stdin=subprocess.DEVNULL)
    return r, env_file


def test_jarvo_android_status_i_off(tmp_path):
    r, env_file = _jarvo_android(tmp_path, "status", profile_line="COMPOSE_PROFILES=monitoring,android")
    assert r.returncode == 0, r.stderr
    assert "telefon testowy:       włączony, Redroid" in r.stdout and "Android:               nie działa" in r.stdout
    r, env_file = _jarvo_android(tmp_path, "off")
    assert r.returncode == 0, r.stderr
    assert "COMPOSE_PROFILES=monitoring\n" in env_file.read_text(encoding="utf-8")
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert "stop android android-emulator android-ekran" in log and "rm -f android android-emulator android-ekran" in log
    env_file.write_text("DASHBOARD_PASSWORD=x\nCOMPOSE_PROFILES=android-kvm\n", encoding="utf-8")
    r, _ = _jarvo_android(tmp_path, "status")
    assert "włączony, emulator" in r.stdout
    r, _ = _jarvo_android(tmp_path, "off")
    assert "COMPOSE_PROFILES" not in env_file.read_text(encoding="utf-8") and "DASHBOARD_PASSWORD=x" in env_file.read_text()
    r, _ = _jarvo_android(tmp_path, "status")
    assert "telefon testowy:       wyłączony" in r.stdout


def test_jarvo_android_zle_uzycie_i_brak_instalacji(tmp_path):
    r, _ = _jarvo_android(tmp_path, "byle")
    assert r.returncode == 1 and "jarvo android on [--emulator|--redroid] | off | status" in r.stderr
    r, _ = _jarvo_android(tmp_path, "on", "--szybko")
    assert r.returncode == 1 and "jarvo android on [--emulator|--redroid]" in r.stderr
    r = subprocess.run(["bash", str(ROOT / "bin/jarvo"), "android", "on"], env={**os.environ, "JARVO_LOCAL": str(tmp_path / "nic")},
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 1 and "nie jest zainstalowana" in r.stderr


def test_jarvo_android_on_na_macos(tmp_path):
    shims = tmp_path / "shims"
    shims.mkdir()
    _shim(shims, "uname", 'echo Darwin\n')
    r, env_file = _jarvo_android(tmp_path, "on")
    assert r.returncode == 1 and "Docker na macOS" in r.stderr
    assert "COMPOSE_PROFILES" not in env_file.read_text(encoding="utf-8")   # nic nie zmienione


@pytest.mark.skipif(Path("/dev/kvm").exists(), reason="ten host ma KVM: ścieżka bez wirtualizacji nie do sprawdzenia")
def test_jarvo_android_emulator_bez_kvm(tmp_path):
    r, env_file = _jarvo_android(tmp_path, "on", "--emulator")
    assert r.returncode == 1 and "Brak /dev/kvm" in r.stderr and "--redroid" in r.stderr
    assert "COMPOSE_PROFILES" not in env_file.read_text(encoding="utf-8")


@pytest.mark.skipif(Path("/dev/binder").exists() or "binder" in Path("/proc/filesystems").read_text(),
                    reason="ten host ma binder: ścieżka bez sterownika nie do sprawdzenia")
def test_jarvo_android_redroid_bez_bindera(tmp_path):
    shims = tmp_path / "shims"
    shims.mkdir()
    _shim(shims, "modprobe", 'echo "modprobe $*" >> "$JARVO_TEST_LOG"; exit 1\n')
    _shim(shims, "sudo", '"$@"\n')
    r, env_file = _jarvo_android(tmp_path, "on", "--redroid")
    assert r.returncode == 1 and "Brak modułu binder_linux" in r.stderr
    assert "modprobe binder_linux devices=binder,hwbinder,vndbinder" in (tmp_path / "docker.log").read_text()
    assert "COMPOSE_PROFILES" not in env_file.read_text(encoding="utf-8")
