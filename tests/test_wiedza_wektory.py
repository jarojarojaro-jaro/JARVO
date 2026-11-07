"""Wektory skarbca (docs/WIEDZA.md §7, W4) na atrapie osadzania: wektory w state/wiedza.db przyrostowo i od nowa przy
zmianie modelu, szukanie wektorami z powrotem do słów (brak usługi, czas), aliasy z frontmattera, długie pytania
zdaniami, usługa HTTP z tokenem (wiedza/wektory.py z atrapą zamiast modelu), CLI `indeksuj`, `szukaj`, `ocena`."""
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wiedza"))
import wiedza as w  # noqa: E402
from atrapa_wektorow import MODEL, AtrapaWektorow, usluga_atrapy, wektor, wolny_koder  # noqa: E402


def notatka(sk, rel, tytul, streszczenie, tresc="", typ="fakt", **fm):
    front = {"typ": typ, "tagi": [], "utworzono": "2026-11-01", "zmieniono": "2026-11-01", "status": "aktualna",
             "zrodlo": "test", **fm}
    sk.zapisz_plik(rel, w.sklej(front, f"# {tytul}\n\n**{streszczenie}**\n\n{tresc}\n"))


@pytest.fixture
def sk(tmp_path, monkeypatch):
    monkeypatch.setenv("WIEDZA_DZIS", "2026-11-08")
    sk = w.Skarbiec(tmp_path / "knowledge", tmp_path / "state")
    sk.root.mkdir(parents=True)
    notatka(sk, "agenci/jarvo-web/formularz bez spamu", "Formularz bez spamu",
            "Formularze kontaktowe chronimy ukrytym polem przed spamem.", "Limit pięć wiadomości na godzinę.")
    notatka(sk, "pojecia/szybkość strony", "Szybkość strony", "Strona ma się pokazać na telefonie w 2,5 sekundy.")
    notatka(sk, "pojecia/kopie stron", "Kopie stron", "Kopie stron klientów robimy co noc i trzymamy 30 dni.")
    notatka(sk, "user/ola wrona", "Ola Wrona", "Ola Wrona prowadzi pracownię projektową w Toruniu.", typ="podmiot",
            aliasy=["szefowa", "właścicielka"])
    notatka(sk, "fleet/skille/audyt", "Audyt", "Skill audytu strony.", typ="skill")
    (sk.root / "zrodla" / "rozmowy").mkdir(parents=True)
    (sk.root / "zrodla" / "rozmowy" / "surowe.md").write_text("# Surowe\nSpam i formularze w rozmowie.\n", encoding="utf-8")
    return sk


def _szukane(ix):
    return {r[0] for r in ix.db.execute("SELECT sciezka FROM pliki") if not r[0].startswith(w.POZA_WYSZUKIWANIEM)}


def test_wektory_przyrostowo_i_pelne_przeliczenie_przy_innym_modelu(sk, monkeypatch):
    ix = w.Indeks(sk)
    try:
        ix.odswiez()
        a = AtrapaWektorow()
        r = ix.odswiez_wektory(a)
        szukane = _szukane(ix)
        assert r["nowe"] == r["wektorow"] == r["notatek"] == len(szukane) and not r["przerwane"]
        wiersze = ix.db.execute("SELECT sciezka, model, length(wektor), hash FROM wektory").fetchall()
        assert {x[0] for x in wiersze} == szukane                              # bez zrodla/ i skrzynka/
        assert all(x[1] == MODEL and x[2] == 4 * 64 and len(x[3]) == 16 for x in wiersze)
        assert all(t.startswith("passage: ") for t in a.wywolania[0])
        a.wywolania.clear()
        assert ix.odswiez_wektory(a)["nowe"] == 0 and a.wywolania == []        # bez zmian: bez usługi
        p = sk.root / "pojecia" / "kopie stron.md"
        t = p.stat().st_mtime + 30
        os.utime(p, (t, t))                                                    # dotknięty plik, ta sama treść
        ix.odswiez()
        assert ix.odswiez_wektory(a)["nowe"] == 0 and a.wywolania == []
        assert ix.db.execute("SELECT mtime FROM wektory WHERE sciezka = 'pojecia/kopie stron'").fetchone()[0] == p.stat().st_mtime
        notatka(sk, "pojecia/kopie stron", "Kopie stron", "Kopie stron klientów robimy co noc i trzymamy 60 dni.")
        ix.odswiez()
        assert ix.odswiez_wektory(a)["nowe"] == 1 and [len(x) for x in a.wywolania] == [1]
        p.unlink()
        ix.odswiez()
        assert ix.odswiez_wektory(a)["wektorow"] == len(szukane) - 1
        r = ix.odswiez_wektory(AtrapaWektorow(model="atrapa-e5@2"))         # inny model: wszystko od nowa
        assert r["usuniete"] == len(szukane) - 1 and r["nowe"] == r["wektorow"] == len(szukane) - 1
        assert {x[0] for x in ix.db.execute("SELECT DISTINCT model FROM wektory")} == {"atrapa-e5@2"}
        monkeypatch.setattr(w, "WEKTORY_PACZKA", 2)
        r = ix.odswiez_wektory(AtrapaWektorow(model="atrapa-e5@3", padnij_po=1))   # usługa pada w trakcie
        assert r["przerwane"] and r["nowe"] == 2 and r["wektorow"] == 2
        assert ix.odswiez_wektory(None) == {"model": "", "nowe": 0, "usuniete": 0, "wektorow": 0, "notatek": 0,
                                            "przerwane": True}
    finally:
        ix.zamknij()


def test_szukanie_wektorami_i_powrot_do_slow(sk):
    ix = w.Indeks(sk)
    try:
        ix.odswiez()
        a = AtrapaWektorow()
        ix.odswiez_wektory(a)
        assert ix.szukaj("jak odstraszyć automaty?") == [] and ix.silnik == "slowa"      # słowa nic nie znajdą
        wyn = ix.szukaj("jak odstraszyć automaty?", wektory=a)
        assert wyn[0]["sciezka"] == "agenci/jarvo-web/formularz bez spamu" and ix.silnik == "wektory"
        assert all(not r["sciezka"].startswith(("zrodla/", "fleet/")) for r in wyn)      # poza szukaniem i skille
        assert ix.szukaj("skill audytu", wektory=a, folder="fleet")[0]["sciezka"] == "fleet/skille/audyt"
        assert ix.szukaj("jak odstraszyć automaty?", wektory=a, silnik="slowa") == [] and ix.silnik == "slowa"
        hyb = ix.szukaj("kopie stron co noc", wektory=a, silnik="hybryda")
        assert hyb[0]["sciezka"] == "pojecia/kopie stron" and ix.silnik == "hybryda"
        slowa = [r["sciezka"] for r in ix.szukaj("kopie stron")]
        for zla in (AtrapaWektorow(padnij=True), AtrapaWektorow(model="")):              # usługa nie odpowiada
            assert [r["sciezka"] for r in ix.szukaj("kopie stron", wektory=zla)] == slowa and ix.silnik == "slowa"
        # notatka bez wektora (po ostatnim osadzaniu) wchodzi z miejscem z listy słów
        notatka(sk, "pojecia/kalendarz publikacji", "Kalendarz publikacji", "Posty planujemy w kalendarzu publikacji.")
        ix.odswiez()
        assert "pojecia/kalendarz publikacji" in [r["sciezka"] for r in ix.szukaj("kalendarz publikacji", wektory=a)]
        przyp = w.notatki_przypomnienia(ix, "jak odstraszyć automaty?", wektory=a)
        assert przyp[0]["sciezka"] == "agenci/jarvo-web/formularz bez spamu" and ix.silnik == "wektory"
    finally:
        ix.zamknij()


def test_aliasy_rozszerzaja_pytanie_takze_w_odmianie(sk):
    ix = w.Indeks(sk)
    try:
        ix.odswiez()
        assert ix.rozszerz("co lubi szefowa?") == "co lubi szefowa? Ola Wrona"
        assert ix.rozszerz("kto zastępuje szefową i właścicielce?").endswith(" Ola Wrona")
        assert ix.rozszerz("Ola Wrona to szefowa") == "Ola Wrona to szefowa"            # tytuł już jest
        assert ix.rozszerz("szef kuchni") == "szef kuchni"                              # inne słowo
        assert ix.szukaj("co lubi szefowa?")[0]["sciezka"] == "user/ola wrona"
        notatka(sk, "user/ola wrona", "Ola Wrona", "Ola Wrona prowadzi pracownię projektową w Toruniu.", typ="podmiot")
        ix.odswiez()
        assert ix.rozszerz("co lubi szefowa?") == "co lubi szefowa?"                    # aliasy idą za plikiem
        notatka(sk, "user/ola wrona", "Ola Wrona", "Ola Wrona prowadzi pracownię.", typ="podmiot", aliasy="Ola W., szefowa")
        ix.odswiez()
        assert ix.rozszerz("pytanie do szefowej") == "pytanie do szefowej Ola Wrona"
        assert w._ma_fraze(["ola", "w", "mowi"], ["ola", "w"]) and not w._ma_fraze(["ola"], ["ola", "w"])
    finally:
        ix.zamknij()
    # indeks sprzed aliasów (bez wersji w meta): jedno pełne odświeżenie odbudowuje aliasy
    ix = w.Indeks(sk)
    with ix.db:
        ix.db.execute("DELETE FROM aliasy")
        ix.db.execute("DELETE FROM meta WHERE klucz = 'wersja'")
    ix.zamknij()
    ix = w.Indeks(sk)
    try:
        assert ix.odswiez()["zmienione"] >= 4
        assert ix.rozszerz("szefowa") == "szefowa Ola Wrona"
        assert ix.odswiez()["zmienione"] == 0                                           # potem znów przyrostowo
    finally:
        ix.zamknij()


def test_dlugie_pytanie_idzie_zdaniami(sk):
    krotkie = "jak chronić formularze przed spamem"
    assert w.zdania_zapytania(krotkie) == [krotkie]
    dlugie = ("Przygotuj dla klienta krótki raport o wynikach ostatniego miesiąca i wyślij go rano. "
              "Sprawdź też, czy strona pokazuje się na telefonie w 2,5 sekundy i bez błędów.\n"
              "To ważne dla kampanii jesiennej, którą zaczynamy w przyszłym tygodniu. Tak.")
    zdania = w.zdania_zapytania(dlugie)
    assert len(dlugie.split()) > w.DLUGIE_ZAPYTANIE and len(zdania) == 3 and "Tak." not in zdania
    assert len(w.zdania_zapytania(" ".join(f"Zdanie numer {i} ma kilka słów." for i in range(20)))) == w.MAX_ZDAN
    jedno = " ".join(["słowo"] * 40)
    assert w.zdania_zapytania(jedno) == [jedno]                                         # bez zdań: całe pytanie
    ix = w.Indeks(sk)
    try:
        ix.odswiez()
        a = AtrapaWektorow()
        ix.odswiez_wektory(a)
        a.wywolania.clear()
        wyn = ix.szukaj(dlugie, wektory=a)
        assert a.wywolania == [[f"query: {z}" for z in zdania]]                          # jeden wektor na zdanie
        assert wyn[0]["sciezka"] == "pojecia/szybkość strony"                              # najlepsze zdanie wygrywa
    finally:
        ix.zamknij()


def test_usluga_http_token_czas_i_plik_stanu(tmp_path):
    stan = tmp_path / "state"
    plik = stan / w.WEKTORY_STAN
    with usluga_atrapy(stan) as serwer:
        d = json.loads(plik.read_text(encoding="utf-8"))
        assert set(d) == {"port", "token", "model", "wymiar", "pid", "od"} and d["pid"] == os.getpid()
        if os.name != "nt":
            assert stat.S_IMODE(plik.stat().st_mode) == 0o600                          # token: tylko właściciel
        k = w.KlientWektorow(stan, 2.0)
        assert k.dostepny and k.model == MODEL and k.zdrowie()["wymiar"] == 64
        v = k.osadz(["query: kopie stron", "passage: Formularz bez spamu"])
        assert len(v) == 2 and list(v[0]) == pytest.approx(wektor("query: kopie stron"), abs=1e-6)
        assert k.osadz([]) == []
        zly = w.KlientWektorow(stan, 2.0)
        zly.token = "zly"
        assert zly.osadz(["a"]) is None and "401" in zly.blad and zly.zdrowie() is None
        assert k._zapytaj("POST", "/osadz", {"teksty": "nie lista"}) is None and "400" in k.blad
        assert k._zapytaj("GET", "/inne") is None and "404" in k.blad
        serwer.koder = lambda _t: 1 / 0                                                  # błąd modelu: 500, usługa żyje
        assert k.osadz(["a"]) is None and "500" in k.blad and k.zdrowie() is not None
        serwer.koder = wolny_koder(0.6)
        wolny = w.KlientWektorow(stan, 0.15)
        start = time.perf_counter()
        assert wolny.osadz(["query: x"]) is None and "Timeout" in wolny.blad
        assert time.perf_counter() - start < 0.5                                         # nie czeka na model
        inny = w.KlientWektorow(stan, 2.0)
        inny.model = "inny@1"                                                            # usługa z innym modelem
        serwer.koder = wolny_koder(0)
        assert inny.osadz(["a"]) is None and "inny model" in inny.blad
    assert not plik.exists()                                                             # zatrzymana: bez pliku
    assert not w.KlientWektorow(stan).dostepny and "brak state/wektory.json" in w.KlientWektorow(stan).blad
    martwy = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    stan.mkdir(exist_ok=True)
    plik.write_text(json.dumps({"port": 1, "token": "t", "model": MODEL, "pid": int(martwy.stdout)}), encoding="utf-8")
    k = w.KlientWektorow(stan)
    assert not k.dostepny and k.model == "" and "nie działa (PID" in k.blad and k.osadz(["a"]) is None


def test_cli_indeksuj_szukaj_ocena_status_z_usluga_i_bez(sk, tmp_path, capsys):
    argv = ["--skarbiec", str(sk.root), "--stan", str(sk.stan)]
    assert w.main(argv + ["indeksuj"]) == 0
    assert "usługa wektorów nie działa" in capsys.readouterr().out
    zestaw = tmp_path / "zestaw.json"
    zestaw.write_text(json.dumps([{"pytanie": "jak odstraszyć automaty?", "wzor": ["agenci/jarvo-web/formularz bez spamu"]}],
                                 ensure_ascii=False), encoding="utf-8")
    with usluga_atrapy(sk.stan):
        assert w.main(argv + ["indeksuj"]) == 0
        n = len(_szukane(w.Indeks(sk)))
        assert f"✓ wektory: {n}/{n} notatek ({n} osadzonych" in capsys.readouterr().out
        assert w.main(argv + ["szukaj", "jak odstraszyć automaty?", "--json"]) == 0
        assert json.loads(capsys.readouterr().out)[0]["sciezka"] == "agenci/jarvo-web/formularz bez spamu"
        assert w.main(argv + ["ocena", str(zestaw), "--json"]) == 0
        r = json.loads(capsys.readouterr().out)
        assert r["trafione"] == 1 and r["silniki"] == {"wektory": 1} and r["pytania"][0]["silnik"] == "wektory"
        assert w.main(argv + ["ocena", str(zestaw), "--silnik", "slowa"]) == 0
        out = capsys.readouterr().out
        assert "hit@5: 0/1" in out and "silnik: slowa 1" in out
        assert w.main(argv + ["status", "--json"]) == 0
        st = json.loads(capsys.readouterr().out)["wektory"]
        assert st["usluga"] and st["model"] == MODEL and st["wektorow"] == st["notatek"] == n
    assert w.main(argv + ["ocena", str(zestaw), "--json"]) == 0                          # bez usługi: słowa, bez błędu
    assert json.loads(capsys.readouterr().out)["silniki"] == {"slowa": 1}
    assert w.main(argv + ["status"]) == 0
    assert f"wektory: {n}/{n} notatek · usługa: nie działa" in capsys.readouterr().out
