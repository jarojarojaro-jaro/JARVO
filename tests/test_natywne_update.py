"""`jarvo update` i `jarvo uninstall` natywnie (docs/NATYWNIE.md: N09, N11, c4, S09, D07, D08, N15, etap E13).

Aktualizacja na atrapach (instalator nowej wersji, `jarvo doctor --json` i procesy podaje Zaplecze, GitHub to serwer
na 127.0.0.1 z portów prób 19220–19229): ref instalacji (--ref zapamiętany, nowszy `.jarvo-ref` z ponownej instalacji
wygrywa), klucz tylko w nagłówku do API (bez przeniesienia na codeload po przekierowaniu) i nigdy w wyjściu, w logu ani
w otoczeniu programów; ta sama wersja = nic; nowa wersja obok starej z opcjami tej instalacji; urwane pobieranie
(IncompleteRead) i uszkodzone archiwum pobierane jeszcze raz; powrót instalatorem poprzedniej wersji przy błędzie po
przełączeniu, przy regresji doctora i przy nieprzewidzianym wyjątku (stan „failed”, bez śladu stosu na ekranie);
awaryjny current.json; jedna aktualizacja naraz; sprzątanie starych wersji poza tymi, z których coś korzysta (także
wstrzymane przez proces, którego ścieżki nie widać); nowy Python przy tym samym pinie Hermesa i locku venvu = katalogi
obok (atrapy git i uv z testów Hermesa i instalatora). Pomocnik dla panelu (kontrakt update-request i update.json
z hq/plugin/plugin_api.py): pierwsze sprawdzenie, przerwana aktualizacja, błąd obiegu i sygnał końca; całość od
przycisku do końca: prawdziwy nadzorca z usługą `aktualizacje`, prawdziwy plugin_api (TestClient) i prawdziwe
`jarvo update` w tle na atrapie instalatora.

Odinstalowanie na atrapach: zgoda (bez terminala tylko z --yes, pytania na stderr), stop, procesy Jarva bez tego
procesu i jego przodków, autostart off, dziennik zmian hosta od końca (wpis pliku z korzenia zapomniany, nie usuwany),
klucz GitHuba z magazynu (atrapa: magazynu właściciela test nie dotyka), dane tylko z --all, obce pliki zostają, skan
śladów; na Windows proces sprzątający (PowerShell bez cudzysłowów, apostrofy typograficzne; prawdziwy przebieg na
katalogu testu, bez RunOnce) i polecenie RunOnce z warunkiem (prawdziwy cmd.exe na katalogu testu). Lista procesów,
usuwanie drzew (tylko do odczytu, junction, zablokowany plik) i dopasowanie ścieżek na prawdziwym systemie. Bootstrap
zapisuje `.jarvo-ref` dla `jarvo update`.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import atrapy
from conftest import REPO, WINDOWS, uruchom_bash

sys.path.insert(0, str(REPO))
from jarvo import aktualizacja, cli, hermes, instalator, odinstalowanie, przenosne, sciezki, srodowisko  # noqa: E402
from jarvo import venvy, zmiany_hosta  # noqa: E402
from jarvo.odinstalowanie import Proces, Zaplecze  # noqa: E402

PORTY = range(19220, 19230)                  # porty prób obszaru update-uninstall
REPO_GH = "jarojarojaro-jaro/JARVO"
KLUCZ = "klucz-testowy-0123456789-abcdef"     # nie wygląda jak prawdziwy klucz GitHuba (validate.py)
PS1 = REPO / "jarvo" / "bootstrap" / "install.ps1"
SH = REPO / "jarvo" / "bootstrap" / "install.sh"


def _sha1(tekst: str) -> str:
    return hashlib.sha1(tekst.encode("utf-8")).hexdigest()


SHA_STARA, SHA_NOWA, SHA_INNA = _sha1("stara"), _sha1("nowa"), _sha1("inna")


# ---------------------------------------------------------------- instalacja na atrapach

def _kod(katalog: Path, sha: str | None, *, ref: str | None = None, sumy: tuple[str, ...] = ()) -> Path:
    """Katalog kodu Jarva: jarvo/start.py, manifest z podanymi sumami, `.jarvo-wersja` i `.jarvo-ref`."""
    (katalog / "jarvo").mkdir(parents=True, exist_ok=True)
    (katalog / "jarvo" / "start.py").write_text("# atrapa\n", encoding="utf-8")
    (katalog / "vendor").mkdir(exist_ok=True)
    narz = {f"n{i}": {"wersja": "1", "pliki": {"windows-x64": {"sha256": s}}} for i, s in enumerate(sumy)}
    (katalog / "vendor" / "natywne.lock.json").write_text(json.dumps({"version": 1, "hermes": {}, "narzedzia": narz}),
                                                          encoding="utf-8")
    if sha:
        (katalog / ".jarvo-wersja").write_text(sha + "\n", encoding="utf-8")
    if ref:
        (katalog / ".jarvo-ref").write_text(ref + "\n", encoding="utf-8")
    return katalog


def _instalacja(tmp_path: Path, *, sha: str = SHA_STARA, ref: str | None = None) -> tuple[sciezki.Uklad, Path]:
    """Układ jak po `jarvo instaluj` z bootstrapu: kod w `<program>/app/<sha12>`, current.json, narzedzia.json."""
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    app = _kod(u.program / "app" / sha[:12], sha, ref=ref)
    checkout = u.program / "hermes" / "f97608f178d1"
    checkout.mkdir(parents=True)
    py = u.program / "narzedzia" / "python313" / "3.13.17"
    py.mkdir(parents=True)
    narz = {"python313": {"wersja": "3.13.17+20261021", "katalog": str(py), "bin": [], "env": {}}}
    (u.stan / "narzedzia.json").write_text(json.dumps(narz), encoding="utf-8")
    (u.program / "current.json").write_text(json.dumps({"app": str(app), "hermes": str(checkout),
                                                        "wersja": sha[:12]}), encoding="utf-8")
    return u, app


def _ot(tmp_path: Path, *, moduly: dict | None = None, env: dict | None = None, **kw) -> instalator.Otoczenie:
    """Otoczenie na atrapach: bez JARVO_* właściciela, LOCALAPPDATA w katalogu testu (bez starej instalacji z WSL),
    wirtualny zegar, nikt nie słucha na portach."""
    e = {k: v for k, v in os.environ.items() if not k.startswith("JARVO_")}
    e.update({"JARVO_ROOT": str(tmp_path / "j"), "JARVO_PANEL_PORT": "19229",
              "LOCALAPPDATA": str(tmp_path / "lad"), **(env or {})})
    moduly = dict(moduly or {})

    def modul(nazwa):
        if nazwa not in moduly:
            raise ImportError(f"No module named 'jarvo.{nazwa}'")
        return moduly[nazwa]
    teraz = [0.0]
    kw.setdefault("czekaj", lambda s: teraz.__setitem__(0, teraz[0] + s))
    kw.setdefault("zegar", lambda: teraz[0])
    kw.setdefault("sluchacz", lambda port: None)
    kw.setdefault("zapytaj_http", lambda url, czas: None)
    return instalator.Otoczenie(modul=modul, env=e, **kw)


class Nadzorca:
    """Jak jarvo/nadzorca.py: kanał (polacz, status, stop), znacznik zatrzymania i stan z pliku."""
    CZAS_ZATRZYMANIA = 1.0

    def __init__(self, dziala: bool = False):
        self.dziala, self.stopy, self.znaczniki = dziala, [], []

    def polacz(self, u):
        if not self.dziala:
            raise ConnectionRefusedError("atrapa: nadzorca nie działa")
        return self

    def status(self):
        return {"nadzorca": {"pid": 1, "stan": "dziala"}, "uslugi": {}}

    def stop(self, czekaj: float = 0.0, powod: str = ""):
        self.dziala = False
        self.stopy.append(powod)
        return {"ok": True, "trwale": True}

    def stan_z_pliku(self, u):
        return {"dziala": self.dziala}

    def oznacz_zatrzymanie(self, u, powod=""):
        self.znaczniki.append(("oznacz", powod))
        (u.stan / "zatrzymany.json").write_text("{}", encoding="utf-8")

    def zdejmij_zatrzymanie(self, u):
        self.znaczniki.append(("zdejmij",))
        (u.stan / "zatrzymany.json").unlink(missing_ok=True)
        return True


class Autostart:
    """Jak jarvo/autostart.py: stan i wylacz (tylko pamięć)."""

    class BladAutostartu(RuntimeError):
        pass

    def __init__(self, wlaczony: bool = False):
        self.wlaczony, self.wylaczenia = wlaczony, 0

    def stan(self, u, wykonaj=None, *, env=None, **_kw):
        return {"mechanizm": "harmonogram" if self.wlaczony else None, "wlaczony": self.wlaczony, "nasz": True,
                "nazwa": "Jarvo-test", "opis": "włączony (atrapa)" if self.wlaczony else "wyłączony"}

    def wylacz(self, u, wykonaj=None, *, env=None, log=None, **_kw):
        bylo, self.wlaczony = self.wlaczony, False
        self.wylaczenia += 1
        return {"nazwa": "Jarvo-test", "usuniety": bylo, "uwagi": []}


class Rejestr:
    """HKCU w pamięci (interfejs zmiany_hosta.Rejestr): rejestru właściciela test nie dotyka."""

    def __init__(self, path: str = r"C:\Narzedzia"):
        self.wartosci = {("Environment", "Path"): (path, 2)}

    def czytaj(self, klucz, nazwa):
        return self.wartosci.get((klucz, nazwa))

    def zapisz(self, klucz, nazwa, wartosc, typ):
        self.wartosci[(klucz, nazwa)] = (wartosc, typ)

    def usun(self, klucz, nazwa):
        self.wartosci.pop((klucz, nazwa), None)

    def oglos(self):
        pass


class Instalator:
    """Atrapa `Zaplecze.strumien` dla instalatora wersji z argv (`<python> -I -u -X utf8 <app>/jarvo/start.py …
    instaluj …`): jak prawdziwy przełącza current.json (poprzedni do current.poprzedni.json) i zwraca kolejny kod."""

    def __init__(self, u: sciezki.Uklad, kody=(0,), przelacz=(True,)):
        self.u, self.kody, self.przelacz, self.wywolania = u, list(kody), list(przelacz), []

    def __call__(self, argv, *, env, cwd, log, czas=None):
        argv = [str(a) for a in argv]
        i = len(self.wywolania)
        self.wywolania.append({"argv": argv, "env": dict(env), "cwd": str(cwd)})
        app = Path(argv[5]).parent.parent
        if self.przelacz[min(i, len(self.przelacz) - 1)]:
            cur = self.u.program / "current.json"
            biez = json.loads(cur.read_text(encoding="utf-8"))
            if biez.get("app") != str(app):
                (self.u.program / "current.poprzedni.json").write_text(json.dumps(biez), encoding="utf-8")
                cur.write_text(json.dumps({**biez, "app": str(app), "wersja": app.name}), encoding="utf-8")
        log("Gotowe. Zmiany w tym przebiegu: atrapa.")
        return self.kody[min(i, len(self.kody) - 1)]

    def aplikacje(self) -> list[str]:
        return [Path(w["argv"][5]).parent.parent.name for w in self.wywolania]


class Doctor:
    """Atrapa `Zaplecze.przechwyc` dla `jarvo doctor --json`: wyniki zależne od katalogu kodu (nazwa = sha12)."""

    def __init__(self, mapa: dict | None = None, domyslne=(("korzeń", "ok"), ("Hermes", "ok"))):
        self.mapa, self.domyslne, self.wywolania = dict(mapa or {}), list(domyslne), []

    def __call__(self, argv, *, env, cwd, czas=600):
        argv = [str(a) for a in argv]
        self.wywolania.append({"argv": argv, "env": dict(env)})
        app = Path(argv[5]).parent.parent.name
        wyniki = self.mapa.get(app, self.domyslne)
        if wyniki is None:
            return 1, "Traceback: atrapa doctor nie działa"
        d = {"wyniki": [{"nazwa": n, "stan": s, "opis": "", "rada": ""} for n, s in wyniki],
             "bledy": sum(s == "blad" for _, s in wyniki), "uwagi": 0}
        return 0, "Uwaga przed JSON-em\n" + json.dumps(d, ensure_ascii=False)


def _zaplecze(**kw) -> Zaplecze:
    """Zaplecze na atrapach; magazyn kluczy zawsze atrapą (klucza GitHuba właściciela test nie czyta ani nie usuwa)."""
    domyslne = dict(procesy=lambda: [], zakoncz=lambda lista: [], odlacz=lambda argv, cwd=None: 4321,
                    pytaj=lambda tekst: "n", terminal=lambda: False,
                    wykonaj=lambda argv: (0, "") if "/FO" in [str(a) for a in argv] else (1, ""),
                    aplikacje=lambda nazwa: None, usun_aplikacje=lambda nazwa: None,
                    klucz_jest=lambda: False, usun_klucz=lambda: True, sesja=lambda pid: 1, pid=100)
    domyslne.update(kw)
    return Zaplecze(**domyslne)


# ---------------------------------------------------------------- serwer GitHuba na 127.0.0.1

class _Serwer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


class _GitHub(BaseHTTPRequestHandler):
    """api.github.com (pod /api) i codeload.github.com (pod /codeload) dla jednego repo."""

    def log_message(self, *_a):
        pass

    def _odpowiedz(self, kod: int, tresc: bytes = b"", naglowki: dict | None = None) -> None:
        self.send_response(kod)
        for k, v in (naglowki or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(tresc)))
        self.end_headers()
        self.wfile.write(tresc)

    def do_GET(self):
        s = self.server
        p = urllib.parse.urlsplit(self.path)
        s.zapytania.append({"sciezka": p.path, "zapytanie": p.query, "auth": self.headers.get("Authorization"),
                            "accept": self.headers.get("Accept")})
        api = f"/api/repos/{REPO_GH}"
        if p.path.startswith(f"{api}/commits/"):
            ref = urllib.parse.unquote(p.path.split("/commits/", 1)[1])
            if ref == "limit":
                return self._odpowiedz(403, b"{}", {"X-RateLimit-Remaining": "0"})
            if ref in s.prywatne and not self.headers.get("Authorization"):
                return self._odpowiedz(404, b"{}")
            sha = s.refy.get(ref)
            return self._odpowiedz(200, sha.encode()) if sha else self._odpowiedz(404, b"{}")
        if p.path == f"{api}/commits":
            return self._odpowiedz(200, json.dumps(s.lista).encode("utf-8"), {"Content-Type": "application/json"})
        if p.path.startswith(f"{api}/tarball/"):
            sha = p.path.rsplit("/", 1)[1]
            return self._odpowiedz(302, b"", {"Location": f"/codeload/{REPO_GH}/tar.gz/{sha}?token=tymczasowy"})
        if p.path.startswith(f"/codeload/{REPO_GH}/tar.gz/"):
            sha = p.path.rsplit("/", 1)[1]
            if s.urwij.get(sha):                     # jak codeload: chunked zamknięte przed ostatnim kawałkiem
                s.urwij[sha] -= 1
                self.close_connection = True
                self.wfile.write(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n10\r\n" + b"x" * 16 + b"\r\n")
                return None
            kolejne = s.kolejne.get(sha)
            dane = kolejne.pop(0) if kolejne else s.archiwa.get(sha)
            return self._odpowiedz(200, dane) if dane else self._odpowiedz(404, b"")
        return self._odpowiedz(404, b"")


def _archiwum(sha: str, *, start: bool = True) -> bytes:
    bufor = io.BytesIO()
    pliki = {f"JARVO-{sha}/README.md": b"readme"}
    if start:
        pliki[f"JARVO-{sha}/jarvo/start.py"] = b"# start\n"
        pliki[f"JARVO-{sha}/vendor/natywne.lock.json"] = b'{"version": 1, "hermes": {}, "narzedzia": {}}'
    with tarfile.open(fileobj=bufor, mode="w:gz") as tf:
        for nazwa, dane in pliki.items():
            info = tarfile.TarInfo(nazwa)
            info.size = len(dane)
            tf.addfile(info, io.BytesIO(dane))
    return bufor.getvalue()


@pytest.fixture
def github(monkeypatch):
    """Serwer udający GitHub na 127.0.0.1 (port z zakresu 19220–19229); adresy API i KOD modułu wskazują na niego."""
    httpd = None
    for port in PORTY:
        try:
            httpd = _Serwer(("127.0.0.1", port), _GitHub)
            break
        except OSError:
            continue
    if httpd is None:
        pytest.skip("brak wolnego portu 19220–19229")
    httpd.zapytania, httpd.refy, httpd.lista, httpd.archiwa, httpd.prywatne = [], {}, [], {}, set()
    httpd.urwij, httpd.kolejne = {}, {}            # urwane odpowiedzi i kolejne archiwa (np. uszkodzone, potem dobre)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    adres = f"http://127.0.0.1:{httpd.server_address[1]}"
    monkeypatch.setattr(aktualizacja, "API", f"{adres}/api")
    monkeypatch.setattr(aktualizacja, "KOD", f"{adres}/codeload")
    yield httpd
    httpd.shutdown()
    httpd.server_close()


# ---------------------------------------------------------------- ref, wersja, klucz

def test_ref_z_opcji_zmiennej_nowszego_zapisu_albo_main(tmp_path):
    """--ref, JARVO_REF, potem nowszy z dwóch: `.jarvo-ref` kodu (bootstrap, aktualizacja) albo zapamiętany --ref.
    Ref z samego sprawdzenia (pole `ref`) niczego nie przestawia: ponowna instalacja z innym JARVO_REF wygrywa."""
    u, app = _instalacja(tmp_path)
    assert aktualizacja.ustal_ref(u, {}) == "main"
    plik = app / ".jarvo-ref"
    plik.write_text("claude/epic-allen-qfjd0s\n", encoding="utf-8")
    assert aktualizacja.ustal_ref(u, {}) == "claude/epic-allen-qfjd0s"            # z bootstrapu
    aktualizacja.zapisz_stan(u, ref="main")                                      # zwykłe sprawdzenie: tylko opis
    assert aktualizacja.ustal_ref(u, {}) == "claude/epic-allen-qfjd0s"
    aktualizacja.zapamietaj_ref(u, "v1.2")                                       # `jarvo update --ref v1.2`
    assert aktualizacja.ustal_ref(u, {}) == "v1.2"
    teraz = time.time()
    plik.write_text("v2\n", encoding="utf-8")                                    # bootstrap z JARVO_REF=v2 potem
    os.utime(plik, (teraz + 30, teraz + 30))
    assert aktualizacja.ustal_ref(u, {}) == "v2"
    assert aktualizacja.ustal_ref(u, {"JARVO_REF": "inna"}) == "inna"
    assert aktualizacja.ustal_ref(u, {"JARVO_REF": "inna"}, "jawny") == "jawny"
    for zly in ("a b", "../x", "-zle"):
        with pytest.raises(aktualizacja.BladAktualizacji):
            aktualizacja.ustal_ref(u, {}, zly)
    aktualizacja.zapisz_stan(u, ref_jawny="zly ref", ref_kiedy=teraz + 60)       # zepsuty zapis pomijamy
    assert aktualizacja.ustal_ref(u, {}) == "v2"
    plik.unlink()                                                                # kod z kopii repo: bez .jarvo-ref
    aktualizacja.zapamietaj_ref(u, "v3")
    assert aktualizacja.ustal_ref(u, {}) == "v3"


def test_update_z_ref_zapamietuje_go_tez_przy_tej_samej_wersji(tmp_path):
    """`jarvo update --ref v3` do tej samej wersji (kod nie dostaje nowego `.jarvo-ref`): następne `jarvo update` dalej
    sprawdza v3, a pomocnik pod nadzorcą nie dostaje JARVO_REF z okna instalacji (env_podprocesu)."""
    u, app = _instalacja(tmp_path, ref="main")
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_STARA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=Instalator(u), przechwyc=Doctor()), ref="v3")
    assert kod == 0 and raport["wynik"] == "aktualne" and raport["ref"] == "v3", log
    assert aktualizacja.ref_kodu(app) == "main" and aktualizacja.ustal_ref(u, {}) == "v3"
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=Instalator(u), przechwyc=Doctor()))
    assert raport["ref"] == "v3", log
    env = odinstalowanie.env_podprocesu(u, {"JARVO_REF": "z-okna", "jarvo_token": "x" * 20, "PATH": "p"})
    assert env == {"PATH": "p"}


def test_wersja_kodu_z_pliku_albo_gita(tmp_path):
    assert aktualizacja.wersja_kodu(_kod(tmp_path / "a", SHA_NOWA)) == SHA_NOWA
    assert aktualizacja.wersja_kodu(_kod(tmp_path / "b", None)) is None
    assert aktualizacja.wersja_kodu(None) is None
    (tmp_path / "b" / ".jarvo-wersja").write_text("nie-sha\n", encoding="utf-8")
    assert aktualizacja.wersja_kodu(tmp_path / "b") is None
    git = tmp_path / "c" / ".git"
    git.mkdir(parents=True)
    (git / "HEAD").write_text(SHA_INNA + "\n", encoding="utf-8")
    assert aktualizacja.wersja_kodu(tmp_path / "c") == SHA_INNA


def test_klucz_ze_zmiennej_albo_z_magazynu(tmp_path):
    u, _ = _instalacja(tmp_path)
    magazyn = lambda _u: "z-magazynu-0123456789"                                   # noqa: E731
    assert aktualizacja.klucz_github(u, {"JARVO_TOKEN": KLUCZ}, magazyn) == KLUCZ
    assert aktualizacja.klucz_github(u, {}, magazyn) == "z-magazynu-0123456789"
    assert aktualizacja.klucz_github(u, {"JARVO_TOKEN": "krótki"}, lambda _u: None) is None
    assert aktualizacja.klucz_github(u, {"JARVO_TOKEN": "ze spacją 0123456789"}, lambda _u: None) is None


@pytest.mark.posix_only
def test_klucz_z_pliku_tylko_dla_wlasciciela(tmp_path, monkeypatch):
    """Linux bez libsecret: `<dane>/jarvo/konfig/github-token`, ale tylko z prawami 0600."""
    if sys.platform == "darwin":
        pytest.skip("macOS czyta pęk kluczy (security), pliku nie")
    u, _ = _instalacja(tmp_path)
    monkeypatch.setattr(aktualizacja.shutil, "which", lambda *a, **k: None)
    plik = u.jarvo_dane / "konfig" / "github-token"
    plik.parent.mkdir(parents=True)
    plik.write_text(KLUCZ + "\n", encoding="utf-8")
    os.chmod(plik, 0o644)
    assert aktualizacja.czytaj_magazyn(u) is None
    os.chmod(plik, 0o600)
    assert aktualizacja.czytaj_magazyn(u) == KLUCZ


# ---------------------------------------------------------------- GitHub: wersja i kod

def test_zdalna_wersja_z_api_z_kluczem_tylko_w_naglowku(github):
    github.refy["main"] = SHA_NOWA
    github.refy["claude/epic"] = SHA_INNA
    assert aktualizacja.zdalna_wersja("main", None, {}) == SHA_NOWA
    assert github.zapytania[-1]["accept"] == "application/vnd.github.sha" and github.zapytania[-1]["auth"] is None
    assert aktualizacja.zdalna_wersja("claude/epic", KLUCZ, {}) == SHA_INNA
    assert github.zapytania[-1]["sciezka"].endswith("/commits/claude/epic")
    assert github.zapytania[-1]["auth"] == f"Bearer {KLUCZ}"
    n = len(github.zapytania)
    assert aktualizacja.zdalna_wersja(SHA_INNA.upper(), None, {}) == SHA_INNA      # pełny SHA: bez pytania API
    assert len(github.zapytania) == n


def test_zdalna_wersja_bledy_po_polsku_bez_klucza(github):
    github.prywatne.add("prywatna")
    github.refy["prywatna"] = SHA_NOWA
    with pytest.raises(aktualizacja.BladAktualizacji, match="JARVO_TOKEN") as e:
        aktualizacja.zdalna_wersja("nie-ma", None, {})
    assert "404" in str(e.value)
    with pytest.raises(aktualizacja.BladAktualizacji, match="limit zapytań"):
        aktualizacja.zdalna_wersja("limit", KLUCZ, {})
    with pytest.raises(aktualizacja.BladAktualizacji, match="JARVO_TOKEN"):
        aktualizacja.zdalna_wersja("prywatna", None, {})
    assert aktualizacja.zdalna_wersja("prywatna", KLUCZ, {}) == SHA_NOWA


def test_nowe_zmiany_z_listy_commitow(github):
    github.lista = [{"sha": SHA_NOWA, "commit": {"message": "Nowa funkcja\n\nopis"}},
                    {"sha": SHA_INNA, "commit": {"message": "Poprawka"}},
                    {"sha": SHA_STARA, "commit": {"message": "Stara wersja"}}]
    ile, zmiany, pelna = aktualizacja.nowe_zmiany(SHA_STARA, SHA_NOWA, None, {})
    assert (ile, pelna) == (2, True)
    assert zmiany == [{"sha": SHA_NOWA[:7], "subject": "Nowa funkcja"}, {"sha": SHA_INNA[:7], "subject": "Poprawka"}]
    assert f"sha={SHA_NOWA}" in github.zapytania[-1]["zapytanie"]
    ile, zmiany, pelna = aktualizacja.nowe_zmiany(_sha1("spoza listy"), SHA_NOWA, None, {})
    assert ile == 3 and pelna is False                                            # „3+” w opisie
    assert aktualizacja.nowe_zmiany(None, SHA_NOWA, None, {}) == (1, [], False)


def test_pobierz_kod_publiczny_z_codeload(tmp_path, github):
    u, _ = _instalacja(tmp_path)
    github.archiwa[SHA_NOWA] = _archiwum(SHA_NOWA)
    log: list[str] = []
    cel = aktualizacja.pobierz_kod(u, SHA_NOWA, "main", None, {}, log.append)
    assert cel == u.program / "app" / SHA_NOWA[:12]
    assert (cel / "jarvo" / "start.py").read_bytes() == b"# start\n"
    assert aktualizacja.wersja_kodu(cel) == SHA_NOWA and aktualizacja.ref_kodu(cel) == "main"
    assert github.zapytania[-1]["sciezka"] == f"/codeload/{REPO_GH}/tar.gz/{SHA_NOWA}"
    assert not list((u.cache / "pobrane").glob("jarvo-*")) and not cel.with_name(cel.name + ".new").exists()
    n = len(github.zapytania)
    assert aktualizacja.pobierz_kod(u, SHA_NOWA, "main", None, {}, log.append) == cel   # gotowy: bez pobierania
    assert len(github.zapytania) == n and "już jest" in log[-1]


def test_pobierz_kod_prywatny_przez_api_bez_klucza_po_przekierowaniu(tmp_path, github):
    u, _ = _instalacja(tmp_path)
    github.archiwa[SHA_NOWA] = _archiwum(SHA_NOWA)
    log: list[str] = []
    cel = aktualizacja.pobierz_kod(u, SHA_NOWA, "main", KLUCZ, {}, log.append)
    assert (cel / "jarvo" / "start.py").is_file()
    api, codeload = github.zapytania[-2], github.zapytania[-1]
    assert api["sciezka"].endswith(f"/tarball/{SHA_NOWA}") and api["auth"] == f"Bearer {KLUCZ}"
    assert codeload["sciezka"].startswith("/codeload/") and codeload["auth"] is None   # add_unredirected_header
    assert KLUCZ not in "\n".join(log)


def test_pobierz_kod_bez_start_py_to_blad_bez_resztek(tmp_path, github):
    u, _ = _instalacja(tmp_path)
    github.archiwa[SHA_NOWA] = _archiwum(SHA_NOWA, start=False)
    niepelny = u.program / "app" / SHA_NOWA[:12]
    (niepelny / "resztka").mkdir(parents=True)                                     # przerwana próba
    with pytest.raises(aktualizacja.BladAktualizacji, match="start.py"):
        aktualizacja.pobierz_kod(u, SHA_NOWA, "main", None, {}, lambda t: None)
    assert not niepelny.with_name(niepelny.name + ".new").exists()
    github.archiwa[SHA_NOWA] = _archiwum(SHA_NOWA)
    cel = aktualizacja.pobierz_kod(u, SHA_NOWA, "main", None, {}, lambda t: None)
    assert not (cel / "resztka").exists() and (cel / "jarvo" / "start.py").is_file()


def test_pobierz_kod_po_urwanym_strumieniu_ponawia(tmp_path, github, monkeypatch):
    """codeload zamyka chunked przed końcem: http.client.IncompleteRead to nie OSError, a pobieranie i tak ponawia."""
    monkeypatch.setattr(aktualizacja.time, "sleep", lambda _s: None)
    u, _ = _instalacja(tmp_path)
    github.archiwa[SHA_NOWA] = _archiwum(SHA_NOWA)
    github.urwij[SHA_NOWA] = 1
    log: list[str] = []
    cel = aktualizacja.pobierz_kod(u, SHA_NOWA, "main", None, {}, log.append)
    assert (cel / "jarvo" / "start.py").is_file() and any("IncompleteRead" in x for x in log), log
    github.urwij[SHA_INNA] = 5                                                     # zawsze urwane: błąd po polsku
    with pytest.raises(aktualizacja.BladAktualizacji, match="urwało się w trakcie"):
        aktualizacja.pobierz_kod(u, SHA_INNA, "main", None, {}, log.append)
    assert not list((u.cache / "pobrane").glob("*.czesc"))


def test_pobierz_kod_uszkodzone_archiwum_raz_i_zawsze(tmp_path, github):
    """Uszkodzony gzip (urwany plik) pobieramy jeszcze raz; zawsze uszkodzony = BladAktualizacji, nie tarfile.ReadError."""
    u, _ = _instalacja(tmp_path)
    dobre = _archiwum(SHA_NOWA)
    github.kolejne[SHA_NOWA] = [dobre[: len(dobre) // 2], dobre]
    log: list[str] = []
    cel = aktualizacja.pobierz_kod(u, SHA_NOWA, "main", None, {}, log.append)
    assert (cel / "jarvo" / "start.py").is_file() and any("archiwum uszkodzone" in x for x in log), log
    github.kolejne[SHA_INNA] = [b"to nie gzip", b"\x1f\x8b\x08" + b"\0" * 20]
    with pytest.raises(aktualizacja.BladAktualizacji, match="uszkodzone"):
        aktualizacja.pobierz_kod(u, SHA_INNA, "main", None, {}, log.append)
    assert not (u.program / "app" / f"{SHA_INNA[:12]}.new").exists()
    assert not list((u.cache / "pobrane").glob("jarvo-*"))


def test_kod_z_katalogu_testowego_bez_gita_i_pamieci_podrecznej(tmp_path):
    """JARVO_FAKE_KOD (próby): wersja z `.jarvo-wersja` katalogu, kopia bez .git i __pycache__, bez sieci."""
    u, _ = _instalacja(tmp_path)
    zrodlo = _kod(tmp_path / "zrodlo", SHA_NOWA)
    (zrodlo / ".git").mkdir()
    (zrodlo / ".git" / "config").write_text("x", encoding="utf-8")
    (zrodlo / "jarvo" / "__pycache__").mkdir()
    (zrodlo / "jarvo" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    env = {aktualizacja.FAKE: str(zrodlo)}
    assert aktualizacja.zdalna_wersja("main", None, env) == SHA_NOWA
    cel = aktualizacja.pobierz_kod(u, SHA_NOWA, "main", None, env, lambda t: None)
    assert (cel / "jarvo" / "start.py").is_file() and not (cel / ".git").exists()
    assert not (cel / "jarvo" / "__pycache__").exists()
    assert aktualizacja.nowe_zmiany(SHA_STARA, SHA_NOWA, None, env)[0] == 1
    with pytest.raises(aktualizacja.BladAktualizacji, match=aktualizacja.FAKE):
        aktualizacja.zdalna_wersja("main", None, {aktualizacja.FAKE: str(tmp_path / "nie-ma")})


# ---------------------------------------------------------------- jarvo update

def _aktualizuj(u, ot, z, **kw):
    log: list[str] = []
    kod, raport = aktualizacja.aktualizuj(u, ot, log=log.append, zaplecze=z, magazyn=lambda _u: None, **kw)
    return kod, raport, "\n".join(log)


def test_ta_sama_wersja_nic_nie_zmienia(tmp_path):
    u, _ = _instalacja(tmp_path)
    zrodlo = _kod(tmp_path / "zrodlo", SHA_STARA)
    inst, doc = Instalator(u), Doctor()
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(zrodlo)}, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    przed = {p: p.read_bytes() for p in u.program.rglob("*") if p.is_file()}
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=doc))
    assert kod == 0 and raport["wynik"] == "aktualne", log
    assert "nic do zrobienia" in log and not inst.wywolania and not doc.wywolania
    assert {p: p.read_bytes() for p in u.program.rglob("*") if p.is_file()} == przed
    panel = aktualizacja.stan_panelu(u)
    assert panel["state"] == "idle" and panel["behind"] == 0 and panel["latest"] == SHA_STARA[:7]
    assert panel["mode"] == "natywny" and isinstance(panel["checked_at"], float)


def test_nowa_wersja_obok_starej_instalator_doctor_i_sprzatanie(tmp_path):
    u, stara = _instalacja(tmp_path)
    zrodlo = _kod(tmp_path / "zrodlo", SHA_NOWA)
    inst, doc = Instalator(u), Doctor()
    nadzorca = Nadzorca(dziala=False)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(zrodlo)},
             moduly={"nadzorca": nadzorca, "autostart": Autostart(wlaczony=False)})
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=doc))
    assert kod == 0 and raport["wynik"] == "zaktualizowano", log
    nowa = u.program / "app" / SHA_NOWA[:12]
    assert inst.aplikacje() == [SHA_NOWA[:12]] and len(doc.wywolania) == 2
    argv = inst.wywolania[0]["argv"]
    assert argv[1:5] == ["-I", "-u", "-X", "utf8"] and argv[5] == str(nowa / "jarvo" / "start.py")
    assert argv[6:9] == ["--korzen", str(u.root), "instaluj"]
    assert argv[9:] == ["--bez-path", "--bez-autostartu", "--bez-startu"]      # jak ta instalacja (atrapy)
    assert srodowisko.biezace(u)["app"] == str(nowa)
    assert raport["wersja_przed"] == SHA_STARA[:12] and raport["wersja_po"] == SHA_NOWA[:12]
    assert not stara.exists(), "stara wersja, z której nic nie korzysta, znika"
    assert str(stara) in raport["sprzatanie"]["usuniete"]
    panel = aktualizacja.stan_panelu(u)
    assert panel["state"] == "done" and panel["current"] == SHA_NOWA[:7] and panel["behind"] == 0
    assert isinstance(panel["finished_at"], float) and "Gotowe" in panel["log"]
    assert aktualizacja.stan(u)["wynik"] == "zaktualizowano" and aktualizacja.stan(u)["ref"] == "main"
    assert (u.logi / "aktualizacja.log").read_text(encoding="utf-8").count("[Instalator wersji") == 1
    assert not (u.stan / "aktualizacja.lock").exists() or not aktualizacja.trwa(u)


def test_opcje_instalatora_jak_przy_instalacji(tmp_path):
    """PATH w dzienniku, włączony autostart i działający serwis: instalator nowej wersji bez --bez-* (zmieni PATH,
    autostart i uruchomi serwis od nowa jak przy instalacji)."""
    u, _ = _instalacja(tmp_path)
    if WINDOWS:
        zmiany_hosta.dopisz(u, "path-uzytkownika", wartosc=str(u.root / "bin"))
    else:
        zmiany_hosta.dopisz(u, "plik", sciezka=str(Path.home() / ".local" / "bin" / "jarvo"), sha256="0" * 64)
    inst = Instalator(u)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(dziala=True), "autostart": Autostart(wlaczony=True)})
    kod, _, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor()))
    assert kod == 0, log
    assert inst.wywolania[0]["argv"][8:] == ["instaluj"]


def test_blad_przed_przelaczeniem_zostawia_stara_wersje(tmp_path):
    u, stara = _instalacja(tmp_path)
    inst = Instalator(u, kody=(1,), przelacz=(False,))
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    cur = (u.program / "current.json").read_bytes()
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor()))
    assert kod == 1 and raport["wynik"] == "blad" and len(inst.wywolania) == 1, log
    assert "nic się nie przełączyło" in log and (u.program / "current.json").read_bytes() == cur
    assert stara.is_dir() and aktualizacja.stan_panelu(u)["state"] == "failed"


def test_blad_po_przelaczeniu_wraca_instalatorem_poprzedniej_wersji(tmp_path):
    u, stara = _instalacja(tmp_path)
    inst = Instalator(u, kody=(1, 0), przelacz=(True, True))
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor()))
    assert kod == 1 and raport["wynik"] == "wycofano", log
    assert inst.aplikacje() == [SHA_NOWA[:12], SHA_STARA[:12]]
    assert inst.wywolania[1]["argv"][9:] == inst.wywolania[0]["argv"][9:]            # te same opcje
    assert srodowisko.biezace(u)["app"] == str(stara) and "wróciła poprzednia wersja" in log
    panel = aktualizacja.stan_panelu(u)
    assert panel["state"] == "failed" and "kodem 1" in panel["error"]


def test_regresja_doctora_wycofuje_a_nowe_sprawdzenie_nie(tmp_path):
    u, stara = _instalacja(tmp_path)
    zrodlo = _kod(tmp_path / "zrodlo", SHA_NOWA)
    env = {aktualizacja.FAKE: str(zrodlo)}
    moduly = {"nadzorca": Nadzorca(), "autostart": Autostart()}
    doc = Doctor({SHA_STARA[:12]: [("Hermes", "ok"), ("uv", "blad")],
                  SHA_NOWA[:12]: [("Hermes", "blad"), ("uv", "blad")]})
    inst = Instalator(u)
    kod, raport, log = _aktualizuj(u, _ot(tmp_path, env=env, moduly=moduly), _zaplecze(strumien=inst, przechwyc=doc))
    assert kod == 1 and raport["wynik"] == "wycofano" and raport["regresje"] == ["Hermes"], log
    assert srodowisko.biezace(u)["app"] == str(stara)
    # błąd, który był już przed aktualizacją (uv), i nowe sprawdzenie nowej wersji: bez wycofania, z uwagą
    doc = Doctor({SHA_STARA[:12]: [("Hermes", "ok"), ("uv", "blad")],
                  SHA_NOWA[:12]: [("Hermes", "ok"), ("uv", "blad"), ("nowe", "blad")]})
    inst = Instalator(u)
    kod, raport, log = _aktualizuj(u, _ot(tmp_path, env=env, moduly=moduly), _zaplecze(strumien=inst, przechwyc=doc))
    assert kod == 0 and raport["wynik"] == "zaktualizowano" and raport["nowe_bledy"] == ["nowe"], log
    assert "nowe sprawdzenia z błędem: nowe" in log


def test_rozgrzewka_uslug_nowej_wersji_to_nie_regresja(tmp_path):
    """API bramy wstaje chwilę po panelu (próba na Windows 11): błąd w pierwszym doctorze po aktualizacji, który mija
    w czasie rozgrzewki, nie wycofuje aktualizacji."""
    u, _ = _instalacja(tmp_path)

    class Rozgrzewka(Doctor):
        def __call__(self, argv, *, env, cwd, czas=600):
            app = Path(str(argv[5])).parent.parent.name
            po = [w for w in self.wywolania if Path(w["argv"][5]).parent.parent.name == app]
            self.mapa[SHA_NOWA[:12]] = [("API bramy", "blad" if len(po) < 2 else "ok")]
            return super().__call__(argv, env=env, cwd=cwd, czas=czas)
    doc = Rozgrzewka({SHA_STARA[:12]: [("API bramy", "ok")]})
    inst = Instalator(u)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=doc))
    assert kod == 0 and raport["wynik"] == "zaktualizowano" and len(inst.wywolania) == 1, log
    assert "czekam, aż usługi nowej wersji wstaną (API bramy)" in log and len(doc.wywolania) == 4


def test_doctor_nowej_wersji_bez_wyniku_wycofuje(tmp_path):
    u, stara = _instalacja(tmp_path)
    inst = Instalator(u)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor({SHA_NOWA[:12]: None})))
    assert kod == 1 and raport["wynik"] == "wycofano" and srodowisko.biezace(u)["app"] == str(stara), log


def test_nieudany_powrot_przywraca_current_json_sprzed_aktualizacji(tmp_path):
    u, _ = _instalacja(tmp_path)
    przed = (u.program / "current.json").read_bytes()
    inst = Instalator(u, kody=(1, 1), przelacz=(True, False))
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor()))
    assert kod == 1 and raport["wynik"] == "blad" and len(inst.wywolania) == 2, log
    assert (u.program / "current.json").read_bytes() == przed and "sprzed aktualizacji" in log


def test_jedna_aktualizacja_naraz(tmp_path):
    u, _ = _instalacja(tmp_path)
    inst = Instalator(u)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    with przenosne.Zamek(u.stan / aktualizacja.ZAMEK, czekaj=False):
        assert aktualizacja.trwa(u)
        kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor()))
    assert kod == 1 and raport["wynik"] == "trwa" and not inst.wywolania and "już trwa" in log
    assert not aktualizacja.trwa(u)


def test_sprawdz_tylko_sprawdza(tmp_path):
    u, _ = _instalacja(tmp_path)
    inst = Instalator(u)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor()), tylko_sprawdz=True)
    assert kod == 0 and raport["wynik"] == "dostepna" and not inst.wywolania, log
    assert not (u.program / "app" / SHA_NOWA[:12]).exists()
    assert aktualizacja.stan_panelu(u)["behind"] == 1


def test_klucz_nigdy_w_wyjsciu_logu_stanie_ani_otoczeniu(tmp_path, github):
    """Prywatna kopia przez API z kluczem z JARVO_TOKEN: klucz idzie tylko w nagłówku do API."""
    u, _ = _instalacja(tmp_path)
    github.refy["main"] = SHA_NOWA
    github.lista = [{"sha": SHA_NOWA, "commit": {"message": "Nowa"}}, {"sha": SHA_STARA, "commit": {"message": "x"}}]
    github.archiwa[SHA_NOWA] = _archiwum(SHA_NOWA)
    inst, doc = Instalator(u), Doctor()
    ot = _ot(tmp_path, env={"JARVO_TOKEN": KLUCZ}, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=doc))
    assert kod == 0 and raport["wynik"] == "zaktualizowano", log
    assert raport["behind"] == 1 and raport["zmiany"] == [{"sha": SHA_NOWA[:7], "subject": "Nowa"}]
    assert any(z["auth"] == f"Bearer {KLUCZ}" for z in github.zapytania)
    assert all(z["auth"] is None for z in github.zapytania if z["sciezka"].startswith("/codeload/"))
    pliki = [u.logi / "aktualizacja.log", aktualizacja.plik_panelu(u), u.stan / aktualizacja.STAN]
    assert KLUCZ not in log + json.dumps(raport) + "".join(p.read_text(encoding="utf-8") for p in pliki)
    for w in inst.wywolania + doc.wywolania:
        assert "JARVO_TOKEN" not in {k.upper() for k in w["env"]}


def test_sprzatanie_starych_wersji_poza_uzywanymi(tmp_path):
    u, app = _instalacja(tmp_path)
    p = u.program
    for k in ("app/111111111111", "app/222222222222.new", "hermes/stary0000000", "hermes/uzywany00000",
              "venvs/narzedzia-aaaaaaaaaaaa", "venvs/narzedzia-bbbbbbbbbbbb", "narzedzia/uv/0.12.13",
              "narzedzia/uv/0.11.0", "narzedzia/uv/0.12.13.stary-1700000000", "web-dist/stary0000000000",
              "web-dist/biezacy000000000"):
        (p / k / "plik").parent.mkdir(parents=True, exist_ok=True)
        (p / k / "plik").write_bytes(b"x" * 100_000)
    for opis in ("stary0000000000", "biezacy000000000"):                  # opisy frontu obok (hermes.dist_jarva)
        (p / "web-dist" / f"{opis}.json").write_text("{}", encoding="utf-8")
    narz = srodowisko.narzedzia(u)
    narz.update({"uv": {"wersja": "0.12.13", "katalog": str(p / "narzedzia" / "uv" / "0.12.13")},
                 "venv-narzedzia": {"wersja": "aaaaaaaaaaaa", "katalog": str(p / "venvs" / "narzedzia-aaaaaaaaaaaa"),
                                    "python": "x"}})
    (u.stan / "narzedzia.json").write_text(json.dumps(narz), encoding="utf-8")
    (u.program / "current.json").write_text(json.dumps({**srodowisko.biezace(u),
                                                        "hermes": str(p / "hermes" / "uzywany00000"),
                                                        "web_dist": str(p / "web-dist" / "biezacy000000000")}),
                                            encoding="utf-8")
    uzywa = Proces(55, 1, str(p / "hermes" / "stary0000000" / ".venv" / "Scripts" / "python.exe"), "python -m x")
    pobrane = u.cache / "pobrane"
    pobrane.mkdir(parents=True)
    znana = "ab" * 32
    (pobrane / f"{znana[:16]}-uv.zip").write_bytes(b"z")
    (pobrane / f"{'cd' * 8}-stary.zip").write_bytes(b"z")
    (pobrane / f"jarvo-{SHA_STARA}.tar.gz").write_bytes(b"z")
    _kod(app, SHA_STARA, sumy=(znana,))
    log: list[str] = []
    wynik = aktualizacja.sprzataj(u, _zaplecze(procesy=lambda: [uzywa]), log.append, app=app)
    zostaja = sorted(str(k.relative_to(p)).replace("\\", "/") for k in p.glob("*/*") if k.is_dir())
    zostaja += sorted(str(k.relative_to(p)).replace("\\", "/") for k in (p / "narzedzia").glob("*/*"))
    assert "hermes/stary0000000" in zostaja, "używany przez proces zostaje"
    for znika in ("app/111111111111", "app/222222222222.new", "hermes/f97608f178d1", "venvs/narzedzia-bbbbbbbbbbbb",
                  "narzedzia/uv/0.11.0", "narzedzia/uv/0.12.13.stary-1700000000", "web-dist/stary0000000000"):
        assert znika not in zostaja, znika
    for zostaje in (f"app/{SHA_STARA[:12]}", "hermes/uzywany00000", "venvs/narzedzia-aaaaaaaaaaaa",
                    "narzedzia/uv/0.12.13", "narzedzia/python313/3.13.17", "web-dist/biezacy000000000"):
        assert zostaje in zostaja, zostaje                                  # web_dist z current.json zostaje
    assert sorted(x.name for x in (p / "web-dist").glob("*.json")) == ["biezacy000000000.json"]
    assert wynik["w_uzyciu"][0]["procesy"] == ["python.exe (PID 55)"]
    assert sorted(x.name for x in pobrane.iterdir()) == [f"{znana[:16]}-uv.zip"]
    assert wynik["zwolnione_mb"] > 0 and not list(p.rglob("*.usun-*"))


def test_regresje_doctora():
    def d(*w):
        return {"wyniki": [{"nazwa": n, "stan": s} for n, s in w]}
    assert aktualizacja.regresje(d(("a", "ok"), ("b", "blad")), d(("a", "blad"), ("b", "blad"), ("c", "blad"))) == \
        (["a"], ["c"])
    assert aktualizacja.regresje(d(("a", "uwaga")), d(("a", "ok"))) == ([], [])


def test_opis_liczby_zmian_po_polsku():
    assert [aktualizacja.opis_liczby_zmian(n) for n in (1, 2, 4, 5, 12, 22, 25, 112)] == [
        "1 nowa zmiana", "2 nowe zmiany", "4 nowe zmiany", "5 nowych zmian", "12 nowych zmian", "22 nowe zmiany",
        "25 nowych zmian", "112 nowych zmian"]
    assert aktualizacja.opis_liczby_zmian(50, pelna=False) == "co najmniej 50 nowych zmian"


def test_nieprzewidziany_blad_po_przelaczeniu_wraca_i_konczy_failed(tmp_path, monkeypatch):
    """Wyjątek spoza obsłużonych (np. ValueError z doctora nowej wersji) po przełączeniu: powrót instalatorem
    poprzedniej wersji, update.json „failed” (nie „updating”), komunikat po polsku i ślad tylko w aktualizacja.log."""
    u, stara = _instalacja(tmp_path)
    inst = Instalator(u)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    monkeypatch.setattr(aktualizacja._Aktualizacja, "_doctor_po",
                        lambda self, app, przed: (_ for _ in ()).throw(ValueError("zepsuty JSON doctora")))
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor()))
    assert kod == 1 and raport["wynik"] == "wycofano" and inst.aplikacje() == [SHA_NOWA[:12], SHA_STARA[:12]], log
    assert srodowisko.biezace(u)["app"] == str(stara) and "nieprzewidziany błąd (ValueError" in log
    assert "Traceback" not in log and "Traceback" in (u.logi / "aktualizacja.log").read_text(encoding="utf-8")
    panel = aktualizacja.stan_panelu(u)
    assert panel["state"] == "failed" and "ValueError" in panel["error"]


def test_nieprzewidziany_blad_przed_krokami_bez_sladu_stosu(tmp_path, monkeypatch):
    u, _ = _instalacja(tmp_path)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    monkeypatch.setattr(aktualizacja, "nowe_zmiany", lambda *a: (_ for _ in ()).throw(KeyError("commit")))
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=Instalator(u), przechwyc=Doctor()))
    assert kod == 1 and raport["wynik"] == "blad" and "nieprzewidziany błąd aktualizacji (KeyError" in log
    assert aktualizacja.stan_panelu(u)["state"] == "idle" and "KeyError" in aktualizacja.stan_panelu(u)["error"]


def test_blad_sprzatania_nie_wycofuje_udanej_aktualizacji(tmp_path, monkeypatch):
    u, _ = _instalacja(tmp_path)
    inst = Instalator(u)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))},
             moduly={"nadzorca": Nadzorca(), "autostart": Autostart()})
    monkeypatch.setattr(aktualizacja, "sprzataj", lambda *a, **k: (_ for _ in ()).throw(PermissionError(5, "x")))
    kod, raport, log = _aktualizuj(u, ot, _zaplecze(strumien=inst, przechwyc=Doctor()))
    assert kod == 0 and raport["wynik"] == "zaktualizowano" and len(inst.wywolania) == 1, log
    assert "sprzątanie starych wersji nie przeszło" in log and aktualizacja.stan_panelu(u)["state"] == "done"


@pytest.mark.windows_only
def test_sprzatanie_wstrzymane_przez_niewidoczny_proces_jarva(tmp_path):
    """Windows: proces w tej samej sesji bez ścieżki i wiersza polecenia (np. podniesiony `jarvo chat` starej
    wersji), o nazwie programu z wersji Jarva, wstrzymuje sprzątanie; obcy z innej sesji (usługa systemu) nie."""
    u, app = _instalacja(tmp_path)
    stary = u.program / "app" / "111111111111"
    (stary / "jarvo").mkdir(parents=True)
    niewidoczny = Proces(77, 1, "python.exe")
    log: list[str] = []
    wynik = aktualizacja.sprzataj(u, _zaplecze(procesy=lambda: [niewidoczny]), log.append, app=app)
    assert stary.is_dir() and wynik["wstrzymane"] == ["python.exe (PID 77)"] and not wynik["usuniete"]
    assert "usunie je następna aktualizacja" in log[0]
    usluga = _zaplecze(procesy=lambda: [niewidoczny], sesja=lambda pid: 0 if pid == 77 else 1)
    wynik = aktualizacja.sprzataj(u, usluga, log.append, app=app)
    assert not stary.exists() and not wynik["wstrzymane"]
    obcy = Proces(78, 1, "notepad.exe")
    assert aktualizacja.niewidoczne(u, [obcy, niewidoczny], _zaplecze()) == [niewidoczny]


# ---------------------------------------------------------------- pomocnik dla panelu (S09)

def _prosba(u, tresc: str) -> Path:
    p = u.jarvo_dane / aktualizacja.PROSBA_PANELU
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tresc, encoding="utf-8")
    return p


def test_pomocnik_check_pisze_stan_dla_panelu(tmp_path):
    u, _ = _instalacja(tmp_path)
    prosba = _prosba(u, "check")
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_NOWA))})
    assert aktualizacja.pomocnik(u, ot, raz=True, log=lambda t: None, magazyn=lambda _u: None) == 0
    assert not prosba.exists()
    panel = json.loads(aktualizacja.plik_panelu(u).read_text(encoding="utf-8"))
    assert panel["behind"] == 1 and panel["current"] == SHA_STARA[:7] and panel["latest"] == SHA_NOWA[:7]
    assert panel["branch"] == "main" and panel["state"] == "idle" and panel["error"] is None
    assert time.time() - panel["checked_at"] < 60                                # panel: pomocnik „online”


def test_pomocnik_update_uruchamia_jarvo_update_w_tle(tmp_path):
    u, _ = _instalacja(tmp_path)
    prosba = _prosba(u, "update\n")
    w_tle = []
    ot = _ot(tmp_path, env={"JARVO_TOKEN": KLUCZ, "OPENAI_API_KEY": "sk-tajny"},
             uruchom_w_tle=lambda argv, env, log: w_tle.append((argv, env, log)) or 777)
    assert aktualizacja.pomocnik(u, ot, raz=True, log=lambda t: None, magazyn=lambda _u: None) == 0
    assert not prosba.exists() and len(w_tle) == 1
    argv, env, log = w_tle[0]
    assert argv[-1] == "update" and "--korzen" in argv and str(u.root) in argv
    assert not {"JARVO_TOKEN", "OPENAI_API_KEY"} & {k.upper() for k in env}
    assert log == u.logi / aktualizacja.LOG_PANELU
    panel = aktualizacja.stan_panelu(u)
    assert panel["state"] == "updating" and isinstance(panel["started_at"], float)


def test_pomocnik_ignoruje_zla_prosbe_i_trwajaca_aktualizacje(tmp_path):
    u, _ = _instalacja(tmp_path)
    w_tle = []
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(_kod(tmp_path / "zrodlo", SHA_STARA))},
             uruchom_w_tle=lambda argv, env, log: w_tle.append(argv) or 1)
    zla = _prosba(u, "rm -rf /")
    aktualizacja.pomocnik(u, ot, raz=True, log=lambda t: None, magazyn=lambda _u: None)
    assert not zla.exists() and not w_tle
    _prosba(u, "update")
    with przenosne.Zamek(u.stan / aktualizacja.ZAMEK, czekaj=False):
        aktualizacja.pomocnik(u, ot, raz=True, log=lambda t: None, magazyn=lambda _u: None)
    assert not w_tle, "aktualizacja już trwa: drugiej nie uruchamiamy"


def test_argv_aktualizacji_w_usludze_systemd_przez_scope(tmp_path, monkeypatch):
    """W jednostce systemd --user Jarva `jarvo update` z panelu idzie przez systemd-run --scope (KillMode=mixed nie
    zabije go z nadzorcą); poza nią (np. runner CI bez user busa) zwykły proces w tle."""
    u, _ = _instalacja(tmp_path)
    assert aktualizacja.w_jednostce_jarva("0::/user.slice/user-1000.slice/user@1000.service/app.slice/jarvo.service\n")
    assert aktualizacja.w_jednostce_jarva("0::/user.slice/user-1000.slice/user@1000.service/jarvo-1a2b3c4d.service")
    assert not aktualizacja.w_jednostce_jarva("0::/system.slice/actions.runner.service\n")
    assert not aktualizacja.w_jednostce_jarva("0::/user.slice/user-1000.slice/user@1000.service/app.slice/inne.service")
    monkeypatch.setattr(aktualizacja, "LINUX", True)
    monkeypatch.setattr(aktualizacja.shutil, "which", lambda nazwa, path=None: "/usr/bin/systemd-run")
    monkeypatch.setattr(aktualizacja, "w_jednostce_jarva", lambda cgroup=None: True)
    argv = aktualizacja.argv_aktualizacji(u, {"JARVO_ROOT": str(u.root)})
    assert argv[:5] == ["/usr/bin/systemd-run", "--user", "--scope", "--quiet", "--collect"] and argv[-1] == "update"
    monkeypatch.setattr(aktualizacja, "w_jednostce_jarva", lambda cgroup=None: False)
    assert aktualizacja.argv_aktualizacji(u, {"JARVO_ROOT": str(u.root)})[0] != "/usr/bin/systemd-run"


def test_pomocnik_blad_obiegu_nie_konczy_petli(tmp_path, monkeypatch):
    """Wyjątek spoza BladAktualizacji w sprawdzeniu (np. IncompleteRead z API): obieg kończy się wpisem błędu
    w update.json i pulsem, a pętla (usługa nadzorcy) działa dalej i nie pyta GitHuba co 3 s."""
    import http.client
    u, _ = _instalacja(tmp_path)
    _prosba(u, "check")
    wywolania = []

    def zle(*_a, **_k):
        wywolania.append(1)
        raise http.client.IncompleteRead(b"ab", 10)
    monkeypatch.setattr(aktualizacja, "sprawdz_dla_panelu", zle)
    ot = _ot(tmp_path)
    obiegi = [0]

    def czekaj(_s):
        obiegi[0] += 1
        if obiegi[0] >= 3:
            raise KeyboardInterrupt
    ot.czekaj = czekaj
    with pytest.raises(KeyboardInterrupt):
        aktualizacja.pomocnik(u, ot, log=lambda t: None, magazyn=lambda _u: None)
    assert obiegi[0] == 3 and len(wywolania) == 1                                 # jedno sprawdzenie, trzy obiegi
    panel = aktualizacja.stan_panelu(u)
    assert "IncompleteRead" in panel["error"] and time.time() - panel["beat"] < 60


def test_pomocnik_przerwana_aktualizacja_na_failed(tmp_path):
    """„updating” bez żadnego `jarvo update` z blokadą (proces zabity albo nie wystartował): po CZAS_STARTU s
    „failed” z opisem; świeży start i trwająca aktualizacja (blokada) zostają."""
    u, _ = _instalacja(tmp_path)
    teraz = time.time()
    aktualizacja.zapisz_panel(u, state="updating", started_at=teraz - 10)
    assert not aktualizacja.przerwana_aktualizacja(u, teraz)                     # dopiero co zlecona
    aktualizacja.zapisz_panel(u, state="updating", started_at=teraz - aktualizacja.CZAS_STARTU - 1)
    with przenosne.Zamek(u.stan / aktualizacja.ZAMEK, czekaj=False):
        assert not aktualizacja.przerwana_aktualizacja(u, teraz)                 # trwa naprawdę
    assert aktualizacja.przerwana_aktualizacja(u, teraz)
    panel = aktualizacja.stan_panelu(u)
    assert panel["state"] == "failed" and "przerwana" in panel["error"] and panel["finished_at"] == teraz
    assert not aktualizacja.przerwana_aktualizacja(u, teraz)                     # „failed” zostaje


def test_pomocnik_pierwsze_sprawdzenie_bez_zbednego_pytania(tmp_path):
    """Restart serwisu: udane sprawdzenie tej samej wersji sprzed 10 min = następne za 50 min; inna wersja (ponowna
    instalacja), błąd albo stare sprawdzenie = od razu."""
    u, _ = _instalacja(tmp_path)
    teraz = time.time()
    assert aktualizacja.pierwsze_sprawdzenie(u, 3600, teraz) == 0.0              # brak update.json
    aktualizacja.zapisz_panel(u, checked_at=teraz - 600, current=SHA_STARA[:7], error=None)
    assert aktualizacja.pierwsze_sprawdzenie(u, 3600, teraz) == pytest.approx(3000)
    aktualizacja.zapisz_panel(u, current=SHA_NOWA[:7])
    assert aktualizacja.pierwsze_sprawdzenie(u, 3600, teraz) == 0.0
    aktualizacja.zapisz_panel(u, current=SHA_STARA[:7], error="brak sieci")
    assert aktualizacja.pierwsze_sprawdzenie(u, 3600, teraz) == 0.0
    aktualizacja.zapisz_panel(u, error=None, checked_at=teraz - 7200)
    assert aktualizacja.pierwsze_sprawdzenie(u, 3600, teraz) == 0.0


def test_pomocnik_konczy_sie_na_sygnale_kodem_0():
    """SIGTERM (POSIX, systemd) i SIGBREAK (Ctrl+Break nadzorcy na Windows) w pętli pomocnika = KeyboardInterrupt,
    który `jarvo update --pomocnik` zamienia na kod 0; po wyjściu poprzednia obsługa wraca."""
    for nazwa in ("SIGTERM", "SIGBREAK"):
        numer = getattr(signal, nazwa, None)
        if numer is None:
            continue
        przed = signal.getsignal(numer)
        with pytest.raises(KeyboardInterrupt):
            with aktualizacja._sygnaly_konca(True):
                signal.raise_signal(numer)
                time.sleep(1)
        assert signal.getsignal(numer) == przed


def test_zlec_aktualizacje_zapisuje_pid_procesu_w_tle(tmp_path):
    u, _ = _instalacja(tmp_path)
    ot = _ot(tmp_path, uruchom_w_tle=lambda argv, env, log: 4242)
    assert aktualizacja.zlec_aktualizacje(u, ot) == 4242
    panel = aktualizacja.stan_panelu(u)
    assert panel["state"] == "updating" and panel["updater_pid"] == 4242


# Atrapa jarvo/start.py zainstalowanej wersji: `doctor --json` i `instaluj` udaje (instalator przełącza current.json na
# swój katalog, jak prawdziwy krok „Przełączenie wersji”), reszta poleceń idzie do prawdziwego jarvo/cli.py z repo:
# pomocnik pod nadzorcą i `jarvo update`, które ten uruchamia w tle
START_WERSJI = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["JARVO_TEST_REPO"])
APP = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
argv = sys.argv[1:]
korzen = argv[1] if argv[:1] == ["--korzen"] else None
reszta = argv[2:] if korzen else argv
if reszta[:1] == ["doctor"]:
    print(json.dumps({"wyniki": [{"nazwa": "korzeń", "stan": "ok", "opis": "", "rada": ""}], "bledy": 0, "uwagi": 0}))
    sys.exit(0)
if reszta[:1] == ["instaluj"]:
    from jarvo import sciezki
    u = sciezki.uklad({**os.environ, **({"JARVO_ROOT": korzen} if korzen else {})})
    cur = u.program / "current.json"
    biez = json.loads(cur.read_text(encoding="utf-8"))
    if biez.get("app") != str(APP):
        (u.program / "current.poprzedni.json").write_text(json.dumps(biez), encoding="utf-8")
        cur.write_text(json.dumps({**biez, "app": str(APP), "wersja": APP.name}), encoding="utf-8")
    print("Gotowe. Zmiany w tym przebiegu: atrapa instalatora.", flush=True)
    sys.exit(0)
from jarvo.cli import main
sys.exit(main(argv))
'''


def _czekaj(warunek, limit: float, opis: str, logi: Path | None = None):
    koniec = time.monotonic() + limit
    while time.monotonic() < koniec:
        wynik = warunek()
        if wynik:
            return wynik
        time.sleep(0.2)
    tekst = ""
    if logi is not None and logi.is_dir():
        tekst = "\n".join(f"== {p.name}\n{p.read_text(encoding='utf-8', errors='replace')[-3000:]}"
                          for p in sorted(logi.glob("*.log")))
    raise AssertionError(f"{opis}: nie doczekałem się w {limit} s\n{tekst}")


def test_przycisk_panelu_do_konca_przez_pomocnika_pod_nadzorca(tmp_path, monkeypatch):
    """Bloker S09 na żywo w jednym procesie testu: prawdziwy nadzorca uruchamia usługę `aktualizacje` (prawdziwe
    `jarvo update --pomocnik` z repo), prawdziwy plugin_api panelu (TestClient) widzi pomocnika online i zapisuje
    prośbę „update”, pomocnik uruchamia w tle prawdziwe `jarvo update` (nowa wersja z JARVO_FAKE_KOD, instalator
    i doctor to atrapy z START_WERSJI), update.json kończy się „done”, a stop nadzorcy kończy pomocnika kodem 0."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from conftest import load_script
    from jarvo import nadzorca

    u, stara = _instalacja(tmp_path)
    (stara / "jarvo" / "start.py").write_text(START_WERSJI, encoding="utf-8")
    zrodlo = _kod(tmp_path / "zrodlo", SHA_NOWA)
    (zrodlo / "jarvo" / "start.py").write_text(START_WERSJI, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("JARVO_")}
    env.update({"JARVO_ROOT": str(u.root), "JARVO_PANEL_PORT": "19229", "LOCALAPPDATA": str(tmp_path / "lad"),
                aktualizacja.FAKE: str(zrodlo), "JARVO_TEST_REPO": str(REPO), "JARVO_TOKEN": KLUCZ,
                "JARVO_REF": "z-okna-instalacji", "PYTHONUTF8": "1"})
    usluga = nadzorca.usluga_pomocnika(u, env, stara)
    assert usluga is not None and usluga.nazwa == "aktualizacje" and usluga.argv[-2:] == ["update", "--pomocnik"]
    assert not {"JARVO_TOKEN", "JARVO_REF"} & set(usluga.env) and usluga.kolejnosc == 2
    n = nadzorca.Nadzorca(u, [usluga], env, kanal=False, limit_stopu=20, takt=0.05, co_ile_rotacja=1)
    watek = threading.Thread(target=n.uruchom, daemon=True)
    monkeypatch.setenv("HERMES_HOME", str(u.dane))
    monkeypatch.setenv("JARVO_ROOT", str(u.root))
    monkeypatch.setenv("JARVO_SHARE_KEYS", "0")
    api = load_script("hq/plugin/plugin_api.py", "jarvo_hq_plugin_api_natywny_update")
    monkeypatch.setattr(api, "UPDATE_FILE", aktualizacja.plik_panelu(u))
    monkeypatch.setattr(api, "UPDATE_REQUEST", u.jarvo_dane / aktualizacja.PROSBA_PANELU)
    app = FastAPI()
    app.include_router(api.router, prefix="/api/plugins/jarvo-hq")
    k = TestClient(app, headers={"X-Jarvo-Request": "1"})
    adres = "/api/plugins/jarvo-hq/update"
    watek.start()
    try:
        # pomocnik wstaje pod nadzorcą i od razu sprawdza wersję: panel widzi go online i nową wersję
        st = _czekaj(lambda: (lambda s: s if s.get("online") and s.get("behind") == 1 else None)(k.get(adres).json()),
                     90, "pomocnik online z nową wersją", u.logi)
        assert st["latest"] == SHA_NOWA[:7] and st["current"] == SHA_STARA[:7] and st["mode"] == "natywny"
        r = k.post(adres, json={"action": "update"})
        assert r.status_code == 202, r.text
        koniec = _czekaj(lambda: (lambda s: s if s.get("state") in ("done", "failed") and not aktualizacja.trwa(u)
                                  else None)(k.get(adres).json()), 180, "aktualizacja z przycisku", u.logi)
        assert koniec["state"] == "done", koniec
        assert koniec["current"] == SHA_NOWA[:7] and koniec["behind"] == 0 and not koniec.get("pending")
        assert srodowisko.biezace(u)["app"] == str(u.program / "app" / SHA_NOWA[:12])
        log_panelu = (u.logi / aktualizacja.LOG_PANELU).read_text(encoding="utf-8", errors="replace")
        assert "Gotowe: Jarvo" in log_panelu and KLUCZ not in log_panelu
        assert stara.is_dir(), "stara wersja zostaje, póki pomocnik z niej działa"
    finally:
        n.zatrzymaj()
        watek.join(60)
    assert not watek.is_alive()
    pomocnik = nadzorca.stan_z_pliku(u)["uslugi"]["aktualizacje"]
    assert pomocnik["ostatni_kod"] == 0 and pomocnik["stan"] == "zatrzymana", pomocnik
    assert "pomocnik aktualizacji:" in (u.logi / "aktualizacje.log").read_text(encoding="utf-8", errors="replace")


def test_panel_natywnie_mowi_co_zrobic_gdy_pomocnik_nie_dziala(tmp_path, monkeypatch):
    """503 `pomocnik` natywnie radzi `jarvo serwis --restart aktualizacje`, a stan dla panelu ma `rada` z poleceniem
    (front pokazuje je do skopiowania); w kontenerze rada z kontenera zostaje bez zmian."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from conftest import load_script
    upd = tmp_path / "update.json"
    upd.write_text(json.dumps({"state": "idle", "checked_at": time.time() - 3600}), encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("JARVO_SHARE_KEYS", "0")
    for natywnie, oczekiwana in ((True, "jarvo serwis --restart aktualizacje"), (False, "bash scripts/local-up.sh")):
        if natywnie:
            monkeypatch.setenv("JARVO_ROOT", str(tmp_path / "j"))
        else:
            monkeypatch.delenv("JARVO_ROOT", raising=False)
        api = load_script("hq/plugin/plugin_api.py", f"jarvo_hq_plugin_api_rada_{natywnie}")
        monkeypatch.setattr(api, "UPDATE_FILE", upd)
        monkeypatch.setattr(api, "UPDATE_REQUEST", tmp_path / "update-request")
        app = FastAPI()
        app.include_router(api.router, prefix="/api/plugins/jarvo-hq")
        r = TestClient(app, headers={"X-Jarvo-Request": "1"}).post("/api/plugins/jarvo-hq/update",
                                                                    json={"action": "update"})
        assert r.status_code == 503 and r.json()["blad"]["kod"] == "pomocnik"
        assert oczekiwana in r.json()["blad"]["komunikat"] and r.json()["detail"] == r.json()["blad"]["komunikat"]
        stan = api._update_state()
        assert stan["natywnie"] is natywnie and not stan["online"]
        assert (stan["rada"]["polecenie"] == "jarvo serwis --restart aktualizacje") is natywnie
        assert not (tmp_path / "update-request").exists()


def test_test_na_zywo_aktualizacji_gotowy_dla_ci(tmp_path, monkeypatch, capsys):
    """tests/live/natywnie_update.py: argumenty (podpolecenia, --limit, --bez-panelu, --migawka-przed), budżet czasu,
    trasa panelu z tokenem sesji z index.html i nagłówkiem ochrony zapisu, podsumowanie JSON na stdout z kodem 1, gdy
    punkt nie przeszedł, i kod 2 przy złych argumentach."""
    from conftest import load_script
    zywo = load_script("tests/live/natywnie_update.py", "natywnie_update_test")
    a = zywo.parser().parse_args(["aktualizacja", "--limit", "100", "--bez-panelu"])
    assert a.limit == 100 and a.bez_panelu and a.funkcja is zywo.polecenie_aktualizacja
    a = zywo.parser().parse_args(["wszystko", "--migawka-przed", "m.json"])
    assert a.migawka_przed == "m.json" and a.limit == zywo.LIMIT and a.funkcja is zywo.polecenie_wszystko
    with pytest.raises(SystemExit) as e:
        zywo.parser().parse_args(["odinstalowanie", "--limit", "5"])
    assert e.value.code == 2
    capsys.readouterr()
    assert 30 <= zywo.Budzet(40).czas(1000) <= 40 and not zywo.Budzet(40).koniec() and zywo.Budzet(10).koniec()

    widziane: list[dict] = []

    class Panel(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            pass

        def _wyslij(self, kod: int, tresc: bytes) -> None:
            self.send_response(kod)
            self.send_header("Content-Length", str(len(tresc)))
            self.end_headers()
            self.wfile.write(tresc)

        def do_GET(self):
            self._wyslij(200, b'<script>window.__HERMES_SESSION_TOKEN__="tok-123";</script>')

        def do_POST(self):
            dane = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            widziane.append({"token": self.headers.get("X-Hermes-Session-Token"), "dane": dane,
                             "jarvo": self.headers.get("X-Jarvo-Request"), "typ": self.headers.get("Content-Type")})
            self._wyslij(202, json.dumps({"ok": True, "action": dane["action"]}).encode())
    httpd = None
    for port in PORTY:
        try:
            httpd = _Serwer(("127.0.0.1", port), Panel)
            break
        except OSError:
            continue
    if httpd is None:
        pytest.skip("brak wolnego portu 19220–19229")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        inst = type("I", (), {"port_panelu": lambda self: httpd.server_address[1]})()
        assert zywo.panel(inst, "POST", zywo.API_UPDATE, {"action": "check"}) == (202, {"ok": True, "action": "check"})
        assert widziane == [{"token": "tok-123", "dane": {"action": "check"}, "jarvo": "1", "typ": "application/json"}]
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert zywo.panel(inst, "GET", zywo.API_UPDATE)[0] == 0                      # panel nie odpowiada: 0, bez wyjątku
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path / "brak"))
    assert zywo.main(["aktualizacja", "--korzen", str(tmp_path / "brak"), "--artefakty", str(tmp_path / "art")]) == 1
    wyjscie = capsys.readouterr().out
    podsumowanie = json.loads(wyjscie[wyjscie.index("{\n"):])
    assert podsumowanie["kod"] == 1 and podsumowanie["polecenie"] == "aktualizacja"
    assert podsumowanie["punkty"][0]["id"] == "update-instalacja" and podsumowanie["punkty"][0]["ok"] is False


# ---------------------------------------------------------------- nowy Python przy tym samym pinie: katalogi obok

def test_hermes_nowy_python_przy_tym_samym_pinie_obok(tmp_path, monkeypatch):
    """Nowa wersja Jarva zmienia tylko Pythona: gotowy checkout zostaje (może z niego działać serwis), nowy powstaje
    obok w `<commit12>-<skrót>` z frontem skopiowanym z gotowego; powrót do starego Pythona go odnajduje."""
    import test_natywne_hermes as th
    dziennik = tmp_path / "dziennik.jsonl"
    monkeypatch.setenv("ATRAPA_DZIENNIK", str(dziennik))
    for zmienna in ("ATRAPA_GIT_HEAD", "ATRAPA_GIT_KLON_BLAD", "ATRAPA_UV_BLAD", "ATRAPA_UV_SUMA", "ATRAPA_BUDOWA",
                    "ATRAPA_NPM_BLAD", "NODE_ENV"):
        monkeypatch.delenv(zmienna, raising=False)
    atrapa = th.Atrapy(tmp_path / "bin", dziennik)
    u = th._uklad(tmp_path)
    stary_py, nowy_py = tmp_path / "py-3.13.17" / "python.exe", tmp_path / "py-3.13.18" / "python.exe"
    for p in (stary_py, nowy_py):
        p.parent.mkdir(parents=True)
        p.write_bytes(b"")
    stary = hermes.zainstaluj(u, th.PIN, git=atrapa.git, uv=atrapa.uv, python=stary_py, log=lambda t: None)
    assert stary == u.program / "hermes" / th.COMMIT[:12]
    dist = stary / "hermes_cli" / "web_dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (stary / hermes.ZNACZNIK_WEB).write_text(json.dumps({"commit": th.COMMIT}), encoding="utf-8")
    venv_starego = srodowisko.hermes_python(stary).read_bytes()
    atrapa.wyczysc()
    logi: list[str] = []
    nowy = hermes.zainstaluj(u, th.PIN, git=atrapa.git, uv=atrapa.uv, python=nowy_py, log=logi.append)
    assert nowy.parent == stary.parent and nowy.name == f"{th.COMMIT[:12]}-{hermes.skrot_srodowiska(nowy_py)}"
    assert any("powstaje obok" in x for x in logi) and srodowisko.hermes_python(stary).read_bytes() == venv_starego
    assert json.loads((stary / hermes.ZNACZNIK).read_text(encoding="utf-8"))["python"] == str(stary_py)
    assert all(th._ta_sama(w["cwd"], nowy) for w in atrapa.wpisy("uv"))          # uv tylko w nowym katalogu
    assert (nowy / "hermes_cli" / "web_dist" / "index.html").is_file()            # front bez npm
    assert hermes.katalog_dla(u, th.COMMIT, th.PIN["dodatki"], nowy_py) == nowy
    assert hermes.katalog_dla(u, th.COMMIT, th.PIN["dodatki"], stary_py) == stary  # powrót: gotowy stary
    atrapa.wyczysc()
    assert hermes.zainstaluj(u, th.PIN, git=atrapa.git, uv=atrapa.uv, python=nowy_py, log=lambda t: None) == nowy
    assert atrapa.wpisy() == []                                                   # drugi przebieg: nic


def test_venv_nowy_python_przy_tym_samym_locku_obok(tmp_path, monkeypatch):
    """Ten sam lock na nowym Pythonie: gotowy venv zostaje nietknięty (bez usuwania w miejscu), nowy w katalogu obok,
    a wpis narzedzia.json wskazuje nowy."""
    import test_natywne_instalacja as ti
    log = tmp_path / "uv.log"
    monkeypatch.setenv("ATRAPA_UV_LOG", str(log))
    monkeypatch.delenv("ATRAPA_UV_KOD", raising=False)
    uv = atrapy.program(tmp_path / "uv-bin", "uv", ti.ATRAPA_UV)
    u, app = ti.uklad(tmp_path / "j"), tmp_path / "app"
    wpis = ti._lock(app)
    stary_py, nowy_py = tmp_path / "py-a" / "python.exe", tmp_path / "py-b" / "python.exe"
    for p in (stary_py, nowy_py):
        p.parent.mkdir(parents=True)
        p.write_bytes(b"")
    stary, _ = venvy.zainstaluj(u, app, "narzedzia", wpis, uv=Path(uv), python=stary_py, log=lambda t: None)
    znacznik = (Path(stary["katalog"]) / venvy.ZNACZNIK).read_text(encoding="utf-8")
    nowy, zmiana = venvy.zainstaluj(u, app, "narzedzia", wpis, uv=Path(uv), python=nowy_py, log=lambda t: None)
    assert zmiana and nowy["katalog"] != stary["katalog"] and Path(stary["katalog"]).is_dir()
    assert (Path(stary["katalog"]) / venvy.ZNACZNIK).read_text(encoding="utf-8") == znacznik
    assert Path(nowy["katalog"]).name == f"{Path(stary['katalog']).name}-{hermes.skrot_srodowiska(nowy_py, '')}"
    assert nowy["env"]["JARVO_TOOLS_PYTHON"] == str(venvy.python_venvu(Path(nowy["katalog"])))
    n = len(log.read_text(encoding="utf-8").splitlines())
    assert venvy.zainstaluj(u, app, "narzedzia", wpis, uv=Path(uv), python=nowy_py, log=lambda t: None) == (nowy,
                                                                                                         False)
    assert venvy.zainstaluj(u, app, "narzedzia", wpis, uv=Path(uv), python=stary_py, log=lambda t: None) == (stary,
                                                                                                          False)
    assert len(log.read_text(encoding="utf-8").splitlines()) == n                 # oba gotowe: bez uv


# ---------------------------------------------------------------- polecenie jarvo: update i uninstall

class _Modul:
    def __init__(self, kod: int = 0):
        self.kod, self.args = kod, []

    def polecenie(self, u, a, ot, **_kw):
        self.args.append(a)
        return self.kod


def test_cli_update_i_uninstall_nie_sa_juz_w_budowie(tmp_path, capsys):
    _instalacja(tmp_path)
    akt, odin = _Modul(), _Modul(1)
    ot = _ot(tmp_path, moduly={"aktualizacja": akt, "odinstalowanie": odin})
    assert cli.main(["update", "--sprawdz", "--json", "--ref", "main"], otoczenie=ot) == 0
    a = akt.args[-1]
    assert a.sprawdz and a.json and a.ref == "main" and not a.pomocnik
    assert cli.main(["update", "--pomocnik", "--raz"], otoczenie=ot) == 0 and akt.args[-1].raz
    assert cli.main(["uninstall", "--all", "--yes"], otoczenie=ot) == 1
    assert odin.args[-1].wszystko and odin.args[-1].tak and not odin.args[-1].json
    assert cli.main(["uninstall", "-y"], otoczenie=ot) == 1 and not odin.args[-1].wszystko
    assert cli.main(["update", "--nieznana"], otoczenie=ot) == 2
    assert cli.main(["migruj"], otoczenie=ot) == 1 and "brak modułu migracji" in capsys.readouterr().err  # podpięte
    assert cli.main(["help", "update"], otoczenie=ot) == 0
    out = capsys.readouterr().out
    assert "--sprawdz" in out and "--ref" in out and "--pomocnik" in out
    assert cli.main(["help", "uninstall"], otoczenie=ot) == 0
    assert "--all" in (out := capsys.readouterr().out) and "--yes" in out


def test_cli_update_bez_instalacji_i_bez_modulu(tmp_path, capsys):
    ot = _ot(tmp_path)
    assert cli.main(["update"], otoczenie=ot) == 1 and "nie jest zainstalowane" in capsys.readouterr().err
    _instalacja(tmp_path)
    assert cli.main(["update"], otoczenie=ot) == 1 and "brak modułu aktualizacji" in capsys.readouterr().err
    assert cli.main(["uninstall", "--yes"], otoczenie=ot) == 1
    assert "brak modułu odinstalowania" in capsys.readouterr().err


def test_cli_update_na_prawdziwym_module(tmp_path, capsys):
    """`jarvo update --json` z prawdziwym modułem (ładowanym przez Otoczenie.modul): raport JSON na stdout."""
    _instalacja(tmp_path)
    zrodlo = _kod(tmp_path / "zrodlo", SHA_STARA)
    ot = _ot(tmp_path, env={aktualizacja.FAKE: str(zrodlo)},
             moduly={"aktualizacja": aktualizacja, "nadzorca": Nadzorca(), "autostart": Autostart()})
    assert cli.main(["update", "--json"], otoczenie=ot) == 0
    wynik = capsys.readouterr()
    assert json.loads(wynik.out)["wynik"] == "aktualne" and "nic do zrobienia" in wynik.err


# ---------------------------------------------------------------- jarvo uninstall

@pytest.fixture
def dom(tmp_path, monkeypatch):
    d = tmp_path / "dom"
    d.mkdir()
    monkeypatch.setenv("HOME", str(d))
    monkeypatch.setenv("USERPROFILE", str(d))
    return d


def _do_odinstalowania(tmp_path: Path, dom: Path, rejestr: Rejestr) -> sciezki.Uklad:
    """Instalacja z dziennikiem zmian hosta: plik poza korzeniem (~/.local/bin/jarvo), plik w korzeniu (polecenie
    w <root>/bin), blok w ~/.profile, wpis w PATH użytkownika (atrapa rejestru), dane, logi, cache i build."""
    u, _ = _instalacja(tmp_path)
    polecenie = dom / ".local" / "bin" / "jarvo"
    zmiany_hosta.zapisz_plik(u, polecenie, "#!/bin/sh\n# Jarvo natywnie (jarvo instaluj)\n", 0o755)
    zmiany_hosta.zapisz_plik(u, u.root / "bin" / "jarvo.cmd", "@echo off\r\n", None)
    (dom / ".profile").write_text("export A=1\n", encoding="utf-8")
    zmiany_hosta.dodaj_blok_rc(u, dom / ".profile", instalator.PATH_RC)
    zmiany_hosta.dodaj_do_path(u, u.root / "bin", rejestr=rejestr)
    for k, plik in ((u.dane, "config.yaml"), (u.logi, "nadzorca.log"), (u.cache / "uv", "x"), (u.build, "y")):
        k.mkdir(parents=True, exist_ok=True)
        (k / plik).write_text("x", encoding="utf-8")
    ro = u.program / "hermes" / "f97608f178d1" / ".git" / "objects" / "pack.idx"
    ro.parent.mkdir(parents=True)
    ro.write_bytes(b"pack")
    os.chmod(ro, stat.S_IREAD)                                                    # paczka gita: tylko do odczytu
    return u


def _odinstaluj(u, ot, z, **kw):
    log: list[str] = []
    kod, raport = odinstalowanie.odinstaluj(u, ot, log=log.append, zaplecze=z, **kw)
    return kod, raport, "\n".join(log)


def test_odinstalowanie_bez_danych(tmp_path, dom):
    rejestr = Rejestr()
    u = _do_odinstalowania(tmp_path, dom, rejestr)
    nadzorca, auto = Nadzorca(dziala=True), Autostart(wlaczony=True)
    ot = _ot(tmp_path, moduly={"nadzorca": nadzorca, "autostart": auto}, rejestr=rejestr)
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(), tak=True)
    assert kod == 0 and raport["wynik"] == "odinstalowane", log
    assert nadzorca.stopy == ["jarvo uninstall"] and auto.wylaczenia == 1
    for k in (u.program, u.stan, u.root / "bin", u.logi, u.cache, u.build):
        assert not k.exists(), k
    assert (u.dane / "config.yaml").is_file() and sorted(x.name for x in u.root.iterdir()) == ["dane"]
    assert not (dom / ".local" / "bin" / "jarvo").exists()                         # cofnięty plik poza korzeniem
    assert (dom / ".profile").read_text(encoding="utf-8") == "export A=1\n"         # blok jarvo cofnięty
    assert rejestr.wartosci[("Environment", "Path")][0] == r"C:\Narzedzia"
    wyniki = {(r["rodzaj"], r["wynik"]) for r in raport["cofniete"]}
    assert {("plik", "cofniete"), ("blok-rc", "cofniete"), ("path-uzytkownika", "cofniete")} <= wyniki
    assert all("jarvo.cmd" not in r["opis"] for r in raport["cofniete"]), "plik z korzenia: zapomniany"
    assert [c["rodzaj"] for c in raport["celowo"]] == ["dane"] and not raport["slady"]
    assert "Zostaje celowo" in log and "Śladów Jarva na komputerze nie ma" in log


def test_odinstalowanie_z_danymi_usuwa_caly_korzen(tmp_path, dom):
    rejestr = Rejestr()
    u = _do_odinstalowania(tmp_path, dom, rejestr)
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=rejestr)
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(), wszystko=True, tak=True)
    assert kod == 0 and raport["dane_usuniete"] and not u.root.exists(), log
    assert not raport["celowo"] and not raport["slady"] and raport["sprzatanie"] is None


def test_odinstalowanie_pyta_a_bez_terminala_odmawia(tmp_path, dom):
    rejestr = Rejestr()
    u = _do_odinstalowania(tmp_path, dom, rejestr)
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=rejestr)
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(terminal=lambda: False))
    assert kod == 1 and raport["wynik"] == "odmowa" and "--yes" in log and u.program.is_dir()
    pytania: list[str] = []
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(terminal=lambda: True,
                                                    pytaj=lambda t: pytania.append(t) or "n"))
    assert kod == 0 and raport["wynik"] == "anulowane" and len(pytania) == 1 and u.program.is_dir()
    odpowiedzi = iter(["t", "nie"])
    pytania.clear()
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(terminal=lambda: True,
                                                    pytaj=lambda t: pytania.append(t) or next(odpowiedzi)),
                                   wszystko=True)
    assert kod == 0 and len(pytania) == 2 and "dane" in pytania[1].lower(), log
    assert not u.program.exists() and (u.dane / "config.yaml").is_file() and "Dane zostają" in log


def test_odinstalowanie_procesy_jarva_bez_przodkow_i_obcych(tmp_path, dom):
    u, _ = _instalacja(tmp_path)
    pyw = str(u.program / "narzedzia" / "python313" / "3.13.17" / ("pythonw.exe" if WINDOWS else "python3"))
    lista = [Proces(100, 50, sys.executable, "python jarvo uninstall"),             # ten proces
             Proces(50, 10, r"C:\Windows\System32\cmd.exe", f'cmd /c "{u.root / "bin" / "jarvo.cmd"}" uninstall'),
             Proces(200, 1, pyw, f"{pyw} start.py serwis", start=1000),             # nadzorca Jarva
             Proces(201, 200, r"C:\Windows\System32\cmd.exe", "cmd /c dir", start=2000),   # dziecko Jarva
             Proces(202, 200, "/bin/inny", "stary PID rodzica", start=10),          # PID rodzica użyty ponownie
             Proces(300, 1, "/usr/bin/code", f"code {u.root}"),                     # edytor z katalogiem Jarva
             Proces(400, 1, "/usr/bin/inny", "bez związku")]
    zamkniete: list[int] = []
    z = _zaplecze(procesy=lambda: lista, zakoncz=lambda l: zamkniete.extend(p.pid for p in l) or [])
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=Rejestr())
    kod, raport, log = _odinstaluj(u, ot, z, tak=True, wszystko=True)
    assert sorted(zamkniete) == [200, 201], log
    assert "nie zamykam code (PID 300)" in log
    assert any(s["rodzaj"] == "proces" and "PID 300" in s["opis"] for s in raport["slady"]) and kod == 1


def test_odinstalowanie_zly_korzen_i_brak_instalacji(tmp_path, dom):
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=Rejestr())
    kod, raport, log = _odinstaluj(sciezki.uklad({"JARVO_ROOT": str(dom)}), ot, _zaplecze(), tak=True)
    assert kod == 1 and raport["wynik"] == "odmowa" and "katalog domowy" in log
    (dom / "program").mkdir()
    (dom / "program" / "current.json").write_text("{}", encoding="utf-8")
    kod, raport, log = _odinstaluj(sciezki.uklad({"JARVO_ROOT": str(dom)}), ot, _zaplecze(), tak=True)
    assert kod == 1 and (dom / "program" / "current.json").is_file(), "katalogu domowego nie ruszamy"
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "nie-ma")})
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(), tak=True)
    assert kod == 0 and raport["wynik"] == "brak instalacji" and not u.root.exists(), log


def test_odinstalowanie_obce_pliki_w_korzeniu_zostaja(tmp_path, dom):
    u, _ = _instalacja(tmp_path)
    (u.root / "moje.txt").write_text("nie ruszać", encoding="utf-8")
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=Rejestr())
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(), tak=True, wszystko=True)
    assert kod == 0 and (u.root / "moje.txt").read_text(encoding="utf-8") == "nie ruszać", log
    assert any(c["rodzaj"] == "obce pliki" for c in raport["celowo"])


def test_odinstalowanie_blad_cofania_pyta_a_z_yes_idzie_dalej(tmp_path, dom):
    u, _ = _instalacja(tmp_path)
    zmiany_hosta.dopisz(u, "autostart-windows", tryb="harmonogram", nazwa="Jarvo-test", odcisk="abc")
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=Rejestr())
    zawsze_blad = _zaplecze(wykonaj=lambda argv: (1, "Harmonogram nie odpowiada"), terminal=lambda: True,
                            pytaj=lambda t: "t" if "Odinstalować" in t else "n")
    kod, raport, log = _odinstaluj(u, ot, zawsze_blad)
    assert kod == 1 and raport["wynik"] == "przerwane" and u.program.is_dir(), log
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(wykonaj=lambda argv: (1, "Harmonogram nie odpowiada")),
                                   tak=True, wszystko=True)
    assert kod == 1 and not u.program.exists(), log
    assert any(s["rodzaj"] == "dziennik" for s in raport["slady"])


@pytest.mark.windows_only
def test_odinstalowanie_windows_python_i_jarvo_cmd_dla_procesu_sprzatajacego(tmp_path, dom, monkeypatch):
    """Python tego polecenia w korzeniu i cmd.exe z jarvo.cmd wśród przodków: oba zostają na koniec procesu
    sprzątającego (PowerShell z korzeniem w wierszu polecenia, czeka na ten proces i na cmd.exe)."""
    u, _ = _instalacja(tmp_path)
    python = u.program / "narzedzia" / "python313" / "3.13.17"
    (python / "python.exe").write_bytes(b"MZ")
    (u.root / "bin").mkdir(exist_ok=True)
    (u.root / "bin" / "jarvo.cmd").write_text("@echo off\r\n", encoding="utf-8")
    monkeypatch.setattr(odinstalowanie, "_python_w_korzeniu", lambda _u: python)
    lista = [Proces(100, 50, str(python / "python.exe"), "python jarvo uninstall"),
             Proces(50, 10, r"C:\Windows\System32\cmd.exe", f'cmd /c "{u.root / "bin" / "jarvo.cmd"}" uninstall')]
    odlaczone = []
    z = _zaplecze(procesy=lambda: lista, odlacz=lambda argv, cwd=None: odlaczone.append((argv, cwd)) or 999)
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=Rejestr())
    kod, raport, log = _odinstaluj(u, ot, z, tak=True, wszystko=True)
    assert kod == 0, log
    assert (python / "python.exe").is_file() and (u.root / "bin" / "jarvo.cmd").is_file()
    assert not u.stan.exists() and not (u.program / "app").exists() and not u.dane.exists()
    assert len(odlaczone) == 1 and raport["sprzatanie"]["czeka_na"] == [100, 50]
    argv, cwd = odlaczone[0]
    assert argv[0].lower().endswith("powershell.exe") and "-Command" in argv and cwd.lower().endswith("system32")
    skrypt = argv[-1]
    assert '"' not in skrypt and str(u.root) in skrypt and "Wait-Process -Id $p" in skrypt
    assert "@(100, 50)" in skrypt and str(u.program) in skrypt and str(u.root / "bin") in skrypt
    assert any(c["rodzaj"] == "katalog" and "proces sprzątający" in c["powod"] for c in raport["celowo"])


@pytest.mark.windows_only
def test_proces_sprzatajacy_naprawde_usuwa_reszte(tmp_path):
    """Prawdziwy PowerShell na katalogu testu (bez RunOnce): czeka na zakończony proces, usuwa ścieżki i pusty
    korzeń; korzeń z danymi zostaje."""
    for z_danymi in (False, True):
        korzen = tmp_path / f"korzen-{z_danymi}"
        (korzen / "program" / "narzedzia" / "python313").mkdir(parents=True)
        (korzen / "program" / "narzedzia" / "python313" / "python.exe").write_bytes(b"MZ")
        (korzen / "bin").mkdir()
        (korzen / "bin" / "jarvo.cmd").write_text("@echo off\r\n", encoding="utf-8")
        os.chmod(korzen / "bin" / "jarvo.cmd", stat.S_IREAD)
        if z_danymi:
            (korzen / "dane").mkdir()
        zakonczony = subprocess.Popen([sys.executable, "-c", "pass"])
        zakonczony.wait()
        skrypt = odinstalowanie.skrypt_sprzatania([zakonczony.pid], [korzen / "program", korzen / "bin"], korzen,
                                                  usun_korzen=True, czas=10, runonce=False)
        assert "RunOnce" not in skrypt
        r = subprocess.run(odinstalowanie.argv_sprzatania(skrypt), capture_output=True, timeout=120,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
        if z_danymi:
            assert sorted(x.name for x in korzen.iterdir()) == ["dane"]
        else:
            assert not korzen.exists()


def test_skrypt_sprzatania_z_runonce_bez_cudzyslowow():
    skrypt = odinstalowanie.skrypt_sprzatania([1, 2], [Path("C:/Jarvo O'Brien/program")], Path("C:/Jarvo O'Brien"),
                                              usun_korzen=True)
    assert '"' not in skrypt and "O''Brien" in skrypt and "RunOnce" in skrypt and "[char]34" in skrypt
    assert "GetTempPath" in skrypt and "Move-Item" in skrypt              # zajęte: zmiana nazwy do %TEMP%
    if WINDOWS:                                       # składnia całości (z gałęzią RunOnce), bez uruchamiania
        ps = shutil.which("powershell")
        if ps is None:
            pytest.skip("brak PowerShella")
        sprawdz = ("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseInput("
                   "[Console]::In.ReadToEnd(), [ref]$null, [ref]$e); $e | ForEach-Object { $_.ToString() }; "
                   "exit $e.Count")
        r = subprocess.run([ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", sprawdz], input=skrypt,
                           capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        assert r.returncode == 0, r.stdout + r.stderr


def test_napis_powershella_z_apostrofami_typograficznymi():
    """PowerShell kończy napis także na ‘ ’ ‚ ‛: każdy z nich podwojony, więc korzeń konta O’Brien nie psuje skryptu."""
    assert odinstalowanie._ps_napis("O'Brien") == "'O''Brien'"
    for z in ("\u2018", "\u2019", "\u201a", "\u201b"):
        assert odinstalowanie._ps_napis(f"O{z}Brien") == f"'O{z}{z}Brien'"


@pytest.mark.windows_only
def test_skrypt_sprzatania_z_apostrofem_typograficznym_dziala(tmp_path):
    """Prawdziwy PowerShell: korzeń „Jarvo O’Brien” (U+2019) w skrypcie procesu sprzątającego parsuje się, a ścieżki
    wracają bez zmian (usunięte są właściwe katalogi, korzeń też)."""
    korzen = tmp_path / "Jarvo O\u2019Brien \u2018x\u2019"
    (korzen / "program" / "a").mkdir(parents=True)
    (korzen / "bin").mkdir()
    (korzen / "bin" / "jarvo.cmd").write_text("@echo off\r\n", encoding="utf-8")
    zakonczony = subprocess.Popen([sys.executable, "-c", "pass"])
    zakonczony.wait()
    skrypt = odinstalowanie.skrypt_sprzatania([zakonczony.pid], [korzen / "program", korzen / "bin"], korzen,
                                              usun_korzen=True, czas=10, runonce=False)
    r = subprocess.run(odinstalowanie.argv_sprzatania(skrypt), capture_output=True, timeout=120,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert not korzen.exists(), sorted(p.name for p in tmp_path.iterdir())
    ps = shutil.which("powershell")
    skrypt = odinstalowanie.skrypt_sprzatania([1], [korzen / "program"], korzen, usun_korzen=True)
    sprawdz = ("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseInput("
               "[Console]::In.ReadToEnd(), [ref]$null, [ref]$e); exit $e.Count")
    r = subprocess.run([ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", sprawdz], input=skrypt,
                       capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr                               # z gałęzią RunOnce też


def test_polecenie_runonce_z_warunkiem_nowej_instalacji():
    p = odinstalowanie.polecenie_runonce(Path(r"D:\Jarvo\program"), znacznik=Path(r"D:\Jarvo\program\current.json"),
                                         korzen=Path(r"D:\Jarvo"))
    assert p == (r'cmd.exe /c if not exist "D:\Jarvo\program\current.json" (rmdir /s /q "D:\Jarvo\program" & '
                 r'rmdir "D:\Jarvo" 2>nul)')
    assert odinstalowanie.polecenie_runonce(Path(r"C:\T\jarvo-usun-1")) == r'cmd.exe /c rmdir /s /q "C:\T\jarvo-usun-1"'
    skrypt = odinstalowanie.skrypt_sprzatania([1], [Path(r"D:\Jarvo\program")], Path(r"D:\Jarvo"), usun_korzen=True,
                                              znacznik=Path(r"D:\Jarvo\program\current.json"))
    assert "'D:\\Jarvo\\program' = 'cmd.exe /c if not exist |D:\\Jarvo\\program\\current.json|" in skrypt
    assert '"' not in skrypt and "$warunkowe[$s].Replace('|', $q)" in skrypt


@pytest.mark.windows_only
def test_polecenie_runonce_naprawde_omija_nowa_instalacje(tmp_path):
    """Prawdziwy cmd.exe z poleceniem wpisu RunOnce (bez rejestru): przy `<program>\\current.json` ponownej instalacji
    nic nie znika; bez niego katalog i pusty korzeń znikają (jak przy logowaniu)."""
    korzen = tmp_path / "Jarvo z spacją"
    program = korzen / "program"
    (program / "narzedzia").mkdir(parents=True)
    (program / "current.json").write_text("{}", encoding="utf-8")                # ponowna instalacja przed logowaniem
    polecenie = odinstalowanie.polecenie_runonce(program, znacznik=program / "current.json", korzen=korzen)
    cmd = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "cmd.exe"
    assert subprocess.run(f'"{cmd}" ' + polecenie.removeprefix("cmd.exe "), timeout=60,
                          creationflags=subprocess.CREATE_NO_WINDOW).returncode in (0, 1)
    assert (program / "current.json").is_file() and (program / "narzedzia").is_dir()
    (program / "current.json").unlink()
    subprocess.run(f'"{cmd}" ' + polecenie.removeprefix("cmd.exe "), timeout=60,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    assert not program.exists() and not korzen.exists()


def _z_kluczem(**kw):
    """Zaplecze z atrapą magazynu kluczy: klucz jest, usunięcie się udaje i jest liczone."""
    stan = {"jest": True, "usuniecia": 0}

    def usun():
        stan["usuniecia"] += 1
        stan["jest"] = False
        return True
    return _zaplecze(klucz_jest=lambda: stan["jest"], usun_klucz=usun, **kw), stan


def test_odinstalowanie_all_usuwa_klucz_github_z_magazynu(tmp_path, dom):
    """--all: klucz jarvo-github znika z magazynu systemu (czyta go jarvo update), bez --all zostaje celowo, a przy
    innej instalacji Jarva na koncie (np. stara z WSL) zostaje z powodem i radą; nieudane usunięcie to ślad."""
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=Rejestr())
    u, _ = _instalacja(tmp_path)
    z, stan = _z_kluczem()
    kod, raport, log = _odinstaluj(u, ot, z, tak=True)                          # bez --all
    assert kod == 0 and stan["usuniecia"] == 0, log
    assert any(c["rodzaj"] == "klucz" and "bez --all" in c["powod"] for c in raport["celowo"])
    u, _ = _instalacja(tmp_path)
    z, stan = _z_kluczem()
    kod, raport, log = _odinstaluj(u, ot, z, tak=True, wszystko=True)
    assert kod == 0 and stan["usuniecia"] == 1 and "magazyn systemu: jarvo-github" in raport["usuniete"], log
    assert not any(c["rodzaj"] == "klucz" for c in raport["celowo"] + raport["slady"])
    (tmp_path / "lad" / "Jarvo" / "wsl").mkdir(parents=True)                    # stara instalacja z WSL (Windows)
    (dom / "jarvo-local").mkdir()                                               # albo z Dockerem (macOS, Linux)
    u, _ = _instalacja(tmp_path)
    z, stan = _z_kluczem()
    kod, raport, log = _odinstaluj(u, ot, z, tak=True, wszystko=True)
    klucz = [c for c in raport["celowo"] if c["rodzaj"] == "klucz"]
    assert stan["usuniecia"] == 0 and klucz and "stara instalacja" in klucz[0]["powod"], log
    assert odinstalowanie.rada_klucza() in klucz[0]["powod"] and kod == 0
    shutil.rmtree(tmp_path / "lad" / "Jarvo")
    (dom / "jarvo-local").rmdir()
    u, _ = _instalacja(tmp_path)
    kod, raport, log = _odinstaluj(u, ot, _zaplecze(klucz_jest=lambda: True, usun_klucz=lambda: False), tak=True,
                                   wszystko=True)
    assert kod == 1 and any(s["rodzaj"] == "klucz" for s in raport["slady"]), log


def test_pytania_odinstalowania_na_stderr_przy_json(tmp_path, dom, monkeypatch, capsys):
    """`jarvo uninstall --json` w terminalu bez --yes (np. `> raport.json`): pytania idą na stderr, a stdout to sam
    poprawny JSON."""
    u, _ = _instalacja(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO("n\n"))
    z = _zaplecze(terminal=lambda: True, pytaj=odinstalowanie.pytaj)
    ot = _ot(tmp_path, moduly={"nadzorca": Nadzorca(), "autostart": Autostart()}, rejestr=Rejestr())
    a = type("A", (), {"json": True, "wszystko": False, "tak": False})()
    assert odinstalowanie.polecenie(u, a, ot, zaplecze=z) == 0
    wyjscie = capsys.readouterr()
    assert json.loads(wyjscie.out)["wynik"] == "anulowane" and "Odinstalować Jarvo" in wyjscie.err
    assert "Odinstalować" not in wyjscie.out and u.program.is_dir()


# ---------------------------------------------------------------- procesy i pliki na prawdziwym systemie

def test_procesy_widza_ten_proces_z_programem_i_poleceniem():
    lista = odinstalowanie.procesy()
    ja = next((p for p in lista if p.pid == os.getpid()), None)
    assert ja is not None, "brak tego procesu na liście"
    if not sys.platform == "darwin":
        # Windows: `Scripts\python.exe` venvu to launcher, a ten proces to jego dziecko z bazowym python.exe
        mozliwe = {os.path.normcase(os.path.realpath(p)) for p in (sys.executable, getattr(sys, "_base_executable",
                                                                                            sys.executable))}
        assert os.path.normcase(os.path.realpath(ja.program)) in mozliwe
    assert "pytest" in ja.polecenie or "py" in ja.polecenie
    if os.getppid() in {p.pid for p in lista}:
        assert os.getppid() in odinstalowanie.przodkowie(os.getpid(), lista)
    assert odinstalowanie.zyje(os.getpid())
    zakonczony = subprocess.Popen([sys.executable, "-c", "pass"])
    zakonczony.wait()
    assert not odinstalowanie.zyje(zakonczony.pid)


def test_zakoncz_konczy_proces():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        p = next(x for x in odinstalowanie.procesy() if x.pid == proc.pid)
        assert odinstalowanie.zakoncz([p], czas=5) == []
        assert proc.wait(timeout=10) is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_dopasowanie_sciezek_z_granica_katalogu(tmp_path):
    k = tmp_path / "Jarvo"
    assert odinstalowanie.zawiera_sciezke(f'"{k / "bin" / "jarvo.cmd"}" uninstall', k)
    assert odinstalowanie.zawiera_sciezke(f"python {k}", k)
    assert not odinstalowanie.zawiera_sciezke(f"python {tmp_path / 'JarvoTest' / 'x.py'}", k)
    assert odinstalowanie.w_katalogu(str(k / "program" / "python.exe"), k)
    assert not odinstalowanie.w_katalogu(str(tmp_path / "JarvoTest" / "python.exe"), k)
    if WINDOWS:
        assert odinstalowanie.zawiera_sciezke(str(k).upper().replace("\\", "/") + "/x", k)
        assert odinstalowanie.w_katalogu(str(k / "a.exe").lower(), k)


@pytest.mark.windows_only
def test_dopasowanie_krotkiej_nazwy_8_3(tmp_path):
    """Korzeń z polskimi znakami: `<program>` i Python mają krótką nazwę 8.3 (c1), a korzeń w układzie długą."""
    dlugi = tmp_path / "Michał Żółć"
    (dlugi / "program").mkdir(parents=True)
    krotki = sciezki.krotka_sciezka(dlugi)
    if krotki == dlugi or not str(krotki).isascii():
        pytest.skip("ten wolumen nie ma krótkich nazw 8.3")
    assert odinstalowanie.w_katalogu(str(krotki / "program" / "python.exe"), dlugi)
    assert odinstalowanie.zawiera_sciezke(f'"{krotki / "program" / "python.exe"}" -I start.py', dlugi)


def test_usun_drzewo_tylko_do_odczytu_i_pomin(tmp_path):
    k = tmp_path / "drzewo"
    (k / "a" / "b").mkdir(parents=True)
    (k / "a" / "b" / "ro.txt").write_text("x", encoding="utf-8")
    os.chmod(k / "a" / "b" / "ro.txt", stat.S_IREAD)
    (k / "zostaje" / "c").mkdir(parents=True)
    (k / "zostaje" / "c" / "plik").write_text("x", encoding="utf-8")
    bledy: list[str] = []
    assert odinstalowanie.usun_drzewo(k, bledy, pomin=[k / "zostaje"]) is False and not bledy
    assert not (k / "a").exists() and (k / "zostaje" / "c" / "plik").is_file()
    assert odinstalowanie.usun_drzewo(k, bledy) is True and not k.exists() and not bledy
    assert odinstalowanie.usun_drzewo(tmp_path / "nie-ma") is True


@pytest.mark.windows_only
def test_usun_drzewo_nie_wchodzi_w_junction_i_zglasza_zablokowany(tmp_path):
    import _winapi
    cel = tmp_path / "cel"
    cel.mkdir()
    (cel / "cudzy.txt").write_text("zostaje", encoding="utf-8")
    k = tmp_path / "drzewo"
    k.mkdir()
    _winapi.CreateJunction(str(cel), str(k / "lacze"))
    (k / "otwarty.txt").write_text("x", encoding="utf-8")
    with open(k / "otwarty.txt", "rb"):                       # Python otwiera bez FILE_SHARE_DELETE
        bledy: list[str] = []
        assert odinstalowanie.usun_drzewo(k, bledy) is False
        assert len(bledy) == 1 and "otwarty.txt" in bledy[0]
    assert (cel / "cudzy.txt").read_text(encoding="utf-8") == "zostaje" and not (k / "lacze").exists()
    assert odinstalowanie.usun_drzewo(k) is True


@pytest.mark.wymaga_symlinku
def test_usun_drzewo_nie_wchodzi_w_dowiazanie(tmp_path):
    cel = tmp_path / "cel"
    cel.mkdir()
    (cel / "cudzy.txt").write_text("zostaje", encoding="utf-8")
    k = tmp_path / "drzewo"
    k.mkdir()
    os.symlink(cel, k / "link", target_is_directory=True)
    assert odinstalowanie.usun_drzewo(k) is True
    assert (cel / "cudzy.txt").is_file()


def test_uklad_domyslnego_korzenia_bez_jarvo_root(tmp_path, monkeypatch):
    """Procesy floty mają JARVO_ROOT; dla korzenia domyślnego układ liczymy bez niego (na Linuksie logi i cache
    zostają w katalogach XDG, jak w poleceniu jarvo i autostarcie)."""
    env = {"XDG_DATA_HOME": str(tmp_path / "xdg-data"), "XDG_STATE_HOME": str(tmp_path / "xdg-state"),
           "XDG_CACHE_HOME": str(tmp_path / "xdg-cache"), "LOCALAPPDATA": str(tmp_path / "lad")}
    monkeypatch.setenv("HOME", str(tmp_path))
    domyslny = sciezki.uklad(env)
    z_root = sciezki.uklad({**env, "JARVO_ROOT": str(domyslny.root)})
    assert odinstalowanie.uklad_instalacji(z_root, {**env, "JARVO_ROOT": str(domyslny.root)}) == domyslny
    inny = sciezki.uklad({**env, "JARVO_ROOT": str(tmp_path / "inny")})
    assert odinstalowanie.uklad_instalacji(inny, {**env, "JARVO_ROOT": str(tmp_path / "inny")}) == inny
    e = odinstalowanie.env_podprocesu(z_root, {**env, "JARVO_ROOT": str(domyslny.root), "JARVO_TOKEN": "x" * 20,
                                               "jarvo_token": "y" * 20})
    assert "JARVO_ROOT" not in e and not {k.upper() for k in e} & {"JARVO_TOKEN"}


# ---------------------------------------------------------------- bootstrap: .jarvo-ref dla jarvo update

class _Cichy(SimpleHTTPRequestHandler):
    def log_message(self, *_a):
        pass


@pytest.fixture
def pliki(tmp_path):
    katalog = tmp_path / "www"
    katalog.mkdir()
    httpd = None
    for port in PORTY:
        try:
            httpd = _Serwer(("127.0.0.1", port), partial(_Cichy, directory=str(katalog)))
            break
        except OSError:
            continue
    if httpd is None:
        pytest.skip("brak wolnego portu 19220–19229")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield katalog, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


_PS_FUNKCJE = r"""
$ErrorActionPreference = 'Stop'
$e = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{skrypt}', [ref]$null, [ref]$e)
$typ = [System.Management.Automation.Language.FunctionDefinitionAst]
foreach ($f in $ast.FindAll({{ param($n) $n -is $typ }}, $true)) {{
  . ([scriptblock]::Create($f.Extent.Text))
}}
$JarvoNaSucho = $false
$JarvoRepo = 'jarojarojaro-jaro/JARVO'
"""


@pytest.mark.windows_only
def test_bootstrap_ps1_zapisuje_ref(tmp_path, pliki):
    www, adres = pliki
    (www / "app.tar.gz").write_bytes(_archiwum(SHA_NOWA))
    ps = shutil.which("powershell")
    if ps is None:
        pytest.skip("brak PowerShella")
    cel, pobrane = tmp_path / "program" / "app" / SHA_NOWA[:12], tmp_path / "pobrane"
    skrypt = (_PS_FUNKCJE.format(skrypt=PS1) + f"function JarvoAdresKodu([string]$Sha) {{ '{adres}/app.tar.gz' }}\n"
              f"JarvoKod '{SHA_NOWA}' '{cel}' '{pobrane}' 'claude/epic-allen'\n"
              f"JarvoKod '{SHA_NOWA}' '{tmp_path / 'bez-refu'}' '{pobrane}'\n")
    r = subprocess.run([ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                        skrypt], capture_output=True, encoding="utf-8", errors="replace", timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    assert aktualizacja.ref_kodu(cel) == "claude/epic-allen" and aktualizacja.wersja_kodu(cel) == SHA_NOWA
    assert not (tmp_path / "bez-refu" / ".jarvo-ref").exists()


@pytest.mark.wymaga_bash
def test_bootstrap_sh_zapisuje_ref(tmp_path, pliki):
    www, adres = pliki
    (www / "app.tar.gz").write_bytes(_archiwum(SHA_NOWA))

    def msys(p: Path) -> str:
        return "/" + p.drive[0].lower() + p.as_posix()[2:] if WINDOWS else str(p)
    program, pobrane = tmp_path / "program", tmp_path / "pobrane"
    czyste = {k: v for k, v in os.environ.items()
              if not k.startswith("JARVO_") and k not in ("MSYS_NO_PATHCONV", "MSYS2_ARG_CONV_EXCL")}
    r = uruchom_bash("-c", f'source "{msys(SH)}"\n'
                           f"adres_kodu() {{ printf '%s\\n' '{adres}/app.tar.gz'; }}\n"
                           f'SHA={SHA_NOWA}; REF=v1.2; PROGRAM="{msys(program)}"; POBRANE="{msys(pobrane)}"; DRY=0\n'
                           "kod\n", env=czyste, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    app = program / "app" / SHA_NOWA[:12]
    assert aktualizacja.ref_kodu(app) == "v1.2" and aktualizacja.wersja_kodu(app) == SHA_NOWA
    tekst = SH.read_text(encoding="utf-8")
    assert re.search(r'REF="\$ref"', tekst) and ".jarvo-ref" in tekst
