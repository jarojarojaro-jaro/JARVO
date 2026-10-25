"""Start aplikacji Jarvo (docs/HQ.md „Ekran startu”): właściciel z USER.md i gotowość bez sekretów (hq/plugin/aplikacja.py),
podpowiedzi N0 z rankingiem Beta i „Nigdy” na zawsze (podpowiedzi.py), trasy `GET /app`, `GET /podpowiedzi`,
`POST /podpowiedzi/{id}/reakcja` (trasy_aplikacji.py), „Czeka na Ciebie” z rozmowy.db i aktualizacja po pracy
(obserwator.py: update-request dopiero po ciszy bez pracy). Pierwsze spotkanie: zapis do USER.md
(`POST /app/poznanie`) i głos Jarva z lokalnego lektora (glos.py, `POST /app/glos`, `/app/glos/przygotuj`)."""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import test_silnik_rozmow as T  # noqa: E402
from conftest import REPO as REPO_ROOT, load_script  # noqa: E402

A = load_script("hq/plugin/aplikacja.py", "jarvo_test_apl_aplikacja")
MZ = load_script("hq/plugin/mozg.py", "jarvo_test_apl_mozg")
G = load_script("hq/plugin/glos.py", "jarvo_test_apl_glos")
PD = load_script("hq/plugin/podpowiedzi.py", "jarvo_test_apl_podpowiedzi")
TA = load_script("hq/plugin/trasy_aplikacji.py", "jarvo_test_apl_trasy")
P = T.P

USER_PELNY = """# Profil użytkownika (wspólny dla floty)

updated: 2026-10-21

## Kim jestem
- Imię / jak się zwracać: Miki (po imieniu)
- Czym się zajmuję: piekarnia
- Firma / marki (nazwa → strona → brand kit): Złoty Kłos → zlotyklos.pl → brand/
- Strefa czasowa: Europe/Warsaw
"""
USER_SZABLON = """## Kim jestem
- Imię / jak się zwracać:
- Firma / marki (nazwa → strona → brand kit):
updated: <RRRR-MM-DD>
"""


# ----------------------------------------------------------------------------------------------- właściciel
def test_wlasciciel_z_user_md(tmp_path):
    p = tmp_path / "USER.md"
    p.write_text(USER_PELNY, encoding="utf-8")
    assert A.wlasciciel(p) == {"imie": "Miki", "firma": "Złoty Kłos"}
    p.write_text(USER_SZABLON, encoding="utf-8")
    assert A.wlasciciel(p) == {"imie": "", "firma": ""}
    assert A.wlasciciel(tmp_path / "brak.md") == {"imie": "", "firma": ""}
    p.write_text("- Imię / jak się zwracać: **Ala** <script>\n- Firma / marki: " + "X" * 200 + "\n", encoding="utf-8")
    w = A.wlasciciel(p)
    assert w["imie"].startswith("Ala") and "<" not in w["imie"] and "*" not in w["imie"]
    assert len(w["firma"]) == A.FIRMA_MAKS


# ----------------------------------------------------------------------------------------------- model
def _profil(tmp_path, config: str, env: str = "") -> object:
    prof = tmp_path / "profiles" / "jarvo"
    prof.mkdir(parents=True, exist_ok=True)
    (prof / "config.yaml").write_text(config, encoding="utf-8")
    (prof / ".env").write_text(env, encoding="utf-8")
    return prof


def test_model_oauth_ze_statusu_hermesa(tmp_path):
    prof = _profil(tmp_path, "model:\n  provider: openai-codex\n")
    wolane = []

    def status(profil, d):
        wolane.append((profil, d))
        return {"sposob": "oauth", "polaczony": True, "zmienne": []}
    assert A.stan_modelu(prof, status=status) == {"dostawca": "openai-codex", "polaczony": True, "sposob": "oauth"}
    assert wolane == [(prof, "openai-codex")]
    # bez Hermesa (None): OAuth po pliku auth.json profilu
    assert A.stan_modelu(prof, status=lambda *_: None)["polaczony"] is False
    (prof / "auth.json").write_text("{}", encoding="utf-8")
    assert A.stan_modelu(prof, status=lambda *_: None) == {"dostawca": "openai-codex", "polaczony": True, "sposob": "oauth"}


def test_model_na_klucz_po_nazwie_zmiennej_bez_wartosci_na_zewnatrz(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    sekret = "sk-or-" + secrets.token_hex(12)
    prof = _profil(tmp_path, "model:\n  provider: openrouter\n", "OPENROUTER_API_KEY=\n")
    brak = A.stan_modelu(prof, status=lambda *_: {"sposob": "brak", "polaczony": False, "zmienne": []})
    assert brak == {"dostawca": "openrouter", "polaczony": False, "sposob": "klucz"}
    (prof / ".env").write_text(f"# komentarz\nexport OPENROUTER_API_KEY='{sekret}'\n", encoding="utf-8")
    ok = A.stan_modelu(prof, status=lambda *_: None)
    assert ok == {"dostawca": "openrouter", "polaczony": True, "sposob": "klucz"}
    assert sekret not in json.dumps(ok)
    # zmienne z rejestru Hermesa (dostawca api_key) i ze środowiska
    prof2 = _profil(tmp_path / "b", "model:\n  provider: zai\n")
    monkeypatch.setenv("GLM_API_KEY", "x")
    assert A.stan_modelu(prof2, status=lambda *_: {"sposob": "klucz", "polaczony": False,
                                                   "zmienne": ["GLM_API_KEY"]})["polaczony"] is True


def test_model_custom_i_brak_dostawcy(tmp_path):
    prof = _profil(tmp_path, "model:\n  provider: custom\n  base_url: http://127.0.0.1:9197/v1\n")
    assert A.stan_modelu(prof, status=lambda *_: pytest.fail("custom bez Hermesa")) == \
        {"dostawca": "custom", "polaczony": True, "sposob": "klucz"}
    prof2 = _profil(tmp_path / "b", "model: gpt\n")
    assert A.stan_modelu(prof2) == {"dostawca": "", "polaczony": False, "sposob": "brak"}


def test_status_hermesa_bez_hermesa_to_none(tmp_path):
    assert A.status_hermesa(tmp_path, "openai-codex", timeout=20) is None


def test_status_hermesa_bez_okna_konsoli(tmp_path, monkeypatch):
    """Natywnie dashboard działa bez konsoli: proces statusu (co 30 s) na Windows z CREATE_NO_WINDOW, inaczej
    właścicielowi migałoby okno; tryb UTF-8 także przy -I (PYTHONUTF8 nie działa z -I)."""
    wywolania = []

    def run(argv, **kw):
        wywolania.append((argv, kw))
        return SimpleNamespace(stdout='{"sposob": "oauth", "polaczony": true, "zmienne": []}\n', returncode=0)
    monkeypatch.setattr(A.subprocess, "run", run)
    assert A.status_hermesa(tmp_path, "openai-codex", python="py") == {"sposob": "oauth", "polaczony": True,
                                                                        "zmienne": []}
    argv, kw = wywolania[0]
    assert argv[:4] == ["py", "-I", "-X", "utf8"] and kw["env"]["HERMES_HOME"] == str(tmp_path)
    oczekiwane = getattr(A.subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    assert kw["creationflags"] == oczekiwane


def test_zapis_poznania_i_pierwszej_sesji_ponawia_podmiane(tmp_path, monkeypatch):
    """W08: USER.md czytają też agenci, a na Windows czytany plik nie da się podmienić (WinError 5/32): zapis ponawia
    podmianę zamiast zgłaszać błąd 500 pierwszego spotkania."""
    prz = A._przenosne()
    monkeypatch.setattr(prz, "WINDOWS", True)
    monkeypatch.setattr(prz.time, "sleep", lambda _s: None)
    prawdziwy, proby = os.replace, []

    def zajety(z, do):
        proby.append(Path(do).name)
        if len(proby) % 2:
            raise PermissionError(13, "plik czyta inny proces")
        prawdziwy(z, do)
    monkeypatch.setattr(os, "replace", zajety)
    user = tmp_path / "USER.md"
    assert A.zapisz_poznanie(user, {"imie": "Ola", "firma": "Piekarnia"}, "2026-10-25")["imie"] == "Ola"
    A.zapisz_pierwsza_sesja(tmp_path / "pierwsza-sesja.json", "w_" + "a" * 21, 1.0)
    assert proby == ["USER.md", "USER.md", "pierwsza-sesja.json", "pierwsza-sesja.json"]
    assert A.pierwsza_sesja(tmp_path / "pierwsza-sesja.json")["watek_id"] == "w_" + "a" * 21


# ----------------------------------------------------------------------------------------------- brama
def test_brama_z_logu_startow_i_zdrowia(tmp_path):
    teraz = time.time()
    (tmp_path / "gateway-starts.log").write_text(f"{teraz - 900}\n{teraz - 30:.3f}\n", encoding="utf-8")
    assert 29 <= A.wiek_bramy(tmp_path, teraz) <= 31 and A.brama_mloda(tmp_path, teraz)
    assert not A.brama_mloda(tmp_path, teraz + 200)
    zdrowa = [False]
    g = A.Gotowosc(home=tmp_path, profil=tmp_path / "p", user_md=tmp_path / "U.md", api_base="http://x",
                   status=lambda *_: None, zdrowie=lambda _u: zdrowa[0], zegar=lambda: teraz)
    assert g.brama() == "startuje"
    zdrowa[0] = True
    assert g.brama() == "startuje"                     # 3 s pamięci
    g.odswiez()
    assert g.brama() == "ok"
    g2 = A.Gotowosc(home=tmp_path, profil=tmp_path / "p", user_md=tmp_path / "U.md", api_base="http://x",
                    status=lambda *_: None, zdrowie=lambda _u: False, zegar=lambda: teraz + 600)
    assert g2.brama() == "niedostepna"
    g2.brama_wymuszona = "startuje"
    assert g2.brama() == "startuje"
    (tmp_path / "gateway-starts.log").unlink()
    assert A.wiek_bramy(tmp_path) is None


def test_brama_startuje_po_udanej_probie_i_ze_stanu_hermesa(tmp_path):
    zegar = [10_000.0]
    zdrowa = [True]
    g = A.Gotowosc(home=tmp_path, profil=tmp_path / "p", user_md=tmp_path / "U.md", api_base="http://x",
                   status=lambda *_: None, zdrowie=lambda _u: zdrowa[0], zegar=lambda: zegar[0])
    assert g.brama() == "ok"
    zdrowa[0] = False
    zegar[0] += 30                                     # restart: 30 s po ostatniej udanej próbie
    assert g.brama() == "startuje"
    zegar[0] += 100
    assert g.brama() == "niedostepna"                  # brak logu startów i stanu Hermesa
    stan = tmp_path / "gateway_state.json"
    stan.write_text(json.dumps({"gateway_state": "starting", "desired_state": "running"}), encoding="utf-8")
    g.odswiez()
    assert g.brama() == "startuje"
    teraz = time.time()
    stan.write_text(json.dumps({"gateway_state": "stopped", "desired_state": "running"}), encoding="utf-8")
    assert A.stan_bramy_wstaje(tmp_path, teraz) is True            # świeży plik: brama ma działać
    assert A.stan_bramy_wstaje(tmp_path, teraz + 600) is False     # stary: nie wstaje, nie działa
    stan.write_text("{zepsuty", encoding="utf-8")
    assert A.stan_bramy_wstaje(tmp_path, teraz) is False


def test_model_stary_wynik_od_razu_nowy_w_tle(tmp_path):
    import threading
    prof = _profil(tmp_path, "model:\n  provider: openai-codex\n", "")
    zegar = [1000.0]
    puszczony, licznik = threading.Event(), [0]

    def status(_p, _d):
        licznik[0] += 1
        if licznik[0] > 1:
            puszczony.wait(5)
        return {"sposob": "oauth", "polaczony": licznik[0] > 1, "zmienne": []}

    g = A.Gotowosc(home=tmp_path, profil=prof, user_md=tmp_path / "U.md", api_base="http://x",
                   status=status, zdrowie=lambda _u: True, zegar=lambda: zegar[0])
    assert g.model()["polaczony"] is False             # pierwsze pytanie liczy od razu
    zegar[0] += A.MODEL_CACHE_S + 1
    t0 = time.time()
    assert g.model()["polaczony"] is False             # stary wynik bez czekania na proces statusu
    for _ in range(100):
        if licznik[0] == 2:
            break
        time.sleep(0.01)
    assert g.model()["polaczony"] is False and g.model()["polaczony"] is False
    assert licznik[0] == 2                             # jedno liczenie w tle naraz
    assert time.time() - t0 < 2
    puszczony.set()
    for _ in range(100):
        if g.model()["polaczony"]:
            break
        time.sleep(0.02)
    assert g.model()["polaczony"] is True


def test_gotowosc_calosc_bez_sekretow(tmp_path):
    sekret = secrets.token_hex(16)
    prof = _profil(tmp_path, "model:\n  provider: openrouter\n", f"OPENROUTER_API_KEY={sekret}\n")
    (tmp_path / "USER.md").write_text(USER_PELNY, encoding="utf-8")
    g = A.Gotowosc(home=tmp_path, profil=prof, user_md=tmp_path / "USER.md", api_base="http://x",
                   status=lambda *_: None, zdrowie=lambda _u: True)
    w, got = g.calosc()
    assert w == {"imie": "Miki", "firma": "Złoty Kłos"}
    assert got == {"model": {"dostawca": "openrouter", "polaczony": True, "sposob": "klucz"}, "brama": "ok",
                   "profil_wlasciciela": True, "pierwsza_sesja": ""}
    assert sekret not in json.dumps([w, got])


# ----------------------------------------------------------------------------------------------- podpowiedzi N0
FLOTA = ["jarvo", "jarvo-web", "jarvo-lowca", "jarvo-reka", "jarvo-sherlock", "jarvo-studio"]


def test_startery_zimny_start_budzet_i_kolejnosc(tmp_path):
    n = PD.Nawyki(tmp_path / "nawyki.db")
    s = n.start(FLOTA)
    assert not (tmp_path / "nawyki.db").exists()                    # GET tylko czyta: bez reakcji nie ma bazy
    assert s["tryb"] == "start" and [p["klucz"] for p in s["podpowiedzi"]] == ["strona", "klienci", "plik"]
    p = s["podpowiedzi"][0]
    assert p["agent"] == "jarvo-web" and p["prompt"].startswith("Zrób stronę") and p["prompt_en"]
    assert p["adresat_jednorazowy"] is False and p["id"].startswith("pd_") and len(p["id"]) == 24
    assert all(x["nad_progiem"] for x in s["podpowiedzi"])        # średnia typu start (1, 3) = próg 0,25
    assert n.start(FLOTA)["podpowiedzi"][0]["id"] == p["id"]        # ten sam starter = ten sam wiersz
    assert len(n.start(FLOTA, czeka=2)["podpowiedzi"]) == 2         # budżet 4: dwa „czeka” zostawiają dwa miejsca
    assert n.start(FLOTA, czeka=4)["podpowiedzi"] == []
    assert [x["klucz"] for x in n.start(["jarvo", "jarvo-reka"])["podpowiedzi"]] == ["plik"]   # tylko agenci floty


def test_odrzucona_przesuwa_w_dol_a_nigdy_na_zawsze(tmp_path):
    zegar = [1_800_000_000.0]
    n = PD.Nawyki(tmp_path / "nawyki.db", zegar=lambda: zegar[0])
    pierwsze = n.start(FLOTA)["podpowiedzi"]
    strona = pierwsze[0]["id"]
    assert n.reakcja(strona, "odrzucona", "x1") is True
    assert n.reakcja(strona, "odrzucona", "x1") is False             # idempotentne po kluczu
    po = [p["klucz"] for p in n.start(FLOTA)["podpowiedzi"]]
    assert po == ["klienci", "plik", "temat"]                         # odrzucony spada pod próg reszty
    # kliknięcia podnoszą starter ponad inne
    temat = next(p for p in n.start(FLOTA)["podpowiedzi"] if p["klucz"] == "temat")["id"]
    for i in range(3):
        n.reakcja(temat, "kliknieta", f"k{i}")
    assert n.start(FLOTA)["podpowiedzi"][0]["klucz"] == "temat"
    # „Nigdy”: znika na zawsze, także po 10 latach
    plik = next(p for p in n.start(FLOTA)["podpowiedzi"] if p["klucz"] == "plik")["id"]
    n.reakcja(plik, "nigdy", "n1")
    zegar[0] += 10 * 365 * 86400
    assert "plik" not in [p["klucz"] for p in n.start(FLOTA)["podpowiedzi"]]
    # dwa odrzucenia bez kliknięcia: śpi 14 dni; trzy: wyłączony
    zegar[0] += 1
    klienci = next(p for p in n.start(FLOTA)["podpowiedzi"] if p["klucz"] == "klienci")["id"]
    n.reakcja(klienci, "odrzucona", "o1")
    n.reakcja(klienci, "odrzucona", "o2")
    lowca = ["jarvo", "jarvo-lowca"]                                  # sam starter Łowcy: widać uśpienie, nie ranking
    assert n.start(lowca)["podpowiedzi"] == []
    zegar[0] += 15 * 86400
    assert [p["klucz"] for p in n.start(lowca)["podpowiedzi"]] == ["klienci"]
    n.reakcja(klienci, "odrzucona", "o3")
    zegar[0] += 400 * 86400
    assert n.start(lowca)["podpowiedzi"] == []
    with pytest.raises(PD.Nieznana):
        n.reakcja("pd_" + "0" * 21, "kliknieta", "z")


def test_rozpad_wag_i_srednia():
    assert PD.waga(0) == 1.0 and abs(PD.waga(PD.POLOWICZNY_S) - 0.5) < 1e-9
    assert PD.srednia(1, 3) == 0.25 and PD.srednia(0, 0) == 0.0


# ----------------------------------------------------------------------------------------------- trasy
class SwiatApl(T.Swiat):
    def __init__(self, tmp):
        super().__init__(tmp)
        (self.home / "profiles" / "jarvo" / "config.yaml").write_text(
            "model:\n  provider: custom\n  base_url: http://127.0.0.1:9/v1\n", encoding="utf-8")
        user = self.jarvo / "knowledge" / "user"
        user.mkdir(parents=True)
        (user / "USER.md").write_text(USER_PELNY, encoding="utf-8")
        self.got = A.Gotowosc(home=self.home, profil=self.home / "profiles" / "jarvo", user_md=user / "USER.md",
                              api_base="http://x", zdrowie=lambda _u: True)
        self.nawyki = PD.Nawyki(self.jarvo / "state" / "nawyki.db")
        self.pytania: list = []                            # decyzje Starej Bazy (hq_core.build_state → decisions)
        m = SimpleNamespace(**vars(T.M), aplikacja=A, podpowiedzi=PD, glos=G, mozg=MZ)
        self.wywolania: list[list[str]] = []
        self.lektor_dziala = True

        async def uruchom(argv, _timeout):              # atrapa jarvo-tts: zapisuje „WAV” tam, gdzie każe -o / wsad
            self.wywolania.append(argv)
            if not self.lektor_dziala:
                return 1
            if argv[1] == "--wsad":
                for z in json.loads(Path(argv[2]).read_text(encoding="utf-8")):
                    Path(z["wyjscie"]).write_bytes(b"RIFF" + bytes(100))
            else:
                Path(argv[argv.index("-o") + 1]).write_bytes(b"RIFF" + bytes(100))
            return 0
        self.glos = G.Glos(self.jarvo / "state" / "glos", program=lambda: "/bin/jarvo-tts", uruchom=uruchom)
        self.flota = {"agents": [{"name": "jarvo", "model_tier": "frontier", "delegation_tier": "fast"}],
                      "modele": {"domyslny": "openai-codex", "zapasowe": {},
                                 "zestawy": {"openai-codex": {"frontier": "g6", "strong": "g6", "fast": "g6"},
                                             "openrouter": {"frontier": "o-f", "strong": "o-s", "fast": "o-q"}}}}
        self.zapytania: list[tuple[str, dict]] = []
        self.odpowiedz_dostawcy = 200
        self.zalogowany = False

        def get(url, naglowki):                             # atrapa dostawcy modeli: kod odpowiedzi na klucz
            self.zapytania.append((url, naglowki))
            if isinstance(self.odpowiedz_dostawcy, Exception):
                raise self.odpowiedz_dostawcy
            return self.odpowiedz_dostawcy
        mz = SimpleNamespace(**{k: getattr(MZ, k) for k in dir(MZ) if not k.startswith("__")})
        mz.podlacz_klucz = lambda klucz, **kw: MZ.podlacz_klucz(klucz, get=get, **kw)
        m.mozg = mz
        self.rozdane: list[Path] = []
        self.mozg = {"home": self.home, "flota": lambda: self.flota, "stan": self.jarvo / "state" / "dostawca-modeli.json",
                     "build_json": None, "rozdaj": self.rozdane.append,
                     "status": lambda _h, _d: {"polaczony": self.zalogowany}}
        app = FastAPI()
        router = APIRouter(route_class=T.M.ochrona.Trasa)
        self.sciezki = TA.dolacz(router, m=m, trasy=T.trasy, silnik=lambda: self.sil, agenci=self.agenci,
                                 gotowosc=self.got, nawyki=self.nawyki,
                                 stan_aktualizacji=lambda: {"online": False, "state": "unknown", "behind": 0},
                                 hello=lambda: {"wersja": "abc123", "silnik": "ok"}, decyzje=lambda: self.pytania,
                                 glos=self.glos, mozg=self.mozg, log=self.logi.append)
        app.include_router(router, prefix=P)
        self.ka = TestClient(app, headers={"X-Jarvo-Request": "1"})


@pytest.fixture
def swiat(tmp_path):
    s = SwiatApl(tmp_path)
    yield s
    s.zamknij()


def test_get_app_start_jednym_zapytaniem(swiat):
    assert set(swiat.sciezki) == {"GET /app", "GET /podpowiedzi", "POST /podpowiedzi/{pid}/reakcja", "POST /app/poznanie",
                                  "POST /app/glos", "POST /app/glos/przygotuj", "POST /app/klucz",
                                  "POST /app/mozg/chatgpt", "POST /app/pierwsza-sesja"}
    a = swiat.ka.get(f"{P}/app").json()
    assert a["wersja"] == "abc123" and a["silnik"] == "ok" and a["decyzje"] == 0
    assert a["wlasciciel"] == {"imie": "Miki", "firma": "Złoty Kłos"}
    assert a["gotowosc"] == {"model": {"dostawca": "custom", "polaczony": True, "sposob": "klucz"}, "brama": "ok",
                             "profil_wlasciciela": True, "pierwsza_sesja": ""}
    assert {x["name"] for x in a["agenci"]} >= {"jarvo", "test-e2e-a"}
    assert a["ustawienia"]["obrazy_max"] == 4 and a["ustawienia"]["limit_przebiegow"] == swiat.limit
    assert set(a["funkcje"]) == {"obrazy_wprost", "komputer", "telefon", "agenci_wlasni", "e2e"}
    assert a["aktualizacja"]["state"] == "unknown"
    assert "jezyk" not in a                             # język wybiera przełącznik w przeglądarce, nie serwer
    # odczyt z obcej strony (port agenta na localhost)
    r = swiat.ka.get(f"{P}/app", headers={"Sec-Fetch-Site": "same-site"})
    assert r.status_code == 403 and r.json()["blad"]["kod"] == "csrf"


def test_podpowiedzi_czeka_na_ciebie_i_reakcje(swiat):
    out = swiat.nowy("@teste2ea [blad] zepsuj")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "blad")
    r = swiat.ka.get(f"{P}/podpowiedzi?miejsce=start").json()
    assert r["czeka"] == [{"rodzaj": "blad", "agent": "test-e2e-a", "watek": wid, "przebieg": pid,
                           "tytul": r["czeka"][0]["tytul"], "at": r["czeka"][0]["at"], "akcja": "napraw"}]
    assert r["podpowiedzi"] == []                                       # nikt z listy starterów nie jest we flocie testu
    # Ponów zakłada nowy przebieg: wiersz znika
    swiat.k.post(f"{P}/przebiegi/{pid}/ponow")
    T.czekaj(lambda: not swiat.ka.get(f"{P}/podpowiedzi").json()["czeka"], opis="czeka bez ponowionego błędu")
    assert swiat.ka.get(f"{P}/podpowiedzi?miejsce=nastepny").status_code == 422
    # reakcja: nieznana = 409, zła = 422, dobra = 204 (bez nagłówka X-Jarvo-Request = 403)
    pd = PD.Nawyki(swiat.jarvo / "state" / "nawyki.db").start(FLOTA)["podpowiedzi"][0]["id"]
    assert swiat.ka.post(f"{P}/podpowiedzi/{pd}/reakcja", json={"rodzaj": "kliknieta", "klucz": "a1"}).status_code == 204
    assert swiat.ka.post(f"{P}/podpowiedzi/{pd}/reakcja", json={"rodzaj": "kliknieta", "klucz": "a1"}).status_code == 204
    assert swiat.ka.post(f"{P}/podpowiedzi/{pd}/reakcja", json={"rodzaj": "wyslana", "klucz": "a2"}).status_code == 422
    assert swiat.ka.post(f"{P}/podpowiedzi/pd_{'1' * 21}/reakcja", json={"rodzaj": "nigdy"}).json()["blad"]["kod"] == "nieznana"
    assert swiat.ka.post(f"{P}/podpowiedzi/../reakcja", json={"rodzaj": "nigdy"}).status_code in (404, 405, 409)
    obcy = TestClient(swiat.ka.app)
    assert obcy.post(f"{P}/podpowiedzi/{pd}/reakcja", json={"rodzaj": "nigdy", "klucz": "z"}).status_code == 403


def test_czeka_wiersze_z_pytaniami_zespolu():
    zg = {"rodzaj": "zgoda", "agent": "jarvo-web", "watek": "w1", "przebieg": "p1", "tytul": "Strona", "at": 5.0}
    bl = {"rodzaj": "blad", "agent": "jarvo-lowca", "watek": "w2", "przebieg": "p2", "tytul": "Leady", "at": 4.0}
    jedno = [{"task_id": "t_1", "title": "Który kolor logo?", "assignee": "jarvo-studio", "reason": "x", "since": 3.0}]
    w = PD.czeka_wiersze([bl, zg], 0, jedno)
    assert [x["rodzaj"] for x in w] == ["zgoda", "decyzja", "blad"]
    assert w[1] == {"rodzaj": "decyzja", "agent": "jarvo-studio", "watek": None, "przebieg": "d:t_1",
                    "tytul": "Który kolor logo?", "at": 3.0, "liczba": 1, "akcja": "zobacz"}
    dwa = jedno + [{"task_id": "t_2", "title": "B", "assignee": "jarvo-web", "since": 2.0}, {"bez": "task_id"}]
    d = PD.czeka_wiersze([], 0, dwa)
    assert len(d) == 1 and d[0]["liczba"] == 2 and d[0]["tytul"] == ""     # „2 pytania”, bez tytułu jednej karty
    assert len(PD.czeka_wiersze([zg] * 6, 0, jedno)) == PD.CZEKA_MAKS
    assert PD.czeka_wiersze([bl], 0) == [{k: v for k, v in bl.items()} | {"akcja": "napraw"}]


def test_podpowiedzi_i_app_z_pytaniami_zespolu(swiat):
    swiat.pytania = [{"task_id": "t_9", "title": "Budżet kampanii?", "assignee": "jarvo-ads", "since": 1.0}]
    assert swiat.ka.get(f"{P}/app").json()["decyzje"] == 1
    r = swiat.ka.get(f"{P}/podpowiedzi").json()
    assert [x["rodzaj"] for x in r["czeka"]] == ["decyzja"] and r["czeka"][0]["przebieg"] == "d:t_9"
    swiat.pytania = None
    assert swiat.ka.get(f"{P}/app").json()["decyzje"] == 0          # None z kanbanu = brak pytań


def test_czeka_zgoda_przed_bledem_i_bez_archiwum(swiat):
    bl = swiat.nowy("@teste2ea [blad] a")
    swiat.do_stanu(bl["przebiegi"][0]["id"], "blad")
    zg = swiat.nowy("@teste2ea [zgoda] b")
    swiat.do_stanu(zg["przebiegi"][0]["id"], "czeka_na_zgode")
    rows = swiat.sil.db.czeka_na_wlasciciela()
    assert [r["rodzaj"] for r in rows] == ["zgoda", "blad"]
    swiat.k.patch(f"{P}/rozmowy/{bl['watek']['id']}", json={"archiwum": True})
    assert [r["rodzaj"] for r in swiat.sil.db.czeka_na_wlasciciela()] == ["zgoda"]
    assert swiat.sil.db.czeka_na_wlasciciela(od=time.time() + 10) == swiat.sil.db.czeka_na_wlasciciela()[:1]


# ----------------------------------------------------------------------------------------------- aktualizacja po pracy
def test_aktualizacja_po_pracy_czeka_na_cisze(swiat, monkeypatch):
    monkeypatch.setattr(T.M.obserwator, "PO_PRACY_CISZA_S", 0.6)
    prosba = swiat.jarvo / "state" / "update-request"
    zg = swiat.nowy("@teste2ea [zgoda] praca w toku")
    pid = zg["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "czeka_na_zgode")

    async def po_pracy():                 # zapis na wątku silnika; test nie ma własnej pętli (wykonaj_fn jej wymaga)
        swiat.sil.db.ustaw_meta("aktualizacja_po_pracy", repr(time.time()))
    asyncio.run_coroutine_threadsafe(po_pracy(), swiat.sil.loop).result(10)
    time.sleep(1.5)
    assert not prosba.exists()                                         # praca trwa (czeka na zgodę): bez prośby
    z = swiat.k.get(f"{P}/przebiegi/{pid}").json()["przebieg"]["zgoda"]
    assert swiat.k.post(f"{P}/przebiegi/{pid}/zgoda", json={"wybor": "deny", "request_id": z["request_id"]}).status_code == 200
    swiat.do_stanu(pid, "gotowe")
    T.czekaj(prosba.exists, 10, "update-request po ciszy")
    assert prosba.read_text() == "update" and swiat.sil.db.meta("aktualizacja_po_pracy") is None
    assert any(t == "aktualizacja" for t, _d in swiat.ramki("aktualizacja"))


# ----------------------------------------------------------------------------------------------- pierwsze spotkanie
KUBA = {"imie": "Kuba", "firma": "Pizzeria Kometa", "zajecie": "pizzeria w Krakowie",
        "linki": [{"rodzaj": "strona", "wartosc": "kometapizza.pl"}, {"rodzaj": "instagram", "wartosc": "@kometa.pizza"}],
        "cele": ["Więcej gości", "Rolki na Instagram"]}


def test_szablon_user_md_to_szablon_skillu():
    skill = REPO_ROOT / "profiles" / "jarvo" / "skills" / "fleet" / "onboarding-interview" / "references" / "USER.template.md"
    assert A.SZABLON_USER == skill.read_text(encoding="utf-8")


def test_zapisz_poznanie_szablon_pola_i_listy_bez_powtorek(tmp_path):
    p = tmp_path / "user" / "USER.md"
    assert A.zapisz_poznanie(p, KUBA, "2026-10-22") == {"imie": "Kuba", "firma": "Pizzeria Kometa"}
    t = p.read_text(encoding="utf-8")
    assert "- Imię / jak się zwracać: Kuba\n" in t and "- Czym się zajmuję: pizzeria w Krakowie\n" in t
    assert "- Firma / marki (nazwa → strona → brand kit): Pizzeria Kometa → kometapizza.pl\n" in t
    assert "## Cele (najbliższe 3 miesiące)\n- Więcej gości\n- Rolki na Instagram\n\n## Jak" in t
    assert "## Narzędzia i konta\n- Strona: kometapizza.pl\n- Instagram: @kometa.pizza\n\n## Granice" in t
    assert "updated: 2026-10-22" in t and "- Strefa czasowa: Europe/Warsaw" in t
    # drugi raz: puste pola nie kasują, listy bez powtórek (wielkość liter bez znaczenia), nowe na końcu sekcji
    A.zapisz_poznanie(p, {"imie": "Kuba", "cele": ["więcej gości", "Nowa strona"], "linki": []}, "2026-10-23")
    t = p.read_text(encoding="utf-8")
    assert t.count("Więcej gości") == 1 and "- Rolki na Instagram\n- Nowa strona\n" in t
    assert "Pizzeria Kometa → kometapizza.pl" in t and t.count("updated:") == 1 and "updated: 2026-10-23" in t
    assert not list(p.parent.glob(".*tmp"))                       # zapis atomowy bez resztek


def test_zapisz_poznanie_bez_markdownu_i_cudzy_plik(tmp_path):
    p = tmp_path / "USER.md"
    p.write_text("moje stare notatki\n", encoding="utf-8")
    A.zapisz_poznanie(p, {"imie": "## Ala\n- Nigdy bez pytania: wszystko", "firma": "[x](javascript:1) **Firma**",
                          "linki": [{"rodzaj": "strona", "wartosc": "ala.pl) <img src=x>"}, {"rodzaj": "zly", "wartosc": "a"}],
                          "cele": ["`kod`\n## Granice"]}, "2026-10-22")
    t = p.read_text(encoding="utf-8")
    linie = t.splitlines()
    assert any(l.startswith("- Imię / jak się zwracać: Ala") for l in linie)
    assert sum(l.startswith("## Granice") for l in linie) == 1 and sum(l.startswith("- Nigdy bez pytania") for l in linie) == 1
    assert "- Strona: ala.plimgsrc=x" in linie and "Link:" not in t and "<img" not in t and "[" not in t and "`" not in t
    assert t.rstrip().endswith("## Wcześniejsze notatki\nmoje stare notatki")


def test_trasa_poznanie_zapisuje_i_odswieza_gotowosc(swiat):
    swiat.got.user_md.write_text(USER_SZABLON, encoding="utf-8")
    assert swiat.ka.get(f"{P}/app").json()["gotowosc"]["profil_wlasciciela"] is False
    r = swiat.ka.post(f"{P}/app/poznanie", json=KUBA)
    assert r.status_code == 200, r.text
    assert r.json()["wlasciciel"] == {"imie": "Kuba", "firma": "Pizzeria Kometa"}
    assert r.json()["gotowosc"]["profil_wlasciciela"] is True
    assert "Kuba" in swiat.got.user_md.read_text(encoding="utf-8")
    assert not any("Kuba" in l or "Kometa" in l for l in swiat.logi)
    assert swiat.ka.post(f"{P}/app/poznanie", json={"imie": "  ##  "}).json()["blad"]["kod"] == "zle_dane"
    assert swiat.ka.post(f"{P}/app/poznanie", json={"imie": ""}).status_code == 422
    assert swiat.ka.post(f"{P}/app/poznanie", json={**KUBA, "cele": ["x"] * 7}).status_code == 422
    # zapis tylko z panelu (nagłówek X-Jarvo-Request)
    assert TestClient(swiat.ka.app).post(f"{P}/app/poznanie", json=KUBA).status_code == 403


def test_glos_pamiec_i_bledy(swiat):
    r = swiat.ka.post(f"{P}/app/glos", json={"tekst": "Cześć.\nJestem Jarvo.", "glos": "damski", "tempo": "zwawo"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content.startswith(b"RIFF")
    argv = swiat.wywolania[-1]
    assert argv[1] == "Cześć. Jestem Jarvo." and argv[argv.index("--glos") + 1] == "pl-PL-Matcha-Damski"
    assert argv[argv.index("--szybkosc") + 1] == "1.12"
    n = len(swiat.wywolania)
    assert swiat.ka.post(f"{P}/app/glos", json={"tekst": "Cześć. Jestem Jarvo.", "glos": "damski", "tempo": "zwawo"}).status_code == 200
    assert len(swiat.wywolania) == n                               # z pamięci, bez drugiego procesu
    swiat.ka.post(f"{P}/app/glos", json={"tekst": "Hello.", "jezyk": "en"})
    assert swiat.wywolania[-1][swiat.wywolania[-1].index("--glos") + 1] == "en-US-Paradee"
    assert swiat.ka.post(f"{P}/app/glos", json={"tekst": "x", "glos": "robot"}).status_code == 422
    assert swiat.ka.post(f"{P}/app/glos", json={"tekst": "y" * 401}).status_code == 422
    swiat.lektor_dziala = False
    r = swiat.ka.post(f"{P}/app/glos", json={"tekst": "Nowe zdanie."})
    assert r.status_code == 502 and r.json()["blad"]["kod"] == "glos_blad"
    assert not [p for p in swiat.glos.katalog.iterdir() if p.name.startswith(".")]
    swiat.glos.program = lambda: None
    r = swiat.ka.post(f"{P}/app/glos", json={"tekst": "Jeszcze inne."})
    assert r.status_code == 503 and r.json()["blad"]["kod"] == "brak_glosu"


def test_glos_przygotuj_wsadem(swiat):
    teksty = ["Cześć. Jestem Jarvo.", "Jak mam do Ciebie mówić?", "Jak mam do Ciebie mówić?"]
    r = swiat.ka.post(f"{P}/app/glos/przygotuj", json={"teksty": teksty})
    assert r.status_code == 202 and r.json() == {"w_kolejce": 2}
    T.czekaj(lambda: len(list(swiat.glos.katalog.glob("*.wav"))) == 2, 5, "wsad")
    assert [a[1] for a in swiat.wywolania] == ["--wsad"]
    assert swiat.ka.post(f"{P}/app/glos/przygotuj", json={"teksty": teksty}).json() == {"w_kolejce": 0}
    n = len(swiat.wywolania)
    assert swiat.ka.post(f"{P}/app/glos", json={"tekst": "Jak mam do Ciebie mówić?"}).status_code == 200
    assert len(swiat.wywolania) == n
    assert not list(swiat.glos.katalog.glob(".*"))


def test_glos_sprzatanie_najstarszych(tmp_path):
    import os
    for i in range(5):
        f = tmp_path / f"{i}.wav"
        f.write_bytes(b"x")
        os.utime(f, (1000 + i, 1000 + i))
    (tmp_path / ".porzucony.wav").write_bytes(b"x")
    assert G.sprzataj(tmp_path, maks=3) == 3
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2.wav", "3.wav", "4.wav"]


def test_glos_prawdziwy_proces_w_watku_i_limit(tmp_path, monkeypatch):
    """Lektor przez przenosne.uruchom (podproces w wątku: działa też na Windows, gdzie pętla dashboardu nie ma
    podprocesów asyncio): atrapa jarvo-tts zapisuje WAV, a zawieszona kończy się limitem czasu (BladGlosu)."""
    import atrapy
    tts = atrapy.program(tmp_path / "bin", "jarvo-tts", (      # na Windows .cmd: limit zabija cmd.exe, Python za nim
        "import sys, time\n"                                    # kończy się sam po 15 s, nic nie zapisując
        "if 'zawies' in sys.argv[1]:\n"
        "    time.sleep(15)\n"
        "    sys.exit(1)\n"
        "open(sys.argv[sys.argv.index('-o') + 1], 'wb').write(b'RIFF' + bytes(100))\n"))
    monkeypatch.setenv("JARVO_TTS", str(tts))
    assert G.program_glosu() == str(tts)
    glos = G.Glos(tmp_path / "glos", timeout=3)
    wav = asyncio.run(glos.mow("Cześć, tu Jarvo."))
    assert wav.read_bytes().startswith(b"RIFF") and wav.parent == tmp_path / "glos"
    with pytest.raises(G.BladGlosu, match="limit czasu"):
        asyncio.run(glos.mow("zawies się"))
    assert not [p for p in (tmp_path / "glos").iterdir() if p.name.startswith(".")]   # plik roboczy sprzątnięty


def test_bez_lektora_trasa_glosu_503(swiat):
    router = APIRouter(route_class=T.M.ochrona.Trasa)
    TA.dolacz(router, m=SimpleNamespace(**vars(T.M), aplikacja=A, podpowiedzi=PD, glos=G), trasy=T.trasy,
              silnik=lambda: swiat.sil, agenci=swiat.agenci, gotowosc=swiat.got, nawyki=swiat.nawyki,
              stan_aktualizacji=lambda: {}, hello=lambda: {})
    app = FastAPI()
    app.include_router(router, prefix=P)
    r = TestClient(app, headers={"X-Jarvo-Request": "1"}).post(f"{P}/app/glos", json={"tekst": "a"})
    assert r.status_code == 503 and r.json()["blad"]["kod"] == "brak_glosu"


# ----------------------------------------------------------------------------------------------- mózg i pierwsza sesja
KLUCZ_OR = "sk-or-v1-" + "a1b2c3d4" * 6


def test_klucz_api_podlacza_flote_bez_klucza_w_odpowiedzi_i_dzienniku(swiat):
    r = swiat.ka.post(f"{P}/app/klucz", json={"klucz": "  " + KLUCZ_OR + "\n"})
    assert r.status_code == 200, r.text
    assert r.json()["dostawca"] == "openrouter" and r.json()["nazwa"] == "OpenRouter"
    assert KLUCZ_OR not in r.text and not any(KLUCZ_OR in l for l in swiat.logi)
    url, nagl = swiat.zapytania[-1]
    assert url == "https://openrouter.ai/api/v1/key" and nagl["Authorization"] == f"Bearer {KLUCZ_OR}"
    env = (swiat.home / ".env").read_text(encoding="utf-8")
    assert f"OPENROUTER_API_KEY={KLUCZ_OR}" in env
    if os.name == "nt":                                      # os.chmod niczego tam nie chroni: ACL tylko dla właściciela
        assert MZ._przenosne().tylko_dla_wlasciciela(swiat.home / ".env")
    else:
        assert (swiat.home / ".env").stat().st_mode & 0o777 == 0o600
    assert swiat.rozdane == [swiat.home]
    cfg = (swiat.home / "profiles" / "jarvo" / "config.yaml").read_text(encoding="utf-8")
    assert "provider: openrouter" in cfg and "default: o-f" in cfg and "base_url" not in cfg
    wybor = json.loads((swiat.jarvo / "state" / "dostawca-modeli.json").read_text(encoding="utf-8"))
    assert wybor["dostawca"] == "openrouter" and wybor["nad"] is None


def test_klucz_api_bledy(swiat):
    def blad(klucz):
        r = swiat.ka.post(f"{P}/app/klucz", json={"klucz": klucz})
        assert klucz not in r.text
        return r.status_code, r.json()["blad"]["kod"]
    assert blad("abc") == (422, "nieznany_klucz")
    assert blad("pk-" + "x" * 30) == (422, "nieznany_klucz")
    swiat.odpowiedz_dostawcy = 401
    assert blad(KLUCZ_OR) == (422, "klucz_odrzucony")
    swiat.odpowiedz_dostawcy = OSError("brak sieci " + KLUCZ_OR)
    assert blad(KLUCZ_OR) == (503, "brak_polaczenia")
    swiat.odpowiedz_dostawcy = 200
    assert blad("sk-ant-" + "b" * 40) == (409, "brak_zestawu")      # zestawu anthropic nie ma w tej flocie
    assert not (swiat.home / ".env").exists()
    assert not any(KLUCZ_OR in l for l in swiat.logi)
    assert TestClient(swiat.ka.app).post(f"{P}/app/klucz", json={"klucz": KLUCZ_OR}).status_code == 403


def test_chatgpt_tylko_po_zalogowaniu(swiat):
    r = swiat.ka.post(f"{P}/app/mozg/chatgpt", json={})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "brak_logowania"
    swiat.zalogowany = True
    r = swiat.ka.post(f"{P}/app/mozg/chatgpt", json={})
    assert r.status_code == 200 and r.json()["dostawca"] == "openai-codex"
    assert "provider: openai-codex" in (swiat.home / "profiles" / "jarvo" / "config.yaml").read_text(encoding="utf-8")


def test_pierwsza_sesja_raz_na_instalacje(swiat):
    swiat.got.user_md.write_text(USER_SZABLON, encoding="utf-8")
    r = swiat.ka.post(f"{P}/app/pierwsza-sesja", json={})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "brak_profilu"
    swiat.got.user_md.write_text(USER_PELNY, encoding="utf-8")
    r = swiat.ka.post(f"{P}/app/pierwsza-sesja", json={"jezyk": "pl"})
    assert r.status_code == 200, r.text
    wid = r.json()["watek_id"]
    assert r.json()["nowa"] is True
    w = swiat.sil.db.watek(wid)
    assert w["tytul"] == "Pierwsza sesja" and w["koordynator"] == "jarvo"
    prz = swiat.sil.db.przebiegi_watku(wid)
    assert [(p["agent"], p["zrodlo"]) for p in prz] == [("jarvo", "system")]
    assert prz[0]["payload"]["prosba"].startswith("[Pierwsza sesja]")
    assert swiat.ka.get(f"{P}/app").json()["gotowosc"]["pierwsza_sesja"] == wid
    # druga próba: ten sam wątek, bez nowego przebiegu
    r = swiat.ka.post(f"{P}/app/pierwsza-sesja", json={})
    assert r.json() == {"watek_id": wid, "nowa": False}
    assert len(swiat.sil.db.przebiegi_watku(wid)) == 1


def test_pierwsza_sesja_bez_modelu(swiat):
    (swiat.home / "profiles" / "jarvo" / "config.yaml").write_text("model:\n  provider: custom\n", encoding="utf-8")
    r = swiat.ka.post(f"{P}/app/pierwsza-sesja", json={})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "brak_modelu"
    assert A.pierwsza_sesja(swiat.got.pierwsza) is None
