"""Start aplikacji Jarvo (docs/HQ.md „Ekran startu”): właściciel z USER.md i gotowość bez sekretów (hq/plugin/aplikacja.py),
podpowiedzi N0 z rankingiem Beta i „Nigdy” na zawsze (podpowiedzi.py), trasy `GET /app`, `GET /podpowiedzi`,
`POST /podpowiedzi/{id}/reakcja` (trasy_aplikacji.py), „Czeka na Ciebie” z rozmowy.db i aktualizacja po pracy
(obserwator.py: update-request dopiero po ciszy bez pracy)."""
from __future__ import annotations

import json
import secrets
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import test_silnik_rozmow as T  # noqa: E402
from conftest import load_script  # noqa: E402

A = load_script("hq/plugin/aplikacja.py", "jarvo_test_apl_aplikacja")
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
                   "profil_wlasciciela": True}
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
        m = SimpleNamespace(**vars(T.M), aplikacja=A, podpowiedzi=PD)
        app = FastAPI()
        router = APIRouter(route_class=T.M.ochrona.Trasa)
        self.sciezki = TA.dolacz(router, m=m, trasy=T.trasy, silnik=lambda: self.sil, agenci=self.agenci,
                                 gotowosc=self.got, nawyki=self.nawyki,
                                 stan_aktualizacji=lambda: {"online": False, "state": "unknown", "behind": 0},
                                 hello=lambda: {"wersja": "abc123", "silnik": "ok"}, decyzje=lambda: self.pytania,
                                 log=self.logi.append)
        app.include_router(router, prefix=P)
        self.ka = TestClient(app, headers={"X-Jarvo-Request": "1"})


@pytest.fixture
def swiat(tmp_path):
    s = SwiatApl(tmp_path)
    yield s
    s.zamknij()


def test_get_app_start_jednym_zapytaniem(swiat):
    assert set(swiat.sciezki) == {"GET /app", "GET /podpowiedzi", "POST /podpowiedzi/{pid}/reakcja"}
    a = swiat.ka.get(f"{P}/app").json()
    assert a["wersja"] == "abc123" and a["silnik"] == "ok" and a["decyzje"] == 0
    assert a["wlasciciel"] == {"imie": "Miki", "firma": "Złoty Kłos"}
    assert a["gotowosc"] == {"model": {"dostawca": "custom", "polaczony": True, "sposob": "klucz"}, "brama": "ok",
                             "profil_wlasciciela": True}
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
    swiat.sil.wykonaj_fn(swiat.sil.db.ustaw_meta, "aktualizacja_po_pracy", repr(time.time()))
    time.sleep(1.5)
    assert not prosba.exists()                                         # praca trwa (czeka na zgodę): bez prośby
    z = swiat.k.get(f"{P}/przebiegi/{pid}").json()["przebieg"]["zgoda"]
    assert swiat.k.post(f"{P}/przebiegi/{pid}/zgoda", json={"wybor": "deny", "request_id": z["request_id"]}).status_code == 200
    swiat.do_stanu(pid, "gotowe")
    T.czekaj(prosba.exists, 10, "update-request po ciszy")
    assert prosba.read_text() == "update" and swiat.sil.db.meta("aktualizacja_po_pracy") is None
    assert any(t == "aktualizacja" for t, _d in swiat.ramki("aktualizacja"))
