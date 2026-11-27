"""Ścieżki Komputera Jarva (komputer/plugin/sciezki.py, narzędzie `komputer`: sciezki, zapisz_sciezke, odtworz).

Bez przeglądarki: nagranie kroku (cel numerem → napis, hasło jako znacznik), parametry jako znaczniki, wzory adresu
po kroku, plan paczek i odtworzenie na udawanym run_steps (krok, który nie pasuje, odmowa zasad, baner opcjonalny).
Z przeglądarką z manifestu (JARVO_KOMPUTER_CHROME_PROBA, jak test_komputer_cdp.py): agent przechodzi wyszukanie
z filtrem ceny na stronie testowej (ogloszenia.html), zapisuje ścieżkę, odtwarza ją jednym wywołaniem, a po zmianie
przycisku na stronie robi krok sam i ścieżka zapisuje się poprawiona; hasło nie trafia do pliku, a krok płatności
przy odtworzeniu zatrzymują twarde zasady."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))


def _modul(nazwa: str, plik: Path):
    spec = importlib.util.spec_from_file_location(nazwa, plik)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


S = _modul("jarvo_test_sciezki", REPO / "komputer" / "plugin" / "sciezki.py")


# ---------------------------------------------------------------------- bez przeglądarki

def test_nagranie_kroku_cel_numerem_napisem_haslo_znacznikiem_adres_bez_tokenu():
    w = S.wpis_kroku({"click": {"element_index": 7, "window_id": 3}}, {"role": "push button", "label": "Szukaj"},
                     "https://www.olx.pl/", "https://www.olx.pl/oferty/q-telefon/")
    assert w["krok"] == {"click": {"text": "Szukaj", "role": "push button"}} and w["domena"] == "olx.pl"
    assert w["po_adres"] == "https://www.olx.pl/oferty/q-telefon/" and not w.get("opcjonalny")
    w = S.wpis_kroku({"type_text": {"element_index": 4, "text": "Tajne-Haslo-123\n"}},
                     {"role": "password text", "label": "Hasło"}, "https://www.vinted.pl/login")
    assert w["krok"] == {"type_text": {"name": "Hasło", "role": "password text", "text": "{haslo}\n"}}
    assert w["tajne"] == ["haslo"] and "Tajne" not in json.dumps(w)
    w = S.wpis_kroku({"type_text": {"name": "Kod z SMS", "text": "123456"}}, {"role": "entry", "label": "Kod z SMS"}, "")
    assert w["krok"]["type_text"]["text"] == "{kod}"
    w = S.wpis_kroku({"navigate": {"url": "https://x.pl/a?q=1&token=abc123&sessionid=z#access_token=q"}}, None, "")
    assert w["krok"]["navigate"]["url"] == "https://x.pl/a?q=1"
    assert S.wpis_kroku({"click": {"element_index": 9}}, {"role": "push button", "label": ""}, "")["uwaga"] == "numer"
    assert S.wpis_kroku({"click": {"text": "Akceptuję wszystkie"}}, None, "").get("opcjonalny")
    assert not S.wpis_kroku({"click": {"text": "Xiaomi Redmi"}}, None, "").get("opcjonalny")


def _sciezka_olx() -> dict:
    nagranie = [
        S.wpis_kroku({"navigate": {"url": "https://www.olx.pl/"}}, None, "", "https://www.olx.pl/"),
        S.wpis_kroku({"click": {"text": "Akceptuję"}}, {"role": "push button", "label": "Akceptuję"},
                     "https://www.olx.pl/"),
        S.wpis_kroku({"type_text": {"name": "Czego szukasz?", "text": "telefon\n"}}, None, "https://www.olx.pl/",
                     "https://www.olx.pl/oferty/q-telefon/"),
        S.wpis_kroku({"navigate": {"url": "https://www.olx.pl/oferty/q-telefon/?search%5Bfilter_float_price"
                                          "%3Afrom%5D=60&search%5Bfilter_float_price%3Ato%5D=80"}}, None,
                     "https://www.olx.pl/oferty/q-telefon/", "https://www.olx.pl/oferty/q-telefon/?x=1"),
    ]
    wartosci = {"fraza": "telefon", "cena_od": "60", "cena_do": "80"}
    return S.nowa_sciezka("olx szukaj", S.kroki_sciezki(S.odcinek(nagranie), wartosci), wartosci,
                          "wyszukanie z ceną", "Znaleźliśmy")


def test_zapis_parametry_jako_znaczniki_i_wzor_adresu_po_kroku():
    sc = _sciezka_olx()
    kroki = sc["kroki"]
    assert sc["domena"] == "olx.pl" and len(kroki) == 4
    assert kroki[1]["opcjonalny"] and kroki[2]["krok"]["type_text"]["text"] == "{fraza}\n"
    assert kroki[2]["po"] == "*olx.pl/oferty/q-*/*"
    assert kroki[3]["krok"]["navigate"]["url"] == ("https://www.olx.pl/oferty/q-{fraza|-}/?search[filter_float_price"
                                                   ":from]={cena_od}&search[filter_float_price:to]={cena_do}")
    assert sc["parametry"] == {"cena_do": {"przyklad": "80"}, "cena_od": {"przyklad": "60"},
                               "fraza": {"przyklad": "telefon"}}
    krok = S.wypelnij(kroki[3]["krok"], {"fraza": "rower miejski", "cena_od": "10", "cena_do": "20"})
    assert krok["navigate"]["url"] == ("https://www.olx.pl/oferty/q-rower-miejski/?search[filter_float_price:from]=10"
                                       "&search[filter_float_price:to]=20")


def test_skrot_tylko_gdy_adres_niesie_wszystkie_parametry_i_kliki_zmieniaja_adres():
    wartosci = {"fraza": "telefon", "cena_od": "60"}
    start = S.wpis_kroku({"navigate": {"url": "https://www.olx.pl/"}}, None, "", "https://www.olx.pl/")
    szukaj = S.wpis_kroku({"type_text": {"name": "Szukaj", "text": "telefon\n"}}, None, "https://www.olx.pl/",
                          "https://www.olx.pl/oferty/q-telefon/")
    cena = S.wpis_kroku({"type_text": {"name": "Od", "text": "60\n"}}, None, "https://www.olx.pl/oferty/q-telefon/",
                        "https://www.olx.pl/oferty/q-telefon/?search%5Bfilter_float_price%3Afrom%5D=60")
    ulubione = S.wpis_kroku({"click": {"text": "Obserwuj"}}, None, "https://www.olx.pl/oferty/q-telefon/")
    czekaj = S.wpis_kroku({"wait_for": {"text": "Znaleźliśmy"}}, None, "")
    assert S.skrot([start, szukaj, cena, czekaj], wartosci) == (
        "https://www.olx.pl/oferty/q-{fraza|-}/?search[filter_float_price:from]={cena_od}")
    assert S.skrot([start, szukaj, czekaj], wartosci) == ""                 # cena nie jest w adresie
    assert S.skrot([start, szukaj, cena, ulubione], wartosci) == ""         # klik zmienia stan, nie adres
    haslo = S.wpis_kroku({"type_text": {"name": "Hasło", "text": "x"}}, {"role": "password text", "label": "Hasło"}, "")
    assert S.skrot([start, haslo, szukaj, cena], wartosci) == ""
    kroki = S.kroki_sciezki([start, szukaj, cena, czekaj], wartosci)
    sc = S.nowa_sciezka("olx", kroki, wartosci, sprawdz="Znaleźliśmy", skrot=S.skrot([start, szukaj, cena], wartosci))
    u = Udawany()
    w = S.odtworz(sc, {"fraza": "rower miejski"}, 1, u, None, ze_skrotem=True)
    assert w["ok"] and w["skrot"].startswith("https://www.olx.pl/oferty/q-rower-miejski/?search[") and \
        len(u.wywolania) == 1 and u.wywolania[0]["steps"][1]["wait_for"]["text"] == "Znaleźliśmy", w
    assert "skrot" not in S.nowa_sciezka("olx", kroki, wartosci, skrot="https://www.olx.pl/q-{fraza}")   # bez sprawdz
    u = Udawany(zmienione={"Znaleźliśmy"})          # pod skrótem strona inna: cała ścieżka krok po kroku
    w = S.odtworz(sc, {}, 1, u, None, ze_skrotem=True)
    assert w["ok"] and not w.get("skrot") and w["skrot_nie"].startswith("czas_minal") and len(u.wywolania) == 2, w


def test_sekret_nie_trafia_do_pliku(tmp_path):
    wpisy = [S.wpis_kroku({"navigate": {"url": "https://x.pl/login"}}, None, ""),
             S.wpis_kroku({"type_text": {"name": "E-mail", "text": "jan@example.com"}}, None, "https://x.pl/login"),
             S.wpis_kroku({"type_text": {"name": "Hasło", "text": "Tajne-Haslo-123\n"}},
                          {"role": "password text", "label": "Hasło"}, "https://x.pl/login")]
    sc = S.nowa_sciezka("x logowanie", S.kroki_sciezki(wpisy, {"email": "jan@example.com"}), {"email": "jan@example.com"})
    assert sc["parametry"]["haslo"]["tajny"] and "przyklad" not in sc["parametry"]["haslo"]
    S.zapisz(sc, tmp_path / S.PLIK)
    tekst = (tmp_path / S.PLIK).read_text(encoding="utf-8")
    assert "Tajne-Haslo-123" not in tekst and "{haslo}" in tekst
    with pytest.raises(S.BladSciezki):
        S.nowa_sciezka("x klucz", [{"krok": {"navigate": {"url": "https://x.pl/k/sk-proj-ABCDEFGHIJKLMNOPQRSTUV"}}}], {})
    assert S.wczytaj(tmp_path / S.PLIK).keys() == {"x logowanie"}


class Udawany:
    """run_steps jak sterownik: kroki po kolei, pierwszy z napisem z `brak` to brak_celu, z `platnosc` odmowa zasad."""

    def __init__(self, brak=(), platnosc=(), baner=False, zmienione=()):
        self.brak, self.platnosc, self.baner, self.wywolania = set(brak), set(platnosc), baner, []
        self.zmienione = set(zmienione)                 # raz: odmowa element_zmieniony (reklama przesunęła stronę)

    def __call__(self, args: dict) -> dict:
        self.wywolania.append(args)
        raporty = []
        for i, krok in enumerate(args["steps"]):
            nazwa, a, pola = S.rozbierz(krok)
            napis = S.cel_kroku(nazwa, a)
            czeka = (pola.get("wait_for") or {}).get("text") if nazwa is None else None
            if czeka in self.zmienione:
                self.zmienione.discard(czeka)
                raporty.append({"index": i, "ok": False, "phase": "wait_for", "code": "czas_minal",
                                "message": "tekstu nie ma"})
                break
            if napis in self.zmienione:
                self.zmienione.discard(napis)
                raporty.append({"index": i, "ok": False, "code": "zablokowane", "rule": "element_zmieniony",
                                "decision": "odmowa", "next_step": "fresh_state", "message": "strona zmieniła się"})
                break
            if napis in self.platnosc:
                raporty.append({"index": i, "ok": False, "code": "wymaga_czlowieka", "decision": "czlowiek",
                                "next_step": "ask_owner", "message": "krok właściciela"})
                break
            if napis in self.brak or (napis == "Akceptuję" and not self.baner):
                raporty.append({"index": i, "ok": False, "phase": "find", "code": "brak_celu", "message": "brak"})
                if args.get("stop_on") != "refusal":
                    break
                continue
            raporty.append({"index": i, "ok": True, "message": "ok"})
        stop = next((r["index"] for r in raporty if not r["ok"] and (r.get("decision") or args.get("stop_on") != "refusal")),
                    None)
        return {"structuredContent": {"steps": raporty, "failed_step": stop, "observation": {
            "ok": True, "snapshot_id": "m1", "url": "https://www.olx.pl/", "elements": []}}, "isError": stop is not None}


def test_odtworzenie_paczkami_baner_opcjonalny_i_weryfikacja_adresu():
    sc = _sciezka_olx()
    u = Udawany()
    w = S.odtworz(sc, {"fraza": "rower"}, 1, u, {"max_elements": 50})
    assert w["ok"] and w["wykonane"] == [0, 2, 3] and w["pominiete"] == [1], w
    assert w["wartosci"] == {"fraza": "rower", "cena_od": "60", "cena_do": "80"}       # przykłady z zapisu
    assert [a["stop_on"] for a in u.wywolania] == ["error", "refusal", "error"]
    ostatnia = u.wywolania[-1]["steps"]
    assert ostatnia[0]["type_text"]["text"] == "rower\n" and ostatnia[0]["timeout_ms"] == S.CZAS_CELU
    assert ostatnia[1]["wait_for"] == {"url": "*olx.pl/oferty/q-*/*", "timeout_ms": S.CZAS_PO}   # adres po kroku 3
    assert ostatnia[-1] == {"wait_for": {"text": "Znaleźliśmy", "timeout_ms": S.CZAS_PO}}


def test_krok_ktory_nie_pasuje_i_odmowa_zasad_koncza_odtworzenie():
    sc = _sciezka_olx()
    w = S.odtworz(sc, {}, 1, Udawany(brak={"Czego szukasz?"}), None)
    assert not w["ok"] and (w["stop"], w["rodzaj"]) == (2, "cel") and w["wykonane"] == [0], w
    sc["kroki"].insert(3, {"krok": {"click": {"text": "Kup teraz"}}})
    w = S.odtworz(sc, {}, 1, Udawany(platnosc={"Kup teraz"}), None)
    assert (w["stop"], w["rodzaj"], w["decision"], w["next_step"]) == (3, "zasady", "czlowiek", "ask_owner")
    w = S.odtworz(sc, {}, 5, Udawany(), None)                        # od kroku 5: bez kroku płatności
    assert w["ok"] and w["wykonane"] == [4]
    u = Udawany(zmienione={"Czego szukasz?"})                         # reklama między celem a klikiem: ponowienie
    w = S.odtworz(_sciezka_olx(), {}, 1, u, None)
    assert w["ok"] and w["wykonane"] == [0, 2, 3] and len(u.wywolania) == 4, w


def test_tajny_parametr_bez_wartosci_oddaje_krok_agentowi():
    wpisy = [S.wpis_kroku({"navigate": {"url": "https://x.pl/login"}}, None, ""),
             S.wpis_kroku({"type_text": {"name": "Hasło", "text": "Tajne-Haslo-123\n"}},
                          {"role": "password text", "label": "Hasło"}, "https://x.pl/login"),
             S.wpis_kroku({"click": {"text": "Moje konto"}}, None, "https://x.pl/login")]
    sc = S.nowa_sciezka("x logowanie", S.kroki_sciezki(wpisy, {}), {})
    u = Udawany()
    w = S.odtworz(sc, {}, 1, u, None)
    assert (w["stop"], w["rodzaj"], w["wykonane"]) == (1, "parametr", [0]) and len(u.wywolania) == 1
    w = S.odtworz(sc, {"haslo": "Inne-Haslo-9"}, 1, Udawany(), None)
    assert w["ok"] and w["wartosci"] == {}                           # hasło nie wraca w wyniku


# ---------------------------------------------------------------------- na prawdziwej przeglądarce

PROGRAM = os.environ.get("JARVO_KOMPUTER_CHROME_PROBA") or ""
na_zywo = pytest.mark.skipif(not (PROGRAM and Path(PROGRAM).is_file()),
                             reason="potrzebna przeglądarka z manifestu: JARVO_KOMPUTER_CHROME_PROBA")
from test_komputer_cdp import przegl  # noqa: E402,F401 - ta sama przeglądarka testowa (fixture modułu)


@pytest.fixture
def wtyczka(przegl, monkeypatch):
    """Wtyczka Jarva przez bramkę floty i kanał `cua` do wejścia z zasadami (jak test_komputer_cdp), HERMES_HOME
    w katalogu tymczasowym (plik ścieżek agenta)."""
    from jarvo import komputer as jk
    from jarvo import sciezki
    from komputer import kanal, wejscie_natywne
    st, _, _ = przegl
    root = Path(tempfile.mkdtemp(prefix="jks"))
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
    monkeypatch.setenv("HERMES_HOME", str(root / "profil"))
    monkeypatch.delenv("JARVO_KOMPUTER_GNIAZDO", raising=False)
    monkeypatch.setenv("JARVO_KOMPUTER_GRUPA", "grupa-testowa-sciezek-0123456789")
    wt = _modul("jarvo_test_wtyczka_sciezki", REPO / "komputer" / "plugin" / "__init__.py")
    try:
        yield wt, st, root / "profil" / S.PLIK
    finally:
        wt._zamknij_wszystkie()
        serwer.zamknij()
        shutil.rmtree(root, ignore_errors=True)


def _js(st, wyrazenie: str):
    w = st.b.wyslij("Runtime.evaluate", {"expression": wyrazenie, "returnByValue": True},
                    st.okno(st.aktywne_okno()).sesja, czas=30)
    return (w.get("result") or {}).get("value")


@na_zywo
def test_zapis_odtworzenie_i_samonaprawa_na_stronie_testowej(wtyczka):
    wt, st, plik = wtyczka

    def k(**args):
        return wt.obsluz(args, session_id="agent")

    odp = k(akcja="idz", adres="https://sklep.jarvo.test/ogloszenia.html")
    assert odp.startswith("ok: okno"), odp
    _js(st, "localStorage.clear()")
    k(akcja="idz", adres="https://sklep.jarvo.test/ogloszenia.html")
    odp = k(akcja="patrz")
    assert "dialog „Zgoda na ciasteczka”" in odp, odp
    nr = next(linia.split("]")[0].strip().lstrip("*[") for linia in odp.splitlines() if "„Akceptuję”" in linia)
    odp = k(akcja="kroki", kroki=[
        {"click": {"element_index": int(nr)}},
        {"type_text": {"name": "Czego szukasz?", "text": "telefon"}},
        {"type_text": {"name": "Cena od", "text": "60"}},
        {"type_text": {"name": "Cena do", "text": "80"}},
        {"click": {"text": "Szukaj", "role": "button"}},
        {"wait_for": {"text": "Znaleziono"}}], obserwuj=True)
    assert "run_steps: 6/6 kroków ok" in odp and "Znaleziono 2 ogłoszeń od 60 do 80 zł" in odp, odp
    odp = k(akcja="sciezki")
    assert "ścieżki: 0" in odp and "8. czekaj na „Znaleziono”" in odp, odp            # dwa razy idz: jedno w zapisie
    odp = k(akcja="zapisz_sciezke", nazwa="ogloszenia szukaj", opis="wyszukanie z ceną",
            parametry={"fraza": "telefon", "cena_od": "60", "cena_do": "80"}, sprawdz="Znaleziono")
    assert odp.startswith("ok: ścieżka zapisana") and "klik „Akceptuję” (push button) (opcjonalny)" in odp, odp
    zapis = json.loads(plik.read_text(encoding="utf-8"))["sciezki"]["ogloszenia szukaj"]
    assert [x["krok"].get("type_text", {}).get("text") for x in zapis["kroki"][2:5]] == [
        "{fraza}", "{cena_od}", "{cena_do}"]
    assert zapis["kroki"][5]["po"] == "*sklep.jarvo.test/wyniki.html*", zapis
    assert zapis["skrot"] == "https://sklep.jarvo.test/wyniki.html?q={fraza}&od={cena_od}&do={cena_do}", zapis

    # drugi raz: jedno wywołanie; skrót (sam adres wyników i „Znaleziono”), nowa cena
    odp = k(akcja="odtworz", nazwa="ogloszenia szukaj", parametry={"cena_od": "70"})
    assert odp.startswith("ok: ścieżka „ogloszenia szukaj” skrótem https://sklep.jarvo.test/wyniki.html?q=telefon&od=70"
                          "&do=80"), odp
    assert "Znaleziono 1 ogłoszeń od 70 do 80 zł" in odp and "Telefon Motorola" in odp, odp
    # cała ścieżka (z `od`): baneru już nie ma (zgoda zapamiętana), krok opcjonalny pominięty
    odp = k(akcja="odtworz", nazwa="ogloszenia szukaj", od=1)
    assert odp.startswith("ok: ścieżka „ogloszenia szukaj” kroki 1–7: 6 zrobione") and \
        "pominięte opcjonalne (nie było celu): 2" in odp and "Znaleziono 2 ogłoszeń od 60 do 80 zł" in odp, odp

    # strona zmieniona: przycisk wyszukania ma inny napis → krok 6 wraca do agenta z widokiem strony
    _js(st, "localStorage.wersja = '2'")
    odp = k(akcja="odtworz", nazwa="ogloszenia szukaj", parametry={"cena_od": "60"}, od=1)
    assert "krok 6 z 7 (klik „Szukaj” (button)) nie pasuje do strony: BŁĄD brak_celu" in odp, odp
    assert "Samonaprawa" in odp and "\"od\": 7" in odp and "„Pokaż ogłoszenia”" in odp, odp
    odp = k(akcja="kroki", kroki=[{"click": {"text": "Pokaż ogłoszenia"}}])
    assert "1/1 kroków ok" in odp, odp
    odp = k(akcja="odtworz", nazwa="ogloszenia szukaj", od=7)
    assert odp.startswith("ok:") and "samonaprawa: ścieżka poprawiona i zapisana" in odp, odp
    zapis = json.loads(plik.read_text(encoding="utf-8"))["sciezki"]["ogloszenia szukaj"]
    assert zapis["kroki"][5]["krok"]["click"]["text"] == "Pokaż ogłoszenia" and zapis["naprawy"] == 1, zapis
    odp = k(akcja="odtworz", nazwa="ogloszenia szukaj", parametry={"fraza": "rower", "cena_od": "1"})
    assert odp.startswith("ok:") and "Rower miejski" in odp, odp
    assert json.loads(plik.read_text(encoding="utf-8"))["sciezki"]["ogloszenia szukaj"]["uzycia"] == 4
    _js(st, "localStorage.clear()")


@na_zywo
def test_haslo_poza_plikiem_i_platnosc_przy_odtworzeniu_staje(wtyczka):
    wt, st, plik = wtyczka

    def k(**args):
        return wt.obsluz(args, session_id="agent-2")

    k(akcja="idz", adres="https://sklep.jarvo.test/formularz.html")
    odp = k(akcja="kroki", kroki=[{"type_text": {"name": "E-mail", "text": "jan@example.com"}},
                                  {"type_text": {"name": "Hasło do konta", "text": "Tajne-Haslo-123"}},
                                  {"click": {"text": "Sprawdź dane"}}, {"wait_for": {"text": "Dane sprawdzone"}}])
    assert "4/4 kroków ok" in odp, odp
    odp = k(akcja="zapisz_sciezke", nazwa="formularz konto", parametry={"email": "jan@example.com"})
    assert odp.startswith("ok:") and "haslo (tajny)" in odp, odp
    tekst = plik.read_text(encoding="utf-8")
    assert "Tajne-Haslo-123" not in tekst and "{haslo}" in tekst and "jan@example.com" in tekst   # e-mail: przykład
    odp = k(akcja="odtworz", nazwa="formularz konto")
    assert "krok 3 (pisz „{haslo}” w „Hasło do konta”" in odp and "wartość tajną" in odp and "\"od\": 4" in odp, odp
    odp = k(akcja="odtworz", nazwa="formularz konto", parametry={"haslo": "Inne-Haslo-456"})
    assert odp.startswith("ok:") and "Dane sprawdzone" in odp and "Inne-Haslo-456" not in odp, odp
    assert "Inne-Haslo-456" not in plik.read_text(encoding="utf-8")

    # ścieżka z krokiem płatności (zapisana, gdy była zgoda): przy odtworzeniu bez zgody stoi na nim
    sc = json.loads(plik.read_text(encoding="utf-8"))
    sc["sciezki"]["wyniki kup"] = {
        "nazwa": "wyniki kup", "domena": "sklep.jarvo.test", "parametry": {"fraza": {"przyklad": "telefon"}},
        "kroki": [{"krok": {"navigate": {"url": "https://sklep.jarvo.test/wyniki.html?q={fraza}&od=60&do=70"}}},
                  {"krok": {"click": {"text": "Kup teraz za 65 zł"}}},
                  {"krok": {"click": {"text": "Dodaj do ulubionych: Telefon Samsung"}}}]}
    plik.write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
    odp = k(akcja="odtworz", nazwa="wyniki kup")
    assert "krok 2 (klik „Kup teraz za 65 zł”) zatrzymały twarde zasady: BŁĄD wymaga_czlowieka" in odp, odp
    assert "akcja=oddaj" in odp and "\"od\": 3" in odp, odp
    assert _js(st, "document.getElementById('wynik').textContent") == "Nic nie kliknięto"      # krok 3 nie poszedł
    odp = k(akcja="odtworz", nazwa="wyniki kup", od=3)
    assert odp.startswith("ok:") and "W ulubionych: Telefon Samsung" in odp, odp
